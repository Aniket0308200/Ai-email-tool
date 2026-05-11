"""
slack_handler.py
----------------
Handles Slack workspace authentication and core API interactions.
"""

import os
import json
import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "slack_credentials.json")

def get_slack_client() -> WebClient | None:
    token = _load_token()
    if token:
        return WebClient(token=token)
    return None

def _load_token() -> str | None:
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "r") as f:
                data = json.load(f)
                # Support new format 'slack_token' or fallback to old 'bot_token'
                return data.get("slack_token") or data.get("bot_token")
        except Exception as e:
            logger.error(f"Error reading slack token: {e}")
    return None

def is_slack_authenticated() -> bool:
    """Return True if a valid Slack token is stored."""
    return _load_token() is not None

def get_authenticated_workspace() -> str:
    """Return the name of the connected Slack workspace, or empty string."""
    client = get_slack_client()
    if client:
        try:
            response = client.auth_test()
            return response.data.get("team", "Unknown Workspace")
        except SlackApiError as e:
            logger.error(f"Slack auth error: {e}")
    return ""

def authenticate_slack(token: str) -> bool:
    """
    Validate the token and save it locally if valid.
    """
    client = WebClient(token=token)
    try:
        response = client.auth_test()
        if response.get("ok"):
            # Save token
            with open(CREDENTIALS_FILE, "w") as f:
                json.dump({"slack_token": token}, f)
            return True
        return False
    except SlackApiError as e:
        raise Exception(f"Slack API Error: {e.response['error']}")

def clear_authentication() -> bool:
    """Remove stored Slack credentials."""
    if os.path.exists(CREDENTIALS_FILE):
        os.remove(CREDENTIALS_FILE)
    return True

def fetch_channels() -> list[dict]:
    """Fetch public and private channels the bot has access to."""
    client = get_slack_client()
    if not client:
        return []
    try:
        response = client.conversations_list(types="public_channel,private_channel")
        channels = response.get("channels", [])
        return [{"id": c["id"], "name": c["name"]} for c in channels if not c.get("is_archived")]
    except SlackApiError as e:
        logger.error(f"Error fetching channels: {e}")
        return []

def fetch_users() -> list[dict]:
    """Fetch users in the workspace."""
    client = get_slack_client()
    if not client:
        return []
    try:
        response = client.users_list()
        users = response.get("members", [])
        return [{"id": u["id"], "name": u.get("real_name") or u.get("name")} 
                for u in users if not u.get("deleted") and not u.get("is_bot") and u["id"] != "USLACKBOT"]
    except SlackApiError as e:
        logger.error(f"Error fetching users: {e}")
        return []

def send_slack_message(destination_id: str, text: str) -> dict:
    """
    Send a message to a channel or user (DM).

    - If destination_id starts with U/W → open a DM conversation first, then post.
    - If destination_id is a channel → try chat_postMessage directly.
      If the bot is not in the channel, try conversations_join first.
      If join is not allowed (missing scope), suggest chat:write.public or manual invite.
    """
    client = get_slack_client()
    if not client:
        return {"success": False, "error": "Slack not authenticated"}

    # ── Direct Message ────────────────────────────────────────────────────────
    if destination_id.startswith("U") or destination_id.startswith("W"):
        try:
            conv = client.conversations_open(users=destination_id)
            dm_channel_id = conv["channel"]["id"]
        except SlackApiError as e:
            error_code = e.response.get("error", "unknown")
            if error_code == "missing_scope":
                return {
                    "success": False,
                    "error": (
                        "Missing scope for DMs. Add the 'im:write' scope to your "
                        "Slack app under OAuth & Permissions → Bot Token Scopes, "
                        "then reinstall the app to your workspace."
                    ),
                }
            return {"success": False, "error": f"Could not open DM: {error_code}"}

        try:
            response = client.chat_postMessage(channel=dm_channel_id, text=text)
            return {"success": True, "message_id": response["ts"]}
        except SlackApiError as e:
            error_code = e.response.get("error", "unknown")
            return {"success": False, "error": f"Failed to send DM: {error_code}"}

    # ── Channel Message ───────────────────────────────────────────────────────
    try:
        response = client.chat_postMessage(channel=destination_id, text=text)
        return {"success": True, "message_id": response["ts"]}

    except SlackApiError as e:
        error_code = e.response.get("error", "unknown")

        if error_code == "not_in_channel":
            # Try to join the channel first
            try:
                client.conversations_join(channel=destination_id)
                response = client.chat_postMessage(channel=destination_id, text=text)
                return {"success": True, "message_id": response["ts"]}
            except SlackApiError as join_err:
                join_error_code = join_err.response.get("error", "unknown")
                if join_error_code == "missing_scope":
                    return {
                        "success": False,
                        "error": (
                            "Bot is not in this channel. Fix with one of these options:\n"
                            "Option A (recommended): Add the 'chat:write.public' scope to your "
                            "Slack app — this lets the bot post to any public channel without joining.\n"
                            "Option B: Add the 'channels:join' scope so the bot can auto-join.\n"
                            "Option C: Manually invite the bot by typing '/invite @your_bot_name' "
                            "in the Slack channel."
                        ),
                    }
                return {
                    "success": False,
                    "error": (
                        f"Bot is not in this channel (join failed: {join_error_code}). "
                        "Invite the bot by typing '/invite @your_bot_name' in the channel."
                    ),
                }

        if error_code == "channel_not_found":
            return {
                "success": False,
                "error": "Channel not found. Make sure the bot is invited to private channels.",
            }

        return {"success": False, "error": f"Slack API error: {error_code}"}
