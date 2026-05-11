"""
Direct email send workflow.

This module owns the Streamlit UI and orchestration for composing,
previewing, generating, saving drafts, and sending emails.
Shared services stay in email_composer.py, gmail_handler.py, and contacts_manager.py.
"""
import streamlit as st
from datetime import datetime

from .gmail_handler import (
    get_authenticated_email,
    is_gmail_authenticated,
    send_email,
    create_draft,
    send_draft,
)


EMAIL_TONES = ["Nothing", "Professional", "Formal", "Casual", "Friendly"]


# ── Top-level renderer ─────────────────────────────────────────────────────────

def render_send_email_workflow():
    """Render the direct email send workflow in the Email tab."""
    st.header("Direct Email Send Workflow")

    _apply_pending_state_changes()
    _render_auth_status()

    st.divider()
    recipient_input, subject_context, email_tone, additional_context = _render_compose_section()

    st.divider()
    _render_generate_and_actions(
        recipient_input=recipient_input,
        subject_context=subject_context,
        email_tone=email_tone,
        additional_context=additional_context,
    )

    st.divider()
    _render_preview(recipient_input)

    st.divider()
    _render_draft_history()

    st.divider()
    _render_email_history()


# ── State helpers ──────────────────────────────────────────────────────────────

def _apply_pending_state_changes():
    """Apply widget state changes before widgets are instantiated."""
    if st.session_state.pop("reset_email_form", False):
        st.session_state.recipients = [""]
        st.session_state.subject_context = ""
        st.session_state.additional_context = ""
        st.session_state.email_tone = "Nothing"
        st.session_state.generated_subject = ""
        st.session_state.generated_body = ""
        st.session_state.preview_editing = False

    # Quick-contact button appends to the recipients list
    pending_recipient = st.session_state.pop("pending_recipient_input", None)
    if pending_recipient is not None:
        if "recipients" not in st.session_state:
            st.session_state.recipients = [pending_recipient]
        else:
            # Fill the first empty slot, or add a new one
            try:
                empty_idx = st.session_state.recipients.index("")
                st.session_state.recipients[empty_idx] = pending_recipient
            except ValueError:
                st.session_state.recipients.append(pending_recipient)

    sent_message = st.session_state.pop("email_sent_message", None)
    if sent_message:
        st.success(sent_message)

    draft_message = st.session_state.pop("draft_saved_message", None)
    if draft_message:
        st.success(draft_message)


def _init_session_defaults():
    """Ensure all session keys used by this module exist."""
    defaults = {
        "email_history": [],
        "draft_history": [],
        "recipients": [""],         # list of recipient strings (name or email)
        "generated_subject": "",
        "generated_body": "",
        "preview_editing": False,   # True while the user is editing the preview
        "draft_editing_idx": None,  # int index of the draft currently being edited
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ── Auth status ────────────────────────────────────────────────────────────────

def _render_auth_status():
    """Show Gmail authentication status for this workflow."""
    _init_session_defaults()

    if not is_gmail_authenticated():
        st.warning(
            "Gmail is not authenticated. Please set up authentication in Settings.",
            icon="⚠️",
        )
        return

    auth_email = get_authenticated_email()
    st.success(f"Gmail authenticated as: {auth_email}")


# ── Compose section ────────────────────────────────────────────────────────────

def _render_compose_section() -> tuple[str, str, str, str]:
    """Render compose inputs and quick contacts."""
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("1. Compose Email")

        # ── Dynamic multi-recipient inputs ─────────────────────────────────
        st.markdown("**Recipients (name or email)**")

        if "recipients" not in st.session_state or not st.session_state.recipients:
            st.session_state.recipients = [""]

        recipients: list[str] = st.session_state.recipients

        for i in range(len(recipients)):
            r_col, del_col = st.columns([9, 1])
            with r_col:
                recipients[i] = st.text_input(
                    f"Recipient {i + 1}",
                    value=recipients[i],
                    placeholder="e.g., rahul@example.com or Rahul",
                    key=f"recipient_{i}",
                    label_visibility="collapsed",
                )
            with del_col:
                # Only show remove button when there is more than one row
                if len(recipients) > 1:
                    if st.button("🗑", key=f"remove_recipient_{i}", help="Remove this recipient"):
                        st.session_state.recipients.pop(i)
                        st.rerun()

        if st.button("➕ Add Recipient", key="add_recipient_btn"):
            st.session_state.recipients.append("")
            st.rerun()

        # Collect the non-empty recipient values after widget rendering
        recipient_input = ", ".join(
            r.strip() for r in st.session_state.recipients if r.strip()
        )

        # ── Other compose fields ───────────────────────────────────────────
        subject_context = st.text_input(
            "What is this email about?",
            placeholder="Write the message you want to send",
            key="subject_context",
        )

        email_tone = st.selectbox(
            "Email Tone",
            EMAIL_TONES,
            index=0,
            key="email_tone",
        )

        additional_context = st.text_area(
            "Additional Context (optional)",
            placeholder="Any extra details to include...",
            height=80,
            key="additional_context",
        )

    with col2:
        _render_quick_contacts()

    return recipient_input, subject_context, email_tone, additional_context


def _render_quick_contacts():
    """Render recent contacts for quickly adding them to the recipients list."""
    st.subheader("Quick Contacts")

    contacts = st.session_state.contacts_manager.get_all_contacts()
    if not contacts:
        st.info("No saved contacts yet. Add them in Settings.")
        return

    st.write("**Recent Contacts:**")
    st.caption("Click to add to recipients list")
    for name, email in list(contacts.items())[:5]:
        if st.button(f"➕ {name}", key=f"contact_{name}"):
            st.session_state.pending_recipient_input = email
            st.rerun()


# ── Action buttons ─────────────────────────────────────────────────────────────

def _render_generate_and_actions(
    recipient_input: str,
    subject_context: str,
    email_tone: str,
    additional_context: str,
):
    """Render Generate Email, Save Draft, and Send Email action buttons."""
    st.subheader("2. Actions")

    col_gen, col_draft, col_send = st.columns(3)

    with col_gen:
        if st.button("✨ Generate Email", use_container_width=True):
            _handle_generate_email(
                recipient_input=recipient_input,
                subject_context=subject_context,
                email_tone=email_tone,
                additional_context=additional_context,
            )

    with col_draft:
        draft_enabled = is_gmail_authenticated() and bool(recipient_input) and bool(subject_context)
        if st.button(
            "📝 Save as Draft",
            use_container_width=True,
            disabled=not draft_enabled,
            help="Generate (if needed) and save to Gmail Drafts",
        ):
            _handle_save_draft(
                recipient_input=recipient_input,
                subject_context=subject_context,
                email_tone=email_tone,
                additional_context=additional_context,
            )

    with col_send:
        send_enabled = is_gmail_authenticated() and bool(recipient_input) and bool(subject_context)
        if st.button(
            "📤 Send Email",
            use_container_width=True,
            disabled=not send_enabled,
            help="Generate (if needed) and send immediately",
        ):
            _handle_send_email(
                recipient_input=recipient_input,
                subject_context=subject_context,
                email_tone=email_tone,
                additional_context=additional_context,
            )


# ── Email generation helpers ───────────────────────────────────────────────────

def _ensure_email_generated(
    recipient_input: str,
    subject_context: str,
    email_tone: str,
    additional_context: str,
) -> bool:
    """
    Generate the email if it hasn't been generated yet.
    Returns True if a valid generated email is available.
    """
    if st.session_state.get("generated_subject") and st.session_state.get("generated_body"):
        return True

    if not recipient_input or not subject_context:
        st.error("Please fill in recipient and email message.")
        return False

    with st.spinner("Generating email..."):
        composer = st.session_state.email_composer
        email_result = composer.generate_email(
            recipient=recipient_input,
            subject_context=subject_context,
            tone=email_tone.lower(),
            additional_context=additional_context,
        )

    if email_result["success"]:
        st.session_state.generated_subject = email_result["subject"]
        st.session_state.generated_body = email_result["body"]
        st.session_state.preview_editing = False
        return True

    st.error(f"Generation failed: {email_result.get('error', 'Unknown error')}")
    return False


def _handle_generate_email(
    recipient_input: str,
    subject_context: str,
    email_tone: str,
    additional_context: str,
):
    """Generate and store the email preview."""
    if not recipient_input or not subject_context:
        st.error("Please fill in recipient and email message.")
        return

    # Clear any previously generated email so a fresh one is created
    st.session_state.generated_subject = ""
    st.session_state.generated_body = ""
    st.session_state.preview_editing = False

    with st.spinner("Generating email..."):
        composer = st.session_state.email_composer
        email_result = composer.generate_email(
            recipient=recipient_input,
            subject_context=subject_context,
            tone=email_tone.lower(),
            additional_context=additional_context,
        )

    if email_result["success"]:
        st.session_state.generated_subject = email_result["subject"]
        st.session_state.generated_body = email_result["body"]
        st.success("Email generated. Review the preview below, then Edit, Save as Draft, or Send.")
        return

    st.error(f"Generation failed: {email_result.get('error', 'Unknown error')}")


def _handle_save_draft(
    recipient_input: str,
    subject_context: str,
    email_tone: str,
    additional_context: str,
):
    """Generate (if needed), resolve recipient, and save as Gmail draft."""
    if not _ensure_email_generated(recipient_input, subject_context, email_tone, additional_context):
        return

    resolved_email = _resolve_and_validate(recipient_input)
    if resolved_email is None:
        return

    with st.spinner("Saving draft..."):
        result = create_draft(
            to_email=resolved_email,
            subject=st.session_state.generated_subject,
            body=st.session_state.generated_body,
            html=False,
        )

    if not result["success"]:
        st.error(result["message"])
        return

    st.session_state.draft_history.append({
        "to": resolved_email,
        "subject": st.session_state.generated_subject,
        "body": st.session_state.generated_body,
        "draft_id": result.get("draft_id"),
        "status": "draft",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    st.session_state.draft_saved_message = f"✅ {result['message']}"
    st.session_state.reset_email_form = True
    st.rerun()


def _handle_send_email(
    recipient_input: str,
    subject_context: str,
    email_tone: str,
    additional_context: str,
):
    """Generate (if needed), resolve recipient, and send immediately."""
    if not _ensure_email_generated(recipient_input, subject_context, email_tone, additional_context):
        return

    resolved_email = _resolve_and_validate(recipient_input)
    if resolved_email is None:
        return

    with st.spinner("Sending email..."):
        result = send_email(
            to_email=resolved_email,
            subject=st.session_state.generated_subject,
            body=st.session_state.generated_body,
            html=False,
        )

    if not result["success"]:
        st.error(result["message"])
        return

    st.session_state.email_history.append({
        "to": resolved_email,
        "subject": st.session_state.generated_subject,
        "body": st.session_state.generated_body,
        "status": "sent",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    st.session_state.email_sent_message = f"✅ {result['message']}"
    st.session_state.reset_email_form = True
    st.rerun()


def _resolve_and_validate(recipient_input: str) -> str | None:
    """
    Resolve each name/email in the comma-separated recipient_input,
    validate all of them, and return a comma-separated string of
    resolved emails, or None if any address is invalid.
    """
    contacts = st.session_state.contacts_manager.get_all_contacts()
    composer  = st.session_state.email_composer

    raw_list = [r.strip() for r in recipient_input.split(",") if r.strip()]
    if not raw_list:
        st.error("Please add at least one recipient.")
        return None

    resolved_list = []
    for raw in raw_list:
        resolved = composer.resolve_recipient_name_to_email(raw, contacts)
        if not composer.validate_email_address(resolved):
            st.error(f"Invalid email address: {resolved}")
            return None
        resolved_list.append(resolved)

    return ", ".join(resolved_list)


# ── Preview section (generated email) ─────────────────────────────────────────

def _render_preview(recipient_input: str):
    """
    Render the generated email preview.

    - Read-only by default with an ✏️ Edit button.
    - Clicking Edit switches subject + body to editable inputs.
    - ✅ Done Editing saves the changes and returns to read-only view.
    """
    if not st.session_state.get("generated_subject"):
        return

    st.subheader("3. Preview & Edit")

    editing: bool = st.session_state.get("preview_editing", False)

    # ── Header row: To / Subject + Edit toggle ─────────────────────────────
    header_col, btn_col = st.columns([5, 1])
    with header_col:
        st.markdown(f"**To:** {recipient_input}")
        if not editing:
            st.markdown(f"**Subject:** {st.session_state.generated_subject}")
    with btn_col:
        if not editing:
            if st.button("✏️ Edit", key="preview_edit_btn", use_container_width=True):
                st.session_state.preview_editing = True
                st.rerun()
        else:
            if st.button("✅ Done", key="preview_done_btn", use_container_width=True):
                # Flush widget values into session state before leaving edit mode
                st.session_state.generated_subject = st.session_state.get(
                    "_edit_subject", st.session_state.generated_subject
                )
                st.session_state.generated_body = st.session_state.get(
                    "_edit_body", st.session_state.generated_body
                )
                st.session_state.preview_editing = False
                st.rerun()

    # ── Body area ──────────────────────────────────────────────────────────
    if editing:
        # Editable subject (shown here when in edit mode)
        edited_subject = st.text_input(
            "Subject",
            value=st.session_state.generated_subject,
            key="_edit_subject",
        )
        st.session_state.generated_subject = edited_subject

        st.write("**Message:**")
        edited_body = st.text_area(
            "Email body",
            value=st.session_state.generated_body,
            height=200,
            key="_edit_body",
        )
        st.session_state.generated_body = edited_body

        st.caption("Edit the subject and body above, then click ✅ Done when finished.")
    else:
        # Read-only view
        st.write("**Message:**")
        st.text_area(
            "Email body",
            value=st.session_state.generated_body,
            height=200,
            disabled=True,
            key="preview_body_readonly",
        )


# ── Draft history ──────────────────────────────────────────────────────────────

def _render_draft_history():
    """
    Render saved drafts.

    Each draft shows:
    - Read-only view with ✏️ Edit, 📤 Send, 🗑️ Remove buttons.
    - Clicking ✏️ Edit opens an inline form with editable subject + body,
      💾 Save Changes (updates the record), and ✖ Cancel.
    - After editing, the user can send the updated draft.
    """
    if "draft_history" not in st.session_state:
        st.session_state.draft_history = []
    if "draft_editing_idx" not in st.session_state:
        st.session_state.draft_editing_idx = None

    if not st.session_state.draft_history:
        return

    st.subheader("📝 Saved Drafts")

    drafts = st.session_state.draft_history
    # Iterate newest-first
    for idx, draft in enumerate(reversed(drafts)):
        real_idx = len(drafts) - 1 - idx
        is_editing = st.session_state.draft_editing_idx == real_idx

        label = (
            f"{idx + 1}. To: {draft['to']} — "
            f"{draft['subject'][:40]}{'...' if len(draft['subject']) > 40 else ''}"
            + (" ✏️" if is_editing else "")
        )

        with st.expander(label, expanded=is_editing):
            if is_editing:
                _render_draft_edit_form(real_idx, draft)
            else:
                _render_draft_read_view(real_idx, draft)


def _render_draft_read_view(real_idx: int, draft: dict):
    """Read-only view of a single draft with Edit / Send / Remove buttons."""
    st.write(f"**To:** {draft['to']}")
    st.write(f"**Subject:** {draft['subject']}")
    st.write(f"**Saved at:** {draft.get('timestamp', '—')}")
    st.write(f"**Status:** {draft['status'].capitalize()}")

    st.text_area(
        "Body",
        value=draft["body"],
        height=140,
        disabled=True,
        key=f"draft_body_ro_{real_idx}",
    )

    if draft["status"] == "sent":
        st.info("This draft has already been sent.")
        return

    col_edit, col_send, col_delete = st.columns(3)

    with col_edit:
        if st.button("✏️ Edit", key=f"draft_edit_{real_idx}", use_container_width=True):
            st.session_state.draft_editing_idx = real_idx
            st.rerun()

    with col_send:
        draft_id = draft.get("draft_id")
        if draft_id:
            if st.button("📤 Send", key=f"send_draft_{real_idx}", use_container_width=True):
                with st.spinner("Sending draft..."):
                    result = send_draft(draft_id)
                if result["success"]:
                    st.session_state.draft_history[real_idx]["status"] = "sent"
                    st.session_state.email_history.append({
                        "to": draft["to"],
                        "subject": draft["subject"],
                        "body": draft["body"],
                        "status": "sent",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })
                    st.success(result["message"])
                    st.rerun()
                else:
                    st.error(result["message"])
        else:
            st.caption("Draft ID unavailable.")

    with col_delete:
        if st.button("🗑️ Remove", key=f"delete_draft_{real_idx}", use_container_width=True):
            st.session_state.draft_history.pop(real_idx)
            st.rerun()


def _render_draft_edit_form(real_idx: int, draft: dict):
    """Inline edit form for a draft with Save Changes and Cancel."""
    st.write(f"**To:** {draft['to']}")
    st.caption("Edit the subject and body below, then save or cancel.")

    edited_subject = st.text_input(
        "Subject",
        value=draft["subject"],
        key=f"draft_edit_subject_{real_idx}",
    )

    edited_body = st.text_area(
        "Body",
        value=draft["body"],
        height=200,
        key=f"draft_edit_body_{real_idx}",
    )

    col_save, col_cancel = st.columns(2)

    with col_save:
        if st.button("💾 Save Changes", key=f"draft_save_{real_idx}", use_container_width=True):
            st.session_state.draft_history[real_idx]["subject"] = edited_subject
            st.session_state.draft_history[real_idx]["body"] = edited_body
            st.session_state.draft_history[real_idx]["timestamp"] = (
                datetime.now().strftime("%Y-%m-%d %H:%M") + " (edited)"
            )
            st.session_state.draft_editing_idx = None
            st.success("Draft updated.")
            st.rerun()

    with col_cancel:
        if st.button("✖ Cancel", key=f"draft_cancel_{real_idx}", use_container_width=True):
            st.session_state.draft_editing_idx = None
            st.rerun()


# ── Sent history ───────────────────────────────────────────────────────────────

def _render_email_history():
    """Render recent sent email history."""
    if not st.session_state.email_history:
        return

    st.subheader("📬 Sent Email History")
    for idx, email in enumerate(reversed(st.session_state.email_history[-5:]), 1):
        label = (
            f"{idx}. To: {email['to']} — "
            f"{email['subject'][:30]}{'...' if len(email['subject']) > 30 else ''}"
        )
        with st.expander(label):
            st.write(f"**Status:** {email['status'].capitalize()}")
            st.write(f"**Sent at:** {email.get('timestamp', '—')}")
            st.write(f"**Subject:** {email['subject']}")
            st.write(f"**Body:**\n{email['body']}")
