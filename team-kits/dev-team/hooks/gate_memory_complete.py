#!/usr/bin/env python3
"""
PreToolUse(Bash) — block merge/push while a required project_memory YAML is unfilled.

A real run left `testing_guidelines.languages: {}` empty because nothing forced filling.
This gate makes "still an empty template at acceptance" a hard FAIL — by CONTENT, not by a
marker an agent must remember to delete: a file is "unfilled" when, after dropping comments,
it is empty or holds only empty containers (`{}` / `[]` / `""` / null). An artifact that
genuinely does not apply must say so: `applicable: false` (+ reason) — then it is allowed.

Only fires on `git push`/`git merge`, only when real work exists. Stdlib only (no YAML dep).
Any uncertainty -> exit 0.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _audit

EMPTY_VALUE_RE = re.compile(r":\s*(\{\}|\[\]|\"\"|''|null|~)?\s*$")
INLINE_SCALAR_RE = re.compile(r":\s+\S")
INDENTED_RE = re.compile(r"^\s+\S")


def read(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except Exception:
        return ""


def is_unfilled(text):
    """True if the file has no real data (empty, or only empty-container keys)."""
    body = [ln for ln in text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    if not body:
        return True
    for ln in body:
        if INDENTED_RE.match(ln):
            return False  # nested data present
        if INLINE_SCALAR_RE.search(ln) and not EMPTY_VALUE_RE.search(ln):
            return False  # a real inline scalar value present
    return True


def block(files):
    _audit.record("gate_memory_complete", ", ".join(files))
    sys.stderr.write(
        "[team-kit gate] Blocked merge/push: these required project_memory files are still empty/templates:\n"
        "  %s\n"
        "Fill each with real content, or — if it genuinely does not apply to this project — set "
        "'applicable: false' with a one-line reason (constitution §6a). No required artifact may stay "
        "empty at acceptance.\n" % "\n  ".join(files)
    )
    sys.exit(2)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    low = ((data.get("tool_input") or {}).get("command") or "").lower()
    if "git push" not in low and "git merge" not in low:
        sys.exit(0)

    root = find_repo_root(data.get("cwd"))
    pm = os.path.join(root, "project_memory")
    if not os.path.isdir(pm):
        sys.exit(0)

    # only gate once there is real work (a PRD/RQ exists)
    work = False
    for f in ("product_requirements.yaml", "research_questions.yaml"):
        if re.search(r"\n\s*(PRD|RQ)-\d", read(os.path.join(pm, f))):
            work = True
            break
    if not work:
        sys.exit(0)

    stale = []
    for path in sorted(glob.glob(os.path.join(pm, "*.yaml"))):
        text = read(path)
        if re.search(r"(?m)^\s*applicable:\s*false", text):
            continue  # explicitly marked not-applicable
        if is_unfilled(text):
            stale.append(os.path.basename(path))
    if stale:
        block(stale)
    sys.exit(0)


if __name__ == "__main__":
    main()
