"""
Delete workflow — Safe Email Deletion.

All delete operations move emails to Trash first (safe delete).
Provides: search → select → confirm → trash, plus trash management.
"""
import streamlit as st

from .gmail_handler import (
    is_gmail_authenticated, search_messages,
    trash_messages, untrash_messages, delete_messages_permanently
)

# ── Lookup tables ──────────────────────────────────────────────────────────────

QUICK_DELETE_FILTERS = {
    "📩 Unread":       "is:unread",
    "🏷️ Promotions":  "category:promotions",
    "👥 Social":       "category:social",
    "⚠️ Spam":         "in:spam",
    "📅 Older 30d":    "older_than:30d",
    "📅 Older 90d":    "older_than:90d",
    "📎 Attachments":  "has:attachment",
    "📝 Drafts":       "in:drafts",
    "🔔 Updates":      "category:updates",
    "📤 Sent":         "in:sent",
}

DATE_PRESETS = {
    "—  No date filter":      "",
    "📅  Today":              "newer_than:1d",
    "📅  Yesterday":          "newer_than:2d older_than:1d",
    "📆  Last 7 days":        "newer_than:7d",
    "📆  Last 30 days":       "newer_than:30d",
    "📆  Older than 30 days": "older_than:30d",
    "📆  Older than 90 days": "older_than:90d",
    "📆  Older than 6 months":"older_than:6m",
    "📆  Older than 1 year":  "older_than:1y",
}

ATTACH_OPTIONS = {
    "—  None":             "",
    "📎  Any attachment":  "has:attachment",
    "📄  PDF":             "filename:pdf",
    "🖼️  Images":         "filename:(jpg OR png OR gif OR jpeg)",
    "🎥  Videos":          "filename:(mp4 OR avi OR mov)",
    "📝  Word docs":       "filename:(doc OR docx)",
    "📊  Excel / CSV":     "filename:(xls OR xlsx OR csv)",
    "🗜️  ZIP / Archive":  "filename:(zip OR rar OR 7z)",
}

STATUS_OPTIONS = {
    "—  Any":       "",
    "📩  Unread":   "is:unread",
    "📬  Read":     "is:read",
    "⭐  Starred":  "is:starred",
    "❗  Important": "is:important",
}

CATEGORY_OPTIONS = {
    "—  Any":           "",
    "📬  Primary":      "category:primary",
    "👥  Social":       "category:social",
    "🏷️  Promotions":  "category:promotions",
    "🔔  Updates":      "category:updates",
    "💬  Forums":       "category:forums",
}


# ── Main renderer ──────────────────────────────────────────────────────────────

def render_delete_workflow():
    """Render the delete workflow tab."""
    st.header("🗑️ Delete — Safe Email Deletion")

    if not is_gmail_authenticated():
        st.warning(
            "Gmail is not authenticated. Go to **Settings** tab first.",
            icon="⚠️",
        )
        return

    # Safety banner
    st.markdown(
        """<div style="
            background: linear-gradient(135deg, rgba(239,68,68,0.08), rgba(251,146,60,0.05));
            border: 1px solid rgba(239,68,68,0.25); border-radius: 10px;
            padding: 12px 18px; margin-bottom: 16px;
        "><span style="font-size:15px;">
            🛡️ <b>Safe Mode</b> — All deletes move emails to <b>Trash</b> first.
            You can restore them anytime.
        </span></div>""",
        unsafe_allow_html=True,
    )

    # ── Step 1: Find emails ────────────────────────────────────────────────
    st.subheader("Step 1 · Find Emails")

    col_s, col_c, col_b = st.columns([4, 0.8, 1])
    with col_s:
        search_text = st.text_input(
            "Search", placeholder="Type keywords or Gmail syntax …",
            key="del_search", label_visibility="collapsed",
        )
    with col_c:
        max_res = st.selectbox("Count", [5, 10, 15, 20, 30, 50], index=1, key="del_count")
    with col_b:
        find_clicked = st.button("🔍 Find", use_container_width=True, key="del_find_btn")

    # Quick filters
    st.markdown("**Quick Filters:**")
    qf = list(QUICK_DELETE_FILTERS.items())
    quick_q = None
    for row_items in [qf[:5], qf[5:]]:
        cols = st.columns(5)
        for i, (label, query) in enumerate(row_items):
            with cols[i]:
                if st.button(label, key=f"dqf_{label}", use_container_width=True):
                    quick_q = query

    # Advanced filters
    adv_parts = _render_filters()

    # Execute find
    pending = None
    if quick_q:
        pending = quick_q
    elif find_clicked:
        parts = []
        if search_text.strip():
            parts.append(search_text.strip())
        parts.extend(adv_parts)
        pending = " ".join(parts) if parts else None
        if not pending:
            st.warning("Enter a query or select a filter first.")

    if pending:
        with st.spinner(f"Searching: `{pending}` …"):
            result = search_messages(query=pending, max_results=max_res)
        if not result["success"]:
            st.error(f"❌ {result['error']}")
        else:
            st.session_state.del_results = result["messages"]
            st.session_state.del_query = result.get("query", pending)
            st.session_state.del_total = result.get("total_estimate", 0)
            # Reset selections
            _clear_selections(result["messages"])

    # ── Step 2: Review & Select ────────────────────────────────────────────
    _render_review()

    # ── Trash management ───────────────────────────────────────────────────
    st.divider()
    _render_trash_management()


# ── Advanced filters ───────────────────────────────────────────────────────────

def _render_filters() -> list[str]:
    """Render advanced filters and return query parts."""
    parts: list[str] = []
    with st.expander("🔧 Advanced Filters", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            from_v = st.text_input("From", placeholder="e.g. rahul@gmail.com", key="df_from")
        with c2:
            subj_v = st.text_input("Subject", placeholder="e.g. Invoice", key="df_subj")

        c3, c4, c5 = st.columns(3)
        with c3:
            date_k = st.selectbox("Date", list(DATE_PRESETS.keys()), index=0, key="df_date")
        with c4:
            attach_k = st.selectbox("Attachment", list(ATTACH_OPTIONS.keys()), index=0, key="df_att")
        with c5:
            status_k = st.selectbox("Status", list(STATUS_OPTIONS.keys()), index=0, key="df_stat")

        c6, c7 = st.columns(2)
        with c6:
            cat_k = st.selectbox("Category", list(CATEGORY_OPTIONS.keys()), index=0, key="df_cat")
        with c7:
            excl_v = st.text_input("Exclude words", placeholder="e.g. newsletter", key="df_excl")

        # Build parts
        if from_v.strip():
            parts.append(f"from:({from_v.strip()})")
        if subj_v.strip():
            parts.append(f"subject:({subj_v.strip()})")
        if excl_v.strip():
            for w in excl_v.strip().split():
                parts.append(f"-{w}")

        for val in [DATE_PRESETS.get(date_k, ""), ATTACH_OPTIONS.get(attach_k, ""),
                     STATUS_OPTIONS.get(status_k, ""), CATEGORY_OPTIONS.get(cat_k, "")]:
            if val:
                parts.append(val)

        if parts:
            st.code(f"Query: {' '.join(parts)}", language=None)

        if st.button("🔍 Apply Filters", use_container_width=True, key="df_apply"):
            st.session_state.del_filter_apply = True

    # Handle apply button from inside expander
    if st.session_state.pop("del_filter_apply", False):
        if parts:
            with st.spinner(f"Searching: `{' '.join(parts)}` …"):
                result = search_messages(query=" ".join(parts),
                                         max_results=st.session_state.get("del_count", 10))
            if result["success"]:
                st.session_state.del_results = result["messages"]
                st.session_state.del_query = result.get("query", "")
                st.session_state.del_total = result.get("total_estimate", 0)
                _clear_selections(result["messages"])
            else:
                st.error(f"❌ {result['error']}")

    return parts


# ── Review & select ────────────────────────────────────────────────────────────

def _clear_selections(messages: list[dict]):
    """Reset all checkbox selections."""
    for msg in messages:
        st.session_state[f"dsel_{msg['id']}"] = False
    st.session_state.pop("del_confirm", None)


def _render_review():
    """Render results table with checkboxes for selection."""
    messages = st.session_state.get("del_results")
    if messages is None:
        return

    query = st.session_state.get("del_query", "")
    total = st.session_state.get("del_total", 0)

    if not messages:
        st.info(f'No emails found for **"{query}"**')
        return

    st.divider()
    st.subheader("Step 2 · Review & Select")

    showing = len(messages)
    if total > showing:
        st.info(f"📋 Showing **{showing}** of ~**{total}** results for: `{query}`")
    else:
        st.info(f"📋 Found **{showing}** email(s) for: `{query}`")

    # Select / Deselect all
    sa_col, da_col, _ = st.columns([1, 1, 4])
    with sa_col:
        if st.button("☑ Select All", key="del_sel_all", use_container_width=True):
            for msg in messages:
                st.session_state[f"dsel_{msg['id']}"] = True
            st.rerun()
    with da_col:
        if st.button("☐ Deselect All", key="del_desel_all", use_container_width=True):
            for msg in messages:
                st.session_state[f"dsel_{msg['id']}"] = False
            st.rerun()

    # Table header
    hcols = st.columns([0.3, 0.3, 1.8, 1.2, 2, 2.5])
    for col, h in zip(hcols, ["✓", "#", "From", "Date", "Subject", "Preview"]):
        col.markdown(f"**{h}**")

    # Table rows
    selected_ids = []
    for idx, msg in enumerate(messages):
        rcols = st.columns([0.3, 0.3, 1.8, 1.2, 2, 2.5])
        with rcols[0]:
            checked = st.checkbox("", key=f"dsel_{msg['id']}", label_visibility="collapsed")
            if checked:
                selected_ids.append(msg["id"])
        with rcols[1]:
            st.write(f"{idx + 1}")
        with rcols[2]:
            name = msg["from_name"]
            if msg["from_email"] and msg["from_email"] != msg["from_name"]:
                name += f"\n_{msg['from_email']}_"
            st.markdown(name)
        with rcols[3]:
            st.write(msg["date"])
        with rcols[4]:
            subj = msg["subject"]
            st.write(subj[:40] + "..." if len(subj) > 40 else subj)
        with rcols[5]:
            st.caption(msg["body_preview"] or "_(empty)_")

        if idx < len(messages) - 1:
            st.markdown(
                "<hr style='margin:2px 0;border:none;border-top:1px solid #2a2a2a'>",
                unsafe_allow_html=True,
            )

    # ── Step 3: Confirm & delete ───────────────────────────────────────────
    st.divider()
    count = len(selected_ids)
    st.markdown(f"**Selected: {count} email(s)**")

    if count == 0:
        st.caption("Select emails above to enable deletion.")
        return

    st.subheader("Step 3 · Confirm & Delete")

    # Confirmation gate
    confirm = st.session_state.get("del_confirm", False)

    if not confirm:
        st.warning(
            f"You are about to move **{count}** email(s) to Trash.",
            icon="⚠️",
        )
        if st.button(
            f"🗑️ Move {count} Email(s) to Trash",
            use_container_width=True,
            key="del_trash_btn",
            type="primary",
        ):
            st.session_state.del_confirm = True
            st.session_state.del_pending_ids = selected_ids
            st.rerun()
    else:
        # Final confirmation
        pending_ids = st.session_state.get("del_pending_ids", [])
        st.error(
            f"⛔ **FINAL CONFIRMATION** — Move **{len(pending_ids)}** email(s) to Trash?",
            icon="🗑️",
        )

        c_yes, c_no = st.columns(2)
        with c_yes:
            if st.button(
                "✅ Yes, Move to Trash",
                use_container_width=True,
                key="del_confirm_yes",
                type="primary",
            ):
                with st.spinner("Moving emails to Trash…"):
                    result = trash_messages(pending_ids)
                if result["success"]:
                    st.session_state.del_last_result = result
                    st.session_state.del_results = None
                    st.session_state.pop("del_confirm", None)
                    st.session_state.pop("del_pending_ids", None)
                    st.rerun()
                else:
                    st.error(f"❌ Failed: {result['error']}")
        with c_no:
            if st.button("❌ Cancel", use_container_width=True, key="del_confirm_no"):
                st.session_state.pop("del_confirm", None)
                st.session_state.pop("del_pending_ids", None)
                st.rerun()

    # Show last result
    last = st.session_state.get("del_last_result")
    if last:
        st.success(
            f"✅ Successfully moved **{last['trashed_count']}** email(s) to Trash!"
            + (f" ({last['failed_count']} failed)" if last["failed_count"] else "")
        )
        if st.button("Clear result", key="del_clear_result"):
            st.session_state.pop("del_last_result", None)
            st.rerun()


# ── Trash management ───────────────────────────────────────────────────────────

def _render_trash_management():
    """View trash and restore emails."""
    st.subheader("📋 Trash Management")

    tc1, tc2 = st.columns(2)
    with tc1:
        trash_count = st.selectbox("Show", [5, 10, 20], index=1, key="trash_count")
    with tc2:
        st.write("")
        st.write("")
        view_trash = st.button("📋 View Trash", use_container_width=True, key="trash_view_btn")

    if view_trash:
        with st.spinner("Loading Trash…"):
            result = search_messages(query="in:trash", max_results=trash_count)
        if result["success"]:
            st.session_state.trash_items = result["messages"]
            # reset selections
            for msg in result["messages"]:
                st.session_state[f"tsel_{msg['id']}"] = False
        else:
            st.error(f"❌ {result['error']}")

    trash_items = st.session_state.get("trash_items")
    if trash_items is None:
        st.caption("Click **📋 View Trash** to see deleted emails.")
        return

    if not trash_items:
        st.info("🎉 Trash is empty!")
        return

    st.info(f"🗑️ Showing **{len(trash_items)}** item(s) in Trash")

    # Select all / deselect all for trash
    ta1, ta2, _ = st.columns([1, 1, 4])
    with ta1:
        if st.button("☑ Select All", key="trash_sel_all", use_container_width=True):
            for m in trash_items:
                st.session_state[f"tsel_{m['id']}"] = True
            st.rerun()
    with ta2:
        if st.button("☐ Deselect All", key="trash_desel_all", use_container_width=True):
            for m in trash_items:
                st.session_state[f"tsel_{m['id']}"] = False
            st.rerun()

    # Trash table
    t_selected = []
    for idx, msg in enumerate(trash_items):
        rcols = st.columns([0.3, 0.3, 2, 1.2, 2.5, 2.5])
        with rcols[0]:
            if st.checkbox("", key=f"tsel_{msg['id']}", label_visibility="collapsed"):
                t_selected.append(msg["id"])
        with rcols[1]:
            st.write(f"{idx + 1}")
        with rcols[2]:
            st.markdown(msg["from_name"])
        with rcols[3]:
            st.write(msg["date"])
        with rcols[4]:
            subj = msg["subject"]
            st.write(subj[:40] + "..." if len(subj) > 40 else subj)
        with rcols[5]:
            st.caption(msg["body_preview"] or "_(empty)_")

    # Restore / Delete Forever buttons
    if t_selected:
        st.markdown(f"**Selected: {len(t_selected)} email(s)**")
        
        c_restore, c_forever = st.columns(2)
        with c_restore:
            if st.button(
                f"♻️ Restore {len(t_selected)} Email(s)",
                use_container_width=True,
                key="trash_restore_btn",
                type="primary",
            ):
                with st.spinner("Restoring…"):
                    result = untrash_messages(t_selected)
                if result["success"]:
                    st.success(f"✅ Restored **{result['restored_count']}** email(s)!")
                    st.session_state.trash_items = None
                    st.rerun()
                else:
                    st.error(f"❌ {result['error']}")
                    
        with c_forever:
            if st.button(
                f"🔥 Delete Forever",
                use_container_width=True,
                key="trash_forever_btn",
            ):
                with st.spinner("Deleting permanently…"):
                    result = delete_messages_permanently(t_selected)
                if result["success"]:
                    st.success(f"✅ Permanently deleted **{result['deleted_count']}** email(s)!")
                    st.session_state.trash_items = None
                    st.rerun()
                else:
                    st.error(f"❌ {result['error']}")
    else:
        st.caption("Select emails above to restore them from Trash or delete them permanently.")
