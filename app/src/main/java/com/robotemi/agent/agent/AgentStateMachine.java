package com.robotemi.agent.agent;

import android.os.Handler;
import android.os.Looper;
import android.util.Log;

/**
 * Manages the lifecycle and state transitions of the Embodied AI agent.
 *
 * <p>The AgentStateMachine guarantees thread-safe transitions between conversational
 * and execution phases. It provides latency masking by ensuring non-blocking transitions
 * and safeguards the system against VLM timeouts via a built-in watchdog timer.</p>
 *
 * <p>Additionally, it implements a global preemption mechanism, allowing human users
 * to override the state machine at any given moment.</p>
 */
public class AgentStateMachine {
    private static final String TAG = "AgentStateMachine";
    
    /** Maximum duration (60 seconds) to wait for the cloud VLM response before timing out. */
    private static final long WAITING_TIMEOUT_MS = 60000L; 

    /**
     * Enumeration of all possible autonomous states of the Agent.
     */
    public enum State {
        /** The agent is inactive and listening passively for the wake word. */
        IDLE,               
        /** The wake word was detected; the system captures the precise timestamp. */
        WAKEUP_TRIGGERED,   
        /** The agent is actively listening to the user's speech command (ASR). */
        ASR_LISTENING,      
        /** ASR concluded. The agent provides non-blocking auditory feedback (e.g., "Let me take a look") and dispatches the MQTT event. */
        THINKING,           
        /** The agent is waiting for the backend VLM's JSON response. The watchdog timer is active. */
        WAITING,            
        /** The agent is executing physical hardware commands (e.g., Speak, Navigate) sent by the VLM. */
        EXECUTING           
    }

    /**
     * Callback interface to notify UI or SDK components of state changes.
     */
    public interface StateChangeListener {
        /**
         * Invoked when the state machine successfully transitions.
         *
         * @param oldState The previous state.
         * @param newState The new current state.
         */
        void onStateChanged(State oldState, State newState);

        /**
         * Invoked when a global interrupt (preemption) is triggered by the user.
         */
        void onInterrupt();

        /**
         * Invoked when the backend fails to respond within {@value #WAITING_TIMEOUT_MS} milliseconds.
         */
        void onTimeout();
    }

    private State currentState = State.IDLE;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final StateChangeListener listener;
    
    // Watchdog timer runnable to catch VLM network failures
    private final Runnable watchdogRunnable = new Runnable() {
        @Override
        public void run() {
            if (currentState == State.WAITING) {
                Log.w(TAG, "Watchdog timeout in WAITING state.");
                // Transition to IDLE internally, then notify UI safely
                State oldState = currentState;
                currentState = State.IDLE;
                if (listener != null) {
                    listener.onTimeout();
                    listener.onStateChanged(oldState, State.IDLE);
                }
            }
        }
    };

    /**
     * Constructs a new AgentStateMachine.
     *
     * @param listener The listener to handle state transition callbacks.
     */
    public AgentStateMachine(StateChangeListener listener) {
        this.listener = listener;
    }

    /**
     * Retrieves the current state in a thread-safe manner.
     *
     * @return The current {@link State}.
     */
    public synchronized State getCurrentState() {
        return currentState;
    }

    /**
     * Attempts to transition the machine to a new state.
     *
     * <p>This method automatically manages the lifecycle of the watchdog timer
     * and guarantees that callbacks are executed on the Main Thread to ensure UI safety.</p>
     *
     * @param newState The targeted state to transition into.
     */
    public synchronized void transitionTo(State newState) {
        if (this.currentState == newState) {
            return;
        }
        
        State oldState = this.currentState;
        this.currentState = newState;
        Log.i(TAG, "State transition: " + oldState + " -> " + newState);

        // Manage watchdog timer based on the new state
        if (newState == State.WAITING) {
            startWatchdog();
        } else {
            cancelWatchdog();
        }

        // Notify listener on the main UI thread to trigger Temi SDK actions safely
        mainHandler.post(() -> {
            if (listener != null) {
                listener.onStateChanged(oldState, newState);
            }
        });
    }

    /**
     * Global interrupt mechanism (Preemption).
     * 
     * <p>Instantly aborts any ongoing action, stops the watchdog timer, 
     * and forces the state machine back to {@link State#IDLE}.</p>
     */
    public synchronized void interrupt() {
        Log.w(TAG, "Global interrupt triggered!");
        cancelWatchdog();
        
        State oldState = this.currentState;
        this.currentState = State.IDLE;
        
        mainHandler.post(() -> {
            if (listener != null) {
                listener.onInterrupt();
                if (oldState != State.IDLE) {
                    listener.onStateChanged(oldState, State.IDLE);
                }
            }
        });
    }

    /**
     * Activates the watchdog timer.
     */
    private void startWatchdog() {
        mainHandler.removeCallbacks(watchdogRunnable);
        mainHandler.postDelayed(watchdogRunnable, WAITING_TIMEOUT_MS);
        Log.i(TAG, "Watchdog started for " + WAITING_TIMEOUT_MS + " ms.");
    }

    /**
     * Deactivates the watchdog timer.
     */
    private void cancelWatchdog() {
        mainHandler.removeCallbacks(watchdogRunnable);
    }
}
