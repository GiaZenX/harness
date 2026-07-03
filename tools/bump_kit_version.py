#!/usr/bin/env python3
"""
bump_kit_version.py — stamp each team kit with a version + content hash.

Writes team-kits/<kit>/VERSION:
    version: YYYY.MM.DD-N        (human-readable, monotonic per day)
    content: <sha256>            (hash over every kit file, CRLF-normalized)

validate.py recomputes the hash and FAILS when kit files changed without a bump — so forgetting
is impossible (CI goes red). The scaffold stamps the version into a project's ./.claude/kit_version;
session_status compares it against the staged kit and flags available updates at session start.

Run after any kit change:  python tools/bump_kit_version.py
"""
import datetime
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KITS = ("dev-team", "research-team")
SKIP_DIRS = {"__pycache__", ".ruff_cache", ".mypy_cache", ".pytest_cache"}


def kit_hash(kit_dir):
    """sha256 over relpath + CRLF-normalized bytes of every kit file (except VERSION + caches).

    CRLF normalization keeps the hash identical across Windows/Linux checkouts of the same commit.
    """
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(kit_dir):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn == "VERSION" or fn.endswith(".pyc"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, kit_dir).replace("\\", "/")
            h.update(rel.encode("utf-8"))
            with open(p, "rb") as fh:
                h.update(fh.read().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def read_version_line(path):
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("version:"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return ""


def next_version(previous):
    today = datetime.date.today().strftime("%Y.%m.%d")
    if previous.startswith(today + "-"):
        try:
            return "%s-%d" % (today, int(previous.rsplit("-", 1)[1]) + 1)
        except ValueError:
            pass
    return today + "-1"


def main():
    changed = False
    for kit in KITS:
        kit_dir = os.path.join(ROOT, "team-kits", kit)
        if not os.path.isdir(kit_dir):
            continue
        vfile = os.path.join(kit_dir, "VERSION")
        digest = kit_hash(kit_dir)
        old = ""
        if os.path.isfile(vfile):
            old = open(vfile, encoding="utf-8").read()
        if ("content: %s" % digest) in old:
            print("  %s: unchanged (%s)" % (kit, read_version_line(vfile)))
            continue
        version = next_version(read_version_line(vfile))
        with open(vfile, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("version: %s\ncontent: %s\n" % (version, digest))
        print("  %s: bumped -> %s" % (kit, version))
        changed = True
    if changed:
        print("VERSION files updated — commit them with the kit change.")
    sys.exit(0)


if __name__ == "__main__":
    main()
