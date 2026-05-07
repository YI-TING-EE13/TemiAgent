package com.robotemi.agent.mqtt;

/**
 * Centralized MQTT topic definitions for the TemiAgent system.
 * All topics follow the convention: temi/{direction}/{category}
 *
 * <p>Edge → Cloud topics are PUBLISHED by Temi, SUBSCRIBED by PC-B.
 * Cloud → Edge topics are PUBLISHED by PC-B, SUBSCRIBED by Temi.</p>
 */
public final class MqttTopics {

    private MqttTopics() {} // Prevent instantiation

    // ─── Edge → Cloud (Temi publishes) ───────────────────────────────────

    /** ASR result with wakeup timestamp for Frame Lock alignment. */
    public static final String EVENT_ASR = "temi/event/asr";

    /** Periodic telemetry: battery, position, status. */
    public static final String STATUS_TELEMETRY = "temi/status/telemetry";

    // ─── Cloud → Edge (PC-B publishes, Temi subscribes) ─────────────────

    /** TTS command: speak text with language and continue_listening flag. */
    public static final String ACTION_SPEAK = "temi/action/speak";

    /** Navigation command: go to a saved location. */
    public static final String ACTION_NAVIGATE = "temi/action/navigate";

    /** Force-trigger wakeup/listening from server side. */
    public static final String ACTION_WAKEUP = "temi/action/wakeup";

    /** All action topics Temi must subscribe to. */
    public static final String[] SUBSCRIBED_TOPICS = {
            ACTION_SPEAK,
            ACTION_NAVIGATE,
            ACTION_WAKEUP
    };

    /** Default MQTT QoS level. */
    public static final int QOS = 1;
}
