package com.robotemi.agent.command;

import java.util.LinkedHashMap;

/** Thread-safe, bounded command-id registry whose contents live for the app process. */
public final class ProcessCommandRegistry {
    private final int capacity;
    private final LinkedHashMap<String, Entry> entries = new LinkedHashMap<>();

    public ProcessCommandRegistry(int capacity) {
        if (capacity < 1) {
            throw new IllegalArgumentException("capacity must be positive");
        }
        this.capacity = capacity;
    }

    public synchronized BeginResult begin(String commandId) {
        Entry existing = entries.get(commandId);
        if (existing != null) {
            if (existing.resultPayload != null) {
                return BeginResult.completedDuplicate(existing.resultPayload);
            }
            existing.pendingReplayCount++;
            return BeginResult.pendingDuplicate();
        }

        if (entries.size() >= capacity) {
            return BeginResult.capacityRejected();
        }
        entries.put(commandId, new Entry());
        return BeginResult.firstDelivery();
    }

    /** Stores the deterministic final payload and returns pending duplicate replay count. */
    public synchronized int complete(String commandId, String resultPayload) {
        Entry entry = entries.get(commandId);
        if (entry == null) {
            throw new IllegalStateException("command_id was not registered");
        }
        entry.resultPayload = resultPayload;
        int replayCount = entry.pendingReplayCount;
        entry.pendingReplayCount = 0;
        return replayCount;
    }

    public synchronized int size() {
        return entries.size();
    }

    private static final class Entry {
        private String resultPayload;
        private int pendingReplayCount;
    }

    public static final class BeginResult {
        public enum State {
            FIRST_DELIVERY,
            DUPLICATE_PENDING,
            DUPLICATE_COMPLETE,
            CAPACITY_REJECTED
        }

        private final State state;
        private final String resultPayload;

        private BeginResult(State state, String resultPayload) {
            this.state = state;
            this.resultPayload = resultPayload;
        }

        private static BeginResult firstDelivery() {
            return new BeginResult(State.FIRST_DELIVERY, null);
        }

        private static BeginResult pendingDuplicate() {
            return new BeginResult(State.DUPLICATE_PENDING, null);
        }

        private static BeginResult completedDuplicate(String resultPayload) {
            return new BeginResult(State.DUPLICATE_COMPLETE, resultPayload);
        }

        private static BeginResult capacityRejected() {
            return new BeginResult(State.CAPACITY_REJECTED, null);
        }

        public State getState() { return state; }
        public String getResultPayload() { return resultPayload; }
    }
}
