"""
settings_workflow.py
--------------------
Streamlit workflow for Slack settings: authentication, workspace config, etc.
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
        
        with st.expander("📖 Setup Instructions", expanded=True):
            st.markdown("""
            **Step 1: Create a Slack App**
            1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
            2. Name it (e.g., "AI Assistant") and select your workspace
            
            **Step 2: Add User Token Scopes**
            Since we are using a **User Token Workflow**, go to **OAuth & Permissions** → **Scopes** → **User Token Scopes**, add:
            - `chat:write` — Send messages as you
            - `channels:read` — View public channels
            - `groups:read` — View private channels
            - `users:read` — View workspace users
            - `im:read` — Read DMs (optional)
            - `mpim:read` — Read Group DMs (optional)
            
            **Step 3: Install App to Workspace**
            - Click **Install to Workspace** → **Allow**
            - Copy the **User OAuth Token** (starts with `xoxp-`)
            
            **Step 4: Paste Token Below**
            """)
        
        with st.form("slack_auth_form"):
            token_input = st.text_input(
                "Slack User OAuth Token (xoxp-...)", 
                type="password",
                placeholder="xoxp-..."
            )
            submit = st.form_submit_button("🔗 Connect Slack Workspace", use_container_width=True)
            
            if submit:
                # We also support xoxb- just in case, but prefer xoxp-
                if token_input.startswith("xoxp-") or token_input.startswith("xoxb-"):
                    try:
                        with st.spinner("Connecting to Slack…"):
                            if authenticate_slack(token_input):
                                st.success("✅ Slack connected successfully!")
                                st.rerun()
                            else:
                                st.error("❌ Failed to authenticate. Please check your token.")
                    except Exception as e:
                        st.error(f"❌ {str(e)}")
                else:
                    st.error("Token should start with 'xoxp-'. Please check your Slack app dashboard.")

    st.divider()
    st.subheader("ℹ️ About")
    st.markdown(
        "Slack integration is powered by the "
        "[Slack Web API](https://api.slack.com/web). "
        "Your Bot Token is stored locally in `slack_credentials.json`."
    )
