"""
search_workflow.py
------------------
Direct keyword search across the entire Slack workspace.
Type one word → all matching results appear in a table grouped by category.
No dropdowns, no category selection required.
"""

import re
import streamlit as st
from slack.slack_handler import is_slack_authenticated, search_workspace_data


# ── CSS — injected once per render ────────────────────────────────────────────
_POPOVER_CSS = """
<style>
/* Remove the chevron SVG Streamlit adds to every popover button */
[data-testid="stPopover"] button svg {
    display: none !important;
}
/* Square icon-button, perfectly centered ⋮ */
[data-testid="stPopover"] button {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 2rem !important;
    height: 2rem !important;
    min-width: 2rem !important;
    padding: 0 !important;
    font-size: 1.25rem !important;
    font-weight: 900 !important;
    line-height: 1 !important;
    letter-spacing: 0 !important;
    color: #d0d0d0 !important;
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    border-radius: 6px !important;
    cursor: pointer !important;
    flex-shrink: 0 !important;
    transition: background 0.15s, border-color 0.15s !important;
}
[data-testid="stPopover"] button:hover {
    background: rgba(108,99,255,0.18) !important;
    border-color: rgba(108,99,255,0.55) !important;
    color: #fff !important;
}
/* The text node inside the button */
[data-testid="stPopover"] button p,
[data-testid="stPopover"] button span {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-size: 1.25rem !important;
    height: 1.25rem !important;
    line-height: 1 !important;
    font-weight: 900 !important;
    color: inherit !important;
    flex-shrink: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}
</style>
"""

# ── Category config ────────────────────────────────────────────────────────────
_CATEGORIES = {
    "channels": {
        "icon": "📁", "label": "Channels",
        "cols": ["Name", "Members", "Topic"],
    },
    "users": {
        "icon": "👥", "label": "Users",
        "cols": ["Name", "Title", "Email"],
    },
    "messages": {
        "icon": "💬", "label": "Messages",
        "cols": ["Channel", "User", "Message", "Time"],
    },
    "files": {
        "icon": "📎", "label": "Files",
        "cols": ["Name", "Type", "Size KB", "User"],
    },
}


# ── Main renderer ──────────────────────────────────────────────────────────────

def render_search_workflow():
    st.header("🔍 Slack Search")

    if not is_slack_authenticated():
        st.warning("⚠️ Connect your Slack workspace first via the **Settings** tab.")
        return

    # Inject popover CSS
    st.markdown(_POPOVER_CSS, unsafe_allow_html=True)

    # ── Search bar ─────────────────────────────────────────────────────────
    col_q, col_limit, col_btn = st.columns([4, 1.2, 1])

    with col_q:
        query = st.text_input(
            "query",
            placeholder="Type any word — messages, names, channels, files…",
            label_visibility="collapsed",
            key="slack_search_query",
        )

    with col_limit:
        limit_opt = st.selectbox(
            "limit",
            options=[10, 25, 50, 100],
            index=1,
            label_visibility="collapsed",
            key="slack_search_limit",
        )

    with col_btn:
        clicked = st.button("🔍 Search", use_container_width=True, key="slack_search_btn")

    # Trigger on Enter too (query changed)
    prev = st.session_state.get("_slack_prev_query", "")
    if query and query != prev:
        clicked = True
    st.session_state["_slack_prev_query"] = query

    # ── Execute ────────────────────────────────────────────────────────────
    if clicked and query.strip():
        with st.spinner(f'Searching for "{query.strip()}"…'):
            results = search_workspace_data(
                query.strip(),
                limit=limit_opt,
                newest_first=True,
            )
        st.session_state["_slack_results"] = results
        st.session_state["_slack_results_query"] = query.strip()
        st.session_state["_slack_detail_key"] = None

    # ── Render results ─────────────────────────────────────────────────────
    if "_slack_results" in st.session_state:
        _render_results(
            st.session_state["_slack_results"],
            st.session_state.get("_slack_results_query", ""),
        )


# ── Results ────────────────────────────────────────────────────────────────────

def _render_results(results: dict, query: str):
    total = sum(len(v) for v in results.values())

    st.divider()

    if total == 0:
        st.info(
            f'No results found for **"{query}"** across '
            "channels, users, messages, or files."
        )
        return

    st.success(f'**{total}** result(s) found for **"{query}"**')

    for cat, meta in _CATEGORIES.items():
        rows = results.get(cat, [])
        if not rows:
            continue

        # Section heading
        st.markdown(
            f"### {meta['icon']} {meta['label']} "
            f"<span style='font-size:13px;color:#888;font-weight:400'>"
            f"— {len(rows)} result(s)</span>",
            unsafe_allow_html=True,
        )

        cols = meta["cols"]
        n = len(cols)

        # Column widths — last col is the narrow ⋮ button
        if cat == "messages":
            widths = [1.4, 1.2, 4.0, 1.6, 0.55]
        elif cat == "users":
            widths = [2.0, 2.0, 3.0, 0.55]
        elif cat == "channels":
            widths = [2.0, 1.0, 4.0, 0.55]
        else:
            widths = [2.5] * n + [0.55]

        # Header row
        hcols = st.columns(widths)
        for i, c in enumerate(cols):
            hcols[i].markdown(f"**{c}**")
        hcols[-1].markdown("**Details**")

        # Data rows
        for idx, row in enumerate(rows):
            rcols = st.columns(widths)

            for i, col_name in enumerate(cols):
                val = str(row.get(col_name, "—"))
                rcols[i].markdown(_highlight(val, query), unsafe_allow_html=True)

            # ⋮ popover menu
            detail_key = f"{cat}_{idx}"
            with rcols[-1].popover("⋮"):
                if st.button("👁️ View details", key=f"view_{detail_key}",
                             use_container_width=True):
                    current = st.session_state.get("_slack_detail_key")
                    st.session_state["_slack_detail_key"] = (
                        None if current == detail_key else detail_key
                    )
                    st.session_state["_slack_edit_key"] = None  # close edit if open
                    st.rerun()

                if cat == "messages":
                    if st.button("✏️ Edit", key=f"edit_{detail_key}",
                                 use_container_width=True):
                        current = st.session_state.get("_slack_edit_key")
                        st.session_state["_slack_edit_key"] = (
                            None if current == detail_key else detail_key
                        )
                        st.session_state["_slack_detail_key"] = None
                        st.rerun()

                    if st.button("📌 Pin", key=f"pin_{detail_key}",
                                 use_container_width=True):
                        from slack.slack_handler import add_pin
                        r = add_pin(row.get("channel_id", ""), row.get("ts", ""))
                        if r["success"]:
                            st.success("📌 Pinned!")
                        elif "missing_scope" in str(r.get("error", "")):
                            st.warning(
                                "Add **`pins:write`** scope to your Slack app "
                                "(OAuth & Permissions → Bot Token Scopes), "
                                "then reinstall."
                            )
                        else:
                            st.error(r["error"])

                    if st.button("⭐ Star", key=f"star_{detail_key}",
                                 use_container_width=True):
                        from slack.slack_handler import add_star
                        r = add_star(row.get("channel_id", ""), row.get("ts", ""))
                        if r["success"]:
                            st.success("⭐ Starred!")
                        elif "missing_scope" in str(r.get("error", "")):
                            st.warning(
                                "Add **`stars:write`** scope to your Slack app "
                                "(OAuth & Permissions → Bot Token Scopes), "
                                "then reinstall."
                            )
                        elif "deprecated" in str(r.get("error", "")).lower() or \
                             "not_allowed" in str(r.get("error", "")):
                            st.warning(
                                "Starring is not supported on this Slack plan or app type. "
                                "Use the Slack app directly to save messages."
                            )
                        else:
                            st.error(r["error"])

                copy_val = (
                    row.get("_raw")
                    or row.get("Message")
                    or row.get("Name")
                    or row.get("ID", "")
                )
                if st.button("📋 Copy text", key=f"copy_{detail_key}",
                             use_container_width=True):
                    st.session_state[f"_copied_{detail_key}"] = True
                    st.rerun()

            # Show copy confirmation outside the popover (toast-style)
            if st.session_state.pop(f"_copied_{detail_key}", False):
                copy_val = (
                    row.get("_raw")
                    or row.get("Message")
                    or row.get("Name")
                    or row.get("ID", "")
                )
                st.toast("✅ Message copied!", icon="📋")
                # Write to clipboard via JS
                escaped = copy_val.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
                st.markdown(
                    f"<script>navigator.clipboard.writeText(`{escaped}`);</script>",
                    unsafe_allow_html=True,
                )

            # Inline detail panel
            if st.session_state.get("_slack_detail_key") == detail_key:
                _render_detail_panel(row, cat, idx, meta)

            # Inline edit form (messages only)
            if cat == "messages" and st.session_state.get("_slack_edit_key") == detail_key:
                _render_edit_form(row, cat, idx)

            # Row separator
            if idx < len(rows) - 1:
                st.markdown(
                    "<hr style='margin:3px 0;border:none;"
                    "border-top:1px solid #222'>",
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)


def _render_detail_panel(row: dict, cat: str, idx: int, meta: dict):
    """Inline expandable detail card shown below the row."""
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg,rgba(108,99,255,0.09),
                        rgba(167,139,250,0.04));
            border: 1px solid rgba(108,99,255,0.28);
            border-radius: 10px;
            padding: 18px 20px;
            margin: 6px 0 12px 0;
        ">
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"**{meta['icon']} {meta['label']} — Detail**")

    for k, v in row.items():
        if k.startswith("_") or k in ("ts", "channel_id", "user_id"):
            continue
        st.markdown(
            f"<span style='color:#a78bfa;font-weight:600'>{k}:</span> {v}",
            unsafe_allow_html=True,
        )

    raw = row.get("_raw")
    if raw and cat == "messages":
        st.markdown(
            "<span style='color:#a78bfa;font-weight:600'>Full text:</span>",
            unsafe_allow_html=True,
        )
        st.code(raw, language=None)

    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("✖ Close", key=f"close_{cat}_{idx}", use_container_width=False):
        st.session_state["_slack_detail_key"] = None
        st.rerun()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _render_edit_form(row: dict, cat: str, idx: int):
    """Inline edit form for a message — saves via Slack chat.update API."""
    from slack.slack_handler import update_message

    st.markdown(
        """
        <div style="
            background: rgba(108,99,255,0.10);
            border: 1px solid rgba(108,99,255,0.45);
            border-radius: 10px;
            padding: 16px 20px;
            margin: 6px 0 12px 0;
        ">
        """,
        unsafe_allow_html=True,
    )
    st.markdown("**✏️ Edit Message**")

    current_text = row.get("_raw") or row.get("Message", "")
    new_text = st.text_area(
        "Message content",
        value=current_text,
        height=120,
        key=f"edit_area_{cat}_{idx}",
        label_visibility="collapsed",
    )

    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("💾 Save", key=f"save_{cat}_{idx}", use_container_width=True):
            channel_id = row.get("channel_id", "")
            ts = row.get("ts", "")
            if not channel_id or not ts:
                st.error("Cannot edit — channel ID or timestamp missing.")
            else:
                result = update_message(channel_id, ts, new_text)
                if result["success"]:
                    # Update the cached result in session state so the table reflects the change
                    cached = st.session_state.get("_slack_results", {})
                    for r in cached.get(cat, []):
                        if r.get("ts") == ts:
                            preview = new_text[:120] + ("…" if len(new_text) > 120 else "")
                            r["Message"] = preview
                            r["_raw"] = new_text
                    st.session_state["_slack_results"] = cached
                    st.session_state["_slack_edit_key"] = None
                    st.success("✅ Message updated!")
                    st.rerun()
                else:
                    st.error(f"❌ {result['error']}")
    with col_cancel:
        if st.button("✖ Cancel", key=f"cancel_{cat}_{idx}", use_container_width=True):
            st.session_state["_slack_edit_key"] = None
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _highlight(text: str, query: str) -> str:
    """Highlight the query keyword inside a cell value."""
    if not query or not text:
        return text
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(
        lambda m: (
            f"<mark style='background:rgba(108,99,255,0.38);"
            f"color:#e8e8e8;border-radius:3px;padding:0 2px'>"
            f"{m.group()}</mark>"
        ),
        text,
    )
