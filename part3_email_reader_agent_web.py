"""
Hackathon · Part 3 (web version): scan the last 24 hours of email and sort it into
"needs action" and "no action".

Runs a tiny local web server (Python standard library only) on http://localhost:8080.
Only reads and classifies. It never writes replies, creates drafts, or sends anything.

USAGE (keep part2_email_writer_agent.py, part3_email_reader_agent.py and gmail_client.py
in the same folder):
  PowerShell:  $env:GROQ_API_KEY = "your-key"
  python part3_email_reader_agent_web.py
  # open http://localhost:8080
  # If the Part 2 page is still running on 8080, stop it with Ctrl-C first,
  # or use another port:  $env:PORT = "9000"
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import part3_email_reader_agent as reader

HOST = "127.0.0.1"  # local machine only
PORT = int(os.getenv("PORT", "8080"))

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Inbox Reader</title>
<style>
  :root {
    --bg: #f6f5f1; --card: #ffffff; --ink: #1f2328; --muted: #6b7280; --line: #e3e1da;
    --accent: #2f6f5e; --accent-ink: #ffffff; --warn: #b45309; --need: #b45309; --skip: #2f6f5e;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #151716; --card: #1e2120; --ink: #ecece8; --muted: #9aa09d; --line: #323634;
            --accent: #5fb89f; --accent-ink: #0f1a16; --warn: #f0a85a; --need: #f0a85a; --skip: #5fb89f; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink);
         font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  main { max-width: 1040px; margin: 0 auto; padding: 32px 16px 56px; }
  h1 { font-size: 26px; margin: 0 0 4px; letter-spacing: -0.01em; }
  .sub { color: var(--muted); margin: 0 0 20px; }
  .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  button { font: inherit; font-weight: 600; border-radius: 8px; padding: 10px 16px;
           border: 1px solid var(--line); background: var(--card); color: var(--ink); cursor: pointer; }
  button.primary { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
  button:disabled { opacity: .55; cursor: not-allowed; }
  .status { margin: 12px 0 18px; font-size: 14px; color: var(--muted); min-height: 21px; }
  .status.error { color: var(--warn); }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; }
  @media (max-width: 760px) { .grid { grid-template-columns: 1fr; } }
  .col { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px; }
  .col h2 { font-size: 16px; margin: 0 0 12px; display: flex; justify-content: space-between; }
  .col.need h2 { color: var(--need); } .col.skip h2 { color: var(--skip); }
  .email { border-top: 1px solid var(--line); padding: 12px 0; }
  .email:first-of-type { border-top: 0; padding-top: 0; }
  .subj { font-weight: 600; word-break: break-word; }
  .from { color: var(--muted); font-size: 13px; word-break: break-word; }
  .why { font-size: 14px; margin-top: 4px; }
  .tag { display: inline-block; font-size: 12px; color: var(--muted); border: 1px solid var(--line);
         border-radius: 999px; padding: 0 8px; margin-left: 6px; }
  .preview { color: var(--muted); font-size: 13px; margin-top: 4px; word-break: break-word; }
  .empty { color: var(--muted); font-size: 14px; }
</style>
</head>
<body>
<main>
  <h1>Inbox Reader</h1>
  <p class="sub">Scans emails from the last 24 hours and sorts them. It only reads. It never replies or sends anything.</p>

  <div class="row">
    <button id="scan" class="primary" type="button">Scan my last 24 hours</button>
    <button id="demo" type="button">Try with sample emails</button>
  </div>
  <div id="status" class="status" role="status"></div>

  <div class="grid">
    <section class="col need"><h2><span>Needs action from me</span><span id="needCount"></span></h2><div id="need"></div></section>
    <section class="col skip"><h2><span>No action needed</span><span id="skipCount"></span></h2><div id="skip"></div></section>
  </div>
</main>

<script>
  const $ = (id) => document.getElementById(id);
  const statusEl = $("status"), scanBtn = $("scan"), demoBtn = $("demo");

  function setStatus(msg, isError) {
    statusEl.textContent = msg || "";
    statusEl.className = "status" + (isError ? " error" : "");
  }

  // Email text is untrusted, so build the page with textContent only (never innerHTML).
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function render(items, boxId, countId) {
    const box = $(boxId);
    box.replaceChildren();
    $(countId).textContent = items.length;
    if (!items.length) { box.appendChild(el("div", "empty", "Nothing here.")); return; }
    items.forEach((t) => {
      const card = el("div", "email");
      const subj = el("div", "subj", t.subject || "(no subject)");
      if (t.category && t.category !== "Primary") subj.appendChild(el("span", "tag", t.category));
      card.appendChild(subj);
      card.appendChild(el("div", "from", t.from));
      card.appendChild(el("div", "why", t.reason));
      if (t.preview) card.appendChild(el("div", "preview", t.preview));
      box.appendChild(card);
    });
  }

  async function scan(demo) {
    scanBtn.disabled = demoBtn.disabled = true;
    setStatus(demo ? "Reading the sample emails..." :
      "Reading your inbox and sorting it... this can take up to a minute. (The first time, a Google sign-in may open.)");
    try {
      const res = await fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ demo: demo }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Something went wrong.");
      const items = data.emails;
      render(items.filter((t) => t.needs_action), "need", "needCount");
      render(items.filter((t) => !t.needs_action), "skip", "skipCount");
      setStatus(items.length ? "Done. Sorted " + items.length + " email(s)." : "No emails found in the last 24 hours.");
    } catch (e) {
      setStatus(e.message, true);
    } finally {
      scanBtn.disabled = demoBtn.disabled = false;
    }
  }

  scanBtn.addEventListener("click", () => scan(false));
  demoBtn.addEventListener("click", () => scan(true));
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
        origin = self.headers.get("Origin")
        return origin is None or origin in (f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/api/scan":
            self._json(404, {"error": "Not found"})
            return
        if not self._origin_ok():
            self._json(403, {"error": "Request blocked."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(min(length, 10_000)) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"error": "Invalid request."})
            return

        demo = bool(data.get("demo"))
        try:
            emails = reader.fetch_emails(demo)
            self._json(200, {"emails": reader.triage_emails(emails) if emails else []})
        except ImportError:
            self._json(500, {"error": "Gmail libraries are missing. Run: python -m pip install "
                                      "google-api-python-client google-auth-oauthlib google-auth-httplib2"})
        except RuntimeError as exc:
            self._json(500, {"error": str(exc)})
        except Exception as exc:
            print(f"[error] {type(exc).__name__}: {exc}", file=sys.stderr)
            self._json(500, {"error": f"Scan failed ({type(exc).__name__}). Check the terminal for details."})

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main():
    if not os.getenv("GROQ_API_KEY"):
        sys.exit("Set GROQ_API_KEY before running.")
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as exc:
        sys.exit(f"Could not start on port {PORT}: {exc}. Stop the other page or set a different PORT.")
    print(f"Open http://localhost:{PORT}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()