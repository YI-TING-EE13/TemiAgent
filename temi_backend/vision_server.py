"""
WebSocket Vision Server for TemiAgent.

This module acts as the sensory visual cortex. It receives the H.264 video stream from
the Temi robot via WebSocket, decodes the stream using PyAV, and pushes the decoded
BGR frames into a thread-safe rolling buffer mapped precisely to the hardware's 
Single Source of Truth (SSoT) timestamp.
"""

import av
import websockets
import asyncio
import struct
import cv2
import numpy as np
import threading
import collections
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')


class VisionBuffer:
    """
    A thread-safe rolling buffer that caches chronological video frames.

    Retains the latest N seconds of video history to enable backward keyframe
    sampling for gesture and temporal manifold alignment.
    """

    def __init__(self, max_seconds: int = 10, fps: int = 30):
        """
        Initialize the VisionBuffer.

        Args:
            max_seconds (int): The maximum duration of video history to retain.
            fps (int): Estimated frames per second from the source stream.
        """
        # Store tuples of (timestamp_ms, frame_bgr)
        self.buffer = collections.deque(maxlen=max_seconds * fps)
        self.lock = threading.Lock()

    def push(self, timestamp_ms: int, frame: np.ndarray) -> None:
        """
        Append a new frame to the buffer in a thread-safe manner.

        Args:
            timestamp_ms (int): The hardware timestamp from Temi.
            frame (np.ndarray): The decoded BGR OpenCV image.
        """
        with self.lock:
            self.buffer.append((timestamp_ms, frame))

    def get_keyframes(self, target_ms: int) -> list:
        """
        Extract 3 asymmetric frames: T-1000ms, T-500ms, T.

        This mechanism captures the Stroke, Apex, and Conclusion of a human gesture.

        Args:
            target_ms (int): The baseline timestamp (e.g., end of speech).

        Returns:
            list: A list of dicts containing the targeted time, actual time, and frame data.
        """
        offsets = [-1000, -500, 0]
        results = []
        
        with self.lock:
            if not self.buffer:
                logging.warning("VisionBuffer is empty!")
                return []
            
            # Helper to find closest frame chronologically
            def find_closest(t_target):
                return min(self.buffer, key=lambda x: abs(x[0] - t_target))

            for offset in offsets:
                closest_timestamp, closest_frame = find_closest(target_ms + offset)
                # Return a deep copy of the frame to prevent modification issues
                results.append({
                    "target_t": target_ms + offset,
                    "actual_t": closest_timestamp,
                    "frame": closest_frame.copy()
                })
        return results


class VisionServer:
    """
    WebSocket server handling incoming H.264 streams and decoding them.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        """
        Initialize the Vision Server.

        Args:
            host (str): Bind IP address.
            port (int): Bind Port.
        """
        self.host = host
        self.port = port
        self.buffer = VisionBuffer()

    async def stream_handler(self, websocket) -> None:
        """
        Asynchronous handler for incoming WebSocket connections.

        Parses the 8-byte big-endian timestamp header and decodes the subsequent NAL units.

        Args:
            websocket: The active WebSocket connection object.
        """
        logging.info("VisionServer: Video stream connected!")
        codec = av.CodecContext.create('h264', 'r')
        
        try:
            async for message in websocket:
                if isinstance(message, bytes) and len(message) >= 8:
                    # 1. Extract Temi Timestamp (8-byte Big-Endian)
                    timestamp_ms = struct.unpack(">q", message[:8])[0]
                    h264_payload = message[8:]
                    
                    try:
                        packets = codec.parse(h264_payload)
                        for packet in packets:
                            frames = codec.decode(packet)
                            for frame in frames:
                                img = frame.to_ndarray(format='bgr24')
                                img = cv2.rotate(img, cv2.ROTATE_180) # Temi hardware specific
                                self.buffer.push(timestamp_ms, img)
                    except av.error.InvalidDataError:
                        pass # Wait patiently for the next I-frame
                    except Exception as e:
                        logging.error(f"Decode error: {e}")
        except websockets.exceptions.ConnectionClosed:
            logging.info("VisionServer: Video stream disconnected.")

    async def start(self) -> None:
        """Launch the asyncio WebSocket server."""
        async with websockets.serve(self.stream_handler, self.host, self.port):
            logging.info(f"VisionServer started on ws://{self.host}:{self.port}")
            await asyncio.Future()

    def run_in_background(self) -> threading.Thread:
        """
        Start the asyncio loop in a separate daemon thread.

        Returns:
            threading.Thread: The active background thread object.
        """
        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.start())
            
        t = threading.Thread(target=run_loop, daemon=True)
        t.start()
        return t
