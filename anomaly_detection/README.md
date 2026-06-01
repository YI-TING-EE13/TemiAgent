# Temi Anomaly Detection Stream Viewer

This folder is an isolated `uv` project for testing continuous Temi camera intake.

The viewer accepts Temi's timestamp-prefixed H.264 WebSocket stream and exposes a browser MJPEG preview on the same HTTP port.

## Run

```bash
cd /TemiAgent/anomaly_detection
uv sync
uv run temi-live-viewer --host 0.0.0.0 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

Point Temi's video WebSocket target to one of:

```text
ws://<container-or-host-ip>:8000/
ws://<container-or-host-ip>:8000/ws
```

## Endpoints

- `/` browser page and WebSocket intake when the request is a WebSocket upgrade.
- `/ws` explicit WebSocket intake path.
- `/stream.mjpg` MJPEG stream for the browser.
- `/snapshot.jpg` latest frame as JPEG.
- `/health` JSON status.

## Notes

- MQTT is not used for image bytes.
- The server keeps only the latest JPEG frame in memory.
- This is a test viewer, not the final abnormal behavior model pipeline.
