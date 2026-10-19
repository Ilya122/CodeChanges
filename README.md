# CodeChanges

A small local extension for reviewing AI-proposed code changes. The AI proposes
small decision blocks; you apply, deny or revise each one in the browser. The AI
does all the git work. Standard library only.

## Install into a repo

From GitHub, with one line (run it inside the repo, or pass its path after `--`):

    curl -fsSL https://raw.githubusercontent.com/Ilya122/CodeChanges/main/install.sh | sh

Or from a copy of this project:

    python3 install.py /path/to/repo

Or build one file and carry it anywhere, no clone needed:

    python3 build.py                       # writes dist/codechanges.pyz
    python3 codechanges.pyz /path/to/repo

This creates `/path/to/repo/.codechanges/` (git-ignored by its own `.gitignore`)
and registers the MCP server with Claude Code in local scope. Nothing else in the
repo is touched. Pass `--no-register` to skip registration and get the command to
run yourself. Run it again to update.

To uninstall, delete `.codechanges/` and run
`claude mcp remove codechanges --scope local` from the repo.

## Use

Start the review page from the repo:

    python3 .codechanges/app/run.py serve

and open the address it prints (each repo gets its own port, saved in
`.codechanges/data/config.json`). Ask Claude to make changes as usual: it proposes
a plan, then one block per change, and waits for your decisions.

`run.py` also has `mcp` (the MCP server), `wait` (block until you decide) and
`propose` (send a block without MCP).

## Decision levels

How much the AI asks before changing things. Switch it at the top of the review page,
or with `python3 .codechanges/app/run.py mode [strict|formal|minimal]`.

- **Strict** (default): every code change comes to you as a card.
- **Formal**: cards for design, database and production-affecting changes; routine code the AI does directly.
- **Minimal**: cards only for real decisions, such as forks and anything that can't be undone.

The AI controls git, so the levels are rules it follows, not something the server can force.
