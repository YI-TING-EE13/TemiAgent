package com.robotemi.agent.command;

import org.junit.Test;

import java.util.UUID;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

public class CanonicalTtsTrackerTest {
    @Test
    public void ttsHasNoResultBeforeMatchingTerminalCallback() {
        CanonicalTtsTracker tracker = new CanonicalTtsTracker();
        UUID requestId = UUID.randomUUID();
        tracker.begin(requestId);

        assertTrue(tracker.isPending());
        assertNull(tracker.resolve(UUID.randomUUID(), true));
        assertTrue(tracker.isPending());
    }

    @Test
    public void completedCallbackProducesCompletedResult() {
        CanonicalTtsTracker tracker = new CanonicalTtsTracker();
        UUID requestId = UUID.randomUUID();
        tracker.begin(requestId);

        CanonicalTtsTracker.Resolution result = tracker.resolve(requestId, true);

        assertEquals("completed", result.getStatus());
        assertNull(result.getError());
    }

    @Test
    public void errorCallbackProducesFailedResult() {
        CanonicalTtsTracker tracker = new CanonicalTtsTracker();
        UUID requestId = UUID.randomUUID();
        tracker.begin(requestId);

        CanonicalTtsTracker.Resolution result = tracker.resolve(requestId, false);

        assertEquals("failed", result.getStatus());
        assertEquals("tts_error", result.getError());
    }

    @Test(expected = IllegalStateException.class)
    public void secondConcurrentTtsIsRejected() {
        CanonicalTtsTracker tracker = new CanonicalTtsTracker();
        tracker.begin(UUID.randomUUID());
        tracker.begin(UUID.randomUUID());
    }
}
