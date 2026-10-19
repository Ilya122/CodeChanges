"""Pack the installer and app/ into one file: dist/codechanges.pyz.

    python3 build.py
    python3 dist/codechanges.pyz /path/to/repo [--no-register]
"""
import shutil
import tempfile
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    out = ROOT / "dist" / "codechanges.pyz"
    out.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        shutil.copy(ROOT / "install.py", stage)
        shutil.copytree(ROOT / "app", stage / "app", ignore=shutil.ignore_patterns("__pycache__"))
        (stage / "__main__.py").write_text("import install\n\ninstall.main()\n")
        zipapp.create_archive(stage, out, interpreter="/usr/bin/env python3")
    print(out)


if __name__ == "__main__":
    main()
