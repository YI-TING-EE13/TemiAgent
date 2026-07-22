package com.robotemi.agent.command;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

public class CanonicalMediaTrackerTest {
    @Test
    public void playbackDoesNotCompleteBeforeStartedEvent() {
        CanonicalMediaTracker tracker = new CanonicalMediaTracker();
        tracker.begin("token-1", "elderly_hand_exercise");

        assertNull(tracker.complete("token-1"));
        assertTrue(tracker.isPending());
        assertEquals(CanonicalMediaTracker.State.RECEIVED, tracker.getState());
    }

    @Test
    public void playbackCompletionProducesCompletedResult() {
        CanonicalMediaTracker tracker = new CanonicalMediaTracker();
        tracker.begin("token-1", "elderly_hand_exercise");
        assertTrue(tracker.markStarted("token-1"));

        CanonicalMediaTracker.Resolution result = tracker.complete("token-1");

        assertEquals("elderly_hand_exercise", result.getMediaId());
        assertEquals("completed", result.getStatus());
        assertNull(result.getError());
        assertFalse(tracker.isPending());
    }

    @Test
    public void playbackFailureProducesFailedResult() {
        CanonicalMediaTracker tracker = new CanonicalMediaTracker();
        tracker.begin("token-1", "elderly_leg_exercise");

        CanonicalMediaTracker.Resolution result =
                tracker.fail("token-1", "decoder_failed");

        assertEquals("failed", result.getStatus());
        assertEquals("decoder_failed", result.getError());
        assertFalse(tracker.isPending());
    }

    @Test
    public void cancelDoesNotLaterProduceCompletedResult() {
        CanonicalMediaTracker tracker = new CanonicalMediaTracker();
        tracker.begin("token-1", "elderly_leg_exercise");
        tracker.markStarted("token-1");

        CanonicalMediaTracker.Resolution cancelled =
                tracker.cancel("token-1", "user_cancelled");

        assertEquals("cancelled", cancelled.getStatus());
        assertEquals("user_cancelled", cancelled.getError());
        assertNull(tracker.complete("token-1"));
        assertFalse(tracker.isPending());
    }
}
