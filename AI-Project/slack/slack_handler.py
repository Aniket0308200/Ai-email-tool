"""
slack_handler.py
----------------
Handles Slack workspace authentication and core API interactions.
"""

import os
import json
import time
import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "slack_credentials.json")

def get_slack_client() -> WebClient | None:
    token = _load_token()
    if token:
        # Increased timeout to 60s to prevent TimeoutErrors during deep workspace searches
        return WebClient(token=token, timeout=60)
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

def fetch_channels() -> dict:
    """Fetch public and private channels with error reporting."""
    client = get_slack_client()
    if not client:
        return {"data": [], "error": "Slack not authenticated"}
    try:
        response = client.conversations_list(types="public_channel,private_channel")
        channels = response.get("channels", [])
        data = [{"id": c["id"], "name": c["name"]} for c in channels if not c.get("is_archived")]
        return {"data": data, "error": None}
    except SlackApiError as e:
        err = e.response.get("error", str(e))
        return {"data": [], "error": err}

def fetch_users() -> dict:
    """Fetch users with error reporting."""
    client = get_slack_client()
    if not client:
        return {"data": [], "error": "Slack not authenticated"}
    try:
        response = client.users_list()
        users = response.get("members", [])
        data = [{"id": u["id"], "name": u.get("real_name") or u.get("name")} 
                for u in users if not u.get("deleted") and not u.get("is_bot") and u["id"] != "USLACKBOT"]
        return {"data": data, "error": None}
    except SlackApiError as e:
        err = e.response.get("error", str(e))
        return {"data": [], "error": err}

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
            return {"success": True, "message_id": response["ts"], "ts": response["ts"]}
        except SlackApiError as e:
            error_code = e.response.get("error", "unknown")
            return {"success": False, "error": f"Failed to send DM: {error_code}"}

    # ── Channel Message ───────────────────────────────────────────────────────
    try:
        response = client.chat_postMessage(channel=destination_id, text=text)
        return {"success": True, "message_id": response["ts"], "ts": response["ts"]}

    except SlackApiError as e:
        error_code = e.response.get("error", "unknown")

        if error_code == "not_in_channel":
            # Try to join the channel first
            try:
                client.conversations_join(channel=destination_id)
                response = client.chat_postMessage(channel=destination_id, text=text)
                return {"success": True, "message_id": response["ts"], "ts": response["ts"]}
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

def fetch_list_data(list_type: str, channel_id: str = None, limit: int = 50, search_query: str = None) -> dict:
    """
    Fetch structured lists of data from Slack API for Explorer Views.

    All calls use Bot Token scopes only — no User Token / search:read required.
    search_messages / search_files require a User Token and are intentionally
    avoided here; keyword filtering is done client-side instead.
    """
    client = get_slack_client()
    if not client:
        return {"data": [], "error": "Slack not authenticated"}

    try:
        # ── Channels ──────────────────────────────────────────────────────────
        if list_type == "channels":
            resp = client.conversations_list(types="public_channel", limit=limit)
            return {"data": resp.get("channels", []), "error": None}

        elif list_type == "private_channels":
            resp = client.conversations_list(types="private_channel", limit=limit)
            return {"data": resp.get("channels", []), "error": None}

        elif list_type == "dms":
            resp = client.conversations_list(types="im", limit=limit)
            return {"data": resp.get("channels", []), "error": None}

        elif list_type == "group_dms":
            resp = client.conversations_list(types="mpim", limit=limit)
            return {"data": resp.get("channels", []), "error": None}

        # ── Users ─────────────────────────────────────────────────────────────
        elif list_type == "users":
            resp = client.users_list(limit=limit)
            members = [
                m for m in resp.get("members", [])
                if not m.get("deleted") and not m.get("is_bot") and m["id"] != "USLACKBOT"
            ]
            return {"data": members, "error": None}

        # ── Messages (channel history only — no search API) ───────────────────
        elif list_type == "messages":
            if channel_id == "all":
                chan_resp = client.conversations_list(
                    types="public_channel,private_channel", limit=20
                )
                joined = [c for c in chan_resp.get("channels", []) if c.get("is_member")]
                all_msgs = []
                for ch in joined[:10]:
                    try:
                        h = client.conversations_history(channel=ch["id"], limit=20)
                        for m in h.get("messages", []):
                            m["channel_id"] = ch["id"]
                            m["channel_name"] = ch.get("name", "Unknown")
                        all_msgs.extend(h.get("messages", []))
                    except:
                        continue
                return {"data": all_msgs, "error": None}
            if not channel_id:
                return {"data": [], "error": "Channel ID required for messages."}
            resp = client.conversations_history(channel=channel_id, limit=limit)
            msgs = resp.get("messages", [])
            for m in msgs:
                m["channel_id"] = channel_id
            return {"data": msgs, "error": None}

        # ── Reactions (messages that have reactions) ──────────────────────────
        elif list_type == "reactions":
            if channel_id == "all":
                chan_resp = client.conversations_list(
                    types="public_channel,private_channel", limit=20
                )
                joined = [c for c in chan_resp.get("channels", []) if c.get("is_member")]
                all_msgs = []
                for ch in joined[:10]:
                    try:
                        h = client.conversations_history(channel=ch["id"], limit=50)
                        for m in h.get("messages", []):
                            if m.get("reactions"):
                                m["channel_id"] = ch["id"]
                                m["channel_name"] = ch.get("name", "Unknown")
                                all_msgs.append(m)
                    except:
                        continue
                return {"data": all_msgs, "error": None}
            if not channel_id:
                return {"data": [], "error": "Channel ID required for reactions."}
            resp = client.conversations_history(channel=channel_id, limit=limit)
            msgs = [m for m in resp.get("messages", []) if m.get("reactions")]
            for m in msgs:
                m["channel_id"] = channel_id
            return {"data": msgs, "error": None}

        # ── Threads (messages with replies) ───────────────────────────────────
        elif list_type == "threads":
            if channel_id == "all":
                chan_resp = client.conversations_list(
                    types="public_channel,private_channel", limit=20
                )
                joined = [c for c in chan_resp.get("channels", []) if c.get("is_member")]
                all_msgs = []
                for ch in joined[:10]:
                    try:
                        h = client.conversations_history(channel=ch["id"], limit=50)
                        for m in h.get("messages", []):
                            if m.get("reply_count", 0) > 0:
                                m["channel_id"] = ch["id"]
                                m["channel_name"] = ch.get("name", "Unknown")
                                all_msgs.append(m)
                    except:
                        continue
                return {"data": all_msgs, "error": None}
            if not channel_id:
                return {"data": [], "error": "Channel ID required for threads."}
            resp = client.conversations_history(channel=channel_id, limit=limit)
            msgs = [m for m in resp.get("messages", []) if m.get("reply_count", 0) > 0]
            for m in msgs:
                m["channel_id"] = channel_id
            return {"data": msgs, "error": None}

        # ── Unread Messages — uses conversations.info unread_count ────────────
        elif list_type == "unread_messages":
            # Bot tokens cannot track per-user read state.
            # We use conversations.info which exposes unread_count for the bot.
            # Only channels where unread_count > 0 are included.
            if not channel_id:
                return {"data": [], "error": "Channel ID required for unread messages."}
            try:
                info = client.conversations_info(channel=channel_id, include_num_members=False)
                ch_info = info.get("channel", {})
                unread_count = ch_info.get("unread_count", 0)
                if unread_count == 0:
                    return {"data": [], "error": None, "empty_reason": "no_unread"}
                # Fetch the unread messages (last unread_count messages)
                resp = client.conversations_history(channel=channel_id, limit=min(unread_count, limit))
                msgs = resp.get("messages", [])
                for m in msgs:
                    m["channel_id"] = channel_id
                return {"data": msgs, "error": None}
            except SlackApiError as e:
                err = e.response.get("error", str(e))
                return {"data": [], "error": err}

        # ── Mentions — messages containing <@BOTID> or <@USERID> ─────────────
        elif list_type == "mentions":
            # Bot tokens cannot use search.messages (requires User Token).
            # We fetch history and filter for messages containing <@ mentions.
            if not channel_id:
                return {"data": [], "error": "Channel ID required for mentions."}
            try:
                # Get the bot's own user ID to filter self-mentions
                auth = client.auth_test()
                bot_user_id = auth.get("user_id", "")
                resp = client.conversations_history(channel=channel_id, limit=limit)
                msgs = [
                    m for m in resp.get("messages", [])
                    if "<@" in m.get("text", "")
                ]
                for m in msgs:
                    m["channel_id"] = channel_id
                return {"data": msgs, "error": None}
            except SlackApiError as e:
                err = e.response.get("error", str(e))
                return {"data": [], "error": err}

        # ── Files ─────────────────────────────────────────────────────────────
        elif list_type == "files":
            # files.list requires files:read bot scope — no search API needed
            kwargs = {"count": limit}
            if channel_id:
                kwargs["channel"] = channel_id
            resp = client.files_list(**kwargs)
            return {"data": resp.get("files", []), "error": None}

        # ── Pinned messages ───────────────────────────────────────────────────
        elif list_type == "pinned_messages":
            if not channel_id:
                return {"data": [], "error": "Channel ID required to view pinned messages."}
            resp = client.pins_list(channel=channel_id)
            return {"data": resp.get("items", []), "error": None}

        # ── Starred Items ─────────────────────────────────────────────────────
        elif list_type == "stars":
            # stars.list returns all starred items for the user
            resp = client.stars_list(limit=limit)
            return {"data": resp.get("items", []), "error": None}

        else:
            return {"data": [], "error": f"Invalid list type: {list_type}"}

    except SlackApiError as e:
        err = e.response.get("error", str(e))
        if err == "missing_scope":
            scopes_needed = {
                "channels":         "channels:read",
                "private_channels": "groups:read",
                "dms":              "im:read",
                "group_dms":        "mpim:read",
                "users":            "users:read",
                "messages":         "channels:history or groups:history",
                "reactions":        "channels:history",
                "threads":          "channels:history",
                "unread_messages":  "channels:history",
                "mentions":         "channels:history",
                "files":            "files:read",
                "pinned_messages":  "pins:read",
            }.get(list_type, "appropriate scope")
            return {
                "data": [],
                "error": f"missing_scope — add '{scopes_needed}' to your Slack app's Bot Token Scopes, then reinstall.",
            }
        return {"data": [], "error": err}

def create_channel(name: str, is_private: bool = False) -> dict:
    """Create a new channel, normalizing the name first."""
    client = get_slack_client()
    if not client:
        return {"success": False, "error": "Slack not authenticated"}
    
    # Normalize name: lowercase, replace spaces/specials with hyphens
    import re
    clean_name = name.lower().strip()
    clean_name = re.sub(r'[^a-z0-9._-]', '-', clean_name)
    clean_name = re.sub(r'-+', '-', clean_name).strip('-')
    
    try:
        response = client.conversations_create(name=clean_name, is_private=is_private)
        return {"success": True, "channel_id": response["channel"]["id"], "final_name": clean_name}
    except SlackApiError as e:
        return {"success": False, "error": e.response.get("error", str(e))}

def rename_channel(channel_id: str, new_name: str) -> dict:
    """Rename an existing channel."""
    client = get_slack_client()
    if not client:
        return {"success": False, "error": "Slack not authenticated"}
    try:
        response = client.conversations_rename(channel=channel_id, name=new_name)
        return {"success": True, "channel_id": response["channel"]["id"]}
    except SlackApiError as e:
        return {"success": False, "error": e.response.get("error", str(e))}

def add_users_to_channel(channel_id: str, user_ids: list[str]) -> dict:
    """Add one or more users to a channel."""
    client = get_slack_client()
    if not client:
        return {"success": False, "error": "Slack not authenticated"}
    try:
        users_str = ",".join(user_ids)
        client.conversations_invite(channel=channel_id, users=users_str)
        return {"success": True}
    except SlackApiError as e:
        return {"success": False, "error": e.response.get("error", str(e))}

def archive_channel(channel_id: str) -> dict:
    """Archive a channel (Slack's equivalent of temporary/soft deletion)."""
    client = get_slack_client()
    if not client:
        return {"success": False, "error": "Slack not authenticated"}
    try:
        client.conversations_archive(channel=channel_id)
        return {"success": True}
    except SlackApiError as e:
        return {"success": False, "error": e.response.get("error", str(e))}

def forward_message(channel_id: str, message_ts: str, target_channel_id: str) -> dict:
    """Forward a message by quoting it in a new message via permalink."""
    client = get_slack_client()
    if not client:
        return {"success": False, "error": "Slack not authenticated"}
    try:
        # Get permalink for the message
        p_resp = client.chat_getPermalink(channel=channel_id, message_ts=message_ts)
        permalink = p_resp.get("permalink")
        
        # Post permalink to target channel
        client.chat_postMessage(channel=target_channel_id, text=f"Forwarded message: {permalink}")
        return {"success": True}
    except SlackApiError as e:
        return {"success": False, "error": e.response.get("error", str(e))}

def unarchive_channel(channel_id: str) -> dict:
    """Restore an archived channel."""
    client = get_slack_client()
    if not client:
        return {"success": False, "error": "Slack not authenticated"}
    try:
        client.conversations_unarchive(channel=channel_id)
        return {"success": True}
    except SlackApiError as e:
        return {"success": False, "error": e.response.get("error", str(e))}

def update_message(channel_id: str, ts: str, text: str) -> dict:
    """Edit an existing message."""
    client = get_slack_client()
    if not client: return {"success": False, "error": "Not authenticated"}
    try:
        client.chat_update(channel=channel_id, ts=ts, text=text)
        return {"success": True}
    except SlackApiError as e:
        return {"success": False, "error": e.response["error"]}

def add_pin(channel_id: str, ts: str) -> dict:
    """Pin a message to a channel."""
    client = get_slack_client()
    if not client: return {"success": False, "error": "Not authenticated"}
    try:
        client.pins_add(channel=channel_id, timestamp=ts)
        return {"success": True}
    except SlackApiError as e:
        return {"success": False, "error": e.response["error"]}

def add_star(channel_id: str, ts: str) -> dict:
    """Star/Save a message."""
    client = get_slack_client()
    if not client: return {"success": False, "error": "Not authenticated"}
    try:
        # stars.add can take channel or file, etc.
        client.stars_add(channel=channel_id, timestamp=ts)
        return {"success": True}
    except SlackApiError as e:
        return {"success": False, "error": e.response["error"]}

def fetch_unread_mentions(limit: int = 20) -> dict:
    """Fetch recent mentions/activity as a proxy for unreads."""
    client = get_slack_client()
    if not client: return {"data": [], "error": "Not authenticated"}
    try:
        # Search for mentions of the current user or just recent messages in joined channels
        # Using search.messages if possible, or conversations.history for all channels
        # For simplicity and reliability, we'll fetch recent messages from all joined channels
        chan_resp = client.conversations_list(types="public_channel,private_channel,im,mpim", limit=100)
        channels = [c for c in chan_resp.get("channels", []) if c.get("is_member")]
        
        unreads = []
        # Pre-fetch users for mapping
        u_resp = fetch_users()
        user_map = {u["id"]: u["name"] for u in u_resp.get("data", [])}
        
        for ch in channels[:10]: # Limit channels for speed
            hist = client.conversations_history(channel=ch["id"], limit=10)
            for m in hist.get("messages", []):
                ts = float(m.get("ts", 0))
                if time.time() - ts < 86400: # Last 24 hours
                    user_id = m.get("user", "—")
                    user_name = user_map.get(user_id, user_id)
                    unreads.append({
                        "channel_id": ch["id"],
                        "channel_name": ch.get("name", "DM"),
                        "user": user_id,
                        "user_name": user_name,
                        "text": m.get("text", "—"),
                        "ts": m.get("ts"),
                        "time": datetime.fromtimestamp(ts).strftime("%H:%M")
                    })
        return {"data": unreads, "error": None}
    except SlackApiError as e:
        return {"data": [], "error": str(e)}

def delete_message(channel_id: str, ts: str) -> dict:
    """Permanently delete a message from Slack."""
    client = get_slack_client()
    if not client:
        return {"success": False, "error": "Slack not authenticated"}
    try:
        client.chat_delete(channel=channel_id, ts=ts)
        return {"success": True}
    except SlackApiError as e:
        return {"success": False, "error": e.response.get("error", str(e))}

def fetch_archived_channels() -> dict:
    """Fetch only archived channels."""
    client = get_slack_client()
    if not client:
        return {"data": [], "error": "Slack not authenticated"}
    try:
        response = client.conversations_list(types="public_channel,private_channel", limit=1000)
        channels = response.get("channels", [])
        data = [{"id": c["id"], "name": c["name"]} for c in channels if c.get("is_archived")]
        return {"data": data, "error": None}
    except SlackApiError as e:
        err = e.response.get("error", str(e))
        return {"data": [], "error": err}

def remove_reaction(channel_id: str, ts: str, name: str) -> dict:
    """Remove a specific reaction from a message."""
    client = get_slack_client()
    if not client: return {"success": False, "error": "Auth failed"}
    try:
        client.reactions_remove(channel=channel_id, timestamp=ts, name=name)
        return {"success": True}
    except SlackApiError as e:
        return {"success": False, "error": e.response.get("error", str(e))}

def remove_pin(channel_id: str, ts: str) -> dict:
    """Unpin a message."""
    client = get_slack_client()
    if not client: return {"success": False, "error": "Auth failed"}
    try:
        client.pins_remove(channel=channel_id, timestamp=ts)
        return {"success": True}
    except SlackApiError as e:
        return {"success": False, "error": e.response.get("error", str(e))}

def remove_star(channel_id: str, ts: str) -> dict:
    """Remove a star/saved item."""
    client = get_slack_client()
    if not client: return {"success": False, "error": "Auth failed"}
    try:
        client.stars_remove(channel=channel_id, timestamp=ts)
        return {"success": True}
    except SlackApiError as e:
        return {"success": False, "error": e.response.get("error", str(e))}

def delete_scheduled_message(channel_id: str, scheduled_id: str) -> dict:
    """Delete a message that was scheduled to be sent."""
    client = get_slack_client()
    if not client: return {"success": False, "error": "Auth failed"}
    try:
        client.chat_scheduledMessages_delete(channel=channel_id, scheduled_message_id=scheduled_id)
        return {"success": True}
    except SlackApiError as e:
        return {"success": False, "error": e.response.get("error", str(e))}

def delete_reminder(reminder_id: str) -> dict:
    """Delete a Slack reminder."""
    client = get_slack_client()
    if not client: return {"success": False, "error": "Auth failed"}
    try:
        client.reminders_delete(reminder=reminder_id)
        return {"success": True}
    except SlackApiError as e:
        return {"success": False, "error": e.response.get("error", str(e))}

def close_conversation(channel_id: str) -> dict:
    """Close a DM or multi-person DM."""
    client = get_slack_client()
    if not client: return {"success": False, "error": "Auth failed"}
    try:
        client.conversations_close(channel=channel_id)
        return {"success": True}
    except SlackApiError as e:
        return {"success": False, "error": e.response.get("error", str(e))}


def mark_channel_read(channel_id: str) -> dict:
    """
    Mark all messages in a channel as read by setting the read cursor
    to the latest message timestamp via conversations.mark.
    Requires channels:write or groups:write scope.
    """
    client = get_slack_client()
    if not client:
        return {"success": False, "error": "Not authenticated"}
    try:
        # Get the latest message ts
        hist = client.conversations_history(channel=channel_id, limit=1)
        messages = hist.get("messages", [])
        if not messages:
            return {"success": True}  # Nothing to mark
        latest_ts = messages[0]["ts"]
        client.conversations_mark(channel=channel_id, ts=latest_ts)
        return {"success": True}
    except SlackApiError as e:
        err = e.response.get("error", str(e))
        if err == "missing_scope":
            return {
                "success": False,
                "error": "Add 'channels:write' (public) or 'groups:write' (private) scope to mark channels as read.",
            }
        return {"success": False, "error": err}

def kick_user_from_channel(channel_id: str, user_id: str) -> dict:
    """Remove a user from a channel."""
    client = get_slack_client()
    if not client: return {"success": False, "error": "Auth failed"}
    try:
        client.conversations_kick(channel=channel_id, user=user_id)
        return {"success": True}
    except SlackApiError as e:
        return {"success": False, "error": e.response.get("error", str(e))}

def get_or_create_dm(user_id: str) -> str | None:
    """Resolve a DM channel ID for a given user ID."""
    client = get_slack_client()
    if not client: return None
    try:
        resp = client.conversations_open(users=user_id)
        return resp.get("channel", {}).get("id")
    except SlackApiError:
        return None

def search_workspace_data(query: str, limit: int, newest_first: bool, filter_type: str = "All") -> dict:
    """
    Fetch all accessible data from the workspace and return rows
    matching the query keyword, grouped by category.
    """
    q = query.lower()
    results = {
        "channels":  [],
        "users":     [],
        "messages":  [],
        "files":     [],
    }

    client = get_slack_client()
    if not client:
        return results

    # Pre-fetch users for ID-to-Name mapping
    user_map = {}
    try:
        u_resp = client.users_list(limit=1000)
        user_map = {u["id"]: u.get("real_name") or u.get("name") for u in u_resp.get("members", [])}
    except: pass

    # ── Channels ──────────────────────────────────────────────────────────
    if filter_type in ["All", "Channels"]:
        try:
            resp = client.conversations_list(types="public_channel,private_channel", limit=1000)
            for c in resp.get("channels", []):
                name = (c.get("name") or "").lower()
                topic = (c.get("topic", {}).get("value") or "").lower()
                purpose = (c.get("purpose", {}).get("value") or "").lower()
                if q in name or q in topic or q in purpose:
                    results["channels"].append({
                        "Name":    "#" + c.get("name", ""),
                        "Members": c.get("num_members", "—"),
                        "Topic":   c.get("topic", {}).get("value") or "—",
                        "ID":      c.get("id"),
                        "channel_id": c.get("id")
                    })
                    if len(results["channels"]) >= limit:
                        break
        except SlackApiError:
            pass

    # ── Users ─────────────────────────────────────────────────────────────
    if filter_type in ["All", "Users"]:
        try:
            resp = client.users_list(limit=1000)
            for u in resp.get("members", []):
                if u.get("deleted") or u.get("is_bot") or u["id"] == "USLACKBOT":
                    continue
                name      = (u.get("real_name") or u.get("name") or "").lower()
                email     = (u.get("profile", {}).get("email") or "").lower()
                title     = (u.get("profile", {}).get("title") or "").lower()
                display   = (u.get("profile", {}).get("display_name") or "").lower()
                if q in name or q in email or q in title or q in display:
                    results["users"].append({
                        "Name":  u.get("real_name") or u.get("name"),
                        "Title": u.get("profile", {}).get("title") or "—",
                        "Email": u.get("profile", {}).get("email") or "—",
                        "ID":    u["id"],
                        "user_id": u["id"]
                    })
                    if len(results["users"]) >= limit:
                        break
        except SlackApiError:
            pass

    # ── Messages ──────────────────────────────────────────────────────────
    if filter_type in ["All", "Messages"]:
        try:
            channel_resp = client.conversations_list(
                types="public_channel,private_channel,im,mpim", limit=200
            )
            joined_channels = [
                c for c in channel_resp.get("channels", [])
                if c.get("is_member")
            ]
            for ch in joined_channels[:30]:          # cap at 30 channels to stay fast
                try:
                    hist = client.conversations_history(channel=ch["id"], limit=200)
                    for m in hist.get("messages", []):
                        text = m.get("text", "")
                        if q in text.lower():
                            preview = text[:120] + ("…" if len(text) > 120 else "")
                            ts_raw = m.get("ts")
                            try:
                                ts_val = float(ts_raw)
                                dt = datetime.fromtimestamp(ts_val).strftime("%b %d, %Y %H:%M")
                            except:
                                ts_val = 0
                                dt = "—"
                            
                            uid = m.get("user") or m.get("username") or "—"
                            uname = user_map.get(uid, uid)
                            
                            results["messages"].append({
                                "Channel": "#" + ch.get("name", ch["id"]),
                                "User":    uname,
                                "Message": preview,
                                "Time":    dt,
                                "_ts":     ts_val,
                                "_raw":    text,
                                "channel_id": ch["id"],
                                "ts": ts_raw
                            })
                            if len(results["messages"]) >= limit:
                                break
                    if len(results["messages"]) >= limit:
                        break
                except SlackApiError as e:
                    logger.warning(f"Failed to fetch history for channel {ch['id']}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Unexpected error in channel {ch['id']}: {e}")
                    continue
        except SlackApiError:
            pass

    # ── Files ─────────────────────────────────────────────────────────────
    if filter_type in ["All", "Files"]:
        try:
            resp = client.files_list(count=200)
            for f in resp.get("files", []):
                name    = (f.get("name") or "").lower()
                title   = (f.get("title") or "").lower()
                ftype   = (f.get("filetype") or "").lower()
                if q in name or q in title or q in ftype:
                    size_kb = round(f.get("size", 0) / 1024, 1) if f.get("size") else 0
                    uid = f.get("user") or "—"
                    uname = user_map.get(uid, uid)
                    results["files"].append({
                        "Name":    f.get("name") or "—",
                        "Type":    f.get("filetype") or "—",
                        "Size KB": size_kb,
                        "User":    uname,
                        "ID":      f.get("id"),
                        "file_id": f.get("id")
                    })
                    if len(results["files"]) >= limit:
                        break
        except SlackApiError:
            pass

    # ── Sort Messages by Timestamp ───────────────────────────────────────
    results["messages"].sort(key=lambda x: x["_ts"], reverse=newest_first)

    return results





