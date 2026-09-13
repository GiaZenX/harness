"""The DONE side of a derived duty -- what a project records when a dated obligation was met
(BUG-0197 / H113, shape frozen in `project_memory/staging/TSK-0146/protocol.md` row 6).

WHAT WAS MISSING AND WHAT IT COST. A kit's duty register DERIVES what is owed out of the records a
business already keeps -- a filing period that closed, an archive year past its retention, an
unpaid invoice, a review date. Two of those five feeds have no switch-off condition of their own: a
closed tax period stays closed and an expired retention year stays expired, so the duty stood until
its SOURCE changed, and nothing in a kit could say "submitted on the 10th". A register that keeps
naming what has been done is a register that gets switched off, and then it protects nothing.

WHY A CONTENT-ADDRESSED KEY AND NOT AN ID. A duty is DERIVED and stored nowhere, so a done record
cannot point at an item that exists -- it has to carry something both sides re-derive from the same
three facts: which FEED found the duty, which SOURCE it read, and WHICH ONE of that source's duties
it is (`period`). That is the construction `gaplog.entry_id` already uses for an entry nobody can
number, and for the same reason: the same duty derived again is the same key, so a second `done` is
not a second record, and next period's duty -- a different `period`, a different digest -- appears
by itself with nothing to expire.

WHAT A RECORD CARRIES AND WHY NOTHING ELSE. `duty_key`, the `what` sentence as it stood when it was
closed (a reader a year later cannot re-derive the wording of a feed that has since changed),
`done_at`, and the `note` that says what actually happened. No `kind:`, no vocabulary -- P4-12 is
what an enumerated vocabulary in a kit document costs when a real business meets a case it does not
carry.

THE KERNEL IS THE WRITER, like every other canonical record: `gate_write_scope` refuses every agent
write under the state root, so the role runs a COMMAND and the command writes. The log sits in
`.audit/` beside `kit_gaps.jsonl`, an area no template ships.

WHAT THIS DOES NOT DO, said rather than left to be found: it does not check that the key names a
duty that exists. The feeds live in the kit and the kernel does not run them, so a key for a duty
nobody derives is an inert line -- it hides no duty, because the register only ever drops the key
it computes for a duty it just found.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

from .state import ProjectState, StateError

COMMAND = "duty-done"
LOG_DIR = ".audit"
LOG_NAME = "duties_done.jsonl"
# THE THREE FACTS THAT MAKE A DUTY THIS DUTY -- named once, so the writer here and the reader in a
# kit's register cannot come to key the same duty differently. `period` is whatever distinguishes
# one duty of a feed+source from the next AND STAYS THE SAME FROM DAY TO DAY: a filing period, the
# oldest expired year, an invoice number. A part that moves with the clock (a "5 days overdue"
# count) would give the same duty a new key every morning and make every done record dead by noon.
KEY_PARTS = ("feed", "source", "period")
KEY_LENGTH = 16
# Per-field bound, the same argument as `gaplog.MAX_FIELD`: a duty sentence and a note about it run
# to a few hundred characters; a pasted transcript is not a record and is cut with a marker.
MAX_FIELD = 2000
# The bound on the whole log, and the same reason as the gap log's: past it the command REFUSES
# rather than appending, because a log that silently drops its newest lines is worse than one that
# says it is full.
MAX_LOG_BYTES = 512 * 1024


def log_path(state: ProjectState) -> str:
    return os.path.join(state.root, LOG_DIR, LOG_NAME)


def _cut(value) -> str:
    text = " ".join(str(value if value is not None else "").split())
    if len(text) <= MAX_FIELD:
        return text
    return text[:MAX_FIELD] + " ...[cut at %d characters]" % MAX_FIELD


def duty_key(feed, source, period) -> str:
    """The identity of one derived duty, from the three facts of `KEY_PARTS` and nothing else.

    THE ONE PROPERTY THIS READER MEASURES: two duties get the same key exactly when all three parts
    are the same string, so the key is idempotent for a duty derived again and distinct for the
    next one. Each part carries its own mutation row --
    `tools/test_office_duties.py::test_a_duty_key_moves_with_each_of_its_three_parts_and_with_nothing_else`
    changes one part at a time and asserts the key moves, and asserts the key does NOT move for the
    parts of the duty that are not in the material (the sentence, the due date, the clock).

    THE CLOCK IS DELIBERATELY OUT OF IT, exactly as in `gaplog.entry_id`: the same duty seen again
    tomorrow is the same duty, and a key that moved overnight would resurrect every done record's
    duty the next morning.
    """
    material = "\x1f".join(_cut(part) for part in (feed, source, period))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:KEY_LENGTH]


def done_keys(root: str) -> set:
    """Every duty key this project has recorded as done -- the READER half, as a set.

    Takes a ROOT and not a `ProjectState` for `gaplog.entries`' reason: the caller is a kit HOOK
    reading the project it runs in, and constructing a state object would validate a store this
    reader has no business judging. An unreadable or absent log is an EMPTY set, which leaves every
    duty standing -- the over-reporting direction, and the only safe one for a register.
    """
    found = set()
    try:
        with open(os.path.join(root, LOG_DIR, LOG_NAME), encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except ValueError:
                    continue
                if isinstance(parsed, dict) and parsed.get("duty_key"):
                    found.add(str(parsed["duty_key"]))
    except OSError:
        return set()
    return found


def records(root: str) -> list:
    """Every done record the log at `root` holds, oldest first -- for a reader that wants the note
    and not only the key (the browser, a report, a human reading the file)."""
    found = []
    try:
        with open(os.path.join(root, LOG_DIR, LOG_NAME), encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except ValueError:
                    continue
                if isinstance(parsed, dict) and parsed.get("duty_key"):
                    found.append(parsed)
    except OSError:
        return []
    return found


def record_done(state: ProjectState, key: str, what: str, note: str) -> dict:
    """Append one done record. Idempotent on the KEY, like `gaplog.record` on its entry id.

    Returns the record with `recorded` False when the key was already there, so the caller prints
    that instead of pretending to have written something -- a duty marked done twice is one duty.
    """
    key = _cut(key)
    if not key:
        raise StateError(
            "a done record needs the duty's KEY: the duty itself is derived and stored nowhere, so "
            "the key is the only thing both sides can re-derive. Remedy: the deadline register "
            "prints it beside each duty -- run `%s --key <that digest> --what \"<the duty>\" "
            "--note \"<what happened>\"`." % COMMAND)
    what, note = _cut(what), _cut(note)
    if not what or not note:
        raise StateError(
            "a done record needs `what` and `note`: without the first, a reader a year from now "
            "cannot re-derive the wording of a feed that has changed since; without the second the "
            "record says a duty ended and not how (`Voranmeldung Q3 am 10.10. uebermittelt`). "
            "Remedy: run `%s --key %s --what \"<the duty>\" --note \"<what happened>\"`."
            % (COMMAND, key))
    with state.lock:
        if key in done_keys(state.root):
            already = [one for one in records(state.root) if str(one.get("duty_key")) == key]
            result = dict(already[-1])
            result["recorded"] = False
            return result
        path = log_path(state)
        try:
            if os.path.exists(path) and os.path.getsize(path) >= MAX_LOG_BYTES:
                raise StateError(
                    "%s has reached its %d byte bound, so nothing was appended -- a log that "
                    "silently dropped its newest records would be worse than one that says it is "
                    "full. Remedy: report this to the user; the file is plain JSONL and pruning it "
                    "is a decision, not a repair."
                    % (os.path.join(LOG_DIR, LOG_NAME), MAX_LOG_BYTES))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            written = {"duty_key": key, "what": what, "note": note,
                       "done_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(written, ensure_ascii=False, sort_keys=True) + "\n")
        except OSError as exc:
            raise StateError(
                "the duty-done log could not be written (%s), so this duty is recorded NOWHERE and "
                "the register will keep naming it -- say that to the user in the same turn. "
                "Remedy: report the write failure with the path %s." % (exc, log_path(state))
            ) from None
    result = dict(written)
    result["recorded"] = True
    return result
