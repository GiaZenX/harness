#!/usr/bin/env python3
"""
PreToolUse(Bash) — block merge/push while a required project_memory YAML is unfilled.

A real run left `testing_guidelines.languages: {}` empty because nothing forced filling.
This gate makes "still an empty template at acceptance" a hard FAIL — by CONTENT, not by a
marker an agent must remember to delete: a file is "unfilled" when, after dropping comments,
it is empty or holds only empty containers (`{}` / `[]` / `""` / null). An artifact that
genuinely does not apply must say so: `applicable: false` (+ reason) — then it is allowed.
project_config.yaml is special-cased: it has real scalars (preset/repo_mode) so the generic
check sees it as filled — we additionally require a non-empty project name and, if it lists
`stacks:`, at least one real (non-TODO) stack, so an unnamed/undeclared config can't slip through.

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
from _compat import wants_push_or_merge
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


CONFIG_NAME_RE = re.compile(r"(?m)^\s*name:\s*(.*)$")
CONFIG_STACKS_INLINE_RE = re.compile(r"(?m)^\s*stacks:\s*\[([^\]]*)\]")
CONFIG_STACKS_BLOCK_RE = re.compile(r"(?m)^[ \t]*stacks:[ \t]*$")
CONFIG_STACK_ITEM_RE = re.compile(r"[ \t]*-[ \t]*([A-Za-z0-9_+-]+)[ \t]*$")


def config_unfilled(text):
    """project_config.yaml needs a real project name and, if it lists stacks, >=1 non-TODO stack.

    Real inline scalars (preset/repo_mode) make is_unfilled() treat it as 'filled', so a config with
    name:"" and stacks:[TODO] would otherwise slip through. This closes that loophole.
    """
    m = CONFIG_NAME_RE.search(text)
    name = (m.group(1).split("#", 1)[0].strip().strip("'\"") if m else "")
    if not name:
        return True
    if re.search(r"(?m)^\s*stacks:", text):  # only enforce stacks when the key is present
        stacks = []
        mi = CONFIG_STACKS_INLINE_RE.search(text)
        if mi:
            stacks = [s.strip().strip("'\"").lower() for s in mi.group(1).split(",") if s.strip()]
        else:
            mb = CONFIG_STACKS_BLOCK_RE.search(text)
            if mb:
                for line in text[mb.end():].splitlines():
                    mm = CONFIG_STACK_ITEM_RE.match(line)
                    if mm:
                        stacks.append(mm.group(1).lower())
                    elif line.strip():
                        break
        if not [s for s in stacks if s != "todo"]:
            return True
    return False


def _repeat_count(root, files):
    """How often this gate already blocked for the SAME file set (audit log) — a real night
    produced ~14 identical blocks without anyone being told to stop retrying and fix it."""
    try:
        reason = ", ".join(files)
        count = 0
        log = os.path.join(root, "project_memory", ".audit", "hook_events.jsonl")
        with open(log, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                er = str(entry.get("reason") or "")
                # exact match (a shared 80-char prefix over-counted in an audit); older
                # truncated audit entries still match via prefix-of-the-truncation
                if (entry.get("hook") == "gate_memory_complete"
                        and entry.get("event") == "block"
                        and (er == reason or (len(er) >= 290 and reason.startswith(er)))):
                    count += 1
        return count
    except Exception:
        return 0


def block(root, files):
    repeats = _repeat_count(root, files)
    _audit.record("gate_memory_complete", ", ".join(files))
    escalation = ""
    if repeats >= 2:
        escalation = (
            "REPEAT BLOCK #%d for the SAME files — STOP retrying the push. Fix it NOW: task the "
            "owning role to fill the file(s) (or record 'applicable: false' + reason) in THIS "
            "cycle, before anything else.\n" % (repeats + 1)
        )
    sys.stderr.write(
        "[team-kit gate] Blocked merge/push: these required project_memory files are still empty/templates:\n"
        "  %s\n"
        "Fill each with real content, or — if it genuinely does not apply to this project — set "
        "'applicable: false' with a one-line reason (constitution §6a). No required artifact may stay "
        "empty at acceptance.\n" % "\n  ".join(files)
        + escalation
    )
    sys.exit(2)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") not in ("Bash", "PowerShell"):
        sys.exit(0)
    # Detection lives in _compat.wants_push_or_merge (single home): wrapper payloads are
    # CODE, quoted prose is not (a commit MESSAGE once re-triggered a full gate).
    if not wants_push_or_merge(((data.get("tool_input") or {}).get("command") or "")):
        sys.exit(0)

    root = find_repo_root(data.get("cwd"))
    pm = os.path.join(root, "project_memory")
    if not os.path.isdir(pm):
        sys.exit(0)

    # only gate once there is real work (an RQ exists)
    if not re.search(r"\n\s*RQ-\d", read(os.path.join(pm, "research_questions.yaml"))):
        sys.exit(0)

    stale = []
    # the masterplan (a .md, outside the *.yaml glob) must not still be the raw template once real
    # work exists — an unfilled north star means the plan lives only in chat (the observed gap).
    mp = os.path.join(pm, "masterplan.md")
    if os.path.isfile(mp) and "<project name>" in read(mp):
        stale.append("masterplan.md (still the unfilled template — write the real masterplan)")
    for path in sorted(glob.glob(os.path.join(pm, "*.yaml"))):
        text = read(path)
        if re.search(r"(?m)^\s*applicable:\s*false", text):
            continue  # explicitly marked not-applicable
        base = os.path.basename(path)
        if base == "project_config.yaml":
            if config_unfilled(text):
                stale.append(base)
            continue
        if is_unfilled(text):
            stale.append(base)
    if stale:
        block(root, stale)
    sys.exit(0)


if __name__ == "__main__":
    main()
