"""User answers 2026-09-28 ~22:0x on FR-0098's two open decisions. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Modellklassen nach FR-0098: Codex baut mit Sol (Mega) auf high bis Astra (Tera) gemessen ist; Fable "
             "kommt nach dem dritten Fehlschlag nicht automatisch -- erst neu schneiden, Fable nur mit Messbeleg; "
             "Klassenfragen: Boden -> Kilo -> Mega -> sonst Giga",
    "context": "Research FR-0098 (project_memory/staging/FR-0098/research-model-classes-2026-09-28.md) on DEC-0129's "
               "scale: OpenAI placed honestly -- Luna Kilo (borderline, high hallucination), Sol Mega, Astra Tera, Giga "
               "EMPTY; DEC-0096 lifted Opus to Fable on the third failure while DEC-0128/0129 require a measured "
               "advantage for Tera. The lead asked both; the user chose the recommended options (AskUserQuestion "
               "2026-09-28).",
    "decision": "(1) Codex default builder: Sol (Mega) at high until a measurement shows Astra (Tera) worth its price "
                "per solved task; then Astra becomes the builder. (2) After a third failure an order is RE-CUT or "
                "returned to the planner (DEC-0088 (c)); Fable (Tera) only where the measurement shows an advantage "
                "for that kind of task -- supersedes DEC-0096's automatic lift to Fable. (3) CLASS questions per "
                "order, in this order, reading only fields the order carries: protected surface or irreversible "
                "change -> never below Giga; read-only summary/lookup -> Kilo (only once DEC-0128 (3)'s measurement "
                "opened it); a test decides and the allowed scope names at most N files (start N=3, measured) -> "
                "Mega; else Giga. 'Already failed' is part of the escalation (effort first, class later -- DEC-0096 "
                "(1)), not a start question. (4) The failure question for escalation: did it not TRY hard enough "
                "(more effort) or not KNOW enough (bigger class)? A misread requirement is neither -- it goes back as "
                "a question (DEC-0127 (6)). (5) The Mega builder (Sonnet) is measured at medium AND high before its "
                "default is fixed.",
    "consequences": "Stream C builds the four class questions as the closed reason list, the escalation rule, and "
                    "the measurement harness with paired runs (>= 3 per variant), actual model read from the "
                    "transcript, and a quote-verified hallucination check for Kilo.",
    "work": ["PR-0012"],
    "source": "FR-0098 research report; user answers 2026-09-28; DEC-0088; DEC-0096; DEC-0127; DEC-0128; DEC-0129",
}

env = dict(os.environ, PYTHONPATH="team-kits")
r = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY), capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
