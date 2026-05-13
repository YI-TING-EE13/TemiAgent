"""Manual OpenCV video receiver for validating Temi WebSocket streaming."""

from __future__ import annotations

import argparse
import asyncio
import time
from typing import Any

import av
import cv2
import websockets

from temi_backend.vision_server import VisionServer


def parse_args() -> argparse.Namespace:
    """Parse command line options for the video receiver."""
    parser = argparse.ArgumentParser(description="Display Temi video frames received over WebSocket.")
    parser.add_argument("--host", default="0.0.0.0", help="WebSocket bind host.")
    parser.add_argument("--port", default=8080, type=int, help="WebSocket bind port.")
    return parser.parse_args()


async def main_async(host: str, port: int) -> None:
    """Start a WebSocket receiver that displays decoded frames in OpenCV."""
    server = VisionServer(host=host, port=port)

    async def handler(websocket: Any) -> None:
        codec = av.CodecContext.create("h264", "r")
        frame_count = 0
        start_time = time.time()
        print("Video stream connected.")

        try:
            async for message in websocket:
                if not isinstance(message, bytes) or len(message) < 8:
                    continue
                try:
                    server.decode_message(codec, message)
                except av.error.InvalidDataError:
                    continue

                keyframe = server.buffer.latest()
                if keyframe is None:
                    continue

                frame = keyframe["frame"]
                cv2.putText(
                    frame,
                    f"Temi time: {keyframe['actual_t']} ms",
                    (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 255, 0),
                    2,
                )
                cv2.imshow("Temi Video Stream", frame)
                frame_count += 1
                if frame_count % 30 == 0:
                    fps = frame_count / max(time.time() - start_time, 0.001)
                    print(f"FPS: {fps:.2f}")
                    frame_count = 0
                    start_time = time.time()
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    return
        except websockets.exceptions.ConnectionClosed:
            print("Video stream disconnected.")
        finally:
            cv2.destroyAllWindows()

    async with websockets.serve(handler, host, port):
        print(f"WebSocket video receiver listening on ws://{host}:{port}")
        await asyncio.Future()


def main() -> None:
    """Run the manual video receiver until interrupted."""
    args = parse_args()
    try:
        asyncio.run(main_async(args.host, args.port))
    except KeyboardInterrupt:
        print("\nStopping video receiver.")


if __name__ == "__main__":
    main()
