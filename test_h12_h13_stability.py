"""Unit tests for H12 cancel-priority queue and H13 SERVER_BUSY backoff."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock


def _load_miniagent_ws():
    # Avoid importing sitecustomize / starting a real WS connection.
    path = Path(__file__).resolve().parent / "miniagent_ws.py"
    # Stub websocket dependency if missing.
    if "websocket" not in sys.modules:
        ws_mod = types.ModuleType("websocket")
        class WebSocketApp:  # noqa: N801
            def __init__(self, *args, **kwargs):
                pass
            def run_forever(self, *args, **kwargs):
                pass
            def send(self, *args, **kwargs):
                pass
            def close(self):
                pass
        ws_mod.WebSocketApp = WebSocketApp
        sys.modules["websocket"] = ws_mod

    spec = importlib.util.spec_from_file_location("miniagent_ws_under_test", path)
    module = importlib.util.module_from_spec(spec)
    # Prevent background reconnect thread from starting during class init.
    original_init = None

    def _patched_client_init(self, ws_url, token, client_name="python-cdp-monitor"):
        self.ws_url = ws_url
        self.token = token
        self.client_name = client_name
        self.version = "1.0"
        self.ws = None
        self.connected = False
        self.authenticated = False
        self.pending_messages = []
        self.lock = __import__("threading").Lock()
        self.ws_thread = None
        self.reconnect_delay = 0.5
        self.max_reconnect_delay = 8.0
        self.last_connect_attempt = 0
        # Do not call _start_connection()

    # Load source and exec after patching via run
    source = path.read_text()
    # Replace _start_connection call in __init__
    source = source.replace("self._start_connection()", "pass  # tests: skip auto-connect")
    code = compile(source, str(path), "exec")
    module.__dict__["__name__"] = "miniagent_ws_under_test"
    exec(code, module.__dict__)
    return module


class CancelQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_miniagent_ws()

    def setUp(self):
        self.client = self.mod.MiniAgentWSClient("ws://127.0.0.1:9/ws", "tok")

    def test_cancel_never_dropped_when_queue_full(self):
        for i in range(10):
            self.client._queue_pending_message({"type": "support_request", "i": i})
        self.client._queue_pending_message({"type": "support_cancelled", "payload": {"runId": "r1"}})

        cancel_msgs = [m for m in self.client.pending_messages if m.get("type") == "support_cancelled"]
        self.assertEqual(len(cancel_msgs), 1)
        self.assertEqual(self.client.pending_messages[0]["type"], "support_cancelled")
        # Cap may keep cancels; non-cancels should be <= 10 total messages with cancel preserved
        self.assertLessEqual(len(self.client.pending_messages), 11)
        self.assertTrue(any(m.get("type") == "support_cancelled" for m in self.client.pending_messages))

    def test_non_cancel_dropped_before_cancel(self):
        self.client._queue_pending_message({"type": "support_cancelled", "payload": {}})
        for i in range(12):
            self.client._queue_pending_message({"type": "status_check", "i": i})
        cancel_msgs = [m for m in self.client.pending_messages if m.get("type") == "support_cancelled"]
        self.assertEqual(len(cancel_msgs), 1)


class ServerBusyBackoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_miniagent_ws()

    def setUp(self):
        self.client = self.mod.MiniAgentWSClient("ws://127.0.0.1:9/ws", "tok")
        self.client.reconnect_delay = 0.5

    def test_server_busy_sets_reconnect_floor_4s(self):
        ws = MagicMock()
        self.client._on_message(
            ws,
            '{"type":"error","code":"SERVER_BUSY","message":"at capacity"}',
        )
        self.assertGreaterEqual(self.client.reconnect_delay, 4.0)
        ws.close.assert_called()


class DebugPortPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_miniagent_ws()

    def test_debug_port_zero_omitted(self):
        client = MagicMock()
        client.send_support_request = MagicMock()
        mgr = self.mod.SupportRequestManager(client, cooldown_sec=0)
        mgr.trigger_support_request(
            reason="test",
            details="details",
            debug_port=0,
        )
        args, kwargs = client.send_support_request.call_args
        payload = args[0]
        self.assertNotIn("debugPort", payload.get("controlTarget", {}))


if __name__ == "__main__":
    unittest.main()
