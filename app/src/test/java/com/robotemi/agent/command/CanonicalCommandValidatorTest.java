package com.robotemi.agent.command;

import com.robotemi.agent.command.CanonicalCommandValidator.CanonicalAction;
import com.robotemi.agent.command.CanonicalCommandValidator.CanonicalCommand;
import com.robotemi.agent.command.CanonicalCommandValidator.ValidationException;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

public class CanonicalCommandValidatorTest {
    private static final String ROBOT_ID = "temi-01";

    @Test
    public void validSpeakCommandIsAccepted() throws Exception {
        CanonicalCommand command = validate(action(
                "{\"action_id\":\"a1\",\"type\":\"speak\",\"text\":\"hello\"}"));

        assertEquals("cmd-1", command.getCommandId());
        assertEquals(1, command.getActions().size());
        assertEquals("hello", command.getActions().get(0).getText());
    }

    @Test
    public void malformedJsonIsRejectedWithoutCorrelation() {
        ValidationException error = expectFailure("{not-json");

        assertEquals("malformed_json", error.getReason());
        assertFalse(error.hasCorrelation());
    }

    @Test
    public void nonObjectCommandIsRejected() {
        assertEquals("command_not_object", expectFailure("[]").getReason());
    }

    @Test
    public void missingActionsIsRejectedWithCorrelation() {
        ValidationException error = expectFailure(
                "{\"schema_version\":\"1.0\",\"command_id\":\"cmd-1\","
                        + "\"event_id\":\"evt-1\",\"robot_id\":\"temi-01\"}");

        assertEquals("missing_actions", error.getReason());
        assertTrue(error.hasCorrelation());
    }

    @Test
    public void actionsMustBeArray() {
        assertEquals("missing_actions", expectFailure(envelope("{}" )).getReason());
    }

    @Test
    public void actionMustBeObject() {
        assertEquals("action_not_object", expectFailure(envelope("[1]")).getReason());
    }

    @Test
    public void unsupportedActionIsRejected() {
        assertEquals("unsupported_action_type", expectFailure(action(
                "{\"action_id\":\"a1\",\"type\":\"dance\"}")).getReason());
    }

    @Test
    public void invalidTurnDirectionIsRejected() {
        assertEquals("invalid_turn_direction", expectFailure(action(
                "{\"action_id\":\"a1\",\"type\":\"turn\","
                        + "\"direction\":\"forward\",\"degrees\":30}")).getReason());
    }

    @Test
    public void invalidTurnDegreesIsRejected() {
        assertEquals("invalid_turn_degrees", expectFailure(action(
                "{\"action_id\":\"a1\",\"type\":\"turn\","
                        + "\"direction\":\"left\",\"degrees\":120}")).getReason());
    }

    @Test
    public void allowedTurnIsAccepted() throws Exception {
        CanonicalAction turn = validate(action(
                "{\"action_id\":\"a1\",\"type\":\"turn\","
                        + "\"direction\":\"right\",\"degrees\":45}"))
                .getActions().get(0);

        assertEquals("right", turn.getDirection());
        assertEquals(45, turn.getDegrees());
    }

    @Test
    public void allowedNavigationTargetIsAccepted() throws Exception {
        CanonicalAction navigate = validate(action(
                "{\"action_id\":\"a1\",\"type\":\"navigate\","
                        + "\"target\":\"meeting_room\"}"))
                .getActions().get(0);

        assertEquals("meeting_room", navigate.getTarget());
    }

    @Test
    public void disallowedNavigationTargetIsRejected() {
        assertEquals("navigation_target_not_allowed", expectFailure(action(
                "{\"action_id\":\"a1\",\"type\":\"navigate\","
                        + "\"target\":\"roof\"}")).getReason());
    }

    @Test
    public void emptySpeakTextIsRejected() {
        assertEquals("missing_action_text", expectFailure(action(
                "{\"action_id\":\"a1\",\"type\":\"speak\",\"text\":\"  \"}"))
                .getReason());
    }

    @Test
    public void missingActionIdIsRejected() {
        assertEquals("missing_action_id", expectFailure(action(
                "{\"type\":\"stop\"}")).getReason());
    }

    @Test
    public void askClarificationDefaultsToContinueListening() throws Exception {
        CanonicalAction ask = validate(action(
                "{\"action_id\":\"a1\",\"type\":\"ask_clarification\","
                        + "\"text\":\"Which room?\"}"))
                .getActions().get(0);

        assertTrue(ask.shouldContinueListening());
    }

    @Test
    public void robotIdMismatchIsRejected() {
        String payload = envelope(
                "[{\"action_id\":\"a1\",\"type\":\"stop\"}]")
                .replace("temi-01", "temi-02");

        assertEquals("robot_id_mismatch", expectFailure(payload).getReason());
    }

    @Test
    public void validHandExerciseMediaIsAccepted() throws Exception {
        CanonicalAction media = validate(action(
                "{\"action_id\":\"a1\",\"type\":\"play_media\","
                        + "\"media_id\":\"elderly_hand_exercise\"}"))
                .getActions().get(0);

        assertEquals("play_media", media.getType());
        assertEquals("elderly_hand_exercise", media.getMediaId());
    }

    @Test
    public void validLegExerciseMediaIsAccepted() throws Exception {
        CanonicalAction media = validate(action(
                "{\"action_id\":\"a1\",\"type\":\"play_media\","
                        + "\"media_id\":\"elderly_leg_exercise\"}"))
                .getActions().get(0);

        assertEquals("elderly_leg_exercise", media.getMediaId());
    }

    @Test
    public void unknownMediaIsRejected() {
        assertEquals("media_id_not_allowed", expectFailure(action(
                "{\"action_id\":\"a1\",\"type\":\"play_media\","
                        + "\"media_id\":\"unknown_video\"}")).getReason());
    }

    @Test
    public void missingMediaIdIsRejected() {
        assertEquals("missing_media_id", expectFailure(action(
                "{\"action_id\":\"a1\",\"type\":\"play_media\"}"))
                .getReason());
    }

    @Test
    public void nonStringMediaIdIsRejected() {
        assertEquals("invalid_media_id", expectFailure(action(
                "{\"action_id\":\"a1\",\"type\":\"play_media\","
                        + "\"media_id\":42}")).getReason());
    }

    @Test
    public void emptyMediaIdIsRejected() {
        assertEquals("invalid_media_id", expectFailure(action(
                "{\"action_id\":\"a1\",\"type\":\"play_media\","
                        + "\"media_id\":\"  \"}")).getReason());
    }

    private CanonicalCommand validate(String payload) throws Exception {
        return CanonicalCommandValidator.validate(payload, ROBOT_ID);
    }

    private ValidationException expectFailure(String payload) {
        try {
            validate(payload);
            fail("Expected validation failure");
            return null;
        } catch (ValidationException e) {
            return e;
        } catch (Exception e) {
            throw new AssertionError(e);
        }
    }

    private String action(String action) {
        return envelope("[" + action + "]");
    }

    private String envelope(String actions) {
        return "{\"schema_version\":\"1.0\",\"command_id\":\"cmd-1\","
                + "\"event_id\":\"evt-1\",\"robot_id\":\"temi-01\","
                + "\"actions\":" + actions + "}";
    }
}
