"""
Hackathon · Part 2: Gmail helper
Reads the newest email in your inbox and can save a reply as a Gmail DRAFT.
It never sends anything.

FIRST-TIME SETUP (see the steps in chat):
  1. Put credentials.json (downloaded from Google Cloud) in this folder.
  2. pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
  3. python gmail_client.py
     -> a browser window opens, you sign in and approve, and token.json is created.

NEVER commit credentials.json or token.json to git, and never share them.
"""

import base64
import os
import re
from email.header import Header
from email.mime.text import MIMEText
from html import unescape

# Read the inbox, and create drafts (compose scope cannot read; readonly cannot write).
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
MAX_BODY_CHARS = 8000  # keep prompts small so the model stays fast and within rate limits


def get_service():
    """Return an authorized Gmail API client, opening a browser sign-in the first time."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None  # token revoked or expired: sign in again
        if not creds or not creds.valid:
            if not os.path.exists(CREDS_FILE):
                raise RuntimeError(
                    "credentials.json not found. Put it in the same folder as gmail_client.py "
                    "(see the Google Cloud setup steps)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# ---------- parsing helpers (pure functions, easy to test) ----------

def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _find_part(payload: dict, mime_type: str):
    """Depth-first search for the first part with this MIME type that has body data."""
    if payload.get("mimeType") == mime_type and payload.get("body", {}).get("data"):
        return _decode(payload["body"]["data"])
    for part in payload.get("parts") or []:
        found = _find_part(part, mime_type)
        if found:
            return found
    return None


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", html)
    text = unescape(re.sub(r"<[^>]+>", "", html)).replace("\xa0", " ")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_body(payload: dict) -> str:
    """Prefer the plain-text part; fall back to stripping the HTML part."""
    text = _find_part(payload, "text/plain")
    if text is None:
        html = _find_part(payload, "text/html")
        text = _html_to_text(html) if html else ""
    return text.strip()[:MAX_BODY_CHARS]


def _header(headers: list, name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


# ---------- Gmail calls ----------

def get_email(service, msg_id: str) -> dict:
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])
    return {
        "id": msg["id"],
        "thread_id": msg.get("threadId"),
        "from": _header(headers, "From"),
        "reply_to": _header(headers, "Reply-To"),
        "subject": _header(headers, "Subject") or "(no subject)",
        "message_id": _header(headers, "Message-ID") or _header(headers, "Message-Id"),
        "references": _header(headers, "References"),
        "body": extract_body(payload),
        "labels": msg.get("labelIds", []),
    }


def list_recent_emails(days: int = 1, max_results: int = 20) -> list:
    """Inbox emails from the last `days` days (newest first), up to max_results."""
    service = get_service()
    resp = service.users().messages().list(
        userId="me", labelIds=["INBOX"], q=f"newer_than:{days}d", maxResults=max_results
    ).execute()
    return [get_email(service, m["id"]) for m in resp.get("messages", [])]


def get_latest_email() -> dict:
    """The first (newest) email in the inbox."""
    service = get_service()
    resp = service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=1).execute()
    messages = resp.get("messages", [])
    if not messages:
        raise RuntimeError("Your inbox is empty.")
    return get_email(service, messages[0]["id"])


def create_reply_draft(msg_id: str, reply_text: str) -> str:
    """Save reply_text as a draft reply in the same thread. Returns the draft id."""
    service = get_service()
    original = get_email(service, msg_id)

    subject = original["subject"]
    if not subject.lower().startswith("re:"):
        subject = "Re: " + subject

    mime = MIMEText(reply_text, "plain", "utf-8")
    mime["To"] = original["reply_to"] or original["from"]
    mime["Subject"] = subject if subject.isascii() else Header(subject, "utf-8")
    if original["message_id"]:
        mime["In-Reply-To"] = original["message_id"]
        mime["References"] = (original["references"] + " " + original["message_id"]).strip()

    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
    body = {"message": {"raw": raw}}
    if original["thread_id"]:
        body["message"]["threadId"] = original["thread_id"]

    draft = service.users().drafts().create(userId="me", body=body).execute()
    return draft["id"]


if __name__ == "__main__":
    # Run this once to sign in and confirm the connection works.
    mail = get_latest_email()
    print("Connected to Gmail.\n")
    print("From:   ", mail["from"])
    print("Subject:", mail["subject"])
    print("Body (first 300 chars):\n", mail["body"][:300])