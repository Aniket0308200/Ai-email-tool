import os
import json
import logging
import requests
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# File paths
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "notion_credentials.json")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "notion_config.json")

def _load_config() -> Dict[str, str]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading Notion config: {e}")
    return {"client_id": "", "client_secret": "", "redirect_uri": ""}

def _save_config(config: Dict[str, str]):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def _load_credentials() -> Dict[str, Any]:
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading Notion credentials: {e}")
    return {}

def _save_credentials(creds: Dict[str, Any]):
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(creds, f, indent=4)

def is_notion_authenticated() -> bool:
    creds = _load_credentials()
    return "access_token" in creds

def get_notion_auth_url() -> str:
    config = _load_config()
    client_id = config.get("client_id")
    redirect_uri = config.get("redirect_uri")
    
    if not client_id or not redirect_uri:
        return ""
    
    return f"https://api.notion.com/v1/oauth/authorize?owner=user&client_id={client_id}&redirect_uri={redirect_uri}&response_type=code"

def exchange_code_for_token(code: str) -> bool:
    config = _load_config()
    client_id = config.get("client_id")
    client_secret = config.get("client_secret")
    redirect_uri = config.get("redirect_uri")
    
    if not client_id or not client_secret or not redirect_uri:
        return False
    
    import base64
    auth_str = f"{client_id}:{client_secret}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_auth}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    }
    
    try:
        response = requests.post("https://api.notion.com/v1/oauth/token", headers=headers, json=data)
        if response.status_code == 200:
            _save_credentials(response.json())
            return True
        else:
            logger.error(f"Notion token exchange failed: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error exchanging Notion code: {e}")
        return False

def get_notion_headers() -> Dict[str, str]:
    creds = _load_credentials()
    token = creds.get("access_token")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

def create_notion_page(title: str, content: Optional[str] = None, parent_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new standalone Notion page.

    - By default (no parent_id) creates at workspace root level.
    - If parent_id is explicitly provided, creates as a child of that page.
    """
    if not is_notion_authenticated():
        return {"success": False, "error": "Notion not authenticated"}

    headers = get_notion_headers()

    # ── Determine parent ──────────────────────────────────────────────────────
    if parent_id:
        # Explicit parent requested by user
        parent = {"page_id": parent_id}
        parent_name = "Specified Parent Page"
    else:
        # Default: create as a standalone workspace-level page
        parent = {"workspace": True}
        parent_name = "Workspace (Top Level)"

    # ── Build page payload ────────────────────────────────────────────────────
    data = {
        "parent": parent,
        "properties": {
            "title": [{"text": {"content": title}}]
        },
    }

    if content:
        data["children"] = parse_markdown_to_notion_blocks(content)

    try:
        response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data)
        if response.status_code == 200:
            return {
                "success": True,
                "data": response.json(),
                "parent_name": parent_name,
                "parent_id": parent_id or "workspace",
            }
        else:
            error_msg = response.json().get("message", response.text)
            # Workspace-level creation may be restricted on some plans — fall back to first page
            if "parent" in error_msg.lower() or response.status_code == 400:
                return _create_page_with_fallback_parent(title, content, headers)
            return {"success": False, "error": error_msg}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _create_page_with_fallback_parent(title: str, content: Optional[str], headers: dict) -> Dict[str, Any]:
    """Fallback: find the first accessible page and use it as parent."""
    search_results = search_notion("")
    if not search_results.get("success") or not search_results.get("data"):
        return {
            "success": False,
            "error": (
                "Could not create a workspace-level page (your Notion plan may not support it). "
                "Please share at least one page with the integration so it can be used as a parent."
            ),
        }

    parent_id = None
    parent_name = "Notion Workspace"
    for item in search_results["data"]:
        if item["object"] == "page":
            parent_id = item["id"]
            title_list = (
                item.get("properties", {}).get("title", {}).get("title", [])
                or item.get("properties", {}).get("Name", {}).get("title", [])
            )
            parent_name = (
                title_list[0].get("plain_text", "Untitled Page") if title_list else "First Accessible Page"
            )
            break

    if not parent_id:
        parent_id = search_results["data"][0]["id"]
        parent_name = "Notion Workspace Root"

    # Rebuild payload with page parent
    data: Dict[str, Any] = {
        "parent": {"page_id": parent_id},
        "properties": {"title": [{"text": {"content": title}}]},
    }
    if content:
        data["children"] = parse_markdown_to_notion_blocks(content)

    try:
        resp = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data)
        if resp.status_code == 200:
            return {
                "success": True,
                "data": resp.json(),
                "parent_name": parent_name,
                "parent_id": parent_id,
            }
        return {"success": False, "error": resp.json().get("message", resp.text)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def search_notion(query: str) -> Dict[str, Any]:
    if not is_notion_authenticated():
        return {"success": False, "error": "Notion not authenticated"}
    
    headers = get_notion_headers()
    data = {"query": query, "sort": {"direction": "descending", "timestamp": "last_edited_time"}}
    
    try:
        response = requests.post("https://api.notion.com/v1/search", headers=headers, json=data)
        if response.status_code == 200:
            return {"success": True, "data": response.json().get("results", [])}
        else:
            return {"success": False, "error": response.json().get("message", response.text)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_authenticated_user() -> str:
    creds = _load_credentials()
    return creds.get("owner", {}).get("user", {}).get("name", "Unknown User")

def clear_authentication() -> bool:
    if os.path.exists(CREDENTIALS_FILE):
        os.remove(CREDENTIALS_FILE)
    return True

def generate_page_content(topic: str, instructions: str, model: str = "llama3:latest") -> str:
    """
    Generate rich, professionally structured Notion page content.
    Uses llama3 (8B) for high-quality, detailed output.
    """
    import re
    from langchain_ollama import ChatOllama
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    llm = ChatOllama(
        model=model,
        base_url="http://localhost:11434",
        temperature=0.65,
        num_predict=2048,
    )

    # Auto-detect content type to adapt structure
    combined = f"{topic} {instructions}".lower()
    if any(w in combined for w in ["plan", "project", "task", "checklist", "todo", "roadmap", "sprint", "milestone"]):
        style_hint = "planning"
    elif any(w in combined for w in ["code", "api", "function", "script", "technical", "developer", "programming", "tutorial", "install", "setup"]):
        style_hint = "technical"
    elif any(w in combined for w in ["learn", "study", "course", "education", "explain", "concept", "guide", "how to", "what is", "overview"]):
        style_hint = "educational"
    elif any(w in combined for w in ["meeting", "notes", "minutes", "summary", "report", "document", "recap"]):
        style_hint = "documentation"
    elif any(w in combined for w in ["business", "strategy", "proposal", "pitch", "analysis", "market", "revenue", "growth"]):
        style_hint = "business"
    else:
        style_hint = "general"

    style_guide = {
        "planning":       "Use ## sections for phases, - [ ] checkboxes for tasks, numbered steps, >> callouts for risks, tables for timelines.",
        "technical":      "Use ## sections per concept/step, ```code blocks for code/commands, numbered steps, > warnings/tips, tables for parameters.",
        "educational":    "Use ## for topics, ### for subtopics, bullets for key facts, > for definitions, >> for highlights, a ## Summary at the end.",
        "documentation":  "Use ## sections, bullets for details, tables for structured data, >> callouts for action items.",
        "business":       "Use ## for Overview/Goals/Strategy/Next Steps, tables for metrics, >> for key insights, bullets for lists.",
        "general":        "Use ## for major sections, ### for subsections, bullets and numbered lists, >> callouts, --- dividers.",
    }[style_hint]

    system_msg = (
        "You are an expert content writer creating a professional Notion page. "
        "Write detailed, well-structured content using markdown formatting.\n\n"
        "FORMATTING RULES:\n"
        "- # Heading 1  |  ## Heading 2  |  ### Heading 3\n"
        "- - bullet  |  1. numbered  |  - [ ] checkbox  |  - [x] done\n"
        "- > quote  |  >> callout  |  --- divider\n"
        "- **bold**  |  *italic*  |  `code`\n"
        "- ```python\ncode\n``` for code blocks\n"
        "- | Col | Col |\n|---|---|\n| val | val | for tables\n\n"
        f"STRUCTURE GUIDE ({style_hint.upper()}): {style_guide}\n\n"
        "REQUIREMENTS:\n"
        "1. Write at least 400 words of real, meaningful content\n"
        "2. Use at least 3-4 ## sections with actual content under each\n"
        "3. Never write placeholder text like 'Add content here'\n"
        "4. Start directly with content — no 'Here is your page' preamble\n"
        "5. End with a ## Summary or ## Next Steps section"
    )

    human_msg = (
        f"Create a complete, detailed Notion page:\n\n"
        f"TOPIC: {topic}\n"
        f"INSTRUCTIONS: {instructions}\n\n"
        f"Write the full page content now:"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        ("human", human_msg),
    ])

    try:
        chain = prompt | llm | StrOutputParser()
        content = chain.invoke({})
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        # Strip preamble lines
        content_lines = content.splitlines()
        while content_lines and re.match(
            r"^(here|sure|of course|certainly|absolutely|great|okay|alright|i'll|i will)[,!. ]",
            content_lines[0], re.IGNORECASE
        ):
            content_lines.pop(0)
        return "\n".join(content_lines).strip()
    except Exception as e:
        logger.error(f"Error generating page content: {e}")
        return f"# {topic}\n\n{instructions}"


def refine_direct_content(content: str, model: str = "llama3:latest") -> str:
    """Refine user's direct input: fix spelling, punctuation, formatting."""
    import re
    from langchain_ollama import ChatOllama
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    llm = ChatOllama(
        model=model,
        base_url="http://localhost:11434",
        temperature=0.1,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a professional editor. "
         "Improve the following text by fixing spelling, punctuation, and alignment. "
         "Ensure paragraph formatting and line spacing are professional. "
         "DO NOT change the core meaning or add new information. "
         "If the user used bullet points or symbols, preserve or improve their consistency. "
         "Return ONLY the refined text without any preamble."),
        ("human", f"Text to refine:\n{content}"),
    ])

    try:
        chain = prompt | llm | StrOutputParser()
        refined = chain.invoke({})
        refined = re.sub(r"<think>.*?</think>", "", refined, flags=re.DOTALL).strip()
        return refined
    except Exception as e:
        logger.error(f"Error refining direct content: {e}")
        return content


def parse_markdown_to_notion_blocks(content: str) -> list:
    """Convert markdown text into Notion API block objects."""
    import re
    blocks = []
    lines = content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Code block
        if line.startswith("```"):
            lang = line[3:].strip() or "plain text"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append({
                "object": "block", "type": "code",
                "code": {
                    "language": lang,
                    "rich_text": [{"type": "text", "text": {"content": "\n".join(code_lines)}}],
                },
            })
            i += 1
            continue

        # Table — with cell-count normalization to prevent Notion API errors
        if line.startswith("|") and i + 1 < len(lines) and "|" in lines[i + 1]:
            raw_rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row_line = lines[i].strip()
                if not all(c in "-| " for c in row_line):  # skip separator rows
                    cells = [c.strip() for c in row_line.split("|")[1:-1]]
                    raw_rows.append(cells)
                i += 1

            if raw_rows:
                # Determine the canonical width from the header row (first row)
                table_width = len(raw_rows[0])
                normalized_rows = []
                for cells in raw_rows:
                    # Pad short rows with empty cells, trim long rows
                    if len(cells) < table_width:
                        cells = cells + [""] * (table_width - len(cells))
                    elif len(cells) > table_width:
                        cells = cells[:table_width]
                    normalized_rows.append({
                        "type": "table_row",
                        "table_row": {
                            "cells": [[{"type": "text", "text": {"content": c}}] for c in cells]
                        },
                    })
                blocks.append({
                    "object": "block", "type": "table",
                    "table": {
                        "table_width": table_width,
                        "has_column_header": True,
                        "children": normalized_rows,
                    },
                })
            continue

        # Image: ![alt](url)
        img_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line)
        if img_match:
            alt = img_match.group(1) or "Image"
            url = img_match.group(2)
            if url.startswith("http"):
                blocks.append({
                    "object": "block", "type": "image",
                    "image": {"type": "external", "external": {"url": url}}
                })
            continue

        # Video: {video:url}
        vid_match = re.match(r"\{video:(.+)\}", line)
        if vid_match:
            url = vid_match.group(1).strip()
            if "youtube.com" in url or "youtu.be" in url:
                blocks.append({
                    "object": "block", "type": "video",
                    "video": {"type": "external", "external": {"url": url}}
                })
            else:
                blocks.append({
                    "object": "block", "type": "video",
                    "video": {"type": "external", "external": {"url": url}}
                })
            continue

        # Embed: {embed:url}
        emb_match = re.match(r"\{embed:(.+)\}", line)
        if emb_match:
            url = emb_match.group(1).strip()
            blocks.append({
                "object": "block", "type": "embed",
                "embed": {"url": url}
            })
            continue

        # Button: {button:Label|URL}
        btn_match = re.match(r"\{button:(.+)\|(.+)\}", line)
        if btn_match:
            label = btn_match.group(1).strip()
            url = btn_match.group(2).strip()
            # Notion API doesn't have a direct 'button' block that redirects on click yet (as of 2024/2025)
            # but it has 'callout' with a link, or we can use a 'paragraph' with a link styled like a button.
            # However, for a 'real' feel, we use a callout with a link or a bookmark.
            # Recent Notion API additions might include buttons, but for safety and 'click to open',
            # we'll use a callout with a bold link.
            blocks.append({
                "object": "block", "type": "callout",
                "callout": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "🔘 "}},
                        {"type": "text", "text": {"content": label, "link": {"url": url}}, "annotations": {"bold": True}}
                    ],
                    "icon": {"emoji": "🔗"}
                }
            })
            continue

        # Web Bookmark: > 🔖 Bookmark: [title](url)
        bookmark_match = re.search(r"🔖 Bookmark: \[([^\]]+)\]\(([^)]+)\)", line)
        if bookmark_match:
            url = bookmark_match.group(2)
            blocks.append({
                "object": "block", "type": "bookmark",
                "bookmark": {"url": url}
            })
            continue

        # Headings
        if line.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1",
                           "heading_1": {"rich_text": parse_rich_text(line[2:])}})
        elif line.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2",
                           "heading_2": {"rich_text": parse_rich_text(line[3:])}})
        elif line.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3",
                           "heading_3": {"rich_text": parse_rich_text(line[4:])}})

        # Callout / Toggle / Quote
        elif line.startswith(">> "):
            blocks.append({"object": "block", "type": "callout",
                           "callout": {"rich_text": parse_rich_text(line[3:]),
                                       "icon": {"emoji": "💡"}}})
        elif line.startswith(">? "):
            blocks.append({"object": "block", "type": "toggle",
                           "toggle": {"rich_text": parse_rich_text(line[3:])}})
        elif line.startswith("> "):
            blocks.append({"object": "block", "type": "quote",
                           "quote": {"rich_text": parse_rich_text(line[2:])}})

        # To-do / Bullet / Numbered
        elif line.startswith("- [ ] ") or line.startswith("- [x] "):
            checked = line.startswith("- [x] ")
            blocks.append({"object": "block", "type": "to_do",
                           "to_do": {"rich_text": parse_rich_text(line[6:]), "checked": checked}})
        elif line.startswith("- ") or line.startswith("* "):
            blocks.append({"object": "block", "type": "bulleted_list_item",
                           "bulleted_list_item": {"rich_text": parse_rich_text(line[2:])}})
        elif re.match(r"^\d+\. ", line):
            start = line.find(". ") + 2
            blocks.append({"object": "block", "type": "numbered_list_item",
                           "numbered_list_item": {"rich_text": parse_rich_text(line[start:])}})

        # Divider
        elif line == "---":
            blocks.append({"object": "block", "type": "divider", "divider": {}})

        # Paragraph (default)
        else:
            blocks.append({"object": "block", "type": "paragraph",
                           "paragraph": {"rich_text": parse_rich_text(line)}})

        i += 1

    return blocks


def parse_rich_text(text: str) -> list:
    """Parse inline markdown into Notion rich_text objects."""
    import re

    annotations = {"bold": False, "italic": False, "strikethrough": False, "code": False}
    content = text

    if content.startswith("**") and content.endswith("**") and len(content) > 4:
        annotations["bold"] = True
        content = content[2:-2]
    elif content.startswith("*") and content.endswith("*") and len(content) > 2:
        annotations["italic"] = True
        content = content[1:-1]
    elif content.startswith("~~") and content.endswith("~~") and len(content) > 4:
        annotations["strikethrough"] = True
        content = content[2:-2]
    elif content.startswith("`") and content.endswith("`") and len(content) > 2:
        annotations["code"] = True
        content = content[1:-1]

    return [{"type": "text", "text": {"content": content}, "annotations": annotations}]


def get_existing_pages() -> Dict[str, Any]:
    """
    Fetch all accessible pages from Notion workspace.
    Returns a dictionary with success flag and list of pages.
    Each page has: id, title, and created_time.
    """
    if not is_notion_authenticated():
        return {"success": False, "error": "Notion not authenticated", "pages": []}
    
    headers = get_notion_headers()
    pages = []
    has_more = True
    next_cursor = None
    
    try:
        while has_more:
            data = {
                "filter": {"property": "object", "value": "page"},
                "sort": {"direction": "descending", "timestamp": "last_edited_time"}
            }
            if next_cursor:
                data["start_cursor"] = next_cursor
            
            response = requests.post(
                "https://api.notion.com/v1/search",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": response.json().get("message", response.text),
                    "pages": pages
                }
            
            result = response.json()
            results = result.get("results", [])
            
            for item in results:
                if item.get("object") == "page":
                    # Extract title
                    properties = item.get("properties", {})
                    title_data = properties.get("title", {}).get("title", []) or \
                                 properties.get("Name", {}).get("title", [])
                    title = title_data[0].get("plain_text", "Untitled") if title_data else "Untitled"
                    
                    created_by = item.get("created_by", {}).get("name", "Unknown")
                    if not created_by or created_by == "Unknown":
                        # If name is not directly available, it might be a bot or person with just ID
                        cb_type = item.get("created_by", {}).get("object")
                        if cb_type == "user":
                            created_by = "User"
                    
                    pages.append({
                        "id": item.get("id"),
                        "title": title,
                        "created_time": item.get("created_time", ""),
                        "last_edited_time": item.get("last_edited_time", ""),
                        "created_by": created_by,
                        "url": item.get("url", ""),
                        "archived": item.get("archived", False),
                        "icon": item.get("icon"),
                        "cover": item.get("cover"),
                    })
            
            has_more = result.get("has_more", False)
            next_cursor = result.get("next_cursor")
        
        return {"success": True, "pages": pages, "error": None}
    
    except Exception as e:
        return {"success": False, "error": str(e), "pages": pages}

def get_page_preview(page_id: str, max_lines: int = 2) -> str:
    """Fetch the first few blocks of a page to create a preview."""
    if not is_notion_authenticated():
        return ""
    
    headers = get_notion_headers()
    try:
        response = requests.get(
            f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=5",
            headers=headers
        )
        if response.status_code != 200:
            return ""
        
        blocks = response.json().get("results", [])
        preview_parts = []
        for block in blocks:
            btype = block.get("type")
            content_list = block.get(btype, {}).get("rich_text", [])
            if content_list:
                text = "".join([t.get("plain_text", "") for t in content_list])
                if text.strip():
                    preview_parts.append(text.strip())
            
            if len(preview_parts) >= max_lines:
                break
        
        preview = " ".join(preview_parts)
        if len(preview) > 150:
            preview = preview[:147] + "..."
        return preview
    except Exception:
        return ""

def get_notion_databases() -> Dict[str, Any]:
    """Fetch all accessible databases."""
    if not is_notion_authenticated():
        return {"success": False, "error": "Notion not authenticated", "databases": []}
    
    headers = get_notion_headers()
    databases = []
    try:
        data = {
            "filter": {"property": "object", "value": "database"},
            "sort": {"direction": "descending", "timestamp": "last_edited_time"}
        }
        response = requests.post("https://api.notion.com/v1/search", headers=headers, json=data)
        if response.status_code == 200:
            results = response.json().get("results", [])
            for item in results:
                title_data = item.get("title", [])
                title = title_data[0].get("plain_text", "Untitled Database") if title_data else "Untitled Database"
                databases.append({
                    "id": item.get("id"),
                    "title": title,
                    "created_time": item.get("created_time", ""),
                    "last_edited_time": item.get("last_edited_time", ""),
                    "url": item.get("url", ""),
                })
            return {"success": True, "databases": databases}
        else:
            return {"success": False, "error": response.json().get("message", response.text)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_database_items(database_id: str) -> Dict[str, Any]:
    """Query items inside a specific database."""
    if not is_notion_authenticated():
        return {"success": False, "error": "Notion not authenticated"}
    
    headers = get_notion_headers()
    try:
        response = requests.post(f"https://api.notion.com/v1/databases/{database_id}/query", headers=headers)
        if response.status_code == 200:
            results = response.json().get("results", [])
            items = []
            for item in results:
                props = item.get("properties", {})
                # Try to find a title property
                title = "Untitled Item"
                for p_name, p_val in props.items():
                    if p_val.get("type") == "title":
                        t_data = p_val.get("title", [])
                        title = t_data[0].get("plain_text", "Untitled") if t_data else "Untitled"
                        break
                
                items.append({
                    "id": item.get("id"),
                    "title": title,
                    "created_time": item.get("created_time", ""),
                    "url": item.get("url", ""),
                    "data": item
                })
            return {"success": True, "items": items}
        return {"success": False, "error": response.json().get("message", response.text)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def list_page_children(page_id: str) -> Dict[str, Any]:
    """List child pages of a specific page."""
    if not is_notion_authenticated():
        return {"success": False, "error": "Notion not authenticated"}
    
    headers = get_notion_headers()
    try:
        # We need to fetch blocks and check for 'child_page' type
        response = requests.get(f"https://api.notion.com/v1/blocks/{page_id}/children", headers=headers)
        if response.status_code == 200:
            blocks = response.json().get("results", [])
            children = []
            for block in blocks:
                if block.get("type") == "child_page":
                    children.append({
                        "id": block.get("id"),
                        "title": block.get("child_page", {}).get("title", "Untitled"),
                        "type": "page"
                    })
                elif block.get("type") == "child_database":
                    children.append({
                        "id": block.get("id"),
                        "title": block.get("child_database", {}).get("title", "Untitled"),
                        "type": "database"
                    })
            return {"success": True, "children": children}
        return {"success": False, "error": response.json().get("message", response.text)}
    except Exception as e:
        return {"success": False, "error": str(e)}
