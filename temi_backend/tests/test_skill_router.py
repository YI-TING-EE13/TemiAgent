"""Unit tests for VLM action parsing and routing."""

from __future__ import annotations

from temi_backend.agent_core import SkillRouter


class FakeBridge:
    """Capture robot commands emitted by the router."""

    def __init__(self) -> None:
        self.speak_calls = []
        self.navigate_calls = []

    def publish_speak(self, text: str, language: str = "ZH_TW", continue_listening: bool = False) -> None:
        self.speak_calls.append((text, language, continue_listening))

    def publish_navigate(self, target_location: str) -> None:
        self.navigate_calls.append(target_location)


def test_route_executes_supported_actions_from_markdown_response() -> None:
    bridge = FakeBridge()
    router = SkillRouter(bridge)

    executed_count = router.route(
        """
<think>Analyze the scene.</think>
```json
[
  {"action": "speak", "parameters": {"text": "I see it.", "language": "EN_US", "continue_listening": true}},
  {"action": "navigate", "parameters": {"target_location": "home_base"}}
]
```
"""
    )

    assert executed_count == 2
    assert bridge.speak_calls == [("I see it.", "EN_US", True)]
    assert bridge.navigate_calls == ["home_base"]


def test_route_ignores_invalid_json() -> None:
    bridge = FakeBridge()
    router = SkillRouter(bridge)

    assert router.route("not json") == 0
    assert bridge.speak_calls == []
    assert bridge.navigate_calls == []


def test_route_skips_unknown_actions() -> None:
    bridge = FakeBridge()
    router = SkillRouter(bridge)

    executed_count = router.route('[{"action":"dance","parameters":{}}]')

    assert executed_count == 0
    assert bridge.speak_calls == []
    assert bridge.navigate_calls == []
