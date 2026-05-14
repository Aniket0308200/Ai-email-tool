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


# ── Session state defaults ─────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "notion_workflow_state": "idle",
        "notion_current_plan":   [],
        "notion_parsed_intent":  None,
        "last_notion_result":    None,
        "notion_page_history":   [],   # ← persistent log of all created pages
        "notion_preview_content": "",
        "notion_preview_title":   "",
        "notion_is_editing":     False,
        "notion_form_version":   0,
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
            3. Click **Create Connection** — go **Connections** option in left sidebar. 
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

        st.write("Construct your page using direct text, AI generation, or both. Preview before final creation.")

        # -- Inputs Section --
        version = st.session_state.notion_form_version
        page_title = st.text_input(
            "📄 Page Title",
            placeholder="e.g. Project Research",
            key=f"notion_title_input_{version}",
            value=st.session_state.get("notion_preview_title", "") if st.session_state.get("notion_preview_title") else ""
        )

        # -- Mutual Exclusion Logic --
        # We check session state directly using the versioned keys
        direct_text = st.session_state.get(f"notion_direct_input_{version}", "").strip()
        ai_text = st.session_state.get(f"notion_ai_input_{version}", "").strip()
        
        col1, col2 = st.columns(2)
        with col1:
            direct_content = st.text_area(
                "✍️ Direct Content (Fixed & Formatted)",
                placeholder="Enter text you want to keep as is, but with better formatting...",
                key=f"notion_direct_input_{version}",
                height=150,
                disabled=(ai_text != "")
            )
        with col2:
            ai_prompt = st.text_area(
                "🤖 AI Generation Prompt",
                placeholder="Describe what you want the AI to generate (e.g., 'Write 5 points about...')",
                key=f"notion_ai_input_{version}",
                height=150,
                disabled=(direct_text != "")
            )

        if st.button("🔍 Prepare Preview", key="run_notion_agent") and (page_title or direct_content or ai_prompt):
            st.session_state.notion_workflow_state = "preparing"
            st.session_state.notion_preview_title = page_title or "Untitled Page"

            with st.status("🧠 Preparing content preview...", expanded=True) as status:
                current_model = st.session_state.get("selected_model", "deepseek-r1:1.5b")
                
                final_content_parts = []
                
                if direct_content:
                    st.write("✨ Refining direct content...")
                    refined = refine_direct_content(direct_content, model=current_model)
                    final_content_parts.append(refined)
                
                if ai_prompt:
                    st.write("✍️ Generating AI content...")
                    generated = generate_page_content(st.session_state.notion_preview_title, ai_prompt, model=current_model)
                    final_content_parts.append(generated)
                
                st.session_state.notion_preview_content = "\n\n".join(final_content_parts)
                
                # Setup a plan for display
                st.session_state.notion_current_plan = [
                    {"step": 1, "action": "Content Preparation", "description": "Refining direct text and generating AI sections", "status": "complete"},
                    {"step": 2, "action": "Preview & Review", "description": "Human-in-the-loop verification", "status": "pending"},
                    {"step": 3, "action": "Notion Creation", "description": "Final API execution", "status": "pending"}
                ]
                
                status.update(label="✅ Preview Ready", state="complete")
                st.session_state.notion_workflow_state = "preview"

        # ── Preview Section ───────────────────────────────────────────────────
        if st.session_state.notion_workflow_state == "preview":
            st.divider()
            st.subheader("👀 Content Preview")
            st.info("Review your content. You can Send directly, Edit the result, or Cancel the process.")

            if st.session_state.notion_is_editing:
                st.session_state.notion_preview_title = st.text_input("Edit Title", value=st.session_state.notion_preview_title)
                st.session_state.notion_preview_content = st.text_area("Edit Content", value=st.session_state.notion_preview_content, height=300)
            else:
                st.markdown(f"### {st.session_state.notion_preview_title}")
                st.markdown(st.session_state.notion_preview_content)

            st.divider()
            
            # Three options: Send, Edit, Cancel
            col_send, col_edit, col_cancel = st.columns(3)
            
            with col_send:
                if st.button("📤 Send", key="execute_notion_final", use_container_width=True):
                    st.session_state.notion_workflow_state = "executing"
                    st.rerun()
            
            with col_edit:
                edit_label = "💾 Save" if st.session_state.notion_is_editing else "📝 Edit"
                if st.button(edit_label, key="toggle_edit", use_container_width=True):
                    st.session_state.notion_is_editing = not st.session_state.notion_is_editing
                    st.rerun()
            
            with col_cancel:
                if st.button("❌ Cancel", key="cancel_notion_preview", use_container_width=True):
                    st.session_state.notion_workflow_state = "idle"
                    st.session_state.notion_preview_title = ""
                    st.session_state.notion_preview_content = ""
                    st.session_state.notion_form_version += 1
                    st.rerun()

        # ── Execution ──────────────────────────────────────────────────────────
        if st.session_state.notion_workflow_state == "executing":
            title = st.session_state.notion_preview_title
            content = st.session_state.notion_preview_content
            
            with st.spinner(f"🚀 Creating Notion page: {title}..."):
                result = create_notion_page(title, content=content)

            if result["success"]:
                page_id  = result["data"]["id"].replace("-", "")
                page_url = f"https://www.notion.so/{page_id}"

                record = {
                    "title":       title,
                    "url":         page_url,
                    "content":     content,
                    "parent_name": result.get("parent_name", "Workspace"),
                    "created_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "data":        result["data"],
                }
                st.session_state.notion_page_history.append(record)
                st.session_state.last_notion_result = record
                st.session_state.notion_workflow_state = "completed"
                st.rerun()
            else:
                st.error(f"❌ Execution failed: {result['error']}")
                st.session_state.notion_workflow_state = "preview" # Go back to preview if error

        # ── Completed — result card ────────────────────────────────────────────
        if st.session_state.notion_workflow_state == "completed":
            res = st.session_state.last_notion_result
            if res:
                st.divider()
                st.success("🎉 **Page Created Successfully!**")
                _render_page_card(res, idx=999, show_raw=True) # Use high idx to avoid clash with history

            if st.button("↩️ Create Another Page", key="new_notion_task", use_container_width=True):
                st.session_state.notion_workflow_state = "idle"
                st.session_state.notion_current_plan   = []
                st.session_state.notion_parsed_intent  = None
                st.session_state.last_notion_result    = None
                # Increment version to reset all input fields
                st.session_state.notion_preview_title = ""
                st.session_state.notion_preview_content = ""
                st.session_state.notion_is_editing = False
                st.session_state.notion_form_version += 1
                st.rerun()

        # ── History log ────────────────────────────────────────────────────────
        _render_history()


# ── Page card ──────────────────────────────────────────────────────────────────
def _render_page_card(rec: dict, idx: int, show_raw: bool = False):
    """Render a single page record as a styled info card."""
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, rgba(108,99,255,0.08), rgba(167,139,250,0.04));
            border: 1px solid rgba(108,99,255,0.28);
            border-radius: 12px;
            padding: 18px 22px;
            margin-bottom: 10px;
        ">
        """,
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
            key=f"notion_content_v2_{idx}_{rec.get('created_at', idx)}",
            label_visibility="collapsed",
        )
    else:
        st.caption("No content body — page created with title only.")

    st.markdown("</div>", unsafe_allow_html=True)

    if show_raw:
        with st.expander("📦 Raw API Response"):
            st.json(rec["data"])


# ── History section ────────────────────────────────────────────────────────────
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
        label = f"{i + 1}. {rec['title']}  —  {rec.get('created_at', '')}"
        with st.expander(label, expanded=(i == 0)):
            _render_page_card(rec, idx=real_idx, show_raw=False)
