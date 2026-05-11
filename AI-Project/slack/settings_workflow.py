"""
settings_workflow.py
--------------------
Streamlit workflow for Slack settings: authentication, workspace config, etc.
Analogous to the Settings tab in the Email section of app.py.

Future work:
  - Slack Bot Token / OAuth2 setup
  - Workspace info display
  - Notification preferences
"""

import streamlit as st
from slack.slack_handler import (
    is_slack_authenticated,
    get_authenticated_workspace,
    authenticate_slack,
    clear_authentication,
)


def render_settings_workflow():
    """Render the 'Settings' tab inside the Slack view."""
    st.header("⚙️ Slack Settings")

    st.subheader("🔐 Workspace Authentication")
    if is_slack_authenticated():
        workspace = get_authenticated_workspace()
        st.success(f"✅ Connected to workspace: **{workspace}**")
        if st.button("🔓 Disconnect Slack", key="disconnect_slack", use_container_width=True):
            if clear_authentication():
                st.success("✅ Slack disconnected.")
                st.rerun()
    else:
        st.info("Connect your Slack workspace to enable messaging features.")
        if st.button("🔗 Connect Slack Workspace", key="connect_slack", use_container_width=True):
            try:
                with st.spinner("Connecting to Slack…"):
                    authenticate_slack()
                    st.success("✅ Slack connected successfully!")
                    st.rerun()
            except NotImplementedError:
                st.warning("🚧 Slack authentication is not yet implemented.")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

    st.divider()
    st.subheader("ℹ️ About")
    st.markdown(
        "Slack integration is powered by the "
        "[Slack Web API](https://api.slack.com/web). "
        "Configure your Bot Token in the environment to get started."
    )
