# YUV Copy Performance Optimization — 2026-08-09

## Scope

This change reduces CPU time in the 1280x720 camera preprocessing step that
copies CameraX `YUV_420_888` planes into the packed buffer consumed by the H.264
encoder. The benchmark excludes CameraX capture, `MediaCodec` encoding,
WebSocket transmission, UI rendering, memory use, power use, and end-to-end
latency.

A separate smoke test on the documented `.204` Temi target used an APK built
from the same production implementation in the canonical Android worktree.
The App remained resumed, held camera device 1, initialized the encoder at
1280x720 and 30 FPS, retained App and Agent-status UI nodes, and produced no
target crash, frame-processing, or encoding-failure match during the bounded
test window. The smoke test sent no movement, MQTT, or media command and ended
with an explicit ADB disconnect.

## Bottleneck and change

The previous `H264Encoder.copyPlane(...)` copied each source row into a scratch
array and then copied every visible sample with a Java loop. A 1280x720 YUV
4:2:0 frame contains 1,382,400 visible samples, or about 41.5 million samples
per second at the configured 30 FPS.

`Yuv420PlaneCopier` now uses `ByteBuffer.get(byte[], offset, length)` for packed
source and target rows. Interleaved chroma planes retain the strided path. The
encoder continues to reuse its frame and scratch buffers, so the change adds no
per-frame array allocation.

## Measurement method

The standalone benchmark preserves the previous implementation as `legacy`
and invokes the production `Yuv420PlaneCopier` as `optimized`. It requires
byte-for-byte equality before timing either implementation.

- Repository baseline: `YI-TING-EE13/TemiAgent` main commit `12156ba`
- Runtime: Alibaba Dragonwell Extended Edition 21.0.11.0.11, 64-bit Server VM
- Architecture: Windows `amd64`
- Sampling per process: 50 warm-ups, 15 samples, 20 frames per sample
- Repetitions: three independent Java processes

Run from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\benchmark_yuv_copy.ps1 `
  -JavaHomePath 'C:\path\to\jdk-21'
```

## Results

The table uses the median of the three process-level results for each metric.

| Source layout | Metric | Previous | Current | Reduction |
|---|---:|---:|---:|---:|
| Interleaved chroma to planar | Median | 0.607 ms/frame | 0.206 ms/frame | 66.1% |
| Interleaved chroma to planar | p95 | 0.616 ms/frame | 0.213 ms/frame | 65.4% |
| Planar to planar | Median | 0.592 ms/frame | 0.044 ms/frame | 92.6% |
| Planar to planar | p95 | 0.602 ms/frame | 0.047 ms/frame | 92.2% |

All six layout/process combinations reported `output_equal=true`.

## Verification

- `Yuv420PlaneCopierTest`: PASS, 4 tests, 0 failures, 0 errors, 0 skipped.
- Debug Java compile, JVM tests, APK assembly, and lint tasks: PASS.
- Lint report: one baseline error and 23 warnings; the YUV change added no lint
  finding.
- Debug APK: 5,575,593 bytes,
  SHA-256 `05CA88A476CAB1F64FDCE5512EBBFDF768176E48A0CF70F86DE00D7DA58952DC`.
  Build evidence does not replace exact-tree real-device acceptance.

## Limits and rollback

Desktop JVM timing does not prove the same percentage on Android Runtime or
Temi hardware. Real-device CPU, frame cadence, thermal behavior, power use,
and end-to-end latency improvement remain unverified.

Reverting the performance commit restores the previous copy path without
changing camera resolution, frame rate, encoder settings, packet format,
MQTT/WebSocket endpoints, or robot controls.
