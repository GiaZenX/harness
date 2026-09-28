"""User 2026-09-28 ~21:5x: effort per role -- planners deep, builders medium, escalate on need. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Denktiefe je Rolle: PM, Architekt und Designer (erster Entwurf) auf xhigh -- sie legen die Details und "
             "damit die Genauigkeit fest; Bauer mit klarer Vorgabe und Test auf medium; hochgestuft wird bei Bedarf; "
             "der PM-xhigh-Default wird gemessen",
    "context": "User 2026-09-28: 'Der PM verteilt Aufgaben und traegt dazu bei wie sie zu loesen sind mit seinen FR "
               "und SR TSK usw. deshalb wuerde ich ihn vermutlich auf xhigh setzen, er gibt massgeblich die "
               "Codegenauigkeit vor ... Genauso der Designer. Beim ersten Entwurf ist mehr Detail besser ... wenn man "
               "den ersten Entwurf setzt und Aenderungen anfordert, ist es ziemlich zaeh ... Die Bauer auf Medium ist "
               "glaub gut ... Im Notfall wird halt hochgestuft.' Research FR-0097 (staging/FR-0097/research-effort-by-"
               "role-2026-09-28.md): builders on Opus 5.5 medium with a spec+test are well supported; 'planners on "
               "xhigh' is NOT proven by the source -- clarity came from the interview with the human and the spec; "
               "Anthropic: xhigh only where a gain is measured. The orchestrating PM session is the largest token "
               "consumer (DEC-0095).",
    "decision": "(1) PM: xhigh (it writes the SR/TSK cut and the order text the builders follow). (2) Architect: xhigh "
                "(DEC-0118). (3) Designer: xhigh for the FIRST draft of a screen/flow; revisions at high. (4) Builder "
                "with a spec and a test acceptance: medium; builder on an unclear spec or a bug hunt: high; Kilo "
                "(Sonnet) builder: high. (5) Verifier: high. (6) Escalation: a MISSED case raises effort one step; a "
                "MISREAD requirement goes back to the PM/planner with a question to the user (more effort does not fix "
                "a wrong reading). (7) The planning step keeps the interview with the user before the spec (the "
                "research's main lever). (8) MEASURED, not assumed: the harness of stream C compares PM xhigh vs high "
                "and builder medium vs high on fixed tasks (quality, rounds, tokens); a default that shows no gain "
                "for its cost is put back to the user with the numbers.",
    "consequences": "More tokens per PM turn, fewer build/verify rounds expected. Stream C sets the defaults in the "
                    "role variants (subagent frontmatter `effort:`; Codex model_reasoning_effort) and in the PM "
                    "session binding.",
    "work": ["PR-0012"],
    "source": "user message 2026-09-28; FR-0097 research report; DEC-0088 (4) (superseded in part: xhigh is now a "
              "standing setting for the planning roles); DEC-0118",
}

env = dict(os.environ, PYTHONPATH="team-kits")
r = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY), capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
