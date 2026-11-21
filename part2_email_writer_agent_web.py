"""
Hackathon · Parts 1 + 2 (web version)
Paste an email OR load your latest Gmail email, get a drafted reply, and save it as a Gmail draft.

Runs a tiny local web server (Python standard library only) on http://localhost:8080
and reuses the writer crew from part2_email_writer_agent.py and the Gmail helper in gmail_client.py.

USAGE (keep part2_email_writer_agent.py, part2_email_writer_agent_web.py and gmail_client.py in the same folder):
  Windows PowerShell:   $env:GROQ_API_KEY = "your-key"
  Mac/Linux:            export GROQ_API_KEY=your-key
  python part2_email_writer_agent_web.py
  # then open http://localhost:8080
  # optional: PORT=9000 python part2_email_writer_agent_web.py   (PowerShell: $env:PORT = "9000")

The Gmail buttons need the Part 2 setup (credentials.json). Pasting an email works without it.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from part2_email_writer_agent import write_reply

HOST = "127.0.0.1"  # local machine only; not reachable from other devices
PORT = int(os.getenv("PORT", "8080"))
MAX_EMAIL_CHARS = 20000

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Email Reply Writer</title>
<style>
  :root {
    --bg: #f6f5f1; --card: #ffffff; --ink: #1f2328; --muted: #6b7280;
    --line: #e3e1da; --accent: #2f6f5e; --accent-ink: #ffffff; --warn: #b45309;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #151716; --card: #1e2120; --ink: #ecece8; --muted: #9aa09d;
            --line: #323634; --accent: #5fb89f; --accent-ink: #0f1a16; --warn: #f0a85a; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink);
         font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  main { max-width: 1040px; margin: 0 auto; padding: 32px 16px 56px; }
  h1 { font-size: 26px; margin: 0 0 4px; letter-spacing: -0.01em; }
  .sub { color: var(--muted); margin: 0 0 24px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 760px) { .grid { grid-template-columns: 1fr; } }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px; }
  label { display: block; font-weight: 600; font-size: 14px; margin-bottom: 6px; }
  textarea, input[type=text] {
    width: 100%; border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px;
    font: inherit; color: var(--ink); background: var(--bg); resize: vertical; }
  textarea { min-height: 260px; }
  textarea:focus, input:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
  .hint { color: var(--muted); font-size: 13px; margin: 6px 0 14px; }
  .row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
  button { font: inherit; font-weight: 600; border-radius: 8px; padding: 10px 16px;
           border: 1px solid var(--line); background: var(--card); color: var(--ink); cursor: pointer; }
  button.primary { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
  button:disabled { opacity: .55; cursor: not-allowed; }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
  .chip { font-weight: 500; font-size: 13px; padding: 4px 10px; border-radius: 999px; }
  #reply { white-space: pre-wrap; min-height: 260px; background: var(--bg);
           border: 1px dashed var(--line); border-radius: 8px; padding: 12px; }
  #reply.empty { color: var(--muted); }
  .status { margin-top: 10px; font-size: 14px; color: var(--muted); min-height: 21px; }
  .status.error { color: var(--warn); }
  .placeholder-note { color: var(--warn); font-size: 13px; margin-top: 10px; display: none; }
  .meta { color: var(--muted); font-size: 13px; margin: 0 0 8px; min-height: 20px; word-break: break-word; }
  .topbar { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; }
  .topbar label { margin: 0; }
</style>
</head>
<body>
<main>
  <h1>Email Reply Writer</h1>
  <p class="sub">Paste an email or load your latest one, say what you want to reply, and get a draft. Nothing is ever sent automatically.</p>

  <div class="grid">
    <section class="card">
      <div class="topbar">
        <label for="email">Email you received</label>
        <button id="load" type="button">Load my latest Gmail email</button>
      </div>
      <p id="meta" class="meta"></p>
      <textarea id="email" placeholder="Paste the email body here, or click the button above..."></textarea>

      <div style="margin-top:14px">
        <label for="note">What should the reply say? <span style="font-weight:400;color:var(--muted)">(optional)</span></label>
        <input id="note" type="text" placeholder='e.g. politely decline, I have another commitment'>
        <div class="chips">
          <button class="chip" type="button" data-note="say yes, I'm in">Say yes</button>
          <button class="chip" type="button" data-note="politely decline, I have another commitment">Decline</button>
          <button class="chip" type="button" data-note="say I need to check and will confirm later">Need time</button>
        </div>
        <p class="hint">Leave this empty and the draft will contain a [YES/NO: ...] placeholder instead of deciding for you.</p>
      </div>

      <div class="row">
        <button id="go" class="primary" type="button">Write reply</button>
        <button id="clear" type="button">Clear</button>
      </div>
      <div id="status" class="status" role="status"></div>
    </section>

    <section class="card">
      <label>Draft reply</label>
      <div id="reply" class="empty">Your draft will appear here.</div>
      <div id="ph" class="placeholder-note">This draft has a placeholder in [brackets]. Fill it in before sending.</div>
      <div class="row">
        <button id="copy" type="button" disabled>Copy reply</button>
        <button id="draft" type="button" disabled title="Only available for emails loaded from Gmail">Save as Gmail draft</button>
      </div>
    </section>
  </div>
</main>

<script>
  const $ = (id) => document.getElementById(id);
  const emailEl = $("email"), noteEl = $("note"), replyEl = $("reply"), metaEl = $("meta");
  const goBtn = $("go"), copyBtn = $("copy"), loadBtn = $("load"), draftBtn = $("draft");
  const statusEl = $("status"), phEl = $("ph");
  let currentMessageId = null;  // set only when the email was loaded from Gmail
  const PLACEHOLDER = /\\[[^\\]]+\\]/;

  function setStatus(msg, isError) {
    statusEl.textContent = msg || "";
    statusEl.className = "status" + (isError ? " error" : "");
  }

  async function post(url, payload) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Something went wrong.");
    return data;
  }

  document.querySelectorAll(".chip").forEach((c) =>
    c.addEventListener("click", () => { noteEl.value = c.dataset.note; noteEl.focus(); }));

  // Editing the email by hand means it no longer matches the Gmail message.
  emailEl.addEventListener("input", () => {
    currentMessageId = null; metaEl.textContent = ""; draftBtn.disabled = true;
  });

  $("clear").addEventListener("click", () => {
    emailEl.value = ""; noteEl.value = ""; metaEl.textContent = ""; currentMessageId = null;
    replyEl.textContent = "Your draft will appear here."; replyEl.className = "empty";
    copyBtn.disabled = true; draftBtn.disabled = true; phEl.style.display = "none"; setStatus("");
  });

  copyBtn.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(replyEl.textContent); setStatus("Copied."); }
    catch (e) { setStatus("Could not copy. Select the text and copy it manually.", true); }
  });

  loadBtn.addEventListener("click", async () => {
    loadBtn.disabled = true;
    setStatus("Fetching your latest email... (the first time, a Google sign-in window may open)");
    try {
      const res = await fetch("/api/latest-email");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Could not load the email.");
      emailEl.value = data.body;
      currentMessageId = data.id;
      metaEl.textContent = "From: " + data.from + "  |  Subject: " + data.subject;
      replyEl.textContent = "Your draft will appear here."; replyEl.className = "empty";
      copyBtn.disabled = true; draftBtn.disabled = true; phEl.style.display = "none";
      setStatus("Loaded. Add a note if you want, then click Write reply.");
    } catch (e) {
      setStatus(e.message, true);
    } finally {
      loadBtn.disabled = false;
    }
  });

  goBtn.addEventListener("click", async () => {
    const email = emailEl.value.trim();
    if (!email) { setStatus("Paste an email or load one from Gmail first.", true); return; }

    goBtn.disabled = true; copyBtn.disabled = true; draftBtn.disabled = true;
    setStatus("Writing reply... this can take 5-20 seconds.");
    try {
      const data = await post("/api/reply", { email: email, note: noteEl.value.trim() });
      replyEl.textContent = data.reply; replyEl.className = "";
      phEl.style.display = PLACEHOLDER.test(data.reply) ? "block" : "none";
      copyBtn.disabled = false;
      draftBtn.disabled = !currentMessageId;
      setStatus("Done.");
    } catch (e) {
      setStatus(e.message, true);
    } finally {
      goBtn.disabled = false;
    }
  });

  draftBtn.addEventListener("click", async () => {
    const reply = replyEl.textContent;
    if (PLACEHOLDER.test(reply) &&
        !confirm("This reply still has a [placeholder]. Save it as a draft anyway?")) return;
    draftBtn.disabled = true;
    setStatus("Saving draft to Gmail...");
    try {
      await post("/api/draft", { message_id: currentMessageId, reply: reply });
      setStatus("Saved to your Gmail Drafts. Open Gmail to review and send it yourself.");
    } catch (e) {
      setStatus(e.message, true);
      draftBtn.disabled = false;
    }
  });
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def _origin_ok(self) -> bool:
        # Blocks other websites from making your browser call this local server.
        origin = self.headers.get("Origin")
        return origin is None or origin in (f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}")

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_EMAIL_CHARS * 4:
                self._json(413, {"error": "Request too large."})
                return None
            return json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"error": "Invalid request."})
            return None

    def _gmail_failure(self, exc: Exception) -> None:
        print(f"[gmail error] {type(exc).__name__}: {exc}", file=sys.stderr)
        if isinstance(exc, ImportError):
            msg = ("Gmail libraries are missing. Run: pip install google-api-python-client "
                   "google-auth-oauthlib google-auth-httplib2")
        elif isinstance(exc, RuntimeError):
            msg = str(exc)
        else:
            msg = f"Gmail request failed ({type(exc).__name__}). Check the terminal for details."
        self._json(500, {"error": msg})

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/latest-email":
            try:
                import gmail_client  # imported here so pasting still works without Gmail set up
                self._json(200, gmail_client.get_latest_email())
            except Exception as exc:
                self._gmail_failure(exc)
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path not in ("/api/reply", "/api/draft"):
            self._json(404, {"error": "Not found"})
            return
        if not self._origin_ok():
            self._json(403, {"error": "Request blocked."})
            return
        data = self._read_json()
        if data is None:
            return

        if self.path == "/api/draft":
            message_id = str(data.get("message_id", "")).strip()
            reply = str(data.get("reply", "")).strip()
            if not message_id or not reply:
                self._json(400, {"error": "Nothing to save. Load an email from Gmail and write a reply first."})
                return
            try:
                import gmail_client
                draft_id = gmail_client.create_reply_draft(message_id, reply)
                self._json(200, {"draft_id": draft_id})
            except Exception as exc:
                self._gmail_failure(exc)
            return

        email = str(data.get("email", "")).strip()
        note = str(data.get("note", "")).strip()
        if not email:
            self._json(400, {"error": "Paste an email first."})
            return
        if len(email) > MAX_EMAIL_CHARS:
            self._json(400, {"error": f"Email is too long (max {MAX_EMAIL_CHARS} characters)."})
            return

        try:
            self._json(200, {"reply": write_reply(email, note)})
        except Exception as exc:  # show the failure in the page instead of a blank error
            print(f"[error] {type(exc).__name__}: {exc}", file=sys.stderr)
            self._json(500, {"error": f"The agent failed: {type(exc).__name__}. Check the terminal for details."})

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main():
    if not os.getenv("GROQ_API_KEY"):
        sys.exit("Set GROQ_API_KEY before running.")
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as exc:
        sys.exit(f"Could not start on port {PORT}: {exc}. Try a different port with the PORT variable.")
    print(f"Open http://localhost:{PORT}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()