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
