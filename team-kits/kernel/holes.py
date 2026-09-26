"""The H-numbered hole list of `docs/POST_V2_WISHLIST.md` as typed items -- the migration door.

WHY THIS LIVES IN THE KERNEL. It writes canonical state, and gate 1 gives canonical state exactly
one writer: `python -B -m kernel.cli --root project_memory <command>`. As a tool under `tools/` its
one writing run was a line no role inside a session could take -- it had to be handed to the user
for a shell outside Claude Code, which is a route a remote user does not have (TSK-0126, merge
rework 3). `tools/migrate_holes.py` still exists and still has its own command line; it calls this
module, so there is one door and not two.

WHAT IT WRITES, and it writes it in TWO places for one reason each:

  * the ITEM -- through `state.capture_migrated_hole`, the migration door DEC-0073's sub-question
    (3a) settled. It is thin on purpose: identity (`hole_number`), verdict (the STATUS), what
    limits instead (`limits`), the tests that would notice a relapse (`regression_tests`) and a
    pointer to the prose. That is the shape CLAUDE.md already prescribes for an FR -- the prose
    stays in `docs/`, the item carries identity and standing -- and it is not a preference here:
    measured over the shipped section, three entries are larger than the 12 KB an active item may
    be and ten are longer than 200 lines, so the full text cannot live in an item at all.
  * the PROSE -- one file per entry under `docs/holes/`, carrying what the section carried.

WHAT IS LEFT IN THE DOCUMENT is a GENERATED index: one row per hole, pointing at the item and at
the prose file. Generated the way the board is, and a hand edit is caught the same way -- not by a
digest written beside it but by regenerating it and comparing, which is what
`.claude/hooks/test_gates.py::test_the_hole_index_in_the_document_is_the_one_the_items_generate`
does. A number in two places is what this migration exists to end, so there is no second one.

IDEMPOTENT, and the property is the store rather than a marker file: `state.hole_by_number` answers
"is this number already in the store", so a second run writes nothing and a run interrupted halfway
resumes where it stopped. Measured, not asserted --
`tools/test_migrate_holes.py::test_a_second_run_over_the_same_document_writes_nothing`.

HOW THE OTHER STREAMS' ENTRIES ARRIVE. A generation cuts several streams, and each files the holes
it measures in the CURRENT format -- an `### H<n>` heading in the section plus a summary row. This
reads exactly that format, so entries that arrive in a merge patch are migrated by the same run as
the rest; the number a stream reserved in its own item is kept as written, because the migration
carries the number over instead of allocating one. Only a hole captured AFTER the migration gets
its number from `state.capture(hole=True)`.
"""
from __future__ import annotations

import io
import os
import re

from .backlog_types import (
    HOLE_LIMIT_FIELD,
    HOLE_NUMBER_FIELD,
    HOLE_TEST_FIELD,
    TEST_REF_AMENDMENTS_FIELD,
)
from .state import ProjectState


def document_for(state: ProjectState) -> str:
    """The hole document of the project this state belongs to.

    Derived from the state directory rather than from this module's own location: the kernel is
    COPIED into every project (`.claude/kernel`), so a path relative to the source tree would name
    the repository this file happens to have been edited in.
    """
    return os.path.join(os.path.dirname(os.path.abspath(state.root)),
                        "docs", "POST_V2_WISHLIST.md")


# The heading the hole list opens with, and the level that closes it. The section is found by its
# NUMBER and not by its words, so a retitled section is still found and a renumbered one fails
# loudly instead of migrating half a document.
SECTION_PREFIX = "## 12."
ENTRY_RX = re.compile(r"^### (H\d+)\b(.*)$")
DEFAULT_HOLES_DIR = "docs/holes"

# WHAT AN ENTRY'S VERDICT MAKES OF IT: {first bold word of its summary row -> (status, severity)}.
#
# AN ENUMERATION, BECAUSE THE SOURCE IS GROWN GERMAN PROSE and no property of the text decides it.
# So it carries the tripwire at both ends: `_assert_the_verdict_map_fits` refuses to run when a
# word of this map appears in no row (a dead row) AND when a row uses a word this map does not know
# (an entry that would otherwise be migrated on a guess). Measured over the shipped section on
# 2026-09-04: these six words cover all 140 rows and each of them is used.
#
# `rest` and `verkleinert` map to TRIAGED rather than OPEN deliberately: an entry saying a defect
# was narrowed and naming what is left is one somebody has already read and weighed, which is what
# TRIAGED means; OPEN is the entry nobody has weighed yet. `kein` is the row saying the
# investigation found no hole, and REJECTED is the automaton's word for a report that does not
# stand.
VERDICT_STATUS = {
    "geschlossen": ("VERIFIED", "low"),
    "ausnahme": ("ACCEPTED_EXCEPTION", "medium"),
    "kein": ("REJECTED", "low"),
    "rest": ("TRIAGED", "low"),
    "offen": ("TRIAGED", "medium"),
    "verkleinert": ("TRIAGED", "low"),
}

BOLD_RX = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_FENCE_LINE_RX = re.compile(r"^([`]{3,}|[~]{3,})(.*)$")
_CODE_SPAN_RX = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)
_CITATION_SPLIT_RX = re.compile(r"::|\.")
_DECORATION = "…._"
# What `observed` may carry off the entry's first paragraph. A bound and not a truncation habit:
# an active item is capped at 12 KB by `report.ITEM_MAX_BYTES`, and the whole text lives in the
# prose file the item points at.
OBSERVED_MAX_CHARS = 1500


def read_section(path):
    """(all lines, first line of the section, first line after it)."""
    lines = io.open(path, encoding="utf-8").read().splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.startswith(SECTION_PREFIX))
    except StopIteration:
        raise SystemExit("no %r section in %s -- nothing to migrate" % (SECTION_PREFIX, path))
    end = next((i for i, line in enumerate(lines[start + 1:], start + 1)
                if line.startswith("## ")), len(lines))
    return lines, start, end


def parse_entries(section):
    """{H<n>: (title, [body lines])} in the order the section carries them."""
    entries, current = {}, None
    for line in section:
        found = ENTRY_RX.match(line)
        if found:
            current = found.group(1)
            entries[current] = (found.group(2).lstrip(" —-").strip(), [])
        elif current:
            entries[current][1].append(line)
    return entries


def parse_rows(section):
    """{H<n>: (verdict word, what takes the place of the protection)} from the summary table."""
    rows = {}
    for line in section:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3 or not re.search(r"H\d+", cells[0]) or set(cells[1]) <= set("- "):
            continue
        bold = BOLD_RX.search(cells[1])
        words = re.findall(r"\w+", (bold.group(1) if bold else cells[1]).lower())
        for name in re.findall(r"H\d+", cells[0]):
            rows[name] = (words[0] if words else "", cells[2])
    return rows


def _fence_marker(line):
    found = _FENCE_LINE_RX.match(line.strip())
    if not found or found.group(1)[0] in found.group(2):
        return None
    return found.group(1)[0]


def _prose_of(body):
    """The lines of an entry that carry prose -- its fenced blocks cut out.

    The same reading the shipped judge in `.claude/hooks/test_gates.py` had to grow for this
    document (a fence line is its marker and nothing else; a code span is a RUN of backticks closed
    by a run of the same length). It is here because this is the LAST run that reads those
    citations out of prose at all: from here on they are a field of the item.
    """
    kept, opened = [], None
    for line in body:
        marker = _fence_marker(line)
        if marker and (opened is None or marker == opened):
            opened = None if opened else marker
            continue
        if opened is None:
            kept.append(line)
    return "\n".join(kept)


def cited_tests(body):
    """Every test name the entry's prose cites, de-duplicated and in reading order."""
    names = []
    for found in _CODE_SPAN_RX.finditer(_prose_of(body)):
        span = re.sub(r"\s+", "", found.group(2))
        if "`" in span:
            continue
        tail = _CITATION_SPLIT_RX.split(span)[-1]
        if not tail.lstrip(_DECORATION).startswith("test_") or tail.strip(_DECORATION) == "test":
            continue
        if span not in names:
            names.append(span)
    return names


def test_modules_under(repo: str):
    """Every file a runner would collect as a test module, as repo-relative paths.

    A DEFINITION AND NOT A LIST OF DIRECTORIES: pytest's own rule is the file NAME, so this is that
    rule applied to the tree. The directories that hold no tests of a project -- its git store, its
    TOOL LEFTOVERS, its dependency tree -- are skipped because walking them answers nothing and
    costs the whole disk. The leftovers are asked of `hashing.is_transient`, the kernel's ONE answer
    to "is this a tool's cache", rather than spelled out here: the second spelling of that list was
    short by three names and looked exactly as authoritative as the complete one
    (`tools/test_hooks_v2.py::test_no_shipped_script_knows_about_only_some_tool_caches` is what
    caught it, and the day a fifth cache kind ships this walk moves with it).
    """
    from .hashing import is_transient
    found = []
    for directory, subdirectories, names in os.walk(repo):
        subdirectories[:] = [one for one in subdirectories
                             if one not in (".git", "node_modules") and not is_transient(one)]
        for name in sorted(names):
            if name.startswith("test_") and name.endswith(".py"):
                found.append(os.path.relpath(os.path.join(directory, name), repo)
                             .replace(os.sep, "/"))
    return found


def citation_resolution(repo: str, citation: str):
    """Every test declaration this citation names -- [] when it names none, several when ambiguous.

    THE READER IS `kernel.naming_tests`, the one this repository already decides "does this test
    name that item" with, so "a test exists" cannot mean two things. A citation carrying a FILE is
    resolved in that file alone; a bare name is searched over every test module, which is what
    makes "more than one" a possible answer at all.
    `tools/test_migrate_holes.py::test_a_citation_that_names_no_test_stops_the_run_before_it_writes`
    """
    from . import naming_tests

    path, _sep, name = str(citation or "").strip().rpartition("::")
    name = name.split("[")[0].strip().strip("`*_.,;:()")
    if not name:
        return []
    if path:
        node = "%s::%s" % (path.replace("\\", "/"), name)
        return [node] if naming_tests.declares(repo, node) else []
    return [node for node in
            ("%s::%s" % (module, name) for module in test_modules_under(repo))
            if naming_tests.declares(repo, node)]


def _assert_every_citation_resolves(repo: str, name: str, tests) -> None:
    """Refuse BEFORE the item is written when a cited test names no test, or more than one.

    THE DEFECT WAS THE ORDER AND NOT THE COLLECTION (BUG-0246). `cited_tests` reads a code span the
    prose wrote, and a MODULE name in backticks looks exactly like a test name to it; the judge that
    notices lives downstream and runs AFTER the item is in the store -- and this migration is
    idempotent, so a second run reports "already in the store" and repairs nothing. Asking the same
    question here, in front of the write, turns a record that has to be repaired by hand into a run
    that stops with the citation in its message.

    A BARE NAME MATCHING SEVERAL MODULES IS ALSO A REFUSAL, and for the same reason: the item would
    claim a regression test the reader cannot point at, and which of them it meant is a question
    only the author can answer.

    A CHECKOUT THAT DECLARES NO TEST MODULE AT ALL IS NOT ASKED, and that is the same third answer
    the rest of this kernel gives: in such a tree every citation resolves to nothing, so a refusal
    would be a statement about the checkout rather than about the document -- and it is what keeps
    this from refusing a migration run over a synthetic tree.
    """
    if not test_modules_under(repo):
        return
    broken = []
    for citation in tests:
        found = citation_resolution(repo, citation)
        if len(found) != 1:
            broken.append("%s -> %s" % (citation, ", ".join(found) if found else "no test"))
    if broken:
        raise SystemExit(
            "%s cites a test this checkout cannot resolve to exactly one declaration: %s. A hole "
            "item that names a test nobody can run claims a cover it does not have, and this "
            "migration is idempotent -- written once, a second run will not repair it. Remedy: "
            "write the node id the runner prints (`<file>::<test>`), or drop the citation."
            % (name, "; ".join(broken)))


def _assert_the_verdict_map_fits(rows):
    """No row this run would have to GUESS a status for -- the one direction that is a refusal.

    THE OTHER DIRECTION IS NOT CHECKED HERE, and that is a correction rather than an omission.
    A first cut also refused when a word of `VERDICT_STATUS` appeared in no row, and it was wrong
    twice over, measured on 2026-09-04: the second run over an already migrated document found no
    rows at all and exited 1 instead of doing nothing, and a MERGE PATCH bringing three new entries
    would have made four of the six words "dead" and refused the very run this script exists for.
    A rule about the shipped document does not belong in a run over an arbitrary one -- it is
    `tools/test_migrate_holes.py::test_every_verdict_the_migration_reads_maps_onto_the_bug_automaton`
    that holds the map to something that cannot go stale, and the reading of the shipped section
    (140 of 140 rows, no unknown word) is a measurement of one round and lives in its report.
    """
    used = {word for word, _limit in rows.values()}
    unknown = sorted(used - set(VERDICT_STATUS))
    if unknown:
        raise SystemExit(
            "these summary rows state a verdict this migration cannot read, so it would have to "
            "guess a status: %s. Remedy: decide what each one means and add it to VERDICT_STATUS "
            "-- a guessed status is a lie the store then keeps." % unknown)


def item_body(name, title, body, verdict, limit, related_pr, prose_path):
    """(the thin item one entry becomes, the status it is written at)."""
    status, severity = VERDICT_STATUS[verdict]
    first_paragraph = "\n".join(body).strip().split("\n\n")[0]
    fields = {
        "title": title or name,
        "related_pr": related_pr,
        "observed": first_paragraph[:OBSERVED_MAX_CHARS] or title or name,
        "severity": severity,
        HOLE_NUMBER_FIELD: name,
        "source": prose_path,
    }
    if limit:
        fields[HOLE_LIMIT_FIELD] = limit
    tests = cited_tests(body)
    if tests:
        fields[HOLE_TEST_FIELD] = tests
    return fields, status


# WHAT MAKES TWO RECORDS OF ONE NUMBER THE SAME ENTRY. The migration is resumable, so meeting a
# number the store already carries is the ORDINARY case -- an interrupted run coming back. It is
# also the DANGEROUS case: at a merge, four streams reserve numbers by hand in their own items, and
# two of them can pick the same one. Measured 2026-09-05 before this existed: the store carried
# H151, the document brought a DIFFERENT H151 in the current format, and the run answered
# "0 written, 1 already in the store" with rc 0 -- the second entry's prose was written nowhere, its
# item never existed, and the rewrite of the section removed it from the document. Silent data loss
# on the one run the whole migration rests on.
#
# The fields compared are the two that carry the entry's identity: its title and the mechanism
# paragraph. Not the limit and not the cited tests -- those legitimately change when an entry is
# re-judged, and a resumed run must not trip over a document somebody edited between two halves of
# it.
_IDENTITY_FIELDS = ("title", "observed")


def _assert_it_is_the_same_hole(name, existing, fields):
    """Refuse when a number the store carries names a DIFFERENT entry than the document brings.

    `tools/test_migrate_holes.py::test_a_number_collision_at_the_merge_is_refused_not_skipped`
    """
    differing = [field for field in _IDENTITY_FIELDS
                 if str(existing.get(field) or "").strip() != str(fields.get(field) or "").strip()]
    if not differing:
        return
    raise SystemExit(
        "%s is already in the store as %s, and the entry this document brings is a DIFFERENT one "
        "(%s differ). Two streams reserved one number. Nothing was written for the second entry, "
        "and skipping it would drop it from the document without a word. Remedy: give one of the "
        "two a number no item carries -- `%s` in the store reads %r, the document reads %r -- and "
        "run this again; every other entry is unaffected, because a run that finds its number "
        "already stored writes nothing."
        % (name, existing.get("id"), "/".join(differing), differing[0],
           str(existing.get(differing[0]) or "")[:120], str(fields.get(differing[0]) or "")[:120]))


def _amendment_note(item) -> str:
    """What the Stand cell adds for a hole whose test reference the archive door corrected.

    DEC-0117 (2): the hole list shows every use of the door. The newest record's date and the count
    are enough for a row; who and why stand in the item's own record.
    `tools/test_archive_door.py::test_the_hole_list_shows_the_correction`
    """
    records = [one for one in (item.get(TEST_REF_AMENDMENTS_FIELD) or []) if isinstance(one, dict)]
    if not records:
        return ""
    return "Testverweis korrigiert %s (%dx)" % (str(records[-1].get("at") or "?")[:10],
                                               len(records))


def index_rows(state):
    """[(H number, item id, status, title, note)] for every hole the STORE carries, by number.

    THE INDEX IS GENERATED FROM THE ITEMS and from nothing else -- that is the whole point of the
    migration. A reader falling back to the document would be the second list FR-0087 forbids.
    `note` is `_amendment_note`'s, "" for every hole the archive door never touched.
    """
    rows = []
    with state.lock:
        for item in state._iter_every_stored_item():
            number = str(item.get(HOLE_NUMBER_FIELD) or "")
            if not number:
                continue
            rows.append((number, str(item.get("id")), str(item.get("status") or "-"),
                         str(item.get("title") or ""), _amendment_note(item)))
    return sorted(rows, key=lambda row: int(row[0][1:]) if row[0][1:].isdigit() else 0)


GENERATED_HEADER = (
    "<!-- GENERATED by tools/migrate_holes.py -- do not edit by hand. The holes are ITEMS; this is "
    "a pointer index regenerated from them, and a hand edit is what "
    "test_the_hole_index_in_the_document_is_the_one_the_items_generate reports. -->")


def _prose_link(repo, holes_dir, number):
    """The first cell of a row: a LINK where the prose file is there, the bare number where it is not.

    THE MEASURED DEFECT: this cell used to be a link unconditionally. Only the MIGRATION writes a
    prose file (`migrate`, above); `capture --hole` writes an item and nothing else -- so from the
    first hole captured after the migration on, the shipped index pointed at files that do not
    exist. Measured 2026-09-05 in this repository's own document: 164 rows, 155 files, nine dead
    links (H166-H173, plus H174 the moment it was captured). A pointer nobody can follow is the
    class this repository keeps re-learning, and the index is read by humans, so the honest cell
    for a hole whose full text lives in its ITEM is the number without a link.
    `tools/test_migrate_holes.py::test_a_hole_with_no_prose_file_is_a_row_without_a_link` holds
    both directions; `tools/test_repo_hygiene.py::test_every_hole_is_one_index_row_one_prose_file
    _and_one_item` holds the result over this repository's own document.
    """
    relative = "%s/%s.md" % (holes_dir, number)
    if os.path.isfile(os.path.join(repo, relative.replace("/", os.sep))):
        return "[%s](%s)" % (number, relative)
    return number


def render_index(state, holes_dir=DEFAULT_HOLES_DIR):
    """The generated section that replaces the entries in the document."""
    repo = os.path.dirname(os.path.abspath(state.root))
    lines = [
        "## 12. Loecherliste der Repo-Gates -- GENERIERTER ZEIGERINDEX",
        "",
        GENERATED_HEADER,
        "",
        "Jedes Loch ist ein Item (`BUG` mit `hole_number`) und wird dort gelesen. Wo die Nummer "
        "verlinkt ist, liegt unter `%s/` zusaetzlich der Volltext, den die Migration aus dem "
        "frueheren Dokument uebernommen hat; ein spaeter erfasstes Loch hat keinen und ist "
        "deshalb nicht verlinkt. Neue Nummern vergibt der Kernel (`capture --hole`), nicht die "
        "Hand." % holes_dir,
        "",
        "| Loch | Item | Stand | Titel |",
        "|---|---|---|---|",
    ]
    for number, item_id, status, title, note in index_rows(state):
        lines.append("| %s | %s | %s | %s |"
                     % (_prose_link(repo, holes_dir, number), item_id,
                        "%s; %s" % (status, note) if note else status,
                        title.replace("|", "/")))
    lines.append("")
    return lines


def _write_index(doc, lines, start, end, state, holes_dir):
    """Replace the section with the index the STORE generates -- unless that would empty it.

    THE ONE REFUSAL: a run whose store carries no hole at all, over a document that carries some,
    would answer "index rewritten: 0 hole(s)" and delete the pointer index of a shipped document
    with rc 0. Measured 2026-09-05 (round-2 verification, R2): a mistyped `--root` cost 143 rows
    and said it had succeeded. That is the same class as the number collision -- a loss the run
    reports as a success -- and it is refused for the same reason.

    It is not a general "the index may only grow": an index that SHRINKS because a hole was
    archived out of the store is a legitimate rewrite, and this lets it through. What it refuses is
    the one case where the new index is empty and the old one is not, because a store with no hole
    at all is a store this document was not generated from.
    `tools/test_migrate_holes.py::test_an_empty_store_does_not_empty_a_full_index`
    """
    rendered = render_index(state, holes_dir)
    if not index_rows(state) and _index_row_count(lines[start:end]):
        raise SystemExit(
            "the store under this --root carries no hole at all, and the document carries %d. "
            "Writing the generated index now would delete every pointer with a success message. "
            "Remedy: point --root at the state directory this document was generated from; if the "
            "store really is empty on purpose, remove the section by hand -- this command will not "
            "do it silently." % _index_row_count(lines[start:end]))
    io.open(doc, "w", encoding="utf-8", newline="\n").write(
        "\n".join(lines[:start] + rendered + lines[end:]) + "\n")


def _index_row_count(section):
    """How many pointer rows the section carries -- read off the shape `render_index` writes.

    The link is OPTIONAL here for the reason `_prose_link` gives: a hole with no prose file is a
    row without one, and counting only the linked rows would let the empty-index refusal above
    read a document of unlinked rows as empty -- which is the loss it exists to refuse.
    """
    return len([line for line in section if re.match(r"^\| (?:\[)?H\d+\b", line)])


def migrate(state, doc, related_pr, holes_dir=DEFAULT_HOLES_DIR, apply=False):
    """Read the document, write the prose files and the items, return a report."""
    lines, start, end = read_section(doc)
    section = lines[start:end]
    entries = parse_entries(section)
    rows = parse_rows(section)
    report = {"written": [], "already": [], "prose": []}
    if entries:
        # A verdict map is only asked of a document that still HAS entries. Asked of one that is
        # already the generated index it found no rows at all and exited 1 -- the second run of the
        # migration, measured 2026-09-04.
        _assert_the_verdict_map_fits(rows)
        unjudged = sorted(set(entries) - set(rows))
        if unjudged:
            raise SystemExit(
                "these entries carry no summary row, so nothing states their verdict: %s"
                % unjudged)
    repo = os.path.dirname(os.path.abspath(state.root))
    for name, (title, body) in entries.items():
        verdict, limit = rows[name]
        prose_rel = "%s/%s.md" % (holes_dir, name)
        fields, status = item_body(name, title, body, verdict, limit, related_pr, prose_rel)
        # BEFORE THE WRITE, never after it -- see `_assert_every_citation_resolves` (BUG-0246).
        # Asked on the DRY RUN too, because a dry run that says "this would be written" about a
        # record the real run refuses is worse than no dry run.
        _assert_every_citation_resolves(repo, name, fields.get(HOLE_TEST_FIELD) or ())
        existing = state.hole_by_number(name)
        if existing is not None:
            _assert_it_is_the_same_hole(name, existing, fields)
            report["already"].append((name, existing["id"]))
            continue
        if not apply:
            report["written"].append((name, "(dry run)", status))
            continue
        target = os.path.join(repo, prose_rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        io.open(target, "w", encoding="utf-8", newline="\n").write(
            "# %s -- %s\n\n%s\n" % (name, title, "\n".join(body).strip()))
        report["prose"].append(prose_rel)
        item = state.capture_migrated_hole(fields, status)
        report["written"].append((name, item["id"], status))
    if apply:
        # THE INDEX IS REWRITTEN FROM THE STORE, ALWAYS -- and that is the correction of
        # 2026-09-05. It used to sit behind the entry loop, so after the one-time migration this
        # run had nothing to do and the section could never be brought back into step: a hole
        # captured through `capture --hole` was missing from the index, and the remedy the gate
        # test prints ("re-run this with --apply") did nothing. Measured then: index != generated
        # before AND after the remedy.
        _write_index(doc, lines, start, end, state, holes_dir)
    return report


def reindex(state: ProjectState, doc: str, holes_dir: str = DEFAULT_HOLES_DIR) -> str:
    """Rewrite the document's generated pointer index from the store, and nothing else."""
    lines, start, end = read_section(doc)
    _write_index(doc, lines, start, end, state, holes_dir)
    return "index rewritten from the store: %d hole(s)" % len(index_rows(state))


def render_report(report: dict):
    """The lines a caller prints -- one per entry, then the count."""
    for name, item_id, status in report["written"]:
        yield "%-6s -> %-10s %s" % (name, item_id, status)
    yield ("%d written, %d already in the store, %d prose files"
           % (len(report["written"]), len(report["already"]), len(report["prose"])))
