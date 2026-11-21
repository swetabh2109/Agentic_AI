"""
Hackathon · Part 4: Reader agent -> Writer agent
Scan the last 24 hours, let the reader sort the emails, then let the writer draft a reply for
every email that needs action. The reader passes its reasoning to the writer as context.

Nothing is ever sent. Replies can only be saved as Gmail DRAFTS.

TERMINAL USAGE (keep the part2/part3 files and gmail_client.py in the same folder):
  python part4_email_assistant.py --demo     # sample emails, no Gmail needed, replies printed
  python part4_email_assistant.py            # your real inbox (last 24 hours), replies printed
The web page (part4_email_assistant_web.py) is the main way to use this.
"""

import os
import sys
import threading

import part3_email_reader_agent as reader
from part2_email_writer_agent import write_reply

_LOCK = threading.Lock()
_SCAN: dict = {}  # last scan, kept on the server so the browser only sends ids and notes


class ScanExpired(Exception):
    """The email is not in the last scan (the server restarted, or you have not scanned yet)."""


def scan(demo: bool = False) -> list:
    """Fetch the last 24 hours, let the reader sort them, and remember the full emails."""
    emails = reader.fetch_emails(demo)
    triaged = reader.triage_emails(emails) if emails else []
    by_id = {m["id"]: m for m in emails}
    with _LOCK:
        _SCAN.clear()
        for t in triaged:
            _SCAN[t["id"]] = {"email": by_id[t["id"]], "reason": t["reason"], "demo": demo}
    return triaged


def _entry(msg_id: str) -> dict:
    with _LOCK:
        entry = _SCAN.get(msg_id)
    if not entry:
        raise ScanExpired("This email is not in the last scan. Please scan again.")
    return entry


def write_for(msg_id: str, note: str = "", manual: bool = False) -> str:
    """Writer agent drafts a reply, with the reader's reasoning passed along as context.

    note   : the user's decision (yes / no / a time). Empty means a [placeholder] is left.
    manual : the user moved this email into 'needs action' themselves, so the reader's
             reason (which said no action) is replaced by a neutral line.
    """
    entry = _entry(msg_id)
    mail = entry["email"]
    if manual:
        context = "The user marked this email as one that needs a reply."
    else:
        context = f"The inbox reader flagged this email as needing action. Reader's reason: {entry['reason']}"
    email_text = (
        f"From: {mail.get('from', '')}\n"
        f"Subject: {mail.get('subject', '')}\n\n"
        f"{mail.get('body', '')}"
    )
    return write_reply(email_text, note, reader_context=context)


def save_draft(msg_id: str, reply: str) -> str:
    """Save the reply as a Gmail draft in the original email's thread. Returns the draft id."""
    entry = _entry(msg_id)
    if entry["demo"]:
        raise RuntimeError("Sample emails are not in your Gmail, so there is nothing to attach a draft to. "
                           "Use Copy instead.")
    import gmail_client  # imported here so the demo works without Gmail set up
    return gmail_client.create_reply_draft(msg_id, reply)


def main():
    if not os.getenv("GROQ_API_KEY"):
        sys.exit("Set GROQ_API_KEY before running.")
    demo = "--demo" in sys.argv[1:]
    print("Scanning and sorting emails... this can take a little while.")
    triaged = scan(demo)
    need = [t for t in triaged if t["needs_action"]]
    print(f"{len(triaged)} email(s): {len(need)} need action, {len(triaged) - len(need)} do not.")
    for t in need:
        print(f"\n--- {t['from']} | {t['subject']}\n    reader: {t['reason']}\n")
        print(write_for(t["id"]))


if __name__ == "__main__":
    main()