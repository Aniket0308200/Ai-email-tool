"""
send_message_workflow.py
------------------------
Streamlit workflow for composing and sending Slack messages.
Analogous to email_send/send_email_workflow.py.

Future work:
  - Channel / DM selector
  - AI-assisted message composer
  - Tone selector (professional, casual, urgent, …)
  - Send via Slack Web API
"""

import streamlit as st
from slack.slack_handler import is_slack_authenticated


def render_send_message_workflow():
    """Render the 'Send Message' tab inside the Slack view."""
    st.header("📨 Send Slack Message")

    if not is_slack_authenticated():
        st.warning("⚠️ Connect your Slack workspace first via the **Settings** tab.")
        return

    # TODO: implement full send-message UI
    st.info("🚧 Send Message workflow coming soon.")
