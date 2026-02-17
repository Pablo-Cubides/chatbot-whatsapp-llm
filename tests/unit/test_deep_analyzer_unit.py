"""Unit tests for deep analyzer behavior."""

import pytest

from src.services.deep_analyzer import DeepAnalyzer, ObjectiveStatus

pytestmark = pytest.mark.unit


def test_should_trigger_analysis_by_count(monkeypatch) -> None:
    monkeypatch.setenv("DEEP_ANALYSIS_ENABLED", "true")
    monkeypatch.setenv("DEEP_ANALYSIS_TRIGGER_CONVERSATIONS", "2")
    analyzer = DeepAnalyzer()

    analyzer.record_conversation_end()
    assert analyzer.should_trigger_analysis() is False

    analyzer.record_conversation_end()
    assert analyzer.should_trigger_analysis() is True


@pytest.mark.asyncio
async def test_analyze_conversation_fallback_without_llm(monkeypatch) -> None:
    monkeypatch.setenv("DEEP_ANALYSIS_ENABLED", "true")
    analyzer = DeepAnalyzer(multi_llm=None)

    analysis = await analyzer.analyze_conversation(
        session_id="s1",
        contact="c1",
        messages=[{"role": "user", "content": "hola"}],
    )

    assert analysis.session_id == "s1"
    assert analysis.objective_status == ObjectiveStatus.IN_PROGRESS
    assert analysis.conversation_quality_score >= 0
