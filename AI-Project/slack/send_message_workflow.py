"""
send_message_workflow.py
------------------------
Streamlit workflow for composing and sending Slack messages.
"""

import streamlit as st
from slack.slack_handler import (
    is_slack_authenticated,
    fetch_channels,
    fetch_users,
    send_slack_message
)

def render_send_message_workflow():
    """Render the 'Send Message' tab inside the Slack view."""
    st.header("📨 Send Slack Message")

    if not is_slack_authenticated():
        st.warning("⚠️ Connect your Slack workspace first via the **Settings** tab.")
        return

    # Cache channels and users to avoid hitting the API repeatedly
    if "slack_channels" not in st.session_state:
        with st.spinner("Loading Slack workspace data..."):
            st.session_state.slack_channels = fetch_channels()
            st.session_state.slack_users = fetch_users()

    channels = st.session_state.slack_channels
    users = st.session_state.slack_users

    col1, col2 = st.columns([2, 1])

    with col1:
        dest_type = st.radio("Send to:", ["Channel", "Direct Message"], horizontal=True)
        
        selected_dest_id = None
        if dest_type == "Channel":
            if channels:
                channel_options = {f"#{c['name']}": c["id"] for c in channels}
                selected_name = st.selectbox("Select Channel", options=list(channel_options.keys()))
                selected_dest_id = channel_options[selected_name]
            else:
                st.info("No channels found. (Make sure your bot is invited to channels)")
        else:
            if users:
                user_options = {u["name"]: u["id"] for u in users}
                selected_name = st.selectbox("Select User", options=list(user_options.keys()))
                selected_dest_id = user_options[selected_name]
            else:
                st.info("No users found.")

        st.markdown("**Message**")
        
        if "slack_msg_key" not in st.session_state:
            st.session_state.slack_msg_key = 0
            
        message_text = st.text_area(
            "Type your message here...", 
            height=150, 
            label_visibility="collapsed",
            key=f"slack_message_input_{st.session_state.slack_msg_key}"
        )
        
        if st.button("📤 Send Message", use_container_width=True):
            if not selected_dest_id:
                st.error("Please select a destination.")
            elif not message_text.strip():
                st.error("Message cannot be empty.")
            else:
                with st.spinner("Sending message..."):
                    result = send_slack_message(selected_dest_id, message_text)
                    if result["success"]:
                        st.success("✅ Message sent successfully!")
                        st.session_state.slack_msg_key += 1
                        st.rerun()
                    else:
                        error_msg = result.get("error", "Unknown error")
                        st.error(f"❌ Failed to send message")
                        # Show each line of the error as a separate info block
                        for line in error_msg.split("\n"):
                            line = line.strip()
                            if line:
                                if line.startswith("Option"):
                                    st.info(f"💡 {line}")
                                else:
                                    st.warning(line)

    with col2:
        st.subheader("Data Refresh")
        st.caption("If you recently added a channel or user, refresh the list.")
        if st.button("🔄 Refresh Data", use_container_width=True):
            del st.session_state["slack_channels"]
            del st.session_state["slack_users"]
            st.rerun()
