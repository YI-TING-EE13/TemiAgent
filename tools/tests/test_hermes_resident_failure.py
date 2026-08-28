"""Contract tests for resident Hermes failure responses."""

from __future__ import annotations

import http.client
import importlib.util
import json
from pathlib import Path
import threading
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "hermes_resident_server.py"
SPEC = importlib.util.spec_from_file_location("hermes_resident_server_failure_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
resident_server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resident_server)


class _TypedFailure(RuntimeError):
    def to_dict(self) -> dict[str, object]:
        return {
            "error_class": "hermes_compression_exhausted",
            "safe_message": "provider raw secret must never cross this boundary",
            "retryable": True,
            "original_failure_category": "context_overflow",
        }


class _FakeResident:
    def __init__(self, *, failure: BaseException | None = None) -> None:
        self.failure = failure

    def invoke(self, prompt: str, context: dict[str, str], *, asr_text: str = "") -> dict[str, object]:
        del prompt, context, asr_text
        if self.failure is not None:
            raise self.failure
        return {"status": "ok", "raw_output": "safe response"}

    def health(self) -> dict[str, object]:
        return {"status": "ok", "request_count": 0}


def _request(
    server: resident_server.ResidentServer,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    try:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read().decode("utf-8"))
    finally:
        connection.close()


class ResidentFailureContractTests(unittest.TestCase):
    def _serve(self, resident: _FakeResident) -> tuple[resident_server.ResidentServer, threading.Thread]:
        server = resident_server.ResidentServer(("127.0.0.1", 0), resident)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_success_response_is_unchanged(self) -> None:
        server, thread = self._serve(_FakeResident())
        try:
            status, payload = _request(server, "POST", "/invoke", {"prompt": "hello"})
            self.assertEqual(status, 200)
            self.assertEqual(payload, {"status": "ok", "raw_output": "safe response"})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_typed_failure_is_bounded_and_health_remains_available(self) -> None:
        server, thread = self._serve(_FakeResident(failure=_TypedFailure("provider raw secret")))
        try:
            status, payload = _request(server, "POST", "/invoke", {"prompt": "hello"})
            self.assertEqual(status, 500)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(
                payload["error"],
                "Hermes could not produce a response after bounded context recovery.",
            )
            self.assertEqual(
                payload["failure"],
                {
                    "error_class": "hermes_compression_exhausted",
                    "original_failure_category": "context_overflow",
                    "retryable": True,
                },
            )
            encoded = json.dumps(payload)
            self.assertNotIn("provider raw secret", encoded)
            self.assertNotIn("safe_message", encoded)

            health_status, health_payload = _request(server, "GET", "/health")
            self.assertEqual(health_status, 200)
            self.assertEqual(health_payload["status"], "ok")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
