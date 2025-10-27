#!/usr/bin/env python3
"""
Cross-platform Playwright Watchdog with CDP support.
Tracks Playwright process lifecycle, logs events as JSONL, and correlates artifacts.
"""

import os
import sys
import json
import time
import psutil
import platform
import threading
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime
import signal

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuration from environment
WATCHDOG_DIR = Path(os.getenv('PW_WATCHDOG_DIR', Path.home() / '.pw_watchdog'))
LOG_DIR = WATCHDOG_DIR / 'logs'
CDP_DIR = WATCHDOG_DIR / 'cdp'
REPORTS_DIR = WATCHDOG_DIR / 'reports'
TMP_DIR = WATCHDOG_DIR / 'tmp'

POLL_INTERVAL = float(os.getenv('PW_WATCHDOG_POLL_INTERVAL', '0.5'))
LOG_MAX_SIZE = int(os.getenv('PW_WATCHDOG_LOG_MAX_SIZE', str(10 * 1024 * 1024)))  # 10MB
LOG_BACKUPS = int(os.getenv('PW_WATCHDOG_LOG_BACKUPS', '5'))
STDOUT_LOGGING = os.getenv('PW_WATCHDOG_STDOUT', '1') == '1'
USE_NETLINK = os.getenv('PW_WATCHDOG_USE_NETLINK', 'auto')

# Process detection patterns
NODE_PATTERNS = [
    r'node.*playwright.*test',
    r'npx\s+playwright\s+test',
    r'playwright\s+test',
]
PYTHON_PATTERNS = [
    r'pytest.*playwright',
    r'pytest.*--browser',
    r'python.*-m\s+pytest.*playwright',
]

@dataclass
class ProcessInfo:
    pid: int
    ppid: int
    cmdline: List[str]
    cwd: str
    user: str
    start_time: float
    run_id: Optional[str] = None
    engine: Optional[str] = None
    cdp_info: Optional[Dict[str, Any]] = None


class RotatingJSONLHandler:
    """Simple size-based rotating JSONL file handler."""
    
    def __init__(self, filepath: Path, max_size: int, backup_count: int):
        self.filepath = filepath
        self.max_size = max_size
        self.backup_count = backup_count
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        
    def write(self, event: Dict[str, Any]):
        """Write JSON event and rotate if needed."""
        line = json.dumps(event, default=str) + '\n'
        
        # Check size and rotate if needed
        if self.filepath.exists() and self.filepath.stat().st_size + len(line) > self.max_size:
            self._rotate()
        
        with open(self.filepath, 'a') as f:
            f.write(line)
            
    def _rotate(self):
        """Rotate log files."""
        for i in range(self.backup_count - 1, 0, -1):
            old = self.filepath.with_suffix(f'.jsonl.{i}')
            new = self.filepath.with_suffix(f'.jsonl.{i + 1}')
            if old.exists():
                old.replace(new)
        
        if self.filepath.exists():
            self.filepath.replace(self.filepath.with_suffix('.jsonl.1'))


class PlaywrightWatchdog:
    """Main watchdog service."""
    
    def __init__(self):
        self.os_name = platform.system()
        self.tracked_processes: Dict[int, ProcessInfo] = {}
        self.lock = threading.Lock()
        self.running = False
        self.logger = self._setup_logging()
        self.jsonl_handler = RotatingJSONLHandler(
            LOG_DIR / 'watchdog.jsonl',
            LOG_MAX_SIZE,
            LOG_BACKUPS
        )
        
        # Ensure runtime directories exist
        for directory in [LOG_DIR, CDP_DIR, REPORTS_DIR, TMP_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Watchdog initialized on {self.os_name}")
        
    def _setup_logging(self) -> logging.Logger:
        """Setup Python logging for internal watchdog logs."""
        logger = logging.getLogger('playwright_watchdog')
        logger.setLevel(logging.INFO)
        
        if STDOUT_LOGGING:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter(
                '%(asctime)s [%(levelname)s] %(message)s'
            ))
            logger.addHandler(handler)
        
        return logger
    
    def _is_playwright_process(self, proc: psutil.Process) -> bool:
        """Check if process is a Playwright run."""
        try:
            cmdline = ' '.join(proc.cmdline())
            
            # Check Node patterns
            for pattern in NODE_PATTERNS:
                if re.search(pattern, cmdline, re.IGNORECASE):
                    return True
            
            # Check Python patterns
            for pattern in PYTHON_PATTERNS:
                if re.search(pattern, cmdline, re.IGNORECASE):
                    return True
            
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def _extract_run_id(self, proc: psutil.Process) -> str:
        """Extract or generate runId for a process."""
        try:
            # Check environment variable
            env = proc.environ()
            if 'PW_WATCHDOG_RUN_ID' in env:
                return env['PW_WATCHDOG_RUN_ID']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        # Generate from pid and start time
        start_time_ms = int(proc.create_time() * 1000)
        return f"{proc.pid}-{start_time_ms}"
    
    def _get_process_info(self, proc: psutil.Process) -> Optional[ProcessInfo]:
        """Extract detailed process information."""
        try:
            return ProcessInfo(
                pid=proc.pid,
                ppid=proc.ppid(),
                cmdline=proc.cmdline(),
                cwd=proc.cwd(),
                user=proc.username(),
                start_time=proc.create_time()
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self.logger.warning(f"Failed to get info for pid {proc.pid}: {e}")
            return None
    
    def _read_cdp_info(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Read CDP metadata written by injector."""
        cdp_file = CDP_DIR / f"{run_id}.json"
        
        # Poll for a few seconds in case injector is still writing
        for _ in range(10):
            if cdp_file.exists():
                try:
                    with open(cdp_file) as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    self.logger.warning(f"Failed to read CDP info: {e}")
                    return None
            time.sleep(0.5)
        
        return None
    
    def _detect_engine(self, proc_info: ProcessInfo) -> str:
        """Detect browser engine from command line."""
        cmdline = ' '.join(proc_info.cmdline)
        
        if '--browser=chromium' in cmdline or 'chromium' in cmdline.lower():
            return 'chromium'
        elif '--browser=firefox' in cmdline or 'firefox' in cmdline.lower():
            return 'firefox'
        elif '--browser=webkit' in cmdline or 'webkit' in cmdline.lower():
            return 'webkit'
        
        # Default to chromium for most Playwright runs
        return 'chromium'
    
    def _emit_event(self, event: Dict[str, Any]):
        """Emit JSONL event to log file and optionally stdout."""
        event['ts'] = datetime.utcnow().isoformat() + 'Z'
        
        self.jsonl_handler.write(event)
        
        if STDOUT_LOGGING:
            print(json.dumps(event, default=str))
    
    def _on_process_start(self, proc: psutil.Process):
        """Handle Playwright process start."""
        proc_info = self._get_process_info(proc)
        if not proc_info:
            return
        
        run_id = self._extract_run_id(proc)
        proc_info.run_id = run_id
        proc_info.engine = self._detect_engine(proc_info)
        
        with self.lock:
            self.tracked_processes[proc.pid] = proc_info
        
        self.logger.info(f"Playwright started: pid={proc.pid}, runId={run_id}")
        
        # Try to read CDP info (may not be available immediately)
        threading.Thread(
            target=self._emit_start_event_async,
            args=(proc_info,),
            daemon=True
        ).start()
    
    def _emit_start_event_async(self, proc_info: ProcessInfo):
        """Emit start event after attempting to read CDP info."""
        cdp_info = self._read_cdp_info(proc_info.run_id)
        proc_info.cdp_info = cdp_info
        
        event = {
            'event': 'playwright_started',
            'runId': proc_info.run_id,
            'os': self.os_name,
            'pid': proc_info.pid,
            'ppid': proc_info.ppid,
            'cmdline': proc_info.cmdline,
            'cwd': proc_info.cwd,
            'user': proc_info.user,
            'engine': proc_info.engine,
        }
        
        if cdp_info:
            event['cdp'] = cdp_info
        
        self._emit_event(event)
    
    def _parse_artifacts(self, proc_info: ProcessInfo) -> Dict[str, Any]:
        """Parse artifacts from report files."""
        artifacts = {}
        
        # Try to find report file
        report_file = None
        
        # Check for Node JSON report
        json_report = REPORTS_DIR / f"{proc_info.run_id}.json"
        if json_report.exists():
            report_file = str(json_report)
            artifacts['reportFile'] = report_file
            
            # Parse Playwright Test JSON report for failures
            try:
                with open(json_report) as f:
                    report_data = json.load(f)
                    
                # Extract trace/screenshot paths if present
                if 'suites' in report_data:
                    for suite in report_data.get('suites', []):
                        for spec in suite.get('specs', []):
                            for test in spec.get('tests', []):
                                for result in test.get('results', []):
                                    if result.get('status') == 'failed':
                                        # Collect attachments
                                        for attachment in result.get('attachments', []):
                                            name = attachment.get('name', '')
                                            path = attachment.get('path', '')
                                            
                                            if 'trace' in name.lower() and path:
                                                artifacts.setdefault('traces', []).append(path)
                                            elif 'screenshot' in name.lower() and path:
                                                artifacts.setdefault('screenshots', []).append(path)
                                            elif 'video' in name.lower() and path:
                                                artifacts['video'] = path
            except (json.JSONDecodeError, IOError, KeyError) as e:
                self.logger.warning(f"Failed to parse JSON report: {e}")
        
        # Check for Python JUnit XML report
        xml_report = REPORTS_DIR / f"{proc_info.run_id}.xml"
        if xml_report.exists():
            report_file = str(xml_report)
            artifacts['reportFile'] = report_file
        
        return artifacts
    
    def _extract_error_summary(self, proc_info: ProcessInfo, exit_code: int) -> Optional[Dict[str, Any]]:
        """Extract error summary from report if available."""
        json_report = REPORTS_DIR / f"{proc_info.run_id}.json"
        
        if json_report.exists():
            try:
                with open(json_report) as f:
                    report_data = json.load(f)
                    
                # Find first failure
                for suite in report_data.get('suites', []):
                    for spec in suite.get('specs', []):
                        for test in spec.get('tests', []):
                            for result in test.get('results', []):
                                if result.get('status') == 'failed':
                                    error = result.get('error', {})
                                    return {
                                        'title': f"{spec.get('title', '')} > {test.get('title', '')}",
                                        'message': error.get('message', ''),
                                        'stack': error.get('stack', '')
                                    }
            except (json.JSONDecodeError, IOError, KeyError):
                pass
        
        # Fallback: generic error based on exit code
        if exit_code != 0:
            return {
                'title': 'Test failed',
                'message': f'Process exited with code {exit_code}',
                'stack': ''
            }
        
        return None
    
    def _on_process_exit(self, pid: int, exit_code: int):
        """Handle Playwright process exit."""
        with self.lock:
            proc_info = self.tracked_processes.pop(pid, None)
        
        if not proc_info:
            return
        
        duration_ms = int((time.time() - proc_info.start_time) * 1000)
        
        self.logger.info(f"Playwright exited: pid={pid}, runId={proc_info.run_id}, exitCode={exit_code}")
        
        artifacts = self._parse_artifacts(proc_info)
        
        if exit_code == 0:
            event = {
                'event': 'playwright_succeeded',
                'runId': proc_info.run_id,
                'pid': pid,
                'exitCode': exit_code,
                'durationMs': duration_ms,
                'artifacts': artifacts
            }
        else:
            error = self._extract_error_summary(proc_info, exit_code)
            event = {
                'event': 'playwright_failed',
                'runId': proc_info.run_id,
                'pid': pid,
                'exitCode': exit_code,
                'durationMs': duration_ms,
                'artifacts': artifacts
            }
            if error:
                event['error'] = error
        
        self._emit_event(event)
        
        # Cleanup old CDP metadata
        self._cleanup_old_cdp_files()
    
    def _cleanup_old_cdp_files(self):
        """Remove CDP metadata files older than 24 hours."""
        try:
            cutoff = time.time() - (24 * 3600)
            for cdp_file in CDP_DIR.glob('*.json'):
                if cdp_file.stat().st_mtime < cutoff:
                    cdp_file.unlink()
        except OSError:
            pass
    
    def _poll_processes(self):
        """Poll-based process tracking (fallback)."""
        known_pids = set()
        
        while self.running:
            try:
                current_pids = set()
                
                for proc in psutil.process_iter(['pid']):
                    try:
                        if self._is_playwright_process(proc):
                            current_pids.add(proc.pid)
                            
                            if proc.pid not in known_pids:
                                # New process
                                self._on_process_start(proc)
                                known_pids.add(proc.pid)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                # Check for terminated processes
                terminated = known_pids - current_pids
                for pid in terminated:
                    # Try to get exit code (best effort)
                    exit_code = -1
                    try:
                        proc = psutil.Process(pid)
                        status = proc.status()
                        if status == psutil.STATUS_ZOMBIE:
                            exit_code = proc.wait(timeout=1)
                    except:
                        pass
                    
                    self._on_process_exit(pid, exit_code)
                    known_pids.discard(pid)
                
            except Exception as e:
                self.logger.error(f"Error in poll loop: {e}")
            
            time.sleep(POLL_INTERVAL)
    
    def _use_wmi_windows(self):
        """Windows WMI-based process tracking."""
        try:
            import wmi
            c = wmi.WMI()
            
            self.logger.info("Using Windows WMI for process tracking")
            
            # Watch for process creation
            process_watcher = c.Win32_Process.watch_for("creation")
            process_termination = c.Win32_ProcessStopTrace.watch_for("operation")
            
            while self.running:
                try:
                    # Check for new processes
                    new_proc = process_watcher(timeout_ms=100)
                    if new_proc:
                        try:
                            proc = psutil.Process(new_proc.ProcessId)
                            if self._is_playwright_process(proc):
                                self._on_process_start(proc)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    
                    # Check for terminated processes
                    term_proc = process_termination(timeout_ms=100)
                    if term_proc:
                        pid = term_proc.ProcessId
                        exit_code = getattr(term_proc, 'ExitStatus', -1)
                        if pid in self.tracked_processes:
                            self._on_process_exit(pid, exit_code)
                
                except wmi.x_wmi_timed_out:
                    continue
                except Exception as e:
                    self.logger.error(f"WMI error: {e}")
                    time.sleep(1)
                    
        except ImportError:
            self.logger.warning("WMI not available, falling back to polling")
            self._poll_processes()
    
    def _use_netlink_linux(self):
        """Linux netlink proc connector (requires root)."""
        try:
            from pyroute2 import IPRoute
            self.logger.info("Netlink process tracking not yet implemented, using polling")
            self._poll_processes()
        except ImportError:
            self.logger.warning("pyroute2 not available, using polling")
            self._poll_processes()
    
    def start(self):
        """Start the watchdog service."""
        self.running = True
        self.logger.info("Watchdog service starting...")
        
        try:
            if self.os_name == 'Windows':
                self._use_wmi_windows()
            elif self.os_name == 'Linux':
                if USE_NETLINK == 'true' and os.geteuid() == 0:
                    self._use_netlink_linux()
                else:
                    self.logger.info("Using polling-based process tracking")
                    self._poll_processes()
            else:
                self.logger.info("Using polling-based process tracking")
                self._poll_processes()
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the watchdog service."""
        self.running = False
        self.logger.info("Watchdog service stopped")


def main():
    """Main entry point."""
    watchdog = PlaywrightWatchdog()
    
    # Handle signals
    def signal_handler(signum, frame):
        watchdog.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    watchdog.start()


if __name__ == '__main__':
    main()


