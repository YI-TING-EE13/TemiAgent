package com.robotemi.agent.command;

import java.util.UUID;

/** Tracks the single serialized canonical TTS action awaiting a terminal Temi callback. */
public final class CanonicalTtsTracker {
    private UUID pendingRequestId;

    public synchronized void begin(UUID requestId) {
        if (pendingRequestId != null) {
            throw new IllegalStateException("canonical TTS is already pending");
        }
        pendingRequestId = requestId;
    }

    public synchronized boolean isPending() {
        return pendingRequestId != null;
    }

    public synchronized void clear() {
        pendingRequestId = null;
    }

    public synchronized Resolution resolve(UUID requestId, boolean completed) {
        if (pendingRequestId == null || !pendingRequestId.equals(requestId)) {
            return null;
        }
        pendingRequestId = null;
        return new Resolution(completed ? "completed" : "failed",
                completed ? null : "tts_error");
    }

    public static final class Resolution {
        private final String status;
        private final String error;

        private Resolution(String status, String error) {
            this.status = status;
            this.error = error;
        }

        public String getStatus() { return status; }
        public String getError() { return error; }
    }
}
