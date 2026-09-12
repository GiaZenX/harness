#!/usr/bin/env python3
"""
Approval-provenance gate — the two-phase protocol of spec II.2 ("Beweisbare Freigabe-Herkunft").

A manual `approved_by: user` proves nothing, so an approval only exists if the platform itself
wrote the answer to a question the KERNEL composed. Two events:

  PreToolUse(AskUserQuestion)   a question carrying the marker `[APR-REQ:<id>]` must match the
                               kernel-generated question EXACTLY — text, header, multiSelect and
                               every option label and description. Mismatch blocks.
  PostToolUse(AskUserQuestion) reads the answer the platform recorded and mints the APR, but only
                               for the verbatim approval label with THIS request's mint code.

WHY EXACT STRING EQUALITY AND NOT A SEMANTIC CHECK: the model relays the question, so if it could
paraphrase it, it would control what the user believes they are approving. The comparison is
therefore dumb on purpose — no normalisation, no tolerance. The kernel wrote it; the model may
only pass it through.

MARKERLESS QUESTIONS ALWAYS PASS and never mint (spec II.2/2). That asymmetry is the design: a
model that invents an approval-looking question achieves nothing, because only the marked,
byte-identical path can reach `mint`, and everything downstream is fail-closed.

WHAT THE MINT CODE DOES, and does not: `Freigeben [7f3a2c]` carries per-request entropy that
exists ONLY in the option label — never in the question text — so casual free text ("ok", "ja",
even a typed "Freigeben") can never mint. Claude Code 2.1.219 reports a clicked option and text
typed into the always-present "Other" row identically (spike S2b), which is why entropy in the
label is the available substitute for option identity. Residual, honestly: a user who transcribes
the code deliberately mints — but that user IS the approving authority.

ONE EVENT CAN REFUSE, THE OTHER CANNOT (hooks reference, exit-code-2 table): PreToolUse blocks;
PostToolUse only shows stderr. So prevention lives in the PreToolUse comparison, and the
PostToolUse side protects state by REFUSING TO MINT, never by pretending to block.

AND A REFUSAL TO MINT IS SPOKEN, not merely performed (BUG-0039). On this event stderr reaches
nobody: pilot 3 relayed the approval question in the model's own words, the user clicked
`Freigeben [489405]`, nothing minted — correctly — and no surface told her her yes had evaporated.
`_announce` names the channel that does reach her.

WHAT TRIGGERS THAT MESSAGE IS THE STATE, NOT A SPELLING, and the first cut of this fix got that
wrong in a way worth recording: it asked whether the ANSWER looked like the kernel's approval
label, so a relay that reworded the options ("Ja, freigeben" / "Nein") walked the pilot's hole
again, unannounced. The trigger is now `approvals.open_requests` — this project is waiting on an
approval AND the question that was answered was not that request's (no marker, therefore not it).
It says nothing at all in a project with no request outstanding, and it covers every rewording FOR
AS LONG AS THE REQUEST IS ANSWERABLE: `open_requests` drops one whose TTL has run out, so past that
clock a reworded relay is silent again — measured, and named in
`tools/test_hooks_v2.py::test_an_expired_request_is_not_open_and_a_reworded_relay_goes_silent`.

THE COST OF THAT DEFINITION IS PAID IN THE MESSAGE: an unrelated question answered while a request
is open also lands here, so what the user is told is INFORMATION — an approval is still open and
this was not it — rather than an accusation. The marked path keeps its own, sharper sentences, and
a deliberate `Ändern`/`Ablehnen` on the kernel's own question stays quiet
(`tools/test_hooks_v2.py::test_only_the_requests_own_decline_options_stay_quiet`).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import _kernel
except BaseException as exc:  # noqa: BLE001 — a hook that cannot load must not mean "allow"
    sys.stderr.write("[team-kit hook] refused: could not load hook helpers (%r). Remedy: run "
                     "`python scripts/harness.py doctor`; a partial checkout or half-finished kit update is the "
                     "usual cause.\n" % (exc,))
    sys.exit(2)

import json  # noqa: E402 — everything after GATE_PREAMBLE, which must stay verbatim
import re  # noqa: E402

HOOK = "gate_approval"
TOOL = "AskUserQuestion"
# request ids are uuid4().hex — 32 lowercase hex chars. Anchored and ASCII so a near-miss marker
# is a mismatch rather than a loose partial match.
MARKER_RX = re.compile(r"\[APR-REQ:([0-9a-f]{32})\]", re.ASCII)


def _questions(data):
    """The asked questions. A present-but-malformed `questions` BLOCKS rather than reading as
    "no approval question here" — same reason `_kernel.payload` refuses an unreadable payload."""
    tool_input = data.get("tool_input") or {}
    raw = tool_input.get("questions")
    if raw is None:
        return []
    if not isinstance(raw, list):
        _kernel.block(HOOK, "tool_input.questions is a %s, not a list — this call could not be "
                            "inspected for an approval marker, so it is refused rather than "
                            "waved through (spec II.4 fail-closed)." % type(raw).__name__)
    return raw


def _markers(text):
    return MARKER_RX.findall(str(text or ""))


def _mismatch(built, asked):
    """The first difference between the kernel's question and the one being asked, or None.

    Compared field by field so the block message can name WHAT differs — a bare "does not match"
    on a multi-line question is unactionable, and the user has to be able to see that the text
    they were about to be shown was not the text the kernel wrote.
    """
    # No unknown TOP-LEVEL keys either: if any undocumented question field ever renders (a
    # preview, a context block), it would be text the model wrote on an approval question. The one
    # tolerated difference is a MISSING `multiSelect` — measured against 37 real toolUseResult
    # blobs (Claude Code 2.1.195-2.1.219): the platform drops `multiSelect: false` from its echo in
    # 15 of them, so demanding the key would refuse ~40% of genuine approvals.
    extra = set(asked) - set(built)
    absent = set(built) - set(asked) - {"multiSelect"}
    if extra or absent:
        return "question fields differ (unexpected: %s, missing: %s)" % (
            sorted(extra) or "-", sorted(absent) or "-")
    for field in ("question", "header"):
        if str(asked.get(field) or "") != built[field]:
            return "%s differs\n  kernel: %r\n  asked:  %r" % (
                field, built[field], asked.get(field))
    if bool(asked.get("multiSelect")) != bool(built["multiSelect"]):
        return "multiSelect differs (an approval is a single choice)"
    asked_options = asked.get("options")
    asked_options = asked_options if isinstance(asked_options, list) else []
    if len(asked_options) != len(built["options"]):
        return "option count differs (%d asked, %d generated)" % (
            len(asked_options), len(built["options"]))
    for index, (want, got) in enumerate(zip(built["options"], asked_options)):
        if not isinstance(got, dict):
            return "option %d is not a mapping" % index
        # every key matters: an extra key is content the kernel did not write, and `label` is
        # where the mint code lives
        if set(got) != set(want):
            return "option %d has different fields (%s vs %s)" % (
                index, sorted(got), sorted(want))
        for key in want:
            if str(got.get(key) or "") != want[key]:
                return "option %d %s differs\n  kernel: %r\n  asked:  %r" % (
                    index, key, want[key], got.get(key))
    return None


def handle_pre_tool_use(data):
    if data.get("tool_name") != TOOL:
        sys.exit(0)
    questions = _questions(data)
    marked = [(index, q) for index, q in enumerate(questions)
              if isinstance(q, dict) and _markers(q.get("question"))]
    if not marked:
        sys.exit(0)  # ordinary questions are none of this gate's business
    if len(questions) > 1:
        _kernel.block(
            HOOK,
            "an approval question was bundled with %d other question(s) — refused. Spec II.2 "
            "wants exactly ONE question per approval, so the decision the user makes is "
            "unmistakable and cannot be answered by reflex while dealing with something else."
            % (len(questions) - 1),
            remedy="ask the approval on its own, then ask the rest.")
    index, question = marked[0]
    ids = _markers(question.get("question"))
    if len(set(ids)) != 1:
        _kernel.block(HOOK, "the question carries %d approval markers (%s) — refused, because "
                            "which request is being approved would be ambiguous."
                      % (len(ids), ", ".join(sorted(set(ids)))),
                      remedy="one approval marker per question.")
    request_id = ids[0]
    state = _kernel.open_state(_kernel.find_repo_root(data.get("cwd")))
    approvals = _kernel.kernel_module("approvals")
    try:
        request = approvals.pending_request(state, request_id)
    except approvals.ApprovalError as exc:
        _kernel.block(HOOK, "approval question refused.\n%s" % exc)
    difference = _mismatch(approvals.build_question(request), question)
    if difference is not None:
        _kernel.block(
            HOOK,
            "this approval question is NOT the one the kernel generated for request %s, so it "
            "must not be shown as one — the model does not get to decide what the user is "
            "approving (spec II.2/2).\nDifference: %s" % (request_id, difference),
            remedy="relay the entry point's approval question verbatim; it is generated from the "
                   "pending request and must be passed through unchanged.")
    _kernel.record_note(HOOK, "approval question for %s matched the kernel's" % request_id)
    sys.exit(0)


def _result(data):
    """The platform's AskUserQuestion result blob.

    Read from `tool_response` and `toolUseResult` — the transcript uses the latter name and the
    hook payload the former, and a gate that knew only one of them would silently never mint.
    """
    for key in ("tool_response", "toolUseResult"):
        blob = data.get(key)
        if isinstance(blob, dict) and isinstance(blob.get("answers"), dict):
            return blob
    return {}


def _echoed(result, answered_text):
    """The echo of the question that was ANSWERED, matched by its exact text — or None.

    `toolUseResult` carries exactly two keys: `answers` and `questions`, the echo of what was
    asked (spike S2b, verified against real transcripts). That echo lets the minting side re-run
    the exact-match check instead of trusting that PreToolUse got its say — a hook TIMEOUT there
    is a non-blocking error, so otherwise the one event that moves state would be the one event
    that verified nothing.

    Matched by ANSWERED TEXT, never by the marker: with a marker match, a call carrying
    `[pristine, tampered]` and an answer keyed on the TAMPERED text verified the pristine copy and
    minted anyway — the model would have controlled what the user read while a decoy passed the
    check. The answers key is the full, untruncated question text on this platform, so it is a
    usable join key; the questions echo is not addressed by anything else.
    """
    for question in result.get("questions") or []:
        if isinstance(question, dict) and str(question.get("question") or "") == answered_text:
            return question
    return None


def _user_text_of(approvals, exc):
    """An ApprovalError's sentence for the user — or a last resort that still says the true things.

    A kernel branch that carries none must not fall back into SILENCE, which is the whole of
    BUG-0039; it falls back to the two facts that hold for every refusal (nothing was approved, and
    starting the flow over is a way out) plus an admission that the precise reason is not in plain
    language here. Kept a LAST RESORT rather than the normal answer by
    `tools/test_hooks_v2.py::test_every_approval_refusal_the_hook_can_surface_speaks_to_the_user`,
    which derives the reachable branches from this hook's own calls.
    """
    return getattr(exc, "user_text", None) or (
        "Es wurde keine Freigabe erteilt — dein Klick hat nichts bewirkt. Warum genau, kann das "
        "Programm hier nicht in einfachen Worten sagen. " + approvals.NEXT_START_OVER)


# THE ONE CASE THAT NEEDS NO NOTICE — a deliberate decline on the kernel's own question, appended
# once the request behind the answer is known. A hook process handles exactly one payload, so this
# is a value of the run and not shared state; keeping it here rather than threading it through
# every refusal site is what keeps each of those sites one call. Empty means "not established",
# and that direction announces.
_QUIET = []


def _announce(user_text, model_text):
    """Say a refusal on the channels this event actually has.

    TWO KEYS BECAUSE TWO AUDIENCES, and neither of them is stderr: measured live against
    claude.exe 2.1.227 on 2026-08-15, stderr on this event reaches nobody, `systemMessage` reaches
    the USER and `hookSpecificOutput.additionalContext` reaches the MODEL. The full record with its
    provenance is the harness's `provider_observations.json` → `hook_output_channels`; this
    docstring keeps only the consequence, so the measurement has one home.

    Exit code stays 0. Exit 2 would reach the model's side too, but PostToolUse cannot block and
    this gate does not pretend otherwise (see the module docstring); the protection was never the
    exit code.
    """
    sys.stdout.write(json.dumps({
        "systemMessage": user_text,
        "hookSpecificOutput": {"hookEventName": "PostToolUse",
                               "additionalContext": model_text},
    }))


def handle_post_tool_use(data):
    if data.get("tool_name") != TOOL:
        sys.exit(0)
    result = _result(data)
    answers = result.get("answers") or {}
    if not answers:
        sys.exit(0)  # nothing was answered — nothing to mint and nothing to say
    root = _kernel.find_repo_root(data.get("cwd"))
    if not os.path.isdir(_kernel.state_dir(root)):
        sys.exit(0)
    state = _kernel.open_state(root)
    approvals = _kernel.kernel_module("approvals")
    # The kernel is loaded for an ordinary question too, which it used not to be: the trigger below
    # is a question about this project's STATE, and the cost is one import on an event that only
    # ever follows a human click.
    marked = [(text, answer) for text, answer in answers.items() if _markers(text)]
    if not marked:
        # THE PILOT'S OWN SHAPE (BUG-0039): the relayed question carried no marker at all, so this
        # exit was reached with no note, no stderr and no state change — the purest form of the
        # silence.
        # WHAT DECIDES IS THE STATE: an approval this project is waiting on, answered past. Every
        # question the kernel generates carries its marker, so arriving here already proves the
        # answered question was not the open request's — whatever words the relay used, and whether
        # the model reworded the options or only dropped the marker (neither is measurable here).
        # A project with nothing outstanding says nothing at all, which is what keeps an ordinary
        # question traceless.
        outstanding = approvals.open_requests(state)
        if outstanding:
            _report("%d approval request(s) outstanding and the answered question was none of "
                    "them — nothing to mint, and the user was told (BUG-0039)." % len(outstanding),
                    user_text="Hinweis: eine Freigabe-Frage des Programms ist noch offen und "
                              "unbeantwortet — die Frage, die du eben beantwortet hast, war nicht "
                              "diese, und dabei ist keine Freigabe entstanden. Falls du gerade "
                              "freigeben wolltest: " + approvals.NEXT_ASK_AGAIN)
        sys.exit(0)  # nothing marked was answered — nothing to mint, and that is the normal case
    # exactly one, by construction: the PreToolUse side refuses a bundle, and spec II.2 wants one
    # question per approval. More than one marked answer here means the pair did not go through
    # that gate, so nothing is minted.
    if len(marked) > 1:
        _report("%d answered questions carry approval markers — minting nothing, because an "
                "approval is one deliberate decision (spec II.2)." % len(marked),
                user_text="Es wurde keine Freigabe erteilt: es standen mehrere Freigabe-Fragen "
                          "gleichzeitig zur Wahl, und eine Freigabe muss allein stehen. "
                          + approvals.NEXT_ASK_AGAIN)
    text, answer = marked[0]
    ids = set(_markers(text))
    if len(ids) != 1:
        _report("the answered question carries %d approval markers — not minting, because which "
                "request was approved would be ambiguous." % len(ids),
                user_text="Es wurde keine Freigabe erteilt: die Frage bezog sich auf mehrere "
                          "Freigaben auf einmal, und es wäre nicht eindeutig, welche du erteilt "
                          "hast. " + approvals.NEXT_ASK_AGAIN)
    request_id = ids.pop()
    # Re-run the exact-match on the PLATFORM's echo of what was asked. PreToolUse is where this
    # gets PREVENTED, but this event is the one that MOVES STATE, and a gate that mints on the
    # strength of a sibling event having run is a gate that trusts a process it never saw — so it
    # must not mint on trust alone. No echo means nothing to verify
    # against, which is a refusal rather than a shrug (and on a provider that does not echo, that
    # correctly forces approval_provenance to `unverified` instead of quietly claiming it).
    try:
        request = approvals.pending_request(state, request_id)
    except approvals.ApprovalError as exc:
        _report("no approval was created for request %s.\n%s" % (request_id, exc),
                _user_text_of(approvals, exc))
    # THE ONE ANSWER THAT NEEDS NO NOTICE, decided against THIS request's own options rather than
    # against the shape of what was typed: a user who picked `Ändern` or `Ablehnen` on the kernel's
    # question got the outcome she chose. Everything else that fails to mint — free text, the label
    # with a trailing space, a list — is announced, because from her seat it was a yes.
    _QUIET.append(str(answer) in approvals.declining_labels(request))
    # The one-question rule is enforced HERE too, not left to PreToolUse. The echo makes it free,
    # and bundles are the normal shape rather than an exotic one (measured: 15 of 37 real
    # AskUserQuestion calls in this repo's transcripts carry 2-4 questions). II.2/1 wants exactly
    # one question per approval precisely so the decision cannot be answered by reflex while the
    # user is dealing with something else.
    echoed_all = result.get("questions")
    echoed_all = echoed_all if isinstance(echoed_all, list) else []
    if not echoed_all:
        _report("the platform recorded no copy of the question that was actually answered for "
                "request %s, so there is nothing to verify the answer against — not minting "
                "(spec II.2 wants the approved question provably the kernel's)." % request_id,
                user_text="Es wurde keine Freigabe erteilt: das Programm hat keine Kopie der "
                          "Frage erhalten, die du beantwortet hast, und kann deine Antwort "
                          "deshalb keiner geprüften Frage zuordnen. " + approvals.NEXT_ASK_AGAIN)
    if len(echoed_all) != 1 or len(answers) != 1:
        _report("the approval for request %s was answered as part of a batch of %d question(s) — "
                "not minting. Spec II.2 wants exactly ONE question per approval, so the decision "
                "is deliberate rather than a reflex click."
                % (request_id, max(len(echoed_all), len(answers))),
                user_text="Es wurde keine Freigabe erteilt: die Freigabe-Frage kam zusammen mit "
                          "anderen Fragen, und eine Freigabe muss für sich allein beantwortet "
                          "werden. " + approvals.NEXT_ASK_AGAIN)
    echo = _echoed(result, text)
    if echo is None:
        _report("the platform's question echo does not contain the question that was answered for "
                "request %s — not minting, because the answer cannot be tied to a verified "
                "question." % request_id,
                user_text="Es wurde keine Freigabe erteilt: deine Antwort lässt sich keiner "
                          "geprüften Frage zuordnen. " + approvals.NEXT_ASK_AGAIN)
    difference = _mismatch(approvals.build_question(request), echo)
    if difference is not None:
        _report("the question the user actually answered was NOT the one the kernel generated for "
                "request %s — not minting, whatever the answer said.\nDifference: %s"
                % (request_id, difference),
                user_text="Es wurde keine Freigabe erteilt: die Frage, die du beantwortet hast, "
                          "war nicht Wort für Wort die Freigabe-Frage des Programms. "
                          + approvals.NEXT_ASK_AGAIN)
    try:
        apr = approvals.mint(state, request_id, str(answer))
    except approvals.ApprovalError as exc:
        # The normal, expected outcome for "Ändern"/"Ablehnen"/free text. Reported, not blocked:
        # PostToolUse cannot block, and the protection is that no APR was written.
        _report("no approval was created for request %s.\n%s" % (request_id, exc),
                _user_text_of(approvals, exc))
    # THE CARD IS THE KERNEL'S, not this hook's (`approvals.approval_card`): it reads the stored
    # provenance back out of the record, so what is announced here is what an auditor reading the
    # same file later would read. The SDK route prints the same card from the same composer, which
    # is the point -- the difference between a human's yes and a program's is exactly what must not
    # depend on which surface reports it (FR-0083).
    _kernel.record_note(HOOK, "minted %s for request %s (%s)"
                        % (apr["id"], request_id, approvals.minted_via(apr)))
    sys.stderr.write("[team-kit %s] approval %s recorded for %s.\n%s\n"
                     % (HOOK, apr["id"], apr.get("item") or apr["kind"],
                        approvals.approval_card(apr, state)))
    sys.exit(0)


def _report(message, user_text):
    """Say something on an event that cannot refuse, and audit it — see gate_dispatch._report.

    `user_text` is the SAME refusal for the person who clicked, written by the branch that refused
    (`kernel.approvals.ApprovalError.user_text` for the kernel's own branches). It is emitted
    unless `_QUIET` established that the answer was a deliberate decline. Every refusal site passes
    one —
    `tools/test_hooks_v2.py::test_every_non_minting_exit_of_the_approval_hook_carries_a_user_sentence`
    reads this file's own calls rather than trusting them to stay in step.
    """
    _kernel.record_note(HOOK, message)
    sys.stderr.write("[team-kit %s] %s\n" % (HOOK, message))
    if not (_QUIET and _QUIET[0]):
        if not user_text:
            # A refusal site without a sentence would put this event back where BUG-0039 found it,
            # for that one reason only — so it fails loudly instead of quietly.
            raise ValueError("a refusal the user has to hear must carry a sentence for her; this "
                             "one carried none: %s" % message)
        # THE MODEL'S HALF CLAIMS ONLY WHAT THIS CALL MEASURED — that it minted nothing — and
        # leaves the consequence to the branch's own sentence. "her click did nothing" stood here
        # and was false for the branch where the approval already exists, which is the same
        # over-claim in prose that `_gone_request_user_text` removed from the user's half.
        _announce(user_text,
                  "gate_approval: this AskUserQuestion answer minted NO approval. The user has "
                  "just been shown the sentence below, so say the same thing in her language "
                  "before anything else and then do exactly what it names. Technical reason: "
                  "%s\nShown to the user: %s" % (message, user_text))
    sys.exit(0)


HANDLERS = {
    "PreToolUse": handle_pre_tool_use,
    "PostToolUse": handle_post_tool_use,
}


def main():
    data = _kernel.payload(HOOK)
    event = str(data.get("hook_event_name") or "")
    handler = HANDLERS.get(event)
    if handler is None:
        sys.exit(0)
    # the guard is re-entered with the RESOLVED event: an internal error on an event that cannot
    # block must not be audited as a "block" that never blocked (see _kernel.record_note)
    with _kernel.fail_closed(HOOK, event):
        handler(data)


if __name__ == "__main__":
    _kernel.run_gate(HOOK, main)
