[33mcommit e97550a8072ecc49b99babac9771bd0dbbdf4d50[m[33m ([m[1;36mHEAD[m[33m -> [m[1;32mmain[m[33m, [m[1;31morigin/main[m[33m, [m[1;31morigin/HEAD[m[33m)[m
Author: mohamedbenhadjer <benhadjer.mohamed2005@gmail.com>
Date:   Fri Oct 31 19:28:19 2025 +0100

    adding flags to start the browser

[1mdiff --git a/sitecustomize.py b/sitecustomize.py[m
[1mindex 98cbe4c..c494bda 100644[m
[1m--- a/sitecustomize.py[m
[1m+++ b/sitecustomize.py[m
[36m@@ -1,524 +1,37 @@[m
[31m-"""[m
[31m-Sitecustomize hook for Playwright error detection.[m
[31m-Auto-loaded by Python when this directory is in PYTHONPATH.[m
[31m-Intercepts Playwright exceptions and sends support requests without modifying user code.[m
[31m-"""[m
[31m-import os[m
[31m-import sys[m
[31m-import logging[m
[31m-import time[m
[31m-import asyncio[m
[31m-import threading[m
[31m-import json[m
[31m-from pathlib import Path[m
[31m-from typing import Optional, Any, Dict[m
[31m-from http.server import HTTPServer, BaseHTTPRequestHandler[m
[32m+[m[32m# sitecustomize.py[m
[32m+[m[32m# Forces Chromium to keep rendering/animating when backgrounded/occluded.[m
 [m
[31m-# Only activate if explicitly enabled[m
[31m-if os.environ.get("MINIAGENT_ENABLED", "1") != "1":[m
[31m-    sys.exit(0)[m
[32m+[m[32mDEFAULT_CHROMIUM_ARGS = [[m
[32m+[m[32m    "--disable-backgrounding-occluded-windows",[m
[32m+[m[32m    "--disable-renderer-backgrounding",[m
[32m+[m[32m    "--disable-background-timer-throttling",[m
[32m+[m[32m][m
 [m
[31m-logger = logging.getLogger("miniagent.hook")[m
[31m-logger.setLevel(logging.INFO)[m
[31m-if not logger.handlers:[m
[31m-    handler = logging.StreamHandler()[m
[31m-    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))[m
[31m-    logger.addHandler(handler)[m
[31m-[m
[31m-# Track if we've already patched[m
[31m-_patched = False[m
[31m-[m
[31m-# Error handling mode configuration[m
[31m-_MODE = os.environ.get("MINIAGENT_ON_ERROR", "report").lower()  # report|hold|swallow[m
[31m-_HOLD_RAW = os.environ.get("MINIAGENT_HOLD_SECS", "").strip().lower()[m
[31m-_RESUME_FILE = os.environ.get("MINIAGENT_RESUME_FILE", "/tmp/miniagent_resume")[m
[31m-[m
[31m-# Optional HTTP resume endpoint configuration[m
[31m-_RESUME_HTTP_ENABLED = os.environ.get("MINIAGENT_RESUME_HTTP", "0") == "1"[m
[31m-_RESUME_HTTP_HOST = os.environ.get("MINIAGENT_RESUME_HTTP_HOST", "127.0.0.1")[m
[31m-_RESUME_HTTP_PORT = int(os.environ.get("MINIAGENT_RESUME_HTTP_PORT", "8787"))[m
[31m-_RESUME_HTTP_TOKEN = os.environ.get("MINIAGENT_RESUME_HTTP_TOKEN", "").strip()[m
[31m-[m
[31m-# Remote debugging port configuration[m
[31m-_DEBUG_PORT = int(os.environ.get("MINIAGENT_DEBUG_PORT", "9222"))[m
[31m-_FORCE_DEBUG_PORT = os.environ.get("MINIAGENT_FORCE_DEBUG_PORT", "1") == "1"[m
[31m-[m
[31m-[m
[31m-def _hold_deadline():[m
[31m-    """Compute hold deadline from MINIAGENT_HOLD_SECS env var."""[m
[31m-    if _HOLD_RAW in ("", "forever", "inf"):[m
[31m-        return None[m
[32m+[m[32mdef _patch_playwright():[m
     try:[m
[31m-        return time.time() + float(_HOLD_RAW)[m
[32m+[m[32m        from playwright.sync_api import BrowserType  # type: ignore[m
     except Exception:[m
[31m-        return None[m
[31m-[m
[31m-[m
[31m-def _park_until_resume(reason: str, details: str):[m
[31m-    """[m
[31m-    Block the process until resume signal or timeout.[m
[31m-    Resume happens when MINIAGENT_RESUME_FILE is created or deadline is reached.[m
[31m-    """[m
[31m-    logger.warning(f"Holding on error ({reason}) - waiting for agent. Resume file: {_RESUME_FILE}")[m
[31m-    deadline = _hold_deadline()[m
[31m-    [m
[31m-    while True:[m
[31m-        try:[m
[31m-            if _RESUME_FILE and Path(_RESUME_FILE).exists():[m
[31m-                logger.info("Resume signal detected; continuing.")[m
[31m-                try:[m
[31m-                    Path(_RESUME_FILE).unlink(missing_ok=True)[m
[31m-                except Exception:[m
[31m-                    pass[m
[31m-                return[m
[31m-        except Exception:[m
[31m-            pass[m
[31m-        [m
[31m-        if deadline and time.time() >= deadline:[m
[31m-            logger.info("Hold timeout reached; continuing.")[m
[31m-            return[m
[31m-        [m
[31m-        time.sleep(1.0)[m
[31m-[m
[31m-[m
[31m-class _ResumeRequestHandler(BaseHTTPRequestHandler):[m
[31m-    """Minimal HTTP handler for POST /resume with bearer auth.[m
[31m-    Creates the resume file watched by the hold loop.[m
[31m-    """[m
[31m-[m
[31m-    server_version = "MiniAgentResumeHTTP/1.0"[m
[31m-    sys_version = ""[m
[31m-[m
[31m-    def log_message(self, format, *args):[m
[31m-        try:[m
[31m-            logger.info("resume-http: " + (format % args))[m
[31m-        except Exception:[m
[31m-            pass[m
[31m-[m
[31m-    def _send_json(self, status: int, payload: Dict[str, Any]):[m
[31m-        try:[m
[31m-            body = json.dumps(payload).encode("utf-8")[m
[31m-        except Exception:[m
[31m-            body = b"{}"[m
[31m-        self.send_response(status)[m
[31m-        self.send_header("Content-Type", "application/json")[m
[31m-        self.send_header("Content-Length", str(len(body)))[m
[31m-        self.end_headers()[m
[31m-        try:[m
[31m-            self.wfile.write(body)[m
[31m-        except Exception:[m
[31m-            pass[m
[31m-[m
[31m-    def do_POST(self):  # noqa: N802 (method name by BaseHTTPRequestHandler)[m
[31m-        if self.path != "/resume":[m
[31m-            self._send_json(404, {"ok": False, "error": "not_found"})[m
[31m-            return[m
[31m-[m
[31m-        token = _RESUME_HTTP_TOKEN[m
[31m-        auth_header = self.headers.get("Authorization", "")[m
[31m-[m
[31m-        if not token or not auth_header.startswith("Bearer "):[m
[31m-            self._send_json(401, {"ok": False, "error": "unauthorized"})[m
[31m-            return[m
[31m-[m
[31m-        expected = f"Bearer {token}"[m
[31m-        if auth_header.strip() != expected:[m
[31m-            self._send_json(401, {"ok": False, "error": "unauthorized"})[m
[31m-            return[m
[31m-[m
[31m-        try:[m
[31m-            Path(_RESUME_FILE).touch(exist_ok=True)[m
[31m-            logger.info("Resume HTTP: resume signal emitted via file")[m
[31m-            self._send_json(200, {"ok": True})[m
[31m-        except Exception as e:[m
[31m-            logger.error(f"Resume HTTP: failed to emit resume signal: {e}")[m
[31m-            self._send_json(500, {"ok": False, "error": "server_error"})[m
[31m-[m
[31m-[m
[31m-def _start_resume_http_server():[m
[31m-    """Start a daemonized HTTP server that exposes POST /resume.[m
[31m-    Only starts when MINIAGENT_RESUME_HTTP=1 and a token is configured.[m
[31m-    """[m
[31m-    if not _RESUME_HTTP_ENABLED:[m
[31m-        return[m
[31m-[m
[31m-    if not _RESUME_HTTP_TOKEN:[m
[31m-        logger.error("Resume HTTP enabled but MINIAGENT_RESUME_HTTP_TOKEN is not set; not starting HTTP server")[m
         return[m
 [m
[31m-    try:[m
[31m-        httpd = HTTPServer((_RESUME_HTTP_HOST, _RESUME_HTTP_PORT), _ResumeRequestHandler)[m
[31m-    except Exception as e:[m
[31m-        logger.warning(f"Resume HTTP: failed to bind {_RESUME_HTTP_HOST}:{_RESUME_HTTP_PORT}: {e}")[m
[31m-        return[m
[31m-[m
[31m-    th = threading.Thread(target=httpd.serve_forever, name="miniagent-resume-http", daemon=True)[m
[31m-    th.start()[m
[31m-    logger.info(f"Resume HTTP server listening on http://{_RESUME_HTTP_HOST}:{_RESUME_HTTP_PORT}")[m
[31m-[m
[31m-[m
[31m-def _get_page_info(page_obj) -> Dict[str, Any]:[m
[31m-    """Extract URL, title, and page ID from a Playwright Page object."""[m
[31m-    info = {"url": None, "title": None, "page_id": None}[m
[31m-    [m
[31m-    try:[m
[31m-        if hasattr(page_obj, "url"):[m
[31m-            info["url"] = pag