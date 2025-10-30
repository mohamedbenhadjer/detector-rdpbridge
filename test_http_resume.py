#!/usr/bin/env python3
"""Quick test to verify HTTP resume server starts."""
import os
import sys
import time

# Set env vars BEFORE importing sitecustomize
os.environ["MINIAGENT_ON_ERROR"] = "hold"
os.environ["MINIAGENT_RESUME_HTTP"] = "1"
os.environ["MINIAGENT_RESUME_HTTP_TOKEN"] = "strong-secret"
os.environ["MINIAGENT_TOKEN"] = "test-token"
os.environ["MINIAGENT_WS_URL"] = "ws://127.0.0.1:8777/ws"

print("Environment configured:")
print(f"  MINIAGENT_ON_ERROR={os.environ.get('MINIAGENT_ON_ERROR')}")
print(f"  MINIAGENT_RESUME_HTTP={os.environ.get('MINIAGENT_RESUME_HTTP')}")
print(f"  MINIAGENT_RESUME_HTTP_TOKEN={os.environ.get('MINIAGENT_RESUME_HTTP_TOKEN')}")
print()

print("Importing sitecustomize...")
import sitecustomize
print("Imported successfully")
print()

print("Waiting 30 seconds for HTTP server (check with curl in another terminal)...")
print("Test command:")
print('  curl -v -X POST http://127.0.0.1:8787/resume -H "Authorization: Bearer strong-secret"')
print()

time.sleep(30)
print("Done")

