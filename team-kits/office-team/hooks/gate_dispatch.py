#!/usr/bin/env python3
"""
Dispatch gate — gate layer 2 of spec II.4. Registered on SIX events -- the first of them
on two tool classes -- because the dispatch lifecycle is one story and splitting it across files
would let the halves drift:

  PreToolUse(Bash|PowerShell)   refuse a FAIL CLASSIFICATION written by anybody but the bound
                                child of the judging class (DEC-0107) -- a shell question answered
                                here because who is running is read off the leases this gate writes
  PreToolUse(Agent|Task)        reconcile claims that never produced a child; refuse while the
                                installed enforcement bundle is not the one this project recorded
                                trust for (`_kernel.bundle_trust`); then validate the
                                HARNESS_DISPATCH header against the lease and CLAIM the lease for
                                this one dispatch, which opens the bind window; for a BUILD-class
                                lease hand the model the fact-based checkpoint (DEC-0092 (3)) as
                                context on the allowed call -- a mirror, never a refusal
  SubagentStart(*)              bind that lease to the child's agent_id (gate layer 3 needs the
                                agent_id -> task mapping while the child is still running)
  PostToolUse(Agent|Task)       the spawn STARTED: re-verify the header, bind the agent_id
                                authoritatively (here the header and the agentId arrive
                                together), and move the task to IN_PROGRESS
  PostToolUseFailure(Agent|Task) the spawn did NOT start: return the task to READY at once and
                                close the bind window — an ACCELERATOR, not the guarantee
  SubagentStop()                record that this dispatch's child has STOPPED, so the end of a
                                later turn has a RECORD to read where it otherwise has only a
                                status that says IN_PROGRESS either way (BUG-0058)
  Stop()                        reconcile again at the end of the turn, so a claim that produced
                                no child does not wait for the next spawn attempt to be noticed —
                                and refuse ONE turn-end per dispatch the records say has no
                                child on it

WHAT THIS GATE PARSES: the header, and only the header (spec II.4). Free prompt prose is never
evidence of anything — the V1 `guard_agent_spawn` keyword check is exactly the "looks approved"
failure this replaces. A spawn without a header is refused; a spawn whose header names a task
that is not leased to it is refused.

WHICH EVENTS CAN ACTUALLY REFUSE (hooks reference, exit-code-2 table — this decides the whole
design, so it is written down rather than assumed): PreToolUse blocks. PostToolUse,
PostToolUseFailure, SubagentStart and SubagentStop do NOT stop what they are about — their stderr
is shown and the action stands. Stop does block: exit 2 there makes the assistant keep going
rather than end its turn, and this gate uses it for exactly ONE thing, the one thing "keep going"
is the right answer to — a dispatch whose own records say no child is on it, which the lead was
about to leave unmentioned for another turn (BUG-0058,
`_name_the_dispatches_the_records_say_nobody_is_on`). It does NOT use it for the
reconciliation beside it: "a lease was returned to READY" is no reason to refuse
somebody's turn. So prevention of a TOOL CALL still lives in PreToolUse alone. In the later events
this gate protects the only thing it still can: it REFUSES TO MUTATE STATE on anything it cannot
verify, and says so on stderr. Calling that a "block" would be theatre, and theatre is what V2 is
removing.

THE ROLLBACK DOES NOT DEPEND ON ANY EVENT, and it used to. Measured 2026-08-02 across twelve real
headless sessions with an observer on eleven events: `PermissionDenied` fired NOT ONCE — neither
after a hook refusal nor after a permission refusal (the stream counted the denial and no hook
saw it), while `PostToolUseFailure` registered from the same file with the same matcher shape did
fire. The claim was previously an eternal flag undone only by `PostToolUseFailure|PermissionDenied`,
so a refused spawn stranded its task for the remaining ~900 s of the lease TTL. What returns a
spent claim now is time: `dispatch.spent_claim_reason` says when a claim still stands and
`dispatch.reconcile_unstarted_dispatches` returns the task to READY when it does not. The two
events above only make that verdict arrive sooner.

AND A CLAIM IS NOT MADE UNTIL EVERY HARNESS REFUSAL IS KNOWN. Also measured: every PreToolUse
hook of one event runs to completion even when a sibling exits 2, so this gate used to spend the
lease while another gate of the same event was refusing the very same spawn. The kits therefore
register the PreToolUse(Agent|Task) gates as ONE chained command with this one LAST (see
`_gate.py`); which gates precede it is each kit's business, and office has four where dev has two.

THE PLATFORM LIMIT, stated plainly: SubagentStart carries `agent_id`, `agent_type` and
`prompt_id`, but no key back to the tool call that started it — no tool_use_id, no prompt
(verified against the S3 spike payloads and the hooks reference). So the child is matched to its
lease by ROLE, within a window narrowed by `prompt_id`. Two concurrent dispatches of the SAME
role inside ONE turn stay ambiguous, and the kernel refuses to guess rather than binding one
specialist's writes to another's allowed_scope. Consequence, honestly: such a child starts
UNBOUND (SubagentStart cannot stop it) and the write-scope gate refuses its writes. Different
roles in parallel are unaffected.

The GATE_PREAMBLE below must stay the first executable statement — see _kernel.py for why. Only
the docstring may precede it, because a docstring cannot fail.
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

import json  # noqa: E402 — after GATE_PREAMBLE, which must stay the first executable statement
import re  # noqa: E402 — same reason

import _compat  # noqa: E402

HOOK = "gate_dispatch"
SPAWN_TOOLS = ("Agent", "Task")
# A spawn SUCCEEDED when the child was launched — not when it finished. Measured on Claude Code
# 2.1.219: a synchronous spawn reports status "completed", while `run_in_background: true` (the
# platform's own default, which a real run hit 37/37 times by omission) reports "async_launched"
# with isAsync: true. Treating anything-but-"completed" as failure sent every background
# specialist's task back to READY while the child was still running: unbound, so every write
# refused, and the freed task immediately re-leasable — breaking the very "second claim blocked"
# rule this gate enforces. A tool call that FAILS arrives as PostToolUseFailure; a call the
# permission layer refuses arrives as nothing at all, which is why the rollback does not wait for
# an event (see the module docstring and `dispatch.reconcile_unstarted_dispatches`).
STARTED_STATUSES = ("completed", "async_launched")


def _state_for_prevention(data):
    """The project state, or a BLOCK. Only for PreToolUse, the one event that can refuse."""
    root = _kernel.find_repo_root(data.get("cwd"))
    if not os.path.isdir(_kernel.state_dir(root)):
        if _kernel.bootstrap_active(root):
            return None  # explicit installer/migration window (spec II.4)
        _kernel.block(
            HOOK,
            "no canonical project state — refusing to authorise a specialist spawn against a "
            "state that does not exist (spec II.4 fail-closed; the V1 gate let spawns through "
            "on an empty store, which is the hole this closes).",
            event="PreToolUse",
            remedy="initialise the project via the installer/scaffold, the only path that may "
                   "run with an empty state.")
    return _kernel.open_state(root)


def _state_for_recording(data):
    """The project state, or None. For the events that can only RECORD, never refuse — with no
    state there is nothing to record, and a refusal they cannot enforce would be noise."""
    root = _kernel.find_repo_root(data.get("cwd"))
    if not os.path.isdir(_kernel.state_dir(root)):
        return None
    return _kernel.open_state(root)


def _refuse_untrusted_bundle(data):
    """No delegation while the enforcement bundle is not the one this project trusts.

    THE HOLE THIS CLOSES, measured 2026-08-01: `.claude/kit_state.json` was WRITTEN by the
    scaffold and by `kit_trust_state`, and read by exactly two places — `kernel/report.py` for the
    doctor's `hook_trust` capability and `guard_harness_selfmod` for its write-protection list.
    No authorising code path read it. An ablation over four trust states with one identical spawn
    payload produced four identical verdicts with identical reasons: the trust record was not a
    term in the decision, so a project could delegate on a bundle it had never vouched for.

    A SPAWN is where it binds, because a spawn is the moment the harness hands a task's
    `allowed_scope` to a child — the grant every downstream gate is measured against. What
    `withdrawn` means is `_kernel.bundle_trust`'s business, and deliberately: this file must not
    grow a second opinion about which trust states are which.
    """
    trust = _kernel.bundle_trust(_kernel.find_repo_root(data.get("cwd")))
    if not trust.withdrawn:
        return
    _kernel.block(
        HOOK,
        "specialist spawn refused: %s.\nDelegation hands a child the task's `allowed_scope`, and "
        "the gates that would hold it to that scope are the very files whose integrity is in "
        "question — so no spawn is authorised until somebody has vouched for the bundle again."
        % trust.reason,
        event="PreToolUse",
        remedy="open /hooks and review what changed in `.claude/hooks` and `.claude/kernel`; if "
               "the change is not yours, treat it as a finding. Re-running the scaffold "
               "reinstalls the kit files and records the reviewed bundle; then start ONE new "
               "session. ASK THE USER TO RUN IT — `gate_write_scope` refuses a WRITE-CAPABLE "
               "command line that names the enforcement layer, and starting a script is one, so "
               "this session cannot run the scaffold itself; and no number of new sessions "
               "clears the state without it. "
               "`python scripts/harness.py doctor` reports the same state as `hook_trust`.")


def _refuse_while_a_restart_is_pending(data):
    """No delegation while an installer has changed this project and no session has started since.

    THE WINDOW, measured 2026-08-16 against a real scaffold over a live project: `.claude/hooks`
    and `.claude/kernel` are the new kit's from 1.6 s into a 3.4 s run, while the REGISTRATION in
    `settings.json`, the agent set and the session agent stay whatever this session started with.
    A spawn in that window hands a child a task's `allowed_scope` under a rule set that is half one
    release and half another -- and the child's own definition is read from the file the installer
    just replaced.

    THE MARKER IS THE SIGNAL AND ITS ABSENCE IS THE ALL-CLEAR, which is what makes this cheap and
    invisible: `clear_handover_marker` removes it on a SessionStart whose source is `startup`, so
    outside such a window this costs one `os.path.exists`. The global
    `~/.claude/hooks/handover_guard.py` refuses the same act on the same file; this one is the
    kit's own, so a project whose user never installed the global half is not left with the
    handover unenforced (measured: `tools/test_kitupdate.py::test_the_marker_this_command_leaves_
    really_stops_the_session` runs both hooks as processes).

    NO KERNEL IS ASKED, deliberately: a half-finished kit update is exactly the state in which the
    kernel may be mid-copy, and a check that needed it would fail closed with a message about the
    wrong thing.
    """
    marker = os.path.join(_kernel.find_repo_root(data.get("cwd")), _compat.HANDOVER_MARKER)
    if not os.path.exists(marker):
        return
    _kernel.block(
        HOOK,
        "specialist spawn refused: %s exists, so an installer changed this project's kit files "
        "during this session and no session has started since. The hooks on disk are the new "
        "release's while this session's registration, agent set and session agent are the old "
        "one's, so what a child would be held to is not what this session was started under."
        % _compat.HANDOVER_MARKER.replace(os.sep, "/"),
        event="PreToolUse",
        remedy="end this session and start a new one in this folder -- the marker clears itself on "
               "a real restart, and the work is picked up there. Tell the USER that this is what "
               "is needed; nothing else clears it, and deleting it by hand only removes the sign.")


# DEC-0107 (the user's answer b to H178/BUG-0260: "mit Hook gemessen, keine Gewohnheitsaktionen"):
# a QA fail the verifying role calls MECHANICAL does not climb the rung, and the classification is
# a field only that role may write. The kernel refuses what the STATE can see -- the role the bound
# lease names (`dispatch.fail_class_refusal`) -- and that leaves exactly one writer it cannot see:
# the session instance itself, typing the command while a specialist's lease is bound. A field the
# judged role can set is a discount it grants itself, so the hook measures the WRITER and the
# kernel measures the record. Which roles may write it is not decided here either: the class
# vocabulary is `dispatch.QA_CLASS` against the kit's own `ladder.yaml` declaration, so one rule
# has one home.
# `tools/test_hooks_v2.py::test_the_fail_classification_is_refused_from_every_writer_but_the_verifying_one`
# `tools/test_hooks_v2.py::test_an_everyday_line_that_only_looks_like_a_classification_is_left_alone`
_OPTION_RX = re.compile(r"(?<![\w-])--[A-Za-z][\w-]*")


# The kernel subcommand that writes the classification. The hook keeps the word for the same reason
# it keeps the entry point's name -- a Bash call must not import argparse to answer "which command
# is this" -- and it is pinned against the shipped parser by
# `tools/test_hooks_v2.py::test_the_gate_knows_the_command_that_writes_the_classification`.
_EVIDENCE_COMMAND = "evidence"
# A word the SHELL builds before any program sees it: a parameter expansion, a command
# substitution, a backtick. `gate_write_scope` refuses such a word wherever it could name a path and
# states the reason at length (`_compat._UNDETERMINED_CHARS`): the text this reader holds is not the
# text the program is handed. NARROWER HERE on purpose -- no glob and no brace -- because on an
# `evidence` line those name a path, while these three can produce the option itself.
_UNPLACEABLE_RX = re.compile(r"[$`]")
# A MASK for one quoted span: a character that can be neither an expansion nor a word separator,
# so a masked span cannot look like either. The masking itself is `_compat`'s (`_SPAN_RX`),
# borrowed rather than rewritten -- a second answer to "which part of this word is quoted" is drift
# this repository has already paid for, and `_compat` names the borrowing in its own block comment.
_QUOTED_SPAN = "\x01"
_LONG_OPTION_RX = re.compile(r"^--[A-Za-z][\w-]*$")

WRITTEN = "names the classification"
UNREADABLE = "carries a word the shell builds, so whether it classifies cannot be read"


def _takes_a_value(word, options):
    """Does `word` name -- by argparse's own PREFIX rule -- an option of `options` that eats the
    next word? Ambiguous and unknown both answer no, which is the fail-closed direction here."""
    if not _LONG_OPTION_RX.match(word):
        return False
    hits = [option for option in options if option == word or option.startswith(word)]
    return len(hits) == 1


def _an_expansion_stands_where_it_could_be_an_option(text):
    """True when an expansion on this `evidence` line could reach the parser as an OPTION.

    THE CORRECTION OF A MEASURED OVER-REFUSAL (verifier of TSK-0147, round 2, F3): every `$` and
    every backtick anywhere on an `evidence` line was refused, so `--run-command "$(cat cmd.txt)"`
    and `--related "$ID"` -- lines the QA role writes daily -- came back rc 2 at both pilots. What
    the rule is about is whether the shell can hand the PARSER an option nobody wrote, and that is
    a question of POSITION and not of a character being present:

      * an UNQUOTED expansion word-splits, so what it produces can start a fresh word in option
        position -- unreadable, whatever stands before it;
      * a DOUBLE-QUOTED expansion is exactly one word, so it can be read as an option only where
        the parser is not already consuming it as the VALUE of the option before it (or of an
        `--option=` assignment it stands inside). WHICH options consume a value is the parser's own
        answer (`kernel.cli.value_taking_options`) and not a list kept in three hook copies;
      * a SINGLE-QUOTED `$` is no expansion at all and never was.

    STILL UNREADABLE, and this case is what keeps the narrowing honest:
    `a="--"; b="fail-class"; ... --related TSK-0001 "$a$b" mechanical` is quoted AND stands in no
    value position, so it is refused exactly as before (measured in round 1, F3).

    THE PARSER IS ASKED ONLY HERE, and only for a line that already reaches the kernel entry point
    and already carries an expansion -- `kernel.cli` costs 0.03 s on top of the `dispatch` import
    this gate makes anyway (measured 2026-09-13, three runs).
    `tools/test_hooks_v2.py::test_a_quoted_expansion_the_parser_takes_as_a_value_is_not_a_classification`
    """
    spans = []
    masked = _compat._SPAN_RX.sub(lambda match: (spans.append(match.group(0)) or _QUOTED_SPAN),
                                  str(text or ""))
    quoted = iter(spans)
    options = None
    previous = ""
    for token in masked.split():
        if _UNPLACEABLE_RX.search(token):
            return True
        carried = [next(quoted, "") for _ in range(token.count(_QUOTED_SPAN))]
        if any(span[:1] == '"' and _UNPLACEABLE_RX.search(span) for span in carried):
            if options is None:
                options = _kernel.kernel_module("cli").value_taking_options(_EVIDENCE_COMMAND)
            head = token.split("=", 1)[0]
            if not (_takes_a_value(previous, options)
                    or ("=" in token and _takes_a_value(head, options))):
                return True
        previous = token
    return False


def _classification_reading(command):
    """What this shell line does with a fail classification: WRITTEN, UNREADABLE, or None.

    THREE CONDITIONS, AND THE FIRST IS THE FIX OF A MEASURED FALSE ALARM. The line has to be able to
    reach the kernel CLI at all (`_compat.names_the_kernel_entry_point`) -- until 2026-09-13 this
    reader asked only about option prefixes, and `curl --fail https://…` was refused as a
    classification the session instance may not write (verifier round 1, F2, measured as a real hook
    process against two pilots). `--fail` IS a prefix of `--fail-class`, and prefixes are the whole
    point of the second condition, so the entry-point condition is what keeps this reader off every
    other line of the day.

    THE MECHANISM, NOT A SPELLING (DEC-0102 (2)): argparse accepts any UNAMBIGUOUS PREFIX of an
    option, so `--fail-class`, `--fail-cl` and `--f` are one word to the parser that reads them --
    measured 2026-09-12 against the shipped CLI, `evidence … --f mechanical` was accepted and only
    the MISSING arguments were complained about. A reader matching the full spelling is answered by
    a shorter one.

    AND THE THIRD READING, which is a refusal rather than a judgement (verifier round 1, F3):
    `a="--"; b="fail-class"; python scripts/harness.py evidence … "$a$b" mechanical` hands the
    parser the option while nothing here ever holds that text. On an `evidence` line that reaches
    the kernel, such a word makes the question unanswerable, and unanswerable is refused -- the same
    fail-closed direction `gate_write_scope` takes for a word it cannot place. It is bounded to the
    `evidence` command so that an ordinary harness line with a `$` in it is not touched.

    WHAT STAYS OPEN is the wider H11 class: a line that runs a SCRIPT which then calls the kernel is
    not this line, and no reader of a command line can see into it.

    THE VALUE IS NOT READ HERE: what the classification says is the kernel's question
    (`FAIL_CLASSES`); this gate's question is who is writing it at all.
    """
    if not _compat.names_the_kernel_entry_point(command):
        return None
    text = str(command or "")
    words = _OPTION_RX.findall(text)
    evidence_line = re.search(r"(?<![\w-])%s(?![\w-])" % _EVIDENCE_COMMAND, text) is not None
    if not words and not evidence_line:
        return None
    # THE KERNEL IS THE AUTHORITY ON THE NAME, AND IT IS ASKED LAST, because asking costs: the
    # import of the kernel package measured 0.10 s on this host (0.25 s against 0.15 s for the whole
    # hook process, three runs each, 2026-09-13). Since the entry-point condition above, only a line
    # that names the harness pays it -- before it, verifier round 1 measured that EVERY line with a
    # long option did.
    option = "--" + _kernel.kernel_module("backlog_types").FAIL_CLASS_FIELD.replace("_", "-")
    if any(option.startswith(word) for word in words):
        return WRITTEN
    if evidence_line and _an_expansion_stands_where_it_could_be_an_option(text):
        return UNREADABLE
    return None


def _refuse_a_classification_the_judged_role_wrote(data):
    """Refuse a fail classification from anybody but the bound child of the judging class."""
    command = str((data.get("tool_input") or {}).get("command") or "")
    reading = _classification_reading(command)
    if reading is None:
        return                                    # the ordinary shell call pays one substring test
    dispatch = _kernel.kernel_module("dispatch")
    remedy = ("have the verifying role record it from inside its own dispatch -- it is the one "
              "writer whose lease the kernel can attribute (DEC-0107).")
    if not _compat.calling_subagent(data):
        _kernel.block(
            HOOK,
            "the session instance may not classify a failed run: this line %s. The classification "
            "is what keeps " % reading +
            "a mechanical fail from raising the next lease's rung, and the role that ORDERED the "
            "run would be discounting its own dispatch -- DEC-0107 gives it to the verifying role "
            "and to no habitual action of the session agent.",
            event="PreToolUse", remedy=remedy)
    state = _state_for_prevention(data)
    if state is None:
        return                                    # explicit installer window (spec II.4)
    task = dispatch.task_for_agent(state, str(data.get("agent_id") or ""))
    if task is None:
        _kernel.block(
            HOOK,
            "this line %s and no lease binds the agent making it -- so " % reading +
            "nothing here can say which role is writing. A classification nobody can attribute "
            "looks like a discount and is none (DEC-0107).",
            event="PreToolUse", remedy=remedy)
    role = str(task.get("assigned_role") or "")
    # ONE READER FOR ONE RULE. Which classes may classify is the kernel's question and it is asked
    # THERE, through the same predicate `dispatch.fail_class_refusal` uses for its own last check --
    # this hook re-derived the comparison from `ladder_declaration` until TSK-0149, so `QA_CLASS`
    # and the declaration shape had two homes and could drift apart without a test noticing.
    # WHY THE ROLE HALF AND NOT THE WHOLE PREDICATE: the rest of `fail_class_refusal` judges the
    # RECORD -- which orders it names, what verdict it carries, whether one of them is the writer's
    # own -- and a shell line states none of that in a form this reader may trust (that is what
    # `UNREADABLE` above is about). Asking the whole predicate would mean inventing those values,
    # and an invented one refuses lines nobody wrote.
    # None here also covers "no ladder declared", where the kernel's own refusal is the whole rule.
    wrong_class = dispatch.fail_class_role_refusal(state, role)
    if wrong_class:
        _kernel.block(
            HOOK,
            "this line %s, and %s A fail the judged role may call mechanical is a rung it grants "
            "itself (DEC-0107, BUG-0260 AC-2)." % (reading, wrong_class),
            event="PreToolUse", remedy=remedy)


def handle_pre_tool_use(data):
    # TWO tool classes reach this event, and the shell one is here rather than in a
    # gate of its own because the question it answers is a dispatch question: which
    # role is running, read off the leases this gate writes.
    _refuse_a_classification_the_judged_role_wrote(data)
    if data.get("tool_name") not in SPAWN_TOOLS:
        sys.exit(0)
    # AFTER the bundle reading, and that order was measured rather than chosen: mid-way through an
    # installer run BOTH hold -- the bundle on disk is the new kit's while `kit_state.json` still
    # records the old one (1.6 s into a 3.4 s scaffold, docs/reviews/2026-08-16-tsk0067-
    # measurements.md) -- and of the two the withdrawn bundle is the finding a reader must not have
    # hidden from them. Its remedy (reinstall, then ONE new session) also ends the state this one
    # names, so nothing is lost by it winning.
    _refuse_untrusted_bundle(data)
    _refuse_while_a_restart_is_pending(data)
    state = _state_for_prevention(data)
    if state is None:
        sys.exit(0)
    dispatch = _kernel.kernel_module("dispatch")
    tool_input = data.get("tool_input") or {}
    try:
        # BEFORE judging this spawn, and that order is the point: a claim whose bind window has
        # closed with no child is not evidence of anything, so it must not be what refuses the
        # next attempt. Reconciling here means the way out is walked by the very act of trying
        # again, without waiting for the turn to end.
        dispatch.reconcile_unstarted_dispatches(state)
        header = dispatch.parse_header(str(tool_input.get("prompt") or ""))
        # `session_id` is what makes a later session able to tell a dispatch of ITS OWN from one
        # nothing can be behind any more (DEC-0044; `dispatch.DISPATCHING_SESSION`). It is recorded
        # at the CLAIM because that is the moment a child is asked for -- and the key is one the
        # provider was measured to send on this event (`tools/provider_observations.json`).
        # `model` is the one spawn parameter that decides which RUNG the child runs on (measured
        # 2026-09-05: it arrives here when the lead passes it, and it overrides the role's pin);
        # the kernel holds it against the rung the lease derived -- `dispatch.spawn_model_refusal`
        # says when its absence is fine and when it is not.
        verified = dispatch.validate_dispatch(state, header, tool_input.get("subagent_type"),
                                              claim=True, prompt_id=data.get("prompt_id"),
                                              session_id=data.get("session_id"),
                                              spawn_model=tool_input.get("model"))
    except dispatch.DispatchError as exc:
        _kernel.block(HOOK, "specialist spawn refused.\n%s" % exc, event="PreToolUse")
    _mirror_the_builder_start(state, dispatch, verified)
    sys.exit(0)


def _mirror_the_builder_start(state, dispatch, verified):
    """The fact-based checkpoint before a BUILDER starts (DEC-0092 (3)) -- handed to the model as
    context on the same event that just allowed the spawn, and NEVER a refusal.

    ONLY FOR THE BUILD CLASS, read off the lease's own ladder answer: the habit DEC-0092 mirrors
    is how many builders a goal gets and on which rung, so a QA or design spawn gets no mirror,
    and a kit-less project (no ladder answer) gets none either. The four lines are the kernel's
    (`dispatch.reflection_checkpoint`), delivered on `hookSpecificOutput.additionalContext` and
    then audited as a note so the mirror is on the record too. Which channel of THIS event reaches
    the model is `tools/provider_observations.json` -> `hook_output_channels.pre_tool_use`, a
    measurement of its own (2026-09-11); the PostToolUse entry beside it measured a different
    event and is not this claim's source.

    NOTHING IN HERE REFUSES, and the whole body is under one guard because of where this stands:
    AFTER `validate_dispatch(claim=True)`, so the lease's claim is already spent. A refusal here
    would leave the order LEASED with no child and no way back but the TTL -- measured at the
    mid-goal check (B1): with only the derivation guarded, an audit sink that raised gave rc 2 and
    `dispatched_at` set. So the derivation has its own fallback line, the context is written
    BEFORE the audit note (a lost note costs the record, a lost mirror costs the PM's reading),
    and any failure of either simply ends the mirror. `SystemExit` is re-raised because nothing
    below calls it, and swallowing one would hide a gate that spoke.
    `tools/test_light_kit.py::test_the_mirror_still_exits_zero_when_its_audit_sink_is_gone`
    """
    try:
        lease = verified.get("lease") or {}
        answer = lease.get(dispatch.LADDER_KEY)
        if not isinstance(answer, dict) or answer.get("role_class") != dispatch.BUILD_CLASS:
            return
        try:
            lines = dispatch.reflection_checkpoint(state, verified["task"], verified["root"], lease)
        except Exception as exc:  # noqa: BLE001 -- the mirror never turns into a refusal
            lines = ["the checkpoint could not be derived (%s: %s); the spawn stands, the mirror "
                     "does not" % (type(exc).__name__, exc)]
        text = "CHECKPOINT before builder %s starts (DEC-0092 (3)):\n%s" % (
            verified["task"].get("id"), "\n".join(lines))
        sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                            "additionalContext": text}}))
        sys.stdout.flush()
        _kernel.record_note(HOOK, text)
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001 -- the claim is spent; a refusal now protects nothing
        return


def _report(message, and_stop=True):
    """Say something WITHOUT claiming to have prevented anything, and audit it.

    Deliberately not `_kernel.block`. Every event this gate uses it on is one where a refusal
    would be a lie of a different kind: on PostToolUse, PostToolUseFailure, SubagentStart and
    SubagentStop exit 2 does not stop what the event is about (the action stands and only stderr
    is shown), and on Stop a refusal about a ROLLBACK would block something nobody asked about.
    The real protection on the others is that we DID NOT MUTATE state; on Stop it is that the
    mutation is a rollback.

    `and_stop=False` for the ONE caller that has something to say afterwards: `handle_stop` reports
    its reconciliation and then still has to look at the idle dispatches. Exiting here used to
    swallow that second half whenever a claim happened to be reconciled in the same turn.
    """
    _kernel.record_note(HOOK, message)
    sys.stderr.write("[team-kit %s] %s\n" % (HOOK, message))
    if and_stop:
        sys.exit(0)


def handle_subagent_start(data):
    """Claim the pending lease for this child (spec II.4: lease -> agent_id).

    A subagent with no pending dispatch is not an error here. SubagentStart fires for every
    subagent, and gate layers 1+2 already refused the ones that had no business starting; a
    complaint here would only catch subagents the harness never dispatched while breaking every
    legitimate un-dispatched helper. Such a child simply stays UNBOUND — and gate layer 3
    refuses writes from an unbound agent, which is the part that actually holds.
    """
    state = _state_for_recording(data)
    if state is None:
        sys.exit(0)
    dispatch = _kernel.kernel_module("dispatch")
    try:
        dispatch.bind_agent_by_role(state, data.get("agent_id"), data.get("agent_type"),
                                    data.get("prompt_id"))
    except dispatch.NoPendingDispatch:
        sys.exit(0)
    except dispatch.DispatchError as exc:
        _report("this subagent was NOT bound to a task, so the write-scope gate will refuse its "
                "writes.\n%s" % exc)
    sys.exit(0)


def _verified_header(data, state, dispatch, event, require_role=True):
    """The header of a spawn, verified to BELONG to the lease it names — or no mutation.

    `tool_input.prompt` is model-controlled text, and this event cannot block. Taking the task id
    on faith would let an unvalidated spawn collect a VALID agent binding (i.e. gate layer 3
    would hand it that task's allowed_scope) whenever PreToolUse did not get to refuse — a hook
    timeout, or a settings.json whose PostToolUse matcher is wider than its PreToolUse one.

    `require_role=False` on the rollback paths only: binding an agent is a GRANT and must be
    fully identified, while returning a task to READY takes permission away, so refusing that over
    a missing payload field would strand the task for no safety gain.

    IDENTITY only (nonce, root revision, role) — not authorisation. See
    `dispatch.verify_dispatch_identity`: re-asking "is this still approved?" here would freeze a
    task whose approval was revoked mid-flight, in the exact case where recording the outcome
    matters most.
    """
    tool_input = data.get("tool_input") or {}
    try:
        header = dispatch.parse_header(str(tool_input.get("prompt") or ""))
    except dispatch.DispatchError:
        return None  # not a dispatched spawn — nothing of ours to record
    try:
        dispatch.verify_dispatch_identity(state, header, tool_input.get("subagent_type"),
                                          require_role=require_role)
    except dispatch.DispatchError as exc:
        _report("refusing to record an outcome for %s on %s: the spawn's header does not check "
                "out, so state is left untouched.\n%s" % (header["task_id"], event, exc))
    return header


def handle_post_tool_use(data):
    """The spawn STARTED: bind the child authoritatively and move the task to IN_PROGRESS.

    This is the only place where the dispatch header and the child's agentId are both present
    (spike S3), so the role-matched binding from SubagentStart is confirmed here even when it was
    right — cheap, and it makes the audit record independent of the ambiguous path.
    """
    if data.get("tool_name") not in SPAWN_TOOLS:
        sys.exit(0)
    state = _state_for_recording(data)
    if state is None:
        sys.exit(0)
    dispatch = _kernel.kernel_module("dispatch")
    header = _verified_header(data, state, dispatch, "PostToolUse")
    if header is None:
        sys.exit(0)
    response = data.get("tool_response")
    response = response if isinstance(response, dict) else {}
    agent_id = response.get("agentId")
    started = str(response.get("status") or "").lower() in STARTED_STATUSES
    try:
        if not started:
            # PostToolUse means the tool call SUCCEEDED, so an unrecognised status is a platform
            # shape we have not measured. Leave the task LEASED and say so: guessing "failed"
            # would free a task whose child may be running, guessing "started" would mark a task
            # in progress that may not be. The TTL sweep is the backstop.
            _report("spawn of %s reported an unrecognised status %r — leaving the task LEASED "
                    "rather than guessing. It returns to READY on lease timeout."
                    % (header["task_id"], response.get("status")))
        if agent_id:
            dispatch.bind_agent(state, header["task_id"], agent_id)
        # The session goes onto the TASK here, because the lease it also sits on is the record the
        # TTL sweep deletes first -- see `dispatch.spawn_outcome`.
        dispatch.spawn_outcome(state, header["task_id"], True, session_id=data.get("session_id"))
    except dispatch.DispatchError as exc:
        _report("could not record the spawn outcome for %s.\n%s" % (header["task_id"], exc))
    sys.exit(0)


def handle_spawn_failure(data):
    """The spawn did NOT start -> READY at once. An ACCELERATOR, not the guarantee.

    Spec II.4 wants "Fehlschlag -> sofort zurueck auf READY". A failing tool call fires
    PostToolUseFailure and this makes that immediate. It is deliberately NOT the only way back:
    measured 2026-08-02, a permission refusal delivers no hook event at all, so a task whose
    return to READY hung on one would simply never return. `handle_stop` and the reconciliation
    at the next PreToolUse cover the silent cases; this one only saves the wait.
    """
    if data.get("tool_name") not in SPAWN_TOOLS:
        sys.exit(0)
    state = _state_for_recording(data)
    if state is None:
        sys.exit(0)
    dispatch = _kernel.kernel_module("dispatch")
    header = _verified_header(data, state, dispatch, "PostToolUseFailure", require_role=False)
    if header is None:
        sys.exit(0)
    try:
        dispatch.clear_awaiting_bind(state, header["task_id"])
        dispatch.spawn_outcome(state, header["task_id"], False)
    except dispatch.DispatchError as exc:
        _report("could not return %s to READY after a failed spawn.\n%s"
                % (header["task_id"], exc))
    sys.exit(0)


def handle_subagent_stop(data):
    """A child stopped: record it against its dispatch, so a later turn-end can see it.

    WHY A RECORD RATHER THAN A REPORT HERE. The party that has to know a specialist is over is the
    LEAD, and it needs to know at the end of one of its OWN turns — which is a different event,
    possibly minutes later. This event is where the fact exists; `dispatch.idle_dispatches` is
    where it is read (BUG-0058).

    WHY THIS GATE RUNS LAST IN THE SubagentStop CHAIN, and it is registration, not tidiness: the
    gate ahead of it can turn this stop into a CONTINUATION (`gate_subagent_output` exits 2 for a
    final message without its output contract, and the child then keeps working). A record written
    ahead of that refusal would say the child ended while it had just been told to carry on, and
    the lead's next turn-end would be refused over a specialist that is still running.

    Nothing is refused here: SubagentStop's exit 2 is the OTHER gate's mechanism for making a
    child continue, and this one has nothing to ask of it.
    """
    state = _state_for_recording(data)
    if state is None:
        sys.exit(0)
    dispatch = _kernel.kernel_module("dispatch")
    try:
        dispatch.record_child_end(state, data.get("agent_id"), data.get("agent_type"))
    except dispatch.DispatchError as exc:
        _report("this subagent's stop was not attributed to a dispatch, so the end of the turn "
                "will not name that task as idle.\n%s" % exc)
    sys.exit(0)


def handle_stop(data):
    """End of the turn: return every claim that produced no child to READY, then name every
    dispatch whose records say no child is on it.

    WHY THIS EVENT. It is the one that was MEASURED to arrive: `Stop` fired in all twelve real
    headless sessions of 2026-08-02, including the ones that ended after four refused tool calls,
    while `PermissionDenied` fired in none of them. A reconciliation that runs here therefore
    needs no cooperation from the failure path it is cleaning up after. It is also the ONE place
    the harness gets a word in on the lead's answer path: the turn the lead is about to finish is
    the turn in which it would otherwise say "it is running" again.

    The RECONCILIATION never refuses — see the module docstring. The refusal below is the other
    half and belongs to a different question.
    """
    state = _state_for_recording(data)
    if state is None:
        sys.exit(0)
    dispatch = _kernel.kernel_module("dispatch")
    released = dispatch.reconcile_unstarted_dispatches(state)
    if released:
        _report("returned to READY — dispatched, but no subagent ever started for %s. A spawn "
                "that the permission layer or the provider refused delivers no hook event, so "
                "this is measured by the bind window closing empty, not reported by anything."
                % ", ".join(released), and_stop=False)
    _name_the_dispatches_the_records_say_nobody_is_on(data, state, dispatch)
    sys.exit(0)


def _finding_line(finding):
    """One dispatch, as the lead has to read it: what it is, what the record says about its child,
    what it left on disk, and the status its own automaton offers for a run that produced
    nothing."""
    return ("%s (%s, role %s): %s. What the run left: %s. The no-progress status its automaton "
            "offers is %s."
            % (finding["task_id"], finding["status"], finding.get("assigned_role"),
               finding["why"], finding["staged"],
               finding["no_progress_status"] or "none — this one has to be decided by hand"))


def _name_the_dispatches_the_records_say_nobody_is_on(data, state, dispatch):
    """Refuse ONE turn-end per finding, so a dispatch the records say has no child on it reaches
    the lead before it answers with another waiting phrase.

    WHAT IS AND IS NOT CLAIMED HERE: `dispatch.idle_dispatches` reports a dispatch its own RECORDS
    speak against -- a recorded child end, or a window that ran out with nothing ever bound. It
    does not observe processes, so "nothing is running" is not what this says and must not be what
    the text says either; a bound child that outlived its lease is deliberately absent from it.

    THE MEASURED FAILURE (BUG-0058, pilot 4 half 2 / P4-2): the dispatched specialist produced no
    file and stopped, the task stayed IN_PROGRESS with a live lease and an empty staging directory,
    and the lead answered NINE consecutive user turns with waiting phrases without one follow-up
    call. Nothing in the apparatus put the question in front of it.

    WHY A REFUSAL AND NOT A NOTE. On this event a note reaches nobody: exit-0 stderr was measured
    to reach neither the user nor the model (tools/provider_observations.json, hook_output_channels
    — measured on PostToolUse, and it is the same channel). Exit 2 is the event's documented
    contract: the assistant does not end its turn and is handed this stderr. That the provider
    honours it on Stop is the hooks reference's exit-code table, which `_kernel.BLOCKING_EVENTS`
    transcribes — this repo has measured that Stop FIRES, not what its exit 2 does, and a live run
    on the shipped lead is where that half is measured (BUG-0058 AC-2).

    TWO BOUNDS AGAINST A LOOP, because a refused stop is answered by CONTINUING and the condition
    outlives the refusal: `dispatch.mark_idle_reported` speaks at most once per FINDING (the
    harness's own record), and `stop_hook_active` stands down for a cycle a stop hook already
    blocked (the provider's word, and the same key `gate_subagent_output` relies on). Neither is
    decoration — with one of them gone the other still holds, which is why there are two. How
    LONG the provider keeps that key set is not measured here, and the direction it fails in is
    the safe one: a key that stayed set would make this silent, never repetitive, so what a
    sticky one costs is the finding arriving at all — which is why nothing in this file or in
    the kits' texts promises that it does.

    Every finding is AUDITED whether or not it is refused over, so "it was reported once and
    ignored" stays readable afterwards.
    """
    findings = dispatch.idle_dispatches(state)
    if not findings:
        return
    for finding in findings:
        _kernel.record_note(HOOK, "idle dispatch — %s" % _finding_line(finding))
    if data.get("stop_hook_active"):
        return
    fresh = [finding for finding in findings if dispatch.mark_idle_reported(state, finding)]
    if not fresh:
        return
    _kernel.block(
        HOOK,
        "this turn was about to end while the records say no child is on %d dispatch(es):\n%s"
        % (len(fresh), "\n".join("  " + _finding_line(finding) for finding in fresh)),
        event="Stop",
        remedy="find out what really happened before you answer again. Read what the run left and "
               "ask whether it can be resumed (`python scripts/harness.py checkpoint-status "
               "<TSK-ID>`); book a handed-back envelope if one is staged (`python "
               "scripts/harness.py submit-result --task-id <TSK-ID> --from <NAME>`); otherwise "
               "take the task "
               "to the no-progress status named above (`python scripts/harness.py transition "
               "<TSK-ID> <STATUS>`), whose way back is the user's approved retry, and TELL THE "
               "USER what happened. Reporting the task as running is the failure this refusal is "
               "named after (BUG-0058). It comes AT MOST once per finding — this stop is "
               "not blocked again for the same one.")


HANDLERS = {
    "PreToolUse": handle_pre_tool_use,
    "SubagentStart": handle_subagent_start,
    "PostToolUse": handle_post_tool_use,
    "PostToolUseFailure": handle_spawn_failure,
    "SubagentStop": handle_subagent_stop,
    "Stop": handle_stop,
}


def main():
    data = _kernel.payload(HOOK)
    event = str(data.get("hook_event_name") or "")
    handler = HANDLERS.get(event)
    if handler is None:
        sys.exit(0)  # an event this gate is not registered for is not its business
    # re-entered with the RESOLVED event: an internal error on an event that cannot block must not
    # be audited as a "block" that never blocked (see _kernel.record_note)
    with _kernel.fail_closed(HOOK, event):
        handler(data)


if __name__ == "__main__":
    _kernel.run_gate(HOOK, main)
