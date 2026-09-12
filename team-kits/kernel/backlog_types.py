"""Item types, status automata and V1 mapping (HARNESS_V2_SPEC.md II.2 / II.10).

Single machine-readable source for:
- the 12 typed items (dev/office root: PR; research root: RQ + HYP/EXP)
- their status automata (chains, explicit terminal edges, TSK back-edges) --
  transitions happen ONLY through `assert_transition` callers (kernel
  `transition`); anything else is a schema error (spec II.2)
- type-dependent approval invalidation targets (PR/RQ/CR/PROC -> DRAFT,
  BUG -> TRIAGED, SR -> PROPOSED, EXP -> DESIGNED; HYP deliberately absent --
  it carries no approval_ref and rides on the RQ scope approval)
- the `<TYP>-nnnn` id convention
- the binding V1 -> V2 status mapping (spec II.10; unknown values RAISE --
  the kernel layer turns that into a block + Decision item, never a guess)

Terminal edges are the conservative explicit set below; widening any of them
is a SPEC change, not an implementation decision (spec II.2). BLOCKED is a
flag (`blocked_by`), never a status.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date


# -- status automata -----------------------------------------------------------

def _edges(chain, terminal_from):
    """Build the allowed-transition set: consecutive chain edges + terminal edges."""
    allowed = set(zip(chain, chain[1:]))
    for terminal, sources in terminal_from.items():
        for src in sources:
            allowed.add((src, terminal))
    return allowed


class _Automaton:
    def __init__(self, chain, terminals, terminal_from, extra_edges=(), extra_states=()):
        self.chain = tuple(chain)
        self.terminals = frozenset(terminals)
        self.states = frozenset(chain) | self.terminals | frozenset(extra_states)
        self.allowed = _edges(chain, terminal_from) | set(extra_edges)
        # construction-time self-checks (Fable-Check 5): terminals never have
        # outgoing edges, and every edge endpoint is a registered state -- a
        # typo in an edge fails loudly here instead of becoming a dead edge
        for src, dst in self.allowed:
            if src in self.terminals:
                raise AssertionError("terminal state %r must not have outgoing edges" % src)
            if src not in self.states or dst not in self.states:
                raise AssertionError("edge (%r -> %r) references unregistered state" % (src, dst))

    @property
    def initial(self):
        return self.chain[0]


_PR_LIKE = _Automaton(
    chain=("DRAFT", "APPROVED", "IN_DELIVERY", "DELIVERED", "ACCEPTED"),
    terminals=("ACCEPTED", "REJECTED", "SUPERSEDED"),
    terminal_from={
        "REJECTED": ("DRAFT", "APPROVED", "IN_DELIVERY", "DELIVERED"),
        "SUPERSEDED": ("DRAFT", "APPROVED", "IN_DELIVERY", "DELIVERED"),
        # ACCEPTED only via the chain (DELIVERED -> ACCEPTED)
    },
)

AUTOMATA = {
    "PR": _PR_LIKE,
    "RQ": _PR_LIKE,
    "FR": _Automaton(
        chain=("OPEN", "TRIAGED"),
        terminals=("MERGED", "CONVERTED", "REJECTED"),
        terminal_from={  # a triage OUTCOME requires a triage first
            "MERGED": ("TRIAGED",),
            "CONVERTED": ("TRIAGED",),
            "REJECTED": ("TRIAGED",),
        },
    ),
    "CR": _Automaton(
        chain=("DRAFT", "APPROVED", "APPLIED"),
        terminals=("APPLIED", "REJECTED"),
        terminal_from={"REJECTED": ("DRAFT", "APPROVED")},
    ),
    # A DEFECT, AND SINCE DEC-0073 ALSO A HOLE. A measured, open gap in a guard carries exactly
    # this type's fields -- observed, expected, repro, severity, acceptance criteria -- plus one
    # duty (`limits`: what takes the place of the protection) and one ending this automaton did not
    # have: a gap the USER has accepted as a named exception. `ACCEPTED_EXCEPTION` is that ending.
    # ONLY FROM TRIAGED, and that is the whole placement: an exception is accepted for a gap
    # somebody has LOOKED at, never for one nobody has read yet (OPEN) and never for one already
    # fixed (FIXED). It is a terminal, so nothing walks out of it again -- a gap whose exception
    # falls (DEC-0069 (3) names that moment) is a NEW item with its own measurement, which is what
    # keeps the record of the acceptance from being edited into something the user never said.
    # WHO MAY WALK IT is not this table's answer but `approvals.APPROVAL_TRANSITIONS`': the pair
    # (BUG, hole_exception) binds this edge to a user-minted approval, because a status the
    # supervised party can set itself is a status no gate may read as an acceptance.
    "BUG": _Automaton(
        chain=("OPEN", "TRIAGED", "APPROVED", "FIXED", "VERIFIED"),
        terminals=("VERIFIED", "REJECTED", "DUPLICATE", "ACCEPTED_EXCEPTION"),
        terminal_from={
            "REJECTED": ("OPEN", "TRIAGED", "APPROVED", "FIXED"),
            "DUPLICATE": ("OPEN", "TRIAGED", "APPROVED", "FIXED"),
            "ACCEPTED_EXCEPTION": ("TRIAGED",),
            # VERIFIED only via the chain (FIXED -> VERIFIED)
        },
    ),
    "SR": _Automaton(
        chain=("PROPOSED", "ACCEPTED"),
        terminals=("SUPERSEDED",),
        terminal_from={"SUPERSEDED": ("PROPOSED", "ACCEPTED")},
    ),
    "TSK": _Automaton(
        chain=("DRAFT", "READY", "LEASED", "IN_PROGRESS", "SUBMITTED", "DONE", "VALIDATED"),
        terminals=("VALIDATED", "CANCELLED"),
        terminal_from={
            "CANCELLED": ("DRAFT", "READY", "LEASED", "IN_PROGRESS", "SUBMITTED", "DONE", "FAILED"),
            # VALIDATED only via the chain (DONE -> VALIDATED, QA evidence)
        },
        extra_edges=(
            # explicit back-edges (spec II.2 Querregeln)
            ("LEASED", "READY"),          # lease timeout / spawn failure
            ("IN_PROGRESS", "FAILED"),
            ("SUBMITTED", "FAILED"),
            ("DONE", "FAILED"),
            ("FAILED", "READY"),          # ONLY on approved retry (kernel checks)
        ),
        extra_states=("FAILED",),         # non-terminal, non-chain side state
    ),
    "PROC": _Automaton(
        chain=("DRAFT", "APPROVED", "ACTIVE"),
        terminals=("RETIRED",),
        terminal_from={"RETIRED": ("DRAFT", "APPROVED", "ACTIVE")},
    ),
    "HYP": _Automaton(
        chain=("PROPOSED", "TESTING"),
        terminals=("SUPPORTED", "REFUTED", "INCONCLUSIVE"),
        terminal_from={
            "SUPPORTED": ("TESTING",),
            "REFUTED": ("TESTING",),
            "INCONCLUSIVE": ("TESTING",),
        },
    ),
    "EXP": _Automaton(
        chain=("DESIGNED", "APPROVED", "RUNNING", "COMPLETED", "ANALYZED"),
        terminals=("ANALYZED", "ABORTED"),
        terminal_from={"ABORTED": ("DESIGNED", "APPROVED", "RUNNING", "COMPLETED")},
    ),
    # A MILESTONE (DEC-0064, FR-0079). A date several goals share, with a NAME and an OUTCOME --
    # which is what makes it a type rather than a field: a `due` copied into every item it applies
    # to has no identity, no way to record "missed", and no test that notices when one copy was not
    # moved (items are practically immutable, so a shifted deadline would be n kernel edits).
    # THE THREE ENDINGS ARE THE POINT. `REACHED` only through the chain -- a milestone is reached
    # by arriving at it; `MISSED` and `DROPPED` only from `PLANNED`, because a milestone that has
    # already been reached cannot afterwards have been missed or called off. No approval kind pairs
    # with it in `approvals.APPROVAL_TRANSITIONS` and it has no `INVALIDATION_TARGET`: a date is
    # not something a user signs, and nothing about it can invalidate an approval.
    "MST": _Automaton(
        chain=("PLANNED", "REACHED"),
        terminals=("REACHED", "MISSED", "DROPPED"),
        terminal_from={"MISSED": ("PLANNED",), "DROPPED": ("PLANNED",)},
    ),
}

# -- approval invalidation (spec II.2 table; atomic op lives in the kernel) ----

INVALIDATION_TARGET = {
    "PR": "DRAFT",
    "RQ": "DRAFT",
    "CR": "DRAFT",
    "PROC": "DRAFT",
    "BUG": "TRIAGED",
    "SR": "PROPOSED",
    "EXP": "DESIGNED",
    # HYP deliberately absent: no approval_ref, rides on the RQ scope approval
}

# -- id convention + storage dirs ---------------------------------------------

ACTIVE_DIRS = {
    "PR": "product/active",
    "FR": "inbox/active",
    "CR": "changes/active",
    "BUG": "bugs/active",
    "SR": "system/active",
    "TSK": "tasks/active",
    "PROC": "procedures/active",
    "INV": "invariants/active",
    "APR": "approvals",
    "RQ": "research/active",
    "HYP": "hypotheses/active",
    "EXP": "experiments/active",
    "DEC": "decisions/active",   # Decision items (id prefix: implementation choice)
    "EVD": "evidence",           # Evidence (no own project status; id prefix: impl. choice)
    "ARC": "architecture/active",
    "MST": "milestones/active",  # milestones (DEC-0064)
    "WFR": "design/wireframes",  # frozen on scope approval (II.6a)
    "DSN": "design/revisions",   # frozen design revisions (II.6; promotion path)
}

# The item a project HANGS FROM, per kit -- the one the entry gate seeds at onboarding and the one
# `_root.has_root_item` looks for to decide a repo is past setup. A kit is absent here when it has no
# such item: the office kit is led by procedures and master data, its constitution knows no PR
# anywhere, and the "PR" this map used to claim for it sent the entry gate to write a PR-0001 no
# office role would ever read.
ROOT_TYPE_BY_KIT = {"dev-team": "PR", "research-team": "RQ"}

_ID_RE = re.compile(r"([A-Z]{2,4})-(\d{4,})", re.ASCII)


def format_id(item_type: str, number: int) -> str:
    if item_type not in ACTIVE_DIRS:
        raise KeyError("unknown item type %r" % item_type)
    return "%s-%04d" % (item_type, number)


def parse_id(item_id: str):
    """Return (type, number) or raise ValueError with a remedy."""
    # fullmatch + ASCII: `$` would match before a trailing newline and \d would
    # accept non-ASCII digits (Fable-Check 6/BUG-2)
    m = _ID_RE.fullmatch(item_id or "")
    if not m or m.group(1) not in ACTIVE_DIRS:
        raise ValueError(
            "invalid item id %r -- expected <TYP>-nnnn with TYP one of %s. "
            "Remedy: use kernel-assigned ids only."
            % (item_id, "/".join(sorted(ACTIVE_DIRS)))
        )
    return m.group(1), int(m.group(2))


# -- transition API ------------------------------------------------------------

class TransitionError(ValueError):
    """Illegal status transition -- a schema error per spec II.2."""


def initial_status(item_type: str) -> str:
    auto = AUTOMATA.get(item_type)
    if auto is None:
        raise TransitionError(
            "unknown item type %r. Remedy: use one of %s."
            % (item_type, "/".join(sorted(AUTOMATA)))
        )
    return auto.initial


def is_terminal(item_type: str, status: str) -> bool:
    return status in AUTOMATA[item_type].terminals


# THE STATUS VOCABULARY OF THE TYPES THAT CARRY ONE WITHOUT AN AUTOMATON (spec II.2). Written out
# because there is nothing to derive it from -- these types have no edge set -- and written HERE
# rather than in `state` so that the kernel's initial-status map and the V1 mapping table's target
# check read ONE answer; it lived only in a comment before, which is why a mapping row could name
# a `DEC` status nothing could check. The FIRST value is the initial one.
#
# `INV.verified` is what spec II.2 names as the other side of `unverified` and NOTHING in this
# kernel writes it yet: an invariant becomes verified once its referenced check test exists and is
# collectable, and no code here establishes that. It is in the vocabulary, not in the behaviour.
NON_AUTOMATON_STATUSES = {"DEC": ("VALID", "SUPERSEDED"), "INV": ("unverified", "verified")}


def status_values(item_type: str) -> tuple:
    """Every status this type can carry -- from its automaton, or from the map above."""
    automaton = AUTOMATA.get(item_type)
    if automaton is not None:
        return tuple(sorted(automaton.states))
    return NON_AUTOMATON_STATUSES.get(item_type, ())


def widest_status() -> str:
    """The longest status string any shipped automaton carries.

    A FUNCTION over `AUTOMATA` rather than a literal in the caller, and the caller is `migrate`'s
    per-item budget check: it measures the body the kernel WILL write, so it needs a placeholder
    that can never be shorter than the real value. Its previous placeholder was the literal
    `"VALID"`, one byte short of `DRAFT`... and of `RETIRED`, and the check then passed items
    `validate` flags. Derived here so a renamed status moves the measure with it, and so the AST
    reader in `test_approvals_dispatch` can bound the write it feeds from the same map.
    """
    return max((status for automaton in AUTOMATA.values() for status in automaton.states), key=len)


def confirming_edge(item_type: str):
    """The (from, to) edge on which a type is closed as CONFIRMED, or None.

    DERIVED FROM THE TYPE'S OWN EDGE SET, because that set already draws the distinction: a
    terminal a type can be dropped into is reachable from SEVERAL statuses at once, which is what
    "closed because it was abandoned" looks like (REJECTED, DUPLICATE, CANCELLED, SUPERSEDED); the
    chain's LAST status, when it is a terminal whose only incoming edge is from its chain
    predecessor, can be reached only by walking the whole chain, which is what "closed because it
    was confirmed" looks like. Measured over the shipped automata it picks out SIX types -- BUG
    FIXED->VERIFIED, TSK DONE->VALIDATED, PR and RQ DELIVERED->ACCEPTED, CR APPROVED->APPLIED and
    EXP COMPLETED->ANALYZED -- and it picks out the next such chain without an edit here. (An
    earlier wording of this line said "exactly BUG, TSK, PR/RQ" and left CR and EXP out; the answer
    is `test_the_confirming_edge_is_derived_from_each_types_own_edge_set`, not this sentence.)

    What a confirmation must SHOW is a different question, and one no automaton answers -- see
    `state.CONFIRMING_EVIDENCE`, which is where the promises the shipped texts actually make are
    recorded, and where the ones nothing enforces are named as not enforced.
    """
    auto = AUTOMATA.get(item_type)
    if auto is None or len(auto.chain) < 2:
        return None
    target = auto.chain[-1]
    if target not in auto.terminals:
        return None
    sources = {src for src, dst in auto.allowed if dst == target}
    return (auto.chain[-2], target) if sources == {auto.chain[-2]} else None


def replanning_route(item_type: str, status: str) -> dict:
    """Where an item standing in `status` can GO, for the two moves a frozen work order leaves.

    THE REMEDY OF A FROZEN-FIELD REFUSAL IS READ OFF THE AUTOMATON AT REFUSAL TIME (BUG-0089), and
    that is the whole reason this function exists. The refusal used to name "transition the task
    back to DRAFT" as prose beside the table; measured 2026-09-02 on a READY `TSK`, `transition
    <id> DRAFT` answers "illegal transition TSK: READY -> DRAFT (allowed from READY: CANCELLED,
    LEASED)" -- the printed remedy could not be walked. The sentence had outlived the table, which
    is the defect class every enumeration in this kernel is watched for.

    TWO KEYS, because the two moves are different work:
      * `replan` -- the statuses ONE EDGE away in which the work-order fields are writable again.
        That is the type's INITIAL status and nothing else, and it is the same fact
        `state._update_item_locked` decides the freeze on: the fields are open exactly while the
        item still stands where planning happens. One fact, read by the refusal and by the remedy.
      * `close` -- the TERMINAL statuses one edge away, i.e. the "close it and capture a new one"
        half. Terminal, because a status the item can still leave is not a way of ending it.

    EITHER MAY BE EMPTY and the caller may only name what is not. On the shipped `TSK` automaton
    `replan` is empty from every status except the initial one, because no edge leads into DRAFT at
    all -- which is exactly what BUG-0089 measured.
    `tools/test_backlog_types.py::test_the_replanning_route_names_only_edges_the_automaton_has`
    holds both ends: no named target without an edge, and no edge left unnamed.
    """
    auto = AUTOMATA.get(item_type)
    if auto is None:
        return {"replan": (), "close": ()}
    reachable = {dst for src, dst in auto.allowed if src == status}
    return {
        "replan": tuple(sorted(reachable & {auto.initial})),
        "close": tuple(sorted(reachable & auto.terminals)),
    }


def assert_transition(item_type: str, from_status: str, to_status: str) -> None:
    """Raise TransitionError unless (from -> to) is an allowed edge."""
    auto = AUTOMATA.get(item_type)
    if auto is None:
        raise TransitionError(
            "unknown item type %r. Remedy: use one of %s."
            % (item_type, "/".join(sorted(AUTOMATA)))
        )
    for status in (from_status, to_status):
        if status not in auto.states:
            raise TransitionError(
                "unknown status %r for %s (states: %s). BLOCKED is a flag "
                "(blocked_by), never a status. Remedy: use `python scripts/harness.py transition` "
                "with a defined status." % (status, item_type, ", ".join(sorted(auto.states)))
            )
    if (from_status, to_status) not in auto.allowed:
        raise TransitionError(
            "illegal transition %s: %s -> %s (allowed from %s: %s). Remedy: "
            "run the required intermediate kernel operations; direct jumps are "
            "schema errors (spec II.2)."
            % (
                item_type,
                from_status,
                to_status,
                from_status,
                ", ".join(sorted(dst for src, dst in auto.allowed if src == from_status)) or "-",
            )
        )


def invalidation_target(item_type: str) -> str:
    """Target status when hashed fields of an approved item change (spec II.2)."""
    try:
        return INVALIDATION_TARGET[item_type]
    except KeyError:
        raise KeyError(
            "%s has no approval invalidation target (it carries no approval_ref)"
            % item_type
        ) from None


# -- per-type field contracts (spec II.2 "Pflichtfelder") ----------------------

# Kernel-set on capture (callers never provide these): id, status, revision,
# approval_ref, created. The lists below are the CALLER-provided required
# fields; optionality noted per spec (user_story, related_pr, derives_from on
# PROC, design_ref conditional on TSK).
# STATUS-DEPENDENT duties enforced by the 1.4c validator, NOT at capture:
# FR.triage_result (from TRIAGED), PROC.approved_hash (from APPROVED),
# PR.user_story (required unless class == technical_enabler),
# INV text/value (exactly one of the two required).
REQUIRED_FIELDS = {
    "PR": ("title", "class", "problem", "goal", "acceptance_criteria",
           "invariants", "out_of_scope", "priority"),
    "RQ": ("title", "class", "question", "motivation", "acceptance_criteria",
           "out_of_scope", "priority"),
    "FR": ("title", "request_text"),
    "CR": ("title", "target_pr", "target_revision", "change_description",
           "acceptance_criteria"),
    "BUG": ("title", "related_pr", "observed", "expected", "repro", "severity",
            "acceptance_criteria"),
    "SR": ("title", "derives_from", "contract", "affected_components"),
    "TSK": ("product_requirement", "root_revision", "derives_from", "type",
            "assigned_role", "acceptance_refs", "required_inputs",
            "allowed_scope", "forbidden_scope", "expected_outputs",
            "dependencies"),
    "PROC": ("title", "steps", "roles"),
    "INV": ("scope", "source", "check"),
    "HYP": ("derives_from", "statement", "testable_prediction"),
    "EXP": ("derives_from", "design", "variables", "success_criteria",
            "evidence_refs"),
    "DEC": ("title", "context", "decision", "consequences", "source"),
    # `result` beyond the spec's field list, and additively: the spec fixes what
    # Evidence must SAY about itself, while a gate has to know what it says about
    # the work. Without a verdict field the store cannot distinguish "QA ran and
    # passed" from "QA ran and failed", and `gate_git` would open a merge on the
    # existence of a failing report -- the false-accept an earlier audit found in
    # the V1 report files, one level in.
    "EVD": ("kind", "related", "result", "summary", "artifact_refs"),
    # A MILESTONE (DEC-0064): the name it is known by, the date it falls on, and the roots the
    # date applies to. `derives_from` is REQUIRED and is what makes membership readable at all --
    # a milestone that names no goal is a date nobody can act on -- and it is the binding
    # direction the tree already walks (`_BINDING_FIELD_NAMES`), so the milestone hangs under its
    # roots instead of turning the tree over. The reverse reference (a `milestone` field on a task)
    # is deliberately not built; DEC-0064 (6) names it as its own FR if anybody needs it.
    "MST": ("title", "due", "derives_from"),
}

# The OTHER half of the same contract: fields spec II.2 declares for a type and
# lets it omit. Machine-readable for the reason `schemas.item_field_contracts`
# reports every DECLARED field rather than only the required ones -- whether a
# field means anything to the reference graph is a question about the FIELD, and
# an item's freedom to leave it out is a question about the ITEM. Reading only
# `REQUIRED_FIELDS` answers the first question with the second one, and that is
# how `PROC.derives_from` (spec II.2: "derives_from (optional)") and
# `FR.related_pr` ("related_pr (optional)") stayed outside the graph: a PROC
# captured against a phantom parent was reported by nobody and an Evidence
# recorded on it never reached its root, the identical damage the `SR` and the
# `ARC`/`WFR`/`DSN` rounds were about.
# The comment above lists the same four fields in prose; this is that sentence
# in a form the derivation can read.
# WHAT THE RUN BEHIND AN EVIDENCE COVERED (FR-0040). Until this pair existed, a pass from
# `pytest -k one_test` and a pass from the whole suite were the SAME record: `REQUIRED_FIELDS`
# named the verdict, the summary and the artefacts, and no field named the run -- while two
# places in the shipped tree already told the reader that a partial run is not merge evidence (the
# refusal texts of `gate_git`, and the vocabulary comment at `EVIDENCE_RESULTS` as it then stood).
# That claim is what these two fields make true.
#
# TWO FIELDS BECAUSE THEY ARE TWO DIFFERENT THINGS, and only the second is machine-readable:
# `run_command` is the line that was executed, which is what an auditor re-runs, and `run_scope`
# is the claim about it. The kernel cannot DERIVE the second from the first -- what counts as the
# whole suite is a fact about the project's test runner, not about a string -- so the claim is the
# role's and the command is what it can be checked against. That limit is the honest one and it is
# stated here rather than papered over with a list of `pytest` flags, which would be a rule about
# one runner in a kernel three kits share.
#
# ONLY THE PASS SIDE IS FILTERED (`report._delivery_evidence`), and the asymmetry is the argument:
# a run over part of the work can show a defect, so a `fail` from a selection is a fail; it cannot
# show the absence of one over a whole DELIVERY, so a `pass` from a selection opens no merge.
# IT DOES CONFIRM A NAMED DEFECT, and that is DEC-0071: the absence a regression run has to show is
# bounded by the item it names, so the confirming edge reads the very record the merge drops. Two
# questions, one derivation -- `report.DELIVERY_QUESTION` is where the split is argued.
# DECISION: DEC-0061. FR-0040 asked for the decision FIRST, and a built file that embodies one
# names its number (CLAUDE.md) -- so a reader who arrives here through the code lands on the same
# record as one who greps the decisions.
RUN_SCOPES = frozenset(("full", "selection"))
PARTIAL_RUN_SCOPE = "selection"

# The two of them are ONE statement and are declared together or not at all: a scope with no
# command is a claim with nothing behind it, and a command with no scope is a record the merge
# cannot read. Enforced in `state.capture_preflight`; the decision is DEC-0061.
RUN_RECORD_FIELDS = ("run_command", "run_scope")

# THE THIRD EVIDENCE OUTCOME AND THE SENTENCE IT OWES (FR-0082). Declared up here because
# `OPTIONAL_FIELDS` below has to name the field; the argument for the VALUE is at
# `EVIDENCE_RESULTS`, where the vocabulary is, and it is not repeated here.
# The pair is enforced in `state.capture_preflight` in BOTH directions -- a `blocked` without the
# sentence, and the sentence without a `blocked` -- and
# `tools/test_state.py::test_a_blocked_evidence_owes_its_sentence_and_the_sentence_owes_its_verdict`
# measures both ends.
BLOCKED_RESULT = "blocked"
BLOCKED_REASON_FIELD = "blocked_reason"
# The field the pair is about, named once so the rule and everything that has to SATISFY the rule
# (the capture path, the CLI, the suite's contract fixture) read one spelling.
EVIDENCE_RESULT_FIELD = "result"


# -- a HOLE: a measured gap the project does not close (FR-0087, DEC-0073) -----
#
# WHAT A HOLE IS, AND WHY IT IS NOT ITS OWN TYPE. It is a defect with a named limit -- the same
# five things a `BUG` already carries (observed, expected, repro, severity, acceptance criteria)
# plus one field and one ending. DEC-0073 decided the `BUG` shape against a type of its own, on a
# cost measured rather than guessed: a new entry in `ACTIVE_DIRS` turns
# `tools/test_hooks.py::test_no_adhoc_covers_every_item_type` and
# `tools/test_board.py::test_every_type_that_moves_through_a_lifecycle_is_placed_by_a_backlog_view`
# red, and the first of those two is repaired in `team-kits/*/hooks/guard_no_adhoc.py`, three
# mirrored copies outside this stream's reach -- while the second contract would repeat `BUG`'s
# field list word for word to add one field.
#
# THE NUMBER IS ALLOCATED BY THE KERNEL (`state.capture`), never by hand. Hand-reserved H numbers
# are the measured defect FR-0087 was written for: generation 3 handed them out per stream by
# message, and the verifier of stream E found two of them in no frozen item at all. A caller says
# THAT the item is a hole; WHICH number it gets is not a caller's decision.
# `tools/test_state.py::test_the_kernel_hands_out_the_hole_number_and_never_the_caller`
HOLE_NUMBER_FIELD = "hole_number"
HOLE_NUMBER_PREFIX = "H"
# WHAT TAKES THE PLACE OF THE PROTECTION -- the sentence a hole owes and an ordinary defect does
# not. Required in `ACCEPTED_EXCEPTION` and in no other status: see `STATUS_DEPENDENT_FIELDS`.
HOLE_LIMIT_FIELD = "limits"
# The tests that go RED without the fix an entry claims. A FIELD and not a sentence in the prose,
# and that is the whole move FR-0087 (c) asks for: the shipped judge used to fish these names out
# of a markdown document with a code-span reader, and every limit of that reader -- a name behind a
# fence, a wrapped name, a span showing a span -- was a citation nobody checked. Read off the item,
# the question "does this name resolve" is asked of a parsed list.
HOLE_TEST_FIELD = "regression_tests"

# WHAT A HOLE OWES *ONCE IT IS STORED*, and it is NOT its type's full contract. A `BUG` owes
# `expected`, `repro` and `acceptance_criteria` because it is a defect somebody is going to CLOSE;
# a hole is a defect nobody is closing -- that is what makes it a hole -- so those three would be a
# form filled in for a fix that is not planned. Measured over the shipped hole list before this was
# written: every entry states a verdict, most state a mechanism, and well under two thirds state a
# measured chain, so a contract demanding a repro of each could only be met by inventing them.
#
# WHERE IT APPLIES, said exactly rather than as a whole: `report.validate_state` judges STORED
# items through `required_fields_of`, and `state.capture_migrated_hole` writes past the field
# contract like every migration door. `state.capture` does NOT use it -- it asks
# `REQUIRED_FIELDS[type]` through `capture_preflight`, so filing a hole with `capture --hole` still
# owes the full `BUG` contract. That is the honest split and it is deliberate: a gap somebody is
# measuring TODAY can say what should happen instead and how it was reproduced, while a fifteen-
# month-old document entry cannot be made to. `tools/test_backlog_types.py::test_the_hole_contract
# _is_the_reading_side_and_capture_still_asks_the_full_one` holds both halves.
# `tools/test_backlog_types.py::test_the_hole_contract_is_a_subset_of_the_contract_its_type_declares`
HOLE_REQUIRED_FIELDS = ("title", "related_pr", "observed", "severity")


def hole_type() -> str:
    """The type a HOLE IS -- derived from the contract, never spelled a second time.

    A hole is a defect with a named limit, so it is the type this kernel already holds a defect in
    (DEC-0073 decided that against a type of its own, with the cost measured). WHICH type that is
    is read off the field contract: exactly one type declares `HOLE_NUMBER_FIELD`, because that is
    what "this type can carry a hole number" means. Every other reader takes it from here --
    `state.capture`'s refusal, `state.capture_migrated_hole`'s target, `required_fields_of` below --
    so the answer exists once.

    THE DEFECT THAT ASKED FOR IT: the CLI checked the type as an enumeration of ONE (`!= "TSK"`)
    while the definition lay beside it, so `capture DEC --hole` stamped a hole number on a decision,
    burnt a number nothing can free, and left the hole judge permanently red -- one rc-0 command,
    repairable only from outside the session (`project_memory/` takes no tool write).
    `tools/test_state.py::test_only_the_type_a_hole_is_can_be_captured_as_one`
    """
    # `_contract_fields()` and not `OPTIONAL_FIELDS`: the sentence above says "the field
    # contract", and the contract is BOTH halves -- what a type must carry and what it may. Reading
    # only the optional half meant a second type declaring the field as REQUIRED slipped past the
    # loud abort without a word (measured 2026-09-05: contract carriers ['BUG', 'PROC'],
    # `hole_type()` still answered BUG).
    carriers = sorted(item_type for item_type, fields in _contract_fields().items()
                      if HOLE_NUMBER_FIELD in fields)
    if len(carriers) != 1:
        raise AssertionError(
            "%d types declare %s, so what a hole IS has no single answer: %s. A hole is one type's "
            "shape (DEC-0073); declaring the field on a second type is a contract decision that "
            "needs its own DEC, not a widening this derivation can absorb."
            % (len(carriers), HOLE_NUMBER_FIELD, carriers))
    return carriers[0]


def required_fields_of(item_type: str, item: dict) -> tuple:
    """The fields THIS item owes -- its type's contract, or the hole contract when it is a hole.

    ONE reader (`report.validate_state`'s field-duty loop), so "what does this item owe" has one
    answer. The hole is recognised by the field the kernel stamps and no caller may hand in
    (`HOLE_NUMBER_FIELD`), which is why the narrower contract cannot be claimed by a body that
    simply says so.
    """
    if item_type == hole_type() and (item or {}).get(HOLE_NUMBER_FIELD):
        return HOLE_REQUIRED_FIELDS
    # `__getattr__` and not the bare name: `DECLARED_REQUIRED_FIELDS` is one of the DERIVED maps
    # this module computes on first access (see `_DERIVED`), so the name is bound for an importer
    # and NOT inside the module. Written as a plain reference first, this raised `NameError` in
    # `report.validate_state` -- measured 2026-09-04 against a migrated store, where every single
    # validate died before its first finding.
    return __getattr__("DECLARED_REQUIRED_FIELDS").get(item_type, ())

# What an item owes ONLY while it stands in ONE status: {(type, status): field}.
#
# A MAP AND NOT A BRANCH PER CASE, because the validator's loop then gains a row rather than an
# `if`, and because the two ends can be measured against the automata:
# `tools/test_backlog_types.py::test_every_status_dependent_duty_names_a_status_its_type_really_has`
# holds every key to `AUTOMATA` and every field to a name its type's readers use.
#
# WHY THE DUTY IS NARROW. `HOLE_LIMIT_FIELD` binds in `ACCEPTED_EXCEPTION` alone and not from
# TRIAGED on, and the reason is the cost DEC-0061 (a) measured for a wider duty on a stored type:
# a duty on a status the stored records already stand in turns every one of them into a validator
# error on the day of the rule, with no command that repairs it -- `gate_memory_complete` blocks
# every merge and push on such an error. How many that is in a given store is a measurement of the
# round that asks, not a number this comment can keep.
STATUS_DEPENDENT_FIELDS = {
    ("FR", "TRIAGED"): "triage_result",
    ("BUG", "ACCEPTED_EXCEPTION"): HOLE_LIMIT_FIELD,
}

# The terminal a hole reaches when the USER has accepted it as a named exception. Spelled once,
# read by the automaton comment above, by `approvals.APPROVAL_TRANSITIONS` and by the migration.
HOLE_EXCEPTION_STATUS = "ACCEPTED_EXCEPTION"


# THE OTHER HALF OF A DECISION'S LIFE, and the one FR-0012 asked for: does it commit anybody to
# BUILD something, and to what. `none` is the honest silence for a decision that demands nothing;
# a list of item ids is resolved like every other binding. Read by `report._check_decision_carriers`
# in both directions -- an id no item carries is an error, a decision in force that names no work
# and that NO item names is a warning. Spelled once here because three readers ask for it.
DEC_WORK_FIELD = "work"
# What `DEC_WORK_FIELD` says when the decision commits nobody. A closed value beside the id list,
# so "nothing to build" and "nobody wrote the field" are two different states -- which is the whole
# difference between the honest silence and the DEC-0034 case.
DEC_WORK_NONE = "none"

# THE PM'S TIER ASK ON A WORK ORDER (DEC-0091 (1)): the rung and the effort the PM judges THIS slice
# needs, set at `create-task` and changeable while the order is still being planned. They are an
# INPUT of the dispatcher's derivation and never its answer: `kernel.dispatch.ladder_for_order`
# takes the higher of the ladder's floor and this ask (DEC-0091 (2)), and what the lease then
# derived lands on the task under `kernel.dispatch.LEASE_RUNG_FIELD` / `LEASE_EFFORT_FIELD`. Two
# names for two facts, because the derived value written back under the ask's name would become the
# next lease's floor and climb twice. Spelled here and imported by `dispatch` (its `RUNG_KEY` /
# `EFFORT_KEY`), so the contract and its reader cannot come to spell the field differently;
# `tools/test_light_kit.py::test_the_order_fields_are_the_contracts_and_frozen_with_the_plan`.
TSK_RUNG_FIELD = "rung"
TSK_EFFORT_FIELD = "effort"

# Fields a type owes when a caller CAPTURES it, and never in the store (DEC-0083 (1)). The two are
# not the same duty: `REQUIRED_FIELDS` is read by the validator too, so putting `work` there would
# turn every decision this project already holds into an error no command repairs -- the same
# argument DEC-0061 measured for `EVD`. Here the duty binds the door alone: from the day the field
# exists a NEW decision says whether it commits anybody, and the stored ones are answered by the
# pointer direction instead (`report._check_decision_carriers`).
CAPTURE_ONLY_REQUIRED = {"DEC": (DEC_WORK_FIELD,)}


def work_is_none(value) -> bool:
    """True where a decision's `work` is THE silence -- the scalar `none` and nothing else.

    ONE SILENCE, because `DEC-0083` (2)(c) names one: `work: none` says "this commits nobody", and a
    reader that also accepted `[]`, `""`, `[""]` or `"   "` would let a decision that DOES demand
    work silence the carrier line without ever saying so. Measured (verifier round 2, N-B2): all
    four passed the door and silenced the warning, and `[]` is exactly what a JSON body carries when
    the author does not have the ids yet -- the `DEC-0034` case, reopened.

    A LIST whose only entry is the word is NOT the silence either: `["none"]` is a list of ids, so
    its entry is resolved like any other and reported when no item carries it.
    """
    return isinstance(value, str) and value.strip() == DEC_WORK_NONE


def work_is_stated(value) -> bool:
    """True where a decision's `work` gives an ANSWER -- the one silence, or entries that name items.

    The two ends of `DEC-0083` (1) in one predicate, so the door (`kernel.cli`'s `capture` branch)
    and the validator (`report._check_decision_carriers`) cannot come to read the field differently.
    `tools/test_report.py::test_a_decision_nobody_carries_is_named_and_none_is_the_silence` drives
    every empty spelling through both.
    """
    return work_is_none(value) or names_something(value)


OPTIONAL_FIELDS = {
    "PR": ("user_story",),      # optional for class == technical_enabler
    "FR": ("related_pr",),
    # THE SYSTEM SIDE OF A BUG (FR-0054). `related_pr` is the product root a bug is filed under
    # and it stays mandatory; a bug in the software rather than in the product hits a SYSTEM
    # requirement, and until this field existed there was nowhere to say which. Optional, so no
    # stored item changes and no migration is forced -- and a parent binding
    # (`_BINDING_FIELD_NAMES`), which is what makes the system tree place the bug under the SR
    # instead of under the root, and what makes `report._check_bug_system_link` judge it.
    # `related_sr` (FR-0054) and the two fields a HOLE carries (FR-0087, DEC-0073). All three are
    # optional for one reason: an item already stored may not become a validator error the day a
    # field is added. `HOLE_NUMBER_FIELD` is what makes a defect a hole and is kernel-set
    # (`state.capture(hole=True)`); `HOLE_LIMIT_FIELD` is owed in `ACCEPTED_EXCEPTION` alone --
    # `STATUS_DEPENDENT_FIELDS` is where that duty lives, and the only place.
    "BUG": ("related_sr", HOLE_NUMBER_FIELD, HOLE_LIMIT_FIELD, HOLE_TEST_FIELD),
    "PROC": ("derives_from",),
    # `design_ref` required only when the UI scope has a frozen design; `seam_scope` is the
    # DECLARED SHARE (DEC-0062 (5), stream D requirement C-4): the paths this order knowingly
    # touches together with another, applied in the merge round. Optional because most orders
    # share nothing, and a required empty list would be a field every planner types to say
    # "nothing". `kernel.scopes` subtracts it before it judges a pair, and only where BOTH orders
    # of that pair declare it -- see `scopes.pair_seam` for why a one-sided declaration is not one.
    # `TSK_RUNG_FIELD` / `TSK_EFFORT_FIELD` are the PM's ask per order (DEC-0091 (1)); optional
    # because most orders take the ladder's own answer, and an ask is the exception the PM names.
    "TSK": ("design_ref", "seam_scope", TSK_RUNG_FIELD, TSK_EFFORT_FIELD),
    # OPTIONAL and not required, and the reason is the type: an `EVD` is immutable, so a field
    # made required here would turn every Evidence a project already holds into a validator error
    # with no command that could repair it. What that costs is counted where it is judged -- H108
    # in `docs/POST_V2_WISHLIST.md` -- and not a second time here. What the merge demands instead
    # is that a PASS carry the declaration -- `report._delivery_evidence` -- which an undeclared
    # record satisfies by being superseded, the one route an immutable type does have.
    # See RUN_SCOPES. `BLOCKED_REASON_FIELD` rides here for the same reason and one more: it is
    # required only for the ONE result value that owes it (`state.capture_preflight`), so making it
    # a required field of the type would demand it of every passing record too.
    "EVD": RUN_RECORD_FIELDS + (BLOCKED_REASON_FIELD,),
    # WHICH ITEMS A DECISION COMMITS SOMEBODY TO BUILD (FR-0012, decided as DEC-0083 option A).
    # `none` where it commits nobody -- a naming rule, a verdict -- or the ids of the items that
    # carry the work, resolved like every other binding. OPTIONAL for the reason every field added
    # to a stored type is optional here: a required field would turn ~80 stored decisions into
    # validator errors no command repairs. What makes it worth a field at all is the measured case:
    # DEC-0034 stood VALID for 26 days while nothing built it and no item pointed at it, and
    # `validate` had no line about a DEC except the supersedes shape (DEC-0080).
    "DEC": (DEC_WORK_FIELD,),
}

# Required fields for which an EMPTY value is the same lie as absence. A list-valued
# field is normally allowed to be empty -- a PR with no invariants has none -- so this
# is the exception, and it exists only where the emptiness would leave a gate deciding
# on nothing:
#   * `EVD.related` is the binding the merge gate resolves. Bound to nothing, the
#     record judges nothing; `report.qa_verdicts_by_subject` can only file it under its
#     own id, so it neither opens nor closes the merge it was recorded for.
#   * `EVD.artifact_refs` is the only field of an Evidence that points OUT of the
#     record. `result` is the claim and `summary` is prose about the claim, so with no
#     reference the record IS the assertion it exists to prove -- while `gate_git`
#     opens a merge on it and its own remedy text presents the reference as the proof.
#     What the kernel can check is that the verdict names where to look; whether the
#     artefact holds up is the auditor's job, and it cannot even start without a path.
#   * `TSK.expected_outputs` is what a verifier measures the package against. Against an
#     empty list every package is conformant, so the order asks for nothing and proves
#     nothing (BUG-0023). ONE entry here reaches both entrances -- `create-task` and
#     `capture TSK` end in `state.capture` -- and the validator names the stored items the
#     rule came too late for (`report._check_nonempty_fields`).
NONEMPTY_FIELDS = {"EVD": ("related", "artifact_refs"), "TSK": ("expected_outputs",)}


def names_something(value) -> bool:
    """True where a `NONEMPTY_FIELDS` value really names something -- the PROPERTY, not one spelling.

    THE CONTAINER WAS THE WRONG QUESTION, and asking it was the defect: `not value` refuses `[]`
    and accepts `[""]`, `[None]`, `["   "]` and `[[]]` -- every one of them an order that names
    nothing, and the first is reachable from the shipped command surface with one word
    (`--expected-output ""`, measured rc 0 with a DRAFT order created and the validator silent).
    What has to hold is what the refusal already SAYS: at least one ENTRY carries text -- a string
    that is not blank once stripped. A non-string entry names nothing here either: a list, a mapping
    or a number is neither a path, an artefact reference nor an item id.

    `field_elements` is the reader, so a field that arrived as a bare scalar counts as the one thing
    it is (BUG-0015) rather than as its letters -- and `capture EVD --related PR-0001` written into
    a body as a scalar stays legal.

    ONE function for both ends: `state.capture_preflight` refuses with it and
    `report._check_nonempty_fields` names stored items with it, so what a new item is refused for
    and what an old one is reported for cannot become two readings.
    `tools/test_state.py::test_a_work_order_that_expects_nothing_is_refused_at_both_entrances`
    drives every shape through both.
    """
    return any(isinstance(one, str) and one.strip() for one in field_elements(value))

# Fields whose value is a CALENDAR DATE and nothing else, per type. Declared rather than guessed
# from the name, and enforced in `state.capture_preflight` with `datetime.date.fromisoformat` --
# so what counts as a date is the standard library's answer, not a regular expression this kernel
# would have to keep.
# WHY IT IS CHECKED AT ALL (DEC-0064 (3)): a milestone's whole content is a name and a day, and a
# `due` nothing can read renders as "no date" -- a timeline entry that silently stops being one.
# Refusing at capture is the only moment anything can be done about it, because the item is
# practically immutable afterwards.
# Both ends are measured against the field contracts --
# `tools/test_backlog_types.py::test_every_declared_date_field_is_a_field_its_type_really_has`.
DATE_FIELDS = {"MST": ("due",)}


def normalised_date(value) -> str:
    """The stored form of a date field -- `date.fromisoformat` read back out as `YYYY-MM-DD`.

    ONE FUNCTION FOR BOTH JOBS, and that is why it exists rather than a bare `fromisoformat` at
    each call site: `state.capture_preflight` uses it to REFUSE what cannot be read, and
    `state.capture` uses the same call to STORE what was read. Without the second half the store
    keeps whatever spelling the caller typed, and `date.fromisoformat` accepts more than one --
    `20260903` on Python 3.11+ -- so two milestones of the same day sort against each other
    lexically and every reader that orders by `due` gets it wrong.

    WHAT IS STILL THE INTERPRETER'S, named because this function cannot make it ours: WHICH
    spellings are accepted is `datetime`'s answer and it has widened across versions (`20260903`
    is refused on 3.10 and read on 3.13), so a project can capture on one machine what another
    would refuse. That is `H147` in `docs/POST_V2_WISHLIST.md`, with the measurement. What this
    does fix is that whatever was accepted is stored in ONE form.
    Raises `ValueError` like `fromisoformat` does; the caller turns it into the refusal.
    """
    return date.fromisoformat(str(value)).isoformat()

# -- the backlog's own outline (FR-0017) ---------------------------------------
#
# WHAT THE FIELD IS. `area` is a path of names -- "Frontend/Login" -- and nothing else: it carries
# no text, no owner and no status, because an outline level that can hold content is a second
# place for a requirement to live. That was the FR's open design question, and the round decided
# it MEASURING rather than by taste: the alternative (a contentless HEADING item type) is a type
# in `ACTIVE_DIRS`, and a type there is a prefix in `guard_no_adhoc.ITEM_TYPES` in all three kits'
# hooks, a directory in all three template trees and a line in three constitutions -- measured by
# turning `test_hooks.test_no_adhoc_covers_every_item_type` red with a type that nothing else
# needed. An attribute costs one field and no file outside the kernel. The decision and its
# measurement are in the TSK-0106 protocol.
#
# ON EVERY CAPTURED TYPE, which is the definition rather than the pair the FR names ("both
# backlogs"): grouping is orthogonal to what an item IS, the two backlogs are two kits' root types
# plus what hangs under them, and a per-type list would have to be reopened for the next kit.
AREA_FIELD = "area"
AREA_SEPARATOR = "/"
# TWO LEVELS, which is the outline the FR describes (a document holds headings, a heading holds
# requirements) and at the same time the whole protection against a tree nobody can read: depth is
# refused at capture, so an outline cannot grow a third level by accident. The other half is at
# the moment the FR's own rule is about -- a new level is invented -- and it is a HINT rather than
# a count: `report.standing_areas`, printed by `cli` when a body names an area no item carries yet.
# No threshold anywhere, because "1000 headings" has no number that separates it from 999 honest
# ones; what separates them is whether the writer saw the outline they already had.
AREA_MAX_DEPTH = 2
# Every type `capture` creates may carry it. Read by `_contract_fields`, so it reaches the field
# contract, the validator's field duties and `schemas` through the one derivation they all use.
UNIVERSAL_OPTIONAL_FIELDS = (AREA_FIELD,)


def area_segments(value) -> list:
    """The outline levels a raw `area` value names -- [] when it names none.

    ONE READER for a shape three places ask about (capture's refusal, the validator's warning and
    anything that groups by it), because a second split is a second answer about what "Frontend/"
    means.
    """
    if isinstance(value, (list, tuple)):
        parts = [str(one) for one in value]
    elif value is None or value == "":
        return []
    else:
        parts = str(value).split(AREA_SEPARATOR)
    return [part.strip() for part in parts if str(part).strip()]

# -- the reference graph: through which field an item names what it belongs to --
#
# A field BINDS an item when its value is the ID of the item this one hangs from.
# WHICH FIELD NAMES do that is a decision about the state model and is made here,
# once, in `_BINDING_FIELD_NAMES`. WHICH TYPES carry one is NOT a second decision:
# it follows from the type's FIELD CONTRACT, so the map below is DERIVED rather
# than listed beside it.
#
# THE CONTRACT HAS TWO SOURCES AND THE DERIVATION READS BOTH IN FULL, because
# reading half of one of them is how this went wrong three times, one type
# further along each time:
#   * the CAPTURE-time contract, which covers exactly the types `capture`
#     creates. It is `REQUIRED_FIELDS` PLUS `OPTIONAL_FIELDS` -- a contract is
#     the set of fields a type HAS, and `REQUIRED_FIELDS` is by construction
#     only the fields an item may not omit.
#   * `kernel/schemas/*.yaml` is the contract of the types the kernel FREEZES
#     (ARC/WFR/DSN, spec II.6a) -- `schemas.item_field_contracts`, which reports
#     required and optional fields alike, for this same reason. Those items
#     never pass `capture`, so `REQUIRED_FIELDS` says nothing about them at all.
#
# Round one: `report._parents_of` enumerated the derived types (TSK/BUG/CR/HYP/
# EXP) and `SR` -- given a REQUIRED `derives_from` in this lockstep, and the
# natural subject of a review -- was not in the list, so an Evidence recorded
# against an `SR` resolved to no root and `gate_git` refused the merge with
# "nothing judges this work" at the role that had just judged exactly this work.
# Round two: the map was derived, but from `REQUIRED_FIELDS` alone, and `ARC`,
# `WFR` and `DSN` -- each of which declares its parent binding in its schema --
# reproduced the identical refusal for the architect and the designer. Reading
# both sources is what makes this a definition: a type joins the graph the day
# some contract of its own gives it a binding field. (Knowing the field was half
# of it for `WFR`/`DSN`: those are stored per revision, so their ids resolved to
# no file at all -- `state._frozen_revision_path` is the other half.)
# Round three: both sources were read, but the capture-time one only through
# `REQUIRED_FIELDS` -- so `PROC.derives_from` and `FR.related_pr`, optional by
# spec II.2 and item ids when present, were bindings the graph did not walk.
#
# `EVD.related` is in here for the same reason it is in `NONEMPTY_FIELDS`: it is
# the id of the work the record is ABOUT, which is the same hop the graph walks.
# `DSN.root` is the frozen design revision's binding to the PR/RQ it was frozen
# against (`staging.freeze_design`); the name is generic, the meaning is not.
_BINDING_FIELD_NAMES = ("product_requirement", "derives_from", "related_pr",
                        "target_pr", "related", "related_sr", "root")


def field_elements(value) -> list:
    """How many things one item field holds -- a string is ONE of them, never len(value).

    THE TUPLES ABOVE NAME FIELDS AND NOT THEIR SHAPES -- `REQUIRED_FIELDS`/`OPTIONAL_FIELDS` are
    the contract of the types `capture` creates, and they are names. (The other half of the field
    contract, `kernel/schemas/*.yaml` for the frozen ARC/WFR/DSN, DOES declare `type:` per field;
    `_contract_fields` below reads both. This function is about the capture-time half.) So every
    field that reads as a sequence can arrive as a bare scalar: `capture` takes it, `migrate`'s
    `--map` carries the V1 spelling over verbatim, and a hand-written YAML list with one entry and
    no `-` is the same file. A reader that iterates the value directly then reads a WORD as its
    letters.

    BUG-0015 is what that costs, and it is why this lives here rather than in each reader: the
    sweep that BUG asked for found the same assumption across unrelated reader CLASSES at once --
    a kit rendering script, a hook reading a work order, the dispatch gate resolving references,
    and the state validator. `report._parent_bindings` had carried the normalisation inline for
    the reference graph since long before, which is what made this a pattern rather than a single
    fix. The call sites are measured by
    `test_hooks.test_process_doc_renders_a_scalar_field_as_one_element`,
    `test_hooks_v2.test_a_scalar_scope_decides_like_a_one_element_list`,
    `test_approvals_dispatch.test_a_scalar_acceptance_ref_is_one_ref_not_four_letters`,
    `test_approvals_dispatch.test_a_scalar_dependency_is_one_dependency` and
    `test_report.test_a_scalar_dependency_is_reported_once_not_once_per_letter`.
    """
    if isinstance(value, (list, tuple)):
        return list(value)
    if value is None or value == "":
        return []
    return [value]


def _contract_fields() -> dict:
    """{item type -> set of field names its contracts declare}, over BOTH sources, in full."""
    from .schemas import item_field_contracts
    fields = {item_type: set(names) | set(UNIVERSAL_OPTIONAL_FIELDS)
              for item_type, names in REQUIRED_FIELDS.items()}
    for item_type, names in OPTIONAL_FIELDS.items():
        fields.setdefault(item_type, set()).update(names)
    for item_type, declared in item_field_contracts().items():
        fields.setdefault(item_type, set()).update(declared)
    return fields


def _declared_required_fields() -> dict:
    """{item type -> the fields SOME contract of its own requires}, over both sources.

    `REQUIRED_FIELDS` is what a CALLER must hand `capture`; this is what an item must CARRY, and
    the two differ exactly for the types no caller captures. The state validator judges files, not
    capture calls, so it reads this: its field-duty loop ran zero times for `ARC`, `WFR` and `DSN`
    -- the three types whose duties are declared in `kernel/schemas/` -- while spec II.8 assigns
    it "ARC ohne derives_from -> Validator-Flag" by name.
    """
    from .schemas import item_required_fields
    required = {item_type: tuple(names) for item_type, names in REQUIRED_FIELDS.items()}
    for item_type, names in item_required_fields().items():
        required[item_type] = tuple(dict.fromkeys(required.get(item_type, ()) + tuple(names)))
    return required


def _parent_fields() -> dict:
    return {
        item_type: tuple(f for f in _BINDING_FIELD_NAMES if f in fields)
        for item_type, fields in sorted(_contract_fields().items())
        if not fields.isdisjoint(_BINDING_FIELD_NAMES)
    }


# -- which types AMEND another item's contract (BUG-0040) ----------------------
#
# An amendment is a delta on ONE REVISION of another item's contract, and that is
# what this field name means: the revision of the target the delta was written
# against. It is the property that decides whose contract the amendment's
# `acceptance_criteria` belong to -- they extend the TARGET's criteria, which is
# why an approved amendment widens the universe the dispatch gate resolves
# `acceptance_refs` in (`dispatch._known_acceptance_ids_locked`).
#
# A BUG is the counter-example that makes this a property rather than a synonym
# for "CR": it binds to a root through `related_pr` and carries its own
# `acceptance_criteria`, but names NO revision of that root -- its Fix-Kriterien
# are criteria of the bug, not of the root's contract, so they reach a task
# through `derives_from` and never through this derivation.
#
# DERIVED from the field contracts for the reason `PARENT_FIELDS` is: a type joins
# the day some contract of its own gives it the field. Both ends are measured by
# `test_backlog_types.test_an_amendment_is_the_type_that_names_the_revision_it_amends`.
#
# ONLY THE FIELD'S NAME IS READ, NEVER ITS VALUE, and that is the honest limit of
# this constant: it discriminates the TYPE, and no reader compares the recorded
# revision with the root's current one. So an amendment written against revision 1
# keeps widening after the root has moved on -- measured 2026-08-15 with a root
# re-approved at revision 2 whose criteria had been replaced.
#
# WHY THE EQUALITY TERM STAYS OUT, re-measured against the pilot store rather than
# assumed -- an earlier version of this paragraph claimed it would have refused the
# BUG-0040 chain, and that was false. Under a root at revision 2, the five change
# requests carrying that chain all sit at target_revision 2: an equality term would
# have PASSED every one of them. The one it would have dropped is the SIXTH, written
# against revision 3 -- a later, still planned revision of the same root, approved by
# the user in that form. That shape is the reason: an amendment may legitimately be
# signed for a revision the root has not reached yet, so an equality term would
# refuse real, user-approved work rather than catch a mistake.
AMENDMENT_REVISION_FIELD = "target_revision"


def _amendment_types() -> frozenset:
    return frozenset(item_type for item_type, fields in _declared_required_fields().items()
                     if AMENDMENT_REVISION_FIELD in fields)


# `PARENT_FIELDS` (the reference graph) and `DECLARED_REQUIRED_FIELDS` (what the state VALIDATOR
# holds a stored item to -- see `_declared_required_fields`) are DERIVED, and both derivations
# read `kernel/schemas/*.yaml`, which needs PyYAML. Computing them at module scope would make
# `import kernel.backlog_types` a PyYAML import and six file reads, and that import is the one
# path a hook can take to learn the type names without pulling the parser in:
# `guard_no_adhoc` keeps its type list as a LITERAL for exactly that reason ("a guard that cannot
# load must not stop guarding"), and spec II.7 says integrity gates are stdlib-first with no
# PyYAML import load on the hot path. So the values are computed on FIRST ACCESS instead. The
# consumers inside the kernel (`state`, `report`) bind them with a normal `from ... import` and
# pay the cost once at their own import, where PyYAML is already loaded anyway.
_DERIVED = {"PARENT_FIELDS": _parent_fields, "DECLARED_REQUIRED_FIELDS": _declared_required_fields,
            "AMENDMENT_TYPES": _amendment_types}
_derived_cache: dict = {}


def __getattr__(name: str):
    """Module-level lazy attributes (PEP 562) -- also serves `from .backlog_types import X`."""
    if name in _DERIVED:
        if name not in _derived_cache:
            _derived_cache[name] = _DERIVED[name]()
        return _derived_cache[name]
    raise AttributeError("module %r has no attribute %r" % (__name__, name))


def __dir__():
    return sorted(list(globals()) + list(_DERIVED))

# Fields whose change INVALIDATES a current approval (spec II.2 subject
# manifests + Freigabe-Invalidierung): revision +1, approval_ref cleared,
# status -> INVALIDATION_TARGET -- atomically, in the kernel edit path.
# Implementation notes: `design_refs` (PR/RQ) is the item field carrying the
# scope manifest's "verbindliche Designreferenzen" (frozen WFR/DSN refs);
# PROC hashes `roles` IN ADDITION to the V1 steps-only hash -- a role change
# is approval-relevant (additive hardening over V1).
HASHED_FIELDS = {
    "PR": ("problem", "goal", "acceptance_criteria", "invariants",
           "out_of_scope", "design_refs"),
    "RQ": ("question", "motivation", "acceptance_criteria", "out_of_scope",
           "design_refs"),
    "CR": ("target_pr", "target_revision", "change_description",
           "acceptance_criteria"),
    "BUG": ("observed", "expected", "repro", "severity", "acceptance_criteria"),
    "SR": ("derives_from", "contract", "affected_components"),
    "PROC": ("steps", "roles"),
    "EXP": ("design", "variables", "success_criteria"),
}


# -- TSK.type vocabulary -------------------------------------------------------

# The spec names TSK.type as a required field without fixing its values. Left
# free-form it is unusable as a GATE input: the design_ref rule (II.6 "UI-Tasks
# bei vorhandenem bestaetigtem Design ohne design_ref gesperrt") has to decide
# "is this a UI task", and matching a free-text field against a sample list
# fails OPEN on every synonym the orchestrator invents ("ui-implementation",
# "frontend-work", ...). So the vocabulary is CLOSED here and validated at
# capture: an unknown type is refused early and visibly, instead of quietly
# skipping a gate later. Widening the list is a spec decision, not a guess at
# call time.
TASK_TYPES = frozenset((
    "analysis",         # read-only investigation (rides an APR.kind: analysis)
    "design",           # WFR/DSN authoring
    "architecture",     # ARC authoring
    "implementation",   # non-UI production code
    "bugfix",           # BUG is a first-class root type (II.2) and its fix work
                        # is not "implementation" of a new requirement
    "ui",               # user-facing surface -- the design_ref-bearing type
    "test",             # QA/regression work
    "review",           # audit/review pass
    "docs",
    "ops",              # devops/pipeline/release work
    "research",         # research-kit execution work
))

# The subset for which a confirmed design makes design_ref mandatory (II.6).
UI_TASK_TYPES = frozenset(("ui",))


# -- FR terminal outcomes: which of them point to a RESULT item (BUG-0009) -----
#
# A triaged feature request ends in one of three terminals, and the split that decides whether the
# STATE keeps a link is whether the outcome LEFT A TRACE in another item. CONVERTED (the request
# became a PR/RQ) and MERGED (it was folded into another request) both do -- the FR automaton's own
# `terminal_from` comment reads "a triage OUTCOME", and the V1 mapping row for `FR ACCEPTED` reads
# "becomes a PRD"; WHICH item it became was nowhere in the state, which is the defect BUG-0009
# records. REJECTED points to nothing: a discarded request has no result to name.
#
# The two sets are written out because no property of the automaton tells them apart -- it is a fact
# about what each OUTCOME MEANS -- but they are pinned to it from BOTH ends
# (`test_backlog_types.test_the_fr_result_terminals_partition_the_fr_automaton`): every value here is
# a real FR terminal, and together they cover every FR terminal, so a fourth terminal added to the
# automaton fails the test until it is placed on one side. `FR_RESULT_FIELD` is the field the first
# two owe -- a status-dependent duty the validator enforces, not a capture field, like `triage_result`.
FR_RESULT_TERMINALS = frozenset(("CONVERTED", "MERGED"))
FR_DISCARD_TERMINALS = frozenset(("REJECTED",))
FR_RESULT_FIELD = "resulting_item"

# -- the INBOX property (BUG-0091, DEC-0066) -----------------------------------
#
# {type: (the terminals that leave a result, the field that names it)} -- the types whose lifecycle
# can end by naming the item they BECAME. That is what "inbox" means as a property rather than as a
# type name: such an item is not a thing the project builds, it is a thing waiting for the triage
# that turns it into one, and the item it turns into is what work hangs from.
#
# WHY IT IS A CONTRACT AND NOT A DERIVATION: no shape of an automaton tells a triage outcome from
# any other terminal -- it is a fact about what the outcome MEANS, which is the same argument
# `FR_RESULT_TERMINALS` above and `SINGLE_VALUE_FIELDS` below already carry. What is derived is
# everything downstream: `report._check_fr_result_link` takes the duty from here, and
# `dispatch._assert_the_origins_are_not_inbox_items` takes the refusal from here, so a type added
# to this map arrives with both and neither is a second list.
#
# THE DEFECT (BUG-0091, measured 2026-09-03, re-measured on 75a00d1): `create-task` accepted an FR
# as `product_requirement` and as `derives_from` without a word -- 21 of 120 work orders in this
# repository hang from one. What that produced is a DEAD END rather than a difference of taste:
# `FR` is in no row of `approvals.APPROVAL_TRANSITIONS`, so no scope approval exists for it at all
# (`create_pending_request` refuses: "this type carries no user approval"), and `create_lease` then
# refuses the task with "no user approval authorises dispatching". A task under a wish is
# undispatchable BY CONSTRUCTION, and its fields are frozen outside DRAFT -- the same class as the
# cross-root origin `dispatch._assert_origins_belong_to_root_locked` refuses at creation.
# `tools/test_backlog_types.py::test_the_inbox_types_are_the_ones_whose_triage_names_a_result`
TRIAGE_RESULT_LINK = {"FR": (FR_RESULT_TERMINALS, FR_RESULT_FIELD)}


def is_inbox_type(item_type: str) -> bool:
    """Does this type's lifecycle end by naming the item it BECAME? -- see `TRIAGE_RESULT_LINK`."""
    return item_type in TRIAGE_RESULT_LINK

# -- DEC supersession: the one lifecycle link a decision has (BUG-0009) --------
#
# A DEC carries no automaton and no future; the single relation its life HAS is that a newer decision
# can replace an older one. Before this that relation lived only as prose in `context`, so "which
# decisions still hold" could not be answered from the state. `DEC_SUPERSEDES_FIELD` makes it a
# FORWARD link on the NEWER decision -- one source of truth, DERIVED into "which are superseded"
# (`report.standing_decisions`) rather than double-stored as a back-pointer that could drift.
# Optional by construction (a decision that replaces nothing carries none), so every DEC captured
# before this stays valid; the validator only checks that a link, WHEN present, names a real DEC.
DEC_SUPERSEDES_FIELD = "supersedes"


# -- the item fields NO capture contract declares, whose ELEMENTS the kernel resolves -----------
#
# THE BOUNDARY THIS CROSSES. `REQUIRED_FIELDS` and `OPTIONAL_FIELDS` are the contract of what a
# CALLER hands `capture`, and `migrate.parse_field_map` derives the whole `--map` surface from that
# union. But the state has a SECOND author -- the kernel itself (`staging.freeze_design`) -- and a
# second way in, because `capture` takes a body's extra keys unchanged. A field that arrives either
# way is declared in neither tuple, so a sweep whose field set comes from the capture contract
# cannot see it at all. BUG-0038 is what that cost: a scalar `design_refs` was letter-split by
# `freeze_design` INTO THE CANONICAL ITEM, and the state validator reported nothing.
#
# WHAT PUTS A FIELD IN HERE is one property: the kernel resolves its ELEMENTS -- each is an item id
# or a state-relative path to a frozen revision -- so an element is something that has to exist
# somewhere, which is why these are read through `field_elements` and why `report.validate_state`
# resolves their entries one by one.
#
# AN ENUMERATION, WITH BOTH ENDS MEASURED, because nothing in the running code names these three on
# its own. `test_backlog_types.test_the_reference_list_fields_are_what_the_kernel_reads_elementwise`
# derives the set from the kernel's own sources -- every sequence-context read off a value bound
# from an item source -- and compares it BOTH ways, so a name that no longer occurs and a field
# nobody declared each turn it red;
# `test_backlog_types.test_every_kernel_read_of_a_reference_list_field_goes_through_field_elements`
# then holds every derived read site to the one definition. What that derivation cannot see is
# named in its own docstring rather than promised away here.
REFERENCE_LIST_FIELDS = ("design_refs", "architecture_refs", DEC_SUPERSEDES_FIELD,
                         "premise_rechecks")


# -- the item fields that hold exactly ONE thing, by contract -------------------------------------
#
# THE OTHER DIRECTION OF THE SAME PROBLEM `field_elements` ANSWERS, and the answer here is a
# DECISION rather than a normalisation (DEC-0043). `REQUIRED_FIELDS` names fields and not shapes,
# so every field can also arrive as a list -- and where a field's readers each read ONE value, the
# list spelling is not "several", it is a value that reaches nobody: it arrives as the text
# `"['a']"` and matches nothing. H42 is what that cost. Normalising it the other way
# (`field_elements` at the readers) would mean one INV governs SEVERAL areas, which is the branch
# the user rejected -- for `kit_checks.invariant_knob` a `scope` is the NAME of a configuration
# knob, where "several names" means nothing at all.
#
# WHAT PUTS A FIELD IN HERE: every shipped reader of it reads ONE value, so the field's contract is
# that it HOLDS one. The consequence is `state.capture_preflight`/`_update_item_locked` refusing the
# several-things spelling on the way into the ACTIVE store, and `report._check_single_value_fields`
# naming an item already written that way.
#
# AN ENUMERATION -- a contract is decided, not derived -- SO BOTH ENDS ARE MEASURED:
# `test_backlog_types.test_the_single_value_fields_are_contract_fields_nothing_resolves_elementwise`
# is the end where the entry has gone dead (the field left its type's contract, or turned into one
# whose elements the kernel resolves), and
# `test_hooks.test_the_shipped_readers_of_a_single_value_field_still_read_one_value` is the end
# where it was never needed (the readers learned to read several, at which point the contract is
# DEC-0043's to re-decide and not this tuple's to keep).
SINGLE_VALUE_FIELDS = {
    ("INV", "scope"): (
        "every shipped reader reads it as ONE path or ONE knob name",
        "one area per rule -- an invariant meant to govern two areas is TWO INV items, one each",
    ),
}


def holds_one_thing(value) -> bool:
    """Is this value ONE thing a reader of such a field can read? -- asked as a property, so no
    spelling of "several" gets past it.

    ITERABLE IS SEVERAL, and the single exception is the string: it is the one iterable whose
    printed form IS its value, which is what every reader of a `SINGLE_VALUE_FIELDS` field does with
    it. That is the reading `field_elements` gives a value, seen from the other side, and it is why
    a `dict` and a one-element list are refused too -- what those readers cannot do is take a
    container apart, so `['a']` reaches them as `"['a']"` exactly like `['a', 'b']` does.

    `bytes` IS NOT THE STRING'S TWIN HERE, and it was exempted with it for one round. Measured
    2026-08-14 through the shipped edit path: a `bytes` scope was taken, all three readers saw
    `b'api/'`, `gate_test_coverage` went from rc 2 to rc 0 and -- unlike the list spelling -- the
    validator stayed silent, so no merge gate caught it either. Nothing about the exemption was
    earned: no reader of such a field has a byte meaning, and its printed form carries a wrapper
    the value never had. `test_state.test_a_several_things_inv_scope_is_refused_at_capture_and_on
    _the_edit_path` carries the case.
    """
    return isinstance(value, str) or not isinstance(value, Iterable)


def single_value_offences(item_type: str, fields: dict) -> list:
    """[(field, why, remedy)] for every `SINGLE_VALUE_FIELDS` field of `item_type` that `fields`
    spells as several things -- the ONE reading, so the write path's refusal and the validator's
    finding can never disagree about what the contract is."""
    return [(field, why, remedy)
            for (owner, field), (why, remedy) in sorted(SINGLE_VALUE_FIELDS.items())
            if owner == item_type and field in fields and not holds_one_thing(fields[field])]


# -- Evidence contract (spec II.2 "Evidence") ----------------------------------

# Evidence carries no project STATUS, and that is exactly why it has to carry a
# VERDICT: it is the only item type whose whole purpose is to say whether
# something held. `gate_git` opens a merge on it, so both fields below are gate
# inputs and both are CLOSED for the same reason TASK_TYPES is -- an unrecognised
# value does not fail a check, it SKIPS one. An unknown `result` is not a `fail`
# and an unknown `kind` is not QA, so in either direction the gate would go quiet
# on precisely the value nobody validated. Widening either set is a spec
# decision, not a guess at call time.
EVIDENCE_KINDS = frozenset(("test", "review", "acceptance", "audit"))

# The kinds that judge the PROJECT rather than one delivery. `audit` is the whole
# list and the reason is specific to it: an audit run judges the repo-wide scope
# (II.10a Auditor-Routine: one Evidence per run, related to that scope), so
# accepting it as a delivery's QA would open a merge on a report that never looked
# at the branch.
PROJECT_EVIDENCE_KINDS = frozenset(("audit",))

# The kinds a merge of an item may rest on -- DERIVED, and that is the point. Two
# hand-written lists of the same words drift in one direction only: a kind added to
# EVIDENCE_KINDS and forgotten here would become a verdict the merge gate never
# reads, i.e. a role recording it in good faith while the gate reports "no QA
# Evidence". Subtracting the declared exception makes a new kind judge deliveries by
# DEFAULT, which is the reading a reviewer can check against the one sentence above.
QA_EVIDENCE_KINDS = EVIDENCE_KINDS - PROJECT_EVIDENCE_KINDS

# ONE VALUE OPENS A MERGE AND EVERY OTHER ONE CLOSES IT. That asymmetry is what lets this
# vocabulary grow without a second list to keep in step: `report._newest_per_kind` hands the gates
# the current verdict per kind and `gate_git` refuses everything that is not `PASSING_RESULT`, so a
# value added here arrives CLOSING. Measured over the readers rather than asserted:
# `tools/test_backlog_types.py::test_only_the_passing_result_opens_anything_the_kernel_decides`.
PASSING_RESULT = "pass"
# "inconclusive" stays refused, for the reason it always was: a gate cannot act on it -- it would
# have to be read as pass or as fail, and whichever was chosen the other reading would be the
# silent one.
# `blocked` is a different case, and it is why this set is no longer two-valued (FR-0082, wishlist
# section 7). A run that never HAPPENED -- no browser, no device, no network -- had to be booked as
# `fail`, and afterwards the store held a red verdict that nobody could tell from a real one. The
# gate does not have to guess: `blocked` closes exactly as `fail` closes; what it changes is what a
# later reader is told.
# WHAT IT IS NOT, and this sentence is part of the feature rather than a caveat beside it: nobody
# measures whether the browser was really missing. The value turns an honesty duty into a state and
# adds nothing to the question "is this true". That is why the kernel demands the sentence beside
# the word (`BLOCKED_REASON_FIELD`, enforced in `state.capture_preflight`) and why every surface
# that reports such a verdict says that nothing was checked -- otherwise the next reader takes a
# `blocked` for a checked fact, which is the one failure mode the wishlist section names.
EVIDENCE_RESULTS = frozenset((PASSING_RESULT, "fail", BLOCKED_RESULT))


# Types that are a RECORD of something that already happened rather than a piece of
# living state. What separates them from every other type is that they have no
# automaton and no future: an item with a status is a thing whose story continues, so
# editing a detail of it is part of that story, while a record's only claim is that a
# run produced this verdict at this time. Change any field of it and the claim is
# simply false -- there is no revision, no approval to invalidate, nothing that would
# make the change visible. So the kernel refuses the edit outright (state.py edit path)
# and a superseding record is the only way forward. This is what lets `gate_git` say
# "retired by recording the re-run, never by editing" and mean it: without the refusal
# a FAIL becomes a PASS in place, with no new item and no trace in the store.
IMMUTABLE_TYPES = frozenset(("EVD",))

# The work-order contract of a TSK: everything a gate reads to decide what this
# task may do. FROZEN once the task leaves DRAFT (enforced in the kernel edit
# path), because these fields are gate INPUTS and a task past DRAFT is either
# queued, leased or being worked by a live specialist:
#   * `allowed_scope`/`forbidden_scope` are gate layer 3's only inputs -- widening
#     them on a LEASED, BOUND task hands a running specialist the whole repo,
#     with no approval and no revision bump,
#   * `type` decides whether the design_ref rule applies (II.6),
#   * `assigned_role` is what the dispatch gate matches the spawn against,
#   * `acceptance_refs`/`dependencies` are what makes the task checkable at all.
# Re-planning is legitimate -- it just has to be VISIBLE: bring the task back to
# DRAFT (or cancel and re-create it), which is a status transition through the
# automaton rather than a quiet field write.
TSK_PLAN_FIELDS = frozenset((
    "product_requirement", "root_revision", "derives_from", "type", "assigned_role",
    "acceptance_refs", "required_inputs", "allowed_scope", "forbidden_scope",
    "expected_outputs", "dependencies",
    # `seam_scope` for the same reason the two scope fields are here and one step further: it is
    # what the pre-dispatch check SUBTRACTS from a pair's overlap (`kernel.scopes`), so a seam
    # added to a LEASED order re-decides a cut that has already been handed out. Declaring one
    # later is legitimate -- it just has to be visible, like every other re-planning.
    "seam_scope",
    # The tier ask for the same reason one step further still: it is an input of the rung the
    # dispatcher derives at the lease, and DEC-0091 (1) says "changeable while DRAFT" -- which is
    # exactly the freeze this tuple carries, so the rule needs no second mechanism.
    TSK_RUNG_FIELD, TSK_EFFORT_FIELD,
))


# -- V1 -> V2 status mapping (spec II.10; machine-readable, never guess) -------

# WHERE AN IMPORTED ITEM KEEPS ITS PAST, named here rather than in `migrate` because TWO modules
# have to agree on it: `migrate` composes the block, and `state.capture_migrated_archive` refuses a
# body that carries none and stamps its own two facts into it (which required fields were absent,
# and which kit version the record came from -- SR-0002). A constant in `migrate` would have made
# the kernel import the caller it is called by.
LEGACY_FIELD = "legacy_fields"
# WHAT THE MARK SAYS, AND WHY IT NO LONGER SAYS MORE (DEC-0021). It was
# `migration_confirmation_required`, and that name promised a duty: something
# somewhere would demand a human confirmation before the item counted. Nothing
# does -- no reader in this kernel, in the hooks, in the session brief or in the
# dashboard asks for it, and the spec promises none either. Two review rounds
# measured that independently. The bolt that IS read is `approval_ref`, so a
# second one beside it would be two answers to one question, which is the drift
# class this repo has measured on itself. The mark therefore states its subject
# and nothing else: this item's content came out of a V1 store rather than out
# of a session. `test_migrate.test_the_import_mark_says_where_an_item_came_from
# _and_claims_no_lever` is where the seam between the name and the behaviour
# under it is measured.
IMPORT_MARK = "imported_from_v1"

# WHAT THE THIRD COLUMN MEANS, stated ONCE for every row rather than argued per row -- and it is
# stated here because without it the column is a list of individual calls, which is what it had
# become: `("TSK", "DONE")` carried fifteen lines of argument and `("EXP", "DONE")` -- the last box
# of the other shipped chain -- carried none, so no reader could tell which of the two was the rule.
#
#     `archive_candidate` is True exactly when the V1 value is where THE V1 RECORD'S LIFE ENDED,
#     as the V1 kit itself recorded it: the shipped template's own status chain does not leave it.
#
# It is a fact about the V1 VOCABULARY and about nothing else. In particular it is NOT "the mapped
# V2 status is a terminal of the V2 automaton" -- that is a property of a live V2 item and says
# nothing about a 2025 record, and reading it that way is the defect SR-0004 was written against
# (a V1 `TSK DONE` landing in `tasks/active/` as a fresh work order). And it is not a routing
# decision either: WHERE a record goes is `state.migration_archive_status`, which asks this column
# AND the approval bolt, so a row may say "this life is over" and the record still land in active/
# because the import may not write that status. `legacy_fields.archive_candidate` and
# `legacy_fields.written_to` are the two answers, kept apart in the item on purpose.
#
# WHERE A ROW DEPARTS FROM THAT READING it is recorded in `ARCHIVE_CANDIDATE_DEVIATIONS` below with
# its reason, and `test_migrate.test_every_archive_candidate_row_follows_the_v1_chain_or_is_recorded`
# derives the departures from the kits' own shipped chains in git history -- so a flag flipped here
# without a reason turns that test red, and a reason left behind for a row that no longer departs
# turns it red from the other side.
V1_STATUS_MAPPING = {
    # (v1_type, v1_status) -> (v2_type, v2_status, archive_candidate)
    # The spec's II.10 table lists only the NON-identity rows; the identity
    # rows below (TSK IN_PROGRESS/DONE/VALIDATED, PRD APPROVED/ACCEPTED,
    # PROC APPROVED/ACTIVE/RETIRED) are an ADDITIVE completion covering the
    # V1 vocabulary actually measured in the 2026-07-24 review (report par. 4) --
    # without them every plain DONE import would block.
    ("TSK", "TODO"): ("TSK", "READY", False),
    ("TSK", "IN_PROGRESS"): ("TSK", "IN_PROGRESS", False),
    # ARCHIVE-BOUND AT `DONE` (user decision 2026-08-04), and this is a recorded DEPARTURE from the
    # chain rule above -- `DONE` is mid-chain in the shipped `tasks.yaml`; see
    # `ARCHIVE_CANDIDATE_DEVIATIONS` for the reason and for what the field data says.
    # WHAT IT MAY NOT SAY, which is the other half of the same decision: `VALIDATED` would be the V2
    # terminal, and it is the one value this row may not carry. In V2 `DONE` means the work is
    # finished and `VALIDATED` means QA confirmed it; V1 collected no such confirmation, so mapping
    # on to it would be the import inventing a statement about quality that nobody ever made.
    ("TSK", "DONE"): ("TSK", "DONE", True),
    ("TSK", "VALIDATED"): ("TSK", "VALIDATED", True),
    # V1 REJECTED is a task QA turned down -- a work order that ended without being delivered.
    # V2's `FAILED` is NOT that: it is a live retry state a task comes back out of. `CANCELLED` is
    # the terminal that means "this work order was not delivered", so that is the row.
    ("TSK", "REJECTED"): ("TSK", "CANCELLED", True),
    ("PRD", "PROPOSED"): ("PR", "DRAFT", False),
    ("PRD", "APPROVED"): ("PR", "APPROVED", False),
    ("PRD", "TESTED"): ("PR", "DELIVERED", False),
    ("PRD", "ACCEPTED"): ("PR", "ACCEPTED", True),
    ("PRD", "DONE"): ("PR", "ACCEPTED", True),
    ("PRD", "REJECTED"): ("PR", "REJECTED", True),
    ("SR", "DRAFT"): ("SR", "PROPOSED", False),
    ("SR", "ACTIVE"): ("SR", "ACCEPTED", False),
    ("SR", "DONE"): ("SR", "ACCEPTED", True),
    ("PROC", "PROPOSED"): ("PROC", "DRAFT", False),
    ("PROC", "APPROVED"): ("PROC", "APPROVED", False),
    ("PROC", "ACTIVE"): ("PROC", "ACTIVE", False),
    ("PROC", "RETIRED"): ("PROC", "RETIRED", True),
    # -- THE BACKLOG TYPES THE TABLE DID NOT COVER, added 2026-08-04 ---------------------------
    # Every value below is READ OFF THE V1 TEMPLATE that shipped it -- the `Status: ...` chain in
    # the header comment of each kit's own `templates/project_memory/*.yaml`, at the last commit
    # that carried them -- and never invented. `test_migrate` derives the same pairs from that
    # same history and fails on any this table is missing, so the coverage claim is measured
    # rather than asserted. Without these rows the migration reported a V1 `bugs.yaml`,
    # `change_requests.yaml`, `feature_requests.yaml`, `research_questions.yaml`,
    # `hypotheses.yaml` and `experiment_designs.yaml` as "not a backlog type" and exited 0, which
    # is a false all-clear over most of the dev and research stores.
    #
    # WHERE A V1 VALUE HAS NO V2 COUNTERPART the row records the closest state on the V2
    # automaton and says so here; nothing is lost, because an imported item arrives at its
    # INITIAL status and the V1 original is kept in `legacy_fields` (spec II.10). The mapped
    # value is a NOTE about what V1 meant, not a position the kernel walks to.
    # bugs.yaml: OPEN -> IN_PROGRESS -> FIXED -> VERIFIED / WONTFIX / DUPLICATE
    ("BUG", "OPEN"): ("BUG", "OPEN", False),
    ("BUG", "IN_PROGRESS"): ("BUG", "APPROVED", False),   # V2 has no IN_PROGRESS: work sanctioned
    ("BUG", "FIXED"): ("BUG", "FIXED", False),
    ("BUG", "VERIFIED"): ("BUG", "VERIFIED", True),
    ("BUG", "WONTFIX"): ("BUG", "REJECTED", True),
    ("BUG", "DUPLICATE"): ("BUG", "DUPLICATE", True),
    # change_requests.yaml: PROPOSED -> WAITING_APPROVAL -> APPROVED -> APPLIED / REJECTED
    ("CR", "PROPOSED"): ("CR", "DRAFT", False),
    ("CR", "WAITING_APPROVAL"): ("CR", "DRAFT", False),   # V2 has no waiting state: still a draft
    ("CR", "APPROVED"): ("CR", "APPROVED", False),
    ("CR", "APPLIED"): ("CR", "APPLIED", True),
    ("CR", "REJECTED"): ("CR", "REJECTED", True),
    # research protocol_amendments.yaml ships the SAME chain under its own `PA-` prefix
    ("PA", "PROPOSED"): ("CR", "DRAFT", False),
    ("PA", "WAITING_APPROVAL"): ("CR", "DRAFT", False),
    ("PA", "APPROVED"): ("CR", "APPROVED", False),
    ("PA", "APPLIED"): ("CR", "APPLIED", True),
    ("PA", "REJECTED"): ("CR", "REJECTED", True),
    # feature_requests.yaml: PROPOSED -> TRIAGED -> ACCEPTED (-> becomes a PRD) / REJECTED /
    # DEFERRED. "becomes a PRD" is exactly what V2 calls CONVERTED.
    ("FR", "PROPOSED"): ("FR", "OPEN", False),
    ("FR", "TRIAGED"): ("FR", "TRIAGED", False),
    ("FR", "ACCEPTED"): ("FR", "CONVERTED", True),
    ("FR", "REJECTED"): ("FR", "REJECTED", True),
    ("FR", "DEFERRED"): ("FR", "TRIAGED", False),         # triaged and parked; V2 has no DEFERRED
    # research_questions.yaml: PROPOSED -> APPROVED -> INVESTIGATED -> VALIDATED -> ACCEPTED /
    # REJECTED. RQ runs the PR-like automaton, so the middle two land on its delivery states.
    ("RQ", "PROPOSED"): ("RQ", "DRAFT", False),
    ("RQ", "APPROVED"): ("RQ", "APPROVED", False),
    ("RQ", "INVESTIGATED"): ("RQ", "IN_DELIVERY", False),
    ("RQ", "VALIDATED"): ("RQ", "DELIVERED", False),
    ("RQ", "ACCEPTED"): ("RQ", "ACCEPTED", True),
    ("RQ", "REJECTED"): ("RQ", "REJECTED", True),
    # ...and the research kit ships a SECOND store under the `RQ-` prefix: `fzulg_documentation.yaml`
    # keys the BSFZ application layer by the research question it documents, with its own two-state
    # chain (DRAFT -> READY, "ready for the application"). Those values describe the FORM, not the
    # question's own life, so neither of them moves the RQ anywhere: an imported item arrives at its
    # initial status regardless, and the V1 value is kept in `legacy_fields`. Without these rows a
    # research project that filled that file could not be migrated at all -- `RQ` has rows, so an
    # unknown `RQ` status blocks the whole run.
    ("RQ", "DRAFT"): ("RQ", "DRAFT", False),
    ("RQ", "READY"): ("RQ", "DRAFT", False),
    # hypotheses.yaml: DRAFT -> ACTIVE -> SUPPORTED / REFUTED
    ("HYP", "DRAFT"): ("HYP", "PROPOSED", False),
    ("HYP", "ACTIVE"): ("HYP", "TESTING", False),
    ("HYP", "SUPPORTED"): ("HYP", "SUPPORTED", True),
    ("HYP", "REFUTED"): ("HYP", "REFUTED", True),
    # experiment_designs.yaml: DRAFT -> ACTIVE -> DONE
    ("EXP", "DRAFT"): ("EXP", "DESIGNED", False),
    ("EXP", "ACTIVE"): ("EXP", "RUNNING", False),
    # ARCHIVE-BOUND BY THE RULE, not by a second decision: `DONE` is the last box of the shipped
    # `experiment_designs.yaml` chain, exactly as `RETIRED` is for a procedure. It stood at False
    # while `TSK DONE` -- the last box of the OTHER shipped chain -- stood at True, and nothing said
    # why; that asymmetry is what made this column read as a list of calls.
    # THE RECORD STILL LANDS IN active/, and by the OTHER bolt rather than by this flag: `COMPLETED`
    # sits behind `EXP` DESIGNED->APPROVED, which `approvals.APPROVAL_TRANSITIONS` marks as an edge
    # a user approval commits, so `state.migration_archive_status` refuses to write it. The item
    # then carries `archive_candidate: true` beside `written_to: active`, which is the two answers
    # staying apart rather than one of them being bent to produce the other.
    ("EXP", "DONE"): ("EXP", "COMPLETED", True),
    # decisions.yaml: PROPOSED -> ACCEPTED -> SUPERSEDED, shipped by dev under the `ADR-` prefix
    # and by research under `MDR-` with the identical status chain and the identical four content
    # fields. They are ONE row set under two prefixes because the two templates are the same
    # schema, not because somebody listed two spellings.
    #
    # WHY THEY ARE ITEMS AND NOT CARRIED DOCUMENTS (DEC-0002, user decision 2026-08-04): the
    # alternative was to leave 106 measured records in V1 form beside V2 `DEC` items -- two forms
    # for one thing, permanently. `decisions.yaml` is a backlog store with ids, a status and a
    # lifecycle, exactly like `tasks.yaml`, and `title`/`context`/`decision`/`consequences` are
    # spelled the same in `REQUIRED_FIELDS["DEC"]`, so nothing has to be guessed to carry them.
    #
    # `SUPERSEDED` CARRIES THE FLAG BY THE RULE -- it is the last box of the shipped
    # `decisions.yaml` chain -- AND THE RECORD STILL ARRIVES IN active/, for a reason that is about
    # the writer and not about the V1 value: `DEC` has no automaton, so
    # `state.migration_writable_statuses("DEC")` is empty and the archive path refuses every status
    # for it. The flag said False for that routing reason for one round, which is the two questions
    # collapsing into one word again. A superseded V1 decision therefore arrives as an active `DEC`
    # carrying `archive_candidate: true`, `written_to: active` and `SUPERSEDED` under
    # `legacy_fields.legacy_status`. What DEC has no field for at all is WHICH decision superseded
    # it (named in DEC-0002); that relation stays prose in `context`.
    ("ADR", "PROPOSED"): ("DEC", "VALID", False),
    ("ADR", "ACCEPTED"): ("DEC", "VALID", False),
    ("ADR", "SUPERSEDED"): ("DEC", "SUPERSEDED", True),
    ("MDR", "PROPOSED"): ("DEC", "VALID", False),
    ("MDR", "ACCEPTED"): ("DEC", "VALID", False),
    ("MDR", "SUPERSEDED"): ("DEC", "SUPERSEDED", True),
}

# THE ROWS WHOSE `archive_candidate` DEPARTS FROM THE V1 CHAIN, each with the reason it departs.
#
# Not a second statement of the flag -- the flag is above and this says WHY it disagrees with the
# shipped chain. `test_migrate.test_every_archive_candidate_row_follows_the_v1_chain_or_is_recorded`
# derives the set of departures from the kit templates in this repository's own history and
# compares it against these keys, so neither side can move alone: a flag flipped without a reason
# fails on the left, a reason kept for a row that no longer departs fails on the right.
ARCHIVE_CANDIDATE_DEVIATIONS = {
    ("TSK", "DONE"):
        "mid-chain (`DONE -> VALIDATED`), flagged as finished anyway. V2 keeps `VALIDATED` for "
        "'QA confirmed', a confirmation V1 never collected, so no V1 record ever reached the "
        "chain's last box on the strength of a real check. Measured across the two dev field "
        "projects on 2026-08-05: 422 task records stand at DONE and 1 at VALIDATED -- reading DONE "
        "as unfinished would bury the ten live tasks under them, which is what SR-0004 exists to "
        "prevent (user decision 2026-08-04).",
    ("PRD", "DONE"):
        "mid-chain (`DONE -> TESTED -> ACCEPTED`), flagged as finished anyway, and this row is the "
        "weakest of the four: it comes from spec II.10's original table and this repository has "
        "never re-derived it. Measured 2026-08-05: 10 field records stand at PRD DONE. It costs "
        "nothing today "
        "-- `PR ACCEPTED` sits behind the acceptance approval, so `migration_archive_status` "
        "refuses it and the record lands in active/ either way -- and it is recorded as a departure "
        "rather than quietly corrected, because changing what a V1 requirement status MEANS is a "
        "spec decision and not an implementer's.",
    ("FR", "DEFERRED"):
        "the chain's own last box, deliberately NOT flagged: a deferred feature request is parked, "
        "not finished -- the V1 template writes it as an outcome of triage beside ACCEPTED and "
        "REJECTED, and the project can still pick it up. It maps to `TRIAGED` for the same reason.",
    ("RQ", "READY"):
        "the last box of the SECOND chain the `RQ` prefix carries: "
        "`fzulg_documentation.yaml` keys the BSFZ application layer by the research question it "
        "documents and runs its own DRAFT -> READY pair. Those two values describe the FORM of the "
        "documentation, not the question's life, so neither of them ends anything.",
}


# -- V1 -> V2 FIELD suggestions (SR-0007) --------------------------------------
#
# WHAT A ROW IS. A V2 required field a V1 store never spelled the same way, together with the V1
# field of that store which carries the same thing, and WHY. It is a SUGGESTION and nothing else:
# `migrate` prints it as the `--map` flag it would be, the run stays unexecutable until a human
# types that flag back, and a `--map` naming a different field wins. SR-0007 is where the boundary
# is argued ("ein Vorschlag ist keine Antwort").
#
# WHY THIS IS A TABLE AND NOT A RULE, stated rather than left as an apparent oversight: the step
# from "the V1 template documents this field as X" to "X is what the V2 contract calls Y" is a
# reading of two prose contracts, and no property of the two field NAMES produces it -- `actual`
# and `observed` share no substring, while `description` means three different things in three
# stores. What IS mechanical is everything AROUND the row, and all of it is checked rather than
# claimed: `test_migrate.test_every_field_suggestion_rests_on_a_field_the_kit_really_shipped`
# derives, from the V1 templates in this repository's own history, that each row's V1 store really
# documents that V1 field, that the V2 field really is required for the type the store maps to,
# and that the row is NEEDED (the two contracts do not already spell it the same). A row invented
# here for a field no kit ever shipped turns that test red.
#
# WHERE NO ROW STANDS THERE IS NO SUGGESTION, and that is the other half of SR-0007. `BUG` carries
# `violates`, which its own V1 template documents as `[PRD-XXXX | SR-XXXX]` -- two different
# parents -- so nothing here proposes it for `related_pr`; `PR`'s six uncollected fields
# (`class`, `problem`, `goal`, `invariants`, `out_of_scope`, `priority`) appear in no V1 product
# requirement template at all. Those stay open questions, because a suggestion with no ground under
# it is worse than a question.
V1_FIELD_SUGGESTIONS = {
    # (v1_type, v2_field): (v1_field, why)
    ("SR", "contract"): (
        "title",
        "the V1 system-requirements store carried the requirement ITSELF in `title` -- it has no "
        "second prose field -- and `contract` is where V2 asks for that requirement. A project "
        "whose architect added a longer field of its own should override this"),
    ("TSK", "assigned_role"): (
        "owner",
        "`owner` is the V1 task store's role vocabulary; `assigned_role` is the same choice in V2"),
    ("PROC", "roles"): (
        "owner",
        "the V1 process store documents `owner` as the executing specialist role; `roles` is that "
        "role in V2"),
    ("FR", "request_text"): (
        "user_story",
        "the V1 feature-request store writes the request as a user story; `request_text` is the "
        "request in the requester's words"),
    ("CR", "change_description"): (
        "description",
        "the V1 change-request store documents `description` as what should change, which is what "
        "`change_description` names"),
    ("CR", "target_pr"): (
        "affects",
        "the V1 change-request store documents `affects` as the requirement id the change is "
        "against, which is the binding `target_pr` carries"),
    ("PA", "change_description"): (
        "description",
        "the research protocol-amendment store ships the change-request schema under its own "
        "prefix, and documents `description` as what should change"),
    ("PA", "target_pr"): (
        "affects",
        "the research protocol-amendment store documents `affects` as the research question the "
        "amendment is against, which is the binding `target_pr` carries"),
    ("BUG", "observed"): (
        "actual",
        "the V1 bug store documents `actual` as what happens instead, which is what `observed` "
        "records beside `expected`"),
    ("BUG", "repro"): (
        "steps_to_reproduce",
        "`steps_to_reproduce` is the V1 spelling of the reproduction `repro` asks for"),
    ("HYP", "testable_prediction"): (
        "success_criteria",
        "the V1 hypothesis store documents `success_criteria` as what would support the "
        "hypothesis, which is the prediction `testable_prediction` asks to be able to test"),
    ("EXP", "design"): (
        "title",
        "the V1 experiment store named the design itself in `title` -- its prose lives in "
        "`procedure` and `analysis_plan`, neither of which is the design as a whole"),
}


def suggested_v1_field(v1_type: str, v2_field: str):
    """(v1_field, why) for a V2 required field this V1 store spells differently, or None."""
    return V1_FIELD_SUGGESTIONS.get((v1_type, v2_field))


def v1_types() -> frozenset:
    """Every V1 type this harness has a mapping row for -- the table's own answer.

    The migration needs it to tell two different findings apart, and the difference decides whether
    a project can be migrated at all: a type with rows here and an unrecognised STATUS is a backlog
    record the harness does not understand yet (block, spec II.10), while a type with no row at all
    is not a backlog record -- a dev project's `acceptance_reports.yaml` keys its criteria `AC-<n>`
    and gives them a `status`, and treating those as unmappable backlog items blocked the whole
    migration of a project whose QA reports were simply QA reports. The field reading behind that
    example is recorded at `migrate._is_backlog_type`, which is the function that asks this one.
    """
    return frozenset(v1_type for v1_type, _status in V1_STATUS_MAPPING)


class UnknownV1Status(ValueError):
    """No mapping for a V1 status -- the migration BLOCKS and the human records a
    Decision item; nothing guesses (spec II.10).

    Raised into `kernel/migrate.py`, which turns it into a `blocked` finding on the
    dry run and refuses the executing run wholesale while any one of them stands --
    a plan with a blocker is not partially applied."""


def map_v1_status(v1_type: str, v1_status: str):
    """Return (v2_type, v2_status, archive_candidate); the V1 original is
    preserved by the caller in `legacy_fields` (lossless, spec II.10)."""
    try:
        return V1_STATUS_MAPPING[(v1_type, v1_status)]
    except KeyError:
        raise UnknownV1Status(
            "no V1->V2 mapping for %s status %r; `%s` has rows in spec II.10's table but this "
            "value is not one of them, so the migration blocks rather than guessing. Remedy: this "
            "is a HARNESS gap, not a project one -- the table lives in the enforcement layer, "
            "which a session may not edit (`guard_harness_selfmod` refuses it). Record it with "
            "`python scripts/harness.py capture DEC` and report it; the walkable alternative "
            "inside the project is to correct the status in the V1 file itself, in an editor "
            "outside the session, if the value is simply wrong."
            % (v1_type, v1_status, v1_type)
        ) from None
