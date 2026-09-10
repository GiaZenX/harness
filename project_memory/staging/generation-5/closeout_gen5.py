"""Generation-5 close-out through the kernel, run by the lead AFTER the merge commit (DEC-0093 (1)):
(1) the delivered wishes -> MERGED with resulting_item (the goal that carried them; FR-0058 AC-2 form),
(2) the four generation-5 work orders TSK-0130..0133 -> archived (TSK-0133 CANCELLED = delivered first),
(3) prints what it did. Every write is a kernel line; nothing here touches a file. Idempotent per step:
a transition already made is reported by the kernel as illegal and skipped."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ENV = dict(os.environ, PYTHONPATH="team-kits")


def kernel(*args, body=None):
    argv = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory"] + list(args)
    r = subprocess.run(argv, cwd=ROOT, env=ENV, input=json.dumps(body) if body is not None else None,
                       capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout.strip() or r.stderr.strip()).splitlines()
    print("  %-40s -> %s" % (" ".join(args)[:40], out[-1][:160] if out else "(no output)"))
    return r.returncode


# wish -> (goal, one-line triage result: what shipped, where measured)
MERGED = {
    "FR-0088": ("PR-0010", "DELIVERED in generation 5 (G5-2, TSK-0130): model_tiers.yaml three rungs per provider "
                           "(astra/sol/terra = fable/opus/sonnet), generator refusal of a light pin, ladder.yaml per kit, "
                           "escalation in the dispatcher; merged TSK-0133"),
    "FR-0058": ("PR-0008", "DELIVERED in generation 5 (G5-1, TSK-0131): every active BUG/FR surveyed against the running "
                           "code (survey-table.md), stock rollup + 'stock lies upward' validator line in report.py, five "
                           "gen-4 bugs VERIFIED/archived; merged TSK-0133"),
    "FR-0007": ("PR-0008", "DELIVERED in generation 5 (G5-1): the comment-discipline duty in the three constitutions "
                           "(byte-identical) and nine implementing roles, mechanical half = sweep-pointers; merged TSK-0133"),
    "FR-0012": ("PR-0008", "DELIVERED in generation 5 (G5-1, DEC-0083): the DEC `work` field + capture door + "
                           "decision-carrier validator (option A); merged TSK-0133"),
    "FR-0033": ("PR-0009", "DELIVERED in generation 5 (G5-3, DEC-0082): correspondence as a teachable workflow "
                           "(letter_draft.py, correspondence.yaml, skills/correspondence); merged TSK-0133"),
    "FR-0081": ("PR-0009", "DELIVERED in generation 5 (G5-3): chart_of_accounts.yaml (SKR03/SKR04 + EUeR mapping, "
                           "year-versioned) with its kernel writer; merged TSK-0133"),
}
KEEP_TRIAGED_NOTE = {
    "FR-0002": "PARTLY absorbed by PR-0009 (G5-3) -- the eight takeovers were not recounted by the merge verifier "
               "(verify-round-1.md section 5); stays TRIAGED until the acceptance of PR-0009 names which of the eight "
               "shipped",
    "FR-0047": "PARTLY delivered by PR-0010 (rung + effort on the lease and in the session brief, BUG-0249); the "
               "'silent downgrade visible' half is measured by test_model_pins -- stays TRIAGED until PR-0010's "
               "acceptance",
}


def main():
    print("== wishes delivered in generation 5")
    for fr, (goal, note) in MERGED.items():
        kernel("transition", fr, "TRIAGED")  # OPEN -> TRIAGED where still OPEN (FR-0088); illegal elsewhere, skipped
        kernel("update", fr, body={"resulting_item": goal, "triage_result": note})
        kernel("transition", fr, "MERGED")
        kernel("archive", fr)
    print("== wishes kept TRIAGED with the note")
    for fr, note in KEEP_TRIAGED_NOTE.items():
        kernel("update", fr, body={"triage_result": note})
    print("== the generation-5 orders")
    kernel("transition", "TSK-0133", "CANCELLED")
    for tsk in ("TSK-0130", "TSK-0131", "TSK-0132", "TSK-0133"):
        kernel("archive", tsk)
    kernel("generate-index")
    return 0


if __name__ == "__main__":
    sys.exit(main())
