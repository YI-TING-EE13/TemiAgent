package com.robotemi.agent.camera;

import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaCodecList;
import android.media.MediaFormat;
import android.os.Build;
import android.util.Log;

import androidx.annotation.NonNull;
import androidx.camera.core.ImageProxy;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/**
 * Hardware H.264 encoder for CameraX YUV_420_888 frames.
 *
 * <p><b>Relative Timestamping (Single Source of Truth):</b>
 * Every output packet is prefixed with an 8-byte big-endian timestamp
 * from {@code System.currentTimeMillis()} captured at encode time.
 * This allows the PC-B VisionBuffer to align frames using Temi's clock
 * exclusively, eliminating cross-device clock synchronization issues.</p>
 *
 * <p>Packet format: {@code [8-byte BE temi_timestamp_ms] [H.264 NAL units]}</p>
 *
 * <p>Ported from TemiStream H264Encoder with timestamp header addition.</p>
 */
public class H264Encoder {
    private static final String TAG = "H264Encoder";
    private static final String MIME_TYPE = MediaFormat.MIMETYPE_VIDEO_AVC;
    private static final int TARGET_FPS = 30;
    private static final int BITRATE = 2_500_000;
    private static final int I_FRAME_INTERVAL_SECONDS = 1;
    private static final long INPUT_TIMEOUT_US = 0L;
    private static final long OUTPUT_TIMEOUT_US = 0L;

    /** Size of the timestamp header prepended to every packet. */
    public static final int TIMESTAMP_HEADER_SIZE = 8;

    private final EncodedFrameListener listener;
    private MediaCodec encoder;
    private int width;
    private int height;
    private int colorFormat;
    private long frameIndex;
    private byte[] yuvBuffer;
    private byte[] yRowBuffer;
    private byte[] uRowBuffer;
    private byte[] vRowBuffer;
    private byte[] codecConfig;

    public interface EncodedFrameListener {
        void onEncodedFrame(byte[] data);
    }

    public H264Encoder(EncodedFrameListener listener) {
        this.listener = listener;
    }

    public void encode(@NonNull ImageProxy image) {
        try {
            ensureStarted(image.getWidth(), image.getHeight());
            drainEncoder();

            int inputBufferIndex = encoder.dequeueInputBuffer(INPUT_TIMEOUT_US);
            if (inputBufferIndex < 0) return;

            ByteBuffer inputBuffer = encoder.getInputBuffer(inputBufferIndex);
            if (inputBuffer == null) return;

            inputBuffer.clear();
            int frameSize = width * height * 3 / 2;
            if (yuvBuffer == null || yuvBuffer.length != frameSize) {
                yuvBuffer = new byte[frameSize];
            }

            copyImageToEncoderBuffer(image, yuvBuffer);
            inputBuffer.put(yuvBuffer, 0, frameSize);

            long presentationTimeUs = computePresentationTimeUs(frameIndex++);
            encoder.queueInputBuffer(inputBufferIndex, 0, frameSize, presentationTimeUs, 0);
            drainEncoder();
        } catch (Exception e) {
            Log.e(TAG, "H.264 encoding failed", e);
            restartAfterFailure();
        }
    }

    public void stop() {
        if (encoder == null) return;
        try { encoder.stop(); } catch (Exception e) { Log.w(TAG, "Encoder stop failed", e); }
        try { encoder.release(); } catch (Exception e) { Log.w(TAG, "Encoder release failed", e); }
        encoder = null;
        codecConfig = null;
        frameIndex = 0;
    }

    // ─── Timestamp header ──────────────────────────────────────────────

    /**
     * Prepends 8-byte big-endian Temi timestamp to H.264 payload.
     * This is the core of the Relative Timestamping strategy.
     */
    private byte[] prependTimestamp(byte[] h264Data) {
        long temiTimestamp = System.currentTimeMillis();
        byte[] result = new byte[TIMESTAMP_HEADER_SIZE + h264Data.length];
        ByteBuffer.wrap(result, 0, TIMESTAMP_HEADER_SIZE)
                .order(ByteOrder.BIG_ENDIAN)
                .putLong(temiTimestamp);
        System.arraycopy(h264Data, 0, result, TIMESTAMP_HEADER_SIZE, h264Data.length);
        return result;
    }

    // ─── Encoder lifecycle ─────────────────────────────────────────────

    private void ensureStarted(int newWidth, int newHeight) throws Exception {
        if (encoder != null && width == newWidth && height == newHeight) return;

        stop();
        width = newWidth;
        height = newHeight;
        colorFormat = selectColorFormat();

        MediaFormat format = MediaFormat.createVideoFormat(MIME_TYPE, width, height);
        format.setInteger(MediaFormat.KEY_COLOR_FORMAT, colorFormat);
        format.setInteger(MediaFormat.KEY_BIT_RATE, BITRATE);
        format.setInteger(MediaFormat.KEY_FRAME_RATE, TARGET_FPS);
        format.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, I_FRAME_INTERVAL_SECONDS);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            format.setInteger(MediaFormat.KEY_BITRATE_MODE,
                    MediaCodecInfo.EncoderCapabilities.BITRATE_MODE_CBR);
        }

        encoder = MediaCodec.createEncoderByType(MIME_TYPE);
        encoder.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
        encoder.start();
        frameIndex = 0;
        Log.i(TAG, "Encoder started: " + width + "x" + height + " @ " + TARGET_FPS
                + "fps, bitrate=" + BITRATE + ", timestamp header enabled");
    }

    private int selectColorFormat() {
        int[] preferredFormats = {
                MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible,
                MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Planar,
                MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420SemiPlanar
        };
        MediaCodecList codecList = new MediaCodecList(MediaCodecList.ALL_CODECS);
        for (MediaCodecInfo codecInfo : codecList.getCodecInfos()) {
            if (!codecInfo.isEncoder()) continue;
            for (String type : codecInfo.getSupportedTypes()) {
                if (!MIME_TYPE.equalsIgnoreCase(type)) continue;
                MediaCodecInfo.CodecCapabilities caps = codecInfo.getCapabilitiesForType(type);
                for (int pref : preferredFormats) {
                    for (int supported : caps.colorFormats) {
                        if (supported == pref) {
                            Log.i(TAG, "Encoder: " + codecInfo.getName() + ", format=" + pref);
                            return pref;
                        }
                    }
                }
            }
        }
        Log.w(TAG, "Falling back to COLOR_FormatYUV420Flexible");
        return MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible;
    }

    // ─── Frame data extraction ─────────────────────────────────────────

    private void copyImageToEncoderBuffer(@NonNull ImageProxy image, byte[] out) {
        int ySize = width * height;
        int chromaSize = ySize / 4;

        copyPlane(image.getPlanes()[0], width, height, out, 0, width, 1);

        boolean planar = colorFormat == MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Planar
                || colorFormat == MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible;
        if (planar) {
            copyPlane(image.getPlanes()[1], width / 2, height / 2, out, ySize, width / 2, 1);
            copyPlane(image.getPlanes()[2], width / 2, height / 2, out, ySize + chromaSize, width / 2, 1);
        } else {
            copyChromaToNv12(image.getPlanes()[1], image.getPlanes()[2], out, ySize);
        }
    }

    private void copyPlane(@NonNull ImageProxy.PlaneProxy plane,
                           int planeWidth, int planeHeight,
                           byte[] out, int outOffset, int outRowStride, int outPixelStride) {
        ByteBuffer buffer = plane.getBuffer();
        int rowStride = plane.getRowStride();
        int pixelStride = plane.getPixelStride();
        byte[] rowBuffer = pixelStride == 1 && outPixelStride == 1
                ? null
                : getReusableRowBuffer(rowStride);
        Yuv420PlaneCopier.copy(
                buffer,
                rowStride,
                pixelStride,
                planeWidth,
                planeHeight,
                out,
                outOffset,
                outRowStride,
                outPixelStride,
                rowBuffer);
    }

    private byte[] getReusableRowBuffer(int rowStride) {
        if (rowStride <= width) {
            if (yRowBuffer == null || yRowBuffer.length < rowStride) {
                yRowBuffer = new byte[rowStride];
            }
            return yRowBuffer;
        }
        if (uRowBuffer == null || uRowBuffer.length < rowStride) {
            uRowBuffer = new byte[rowStride];
        }
        return uRowBuffer;
    }

    private void copyChromaToNv12(@NonNull ImageProxy.PlaneProxy uPlane,
                                  @NonNull ImageProxy.PlaneProxy vPlane,
                                  byte[] out, int outOffset) {
        ByteBuffer uBuf = uPlane.getBuffer(), vBuf = vPlane.getBuffer();
        int uStride = uPlane.getRowStride(), vStride = vPlane.getRowStride();
        int uPix = uPlane.getPixelStride(), vPix = vPlane.getPixelStride();

        if (uRowBuffer == null || uRowBuffer.length < uStride) uRowBuffer = new byte[uStride];
        if (vRowBuffer == null || vRowBuffer.length < vStride) vRowBuffer = new byte[vStride];

        for (int row = 0; row < height / 2; row++) {
            int uStart = row * uStride, vStart = row * vStride;
            int uLen = Math.min(uStride, uBuf.limit() - uStart);
            int vLen = Math.min(vStride, vBuf.limit() - vStart);
            if (uLen <= 0 || vLen <= 0) break;

            uBuf.position(uStart); uBuf.get(uRowBuffer, 0, uLen);
            vBuf.position(vStart); vBuf.get(vRowBuffer, 0, vLen);

            for (int col = 0; col < width / 2; col++) {
                int idx = outOffset + row * width + col * 2;
                out[idx] = uRowBuffer[col * uPix];
                out[idx + 1] = vRowBuffer[col * vPix];
            }
        }
    }

    // ─── Output drain ──────────────────────────────────────────────────

    private void drainEncoder() {
        if (encoder == null) return;
        MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
        while (true) {
            int idx = encoder.dequeueOutputBuffer(info, OUTPUT_TIMEOUT_US);
            if (idx == MediaCodec.INFO_TRY_AGAIN_LATER) return;
            if (idx == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                cacheCodecConfig(encoder.getOutputFormat());
                continue;
            }
            if (idx < 0) continue;

            ByteBuffer outBuf = encoder.getOutputBuffer(idx);
            if (outBuf != null && info.size > 0) {
                outBuf.position(info.offset);
                outBuf.limit(info.offset + info.size);
                byte[] encoded = new byte[info.size];
                outBuf.get(encoded);

                if ((info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0) {
                    codecConfig = encoded;
                } else if (listener != null) {
                    byte[] h264Payload;
                    if ((info.flags & MediaCodec.BUFFER_FLAG_KEY_FRAME) != 0 && codecConfig != null) {
                        h264Payload = concat(codecConfig, encoded);
                    } else {
                        h264Payload = encoded;
                    }
                    // Prepend Temi timestamp before sending
                    listener.onEncodedFrame(prependTimestamp(h264Payload));
                }
            }
            encoder.releaseOutputBuffer(idx, false);
        }
    }

    private void cacheCodecConfig(MediaFormat format) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        appendFormatBuffer(format, "csd-0", out);
        appendFormatBuffer(format, "csd-1", out);
        byte[] data = out.toByteArray();
        if (data.length > 0) codecConfig = data;
    }

    private void appendFormatBuffer(MediaFormat format, String key, ByteArrayOutputStream out) {
        if (!format.containsKey(key)) return;
        ByteBuffer buf = format.getByteBuffer(key);
        if (buf == null) return;
        ByteBuffer dup = buf.duplicate();
        byte[] data = new byte[dup.remaining()];
        dup.get(data);
        out.write(data, 0, data.length);
    }

    private byte[] concat(byte[] a, byte[] b) {
        byte[] result = new byte[a.length + b.length];
        System.arraycopy(a, 0, result, 0, a.length);
        System.arraycopy(b, 0, result, a.length, b.length);
        return result;
    }

    private long computePresentationTimeUs(long frameIndex) {
        return 132L + frameIndex * 1_000_000L / TARGET_FPS;
    }

    private void restartAfterFailure() {
        stop();
    }
}
