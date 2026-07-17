#!/usr/bin/env python3
"""
PreToolUse(AskUserQuestion) guard — a question must never point at INVISIBLE context.

A real PM asked "Kategorien-Set freigeben (wie oben zusammengefasst)?" — but the whole turn
before the question was thinking + tool calls, no visible text: the summary the question
referenced existed only in the model's (hidden) thinking, so the user got a bare dialog
deciding about content they never saw. This guard blocks question/option text that refers to
"above"/"as summarized" style context. The rule it enforces (PM skill): the full decision
context is either visible TEXT in the SAME message before the question, or lives inside the
question and its option descriptions — thinking does not count, and "oben" is never a place.

Any uncertainty -> exit 0 (never block legitimate questions).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _audit

# References to context OUTSIDE the question itself (German + English variants seen in real
# transcripts). Deliberately narrow: "wie besprochen" (the user SAW that dialogue) stays legal;
# the guard targets references to PM-produced artifacts ("wie zusammengefasst") and spatial
# "above" references — the question dialog renders detached from prose, so a question must be
# self-contained. Missing prose like "the above-average latency" is fine to block-miss.
_INVISIBLE_REF_RX = re.compile(
    r"\bwie\s+oben\b"
    r"|\bsiehe\s+oben\b"
    r"|\bs\.\s?o\.\B"
    r"|\boben\s+(?:zusammengefasst|beschrieben|genannt|erwähnt|dargestellt|erläutert|skizziert)\b"
    r"|\bwie\s+(?:gerade\s+|eben\s+|zuvor\s+)?(?:zusammengefasst|dargestellt|skizziert)\b"
    r"|\bsee\s+above\b"
    r"|\bas\s+(?:discussed|summarized|summarised|described|outlined|explained|shown)\s+above\b"
    r"|\bthe\s+above\s+(?:summary|proposal|list|plan)\b",
    re.IGNORECASE)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") != "AskUserQuestion":
        sys.exit(0)
    ti = data.get("tool_input") or {}
    texts = []
    for q in (ti.get("questions") or []):
        if not isinstance(q, dict):
            continue
        texts.append(str(q.get("question") or ""))
        for o in (q.get("options") or []):
            if isinstance(o, dict):
                texts.append(str(o.get("label") or ""))
                texts.append(str(o.get("description") or ""))
    hits = sorted({m.group(0) for t in texts for m in _INVISIBLE_REF_RX.finditer(t)})
    if not hits:
        sys.exit(0)
    _audit.record("guard_question_context", "; ".join(hits)[:200])
    sys.stderr.write(
        "[team-kit guard] Blocked AskUserQuestion: it references context the user CANNOT see "
        "(%s). Your thinking and earlier tool calls are invisible — a real PM once asked for "
        "sign-off on a summary that was never printed. Fix: put the full decision context as "
        "visible TEXT in this same message BEFORE the question, or make the question "
        "self-contained (details into the question text and option descriptions), then ask "
        "again without the reference.\n" % ", ".join("'%s'" % h for h in hits[:4])
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
