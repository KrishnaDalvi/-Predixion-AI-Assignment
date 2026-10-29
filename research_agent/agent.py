from __future__ import annotations

from typing import Protocol
from urllib.parse import urlparse

from research_agent.models import Finding, ResearchAnswer, ResearchPlan, Source
from research_agent.planner import create_plan
from research_agent.synthesizer import SynthesisError
from research_agent.tools import ToolError


class ResearchTools(Protocol):
    def search(self, query: str) -> list[dict[str, object]]: ...

    def extract(self, urls: list[str]) -> dict[str, str]: ...


class Synthesizer(Protocol):
    def synthesize(
        self,
        question: str,
        plan: ResearchPlan,
        sources: list[Source],
        tools_used: list[str],
        errors: list[str],
    ) -> ResearchAnswer: ...


class ResearchAgent:
    def __init__(self, tools: ResearchTools, synthesizer: Synthesizer) -> None:
        self.tools = tools
        self.synthesizer = synthesizer

    def run(self, question: str) -> ResearchAnswer:
        question = question.strip()
        if not question:
            raise ValueError("Question must not be empty")
        if len(question) > 1000:
            raise ValueError("Question must be 1000 characters or fewer")

        plan = create_plan(question)
        records: list[dict[str, object]] = []
        errors: list[str] = []
        tools_used: list[str] = []
        for query in plan.search_queries:
            try:
                records.extend(self.tools.search(query))
                if "web_search" not in tools_used:
                    tools_used.append("web_search")
            except ToolError as exc:
                errors.append(str(exc))
                break

        sources = self._normalize_sources(records)
        if sources:
            try:
                extracted = self.tools.extract([source.url for source in sources])
                if extracted:
                    tools_used.append("source_extract")
                    sources = [
                        source.model_copy(
                            update={
                                "evidence": extracted.get(
                                    source.url, source.evidence
                                )[:1800],
                                "fetched": source.url in extracted,
                            }
                        )
                        for source in sources
                    ]
            except ToolError as exc:
                errors.append(str(exc))

        if not sources:
            return ResearchAnswer(
                status="failed",
                question=question,
                short_answer="I could not retrieve usable sources, so I cannot provide a reliable research answer.",
                confidence="low",
                confidence_rationale="No usable source evidence was retrieved.",
                limitations=["The research tools did not return usable evidence."],
                suggested_next_steps=[
                    "Check tool credentials and provider availability, then retry."
                ],
                plan=plan,
                tools_used=tools_used,
                errors=errors or ["No sources passed relevance and validity checks."],
            )

        try:
            answer = self.synthesizer.synthesize(
                question, plan, sources, tools_used, errors
            )
            if errors and answer.status == "complete":
                answer.status = "partial"
            answer.errors = list(dict.fromkeys([*answer.errors, *errors]))
            if errors and not answer.limitations:
                answer.limitations = ["One or more research tools failed."]
            return answer
        except SynthesisError as exc:
            errors.append(str(exc))
            return ResearchAnswer(
                status="partial",
                question=question,
                short_answer="Sources were retrieved, but synthesis failed. Review the evidence before drawing conclusions.",
                sources_used=sources,
                confidence="low",
                confidence_rationale="No validated synthesis was produced.",
                limitations=[
                    "This response contains retrieved excerpts only; it is not a synthesized answer."
                ],
                suggested_next_steps=[
                    "Retry synthesis or review the linked source material manually."
                ],
                plan=plan,
                tools_used=tools_used,
                errors=errors,
            )

    @staticmethod
    def _normalize_sources(records: list[dict[str, object]]) -> list[Source]:
        sources: list[Source] = []
        seen: set[str] = set()
        for record in records:
            title, url, evidence = (
                record.get("title"),
                record.get("url"),
                record.get("evidence"),
            )
            if not all(isinstance(value, str) for value in (title, url, evidence)):
                continue
            clean_url = url.split("#", 1)[0].rstrip("/")
            parsed_url = urlparse(clean_url)
            if (
                not title.strip()
                or clean_url in seen
                or len(evidence.strip()) < 30
                or parsed_url.scheme not in {"http", "https"}
                or not parsed_url.hostname
            ):
                continue
            seen.add(clean_url)
            publisher = record.get("publisher")
            if not isinstance(publisher, str) or not publisher:
                publisher = parsed_url.hostname
            sources.append(
                Source(
                    id=f"S{len(sources) + 1}",
                    title=title.strip()[:240],
                    url=clean_url,
                    publisher=publisher,
                    evidence=evidence.strip()[:1800],
                    fetched=bool(record.get("fetched", False)),
                )
            )
            if len(sources) >= 8:
                break
        return sources
