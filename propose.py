"""Send a block to the CodeChange server, checking first that its patch applies.

    uv run propose.py < block.json            # new block
    uv run propose.py --revise 3 < block.json  # revise block 3
    uv run propose.py --existing < block.json  # change is already in the working tree

--existing checks the patch against the index instead, so applying the block
means committing what is already written.

The server never runs git, so the check happens here.
"""
import json
import subprocess
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:34159"


def check_patch(patch, cached=False):
    cmd = ["git", "apply", "--check", *(["--cached"] if cached else []), "-"]
    result = subprocess.run(
        cmd, input=patch, capture_output=True, text=True
    )
    if result.returncode != 0:
        sys.exit(f"patch does not apply to the working tree:\n{result.stderr.strip()}")


def main():
    args = sys.argv[1:]
    existing = "--existing" in args
    args = [a for a in args if a != "--existing"]
    url = f"{BASE}/api/blocks"
    if args[:1] == ["--revise"]:
        url += f"/{int(args[1])}/revise"
    block = json.load(sys.stdin)
    if block.get("patch"):
        check_patch(block["patch"], cached=existing)
    request = urllib.request.Request(url, json.dumps(block).encode())
    try:
        print(urllib.request.urlopen(request).read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(e.read().decode())


if __name__ == "__main__":
    main()
