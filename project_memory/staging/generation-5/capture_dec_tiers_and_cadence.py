"""Capture the user's addendum of 2026-09-06 to DEC-0087: the orchestrator derives the TIERS itself --
quality outranks cost, but needless cost (a verification round after every change) is avoided -- and
the verification CADENCE of the light form. Body on stdin to `kernel.cli capture DEC`. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Stufen und Prueftakt der leichten Arbeitsform (Zusatz zu DEC-0087): der Orchestrator leitet die "
             "Stufe selbst ab -- Qualitaet vor Kosten, aber keine unnoetigen Kosten --, und geprueft wird am Ziel: "
             "hoechstens zwei Prueferrunden je Ziel, keine nach einer Kleinaenderung",
    "context": "USER 2026-09-06, minutes after DEC-0087: 'die Stufen muss der Orchestrator ja auch selbst "
               "entscheiden. Was wichtig ist: Qualitaet ist mehr wert als Kosten. Aber unnoetige Kosten "
               "erzeugen sollte vermieden werden (die 1000 Pruefrunden z.B. immer nach jeder Aenderung). Und "
               "wie laeuft das dann kuenftig mit den Pruefrunden?' MEASURED behind it: generation 4's streams "
               "took 3-5 verification rounds each, generation 5's 3-4; the verifier's finds that the author "
               "could not see came mostly at INTEGRATION (the merge: 435 red tests) and at the first full "
               "round; later rounds returned mainly prose-vs-code and the edges of the previous fix "
               "(TSK-0130/0131/0132 rounds 2-4); the FR-0089 research: review by an agent without the "
               "author's context is the one proven gain, and effort/thinking beyond 'high' is logarithmic.",
    "decision": "TIERS -- derived by the orchestrator from the kit's ladder declaration (DEC-0078) and the "
                "goal, never asked: (1) a goal-sized build (architecture, product, frontend, anything that "
                "needs judgment) goes to a BUILDER on the kit's TOP rung (dev/research: fable) at effort high "
                "-- quality first; (2) a MECHANICAL slice with a complete spec and an acceptance criterion may "
                "go to a lower rung; (3) the independent VERIFIER runs on opus at high (a different model from "
                "the builder, so the second reader is independent -- DEC-0081's reason); (4) xhigh/max only on "
                "the orchestrator's explicit call for one named step, never as a standing setting; (5) the "
                "chosen rung and effort stand on the lease and in the brief (PR-0010 AC-6). CADENCE -- (a) "
                "DURING the build: no verifier; the builder writes a red-first test per fix and runs the "
                "reading suites (DEC-0050 / DEC-0080 (2)); (b) AT THE GOAL: ONE verifier round against the "
                "goal's acceptance criteria, verdict per AC; a FAIL gets ONE rework and ONE short second round "
                "over the failed ACs only -- never the whole package again; (c) a THIRD round is not a round "
                "but a re-cut: the finding class decides (prose-vs-code -> the builder's own checklist grows; "
                "coordination -> the cut was wrong; product defects -> the goal was too big); (d) a small "
                "change under an existing goal (a bug fix, a wording) gets NO separate verifier -- its "
                "red-first test and the goal's final round cover it, the delivery approval is the human gate; "
                "(e) a mid-goal check only for a goal the orchestrator marks LARGE at the cut, once, at the "
                "half; (f) the MERGE / integration stays its own verification (DEC-0063 (1), confirmed three "
                "times) -- stamp before the full run (DEC-0080 (5)), one full run with the delivery prefix. "
                "COST DISCIPLINE -- 'unnecessary' is defined, not felt: a verifier round that repeats a "
                "measurement the builder's protocol already carries, a full-suite run inside a goal, an "
                "effort above high without a named step, a second builder without check-scopes evidence.",
    "consequences": "Per goal: one builder on the top rung, at most two verifier rounds, one merge round -- "
                    "against 3-5 rounds per stream today; quality kept where it is bought (the builder's "
                    "rung and the independent second reader), cost cut where it was measured wasted (rounds "
                    "after small changes, repeated full packages, standing xhigh). Rejected: asking the user "
                    "for tiers; a verifier after every change; the cheapest rung for judgment work.",
    "source": "user message 2026-09-06; DEC-0087; DEC-0081; DEC-0078; DEC-0080; DEC-0063; DEC-0050; FR-0089 "
              "research A/B/C and summary.md; the (g) rows of TSK-0121..0132",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
