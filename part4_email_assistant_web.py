"""
Hackathon · Part 4 (web version): scan -> review -> write replies -> save Gmail drafts

Flow on the page:
  1. Scan the last 24 hours. The reader agent sorts emails into "needs action" / "no action".
  2. Check the sort (move any email to the other side if the reader got it wrong).
  3. Optionally type what each reply should say (yes / no / a time), then write the replies.
     The reader's reasoning is passed to the writer as context.
  4. Edit the drafts, then save them as Gmail drafts. Nothing is ever sent.

USAGE (keep part2_*, part3_*, part4_email_assistant.py and gmail_client.py in the same folder):
  PowerShell:  $env:GROQ_API_KEY = "your-key"
  python part4_email_assistant_web.py
  # open http://localhost:8080   (stop any other page on 8080 first, or set $env:PORT = "9000")
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import part4_email_assistant as assistant

HOST = "127.0.0.1"  # local machine only
PORT = int(os.getenv("PORT", "8080"))
MAX_NOTE_CHARS = 500
MAX_REPLY_CHARS = 20000

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Email Assistant</title>
<style>
  :root {
    --bg: #f6f5f1; --card: #ffffff; --ink: #1f2328; --muted: #6b7280; --line: #e3e1da;
    --accent: #2f6f5e; --accent-ink: #ffffff; --warn: #b45309;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #151716; --card: #1e2120; --ink: #ecece8; --muted: #9aa09d; --line: #323634;
            --accent: #5fb89f; --accent-ink: #0f1a16; --warn: #f0a85a; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink);
         font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  main { max-width: 860px; margin: 0 auto; padding: 32px 16px 64px; }
  h1 { font-size: 26px; margin: 0 0 4px; letter-spacing: -0.01em; }
  .sub { color: var(--muted); margin: 0 0 20px; }
  .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  button { font: inherit; font-weight: 600; border-radius: 8px; padding: 9px 14px;
           border: 1px solid var(--line); background: var(--card); color: var(--ink); cursor: pointer; }
  button.primary { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
  button.small { font-size: 13px; font-weight: 500; padding: 4px 10px; border-radius: 999px; }
  button.link { border: 0; background: none; color: var(--muted); font-weight: 500; font-size: 13px;
                padding: 2px 0; text-decoration: underline; }
  button:disabled { opacity: .55; cursor: not-allowed; }
  .status { margin: 12px 0; font-size: 14px; color: var(--muted); min-height: 21px; }
  .status.error { color: var(--warn); }
  h2 { font-size: 17px; margin: 28px 0 10px; display: flex; justify-content: space-between;
       align-items: center; gap: 8px; flex-wrap: wrap; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 12px;
          padding: 14px 16px; margin-bottom: 12px; }
  .subj { font-weight: 600; word-break: break-word; }
  .from { color: var(--muted); font-size: 13px; word-break: break-word; }
  .why { font-size: 14px; margin-top: 4px; }
  .preview { color: var(--muted); font-size: 13px; margin-top: 4px; word-break: break-word; }
  .tag { display: inline-block; font-size: 12px; color: var(--muted); border: 1px solid var(--line);
         border-radius: 999px; padding: 0 8px; margin-left: 6px; font-weight: 400; }
  .controls { margin-top: 12px; }
  input[type=text] { width: 100%; border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px;
                     font: inherit; color: var(--ink); background: var(--bg); }
  textarea { width: 100%; min-height: 150px; border: 1px solid var(--line); border-radius: 8px;
             padding: 10px 12px; font: inherit; color: var(--ink); background: var(--bg); resize: vertical; }
  input:focus, textarea:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; margin: 8px 0; }
  .replybox { margin-top: 12px; display: none; }
  .cardstatus { font-size: 13px; color: var(--muted); margin-top: 6px; min-height: 18px; }
  .cardstatus.error { color: var(--warn); }
  .empty { color: var(--muted); font-size: 14px; }
  details summary { cursor: pointer; font-weight: 600; margin: 24px 0 10px; }
</style>
</head>
<body>
<main>
  <h1>Email Assistant</h1>
  <p class="sub">Scans the last 24 hours, sorts your email, and drafts replies for the ones that need action. Nothing is ever sent. Drafts only.</p>

  <div class="row">
    <button id="scan" class="primary" type="button">Scan my last 24 hours</button>
    <button id="demo" type="button">Try with sample emails</button>
  </div>
  <div id="status" class="status" role="status"></div>

  <div id="results" style="display:none">
    <h2>
      <span>Needs action from me <span id="needCount" class="tag"></span></span>
      <span class="row">
        <button id="writeAll" type="button">Write all replies</button>
        <button id="saveAll" type="button" disabled>Save all as Gmail drafts</button>
      </span>
    </h2>
    <div id="need"></div>

    <details>
      <summary>No action needed <span id="skipCount" class="tag"></span></summary>
      <div id="skip"></div>
    </details>
  </div>
</main>

<script>
  const $ = (id) => document.getElementById(id);
  const statusEl = $("status"), scanBtn = $("scan"), demoBtn = $("demo");
  const writeAllBtn = $("writeAll"), saveAllBtn = $("saveAll");
  const PLACEHOLDER = /\\[[^\\]]+\\]/;
  const QUICK = [["Yes", "say yes, I'm in"], ["Decline", "politely decline, I have another commitment"],
                 ["Need time", "say I need to check and will confirm later"]];
  let items = [];

  function setStatus(msg, isError) {
    statusEl.textContent = msg || "";
    statusEl.className = "status" + (isError ? " error" : "");
  }

  // Email text is untrusted, so the page is built with textContent only (never innerHTML).
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function button(label, cls, onClick) {
    const b = el("button", cls, label);
    b.type = "button";
    b.addEventListener("click", onClick);
    return b;
  }

  async function post(url, payload) {
    const res = await fetch(url, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Something went wrong.");
    return data;
  }

  function setCard(item, msg, isError) {
    item.ui.status.textContent = msg || "";
    item.ui.status.className = "cardstatus" + (isError ? " error" : "");
  }

  function refreshSaveAll() {
    saveAllBtn.disabled = !items.some((i) => i.needs_action && i.reply && !i.saved);
  }

  function buildCard(item) {
    const ui = (item.ui = {});
    const card = el("div", "card");
    const subj = el("div", "subj", item.subject || "(no subject)");
    if (item.category && item.category !== "Primary") subj.appendChild(el("span", "tag", item.category));
    card.append(subj, el("div", "from", item.from), el("div", "why", item.reason));
    if (item.preview) card.appendChild(el("div", "preview", item.preview));

    const moveBtn = button(item.needs_action ? "Not needed" : "Needs a reply", "link", () => {
      item.needs_action = !item.needs_action;
      item.manual = true;
      render();
    });
    card.appendChild(moveBtn);

    if (item.needs_action) {
      const controls = el("div", "controls");
      const note = el("input");
      note.type = "text";
      note.placeholder = "What should the reply say? (optional) e.g. say yes, I'm in";
      note.value = item.note;
      note.addEventListener("input", () => { item.note = note.value; });
      const chips = el("div", "chips");
      QUICK.forEach(([label, text]) =>
        chips.appendChild(button(label, "small", () => { note.value = text; item.note = text; })));
      ui.write = button(item.reply ? "Rewrite reply" : "Write reply", "primary", () => writeReply(item));
      controls.append(note, chips, ui.write);
      card.appendChild(controls);

      ui.box = el("div", "replybox");
      ui.reply = el("textarea");
      ui.reply.value = item.reply;
      ui.reply.addEventListener("input", () => {
        item.reply = ui.reply.value; item.saved = false;
        ui.save.disabled = !item.reply.trim(); refreshSaveAll();
      });
      const actions = el("div", "row");
      actions.style.marginTop = "8px";
      ui.save = button(item.saved ? "Saved" : "Save as Gmail draft", "", () => saveDraft(item, false));
      ui.save.disabled = !item.reply || item.saved;
      const copy = button("Copy", "", async () => {
        try { await navigator.clipboard.writeText(item.reply); setCard(item, "Copied."); }
        catch (e) { setCard(item, "Could not copy. Select the text and copy it manually.", true); }
      });
      actions.append(ui.save, copy);
      ui.box.append(ui.reply, actions);
      if (item.reply) ui.box.style.display = "block";
      card.appendChild(ui.box);
    }
    ui.status = el("div", "cardstatus");
    card.appendChild(ui.status);
    return card;
  }

  function render() {
    const need = items.filter((i) => i.needs_action), skip = items.filter((i) => !i.needs_action);
    $("results").style.display = "block";
    $("needCount").textContent = need.length;
    $("skipCount").textContent = skip.length;
    [["need", need], ["skip", skip]].forEach(([id, list]) => {
      const box = $(id);
      box.replaceChildren();
      if (!list.length) box.appendChild(el("div", "empty", "Nothing here."));
      list.forEach((i) => box.appendChild(buildCard(i)));
    });
    writeAllBtn.disabled = !need.length;
    refreshSaveAll();
  }

  async function writeReply(item) {
    item.ui.write.disabled = true;
    setCard(item, "Writing reply... this can take 5 to 20 seconds.");
    try {
      const data = await post("/api/write", { id: item.id, note: item.note, manual: !!item.manual });
      item.reply = data.reply; item.saved = false;
      item.ui.reply.value = item.reply;
      item.ui.box.style.display = "block";
      item.ui.write.textContent = "Rewrite reply";
      item.ui.save.textContent = "Save as Gmail draft";
      item.ui.save.disabled = false;
      setCard(item, PLACEHOLDER.test(item.reply) ? "This draft has a [placeholder]. Fill it in before sending." : "");
      refreshSaveAll();
      return true;
    } catch (e) {
      setCard(item, e.message, true);
      return false;
    } finally {
      item.ui.write.disabled = false;
    }
  }

  async function saveDraft(item, skipConfirm) {
    if (!skipConfirm && PLACEHOLDER.test(item.reply) &&
        !confirm("This reply still has a [placeholder]. Save it as a draft anyway?")) return false;
    item.ui.save.disabled = true;
    setCard(item, "Saving draft to Gmail...");
    try {
      await post("/api/draft", { id: item.id, reply: item.reply });
      item.saved = true;
      item.ui.save.textContent = "Saved";
      setCard(item, "Saved to your Gmail Drafts. Review and send it from Gmail.");
      refreshSaveAll();
      return true;
    } catch (e) {
      item.ui.save.disabled = false;
      setCard(item, e.message, true);
      return false;
    }
  }

  writeAllBtn.addEventListener("click", async () => {
    const todo = items.filter((i) => i.needs_action && !i.reply);
    if (!todo.length) { setStatus("Every email that needs action already has a reply. Use Rewrite on any card to redo one."); return; }
    scanBtn.disabled = demoBtn.disabled = writeAllBtn.disabled = true;
    let failed = 0;
    for (let k = 0; k < todo.length; k++) {
      setStatus("Writing reply " + (k + 1) + " of " + todo.length + "...");
      if (!(await writeReply(todo[k]))) failed++;
    }
    setStatus(failed ? "Done, but " + failed + " reply(ies) failed. See the cards for details."
                     : "All replies written. Review them, then save as drafts.", !!failed);
    scanBtn.disabled = demoBtn.disabled = writeAllBtn.disabled = false;
  });

  saveAllBtn.addEventListener("click", async () => {
    const todo = items.filter((i) => i.needs_action && i.reply && !i.saved);
    const withPh = todo.filter((i) => PLACEHOLDER.test(i.reply)).length;
    if (withPh && !confirm(withPh + " of these replies still have a [placeholder]. Save them all anyway?")) return;
    saveAllBtn.disabled = true;
    let saved = 0;
    for (let k = 0; k < todo.length; k++) {
      setStatus("Saving draft " + (k + 1) + " of " + todo.length + "...");
      if (await saveDraft(todo[k], true)) saved++;
    }
    setStatus(saved + " draft(s) saved to Gmail." + (saved < todo.length ? " Some failed. See the cards." : ""),
              saved < todo.length);
    refreshSaveAll();
  });

  async function scan(demo) {
    scanBtn.disabled = demoBtn.disabled = true;
    setStatus(demo ? "Reading the sample emails..." :
      "Reading your inbox and sorting it... this can take up to a minute. (The first time, a Google sign-in may open.)");
    try {
      const data = await post("/api/scan", { demo: demo });
      items = data.emails.map((t) => Object.assign({ note: "", reply: "", saved: false, manual: false }, t));
      if (!items.length) { $("results").style.display = "none"; setStatus("No emails found in the last 24 hours."); return; }
      render();
      setStatus("Sorted " + items.length + " email(s). Check the sort, add notes if you like, then write the replies.");
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
        # Stops other websites from making your browser call this local server.
        origin = self.headers.get("Origin")
        return origin is None or origin in (f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path not in ("/api/scan", "/api/write", "/api/draft"):
            self._json(404, {"error": "Not found"})
            return
        if not self._origin_ok():
            self._json(403, {"error": "Request blocked."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_REPLY_CHARS * 4:
                self._json(413, {"error": "Request too large."})
                return
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"error": "Invalid request."})
            return

        try:
            if self.path == "/api/scan":
                self._json(200, {"emails": assistant.scan(bool(data.get("demo")))})
            elif self.path == "/api/write":
                note = str(data.get("note", "")).strip()[:MAX_NOTE_CHARS]
                reply = assistant.write_for(str(data.get("id", "")), note, bool(data.get("manual")))
                self._json(200, {"reply": reply})
            else:
                reply = str(data.get("reply", "")).strip()
                if not reply or len(reply) > MAX_REPLY_CHARS:
                    self._json(400, {"error": "Nothing to save, or the reply is too long."})
                    return
                self._json(200, {"draft_id": assistant.save_draft(str(data.get("id", "")), reply)})
        except assistant.ScanExpired as exc:
            self._json(409, {"error": str(exc)})
        except ImportError:
            self._json(500, {"error": "Gmail libraries are missing. Run: python -m pip install "
                                      "google-api-python-client google-auth-oauthlib google-auth-httplib2"})
        except RuntimeError as exc:
            self._json(500, {"error": str(exc)})
        except Exception as exc:  # show the failure on the page instead of a blank error
            print(f"[error] {type(exc).__name__}: {exc}", file=sys.stderr)
            self._json(500, {"error": f"Something failed ({type(exc).__name__}). Check the terminal for details."})

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