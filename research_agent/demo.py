from __future__ import annotations

from research_agent.agent import ResearchAgent
from research_agent.models import Finding, ResearchAnswer, ResearchPlan, Source


class DemoTools:
    """Offline fixtures; results are illustrative and are not live-verified."""

    def __init__(self, fail_search: bool = False) -> None:
        self.fail_search = fail_search

    def search(self, query: str) -> list[dict[str, object]]:
        if self.fail_search:
            from research_agent.tools import ToolError

            raise ToolError("Demo search failure: simulated provider timeout.")
        return [
            {
                "title": "Chroma documentation",
                "url": "https://docs.trychroma.com/",
                "publisher": "trychroma.com",
                "evidence": "Chroma is an open-source embedding database designed for AI applications and retrieval workflows.",
                "fetched": False,
            },
            {
                "title": "Qdrant documentation",
                "url": "https://qdrant.tech/documentation/",
                "publisher": "qdrant.tech",
                "evidence": "Qdrant is an open-source vector search engine and vector database, with documentation for filtering and deployment.",
                "fetched": False,
            },
        ]

    def extract(self, urls: list[str]) -> dict[str, str]:
        return {}


class DemoSynthesizer:
    def synthesize(
        self,
        question: str,
        plan: ResearchPlan,
        sources: list[Source],
        tools_used: list[str],
        errors: list[str],
    ) -> ResearchAnswer:
        by_title = {source.title: source for source in sources}
        chroma = by_title["Chroma documentation"]
        qdrant = by_title["Qdrant documentation"]
        return ResearchAnswer(
            status="complete",
            question=question,
            short_answer="Both are open-source options for RAG prototypes; validate operational and filtering needs against the current documentation before choosing.",
            key_findings=[
                Finding(
                    text="Chroma positions itself as an embedding database for AI application and retrieval workflows.",
                    source_ids=[chroma.id],
                ),
                Finding(
                    text="Qdrant positions itself as a vector search engine/database and documents filtering and deployment options.",
                    source_ids=[qdrant.id],
                ),
            ],
            sources_used=sources,
            confidence="low",
            confidence_rationale="Offline demo fixtures illustrate the output format and have not been checked against live pages.",
            assumptions=["The comparison is an initial shortlist for a prototype, not a production benchmark."],
            limitations=["Demo mode uses static fixtures; it does not perform live search or page extraction."],
            suggested_next_steps=["Compare current deployment, filtering, scaling, and operational requirements using live vendor documentation."],
            plan=plan,
            tools_used=tools_used,
            errors=errors,
        )


def build_demo_agent(fail_search: bool = False) -> ResearchAgent:
    return ResearchAgent(DemoTools(fail_search=fail_search), DemoSynthesizer())
