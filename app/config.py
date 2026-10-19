"""Where the repo, data folder and port are. Installed copies live in <repo>/.codechanges/app."""
import json
import os
import socket
import zlib
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DEFAULT_PORT = 34159
PORT_SPAN = 100


def repo_root():
    env = os.environ.get("CODECHANGES_REPO")
    if env:
        return Path(env).resolve()
    if APP_DIR.parent.name == ".codechanges":
        return APP_DIR.parent.parent
    return Path.cwd()


def data_dir(repo=None):
    return (repo or repo_root()) / ".codechanges" / "data"


def port(repo=None):
    env = os.environ.get("CODECHANGES_PORT")
    if env:
        return int(env)
    path = data_dir(repo) / "config.json"
    if path.exists():
        return json.loads(path.read_text()).get("port", DEFAULT_PORT)
    return DEFAULT_PORT


def base_url(repo=None):
    return f"http://127.0.0.1:{port(repo)}"


def _is_free(candidate):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", candidate))
        except OSError:
            return False
    return True


def pick_port(repo):
    """A stable port per repo, so several repos can run side by side."""
    start = zlib.crc32(str(Path(repo).resolve()).encode()) % PORT_SPAN
    for i in range(PORT_SPAN):
        candidate = DEFAULT_PORT + (start + i) % PORT_SPAN
        if _is_free(candidate):
            return candidate
    raise RuntimeError(f"no free port in {DEFAULT_PORT}-{DEFAULT_PORT + PORT_SPAN - 1}")


def save_port(repo, value):
    folder = data_dir(repo)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "config.json").write_text(json.dumps({"port": value}) + "\n")
