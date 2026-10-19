"""Install the CodeChanges extension into a git repo as <repo>/.codechanges.

    python3 install.py [path/to/repo] [--no-register]
    python3 codechanges.pyz [path/to/repo] [--no-register]   (one file, see build.py)

Nothing outside .codechanges/ is touched. The MCP server is registered with
Claude Code in local scope, which lives in your user config, not in the repo.
Run it again to update. To uninstall: delete .codechanges and run
`claude mcp remove codechanges --scope local` from the repo.
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / "app"
sys.path.insert(0, str(SOURCE))
import config  # noqa: E402


def copy_app(app):
    """Copy the app files from the .pyz archive we run from, or from the source tree."""
    archive = Path(sys.argv[0])
    if zipfile.is_zipfile(archive):
        app.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if name.startswith("app/") and name.endswith(".py"):
                    (app / Path(name).name).write_bytes(z.read(name))
    else:
        shutil.copytree(SOURCE, app, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))


def git_root(path):
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=path, capture_output=True, text=True
    )
    if result.returncode != 0:
        sys.exit(f"{path} is not inside a git repository")
    return Path(result.stdout.strip())


def main():
    args = [a for a in sys.argv[1:] if a != "--no-register"]
    register = "--no-register" not in sys.argv
    root = git_root(Path(args[0]) if args else Path.cwd())
    home = root / ".codechanges"
    app = home / "app"

    copy_app(app)
    (home / ".gitignore").write_text("*\n")
    if not (config.data_dir(root) / "config.json").exists():
        config.save_port(root, config.pick_port(root))
    run = app / "run.py"
    command = ["claude", "mcp", "add", "--scope", "local", "codechanges", "--",
               sys.executable, str(run), "mcp"]

    print(f"Installed into {home}")
    if register and shutil.which("claude"):
        subprocess.run(["claude", "mcp", "remove", "codechanges", "--scope", "local"],
                       cwd=root, capture_output=True)
        result = subprocess.run(command, cwd=root, capture_output=True, text=True)
        print("MCP server registered." if result.returncode == 0
              else f"MCP registration failed: {result.stderr.strip()}")
    else:
        print("Register the MCP server by running this from the repo:\n  " + " ".join(command))
    print(f"\nStart the review page:\n  {sys.executable} {run} serve\nthen open {config.base_url(root)}")


if __name__ == "__main__":
    main()
