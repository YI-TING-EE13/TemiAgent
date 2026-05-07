package com.robotemi.agent.mqtt;

import android.util.Log;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import org.eclipse.paho.client.mqttv3.IMqttDeliveryToken;
import org.eclipse.paho.client.mqttv3.MqttCallback;
import org.eclipse.paho.client.mqttv3.MqttClient;
import org.eclipse.paho.client.mqttv3.MqttConnectOptions;
import org.eclipse.paho.client.mqttv3.MqttException;
import org.eclipse.paho.client.mqttv3.MqttMessage;
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence;

import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Thread-safe MQTT client wrapper with automatic reconnection.
 *
 * <p>All network operations are offloaded to a dedicated background thread.
 * Incoming messages are dispatched via the {@link OnMqttMessageListener} callback.</p>
 */
public class MqttManager {
    private static final String TAG = "MqttManager";
    private static final long RECONNECT_DELAY_MS = 5_000L;
    private static final int CONNECT_TIMEOUT_SECONDS = 10;
    private static final int KEEP_ALIVE_INTERVAL_SECONDS = 30;

    private final String brokerUrl;
    private final String clientId;
    private final ExecutorService executor;
    private final ScheduledExecutorService reconnectScheduler;
    private final AtomicBoolean shouldReconnect = new AtomicBoolean(false);

    @Nullable private MqttClient client;
    @Nullable private OnMqttMessageListener messageListener;
    @Nullable private OnMqttConnectionListener connectionListener;
    @Nullable private ScheduledFuture<?> reconnectFuture;

    /**
     * Callback for incoming MQTT messages.
     */
    public interface OnMqttMessageListener {
        void onMessage(@NonNull String topic, @NonNull String payload);
    }

    /**
     * Callback for MQTT connection state changes.
     */
    public interface OnMqttConnectionListener {
        void onConnected();
        void onDisconnected(String reason);
    }

    public MqttManager(@NonNull String brokerUrl, @NonNull String clientId) {
        this.brokerUrl = brokerUrl;
        this.clientId = clientId;
        this.executor = Executors.newSingleThreadExecutor();
        this.reconnectScheduler = Executors.newSingleThreadScheduledExecutor();
    }

    public void setMessageListener(@Nullable OnMqttMessageListener listener) {
        this.messageListener = listener;
    }

    public void setConnectionListener(@Nullable OnMqttConnectionListener listener) {
        this.connectionListener = listener;
    }

    /**
     * Initiates connection to the MQTT broker on a background thread.
     */
    public void connect() {
        shouldReconnect.set(true);
        executor.submit(this::connectInternal);
    }

    /**
     * Disconnects and releases all resources. Instance should not be reused.
     */
    public void disconnect() {
        shouldReconnect.set(false);
        cancelReconnect();
        executor.submit(() -> {
            try {
                if (client != null && client.isConnected()) {
                    client.disconnect();
                    Log.i(TAG, "Disconnected from broker.");
                }
            } catch (MqttException e) {
                Log.w(TAG, "Error during disconnect", e);
            } finally {
                closeClient();
            }
        });
        executor.shutdown();
        reconnectScheduler.shutdown();
    }

    /**
     * Publishes a JSON string to the specified topic.
     */
    public void publish(@NonNull String topic, @NonNull String jsonPayload) {
        executor.submit(() -> {
            try {
                if (client != null && client.isConnected()) {
                    MqttMessage msg = new MqttMessage(
                            jsonPayload.getBytes(StandardCharsets.UTF_8));
                    msg.setQos(MqttTopics.QOS);
                    client.publish(topic, msg);
                } else {
                    Log.w(TAG, "Cannot publish — not connected. Topic: " + topic);
                }
            } catch (MqttException e) {
                Log.e(TAG, "Publish failed on topic: " + topic, e);
            }
        });
    }

    /**
     * Returns current connection status.
     */
    public boolean isConnected() {
        return client != null && client.isConnected();
    }

    // ─── Internal ─────────────────────────────────────────────────────────

    private void connectInternal() {
        try {
            closeClient();
            client = new MqttClient(brokerUrl, clientId, new MemoryPersistence());
            client.setCallback(mqttCallback);

            MqttConnectOptions opts = new MqttConnectOptions();
            opts.setCleanSession(true);
            opts.setConnectionTimeout(CONNECT_TIMEOUT_SECONDS);
            opts.setKeepAliveInterval(KEEP_ALIVE_INTERVAL_SECONDS);
            opts.setAutomaticReconnect(false); // We handle reconnect ourselves

            Log.i(TAG, "Connecting to broker: " + brokerUrl);
            client.connect(opts);
            Log.i(TAG, "Connected successfully.");

            // Subscribe to all action topics
            for (String topic : MqttTopics.SUBSCRIBED_TOPICS) {
                client.subscribe(topic, MqttTopics.QOS);
                Log.i(TAG, "Subscribed to: " + topic);
            }

            if (connectionListener != null) {
                connectionListener.onConnected();
            }
        } catch (MqttException e) {
            Log.e(TAG, "Connection failed: " + e.getMessage());
            if (connectionListener != null) {
                connectionListener.onDisconnected(e.getMessage());
            }
            scheduleReconnect();
        }
    }

    private void scheduleReconnect() {
        if (!shouldReconnect.get()) return;
        cancelReconnect();
        Log.i(TAG, "Scheduling reconnect in " + RECONNECT_DELAY_MS + "ms");
        reconnectFuture = reconnectScheduler.schedule(
                this::connectInternal, RECONNECT_DELAY_MS, TimeUnit.MILLISECONDS);
    }

    private void cancelReconnect() {
        if (reconnectFuture != null) {
            reconnectFuture.cancel(false);
            reconnectFuture = null;
        }
    }

    private void closeClient() {
        if (client != null) {
            try {
                client.close();
            } catch (Exception ignored) {}
            client = null;
        }
    }

    private final MqttCallback mqttCallback = new MqttCallback() {
        @Override
        public void connectionLost(Throwable cause) {
            String reason = cause != null ? cause.getMessage() : "Unknown";
            Log.w(TAG, "Connection lost: " + reason);
            if (connectionListener != null) {
                connectionListener.onDisconnected(reason);
            }
            scheduleReconnect();
        }

        @Override
        public void messageArrived(String topic, MqttMessage message) {
            String payload = new String(message.getPayload(), StandardCharsets.UTF_8);
            Log.d(TAG, "Message on [" + topic + "]: " + payload);
            if (messageListener != null) {
                messageListener.onMessage(topic, payload);
            }
        }

        @Override
        public void deliveryComplete(IMqttDeliveryToken token) {
            // No action needed for fire-and-forget publishes
        }
    };
}
