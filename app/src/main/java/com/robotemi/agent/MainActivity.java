package com.robotemi.agent;

import android.Manifest;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.camera.view.PreviewView;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.robotemi.agent.camera.CameraManager;
import com.robotemi.agent.mqtt.MqttManager;
import com.robotemi.agent.mqtt.MqttTopics;
import com.robotemi.agent.network.WebSocketClient;
import com.robotemi.sdk.NlpResult;
import com.robotemi.sdk.Robot;
import com.robotemi.sdk.SttLanguage;
import com.robotemi.sdk.TtsRequest;
import com.robotemi.sdk.listeners.OnRobotReadyListener;

import org.json.JSONException;
import org.json.JSONObject;

import com.robotemi.agent.agent.AgentStateMachine;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

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

    // ─── Components ───────────────────────────────────────────────────
    private Robot robot;
    private CameraManager cameraManager;
    private List<WebSocketClient> webSocketClients = new ArrayList<>();
    private List<MqttManager> mqttManagers = new ArrayList<>();
    private AgentStateMachine stateMachine;
    private boolean shouldContinueListening = false;

    // ─── UI ───────────────────────────────────────────────────────────
    private PreviewView viewFinder;
    private TextView statusText;
    private TextView agentStateText;
    private TextView mqttStatusText;

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
        cameraManager = new CameraManager(videoData -> {
            for (WebSocketClient client : webSocketClients) {
                if (client != null && client.isConnected()) {
                    client.sendVideoPacket(videoData);
                }
            }
        });

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
        robot.removeOnRobotReadyListener(this);
        robot.removeAsrListener(this);
        robot.removeNlpListener(this);
        robot.removeWakeupWordListener(this);
        robot.removeTtsListener(this);
        
        for (WebSocketClient wsc : webSocketClients) {
            if (wsc != null) wsc.disconnect();
        }
        if (cameraManager != null) cameraManager.shutdown();
        
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
        robot.cancelAllTtsRequests();
        robot.stopMovement();
    }

    @Override
    public void onTimeout() {
        Log.w(TAG, "Watchdog timeout! Returning to IDLE.");
        TtsRequest.Language ttsLang = mapTtsLanguage("ZH_TW");
        speakWithoutConversationLayer("連線逾時，請稍後再試", ttsLang);
    }

    @Override
    public void onTtsStatusChanged(@NonNull TtsRequest ttsRequest) {
        if (stateMachine.getCurrentState() == AgentStateMachine.State.EXECUTING) {
            if (ttsRequest.getStatus() == TtsRequest.Status.COMPLETED ||
                ttsRequest.getStatus() == TtsRequest.Status.ERROR) {
                if (shouldContinueListening) {
                    stateMachine.transitionTo(AgentStateMachine.State.IDLE);
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
        
        String target = json.getString("target_location");
        Log.i(TAG, "ACTION_NAVIGATE: " + target);
        robot.goTo(target);
        
        // Navigation doesn't trigger TTS completion usually, so we manually go to IDLE
        stateMachine.transitionTo(AgentStateMachine.State.IDLE);
    }

    private void handleWakeupAction(JSONObject json) {
        Log.i(TAG, "ACTION_WAKEUP");
        wakeupWithoutBuiltInResponse();
    }

    // ═══════════════════════════════════════════════════════════════════
    //  Voice & ASR Callbacks
    // ═══════════════════════════════════════════════════════════════════

    @Override
    public void onWakeupWord(@NonNull String wakeupWord, int direction) {
        stateMachine.transitionTo(AgentStateMachine.State.WAKEUP_TRIGGERED);
        
        long wakeupTimeMs = System.currentTimeMillis();
        Log.i(TAG, "onWakeupWord: " + wakeupWord + " dir=" + direction + " time=" + wakeupTimeMs);
        
        stateMachine.transitionTo(AgentStateMachine.State.ASR_LISTENING);
    }

    @Override
    public void onAsrResult(@NonNull String text, @NonNull SttLanguage sttLanguage) {
        long asrCompleteTimeMs = System.currentTimeMillis();
        Log.i(TAG, "onAsrResult: '" + text + "' (lang=" + sttLanguage + ") time=" + asrCompleteTimeMs);

        if (text.isEmpty()) {
            stateMachine.transitionTo(AgentStateMachine.State.IDLE);
            return;
        }

        suppressLauncherConversation();

        try {
            JSONObject json = new JSONObject();
            json.put("text", text);
            json.put("language", sttLanguage.name());
            json.put("timestamp_ms", asrCompleteTimeMs);
            
            // Multicast: Publish ASR to ALL connected MQTT brokers
            for (MqttManager mm : mqttManagers) {
                if (mm != null && mm.isConnected()) {
                    mm.publish(MqttTopics.EVENT_ASR, json.toString());
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

        // 1. Start all MQTT clients
        for (MqttManager mm : mqttManagers) {
            mm.connect();
        }

        // 2. Start all WebSocket clients + Camera
        for (WebSocketClient wsc : webSocketClients) {
            wsc.connect();
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
        }, 3000);

        speakWithoutConversationLayer("系統就緒", TtsRequest.Language.ZH_TW);
    }

    // ═══════════════════════════════════════════════════════════════════
    //  Permissions
    // ═══════════════════════════════════════════════════════════════════

    private boolean checkPermissions() {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED;
    }

    private void requestPermissions() {
        ActivityCompat.requestPermissions(this,
                new String[]{Manifest.permission.CAMERA}, PERMISSION_REQUEST_CODE);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode,
                                           @NonNull String[] permissions,
                                           @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == PERMISSION_REQUEST_CODE) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                startAllServices();
            } else {
                Toast.makeText(this, "Camera permission is required.", Toast.LENGTH_LONG).show();
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

    private TtsRequest.Language mapTtsLanguage(String lang) {
        switch (lang) {
            case "ZH_TW": return TtsRequest.Language.ZH_TW;
            case "ZH_CN": return TtsRequest.Language.ZH_CN;
            case "EN_US": return TtsRequest.Language.EN_US;
            case "JA_JP": return TtsRequest.Language.JA_JP;
            default: return TtsRequest.Language.ZH_TW;
        }
    }

    private void suppressLauncherConversation() {
        robot.finishConversation();
        robot.cancelAllTtsRequests();
    }

    private void wakeupWithoutBuiltInResponse() {
        robot.wakeup(Collections.singletonList(SttLanguage.ZH_TW));
    }

    private void speakWithoutConversationLayer(String text, TtsRequest.Language language) {
        robot.speak(TtsRequest.create(text, false, language));
    }

    private void updateStatus(String text) {
        runOnUiThread(() -> statusText.setText(text));
    }

    private void updateAgentState(String state) {
        runOnUiThread(() -> agentStateText.setText("Agent: " + state));
    }
}
