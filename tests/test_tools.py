from __future__ import annotations

import httpx

from research_agent.tools import TavilyTools


def test_search_filters_weak_malformed_private_and_duplicate_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Useful",
                        "url": "https://example.com/page#top",
                        "content": "This is a sufficiently long useful result snippet.",
                        "score": 0.9,
                    },
                    {
                        "title": "Duplicate",
                        "url": "https://example.com/page",
                        "content": "This is another sufficiently long useful result.",
                        "score": 0.8,
                    },
                    {
                        "title": "Weak",
                        "url": "https://weak.example/page",
                        "content": "This is a sufficiently long weak result snippet.",
                        "score": 0.01,
                    },
                    {
                        "title": "Private",
                        "url": "http://127.0.0.1/private",
                        "content": "This is a sufficiently long private result.",
                        "score": 0.9,
                    },
                    {"url": "https://example.net/malformed"},
                ]
            },
        )

    tools = TavilyTools(
        "test-key",
        transport=httpx.MockTransport(handler),
        sleeper=lambda _: None,
    )
    try:
        sources = tools.search("example query")
    finally:
        tools.close()

    assert len(sources) == 1
    assert sources[0]["url"] == "https://example.com/page"
    assert sources[0]["publisher"] == "example.com"


def test_transient_server_error_is_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": "temporarily unavailable"})
        return httpx.Response(200, json={"results": []})

    tools = TavilyTools(
        "test-key",
        max_retries=1,
        transport=httpx.MockTransport(handler),
        sleeper=lambda _: None,
    )
    try:
        assert tools.search("example query") == []
    finally:
        tools.close()

    assert calls == 2
