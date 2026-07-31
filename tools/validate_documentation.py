#!/usr/bin/env python3
"""Validate tracked TemiAgent documentation without starting runtime services.

The checker intentionally stays small and dependency-free. It validates the
portable structure that is easy to regress in a documentation-only change:
relative Markdown links, balanced fenced code blocks, and reader-schema copies
mapped by ``docs/architecture/contract_traceability.md``.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
FENCE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})")
SCHEMA_COPIES = (
    ("hermes_temi_bridge/schemas/asr_final_event.schema.json", "docs/schemas/asr_final_event.schema.json"),
    ("hermes_temi_bridge/schemas/hermes_action_output.schema.json", "docs/schemas/hermes_output.schema.json"),
    ("hermes_temi_bridge/schemas/temi_command_request.schema.json", "docs/schemas/command_request.schema.json"),
    ("hermes_temi_bridge/schemas/temi_command_result.schema.json", "docs/schemas/command_result.schema.json"),
    ("hermes_temi_bridge/schemas/cross_service_common.schema.json", "docs/schemas/cross_service_common.schema.json"),
    ("hermes_temi_bridge/schemas/resident_identity_result.schema.json", "docs/schemas/resident_identity_result.schema.json"),
    ("hermes_temi_bridge/schemas/care_report.schema.json", "docs/schemas/care_report.schema.json"),
    ("hermes_temi_bridge/schemas/care_report_interaction_result.schema.json", "docs/schemas/care_report_interaction_result.schema.json"),
)


def _documentation_files() -> list[Path]:
    """Return first-party tracked Markdown plus untracked in-tree operations docs."""
    completed = subprocess.run(
        ["git", "-c", "core.quotePath=false", "ls-files", "--", "*.md"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    ignored_prefixes = ("anomaly_detection/third_party/", "hermes-agent/")
    tracked = {
        ROOT / relative
        for relative in completed.stdout.splitlines()
        if not relative.startswith(ignored_prefixes)
    }
    working_docs = {ROOT / "README.md", *ROOT.glob("docs/**/*.md")}
    return sorted(path for path in tracked | working_docs if path.is_file())


def _is_external_or_anchor(target: str) -> bool:
    """Return whether a Markdown link does not name a local repository file."""
    return not target or target.startswith(("#", "http://", "https://", "mailto:"))


def _validate_links(path: Path, errors: list[str]) -> None:
    """Append failures for missing local Markdown link targets in one file."""
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for match in LINK_PATTERN.finditer(line):
            target = match.group(1).strip().strip("<>")
            target = unquote(target.split("#", 1)[0])
            if _is_external_or_anchor(target):
                continue
            candidate = (path.parent / target).resolve()
            if not candidate.exists():
                errors.append(f"{path.relative_to(ROOT)}:{line_number}: missing link target {target!r}")


def _validate_fences(path: Path, errors: list[str]) -> None:
    """Append failures for unclosed Markdown fenced code blocks in one file."""
    active: tuple[str, int] | None = None
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = FENCE_PATTERN.match(line)
        if match is None:
            continue
        fence = match.group(1)
        if active is None:
            active = (fence[0], line_number)
        elif fence[0] == active[0]:
            active = None
    if active is not None:
        errors.append(f"{path.relative_to(ROOT)}:{active[1]}: unclosed {active[0] * 3} fence")


def _validate_schema_copies(errors: list[str]) -> None:
    """Append failures when a reader schema differs from its runtime source."""
    for runtime_relative, reader_relative in SCHEMA_COPIES:
        runtime = ROOT / runtime_relative
        reader = ROOT / reader_relative
        if not runtime.is_file() or not reader.is_file():
            errors.append(f"missing schema mapping endpoint: {runtime_relative} -> {reader_relative}")
        elif runtime.read_bytes() != reader.read_bytes():
            errors.append(f"schema copy drift: {runtime_relative} != {reader_relative}")


def main() -> int:
    """Run all read-only documentation structure checks and report a summary."""
    errors: list[str] = []
    files = _documentation_files()
    for path in files:
        _validate_links(path, errors)
        _validate_fences(path, errors)
    _validate_schema_copies(errors)
    if errors:
        print("Documentation validation failed:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"Documentation validation passed: {len(files)} first-party Markdown files, {len(SCHEMA_COPIES)} schema mappings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
