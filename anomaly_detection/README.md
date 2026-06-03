# Temi Anomaly Detection Stream Viewer

This folder is an isolated `uv` project for testing continuous Temi camera intake.

The viewer provides a browser page on port `8000`.

The browser page can connect directly to the decoded JPEG frame broadcast endpoint:

```text
ws://<pc-ip>:8081
```

It can also still accept Temi's timestamp-prefixed H.264 WebSocket stream and expose a browser MJPEG preview on the same HTTP port.

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

By default, the page connects to:

```text
ws://<same-host-as-page>:8081
```

The page decodes the `8081` binary frame format in JavaScript:

```text
bytes 0..7    int64 big-endian timestamp_ms
bytes 8..15   uint64 big-endian sequence
bytes 16..    JPEG image bytes
```

`8081` must be provided by the TemiAgent `JpegFrameBroadcaster`; it is not an HTTP page.

Point Temi's video WebSocket target to one of:

```text
ws://<container-or-host-ip>:8000/
ws://<container-or-host-ip>:8000/ws
```

## Endpoints

- `/` browser page for `8081` decoded JPEG broadcast, and WebSocket intake when the request is a WebSocket upgrade.
- `/ws` explicit WebSocket intake path.
- `/stream.mjpg` MJPEG stream for the browser.
- `/snapshot.jpg` latest frame as JPEG.
- `/health` JSON status.

## Action prediction viewer

`temi_action_viewer.py` reads decoded JPEG frames from `8081`, samples eight frames, optionally draws YOLO pose skeletons for model input, sends the frames to a llama.cpp multimodal server, and overlays the predicted visible human action in the top-left corner.

Sampling policy:

- Three frames from the previous three one-second windows.
- Five frames from the latest one-second window.
- Total: eight chronological frames per prediction.
- The current second is sampled uniformly at inference time.
- The completed-second history representative is the second sampled frame when available, otherwise the first frame.

Run:

```bash
cd /TemiAgent/anomaly_detection
.venv/bin/python temi_action_viewer.py \
  --host 0.0.0.0 \
  --port 8010 \
  --source-url ws://127.0.0.1:8081 \
  --model gemma-4-e4b-finetuned@q8_0 \
  --gguf-model-path /TemiAgent/.lmstudio-data/models/lmstudio-community/gemma-4-E4B-finetuned-GGUF/local_unsloth_gemma4.Q8_0.gguf \
  --mmproj-path /TemiAgent/.lmstudio-data/models/lmstudio-community/gemma-4-E4B-finetuned-GGUF/local_unsloth_gemma4.BF16-mmproj.gguf
```

By default the action viewer expects `llama-server` at:

```text
/TemiAgent/anomaly_detection/third_party/llama.cpp/build/bin/llama-server
```

If the binary is missing, the browser viewer still starts and `/health` reports `llama_server_ready: false` with the missing path. To connect to an already running llama.cpp server instead of letting the viewer start one, pass:

```bash
--llama-api-base-url http://127.0.0.1:8011/v1
```

YOLO pose preprocessing is controlled by:

```bash
--pose-mode auto --pose-model yolo26x-pose.pt --pose-device 0
```

`auto` uses skeleton overlays only when `ultralytics` and the pose model file are available. `on` fails fast if either is missing. `off` sends raw frames.
`--pose-device 0` forces YOLO pose inference onto GPU 0; use `cpu` only for debugging.

Open:

```text
http://127.0.0.1:8010/
```

Endpoints:

- `/` browser page with prediction overlay stream.
- `/stream.mjpg` MJPEG stream with overlay.
- `/snapshot.jpg` latest overlay frame.
- `/health` JSON status.

The model prompt asks for exactly:

```text
action_name:...
reason:...
```

The parser also accepts the reference format `Action:` and `Evidence/Reason:`.

## Notes

- MQTT is not used for image bytes.
- The server keeps only the latest JPEG frame in memory.
- This is a test viewer, not the final abnormal behavior model pipeline.


## Safe restart for 8010

Do not restart this service with `pkill -f` or broad process-name patterns. A pattern such as `pkill -f "temi_action_viewer.py ..."` can match the shell that is running the restart command, causing the shell to kill itself before the service is relaunched.

Use the dedicated restart script instead:

```bash
cd /TemiAgent/anomaly_detection
./restart_action_viewer_8010.sh
```

The script only inspects the process currently listening on port `8010`, verifies that the PID is running `temi_action_viewer.py` from `/TemiAgent/anomaly_detection`, then stops that exact PID and starts a fresh viewer. It does not touch MQTT, 8080 ingest, 8081 frame broadcast, Hermes resident server, Bridge, or the 8000 live viewer.
