import html
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import config
from db import Store

HOST = "127.0.0.1"
REPO = config.repo_root()
PORT = config.port(REPO)

STYLE = """
:root {
  --bg: #ffffff; --fg: #1f2328; --muted: #656d76; --border: #d0d7de;
  --panel: #f6f8fa; --add-bg: #e6ffec; --add-fg: #116329;
  --del-bg: #ffebe9; --del-fg: #82071e; --hunk-bg: #ddf4ff; --hunk-fg: #0550ae;
  --low: #1a7f37; --medium: #9a6700; --high: #cf222e;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0d1117; --fg: #e6edf3; --muted: #8d96a0; --border: #30363d;
    --panel: #161b22; --add-bg: #12261e; --add-fg: #7ee787;
    --del-bg: #2d1214; --del-fg: #ffa198; --hunk-bg: #121d2f; --hunk-fg: #79c0ff;
    --low: #3fb950; --medium: #d29922; --high: #f85149;
  }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 24px 16px; background: var(--bg); color: var(--fg);
  font: 14px/1.5 system-ui, sans-serif; }
main { max-width: 960px; margin: 0 auto; }
.strip { display: flex; gap: 16px; flex-wrap: wrap; color: var(--muted); margin-bottom: 16px; }
.strip b { color: var(--fg); }
.card { border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.card-head { padding: 14px 16px; background: var(--panel); border-bottom: 1px solid var(--border); }
.card-head h1 { font-size: 18px; margin: 0 0 4px; }
.meta-line { color: var(--muted); font: 13px ui-monospace, monospace; }
.tag { display: inline-block; padding: 0 8px; margin-left: 6px; border-radius: 999px;
  border: 1px solid currentColor; font-size: 12px; }
.tag.low { color: var(--low); } .tag.medium { color: var(--medium); } .tag.high { color: var(--high); }
.card-body { padding: 16px; }
.why { white-space: pre-wrap; margin: 0 0 16px; }
.note { padding: 8px 12px; margin-bottom: 16px; border-left: 3px solid var(--medium);
  background: var(--panel); }
.stats { font: 13px ui-monospace, monospace; margin-bottom: 6px; }
.stat-add { color: var(--add-fg); } .stat-del { color: var(--del-fg); margin-left: 6px; }
.code { overflow-x: auto; border: 1px solid var(--border); border-radius: 6px;
  font: 12px/1.45 ui-monospace, monospace; }
.code div { padding: 0 12px; white-space: pre; min-width: max-content; }
.add { background: var(--add-bg); color: var(--add-fg); }
.del { background: var(--del-bg); color: var(--del-fg); }
.hunk { background: var(--hunk-bg); color: var(--hunk-fg); }
.actions { padding: 14px 16px; border-top: 1px solid var(--border); background: var(--panel); }
textarea { width: 100%; min-height: 60px; margin-bottom: 10px; padding: 8px; resize: vertical;
  background: var(--bg); color: var(--fg); border: 1px solid var(--border); border-radius: 6px;
  font: inherit; }
button { padding: 6px 16px; margin-right: 8px; border-radius: 6px; cursor: pointer;
  border: 1px solid var(--border); background: var(--bg); color: var(--fg); font: inherit; }
button.apply { background: var(--low); border-color: var(--low); color: #fff; }
button.deny { color: var(--high); border-color: var(--high); }
kbd { font: 11px ui-monospace, monospace; opacity: .7; margin-left: 4px; }
.muted { color: var(--muted); }
"""

SCRIPT = """
const id = document.body.dataset.block;
const box = document.getElementById("comment");
async function decide(decision) {
  const comment = box.value.trim();
  if (decision === "revise" && !comment) { box.focus(); return; }
  const r = await fetch(`/api/blocks/${id}/decision`, {
    method: "POST", body: JSON.stringify({decision, comment}),
  });
  if (r.ok) location.reload(); else alert((await r.json()).error);
}
document.addEventListener("keydown", e => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.target === box) { return; }
  if (e.key === "a") decide("apply");
  else if (e.key === "d") decide("deny");
  else if (e.key === "r") { e.preventDefault(); box.focus(); }
});
box.addEventListener("keydown", e => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) decide("revise");
});
"""


def render_patch(file, patch):
    rows, added, removed, in_hunk = [], 0, 0, False
    for line in patch.splitlines():
        if line.startswith("@@"):
            in_hunk, cls = True, "hunk"
        elif not in_hunk:
            continue  # diff --git / index / --- / +++ headers
        elif line.startswith("+"):
            added, cls = added + 1, "add"
        elif line.startswith("-"):
            removed, cls = removed + 1, "del"
        else:
            cls = ""
        rows.append(f'<div class="{cls}">{html.escape(line) or " "}</div>')
    return (
        f'<div class="stats">{html.escape(file or "")}'
        f' <span class="stat-add">+{added}</span><span class="stat-del">-{removed}</span></div>'
        f'<div class="code">{"".join(rows)}</div>'
    )


def render_strip(counts):
    awaiting = counts.get("approved", 0) + counts.get("revising", 0)
    parts = [
        ("Pending", counts.get("pending", 0)),
        ("Awaiting AI", awaiting),
        ("Applied", counts.get("applied", 0)),
        ("Denied", counts.get("denied", 0)),
    ]
    return '<div class="strip">' + "".join(f"<span>{k} <b>{v}</b></span>" for k, v in parts) + "</div>"


def render_card(block, position, total):
    esc = html.escape
    revision = f'<span class="tag">rev {block["revision"]}</span>' if block["revision"] > 1 else ""
    where = "Plan" if block["kind"] == "plan" else esc(block["file"])
    note = ""
    if block["revision"] > 1 and block["comment"]:
        note = f'<div class="note"><b>Your last comment:</b> {esc(block["comment"])}</div>'
    body = f'<p class="why">{esc(block["why"])}</p>' if block["why"] else ""
    if block["kind"] == "change":
        body += render_patch(block["file"], block["patch"])
    return f"""
<div class="card">
  <div class="card-head">
    <h1>{esc(block["title"])}</h1>
    <div class="meta-line">{where} · {position} of {total}
      <span class="tag {esc(block["risk"])}">{esc(block["risk"])} risk</span>{revision}</div>
  </div>
  <div class="card-body">{note}{body}</div>
  <div class="actions">
    <textarea id="comment" placeholder="Comment (required to revise, Ctrl+Enter to send)"></textarea>
    <button class="apply" onclick="decide('apply')">Apply<kbd>a</kbd></button>
    <button onclick="decide('revise')">Revise<kbd>r</kbd></button>
    <button class="deny" onclick="decide('deny')">Deny<kbd>d</kbd></button>
  </div>
</div>"""


def render_page(store):
    pending = store.list(["pending"])
    counts = store.counts()
    total = sum(counts.values())
    if pending:
        block = pending[0]
        done = total - len(pending)
        content = render_card(block, done + 1, total)
        attr = f' data-block="{block["id"]}"'
        script = f"<script>{SCRIPT}</script>"
    else:
        msg = "Nothing to decide right now." if total else "No blocks yet. Waiting for the AI."
        content, attr, script = f'<p class="muted">{msg}</p>', "", ""
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>CodeChange</title><style>{STYLE}</style></head>"
        f"<body{attr}><main>{render_strip(counts)}{content}</main>{script}</body></html>"
    )


class Handler(BaseHTTPRequestHandler):
    store = None

    def _send(self, status, body, content_type):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status, payload):
        self._send(status, json.dumps(payload), "application/json")

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            raise ValueError("invalid JSON")
        if not isinstance(payload, dict):
            raise ValueError("body must be a JSON object")
        return payload

    def _route(self, method):
        url = urlsplit(self.path)
        parts = [p for p in url.path.split("/") if p]
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        store = self.store

        if method == "GET" and not parts:
            return self._send(200, render_page(store), "text/html")
        if parts == ["api", "wait"]:
            # long-poll: return as soon as a block in one of these statuses exists
            statuses = query.get("status", "approved,revising").split(",")
            deadline = time.monotonic() + min(float(query.get("timeout", 300)), 600)
            while True:
                found = store.list(statuses)
                if found or time.monotonic() >= deadline:
                    return self._json(200, found)
                time.sleep(0.5)
        if parts[:2] != ["api", "blocks"] and parts != ["api", "status"]:
            raise LookupError("not found")
        if parts == ["api", "status"]:
            return self._json(200, {"status": "ok", "repo": str(REPO), "counts": store.counts()})
        if len(parts) == 2:
            if method == "GET":
                statuses = query["status"].split(",") if "status" in query else None
                return self._json(200, store.list(statuses, query.get("task")))
            return self._json(201, store.create(self._body()))
        try:
            block_id = int(parts[2])
        except ValueError:
            raise ValueError("invalid block id")
        if len(parts) == 3 and method == "GET":
            return self._json(200, store.get(block_id))
        if len(parts) == 4 and method == "POST":
            action, body = parts[3], self._body()
            if action == "decision":
                result = store.decide(block_id, body.get("decision"), str(body.get("comment", "")))
            elif action == "revise":
                result = store.revise(block_id, body)
            elif action == "applied":
                result = store.mark_applied(block_id, body.get("commit", ""))
            else:
                raise LookupError("not found")
            return self._json(200, result)
        raise LookupError("not found")

    def _handle(self, method):
        try:
            self._route(method)
        except ValueError as e:
            self._json(400, {"error": str(e)})
        except LookupError as e:
            self._json(404, {"error": str(e).strip("'\"")})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


def main():
    Handler.store = Store(REPO)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Serving {REPO} on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
