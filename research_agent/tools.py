from __future__ import annotations

import ipaddress
import time
from collections.abc import Callable
from urllib.parse import urlparse

import httpx


class ToolError(RuntimeError):
    """A research tool failed or returned unusable data."""


def _is_public_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        host = parsed.hostname.rstrip(".").casefold()
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
            return False
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return "." in host
        return address.is_global
    except ValueError:
        return False


class TavilyTools:
    """Read-only web search and page extraction through Tavily's API."""

    def __init__(
        self,
        api_key: str,
        timeout: float = 15,
        max_results: int = 6,
        max_extract_sources: int = 4,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("TAVILY_API_KEY is required for live research")
        self.api_key = api_key
        self.max_results = max_results
        self.max_extract_sources = max_extract_sources
        self.max_retries = max_retries
        self.sleeper = sleeper
        self.client = httpx.Client(
            base_url="https://api.tavily.com",
            timeout=httpx.Timeout(timeout),
            transport=transport,
            follow_redirects=False,
        )

    def close(self) -> None:
        self.client.close()

    def _post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.post(
                    path, json={**payload, "api_key": self.api_key}
                )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self.max_retries:
                        self.sleeper(0.2 * (2**attempt))
                        continue
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ToolError(f"Tavily {path} returned a non-object response")
                return data
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt < self.max_retries:
                    self.sleeper(0.2 * (2**attempt))
                    continue
                raise ToolError(f"Tavily {path} request failed: {exc}") from exc
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                raise ToolError(f"Tavily {path} returned HTTP {status}") from exc
            except ValueError as exc:
                raise ToolError(f"Tavily {path} returned malformed JSON") from exc
        raise ToolError(f"Tavily {path} failed after retries")

    def search(self, query: str) -> list[dict[str, object]]:
        data = self._post(
            "/search",
            {
                "query": query,
                "max_results": self.max_results,
                "search_depth": "basic",
                "include_answer": False,
            },
        )
        results = data.get("results")
        if not isinstance(results, list):
            raise ToolError("Tavily search response is missing its results list")
        sources: list[dict[str, object]] = []
        seen_urls: set[str] = set()
        for item in results:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            title = item.get("title")
            content = item.get("content")
            score = item.get("score")
            if (
                not isinstance(url, str)
                or not _is_public_http_url(url)
                or not isinstance(title, str)
                or not title.strip()
                or not isinstance(content, str)
                or len(content.strip()) < 30
            ):
                continue
            if isinstance(score, (int, float)) and score < 0.15:
                continue
            canonical_url = url.split("#", 1)[0].rstrip("/")
            if canonical_url in seen_urls:
                continue
            seen_urls.add(canonical_url)
            host = urlparse(url).hostname or "unknown"
            sources.append(
                {
                    "title": title.strip()[:240],
                    "url": canonical_url,
                    "publisher": host.removeprefix("www."),
                    "evidence": content.strip()[:1800],
                    "fetched": False,
                }
            )
        return sources

    def extract(self, urls: list[str]) -> dict[str, str]:
        safe_urls = list(
            dict.fromkeys(url for url in urls if _is_public_http_url(url))
        )[: self.max_extract_sources]
        if not safe_urls:
            return {}
        data = self._post(
            "/extract", {"urls": safe_urls, "extract_depth": "basic"}
        )
        results = data.get("results")
        if not isinstance(results, list):
            raise ToolError("Tavily extract response is missing its results list")
        extracted: dict[str, str] = {}
        for item in results:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            content = item.get("raw_content")
            if isinstance(url, str) and isinstance(content, str) and content.strip():
                extracted[url.split("#", 1)[0].rstrip("/")] = content.strip()[:1800]
        return extracted
