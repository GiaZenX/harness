"""The user approved the V2.5 simplification plan (docs/PLAN_V2_5_VEREINFACHUNG.md) on 2026-09-27, with his own
decisions folded in. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Plan V2.5 freigegeben: vom bremsenden zum effizienten Agentensystem -- Befehlszeilen-Raten ersetzt durch "
             "Kernel-Schreibprotokoll + Kontrolle danach, Modellklasse (Kilo/Mega/Giga) und Denktiefe getrennt mit "
             "Begruendung aus fester Liste, Watcher breiter, Lebenszeichen statt Polling, feste Groessengrenzen, "
             "parallele Bloecke; in Wellen parallel umgesetzt",
    "context": "USER 2026-09-27: 'Vereinfachungsrunde ja, ABER ...' (autonom, grosse Bloecke, eine Datei einmal, CRs "
               "direkt in den laufenden Block, mehr Stroeme, weniger Freigaben, Polling auf null, Frontend-Pruefung, "
               "Bestandsaufnahme). Basis: the independent review staging/FR-0089/independent-review-2026-09-27.md; a "
               "model-tier web research (Anthropic, Codex guide, Aider, Cursor Router, Cline, RouteLLM, arXiv "
               "2608.01347); a counter-review of the plan against the DECs (12 corrections: fixed size ceilings instead "
               "of deletion, the kernel write log does not exist yet, the full run after every merge stays, the "
               "Write/Edit path check and the git/push/docker/test-run readers stay, an approval after-check replaces "
               "the H80 wall, DEC supersession list). The user's answers: command-line gates 'Ersetzen'; ladder: two "
               "axes model class and effort, each with a reason enforced by a hook, names like Kilo/Mega/Giga/Tera, "
               "Haiku never for code, a new model replaces a ladder model only with measured proof, the PM always "
               "briefed with a researched 'which model for what' file; workshop: 'verschlanken wo man merkt man wird "
               "unnoetig gebremst', measured during the process, also in synaipse; watcher BROADER not slimmer ('unsere "
               "Quelle der Neuigkeiten'); polling to zero via HEARTBEATS: every long run emits a life sign, missing "
               "it past a deadline means hung/failed. Approved via the plan dialog on 2026-09-27.",
    "decision": "The plan docs/PLAN_V2_5_VEREINFACHUNG.md is the order for the next rounds: Welle 0 (finish order 7; "
                "baseline metrics here and in synaipse), Welle 1 in four parallel streams (A approvals + walkthrough, "
                "B protection layer: kernel write log + after-check + approval after-check, then remove only the "
                "write-target guessing; C PM intelligence: two-axis model choice with a closed reason list, role "
                "variants, model guide file, heartbeats, broader watchers, blocks instead of slices, parallel builders; "
                "D frontend review tool from synaipse PR-0031/0032), Welle 2 in two (E text diet with fixed size "
                "ceilings raised only by the user; F tests split + workshop slimmed where measured + DEC supersession "
                "list), then merge, one verifier, the full run, delivery, synaipse field check. The six guarantees "
                "G1-G6 are held by mechanism; everything else must bring more than it blocks, measured per wave "
                "(section 5 of the plan).",
    "consequences": "Supersedes, where they conflict, the parts of DEC-0034/0076-0078/0091/0092 (1)/0095-0097 about "
                    "the ladder's shape (two axes, closed reason list) and of SR-0009's write-target reading; each "
                    "stream names the DECs it supersedes in the supersession list (F). Not a V3: kernel, items, "
                    "approval guarantee and builder/verifier stay.",
    "work": ["PR-0012"],
    "source": "docs/PLAN_V2_5_VEREINFACHUNG.md; user messages 2026-09-27; staging/FR-0089/independent-review-2026-09-27.md",
}

env = dict(os.environ, PYTHONPATH="team-kits")
r = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY), capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
