"""Capture the user's finding of 2026-09-06: the approval questions the kits put to him read as garbled
German/English machine text. Measured against kernel/approvals.py build_question: the sentence frame is German,
but it carries the English kind name, a sha256 prefix, a request id twice, a YAML path and -- for manifest
subjects -- a bracket list of English field names; the gate then forces the PM to relay it character for
character. Body on stdin to `kernel.cli capture BUG`. Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "BUG"]

BODY = {
    "title": "Die Freigabe-Frage der Kits ist Maschinendeutsch: englische Freigabe-Art, Hash, Anfrage-Id (zweimal), "
             "YAML-Pfad und englische Feldnamen in einem deutschen Satz -- und das Gate zwingt den PM, genau diesen "
             "Text wortgleich zu stellen",
    "related_pr": "PR-0003",
    "observed": "USER 2026-09-06: 'Wurde in den Kits behoben, dass die bei den Fragen bei der Freigabe ganz wirre "
                "komische Texte auf Englisch+Deutsch schreiben?' -- NOT fixed, and not an accident of one PM turn: "
                "kernel/approvals.py build_question renders, deterministically, 'Freigabe erbeten: <kind> für "
                "<target> (Revision <n>, subject_manifest sha256 <12 hex>…). Details: approvals/pending/<id>.yaml "
                "[APR-REQ:<id>]' with <kind> an English enum value (scope, delivery, acceptance, plan, routine, "
                "preset, filing_rule …), <target> the item id or -- for a manifest subject -- '[allowed_paths: …, "
                "expires_at: …, role: …]' with English field names, and the option descriptions repeat the kind "
                "('Erteilt die scope-Freigabe für …'). gate_approval.py (PreToolUse) compares question, header and "
                "every option character for character with this text, so the PM cannot say it in plain German even "
                "when it wants to. The one form that reads well is the item form: a PR shows its German title "
                "(TARGET_FORMS, BUG-0041's fix for 'preset'). The user has seen this in every pilot and in this "
                "repo's own mints (five scope + four delivery mints on 2026-09-06). BUG-0046 covers a different leak "
                "(specialist narration); FR-0048 carries the rule ('every sentence to the user is German; an "
                "identifier does not make the sentence English') -- this question is the kernel itself breaking it.",
    "expected": "The question a non-developer answers is a German sentence a non-developer can judge: WHAT is being "
                "approved (the kind in plain words from ONE translation table beside the enum -- 'Arbeitsbereich', "
                "'Lieferung', 'Abnahme', 'Plan', 'Dauer-Erlaubnis', 'Teamgröße', 'Ablage-Regel'), FOR WHAT (the "
                "item's title, or the manifest rendered with German labels from the same table), and the one code "
                "the mint needs; the hash prefix, the request id and the YAML path move out of the question into the "
                "option description or the details line, where the gate can still compare them -- determinism kept, "
                "verbatim enforcement kept, the sentence human. The translation table is measured both ways (a kind "
                "without a label is red; a label without a kind is red), so the enumeration carries its tripwire.",
    "repro": "Any kit project: `kernel.cli request-approval scope PR-0001` then the PM's AskUserQuestion -- read the "
             "question text; in this repo: the five scope mints of 2026-09-06 (staging scratch approval_question.json).",
    "severity": "medium",
    "acceptance_criteria": [
        "AC-1: build_question yields a German sentence with no English enum value, no hash and no request id in the "
        "question text; the mint code stays in the option label; a test renders every kind and every TARGET_FORM and "
        "refuses an English enum word or a hex run in the sentence",
        "AC-2: the gate still compares character for character, and the moved details (hash, id, path) are still "
        "part of what it compares (option description or a details field) -- red-first: a tampered description is "
        "refused",
        "AC-3: the kind-to-label table has the two-sided tripwire (kind without label red, label without kind red)",
    ],
    "source": "user message 2026-09-06 evening; kernel/approvals.py build_question (:1744) and TARGET_FORMS; BUG-0041; "
              "BUG-0046; FR-0048; the mints of 2026-09-06",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
