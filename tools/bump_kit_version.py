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
SKIP_DIRS = {"__pycache__", ".ruff_cache", ".mypy_cache", ".pytest_cache"}
SHARED_HARNESS_FILES = (
    "gen_provider_artifacts.py",
    "init_project_memory.ps1",
    "init_project_memory.sh",
    "model_tiers.yaml",
    "preset_config.py",
    "registry.yaml",
    "scaffold_team.ps1",
    "scaffold_team.sh",
)


def discover_kits(root=ROOT):
    """Every directory under team-kits/ that ships agents/ is a kit — no hard-coded list, so a
    future third kit can never ship unversioned/unchecked by omission."""
    base = os.path.join(root, "team-kits")
    if not os.path.isdir(base):
        return []
    return sorted(d for d in os.listdir(base)
                  if os.path.isdir(os.path.join(base, d, "agents")))


def kit_hash(kit_dir):
    """Hash kit-local files plus shared scaffold/generator inputs (except VERSION + caches).

    CRLF normalization keeps the hash identical across Windows/Linux checkouts of the same commit.
    """
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(kit_dir):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if (fn == "VERSION" and dirpath == kit_dir) or fn.endswith(".pyc"):
                continue  # only the kit's own top-level VERSION is hash-excluded
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, kit_dir).replace("\\", "/")
            h.update(rel.encode("utf-8"))
            with open(p, "rb") as fh:
                h.update(fh.read().replace(b"\r\n", b"\n"))
    team_kits_root = os.path.dirname(os.path.abspath(kit_dir))
    for rel in SHARED_HARNESS_FILES:
        path = os.path.join(team_kits_root, rel)
        if not os.path.isfile(path):
            continue
        h.update(("@shared/" + rel).encode("utf-8"))
        with open(path, "rb") as fh:
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
    for kit in discover_kits():
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
