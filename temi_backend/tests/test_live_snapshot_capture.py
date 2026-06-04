import argparse
import importlib.util
from pathlib import Path
import socket
import struct
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "capture_temi_live_snapshot.py"
SPEC = importlib.util.spec_from_file_location("capture_temi_live_snapshot", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module)


def tiny_jpeg() -> bytes:
    return b"\xff\xd8" + b"temi-test-jpeg" + b"\xff\xd9"


def ws_frame(opcode: int, payload: bytes) -> bytes:
    first = 0x80 | opcode
    length = len(payload)
    if length < 126:
        return bytes([first, length]) + payload
    if length <= 0xFFFF:
        return bytes([first, 126]) + struct.pack(">H", length) + payload
    return bytes([first, 127]) + struct.pack(">Q", length) + payload


class FakeBroadcastServer:
    def __init__(self, binary_payload: bytes) -> None:
        self.binary_payload = binary_payload
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.port = 0

    def __enter__(self):
        self.thread.start()
        self.ready.wait(timeout=2)
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.thread.join(timeout=2)

    def _run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            self.port = server.getsockname()[1]
            self.ready.set()
            conn, _ = server.accept()
            with conn:
                request = b""
                while b"\r\n\r\n" not in request:
                    request += conn.recv(1024)
                key = ""
                for line in request.decode("iso-8859-1").split("\r\n"):
                    if line.lower().startswith("sec-websocket-key:"):
                        key = line.split(":", 1)[1].strip()
                        break
                accept = module.websocket_accept_key(key)
                conn.sendall(
                    (
                        "HTTP/1.1 101 Switching Protocols\r\n"
                        "Upgrade: websocket\r\n"
                        "Connection: Upgrade\r\n"
                        f"Sec-WebSocket-Accept: {accept}\r\n"
                        "\r\n"
                    ).encode("ascii")
                )
                conn.sendall(ws_frame(0x1, b'{"status":"connected"}'))
                conn.sendall(ws_frame(0x2, self.binary_payload))


class LiveSnapshotCaptureTests(unittest.TestCase):
    def test_parse_broadcast_payload(self) -> None:
        payload = struct.pack(">qQ", 1234, 7) + tiny_jpeg()
        parsed = module.parse_broadcast_payload(payload)

        self.assertEqual(parsed["timestamp_ms"], 1234)
        self.assertEqual(parsed["sequence"], 7)
        self.assertEqual(parsed["jpeg"], tiny_jpeg())

    def test_capture_live_snapshot_saves_frame_metadata(self) -> None:
        payload = struct.pack(">qQ", 5678, 42) + tiny_jpeg()
        with tempfile.TemporaryDirectory() as tmp, FakeBroadcastServer(payload) as server:
            args = argparse.Namespace(
                source_url=f"ws://127.0.0.1:{server.port}",
                robot_id="temi-01",
                request_id="snap_test",
                request_prefix="snap_live",
                count=1,
                timeout_seconds=2.0,
                shared_root=tmp,
                bridge_root="/shared/temi",
                pretty=False,
            )

            result = module.capture_live_snapshots(args)

            self.assertEqual(result["status"], "captured")
            self.assertEqual(result["source_type"], "live.snapshot")
            self.assertEqual(result["frames"][0]["name"], "current")
            self.assertEqual(result["frames"][0]["ts_ms"], 5678)
            self.assertEqual(result["frames"][0]["sequence"], 42)
            self.assertEqual(result["frames"][0]["path"], "/shared/temi/live_snapshots/temi-01/snap_test/frame_current.jpg")
            self.assertEqual(Path(result["frames"][0]["local_path"]).read_bytes(), tiny_jpeg())


if __name__ == "__main__":
    unittest.main()
