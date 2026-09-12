#!/usr/bin/env python3
"""
kit_browser_checks.py — KIT-OWNED browser smoke (Tier 2). DO NOT EDIT IN THE PROJECT.

Serves the PRODUCTION build (`vite preview` on frontend/dist) and drives a real Chromium via
Playwright: the configured mount element must render non-empty and the console must stay free of
errors. This exists because jsdom-green unit tests shipped two REAL browser bugs in a live
project (a dead send button, a white screen): jsdom/Node always have crypto.randomUUID and always
count as a secure context — the actual failure (randomUUID throwing on a plain-http LAN origin)
is only observable in a real browser against the real build.

Config (optional) as an INV item:
  scope: browser_smoke
  value:
    entry: /             # path to open on the preview server
    mount_selector: "#root"   # element that must render non-empty

THE DESIGN STANDARDS ON THE BUILT APP (C1/C2/C3, the BUILD half of FR-0077). The same page that
is already open for the mount check is measured against the three mechanically checkable design
rules, with the SAME reader the design revision is judged by (kit_design_render._PAGE_PROBE and
keyboard_path) rather than a second implementation of them:
  C1  contrast — every text node against WCAG 4.5:1 / 3:1, computed from what the browser paints;
  C2  the keyboard path — every focusable element reached by a REAL Tab press, its focus visible in
      PIXELS (two screenshots differing, not two computed styles), nothing the mouse can click that
      the keyboard cannot reach, and no positive tabindex;
  C3  reduced motion and focus-visible — the same page re-opened in a context that asks for reduced
      motion must stop animating, and the sheets must declare a :focus-visible rule at all.
Until this existed the three ran on the STAGED DESIGN REVISION only, so a build that dropped them
was caught by nothing (H139, closed by
tools/test_hooks.py::test_the_built_app_is_judged_on_c1_c2_c3_and_each_is_red_on_its_own_violation).

ONE RULE OF THE DESIGN READER IS DELIBERATELY NOT APPLIED TO THE RENDERED PAGE, and this is the
difference between a frozen revision and a build: the one-primary-action-per-view rule, because a
built app carries no data-view contract. Applying it would produce findings no project could act
on, which is the over-refusal half of the house rule.

B3 (COLOUR LITERALS, the remaining BUILD half of FR-0077) IS NOT ASKED OF THE RENDERED PAGE EITHER,
and for the reason this module carried from the start: a build legitimately serves third-party CSS
nobody wrote as tokens, so the rendered document is the wrong subject. It is asked of the
STYLESHEETS THIS PROJECT WROTE -- the walker is `kit_checks._frontend_sources`, which already
excludes vendored and minified files, and the judge is the same browser probe, because what a
colour literal is, is decided by a CSS parser and not by a table of notations (BUG-0222). What that
leaves unjudged is named rather than implied: a colour spelled in JavaScript, in a `style`
attribute of a template, or in a preprocessor source this project compiles to CSS.

Degrades honestly: playwright or npx missing -> warn locally (CI installs + enforces); missing
frontend/dist -> warn (the build step reports its own failure; never double-fail); the design
reader missing -> warn, never a silent pass. A project with no frontend/dist pays NOTHING for any
of this - the function returns before a browser is started. Product-
specific click-flows do NOT belong here — extend scripts/quality.py in the project for those.
Runtime budget: one preview boot + one page load; keep it well under the gate's hook timeout.

Every kit update OVERWRITES this file (like kit_checks.py), so fixes reach existing projects.
"""
import hashlib
import os
import socket
import subprocess
import time


def _config(root):
    """entry + mount_selector from the `browser_smoke` invariant's `value` — one reader.

    V1 read `browser_smoke:` out of `testing_guidelines.yaml`, a monolith V2 deleted and no kit
    ships a template for, so the knob was unreachable and the smoke always tested `/` and `#root`.
    It is an INV item now (`kit_checks.invariant_knob`). The regex fallback that used to stand
    beside this is gone with it: it existed for a machine without pyyaml, and without pyyaml the
    item store cannot be read at all — a second parser could only have disagreed with the first.
    """
    entry, mount = "/", "#root"
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import kit_checks
        cfg = kit_checks.invariant_knob(root, "browser_smoke")
    except Exception:
        return entry, mount
    if isinstance(cfg, dict):
        entry = str(cfg.get("entry") or entry).strip() or entry
        mount = str(cfg.get("mount_selector") or mount).strip() or mount
    return entry, mount


def _free_port():
    """A currently-free TCP port — hardcoding 4173 collided with parallel runs/leftover servers."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _terminate_process_tree(proc):
    """Windows: the Popen child is the shell/npx shim; the real `vite preview` node process is a
    GRANDCHILD that survives a plain terminate() — a live project found genuinely orphaned
    preview servers minutes after its gate runs (chronic memory pressure). taskkill /T kills the
    whole tree by PID lineage; POSIX terminate() already reaches the real process."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _file_hash(path):
    """sha256 of a file, or None when it cannot be read (the caller then says nothing)."""
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return None


def _served_index_hash(base):
    """sha256 of the index the server actually returns, or None when it cannot be fetched.

    None rather than a failure: a project with a custom entry, an auth wall or a redirect is not
    misconfigured, and this check has nothing to say about it. It speaks only when it can compare
    two concrete byte strings.
    """
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(base, timeout=5) as response:
            if response.status != 200:
                return None
            return hashlib.sha256(response.read()).hexdigest()
    except (urllib.error.URLError, OSError, ValueError):
        return None



# The three design rules this build is held to, and the name each one is reported under. Read off
# the design reader's OWN output keys rather than restated, so a rule that reader renames stops
# being reported here instead of being reported as passing.
C1 = "C1 contrast (WCAG AA)"
C2 = "C2 keyboard path"
C3 = "C3 reduced motion + focus-visible"
B3 = "B3 colour literals in this project's own stylesheets"


def _own_stylesheets(root):
    """(repo-relative path, text) for every stylesheet THIS PROJECT wrote.

    The walk is `kit_checks._frontend_sources`, not a second one: that reader already decides which
    files are browser-facing and skips the vendor trees, and a copy here would answer a different
    question than the check the same project meets in Tier 1. A minified sheet is dropped for the
    reason the API grep drops it there -- it is vendored code the project did not author, and B3 is
    a rule about authoring.

    An empty answer is a fact and not a failure: a project that keeps its colours in JavaScript or
    in a preprocessor source has no subject for this rule, and the caller says so rather than
    reporting a pass.
    """
    try:
        import sys as _sys
        _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import kit_checks
    except Exception:                                    # noqa: BLE001 — see `_design_reader`
        return []
    found = []
    for path in kit_checks._frontend_sources(root):
        name = os.path.basename(path).lower()
        if not name.endswith(".css") or name.endswith(".min.css"):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                found.append((os.path.relpath(path, root).replace("\\", "/"), handle.read()))
        except OSError:
            continue
    return sorted(found)


def own_stylesheet_literals(browser, reader, sheets, limit=12):
    """Findings for the colour literals in the stylesheets this project wrote.

    ONE BLANK PAGE PER SHEET, and that is what buys the file name in the finding: the probe reports
    a rule's selector, and a designer who is told `card` without a file has to search for it. A
    blank page also means the subject is the sheet and nothing else -- no third-party CSS the build
    serves, which is the objection that keeps this rule off the rendered page.

    `add_style_tag` rather than markup with the text pasted into it: a sheet carrying `</style>` in
    a string would otherwise end the element it was meant to fill and the rest of it would be
    judged as text.
    """
    findings = []
    for relative, text in sheets:
        page = browser.new_page()
        try:
            page.add_style_tag(content=text)
            facts = page.evaluate(reader._PAGE_PROBE, reader._probe_config())
        finally:
            page.close()
        for entry in facts["colour_literals"]:
            if len(findings) >= limit:
                findings.append("... and further colour literal(s) in this project's stylesheets")
                return findings
            findings.append(
                "colour literal in %s: `%s` in `%s`%s — the design tokens are the one place a "
                "colour is spelled; declare it as a custom property and reference it with var()"
                % (relative, entry["property"] + ": " + entry["value"], entry["where"],
                   " under @media %s" % entry["media"] if entry["media"] else ""))
    return findings


def _design_reader():
    """`kit_design_render`, or None when it is not beside this file.

    None rather than an exception: this module ships into a project that may hold an older kit, and
    a browser smoke that CRASHED on a missing sibling would take the mount check down with it. The
    caller warns, so the absence is visible instead of silent.
    """
    try:
        import sys as _sys
        _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import kit_design_render
    except Exception:                                    # noqa: BLE001 — see the docstring
        return None
    return kit_design_render


def design_standards(page, reader, open_reduced):
    """{rule: [findings]} for the three build-side design rules on an OPEN page.

    ONE probe evaluation for all three, because the probe is the cost: it walks every text node and
    every sheet of the document, and asking it three times would triple the only expensive part of
    this check. The reduced-motion context is opened ONLY when the page animates at all — a still
    build pays no second page load for a question it cannot fail.
    """
    facts = page.evaluate(reader._PAGE_PROBE, reader._probe_config())
    found = {C1: [], C2: [], C3: []}

    for entry in facts["contrast"][:12]:
        found[C1].append(
            "contrast %.2f:1 where %.1f:1 is required — %s on %s at %s (%r)"
            % (entry["ratio"], entry["need"], entry["colour"], entry["background"],
               entry["where"], entry["sample"]))
    if len(facts["contrast"]) > 12:
        found[C1].append("... and %d further text node(s) under the contrast floor"
                         % (len(facts["contrast"]) - 12))

    keyboard, _undecided = reader.keyboard_path(page, facts["focusable"])
    found[C2] += keyboard
    for entry in facts["pointer_only"][:6]:
        found[C2].append(
            "%s is clickable for the mouse (%s) and is in no tab order — the keyboard cannot reach "
            "it at all" % (entry["where"], entry["signals"]))
    for entry in facts["positive_tabindex"][:6]:
        found[C2].append(
            "%s carries tabindex=%d — a positive tabindex overrides the document order for the "
            "whole page" % (entry["where"], entry["value"]))

    if facts["focusable"] and not facts["focus_visible_rules"]:
        found[C3].append(
            "no :focus-visible rule in the sheets this run could read%s — whatever focus looks like "
            "in this build is the browser default"
            % ("" if not facts["unreadable_sheets"]
               else " (%d sheet(s) unreadable)" % len(facts["unreadable_sheets"])))
    if facts["animated"] and open_reduced is not None:
        reduced = open_reduced()
        try:
            still_moving = reduced.evaluate(reader._PAGE_PROBE, reader._probe_config())["animated"]
        finally:
            reduced.context.close()
        if still_moving:
            found[C3].append(
                "%d element(s) keep animating when the system asks for reduced motion (%s) — the "
                "@media (prefers-reduced-motion: reduce) fallback is missing or does not cover them"
                % (len(still_moving), ", ".join(still_moving[:4])))
    return found


def browser_smoke(root, ok, fail, warn):
    """Entry point for scripts/quality.py's node stage."""
    name = "frontend browser smoke (vite preview + Playwright)"
    fe = os.path.join(root, "frontend")
    if not os.path.isfile(os.path.join(fe, "dist", "index.html")):
        warn(name, "frontend/dist missing — the build step reports its own failure")
        return
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    except ImportError:
        warn(name, "playwright (Python) not installed — add it to requirements-dev.txt and run "
                   "`playwright install chromium`; CI enforces this")
        return
    import shutil as _shutil
    if not _shutil.which("npx"):
        warn(name, "npx not available — cannot start `vite preview`")
        return
    import urllib.error
    import urllib.request

    entry, mount = _config(root)
    port = _free_port()
    url = "http://localhost:%d%s" % (port, entry if entry.startswith("/") else "/" + entry)
    env = os.environ.copy()
    for var in ("ELECTRON_RUN_AS_NODE", "ELECTRON_NO_ATTACH_CONSOLE"):
        env.pop(var, None)
    proc = subprocess.Popen(
        ["npx", "--no-install", "vite", "preview", "--port", str(port), "--strict-port"],
        cwd=fe, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", shell=(os.name == "nt"), env=env)
    try:
        # probe the server ROOT, not entry: a 404 on a custom entry (HTTPError) still proves the
        # server is up — entry itself is judged by the browser below. A preview process that
        # dies immediately must fail FAST with its own output, not after 45s of silence (audit).
        base = "http://localhost:%d/" % port
        ready = False
        for _ in range(30):
            if proc.poll() is not None:
                out = (proc.stdout.read() if proc.stdout else "") or ""
                fail(name, "`vite preview` exited immediately (rc=%s)%s"
                     % (proc.returncode, (" :: " + out.strip()[-500:]) if out.strip() else ""))
                return
            try:
                urllib.request.urlopen(base, timeout=1)
                ready = True
                break
            except urllib.error.HTTPError:
                ready = True  # server responded (even 404) — it is up
                break
            except (urllib.error.URLError, OSError):
                time.sleep(0.5)
        if not ready:
            fail(name, "`vite preview` did not become ready on %s" % base)
            return

        # DELIVERY FRESHNESS (parity risk R6): what the server hands out must BE the build output.
        # A green smoke test against a stale bundle is the worst kind of pass -- it certifies code
        # that is not the code under review. The failure is silent by nature: a leftover dev server
        # on the port, a `dist/` from a previous branch, or a service worker replaying a cached
        # shell all render fine and all lie about what was tested.
        served_hash = _served_index_hash(base)
        built_hash = _file_hash(os.path.join(fe, "dist", "index.html"))
        if served_hash and built_hash and served_hash != built_hash:
            fail(name, "the server is not serving this build: index.html sha256 %s on disk vs %s "
                       "served. A pass here would certify a bundle nobody built — rebuild "
                       "(`npm run build`) and make sure no other server holds the port."
                 % (built_hash[:12], served_hash[:12]))
            return

        console_errors = []
        reader = _design_reader()
        standards = None
        own_sheets = _own_stylesheets(root)
        own_literals = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.on("console",
                        lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                page.goto(url, wait_until="networkidle", timeout=15000)
                mount_html = page.inner_html(mount)
                if reader is not None:
                    # SAME page, SAME load. The design rules are asked of the app that was just
                    # proven to mount, so a build that fails to mount is never also reported as
                    # failing three design rules it never got to render.
                    def open_reduced():
                        context = browser.new_context(reduced_motion="reduce")
                        reduced = context.new_page()
                        reduced.goto(url, wait_until="networkidle", timeout=15000)
                        return reduced

                    standards = design_standards(page, reader, open_reduced)
                    # THE SAME BROWSER, a page of its own: B3's subject is the project's stylesheet
                    # and not the document this run just served.
                    own_literals = own_stylesheet_literals(browser, reader, own_sheets)
                browser.close()
        except Exception as exc:
            # missing BROWSER BINARY is a setup gap, not a product failure: requirements-dev
            # installs the playwright PACKAGE by default, so package-yes/browser-no is every
            # fresh machine's state — keep the documented warn degradation (CI enforces).
            # Every other Playwright/browser failure stays a real gate FAIL.
            msg = str(exc)
            if "Executable doesn't exist" in msg or "playwright install" in msg:
                warn(name, "Playwright browser not installed — run `playwright install "
                           "chromium` once; CI enforces this")
            else:
                fail(name, "Playwright run errored: %s" % exc)
            return
        if not mount_html.strip():
            fail(name, "%s rendered empty — the built app did not mount" % mount)
            return
        if console_errors:
            fail(name, "browser console error(s): " + "; ".join(console_errors[:3]))
            return
        ok(name)
        if standards is None:
            warn(name + " — design standards",
                 "scripts/kit_design_render.py missing — C1/C2/C3 were not checked on this build; "
                 "re-run the kit scaffold to restore it (kit-owned, auto-updated)")
            return
        # ONE VERDICT PER RULE, and each one named: a build that breaks two of the three has to say
        # which two, or the round that fixes one reads the remaining refusal as the same finding.
        for rule in (C1, C2, C3):
            if standards[rule]:
                fail(rule, "; ".join(standards[rule][:3]))
            else:
                ok(rule)
        # B3 IS REPORTED IN THREE STATES, not two: a project whose colours never reach a stylesheet
        # of its own has no subject for this rule, and calling that a pass is the reassuring
        # direction of exactly the claim this module refuses to make elsewhere.
        if own_literals:
            fail(B3, "; ".join(own_literals[:3])
                 + ("" if len(own_literals) <= 3 else " (+%d more)" % (len(own_literals) - 3)))
        elif own_sheets:
            ok(B3)
        else:
            warn(B3, "this project wrote no stylesheet of its own that the frontend walk finds — "
                     "colours spelled in JavaScript, in a template's style attribute or in a "
                     "preprocessor source are not judged by this rule")
    finally:
        _terminate_process_tree(proc)
