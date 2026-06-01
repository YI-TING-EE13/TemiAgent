package com.robotemi.agent.mqtt;

import com.robotemi.agent.BuildConfig;

/**
 * Centralized MQTT topic definitions for the TemiAgent system.
 * Hermes bridge topics follow the convention: temi/{robot_id}/{category}/{event}.
 *
 * <p>The legacy temi/action/* topics are kept temporarily for the original
 * TemiAgent backend and manual scripts.</p>
 */
public final class MqttTopics {

    private MqttTopics() {} // Prevent instantiation

    public static final String ROBOT_ID = BuildConfig.ROBOT_ID;

    // ─── Edge -> Bridge (Temi publishes) ─────────────────────────────────

    /** Legacy ASR result used by the original TemiAgent backend. */
    public static final String EVENT_ASR_LEGACY = "temi/event/asr";

    /** Hermes-ready ASR final event topic. Published by the PC-side frame assembler. */
    public static final String EVENT_ASR_FINAL = "temi/" + ROBOT_ID + "/asr/final";

    /** Periodic telemetry: battery, position, status. */
    public static final String STATUS_TELEMETRY = "temi/" + ROBOT_ID + "/state";

    // ─── Bridge -> Edge (Temi subscribes) ────────────────────────────────

    /** Validated Hermes command request with an actions[] array. */
    public static final String COMMAND_REQUEST = "temi/" + ROBOT_ID + "/cmd/request";

    /** Command execution result published by Temi after handling a command request. */
    public static final String COMMAND_RESULT = "temi/" + ROBOT_ID + "/cmd/result";

    // ─── Legacy Cloud -> Edge topics ─────────────────────────────────────

    /** TTS command: speak text with language and continue_listening flag. */
    public static final String ACTION_SPEAK = "temi/action/speak";

    /** Navigation command: go to a saved location. */
    public static final String ACTION_NAVIGATE = "temi/action/navigate";

    /** Force-trigger wakeup/listening from server side. */
    public static final String ACTION_WAKEUP = "temi/action/wakeup";

    /** All action topics Temi must subscribe to. */
    public static final String[] SUBSCRIBED_TOPICS = {
            COMMAND_REQUEST,
            ACTION_SPEAK,
            ACTION_NAVIGATE,
            ACTION_WAKEUP
    };

    /** Default MQTT QoS level. */
    public static final int QOS = 1;
}
