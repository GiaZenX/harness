#!/usr/bin/env python3
"""
quality.py — the deterministic quality pipeline (the thing the constitution promised).

Runs the real tools and FAILS (exit 1) on any hard problem, so "pipeline green" is a fact, not a
self-reported YAML string. Used three ways: by the `gate_pipeline` hook before merge/push, by the
shipped pre-commit config, and by CI. The DevOps role owns and may extend it.

Config-driven, not hardcoded to Python+JS:
  - Active stacks come from project_memory/project_config.yaml `stacks: [...]` (inline OR block list) if
    present, else they are auto-detected. A DECLARED stack with no check definition here is a FAIL (no
    silent "green empty gate" for Rust/Go/.NET/…) — DevOps must add its checks.
  - Per stack: lint, types, tests+coverage (core, hard-fail) and SAST/SCA (security).
  - Repo-wide security: secret scan + SBOM.

Policy: a CORE tool missing for an ACTIVE stack is a FAIL (the pipeline must be set up). SECURITY tools
missing are a WARN locally but are installed + enforced in CI (requirements-dev.txt + ci.yml). Findings
from any tool are a hard FAIL (with a tail of the tool's own output for debugging). No source for a stack
-> that stack is skipped (auto-detect) or fails cleanly (explicitly declared but its files are absent).

`--only <stack>` runs a single stack's checks for FAST ITERATION (no kit checks, no secret scan)
and says so loudly — it is never merge evidence; the gate_pipeline hook always runs flag-less.

Exit 0 = all green. Exit 1 = at least one hard failure. Cross-platform (uses shutil.which).
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import time

# On Windows, stdout/stderr default to the OS codepage (cp1252): a UTF-8 char (✓, box-drawing)
# inside a FAIL detail then raises UnicodeEncodeError and crashes the script BEFORE the actual
# failure reason prints — the single worst failure mode for a gate. Two live projects fixed this
# independently; force UTF-8 with a lossy fallback, never a crash.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # non-reconfigurable stream (e.g. a test harness capture) — best effort

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS, WARNS, OKS = [], [], []


def have(tool):
    return shutil.which(tool) is not None


def run(cmd, cwd=None):
    try:
        p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)


# Electron-host env vars leak into hook subprocesses (gate_pipeline runs as a child of the
# VS Code/Claude host) and from there into every npm/vite child. Real node.exe ignores them,
# but a PATH resolving to an Electron-bundled node would not — zero-cost strip, applied to
# every Node child this script spawns.
_ELECTRON_VARS = ("ELECTRON_RUN_AS_NODE", "ELECTRON_NO_ATTACH_CONSOLE")


def _clean_node_env():
    env = os.environ.copy()
    for var in _ELECTRON_VARS:
        env.pop(var, None)
    return env


def run_npm(cmd, cwd=None):
    """Node-toolchain invocations ONLY (npm/npx/vite). On Windows they are `.cmd` shims that
    `subprocess.run([...], shell=False)` cannot exec (WinError 2) even though shutil.which finds
    them — a reproduced Windows-only gap that made the previous check_node effectively dead on
    Windows hosts. shell=True with a STATIC argument list is the portable fix; POSIX unchanged.
    Python console-scripts (ruff/pytest/...) keep using plain run()."""
    try:
        p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800,
                           shell=(os.name == "nt"), env=_clean_node_env())
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)


# pip on Windows regularly drops console-script shims OUTSIDE PATH (AppData\...\Scripts) while
# the module itself imports fine — "not installed" would be a lie. Fall back to `python -m`.
_TOOL_MODULES = {"ruff": "ruff", "mypy": "mypy", "pytest": "pytest", "bandit": "bandit",
                 "pip-audit": "pip_audit"}


def tool_cmd(tool):
    """Invocation prefix for a Python console-script, or None when truly absent."""
    if have(tool):
        return [tool]
    mod = _TOOL_MODULES.get(tool)
    if mod and importlib.util.find_spec(mod) is not None:
        return [sys.executable, "-m", mod]
    return None


def has_files(rel_dir, exts, skip=("node_modules", "dist", "build", "__pycache__", ".venv", "venv", "target")):
    d = os.path.join(ROOT, rel_dir)
    if not os.path.isdir(d):
        return False
    for dp, dn, fn in os.walk(d):
        dn[:] = [x for x in dn if x not in skip]
        for f in fn:
            if os.path.splitext(f)[1].lower() in exts:
                return True
    return False


def rootfile(*names):
    return any(os.path.isfile(os.path.join(ROOT, n)) for n in names)


def coverage_threshold():
    p = os.path.join(ROOT, "project_memory", "testing_guidelines.yaml")
    try:
        m = re.search(r"(?m)^\s*threshold:\s*(\d+)", open(p, encoding="utf-8", errors="ignore").read())
        return int(m.group(1)) if m else 80
    except Exception:
        return 80


def declared_stacks():
    """Parse `stacks:` from project_config.yaml — supports inline `[a, b]` AND block (`- a`) form."""
    p = os.path.join(ROOT, "project_memory", "project_config.yaml")
    try:
        txt = open(p, encoding="utf-8", errors="ignore").read()
    except Exception:
        return []
    out = []
    m = re.search(r"(?m)^\s*stacks:\s*\[([^\]]*)\]", txt)
    if m:
        out = [s.strip().strip("'\"").lower() for s in m.group(1).split(",") if s.strip()]
    else:
        m = re.search(r"(?m)^[ \t]*stacks:[ \t]*(?:#.*)?$", txt)
        if m:
            for line in txt[m.end():].splitlines():
                # quoted items and comment lines are valid YAML inside the list — an audit
                # showed `- 'python'` silently emptying the list ("stacks: is empty" FAIL)
                mm = re.match(r"[ \t]*-[ \t]*['\"]?([A-Za-z0-9_+-]+)['\"]?[ \t]*(?:#.*)?$", line)
                if mm:
                    out.append(mm.group(1).lower())
                elif re.match(r"[ \t]*#", line):
                    continue
                elif line.strip():
                    break  # left the list block
    return [s for s in out if s != "todo"]  # the [TODO] placeholder does not count as declared


def ok(name):
    OKS.append(name)


def fail(name, detail=""):
    FAILS.append(name + ((" — " + detail) if detail else ""))


def warn(name, detail=""):
    WARNS.append(name + ((" — " + detail) if detail else ""))


def _tail(out):
    out = (out or "").strip()
    return (" :: " + out[-300:]) if out else ""


def _core(name, tool, cmd, detail):
    prefix = tool_cmd(tool) if tool in _TOOL_MODULES else ([tool] if have(tool) else None)
    if prefix is None:
        fail(name, "%s not installed — set up the dev requirements" % tool)
        return
    rc, out = run(prefix + cmd[1:])
    ok(name) if rc == 0 else fail(name, detail + _tail(out))


def _sec(name, tool, cmd, detail):
    prefix = tool_cmd(tool) if tool in _TOOL_MODULES else ([tool] if have(tool) else None)
    if prefix is None:
        warn(name, "%s not installed; runs + hard-fails in CI" % tool)
        return
    rc, out = run(prefix + cmd[1:])
    ok(name) if rc == 0 else fail(name, detail + _tail(out))


def _declared_source_areas():
    """Top-level source dirs from coding/research_guidelines `source_areas:` — the same key
    kit_checks' file budget reads, and the SAME accepted forms (inline `[a, b]` AND block
    `- a`, quoted or not; an audit caught the block-only version silently skipping an
    inline-declared area that the budget check DID scan). Dot-only names are rejected
    (audit: '..' walked the parent dir)."""
    out = []
    for name in ("coding_guidelines.yaml", "research_guidelines.yaml"):
        p = os.path.join(ROOT, "project_memory", name)
        try:
            txt = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        mi = re.search(r"(?m)^source_areas:[ \t]*\[([^\]]*)\]", txt)
        if mi:
            for item in mi.group(1).split(","):
                item = item.strip().strip("'\"")
                if re.fullmatch(r"[A-Za-z0-9_.-]+", item) and set(item) != {"."}:
                    out.append(item)
            continue
        m = re.search(r"(?m)^source_areas:[ \t]*(?:#.*)?$", txt)
        if not m:
            continue
        for line in txt[m.end():].splitlines():
            mm = re.match(r"[ \t]*-[ \t]*['\"]?([A-Za-z0-9_.-]+)['\"]?[ \t]*(?:#.*)?$", line)
            if mm and set(mm.group(1)) != {"."}:
                out.append(mm.group(1))
            elif re.match(r"[ \t]*#", line):
                continue  # a comment line inside the list must not end it
            elif line.strip():
                break
    return out


def _python_targets():
    """Explicit ruff/mypy targets instead of the repo root: linting `.` drags .claude/ and venvs
    into the verdict (a live project's PM had to forbid exactly that), and explicit paths keep CI
    runners without a ruff.toml consistent with local runs."""
    targets = []
    for d in ["src", "tests", "scripts"] + _declared_source_areas():
        if d not in targets and os.path.isdir(os.path.join(ROOT, d)):
            targets.append(d)
    return targets or ["."]


# ---------------- per-stack check definitions ----------------
def check_python():
    targets = _python_targets()
    # every SOURCE target gets type-checked, not only src/ (an audit caught a declared extra
    # area silently un-typechecked); coverage keeps the primary source dir as its base
    src_targets = [t for t in targets if t not in ("tests", "scripts")] or ["."]
    tgt = "src" if os.path.isdir(os.path.join(ROOT, "src")) else src_targets[0]
    thr = coverage_threshold()
    _core("ruff (lint)", "ruff", ["ruff", "check"] + targets, "lint errors")
    _core("mypy (types)", "mypy", ["mypy"] + src_targets, "type errors")
    if os.path.isdir(os.path.join(ROOT, "tests")) and has_files("tests", {".py"}):
        # pytest-xdist (requirements-dev) parallelizes across cores when installed — a serial suite is
        # the measured top time eater; pytest-cov combines per-worker coverage correctly.
        par = ["-n", "auto"] if importlib.util.find_spec("xdist") else []
        name = "pytest (+cov>=%d%%%s)" % (thr, ", -n auto" if par else "")
        prefix = tool_cmd("pytest")  # python -m fallback for shim-less Windows installs too
        if prefix is None:
            fail(name, "pytest not installed — set up the dev requirements")
        else:
            cov = ["-q", *par, "--cov=" + tgt, "--cov-fail-under=" + str(thr)]
            rc, out = run(prefix + cov)
            if rc != 0 and par and "unrecognized arguments" in out:
                # xdist importable in THIS interpreter but the PATH pytest lacks the plugin —
                # retry serial instead of hard-failing on a tooling mismatch (mirrors check_node)
                rc, out = run(prefix + ["-q", "--cov=" + tgt, "--cov-fail-under=" + str(thr)])
            ok(name) if rc == 0 else fail(name, "tests failed or coverage below %d%%" % thr + _tail(out))
    _sec("bandit (SAST)", "bandit", ["bandit", "-r", tgt, "-ll", "-q"], "high-severity finding")
    # audit only the project's own DECLARED dependencies, never the whole host interpreter —
    # unrelated user-site packages (e.g. a globally installed torch) caused false-red audits
    if rootfile("pyproject.toml"):
        _sec("pip-audit (SCA)", "pip-audit", ["pip-audit", ROOT], "vulnerable dependency")
    elif rootfile("requirements.txt"):
        _sec("pip-audit (SCA)", "pip-audit",
             ["pip-audit", "-r", os.path.join(ROOT, "requirements.txt")], "vulnerable dependency")
    else:
        _sec("pip-audit (SCA)", "pip-audit", ["pip-audit", "--local"], "vulnerable dependency")


def _frontend_build_with_retry(fe):
    """`npm run build` with up to 2 retries WITHOUT weakening the check (same success criterion
    every attempt: rc==0 AND dist/index.html exists). Before each retry, Vite's own cache dir
    (node_modules/.vite) is cleared — the documented fix for the "No matching HTML proxy module
    found" stale-cache failure a live project reproduced ONLY under the hook chain — plus a short
    settle. Returns (rc, output, attempts) so the report can say a retry was needed."""
    dist_index = os.path.join(fe, "dist", "index.html")
    rc, out = run_npm(["npm", "run", "-s", "build"], cwd=fe)
    if rc == 0 and os.path.isfile(dist_index):
        return rc, out, 1
    combined = out
    for attempt, settle in enumerate((3, 8), start=2):
        shutil.rmtree(os.path.join(fe, "node_modules", ".vite"), ignore_errors=True)
        time.sleep(settle)
        rc, out = run_npm(["npm", "run", "-s", "build"], cwd=fe)
        combined += "\n--- retry %d (cleared node_modules/.vite, %ds settle) ---\n" % (attempt, settle) + out
        if rc == 0 and os.path.isfile(dist_index):
            return rc, combined, attempt
    return rc, combined, 3


def check_node():
    fe = os.path.join(ROOT, "frontend")
    pkgf = os.path.join(fe, "package.json")
    if not os.path.isfile(pkgf):
        fail("frontend (node)", "declared a node/typescript stack but no frontend/package.json")
        return
    if not have("npm"):
        fail("npm toolchain", "npm not installed — set up the frontend toolchain")
        return
    pkg = open(pkgf, encoding="utf-8", errors="ignore").read()
    if '"lint"' in pkg:
        rc, out = run_npm(["npm", "run", "-s", "lint"], cwd=fe)
        ok("frontend lint") if rc == 0 else fail("frontend lint", "lint errors" + _tail(out))
    # type-check only when the project is actually TypeScript-configured
    if os.path.isfile(os.path.join(fe, "tsconfig.json")):
        rc, out = run_npm(["npx", "--no-install", "tsc", "--noEmit"], cwd=fe)
        ok("tsc (types)") if rc == 0 else fail("tsc (types)", "type errors" + _tail(out))
    # buildable-skeleton proof: the app must BUILD, not just lint/test (a lint-green frontend
    # with a red `vite build` shipped in a live project before this step existed)
    if '"build"' in pkg:
        rc, out, attempts = _frontend_build_with_retry(fe)
        note = " [needed retry %d/3]" % attempts if attempts > 1 else ""
        if rc == 0 and os.path.isfile(os.path.join(fe, "dist", "index.html")):
            ok("frontend build (vite -> dist/)" + note)
        else:
            # a WIDE tail: the real error (heap exhaustion, proxy-module line) sits further back
            # than 300 chars — a narrow tail cost a live project a full night of misdiagnosis
            wide = (out or "").strip()
            fail("frontend build (vite -> dist/)",
                 "build failed or dist/index.html missing (after %d attempts)" % attempts
                 + ((" :: " + wide[-2000:]) if wide else ""))
    else:
        fail("frontend build", "no build script — the frontend must produce a static build "
             "(a lint-green frontend with no build proof is exactly the gap this step closes)")
    if '"test"' in pkg:
        rc, out = run_npm(["npm", "run", "-s", "test", "--", "--run", "--coverage"], cwd=fe)
        if rc != 0:
            rc, out = run_npm(["npm", "run", "-s", "test"], cwd=fe)
        ok("frontend tests") if rc == 0 else fail("frontend tests", "tests failed" + _tail(out))
    else:
        fail("frontend tests", "no test script — frontend must be tested")
    rc, out = run_npm(["npm", "audit", "--audit-level=high"], cwd=fe)
    if rc != 0 and "vulnerab" in out.lower():
        fail("npm audit (SCA)", "high/critical vulnerability" + _tail(out))
    else:
        ok("npm audit (SCA)")
    # Tier 2: browser smoke against the PRODUCTION build (kit-owned module — jsdom-green tests
    # shipped two real browser bugs: crypto.randomUUID exists in jsdom/Node but throws on a
    # plain-http LAN origin). Degrades to warn when playwright/npx are absent.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import kit_browser_checks
        kit_browser_checks.browser_smoke(ROOT, ok, fail, warn)
    except ImportError:
        warn("frontend browser smoke", "scripts/kit_browser_checks.py missing — re-run the kit "
             "scaffold to restore it (kit-owned, auto-updated)")


def check_go():
    _core("go vet", "go", ["go", "vet", "./..."], "vet errors")
    _core("go test (+cover)", "go", ["go", "test", "-cover", "./..."], "tests failed")


def check_rust():
    _core("cargo clippy", "cargo", ["cargo", "clippy", "--", "-D", "warnings"], "clippy warnings")
    _core("cargo test", "cargo", ["cargo", "test"], "tests failed")


def check_dotnet():
    _core("dotnet format", "dotnet", ["dotnet", "format", "--verify-no-changes"], "format/style issues")
    _core("dotnet test", "dotnet", ["dotnet", "test"], "tests failed")


def check_embedded():
    # firmware / C-C++ — PlatformIO build + tests + static analysis; Wokwi is the simulation real-run.
    if rootfile("platformio.ini"):
        _core("pio build", "pio", ["pio", "run"], "firmware build failed")
        _core("pio test", "pio", ["pio", "test"], "unit/sim tests failed")
    else:
        fail("embedded toolchain", "declared embedded but no platformio.ini — DevOps must wire the "
             "build/test (PlatformIO) + Wokwi simulation into scripts/quality.py")
    if have("cppcheck"):
        rc, out = run(["cppcheck", "--error-exitcode=1", "--enable=warning,style", "."])
        ok("cppcheck (SAST)") if rc == 0 else fail("cppcheck (SAST)", "static analysis findings" + _tail(out))


def _has_frontend():
    return os.path.isfile(os.path.join(ROOT, "frontend", "package.json"))


STACKS = {
    "python": {"detect": lambda: has_files("src", {".py"}) or rootfile("app.py", "main.py"), "run": check_python},
    "node": {"detect": _has_frontend, "run": check_node},
    "typescript": {"detect": _has_frontend, "run": check_node},
    # architects write stack names like `typescript_react` in the guidelines — the vocabulary
    # mismatch made a live project's declared stack look "undefined" to this runner
    "typescript_react": {"detect": _has_frontend, "run": check_node},
    "react": {"detect": _has_frontend, "run": check_node},
    "go": {"detect": lambda: rootfile("go.mod"), "run": check_go},
    "rust": {"detect": lambda: rootfile("Cargo.toml"), "run": check_rust},
    "dotnet": {"detect": lambda: has_files(".", {".csproj", ".sln"}), "run": check_dotnet},
    "embedded": {"detect": lambda: rootfile("platformio.ini"), "run": check_embedded},
    "cpp": {"detect": lambda: has_files(".", {".c", ".cpp", ".ino"}), "run": check_embedded},
    "c": {"detect": lambda: has_files(".", {".c", ".h"}), "run": check_embedded},
}


def kit_checks_stage():
    """KIT-OWNED checks live in scripts/kit_checks.py — the scaffold OVERWRITES that file on every
    kit update (like the hooks), so kit-level fixes reach existing projects even when this runner
    has been customised (a real 1,241-line fork never received the kit's fixes). Extend THIS file
    for project checks; never edit kit_checks.py in the project."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import kit_checks
    except Exception as e:
        fail("kit checks", "scripts/kit_checks.py not loadable (%s) — re-run the kit scaffold to "
             "restore it (kit-owned, auto-updated)" % e)
        return
    try:
        kit_checks.run_kit_checks(ROOT, ok, fail, warn)
    except Exception as e:
        fail("kit checks", "run_kit_checks errored: %s" % e)


def secret_scan():
    if have("gitleaks"):
        rc, out = run(["gitleaks", "detect", "--no-banner", "-r", os.devnull])
        ok("gitleaks (secrets)") if rc == 0 else fail("gitleaks (secrets)", "potential secret" + _tail(out))
    else:
        warn("gitleaks (secrets)", "not installed; runs + hard-fails in CI")


def sbom():
    if have("cyclonedx-py"):
        run(["cyclonedx-py", "environment", "-o", "sbom.json"])
        ok("SBOM (sbom.json)")
    else:
        warn("SBOM", "cyclonedx-py not installed; generated in CI")


def main():
    # --only <stack>: FAST-ITERATION partial run (one stack, no kit checks/secret scan/SBOM).
    # Loudly not merge evidence — gate_pipeline always invokes this script flag-less, so the
    # full pipeline still guards every push/merge. Pairs with the PM's test-scoping ladder.
    only = None
    argv = sys.argv[1:]
    if "--only" in argv:
        idx = argv.index("--only")
        if idx + 1 >= len(argv):
            print("[quality] --only requires a stack name (e.g. --only node)")
            sys.exit(2)
        only = argv[idx + 1].lower()
        if only not in STACKS:
            print("[quality] unknown stack %r — known: %s" % (only, ", ".join(sorted(STACKS))))
            sys.exit(2)
    if only:
        print("[quality] PARTIAL RUN (--only %s) — fast iteration only, NOT merge evidence; "
              "the gate always runs the full pipeline." % only)
        try:
            STACKS[only]["run"]()
        except Exception as e:
            fail("stack '%s'" % only, "runner errored: %s" % e)
        _report(partial=only)
        return

    active = declared_stacks()
    ran = set()
    if active:
        for s in active:
            if s not in STACKS:
                fail("stack '%s'" % s, "no quality checks defined — DevOps must add them to scripts/quality.py")
                continue
            fn = STACKS[s]["run"]
            if fn in ran:
                continue  # e.g. node + typescript share one runner
            ran.add(fn)
            try:
                fn()
            except Exception as e:
                fail("stack '%s'" % s, "runner errored: %s" % e)
    else:
        detected = []
        for s, spec in STACKS.items():
            fn = spec["run"]
            if fn in ran:
                continue
            try:
                if spec["detect"]():
                    ran.add(fn)
                    detected.append(s)
                    fn()
            except Exception as e:
                fail("stack '%s'" % s, "runner errored: %s" % e)
        if detected:
            fail("stacks not declared",
                 "code detected (%s) but project_config.yaml `stacks:` is empty/TODO. The architect MUST "
                 "declare the project's stacks + domain so the gate enforces the right toolchain — "
                 "auto-detect is not a substitute (this is exactly how a critical tool gets forgotten)."
                 % ", ".join(sorted(set(detected))))
    kit_checks_stage()
    secret_scan()
    sbom()
    _report()


def _report(partial=None):
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
    if partial:
        print("[quality] partial run (--only %s) GREEN — run flag-less for merge evidence." % partial)
    else:
        print("[quality] pipeline GREEN.")
    sys.exit(0)


if __name__ == "__main__":
    main()
