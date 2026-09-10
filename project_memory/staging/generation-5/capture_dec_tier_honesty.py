"""Capture the user's decision of 2026-09-10 on HOW the PM's team-size and tier choices are measured, enforced and
nudged (the follow-up to DEC-0091): no free-text justification field (no gate reads prose), but a structural
gate, a distribution line, a retrospective rule, a pilot rig -- and a FACT-BASED reflection checkpoint the
spawn gate prints, because the user's point is 'think again instead of acting from habit'. Body on stdin to
`kernel.cli capture DEC`, work = PR-0011. Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Ehrliche Team- und Stufenwahl (Zusatz zu DEC-0087/0088/0091): kein Begruendungs-Freitext, sondern ein "
             "Struktur-Gate (zweiter Bauer nur mit Bereichsabgleich), eine Verteilungszeile im Briefing, eine "
             "Rueckschau-Regel, ein Pilot-Rig -- und ein FAKTEN-Checkpoint des Spawn-Gates, der den PM vor jedem "
             "Start zum Nachdenken bringt statt ihn zu blockieren",
    "context": "USER 2026-09-10: 'wie messen wir das und wie erzwingen wir, dass der Sitzungsagent sauber entscheidet -- "
               "nicht immer nur einen (Sonnet) oder immer drei (Fable)? Sollte das als Hook rein: vor jedem Subagent-Start "
               "Felder ausfuellen, wieso nur einer und wieso die Stufen -- oder ist das zu viel Overload?' and, after "
               "the lead's proposal: 'ja -- ich dachte der Begruendungs-Hook zeigt dem PM eben immer auf, dass er "
               "nochmal drueber nachdenken soll statt aus Gewohnheit zu handeln.' MEASURED FACTS behind the design: no "
               "gate reads free text (CLAUDE.md, gaplog.py, FR-0052 -- a prose duty is satisfied with words; the P4 "
               "pilots measured it); the under-pick corrects itself through escalation (DEC-0034 rule 2, one rung per "
               "FAIL, built in G5-2); the over-pick and the always-one/always-three habits show only in cost, never in "
               "the outcome; every lease and every dispatch already lands in the project's .audit/hook_events.jsonl and "
               "the lease record (rung + effort per PR-0010 AC-6), so the DISTRIBUTION is derivable without a new "
               "instrument; a PreToolUse hook may return context to the model without refusing.",
    "decision": "(1) NO free-text justification field on the spawn: a required 'why' is boilerplate nobody can check "
                "and it trains the habit it is meant to break. (2) STRUCTURAL GATE: a second concurrent BUILD lease "
                "under one goal is refused unless a check-scopes record shows the two orders' file sets measured "
                "disjoint (DEC-0087 (2) as a gate, not a sentence); a lease without rung and effort is refused "
                "(PR-0010 AC-6 kept). (3) THE REFLECTION CHECKPOINT -- the user's intent, built with facts instead of "
                "a blank: the spawn/dispatch gate PRINTS, before every builder start, a derived four-line checkpoint "
                "the PM reads in the same turn: (a) the goal's measured file sets (check-scopes: 'this goal splits "
                "into N disjoint sets' or 'one set'), (b) the order's size signals (allowed-scope file count, expected "
                "outputs count, goal class), (c) the rung and effort about to be leased with the ladder floor beside "
                "them, (d) the distribution of the last N leases in this project (builders per goal, rungs). It ends "
                "with one question the PM answers to itself, not in a field: 'does the rung fit the slice, and is one "
                "builder still the right count?'. It never blocks; it is a mirror with numbers. (4) DISTRIBUTION LINE: "
                "the session brief carries the same distribution (last N leases: builders per goal, rungs, rounds to "
                "PASS per rung) so the USER sees a habit at a glance. (5) RETROSPECTIVE RULE at the goal (DEC-0087 "
                "(2) made concrete): the retrospective step compares the builder count against the measured-disjoint "
                "sets and the chosen rung against the outcome (rounds to PASS, findings class) and writes the verdict "
                "as its own line -- 'solo where parallel would have paid' and 'fable where sonnet passed first round' "
                "are named, with numbers. (6) PILOT RIG: a repeatable rig on a scaffolded project hands the PM three "
                "orders of obviously different size and records what it leases; run at every kit stamp that touches "
                "the ladder or the PM texts; red-first tests on the derivation (rung under the floor refused; second "
                "lease without a check-scopes record refused). (7) THE HONEST LIMIT, said in the texts: whether the PM "
                "judges WELL is measured only by the outcome (rounds, cost, the user's verdict) -- the checkpoint and "
                "the line make the habit visible, they do not make the judgment right. CARRIER: PR-0011 (generation 6).",
    "consequences": "Four lines per spawn instead of a form; the two degenerate habits become visible in the brief and "
                    "named in the retrospective; 'always three' becomes impossible without measured disjointness; the "
                    "under-pick stays self-correcting. Cost: one gate rule, one derivation in report.py, one rig. "
                    "Rejected: a required justification field (unreadable by gates, measured boilerplate); blocking on "
                    "a rung choice (the judgment is the PM's, the floor is the ladder's); no nudge at all (the user's "
                    "point -- habit -- is real and cheap to mirror).",
    "work": ["PR-0011"],
    "source": "user messages 2026-09-10; DEC-0087; DEC-0088; DEC-0091; DEC-0034; PR-0010 AC-6; kernel/gaplog.py "
              "(no gate reads free text); FR-0052; .audit/hook_events.jsonl as the lease/dispatch record",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
