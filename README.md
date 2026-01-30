## AI Research System – Single-Agent MCP-Based OSINT Platform

This project implements a **single autonomous AI agent** for cybersecurity research and OSINT that strictly uses an **MCP-style server** to perform real-time web search, scraping, and data extraction.

### High-level architecture

- **User → Web UI (Streamlit) → FastAPI backend → Single Agent → MCP Server → Web tools → Agent → UI**
- Exactly **one agent** (`ResearchAgent`) orchestrates:
  - DuckDuckGo-based web search (via MCP `/mcp/search`)
  - Website scraping using `requests` + `BeautifulSoup` (via `/mcp/scrape`)
  - Data extraction and summarisation using **Ollama** (`llama3` by default) (via `/mcp/extract`)
- The agent **never accesses the internet directly** – all external data flows through the MCP endpoints.

### Features

- **Input fields** (web UI):
  - Phone number
  - ID
  - CVE
  - Keyword
- **Output per finding**:
  - Website name
  - Date found
  - Source link
  - Summary
- **Real-time status** in the UI via polling of `/agent/status/{task_id}`:
  - Shows live progress log and task state (`pending`, `running`, `completed`, `error`).

### Requirements

- Python 3.10+
- [Ollama](https://ollama.com/) running locally with the `llama3` (or `mistral`) model pulled.
  - Example: `ollama pull llama3` then `ollama serve`

### Setup

1. **Create and activate a virtual environment (recommended)**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # on Windows PowerShell / CMD
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Ensure Ollama is running locally**

   - Start Ollama: `ollama serve`
   - Make sure the `llama3` (or `mistral`) model is available:
     - `ollama pull llama3`

### Running the system

1. **Start the FastAPI backend (includes MCP server)**

   ```bash
   python main.py
   ```

   This runs the API (including `/mcp/*` and `/agent/*`) on `http://localhost:8000`.

2. **Start the Streamlit web UI** (in a second terminal)

   ```bash
   streamlit run ui_app.py
   ```

3. **Use the UI**

   - Open the Streamlit URL in your browser (usually `http://localhost:8501`).
   - Fill in any combination of:
     - Phone number
     - ID
     - CVE
     - Keyword
   - Click **Run Investigation**.
   - Watch the **live progress log** and final **structured findings** table.

### Automated verification

Run the test suite to verify MCP connectivity, tool execution, and agent behaviour:

```bash
pytest
```

These tests will:

- Check MCP health (`/mcp/health`).
- Perform a real DuckDuckGo search and scrape roundtrip.
- Run an end-to-end agent task with a real CVE-style query and verify status and reasoning logs.

### Notes

- All browsing, searching, and scraping is routed via the MCP server implemented in `mcp_server.py` and exposed on `/mcp/*`.
- The agent is implemented in `agent.py` and interacts with MCP only via HTTP.
- The system is designed for **cybersecurity research, OSINT, and automated investigation**, overcoming traditional LLM browsing limitations by delegating all web access to the MCP tools.

