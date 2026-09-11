"""Capture the user's refinement of 2026-09-11 07:2x to the escalation mechanic (DEC-0034 rule 2 / DEC-0095 (4)):
EFFORT BEFORE RUNG -- the first FAIL raises the effort on the same rung, the rung climbs (to Fable) only after
repeated failure, because the first verification round fails as a rule and mostly on prose-vs-code. Then appends
the mechanic to TSK-0136 (DRAFT) as one more expected_output. Not idempotent -- run once."""
import io
import json
import os
import subprocess
import sys

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ENV = dict(os.environ, PYTHONPATH="team-kits")


def kernel(*args, body=None):
    argv = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory"] + list(args)
    r = subprocess.run(argv, cwd=ROOT, env=ENV, input=json.dumps(body) if body is not None else None,
                       capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout.strip() or r.stderr.strip())
    print(out[-300:])
    return r.returncode, out


DEC = {
    "title": "Eskalation: erst AUFWAND, dann SPROSSE (Zusatz zu DEC-0034 Regel 2 / DEC-0095 (4)): der erste "
             "Fehlschlag hebt den Aufwand auf derselben Sprosse (high -> xhigh), die Sprosse steigt erst nach "
             "wiederholtem Scheitern -- Fable wird beim dritten Fehlschlag erreicht, nicht beim ersten",
    "context": "USER 2026-09-11 ~07:20: 'Soll lieber nur auf Fable eskaliert werden, wenn Opus es 3x nicht hinbekommt, "
               "und vorher nur der Effort steigen? Weil durch die erste Pruefung fallen wir in der Regel immer durch.' "
               "MEASURED: every stream of generations 3-5 and both generation-5/6 goal packages FAILED their first "
               "verification round (TSK-0130/0131/0132 round 1, TSK-0133 round 1, TSK-0135's mid-goal check found six "
               "code lines); the first round's findings are mostly prose-vs-code and the fix's own edges, not a lack of "
               "model capability (DEC-0088 (c) finding classes). Today's ladder (dev/research/office ladder.yaml "
               "`escalation: failed_runs_per_rung: 1`, DEC-0034 rule 2 'one rung per FAIL') would therefore lift an "
               "Opus builder to Fable after the first round of almost every goal -- the standing Fable cost DEC-0095 "
               "just removed, back through the side door. DEC-0077 (2) made the thresholds config values with their "
               "DEC line for exactly this: a pilot may move them.",
    "decision": "(1) ORDER OF THE TWO AXES ON FAILURE: FAIL 1 -> same rung, effort one step up (high -> xhigh; an order "
                "already at the kit's ceiling stays); FAIL 2 -> same rung at the raised effort, and the lead applies "
                "DEC-0088 (c): a re-cut by finding class (prose-vs-code -> the builder's checklist grows, no "
                "escalation; coordination -> the cut was wrong; product defects -> the goal was too big); FAIL 3 -> the "
                "rung climbs one step (opus -> fable, DEC-0034 rule 2), from where the effort restarts at the kit's "
                "default. (2) CONFIG, NOT CONSTANTS (DEC-0077 (2)): `escalation.effort_steps_before_rung: 2` and "
                "`escalation.failed_runs_per_rung: 3` in every kit's ladder.yaml, each line carrying this DEC; the "
                "dispatcher derives effort and rung from the order's FAILED count and these two values; a kit may "
                "declare other numbers (office's ceiling is high, so its first step is a no-op and it climbs to opus "
                "at FAIL 3 -- said in its ladder). (3) COUNTED PER ORDER, as today: a re-cut order starts its own "
                "count -- the re-cut IS the reset, by design (a smaller order on the same rung is the cheaper "
                "correction). (4) SHOWN: the lease and the checkpoint print 'FAIL n of the order: effort/rung derived "
                "as ...', the (g) table records rounds-to-PASS per rung and per effort, so the two thresholds are "
                "re-measured over generations. (5) CARRIER: TSK-0136 (DEC-0095's order) -- one mechanic, one place "
                "(kernel/dispatch.py ladder_for_order + the three ladder.yaml + tests red-first on FAIL 1/2/3).",
    "consequences": "The first verification FAIL costs an effort step, not the top model; Fable stays what DEC-0095 "
                    "made it -- the architecture step and a measured last resort. Cost: a goal that truly needs the "
                    "top rung pays two more Opus rounds before it gets there -- bounded by DEC-0088's two-round cap "
                    "and the re-cut in between. Rejected: one rung per FAIL as the default (the measured first-round "
                    "FAIL rate makes it a standing Fable cost); escalating on the verifier's finding class "
                    "automatically (no kernel reader can classify prose-vs-code -- the lead does, at the re-cut).",
    "work": ["TSK-0136", "PR-0011"],
    "source": "user message 2026-09-11 ~07:20; DEC-0034; DEC-0077 (2); DEC-0088 (b)/(c); DEC-0095; the verification "
              "histories of TSK-0130..0135 (round logs generation-5/6-streams.md); team-kits/*/ladder.yaml escalation block",
}

NEW_OUTPUT = (
    "ESCALATION ORDER (DEC-0096): `escalation.effort_steps_before_rung: 2` and `escalation.failed_runs_per_rung: 3` in "
    "the three ladder.yaml (each line citing DEC-0096; office's ceiling makes its first step a no-op -- said there); "
    "kernel/dispatch.py ladder_for_order derives from the order's FAILED count: FAIL 1 -> same rung, effort +1 (capped "
    "by the kit's ceiling), FAIL 2 -> same rung at the raised effort, FAIL 3 -> rung +1 with the effort back at the "
    "kit's default; the lease `why` and the checkpoint print 'FAIL n: ...'; report.lease_distribution records "
    "rounds-to-PASS per rung AND per effort; red-first: a test per FAIL count (0/1/2/3) on a synthetic ladder plus the "
    "real dev ladder, red on today's one-rung-per-FAIL; the constitutions' ladder statement says effort before rung."
)


def main():
    rc, out = kernel("capture", "DEC", body=DEC)
    if rc != 0:
        return rc
    dec_id = out.strip().split()[0]
    item = yaml.safe_load(io.open(os.path.join(ROOT, "project_memory", "tasks", "active", "TSK-0136.yaml"), encoding="utf-8"))
    outputs = list(item["expected_outputs"])
    outputs.append(NEW_OUTPUT.replace("DEC-0096", dec_id))
    inputs = list(item["required_inputs"])
    inputs.insert(1, "%s (escalation: effort before rung; FAIL 1 effort +1, FAIL 2 re-cut, FAIL 3 rung +1; the two "
                     "thresholds as config values with their DEC line) -- the mechanic this order builds beside "
                     "DEC-0095's pins" % dec_id)
    kernel("update", "TSK-0136", body={"expected_outputs": outputs, "required_inputs": inputs})
    return 0


if __name__ == "__main__":
    sys.exit(main())
