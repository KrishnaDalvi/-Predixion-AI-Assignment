import pytest
from pydantic import ValidationError

from research_agent.models import Finding, ResearchAnswer, ResearchPlan


def test_answer_rejects_citation_ids_missing_from_sources() -> None:
    plan = ResearchPlan(
        task_type="overview",
        search_queries=["question"],
        steps=["search", "filter", "synthesize"],
        selected_tools=["web_search", "source_extract"],
    )
    with pytest.raises(ValidationError, match="unknown source IDs"):
        ResearchAnswer(
            status="partial",
            question="question",
            short_answer="answer",
            key_findings=[Finding(text="claim", source_ids=["S9"])],
            sources_used=[],
            confidence="low",
            confidence_rationale="No evidence.",
            plan=plan,
        )


def test_answer_rejects_uncited_partial_findings() -> None:
    plan = ResearchPlan(
        task_type="overview",
        search_queries=["question"],
        steps=["search", "filter", "synthesize"],
        selected_tools=["web_search", "source_extract"],
    )
    with pytest.raises(ValidationError, match="Every finding must cite"):
        ResearchAnswer(
            status="partial",
            question="question",
            short_answer="answer",
            key_findings=[Finding(text="unsupported claim")],
            sources_used=[],
            confidence="low",
            confidence_rationale="Insufficient evidence.",
            plan=plan,
        )
