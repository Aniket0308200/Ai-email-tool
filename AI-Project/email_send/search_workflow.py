"""
Search workflow — Gmail Advanced Search.

Streamlit UI for searching Gmail messages using free-text queries,
quick-filter buttons, and a structured advanced-filter panel.
Results are displayed in the same tabular format as the Inbox listing.
"""
import streamlit as st
from datetime import date, timedelta

from .gmail_handler import is_gmail_authenticated, search_messages


# ── Lookup tables ──────────────────────────────────────────────────────────────

QUICK_FILTERS = {
    "📩 Unread":        "is:unread",
    "⭐ Starred":       "is:starred",
    "📎 Attachments":   "has:attachment",
    "📅 Today":         "newer_than:1d",
    "📆 This Week":     "newer_than:7d",
    "❗ Important":      "is:important",
    "📤 Sent by me":    "in:sent",
    "📝 Drafts":        "in:drafts",
    "⚠️ Spam":          "in:spam",
    "🗑️ Trash":         "in:trash",
}

ATTACHMENT_OPTIONS = {
    "—  None":              "",
    "📎  Any attachment":   "has:attachment",
    "📄  PDF":              "filename:pdf",
    "🖼️  Images":          "filename:(jpg OR png OR gif OR jpeg OR webp)",
    "🎥  Videos":           "filename:(mp4 OR avi OR mov OR mkv)",
    "📝  Word docs":        "filename:(doc OR docx)",
    "📊  Excel / CSV":      "filename:(xls OR xlsx OR csv)",
    "📑  PowerPoint":       "filename:(ppt OR pptx)",
    "🗜️  ZIP / Archive":   "filename:(zip OR rar OR 7z OR tar OR gz)",
    "📁  Google Drive":     "has:drive",
    "▶️  YouTube links":    "has:youtube",
}

STATUS_OPTIONS = {
    "—  Any":        "",
    "📩  Unread":    "is:unread",
    "📬  Read":      "is:read",
    "⭐  Starred":   "is:starred",
    "☆  Unstarred":  "-is:starred",
    "❗  Important":  "is:important",
    "🔇  Muted":     "is:muted",
    "😴  Snoozed":   "is:snoozed",
}

CATEGORY_OPTIONS = {
    "—  Any":            "",
    "📬  Primary":       "category:primary",
    "👥  Social":        "category:social",
    "🏷️  Promotions":   "category:promotions",
    "🔔  Updates":       "category:updates",
    "💬  Forums":        "category:forums",
}

SEARCH_IN_OPTIONS = {
    "📁  All Mail":   "",
    "📥  Inbox":      "in:inbox",
    "📤  Sent":       "in:sent",
    "📝  Drafts":     "in:drafts",
    "⚠️  Spam":       "in:spam",
    "🗑️  Trash":      "in:trash",
    "⭐  Starred":    "is:starred",
    "🗂️  Anywhere":   "in:anywhere",
}

SIZE_OPERATORS = {
    "—  Any":          "",
    "📈  Larger than":  "larger",
    "📉  Smaller than": "smaller",
}

SIZE_UNITS = ["KB", "MB"]


# ── Top-level renderer ─────────────────────────────────────────────────────────

def render_search_workflow():
    """Render the Gmail search workflow tab."""
    st.header("🔍 Search — Gmail Search")

    if not is_gmail_authenticated():
        st.warning(
            "Gmail is not authenticated. Please connect your Gmail in the **Settings** tab first.",
            icon="⚠️",
        )
        return

    # ── Search bar row ─────────────────────────────────────────────────────
    col_search, col_count, col_btn = st.columns([4, 0.8, 1])

    with col_search:
        search_text = st.text_input(
            "Search query",
            placeholder="Type keywords, names, or use Gmail syntax (e.g. from:user@mail.com subject:invoice)…",
            key="search_text_input",
            label_visibility="collapsed",
        )

    with col_count:
        max_results = st.selectbox(
            "Results",
            options=[5, 10, 15, 20, 30, 50],
            index=1,
            key="search_max_results",
        )

    with col_btn:
        search_clicked = st.button("🔍 Search", use_container_width=True, key="search_btn")

    # ── Quick filters ──────────────────────────────────────────────────────
    st.markdown("**Quick Filters:**")
    qf_items = list(QUICK_FILTERS.items())
    quick_query = None

    # Row 1 — first 5
    qf_row1 = st.columns(5)
    for i, (label, query) in enumerate(qf_items[:5]):
        with qf_row1[i]:
            if st.button(label, key=f"qf_{i}", use_container_width=True):
                quick_query = query

    # Row 2 — next 5
    qf_row2 = st.columns(5)
    for i, (label, query) in enumerate(qf_items[5:]):
        with qf_row2[i]:
            if st.button(label, key=f"qf_{i + 5}", use_container_width=True):
                quick_query = query

    # ── Advanced filters ───────────────────────────────────────────────────
    adv_query_parts, apply_filters_clicked = _render_advanced_filters()

    # ── Execute search ─────────────────────────────────────────────────────
    # Determine the final query
    pending_query = None

    if quick_query:
        # Quick-filter click → immediate search with that query
        pending_query = quick_query

    elif search_clicked or apply_filters_clicked:
        # Combine search bar text + advanced filter parts
        parts = []
        if search_text.strip():
            parts.append(search_text.strip())
        parts.extend(adv_query_parts)
        pending_query = " ".join(parts) if parts else None

        if pending_query is None:
            st.warning("Please enter a search query or select at least one filter.")

    if pending_query:
        with st.spinner(f"Searching: `{pending_query}` …"):
            result = search_messages(query=pending_query, max_results=max_results)

        if not result["success"]:
            st.error(f"❌ Search failed: {result['error']}")
        else:
            st.session_state.search_results = result["messages"]
            st.session_state.search_view_idx = None
            st.session_state.search_last_query = result.get("query", pending_query)
            st.session_state.search_total_estimate = result.get("total_estimate", 0)

    # ── Display results ────────────────────────────────────────────────────
    _render_results()

    # ── Examples & help ────────────────────────────────────────────────────
    st.divider()
    _render_search_examples()


# ── Date range presets ─────────────────────────────────────────────────────────

DATE_RANGE_OPTIONS = {
    "—  No date filter":  "",
    "📅  Today":          "newer_than:1d",
    "📅  Yesterday":      "newer_than:2d older_than:1d",
    "📆  Last 7 days":    "newer_than:7d",
    "📆  Last 30 days":   "newer_than:30d",
    "📆  Last 3 months":  "newer_than:3m",
    "📆  Last 6 months":  "newer_than:6m",
    "📆  Last year":      "newer_than:1y",
    "🔧  Custom range":   "__custom__",
}


# ── Advanced filter panel ──────────────────────────────────────────────────────

def _render_advanced_filters() -> tuple[list[str], bool]:
    """
    Render the advanced filter expander.

    Returns:
        (query_parts, apply_clicked)
        - query_parts: list of Gmail query fragments built from the filter fields.
        - apply_clicked: True when the user pressed the Apply button inside the
          expander, signalling the caller to execute the search immediately.
    """
    parts: list[str] = []
    apply_clicked = False

    with st.expander("🔧 Advanced Filters", expanded=False):
        # Row 1: From / To
        c1, c2 = st.columns(2)
        with c1:
            from_val = st.text_input(
                "From (sender)",
                placeholder="e.g. rahul@gmail.com",
                key="af_from",
            )
        with c2:
            to_val = st.text_input(
                "To (recipient)",
                placeholder="e.g. priya@gmail.com",
                key="af_to",
            )

        # Row 2: Subject / Has words
        c3, c4 = st.columns(2)
        with c3:
            subject_val = st.text_input(
                "Subject contains",
                placeholder="e.g. Project Update",
                key="af_subject",
            )
        with c4:
            has_words = st.text_input(
                "Has words (body)",
                placeholder="e.g. invoice payment",
                key="af_has_words",
            )

        # Row 3: Doesn't have / Label
        c5, c6 = st.columns(2)
        with c5:
            exclude_val = st.text_input(
                "Doesn't have words",
                placeholder="e.g. newsletter",
                key="af_exclude",
            )
        with c6:
            label_val = st.text_input(
                "Label",
                placeholder="e.g. work, personal",
                key="af_label",
            )

        # Row 4: Date range — preset dropdown
        st.markdown("**Date range:**")
        date_key = st.selectbox(
            "Date filter",
            list(DATE_RANGE_OPTIONS.keys()),
            index=0,
            key="af_date_preset",
        )

        date_query = DATE_RANGE_OPTIONS.get(date_key, "")

        # Show custom date pickers only when "Custom range" is selected
        if date_query == "__custom__":
            date_query = ""  # reset; will be built from pickers
            dc1, dc2 = st.columns(2)
            with dc1:
                after_date = st.date_input(
                    "After (start date)",
                    value=date.today() - timedelta(days=30),
                    min_value=date(2004, 1, 1),
                    max_value=date.today(),
                    key="af_after",
                )
            with dc2:
                before_date = st.date_input(
                    "Before (end date)",
                    value=date.today(),
                    min_value=date(2004, 1, 1),
                    max_value=date.today() + timedelta(days=1),
                    key="af_before",
                )
            if after_date:
                date_query += f"after:{after_date.strftime('%Y/%m/%d')} "
            if before_date:
                date_query += f"before:{before_date.strftime('%Y/%m/%d')}"
            date_query = date_query.strip()

        # Row 5: Attachment / Status / Category
        f1, f2, f3 = st.columns(3)
        with f1:
            attach_key = st.selectbox(
                "Attachment type",
                list(ATTACHMENT_OPTIONS.keys()),
                index=0,
                key="af_attach",
            )
        with f2:
            status_key = st.selectbox(
                "Message status",
                list(STATUS_OPTIONS.keys()),
                index=0,
                key="af_status",
            )
        with f3:
            cat_key = st.selectbox(
                "Category",
                list(CATEGORY_OPTIONS.keys()),
                index=0,
                key="af_category",
            )

        # Row 6: Search in / Size
        g1, g2, g3, g4 = st.columns([1.2, 1, 0.8, 0.6])
        with g1:
            search_in_key = st.selectbox(
                "Search in",
                list(SEARCH_IN_OPTIONS.keys()),
                index=0,
                key="af_search_in",
            )
        with g2:
            size_op_key = st.selectbox(
                "Size filter",
                list(SIZE_OPERATORS.keys()),
                index=0,
                key="af_size_op",
            )
        with g3:
            size_val = st.number_input(
                "Size",
                min_value=0,
                value=0,
                step=1,
                key="af_size_val",
            )
        with g4:
            size_unit = st.selectbox("Unit", SIZE_UNITS, index=1, key="af_size_unit")

        # ── Build query parts from the fields ──────────────────────────────
        if from_val.strip():
            parts.append(f"from:({from_val.strip()})")
        if to_val.strip():
            parts.append(f"to:({to_val.strip()})")
        if subject_val.strip():
            parts.append(f"subject:({subject_val.strip()})")
        if has_words.strip():
            parts.append(has_words.strip())
        if exclude_val.strip():
            for word in exclude_val.strip().split():
                parts.append(f"-{word}")
        if label_val.strip():
            for lbl in label_val.strip().split(","):
                lbl = lbl.strip().replace(" ", "-")
                if lbl:
                    parts.append(f"label:{lbl}")
        if date_query:
            parts.append(date_query)

        attach_q = ATTACHMENT_OPTIONS.get(attach_key, "")
        if attach_q:
            parts.append(attach_q)

        status_q = STATUS_OPTIONS.get(status_key, "")
        if status_q:
            parts.append(status_q)

        cat_q = CATEGORY_OPTIONS.get(cat_key, "")
        if cat_q:
            parts.append(cat_q)

        search_in_q = SEARCH_IN_OPTIONS.get(search_in_key, "")
        if search_in_q:
            parts.append(search_in_q)

        size_op_q = SIZE_OPERATORS.get(size_op_key, "")
        if size_op_q and size_val and size_val > 0:
            unit_suffix = "K" if size_unit == "KB" else "M"
            parts.append(f"{size_op_q}:{size_val}{unit_suffix}")

        # ── Query preview + Apply button ───────────────────────────────────
        st.divider()
        if parts:
            preview = " ".join(parts)
            st.code(f"Query preview:  {preview}", language=None)
        else:
            st.caption("Fill in any field above to build a search query.")

        apply_clicked = st.button(
            "🔍 Apply Filters & Search",
            use_container_width=True,
            key="af_apply_btn",
        )

    return parts, apply_clicked


# ── Results display ────────────────────────────────────────────────────────────

def _render_results():
    """Render search results in tabular format."""
    messages = st.session_state.get("search_results")

    if messages is None:
        return  # no search executed yet

    last_query = st.session_state.get("search_last_query", "")
    total = st.session_state.get("search_total_estimate", 0)

    if not messages:
        st.info(f'No results found for **"{last_query}"**')
        return

    st.divider()

    # Summary
    showing = len(messages)
    if total > showing:
        st.success(f"✅ Showing **{showing}** of ~**{total}** results for: `{last_query}`")
    else:
        st.success(f"✅ Found **{showing}** result(s) for: `{last_query}`")

    # ── Table header ───────────────────────────────────────────────────────
    header_cols = st.columns([0.4, 2, 1.5, 2, 3, 0.8])
    headers = ["#", "From", "Date & Time", "Subject", "Body Preview", "Action"]
    for col, h in zip(header_cols, headers):
        col.markdown(f"**{h}**")

    # ── Table rows ─────────────────────────────────────────────────────────
    for idx, msg in enumerate(messages):
        row_cols = st.columns([0.4, 2, 1.5, 2, 3, 0.8])

        with row_cols[0]:
            st.write(f"{idx + 1}")

        with row_cols[1]:
            from_display = msg["from_name"]
            if msg["from_email"] and msg["from_email"] != msg["from_name"]:
                from_display += f"\n_{msg['from_email']}_"
            st.markdown(from_display)

        with row_cols[2]:
            st.write(msg["date"])

        with row_cols[3]:
            subject_display = msg["subject"]
            if len(subject_display) > 45:
                subject_display = subject_display[:45] + "..."
            st.write(subject_display)

        with row_cols[4]:
            st.caption(msg["body_preview"] or "_(empty)_")

        with row_cols[5]:
            if st.button("👁️", key=f"sv_msg_{idx}", help="View full email"):
                st.session_state.search_view_idx = idx

        # Light separator
        if idx < len(messages) - 1:
            st.markdown(
                "<hr style='margin:2px 0; border:none; border-top:1px solid #2a2a2a'>",
                unsafe_allow_html=True,
            )

    # ── Full message viewer ────────────────────────────────────────────────
    view_idx = st.session_state.get("search_view_idx")
    if view_idx is not None and 0 <= view_idx < len(messages):
        st.divider()
        _render_full_message(messages[view_idx], view_idx)


def _render_full_message(msg: dict, idx: int):
    """Render the full email body in a styled container."""
    st.subheader(f"📧 Message #{idx + 1}")

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, rgba(108,99,255,0.08), rgba(167,139,250,0.04));
            border: 1px solid rgba(108,99,255,0.25);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 12px;
        ">
            <div style="margin-bottom: 8px;">
                <strong style="color:#a78bfa;">From:</strong>
                <span>{msg['from_name']} &lt;{msg['from_email']}&gt;</span>
            </div>
            <div style="margin-bottom: 8px;">
                <strong style="color:#a78bfa;">Date:</strong>
                <span>{msg['date']}</span>
            </div>
            <div style="margin-bottom: 8px;">
                <strong style="color:#a78bfa;">Subject:</strong>
                <span>{msg['subject']}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("**Full Message:**")
    body_text = msg["body_full"] if msg["body_full"] else "_(No text content available)_"
    st.text_area(
        "Email body",
        value=body_text,
        height=300,
        disabled=True,
        key=f"search_full_body_{idx}",
        label_visibility="collapsed",
    )

    col_gmail, col_close = st.columns(2)
    with col_gmail:
        st.link_button("📧 Open in Gmail", url=msg["gmail_link"], use_container_width=True)
    with col_close:
        if st.button("✖ Close Viewer", key=f"search_close_{idx}", use_container_width=True):
            st.session_state.search_view_idx = None
            st.rerun()


# ── Search examples & help ─────────────────────────────────────────────────────

def _render_search_examples():
    """Show categorised example queries to teach users the search syntax."""
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, rgba(108,99,255,0.06), rgba(167,139,250,0.03));
            border: 1px solid rgba(108,99,255,0.15);
            border-radius: 10px;
            padding: 18px 22px;
        ">
            <p style="font-weight:600; color:#a78bfa; margin-bottom:12px; font-size:15px;">
                💡 Search Examples — type these in the search bar:
            </p>
            <table style="width:100%; border-collapse:collapse; font-size:13px; line-height:1.7;">
                <tr style="border-bottom:1px solid rgba(108,99,255,0.12);">
                    <td style="padding:6px 8px; color:#888; width:25%;">🔤 <b>Keyword</b></td>
                    <td style="padding:6px 8px;"><code>invoice</code> &nbsp;|&nbsp; <code>"project update"</code> &nbsp;|&nbsp; <code>meeting OR standup</code></td>
                </tr>
                <tr style="border-bottom:1px solid rgba(108,99,255,0.12);">
                    <td style="padding:6px 8px; color:#888;">👤 <b>Sender / Receiver</b></td>
                    <td style="padding:6px 8px;"><code>from:rahul</code> &nbsp;|&nbsp; <code>to:priya@gmail.com</code> &nbsp;|&nbsp; <code>cc:boss@corp.com</code></td>
                </tr>
                <tr style="border-bottom:1px solid rgba(108,99,255,0.12);">
                    <td style="padding:6px 8px; color:#888;">📌 <b>Subject</b></td>
                    <td style="padding:6px 8px;"><code>subject:invoice</code> &nbsp;|&nbsp; <code>subject:(project update)</code></td>
                </tr>
                <tr style="border-bottom:1px solid rgba(108,99,255,0.12);">
                    <td style="padding:6px 8px; color:#888;">📅 <b>Date / Time</b></td>
                    <td style="padding:6px 8px;"><code>newer_than:1d</code> &nbsp;|&nbsp; <code>older_than:3m</code> &nbsp;|&nbsp; <code>after:2025/01/01 before:2025/06/01</code></td>
                </tr>
                <tr style="border-bottom:1px solid rgba(108,99,255,0.12);">
                    <td style="padding:6px 8px; color:#888;">📎 <b>Attachments</b></td>
                    <td style="padding:6px 8px;"><code>has:attachment</code> &nbsp;|&nbsp; <code>filename:pdf</code> &nbsp;|&nbsp; <code>filename:(jpg OR png)</code></td>
                </tr>
                <tr style="border-bottom:1px solid rgba(108,99,255,0.12);">
                    <td style="padding:6px 8px; color:#888;">📊 <b>Status</b></td>
                    <td style="padding:6px 8px;"><code>is:unread</code> &nbsp;|&nbsp; <code>is:starred</code> &nbsp;|&nbsp; <code>is:important</code> &nbsp;|&nbsp; <code>in:drafts</code></td>
                </tr>
                <tr style="border-bottom:1px solid rgba(108,99,255,0.12);">
                    <td style="padding:6px 8px; color:#888;">🏷️ <b>Category / Label</b></td>
                    <td style="padding:6px 8px;"><code>category:promotions</code> &nbsp;|&nbsp; <code>category:social</code> &nbsp;|&nbsp; <code>label:work</code></td>
                </tr>
                <tr style="border-bottom:1px solid rgba(108,99,255,0.12);">
                    <td style="padding:6px 8px; color:#888;">📐 <b>Size</b></td>
                    <td style="padding:6px 8px;"><code>larger:5M</code> &nbsp;|&nbsp; <code>smaller:100K</code></td>
                </tr>
                <tr style="border-bottom:1px solid rgba(108,99,255,0.12);">
                    <td style="padding:6px 8px; color:#888;">🔗 <b>Special</b></td>
                    <td style="padding:6px 8px;"><code>has:drive</code> &nbsp;|&nbsp; <code>has:youtube</code> &nbsp;|&nbsp; <code>in:anywhere</code></td>
                </tr>
                <tr style="border-bottom:1px solid rgba(108,99,255,0.12);">
                    <td style="padding:6px 8px; color:#888;">🔐 <b>Security</b></td>
                    <td style="padding:6px 8px;"><code>subject:OTP</code> &nbsp;|&nbsp; <code>subject:"security alert"</code> &nbsp;|&nbsp; <code>subject:"password reset"</code></td>
                </tr>
                <tr style="border-bottom:1px solid rgba(108,99,255,0.12);">
                    <td style="padding:6px 8px; color:#888;">💼 <b>Business</b></td>
                    <td style="padding:6px 8px;"><code>subject:invoice</code> &nbsp;|&nbsp; <code>subject:receipt</code> &nbsp;|&nbsp; <code>subject:interview</code></td>
                </tr>
                <tr>
                    <td style="padding:6px 8px; color:#888;">🧠 <b>Advanced (Boolean)</b></td>
                    <td style="padding:6px 8px;"><code>from:rahul subject:meeting has:attachment</code> &nbsp;|&nbsp; <code>{invoice OR receipt} -newsletter</code></td>
                </tr>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )
