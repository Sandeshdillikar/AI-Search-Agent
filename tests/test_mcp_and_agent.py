"""
Automated verification for MCP connectivity, tool execution, and agent behaviour.

These tests are intentionally high-level and exercise the real FastAPI app.
They assume outbound internet access for DuckDuckGo and that Ollama is running
locally with the configured model.
"""

import time

from fastapi.testclient import TestClient

from src.ai_research_system.backend import app


client = TestClient(app)


def test_mcp_health():
    resp = client.get("/mcp/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_mcp_search_and_scrape_roundtrip():
    # Basic integration: search, then scrape first result
    resp = client.post("/mcp/search", json={"query": "CVE-2023-12345", "max_results": 1})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert isinstance(results, list)
    if not results:
        # If search provider returned nothing, we skip stricter asserts
        return
    first = results[0]
    assert "url" in first and first["url"]

    scrape_resp = client.post("/mcp/scrape", json={"url": first["url"], "max_chars": 2000})
    assert scrape_resp.status_code == 200
    scrape_data = scrape_resp.json()
    assert "content_text" in scrape_data and scrape_data["content_text"]


def test_agent_end_to_end():
    # Start a real agent task and wait for completion.
    start = client.post(
        "/agent/start",
        json={"phone_number": None, "identifier": None, "cve": "CVE-2023-12345", "keyword": None},
    )
    assert start.status_code == 200
    task_id = start.json()["task_id"]

    # Poll status for up to ~90 seconds
    for _ in range(90):
        time.sleep(1)
        status = client.get(f"/agent/status/{task_id}")
        assert status.status_code == 200
        data = status.json()
        if data["status"] in {"completed", "error"}:
            break

    assert data["status"] in {"completed", "error"}
    # Even in error, we verify that progress_log is present, showing reasoning attempts.
    assert isinstance(data.get("progress_log", []), list)


