"""The V1 -> V2 import (spec II.10), as a kernel operation rather than a script beside the harness.

WHY IT IS A KERNEL COMMAND AND NOT A TOOL. A migration rewrites canonical state, and every other
writer of canonical state in this harness goes through `ProjectState`: the status automaton, the
approval hashes, the id allocator and the index all hang off it. A migration tool living outside
would be the one write route no gate sees -- `gate_write_scope` refuses tool writes under the state
directory precisely so that there is exactly one, and a second one carrying the word "migration"
would not be a smaller hole for being well meant. So the import is `migrate` on the entry point,
the lead runs it itself, and everything it writes is written by the same `capture` a role uses.

WHAT IT TRANSLATES, as a property rather than as a list of file names. The kernel does not know
what a "V1 file" is and deliberately never learns: it knows what a V1 RECORD is.

    A V1 record is a mapping that identifies itself with a `<TYP>-nnnn` id -- as its key in an
    enclosing mapping, or in its own `id` field -- and carries a `status`. It is TRANSLATABLE
    exactly when `backlog_types.map_v1_status` answers for `(TYP, status)`.

WHERE THE MAPPING LIES IS NOT PART OF THAT DEFINITION, and for one revision the code read it as if
it were: the `id` field was consulted for LIST members only, so a mapping sitting in a value
position under an ordinary key and naming itself in its own `id` field was found by nobody. See
`scan_document` for the measurement and for what the two positions now share.

That table is spec II.10's own, it is machine-readable, and it is the only place in this harness
where a V1 vocabulary is written down. Everything follows from it: `process_definitions.yaml`,
`tasks.yaml` and `product_requirements.yaml` are found because of what is INSIDE them, and a V1
kit whose monolith this code has never seen is found the same way.

WHEN THE TABLE HAS NO ANSWER THERE ARE TWO DIFFERENT FINDINGS, and telling them apart decides
whether a project can be migrated at all. A type the table HAS rows for, with a status it does not
know, is a backlog record this harness does not understand: the run BLOCKS (spec II.10: "unbekannte
Werte -> Block + Decision-Item, nie raten"). A type with no row anywhere is not a backlog record --
a dev project's `acceptance_reports.yaml` keys each report `ACC-nnnn` and each criterion of it
`AC-<n>` with a `status`, and the first cut of this module treated those as unmappable backlog
items and blocked the whole migration of a project whose QA reports were simply QA reports. Such a
record is REPORTED and skipped, never imported and never a blocker. That example is measured, not
imagined: `_is_backlog_type` names the field reading it comes from.

EVERYTHING CARRYING THE ID SHAPE IS REPORTED, whether or not it is translated. That is the whole
promise of the reading half, and it has no depth limit, no "found one, stop looking here" and no
silent skip: a document this command cannot parse for records is named as unsearched, an
unreadable one refuses the run, and a record nested inside another record is found. Silence about
something id-shaped is the one outcome that would make the report unusable, because a reader
cannot tell it from an absence. WHICH FILES THAT COVERS IS NOT DECIDED HERE AND NOT DECIDED TWICE:
`search_coverage` gives every file under the state root exactly one verdict, this command and the
SR-0001 scan in `report` both read it, and what it names as unsearched and what it deliberately
leaves out -- with the residual that leaves -- is argued there rather than restated here.

WHAT IT REFUSES TO DECIDE, and this is the half the command exists for. A V1 record's FIELDS do not
map onto a V2 type's field contract by any rule anybody has written down, in this repo or in the
spec. `REQUIRED_FIELDS["PROC"]` asks for `roles`; a V1 PROC carries `owner`. Guessing that those
are the same field is exactly the kind of quiet decision that makes a migration unreviewable, so
this module does not: a field carries over when BOTH contracts spell it the same way, and every
remaining required field is reported as a decision with the `--map` flag that would settle it. The
dry run prints those flags; the human types them; the executed run is then mechanical. ONE
EXCEPTION, and it is not a decision about the record: a required field whose subject is where the
record CAME FROM is the importer's own fact -- see `PROVENANCE_FIELDS` for why that is a field name
rather than a type, and why leaving it to `--map` would have been a dead end.

WHAT AN IMPORTED ITEM LOOKS LIKE, and why it is not the V1 status. Spec II.10 asks that imported
items keep their regular initial status, carry a mark saying they were imported and carry
`approval_ref: null` -- no new status, and only a real user action mints an APR. The mark's NAME is
this harness's, not the spec's demand, and it was changed (DEC-0021): it said
`migration_confirmation_required`, which promised a confirmation duty no reader in this kernel, in
the hooks, in the session brief or in the dashboard enforces. `backlog_types.IMPORT_MARK` is the
name and the argument. So an imported PROC
arrives in DRAFT even when V1 called it ACTIVE, the V1 value and the whole V1 record are preserved
verbatim under `legacy_fields`, and `map_v1_status`'s answer is recorded there as what the V1
status WOULD mean -- a note, not a position on the automaton. The consequence is worth stating
plainly rather than discovering: this command does not unblock `gate_proc_approved`. It makes the
procedures reachable; the user approves them afterwards, one `request-approval scope` at a time,
and that is the only thing that can mint an APR.

...EXCEPT FOR A RECORD THAT IS ALREADY FINISHED, which is SR-0004 and which the initial-status rule
alone gets wrong. Measured across two field projects: 260 of 264 tasks in one and 162 of 165 in the
other are DONE. Writing all of them into `tasks/active/` at DRAFT buries the four that are alive
under the ones that are not, and says the opposite of what V1 recorded. So a record spec II.10's
mapping table marks as FINISHED (`archive_candidate`) is written straight into
`archive/<TYPE>/<year>/` at its mapped status, by `state.capture_migrated_archive`, and the
per-item FIELD contract does not apply to it (DEC-0004) -- a V1 task is missing ten of eleven
required fields, and no rule turns a line on a list into a work order. Which records qualify, which
bolts hold that exemption in place, and which V1 statuses are deliberately NOT archivable (the ones
only a user approval could have reached) are argued at `state.migration_archive_status`; the year
comes from the record's own dates and is never guessed (`_record_year`).

A V1 PARENT CHAIN IS THE NORMAL SHAPE and is what forced planning into two phases. The bindings
between records are resolved against the state the run WILL have reached rather than the one it
starts in, the writes are ordered so a parent exists before its child, a cycle is refused, and each
binding is rewritten to the id the parent ACTUALLY got -- V2 allocates ids, so the V1 number is not
the V2 number. A binding whose target is in neither the plan nor the store is refused exactly as
before. `_settle_bindings` carries all of it, including the defect it is the correction of.

WHERE THE BOOKKEEPING GOES. One `DEC` item per run, written by the same `capture` as everything
else, naming every source it read (with its content hash), every id range it created, the flags it
was given and everything it left alone. A Decision item is what this harness already uses for "a
choice was made about the state, here is the record of it", it is canonical state, and it survives
in git -- which is what a migration run needs and what a log line on somebody's terminal is not.
Per-record traceability is NOT in that item and deliberately so: it lives in each imported item's
own `legacy_fields`, so the receipt stays bounded by the number of source FILES while a project
with nine hundred records keeps a complete trail.

WHAT HAPPENS TO WHAT IT CANNOT TRANSLATE -- the third way, because throwing it away and dragging it
along are both wrong. A V1 filing log with nine hundred entries has no V2 counterpart and never
will: it is not a backlog, it is a business record. It is left exactly where it is, untouched and
unrenamed, and INVENTORIED in the run's Decision item with its byte size and its content hash, so
a later audit can tell whether the file it is reading is the file the migration saw. That is the
whole of it, and the limit is named here rather than left to be found: spec II.10 also asks for a
fail-closed integrity guard that BLOCKS writes to those retained files, and this module builds no
such guard -- nothing stops a later session from editing them.

NO APPROVAL KIND FITS THIS, which is a finding rather than an omission, and the kinds are named
by asking rather than by counting -- an earlier draft of this paragraph said "the five" over a
vocabulary of six and put `analysis` among the item-bound ones, which it is not. Everything
`approvals.item_derived_kinds()` returns is bound to an ITEM and hashes that item's own fields; a
migration has no item, it creates them. `analysis` is not in that set precisely because its subject
is an analysis question, a read-only scope and a cadence, none of which a migration has. `routine`
is a standing licence for a RECURRING run, so minting one for a one-off would leave the licence
behind afterwards. Every kind `approvals.line_manifest_kinds()` returns is bound to a subject a
COMMAND LINE can put together, i.e. to a handful of named facts a role types or the project
resolves; a migration touches every record it finds and has no such subject, so none of them fits
either -- whichever kinds that function returns today. (This paragraph carried a LIST of them, and
the list was one entry short for two releases running; asking the function is what keeps the reason
from having to be re-checked against a set that moves.)
Rather than bend any of them, the consent this command carries is structural: the dry run changes
nothing and prints a DIGEST, and the executing run refuses unless it re-derives that same digest.
What the digest is taken over is stated where it is built (`state_fingerprint`), not here, because
a second statement of a coverage claim is how the first one comes to be wrong. A state that moved
between the reading and the writing cannot be migrated on the strength of the reading -- and a
human who never read the dry run has no digest to type. That is weaker than an APR in one specific
way, and the difference is named here so that no text has to imply otherwise: it proves the STATE
is unchanged, not that a user consented.

NOT ATOMIC, RESUMABLE, AND NEVER SILENT ABOUT A PARTIAL RUN. `capture` takes the kernel lock per
item and the lock is not reentrant, so a run of N records is N locked writes rather than one. Two
things carry that:

  * every record is put through the PREFLIGHT OF THE METHOD THAT WILL WRITE IT
    (`state.capture_preflight`, or `capture_migrated_archive_preflight` for an archive-bound one)
    at PLANNING time, so the plan cannot promise a run the writer will refuse. Measured before that
    existed: a dev project with a V1 `system_requirements.yaml` planned READY, wrote three items and
    died on the fourth, because every record of that store names `derives_from: PRD-0001` and `PRD`
    is no V2 type. Three items in the state, no receipt, and a raw kernel message that never
    mentioned either.
  * what no reading can rule out -- a lock, a disk, an interrupt -- still leaves the run half done,
    so `execute` writes the receipt for what it DID create and refuses with a message that names
    those ids. Idempotency is what makes that safe rather than a transaction: a record counts as
    imported when an item already carries its id in `legacy_fields.legacy_id`, so a second run
    picks up exactly where the first stopped and a completed run reports there is nothing to do.
    That id is the WHOLE key, and it was the pair (source document, id) for a round: renaming the
    V1 file then made every record of it unseen again, so the same records imported a second time
    as new items. A known id arriving under a different path is now a FINDING with both paths in
    it -- see `build_plan` -- because this command cannot tell a moved file from a copied one and
    guessing either way writes something nobody can undo.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import os
import re
import textwrap

import yaml

from . import layout
from .backlog_types import (
    ACTIVE_DIRS,
    DEC_WORK_FIELD,
    DEC_WORK_NONE,
    IMPORT_MARK,
    LEGACY_FIELD,
    OPTIONAL_FIELDS,
    PARENT_FIELDS,
    REQUIRED_FIELDS,
    ROOT_TYPE_BY_KIT,
    UnknownV1Status,
    GOAL_CLASSES,
    GOAL_CLASS_FIELD,
    GOAL_CLASS_TYPES,
    format_id,
    map_v1_status,
    parse_id,
    suggested_v1_field,
    v1_types,
    widest_status,
)
from .hashing import canonical_json
from .report import ITEM_MAX_BYTES, ITEM_MAX_LINES
from .state import ProjectState, StateError, migration_archives

# The V1 id shape, as a PROPERTY of how V1 numbered records rather than as the shape V2 allocates.
# Wider than `backlog_types._ID_RE` in three directions, each for its own measured reason:
#
#   * the TYPE is not checked against any list. V1 types that V2 renamed (`PRD`) must still parse,
#     and `map_v1_status` is the only judge of whether a type is known -- it is the spec's table.
#   * the number has no fixed width. V1 had no allocator and no formatter.
#   * ...and for the same reason it has an optional DISCRIMINATOR: V1 numbers were typed by hand
#     into an ordered document, so a record inserted between `TSK-0017` and `TSK-0018` was named
#     `TSK-0017b` rather than renumbering everything after it. That is the SAME id shape used the
#     way a hand-kept list uses it, not a different kind of name.
#
# WHAT THE DISCRIMINATOR AND THE FREE WIDTH EACH COST WHILE THEY WERE MISSING is measured rather
# than retold here: `test_migrate.test_a_hand_numbered_v1_id_is_a_record_and_not_a_silence` and
# `test_the_recogniser_reads_every_id_width_a_hand_kept_list_produces` are the two, and both name
# the field reading behind them.
#
# THE COUNTER-DIRECTION, since widening a recogniser is how the opposite defect gets in: the
# separator, the case and the discriminator's position are unchanged, so nothing that is not
# `<UPPERCASE TYPE>-<digits>` starts matching -- a lower-case `unavailable_503` or `tablet_768` in
# a design document is not an id and is not read as one. A record whose id this reads and whose
# type no table knows is reported as `not_an_item` by the same rule as before: it is not imported
# by being recognised.
V1_ID_RE = re.compile(r"([A-Z]{2,4})-(\d+)([A-Za-z][A-Za-z0-9]*)?\Z", re.ASCII)

STATUS_FIELD = "status"
# `LEGACY_FIELD` and `IMPORT_MARK` are imported from `backlog_types` rather than spelled again here,
# because `state.capture_migrated_archive` writes the same two names. What the mark may and may not
# claim is argued where it is defined (DEC-0021): it says where the item's content came from, and
# nothing in this harness reads it as a permission.

# THE ONE KIND OF REQUIRED FIELD AN IMPORT MAY ANSWER ITSELF, and it is spelled as a FIELD NAME
# rather than as a type because the name means the same thing in every contract that carries it: a
# field whose subject is where the record CAME FROM, not what the record says. The importer is the
# only writer that knows that, V1 recorded it in no field, and `--map` cannot settle it because
# there is no V1 field to name -- which would leave every `decisions.yaml` in the field permanently
# untranslatable (DEC-0002: 106 measured records). A `--map` for the same field still wins, so a V1
# store that DOES carry its own provenance is not overwritten by this.
#
# Everything else stays a decision. Nothing here infers a field from a similar name, and a required
# field that is about the record's CONTENT is never filled by this module.
PROVENANCE_FIELDS = frozenset(("source",))

# WHAT A YEAR IS IN THIS MODULE, written once and read by both things that produce one: the date
# inside a V1 record, and the `--archive-year` flag. It went unwritten for the flag, and `int` was
# the only judge -- so `--archive-year 12` filed items under `archive/<TYPE>/12/` and a negative
# value produced a directory name a path builder should never have been handed. Four digits is not
# a range somebody picked here; it is the shape `_DATE_RE` already reads a year in, so the flag and
# the record answer the same question in the same terms.
_YEAR_RE = re.compile(r"\d{4}", re.ASCII)
# What a printed archive path says where the year is not settled yet. Its own name because
# `archive_location` is the only composer of that path and two spellings of the placeholder would
# make two shapes of one sentence.
_YEAR_PLACEHOLDER = "<year>"
# A date-shaped value inside a V1 record. Used only to answer "which archive YEAR" and only where
# the record itself carries a date; see `_record_year`.
_DATE_RE = re.compile(r"\b(%s)-\d{2}-\d{2}\b" % _YEAR_RE.pattern, re.ASCII)

# The receipt's own type. `DEC` is the harness's existing "a choice was made about the state"
# item -- it has no automaton to walk, no approval to obtain and no parent to bind, which is
# exactly the shape a run record needs.
RECEIPT_TYPE = "DEC"

_DOCUMENT_SUFFIXES = (".yaml", ".yml")

# WHAT MARKS A FILE AS THIS COMMAND'S OWN DEPOSIT COPY (DEC-0024). A file name, not a directory
# name, and that is measured rather than tidy: a DIRECTORY under `staging/` is a staging KEY, and
# `report.validate_state` reports every key that is not an active item as an orphaned staging dir --
# so a deposit DIRECTORY would make this command's own printed instruction produce a finding in the
# validator. EVERY reader of that directory is asked, not one: `report.generate_session_brief` reads
# it too, and it listed every FILE there as a key until the deposit made that visible.
# `test_migrate.test_the_deposit_an_instruction_names_is_no_staging_key_either_reader_reports`
# measures both directions against both readers.
_DEPOSIT_MARK = "v1-deposit--"

# THE LONGEST NAME A FILE MAY CARRY HERE, written once and read nowhere else. Measured 2026-08-09
# on this host: a name of exactly the length below is created, one character more answers
# `OSError: [Errno 22] Invalid argument`. It is not a bound this module chose and not one it can
# shorten -- see `deposit_note` and the entry `L32` in `docs/POST_V2_WISHLIST.md`, which carries the
# chain and what stays open with it. `test_a_deposit_name_too_long_to_create_says_so_where_it_is_
# printed` couples this value to the filesystem rather than restating it, so a host with another
# limit reports THIS line as the wrong one.
_NAME_MAX_CHARS = 255


# THE ALPHABET A DEPOSIT NAME IS WRITTEN IN, and it is chosen by a property rather than assembled
# from the characters that have caused trouble: on every character in it, this filesystem's folding
# is the identity. No upper case, so a case-insensitive name comparison cannot join two of these; no
# dot and no space, so stripping a trailing one cannot; nothing outside ASCII, so neither can
# Unicode normalisation. Everything else -- and that includes `%` itself, so an escape is never
# ambiguous -- is written as `%xx` in LOWER-CASE hex, which is the same escape `urllib.parse.unquote`
# reads and therefore keeps the encoding invertible.
_NAME_ALPHABET = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-_")


def deposit_of(rel: str) -> str:
    """Where a COPY of the state-relative path `rel` may be put -- the ONE place a remedy names.

    DEC-0024, AND IT IS A CONSTRUCTION RATHER THAN A CLAUSE. Every earlier version of the printed
    remedy derived a target from the state tree ("move it out of the dotted path", "rename it back
    to a .yaml document") and then had to be asked, one review round per authority, whether that
    target was a kernel area, a wall, a wall as SOURCE, or already occupied -- and the round after
    each fix found the next unasked authority. The last one was not about a single sentence at all:
    two remedies of ONE report named one free path, so a reader who followed both lost a V1 store to
    a silent `mv`.

    WHAT THIS NAMES INSTEAD, and why the four questions cannot be asked of it:

      * it lies under `staging/`, spec II.4's proposal area, so it is not state, no kernel writer
        lands there, no gate reads it, and it is not a document this command inventories or moves.
      * the file name carries `_DEPOSIT_MARK` and then the SOURCE PATH, percent-encoded into
        `_NAME_ALPHABET`. The encoding is invertible (`urllib.parse.unquote` reads it back), and an
        invertible encoding is injective -- which is the collision that made this a class rather
        than a sentence.
      * INJECTIVE AFTER THE FILESYSTEM HAS FOLDED THE NAME, which is not the same claim and is the
        one this got wrong twice. Two names a filesystem folds into one are one name, so it is not
        enough that the strings differ. Measured 2026-08-09 on this host, with `quote`'s own output:
        `v1-deposit--foo.yaml.` and `v1-deposit--foo.yaml` were ONE file, a trailing dot being no
        part of a name here; and after that dot was escaped, a document holding `PROC-0811a` and
        `PROC-0811A` produced TWO instructions landing on ONE file, because names here are compared
        without regard to case while a YAML key is not. The answer is not a third escape but the
        alphabet: nothing that survives into the name is something a fold can change.
      * the instruction that names it says COPY. Where THIS name is printed -- the coverage note in
        `_coverage_of` -- the source stays where it is, so no reader who follows it can lose the
        file, and the only path this name can ever land on is an earlier copy OF THE SAME SOURCE.
        The one caller whose remedy ALSO changes the source is `record_deposit_of`, and it does not
        rest on this clause: it feeds a content digest through this encoder for exactly that reason.

    THE RESIDUAL, and it is the reason nothing here shortens the name: a source path deep enough to
    push the encoded name past what the filesystem allows produces a name the reader cannot create.
    Truncating or hashing it would buy that back by making two sources share one name, which is the
    defect this construction exists to remove; so the name stays long, `deposit_note` says so in the
    message where it happens, and `L32` carries the measured chain.
    """
    return "%s/%s%s" % (layout.STAGING_DIRNAME, _DEPOSIT_MARK, _encoded_name(rel))


def _encoded_name(rel: str) -> str:
    """`rel` as ONE file name, invertible by `urllib.parse.unquote` -- the encoder, on its own.

    Extracted from `deposit_of` when a second place needed the same property (`overflow_deposit_of`).
    Two encoders would be two answers to the question the whole construction rests on, and an
    injectivity that holds for one of them says nothing about the other.
    """
    return "".join(chr(byte) if chr(byte) in _NAME_ALPHABET else "%%%02x" % byte
                   for byte in rel.encode("utf-8"))


# THE DIRECTORY A FILE IS COPIED INTO WHEN IT HAS TO LEAVE THE STATE DIRECTORY ALTOGETHER. Beside
# the state directory, not under it, which is the difference to `deposit_of` and the reason both
# exist: a deposit is a copy of a file that STAYS, and this is the copy of a file the reader then
# removes. Naming a place under `staging/` for that would leave the file in the project, and the
# whole point of the one remedy that uses this is to free a place in the project.
OVERFLOW_DIRNAME = "v1-legacy-overflow"


def overflow_deposit_of(rel: str, digest: str) -> str:
    """Where a COPY of `rel` may go when the point is that `rel` afterwards goes away.

    STATE-RELATIVE LIKE EVERY OTHER PATH THIS MODULE PRINTS, and it begins with `../` for that
    reason: every other path in the same report is read against the state root, so a name printed
    without it would read as a place inside the state directory -- which is the one thing this
    target may not be.

    WHY IT CARRIES THE CONTENT AND NOT ONLY THE PATH, which is the difference to `deposit_of` and
    is a measured chain rather than caution. There the source stays, so a name that is taken holds
    an earlier copy OF THE SAME FILE. Here the reader removes the original afterwards, so the same
    state-relative path can hold different bytes later on: a run retires `old_procs.yaml` to the
    legacy area, the reader copies that file out and removes it, the run then retires a SECOND
    document of the same name there, and a third run offers the same remedy again. With the path
    alone in the name, that third instruction lands on the first file and takes it away -- the one
    thing DEC-0024 exists to make impossible. With the digest in it, a name that is taken holds
    bytes identical to the ones being copied, so following the instruction destroys nothing.

    WHAT IT DOES NOT COVER is the span between the answer and the action (`L30`): the digest is of
    the file as it stood when the dry run read it, and a file that changes in between is copied
    under the name its OLD content earned.
    """
    return "../%s/%s%s" % (OVERFLOW_DIRNAME, _DEPOSIT_MARK, _encoded_name("%s/%s" % (rel, digest)))


def _body_digest(body: dict) -> str:
    """sha256 over the item body a record would become -- the content half of a record deposit name.

    Through `yaml.safe_dump` rather than `canonical_json`, and that is not a stylistic choice: a V1
    record inlines dates (`created: 2026-01-06` parses to `datetime.date`), and `canonical_json`
    fails closed on any non-JSON type. `item_size` already dumps the shape the kernel will write
    with the same serialiser, so this measures the same bytes; `sort_keys=True` makes the digest a
    function of the CONTENT and not of a mapping's insertion order.
    """
    return hashlib.sha256(
        yaml.safe_dump(body, sort_keys=True, allow_unicode=True).encode("utf-8")).hexdigest()


def record_deposit_of(rel: str, legacy_id: str, digest: str) -> str:
    """The deposit name for ONE RECORD of the document `rel`, rather than for the document.

    Same encoder as `deposit_of` on purpose: the property that has to hold is the same one, and two
    encoders would be two answers to one question. What is encoded is `<document>/<record id>/
    <digest>`.

    WHY IT CARRIES THE CONTENT AND NOT ONLY THE LOCATOR, which is the difference to `deposit_of`'s
    own use and the same measured chain `overflow_deposit_of` carries. In `_coverage_of` the source
    STAYS, so a name that is taken holds an earlier copy of the same file. Here it does not: the
    remedy this name is printed in says COPY the record out AND THEN SHORTEN it in the V1 file, so
    the record at `<document>/<record id>` holds different bytes on a re-run. With the locator alone
    in the name, a reader who shortens too little re-runs, is handed the SAME name, and the second
    COPY overwrites the first -- the bulk they moved out of the V1 file is then in neither place.
    Measured chain (real synaipse ADR-0013): 1604 bytes lost on the second following. With the
    digest in it, a shortened record earns a DIFFERENT name, so the first copy stands untouched and
    a name that is taken holds bytes identical to the ones being copied.

    The locator part still cannot be given to a document of the same state -- a document is a FILE,
    so no path of that state has it as a directory component, and the record locator is exactly such
    a path -- so this collides neither with a document's deposit nor with another record's.
    """
    return deposit_of("%s/%s/%s" % (rel, legacy_id, digest))


def deposit_note(target: str) -> str:
    """What a deposit name owes a reader ABOUT ITSELF, or "" when it owes nothing.

    A construction that is injective by never shortening buys that with length, and the price is
    paid by the reader: past `_NAME_MAX_CHARS` the instruction is still printed and cannot be
    carried out. Saying nothing there would make this module's own message a claim it does not keep,
    so the message says it -- and says it as a fact rather than as an alternative name, because a
    shorter name is exactly the collision the construction exists to remove.
    """
    over = len(target.split("/")[-1]) - _NAME_MAX_CHARS
    if over <= 0:
        return ""
    return (" That name is %d character(s) longer than the %d this filesystem takes, so the copy "
            "cannot be made under it here. This command has no shorter name to offer: shortening "
            "is what would let two sources share one place." % (over, _NAME_MAX_CHARS))


def copy_instruction(target: str) -> str:
    """The ONE shape every instruction this module prints has (DEC-0024), composed in one place.

    Where this module tells a reader to put something -- the coverage note for a file out of reach,
    the refusal of a record too large for one item -- it used to say it in its own words, and one of
    those words was a bare directory (`staging/`), which let the READER invent the file name. One
    composer is what makes "a printed instruction names a constructed file and says COPY" a property
    of this module rather than of whichever sentences happen to exist.
    `test_migrate.test_the_instruction_this_module_prints_has_exactly_one_composer` is the claim's
    own tripwire, over everything this repo ships and not over this file.
    """
    return "COPY it -- the original stays where it is -- to `%s`.%s" % (target, deposit_note(target))


def in_deposit(rel: str) -> bool:
    """Is this state-relative path a deposit copy -- a file this command's own remedy named?

    Folded the way `layout.is_in_proposal_area` folds, so the deposit and the proposal area agree
    about one file on this filesystem. DEPTH IS PART OF THE QUESTION: only a file directly under
    `staging/` carries the mark, because that is the only shape `deposit_of` produces, and a
    directory somebody named after the mark is a staging key and not this.
    """
    parts = str(rel or "").replace("\\", "/").strip("/").lower().split("/")
    return (layout.is_in_proposal_area(rel) and len(parts) == 2
            and parts[1].startswith(_DEPOSIT_MARK))


class MigrationError(StateError):
    """The migration refused. Same exit channel as every other kernel refusal (cli: 1)."""


# -- reading the state directory ------------------------------------------------------------------


def _relative(state: ProjectState, path: str) -> str:
    return os.path.relpath(path, state.root).replace(os.sep, "/")


def documents(state: ProjectState) -> list:
    """Every KIT DOCUMENT under the state root, state-relative, sorted.

    `layout.is_project_document` is the definition and it is not restated here: a document is what
    no kernel path builder can name, minus the dotted machinery and minus `staging/`. That is the
    same predicate `gate_write_scope` refuses tool writes with, so what this command inventories
    and what a role is refused are one answer.
    """
    found = []
    for dirpath, dirs, files in os.walk(state.root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in sorted(files):
            rel = _relative(state, os.path.join(dirpath, name))
            if layout.is_project_document(state.root, rel):
                found.append(rel)
    return sorted(found)


# The answers `search_coverage` gives, and every entry it produces carries exactly one of them.
# `SEARCHED` and `UNSEARCHED` are what a reader is told about; `KERNEL` and `MACHINERY` are the two
# areas that are not V1 documents at all and are named here so that "not reported" is a decision
# with a name rather than a branch that fell through. `DEPOSIT` is a copy THIS command's own remedy
# told a reader to make, counted rather than named one line each (BUG-0028). `UNLISTABLE` is the
# only one that is not about a file: it is a DIRECTORY the walk could not open, and therefore the
# one verdict that says the others are incomplete -- see `search_coverage` for why that has to block
# rather than warn.
SEARCHED = "searched"
UNSEARCHED = "unsearched"
KERNEL = "kernel"
MACHINERY = "machinery"
DEPOSIT = "deposit"
UNLISTABLE = "unlistable"

# THE ONE STEP THIS COMMAND OFFERS FOR AN UNLISTABLE DIRECTORY, and the reason it is one and not two
# (DEC-0024, second clause). The alternative that stood beside it until round 8 said "or take the
# directory out of the state directory": a walk error produces this row for ANY directory (`L28`),
# the canonical ones included, so a reader who followed it could carry off the very directory the
# root item lives in -- and after the install `gate_write_scope` leaves no writer that could put it
# back. A step that changes the SESSION'S access changes nothing that a state directory holds, which
# is why this one may stand alone.
THE_ONLY_UNLISTABLE_STEP = "give the session read access to it"


def _is_yaml_document(rel: str) -> bool:
    """Is this path a YAML document -- the one place the record search's file kind is decided.

    Asked by the run-up (`_coverage_of`) and by the wall listing in `render`, because both have to
    answer the same question about the same file: a document this module would not hand to a YAML
    parser may not be REPORTED as one that a YAML parser refused.
    """
    return rel.lower().endswith(_DOCUMENT_SUFFIXES)


def walls_of(state: ProjectState) -> dict:
    """`layout.gated_documents` for the installation this state directory sits in.

    WHERE THE REPOSITORY ROOT COMES FROM lives here rather than at each caller: the state directory
    is a child of the project root, and two callers spelling that themselves is the shape in which
    a report and a move come to disagree about which files are walls.
    """
    return layout.gated_documents(os.path.dirname(os.path.abspath(state.root)), state.root)


def search_coverage(state: ProjectState) -> list:
    """[(state-relative path, verdict, why)] for EVERYTHING under the state root, sorted.

    THE RUN-UP OF THE RECORD SEARCH, AS ONE ANSWER FOR ITS TWO READERS. `build_plan` and
    `report._check_no_v1_records_outside_the_archive` both have to decide which files a V1 record
    search may look at, and for one round each decided it for itself. Measured 2026-08-07 with the
    same `PROC-0001` record laid down in seven places of one state: three of them (a kit document,
    one in a subdirectory, one spelled `.yml`) were reported by both, and FOUR -- another suffix, a
    dotted path, `staging/`, and a dotted path again -- were reported by the dry run, by the
    validator, or by neither, in three different combinations. Two readers of one question is how
    they came to contradict each other about one file, which is the thing the round before this was
    supposed to have ended.

    THE VERDICT IS TOTAL, AND TOTALITY IS A CLAIM ABOUT THE WALK, NOT ONLY ABOUT THE CLASSIFIER.
    Every file this walk reaches comes back with a name for what happened to it -- a skip that
    reports nothing has to be spelled as `KERNEL` or `MACHINERY` here, in front of both readers,
    instead of being a `continue` in one of them. But a classifier that answers for every file it is
    handed says nothing about the files it is never handed: `os.walk` swallows the error from a
    directory it cannot open and simply yields nothing for that whole subtree. Measured 2026-08-08
    on this host, a state whose `hidden/` directory was denied read access to the running user:
    `search_coverage` came back with two rows and neither the directory nor the `old_procs.yaml`
    with a V1 record in it was among them, the plan was executable, `validate` had no finding and
    the shipped merge gate answered `git merge` with rc 0. So the walk reports its own errors, one
    `UNLISTABLE` row per directory it could not open, and BOTH readers turn that row into a refusal
    (`build_plan` puts it in `unreadable`; `report` makes an error finding of it). Unknown is not
    empty, one storey below where that sentence was already written.

    THAT ONE ROW IS ALSO WHAT COVERS THE OTHER WALKS. `documents`, `imported_legacy_ids` and
    `state_fingerprint` walk the same tree with the same blindness, and each of them is silent about
    a subtree it cannot list. Nothing here makes those three see it; what it does is refuse the run
    while such a directory exists, so no plan is built, no digest is presented and no import is
    written on the strength of a reading that was short a subtree.

    WHY THE FOUR FILE VERDICTS, in the order they are asked:

      * a DOTTED segment that is not YAML is MACHINERY -- `.kernel.lock`, `.audit/hook_events.jsonl`,
        the `.gitkeep` in every empty item directory. Nothing puts a V1 record there and naming
        them would bury the two answers that matter under one line per directory. This is a
        residual, and it is the same one this module has carried since the dotted walk was added: a
        V1 record in a dotted file that is not YAML is in no report.
      * a DOTTED segment that IS YAML is UNSEARCHED. `.legacy/old_procs.yaml` is a hiding place,
        not machinery -- wherever it lies, which is why this is decided before the kernel's own
        areas are asked about.
      * a KERNEL-written path is the kernel's own area (`layout.is_kernel_written`, asked of the
        writers' path builders) -- items, `generated/`, `approvals/`, `archive/` and the `legacy/`
        the import itself moves absorbed documents into. THIS IS THE SECOND RESIDUAL AND IT IS THE
        WIDER ONE: the verdict is about the AREA, not about who wrote the file, so a V1 store
        copied into `product/active/` is in neither report and stops no merge (measured; the entry
        is `L20` in `docs/POST_V2_WISHLIST.md`). What keeps that area empty of foreign files is
        `gate_write_scope`, which refuses every tool write under it -- not this classifier.
      * everything else is a project file: UNSEARCHED when it is not a YAML document (the record
        search reads YAML, and a store renamed to `tasks.yaml.bak` is out of its reach) or when it
        lies in the proposal area (`layout.is_in_proposal_area`, spec II.4: what is there is a
        proposal and not state, and searching it would report every staged item body as a V1
        record), and SEARCHED otherwise. A file that is BOTH gets both reasons, because a report
        that names one of two conditions describes the file only half.
      * a project file in the proposal area that carries THIS command's own deposit mark
        (`in_deposit`) is DEPOSIT, not UNSEARCHED. It is a copy a remedy of this command named, so
        it needs no remedy of its own and no reader has to act on it -- and one appears per applied
        remedy, so naming each one a line would grow the "did not search" section without bound as a
        project follows the report (BUG-0028: synaipse went 26 -> 62). `deposit_notes` COUNTS them
        instead; `unsearched_notes` no longer carries them.

    WHAT AN UNSEARCHED FILE IS OFFERED is a copy into this command's own deposit and nothing else
    (DEC-0024, argued at `deposit_of`). This walk therefore needs no wall list: it names no move,
    so there is no move it could name onto a document a gate reads. The wall list is still read
    once per run for the two places that DO move a file -- `absorbed_documents` and the dry run's
    own wall section -- and it is `build_plan` that carries it.
    """
    coverage, blind = [], []
    for dirpath, dirs, files in os.walk(state.root, onerror=blind.append):
        dirs[:] = sorted(dirs)
        for name in sorted(files):
            rel = _relative(state, os.path.join(dirpath, name))
            coverage.append((rel,) + _coverage_of(state, rel))
    for error in blind:
        # The directory is named from the ERROR rather than from the walk: the walk yielded nothing
        # for it, so its own path exists only in the exception the OS raised. `filename` is what
        # `os.scandir` puts there; a walk error without one would leave the reader with no name at
        # all, so the fallback says that instead of inventing one.
        # THE FALLBACK GOES THROUGH `_relative` INSTEAD OF CARRYING `state.root` ALONG, for the same
        # reason `_unreadable_because` takes `rel` and not a path: what a local of this function
        # holds is what `test_migrate._handed_a_finished_path` follows, and a raw root parked here
        # made every later use of `rel` look like a path being passed on. `ProjectState.__init__`
        # makes `root` absolute (`kernel/state.py`), so the two spellings answer alike.
        where = str(getattr(error, "filename", None) or "") or _relative(state, state.root)
        rel = _relative(state, where) if os.path.isabs(where) else where
        coverage.append((
            rel.rstrip("/") + "/", UNLISTABLE,
            "this directory could not be listed (%s: %s), so what is under it was not classified "
            "and not searched -- and a V1 store hidden there would be in no report. The run "
            "refuses while this stands. Remedy: %s"
            % (type(error).__name__, error.strerror or error, THE_ONLY_UNLISTABLE_STEP)))
    return sorted(coverage)


def _classify(state: ProjectState, rel: str) -> tuple:
    """(verdict, why, [every condition that keeps it out]) for one state-relative path.

    THE DECIDING HALF, kept apart from the WORDING half (`_coverage_of`) so that a caller can ask
    what a path classifies as without being handed the sentence a reader gets.

    EVERY CONDITION THAT KEEPS IT OUT, NOT THE FIRST ONE. `staging/PR-0001/old_procs.yaml.bak` is
    kept out by two of them, and a report that names one of the two describes a file only half.
    All three are collected -- including the dotted one, which is the same half-description for
    `staging/.bak/x.yaml`.

    NO CONDITION CARRIES A STEP TO UNDO IT ANY MORE (DEC-0024). Each of them used to, and each of
    those steps was a MOVE somebody could follow: "rename it back to a .yaml document" landed on
    the living store the backup was of, "move it out of the dotted path" landed on the project's
    own config, which is a wall. What is printed now is a copy into this command's own deposit
    (`deposit_of`), so what a condition owes the reader is the reason and nothing else.
    """
    is_yaml = _is_yaml_document(rel)
    dotted = any(part.startswith(".") for part in rel.split("/"))
    if dotted and not is_yaml:
        return (MACHINERY, "a dotted path that is no YAML document", [])
    conditions = []
    if dotted:
        conditions.append("it lies under a dotted path, which this harness treats as machinery "
                          "and does not search")
    elif layout.is_kernel_written(state.root, rel):
        # asked only OFF the dotted paths, so a dotted file inside a kernel area keeps the answer
        # it had: a hiding place is a hiding place wherever it is
        return (KERNEL, "written by the kernel itself, so it is not a V1 document", [])
    if not is_yaml:
        conditions.append("it is no YAML document (a V1 record is read out of %s)"
                          % " or ".join(_DOCUMENT_SUFFIXES))
    if layout.is_in_proposal_area(rel):
        conditions.append(
            "it lies under `%s/`, spec II.4's proposal area, where a file is a proposal and not "
            "state -- an item body staged for capture would read as a V1 record"
            % layout.STAGING_DIRNAME)
    if not conditions:
        return (SEARCHED, "", [])
    return (UNSEARCHED, "", conditions)


def _is_occupied(state: ProjectState, rel: str) -> bool:
    """Does something already stand at this state-relative path?

    `lexists` rather than `exists`, because the question is only ever "would putting a file here
    take something away": a symlink whose target is gone is still a thing a move destroys. On a
    case-insensitive filesystem this folds the way that filesystem folds, so the answer is the one
    the move itself would get rather than the one a lexical comparison would give.
    """
    return os.path.lexists(_state_path(state, rel))


def _occupant_digest(state: ProjectState, rel: str) -> str:
    """sha256 of whatever stands at `rel`, or "" when this run could not read it.

    Through `_read_bytes` like every other read this module makes under the state root, and not
    with an `open` of its own: the occupant of a landing place is a file in a KERNEL area, so it is
    not in the inventory and nothing else here has ever opened it -- exactly the shape in which the
    second reader `_read_bytes` exists against gets added.

    The empty string is not a digest and is never treated as one: `overflow_deposit_of` would build
    a name that two different files could share, so the caller prints the reason instead of an
    instruction. A file the run cannot read is a file it cannot promise anything about.
    """
    raw, problem = _read_bytes(state, rel)
    return "" if problem is not None else hashlib.sha256(raw).hexdigest()


def _coverage_of(state: ProjectState, rel: str) -> tuple:
    """(verdict, why) for one state-relative path -- the rule `search_coverage` documents.

    THE REMEDY HALF IS ONE PROPERTY AND NO LONGER A CHAIN OF CLAUSES (DEC-0024). What used to stand
    here derived a target out of the state tree and then asked authority after authority whether
    that target was safe -- the classifier, then existence, then the wall list, then the other
    sentences of the same report -- and every round found the next unasked one. The property that
    replaces all of them is `deposit_of`: a copy, into an area this command owns, under a name
    derived from the source path. It takes no wall, no kernel area and no occupancy question,
    because none of those can be true of it, and two lines of one report cannot name one file.

    WHAT THIS COSTS, said plainly because it is the trade DEC-0024 made: the sentence no longer
    tells anybody where to put the file so that the next run would search it. That was the SHORT
    way, and it is the one that took files away. Where a V1 store has to lie is a decision about
    the reader's own state directory, and this report is the oracle for it -- a file that is no
    longer on this list is a file this command searches.
    """
    verdict, why, conditions = _classify(state, rel)
    if verdict != UNSEARCHED:
        return (verdict, why)
    reasons = " and ".join(conditions)
    if in_deposit(rel):
        # A COPY THIS COMMAND'S OWN REMEDY NAMED, so it gets no remedy: pointing at `deposit_of`
        # again would name a deposit of a deposit, one nesting level per run, which is a step that
        # changes nothing -- the shape this module refuses to print anywhere else. Its OWN verdict
        # (`DEPOSIT`, not `UNSEARCHED`) so it is counted rather than named one line per remedy
        # applied (BUG-0028); the reason is kept for the count's own wording.
        return (DEPOSIT,
                "%s. It carries this command's own deposit mark, so it is a COPY somebody was told "
                "to make of a file that is out of reach of the record search; the original is the "
                "one that decides anything, and no step is named for this one." % reasons)
    return (UNSEARCHED,
            "%s, so nothing here can say whether it holds one. If it IS a V1 store: this command "
            "names no way to move or rename it (DEC-0024 -- every such name is a claim about a "
            "filesystem it does not control, and following one has taken a file away). What it "
            "does name is a place of its own: %s That name is derived from the path above, so no "
            "two lines of this report can name one file. Where the file has to lie for this "
            "command to search it is a decision about your own state directory; re-run the dry run "
            "afterwards and this list says whether it is still out of reach."
            % (reasons, copy_instruction(deposit_of(rel))))


def unsearched_notes(coverage) -> list:
    """[(path, why)] for the files a record search cannot look at -- one wording, both readers.

    A DEPOSIT copy is NOT here (BUG-0028): it is a copy this command's own remedy made, so it needs
    no remedy of its own, and one appears per applied remedy -- listing each would grow this section
    without bound. `deposit_notes` counts them instead.
    """
    return [(rel, why) for rel, verdict, why in coverage if verdict == UNSEARCHED]


def deposit_notes(coverage) -> list:
    """[(path, why)] for the deposit copies this command's own remedies made -- COUNTED, not listed.

    Their own accessor so `validate` and `doctor` can report `N deposit copies` in one line instead
    of one `NOT SEARCHED` line each. Kept apart from `unsearched_notes` for the reason BUG-0028
    names: a deposit is not a file a reader has to do anything about, and a project that follows the
    report accumulates one per applied remedy (synaipse: 26 remedies applied -> 62 lines before this
    was a class of its own).
    """
    return [(rel, why) for rel, verdict, why in coverage if verdict == DEPOSIT]


def unlistable_notes(coverage) -> list:
    """[(directory, why)] for the subtrees the walk could not open -- one wording, both readers.

    Kept apart from `unsearched_notes` because the two carry opposite verdicts: an unsearched file
    is NAMED and blocks nothing (a project cannot be blocked out of the `README.md` its own kit
    ships), while a directory nobody could list means the coverage itself is short and every reader
    of it refuses.
    """
    return [(rel, why) for rel, verdict, why in coverage if verdict == UNLISTABLE]


def _state_path(state: ProjectState, rel: str) -> str:
    """The absolute path of a state-relative name -- composed in one place, because the reason a
    read failed is stripped of exactly the string this module handed to `open` (`_without_path`)."""
    return os.path.join(state.root, *rel.split("/"))


def _unreadable_because(exc: BaseException, state: ProjectState, rel: str) -> str:
    """One line saying what ended a read of `rel`, with the path itself replaced by a name for it.

    TAKES THE STATE-RELATIVE NAME AND COMPOSES ITS OWN PATH, which is not a convenience: the rule
    that says which functions can reach a state file reads this file and asks who NAMES one
    (`test_migrate._names_a_state_file`). A function handed a finished path names nothing that rule
    can see, so a reader added inside one would have been invisible to it -- measured, and it is
    why this signature is `rel` and not `path`.
    """
    return "could not be read (%s: %s)" % (type(exc).__name__,
                                           _without_path(str(exc), state, rel))


def _read_bytes(state: ProjectState, rel: str):
    """(the file's bytes, why there are none) -- `problem` is None exactly when the bytes were read.

    EVERY READ THIS MODULE MAKES UNDER THE STATE ROOT GOES THROUGH HERE. That is a claim about the
    code, and it is measured from TWO SIDES because neither side alone covers it. Both are in
    `test_migrate`, and what each is blind to is what the other reads:

      * `test_every_state_file_this_module_opens_it_opens_through_read_bytes` runs a plan under
        `sys.addaudithook` and requires that every `open` event on a path under the state directory
        whose asking frame is a frame of this module comes from here. Total over the SPELLING --
        `io.open`, `codecs.open`, `os.open`, `pathlib.Path.read_bytes` are all one event -- and
        only over the code that one run walks, which is about half of this file.
      * `test_nothing_but_these_functions_can_name_a_file_of_the_state_directory` parses the file
        and asks which functions can NAME a path under the state root at all, one step before
        anything can be opened. Total over the FILE and silent about spellings.

    The rule they replace counted `ast.Call` nodes named `open` and was measured wrong in BOTH
    directions -- a real second reader spelled `io.open` was invisible to it, and an equivalent
    rewrite inside this function made it fail with a message that was then untrue. WHAT IS LEFT
    OVER AFTER BOTH is named at the second test, and it is that test's business rather than this
    docstring's: it follows the composed path through the calls of this file, so a function that
    RECEIVES one is named at the call that hands it over. `_unreadable_because` and `_without_path`
    still compose their own path from `rel` rather than taking one, because a signature that says
    `(state, rel)` is the shape the rule asks for and not merely the shape it tolerates. Other
    modules read under the state root too (`state._load` for one); this paragraph is about this
    one.

    IT IS THE CORRECTION OF A BLINDNESS one storey below the one this module closed the round
    before. `search_coverage` names
    a DIRECTORY it cannot list and both of its readers refuse on that row; a FILE nobody could OPEN
    was three different stories -- `_read_document` reported it, and `_file_facts` and
    `state_fingerprint` opened it without a handler.

    Measured 2026-08-08 on this host, `icacls /deny <user>:(RD,RA)` on ONE kit document of an
    otherwise clean state, both commands as real processes: `validate` answered rc 1 with a finding
    naming the file, and `migrate --dry-run` answered rc 1 with a `PermissionError` traceback out of
    `_file_facts`. One file, two commands, and the one whose module head promises that "an
    unreadable one refuses the run" was the one that crashed -- while the validator's own remedy
    told the reader that the dry run would name it under UNREADABLE.

    So the rule is the property `_read_document` already states for the parse, one call earlier:
    turning a foreign file into anything is a statement ABOUT THE FILE, and every way it can fail is
    reported as one. What each caller does with the reason is its own business -- both of the two
    above put it in the plan's `unreadable`, which is the list `plan_is_executable` refuses on and
    the same one the `UNLISTABLE` row joins.
    """
    try:
        with open(_state_path(state, rel), "rb") as handle:
            return handle.read(), None
    except Exception as exc:                 # noqa: BLE001 -- see `_read_document` for why the net
        return None, _unreadable_because(exc, state, rel)


def _file_facts(state: ProjectState, rel: str):
    """({path, bytes, sha256}, why there is no such row) -- one document's inventory entry."""
    raw, problem = _read_bytes(state, rel)
    if problem is not None:
        return None, problem
    return ({"path": rel, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}, None)


def _declared_id(node):
    """The id a mapping states in its OWN `id` field, or None.

    Asked of the mapping and of nothing around it, which is the whole point: the field means the
    same thing wherever the mapping sits, and reading it in one position only is what made the
    third id form a silence (see `scan_document`).
    """
    value = node.get("id")
    if isinstance(value, str) and V1_ID_RE.match(value.strip()):
        return value.strip()
    return None


def _keyed_id(key):
    """The id a mapping is FILED UNDER, or None -- the other half of the same self-identification."""
    if isinstance(key, str) and V1_ID_RE.match(key.strip()):
        return key.strip()
    return None


def scan_document(payload):
    """[(ordinal, id, mapping)] for every self-identifying record in a parsed document.

    THE TWO WAYS A MAPPING NAMES ITSELF, asked of every mapping the walk reaches and never of its
    position: the KEY it is filed under, and its own `id` FIELD. Both are in the module head's
    definition of a V1 record, and both are read here for the same node.

    THIS USED TO BE A RULE ABOUT POSITIONS -- an id-keyed mapping value, or a LIST member with an
    `id` field -- and the third combination fell between them. Measured on the field copy of
    `synaipse` (2026-08-05): `review_reports.yaml` carries `wording_correction_needed: {id: "OQ-1",
    status: closed}`, a mapping in a value position naming itself in its own field, and it appeared
    under no heading of the dry run, in no `validate` finding and in no completeness count -- the
    one outcome this command may not produce. Widening the rule to the PROPERTY finds it and
    changes nothing else: across all three field copies it is the only record the position rule
    missed, and no record the position rule found is lost.

    A MAPPING THAT NAMES ITSELF THE SAME WAY TWICE IS ONE RECORD (`SR-0001: {id: SR-0001, ...}`,
    the ordinary shape of a store that repeats its key inside the entry). One that names itself
    with two DIFFERENT ids yields two entries over the same mapping, so neither name is a silence;
    `build_plan` refuses such a record rather than importing one mapping as two items.

    THE ORDINAL IS THE IDENTITY, not the id. Two records in one document may carry the same V1 id
    -- V1 had no allocator -- and keying the walk's result by id made the LAST one win: measured
    with both shapes in one file, the written item carried record B's fields under record A's
    legacy metadata, an item that never existed in V1, and record A was gone even from
    `legacy_fields.record`. The ordinal is stable because a YAML mapping parses in document order,
    so the record the plan classified is the record the run writes. (Such a document is refused
    outright as well -- see `build_plan` -- because two items claiming one `legacy_id` would break
    the idempotency scan too. The ordinal is what makes the refusal ACCURATE about which records
    collide rather than merely present.)

    THE WALK DOES NOT STOP AT A HIT, and that is a correction. It used to recurse only into values
    that were NOT records, so anything nested inside a record was invisible -- measured: a
    `PROC-0101` with an unknown status sitting inside `PROC-0100` appeared under no heading of the
    dry run at all, neither imported nor blocked nor reported, while the module promised that an
    unknown status blocks. Silence about a record is the one outcome this command may not produce.

    THERE IS NO DEPTH LIMIT, and that is the second correction. The first cut stopped at a
    hand-picked `_SCAN_DEPTH = 3`, and no value of it was defensible: the number was measured
    against nothing, and once the walk stopped skipping record bodies the same bound cut a real
    office `review_findings.yaml` in half (its `findings:` entries sit one level below where 3
    reaches). A limit that decides whether a project can be migrated may not be a number somebody
    liked.

    What the bound was actually guarding against is CYCLES -- `yaml.safe_load` will happily build
    a self-referencing structure out of an anchor -- and that is guarded against directly: every
    container is walked at most once, by identity. A repeated node is a YAML alias and loses
    nothing by being skipped, because the object it aliases was already scanned. The walk is then
    linear in the document, and "everything carrying the V1 id shape is reported" is a promise the
    code keeps at any nesting rather than down to a chosen level.
    """
    records, seen = [], set()

    def walk(node, keyed_as=None):
        if not isinstance(node, (dict, list)):
            return
        first_visit = id(node) not in seen
        if isinstance(node, dict):
            if keyed_as is not None:
                records.append((len(records), keyed_as, node))
            declared = _declared_id(node)
            # `first_visit` only for the DECLARED name: an alias reaches the same mapping under a
            # second key, and that second key is a second name; its own `id` field is not.
            if declared is not None and declared != keyed_as and first_visit:
                records.append((len(records), declared, node))
        if not first_visit:
            return
        seen.add(id(node))
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, _keyed_id(key))
        else:
            for entry in node:
                walk(entry)

    walk(payload)
    return records


def _declares_status(record) -> bool:
    """Does this self-identifying mapping CLAIM to be a V1 item? -- the one definition, two readers.

    A record with no `status` is a cross-reference table, not a backlog entry, and the two places
    that have to agree on that are the claimant count (an id-keyed note may not make the real
    record a duplicate) and the classification that reports it. They disagreed for one revision,
    and the direction of the disagreement was a whole migration blocked by a table of notes.

    IT ASKS WHETHER THE FIELD IS THERE, NOT WHETHER IT IS READABLE, and that split is the
    correction of 2026-08-04. This used to demand `isinstance(status, str)`, so a record carrying
    `status: 7`, or the unquoted `NO` that PyYAML parses as a boolean, was reported as "carries no
    `status`" -- untrue about the record, and it dropped a record of a KNOWN backlog type out of
    the count of claimants for its own id. What an unreadable status means for the RUN is a
    separate verdict; see `_status_text` and its caller. A YAML null is the absent case: `status:`
    with nothing after it says as little as no key at all.
    """
    return isinstance(record, dict) and record.get(STATUS_FIELD) is not None


def _is_backlog_type(legacy_type: str) -> bool:
    """Is a record of this type a BACKLOG record at all? -- asked of both maps, in one place.

    Two maps answer half of it each and neither alone is the question: `v1_types` says the V1
    status vocabulary is known, `REQUIRED_FIELDS` says the kernel captures items of this type. A
    type in either is a backlog type whose records this harness owes an answer about; a type in
    neither is something else that happens to use the id shape. Spelled once because two branches
    of the classification ask it, and for a revision they asked it in two spellings.

    THE EXAMPLE IS FIELD DATA, and it replaces an invented one that stood in seven places (a
    `PROD-nnnn` product catalogue the office kit does not ship: its template's only entry is
    commented out, is spelled `PRD-A0001` and does not even match the id shape). A dev project's
    `acceptance_reports.yaml` keys each report `ACC-nnnn` and each criterion of it `AC-<n>`, with a
    `status` on the criteria; neither type is one any contract here knows, and treating them as
    unmappable backlog items blocked the whole migration of a project whose QA reports were simply
    QA reports. The counts behind that sentence are recorded once, in the fixture built from it --
    `test_migrate._fill_acceptance_reports` -- rather than here.
    """
    return legacy_type in v1_types() or legacy_type in REQUIRED_FIELDS


def _status_text(record):
    """The V1 status this record states, or None when the value is not text this run can map.

    The mapping table is keyed by a STRING, so a value that is not one cannot be looked up in it
    however plausible it looks -- and spec II.10's rule for a value a known backlog type cannot be
    mapped from is to BLOCK, never to guess. Kept apart from `_declares_status` so that neither
    answer has to stand in for the other.
    """
    status = record.get(STATUS_FIELD) if isinstance(record, dict) else None
    if isinstance(status, str) and status.strip():
        return status.strip()
    return None


def _read_document(state: ProjectState, rel: str):
    """(parsed payload, why the read produced no payload) -- `problem` is None exactly when the
    bytes on disk were turned into a payload.

    THE CONTRACT IS ABOUT THE READ, NOT ABOUT THE PAYLOAD, and the sentence it replaces said
    "exactly one of the two is None": an EMPTY document parses to `None`, so both were, and the
    only thing that told the two apart was that one of them never returned at all. Measured, and
    `test_migrate.test_the_readers_contract_holds_for_an_empty_document_and_for_every_failure`
    is where both directions are recorded.

    WHAT ENDS A READ IS NOT A LIST THIS MODULE KEEPS, and the two halves of that are worth keeping
    apart, because the paragraph that stood here named the wrong one as the fix.

    THE OPEN ITSELF IS NO LONGER HERE. It is `_read_bytes`, because this function was not the only
    place that opened a file under the state root and was the only one that survived a file it could
    not open -- see there for the measurement. What is left in here is the PARSE, and the two
    paragraphs below are about that.

    THE ENCODING CASE IS CARRIED BY THE BYTES, one line below. A kit document a Windows editor
    saved as UTF-16 or as ANSI used to raise `UnicodeDecodeError` (a `ValueError`) straight through
    the plan, the validator and the merge gate -- measured 2026-08-07 on the shipped
    `gate_memory_complete` as a process: rc 2 as an INTERNAL ERROR with a traceback and without the
    file's name in it, `validate` exit 1 printing one codec line and no finding, `build_plan`
    raising. What ended that is handing the bytes to `yaml.safe_load` UNCHANGED: a YAML stream
    declares its own encoding by a BOM and the reader implements that, so UTF-16 now READS, and
    what is not a stream in any declaration comes back as `yaml.reader.ReaderError` naming the
    offending byte. `ReaderError` IS a `yaml.YAMLError`, so a narrower `except (OSError,
    yaml.YAMLError)` handles the whole encoding class as well -- measured 2026-08-08 by restoring
    exactly that tuple in a clone outside the repo: the encoding test stays green. Decoding here
    first would have been this module picking a codec, which is the guess the same module refuses to
    make about a status.

    WHAT THE UNCONDITIONAL `except` CARRIES IS WHAT IS NEITHER, and it is reachable rather than
    theoretical: `yaml`'s composer recurses once per nesting level, so a document nested deeper than
    this interpreter's own limit allows raises `RecursionError` -- a `RuntimeError`, neither an
    `OSError` nor a `YAMLError`. Measured 2026-08-08 on this host (recursion limit 1000): a document
    nesting 400 sequences reads and scans, one nesting 500 raises. With the narrow tuple that
    exception leaves this function, and the merge gate answers a document with its crash handler
    again. `test_migrate.test_a_document_nested_deeper_than_the_reader_can_follow_is_named_not_a
    _crash` is where both directions are measured, including the counter-direction that matters
    here: the parser gives up BEFORE `scan_document`'s own walk does, measured at the boundary
    depth itself rather than assumed, so a document that reads is one the walk survives.

    So the rule is the property: turning a foreign file into a payload is a statement about the
    FILE, and every way it can fail is reported as one.

    THE REASON NAMES NO PATH -- built rather than asserted, because the assertion was measured
    false: `yaml.safe_load` names its stream in every mark, so reading through an open file made
    the reason carry the absolute path, and `report`'s finding then said the name twice (its
    `item` IS the path). Everything the exception says is kept; the one string this function
    opened the file with is replaced by a placeholder, and the result is folded onto one line
    because its readers print one finding per line.

    ITS CALLERS EACH PUT THE NAME WHERE THEIR OWN READER EXPECTS IT -- `build_plan` in the plan's
    `unreadable` list, `imported_legacy_ids` in the same list with what the blindness would cost,
    `execute` in its refusal, `render` in the wall listing, and
    `report._check_no_v1_records_outside_the_archive` in a per-document finding. That list is a
    claim about the code, so it is checked as one: the previous version of this paragraph counted
    three and there were four, and `test_migrate.test_the_readers_docstring_names_every_caller_it_has`
    reads the call sites out of the modules rather than out of this sentence.
    """
    raw, problem = _read_bytes(state, rel)
    if problem is not None:
        return None, problem
    try:
        return yaml.safe_load(raw), None
    except Exception as exc:                 # noqa: BLE001 -- see the docstring: this is the point
        return None, _unreadable_because(exc, state, rel)


def _without_path(text: str, state: ProjectState, rel: str) -> str:
    """`text` on one line, with the path this module opened replaced by a name for it.

    The path is removed rather than filtered out of a pattern: the caller of `_read_document`
    already holds the document's name, and the only path that can be in there is the one this
    module composed and handed to `open` -- so it is known exactly, not guessed at.

    TWO SPELLINGS OF ONE STRING, both derived from it rather than listed: a message that quotes
    the name writes it as Python writes a string LITERAL, so `FileNotFoundError` on Windows
    carries `C:\\\\dir\\\\file` where the YAML mark carries `C:\\dir\\file`. Removing only the
    first was measured by this function's own test before it shipped.

    IT COMPOSES THE PATH RATHER THAN BEING HANDED ONE, for the reason written at
    `_unreadable_because`: a function that only RECEIVES a path is one the static rule over this
    file cannot see, and a second reader inside it would have been licensed by nothing.
    """
    path = _state_path(state, rel)
    spellings = sorted({path, repr(path)[1:-1]}, key=len, reverse=True)
    for spelling in spellings:
        text = text.replace(spelling, "this document")
    return " ".join(text.split())


# -- what is already imported ---------------------------------------------------------------------


def imported_legacy_ids(state: ProjectState):
    """({(source, legacy_id): item id}, [(path, why it could not be read)]) -- the idempotency
    scan, and what it could not see.

    Read off the items themselves rather than from a manifest file. A manifest would be a second
    statement of the same fact, and the failure mode of a second statement is that it is the one
    that is wrong: an item deleted by hand would leave the manifest claiming an import that is not
    there, and a re-run would then skip a record nothing holds. The items ARE the record.

    A FILE IT CANNOT READ IS NAMED, and it used to be a bare `continue`. This map is the whole of
    "has this record already been imported": an item skipped here is an item whose `legacy_id` the
    plan does not know, so the record it came from is planned as NEW and the run writes a second
    item for one V1 record -- silently, and against the one promise a re-run makes. The reason
    joins `build_plan`'s `unreadable`, which is what makes the plan refuse instead.
    """
    seen, unreadable = {}, []
    for dirpath, dirs, files in os.walk(state.root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if layout.is_in_proposal_area(_relative(state, dirpath)):
            continue
        for name in sorted(files):
            if not name.endswith(".yaml"):
                continue
            rel = _relative(state, os.path.join(dirpath, name))
            if not layout.is_kernel_written(state.root, rel):
                continue
            item, problem = _read_document(state, rel)
            if problem:
                unreadable.append((
                    rel,
                    "%s -- this run reads every item the kernel wrote to find out which V1 "
                    "records are already imported, so a file it cannot read would let a record be "
                    "imported a second time" % problem))
                continue
            legacy = (item or {}).get(LEGACY_FIELD) if isinstance(item, dict) else None
            if isinstance(legacy, dict) and legacy.get("legacy_id"):
                seen[(str(legacy.get("legacy_source") or ""),
                      str(legacy["legacy_id"]))] = item.get("id")
    return seen, unreadable


# -- the field decision ----------------------------------------------------------------------------


def parse_field_map(entries) -> dict:
    """`TYPE.v2_field=v1_field` -> {(TYPE, v2_field): v1_field}, or a MigrationError.

    Flag-shaped rather than a body on stdin, unlike `capture`: this is a handful of scalar pairs
    the DRY RUN itself prints, so what a human does with it is paste a line back, and a line is
    what a shell carries best.
    """
    mapping = {}
    for entry in entries or []:
        left, sep, right = str(entry).partition("=")
        item_type, dot, field = left.partition(".")
        if not (sep and dot and item_type and field and right):
            raise MigrationError(
                "--map %r is not a mapping. Remedy: spell it TYPE.v2_field=v1_field, e.g. "
                "`--map PROC.roles=owner`; `python scripts/harness.py migrate --dry-run` "
                "prints the exact flags this state needs." % (entry,))
        if item_type not in REQUIRED_FIELDS:
            raise MigrationError(
                "--map %r names type %r, which the kernel does not capture. Remedy: use one of "
                "%s." % (entry, item_type, "/".join(sorted(REQUIRED_FIELDS))))
        contract = set(REQUIRED_FIELDS[item_type]) | set(OPTIONAL_FIELDS.get(item_type, ()))
        if field not in contract:
            raise MigrationError(
                "--map %r names %s field %r, which is not in that type's contract. Remedy: use "
                "one of %s." % (entry, item_type, field, ", ".join(sorted(contract))))
        mapping[(item_type, field)] = right
    return mapping


def _item_fields(v2_type: str, record: dict, field_map: dict, provenance=None):
    """(fields, missing) -- the V2 item body this V1 record yields, and what it still lacks.

    THE RULE, and it is the whole of the field policy: a field carries over when both contracts
    spell it the same, or when `--map` says which V1 field it is. Nothing is inferred from a
    similar name, a similar type or a position. `missing` is what the dry run turns into flags.

    THE ONE EXCEPTION IS NOT A GUESS ABOUT THE RECORD: a required field in `PROVENANCE_FIELDS` is
    about where the record came from, which is the importer's own fact and nobody else's. See that
    constant for why it is a field name rather than a type. `--map` still wins over it.

    DEEP-COPIED, and this is not hygiene. The same V1 record is read twice -- once for the item's
    own fields and once for the verbatim copy under `legacy_fields` -- and handing out the same
    list object twice made `yaml.safe_dump` write an ANCHOR and an ALIAS (`steps: &id001` /
    `steps: *id001`, measured in a real imported PROC). The file is still valid YAML, but the two
    fields are then ONE object on the way back in, so editing the item's `steps` through the
    kernel would silently rewrite the legacy record that exists to say what V1 held.
    """
    fields, missing = {}, []
    contract = list(REQUIRED_FIELDS[v2_type]) + list(OPTIONAL_FIELDS.get(v2_type, ()))
    required = set(REQUIRED_FIELDS[v2_type])
    for name in contract:
        source = field_map.get((v2_type, name), name)
        if source in record:
            fields[name] = copy.deepcopy(record[source])
        elif name in required and name in PROVENANCE_FIELDS and provenance:
            fields[name] = provenance
        elif name in required:
            missing.append(name)
    return fields, missing


def _field_suggestions(legacy_type: str, record: dict, missing) -> dict:
    """{v2 field: (v1 field, why)} for the missing fields this V1 store has a proposal for.

    TWO CONDITIONS, and the second is what keeps a suggestion from being a guess about THIS record:
    `backlog_types.V1_FIELD_SUGGESTIONS` has to hold a row for the store's own V1 type, and the
    record in front of us has to actually carry that V1 field. A row is a statement about what a
    kit's V1 template shipped; a record that never filled the field is answered by nothing, and
    proposing a flag that would carry nothing is the same silence with a friendlier name.

    A `--map` the human already typed is not in `missing` by then, so it wins by construction
    rather than by a precedence rule spelled here.
    """
    found = {}
    for name in missing:
        suggestion = suggested_v1_field(legacy_type, name)
        if suggestion and suggestion[0] in record:
            found[name] = suggestion
    return found


def _with_legacy(fields: dict, entry: dict, record: dict) -> dict:
    """The COMPLETE item body an import writes -- one definition, two callers.

    `build_plan` measures this shape against the item budget and `execute` writes it. Two
    assemblies of one body is how a plan comes to measure something the run does not write, so
    there is one.
    """
    body = dict(fields)
    body[LEGACY_FIELD] = {
        "legacy_id": entry["legacy_id"],
        "legacy_source": entry["source"],
        "legacy_type": entry["legacy_type"],
        "legacy_status": entry["legacy_status"],
        # what the V1 status WOULD mean in V2 terms -- recorded, never walked: the item starts at
        # its own initial status (spec II.10), and only a user action moves it from there.
        "mapped_status": entry["mapped_status"],
        "archive_candidate": entry["archive_candidate"],
        # WHERE THE RUN PUT IT, which is not the same question as `archive_candidate`: a record can
        # be finished in V1 and still land in active/, and on the shipped tables that happens for
        # two different reasons -- the status is one only a user approval could have reached
        # (`EXP DONE` -> `COMPLETED`), or the type has no automaton for this kernel to walk at all
        # (`ADR SUPERSEDED` -> a `DEC`). Both are `state.migration_archive_status`. The item says
        # which of the two answers it got rather than leaving a reader to re-derive them.
        "written_to": entry["target"],
        "record": copy.deepcopy(record),
    }
    if entry.get("unresolved_fields"):
        # DEC-0009's second archive door writes a record NOBODY could translate, so the item
        # carries the sentence that says so. `state.capture_migrated_unresolved` refuses a body
        # without it, which is why this is composed here and not there: the writer must not be
        # able to invent a reason for a record it never read.
        body[LEGACY_FIELD]["unresolved"] = entry["reason"]
    body[IMPORT_MARK] = True
    return body


def item_size(fields: dict, v2_type: str = RECEIPT_TYPE):
    """(bytes, lines) the kernel would write for this body -- the measure, without the verdict.

    Its own function so a test can compare it against a REAL captured item instead of against the
    verdict, which only speaks when the budget is already blown. That comparison is what caught the
    placeholders being one byte short; see `_too_large` for what they are now.
    """
    shape = dict(fields)
    # A LENGTH, NOT A STATUS. What this needs is a placeholder that can never be shorter than the
    # real value; what it must NOT be is a status word, because then this line reads as a direct
    # status write. The reader that bounds every such write against the statuses a user approval
    # commits lives in `tools/test_approvals_dispatch.py` and is named
    # `test_no_direct_status_write_can_produce_a_status_an_approval_commits`; the day
    # `widest_status()` first returned an approval-bound word (`ACCEPTED_EXCEPTION`, FR-0087) this
    # measurement was reported as a writer of it. Nothing here is stored: the body is dumped to be
    # counted and thrown away.
    shape.update({"id": format_id(v2_type, 9999), "status": "x" * len(widest_status()),
                  "revision": 1,
                  "approval_ref": None, "created": "0000-00-00T00:00:00"})
    dumped = yaml.safe_dump(shape, sort_keys=False, allow_unicode=True)
    return len(dumped.encode("utf-8")), dumped.count("\n")


def _too_large(fields: dict, v2_type: str = RECEIPT_TYPE):
    """The reason this item body would exceed spec II.5's per-item budget, or None.

    Measured on the SHAPE THE KERNEL WILL WRITE -- the caller's fields plus placeholders of the
    kernel-set ones, dumped exactly as `ProjectState._write_yaml_atomic` dumps them -- rather than
    on the fields alone, so the answer is not a guess with a margin on top. The limits are
    `report`'s own constants, the same two numbers `validate` reports against; this exists so that
    a migration refuses to write an item the validator would immediately flag, instead of leaving
    a project with an oversized file no editing route can shrink.

    WHOSE ITEMS THAT COVERS is decided by the CALLER and is deliberately not this function's
    business -- see `_settle_bindings`, where an archive-bound record is not asked, and
    `_receipt_fields`, where the run's own `DEC` is.

    THE PLACEHOLDERS ERR UPWARDS, WHICH IS THE ONLY SAFE DIRECTION, and the previous ones did not:
    they were the literals `id: DEC-0000` and `status: VALID`, which are one byte SHORTER than a
    real `PROC-0001` / `DRAFT` -- measured constant at +1 B over three samples. A budget check that
    under-measures passes exactly the items that then fail `validate`. So the id is the widest this
    type's four-digit allocator produces and the status is the longest any shipped automaton
    carries. THE RESIDUAL, since this is the sentence that was wrong before: past 9999 items of one
    type an id grows by a digit, and this measure is short by that one byte per id.
    """
    size, lines = item_size(fields, v2_type)
    if size > ITEM_MAX_BYTES or lines > ITEM_MAX_LINES:
        return ("would be %d bytes / %d lines; spec II.5 caps an ACTIVE item at %d / %d, and "
                "`python scripts/harness.py validate` reports an active item above that as an "
                "error" % (size, lines, ITEM_MAX_BYTES, ITEM_MAX_LINES))
    return None


# -- the plan ------------------------------------------------------------------------------------


def archive_location(v2_type: str, year=_YEAR_PLACEHOLDER) -> str:
    """The state-relative DIRECTORY an archived item of this type is written into.

    ASKED OF THE PATH BUILDER, never composed a second time here, and that is the correction of a
    defect one filesystem hides: the three places that printed this composed `archive/<type>/` out
    of `v2_type.lower()`, while `ProjectState.archive_path` keys the directory by the id's own type
    -- so the run created `archive/PR/2026/` and told the reader `archive/pr/2026/`. On Windows and
    APFS the two open the same directory; on the case-sensitive filesystems the installers also
    support, the printed one is a path nobody finds. Composing it once, from the builder, is what
    makes the printed path and the created path one answer rather than two.

    `year` stays a placeholder where the caller has no year yet, so both readings come out of the
    same composer.
    """
    probe = ProjectState(os.curdir)
    directory = os.path.dirname(probe.archive_path(format_id(v2_type, 1), year))
    return os.path.relpath(directory, probe.root).replace(os.sep, "/") + "/"


def legacy_location(rel: str) -> str:
    """The state-relative path a fully absorbed V1 document is moved to (SR-0005).

    ASKED OF THE PATH BUILDER, for the same reason `archive_location` is, and it is the same
    defect one file further on: the dry run composed this target by hand (`"legacy/" + path`)
    while `_retire_absorbed_documents` moves the file to `ProjectState.legacy_path`. The two agree
    today -- that is a coincidence between two spellings, not a property, and the archive path
    above is what a coincidence like that looks like once a filesystem stops hiding it.
    """
    probe = ProjectState(os.curdir)
    return os.path.relpath(probe.legacy_path(rel), probe.root).replace(os.sep, "/")


def _archive_year_of(value, where: str):
    """`value` as an archive year, or a MigrationError naming where it came from.

    ONE JUDGE FOR THE TWO PRODUCERS (`_YEAR_RE` is the shape). The flag was checked by `int` alone
    and the record's own date by `_DATE_RE`, so the two disagreed about what a year is -- and the
    one that agreed with nothing is the one that reaches `ProjectState.archive_path`, which builds
    a directory name out of it.
    """
    text = str(value).strip()
    if not _YEAR_RE.fullmatch(text):
        raise MigrationError(
            "%r is not an archive year (%s). An item is filed in a per-type, per-year archive "
            "directory, and a year here is four digits -- the same shape this command reads out of "
            "a record's own dates. Remedy: give the four-digit year." % (value, where))
    return int(text)


def build_plan(state: ProjectState, field_map: dict = None, archive_year=None) -> dict:
    """Everything the run would read and do, as data. Reads the disk; writes nothing.

    Carries no timestamp and no absolute path on purpose: the digest below is taken over this
    object, and a plan that changed every second could not be handed back.

    TWO PHASES, and the second one exists because the first cannot answer its own question. The
    document loop classifies each record on its own; `_settle_bindings` then resolves the bindings
    BETWEEN records, orders the writes and asks the writer's verdict. See there for the defect that
    forced the split.
    """
    field_map = field_map or {}
    if archive_year is not None:
        # Refused HERE and not at the record that happens to need it: a flag nothing in this state
        # uses is still a flag the caller meant something by, and learning about it on the next run
        # is learning about it after the reading.
        archive_year = _archive_year_of(archive_year, "--archive-year")
    already, unreadable = imported_legacy_ids(state)
    already_by_id = {}
    for (source, legacy_id), item_id in sorted(already.items()):
        already_by_id.setdefault(legacy_id, []).append((source, item_id))
    inventory, records, carried_values = [], [], {}
    # WHICH FILES ARE SEARCHED IS NOT DECIDED HERE, and it was for a round: `search_coverage` is
    # the one run-up both this command and the validator read, so a file the two would classify
    # differently no longer exists. The inventory below is a different question -- what the run
    # READ and carries a hash of -- and is still `documents`.
    # THE WALLS, READ ONCE FOR THE WHOLE RUN. The two parts of this command that MOVE or read a
    # wall's bytes need them -- `absorbed_documents` (it may not move one) and the dry run's own
    # wall section -- and asking `layout.gated_documents` twice is how they come to disagree about
    # one file. The coverage run-up is no longer among them: since DEC-0024 it names no move at
    # all, so it has no move it could name onto a document a gate reads.
    walls = walls_of(state)
    coverage = search_coverage(state)
    unscanned = ["%s (%s)" % pair for pair in unsearched_notes(coverage)]
    # THE DEPOSIT COPIES, CARRIED AS A COUNT AND NOT AS LINES (BUG-0028). One appears per remedy a
    # reader applies, so naming each in `unscanned` grew that section without bound; the paths are
    # kept (sorted) so the dry run can say how many and, on demand, which -- one summary line.
    deposits = sorted(rel for rel, _why in deposit_notes(coverage))
    # A SUBTREE NOBODY COULD LIST IS A READING FAILURE, not a coverage note, so it goes where a
    # reading failure goes: `unreadable` is what `plan_is_executable` refuses on. The alternative --
    # a note beside the plan -- is what the walk already did on its own, and it was measured as
    # silence with a plan that said READY.
    unreadable += list(unlistable_notes(coverage))
    searched = {rel for rel, verdict, _why in coverage if verdict == SEARCHED}
    pending, parsed = [], []
    for rel in documents(state):
        # A FILE NOBODY COULD OPEN IS THE SAME KIND OF ANSWER AS A DIRECTORY NOBODY COULD LIST, and
        # it used to be the one shape of blindness this command answered with a traceback instead of
        # a refusal (`_read_bytes` carries the measurement).
        facts, problem = _file_facts(state, rel)
        if problem:
            unreadable.append((rel, problem))
            continue
        inventory.append(facts)
        if rel not in searched:
            continue
        payload, problem = _read_document(state, rel)
        if problem:
            unreadable.append((rel, problem))
            continue
        parsed.append((rel, scan_document(payload)))
    # A LEGACY ID NAMES ONE V1 RECORD, WHEREVER IT LIES -- so the claimants are counted over the
    # WHOLE run and not per document, and the same count is what the store is asked for below.
    # Per document was the first cut and it was half the rule: two documents each holding a
    # `PROC-0001` produced two items for one V1 record, which is the same unresolvable state as two
    # in one file. Reading the ids ahead of the classification loop is what lets the second record
    # be refused as well as the first; the alternative -- refusing whichever came later -- would
    # make the verdict depend on the walk order of a directory.
    #
    # ONLY ITEMS CLAIM AN ID, and "item" is TWO conditions rather than one.
    #
    # A mapping keyed by an id and carrying no status is a cross-reference table, which is why the
    # classification below reports it and never blocks on it -- and counting it as a claimant would
    # have turned exactly that document into a blocker for the whole run, one branch above the one
    # that exists to prevent it. `_declares_status` is the same question both places ask, and it
    # asks whether the field is THERE: a record whose status this run cannot read is still a
    # record, and dropping it out of the count here would let a second record take its id
    # unopposed.
    #
    # AND IT HAS TO BE A BACKLOG TYPE. A collision is a conflict about which ITEM gets the legacy
    # id, and a record of a type no contract knows never becomes an item at all -- `not_an_item` is
    # a FINAL answer about it, so two of them sharing a number conflict about nothing. Measured on
    # the field copy of `synaipse` (2026-08-05), and it is the counter-defect of reading one- and
    # two-digit numbers: `acceptance_reports.yaml` keys six of its acceptance criteria `AC-1` with
    # `status: met`, once per report, and the run refused sixty records -- and with them the whole
    # migration -- over a document whose entries this command never imports and which no `--map`
    # and no renumbering could help, because the ids are the criteria's own numbering inside each
    # report.
    claimants = {}
    # ...AND ONE MAPPING NAMES ITSELF ONCE, which is the same rule seen from the other side.
    # `scan_document` reads both ways a mapping can carry an id, so a mapping whose key and whose
    # own `id` field disagree arrives here twice. Counting the names per MAPPING (by object
    # identity -- `parsed` holds the parsed documents, so the objects stay alive) is what lets the
    # branch below refuse it instead of writing one V1 mapping into the store as two items. Across
    # all three field copies (2026-08-05) no mapping does this, so the branch costs those runs
    # nothing; it exists because the widened reader is what makes the shape reachable at all.
    self_named = {}
    for rel, found in parsed:
        for _ordinal, key, record in found:
            self_named.setdefault(id(record), set()).add(key)
            if _declares_status(record) and _is_backlog_type(V1_ID_RE.match(key).group(1)):
                claimants.setdefault(key, []).append(rel)
    for rel, found in parsed:
        for ordinal, key, record in found:
            entry = {"source": rel, "ordinal": ordinal, "legacy_id": key,
                     "legacy_type": V1_ID_RE.match(key).group(1)}
            names = self_named.get(id(record), {key})
            if len(names) > 1 and _declares_status(record) \
                    and _is_backlog_type(entry["legacy_type"]):
                # A DEFECT INSIDE THE RECORD, so it is decided before the ones about other records.
                # The condition is the claimant rule's own: a mapping that never becomes an item
                # cannot become two, so a criterion or a note wearing two ids is reported by the
                # branches below and blocks nothing.
                entry["verdict"] = "blocked"
                entry["reason"] = (
                    "this one mapping identifies itself with %d different ids (%s): a V1 record "
                    "names itself by the key it is filed under AND by its own `id` field, and "
                    "these disagree. Importing it would put the same V1 mapping in the store as "
                    "two items, and leaving one of the names unread would make it invisible to "
                    "this report. Remedy: in the V1 file, make the `id` field agree with the key, "
                    "or split the mapping into the two records it claims to be. Then re-run the "
                    "dry run." % (len(names), ", ".join("`%s`" % one for one in sorted(names))))
                records.append(entry)
                continue
            if len(claimants.get(key, ())) > 1:
                entry["verdict"] = "blocked"
                # THE REMEDY IS TWO BRANCHES BECAUSE THE SITUATION IS, and printing one of them for
                # both was measured wrong in both directions. "Split the document" was in here and
                # cannot help at all -- the claimants are counted over the WHOLE run, which the
                # comment fifty lines up says and this line contradicted. And "give them distinct
                # ids" is the right answer only when the two records really are two things: the
                # research kit's `fzulg_documentation.yaml` keys the BSFZ application layer by the
                # research question it documents, so every one of its entries collides with the
                # `research_questions.yaml` entry it is ABOUT -- renumbering it would import the
                # documentation as a second, parallel RQ backlog, one item per question that has
                # nothing to do with that question's life. For that shape the walkable answer is to
                # take the document out of the state directory before the run.
                entry["reason"] = (
                    "%s appears %d times in this run, in %s. Two items cannot both carry it as "
                    "`legacy_fields.legacy_id` -- that is the key a re-run recognises an import "
                    "by, and the count is over the whole run, so moving one of them into a "
                    "separate file changes nothing. Remedy: decide which of the two is a BACKLOG "
                    "RECORD. If both are, give one a distinct id in the V1 file. If one of them "
                    "describes the OTHER one under its id -- a second document keyed by the record "
                    "it documents -- it is not a backlog record at all and renumbering it would "
                    "import it as a second item for one subject: move that document out of the "
                    "state directory instead. Then re-run the dry run."
                    % (key, len(claimants[key]), ", ".join(sorted(set(claimants[key])))))
                records.append(entry)
                continue
            if not _declares_status(record):
                # An id-keyed mapping with no status is not a V1 ITEM -- a cross-reference table
                # looks exactly like one. Reported so it is not silently invisible, never
                # imported, and never a reason to block: blocking on it would make a document a
                # project cannot change into a migration it can never run.
                entry["verdict"] = "not_an_item"
                entry["reason"] = "carries no `%s`, so nothing maps it" % STATUS_FIELD
                records.append(entry)
                continue
            status_text = _status_text(record)
            if status_text is None:
                # DECLARED BUT UNREADABLE, which is neither of the two findings above and may not
                # be reported as either. Spec II.10 blocks on a value a known backlog type cannot
                # be mapped from, and this is that case one step earlier: the value is not even
                # text to look up. Which of the two findings it is still depends on the TYPE, by
                # the same rule the branch further down uses (`_is_backlog_type`): a record of a
                # type no contract knows is not a backlog record whatever its status says.
                unreadable_status = repr(record[STATUS_FIELD])
                if _is_backlog_type(entry["legacy_type"]):
                    entry["verdict"] = "blocked"
                    entry["reason"] = (
                        "carries a `%s` this run cannot read: %s is not text, and spec II.10's "
                        "mapping table is keyed by the V1 status STRING -- so nothing maps it and "
                        "nothing here guesses. `%s` is a backlog type, so this blocks rather than "
                        "being reported past. Remedy: quote the value in the V1 file (an unquoted "
                        "`NO`, `YES` or `ON` is a BOOLEAN to a YAML reader, not a status), then "
                        "re-run the dry run."
                        % (STATUS_FIELD, unreadable_status, entry["legacy_type"]))
                else:
                    entry["verdict"] = "not_an_item"
                    entry["reason"] = (
                        "carries a `%s` that is not text (%s), and `%s` is no backlog type this "
                        "harness knows either, so this is a record of some other kind"
                        % (STATUS_FIELD, unreadable_status, entry["legacy_type"]))
                records.append(entry)
                continue
            entry["legacy_status"] = status_text
            if (rel, key) in already:
                entry["verdict"] = "already_imported"
                entry["item_id"] = already[(rel, key)]
                records.append(entry)
                continue
            if key in already_by_id:
                # THE SAME RULE AS ABOVE, ASKED OF THE STORE: a legacy id names one V1 record
                # wherever it lies, so a known one arriving under a NEW path is a finding rather
                # than a new record. Measured before this: renaming the V1 document was enough to
                # make the whole store import a second time -- the idempotency key was the PAIR
                # (source, legacy id), so every record came back as unseen, and the third bolt of
                # DEC-0004 held for each item while the RECORD was reactivatable by a `mv`.
                held = already_by_id[key]
                entry["verdict"] = "blocked"
                entry["reason"] = (
                    "%s is already in this state as %s, imported from %s -- and this run reads it "
                    "from %s. A legacy id names ONE V1 record wherever it lies, so importing it "
                    "again would put a second item in the store for one record and leave a re-run "
                    "unable to tell them apart. Remedy: if this is the same record under a new "
                    "path, it is already imported and this copy needs nothing done to it -- move "
                    "it out of the state directory; if it is a DIFFERENT record that happens to "
                    "share the id, give it a distinct id in the V1 file. Then re-run the dry run."
                    % (key, ", ".join(item_id for _s, item_id in held),
                       ", ".join(source or "(unrecorded)" for source, _i in held), rel))
                records.append(entry)
                continue
            if entry["legacy_type"] not in v1_types():
                # THREE OUTCOMES, NOT TWO, and the middle one is the correction of 2026-08-04.
                # The previous cut asked ONE question -- "does the mapping table know this type"
                # -- and answered "not a backlog record" whenever it did not. Measured against a
                # real dev scaffold with a V1 `bugs.yaml` and a research one with
                # `research_questions.yaml`: `BUG`, `CR`, `FR`, `RQ`, `HYP` and `EXP` are V2 ITEM
                # TYPES with their own `ACTIVE_DIRS` entry, and every one of them was reported as
                # "no V1 backlog type" and the run exited 0. A false all-clear over most of two
                # kits' stores, produced by the fix for the opposite defect.
                #
                # So the question is asked of the right map. `REQUIRED_FIELDS` says whether a type
                # is an ITEM this kernel captures; the mapping table says whether its V1 status
                # vocabulary is known. A type in neither is genuinely something else, and blocking
                # a project's whole migration over such a store is the dead end this branch exists
                # to avoid -- `_is_backlog_type` is that union, carries the measured example, and
                # is what the unreadable-status branch above asks in the same words. A type in the
                # FIRST but not the second is a harness gap, and a harness gap may not present
                # itself as "nothing to do".
                if _is_backlog_type(entry["legacy_type"]):
                    entry["verdict"] = "blocked"
                    entry["reason"] = (
                        "`%s` IS a V2 item type, but spec II.10's mapping table has no row for it, "
                        "so nothing here knows what its V1 statuses mean. This is a HARNESS gap, "
                        "not a project one: the table lives in the enforcement layer, which a "
                        "session may not edit. Remedy: record it with `python scripts/harness.py "
                        "capture DEC` and report it -- the run refuses rather than reporting an "
                        "all-clear over records it cannot read." % entry["legacy_type"])
                else:
                    entry["verdict"] = "not_an_item"
                    entry["reason"] = (
                        "`%s` is no item type this kernel captures and has no row in spec II.10's "
                        "mapping table either, so this is a record of some other kind that happens "
                        "to use the id shape" % entry["legacy_type"])
                records.append(entry)
                continue
            try:
                v2_type, v2_status, archive_candidate = map_v1_status(
                    entry["legacy_type"], entry["legacy_status"])
            except UnknownV1Status as exc:
                entry["verdict"] = "blocked"
                entry["reason"] = str(exc)
                records.append(entry)
                continue
            entry.update({"v2_type": v2_type, "mapped_status": v2_status,
                          "archive_candidate": bool(archive_candidate)})
            if v2_type not in REQUIRED_FIELDS:
                entry["verdict"] = "blocked"
                entry["reason"] = (
                    "%s maps to %s, which `capture` does not create (it is frozen through the "
                    "promotion path). Remedy: record a Decision item and migrate it by hand."
                    % (key, v2_type))
                records.append(entry)
                continue
            # WHERE IT LANDS -- asked of the WRITER's own rule (`state.migration_archives`), never
            # re-derived here. Both halves of that rule (does the table call this record finished,
            # and may the import write the status at all) live at `migration_archive_status`, and
            # the one time this line spelled a condition of its own the plan and the writer could
            # disagree about a row.
            entry["target"] = ("archive"
                               if migration_archives(v2_type, entry["legacy_type"],
                                                     entry["legacy_status"])
                               else "active")
            fields, missing = _item_fields(v2_type, record, field_map,
                                           provenance=_provenance(rel, key))
            entry["carried_fields"] = sorted(fields)
            entry["missing_fields"] = missing
            if missing and entry["target"] == "active":
                # THE TWO ANSWERS A GAP CAN HAVE, and telling them apart is SR-0007 and DEC-0009
                # meeting. A field this store HAS a proposal for is a question with an answer
                # printed beside it, and the run stays unexecutable until a human types it back --
                # a suggestion is not a confirmation. A field NOTHING can propose and no `--map`
                # named is a gap V1 never collected, and DEC-0009 archives that record with the
                # gap as its reason instead of refusing the whole run over it.
                suggested = _field_suggestions(entry["legacy_type"], record, missing)
                entry["record_keys"] = sorted(str(k) for k in record)
                if suggested:
                    entry["suggested_fields"] = {
                        name: list(pair) for name, pair in sorted(suggested.items())}
                unanswered = [name for name in missing if name not in suggested]
                if not unanswered:
                    entry["verdict"] = "needs_decision"
                    records.append(entry)
                    continue
                entry["unresolved_fields"] = unanswered
                entry["target"] = "archive"
                entry["reason"] = (
                    "V1 collected nothing for %s, and no `--map` and no suggestion of this "
                    "harness can name a field that does: the record carries %s. DEC-0009: this is "
                    "archived with that reason rather than blocking the run. Remedy, if you want "
                    "it as a LIVE item instead: add the field(s) to this record in the V1 file "
                    "(in an editor outside the session), or name the V1 field they come from with "
                    "`--map`, then re-run the dry run."
                    % (", ".join(unanswered), ", ".join(entry["record_keys"])))
            if entry["target"] == "archive":
                year, source_of_year = _record_year(record), "the record's own newest date"
                if year is None and archive_year:
                    year, source_of_year = archive_year, "--archive-year"
                if year is None:
                    entry["verdict"] = "blocked"
                    entry["reason"] = (
                        "%s belongs in %s rather than under active (%s), and this "
                        "record carries no date, so nothing here knows which year. Nothing is "
                        "guessed. Remedy: re-run with `--archive-year <YYYY>`, which applies to "
                        "every dated-nowhere record of this run."
                        % (key, archive_location(v2_type),
                           entry.get("reason")
                           or "finished in V1: %r" % entry["legacy_status"]))
                    records.append(entry)
                    continue
                try:
                    entry["archive_year"] = _archive_year_of(year, source_of_year)
                except MigrationError as exc:
                    # A record whose own newest date is a year outside the four-digit shape --
                    # PyYAML parses `0012-01-01` into a real `datetime.date`, and `_record_year`
                    # answers 12. A blocked record rather than a refused run, because it is one
                    # record's data and every other record of the run is unaffected.
                    entry["verdict"] = "blocked"
                    entry["reason"] = "%s belongs in %s, and %s" % (
                        key, archive_location(v2_type), str(exc)[0].lower() + str(exc)[1:])
                    records.append(entry)
                    continue
                entry["archive_year_from"] = source_of_year
            for (map_type, map_field), source_field in field_map.items():
                if map_type == v2_type and source_field in record:
                    carried_values.setdefault(
                        "%s.%s <- %s" % (map_type, map_field, source_field),
                        set()).add(repr(record[source_field]))
            pending.append((entry, record, fields))
            records.append(entry)
    _settle_bindings(state, records, pending)
    fingerprint, unreadable_here = state_fingerprint(state)
    unreadable += unreadable_here
    plan = {"documents": inventory,
            "state": fingerprint,
            # THE WALLS, CARRIED IN THE PLAN. Read once above; in the plan rather than beside it, so
            # the digest covers them: installing or removing a gate between the reading and the
            # writing changes what the run may move.
            "gated_documents": walls,
            "root_items_after": _root_items_after(state, records),
            "records": sorted(records, key=lambda e: (e["source"], e["ordinal"])),
            "field_map": {"%s.%s" % key: value for key, value in sorted(field_map.items())},
            "archive_year": int(archive_year) if archive_year else None,
            "carried_values": {pair: sorted(values) for pair, values in carried_values.items()},
            "unscanned": sorted(unscanned),
            # THE DEPOSIT COPIES, as their own list so the dry run counts them in one line rather
            # than one `NOT SEARCHED` per applied remedy (BUG-0028).
            "deposits": deposits,
            # PAIRS, not sentences: `_unreadable_paths` counts the paths, and a path recovered from
            # a sentence is a path that ends at the first space (see there). Written as LISTS
            # because the plan goes through `canonical_json` on its way to the digest, and a tuple
            # comes back out of JSON as a list -- one shape in, one shape out.
            "unreadable": sorted([list(pair) for pair in unreadable])}
    # THE LANDING PLACES OF THE MOVE THIS RUN WOULD MAKE, asked after the plan is otherwise whole
    # because `absorbed_documents` reads it. SR-0001's rule that the dry run reports the same
    # condition the run refuses on: `plan_is_executable` reads this key too.
    # THE THIRD COLUMN IS THE OCCUPANT'S OWN CONTENT, read here rather than at the printer because
    # this is where the state is: `render` may be handed a plan without one. What it is for is
    # argued at `overflow_deposit_of` -- it is the part of the remedy's target name that keeps a
    # later instruction from landing on an earlier file.
    plan["occupied_landings"] = sorted(
        [rel, legacy_location(rel), _occupant_digest(state, legacy_location(rel))]
        for rel in absorbed_documents(plan)
        if _is_occupied(state, legacy_location(rel)))
    return plan


def _root_items_after(state: ProjectState, records: list) -> dict:
    """{root type: (items left ACTIVE after this run, records of it this run archives)}.

    WHY THE MIGRATION COUNTS THIS AT ALL. DEC-0009 archives a record no answer can fill, and the
    types that meet that most often are exactly the ROOT types: a V1 product requirement carries
    none of `class`, `problem`, `goal`, `invariants`, `out_of_scope`, `priority`. Measured on the
    two dev field copies (2026-08-05): every one of their 38 product requirements is archived, and
    the migrated project then holds no active `PR` file at all.

    That is not a state the kernel refuses -- it is the decision DEC-0009 made -- but it is one a
    reader has to see BEFORE the run, because an archived item cannot be brought back. The kits'
    setup-phase predicate reads the presence of an active root item FILE (`hooks/_root.py`,
    `ROOT_ITEM_GLOBS`; `test_hooks.test_root_item_globs_are_the_kernels_root_types` derives that
    tuple from `ACTIVE_DIRS` + `ROOT_TYPE_BY_KIT`), so a project in this state answers that
    predicate the way a project before its first requirement does.

    Which types are root types is asked of `ROOT_TYPE_BY_KIT`, the same map the entry gate seeds
    from, rather than named here.
    """
    after = {}
    for root_type in sorted(set(ROOT_TYPE_BY_KIT.values())):
        if root_type not in ACTIVE_DIRS:
            continue
        live = len([one for one, _path in state.iter_active_items(root_type)])
        live += len([entry for entry in records
                     if entry.get("v2_type") == root_type
                     and entry["verdict"] == "translatable" and entry.get("target") != "archive"])
        archiving = len([entry for entry in records
                         if entry.get("v2_type") == root_type
                         and entry["verdict"] in _IMPORTING_VERDICTS
                         and entry.get("target") == "archive"])
        after[root_type] = [live, archiving]
    return after


def _provenance(rel: str, legacy_id: str) -> str:
    """What a `PROVENANCE_FIELDS` field is filled with -- one composer, so the receipt and the
    item cannot describe the same import differently."""
    return "V1 import: %s in %s" % (legacy_id, rel)


def _record_year(record):
    """The newest year any date-shaped value in this V1 record carries, or None.

    THE RULE AND ITS LIMIT IN ONE SENTENCE: an item is archived under the year its life ended, and
    no date the record itself carries is later than that -- so the newest one is the answer, and a
    record with no date at all gets NO answer rather than a plausible one (SR-0004: "wo keines
    dasteht ... ist es eine vorgelegte Entscheidung und keine Vermutung"). Read off the VALUES
    rather than off a field name, because V1 spelled the field `completed` in `tasks.yaml`, `date`
    in `filing_log.yaml` and nothing at all in `system_requirements.yaml`.

    WHAT THAT COSTS, stated rather than left to be found: a V1 record carrying a FUTURE date (a
    deadline, a retention date) yields that year, and the archive path then files it under a year
    in which nothing happened. `--archive-year` cannot override it -- that flag answers only the
    records that carry no date at all -- so such a record is filed by its own newest date and the
    dry run prints which year each archive-bound record got and where it came from.

    Walked by identity like `scan_document`, for the same reason: a YAML anchor can make a record
    self-referencing, and a value seen twice adds no year.
    """
    years, seen = set(), set()

    def walk(node):
        if id(node) in seen:
            return
        seen.add(id(node))
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)
        elif isinstance(node, datetime.date):
            years.add(node.year)
        elif isinstance(node, str):
            years.update(int(found) for found in _DATE_RE.findall(node))
    walk(record)
    return max(years) if years else None


def _rebind(v2_type: str, fields: dict, resolution: dict) -> dict:
    """`fields` with every binding value this plan resolves replaced by the id it resolves to.

    A V1 store names its parents by V1 id, and V2 REALLOCATES: the V1 `PROC-0001` may land as
    `PROC-0004` in a project that already holds three procedures, so carrying `derives_from:
    PROC-0001` over verbatim would bind the child to whatever else happens to be called that. The
    fields this touches are `PARENT_FIELDS`, the same set the kernel checks the binding of, so a
    field that binds and a field that is rewritten cannot become two different lists.
    """
    if not resolution:
        return fields
    bound = dict(fields)
    for field in PARENT_FIELDS.get(v2_type, ()):
        if field not in bound:
            continue
        value = bound[field]
        if isinstance(value, (list, tuple)):
            bound[field] = [resolution.get(str(one), one) for one in value]
        else:
            bound[field] = resolution.get(str(value), value)
    return bound


def _planned_resolution(records: list, pending: list) -> dict:
    """{V1 id: the id a binding on it will name} -- at PLAN time, with stand-ins for what is new.

    WHAT IT IS AND IS NOT. For a record an earlier run already imported this is the real item id,
    read off that item's own `legacy_fields`. For a record THIS run will create the id does not
    exist yet -- the kernel allocates it under the lock -- so the entry is a stand-in of the right
    TYPE and the widest width that type's allocator produces. That is enough for the two questions
    planning asks (does this binding resolve at all, and does the resulting body fit in one item)
    and it is deliberately not enough to be mistaken for the answer: `execute` builds its own map
    from the ids the parents ACTUALLY got, and it is that map the written item carries.

    A V1 id that TWO records in the plan claim resolves to nothing -- an ambiguous parent is not a
    parent -- and the binding then stands or falls on whether the state already holds an item of
    that name.

    WHAT IT DELIBERATELY OVERRIDES, because the choice is real: when a V1 id also names an item
    that already exists for unrelated reasons, this plan's own record wins. The V1 document meant
    the V1 record, and the V1 record is being imported; an unrelated V2 item that happens to share
    the number is a different thing. The dry run names every binding it rewrote.
    """
    claimed, resolution = {}, {}
    for entry in records:
        if entry.get("verdict") == "already_imported":
            claimed.setdefault(entry["legacy_id"], []).append(entry.get("item_id"))
    for entry, _record, _fields in pending:
        claimed.setdefault(entry["legacy_id"], []).append(format_id(entry["v2_type"], 9999))
    for legacy_id, targets in claimed.items():
        if len(targets) == 1 and targets[0]:
            resolution[legacy_id] = targets[0]
    return resolution


def _unsettled_parents(entry: dict, fields: dict, records: list, resolution: dict) -> list:
    """[(field, legacy id, [(verdict, source), ...])] -- bindings this run HOLDS but cannot resolve.

    THE PROPERTY: a binding value that names a record this run read, that the plan has no id for,
    AND about which the run still owes an answer. The middle clause covers two situations that are
    one fact for the reader -- the parent is not translatable yet (it needs a `--map`, it is
    blocked), or two records claim its id so `_planned_resolution` deliberately resolves it to
    nothing.

    THE LAST CLAUSE IS WHERE THE COUNTER-DEFECT WOULD SIT. `not_an_item` is the one verdict that is
    a FINAL answer about a record: it says this mapping is a cross-reference note or a record of
    some other kind, so it will never be an item and a binding to it really does bind to nothing.
    For those the writer's own message is the true one and this returns nothing, or the report
    would send a reader off to settle a record that has nothing to settle.

    Asked over `PARENT_FIELDS`, the same set `_rebind` rewrites and the kernel checks the binding
    of, so "a field that binds" cannot become three different lists. Returns the parents in field
    order; a value the run holds no record for is NOT in here either, for the same reason.
    """
    held = {}
    for other in records:
        if other.get("verdict") == "not_an_item":
            continue
        held.setdefault(other["legacy_id"], []).append(
            (other.get("verdict", "unclassified"), other["source"]))
    unsettled = []
    for field in PARENT_FIELDS.get(entry["v2_type"], ()):
        value = fields.get(field)
        for one in (value if isinstance(value, (list, tuple)) else [value]):
            name = str(one)
            if name in resolution or name not in held or name == entry["legacy_id"]:
                continue
            unsettled.append((field, name, held[name]))
    return unsettled


def _stolen_bindings(state: ProjectState, entry: dict, bound: dict, resolution: dict) -> list:
    """[(field, value)] -- bindings this run would carry over to an item it did NOT resolve to.

    THE DEFECT, and it is silent in every direction a reader could look. A V1 store names its
    parents by V1 id and V2 REALLOCATES, so `_rebind` replaces every value the run resolved. A
    value it did NOT resolve is left verbatim -- and when the store happens to hold an item of that
    name for unrelated reasons, `_assert_origins_resolve` finds it, accepts it, and the child is
    written bound to a different thing. Nothing reports it afterwards: the reference resolves, so
    `validate` has no finding to make, and the item's own `legacy_fields.record` shows the V1 value
    that "matches".

    HOW IT IS REACHED WITHOUT ANY UNUSUAL DATA: the collision refusal's own printed remedy is to
    take the colliding document out of the state directory. Do that, and the parent is no longer a
    record of the run, so `_unsettled_parents` -- which only speaks about records the run HOLDS --
    goes quiet, and every child of that parent falls straight into this hole.

    THE PROPERTY, and all three clauses are load-bearing: a binding value that (1) still carries
    the V1 ID SHAPE after the rewrite, (2) this plan did not resolve, and (3) NAMES AN ITEM THE
    STORE ALREADY HOLDS. Without the third clause this would swallow the case the writer answers
    correctly -- a value that names nothing at all really is free text, and
    `_assert_origins_resolve`'s own message is the true one about it. Without the first, a value
    that was never V1-shaped would be refused for looking unfamiliar.
    """
    stolen = []
    resolved_to = set(resolution.values())
    for field in PARENT_FIELDS.get(entry["v2_type"], ()):
        if field not in bound:
            continue
        value = bound[field]
        for one in (value if isinstance(value, (list, tuple)) else [value]):
            name = str(one).strip()
            if V1_ID_RE.match(name) and name not in resolved_to and _store_holds(state, name):
                stolen.append((field, name))
    return stolen


def _store_holds(state: ProjectState, name: str) -> bool:
    """Does this state already hold an item under that exact id?

    `exists_anywhere` raises for a name the V2 allocator could never have produced -- a V1 type it
    has no directory for, a number of fewer than four digits -- and such a name cannot be the id of
    a stored item, so the answer is False rather than an exception escaping into the planner.
    """
    try:
        return state.exists_anywhere(name)
    except ValueError:
        return False


def _seen_but_not_an_item(entry: dict, fields: dict, records: list) -> str:
    """An ANNOTATION on the writer's refusal, or "" -- never a replacement for it.

    The writer says "derives_from SR-0096 does not exist", which is true of the V2 state and is
    what a reader has to act on. What it cannot say is that the run READ a record of that name and
    classified it as no item at all -- measured on the field copy of `synaipse` (2026-08-05):
    `SR-0096` sits in `system_requirements.yaml` carrying no `status`, so it is a document entry,
    and a reader following the writer's remedy would go looking for a record that is right there.

    `_unsettled_parents` deliberately stays silent about a `not_an_item` parent, because that
    verdict is FINAL and turning it into "settle that record first" would send a reader after
    something with nothing to settle. This adds the fact without moving the remedy.
    """
    held = {other["legacy_id"]: other["source"] for other in records
            if other.get("verdict") == "not_an_item"}
    seen = []
    for field in PARENT_FIELDS.get(entry["v2_type"], ()):
        value = fields.get(field)
        for one in (value if isinstance(value, (list, tuple)) else [value]):
            if str(one) in held:
                seen.append("`%s` (%s in %s)" % (one, field, held[str(one)]))
    if not seen:
        return ""
    return (". NOTE: this run DID read %s and classified it as no item -- it carries no `status`, "
            "or its type is one no contract knows, so it never becomes an item and nothing here "
            "can make the binding resolve. Remedy: give that record a status in the V1 file if it "
            "really is a backlog record, or point this one somewhere else."
            % "; ".join(sorted(set(seen))))


def _settle_bindings(state: ProjectState, records: list, pending: list) -> None:
    """The second half of planning: bindings, write order, and the two ways it can still fail.

    WHY THIS CANNOT HAPPEN IN THE DOCUMENT LOOP -- the defect it is the correction of. The plan
    asked `capture_preflight` the moment it had a body, i.e. against the state BEFORE the run, and
    a V1 parent chain is the normal shape of every V1 store: measured on an office scaffold with
    `PROC-0001` and `PROC-0002 derives_from PROC-0001`, the dry run reported PROC-0001 importable
    and PROC-0002 blocked, `plan_is_executable` was then False, the run refused wholesale, PROC-0001
    was never written -- and the next dry run said the same thing. A stationary state.

    So the question is asked of the state the run WILL have reached: the ids this plan promises are
    handed to the preflight as existing (`also_existing`), and the writes are ordered so that the
    promise is kept. Both counter-directions stay closed and both are measured rather than argued:
    a binding whose target is NOT in the plan and not in the state is still refused, by the same
    check as before; and a CYCLE (A binds B, B binds A) is refused outright, because "create A
    before B and B before A" is a promise no order keeps.
    """
    resolution = _planned_resolution(records, pending)
    creating = {}
    for entry, _record, _fields in pending:
        creating[entry["legacy_id"]] = entry
    order, depth = {}, {}

    def dependencies(entry, fields):
        """The pending entries this one must be written after."""
        found = []
        for field in PARENT_FIELDS.get(entry["v2_type"], ()):
            value = fields.get(field)
            for one in (value if isinstance(value, (list, tuple)) else [value]):
                parent = creating.get(str(one))
                if parent is not None and str(one) in resolution:
                    # A RECORD THAT NAMES ITSELF IS NOT EXCLUDED HERE, and excluding it was a hole
                    # this fix nearly shipped: it would have settled at depth 1, been promised by
                    # the plan, and then died at write time because its own id does not exist yet.
                    # A self-binding is a cycle of length one and is refused as one.
                    found.append(parent)
        return found

    edges = {id(entry): dependencies(entry, fields) for entry, _record, fields in pending}

    def settle(entry, stack):
        """Depth of this entry in the dependency order, or None when it sits on a cycle."""
        key = id(entry)
        if key in depth:
            return depth[key]
        if key in stack:
            return None
        stack = stack | {key}
        levels = []
        for parent in edges[key]:
            level = settle(parent, stack)
            if level is None:
                return None
            levels.append(level)
        depth[key] = 1 + max(levels, default=0)
        return depth[key]

    for entry, record, fields in pending:
        level = settle(entry, frozenset())
        if level is None:
            entry["verdict"] = "blocked"
            entry["reason"] = (
                "%s and the record(s) it binds to form a cycle: each names the other as its "
                "parent, so no write order creates a parent before its child. Remedy: break the "
                "cycle in the V1 file -- one of the two is not really derived from the other -- "
                "then re-run the dry run." % entry["legacy_id"])
            continue
        order[id(entry)] = level

    also_existing = sorted(set(resolution.values()))
    for entry, record, fields in pending:
        if entry.get("verdict") == "blocked":
            continue
        bound = _rebind(entry["v2_type"], fields, resolution)
        entry["rebound_fields"] = sorted(
            field for field in PARENT_FIELDS.get(entry["v2_type"], ())
            if field in fields and bound[field] != fields[field])
        body = _with_legacy(bound, entry, record)
        # THE ORDER OF THE REFUSALS IS THE ORDER OF THE READER'S WORK: a defect INSIDE the record
        # is named before one that is about another record, so settling a parent can never move a
        # record from one refusal straight into the next.
        # `test_a_record_that_is_both_oversized_and_unsettled_reports_its_own_size` is what holds
        # the order; it, not this comment, is where the field reading behind it is recorded.
        #
        # THE BUDGET IS ASKED ONLY WHERE IT IS ENFORCED, and that clause is DEC-0009 read as it is
        # written. `report.validate_state` walks the ACTIVE items (`_iter_active`) and measures
        # each file against spec II.5; nothing measures a file under `archive/`. So an
        # archive-bound record was held back with a reason that was untrue about this harness, and
        # DEC-0009's answer for that class is the archive rather than a human sent to the business
        # data. An ACTIVE-bound oversized record still blocks, because for it the sentence is true.
        # `test_migrate.test_an_archive_bound_record_is_not_held_back_by_a_budget_nothing_measures`
        # is where the field reading behind this lives and where the second direction is measured
        # by running `validate`; the first is
        # `test_migrate.test_a_record_too_large_for_one_item_blocks_instead_of_being_written`.
        oversized = (None if entry["target"] == "archive"
                     else _too_large(body, entry["v2_type"]))
        unsettled = [] if oversized else _unsettled_parents(entry, fields, records, resolution)
        stolen = ([] if (oversized or unsettled)
                  else _stolen_bindings(state, entry, bound, resolution))
        if oversized:
            entry["verdict"] = "blocked"
            # WHERE THE BULK GOES IS CONSTRUCTED, NOT LEFT TO THE READER (DEC-0024). This line
            # named `staging/` -- a directory, so the reader picked the file name, and a picked
            # name can be taken. `record_deposit_of` is a name no other line of this report can
            # produce. But COPY is not the whole remedy here: the second half SHORTENS the record in
            # the V1 file, so this instruction's source does not stay put the way `_coverage_of`'s
            # does. That is why the name carries `_body_digest(body)` -- a reader who shortens too
            # little and re-runs is handed a DIFFERENT name, so the second copy cannot land on the
            # first and take the moved-out bulk with it (`record_deposit_of` carries the measured
            # chain).
            entry["reason"] = (
                "it does not fit in one item: it %s. An item REFERENCES its detail and this V1 "
                "record inlines it, so the bulk belongs beside the item rather than in it. "
                "Remedy: %s Then shorten the record in the V1 file itself so that it points at "
                "that copy, and re-run the dry run."
                % (oversized, copy_instruction(
                    record_deposit_of(entry["source"], entry["legacy_id"],
                                      _body_digest(body)))))
            continue
        if unsettled:
            # A BINDING TO A RECORD OF THIS RUN IS A PLANNING FACT, NOT A WRITER'S REFUSAL, and
            # letting the writer answer it was measured as an untrue message. `capture_preflight`
            # sees a V1 id -- `PRD-0007` -- and says what is true of it as a V2 value: "is not an
            # item id ... free text there binds to nothing". Measured on the field copy of
            # `portfoliomanaigement` (2026-08-04): 111 of 157 blocked records carried that
            # sentence, and every one of the named parents was a record sitting in
            # `product_requirements.yaml` in the same run, waiting for a `--map`. A reader acting
            # on that message would look for free text that is not there.
            #
            # So the case is decided BEFORE the writer is asked, and only for a value this run
            # actually holds a record for. Anything else still goes to the writer and still gets
            # its message, because then the value really does name nothing.
            entry["verdict"] = "blocked"
            entry["reason"] = (
                "it binds to %s, and %s a record of THIS run rather than free text -- so this "
                "record follows as soon as that one does, and nothing about this record needs "
                "changing. Remedy: settle the record(s) named above (the sections of this report "
                "say what each one still needs), then re-run the dry run."
                % ("; ".join(
                    "`%s` (%s: %s in %s)"
                    % (legacy_id, field, "/".join(sorted({verdict for verdict, _s in held})),
                       ", ".join(sorted({source for _v, source in held})))
                    for field, legacy_id, held in unsettled),
                   "they are" if len(unsettled) > 1 else "it is"))
            continue
        if stolen:
            entry["verdict"] = "blocked"
            entry["reason"] = (
                "its %s still names %s, which this run did not import and did not resolve -- and "
                "an item of that name already exists in this state. Carrying the value over would "
                "bind this record to a DIFFERENT thing that happens to wear the same number: V1 "
                "numbers were typed by hand and V2 numbers are allocated by the kernel, so the two "
                "agreeing is a coincidence and not a reference. Remedy: import the record that "
                "value means (it is named in the sections above if this run read it), or correct "
                "the value in the V1 file, then re-run the dry run."
                % (", ".join(sorted({field for field, _v in stolen})),
                   ", ".join("`%s`" % value for _f, value in stolen)))
            continue
        refused = None
        # THE WRITER'S OWN VERDICT, asked before the plan promises anything, and asked of the
        # SAME method the run will use -- the archive path enforces a different contract
        # (DEC-0004), so asking `capture_preflight` about an archive-bound record would have
        # been a plan measuring something the run does not do.
        try:
            if entry.get("unresolved_fields"):
                state.capture_migrated_unresolved_preflight(
                    entry["v2_type"], body, also_existing)
            elif entry["target"] == "archive":
                state.capture_migrated_archive_preflight(
                    entry["v2_type"], body, entry["legacy_type"], entry["legacy_status"],
                    also_existing)
            else:
                state.capture_preflight(entry["v2_type"], body, also_existing, imported=True)
        except StateError as exc:
            refused = str(exc)
        if refused:
            entry["verdict"] = "blocked"
            entry["reason"] = (
                "the kernel would refuse this item: %s (asked of the same check that writes "
                "it, so the plan cannot promise what the run cannot do)%s"
                % (refused, _seen_but_not_an_item(entry, fields, records)))
        else:
            entry["verdict"] = "unresolved" if entry.get("unresolved_fields") else "translatable"
            entry["write_order"] = order[id(entry)]


def state_fingerprint(state: ProjectState):
    """([(path, sha256)], [(path, why it is missing from them)]) -- what the digest covers.

    WHAT IT COVERS AND WHAT IT DOES NOT, because the sentence this replaces said "any file under
    the state directory" and that was measured false: the fingerprint used to be the DOCUMENT
    inventory, so a hand-edited `procedures/active/PROC-0001.yaml` left the digest unchanged and
    the run went through on a plan that had never seen it.

    The rule is the dotted-segment one `layout.is_project_document` already uses, and for the same
    reason: everything under the state root EXCEPT paths with a dotted segment. So kit documents,
    every kernel-written item, `generated/` and `staging/` are all in. The exclusion is machinery
    -- the lock and `.audit/hook_events.jsonl`, which grows whenever any gate refuses anything;
    including it would invalidate a plan because an unrelated hook fired between the reading and
    the run, which is a refusal a person cannot act on. THE RESIDUAL, stated rather than implied: a
    file placed under a dotted directory of somebody's own making is invisible here.

    A FILE NOBODY COULD OPEN IS NOT IN THE ROWS EITHER, so it is REPORTED instead of being dropped
    -- a digest short one file is a statement about a state nobody saw, and the second return value
    is what makes `build_plan` refuse rather than present it. Before this it was a `PermissionError`
    out of the walk; the measurement is at `_read_bytes`.
    """
    seen, unreadable = [], []
    for dirpath, dirs, files in os.walk(state.root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if name.startswith("."):
                continue
            rel = _relative(state, os.path.join(dirpath, name))
            raw, problem = _read_bytes(state, rel)
            if problem is not None:
                unreadable.append((
                    rel,
                    "%s -- the digest a dry run presents is taken over every file under the "
                    "state root, so one nobody can open would make it a statement about a state "
                    "nobody read" % problem))
                continue
            seen.append([rel, hashlib.sha256(raw).hexdigest()])
    return sorted(seen), sorted(unreadable)


def plan_digest(plan: dict) -> str:
    """The fingerprint the executing run must be handed back.

    Over the WHOLE plan, which is what makes it a statement about the state rather than about the
    records: `state_fingerprint` is in there, so editing anything the fingerprint covers --
    including a file this command would never translate -- invalidates a plan that was presented
    before the edit, and so does changing the `--map` flags. That is deliberate. A migration
    reviewed against one state and run against another is the failure this digest exists for, and
    being too strict costs one more dry run. What the fingerprint does NOT cover is named where it
    is built, not here.
    """
    return hashlib.sha256(canonical_json(plan).encode("utf-8")).hexdigest()


def _by_verdict(plan: dict, verdict: str) -> list:
    return [entry for entry in plan["records"] if entry["verdict"] == verdict]


# The verdicts under which a record BECOMES AN ITEM in this run. `translatable` is the ordinary
# import (active/ or the finished-record archive); `unresolved` is DEC-0009's second archive door.
# Named once because four readers ask it -- the write loop, the receipt, SR-0005's absorption rule
# and the dry run -- and a fifth spelling of the same set is how one of them comes to disagree.
_IMPORTING_VERDICTS = ("translatable", "unresolved")


def _importable(plan: dict) -> list:
    return [entry for entry in plan["records"] if entry["verdict"] in _IMPORTING_VERDICTS]


def _unreadable_paths(plan: dict) -> set:
    """The distinct paths the plan's `unreadable` list is about -- what a COUNT of it may say.

    ONE PATH CAN BE IN THAT LIST TWICE and the two entries are not duplicates: a denied document is
    reported once by the inventory (no hash for the receipt) and once by the fingerprint (the
    digest is short a file), and both are true. So a refusal that counts "documents" counts the
    paths, not the entries.

    THE PATH IS CARRIED, NOT RECOVERED FROM THE SENTENCE. It used to be `line.split(" ")[0]`,
    resting on "a line BEGINS with its path" -- which is true of every producer and still does not
    say where the path ENDS. Measured 2026-08-09 with two denied documents named `my
    procedures.yaml` and `my other procedures.yaml`: four true lines, `_unreadable_paths` answered
    `{'my'}` -- a path this state does not have -- and `execute` refused with "1 path(s) unreadable"
    for two files. That is the same defect as the count-the-lines one this replaced, one spelling
    further on and in the UNDER-counting direction, so the plan now carries the pair the way
    `unlistable_notes` already does and the formatting happens where it is printed.
    """
    return {path for path, _why in plan["unreadable"]}


def plan_is_executable(plan: dict) -> bool:
    """Would `migrate` run this plan, or does something still need a human?

    FOUR THINGS STOP IT AND `unresolved` IS NOT ONE OF THEM (DEC-0009): a record nobody can
    translate is archived with its reason, so it is an outcome rather than an obstacle. What
    remains is what no run can proceed past -- a `blocked` record (it cannot be written at all: it
    does not fit in one item, its year is unknown, its id is claimed twice, or the harness has no
    row for it), a `needs_decision` record (a suggestion is on the table and SR-0007 says a
    suggestion is not an answer), a document that does not parse, and a document whose landing
    place under `legacy/` is already taken (`occupied_landings`: the move is an `os.replace`, which
    overwrites without saying so, and what stands there is what an earlier run's receipt carries
    the hash of).

    EVERY ONE OF THEM IS READ AS A REQUIRED KEY. A plan that does not carry one is a plan `build_plan`
    did not make, and answering "nothing known, so go ahead" for it is how a condition comes to be
    switched off by an incomplete caller rather than by a decision.
    """
    return not (_by_verdict(plan, "blocked") or _by_verdict(plan, "needs_decision")
                or plan["unreadable"] or plan["occupied_landings"])


# -- the dry run's text --------------------------------------------------------------------------

def _group_decisions(entries) -> dict:
    """{what the answer depends on: [entry, ...]} -- see the caller for why this is grouped."""
    grouped = {}
    for entry in entries:
        key = (entry["source"], entry["v2_type"], tuple(entry["missing_fields"]),
               tuple(entry["record_keys"]))
        grouped.setdefault(key, []).append(entry)
    return grouped


def _group_unresolved(entries) -> dict:
    """{what a human would have to do about it: [entry, ...]} -- grouped for the same reason.

    The key carries the V1 STATUS as well, which the decision key does not: an unresolved record
    is going into the archive, and whether the thing being archived was live or finished is the
    first question a reader has about it.
    """
    grouped = {}
    for entry in entries:
        key = (entry["source"], entry["v2_type"], entry["legacy_status"],
               tuple(entry["unresolved_fields"]), tuple(entry["record_keys"]))
        grouped.setdefault(key, []).append(entry)
    return grouped


def _named_ids(group) -> list:
    """The legacy ids of a grouped section, EVERY one of them, as indented wrapped lines.

    THE SECTIONS THIS SERVES ARE THE ANSWER TO "which records need a human", so a reader has to
    come out of them holding the records rather than a range. They printed `first .. last (n)`,
    which names two ids per group and leaves the rest unsayable -- the spans were not sorted
    either, so nothing about them could be inferred. Sorted and complete is what makes the list
    usable and what makes two runs comparable. The field reading behind that is recorded in
    `test_migrate.test_every_record_that_needs_a_human_is_named_and_not_spanned`.

    Wrapped rather than printed on one line, because the bound here is the number of records a
    project has, which is no bound at all.
    """
    ids = sorted(entry["legacy_id"] for entry in group)
    return ["    " + line for line in textwrap.wrap(", ".join(ids), width=94)]


def _map_flags(plan: dict) -> list:
    """The `--map` flags this state still needs, deduplicated, in command-line order.

    A field this harness has a SUGGESTION for is printed as the flag it would be rather than as a
    placeholder, so confirming the run is a paste and not a transcription (SR-0007). A field with
    no suggestion keeps its placeholder, because the alternative is a flag that looks answered.
    """
    wanted = {}
    for entry in _by_verdict(plan, "needs_decision"):
        for field in entry["missing_fields"]:
            suggested = (entry.get("suggested_fields") or {}).get(field)
            wanted.setdefault((entry["v2_type"], field), suggested[0] if suggested else None)
    return ["--map %s.%s=%s" % (pair[0], pair[1], value or "<v1_field>")
            for pair, value in sorted(wanted.items())]


def _suggestion_lines(plan: dict) -> list:
    """One line per DISTINCT suggestion, with the reason the row carries."""
    seen = {}
    for entry in _by_verdict(plan, "needs_decision"):
        for field, (v1_field, why) in sorted((entry.get("suggested_fields") or {}).items()):
            seen.setdefault((entry["v2_type"], field, v1_field, why), []).append(entry)
    lines = []
    for (v2_type, field, v1_field, why), group in sorted(seen.items()):
        lines.append("  --map %s.%s=%s  (%d record(s)) -- %s"
                     % (v2_type, field, v1_field, len(group), why))
    return lines


def _plan_flags(plan: dict) -> list:
    """The BUILD flags this plan carries, in command-line order -- what a re-run must repeat.

    NOT `_map_flags`. That one prints the `--map` a record STILL needs (a decision the reader has
    yet to make); this prints the flags the plan was ALREADY built with, which are two of the plan's
    own inputs. `build_plan` takes `field_map` and `archive_year`, and `plan_digest` covers the
    whole plan, so a `migrate --plan <digest>` that drops either flag digests to a different value
    and the run refuses it as a usage error (measured rc 2, no state touched). Read from the plan
    itself -- `field_map` and `archive_year` -- rather than from the command line, so the READY line
    the dry run prints and the plan the digest is taken over can never name different flags.
    """
    flags = ["--map %s=%s" % (key, value)
             for key, value in sorted((plan.get("field_map") or {}).items())]
    if plan.get("archive_year"):
        flags.append("--archive-year %d" % plan["archive_year"])
    return flags


def _ready_command(plan: dict) -> str:
    """The command a reader pastes to execute this exact plan -- digest AND the flags that built it.

    The digest alone was wrong the moment any flag was in play (BUG-0027): the copied line digests
    to a plan with no flags, which is not the plan that was reviewed.
    """
    return " ".join(["python scripts/harness.py migrate --plan %s" % plan_digest(plan)]
                    + _plan_flags(plan))


def root_item_warnings(plan: dict, written: bool = False) -> list:
    """The "this project keeps no root item" warning, for BOTH halves of the command.

    IT SAYS THE CONSEQUENCE AND NOT ONLY THE STATE. The first version named the state ("the project
    answers the setup-phase predicate the way one before its first requirement does") and left the
    reader to work out what follows from it; what follows is that the gates built on that predicate
    stop applying, and two of them are the ones in front of a merge and a push.
    `test_migrate.test_a_project_left_without_a_root_item_really_does_open_the_merge_gate` is where
    that sentence is measured, against the shipped `gate_git.py` as a process.

    AND IT IS PRINTED WHERE IT IS WRITTEN, TOO. It used to appear in the dry run only, so the run
    that actually produced the state said nothing about it -- and a person who runs `--plan` from a
    scrollback, or from a script, never sees it. `written` only moves the tense; what is said is
    one text, because two texts is how the two halves come to say different things.
    """
    lines = []
    for root_type, (live, archiving) in sorted(plan.get("root_items_after", {}).items()):
        if not archiving or live:
            continue
        lines += ["", "%s THIS PROJECT HOLDS NO ACTIVE %s ITEM: all %d of them %s into the "
                      "archive. WHAT THAT COSTS is not only bookkeeping -- a kit's setup-phase "
                      "predicate (`hooks/_root.py`, `has_root_item`) reads whether an active %s "
                      "file exists, and a gate that asks it DOES NOT APPLY while the answer is no. "
                      "In the dev and research kits the gate in front of `git merge` and `git "
                      "push` is one of those, so neither is refused by it until this project holds "
                      "a root item again. Nothing here refuses that -- it is DEC-0009's decision "
                      "-- and no kernel operation moves an item back out of the archive."
                  % ("THIS RUN IS DONE AND" if written else "AFTER THIS RUN",
                     root_type, archiving, "went" if written else "go", root_type)]
    return lines


def render(plan: dict, state: ProjectState = None) -> str:
    """The dry run, in the three parts the command promises: found, becomes, cannot.

    WHICH DOCUMENTS ARE WALLS is `plan["gated_documents"]` and no longer a second reading taken
    here: the plan already had to know, because the same answer decides which documents may be
    moved to `legacy/`. `state` stays optional and buys only the top-level KEYS of each wall, which
    need the file; without it the walls are named without them rather than guessed at.
    """
    lines = ["MIGRATION DRY RUN -- nothing was written.",
             "plan digest: %s" % plan_digest(plan), ""]

    translatable = _by_verdict(plan, "translatable")
    lines.append("WHAT IT WOULD IMPORT (%d record(s)):" % len(translatable))
    for entry in translatable:
        if entry["target"] == "archive":
            # A DIFFERENT SENTENCE BECAUSE IT IS A DIFFERENT WRITE, and the two things a reader
            # must be able to object to are both in it: the YEAR and where that year came from.
            lines.append(
                "  %-18s %s -> %s at %s (finished in V1: %r). The year comes from "
                "%s. Spec II.2's field contract does not apply to it (DEC-0004); the item names "
                "every required field it lacks."
                % (entry["source"], entry["legacy_id"],
                   archive_location(entry["v2_type"], entry["archive_year"]),
                   entry["mapped_status"], entry["legacy_status"],
                   entry["archive_year_from"]))
        else:
            lines.append(
                "  %-18s %s -> a new %s item at its initial status (V1 %r would mean %s; that "
                "value is kept in `%s`, not walked)"
                % (entry["source"], entry["legacy_id"], entry["v2_type"], entry["legacy_status"],
                   entry["mapped_status"], LEGACY_FIELD))
        if entry.get("rebound_fields"):
            # NAMED, never silent: the value in the V1 file is not the value the item gets, and a
            # reader who is not told that would check the wrong id.
            lines.append(
                "  %-18s   ...its %s point(s) at a record THIS RUN creates, so the written item "
                "carries the id that record actually gets -- not the V1 one."
                % ("", ", ".join(entry["rebound_fields"])))
    if translatable:
        lines.append("  ...each with `%s: true` and `approval_ref: null` (spec II.10): the import "
                     "creates NO approval, and no gate that requires one opens because of it."
                     % IMPORT_MARK)
    else:
        lines.append("  (none)")

    # THE VALUES A `--map` WOULD ACTUALLY CARRY, and this section exists because of a shape this
    # command does not convert: `--map PROC.roles=owner` puts a V1 SCALAR into a V2 field whose
    # name is plural. The contract of the types THIS COMMAND CREATES names fields and not their
    # shapes: `_item_fields` copies whatever `REQUIRED_FIELDS`/`OPTIONAL_FIELDS` list, and those
    # tuples are field NAMES. The other half of the kernel's field contract does declare shapes --
    # `kernel/schemas/arc_companion.yaml` gives `derives_from` `type: list` with an `item_type`,
    # and `schemas.item_field_contracts` calls it a field contract in those words -- but that half
    # covers ARC/WFR/DSN, which `staging.freeze_*` promotes and no import ever creates. So there
    # is nothing HERE to convert against; there is elsewhere, for types this command cannot reach.
    #
    # WHAT IS NOT TRUE IS THAT NOBODY WROTE THE SHAPE DOWN, which is what this comment claimed
    # until BUG-0015. A kit's READER is a shape contract of its own: the office kit renders
    # `roles` into the Steuerberatung's Verfahrensdokumentation, and it iterated the scalar --
    # `records-clerk` reached that document as `r, e, c, o, r, d, s, -, c, l, e, r, k`. The
    # normalisation belongs at the reader, because `kernel.capture` accepts the same scalar and
    # this command is not on that path at all: it is `backlog_types.field_elements`, which the
    # office renderer now asks instead of iterating the value
    # (`test_hooks.test_process_doc_renders_a_scalar_field_as_one_element`).
    # WHICH OTHER READERS ASSUME A SHAPE is a per-reader question; the sweep BUG-0015 asked for
    # named the ones it could reach, and no claim beyond those is made here.
    #
    # What this section does is show the human every distinct value the mapping would carry,
    # before it carries it. Distinct values, so the section is bounded by the VARIETY of the data
    # rather than by its size.
    if plan["carried_values"]:
        lines += ["", "FIELD MAPPING IN EFFECT -- values carried VERBATIM, in the shape the V1 "
                      "record holds them (nothing here converts a scalar into a list):"]
        for pair in sorted(plan["carried_values"]):
            lines.append("  %-30s %s" % (pair, ", ".join(plan["carried_values"][pair])))
    already = _by_verdict(plan, "already_imported")
    if already:
        lines.append("")
        lines.append("ALREADY IMPORTED (%d) -- a re-run leaves these alone:" % len(already))
        for entry in already:
            lines.append("  %-18s %s -> %s" % (entry["source"], entry["legacy_id"],
                                               entry["item_id"]))

    decisions = _by_verdict(plan, "needs_decision")
    lines += ["", "WHAT IT CANNOT DECIDE (%d record(s)) -- a field carries over only when both "
                  "contracts spell it the same:" % len(decisions)]
    # ONE LINE PER DECISION, not per record. Records that differ in no way the decision depends on
    # -- same source, same target type, same missing fields, same available keys -- pose ONE
    # question, and printing it once per record turns a sixteen-record import into sixteen
    # identical lines and a nine-hundred-record one into a wall nobody reads. The grouping key is
    # exactly what the answer depends on, so two records that would need DIFFERENT answers can
    # never collapse into one line.
    for _key, group in sorted(_group_decisions(decisions).items()):
        first = group[0]
        lines.append(
            "  %-18s %d record(s) (%s): missing %s; the record carries %s"
            % (first["source"], len(group), first["v2_type"],
               ", ".join(first["missing_fields"]), ", ".join(first["record_keys"])))
        lines += _named_ids(group)
    if decisions:
        suggestions = _suggestion_lines(plan)
        if suggestions:
            # SR-0007: a proposal with its reason, and the boundary stated where the reason is --
            # the run does NOT act on it. Everything below is what the human would be pasting.
            lines.append("  SUGGESTED, from what the kit's own V1 template documents -- NOT "
                         "applied: the run stays unexecutable until you type these back.")
            lines += suggestions
        lines.append("  Remedy: decide each one and say so on the line --")
        lines.append("    python scripts/harness.py migrate --plan <digest> %s"
                     % " ".join(_map_flags(plan)))
        lines.append("  The digest changes when you change the state, so re-run --dry-run after "
                     "any edit and take the digest it prints.")
    else:
        lines.append("  (none)")

    unresolved = _by_verdict(plan, "unresolved")
    if unresolved:
        lines += ["", "WOULD BE ARCHIVED AS UNRESOLVED (%d record(s)) -- DEC-0009: V1 collected "
                      "nothing for these required fields, so the record is archived with that "
                      "reason instead of stopping the run. THESE ARE THE RECORDS THAT NEED A "
                      "HUMAN if you want them as live items:" % len(unresolved)]
        for _key, group in sorted(_group_unresolved(unresolved).items()):
            first = group[0]
            lines.append(
                "  %-18s %d record(s) (%s, V1 %s): no source for %s; the record carries %s"
                % (first["source"], len(group), first["v2_type"], first["legacy_status"],
                   ", ".join(first["unresolved_fields"]), ", ".join(first["record_keys"])))
            lines += _named_ids(group)
        lines.append("  Remedy, per record: add the field in the V1 file, or name the V1 field it "
                     "comes from with `--map`. Doing nothing archives it -- and this kernel has "
                     "no operation that brings an item back out of the archive.")

    lines += root_item_warnings(plan)

    blocked = _by_verdict(plan, "blocked")
    if blocked:
        lines += ["", "BLOCKED (%d) -- the run refuses while any of these stands:" % len(blocked)]
        for entry in blocked:
            lines.append("  %-18s %s: %s" % (entry["source"], entry["legacy_id"], entry["reason"]))
    for path, problem in plan["unreadable"]:
        lines += ["", "UNREADABLE (the run refuses): %s %s" % (path, problem)]
    for note in plan["unscanned"]:
        lines += ["", "NOT SEARCHED: %s" % note]
    # THE DEPOSIT COPIES, COUNTED IN ONE LINE (BUG-0028). One is created per remedy a reader applies,
    # so a line each grew the report every time the project followed it; they need no action, so the
    # count is what a reader wants and the paths follow it once rather than as N headings.
    deposits = plan.get("deposits") or []
    if deposits:
        lines += ["", "DEPOSIT COPIES (%d) -- copies this command's own remedies told a reader to "
                      "make; not searched as V1 sources and nothing here acts on them: %s"
                  % (len(deposits), ", ".join(deposits))]

    not_items = _by_verdict(plan, "not_an_item")
    if not_items:
        lines += ["", "ID-SHAPED BUT NOT ITEMS (%d) -- read, not imported, not a blocker:"
                  % len(not_items)]
        for entry in not_items:
            lines.append("  %-18s %s: %s" % (entry["source"], entry["legacy_id"], entry["reason"]))

    absorbed = absorbed_documents(plan)
    occupied = {rel: (landing, digest) for rel, landing, digest in plan["occupied_landings"]}
    if absorbed:
        lines += ["", "WOULD MOVE TO legacy/ (%d document(s)) -- SR-0005: every record of these "
                      "became an item, so leaving them here would be the same thing twice in one "
                      "project. The run's Decision item records each with its pre-move hash, and "
                      "`legacy/` is a kernel-written area, so a later run does not read it as a V1 "
                      "source and no tool write reaches it:" % len(absorbed)]
        for path in absorbed:
            lines.append("  %-28s -> %s%s"
                         % (path, legacy_location(path),
                            "   ALREADY TAKEN" if path in occupied else ""))
    if occupied:
        # SR-0001's rule that the dry run reports in advance what the run refuses on, for the one
        # condition that is not about a record: `os.replace` overwrites silently, and what stands
        # there is what an earlier run's receipt carries the hash of.
        lines += ["", "LANDING PLACE UNDER legacy/ ALREADY TAKEN (%d document(s)) -- the run "
                      "refuses while any of these stands, because the move would replace the file "
                      "that is there without saying so, and an earlier run's Decision item names "
                      "its hash:" % len(occupied)]
        for path in sorted(occupied):
            landing, digest = occupied[path]
            # "TAKEN", not "a file": `_is_occupied` asks `lexists`, so a directory and a
            # dangling link count too, and the branch below exists because one of them is
            # what the run may be looking at.
            lines.append("  %-28s -> %s is already taken" % (path, landing))
            # THE PLACE IS NAMED AND IT LIES OUTSIDE THE STATE DIRECTORY (DEC-0024, and the user's
            # decision of 2026-08-09 on `L35`). Until round 9 this said "take the file out of the
            # state directory, where it goes is yours to choose" -- no destination, and the source
            # gone: what the reader carries off is a file an earlier run put there and whose only
            # other trace is the hash in that run's Decision item. Two steps replace it, and the
            # order is what makes them safe: the COPY first, under a name that can only ever be
            # taken by a copy of the SAME BYTES (`overflow_deposit_of`), and the removal only
            # afterwards.
            if digest:
                lines.append("     Remedy: %s Then, and only once that copy exists, remove %s "
                             "itself from a shell outside the session -- the copy is what keeps "
                             "the file, and removing the original is what frees the place."
                             % (copy_instruction(overflow_deposit_of(landing, digest)), landing))
            else:
                # NO CAUSE IS NAMED HERE, because this branch cannot tell them apart and a remedy
                # that guesses one sends the reader after the wrong thing: what stands there may be
                # unreadable to this session, or it may be a directory or a dangling link, which is
                # a thing `_is_occupied` counts on purpose.
                lines.append("     Remedy: this run could not read %s as a file, and the name of a "
                             "copy is built from that file's own content -- so it can name no "
                             "place for it. Re-run the dry run once this run can read it."
                             % landing)

    still_holding = _documents_still_holding_records(plan)
    if still_holding:
        # SR-0001, REPORTED IN ADVANCE: the same condition `validate` enforces afterwards, asked of
        # the plan. A dry run that said READY while a document would keep V1 backlog records is a
        # dry run that promises a state the validator refuses.
        lines += ["", "WOULD STILL HOLD V1 BACKLOG RECORDS AFTER THE RUN (%d document(s)) -- "
                      "SR-0001's completion criterion, and `validate` reports each of them as an "
                      "error until it is cleared:" % len(still_holding)]
        for path in sorted(still_holding):
            lines.append("  %-28s %d record(s) stay in the file" % (path, still_holding[path]))

    retired = set(absorbed)
    carried = [doc for doc in plan["documents"]
               if doc["path"] not in {entry["source"] for entry in plan["records"]}
               and doc["path"] not in retired]
    lines += ["", "CARRIED, NOT TRANSLATED (%d document(s)) -- left exactly where they are, "
                  "unrenamed and unedited; the run's Decision item records each with this hash:"
              % len(carried)]
    for doc in carried:
        lines.append("  %-28s %8d B  %s" % (doc["path"], doc["bytes"], doc["sha256"][:16]))
    lines.append("  No kernel command writes any of these, before or after the migration "
                 "(`gate_write_scope` refuses a tool write to them for that reason). Nothing here "
                 "blocks writes to them either -- spec II.10 asks for a fail-closed integrity "
                 "guard over retained V1 files and this command does not build one.")

    walls = plan.get("gated_documents") or {}
    if walls:
        lines += ["", "WALLS (%d) -- a registered gate reads these and can refuse work over their "
                      "CONTENT:" % len(walls)]
        for path in sorted(walls):
            # THE REASON IS NOT DISCARDED HERE, and it was: a wall that does not parse and a wall
            # with no keys both printed `-`, which is the reader's-eye version of the silence this
            # whole command is built against -- and this is the one place a wall's own bytes are
            # read, so nothing else would have said it. A wall is not searched for records (it is
            # never moved and never imported), so its state reaches no other heading of this run.
            #
            # AND A WALL THAT IS NOT A YAML DOCUMENT IS NOT A WALL THAT FAILED TO PARSE. Two of the
            # three walls every kit ships are PROSE -- `product/masterplan.md` is the one a user
            # fills -- and handing prose to `yaml.safe_load` produced `NOT READ: could not be read
            # (ScannerError: ...)` for a file that is exactly as it should be. An alarm about a
            # healthy shipped file is the same defect as silence about a broken one, from the other
            # side. `_is_yaml_document` is the same predicate the run-up uses, so what this command
            # parses and what it reports as unparsable are one answer.
            said = "top-level keys: -"
            if not _is_yaml_document(path):
                said = "prose or configuration; not a YAML document, so it has no top-level keys"
            elif state is not None:
                payload, problem = _read_document(state, path)
                if problem:
                    said = "NOT READ: %s" % problem
                elif isinstance(payload, dict):
                    said = "top-level keys: %s" % (", ".join(sorted(str(k) for k in payload)) or "-")
            lines.append("  %-28s %-24s %s" % (path, walls[path]["hook"], said))
        lines.append("  This command does not rewrite a wall and does not MOVE one: its content is "
                     "prose or configuration a kit ships and a USER fills, in an editor outside "
                     "the session, and taking it to legacy/ would leave its gate reading an absent "
                     "file. Whether a wall is currently UNFILLED is its own gate's verdict -- "
                     "`python scripts/harness.py doctor` and the SessionStart briefing report "
                     "it, and this command does not re-derive it.")

    lines += ["", ("READY: `%s`" % _ready_command(plan))
              if plan_is_executable(plan) and _importable(plan)
              else ("NOTHING TO DO: no record in this state becomes an item."
                    if plan_is_executable(plan) else
                    "NOT EXECUTABLE YET: settle the sections above, then run --dry-run again.")]
    return "\n".join(lines)


def _documents_still_holding_records(plan: dict) -> dict:
    """{document: how many V1 BACKLOG records it would still hold after this run}.

    THE SAME PREDICATE `validate` ENFORCES, asked of the plan instead of the disk -- SR-0001's
    "der Trockenlauf meldet dieselbe Bedingung vorab".

    IMPORTING A RECORD DOES NOT REMOVE IT FROM ITS V1 FILE, and that is the whole reason this
    counts what it counts: the only thing that takes a V1 record out of the working tree is the
    document MOVE (SR-0005). So a document this run absorbs is not in here, and every other
    document is in here with ALL of its backlog records -- the imported ones included, because
    after the run they are the second copy SR-0001 exists to forbid. A `not_an_item` record is not
    a backlog record and `report.validate_state` does not flag it, by the same rule both ends read.
    """
    retired = set(absorbed_documents(plan))
    still = {}
    for entry in plan["records"]:
        if entry["source"] in retired or entry["verdict"] == "not_an_item":
            continue
        still[entry["source"]] = still.get(entry["source"], 0) + 1
    return still


# -- execution -----------------------------------------------------------------------------------


def _receipt_fields(plan: dict, created: list, digest: str, interrupted: str = None,
                    moved: list = None) -> dict:
    """The run's Decision item, in a form that fits inside spec II.5's per-item budget.

    TWO PARTS OF IT GROW WITH THE NUMBER OF DOCUMENTS -- the per-document inventory in `context`
    and the carried-not-translated list in `consequences` -- and the first cut shortened only the
    first. Measured with 310 carried documents: the receipt came to 21 316 B, `validate` exit 1,
    and `consequences` alone was 20 070 characters. The docstring claimed the protection the code
    did not build, in the item whose job is to be the honest record of the run.

    THAT FIX WAS ITSELF SHORT BY ONE FIELD, which is why this is now a loop over a LIST rather than
    two hand-paired strings and one `if`. `decision` carries one line per SOURCE DOCUMENT and had
    no short form at all: measured on an office scaffold with 300 translatable V1 files, the
    receipt came to 17 285 B / 204 lines and `validate` exited 1 -- the fallback fired and did not
    help, because the part that had grown was the part with no short form. The rule is now the one
    property rather than three cases: every part that grows with the INPUT has both forms, and the
    forms are swapped in one at a time, re-measuring the whole item after each swap, until
    `_too_large` says None.

    AND SHORT BY ONE PART AGAIN: `interrupted` is the message of whatever killed a partial run, so
    its length is the failing library's business and not this module's -- an `OSError` carrying a
    path per item is enough on its own. It is the last step of the loop rather than the first,
    because it is the only part that says the state is HALF WRITTEN, and that sentence should
    survive longer than the per-source breakdown does. What its short form drops is the failure
    TEXT; the refusal `execute` raises carries that text verbatim to the command line.

    WHAT IS LEFT WHEN EVERY SHORT FORM IS IN, stated because the previous version of this sentence
    was the untrue one: `title`, `source` and the short bodies are fixed sentences plus counts and
    one digest, so the floor is a constant -- except for the `--map` echo, whose size is the
    command line the human typed. A person who types more `--map` bytes than an item may hold
    still gets a receipt that does not fit, and nothing here shrinks that: it is their own input
    read back, and dropping it would make the receipt silent about what the run was told to do.

    NO SHORT FORM POINTS AT SOMETHING THAT IS NOT THERE, which is the failure mode of every one of
    these fallbacks and which each of them has had: a sentence saying "above" while `context` is
    the short one, and a sentence sending the reader to `generated/index.yaml` for the per-item
    breakdown when the index is regenerated from the ACTIVE items only and an archived import is
    in none of it. What every dropped list is still recoverable from is the plan digest in
    `source`, which is taken over all of it, plus a dry run over the same untouched state.
    """
    per_source = {}
    for entry, item_id in created:
        bucket = per_source.setdefault(entry["source"], [])
        bucket.append(item_id)
    moved = list(moved or [])
    # A MOVED DOCUMENT IS NOT A CARRIED ONE: "carried" means left exactly where it was, and this
    # list is what the receipt promises about the files still in the project.
    retired = {doc["path"] for doc in moved}
    carried = [doc["path"] for doc in plan["documents"]
               if doc["path"] not in set(per_source) and doc["path"] not in retired]

    long_context = "\n".join(
        ["read %d document(s) under the state directory:" % len(plan["documents"])]
        + ["  %s (%d B, sha256 %s)" % (doc["path"], doc["bytes"], doc["sha256"])
           for doc in plan["documents"]])
    short_context = (
        "read %d document(s) under the state directory; the per-document inventory with its "
        "content hashes does not fit in one item (spec II.5) and is NOT written here. The plan "
        "digest in `source` is taken over all of them, and `python scripts/harness.py migrate "
        "--dry-run` prints them in full for as long as the state is unchanged."
        % len(plan["documents"]))

    unresolved = [item_id for entry, item_id in created if entry.get("unresolved_fields")]
    archived = [item_id for entry, item_id in created
                if entry.get("target") == "archive" and not entry.get("unresolved_fields")]
    head = ("imported %d V1 record(s) -- %d into active/ at their V2 initial status, %d finished "
            "in V1 straight into archive/<TYPE>/<year>/ at their mapped status (SR-0004/DEC-0004) "
            "and %d into the same archive at their INITIAL status because no answer could fill "
            "their required fields (DEC-0009; each says which under `%s.unresolved`). Every "
            "archived item names its own gaps under `%s.missing_required_fields`, and every "
            "imported item carries `%s: true`, `approval_ref: null` and its whole V1 record "
            "under `%s`"
            % (len(created), len(created) - len(archived) - len(unresolved), len(archived),
               len(unresolved), LEGACY_FIELD, LEGACY_FIELD, IMPORT_MARK, LEGACY_FIELD))
    flags = ("field mapping supplied on the command line: %s"
             % (", ".join("%s=%s" % pair for pair in sorted(plan["field_map"].items())) or "none"))
    # NO "above" AND NO PATH IN HERE: this sentence survives into shapes where the per-source
    # breakdown has been dropped, and the refusal `execute` raises is what names the ids.
    half_written = ("The %d item(s) this run created are in the state and were not rolled back; a "
                    "re-run skips them by their legacy id." % len(created))
    long_tail = ([] if not interrupted else
                 ["THE RUN DID NOT FINISH: %s. %s" % (interrupted, half_written)])
    short_tail = ([] if not interrupted else
                  ["THE RUN DID NOT FINISH. What stopped it does not fit in one item (spec II.5) "
                   "and is NOT written here; the refusal the command raised carries it. %s"
                   % half_written])

    long_breakdown = (
        [head + ":"]
        + ["  %s -> %d item(s): %s .. %s"
           % (source, len(per_source[source]), sorted(per_source[source])[0],
              sorted(per_source[source])[-1]) for source in sorted(per_source)])
    short_breakdown = [
        head + ", out of %d source document(s). The per-source breakdown does not fit in one item "
               "(spec II.5) and is NOT written here; each imported item names its own source in "
               "`%s.legacy_source`." % (len(per_source), LEGACY_FIELD)]

    def decision_with(breakdown, tail):
        return "\n".join(breakdown + [flags] + tail)

    def consequences_with(carried_line, moved_line):
        return "\n".join([
            "imported items are NOT approved: the import mints no APR and no gate that requires "
            "one opens because of it. Each needs `python scripts/harness.py request-approval "
            "scope <ID>` and a user answer.",
            "the V1 sources that were NOT fully absorbed are untouched and stay readable; nothing "
            "in this harness blocks a later write to them.",
            moved_line,
            carried_line,
        ])

    # THE MOVE IS THE ONE THING THIS RUN DID TO A SOURCE FILE (SR-0005), so the receipt carries
    # each moved document's pre-move hash: that is what makes the copy under `legacy/` checkable
    # against what the migration actually read.
    long_moved = ("fully absorbed and moved to legacy/ (every record of them became an item): %s"
                  % ("; ".join("%s -> %s (%d B, sha256 %s)"
                               % (doc["path"], doc["moved_to"], doc["bytes"], doc["sha256"])
                               for doc in moved) or "none"))
    short_moved = ("%d document(s) were fully absorbed and moved to legacy/. Neither their paths "
                   "nor their pre-move hashes fit in one item (spec II.5); the plan digest in "
                   "`source` covers what was read, and `legacy/` holds the files themselves."
                   % len(moved))

    # The SHORT form does not say "hash recorded above": once `context` is the short one, no hash
    # is recorded above, and a sentence pointing at a list that is not there is the defect this
    # whole function is a correction of, one sentence further on.
    long_consequences = consequences_with(
        "carried, not translated (left in place, hashes in `context` above): %s"
        % (", ".join(carried) or "none"), long_moved)
    short_consequences = consequences_with(
        "%d document(s) were carried, not translated -- left in place, unrenamed and unedited. "
        "Neither their paths nor their hashes fit in one item (spec II.5); the plan digest in "
        "`source` covers them and the dry run lists them." % len(carried), short_moved)

    fields = {"title": "V1 import: %d record(s) into the V2 item store" % len(created),
              "context": long_context,
              "decision": decision_with(long_breakdown, long_tail),
              "consequences": long_consequences,
              "source": "spec II.10; plan digest %s" % digest,
              # The receipt records what a run DID and decides nothing anybody has to build, so
              # it is the one decision the kernel may answer DEC-0083's carrier question for
              # itself (`work: none`, the only silence the validator accepts). Written HERE and
              # not at the capture door, which the importer never passes (DEC-0021 refused a
              # reader of the import mark). Handed to the merge by TSK-0131 (N11):
              # `tools/test_migrate.py::test_the_run_receipt_carries_work_none_and_owes_no_carrier_warning`.
              DEC_WORK_FIELD: DEC_WORK_NONE}
    # EVERY GROWING PART, GROUPED BY WHAT IT POINTS AT. The loop re-measures the whole item after
    # each step and stops at the first shape that fits, so the ORDER of the steps carries nothing
    # about correctness -- only about which sentence survives longest, and the one that says the
    # state is half written is meant to survive longest of the three.
    # What the GROUPING carries is a coupling that is real and was broken once by shortening these
    # one at a time: the long `consequences` says the hashes are "in `context` above", so it is
    # only true while `context` is the long one. Giving them up together is that sentence's
    # correctness expressed as code rather than as a rule somebody has to remember.
    for step in ({"context": short_context, "consequences": short_consequences},
                 {"decision": decision_with(short_breakdown, long_tail)},
                 {"decision": decision_with(short_breakdown, short_tail)}):
        if not _too_large(fields):
            break
        fields.update(step)
    return fields


def execute(state: ProjectState, plan: dict, digest: str) -> dict:
    """Import every translatable record, then write the run's receipt.

    The caller has already checked the digest -- this function is the write half and nothing else,
    so a test can drive it without a command line.
    """
    if not plan_is_executable(plan):
        raise MigrationError(
            "this state is not migratable as it stands: %d record(s) blocked, %d still waiting "
            "for a field decision to be confirmed, %d path(s) unreadable, %d document(s) whose "
            "place in the kernel's legacy area is already taken. Remedy: `python "
            "scripts/harness.py migrate --dry-run` names each one and prints the flags that "
            "settle it."
            % (len(_by_verdict(plan, "blocked")), len(_by_verdict(plan, "needs_decision")),
               len(_unreadable_paths(plan)), len(plan["occupied_landings"])))
    importable = _importable(plan)
    if not importable:
        # WRITE NOTHING, INCLUDING THE RECEIPT. A receipt for a run that imported nothing is a new
        # item on every invocation, which would make the SECOND run of a finished migration
        # change the state -- the exact property this command promises it does not have. So the
        # empty run is a no-op with an answer, and idempotency is a fact about the code rather
        # than about how carefully somebody types.
        return {"created": [], "receipt": None, "moved": []}
    field_map = {tuple(key.split(".", 1)): value
                 for key, value in plan["field_map"].items()}
    # THE WRITE ORDER IS THE DEPENDENCY ORDER, not the reading order. A V1 store is a parent chain,
    # and a child written before its parent is a child the kernel refuses -- so `_settle_bindings`
    # numbered every record by how deep it sits in that chain and the run walks the levels. Within
    # a level the reading order is kept, so a run is reproducible.
    #
    # `resolved` is what makes the rewrite honest: the V1 parent id is replaced by the id the
    # parent ACTUALLY got, which is not the V1 one in any project that already holds items of that
    # type. It starts from the records an earlier run imported (idempotency: a re-run of a partial
    # migration must bind to those, not to nothing) and grows as this run creates items.
    # `moved` IS HELD HERE AND NOT INSIDE THE MOVE LOOP, because both receipts are written from it:
    # a run that stops half way through the retirement has moved documents, and the receipt of an
    # interrupted run used to say "none" about them (`_retire_absorbed_documents` carries the
    # measurement).
    created, resolved, moved = [], {}, []
    for entry in plan["records"]:
        if entry["verdict"] == "already_imported" and entry.get("item_id"):
            resolved[entry["legacy_id"]] = entry["item_id"]
    try:
        for entry in sorted(importable,
                            key=lambda e: (e.get("write_order", 0), e["source"], e["ordinal"])):
            payload, problem = _read_document(state, entry["source"])
            if problem:
                raise MigrationError("%s %s" % (entry["source"], problem))
            # BY ORDINAL, not by id: two records in one document may carry one V1 id, and keying
            # this lookup by id wrote record B's fields under record A's legacy metadata. Such a
            # document is refused at planning time, so this is the second line of the same defence
            # rather than the only one -- and it is what makes the plan's classification and the
            # written item provably the same record.
            found = scan_document(payload)
            by_ordinal = {ordinal: record for ordinal, _key, record in found}
            record = by_ordinal.get(entry["ordinal"])
            if record is None or _key_of(found, entry["ordinal"]) != entry["legacy_id"]:
                raise MigrationError(
                    "%s no longer holds %s at position %d; the document changed under the plan. "
                    "Remedy: re-run `python scripts/harness.py migrate --dry-run`."
                    % (entry["source"], entry["legacy_id"], entry["ordinal"]))
            fields, missing = _item_fields(
                entry["v2_type"], record, field_map,
                provenance=_provenance(entry["source"], entry["legacy_id"]))
            if missing and entry["target"] != "archive":
                raise MigrationError(
                    "%s no longer yields %s for %s; the state changed under the plan. Remedy: "
                    "re-run `python scripts/harness.py migrate --dry-run`."
                    % (entry["source"], ", ".join(missing), entry["legacy_id"]))
            body = _with_legacy(_rebind(entry["v2_type"], fields, resolved), entry, record)
            if entry.get("unresolved_fields"):
                item = state.capture_migrated_unresolved(
                    entry["v2_type"], body, entry["archive_year"])
            elif entry["target"] == "archive":
                item = state.capture_migrated_archive(
                    entry["v2_type"], body, entry["legacy_type"], entry["legacy_status"],
                    entry["archive_year"])
            else:
                item = state.capture(entry["v2_type"], body, imported=True)
            resolved[entry["legacy_id"]] = item["id"]
            created.append((entry, item["id"]))
        # INSIDE THE SAME BLOCK AS THE WRITES, because it can refuse too (a document it cannot read
        # is not moved) and because everything that fails after the first item was written owes the
        # reader the same thing: a receipt naming the ids that ARE in the state.
        _retire_absorbed_documents(state, plan, created, moved)
    except BaseException as exc:
        # A HALF-WRITTEN RUN STILL GETS ITS RECEIPT, and the refusal names the partial state.
        # `capture_preflight` is asked of every record before the plan promises anything, so the
        # expected causes here are the ones no reading can rule out -- a lock another process
        # holds, a disk, an interrupt. What must not happen either way is what was measured before
        # this: items in the store, no `DEC`, and a raw kernel message that never mentions that
        # anything had been written. The receipt is attempted first and its own failure is folded
        # into the message rather than replacing it.
        # Nothing written means nothing moved either: the retirement loop runs after the write
        # loop, and the write loop is only entered when at least one record is importable.
        if not created:
            raise
        note = None
        try:
            # `moved` IS HANDED IN HERE TOO. It used to be built inside the retirement loop and
            # returned from it, so this call got nothing -- and the receipt of a run that really
            # had moved documents said "moved to legacy/: none" and put those same documents under
            # "carried, not translated (left in place, unrenamed and unedited)".
            receipt = state.capture(RECEIPT_TYPE,
                                    _receipt_fields(plan, created, digest, interrupted=str(exc),
                                                    moved=moved))
            note = "recorded as %s" % receipt["id"]
        except BaseException as second:      # noqa: BLE001 -- the first failure must survive
            note = ("and the receipt could NOT be written either (%s), so the only record of "
                    "these ids is this message" % second)
        raise MigrationError(
            "the import stopped after writing %d item(s) (%s) and moving %d document(s) to "
            "legacy/ (%s) -- %s. Those items are in the state and are NOT rolled back; a re-run "
            "skips them by their `legacy_fields.legacy_id`. The failure was: %s"
            % (len(created), ", ".join(item_id for _e, item_id in created), len(moved),
               ", ".join(doc["path"] for doc in moved) or "none", note, exc)) from exc
    receipt = state.capture(RECEIPT_TYPE, _receipt_fields(plan, created, digest, moved=moved))
    return {"created": [item_id for _entry, item_id in created], "receipt": receipt["id"],
            "moved": moved}


def absorbed_documents(plan: dict, written=None) -> list:
    """The V1 documents this plan leaves with nothing of its own left -- SR-0005's condition.

    TWO CLAUSES, and each one is a defect the other does not cover:

      * at least one record of the document BECAME AN ITEM. Without it, a kit document that merely
        mentions ids -- `acceptance_reports.yaml` keys its entries `ACC-nnnn` and every one of them
        is a report about a task, not a backlog record -- would satisfy the second clause vacuously
        and be moved out of the project.
      * NO BACKLOG RECORD of it is left untranslated. `not_an_item` records do not hold a document
        back, and that is deliberate rather than lenient: such a record is a cross-reference note
        or a record of some other kind, so it is not a second copy of anything, while ONE of them
        in a store of 265 real ones would otherwise keep the whole store beside its own items for
        ever -- which is exactly the double SR-0005 exists to end, and which `validate` would then
        report as an error nobody could clear.

    ...AND A WALL IS NEVER MOVED, whatever its records did. A wall is a kit document whose CONTENT
    a registered, refusal-capable hook reads (`layout.gated_documents`, carried in the plan), and
    moving one to `legacy/` takes it out from under that gate: the gate then reads an absent file,
    and what a fail-closed gate does with one is its own business and not this command's to
    provoke. SR-0005's reason for the move -- the same thing existing twice -- does not reach this
    case either, because the gate does not read the file for its ITEMS. Reachable by construction
    rather than in the field, which is why it is a clause rather than a note;
    `test_migrate.test_a_document_a_registered_gate_reads_is_never_moved_to_legacy` builds the
    installation that reaches it and is where that reading is recorded.

    THE PRINTED SIDE OF THE SAME QUESTION IS GONE RATHER THAN DUPLICATED (DEC-0024): `_coverage_of`
    used to carry a clause of its own so that no wall was named as the target of a move a READER
    would make, and it needs none now, because it names no move. This clause stays because this
    move is one the COMMAND makes.

    `written` is the set of `(source, ordinal)` pairs the RUN actually created, so a document is
    only retired on the strength of writes that happened -- an interrupted run leaves its documents
    where they are. The dry run passes None and asks the plan instead, which is the same question
    about a run that has not happened yet.
    """
    absorbed, unfinished = set(), set(plan.get("gated_documents") or ())
    for entry in plan["records"]:
        source, verdict = entry["source"], entry["verdict"]
        if verdict == "already_imported" or (
                verdict in _IMPORTING_VERDICTS
                and (written is None or (source, entry["ordinal"]) in written)):
            absorbed.add(source)
        elif verdict != "not_an_item":
            unfinished.add(source)
    return sorted(absorbed - unfinished)


def _retire_absorbed_documents(state: ProjectState, plan: dict, created: list, moved: list) -> None:
    """Move every absorbed V1 document under `legacy/`, with its hash, appending the receipt rows.

    THE HASH IS TAKEN BEFORE THE MOVE and of the bytes that are moved, so the receipt says what
    was carried rather than what was planned; a document that changed under the plan is caught by
    the digest long before this. The move itself is `os.replace` within one directory tree, which
    is atomic per file -- there is no state in which a document is in both places, and none in
    which it is in neither.

    A DOCUMENT WHOSE BYTES CANNOT BE READ HERE IS NOT MOVED AND NOT HASHED, and the run stops on it
    rather than filing a receipt row with no hash in it. Reaching that needs a file that was
    readable while the plan was built and the digest re-derived and is not readable now, so what it
    really guards is that such a run ends as a REFUSAL naming the document.

    AND A LANDING PLACE THAT IS TAKEN STOPS THE MOVE INSTEAD OF OVERWRITING IT. `os.replace` is
    atomic and silent: it replaces what is there. Measured 2026-08-09 -- one run absorbed
    `old_procs.yaml` and filed its hash in the receipt; the document was put back and edited; the
    second run replaced `legacy/old_procs.yaml`, and the first receipt's hash then named bytes that
    exist nowhere. `build_plan` reports the same condition in advance (`occupied_landings`), so a
    dry run says it before anything is written; this is the same question one step before the write,
    for the case where the two are not the same moment.

    `moved` BELONGS TO THE CALLER, so a run that stops half way through the loop still knows which
    documents it moved: `execute` hands in the list it also gives the interrupted receipt. Before
    this the list was built here and returned, so an interrupted run filed a receipt saying "moved
    to legacy/: none" about documents that really had been moved -- and listed them under "carried,
    not translated (left in place, unrenamed and unedited)".
    """
    written = {(entry["source"], entry["ordinal"]) for entry, _item_id in created}
    for rel in absorbed_documents(plan, written):
        facts, problem = _file_facts(state, rel)
        if problem:
            raise MigrationError(
                "%s %s, so it is left where it is and this run stops: SR-0005 retires a document "
                "with the hash of the bytes it carried, and a receipt row without one says nothing "
                "a later audit could check." % (rel, problem))
        landing = legacy_location(rel)
        if _is_occupied(state, landing):
            raise MigrationError(
                "%s would be retired to %s, and something is already there: the move is an "
                "`os.replace`, which would take it away without saying so, and an earlier run's "
                "receipt carries the hash of what stands there. This run stops instead. Remedy: "
                "move %s out of the state directory from a shell outside the session, then re-run "
                "the dry run." % (rel, landing, landing))
        target = state.legacy_path(rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        os.replace(os.path.join(state.root, *rel.split("/")), target)
        facts["moved_to"] = _relative(state, target)
        moved.append(facts)


def _key_of(found, ordinal):
    """The legacy id the walk saw at `ordinal`, or None."""
    for position, key, _record in found:
        if position == ordinal:
            return key
    return None


# -- the goal-size vocabulary migration (DEC-0103) --------------------------------------------

def goal_class_plan(state: ProjectState, mapping: dict) -> list:
    """One row per STORED root goal: what its class says now and what this run would write.

    WHY A MIGRATION DOOR AT ALL. DEC-0103 closed the vocabulary at the two doors that WRITE a goal
    (`state._assert_closed_vocabularies`), and a door only ever sees the next write: a project that
    already holds `class: feature` keeps it, and every reader of that value goes on deciding from a
    word the vocabulary does not know -- fail-closed, but silently more expensive forever (an
    architect step asked of a goal that owes none). This is the one command that moves such a value,
    and it is in the kernel because the store has exactly one writer.

    WHAT IT REFUSES TO GUESS. The mapping is the caller's (`--map feature=normal`), never a table
    in here: which size a project's own word meant is a fact about that project. A stray this run
    has no mapping for is REPORTED and left, and the command exits non-zero on it, so "nothing to
    do" and "I could not decide" are two different answers.

    ARCHIVED GOALS ARE READ AND NOT WRITTEN. A record under `archive/` is a protocol of what
    happened (DEC-0004), and the active door is the one every reader that DECIDES from a class goes
    through: an order is leased against `state.read_item(root_id)` and the delivery-sequence check
    reads the active items. Such a row carries `archived: True`, is counted in the plan and left
    alone, with the reason in the rendering.
    `tools/test_migrate.py::test_the_goal_class_plan_reads_every_stored_goal_and_writes_only_the_active_strays`
    """
    # WHICH GOALS ARE ACTIVE, asked of the store's own reader rather than by composing a path:
    # `_read_bytes` is this module's ONE opener of a state file and everything that can NAME one
    # carries a licence beside it (`tools/test_migrate.py::_NAMES_A_STATE_FILE`). A membership test
    # over the active stems answers the same question and names nothing.
    active = set()
    for item_type in sorted(GOAL_CLASS_TYPES):
        for stem, _path in state.iter_active_items(item_type):
            active.add(str(stem))
    rows = []
    for item in state._iter_every_stored_item():
        item_id = str(item.get("id") or "")
        try:
            item_type, _ = parse_id(item_id)
        except ValueError:
            continue
        if item_type not in GOAL_CLASS_TYPES:
            continue
        current = item.get(GOAL_CLASS_FIELD)
        archived = item_id not in active
        if current in GOAL_CLASSES:
            target, why = None, "already a word of the vocabulary"
        elif str(current) in mapping:
            target = mapping[str(current)]
            why = "archived -- left as the protocol of what happened (DEC-0004)" if archived else (
                "mapped by this run")
            if archived:
                target = None
        else:
            target, why = None, "no --map entry names this value"
        rows.append({"id": item_id, "type": item_type, "current": current, "target": target,
                     "archived": archived, "why": why})
    return sorted(rows, key=lambda row: row["id"])


def unmapped_goal_classes(plan) -> list:
    """The rows this run could not decide -- what makes the command exit non-zero."""
    return [row for row in plan
            if row["current"] not in GOAL_CLASSES and row["target"] is None
            and not row["archived"]]


def render_goal_class_plan(plan) -> str:
    """The before/after list, one line per stored goal, plus what the run leaves behind."""
    lines = ["%d stored goal(s); vocabulary: %s"
             % (len(plan), ", ".join(sorted(GOAL_CLASSES)))]
    for row in plan:
        lines.append("%s %s: %r -> %s%s -- %s"
                     % (row["type"], row["id"], row["current"],
                        row["target"] if row["target"] is not None else "(unchanged)",
                        " [archived]" if row["archived"] else "", row["why"]))
    unmapped = unmapped_goal_classes(plan)
    if unmapped:
        lines.append("UNDECIDED: %s -- pass `--map <value>=<%s>` for each, or leave them and read "
                     "the refusal at the next `update`."
                     % (", ".join("%s (%r)" % (row["id"], row["current"]) for row in unmapped),
                        "|".join(sorted(GOAL_CLASSES))))
    return "\n".join(lines)


def execute_goal_classes(state: ProjectState, plan) -> list:
    """Write the rows the plan decided, through the SAME door a role would use.

    `state.update_item` and not a file write: it is the edit path, so the new value passes the very
    vocabulary check this migration exists to satisfy, and a rewrite that would still be refused
    stops the run instead of landing.
    """
    written = []
    for row in plan:
        if row["target"] is None:
            continue
        state.update_item(row["id"], {GOAL_CLASS_FIELD: row["target"]})
        written.append((row["id"], row["current"], row["target"]))
    return written
