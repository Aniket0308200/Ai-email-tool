"""
delete_workflow.py
------------------
Master Cleanup & Management Center for Slack with Search & Delete and Advanced Cleanup tables.
Includes centered confirmation dialogs, message previews, and robust selection logic.
"""

import streamlit as st
import time
from datetime import datetime
from slack.slack_handler import (
    is_slack_authenticated,
    fetch_channels,
    fetch_users,
    fetch_list_data,
    archive_channel,
    unarchive_channel,
    delete_message,
    fetch_archived_channels,
    remove_reaction,
    remove_pin,
    remove_star,
    close_conversation,
    kick_user_from_channel,
    search_workspace_data,
    get_or_create_dm
)

# ── DIALOGS ───────────────────────────────────────────────────────────────────

@st.dialog("🔍 Message Preview")
def _view_message_dialog(msg_text, channel_name, timestamp):
    st.markdown(f"**Channel:** {channel_name}")
    st.markdown(f"**Time:** {timestamp}")
    st.markdown("---")
    st.markdown(f"**Content ({len(msg_text)} chars):**")
    st.code(msg_text, language=None, wrap_lines=True)
    if st.button("Close"):
        st.rerun()

@st.dialog("⚠️ Confirm Deletion")
def _confirm_delete_dialog(action_type, count, callback, **kwargs):
    st.markdown(f"""
        <div style="text-align: center; color: #ff4b4b; padding: 20px;">
            <h1 style="margin: 0; font-size: 60px;">🚨</h1>
            <h2 style="margin-top: 10px;">Are you absolutely sure?</h2>
            <p style="font-size: 16px;">You are about to permanently delete <b>{count}</b> {action_type}.</p>
            <p style="font-weight: bold; background: rgba(255, 75, 75, 0.1); padding: 10px; border-radius: 5px;">
                THIS ACTION IS PERMANENT AND CANNOT BE UNDONE.
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    if c1.button("Cancel", use_container_width=True):
        st.rerun()
    if c2.button("🔥 Yes, Delete Permanently", type="primary", use_container_width=True):
        callback(**kwargs)
        st.success("Action completed successfully.")
        time.sleep(1)
        st.rerun()

# ── WORKFLOW CORE ─────────────────────────────────────────────────────────────

def _track_manual_selection(key):
    """Callback to track manual checkbox clicks."""
    if "manual_selections" not in st.session_state:
        st.session_state.manual_selections = {}
    st.session_state.manual_selections[key] = st.session_state[key]

def render_delete_workflow():
    st.header("🗑️ Global Cleanup & Management Center")

    if not is_slack_authenticated():
        st.warning("⚠️ Connect your Slack workspace first via the **Settings** tab.")
        return

    # Initialize session states
    if "slack_trash" not in st.session_state:
        st.session_state.slack_trash = {"messages": [], "users": []}
    
    # Selection state trackers
    if "purge_selection" not in st.session_state:
        st.session_state.purge_selection = {}
    if "search_purge_selection" not in st.session_state:
        st.session_state.search_purge_selection = {}
    if "manual_selections" not in st.session_state:
        st.session_state.manual_selections = {}
        
    # Shared Edit Dialog for search results
    if st.session_state.get("editing_msg"):
        e_msg = st.session_state.editing_msg
        with st.expander("📝 Edit Message", expanded=True):
            new_text = st.text_area("Update content", value=e_msg.get("text", ""), key="edit_area_search")
            ec1, ec2 = st.columns(2)
            if ec1.button("💾 Save Changes", use_container_width=True, type="primary", key="save_edit_search"):
                with st.spinner("Updating..."):
                    from slack.slack_handler import update_message
                    res = update_message(e_msg["chan_id"], e_msg["ts"], new_text)
                    if res["success"]:
                        st.success("Message updated! Re-run search to see changes.")
                        st.session_state.editing_msg = None
                        import time as pytime
                        pytime.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Error: {res['error']}")
            if ec2.button("❌ Cancel", use_container_width=True, key="cancel_edit_search"):
                st.session_state.editing_msg = None
                st.rerun()

    tab_search, tab_messages, tab_unified, tab_trash = st.tabs([
        "🔍 Search & Delete", "💬 Advanced Cleanup", "🌐 Asset & Topology", "♻️ Recycle Bin"
    ])

    with tab_search: _render_search_purge_section()
    with tab_messages: _render_message_purge_section()
    with tab_unified: _render_asset_topology_unified_section()
    with tab_trash: _render_trash_section()

# ── 🔍 SEARCH & DELETE ────────────────────────────────────────────────────────

def _render_search_purge_section():
    st.subheader("🔍 Search & Delete")
    
    col_type, col_input, col_count, col_btn = st.columns([1.2, 2.8, 1, 1])
    with col_type:
        search_type = st.selectbox("Search Type", ["All", "Messages", "Channels", "Users"], key="sd_type_filter")
    with col_input:
        query = st.text_input("search_query", placeholder=f"Search {search_type.lower()}...", label_visibility="collapsed")
    with col_count:
        limit = st.number_input("Limit", 1, 100, 20, key="sd_limit", label_visibility="collapsed")
    with col_btn:
        if st.button("🔍 Search", use_container_width=True):
            if not query:
                st.warning("Please enter a search term.")
            else:
                with st.spinner("Searching..."):
                    results = search_workspace_data(query, limit, newest_first=True, filter_type=search_type)
                    st.session_state.slack_del_search_results = results
                    st.session_state.slack_del_search_query = query
                    st.session_state.slack_del_active_type = search_type
                    st.session_state.manual_selections = {}

    results = st.session_state.get("slack_del_search_results")
    if results:
        _render_search_results_with_selection(results)

def _render_search_results_with_selection(results):
    st.markdown("---")
    
    active_key = st.session_state.get("slack_del_active_type", "All").lower()
    
    # Prepare items based on category
    items = []
    if active_key == "all":
        for k in ["messages", "channels", "users", "files"]:
            for item in results.get(k, []):
                item["_key_type"] = k
                items.append(item)
    else:
        for item in results.get(active_key, []):
            item["_key_type"] = active_key
            items.append(item)

    if not items:
        st.info(f"No results found for search.")
        return

    st.markdown(f"#### 📊 {active_key.title()} Results ({len(items)})")
    
    # Bulk actions header
    c1, c2, c3 = st.columns([2.5, 1, 1.5])
    
    with c1:
        cc1, cc2, cc3 = st.columns(3)
        if cc1.button("✅ Select All", key=f"sd_all_btn_{active_key}"):
            for i in range(len(items)): st.session_state[f"sd_cb_{active_key}_{i}"] = True
            st.rerun()
        if cc2.button("🔲 Deselect All", key=f"sd_none_btn_{active_key}"):
            for i in range(len(items)): st.session_state[f"sd_cb_{active_key}_{i}"] = False
            st.rerun()
        if cc3.button("♻️ Restore Manual", key=f"sd_restore_btn_{active_key}"):
            manuals = st.session_state.get("manual_selections", {})
            for i in range(len(items)):
                k = f"sd_cb_{active_key}_{i}"
                st.session_state[k] = manuals.get(k, False)
            st.rerun()

    # Track selection
    selected_indices = [i for i in range(len(items)) if st.session_state.get(f"sd_cb_{active_key}_{i}")]
    
    with c3:
        del_label = f"🔥 Clean Selected ({len(selected_indices)})"
        if st.button(del_label, type="primary", use_container_width=True, disabled=not selected_indices):
            _confirm_delete_dialog(
                action_type="items", 
                count=len(selected_indices), 
                callback=_execute_bulk_search_delete,
                items_to_delete=[items[i] for i in selected_indices],
                active_key=active_key
            )

    # 4. Table Layout
    st.markdown("""
        <div style="display: flex; background: rgba(255,255,255,0.05); padding: 10px; border-radius: 4px; font-weight: bold; margin-bottom: 10px;">
            <div style="flex: 0.5;">Sel</div>
            <div style="flex: 1;">Type</div>
            <div style="flex: 1.5;">Date / Time</div>
            <div style="flex: 3;">Content Preview</div>
            <div style="flex: 1;">Action</div>
        </div>
    """, unsafe_allow_html=True)

    for i, item in enumerate(items):
        k_type = item["_key_type"]
        cols = st.columns([0.5, 1, 1.5, 3, 1])
        k = f"sd_cb_{active_key}_{i}"
        
        # Checkbox (Updates manual tracker on change)
        cols[0].checkbox(" ", key=k, label_visibility="collapsed", on_change=_track_manual_selection, args=(k,))
        
        # Type & Time
        cols[1].caption(k_type.title())
        cols[2].caption(item.get("Time", "—"))
        
        # Content
        if k_type == "messages":
            display_text = f"**{item['Channel']}**: {item['Message']}"
            cols[3].markdown(display_text)
            
            with cols[4].popover("⋮"):
                if st.button("👁️ View", key=f"sd_view_{active_key}_{i}", use_container_width=True):
                    _view_message_dialog(item["_raw"], item["Channel"], item["Time"])
                
                if st.button("📌 Pin", key=f"sd_pin_{active_key}_{i}", use_container_width=True):
                    if add_pin(item["channel_id"], item["ts"])["success"]: st.success("Pinned")
                
                if st.button("⭐ Star", key=f"sd_star_{active_key}_{i}", use_container_width=True):
                    if add_star(item["channel_id"], item["ts"])["success"]: st.success("Starred")
                
                if st.button("📋 Copy", key=f"sd_copy_{active_key}_{i}", use_container_width=True):
                    st.code(item["_raw"])
                
                if st.button("✏️ Edit", key=f"sd_edit_{active_key}_{i}", use_container_width=True):
                    st.session_state.editing_msg = {"chan_id": item["channel_id"], "ts": item["ts"], "text": item["_raw"]}
                    st.rerun()
        else:
            cols[3].markdown(f"**{item.get('Name', '—')}** (ID: {item.get('ID', '—')})")
            cols[4].caption("No Preview")

def _execute_bulk_search_delete(items_to_delete, active_key):
    results = st.session_state.slack_del_search_results
    
    success_count = 0
    for item in items_to_delete:
        k_type = item["_key_type"]
        success = False
        
        if k_type == "messages":
            res = delete_message(item["channel_id"], item["ts"])
            success = res["success"]
        elif k_type == "channels":
            res = archive_channel(item["channel_id"])
            success = res["success"]
        elif k_type == "users":
            st.session_state.slack_trash["users"].append(item)
            success = True
        
        if success:
            if k_type in results:
                if k_type == "messages":
                    results[k_type] = [m for m in results[k_type] if m["ts"] != item["ts"]]
                else:
                    results[k_type] = [m for m in results[k_type] if m.get("ID") != item.get("ID")]
            success_count += 1

    for k in list(st.session_state.keys()):
        if k.startswith(f"sd_cb_{active_key}_"):
            st.session_state[k] = False
    
    st.success(f"Successfully processed {success_count} items.")
    st.session_state.search_purge_selection = {}

# ── 💬 ADVANCED CLEANUP ──────────────────────────────────────────────────────

def _render_message_purge_section():
    st.subheader("🔥 Advanced Message Cleanup")
    col_chan, col_filter = st.columns([1, 1])
    
    chan_res = fetch_channels()
    if chan_res["error"]: return
    chan_opts = {f"#{c['name']}": c["id"] for c in chan_res["data"]}
    
    with col_chan: 
        c_list = ["All"] + list(chan_opts.keys())
        sel_chan = st.selectbox("Target Channel", c_list, key="msg_purge_chan")
    with col_filter:
        purge_filter = st.selectbox("Cleanup Strategy", [
            "Bulk Delete (All)", "Keyword Filter", "Specific User", "Bot/App Messages",
            "Attachments/Files Only", "Duplicate Messages", "Old Messages (>30d)", "Last Message"
        ])
    
    filter_val = None
    if purge_filter == "Keyword Filter": filter_val = st.text_input("Enter Keyword", placeholder="e.g. spam")
    elif purge_filter == "Specific User":
        user_res = fetch_users()
        if not user_res["error"]:
            u_opts = {u["name"]: u["id"] for u in user_res["data"]}
            sel_user = st.selectbox("Select User", list(u_opts.keys()))
            filter_val = u_opts[sel_user]
            
    col_count, col_btn = st.columns([1, 1])
    with col_count: limit = st.number_input("Scan Limit", 1, 500, 50, key="ap_limit")
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔍 Scan Workspace", use_container_width=True, key="ap_scan_btn"):
            if sel_chan == "All":
                st.warning(
                    "⚠️ **Please select one channel instead of All.** "
                    "Scanning all channels at once is not supported — "
                    "select a specific channel from the dropdown."
                )
            else:
                st.session_state.purge_scan_results = _perform_scan(chan_opts[sel_chan], purge_filter, filter_val, limit)
                st.session_state.purge_chan_id = chan_opts[sel_chan]
                st.session_state.purge_chan_name = sel_chan
                st.session_state.purge_selection = {}

    results = st.session_state.get("purge_scan_results")
    if results:
        _render_purge_results_table(results)

def _perform_scan(channel_id, strategy, filter_val, limit):
    with st.spinner("Scanning..."): msg_res = fetch_list_data("messages", channel_id, limit=limit)
    if msg_res["error"]: return []
    msgs = msg_res["data"]
    to_delete = []
    if strategy == "Bulk Delete (All)": to_delete = msgs
    elif strategy == "Keyword Filter": to_delete = [m for m in msgs if filter_val.lower() in m.get("text", "").lower()]
    elif strategy == "Specific User": to_delete = [m for m in msgs if m.get("user") == filter_val]
    elif strategy == "Bot/App Messages": to_delete = [m for m in msgs if m.get("bot_id") or m.get("subtype") == "bot_message"]
    elif strategy == "Attachments/Files Only": to_delete = [m for m in msgs if m.get("files") or m.get("attachments")]
    elif strategy == "Duplicate Messages":
        seen = set()
        for m in msgs:
            txt = m.get("text", "").strip()
            if txt in seen and txt != "": to_delete.append(m)
            else: seen.add(txt)
    elif strategy == "Old Messages (>30d)":
        threshold = time.time() - (30 * 86400)
        to_delete = [m for m in msgs if float(m.get("ts", 0)) < threshold]
    elif strategy == "Last Message": to_delete = [msgs[0]] if msgs else []
    return to_delete

def _render_purge_results_table(results):
    st.markdown("---")
    st.subheader(f"📊 Scanned Results ({len(results)} matches)")
    
    c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
    with c1:
        cc1, cc2, cc3 = st.columns(3)
        if cc1.button("✅ All", key="ap_all_btn"):
            for i in range(len(results)): st.session_state[f"ap_cb_{i}"] = True
            st.rerun()
        if cc2.button("🔲 None", key="ap_none_btn"):
            for i in range(len(results)): st.session_state[f"ap_cb_{i}"] = False
            st.rerun()
        if cc3.button("♻️ Manual", key="ap_restore_btn"):
            manuals = st.session_state.get("manual_selections", {})
            for i in range(len(results)):
                k = f"ap_cb_{i}"
                st.session_state[k] = manuals.get(k, False)
            st.rerun()
            
    selected_indices = [i for i in range(len(results)) if st.session_state.get(f"ap_cb_{i}")]
    
    with c3:
        if st.button("🗑️ Move to Trash", use_container_width=True, disabled=not selected_indices):
            for idx in selected_indices:
                m = results[idx]
                st.session_state.slack_trash["messages"].append({
                    "channel_id": st.session_state.purge_chan_id,
                    "channel_name": st.session_state.purge_chan_name,
                    "ts": m["ts"],
                    "text": m.get("text", ""),
                    "time": datetime.fromtimestamp(float(m["ts"])).strftime("%Y-%m-%d %H:%M")
                })
            # Remove from local results
            new_results = [m for i, m in enumerate(results) if i not in selected_indices]
            st.session_state.purge_scan_results = new_results
            # Clear checkbox states
            for i in range(len(results)): st.session_state[f"ap_cb_{i}"] = False
            st.success("Moved to Trash.")
            st.rerun()

    with c4:
        if st.button("🔥 Purge Selection", type="primary", use_container_width=True, disabled=not selected_indices):
            _confirm_delete_dialog(
                action_type="messages",
                count=len(selected_indices),
                callback=_execute_bulk_purge_delete,
                indices=selected_indices
            )

    # Table Layout
    st.markdown("""
        <div style="display: flex; background: rgba(255,255,255,0.05); padding: 10px; border-radius: 4px; font-weight: bold; margin-bottom: 10px;">
            <div style="flex: 0.5;">Sel</div>
            <div style="flex: 1.5;">Time</div>
            <div style="flex: 3;">Preview</div>
            <div style="flex: 1;">Action</div>
        </div>
    """, unsafe_allow_html=True)

    for i, m in enumerate(results):
        ts = m["ts"]
        dt = datetime.fromtimestamp(float(ts)).strftime("%H:%M:%S")
        txt = m.get("text", "—")[:100] + ("..." if len(m.get("text", "")) > 100 else "")
        
        c_sel, c_time, c_msg, c_view = st.columns([0.5, 1.5, 3, 1])
        k = f"ap_cb_{i}"
        c_sel.checkbox(" ", key=k, label_visibility="collapsed", on_change=_track_manual_selection, args=(k,))
        c_time.caption(dt)
        c_msg.markdown(txt)
        if c_view.button("👁️ View", key=f"ap_view_{i}"):
            _view_message_dialog(m.get("text", ""), st.session_state.purge_chan_name, dt)

def _execute_bulk_purge_delete(indices):
    results = st.session_state.purge_scan_results
    chan_id = st.session_state.purge_chan_id
    
    to_remove = []
    for idx in indices:
        m = results[idx]
        if delete_message(chan_id, m["ts"])["success"]:
            to_remove.append(idx)
            
    # Update UI
    new_results = [m for i, m in enumerate(results) if i not in to_remove]
    st.session_state.purge_scan_results = new_results
    # Clear checkbox states
    for k in list(st.session_state.keys()):
        if k.startswith("ap_cb_"):
            st.session_state[k] = False

# ── OTHER SECTIONS (Asset Cleanup, Topology, Trash) ───────────────────────────

# ── 🌐 ASSET & TOPOLOGY (UNIFIED) ──────────────────────────────────────────

def _render_asset_topology_unified_section():
    st.subheader("✨ Asset & Topology Management")
    
    # 1. Fetch data with caching
    if "slack_chan_cache" not in st.session_state or st.button("🔄 Refresh Data", key="refresh_slack_data"):
        with st.spinner("Fetching Slack data..."):
            st.session_state.slack_chan_cache = fetch_channels()
            st.session_state.slack_user_cache = fetch_users()
            # If rate limited, show a clear warning
            if st.session_state.slack_chan_cache.get("error") == "ratelimited":
                st.error("⚠️ **Rate Limited by Slack**: Too many requests. Please wait a minute before refreshing.")
                return

    chan_res = st.session_state.slack_chan_cache
    user_res = st.session_state.slack_user_cache
    
    if chan_res.get("error") or user_res.get("error"):
        err = chan_res.get("error") or user_res.get("error")
        st.error(f"❌ Error fetching data: {err}")
        return
        
    chan_opts = {f"#{c['name']}": c["id"] for c in chan_res["data"]}
    user_opts = {u["name"]: u["id"] for u in user_res["data"]}
    
    # 2. Select Target (Mutually Exclusive)
    col1, col2 = st.columns(2)
    
    # Initialize session state for targets
    if "asset_topo_target_chan" not in st.session_state: st.session_state.asset_topo_target_chan = "None"
    if "asset_topo_target_user" not in st.session_state: st.session_state.asset_topo_target_user = "None"

    # Disable logic
    chan_disabled = st.session_state.asset_topo_target_user != "None"
    user_disabled = st.session_state.asset_topo_target_chan != "None"

    with col1:
        sel_chan = st.selectbox("Select Channel", ["None", "All"] + list(chan_opts.keys()), key="asset_topo_target_chan", disabled=chan_disabled)
    with col2:
        sel_user = st.selectbox("Select User / DM", ["None", "All"] + list(user_opts.keys()), key="asset_topo_target_user", disabled=user_disabled)
        
    if sel_chan == "None" and sel_user == "None":
        st.info("💡 Select a **Channel** OR a **User** to begin managing assets and topology.")
        return

    st.markdown("---")
    
    # 3. Mode & Action Logic
    target_id = None
    is_channel = sel_chan != "None"
    
    if is_channel:
        target_id = chan_opts[sel_chan]
        # Channel Selection Logic: Action Select vs Asset Type (One at a time)
        st.write("### Channel Selection Mode")
        mode = st.radio("Choose Workflow Mode:", ["Action Selection (Topology)", "Asset Cleanup"], horizontal=True, key="chan_workflow_mode")
        
        c_act, c_asset = st.columns(2)
        with c_act:
            topo_action = st.selectbox("Action Select", ["Remove User from Channel", "Close DM/Conversation", "Archive Channel"], disabled=(mode != "Action Selection (Topology)"), key="chan_topo_act")
        with c_asset:
            asset_type = st.selectbox("Asset Type", ["Pinned Messages", "Messages with Reactions", "Starred/Saved Items"], disabled=(mode != "Asset Cleanup"), key="chan_asset_type")
            
        if mode == "Action Selection (Topology)":
            _render_topology_logic(topo_action, target_id, user_opts)
        else:
            _render_asset_cleanup_logic(asset_type, target_id)
            
    else:
        # User Selection Logic
        user_id = user_opts[sel_user]
        st.write(f"### User/DM Mode: {sel_user}")
        
        c_act, c_asset = st.columns(2)
        with c_act:
            st.selectbox("Action Select", ["Remove User from Channel", "Close DM/Conversation", "Archive Channel"], disabled=True, key="user_topo_act_disabled")
        with c_asset:
            asset_type = st.selectbox("Asset Type", ["Pinned Messages", "Messages with Reactions", "Starred/Saved Items"], disabled=False, key="user_asset_type")
        
        # Resolve DM Channel
        with st.spinner("Resolving DM channel..."):
            dm_id = get_or_create_dm(user_id)
        
        if dm_id:
            _render_asset_cleanup_logic(asset_type, dm_id)
        else:
            st.error(f"❌ Could not open a DM with {sel_user}. Ensure the bot has 'im:write' permissions.")

def _render_asset_cleanup_logic(asset_type, channel_id):
    st.markdown(f"#### 🔎 Scanning {asset_type}")
    if st.button("🔍 Find Assets", key="run_asset_scan"): 
        st.session_state.asset_scan_active = True
        st.session_state.asset_scan_type = asset_type
        st.session_state.asset_scan_chan = channel_id

    if st.session_state.get("asset_scan_active") and st.session_state.get("asset_scan_chan") == channel_id:
        with st.spinner("Fetching assets..."):
            type_map = {
                "Pinned Messages":        "pinned_messages",
                "Messages with Reactions": "reactions",
                "Starred/Saved Items":    "stars",
            }
            res = fetch_list_data(type_map.get(asset_type), channel_id)

        if res.get("error"):
            err = res["error"]
            if "missing_scope" in err:
                scope_map = {
                    "Pinned Messages":        "`pins:read` and `pins:write`",
                    "Messages with Reactions": "`reactions:read` and `reactions:write`",
                    "Starred/Saved Items":    "`stars:read` and `stars:write`",
                }
                st.warning(
                    f"⚠️ **Missing Slack scope** — add {scope_map.get(asset_type, 'the required scope')} "
                    "to your Slack app (OAuth & Permissions → Bot Token Scopes), then reinstall."
                )
            elif "restricted_action" in err:
                st.warning(
                    "⚠️ **Restricted action** — your Slack workspace admin has restricted this operation. "
                    "Contact your workspace admin to allow this action, or perform it directly in Slack."
                )
            else:
                st.error(f"❌ Error: {err}")
            return

        if res.get("data"):
            items = res["data"]
            st.success(f"Found {len(items)} assets.")
            for i, item in enumerate(items[:20]):
                c1, c2 = st.columns([4, 1.5])
                txt = item.get("text") or item.get("message", {}).get("text", "—")
                ts = item.get("ts") or item.get("message", {}).get("ts")
                c1.markdown(f"**Asset:** {str(txt)[:100]}...")
                if c2.button("❌ Remove", key=f"rem_asset_{i}"):
                    with st.spinner("Removing..."):
                        success = False
                        err_msg = ""
                        if asset_type == "Pinned Messages":
                            r = remove_pin(channel_id, ts)
                            success = r["success"]
                            err_msg = r.get("error", "")
                        elif asset_type == "Messages with Reactions":
                            # reactions is a list of dicts: [{"name": "thumbsup", "count": 1, ...}]
                            reactions = item.get("reactions", [])
                            if reactions and isinstance(reactions[0], dict):
                                reaction_name = reactions[0].get("name", "")
                            elif reactions and isinstance(reactions[0], str):
                                reaction_name = reactions[0]
                            else:
                                reaction_name = ""
                            if reaction_name:
                                r = remove_reaction(channel_id, ts, reaction_name)
                                success = r["success"]
                                err_msg = r.get("error", "")
                            else:
                                st.warning("No reaction name found on this message.")
                        elif asset_type == "Starred/Saved Items":
                            r = remove_star(channel_id, ts)
                            success = r["success"]
                            err_msg = r.get("error", "")

                        if success:
                            st.success("Removed.")
                            time.sleep(0.5)
                            st.rerun()
                        elif "restricted_action" in err_msg:
                            st.warning(
                                "⚠️ **Restricted action** — your workspace admin has restricted this. "
                                "Perform it directly in Slack."
                            )
                        elif "missing_scope" in err_msg:
                            st.warning(f"⚠️ Missing scope: {err_msg}")
                        else:
                            st.error(f"Failed to remove: {err_msg or 'Unknown error'}")
        else:
            st.info(f"No {asset_type} found in this context.")

def _render_topology_logic(action, channel_id, user_opts):
    st.markdown(f"#### ⚙️ Topology Action: {action}")
    
    if action == "Remove User from Channel":
        sel_user_kick = st.selectbox("Select User to Kick", list(user_opts.keys()), key="kick_user_sel")
        if st.button("🚫 Kick User", use_container_width=True, type="primary"):
            res = kick_user_from_channel(channel_id, user_opts[sel_user_kick])
            if res["success"]:
                st.success(f"Successfully removed {sel_user_kick} from channel.")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"Error: {res['error']}")
                
    elif action == "Close DM/Conversation":
        st.warning("This will remove the conversation from your sidebar. It does not delete message history.")
        if st.button("🔒 Close Conversation", use_container_width=True, type="primary"):
            res = close_conversation(channel_id)
            if res["success"]:
                st.success("Conversation closed.")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"Error: {res['error']}")
                
    elif action == "Archive Channel":
        st.error("This will archive the channel and make it read-only for everyone.")
        if st.button("🗑️ Archive Channel", use_container_width=True, type="primary"):
            res = archive_channel(channel_id)
            if res["success"]:
                st.success("Channel archived.")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"Error: {res['error']}")

def _render_trash_section():
    st.subheader("♻️ Recovery")
    msgs = st.session_state.slack_trash.get("messages", [])
    if msgs:
        st.markdown("#### 💬 Message Trash")
        for i, m in enumerate(msgs):
            c1, c2, c3, c4 = st.columns([1, 3, 1, 1])
            c1.caption(m["time"])
            c2.markdown(f"**{m['channel_name']}**: {m['text'][:80]}...")
            if c3.button("🔄 Restore", key=f"rest_msg_{i}"):
                msgs.pop(i); st.success("Restored."); st.rerun()
            if c4.button("🔥 Delete", key=f"del_msg_trash_{i}"):
                if delete_message(m["channel_id"], m["ts"])["success"]:
                    msgs.pop(i); st.success("Permanently Deleted."); st.rerun()

    arch_res = fetch_archived_channels()
    if arch_res.get("data"):
        st.markdown("#### 📁 Channel Trash (Archived)")
        for i, c in enumerate(arch_res["data"]):
            c1, c2 = st.columns([4, 1.5])
            c1.markdown(f"**#{c['name']}** (Archived)")
            if c2.button("🔄 Restore", key=f"conf_unarch_{i}"):
                if unarchive_channel(c['id'])["success"]: st.success("Restored."); st.rerun()

def _render_delete_planner(action: str, entities: dict):
    steps = {
        "Bulk Delete": ["Scanning strategy", "Batching selected items", "Executing API deletes", "Verifying consistency"],
        "Archive Channel": ["Archiving request", "Updating metadata", "Moving to Restore pool"],
        "Kick Member": ["Checking authority", "Removing user", "Revoking access"],
        "Unified Delete": ["Locating cross-category item", "Executing specific delete logic", "Clearing related indexes"]
    }.get(action, ["Analyzing operation", "Executing API"])
    st.markdown(f"""
        <div style="background: rgba(255, 75, 75, 0.05); border-left: 4px solid #ff4b4b; padding: 15px; border-radius: 4px; margin-bottom: 20px;">
            <div style="color: #ff4b4b; font-weight: bold; font-size: 14px; margin-bottom: 8px;">🚀 AI DELETE PLANNER</div>
            <div style="font-size: 13px;">
                <b>Action:</b> {action} <br>
                <b>Entities:</b> {", ".join([f"{k}: {v}" for k, v in entities.items()])} <br>
                <b>Steps:</b><br>{"".join([f"&nbsp;&nbsp;{i+1}. {step}<br>" for i, step in enumerate(steps)])}
            </div>
        </div>""", unsafe_allow_html=True)
