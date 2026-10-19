"""MCP server (stdio) that lets the AI talk to the CodeChange HTTP server.

install.py registers it with Claude Code (local scope). It speaks plain JSON-RPC
over stdin/stdout, so it needs no dependencies. Like propose.py, it checks a patch with `git apply --check` before sending it; the
HTTP server itself never runs git.
"""
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

import config

PROTOCOL = "2024-11-05"

INSTRUCTIONS = """CodeChanges is connected. The user reviews your work as small decision blocks in a browser at {url}; they do not touch git, you do.

1. Before editing files or committing, propose a 'plan' block (the plan text goes in 'why') and wait for approval.
2. Propose each logical change as a 'change' block: one file, a unified diff patch (from `git diff`), a one-line title, a short 'why' and a risk. Group related hunks into one block, and put mechanical changes (lockfiles, formatting) in a single block.
3. Wait without polling: run `{python} {run} wait` as a background command. It exits when blocks are approved or need revision. Then read them with list_blocks (status 'approved,revising').
4. approved: apply the patch and commit it yourself, one commit per block, then call mark_applied with the commit hash. revising: read the user's comment and answer with revise_block. denied: leave it alone.
5. Act only on statuses the server reports. A notification that something finished is not approval."""

RISK = {"type": "string", "enum": ["low", "medium", "high"]}
TOOLS = {
    "propose_block": {
        "description": (
            "Propose a decision block for the user to apply, deny or revise. A 'change' "
            "block needs file and patch (unified diff); a 'plan' block puts its text in 'why'. "
            "The patch is checked with git apply first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "why": {"type": "string", "description": "One or two sentences of rationale (plan text for plans)."},
                "kind": {"type": "string", "enum": ["plan", "change"]},
                "file": {"type": "string"},
                "patch": {"type": "string"},
                "risk": RISK,
                "task": {"type": "string"},
                "existing": {
                    "type": "boolean",
                    "description": "The change is already in the working tree; check the patch against the index.",
                },
            },
            "required": ["title"],
        },
    },
    "list_blocks": {
        "description": "List blocks. Use status 'approved,revising' to read the user's decisions and comments.",
        "inputSchema": {
            "type": "object",
            "properties": {"status": {"type": "string"}, "task": {"type": "string"}},
        },
    },
    "revise_block": {
        "description": "Answer a 'revising' block with new title, why, patch or risk. It goes back to pending.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"}, "title": {"type": "string"}, "why": {"type": "string"},
                "patch": {"type": "string"}, "risk": RISK,
                "existing": {"type": "boolean"},
            },
            "required": ["id"],
        },
    },
    "mark_applied": {
        "description": "Report that an approved block was applied. 'commit' is required for changes, optional for plans.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer"}, "commit": {"type": "string"}},
            "required": ["id"],
        },
    },
}


def http(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{config.base_url()}{path}", data, method=method)) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(json.loads(e.read()).get("error", str(e)))
    except urllib.error.URLError:
        raise RuntimeError(f"CodeChanges server is not running at {config.base_url()}. Start it with: {sys.executable} {config.APP_DIR / 'run.py'} serve")


def check_patch(patch, existing):
    cmd = ["git", "apply", "--check", *(["--cached"] if existing else []), "-"]
    result = subprocess.run(cmd, input=patch, capture_output=True, text=True, cwd=config.repo_root())
    if result.returncode != 0:
        raise RuntimeError(f"patch does not apply:\n{result.stderr.strip()}")


def call(name, args):
    if name == "propose_block":
        existing = args.pop("existing", False)
        args.setdefault("kind", "change" if args.get("patch") else "plan")
        if args.get("patch"):
            check_patch(args["patch"], existing)
        return http("POST", "/api/blocks", args)
    if name == "list_blocks":
        return http("GET", "/api/blocks?" + urllib.parse.urlencode(args))
    if name == "revise_block":
        block_id, existing = args.pop("id"), args.pop("existing", False)
        if args.get("patch"):
            check_patch(args["patch"], existing)
        return http("POST", f"/api/blocks/{block_id}/revise", args)
    if name == "mark_applied":
        return http("POST", f"/api/blocks/{args['id']}/applied", {"commit": args.get("commit", "")})
    raise RuntimeError(f"unknown tool {name}")


def handle(msg):
    method, params = msg.get("method"), msg.get("params") or {}
    if method == "initialize":
        return {
            "protocolVersion": params.get("protocolVersion", PROTOCOL),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "codechanges", "version": "0.1.0"},
            "instructions": INSTRUCTIONS.format(
                url=config.base_url(), python=sys.executable, run=config.APP_DIR / "run.py"
            ),
        }
    if method == "tools/list":
        return {"tools": [{"name": n, **t} for n, t in TOOLS.items()]}
    if method == "tools/call":
        try:
            result = call(params["name"], dict(params.get("arguments") or {}))
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
        except (RuntimeError, KeyError) as e:
            return {"content": [{"type": "text", "text": str(e)}], "isError": True}
    if method == "ping":
        return {}
    raise LookupError(method)


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        if "id" not in msg:  # notifications get no reply
            continue
        try:
            reply = {"jsonrpc": "2.0", "id": msg["id"], "result": handle(msg)}
        except LookupError:
            reply = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "method not found"}}
        print(json.dumps(reply), flush=True)


if __name__ == "__main__":
    main()
