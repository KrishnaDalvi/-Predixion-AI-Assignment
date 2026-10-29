from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from research_agent.models import Finding, ResearchAnswer, Source
from research_agent.planner import create_plan
from research_agent.synthesizer import GroqSynthesizer, SynthesisError


def _answer_json(question: str, plan, source: Source) -> str:
    answer = ResearchAnswer(
        status="complete",
        question=question,
        short_answer="A supported answer.",
        key_findings=[Finding(text="A supported finding.", source_ids=[source.id])],
        sources_used=[source],
        confidence="medium",
        confidence_rationale="The source supports this finding.",
        plan=plan,
    )
    return answer.model_dump_json()


def test_groq_synthesizer_uses_configured_model_and_json_response(monkeypatch) -> None:
    question = "Research an example"
    plan = create_plan(question)
    source = Source(
        id="S1",
        title="Example",
        url="https://example.com",
        publisher="example.com",
        evidence="A sufficiently long excerpt with evidence for this test.",
    )
    response_text = _answer_json(question, plan, source)
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=response_text))]
        )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    monkeypatch.setattr(
        "research_agent.synthesizer.Groq",
        lambda **kwargs: fake_client,
    )
    synthesizer = GroqSynthesizer("test-key", "llama-3.3-70b-versatile")

    answer = synthesizer.synthesize(question, plan, [source], ["web_search"], [])

    assert answer.status == "complete"
    assert calls[0]["model"] == "llama-3.3-70b-versatile"
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert json.loads(calls[0]["messages"][1]["content"])["question"] == question


def test_groq_synthesizer_rejects_unknown_citation(monkeypatch) -> None:
    question = "Research an example"
    plan = create_plan(question)
    source = Source(
        id="S1",
        title="Example",
        url="https://example.com",
        publisher="example.com",
        evidence="A sufficiently long excerpt with evidence for this test.",
    )
    response = ResearchAnswer(
        status="complete",
        question=question,
        short_answer="Unsupported answer.",
        key_findings=[Finding(text="Unverified finding.", source_ids=["S1"])],
        sources_used=[source],
        confidence="low",
        confidence_rationale="Invalid citation.",
        plan=plan,
    ).model_dump(mode="json")
    response["key_findings"][0]["source_ids"] = ["S2"]
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content=json.dumps(response))
                        )
                    ]
                )
            )
        )
    )
    monkeypatch.setattr("research_agent.synthesizer.Groq", lambda **kwargs: fake_client)
    synthesizer = GroqSynthesizer("test-key", "llama-3.3-70b-versatile")

    with pytest.raises(SynthesisError, match="unknown source"):
        synthesizer.synthesize(question, plan, [source], ["web_search"], [])
