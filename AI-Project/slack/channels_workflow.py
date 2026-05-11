"""
channels_workflow.py
--------------------
Streamlit workflow for listing and browsing Slack channels and DMs.
Analogous to email_send/inbox_workflow.py.

Future work:
  - List public / private channels
  - Show recent messages per channel
  - Join / leave channel actions
"""

import streamlit as st
from slack.slack_handler import is_slack_authenticated


def render_channels_workflow():
    """Render the 'Channels' tab inside the Slack view."""
    st.header("📋 Slack Channels")

    if not is_slack_authenticated():
        st.warning("⚠️ Connect your Slack workspace first via the **Settings** tab.")
        return

    # TODO: implement channel listing UI
    st.info("🚧 Channels workflow coming soon.")
