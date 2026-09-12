"""Re-file the 14 holes the 2026-09-05 migration archived as ACCEPTED_EXCEPTION with `approval: null` --
nobody ever clicked them (measured 2026-09-12 09:4x over archive/bug/*: 14 items, status ACCEPTED_EXCEPTION,
no approval). The archive has no reopen door, so each becomes a NEW hole item (kernel allocates the number;
the old H-number stays in the title and `observed`) under PR-0012, with the old `limits` carried over and the
lead's classification (ja = fixed by the named stream / gesperrt = the user's shell patch / nein = exception
question with a German sentence). The streams measure that classification and may overturn it. Run once."""
import io
import json
import os
import subprocess
import sys

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "BUG", "--hole"]

# old id -> (classification, stream, where the fix lies, plain-German sentence if not fixable here)
PLAN = {
    "BUG-0099": ("ja", "A", "team-kits/kernel/backlog_types.py AUTOMATA done_states + kernel carries_work", ""),
    "BUG-0113": ("ja", "B", "team-kits/*/hooks/gate_write_scope.py directory vocabulary (Push-Location/Pop-Location)", ""),
    "BUG-0114": ("ja", "B", "team-kits/*/hooks read-only classification: the path travels with the stage", ""),
    "BUG-0124": ("ja", "B", "team-kits/*/hooks/gate_write_scope.py prose removal before the substitution reader", ""),
    "BUG-0130": ("ja", "B", "team-kits/*/hooks/gate_write_scope.py _HEREDOC_RX: a heredoc handed to a shell", ""),
    "BUG-0221": ("ja", "B", "team-kits/dev-team/templates/repo/scripts/kit_design_render.py rc 3 + gate_design_sighted", ""),
    "BUG-0131": ("ja", "C", "tools/ + .claude/hooks/test_gates.py: which end states this repo reaches today, measured", ""),
    "BUG-0132": ("ja", "C", ".claude/hooks/test_gates.py: the contract-citation tripwire widened to registration, roles, CLAUDE.md, docs", ""),
    "BUG-0104": ("gesperrt", "-", ".claude/hooks/gate_spawn_needs_item.py (this repo's own gate)",
                 "Ein Unteragent koennte sich die Ausnahme der Startpruefung selbst eintragen; die Stelle liegt in "
                 "einer Schutzdatei dieses Repos, die nur du von aussen aendern kannst."),
    "BUG-0117": ("gesperrt", "-", ".claude/hooks/_harness.py Deadline (this repo's own gate)",
                 "Wer die Schutzdateien schreiben darf, kann auch die Frist hochsetzen, die sich eine Pruefung "
                 "zugesteht; nur du kannst das von aussen aendern."),
    "BUG-0103": ("nein", "-", "a program the shell starts runs code no text reader sees",
                 "Ein Programm, das die Kommandozeile startet, fuehrt Code aus, den keine Textpruefung sieht - das "
                 "kann kein Waechter lesen, der nur die Zeile liest."),
    "BUG-0108": ("nein", "-", "a path held in a shell variable is invisible to a text reader",
                 "Steht der Pfad in einer Variablen, sieht die Pruefung nur den Variablennamen; den Wert kennt nur "
                 "die Shell im Moment des Laufs."),
    "BUG-0188": ("nein", "-", "H11's interpreter class reaches the four-eyes ledger booking",
                 "Dieselbe Luecke wie beim Programm-Start: ein Skript kann eine Buchungszeile eintragen, die niemand "
                 "vorher gelesen hat."),
    "BUG-0200": ("nein", "-", "the provider re-reads the hook registration mid-session",
                 "Das Programm liest seine Schutzregeln mitten in der Sitzung neu ein; wann, entscheidet der "
                 "Anbieter, nicht dieses Repo."),
}

ARCHIVE = os.path.join(ROOT, "project_memory", "archive", "bug")


def old_items():
    for year in sorted(os.listdir(ARCHIVE)):
        folder = os.path.join(ARCHIVE, year)
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".yaml"):
                continue
            with io.open(os.path.join(folder, name), encoding="utf-8") as handle:
                item = yaml.safe_load(handle)
            if item.get("status") == "ACCEPTED_EXCEPTION" and not item.get("approval") and item["id"] in PLAN:
                yield item


def body_for(old):
    cls, stream, where, sentence = PLAN[old["id"]]
    hole = old.get("hole_number")
    title = "%s neu aufgelegt (Ausnahme nie freigegeben): %s" % (hole, old.get("title") or "")
    if cls == "ja":
        expected = ("CLOSED red-first by stream %s with a test that NAMES this bug id (DEC-0100); fix location: %s. "
                    "If the attempt measures it unclosable here, the downgrade carries the measurement and a "
                    "plain-German sentence (never 'later')." % (stream, where))
    elif cls == "gesperrt":
        expected = ("The fix lies in %s, forbidden to every role of this repo: the exact patch goes to the user's "
                    "shell patch file (h182 precedent); until applied, an exception with this sentence: %s" % (where, sentence))
    else:
        expected = ("Not closable in this repository (%s): an accepted exception the USER clicks, asked with this "
                    "sentence: %s" % (where, sentence))
    return {
        "title": title[:240],
        "related_pr": "PR-0012",
        "observed": ("Migrated 2026-09-05 as %s into %s with status ACCEPTED_EXCEPTION and approval null -- the user "
                     "never saw a question for it (measured 2026-09-12 over archive/bug/*). Original finding: %s"
                     % (hole, old["id"], (old.get("observed") or "")[:1200])),
        "expected": expected,
        "repro": "read %s (status ACCEPTED_EXCEPTION, approval: null); the mechanism: %s" % (old["id"], old.get("source") or "-"),
        "severity": old.get("severity") or "medium",
        "acceptance_criteria": [
            "AC-1: the item ends VERIFIED on a passing test that names it, or ACCEPTED_EXCEPTION on a request the "
            "user answered -- never on a migration",
            "AC-2: if an exception, its `limits` is the plain-German sentence a non-developer understands",
        ],
        "source": "archive %s; staging/generation-6/refile_unclicked_exceptions.py (lead classification: %s, stream %s)"
                  % (old["id"], cls, stream),
        "limits": sentence if sentence else (old.get("limits") or ""),
        "supersedes": old["id"],
    }


def main():
    env = dict(os.environ, PYTHONPATH="team-kits")
    for old in old_items():
        result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(body_for(old)),
                                capture_output=True, text=True, encoding="utf-8")
        print(old["id"], "->", (result.stdout.strip() or result.stderr.strip())[-200:])


if __name__ == "__main__":
    main()
