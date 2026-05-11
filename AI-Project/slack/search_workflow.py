"""
search_workflow.py
------------------
Streamlit workflow for searching messages across Slack channels.
Analogous to email_send/search_workflow.py.

Future work:
  - Full-text message search via Slack Search API
  - Filter by channel, user, date range
  - AI-powered semantic search
"""

import streamlit as st
from slack.slack_handler import is_slack_authenticated


def render_search_workflow():
    """Render the 'Search' tab inside the Slack view."""
    st.header("🔍 Search Slack Messages")

    if not is_slack_authenticated():
        st.warning("⚠️ Connect your Slack workspace first via the **Settings** tab.")
        return

    # TODO: implement search UI
    st.info("🚧 Search workflow coming soon.")
