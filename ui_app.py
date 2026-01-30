"""
Streamlit-based web UI for the AI Research System.

Run with:
    streamlit run ui_app.py
"""

import time
from typing import Optional

import requests
import streamlit as st

from src.ai_research_system.config import settings


API_BASE = settings.api_base_url


def start_task(
    phone_number: Optional[str],
    identifier: Optional[str],
    cve: Optional[str],
    keyword: Optional[str],
) -> str:
    resp = requests.post(
        f"{API_BASE}/agent/start",
        json={
            "phone_number": phone_number or None,
            "identifier": identifier or None,
            "cve": cve or None,
            "keyword": keyword or None,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["task_id"]


def get_status(task_id: str) -> dict:
    resp = requests.get(f"{API_BASE}/agent/status/{task_id}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    st.set_page_config(page_title="AI Research System", layout="wide")

    st.title("AI Research System – Cybersecurity & OSINT Agent")
    st.write(
        "This single-agent system uses an MCP-style server for real-time web search, "
        "scraping, and analysis. Provide one or more fields below to start an automated investigation."
    )

    with st.form("query_form"):
        col1, col2 = st.columns(2)
        with col1:
            phone = st.text_input("Phone number", help="e.g., +1-555-123-4567")
            identifier = st.text_input("ID", help="Any identifier (user ID, handle, etc.)")
        with col2:
            cve = st.text_input("CVE", help="e.g., CVE-2023-12345")
            keyword = st.text_input("Keyword", help="e.g., malware family, tool name")

        submitted = st.form_submit_button("Run Investigation")

    status_container = st.container()
    results_container = st.container()

    if submitted:
        with status_container:
            st.info("Starting investigation via agent...")
        try:
            task_id = start_task(phone, identifier, cve, keyword)
        except Exception as exc:  # pylint: disable=broad-except
            st.error(f"Failed to start agent task: {exc}")
            return

        # Poll for status updates and display progress in near–real-time
        progress_bar = status_container.progress(0, text="Agent is running...")
        log_box = status_container.empty()

        final_status: Optional[dict] = None
        for i in range(100):
            time.sleep(1.0)
            try:
                status = get_status(task_id)
            except Exception as exc:  # pylint: disable=broad-except
                st.error(f"Error while fetching status: {exc}")
                break

            final_status = status
            pct = min(99, i + 1)
            progress_bar.progress(pct, text=f"Status: {status['status']}")
            log_text = "\n".join(status.get("progress_log", [])) or "Waiting for agent updates..."
            log_box.code(log_text, language="text")

            if status["status"] in {"completed", "error"}:
                break

        progress_bar.progress(100, text=f"Final status: {final_status['status'] if final_status else 'unknown'}")

        with results_container:
            st.subheader("Findings")
            if not final_status:
                st.warning("No final status available.")
                return

            if final_status["status"] == "error":
                st.error(f"Agent encountered an error: {final_status.get('error_message')}")
                return

            findings = final_status.get("findings", [])
            if not findings:
                st.info("No findings were produced for this query.")
                return

            for f in findings:
                with st.expander(f"{f['website_name']} – {f['date_found']}"):
                    st.markdown(f"**Website name:** {f['website_name']}")
                    st.markdown(f"**Date found:** {f['date_found']}")
                    st.markdown(f"**Source link:** [{f['source_link']}]({f['source_link']})")
                    st.markdown("**Summary:**")
                    st.write(f["summary"])


if __name__ == "__main__":
    main()


