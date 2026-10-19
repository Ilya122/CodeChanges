"""Block until the user has decided something, then print those blocks as JSON.

    run.py wait [--status approved,revising] [--timeout SECONDS]

Meant to run as a background command, so the AI is woken when it exits.
Without --timeout it keeps waiting.
"""
import json
import sys
import time
import urllib.error
import urllib.request

import config


def main():
    args = sys.argv[1:]
    options = dict(zip(args[::2], args[1::2]))
    status = options.get("--status", "approved,revising")
    deadline = time.monotonic() + float(options["--timeout"]) if "--timeout" in options else None
    url = f"{config.base_url()}/api/wait?status={status}&timeout=55"
    while True:
        try:
            with urllib.request.urlopen(url, timeout=70) as r:
                blocks = json.load(r)
        except urllib.error.URLError:
            sys.exit(f"CodeChanges server is not running at {config.base_url()}")
        if blocks or (deadline and time.monotonic() >= deadline):
            print(json.dumps(blocks, indent=2))
            return


if __name__ == "__main__":
    main()
