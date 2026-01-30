"""
Configuration utilities for the AI Research System.

Central place to configure:
- MCP server base URL (used by the agent)
- Search provider
- Ollama model and endpoint
"""

from pydantic import BaseModel


class Settings(BaseModel):
    # Base URL where the FastAPI app (and embedded MCP server) is running.
    api_base_url: str = "http://localhost:8000"

    # MCP-style server paths (relative to api_base_url)
    mcp_search_path: str = "/mcp/search"
    mcp_scrape_path: str = "/mcp/scrape"
    mcp_extract_path: str = "/mcp/extract"
    mcp_health_path: str = "/mcp/health"

    # Search configuration (DuckDuckGo)
    search_max_results: int = 5

    # Ollama configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"


settings = Settings()


