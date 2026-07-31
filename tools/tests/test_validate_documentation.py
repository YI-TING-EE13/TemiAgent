"""Regression coverage for the repository documentation structure checker."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import validate_documentation


class DocumentationValidationTests(unittest.TestCase):
    """Keep canonical documentation structure executable as a narrow test."""

    def test_repository_documentation_is_valid(self) -> None:
        """The current working tree has valid links, fences, and schema copies."""
        self.assertEqual(validate_documentation.main(), 0)
