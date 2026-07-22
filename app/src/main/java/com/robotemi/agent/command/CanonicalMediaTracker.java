package com.robotemi.agent.command;

/**
 * Tracks one serialized canonical media action from receipt through a terminal
 * playback callback without depending on the Android media framework.
 */
public final class CanonicalMediaTracker {
    public enum State { IDLE, RECEIVED, STARTED }

    private String pendingToken;
    private String mediaId;
    private State state = State.IDLE;

    public synchronized void begin(String token, String requestedMediaId) {
        if (state != State.IDLE) {
            throw new IllegalStateException("canonical media is already pending");
        }
        pendingToken = token;
        mediaId = requestedMediaId;
        state = State.RECEIVED;
    }

    public synchronized boolean markStarted(String token) {
        if (!matches(token) || state != State.RECEIVED) {
            return false;
        }
        state = State.STARTED;
        return true;
    }

    /** Completion is accepted only after playback has actually started. */
    public synchronized Resolution complete(String token) {
        if (!matches(token) || state != State.STARTED) {
            return null;
        }
        return finish("completed", null);
    }

    public synchronized Resolution fail(String token, String error) {
        if (!matches(token) || state == State.IDLE) {
            return null;
        }
        return finish("failed", error == null ? "media_playback_error" : error);
    }

    public synchronized Resolution cancel(String token, String reason) {
        if (!matches(token) || state == State.IDLE) {
            return null;
        }
        return finish("cancelled", reason == null ? "media_cancelled" : reason);
    }

    public synchronized boolean isPending() {
        return state != State.IDLE;
    }

    public synchronized State getState() {
        return state;
    }

    private boolean matches(String token) {
        return pendingToken != null && pendingToken.equals(token);
    }

    private Resolution finish(String status, String error) {
        Resolution resolution = new Resolution(mediaId, status, error);
        pendingToken = null;
        mediaId = null;
        state = State.IDLE;
        return resolution;
    }

    public static final class Resolution {
        private final String mediaId;
        private final String status;
        private final String error;

        private Resolution(String mediaId, String status, String error) {
            this.mediaId = mediaId;
            this.status = status;
            this.error = error;
        }

        public String getMediaId() { return mediaId; }
        public String getStatus() { return status; }
        public String getError() { return error; }
    }
}
