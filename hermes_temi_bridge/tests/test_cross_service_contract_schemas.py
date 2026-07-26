import copy
import json
from pathlib import Path
import shutil
import subprocess
import unittest


SCHEMA_DIR = Path(__file__).parents[1] / "schemas"
AJV_DRIVER = r"""
const fs = require("fs");
const path = require("path");
const Ajv2020 = require("ajv/dist/2020").default;
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const ajv = new Ajv2020({allErrors: true, strict: false});
for (const filename of fs.readdirSync(input.schemaDir)) {
  if (!filename.endsWith(".schema.json")) continue;
  const schema = JSON.parse(fs.readFileSync(path.join(input.schemaDir, filename), "utf8"));
  if (schema.$id) ajv.addSchema(schema);
}
const schema = JSON.parse(fs.readFileSync(path.join(input.schemaDir, input.schema), "utf8"));
const validate = schema.$id ? ajv.getSchema(schema.$id) : ajv.compile(schema);
const valid = validate(input.payload);
process.stdout.write(JSON.stringify({valid, errors: validate.errors || []}));
"""


class CrossServiceContractSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("node") is None:
            raise RuntimeError("node is required for contract schema validation")
        probe = subprocess.run(
            ["node", "-e", "require('ajv/dist/2020')"],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode != 0:
            raise RuntimeError("Ajv 2020 is required for contract schema validation")

    def assert_schema(self, schema, payload, expected=True):
        result = subprocess.run(
            ["node", "-e", AJV_DRIVER],
            input=json.dumps(
                {"schemaDir": str(SCHEMA_DIR), "schema": schema, "payload": payload},
                ensure_ascii=False,
            ),
            capture_output=True,
            text=True,
            check=True,
        )
        outcome = json.loads(result.stdout)
        self.assertEqual(outcome["valid"], expected, outcome["errors"])

    def test_all_schema_documents_declare_draft_2020_12(self):
        for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_resident_identity_legal_boundary_and_illegal(self):
        legal = {
            "schema_version": "1.0",
            "event_id": "evt_identity_001",
            "resident_id": "resident_father",
            "display_name": "father",
            "identity_status": "father",
            "confidence": 0.71,
            "source": "vision_gender_fallback",
            "reason": "Temporary first-year gender-based mapping; not face recognition.",
            "timestamp": "2026-07-26T10:00:00Z",
        }
        boundary = {
            **legal,
            "resident_id": None,
            "display_name": "unknown",
            "identity_status": "unknown",
            "confidence": 0,
            "source": "unknown",
        }
        illegal = {**legal, "identity_status": "mother", "display_name": "father"}
        self.assert_schema("resident_identity_result.schema.json", legal)
        self.assert_schema("resident_identity_result.schema.json", boundary)
        self.assert_schema("resident_identity_result.schema.json", illegal, False)

    def test_legacy_command_request_remains_valid(self):
        payload = {
            "schema_version": "1.0",
            "command_id": "cmd_legacy_001",
            "event_id": "evt_legacy_001",
            "robot_id": "temi-01",
            "source": "hermes_temi_bridge",
            "created_at_ms": 1785060000000,
            "actions": [{"action_id": "act_001", "type": "speak", "text": "hello"}],
        }
        self.assert_schema("temi_command_request.schema.json", payload)

    def test_video_command_legal_boundary_and_illegal(self):
        legal = {
            "schema_version": "1.1",
            "message_type": "video.command",
            "command_id": "req_video_001",
            "request_id": "req_video_001",
            "event_id": "evt_video_001",
            "robot_id": "temi-01",
            "resident_id": "resident_father",
            "action": "play_video",
            "video_id": "exercise_upper_body_01",
            "parameters": {"start_position_ms": 0},
            "source": "hermes_temi_bridge",
            "timestamp": "2026-07-26T10:01:00Z",
        }
        boundary = {**legal, "action": "stop_video", "parameters": {}}
        illegal = {**legal, "action": "seek_video"}
        self.assert_schema("temi_command_request.schema.json", legal)
        self.assert_schema("temi_command_request.schema.json", boundary)
        self.assert_schema("temi_command_request.schema.json", illegal, False)

    def test_legacy_command_result_remains_valid(self):
        payload = {
            "schema_version": "1.0",
            "command_id": "cmd_legacy_001",
            "event_id": "evt_legacy_001",
            "robot_id": "temi-01",
            "status": "success",
            "results": [],
        }
        self.assert_schema("temi_command_result.schema.json", payload)

    def test_video_result_legal_boundary_and_illegal(self):
        legal = {
            "schema_version": "1.1",
            "message_type": "video.command_result",
            "command_id": "req_video_001",
            "request_id": "req_video_001",
            "event_id": "evt_video_001",
            "robot_id": "temi-01",
            "video_id": "exercise_upper_body_01",
            "status": "started",
            "error_code": None,
            "error_message": None,
            "timestamp": "2026-07-26T10:01:01Z",
        }
        boundary = {
            **legal,
            "status": "failed",
            "error_code": "invalid_video_state",
            "error_message": "Video is not active.",
        }
        illegal = {**legal, "status": "failed"}
        self.assert_schema("temi_command_result.schema.json", legal)
        self.assert_schema("temi_command_result.schema.json", boundary)
        self.assert_schema("temi_command_result.schema.json", illegal, False)

    def test_care_report_legal_boundary_and_illegal(self):
        legal = {
            "schema_version": "1.0",
            "report_id": "report_2026-07-26_father",
            "resident_id": "resident_father",
            "display_name": "father",
            "report_date": "2026-07-26",
            "generated_at": "2026-07-26T20:00:00Z",
            "status": "complete",
            "summary": "Synthetic contract example.",
            "discomfort_events": [],
            "abnormal_events": [],
            "reminder_status": [],
            "important_changes": [],
            "follow_up_notes": [],
            "data_completeness": {"status": "complete", "missing_sections": []},
            "error_code": None,
            "error_message": None,
        }
        boundary = copy.deepcopy(legal)
        boundary.update(
            {
                "resident_id": None,
                "display_name": "unknown",
                "status": "identity_unknown",
                "summary": "",
            }
        )
        boundary["data_completeness"] = {
            "status": "identity_unknown",
            "missing_sections": ["summary"],
        }
        boundary["error_code"] = "unknown_resident"
        boundary["error_message"] = "Resident identity is unknown; no resident memory was read."
        illegal = copy.deepcopy(legal)
        illegal["data_completeness"]["missing_sections"] = ["summary"]
        self.assert_schema("care_report.schema.json", legal)
        self.assert_schema("care_report.schema.json", boundary)
        self.assert_schema("care_report.schema.json", illegal, False)

    def test_unsupported_report_version_is_representable(self):
        payload = {
            "schema_version": "1.0",
            "report_id": "report_error_001",
            "resident_id": "resident_father",
            "display_name": "father",
            "report_date": "2026-07-26",
            "generated_at": "2026-07-26T20:00:00Z",
            "status": "unsupported_schema_version",
            "summary": "",
            "discomfort_events": [],
            "abnormal_events": [],
            "reminder_status": [],
            "important_changes": [],
            "follow_up_notes": [],
            "data_completeness": {
                "status": "unsupported_schema_version",
                "missing_sections": [],
                "requested_schema_version": "9.0",
            },
            "error_code": "unsupported_schema_version",
            "error_message": "Requested schema version 9.0 is unsupported.",
        }
        self.assert_schema("care_report.schema.json", payload)

    def test_report_partial_no_records_and_date_not_found_are_representable(self):
        base = {
            "schema_version": "1.0",
            "report_id": "report_state_001",
            "resident_id": "resident_father",
            "display_name": "father",
            "report_date": "2026-07-26",
            "generated_at": "2026-07-26T20:00:00Z",
            "summary": "",
            "discomfort_events": [],
            "abnormal_events": [],
            "reminder_status": [],
            "important_changes": [],
            "follow_up_notes": [],
        }
        cases = (
            (
                "partial",
                "report_partial_data",
                ["reminder_status"],
                "Reminder source was unavailable.",
            ),
            ("no_records", "report_no_records", [], "No records exist for the requested date."),
            ("date_not_found", "report_not_found", [], "The requested date was not found."),
        )
        for status, error_code, missing_sections, error_message in cases:
            with self.subTest(status=status):
                payload = {
                    **base,
                    "status": status,
                    "data_completeness": {
                        "status": status,
                        "missing_sections": missing_sections,
                    },
                    "error_code": error_code,
                    "error_message": error_message,
                }
                self.assert_schema("care_report.schema.json", payload)

    def test_report_interaction_legal_boundary_and_illegal(self):
        legal = {
            "schema_version": "1.0",
            "request_id": "req_report_001",
            "report_id": "report_2026-07-26_father",
            "resident_id": "resident_father",
            "action": "viewed",
            "status": "accepted",
            "error_code": None,
            "error_message": None,
            "timestamp": "2026-07-26T20:05:00Z",
        }
        boundary = {**legal, "action": "acknowledged"}
        illegal = {**legal, "resident_id": ""}
        self.assert_schema("care_report_interaction_result.schema.json", legal)
        self.assert_schema("care_report_interaction_result.schema.json", boundary)
        self.assert_schema("care_report_interaction_result.schema.json", illegal, False)


if __name__ == "__main__":
    unittest.main()
