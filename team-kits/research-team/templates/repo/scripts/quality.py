#!/usr/bin/env python3
"""
quality.py — the deterministic quality pipeline (the thing the constitution promised).

Runs the real tools and FAILS (exit 1) on any hard problem, so "pipeline green" is a fact, not a
self-reported YAML string. Used three ways: by the `gate_pipeline` hook before merge/push, by the
shipped pre-commit config, and by CI. The DevOps role owns and may extend it.

Hard checks (block): lint (ruff / eslint), types (mypy / tsc), tests + coverage (pytest --cov-fail-under
/ vitest --coverage) for every stack that is actually present. A stack present but its core tool missing
is a FAIL (the pipeline must be set up — that is the point). Security scanners (gitleaks, pip-audit,
npm audit) run when available and fail on findings; if a scanner is absent it warns (so the gate is not
brittle on machines without it). No code present for a stack -> that stack is skipped.

Exit 0 = all green. Exit 1 = at least one hard failure. Cross-platform (uses shutil.which).
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []
WARNS = []
OKS = []


def have(tool):
    return shutil.which(tool) is not None


def run(cmd, cwd=None):
    try:
        p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True, timeout=1800)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)


def has_files(rel_dir, exts, skip=("node_modules", "dist", "build", "__pycache__", ".venv", "venv")):
    d = os.path.join(ROOT, rel_dir)
    if not os.path.isdir(d):
        return False
    for dp, dn, fn in os.walk(d):
        dn[:] = [x for x in dn if x not in skip]
        for f in fn:
            if os.path.splitext(f)[1].lower() in exts:
                return True
    return False


def coverage_threshold():
    p = os.path.join(ROOT, "project_memory", "testing_guidelines.yaml")
    try:
        m = re.search(r"(?m)^\s*threshold:\s*(\d+)", open(p, encoding="utf-8", errors="ignore").read())
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return 80


def check(name, ok, detail=""):
    (OKS if ok else FAILS).append(name + ((" — " + detail) if detail and not ok else ""))


def warn(name, detail=""):
    WARNS.append(name + ((" — " + detail) if detail else ""))


# ---------------- Python ----------------
def python_stack():
    if not (has_files("src", {".py"}) or has_files(".", {".py"}, ) ):
        return
    py_src = has_files("src", {".py"}) or any(
        os.path.isfile(os.path.join(ROOT, f)) for f in ("app.py", "main.py")
    )
    if not py_src:
        return
    # lint
    if have("ruff"):
        rc, out = run(["ruff", "check", "."])
        check("ruff (lint)", rc == 0, "lint errors")
    else:
        check("ruff (lint)", False, "ruff not installed — set up the dev requirements")
    # types
    if have("mypy"):
        rc, out = run(["mypy", "src"] if os.path.isdir(os.path.join(ROOT, "src")) else ["mypy", "."])
        check("mypy (types)", rc == 0, "type errors")
    else:
        check("mypy (types)", False, "mypy not installed — set up the dev requirements")
    # tests + coverage
    if os.path.isdir(os.path.join(ROOT, "tests")) and has_files("tests", {".py"}):
        if have("pytest"):
            thr = coverage_threshold()
            cov_target = "src" if os.path.isdir(os.path.join(ROOT, "src")) else "."
            rc, out = run(["pytest", "-q", "--cov=" + cov_target, "--cov-fail-under=" + str(thr)])
            check("pytest (+coverage>=%d%%)" % thr, rc == 0, "tests failed or coverage below %d%%" % thr)
        else:
            check("pytest", False, "pytest not installed — set up the dev requirements")
    # security (optional)
    if have("pip-audit"):
        rc, out = run(["pip-audit", "-l"])
        if rc != 0:
            check("pip-audit (deps)", False, "vulnerable dependency")
    else:
        warn("pip-audit (deps)", "not installed; dependency audit skipped")


# ---------------- Node / TypeScript ----------------
def node_stack():
    fe = os.path.join(ROOT, "frontend")
    if not os.path.isfile(os.path.join(fe, "package.json")):
        return
    if not have("npm"):
        check("npm toolchain", False, "npm not installed — set up the frontend toolchain")
        return
    pkg = open(os.path.join(fe, "package.json"), encoding="utf-8", errors="ignore").read()
    # lint
    if '"lint"' in pkg:
        rc, out = run(["npm", "run", "-s", "lint"], cwd=fe)
        check("eslint (lint)", rc == 0, "lint errors")
    elif have("npx"):
        rc, out = run(["npx", "--no-install", "eslint", "."], cwd=fe)
        check("eslint (lint)", rc == 0, "lint errors")
    else:
        warn("eslint (lint)", "no lint script and eslint unavailable")
    # types
    rc, out = run(["npx", "--no-install", "tsc", "--noEmit"], cwd=fe)
    check("tsc (types)", rc == 0, "type errors")
    # tests + coverage
    if '"test"' in pkg:
        rc, out = run(["npm", "run", "-s", "test", "--", "--run", "--coverage"], cwd=fe)
        if rc != 0:  # retry without extra flags (jest etc.)
            rc, out = run(["npm", "run", "-s", "test"], cwd=fe)
        check("frontend tests", rc == 0, "tests failed")
    else:
        check("frontend tests", False, "no test script — frontend must be tested")
    # security (optional)
    rc, out = run(["npm", "audit", "--audit-level=high"], cwd=fe)
    if rc != 0 and "vulnerab" in out.lower():
        check("npm audit (deps)", False, "high/critical vulnerability")


# ---------------- Secrets (repo-wide, optional) ----------------
def secret_scan():
    if have("gitleaks"):
        rc, out = run(["gitleaks", "detect", "--no-banner", "-r", os.devnull])
        check("gitleaks (secrets)", rc == 0, "potential secret committed")
    else:
        warn("gitleaks (secrets)", "not installed; secret scan skipped")


def main():
    python_stack()
    node_stack()
    secret_scan()

    print("[quality] pipeline report")
    for o in OKS:
        print("  PASS  " + o)
    for w in WARNS:
        print("  warn  " + w)
    for f in FAILS:
        print("  FAIL  " + f)
    if not (OKS or FAILS):
        print("  (no source detected — nothing to check)")
    if FAILS:
        print("[quality] %d hard failure(s) — pipeline is RED." % len(FAILS))
        sys.exit(1)
    print("[quality] pipeline GREEN.")
    sys.exit(0)


if __name__ == "__main__":
    main()
