from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: Literal["comparison", "list", "pros_cons", "overview"]
    search_queries: list[str] = Field(min_length=1, max_length=3)
    steps: list[str] = Field(min_length=3, max_length=5)
    selected_tools: list[Literal["web_search", "source_extract"]]


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    url: str
    publisher: str
    evidence: str = Field(max_length=1800)
    fetched: bool = False


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    source_ids: list[str] = Field(default_factory=list)


class ResearchAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["complete", "partial", "failed"]
    question: str
    short_answer: str
    key_findings: list[Finding] = Field(default_factory=list)
    sources_used: list[Source] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]
    confidence_rationale: str
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    suggested_next_steps: list[str] = Field(default_factory=list)
    plan: ResearchPlan
    tools_used: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def citations_must_reference_sources(self) -> ResearchAnswer:
        source_ids = {source.id for source in self.sources_used}
        unknown = {
            source_id
            for finding in self.key_findings
            for source_id in finding.source_ids
            if source_id not in source_ids
        }
        if unknown:
            raise ValueError(f"Findings cite unknown source IDs: {sorted(unknown)}")
        if any(not finding.source_ids for finding in self.key_findings):
            raise ValueError("Every finding must cite at least one source")
        if self.status == "complete" and (
            not self.sources_used
            or not self.key_findings
        ):
            raise ValueError(
                "A complete answer must include cited findings and at least one source"
            )
        return self
