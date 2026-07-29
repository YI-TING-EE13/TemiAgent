"""Hermetic behavior checks for the LM Studio Demo start helper."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "start_lmstudio_3gpu.sh"
E2E_VALIDATION_SCRIPT = ROOT / "tools" / "validate_temi_e2e_stack.sh"


class LmStudioStartHelperTests(unittest.TestCase):
    def _environment(self, root: Path) -> tuple[dict[str, str], Path]:
        target = root / "lmstudio"
        bin_dir = target / "bin"
        bin_dir.mkdir(parents=True)
        capture = root / "calls.txt"
        fake_lms = bin_dir / "lms"
        fake_lms.write_text(
            "#!/usr/bin/env bash\nprintf '%s|%s\\n' \"${CUDA_VISIBLE_DEVICES:-}\" \"$*\" >> \"$LMSTUDIO_CAPTURE\"\n",
            encoding="utf-8",
        )
        fake_lms.chmod(0o755)
        fake_curl = bin_dir / "curl"
        fake_curl.write_text("#!/usr/bin/env bash\nprintf '{}\\n'\n", encoding="utf-8")
        fake_curl.chmod(0o755)
        environment = os.environ.copy()
        environment.update(
            {
                "LMSTUDIO_PROJECT_ROOT": str(ROOT),
                "LMSTUDIO_TARGET_DIR": str(target),
                "LMSTUDIO_MODEL_ID": "test/model",
                "LMSTUDIO_API_IDENTIFIER": "test-model",
                "LMSTUDIO_CAPTURE": str(capture),
                "PATH": f"{bin_dir}:{environment.get('PATH', '')}",
            }
        )
        return environment, capture

    def test_defaults_load_64k_on_demo_gpu_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment, capture = self._environment(Path(temporary))
            result = subprocess.run(
                ["bash", str(SCRIPT)], cwd=ROOT, env=environment, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = capture.read_text(encoding="utf-8")
            self.assertIn("0,1|daemon up", calls)
            self.assertIn(
                "|load test/model --context-length 64000 --gpu max --identifier test-model",
                calls,
            )

    def test_context_drift_is_rejected_before_lm_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment, capture = self._environment(Path(temporary))
            environment.update({"CONTEXT_LENGTH": "64000", "LMSTUDIO_CONTEXT_LENGTH": "32000"})
            result = subprocess.run(
                ["bash", str(SCRIPT)], cwd=ROOT, env=environment, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("must match", result.stderr)
            self.assertFalse(capture.exists())

    def test_gpu_policy_rejects_non_demo_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment, capture = self._environment(Path(temporary))
            environment["LMSTUDIO_VISIBLE_GPUS"] = "0,1,2"
            result = subprocess.run(
                ["bash", str(SCRIPT)], cwd=ROOT, env=environment, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("requires LMSTUDIO_VISIBLE_GPUS=0,1", result.stderr)
            self.assertFalse(capture.exists())

    def test_e2e_validation_helper_uses_the_same_gpu_default(self) -> None:
        source = E2E_VALIDATION_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('LMSTUDIO_VISIBLE_GPUS="${LMSTUDIO_VISIBLE_GPUS:-0,1}"', source)


if __name__ == "__main__":
    unittest.main()
