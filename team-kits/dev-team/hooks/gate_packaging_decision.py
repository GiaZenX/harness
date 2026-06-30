#!/usr/bin/env python3
"""
PreToolUse(Bash) — block merge/push while the packaging/deployment decision is unmade.

Generalises the "Docker was forgotten" failure mode: HOW the software is built and shipped
must be a CONSCIOUS choice (even "none / library" is valid), never implicit. The architect
records it in architecture.yaml `packaging.method` (+ an ADR in decisions.yaml). This gate
blocks the merge while `packaging.method` is still TODO/empty — so a critical packaging tool
(e.g. Docker) can never be silently forgotten.

Only fires on `git push`/`git merge`, only when real work exists (a PRD entry). Any
uncertainty -> exit 0 (never block legitimate work). Stdlib only (no YAML dep).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _audit


def read(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except Exception:
        return ""


def packaging_method(text):
    """Return the packaging.method value ('' if the block/key is absent)."""
    mi = re.search(r"(?m)^packaging:\s*\{[^}]*\bmethod:\s*([^,}]+)", text)
    if mi:
        return mi.group(1).strip().strip("'\"")
    m = re.search(r"(?m)^packaging:\s*$", text)
    if not m:
        return ""
    for line in text[m.end():].splitlines():
        if line.strip() and not line[:1].isspace() and not line.lstrip().startswith("#"):
            break  # dedented to a new top-level key -> left the packaging block
        mm = re.match(r"[ \t]+method:\s*(.*)$", line)
        if mm:
            return mm.group(1).split("#", 1)[0].strip().strip("'\"")
    return ""


def block(detail):
    _audit.record("gate_packaging_decision", detail)
    sys.stderr.write(
        "[team-kit gate] Blocked merge/push: the packaging/deployment decision is unmade (%s).\n"
        "HOW the software is built + shipped must be a CONSCIOUS choice — even 'none/library' is valid, but "
        "it must be stated. Have the architect set `packaging.method` in architecture.yaml (+ an ADR in "
        "decisions.yaml). This is the deterministic guard against a critical packaging tool (e.g. Docker) "
        "being silently forgotten (constitution §6).\n" % detail
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
    # only gate once there is real work (a PRD)
    if not re.search(r"\n\s*PRD-\d", read(os.path.join(pm, "product_requirements.yaml"))):
        sys.exit(0)

    arch = os.path.join(pm, "architecture.yaml")
    if not os.path.isfile(arch):
        sys.exit(0)  # no architecture yet -> nothing to enforce
    method = packaging_method(read(arch)).upper()
    if method in ("", "TODO"):
        block("architecture.yaml `packaging.method` is still %s" % (method.lower() or "absent"))
    sys.exit(0)


if __name__ == "__main__":
    main()
