package com.robotemi.agent;

import android.Manifest;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.util.Log;
import android.view.View;
import android.widget.TextView;
import android.widget.Toast;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.VideoView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.camera.view.PreviewView;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.robotemi.agent.camera.CameraManager;
import com.robotemi.agent.command.CanonicalCommandValidator;
import com.robotemi.agent.command.CanonicalCommandValidator.CanonicalAction;
import com.robotemi.agent.command.CanonicalCommandValidator.CanonicalCommand;
import com.robotemi.agent.command.CanonicalMediaTracker;
import com.robotemi.agent.command.CanonicalTtsTracker;
import com.robotemi.agent.command.ProcessCommandRegistry;
import com.robotemi.agent.mqtt.MqttManager;
import com.robotemi.agent.mqtt.MqttTopics;
import com.robotemi.agent.network.WebSocketClient;
import com.robotemi.sdk.NlpResult;
import com.robotemi.sdk.Robot;
import com.robotemi.sdk.SttLanguage;
import com.robotemi.sdk.TtsRequest;
import com.robotemi.sdk.listeners.OnRobotReadyListener;

import org.json.JSONException;
import org.json.JSONArray;
import org.json.JSONObject;

import com.robotemi.agent.agent.AgentStateMachine;

import java.util.ArrayList;
import java.util.ArrayDeque;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

/**
 * TemiAgent Main Controller & Embodied AI Orchestrator.
 *
 * <p>This activity serves as the primary integration point for the Temi SDK,
 * CameraX hardware streaming, and the MQTT/WebSocket telemetry bridges.</p>
 *
 * <p>It initializes the {@link AgentStateMachine} to manage the dialogue lifecycle
 * safely, ensuring that physical hardware interrupts (touch) and VLM timeouts
 * are handled deterministically without blocking the UI thread.</p>
 * 
 * <p>Multicast Edition: Supports broadcasting telemetry (Vision/ASR) to multiple
 * PC backends simultaneously (e.g. Original Backend + Hermes Agent).</p>
 */
public class MainActivity extends AppCompatActivity
        implements OnRobotReadyListener, MqttManager.OnMqttMessageListener,
                   MqttManager.OnMqttConnectionListener,
                   Robot.AsrListener, Robot.WakeupWordListener,
                   Robot.TtsListener, Robot.NlpListener,
                   AgentStateMachine.StateChangeListener {

    private static final String TAG = "MainActivity";
    private static final int PERMISSION_REQUEST_CODE = 1001;
    private static final String CUSTOM_WAKE_WORD = "\u5c0f\u5b89";
    private static final String[] CUSTOM_WAKE_WORD_VARIANTS = {
            "\u5c0f\u5b89",
            "\u5c0f\u5b89\u4f60\u597d",
            "\u4f60\u597d\u5c0f\u5b89",
            "\u5c0f\u6069",
            "\u5c0f\u5eb5",
            "\u5c0f\u978d",
            "\u6653\u5b89",
            "\u6653\u6069",
            "\u6653\u5eb5",
            "\u6821\u5b89",
            "\u7b11\u5b89"
    };
    private static final int HOTWORD_RESTART_DELAY_MS = 250;

    // ─── Components ───────────────────────────────────────────────────
    private Robot robot;
    private CameraManager cameraManager;
    private List<WebSocketClient> webSocketClients = new ArrayList<>();
    private List<MqttManager> mqttManagers = new ArrayList<>();
    private AgentStateMachine stateMachine;
    private boolean shouldContinueListening = false;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private SpeechRecognizer hotwordRecognizer;
    private Intent hotwordIntent;
    private boolean hotwordEnabled = false;
    private boolean hotwordListening = false;
    private boolean acceptingTemiAsr = false;
    private String activeConversationId = "conv-" + UUID.randomUUID();
    private final ProcessCommandRegistry commandRegistry = new ProcessCommandRegistry(1024);
    private final ArrayDeque<CanonicalCommand> canonicalCommandQueue = new ArrayDeque<>();
    private final CanonicalTtsTracker canonicalTtsTracker = new CanonicalTtsTracker();
    private final CanonicalMediaTracker canonicalMediaTracker = new CanonicalMediaTracker();
    private PendingCanonicalCommand activeCanonicalCommand;
    private boolean resumeListeningAfterCanonicalQueue;

    // ─── UI ───────────────────────────────────────────────────────────
    private PreviewView viewFinder;
    private TextView statusText;
    private TextView agentStateText;
    private TextView mqttStatusText;
    private TextView subtitleText;
    private UUID activeSubtitleTtsId;
    private FrameLayout mediaContainer;
    private VideoView exerciseVideoView;
    private TextView mediaTitleText;
    private Button mediaStopButton;

    // ═══════════════════════════════════════════════════════════════════
    //  Lifecycle
    // ═══════════════════════════════════════════════════════════════════

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // Bind UI
        viewFinder = findViewById(R.id.viewFinder);
        statusText = findViewById(R.id.statusText);
        agentStateText = findViewById(R.id.agentStateText);
        mqttStatusText = findViewById(R.id.mqttStatusText);
        subtitleText = findViewById(R.id.subtitleText);
        mediaContainer = findViewById(R.id.mediaContainer);
        exerciseVideoView = findViewById(R.id.exerciseVideoView);
        mediaTitleText = findViewById(R.id.mediaTitleText);
        mediaStopButton = findViewById(R.id.mediaStopButton);
        mediaStopButton.setOnClickListener(v -> cancelCanonicalMedia("user_cancelled"));

        // Initialize State Machine
        stateMachine = new AgentStateMachine(this);

        // Global Interrupt mechanism on screen touch
        View rootView = findViewById(android.R.id.content);
        rootView.setOnClickListener(v -> {
            if (stateMachine.getCurrentState() != AgentStateMachine.State.IDLE) {
                stateMachine.interrupt();
            }
        });

        // Initialize Robot SDK
        robot = Robot.getInstance();

        // Initialize WebSocket clients (Multicast)
        String[] wsUrls = BuildConfig.WS_SERVER_URLS.split(",");
        for (String url : wsUrls) {
            String cleanUrl = url.trim();
            if (!cleanUrl.isEmpty()) {
                webSocketClients.add(new WebSocketClient(cleanUrl));
            }
        }

        // Initialize Camera with multicast callback → WebSockets
        cameraManager = createCameraManager();

        // Initialize MQTT clients (Multicast)
        String[] mqttUrls = BuildConfig.MQTT_BROKER_URLS.split(",");
        for (int i = 0; i < mqttUrls.length; i++) {
            String cleanUrl = mqttUrls[i].trim();
            if (!cleanUrl.isEmpty()) {
                MqttManager mm = new MqttManager(cleanUrl, BuildConfig.MQTT_CLIENT_ID + "-" + i);
                mm.setMessageListener(this);
                mm.setConnectionListener(this);
                mqttManagers.add(mm);
            }
        }

        updateStatus("Initialized. Waiting for Robot...");
    }

    @Override
    protected void onStart() {
        super.onStart();
        robot.addOnRobotReadyListener(this);
        robot.addAsrListener(this);
        robot.addNlpListener(this);
        robot.addWakeupWordListener(this);
        robot.addTtsListener(this);
        ActivityInfo activityInfo = getActivityInfo();
        if (activityInfo != null) {
            robot.onStart(activityInfo);
        }
    }

    @Override
    protected void onStop() {
        super.onStop();
        cancelCanonicalMedia("activity_stopped");
        hotwordEnabled = false;
        mainHandler.removeCallbacksAndMessages(null);
        stopHotwordListening();
        destroyHotwordRecognizer();
        robot.removeOnRobotReadyListener(this);
        robot.removeAsrListener(this);
        robot.removeNlpListener(this);
        robot.removeWakeupWordListener(this);
        robot.removeTtsListener(this);
        
        for (WebSocketClient wsc : webSocketClients) {
            if (wsc != null) wsc.disconnect();
        }
        if (cameraManager != null) cameraManager.shutdown();
        cameraManager = null;
        
        for (MqttManager mm : mqttManagers) {
            if (mm != null) mm.disconnect();
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    //  Robot SDK Callback
    // ═══════════════════════════════════════════════════════════════════

    @Override
    public void onRobotReady(boolean isReady) {
        if (isReady) {
            Log.i(TAG, "Temi Robot is ready.");
            runOnUiThread(() -> {
                if (checkPermissions()) {
                    startAllServices();
                } else {
                    requestPermissions();
                }
            });
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    //  MQTT Callbacks
    // ═══════════════════════════════════════════════════════════════════

    @Override
    public void onConnected() {
        Log.i(TAG, "MQTT connected to one of the brokers.");
        // UI updates are handled in delayed status check
    }

    @Override
    public void onDisconnected(String reason) {
        Log.w(TAG, "MQTT disconnected: " + reason);
    }

    @Override
    public void onMessage(@NonNull String topic, @NonNull String payload) {
        Log.i(TAG, "MQTT [" + topic + "]: " + payload);
        if (MqttTopics.COMMAND_REQUEST.equals(topic)) {
            handleCommandRequest(payload);
            return;
        }
        try {
            JSONObject json = new JSONObject(payload);
            switch (topic) {
                case MqttTopics.ACTION_SPEAK:
                    handleSpeakAction(json);
                    break;
                case MqttTopics.ACTION_NAVIGATE:
                    handleNavigateAction(json);
                    break;
                case MqttTopics.ACTION_WAKEUP:
                    handleWakeupAction(json);
                    break;
                default:
                    Log.w(TAG, "Unhandled topic: " + topic);
            }
        } catch (JSONException e) {
            Log.e(TAG, "Invalid JSON on topic " + topic, e);
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    //  State Machine Callbacks & TTS
    // ═══════════════════════════════════════════════════════════════════

    @Override
    public void onStateChanged(AgentStateMachine.State oldState, AgentStateMachine.State newState) {
        updateAgentState(newState.name());
        if (newState == AgentStateMachine.State.IDLE) {
            startHotwordListening();
        } else {
            stopHotwordListening();
        }
        
        if (newState == AgentStateMachine.State.THINKING) {
            // Non-blocking transition feedback
            TtsRequest.Language ttsLang = mapTtsLanguage("ZH_TW");
            speakWithoutConversationLayer("讓我看一下", ttsLang);
            
            // Immediately transition to WAITING to start the Watchdog
            stateMachine.transitionTo(AgentStateMachine.State.WAITING);
        }
    }

    @Override
    public void onInterrupt() {
        Log.w(TAG, "Executing Global Interrupt: Stopping all actions.");
        cancelCanonicalMedia("interrupted");
        robot.cancelAllTtsRequests();
        robot.stopMovement();
        hideSubtitle();
    }

    @Override
    public void onTimeout() {
        Log.w(TAG, "Watchdog timeout! Returning to IDLE.");
        TtsRequest.Language ttsLang = mapTtsLanguage("ZH_TW");
        speakWithoutConversationLayer("連線逾時，請稍後再試", ttsLang);
    }

    @Override
    public void onTtsStatusChanged(@NonNull TtsRequest ttsRequest) {
        if (ttsRequest.getStatus() == TtsRequest.Status.COMPLETED ||
            ttsRequest.getStatus() == TtsRequest.Status.ERROR) {
            hideSubtitleForRequest(ttsRequest);

            CanonicalTtsTracker.Resolution resolution = canonicalTtsTracker.resolve(
                    ttsRequest.getId(),
                    ttsRequest.getStatus() == TtsRequest.Status.COMPLETED);
            if (resolution != null) {
                runOnUiThread(() -> completeCanonicalTtsAction(resolution));
                return;
            }
            if (activeCanonicalCommand != null) {
                Log.i(TAG, "Ignoring unrelated terminal TTS callback during canonical execution");
                return;
            }
        }

        if (stateMachine.getCurrentState() == AgentStateMachine.State.EXECUTING) {
            if (ttsRequest.getStatus() == TtsRequest.Status.COMPLETED ||
                ttsRequest.getStatus() == TtsRequest.Status.ERROR) {
        if (shouldContinueListening) {
                    stateMachine.transitionTo(AgentStateMachine.State.WAKEUP_TRIGGERED);
                    stateMachine.transitionTo(AgentStateMachine.State.ASR_LISTENING);
                    wakeupWithoutBuiltInResponse();
                } else {
                    stateMachine.transitionTo(AgentStateMachine.State.IDLE);
                }
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    //  Action Handlers
    // ═══════════════════════════════════════════════════════════════════

    private void handleSpeakAction(JSONObject json) throws JSONException {
        stateMachine.transitionTo(AgentStateMachine.State.EXECUTING);
        
        String text = json.getString("text");
        String language = json.optString("language", "ZH_TW");
        shouldContinueListening = json.optBoolean("continue_listening", false);

        Log.i(TAG, "ACTION_SPEAK: \"" + text + "\" (lang=" + language
                + ", continue=" + shouldContinueListening + ")");

        TtsRequest.Language ttsLang = mapTtsLanguage(language);
        suppressLauncherConversation();
        speakWithoutConversationLayer(text, ttsLang);
    }

    private void handleNavigateAction(JSONObject json) throws JSONException {
        stateMachine.transitionTo(AgentStateMachine.State.EXECUTING);
        
        String target = json.optString("target", json.optString("target_location", ""));
        if (target.trim().isEmpty()) {
            throw new JSONException("Missing navigation target");
        }
        Log.i(TAG, "ACTION_NAVIGATE: " + target);
        robot.goTo(target);
        
        // Navigation doesn't trigger TTS completion usually, so we manually go to IDLE
        stateMachine.transitionTo(AgentStateMachine.State.IDLE);
    }

    private void handleWakeupAction(JSONObject json) {
        Log.i(TAG, "ACTION_WAKEUP");
        stateMachine.transitionTo(AgentStateMachine.State.WAKEUP_TRIGGERED);
        stateMachine.transitionTo(AgentStateMachine.State.ASR_LISTENING);
        wakeupWithoutBuiltInResponse();
    }

    private void handleCommandRequest(String payload) {
        final CanonicalCommand command;
        try {
            command = CanonicalCommandValidator.validate(payload, MqttTopics.ROBOT_ID);
        } catch (CanonicalCommandValidator.ValidationException e) {
            Log.e(TAG, "Rejected canonical command: " + e.getReason());
            if (e.hasCorrelation()) {
                JSONArray results = new JSONArray();
                if (e.getActionId() != null || e.getActionType() != null) {
                    results.put(createActionResult(
                            e.getActionId(), e.getActionType(), "failed", e.getReason()));
                }
                publishRawCommandResult(buildCommandResultPayload(
                        e.getCommandId(), e.getEventId(), "failed", results, e.getReason()));
            } else {
                Log.e(TAG, "Cannot publish failure result without command_id and event_id correlation");
            }
            return;
        }

        ProcessCommandRegistry.BeginResult beginResult =
                commandRegistry.begin(command.getCommandId());
        switch (beginResult.getState()) {
            case DUPLICATE_COMPLETE:
                Log.i(TAG, "Duplicate completed command; replaying cached result: "
                        + command.getCommandId());
                publishRawCommandResult(beginResult.getResultPayload());
                return;
            case DUPLICATE_PENDING:
                Log.i(TAG, "Duplicate pending command; execution suppressed and final result queued: "
                        + command.getCommandId());
                return;
            case CAPACITY_REJECTED:
                Log.e(TAG, "Canonical command registry capacity exhausted; rejecting command: "
                        + command.getCommandId());
                publishRawCommandResult(buildCommandResultPayload(
                        command.getCommandId(), command.getEventId(), "failed",
                        new JSONArray(), "command_registry_capacity_exhausted"));
                return;
            case FIRST_DELIVERY:
            default:
                Log.i(TAG, "COMMAND_REQUEST: " + command.getCommandId()
                        + " actions=" + command.getActions().size());
                runOnUiThread(() -> {
                    canonicalCommandQueue.add(command);
                    startNextCanonicalCommand();
                });
        }
    }

    private void startNextCanonicalCommand() {
        if (activeCanonicalCommand != null) {
            return;
        }
        CanonicalCommand command = canonicalCommandQueue.poll();
        if (command == null) {
            return;
        }
        activeCanonicalCommand = new PendingCanonicalCommand(command);
        stateMachine.transitionTo(AgentStateMachine.State.EXECUTING);
        executeNextCanonicalAction();
    }

    private void executeNextCanonicalAction() {
        while (activeCanonicalCommand != null
                && activeCanonicalCommand.nextActionIndex
                < activeCanonicalCommand.command.getActions().size()) {
            CanonicalAction action = activeCanonicalCommand.command.getActions().get(
                    activeCanonicalCommand.nextActionIndex);
            if ("speak".equals(action.getType())
                    || "ask_clarification".equals(action.getType())) {
                startCanonicalSpeech(action);
                return;
            }
            if ("play_media".equals(action.getType())) {
                startCanonicalMedia(action);
                return;
            }

            JSONObject result = executeImmediateCanonicalAction(action);
            activeCanonicalCommand.recordResult(result);
            activeCanonicalCommand.nextActionIndex++;
        }

        if (activeCanonicalCommand != null) {
            finishCanonicalCommand();
        }
    }

    private void startCanonicalSpeech(CanonicalAction action) {
        try {
            suppressLauncherConversation();
            TtsRequest request = TtsRequest.create(
                    action.getText(), false, mapTtsLanguage(action.getLanguage()));
            activeCanonicalCommand.continueListeningAfterCompletion |=
                    action.shouldContinueListening();
            activeCanonicalCommand.pendingSpeechAction = action;
            canonicalTtsTracker.begin(request.getId());
            showSubtitle(action.getText(), request.getId());
            Log.i(TAG, "CANONICAL_TTS_DISPATCH: " + action.getActionId());
            robot.speak(request);
        } catch (Exception e) {
            Log.e(TAG, "Failed to dispatch canonical TTS", e);
            canonicalTtsTracker.clear();
            activeCanonicalCommand.recordResult(createActionResult(
                    action.getActionId(), action.getType(), "failed", safeError(e)));
            activeCanonicalCommand.pendingSpeechAction = null;
            activeCanonicalCommand.nextActionIndex++;
            executeNextCanonicalAction();
        }
    }

    private void completeCanonicalTtsAction(CanonicalTtsTracker.Resolution resolution) {
        if (activeCanonicalCommand == null
                || activeCanonicalCommand.pendingSpeechAction == null) {
            Log.e(TAG, "Canonical TTS resolved without an active speech action");
            return;
        }
        CanonicalAction action = activeCanonicalCommand.pendingSpeechAction;
        activeCanonicalCommand.recordResult(createActionResult(
                action.getActionId(), action.getType(),
                resolution.getStatus(), resolution.getError()));
        activeCanonicalCommand.pendingSpeechAction = null;
        activeCanonicalCommand.nextActionIndex++;
        executeNextCanonicalAction();
    }

    private void startCanonicalMedia(CanonicalAction action) {
        String token = UUID.randomUUID().toString();
        try {
            int resourceId = mediaResourceId(action.getMediaId());
            activeCanonicalCommand.pendingMediaAction = action;
            activeCanonicalCommand.pendingMediaToken = token;
            canonicalMediaTracker.begin(token, action.getMediaId());

            mediaTitleText.setText(mediaTitleResourceId(action.getMediaId()));
            mediaContainer.setVisibility(View.VISIBLE);
            exerciseVideoView.setOnPreparedListener(player -> {
                if (!canonicalMediaTracker.markStarted(token)) {
                    return;
                }
                try {
                    player.setLooping(false);
                    exerciseVideoView.start();
                    Log.i(TAG, "CANONICAL_MEDIA_STARTED: " + action.getActionId()
                            + " media_id=" + action.getMediaId());
                } catch (Exception e) {
                    CanonicalMediaTracker.Resolution resolution =
                            canonicalMediaTracker.fail(token, safeError(e));
                    if (resolution != null) {
                        Log.e(TAG, "CANONICAL_MEDIA_FAILED_TO_START: "
                                + action.getActionId(), e);
                        completeCanonicalMediaAction(resolution);
                    }
                }
            });
            exerciseVideoView.setOnCompletionListener(player -> {
                CanonicalMediaTracker.Resolution resolution =
                        canonicalMediaTracker.complete(token);
                if (resolution != null) {
                    Log.i(TAG, "CANONICAL_MEDIA_COMPLETED: " + action.getActionId()
                            + " media_id=" + action.getMediaId());
                    completeCanonicalMediaAction(resolution);
                }
            });
            exerciseVideoView.setOnErrorListener((player, what, extra) -> {
                CanonicalMediaTracker.Resolution resolution = canonicalMediaTracker.fail(
                        token, "media_playback_error_" + what + "_" + extra);
                if (resolution != null) {
                    Log.e(TAG, "CANONICAL_MEDIA_FAILED: " + action.getActionId()
                            + " media_id=" + action.getMediaId()
                            + " what=" + what + " extra=" + extra);
                    completeCanonicalMediaAction(resolution);
                }
                return true;
            });
            Log.i(TAG, "CANONICAL_MEDIA_RECEIVED: " + action.getActionId()
                    + " media_id=" + action.getMediaId());
            Uri uri = Uri.parse("android.resource://" + getPackageName() + "/" + resourceId);
            exerciseVideoView.setVideoURI(uri);
            exerciseVideoView.requestFocus();
        } catch (Exception e) {
            Log.e(TAG, "Failed to prepare canonical media", e);
            CanonicalMediaTracker.Resolution resolution =
                    canonicalMediaTracker.fail(token, safeError(e));
            if (resolution != null) {
                completeCanonicalMediaAction(resolution);
            } else {
                activeCanonicalCommand.recordResult(createMediaActionResult(
                        action, "failed", safeError(e)));
                activeCanonicalCommand.pendingMediaAction = null;
                activeCanonicalCommand.pendingMediaToken = null;
                activeCanonicalCommand.nextActionIndex++;
                executeNextCanonicalAction();
            }
        }
    }

    private void cancelCanonicalMedia(String reason) {
        if (activeCanonicalCommand == null
                || activeCanonicalCommand.pendingMediaAction == null
                || activeCanonicalCommand.pendingMediaToken == null) {
            return;
        }
        CanonicalAction action = activeCanonicalCommand.pendingMediaAction;
        CanonicalMediaTracker.Resolution resolution = canonicalMediaTracker.cancel(
                activeCanonicalCommand.pendingMediaToken, reason);
        if (resolution == null) {
            return;
        }
        Log.i(TAG, "CANONICAL_MEDIA_CANCELLED: " + action.getActionId()
                + " media_id=" + action.getMediaId() + " reason=" + reason);
        completeCanonicalMediaAction(resolution);
    }

    private void completeCanonicalMediaAction(CanonicalMediaTracker.Resolution resolution) {
        if (activeCanonicalCommand == null
                || activeCanonicalCommand.pendingMediaAction == null) {
            Log.e(TAG, "Canonical media resolved without an active media action");
            clearMediaPlaybackUi();
            return;
        }
        CanonicalAction action = activeCanonicalCommand.pendingMediaAction;
        clearMediaPlaybackUi();
        activeCanonicalCommand.recordResult(createMediaActionResult(
                action, resolution.getStatus(), resolution.getError()));
        activeCanonicalCommand.pendingMediaAction = null;
        activeCanonicalCommand.pendingMediaToken = null;
        activeCanonicalCommand.nextActionIndex++;
        executeNextCanonicalAction();
    }

    private JSONObject createMediaActionResult(
            CanonicalAction action, String status, String error) {
        JSONObject result = createActionResult(
                action.getActionId(), action.getType(), status, error);
        try {
            result.put("media_id", action.getMediaId());
        } catch (JSONException e) {
            Log.e(TAG, "Failed to attach media_id to action result", e);
        }
        return result;
    }

    private int mediaResourceId(String mediaId) {
        switch (mediaId) {
            case "elderly_hand_exercise":
                return R.raw.elderly_hand_exercise;
            case "elderly_leg_exercise":
                return R.raw.elderly_leg_exercise;
            default:
                throw new IllegalArgumentException("Unsupported media_id: " + mediaId);
        }
    }

    private int mediaTitleResourceId(String mediaId) {
        return "elderly_hand_exercise".equals(mediaId)
                ? R.string.hand_exercise_title : R.string.leg_exercise_title;
    }

    private void clearMediaPlaybackUi() {
        exerciseVideoView.setOnPreparedListener(null);
        exerciseVideoView.setOnCompletionListener(null);
        exerciseVideoView.setOnErrorListener(null);
        exerciseVideoView.stopPlayback();
        mediaContainer.setVisibility(View.GONE);
        mediaTitleText.setText(null);
    }

    private JSONObject executeImmediateCanonicalAction(CanonicalAction action) {
        try {
            switch (action.getType()) {
                case "navigate":
                    Log.i(TAG, "ACTION_NAVIGATE_DISPATCH: " + action.getTarget());
                    robot.goTo(action.getTarget());
                    return createActionResult(
                            action.getActionId(), action.getType(), "dispatched", null);
                case "turn":
                    int signedDegrees = "left".equals(action.getDirection())
                            ? action.getDegrees() : -action.getDegrees();
                    Log.i(TAG, "ACTION_TURN_DISPATCH: " + action.getDirection()
                            + " " + action.getDegrees());
                    robot.turnBy(signedDegrees, 0.6f);
                    return createActionResult(
                            action.getActionId(), action.getType(), "dispatched", null);
                case "stop":
                    Log.i(TAG, "ACTION_STOP");
                    robot.cancelAllTtsRequests();
                    robot.stopMovement();
                    hideSubtitle();
                    return createActionResult(
                            action.getActionId(), action.getType(), "completed", null);
                case "noop":
                    Log.i(TAG, "ACTION_NOOP: " + action.getReason());
                    return createActionResult(
                            action.getActionId(), action.getType(), "completed", null);
                default:
                    throw new IllegalStateException(
                            "Unexpected validated action type: " + action.getType());
            }
        } catch (Exception e) {
            Log.e(TAG, "Failed to execute canonical action " + action.getActionId(), e);
            return createActionResult(
                    action.getActionId(), action.getType(), "failed", safeError(e));
        }
    }

    private void handleTurnAction(JSONObject json) throws JSONException {
        stateMachine.transitionTo(AgentStateMachine.State.EXECUTING);
        String direction = json.getString("direction");
        int degrees = json.getInt("degrees");
        int signedDegrees = "left".equals(direction) ? degrees : -degrees;
        Log.i(TAG, "ACTION_TURN: " + direction + " " + degrees);
        robot.turnBy(signedDegrees, 0.6f);
        stateMachine.transitionTo(AgentStateMachine.State.IDLE);
    }

    private void handleStopAction() {
        Log.i(TAG, "ACTION_STOP");
        robot.cancelAllTtsRequests();
        robot.stopMovement();
        hideSubtitle();
        stateMachine.transitionTo(AgentStateMachine.State.IDLE);
    }

    private String buildCommandResultPayload(
            String commandId,
            String eventId,
            String status,
            JSONArray actionResults,
            String error
    ) {
        try {
            JSONObject result = new JSONObject();
            result.put("schema_version", "1.0");
            result.put("command_id", commandId);
            result.put("event_id", eventId);
            result.put("robot_id", MqttTopics.ROBOT_ID);
            result.put("status", status);
            result.put("finished_at_ms", System.currentTimeMillis());
            result.put("results", actionResults);
            if (error != null) {
                result.put("error", error);
            }
            return result.toString();
        } catch (JSONException e) {
            Log.e(TAG, "Failed to build command result", e);
            return null;
        }
    }

    private JSONObject createActionResult(
            String actionId, String type, String status, String error) {
        JSONObject result = new JSONObject();
        try {
            result.put("action_id", actionId == null ? "unknown_action" : actionId);
            result.put("type", type == null ? "unknown" : type);
            result.put("status", status);
            if (error != null) {
                result.put("error", error);
            }
        } catch (JSONException e) {
            Log.e(TAG, "Failed to build action result", e);
        }
        return result;
    }

    private void finishCanonicalCommand() {
        PendingCanonicalCommand completed = activeCanonicalCommand;
        int actionCount = completed.command.getActions().size();
        String status;
        if (completed.cancelledCount == actionCount) {
            status = "cancelled";
        } else if (completed.failedCount == actionCount) {
            status = "failed";
        } else if (completed.failedCount > 0 || completed.cancelledCount > 0) {
            status = "partial_success";
        } else {
            status = "success";
        }
        String payload = buildCommandResultPayload(
                completed.command.getCommandId(),
                completed.command.getEventId(),
                status,
                completed.results,
                null);
        if (payload != null) {
            int pendingReplays = commandRegistry.complete(
                    completed.command.getCommandId(), payload);
            publishRawCommandResult(payload);
            for (int i = 0; i < pendingReplays; i++) {
                publishRawCommandResult(payload);
            }
        }

        activeCanonicalCommand = null;
        resumeListeningAfterCanonicalQueue |= completed.continueListeningAfterCompletion;
        if (!canonicalCommandQueue.isEmpty()) {
            startNextCanonicalCommand();
            return;
        }
        if (resumeListeningAfterCanonicalQueue) {
            resumeListeningAfterCanonicalQueue = false;
            stateMachine.transitionTo(AgentStateMachine.State.WAKEUP_TRIGGERED);
            stateMachine.transitionTo(AgentStateMachine.State.ASR_LISTENING);
            wakeupWithoutBuiltInResponse();
        } else if (stateMachine.getCurrentState() != AgentStateMachine.State.IDLE) {
            stateMachine.transitionTo(AgentStateMachine.State.IDLE);
        }
    }

    private void publishRawCommandResult(String payload) {
        if (payload == null) {
            return;
        }
        for (MqttManager mm : mqttManagers) {
            if (mm != null && mm.isConnected()) {
                mm.publish(MqttTopics.COMMAND_RESULT, payload);
            }
        }
    }

    private String safeError(Exception e) {
        return e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
    }

    private static final class PendingCanonicalCommand {
        private final CanonicalCommand command;
        private final JSONArray results = new JSONArray();
        private int nextActionIndex;
        private int failedCount;
        private int cancelledCount;
        private CanonicalAction pendingSpeechAction;
        private CanonicalAction pendingMediaAction;
        private String pendingMediaToken;
        private boolean continueListeningAfterCompletion;

        private PendingCanonicalCommand(CanonicalCommand command) {
            this.command = command;
        }

        private void recordResult(JSONObject result) {
            results.put(result);
            if ("failed".equals(result.optString("status"))) {
                failedCount++;
            } else if ("cancelled".equals(result.optString("status"))) {
                cancelledCount++;
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    //  Voice & ASR Callbacks
    // ═══════════════════════════════════════════════════════════════════

    @Override
    public void onWakeupWord(@NonNull String wakeupWord, int direction) {
        long wakeupTimeMs = System.currentTimeMillis();
        if (acceptingTemiAsr) {
            Log.i(TAG, "Temi ASR wakeup accepted: " + wakeupWord
                    + " dir=" + direction + " time=" + wakeupTimeMs);
            return;
        }
        Log.i(TAG, "Ignoring Temi system wake word: " + wakeupWord
                + " dir=" + direction + " time=" + wakeupTimeMs);
        suppressLauncherConversation();
    }

    @Override
    public void onAsrResult(@NonNull String text, @NonNull SttLanguage sttLanguage) {
        long asrCompleteTimeMs = System.currentTimeMillis();
        Log.i(TAG, "onAsrResult: '" + text + "' (lang=" + sttLanguage + ") time=" + asrCompleteTimeMs);

        if (!acceptingTemiAsr) {
            Log.i(TAG, "Ignoring ASR because it was not requested by custom wake word.");
            suppressLauncherConversation();
            stateMachine.transitionTo(AgentStateMachine.State.IDLE);
            return;
        }
        acceptingTemiAsr = false;

        if (text.isEmpty()) {
            stateMachine.transitionTo(AgentStateMachine.State.IDLE);
            return;
        }

        suppressLauncherConversation();

        try {
            JSONObject json = new JSONObject();
            String eventId = "evt_" + asrCompleteTimeMs + "_" + UUID.randomUUID().toString().substring(0, 8);
            json.put("schema_version", "1.0");
            json.put("event_id", eventId);
            json.put("robot_id", MqttTopics.ROBOT_ID);
            json.put("conversation_id", activeConversationId);
            json.put("type", "asr.legacy_text");
            json.put("text", text);
            json.put("language", sttLanguage.name());
            json.put("timestamp_ms", asrCompleteTimeMs);
            
            // Multicast: Publish ASR to ALL connected MQTT brokers
            for (MqttManager mm : mqttManagers) {
                if (mm != null && mm.isConnected()) {
                    mm.publish(MqttTopics.EVENT_ASR_LEGACY, json.toString());
                }
            }
            
            stateMachine.transitionTo(AgentStateMachine.State.THINKING);
        } catch (JSONException e) {
            Log.e(TAG, "Failed to create ASR JSON", e);
            stateMachine.transitionTo(AgentStateMachine.State.IDLE);
        }
    }

    @Override
    public void onNlpCompleted(@NonNull NlpResult nlpResult) {
        Log.i(TAG, "Ignoring Temi default NLU result: " + nlpResult);
        robot.finishConversation();
    }

    // ═══════════════════════════════════════════════════════════════════
    //  Service Initialization
    // ═══════════════════════════════════════════════════════════════════

    private void startAllServices() {
        updateStatus("Starting services...");
        configureTemiVoiceOwnership();
        initHotwordRecognizer();

        // 1. Start all MQTT clients
        for (MqttManager mm : mqttManagers) {
            mm.connect();
        }

        // 2. Start all WebSocket clients + Camera
        for (WebSocketClient wsc : webSocketClients) {
            wsc.connect();
        }
        if (cameraManager == null) {
            cameraManager = createCameraManager();
        }
        cameraManager.startCamera(this, this, viewFinder);

        // 3. Delayed status check
        new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(() -> {
            int wsConnected = 0;
            for (WebSocketClient wsc : webSocketClients) {
                if (wsc != null && wsc.isConnected()) wsConnected++;
            }
            
            int mqttConnected = 0;
            for (MqttManager mm : mqttManagers) {
                if (mm != null && mm.isConnected()) mqttConnected++;
            }
            
            String wsStatus = "WS: " + wsConnected + "/" + webSocketClients.size();
            String mqttStatus = "MQTT: " + mqttConnected + "/" + mqttManagers.size();
            
            updateStatus(wsStatus + " | " + mqttStatus);
            
            final int finalMqttConnected = mqttConnected;
            runOnUiThread(() -> {
                mqttStatusText.setText(mqttStatus);
                mqttStatusText.setTextColor(finalMqttConnected > 0 ? 0xFF00FF00 : 0xFFFF6666);
            });
            
            stateMachine.transitionTo(AgentStateMachine.State.IDLE);
            startHotwordListening();
        }, 3000);

        speakWithoutConversationLayer("系統就緒", TtsRequest.Language.ZH_TW);
    }

    // ═══════════════════════════════════════════════════════════════════
    //  Permissions
    // ═══════════════════════════════════════════════════════════════════

    private boolean checkPermissions() {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED
                && ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                == PackageManager.PERMISSION_GRANTED;
    }

    private void requestPermissions() {
        ActivityCompat.requestPermissions(this,
                new String[]{Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO},
                PERMISSION_REQUEST_CODE);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode,
                                           @NonNull String[] permissions,
                                           @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == PERMISSION_REQUEST_CODE) {
            if (allPermissionsGranted(grantResults)) {
                startAllServices();
            } else {
                Toast.makeText(this, "Camera and microphone permissions are required.", Toast.LENGTH_LONG).show();
                updateStatus("Permission Denied");
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    //  Helpers
    // ═══════════════════════════════════════════════════════════════════

    private ActivityInfo getActivityInfo() {
        try {
            return getPackageManager().getActivityInfo(
                    getComponentName(), PackageManager.GET_META_DATA);
        } catch (PackageManager.NameNotFoundException e) {
            Log.e(TAG, "Failed to retrieve ActivityInfo", e);
            return null;
        }
    }

    private CameraManager createCameraManager() {
        return new CameraManager(videoData -> {
            for (WebSocketClient client : webSocketClients) {
                if (client != null && client.isConnected()) {
                    client.sendVideoPacket(videoData);
                }
            }
        });
    }

    private TtsRequest.Language mapTtsLanguage(String lang) {
        String normalized = lang == null ? "ZH_TW" : lang.trim().replace('-', '_').toUpperCase(Locale.ROOT);
        switch (normalized) {
            case "ZH_TW": return TtsRequest.Language.ZH_TW;
            case "ZH_CN": return TtsRequest.Language.ZH_CN;
            case "EN_US": return TtsRequest.Language.EN_US;
            case "JA_JP": return TtsRequest.Language.JA_JP;
            default: return TtsRequest.Language.ZH_TW;
        }
    }

    private void configureTemiVoiceOwnership() {
        try {
            robot.toggleWakeup(true);
            robot.setAsrLanguages(Collections.singletonList(SttLanguage.ZH_TW));
            Log.i(TAG, "Temi built-in wake trigger disabled; custom wake word is " + CUSTOM_WAKE_WORD);
            mainHandler.postDelayed(() ->
                    Log.i(TAG, "Temi wakeup disabled state: " + robot.isWakeupDisabled()), 500);
        } catch (Exception e) {
            Log.w(TAG, "Failed to configure Temi voice ownership", e);
        }
    }

    private void initHotwordRecognizer() {
        if (hotwordRecognizer != null) {
            return;
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            Log.e(TAG, "Android SpeechRecognizer is not available on this device.");
            updateStatus("Hotword unavailable");
            return;
        }

        hotwordIntent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        hotwordIntent.putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        hotwordIntent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-TW");
        hotwordIntent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        hotwordIntent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3);
        hotwordIntent.putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, getPackageName());

        hotwordRecognizer = SpeechRecognizer.createSpeechRecognizer(this);
        hotwordRecognizer.setRecognitionListener(new RecognitionListener() {
            @Override
            public void onReadyForSpeech(Bundle params) {
                hotwordListening = true;
                updateStatus("Waiting for \"" + CUSTOM_WAKE_WORD + "\"");
            }

            @Override
            public void onBeginningOfSpeech() {
            }

            @Override
            public void onRmsChanged(float rmsdB) {
            }

            @Override
            public void onBufferReceived(byte[] buffer) {
            }

            @Override
            public void onEndOfSpeech() {
                hotwordListening = false;
            }

            @Override
            public void onError(int error) {
                hotwordListening = false;
                Log.d(TAG, "Hotword recognizer error: " + error);
                scheduleHotwordRestart();
            }

            @Override
            public void onResults(Bundle results) {
                hotwordListening = false;
                if (containsCustomWakeWord(results)) {
                    triggerCustomWakeWord();
                } else {
                    scheduleHotwordRestart();
                }
            }

            @Override
            public void onPartialResults(Bundle partialResults) {
                if (containsCustomWakeWord(partialResults)) {
                    triggerCustomWakeWord();
                }
            }

            @Override
            public void onEvent(int eventType, Bundle params) {
            }
        });
    }

    private void startHotwordListening() {
        hotwordEnabled = true;
        if (hotwordRecognizer == null) {
            initHotwordRecognizer();
        }
        if (hotwordRecognizer == null || hotwordListening) {
            return;
        }
        if (stateMachine.getCurrentState() != AgentStateMachine.State.IDLE) {
            return;
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            return;
        }

        try {
            hotwordListening = true;
            hotwordRecognizer.startListening(hotwordIntent);
        } catch (Exception e) {
            hotwordListening = false;
            Log.w(TAG, "Failed to start hotword recognizer", e);
            scheduleHotwordRestart();
        }
    }

    private void stopHotwordListening() {
        if (hotwordRecognizer == null) {
            return;
        }
        try {
            hotwordRecognizer.cancel();
        } catch (Exception e) {
            Log.d(TAG, "Failed to cancel hotword recognizer", e);
        }
        hotwordListening = false;
    }

    private void destroyHotwordRecognizer() {
        if (hotwordRecognizer == null) {
            return;
        }
        hotwordRecognizer.destroy();
        hotwordRecognizer = null;
        hotwordIntent = null;
        hotwordListening = false;
    }

    private void scheduleHotwordRestart() {
        mainHandler.postDelayed(() -> {
            if (hotwordEnabled && stateMachine.getCurrentState() == AgentStateMachine.State.IDLE) {
                startHotwordListening();
            }
        }, HOTWORD_RESTART_DELAY_MS);
    }

    private boolean containsCustomWakeWord(Bundle results) {
        if (results == null) {
            return false;
        }
        ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (matches == null) {
            return false;
        }

        for (String match : matches) {
            String normalized = normalizeHotwordText(match);
            for (String variant : CUSTOM_WAKE_WORD_VARIANTS) {
                String normalizedVariant = normalizeHotwordText(variant);
                if (normalized.contains(normalizedVariant)) {
                    Log.i(TAG, "Custom wake word matched from phrase: " + match
                            + " variant=" + variant);
                    return true;
                }
            }
            Log.d(TAG, "Hotword phrase did not match: " + match + " normalized=" + normalized);
        }
        return false;
    }

    private String normalizeHotwordText(String text) {
        if (text == null) {
            return "";
        }
        StringBuilder normalized = new StringBuilder();
        String lower = text.toLowerCase(Locale.ROOT);
        for (int i = 0; i < lower.length(); i++) {
            char ch = lower.charAt(i);
            int type = Character.getType(ch);
            if (!Character.isWhitespace(ch)
                    && !Character.isISOControl(ch)
                    && type != Character.CONNECTOR_PUNCTUATION
                    && type != Character.DASH_PUNCTUATION
                    && type != Character.START_PUNCTUATION
                    && type != Character.END_PUNCTUATION
                    && type != Character.OTHER_PUNCTUATION
                    && type != Character.INITIAL_QUOTE_PUNCTUATION
                    && type != Character.FINAL_QUOTE_PUNCTUATION) {
                normalized.append(ch);
            }
        }
        return normalized.toString();
    }

    private String normalizeSpeech(String text) {
        if (text == null) {
            return "";
        }
        return text
                .toLowerCase(Locale.ROOT)
                .replaceAll("[\\s\\p{Punct}，。！？、；：「」『』（）()]", "");
    }

    private void triggerCustomWakeWord() {
        if (stateMachine.getCurrentState() != AgentStateMachine.State.IDLE) {
            return;
        }
        stopHotwordListening();
        long wakeupTimeMs = System.currentTimeMillis();
        Log.i(TAG, "Custom wake word triggered: " + CUSTOM_WAKE_WORD + " time=" + wakeupTimeMs);
        stateMachine.transitionTo(AgentStateMachine.State.WAKEUP_TRIGGERED);
        stateMachine.transitionTo(AgentStateMachine.State.ASR_LISTENING);
        wakeupWithoutBuiltInResponse();
    }

    private boolean allPermissionsGranted(@NonNull int[] grantResults) {
        if (grantResults.length == 0) {
            return false;
        }
        for (int grantResult : grantResults) {
            if (grantResult != PackageManager.PERMISSION_GRANTED) {
                return false;
            }
        }
        return true;
    }

    private void suppressLauncherConversation() {
        robot.finishConversation();
        robot.cancelAllTtsRequests();
        hideSubtitle();
    }

    private void wakeupWithoutBuiltInResponse() {
        stopHotwordListening();
        acceptingTemiAsr = true;
        robot.wakeup(Collections.singletonList(SttLanguage.ZH_TW));
    }

    private void speakWithoutConversationLayer(String text, TtsRequest.Language language) {
        TtsRequest request = TtsRequest.create(text, false, language);
        showSubtitle(text, request.getId());
        robot.speak(request);
    }

    private void showSubtitle(String text, UUID requestId) {
        if (text == null || text.trim().isEmpty()) {
            hideSubtitle();
            return;
        }
        activeSubtitleTtsId = requestId;
        runOnUiThread(() -> {
            subtitleText.setText(text.trim());
            subtitleText.setVisibility(View.VISIBLE);
        });
    }

    private void hideSubtitleForRequest(@NonNull TtsRequest request) {
        UUID requestId = request.getId();
        if (activeSubtitleTtsId == null || !activeSubtitleTtsId.equals(requestId)) {
            return;
        }
        hideSubtitle();
    }

    private void hideSubtitle() {
        activeSubtitleTtsId = null;
        runOnUiThread(() -> {
            subtitleText.setText("");
            subtitleText.setVisibility(View.GONE);
        });
    }

    private void updateStatus(String text) {
        runOnUiThread(() -> statusText.setText(text));
    }

    private void updateAgentState(String state) {
        runOnUiThread(() -> agentStateText.setText("Agent: " + state));
    }
}
