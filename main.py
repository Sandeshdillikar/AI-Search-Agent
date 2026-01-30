"""
Entry point to run the AI Research System backend with one command.

Usage:
    python main.py

Then, in a separate terminal:
    streamlit run ui_app.py

Alternatively, see README for combined startup options.
"""

import uvicorn

from src.ai_research_system.backend import app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


