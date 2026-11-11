"""Reasoning configuration tests without Hermes, model, network or services."""

from __future__ import annotations

from contextlib import redirect_stderr
import io
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

from tools import hermes_resident_server as resident


ROOT = Path(__file__).resolve().parents[2]
EXPLICIT_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh")


class ResidentReasoningTests(unittest.TestCase):
    def test_request_overrides_for_default_and_explicit_efforts(self) -> None:
        self.assertIsNone(resident._reasoning_request_overrides("default"))
        for effort in EXPLICIT_EFFORTS:
            with self.subTest(effort=effort):
                self.assertEqual(
                    resident._reasoning_request_overrides(effort),
                    {"reasoning_effort": effort},
                )

    def _run_cli(self, arguments: list[str]) -> mock.Mock:
        fake_resident = SimpleNamespace(
            model="synthetic-model", provider="custom", toolsets=[],
            skill_paths=[], memory_enabled=False, hermes_home="",
        )
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(resident, "_reexec_with_hermes_python_if_available"),
            mock.patch.object(resident.logging, "basicConfig"),
            mock.patch.object(resident, "ResidentHermes", return_value=fake_resident) as constructor,
            mock.patch.object(resident, "ResidentServer") as server,
        ):
            self.assertEqual(resident.main(arguments), 0)
            constructor.assert_called_once()
            server.return_value.serve_forever.assert_called_once_with()
            server.return_value.server_close.assert_called_once_with()
        return constructor

    def test_cli_defaults_and_explicit_efforts(self) -> None:
        constructor = self._run_cli([])
        self.assertEqual(constructor.call_args.kwargs["reasoning_effort"], "default")
        for effort in EXPLICIT_EFFORTS:
            with self.subTest(effort=effort):
                constructor = self._run_cli(["--reasoning-effort", effort])
                self.assertEqual(constructor.call_args.kwargs["reasoning_effort"], effort)

    def test_cli_rejects_invalid_effort_before_initializing_resident(self) -> None:
        for invalid in ("invalid", "on", "off", "", "NONE"):
            with (
                self.subTest(value=invalid),
                mock.patch.object(resident, "_reexec_with_hermes_python_if_available"),
                mock.patch.object(resident, "ResidentHermes") as constructor,
                mock.patch.object(resident, "ResidentServer") as server,
                redirect_stderr(io.StringIO()),
            ):
                with self.assertRaises(SystemExit) as error:
                    resident.main(["--reasoning-effort", invalid])
                self.assertEqual(error.exception.code, 2)
                constructor.assert_not_called()
                server.assert_not_called()

    def _construct_with_fake_agent(self, effort: str) -> mock.Mock:
        package = ModuleType("hermes_cli")
        package.__path__ = []
        config_module = ModuleType("hermes_cli.config")
        config_module.load_config = mock.Mock(return_value={})
        models_module = ModuleType("hermes_cli.models")
        models_module.detect_provider_for_model = mock.Mock()
        runtime_module = ModuleType("hermes_cli.runtime_provider")
        runtime_module.resolve_runtime_provider = mock.Mock(return_value={
            "provider": "custom", "base_url": "http://127.0.0.1:1234/v1",
            "api_key": "synthetic-placeholder", "api_mode": "chat_completions",
        })
        agent_module = ModuleType("run_agent")
        fake_agent = SimpleNamespace(
            context_compressor=SimpleNamespace(context_length=64000),
            _aux_compression_context_length_config=64000,
        )
        agent_module.AIAgent = mock.Mock(return_value=fake_agent)
        modules = {
            "hermes_cli": package, "hermes_cli.config": config_module,
            "hermes_cli.models": models_module,
            "hermes_cli.runtime_provider": runtime_module, "run_agent": agent_module,
        }
        with (
            mock.patch.dict(sys.modules, modules),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(resident.os, "chdir") as chdir,
            mock.patch.object(resident, "_ensure_hermes_import_path"),
            mock.patch.object(resident, "_read_skill_prompt", return_value="Synthetic rules"),
        ):
            worker = resident.ResidentHermes(
                model="synthetic-model", provider="custom", reasoning_effort=effort,
                toolsets=[], skill_paths=[], cwd=ROOT, enable_memory=False,
                media_tool_enabled=False, media_v11_enabled=False,
                media_fast_path_enabled=False, demo_operator_identity_enabled=False,
                demo_repeated_discomfort_enabled=False,
            )
            chdir.assert_called_once_with(ROOT)
            self.assertIs(worker._agent, fake_agent)
            agent_module.AIAgent.assert_called_once()
        return agent_module.AIAgent

    def test_agent_constructor_receives_default_and_explicit_overrides(self) -> None:
        constructor = self._construct_with_fake_agent("default")
        self.assertIsNone(constructor.call_args.kwargs["request_overrides"])
        for effort in EXPLICIT_EFFORTS:
            with self.subTest(effort=effort):
                constructor = self._construct_with_fake_agent(effort)
                self.assertEqual(
                    constructor.call_args.kwargs["request_overrides"],
                    {"reasoning_effort": effort},
                )


if __name__ == "__main__":
    unittest.main()
