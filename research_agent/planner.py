from __future__ import annotations

from research_agent.models import ResearchPlan


def create_plan(question: str) -> ResearchPlan:
    """Create a small, inspectable plan and choose tools from the request intent."""
    lowered = question.casefold()
    if any(word in lowered for word in ("compare", "versus", " vs ", "which is better")):
        task_type = "comparison"
        search_queries = [
            f"{question} official documentation comparison",
            f"{question} independent review tradeoffs",
        ]
    elif any(word in lowered for word in ("pros and cons", "advantages and disadvantages")):
        task_type = "pros_cons"
        search_queries = [f"{question} evidence", f"{question} practical limitations"]
    elif any(word in lowered for word in ("find ", "list ", "top ", "how many")):
        task_type = "list"
        search_queries = [question, f"{question} official company or product sources"]
    else:
        task_type = "overview"
        search_queries = [question, f"{question} authoritative sources"]

    return ResearchPlan(
        task_type=task_type,
        search_queries=search_queries[:2],
        steps=[
            "Search the web for relevant primary and corroborating sources.",
            "Extract content from the strongest distinct results and filter weak evidence.",
            "Synthesize a cited answer and validate its structure and citations.",
        ],
        selected_tools=["web_search", "source_extract"],
    )
