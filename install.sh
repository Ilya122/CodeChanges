#!/bin/sh
# Install CodeChanges into a git repo straight from GitHub.
#
#   curl -fsSL https://raw.githubusercontent.com/Ilya122/CodeChanges/main/install.sh | sh -s -- [path/to/repo] [--no-register]
#
# Without a path it installs into the repo you are in. Run it again to update.
set -eu

URL="${CODECHANGES_TARBALL:-https://github.com/Ilya122/CodeChanges/archive/refs/heads/main.tar.gz}"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

curl -fsSL "$URL" -o "$tmp/source.tar.gz"
tar -xz -C "$tmp" --strip-components=1 -f "$tmp/source.tar.gz"
python3 "$tmp/install.py" "$@"
