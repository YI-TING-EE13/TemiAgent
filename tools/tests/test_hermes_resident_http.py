"""No-network tests for the resident Hermes HTTP boundary."""

from __future__ import annotations

from http.client import HTTPConnection
import importlib.util
import json
from pathlib import Path
import socket
import sys
import threading
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "hermes_resident_server.py"
SPEC = importlib.util.spec_from_file_location("resident_http_contract", MODULE_PATH)
assert SPEC and SPEC.loader
resident_server = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = resident_server
SPEC.loader.exec_module(resident_server)


MALFORMED_ACTIVE_RESIDENT_PAYLOAD = {
    "prompt": "gate5b5-malformed-active-resident-probe",
    "active_resident": "malformed",
}


class FakeResident:
    """Record the resident/model boundary without loading Hermes or an LM."""

    def __init__(self, *, wait_for_release: bool = False, response_size: int = 0) -> None:
        self.wait_for_release = wait_for_release
        self.response_size = response_size
        self.invoke_calls = 0
        self.inference_calls = 0
        self.model_http_calls = 0
        self.invoke_started = threading.Event()
        self.invoke_finished = threading.Event()
        self.release = threading.Event()

    def invoke(
        self,
        prompt: str,
        invocation_context: dict[str, str],
        *,
        asr_text: str = "",
    ) -> dict[str, object]:
        del prompt, invocation_context, asr_text
        self.invoke_calls += 1
        self.invoke_started.set()
        if self.wait_for_release and not self.release.wait(timeout=5):
            raise AssertionError("fake inference release timed out")
        self.inference_calls += 1
        self.model_http_calls += 1
        self.invoke_finished.set()
        return {
            "status": "ok",
            "raw_output": "x" * self.response_size,
            "latency_ms": 1,
            "request_count": self.invoke_calls,
        }

    def health(self) -> dict[str, object]:
        return {"status": "ok", "request_count": self.invoke_calls}


class ResidentHermesHttpTests(unittest.TestCase):
    def start_server(self, resident: FakeResident) -> tuple[resident_server.ResidentServer, threading.Thread]:
        server = resident_server.ResidentServer(("127.0.0.1", 0), resident)  # type: ignore[arg-type]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    @staticmethod
    def stop_server(server: resident_server.ResidentServer, thread: threading.Thread) -> None:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    @staticmethod
    def post_json(server: resident_server.ResidentServer, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        try:
            connection.request(
                "POST",
                "/invoke",
                body=json.dumps(payload, separators=(",", ":")),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            return response.status, json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()

    @staticmethod
    def get_health(server: resident_server.ResidentServer) -> tuple[int, dict[str, object]]:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        try:
            connection.request("GET", "/health")
            response = connection.getresponse()
            return response.status, json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()

    @staticmethod
    def make_failing_handler(error: BaseException) -> tuple[object, list[bytes]]:
        writes: list[bytes] = []

        class FailingWriter:
            def write(self, body: bytes) -> None:
                writes.append(body)
                raise error

        handler = object.__new__(resident_server.RequestHandler)
        handler.send_response = lambda status: None
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None
        handler.wfile = FailingWriter()
        return handler, writes

    def test_malformed_active_resident_probe_rejects_before_inference(self) -> None:
        resident = FakeResident()
        server, thread = self.start_server(resident)
        try:
            status, response = self.post_json(server, MALFORMED_ACTIVE_RESIDENT_PAYLOAD)
            self.assertEqual(status, 400)
            self.assertEqual(response["error"], "invalid active_resident")
            self.assertEqual(resident.invoke_calls, 0)
            self.assertEqual(resident.inference_calls, 0)
            self.assertEqual(resident.model_http_calls, 0)
        finally:
            self.stop_server(server, thread)

    def test_valid_prompt_without_active_resident_is_inference_capable(self) -> None:
        resident = FakeResident()
        server, thread = self.start_server(resident)
        try:
            status, response = self.post_json(server, {"prompt": "valid resident request"})
            self.assertEqual(status, 200)
            self.assertEqual(response["status"], "ok")
            self.assertEqual(resident.invoke_calls, 1)
            self.assertEqual(resident.inference_calls, 1)
            self.assertEqual(resident.model_http_calls, 1)
        finally:
            self.stop_server(server, thread)

    def test_expected_response_disconnects_are_swallowed_at_write_boundary(self) -> None:
        for disconnect_error in (BrokenPipeError("pipe closed"), ConnectionResetError("peer reset")):
            with self.subTest(error=type(disconnect_error).__name__):
                handler, writes = self.make_failing_handler(disconnect_error)
                with self.assertLogs(level="INFO") as logs:
                    result = resident_server.RequestHandler._write_json(
                        handler,
                        200,
                        {"status": "ok"},
                    )
                self.assertFalse(result)
                self.assertEqual(len(writes), 1)
                self.assertIn("resident client disconnected", "\n".join(logs.output))

    def test_legitimate_response_write_errors_are_not_suppressed(self) -> None:
        handler, _ = self.make_failing_handler(RuntimeError("unexpected response writer failure"))
        with self.assertRaisesRegex(RuntimeError, "unexpected response writer failure"):
            resident_server.RequestHandler._write_json(handler, 200, {"status": "ok"})

    def test_long_request_client_disconnect_does_not_mask_completed_inference(self) -> None:
        resident = FakeResident(wait_for_release=True, response_size=4 * 1024 * 1024)
        server, thread = self.start_server(resident)
        client_socket: socket.socket | None = None
        try:
            body = json.dumps({"prompt": "valid delayed resident request"}).encode("utf-8")
            client_socket = socket.create_connection(("127.0.0.1", server.server_port), timeout=2)
            client_socket.sendall(
                b"POST /invoke HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\n".encode("ascii")
                + b"Connection: close\r\n\r\n"
                + body
            )
            self.assertTrue(resident.invoke_started.wait(timeout=2))
            client_socket.close()
            client_socket = None
            with self.assertLogs(level="INFO") as logs:
                resident.release.set()
                self.assertTrue(resident.invoke_finished.wait(timeout=5))
                status, response = self.get_health(server)
            self.assertEqual(status, 200)
            self.assertEqual(response["status"], "ok")
            self.assertEqual(resident.invoke_calls, 1)
            self.assertEqual(resident.inference_calls, 1)
            self.assertEqual(resident.model_http_calls, 1)
            output = "\n".join(logs.output)
            self.assertNotIn("resident Hermes invocation failed", output)
            self.assertNotIn("Traceback", output)
            self.assertNotIn('"POST /invoke HTTP/1.1" 500 -', output)
        finally:
            if client_socket is not None:
                client_socket.close()
            resident.release.set()
            self.stop_server(server, thread)


if __name__ == "__main__":
    unittest.main()
