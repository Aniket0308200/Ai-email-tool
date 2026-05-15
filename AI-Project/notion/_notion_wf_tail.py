def render_notion_workflow():
    st.markdown('<div class="page-title">≡ƒô¥ Notion AI Agent</div>', unsafe_allow_html=True)

    # OAuth callback
    if "code" in st.query_params:
        code = st.query_params["code"]
        with st.spinner("≡ƒöù Completing Notion connection..."):
            if exchange_code_for_token(code):
                st.success("Γ£à Notion connected successfully!")
                st.query_params.clear()
                st.rerun()
            else:
                st.error("Γ¥î Failed to connect Notion.")

    tab_agent, tab_listing, tab_settings = st.tabs(["≡ƒñû Create Page", "≡ƒôï Listing", "ΓÜÖ∩╕Å Settings"])

    # ΓöÇΓöÇ Settings ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
    with tab_settings:
        with st.expander("≡ƒôû Setup Guide", expanded=False):
            st.markdown("""
            Go to **[Notion Developers](https://www.notion.so/my-integrations)** ΓåÆ Developer Portal.
            1. New Connection ΓåÆ OAuth ΓåÆ set Redirect URL to `http://localhost:8501`.
            2. Copy **Client ID** and **Client Secret**.
            """)
        st.subheader("≡ƒöÉ Notion API Configuration")
        cfg = _load_config()
        cid  = st.text_input("Client ID",     value=cfg.get("client_id",""))
        csec = st.text_input("Client Secret", value=cfg.get("client_secret",""), type="password")
        ruri = st.text_input("Redirect URL",  value=cfg.get("redirect_uri","http://localhost:8501"))
        if st.button("≡ƒÆ╛ Save Configuration", key="save_notion_config"):
            _save_config({"client_id":cid,"client_secret":csec,"redirect_uri":ruri})
            st.success("Γ£à Saved!")
            st.rerun()
        st.divider()
        st.subheader("≡ƒæñ Connection Status")
        if is_notion_authenticated():
            st.success(f"Γ£à Connected as: {get_authenticated_user()}")
            if st.button("≡ƒöô Disconnect", key="disconnect_notion"):
                clear_authentication(); st.rerun()
        else:
            st.info("Not connected.")
            auth_url = get_notion_auth_url()
            if auth_url:
                st.link_button("≡ƒöô Connect Notion", auth_url, use_container_width=True)
            else:
                st.warning("Configure Client ID and Redirect URL first.")

    # ΓöÇΓöÇ Listing tab ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
    with tab_listing:
        if not is_notion_authenticated():
            st.warning("ΓÜá∩╕Å Connect your Notion account in Settings first.")
        else:
            render_notion_listing()

    # ΓöÇΓöÇ Agent tab ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
    with tab_agent:
        if not is_notion_authenticated():
            st.warning("ΓÜá∩╕Å Connect your Notion account in Settings first.")
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
                f"ΓÜá∩╕Å Please select a page type: New or Existing, then fill the input box.</div>",
                unsafe_allow_html=True)
        elif not selection_mode:
            # Blue status line after selection is fully confirmed or New Page is selected
            text = "Create a New Page" if parent_mode == "new_page" else f"Create a new page in the {st.session_state.notion_selected_parent_name} page"
            
            sc1, sc2 = st.columns([5, 1])
            with sc1:
                st.markdown(
                    f"<div style='background:rgba(108,99,255,0.12);border:1px solid rgba(108,99,255,0.3);"
                    f"border-radius:10px;padding:12px 18px;color:#a78bfa;font-weight:600;font-size:14px'>"
                    f"Γ£à {text}</div>", unsafe_allow_html=True)
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
                    f"≡ƒöì Selecting Existing Page...</div>", unsafe_allow_html=True)
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
            with st.spinner("≡ƒôé Fetching your Notion pagesΓÇª"):
                result = get_existing_pages()
            
            if not result.get("success"):
                st.error(f"Γ¥î Could not fetch pages: {result.get('error')}")
                if st.button("Γå⌐∩╕Å Back to Options", key="back_to_options"):
                    st.session_state.notion_parent_selection_mode = False
                    st.session_state.notion_parent_selected = False
                    st.rerun()
            else:
                pages = result.get("pages", [])
                if not pages:
                    st.info("≡ƒô¡ No existing pages found in your Notion workspace.")
                    if st.button("Γå⌐∩╕Å Back to Options", key="back_no_pages"):
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
                        
                        # Page selection area and the line showing "Γ£à Selected: ..." with OK button
                        c1, c2 = st.columns([9, 1.2])
                        with c1:
                            st.markdown(
                                f"<div style='background:rgba(106,170,100,0.12);border:1px solid rgba(106,170,100,0.4);"
                                f"border-radius:8px;padding:0 16px;color:#6ee7b7;font-weight:500;height:48px;display:flex;align-items:center'>"
                                f"Γ£à <b>Selected:</b> {selected_title}</div>", unsafe_allow_html=True)
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
    <div style="font-size:40px;margin-bottom:12px">Γ¥ô</div>
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


        page_title = st.text_input("≡ƒôä Page Title", placeholder="e.g. Project Research",
                                   key=f"notion_title_{version}", disabled=not parent_selected,
                                   help="Please select New Page or Existing Page first before filling the inputs." if not parent_selected else None)
        dtv = st.session_state.get(f"notion_direct_{version}", "").strip()
        aiv = st.session_state.get(f"notion_ai_{version}", "").strip()
        c1, c2 = st.columns(2)
        with c1:
            direct_content = st.text_area("Γ£ì∩╕Å Direct Content",
                placeholder="Enter text to keep as-isΓÇª",
                key=f"notion_direct_{version}", height=130, disabled=(aiv != "" or not parent_selected),
                help="Please select New Page or Existing Page first before filling the inputs." if not parent_selected else None)
        with c2:
            ai_prompt = st.text_area("≡ƒñû AI Generation Prompt",
                placeholder="Describe what you want the AI to generateΓÇª",
                key=f"notion_ai_{version}", height=130, disabled=(dtv != "" or not parent_selected),
                help="Please select New Page or Existing Page first before filling the inputs." if not parent_selected else None)

        # ΓöÇΓöÇ Formatting dropdowns ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
        st.markdown("**≡ƒÄ¿ Formatting & Block Preferences**")
        st.caption("Open each dropdown, select options, then click **Apply Preferences** when done.")

        ms_cols = st.columns(5)
        # Use a staging dict ΓÇö only committed when Apply is clicked
        staging_key = f"notion_fmt_staging_{version}"
        if staging_key not in st.session_state:
            st.session_state[staging_key] = {k: [] for k in FORMATTING_OPTIONS}
        staging = st.session_state[staging_key]

        for col, key in zip(ms_cols, list(FORMATTING_OPTIONS.keys())):
            with col:
                opts = FORMATTING_OPTIONS[key]
                cur  = staging.get(key, [])
                cnt  = len(cur)
                lbl  = f"{key} ({cnt}Γ£ô)" if cnt else key
                with st.popover(lbl, use_container_width=True):
                    st.markdown(f"**{key}**")
                    new_cur = []
                    for opt in opts:
                        is_sel = opt in cur
                        checked = st.checkbox(opt, value=is_sel,
                                              key=f"cb_{key}_{opt}_{version}")
                        if checked:
                            new_cur.append(opt)
                    # Only update staging ΓÇö no st.rerun() here to avoid lag
                    staging[key] = new_cur
                    st.session_state[staging_key] = staging

        st.caption("Click any option to select Γ£ô. Click again to deselect.")

        # Apply button ΓÇö commits staging to applied selections
        if st.button("Γ£à Apply Preferences", key=f"apply_fmt_{version}"):
            st.session_state.notion_fmt_selections = {k: list(v) for k, v in staging.items()}
            st.session_state.notion_fmt_applied = True
            st.rerun()

        # Show applied selections summary
        applied = st.session_state.get("notion_fmt_selections", {})
        all_applied = [item for choices in applied.values() for item in choices]
        if all_applied:
            ticks = "  ".join(f"Γ£à {s}" for s in all_applied)
            st.markdown(
                f"<div style='background:rgba(0,200,100,0.08);border:1px solid rgba(0,200,100,0.3);"
                f"border-radius:8px;padding:8px 14px;margin:4px 0;font-size:13px;color:#6ee7b7'>"
                f"<b>Applied:</b> {ticks}</div>", unsafe_allow_html=True)

        # ΓöÇΓöÇ Media inputs ΓÇö dynamic "Add More" per type ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
        media_items = st.session_state.notion_media_items
        media_choices = applied.get("Media & Files", [])
        adv_choices   = applied.get("Advanced & Interactive", [])
        all_needing   = [m for m in media_choices if m in MEDIA_NEEDS_INPUT] + \
                        [m for m in adv_choices if m == "Button"]

        if all_needing:
            st.markdown("---")
            st.markdown("**≡ƒôÄ Media & Embed Sources**")

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
                    if st.button(f"Γ₧ò Add More {mtype}", key=f"addmore_{mtype}_{version}"):
                        st.session_state[count_key] += 1
                        st.rerun()

                st.caption(f"≡ƒÆí Click **'Add {mtype} to Page'** after filling in the fields above.")

                # Commit button
                if st.button(f"Γ£ö Add {mtype} to Page", key=f"commit_{mtype}_{version}"):
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
                        st.success(f"Γ£à {added} {mtype} item(s) added.")
                        st.rerun()
                    else:
                        st.warning("Please fill in at least one URL or upload a file.")

        # Queued media list
        if media_items:
            st.markdown("**Queued media:**")
            for mi, item in enumerate(media_items):
                mc1, mc2 = st.columns([5, 1])
                mc1.caption(f"Γ£à {item['type']} ΓÇö {item['source'].upper()}: {item['value']}")
                if mc2.button("Γ£ò", key=f"rm_media_{mi}_{version}"):
                    media_items.pop(mi)
                    st.session_state.notion_media_items = media_items
                    st.rerun()

        # ΓöÇΓöÇ Prepare Preview ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
        if st.button("≡ƒöì Prepare Preview", key="run_notion_agent") and (page_title or direct_content or ai_prompt):
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

            # Build media blocks ΓÇö placed intelligently
            media_block_str = _build_media_blocks(media_items, position="end")

            with st.status("≡ƒºá Preparing content previewΓÇª", expanded=True) as status:
                model = st.session_state.get("selected_model", "llama3:latest")
                parts = []
                if direct_content:
                    st.write("Γ£¿ Refining direct contentΓÇª")
                    parts.append(refine_direct_content(direct_content, model=model))
                if ai_prompt:
                    st.write("Γ£ì∩╕Å Generating AI contentΓÇª")
                    parts.append(generate_page_content(
                        st.session_state.notion_preview_title,
                        ai_prompt + fmt_instruction, model=model))
                if media_block_str:
                    parts.append(media_block_str)
                st.session_state.notion_preview_content = "\n\n".join(parts)
                status.update(label="Γ£à Preview Ready", state="complete")
                st.session_state.notion_workflow_state = "preview"

        # ΓöÇΓöÇ Preview ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
        if st.session_state.notion_workflow_state == "preview":
            st.divider()
            st.subheader("≡ƒæÇ Content Preview")

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
                st.info("≡ƒôä This page will be created as a **new, standalone page** at the workspace root level.")
            elif st.session_state.notion_parent_mode == "existing_page" and st.session_state.notion_selected_parent_name:
                st.success(f"≡ƒôü This page will be created inside: **{st.session_state.notion_selected_parent_name}**")
            
            st.divider()

            pc1, pc2, pc3, pc4 = st.columns(4)
            with pc1:
                button_label = "≡ƒôñ Send to Notion"
                if st.session_state.notion_parent_mode == "existing_page":
                    button_label = f"≡ƒôñ Create in '{st.session_state.notion_selected_parent_name}'"
                
                if st.button(button_label, key="execute_notion_final", use_container_width=True):
                    st.session_state.notion_workflow_state = "executing"
                    st.rerun()
            with pc2:
                elbl = "≡ƒÆ╛ Save Edits" if st.session_state.notion_is_editing else "≡ƒô¥ Edit"
                if st.button(elbl, key="toggle_edit", use_container_width=True):
                    st.session_state.notion_is_editing = not st.session_state.notion_is_editing
                    st.rerun()
            with pc3:
                if st.button("≡ƒöä Recreate", key="recreate_preview", use_container_width=True):
                    st.session_state.notion_workflow_state = "idle"
                    st.session_state.notion_preview_content = ""
                    st.session_state.notion_is_editing = False
                    st.rerun()
            with pc4:
                if st.button("Γ¥î Cancel", key="cancel_preview", use_container_width=True):
                    st.session_state.notion_confirm_cancel = True
                    st.rerun()

            # Cancel confirmation ΓÇö true full-screen modal via JS injection
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
    <div style="font-size:40px;margin-bottom:12px">ΓÜá∩╕Å</div>
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

  // Button actions ΓÇö click the hidden Streamlit buttons
  doc.getElementById('notion-cancel-yes').onclick = function() {
    overlay.remove();
    var btns = doc.querySelectorAll('button');
    for (var b of btns) {
      if (b.innerText.trim() === 'Γ£à Yes, Cancel') { b.click(); break; }
    }
  };
  doc.getElementById('notion-cancel-keep').onclick = function() {
    overlay.remove();
    var btns = doc.querySelectorAll('button');
    for (var b of btns) {
      if (b.innerText.trim() === '≡ƒöÖ No, Keep') { b.click(); break; }
    }
  };
})();
</script>
""", height=0, width=0)

                # Hidden Streamlit buttons that the JS clicks
                hc1, hc2 = st.columns(2)
                with hc1:
                    if st.button("Γ£à Yes, Cancel", key="confirm_yes"):
                        _reset_form()
                        st.rerun()
                with hc2:
                    if st.button("≡ƒöÖ No, Keep", key="confirm_no"):
                        st.session_state.notion_confirm_cancel = False
                        st.rerun()

        # ΓöÇΓöÇ Execution ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
        if st.session_state.notion_workflow_state == "executing":
            title   = st.session_state.notion_preview_title
            content = st.session_state.notion_preview_content
            parent_id = None
            parent_label = "Workspace Root"
            
            if st.session_state.notion_parent_mode == "existing_page":
                parent_id = st.session_state.notion_selected_parent_id
                parent_label = st.session_state.notion_selected_parent_name
            
            with st.spinner(f"≡ƒÜÇ Creating Notion page: {title}ΓÇª (in {parent_label})"):
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
                st.error(f"Γ¥î Execution failed: {result['error']}")
                st.session_state.notion_workflow_state = "preview"

        # ΓöÇΓöÇ Completed ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
        if st.session_state.notion_workflow_state == "completed":
            res = st.session_state.last_notion_result
            if res:
                st.divider()
                st.success("≡ƒÄë **Page Created Successfully!**")
                _render_page_card(res, idx=999, show_raw=True)
                st.markdown(
                    "<div style='background:rgba(108,99,255,0.06);border:1px solid rgba(108,99,255,0.2);"
                    "border-radius:10px;padding:14px 18px;margin:14px 0'>"
                    "<b>Are you satisfied with this content?</b><br>"
                    "<span style='color:#ccc;font-size:13px'>If not, edit it or recreate it.</span>"
                    "</div>", unsafe_allow_html=True)
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("≡ƒöä Recreate Content", key="recreate_done", use_container_width=True):
                    st.session_state.notion_workflow_state = "idle"
                    st.session_state.notion_preview_content = ""
                    st.rerun()
            with cc2:
                if st.button("Γå⌐∩╕Å Create Another Page", key="new_page", use_container_width=True):
                    _reset_form()
                    st.rerun()

        _render_history()
