import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest

from hermes_temi_bridge.hermes_client import (
    HermesInvocationError,
    HermesRequest,
    HttpHermesClient,
    parse_hermes_output,
)


class FakeHermesHandler(BaseHTTPRequestHandler):
    captured_payload = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        FakeHermesHandler.captured_payload = json.loads(self.rfile.read(length).decode("utf-8"))
        body = json.dumps(
            {
                "status": "ok",
                "raw_output": json.dumps(
                    {
                        "schema_version": "1.0",
                        "event_id": "evt_http",
                        "robot_id": "temi-01",
                        "confidence": 1.0,
                        "reasoning_summary": "HTTP test.",
                        "actions": [
                            {
                                "action_id": "act_001",
                                "type": "speak",
                                "text": "http ok",
                                "language": "zh-TW",
                            }
                        ],
                    }
                ),
                "latency_ms": 7,
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


class HttpHermesClientTests(unittest.TestCase):
    def test_posts_prompt_to_resident_server(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeHermesHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = HttpHermesClient(
                f"http://127.0.0.1:{server.server_port}/invoke",
                timeout_seconds=5,
            )
            response = client.invoke(
                HermesRequest(
                    event_id="evt_http",
                    robot_id="temi-01",
                    conversation_id="conv_http",
                    language="zh-TW",
                    asr_text="你聽得到嗎",
                    frames=[],
                )
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

        self.assertEqual(response.latency_ms, 7)
        self.assertIn("你聽得到嗎", FakeHermesHandler.captured_payload["prompt"])
        self.assertEqual(FakeHermesHandler.captured_payload["asr_text"], "你聽得到嗎")
        parsed = parse_hermes_output(response.raw_output)
        self.assertEqual(parsed["actions"][0]["text"], "http ok")

    def test_http_error_includes_server_body(self):
        class ErrorHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = b'{"status":"error","error":"resident failed"}'
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), ErrorHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = HttpHermesClient(
                f"http://127.0.0.1:{server.server_port}/invoke",
                timeout_seconds=5,
            )
            with self.assertRaisesRegex(HermesInvocationError, "resident failed"):
                client.invoke(
                    HermesRequest(
                        event_id="evt_http_error",
                        robot_id="temi-01",
                        conversation_id=None,
                        language="zh-TW",
                        asr_text="測試",
                        frames=[],
                    )
                )
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
