"""The harness CLI -- the command surface the fail-closed remedies point at (II.4).

Thin argparse wrapper over the kernel API. Exit codes: 0 = ok, 1 = findings/
refusal (message explains), 2 = usage error.

IN A SCAFFOLDED PROJECT THIS MODULE IS NOT WHAT A ROLE RUNS. The scaffold installs
`scripts/harness.py` (ENTRY_POINT below), and the one sanctioned spelling is
`python scripts/harness.py <cmd>` -- identical in bash and PowerShell, which are
gated by the same eight PreToolUse hooks. That shim resolves `--root` itself and
refuses it on the command line, because `gate_write_scope` refuses any pipeline
that can write and whose COMMAND LINE names the state directory or `.claude`
(measured: `python -B .claude/kernel/cli.py doctor` -> "names the enforcement
layer"). `prog` below is that spelling, so every usage and error line argparse
prints is a line a role can retype.

BEFORE a kit is installed there is no shim, and the entry gate that writes the
first item reaches the module directly, with the kit staging on the import path:
`python -B -m kernel.cli <cmd>`. That form works only from there -- an installed
project has the kernel at `.claude/kernel`, where it raises `No module named
'kernel'` (measured) -- so it is documented for the installer position and
nowhere else. The two global entry-gate files spell the same line with an
explicit `PYTHONPATH` prefix, which is the only thing that puts the staging on
that path.

THE `-B` IS NOT DECORATION AND MUST TRAVEL WITH EVERY COPY OF THAT LINE. `-m`
imports the whole package, so the same command without that flag caches eleven
`.pyc` into `.claude/kernel` -- inside the tree `hook_bundle_hash` measures with
nothing excluded. Measured against an installed project: the flagless form ran
`doctor` and reported, in the same run that created them, that the bundle
"changed after trust was recorded", and the next SessionStart dropped the
project to `hooks_trust_required`. On Codex the inline verifier runs before
every tool call, so the same keystroke blocks the session until a re-scaffold.
A diagnosis command that destroys what it diagnoses -- and blames the user for
it -- is worse than no command, which is why every shipped remedy spells it this
way and `test_the_documented_cli_invocation_leaves_the_bundle_alone` runs what
this docstring says. The flagless form is deliberately not written out anywhere
in the shipped tree; a reader who copies a line copies a working one. The shim
carries the same rule as `sys.dont_write_bytecode = True` in its own first
statements, so the sanctioned spelling needs no flag to be safe.
"""
from __future__ import annotations

import argparse
import builtins
import inspect
import json
import os
import subprocess
import sys
import time

from . import (approvals, board, checkpoints, dispatch, documents, duties, filing, gaplog,
               hashing, holes, kitupdate, migrate, plan_diagram, presets, report, scopes,
               staging)
from .backlog_types import (
    AREA_FIELD,
    AREA_SEPARATOR,
    BLOCKED_REASON_FIELD,
    BLOCKED_RESULT,
    CAPTURE_ONLY_REQUIRED,
    DEC_WORK_FIELD,
    DEC_WORK_NONE,
    EVIDENCE_KINDS,
    EVIDENCE_RESULTS,
    FAILING_RESULT,
    FAIL_CLASSES,
    FAIL_CLASS_FIELD,
    HOLE_LIMIT_FIELD,
    HOLE_NUMBER_FIELD,
    REQUIRED_FIELDS,
    RUN_SCOPES,
    TASK_TYPES,
    TransitionError,
    area_segments,
    field_elements,
    work_is_stated,
)
from .schemas import load_schema
from .state import ProjectState, StateError

# The name of the pre-dispatch scope check on this surface, spelled ONCE: the parser and the
# branch that answers it are two readers, and a command name written twice is the drift this
# module removes everywhere else. It also keeps the literal out of `build_parser`'s own body,
# which `tools/test_hooks.py::test_every_span_that_presents_the_command_surface_names_all_of_it`
# reads as a span that would then be presenting a partial command list.
CHECK_SCOPES_COMMAND = "check-scopes"


class UsageError(ValueError):
    """The command was not run because its INPUT was wrong -- exit 2, like argparse's own.

    Separate from `StateError` on purpose: 1 means the kernel looked and refused, 2 means it never
    got as far as looking. A malformed `capture` body is the second, and reporting it as the first
    would tell a role its item was rejected when it was never read.
    """


# WHERE the scaffold installs the entry point, and HOW a role invokes it -- one pair of
# constants because the two are the same fact and every other statement of it is derived:
# `prog` below (so argparse's own usage lines are runnable), the shim's self-location check,
# the scaffold's kit-owned list, and the test that requires every shipped text naming the
# entry point to spell it this way. A second, hand-written spelling anywhere is the drift
# this pair exists to prevent.
ENTRY_POINT = "scripts/harness.py"
INVOCATION = "python " + ENTRY_POINT


# THE PROMOTION SURFACE (spec II.6/II.6a). `kernel/staging.py` has had these three operations since
# 1.6 and its own docstring said "WHO calls freeze at mint time is phase-2 hook/orchestrator logic";
# nothing ever did. Measured 2026-07-31 in a scaffolded project, before this: no subcommand named
# freeze, `capture ARC` refused (`ARC` is not in `REQUIRED_FIELDS`), and `project_memory/**` is
# kernel-only for tool writes -- so an ARC item, a frozen wireframe and a `design_refs` entry were
# all unreachable. Three consequences, none of them theoretical: `gate_packaging_decision` blocked
# every push and merge on a field no role could write (a block with no exit, which is exactly what
# its own docstring said it was not); the UI-design tooth in `dispatch.validate_dispatch` only
# fires on a non-empty `root.design_refs` and that list could never become non-empty; and no
# wireframe could ever be frozen on scope approval.
#
# ONE MAPPING, and the surface is derived from it rather than restated: the subcommand names, their
# `--help`, the body's required and optional keys and the type each key must carry all come from
# `freeze_parameters` reading the operation's own signature. A fourth freeze operation is on the
# command line the day it is written, with the right contract, and a renamed parameter cannot leave
# a stale flag behind.
FREEZE_OPERATIONS = {
    "architecture": staging.freeze_architecture,
    "design": staging.freeze_design,
    "wireframe": staging.freeze_wireframe,
    "report": staging.freeze_report,
}
FREEZE_COMMANDS = {"freeze-" + kind: operation for kind, operation in FREEZE_OPERATIONS.items()}


def freeze_parameters(operation):
    """The body contract of a freeze operation, read off its signature: {name: (required, type)}.

    `state` is dropped -- the CLI holds it, and it is the one parameter a body must never carry.
    The TYPE is the parameter's own annotation resolved against `builtins`; `from __future__ import
    annotations` makes those annotations strings, and anything that does not name a builtin type
    simply carries no type check rather than an invented one. That matters because a body value of
    the wrong shape reaches the kernel as a `TypeError` from inside `list()` or `dict.get`, which is
    a traceback rather than a message a role can act on.
    """
    contract = {}
    for name, parameter in list(inspect.signature(operation).parameters.items())[1:]:
        declared = getattr(builtins, str(parameter.annotation), None)
        contract[name] = (parameter.default is inspect.Parameter.empty,
                          declared if isinstance(declared, type) else None)
    return contract


def _freeze_body(command, operation):
    """The stdin body for a freeze, checked against the operation's declared contract.

    Refusals are UsageErrors (exit 2) on purpose: a body with a missing or misspelled key is input
    the kernel never got to look at, and reporting it as a state refusal would tell a role its
    freeze was rejected when it was never attempted.
    """
    body = _json_body(command)
    contract = freeze_parameters(operation)
    missing = sorted(name for name, (required, _t) in contract.items()
                     if required and name not in body)
    unknown = sorted(key for key in body if key not in contract)
    if missing or unknown:
        raise UsageError(
            "the %s body %s. Its keys are exactly the operation's own parameters -- required: %s; "
            "optional: %s. Remedy: send that object on stdin, e.g. `%s %s <<'EOF'` … `EOF`."
            % (command,
               "; ".join(part for part in (
                   "is missing %s" % ", ".join(missing) if missing else "",
                   "carries %s, which the operation has no parameter for" % ", ".join(unknown)
                   if unknown else "") if part),
               ", ".join(sorted(n for n, (r, _t) in contract.items() if r)) or "none",
               ", ".join(sorted(n for n, (r, _t) in contract.items() if not r)) or "none",
               INVOCATION, command))
    for name, value in sorted(body.items()):
        _required, declared = contract[name]
        if declared is None or isinstance(value, declared):
            continue
        if value is None:
            # NULL IS THE SCHEMA'S QUESTION, NOT THIS ONE. The first cut allowed it only for a
            # parameter with a default and thereby refused a legitimate body: `freeze_wireframe`
            # takes `scope_apr_ref` as a REQUIRED parameter whose companion field is
            # `nullable: true` (same for `arc_companion.approval_ref`), so "no approval yet" had no
            # spelling. This check is about SHAPE -- a list stays a list -- and the strict companion
            # schemas decide which fields may be absent or null.
            continue
        raise UsageError(
            "the %s body gives %s as %s; the operation declares it %s. Remedy: send the field in "
            "the shape the kernel hashes it in -- a list stays a list, a mapping stays a mapping."
            % (command, name, type(value).__name__, declared.__name__))
    return body


def manifest_parameters(builder) -> list:
    """The subject keys a line-manifest builder takes, read off its own signature.

    Same derivation as `freeze_parameters`, and for the same reason: the flag surface of
    `request-approval push` IS `approvals.push_subject_manifest`'s parameter list, so a renamed
    or added subject key cannot leave a stale flag behind. Nothing is dropped here -- unlike a
    freeze operation, a manifest builder holds no `state`.
    """
    return list(inspect.signature(builder).parameters)


def optional_manifest_parameters(builder) -> frozenset:
    """The subject keys a command line may LEAVE OUT, read off the builder's own defaults.

    Same derivation as `freeze_parameters`' required/optional split, and here it carries meaning
    rather than convenience: for `filing_correction` the absent key IS the decision (no destination
    means the document is deleted, `approvals.filing_correction_subject_manifest`), so the builder's
    signature is where that fact belongs -- one statement, read by the parser, by `_line_manifest`
    and by the question the user signs.

    Empty for every builder that declares no default, which is all three of the older line kinds --
    so `push`, `preset` and `kit_update` keep refusing an unanswered subject key exactly as before
    (`tools/test_staging_cli.py::test_a_line_kind_without_a_defaulted_subject_key_still_demands_
    every_one`).
    """
    return frozenset(name for name, parameter in inspect.signature(builder).parameters.items()
                     if parameter.default is not inspect.Parameter.empty)


def _worktree_head(state: ProjectState, _args) -> str:
    """The commit a push would publish, read from the worktree the state directory sits in.

    `gate_push_token` resolves the SAME value with the same git call and binds its check to it, so
    a head a role typed from memory would mint a token for a different commit -- which is exactly
    the single-use property `push_subject_manifest` rests on. None when git cannot answer; the
    caller turns that into a usage error naming the flag.
    """
    repo = os.path.dirname(os.path.abspath(state.root))
    try:
        result = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                                capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return ((result.stdout or "").strip() or None) if result.returncode == 0 else None


def _preset_roles(state: ProjectState, args):
    """The specialist set the requested preset installs here -- the kit's own answer."""
    return presets.change_manifest(state, args.preset)["roles"]


def _preset_removes(state: ProjectState, args):
    """The installed specialists that the requested preset drops -- possibly none, legitimately."""
    return presets.change_manifest(state, args.preset)["removes"]


# Manifest keys the CLI determines ITSELF, from the project rather than from the role -- each with
# the SOURCE it determines them from, in the words the `--help` prints. A key here is not the
# role's to fill in; a key without an entry is required on the line. That split is why `remote` and
# `branch` stay typed: they are what the user is asked to authorise, so they come from the role's
# intent, never from whatever the machine happens to be checked out at. `preset`'s two lists are
# the mirror image -- they are what the KIT decides, and a role typing them would be typing over
# the file that owns them.
#
# A TYPED VALUE FOR ONE OF THESE IS REFUSED, not quietly overridden and not quietly used. The
# verifier measured what "used" costs: `--roles product-designer --removes nothing-at-all` produced
# a real, kernel-signed approval question whose role lists were those strings split into single
# CHARACTERS -- and `build_question` rests on the property that what the hash covers is what the
# user is shown. A silent override would be no better: the question would then be right while the
# line the role typed said something else. `test_a_resolver_owned_key_is_not_the_roles_to_type`
# measures the refusal on both keys.
#
# A resolver takes (state, args): the second half arrived with `preset`, whose answer depends on
# the preset already named on the line. `_worktree_head` ignores it, which is the honest shape --
# one signature, and no branch here about which resolver wants what.
def _kit_update_key(key):
    """One resolver per key of the kit-update manifest, all reading ONE derivation.

    Every key of that manifest is the kit's own statement about a release
    (`approvals.kit_update_subject_manifest`), so none of them is a role's to type -- and the
    entries are generated from the builder's signature rather than written out, for the reason
    `manifest_parameters` exists: a renamed or added key arrives here correctly refused instead of
    silently becoming a flag the command ignores.
    """
    def resolve(state: ProjectState, _args):
        return kitupdate.change_manifest(state).get(key)
    return resolve


def _document_content(state: ProjectState, args) -> str:
    """The FASSUNG of the document a filing correction names -- hashed here, never typed.

    A role typing this would be typing the one value that decides whether the approval still covers
    the document when the gate looks: `guard_fs_tripwire` recomputes it from the file on disk with
    the same function, so a typed value could only differ from what the user was shown -- which is
    the property `LINE_MANIFEST_RESOLVERS` exists for.

    A document that cannot be hashed is refused HERE, with the path in the message, rather than
    reported as a missing manifest key: the two causes a clerk actually hits are a mistyped path and
    a file past `hashing.DOCUMENT_HASH_LIMIT`, and neither is helped by a remedy listing four flags.

    THE SPELLING HAS TO ROUND-TRIP, and this is the half that was silent (verifier finding F5). It
    is not enough that the named file lies inside the project: the typed spelling must BE the
    project-relative position, because that is the only spelling `guard_fs_tripwire` can ever
    produce. An absolute path to a file inside the project passed the earlier check, minted a real
    approval -- and the same document named the way the gate names it was then refused, which is a
    dead end handed over without a word. So the position is resolved and normalised back, and it has
    to come out as what was typed (`tools/test_staging_cli.py::test_a_document_named_in_a_spelling_
    the_gate_cannot_produce_is_refused_at_the_command_line`). `approvals.is_project_position` refuses
    the same class one layer further in, over the subject the user signs; this one is the message
    the clerk gets, with the path in it.

    AND THE ROUND TRIP IS AGAINST THE FILESYSTEM, NOT AGAINST THE STRING (verifier round 2, R2).
    Lexically, `ARCHIVE/…/x.pdf` round-trips perfectly -- and on a case-insensitive filesystem it is
    the same file under a name the archive does not use, so the approval was minted and then matched
    nothing. `hashing.on_disk_position` reads back the spelling the filesystem really carries, and a
    deviating one is refused BY NAME rather than by the generic message: a user who answered a
    question for nothing is worse off than one who was told to type the path again.
    """
    repo = os.path.dirname(os.path.abspath(state.root))
    document = approvals.filed_position(getattr(args, "document", None))
    absolute = os.path.abspath(os.path.join(repo, document)) if document else ""
    inside = bool(document) and (os.path.normcase(absolute)
                                 .startswith(os.path.normcase(repo) + os.sep))
    round_trips = inside and approvals.filed_position(
        os.path.relpath(absolute, repo)) == document
    spelled = hashing.on_disk_position(repo, document) if round_trips else None
    if spelled is not None and spelled != document:
        raise UsageError(
            "the document is called %s; %s names the same file but not by that name, and the gate "
            "reads the position out of the command that touches it. An approval for a spelling the "
            "archive does not use would be minted and would then match nothing -- a question the "
            "user answers for nothing. Remedy: name it exactly as it lies there: `--document %s`."
            % (spelled, document, spelled))
    content = hashing.document_content_hash(absolute) if spelled is not None else None
    if not content:
        raise UsageError(
            "a filing correction is bound to the document's own bytes, and %s could not be read as "
            "a file inside %s under the name the gate uses (it lies outside the project, it is "
            "spelled in a way the gate never produces -- absolute, or climbing -- or it is missing, "
            "is a directory, is unreadable, or is larger than the %d MiB a gate may hash while "
            "judging a call). Remedy: name the document with its path relative to the project root, "
            "exactly as it lies there."
            % (document or "an empty path", repo, hashing.DOCUMENT_HASH_LIMIT // (1024 * 1024)))
    return content


def _proposal_key(key):
    """One resolver per DERIVED key of a document proposal, all reading ONE derivation.

    `base`, `proposed` and `changes` are what the two FILES say -- the document's bytes, the staged
    proposal's bytes, and what applying one to the other would add. None of them is a role's to
    type: a typed hash could only differ from what the user was shown, and a typed change list would
    be a description of a write instead of a derivation of it. `kernel.documents.change_plan` is the
    one place they come from, so the question that ASKS and the command that ACTS cannot come to
    describe two different writes (`presets._plan`'s reason, one document over).
    """
    def resolve(state: ProjectState, args):
        # WHICH PLAN, decided by the KIND and never by the key name (FR-0067). The two document
        # routes share `base` and `proposed`, and the additive planner REFUSES a replacement -- so
        # a resolver that always asked that one would answer a revision's question with the
        # refusal of the other route, about a write the user is entitled to be shown.
        kind = getattr(args, "kind", None) or documents.KIND_BY_COMMAND[args.command]
        return documents.PLAN_BY_KIND[kind](state, getattr(args, "kit_document", None),
                                            getattr(args, "proposal", None)).get(key)
    return resolve


def _plan_goals(state: ProjectState, _args) -> list:
    """The goal list of a plan approval -- READ FROM THE STORE, never typed (FR-0074).

    The one key of `approvals.plan_subject_manifest`, and the reason it is a resolver rather than a
    flag is the reason every entry of this table is one: what the hash covers has to be what the
    user is shown, and a goal list typed on a command line could only differ from the goals the
    project actually holds. It is also not typeable in practice -- each entry carries the goal's
    own scope-manifest hash.
    """
    return approvals.plan_goals(state)


def _verification_bugs(state: ProjectState, args) -> list:
    """The defect records of a batch verification -- the IDS are typed, the PROOF is read.

    The split is the reason this is a resolver at all (PR-0012 AC-1): which defects to close is the
    role's statement and can only be typed, while the Evidence that measured each one is a record
    in the store -- and a typed evidence id could only differ from the record the confirming edge
    will actually read. `approvals.verification_batch` reads it with the very reader that edge uses
    and refuses the whole question, by name, for any listed id that has none.
    """
    return approvals.verification_batch(state, getattr(args, BATCH_ARGUMENT, None) or [])


def _hole_exception_holes(state: ProjectState, args) -> list:
    """The gaps of a hole-exception batch -- the IDS are typed, the BOUND is read (PR-0012 AC-4).

    The same split as `_verification_bugs` and for the same reason: which gaps the user is asked to
    accept is the role's statement and can only be typed, while what BOUNDS each one is the item's
    own `limits` sentence -- a typed bound could only differ from the one the gap's record states,
    and it is the sentence the acceptance is FOR.
    """
    return approvals.hole_exception_batch(state, getattr(args, BATCH_ARGUMENT, None) or [])


# THE COMMAND-LINE ARGUMENT A BATCH KIND NAMES ITS ITEMS ON. Spelled once: the parser adds it, the
# resolver above reads it, and `kinds_reading_argument` derives WHICH kinds may carry it.
BATCH_ARGUMENT = "batch"

LINE_MANIFEST_RESOLVERS = {
    "goals": (_plan_goals, "read from this project's own open product goals"),
    # the third element names the command-line ARGUMENT this resolver reads, for the entries that
    # read one at all -- see `kinds_reading_argument`
    "bugs": (_verification_bugs,
             "read from the ids on --batch and, per id, the Evidence that measured it",
             BATCH_ARGUMENT),
    "holes": (_hole_exception_holes,
              "read from the ids on --batch and, per id, the sentence that says what bounds it",
              BATCH_ARGUMENT),
    "content": (_document_content, "hashed from the document named on this line"),
    "head": (_worktree_head, "read from the worktree this state directory sits in"),
    "roles": (_preset_roles, "read from the kit's own presets.yaml for the preset on this line"),
    "removes": (_preset_removes, "derived from what this installation owns and that preset"),
}
LINE_MANIFEST_RESOLVERS.update(
    (name, (_kit_update_key(name),
            "read from this project's own kit stamp and the kit staged on this machine"))
    for name in manifest_parameters(approvals.kit_update_subject_manifest))
LINE_MANIFEST_RESOLVERS.update(
    (name, (_proposal_key(name),
            "derived from the document and the staged proposal named on this line"))
    for name in ("base", "proposed", "changes", "replacements", "deletions", "additions"))


def kinds_reading_argument(argument: str) -> frozenset:
    """The line kinds whose subject manifest a resolver builds from this command-line argument.

    DERIVED THROUGH THE RESOLVER, so the flag and the kinds that may carry it cannot become two
    statements: an entry of `LINE_MANIFEST_RESOLVERS` names the argument it reads, a builder names
    the manifest keys it takes, and a kind takes the flag exactly when its builder needs a key some
    resolver builds from that argument. Written out as a set of kind names instead, `--batch` would
    go on being accepted for `verification` after the key was renamed, or be refused for the second
    batch kind the day it arrives -- and both of those are silent.
    `tools/test_approvals_dispatch.py::test_the_batch_flag_belongs_to_the_kinds_whose_resolver_reads_it`
    """
    keys = {name for name, entry in LINE_MANIFEST_RESOLVERS.items()
            if len(entry) > 2 and entry[2] == argument}
    return frozenset(kind for kind, builder in approvals.LINE_MANIFEST_BUILDERS.items()
                     if keys.intersection(manifest_parameters(builder)))


def _line_manifest(state: ProjectState, kind: str, builder, args) -> dict:
    """The subject manifest for a line kind, from the flags plus the resolvers.

    EMPTY IS AN ANSWER WHEN A RESOLVER GAVE IT, and that distinction is load-bearing: a preset
    upgrade REMOVES nothing, so `removes: []` is the truth about it, while the same emptiness in a
    key the role must type means the question would not say what it releases. So a resolved key
    fails only when the resolver cannot answer at all (None), and a typed key fails on emptiness.
    `test_a_manifest_key_a_resolver_answers_with_nothing_is_still_an_answer` measures the pair.

    ...AND EMPTY IS AN ANSWER WHEN THE BUILDER DECLARED A DEFAULT FOR IT
    (`optional_manifest_parameters`). That is not a third leniency but the same rule read off the
    one place that owns it: for `filing_correction` an absent `--destination` is what says the
    document ends up nowhere, and the question the user signs spells that out as a deletion. A
    builder that declares no default keeps demanding every key, which is all three older line kinds.

    THE REMEDY IS DERIVED FROM THE SAME TWO STATEMENTS the loop decides on, and that is the fix to
    verifier finding F8: it used to print EVERY manifest key as a flag to type, which named
    `--content` (a resolver-owned key this very function refuses when typed) and `--destination` (a
    key whose OMISSION is the documented way to request a deletion). A remedy that contradicts the
    command it is the remedy for is worse than none, and `optional_manifest_parameters` having a
    reader that disagrees with it is exactly the second statement this kernel keeps unlearning.
    """
    values = {}
    optional = optional_manifest_parameters(builder)
    typed = [key for key in manifest_parameters(builder) if key not in LINE_MANIFEST_RESOLVERS]
    flags = " ".join(
        ("[--%s <%s>]" if key in optional else "--%s <%s>")
        % (key.replace("_", "-"), key) for key in typed)
    for name in manifest_parameters(builder):
        value = getattr(args, name, None)
        entry = LINE_MANIFEST_RESOLVERS.get(name)
        if entry is not None:
            if value:
                raise UsageError(
                    "%s is not a value to type on this line: it is %s, and the command re-derives "
                    "it when it acts on the approval -- a typed one could only differ from what "
                    "the user was shown. Remedy: drop `--%s %s` and run the command again."
                    % (name, entry[1], name.replace("_", "-"), value))
            value = entry[0](state, args)
        if name in optional and not value:
            continue          # the builder's own default answers it -- see the paragraph above
        if value is None or (not value and entry is None):
            raise UsageError(
                "a %s approval question must say what it releases, and %s is missing. Remedy: "
                "`%s request-approval %s %s` -- these are the subject keys a line carries (a "
                "bracketed one may be left out, and what its absence MEANS is in the question the "
                "command prints); every other key of the manifest is derived by the command itself "
                "and is refused when typed."
                % (kind, name, INVOCATION, kind, flags))
        values[name] = value
    try:
        return builder(**values)
    except approvals.ApprovalError as exc:
        # A BUILDER THAT REFUSES ITS SUBJECT IS REFUSING THE LINE, and the role has to read one exit
        # code for that. `filing_correction` is the first line kind whose builder can refuse (a
        # position the gate could never produce, a destination that names no place); as an
        # ApprovalError it came back as exit 1 -- "the kernel refused" -- beside exit 2 for the
        # resolver's refusal about the very same flag. Same input, same fault, two codes.
        raise UsageError(str(exc)) from None


def remedy_flags(builder, values) -> str:
    """The flags a role RETYPES for this line kind, FILLED with the values a refusal already holds.

    The same two statements `_line_manifest` decides on, one function up -- a key a resolver owns
    is not typed, and a key the builder gave a default may be left out -- rendered with the values
    instead of with placeholders. Verifier finding F8 was one reader disagreeing with those two:
    the remedy named `--content` (a resolver-owned key this CLI refuses when typed) and
    `--destination` (a key whose ABSENCE is how a deletion is requested). A second reader deriving
    them again in `kernel/filing.py` would be that finding one module over, which is why the
    derivation lives here and that module asks
    (`tools/test_office_package.py::test_a_printed_remedy_names_only_the_flags_its_own_line_takes`).
    """
    optional = optional_manifest_parameters(builder)
    parts = []
    for name in manifest_parameters(builder):
        if name in LINE_MANIFEST_RESOLVERS:
            continue
        value = values.get(name)
        if name in optional and not value:
            continue
        if isinstance(value, (list, tuple)):
            value = ",".join(str(one) for one in value)
        parts.append("--%s %s"
                     % (name.replace("_", "-"), documents.quoted_for_a_command_line(value)))
    return " ".join(parts)


def value_taking_options(command: str) -> frozenset:
    """The long options of subcommand `command` that CONSUME the next word, off the shipped parser.

    ASKED BY THE KITS' `gate_dispatch` (DEC-0107, seam of TSK-0149). A hook cannot read what a word
    the SHELL builds will become, but it can read WHERE that word stands -- and a word this parser
    consumes as the VALUE of the option before it can never be read as an option itself, however it
    expands. Which options do that is a property of this parser and of nothing else, so it is
    derived here: an option that gains a value, or a whole new subcommand, needs no second edit in
    three hook copies.

    LONG OPTIONS ONLY, because that is the form argparse resolves by unambiguous PREFIX and the
    form the caller has to place; a short option is one character and carries no prefix question.
    An unknown subcommand answers with the empty set, which makes every position fail closed at the
    caller rather than open.
    `tools/test_hooks_v2.py::test_a_quoted_expansion_the_parser_takes_as_a_value_is_not_a_classification`
    """
    parser = build_parser()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if not isinstance(choices, dict) or command not in choices:
            continue
        return frozenset(
            option
            for inner in choices[command]._actions if inner.nargs != 0
            for option in inner.option_strings if option.startswith("--"))
    return frozenset()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=INVOCATION, description="V2 state-kernel commands (HARNESS_V2_SPEC.md II.4)"
    )
    # NOT a flag a role types: the shim fills it in from the repo root and refuses it in argv
    # (`scripts/harness.py`). It stays on the parser -- and stays VISIBLE in `--help` -- because
    # the installer position above really does need it, and a flag that works while the help
    # denies it is the same defect as a help that promises one that does not.
    parser.add_argument("--root", default="project_memory",
                        help="state directory; for the pre-install installer position only -- the "
                             "installed entry point resolves it and refuses this flag")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="read-only activation/diagnosis report")
    sub.add_parser("validate", help="fail-closed state validation (exit 1 on errors)")
    # THE MECHANICAL HALF OF THE COMMENT DUTY (FR-0007), and a command of its own rather than one more
    # branch of the state validator: its subject is the project's FILES, not its items, and it needs
    # git to name them -- so a project without one gets a refusal it can read instead of a validation
    # that silently lost a check. The constitutions name this command where they state the duty.
    sub.add_parser("sweep-pointers",
                   help="report every citation in this project's own files that resolves at "
                        "nothing -- a named test the tree does not define, an item id this store "
                        "does not hold (exit 1 on findings)")
    # NAMES BOTH ARTEFACTS because the command writes both (`state._regenerate_index_locked`): a
    # help line that mentions only the index is a description one release out of date the moment
    # somebody looks for the human-readable view under `generated/`.
    sub.add_parser("generate-index",
                   help="regenerate generated/index.yaml and the board rebuilt with it")
    # THE PRODUCER OF `INV.verified` (FR-0039). It takes no status: what an invariant's check
    # resolves to is a measurement of the repository, not a choice, so the only argument is WHICH
    # invariants to re-measure -- none means all of them.
    verify = sub.add_parser("verify-invariants",
                            help="re-measure every invariant's check and record what it resolves "
                                 "to; exits 1 while one of them resolves to no test")
    verify.add_argument("item_ids", nargs="*", metavar="INV-nnnn",
                        help="the invariants to re-measure (default: every active one)")
    brief = sub.add_parser("generate-session-brief", help="regenerate generated/session_brief.yaml")
    brief.add_argument("--kit", required=True)
    brief.add_argument("--kit-version", required=True)
    brief.add_argument("--enforcement", choices=["hard", "audited"], required=True)
    # The ONE producer of QA evidence. It is a `capture` specialised to a single type, and
    # deliberately so: Evidence is the only item a specialist role is told to hand back on
    # its own (spec II.2 -- no project status, no approval, no automaton to walk), so it is
    # the only capture that needs no orchestrator judgement between the finding and the
    # file. Everything else still goes through the generic capture command the CLI shim
    # brings with it.
    evidence = sub.add_parser("evidence", help="record a test/review/acceptance/audit Evidence item")
    evidence.add_argument("--kind", required=True, choices=sorted(EVIDENCE_KINDS))
    evidence.add_argument("--result", required=True, choices=sorted(EVIDENCE_RESULTS),
                          help="the verdict the merge gate reads")
    evidence.add_argument("--related", required=True, action="append", metavar="ITEM_ID",
                          help="the item this evidence examined (repeatable)")
    evidence.add_argument("--summary", required=True)
    # Required, like `--related`: those two are what make the record evidence rather
    # than an assertion (backlog_types.NONEMPTY_FIELDS). The kernel refuses an empty
    # one anyway; asking argparse first is what turns that into a usage error naming
    # the flag, at the moment the role is typing the command.
    evidence.add_argument("--artifact-ref", required=True, action="append", metavar="PATH",
                          dest="artifact_refs",
                          # STATE-RELATIVE, and that is not cosmetic: `gate_write_scope`
                          # refuses any write-capable command line that names the state
                          # directory, so an argument spelling `project_memory/...` would
                          # make this very command unrunnable for the role that needs it.
                          help="where the raw proof lives, relative to the state directory "
                               "(e.g. staging/TSK-0007/coverage.html; repeatable) -- evidence "
                               "references its artefacts, never inlines them")
    # WHAT THE RUN COVERED (FR-0040). Optional on the flag surface because the field is optional
    # on the type, and the type's reason is in `backlog_types.RUN_SCOPES`: an `EVD` is immutable,
    # so a duty added here reaches only new records anyway. What the pair buys is read at the
    # merge -- a PASS declaring `selection` is not a delivery verdict -- and the kernel refuses
    # one of the two without the other, so a role cannot claim a scope without naming the run.
    # AND REQUIRED SINCE BUG-0192, both of them. The reading end cannot be tightened -- an `EVD`
    # is immutable, so every record a project already holds would become a validator error no
    # command can repair -- which leaves the surface that records NEW ones, and this is it: a run
    # that does not say how much it covered counts as a full one, and that is a partial run
    # opening a merge in silence. The pair is refused half-declared in `state.capture_preflight`,
    # so requiring one and not the other would only move the refusal.
    # `tools/test_hooks.py::test_every_evidence_command_a_text_spells_names_every_argument_the_cli_requires`
    # reads this parser's required set and holds it against every shipped text that spells the
    # call out; those texts belong to the kit stream, so that node is RED until its half lands.
    evidence.add_argument("--run-command", required=True, metavar="LINE",
                          help="the command line that produced this verdict, verbatim -- what an "
                               "auditor re-runs")
    evidence.add_argument("--run-scope", required=True, choices=sorted(RUN_SCOPES),
                          help="whether that command covered the whole surface or a selection; a "
                               "passing `selection` is recorded and does NOT open a merge, and a "
                               "record that declares nothing would count as a full run (BUG-0192)")
    # WHAT STOPPED A RUN THAT NEVER HAPPENED (FR-0082). Not `required` on the parser and not
    # optional in effect: the kernel refuses a `%s` result without it and refuses it under any
    # other result (`state.capture_preflight`), so argparse would have to know the value of
    # `--result` to state the duty -- which is exactly the condition a flag surface cannot carry.
    # The refusal names the flag, at the moment the role runs the command.
    # WHAT KIND OF FAILURE A FAILED RUN WAS (DEC-0107). Not `required` and not optional in effect,
    # exactly like the blocked reason above: the kernel refuses it under any result but a fail
    # (`dispatch.fail_class_refusal`), so argparse would have to know the value of `--result` to
    # state the duty. What it buys is at the next lease -- a run the verifying role calls narrow
    # does not climb the rung -- and WHO may write it is measured rather than trusted: the state
    # names the writing role from the bound lease, and the kit's gate_dispatch asks the same
    # predicate with the agent it sees.
    evidence.add_argument("--fail-class", dest=FAIL_CLASS_FIELD, choices=sorted(FAIL_CLASSES),
                          help="what kind of failure this was: %s. Only for --result %s, only "
                               "from a judging role, and never from the role whose order it is "
                               "(DEC-0107)"
                          % ("; ".join("%s = %s" % (word, FAIL_CLASSES[word].does)
                                       for word in sorted(FAIL_CLASSES)), FAILING_RESULT))
    evidence.add_argument("--%s" % BLOCKED_REASON_FIELD.replace("_", "-"), metavar="SENTENCE",
                          dest=BLOCKED_REASON_FIELD,
                          help="required for --result %s and refused for any other result: what "
                               "stopped the run. A %s verdict closes the merge exactly as a fail "
                               "does; the sentence is what keeps a later reader from taking it for "
                               "a checked fact -- nothing was checked."
                               % (BLOCKED_RESULT, BLOCKED_RESULT))
    # THE GENERIC ITEM PRODUCER (spec II.4 `capture`). Its body arrives on STDIN as JSON, and both
    # halves of that are forced rather than chosen:
    #   * STDIN, because an item's fields include lists of mappings (`acceptance_criteria:
    #     [{id, text}]`) that no flag surface expresses, and the obvious alternative -- a `--from
    #     project_memory/staging/<key>/item.yaml` -- cannot be typed: `gate_write_scope` refuses a
    #     write-capable pipeline whose COMMAND LINE names the state directory (measured: rc 2,
    #     "names the canonical state directory"). A body on stdin names nothing.
    #   * JSON and not YAML, although the store is YAML. The body decides the item's HASHED fields,
    #     and YAML 1.1's implicit typing silently changes values on the way in -- `no` becomes
    #     False, `1.10` becomes a float, `12:30` becomes 750. A value that means one thing to the
    #     role who typed it and another to `subject_manifest_hash` is the approval-invalidation
    #     class this kernel exists to end, and `kernel/hashing.canonical_json` already fixes JSON
    #     as the form a hash is defined over.
    # The type list is the kernel's own (`REQUIRED_FIELDS`), so a new capturable type needs no
    # edit here.
    capture = sub.add_parser(
        "capture", help="create a typed item from a JSON object on stdin")
    capture.add_argument("item_type", choices=sorted(REQUIRED_FIELDS))
    # A MEASURED, OPEN GAP -- and the ONLY way to file one (FR-0087, DEC-0073). The flag says THAT
    # this record is a hole; the kernel says WHICH number it gets, by a max-scan over the store.
    # That split is the whole wish: hole numbers used to be handed out by hand and by message, and
    # two of one generation's were found in no item at all. A body that carries `hole_number` is
    # refused by `state.capture` for the same reason a body carrying `status` is, so there is no
    # second route and no way to choose a number.
    capture.add_argument("--hole", action="store_true",
                         help="file this item as a measured, open gap: the kernel stamps the next "
                              "free hole number (the number is never chosen by the caller). The "
                              "record owes `%s` -- what takes the place of the protection -- from "
                              "the moment a user accepts it as a named exception"
                              % HOLE_LIMIT_FIELD)
    # The TSK work order as FLAGS. Same producer as `capture TSK` (both end in
    # `dispatch.create_task`), different surface: a work order is flat, it is the thing a role
    # types most often, and every one of its fields is a gate input worth naming on the line.
    task = sub.add_parser("create-task", help="create a TSK work order (kernel sets root_revision)")
    task.add_argument("--product-requirement", required=True, metavar="ITEM_ID",
                      help="the PR/RQ root this task serves")
    task.add_argument("--derives-from", required=True, metavar="ITEM_ID",
                      help="the item whose criteria this task serves (root, BUG, CR, EXP)")
    task.add_argument("--type", required=True, choices=sorted(TASK_TYPES), dest="task_type")
    task.add_argument("--assigned-role", required=True,
                      help="the installed role the dispatch gate matches the spawn against")
    task.add_argument("--acceptance-ref", required=True, action="append", dest="acceptance_refs",
                      metavar="AC_ID", help="criterion this task is measured against (repeatable)")
    # QUOTE THE GLOB, and the help says so because the failure is silent in the one case that
    # matters. `**` and `*` are what `gate_write_scope._matches` reads, but the SHELL sees them
    # first: once `src/` exists, `--allowed-scope src/**` is expanded before this parser is
    # reached. With several matches argparse rejects the extra words; with exactly ONE the scope
    # is quietly narrowed to that single file and the task runs under a grant nobody wrote.
    task.add_argument("--allowed-scope", action="append", dest="allowed_scope",
                      metavar="PATH", help="what the specialist may write (repeatable); this IS "
                                           "gate layer 3's input. QUOTE any glob -- "
                                           "`--allowed-scope 'src/**'` -- or the shell expands it "
                                           "against the working tree before the kernel sees it. "
                                           "Either this or --read-only, never neither")
    # A READ-ONLY ORDER SAYS SO (PR-0011 AC-8, BUG-0266): the auditor's route binds a work order
    # that claims NO writable scope (`dispatch._claims_writable_scope`), and until this flag the
    # line could not express one -- `--allowed-scope` was required, so the only walkable auditor
    # was an ordinary order with a writable scope. An order names its scope or says it is
    # read-only; an order that says neither is refused, because an empty scope by omission is the
    # BUG-0023 shape one field over.
    task.add_argument("--read-only", action="store_true", dest="read_only",
                      help="this order writes nothing outside its own staging/<task-id>/ -- the "
                           "shape a routine (audit) approval dispatches; refused together with "
                           "--allowed-scope")
    task.add_argument("--forbidden-scope", action="append", dest="forbidden_scope", metavar="PATH",
                      help="what the specialist may NOT write (repeatable); quote globs, for the "
                           "reason --allowed-scope gives")
    task.add_argument("--required-input", action="append", dest="required_inputs",
                      metavar="PATH_OR_ID")
    task.add_argument("--expected-output", action="append", dest="expected_outputs", metavar="PATH")
    task.add_argument("--dependency", action="append", dest="dependencies", metavar="ITEM_ID")
    task.add_argument("--design-ref", metavar="DSN_ID",
                      help="required for a UI task once its root has a confirmed design (II.6)")
    task.add_argument("--%s" % scopes.SEAM_FIELD.replace("_", "-"), action="append",
                      dest=scopes.SEAM_FIELD, metavar="PATH",
                      help="a path this order shares with another ON PURPOSE, applied in the merge "
                           "round (repeatable). The pre-dispatch scope check (`kernel.scopes`) "
                           "subtracts it before judging a pair, and only where BOTH orders "
                           "declare it.")
    # THE PM'S TIER ASK PER ORDER (DEC-0091 (1)/(2)): the rung is a name of the kit's ladder and
    # the kernel refuses any other (`dispatch.rung_vocabulary`); the effort's vocabulary is the
    # kernel's own ordering, so argparse can refuse it at the line. Both LIFT the ladder's answer
    # and never lower it -- the floor and the top stay the kit's.
    task.add_argument("--%s" % dispatch.RUNG_KEY, dest=dispatch.RUNG_KEY, metavar="RUNG",
                      help="the rung this slice needs, as the PM judges it -- one of the kit's "
                           "ladder rungs (dev/research: sonnet < opus < fable). The lease takes "
                           "the HIGHER of this and the ladder's floor for the role; it never "
                           "lowers a role below its class (DEC-0091).")
    task.add_argument("--%s" % dispatch.EFFORT_KEY, dest=dispatch.EFFORT_KEY,
                      choices=list(dispatch.EFFORT_LEVELS),
                      help="the effort this slice needs; the lease takes the HIGHER of this and "
                           "the goal's effort, capped at the kit's highest declared effort. "
                           "xhigh only for a named step, never as a standing setting (DEC-0088 (4)).")
    # The specialist's hand-back. Field names and the status vocabulary come from the SCHEMA the
    # kernel validates against, not from a copy here -- `submit_result` would reject a divergence
    # anyway, but it would reject it after the role had typed the command.
    envelope_fields = load_schema("result_envelope")["fields"]
    submit = sub.add_parser("submit-result", help="hand a specialist's result envelope back")
    submit.add_argument("--task-id", required=True, metavar="TSK_ID")
    # NOT `required=True` any more, and `--from` is why (BUG-0048). A specialist whose toolset
    # grants no command-running tool cannot type this line at all, so the lead books its result
    # in; retyping the envelope out of the child's final message makes the LEAD the author of
    # what the kernel records. `--from` lets the specialist's OWN bytes travel instead: it stages
    # the envelope under its task's staging key -- the one place `gate_write_scope` lets a bound
    # specialist write -- and the lead names the file. `_submitted_envelope` refuses the flag
    # route without the fields the schema requires, which is what these three lines used to do.
    submit.add_argument("--role")
    submit.add_argument("--status-proposal",
                        choices=list(envelope_fields["status_proposal"]["enum"]))
    submit.add_argument("--summary",
                        help="<= %d chars; raw logs are REFERENCED, never inlined"
                             % envelope_fields["summary"]["max_len"])
    submit.add_argument("--from", dest="envelope_file", metavar="NAME",
                        help="a staged envelope to hand back verbatim: the BARE FILE NAME of a "
                             "JSON object inside this task's own staging directory, e.g. "
                             "`--from result.json`. The path is composed by the kernel, so a name "
                             "that walks out of that directory is refused. Use this to book in a "
                             "specialist that cannot run a command itself; the other flags are "
                             "then unnecessary and a conflicting one is refused.")
    # Paths are repo-relative; anything inside the state directory is named RELATIVE TO IT
    # (`staging/<task-id>/...`), exactly as `evidence --artifact-ref` is and for the same measured
    # reason -- the shell gate refuses a write-capable command line that names `project_memory`.
    submit.add_argument("--output", action="append", dest="outputs", metavar="PATH",
                        help="what the task produced (repeatable); state-relative inside the "
                             "state dir, e.g. staging/TSK-0007/proposal.md")
    submit.add_argument("--evidence", action="append", dest="evidence", metavar="EVD_ID")
    submit.add_argument("--scope-touched", action="append", dest="scope_touched", metavar="PATH")
    submit.add_argument("--followup", action="append", dest="followups")
    # PHASE 1 OF THE APPROVAL PROTOCOL, and the reason it has to be on this surface: without it
    # `create_pending_request` had NO caller in the shipped tree, so no `[APR-REQ:<id>]` question
    # could exist, so `gate_approval` blocked every AskUserQuestion that looked like one, so no
    # APR could ever be minted -- and since `transition` now demands an APR on the edges an
    # approval commits, a root item could never leave DRAFT in a real project. The sperre had no
    # walkable counterpart. Measured before this command: `approvals/pending/` stays empty and
    # `transition PR-0001 APPROVED` refuses forever.
    #
    # IT REQUESTS, IT DOES NOT MINT, and that line is where the provenance lives. This writes the
    # immutable pending request and prints the question the KERNEL composed; the user mints by
    # ANSWERING it, and `approvals.mint` still refuses every caller but `gate_approval.py`.
    # Nothing about spec II.2's chain changes -- what changes is that the chain now has a first
    # link a role can reach.
    #
    # THE KINDS ARE ASKED OF THE FUNCTION THAT DECIDES THEM (`approvals.item_derived_kinds`,
    # which probes `item_subject_manifest`). A command line can carry an item id; it cannot carry
    # an analysis question, a read-only scope and a cadence, so a kind whose manifest is not
    # item-derived keeps needing a caller that builds one. This used to read
    # `APR_KINDS - EXPIRING_KINDS`, which is a different property (time-boxed vs
    # content-invalidated) that agrees today -- a third statement of one split is how they drift.
    #
    # THE SECOND HALF OF THE SPLIT, added 2026-08-02 because its absence was a wall: this parser
    # offered `item_derived_kinds()` only, so `push` -- a kind in `APR_KINDS`, with its own
    # manifest builder and a gate refusing every push without one -- had no way to be requested at
    # all. Measured before this: no project could publish anything, ever, and `gate_push_token`'s
    # remedy named a command the parser did not have. The flags come from the BUILDER'S SIGNATURE,
    # exactly as a freeze body's keys do, so a second line kind arrives correctly flagged.
    request = sub.add_parser(
        "request-approval",
        help="open the approval question (phase 1); the USER mints by answering it")
    request.add_argument("kind", choices=sorted(set(approvals.item_derived_kinds())
                                                | set(approvals.line_manifest_kinds())))
    request.add_argument("item_id", metavar="ITEM_ID", nargs="?",
                         help="the item to approve -- required for %s, and refused for %s, whose "
                              "subject is the flags below rather than an item"
                              % ("/".join(sorted(approvals.item_derived_kinds())),
                                 "/".join(approvals.line_manifest_kinds())))
    for line_kind, builder in sorted(approvals.LINE_MANIFEST_BUILDERS.items()):
        for name in manifest_parameters(builder):
            flag = "--" + name.replace("_", "-")
            if flag in {action.option_strings[0] for action in request._actions
                        if action.option_strings}:
                continue          # two line kinds sharing a manifest key share the flag
            # THE HELP SAYS WHERE THE VALUE COMES FROM, in the resolver's own words, and says it
            # is refused where that source is not the role. It used to say "default: read from the
            # worktree" for every resolved key, which was true of `head` and false of the two the
            # kit's preset file answers -- and it read as an override the line may set, which is
            # exactly what `_line_manifest` refuses. The flag stays VISIBLE for the reason `--root`
            # does: a flag the parser accepts and the command refuses must be findable in `--help`.
            entry = LINE_MANIFEST_RESOLVERS.get(name)
            request.add_argument(
                flag, metavar=name.upper(),
                help="%s subject: %s%s" % (line_kind, name,
                                           " -- NOT typed here: %s, and a value is refused"
                                           % entry[1] if entry else ""))
    # THE TERM OF A TIME-BOXED APPROVAL, in days, for the kinds that carry a clock at all
    # (`approvals.EXPIRING_KINDS`; refused for the others). REQUIRED for a routine (PR-0011
    # AC-8): a standing permission for a recurring run is what the user is signing, and how long
    # it stands is the part of it only the user can decide -- the question renders the date.
    # THE USER'S ANSWER ABOUT A GOAL NOBODY VERIFIED (DEC-0113). Not a claim the PM makes about
    # the project -- the words the user said when asked, once per goal, before the acceptance
    # question goes out. Refused for every other kind by the branch below, because a kind that
    # cannot be accepted has no such question.
    request.add_argument("--unverified-answer", default=None, metavar="TEXT",
                         help="what the user answered when asked whether accepting this goal "
                              "without any verification run is intended (DEC-0113); for "
                              "`acceptance`, refused for every other kind")
    request.add_argument("--expires-in-days", type=float, default=None, metavar="DAYS",
                         help="how many days the approval stays valid; required for `routine`, "
                              "optional for the other time-boxed kinds (default one hour), refused "
                              "for a kind that carries no clock")
    # THE ITEMS ONE QUESTION CLOSES (PR-0012 AC-1). A list on the line rather than one id per call,
    # because the whole point of the kind is that ONE answer of the user's settles all of them; the
    # kinds it is accepted for are derived from the resolver that reads it, and it is refused for
    # every other kind by name.
    request.add_argument("--" + BATCH_ARGUMENT, nargs="+", metavar="ITEM_ID", default=None,
                         help="the items one question closes -- for %s (at most %d per question); "
                              "refused for every other kind"
                              % ("/".join(sorted(kinds_reading_argument(BATCH_ARGUMENT)))
                                 or "no kind on this build", approvals.BATCH_LIMIT))
    # The lease + header, in one command, because they are one moment: spec II.4 orders
    # "READY -> kurzlebige Dispatch-Lease mit Nonce und TTL -> Header", and the gate that reads the
    # header runs at PreToolUse of the spawn -- AFTER the model has composed the prompt. A lease
    # created there would be a lease minted for a nonce the model chose, which is the bearer-token
    # shape the nonce exists to prevent. So the lease is created BEFORE, and this prints the one
    # header line `dispatch_header` produces, for the role to copy verbatim.
    # NO `--ttl`: "kurzlebig" is the property spec II.4 names, and a flag would let the supervised
    # party decide how short short is. The kernel default stands.
    lease = sub.add_parser(
        "dispatch", help="lease a READY task and print its HARNESS_DISPATCH header")
    lease.add_argument("task_id")
    # THE TREE THE ORDER IS GRANTED FOR (stream D's C-3). A flag and not a derivation, because the
    # one case the field exists for is the one the kernel cannot see: several specialists working
    # in separate checkouts against ONE state directory, where "where the state lives" is the same
    # answer for all of them. Left out, the lease records that tree, which is the truth for every
    # project that runs in one.
    lease.add_argument("--worktree", metavar="PATH",
                       help="the checkout this dispatch is granted for; default is the tree the "
                            "state directory lives in")
    # THE LADDER ANSWER WITHOUT A LEASE (DEC-0077 (5)): the rung and effort a lease would carry,
    # read-only, so a lead can see what an order gets -- and why -- before it mints, and a pilot
    # can measure the derivation without spending a lease on it. The neighbouring command is NOT
    # named in a code span here on purpose: three of them in one block make this block read as a
    # presentation of the whole command surface, and
    # `test_every_span_that_presents_the_command_surface_names_all_of_it` (tools/test_hooks.py)
    # then requires it to name all of it -- measured red on exactly this comment, 2026-09-06.
    ladder = sub.add_parser(
        "ladder", help="the rung and effort an order runs on, derived from the kit's ladder.yaml "
                       "and the state (DEC-0077); read-only, mints nothing")
    ladder.add_argument("task_id")
    ladder.add_argument("--provider", default=None,
                        help="the answer for this row of model_tiers.yaml `tiers:` (claude, codex); "
                             "default: the platform whose spawn holds the rung. The top differs per "
                             "provider (DEC-0114 (4))")
    # THE CHECKPOINT PAIR (DEC-0044). Written and read through the kernel for the same reason the
    # result envelope is: the two digests that decide adoption later are MEASUREMENTS, and a record
    # whose integrity data the checked party supplied would verify itself (`kernel/checkpoints.py`).
    # The body is on STDIN like `capture`'s, and for the second of that command's two reasons as
    # well -- an artefact list is a list of mappings once the kernel has measured it, and a
    # `--from project_memory/staging/...` cannot be typed past `gate_write_scope` at all.
    checkpoint = sub.add_parser(
        "checkpoint",
        help="record resumable progress for a dispatched task (JSON body on stdin: next_step, "
             "outputs[{output_index, progress, artifacts[, note]}]) -- a successor MAY adopt it "
             "only after the verification command below confirms it",
        description="Record resumable progress for a task that is dispatched RIGHT NOW, so a "
                    "session break does not take the work with it (DEC-0044). JSON body on stdin: "
                    "{\"next_step\": \"...\", \"outputs\": [{\"output_index\": 0, \"progress\": "
                    "\"partial\", \"artifacts\": [\"src/x.py\"], \"note\": \"...\"}]}. "
                    "`output_index` addresses the task's expected_outputs in order; artefact paths "
                    "are relative to the project root, have to stay inside it (an absolute one, a "
                    "`..` and a link that leads out are refused) and are hashed by the kernel as "
                    "they are recorded. Nothing else is written, and the record is a PROPOSAL in "
                    "staging/<TSK-ID>/, never state.")
    checkpoint.add_argument("task_id")
    status = sub.add_parser(
        "checkpoint-status",
        help="verify a task's checkpoint (read-only) and print what was measured; exit 1 when it "
             "is absent, stale or broken -- which are one answer: treat it as absent")
    status.add_argument("task_id")
    transition = sub.add_parser(
        "transition",
        help="status transition via the automaton; an edge an approval COMMITS needs that "
             "approval in force, and the mint walks such an edge itself")
    transition.add_argument("item_id")
    transition.add_argument("to_status")
    transition.add_argument("--approved-retry", action="store_true")
    # THE SANCTIONED EDIT PATH (BUG-0001). `state.update_item` existed with its approval
    # invalidation (spec II.2) but had no CLI surface, so a typo in a captured field could only be
    # fixed by cancelling the item and recapturing it (measured 2026-08-04). The body is on STDIN
    # for the same two reasons `capture`'s is -- a change can carry lists and mappings no flag
    # expresses, and a `--from project_memory/...` cannot be typed past `gate_write_scope`. The
    # KERNEL-SET fields (`id`, `status`, `revision`, `approval_ref`, `created`) are NOT accepted:
    # they change only through their own operations (capture/transition/approve), and this surface
    # names no flag for them precisely because it does not decide them -- `update_item` refuses any
    # such key in the body, so the automaton cannot be side-stepped by writing `status` here.
    update = sub.add_parser(
        "update", help="edit an item's fields through the kernel (JSON object of changes on "
                       "stdin); invalidates a current approval when a hashed field changes")
    update.add_argument("item_id")
    # THE PROMOTION COMMANDS (see FREEZE_OPERATIONS for what they unblock). Generated from that
    # mapping, so the surface cannot fall behind the kernel; the body is on STDIN for the same two
    # reasons `capture`'s is -- `derives_from`, `assets` and `packaging` are a list and two mappings
    # no flag surface expresses, and a `--from project_memory/staging/...` cannot be typed at all
    # (`gate_write_scope` refuses a write-capable pipeline whose COMMAND LINE names the state
    # directory). Nothing on this line names it: a staging KEY, an item id and a file NAME are
    # state-relative by construction, exactly as `evidence --artifact-ref` is.
    for command, operation in sorted(FREEZE_COMMANDS.items()):
        contract = freeze_parameters(operation)
        summary = (
            "promote the staged %s to canonical state (spec II.6/II.6a); JSON body on stdin, "
            "required: %s%s" % (
                command.split("-", 1)[1],
                ", ".join(sorted(name for name, (required, _t) in contract.items() if required)),
                "; optional: %s" % ", ".join(
                    sorted(name for name, (required, _t) in contract.items() if not required))
                if any(not required for required, _t in contract.values()) else ""))
        # THE CONTRACT GOES INTO `description` AS WELL AS `help`, because the two are printed in
        # different places and a role reads the wrong one: `help` appears only in the PARENT's
        # `--help`, so `freeze-architecture --help` -- the command a role actually types when it
        # wants to know what to send -- printed `usage: ... freeze-architecture [-h]` and nothing
        # else (measured 2026-08-02). A body-taking command whose own help does not name its body
        # is a command with no discoverable contract.
        sub.add_parser(command, help=summary, description="%s. The keys are exactly the "
                       "operation's own parameters; send them as ONE JSON object on stdin, e.g. "
                       "`%s %s <<'EOF'` … `EOF`." % (summary, INVOCATION, command))
    # THE ROUTE OUT OF THE PRESET DEAD END (BUG-0041). Before this, changing which specialist
    # roles a project has meant editing `project_config.yaml` and running the scaffold -- and both
    # are refused from inside a session, on purpose, so the lead's only move was to send the USER
    # to a text editor and a terminal. Pilot 3 measured what that is worth to a non-technical user:
    # she got no further than finding the folder. `kernel/presets.py` carries the design; what
    # belongs here is that this is a NORMAL command line -- it names neither the state directory
    # nor the enforcement layer, which is what lets a role type it at all.
    preset = sub.add_parser(
        "set-preset",
        help="record a user-approved team preset and install exactly its roles (needs a minted "
             "`preset` approval; asks for a session restart afterwards)")
    preset.add_argument("preset", help="the preset to move to; the kit's presets.yaml names them "
                                       "and an unknown one is refused with the list")
    # THE SECOND HALF OF THE SAME DEAD END (FR-0006). A preset change and a kit update were both
    # "ask the USER to run the scaffold", and the second one is the wider of the two: it replaces
    # the hooks, the kernel, the settings and the constitution. `kernel/kitupdate.py` carries the
    # design; what belongs here is that this command takes NO argument -- which kit, which release
    # and which direction are the project's and the staging's own statements, and a role typing
    # any of them would be typing over the files that own them.
    sub.add_parser(
        kitupdate.COMMAND,
        help="install the kit release staged on this machine over this project (needs a minted "
             "`%s` approval; refuses a downgrade and stops the session afterwards)" % kitupdate.KIND)
    # THE ROUTES TO THE PIN AND THE ROLLBACK (FR-0041, the seam `H87` names). The MECHANISM is built
    # and measured at all three doors (`kitupdate.assert_not_pinned`,
    # `kitupdate.assert_no_pin_blocks_a_rollback`); what nobody could do from a session was FIND it.
    # Measured on the shipped entry point of a field copy: 25 subcommands, no pin, no rollback -- so
    # a user who wanted to hold their project at a release was sent to a text editor by whoever
    # happened to know the file name.
    #
    # THEY PRINT AND THEY DO NOT ACT, which is the design and not a half-build. A pin is the USER's
    # statement about their own project -- that is why it lives where a session's tool writes are
    # refused (`kitupdate.PIN_FILE`) -- and the two levers differ in direction: setting one only
    # ever ADDS a refusal, lifting one removes the only thing standing between this session and a
    # replaced enforcement layer. The rollback is the same argument once more: it replaces the
    # installed bundle exactly as the update command one block up does, and that one may only do it
    # on a minted approval, which no kind covers a rollback with. So these three name the deed the user does
    # outside the session, filled in with this project's own bundle, and
    # `tools/test_kitupdate.py::test_the_kit_pin_routes_print_and_never_write` holds them to it.
    sub.add_parser(
        "pin-kit",
        help="PRINTS how to hold this project at the release it runs -- the file and the two lines "
             "the user puts in it; writes nothing itself")
    sub.add_parser(
        "unpin-kit",
        help="PRINTS the pin this project carries and the file the user deletes to lift it; "
             "removes nothing itself")
    sub.add_parser(
        "rollback-kit",
        help="PRINTS which previous bundle could be replayed here and the installer line that does "
             "it; installs nothing itself")
    # THE THIRD DEAD END OF THE SAME FAMILY (FR-0049 step 5). An office project meeting a document
    # class its Aktenplan does not know could not file it -- correctly -- and could not grow the
    # plan either: `filing_plan.yaml` is a kit document, so no tool write reaches it and, until
    # `kernel/filing.py`, no command wrote it. The flags are the manifest builder's own parameters,
    # exactly as the approval request above renders them, so the line that ASKS and the line that ACTS
    # cannot come to describe two different rules; `_line_manifest` builds the same manifest from
    # them and `filing.apply` refuses unless a live approval carries it.
    rule = sub.add_parser(
        filing.COMMAND,
        help="append a user-approved rule to %s (needs a minted `%s` approval; same flags as the "
             "request that opened the question)" % (filing.PLAN, filing.KIND))
    for name in manifest_parameters(approvals.LINE_MANIFEST_BUILDERS[filing.KIND]):
        rule.add_argument("--" + name.replace("_", "-"), metavar=name.upper(),
                          help="the approved rule's %s -- the approval is looked up by the "
                               "manifest these flags build, so they are the ones the user was "
                               "shown" % name)
    # THE SAME DEAD END ACROSS EVERY REMAINING KIT DOCUMENT (BUG-0071). Each kit ships prose and
    # configuration documents whose CONTENT its constitution assigns to a role, and after the
    # install nobody could write one. The user hand-copied a specialist's staged file into the
    # target document four times in ONE day. HOW MANY documents that is stands in exactly one
    # place, `kernel/documents.py`'s own docstring, beside the derivation that measured it -- a
    # count restated here is a count that goes stale where nobody is looking (SR-0008), and this
    # one already had: it read TWELVE. That module also argues why this is one generic route and
    # not a
    # fourth special case; what belongs here is that its flags are the manifest builder's own
    # parameters, exactly as the filing-rule command's are one block up, so the line that ASKS and
    # the line that ACTS cannot describe two different writes.
    proposal = sub.add_parser(
        documents.COMMAND,
        help="apply a user-approved staged proposal to a kit document -- ADDS only, never changes "
             "or removes (needs a minted `%s` approval; same flags as the request that opened the "
             "question)" % documents.KIND)
    for name in manifest_parameters(approvals.LINE_MANIFEST_BUILDERS[documents.KIND]):
        entry = LINE_MANIFEST_RESOLVERS.get(name)
        proposal.add_argument(
            "--" + name.replace("_", "-"), metavar=name.upper(),
            help="the approved proposal's %s%s" % (
                name, " -- NOT typed here: %s, and a value is refused" % entry[1] if entry
                else "; the approval is looked up by the manifest these flags build, so they are "
                     "the ones the user was shown"))
    # THE OTHER HALF OF THAT DEAD END (FR-0067). The command above (`documents.COMMAND`) adds;
    # this one is the only route that may overwrite or remove what a kit document already records,
    # which until now was
    # the one change left to the user's own editor -- and a hand edit into a kit document is the
    # write no gate and no hash ever sees. Its flags come from ITS builder's signature for the same
    # reason, and the two commands share every flag name they share a meaning for.
    #
    # THE SPELLING COMES FROM THE MODULE and not from this comment, twice over: the name above is
    # `documents.COMMAND` because a literal here would be a second place the command is spelled --
    # and because a block of this file that names three subcommands in code spans reads as a
    # PRESENTATION of the whole command surface to
    # `test_hooks.test_every_span_that_presents_the_command_surface_names_all_of_it`, which then
    # requires it to name all of them. Measured twice in this round, once per added comment.
    revision = sub.add_parser(
        documents.REVISION_COMMAND,
        help="apply a user-approved staged revision to a kit document -- may REPLACE and DELETE, "
             "and every spot stands in the approval question (needs a minted `%s` approval; same "
             "flags as the request that opened it)" % documents.REVISION_KIND)
    for name in manifest_parameters(approvals.LINE_MANIFEST_BUILDERS[documents.REVISION_KIND]):
        entry = LINE_MANIFEST_RESOLVERS.get(name)
        revision.add_argument(
            "--" + name.replace("_", "-"), metavar=name.upper(),
            help="the approved revision's %s%s" % (
                name, " -- NOT typed here: %s, and a value is refused" % entry[1] if entry
                else "; the approval is looked up by the manifest these flags build, so they are "
                     "the ones the user was shown"))
    # THE REPORTING HALF of the dead-end family BUG-0041/BUG-0068/BUG-0070 (FR-0062). A session that
    # hits an infrastructure boundary tells the user -- and the report dies in the chat. This books
    # it into the project's own log instead, where the kit's maintainer reads it across repos. The
    # KERNEL is the writer, so the agent-write refusal under `project_memory/` stays intact; nothing
    # forces a session to call it, and `kernel/gaplog.py` says so rather than implying otherwise.
    gap = sub.add_parser(
        gaplog.COMMAND,
        help="record a kit gap in this project's own log (what you tried, what refused you)")
    gap.add_argument("--tried", required=True,
                     help="what this session was trying to do, in its own words")
    gap.add_argument("--refused", required=True,
                     help="the message that stopped it, verbatim")
    gap.add_argument("--title", default="", help="a one-line name (defaults to the start of --tried)")
    gap.add_argument("--item", default="", help="the item this happened under, if there is one")
    # THE DONE SIDE OF A DERIVED DUTY (BUG-0197 / H113). A kit's deadline register derives what
    # is OWED and had no way to record that it was DONE, so two of its five feeds stood until their
    # SOURCE changed. The KEY is what both sides re-derive -- the register prints it beside each
    # duty -- and `kernel/duties.py` carries why it is content-addressed rather than an id.
    duty_done = sub.add_parser(
        duties.COMMAND,
        help="record that a derived duty was met (the register prints the key beside the duty)")
    duty_done.add_argument("--key", required=True,
                           help="the duty's key, as the deadline register printed it")
    duty_done.add_argument("--what", required=True,
                           help="the duty's own sentence as it stood -- a reader a year from now "
                                "cannot re-derive the wording of a feed that has changed")
    duty_done.add_argument("--note", required=True,
                           help="what actually happened (\"Voranmeldung Q3 am 10.10. "
                                "uebermittelt\")")
    archive = sub.add_parser("archive", help="move a terminal item to archive/")
    archive.add_argument("item_id")
    # THE PRE-DISPATCH CHECK OF THE CUT (DEC-0062 (1)/(2), stream D requirement C-1). On the
    # kernel's own surface and not as a repo script, for the reason `kernel.scopes` gives: from a
    # skill directory there is no executable route at all (`gate_write_scope` refuses it, measured
    # as `H136`), and a script per kit would be a fourth spelling of a predicate that has to be
    # the SHIPPED gate's or it answers a different question.
    check_scopes = sub.add_parser(
        CHECK_SCOPES_COMMAND,
        help="do two open work orders own a common file? (exit 2 when they do)")
    check_scopes.add_argument("--only", nargs="*", default=None, metavar="TSK_ID",
                              help="check exactly these orders, whatever their status")
    check_scopes.add_argument("--seam", nargs="*", default=(), metavar="PATH",
                              help="paths shared on purpose for THIS run -- what the orchestrator "
                                   "is about to write into the orders. A seam an order already "
                                   "carries needs no flag; see `--%s` on create-task."
                                   % scopes.SEAM_FIELD.replace("_", "-"))
    sub.add_parser("sweep-leases", help="return expired leases to READY")
    # ...and the same job for the OTHER store that only ever grew. An approval request that ran out
    # of time is already inert everywhere it is read; what it was not, until this command, is
    # removable -- see `approvals.sweep_expired_requests` for the measured occasion.
    sweep = sub.add_parser(
        "sweep-requests",
        help="delete approval requests whose clock ran out (they can never mint); report the ones "
             "nobody can act on any more, and take back the ones that have stood too long")
    # THE SECOND CLOCK (BUG-0302). The expiry is the request's OWN bound and the sweep may delete
    # what it made permanent; staleness is the CALLER's judgement about a question that is still
    # live, so it takes the question back through `withdraw_request` -- recorded, never deleted.
    sweep.add_argument("--stale", type=float, metavar="HOURS",
                       help="also take back every request that has been standing longer than this "
                            "many hours; each is recorded in approvals/withdrawn/ with the reason")
    # TAKING BACK A QUESTION NOBODY ANSWERED (BUG-0302). Its own command and not a flag of the
    # sweep, because it names ONE request the caller decided about -- the sweep judges by a rule.
    # The command name is written WITHOUT backticks here on purpose: a block of this file that
    # names three commands in code spans reads as a span PRESENTING the command surface
    # (`tools/test_hooks.py::test_every_span_that_presents_the_command_surface_names_all_of_it`,
    # `_SURFACE_SPAN_MIN`), and this comment is an argument about one command, not an inventory.
    withdrawal = sub.add_parser(
        "withdraw-request",
        help="take back a pending approval question the lead replaced or the user rejected in "
             "prose; the record moves to approvals/withdrawn/ and the hook stops counting it")
    withdrawal.add_argument("request_id", metavar="APR-REQ-ID")
    withdrawal.add_argument("--reason", required=True, metavar="SENTENCE",
                            help="why the question was taken back -- stored with the record, "
                                 "because a withdrawal nobody explained is one the next reader "
                                 "has to guess about")
    # THE V1 IMPORT (spec II.10). Two halves of one command rather than two commands, because the
    # second half is only sound as the continuation of the first: `--dry-run` reads and prints a
    # DIGEST over everything it read, and `--plan <digest>` refuses unless it re-derives the same
    # value. Splitting them into `migrate-plan`/`migrate-apply` would have made "run the apply
    # without ever running the plan" a spelling that exists.
    #
    # NO APPROVAL KIND IS ASKED FOR HERE, and `kernel/migrate.py`'s docstring is where the reason
    # is argued rather than restated -- including why the kinds are named by ASKING
    # (`approvals.item_derived_kinds`, `approvals.line_manifest_kinds`) rather than counted: this
    # line said "all five" over a vocabulary of six and thereby put the two kinds that hash NEITHER
    # an item nor a commit on the wrong side of its own sentence. What the digest proves is that
    # the STATE has not moved since the run was presented -- not that a user consented -- and no
    # text in this harness may say otherwise.
    migration = sub.add_parser(
        "migrate", help="import V1 records into the V2 item store (spec II.10); --dry-run first")
    exclusive = migration.add_mutually_exclusive_group(required=True)
    exclusive.add_argument("--dry-run", action="store_true",
                           help="read the state and print what a run would do; writes nothing")
    exclusive.add_argument("--plan", metavar="DIGEST",
                           help="the digest the dry run printed; the run refuses any other state")
    # A FLAG AND NOT A BODY ON STDIN, unlike `capture`: these are scalar pairs the DRY RUN ITSELF
    # prints, so what a human does with them is paste a line back. Nothing here names a path, so
    # `gate_write_scope` has nothing to refuse.
    migration.add_argument("--map", action="append", dest="field_map", metavar="TYPE.FIELD=V1_FIELD",
                         help="which V1 field feeds a V2 required field the record does not spell "
                              "the same way (repeatable); the dry run prints the exact flags")
    # THE ONE THING THE IMPORT REFUSES TO GUESS ABOUT A FINISHED RECORD (SR-0004). A record spec
    # II.10's table calls finished is written under `archive/<TYPE>/<year>/`, and the year comes from
    # the record's own newest date. Where a V1 store carries no date at all -- `system_requirements
    # .yaml` carries none in either field project -- this is the answer, given once for the run,
    # rather than a year this command picked.
    migration.add_argument("--archive-year", type=int, metavar="YYYY",
                           help="the archive year for finished records that carry no date of "
                                "their own; the dry run blocks and asks for it when it needs it")

    # THE HOLE LIST AS ITEMS (FR-0087, DEC-0073), and it is a KERNEL command because it writes
    # canonical state -- which gate 1 gives exactly one writer. As a tool under `tools/` its one
    # writing run was a line no role inside a session could take: it had to be handed to the user
    # for a shell outside Claude Code, and a remote user does not have one (TSK-0126, merge
    # rework 3). `tools/migrate_holes.py` still exists and calls the same door, so there is one
    # door and not two.
    #
    # WHAT IT PROMISES, in the same shape `migrate` above does: without `--apply` nothing is
    # written and the plan is printed; the run is idempotent, because "is this number already in
    # the store" is asked of the STORE (`state.hole_by_number`) and not of a marker file; a number
    # two entries claim is a REFUSAL and not a silent second write; and `--reindex` writes the
    # document's generated pointer index and nothing else, which is what a hole captured through
    # `capture --hole` needs afterwards.
    hole_migration = sub.add_parser(
        "migrate-holes",
        help="migrate the H-numbered hole list of docs/POST_V2_WISHLIST.md into typed items "
             "(FR-0087/DEC-0073); without --apply nothing is written")
    hole_migration.add_argument(
        "--related-pr", metavar="PR-nnnn",
        help="the product goal these holes are filed under; required unless --reindex, which "
             "writes no item")
    hole_migration.add_argument(
        "--apply", action="store_true",
        help="write the items, the prose files and the generated index; without it the run is a "
             "plan and the state is untouched")
    hole_migration.add_argument(
        "--reindex", action="store_true",
        help="rewrite the generated pointer index from the store and nothing else")
    hole_migration.add_argument(
        "--doc", metavar="PATH",
        help="the hole document; by default the one beside this state directory "
             "(../docs/POST_V2_WISHLIST.md)")
    hole_migration.add_argument(
        "--holes-dir", default=holes.DEFAULT_HOLES_DIR, metavar="REL",
        help="where the full text of each entry goes, relative to the project root")

    # THE ONE DOOR THAT MOVES A STORED GOAL SIZE (DEC-0103). Same promise shape as the two
    # migrations above: without `--apply` nothing is written and the before/after list is printed.
    # The mapping is the caller's, because which size a project's own word meant is a fact about
    # that project and not a table this kernel could keep -- `migrate.goal_class_plan` argues it.
    class_migration = sub.add_parser(
        "migrate-goal-classes",
        help="report every stored root goal against the goal-size vocabulary and rewrite the "
             "strays a --map names (DEC-0103); without --apply nothing is written")
    class_migration.add_argument(
        "--map", action="append", dest="class_map", metavar="VALUE=WORD",
        help="which vocabulary word a stored value means (repeatable); a stray without one is "
             "reported and left, and the run exits non-zero")
    class_migration.add_argument(
        "--apply", action="store_true",
        help="write the mapped values through the edit path; without it the state is untouched")
    return parser


def _submitted_envelope(state, args) -> dict:
    """The result envelope `submit-result` hands the kernel -- from a staged FILE or from flags.

    THE TWO PATHS ARE THE TWO KINDS OF SPECIALIST (BUG-0048), not a convenience pair. A role
    whose installed definition grants a command-running tool types the flags itself
    (`dispatch.HAND_BACK_SELF`); a role whose definition grants none cannot type any command
    line, so it stages the envelope under its own task's key -- the one path
    `gate_write_scope` leaves a bound specialist inside the state directory -- and the lead
    names that file here (`dispatch.HAND_BACK_LEAD`). What the lead hands over is then the
    specialist's own bytes: retyping them out of a child's final message makes the LEAD the
    author of the record, and a summary the lead paraphrased is a summary nobody can attribute.

    THE FILE NAME IS A NAME, NOT A PATH, and `staging.contained_child` is what makes that true --
    the same chokepoint every freeze parameter goes through, and for the same measured reason (a
    `..` there was an `rmtree` on the repository). It is composed onto the staging directory of
    the task NAMED ON THE COMMAND LINE, so the lead cannot be talked into reading another task's
    proposal by the envelope it is about to submit.

    JSON AND NOT YAML, for the reason `_json_body` gives one screen down: YAML retypes `no` as
    false and `1.10` as a float, and a `summary` is a string whatever it spells.
    """
    if not args.envelope_file:
        missing = [name for name, value in (("--role", args.role),
                                            ("--status-proposal", args.status_proposal),
                                            ("--summary", args.summary)) if not value]
        if missing:
            raise UsageError(
                "submit-result needs %s, or a staged envelope to hand back instead. Remedy: add "
                "the flag(s), or -- for a specialist that cannot run a command itself -- let it "
                "write the envelope into the staging directory its OWN task owns and name that "
                "file here with `--from <NAME>`. No place is spelled out for you to fill in: the "
                "kernel composes it from the task id you already named (DEC-0024)."
                % ", ".join(missing))
        return {
            "task_id": args.task_id,
            "role": args.role,
            "status_proposal": args.status_proposal,
            "summary": args.summary,
            "outputs": list(args.outputs or []),
            "evidence": list(args.evidence or []),
            "scope_touched": list(args.scope_touched or []),
            "followups": list(args.followups or []),
        }
    conflicting = sorted(name for name, value in (
        ("--role", args.role), ("--status-proposal", args.status_proposal),
        ("--summary", args.summary), ("--output", args.outputs),
        ("--evidence", args.evidence), ("--scope-touched", args.scope_touched),
        ("--followup", args.followups)) if value)
    if conflicting:
        raise UsageError(
            "--from hands back a staged envelope VERBATIM, so %s would be a second author of the "
            "same record and the kernel refuses to pick one. Remedy: drop those flags, or drop "
            "--from and type the whole envelope." % ", ".join(conflicting))
    path = staging.contained_child(
        staging.staging_dir(state, args.task_id), args.envelope_file, "staged envelope")
    try:
        with open(path, "rb") as handle:
            raw = handle.read(report.ITEM_MAX_BYTES + 1)
    except OSError as exc:
        raise UsageError(
            "the staged envelope %r is not readable in the staging directory %s owns (%s). "
            "Remedy: the specialist writes it there before it stops -- that directory is the one "
            "place inside the state directory its own writes reach."
            % (args.envelope_file, args.task_id, exc)) from None
    if len(raw) > report.ITEM_MAX_BYTES:
        raise UsageError(
            "the staged envelope %r is over %d bytes. Remedy: an envelope REFERENCES its detail; "
            "the schema caps it far below this and would refuse it anyway."
            % (args.envelope_file, report.ITEM_MAX_BYTES))
    try:
        envelope = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise UsageError(
            "the staged envelope %r is not UTF-8 JSON (%s). Remedy: the specialist writes the "
            "eight envelope fields as ONE JSON object; `kernel/schemas/result_envelope.yaml` is "
            "the contract and `submit-result` validates against it."
            % (args.envelope_file, exc)) from None
    if not isinstance(envelope, dict):
        raise UsageError(
            "the staged envelope %r is a %s; an envelope is a JSON OBJECT of field -> value."
            % (args.envelope_file, type(envelope).__name__))
    named = envelope.get("task_id")
    if named != args.task_id:
        raise UsageError(
            "the staged envelope names task_id %r and this command names %s -- refused rather "
            "than reconciled. Remedy: submit the envelope under the task it was written for."
            % (named, args.task_id))
    return envelope


def _json_body(command: str = "capture") -> dict:
    """The JSON object a body-taking command was given on stdin, or a UsageError naming what
    went wrong.

    `command` is the subcommand the role typed, so the remedy names the line they were running --
    `capture` and the three `freeze-*` commands share this reader because they share the reason
    for it (see the `capture` parser entry: a body carries lists and mappings no flag surface
    expresses, and a `--from project_memory/...` cannot be typed past `gate_write_scope`).

    THE TTY CHECK IS NOT COSMETIC: `read()` on a terminal waits for EOF, so a role that forgets
    the heredoc would hang its own tool call until the harness times it out -- a command that
    hangs teaches "do not use this command". Refused with the remedy instead.
    """
    if sys.stdin is None or sys.stdin.isatty():
        raise UsageError(
            "%s reads its fields as a JSON object on STDIN and nothing is piped in -- "
            "it does not prompt for them. Remedy: `%s %s <<'EOF'` … `EOF`."
            % (command, INVOCATION, command))
    # THE BODY IS A UTF-8 BYTE STREAM, DECODED HERE AND NOT BY THE CONSOLE (BUG-0018/TSK-0028).
    # `sys.stdin.read()` decodes with `sys.stdin.encoding`, which on Windows is the console
    # codepage (cp1252), so a heredoc `ü` (c3bc) arrived as the two cp1252 chars `Ã¼` and
    # `yaml.safe_dump` re-encoded them -- the item stored the double-encoded c383c2bc in a field
    # L2 makes immutable, so a user could only fix it by replacing the whole item. The bytes are
    # the same whatever the codepage; the decode is the kernel's, exactly like every file it opens
    # (state/report/schemas/layout all pass encoding="utf-8"). `buffer` is absent only when a
    # caller replaced stdin with an in-memory text stream (the in-process CLI tests), which already
    # holds decoded text -- there is nothing to decode.
    #
    # `utf-8-sig` AND NOT `utf-8` (BUG-0021): a producer that prepends a byte-order mark -- a
    # PowerShell here-string over a native pipe is the measured one -- sent `EF BB BF` ahead of the
    # JSON, and a strict `utf-8` decode kept those bytes as U+FEFF at the front, so `json.loads`
    # refused with "Unexpected UTF-8 BOM" (exit 2) while its own remedy already named `utf-8-sig`.
    # `utf-8-sig` STRIPS a single leading BOM and otherwise decodes exactly like `utf-8` -- it does
    # not undo BUG-0018: the byte stream is still the kernel's to decode, the codepage still has no
    # say, and a BOM in the MIDDLE of the body (not a real producer, but a well-formed U+FEFF) is
    # left untouched. So the stored item carries no BOM, and its hash is the hash of the JSON.
    stdin_buffer = getattr(sys.stdin, "buffer", None)
    if stdin_buffer is None:
        raw = sys.stdin.read()
    else:
        try:
            raw = stdin_buffer.read().decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise UsageError(
                "the %s body on stdin is not valid UTF-8 (%s). Remedy: send the body as UTF-8 -- "
                "the kernel stores and hashes it as UTF-8 and does not guess a console codepage."
                % (command, exc)) from None
    if not raw.strip():
        raise UsageError(
            "%s reads its fields as a JSON object on STDIN and got nothing. Remedy: "
            "pipe or heredoc the body, e.g. `%s %s <<'EOF'` … `EOF`; the fields a capture type "
            "needs are `kernel/backlog_types.REQUIRED_FIELDS` and a freeze body's keys are its "
            "operation's own parameters, and the kernel names any that are missing."
            % (command, INVOCATION, command))
    # THE BUDGET IS CHECKED ON THE BYTES, BEFORE THE PARSE, and both halves are deliberate.
    # Spec II.5 caps an active item at `report.ITEM_MAX_BYTES`, `guard_memory_budget` enforces it
    # on every TOOL write into the same tree, and `capture` went around both -- measured: a 2 MB
    # body was accepted, the item written, and only `validate` complained afterwards, about a file
    # nothing can now edit. The limit is read from the validator's own constant so there is one
    # number. Before the parse, because a body too large to keep is a body not worth parsing, and
    # because `json.loads` on a deeply nested one raises RecursionError rather than anything a
    # role could act on -- caught below for the same reason.
    if len(raw.encode("utf-8")) > report.ITEM_MAX_BYTES:
        raise UsageError(
            "the %s body is %d bytes; an active item is capped at %d (spec II.5, the same "
            "limit `python scripts/harness.py validate` reports and `guard_memory_budget` enforces "
            "on tool writes). Remedy: an item REFERENCES its detail -- send a body that fits and "
            "keep the bulk in the artefact it belongs to, named from the item. No place for it is "
            "offered here: a place named in a message is one the reader completes, and what they "
            "put there can already be taken (DEC-0024)."
            % (command, len(raw.encode("utf-8")), report.ITEM_MAX_BYTES))
    try:
        body = json.loads(raw)
    except ValueError as exc:
        raise UsageError(
            "the %s body on stdin is not JSON (%s). Remedy: send a JSON object -- JSON and "
            "not YAML because these fields are hashed into approvals, and YAML would retype `no` "
            "as false and `1.10` as a float on the way in." % (command, exc)) from None
    except RecursionError:
        raise UsageError(
            "the %s body on stdin nests too deeply for the parser. Remedy: an item is a flat "
            "record that REFERENCES its detail; nothing in a field contract needs that depth."
            % command) from None
    if not isinstance(body, dict):
        raise UsageError(
            "the %s body is a %s; an item is a JSON OBJECT of field -> value. Remedy: wrap "
            "it in braces." % (command, type(body).__name__))
    return body


def _pin_utf8() -> None:
    """Write UTF-8 whatever the console codepage is -- the approval question depends on it.

    WHICH POSITION THIS ACTUALLY SAVES, measured rather than assumed -- and the first version of
    this paragraph named the wrong one. The INSTALLED entry point was never affected: the shim
    imports `_kernel`, which imports `_compat`, which pins both streams at import time, so a
    scaffolded project prints UTF-8 with or without this function. What was cp1252 is the
    PRE-INSTALL INSTALLER POSITION (`python -B -m kernel.cli …`), which loads no hook helper at
    all -- and that is the position the entry gate uses. So this belongs in the kernel rather than
    in the shim, which is where it is.

    WHY IT MATTERS AT ALL: `request-approval` prints a question containing `für` and `…`, and
    `gate_approval` compares the asked question to the kernel's one CHARACTER FOR CHARACTER. A
    question that loses its encoding on the way out is a protocol that cannot be completed. (The
    mojibake that first surfaced this was a READER defect -- UTF-8 bytes decoded as cp1252 in a
    test subprocess -- and is fixed on that side too; the producer half is here because a role's
    console codepage is not something the harness gets to choose.)

    Failure is ignored on purpose: a stream that cannot be reconfigured (a test runner capturing
    it, a closed handle) is not a reason to refuse a command.
    `test_the_installer_position_prints_utf8_whatever_the_console_codepage_is` measures the
    position this saves, with `PYTHONIOENCODING=cp1252`, rather than counting calls to
    `reconfigure` -- which is all its predecessor did.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass


# The three routes to the pin and the rollback, in one name so the dispatch cannot grow a fourth
# spelling the parser does not carry. Their subparsers above argue why they print rather than act.
KIT_PIN_ROUTES = ("pin-kit", "unpin-kit", "rollback-kit")


def _kit_pin_route(state: ProjectState, command: str) -> int:
    """Answer one of `KIT_PIN_ROUTES` out of this project's own bundle -- and write nothing.

    ONE BODY FOR THREE QUESTIONS because all three stand on the same two readings: which release is
    installed here (`kitupdate.relation`) and whether a pin already stands (`kitupdate.pin_in_force`).
    Three bodies would have been three readings of one file, i.e. three places for them to disagree.

    THE DEED IS NAMED AS A FILE, never as a shell line, and that is the one place this differs from
    `kitupdate.rollback_command`: creating or deleting a file is something the user can do in a file
    manager, while a command line would have to pick a shell for a reader whose shell nobody here
    knows. The rollback keeps its command because it starts the INSTALLER, and which twin that is
    `presets.installer_command` already decides.
    """
    root = presets.repo_root(state)
    kit = presets.installation(root)["kit"]
    pin = kitupdate.pin_in_force(root)
    path = os.path.join(root, kitupdate.PIN_FILE)
    if command == "rollback-kit":
        print(kitupdate.restorable(root, kit))
        if pin is not None:
            # SAID HERE AND NOT LEFT TO THE REFUSAL, because the refusal comes after the user has
            # already started the installer: `kitupdate.assert_no_pin_blocks_a_rollback` stands in
            # the installer's own pre-flight, and this command exists to be read BEFORE that.
            print("...but this project is PINNED, and a pin stops a rollback exactly as it stops "
                  "an update. Lift it first: %s" % path)
        return 0
    if command == "unpin-kit":
        if pin is None:
            print("nothing pins this project: there is no %s. `pin-kit` prints how to make one."
                  % path)
            return 0
        print("this project is PINNED by %s, which says:\n%s" % (path, pin["text"]))
        print("To lift it, the USER deletes that file. This command does not, and no command does: "
              "the pin is the only thing standing between a session and a replaced enforcement "
              "layer, so lifting it is the user's act and not a role's.")
        return 0
    if pin is not None:
        print("this project is ALREADY pinned by %s, which says:\n%s" % (path, pin["text"]))
        print("`unpin-kit` prints how that ends.")
        return 0
    installed = kitupdate.relation(root, kit)["from"]
    version = installed.get("version")
    if not version:
        print("this project's own release stamp (%s) is not readable, so there is no release to "
              "name in a pin -- report that gap rather than pinning a project to nothing."
              % kitupdate.INSTALLED_VERSION_FILE.replace(os.sep, "/"))
        return 1
    print("To hold this project at the release it runs, the USER creates %s with these two lines:"
          % path)
    print("kit: %s" % kit)
    print("version: %s" % version)
    # WHAT THE PIN WILL THEN REFUSE, said here because a user who cannot picture the effect cannot
    # judge the decision -- and all three doors are measured, not assumed
    # (`tools/test_kitupdate.py::test_the_installer_itself_refuses_a_pinned_project_and_writes_nothing`,
    # `::test_a_pinned_project_refuses_the_update_and_says_how_the_pin_is_lifted`,
    # `::test_a_pin_stops_a_rollback_in_both_twins`).
    print("From then on `%s`, the installer run by hand, and a rollback all refuse any other "
          "bundle here; re-installing this same one stays allowed. This command wrote nothing -- "
          "the file is the user's statement, which is why a session cannot make it."
          % kitupdate.COMMAND)
    return 0


def main(argv=None) -> int:
    _pin_utf8()
    args = build_parser().parse_args(argv)
    state = ProjectState(args.root)
    try:
        if args.command == "doctor":
            data = report.doctor(state)
            # Installation defects go to stderr BEFORE the JSON and set the exit code. A comment
            # in report.py called this "the one place a reader cannot page past", and that was
            # only true of the dict: doctor printed one JSON blob and always exited 0, so the
            # loudest thing in the report was a key somewhere in the middle of it. State findings
            # keep their own channel (`validate` exits 1 on those); this is about the KIT.
            for finding in data.get("installation_errors") or []:
                sys.stderr.write("[INSTALLATION] %s: %s -- Remedy: %s\n" % (
                    finding["item"], finding["message"], finding["remedy"]))
            print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
            return 1 if data.get("installation_errors") else 0
        if args.command == "validate":
            findings = report.validate_state(state)
            for finding in findings:
                print("[%s] %s: %s -- Remedy: %s" % (
                    finding["severity"].upper(), finding["item"],
                    finding["message"], finding["remedy"],
                ))
            errors = [f for f in findings if f["severity"] == "error"]
            print("%d error(s), %d warning(s)" % (len(errors), len(findings) - len(errors)))
            # WHAT THE V1 RECORD SCAN DID NOT LOOK AT, printed with the findings and not among
            # them: it is coverage, so it carries no severity and no exit code (see
            # `report.record_scan_coverage`), and without it "no finding about that file" and "that
            # file was never read" are the same silence on this surface.
            coverage = report.record_scan_coverage(state)
            # DEPOSIT copies are COUNTED, not listed (BUG-0028): one appears per applied remedy, so a
            # line each grew this section every time the project followed the report.
            deposits = coverage.get("deposits") or []
            print("V1 record scan: searched %d document(s), did not search %d, %d deposit copy(ies)"
                  % (len(coverage["searched"]), len(coverage["not_searched"]), len(deposits)))
            for entry in coverage["not_searched"]:
                print("  NOT SEARCHED %s: %s" % (entry["path"], entry["why"]))
            # WHAT A DELIVERY HAS ALREADY CLOSED WHILE THE STATUS FIELD STILL READS OPEN
            # (DEC-0051), printed with the findings and not among them for the reason
            # `report.delivery_closure_rollup` gives: a row a project cannot clear -- and a BUG
            # whose route needs a mint the project has no way to run is exactly that -- would be a
            # finding nobody can act on. Without this line the difference between "open" and
            # "delivered, and nobody moved it" is a difference no surface shows.
            rollup = report.delivery_closure_rollup(state)
            # THE HEADLINE SAYS "ALL", not "a passing", and that is not editorial: the derivation
            # closes an item only when EVERY current verdict naming it passes, so a line reading
            # "a passing delivery Evidence names it" taught the reader the one rule
            # `closed_by_delivery` does not have -- the "any pass wins" reading its own regression
            # test exists to red. The docstring was precise and this line was not, which is the
            # half a reader actually meets.
            print("Delivered but still open: %d item(s) whose delivery verdicts ALL pass while "
                  "their status still reads otherwise" % len(rollup))
            for row in rollup:
                print("  %s %s (%s): %s" % (row["item"], row["status"],
                                            ", ".join(row["evidence"]),
                                            row["route"] or "no route on this type's chain"))
            # THE STOCK THAT LIES UPWARD (FR-0058, PR-0008 AC-3): the other question to the same
            # store -- the item's own CONFIRMING Evidence passes, a regression run included, and
            # the status has not followed. Beside the findings for the reason the rollup above is.
            stock = report.stock_rollup(state)
            print("Stock lies upward: %d item(s) whose confirming Evidence passes while their "
                  "status still reads open" % len(stock))
            for row in stock:
                # THREE STATES OF THE RUN AND NOT TWO (verifier round 1, R1): a record with no
                # `run_command` at all left `unresolved` empty, which printed exactly like "every
                # test it names is there" -- so a reader could not tell "nothing repeatable was
                # recorded" from "all present". The third one is said in words.
                if not row.get("run_command"):
                    about = "; its record names no run, so nothing here can be repeated"
                elif row["unresolved"]:
                    about = ("; its run names tests the tree no longer defines: %s"
                             % ", ".join(row["unresolved"]))
                else:
                    about = ""
                print("  %s %s (%s %s%s): %s" % (
                    row["item"], row["status"], row["kind"], ", ".join(row["evidence"]), about,
                    row["route"] or "no route on this type's chain"))
            return 1 if errors else 0
        if args.command == "sweep-pointers":
            try:
                findings = report.pointer_sweep(state)
            except report.PointerSweepUnavailable as unavailable:
                # A SWEEP WITH NO SUBJECT IS NOT A CLEAN SWEEP. Printing "0 finding(s)" here would
                # be the reassuring answer to a question nobody asked, which is the exact failure
                # the duty this command serves is about.
                print("pointer sweep: %s" % unavailable)
                return 1
            for finding in findings:
                print("[%s] %s: %s -- Remedy: %s" % (
                    finding["severity"].upper(), finding["item"],
                    finding["message"], finding["remedy"],
                ))
            print("%d dead pointer(s) in this project's own files. What this reads and what it "
                  "does NOT is `kernel.report.pointer_sweep`; a claim that names no test at all is "
                  "read by nobody and stays with the role that writes and the role that reviews."
                  % len(findings))
            return 1 if findings else 0
        if args.command == "generate-index":
            # EVERY path this call wrote, for the reason the subparser's help gives: the index
            # is what the machines read, the board is what a person opens, the two diagrams are
            # what a person hands around, and the same call writes them together. The list is
            # DERIVED from the renderers rather than typed here, so an artefact added to
            # `state._write_board` cannot arrive unannounced -- which is exactly how the two
            # diagrams would have arrived without this line
            # (`tools/test_board.py::test_the_documented_command_names_every_artefact_it_writes`).
            print(state.generate_index())
            print(state.generated_path(board.FILENAME))
            for name in plan_diagram.FILENAMES:
                print(state.generated_path(name))
            return 0
        if args.command == "verify-invariants":
            wanted = list(args.item_ids) or [
                stem for stem, _path in state.iter_active_items("INV")]
            if not wanted:
                print("no active invariants")
                return 0
            refuted = undecided = 0
            for item_id in wanted:
                item, resolved, reason = state.record_invariant_verification(item_id)
                # THREE OUTCOMES, THREE LINES, and the third one is why this is not a boolean: an
                # invariant this kernel cannot READ is neither met nor unmet, and printing it as
                # "unverified: ..." beside a non-zero exit told a project whose tests are not
                # Python that its state is broken, for ever, with nothing to fix.
                print("%s %s: %s" % (item["id"],
                                     item["status"] if resolved is not None else "undecided",
                                     reason))
                refuted += resolved is False
                undecided += resolved is None
            if undecided:
                print("%d invariant(s) could not be decided here -- that is the reader's limit, "
                      "not a finding about this project (H110): the check names a test file this "
                      "kernel does not parse, and whether that test exists is a question for the "
                      "project's own runner." % undecided)
            # 1 = "there is something to fix", exactly as `validate` uses it -- and it is the SAME
            # condition the state validator turns into an ERROR and the merge blocker, so a role
            # running this and a gate reading the store cannot disagree. Measured before this
            # counted the way it does: an undecidable check made this exit 1 while `validate`
            # exited 0 with a warning, on the same store in the same second.
            return 1 if refuted else 0
        if args.command == "generate-session-brief":
            print(report.generate_session_brief(state, args.kit, args.kit_version, args.enforcement))
            return 0
        if args.command == "evidence":
            # ASKED BEFORE THE RECORD IS WRITTEN, so an ORDINARY refusal -- a word outside the
            # vocabulary, a passing result, a role classifying its own run -- leaves no Evidence
            # behind that claims a classification: the record is immutable, so a wrong one can only
            # be superseded, never repaired. The role is the STATE's answer and not the caller's
            # claim -- `dispatch.writing_role` reads the bound lease.
            #
            # IT IS NOT THE ONLY JUDGEMENT, and that limit is a window rather than a bug (verifier
            # round 2, R3): `record_fail_class` asks each order's status AGAIN under the lock, and
            # that second judgement falls AFTER the capture below. An order that moves in between
            # therefore leaves exactly what the paragraph above rules out for the first judgement --
            # an immutable record carrying a classification that no order carries -- and the command
            # ends rc 1 with the sentence, not with a traceback. The ORDER OF THE TWO WRITES is
            # deliberate and not an oversight: swapping them would trade an unread record for an
            # unrecorded discount, and only the second changes what the next lease runs on.
            # `tools/test_kernel.py::test_a_stamp_refused_under_the_lock_leaves_the_record_behind`
            fail_class = getattr(args, FAIL_CLASS_FIELD)
            role = dispatch.writing_role(state) if fail_class is not None else None
            refusal = dispatch.fail_class_refusal(state, role, args.related, args.result,
                                                  fail_class)
            if refusal:
                sys.stderr.write("fail classification refused: %s\n" % refusal)
                return 2
            item = state.capture("EVD", {
                "kind": args.kind,
                "related": list(args.related),
                "result": args.result,
                "summary": args.summary,
                "artifact_refs": list(args.artifact_refs),
                # dropped when unanswered rather than written as null: the pair is refused
                # half-declared in `state.capture_preflight`, and a `None` is an answer there
                **{name: value for name, value in
                   (("run_command", args.run_command), ("run_scope", args.run_scope),
                    (BLOCKED_REASON_FIELD, getattr(args, BLOCKED_REASON_FIELD)),
                    (FAIL_CLASS_FIELD, fail_class))
                   if value is not None},
            })
            print("%s %s: %s" % (item["id"], item["kind"], item["result"]))
            # ...and the ORDER carries it, because the next lease is what reads it (DEC-0107).
            # Printed by id, so the role sees which orders its verdict moved.
            if fail_class is not None:
                stamped = dispatch.record_fail_class(state, args.related, fail_class, role)
                print("%s %s (by %s) on: %s"
                      % (FAIL_CLASS_FIELD, fail_class, role, ", ".join(stamped) or "-"))
            return 0
        if args.command in FREEZE_COMMANDS:
            operation = FREEZE_COMMANDS[args.command]
            result = operation(state, **_freeze_body(args.command, operation))
            # STATE-RELATIVE, like every other path this surface prints or accepts: the absolute
            # one names `project_memory`, and a role who pastes it into the next command line meets
            # `gate_write_scope` instead of an answer.
            print(os.path.relpath(result["frozen"], state.root).replace(os.sep, "/"))
            # `freeze_design` is the ONE producer of a `design_refs` entry, and that list is the
            # input `dispatch` refuses a UI spawn against (II.6). Printed from the returned root
            # rather than re-read, so what is shown is what the same lock hold wrote.
            root_item = result.get("root")
            if root_item is not None:
                print("%s design_refs: %s" % (
                    root_item["id"],
                    ", ".join(str(ref) for ref in
                              field_elements(root_item.get("design_refs"))) or "-"))
            # WHAT THE FREEZE DID TO THE PROPOSAL AREA, said out loud (BUG-0074). Until this line
            # the answer was `rmtree` on the task's whole staging directory and nothing printed it:
            # three unfrozen wireframes were deleted alongside the one being frozen in the user's
            # real project, and the loss was noticed days later. The freeze now takes only the file
            # it froze, and what is LEFT is named -- a role reading this can see its own unfrozen
            # work is still there instead of assuming it either way.
            # ...and, for the freeze whose subject RECORDS the reference, which item now carries
            # it. `freeze_report` files a rendered report and appends its path to the subject's
            # `evidence_refs` when that item's contract declares the field -- and when it does not
            # (a report written for a question rather than an experiment), `recorded_on` is None
            # and this says so, because a command that stayed silent there would let a role assume
            # a binding the state does not hold (BUG-0085).
            subject = result.get("subject")
            if subject is not None:
                field = result.get("recorded_on")
                print("%s %s: %s" % (
                    subject["id"], field or staging.REPORT_REF_FIELD,
                    ", ".join(str(ref) for ref in field_elements(subject.get(field))) or
                    ("-- this item's contract has no such field, so the report is filed and "
                     "referenced by nothing but its own name")))
            staged = result.get("staging") or {}
            print("staging: %s %s; still staged: %s" % (
                staged.get("artifact") or "-",
                "consumed (the frozen copy is canonical now)" if staged.get("consumed")
                else "COULD NOT BE REMOVED and is still in staging",
                ", ".join(staged.get("remaining") or []) or "nothing"))
            return 0
        if args.command == "capture":
            body = _json_body("capture %s" % args.item_type)
            # TSK goes through its own constructor even here: `root_revision` is denormalized from
            # the CURRENT root (spec II.2) and `dispatch.create_task` is the one thing that reads
            # it. Letting a hand-written body carry that field would be a second producer of one
            # value, and the value decides whether a lease is allowed at all.
            near = report.similar_items(state, args.item_type, body)
            outline = report.standing_areas(state)
            # ASKED BEFORE THE PRODUCER IS CHOSEN, because `capture TSK` does not go through
            # `state.capture` at all -- the flag would be silently ignored there. The rule itself
            # is the kernel's (`assert_capturable_as_hole`), so this surface carries none of its
            # own; a type check written here was an enumeration of one beside the definition, and
            # `capture DEC --hole` walked past it with rc 0.
            if args.hole:
                state.assert_capturable_as_hole(args.item_type)
            # THE FIELDS A TYPE OWES AT THE DOOR A ROLE TYPES (DEC-0083), and HERE rather than in
            # `state.capture_preflight`: down there the duty would also bind the V1 importer and
            # the run receipt, neither of which can answer it -- and exempting the importer needs a
            # READER of `IMPORT_MARK`, which `DEC-0021` refused ("a second bolt beside
            # `approval_ref` is two answers to one question"). Measured: with the clause in the
            # library, 49 migration tests went red and the mark grew a reader. So the duty binds
            # the command surface, and its limit is said out loud: a caller reaching
            # `state.capture` directly is not asked, which is why the STORED half is answered by
            # the pointer direction (`report._check_decision_carriers`) and not by this line.
            # ...and "present" has to mean "says something", the same way it does for every other
            # field this kernel calls non-empty: `work: []`, `""`, `[""]` and `"   "` all passed
            # this door and then silenced the carrier warning without ever saying `none` (verifier
            # round 2, N-B2). `work_is_stated` is the one predicate the validator asks too.
            unsaid = [one for one in CAPTURE_ONLY_REQUIRED.get(args.item_type, ())
                      if not work_is_stated(body.get(one))]
            if unsaid:
                sys.stderr.write(
                    "capture %s: %s says nothing -- it is missing, or it is empty, and the two are "
                    "the same claim. A decision says which items carry the work it commits "
                    "somebody to -- or `%s: %s` when it commits nobody, which is a naming rule or "
                    "a verdict. Remedy: name the ids (they are resolved like every other binding), "
                    "or write `%s` -- that exact word, lower case, and it is the ONLY silence "
                    "(DEC-0083, FR-0012).\n"
                    % (args.item_type, ", ".join(unsaid), DEC_WORK_FIELD, DEC_WORK_NONE,
                       DEC_WORK_NONE))
                return 1
            item = (dispatch.create_task(state, body) if args.item_type == "TSK"
                    else state.capture(args.item_type, body, hole=args.hole))
            # FR-0017: an area nobody uses yet is a NEW outline level, and the FR's rule is that
            # one is invented only when nothing existing fits -- so the outline that already
            # exists is put in front of the writer at exactly that moment, and nowhere else.
            # AFTER the capture, because a body the kernel REFUSES (an area three levels deep, a
            # missing field) never became a level at all, and advising a writer about a level
            # that was not created is the noise this hint is bounded to avoid. The outline itself
            # is read BEFORE the write, so the new item cannot recommend itself.
            invented = AREA_SEPARATOR.join(area_segments(body.get(AREA_FIELD)))
            if invented and invented not in outline:
                sys.stderr.write(
                    "[outline] %s is a new level; the backlog already carries: %s\n"
                    % (invented, ", ".join(outline) or "no outline at all"))
            print("%s %s%s" % (item["id"], item.get("status") or "-",
                                " " + str(item[HOLE_NUMBER_FIELD]) if args.hole else ""))
            if args.hole:
                # The generated index of the hole document is a VIEW of the store, so a new hole
                # only appears in it once it is re-rendered. Said on stderr, at the one moment a
                # caller can act on it, rather than left for a red test to report.
                sys.stderr.write(
                    "[hole] %s is %s. Regenerate the pointer index with `python "
                    "scripts/harness.py migrate-holes --reindex`, which writes the index and "
                    "nothing else.\n"
                    % (item["id"], item[HOLE_NUMBER_FIELD]))
            # THE SOFT HALF OF FR-0018, and it is soft in three ways at once: it is computed
            # BEFORE the capture so the new item cannot match itself, it goes to stderr AFTER the
            # id has been printed to stdout, and it changes no exit code. A duplicate is a
            # judgement about meaning, which the role that just wrote the item is better at than
            # any word count -- what the kernel owes is the moment and the neighbours.
            for row in near:
                sys.stderr.write("[similar] %s: %s\n" % (row["id"], row["title"] or "-"))
            if near:
                sys.stderr.write(
                    "[similar] %s was captured all the same -- nothing here was refused. If one "
                    "of the above is the same requirement, retire this one and extend that.\n"
                    % item["id"])
            return 0
        if args.command == "create-task":
            if bool(args.allowed_scope) == bool(args.read_only):
                raise UsageError(
                    "an order names what it may write (--allowed-scope, repeatable) or says it "
                    "writes nothing (--read-only) -- %s. Remedy: pass exactly one of the two."
                    % ("both were given" if args.read_only else "neither was given"))
            task = dispatch.create_task(state, {
                "product_requirement": args.product_requirement,
                "derives_from": args.derives_from,
                "type": args.task_type,
                "assigned_role": args.assigned_role,
                "acceptance_refs": list(args.acceptance_refs),
                "allowed_scope": list(args.allowed_scope or []),
                "forbidden_scope": list(args.forbidden_scope or []),
                "required_inputs": list(args.required_inputs or []),
                "expected_outputs": list(args.expected_outputs or []),
                "dependencies": list(args.dependencies or []),
                **({"design_ref": args.design_ref} if args.design_ref else {}),
                **({scopes.SEAM_FIELD: list(getattr(args, scopes.SEAM_FIELD))}
                   if getattr(args, scopes.SEAM_FIELD) else {}),
                **{key: getattr(args, key) for key in (dispatch.RUNG_KEY, dispatch.EFFORT_KEY)
                   if getattr(args, key)},
            })
            print("%s %s (%s)" % (task["id"], task["status"], task["assigned_role"]))
            return 0
        if args.command == CHECK_SCOPES_COMMAND:
            # THE EXIT CODE IS THE ANSWER, which is why the lines are printed and then returned
            # rather than raised: an overlap is a finding about the CUT, not a usage error, and a
            # caller that scripts this reads rc 2 the same way it reads `validate`'s rc 1.
            code, lines = scopes.check(state, only=args.only, declared=list(args.seam))
            for line in lines:
                print(line)
            return code
        if args.command == "submit-result":
            task = dispatch.submit_result(state, _submitted_envelope(state, args))
            print("%s -> %s" % (task["id"], task["status"]))
            return 0
        if args.command == "request-approval":
            builder = approvals.LINE_MANIFEST_BUILDERS.get(args.kind)
            if args.expires_in_days is not None and args.kind not in approvals.EXPIRING_KINDS:
                raise UsageError(
                    "a %s approval carries no clock (it is invalidated by its content, not by "
                    "time), so --expires-in-days is refused for it. Remedy: drop the flag."
                    % args.kind)
            if args.unverified_answer is not None and args.kind != "acceptance":
                raise UsageError(
                    "--unverified-answer records the user's answer to DEC-0113's question, which "
                    "is asked before an ACCEPTANCE and before nothing else; a %s approval has no "
                    "such question. Remedy: drop the flag." % args.kind)
            batched = kinds_reading_argument(BATCH_ARGUMENT)
            if getattr(args, BATCH_ARGUMENT, None) and args.kind not in batched:
                raise UsageError(
                    "a %s approval is not asked over a list of items, so --%s is refused for it "
                    "(%s takes one). Remedy: drop the flag."
                    % (args.kind, BATCH_ARGUMENT, "/".join(sorted(batched)) or "no kind here"))
            # THE POSITIONAL ID IS ANSWERED FIRST, and the order matters rather than being tidy:
            # `hole_exception` took a positional id until PR-0012 AC-4, so a role with the older
            # habit types one -- and asked in the other order it met "and none was named" while it
            # HAD named one, with a remedy that dropped the id it gave. Measured 2026-09-12.
            if args.kind in batched and args.item_id:
                raise UsageError(
                    "a %s approval is asked over a LIST, so the id goes on --%s rather than on its "
                    "own. Remedy: `%s request-approval %s --%s %s` (up to %d per question)."
                    % (args.kind, BATCH_ARGUMENT, INVOCATION, args.kind, BATCH_ARGUMENT,
                       args.item_id, approvals.BATCH_LIMIT))
            if args.kind in batched and not getattr(args, BATCH_ARGUMENT, None):
                # THE VERB IS NEUTRAL because the two batch kinds do opposite things: `verification`
                # closes what it lists, `hole_exception` ACCEPTS that it stays open and closes
                # nothing. A sentence saying "closes" is false for half the kinds it is printed for.
                raise UsageError(
                    "a %s approval is asked over the items it lists and none was named. Remedy: "
                    "`%s request-approval %s --%s <ITEM_ID> <ITEM_ID> ...` (at most %d per "
                    "question)."
                    % (args.kind, INVOCATION, args.kind, BATCH_ARGUMENT, approvals.BATCH_LIMIT))
            if builder is None:
                if not args.item_id:
                    raise UsageError(
                        "a %s approval is bound to an ITEM and none was named. Remedy: `%s "
                        "request-approval %s <ITEM_ID>`."
                        % (args.kind, INVOCATION, args.kind))
                pending = approvals.create_pending_request(
                    state, args.kind, args.item_id,
                    unverified_answer=args.unverified_answer)
            elif args.kind == approvals.ROUTINE_KIND:
                # THE ONE LINE KIND THAT HANGS FROM AN ITEM (`approvals.ROUTINE_KIND`): the flags
                # build what the run is bound to, the root is what the dispatcher reads the
                # approval off, and the term is the USER's to see and decide -- a standing
                # permission for a recurring run cannot borrow the one-hour clock of a push
                # token, so it is typed, in days, and rendered as a date in the question.
                # PR-0011 AC-8 (BUG-0266 / H184): before this branch the entry point could not
                # produce the kind the auditor's route is written for.
                if not args.item_id:
                    raise UsageError(
                        "a routine approval hangs from the ROOT whose recurring run it permits, "
                        "and none was named. Remedy: `%s request-approval routine <ROOT_ID> "
                        "--role <role> --scope <read scope> --trigger <when> --cadence <how "
                        "often> --expires-in-days <n>`." % INVOCATION)
                if args.expires_in_days is None:
                    raise UsageError(
                        "a routine approval is a standing permission and needs its term: pass "
                        "--expires-in-days <n>; the question shows the date the user signs.")
                pending = approvals.create_pending_request(
                    state, args.kind, args.item_id,
                    manifest=_line_manifest(state, args.kind, builder, args),
                    approval_expires=time.time() + float(args.expires_in_days) * 86400.0)
            else:
                if args.item_id:
                    # A BATCHED KIND NEVER REACHES HERE -- it is answered above, where the id can
                    # still be carried into the remedy.
                    raise UsageError(
                        "a %s approval has no item -- its subject is %s. Remedy: drop %r from the "
                        "command line." % (args.kind, ", ".join(manifest_parameters(builder)),
                                           args.item_id))
                # THE CLOCK ONLY FOR THE KINDS THAT CARRY ONE, asked of `EXPIRING_KINDS` rather
                # than assumed of every line kind: a plan approval is invalidated by its own
                # content (each goal's revision and scope hash), not by an hour passing, and
                # `create_pending_request` refuses an expiry on a kind that does not take one.
                expires = (time.time() + approvals.LINE_APPROVAL_VALIDITY
                           if args.kind in approvals.EXPIRING_KINDS else None)
                if args.expires_in_days is not None:
                    expires = time.time() + float(args.expires_in_days) * 86400.0
                pending = approvals.create_pending_request(
                    state, args.kind,
                    manifest=_line_manifest(state, args.kind, builder, args),
                    approval_expires=expires)
            # ONLY the question object on stdout, and as JSON, because it has to be relayed
            # VERBATIM: `gate_approval` compares the asked question against `build_question`
            # field by field, so anything printed beside it is something a role might paste in.
            # The request id travels inside the text as `[APR-REQ:<id>]`; that marker is what the
            # gate resolves back to this request.
            print(json.dumps(approvals.build_question(pending), indent=2, ensure_ascii=False))
            # ...AND, ON STDERR, WHETHER THE ANSWER HAS A READER. Same rule as the `dispatch`
            # branch below: stdout carries only what must be relayed verbatim. Without this the
            # only surface that says the answer goes nowhere is the transition refusal, which
            # arrives AFTER the user has been asked and has clicked -- the shape BUG-0039 records,
            # where a yes evaporates and no surface tells her. Said here it is said BEFORE the
            # question is put to her. One reader with `approvals._unwired_mint_note`
            # (`report.approval_mint_is_wired`), so the two surfaces cannot disagree about
            # whether this project mints.
            if not report.approval_mint_is_wired(os.path.dirname(state.root)):
                sys.stderr.write(
                    "warning: this project's own hook registration runs no %s on %s(%s), so "
                    "nothing here is set up to read the answer. The question above can be asked "
                    "and it will approve nothing -- report that gap instead of relaying it.\n"
                    % (approvals.APPROVAL_HOOK, approvals.APPROVAL_MINT_EVENT,
                       approvals.APPROVAL_QUESTION_TOOL))
            return 0
        if args.command == "dispatch":
            # ONLY the header on stdout: it has to be copied into the spawn prompt character for
            # character (the gate compares the nonce), so anything else printed beside it is
            # something a role might copy along with it.
            lease = dispatch.create_lease(state, args.task_id, worktree=args.worktree)
            print(dispatch.dispatch_header(lease))
            # ...AND THE CHECKPOINT VERDICT ON STDERR, for that same rule rather than despite it:
            # the reasons are for the human composing the dispatch, and putting them on stdout
            # would make them one paste away from travelling inside the prompt. `create_lease`
            # has already decided whether the header carries the pointer; this only says why.
            sys.stderr.write(dispatch.checkpoint_verdict(state, args.task_id).summary + "\n")
            # ...AND THE LADDER ANSWER, on the same channel for the same reason (DEC-0077 (5)):
            # the header above already carries rung and effort; this line carries the WHY.
            sys.stderr.write(dispatch.ladder_line(lease) + "\n")
            return 0
        if args.command == "ladder":
            task = state.read_item(args.task_id)
            root = state.read_item(task["product_requirement"])
            answer = dispatch.ladder_for_order(
                state, task, root, int(task.get(dispatch.FAILED_RUNS) or 0), args.provider)
            # The count on the task is the one the LAST lease wrote; the next lease counts a run
            # that started since (`dispatch.count_failed_run_locked`), so a task READY again after
            # a started run shows here what the next dispatch would climb with.
            pending = dict(task)
            if dispatch.count_failed_run_locked(pending) != int(task.get(dispatch.FAILED_RUNS) or 0):
                answer["next_lease_counts"] = pending[dispatch.FAILED_RUNS]
                answer["next_lease"] = dispatch.ladder_for_order(
                    state, task, root, pending[dispatch.FAILED_RUNS], args.provider)
            # WITHOUT `--provider` the answer for every installed provider rides along -- so the
            # command the constitutions name shows the Codex top without an option nobody is told
            # to type. `next_lease` carries its own map, the one the NEXT dispatch header carries
            # (TSK-0151 verifier round 2, R2-2: the map at the old count showed the rung before the
            # climb). `tools/test_ladder.py::test_the_lease_and_the_header_carry_the_answer_for_every_installed_provider_bug_0306`
            if args.provider is None:
                for shown in (answer, answer.get("next_lease")):
                    if isinstance(shown, dict) and dispatch.RUNG_KEY in shown:
                        shown[dispatch.PROVIDERS_KEY] = dispatch.ladders_by_provider(
                            state, task, root, shown)
            print(json.dumps(answer, indent=2, sort_keys=True))
            return 0
        if args.command == "checkpoint":
            stored = checkpoints.record(state, args.task_id, _json_body("checkpoint"))
            print("%s checkpoint recorded: %s (%d output(s), %d artefact(s))" % (
                stored["task_id"], checkpoints.state_relative(
                    state, checkpoints.checkpoint_path(state, args.task_id)),
                len(stored["outputs"]),
                sum(len(entry["artifacts"]) for entry in stored["outputs"])))
            return 0
        if args.command == "checkpoint-status":
            verdict = checkpoints.verify(state, args.task_id)
            print(verdict.summary)
            # 1 = "there is nothing here to adopt", exactly as `validate` uses it for findings: a
            # caller scripting the retry has to tell "adopt" from "start over" without reading
            # prose, and DEC-0044 makes absent, stale and broken ONE answer.
            return 0 if verdict.adoptable else 1
        if args.command == "transition":
            item = state.transition(args.item_id, args.to_status, approved_retry=args.approved_retry)
            print("%s -> %s" % (item["id"], item["status"]))
            return 0
        if args.command == "update":
            # The body carries only the fields that CHANGE. Every guard lives in `update_item`
            # (kernel-set fields refused, immutable types refused, frozen work-order fields refused,
            # closed vocabularies and origins asserted, approval invalidated atomically when a
            # hashed field moves) -- the CLI adds no second copy of any of those rules, so the one
            # that runs is the one the state layer states.
            body = _json_body("update %s" % args.item_id)
            item = state.update_item(args.item_id, body)
            # `revision` and `approval_ref` are printed because they are exactly what an
            # invalidating edit moves: a caller sees the approval gone (`approval_ref: -`) and the
            # revision bumped without re-reading the file.
            print("%s %s rev %s approval_ref: %s" % (
                item["id"], item.get("status") or "-", item.get("revision", 1),
                item.get("approval_ref") or "-"))
            return 0
        if args.command == "set-preset":
            result = presets.apply(state, args.preset)
            print("%s preset: %s" % (result["kit"], result["preset"]))
            # READ BACK OFF THE INSTALLATION, not off the plan: what this prints is the ownership
            # manifest the installer just wrote, so a role that did not arrive does not appear here
            # either. The lead is in that list because the installation manages it too.
            print("roles installed (lead first): %s" % (", ".join(result["installed"]) or "-"))
            print("removed: %s" % (", ".join(result["removed"]) or "-"))
            # THE RESTART IS PART OF THE ANSWER, not an afterthought: the provider reads its agent
            # set at session start, so a role installed here is not spawnable in this session and
            # the installer's handover marker stops this one deriving further. A command that
            # reported success and left the lead to discover that is the shape BUG-0016 named.
            print("RESTART REQUIRED: the new role set loads at the next session start. Tell the "
                  "user in their own words and stop deriving here.")
            return 0
        if args.command == filing.COMMAND:
            builder = approvals.LINE_MANIFEST_BUILDERS[filing.KIND]
            result = filing.apply(state, _line_manifest(state, filing.KIND, builder, args))
            rule = result["rule"]
            print("%s rule added: %s -> %s" % (filing.PLAN, rule["id"], rule["path_template"]))
            # READ BACK OFF THE FILE, not off the plan of what to write: the count is what the
            # plan now PARSES to, so a rule that did not arrive does not appear here either.
            print("rules in the plan now: %d" % result["rules"])
            # The plan grew; nothing moved. Said here because a role that reads "rule added" as
            # "document filed" would report a filing that has not happened -- `gate_filing` judges
            # the move when the move is made, against the plan as it then stands.
            print("NOT done here: no document was filed. File it now; the plan covers it.")
            return 0
        if args.command == documents.COMMAND:
            builder = approvals.LINE_MANIFEST_BUILDERS[documents.KIND]
            result = documents.apply(state, _line_manifest(state, documents.KIND, builder, args))
            print("%s updated (%d bytes): %s" % (result["document"], result["bytes"],
                                                 ", ".join(result["changes"])))
            # THE PROPOSAL IS STILL THERE, and it is said rather than assumed: this command copies
            # bytes into a document, it does not consume the task's workspace -- the lesson
            # BUG-0074 cost three unfrozen wireframes one document over.
            print("the staged proposal is unchanged and still in %s" % args.proposal)
            return 0
        if args.command == documents.REVISION_COMMAND:
            builder = approvals.LINE_MANIFEST_BUILDERS[documents.REVISION_KIND]
            result = documents.apply_revision(
                state, _line_manifest(state, documents.REVISION_KIND, builder, args))
            print("%s revised (%d bytes): %s" % (result["document"], result["bytes"],
                                                 ", ".join(result["changes"])))
            print("the staged revision is unchanged and still in %s" % args.proposal)
            return 0
        if args.command == duties.COMMAND:
            done = duties.record_done(state, args.key, args.what, args.note)
            print("duty %s: %s (%s)"
                  % (done["duty_key"], "recorded" if done["recorded"] else "already recorded",
                     done["done_at"]))
            # WHICH DUTY IT WAS is printed back, because a key is a digest: a user who pasted the
            # wrong one has exactly one chance to see it, and it is this line.
            print("what: %s" % done["what"])
            print("note: %s" % done["note"])
            # THE REGISTER IS DERIVED AT THE NEXT SESSION START, so nothing about this session's
            # briefing changes -- said here rather than left to look like a bug.
            print("NOT changed here: this session's briefing was derived before this record. The "
                  "duty drops out of the register at the next session start.")
            return 0
        if args.command == gaplog.COMMAND:
            entry = gaplog.record(state, args.tried, args.refused, args.title, args.item)
            print("kit gap %s: %s" % (entry["id"],
                                      "recorded" if entry["recorded"] else "already recorded"))
            # THE USER STILL HEARS IT IN THIS TURN. The log is for the kit's maintainer, not a
            # substitute for telling the person whose work just stopped (§8 of every constitution).
            print("NOT done here: the user has not been told. Say it to them in this same turn.")
            return 0
        if args.command in KIT_PIN_ROUTES:
            return _kit_pin_route(state, args.command)
        if args.command == kitupdate.COMMAND:
            result = kitupdate.apply(state)
            print("%s kit: %s -> %s" % (result["kit"], result["from"], result["to"]))
            # READ BACK OFF THE INSTALLATION, never off the plan, and BOTH readers: the stamp says
            # what the project claims to run and the bundle says what it actually runs, which is
            # the pair an aborted run makes disagree (`kitupdate._bundle_reading`).
            print("installed: %s" % result["installed"])
            print("NOT re-read: %s" % kitupdate.UNREAD)
            if result["pending_templates"]:
                print("follow-up: %s" % result["pending_templates"])
            # THE RESTART IS THE COMMAND'S LAST ACT, not a courtesy line: the registration in
            # `settings.json`, the agent set and the session agent are what this session started
            # with, while the hook FILES are already the new kit's. What actually stops the session
            # is the marker, so the line says which one and what state it was found in.
            print("RESTART REQUIRED: %s. Tell the user in their own words and stop here -- "
                  "specialist spawns are refused here; with the harness's user-global "
                  "handover guard installed, further work-engine commands and product writes "
                  "as well." % result["marker"])
            return 0
        if args.command == "archive":
            print(state.archive(args.item_id))
            return 0
        if args.command == "sweep-leases":
            # BOTH ways a lease comes back, because the remedy line that sends a role here does
            # not know which of the two it is looking at. `sweep_expired_leases` is the TTL
            # backstop; `reconcile_unstarted_dispatches` is the one for a lease spent on a spawn
            # that never started -- the case a permission refusal produces, which no hook event
            # reports. Running only the first left that case waiting the full DEFAULT_LEASE_TTL
            # after a sweep that had just told the role there was nothing to release.
            to_ready, lease_only = dispatch.sweep_expired_leases(state)
            released = sorted(set(to_ready) | set(dispatch.reconcile_unstarted_dispatches(state)))
            print("released to READY: %s" % (", ".join(released) or "-"))
            # THE OTHER HALF OF THE SAME SWEEP, and it used to be printed as part of the line above
            # while being none of it (see `sweep_expired_leases`): the lease is gone, the status is
            # not. Which of the two readings applies is not decidable from inside a session, so the
            # line says both and points at the moment that can decide -- a new session's start,
            # where `sweep_orphaned_dispatches` runs against the session that asked for the child.
            print("lease expired, status left standing: %s%s" % (
                ", ".join(sorted(lease_only)) or "-",
                " (either a child still working past its lease, or a dispatch nothing is behind "
                "any more -- this command cannot tell them apart; the next session start can)"
                if lease_only else ""))
            # THE SECOND LINE IS THE ANSWER A CALLER CAME FOR. A role runs this because a lease
            # blocked its dispatch; "released to READY: -" alone tells it the sweep found nothing
            # and leaves the length of the wait unknown, which is what turns a bounded wait into a
            # stall. `live_leases` says which leases are still running and for how long.
            print("still leased: %s" % (", ".join(
                "%s (%d s left)" % (task_id, int(left))
                for task_id, left in dispatch.live_leases(state)) or "-"))
            # A LEASED task with no lease is not a lease the sweep releases -- it is the untrue
            # bookkeeping DEC-0038 makes unreachable by a bare transition. Where old state or a
            # removed lease still shows it, the sweep REPORTS it (BUG-0010 AC-3) rather than
            # resetting it silently, so a human sees the anomaly instead of the sweep papering over it.
            print("LEASED without a lease (report only): %s" % (
                ", ".join(dispatch.leased_without_live_lease(state)) or "-"))
            return 0
        if args.command == "withdraw-request":
            record = approvals.withdraw_request(state, args.request_id, args.reason)
            print("%s withdrawn: %s" % (record.get("request_id") or args.request_id,
                                        record.get("withdrawn_reason")))
            # WHAT IT NO LONGER COUNTS, printed, because the noise is what the lead came for
            print("still open (answering one of these still mints): %s"
                  % (", ".join(str(one.get("request_id") or "") for one in
                               approvals.open_requests(state)) or "-"))
            return 0
        if args.command == "sweep-requests":
            swept = approvals.sweep_expired_requests(state, stale_hours=args.stale)
            # WHAT WAS REMOVED, NAMED. A cleanup that prints a count is one nobody can check
            # afterwards; these ids are the last trace the files leave.
            print("deleted (expired, could never mint): %s" % (", ".join(
                "%s %s%s" % (entry["request_id"], entry["kind"],
                             " for %s" % entry["item"] if entry["item"] else "")
                for entry in swept["removed"]) or "-"))
            print("still open (answering one of these still mints): %s"
                  % (", ".join(swept["kept"]) or "-"))
            # ...and the two answers the clock cannot give (BUG-0302): a question that was taken
            # back on this run, and one nobody can act on any more because every item it names is
            # archived. The second is REPORTED and not removed -- the withdraw-request
            # command is that door (named without backticks: a code span here would make
            # this block read as one PRESENTING the command surface, and it presents an
            # argument about two lines of output).
            print("taken back (stood longer than --stale): %s"
                  % (", ".join(swept["withdrawn"]) or "-"))
            # ...and the ones it could NOT take back, named rather than swallowed: a cleanup that
            # reports only its successes is one nobody can check (BUG-0302, verifier round 1 F8).
            if swept["not_withdrawable"]:
                print("could not be taken back (answered or gone in the meantime): %s"
                      % ", ".join(swept["not_withdrawable"]))
            print("dead (every item they name is archived; answering one changes nothing): %s"
                  % (", ".join(swept["dead"]) or "-"))
            # ...and the third outcome, which is neither: a file this command could not judge is a
            # file it did not touch, and saying so is the difference between a store that is clean
            # and one that merely looks it.
            print("left standing because they could not be read: %s"
                  % (", ".join(swept["unreadable"]) or "-"))
            return 0
        if args.command == "migrate-holes":
            if not args.reindex and not args.related_pr:
                sys.stderr.write(
                    "migrate-holes needs --related-pr <PR-nnnn>: every hole becomes an item, and "
                    "an item hangs from a goal. --reindex is the one shape that writes no item "
                    "and therefore asks for none.\n")
                return 2
            document = args.doc or holes.document_for(state)
            if args.reindex:
                print(holes.reindex(state, document, args.holes_dir))
                return 0
            # NOT named `report`: this function already reads the module of that name, and
            # a local of the same spelling makes every earlier use of it an UnboundLocalError
            # -- measured the moment this command landed.
            outcome = holes.migrate(state, document, args.related_pr, args.holes_dir,
                                    apply=args.apply)
            for line in holes.render_report(outcome):
                print(line)
            return 0

        if args.command == "migrate-goal-classes":
            mapping = {}
            for entry in args.class_map or ():
                value, sep, word = str(entry).partition("=")
                if not sep or not value:
                    sys.stderr.write(
                        "--map takes VALUE=WORD (e.g. --map feature=normal); %r names no pair.\n"
                        % entry)
                    return 2
                mapping[value] = word
            plan = migrate.goal_class_plan(state, mapping)
            print(migrate.render_goal_class_plan(plan))
            if args.apply:
                for item_id, before, after in migrate.execute_goal_classes(state, plan):
                    print("written: %s %r -> %r" % (item_id, before, after))
            else:
                print("nothing written (no --apply)")
            return 1 if migrate.unmapped_goal_classes(plan) else 0

        if args.command == "migrate":
            field_map = migrate.parse_field_map(args.field_map)
            plan = migrate.build_plan(state, field_map, args.archive_year)
            digest = migrate.plan_digest(plan)
            if args.dry_run:
                print(migrate.render(plan, state))
                # 1 = "there are findings", exactly as `validate` uses it: a dry run that cannot
                # be executed as it stands is the same kind of answer as a state finding, and a
                # caller scripting this needs to tell the two apart without parsing prose.
                return 0 if migrate.plan_is_executable(plan) else 1
            if args.plan != digest:
                # A USAGE error and not a state refusal: the command was never attempted.
                #
                # WHAT THE MISMATCH DOES AND DOES NOT TELL THE CALLER, and why the answer is a
                # DECOMPOSITION rather than a list of causes. This message has now been short
                # THREE times, every time in the same direction and every time because it counted:
                # first "something under the state directory changed" while the `--map` flags are
                # in the plan too; then "the flags" while `--archive-year` is equally in it and
                # while the plan carries the WALLS, which come out of the project's `.claude/`
                # registration and not out of the state directory; and then those three while the
                # kernel's OWN contract tables decide half of what a record classifies to.
                # Measured 2026-08-07: adding one entry to `backlog_types.OPTIONAL_FIELDS` moves
                # the digest with `state_fingerprint` byte-identical, the flags unchanged and the
                # registration unchanged -- both places the message named answer nothing about it.
                #
                # A plan is a deterministic COMPUTATION, so it can move for exactly three kinds of
                # reason: what it read, what it was told, and what computed it. That is closed by
                # construction, which a list of three causes was not, and each kind is given the
                # place that answers it rather than an answer restated here.
                raise UsageError(
                    "this run is not the run the dry run presented. You passed %r; this command "
                    "line against this state digests to %s. The digest is a fingerprint of the "
                    "whole PLAN, and a plan is a computation: it moves only when one of its "
                    "inputs does, and it has three kinds of input. What the dry run READ -- the "
                    "content of the state directory, and this project's hook REGISTRATION, "
                    "because the plan records which documents are walls a gate reads (so "
                    "installing, removing or re-pointing a refusal-capable hook moves the plan "
                    "while every file under the state directory stays byte-identical). What it "
                    "was TOLD -- the flags on this command line. And the CODE AND TABLES that "
                    "computed it: a kit update between the two halves can change what the same "
                    "records classify to, with every file and every flag byte-identical. In each "
                    "case the plan you read is not the plan that would run. (WHICH files count is "
                    "`kernel/migrate.state_fingerprint`, which also names what it leaves out; "
                    "WHICH hooks count is `kernel/layout.gated_documents`; `%s doctor` reports "
                    "both -- the walls it derives from that registration, each with the gate that "
                    "reads it, and the `kit_version` this project is installed at, which is where "
                    "the third kind shows.) This command cannot tell you WHICH of them moved: it "
                    "holds the digest of the plan you read, not that plan. "
                    "Remedy: `%s migrate --dry-run` with the flags you mean, read it again, and "
                    "use the digest it prints."
                    % (args.plan, digest, INVOCATION, INVOCATION))
            result = migrate.execute(state, plan, digest)
            if not result["created"]:
                print("nothing to migrate: no record in this state is translatable and none was "
                      "written, so this run changed nothing.")
                return 0
            print("imported %d item(s): %s" % (len(result["created"]),
                                               ", ".join(result["created"])))
            print("run recorded as %s" % result["receipt"])
            # THE SAME WARNING THE DRY RUN PRINTS, on the half that actually produced the state.
            # It stood in `render` only, so the executing run said nothing about a project it had
            # just left without a root item -- and `render` is the half a scripted or scrolled-past
            # invocation never reads. `migrate.root_item_warnings` is the one text.
            for line in migrate.root_item_warnings(plan, written=True):
                print(line)
            return 0
    except UsageError as exc:
        # BEFORE the generic handler, because UsageError IS a ValueError -- the broad clause below
        # would otherwise swallow it and report "the kernel refused" for input the kernel never saw
        print(str(exc), file=sys.stderr)
        return 2
    except (StateError, TransitionError, ValueError, TimeoutError, RuntimeError) as exc:
        # TimeoutError covers LockTimeout (another kernel op holds the lock),
        # RuntimeError the missing-state-dir case -- both carry their remedy
        print(str(exc), file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
