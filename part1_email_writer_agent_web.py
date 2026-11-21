"""
Hackathon · Part 1 (web version): paste an email in the browser, get a drafted reply.

Runs a tiny local web server (Python standard library only, no Flask needed)
on http://localhost:8080 and reuses the writer crew from part1_writer.py.

USAGE (keep part1_writer.py in the same folder):
  export GROQ_API_KEY=gsk_...
  python part1_web.py
  # then open http://localhost:8080
  # optional: PORT=9000 python part1_web.py
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from part1_email_writer_agent import build_crew

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
</style>
</head>
<body>
<main>
  <h1>Email Reply Writer</h1>
  <p class="sub">Paste an email, say what you want to reply, and get a draft. Nothing is sent anywhere.</p>

  <div class="grid">
    <section class="card">
      <label for="email">Email you received</label>
      <textarea id="email" placeholder="Paste the email body here..."></textarea>

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
      </div>
    </section>
  </div>
</main>

<script>
  const $ = (id) => document.getElementById(id);
  const emailEl = $("email"), noteEl = $("note"), replyEl = $("reply");
  const goBtn = $("go"), copyBtn = $("copy"), statusEl = $("status"), phEl = $("ph");

  function setStatus(msg, isError) {
    statusEl.textContent = msg || "";
    statusEl.className = "status" + (isError ? " error" : "");
  }

  document.querySelectorAll(".chip").forEach((c) =>
    c.addEventListener("click", () => { noteEl.value = c.dataset.note; noteEl.focus(); }));

  $("clear").addEventListener("click", () => {
    emailEl.value = ""; noteEl.value = "";
    replyEl.textContent = "Your draft will appear here."; replyEl.className = "empty";
    copyBtn.disabled = true; phEl.style.display = "none"; setStatus("");
  });

  copyBtn.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(replyEl.textContent); setStatus("Copied."); }
    catch (e) { setStatus("Could not copy. Select the text and copy it manually.", true); }
  });

  goBtn.addEventListener("click", async () => {
    const email = emailEl.value.trim();
    if (!email) { setStatus("Paste an email first.", true); return; }

    goBtn.disabled = true; copyBtn.disabled = true;
    setStatus("Writing reply... this can take 5-20 seconds.");
    try {
      const res = await fetch("/api/reply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email, note: noteEl.value.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Something went wrong.");
      replyEl.textContent = data.reply; replyEl.className = "";
      phEl.style.display = /\\[[^\\]]+\\]/.test(data.reply) ? "block" : "none";
      copyBtn.disabled = false; setStatus("Done.");
    } catch (e) {
      setStatus(e.message, true);
    } finally {
      goBtn.disabled = false;
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

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/api/reply":
            self._json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_EMAIL_CHARS * 4:
                self._json(413, {"error": "Request too large."})
                return
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"error": "Invalid request."})
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
            result = build_crew().kickoff(inputs={"email_body": email, "user_note": note or "none"})
            self._json(200, {"reply": result.raw})
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
        sys.exit(f"Could not start on port {PORT}: {exc}. Try: PORT=9000 python part1_web.py")
    print(f"Open http://localhost:{PORT}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()