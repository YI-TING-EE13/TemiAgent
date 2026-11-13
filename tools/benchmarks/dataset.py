"""Versioned JSONL case loading shared by benchmark runners (stdlib only)."""

from dataclasses import dataclass
import json
from pathlib import Path
import re


DEFAULT_DATASET = Path(__file__).parent / "test_cases" / "care_dialogue.jsonl"


@dataclass(frozen=True)
class ActionSelectionCase:
    case_id: str
    text: str
    category: str
    purpose: str


def load_cases(path: Path = DEFAULT_DATASET) -> tuple[ActionSelectionCase, ...]:
    """Validate the single-turn subset; never silently discard future turns/state."""
    cases = []
    seen = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("case must be an object")
            if set(item) - {"case_id", "tags", "purpose", "turns"}:
                raise ValueError("unsupported case fields (state/multi-turn execution is not implemented)")
            case_id = item.get("case_id")
            if not isinstance(case_id, str) or not re.fullmatch(r"[A-Z][A-Z0-9]*-[0-9]+", case_id):
                raise ValueError("case_id must be a safe ID such as BP-01")
            if case_id in seen:
                raise ValueError("duplicate case_id")
            turns = item.get("turns")
            if (not isinstance(turns, list) or len(turns) != 1
                    or not isinstance(turns[0], dict)
                    or set(turns[0]) != {"role", "text"}
                    or turns[0]["role"] != "user"
                    or not isinstance(turns[0]["text"], str) or not turns[0]["text"].strip()):
                raise ValueError("exactly one nonempty user turn is supported")
            tags = item.get("tags", [])
            if not isinstance(tags, list) or not tags or not all(isinstance(t, str) and t.strip() for t in tags):
                raise ValueError("tags must be a nonempty string list")
            purpose = item.get("purpose", "")
            if not isinstance(purpose, str):
                raise ValueError("purpose must be a string")
            seen.add(case_id)
            cases.append(ActionSelectionCase(case_id, turns[0]["text"], ",".join(tags), purpose))
        except ValueError as exc:
            raise ValueError(f"{path.name}:{line_number}: {exc}") from exc
    if not cases:
        raise ValueError("dataset is empty")
    return tuple(cases)
