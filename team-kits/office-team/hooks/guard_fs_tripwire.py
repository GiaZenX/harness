#!/usr/bin/env python3
"""
PreToolUse(Bash|PowerShell) — deletes on inbox/ or archive/, and moves OUT of archive/, are blocked.

Business documents are irreplaceable: "originals are moved, never deleted" must not depend on
discipline. Filing INTO archive/ (mv from inbox) stays free; deleting anything under inbox/ or
archive/, or moving something OUT of archive/, blocks. Reorganisation inside the archive runs as
a user-approved migration PROC — if this guard fires on legitimate reorg, that is the signal to
get the user's OK first, not to work around it. Uncertainty -> exit 0.
"""
import json
import os
import re
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _audit


DELETE_RX = re.compile(
    r"\b(rm|rmdir|del|erase|rd|Remove-Item|ri)\b[^\n;|&]*\b(inbox|archive)(\b|[/\\])", re.I)
MOVE_RX = re.compile(
    r"\b(mv|move|Move-Item|mi|ren|rename|Rename-Item)\b[^\n;|&]*\barchive[/\\]", re.I)
# shell redirects into the ledger bypass the Edit/Write guard (audit finding: `echo >> ledger/x.csv`)
LEDGER_REDIRECT_RX = re.compile(r"[>|]\s*\"?[^\s\"|;&]*\bledger[/\\][^\s\"|;&]*\.csv", re.I)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") not in ("Bash", "PowerShell"):
        sys.exit(0)
    cmd = str((data.get("tool_input") or {}).get("command") or "")
    if LEDGER_REDIRECT_RX.search(cmd) and "ledger_add.py" not in cmd:
        _audit.record("guard_fs_tripwire", "shell redirect into ledger: %s" % cmd[:120])
        sys.stderr.write(
            "[team-kit guard] Shell writes into ledger/*.csv are BLOCKED — the ledger is "
            "script-validated and append-only: use `python scripts/ledger_add.py ...` (arithmetic, "
            "duplicate and year checks) — corrections are reversal entries.\n")
        sys.exit(2)
    if DELETE_RX.search(cmd):
        _audit.record("guard_fs_tripwire", "delete on inbox/archive: %s" % cmd[:120])
        sys.stderr.write(
            "[team-kit guard] Deleting under inbox/ or archive/ is BLOCKED — business documents "
            "are moved (with a filing/migration manifest), never deleted. Duplicates get a _dupNN "
            "suffix and a flag.\n")
        sys.exit(2)
    m = MOVE_RX.search(cmd)
    if m:
        # moving INTO the archive is normal filing (from inbox/, outbox/, reports/ …); only an
        # archive/ SOURCE (moving out) blocks. The SOURCE is the first non-flag token after the
        # verb — checking "first token that mentions archive" wrongly blocked `mv report.pdf
        # archive/…` because the DESTINATION was the first archive mention.
        tail = cmd[m.start():]
        tokens = [t.strip("\"'") for t in tail.split()][1:]          # drop the verb itself
        source = next((t for t in tokens if not t.startswith("-")), "")
        if re.search(r"\barchive[/\\]", source, re.I):
            _audit.record("guard_fs_tripwire", "move out of archive: %s" % cmd[:120])
            sys.stderr.write(
                "[team-kit guard] Moving files OUT of archive/ is BLOCKED — the archive is the "
                "system of record. Reorganisation runs as a user-approved migration PROC (dry-run "
                "-> OK -> move + manifest); ask the manager/user instead of working around this.\n")
            sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
