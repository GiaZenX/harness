"""Two kit gaps reported from the field (synaipse-unified, kit 2026.09.13-6) on 2026-09-26, relayed by the user and
measured by the lead read-only. Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "BUG"]

BUGS = [
    {
        "title": "Feld: ein Weg cached Bytecode in das installierte .claude/kernel -- danach gilt das Buendel als "
                 "veraendert, jeder Spezialisten-Start wird verweigert, und die Sitzung kann den Cache nicht "
                 "entfernen",
        "related_pr": "PR-0012",
        "observed": "MEASURED 2026-09-26 (synaipse-unified, kit 2026.09.13-6): `.claude/kernel/__pycache__/` held "
                    "`__init__.cpython-313.pyc` (08:10) and, minutes later, `backlog_types.cpython-313.pyc` -- a process "
                    "was still importing the kit kernel WITHOUT -B / dont_write_bytecode. The synaipse PM: after a test "
                    "run 'gelten die Schutzregeln als veraendert, und es werden keine Spezialisten mehr gestartet'. "
                    "kernel/hashing.py measures bytecode on purpose (a planted .pyc is an importable module) and says "
                    "every route that starts an interpreter over a hashed tree must refuse to cache (the route list is "
                    "tools/test_hooks_v2.py 'is the thing that is HASHED the thing that RUNS?'): this is a route that "
                    "section does not know -- a PROJECT's own test run or script importing `.claude/kernel`. The lead "
                    "removed the cache by hand from outside that project (2026-09-26 ~08:5x).",
        "expected": "(a) Find the route (the project's pytest / scripts importing .claude/kernel; conftest, PYTHONPATH) "
                    "and make the kit's own guidance and the installed layer refuse or neutralise it (e.g. the kit "
                    "ships `sys.dont_write_bytecode` at the kernel package's import, so ANY importer is covered, not "
                    "only the routes the kit starts). (b) RECOVERY from inside the session: deleting a bytecode cache "
                    "can never add code, so a kernel/doctor door that prunes transient caches under the bundle "
                    "(prune_transient) and re-checks the hash is safe to allow the session -- today the only remedy is "
                    "a shell outside Claude Code.",
        "repro": "In an installed project: `python -c \"import sys; sys.path.insert(0, '.claude'); import kernel\"` "
                 "(no -B) -> `.claude/kernel/__pycache__/__init__.cpython-3xx.pyc` -> the session's bundle check reports "
                 "a change and dispatch refuses.",
        "severity": "high",
        "acceptance_criteria": [
            {"id": "AC-1", "text": "importing the installed kernel package from any process without -B writes no "
                                   "bytecode into the bundle -- a test naming this bug, red on 2026.09.25-6"},
            {"id": "AC-2", "text": "a session can clear transient caches under the bundle through a kernel door and "
                                   "the bundle check is green again, without a shell outside Claude Code -- a test "
                                   "naming this bug; the door removes ONLY transient entries (a planted .py is refused)"},
        ],
        "source": "synaipse-unified PM report relayed by the user 2026-09-26; lead's read-only measurement of "
                  "C:/Offline Repos/synaipse-unified/.claude/kernel/__pycache__; team-kits/kernel/hashing.py header",
        "limits": "Im Feld blockiert: in synaipse startet kein Spezialist mehr, bis der Cache von außen entfernt ist. "
                  "Begrenzt: nichts Fremdes läuft -- die Sperre greift zu streng, nicht zu schwach; der Cache ist "
                  "gelöscht, kann aber wiederkommen, solange der unbekannte Weg ohne -B lädt.",
    },
    {
        "title": "Feld: update-kit bricht ab, wenn .claude/settings.local.json ein (leerer) ORDNER statt einer Datei "
                 "ist -- und die Sitzung darf ihn nicht entfernen",
        "related_pr": "PR-0012",
        "observed": "MEASURED 2026-09-26 (synaipse-unified): `.claude/settings.local.json` was an EMPTY DIRECTORY "
                    "(created 2026-09-12 13:57). The update to 2026.09.25-6 aborted on it (synaipse PM), and the "
                    "session may not remove anything under .claude (gate_write_scope). The lead removed the empty "
                    "directory from outside that project (rmdir) on 2026-09-26 ~08:5x.",
        "expected": "update-kit / scaffold treat a path they expect as a FILE but find as a directory explicitly: an "
                    "EMPTY directory is removed and the step continues (it carries nothing); a non-empty one refuses "
                    "with the exact remedy the user runs outside the session. Plus: find who creates such a directory "
                    "(a tool that mkdir-s a settings path).",
        "repro": "mkdir .claude/settings.local.json in an installed project, then update-kit -> abort.",
        "severity": "medium",
        "acceptance_criteria": [
            {"id": "AC-1", "text": "update-kit over an empty directory at .claude/settings.local.json completes; over "
                                   "a non-empty one it refuses with a remedy line -- a test naming this bug, red on "
                                   "2026.09.25-6"},
        ],
        "source": "synaipse-unified PM report relayed by the user 2026-09-26; lead's read-only measurement",
        "limits": "Im Feld blockiert: das Kit-Update lief nicht durch, bis der leere Ordner von außen entfernt war. "
                  "Begrenzt: nichts wird falsch installiert -- das Update bricht vorher ab.",
    },
]

env = dict(os.environ, PYTHONPATH="team-kits")
rc = 0
for body in BUGS:
    result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(body),
                            capture_output=True, text=True, encoding="utf-8")
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr[-1500:])
    rc = rc or result.returncode
sys.exit(rc)
