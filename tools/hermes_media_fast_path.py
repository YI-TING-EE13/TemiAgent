"""Deterministic, Demo-gated Media intent matching for Resident Hermes.

This module intentionally recognizes a very small, reviewed Chinese phrase set.
It is used only by the root-owned Resident HTTP service before LLM inference;
it never knows about MQTT, Android paths, URLs, or arbitrary video identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


VIDEO_ID = "elderly_hand_exercise"
DISPATCH_MODE = "deterministic_media_fast_path"


@dataclass(frozen=True)
class MediaIntent:
    """One reviewed native Media tool invocation."""

    action: str
    video_id: str

    @property
    def arguments(self) -> dict[str, str]:
        """Return the exact native-tool arguments for this intent."""
        return {"video_id": self.video_id} if self.action == "play_video" else {}


_PLAY_INTENT = MediaIntent("play_video", VIDEO_ID)
# These are reviewed ASR surface forms observed in the real Demo.  The
# expansion is deliberately finite: only the hand-exercise noun phrase can be
# substituted, only fixed playback templates are accepted, and every match
# still targets the one allowlisted video ID.  This is not phonetic/fuzzy search.
_HAND_EXERCISE_SURFACES = ("手部運動", "首都運動", "守護運動")
_PLAY_WITH_VIDEO_PREFIXES = ("播放", "幫我播放", "請幫我播放", "幫我放")

_INTENTS = {
    **{
        f"{prefix}{surface}影片": _PLAY_INTENT
        for surface in _HAND_EXERCISE_SURFACES
        for prefix in _PLAY_WITH_VIDEO_PREFIXES
    },
    **{f"播放{surface}": _PLAY_INTENT for surface in _HAND_EXERCISE_SURFACES},
    **{f"我要做{surface}": _PLAY_INTENT for surface in _HAND_EXERCISE_SURFACES},
    "播放影片": _PLAY_INTENT,
    "暫停影片": MediaIntent("pause_video", VIDEO_ID),
    "先暫停": MediaIntent("pause_video", VIDEO_ID),
    "幫我暫停影片": MediaIntent("pause_video", VIDEO_ID),
    "繼續播放影片": MediaIntent("resume_video", VIDEO_ID),
    "繼續影片": MediaIntent("resume_video", VIDEO_ID),
    "恢復播放": MediaIntent("resume_video", VIDEO_ID),
    "停止影片": MediaIntent("stop_video", VIDEO_ID),
    "關掉影片": MediaIntent("stop_video", VIDEO_ID),
    "不要播了": MediaIntent("stop_video", VIDEO_ID),
}
_WAKE_WORD = "小安小安"
_POLITE_PREFIXES = ("請問", "麻煩", "可以", "可否", "請")
_POLITE_SUFFIXES = ("謝謝你", "謝謝", "拜託")
_PUNCTUATION = re.compile(r"[\s\u3000，,。．！!？?、；;：:\"'「」『』（）()\[\]【】]+")


def normalize_media_transcript(transcript: str) -> str:
    """Normalize only spacing, punctuation, one leading wake word, and polite edges.

    The result is still compared by exact equality.  This is deliberately not a
    fuzzy matcher and it never rewrites semantic terms such as a video name.
    """
    if not isinstance(transcript, str):
        return ""
    normalized = unicodedata.normalize("NFKC", transcript).replace("\u200b", "")
    normalized = _PUNCTUATION.sub("", normalized)
    if normalized.startswith(_WAKE_WORD):
        normalized = normalized[len(_WAKE_WORD) :]
    return normalized


def match_media_intent(transcript: str) -> MediaIntent | None:
    """Return a reviewed intent only when the normalized text is exact."""
    normalized = normalize_media_transcript(transcript)
    direct = _INTENTS.get(normalized)
    if direct is not None:
        return direct
    for prefix in _POLITE_PREFIXES:
        if normalized.startswith(prefix):
            candidate = normalized[len(prefix) :]
            if candidate in _INTENTS:
                return _INTENTS[candidate]
    for suffix in _POLITE_SUFFIXES:
        if normalized.endswith(suffix):
            candidate = normalized[: -len(suffix)]
            if candidate in _INTENTS:
                return _INTENTS[candidate]
    return None
