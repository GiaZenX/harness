#!/usr/bin/env python3
"""
PreToolUse(Bash) — block merge/push while a source area has NO tests.

The real run shipped a frontend with 0 tests, hidden behind a high global backend
coverage number. This gate enforces the floor deterministically: every source area that
exists must have at least some tests — covered here are python (`src/`), JS/TS frontend
(`frontend/`) and C/C++ firmware (`src/`, `lib/`, `firmware/`). NOTE: other declared
stacks (go/rust/dotnet) get their test enforcement from scripts/quality.py (e.g. `go test`,
`cargo test`), not from this hook. The coverage-% threshold itself stays QA's recorded gate
(test_reports.yaml / definition_of_done); this hook only catches the "whole area untested"
failure that a global % can mask.

Only fires on `git push`/`git merge`, only when real work exists (a PRD entry). Any
uncertainty -> exit 0 (never block legitimate work).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _audit

CODE_RE = re.compile(r"\.(py|ts|tsx|js|jsx|vue|svelte)$", re.IGNORECASE)
PY_TEST_RE = re.compile(r"(^test_.*\.py$)|(.*_test\.py$)", re.IGNORECASE)
JS_TEST_RE = re.compile(r"\.(test|spec)\.(t|j)sx?$", re.IGNORECASE)
CPP_CODE_RE = re.compile(r"\.(c|cpp|cc|ino)$", re.IGNORECASE)
CPP_TEST_RE = re.compile(r"(^test_.*\.(c|cpp|cc)$)|(.*_test\.(c|cpp|cc)$)|(^test_main\.cpp$)", re.IGNORECASE)


def block(why):
    _audit.record("gate_test_coverage", why)
    sys.stderr.write(
        "[team-kit gate] Blocked merge/push: %s\n"
        "Every source area must be tested on its own (the per-area coverage rule, constitution "
        "§6). Have QA add real tests for that area before merging.\n" % why
    )
    sys.exit(2)


def has_code(root, rel_dir, name_re=CODE_RE, skip=("node_modules", "dist", "build", "__pycache__")):
    d = os.path.join(root, rel_dir)
    if not os.path.isdir(d):
        return False
    for dp, dn, fn in os.walk(d):
        dn[:] = [x for x in dn if x not in skip]
        for f in fn:
            if name_re.search(f) and not PY_TEST_RE.search(f) and not JS_TEST_RE.search(f):
                return True
    return False


def has_tests(root, dirs, test_re, skip=("node_modules", "dist", "build", "__pycache__")):
    for rel_dir in dirs:
        d = os.path.join(root, rel_dir)
        if not os.path.isdir(d):
            continue
        for dp, dn, fn in os.walk(d):
            dn[:] = [x for x in dn if x not in skip]
            for f in fn:
                if test_re.search(f):
                    return True
    return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") not in ("Bash", "PowerShell"):
        sys.exit(0)
    low = ((data.get("tool_input") or {}).get("command") or "").lower()
    if "git push" not in low and "git merge" not in low:
        sys.exit(0)

    root = find_repo_root(data.get("cwd"))
    pm = os.path.join(root, "project_memory")
    if not os.path.isdir(pm):
        sys.exit(0)
    # only gate once there is real work
    prd = os.path.join(pm, "product_requirements.yaml")
    try:
        with open(prd, encoding="utf-8", errors="ignore") as fh:
            if not re.search(r"\n\s*PRD-\d", fh.read()):
                sys.exit(0)
    except Exception:
        sys.exit(0)

    # python backend area: src/ with code -> needs tests under tests/ or src/
    if has_code(root, "src", CODE_RE) and not has_tests(root, ("tests", "src"), PY_TEST_RE):
        block("source area 'src/' has code but no tests (no test_*.py / *_test.py).")

    # frontend area: frontend/ with components -> needs *.test.* / *.spec.*
    if has_code(root, "frontend", CODE_RE) and not has_tests(root, ("frontend",), JS_TEST_RE):
        block("source area 'frontend/' has code but no UI/unit tests (no *.test.* / *.spec.*).")

    # firmware / C-C++ area: code under src/ | lib/ | firmware/ -> needs tests (PlatformIO test/ or *_test.cpp)
    if any(has_code(root, d, CPP_CODE_RE) for d in ("src", "lib", "firmware")) \
            and not has_tests(root, ("test", "tests", "src", "lib"), CPP_TEST_RE):
        block("C/C++ firmware code exists but has no tests (no test_*.c[pp] / *_test.c[pp] / PlatformIO test/).")

    sys.exit(0)


if __name__ == "__main__":
    main()
