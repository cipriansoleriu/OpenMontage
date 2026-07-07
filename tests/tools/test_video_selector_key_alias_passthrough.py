"""Pins the passthrough contract key_alias depends on (Persona fork, M1).

key_alias reaches provider tools only because VideoSelector.execute() copies
the caller's inputs verbatim (adapted = dict(inputs)) before delegating. If a
future selector change filtered inputs down to the chosen tool's schema, the
alias would be silently stripped and every call would bill the default key —
exactly the silent-wrong-key failure lib/keyvault.py exists to prevent.
Reuses the stub pattern from test_video_selector_routing.py.
"""

from __future__ import annotations

from typing import Any

import pytest

from tools.base_tool import ToolResult, ToolStatus
from tools.video.video_selector import VideoSelector


class _RecordingStubTool:
    capability = "video_generation"

    def __init__(self, name: str = "stub_video", provider: str = "stubprov") -> None:
        self.name = name
        self.provider = provider
        self.quality_score: float | None = None
        self.best_for = [name]
        self.supports = {"text_to_video": True, "image_to_video": True}
        self.input_schema = {"properties": {"prompt": {}}}
        self.agent_skills: list[str] = []
        self.fallback_tools: list[str] = []
        self.received_inputs: dict[str, Any] | None = None

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def is_operation_available(self, operation: str) -> bool:
        return self.supports.get(operation, False)

    def get_info(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "provider": self.provider,
            "agent_skills": self.agent_skills,
            "best_for": self.best_for,
            "supports": self.supports,
            "quality_score": self.quality_score,
        }

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.1

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 60.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        self.received_inputs = dict(inputs)
        return ToolResult(success=True, data={})


class _ScoreStub:
    def __init__(self, tool_name: str, provider: str, weighted: float) -> None:
        self.tool_name = tool_name
        self.provider = provider
        self.weighted_score = weighted

    def explain(self) -> str:
        return f"{self.tool_name} ({self.provider}): {self.weighted_score:.2f}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "provider": self.provider,
            "weighted_score": self.weighted_score,
        }


def test_selector_passes_key_alias_through_to_provider_tool(monkeypatch):
    stub = _RecordingStubTool()
    selector = VideoSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [stub])
    monkeypatch.setattr(
        "lib.scoring.rank_providers",
        lambda candidates, task_context: [_ScoreStub(stub.name, stub.provider, 0.9)],
    )

    result = selector.execute({"prompt": "a cat", "key_alias": "client"})

    assert result.success, result.error
    assert stub.received_inputs is not None
    assert stub.received_inputs.get("key_alias") == "client"
