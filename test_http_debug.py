#!/usr/bin/env python3
"""Debug why HTTP server isn't starting."""
import os

# Set env vars BEFORE importing sitecustomize
os.environ["MINIAGENT_ON_ERROR"] = "hold"
os.environ["MINIAGENT_RESUME_HTTP"] = "1"
os.environ["MINIAGENT_RESUME_HTTP_TOKEN"] = "strong-secret"
os.environ["MINIAGENT_TOKEN"] = "test-token"
os.environ["MINIAGENT_WS_URL"] = "ws://127.0.0.1:8777/ws"

print("Before import - checking env vars:")
print(f"  MINIAGENT_RESUME_HTTP = {os.environ.get('MINIAGENT_RESUME_HTTP')}")
print(f"  MINIAGENT_RESUME_HTTP_TOKEN = {os.environ.get('MINIAGENT_RESUME_HTTP_TOKEN')}")
print()

import sitecustomize

print("\nAfter import - checking sitecustomize globals:")
print(f"  _RESUME_HTTP_ENABLED = {sitecustomize._RESUME_HTTP_ENABLED}")
print(f"  _RESUME_HTTP_HOST = {sitecustomize._RESUME_HTTP_HOST}")
print(f"  _RESUME_HTTP_PORT = {sitecustomize._RESUME_HTTP_PORT}")
print(f"  _RESUME_HTTP_TOKEN = {sitecustomize._RESUME_HTTP_TOKEN}")
print()

print("Manually calling _start_resume_http_server()...")
sitecustomize._start_resume_http_server()
print()

import time
print("Sleeping 10s...")
time.sleep(10)
print("Done")

