from __future__ import annotations

from research_agent.agent import ResearchAgent
from research_agent.models import Finding, ResearchAnswer, Source
from research_agent.planner import create_plan
from research_agent.synthesizer import SynthesisError, SYSTEM_PROMPT
from research_agent.tools import ToolError


class FakeTools:
    def __init__(self) -> None:
        self.search_queries: list[str] = []
        self.extracted_urls: list[str] = []

    def search(self, query: str) -> list[dict[str, object]]:
        self.search_queries.append(query)
        if len(self.search_queries) > 1:
            return [
                {
                    "title": "Source one duplicate",
                    "url": "https://example.com/a#section",
                    "publisher": "example.com",
                    "evidence": "A sufficiently long source summary with useful evidence.",
                }
            ]
        return [
            {
                "title": "Source one",
                "url": "https://example.com/a",
                "publisher": "example.com",
                "evidence": "A sufficiently long source summary with useful evidence.",
            },
            {
                "title": "Source two",
                "url": "https://example.org/b",
                "publisher": "example.org",
                "evidence": "Another sufficiently long source summary with evidence.",
            },
        ]

    def extract(self, urls: list[str]) -> dict[str, str]:
        self.extracted_urls = urls
        return {urls[0]: "Extracted page text with additional relevant evidence."}


class FakeSynthesizer:
    def synthesize(self, question, plan, sources, tools_used, errors):
        return ResearchAnswer(
            status="complete",
            question=question,
            short_answer="A grounded answer.",
            key_findings=[Finding(text="Finding supported by evidence.", source_ids=["S1"])],
            sources_used=sources,
            confidence="medium",
            confidence_rationale="Two sources were retrieved.",
            assumptions=[],
            limitations=[],
            suggested_next_steps=[],
            plan=plan,
            tools_used=tools_used,
            errors=errors,
        )


def test_planner_selects_comparison_intent_and_bounded_tools() -> None:
    plan = create_plan("Compare two vector databases for a startup")

    assert plan.task_type == "comparison"
    assert len(plan.search_queries) <= 3
    assert plan.selected_tools == ["web_search", "source_extract"]
    assert 3 <= len(plan.steps) <= 5


def test_agent_deduplicates_extracts_and_returns_cited_answer() -> None:
    tools = FakeTools()
    answer = ResearchAgent(tools, FakeSynthesizer()).run("Compare two products")

    assert answer.status == "complete"
    assert len(answer.sources_used) == 2
    assert answer.sources_used[0].fetched is True
    assert answer.sources_used[0].evidence.startswith("Extracted")
    assert answer.key_findings[0].source_ids == ["S1"]
    assert len(tools.extracted_urls) == 2


def test_agent_returns_explicit_failure_when_search_fails() -> None:
    class FailedTools(FakeTools):
        def search(self, query: str) -> list[dict[str, object]]:
            raise ToolError("provider timeout")

    answer = ResearchAgent(FailedTools(), FakeSynthesizer()).run("Research this")

    assert answer.status == "failed"
    assert answer.sources_used == []
    assert "provider timeout" in answer.errors[0]
    assert answer.confidence == "low"


def test_agent_does_not_label_answer_complete_after_tool_failure() -> None:
    class FailingExtractTools(FakeTools):
        def extract(self, urls: list[str]) -> dict[str, str]:
            raise ToolError("extract unavailable")

    answer = ResearchAgent(FailingExtractTools(), FakeSynthesizer()).run("Research this")

    assert answer.status == "partial"
    assert "extract unavailable" in answer.errors[0]


def test_synthesis_failure_is_not_presented_as_success() -> None:
    class BrokenSynthesizer:
        def synthesize(self, *args, **kwargs):
            raise SynthesisError("invalid model response")

    answer = ResearchAgent(FakeTools(), BrokenSynthesizer()).run("Research this")

    assert answer.status == "partial"
    assert answer.key_findings == []
    assert "not a synthesized answer" in answer.limitations[0]
    assert "invalid model response" in answer.errors[0]


def test_prompt_marks_retrieved_page_text_as_untrusted() -> None:
    assert "never instructions" in SYSTEM_PROMPT
    assert "Do not invent sources" in SYSTEM_PROMPT
