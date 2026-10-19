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


def load(repo=None):
    path = data_dir(repo) / "config.json"
    return json.loads(path.read_text()) if path.exists() else {}


def save(repo=None, **updates):
    folder = data_dir(repo)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "config.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({**load(repo), **updates}) + "\n")
    tmp.replace(path)


def port(repo=None):
    env = os.environ.get("CODECHANGES_PORT")
    if env:
        return int(env)
    return load(repo).get("port", DEFAULT_PORT)


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
    save(repo, port=value)
