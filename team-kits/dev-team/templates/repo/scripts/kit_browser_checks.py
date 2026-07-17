#!/usr/bin/env python3
"""
kit_browser_checks.py — KIT-OWNED browser smoke (Tier 2). DO NOT EDIT IN THE PROJECT.

Serves the PRODUCTION build (`vite preview` on frontend/dist) and drives a real Chromium via
Playwright: the configured mount element must render non-empty and the console must stay free of
errors. This exists because jsdom-green unit tests shipped two REAL browser bugs in a live
project (a dead send button, a white screen): jsdom/Node always have crypto.randomUUID and always
count as a secure context — the actual failure (randomUUID throwing on a plain-http LAN origin)
is only observable in a real browser against the real build.

Config (optional) in project_memory/testing_guidelines.yaml:
  browser_smoke:
    entry: /             # path to open on the preview server
    mount_selector: "#root"   # element that must render non-empty

Degrades honestly: playwright or npx missing -> warn locally (CI installs + enforces); missing
frontend/dist -> warn (the build step reports its own failure; never double-fail). Product-
specific click-flows do NOT belong here — extend scripts/quality.py in the project for those.
Runtime budget: one preview boot + one page load; keep it well under the gate's hook timeout.

Every kit update OVERWRITES this file (like kit_checks.py), so fixes reach existing projects.
"""
import os
import re
import socket
import subprocess
import time


def _config(root):
    """entry + mount_selector from testing_guidelines.yaml `browser_smoke:` (regex block parse —
    this module must not require pyyaml)."""
    entry, mount = "/", "#root"
    p = os.path.join(root, "project_memory", "testing_guidelines.yaml")
    try:
        txt = open(p, encoding="utf-8", errors="ignore").read()
    except Exception:
        return entry, mount
    m = re.search(r"(?m)^browser_smoke:[ \t]*$", txt)
    if not m:
        return entry, mount
    for line in txt[m.end():].splitlines():
        # quoted values may CONTAIN '#' (a mount selector is usually "#root"); an unquoted
        # value ends at a trailing ' #' comment (audit: the comment used to void the whole
        # line and the smoke silently tested the default route)
        mm = re.match(r"[ \t]+(entry|mount_selector):[ \t]*"
                      r"(?:\"([^\"\n]*)\"|'([^'\n]*)'|([^#\n]+?))[ \t]*(?:#.*)?$", line)
        if mm:
            val = (mm.group(2) if mm.group(2) is not None
                   else mm.group(3) if mm.group(3) is not None else mm.group(4) or "").strip()
            if mm.group(1) == "entry":
                entry = val or entry
            else:
                mount = val or mount
        elif line.strip() and not line.startswith((" ", "\t")):
            break  # left the block
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
        console_errors = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.on("console",
                        lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                page.goto(url, wait_until="networkidle", timeout=15000)
                mount_html = page.inner_html(mount)
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
        elif console_errors:
            fail(name, "browser console error(s): " + "; ".join(console_errors[:3]))
        else:
            ok(name)
    finally:
        _terminate_process_tree(proc)
