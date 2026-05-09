"""
Gmail Handler - Email sending via Gmail API
Manages OAuth2 authentication and email delivery
"""
import os
import pickle
import json
import logging
import socket
import threading
import time
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.api_core.exceptions import GoogleAPIError
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://mail.google.com/",  # Required for permanent deletion
]

# Candidate ports to try for the OAuth callback server (in order)
OAUTH_PORT_CANDIDATES = [8080, 8081, 8082, 8090, 9090]

# Path to credentials files. Keep this relative to this module so the app works
# whether Streamlit is started from AI-Project or from the repo root.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_DIR = os.path.join(BASE_DIR, "email_credentials")
TOKEN_FILE = os.path.join(CREDENTIALS_DIR, "token.pickle")
CREDENTIALS_FILE = os.path.join(CREDENTIALS_DIR, "credentials.json")
FALLBACK_CREDENTIALS_FILES = [
    os.path.join(CREDENTIALS_DIR, "credentials.json.json"),
]


def ensure_credentials_dir():
    """Ensure the credentials directory exists."""
    os.makedirs(CREDENTIALS_DIR, exist_ok=True)


def get_credentials_file() -> str | None:
    """Return the first available OAuth client secrets file."""
    if os.path.exists(CREDENTIALS_FILE):
        return CREDENTIALS_FILE
    for path in FALLBACK_CREDENTIALS_FILES:
        if os.path.exists(path):
            logger.warning("Using %s. Rename it to credentials.json when convenient.", path)
            return path
    return None


def _load_client_config(credentials_file: str) -> dict:
    """Load and return the parsed client config JSON."""
    try:
        with open(credentials_file, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {credentials_file}: {exc}") from exc


def _is_port_free(port: int) -> bool:
    """Return True if the given localhost port is not in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def _force_free_port(port: int) -> bool:
    """
    Attempt to free a port by connecting and closing any lingering socket.
    Returns True if the port is free after the attempt.
    """
    if _is_port_free(port):
        return True
    # Give the OS a moment to release TIME_WAIT sockets
    time.sleep(1)
    return _is_port_free(port)


def _find_free_port(candidates: list[int]) -> int:
    """Return the first free port from the candidate list."""
    for port in candidates:
        if _is_port_free(port):
            return port
    raise OSError(
        f"All OAuth callback ports are in use: {candidates}. "
        "Close any browser windows from a previous authentication attempt, "
        "or restart the application."
    )


def _get_registered_localhost_uris(client_config: dict) -> list[str]:
    """Return all localhost redirect URIs registered in the client config."""
    section = client_config.get("web") or client_config.get("installed") or {}
    return [
        uri
        for uri in section.get("redirect_uris", [])
        if uri.startswith("http://localhost:") or uri.startswith("http://127.0.0.1:")
    ]


def _parse_port_from_uri(uri: str) -> int | None:
    """Extract the port number from a localhost URI string."""
    try:
        return int(uri.rstrip("/").rsplit(":", 1)[-1])
    except (ValueError, IndexError):
        return None


def _run_oauth_flow(credentials_file: str, client_config: dict) -> Credentials:
    """
    Run the OAuth2 local-server flow.

    - Desktop ('installed') client: picks any free port from OAUTH_PORT_CANDIDATES.
    - Web client: must use a port whose full URI is registered in Google Cloud Console.
      If the registered port is busy, raises a clear error with instructions to either
      free the port or register an additional redirect URI.
    """
    client_type = "installed" if "installed" in client_config else "web"

    if client_type == "installed":
        # Desktop app — Google accepts any localhost port automatically.
        port = _find_free_port(OAUTH_PORT_CANDIDATES)
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
        logger.info("Starting OAuth flow on port %d (Desktop client)", port)
        return flow.run_local_server(port=port, open_browser=True)

    # ── Web client ────────────────────────────────────────────────────────────
    registered_uris = _get_registered_localhost_uris(client_config)

    if not registered_uris:
        raise ValueError(
            "Your credentials.json is for a Web OAuth client but has no localhost "
            "redirect URIs registered.\n\n"
            "Fix (choose one):\n"
            "  A) Google Cloud Console → APIs & Services → Credentials → your OAuth client\n"
            "     Add  http://localhost:8080/  to 'Authorized redirect URIs', save, "
            "re-download credentials.json.\n"
            "  B) Create a new OAuth client with Application type 'Desktop app' and "
            "replace credentials.json with the downloaded file."
        )

    # Try each registered URI; pick the first whose port is free (or can be freed).
    chosen_uri: str | None = None
    chosen_port: int | None = None

    for uri in registered_uris:
        port = _parse_port_from_uri(uri)
        if port is None:
            continue
        if _force_free_port(port):
            chosen_uri = uri
            chosen_port = port
            break

    if chosen_uri is None:
        busy_ports = [p for p in (_parse_port_from_uri(u) for u in registered_uris) if p]
        raise OSError(
            f"OAuth callback port(s) {busy_ports} are still in use.\n\n"
            "Quick fixes:\n"
            "  1. Close any browser tab that opened during a previous sign-in attempt.\n"
            "  2. Wait a few seconds and click 'Authenticate' again.\n"
            "  3. Or add an extra redirect URI (e.g. http://localhost:8081/) in\n"
            "     Google Cloud Console → APIs & Services → Credentials → your OAuth client,\n"
            "     save, re-download credentials.json, and replace the existing file."
        )

    # Build the flow with the exact registered redirect_uri so Google accepts it.
    flow = InstalledAppFlow.from_client_secrets_file(
        credentials_file,
        SCOPES,
        redirect_uri=chosen_uri,
    )
    logger.info(
        "Starting OAuth flow on port %d with redirect_uri=%s (Web client)",
        chosen_port,
        chosen_uri,
    )
    return flow.run_local_server(port=chosen_port, open_browser=True)


def _token_has_required_scopes(creds) -> bool:
    """Return True if the saved token covers all scopes in SCOPES."""
    if not creds or not hasattr(creds, "scopes") or not creds.scopes:
        return False
    granted = set(creds.scopes)
    return all(s in granted for s in SCOPES)


def authenticate_gmail():
    """
    Authenticate with Gmail API using OAuth2.
    Returns an authenticated Gmail service object.
    """
    ensure_credentials_dir()
    creds = None

    # ── 1. Load existing token ────────────────────────────────────────────────
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "rb") as fh:
                creds = pickle.load(fh)
            logger.info("Using saved Gmail credentials.")
        except Exception as exc:
            logger.warning("Failed to load saved token: %s", exc)
            creds = None

    # ── 2. Discard token if it is missing required scopes ────────────────────
    if creds and not _token_has_required_scopes(creds):
        logger.warning(
            "Saved token is missing required scopes %s — re-authenticating.", SCOPES
        )
        try:
            os.remove(TOKEN_FILE)
        except OSError:
            pass
        creds = None

    # ── 3. Refresh if expired ─────────────────────────────────────────────────
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            logger.info("Gmail credentials refreshed.")
        except Exception as exc:
            logger.error("Failed to refresh token: %s", exc)
            creds = None

    # ── 4. Full OAuth flow if needed ──────────────────────────────────────────
    if not creds or not creds.valid:
        credentials_file = get_credentials_file()
        if not credentials_file:
            raise FileNotFoundError(
                f"credentials.json not found at {CREDENTIALS_FILE}.\n"
                "Download it from Google Cloud Console and place it in "
                "AI-Project/email_send/email_credentials/."
            )

        client_config = _load_client_config(credentials_file)
        creds = _run_oauth_flow(credentials_file, client_config)

        # Persist token for future runs
        with open(TOKEN_FILE, "wb") as fh:
            pickle.dump(creds, fh)
        logger.info("Gmail OAuth2 authentication successful.")

    return build("gmail", "v1", credentials=creds)


def send_email(to_email: str, subject: str, body: str, html: bool = False) -> dict:
    """
    Send an email via Gmail API.

    Args:
        to_email: Recipient email address
        subject:  Email subject line
        body:     Email body (plain text or HTML)
        html:     If True, send as HTML; otherwise plain text

    Returns:
        dict: {"success": bool, "message": str, "message_id": str | None}
    """
    try:
        service = authenticate_gmail()

        message = MIMEText(body, "html" if html else "plain")
        message["to"] = to_email
        message["subject"] = subject

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw_message})
            .execute()
        )

        logger.info("Email sent to %s | Message ID: %s", to_email, result["id"])
        return {
            "success": True,
            "message": f"Email successfully sent to {to_email}",
            "message_id": result["id"],
            "recipient": to_email,
        }

    except GoogleAPIError as exc:
        logger.error("Gmail API error: %s", exc)
        return {"success": False, "message": f"Gmail API error: {exc}", "message_id": None}
    except Exception as exc:
        logger.error("Email sending failed: %s", exc)
        return {"success": False, "message": f"Error sending email: {exc}", "message_id": None}


def create_draft(to_email: str, subject: str, body: str, html: bool = False) -> dict:
    """
    Save an email as a Gmail draft.

    Args:
        to_email: Recipient email address
        subject:  Email subject line
        body:     Email body (plain text or HTML)
        html:     If True, send as HTML; otherwise plain text

    Returns:
        dict: {"success": bool, "message": str, "draft_id": str | None}
    """
    try:
        service = authenticate_gmail()

        message = MIMEText(body, "html" if html else "plain")
        message["to"] = to_email
        message["subject"] = subject

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = (
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw_message}})
            .execute()
        )

        draft_id = result.get("id")
        logger.info("Draft saved for %s | Draft ID: %s", to_email, draft_id)
        return {
            "success": True,
            "message": f"Draft saved successfully for {to_email}",
            "draft_id": draft_id,
            "recipient": to_email,
        }

    except GoogleAPIError as exc:
        logger.error("Gmail API error while saving draft: %s", exc)
        return {"success": False, "message": f"Gmail API error: {exc}", "draft_id": None}
    except Exception as exc:
        logger.error("Draft creation failed: %s", exc)
        return {"success": False, "message": f"Error saving draft: {exc}", "draft_id": None}


def send_draft(draft_id: str) -> dict:
    """
    Send an existing Gmail draft by its draft ID.

    Args:
        draft_id: The Gmail draft ID to send

    Returns:
        dict: {"success": bool, "message": str, "message_id": str | None}
    """
    try:
        service = authenticate_gmail()

        result = (
            service.users()
            .drafts()
            .send(userId="me", body={"id": draft_id})
            .execute()
        )

        logger.info("Draft %s sent | Message ID: %s", draft_id, result.get("id"))
        return {
            "success": True,
            "message": "Draft sent successfully",
            "message_id": result.get("id"),
        }

    except GoogleAPIError as exc:
        logger.error("Gmail API error while sending draft: %s", exc)
        return {"success": False, "message": f"Gmail API error: {exc}", "message_id": None}
    except Exception as exc:
        logger.error("Sending draft failed: %s", exc)
        return {"success": False, "message": f"Error sending draft: {exc}", "message_id": None}


def is_gmail_authenticated() -> bool:
    """Return True if a saved token file exists."""
    return os.path.exists(TOKEN_FILE)


def clear_authentication() -> bool:
    """Delete saved Gmail credentials."""
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
        logger.info("Gmail credentials cleared.")
        return True
    return False


def get_authenticated_email() -> str | None:
    """Return the authenticated Gmail address, or None if not authenticated."""
    try:
        if is_gmail_authenticated():
            service = authenticate_gmail()
            profile = service.users().getProfile(userId="me").execute()
            return profile.get("emailAddress")
    except Exception as exc:
        logger.error("Failed to get email address: %s", exc)
    return None


# ── Inbox message listing ─────────────────────────────────────────────────────

def _parse_header(headers: list[dict], name: str) -> str:
    """Extract a single header value from the Gmail message headers list."""
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def _parse_from(from_header: str) -> tuple[str, str]:
    """Split a From header into (display_name, email_address)."""
    import re as _re
    match = _re.match(r'^\s*"?(.+?)"?\s*<([^>]+)>\s*$', from_header)
    if match:
        return match.group(1).strip().strip('"'), match.group(2).strip()
    # Bare email address
    email = from_header.strip().strip("<>")
    return email.split("@")[0], email


def _format_date(date_header: str) -> str:
    """Convert an RFC-2822 date header to a friendly local string."""
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(date_header).astimezone()  # convert to local tz
        return dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return date_header[:25] if date_header else "—"


def _extract_plain_body(payload: dict) -> str:
    """
    Recursively walk a Gmail message payload and return the first
    text/plain part decoded to a string.
    """
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        result = _extract_plain_body(part)
        if result:
            return result

    # Fallback: try text/html and strip tags
    if mime_type == "text/html" and body_data:
        import re as _re
        html = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
        return _re.sub(r"<[^>]+>", "", html).strip()

    for part in payload.get("parts", []):
        part_mime = part.get("mimeType", "")
        part_data = part.get("body", {}).get("data")
        if part_mime == "text/html" and part_data:
            import re as _re
            html = base64.urlsafe_b64decode(part_data).decode("utf-8", errors="replace")
            return _re.sub(r"<[^>]+>", "", html).strip()

    return ""


def _truncate(text: str, max_chars: int = 150) -> str:
    """Truncate text to max_chars, appending '...' if shortened."""
    text = " ".join(text.split())  # collapse whitespace
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def list_messages(max_results: int = 10, label_ids: list[str] | None = None) -> dict:
    """
    Fetch the most recent messages matching the given labels.

    Args:
        max_results: Number of messages to retrieve (1-50).
        label_ids:   Gmail label IDs to filter by (e.g. ["INBOX"],
                     ["CATEGORY_PROMOTIONS"], ["SENT"], ["DRAFT"]).
                     Defaults to ["INBOX"] when None.

    Returns:
        dict: {"success": bool, "messages": list[dict], "error": str | None}
        Each message dict contains:
            id, from_name, from_email, date, subject,
            body_preview (~150 chars), body_full, gmail_link
    """
    try:
        service = authenticate_gmail()
        max_results = max(1, min(max_results, 50))
        if label_ids is None:
            label_ids = ["INBOX"]

        # 1. Get message IDs
        result = (
            service.users()
            .messages()
            .list(userId="me", maxResults=max_results, labelIds=label_ids)
            .execute()
        )
        msg_ids = result.get("messages", [])

        if not msg_ids:
            return {"success": True, "messages": [], "total_estimate": 0, "error": None}

        # 2. Fetch full details for each message
        messages = [_fetch_and_parse_message(service, m["id"]) for m in msg_ids]

        logger.info("Fetched %d inbox messages.", len(messages))
        return {
            "success": True,
            "messages": messages,
            "total_estimate": result.get("resultSizeEstimate", len(messages)),
            "error": None,
        }

    except Exception as exc:
        logger.error("Failed to list messages: %s", exc)
        return {"success": False, "messages": [], "total_estimate": 0, "error": str(exc)}


def search_messages(query: str, max_results: int = 10) -> dict:
    """
    Search Gmail messages using Gmail's search query syntax.

    The *query* string supports the full Gmail search syntax, e.g.:
        from:user@example.com
        subject:invoice has:attachment
        is:unread newer_than:7d
        filename:pdf larger:5M
        category:promotions
        "exact phrase" -excluded_word

    Args:
        query:       Gmail search query string.
        max_results: Number of messages to retrieve (1-50).

    Returns:
        dict: {"success": bool, "messages": list[dict],
               "total_estimate": int, "query": str, "error": str | None}
    """
    try:
        service = authenticate_gmail()
        max_results = max(1, min(max_results, 50))

        if not query or not query.strip():
            return {
                "success": False,
                "messages": [],
                "total_estimate": 0,
                "query": query,
                "error": "Search query cannot be empty.",
            }

        result = (
            service.users()
            .messages()
            .list(userId="me", maxResults=max_results, q=query.strip())
            .execute()
        )
        msg_ids = result.get("messages", [])
        total_estimate = result.get("resultSizeEstimate", 0)

        if not msg_ids:
            return {
                "success": True,
                "messages": [],
                "total_estimate": 0,
                "query": query,
                "error": None,
            }

        messages = [_fetch_and_parse_message(service, m["id"]) for m in msg_ids]

        logger.info("Search '%s' returned %d messages (est. %d total).", query, len(messages), total_estimate)
        return {
            "success": True,
            "messages": messages,
            "total_estimate": total_estimate,
            "query": query,
            "error": None,
        }

    except Exception as exc:
        logger.error("Search failed for query '%s': %s", query, exc)
        return {
            "success": False,
            "messages": [],
            "total_estimate": 0,
            "query": query,
            "error": str(exc),
        }


def _fetch_and_parse_message(service, msg_id: str) -> dict:
    """Fetch a single message by ID and return a parsed dict."""
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=msg_id, format="full")
        .execute()
    )

    payload = msg.get("payload", {})
    headers = payload.get("headers", [])

    from_header = _parse_header(headers, "From")
    from_name, from_email = _parse_from(from_header)
    date_str = _format_date(_parse_header(headers, "Date"))
    subject = _parse_header(headers, "Subject") or "(No Subject)"

    body_full = _extract_plain_body(payload)
    body_preview = _truncate(body_full, 150)

    gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{msg_id}"

    return {
        "id": msg_id,
        "from_name": from_name,
        "from_email": from_email,
        "date": date_str,
        "subject": subject,
        "body_preview": body_preview,
        "body_full": body_full,
        "gmail_link": gmail_link,
    }


def trash_messages(msg_ids: list[str]) -> dict:
    """Move messages to Trash (safe delete)."""
    try:
        service = authenticate_gmail()
        trashed, failed = [], []
        for msg_id in msg_ids:
            try:
                service.users().messages().trash(userId="me", id=msg_id).execute()
                trashed.append(msg_id)
            except Exception as e:
                failed.append({"id": msg_id, "error": str(e)})
        logger.info("Trashed %d messages (%d failed).", len(trashed), len(failed))
        return {"success": True, "trashed_count": len(trashed),
                "failed_count": len(failed), "failed": failed, "error": None}
    except Exception as exc:
        logger.error("Failed to trash messages: %s", exc)
        return {"success": False, "trashed_count": 0,
                "failed_count": len(msg_ids), "failed": [], "error": str(exc)}


def untrash_messages(msg_ids: list[str]) -> dict:
    """Restore messages from Trash."""
    try:
        service = authenticate_gmail()
        restored, failed = [], []
        for msg_id in msg_ids:
            try:
                service.users().messages().untrash(userId="me", id=msg_id).execute()
                restored.append(msg_id)
            except Exception as e:
                failed.append({"id": msg_id, "error": str(e)})
        logger.info("Restored %d messages (%d failed).", len(restored), len(failed))
        return {"success": True, "restored_count": len(restored),
                "failed_count": len(failed), "failed": failed, "error": None}
    except Exception as exc:
        logger.error("Failed to restore messages: %s", exc)
        return {"success": False, "restored_count": 0,
                "failed_count": len(msg_ids), "failed": [], "error": str(exc)}


def delete_messages_permanently(msg_ids: list[str]) -> dict:
    """Permanently delete messages."""
    try:
        service = authenticate_gmail()
        deleted, failed = [], []
        for msg_id in msg_ids:
            try:
                service.users().messages().delete(userId="me", id=msg_id).execute()
                deleted.append(msg_id)
            except Exception as e:
                failed.append({"id": msg_id, "error": str(e)})
        logger.info("Permanently deleted %d messages (%d failed).", len(deleted), len(failed))
        return {"success": True, "deleted_count": len(deleted),
                "failed_count": len(failed), "failed": failed, "error": None}
    except Exception as exc:
        logger.error("Failed to permanently delete messages: %s", exc)
        return {"success": False, "deleted_count": 0,
                "failed_count": len(msg_ids), "failed": [], "error": str(exc)}

