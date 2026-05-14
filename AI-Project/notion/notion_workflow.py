import streamlit as st
from datetime import datetime
from notion.notion_handler import (
    is_notion_authenticated,
    get_notion_auth_url,
    exchange_code_for_token,
    create_notion_page,
    get_authenticated_user,
    clear_authentication,
    _load_config,
    _save_config,
    generate_page_content,
    refine_direct_content,
)
from notion.intent_parser import NotionIntentParser
from notion.workflow_planner import NotionWorkflowPlanner

# ── Dropdown option definitions ────────────────────────────────────────────────
FORMATTING_OPTIONS = {
    "Text Formatting": [
        "Text", "Bold", "Italic", "Underline", "Strikethrough",
        "Inline Code", "Text Color", "Background Color (Highlight)",
        "Equations (Math)", "Comments",
    ],
    "Basic Blocks": [
        "Heading 1", "Heading 2", "Heading 3",
        "Bullet List", "Numbered List", "To-do List (Checklist)",
        "Toggle List", "Quote", "Callout", "Divider",
        "Table (Simple)", "Table of Contents",
    ],
    "Media & Files": [
        "Image", "Video", "Audio", "File", "Web Bookmark", "Code Block",
        "YouTube Embed", "Google Drive Embed", "PDF Embed",
        "Maps Embed", "Tally Form",
    ],
    "Databases & Views": [
        "Table View", "Board View (Kanban)", "Gallery View",
        "List View", "Calendar View", "Timeline View",
    ],
    "Advanced & Interactive": [
        "Synced Block", "Columns", "Button", "Template Button",
        "Breadcrumb",
    ],
}

# All options that need a URL or file input
MEDIA_UPLOAD_OPTIONS = {
    "Image", "Video", "Audio", "File", "Web Bookmark",
    "YouTube Embed", "Google Drive Embed", "PDF Embed",
    "Maps Embed", "Tally Form",
}

# Options that only need a URL (no file upload)
URL_ONLY_OPTIONS = {
    "YouTube Embed", "Google Drive Embed", "PDF Embed",
    "Maps Embed", "Tally Form", "Web Bookmark",
}

# Placeholder text per media type
MEDIA_URL_PLACEHOLDERS = {
    "Image":              "https://example.com/image.png",
    "Video":              "https://example.com/video.mp4",
    "Audio":              "https://example.com/audio.mp3",
    "File":               "https://example.com/document.pdf",
    "Web Bookmark":       "https://example.com",
    "YouTube Embed":      "https://www.youtube.com/watch?v=...",
    "Google Drive Embed": "https://drive.google.com/file/d/...",
    "PDF Embed":          "https://example.com/document.pdf",
    "Maps Embed":         "https://maps.google.com/...",
    "Tally Form":         "https://tally.so/r/...",
}

# Mapping from dropdown selection → markdown/block hint for the AI
BLOCK_HINT_MAP = {
    "Bold":                     "Use **bold** text for key terms and important phrases.",
    "Italic":                   "Use *italic* text for emphasis and definitions.",
    "Underline":                "Emphasize important words (use bold as Notion proxy).",
    "Strikethrough":            "Use ~~strikethrough~~ for deprecated or removed items.",
    "Inline Code":              "Use `inline code` for technical terms, commands, and values.",
    "Text Color":               "Use colored text annotations for visual hierarchy.",
    "Background Color (Highlight)": "Use >> callout blocks to highlight key information.",
    "Equations (Math)":         "Include relevant mathematical equations using $...$ syntax.",
    "Comments":                 "Add > quote blocks as inline commentary and notes.",
    "Heading 1":                "Use # Heading 1 for the main page title section.",
    "Heading 2":                "Use ## Heading 2 for major sections.",
    "Heading 3":                "Use ### Heading 3 for subsections.",
    "Bullet List":              "Use - bullet lists for unordered items and features.",
    "Numbered List":            "Use 1. numbered lists for ordered steps and sequences.",
    "To-do List (Checklist)":   "Use - [ ] checkboxes for tasks and action items.",
    "Toggle List":              "Use >? toggle blocks for collapsible details.",
    "Quote":                    "Use > quote blocks for important statements and references.",
    "Callout":                  "Use >> callout blocks with emoji for tips, warnings, and highlights.",
    "Divider":                  "Use --- dividers to separate major sections visually.",
    "Table (Simple)":           "Include a | table | with headers for structured data.",
    "Table of Contents":        "Start with a structured overview of all sections.",
    "Code Block":               "Use ```language code blocks for all code samples.",
    "Table View":               "Structure data as a table with rows and columns.",
    "Board View (Kanban)":      "Organize content into status columns: To Do, In Progress, Done.",
    "Gallery View":             "Present items as a visual card-based gallery layout.",
    "List View":                "Present items as a clean structured list.",
    "Calendar View":            "Include dates and schedule information in the content.",
    "Timeline View":            "Include a timeline or chronological sequence of events.",
    "Synced Block":             "Note that this content block should be synced across pages.",
    "Columns":                  "Organize content into side-by-side column sections.",
    "Button":                   "Include actionable button-style call-to-action items.",
    "Breadcrumb":               "Include a navigation breadcrumb at the top.",
    "YouTube Embed":            "Include a YouTube video embed placeholder.",
    "Google Drive Embed":       "Include a Google Drive file embed placeholder.",
    "Maps Embed":               "Include a map embed placeholder with location details.",
    "PDF Embed":                "Include a PDF document embed placeholder.",
    "Tally Form":               "Include a form/survey embed placeholder.",
}


# ── Session state defaults ─────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "notion_workflow_state":  "idle",
        "notion_current_plan":    [],
        "notion_parsed_intent":   None,
        "last_notion_result":     None,
        "notion_page_history":    [],
        "notion_preview_content": "",
        "notion_preview_title":   "",
        "notion_is_editing":      False,
        "notion_form_version":    0,
        "notion_media_items":     [],   # list of {type, source, url_or_path}
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── Main renderer ──────────────────────────────────────────────────────────────
def render_notion_workflow():
    st.markdown('<div class="page-title">📝 Notion AI Agent</div>', unsafe_allow_html=True)

    # Handle OAuth callback
    query_params = st.query_params
    if "code" in query_params:
        code = query_params["code"]
        with st.spinner("🔗 Completing Notion connection..."):
            if exchange_code_for_token(code):
                st.success("✅ Notion connected successfully!")
                st.query_params.clear()
                st.rerun()
            else:
                st.error("❌ Failed to connect Notion. Check your credentials.")

    tab_agent, tab_settings = st.tabs(["🤖 Create Page", "⚙️ Settings"])

    # ── Settings tab ───────────────────────────────────────────────────────────
    with tab_settings:
        with st.expander("📖 Setup Guide", expanded=False):
            st.markdown("""
            Go to **[Notion Developers](https://www.notion.so/my-integrations)** → **Developer Portal**.

            1. Click **"New Connection"** → fill in the name, select **OAuth**, choose workspace.
            2. Set **Redirect URL** to `http://localhost:8501`.
            3. Click **Create Connection** — go to **Connections** in the left sidebar.
            4. Copy the **Client ID** and **Client Secret**.
            """)

        st.subheader("🔐 Notion API Configuration")
        config = _load_config()
        new_client_id     = st.text_input("Client ID",     value=config.get("client_id", ""))
        new_client_secret = st.text_input("Client Secret", value=config.get("client_secret", ""), type="password")
        new_redirect_uri  = st.text_input("Redirect URL",  value=config.get("redirect_uri", "http://localhost:8501"))

        if st.button("💾 Save Configuration", key="save_notion_config"):
            _save_config({
                "client_id":     new_client_id,
                "client_secret": new_client_secret,
                "redirect_uri":  new_redirect_uri,
            })
            st.success("✅ Configuration saved!")
            st.rerun()

        st.divider()
        st.subheader("👤 Connection Status")
        if is_notion_authenticated():
            st.success(f"✅ Connected as: {get_authenticated_user()}")
            if st.button("🔓 Disconnect Notion", key="disconnect_notion"):
                clear_authentication()
                st.rerun()
        else:
            st.info("Notion is not connected.")
            auth_url = get_notion_auth_url()
            if auth_url:
                st.link_button("🔓 Connect Notion", auth_url, use_container_width=True)
            else:
                st.warning("Please configure Client ID and Redirect URL first.")

    # ── Agent tab ──────────────────────────────────────────────────────────────
    with tab_agent:
        if not is_notion_authenticated():
            st.warning("⚠️ Please connect your Notion account in the Settings tab first.")
            return

        _init_state()

        st.write("Compose your page using direct text, AI generation, or both. "
                 "Use the formatting dropdowns to guide the AI's structure.")

        version = st.session_state.notion_form_version

        # ── Page title ─────────────────────────────────────────────────────────
        page_title = st.text_input(
            "📄 Page Title",
            placeholder="e.g. Project Research",
            key=f"notion_title_input_{version}",
        )

        # ── Content inputs ─────────────────────────────────────────────────────
        direct_text_val = st.session_state.get(f"notion_direct_input_{version}", "").strip()
        ai_text_val     = st.session_state.get(f"notion_ai_input_{version}", "").strip()

        col1, col2 = st.columns(2)
        with col1:
            direct_content = st.text_area(
                "✍️ Direct Content",
                placeholder="Enter text to keep as-is (AI will still format it)…",
                key=f"notion_direct_input_{version}",
                height=140,
                disabled=(ai_text_val != ""),
            )
        with col2:
            ai_prompt = st.text_area(
                "🤖 AI Generation Prompt",
                placeholder="Describe what you want the AI to generate…",
                key=f"notion_ai_input_{version}",
                height=140,
                disabled=(direct_text_val != ""),
            )

        # ── Formatting dropdowns (multi-select) ───────────────────────────────
        st.markdown("**🎨 Formatting & Block Preferences** *(select multiple — AI will apply all chosen styles)*")

        ms_cols = st.columns(5)
        dd_keys = list(FORMATTING_OPTIONS.keys())
        selected_formats: dict[str, list[str]] = {}

        for col, key in zip(ms_cols, dd_keys):
            with col:
                # Options without the "— None —" placeholder (not needed for multiselect)
                opts = [o for o in FORMATTING_OPTIONS[key] if o != "— None —"]
                choices = st.multiselect(
                    key,
                    options=opts,
                    default=[],
                    key=f"notion_fmt_{key}_{version}",
                    placeholder="Choose…",
                )
                selected_formats[key] = choices

        # ── Green-tick summary of all active selections ────────────────────────
        all_selected = [item for choices in selected_formats.values() for item in choices]
        if all_selected:
            ticks = "  ".join(f"✅ {s}" for s in all_selected)
            st.markdown(
                f"<div style='background:rgba(0,200,100,0.08);border:1px solid rgba(0,200,100,0.3);"
                f"border-radius:8px;padding:8px 14px;margin-top:4px;font-size:13px;color:#6ee7b7'>"
                f"{ticks}</div>",
                unsafe_allow_html=True,
            )
        media_items = st.session_state.notion_media_items  # persisted list

        # Show upload/URL input for each selected media type
        media_choices = selected_formats.get("Media & Files", [])
        active_media_choices = [m for m in media_choices if m in MEDIA_UPLOAD_OPTIONS]

        if active_media_choices:
            for media_choice in active_media_choices:
                st.markdown(f"**📎 {media_choice} — Add Source**")
                url_only = media_choice in URL_ONLY_OPTIONS
                placeholder = MEDIA_URL_PLACEHOLDERS.get(media_choice, "https://...")

                if url_only:
                    # URL-only embed — no file upload needed
                    media_url = st.text_input(
                        f"URL for {media_choice}",
                        placeholder=placeholder,
                        key=f"notion_media_url_{version}_{media_choice}",
                        label_visibility="collapsed",
                    )
                    uploaded_file = None
                else:
                    m_col1, m_col2 = st.columns([1, 1])
                    with m_col1:
                        media_url = st.text_input(
                            "Paste URL / link",
                            placeholder=placeholder,
                            key=f"notion_media_url_{version}_{media_choice}",
                        )
                    with m_col2:
                        uploaded_file = st.file_uploader(
                            "Or upload from device",
                            key=f"notion_media_upload_{version}_{media_choice}",
                            label_visibility="visible",
                        )

                add_col, _ = st.columns([1, 4])
                with add_col:
                    if st.button("➕ Add to page", key=f"add_media_{version}_{media_choice}"):
                        if media_url and media_url.strip():
                            media_items.append({
                                "type":   media_choice,
                                "source": "url",
                                "value":  media_url.strip(),
                            })
                            st.success(f"✅ {media_choice} URL added.")
                        elif uploaded_file is not None:
                            media_items.append({
                                "type":   media_choice,
                                "source": "upload",
                                "value":  uploaded_file.name,
                                "data":   uploaded_file.read(),
                            })
                            st.success(f"✅ {media_choice} file '{uploaded_file.name}' added.")
                        else:
                            st.warning("Please paste a URL or upload a file first.")
                        st.session_state.notion_media_items = media_items
                        st.rerun()

        if media_items:
            st.caption(f"**Queued media ({len(media_items)}):**")
            for mi, item in enumerate(media_items):
                c1, c2 = st.columns([5, 1])
                c1.caption(f"• ✅ {item['type']} — {item['source'].upper()}: {item['value']}")
                if c2.button("✕", key=f"rm_media_{mi}"):
                    media_items.pop(mi)
                    st.session_state.notion_media_items = media_items
                    st.rerun()

        # ── Prepare / Generate ─────────────────────────────────────────────────
        if st.button("🔍 Prepare Preview", key="run_notion_agent") and (page_title or direct_content or ai_prompt):
            st.session_state.notion_workflow_state = "preparing"
            st.session_state.notion_preview_title  = page_title or "Untitled Page"

            # Collect active formatting hints from all multi-select choices
            active_hints = []
            for cat, choices in selected_formats.items():
                if cat == "Media & Files":
                    continue
                for choice in choices:
                    hint = BLOCK_HINT_MAP.get(choice)
                    if hint:
                        active_hints.append(f"- {hint}")

            # Build formatting instruction string for the AI
            fmt_instruction = ""
            if active_hints:
                fmt_instruction = (
                    "\n\nUSER-SELECTED FORMATTING PREFERENCES (apply these in the content):\n"
                    + "\n".join(active_hints)
                )

            # Add media placeholders to content
            media_blocks = _build_media_blocks(media_items)

            with st.status("🧠 Preparing content preview…", expanded=True) as status:
                current_model = st.session_state.get("selected_model", "llama3:latest")
                final_parts   = []

                if direct_content:
                    st.write("✨ Refining direct content…")
                    refined = refine_direct_content(direct_content, model=current_model)
                    final_parts.append(refined)

                if ai_prompt:
                    st.write("✍️ Generating AI content…")
                    full_instructions = ai_prompt + fmt_instruction
                    generated = generate_page_content(
                        st.session_state.notion_preview_title,
                        full_instructions,
                        model=current_model,
                    )
                    final_parts.append(generated)

                if media_blocks:
                    final_parts.append(media_blocks)

                st.session_state.notion_preview_content = "\n\n".join(final_parts)
                st.session_state.notion_current_plan = [
                    {"step": 1, "action": "Content Preparation",
                     "description": "Refining and generating content with selected formatting", "status": "complete"},
                    {"step": 2, "action": "Preview & Review",
                     "description": "Human-in-the-loop verification", "status": "pending"},
                    {"step": 3, "action": "Notion Creation",
                     "description": "Final API execution", "status": "pending"},
                ]
                status.update(label="✅ Preview Ready", state="complete")
                st.session_state.notion_workflow_state = "preview"

        # ── Preview ────────────────────────────────────────────────────────────
        if st.session_state.notion_workflow_state == "preview":
            st.divider()
            st.subheader("👀 Content Preview")
            st.info("Review your content. Send directly, Edit, or Cancel.")

            if st.session_state.notion_is_editing:
                st.session_state.notion_preview_title = st.text_input(
                    "Edit Title", value=st.session_state.notion_preview_title,
                    key="edit_title_field",
                )
                st.session_state.notion_preview_content = st.text_area(
                    "Edit Content", value=st.session_state.notion_preview_content,
                    height=320, key="edit_content_field",
                )
            else:
                st.markdown(f"### {st.session_state.notion_preview_title}")
                _render_rich_preview(st.session_state.notion_preview_content)

            st.divider()
            col_send, col_edit, col_cancel = st.columns(3)

            with col_send:
                if st.button("📤 Send to Notion", key="execute_notion_final", use_container_width=True):
                    st.session_state.notion_workflow_state = "executing"
                    st.rerun()

            with col_edit:
                edit_label = "💾 Save Edits" if st.session_state.notion_is_editing else "📝 Edit"
                if st.button(edit_label, key="toggle_edit", use_container_width=True):
                    st.session_state.notion_is_editing = not st.session_state.notion_is_editing
                    st.rerun()

            with col_cancel:
                if st.button("❌ Cancel", key="cancel_notion_preview", use_container_width=True):
                    _reset_form()
                    st.rerun()

        # ── Execution ──────────────────────────────────────────────────────────
        if st.session_state.notion_workflow_state == "executing":
            title   = st.session_state.notion_preview_title
            content = st.session_state.notion_preview_content

            with st.spinner(f"🚀 Creating Notion page: {title}…"):
                result = create_notion_page(title, content=content)

            if result["success"]:
                page_id  = result["data"]["id"].replace("-", "")
                page_url = f"https://www.notion.so/{page_id}"
                record   = {
                    "title":       title,
                    "url":         page_url,
                    "content":     content,
                    "parent_name": result.get("parent_name", "Workspace"),
                    "created_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "data":        result["data"],
                }
                st.session_state.notion_page_history.append(record)
                st.session_state.last_notion_result    = record
                st.session_state.notion_media_items    = []   # clear media queue
                st.session_state.notion_workflow_state = "completed"
                st.rerun()
            else:
                st.error(f"❌ Execution failed: {result['error']}")
                st.session_state.notion_workflow_state = "preview"

        # ── Completed ──────────────────────────────────────────────────────────
        if st.session_state.notion_workflow_state == "completed":
            res = st.session_state.last_notion_result
            if res:
                st.divider()
                st.success("🎉 **Page Created Successfully!**")
                _render_page_card(res, idx=999, show_raw=True)

            if st.button("↩️ Create Another Page", key="new_notion_task", use_container_width=True):
                _reset_form()
                st.rerun()

        # ── History ────────────────────────────────────────────────────────────
        _render_history()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _render_rich_preview(content: str):
    """
    Render the preview content with proper handling of:
    - Standard markdown (headings, bullets, bold, etc.) via st.markdown
    - Images: ![alt](url) → st.image
    - Video/YouTube: {video:url} → st.video
    - Embeds: {embed:url} → clickable link card
    - Audio: {audio:url} → st.audio
    """
    import re

    if not content:
        st.caption("*(no content)*")
        return

    lines = content.split("\n")
    markdown_buffer = []

    def flush_markdown():
        if markdown_buffer:
            st.markdown("\n".join(markdown_buffer))
            markdown_buffer.clear()

    for line in lines:
        stripped = line.strip()

        # Image: ![alt](url)
        img_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if img_match:
            flush_markdown()
            url = img_match.group(2)
            alt = img_match.group(1) or "Image"
            if url.startswith("http"):
                try:
                    st.image(url, caption=alt, use_container_width=True)
                except Exception:
                    st.markdown(f"🖼️ **Image:** [{alt}]({url})")
            else:
                st.markdown(f"🖼️ **Image (local):** `{url}`")
            continue

        # Video: {video:url}
        vid_match = re.match(r"\{video:(.+)\}", stripped)
        if vid_match:
            flush_markdown()
            url = vid_match.group(1).strip()
            try:
                st.video(url)
            except Exception:
                st.markdown(f"🎬 **Video:** [{url}]({url})")
            continue

        # Embed: {embed:url}
        emb_match = re.match(r"\{embed:(.+)\}", stripped)
        if emb_match:
            flush_markdown()
            url = emb_match.group(1).strip()
            st.markdown(
                f"<div style='background:rgba(108,99,255,0.08);border:1px solid rgba(108,99,255,0.25);"
                f"border-radius:8px;padding:10px 14px;margin:4px 0'>"
                f"🔗 <b>Embed:</b> <a href='{url}' target='_blank'>{url}</a></div>",
                unsafe_allow_html=True,
            )
            continue

        # Audio bookmark lines like "> 🎵 Audio: [url](url)"
        audio_match = re.match(r">\s*🎵\s*Audio:\s*\[([^\]]+)\]\(([^)]+)\)", stripped)
        if audio_match:
            flush_markdown()
            url = audio_match.group(2)
            try:
                st.audio(url)
            except Exception:
                st.markdown(f"🎵 **Audio:** [{url}]({url})")
            continue

        # Everything else — accumulate as markdown
        markdown_buffer.append(line)

    flush_markdown()


def _reset_form():
    st.session_state.notion_workflow_state  = "idle"
    st.session_state.notion_current_plan    = []
    st.session_state.notion_parsed_intent   = None
    st.session_state.last_notion_result     = None
    st.session_state.notion_preview_title   = ""
    st.session_state.notion_preview_content = ""
    st.session_state.notion_is_editing      = False
    st.session_state.notion_media_items     = []
    st.session_state.notion_form_version   += 1


def _build_media_blocks(media_items: list) -> str:
    """Convert queued media items into markdown/block syntax for the page."""
    if not media_items:
        return ""
    lines = ["---", "## 📎 Media & Attachments", ""]
    for item in media_items:
        t = item["type"]
        v = item["value"]
        src = item["source"]
        if t == "Image":
            lines.append(f"![{v}]({v})" if src == "url" else f"![{v}](attachment:{v})")
        elif t in ("Video", "YouTube Embed"):
            lines.append(f"{{video:{v}}}")
        elif t in ("PDF Embed", "Google Drive Embed", "Maps Embed", "Tally Form"):
            lines.append(f"{{embed:{v}}}")
        elif t == "Web Bookmark":
            lines.append(f"> 🔖 Bookmark: [{v}]({v})")
        elif t == "Audio":
            lines.append(f"> 🎵 Audio: [{v}]({v})")
        elif t == "File":
            lines.append(f"> 📄 File: {v}")
        else:
            lines.append(f"> 🔗 {t}: [{v}]({v})")
    return "\n".join(lines)


def _render_page_card(rec: dict, idx: int, show_raw: bool = False):
    st.markdown(
        """<div style="
            background: linear-gradient(135deg, rgba(108,99,255,0.08), rgba(167,139,250,0.04));
            border: 1px solid rgba(108,99,255,0.28);
            border-radius: 12px;
            padding: 18px 22px;
            margin-bottom: 10px;">""",
        unsafe_allow_html=True,
    )
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**📄 Title:** {rec['title']}")
        st.markdown(f"**📁 Created in:** {rec['parent_name']}")
    with col_b:
        st.markdown(f"**🕐 Created at:** {rec.get('created_at', '—')}")
        st.markdown(f"**🔗 Link:** [Open in Notion]({rec['url']})")

    if rec.get("content"):
        st.markdown("**📝 Content written:**")
        st.text_area(
            "content_preview",
            value=rec["content"],
            height=160,
            disabled=True,
            key=f"notion_card_{idx}_{rec.get('created_at', idx)}",
            label_visibility="collapsed",
        )
    else:
        st.caption("No content body — page created with title only.")

    st.markdown("</div>", unsafe_allow_html=True)

    if show_raw:
        with st.expander("📦 Raw API Response"):
            st.json(rec["data"])


def _render_history():
    history = st.session_state.get("notion_page_history", [])
    if not history:
        return

    st.divider()
    st.subheader(f"📜 Page Creation History ({len(history)} page(s))")
    st.caption("All pages created in this session — newest first.")

    col_clear, _ = st.columns([1, 5])
    with col_clear:
        if st.button("🗑️ Clear History", key="clear_notion_history"):
            st.session_state.notion_page_history = []
            st.rerun()

    for i, rec in enumerate(reversed(history)):
        real_idx = len(history) - 1 - i
        label    = f"{i + 1}. {rec['title']}  —  {rec.get('created_at', '')}"
        with st.expander(label, expanded=(i == 0)):
            _render_page_card(rec, idx=real_idx, show_raw=False)
