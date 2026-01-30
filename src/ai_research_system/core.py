"""
Core functionality for the AI Research System.

Right now this just provides a tiny placeholder function that
pretends to "summarize" a research query. Replace or extend this
with your actual logic.
"""

from datetime import datetime


def summarize_query(query: str) -> str:
    """
    Return a simple, human-readable summary of a research query.

    Parameters
    ----------
    query:
        A free-form text description of what you're researching.
    """
    query = (query or "").strip()
    if not query:
        return "No query provided. Please describe what you want to research."

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"[{timestamp}] You are exploring the following research topic:\n"
        f"- {query}\n\n"
        "Next steps (suggested):\n"
        "- Identify 3–5 key sub-questions.\n"
        "- Collect relevant papers or articles.\n"
        "- Take structured notes and track findings."
    )


if __name__ == "__main__":
    # Small manual test if you run this file directly
    print(summarize_query("Example: how to evaluate large language models efficiently?"))


