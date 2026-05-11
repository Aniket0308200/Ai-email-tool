"""
delete_workflow.py
------------------
Streamlit workflow for deleting Slack messages.
Analogous to email_send/delete_workflow.py.

Future work:
  - List messages sent by the bot/user
  - Bulk delete with confirmation
  - Delete via Slack Web API (chat.delete)
"""

import streamlit as st
from slack.slack_handler import is_slack_authenticated


def render_delete_workflow():
    """Render the 'Delete' tab inside the Slack view."""
    st.header("🗑️ Delete Slack Messages")

    if not is_slack_authenticated():
        st.warning("⚠️ Connect your Slack workspace first via the **Settings** tab.")
        return

    # TODO: implement delete UI
    st.info("🚧 Delete workflow coming soon.")
