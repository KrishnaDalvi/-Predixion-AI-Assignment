from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from pathlib import Path

from research_agent.agent import ResearchAgent
from research_agent.demo import build_demo_agent
from research_agent.synthesizer import GroqSynthesizer
from research_agent.tools import TavilyTools

LOGGER = logging.getLogger("research_agent")


def _load_dotenv() -> None:
    path = Path(".env")
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research-agent",
        description="Research a question and return a source-grounded JSON answer.",
    )
    parser.add_argument("question", help="Research question (max 1000 characters)")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use deterministic offline fixtures; no credentials or network required",
    )
    parser.add_argument(
        "--demo-failure",
        action="store_true",
        help="Simulate a search-provider timeout and show explicit failure handling",
    )
    parser.add_argument("--pretty", action="store_true", help="Indent JSON output")
    parser.add_argument("--verbose", action="store_true", help="Log run diagnostics to stderr")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    request_id = str(uuid.uuid4())
    if args.demo or args.demo_failure:
        agent = build_demo_agent(fail_search=args.demo_failure)
        tools = None
    else:
        _load_dotenv()
        api_key = os.getenv("TAVILY_API_KEY", "")
        groq_key = os.getenv("GROQ_API_KEY", "")
        if not api_key or not groq_key:
            print(
                "Live mode requires TAVILY_API_KEY and GROQ_API_KEY. "
                "Use --demo for an offline example.",
                file=sys.stderr,
            )
            return 2
        try:
            timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))
            max_results = int(os.getenv("MAX_SEARCH_RESULTS", "6"))
            max_extract = int(os.getenv("MAX_EXTRACT_SOURCES", "4"))
            tools = TavilyTools(
                api_key=api_key,
                timeout=timeout,
                max_results=max_results,
                max_extract_sources=max_extract,
            )
            synthesizer = GroqSynthesizer(
                api_key=groq_key,
                model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                timeout=max(timeout, 30),
            )
            agent = ResearchAgent(tools, synthesizer)
        except (ValueError, TypeError) as exc:
            print(f"Invalid configuration: {exc}", file=sys.stderr)
            return 2

    try:
        answer = agent.run(args.question)
        LOGGER.info(
            "request_id=%s status=%s tools=%s sources=%d errors=%d",
            request_id,
            answer.status,
            answer.tools_used,
            len(answer.sources_used),
            len(answer.errors),
        )
        print(
            json.dumps(
                answer.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2 if args.pretty else None,
            )
        )
        return 0 if answer.status == "complete" else 1
    except ValueError as exc:
        print(f"Invalid question: {exc}", file=sys.stderr)
        return 2
    finally:
        if tools is not None:
            tools.close()
