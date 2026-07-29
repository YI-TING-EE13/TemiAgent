"""No-network tests for resident context health observability."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "hermes_resident_server.py"
SPEC = importlib.util.spec_from_file_location("resident_context_health", MODULE_PATH)
assert SPEC and SPEC.loader
resident_server = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = resident_server
SPEC.loader.exec_module(resident_server)


class ResidentContextHealthTests(unittest.TestCase):
    def test_effective_context_lengths_require_matching_positive_values(self) -> None:
        agent = SimpleNamespace(
            context_compressor=SimpleNamespace(context_length=64_000),
            _aux_compression_context_length_config=64_000,
        )
        self.assertEqual(resident_server._effective_context_lengths(agent), (64_000, 64_000))

    def test_effective_context_lengths_fail_closed_when_auxiliary_config_missing(self) -> None:
        agent = SimpleNamespace(
            context_compressor=SimpleNamespace(context_length=64_000),
            _aux_compression_context_length_config=None,
        )
        with self.assertRaisesRegex(RuntimeError, "must set positive"):
            resident_server._effective_context_lengths(agent)

    def test_health_includes_safe_effective_context_fields(self) -> None:
        resident = object.__new__(resident_server.ResidentHermes)
        resident.model = "google/gemma-4-31b"
        resident.provider = "custom"
        resident.base_url = "http://localhost:1234/v1"
        resident.context_length = 64_000
        resident.compression_context_length = 64_000
        resident.toolsets = []
        resident.skill_paths = []
        resident.hermes_home = ""
        resident.memory_enabled = False
        resident.demo_care_scenario_prompt_enabled = False
        resident.media_tool_enabled = False
        resident.media_tool_names = []
        resident.media_fast_path_enabled = False
        resident.demo_operator_identity_enabled = False
        resident.resident_identity_enabled = False
        resident.identity_tool_enabled = False
        resident.identity_tool_names = []
        resident.identity_fast_path_enabled = False
        resident.care_memory_v2_enabled = False
        resident.demo_repeated_discomfort_enabled = False
        resident.repeated_discomfort_tool_names = []
        resident.repeated_discomfort_fast_path_enabled = False
        resident.started_at = 0
        resident.request_count = 0

        health = resident.health()

        self.assertEqual(health["context_length"], 64_000)
        self.assertEqual(health["compression_context_length"], 64_000)
        self.assertNotIn("api_key", health)


if __name__ == "__main__":
    unittest.main()
