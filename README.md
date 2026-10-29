# Production-Oriented AI Research Agent

A small Python CLI that plans a bounded research workflow, chooses web tools, filters source results, and returns a validated, cited answer. It is intentionally a single-agent system: research tasks benefit from explicit orchestration and bounded tool access more than an opaque multi-agent framework.

## What it does

1. Accepts one research question (up to 1,000 characters).
2. Classifies the request as a comparison, list, pros/cons question, or overview; creates a visible plan with up to two searches.
3. Uses two read-only tools: Tavily web search and Tavily page extraction.
4. Deduplicates sources and filters malformed, very weak, short, or private-network URL results.
5. Synthesizes from retrieved evidence with a Groq-hosted model, requiring citations by source ID and a fixed JSON schema.
6. Validates output and downgrades incomplete runs to `partial` or `failed`, with explicit errors and limitations.

## Architecture

```text
Question
   |
   v
Rule-based planner -----> ResearchPlan (intent, bounded queries, selected tools)
   |                                      |
   v                                      v
Tavily search ----------------------> Candidate source filtering
                                              |
                                              v
                                   Tavily source extraction
                                              |
                                              v
                                  Groq evidence-grounded synthesis
                                              |
                                              v
                                Pydantic validation and JSON output
```

### Why an agentic approach?

The workflow has multiple purposeful steps: plan what evidence is needed, choose tools, retrieve and filter sources, then synthesize. Keeping this orchestration explicit makes tool selection, failures, and output inspectable. A fully autonomous planner or multi-agent design would add cost and variability without clear value for the bounded use case.

### Tools and choices

- **Tavily search** discovers candidate sources for planned queries.
- **Tavily extract** retrieves content from a capped number of distinct results. Using provider-side extraction avoids directly fetching arbitrary URLs from the application.
- **Groq chat completions** synthesizes a structured answer. The model does not control tool execution.
- **Pydantic** validates the plan, source records, final answer, and citation IDs.

The planner is deterministic and intentionally simple; it does not use a model call. Tool choice is explicit and visible in `plan.selected_tools`, while `tools_used` reports tools that actually succeeded in that run.

## Response shape

The CLI emits a single JSON object with:

- `question`, `short_answer`, and `key_findings` (each finding includes source IDs)
- `sources_used` (IDs, titles, URLs, publisher, evidence excerpt, and extraction flag)
- `confidence` and `confidence_rationale`
- `assumptions`, `limitations`, and `suggested_next_steps`
- `plan`, `tools_used`, `status`, and `errors`

Successful answers use `status: "complete"`. A run with tool errors or an incomplete synthesis is `partial`; no usable evidence means `failed`. Partial and failed runs exit with status code `1`; invalid configuration or input exits with `2`.

## Requirements and setup

- Python 3.11+
- Groq API key
- Tavily API key

From the project directory in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Set `GROQ_API_KEY` and `TAVILY_API_KEY` in `.env`. `.env` is ignored by git. The default Groq model is `llama-3.3-70b-versatile`; override it with `GROQ_MODEL` if needed. Other optional settings are `REQUEST_TIMEOUT_SECONDS`, `MAX_SEARCH_RESULTS`, and `MAX_EXTRACT_SOURCES`.

### Run a live research query

```powershell
python -m research_agent "Compare the top 3 open-source vector databases for a startup building RAG products." --pretty
```

The installed console command is also available:

```powershell
research-agent "Compare memory approaches for an AI support agent" --pretty
```

Verbose diagnostics go to stderr, leaving JSON on stdout:

```powershell
python -m research_agent "Find Indian B2B SaaS startups in HR tech" --verbose
```

## Offline demo

The offline demo needs no API keys or network access and uses fixed illustrative fixtures (not live-verified research):

```powershell
python -m research_agent "Compare Chroma and Qdrant for an early RAG prototype" --demo --pretty
python -m research_agent "Compare Chroma and Qdrant for an early RAG prototype" --demo-failure --pretty
```

The second command simulates a search timeout. It should emit a structured `failed` answer, disclose the error, and return a nonzero status. Two captured examples are in [`samples/`](samples/).

## Reliability and safety

- **Timeouts/retries:** HTTP calls have configurable timeouts. Tavily retries timeouts, network errors, HTTP 429, and server errors with bounded exponential backoff; other HTTP failures are surfaced. Groq SDK retries are bounded.
- **Malformed tool results:** validate top-level response shape; skip individual malformed records; deduplicate URLs; cap query, result, extract, source, and excerpt sizes. If nothing usable remains, return a failure rather than fabricate an answer.
- **Weak sources:** discard results with low provider relevance scores (below 0.15), short snippets, malformed fields, duplicate URLs, or non-public URL literals. Search results without a numeric score are retained if other checks pass.
- **Hallucination controls:** send retrieved evidence to synthesis as data; require source IDs for factual findings; validate citations against supplied IDs; preserve raw evidence in the output; do not make a validated synthesis failure look successful.
- **Prompt injection:** retrieved text is explicitly treated as untrusted evidence, never as instructions. The model cannot invoke tools. Extraction occurs via Tavily rather than direct application requests to search-result URLs.
- **Output reliability:** Pydantic validates required fields, status values, and citation references. There is no automatic free-form repair loop; invalid model output is reported as a partial result with original retrieved evidence.
- **Observability:** `--verbose` logs a per-run request ID, status, successful tools, source count, and error count to stderr. Do not log credentials or full retrieved pages.
- **Cost/latency:** at most two search queries and four extracted URLs by default; no separate judge call. Increase limits only when evaluation shows a measurable quality benefit.

This is a focused take-home implementation, not a fully hardened deployment. Public hostname DNS resolution is delegated to Tavily, and network-egress controls, rate limiting, persistent traces, secret management, and provider cost quotas still need deployment-level enforcement.

## Testing

Run the unit tests offline:

```powershell
python -m pytest
```

Tests cover planner bounds and intent, source deduplication and extraction, failures in search/extraction/synthesis, schema citation checks, untrusted-source prompt requirements, malformed/weak/private URL filtering, and a transient HTTP retry.

## Evaluation and submission materials

- [`EVALUATION.md`](EVALUATION.md) lists six reproducible cases, expected behavior, metrics, and current evaluation status.
- [`samples/`](samples/) contains a successful offline output and a simulated tool-failure output.
- [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) provides a short recording walkthrough for the requested 3–5 minute demo.

Offline examples and passing unit tests demonstrate orchestration behavior only. They are not evidence of live search relevance, citation entailment, or answer quality. Run and record the evaluation against configured live providers before making those claims.

## Limitations and production next steps

- The planner uses simple keyword rules; ambiguous or compound requests can be poorly decomposed.
- Live tool execution requires network access and Groq/Tavily credentials. The offline demo is not live research.
- Citation IDs are structurally checked, but claim-to-source entailment is not automatically proven.
- Tavily's snippets and extracted text may be stale, incomplete, or biased; source credibility currently is not independently scored.
- The model response is validated but not automatically retried after a schema failure; failed synthesis retains evidence for review.
- Add quality checks for citation entailment and source credibility, provider quotas, network egress controls, API-key secret management, redacted tracing, retention controls, and monitoring/alerts before production use.
