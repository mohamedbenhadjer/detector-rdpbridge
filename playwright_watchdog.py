#!/usr/bin/env python3
"""
Cross-platform Playwright watchdog that detects runs, discovers CDP, and logs failures.
Works on Windows (WMI) and Linux (proc connector; falls back to /proc polling if not root).

This tool does not wrap your Playwright command and does not edit your test code.
Optionally pair with runtime injectors to ensure Chromium exposes a CDP port:
 - Node:   NODE_OPTIONS=--require /path/to/injectors/pw_injector.js
 - Python: PYTHONPATH=/path/to/injectors/pw_py_inject  (sitecustomize)

Logs JSON lines to ~/.pw_watchdog/logs/watchdog.jsonl
"""
import argparse
import hashlib
import json
import os
import platform
import re
import socket
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any


# Detection patterns for Playwright invocations
PLAYWRIGHT_PATTERNS = [
    r"\bplaywright\b",
    r"@playwright/test",
    r"\bnpx\b\s+playwright\b",
    r"\bnode\b.*@playwright/test",
    r"\bpytest\b.*playwright",
    r"\bpython\b.*playwright",
    r"\b(chromium|chrome|chrome-stable)\b.*--remote-debugging-port",
]


WATCHDOG_DIR = Path.home() / ".pw_watchdog"
CDP_DIR = WATCHDOG_DIR / "cdp"
REPORTS_DIR = WATCHDOG_DIR / "reports"
LOGS_DIR = WATCHDOG_DIR / "logs"
LOG_FILE = LOGS_DIR / "watchdog.jsonl"


def ensure_dirs():
    CDP_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def get_username() -> str:
    try:
        return os.getlogin()
    except Exception:
        return os.environ.get("USER", os.environ.get("USERNAME", "unknown"))


class PlaywrightRun:
    def __init__(self, pid: int, cmdline: str, cwd: str, user: str, ppid: Optional[int] = None):
        self.pid = pid
        self.ppid = ppid
        self.cmdline = cmdline
        self.cwd = cwd
        self.user = user
        self.ts_start = time.time()
        self.run_id = self._generate_run_id(pid)
        self.cdp: Optional[Dict[str, Any]] = None

    def _generate_run_id(self, pid: int) -> str:
        data = f"{pid}:{self.ts_start}".encode("utf-8")
        return hashlib.sha256(data).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runId": self.run_id,
            "pid": self.pid,
            "ppid": self.ppid,
            "cmdline": self.cmdline,
            "cwd": self.cwd,
            "user": self.user,
        }


class Logger:
    def __init__(self, path: Path, verbose: bool):
        self.path = path
        self.verbose = verbose
        self.lock = threading.Lock()
        ensure_dirs()

    def log(self, event: str, data: Dict[str, Any]):
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "event": event,
            "os": platform.system().lower(),
            **data,
        }
        line = json.dumps(entry, ensure_ascii=False)
        with self.lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        if self.verbose or event in {"playwright_failed", "watchdog_error"}:
            print(line, flush=True)


def is_playwright_process(cmdline: str, comm: str = "") -> bool:
    hay = f"{comm} {cmdline}".lower()
    return any(re.search(p, hay) for p in PLAYWRIGHT_PATTERNS)


class CDPDiscovery:
    @staticmethod
    def from_pid_file(pid: int) -> Optional[Dict[str, Any]]:
        path = CDP_DIR / f"{pid}.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    @staticmethod
    def from_cmdline(cmdline: str) -> Optional[Dict[str, Any]]:
        m = re.search(r"--remote-debugging-port[=\s]+(\d+)", cmdline)
        if not m:
            return None
        port = int(m.group(1))
        info: Dict[str, Any] = {"port": port}
        # Try to resolve ws URL
        try:
            import urllib.request
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as resp:
                meta = json.loads(resp.read().decode("utf-8", "replace"))
            info["wsUrl"] = meta.get("webSocketDebuggerUrl")
        except Exception:
            info["wsUrl"] = None
        return info


class Artifacts:
    @staticmethod
    def read_playwright_test_json(key: str) -> Optional[Dict[str, Any]]:
        # key can be runId or pid; we try both
        for name in (f"{key}.json", f"{key}.report.json"):
            path = REPORTS_DIR / name
            if not path.exists():
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                errors = []
                artifacts: Dict[str, Any] = {"reportFile": str(path)}
                for suite in data.get("suites", []):
                    for spec in suite.get("specs", []):
                        for test in spec.get("tests", []):
                            for res in test.get("results", []):
                                if res.get("status") in ("failed", "timedOut"):
                                    err = res.get("error", {}) or {}
                                    errors.append({
                                        "title": test.get("title"),
                                        "message": err.get("message", ""),
                                        "stack": err.get("stack", ""),
                                    })
                                    for att in res.get("attachments", []):
                                        n = att.get("name")
                                        p = att.get("path")
                                        if not p:
                                            continue
                                        if n == "trace":
                                            artifacts.setdefault("traceZip", []).append(p)
                                        elif n == "screenshot":
                                            artifacts.setdefault("screenshots", []).append(p)
                                        elif n == "video":
                                            artifacts["video"] = p
                return {"errors": errors, "artifacts": artifacts}
            except Exception:
                continue
        return None

    @staticmethod
    def read_pytest_junit(key: str) -> Optional[Dict[str, Any]]:
        for name in (f"{key}.xml", f"{key}.junit.xml"):
            path = REPORTS_DIR / name
            if not path.exists():
                continue
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(path)
                root = tree.getroot()
                errors = []
                for tc in root.iter("testcase"):
                    for tag in ("failure", "error"):
                        elem = tc.find(tag)
                        if elem is not None:
                            errors.append({
                                "title": f"{tc.get('classname')}.{tc.get('name')}",
                                "message": elem.get("message", ""),
                                "stack": elem.text or "",
                            })
                return {"errors": errors, "artifacts": {"reportFile": str(path)}}
            except Exception:
                continue
        return None


# ---------------- Windows ---------------- #
def run_windows(logger: Logger, log_success: bool):
    try:
        import wmi  # type: ignore
    except Exception:
        logger.log("watchdog_error", {"message": "Windows mode requires 'wmi' and 'pywin32' (pip install wmi pywin32)"})
        sys.exit(1)

    c = wmi.WMI()
    start_w = c.watch_for(notification_type="Creation", wmi_class="Win32_ProcessStartTrace")
    stop_w = c.watch_for(notification_type="Deletion", wmi_class="Win32_ProcessStopTrace")

    tracked: Dict[int, PlaywrightRun] = {}
    logger.log("watchdog_started", {"mode": "windows_wmi", "user": get_username()})

    while True:
        try:
            try:
                ev = start_w(timeout_ms=200)
            except wmi.x_wmi_timed_out:  # type: ignore
                ev = None
            if ev is not None:
                pid = int(ev.ProcessID)
                name = (ev.ProcessName or "").strip()
                cmdline = name
                ppid = None
                cwd = os.getcwd()
                try:
                    proc = c.Win32_Process(ProcessId=pid)[0]
                    cmdline = proc.CommandLine or name
                    ppid = int(proc.ParentProcessId)
                    # Approximate cwd from ExecutablePath
                    if proc.ExecutablePath:
                        cwd = str(Path(proc.ExecutablePath).parent)
                except Exception:
                    pass
                if is_playwright_process(cmdline, name):
                    run = PlaywrightRun(pid, cmdline, cwd, get_username(), ppid)
                    run.cdp = CDPDiscovery.from_cmdline(cmdline) or CDPDiscovery.from_pid_file(pid)
                    tracked[pid] = run
                    payload = run.to_dict()
                    if run.cdp:
                        payload["cdp"] = run.cdp
                    logger.log("playwright_started", payload)

            try:
                ev = stop_w(timeout_ms=200)
            except wmi.x_wmi_timed_out:  # type: ignore
                ev = None
            if ev is not None:
                pid = int(getattr(ev, "ProcessID", 0))
                exit_code = int(getattr(ev, "ExitStatus", -1))
                run = tracked.pop(pid, None)
                if run is not None:
                    duration_ms = int((time.time() - run.ts_start) * 1000)
                    data = {**run.to_dict(), "exitCode": exit_code, "durationMs": duration_ms}
                    if exit_code != 0:
                        # Attach artifacts if user configured reporters to write here
                        artifacts = Artifacts.read_playwright_test_json(run.run_id) or Artifacts.read_playwright_test_json(str(pid))
                        if not artifacts:
                            artifacts = Artifacts.read_pytest_junit(run.run_id) or Artifacts.read_pytest_junit(str(pid))
                        if artifacts:
                            data.update(artifacts)
                        if run.cdp:
                            data["cdp"] = run.cdp
                        logger.log("playwright_failed", data)
                    elif log_success:
                        logger.log("playwright_succeeded", data)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.log("watchdog_error", {"message": f"windows loop error: {e}"})


# ---------------- Linux ---------------- #
def run_linux(logger: Logger, log_success: bool, poll_interval: float):
    if os.geteuid() == 0:
        try:
            run_linux_proc_connector(logger, log_success)
            return
        except Exception as e:
            logger.log("watchdog_error", {"message": f"proc connector failed, falling back to polling: {e}"})
    run_linux_poll(logger, log_success, poll_interval)


def run_linux_proc_connector(logger: Logger, log_success: bool):
    import socket as pysocket
    import struct

    NETLINK_CONNECTOR = 11
    CN_IDX_PROC = 0x1
    CN_VAL_PROC = 0x1
    NLMSG_DONE = 0x3
    PROC_CN_MCAST_LISTEN = 1
    PROC_CN_MCAST_IGNORE = 2
    PROC_EVENT_EXEC = 2
    PROC_EVENT_EXIT = 9

    NLHDR = "=IHHII"
    CNHDR = "=IIIIHH"
    EVTHDR = "=IIQ"
    EXECF = "=II"
    EXITF = "=IIII"

    def subscribe(sock, pid, op):
        nl_len = struct.calcsize(NLHDR) + struct.calcsize(CNHDR) + 4
        nlh = struct.pack(NLHDR, nl_len, NLMSG_DONE, 0, 0, pid)
        cn = struct.pack("=II", CN_IDX_PROC, CN_VAL_PROC) + struct.pack("=II", 0, 0) + struct.pack("=H", 4) + struct.pack("=H", 0)
        sock.send(nlh + cn + struct.pack("=I", op))

    def read_cmd(pid: int) -> str:
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                parts = [p.decode("utf-8", "replace") for p in f.read().split(b"\x00") if p]
                return " ".join(parts)
        except Exception:
            return ""

    def read_comm(pid: int) -> str:
        try:
            return open(f"/proc/{pid}/comm", "r", encoding="utf-8").read().strip()
        except Exception:
            return ""

    def read_cwd(pid: int) -> str:
        try:
            return os.readlink(f"/proc/{pid}/cwd")
        except Exception:
            return os.getcwd()

    sock = pysocket.socket(pysocket.AF_NETLINK, pysocket.SOCK_DGRAM, NETLINK_CONNECTOR)
    sock.bind((os.getpid(), 0))
    subscribe(sock, os.getpid(), PROC_CN_MCAST_LISTEN)

    tracked: Dict[int, PlaywrightRun] = {}
    logger.log("watchdog_started", {"mode": "linux_proc_connector", "user": get_username()})

    try:
        while True:
            data = sock.recv(65536)
            off = 0
            while off + struct.calcsize(NLHDR) <= len(data):
                nl_len, nl_type, nl_flags, nl_seq, nl_pid = struct.unpack_from(NLHDR, data, off)
                if nl_len < struct.calcsize(NLHDR):
                    break
                blob = data[off + struct.calcsize(NLHDR): off + nl_len]
                off += nl_len if nl_len > 0 else len(data)
                if len(blob) < struct.calcsize(CNHDR):
                    continue
                idx, val, seq, ack, clen, cflags = struct.unpack_from(CNHDR, blob, 0)
                cdata = blob[struct.calcsize(CNHDR): struct.calcsize(CNHDR) + clen]
                if len(cdata) < struct.calcsize(EVTHDR):
                    continue
                what, cpu, ts_ns = struct.unpack_from(EVTHDR, cdata, 0)
                payload = cdata[struct.calcsize(EVTHDR):]
                if what == PROC_EVENT_EXEC and len(payload) >= struct.calcsize(EXECF):
                    pid, tgid = struct.unpack_from(EXECF, payload, 0)
                    cmd = read_cmd(tgid)
                    comm = read_comm(tgid)
                    if is_playwright_process(cmd, comm):
                        run = PlaywrightRun(tgid, cmd, read_cwd(tgid), get_username())
                        run.cdp = CDPDiscovery.from_cmdline(cmd) or CDPDiscovery.from_pid_file(tgid)
                        tracked[tgid] = run
                        data_out = run.to_dict()
                        if run.cdp:
                            data_out["cdp"] = run.cdp
                        logger.log("playwright_started", data_out)
                elif what == PROC_EVENT_EXIT and len(payload) >= struct.calcsize(EXITF):
                    pid, tgid, exit_code, exit_signal = struct.unpack_from(EXITF, payload, 0)
                    status = (exit_code >> 8) & 0xFF
                    run = tracked.pop(tgid, None)
                    if run:
                        duration_ms = int((time.time() - run.ts_start) * 1000)
                        data_out = {**run.to_dict(), "exitCode": status, "exitSignal": exit_signal, "durationMs": duration_ms}
                        if status != 0:
                            artifacts = Artifacts.read_playwright_test_json(run.run_id) or Artifacts.read_playwright_test_json(str(tgid))
                            if not artifacts:
                                artifacts = Artifacts.read_pytest_junit(run.run_id) or Artifacts.read_pytest_junit(str(tgid))
                            if artifacts:
                                data_out.update(artifacts)
                            if run.cdp:
                                data_out["cdp"] = run.cdp
                            logger.log("playwright_failed", data_out)
                        elif log_success:
                            logger.log("playwright_succeeded", data_out)
    finally:
        try:
            subscribe(sock, os.getpid(), PROC_CN_MCAST_IGNORE)
        except Exception:
            pass


def run_linux_poll(logger: Logger, log_success: bool, poll_interval: float):
    logger.log("watchdog_started", {"mode": "linux_polling", "user": get_username(), "note": "Limited fidelity; run as root for exit codes"})
    tracked: Dict[int, PlaywrightRun] = {}
    seen: set[int] = set()
    while True:
        try:
            current: set[int] = set()
            for pid_str in os.listdir("/proc"):
                if not pid_str.isdigit():
                    continue
                pid = int(pid_str)
                current.add(pid)
                if pid in tracked:
                    continue
                # Read cmdline
                cmd = ""
                try:
                    with open(f"/proc/{pid}/cmdline", "rb") as f:
                        parts = [p.decode("utf-8", "replace") for p in f.read().split(b"\x00") if p]
                        cmd = " ".join(parts)
                except Exception:
                    continue
                comm = ""
                try:
                    comm = open(f"/proc/{pid}/comm", "r", encoding="utf-8").read().strip()
                except Exception:
                    pass
                if not is_playwright_process(cmd, comm):
                    continue
                try:
                    cwd = os.readlink(f"/proc/{pid}/cwd")
                except Exception:
                    cwd = os.getcwd()
                run = PlaywrightRun(pid, cmd, cwd, get_username())
                run.cdp = CDPDiscovery.from_cmdline(cmd) or CDPDiscovery.from_pid_file(pid)
                tracked[pid] = run
                out = run.to_dict()
                if run.cdp:
                    out["cdp"] = run.cdp
                logger.log("playwright_started", out)

            # Detect exits (no exit code available)
            for pid, run in list(tracked.items()):
                if pid not in current:
                    duration_ms = int((time.time() - run.ts_start) * 1000)
                    data_out = {**run.to_dict(), "exitCode": None, "durationMs": duration_ms}
                    # Try artifacts
                    artifacts = Artifacts.read_playwright_test_json(run.run_id) or Artifacts.read_playwright_test_json(str(pid))
                    if not artifacts:
                        artifacts = Artifacts.read_pytest_junit(run.run_id) or Artifacts.read_pytest_junit(str(pid))
                    if artifacts:
                        data_out.update(artifacts)
                    if run.cdp:
                        data_out["cdp"] = run.cdp
                    # We can't distinguish success/failure; emit generic exit event
                    logger.log("playwright_exited", data_out)
                    tracked.pop(pid, None)

            time.sleep(poll_interval)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.log("watchdog_error", {"message": f"linux polling error: {e}"})


def main():
    parser = argparse.ArgumentParser(description="Detect Playwright runs system-wide and log start/exit with CDP.")
    parser.add_argument("--verbose", action="store_true", help="Print logs to stdout in addition to file")
    parser.add_argument("--log-success", action="store_true", help="Also log successful exits (when status=0)")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Linux polling interval (seconds) when not root")
    args = parser.parse_args()

    ensure_dirs()
    logger = Logger(LOG_FILE, verbose=args.verbose)

    if sys.platform.startswith("win"):
        run_windows(logger, args.log_success)
    elif sys.platform.startswith("linux"):
        run_linux(logger, args.log_success, args.poll_interval)
    else:
        logger.log("watchdog_error", {"message": f"unsupported OS: {sys.platform}"})
        sys.exit(2)


if __name__ == "__main__":
    main()


