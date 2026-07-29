"""Exact, Demo-only operator identity phrase matching for Resident Hermes."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


DISPATCH_MODE = "deterministic_demo_identity_fast_path"
_WAKE_WORD = "小安小安"
_PUNCTUATION = re.compile(r"[\s\u3000，,。．！!？?、；;：:\"'「」『』（）()\[\]【】]+")


@dataclass(frozen=True)
class DemoIdentityIntent:
    """One explicit operator identity instruction; it is not speech inference."""

    action: str
    identity_status: str | None = None


_INTENTS = {
    # The long forms are the reviewed operator phrases used in the live Demo.
    # They remain exact after only harmless punctuation/wake-word normalization.
    "進入示範管理模式持續發布王先生身分": DemoIdentityIntent("start_demo_identity", "father"),
    "示範模式切換到王先生": DemoIdentityIntent("start_demo_identity", "father"),
    "Demo管理持續發布王先生身分": DemoIdentityIntent("start_demo_identity", "father"),
    "進入示範管理模式持續發布王太太身分": DemoIdentityIntent("start_demo_identity", "mother"),
    "示範模式切換到王太太": DemoIdentityIntent("start_demo_identity", "mother"),
    "Demo管理持續發布王太太身分": DemoIdentityIntent("start_demo_identity", "mother"),
    "停止示範身分發布": DemoIdentityIntent("stop_demo_identity"),
    "示範模式切換為未知住民": DemoIdentityIntent("stop_demo_identity"),
    "Demo管理清除目前身分": DemoIdentityIntent("stop_demo_identity"),
    "目前示範身分是誰": DemoIdentityIntent("get_demo_identity_status"),
    "Demo管理查詢目前身分發布狀態": DemoIdentityIntent("get_demo_identity_status"),
    # Short forms are retained as separately reviewed operator commands.
    "Demo切換為爸爸": DemoIdentityIntent("start_demo_identity", "father"),
    "Demo設定為爸爸": DemoIdentityIntent("start_demo_identity", "father"),
    "Demo切換為媽媽": DemoIdentityIntent("start_demo_identity", "mother"),
    "Demo設定為媽媽": DemoIdentityIntent("start_demo_identity", "mother"),
    "Demo清除身分": DemoIdentityIntent("stop_demo_identity"),
    "Demo停止身分": DemoIdentityIntent("stop_demo_identity"),
    "Demo身分狀態": DemoIdentityIntent("get_demo_identity_status"),
    "Demo查詢身分": DemoIdentityIntent("get_demo_identity_status"),
}


def normalize_demo_identity_transcript(transcript: str) -> str:
    """Remove only presentation noise before exact operator phrase comparison."""
    if not isinstance(transcript, str):
        return ""
    normalized = _PUNCTUATION.sub("", unicodedata.normalize("NFKC", transcript).replace("\u200b", ""))
    if normalized.startswith(_WAKE_WORD):
        normalized = normalized[len(_WAKE_WORD) :]
    return normalized


def match_demo_identity_intent(transcript: str) -> DemoIdentityIntent | None:
    """Return an intent only for the small reviewed operator command set."""
    return _INTENTS.get(normalize_demo_identity_transcript(transcript))
