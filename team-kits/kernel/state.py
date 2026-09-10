"""State-kernel core operations (HARNESS_V2_SPEC.md II.4) -- step 1.4a.

The kernel is the ONLY writer of canonical project state. Every operation:
- runs under the cross-process KernelLock (item write AND index regeneration
  inside the same hold -- no second inconsistent state)
- writes atomically (temp file + os.replace, extended-length paths)
- allocates ids itself (max-scan over active+archive under the lock;
  callers never pick ids)
- enforces the status automata, and enforces the USER APPROVAL an edge needs
  when an approval kind commits that edge (`approvals.APPROVAL_TRANSITIONS`
  read backwards). `transition` is the only writer of such a status; the TSK
  dispatch lifecycle writes its own statuses directly, and none of those is a
  status an approval commits -- see `_transition_locked`
- invalidates approvals atomically when hashed fields change
  (revision +1, approval_ref cleared, status -> INVALIDATION_TARGET)

Later steps add: approvals/dispatch/submit-result (1.4b), session brief /
validate / doctor (1.4c). PyYAML is fine here (kernel ops, not hook hot path).

Interim notes (Fable-Check 7):
- update_item does not yet reject UNKNOWN extra fields -- the 1.4c validator
  closes that (full schemas over the reference graph)
- ProjectState/KernelLock instances are NOT thread-safe when shared: use one
  instance per thread/operation (the lockFILE serializes across them)
- archive() is two-phase (archive write, then active remove): a crash in
  between leaves the item in both places -- harmless for id max-scan,
  flagged by validate/doctor (1.4c)
"""
from __future__ import annotations

import ntpath
import os
import re
import sys
import time

import yaml

from .backlog_types import (
    AREA_FIELD,
    AREA_MAX_DEPTH,
    ACTIVE_DIRS,
    AUTOMATA,
    BLOCKED_REASON_FIELD,
    BLOCKED_RESULT,
    DATE_FIELDS,
    EVIDENCE_RESULT_FIELD,
    EVIDENCE_KINDS,
    EVIDENCE_RESULTS,
    HASHED_FIELDS,
    HOLE_LIMIT_FIELD,
    HOLE_NUMBER_FIELD,
    HOLE_NUMBER_PREFIX,
    IMMUTABLE_TYPES,
    IMPORT_MARK,
    LEGACY_FIELD,
    NON_AUTOMATON_STATUSES,
    NONEMPTY_FIELDS,
    names_something,
    OPTIONAL_FIELDS,
    area_segments,
    PARENT_FIELDS,
    PASSING_RESULT,
    REQUIRED_FIELDS,
    RUN_RECORD_FIELDS,
    RUN_SCOPES,
    STATUS_DEPENDENT_FIELDS,
    TASK_TYPES,
    TSK_PLAN_FIELDS,
    TransitionError,
    assert_transition,
    confirming_edge,
    format_id,
    hole_type,
    initial_status,
    invalidation_target,
    is_terminal,
    map_v1_status,
    normalised_date,
    parse_id,
    replanning_route,
    single_value_offences,
)
from .lock import KernelLock, ext_path
from . import board, plan_diagram

_KERNEL_SET = ("id", "status", "revision", "approval_ref", "created")

# Spec II.4's Vorschlagsbereich. Here rather than in `layout` because it is a path SEGMENT the
# writers below compose (`staging_root`), and `layout` -- which imports this module -- re-exports
# it for the predicates that compare a segment.
STAGING_DIRNAME = "staging"

# WHAT A CONFIRMATION MUST SHOW, per item type: {type: Evidence kind}. WHICH edge this guards is
# not written here -- `backlog_types.confirming_edge` derives it from the type's own automaton, so
# a renamed status moves the rule with it.
#
# THE ROWS ARE THE PROMISES THE SHIPPED TEXTS MAKE, and there is exactly one of them. The three
# constitutions' §2 ("mandatory regression test -- fails pre-fix, passes post; the Evidence for it
# is what moves the bug from FIXED to VERIFIED") is a statement about a MECHANISM, and until
# 2026-07-31 there was none: measured on a fresh state directory, `transition BUG-0001 VERIFIED`
# ran with no Evidence in the project at all and `validate` then reported 0 errors.
#
# WHAT IS DELIBERATELY NOT IN HERE, named because an absence a reader cannot see is the thing this
# file keeps being wrong about: `confirming_edge` also picks out TSK DONE->VALIDATED, PR/RQ
# DELIVERED->ACCEPTED, CR APPROVED->APPLIED and EXP COMPLETED->ANALYZED. Those edges are NOT
# guarded by anything here. The quality-engineer SKILL and the PM SKILL both say QA Evidence is
# what lets a task go DONE -> VALIDATED, and that remains policy the roles follow rather than a
# rule the kernel enforces -- `gate_git` demands the same Evidence at the MERGE, which is a
# different moment. Adding a row is all it takes; inventing one for a type whose required proof no
# shipped text states would be the kernel making up policy.
CONFIRMING_EVIDENCE = {"BUG": "test"}

# HOW THE KERNEL NAMES A FILE IT STORES PER REVISION -- composed and read back in ONE place.
#
# `staging` freezes some items per revision (spec II.6/II.6a): the wireframe `WFR-0001` lives at
# `design/wireframes/WFR-0001.r02.drawio.svg` with the companion `WFR-0001.r02.yaml` beside it.
# FOUR places have to agree on that shape -- three readers (`_frozen_revision_path`: which
# revision IS the item; `iter_active_items`: which files in a directory are items at all;
# `staging._next_frozen_revision`: which number has already been used) and `staging`'s own
# composition of the names -- and for one round they did not: the first read the directory per
# revision while the second read every `*.yaml` as its own item, so a SECOND `freeze_wireframe`
# made `report.validate_state` report `WFR-0001 duplicate id` and `gate_memory_complete` turned
# that into a blocked merge for the whole project (measured 2026-07-28, disposition row 6.5).
#
# The rule is read off the NAME, never off a list of types: an item stored per revision is
# recognised by how the kernel wrote it, so whichever type is frozen that way next arrives here
# already understood. An id carries no dot, which is what lets `[^.]+` separate the base from the
# revision and the revision from the suffixes (`.drawio.svg`, `.yaml`, `.html`).
_REVISION_RE = re.compile(r"(?P<base>[^.]+)\.r(?P<revision>\d+)(?P<suffix>\..*)?\Z", re.ASCII)


def revision_name(item_id: str, revision: int, suffix: str) -> str:
    """The file name of ONE frozen revision -- the only composer, read back by `split_revision`."""
    return "%s.r%02d%s" % (item_id, int(revision), suffix)


def split_revision(name: str):
    """(base, revision, suffix) for a per-revision file name; (None, None, None) otherwise."""
    match = _REVISION_RE.match(name or "")
    if not match:
        return None, None, None
    return match.group("base"), int(match.group("revision")), match.group("suffix") or ""


def names_a_drive(text) -> bool:
    r"""Does this word open with a Windows drive specification (`C:/x`, `C:x`, `//server/share`)?

    ONE ANSWER FOR EVERY HOST, which is the whole reason this is a function and not
    `os.path.splitdrive` at each caller. A position, an artefact path and a staging name are all
    stored in the state tree, and that tree travels: written on Windows, read on Linux, and back.
    `os.path` is the READER's flavour, so the same stored word was a drive to one session and an
    ordinary relative name to the next -- measured 2026-08-28 on the hosted ubuntu runner, where
    `C:\Windows\win.ini` passed `approvals.is_project_position` and `checkpoints.
    contained_artifact` while three docstrings promised a drive letter could not (BUG-0069).

    THE OVER-REFUSAL IS REAL AND IT IS THE SAFE DIRECTION. `ntpath` calls any word whose SECOND
    character is a colon a drive spec -- `a:b` and `1:x` as much as `C:x` -- so a POSIX project
    that holds such a name at its root can no longer name it as a position, an artefact or a
    staged file. It gets a refusal it can report; the other direction mints an approval that
    matches nothing. `test_the_drive_clause_of_a_stored_path_is_one_reader_for_every_host` is
    where both the answer and the three callers' use of it are measured.

    `ntpath` because it is the flavour that KNOWS about drives; a reading that does not cannot
    refuse one. Callers pass the word after their own separator normalisation.
    """
    return bool(ntpath.splitdrive(str(text or ""))[0])


# THE ONE EDGE WHOSE GUARD IS A CALLER ARGUMENT RATHER THAN A STORED RECORD (spec II.2
# Querregeln: a failed task may only be retried on an approved retry). Written here as data
# because TWO readers need it and a condition spelled at each of them is two rules: the transition
# path refuses the edge without `approved_retry=True`, and `migration_writable_statuses` may not
# count it as an edge a session walks on its own. `_transition_locked` is the enforcing reader.
RETRY_APPROVAL_EDGE = ("TSK", "FAILED", "READY")


def _dates_in(item_type: str, fields: dict, operation: str) -> dict:
    """{field: the canonical day} for every declared date field this payload carries -- or raise.

    ONE FUNCTION, TWO VERBS. `capture` and `update` are both writers of a stored item, so a rule
    only one of them enforces is a rule with a second door: measured as a process before this
    existed, `update MST-0001 {"due": "Weihnachten"}` was rc 0 and stored, `{"due": "20261225"}`
    stored a second spelling of a day the store already held as `2026-12-25`, and `{"due": null}`
    put back exactly the `None` the capture path had just been taught to refuse. The check and the
    normalisation travel together for the same reason: what was READ is what gets STORED, so no
    caller can validate one spelling and write another.

    PRESENCE AND NOT TRUTHINESS decides whether a field is judged -- a key the payload does not
    carry belongs to the required-field loop (or is an optional date simply not given), while a key
    that IS there is judged whatever it holds.

    `operation` is the verb in the refusal, because a role meets this mid-command and "capture"
    would be the wrong word half the time.
    `tools/test_state.py::test_a_date_field_that_is_not_a_date_is_refused_at_capture` and
    `tools/test_state.py::test_the_update_path_reads_a_date_field_exactly_as_capture_does`.
    """
    canonical = {}
    for field in DATE_FIELDS.get(item_type, ()):
        if field not in fields:
            continue
        try:
            canonical[field] = normalised_date(fields[field])
        except (TypeError, ValueError):
            raise StateError(
                "%s %s: %s is %r, which is not a calendar date. Remedy: write it as "
                "YYYY-MM-DD -- everything that reads this field reads it as a day, and a value "
                "nothing can parse shows up as no date at all in every view of it."
                % (operation, item_type, field, fields[field])
            ) from None
    return canonical


def _replanning_remedy(item_id: str, item_type: str, status: str, planning_status: str) -> str:
    """The walkable half of a frozen-field refusal, composed from `replanning_route` (BUG-0089).

    EVERY MOVE THIS SENTENCE NAMES IS AN EDGE THE AUTOMATON HAS, at the moment of the refusal.
    The sentence it replaced named a transition back to DRAFT that no `TSK` status can walk -- an
    edge into the initial status does not exist on the shipped automaton -- so a role that followed
    the remedy met a second refusal telling it the opposite. `replanning_route` is the reader; this
    only turns its two answers into a line, and says the honest thing when the first one is empty.

    THE LAST CLAUSE IS NOT A ROUTE AND DOES NOT PRETEND TO BE: with no edge back to the planning
    status and no terminal within reach, there is nothing this kernel can offer but the fact, which
    is better than an instruction that cannot be followed.
    `tools/test_state.py::test_a_frozen_field_refusal_names_only_walkable_transitions` measures the
    three shapes against the running automata.
    """
    route = replanning_route(item_type, status)
    moves = ["transition %s back to %s to re-plan it" % (item_id, target)
             for target in route["replan"]]
    moves += ["transition %s to %s and capture a new task with the corrected work order"
              % (item_id, target) for target in route["close"]]
    if not moves:
        return ("%s has no transition out of %s that this kernel can offer -- neither back to %s "
                "nor into a terminal status -- so the work order cannot be re-planned from here"
                % (item_id, status, planning_status))
    return ", or ".join(moves)


def migration_writable_statuses(item_type: str) -> frozenset:
    """The statuses a MIGRATION may write onto an item directly -- derived, never listed.

    THE PROPERTY: a status this type can REACH from its initial one without ever walking an edge
    whose guard the import cannot satisfy.

    WHICH GUARDS ARE READ, AND WHICH ONE IS NOT. `_transition_locked` names FOUR things that stand
    between a status and its new value, and this walk reads three of them:
      * the AUTOMATON -- the walk is over `automaton.allowed`, so an undefined edge is not walked;
      * the APPROVAL -- `approvals.APPROVAL_TRANSITIONS` read backwards, the same map
        `approvals.required_approval_kinds` refuses an unapproved transition from;
      * the TSK RETRY rule -- `RETRY_APPROVAL_EDGE`, one datum read by this walk and by the
        transition path, rather than a condition spelled twice.
    THE FOURTH IS NOT READ, AND WHAT THAT COSTS IS MEASURED RATHER THAN ASSUMED EITHER WAY:
    `_assert_confirmed` demands the proof `CONFIRMING_EVIDENCE` names on a type's confirming edge,
    and this walk does not consult it. On the shipped maps that costs NOTHING -- the only type
    `CONFIRMING_EVIDENCE` covers is `BUG`, whose confirming edge ends at `VERIFIED`, and `VERIFIED`
    already lies behind the `BUG` scope approval, so the approval bolt excludes it first. So this
    is a guard that is not read rather than a status that escapes, and the difference matters:
    adding a type to `CONFIRMING_EVIDENCE` whose confirming target IS reachable here would turn it
    into the second thing without a line of this file changing.
    `test_state.test_the_migration_write_set_reads_three_of_the_four_edge_guards` is what measures
    that, in both directions, so this paragraph cannot quietly stop matching the maps.

    REACHABILITY RATHER THAN THE EDGE'S OWN TARGET, and that is the correction of 2026-08-04: this
    subtracted the approval TARGETS as a set, which leaves every status further down the same chain
    writable although it sits behind that approval just as much. Measured end to end before it was
    a walk -- a V1 `CR APPLIED` record was written to `archive/CR/<year>/` at `APPLIED`, a status
    no user was ever asked about, with `approval_ref: null` and no request anywhere. Nothing
    outside that file could say so either: `report.validate_state` judges the ACTIVE items, so an
    archived one appears in no finding of any severity.

    WHAT AN ABSENT APPROVAL EDGE MEANS -- and this is a HOLE, named with its mechanism rather than
    described as a guard. This walk reads a missing row in `APPROVAL_TRANSITIONS` as "no approval
    stands in the way". A missing row can mean that, and it can equally mean that the approval kind
    was never built: `approvals.required_approval_kinds` records SR PROPOSED -> ACCEPTED as
    "Reported, not bridged" -- an edge somebody may well have to sign, which has no KIND with a
    manifest, hence no row, hence no guard. So the import writes `SR ACCEPTED` into the archive
    with `approval_ref: null`, which is the same shape as the `CR APPLIED` defect one paragraph
    up, produced by an absence rather than by a subtraction. Nothing here can tell the two readings
    apart, because the harness states the difference only in that prose;
    `test_state.test_which_archive_bound_rows_rest_on_an_absent_approval_edge` derives today's set
    (SR, TSK, FR and HYP rows) and turns red when it changes in either direction. Closing it needs
    an approval KIND, which is a spec decision and not this function's.

    A type with no automaton has no status this kernel can walk to (`DEC`, `INV`), so the answer is
    empty rather than "anything": the import may not decide a record's status on a vocabulary that
    exists only in a comment.

    `approvals.approved_statuses` is the neighbouring question -- which statuses an item holds
    BECAUSE it was approved, for the spawn gates -- and it answers differently on purpose;
    `test_state.test_the_statuses_a_migration_may_write_are_the_ones_reachable_without_an_approval`
    names the types the two disagree about, so neither can be quietly rewritten into the other.
    """
    automaton = AUTOMATA.get(item_type)
    if automaton is None:
        return frozenset()
    from . import approvals
    gated = {edge for (owner, _kind), edge in approvals.APPROVAL_TRANSITIONS.items()
             if owner == item_type}
    if RETRY_APPROVAL_EDGE[0] == item_type:
        gated.add(RETRY_APPROVAL_EDGE[1:])
    reached, frontier = {automaton.initial}, [automaton.initial]
    while frontier:
        current = frontier.pop()
        for edge in automaton.allowed:
            if edge[0] != current or edge in gated or edge[1] in reached:
                continue
            reached.add(edge[1])
            frontier.append(edge[1])
    return frozenset(reached)


def migration_archive_status(item_type: str, v1_type: str, v1_status: str) -> str:
    """The status `capture_migrated_archive` writes, or a refusal -- the archive path's whole rule.

    TWO QUESTIONS, ASKED OF TWO AUTHORITIES, because they are about different things:

      * DOES THIS RECORD BELONG IN THE ARCHIVE -- the `archive_candidate` column of
        `V1_STATUS_MAPPING`, since whether a V1 value means "this life is over" is a fact about the
        V1 vocabulary and about nothing else. It used to be asked of the V2 AUTOMATON instead
        (is the mapped status a terminal), and that is a different question: V1 `TSK DONE` maps to
        `DONE`, which is no terminal of the V2 task automaton because V2 keeps `VALIDATED` for "QA
        confirmed" -- a confirmation V1 never collected. So a task V1 recorded as DONE landed in
        `tasks/active/` at DRAFT, presented as a fresh work order missing ten of eleven contract
        fields: the state of affairs SR-0004 exists to prevent, produced by the exemption written
        to prevent it, for the very rows whose number is its whole argument.
      * MAY THE IMPORT WRITE THAT STATUS AT ALL -- `migration_writable_statuses`, which is the
        approval bolt and which no table may talk its way past: a row that marks a status behind an
        approval edge as archive-bound is refused here, not obeyed.

    THIS IS A DIVERGENCE FROM THE WRITTEN CONTRACT, not an implementation of it: SR-0002 says "nur
    bei Endzustaenden" and SR-0004 "dessen abgebildeter Status ein Endzustand seines Automaten
    ist", i.e. exactly the terminal check the first bullet replaces. The replacement is argued
    above and is what runs; the SRs still say the other thing and are canonical state this module
    may not edit, so the divergence is REPORTED (`capture_migrated_archive`, bolt two) and awaits a
    decision rather than being read as agreement.

    Bounded by construction: whatever it returns is a member of `migration_writable_statuses`, so
    the direct status write it feeds can be read off the kernel's own maps rather than trusted. The
    mapping table is asked for the V2 value (`map_v1_status`) so that the archive path and the dry
    run's classification cannot answer differently.
    """
    v2_type, v2_status, archive_candidate = map_v1_status(v1_type, v1_status)
    if v2_type != item_type:
        raise StateError(
            "%s %r maps to a %s item, not to %s. Remedy: this is a caller bug -- the type the "
            "table answers with is the type the item is written as."
            % (v1_type, v1_status, v2_type, item_type))
    if not archive_candidate:
        raise StateError(
            "the migration archive path takes records spec II.10's table marks as FINISHED, and "
            "%s %r is not one of them. Remedy: import this record the ordinary way -- it lands in "
            "active/ at its initial status with the V1 value kept in `%s`."
            % (v1_type, v1_status, LEGACY_FIELD))
    allowed = migration_writable_statuses(item_type)
    if v2_status not in allowed:
        raise StateError(
            "%s %r maps to %r, which a %s reaches only through an edge a USER APPROVAL commits -- "
            "writing it here would be the automatically generated approval spec II.10 forbids. The "
            "import may write %s. Remedy: import this record the ordinary way -- it lands in "
            "active/ at its initial status with the V1 value kept in `%s`."
            % (v1_type, v1_status, v2_status, item_type,
               "/".join(sorted(allowed)) or "no status of this type (it has no automaton)",
               LEGACY_FIELD))
    return v2_status


def migration_archives(item_type: str, v1_type: str, v1_status: str) -> bool:
    """Would the archive path take this record? -- the ROUTING question, asked of the writer's rule.

    One judge for two callers. `migrate.build_plan` has to route each record and
    `capture_migrated_archive` has to refuse everything that is not routed here, and while the
    routing condition was spelled out at the planner a row could be added that the plan sent to the
    archive and the writer then rejected mid-run -- a plan promising what the run cannot do, which
    is the defect `capture_migrated_archive_preflight` exists to prevent one layer up.
    """
    try:
        migration_archive_status(item_type, v1_type, v1_status)
    except StateError:
        return False
    return True


def _is_item_id(value) -> bool:
    """Does this name an item at all? -- the question `parse_id` answers, without the raise."""
    try:
        parse_id(str(value))
    except ValueError:
        return False
    return True


# The suffix an ITEM file carries. Items are YAML whatever else lies beside them: a frozen
# wireframe revision is a `.drawio.svg` PLUS a `.yaml` companion, a frozen design a `.html` plus a
# `.yaml` manifest, and only the companion is the item.
ITEM_SUFFIX = ".yaml"


def item_revision(name: str):
    """(item id, revision) when `name` is the file of ONE stored revision of an item, else
    (None, None).

    THE predicate, and it is one function because the first cut of this fix had it twice and they
    disagreed within the hour. `_frozen_revision_path` demanded the revision be followed by
    exactly `.yaml`; `iter_active_items` accepted any suffix -- so a hand-placed
    `WFR-0001.r03.backup.yaml` was measured as the ACTIVE item by the second reader while
    `read_anywhere` still resolved `WFR-0001` to `r02`. That is the identical two-readings defect
    disposition row 6.5 is about, one file shape further along, and it is why the question is
    asked here rather than answered in each caller.

    A name that fails any part of it is not a revision file at all: it stays a file in its own
    right, and if its content claims an id another file also claims, the duplicate-id rule says so.
    """
    base, revision, suffix = split_revision(name)
    if revision is None or suffix != ITEM_SUFFIX or not _is_item_id(base):
        return None, None
    return base, revision


class StateError(ValueError):
    """Canonical-state operation refused -- message carries the remedy."""


class ProjectState:
    """All operations on one project_memory/ directory."""

    def __init__(self, root: str, lock_ttl: float = 60.0):
        self.root = os.path.abspath(root)
        self.lock = KernelLock(self.root, ttl=lock_ttl)

    # -- paths -----------------------------------------------------------------

    def active_dir(self, item_type: str) -> str:
        try:
            return os.path.join(self.root, *ACTIVE_DIRS[item_type].split("/"))
        except KeyError:
            raise StateError(
                "unknown item type %r. Remedy: use one of %s."
                % (item_type, "/".join(sorted(ACTIVE_DIRS)))
            ) from None

    def active_path(self, item_id: str) -> str:
        item_type, _ = parse_id(item_id)
        return os.path.join(self.active_dir(item_type), item_id + ".yaml")

    def staging_root(self) -> str:
        """Spec II.4's proposal area -- the whole of it.

        A builder for the same reason the two below are: `os.path.join(state.root, "staging")` was
        composed by hand in the session brief, in the staging sweep and in `staging.staging_dir`,
        and the name itself a fourth time in `layout`. Four spellings of one directory is how a
        reader of one of them comes to look somewhere the writer does not write; the name lives
        here, beside the writers, and `layout.STAGING_DIRNAME` re-exports it for the predicates
        that compare a path SEGMENT rather than a path.
        """
        return os.path.join(self.root, STAGING_DIRNAME)

    def archive_root(self) -> str:
        """The whole archive subtree.

        A builder of its own, and not merely the head of `archive_path`: everything the kernel
        retires lands somewhere under here, but at a path keyed by TYPE and YEAR
        (`archive_path`) or by staging key (`staging.clear_staging`). `kernel.layout` needs the
        SUBTREE -- asking `archive_path` for a probe would have declared `archive/pr/1970`
        canonical and left `archive/pr/2026` outside it, which is the whole archive of a live
        project.
        """
        return os.path.join(self.root, "archive")

    def archive_path(self, item_id: str, year: int) -> str:
        item_type, _ = parse_id(item_id)
        # deterministic archive paths (spec II.2): archive/<TYPE>/<year>/<ID>.yaml
        return os.path.join(self.archive_root(), item_type, str(year), item_id + ".yaml")

    def legacy_root(self) -> str:
        """The subtree a fully absorbed V1 store is moved into (SR-0005).

        A DIRECTORY builder for the same reason `archive_root` is one: what lands under here keeps
        its own relative path from the state root, so a probe of a file builder would declare one
        name canonical and leave every other outside.

        WHY IT IS A KERNEL-WRITTEN AREA AND NOT A KIT DOCUMENT AREA. `kernel.layout` asks the
        builders themselves what the kernel writes, and that one answer decides three things at
        once: `migrate` stops re-reading these files as V1 sources (SR-0005 asks for exactly that:
        "legacy/ ist ausdruecklich als 'bereits verarbeitet' verzeichnet"), `gate_write_scope`
        refuses a tool write into them -- a moved store is evidence of what the migration read, and
        a hand edit there would be an edit to that evidence -- and the SR-0001 scan skips them
        without needing a name of its own.
        """
        return os.path.join(self.root, "legacy")

    def legacy_path(self, relative_path: str) -> str:
        """Where a V1 document that fully became items is moved to, keeping its own path."""
        parts = [part for part in str(relative_path).replace("\\", "/").split("/") if part]
        return os.path.join(self.legacy_root(), *parts)

    def generated_path(self, name: str) -> str:
        """Where a REGENERABLE rollup lives (`generated/<name>`).

        A builder rather than a `os.path.join` at each call site, because `kernel.layout` asks
        the writers themselves where they write and a path composed inline answers nothing. The
        index below is one such writer; the session brief is the other.
        """
        return os.path.join(self.root, "generated", name)

    # -- io (always under the lock) --------------------------------------------

    @staticmethod
    def _read_yaml(path: str):
        with open(ext_path(path), encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    @staticmethod
    def _write_text_atomic(path: str, text: str, errors: str = "strict") -> None:
        """Write `text` to `path` atomically, leaving NO half-written file behind either way.

        THE TEMP FILE IS CLEANED UP ON FAILURE, and that is not tidiness. The serialisation above
        can raise on a payload it cannot represent, and the `.tmp-<pid>` it had already opened then
        stayed in the item directory -- measured in `procedures/active/`, where it is read by
        `migrate.state_fingerprint` (so a later plan digest covers a file nobody wrote on purpose)
        and by `report`'s directory readers. `os.replace` is still what makes the write atomic;
        this only makes the FAILING write leave the directory as it found it.

        The one atomic write in the kernel: `_write_yaml_atomic` is this plus a serialiser, and
        `kernel.presets` writes a kit document's single line through it -- two shapes of content,
        one rule about how bytes land.

        `errors` IS STRICT FOR STATE AND LOOSE FOR EXACTLY ONE CALLER. A YAML file may legally hold
        a lone surrogate (`"\\uD800"`), which `safe_load` hands on and UTF-8 cannot encode. Where
        the bytes ARE the state, refusing is right -- a silently substituted character would be a
        state nobody wrote. The board is a REPORT of that state, so it passes `errors="replace"`:
        a `?` in a rendered page is a reading of the item, while a raised UnicodeEncodeError there
        would fail the state write that had already happened
        (`test_board.test_a_surrogate_in_an_item_does_not_stop_the_state_write`).
        """
        directory = os.path.dirname(path)
        os.makedirs(ext_path(directory), exist_ok=True)
        tmp = path + ".tmp-%s" % os.getpid()
        try:
            with open(ext_path(tmp), "w", encoding="utf-8", newline="", errors=errors) as fh:
                fh.write(text)
            os.replace(ext_path(tmp), ext_path(path))
        except BaseException:
            try:
                os.remove(ext_path(tmp))
            except OSError:
                pass          # never mask the original failure with the cleanup's own
            raise

    @staticmethod
    def _write_yaml_atomic(path: str, data: dict) -> None:
        """Serialise `data` and write it through the atomic write above.

        The dump happens BEFORE any file is opened, so a payload YAML cannot represent leaves the
        directory untouched instead of leaving a temp file behind. `newline="\\n"` used to be given
        to the stream; it is now in the text itself, because `safe_dump` emits `\\n` and the writer
        below is told to translate nothing.
        """
        ProjectState._write_text_atomic(
            path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))

    def read_item(self, item_id: str) -> dict:
        path = self.active_path(item_id)
        try:
            item = self._read_yaml(path)
        except FileNotFoundError:
            raise StateError(
                "no active item %s (expected at %s). Remedy: check the id in the "
                "generated index; a finished item lives in the archive rather "
                "than among the active ones." % (item_id, path)
            ) from None
        if not isinstance(item, dict) or item.get("id") != item_id:
            raise StateError(
                "corrupt item file for %s at %s (id mismatch or non-mapping). "
                "Remedy: `git restore %s` then `python scripts/harness.py generate-index`."
                % (item_id, path, os.path.relpath(path, self.root))
            )
        return item

    def iter_active_items(self, item_type: str):
        """(stem, path) for every file in the type's active dir that IS an active item.

        ONE reading of one directory, for every reader that asks what a project is working on
        now -- the state validator and the session brief through `report._iter_active`, and
        `generated/index.yaml` through `_regenerate_index_locked`. Both used to answer it
        themselves with the older rule "every `*.yaml` in here is an item", which contradicted
        `_frozen_revision_path` next door and cost a merge (see `_REVISION_RE`).

        THE RULE, in one sentence: files whose names differ only in their `.rNN` are REVISIONS
        of one item, and the item is the highest of them. A superseded revision is HISTORY --
        still on disk, still in git, read by nobody who asks what is active, exactly as an
        archived item is. `read_anywhere` resolves the id to that same newest file, so the two
        readings can no longer disagree about which file an id names.

        TWO THINGS IT DELIBERATELY DOES NOT COLLAPSE, because each is a real contradiction the
        validator has to keep reporting rather than resolve by picking one:
          * a plain `<ID>.yaml` beside `<ID>.rNN.yaml` -- one directory then claims two homes
            for one id, and `read_anywhere` silently prefers the plain one;
          * a base that is no item id at all -- the revision rule is about items stored per
            revision, so `notes.r01.yaml` and `notes.r02.yaml` stay two files.
        Both leave the duplicate-id rule to speak, which is the counter-direction that must
        survive: two DIFFERENT items claiming one id is still an error.
        """
        base = self.active_dir(item_type)
        if not os.path.isdir(ext_path(base)):
            return
        newest, plain = {}, []
        for name in sorted(os.listdir(ext_path(base))):
            if not name.endswith(ITEM_SUFFIX):
                continue
            item_id, revision = item_revision(name)
            if item_id is None:
                plain.append(name)
                continue
            if item_id not in newest or revision > newest[item_id][0]:
                newest[item_id] = (revision, name)
        for name in sorted(plain + [name for _revision, name in newest.values()]):
            yield name[: -len(ITEM_SUFFIX)], os.path.join(base, name)

    def _frozen_revision_path(self, item_id: str):
        """The newest `<id>.rNN.yaml` in the type's active dir, or None.

        The kernel freezes some items PER REVISION (`staging.freeze_wireframe` /
        `freeze_design`, spec II.6/II.6a): the canonical file of `WFR-0001` is
        `design/wireframes/WFR-0001.r03.yaml`, and `active_path` -- which composes
        `<id>.yaml` -- names nothing. So `read_anywhere` answered "no such item" for
        every wireframe and every frozen design, and the two readers built on it
        answered with it: `_assert_origins_resolve` REFUSED an Evidence recorded
        against a `WFR` ("does not exist"), and `report._hangs_from` walked no further
        than the id. The designer's review could not be recorded, and once recorded by
        hand it covered nothing.

        The rule is read off the file names, not off a list of types: an item stored
        per revision IS its newest revision, so whichever type is frozen that way next
        arrives here already resolved. `iter_active_items` reads the same names through
        the same `split_revision`, which is what makes that one sentence the whole
        kernel's rather than this method's.

        Deliberately NOT in `active_path`: that path is where a write LANDS, and a write
        must be deterministic -- a frozen revision is immutable, and the way to change
        one is another freeze, not an edit of the file the reader happened to pick.
        """
        item_type, _ = parse_id(item_id)
        base = self.active_dir(item_type)
        if not os.path.isdir(ext_path(base)):
            return None
        best = None
        for name in sorted(os.listdir(ext_path(base))):
            found, revision = item_revision(name)
            if found != item_id:
                continue
            if best is None or revision > best[0]:
                best = (revision, os.path.join(base, name))
        return best[1] if best else None

    def read_anywhere(self, item_id: str):
        """(item, archived) from active/, else from archive/; (None, False) when nowhere.

        The reader for questions that outlive an item's active life. A TSK is
        archived the moment it reaches VALIDATED, so anything that walks from a
        finished piece of work back to the requirement it served -- the merge
        gate resolving Evidence to its root is the case that forced this -- must
        follow that walk into the archive or it stops one hop short of the
        answer.

        LOCKING is not one rule here, because the callers ask two different
        questions. A WRITER or a validator reads to decide what it will then
        write or assert about the store as a whole, so it must hold the lock or
        its premise can change underneath it -- `dispatch` does exactly that.
        The MERGE-GATE path reads single item files to answer a question about
        one item, deliberately lock-free: it runs on the same tool call as
        `gate_memory_complete`, which already takes the lock for
        `validate_state`, and a second acquisition on that event is what turns a
        slow validate into a blocked push. That trade is argued in full at
        `report._delivery_evidence`, where the gate path begins; what makes it
        payable is that a half-written file is no verdict either way: it is read
        as no judgement rather than as consent, and `validate_state` -- taken
        under the lock on the same event -- is what reports it as a finding.
        """
        try:
            item_type, _ = parse_id(item_id)
        except ValueError:
            return None, False   # not an id at all: it names no item, here or anywhere
        try:
            return self.read_item(item_id), False
        except StateError:
            pass
        frozen = self._frozen_revision_path(item_id)
        if frozen is not None:
            item = self._read_yaml(frozen)
            if isinstance(item, dict) and item.get("id") == item_id:
                return item, False
        base = os.path.join(self.archive_root(), item_type)
        if os.path.isdir(ext_path(base)):
            for year in sorted(os.listdir(ext_path(base))):
                candidate = os.path.join(base, year, item_id + ".yaml")
                if os.path.exists(ext_path(candidate)):
                    return self._read_yaml(candidate), True
        return None, False

    def exists_anywhere(self, item_id: str) -> bool:
        """True when the id names an item in active/ OR archive/ -- call under the lock."""
        if os.path.exists(ext_path(self.active_path(item_id))):
            return True
        if self._frozen_revision_path(item_id) is not None:
            return True
        item_type, _ = parse_id(item_id)
        base = os.path.join(self.archive_root(), item_type)
        if not os.path.isdir(ext_path(base)):
            return False
        for year in sorted(os.listdir(ext_path(base))):
            if os.path.exists(ext_path(os.path.join(base, year, item_id + ".yaml"))):
                return True
        return False

    def _assert_origins_resolve(self, item_type: str, fields: dict, also_existing=()) -> None:
        """Every field BINDING an item to the work it belongs to must name items that EXIST.

        `also_existing` is ids a PLANNER has undertaken to create before this body is written, and
        it exists because asking this question at planning time otherwise had no true answer: a V1
        store is a parent chain, so `migrate` planning `PROC-0001` and `PROC-0002 derives_from
        PROC-0001` was told the parent does not exist -- which was true of the state BEFORE the
        run and false of the state the run reaches. It defaults to empty, so every caller that
        writes NOW still asks the unrelaxed question; only a caller that can name the ids it is
        about to write may widen it, and `migrate.build_plan` then also has to order the writes and
        refuse a cycle, because a promise to create A before B and B before A is not keepable.

        WHICH fields those are is `PARENT_FIELDS`, derived from the type's field contracts --
        this check must not carry its own list of types. It carried one (`TSK` and `EVD`,
        the two whose binding is a hot gate input), and the cost was that the same two-name
        list had to be kept in step with the reference graph in `report`, which drifted:
        `SR.derives_from` was in neither, so an `SR` could be captured against a phantom
        parent and the merge gate then found no root for the Evidence judging it.

        The bindings this exists for, and why the CHEAP half of the reference check belongs
        on the write path rather than only in the state validator:

        * `TSK.derives_from` is what the dispatch gate resolves `acceptance_refs` against.
          A phantom id, an integer or a free-text note contributes nothing, so a task can
          look derived while being derived from nothing.
        * `EVD.related` is what `gate_git` resolves a merge against. Evidence bound to a
          nonexistent id is bound to nothing -- and since the gate answers "is there
          passing evidence for THIS item", such a record is the shape that looks like proof
          while covering no work at all.

        Called from capture AND from the edit path, for the reason the vocabulary check is:
        a binding refused at capture and then written by an edit is not refused at all. Which
        types can still reach it there is a fact about `IMMUTABLE_TYPES` (an `EVD` is refused
        wholesale a few lines earlier), not a reason for this check to know which type it is
        judging.

        Only the CHEAP half lives here -- ids parse and resolve. Whether the origin belongs
        to this root's tree (BUG.related_pr == root, CR.target_pr == root, EXP->HYP->RQ ==
        root) is a reference-GRAPH question, which spec II.4 assigns to the state validator
        (gate layer 4) rather than to a hot dispatch path.
        """
        for field in PARENT_FIELDS.get(item_type, ()):
            if field not in fields:
                continue
            origins = fields.get(field)
            origins = origins if isinstance(origins, (list, tuple)) else [origins]
            remedy = _BINDING_REMEDY.get(item_type, _BINDING_REMEDY_DEFAULT % field)
            for origin in origins:
                try:
                    parse_id(str(origin))
                except ValueError:
                    raise StateError(
                        "%s %r is not an item id. Remedy: %s -- free text there binds to "
                        "nothing." % (field, origin, remedy)
                    ) from None
                if str(origin) in set(also_existing):
                    continue
                if not self.exists_anywhere(str(origin)):
                    raise StateError(
                        "%s %s does not exist. Remedy: create the item first, or point at the "
                        "right one -- a phantom reference binds to nothing, and the gate that "
                        "reads it would refuse later with a less obvious message."
                        % (field, origin)
                    )

    # -- id allocation ---------------------------------------------------------

    def _max_number(self, item_type: str) -> int:
        highest = 0
        scan_dirs = [self.active_dir(item_type),
                     os.path.join(self.archive_root(), item_type)]
        for base in scan_dirs:
            if not os.path.isdir(ext_path(base)):
                continue
            for _dir, _subdirs, files in os.walk(ext_path(base)):
                for name in files:
                    stem = name[:-5] if name.endswith(".yaml") else name
                    try:
                        found_type, number = parse_id(stem)
                    except ValueError:
                        continue
                    if found_type == item_type:
                        highest = max(highest, number)
        return highest

    def allocate_id(self, item_type: str) -> str:
        """Next id by max-scan over active+archive -- call ONLY under the lock."""
        return format_id(item_type, self._max_number(item_type) + 1)

    # -- operations ------------------------------------------------------------

    def _assert_capture_shape(self, item_type: str, fields: dict) -> None:
        """What is refused about a NEW item body whatever else is true of it.

        Split out of `capture_preflight` because the migration's archive path (DEC-0004/SR-0002) is
        exempt from the FIELD contract and from nothing else. What stays here is the part the
        exemption may not touch: the type has to be one this kernel captures, and the body may not
        carry a kernel-set field -- the `status` among them, which is the whole reason a caller may
        not hand one in.
        """
        if item_type not in REQUIRED_FIELDS:
            raise StateError(
                "capture does not handle type %r (ARC/WFR go through the "
                "promotion path; APR through approve). Remedy: use one of %s."
                % (item_type, "/".join(sorted(REQUIRED_FIELDS)))
            )
        provided_kernel_fields = [k for k in _KERNEL_SET if k in fields]
        if provided_kernel_fields:
            raise StateError(
                "fields %s are kernel-set and must not be provided on capture. "
                "Remedy: drop them; the kernel assigns id/status/revision/"
                "approval_ref/created." % ", ".join(provided_kernel_fields)
            )
        _assert_closed_vocabularies(item_type, fields)

    def capture_preflight(self, item_type: str, fields: dict, also_existing=()) -> None:
        """Everything `capture` refuses BEFORE it writes anything -- raised, never written.

        WHY THIS IS ITS OWN METHOD, and it is not tidiness. A caller that wants to know whether a
        body WOULD capture had no way to ask, so it guessed -- and `kernel/migrate.py` guessed
        with the one check it could see (are the required fields present?). Measured against a dev
        project holding a V1 `system_requirements.yaml`: every one of its records names
        `derives_from: PRD-0001`, `PRD` is no V2 type, and `_assert_origins_resolve` refuses it --
        but only at write time. The plan said READY, three items landed, the fourth raised, and the
        run died in the middle with no receipt. A plan that cannot answer the question its own
        writer will ask is not a plan.

        So the write path and every planner ask the SAME function. Anything `capture` learns to
        refuse is refused at planning time on the day it is added here, with no second reader to
        keep in step.

        `also_existing` is passed straight through to `_assert_origins_resolve` and is empty for
        the write path; what it is for is argued there.
        """
        self._assert_capture_shape(item_type, fields)
        missing = [k for k in REQUIRED_FIELDS[item_type] if k not in fields]
        if missing:
            raise StateError(
                "capture %s is missing required fields: %s (spec II.2 "
                "Pflichtfelder). Remedy: provide every listed field."
                % (item_type, ", ".join(missing))
            )
        # ...and for a few of them "provided" has to mean "says something": see
        # NONEMPTY_FIELDS for why an empty list there is the same claim as no field.
        # Capture-only, because the types that have such a field are exactly the ones
        # the edit path refuses wholesale (IMMUTABLE_TYPES).
        hollow = [k for k in NONEMPTY_FIELDS.get(item_type, ())
                  if not names_something(fields.get(k))]
        if hollow:
            raise StateError(
                "capture %s: %s must name something -- a list of blanks says exactly what "
                "leaving the field out says. Remedy: %s"
                % (item_type, ", ".join(hollow),
                   _NONEMPTY_REMEDY.get(item_type, _NONEMPTY_REMEDY_DEFAULT))
            )
        # A DATE FIELD HAS TO BE A DATE (DEC-0064) -- `_dates_in` is the reader, and it is the SAME
        # one the edit path asks, so what a role may capture and what it may update cannot come
        # apart. What counts as a date is the standard library's answer rather than a pattern this
        # kernel would keep; which fields are asked is the type's own `DATE_FIELDS`.
        _dates_in(item_type, fields, "capture")
        # ONE STATEMENT, DECLARED WHOLE (FR-0040, DEC-0061):
        # `run_scope` is what the merge reads and
        # `run_command` is what an auditor re-runs it against, so half of the pair is either an
        # unbacked claim or a record nothing can act on. Capture-only, like `NONEMPTY_FIELDS`
        # above and for the same reason: the only type that carries the pair is immutable.
        partial = [name for name in RUN_RECORD_FIELDS if fields.get(name)]
        if partial and len(partial) != len(RUN_RECORD_FIELDS):
            raise StateError(
                "capture %s names %s without %s -- the two are one statement about the run "
                "behind this record: the scope is what the merge reads and the command is what "
                "it can be checked against. Remedy: pass both, or neither."
                % (item_type, ", ".join(partial),
                   ", ".join(name for name in RUN_RECORD_FIELDS if name not in partial)))
        # A `blocked` VERDICT OWES ITS SENTENCE, AND THE SENTENCE OWES ITS VERDICT (FR-0082).
        # `blocked` says that the run did not happen -- so the record has to say WHAT stopped it,
        # or a later reader has a red verdict in front of him that looks exactly like a checked
        # one. The other direction is refused for the mirror reason: a sentence about what blocked,
        # filed under a `pass` or a `fail`, describes a run whose result claims it happened.
        # WHICH TYPES ARE ASKED is derived from the field contract -- the types whose `OPTIONAL_FIELDS`
        # carry the field -- rather than from the type name, so a second type that ever records a
        # verdict arrives with the rule instead of without it.
        if BLOCKED_REASON_FIELD in OPTIONAL_FIELDS.get(item_type, ()):
            blocked = fields.get(EVIDENCE_RESULT_FIELD) == BLOCKED_RESULT
            explained = bool(str(fields.get(BLOCKED_REASON_FIELD) or "").strip())
            if blocked != explained:
                raise StateError(
                    "capture %s: %s. `%s` is the value for a run that did NOT happen, so the record "
                    "has to name what stopped it -- without that sentence the next reader takes it "
                    "for a checked fact, and with it under any other result the record claims a run "
                    "it also reports as done. Remedy: %s."
                    % (item_type,
                       "%s is %r and %s is empty"
                       % (EVIDENCE_RESULT_FIELD, BLOCKED_RESULT, BLOCKED_REASON_FIELD)
                       if blocked else
                       "%s says what blocked while %s is %r"
                       % (BLOCKED_REASON_FIELD, EVIDENCE_RESULT_FIELD,
                          fields.get(EVIDENCE_RESULT_FIELD)),
                       BLOCKED_RESULT,
                       "pass --%s '<what stopped the run>'" % BLOCKED_REASON_FIELD.replace("_", "-")
                       if blocked else
                       "record the result as %r, or drop --%s" % (BLOCKED_RESULT,
                                                                  BLOCKED_REASON_FIELD.replace("_", "-"))))
        # THE OUTLINE STAYS AN OUTLINE (FR-0017). Two levels is what the field is for -- a
        # document holds headings, a heading holds requirements -- and a third one is refused
        # here rather than tidied away later, because an outline nobody can take in at a glance
        # is the over-fragmentation the FR makes a condition of building this at all.
        depth = len(area_segments(fields.get(AREA_FIELD)))
        if depth > AREA_MAX_DEPTH:
            raise StateError(
                "capture %s names an %s %d levels deep (%r); the outline carries at most %d -- a "
                "document and a heading under it. Remedy: put the requirement under an existing "
                "heading, or shorten the path."
                % (item_type, AREA_FIELD, depth, fields.get(AREA_FIELD), AREA_MAX_DEPTH))
        _assert_single_value_fields(item_type, fields)
        self._assert_origins_resolve(item_type, fields, also_existing)

    def _max_hole_number_locked(self) -> int:
        """The highest hole number the store carries, active and archived -- 0 when it carries none.

        A MAX-SCAN, exactly like `allocate_id`, and for the same reason: the store is the register.
        A counter kept beside it would be a second statement of what has been handed out, and the
        defect FR-0087 was written for is precisely a register that lived beside the items (a lead
        reserving numbers by message; two of them existed in no item at all).

        Archived holes are scanned too -- a CLOSED hole keeps its number forever, and reusing it
        would make every citation of that number ambiguous.
        """
        highest = 0
        for item in self._iter_every_stored_item():
            number = str(item.get(HOLE_NUMBER_FIELD) or "")
            if number.startswith(HOLE_NUMBER_PREFIX) and number[1:].isdigit():
                highest = max(highest, int(number[1:]))
        return highest

    def _iter_every_stored_item(self):
        """Every readable item file under this state root -- active and archive alike."""
        for base in (self.root,):
            for directory, _dirs, names in os.walk(ext_path(base)):
                for name in sorted(names):
                    if not name.endswith(".yaml"):
                        continue
                    try:
                        item = self._read_yaml(os.path.join(directory, name))
                    except Exception:  # noqa: BLE001 -- an unreadable file is the validator's finding
                        continue
                    if isinstance(item, dict) and item.get("id"):
                        yield item

    def next_hole_number(self) -> str:
        """The number the next hole would get -- the same answer `capture(hole=True)` stamps."""
        with self.lock:
            return "%s%d" % (HOLE_NUMBER_PREFIX, self._max_hole_number_locked() + 1)

    def assert_capturable_as_hole(self, item_type: str) -> None:
        """Refuse to file anything but a hole as one -- the check both surfaces ask.

        HERE AND NOT IN THE CLI, because the CLI is one caller of two: `capture TSK` never reaches
        `capture` at all (it goes through `dispatch.create_task`), so a check that lived only in
        the parser would have to know that, and a check that lived only in `capture` would let
        `--hole` be silently ignored on a work order. So the command surface asks this before it
        chooses a producer, and `capture` asks it again for every other caller.

        WHAT IT IS ASKED OF is `backlog_types.hole_type()` -- the derivation, not a name repeated
        here.
        """
        wanted = hole_type()
        if item_type != wanted:
            raise StateError(
                "a hole is a %s and %s is not one: a measured, open gap is a defect with a named "
                "limit, which is the shape %s carries (its automaton has the accepted-exception "
                "ending, and the `%s` duty is written for it). Filing another type as a hole burns "
                "a hole number nothing can free and leaves the hole judge reading a record whose "
                "status its own automaton does not have. Remedy: capture the gap as %s, or capture "
                "this item without the hole flag."
                % (wanted, item_type, wanted, HOLE_LIMIT_FIELD, wanted))

    def capture(self, item_type: str, fields: dict, hole: bool = False) -> dict:
        """Create a new item: kernel assigns id/status/revision/approval_ref/created.

        `hole=True` says the item is a MEASURED, OPEN GAP (FR-0087, DEC-0073) and makes the kernel
        stamp `HOLE_NUMBER_FIELD`. The caller says THAT it is a hole and never WHICH number it
        gets: a number chosen by a caller is the hand-reserved number FR-0087 exists to end, and a
        body that carries the field is refused for the same reason a body carrying `status` is.
        """
        if hole:
            self.assert_capturable_as_hole(item_type)
        if HOLE_NUMBER_FIELD in fields:
            raise StateError(
                "%s is kernel-set: a hole's number is allocated by max-scan over the store, never "
                "handed in -- hand-reserved numbers are the defect FR-0087 was written for. "
                "Remedy: drop the field and capture with the hole flag; the migration door "
                "`capture_migrated_hole` is the one place a HISTORICAL number is carried over."
                % HOLE_NUMBER_FIELD)
        self.capture_preflight(item_type, fields)
        with self.lock:
            item_id = self.allocate_id(item_type)
            item = {"id": item_id}
            item.update(fields)
            if hole:
                item[HOLE_NUMBER_FIELD] = "%s%d" % (HOLE_NUMBER_PREFIX,
                                                    self._max_hole_number_locked() + 1)
            # ...AND A DATE FIELD IS STORED AS THE DAY IT WAS READ AS -- out of the same reader that
            # refused, so the value checked and the value written are one. Without it two records of
            # the same day sort against each other lexically, because `date.fromisoformat` accepts
            # more than one spelling; `backlog_types.normalised_date` says what stays the
            # interpreter's.
            item.update(_dates_in(item_type, item, "capture"))
            if item_type in _AUTOMATON_TYPES:
                item["status"] = initial_status(item_type)
            elif item_type in _NON_AUTOMATON_INITIAL_STATUS:
                item["status"] = _NON_AUTOMATON_INITIAL_STATUS[item_type]
            # EVD deliberately gets NO status: Evidence never carries its own
            # project status (spec II.2)
            item["revision"] = 1
            item["approval_ref"] = None
            item["created"] = _now_iso()
            # note: this writes the item file and thereby creates the TYPE
            # subdirectory -- item io, not state scaffolding (the state ROOT
            # must already exist; only the installer bootstrap creates it)
            self._write_yaml_atomic(self.active_path(item_id), item)
            self._regenerate_index_locked()
            return item

    def hole_by_number(self, number: str):
        """The stored hole carrying `number`, or None -- the register read back.

        THE IDEMPOTENCE OF THE MIGRATION IS THIS FUNCTION and not a marker file: a run that finds
        the number already stored writes nothing, so a second run over the same document is a
        no-op whatever happened in between, and a half-finished run resumes where it stopped.
        WHAT IT DOES NOT DECIDE is whether the entry is the SAME one -- two streams can reserve one
        number, and telling a resumption from a collision is `tools/migrate_holes.py`'s job
        (`_assert_it_is_the_same_hole`), because only the caller holds the entry to compare with.
        `tools/test_migrate_holes.py::test_a_second_run_over_the_same_document_writes_nothing`
        """
        wanted = str(number or "")
        if not wanted:
            return None
        with self.lock:
            for item in self._iter_every_stored_item():
                if str(item.get(HOLE_NUMBER_FIELD) or "") == wanted:
                    return item
        return None

    def capture_migrated_hole(self, fields: dict, status: str, year: int = None) -> dict:
        """Write ONE hole-list entry into the store at the status its verdict already had.

        WHY A DOOR AT ALL, measured rather than assumed (DEC-0073, sub-question 3): about half the
        entries of the shipped hole list are CLOSED, and a closed hole is a `BUG` at `VERIFIED`.
        `migration_writable_statuses("BUG")` does not reach `VERIFIED` -- the scope approval stands
        in front of it -- so walking those entries through the ordinary edges would need one
        user-minted approval and one test Evidence PER ENTRY. The user chose this door over leaving
        the closed half in the document as a second list.

        THE FOUR BOLTS ON IT, written as what this code CHECKS:
          * it writes a HOLE and nothing else -- the body must carry `HOLE_NUMBER_FIELD`, which
            `capture` refuses to accept from a caller at all, so this is the only way a historical
            number enters the store;
          * it never writes a number the store already carries (`hole_by_number`), which is what
            makes a second run a no-op;
          * the status must be one the type's own automaton HAS, and a TERMINAL one goes to the
            archive while a non-terminal one goes to `active/` -- so nothing is written into a
            place its status does not belong in;
          * the status-dependent duty holds here too: an `ACCEPTED_EXCEPTION` without
            `HOLE_LIMIT_FIELD` is refused, because that field is the whole content of an accepted
            exception.

        WHAT THE DOOR STILL WIDENS, named as a hole with its own number rather than argued away:
        it writes a terminal status -- `VERIFIED` among them -- without the confirming Evidence
        `_assert_confirmed` demands on the walked edge, and without the approval that stands in
        front of it. That is `H154` in `docs/POST_V2_WISHLIST.md`, and what LIMITS it is stated
        there and built here: the record lands in the archive, `report.validate_state` judges the
        ACTIVE items, no gate reads an archived item as an authorisation, and the door cannot
        overwrite anything -- an existing number is refused rather than replaced.
        `tools/test_state.py::test_the_migration_door_writes_a_hole_and_refuses_everything_else`
        """
        item_type = hole_type()
        number = str(fields.get(HOLE_NUMBER_FIELD) or "")
        if not number:
            raise StateError(
                "the hole migration door writes holes only: this body carries no `%s`. Remedy: "
                "use `capture(..., hole=True)`, which allocates one." % HOLE_NUMBER_FIELD)
        automaton = AUTOMATA[item_type]
        if status not in automaton.states:
            raise StateError(
                "%r is no status of %s (states: %s). Remedy: map the entry's verdict onto one of "
                "them." % (status, item_type, ", ".join(sorted(automaton.states))))
        owed = STATUS_DEPENDENT_FIELDS.get((item_type, status))
        if owed and not fields.get(owed):
            raise StateError(
                "a hole written at %s owes `%s` -- what takes the place of the protection. "
                "Remedy: carry the entry's own limit over into that field." % (status, owed))
        existing = self.hole_by_number(number)
        if existing is not None:
            return existing
        self._assert_capture_shape(item_type, fields)
        with self.lock:
            item_id = self.allocate_id(item_type)
            item = {"id": item_id}
            item.update(fields)
            item["status"] = status
            item["revision"] = 1
            item["approval_ref"] = None
            item["created"] = _now_iso()
            if status in automaton.terminals:
                item["closed_at"] = item["created"]
                path = self.archive_path(item_id, int(year or int(item["created"][:4])))
            else:
                path = self.active_path(item_id)
            self._write_yaml_atomic(path, item)
            self._regenerate_index_locked()
            return item

    def capture_migrated_archive_preflight(self, item_type: str, fields: dict, v1_type: str,
                                           v1_status: str, also_existing=()) -> None:
        """Everything `capture_migrated_archive` refuses before it writes -- raised, never written.

        The same split as `capture`/`capture_preflight` and for the same reason: `migrate` has to
        be able to ask the writer's own verdict at PLANNING time, and a planner that asked the
        ordinary `capture_preflight` about an archive-bound record would be told the field contract
        is unmet -- which is exactly the contract this path is exempt from (DEC-0004). A plan that
        measures a check the run does not run is the defect this method exists to prevent.
        """
        self._assert_capture_shape(item_type, fields)
        legacy = fields.get(LEGACY_FIELD)
        if not isinstance(legacy, dict) or not legacy.get("legacy_id"):
            raise StateError(
                "the archive import path is for MIGRATED records only: this body carries no `%s` "
                "with a `legacy_id`, so nothing says where it came from. Remedy: use `capture`, "
                "which enforces the full field contract." % LEGACY_FIELD)
        migration_archive_status(item_type, v1_type, v1_status)
        self._assert_origins_resolve(item_type, fields, also_existing)

    def capture_migrated_archive(self, item_type: str, fields: dict, v1_type: str,
                                 v1_status: str, year: int, also_existing=()) -> dict:
        """Write ONE finished V1 record straight into `archive/<TYPE>/<year>/` (SR-0004/SR-0002).

        WHY THERE IS A SECOND WRITE ENTRY POINT AT ALL. Measured 2026-08-04 across two field
        projects: 260 of 264 tasks in one and 162 of 165 in the other are DONE, and a V1 task
        record is missing TEN of `REQUIRED_FIELDS["TSK"]`'s eleven fields -- `allowed_scope`,
        `expected_outputs`, `assigned_role` and the rest were never collected, not renamed. So the
        import had exactly three options and two of them are worse than this one: writing
        placeholders would hand `gate_write_scope` a sentence instead of leaving it a gap, and
        relaxing the contract in `capture` would make V2's promises untrue for 700+ items with no
        way to see it from outside. DEC-0004 chose the third: the field contract does not apply to
        a record this method writes, because such a record is a PROTOCOL of what happened and not
        a work order anybody will execute again.

        THE THREE BOLTS ON THAT EXEMPTION, written as what this code CHECKS -- and the second one
        is not the bolt SR-0002 asks for. That divergence is stated here rather than smoothed over,
        because a comment that credits a contract with a lock the code does not build is how a
        reader comes to trust the wrong thing:
          * the exemption is reachable through THIS method only. `capture` is untouched and still
            refuses a body missing a required field, so nothing about a normal capture changed.
            (SR-0002's first bolt, built as written.)
          * WHAT THE CODE CHECKS SECOND: the record's V1 status must be one spec II.10's own table
            marks as FINISHED (`archive_candidate`), AND the status it maps to must be one this
            kernel could have walked to without a user approval. Both halves are
            `migration_archive_status`, which is where they are argued; the second is why a V1
            `PRD ACCEPTED` is NOT written here -- it is imported at its initial status like every
            other record, because minting an ACCEPTED PR without an APR is precisely the
            "automatically generated user approval" spec II.10 forbids.
            WHAT SR-0002 ASKS FOR INSTEAD, verbatim: "nur bei Endzustaenden" -- the status must be
            a TERMINAL of the item's own automaton (SR-0004 words it the same way). This code does
            not check that, and the two answers differ in both directions on the shipped tables:
            `TSK DONE` is archived although `DONE` is no terminal of the task automaton, and an
            `SR` mapped to `ACCEPTED` is archived although `SUPERSEDED` is that automaton's only
            terminal. The reason for the replacement is argued at `migration_archive_status`
            (terminality is a property of a live V2 item and says nothing about a 2025 record, and
            reading it that way is what put finished V1 tasks into `tasks/active/`), and the
            replacement is what shipped. SR-0002 and SR-0004 have NOT been rewritten to match --
            they are canonical state and this module may not edit them -- so this is a REPORTED
            contract divergence awaiting a decision, not a re-reading of the contract.
            `test_state.test_the_archive_paths_second_bolt_is_not_the_terminal_check_sr_0002_asks_for`
            measures both directions of it.
          * an item written here is not reactivatable, and that is structural rather than a flag:
            it never exists under `active/`, and this kernel has no operation that moves an item
            out of the archive -- `transition` and `update_item` both resolve through
            `active_path` and answer "no active item". (SR-0002's third bolt, built as written.)

        WHAT THE ITEM RECORDS ABOUT ITS OWN GAPS is stamped HERE, not by the caller, because a
        record of what is missing that the caller composes is a record that can disagree with the
        body it describes: `legacy_fields.missing_required_fields` names every field of the
        contract this body does not carry, and `legacy_fields.kit_version` is what the
        installation says about itself (`report.installed_identity`), so a later reader can tell
        which vocabulary the record was read with.
        """
        self.capture_migrated_archive_preflight(item_type, fields, v1_type, v1_status,
                                                also_existing)
        legacy = fields[LEGACY_FIELD]
        from . import report
        body = dict(fields)
        body[LEGACY_FIELD] = dict(legacy)
        body[LEGACY_FIELD]["missing_required_fields"] = [
            name for name in REQUIRED_FIELDS[item_type] if name not in fields]
        body[LEGACY_FIELD]["kit_version"] = report.installed_identity(self)["kit_version"]
        body[IMPORT_MARK] = True
        with self.lock:
            item_id = self.allocate_id(item_type)
            item = {"id": item_id}
            item.update(body)
            # INSIDE THE LOCK because this call is the archive-path REFUSAL as well as the value,
            # and there is deliberately no second reader of that rule to raise earlier with. An id
            # was allocated by then and nothing was written, so a refusal here leaves the store as
            # it was; the id is not consumed, `allocate_id` re-derives it by max-scan.
            item["status"] = migration_archive_status(item_type, v1_type, v1_status)
            item["revision"] = 1
            item["approval_ref"] = None
            item["created"] = _now_iso()
            self._write_yaml_atomic(self.archive_path(item_id, int(year)), item)
            self._regenerate_index_locked()
            return item

    def capture_migrated_unresolved_preflight(self, item_type: str, fields: dict,
                                              also_existing=()) -> None:
        """Everything `capture_migrated_unresolved` refuses before it writes -- raised, never
        written. Same split, same reason, as the two preflights above."""
        self._assert_capture_shape(item_type, fields)
        legacy = fields.get(LEGACY_FIELD)
        if not isinstance(legacy, dict) or not legacy.get("legacy_id"):
            raise StateError(
                "the unresolved-import path is for MIGRATED records only: this body carries no "
                "`%s` with a `legacy_id`, so nothing says where it came from. Remedy: use "
                "`capture`, which enforces the full field contract." % LEGACY_FIELD)
        # A SENTENCE, not merely something truthy. `str(x) or ""` accepted `True`, a number and a
        # list -- each of which reads as "why" to this check and as nothing at all to the person
        # who later opens the archived item looking for the reason it is there.
        reason = legacy.get("unresolved")
        if not isinstance(reason, str) or not reason.strip():
            raise StateError(
                "the unresolved-import path writes a record NOBODY could translate, so the item "
                "has to say why: `%s.unresolved` is %s and this path needs a sentence. Remedy: "
                "this is a caller bug -- `migrate` composes that sentence out of the fields the "
                "record could not fill."
                % (LEGACY_FIELD, "empty" if isinstance(reason, str) else "%r" % (reason,)))
        self._assert_origins_resolve(item_type, fields, also_existing)

    def capture_migrated_unresolved(self, item_type: str, fields: dict, year: int,
                                    also_existing=()) -> dict:
        """Write ONE V1 record no answer could translate into `archive/<TYPE>/<year>/` (DEC-0009).

        THE SECOND ARCHIVE DOOR, and it is a different question from the first one. The door above
        takes a record whose LIFE IS OVER, as the V1 vocabulary itself recorded it, and writes it at
        the status that life ended in. This one takes a record that is still whatever V1 said it
        was, and whose V2 required fields have no source anywhere -- neither spelled the same, nor
        named by a `--map`, nor covered by a suggestion. DEC-0009's decision is that such a record
        is archived with its reason rather than blocking the whole run, because the alternative was
        measured: five hardening rounds spent on refusal messages for a command that runs three
        times, while the real projects stayed unmigrated beside them.

        THE STATUS IS THE TYPE'S INITIAL ONE, never the mapped V1 value, and that is what keeps
        this door from being a way past the approval bolt `migration_archive_status` builds: an
        initial status is what `capture` itself writes and is reachable without any approval by
        construction. What V1 said is kept in `legacy_fields.legacy_status`, unwalked, exactly as
        on the ordinary import path.

        WHAT IS LOST, named because DEC-0009 names it: a record ONE field decision would have saved
        is archived here, and this kernel has no operation that moves an item back out of the
        archive. The mitigation is not in this method -- it is that `migrate`'s dry run lists every
        record this door would take, with the fields it could not fill, BEFORE anything is written,
        and that the field suggestions (SR-0007) run first.
        """
        self.capture_migrated_unresolved_preflight(item_type, fields, also_existing)
        from . import report
        body = dict(fields)
        body[LEGACY_FIELD] = dict(fields[LEGACY_FIELD])
        body[LEGACY_FIELD]["missing_required_fields"] = [
            name for name in REQUIRED_FIELDS[item_type] if name not in fields]
        body[LEGACY_FIELD]["kit_version"] = report.installed_identity(self)["kit_version"]
        body[IMPORT_MARK] = True
        with self.lock:
            item_id = self.allocate_id(item_type)
            item = {"id": item_id}
            item.update(body)
            if item_type in _AUTOMATON_TYPES:
                item["status"] = initial_status(item_type)
            elif item_type in _NON_AUTOMATON_INITIAL_STATUS:
                item["status"] = _NON_AUTOMATON_INITIAL_STATUS[item_type]
            item["revision"] = 1
            item["approval_ref"] = None
            item["created"] = _now_iso()
            self._write_yaml_atomic(self.archive_path(item_id, int(year)), item)
            self._regenerate_index_locked()
            return item

    def update_item(self, item_id: str, changes: dict) -> dict:
        """Edit an item through the kernel. Changing a hashed field of an item
        with a current approval invalidates it ATOMICALLY (spec II.2)."""
        with self.lock:
            return self._update_item_locked(item_id, changes)

    def _update_item_locked(self, item_id: str, changes: dict) -> dict:
        """update_item body for callers that ALREADY hold the lock (the lock is
        not reentrant); e.g. staging.freeze_design keeps read+update in ONE hold
        (Fable-Check 11/BUG-1: no lost-update window)."""
        item_type, _ = parse_id(item_id)
        forbidden = [k for k in changes if k in ("id", "status", "revision", "approval_ref", "created")]
        if forbidden:
            raise StateError(
                "fields %s change only through their kernel operations "
                "(transition/approve). Remedy: use the dedicated command."
                % ", ".join(forbidden)
            )
        item = self.read_item(item_id)
        if item_type in IMMUTABLE_TYPES and changes:
            # A record is superseded, never corrected -- see IMMUTABLE_TYPES for why
            # the type has no other way to change. Measured before this existed: an
            # `EVD` whose `result` was edited from `fail` to `pass` reopened a merge
            # `gate_git` had closed, and an edited `related` bound a failing verdict
            # to a different item; neither left an item behind to notice.
            raise StateError(
                "%s is a %s -- a record of something that already happened, so none of "
                "its fields change (spec II.2). Remedy: record the new run as its own "
                "item (`python scripts/harness.py evidence ...`, run from the project root "
                "and never with --root), which supersedes this one; archive this one "
                "afterwards if it should also leave the active store. Both are visible in "
                "git, an edit is not." % (item_id, item_type)
            )
        # the SANCTIONED edit path has to enforce the same rules as capture: otherwise
        # an orchestrator that hits the capture-time refusal simply re-types the task
        # afterwards, and the design_ref rule stops applying. The same holds for a
        # binding -- `derives_from` rewritten to a phantom id makes the task's
        # acceptance criteria resolve against nothing, exactly as it would at capture.
        _assert_closed_vocabularies(item_type, changes)
        _assert_single_value_fields(item_type, changes)
        self._assert_origins_resolve(item_type, changes)
        # THE SAME DATE READER AS THE CAPTURE PATH, and applied to `changes` BEFORE the hashed-field
        # comparison below: a re-spelling of the day the item already carries (`20261225` for a
        # stored `2026-12-25`) is then not a change at all, so it neither bumps a revision nor
        # invalidates an approval for a value that did not move.
        changes = dict(changes, **_dates_in(item_type, changes, "update"))
        planning_status = initial_status(item_type) if item_type == "TSK" else None
        if planning_status is not None and item.get("status") != planning_status:
            # ... and closing the vocabulary is not enough on its own: a
            # vocabulary-LEGAL re-type dodges the design gate just as well, and
            # widening allowed_scope on a LEASED, BOUND task hands a running
            # specialist the whole repo. The work-order contract is frozen once
            # the task leaves the status it was PLANNED in (see TSK_PLAN_FIELDS).
            # THE PLANNING STATUS IS THE AUTOMATON'S INITIAL ONE, asked rather than spelled, for
            # BUG-0089's reason: the remedy below is derived from the same fact, so the condition
            # and the advice cannot come to disagree about which status frees the fields.
            frozen = sorted(set(changes) & TSK_PLAN_FIELDS)
            if frozen:
                raise StateError(
                    "%s is %s -- its work-order fields (%s) are frozen outside %s because gates "
                    "read them (allowed_scope is the write-scope gate's only input). Remedy: %s -- "
                    "re-planning has to be visible, not a field write."
                    % (item_id, item.get("status"), ", ".join(frozen), planning_status,
                       _replanning_remedy(item_id, item_type, item.get("status"), planning_status))
                )
        hashed = set(HASHED_FIELDS.get(item_type, ()))
        touches_hashed = any(
            key in hashed and item.get(key) != value
            for key, value in changes.items()
        )
        item.update(changes)
        if touches_hashed and item.get("approval_ref"):
            item["revision"] = int(item.get("revision", 1)) + 1
            item["approval_ref"] = None
            item["status"] = invalidation_target(item_type)
        self._write_yaml_atomic(self.active_path(item_id), item)
        self._regenerate_index_locked()
        return item

    def record_invariant_verification(self, item_id: str) -> tuple:
        """Set an INV's status from what its `check` RESOLVES TO -- the producer II.12 lacked.

        NOT A TRANSITION, and that is the decision rather than a workaround for `INV` having no
        automaton. Every other status in this kernel records a DECISION -- someone approved,
        someone delivered -- and the automaton exists so that a decision cannot skip its
        predecessor. `verified` records a MEASUREMENT of the repository: the check names a test and
        the test is there. A role may not choose it, and neither may this method: the value comes
        from `report.invariant_check_resolution` and the caller passes no status at all.

        THEREFORE BOTH DIRECTIONS. A check that stops resolving -- a renamed or deleted test --
        takes the item back to `unverified` on the next run, because a verification that outlives
        its evidence is worse than none: `report._check_invariant_checks` blocks the merge on the
        unresolvable check either way, and an item left reading `verified` beside that error is
        the state telling a reader two different things.

        RETURNS `(item, resolved, reason)` and not just the item, because `unverified` covers
        two different facts -- "the test is not there" and "this kernel cannot read the file" --
        and a caller that wants to act differently on them (`kernel.cli`'s exit code does) would
        otherwise have to resolve the check a second time, on a store that may have moved.

        `tools/test_state.py::test_an_invariant_is_verified_by_its_check_and_unverified_when_it_
        stops_resolving` measures both directions.
        """
        item_type, _ = parse_id(item_id)
        if item_type != "INV":
            raise StateError(
                "%s is not an invariant: only an INV carries a check to verify. Remedy: move the "
                "item's status with `transition`." % item_id)
        from . import report as _report
        with self.lock:
            item = self.read_item(item_id)
            resolved, reason = _report.invariant_check_resolution(self, item)
            # `resolved is True` and not truthiness: the reader answers None for a check it
            # cannot read at all (a test file in another language), and an invariant this kernel
            # cannot confirm stays unverified -- it may not be verified on a shrug, and the
            # validator says so as a warning rather than blocking a merge on it (`H110`).
            item["status"] = INVARIANT_STATUSES[1 if resolved is True else 0]
            self._write_yaml_atomic(self.active_path(item_id), item)
            self._regenerate_index_locked()
            # The reason goes into no FIELD: the item's contract declares none for it, and a
            # note stored beside a status is a second place for one fact to go stale. The caller
            # prints it; the validator derives the same sentence again.
            return item, resolved, reason

    def transition(self, item_id: str, to_status: str, approved_retry: bool = False) -> dict:
        with self.lock:
            return self._transition_locked(item_id, to_status, approved_retry)

    def _transition_locked(self, item_id: str, to_status: str,
                           approved_retry: bool = False) -> dict:
        """transition body for callers that ALREADY hold the lock (it is not reentrant).

        THE ONLY WRITER OF A STATUS AN APPROVAL COMMITS, which is a narrower claim than the one
        this kernel used to make and is the one it can keep. `approvals.mint` set
        `item["status"]` directly and thereby skipped the automaton -- and would have skipped the
        approval check -- on the single path that moves a root item most often; it comes through
        here now. OTHER WRITERS REMAIN, and they are described rather than listed -- a list here
        said "the TSK dispatch lifecycle, four functions" and the AST finds seven sites, because
        `capture` (the initial status) and `_update_item_locked` (the approval-invalidation reset
        spec II.2 requires to be atomic) write one too. The property that holds is not "there are
        four" but: every status any of them can produce is bounded from a kernel map, and none of
        those values is a status an approval commits.
        `test_no_direct_status_write_can_produce_a_status_an_approval_commits` derives that from
        the running source -- it enumerates the writers itself, bounds each one's possible values
        and compares them against `APPROVAL_TRANSITIONS`, so a new writer needs no edit here and a
        new writer that could produce APPROVED/IN_DELIVERY/ACCEPTED turns it red.

        FOUR things stand between a status and its new value, and they are four because their
        evidence lives in four different places:
          * the AUTOMATON (`assert_transition`) -- is this edge defined at all;
          * the TSK retry rule (`RETRY_APPROVAL_EDGE`) -- its evidence is a caller argument, because
            spec II.2 records the retry approval as a Querregel and no APR kind has a manifest for
            it. The edge is a datum rather than a condition here, because
            `migration_writable_statuses` has to read the same one;
          * the APPROVAL (`approvals.assert_transition_approved`) -- derived from
            `APPROVAL_TRANSITIONS`, so which edges it guards follows from which edges an approval
            commits, rather than from a list kept beside it;
          * the CONFIRMING EVIDENCE (`_assert_confirmed`) -- the edge from
            `backlog_types.confirming_edge`, the proof from `CONFIRMING_EVIDENCE`.
        """
        item_type, _ = parse_id(item_id)
        item = self.read_item(item_id)
        from_status = item.get("status")
        assert_transition(item_type, from_status, to_status)
        if (item_type,) + (from_status, to_status) == RETRY_APPROVAL_EDGE and not approved_retry:
            raise TransitionError(
                "%s %s -> %s requires an approved retry (spec II.2 "
                "Querregeln). Remedy: obtain the retry approval, then call "
                "transition with approved_retry=True." % RETRY_APPROVAL_EDGE
            )
        # A lease-bearing status is ESTABLISHED by a real lease, not by this path (DEC-0038/
        # BUG-0010): the dispatch lifecycle sets LEASED/IN_PROGRESS directly and never comes through
        # here, so a direct transition INTO one of them with no live lease is the untrue bookkeeping
        # -- LEASED without a lease -- that a later lease sweep would be asked to reconcile. The
        # enforcing reader is dispatch.assert_lease_backed_transition_locked; deferred import for the
        # same cycle reason the approvals and dispatch modules are imported deferred below.
        from . import dispatch as _dispatch
        _dispatch.assert_lease_backed_transition_locked(self, item_id, to_status)
        # DEFERRED import: `approvals` imports this module at its own module scope, so a top-level
        # import here would be a cycle. By the time any transition runs, both halves are loaded.
        from . import approvals
        apr = approvals.assert_transition_approved(self, item, item_type, from_status, to_status)
        self._assert_confirmed(item_id, item_type, from_status, to_status)
        # THE APPROVAL THIS ITEM NOW PRESENTS. `mint` stamps `approval_ref` itself before it walks
        # its own edge, so for that path this is already true and writes nothing. It matters for
        # the edge a PLAN approval commits (FR-0074): nothing mints per goal there, so without
        # this line a goal would walk to APPROVED presenting no approval at all -- and
        # `dispatch._assert_root_approval_locked` reads exactly that field, so every task under
        # the goals a plan covers would be refused for want of an approval that exists.
        if apr is not None and item.get("approval_ref") != apr.get("id"):
            item["approval_ref"] = apr["id"]
        item["status"] = to_status
        self._write_yaml_atomic(self.active_path(item_id), item)
        # A DISPATCH LEASE IS BOUND TO THE STATUS IT SERVES. Deferred import for the same reason
        # `approvals` is deferred: `dispatch` imports this module. Without this, `transition
        # TSK-0001 READY` off LEASED left a live lease behind that `create_lease` then refused the
        # task on for its whole TTL, and `validate` called that state green -- see
        # `dispatch.release_lease_for_status_locked` for the measurement.
        from . import dispatch
        dispatch.release_lease_for_status_locked(self, item_id, to_status)
        self._regenerate_index_locked()
        return item

    def _assert_confirmed(self, item_id, item_type, from_status, to_status):
        """A confirming edge needs the proof `CONFIRMING_EVIDENCE` names, in force RIGHT NOW.

        `report.qa_verdicts` is asked rather than the Evidence store scanned here, and that is the
        whole point of routing through it: it already answers "which Evidence covers this item"
        (`evidence_covers`, including the indirect hop from a task to its root) and "which of
        several counts" (newest per kind supersedes). A second reader of the same store would be a
        second answer to the same question.

        IT ASKS THE CONFIRMATION QUESTION AND NOT THE DELIVERY ONE (BUG-0090, DEC-0071). Measured on the
        shipped kernel: a `pass` that declared `run_scope: selection` and named the BUG was dropped
        by the delivery filter, so this edge refused with "there is none" -- while its own remedy
        below asks for the regression run, which is a selection by nature; the SAME run recorded
        without the declaration walked, so the record that said more about itself was the one
        punished. The two questions and why only one of them filters a passing selection are at
        `report.DELIVERY_QUESTION`. The merge gate keeps the delivery reading, so a passing
        selection still opens no merge -- and a BUG that reaches VERIFIED on one is therefore no
        longer the same thing as a merge `gate_git` would let through.
        `tools/test_state.py::test_a_declared_regression_run_confirms_the_bug_it_names`

        It is lock-safe from inside `_transition_locked` because `report._delivery_evidence` takes
        no lock, by its own design note; the kernel lock is not reentrant, so a reader that did
        would deadlock every transition.
        """
        kind = CONFIRMING_EVIDENCE.get(item_type)
        if not kind or (from_status, to_status) != confirming_edge(item_type):
            return
        from . import report
        verdict = report.qa_verdicts(self, item_id, report.CONFIRMATION_QUESTION).get(kind)
        if verdict and verdict.get("result") == PASSING_RESULT:
            return
        raise TransitionError(
            "%s %s -> %s needs a %r Evidence that PASSES and covers %s; %s. The regression test "
            "is what turns a fix into a verification -- without it the status says the bug is gone "
            "and nothing measured that. Remedy: run the test that fails before the fix and passes "
            "after it, then record the run: `python scripts/harness.py evidence --kind %s "
            "--result pass --related %s --summary ... --artifact-ref <path to the raw proof>`, "
            "from the project root."
            % (item_id, from_status, to_status, kind, item_id,
               "the current %r verdict is %r" % (kind, verdict.get("result")) if verdict
               else "there is none",
               kind, item_id))

    def archive(self, item_id: str) -> str:
        """Move a TERMINAL item to archive/<TYPE>/<year>/ (never delete)."""
        item_type, _ = parse_id(item_id)
        with self.lock:
            item = self.read_item(item_id)
            if item_type in _AUTOMATON_TYPES and not is_terminal(item_type, item.get("status")):
                raise StateError(
                    "%s is %s -- only terminal items are archived (spec II.2). "
                    "Remedy: finish the lifecycle first, or CANCEL/REJECT it "
                    "via transition." % (item_id, item.get("status"))
                )
            item["closed_at"] = _now_iso()
            year = int(item["closed_at"][:4])
            target = self.archive_path(item_id, year)
            self._write_yaml_atomic(target, item)
            os.remove(ext_path(self.active_path(item_id)))
            self._regenerate_index_locked()
            return target

    # -- generated index (atomic within the state operation, spec II.4) --------

    def generate_index(self) -> str:
        with self.lock:
            return self._regenerate_index_locked()

    def _regenerate_index_locked(self) -> str:
        """Rewrite `generated/index.yaml` AND the board beside it, from one reading of the store.

        THE BOARD IS WRITTEN HERE AND NOWHERE ELSE (FR-0030). Every kernel writer that regenerates
        the index arrives in this method, so the human-readable view is REBUILT WITH the index --
        a second trigger is a second thing to forget, and the measured baseline of the shipped
        dashboard was exactly that: nothing ran it, so it was stale by default.
        `test_board.test_every_state_write_leaves_a_board_as_fresh_as_the_index` drives real
        writers through it; `kernel.board` is what the page itself is.

        "REBUILT WITH" AND NOT "NEVER OLDER THAN", because `_write_board` below is deliberately
        fail-soft and therefore builds the counter-case itself: a rebuild that cannot finish says
        so on stderr and leaves the page -- with its own, now older, timestamp -- where it was.
        Which is the honest claim is decided there, not here.

        The item BODIES this loop already reads travel to the renderer, so the second reader the
        board would otherwise need does not exist and the two cannot report different states.
        """
        rows = []
        entries = []
        for item_type in sorted(ACTIVE_DIRS):
            # through `iter_active_items`, not a second listing of the same directory: the index
            # is what the dashboard and every "what is open" reader work from, and with its own
            # copy of the rule it listed a twice-frozen wireframe as two rows carrying one id
            for stem, path in self.iter_active_items(item_type):
                try:
                    item = self._read_yaml(path)
                except Exception:
                    item = None
                if not isinstance(item, dict):
                    row = {"id": stem, "type": item_type, "corrupt": True}
                    rows.append(row)
                    entries.append((row, None))
                    continue
                row = {
                    "id": item.get("id", stem),
                    "type": item_type,
                    "title": item.get("title"),
                    "status": item.get("status"),
                    "revision": item.get("revision"),
                    "approval_ref": item.get("approval_ref"),
                }
                if item.get("blocked_by"):
                    row["blocked_by"] = item["blocked_by"]
                rows.append(row)
                entries.append((row, item))
        # ONE timestamp for both files, so "the board is as old as the index" is a fact a reader can
        # check rather than a claim: two calls to the clock would differ by a second often enough.
        generated_at = _now_iso()
        index_path = self.generated_path("index.yaml")
        self._write_yaml_atomic(index_path, {"generated_at": generated_at, "items": rows})
        self._write_board(entries, generated_at)
        return index_path

    def _write_board(self, entries: list, generated_at: str) -> None:
        """Render `generated/<board.FILENAME>` -- and never let it fail a state write.

        FAIL-SOFT, AND THIS IS THE ONE PLACE IN THE KERNEL WHERE THAT IS THE RIGHT ANSWER. The
        index above is state: if it cannot be written, the operation must fail. The board is a
        REPORT of that state and it is written AFTER the item and after the index, so an exception
        here would report a write that had already happened as failed -- and, because this method
        runs on EVERY state write over ALL items, one file the renderer cannot cope with would fail
        every later capture in that project with a traceback whose only apparent remedy is the hand
        edit the gates refuse. Measured instances: a lone surrogate in any field, and a board file
        another process holds open (Windows `os.replace`).

        WHAT IT COSTS AND HOW THAT IS PAID: a silent failure would be a stale page nobody doubts.
        So the failure is SAID -- on stderr, which belongs to the caller's own error channel --
        and the page keeps its own timestamp for comparison. `board._card` catches per item and
        names the id ON the page; this catches what is left, which is the write itself.
        `test_board.test_a_board_that_cannot_be_written_does_not_fail_the_state_write` carries it.
        """
        try:
            self._write_text_atomic(self.generated_path(board.FILENAME),
                                    board.render(self, entries, generated_at),
                                    errors="replace")
        except Exception as exc:                  # noqa: BLE001 -- see the docstring
            # `print(..., file=sys.stderr)` and NOT `sys.stderr.write`, which is the spelling one
            # would reach for: `test_approvals_dispatch.test_the_store_has_exactly_one_writer_for
            # _this_derivation_to_rest_on` derives every route into the store from the functions of
            # this module that call something write-shaped, and a `.write` here would make this
            # method look like a second byte writer beside `_write_text_atomic`. `kernel.cli` uses
            # the same spelling for the same output.
            print("[board] %s was NOT rebuilt (%s: %s); the state write itself went through and "
                  "%s is current. The page keeps its previous timestamp — read that, not this "
                  "board, until the next state write succeeds."
                  % (self.generated_path(board.FILENAME), type(exc).__name__, exc,
                     self.generated_path("index.yaml")), file=sys.stderr)
        # THE DIAGRAMS ARE THE SAME REPORT OF THE SAME ENTRIES and are written here, fail-soft for
        # the reason above -- but in a `try` OF THEIR OWN, because the message above names the
        # board, and a board that WAS rebuilt must not be reported as lost by a picture that was
        # not. Until TSK-0120 nothing in a running project called `plan_diagram` at all: the module
        # had no caller outside its tests, which is the half of `H127` that closes with this line.
        # Both ends:
        # `tools/test_plan_diagram.py::test_a_state_write_leaves_both_diagrams_beside_the_board`.
        try:
            for name, text in plan_diagram.render_all(entries):
                self._write_text_atomic(self.generated_path(name), text, errors="replace")
        except Exception as exc:                  # noqa: BLE001 -- as above
            print("[plan] the diagrams beside %s were NOT rebuilt (%s: %s); the state write itself "
                  "went through and %s is current. The pictures keep their previous content — read "
                  "the board, not them, until the next state write succeeds."
                  % (self.generated_path(board.FILENAME), type(exc).__name__, exc,
                     self.generated_path("index.yaml")), file=sys.stderr)


# THE TYPES THAT CARRY AN AUTOMATON, asked of the map that IS the automata rather than listed
# beside it. This was a hand-written tuple of ten names that happened to equal `AUTOMATA`'s keys,
# and the day an eleventh type arrived (`MST`, DEC-0064) the two came apart in the quietest
# possible way: `capture` wrote the item with NO status at all, `archive` then read it as
# non-terminal, and nothing raised. Measured before the change, in a pilot outside the repo --
# `capture("MST", ...)` returned an item whose `status` key did not exist.
# `tools/test_state.py::test_every_type_with_an_automaton_is_captured_with_its_initial_status`
# holds it from both ends.
_AUTOMATON_TYPES = frozenset(AUTOMATA)

# status-bearing types WITHOUT an automaton (spec II.2 Pflichtfelder): the FIRST value of each
# vocabulary in `backlog_types.NON_AUTOMATON_STATUSES`, derived rather than retyped -- the two
# used to be one map here and one sentence in a comment, and the comment was the only place a
# reader could learn that `DEC` also has `SUPERSEDED`.
_NON_AUTOMATON_INITIAL_STATUS = {item_type: values[0]
                                 for item_type, values in NON_AUTOMATON_STATUSES.items()}

# THE TWO STATES AN INVARIANT CAN BE IN, read out of the same vocabulary and in its declared order
# (unverified first). `record_invariant_verification` picks one of them BY MEASUREMENT, which is
# why they are a pair here and not two literals at the write: the value is never a caller's choice.
# Read as a bound on that writer by
# `tools/test_approvals_dispatch.py::test_no_direct_status_write_can_produce_a_status_an_approval_commits`,
# which refuses any status write in this kernel whose range it cannot derive from a kernel map.
INVARIANT_STATUSES = tuple(NON_AUTOMATON_STATUSES["INV"])


# Which field an item names its parent through is `backlog_types.PARENT_FIELDS`,
# derived there from the type's field contract -- the SAME definition the reference
# graph in `report` walks, so a binding the graph resolves and a binding the write
# path checks can no longer be two different sets. What lives here is only the
# REMEDY: one sentence per type whose refusal a role meets mid-command.
_BINDING_REMEDY = {
    "TSK": "name the item this task derives from (the PR/RQ, or the BUG/CR/EXP "
           "whose criteria it serves)",
    "EVD": "name the item this evidence examined (the TSK it judged, or the "
           "PR/RQ/EXP it covers)",
}
_BINDING_REMEDY_DEFAULT = "put the id of the item this one belongs to in `%s`"

# What to DO about an empty NONEMPTY_FIELDS entry, per type -- one sentence naming
# the arguments, because the role hitting this refusal is mid-command.
_NONEMPTY_REMEDY = {
    "EVD": "pass `--related <ITEM-ID>` for the item you examined and "
           "`--artifact-ref <path>` for the raw proof, state-relative "
           "(`staging/<task-id>/coverage.html`). A verdict with nothing to point at "
           "is an assertion, and the merge gate would open on it.",
    "TSK": "pass `--expected-output <path or artefact>` for every result the order is "
           "measured against (or `expected_outputs: [...]` in the body). An order that "
           "expects nothing is met by any package, so nothing can verify it (BUG-0023).",
}
# The sentence for a type the map above does not name -- so widening `NONEMPTY_FIELDS` by a type
# refuses with a remedy instead of a KeyError (measured red by
# `test_report.test_validate_names_a_stored_order_that_expects_nothing`, whose second half widens it).
_NONEMPTY_REMEDY_DEFAULT = "name at least one entry in the field."

# Fields whose value must come from a CLOSED vocabulary, per type. Every one of
# them is read by a gate to DECIDE something, which is what closing them buys:
# see TASK_TYPES (design_ref rule, II.6) and EVIDENCE_KINDS/EVIDENCE_RESULTS
# (merge gate, II.10a). Anything not listed here is free-form by intent.
_CLOSED_VOCABULARY = {
    ("TSK", "type"): (TASK_TYPES,
                      "the type is a gate input (a UI task needs a design_ref)"),
    ("EVD", "kind"): (EVIDENCE_KINDS,
                      "the kind decides whether this evidence judges a delivery "
                      "or the project, and the merge gate only accepts the former"),
    ("EVD", "result"): (EVIDENCE_RESULTS,
                        "the verdict is what the merge gate reads; an unknown "
                        "value is not a fail, so the gate would go quiet"),
    ("EVD", "run_scope"): (RUN_SCOPES,
                           "the scope decides whether a PASS is merge evidence at all "
                           "(`report._delivery_evidence`), and an unknown value would "
                           "read as neither -- the run would open the merge unexamined"),
}


def _assert_closed_vocabularies(item_type: str, fields: dict) -> None:
    """Refuse a value outside its field's closed vocabulary (see _CLOSED_VOCABULARY).

    Called from capture AND from the edit path, because a value refused at capture
    and then written by an edit is not refused at all. A free-text value would not
    FAIL the gate that reads it -- it would silently skip it, which is the failure
    both vocabularies exist to prevent.

    On the edit path only `TSK.type` can actually arrive here: an `EVD` is refused
    wholesale a few lines earlier (IMMUTABLE_TYPES), so the two EVD entries below
    are capture-only in practice. That is a fact about EVD and not a reason for
    this check to know which type it is judging -- the same argument the
    neighbouring `_assert_origins_resolve` makes, and the reason a later type with
    a closed field needs no second edit-path wiring.
    """
    for (owner, field), (allowed, why) in _CLOSED_VOCABULARY.items():
        if owner != item_type or field not in fields:
            continue
        if fields.get(field) not in allowed:
            raise StateError(
                "unknown %s %s %r. Remedy: use one of %s -- %s, so a free-text "
                "value would skip that check instead of failing it."
                % (item_type, field, fields.get(field),
                   ", ".join(sorted(allowed)), why)
            )


def _assert_single_value_fields(item_type: str, fields: dict) -> None:
    """Refuse a `backlog_types.SINGLE_VALUE_FIELDS` field spelled as several things (DEC-0043).

    LOUD RATHER THAN NORMALISED, which is a decision and not a preference about strictness: every
    shipped reader of such a field reads ONE value, so the several-things spelling is taken happily
    and then reaches nobody. H42 measured what that costs -- the same project's coverage rule went
    from refusing an untested push to allowing it, and nothing anywhere said a word. Normalising
    instead would mean one INV governs SEVERAL areas, and that is the branch DEC-0043 rejected.

    ON THE TWO DOORS INTO THE **ACTIVE** STORE ONLY, `capture_preflight` and the edit path, and not
    in `_assert_capture_shape` where the neighbouring vocabulary check sits. For today's one entry
    that placement changes nothing either way and the honest reason says so: no shipped command
    reaches an archive door with an `INV` at all -- `V1_STATUS_MAPPING` produces eleven V2 types and
    `INV` is not among them, so the doors are a kernel surface only. The placement is DISCIPLINE FOR
    THE NEXT ENTRY, whose type migration may well produce: an archive-bound record is a PROTOCOL of
    what happened, DEC-0004 exempts it from the field contract for that reason, and DEC-0009 has the
    unresolved ones archived WITH THEIR REASON rather than stopping a run -- a shape refusal there
    would stop it, and it would guard nothing, because no reader of these fields scans
    `archive/<TYPE>/<year>/`. That the archive door still takes such a body is
    `test_state.test_the_archive_door_still_takes_a_record_the_active_door_refuses`.

    The remedy the refusal carries is the one `report._check_single_value_fields` gives an item
    already written that way; both read `single_value_offences`.
    `test_state.test_a_several_things_inv_scope_is_refused_at_capture_and_on_the_edit_path`.
    """
    for field, why, remedy in single_value_offences(item_type, fields):
        raise StateError(
            "%s %s holds ONE thing and this body's value is not one (a %s): %s, and anything "
            "else reaches them as its own PRINTED form, which matches nothing -- the item would "
            "be written and the rule it states would guard nothing (DEC-0043, H42). Remedy: %s."
            % (item_type, field, type(fields[field]).__name__, why, remedy))


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")
