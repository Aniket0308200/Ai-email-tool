"""
Inbox message listing workflow.

Streamlit UI for fetching and displaying recent Gmail inbox messages
in a structured tabular format with full-body viewer.
"""
import streamlit as st

from .gmail_handler import is_gmail_authenticated, list_messages


# ── Top-level renderer ─────────────────────────────────────────────────────────

def render_inbox_workflow():
    """Render the inbox message listing workflow."""
    st.header("📥 Inbox — Message Listing")

    # Auth check
    if not is_gmail_authenticated():
        st.warning(
            "Gmail is not authenticated. Please connect your Gmail in the **Settings** tab first.",
            icon="⚠️",
        )
        return

    # ── Category → Gmail label mapping ──────────────────────────────────────
    CATEGORY_MAP = {
        "📥 All Inbox":    ["INBOX"],
        "📬 Primary":      ["INBOX", "CATEGORY_PERSONAL"],
        "🏷️ Promotions":   ["INBOX", "CATEGORY_PROMOTIONS"],
        "👥 Social":       ["INBOX", "CATEGORY_SOCIAL"],
        "🔔 Updates":      ["INBOX", "CATEGORY_UPDATES"],
        "💬 Forums":       ["INBOX", "CATEGORY_FORUMS"],
        "📤 Sent":         ["SENT"],
        "📝 Drafts":       ["DRAFT"],
        "⭐ Starred":      ["STARRED"],
        "❗ Important":     ["IMPORTANT"],
        "⚠️ Spam":         ["SPAM"],
        "🗑️ Trash":        ["TRASH"],
        "📁 All Mail":     [],            # empty = no label filter
    }

    # ── Controls row ───────────────────────────────────────────────────────
    col_category, col_count, col_fetch = st.columns([1.2, 0.8, 1])

    with col_category:
        category = st.selectbox(
            "Category / Folder",
            options=list(CATEGORY_MAP.keys()),
            index=0,  # "📥 All Inbox" by default
            key="inbox_category",
        )

    with col_count:
        count = st.selectbox(
            "Messages",
            options=[1, 5, 10, 15, 20],
            index=2,  # default 10
            key="inbox_msg_count",
        )

    with col_fetch:
        st.write("")  # spacing to align with selectbox
        st.write("")
        fetch_clicked = st.button(
            "📥 Fetch Messages",
            use_container_width=True,
            key="inbox_fetch_btn",
        )

    # ── Fetch messages ─────────────────────────────────────────────────────
    if fetch_clicked:
        label_ids = CATEGORY_MAP[category] or None  # None → all mail
        with st.spinner(f"Fetching last {count} messages from {category}..."):
            result = list_messages(max_results=count, label_ids=label_ids)

        if not result["success"]:
            st.error(f"❌ Failed to fetch messages: {result['error']}")
            return

        st.session_state.inbox_messages = result["messages"]
        st.session_state.inbox_view_idx = None  # reset viewer
        st.session_state.inbox_last_category = category

    # ── Display results ────────────────────────────────────────────────────
    messages = st.session_state.get("inbox_messages")

    if messages is None:
        st.info("Click **📥 Fetch Messages** to load your recent emails.")
        _render_example_prompts()
        return

    if not messages:
        st.info("Your inbox is empty — no messages found.")
        _render_example_prompts()
        return

    last_cat = st.session_state.get("inbox_last_category", "📥 All Inbox")
    st.success(f"✅ Showing {len(messages)} message(s) from **{last_cat}**")

    st.divider()

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
            if st.button("👁️", key=f"view_msg_{idx}", help="View full email"):
                st.session_state.inbox_view_idx = idx

        # Light separator between rows
        if idx < len(messages) - 1:
            st.markdown(
                "<hr style='margin:2px 0; border:none; border-top:1px solid #2a2a2a'>",
                unsafe_allow_html=True,
            )

    # ── Full message viewer ────────────────────────────────────────────────
    view_idx = st.session_state.get("inbox_view_idx")
    if view_idx is not None and 0 <= view_idx < len(messages):
        st.divider()
        _render_full_message(messages[view_idx], view_idx)

    # ── Example prompts ────────────────────────────────────────────────────
    st.divider()
    _render_example_prompts()


# ── Full message viewer ────────────────────────────────────────────────────────

def _render_full_message(msg: dict, idx: int):
    """Render the full email body in a styled container."""
    st.subheader(f"📧 Message #{idx + 1}")

    # Styled card-like container
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

    # Full body
    st.write("**Full Message:**")
    body_text = msg["body_full"] if msg["body_full"] else "_(No text content available)_"
    st.text_area(
        "Email body",
        value=body_text,
        height=300,
        disabled=True,
        key=f"full_body_{idx}",
        label_visibility="collapsed",
    )

    # Action buttons
    col_gmail, col_close = st.columns(2)

    with col_gmail:
        st.link_button(
            "📧 Open in Gmail",
            url=msg["gmail_link"],
            use_container_width=True,
        )

    with col_close:
        if st.button("✖ Close Viewer", key=f"close_viewer_{idx}", use_container_width=True):
            st.session_state.inbox_view_idx = None
            st.rerun()


# ── Example prompts ────────────────────────────────────────────────────────────

def _render_example_prompts():
    """Show example usage hints at the bottom."""
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, rgba(108,99,255,0.06), rgba(167,139,250,0.03));
            border: 1px solid rgba(108,99,255,0.15);
            border-radius: 10px;
            padding: 16px 20px;
            margin-top: 8px;
        ">
            <p style="font-weight:600; color:#a78bfa; margin-bottom:10px;">
                💡 How to use this feature:
            </p>
            <ol style="margin:0; padding-left:20px; line-height:1.8;">
                <li>Select <strong>1</strong> from the dropdown → click <strong>📥 Fetch Messages</strong> → see only the latest email.</li>
                <li>Select <strong>5</strong> → click <strong>📥 Fetch Messages</strong> → see the last 5 emails in a table.</li>
                <li>Select <strong>10</strong> → click <strong>📥 Fetch Messages</strong> → see the last 10 emails, then click <strong>👁️</strong> on any row to read the full body.</li>
            </ol>
        </div>
        """,
        unsafe_allow_html=True,
    )
