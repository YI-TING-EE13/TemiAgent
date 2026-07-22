package com.robotemi.agent.command;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import com.google.gson.JsonParser;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Parses and validates canonical command requests before any hardware action runs. */
public final class CanonicalCommandValidator {
    private static final String SUPPORTED_SCHEMA_VERSION = "1.0";
    private static final int MAX_ACTIONS = 5;
    private static final int MAX_SPEECH_LENGTH = 500;
    private static final Set<String> ACTION_TYPES = Collections.unmodifiableSet(
            new HashSet<>(Arrays.asList(
                    "speak", "ask_clarification", "turn", "navigate", "stop", "noop",
                    "play_media")));
    private static final Set<String> TURN_DIRECTIONS = Collections.unmodifiableSet(
            new HashSet<>(Arrays.asList("left", "right")));
    private static final Set<Integer> TURN_DEGREES = Collections.unmodifiableSet(
            new HashSet<>(Arrays.asList(15, 30, 45, 60, 90)));
    private static final Set<String> NAVIGATION_TARGETS = Collections.unmodifiableSet(
            new HashSet<>(Arrays.asList("home_base", "kitchen", "living_room", "meeting_room")));
    private static final Set<String> MEDIA_IDS = Collections.unmodifiableSet(
            new HashSet<>(Arrays.asList("elderly_hand_exercise", "elderly_leg_exercise")));

    private CanonicalCommandValidator() {}

    public static CanonicalCommand validate(String payload, String expectedRobotId)
            throws ValidationException {
        JsonElement root;
        try {
            root = JsonParser.parseString(payload);
        } catch (JsonParseException | IllegalStateException e) {
            throw new ValidationException("malformed_json", null, null, null, null);
        }
        if (!root.isJsonObject()) {
            throw new ValidationException("command_not_object", null, null, null, null);
        }

        JsonObject object = root.getAsJsonObject();
        String commandId = optionalString(object, "command_id");
        String eventId = optionalString(object, "event_id");
        String robotId = optionalString(object, "robot_id");

        requireEquals(object, "schema_version", SUPPORTED_SCHEMA_VERSION,
                "unsupported_schema_version", commandId, eventId);
        requireNonEmpty(commandId, "missing_command_id", commandId, eventId, null, null);
        requireNonEmpty(eventId, "missing_event_id", commandId, eventId, null, null);
        requireNonEmpty(robotId, "missing_robot_id", commandId, eventId, null, null);
        if (!expectedRobotId.equals(robotId)) {
            throw new ValidationException(
                    "robot_id_mismatch", commandId, eventId, null, null);
        }

        JsonElement actionsElement = object.get("actions");
        if (actionsElement == null || !actionsElement.isJsonArray()) {
            throw new ValidationException("missing_actions", commandId, eventId, null, null);
        }
        JsonArray actionsArray = actionsElement.getAsJsonArray();
        if (actionsArray.size() == 0) {
            throw new ValidationException("missing_actions", commandId, eventId, null, null);
        }
        if (actionsArray.size() > MAX_ACTIONS) {
            throw new ValidationException("too_many_actions", commandId, eventId, null, null);
        }

        List<CanonicalAction> actions = new ArrayList<>();
        for (JsonElement element : actionsArray) {
            if (!element.isJsonObject()) {
                throw new ValidationException("action_not_object", commandId, eventId, null, null);
            }
            actions.add(validateAction(element.getAsJsonObject(), commandId, eventId));
        }
        return new CanonicalCommand(commandId, eventId, robotId, actions);
    }

    private static CanonicalAction validateAction(
            JsonObject action, String commandId, String eventId) throws ValidationException {
        String actionId = optionalString(action, "action_id");
        String type = optionalString(action, "type");
        requireNonEmpty(actionId, "missing_action_id", commandId, eventId, actionId, type);
        if (!ACTION_TYPES.contains(type)) {
            throw new ValidationException(
                    "unsupported_action_type", commandId, eventId, actionId, type);
        }

        switch (type) {
            case "speak":
            case "ask_clarification":
                String text = optionalString(action, "text");
                requireNonEmpty(text, "missing_action_text", commandId, eventId, actionId, type);
                if (text.length() > MAX_SPEECH_LENGTH) {
                    throw new ValidationException(
                            "action_text_too_long", commandId, eventId, actionId, type);
                }
                String language = optionalString(action, "language");
                if (action.has("language") && language == null) {
                    throw new ValidationException(
                            "invalid_action_language", commandId, eventId, actionId, type);
                }
                boolean continueListening = "ask_clarification".equals(type);
                if (action.has("continue_listening")) {
                    JsonElement continueElement = action.get("continue_listening");
                    if (!continueElement.isJsonPrimitive()
                            || !continueElement.getAsJsonPrimitive().isBoolean()) {
                        throw new ValidationException(
                                "invalid_continue_listening", commandId, eventId, actionId, type);
                    }
                    continueListening = continueElement.getAsBoolean();
                }
                return CanonicalAction.speech(
                        actionId, type, text, language == null ? "zh-TW" : language,
                        continueListening);
            case "turn":
                String direction = optionalString(action, "direction");
                if (!TURN_DIRECTIONS.contains(direction)) {
                    throw new ValidationException(
                            "invalid_turn_direction", commandId, eventId, actionId, type);
                }
                Integer degrees = optionalInteger(action, "degrees");
                if (degrees == null || !TURN_DEGREES.contains(degrees)) {
                    throw new ValidationException(
                            "invalid_turn_degrees", commandId, eventId, actionId, type);
                }
                return CanonicalAction.turn(actionId, direction, degrees);
            case "navigate":
                String target = optionalString(action, "target");
                if (!NAVIGATION_TARGETS.contains(target)) {
                    throw new ValidationException(
                            "navigation_target_not_allowed", commandId, eventId, actionId, type);
                }
                return CanonicalAction.navigate(actionId, target);
            case "play_media":
                if (!action.has("media_id")) {
                    throw new ValidationException(
                            "missing_media_id", commandId, eventId, actionId, type);
                }
                String mediaId = optionalString(action, "media_id");
                if (mediaId == null || mediaId.isEmpty()) {
                    throw new ValidationException(
                            "invalid_media_id", commandId, eventId, actionId, type);
                }
                if (!MEDIA_IDS.contains(mediaId)) {
                    throw new ValidationException(
                            "media_id_not_allowed", commandId, eventId, actionId, type);
                }
                return CanonicalAction.media(actionId, mediaId);
            case "stop":
                return CanonicalAction.simple(actionId, type, null);
            case "noop":
                String reason = optionalString(action, "reason");
                requireNonEmpty(reason, "missing_noop_reason", commandId, eventId, actionId, type);
                return CanonicalAction.simple(actionId, type, reason);
            default:
                throw new ValidationException(
                        "unsupported_action_type", commandId, eventId, actionId, type);
        }
    }

    private static void requireEquals(
            JsonObject object,
            String name,
            String expected,
            String reason,
            String commandId,
            String eventId
    ) throws ValidationException {
        if (!expected.equals(optionalString(object, name))) {
            throw new ValidationException(reason, commandId, eventId, null, null);
        }
    }

    private static void requireNonEmpty(
            String value,
            String reason,
            String commandId,
            String eventId,
            String actionId,
            String actionType
    ) throws ValidationException {
        if (value == null || value.isEmpty()) {
            throw new ValidationException(reason, commandId, eventId, actionId, actionType);
        }
    }

    private static String optionalString(JsonObject object, String name) {
        JsonElement value = object.get(name);
        if (value == null || !value.isJsonPrimitive() || !value.getAsJsonPrimitive().isString()) {
            return null;
        }
        return value.getAsString().trim();
    }

    private static Integer optionalInteger(JsonObject object, String name) {
        JsonElement value = object.get(name);
        if (value == null || !value.isJsonPrimitive() || !value.getAsJsonPrimitive().isNumber()) {
            return null;
        }
        try {
            double number = value.getAsDouble();
            if (Double.isNaN(number) || Double.isInfinite(number)
                    || number != Math.rint(number)) {
                return null;
            }
            return value.getAsInt();
        } catch (NumberFormatException e) {
            return null;
        }
    }

    public static final class CanonicalCommand {
        private final String commandId;
        private final String eventId;
        private final String robotId;
        private final List<CanonicalAction> actions;

        private CanonicalCommand(
                String commandId, String eventId, String robotId, List<CanonicalAction> actions) {
            this.commandId = commandId;
            this.eventId = eventId;
            this.robotId = robotId;
            this.actions = Collections.unmodifiableList(new ArrayList<>(actions));
        }

        public String getCommandId() { return commandId; }
        public String getEventId() { return eventId; }
        public String getRobotId() { return robotId; }
        public List<CanonicalAction> getActions() { return actions; }
    }

    public static final class CanonicalAction {
        private final String actionId;
        private final String type;
        private final String text;
        private final String language;
        private final boolean continueListening;
        private final String direction;
        private final Integer degrees;
        private final String target;
        private final String reason;
        private final String mediaId;

        private CanonicalAction(
                String actionId,
                String type,
                String text,
                String language,
                boolean continueListening,
                String direction,
                Integer degrees,
                String target,
                String reason,
                String mediaId
        ) {
            this.actionId = actionId;
            this.type = type;
            this.text = text;
            this.language = language;
            this.continueListening = continueListening;
            this.direction = direction;
            this.degrees = degrees;
            this.target = target;
            this.reason = reason;
            this.mediaId = mediaId;
        }

        private static CanonicalAction speech(
                String actionId, String type, String text, String language,
                boolean continueListening) {
            return new CanonicalAction(
                    actionId, type, text, language, continueListening,
                    null, null, null, null, null);
        }

        private static CanonicalAction turn(String actionId, String direction, int degrees) {
            return new CanonicalAction(
                    actionId, "turn", null, null, false,
                    direction, degrees, null, null, null);
        }

        private static CanonicalAction navigate(String actionId, String target) {
            return new CanonicalAction(
                    actionId, "navigate", null, null, false,
                    null, null, target, null, null);
        }

        private static CanonicalAction media(String actionId, String mediaId) {
            return new CanonicalAction(
                    actionId, "play_media", null, null, false,
                    null, null, null, null, mediaId);
        }

        private static CanonicalAction simple(String actionId, String type, String reason) {
            return new CanonicalAction(
                    actionId, type, null, null, false,
                    null, null, null, reason, null);
        }

        public String getActionId() { return actionId; }
        public String getType() { return type; }
        public String getText() { return text; }
        public String getLanguage() { return language; }
        public boolean shouldContinueListening() { return continueListening; }
        public String getDirection() { return direction; }
        public int getDegrees() { return degrees == null ? 0 : degrees; }
        public String getTarget() { return target; }
        public String getReason() { return reason; }
        public String getMediaId() { return mediaId; }
    }

    public static final class ValidationException extends Exception {
        private final String reason;
        private final String commandId;
        private final String eventId;
        private final String actionId;
        private final String actionType;

        private ValidationException(
                String reason,
                String commandId,
                String eventId,
                String actionId,
                String actionType
        ) {
            super(reason);
            this.reason = reason;
            this.commandId = commandId;
            this.eventId = eventId;
            this.actionId = actionId;
            this.actionType = actionType;
        }

        public String getReason() { return reason; }
        public String getCommandId() { return commandId; }
        public String getEventId() { return eventId; }
        public String getActionId() { return actionId; }
        public String getActionType() { return actionType; }
        public boolean hasCorrelation() {
            return commandId != null && !commandId.isEmpty()
                    && eventId != null && !eventId.isEmpty();
        }
    }
}
