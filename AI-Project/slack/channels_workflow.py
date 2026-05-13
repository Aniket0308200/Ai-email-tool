"""
channels_workflow.py
--------------------
Streamlit workflow for listing and browsing Slack data (Data Explorer).
Supports listing channels, DMs, users, messages, files, reactions, threads, etc.
"""

import streamlit as st
from slack.slack_handler import is_slack_authenticated, fetch_list_data

def render_channels_workflow():
    st.header("📋 Slack Data Explorer")

    if not is_slack_authenticated():
        st.warning("⚠️ Connect your Slack workspace first via the **Settings** tab.")
        return

    # Select View
    view_options = [
        "Public Channels", "Private Channels", "Users", "Messages", 
        "Pinned Messages", "Files", "Reactions", "Threads",
        "Unread Messages", "Mentions"
    ]
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.markdown("**1. Choose View**")
        selected_view = st.radio("Select View:", view_options, label_visibility="collapsed")
        
        channel_id = None
        # Views that require a target channel context
        if selected_view in ["Messages", "Pinned Messages", "Reactions", "Threads",
                              "Unread Messages", "Mentions"]:
            st.markdown("---")
            st.markdown("**2. Select Target Channel/DM**")
            
            # Fetch channels cached for dropdown
            if "slack_explorer_channels" not in st.session_state:
                with st.spinner("Loading channels..."):
                    c_resp = fetch_list_data("channels")
                    p_resp = fetch_list_data("private_channels")
                    d_resp = fetch_list_data("dms")
                    st.session_state.slack_explorer_channels = (
                        c_resp.get("data", []) + 
                        p_resp.get("data", []) + 
                        d_resp.get("data", [])
                    )
            
            # Map for user display names if needed
            if "slack_user_map" not in st.session_state:
                from slack.slack_handler import fetch_users
                u_resp = fetch_users()
                st.session_state.slack_user_map = {u["id"]: u["name"] for u in u_resp.get("data", [])}
                    
            opts = { (c.get("name") or c.get("id")): c["id"] for c in st.session_state.slack_explorer_channels }
            if opts:
                # Unread and Mentions must have a specific channel — no "All"
                needs_specific = selected_view in ["Unread Messages", "Mentions",
                                                   "Pinned Messages"]
                all_opts = list(opts.keys()) if needs_specific else ["All"] + list(opts.keys())
                selected_name = st.selectbox(
                    "Select Target", options=all_opts, index=0,
                    label_visibility="collapsed"
                )
                channel_id = "all" if selected_name == "All" else opts.get(selected_name)
            else:
                st.warning("No channels found.")
                
        st.markdown("---")
        # Add Count Option
        st.markdown("**3. Item Count**")
        list_limit = st.number_input("Limit results", min_value=1, max_value=1000, value=50, step=1, label_visibility="collapsed")
        
        st.markdown("---")
        if st.button("🔄 Refresh Data", key="refresh_explorer_data", use_container_width=True):
            if "slack_explorer_channels" in st.session_state:
                del st.session_state.slack_explorer_channels
            if "slack_user_map" in st.session_state:
                del st.session_state.slack_user_map
            st.rerun()

    with col2:
        st.subheader(f"Results: {selected_view}")
        
        api_map = {
            "Public Channels": "channels",
            "Private Channels": "private_channels",
            "Users": "users",
            "Direct Messages": "dms",
            "Group DMs": "group_dms",
            "Messages": "messages",
            "Unread Messages": "unread_messages",
            "Mentions": "mentions",
            "Pinned Messages": "pinned_messages",
            "Files": "files",
            "Reactions": "reactions",
            "Threads": "threads"
        }
        
        list_type = api_map[selected_view]

        # Guard: some views always require a specific channel
        always_needs_channel = list_type in (
            "unread_messages", "mentions", "pinned_messages"
        )
        if always_needs_channel and not channel_id:
            st.warning(
                f"⚠️ Please select a specific channel to view **{selected_view}**."
            )
        else:
            with st.spinner(f"Fetching {selected_view}..."):
                result = fetch_list_data(list_type, channel_id, limit=list_limit)

            # ── Error handling ─────────────────────────────────────────────
            if result.get("error"):
                err = result["error"]
                if "missing_scope" in err:
                    st.warning(f"⚠️ Missing Slack permission: {err}")
                else:
                    st.error(f"❌ {err}")

            # ── Empty-state messages ───────────────────────────────────────
            elif not result.get("data"):
                empty_reason = result.get("empty_reason", "")
                empty_messages = {
                    "no_unread":        "✅ No unread messages — you're all caught up!",
                    "pinned_messages":  "📌 No pinned messages in this channel.",
                    "reactions":        "😶 No messages with reactions found.",
                    "threads":          "🧵 No threads found.",
                    "mentions":         "💬 No mentions found in this channel.",
                    "unread_messages":  "✅ No unread messages — you're all caught up!",
                    "stars":            "⭐ No starred messages.",
                    "files":            "📎 No files found.",
                    "messages":         "💬 No messages found.",
                    "channels":         "📁 No channels found.",
                    "users":            "👥 No users found.",
                    "dms":              "📩 No direct messages found.",
                    "group_dms":        "👥 No group DMs found.",
                    "private_channels": "🔒 No private channels found.",
                }
                if empty_reason:
                    st.info(empty_messages.get(empty_reason, "No data available."))
                else:
                    st.info(empty_messages.get(list_type, "No data available."))

            # ── Results table ──────────────────────────────────────────────
            else:
                data = result["data"]
                processed_data = process_slack_data(list_type, data)

                # Mark-as-read button for unread messages
                if list_type == "unread_messages" and channel_id:
                    if st.button("✅ Mark all as read", key="mark_read_btn"):
                        from slack.slack_handler import mark_channel_read
                        r = mark_channel_read(channel_id)
                        if r["success"]:
                            st.success("✅ Channel marked as read.")
                            st.rerun()
                        else:
                            st.warning(f"Could not mark as read: {r['error']}")

                search_query = st.text_input(
                    "🔍 Filter results...", key=f"search_{list_type}"
                )
                if search_query:
                    q = search_query.lower()
                    processed_data = [
                        row for row in processed_data
                        if any(q in str(v).lower() for v in row.values())
                    ]

                st.dataframe(processed_data, use_container_width=True, hide_index=True)
                st.caption(f"Showing {len(processed_data)} item(s).")

def process_slack_data(list_type: str, data: list) -> list:
    """Flatten Slack API responses into nice dictionaries for Streamlit display."""
    processed = []
    user_map = st.session_state.get("slack_user_map", {})
    
    def get_name(uid):
        return user_map.get(uid, uid)
    
    for item in data:
        if list_type in ["channels", "private_channels", "dms", "group_dms"]:
            processed.append({
                "ID": item.get("id"),
                "Name": item.get("name", "—"),
                "Creator": get_name(item.get("creator", "—")),
                "Members": item.get("num_members", "—"),
                "Archived": "Yes" if item.get("is_archived") else "No"
            })
        elif list_type == "users":
            processed.append({
                "ID": item.get("id"),
                "Name": item.get("real_name") or item.get("name"),
                "Title": item.get("profile", {}).get("title", "—"),
                "Email": item.get("profile", {}).get("email", "—"),
                "Admin": "Yes" if item.get("is_admin") else "No"
            })
        elif list_type in ["messages", "reactions", "threads", "unread_messages", "mentions"]:
            text = item.get("text", "—")
            if text and len(text) > 100:
                text = text[:100] + "..."
            
            user_id = item.get("user") or item.get("username") or "Unknown"
            user_display = get_name(user_id)
            
            processed.append({
                "User": user_display,
                "Text": text,
                "Timestamp": item.get("ts"),
                "Reactions": len(item.get("reactions", [])) if isinstance(item.get("reactions"), list) else 0,
                "Replies": item.get("reply_count", 0)
            })
        elif list_type == "files":
            processed.append({
                "ID": item.get("id"),
                "Name": item.get("name"),
                "Type": item.get("filetype"),
                "Size (KB)": round(item.get("size", 0) / 1024, 1) if item.get("size") else 0,
                "User": get_name(item.get("user", "—"))
            })
        elif list_type == "pinned_messages":
            if item.get("type") == "message":
                msg = item.get("message", {})
                text = msg.get("text", "—")
                processed.append({
                    "Pinned By": get_name(item.get("created_by", "—")),
                    "User": get_name(msg.get("user", "Unknown")),
                    "Text": text[:100] + "..." if len(text) > 100 else text,
                    "Timestamp": msg.get("ts")
                })
            else:
                processed.append({
                    "Type": item.get("type"), 
                    "ID": item.get("created_by"),
                    "Text": "—",
                    "User": "—",
                    "Timestamp": item.get("created")
                })
                
    return processed
