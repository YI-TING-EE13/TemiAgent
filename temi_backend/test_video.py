import av
import websockets
import asyncio
import struct
import cv2
import time

async def stream_handler(websocket):
    print("Video stream connected!")
    
    # Initialize PyAV codec context for H.264
    codec = av.CodecContext.create('h264', 'r')
    
    frame_count = 0
    start_time = time.time()
    
    try:
        async for message in websocket:
            if isinstance(message, bytes):
                if len(message) < 8:
                    continue
                
                # 1. Extract 8-byte timestamp (Big-Endian long)
                timestamp_ms = struct.unpack(">q", message[:8])[0]
                
                # 2. Extract H.264 payload
                h264_payload = message[8:]
                
                # 3. Decode H.264 payload
                try:
                    packets = codec.parse(h264_payload)
                    for packet in packets:
                        frames = codec.decode(packet)
                        for frame in frames:
                            # Convert PyAV frame to OpenCV BGR format
                            img = frame.to_ndarray(format='bgr24')
                            
                            # Rotate 180 degrees (Temi's camera is upside down)
                            img = cv2.rotate(img, cv2.ROTATE_180)
                            
                            # Display overlay
                            cv2.putText(img, f"Temi Time: {timestamp_ms} ms", (20, 50),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
                            cv2.imshow("Temi Video Stream", img)
                            
                            frame_count += 1
                            if frame_count % 30 == 0:
                                fps = frame_count / (time.time() - start_time)
                                print(f"FPS: {fps:.2f}, Temi Time: {timestamp_ms}")
                                frame_count = 0
                                start_time = time.time()
                            
                            if cv2.waitKey(1) & 0xFF == ord('q'):
                                return
                except av.error.InvalidDataError:
                    # Ignore early decoding errors before the first I-frame (Keyframe) arrives
                    pass
                except Exception as e:
                    print(f"Decode error: {e}")
                    
    except websockets.exceptions.ConnectionClosed:
        print("Video stream disconnected.")
    finally:
        cv2.destroyAllWindows()

async def main():
    async with websockets.serve(stream_handler, "0.0.0.0", 8080):
        print("WebSocket Video Receiver started on ws://0.0.0.0:8080")
        print("Waiting for Temi to connect and stream video...")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
