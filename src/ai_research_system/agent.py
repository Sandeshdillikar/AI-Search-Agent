"""
Single autonomous research agent that communicates with the MCP server.

The agent:
- Receives a user query (phone, ID, CVE, keyword).
- Uses MCP tools for search, scraping, and extraction.
- Performs basic deduplication and sanity checks.
- Returns a structured report of findings.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx
from pydantic import BaseModel

from .config import settings


class QueryPayload(BaseModel):
    phone_number: Optional[str] = None
    identifier: Optional[str] = None
    cve: Optional[str] = None
    keyword: Optional[str] = None


class Finding(BaseModel):
    website_name: str
    date_found: str
    source_link: str
    summary: str


class AgentStatus(BaseModel):
    task_id: str
    status: str  # pending, running, completed, error
    progress_log: List[str] = []
    findings: List[Finding] = []
    error_message: Optional[str] = None


@dataclass
class InMemoryTaskStore:
    """Simple in-memory store for task status. Not for production use."""

    tasks: Dict[str, AgentStatus] = field(default_factory=dict)

    def create(self, task_id: str) -> AgentStatus:
        status = AgentStatus(task_id=task_id, status="pending", progress_log=[], findings=[])
        self.tasks[task_id] = status
        return status

    def get(self, task_id: str) -> Optional[AgentStatus]:
        return self.tasks.get(task_id)

    def update(self, task_id: str, **kwargs) -> AgentStatus:
        status = self.tasks[task_id]
        for key, value in kwargs.items():
            setattr(status, key, value)
        self.tasks[task_id] = status
        return status


task_store = InMemoryTaskStore()


class ResearchAgent:
    """
    The single autonomous agent that orchestrates the research process.

    It never accesses the internet directly; all external data comes
    from the MCP server via HTTP.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=60.0)

    async def _log(self, status: AgentStatus, message: str) -> None:
        status.progress_log.append(message)
        task_store.tasks[status.task_id] = status

    async def run_task(self, task_id: str, payload: QueryPayload) -> None:
        status = task_store.get(task_id)
        if status is None:
            status = task_store.create(task_id)
        status.status = "running"
        task_store.tasks[task_id] = status

        try:
            await self._log(status, "Preparing query from input fields.")
            query = self._build_query(payload)

            await self._log(status, f"Query constructed: {query!r}")

            await self._log(status, "Contacting MCP search tool.")
            search_results = await self._mcp_search(query)
            await self._log(
                status, f"MCP search returned {len(search_results)} candidate results."
            )

            all_findings: List[Finding] = []

            for idx, item in enumerate(search_results, start=1):
                url = item["url"]
                await self._log(status, f"[{idx}/{len(search_results)}] Scraping {url}")
                scraped = await self._mcp_scrape(url)

                await self._log(
                    status,
                    f"[{idx}/{len(search_results)}] Extracting relevant info via MCP extract tool.",
                )
                extracted = await self._mcp_extract(query, scraped["content_text"], url)

                for f in extracted:
                    all_findings.append(
                        Finding(
                            website_name=f["website_name"],
                            date_found=f["date_found"],
                            source_link=f["source_link"],
                            summary=f["summary"],
                        )
                    )

            unique = self._deduplicate_findings(all_findings)
            await self._log(status, f"Deduplicated to {len(unique)} unique findings.")

            status.findings = unique
            status.status = "completed"
            task_store.tasks[task_id] = status
        except Exception as exc:  # pylint: disable=broad-except
            status.status = "error"
            status.error_message = str(exc)
            task_store.tasks[task_id] = status

    def _build_query(self, payload: QueryPayload) -> str:
        parts: List[str] = []
        if payload.phone_number:
            parts.append(f"phone:{payload.phone_number}")
        if payload.identifier:
            parts.append(f"id:{payload.identifier}")
        if payload.cve:
            parts.append(f"CVE:{payload.cve}")
        if payload.keyword:
            parts.append(payload.keyword)
        return " ".join(parts) if parts else "cybersecurity osint"

    async def _mcp_search(self, query: str) -> List[dict]:
        url = f"{settings.api_base_url}{settings.mcp_search_path}"
        resp = await self._client.post(url, json={"query": query, "max_results": 5})
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])

    async def _mcp_scrape(self, url: str) -> dict:
        endpoint = f"{settings.api_base_url}{settings.mcp_scrape_path}"
        resp = await self._client.post(endpoint, json={"url": url, "max_chars": 6000})
        resp.raise_for_status()
        return resp.json()

    async def _mcp_extract(self, query: str, raw_text: str, source_url: str) -> List[dict]:
        endpoint = f"{settings.api_base_url}{settings.mcp_extract_path}"
        resp = await self._client.post(
            endpoint,
            json={"query": query, "raw_text": raw_text, "source_url": source_url},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("findings", [])

    def _deduplicate_findings(self, findings: List[Finding]) -> List[Finding]:
        seen_keys = set()
        unique: List[Finding] = []
        for f in findings:
            key = (f.website_name, f.source_link, f.summary[:80])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique.append(f)
        return unique


agent = ResearchAgent()


async def start_agent_task(task_id: str, payload: QueryPayload) -> None:
    """Helper to schedule agent work asynchronously."""
    await agent.run_task(task_id, payload)


def spawn_agent_task(task_id: str, payload: QueryPayload) -> None:
    """
    Fire-and-forget wrapper suitable for FastAPI background tasks.

    We avoid exposing any additional agents — this is just a convenience
    around the single `ResearchAgent` instance.
    """

    async def _runner() -> None:
        await start_agent_task(task_id, payload)

    asyncio.create_task(_runner())


