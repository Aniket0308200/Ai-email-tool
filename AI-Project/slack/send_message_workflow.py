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
    send_slack_message,
    update_message,
    add_pin,
    add_star
)
import time

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

    channels_res = st.session_state.slack_channels
    users_res = st.session_state.slack_users

    # Handle fetch errors
    if channels_res.get("error"):
        if "missing_scope" in channels_res["error"]:
            st.warning("⚠️ **Permission Denied:** Your token lacks 'channels:read' scope. Update your app and reinstall.")
        else:
            st.error(f"❌ Error loading channels: {channels_res['error']}")
    
    if users_res.get("error"):
        if "missing_scope" in users_res["error"]:
            st.warning("⚠️ **Permission Denied:** Your token lacks 'users:read' scope. Update your app and reinstall.")
        else:
            st.error(f"❌ Error loading users: {users_res['error']}")

    channels = channels_res.get("data", [])
    users = users_res.get("data", [])

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("**Select Recipients**")
        
        selected_dest_ids = []
        
        # 1. Channel Selection
        if channels:
            chan_names = [f"#{c['name']}" for c in channels]
            sel_chans = st.multiselect(
                "Channels", 
                ["All Channels"] + chan_names, 
                default=["All Channels"],
                help="Select individual channels or 'All Channels'"
            )
            
            if "All Channels" in sel_chans:
                for c in channels: selected_dest_ids.append((f"#{c['name']}", c["id"]))
            else:
                channel_map = {f"#{c['name']}": c["id"] for c in channels}
                for name in sel_chans: selected_dest_ids.append((name, channel_map[name]))
        
        # 2. DM Selection
        if users:
            # Map IDs to names for cleaner display
            user_names = [f"👤 {u['name']}" for u in users]
            sel_users = st.multiselect(
                "Direct Messages", 
                ["All Users"] + user_names, 
                default=["All Users"],
                help="Select individual users or 'All Users'"
            )
            
            if "All Users" in sel_users:
                for u in users: selected_dest_ids.append((f"👤 {u['name']}", u["id"]))
            else:
                user_map = {f"👤 {u['name']}": u["id"] for u in users}
                for name in sel_users: selected_dest_ids.append((name, user_map[name]))

        st.markdown("**Message**")
        if "slack_msg_key" not in st.session_state: st.session_state.slack_msg_key = 0
            
        message_text = st.text_area(
            "Type your message here...", height=120, label_visibility="collapsed",
            key=f"slack_message_input_{st.session_state.slack_msg_key}"
        )
        
        if st.button("📤 Send Message", use_container_width=True):
            if not selected_dest_ids: st.error("Please select at least one destination.")
            elif not message_text.strip(): st.error("Message cannot be empty.")
            else:
                with st.spinner("Sending..."):
                    sent_msgs = []
                    for name, dest_id in selected_dest_ids:
                        res = send_slack_message(dest_id, message_text)
                        if res["success"]:
                            sent_msgs.append({"chan_id": dest_id, "chan_name": name, "ts": res["ts"], "text": message_text, "sent_at": time.time()})
                    
                    if sent_msgs:
                        st.success(f"✅ Sent successfully to {len(sent_msgs)} destination(s)!")
                        if "slack_recent_sent" not in st.session_state: st.session_state.slack_recent_sent = []
                        st.session_state.slack_recent_sent.extend(sent_msgs)
                        st.session_state.slack_msg_key += 1
                        st.rerun()
                    else:
                        st.error("❌ Failed to send message.")

        # ── Message Edit Workflow (15 min window) ───────────────────────────
        recent = st.session_state.get("slack_recent_sent", [])
        if recent:
            st.markdown("---")
            st.subheader("📝 Recently Sent (Editable for 15m)")
            
            import time as pytime
            now = pytime.time()
            to_keep = []
            
            for i, msg in enumerate(reversed(recent)):
                age = now - msg["sent_at"]
                if age < 900: # 15 minutes
                    to_keep.append(msg)
                    c1, c2 = st.columns([4, 1])
                    c1.caption(f"To: {msg['chan_name']} ({int((900-age)/60)}m left)")
                    c1.markdown(f"_{msg['text'][:60]}..._")
                    
                    if c2.button("✏️ Edit", key=f"edit_recent_{i}"):
                        st.session_state.editing_msg = msg
                        st.rerun()
            
            # Update session state to remove expired messages
            st.session_state.slack_recent_sent = to_keep

        # Edit Dialog
        if st.session_state.get("editing_msg"):
            e_msg = st.session_state.editing_msg
            with st.expander("📝 Edit Message", expanded=True):
                new_text = st.text_area("Update content", value=e_msg["text"], key="edit_area")
                cc1, cc2 = st.columns(2)
                if cc1.button("💾 Save Changes", use_container_width=True, type="primary"):
                    with st.spinner("Updating..."):
                        res = update_message(e_msg["chan_id"], e_msg["ts"], new_text)
                        if res["success"]:
                            # Reset timer on edit
                            for m in st.session_state.slack_recent_sent:
                                if m["ts"] == e_msg["ts"] and m["chan_id"] == e_msg["chan_id"]:
                                    m["text"] = new_text
                                    m["sent_at"] = pytime.time()
                            st.success("Message updated!")
                            st.session_state.editing_msg = None
                            pytime.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Error: {res['error']}")
                if cc2.button("❌ Cancel", use_container_width=True):
                    st.session_state.editing_msg = None
                    st.rerun()

    with col2:
        st.subheader("Data Refresh")
        st.caption("If you recently added a channel or user, refresh the list.")
        if st.button("🔄 Refresh Data", use_container_width=True):
            del st.session_state["slack_channels"]
            del st.session_state["slack_users"]
            st.rerun()
