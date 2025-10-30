#!/usr/bin/env python3
"""Check if sitecustomize imports fully."""
import os
import sys

# Set env vars
os.environ["MINIAGENT_ON_ERROR"] = "hold"
os.environ["MINIAGENT_RESUME_HTTP"] = "1"
os.environ["MINIAGENT_RESUME_HTTP_TOKEN"] = "strong-secret"
os.environ["MINIAGENT_TOKEN"] = "test-token"
os.environ["MINIAGENT_WS_URL"] = "ws://127.0.0.1:8777/ws"
os.environ["MINIAGENT_ENABLED"] = "1"

print("Starting import...")
try:
    import sitecustomize
    print("Import successful")
    print(f"Module file: {sitecustomize.__file__}")
    print(f"Module dir: {dir(sitecustomize)}")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()

