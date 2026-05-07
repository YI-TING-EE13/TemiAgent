package com.robotemi.agent.network;

import android.util.Log;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import java.util.Random;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;
import okio.ByteString;

/**
 * Resilient WebSocket client for streaming binary video data.
 * Features: exponential backoff reconnect, PING/PONG heartbeat, thread-safe sends.
 *
 * <p>Ported from TemiStream WebSocketClient — functionally identical.</p>
 */
public class WebSocketClient {
    private static final String TAG = "WebSocketClient";
    private static final long BASE_RECONNECT_DELAY_MS = 1_000L;
    private static final long MAX_RECONNECT_DELAY_MS = 15_000L;

    private final OkHttpClient client;
    private final Request request;
    private final ScheduledExecutorService reconnectExecutor;
    private final Random random = new Random();
    private final Object stateLock = new Object();

    private volatile WebSocket webSocket;
    private volatile boolean isConnected = false;
    private volatile boolean isConnecting = false;
    private volatile boolean shouldReconnect = false;

    private final AtomicInteger sendCount = new AtomicInteger(0);
    private int reconnectAttempt = 0;
    private ScheduledFuture<?> reconnectFuture;

    public WebSocketClient(String url) {
        this.client = new OkHttpClient.Builder()
                .readTimeout(0, TimeUnit.MILLISECONDS)
                .pingInterval(10, TimeUnit.SECONDS)
                .retryOnConnectionFailure(true)
                .build();
        this.request = new Request.Builder().url(url).build();
        this.reconnectExecutor = Executors.newSingleThreadScheduledExecutor();
    }

    public void connect() {
        synchronized (stateLock) {
            shouldReconnect = true;
            if (isConnected || isConnecting) return;
            scheduleConnectLocked(0);
        }
    }

    public void disconnect() {
        WebSocket socketToClose;
        synchronized (stateLock) {
            shouldReconnect = false;
            isConnected = false;
            isConnecting = false;
            reconnectAttempt = 0;
            cancelScheduledReconnectLocked();
            socketToClose = webSocket;
            webSocket = null;
        }
        if (socketToClose != null) {
            socketToClose.close(1000, "Normal Termination");
        }
        reconnectExecutor.shutdown();
        client.dispatcher().executorService().shutdown();
    }

    /**
     * Sends a binary packet (timestamp header + H.264 payload) to the server.
     */
    public void sendVideoPacket(byte[] data) {
        WebSocket socket = this.webSocket;
        if (isConnected && socket != null) {
            boolean sent = socket.send(ByteString.of(data));
            if (!sent) {
                Log.w(TAG, "Outgoing buffer full; link unstable.");
                handleDisconnected("Send rejection");
                return;
            }
            int count = sendCount.incrementAndGet();
            if (count % 100 == 0) {
                Log.i(TAG, "Video packets sent: " + count);
            }
        }
    }

    public boolean isConnected() {
        return isConnected;
    }

    // ─── Internal reconnection ────────────────────────────────────────

    private void scheduleConnectLocked(long delayMs) {
        cancelScheduledReconnectLocked();
        reconnectFuture = reconnectExecutor.schedule(() -> {
            synchronized (stateLock) {
                if (!shouldReconnect || isConnected || isConnecting) return;
                isConnecting = true;
            }
            Log.i(TAG, "Opening socket to " + request.url());
            webSocket = client.newWebSocket(request, new WebSocketListener() {
                @Override
                public void onOpen(@NonNull WebSocket ws, @NonNull Response response) {
                    synchronized (stateLock) {
                        isConnected = true;
                        isConnecting = false;
                        reconnectAttempt = 0;
                        cancelScheduledReconnectLocked();
                    }
                    Log.i(TAG, "WebSocket connected.");
                }

                @Override
                public void onMessage(@NonNull WebSocket ws, @NonNull String text) {
                    Log.d(TAG, "Server message: " + text);
                }

                @Override
                public void onClosing(@NonNull WebSocket ws, int code, @NonNull String reason) {
                    ws.close(1000, null);
                }

                @Override
                public void onClosed(@NonNull WebSocket ws, int code, @NonNull String reason) {
                    handleDisconnected("Closed: " + reason);
                }

                @Override
                public void onFailure(@NonNull WebSocket ws, @NonNull Throwable t, @Nullable Response resp) {
                    handleDisconnected("Failure: " + t.getMessage());
                }
            });
        }, delayMs, TimeUnit.MILLISECONDS);
    }

    private void handleDisconnected(String reason) {
        synchronized (stateLock) {
            isConnected = false;
            isConnecting = false;
            if (!shouldReconnect) return;
            reconnectAttempt++;
            long delay = computeReconnectDelayMs(reconnectAttempt);
            Log.w(TAG, "Link lost (" + reason + "); retry in " + delay + "ms");
            scheduleConnectLocked(delay);
        }
    }

    private long computeReconnectDelayMs(int attempt) {
        long exp = BASE_RECONNECT_DELAY_MS * (1L << Math.min(6, attempt - 1));
        long clamped = Math.min(MAX_RECONNECT_DELAY_MS, exp);
        return (long) (clamped * (0.8 + 0.4 * random.nextDouble()));
    }

    private void cancelScheduledReconnectLocked() {
        if (reconnectFuture != null) {
            reconnectFuture.cancel(false);
            reconnectFuture = null;
        }
    }
}
