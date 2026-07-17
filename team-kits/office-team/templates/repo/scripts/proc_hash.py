#!/usr/bin/env python3
"""
proc_hash.py — set/verify a PROC's approved_hash (canonical hash over its steps).

The approval hash makes tampering detectable: gate_proc_approved recomputes it on every spawn and
blocks when an APPROVED PROC's steps changed after approval. The manager runs this ONLY right
after the user's approval — never to paper over an unapproved edit.

Usage:
  python scripts/proc_hash.py PROC-0001            # print computed vs recorded
  python scripts/proc_hash.py PROC-0001 --update   # write the computed hash (after user approval!)
"""
import argparse
import hashlib
import os
import re
import sys

import yaml  # type: ignore[import-untyped]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "project_memory", "process_definitions.yaml")


def steps_hash(steps):
    """MUST match hooks/gate_proc_approved.py exactly."""
    dumped = yaml.safe_dump(steps, sort_keys=True, allow_unicode=True)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proc_id")
    ap.add_argument("--update", action="store_true")
    args = ap.parse_args()

    text = open(PATH, encoding="utf-8").read()
    doc = yaml.safe_load(text) or {}
    body = (doc.get("processes") or {}).get(args.proc_id)
    if not isinstance(body, dict):
        sys.stderr.write("[proc_hash] %s not found in %s\n" % (args.proc_id, PATH))
        sys.exit(1)
    computed = steps_hash(body.get("steps"))
    recorded = str(body.get("approved_hash") or "")
    print("computed: %s" % computed)
    print("recorded: %s" % (recorded or "(empty)"))
    if not args.update:
        sys.exit(0 if computed == recorded else 1)

    # update: replace the approved_hash line INSIDE this PROC's block only (text-surgical, so
    # comments/formatting of the hand-maintained file survive). (?m) WITHOUT (?s): with DOTALL,
    # `    .*\n` bridged line breaks and a PROC lacking its own approved_hash line swallowed the
    # FOLLOWING blocks — a real PROPOSED PROC ended up carrying its neighbor's hash. `\r?` keeps
    # the header matching after a CRLF-writing tool touched the file (the same real incident).
    block_rx = re.compile(r"(?m)^(  %s:\r?\n(?:    .*\n)*?)(    approved_hash:[^\n]*\n)"
                          % re.escape(args.proc_id))
    m = block_rx.search(text)
    if m:
        new_text = text[:m.start(2)] + '    approved_hash: "%s"\n' % computed + text[m.end(2):]
    else:
        block_rx2 = re.compile(r"(?m)^(  %s:\r?\n(?:    .*\n)*)" % re.escape(args.proc_id))
        m2 = block_rx2.search(text)
        if not m2:
            sys.stderr.write("[proc_hash] could not locate the %s block textually — add "
                             "approved_hash manually per the computed value\n" % args.proc_id)
            sys.exit(1)
        new_text = text[:m2.end(1)] + '    approved_hash: "%s"\n' % computed + text[m2.end(1):]

    # Class-killer verification BEFORE anything touches disk: the surgical edit must set exactly
    # the target PROC's hash and change NO other PROC's hash — otherwise refuse loudly.
    after = yaml.safe_load(new_text) or {}
    after_hashes = {pid: str((body or {}).get("approved_hash") or "")
                    for pid, body in (after.get("processes") or {}).items()
                    if isinstance(body, dict)}
    before_hashes = {pid: str((body or {}).get("approved_hash") or "")
                     for pid, body in (doc.get("processes") or {}).items()
                     if isinstance(body, dict)}
    if after_hashes.get(args.proc_id) != computed or any(
            after_hashes.get(pid) != value
            for pid, value in before_hashes.items() if pid != args.proc_id):
        sys.stderr.write("[proc_hash] REFUSED: the textual update would have landed in the wrong "
                         "block (another PROC's approved_hash would change). File left untouched — "
                         "fix process_definitions.yaml formatting or add the hash manually.\n")
        sys.exit(2)

    with open(PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new_text)
    print("[proc_hash] approved_hash updated for %s" % args.proc_id)


if __name__ == "__main__":
    main()
