import re
import streamlit as st
from datetime import datetime
from notion.notion_handler import (
    is_notion_authenticated, get_notion_auth_url, exchange_code_for_token,
    create_notion_page, get_authenticated_user, clear_authentication,
    _load_config, _save_config, generate_page_content, refine_direct_content,
    get_existing_pages, get_page_preview, get_notion_databases,
    get_database_items, list_page_children,
)

FORMATTING_OPTIONS = {
    "Text Formatting": ["Text","Bold","Italic","Underline","Strikethrough","Inline Code","Text Color","Background Color (Highlight)","Equations (Math)","Comments"],
    "Basic Blocks": ["Heading 1","Heading 2","Heading 3","Bullet List","Numbered List","To-do List (Checklist)","Multi Checkbox","Toggle List","Quote","Callout","Divider","Table (Simple)","Table of Contents"],
    "Media & Files": ["Image","Video","Audio","File","Web Bookmark","Code Block","YouTube Embed","Google Drive Embed","PDF Embed","Maps Embed","Tally Form"],
    "Databases & Views": ["Table View","Board View (Kanban)","Gallery View","List View","Calendar View","Timeline View","Task Checkbox (Database)"],
    "Advanced & Interactive": ["Synced Block","Columns","Button","Template Button","Breadcrumb"],
}

MEDIA_NEEDS_INPUT = {"Image","Video","Audio","File","Web Bookmark","YouTube Embed","Google Drive Embed","PDF Embed","Maps Embed","Tally Form","Button"}
URL_ONLY = {"YouTube Embed","Google Drive Embed","PDF Embed","Maps Embed","Tally Form","Web Bookmark"}
MEDIA_PLACEHOLDERS = {
    "Image":"https://example.com/image.png","Video":"https://example.com/video.mp4",
    "Audio":"https://example.com/audio.mp3","File":"https://example.com/doc.pdf",
    "Web Bookmark":"https://example.com","YouTube Embed":"https://www.youtube.com/watch?v=...",
    "Google Drive Embed":"https://drive.google.com/file/d/...","PDF Embed":"https://example.com/doc.pdf",
    "Maps Embed":"https://maps.google.com/...","Tally Form":"https://tally.so/r/...","Button":"https://example.com/action",
}

BLOCK_HINT_MAP = {
    "Bold":"Use **bold** text for key terms.","Italic":"Use *italic* for emphasis.",
    "Underline":"Emphasize important words (bold as proxy).","Strikethrough":"Use ~~strikethrough~~ for removed items.",
    "Inline Code":"Use `inline code` for technical terms.","Text Color":"Use colored text for visual hierarchy.",
    "Background Color (Highlight)":"Use >> callout blocks to highlight key info.",
    "Equations (Math)":"Include math equations using $...$ syntax.","Comments":"Add > quote blocks as commentary.",
    "Heading 1":"Use # Heading 1 for main title section.","Heading 2":"Use ## Heading 2 for major sections.",
    "Heading 3":"Use ### Heading 3 for subsections.","Bullet List":"Use - bullet lists for unordered items.",
    "Numbered List":"Use 1. numbered lists for ordered steps.","To-do List (Checklist)":"Use - [ ] checkboxes for tasks.",
    "Multi Checkbox":"Generate a checklist with at least 3-5 items using the - [ ] checkbox syntax. Ensure each item is a real, interactive checkbox block.",
    "Toggle List":"Use >? toggle blocks for collapsible details.","Quote":"Use > quote blocks for statements.",
    "Callout":"Use >> callout blocks with emoji for tips/warnings.","Divider":"Use --- dividers between sections.",
    "Table (Simple)":"Include a | table | with headers.","Table of Contents":"Start with a structured overview.",
    "Code Block":"Use ```language code blocks.","Table View":"Structure data as a table.",
    "Board View (Kanban)":"Organize into status columns: To Do, In Progress, Done.",
    "Gallery View":"Present items as a visual card gallery.","List View":"Present items as a clean list.",
    "Calendar View":"Include dates and schedule info.","Timeline View":"Include a chronological sequence.",
    "Task Checkbox (Database)":"Generate a professional task list with at least 3-5 tasks using the - [ ] checkbox syntax, structured like a database task tracker.",
    "Synced Block":"Note this block should be synced.","Columns":"Organize into side-by-side columns.",
    "Button":"Include an actionable button call-to-action.","Breadcrumb":"Include a navigation breadcrumb.",
    "YouTube Embed":"Include a YouTube video embed.","Google Drive Embed":"Include a Google Drive embed.",
    "Maps Embed":"Include a map embed.","PDF Embed":"Include a PDF embed.","Tally Form":"Include a form embed.",
}

def _init_state():
    defaults = {
        "notion_workflow_state":"idle","notion_current_plan":[],"notion_parsed_intent":None,
        "last_notion_result":None,"notion_page_history":[],"notion_preview_content":"",
        "notion_preview_title":"","notion_is_editing":False,"notion_form_version":0,
        "notion_media_items":[],"notion_confirm_cancel":False,
        "notion_fmt_applied":False,"notion_fmt_selections":{},
        "notion_parent_mode":"new_page","notion_selected_parent_id":None,
        "notion_selected_parent_name":"","notion_parent_selection_mode":False,
        "notion_confirm_cancel_parent":False,"notion_parent_selected":False,
    }
    for k,v in defaults.items():
        if k not in st.session_state:
            st.session_state[k]=v

def _reset_form():
    st.session_state.notion_workflow_state="idle"
    st.session_state.notion_current_plan=[]
    st.session_state.notion_parsed_intent=None
    st.session_state.last_notion_result=None
    st.session_state.notion_preview_title=""
    st.session_state.notion_preview_content=""
    st.session_state.notion_is_editing=False
    st.session_state.notion_media_items=[]
    st.session_state.notion_confirm_cancel=False
    st.session_state.notion_fmt_applied=False
    st.session_state.notion_fmt_selections={}
    st.session_state.notion_parent_mode="new_page"
    st.session_state.notion_selected_parent_id=None
    st.session_state.notion_selected_parent_name=""
    st.session_state.notion_parent_selection_mode=False
    st.session_state.notion_confirm_cancel_parent=False
    st.session_state.notion_parent_selected=False
    st.session_state.notion_form_version+=1


def _build_media_blocks(media_items: list, position: str = "end") -> str:
    """
    Convert queued media items into proper block syntax.
    position: 'end' = append at end, 'inline' = caller handles placement.

    Notion API limitations:
    - Images: only external HTTPS URLs work. Local uploads cannot be embedded.
    - Videos: external URLs including YouTube work via video block.
    - Embeds: Google Drive, Maps, Tally, PDF use embed block.
    """
    if not media_items:
        return ""
    lines = []
    if position == "end":
        lines += ["---", "## 📎 Media & Attachments", ""]

    for item in media_items:
        t   = item["type"]
        v   = item["value"]
        src = item["source"]

        if t == "Image":
            if src == "url" and v.startswith("http"):
                lines.append(f"![Image]({v})")
            else:
                lines.append(f"> 🖼️ Image `{v}` — host it externally (https://...) to embed in Notion")

        elif t == "Video":
            if src == "url":
                lines.append(f"{{video:{v}}}")
            else:
                lines.append(f"> 🎬 Video `{v}` — host externally to embed")

        elif t == "YouTube Embed":
            lines.append(f"{{video:{v}}}")

        elif t in ("Google Drive Embed", "PDF Embed", "Maps Embed", "Tally Form"):
            lines.append(f"{{embed:{v}}}")

        elif t == "Web Bookmark":
            lines.append(f"> 🔖 Bookmark: [{v}]({v})")

        elif t == "Audio":
            if src == "url":
                lines.append(f"> 🎵 Audio: [{v}]({v})")
            else:
                lines.append(f"> 🎵 Audio `{v}`")

        elif t == "File":
            lines.append(f"> 📄 File: {v}")

        elif t == "Button":
            parts = v.split("|", 1)
            label = parts[0] if parts else "Click Here"
            url   = parts[1] if len(parts) > 1 else "#"
            lines.append(f"{{button:{label}|{url}}}")

        else:
            lines.append(f"> 🔗 {t}: [{v}]({v})")

    return "\n".join(lines)


def _render_rich_preview(content: str):
    """Render preview with images, video, embeds, audio, buttons all visible."""
    if not content:
        st.caption("*(no content)*")
        return

    lines = content.split("\n")
    md_buf = []

    def flush():
        if md_buf:
            st.markdown("\n".join(md_buf))
            md_buf.clear()

    for line in lines:
        s = line.strip()

        # Image
        m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", s)
        if m:
            flush()
            url = m.group(2)
            alt = m.group(1) or "Image"
            if url.startswith("http"):
                try:
                    st.image(url, caption=alt, use_container_width=False, width=480)
                except Exception:
                    st.markdown(f"🖼️ [Image: {alt}]({url})")
            else:
                st.info(f"🖼️ Local image `{url}` — will appear in Notion only if hosted externally.")
            continue

        # Video / YouTube
        m = re.match(r"\{video:(.+)\}", s)
        if m:
            flush()
            url = m.group(1).strip()
            try:
                st.video(url)
            except Exception:
                st.markdown(f"🎬 [Video]({url})")
            continue

        # Embed
        m = re.match(r"\{embed:(.+)\}", s)
        if m:
            flush()
            url = m.group(1).strip()
            st.markdown(
                f"<div style='background:rgba(108,99,255,0.08);border:1px solid rgba(108,99,255,0.3);"
                f"border-radius:8px;padding:10px 14px;margin:6px 0'>"
                f"🔗 <b>Embed:</b> <a href='{url}' target='_blank'>{url}</a></div>",
                unsafe_allow_html=True)
            continue

        # Button
        m = re.match(r"\{button:(.+)\|(.+)\}", s)
        if m:
            flush()
            label = m.group(1).strip()
            url   = m.group(2).strip()
            st.markdown(
                f"<a href='{url}' target='_blank' style='display:inline-block;"
                f"background:linear-gradient(135deg,#6c63ff,#8b5cf6);color:white;"
                f"padding:8px 22px;border-radius:6px;font-weight:600;text-decoration:none;"
                f"margin:6px 0'>{label}</a>",
                unsafe_allow_html=True)
            continue

        # Audio
        m = re.match(r">\s*🎵\s*Audio:\s*\[([^\]]+)\]\(([^)]+)\)", s)
        if m:
            flush()
            url = m.group(2)
            try:
                st.audio(url)
            except Exception:
                st.markdown(f"🎵 [Audio]({url})")
            continue

        md_buf.append(line)

    flush()


def _render_page_card(rec: dict, idx: int, show_raw: bool = False):
    st.markdown(
        "<div style='background:linear-gradient(135deg,rgba(108,99,255,0.08),rgba(167,139,250,0.04));"
        "border:1px solid rgba(108,99,255,0.28);border-radius:12px;padding:18px 22px;margin-bottom:10px'>",
        unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**📄 Title:** {rec['title']}")
        st.markdown(f"**📁 Created in:** {rec['parent_name']}")
    with c2:
        st.markdown(f"**🕐 Created at:** {rec.get('created_at','—')}")
        st.markdown(f"**🔗 Link:** [Open in Notion]({rec['url']})")
    if rec.get("content"):
        st.markdown("**📝 Content written:**")
        st.text_area("", value=rec["content"], height=160, disabled=True,
                     key=f"notion_card_{idx}_{rec.get('created_at',idx)}", label_visibility="collapsed")
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
    c1, _ = st.columns([1, 5])
    with c1:
        if st.button("🗑️ Clear History", key="clear_notion_history"):
            st.session_state.notion_page_history = []
            st.rerun()
    for i, rec in enumerate(reversed(history)):
        real_idx = len(history) - 1 - i
        with st.expander(f"{i+1}. {rec['title']}  —  {rec.get('created_at','')}", expanded=(i==0)):
            _render_page_card(rec, idx=real_idx, show_raw=False)


def render_notion_listing():
    st.markdown("### 📋 Listing System")
    st.caption("Browse, filter, and sort your Notion pages and data.")

    # 1. Listing Filters & Controls
    col_l1, col_l2, col_l3 = st.columns([1.5, 1.5, 1.2])
    
    with col_l1:
        # Use popover to fulfill the "click icon to open/close" behavior
        with st.popover("📁 Listing Category", use_container_width=True):
            listing_type = st.radio("Select Category", [
                "General Page Listings", "Nested & Structure Listings", "Database Listings",
                "Task & Productivity Listings", "Workspace Listings", "Content Block Listings",
                "Collaboration Listings", "Search-Based Listings", "Template & Notes Listings",
                "Activity Listings", "Special Listings"
            ], key="notion_listing_category_radio")
    
    sub_types = {
        "General Page Listings": ["Total Pages", "Recent Pages", "Last Created Pages", "Last Edited Pages", "Favorite Pages", "Archived Pages", "Shared Pages", "Private Pages", "Public Pages", "Top Used Pages", "Pinned Pages"],
        "Nested & Structure Listings": ["Pages Inside a Page", "Subpages", "Nested Pages", "Child Pages", "Linked Pages", "Page Hierarchy", "Breadcrumb/Page Path", "Workspace Structure"],
        "Database Listings": ["Databases", "Database Items", "Recent Database Entries", "Filtered Database Listing", "Sorted Database Listing"],
        "Task & Productivity Listings": ["Completed Tasks", "Pending Tasks", "Overdue Tasks", "Reminders", "Calendar Entries", "Scheduled Notes", "Todo Pages", "Project Pages"],
        "Workspace Listings": ["Workspace Pages", "Teamspace Pages", "Connected Workspace"],
        "Content Block Listings": ["Page Content Blocks", "Headings", "Paragraphs", "Checklist Items", "Tables", "Images/Files", "Links", "Code Blocks"],
        "Collaboration Listings": ["Comments", "Mentions", "Collaborators", "Shared Users"],
        "Search-Based Listings": ["Search Keyword", "Search by Title", "Search by Date", "Search by Tag", "Search by User"],
        "Template & Notes Listings": ["Templates", "Journals", "Meeting Notes", "Notes"],
        "Activity Listings": ["Recently Opened Pages", "Recently Viewed Pages", "Recently Updated Pages"],
        "Special Listings": ["Duplicate Pages", "Empty Pages", "Untitled Pages", "AI Generated Pages", "Summarized Pages", "Extracted Tasks"]
    }
    
    with col_l2:
        with st.popover("🔍 Specific View", use_container_width=True):
            specific_type = st.radio("Select View", sub_types.get(listing_type, ["Total Pages"]), key="notion_listing_subtype_radio")
    
    with col_l3:
        # Integrated Listing Limit UI
        if "notion_limit_val" not in st.session_state:
            st.session_state.notion_limit_val = 10
            
        l_row = st.columns([1.5, 0.8, 0.8, 1.2])
        
        with l_row[0]:
            # Display current limit (can be a number input for direct typing)
            # Remove key to avoid "modified after instantiation" error
            curr_val = st.number_input("Limit", value=st.session_state.notion_limit_val, 
                                        min_value=1, max_value=500, label_visibility="collapsed")
            if curr_val != st.session_state.notion_limit_val:
                st.session_state.notion_limit_val = curr_val
                st.rerun()
                
        with l_row[1]:
            if st.button("−", key="notion_l_dec", use_container_width=True):
                st.session_state.notion_limit_val = max(1, st.session_state.notion_limit_val - 1)
                st.rerun()
                
        with l_row[2]:
            if st.button("+", key="notion_l_inc", use_container_width=True):
                st.session_state.notion_limit_val = min(500, st.session_state.notion_limit_val + 1)
                st.rerun()
                
        with l_row[3]:
            # Dropdown for fixed options
            with st.popover("", use_container_width=True):
                st.markdown("**Quick Select**")
                if st.button("10", key="notion_l_10", use_container_width=True):
                    st.session_state.notion_limit_val = 10
                    st.rerun()
                if st.button("20", key="notion_l_20", use_container_width=True):
                    st.session_state.notion_limit_val = 20
                    st.rerun()
                if st.button("50", key="notion_l_50", use_container_width=True):
                    st.session_state.notion_limit_val = 50
                    st.rerun()
                if st.button("All", key="notion_l_all", use_container_width=True):
                    st.session_state.notion_limit_val = 500
                    st.rerun()
                    
        limit = st.session_state.notion_limit_val

    # Search & Sorting Row
    col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
    with col_s1:
        search_query = st.text_input("🔍 Search Keyword", placeholder="Search in title...", key="notion_listing_search")
    with col_s2:
        sort_order = st.radio("Sort Order", ["Newest First", "Oldest First"], horizontal=True, key="notion_listing_sort")
    with col_s3:
        st.write("") # spacing
        st.write("")
        fetch_clicked = st.button("📥 Fetch Data", use_container_width=True, key="notion_fetch_listing_btn")

    # Parent Selection for Nested (only if triggered or in state)
    parent_id_for_nested = st.session_state.get("notion_listing_parent_id")
    if specific_type in ["Pages Inside a Page", "Subpages", "Child Pages", "Database Items"]:
        st.markdown(f"**Target Selection for {specific_type}:**")
        sc1, sc2 = st.columns([3, 1])
        with sc1:
            if "Database" in specific_type:
                db_res = get_notion_databases()
                if db_res.get("success"):
                    dbs = {db["title"]: db["id"] for db in db_res.get("databases", [])}
                    sel_db_title = st.selectbox("Select Database", list(dbs.keys()), key="nested_db_sel")
                    parent_id_for_nested = dbs.get(sel_db_title)
            else:
                pg_res = get_existing_pages()
                if pg_res.get("success"):
                    pgs = {p["title"]: p["id"] for p in pg_res.get("pages", [])}
                    sel_pg_title = st.selectbox("Select Parent Page", list(pgs.keys()), key="nested_pg_sel")
                    parent_id_for_nested = pgs.get(sel_pg_title)
        with sc2:
            st.write("")
            st.write("")
            if st.button("Apply Target", key="apply_target_btn", use_container_width=True):
                st.session_state.notion_listing_parent_id = parent_id_for_nested
                st.rerun()

    st.divider()

    # 2. Fetch Data (only if button clicked or already in session)
    if not fetch_clicked and "notion_listing_items" not in st.session_state:
        st.info("⚠️ Please select a **Listing Type** and click **📥 Fetch Data** to view records.")
        return

    if fetch_clicked:
        with st.spinner(f"Fetching {specific_type}..."):
            items = []
            if specific_type == "Databases":
                res = get_notion_databases()
                items = res.get("databases", []) if res.get("success") else []
            elif specific_type == "Database Items" and parent_id_for_nested:
                res = get_database_items(parent_id_for_nested)
                items = res.get("items", []) if res.get("success") else []
            elif specific_type in ["Pages Inside a Page", "Subpages", "Child Pages"] and parent_id_for_nested:
                res = list_page_children(parent_id_for_nested)
                items = res.get("children", []) if res.get("success") else []
            elif specific_type == "Archived Pages":
                res = get_existing_pages()
                items = [p for p in res.get("pages", []) if p.get("archived")] if res.get("success") else []
            else:
                res = get_existing_pages()
                items = res.get("pages", []) if res.get("success") else []
            
            st.session_state.notion_listing_items = items
            st.session_state.notion_listing_last_type = specific_type
            st.session_state.notion_listing_page = 1 # Reset to page 1 on new fetch

    items = st.session_state.get("notion_listing_items", [])
    
    # Filter by Search Query
    if search_query:
        items = [p for p in items if search_query.lower() in p.get("title", "").lower()]

    # Filter for specific types
    if specific_type == "Untitled Pages":
        items = [p for p in items if p.get("title") == "Untitled" or not p.get("title")]
    elif "Task" in specific_type or "Todo" in specific_type:
        items = [p for p in items if any(kw in p.get("title", "").lower() for kw in ["task", "todo", "project", "list", "fix", "issue"])]
    elif "Journal" in specific_type or "Note" in specific_type:
        items = [p for p in items if any(kw in p.get("title", "").lower() for kw in ["journal", "note", "meeting", "daily", "memo"])]
    elif "AI Generated" in specific_type:
        items = [p for p in items if any(kw in p.get("title", "").lower() for kw in ["ai", "generated", "bot"])]

    if not items:
        st.warning(f"No records found for '{specific_type}'.")
        if st.button("Clear Search", key="clear_search_l"):
            st.session_state.notion_listing_search = ""
            st.rerun()
        return

    # Sort
    items.sort(key=lambda x: x.get("created_time", ""), reverse=(sort_order == "Newest First"))
    
    # Limit
    display_items = items[:limit]
    
    # Pagination logic
    items_per_page = 10
    total_items = len(display_items)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    if "notion_listing_page" not in st.session_state:
        st.session_state.notion_listing_page = 1
    
    # Ensure current page is valid
    if st.session_state.notion_listing_page > total_pages and total_pages > 0:
        st.session_state.notion_listing_page = 1
        
    start_idx = (st.session_state.notion_listing_page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    page_items = display_items[start_idx:end_idx]

    for i, item in enumerate(page_items):
        actual_idx = start_idx + i
        r_cols = st.columns([0.4, 2.5, 1.5, 1.5, 3, 0.8])
        
        with r_cols[0]:
            st.write(f"{actual_idx+1}")
        
        with r_cols[1]:
            st.markdown(f"**{item.get('title', 'Untitled')}**")
        
        with r_cols[2]:
            st.write(item.get("created_by", "Unknown"))
            
        with r_cols[3]:
            dt = item.get("created_time", "").replace("T", " ").split(".")[0]
            st.write(dt)
            
        with r_cols[4]:
            preview = get_page_preview(item['id'])
            if preview:
                if len(preview) > 90:
                    preview = preview[:87] + "..."
                st.caption(preview)
            else:
                st.caption("_(no preview)_")
                
        with r_cols[5]:
            if st.button("👁️", key=f"vbtn_{item['id']}_{i}", help="View Details"):
                st.session_state.notion_viewing_id = item['id']
                st.session_state.notion_viewing_title = item['title']
                st.rerun()

        if i < len(page_items) - 1:
            st.markdown("<hr style='margin:2px 0; border:none; border-top:1px solid #222'>", unsafe_allow_html=True)

    st.caption(f"Showing {start_idx+1}-{end_idx} of {total_items} items (Page {st.session_state.notion_listing_page}/{total_pages})")

    # Pagination Controls
    if total_pages > 1:
        st.divider()
        p_col1, p_col2, p_col3, p_col4, p_col5 = st.columns([1, 1, 2, 1, 1])
        with p_col1:
            if st.button("⏪ First", disabled=(st.session_state.notion_listing_page == 1), use_container_width=True):
                st.session_state.notion_listing_page = 1
                st.rerun()
        with p_col2:
            if st.button("⬅️ Prev", disabled=(st.session_state.notion_listing_page == 1), use_container_width=True):
                st.session_state.notion_listing_page -= 1
                st.rerun()
        with p_col3:
            st.markdown(f"<div style='text-align:center; font-weight:600; padding: 5px;'>Page {st.session_state.notion_listing_page} of {total_pages}</div>", unsafe_allow_html=True)
        with p_col4:
            if st.button("Next ➡️", disabled=(st.session_state.notion_listing_page == total_pages), use_container_width=True):
                st.session_state.notion_listing_page += 1
                st.rerun()
        with p_col5:
            if st.button("Last ⏩", disabled=(st.session_state.notion_listing_page == total_pages), use_container_width=True):
                st.session_state.notion_listing_page = total_pages
                st.rerun()

    # 4. Detailed View Modal (Overlay)
    if st.session_state.get("notion_viewing_id"):
        _render_view_overlay()


def _render_view_overlay():
    page_id = st.session_state.notion_viewing_id
    title = st.session_state.notion_viewing_title
    
    st.markdown("---")
    c1, c2 = st.columns([5, 1])
    with c1:
        st.subheader(f"📖 Viewing: {title}")
    with c2:
        if st.button("Close", key="close_notion_view"):
            st.session_state.notion_viewing_id = None
            st.rerun()
            
    with st.spinner("Fetching page content..."):
        # We can reuse _render_rich_preview if we get the markdown
        # But get_page_preview only gets a snippet.
        # Let's add a full page fetcher or just show the snippet for now.
        preview = get_page_preview(page_id, max_lines=20)
        st.markdown(f"""
        <div style='background: #0f0f0f; border: 1px solid #6c63ff; border-radius: 12px; padding: 25px; min-height: 200px;'>
            {preview if preview else "*(No content or could not fetch)*"}
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"[Open in Notion ↗](https://www.notion.so/{page_id.replace('-', '')})")


def render_notion_workflow():
    st.markdown('<div class="page-title">📝 Notion AI Agent</div>', unsafe_allow_html=True)

    # OAuth callback
    if "code" in st.query_params:
        code = st.query_params["code"]
        with st.spinner("🔗 Completing Notion connection..."):
            if exchange_code_for_token(code):
                st.success("✅ Notion connected successfully!")
                st.query_params.clear()
                st.rerun()
            else:
                st.error("❌ Failed to connect Notion.")

    tab_agent, tab_listing, tab_settings = st.tabs(["🤖 Create Page", "📋 Listing", "⚙️ Settings"])

    # ── Settings ───────────────────────────────────────────────────────────────
    with tab_settings:
        with st.expander("📖 Setup Guide", expanded=False):
            st.markdown("""
            Go to **[Notion Developers](https://www.notion.so/my-integrations)** → Developer Portal.
            1. New Connection → OAuth → set Redirect URL to `http://localhost:8501`.
            2. Copy **Client ID** and **Client Secret**.
            """)
        st.subheader("🔐 Notion API Configuration")
        cfg = _load_config()
        cid  = st.text_input("Client ID",     value=cfg.get("client_id",""))
        csec = st.text_input("Client Secret", value=cfg.get("client_secret",""), type="password")
        ruri = st.text_input("Redirect URL",  value=cfg.get("redirect_uri","http://localhost:8501"))
        if st.button("💾 Save Configuration", key="save_notion_config"):
            _save_config({"client_id":cid,"client_secret":csec,"redirect_uri":ruri})
            st.success("✅ Saved!")
            st.rerun()
        st.divider()
        st.subheader("👤 Connection Status")
        if is_notion_authenticated():
            st.success(f"✅ Connected as: {get_authenticated_user()}")
            if st.button("🔓 Disconnect", key="disconnect_notion"):
                clear_authentication(); st.rerun()
        else:
            st.info("Not connected.")
            auth_url = get_notion_auth_url()
            if auth_url:
                st.link_button("🔓 Connect Notion", auth_url, use_container_width=True)
            else:
                st.warning("Configure Client ID and Redirect URL first.")

    # ── Listing tab ────────────────────────────────────────────────────────────
    with tab_listing:
        if not is_notion_authenticated():
            st.warning("⚠️ Connect your Notion account in Settings first.")
        else:
            render_notion_listing()

    # ── Agent tab ──────────────────────────────────────────────────────────────
    with tab_agent:
        if not is_notion_authenticated():
            st.warning("⚠️ Connect your Notion account in Settings first.")
            return

        _init_state()
        version = st.session_state.notion_form_version



        parent_selected = st.session_state.notion_parent_selected
        parent_mode = st.session_state.notion_parent_mode
        selection_mode = st.session_state.notion_parent_selection_mode

        # 1. Header Instruction / Status Line
        if not parent_selected:
            st.markdown(
                f"<div style='background:rgba(255,193,7,0.1);border:1px solid rgba(255,193,7,0.3);"
                f"border-radius:10px;padding:12px 18px;margin-bottom:16px;color:#ffc107;font-size:14px;font-weight:500'>"
                f"⚠️ Please select a page type: New or Existing, then fill the input box.</div>",
                unsafe_allow_html=True)
        elif not selection_mode:
            # Blue status line after selection is fully confirmed or New Page is selected
            text = "Create a New Page" if parent_mode == "new_page" else f"Create a new page in the {st.session_state.notion_selected_parent_name} page"
            
            sc1, sc2 = st.columns([5, 1])
            with sc1:
                st.markdown(
                    f"<div style='background:rgba(108,99,255,0.12);border:1px solid rgba(108,99,255,0.3);"
                    f"border-radius:10px;padding:12px 18px;color:#a78bfa;font-weight:600;font-size:14px'>"
                    f"✅ {text}</div>", unsafe_allow_html=True)
            with sc2:
                if st.button("Cancel", key="cancel_selection_status", use_container_width=True):
                    st.session_state.notion_confirm_cancel_parent = True
                    st.rerun()
        else:
            # Blue status line while selecting existing page
            sc1, sc2 = st.columns([5, 1])
            with sc1:
                st.markdown(
                    f"<div style='background:rgba(108,99,255,0.12);border:1px solid rgba(108,99,255,0.3);"
                    f"border-radius:10px;padding:12px 18px;color:#a78bfa;font-weight:600;font-size:14px'>"
                    f"🔍 Selecting Existing Page...</div>", unsafe_allow_html=True)
            with sc2:
                if st.button("Cancel", key="cancel_selection_picking", use_container_width=True):
                    st.session_state.notion_confirm_cancel_parent = True
                    st.rerun()

        # 2. Selection Buttons (only when nothing selected)
        if not parent_selected:
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("Create New Page", key="select_new_page", use_container_width=True):
                    st.session_state.notion_parent_selected = True
                    st.session_state.notion_parent_mode = "new_page"
                    st.session_state.notion_selected_parent_id = None
                    st.session_state.notion_selected_parent_name = ""
                    st.rerun()
            with btn_col2:
                if st.button("Create in Existing Page", key="select_existing_page", use_container_width=True):
                    st.session_state.notion_parent_selected = True
                    st.session_state.notion_parent_mode = "existing_page"
                    st.session_state.notion_parent_selection_mode = True
                    st.rerun()

        # 3. Existing Page Selection UI
        if parent_selected and parent_mode == "existing_page" and selection_mode:
            st.divider()
            with st.spinner("📂 Fetching your Notion pages…"):
                result = get_existing_pages()
            
            if not result.get("success"):
                st.error(f"❌ Could not fetch pages: {result.get('error')}")
                if st.button("↩️ Back to Options", key="back_to_options"):
                    st.session_state.notion_parent_selection_mode = False
                    st.session_state.notion_parent_selected = False
                    st.rerun()
            else:
                pages = result.get("pages", [])
                if not pages:
                    st.info("📭 No existing pages found in your Notion workspace.")
                    if st.button("↩️ Back to Options", key="back_no_pages"):
                        st.session_state.notion_parent_selection_mode = False
                        st.session_state.notion_parent_selected = False
                        st.rerun()
                else:
                    st.caption(f"Select one of your {len(pages)} pages")
                    

                    page_options = {p["title"]: p["id"] for p in pages}
                    selected_title = st.selectbox(
                        "Choose a page:",
                        options=list(page_options.keys()),
                        key=f"page_selector_{version}",
                        label_visibility="collapsed"
                    )
                    
                    if selected_title:
                        selected_id = page_options[selected_title]
                        
                        # Page selection area and the line showing "✅ Selected: ..." with OK button
                        c1, c2 = st.columns([9, 1.2])
                        with c1:
                            st.markdown(
                                f"<div style='background:rgba(106,170,100,0.12);border:1px solid rgba(106,170,100,0.4);"
                                f"border-radius:8px;padding:0 16px;color:#6ee7b7;font-weight:500;height:48px;display:flex;align-items:center'>"
                                f"✅ <b>Selected:</b> {selected_title}</div>", unsafe_allow_html=True)
                        with c2:
                            # Custom styled button with matching height
                            st.markdown('<div class="custom-button-container">', unsafe_allow_html=True)
                            if st.button("OK", key="confirm_parent_ok", use_container_width=True):
                                st.session_state.notion_selected_parent_id = selected_id
                                st.session_state.notion_selected_parent_name = selected_title
                                st.session_state.notion_parent_selection_mode = False
                                st.rerun()
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            # CSS to match button height and style to the status box
                            st.markdown("""
<style>
.custom-button-container button {
    height: 48px !important;
    margin: 0 !important;
    border-radius: 8px !important;
    border: 1px solid rgba(106,170,100,0.4) !important;
    background: rgba(106,170,100,0.15) !important;
    color: #6ee7b7 !important;
    font-weight: 600 !important;
}
.custom-button-container button:hover {
    background: rgba(106,170,100,0.25) !important;
    border-color: rgba(106,170,100,0.8) !important;
}
</style>
""", unsafe_allow_html=True)





        # Confirmation Modal for Parent Selection
        if st.session_state.get("notion_confirm_cancel_parent"):
            import streamlit.components.v1 as _components
            _components.html("""
<script>
(function() {
  var doc = window.parent.document;
  if (doc.getElementById('notion-cancel-parent-overlay')) return;

  var overlay = doc.createElement('div');
  overlay.id = 'notion-cancel-parent-overlay';
  overlay.style.cssText = [
    'position:fixed','top:0','left:0','width:100%','height:100%',
    'background:rgba(0,0,0,0.65)','z-index:999999',
    'display:flex','align-items:center','justify-content:center',
    'backdrop-filter:blur(3px)','-webkit-backdrop-filter:blur(3px)'
  ].join(';');

  var card = doc.createElement('div');
  card.style.cssText = [
    'background:#1a1a2e','border:1px solid rgba(108,99,255,0.45)',
    'border-radius:16px','padding:36px 40px','text-align:center',
    'min-width:340px','max-width:420px','box-shadow:0 20px 60px rgba(0,0,0,0.5)',
    'font-family:Inter,sans-serif'
  ].join(';');

  card.innerHTML = `
    <div style="font-size:40px;margin-bottom:12px">❓</div>
    <h2 style="color:#f0f0f0;margin:0 0 8px;font-size:20px;font-weight:700">Cancel selection?</h2>
    <p style="color:#999;font-size:14px;margin:0 0 28px;line-height:1.5">
      Would you like to keep the current selection or cancel/remove it?
    </p>
    <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
      <button id="notion-parent-keep" style="
        background:linear-gradient(135deg,#6c63ff,#8b5cf6);color:white;
        border:none;border-radius:8px;padding:10px 28px;font-size:14px;
        font-weight:600;cursor:pointer;transition:opacity 0.15s">
        Keep Selection
      </button>
      <button id="notion-parent-cancel" style="
        background:linear-gradient(135deg,#dc2626,#b91c1c);color:white;
        border:none;border-radius:8px;padding:10px 28px;font-size:14px;
        font-weight:600;cursor:pointer;transition:opacity 0.15s">
        Cancel Selection
      </button>
    </div>
  `;

  overlay.appendChild(card);
  doc.body.appendChild(overlay);

  doc.getElementById('notion-parent-keep').onclick = function() {
    overlay.remove();
    var btns = doc.querySelectorAll('button');
    for (var b of btns) {
      if (b.innerText.trim() === 'Keep Selection') { b.click(); break; }
    }
  };
  doc.getElementById('notion-parent-cancel').onclick = function() {
    overlay.remove();
    var btns = doc.querySelectorAll('button');
    for (var b of btns) {
      if (b.innerText.trim() === 'Cancel Selection') { b.click(); break; }
    }
  };
})();
</script>
""", height=0, width=0)

            hpc1, hpc2 = st.columns(2)
            with hpc1:
                if st.button("Keep Selection", key="keep_parent_selection"):
                    st.session_state.notion_confirm_cancel_parent = False
                    st.rerun()
            with hpc2:
                if st.button("Cancel Selection", key="cancel_parent_start_over"):
                    st.session_state.notion_confirm_cancel_parent = False
                    st.session_state.notion_parent_selection_mode = False
                    st.session_state.notion_parent_selected = False
                    st.session_state.notion_parent_mode = "new_page"
                    st.session_state.notion_selected_parent_id = None
                    st.session_state.notion_selected_parent_name = ""
                    st.rerun()


        page_title = st.text_input("📄 Page Title", placeholder="e.g. Project Research",
                                   key=f"notion_title_{version}", disabled=not parent_selected,
                                   help="Please select New Page or Existing Page first before filling the inputs." if not parent_selected else None)
        dtv = st.session_state.get(f"notion_direct_{version}", "").strip()
        aiv = st.session_state.get(f"notion_ai_{version}", "").strip()
        c1, c2 = st.columns(2)
        with c1:
            direct_content = st.text_area("✍️ Direct Content",
                placeholder="Enter text to keep as-is…",
                key=f"notion_direct_{version}", height=130, disabled=(aiv != "" or not parent_selected),
                help="Please select New Page or Existing Page first before filling the inputs." if not parent_selected else None)
        with c2:
            ai_prompt = st.text_area("🤖 AI Generation Prompt",
                placeholder="Describe what you want the AI to generate…",
                key=f"notion_ai_{version}", height=130, disabled=(dtv != "" or not parent_selected),
                help="Please select New Page or Existing Page first before filling the inputs." if not parent_selected else None)

        # ── Formatting dropdowns ───────────────────────────────────────────────
        st.markdown("**🎨 Formatting & Block Preferences**")
        st.caption("Open each dropdown, select options, then click **Apply Preferences** when done.")

        ms_cols = st.columns(5)
        # Use a staging dict — only committed when Apply is clicked
        staging_key = f"notion_fmt_staging_{version}"
        if staging_key not in st.session_state:
            st.session_state[staging_key] = {k: [] for k in FORMATTING_OPTIONS}
        staging = st.session_state[staging_key]

        for col, key in zip(ms_cols, list(FORMATTING_OPTIONS.keys())):
            with col:
                opts = FORMATTING_OPTIONS[key]
                cur  = staging.get(key, [])
                cnt  = len(cur)
                lbl  = f"{key} ({cnt}✓)" if cnt else key
                with st.popover(lbl, use_container_width=True):
                    st.markdown(f"**{key}**")
                    new_cur = []
                    for opt in opts:
                        is_sel = opt in cur
                        checked = st.checkbox(opt, value=is_sel,
                                              key=f"cb_{key}_{opt}_{version}")
                        if checked:
                            new_cur.append(opt)
                    # Only update staging — no st.rerun() here to avoid lag
                    staging[key] = new_cur
                    st.session_state[staging_key] = staging

        st.caption("Click any option to select ✓. Click again to deselect.")

        # Apply button — commits staging to applied selections
        if st.button("✅ Apply Preferences", key=f"apply_fmt_{version}"):
            st.session_state.notion_fmt_selections = {k: list(v) for k, v in staging.items()}
            st.session_state.notion_fmt_applied = True
            st.rerun()

        # Show applied selections summary
        applied = st.session_state.get("notion_fmt_selections", {})
        all_applied = [item for choices in applied.values() for item in choices]
        if all_applied:
            ticks = "  ".join(f"✅ {s}" for s in all_applied)
            st.markdown(
                f"<div style='background:rgba(0,200,100,0.08);border:1px solid rgba(0,200,100,0.3);"
                f"border-radius:8px;padding:8px 14px;margin:4px 0;font-size:13px;color:#6ee7b7'>"
                f"<b>Applied:</b> {ticks}</div>", unsafe_allow_html=True)

        # ── Media inputs — dynamic "Add More" per type ─────────────────────────
        media_items = st.session_state.notion_media_items
        media_choices = applied.get("Media & Files", [])
        adv_choices   = applied.get("Advanced & Interactive", [])
        all_needing   = [m for m in media_choices if m in MEDIA_NEEDS_INPUT] + \
                        [m for m in adv_choices if m == "Button"]

        if all_needing:
            st.markdown("---")
            st.markdown("**📎 Media & Embed Sources**")

            for mtype in all_needing:
                st.markdown(f"**{mtype}**")
                ph = MEDIA_PLACEHOLDERS.get(mtype, "https://...")
                url_only = mtype in URL_ONLY
                is_btn   = mtype == "Button"

                # Dynamic list of URL fields for this type
                count_key = f"media_count_{mtype}_{version}"
                if count_key not in st.session_state:
                    st.session_state[count_key] = 1
                field_count = st.session_state[count_key]

                for fi in range(field_count):
                    fkey = f"media_url_{mtype}_{fi}_{version}"
                    if is_btn:
                        bc1, bc2 = st.columns(2)
                        with bc1:
                            st.text_input(f"Button Label #{fi+1}", placeholder="e.g. Open Link",
                                          key=f"btn_label_{mtype}_{fi}_{version}")
                        with bc2:
                            st.text_input(f"Button URL #{fi+1}", placeholder=ph, key=fkey)
                    elif url_only:
                        st.text_input(f"URL #{fi+1}", placeholder=ph, key=fkey,
                                      label_visibility="collapsed")
                    else:
                        mc1, mc2 = st.columns(2)
                        with mc1:
                            st.text_input(f"URL #{fi+1}", placeholder=ph, key=fkey)
                        with mc2:
                            st.file_uploader(f"Upload #{fi+1}",
                                             key=f"media_upload_{mtype}_{fi}_{version}",
                                             label_visibility="visible")

                # Add More button
                ac1, ac2 = st.columns([1, 4])
                with ac1:
                    if st.button(f"➕ Add More {mtype}", key=f"addmore_{mtype}_{version}"):
                        st.session_state[count_key] += 1
                        st.rerun()

                st.caption(f"💡 Click **'Add {mtype} to Page'** after filling in the fields above.")

                # Commit button
                if st.button(f"✔ Add {mtype} to Page", key=f"commit_{mtype}_{version}"):
                    added = 0
                    for fi in range(field_count):
                        fkey = f"media_url_{mtype}_{fi}_{version}"
                        url_val = st.session_state.get(fkey, "").strip()
                        if is_btn:
                            lbl_val = st.session_state.get(f"btn_label_{mtype}_{fi}_{version}", "").strip()
                            if lbl_val and url_val:
                                media_items.append({"type":"Button","source":"url",
                                                    "value":f"{lbl_val}|{url_val}"})
                                added += 1
                        elif url_val:
                            media_items.append({"type":mtype,"source":"url","value":url_val})
                            added += 1
                        else:
                            up_key = f"media_upload_{mtype}_{fi}_{version}"
                            uf = st.session_state.get(up_key)
                            if uf is not None:
                                media_items.append({"type":mtype,"source":"upload",
                                                    "value":uf.name,"data":uf.read()})
                                added += 1
                    if added:
                        st.session_state.notion_media_items = media_items
                        st.success(f"✅ {added} {mtype} item(s) added.")
                        st.rerun()
                    else:
                        st.warning("Please fill in at least one URL or upload a file.")

        # Queued media list
        if media_items:
            st.markdown("**Queued media:**")
            for mi, item in enumerate(media_items):
                mc1, mc2 = st.columns([5, 1])
                mc1.caption(f"✅ {item['type']} — {item['source'].upper()}: {item['value']}")
                if mc2.button("✕", key=f"rm_media_{mi}_{version}"):
                    media_items.pop(mi)
                    st.session_state.notion_media_items = media_items
                    st.rerun()

        # ── Prepare Preview ────────────────────────────────────────────────────
        if st.button("🔍 Prepare Preview", key="run_notion_agent") and (page_title or direct_content or ai_prompt):
            st.session_state.notion_workflow_state = "preparing"
            st.session_state.notion_preview_title  = page_title or "Untitled Page"

            # Build formatting hints from applied selections
            active_hints = []
            for cat, choices in applied.items():
                if cat == "Media & Files":
                    continue
                for choice in choices:
                    hint = BLOCK_HINT_MAP.get(choice)
                    if hint:
                        active_hints.append(f"- {hint}")

            fmt_instruction = ""
            if active_hints:
                fmt_instruction = (
                    "\n\nUSER-SELECTED FORMATTING PREFERENCES (apply these):\n"
                    + "\n".join(active_hints))

            # Build media blocks — placed intelligently
            media_block_str = _build_media_blocks(media_items, position="end")

            with st.status("🧠 Preparing content preview…", expanded=True) as status:
                model = st.session_state.get("selected_model", "llama3:latest")
                parts = []
                if direct_content:
                    st.write("✨ Refining direct content…")
                    parts.append(refine_direct_content(direct_content, model=model))
                if ai_prompt:
                    st.write("✍️ Generating AI content…")
                    parts.append(generate_page_content(
                        st.session_state.notion_preview_title,
                        ai_prompt + fmt_instruction, model=model))
                if media_block_str:
                    parts.append(media_block_str)
                st.session_state.notion_preview_content = "\n\n".join(parts)
                status.update(label="✅ Preview Ready", state="complete")
                st.session_state.notion_workflow_state = "preview"

        # ── Preview ────────────────────────────────────────────────────────────
        if st.session_state.notion_workflow_state == "preview":
            st.divider()
            st.subheader("👀 Content Preview")

            if st.session_state.notion_is_editing:
                st.session_state.notion_preview_title = st.text_input(
                    "Edit Title", value=st.session_state.notion_preview_title, key="edit_title_f")
                st.session_state.notion_preview_content = st.text_area(
                    "Edit Content", value=st.session_state.notion_preview_content,
                    height=320, key="edit_content_f")
            else:
                st.markdown(f"### {st.session_state.notion_preview_title}")
                _render_rich_preview(st.session_state.notion_preview_content)

            # Satisfaction message
            st.markdown(
                "<div style='background:rgba(108,99,255,0.06);border:1px solid rgba(108,99,255,0.2);"
                "border-radius:8px;padding:10px 16px;margin:10px 0;font-size:13px;color:#c4b5fd'>"
                "Are you satisfied with this content? If not, <b>Edit</b> or <b>Recreate</b> it."
                "</div>", unsafe_allow_html=True)

            st.divider()
            
            # Show current selection status
            if st.session_state.notion_parent_mode == "new_page":
                st.info("📄 This page will be created as a **new, standalone page** at the workspace root level.")
            elif st.session_state.notion_parent_mode == "existing_page" and st.session_state.notion_selected_parent_name:
                st.success(f"📁 This page will be created inside: **{st.session_state.notion_selected_parent_name}**")
            
            st.divider()

            pc1, pc2, pc3, pc4 = st.columns(4)
            with pc1:
                button_label = "📤 Send to Notion"
                if st.session_state.notion_parent_mode == "existing_page":
                    button_label = f"📤 Create in '{st.session_state.notion_selected_parent_name}'"
                
                if st.button(button_label, key="execute_notion_final", use_container_width=True):
                    st.session_state.notion_workflow_state = "executing"
                    st.rerun()
            with pc2:
                elbl = "💾 Save Edits" if st.session_state.notion_is_editing else "📝 Edit"
                if st.button(elbl, key="toggle_edit", use_container_width=True):
                    st.session_state.notion_is_editing = not st.session_state.notion_is_editing
                    st.rerun()
            with pc3:
                if st.button("🔄 Recreate", key="recreate_preview", use_container_width=True):
                    st.session_state.notion_workflow_state = "idle"
                    st.session_state.notion_preview_content = ""
                    st.session_state.notion_is_editing = False
                    st.rerun()
            with pc4:
                if st.button("❌ Cancel", key="cancel_preview", use_container_width=True):
                    st.session_state.notion_confirm_cancel = True
                    st.rerun()

            # Cancel confirmation — true full-screen modal via JS injection
            if st.session_state.get("notion_confirm_cancel"):
                import streamlit.components.v1 as _components
                _components.html("""
<script>
(function() {
  var doc = window.parent.document;
  if (doc.getElementById('notion-cancel-overlay')) return;

  // Overlay
  var overlay = doc.createElement('div');
  overlay.id = 'notion-cancel-overlay';
  overlay.style.cssText = [
    'position:fixed','top:0','left:0','width:100%','height:100%',
    'background:rgba(0,0,0,0.65)','z-index:999999',
    'display:flex','align-items:center','justify-content:center',
    'backdrop-filter:blur(3px)','-webkit-backdrop-filter:blur(3px)'
  ].join(';');

  // Card
  var card = doc.createElement('div');
  card.style.cssText = [
    'background:#1a1a2e','border:1px solid rgba(220,60,60,0.45)',
    'border-radius:16px','padding:36px 40px','text-align:center',
    'min-width:340px','max-width:420px','box-shadow:0 20px 60px rgba(0,0,0,0.5)',
    'font-family:Inter,sans-serif'
  ].join(';');

  card.innerHTML = `
    <div style="font-size:40px;margin-bottom:12px">⚠️</div>
    <h2 style="color:#f0f0f0;margin:0 0 8px;font-size:20px;font-weight:700">Cancel this page?</h2>
    <p style="color:#999;font-size:14px;margin:0 0 28px;line-height:1.5">
      All unsaved content will be permanently lost.<br>This action cannot be undone.
    </p>
    <div style="display:flex;gap:12px;justify-content:center">
      <button id="notion-cancel-yes" style="
        background:linear-gradient(135deg,#dc2626,#b91c1c);color:white;
        border:none;border-radius:8px;padding:10px 28px;font-size:14px;
        font-weight:600;cursor:pointer;transition:opacity 0.15s">
        Yes, Cancel
      </button>
      <button id="notion-cancel-keep" style="
        background:linear-gradient(135deg,#6c63ff,#8b5cf6);color:white;
        border:none;border-radius:8px;padding:10px 28px;font-size:14px;
        font-weight:600;cursor:pointer;transition:opacity 0.15s">
        Keep Editing
      </button>
    </div>
  `;

  overlay.appendChild(card);
  doc.body.appendChild(overlay);

  // Button actions — click the hidden Streamlit buttons
  doc.getElementById('notion-cancel-yes').onclick = function() {
    overlay.remove();
    var btns = doc.querySelectorAll('button');
    for (var b of btns) {
      if (b.innerText.trim() === '✅ Yes, Cancel') { b.click(); break; }
    }
  };
  doc.getElementById('notion-cancel-keep').onclick = function() {
    overlay.remove();
    var btns = doc.querySelectorAll('button');
    for (var b of btns) {
      if (b.innerText.trim() === '🔙 No, Keep') { b.click(); break; }
    }
  };
})();
</script>
""", height=0, width=0)

                # Hidden Streamlit buttons that the JS clicks
                hc1, hc2 = st.columns(2)
                with hc1:
                    if st.button("✅ Yes, Cancel", key="confirm_yes"):
                        _reset_form()
                        st.rerun()
                with hc2:
                    if st.button("🔙 No, Keep", key="confirm_no"):
                        st.session_state.notion_confirm_cancel = False
                        st.rerun()

        # ── Execution ──────────────────────────────────────────────────────────
        if st.session_state.notion_workflow_state == "executing":
            title   = st.session_state.notion_preview_title
            content = st.session_state.notion_preview_content
            parent_id = None
            parent_label = "Workspace Root"
            
            if st.session_state.notion_parent_mode == "existing_page":
                parent_id = st.session_state.notion_selected_parent_id
                parent_label = st.session_state.notion_selected_parent_name
            
            with st.spinner(f"🚀 Creating Notion page: {title}… (in {parent_label})"):
                result = create_notion_page(title, content=content, parent_id=parent_id)
            if result["success"]:
                pid = result["data"]["id"].replace("-","")
                rec = {
                    "title":       title,
                    "url":         f"https://www.notion.so/{pid}",
                    "content":     content,
                    "parent_name": result.get("parent_name","Workspace"),
                    "created_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "data":        result["data"],
                }
                st.session_state.notion_page_history.append(rec)
                st.session_state.last_notion_result    = rec
                st.session_state.notion_media_items    = []
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
                st.markdown(
                    "<div style='background:rgba(108,99,255,0.06);border:1px solid rgba(108,99,255,0.2);"
                    "border-radius:10px;padding:14px 18px;margin:14px 0'>"
                    "<b>Are you satisfied with this content?</b><br>"
                    "<span style='color:#ccc;font-size:13px'>If not, edit it or recreate it.</span>"
                    "</div>", unsafe_allow_html=True)
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("🔄 Recreate Content", key="recreate_done", use_container_width=True):
                    st.session_state.notion_workflow_state = "idle"
                    st.session_state.notion_preview_content = ""
                    st.rerun()
            with cc2:
                if st.button("↩️ Create Another Page", key="new_page", use_container_width=True):
                    _reset_form()
                    st.rerun()

        _render_history()
