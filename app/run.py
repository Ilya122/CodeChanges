"""Entry point of the CodeChanges extension.

    python3 run.py serve     review UI and API for this repo
    python3 run.py mcp       MCP server for the AI (stdio)
    python3 run.py wait      block until a block is approved or needs revision
    python3 run.py propose   send a block from stdin (fallback when MCP isn't used)
"""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

COMMANDS = {"serve": "server", "mcp": "mcp_server", "wait": "wait", "propose": "propose"}


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command not in COMMANDS:
        sys.exit(__doc__)
    sys.argv = [f"run.py {command}", *sys.argv[2:]]
    importlib.import_module(COMMANDS[command]).main()


if __name__ == "__main__":
    main()
