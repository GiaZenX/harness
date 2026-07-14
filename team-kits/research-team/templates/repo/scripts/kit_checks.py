#!/usr/bin/env python3
"""
kit_checks.py — KIT-OWNED quality checks. DO NOT EDIT IN THE PROJECT.

Every kit update OVERWRITES this file (like the hooks), so kit-level check fixes reach existing
projects without a manual merge — a real project's 1,241-line quality.py fork never received the
kit's xdist/pitfall fixes because "diff the whole runner" was an unrealistic work order. Project-
specific checks belong in scripts/quality.py (the runner, copy-if-absent, yours to extend); it
imports this module and calls run_kit_checks().

Shipped checks:
  * project_memory yaml-lint (parse + duplicate keys + the progress.yaml contract)
  * frontend pitfalls (raw secure-context APIs; local-first external asset loads)
  * file budget (no source file beyond max_lines — the anti-monolith gate; configurable +
    exemptable with a reason in coding_guidelines.yaml `file_budget:`)
"""
import os
import re

# Browser APIs that need a SECURE CONTEXT (https / localhost) — raw use is silently dead on a
# plain-http LAN origin, and jsdom/unit tests stay green (a real run shipped a browser-dead send
# button exactly this way). Route them through ONE helper with a fallback; mark the reviewed helper
# line with a `secure-context` comment to satisfy this check. Test files (mocks/spies name these
# APIs legitimately) and comment-only lines are exempt — a real project's App.test.tsx clipboard
# MOCKS turned the gate red and forced a spy workaround (confirmed kit false positive).
SECURE_CONTEXT_APIS = ("crypto.randomUUID", "navigator.clipboard")
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")
_TEST_FILE_RX = re.compile(r"(\.test\.|\.spec\.|(^|/)(tests?|__tests__)/)", re.I)
# comment-ONLY lines (heuristic; inline code+comment lines are still scanned)
_COMMENT_LINE_RX = re.compile(r"^\s*(//|\*|/\*|#|<!--)")

# vendored/generated code is not ours to fix — a `.next/` chunk or a vendored lib containing
# crypto.randomUUID must not turn the gate red (dot-dirs, vendor dirs, *.min.* are skipped).
_SKIP_DIRS = ("node_modules", "dist", "build", "__pycache__", ".venv", "venv", "coverage",
              "target", "vendor", "third_party")

# The anti-monolith gate. Default threshold: hand-written source files stay below this many lines;
# a real App.tsx grew to 8,966 lines (+666 in one session) while its ui/ component library sat
# 100% unused — visibility flags alone demonstrably did nothing. Projects tune/exempt via
# coding_guidelines.yaml:
#   file_budget:
#     max_lines: 800            # tighten for UI-heavy projects (e.g. 500)
#     exempt:
#       - path: frontend/src/app/App.tsx
#         reason: "legacy monolith — split tracked in TSK-0181"
FILE_BUDGET_DEFAULT = 800
_BUDGET_EXTS = {".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".css", ".html", ".go", ".rs",
                ".c", ".cpp", ".h", ".cs", ".java", ".svelte", ".vue"}
_BUDGET_AREAS = ("src", "frontend", "scripts", "tests", "static", "public")


def _more(items, shown):
    """Honest truncation: a display cut to the first N hits once made a PM report 'almost green'
    to the user while 13 findings were hidden — every truncated list says exactly how many more."""
    return " (+%d more)" % (len(items) - shown) if len(items) > shown else ""


def _local_first_declared(root):
    p = os.path.join(root, "project_memory", "project_config.yaml")
    try:
        return bool(re.search(r"(?m)^\s*local_first:\s*true\b",
                              open(p, encoding="utf-8", errors="ignore").read()))
    except Exception:
        return False


def _frontend_sources(root):
    """Browser-facing sources: everything under frontend/static/public, plus .html anywhere in src/
    and js/css under a static|public|www subdir of src/ (vanilla apps served by the backend). Plain
    backend .js under src/ is deliberately excluded — Node has no secure-context restriction."""
    exts = {".js", ".mjs", ".ts", ".jsx", ".tsx", ".html", ".css", ".svelte", ".vue"}
    for rel, browser_only in (("frontend", False), ("static", False), ("public", False), ("src", True)):
        d = os.path.join(root, rel)
        if not os.path.isdir(d):
            continue
        for dp, dn, fn in os.walk(d):
            dn[:] = [x for x in dn if x not in _SKIP_DIRS and not x.startswith(".")]
            for f in fn:
                ext = os.path.splitext(f)[1].lower()
                if ext not in exts:
                    continue
                if browser_only and ext != ".html":
                    parts = os.path.relpath(dp, root).replace("\\", "/").split("/")
                    if not {"static", "public", "www"} & set(parts):
                        continue
                yield os.path.join(dp, f)


def check_frontend_pitfalls(root, ok, fail, warn):
    """Greps for what jsdom-green tests cannot catch: (a) raw secure-context-only APIs (see
    SECURE_CONTEXT_APIS above); (b) with project_config `local_first: true`, frontend RESOURCES
    loaded from an external origin (CDN fonts/scripts — a real local-first run shipped a Google-CDN
    font no gate caught). Only resource loads count (link/script/img src, css url()/@import) — a
    plain <a href> link to an external site stays legal."""
    api_hits, cdn_hits, scanned = [], [], False
    local_first = _local_first_declared(root)
    # (?:https?:)?// also catches protocol-relative loads like href="//fonts.googleapis.com/…"
    res_html = re.compile(r"<(?:link|script|img)\b[^>]*?(?:href|src)\s*=\s*[\"']((?:https?:)?//[^\"']+)", re.I)
    res_css = re.compile(r"(?:url\(\s*[\"']?|@import\s+[\"'])((?:https?:)?//[^\"')]+)", re.I)
    for path in _frontend_sources(root):
        scanned = True
        rel = os.path.relpath(path, root)
        minified = os.path.basename(path).lower().endswith((".min.js", ".min.css"))
        is_test = bool(_TEST_FILE_RX.search(rel.replace("\\", "/")))
        try:
            lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()
        except Exception:
            continue
        prev = ""
        for i, line in enumerate(lines, 1):
            # minified bundles keep API names but are vendored — only OUR code gets the API grep;
            # the local-first RESOURCE grep still applies (an external font in a .min.css is a violation)
            if not minified and not is_test and any(api in line for api in SECURE_CONTEXT_APIS):
                if ("secure-context" not in line and "secure-context" not in prev
                        and not _COMMENT_LINE_RX.match(line)):
                    api_hits.append("%s:%d" % (rel, i))
            if local_first and os.path.splitext(path)[1].lower() in (".html", ".css"):
                for rx in (res_html, res_css):
                    for m in rx.finditer(line):
                        if not any(h in m.group(1) for h in _LOCAL_HOSTS):
                            cdn_hits.append("%s:%d %s" % (rel, i, m.group(1)[:80]))
            prev = line
    if api_hits:
        fail("secure-context APIs", "raw %s used (%s%s) — silently dead on a non-secure origin "
             "(http:// over LAN); use ONE helper with a fallback and mark it `secure-context`"
             % ("/".join(SECURE_CONTEXT_APIS), "; ".join(api_hits[:5]), _more(api_hits, 5)))
    if cdn_hits:
        fail("local-first assets", "external asset load(s) in a local_first project: %s%s — bundle "
             "them locally (fonts/scripts/styles must not leave the machine)"
             % ("; ".join(cdn_hits[:5]), _more(cdn_hits, 5)))
    if scanned and not api_hits and not cdn_hits:
        ok("frontend pitfalls (secure-context%s)" % (", local-first assets" if local_first else ""))


def check_project_memory_yaml(root, ok, fail, warn):
    """Every project_memory/*.yaml must parse and carry no duplicate keys (safe_load keeps only the
    last duplicate silently); progress.yaml must additionally honor its contract. The write-time
    hook (guard_yaml_valid) catches Edit/Write immediately — this stage is the merge/CI backstop
    and the ONLY one that also sees shell-written files."""
    d = os.path.join(root, "project_memory")
    if not os.path.isdir(d):
        return
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        warn("yaml-lint (project_memory)", "pyyaml not installed; runs + hard-fails in CI")
        return

    def dup_keys(text):
        found = []
        try:
            node_root = yaml.compose(text, Loader=yaml.SafeLoader)
        except Exception:
            return found
        stack = [node_root] if node_root is not None else []
        visited = set()  # anchors/aliases make the node graph cyclic — never walk a node twice
        while stack:
            node = stack.pop()
            if id(node) in visited:
                continue
            visited.add(id(node))
            if isinstance(node, yaml.MappingNode):
                seen = set()
                for k, v in node.value:
                    if isinstance(k, yaml.ScalarNode):
                        if k.value in seen:
                            found.append("duplicate key %r line %d" % (k.value, k.start_mark.line + 1))
                        seen.add(k.value)
                    stack.append(k)
                    stack.append(v)
            elif isinstance(node, yaml.SequenceNode):
                stack.extend(node.value)
        return found

    bad = []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith((".yaml", ".yml")):
            continue
        try:
            text = open(os.path.join(d, fn), encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as e:
            bad.append("%s: %s" % (fn, str(e).splitlines()[0]))
            continue
        for msg in dup_keys(text):
            bad.append("%s: %s" % (fn, msg))
        # progress.yaml contract (same thresholds as the write-time guard_yaml_valid): the guard only
        # sees Edit/Write tool calls — a status blob written via a SHELL heredoc/script bypasses it
        # (a real PM grew a 42k-char "one-liner" exactly that way). This stage catches it at every
        # pipeline run and at merge, whatever wrote the file.
        if fn == "progress.yaml" and isinstance(data, dict):
            status = data.get("status")
            if isinstance(status, str):
                nlines = len([ln for ln in status.splitlines() if ln.strip()])
                if nlines > 3 or len(status) > 700:
                    bad.append("progress.yaml: status is %d non-empty lines / %d chars — it MUST stay "
                               "ONE line (state + concrete next action); history belongs in the "
                               "append-only log: list" % (nlines, len(status)))
            if "log" not in data:
                bad.append("progress.yaml: the append-only log: list is missing (keep `log: []` even "
                           "when empty; history goes there, never into status)")
    ok("yaml-lint (project_memory)") if not bad else fail(
        "yaml-lint (project_memory)", "; ".join(bad[:6]) + _more(bad, 6))


def _count_lines(path):
    """Physical line count WITHOUT the trailing-newline off-by-one: an exactly-800-line file with a
    final newline is 800 lines, not 801."""
    with open(path, "rb") as fh:
        data = fh.read()
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def _budget_config(root):
    """file_budget from coding_guidelines.yaml (fallback: research_guidelines.yaml — the research
    kit ships no coding_guidelines): {max_lines, exempt: [{path, reason}]}. Exemptions are
    architect-owned and REQUIRE a reason — a bare path does not count."""
    max_lines, exempt = FILE_BUDGET_DEFAULT, {}
    for name in ("coding_guidelines.yaml", "research_guidelines.yaml"):
        p = os.path.join(root, "project_memory", name)
        if not os.path.isfile(p):
            continue
        try:
            import yaml  # type: ignore[import-untyped]
            data = yaml.safe_load(open(p, encoding="utf-8", errors="ignore").read()) or {}
            cfg = data.get("file_budget") or {}
            if isinstance(cfg, dict) and cfg:
                if isinstance(cfg.get("max_lines"), int) and cfg["max_lines"] > 0:
                    max_lines = cfg["max_lines"]
                for entry in (cfg.get("exempt") or []):
                    if isinstance(entry, dict) and entry.get("path") and str(entry.get("reason") or "").strip():
                        exempt[str(entry["path"]).replace("\\", "/")] = str(entry["reason"])
                break
        except Exception:
            pass
    return max_lines, exempt


def check_file_budget(root, ok, fail, warn):
    """No hand-written source file beyond max_lines. Deterministic anti-monolith gate: split the
    file or add an architect-owned exemption WITH a reason (visible, reviewable) — never both grow
    silently. Vendored/generated/minified/dot-dirs are skipped."""
    max_lines, exempt = _budget_config(root)
    offenders, scanned = [], False
    for area in _BUDGET_AREAS:
        d = os.path.join(root, area)
        if not os.path.isdir(d):
            continue
        for dp, dn, fn in os.walk(d):
            dn[:] = [x for x in dn if x not in _SKIP_DIRS and not x.startswith(".")]
            for f in fn:
                if os.path.splitext(f)[1].lower() not in _BUDGET_EXTS:
                    continue
                if f.lower().endswith((".min.js", ".min.css")):
                    continue
                path = os.path.join(dp, f)
                rel = os.path.relpath(path, root).replace("\\", "/")
                scanned = True
                try:
                    n = _count_lines(path)
                except Exception:
                    continue
                if n > max_lines and rel not in exempt:
                    offenders.append((rel, n))
    if offenders:
        offenders.sort(key=lambda t: -t[1])
        fail("file budget (<=%d lines)" % max_lines,
             "%d file(s) over budget: %s%s — SPLIT them into modules (a real App.tsx reached 8,966 "
             "lines while its ui/ library sat unused), or add an architect-owned exemption WITH a "
             "reason under coding_guidelines.yaml `file_budget: exempt:`"
             % (len(offenders), "; ".join("%s (%d)" % o for o in offenders[:5]), _more(offenders, 5)))
    elif scanned:
        ok("file budget (<=%d lines%s)" % (max_lines, ", %d exemption(s)" % len(exempt) if exempt else ""))


# Enforcement files no agent may change inside a project (provider-NEUTRAL second line of
# defense: session hooks only exist on the CLI that ran them — a git-level check catches shell
# bypasses and other CLIs; documented real-world compromise pattern is rewriting instruction
# files outside any reviewed diff). A kit update legitimately changes them — and always changes
# .claude/kit_version in the same diff, which lifts the gate.
_ENFORCEMENT_HARD = ("AGENTS.md", "CLAUDE.md", ".claude/hooks/", ".claude/settings.json",
                     ".claude/settings.local.json", ".claude/provider_artifacts.json",
                     ".claude/team_kit_roles.txt", ".codex/", ".agents/skills/",
                     ".github/hooks/")
_ENFORCEMENT_SOFT = (".github/workflows/", "scripts/quality.py", "scripts/kit_checks.py")


def check_enforcement_diff(root, ok, fail, warn):
    """Diff the current branch against the main branch: hard-fail on enforcement-layer changes
    without a kit-version change; warn on CI/gate-file changes and deleted test files ("any
    change that weakens CI is a blocker" — the reviewer must SEE it)."""
    import subprocess
    base = ""
    for cand in ("origin/main", "main", "master"):
        try:
            r = subprocess.run(["git", "-C", root, "rev-parse", "--verify", "--quiet", cand],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                base = cand
                break
        except Exception:
            return
    if not base:
        return  # no base branch (fresh repo) — nothing to diff against

    def _rev(name):
        try:
            r = subprocess.run(["git", "-C", root, "rev-parse", name],
                               capture_output=True, text=True, timeout=10)
            return r.stdout.strip() if r.returncode == 0 else ""
        except Exception:
            return ""

    def _diff(*args):
        try:
            r = subprocess.run(["git", "-C", root, "diff", "--name-status", *args],
                               capture_output=True, text=True, timeout=30)
            return r.stdout.splitlines() if r.returncode == 0 else []
        except Exception:
            return []

    if _rev("HEAD") and _rev("HEAD") == _rev(base):
        # HEAD *is* the base branch (solo/trunk workflow): base...HEAD is empty, so a tampered
        # commit straight to main would pass silently (audit finding) — check the last commit
        # plus the working tree instead of a false green.
        lines = _diff("HEAD~1...HEAD")  # may be empty on the root commit
        scope = "last commit + working tree (HEAD is the base)"
    else:
        lines = _diff(base + "...HEAD")
        scope = "vs %s" % base
    lines += _diff("HEAD")  # uncommitted working-tree/index changes count in every mode
    changed, deleted = [], []
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0], parts[-1].replace("\\", "/")
        changed.append(path)
        if status.startswith("D"):
            deleted.append(path)
    if not changed:
        ok("enforcement diff (no changes, %s)" % scope)
        return
    kit_updated = any(p == ".claude/kit_version" for p in changed)
    hard = [p for p in changed
            if any(p == e or p.startswith(e) for e in _ENFORCEMENT_HARD)]
    if hard and not kit_updated:
        fail("enforcement diff", "enforcement-layer file(s) changed in this branch WITHOUT a kit "
             "update: %s%s — no agent (or shell command) edits hooks/settings/the constitution in "
             "a project; harness changes arrive via a kit update (which stamps .claude/kit_version "
             "in the same diff). Revert these, or run the real kit update."
             % ("; ".join(hard[:5]), _more(hard, 5)))
        return
    soft = [p for p in changed
            if any(p == e or p.startswith(e) for e in _ENFORCEMENT_SOFT)]
    dead_tests = [p for p in deleted
                  if p.startswith("tests/") or "/tests/" in p or ".test." in p or ".spec." in p]
    notes = []
    if soft and not kit_updated:
        notes.append("gate/CI file(s) changed: %s%s" % ("; ".join(soft[:4]), _more(soft, 4)))
    if dead_tests:
        notes.append("test file(s) DELETED: %s%s" % ("; ".join(dead_tests[:4]), _more(dead_tests, 4)))
    if notes:
        warn("enforcement diff", "review deliberately: %s — any change that weakens CI/tests is a "
             "blocker unless explicitly approved (log it in progress.yaml log:)" % " | ".join(notes))
    else:
        ok("enforcement diff (%s)" % scope)


def run_kit_checks(root, ok, fail, warn):
    """Entry point for scripts/quality.py — runs every kit-owned check."""
    check_project_memory_yaml(root, ok, fail, warn)
    check_frontend_pitfalls(root, ok, fail, warn)
    check_file_budget(root, ok, fail, warn)
    check_enforcement_diff(root, ok, fail, warn)
