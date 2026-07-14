#!/usr/bin/env python3
"""
PreToolUse(Edit|Write) — no production code in a language before its coding guidelines exist.

Closes the "code written against empty guidelines" gap deterministically and BEFORE the work
(not just at the merge gate). Lives in the code-writers' frontmatter (it must fire for the
specialist subagents, not the PM). When a specialist writes a code file under src/**/frontend/**/
backend/** (or a root code file), the language's `languages:` block in coding_guidelines.yaml MUST
already be filled — otherwise the architect has to fill it first (constitution §2.7/§2.7).

Uncertainty -> exit 0 (never block legitimate work: no project_memory, unknown language, tests, etc.).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _audit

# Alias TOKENS per extension. A `languages:` key satisfies the guard when ANY of its underscore/
# dash-separated tokens equals one of these aliases — so canonical keys (javascript:) match, and so
# do compound project keys like `html_vanilla_js:` (token "js"). A real run hard-coded its compound
# key into this map because the old exact-key match rejected it; token matching keeps the hook generic.
LANG = {
    ".py": ["python", "py"],
    ".ts": ["typescript", "ts"], ".tsx": ["typescript", "tsx", "ts"],
    ".js": ["javascript", "js", "ecmascript", "node", "typescript", "ts"],
    ".jsx": ["javascript", "js", "jsx", "typescript", "ts"],
    ".mjs": ["javascript", "js", "typescript", "ts"],
    ".go": ["go", "golang"], ".rs": ["rust", "rs"], ".java": ["java"], ".rb": ["ruby", "rb"],
    ".php": ["php"],
    ".cs": ["csharp", "dotnet", "cs"], ".kt": ["kotlin", "kt"], ".swift": ["swift"],
    ".c": ["c"], ".h": ["c", "cpp"], ".cpp": ["cpp", "cxx"], ".cc": ["cpp", "cc"],
    ".hpp": ["cpp", "hpp"], ".ino": ["cpp", "embedded", "arduino", "ino"],
}
CODE_TOP = {"src", "frontend", "backend", "lib", "server", "app", "packages", "cmd", "internal", "api",
            "ui", "web", "firmware", "include", "hardware"}


def block(lang, rel):
    _audit.record("guard_guidelines", rel)
    sys.stderr.write(
        "[team-kit guard] Blocked writing '%s': coding_guidelines.yaml has no `languages: %s` block yet.\n"
        "The architect MUST fill the coding guidelines for %s BEFORE code in it is written "
        "(constitution §2.7/§2.7). Ask the PM to task the architect, then retry.\n" % (rel, lang, lang)
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
    # a filled language block = a key under `languages:` whose tokens (split on non-letters) include one
    # of the language's alias tokens. `javascript:` matches, and so does `html_vanilla_js:` (token "js").
    aliases = {a.lower() for a in langs}

    def key_matches(key):
        tokens = {t for t in re.split(r"[^a-z+]+", str(key).lower()) if t}
        return bool(tokens & aliases)

    # preferred: parse and check ONLY the keys under `languages:` (a stray `node_version:` elsewhere in
    # the file must not satisfy the guard). guard_yaml_valid keeps the file parseable.
    matched = None  # None -> undetermined, use the regex fallback
    try:
        import yaml  # type: ignore[import-untyped]
        data = yaml.safe_load(text)
        if isinstance(data, dict):
            lb = data.get("languages")
            matched = (any(key_matches(k) and v for k, v in lb.items())
                       if isinstance(lb, dict) else False)
    except Exception:
        matched = None  # no pyyaml / unparsable -> fall back, never block blind
    if matched is True:
        sys.exit(0)
    if matched is False:
        block(langs[0], rel)

    # fallback (no parser available): whole-file token scan — the pre-existing looseness, still better
    # than blocking legitimate work.
    for m in re.finditer(r"(?m)^\s+([A-Za-z][\w+-]*):", text):
        if key_matches(m.group(1)):
            sys.exit(0)
    block(langs[0], rel)


if __name__ == "__main__":
    main()
