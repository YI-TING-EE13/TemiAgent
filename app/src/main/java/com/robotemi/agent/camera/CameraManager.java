package com.robotemi.agent.camera;

import android.content.Context;
import android.graphics.ImageFormat;
import android.util.Log;
import android.util.Size;

import androidx.camera.core.CameraInfoUnavailableException;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.ImageAnalysis;
import androidx.camera.core.ImageProxy;
import androidx.camera.core.Preview;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.content.ContextCompat;
import androidx.lifecycle.LifecycleOwner;

import com.google.common.util.concurrent.ListenableFuture;

import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * CameraX handler for the Temi robot.
 * Captures YUV_420_888 frames and feeds them into the H.264 hardware encoder
 * for low-bandwidth, low-latency streaming.
 *
 * <p>Ported from TemiStream with identical capture pipeline.</p>
 */
public class CameraManager {
    private static final String TAG = "CameraManager";
    private static final Size STREAM_RESOLUTION = new Size(1280, 720);

    private final ExecutorService cameraExecutor;
    private final OnFrameAvailableListener listener;
    private final H264Encoder h264Encoder;

    /**
     * Callback for encoded H.264 video data with Temi-local timestamp.
     */
    public interface OnFrameAvailableListener {
        /**
         * Called when one H.264 access unit (with timestamp header) is available.
         * @param videoData Binary payload: [8-byte BE timestamp] + [H.264 NAL units]
         */
        void onFrameAvailable(byte[] videoData);
    }

    public CameraManager(OnFrameAvailableListener listener) {
        this.listener = listener;
        this.cameraExecutor = Executors.newSingleThreadExecutor();
        this.h264Encoder = new H264Encoder(data -> {
            if (this.listener != null) {
                this.listener.onFrameAvailable(data);
            }
        });
    }

    /**
     * Initializes CameraX and binds the lifecycle to the provided Activity.
     */
    public void startCamera(Context context, LifecycleOwner lifecycleOwner, PreviewView previewView) {
        ListenableFuture<ProcessCameraProvider> cameraProviderFuture =
                ProcessCameraProvider.getInstance(context);

        cameraProviderFuture.addListener(() -> {
            try {
                ProcessCameraProvider cameraProvider = cameraProviderFuture.get();

                // 1. Preview: shows camera output on robot screen
                Preview preview = new Preview.Builder().build();
                preview.setSurfaceProvider(previewView.getSurfaceProvider());

                // 2. ImageAnalysis: raw frames for H.264 encoding
                ImageAnalysis imageAnalysis = new ImageAnalysis.Builder()
                        .setTargetResolution(STREAM_RESOLUTION)
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build();

                imageAnalysis.setAnalyzer(cameraExecutor, image -> {
                    try {
                        processImage(image);
                    } finally {
                        image.close();
                    }
                });

                // Bind to lifecycle
                cameraProvider.unbindAll();
                CameraSelector selector = selectCameraSelector(cameraProvider);
                cameraProvider.bindToLifecycle(lifecycleOwner, selector, preview, imageAnalysis);
                Log.i(TAG, "CameraX bound successfully.");

            } catch (ExecutionException | InterruptedException e) {
                Log.e(TAG, "CameraX initialization failure", e);
            }
        }, ContextCompat.getMainExecutor(context));
    }

    private CameraSelector selectCameraSelector(ProcessCameraProvider cameraProvider) {
        try {
            if (cameraProvider.hasCamera(CameraSelector.DEFAULT_FRONT_CAMERA)) {
                return CameraSelector.DEFAULT_FRONT_CAMERA;
            }
            if (cameraProvider.hasCamera(CameraSelector.DEFAULT_BACK_CAMERA)) {
                return CameraSelector.DEFAULT_BACK_CAMERA;
            }
        } catch (CameraInfoUnavailableException e) {
            Log.w(TAG, "Camera query failed, falling back to front camera.", e);
        }
        return CameraSelector.DEFAULT_FRONT_CAMERA;
    }

    private void processImage(ImageProxy image) {
        try {
            if (image.getFormat() != ImageFormat.YUV_420_888) {
                Log.w(TAG, "Unsupported format: " + image.getFormat());
                return;
            }
            h264Encoder.encode(image);
        } catch (Exception e) {
            Log.e(TAG, "Frame processing failed", e);
        }
    }

    /**
     * Releases camera executor and encoder resources.
     */
    public void shutdown() {
        h264Encoder.stop();
        cameraExecutor.shutdown();
    }
}
