"""
MCP-style server exposing tools for web search, scraping, and data extraction.

This module defines a FastAPI router that acts like a minimal MCP server.
The autonomous agent must call these HTTP endpoints instead of accessing
the internet directly.
"""

from datetime import datetime
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from .config import settings


router = APIRouter(prefix="/mcp", tags=["mcp"])


class MCPHealthResponse(BaseModel):
    status: str


@router.get("/health", response_model=MCPHealthResponse)
def mcp_health() -> MCPHealthResponse:
    """Simple connectivity check for MCP server."""
    return MCPHealthResponse(status="ok")


class SearchRequest(BaseModel):
    query: str
    max_results: int = settings.search_max_results


class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    snippet: str


class SearchResponse(BaseModel):
    results: List[SearchResult]


@router.post("/search", response_model=SearchResponse)
def mcp_search(payload: SearchRequest) -> SearchResponse:
    """
    Perform a web search using DuckDuckGo HTML results.

    This is intentionally simple and avoids any proprietary APIs.
    """
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    params = {"q": payload.query, "t": "h_", "ia": "web"}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(
            "https://duckduckgo.com/html", params=params, headers=headers, timeout=20
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Search request failed: {exc}") from exc

    soup = BeautifulSoup(resp.text, "html.parser")
    results: List[SearchResult] = []

    for a in soup.select("a.result__a"):
        title = a.get_text(strip=True)
        href = a.get("href")
        if not href:
            continue
        snippet_el = a.find_parent("div", class_="result")
        snippet_text = ""
        if snippet_el:
            snippet_span = snippet_el.select_one(".result__snippet")
            if snippet_span:
                snippet_text = snippet_span.get_text(" ", strip=True)

        try:
            result = SearchResult(title=title, url=href, snippet=snippet_text)
        except Exception:
            # Skip invalid URLs or parsing issues
            continue

        results.append(result)
        if len(results) >= payload.max_results:
            break

    return SearchResponse(results=results)


class ScrapeRequest(BaseModel):
    url: HttpUrl
    max_chars: int = 8000


class ScrapeResponse(BaseModel):
    url: HttpUrl
    content_text: str
    date_fetched: datetime


@router.post("/scrape", response_model=ScrapeResponse)
def mcp_scrape(payload: ScrapeRequest) -> ScrapeResponse:
    """Fetch and extract visible text from a webpage."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(str(payload.url), headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Scrape request failed: {exc}") from exc

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove script/style tags
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    if payload.max_chars and len(text) > payload.max_chars:
        text = text[: payload.max_chars]

    return ScrapeResponse(url=payload.url, content_text=text, date_fetched=datetime.utcnow())


class ExtractRequest(BaseModel):
    query: str
    raw_text: str
    source_url: Optional[HttpUrl] = None


class ExtractedFinding(BaseModel):
    website_name: str
    date_found: datetime
    source_link: HttpUrl
    summary: str


class ExtractResponse(BaseModel):
    findings: List[ExtractedFinding]


@router.post("/extract", response_model=ExtractResponse)
def mcp_extract(payload: ExtractRequest) -> ExtractResponse:
    """
    Use a local Ollama model to extract and summarise security-relevant
    findings from scraped text.

    NOTE: The model is instructed to rely only on the provided raw_text,
    not its own training data, to meet the requirement that external
    information comes from MCP tools.
    """
    if not payload.raw_text.strip():
        return ExtractResponse(findings=[])

    prompt = (
        "You are an assistant for cybersecurity OSINT research.\n"
        "You are given:\n"
        f"- A user query: {payload.query!r}\n"
        "- Raw text scraped from a single web page.\n\n"
        "TASK:\n"
        "1. ONLY use the scraped text as your source of information.\n"
        "2. Identify information relevant to the query (phone, ID, CVE, or keyword).\n"
        "3. Produce a short, factual summary (2–4 sentences) of what this page says that is relevant.\n"
        "4. Do NOT invent details that are not clearly supported by the text.\n"
        "5. If you find nothing relevant, answer: 'No clearly relevant information found on this page.'\n\n"
        "SCRAPED TEXT STARTS BELOW:\n"
        "-------------------------\n"
        f"{payload.raw_text}\n"
        "-------------------------\n"
    )

    try:
        resp = requests.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [
                    {"role": "system", "content": "You extract facts from provided text only."},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Ollama extract request failed: {exc}") from exc

    data = resp.json()
    try:
        # Non-streaming Ollama chat returns a single 'message'
        content = data["message"]["content"].strip()
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=502, detail=f"Unexpected Ollama response: {data}") from exc

    if (
        "no clearly relevant information" in content.lower()
        or "no relevant information" in content.lower()
    ):
        return ExtractResponse(findings=[])

    website_name = (
        payload.source_url.host if payload.source_url is not None else "unknown-source"
    )

    finding = ExtractedFinding(
        website_name=website_name,
        date_found=datetime.utcnow(),
        source_link=payload.source_url or "http://localhost/",
        summary=content,
    )

    return ExtractResponse(findings=[finding])


