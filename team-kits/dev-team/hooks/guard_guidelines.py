#!/usr/bin/env python3
"""
PreToolUse(Edit|Write) — no production code in a language before its coding guidelines exist.

Closes the "code written against empty guidelines" gap deterministically and BEFORE the work
(not just at the merge gate). Lives in the code-writers' frontmatter (it must fire for the
specialist subagents, not the PM). When a specialist writes a code file under src/**/frontend/**/
backend/** (or a root code file), the language's `languages:` block in coding_guidelines.yaml MUST
already be filled — otherwise the architect has to fill it first (constitution §2.7/§12).

Uncertainty -> exit 0 (never block legitimate work: no project_memory, unknown language, tests, etc.).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root

LANG = {
    ".py": ["python"],
    ".ts": ["typescript"], ".tsx": ["typescript"],
    ".js": ["javascript", "typescript"], ".jsx": ["javascript", "typescript"], ".mjs": ["javascript", "typescript"],
    ".go": ["go"], ".rs": ["rust"], ".java": ["java"], ".rb": ["ruby"], ".php": ["php"],
    ".cs": ["csharp", "dotnet"], ".kt": ["kotlin"], ".swift": ["swift"],
}
CODE_TOP = {"src", "frontend", "backend", "lib", "server", "app", "packages", "cmd", "internal", "api", "ui", "web"}


def block(lang, rel):
    sys.stderr.write(
        "[team-kit guard] Blocked writing '%s': coding_guidelines.yaml has no `languages: %s` block yet.\n"
        "The architect MUST fill the coding guidelines for %s BEFORE code in it is written "
        "(constitution §2.7/§12). Ask the PM to task the architect, then retry.\n" % (rel, lang, lang)
    )
    sys.exit(2)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") not in ("Edit", "Write"):
        sys.exit(0)
    inp = data.get("tool_input") or {}
    path = inp.get("file_path") or inp.get("path") or ""
    if not path:
        sys.exit(0)
    langs = LANG.get(os.path.splitext(path)[1].lower())
    if not langs:
        sys.exit(0)  # not a tracked code language

    root = find_repo_root(data.get("cwd"))
    try:
        rel = os.path.relpath(path, root).replace("\\", "/").lstrip("./")
    except Exception:
        sys.exit(0)
    if rel.startswith("../"):
        sys.exit(0)
    segs = [s for s in rel.split("/") if s]
    top = segs[0] if segs else ""
    is_code = top in CODE_TOP or len(segs) == 1
    if not is_code:
        sys.exit(0)  # only gate production code areas

    cg = os.path.join(root, "project_memory", "coding_guidelines.yaml")
    if not os.path.isfile(cg):
        sys.exit(0)  # can't determine -> don't block
    try:
        text = open(cg, encoding="utf-8", errors="ignore").read()
    except Exception:
        sys.exit(0)
    # a filled language has an indented `<lang>:` key under languages: (not `languages: {}`)
    for lang in langs:
        if re.search(r"(?mi)^\s+%s:" % re.escape(lang), text):
            sys.exit(0)  # guidelines for this language exist
    block(langs[0], rel)


if __name__ == "__main__":
    main()
