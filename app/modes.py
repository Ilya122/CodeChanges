"""Decision levels: how much the AI must ask before changing things.

    run.py mode            show the current level
    run.py mode formal     set it (strict | formal | minimal)

The server cannot stop the AI from skipping a card, since the AI controls git.
These are rules the AI is told to follow.
"""
import sys

import config

DEFAULT = "strict"

MODES = {
    "minimal": {
        "label": "Minimal",
        "summary": "Only real decisions: forks where the AI would have to guess, and anything that can't be undone.",
        "rules": (
            "Do the work directly on a branch and commit it yourself. Ask the user (with a decision "
            "block) only when: there is a real fork where you would otherwise guess (several valid "
            "approaches with different consequences, an unclear requirement, the scope growing); "
            "or a step is destructive or irreversible (deleting data or many files, dropping tables, "
            "force-pushing, rewriting history); or it touches production, secrets or security. "
            "To ask a question, use a plan block that lists the options and your recommendation."
        ),
    },
    "formal": {
        "label": "Formal",
        "summary": "Cards for design, database and production-affecting changes. Routine code the AI just does.",
        "rules": (
            "Propose a plan block first for work that spans several files. Use a decision block for: "
            "(a) design: new modules or files that change the architecture, public API changes, new or "
            "changed dependencies; (b) database: schemas, migrations, anything that modifies data; "
            "(c) anything affecting production: deploy, CI/CD, infrastructure, configuration, secrets, "
            "login and security; (d) destructive or irreversible actions. Routine code inside the existing "
            "design (small fixes, tests, docs, refactors within one module) you may do directly on a "
            "branch and commit yourself, and say what you did in your reply. If you are unsure whether "
            "something needs a decision, treat it as if it does."
        ),
    },
    "strict": {
        "label": "Strict",
        "summary": "Every code change comes to you as a card.",
        "rules": (
            "Every code change goes through a decision block. Propose a plan block first, then one "
            "change block per logical change. Do not edit files or commit anything that has not been "
            "approved."
        ),
    },
}


def current(repo=None):
    mode = config.load(repo).get("mode", DEFAULT)
    return mode if mode in MODES else DEFAULT


def set_mode(mode, repo=None):
    if mode not in MODES:
        raise ValueError(f"mode must be one of {tuple(MODES)}")
    config.save(repo, mode=mode)
    return mode


def describe(repo=None):
    mode = current(repo)
    return {"mode": mode, "summary": MODES[mode]["summary"], "rules": MODES[mode]["rules"],
            "available": list(MODES)}


def main():
    args = sys.argv[1:]
    if args:
        try:
            set_mode(args[0])
        except ValueError as e:
            sys.exit(str(e))
    mode = current()
    print(f"{mode}: {MODES[mode]['summary']}")


if __name__ == "__main__":
    main()
