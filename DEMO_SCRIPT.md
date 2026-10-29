# Demo recording script (3–5 minutes)

The actual video should be recorded by the submitter; this file is a reproducible walkthrough, not a recording.

## 0:00–0:40 — Explain the workflow

Show the repository and describe the bounded flow: rule-based plan, Tavily search and extract, evidence filtering, Groq synthesis, Pydantic validation. Note that the offline demo uses fixtures and is not live research.

## 0:40–2:20 — Happy path

For a reproducible offline run:

```powershell
python -m research_agent "Compare Chroma and Qdrant for an early RAG prototype" --demo --pretty
```

Point out the original question, visible plan/tool selection, cited findings, source list, confidence rationale, limitations, and `complete` status. Explain that this run validates output wiring, not live-source freshness.

If live credentials are configured, additionally run:

```powershell
python -m research_agent "Compare the top 3 open-source vector databases for a startup building RAG products." --pretty --verbose
```

Show the `plan`, `tools_used`, source evidence, and request diagnostics. Avoid displaying secrets.

## 2:20–3:20 — Failure case

Run:

```powershell
python -m research_agent "Compare Chroma and Qdrant for an early RAG prototype" --demo-failure --pretty
```

Explain that it simulates a search timeout, returns an explicit `failed` status and error instead of inventing sources, and exits nonzero. The shell's exit code is `1` for `partial`/`failed` and `2` for invalid setup/input.

## 3:20–4:30 — Tests and tradeoffs

Run `python -m pytest`. Briefly mention deterministic offline tests, no automatic model-output repair, bounded calls, and remaining production work: live source-quality evaluation, citation entailment, quotas, secret management, and monitoring.
