"""Exact father-only repeated-discomfort phrases for the controlled Demo."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


DISPATCH_MODE = "deterministic_repeated_discomfort_fast_path"
_WAKE_WORD = "小安小安"
_PUNCTUATION = re.compile(r"[\s\u3000，,。．！!？?、；;：:\"'「」『』（）()\[\]【】]+")
_BP_PATTERNS = (
    re.compile(r"^(?:我量好(?:了)?)?血壓(?:是)?([0-9]{2,3})[/／]([0-9]{2,3})$"),
    re.compile(r"^我量到([0-9]{2,3})跟([0-9]{2,3})$"),
    re.compile(r"^收縮壓([0-9]{2,3})舒張壓([0-9]{2,3})$"),
)


@dataclass(frozen=True)
class RepeatedDiscomfortIntent:
    """One native care callback request after exact transcript recognition."""

    action: str
    systolic: int | None = None
    diastolic: int | None = None


_RETRIEVE = {"我又不舒服了", "我又不太舒服", "我又覺得不舒服", "今天又不太舒服"}
_CONFIRM = {"對", "是", "是的", "也是頭痛"}


def normalize_repeated_discomfort_transcript(transcript: str) -> str:
    """Normalize only punctuation, spacing, and the optional leading wake word."""
    if not isinstance(transcript, str):
        return ""
    normalized = _PUNCTUATION.sub("", unicodedata.normalize("NFKC", transcript).replace("\u200b", ""))
    if normalized.startswith(_WAKE_WORD):
        normalized = normalized[len(_WAKE_WORD) :]
    return normalized


def match_repeated_discomfort_intent(transcript: str) -> RepeatedDiscomfortIntent | None:
    """Match only reviewed flow phrases; no fuzzy symptom or medical parsing."""
    normalized = normalize_repeated_discomfort_transcript(transcript)
    if normalized in _RETRIEVE:
        return RepeatedDiscomfortIntent("retrieve_repeated_discomfort")
    if normalized in _CONFIRM:
        return RepeatedDiscomfortIntent("confirm_repeated_headache")
    for pattern in _BP_PATTERNS:
        blood_pressure = pattern.fullmatch(normalized)
        if blood_pressure is not None:
            return RepeatedDiscomfortIntent(
                "record_repeated_blood_pressure",
                systolic=int(blood_pressure.group(1)),
                diastolic=int(blood_pressure.group(2)),
            )
    return None
