"""
management_workflow.py
----------------------
Handles Slack CRUD operations like creating, renaming, and archiving channels,
as well as adding users and forwarding messages.
"""

import streamlit as st
from slack.slack_handler import (
    is_slack_authenticated,
    fetch_channels,
    fetch_users,
    create_channel,
    rename_channel,
    add_users_to_channel,
    archive_channel,
    fetch_archived_channels,
    remove_reaction,
    remove_pin,
    remove_star,
    close_conversation,
    kick_user_from_channel,
    search_workspace_data,
    get_or_create_dm,
    fetch_unread_mentions,
    add_star,
    add_pin
)

def render_management_workflow():
    st.header("🛠️ Slack Management")

    if not is_slack_authenticated():
        st.warning("⚠️ Connect your Slack workspace first via the **Settings** tab.")
        return

    tab_create, tab_rename, tab_add_user, tab_forward, tab_unreads = st.tabs([
        "➕ Create Channel", "✏️ Rename Channel", "👥 Add Users", "📨 Forward Message", "📩 Check Unreads"
    ])

    # ── 1. Create Channel ───────────────────────────────────────────────────
    with tab_create:
        st.subheader("➕ Create New Channel")
        c_name = st.text_input("Channel Name", placeholder="e.g. project-x")
        c_private = st.checkbox("Make Private")
        
        if st.button("🚀 Create Channel", use_container_width=True):
            if not c_name:
                st.error("Please enter a channel name.")
            else:
                _render_management_planner("Create Channel", {"Name": c_name, "Privacy": "Private" if c_private else "Public"})
                with st.spinner("Creating channel..."):
                    res = create_channel(c_name, c_private)
                    if res["success"]:
                        st.success(f"✅ Channel '#{res['final_name']}' created successfully!")
                        st.session_state.pop("slack_explorer_channels", None) # Clear cache
                    else:
                        st.error(f"❌ Error: {res['error']}")

    # ── 2. Rename Channel ───────────────────────────────────────────────────
    with tab_rename:
        st.subheader("✏️ Rename Channel")
        chan_res = fetch_channels()
        if chan_res["error"]:
            _render_mgmt_error(chan_res["error"], "channels:read")
        elif not chan_res["data"]:
            st.info("No channels found.")
        else:
            channels = chan_res["data"]
            chan_opts = {c["name"]: c["id"] for c in channels}
            selected_chan = st.selectbox("Select Channel", list(chan_opts.keys()), key="rename_chan_sel")
            new_name = st.text_input("New Channel Name", placeholder="e.g. updated-project-name")
            
            if st.button("💾 Rename Channel", use_container_width=True):
                if not new_name:
                    st.error("Please enter a new name.")
                else:
                    _render_management_planner("Rename Channel", {"ID": chan_opts[selected_chan], "Old Name": selected_chan, "New Name": new_name})
                    with st.spinner("Renaming channel..."):
                        res = rename_channel(chan_opts[selected_chan], new_name)
                        if res["success"]:
                            st.success("✅ Channel renamed successfully!")
                            st.session_state.pop("slack_explorer_channels", None)
                        else:
                            st.error(f"❌ Error: {res['error']}")

    # ── 3. Add Users ────────────────────────────────────────────────────────
    with tab_add_user:
        st.subheader("👥 Add Users to Channel")
        chan_res = fetch_channels()
        user_res = fetch_users()
        
        if chan_res["error"] or user_res["error"]:
            err = chan_res["error"] or user_res["error"]
            _render_mgmt_error(err, "channels:read and users:read")
        elif not chan_res["data"] or not user_res["data"]:
            st.info("Ensure you have channels and users available.")
        else:
            channels = chan_res["data"]
            users = user_res["data"]
            chan_opts = {c["name"]: c["id"] for c in channels}
            user_opts = {u["name"]: u["id"] for u in users}
            
            target_chan = st.selectbox("Select Target Channel", list(chan_opts.keys()), key="add_user_chan_sel")
            target_users = st.multiselect("Select Users", list(user_opts.keys()))
            
            if st.button("➕ Add Users", use_container_width=True):
                if not target_users:
                    st.error("Please select at least one user.")
                else:
                    u_ids = [user_opts[u] for u in target_users]
                    _render_management_planner("Add User", {"Channel": target_chan, "Users": target_users})
                    with st.spinner("Inviting users..."):
                        res = add_users_to_channel(chan_opts[target_chan], u_ids)
                        if res["success"]:
                            st.success(f"✅ Users added to #{target_chan}!")
                        else:
                            st.error(f"❌ Error: {res['error']}")


    # ── 5. Forward Message ──────────────────────────────────────────────────
    with tab_forward:
        st.subheader("📨 Forward Message")
        chan_res = fetch_channels()
        if chan_res["error"]:
            _render_mgmt_error(chan_res["error"], "channels:read")
        elif not chan_res["data"]:
            st.info("Channels required.")
        else:
            channels = chan_res["data"]
            chan_opts = {c["name"]: c["id"] for c in channels}
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                src_chan = st.selectbox("Source Channel", list(chan_opts.keys()), key="fwd_src_chan")
                msg_ts = st.text_input("Message Timestamp (TS)", placeholder="e.g. 1710928371.123400")
            with col_f2:
                dest_chan = st.selectbox("Destination Channel", list(chan_opts.keys()), key="fwd_dest_chan")
                
            if st.button("📨 Forward via Permalink", use_container_width=True):
                if not msg_ts:
                    st.error("Please provide a message timestamp.")
                else:
                    _render_management_planner("Forward Message", {"Source": src_chan, "Destination": dest_chan, "TS": msg_ts})
                    with st.spinner("Forwarding..."):
                        res = forward_message(chan_opts[src_chan], msg_ts, chan_opts[dest_chan])
                        if res["success"]:
                            st.success("✅ Message forwarded successfully!")
                        else:
                            st.error(f"❌ Error: {res['error']}")

    # ── 6. Check Unreads ──────────────────────────────────────────────────
    with tab_unreads:
        st.subheader("📩 Unread Messages & Mentions")
        st.caption("Showing activity from the last 24 hours in your joined channels.")
        
        if st.button("🔄 Fetch Latest Activity", use_container_width=True):
            with st.spinner("Scanning channels..."):
                st.session_state.slack_unreads = fetch_unread_mentions()
        
        unreads = st.session_state.get("slack_unreads")
        if unreads:
            if unreads["error"]:
                st.error(f"Error: {unreads['error']}")
            elif not unreads["data"]:
                st.info("No recent unread messages or mentions found.")
            else:
                for i, m in enumerate(unreads["data"]):
                    with st.container(border=True):
                        c1, c2 = st.columns([4, 0.5])
                        with c1:
                            st.markdown(f"**#{m['channel_name']}** • {m['time']} • {m['user_name']}")
                            st.markdown(m["text"])
                        
                        with c2.popover("⋮"):
                            if st.button("👁️ View", key=f"unr_view_{i}", use_container_width=True):
                                st.session_state.unread_viewing = m
                                st.rerun()
                            if st.button("✏️ Edit", key=f"unr_edit_{i}", use_container_width=True):
                                st.session_state.unread_editing = m
                                st.rerun()
                            if st.button("📌 Pin", key=f"unr_pin_{i}", use_container_width=True):
                                if add_pin(m["channel_id"], m["ts"])["success"]: st.success("Pinned")
                            if st.button("⭐ Star", key=f"unr_star_{i}", use_container_width=True):
                                if add_star(m["channel_id"], m["ts"])["success"]: st.success("Starred")
                            if st.button("📋 Copy", key=f"unr_copy_{i}", use_container_width=True):
                                st.code(m["text"])

                # Detail View for Unreads
                if st.session_state.get("unread_viewing"):
                    uv = st.session_state.unread_viewing
                    with st.expander(f"👁️ Viewing message in #{uv['channel_name']}", expanded=True):
                        st.write(uv["text"])
                        if st.button("Close Viewer", key="close_unr_view"):
                            st.session_state.unread_viewing = None
                            st.rerun()

                # Edit View for Unreads
                if st.session_state.get("unread_editing"):
                    ue = st.session_state.unread_editing
                    with st.expander(f"✏️ Editing message in #{ue['channel_name']}", expanded=True):
                        new_text = st.text_area("Update content", value=ue["text"], key="edit_unr_area")
                        if st.button("Save Changes", key="save_unr_edit", type="primary"):
                            from slack.slack_handler import update_message
                            if update_message(ue["channel_id"], ue["ts"], new_text)["success"]:
                                st.success("Updated!")
                                ue["text"] = new_text
                                st.session_state.unread_editing = None
                                st.rerun()
                        if st.button("Cancel", key="cancel_unr_edit"):
                            st.session_state.unread_editing = None
                            st.rerun()
        else:
            st.info("Click 'Fetch Latest Activity' to scan for unreads.")

def _render_mgmt_error(err_msg: str, scope: str):
    if "missing_scope" in err_msg:
        st.warning(
            f"⚠️ **Permission Denied by Slack**\n\n"
            f"Your token lacks the '{scope}' scope required for this tab. "
            "Please update your app's **User Token Scopes** and reinstall."
        )
    else:
        st.error(f"❌ Error: {err_msg}")

def _render_management_planner(action: str, entities: dict):
    """Render the AI Workflow Planner for management tasks."""
    steps = {
        "Create Channel": [
            "Initializing Slack conversations_create request",
            f"Applying channel name validation for '{entities.get('Name')}'",
            f"Setting channel visibility to {entities.get('Privacy')}",
            "Executing creation and verifying response"
        ],
        "Rename Channel": [
            "Locating target channel ID",
            f"Preparing rename request from '{entities.get('Old Name')}' to '{entities.get('New Name')}'",
            "Executing conversations_rename",
            "Refreshing local channel cache"
        ],
        "Add User": [
            f"Resolving User IDs for {len(entities.get('Users', []))} members",
            f"Checking bot permissions in channel '{entities.get('Channel')}'",
            "Executing conversations_invite",
            "Verifying successful invitation"
        ],
        "Archive Channel": [
            "Performing destructive action pre-check",
            f"Verifying confirmation for channel '{entities.get('Channel')}'",
            "Executing conversations_archive (Moving to Trash)",
            "Updating workspace topology cache"
        ],
        "Forward Message": [
            f"Fetching unique permalink for message {entities.get('TS')}",
            f"Connecting source channel '{entities.get('Source')}' to '{entities.get('Destination')}'",
            "Formatting forward payload",
            "Posting permalink to destination channel"
        ]
    }.get(action, ["Analyzing operation", "Executing Slack API call"])

    st.markdown(
        f"""
        <div style="background: rgba(108,99,255,0.05); border-left: 4px solid #6c63ff; padding: 15px; border-radius: 4px; margin-bottom: 20px;">
            <div style="color: #6c63ff; font-weight: bold; font-size: 14px; margin-bottom: 8px;">🚀 AI MANAGEMENT PLANNER</div>
            <div style="font-size: 13px;">
                <b>Action:</b> {action} <br>
                <b>Entities:</b> {", ".join([f"{k}: {v}" for k, v in entities.items()])} <br>
                <b>Steps:</b><br>
                {"".join([f"&nbsp;&nbsp;{i+1}. {step}<br>" for i, step in enumerate(steps)])}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
