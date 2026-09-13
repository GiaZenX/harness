"""The V1 -> V2 import (spec II.10), measured against a REAL V1 state directory.

WHERE THE V1 PROJECT COMES FROM, and why it is not a fixture. A hand-written "V1 monolith" in this
file would be this round's idea of what V1 looked like, and it would agree with the migration by
construction -- the two would have the same author. So the state under test is the office kit's own
`templates/project_memory/`, read out of THIS REPOSITORY'S HISTORY at the newest commit that still
carries it, filled with four weeks of operation, and then overlaid with the V2 templates the way a
user's re-scaffold overlays them (copy-if-absent). Every V1 schema in it -- `filing_plan.tree`, the
`processes:` mapping, the append-only logs -- is the schema the kit really shipped, and none of it
was written to be migrated.

The lookup is by CONTENT rather than by a commit id: the newest commit in which the V1 monolith
still exists. A commit hash written here would be a fact about one clone; "the last version of the
file that existed" is a fact about the file. If the history is unreachable these tests FAIL rather
than skip -- a measurement that quietly does not happen is the failure mode this suite has been
bitten by before, and a skip is indistinguishable from a pass in a summary line.
"""
import ast
import collections
import contextlib
import copy
import getpass
import hashlib
import io
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tokenize
import unicodedata
import urllib.parse

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "team-kits"))

from kernel import approvals, cli, migrate  # noqa: E402
from kernel.backlog_types import (  # noqa: E402
    REQUIRED_FIELDS,
    V1_FIELD_SUGGESTIONS,
    V1_STATUS_MAPPING,
    initial_status,
    parse_id,
)
from kernel.state import ProjectState, migration_archives  # noqa: E402

# The year handed to the runs below. Only records the V1 office schema dates NOWHERE need it, and
# the office PROC schema dates nothing at all -- see `test_a_finished_record_with_no_date_...`,
# which measures that this is a refusal and not a default.
_ARCHIVE_YEAR = 2026

# The V1 monolith whose absence marks a tree as V2. Used only to LOCATE the last V1 commit; the
# whole template directory at that commit is what gets restored.
_V1_TEMPLATE_DIR = "team-kits/office-team/templates/project_memory"
_V1_MARKER = _V1_TEMPLATE_DIR + "/process_definitions.yaml"
_V2_TEMPLATE_DIR = os.path.join(ROOT, "team-kits", "office-team", "templates", "project_memory")


def _git(*args):
    result = subprocess.run(["git", "-C", ROOT] + list(args),
                            capture_output=True, timeout=120)
    return result.returncode, result.stdout


def _last_v1_commit():
    """The newest commit in this repository in which the V1 monolith still exists."""
    code, out = _git("log", "--all", "--format=%H", "--", _V1_MARKER)
    if code != 0:
        pytest.fail("git could not read this repository's history, so the real V1 state these "
                    "tests measure against cannot be restored: %s" % out.decode("utf-8", "replace"))
    for commit in out.decode("utf-8", "replace").split():
        for candidate in (commit, commit + "^"):
            if _git("cat-file", "-e", "%s:%s" % (candidate, _V1_MARKER))[0] == 0:
                return candidate
    pytest.fail("no commit in this repository still carries %s, so there is no real V1 state to "
                "migrate; these tests measure nothing without it." % _V1_MARKER)
    return None


def _restore_v1_templates(target):
    """Write the office kit's V1 project_memory templates, verbatim from history, into `target`."""
    commit = _last_v1_commit()
    code, out = _git("ls-tree", "--name-only", "-r", commit, _V1_TEMPLATE_DIR + "/")
    assert code == 0, out
    names = [line for line in out.decode("utf-8", "replace").split() if line]
    assert names, "the V1 template directory at %s is empty" % commit
    os.makedirs(target, exist_ok=True)
    for name in names:
        code, blob = _git("cat-file", "blob", "%s:%s" % (commit, name))
        assert code == 0, name
        with open(os.path.join(target, os.path.basename(name)), "wb") as handle:
            handle.write(blob)
    return names


# -- four weeks of operation, in the V1 schemas ----------------------------------------------------

_PROC_OWNERS = ("bookkeeper", "records-clerk", "office-manager", "content-writer")
_PROC_STATUSES = ("ACTIVE", "ACTIVE", "APPROVED", "PROPOSED", "RETIRED")


def _fixture_split(procs=16):
    """(ids the import writes to active/, ids it writes to archive/) for the fixture's procedures.

    DERIVED FROM THE RUNNING RULE, never counted by hand: `state.migration_archives` is the single
    judge `migrate` routes on, so this asks it rather than re-deriving its two halves. A test that
    hard-coded "13 and 3" would keep passing if the routing rule changed under it, which is the
    failure mode this file exists to avoid -- and it would have to be re-counted every time the
    fixture's status cycle moves.
    """
    active, archived = [], []
    for number in range(1, procs + 1):
        status = _PROC_STATUSES[number % len(_PROC_STATUSES)]
        target = archived if migration_archives("PROC", "PROC", status) else active
        target.append("PROC-%04d" % number)
    return active, archived


def _fill_v1(directory, procs=16, filed=920):
    """Fill the restored templates the way a running office project fills them.

    Only the payload is written; every kit header comment stays where the template put it. The two
    numbers are the ones the round's field reading reported (16 procedures, 920 filing-log
    entries), so the sizes the migration reports are the sizes a real project produces.
    """
    def replace_tail(name, marker, text):
        path = os.path.join(directory, name)
        body = io.open(path, encoding="utf-8").read()
        head, sep, _rest = body.partition(marker)
        assert sep, "%s no longer carries %r -- the V1 schema changed under this test" % (name,
                                                                                          marker)
        io.open(path, "w", encoding="utf-8", newline="\n").write(head + text)

    replace_tail("filing_plan.yaml", "tree: []", "tree:\n" + "".join(
        "  - path: archive/finance/node%02d/<year>/\n"
        "    doc_types: [invoice]\n"
        "    retention: \"8y\"\n" % n for n in range(7)))
    replace_tail("process_definitions.yaml", "processes: {}", "processes:\n" + "".join(
        "  PROC-%04d:\n"
        "    title: \"Process %d\"\n"
        "    trigger: \"inbox drop\"\n"
        "    owner: %s\n"
        "    steps:\n"
        "      - \"records-clerk files the document per filing_plan\"\n"
        "      - \"bookkeeper books via scripts/ledger_add.py\"\n"
        "    outputs: [\"archive/<path>\"]\n"
        "    approval_points: [\"new category needed\"]\n"
        "    exceptions: \"anything outside these steps returns as a question\"\n"
        "    status: %s\n"
        "    approved_hash: \"%064x\"\n"
        % (n, n, _PROC_OWNERS[n % len(_PROC_OWNERS)], _PROC_STATUSES[n % len(_PROC_STATUSES)], n)
        for n in range(1, procs + 1)))
    replace_tail("filing_log.yaml", "filed: []", "filed:\n" + "".join(
        "  - source: \"scan_%04d.pdf\"\n"
        "    target: \"archive/finance/node00/2026/2026-07-01_Party_invoice.pdf\"\n"
        "    date: \"2026-07-01\"\n"
        "    proc: PROC-%04d\n"
        "    doc_type: invoice\n" % (n, 1 + n % procs) for n in range(filed)))
    replace_tail("review_findings.yaml", "runs: []", "runs:\n" + "".join(
        "  - date: 2026-07-%02d\n"
        "    pass_fail: pass\n"
        "    findings: []\n" % (1 + n) for n in range(4)))


def _overlay_v2_templates(directory):
    """What the user's re-scaffold leaves behind: the V2 templates, copy-if-absent.

    Same contract as `init_project_memory` -- never clobber -- so the V1 files stay exactly as the
    project had them and the V2 skeleton appears beside them. That is the state `migrate` is run
    in, because the scaffold is the step BEFORE it (the entry point does not exist until then).
    """
    for current, _dirs, files in os.walk(_V2_TEMPLATE_DIR):
        for name in files:
            source = os.path.join(current, name)
            rel = os.path.relpath(source, _V2_TEMPLATE_DIR)
            target = os.path.join(directory, rel)
            if os.path.exists(target):
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(source, "rb") as src, open(target, "wb") as dst:
                dst.write(src.read())


@pytest.fixture
def v1_state(tmp_path):
    """A real V1 office state directory with a V2 skeleton overlaid -- what `migrate` meets."""
    root = str(tmp_path / "project_memory")
    _restore_v1_templates(root)
    _fill_v1(root)
    _overlay_v2_templates(root)
    return ProjectState(root)


def _snapshot(root):
    """{state-relative path: bytes} for the whole state directory -- the 'wrote nothing' witness."""
    seen = {}
    for current, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(current, name)
            with open(path, "rb") as handle:
                seen[os.path.relpath(path, root).replace(os.sep, "/")] = handle.read()
    return seen


def _run(state, *argv):
    """The CLI, through its own parser and `main` -- the surface a role reaches, not the module."""
    return cli.main(["--root", state.root] + list(argv))


def _archived_paths(state, item_type):
    """Every file under `archive/<type>/`, whatever year it was filed in."""
    base = os.path.join(state.root, "archive", item_type)
    found = []
    for current, _dirs, files in os.walk(base):
        found += [os.path.join(current, name) for name in sorted(files) if name.endswith(".yaml")]
    return sorted(found)


def _archived_items(state, item_type):
    return [yaml.safe_load(io.open(path, encoding="utf-8"))
            for path in _archived_paths(state, item_type)]


def _fill_acceptance_reports(state):
    """A V1 QA report store, in the shape a real project's own carries.

    MEASURED, AND IT REPLACES A FIXTURE THAT WAS INVENTED. The previous one filled the office kit's
    `product_catalog.yaml` with `PROD-nnnn` entries and said that was the shape the template's own
    header documents. It is not: that template ships `products: {}` and a single commented-out
    `PRD-A0001`, which does not match the V1 id shape at all, and `PROD` appeared nowhere in this
    repository except in the comments that claimed it and the fixtures built from them.

    What a real store of this kind looks like, read off the field copy of `synaipse` (2026-08-05):
    `acceptance_reports.yaml` holds 77 id-shaped mappings -- 17 reports keyed `ACC-nnnn` and 60
    criteria named `AC-<n>`, 31 of which carry `status: met`. Neither `ACC` nor `AC` is a type any
    contract in this harness knows, and BOTH id positions occur in it: some reports key their
    criteria in a mapping, others list them with an `id` field. That is the property every caller
    below measures, so the fixture carries both.
    """
    path = os.path.join(state.root, "acceptance_reports.yaml")
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        "acceptance_reports:\n"
        "  ACC-0001:\n"
        "    prd: PRD-0001\n"
        "    result: pass\n"
        "    acceptance_criteria:\n"
        "      AC-1:\n"
        "        text: \"the first criterion of the first report\"\n"
        "        status: met\n"
        "  ACC-0002:\n"
        "    prd: PRD-0002\n"
        "    result: pass\n"
        "    criteria:\n"
        "      - id: AC-1\n"
        "        text: \"the first criterion of the second report\"\n"
        "        status: met\n")
    return path


# -- the dry run --------------------------------------------------------------------------------


def test_the_dry_run_reads_a_real_v1_state_and_writes_nothing(v1_state, capsys):
    """The first half has to be useful alone AND has to be inert.

    Inert is the half a test can actually prove, and it is proved over the WHOLE state directory
    rather than over the files the command mentions: a dry run that quietly created a lock file, an
    index or a receipt would still print the same report.
    """
    before = _snapshot(v1_state.root)
    code = _run(v1_state, "migrate", "--dry-run")
    printed = capsys.readouterr().out
    assert _snapshot(v1_state.root) == before, "the dry run changed the state directory"
    # 1 = "there are findings", like `validate`: this state needs a field decision it cannot make.
    assert code == 1, printed
    assert "PROC-0001" in printed and "PROC-0016" in printed
    # the two documents with no V2 counterpart are NAMED rather than silently skipped
    assert "filing_log.yaml" in printed, "the untranslatable payload is not named"
    assert "review_findings.yaml" in printed


def test_the_dry_run_finds_every_v1_record_and_no_other(v1_state):
    """The record rule is a property, and this is the property being measured on real data.

    16 procedures are found because their KEYS are ids and they carry a `status`; the 920 filing-log
    entries and the four audit runs in the same directory are not, and neither is any V2 skeleton
    file. A rule that reached one file by name could not tell those apart.
    """
    plan = migrate.build_plan(v1_state)
    found = [entry for entry in plan["records"] if entry["legacy_type"] == "PROC"]
    assert len(found) == 16, [entry["legacy_id"] for entry in plan["records"]]
    assert {entry["source"] for entry in found} == {"process_definitions.yaml"}
    assert sorted(entry["legacy_id"] for entry in found)[0] == "PROC-0001"
    # the log is 920 entries and contributes no record at all
    log = yaml.safe_load(io.open(os.path.join(v1_state.root, "filing_log.yaml"),
                                 encoding="utf-8"))
    assert len(log["filed"]) == 920
    assert not [entry for entry in plan["records"] if entry["source"] == "filing_log.yaml"]


def test_a_field_the_two_contracts_spell_differently_is_a_decision_and_not_a_guess(v1_state,
                                                                                   capsys):
    """V1 PROCs carry `owner`; `REQUIRED_FIELDS["PROC"]` asks for `roles`.

    RED without the "same spelling or `--map`" rule in `_item_fields`: any similarity heuristic
    would import all sixteen silently, which is the quiet decision the command exists not to make.
    The dry run must instead refuse to run AND hand back the flag that settles it.
    """
    assert _run(v1_state, "migrate", "--dry-run") == 1
    printed = capsys.readouterr().out
    assert "WHAT IT WOULD IMPORT (0 record(s))" in printed
    # SR-0007: the flag is PROPOSED rather than left as a placeholder -- and the run is still
    # refused, which is the whole boundary ("ein Vorschlag ist keine Antwort").
    assert "--map PROC.roles=owner" in printed, printed
    assert "NOT applied" in printed, printed
    assert "owner" in printed, "the record's own keys are not offered to the reader"
    plan = migrate.build_plan(v1_state)
    assert not migrate.plan_is_executable(plan)
    # ...over the records the FIELD contract still applies to. A record bound for the archive is
    # exempt from it (DEC-0004) and is held up by its year instead, which the next test measures.
    assert {entry["verdict"] for entry in plan["records"]
            if entry.get("target") == "active"} == {"needs_decision"}
    # ...and the same state WITH the decision is executable
    decided = _planned(v1_state)
    assert migrate.plan_is_executable(decided)
    assert len(migrate._by_verdict(decided, "translatable")) == 16


def test_identical_decisions_collapse_to_one_line_but_different_ones_never_do(v1_state):
    """Sixteen records posing ONE question must not print sixteen lines; two questions must print
    two. The grouping key is what the answer depends on, so this is a property of the key."""
    plan = migrate.build_plan(v1_state)
    decisions = migrate._by_verdict(plan, "needs_decision")
    active, _archived = _fixture_split()
    assert len(decisions) == len(active)
    assert len(migrate._group_decisions(decisions)) == 1
    split = copy.deepcopy(decisions)
    split[0]["missing_fields"] = ["title"]
    assert len(migrate._group_decisions(split)) == 2


def test_the_ready_line_carries_the_flags_the_plan_was_built_with(v1_state):
    """BUG-0027: the READY line is a paste, and a paste that drops the build flags is a plan the
    reader never reviewed.

    `plan_digest` is over the WHOLE plan, and `--map`/`--archive-year` are two of `build_plan`'s
    inputs, so the copied `migrate --plan <digest>` had to carry them or the executing half rebuilds
    a different plan. This state needs BOTH flags (the sixteen PROCs spell `owner` where the
    contract asks `roles`, and the archive-bound ones need a year), so the printed line names both.

    RED without `_ready_command`/`_plan_flags`: the line reads `--plan <digest>` and nothing else,
    and pasting it answers rc 2 with a digest mismatch (measured) -- the run the reader read is not
    the run they would get.
    """
    plan = _planned(v1_state)
    printed = migrate.render(plan, v1_state)
    ready = [line for line in printed.splitlines() if line.startswith("READY:")]
    assert len(ready) == 1, printed
    command = re.findall(r"`([^`]+)`", ready[0])[0]
    assert "--map PROC.roles=owner" in command, command
    assert "--archive-year %d" % _ARCHIVE_YEAR in command, command
    # ...AND THE PASTE REALLY REPRODUCES THIS PLAN, run through the CLI the reader would use: without
    # the flags this is a digest mismatch (a usage error, no state touched); with them it executes.
    parts = command.split()
    assert parts[:3] == ["python", "scripts/harness.py", "migrate"], command
    assert _run(v1_state, *parts[2:]) == 0, command


# -- the executing half --------------------------------------------------------------------------


def _planned(state):
    """The plan the runs below execute -- the flags and the plan builder always in step."""
    return migrate.build_plan(state, {("PROC", "roles"): "owner"}, _ARCHIVE_YEAR)


def _migrated(state):
    """Run the whole two-step protocol the way a role does, and return the exit code."""
    return _run(state, "migrate", "--plan", migrate.plan_digest(_planned(state)),
                "--map", "PROC.roles=owner", "--archive-year", str(_ARCHIVE_YEAR))


def test_the_import_writes_typed_items_at_their_initial_status(v1_state):
    """Spec II.10: an imported item keeps its REGULAR INITIAL status and carries the import mark
    with a null approval_ref. RED if the V1 status were walked onto the automaton."""
    assert _migrated(v1_state) == 0
    items = [name for name, _path in v1_state.iter_active_items("PROC")]
    active, _archived = _fixture_split()
    assert len(items) == len(active), items
    active_in_v1 = v1_state.read_item("PROC-0001")
    assert active_in_v1["status"] == "DRAFT"
    assert active_in_v1["approval_ref"] is None
    assert active_in_v1[migrate.IMPORT_MARK] is True
    assert active_in_v1[migrate.LEGACY_FIELD]["legacy_status"] == "ACTIVE"
    assert active_in_v1[migrate.LEGACY_FIELD]["mapped_status"] == "ACTIVE"
    # carried VERBATIM: the V1 record's scalar `owner` arrives as a scalar `roles`, because no
    # contract in this kernel declares that field's shape and inventing one would be a guess
    record = active_in_v1[migrate.LEGACY_FIELD]["record"]
    assert active_in_v1["roles"] == record["owner"] and isinstance(active_in_v1["roles"], str)


def test_an_imported_item_holds_its_v1_record_as_an_independent_copy(v1_state):
    """RED when the item field and the legacy snapshot are the SAME object -- which is what the
    first cut of this module did, since both read straight out of the parsed V1 record.

    `yaml.safe_dump` then writes an ANCHOR and an ALIAS (measured in a real imported PROC:
    `steps: &id001` beside `steps: *id001`). The file stays valid YAML, and that is exactly why it
    is dangerous: on the way back in the two fields are ONE object again, so a later edit of
    `steps` through the kernel rewrites the legacy record that exists to say what V1 held.

    WHAT THIS DOES AND DOES NOT CATCH, stated because the round that wrote it measured it: the
    alias needs BOTH reads to hand out the same object, so either copy alone prevents it and
    removing either one alone leaves this test green. It catches the defect, not each half of the
    fix -- and a docstring claiming otherwise would be this kit's own rule broken in the test
    written to keep it.
    """
    assert _migrated(v1_state) == 0
    raw = io.open(v1_state.active_path("PROC-0001"), encoding="utf-8").read()
    assert "&id" not in raw and "*id" not in raw, raw
    item = yaml.safe_load(raw)
    item["steps"].append("a later edit through the kernel")
    assert "a later edit through the kernel" not in item[migrate.LEGACY_FIELD]["record"]["steps"]


def test_the_run_records_itself_as_an_item_naming_what_it_did_not_translate(v1_state):
    """The bookkeeping. A migration is a state change, and a state change with no item is a state
    change with no receipt -- so the run writes a `DEC`, and the things it left alone are IN it."""
    assert _migrated(v1_state) == 0
    receipts = [name for name, _path in v1_state.iter_active_items("DEC")]
    assert len(receipts) == 1, receipts
    receipt = v1_state.read_item(receipts[0])
    assert "process_definitions.yaml" in receipt["decision"]
    assert "PROC-0001 .. PROC-0016" in receipt["decision"]
    assert "PROC.roles=owner" in receipt["decision"]
    # the 920-entry log is neither imported nor dropped: it is inventoried, with its content hash
    assert "filing_log.yaml" in receipt["consequences"]
    assert "filing_log.yaml" in receipt["context"]
    on_disk = io.open(os.path.join(v1_state.root, "filing_log.yaml"), "rb").read()
    assert hashlib.sha256(on_disk).hexdigest() in receipt["context"]


def test_running_the_finished_migration_again_writes_nothing(v1_state):
    """Idempotency, and BOTH halves of it.

    The items half goes red without the `legacy_fields.legacy_id` scan (a second run would allocate
    PROC-0017..PROC-0032). The receipt half goes red without the empty-run guard in `execute`: a
    receipt for a run that imported nothing is a new `DEC` on every invocation, which would make
    re-running a finished migration change the state -- the property the command promises it has.
    """
    assert _migrated(v1_state) == 0
    after_first = _snapshot(v1_state.root)
    assert _migrated(v1_state) == 0
    after_second = _snapshot(v1_state.root)
    assert sorted(after_second) == sorted(after_first), (
        set(after_second) ^ set(after_first))
    active, _archived = _fixture_split()
    assert len([name for name, _p in v1_state.iter_active_items("PROC")]) == len(active)
    assert len([name for name, _p in v1_state.iter_active_items("DEC")]) == 1


def test_the_executing_run_refuses_a_plan_the_state_no_longer_matches(v1_state):
    """The digest is the only thing standing between "a human read this" and "a command ran".

    The file edited here is one the migration would never translate, which is the point: the plan
    was reviewed against a state, and the state moved. RED without the digest comparison in the
    CLI, and the run must write NOTHING -- not the items, not the receipt.
    """
    plan = _planned(v1_state)
    digest = migrate.plan_digest(plan)
    log = os.path.join(v1_state.root, "filing_log.yaml")
    io.open(log, "a", encoding="utf-8", newline="\n").write("# a later edit\n")
    before = _snapshot(v1_state.root)
    assert _run(v1_state, "migrate", "--plan", digest, "--map", "PROC.roles=owner",
                "--archive-year", str(_ARCHIVE_YEAR)) == 2
    assert _snapshot(v1_state.root) == before
    assert not os.path.isdir(os.path.join(v1_state.root, "procedures", "active",
                                          "PROC-0001.yaml"))


def test_the_digest_covers_the_flags_even_when_they_change_nothing_else(v1_state):
    """Changing `--map` changes the plan, so it must change the digest -- ISOLATED.

    The first cut of this test dropped `--map PROC.roles=owner`, which turns all sixteen records
    from `translatable` into `needs_decision`: the digest then differs over `records` and would
    have differed with `field_map` left out of it entirely. It could not fail for the reason it
    named. Here the extra flag names a type the state has no record of, so `records` and
    `carried_values` are provably identical and `field_map` is the only thing that moved.
    """
    plain = _planned(v1_state)
    flagged = migrate.build_plan(v1_state, {("PROC", "roles"): "owner",
                                            ("BUG", "title"): "headline"}, _ARCHIVE_YEAR)
    assert plain["records"] == flagged["records"]
    assert plain["carried_values"] == flagged["carried_values"]
    assert plain["state"] == flagged["state"]
    assert migrate.plan_digest(plain) != migrate.plan_digest(flagged), (
        "two runs that differ only in their --map flags digest the same, so the flags are outside "
        "the plan the human was shown")
    before = _snapshot(v1_state.root)
    assert _run(v1_state, "migrate", "--plan", migrate.plan_digest(plain),
                "--map", "PROC.roles=owner", "--map", "BUG.title=headline",
                "--archive-year", str(_ARCHIVE_YEAR)) == 2
    assert _snapshot(v1_state.root) == before


def test_the_digest_covers_a_hand_edited_item_not_only_the_documents(v1_state):
    """`state_fingerprint`, and the sentence it replaces.

    The digest used to be taken over the DOCUMENT inventory, so a hand-edited
    `procedures/active/PROC-0001.yaml` -- canonical state, the very thing a migration must be
    answerable to -- left it unchanged and the run went through on a plan that had never seen the
    edit, while two texts claimed it covered "every file under the state directory".
    """
    assert _migrated(v1_state) == 0
    plan = migrate.build_plan(v1_state)
    digest = migrate.plan_digest(plan)
    item = v1_state.read_item("PROC-0001")
    item["title"] = "edited by hand between the reading and the run"
    v1_state._write_yaml_atomic(v1_state.active_path("PROC-0001"), item)
    assert migrate.plan_digest(migrate.build_plan(v1_state)) != digest
    assert _run(v1_state, "migrate", "--plan", digest) == 2


def test_the_fingerprint_names_what_it_does_not_cover(v1_state):
    """The residual `state_fingerprint` states, measured so the sentence is answerable.

    A dotted path is machinery -- the lock, and `.audit/hook_events.jsonl`, which grows whenever
    any gate refuses anything. Including it would invalidate a plan because an unrelated hook
    fired, which is a refusal nobody can act on. The cost is that a file hidden under a dotted
    directory is invisible here, and that is what this measures rather than asserts in prose.
    """
    before = migrate.state_fingerprint(v1_state)
    os.makedirs(os.path.join(v1_state.root, ".audit"), exist_ok=True)
    io.open(os.path.join(v1_state.root, ".audit", "hook_events.jsonl"), "a",
            encoding="utf-8", newline="\n").write('{"hook": "gate_git"}\n')
    assert migrate.state_fingerprint(v1_state) == before
    # ...while anything NOT under a dotted path is covered, including staging/
    os.makedirs(os.path.join(v1_state.root, "staging", "PROC-0001"), exist_ok=True)
    io.open(os.path.join(v1_state.root, "staging", "PROC-0001", "note.md"), "w",
            encoding="utf-8", newline="\n").write("a proposal\n")
    assert migrate.state_fingerprint(v1_state) != before


def test_a_document_that_does_not_parse_refuses_the_run(v1_state):
    """An unreadable document is not a document known to hold no records.

    RED without `unreadable` in `plan_is_executable`: the run would import whatever it could read
    and say nothing about the file it could not, which is the silence this command may not produce.
    """
    io.open(os.path.join(v1_state.root, "broken.yaml"), "w", encoding="utf-8",
            newline="\n").write("processes:\n  PROC-0001: {\n")
    plan = _planned(v1_state)
    assert plan["unreadable"] and plan["unreadable"][0][0] == "broken.yaml", plan["unreadable"]
    assert not migrate.plan_is_executable(plan)
    before = _snapshot(v1_state.root)
    assert _run(v1_state, "migrate", "--plan", migrate.plan_digest(plan),
                "--map", "PROC.roles=owner",
                "--archive-year", str(_ARCHIVE_YEAR)) == 1
    assert _snapshot(v1_state.root) == before


def test_a_non_yaml_document_is_reported_as_unsearched_rather_than_skipped(v1_state, capsys):
    """"Found no records" and "did not look for records" are different answers.

    The state directory's `README.md` is the standing example; only one of the two readings is a
    fact about the file, so the dry run says which one it is.
    """
    plan = migrate.build_plan(v1_state)
    assert any("README.md" in note for note in plan["unscanned"]), plan["unscanned"]
    _run(v1_state, "migrate", "--dry-run")
    assert "NOT SEARCHED" in capsys.readouterr().out


def test_the_map_flag_refuses_a_type_and_a_field_the_kernel_does_not_have(v1_state):
    """Both halves of `parse_field_map`'s contract, because a flag that is accepted and then does
    nothing is worse than one that is refused: it would silently leave the field unmapped and the
    record classified `needs_decision` with the human believing they had answered."""
    with pytest.raises(migrate.MigrationError) as unknown_type:
        migrate.parse_field_map(["NOPE.roles=owner"])
    assert "does not capture" in str(unknown_type.value)
    with pytest.raises(migrate.MigrationError) as unknown_field:
        migrate.parse_field_map(["PROC.invented=owner"])
    assert "not in that type's contract" in str(unknown_field.value)
    # ...and a well-formed one is accepted, so the refusals above are not simply "everything fails"
    assert migrate.parse_field_map(["PROC.roles=owner"]) == {("PROC", "roles"): "owner"}


# -- the two refusals ----------------------------------------------------------------------------


def test_a_status_the_spec_table_does_not_know_blocks_the_whole_run(v1_state):
    """Spec II.10: unknown values BLOCK, never get guessed.

    Wholesale, and that is the conservative reading being measured: fifteen of the sixteen records
    are perfectly translatable and none of them is written either, because a plan with a blocker in
    it is not a plan somebody approved half of. RED without the `UnknownV1Status` branch.
    """
    path = os.path.join(v1_state.root, "process_definitions.yaml")
    body = io.open(path, encoding="utf-8").read().replace("status: RETIRED", "status: PAUSED", 1)
    io.open(path, "w", encoding="utf-8", newline="\n").write(body)
    plan = _planned(v1_state)
    blocked = migrate._by_verdict(plan, "blocked")
    assert len(blocked) == 1 and "PAUSED" in blocked[0]["reason"], plan["records"]
    assert len(migrate._by_verdict(plan, "translatable")) == 15
    before = _snapshot(v1_state.root)
    assert _run(v1_state, "migrate", "--plan", migrate.plan_digest(plan),
                "--map", "PROC.roles=owner",
                "--archive-year", str(_ARCHIVE_YEAR)) == 1
    assert _snapshot(v1_state.root) == before


def test_a_record_too_large_for_one_item_blocks_instead_of_being_written(v1_state):
    """A V1 record that inlines its detail would become an item spec II.5 caps and `validate`
    reports as an error -- written by the one command whose job is to leave the state sound.

    RED without `_too_large`: `capture` does not check the budget, so the oversized item lands and
    only the validator complains, about a file no editing route can shrink.
    """
    path = os.path.join(v1_state.root, "process_definitions.yaml")
    body = io.open(path, encoding="utf-8").read().replace(
        '      - "bookkeeper books via scripts/ledger_add.py"\n',
        '      - "bookkeeper books via scripts/ledger_add.py"\n'
        + "".join('      - "inlined detail line %d"\n' % n for n in range(400)), 1)
    io.open(path, "w", encoding="utf-8", newline="\n").write(body)
    plan = _planned(v1_state)
    blocked = migrate._by_verdict(plan, "blocked")
    assert len(blocked) == 1, [(e["legacy_id"], e["verdict"]) for e in plan["records"]]
    assert "spec II.5" in blocked[0]["reason"]
    assert not migrate.plan_is_executable(plan)


def test_a_record_the_writer_would_refuse_never_reaches_the_writer(v1_state):
    """B1: the plan asks `capture_preflight`, the same check `capture` runs before it writes.

    The subject is not hypothetical and not office-specific: EVERY record of a V1
    `system_requirements.yaml` and every V1 `tasks.yaml` names its parent as `PRD-nnnn`, `PRD` is
    no V2 type, and `_assert_origins_resolve` refuses it -- at WRITE time. Measured before this:
    the plan said READY, items landed, the run died in the middle, and there was no receipt.

    Written here in the V1 SR schema rather than mocked, because what makes this a defect is that
    the shape is the normal one.
    """
    io.open(os.path.join(v1_state.root, "system_requirements.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "requirements:\n"
        + "".join("  SR-%04d:\n"
                  "    title: \"Requirement %d\"\n"
                  "    derives_from: PRD-0001\n"
                  "    contract: \"the service answers within 200 ms\"\n"
                  "    affected_components: [api]\n"
                  "    status: DRAFT\n" % (n, n) for n in range(1, 5)))
    plan = _planned(v1_state)
    blocked = [e for e in migrate._by_verdict(plan, "blocked") if e["legacy_type"] == "SR"]
    assert len(blocked) == 4, [(e["legacy_id"], e["verdict"]) for e in plan["records"]]
    assert "PRD-0001" in blocked[0]["reason"], blocked[0]["reason"]
    assert not migrate.plan_is_executable(plan)
    before = _snapshot(v1_state.root)
    assert _run(v1_state, "migrate", "--plan", migrate.plan_digest(plan),
                "--map", "PROC.roles=owner",
                "--archive-year", str(_ARCHIVE_YEAR)) == 1
    assert _snapshot(v1_state.root) == before, "a refused plan still wrote something"


def test_a_run_that_dies_halfway_still_names_and_records_what_it_wrote(v1_state, monkeypatch):
    """B1's other half: what no reading can rule out must not end in a silent partial state.

    `capture_preflight` removes the causes a plan can see; a lock, a disk or an interrupt it
    cannot. So `capture` is made to fail on the fourth item and the run must (a) refuse, (b) name
    the ids it did write, and (c) leave a `DEC` for them. Idempotency then makes a re-run finish
    the job, which is what the module offers instead of a transaction.
    """
    real_capture = ProjectState.capture
    state_of = {"n": 0}

    def failing_capture(self, item_type, fields, **through):
        # `**through` and not a fixed signature: the door grew `imported=` when the goal-size
        # exemption was bound to the PATH (TSK-0146 rework, F1), and a stub that pins today's
        # parameters turns the next one into a TypeError in a test about something else.
        if item_type == "PROC":
            state_of["n"] += 1
            if state_of["n"] == 4:
                raise OSError("the disk went away")
        return real_capture(self, item_type, fields, **through)

    monkeypatch.setattr(ProjectState, "capture", failing_capture)
    plan = _planned(v1_state)
    with pytest.raises(migrate.MigrationError) as refusal:
        migrate.execute(v1_state, plan, migrate.plan_digest(plan))
    message = str(refusal.value)
    assert "the disk went away" in message
    written = [name for name, _p in v1_state.iter_active_items("PROC")]
    assert len(written) == 3, written
    for item_id in written:
        assert item_id in message, (
            "the refusal does not name what it wrote:\n%s" % message)
    receipts = [name for name, _p in v1_state.iter_active_items("DEC")]
    assert len(receipts) == 1, "a half-finished run left no receipt"
    receipt = v1_state.read_item(receipts[0])
    assert "THE RUN DID NOT FINISH" in receipt["decision"]
    assert receipts[0] in message

    # ...and a re-run finishes it, because the three are recognised by their legacy id
    monkeypatch.setattr(ProjectState, "capture", real_capture)
    assert _migrated(v1_state) == 0
    active, _archived = _fixture_split()
    assert len([name for name, _p in v1_state.iter_active_items("PROC")]) == len(active)


def test_a_run_that_dies_with_a_long_message_still_leaves_a_receipt_that_fits(v1_state,
                                                                             monkeypatch):
    """R-4: the failure message is the third part of the receipt that grows with the input.

    Its size belongs to whatever raised -- an `OSError` naming a path per item is enough -- and it
    had no short form at all, so the one shape of receipt that says THE STATE IS HALF WRITTEN was
    the one that could fail to be written. The check is the validator's own verdict rather than a
    byte count typed here, and the sentence that matters has to survive the shortening: what is
    dropped is the failure TEXT, and the refusal on the command line still carries that verbatim.
    """
    from kernel import report
    novel = "the disk went away: " + "x" * (report.ITEM_MAX_BYTES * 2)
    real_capture = ProjectState.capture
    seen = {"n": 0}

    def failing_capture(self, item_type, fields, **through):
        # `**through` and not a fixed signature: the door grew `imported=` when the goal-size
        # exemption was bound to the PATH (TSK-0146 rework, F1), and a stub that pins today's
        # parameters turns the next one into a TypeError in a test about something else.
        if item_type == "PROC":
            seen["n"] += 1
            if seen["n"] == 4:
                raise OSError(novel)
        return real_capture(self, item_type, fields, **through)

    monkeypatch.setattr(ProjectState, "capture", failing_capture)
    plan = _planned(v1_state)
    with pytest.raises(migrate.MigrationError) as refusal:
        migrate.execute(v1_state, plan, migrate.plan_digest(plan))
    assert novel in str(refusal.value), "the refusal itself dropped what stopped the run"
    # A HALF-FINISHED RUN LEAVES ITS SOURCE WHERE IT IS (SR-0005), so the validator's ONE finding
    # is SR-0001's: the store is still in the project beside the items that came out of it. That is
    # the state this test is about, and anything else in the list would be a real defect.
    findings = findings_beside_the_receipts_carrier(v1_state)
    assert [finding["item"] for finding in findings] == ["process_definitions.yaml"], findings
    receipts = [name for name, _p in v1_state.iter_active_items("DEC")]
    assert len(receipts) == 1, "a half-finished run left no receipt"
    receipt = v1_state.read_item(receipts[0])
    assert "THE RUN DID NOT FINISH" in receipt["decision"]
    assert novel not in receipt["decision"]
    assert "does not fit in one item" in receipt["decision"]


def test_the_receipt_fits_in_one_item_however_many_documents_were_carried(v1_state):
    """B2: BOTH growing halves are shortened, and the short form does not point at a list it
    dropped.

    Measured before this with 310 carried documents: 21 316 B, `validate` exit 1, and
    `consequences` alone 20 070 characters -- while the docstring claimed the item always fits.
    The check is the validator's own verdict, not a byte count copied into this file.
    """
    for n in range(310):
        io.open(os.path.join(v1_state.root, "carried_%03d.txt" % n), "w", encoding="utf-8",
                newline="\n").write("a business document with a long enough name to matter\n")
    # the COUNT comes from the plan, not from this file: the fixture ships documents of its own,
    # and it is taken BEFORE the run because the one source it reads is absorbed and moved out of
    # the document set by it (SR-0005)
    carried = len(migrate.build_plan(v1_state)["documents"]) - 1   # minus the one source it read
    assert _migrated(v1_state) == 0
    findings = findings_beside_the_receipts_carrier(v1_state)
    assert not findings, findings
    receipt = v1_state.read_item("DEC-0001")
    assert "does not fit in one item" in receipt["context"]
    assert "hashes in `context` above" not in receipt["consequences"], (
        "the short receipt points at hashes the fallback removed")
    assert "%d document(s) were carried" % carried in receipt["consequences"], (
        receipt["consequences"])


def test_two_records_with_one_legacy_id_are_refused_rather_than_merged(v1_state):
    """B3: the last one used to win, and the item that landed had never existed in V1.

    Both V1 shapes in one document -- an id-keyed mapping and a list member carrying `id` -- which
    is exactly the pair `scan_document`'s own docstring says V1 used. The refusal is required
    rather than a preference: two items claiming one `legacy_fields.legacy_id` would break the
    idempotency scan, which is the only thing that makes a re-run safe.
    """
    io.open(os.path.join(v1_state.root, "twins.yaml"), "w", encoding="utf-8", newline="\n").write(
        "processes:\n"
        "  PROC-0900:\n"
        "    title: \"the keyed one\"\n"
        "    owner: bookkeeper\n"
        "    steps: [\"a\"]\n"
        "    status: ACTIVE\n"
        "extra:\n"
        "  - id: PROC-0900\n"
        "    title: \"the listed one\"\n"
        "    owner: records-clerk\n"
        "    steps: [\"b\"]\n"
        "    status: ACTIVE\n")
    plan = _planned(v1_state)
    twins = [e for e in plan["records"] if e["source"] == "twins.yaml"]
    assert len(twins) == 2, twins
    assert {e["verdict"] for e in twins} == {"blocked"}
    assert "appears 2 times" in twins[0]["reason"]
    assert {e["ordinal"] for e in twins} == {0, 1}, "the two records are not told apart at all"
    assert not migrate.plan_is_executable(plan)


def test_a_known_legacy_id_under_a_new_path_is_a_finding_and_not_a_second_import(v1_state):
    """R-5: the idempotency key is the legacy ID, and it was the pair (source document, id).

    Measured before this: after a completed migration, RENAMING the V1 document was enough to make
    every one of its records unseen again -- the same sixteen procedures planned as new imports and
    a second run wrote sixteen more items. The third bolt of DEC-0004 held for each ITEM (nothing
    moves an archived one back), while the RECORD was reactivatable with a `mv`.

    A rename and a copy are the same thing to this command, so it decides neither: a known id under
    a path it was not imported from is a finding that names both paths and the item that holds it.
    Both directions are in one run -- the SAME path is still recognised and still writes nothing,
    or this would be a rule that refuses re-runs.

    THE ROUTE IS A COPY OUT OF `legacy/` NOW, and that is SR-0005 having removed the cheaper one:
    a fully absorbed store is moved out of the project by the run itself, so there is no longer a
    V1 document lying in the state directory to rename. The defect this test is about is not gone
    with it -- anybody can copy the file back under another name -- so the measurement moves to the
    route that still exists.
    """
    assert _migrated(v1_state) == 0
    after_first = _snapshot(v1_state.root)
    imported = {name for name, _p in v1_state.iter_active_items("PROC")}
    assert imported, "nothing was imported, so the copy below measures nothing"
    retired = os.path.join(v1_state.root, "legacy", "process_definitions.yaml")
    assert os.path.exists(retired), sorted(after_first)
    shutil.copyfile(retired, os.path.join(v1_state.root, "procs_2025.yaml"))
    plan = _planned(v1_state)
    renamed = [e for e in plan["records"] if e["source"] == "procs_2025.yaml"]
    assert renamed, plan["records"]
    assert {e["verdict"] for e in renamed} == {"blocked"}, renamed
    assert not migrate.plan_is_executable(plan)
    reason = renamed[0]["reason"]
    assert "process_definitions.yaml" in reason and "procs_2025.yaml" in reason, reason
    assert renamed[0]["legacy_id"] in reason
    # the run refuses wholesale and the state is exactly what the first run left, plus the copy
    assert _run(v1_state, "migrate", "--plan", migrate.plan_digest(plan),
                "--map", "PROC.roles=owner", "--archive-year", str(_ARCHIVE_YEAR)) == 1
    copied = dict(after_first)
    copied["procs_2025.yaml"] = copied["legacy/process_definitions.yaml"]
    assert _snapshot(v1_state.root) == copied
    # ...and the counter-direction: take the copy away and a re-run is still the no-op it was
    os.remove(os.path.join(v1_state.root, "procs_2025.yaml"))
    assert _migrated(v1_state) == 0
    assert _snapshot(v1_state.root) == after_first
    assert {name for name, _p in v1_state.iter_active_items("PROC")} == imported


def test_two_documents_claiming_one_legacy_id_are_refused_like_two_in_one_document(v1_state):
    """The same rule one step earlier: a plan may not create what a re-run would refuse.

    R-5 makes a known legacy id under a new path a finding, so a RUN that wrote two items for one
    id would leave a state the next dry run cannot make sense of -- and the collision rule was
    per DOCUMENT, so two files each holding `PROC-0900` sailed past it. Refused for both records
    rather than for the later one: which document a directory walk reaches first is not a thing a
    verdict may depend on.
    """
    for name in ("here.yaml", "there.yaml"):
        io.open(os.path.join(v1_state.root, name), "w", encoding="utf-8", newline="\n").write(
            "processes:\n"
            "  PROC-0900:\n"
            "    title: \"the %s one\"\n    owner: bookkeeper\n    steps: [\"a\"]\n"
            "    status: ACTIVE\n" % name)
    plan = _planned(v1_state)
    claimed = [e for e in plan["records"] if e["legacy_id"] == "PROC-0900"]
    assert len(claimed) == 2, claimed
    assert {e["verdict"] for e in claimed} == {"blocked"}, claimed
    assert {e["source"] for e in claimed} == {"here.yaml", "there.yaml"}
    for entry in claimed:
        assert "here.yaml" in entry["reason"] and "there.yaml" in entry["reason"], entry["reason"]
    assert not migrate.plan_is_executable(plan)


def test_an_id_keyed_note_beside_the_real_record_is_not_a_second_claim_on_the_id(v1_state):
    """The counter-direction of the rule above, and the branch it nearly ran over.

    A mapping keyed by an id and carrying NO status is a cross-reference table -- `not_an_item`,
    reported and never a blocker, because a document a project cannot change must not become a
    migration it can never run. Counting such a note as a claimant puts that same document one
    branch EARLIER, as a duplicate id, and blocks the whole run over a table of notes. Measured
    with a note on `PROC-0001`, which the fixture's own `process_definitions.yaml` really holds.
    """
    io.open(os.path.join(v1_state.root, "notes.yaml"), "w", encoding="utf-8", newline="\n").write(
        "cross_reference:\n"
        "  PROC-0001:\n"
        "    note: \"filed under finance\"\n")
    plan = _planned(v1_state)
    note = [e for e in plan["records"] if e["source"] == "notes.yaml"]
    assert len(note) == 1 and note[0]["verdict"] == "not_an_item", note
    real = [e for e in plan["records"] if e["source"] == "process_definitions.yaml"
            and e["legacy_id"] == "PROC-0001"]
    assert len(real) == 1 and real[0]["verdict"] == "translatable", real
    assert migrate.plan_is_executable(plan)
    assert _migrated(v1_state) == 0


def test_an_id_shaped_record_of_an_unknown_type_is_reported_and_does_not_block(v1_state):
    """R3: an unknown TYPE is not a backlog record; an unknown STATUS of a KNOWN type is.

    A dev project's `acceptance_reports.yaml` keys its criteria `AC-<n>` with a `status` (measured;
    see `_fill_acceptance_reports`), and the first cut blocked the entire migration of such a
    project -- with a remedy ("extend the mapping table") pointing into the enforcement layer,
    which `guard_harness_selfmod` refuses. Both directions are measured in one run so the split
    cannot collapse to either side.
    """
    io.open(os.path.join(v1_state.root, "criteria.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "criteria:\n"
        "  AC-7:\n"
        "    text: \"the token stream arrives\"\n"
        "    status: met\n")
    path = os.path.join(v1_state.root, "process_definitions.yaml")
    # read FIRST: `open(path, "w")` truncates, so a read nested in the write call reads an empty
    # file and the substitution silently does nothing
    intact = io.open(path, encoding="utf-8").read()
    assert "status: RETIRED" in intact
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        intact.replace("status: RETIRED", "status: PAUSED", 1))

    plan = _planned(v1_state)
    criteria = [e for e in plan["records"] if e["source"] == "criteria.yaml"]
    assert len(criteria) == 1 and criteria[0]["verdict"] == "not_an_item", criteria
    # WHY it is not an item is asked of the kernel's own two maps rather than of the sentence: a
    # type in neither `REQUIRED_FIELDS` nor the mapping table is a record of some other kind. The
    # reason has to NAME the type, so a reader can see which record was passed over.
    assert "AC" not in migrate.REQUIRED_FIELDS and "AC" not in migrate.v1_types()
    assert "AC" in criteria[0]["reason"], criteria[0]["reason"]
    blocked = migrate._by_verdict(plan, "blocked")
    assert [e["legacy_type"] for e in blocked] == ["PROC"], blocked
    assert "PAUSED" in blocked[0]["reason"]
    # ...and with the known type's status corrected, the criteria alone do not block anything
    io.open(path, "w", encoding="utf-8", newline="\n").write(intact)
    assert migrate.plan_is_executable(_planned(v1_state))


def test_a_record_nested_inside_another_record_is_reported(v1_state):
    """R1: the walk does not stop at a hit, and it has no depth limit.

    Measured before this: a `PROC-0101` with an unknown status sitting INSIDE `PROC-0100` appeared
    under no heading of the dry run at all -- not imported, not blocked, not reported -- while the
    module promised an unknown status blocks. Silence about something id-shaped is the one outcome
    this command may not produce.
    """
    io.open(os.path.join(v1_state.root, "nested.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "processes:\n"
        "  PROC-0100:\n"
        "    title: \"the outer one\"\n"
        "    owner: bookkeeper\n"
        "    steps: [\"a\"]\n"
        "    status: ACTIVE\n"
        "    superseded:\n"
        "      PROC-0101:\n"
        "        title: \"the inner one\"\n"
        "        owner: bookkeeper\n"
        "        steps: [\"b\"]\n"
        "        status: PAUSED\n")
    plan = _planned(v1_state)
    found = {e["legacy_id"]: e["verdict"] for e in plan["records"] if e["source"] == "nested.yaml"}
    assert found == {"PROC-0100": "translatable", "PROC-0101": "blocked"}, found
    assert not migrate.plan_is_executable(plan)


def test_the_receipt_fits_however_many_source_documents_were_translated(v1_state):
    """B2': the fix for B2 shortened two growing parts and left a third.

    `decision` carries one line per SOURCE DOCUMENT and had no short form at all, so a project
    whose V1 records live in many files blew the budget through the very field that says what the
    run did -- measured with 300 such files: 17 285 B / 204 lines, `validate` exit 1, while the
    fallback had already fired on the other two.

    The count comes from `report`'s own line limit rather than from a number typed here: one line
    per source, so anything past the limit cannot fit however short the other parts are.
    """
    from kernel import report
    sources = report.ITEM_MAX_LINES + 20
    for n in range(sources):
        io.open(os.path.join(v1_state.root, "store_%03d.yaml" % n), "w", encoding="utf-8",
                newline="\n").write(
            "processes:\n"
            "  PROC-%04d:\n"
            "    title: \"Process %d\"\n"
            "    owner: bookkeeper\n"
            "    steps: [\"a\"]\n"
            "    status: ACTIVE\n" % (500 + n, n))
    assert _migrated(v1_state) == 0
    findings = findings_beside_the_receipts_carrier(v1_state)
    assert not findings, findings
    receipts = [v1_state.read_item(name) for name, _p in v1_state.iter_active_items("DEC")]
    receipt = [item for item in receipts if migrate.LEGACY_FIELD not in item]
    assert len(receipt) == 1, [item["id"] for item in receipts]
    assert "per-source breakdown does not fit" in receipt[0]["decision"], receipt[0]["decision"]
    # ...and it still says how many records it wrote and which flags it was given: the short form
    # drops the LIST, not the answer
    assert "%d source document(s)" % (sources + 1) in receipt[0]["decision"]
    assert "PROC.roles=owner" in receipt[0]["decision"]
    # R-4: AND IT POINTS AT NOTHING THAT DOES NOT HOLD WHAT IT DROPPED. The short form sent the
    # reader to `generated/index.yaml` for the per-item breakdown -- and that index is regenerated
    # from the ACTIVE items only, so every record this run ARCHIVED is in none of it. Measured as
    # the property rather than as a forbidden string: whatever route the receipt names has to hold
    # every id the run created, so the day the index does cover the archive this stops complaining
    # about it instead of having to be remembered.
    index = yaml.safe_load(io.open(os.path.join(v1_state.root, "generated", "index.yaml"),
                                   encoding="utf-8"))
    indexed = {row.get("id") for row in index["items"]}
    imported = set()
    for current, _dirs, files in os.walk(v1_state.root):
        for name in sorted(files):
            if not name.endswith(".yaml"):
                continue
            item = yaml.safe_load(io.open(os.path.join(current, name), encoding="utf-8"))
            if isinstance(item, dict) and item.get(migrate.LEGACY_FIELD):
                imported.add(item["id"])
    assert imported - indexed, (
        "every imported item is in the index, so this measures nothing -- the fixture archived "
        "none of them")
    if not imported <= indexed:
        assert "generated/index.yaml" not in receipt[0]["decision"], (
            "the short receipt sends the reader to the index for items that are not in it: %s"
            % sorted(imported - indexed))


# -- B6: a V1 parent chain, and the two directions the fix must not shoot through ------------------


def _chain_document(v1_state, name="chain.yaml", child_parent="PROC-0001"):
    """Two V1 procedures, the second derived from the first -- the normal shape of a V1 store."""
    io.open(os.path.join(v1_state.root, name), "w", encoding="utf-8", newline="\n").write(
        "processes:\n"
        "  PROC-0201:\n"
        "    title: \"the parent\"\n"
        "    owner: bookkeeper\n"
        "    steps: [\"a\"]\n"
        "    status: ACTIVE\n"
        "  PROC-0202:\n"
        "    title: \"the child\"\n"
        "    owner: bookkeeper\n"
        "    steps: [\"b\"]\n"
        "    derives_from: %s\n"
        "    status: ACTIVE\n" % child_parent)


def test_a_v1_parent_chain_migrates_and_the_child_points_at_the_id_the_parent_got(v1_state):
    """B6: the plan asked the writer about the state BEFORE the run, so no chain could ever move.

    Measured before this: `PROC-0201` importable, `PROC-0202 derives_from PROC-0201` blocked
    ("does not exist"), `plan_is_executable` False, the run refused wholesale -- so the parent was
    never written and the next dry run said exactly the same thing. A stationary state, over a
    shape every V1 store has.

    The second half is what makes the fix correct rather than merely permissive: V2 ALLOCATES ids,
    the office fixture already holds sixteen procedures, so the V1 `PROC-0201` does not become
    `PROC-0201`. The child must end up pointing at the id its parent actually got -- carrying the
    V1 value over verbatim would bind it to a different procedure that happens to have that number.
    """
    _chain_document(v1_state, child_parent="PROC-0201")
    plan = _planned(v1_state)
    chain = {entry["legacy_id"]: entry for entry in plan["records"]
             if entry["source"] == "chain.yaml"}
    assert {key: entry["verdict"] for key, entry in chain.items()} == {
        "PROC-0201": "translatable", "PROC-0202": "translatable"}, chain
    assert chain["PROC-0202"]["rebound_fields"] == ["derives_from"]
    assert chain["PROC-0202"]["write_order"] > chain["PROC-0201"]["write_order"], (
        "the child is not ordered after the parent, so the run would write it first")
    assert _migrated(v1_state) == 0

    def imported(legacy_id):
        for name, path in v1_state.iter_active_items("PROC"):
            item = yaml.safe_load(io.open(path, encoding="utf-8"))
            if item.get(migrate.LEGACY_FIELD, {}).get("legacy_id") == legacy_id:
                return item
        raise AssertionError("%s was not imported" % legacy_id)

    parent, child = imported("PROC-0201"), imported("PROC-0202")
    assert parent["id"] != "PROC-0201", (
        "the fixture no longer reallocates the id, so this test cannot tell a rewritten binding "
        "from a copied one")
    assert child["derives_from"] == parent["id"], child["derives_from"]
    # ...and the V1 value is not lost, it is where every other V1 value is
    assert child[migrate.LEGACY_FIELD]["record"]["derives_from"] == "PROC-0201"


def test_a_binding_whose_target_this_run_does_not_create_still_blocks(v1_state):
    """The counter-direction of B6, and the reason the fix is not simply "trust every binding".

    `PROC-0900` is in no document and in no store. Handing the preflight the ids the plan PROMISES
    must not turn into handing it every id it is shown -- so this record is refused by the same
    check as before, while the chain in the test above goes through in the same fixture.
    """
    _chain_document(v1_state, child_parent="PROC-0900")
    plan = _planned(v1_state)
    child = [entry for entry in plan["records"] if entry["legacy_id"] == "PROC-0202"]
    assert len(child) == 1 and child[0]["verdict"] == "blocked", child
    assert "PROC-0900" in child[0]["reason"], child[0]["reason"]
    assert not migrate.plan_is_executable(plan)
    before = _snapshot(v1_state.root)
    assert _run(v1_state, "migrate", "--plan", migrate.plan_digest(plan),
                "--map", "PROC.roles=owner", "--archive-year", str(_ARCHIVE_YEAR)) == 1
    assert _snapshot(v1_state.root) == before


def test_two_records_that_bind_to_each_other_are_refused_rather_than_ordered(v1_state):
    """The other counter-direction: A derives from B and B from A.

    Both targets are in the plan, so the "does it resolve" question answers yes for both -- and
    there is still no order that writes a parent before its child. Without the cycle refusal the
    run would either loop or write one of them against an unresolved parent, so the plan says no.
    """
    io.open(os.path.join(v1_state.root, "cycle.yaml"), "w", encoding="utf-8", newline="\n").write(
        "processes:\n"
        "  PROC-0301:\n"
        "    title: \"A\"\n    owner: bookkeeper\n    steps: [\"a\"]\n"
        "    derives_from: PROC-0302\n    status: ACTIVE\n"
        "  PROC-0302:\n"
        "    title: \"B\"\n    owner: bookkeeper\n    steps: [\"b\"]\n"
        "    derives_from: PROC-0301\n    status: ACTIVE\n"
        # ...and the degenerate case, which the first cut of the fix let through: a record that
        # names ITSELF settles at depth 1 if the self-edge is skipped, so the plan promises it and
        # the run then dies at write time on an id that does not exist yet.
        "  PROC-0303:\n"
        "    title: \"its own parent\"\n    owner: bookkeeper\n    steps: [\"c\"]\n"
        "    derives_from: PROC-0303\n    status: ACTIVE\n")
    plan = _planned(v1_state)
    cycle = {entry["legacy_id"]: entry for entry in plan["records"]
             if entry["source"] == "cycle.yaml"}
    assert {key: entry["verdict"] for key, entry in cycle.items()} == {
        "PROC-0301": "blocked", "PROC-0302": "blocked", "PROC-0303": "blocked"}, cycle
    assert "cycle" in cycle["PROC-0301"]["reason"]
    assert not migrate.plan_is_executable(plan)
    before = _snapshot(v1_state.root)
    assert _run(v1_state, "migrate", "--plan", migrate.plan_digest(plan),
                "--map", "PROC.roles=owner", "--archive-year", str(_ARCHIVE_YEAR)) == 1
    assert _snapshot(v1_state.root) == before


# -- SR-0004 / DEC-0004: a finished record goes to the archive, exempt from the field contract -----


def test_a_record_finished_in_v1_is_written_to_the_archive_and_not_to_active(v1_state):
    """SR-0004: 260 of 264 tasks in the measured field project are DONE.

    Writing all of them into `tasks/active/` buries the four that are alive, so a record spec
    II.10's table marks as finished lands under `archive/<type>/<year>/` at its mapped status. RED
    without the routing: every RETIRED procedure would sit in `procedures/active/` at DRAFT, which
    says the opposite of what V1 recorded. (That the TASK rows the sentence above is about really
    are among them is the neighbouring
    `test_a_v1_task_that_is_done_is_archived_at_done_and_not_reopened_as_a_draft`; this one
    measures the fixture's own procedures.)
    """
    active, archived = _fixture_split()
    assert archived, "the fixture holds no finished procedure, so this measures nothing"
    assert _migrated(v1_state) == 0
    in_active = {name for name, _p in v1_state.iter_active_items("PROC")}
    assert len(in_active) == len(active)
    year_dir = os.path.join(v1_state.root, "archive", "PROC", str(_ARCHIVE_YEAR))
    filed = sorted(os.listdir(year_dir))
    assert len(filed) == len(archived), filed
    item = yaml.safe_load(io.open(os.path.join(year_dir, filed[0]), encoding="utf-8"))
    assert item[migrate.LEGACY_FIELD]["legacy_status"] == "RETIRED"
    assert item["status"] == "RETIRED", "the archived item does not carry its own end state"
    assert item["id"] not in in_active
    assert item[migrate.LEGACY_FIELD]["written_to"] == "archive"
    # it is still an unconfirmed import: no approval was minted for it
    assert item["approval_ref"] is None and item[migrate.IMPORT_MARK] is True


def test_the_archive_path_takes_a_record_the_field_contract_would_refuse(v1_state):
    """DEC-0004 and its three bolts, each measured rather than described.

    A V1 task is missing ten of `REQUIRED_FIELDS["TSK"]`'s eleven fields. The exemption lets such a
    record become findable history; the bolts keep it from becoming a way in.
    """
    io.open(os.path.join(v1_state.root, "tasks.yaml"), "w", encoding="utf-8", newline="\n").write(
        "tasks:\n"
        "  TSK-0001:\n"
        "    title: \"wire the ledger export\"\n"
        "    owner: bookkeeper\n"
        "    completed: 2025-11-04\n"
        "    status: VALIDATED\n"
        "  TSK-0002:\n"
        "    title: \"still open\"\n"
        "    owner: bookkeeper\n"
        "    status: TODO\n")
    plan = _planned(v1_state)
    tasks = {entry["legacy_id"]: entry for entry in plan["records"]
             if entry["source"] == "tasks.yaml"}
    # BOLT 2 -- only a record the mapping table calls FINISHED takes THIS exemption, and the open
    # task is what measures it: DEC-0009 archives it too (nine of its ten gaps have no source
    # anywhere), but through the other door and therefore at the TYPE'S INITIAL status. Its mapped
    # V1 value never reaches the file, which is exactly what bolt 2 is for.
    assert tasks["TSK-0002"]["verdict"] == "unresolved", tasks["TSK-0002"]
    assert tasks["TSK-0001"]["verdict"] == "translatable"
    assert tasks["TSK-0001"]["target"] == "archive"
    # the year comes from the record's own date, not from the flag
    assert tasks["TSK-0001"]["archive_year"] == 2025
    assert "--archive-year" not in tasks["TSK-0001"]["archive_year_from"]

    io.open(os.path.join(v1_state.root, "tasks.yaml"), "a", encoding="utf-8", newline="\n").write(
        "    derives_from: PROC-0001\n")   # irrelevant to TSK-0002's missing contract
    assert _migrated(v1_state) == 0
    open_task = [item for item in _archived_items(v1_state, "TSK")
                 if item[migrate.LEGACY_FIELD]["legacy_id"] == "TSK-0002"]
    assert len(open_task) == 1, open_task
    assert open_task[0]["status"] == initial_status("TSK"), open_task[0]
    assert open_task[0][migrate.LEGACY_FIELD]["legacy_status"] == "TODO"
    assert "root_revision" in open_task[0][migrate.LEGACY_FIELD]["unresolved"]

    # remove the open task entirely and the finished one migrates on its own. The run above
    # absorbed `tasks.yaml` and retired it to `legacy/tasks.yaml`, so writing a THIRD document of
    # that name is the field case `occupied_landings` refuses: the move would replace the copy the
    # receipt above carries the hash of. This does what the refusal's own remedy says -- takes the
    # retired copy out of the state directory -- because what is measured below is the archive
    # path, not the retirement.
    os.remove(os.path.join(v1_state.root, "legacy", "tasks.yaml"))
    io.open(os.path.join(v1_state.root, "tasks.yaml"), "w", encoding="utf-8", newline="\n").write(
        "tasks:\n"
        "  TSK-0001:\n"
        "    title: \"wire the ledger export\"\n"
        "    owner: bookkeeper\n"
        "    completed: 2025-11-04\n"
        "    status: VALIDATED\n")
    assert _migrated(v1_state) == 0
    filed = os.path.join(v1_state.root, "archive", "TSK", "2025")
    names = sorted(os.listdir(filed))
    assert len(names) == 1, names
    item = yaml.safe_load(io.open(os.path.join(filed, names[0]), encoding="utf-8"))
    # SR-0002: the item names the fields it lacks, and the kit version it was read with
    missing = item[migrate.LEGACY_FIELD]["missing_required_fields"]
    assert "allowed_scope" in missing and "assigned_role" in missing, missing
    assert set(missing) <= set(REQUIRED_FIELDS["TSK"])
    assert "kit_version" in item[migrate.LEGACY_FIELD]
    # BOLT 1 -- the exemption is reachable through the migration only. The same body handed to
    # `capture` is refused for exactly the fields the archived item records as missing.
    body = {key: value for key, value in item.items()
            if key not in ("id", "status", "revision", "approval_ref", "created")}
    with pytest.raises(Exception) as refusal:
        v1_state.capture("TSK", body)
    # ...and since the goal-size exemption was bound to the PATH (TSK-0146 rework, F1) the ordinary
    # door stops one step EARLIER: a body carrying the provenance record is refused for that alone,
    # because only the import writes it. Both refusals are the same bolt from two sides, so both
    # are measured here rather than one being swapped for the other.
    assert "written by the import path alone" in str(refusal.value), refusal.value
    without_provenance = {key: value for key, value in body.items()
                          if key != migrate.LEGACY_FIELD}
    with pytest.raises(Exception) as contract:
        v1_state.capture("TSK", without_provenance)
    assert "missing required fields" in str(contract.value), contract.value
    # BOLT 3 -- it is not reactivatable: no kernel operation moves it back, and the two that write
    # an item resolve through `active/` and do not find it.
    assert not os.path.exists(v1_state.active_path(item["id"]))
    with pytest.raises(Exception):
        v1_state.update_item(item["id"], {"title": "reopened"})
    with pytest.raises(Exception):
        v1_state.transition(item["id"], "DONE")


_APPROVAL_FINISHED = (
    "product_requirements:\n"
    "  PRD-0001:\n"
    "    title: \"the export requirement\"\n"
    # `technical_enabler` because the state validator asks a PR of any other class for a
    # `user_story`, and V1 had no such field: an imported normal PR is a warning this fixture would
    # otherwise carry into every assertion about findings.
    "    class: technical_enabler\n"
    "    problem: \"no export\"\n"
    "    goal: \"an export\"\n"
    "    acceptance_criteria: []\n"
    "    invariants: []\n"
    "    out_of_scope: []\n"
    "    priority: high\n"
    "    status: PROPOSED\n"
    "change_requests:\n"
    "  CR-0001:\n"
    "    title: \"widen the export\"\n"
    "    target_pr: PRD-0001\n"
    "    target_revision: 1\n"
    "    change_description: \"add the CSV column\"\n"
    "    acceptance_criteria: []\n"
    "    applied: 2025-11-04\n"
    "    status: APPLIED\n")


def test_a_record_whose_end_only_an_approval_could_have_reached_is_not_archived(v1_state):
    """DEC-0004 bolt 2: the archive path may not write a status that stands behind an APR.

    THE DEFECT THIS IS THE MEASUREMENT OF, end to end. The bolt subtracted the statuses an approval
    commits as a SET, so everything further down the same chain stayed writable -- and a V1 `CR
    APPLIED` is exactly that: `APPLIED` is one step past `DRAFT -> APPROVED`, which is a `scope`
    approval's own edge. Measured before the fix, on this fixture: `archive/CR/2025/CR-0001.yaml`
    with `status: APPLIED`, `approval_ref: null`, nothing under `approvals/pending` or
    `approvals/consumed`, and `validate_state` reporting zero findings -- a state that says a user
    signed something no user was ever asked about, and nothing outside the file to notice.

    So it is imported the ordinary way instead, at its initial status, with `APPLIED` kept as what
    V1 meant. That is the same treatment a V1 `PRD ACCEPTED` gets and for the same reason; the cost
    is named in `state.migration_archive_status` rather than hidden here.
    """
    io.open(os.path.join(v1_state.root, "requirements.yaml"), "w", encoding="utf-8",
            newline="\n").write(_APPROVAL_FINISHED)
    plan = _planned(v1_state)
    change = [e for e in plan["records"] if e["legacy_id"] == "CR-0001"][0]
    assert change["archive_candidate"] is True, (
        "the mapping table no longer calls an applied CR finished, so this measures nothing")
    assert change["mapped_status"] == "APPLIED" and change["target"] == "active", change
    assert change["verdict"] == "translatable", change
    assert _migrated(v1_state) == 0
    assert not os.path.isdir(os.path.join(v1_state.root, "archive", "CR")), (
        "an applied CR was written into the archive at a status only an approval reaches")
    stored = [v1_state.read_item(name) for name, _p in v1_state.iter_active_items("CR")]
    assert len(stored) == 1, stored
    item = stored[0]
    assert item["status"] == "DRAFT" and item["approval_ref"] is None
    assert item[migrate.LEGACY_FIELD]["legacy_status"] == "APPLIED"
    assert item[migrate.LEGACY_FIELD]["written_to"] == "active"
    # ...and the binding was rewritten to the id the requirement actually got, not the V1 one
    assert item["target_pr"] == [name for name, _p in v1_state.iter_active_items("PR")][0]
    assert not findings_beside_the_receipts_carrier(v1_state)
    # the kernel's own refusal says WHY, in the terms spec II.10 uses
    from kernel.state import StateError, migration_archive_status
    with pytest.raises(StateError) as refusal:
        migration_archive_status("CR", "CR", "APPLIED")
    assert "USER APPROVAL" in str(refusal.value), refusal.value


def test_a_v1_task_that_is_done_is_archived_at_done_and_not_reopened_as_a_draft(v1_state):
    """SR-0004 / DEC-0004, for the rows the exemption was actually written for.

    260 of 264 tasks in one measured field project are DONE and 162 of 165 in the other, and that
    number is the whole argument for the archive path -- but `("TSK", "DONE")` was not archive-bound
    while it was, because `DONE` is no TERMINAL of the V2 task automaton. So the records the
    exemption exists for went to `tasks/active/` at DRAFT: a 2025 task presented as a fresh work
    order, missing ten of eleven contract fields, buried under nothing.

    It is archived AT `DONE` and deliberately not mapped on to `VALIDATED`: in V2 that means QA
    confirmed the work, V1 never collected such a confirmation, and the import does not invent one.
    Both halves are asserted, because writing `VALIDATED` here would satisfy the first.
    """
    io.open(os.path.join(v1_state.root, "tasks.yaml"), "w", encoding="utf-8", newline="\n").write(
        "tasks:\n"
        "  TSK-0001:\n"
        "    title: \"wire the ledger export\"\n"
        "    owner: bookkeeper\n"
        "    completed: 2025-11-04\n"
        "    status: DONE\n")
    plan = _planned(v1_state)
    task = [e for e in plan["records"] if e["legacy_id"] == "TSK-0001"][0]
    assert task["verdict"] == "translatable" and task["target"] == "archive", task
    assert _migrated(v1_state) == 0
    assert not [name for name, _p in v1_state.iter_active_items("TSK")], (
        "a task V1 recorded as finished was imported as a live work order")
    filed = sorted(os.listdir(os.path.join(v1_state.root, "archive", "TSK", "2025")))
    assert len(filed) == 1, filed
    item = yaml.safe_load(io.open(os.path.join(v1_state.root, "archive", "TSK", "2025", filed[0]),
                                  encoding="utf-8"))
    assert item["status"] == "DONE", (
        "the archived task does not carry the state V1 recorded (%r)" % item["status"])
    assert item[migrate.LEGACY_FIELD]["legacy_status"] == "DONE"
    assert "allowed_scope" in item[migrate.LEGACY_FIELD]["missing_required_fields"]
    assert not findings_beside_the_receipts_carrier(v1_state)


def test_a_finished_record_with_no_date_refuses_rather_than_choosing_a_year(v1_state):
    """SR-0004: "wo keines dasteht ... ist es eine vorgelegte Entscheidung und keine Vermutung".

    The office PROC schema carries no date at all, so the RETIRED procedures are exactly that case.
    Without `--archive-year` the run must BLOCK and say what would settle it; with it, the same
    records migrate. Both halves in one test so neither side can quietly become the only one.
    """
    undated = migrate.build_plan(v1_state, {("PROC", "roles"): "owner"})
    blocked = migrate._by_verdict(undated, "blocked")
    _active, archived = _fixture_split()
    assert sorted(entry["legacy_id"] for entry in blocked) == archived, blocked
    assert "--archive-year" in blocked[0]["reason"]
    assert not migrate.plan_is_executable(undated)
    assert migrate.plan_is_executable(_planned(v1_state))


# -- the residuals the round-2 review left named --------------------------------------------------


def test_a_document_whose_yaml_refers_to_itself_terminates(v1_state):
    """R-a: the identity cycle guard in `scan_document`, which replaced a hand-picked depth limit.

    `yaml.safe_load` builds a genuinely self-referencing structure out of a recursive anchor, and
    the walk descends into record bodies -- so without "every container is walked at most once, by
    identity" this recurses until Python gives up. The guard had no test at all: removing it left
    the file green.
    """
    io.open(os.path.join(v1_state.root, "looping.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "processes: &loop\n"
        "  PROC-0400:\n"
        "    title: \"the looping one\"\n"
        "    owner: bookkeeper\n"
        "    steps: [\"a\"]\n"
        "    status: ACTIVE\n"
        "    back: *loop\n")
    payload = yaml.safe_load(io.open(os.path.join(v1_state.root, "looping.yaml"),
                                     encoding="utf-8"))
    assert payload["processes"]["PROC-0400"]["back"] is payload["processes"], (
        "PyYAML no longer builds the recursive structure, so this measures nothing")
    found = migrate.scan_document(payload)
    assert [key for _o, key, _r in found] == ["PROC-0400"], found
    # ...and the whole planner survives it too, so the guard is not only true of the scanner
    plan = migrate.build_plan(v1_state, None, _ARCHIVE_YEAR)
    assert any(entry["legacy_id"] == "PROC-0400" for entry in plan["records"])


def test_the_run_refuses_when_the_record_at_that_position_is_a_different_one(v1_state):
    """R-b: the ordinal is the identity, and nothing measured the second line of that defence.

    Two records swap places between the reading and the writing. Keyed by ID the run would find
    "a" record with the right name and write it under the plan's classification; keyed by ORDINAL
    it sees that position 0 no longer holds what the plan classified there and refuses. Rebuilding
    the lookup by id left this green, which is why the refusal is measured here rather than argued
    in the docstring.
    """
    def write(first, second):
        io.open(os.path.join(v1_state.root, "pair.yaml"), "w", encoding="utf-8",
                newline="\n").write(
            "processes:\n" + "".join(
                "  %s:\n"
                "    title: \"%s\"\n    owner: bookkeeper\n    steps: [\"x\"]\n"
                "    status: ACTIVE\n" % (key, key) for key in (first, second)))

    write("PROC-0501", "PROC-0502")
    plan = _planned(v1_state)
    digest = migrate.plan_digest(plan)
    pair = {entry["legacy_id"]: entry["ordinal"] for entry in plan["records"]
            if entry["source"] == "pair.yaml"}
    assert pair["PROC-0501"] < pair["PROC-0502"], pair
    write("PROC-0502", "PROC-0501")
    with pytest.raises(migrate.MigrationError) as refusal:
        migrate.execute(v1_state, plan, digest)
    assert "the document changed under the plan" in str(refusal.value), refusal.value


def test_a_v1_document_under_a_dotted_path_is_named_rather_than_swallowed(v1_state, capsys):
    """R-c: the module head promises no silent skip, and a dotted path was silent.

    Measured: `project_memory/.legacy/old_procs.yaml` with a `PROC-0099` in it produced NO mention
    anywhere in the dry run -- not imported, not blocked, not reported. It is still not SEARCHED,
    because those paths are machinery (the lock, the audit log) and searching them would put both
    in every report; it is now NAMED, which is the difference between "found none" and "did not
    look". The machinery itself stays out: `.audit/hook_events.jsonl` is not YAML.
    """
    os.makedirs(os.path.join(v1_state.root, ".legacy"), exist_ok=True)
    io.open(os.path.join(v1_state.root, ".legacy", "old_procs.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "processes:\n"
        "  PROC-0099:\n"
        "    title: \"parked\"\n    owner: bookkeeper\n    steps: [\"x\"]\n    status: ACTIVE\n")
    os.makedirs(os.path.join(v1_state.root, ".audit"), exist_ok=True)
    io.open(os.path.join(v1_state.root, ".audit", "hook_events.jsonl"), "w", encoding="utf-8",
            newline="\n").write('{"hook": "gate_git"}\n')
    plan = migrate.build_plan(v1_state, None, _ARCHIVE_YEAR)
    named = [note for note in plan["unscanned"] if "old_procs.yaml" in note]
    assert len(named) == 1, plan["unscanned"]
    assert not [note for note in plan["unscanned"] if "hook_events" in note]
    _run(v1_state, "migrate", "--dry-run")
    printed = capsys.readouterr().out
    assert ".legacy/old_procs.yaml" in printed, printed
    assert "NOT SEARCHED" in printed


def test_the_budget_measures_at_least_what_the_kernel_really_writes(v1_state):
    """R-f: the budget placeholders were one byte SHORT, constant over three samples.

    `id: DEC-0000` / `status: VALID` against a real `PROC-0001` / `DRAFT`. A budget check that
    under-measures is a check that passes exactly the items `validate` then flags, and the window
    was never measured -- only reasoned about. Here it is measured against items the kernel really
    wrote, for every type this run produced.
    """
    assert _migrated(v1_state) == 0
    seen = 0
    for item_type in ("PROC", "DEC"):
        for name, path in v1_state.iter_active_items(item_type):
            item = yaml.safe_load(io.open(path, encoding="utf-8"))
            body = {key: value for key, value in item.items()
                    if key not in ("id", "status", "revision", "approval_ref", "created")}
            measured, lines = migrate.item_size(body, item_type)
            on_disk = io.open(path, "rb").read()
            assert measured >= len(on_disk), (
                "%s: the budget measured %d bytes for a file of %d" % (name, measured,
                                                                       len(on_disk)))
            assert lines >= on_disk.count(b"\n"), name
            seen += 1
    assert seen > 1, "nothing was measured"


# -- the type table, against what the kits really shipped -----------------------------------------


def _shipped_v1_stores():
    """({V1 prefix: {status, ...}}, {the template documents it was read from}).

    THE DEFINITION, read off the templates themselves at the last commit that carried them rather
    than typed here: a V1 store is a `project_memory` template whose header comment declares BOTH a
    schema key of the `<PREFIX>-<n>` shape and a STATUS CHAIN. That is what makes a file a backlog
    -- ids and a lifecycle -- and it is the same property `kernel/migrate.py` decides on at
    runtime. Everything else in those directories (`architecture.yaml`, `filing_log.yaml`,
    `literature.yaml` ...) mentions ids without being a store, and is left out by the rule instead
    of by a list of exceptions.

    A CHAIN IS RECOGNISED BY ITS FORM, NOT BY A LABEL, and that is the correction of 2026-08-04.
    This asked for the literal word `Status:` at the head of a comment line, which is how thirteen
    of the fourteen documents spell it -- and the research kit's `fzulg_documentation.yaml` writes
    it lower-case and inline behind the field it documents, so the whole store was invisible: the
    two states it declares had no row in the mapping table, `RQ` HAS rows, and an unknown status of
    a known type blocks the entire run. A research project that filled its FZulG layer could not be
    migrated at all, and this check stayed green through it. The form is: a header line that names
    the FIELD `status` and shows a transition between two of its values (`A -> B`), which is what a
    chain looks like however the line around it is written. Parenthesised asides are stripped
    first: `feature_requests.yaml` writes "ACCEPTED (-> becomes a PRD) / REJECTED / DEFERRED", and
    reading the aside as a state would have added a phantom `PRD` row -- and would have made the
    aside's own arrow the thing that identified the line.
    """
    commit = _last_v1_commit()
    code, out = _git("ls-tree", "--name-only", "-r", commit)
    assert code == 0, out
    names = [line for line in out.decode("utf-8", "replace").split()
             if "/templates/project_memory/" in line and line.endswith(".yaml")]
    assert names, "this repository's history holds no V1 project_memory templates at %s" % commit
    key_re = re.compile(r"^#\s+([A-Z]{2,4})-(?:XXXX|\d{3,}):", re.M)
    field_re = re.compile(r"\bstatus\b", re.I)
    chain_re = re.compile(r"[A-Z][A-Z_]{2,}\s*->\s*[A-Z][A-Z_]{2,}")
    stores, documents = {}, set()
    for name in names:
        code, blob = _git("cat-file", "blob", "%s:%s" % (commit, name))
        assert code == 0, name
        header = "\n".join(line for line in blob.decode("utf-8", "replace").splitlines()
                           if line.startswith("#"))
        key = key_re.search(header)
        chain = [plain for plain in
                 (re.sub(r"\([^)]*\)", "", line) for line in header.splitlines()
                  if field_re.search(line))
                 if chain_re.search(plain)]
        if not chain or not key:
            continue
        documents.add(name)
        stores.setdefault(key.group(1), set()).update(re.findall(r"[A-Z][A-Z_]{2,}", chain[0]))
    return stores, documents


def _shipped_v1_store_fields():
    """{V1 prefix: {field name: the template document it was read from}} -- the V1 field contracts.

    Read off the SCHEMA BLOCK of each V1 template's header comment at the last commit that carried
    it, by the same route `_shipped_v1_stores` reads the status chains: a key line of the
    `<PREFIX>-XXXX:` shape, and the `name:` lines exactly one indent level below it. Exactly one --
    a `git:` sub-mapping in the V1 task schema is a field OF a field, and reading it as a field of
    the record would let a suggestion name something no record has at top level.
    """
    commit = _last_v1_commit()
    code, out = _git("ls-tree", "--name-only", "-r", commit)
    assert code == 0, out
    names = [line for line in out.decode("utf-8", "replace").split()
             if "/templates/project_memory/" in line and line.endswith(".yaml")]
    assert names, "this repository's history holds no V1 project_memory templates at %s" % commit
    key_re = re.compile(r"^#(\s+)([A-Z]{2,4})-(?:XXXX|\d+):\s*$")
    field_re = re.compile(r"^#(\s+)([A-Za-z_][A-Za-z0-9_]*):")
    fields = {}
    for name in names:
        code, blob = _git("cat-file", "blob", "%s:%s" % (commit, name))
        assert code == 0, name
        prefix, indent = None, None
        for line in blob.decode("utf-8", "replace").splitlines():
            if not line.startswith("#"):
                continue
            key = key_re.match(line)
            if key:
                prefix, indent = key.group(2), len(key.group(1))
                continue
            if prefix is None:
                continue
            field = field_re.match(line)
            if field is None or len(field.group(1)) <= indent:
                prefix = None if field is None else prefix
                continue
            if len(field.group(1)) == indent + 2:
                fields.setdefault(prefix, {}).setdefault(field.group(2), name)
    return fields


def test_every_field_suggestion_rests_on_a_field_the_kit_really_shipped():
    """SR-0007: a suggestion is derived from the shipped V1 templates, not invented here.

    THREE THINGS ARE DERIVED and each one is a way a row could be wrong:
      * the V1 field it names is documented by that store's OWN V1 template, in this repository's
        history. A row naming a field no kit ever shipped would propose a flag that carries
        nothing, which is the "Vorschlag ohne Grundlage" SR-0007 calls worse than a question.
      * the V2 field it fills is REQUIRED for the type the store's records map to. A suggestion for
        an optional field would be the tool filling in something nobody asked for.
      * the row is NEEDED: the two contracts do not already spell the field the same way, or the
        ordinary rule in `_item_fields` carries it and the suggestion is dead code with an opinion.

    RED for any row whose V1 field the templates do not carry -- which is the whole mechanism that
    keeps this table from drifting into a list of plausible-sounding pairs.
    """
    shipped = _shipped_v1_store_fields()
    assert len(shipped) >= 8, sorted(shipped)
    for (v1_type, v2_field), (v1_field, why) in sorted(V1_FIELD_SUGGESTIONS.items()):
        assert v1_type in shipped, (
            "%s has no V1 schema in the kits' own history, so nothing supports a suggestion for it"
            % v1_type)
        assert v1_field in shipped[v1_type], (
            "%s.%s is proposed from `%s`, which the V1 %s schema (%s) does not document"
            % (v1_type, v2_field, v1_field, v1_type,
               "/".join(sorted(set(shipped[v1_type].values())))))
        assert why.strip(), (v1_type, v2_field)
        v2_type = {row[0]: target for row, target in
                   ((key, value[0]) for key, value in V1_STATUS_MAPPING.items())}[v1_type]
        assert v2_field in REQUIRED_FIELDS[v2_type], (
            "%s.%s is not a required field of the type %s records become" % (v2_type, v2_field,
                                                                             v1_type))
        assert v2_field not in shipped[v1_type], (
            "%s already spells `%s` the same way, so `_item_fields` carries it and this row "
            "proposes something nobody is missing" % (v1_type, v2_field))


def test_the_type_table_covers_every_v1_store_the_kits_shipped():
    """SR-0003 / B5: a shipped V1 status with no row is a record the harness cannot read.

    RED before the rows added on 2026-08-04: `BUG`, `CR`, `FR`, `RQ`, `HYP`, `EXP` and `PA` had no
    row at all, so a whole research backlog and half a dev one were reported as "not a backlog
    type" and the run exited 0 -- a false all-clear. RED again without DEC-0002's `ADR`/`MDR` rows,
    without `PRD REJECTED` / `TSK REJECTED`, which were missing from the ORIGINAL table and would
    have blocked any project that ever rejected a requirement or a task, and RED once more without
    the two `RQ` rows the FZulG layer declares.

    The expectation is derived from this repository's own history, so a kit that ships a new V1
    store, or renames a status in one, turns this red without an edit here.

    THE DOCUMENT COUNT IS A FLOOR AND IT IS THE READER'S OWN TRIPWIRE, not a fact about the kits:
    the point of it is that a reader which narrows -- back to a literal label, say -- finds fewer
    documents while the pairs it does find still all have rows, i.e. goes green on a smaller
    question. It is a floor rather than an equality so that a kit ADDING a store fails on the
    missing row below, which is the message a reader can act on.
    """
    stores, documents = _shipped_v1_stores()
    assert len(stores) >= 8, stores
    assert len(documents) >= 15, sorted(documents)
    missing = sorted((prefix, status) for prefix, states in stores.items() for status in states
                     if (prefix, status) not in V1_STATUS_MAPPING)
    assert not missing, (
        "spec II.10's table has no row for these shipped V1 (type, status) pairs, so a project "
        "holding one of them cannot be migrated: %s" % missing)


def test_a_v1_decision_record_becomes_a_dec_item_carrying_its_own_provenance(v1_state):
    """DEC-0002: `decisions.yaml` is a backlog store, so its records become `DEC` items.

    Written in the dev kit's real V1 ADR schema. Four of the five `REQUIRED_FIELDS["DEC"]` are
    spelled identically in it and carry over by the ordinary rule; `source` is the fifth, and no V1
    field holds it -- so RED without `PROVENANCE_FIELDS`, because the record would sit in
    `needs_decision` for ever asking for a `--map` naming a field that does not exist.

    The counter-direction is in the same run: `roles` is also absent from a V1 PROC and is NOT
    filled, because it is about the record's CONTENT rather than about where it came from.
    """
    io.open(os.path.join(v1_state.root, "decisions.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "decisions:\n"
        "  ADR-0001:\n"
        "    title: \"Store invoices as PDF/A\"\n"
        "    context: \"the tax office asks for long-term readable archives\"\n"
        "    decision: \"convert every incoming invoice to PDF/A on filing\"\n"
        "    consequences: \"one more conversion step; no proprietary readers needed\"\n"
        "    status: ACCEPTED\n")
    plan = _planned(v1_state)
    adr = [entry for entry in plan["records"] if entry["legacy_id"] == "ADR-0001"]
    assert len(adr) == 1 and adr[0]["verdict"] == "translatable", adr
    assert adr[0]["v2_type"] == "DEC" and adr[0]["target"] == "active"
    # THE COUNTER-DIRECTION, taken before the run because a migrated record is `already_imported`
    # afterwards: a required field about the record's CONTENT is still a decision. `roles` is
    # absent from every V1 PROC and is not invented for any of them.
    undecided = migrate.build_plan(v1_state, None, _ARCHIVE_YEAR)
    procs = [entry for entry in undecided["records"] if entry["legacy_type"] == "PROC"]
    assert any("roles" in entry.get("missing_fields", []) for entry in procs), procs
    assert _migrated(v1_state) == 0
    # the run's own receipt is a DEC too, so the imported one is picked out by its legacy id
    stored = [v1_state.read_item(name) for name, _p in v1_state.iter_active_items("DEC")]
    imported = [item for item in stored
                if item.get(migrate.LEGACY_FIELD, {}).get("legacy_id") == "ADR-0001"]
    assert len(imported) == 1, [item["id"] for item in stored]
    item = imported[0]
    assert item["title"] == "Store invoices as PDF/A"
    assert item["status"] == "VALID"
    # the provenance field says where it came from, and it says it in terms a reader can follow
    assert "decisions.yaml" in item["source"] and "ADR-0001" in item["source"]


def test_an_imported_items_legacy_id_is_not_read_as_a_relation(v1_state):
    """R6: a reader skipped a field called `legacy_ids`, and no such field has ever existed.

    What `kernel/migrate.py` writes is `legacy_fields`, and it holds the item's FORMER NAME -- a
    value that parses as an item id and is not a pointer to anything. Measured on a real imported
    item, so the skip is answerable to the field that exists rather than to the one somebody
    remembered.

    THE SUBJECT MOVED WITH THE CODE (TSK-0115, DEC-0065 (1)). The shipped dashboard used to derive
    "relations" from any top-level field whose value parses as an id, and this test held that
    derivation against `legacy_fields`. That generator renders no items any more, so the question
    "does an imported item's former name bind it to something?" is now `backlog_tree.parents_of`'s
    -- the one reader the board's trees, the merge gate and the plan diagram all place items with.
    Its answer is stronger than the old one and comes from the type's own field contract rather
    than from a value's shape: `legacy_fields` is not a binding field of any type, so it can never
    be a parent. The test is kept rather than deleted because the PROPERTY is the same one.
    """
    assert _migrated(v1_state) == 0
    sys.path.insert(0, os.path.join(ROOT, "team-kits"))
    from kernel import backlog_tree
    from kernel.backlog_types import PARENT_FIELDS
    item = v1_state.read_item("PROC-0001")
    assert item[migrate.LEGACY_FIELD]["legacy_id"] == "PROC-0001"
    node = backlog_tree.Node({"id": "PROC-0001", "type": "PROC"}, item)
    assert migrate.LEGACY_FIELD not in PARENT_FIELDS.get("PROC", ()), (
        "the legacy metadata became a binding field, so a former name now binds an item")
    assert "PROC-0001" not in backlog_tree.parents_of(node), (
        "an imported item's legacy metadata was read as a pointer to another item")


def test_the_migrated_state_passes_the_validator(v1_state):
    """The whole point of writing through `capture`: what the import leaves behind is state the
    harness's own validator accepts, with no findings of any severity."""
    assert _migrated(v1_state) == 0
    findings = findings_beside_the_receipts_carrier(v1_state)
    assert not findings, findings


def test_the_import_opens_no_gate_that_requires_an_approval(v1_state, capsys):
    """The claim `kernel/migrate.py` makes about itself, measured against the REAL hook process.

    `gate_proc_approved` refuses a specialist spawn while the project has no APPROVED procedure.
    The import brings sixteen procedures in -- and it must NOT open that gate, because imported
    items carry `approval_ref: null` by spec II.10 and only a user answer mints an APR. A migration
    that quietly satisfied an approval gate would be exactly the "automatically generated user
    approval" the spec forbids.

    Run as a real hook process against a repo laid out the way a scaffolded project is, because the
    gate resolves its own state directory and imports the kernel from `.claude`; asking the module
    in-process would measure this test's sys.path instead of the installation.

    A CRASHING GATE ALSO EXITS 2, and saying so is the correction that made this test measure
    anything. Two earlier cuts were green through a defect that walked every imported procedure to
    APPROVED: the first because a missing `kernel/schemas/` made the gate die with
    `KernelUnavailable`, the second because the only thing it asserted about the text was the HOOK
    NAME -- and `_kernel`'s fail-closed excepthook opens every crash report with exactly that name
    too (measured by replacing the gate's first statement with a `raise`: rc 2, name present, test
    green).

    So the gate is proved to be RUNNING by a positive control instead of by any wording: at the
    end, one procedure is put into an approved status by hand and the same spawn -- naming that
    procedure -- must come back rc 0. A gate that cannot run can never answer 0, so the two
    refusals before it are refusals rather than accidents. That mutation is deliberately last: it
    is the very defect the assertions above forbid, so it may only happen once they have been made.
    """
    repo = os.path.dirname(v1_state.root)
    claude = os.path.join(repo, ".claude")
    os.makedirs(claude, exist_ok=True)
    for source, name in ((os.path.join(ROOT, "team-kits", "office-team", "hooks"), "hooks"),
                         (os.path.join(ROOT, "team-kits", "kernel"), "kernel")):
        # the WHOLE tree: `kernel/schemas/` is a package directory the kernel imports at load time
        shutil.copytree(source, os.path.join(claude, name),
                        ignore=shutil.ignore_patterns("__pycache__"))

    def spawn_verdict(prompt="book the invoice"):
        payload = json.dumps({"tool_name": "Task", "cwd": repo,
                              "tool_input": {"subagent_type": "bookkeeper", "prompt": prompt}})
        env = {k: v for k, v in os.environ.items()
               if k not in ("PYTHONPATH", "PYTHONPYCACHEPREFIX")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        # the project this gate is being asked about, named the way a provider names it: the gate
        # resolves its root through `_root.find_repo_root`, whose first answer is this variable,
        # and a child that inherits the suite's own value measures another tree (BUG-0052's
        # neighbour -- the suite now carries a throwaway root there, and before that it carried
        # the harness checkout, so this was never a variable to leave to chance)
        env["CLAUDE_PROJECT_DIR"] = repo
        return subprocess.run([sys.executable, "-B",
                               os.path.join(claude, "hooks", "gate_proc_approved.py")],
                              input=payload.encode("utf-8"), capture_output=True, cwd=repo,
                              env=env, timeout=120)

    def approved_procedures():
        """The condition the gate reads, asked of the kernel rather than of the gate's prose.

        `approvals.approved_statuses("PROC")` is where that vocabulary is decided and the gate
        composes its refusal out of it -- so this stays true through a reworded message, which a
        copy of the wording would not.
        """
        allowed = approvals.approved_statuses("PROC")
        return sorted(item_id for item_id, path in v1_state.iter_active_items("PROC")
                      if yaml.safe_load(io.open(path, encoding="utf-8"))["status"] in allowed)

    def verdict(result):
        return result.returncode, (result.stdout + result.stderr).decode("utf-8", "replace")

    before_code, before_text = verdict(spawn_verdict())
    assert before_code == 2 and "gate_proc_approved" in before_text, before_text
    assert approved_procedures() == []
    assert _migrated(v1_state) == 0

    # THE STATE the gate decides on -- unchanged by an import of sixteen procedures.
    assert approved_procedures() == [], (
        "the import put procedures into an APPROVED status; spec II.10 says an imported item keeps "
        "its regular initial status and only a real user action mints an APR")
    after_code, after_text = verdict(spawn_verdict())
    # ...and the gate SAYS the same thing it said before. Not a quoted sentence: the two runs are
    # compared with each other, so any change the import caused shows up whatever the wording is.
    # An exit code alone would not have been enough -- measured: with the import walking the V1
    # status onto the automaton, `gate_proc_approved` still exits 2 and switches from "this project
    # has no approved procedure at all" to "the work order names no PROC-nnnn, and 1 approved
    # procedure(s) exist", which is the gate OPENED as far as approvals go.
    assert (after_code, after_text) == (before_code, before_text), (
        "the import changed what the spawn gate says, so it changed the approval state:\n"
        "before: %s\nafter:  %s" % (before_text, after_text))

    # THE POSITIVE CONTROL. Everything above is a pair of REFUSALS, and a gate that cannot start
    # refuses everything -- so without this, the whole test is satisfied by a broken installation.
    # One procedure is put into an approved status, by hand, exactly as the defect this test
    # forbids would have done; the same spawn naming it must now come back rc 0.
    approved = sorted(approvals.approved_statuses("PROC"))[0]
    item = v1_state.read_item("PROC-0001")
    item["status"] = approved
    item[approvals.APPROVED_CONTENT_HASH_FIELD] = approvals.approved_content_hash("PROC", item)
    v1_state._write_yaml_atomic(v1_state.active_path("PROC-0001"), item)
    v1_state.generate_index()
    control = spawn_verdict("execute PROC-0001: book the invoice")
    assert control.returncode == 0, (
        "the positive control failed: with PROC-0001 in %s the gate still refuses, so it is not "
        "running in this installation and the two refusals above prove nothing:\n%s"
        % (approved, (control.stdout + control.stderr).decode("utf-8", "replace")))
    assert approved_procedures() == ["PROC-0001"]


# -- the id shape, and what a hand-numbered V1 store really looks like -----------------------------


def _v1_id_shape_state(state):
    """A V1 `tasks.yaml` numbered the way a hand-kept list numbers: with a discriminator.

    Written in the dev kit's real V1 task schema, and the shape is the one the field copies carry:
    `portfoliomanaigement`'s `tasks.yaml` holds `TSK-0017b`, `TSK-0031b`, `TSK-0055b` and
    `TSK-0058b` beside their unsuffixed neighbours, and its `product_requirements.yaml` holds
    `PRD-0006b` and `PRD-0014b`. V1 had no allocator, so a record inserted between two numbered
    ones was named by appending rather than by renumbering everything after it.
    """
    io.open(os.path.join(state.root, "tasks.yaml"), "w", encoding="utf-8", newline="\n").write(
        "tasks:\n"
        "  PRD-0014b: { title: \"the inserted requirement\", status: PROPOSED,"
        " acceptance_criteria: [\"it is imported under its own id\"], created: 2026-06-11 }\n"
        "  TSK-0017b: { derives_from: PRD-0014b, title: \"the inserted task\", status: DONE,"
        " kind: implementation, created: 2026-06-11, completed: 2026-06-11 }\n")


# The map that leaves a V1 task with nothing missing and nothing outside a closed vocabulary.
# `TSK.type` is one of those, so it is answered from a field that really holds one of its values --
# a map that filled it from `title` would be refused by the writer for the vocabulary rather than
# for the binding, which is a different branch from the one under test.
_COMPLETE_MAP = {
    ("PROC", "roles"): "owner", ("PR", "goal"): "title", ("PR", "problem"): "title",
    ("PR", "class"): "title", ("PR", "invariants"): "title", ("PR", "out_of_scope"): "title",
    ("PR", "priority"): "title", ("TSK", "product_requirement"): "derives_from",
    ("TSK", "root_revision"): "created", ("TSK", "type"): "kind",
    ("TSK", "assigned_role"): "title", ("TSK", "acceptance_refs"): "title",
    ("TSK", "required_inputs"): "title", ("TSK", "allowed_scope"): "title",
    ("TSK", "forbidden_scope"): "title", ("TSK", "expected_outputs"): "title",
    ("TSK", "dependencies"): "title",
}


def test_a_hand_numbered_v1_id_is_a_record_and_not_a_silence(v1_state):
    """B2: every id-shaped record gets a verdict, and a discriminator is part of the id shape.

    RED before `V1_ID_RE` carried the discriminator. Measured on the field copy of
    `portfoliomanaigement` (2026-08-04): the plan classified 354 of its 360 records, and
    `TSK-0017b`, `TSK-0031b`, `TSK-0055b`, `TSK-0058b`, `PRD-0006b` and `PRD-0014b` appeared under
    no heading of the dry run at all. Silence about something id-shaped is the one outcome this
    command's own head says it never produces.

    The legacy id is the WHOLE key, discriminator included, so the record keeps its own identity:
    an import that dropped the suffix would file the inserted record under its neighbour's id and
    a re-run would then skip the wrong one.
    """
    _v1_id_shape_state(v1_state)
    plan = _planned(v1_state)
    seen = {entry["legacy_id"]: entry for entry in plan["records"]
            if entry["source"] == "tasks.yaml"}
    assert set(seen) == {"PRD-0014b", "TSK-0017b"}, sorted(seen)
    assert seen["TSK-0017b"]["legacy_type"] == "TSK"
    assert seen["PRD-0014b"]["legacy_type"] == "PRD"
    # ...and the shape is a discriminator on a NUMBER, not a licence for any trailing text: the
    # counter-direction of widening a recogniser is that it starts recognising other things.
    assert not migrate.V1_ID_RE.match("TSK-0017 b")
    assert not migrate.V1_ID_RE.match("TSK-b0017")
    assert not migrate.V1_ID_RE.match("TSK-b")


def test_a_binding_to_a_record_of_this_run_is_never_reported_as_free_text(v1_state):
    """B2, second half: a refusal may not call a record of the same run a piece of free text.

    THE MEASURED UNTRUTH, on the field copy of `portfoliomanaigement`: 111 of 157 blocked records
    carried "derives_from 'PRD-...' is not an item id ... free text there binds to nothing", and
    every one of those parents was a record in `product_requirements.yaml` in the same run --
    either waiting for a `--map` or, for the two discriminated ones, invisible to the scanner
    entirely. A reader acting on that message would go looking for free text that is not there.

    RED without `_unsettled_parents`: the writer's own preflight is what produced that sentence,
    and it is right about the VALUE while being wrong about the situation. The counter-direction is
    the second half of this test -- a binding to something this run really holds no record for
    still gets the writer's message, because then it is the true one.
    """
    _v1_id_shape_state(v1_state)
    io.open(os.path.join(v1_state.root, "more_tasks.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "tasks:\n"
        # a parent this run HOLDS and cannot settle by itself: a known type, a status no spec row
        # knows, so it blocks and never becomes an item in this run
        "  PRD-0700: { title: \"unknown status\", status: WEIRD, created: 2026-06-11 }\n"
        "  TSK-0501: { derives_from: PRD-0700, title: \"bound to a blocked record\", status: TODO,"
        " kind: implementation, created: 2026-06-11 }\n"
        # ...and one bound to an id no record of this run carries at all
        "  TSK-0500: { derives_from: PRD-9999, title: \"bound to nothing\", status: TODO,"
        " kind: implementation, created: 2026-06-11 }\n")
    # A FULL FIELD MAP, because a record that still needs a decision never reaches the binding
    # question at all -- that is the verdict one branch earlier, and measuring the branch under
    # test needs the records to get there.
    plan = migrate.build_plan(v1_state, dict(_COMPLETE_MAP), _ARCHIVE_YEAR)
    by_id = {entry["legacy_id"]: entry for entry in plan["records"]}

    held = by_id["TSK-0501"]
    assert held["verdict"] == "blocked", held
    # `binds to nothing` is the writer's claim, in both of `_assert_origins_resolve`'s messages,
    # and it is the untrue half: it is what a reader would act on.
    assert "binds to nothing" not in held["reason"], held["reason"]
    assert "PRD-0700" in held["reason"] and "blocked" in held["reason"], held["reason"]

    phantom = by_id["TSK-0500"]
    assert phantom["verdict"] == "blocked", phantom
    assert "binds to nothing" in phantom["reason"], (
        "a binding to an id no record of this run carries is free text, and the writer's own "
        "message is the true one for it: %s" % phantom["reason"])

    # ...and a parent this run CAN settle settles its child, which is what the new message
    # promises: the discriminated pair comes through the same plan translatable.
    assert by_id["PRD-0014b"]["verdict"] == "translatable", by_id["PRD-0014b"]
    assert by_id["TSK-0017b"]["verdict"] == "translatable", by_id["TSK-0017b"]


# -- a status that is there and unreadable is neither of the other two findings --------------------


def test_a_status_that_is_not_text_blocks_and_is_not_reported_as_a_missing_status(v1_state):
    """R-h: "carries no `status`" is a statement about the record, and it has to be true of it.

    Four records, one document: a boolean (the unquoted `NO` PyYAML reads as False), a number, a
    real absence, and a number on a type no map knows. A known backlog type with an unreadable
    status BLOCKS -- spec II.10's rule for a value a known type cannot be mapped from -- and the
    record with no status at all stays the cross-reference-table finding it was.

    RED without the `_declares_status` / `_status_text` split: the reader demanded a string, so the
    first two were reported as carrying no status, which is untrue about them.
    """
    io.open(os.path.join(v1_state.root, "odd.yaml"), "w", encoding="utf-8", newline="\n").write(
        "processes:\n"
        "  PROC-0801: { title: t, owner: o, steps: [a], status: NO }\n"
        "  PROC-0802: { title: t, owner: o, steps: [a], status: 7 }\n"
        "  PROC-0803: { title: t, owner: o, steps: [a] }\n"
        "  REV-0804: { title: t, status: 7 }\n")
    plan = _planned(v1_state)
    found = {entry["legacy_id"]: entry for entry in plan["records"]
             if entry["source"] == "odd.yaml"}
    assert set(found) == {"PROC-0801", "PROC-0802", "PROC-0803", "REV-0804"}, sorted(found)
    for name in ("PROC-0801", "PROC-0802"):
        assert found[name]["verdict"] == "blocked", found[name]
        assert "carries no" not in found[name]["reason"], found[name]["reason"]
        assert "cannot read" in found[name]["reason"], found[name]["reason"]
    assert found["PROC-0803"]["verdict"] == "not_an_item"
    assert "carries no" in found["PROC-0803"]["reason"]
    # a type no map knows is still not a backlog record, whatever its status looks like
    assert found["REV-0804"]["verdict"] == "not_an_item", found["REV-0804"]
    assert "not text" in found["REV-0804"]["reason"], found["REV-0804"]["reason"]
    assert not migrate.plan_is_executable(plan)


def test_a_record_with_an_unreadable_status_still_claims_its_id(v1_state):
    """The half of R-h that is not about the message: such a record is still a claimant.

    RED without the split as well, and this is the direction that costs data rather than trust: the
    unreadable record fell out of `claimants`, so a SECOND record carrying the same id was the only
    claimant, was translatable, and would have been imported -- one V1 id, two records, and the one
    that got written was the one the reader could parse.
    """
    io.open(os.path.join(v1_state.root, "odd.yaml"), "w", encoding="utf-8", newline="\n").write(
        "processes:\n"
        "  PROC-0805: { title: t, owner: o, steps: [a], status: 7 }\n")
    io.open(os.path.join(v1_state.root, "also.yaml"), "w", encoding="utf-8", newline="\n").write(
        "processes:\n"
        "  PROC-0805: { title: t, owner: o, steps: [a], status: ACTIVE }\n")
    plan = _planned(v1_state)
    both = [entry for entry in plan["records"] if entry["legacy_id"] == "PROC-0805"]
    assert len(both) == 2, both
    assert {entry["verdict"] for entry in both} == {"blocked"}, both
    for entry in both:
        assert "appears 2 times" in entry["reason"], entry["reason"]


# -- the archive column, against the chains the kits really shipped --------------------------------


def _shipped_v1_chain_ends():
    """({prefix: states the chain LEAVES}, {prefix: states it does not}) -- read off the templates.

    THE SAME HEADER LINES `_shipped_v1_stores` finds, read for their ORDER instead of for their
    vocabulary. A V1 chain is written `A -> B -> C / D`: everything after the LAST arrow is a state
    the chain does not leave, everything before it is one it does. That is the whole grammar those
    fourteen header comments use, and it is what makes "the V1 record's life ended here" a fact
    that can be derived rather than a per-row opinion.

    A prefix can carry TWO chains -- `RQ` is both `research_questions.yaml` and the FZulG layer --
    so the two sides are accumulated separately and a state that one chain leaves is not an end
    state even if another chain stops at it.
    """
    commit = _last_v1_commit()
    code, out = _git("ls-tree", "--name-only", "-r", commit)
    assert code == 0, out
    names = [line for line in out.decode("utf-8", "replace").split()
             if "/templates/project_memory/" in line and line.endswith(".yaml")]
    key_re = re.compile(r"^#\s+([A-Z]{2,4})-(?:XXXX|\d{3,}):", re.M)
    field_re = re.compile(r"\bstatus\b", re.I)
    chain_re = re.compile(r"[A-Z][A-Z_]{2,}\s*->\s*[A-Z][A-Z_]{2,}")
    state_re = re.compile(r"[A-Z][A-Z_]{2,}")
    ends, continues = {}, {}
    for name in names:
        code, blob = _git("cat-file", "blob", "%s:%s" % (commit, name))
        assert code == 0, name
        header = "\n".join(line for line in blob.decode("utf-8", "replace").splitlines()
                           if line.startswith("#"))
        key = key_re.search(header)
        chain = [plain for plain in
                 (re.sub(r"\([^)]*\)", "", line) for line in header.splitlines()
                  if field_re.search(line))
                 if chain_re.search(plain)]
        if not chain or not key:
            continue
        line = chain[0]
        tail = line.rsplit("->", 1)[1]
        leaves = set(state_re.findall(tail))
        ends.setdefault(key.group(1), set()).update(leaves)
        continues.setdefault(key.group(1), set()).update(set(state_re.findall(line)) - leaves)
    assert ends, "no V1 status chain was read out of this repository's history"
    return ends, continues


def test_every_archive_candidate_row_follows_the_v1_chain_or_is_recorded():
    """R-b: `archive_candidate` is a RULE with recorded exceptions, not a column of separate calls.

    The rule is stated once above `V1_STATUS_MAPPING`: the flag is True exactly when the V1 value
    is where the V1 record's life ended, which the shipped template's own chain says. This derives
    the chain ends from that history and compares the table against them, so a row that departs
    must be in `ARCHIVE_CANDIDATE_DEVIATIONS` with its reason.

    BOTH ENDS. RED before this round with `("EXP", "DONE")` at False -- the last box of
    `experiment_designs.yaml`, sitting eighty lines below fifteen lines of argument for `("TSK",
    "DONE")` and carrying none of its own, which is exactly what made the column read as a list of
    calls -- and RED equally for a reason left behind for a row that no longer departs.

    What it deliberately does NOT check is where a record LANDS: that is
    `state.migration_archive_status`, which asks this column and the approval bolt, and the two
    answers are kept apart in the imported item (`archive_candidate` beside `written_to`).
    """
    from kernel.backlog_types import ARCHIVE_CANDIDATE_DEVIATIONS

    ends, continues = _shipped_v1_chain_ends()
    departures, unknown = set(), set()
    for (v1_type, v1_status), (_v2t, _v2s, flag) in V1_STATUS_MAPPING.items():
        if v1_type not in ends:
            continue
        if v1_status not in ends[v1_type] | continues.get(v1_type, set()):
            unknown.add((v1_type, v1_status))
            continue
        ended = v1_status in ends[v1_type] and v1_status not in continues.get(v1_type, set())
        if bool(flag) != ended:
            departures.add((v1_type, v1_status))
    assert not unknown, (
        "these rows map a V1 status that appears in no shipped chain, so the rule above the table "
        "cannot be applied to them at all: %s" % sorted(unknown))
    assert departures == set(ARCHIVE_CANDIDATE_DEVIATIONS), (
        "the table and its record of departures disagree. Rows that depart from their V1 chain "
        "with no reason recorded: %s. Reasons recorded for rows that do not depart: %s"
        % (sorted(departures - set(ARCHIVE_CANDIDATE_DEVIATIONS)),
           sorted(set(ARCHIVE_CANDIDATE_DEVIATIONS) - departures)))
    assert all(str(reason).strip() for reason in ARCHIVE_CANDIDATE_DEVIATIONS.values())


def test_a_v1_experiment_that_finished_is_a_finished_record_and_says_where_it_landed(v1_state):
    """R-b, measured on a record rather than on the table: the flag and the routing are two answers.

    `EXP DONE` is the last box of the shipped `experiment_designs.yaml` chain, so the record is
    marked finished -- and `migration_archive_status` still refuses to write `COMPLETED`, because
    that status sits behind the `EXP` approval edge. The item carries both answers, which is what
    lets a reader tell "V1 called this over" from "the import was allowed to say so".

    RED with the flag at False: `archive_candidate` in the written item would say the V1 record was
    not finished, which its own kit's chain contradicts.

    WHERE IT LANDS IS NOW THE OTHER DOOR, and that is DEC-0009 rather than a change to this rule:
    the record is missing `variables`, `success_criteria` and `evidence_refs`, so it is archived as
    unresolved -- at the type's INITIAL status. The refusal that matters is unchanged and is
    asserted directly: `COMPLETED` never reaches a file.
    """
    io.open(os.path.join(v1_state.root, "experiment_designs.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "experiments:\n"
        "  EXP-0001:\n"
        "    title: \"the finished run\"\n"
        "    hypothesis: \"HYP-0001\"\n"
        "    method: \"count them\"\n"
        "    status: DONE\n"
        "    created: 2026-06-11\n")
    plan = _planned(v1_state)
    entry = next(one for one in plan["records"] if one["legacy_id"] == "EXP-0001")
    assert entry["archive_candidate"] is True, entry
    assert entry["verdict"] == "unresolved", entry
    assert not migration_archives("EXP", "EXP", "DONE")
    assert _migrated(v1_state) == 0
    filed = [item for item in _archived_items(v1_state, "EXP")
             if item[migrate.LEGACY_FIELD]["legacy_id"] == "EXP-0001"]
    assert len(filed) == 1, filed
    assert filed[0]["status"] == initial_status("EXP") != "COMPLETED"
    assert filed[0][migrate.LEGACY_FIELD]["legacy_status"] == "DONE"
    assert filed[0][migrate.LEGACY_FIELD]["archive_candidate"] is True


# -- the collision remedy has to be an action that works ------------------------------------------


def test_the_collision_remedy_does_not_offer_a_step_that_changes_nothing(v1_state, capsys):
    """R-g: a printed remedy is a promise, and this one was half false in both directions.

    TWO MEASUREMENTS, not two assertions about wording. First: the run-wide claim. Two records
    sharing an id in ONE document are refused; SPLITTING them into two documents -- the step the
    remedy used to name -- leaves the same two records refused, because the claimants are counted
    over the whole run. Second: the branch that does work. A second document keyed by the records
    of the first (the shape `fzulg_documentation.yaml` really has: the BSFZ layer keys its entries
    by the research question they document) is unblocked by taking that document OUT of the state
    directory, and the report has to say so, because renumbering it would import the documentation
    as a second parallel backlog.

    RED before this round: the printed remedy offered "split the document", which the first
    measurement below refutes.
    """
    def collision_reasons(state):
        printed = migrate.render(_planned(state))
        return [one["reason"] for one in _planned(state)["records"]
                if one["verdict"] == "blocked" and "appears" in one.get("reason", "")], printed

    # Two records, one id, ONE document -- under two different keys, so PyYAML keeps both.
    io.open(os.path.join(v1_state.root, "one.yaml"), "w", encoding="utf-8", newline="\n").write(
        "processes:\n"
        "  PROC-0900: { title: a, owner: bookkeeper, steps: [a], status: ACTIVE }\n"
        "also:\n"
        "  PROC-0900: { title: b, owner: bookkeeper, steps: [b], status: ACTIVE }\n")
    reasons, printed = collision_reasons(v1_state)
    assert len(reasons) == 2, reasons
    assert "over the whole run" in reasons[0], reasons[0]
    assert "move that document out of the state directory" in reasons[0], reasons[0]
    assert "PROC-0900" in printed

    # THE MEASUREMENT: perform the step the old remedy named. Splitting changes nothing.
    os.remove(os.path.join(v1_state.root, "one.yaml"))
    for name, title in (("split_a.yaml", "a"), ("split_b.yaml", "b")):
        io.open(os.path.join(v1_state.root, name), "w", encoding="utf-8", newline="\n").write(
            "processes:\n"
            "  PROC-0900: { title: %s, owner: bookkeeper, steps: [x], status: ACTIVE }\n" % title)
    still, _printed = collision_reasons(v1_state)
    assert len(still) == 2, (
        "splitting the document changed the verdict, so the remedy that named it was right and "
        "this test measures nothing: %s" % still)

    # ...and the step the remedy DOES name works: take the second document out of the state.
    os.remove(os.path.join(v1_state.root, "split_b.yaml"))
    settled, _printed = collision_reasons(v1_state)
    assert not settled, settled
    freed = [one for one in _planned(v1_state)["records"] if one["legacy_id"] == "PROC-0900"]
    assert len(freed) == 1 and freed[0]["verdict"] == "translatable", freed


def test_a_finished_v1_sr_is_archived_at_accepted_with_no_approval_behind_it(v1_state):
    """R-a, end to end: the shape an ABSENT approval edge lets the archive path write.

    `SR DONE` maps to `ACCEPTED`, `approvals.APPROVAL_TRANSITIONS` carries no `SR` row at all, so
    `migration_writable_statuses("SR")` allows it and the record is written straight into
    `archive/SR/<year>/` at `ACCEPTED` with `approval_ref: null`. That is the same shape
    `migration_writable_statuses` describes as the `CR APPLIED` defect one paragraph earlier --
    produced here by an absence rather than by a subtraction, because nothing distinguishes
    "decided: no approval needed" from "the kind was never built", and
    `approvals.required_approval_kinds` records this very edge as "Reported, not bridged".

    THIS TEST PINS THE HOLE, it does not close it: closing it needs an approval KIND with a
    manifest, which is a spec decision. Measured on the field copy of `synaipse`: five records
    stand at `SR DONE` and every one of them is routed to the archive. When the kind is built this
    goes red, and the report that names the hole has to move with it.
    """
    io.open(os.path.join(v1_state.root, "system_requirements.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "requirements:\n"
        "  SR-0001:\n"
        "    title: \"the finished contract\"\n"
        "    contract: \"invoices are filed as PDF/A\"\n"
        "    affected_components: [\"filing\"]\n"
        "    status: DONE\n"
        "    created: 2026-06-11\n")
    assert _migrated(v1_state) == 0
    archived = os.path.join(v1_state.root, "archive", "SR", str(_ARCHIVE_YEAR))
    names = sorted(os.listdir(archived))
    assert len(names) == 1, names
    item = yaml.safe_load(io.open(os.path.join(archived, names[0]), encoding="utf-8"))
    assert item["status"] == "ACCEPTED", item
    assert item["approval_ref"] is None, item
    assert item[migrate.IMPORT_MARK] is True, item
    # ...and nothing anywhere was asked: no approval request of any kind exists in this state, so
    # `ACCEPTED` rests on the missing table row and on nothing else
    pending = os.path.join(v1_state.root, "approvals", "pending")
    requests = [name for name in os.listdir(pending) if name.endswith(".yaml")] \
        if os.path.isdir(pending) else []
    assert not requests, requests
    assert not approvals.required_approval_kinds("SR", "PROPOSED", "ACCEPTED")


# -- SR-0007: the suggestions, and the boundary they stop at ---------------------------------------


def test_a_suggestion_is_printed_with_its_reason_and_still_does_not_run(v1_state, capsys):
    """SR-0007, both halves in one run: the flag is proposed, and the run is still refused.

    RED without `_field_suggestions`/`_suggestion_lines`: the dry run printed
    `--map PROC.roles=<v1_field>` and left the reader to work out which V1 field that is, for every
    project of every dev and office kit. RED in the OTHER direction without the boundary: if the
    plan applied its own suggestion, the office fixture would migrate sixteen procedures on a
    reading nobody confirmed, which is "eine stille Entscheidung mit einem hoeflichen Namen".
    """
    assert _run(v1_state, "migrate", "--dry-run") == 1
    printed = capsys.readouterr().out
    assert "--map PROC.roles=owner" in printed, printed
    reason = migrate.suggested_v1_field("PROC", "roles")[1]
    assert reason in printed, printed
    # THE BOUNDARY IS MEASURED WHERE NOTHING ELSE HOLDS THE RUN BACK: the archive year is given, so
    # the ONLY thing between this plan and a run is the unconfirmed suggestion. Measured with the
    # year left out, this assertion passed on the strength of three dated-nowhere records instead,
    # and a plan that acted on its own suggestions would have gone green through it.
    plan = migrate.build_plan(v1_state, None, _ARCHIVE_YEAR)
    assert not migrate._by_verdict(plan, "blocked"), migrate._by_verdict(plan, "blocked")
    assert not plan["unreadable"]
    assert not migrate.plan_is_executable(plan), "an unconfirmed suggestion executed the run"
    procs = [entry for entry in plan["records"] if entry["legacy_type"] == "PROC"
             and entry["verdict"] == "needs_decision"]
    assert procs, plan["records"]
    for entry in procs:
        assert "roles" in entry["missing_fields"], entry
        assert entry["suggested_fields"]["roles"][0] == "owner", entry
    # ...and the EXECUTING half refuses the very digest the dry run printed
    assert _run(v1_state, "migrate", "--plan", migrate.plan_digest(plan),
                "--archive-year", str(_ARCHIVE_YEAR)) == 1
    assert not [name for name, _p in v1_state.iter_active_items("PROC")]


def test_a_suggestion_is_not_offered_for_a_record_that_does_not_carry_the_field(v1_state):
    """The counter-direction: a row is about a STORE, the proposal is about a RECORD.

    A V1 process that never filled `owner` is answered by nothing, and printing
    `--map PROC.roles=owner` for it would be a flag that carries no value -- the same silence with
    a friendlier name. Such a record has no answer at all, so DEC-0009 archives it instead.

    RED if `_field_suggestions` dropped its "the record carries that field" clause.
    """
    io.open(os.path.join(v1_state.root, "process_definitions.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "processes:\n"
        "  PROC-0001:\n"
        "    title: \"ownerless\"\n"
        "    steps: [\"file it\"]\n"
        "    status: PROPOSED\n"
        "    created: 2026-03-02\n")
    plan = migrate.build_plan(v1_state, None, _ARCHIVE_YEAR)
    entry = next(one for one in plan["records"] if one["legacy_id"] == "PROC-0001")
    assert entry["verdict"] == "unresolved", entry
    assert "suggested_fields" not in entry, entry
    assert entry["unresolved_fields"] == ["roles"], entry


# -- DEC-0009: unresolvable is archived with its reason, not blocked -------------------------------


def test_a_record_no_answer_can_fill_is_archived_with_its_reason_instead_of_blocking(v1_state):
    """DEC-0009: the run proceeds, and the archived item says why it is there.

    A V1 product requirement carries none of `class`, `problem`, `goal`, `invariants`,
    `out_of_scope`, `priority` -- six fields V1 never collected, for which no `--map` names
    anything and no template supports a suggestion. Before DEC-0009 one such record made the whole
    plan unexecutable, which is what left three real projects unmigrated for five rounds.

    RED without the `unresolved` branch: `plan_is_executable` is False and nothing is written.
    RED without `capture_migrated_unresolved`'s own refusal: an item would land in the archive with
    no sentence saying why, and an archived item cannot be brought back to ask.
    """
    io.open(os.path.join(v1_state.root, "product_requirements.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "requirements:\n"
        "  PRD-0001:\n"
        "    title: \"the export\"\n"
        "    description: \"users want a CSV export\"\n"
        "    acceptance_criteria: [\"a CSV appears\"]\n"
        "    status: PROPOSED\n"
        "    created: 2026-02-01\n")
    plan = _planned(v1_state)
    entry = next(one for one in plan["records"] if one["legacy_id"] == "PRD-0001")
    assert entry["verdict"] == "unresolved", entry
    assert set(entry["unresolved_fields"]) == set(REQUIRED_FIELDS["PR"]) - {
        "title", "acceptance_criteria"}, entry
    assert migrate.plan_is_executable(plan), "an unresolvable record still blocks the run"
    printed = migrate.render(plan)
    assert "WOULD BE ARCHIVED AS UNRESOLVED" in printed
    assert "PRD-0001" in printed and "NEED A HUMAN" in printed

    assert _migrated(v1_state) == 0
    filed = [item for item in _archived_items(v1_state, "PR")
             if item[migrate.LEGACY_FIELD]["legacy_id"] == "PRD-0001"]
    assert len(filed) == 1, _archived_paths(v1_state, "PR")
    legacy = filed[0][migrate.LEGACY_FIELD]
    assert "class" in legacy["unresolved"] and "priority" in legacy["unresolved"], legacy
    assert set(legacy["missing_required_fields"]) == set(entry["unresolved_fields"])
    assert filed[0]["status"] == initial_status("PR")
    assert filed[0][migrate.IMPORT_MARK] is True
    assert filed[0]["approval_ref"] is None
    # ...and nothing about it is live: the archive is where it is, and no active item exists
    assert not os.path.exists(v1_state.active_path(filed[0]["id"]))


def test_the_unresolved_door_refuses_a_body_that_does_not_say_why_it_is_there(v1_state):
    """The writer's own bolt, asked directly: DEC-0009's door may not be a general way in.

    RED without the `unresolved` check in `capture_migrated_unresolved_preflight`: any caller
    could write an item into the archive past the whole field contract by claiming a legacy id.
    """
    body = {"title": "no reason given",
            migrate.LEGACY_FIELD: {"legacy_id": "PRD-0001", "record": {}}}
    with pytest.raises(Exception) as refusal:
        v1_state.capture_migrated_unresolved("PR", body, 2026)
    assert "unresolved" in str(refusal.value), refusal.value
    assert not _archived_paths(v1_state, "PR")


def test_a_record_that_is_no_backlog_type_is_never_archived_as_unresolved(v1_state):
    """DEC-0009's other half: what is NOT a backlog record stays a document.

    A dev project's `acceptance_reports.yaml` keys its reports `ACC-nnnn` and its criteria `AC-<n>`,
    each with a status (measured; see `_fill_acceptance_reports`). Archiving one of those would take
    a QA record out of the project and call it a backlog item; it stays `not_an_item`, which is a
    FINAL answer about the record rather than a gap.

    RED if the unresolved branch were reached for a record of a type no contract knows.
    """
    _fill_acceptance_reports(v1_state)
    plan = _planned(v1_state)
    reports = [entry for entry in plan["records"] if entry["legacy_type"] in ("ACC", "AC")]
    assert reports, "the fixture no longer ships a QA report store to measure against"
    for entry in reports:
        assert entry["verdict"] == "not_an_item", entry
        assert "unresolved_fields" not in entry, entry
    assert _migrated(v1_state) == 0
    assert os.path.exists(os.path.join(v1_state.root, "acceptance_reports.yaml"))


# -- SR-0001 / SR-0005: the completion criterion and the move to legacy/ ---------------------------


def test_a_fully_absorbed_v1_store_moves_to_legacy_with_its_hash_in_the_receipt(v1_state):
    """SR-0005: the same thing may not lie in the project twice.

    RED without `_retire_absorbed_documents`: `process_definitions.yaml` stays beside the sixteen
    items that came out of it and `validate` reports SR-0001 for ever, because nothing else in this
    harness removes a V1 record from a kit document.
    """
    source = os.path.join(v1_state.root, "process_definitions.yaml")
    before = hashlib.sha256(open(source, "rb").read()).hexdigest()
    assert _migrated(v1_state) == 0
    moved = os.path.join(v1_state.root, "legacy", "process_definitions.yaml")
    assert not os.path.exists(source)
    assert hashlib.sha256(open(moved, "rb").read()).hexdigest() == before, (
        "the moved document is not the document that was read")
    receipt = v1_state.read_item("DEC-0001")
    assert before in receipt["consequences"], receipt["consequences"]
    assert "legacy/process_definitions.yaml" in receipt["consequences"], receipt["consequences"]
    assert not findings_beside_the_receipts_carrier(v1_state)


def _retirement_state(tmp_path, name):
    """A state whose single V1 document is fully absorbed by one run -- the shortest SR-0005 case."""
    state = _plain_state(tmp_path, name)
    _write_document(state, "a.yaml", _v1_records_text())
    return state


def _one_run(state):
    plan = migrate.build_plan(state, {}, _ARCHIVE_YEAR)
    return migrate.execute(state, plan, migrate.plan_digest(plan))


def test_a_second_document_of_the_same_name_does_not_replace_the_one_already_retired(tmp_path):
    """`os.replace` is atomic AND silent, and SR-0005's move never asked what was there.

    Measured 2026-08-09: a run absorbed `old_procs.yaml`, retired it to `legacy/old_procs.yaml` and
    filed that copy's sha256 in its Decision item. A second document of the same name appeared --
    the field case is a restored backup or a fresh export -- and the second run replaced the
    retired copy. The first receipt's hash then named bytes that exist nowhere, and nothing said
    so: the dry run printed `old_procs.yaml -> legacy/old_procs.yaml` exactly as it had the first
    time.

    THE SAME AUTHORITY THE REMEDIES ARE ASKED ABOUT, one file over: being planned says nothing
    about the landing place being free. It is reported by the dry run (SR-0001's rule that the run
    refuses on nothing the dry run did not name) and asked again one step before the write.

    RED without `occupied_landings`: the second run returns 0, `legacy/old_procs.yaml` holds the
    second document, and the first receipt's hash matches nothing in the state. It is NOT red
    without the second half of that bolt -- the question inside `_retire_absorbed_documents` --
    because the plan built here already carries the occupied landing and `plan_is_executable`
    refuses above the move loop. That half has its own measurement in the test below, and this
    sentence names the seam rather than claiming to cover it.
    """
    state = _retirement_state(tmp_path, "retired_twice")
    first = _one_run(state)
    retired = os.path.join(state.root, "legacy", "a.yaml")
    kept = first["moved"][0]["sha256"]
    assert hashlib.sha256(open(retired, "rb").read()).hexdigest() == kept

    _write_document(state, "a.yaml", _v1_records_text(count=1, first=2))
    plan = migrate.build_plan(state, {}, _ARCHIVE_YEAR)
    assert plan["occupied_landings"] == [["a.yaml", "legacy/a.yaml", kept]], (
        "the row the refusal is built from no longer carries what stands there: %s"
        % plan["occupied_landings"])
    assert not migrate.plan_is_executable(plan)
    printed = migrate.render(plan, state)
    assert "ALREADY TAKEN" in printed and "legacy/a.yaml is already taken" in printed, printed
    with pytest.raises(migrate.MigrationError) as refused:
        migrate.execute(state, plan, migrate.plan_digest(plan))
    assert "already taken" in str(refused.value), refused.value
    assert hashlib.sha256(open(retired, "rb").read()).hexdigest() == kept, (
        "the copy the first run's receipt carries the hash of was replaced after all")

    # ...and the counter-direction: with the retired copy taken out of the state directory -- the
    # remedy the refusal names -- the same second document retires normally.
    os.remove(retired)
    second = _one_run(state)
    assert [doc["path"] for doc in second["moved"]] == ["a.yaml"], second
    assert hashlib.sha256(open(retired, "rb").read()).hexdigest() != kept


def _occupied_report(state):
    """The `ALREADY TAKEN` section of a real dry run over `state`, line by line."""
    printed = migrate.render(migrate.build_plan(state, {}, _ARCHIVE_YEAR), state).splitlines()
    start = next(i for i, line in enumerate(printed) if line.startswith("LANDING PLACE UNDER"))
    end = next((i for i in range(start + 1, len(printed)) if not printed[i].startswith(" ")),
               len(printed))
    return printed[start:end]


def test_the_place_a_taken_landing_is_freed_to_is_named_and_lies_outside_the_state_directory(
        tmp_path):
    """The user's decision of 2026-08-09 on `L35`, carried out instead of argued about.

    WHAT THIS SECTION USED TO SAY: "take the file each line above names on the right out of the
    state directory, from a shell outside the session, then re-run the dry run. Where it goes is
    yours to choose." No destination, and the source gone -- and what the reader carries off is a
    file an EARLIER run put under the kernel's legacy area, whose only other trace is the sha256 in
    that run's Decision item. DEC-0024's second clause forbids exactly this: an instruction may not
    destroy, not even its own source.

    WHY THE PLACE MAY NOT BE THE ONE `deposit_of` NAMES, which is the whole reason there is a
    second construction: the point of this remedy is that the file afterwards is GONE from the
    landing place. A copy under `staging/` would leave it inside the project, and the next run
    would find the same condition it just reported.

    THE THREE PROPERTIES, each measured by doing it and not by reading the sentence:

      * the named place lies OUTSIDE the state directory -- resolved against the state root, not
        judged by how it is spelled;
      * carrying the two steps out in the printed order frees the landing place AND keeps the file:
        the copy is byte-for-byte the original, and the next dry run is executable;
      * two different files that occupy the SAME landing place at different times are sent to two
        different names. That is the chain the digest in the name exists for, and it runs here:
        first occupant copied out and removed, second run retires a different document to the same
        place, and the second instruction may not land on the first copy.

    RED without the construction: with "take the file out of the state directory, where it goes is
    yours to choose" back, the section names no place at all and `_instruction` returns None on
    every line of it. RED with `overflow_deposit_of` reduced to the landing path -- the shape
    `deposit_of` has -- on the last assertion: one name for two files, and the first one is gone.
    """
    state = _retirement_state(tmp_path, "freed_landing")
    first = _one_run(state)
    retired = os.path.join(state.root, "legacy", "a.yaml")
    kept = first["moved"][0]["sha256"]
    _write_document(state, "a.yaml", _v1_records_text(count=1, first=2))

    section = _occupied_report(state)
    named = [one for one in (_instruction(line) for line in section) if one is not None]
    assert len(named) == 1 and len(named[0]) == 1, (
        "the section names %s place(s) to copy the occupant to: %s" % (named, section))
    target = named[0][0]

    # OUTSIDE, ASKED OF THE RESOLVED PATH. A spelling test would agree with any `..` somebody wrote.
    landed = os.path.normcase(os.path.abspath(os.path.join(state.root, *target.split("/"))))
    root = os.path.normcase(os.path.abspath(state.root)) + os.sep
    assert not landed.startswith(root), (
        "the copy the reader is told to make lands inside the state directory: %s" % landed)
    assert target == migrate.overflow_deposit_of("legacy/a.yaml", kept), target

    # THE TWO STEPS, IN THE PRINTED ORDER, on the real filesystem.
    os.makedirs(os.path.dirname(landed))
    shutil.copy(retired, landed)
    assert hashlib.sha256(open(landed, "rb").read()).hexdigest() == kept, (
        "the copy is not the file it was made of")
    os.remove(retired)
    freed = migrate.build_plan(state, {}, _ARCHIVE_YEAR)
    assert freed["occupied_landings"] == [] and migrate.plan_is_executable(freed), (
        "the two steps this section prints do not clear the condition it prints them for: %s"
        % freed["occupied_landings"])
    migrate.execute(state, freed, migrate.plan_digest(freed))
    assert hashlib.sha256(open(retired, "rb").read()).hexdigest() != kept, (
        "the same bytes are back at the landing place, so the line below measures one file")

    # ...AND THE SAME PLACE, TAKEN BY A DIFFERENT FILE, IS SENT SOMEWHERE ELSE. Without the content
    # in the name this second instruction lands on the copy made above and the first file is gone.
    _write_document(state, "a.yaml", _v1_records_text(count=1, first=3))
    again = [one for one in (_instruction(line) for line in _occupied_report(state))
             if one is not None]
    assert len(again) == 1 and len(again[0]) == 1, again
    assert again[0][0] != target, (
        "two files that stood at legacy/a.yaml in turn are sent to one name, so following the "
        "second instruction takes the first one away: %s" % target)
    assert os.path.isfile(landed) and \
        hashlib.sha256(open(landed, "rb").read()).hexdigest() == kept, (
        "the first copy did not survive the second instruction")

    # ...AND THE BRANCH WHERE THE NAME CANNOT BE BUILT AT ALL, because a section that names a place
    # it could not construct would be the worst of the three. The occupant is made unreadable, so
    # `_occupant_digest` has nothing: no place may be named, and no cause may be guessed either --
    # `_is_occupied` counts a directory and a dangling link too, and a remedy that said "give the
    # session read access" would send the reader after the wrong thing for those.
    with _unreadable(retired):
        blind = _occupied_report(state)
        assert [one for one in (_instruction(line) for line in blind) if one is not None] == [], (
            "a place is named for a file this run could not read, so the name cannot carry that "
            "file's content: %s" % blind)
        assert any("could not read" in line for line in blind), blind


def test_the_move_asks_again_when_the_place_was_free_while_the_plan_was_built(tmp_path):
    """The second half of the same bolt, in the only order that reaches it.

    The test above builds its plan when the landing place is ALREADY taken, so
    `plan_is_executable` refuses at the top of `execute` and the move loop is never entered:
    measured 2026-08-09, that test stays GREEN with the question inside
    `_retire_absorbed_documents` removed. What reaches that question is this order -- the place
    free while the plan is built, the file appearing afterwards, the same plan then executed.

    WHAT SPAN IT REALLY GUARDS, and this is why the test drives `execute` directly instead of the
    command line: through the CLI a file appearing between the dry run and the writing run is
    caught earlier, by the digest and by `occupied_landings` in the freshly built plan. The span
    left over is the one inside a single run, between `build_plan` and the move loop, where nothing
    else asks again.

    RED without the `_is_occupied` question in `_retire_absorbed_documents`: `os.replace` takes the
    retired copy away without a word, the run finishes, and the hash the FIRST run's Decision item
    carries names bytes that exist nowhere.
    """
    state = _retirement_state(tmp_path, "taken_after_planning")
    first = _one_run(state)
    retired = os.path.join(state.root, "legacy", "a.yaml")
    kept = first["moved"][0]["sha256"]
    carried = open(retired, "rb").read()
    assert hashlib.sha256(carried).hexdigest() == kept

    _write_document(state, "a.yaml", _v1_records_text(count=1, first=2))
    os.remove(retired)
    plan = migrate.build_plan(state, {}, _ARCHIVE_YEAR)
    assert plan["occupied_landings"] == [], (
        "the plan already knows the place is taken, so this measures the first half again")
    assert migrate.plan_is_executable(plan), "the run refuses above the move loop"

    io.open(retired, "wb").write(carried)         # ...and now something stands there again
    with pytest.raises(migrate.MigrationError) as refused:
        migrate.execute(state, plan, migrate.plan_digest(plan))
    assert "already there" in str(refused.value), refused.value
    assert hashlib.sha256(open(retired, "rb").read()).hexdigest() == kept, (
        "the copy the first run's receipt carries the hash of was replaced after all")
    assert os.path.exists(os.path.join(state.root, "a.yaml")), (
        "the document was moved away even though the run refused the move")


def test_the_move_replaces_a_file_that_appears_between_the_question_and_the_write(tmp_path,
                                                                                 monkeypatch):
    """The entry is `L30` in `docs/POST_V2_WISHLIST.md`.

    The question one step before the write is not the write. Between `_is_occupied` and the
    `os.replace` that carries the document there are two more calls, and `os.replace` has no
    no-clobber variant on either platform this harness runs on -- it replaces what is there,
    atomically and without a word. So a file created inside that window is taken away by a run
    that asked and was told the place was free.

    THE WINDOW IS OCCUPIED DETERMINISTICALLY HERE rather than raced for: `os.makedirs` is the call
    the run makes between the two, so a writer standing in for "something else wrote just now" is
    put there. That is the mechanism itself and not an approximation of it -- what the test cannot
    do is decide how likely the window is, which is why this is an entry in the hole list and not
    a defect report.

    RED the day the move stops being an `os.replace` onto a bare path -- which is the only way to
    close this -- and green while it is one.
    """
    state = _retirement_state(tmp_path, "window")
    plan = migrate.build_plan(state, {}, _ARCHIVE_YEAR)
    assert plan["occupied_landings"] == [] and migrate.plan_is_executable(plan)

    landing = os.path.join(state.root, "legacy", "a.yaml")
    real_makedirs = os.makedirs
    here = os.path.normcase(os.path.abspath(os.path.dirname(landing)))

    def occupy(path, **kwargs):
        real_makedirs(path, **kwargs)
        # ONLY the call the move itself makes: `capture` builds directories too, and occupying one
        # of those would measure something else entirely.
        asked = os.path.normcase(os.path.abspath(str(path).replace("\\\\?\\", "")))
        if asked == here and not os.path.exists(landing):
            io.open(landing, "w", encoding="utf-8", newline="\n").write("somebody else's file\n")

    monkeypatch.setattr(migrate.os, "makedirs", occupy)
    result = migrate.execute(state, plan, migrate.plan_digest(plan))
    monkeypatch.undo()

    assert [doc["path"] for doc in result["moved"]] == ["a.yaml"], result["moved"]
    assert "somebody else's file" not in io.open(landing, encoding="utf-8").read(), (
        "the move no longer replaces what appeared in the window, so this entry is closed")


def test_a_run_that_stops_half_way_through_the_move_says_which_documents_it_moved(tmp_path):
    """The receipt of an interrupted run, about the one thing that run did to a source file.

    Measured 2026-08-09, every condition a real filesystem condition and nothing patched: a state
    holding `a.yaml` (a document an earlier run imported and that was put back, so this run absorbs
    it through `already_imported`) and `sub/b.yaml` (a record this run imports), with a FILE at
    `legacy/sub` so that `os.makedirs` cannot build the second document's landing directory. The
    run moved `a.yaml`, stopped on `sub/b.yaml` -- and its Decision item said

        fully absorbed and moved to legacy/ (every record of them became an item): none
        carried, not translated (left in place, hashes in `context` above): a.yaml

    Two sentences about one file, in canonical state, both false: `a.yaml` was under `legacy/` and
    had been renamed by this very run. The receipt of a half-written run is the one record of what
    happened, so a `none` there is worse than the silence it replaced.

    RED without the caller-held `moved` list: the two lines above come back, and the refusal names
    no moved document either.
    """
    state = _plain_state(tmp_path, "interrupted_move")
    _write_document(state, "a.yaml", _v1_records_text())
    _one_run(state)
    shutil.copy(os.path.join(state.root, "legacy", "a.yaml"),
                os.path.join(state.root, "a.yaml"))
    os.remove(os.path.join(state.root, "legacy", "a.yaml"))
    _write_document(state, "sub/b.yaml", _v1_records_text(count=1, first=2))
    io.open(os.path.join(state.root, "legacy", "sub"), "w", encoding="utf-8",
            newline="\n").write("a file where the second document's landing directory would go\n")

    plan = migrate.build_plan(state, {}, _ARCHIVE_YEAR)
    assert migrate.absorbed_documents(plan) == ["a.yaml", "sub/b.yaml"], plan
    assert migrate.plan_is_executable(plan), (
        "the run refuses before it starts, so nothing below measures an INTERRUPTED one")
    with pytest.raises(migrate.MigrationError) as refused:
        migrate.execute(state, plan, migrate.plan_digest(plan))

    assert not os.path.exists(os.path.join(state.root, "a.yaml")), (
        "nothing was moved, so this measures no interrupted move")
    assert os.path.exists(os.path.join(state.root, "legacy", "a.yaml"))
    assert "a.yaml" in str(refused.value), refused.value

    receipt = yaml.safe_load(io.open(
        sorted(path for _name, path in state.iter_active_items("DEC"))[-1], encoding="utf-8"))
    assert "THE RUN DID NOT FINISH" in receipt["decision"], receipt["decision"]
    moved_line = [line for line in receipt["consequences"].splitlines()
                  if "moved to legacy/" in line]
    carried_line = [line for line in receipt["consequences"].splitlines()
                    if line.startswith("carried")]
    assert len(moved_line) == 1 and "a.yaml -> legacy/a.yaml" in moved_line[0], moved_line
    assert len(carried_line) == 1 and "a.yaml" not in carried_line[0], (
        "a document this run moved and renamed is reported as left in place: %s" % carried_line)


def test_a_partly_translated_store_stays_exactly_where_it_is(v1_state):
    """SR-0005's own limit: only a store with NOTHING of its own left is a double.

    A document one of whose records is still blocked is not a copy of anything -- moving it would
    break every reference to it and hide the record that still needs a hand.

    RED without the `unfinished` clause in `absorbed_documents`.
    """
    io.open(os.path.join(v1_state.root, "process_definitions.yaml"), "a", encoding="utf-8",
            newline="\n").write(
        "  PROC-0099:\n"
        "    title: \"a status nothing maps\"\n"
        "    owner: bookkeeper\n"
        "    steps: [\"do it\"]\n"
        "    status: HALTED\n")
    plan = _planned(v1_state)
    assert not migrate.plan_is_executable(plan)
    assert migrate.absorbed_documents(plan) == []
    still = migrate._documents_still_holding_records(plan)
    assert still["process_definitions.yaml"] == 17, still


def test_a_document_that_only_mentions_ids_is_not_absorbed_by_a_run_it_gave_nothing_to(v1_state):
    """The counter-direction of the same rule, and the one that would lose a business record.

    `acceptance_reports.yaml` and its office cousins key their entries by an id and are reports
    about work, not backlog records. A rule that read "no backlog record left" alone would be
    vacuously true of them and would move them out of the project.

    RED without the "at least one record became an item" clause in `absorbed_documents`.
    """
    io.open(os.path.join(v1_state.root, "acceptance_reports.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "acceptance_reports:\n"
        "  ACC-0001:\n"
        "    proc: PROC-0001\n"
        "    result: pass\n")
    plan = _planned(v1_state)
    assert [entry["verdict"] for entry in plan["records"]
            if entry["source"] == "acceptance_reports.yaml"] == ["not_an_item"]
    assert "acceptance_reports.yaml" not in migrate.absorbed_documents(plan)
    assert _migrated(v1_state) == 0
    assert os.path.exists(os.path.join(v1_state.root, "acceptance_reports.yaml"))


def test_a_later_run_does_not_read_the_retired_store_as_a_v1_source(v1_state):
    """SR-0005: `legacy/` is recorded as already processed -- by being a kernel-written area.

    RED without `state.legacy_root` in `layout.kernel_written_subtrees`: the moved document is a
    kit document again, the next dry run reads sixteen records out of it, every one of them is a
    legacy id the store already holds, and the whole run is blocked by the move that was supposed
    to end the double.
    """
    assert _migrated(v1_state) == 0
    plan = _planned(v1_state)
    assert not [entry for entry in plan["records"] if entry["source"].startswith("legacy/")], plan
    assert not [doc for doc in plan["documents"] if doc["path"].startswith("legacy/")]
    assert not [note for note in plan["unscanned"] if "legacy/" in note]
    assert migrate.plan_is_executable(plan)
    assert not migrate._importable(plan), "a re-run would import the retired store again"


def test_validate_reports_a_kit_document_that_still_holds_v1_backlog_records(v1_state):
    """SR-0001, enforced after the run and not only during it.

    RED without `_check_no_v1_records_outside_the_archive`: a project that puts its V1 monolith
    back -- from git, or by copying an old kit template in -- holds the same records twice and
    every rollup counts one of the two, with nothing anywhere saying which is the state.
    """
    assert _migrated(v1_state) == 0
    assert not findings_beside_the_receipts_carrier(v1_state)
    shutil.copyfile(os.path.join(v1_state.root, "legacy", "process_definitions.yaml"),
                    os.path.join(v1_state.root, "process_definitions.yaml"))
    findings = findings_beside_the_receipts_carrier(v1_state)
    restored = [one for one in findings if one["item"] == "process_definitions.yaml"]
    assert len(restored) == 1, findings
    assert restored[0]["severity"] == "error"
    assert "PROC-0001" in restored[0]["message"], restored[0]


def test_validate_leaves_a_document_that_merely_uses_the_id_shape_alone(v1_state):
    """The counter-direction of SR-0001, and the one that would make the rule unclearable.

    A dev project's `acceptance_reports.yaml` keys its criteria `AC-<n>` with a status (measured;
    see `_fill_acceptance_reports`). `AC` is a backlog type to nobody, the migration reports those
    records and imports none of them, and a validator that flagged the file would demand a
    migration that can never happen.

    RED if the scan asked for the id shape alone instead of `migrate._is_backlog_type`.
    """
    from kernel import report
    reports_path = _fill_acceptance_reports(v1_state)
    payload = yaml.safe_load(io.open(reports_path, encoding="utf-8"))
    criteria = [key for _o, key, record in migrate.scan_document(payload)
                if migrate._declares_status(record)]
    assert criteria, "the fixture's QA store carries no id-shaped record with a status any more"
    assert _migrated(v1_state) == 0
    assert not [one for one in report.validate_state(v1_state)
                if one["item"] == "acceptance_reports.yaml"]


# -- the binding a run did not resolve --------------------------------------------------------------


def test_a_binding_this_run_did_not_resolve_never_lands_on_an_item_wearing_the_number(v1_state):
    """F1: the silent misbinding the collision remedy walks a reader straight into.

    THE ROUTE, end to end and with no unusual data. Two documents claim `PROC-0001`; the run
    refuses both and PRINTS the remedy "move that document out of the state directory". Do it, and
    the parent is no longer a record of the run -- so `_unsettled_parents`, which speaks only about
    records the run HOLDS, says nothing. The child's `derives_from: PROC-0001` is then carried over
    verbatim, and the store already holds a `PROC-0001` that an earlier import created for a
    different V1 record. The kernel accepts it, the item is written bound to the wrong thing, and
    `validate` has nothing to report because the reference resolves.

    RED without `_stolen_bindings`: the child imports and its `derives_from` names the unrelated
    item. Both halves are measured -- the refusal, and (by the test below) that a binding to
    nothing still gets the writer's own true message.
    """
    assert _migrated(v1_state) == 0
    held = sorted(name for name, _p in v1_state.iter_active_items("PROC"))
    assert "PROC-0001" in held, held
    io.open(os.path.join(v1_state.root, "later_tasks.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "tasks:\n"
        "  TSK-0900:\n"
        "    title: \"a child of a record that was taken out of the run\"\n"
        "    derives_from: PROC-0001\n"
        "    owner: bookkeeper\n"
        "    status: TODO\n"
        "    created: 2026-04-01\n")
    plan = _planned(v1_state)
    child = next(one for one in plan["records"] if one["legacy_id"] == "TSK-0900")
    assert child["verdict"] == "blocked", child
    assert "PROC-0001" in child["reason"] and "did not resolve" in child["reason"], child
    assert not migrate.plan_is_executable(plan)
    assert _run(v1_state, "migrate", "--plan", migrate.plan_digest(plan),
                "--map", "PROC.roles=owner", "--archive-year", str(_ARCHIVE_YEAR)) == 1
    assert sorted(name for name, _p in v1_state.iter_active_items("TSK")) == []


def test_a_record_that_is_both_oversized_and_unsettled_reports_its_own_size(v1_state):
    """The order of the refusals, as a property rather than as a sentence in a comment.

    A defect INSIDE the record is named before one that is about another record, so settling the
    parent can never move a record from one refusal straight into the next. Measured on `synaipse`
    (2026-08-05): five records do not fit in one item; with the order reversed each of them would
    have reported its parent first and its size only on the following run.

    RED with the two branches swapped.
    """
    bulk = "x" * 40000
    io.open(os.path.join(v1_state.root, "chain.yaml"), "w", encoding="utf-8", newline="\n").write(
        "processes:\n"
        "  PROC-0801:\n"
        "    title: \"the parent, blocked by a status nothing maps\"\n"
        "    owner: bookkeeper\n"
        "    steps: [\"do it\"]\n"
        "    status: HALTED\n"
        "    created: 2026-01-05\n"
        "  PROC-0802:\n"
        "    title: \"the child, far too large\"\n"
        "    owner: bookkeeper\n"
        "    derives_from: PROC-0801\n"
        "    steps: [\"%s\"]\n"
        "    status: PROPOSED\n"
        "    created: 2026-01-06\n" % bulk)
    plan = _planned(v1_state)
    parent = next(one for one in plan["records"] if one["legacy_id"] == "PROC-0801")
    assert parent["verdict"] == "blocked", parent
    child = next(one for one in plan["records"] if one["legacy_id"] == "PROC-0802")
    assert child["verdict"] == "blocked", child
    assert "does not fit in one item" in child["reason"], child
    assert "PROC-0801" not in child["reason"], child


# -- the recogniser, and an INDEPENDENT count of what it may not miss ------------------------------


def test_the_recogniser_reads_every_id_width_a_hand_kept_list_produces(v1_state):
    """B2 again, one direction further: a V1 number of one or two digits is still a V1 number.

    Measured on the field copy of `synaipse` (2026-08-05): `acceptance_reports.yaml` holds 60
    `AC-<n>` keys with one-digit numbers, nested inside the `ACC-nnnn` records they belong to, and
    every one of them appeared under NO heading of the dry run. The module's own head promises it
    never produces that silence, and its recogniser's own comment says the number has no fixed
    width -- while the pattern demanded three digits.

    RED with a three-digit minimum: `SR-7` and `AC-1` below get no verdict at all.
    """
    io.open(os.path.join(v1_state.root, "narrow.yaml"), "w", encoding="utf-8", newline="\n").write(
        "reports:\n"
        "  ACC-0001:\n"
        "    criteria:\n"
        "      AC-1: {text: \"the first one\"}\n"
        "      AC-12: {text: \"the twelfth\"}\n"
        "  SR-7:\n"
        "    title: \"a hand-numbered requirement\"\n"
        "    derives_from: PRD-0001\n"
        "    status: DRAFT\n")
    plan = migrate.build_plan(v1_state, None, _ARCHIVE_YEAR)
    seen = {entry["legacy_id"]: entry for entry in plan["records"]
            if entry["source"] == "narrow.yaml"}
    assert set(seen) == {"ACC-0001", "AC-1", "AC-12", "SR-7"}, sorted(seen)
    assert seen["AC-1"]["verdict"] == "not_an_item", seen["AC-1"]
    # ...and a one-digit id of a BACKLOG type is read as the backlog record it is, not merely seen
    assert seen["SR-7"]["legacy_type"] == "SR", seen["SR-7"]
    assert seen["SR-7"]["legacy_status"] == "DRAFT", seen["SR-7"]
    assert seen["SR-7"]["verdict"] != "not_an_item", seen["SR-7"]


# A DELIBERATELY WIDER READER THAN THE ONE UNDER TEST, in two independent dimensions.
#
# THE ID SHAPE: any case, `_` as well as `-`, one or two digits as well as three or more, and a
# prefix of any length -- each direction one the field reading of 2026-08-05 named.
# `migrate.V1_ID_RE` is a strict subset of this pattern.
#
# THE POSITION: every mapping is asked for BOTH names it could carry (its key and its own `id`
# field), wherever it lies. That half used to mirror the code under test exactly -- key for a
# mapping value, `id` field for a list member -- so the two shared a blind spot and the count could
# not see it: `synaipse`'s `wording_correction_needed: {id: "OQ-1", status: closed}` was missing
# from both sides, and the difference this test judges was empty for a record neither reader found.
# A comparison is only a measurement where the two readers were built apart.
_WIDE_ID_RE = re.compile(r"([A-Za-z]{2,})[-_](\d+)([A-Za-z][A-Za-z0-9]*)?\Z")

# The narrow reader's own shape, spelled independently of `migrate.V1_ID_RE` so that the judgement
# below is a statement about the CONVENTION (upper case, `-`, two to four letters) and not a second
# read of the object under test.
_NARROW_SHAPE = re.compile(r"[A-Z]{2,4}-\d+([A-Za-z][A-Za-z0-9]*)?\Z")


def _wide_records(payload):
    """[(id, mapping)] for everything id-SHAPED under the wide rule, at any nesting.

    Written as "every mapping, both of its possible names", which is the definition rather than a
    walk over positions -- see the comment above `_WIDE_ID_RE` for why the position half has to be
    built independently of the code under test.
    """
    found, seen = [], set()

    def wide(text):
        return text.strip() if isinstance(text, str) and _WIDE_ID_RE.match(text.strip()) else None

    def walk(node, keyed_as=None):
        if not isinstance(node, (dict, list)):
            return
        fresh = id(node) not in seen
        if isinstance(node, dict):
            if keyed_as is not None:
                found.append((keyed_as, node))
            declared = wide(node.get("id"))
            if declared is not None and declared != keyed_as and fresh:
                found.append((declared, node))
        if not fresh:
            return
        seen.add(id(node))
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, wide(key))
        else:
            for item in node:
                walk(item)

    walk(payload)
    return found


def test_the_plan_names_every_id_shaped_record_the_wider_reader_finds(v1_state):
    """The completeness proof, run with a recogniser that REALLY contains the one under test.

    Two counts over the same state directory, and every difference is named and judged here rather
    than absorbed into a tolerance:

      * ONE OR TWO DIGITS -- a real blind spot of the narrow reader, and the reason `V1_ID_RE` no
        longer demands three. Measured on `synaipse`: 60 records. It is closed, so this difference
        must be EMPTY, and `SR-7`/`AC-12` below are what would show it coming back.
      * NOT THE V1 CONVENTION -- lower case, or `_` as the separator. `unavailable_503` and
        `tablet_768` in a real `design.yaml` are a screen state and a breakpoint width. The WIDE
        reader is wrong about those, not the narrow one, so they are judged out by the property
        (they are not spelled the way V1 spelled an id) rather than by naming the two of them.
      * A PREFIX LONGER THAN FOUR LETTERS -- a residual, measured rather than assumed away: across
        all three field copies the wide reader finds no such record. The narrow reader would miss
        one, this test says so by requiring the class to be non-empty in the fixture, and closing
        it is not free -- two `SECTION-1` notes in different documents would then collide under
        the claimant rule and block a run. It is named here and left open.
      * A MAPPING IN A VALUE POSITION NAMING ITSELF IN ITS OWN `id` FIELD -- the third id form, and
        for a round it was a blind spot of BOTH readers, so this count could not see it. Measured
        on the field copy of `synaipse` (2026-08-05): `wording_correction_needed: {id: "OQ-1",
        status: closed}` in `review_reports.yaml`. It is closed, so this difference must be EMPTY,
        and `OQ-9` below is what would show it coming back.
    """
    io.open(os.path.join(v1_state.root, "widths.yaml"), "w", encoding="utf-8", newline="\n").write(
        "notes:\n"
        "  SR-7: {title: \"one digit\", derives_from: PRD-0001, status: DRAFT}\n"
        "  AC-12: {text: \"two digits, no status\"}\n"
        "  unavailable_503: {label: \"a screen state, not an id\"}\n"
        "  tablet_768: {width: 768}\n"
        "  SECTION-1: {text: \"a long prefix, which the narrow reader does not read\"}\n"
        "  wording_correction_needed: {id: \"OQ-9\", status: closed}\n")
    plan = migrate.build_plan(v1_state, None, _ARCHIVE_YEAR)
    narrow = collections.Counter((entry["source"], entry["legacy_id"])
                                 for entry in plan["records"])
    wide = collections.Counter()
    for current, _dirs, files in os.walk(v1_state.root):
        for name in sorted(files):
            path = os.path.join(current, name)
            rel = os.path.relpath(path, v1_state.root).replace(os.sep, "/")
            if not rel.lower().endswith((".yaml", ".yml")):
                continue
            if any(part.startswith(".") for part in rel.split("/")):
                continue
            payload = yaml.safe_load(io.open(path, encoding="utf-8"))
            for key, _record in _wide_records(payload):
                wide[(rel, key)] += 1
    assert not (narrow - wide), (
        "the narrow reader found something the wider one did not, so the wider one is not wider "
        "and this measurement is worthless: %s" % sorted(narrow - wide))
    difference = sorted((wide - narrow).elements())
    not_the_convention = [key for key in difference if not _NARROW_SHAPE.match(key[1])]
    long_prefix = [key for key in difference if re.match(r"[A-Z]{5,}-\d", key[1])]
    judged = set(not_the_convention) | set(long_prefix)
    assert judged == set(difference), (
        "a difference between the two counts falls into neither judged class, so it is a silence "
        "nobody has looked at: %s" % sorted(set(difference) - judged))
    assert long_prefix, "the residual this test names is not in the fixture any more"
    assert ("widths.yaml", "SR-7") not in set(difference)
    assert ("widths.yaml", "AC-12") not in set(difference)
    assert ("widths.yaml", "OQ-9") not in set(difference)


def test_a_binding_to_a_record_the_run_read_but_will_not_import_says_so(v1_state):
    """The writer's refusal is true and incomplete, so it is ANNOTATED and not replaced.

    Measured on the field copy of `synaipse` (2026-08-05): `TSK-0063` names `derives_from: SR-0096`
    and `SR-0096` sits in `system_requirements.yaml` carrying no `status`. The kernel says "SR-0096
    does not exist", which is true of the V2 state -- and a reader following it would go looking
    for a record that is right there in the file they just read.

    RED without `_seen_but_not_an_item`. The counter-direction is measured in the same run: the
    REMEDY the writer gives is still in the message, because a `not_an_item` verdict is final and
    "settle that record first" would send a reader after something with nothing to settle.
    """
    io.open(os.path.join(v1_state.root, "chain.yaml"), "w", encoding="utf-8", newline="\n").write(
        "processes:\n"
        "  PROC-0700:\n"
        "    title: \"a note, not a process\"\n"
        "    owner: bookkeeper\n"
        "  PROC-0701:\n"
        "    title: \"the child of a note\"\n"
        "    owner: bookkeeper\n"
        "    derives_from: PROC-0700\n"
        "    steps: [\"do it\"]\n"
        "    status: PROPOSED\n"
        "    created: 2026-05-05\n")
    plan = _planned(v1_state)
    note = next(one for one in plan["records"] if one["legacy_id"] == "PROC-0700")
    assert note["verdict"] == "not_an_item", note
    child = next(one for one in plan["records"] if one["legacy_id"] == "PROC-0701")
    assert child["verdict"] == "blocked", child
    assert "does not exist" in child["reason"], child["reason"]
    assert "DID read `PROC-0700`" in child["reason"], child["reason"]
    assert "chain.yaml" in child["reason"], child["reason"]


def test_a_run_that_archives_every_root_item_says_so_before_it_writes(v1_state):
    """DEC-0009's cost, made visible at the one moment it can still be acted on.

    Measured on both dev field copies (2026-08-05): every V1 product requirement lacks `class`,
    `problem`, `goal`, `invariants`, `out_of_scope` and `priority`, so every one of them is
    archived -- 21 in one project and 17 in the other -- and the migrated project holds no active
    `PR` file at all. The kits' setup-phase predicate reads exactly that file's presence, so five
    gates that ask it treat the repo as one that has not started yet.

    RED without `_root_items_after` and its section: the run does the same thing and says nothing,
    and no kernel operation brings an archived item back.

    THE COUNTER-DIRECTION IS IN THE SAME TEST: with ONE requirement that keeps its fields, the
    warning must not appear -- a report that cries wolf on every migration is a report a reader
    learns to skip.
    """
    io.open(os.path.join(v1_state.root, "product_requirements.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "requirements:\n"
        "  PRD-0001:\n"
        "    title: \"the export\"\n"
        "    acceptance_criteria: [\"a CSV appears\"]\n"
        "    status: PROPOSED\n"
        "    created: 2026-02-01\n")
    plan = _planned(v1_state)
    assert plan["root_items_after"]["PR"] == [0, 1], plan["root_items_after"]
    printed = migrate.render(plan)
    assert "HOLDS NO ACTIVE PR ITEM" in printed, printed

    io.open(os.path.join(v1_state.root, "product_requirements.yaml"), "a", encoding="utf-8",
            newline="\n").write(
        "  PRD-0002:\n"
        "    title: \"the import\"\n"
        "    class: technical_enabler\n"
        "    problem: \"no import\"\n"
        "    goal: \"an import\"\n"
        "    acceptance_criteria: []\n"
        "    invariants: []\n"
        "    out_of_scope: []\n"
        "    priority: high\n"
        "    status: PROPOSED\n"
        "    created: 2026-02-02\n")
    plan = _planned(v1_state)
    assert plan["root_items_after"]["PR"] == [1, 1], plan["root_items_after"]
    assert "HOLDS NO ACTIVE PR ITEM" not in migrate.render(plan)


def test_two_records_of_a_type_no_contract_knows_do_not_collide_over_an_id(v1_state):
    """A collision is a conflict about which ITEM gets a legacy id, so it is about backlog records.

    Measured on the field copy of `synaipse` (2026-08-05), and it is the counter-defect of reading
    one- and two-digit numbers: `acceptance_reports.yaml` keys six of its acceptance criteria
    `AC-1` with `status: met` -- once per report, because the numbering is per report -- and the
    run refused sixty records and with them the whole migration. No `--map` and no renumbering
    could have helped: the ids are each report's own criterion numbering, and `AC` is a type this
    command never imports.

    RED without the `_is_backlog_type` clause in the claimant count. The counter-direction is the
    neighbouring test `test_two_records_with_one_legacy_id_are_refused_rather_than_merged`, where
    the colliding records ARE of a backlog type and the refusal has to stay.
    """
    io.open(os.path.join(v1_state.root, "reports.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "reports:\n"
        "  REP-0001:\n"
        "    criteria:\n"
        "      AC-1: {text: \"the first criterion of the first report\", status: met}\n"
        "  REP-0002:\n"
        "    criteria:\n"
        "      AC-1: {text: \"the first criterion of the second report\", status: met}\n")
    plan = _planned(v1_state)
    criteria = [entry for entry in plan["records"] if entry["legacy_id"] == "AC-1"]
    assert len(criteria) == 2, criteria
    assert {entry["verdict"] for entry in criteria} == {"not_an_item"}, criteria
    assert migrate.plan_is_executable(plan), [
        entry for entry in plan["records"] if entry["verdict"] == "blocked"]

# -- the third id position, and the three readers that have to agree about it -----------------------


def test_a_mapping_that_names_itself_in_a_value_position_is_found_by_all_three_readers(v1_state):
    """B2: the id form that fell between the two the code read, and the silence it produced.

    THE SHAPE IS FIELD DATA. Measured on the field copy of `synaipse` (2026-08-05), in
    `review_reports.yaml`: a mapping in a VALUE position, naming itself in its own `id` field and
    carrying a status. The reader consulted that field for LIST members only, so such a record
    appeared under no heading of the dry run, in no `validate` finding and in no completeness
    count -- and a reader cannot tell that from an absence, which is the one outcome the module
    head says this command may not produce.

    THREE READERS, ONE ANSWER, which is why the fixture carries a BACKLOG-typed record of the same
    shape as well: `scan_document` answers the dry run, `report.validate_state`'s SR-0001 sweep and
    the completeness proof, so closing this in one of them would leave the others blind.

    RED without the widened `scan_document`: the plan holds neither record, the rendered dry run
    names neither, and `validate` reports nothing about the file that holds them.
    """
    from kernel import report
    io.open(os.path.join(v1_state.root, "review_reports.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "reviews:\n"
        "  gate_one:\n"
        "    wording_correction_needed:\n"
        "      id: \"OQ-1\"\n"
        "      status: closed\n"
        "    the_procedure_it_is_about:\n"
        "      id: \"PROC-0900\"\n"
        "      title: \"a process named in its own field\"\n"
        "      owner: bookkeeper\n"
        "      trigger: \"inbox drop\"\n"
        "      steps: [\"file it\"]\n"
        "      status: PROPOSED\n"
        "      created: 2026-05-05\n")
    plan = _planned(v1_state)
    found = {entry["legacy_id"]: entry for entry in plan["records"]
             if entry["source"] == "review_reports.yaml"}
    assert set(found) == {"OQ-1", "PROC-0900"}, sorted(found)
    # the one whose type no contract knows is REPORTED and blocks nothing...
    assert found["OQ-1"]["verdict"] == "not_an_item", found["OQ-1"]
    # ...and the one that IS a backlog record is read as one, in the same position
    assert found["PROC-0900"]["verdict"] == "translatable", found["PROC-0900"]
    assert found["PROC-0900"]["legacy_status"] == "PROPOSED", found["PROC-0900"]

    printed = migrate.render(plan)
    assert "OQ-1" in printed and "PROC-0900" in printed, printed

    # ...and the completion criterion `validate` enforces afterwards reads the same records
    findings = [one for one in report.validate_state(v1_state)
                if one["item"] == "review_reports.yaml"]
    assert len(findings) == 1, findings
    assert "PROC-0900" in findings[0]["message"], findings[0]


def test_one_mapping_may_not_be_imported_as_two_items_over_two_names(v1_state):
    """The counter-defect of reading both positions: a mapping that names itself twice, differently.

    A record names itself by the key it is filed under AND by its own `id` field. Where the two
    agree it is one record; where they disagree, importing it would put ONE V1 mapping into the
    store as TWO items, and dropping either name would make it invisible to this report. So both
    names are reported and the record is refused.

    RED without the `self_named` branch in `build_plan`: the two entries are classified
    independently and both come out translatable, so the plan promises two items for one mapping.

    THE COUNTER-DIRECTION IS IN THE SAME RUN, twice: a mapping whose key and `id` field AGREE is
    one ordinary record and is imported, and a mapping of a type no contract knows wearing two
    names blocks nothing -- it never becomes an item, so it cannot become two.
    """
    io.open(os.path.join(v1_state.root, "twins.yaml"), "w", encoding="utf-8", newline="\n").write(
        "processes:\n"
        "  PROC-0801:\n"
        "    id: \"PROC-0802\"\n"
        "    title: \"a mapping wearing two numbers\"\n"
        "    owner: bookkeeper\n"
        "    trigger: t\n"
        "    steps: [\"s\"]\n"
        "    status: PROPOSED\n"
        "    created: 2026-05-05\n"
        "  PROC-0803:\n"
        "    id: \"PROC-0803\"\n"
        "    title: \"the ordinary shape -- the key repeated inside the entry\"\n"
        "    owner: bookkeeper\n"
        "    trigger: t\n"
        "    steps: [\"s\"]\n"
        "    status: PROPOSED\n"
        "    created: 2026-05-05\n"
        "  AC-4:\n"
        "    id: \"AC-5\"\n"
        "    text: \"a criterion wearing two numbers\"\n"
        "    status: met\n")
    plan = _planned(v1_state)
    found = {}
    for entry in plan["records"]:
        if entry["source"] == "twins.yaml":
            found.setdefault(entry["legacy_id"], []).append(entry)
    assert sorted(found) == ["AC-4", "AC-5", "PROC-0801", "PROC-0802", "PROC-0803"], sorted(found)
    for name in ("PROC-0801", "PROC-0802"):
        assert [one["verdict"] for one in found[name]] == ["blocked"], found[name]
        assert "PROC-0801" in found[name][0]["reason"], found[name][0]["reason"]
        assert "PROC-0802" in found[name][0]["reason"], found[name][0]["reason"]
    # the ordinary shape stays ONE record and is not refused for repeating its own key
    assert [one["verdict"] for one in found["PROC-0803"]] == ["translatable"], found["PROC-0803"]
    # ...and a record that never becomes an item cannot become two
    for name in ("AC-4", "AC-5"):
        assert [one["verdict"] for one in found[name]] == ["not_an_item"], found[name]


# -- the budget, asked only where it is enforced ----------------------------------------------------


def _oversized_procedure(state, name, number, status):
    """One V1 procedure, far past spec II.5's per-item budget, at the V1 status given."""
    io.open(os.path.join(state.root, name), "w", encoding="utf-8", newline="\n").write(
        "processes:\n"
        "  PROC-%04d:\n"
        "    title: \"Oversized %d\"\n"
        "    trigger: \"inbox drop\"\n"
        "    owner: bookkeeper\n"
        "    steps:\n%s"
        "    status: %s\n"
        "    created: 2026-03-01\n"
        % (number, number, "".join('      - "%s"\n' % ("x" * 200) for _ in range(120)), status))


def test_an_archive_bound_record_is_not_held_back_by_a_budget_nothing_measures(v1_state):
    """B3: a size limit is checked where it is enforced, and nowhere else.

    `report.validate_state` walks the ACTIVE items and measures each file against spec II.5; no
    reader in this harness measures a file under `archive/`. Holding an archive-bound record back
    "because `validate` reports anything above that as an error" was therefore a refusal with an
    untrue reason -- measured on the field copy of `synaipse` (2026-08-05): of its 22 blocked
    records, 8 were archive-bound records the size check held back, and the run refused wholesale
    over them. DEC-0009's answer for that class is the archive, not a person sent to edit business
    data; with the clause in place 14 blocked records remain, all of them active-bound or blocked
    for another reason.

    RED without the `target == "archive"` clause in `_settle_bindings`: the RETIRED procedure is
    blocked and the whole run refuses.

    THE SECOND HALF IS A MEASUREMENT AND NOT AN ASSERTION ABOUT ONE: the archived item really is
    written, really is bigger than the cap, and the RUNNING validator really does report nothing
    about it. The ACTIVE-bound direction is the neighbouring
    `test_a_record_too_large_for_one_item_blocks_instead_of_being_written`, which is what keeps
    this from being read as "the budget was dropped".
    """
    from kernel import report
    _oversized_procedure(v1_state, "oversized.yaml", 900, "RETIRED")
    plan = _planned(v1_state)
    archived = next(one for one in plan["records"] if one["legacy_id"] == "PROC-0900")
    assert archived["verdict"] == "translatable" and archived["target"] == "archive", archived
    assert migrate.plan_is_executable(plan), migrate._by_verdict(plan, "blocked")
    assert _migrated(v1_state) == 0
    written = [path for path in _archived_paths(v1_state, "PROC")
               if yaml.safe_load(io.open(path, encoding="utf-8"))[
                   migrate.LEGACY_FIELD]["legacy_id"] == "PROC-0900"]
    assert len(written) == 1, written
    assert os.path.getsize(written[0]) > report.ITEM_MAX_BYTES, (
        "the fixture no longer exceeds the cap, so this test measures nothing")
    errors = [one for one in report.validate_state(v1_state) if one["severity"] == "error"]
    assert not errors, errors


# -- every record that needs a human is NAMED -------------------------------------------------------

# The span the two grouped sections used to print instead of naming their records. Spelled as the
# SHAPE rather than as a substring, because the report's prose carries `...` of its own and an
# assertion on two dots would have been green for the wrong reason.
_SPAN_RX = re.compile(r"\S+ \.\. \S+ \(\d+\)")


def test_every_record_that_needs_a_human_is_named_and_not_spanned(v1_state):
    """B4: "namentlich" means every id, not the first and the last of a range.

    The two grouped sections printed `first .. last (n)`. Measured on the field copy of
    `portfoliomanaigement` (2026-08-05): 23 of 78 ids named, 55 not -- and the spans were unsorted,
    so the rest could not be inferred from them either. A reader who is supposed to learn from this
    report WHICH records need a person learned 23 of them.

    RED without `_named_ids`: only the first and last legacy id of each group appear in the text.

    BOTH SECTIONS, because both answer that question: `needs_decision` is a question with a
    suggestion beside it, and `unresolved` is a record DEC-0009 archives unless somebody acts.
    """
    io.open(os.path.join(v1_state.root, "many.yaml"), "w", encoding="utf-8", newline="\n").write(
        "processes:\n" + "".join(
            "  PROC-%04d:\n"
            "    title: \"Process %d\"\n"
            "    trigger: t\n"
            "    owner: bookkeeper\n"
            "    steps: [\"s\"]\n"
            "    status: PROPOSED\n"
            "    created: 2026-04-01\n" % (700 + n, n) for n in range(12)))
    # no `--map`, so `PROC.roles` is a decision with a suggestion beside it
    printed = migrate.render(migrate.build_plan(v1_state, {}, _ARCHIVE_YEAR))
    wanted = ["PROC-%04d" % (700 + n) for n in range(12)]
    missing = [one for one in wanted if one not in printed]
    assert not missing, "%s not named in the report:\n%s" % (missing, printed)
    assert not _SPAN_RX.search(printed), "a span survived in the report:\n%s" % printed

    # ...and the section a run does NOT stop for, which is the one DEC-0009 archives
    io.open(os.path.join(v1_state.root, "many.yaml"), "w", encoding="utf-8", newline="\n").write(
        "tasks:\n" + "".join(
            "  TSK-%04d:\n"
            "    title: \"Task %d\"\n"
            "    status: TODO\n"
            "    created: 2026-04-01\n" % (700 + n, n) for n in range(12)))
    plan = _planned(v1_state)
    unresolved = [one["legacy_id"] for one in plan["records"]
                  if one["verdict"] == "unresolved" and one["source"] == "many.yaml"]
    assert len(unresolved) == 12, unresolved
    printed = migrate.render(plan)
    missing = [one for one in unresolved if one not in printed]
    assert not missing, "%s not named in the report:\n%s" % (missing, printed)
    assert not _SPAN_RX.search(printed), "a span survived in the report:\n%s" % printed


# -- the project a run leaves without a root item ---------------------------------------------------


def _one_rejected_requirement(state):
    """A V1 product requirement the mapping table calls FINISHED -- the FIRST archive door.

    Asked of `state.migration_archives` rather than asserted: that is the judge `migrate` routes
    on, and a table change then fails here instead of silently moving this test onto the other
    door -- which is exactly what left the clause below unmeasured.
    """
    assert migration_archives("PR", "PRD", "REJECTED"), (
        "the shipped tables no longer archive any finished ROOT record, so this test would "
        "measure DEC-0009's door instead of the finished-record one")
    io.open(os.path.join(state.root, "product_requirements.yaml"), "w", encoding="utf-8",
            newline="\n").write(
        "requirements:\n"
        "  PRD-0001:\n"
        "    title: \"the export nobody wanted\"\n"
        "    status: REJECTED\n"
        "    created: 2026-02-01\n")


def test_a_root_record_archived_through_the_finished_door_still_empties_the_project(v1_state):
    """B6: the clause that keeps the root warning true, and the mutation it survived.

    `_root_items_after` counts as LIVE only what stays under `active/`. Drop the
    `target != "archive"` half of that condition and a root record archived through the FIRST door
    -- finished in V1 -- counts as a live root item, so the warning falls silent for exactly the
    project it is about. Every other test of the warning archives its requirements through
    DEC-0009's second door, where the mutation makes no difference, which is why that clause came
    through a mutation run untouched.

    RED with that clause removed: `root_items_after["PR"]` reads `[1, 1]` and the section is gone.
    """
    _one_rejected_requirement(v1_state)
    plan = _planned(v1_state)
    requirement = next(one for one in plan["records"] if one["legacy_id"] == "PRD-0001")
    assert requirement["verdict"] == "translatable", requirement
    assert requirement["target"] == "archive", requirement
    assert "unresolved_fields" not in requirement, requirement
    assert plan["root_items_after"]["PR"] == [0, 1], plan["root_items_after"]
    assert "HOLDS NO ACTIVE PR ITEM" in migrate.render(plan)


def test_the_root_item_warning_names_its_consequence_and_is_printed_where_it_writes(v1_state,
                                                                                    capsys):
    """Two defects in one section: it named the STATE, and only the reading half printed it.

    It said the project would answer the setup-phase predicate the way a fresh one does, and left
    the reader to work out that the gates built on that predicate then stop applying. And the half
    of the command that actually PRODUCES that state printed nothing at all, so a run driven from a
    script -- or read back from a scrollback -- never saw it.

    RED without `root_item_warnings` and its caller in `cli`: the executing run's output carries no
    warning at all, and the dry run's names no consequence.

    WHAT THE CONSEQUENCE SENTENCE CLAIMS IS MEASURED NEXT DOOR, against the shipped gate as a
    process -- `test_a_project_left_without_a_root_item_really_does_open_the_merge_gate`.
    """
    _one_rejected_requirement(v1_state)
    assert _run(v1_state, "migrate", "--dry-run", "--map", "PROC.roles=owner",
                "--archive-year", str(_ARCHIVE_YEAR)) == 0
    dry = capsys.readouterr().out
    assert "HOLDS NO ACTIVE PR ITEM" in dry, dry
    assert "git merge" in dry and "git push" in dry, dry

    assert _migrated(v1_state) == 0
    written = capsys.readouterr().out
    assert "HOLDS NO ACTIVE PR ITEM" in written, written
    assert "git merge" in written and "git push" in written, written


def test_a_project_left_without_a_root_item_really_does_open_the_merge_gate(v1_state):
    """The consequence that warning names, measured on the shipped gate instead of described.

    The dry run tells a reader that the gates built on the setup-phase predicate stop applying
    after this run, and names the merge/push one among them. That is a claim about running code, so
    it is measured as one: the dev kit's own `gate_git.py`, as a process, against the state this
    migration leaves behind.

    The counter-direction is the second half: capture one active root item into the same state and
    the same merge is refused again, so "allowed" cannot be the hook exiting on something else.
    """
    hook = os.path.join(ROOT, "team-kits", "dev-team", "hooks", "gate_git.py")
    repo = os.path.dirname(v1_state.root)

    def merge(item_id):
        return subprocess.run(
            [sys.executable, hook],
            input=json.dumps({"tool_name": "Bash",
                              "tool_input": {"command": "git merge feat/%s-x" % item_id},
                              "cwd": repo}),
            capture_output=True, text=True,
            env=dict(os.environ, CLAUDE_PROJECT_DIR=repo,
                     HARNESS_KERNEL_PATH=os.path.join(ROOT, "team-kits")),
            timeout=120)

    _one_rejected_requirement(v1_state)
    assert _migrated(v1_state) == 0
    assert not [one for one, _path in v1_state.iter_active_items("PR")], (
        "the run left an active PR, so this measures nothing")
    allowed = merge("PR-0001")
    assert allowed.returncode == 0, allowed.stderr

    live = v1_state.capture("PR", {"title": "a live requirement", "class": "technical_enabler",
                                   "problem": "p", "goal": "g", "acceptance_criteria": [],
                                   "invariants": [], "out_of_scope": [], "priority": "high"})
    refused = merge(live["id"])
    assert refused.returncode == 2, refused.stdout + refused.stderr


# -- the bolts on the second archive door -----------------------------------------------------------


def test_the_unresolved_archive_door_refuses_a_body_that_does_not_say_where_it_came_from(v1_state):
    """B5: the `legacy_id` bolt, which nothing held.

    `capture_migrated_unresolved` writes a body straight into `archive/<type>/<year>/` past the
    per-item field contract (DEC-0004/DEC-0009). What makes that exemption safe is that the path is
    for MIGRATED records only, and `legacy_fields.legacy_id` is the check for it. Removing that
    check left the suite green: no test drove this path with a body that lacked it, while the
    neighbouring archive door's identical bolt was measured.

    RED with the `legacy_id` check removed from `capture_migrated_unresolved_preflight`: a body
    with no provenance at all is written into the archive, exempt from the contract `capture`
    enforces.

    THE SECOND HALF IS THE OTHER BOLT ON THE SAME DOOR: `unresolved` was judged by
    `str(x or "")`, so `True`, a number or a list passed as the sentence that is supposed to tell a
    later reader why the item is in the archive at all.
    """
    nothing_said = {"title": "no provenance",
                    migrate.LEGACY_FIELD: {"record": {}, "unresolved": "no source for `contract`"}}
    with pytest.raises(Exception) as refusal:
        v1_state.capture_migrated_unresolved("PR", nothing_said, 2026)
    assert "legacy_id" in str(refusal.value), refusal.value
    assert not _archived_paths(v1_state, "PR")

    not_a_sentence = {"title": "a reason that says nothing",
                      migrate.LEGACY_FIELD: {"legacy_id": "PRD-0001", "record": {},
                                             "unresolved": True}}
    with pytest.raises(Exception) as refusal:
        v1_state.capture_migrated_unresolved("PR", not_a_sentence, 2026)
    assert "unresolved" in str(refusal.value), refusal.value
    assert not _archived_paths(v1_state, "PR")


def _install_wall_gate(state, document, hook_name="gate_procs"):
    """Install a REGISTERED, refusal-capable hook that reads `document`, and return its path.

    One builder for every test that needs a wall, because a wall is not a property of a document
    but of an INSTALLATION: `layout.gated_documents` answers from the project's own
    `.claude/settings.json` registration plus the hook's source. Measured on the three field copies
    (2026-08-05): no absorbed document is a wall in any of them, so every test that needs one
    builds the installation that reaches it.

    The refusal is spelled `<x>.block(...)` because that is the spelling `layout._can_refuse`
    recognises today -- which is itself a named hole (`docs/POST_V2_WISHLIST.md`, L15) and is
    measured by `test_a_hook_that_refuses_without_the_recognised_spelling_is_no_wall`.
    """
    repo = os.path.dirname(state.root)
    hooks = os.path.join(repo, ".claude", "hooks")
    os.makedirs(hooks, exist_ok=True)
    path = os.path.join(hooks, hook_name + ".py")
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        "import os\n"
        "import sys\n"
        "HOOK = %r\n"
        "class _kernel:\n"
        "    @staticmethod\n"
        "    def block(message):\n"
        "        sys.exit(2)\n"
        "def main():\n"
        "    path = os.path.join(%s)\n"
        "    if not os.path.exists(path):\n"
        "        _kernel.block('the store this gate reads is gone')\n"
        "    return 0\n"
        % (hook_name, ", ".join(repr(part) for part in
                                ["project_memory"] + document.split("/"))))
    io.open(os.path.join(repo, ".claude", "settings.json"), "w", encoding="utf-8",
            newline="\n").write(json.dumps({"hooks": {"PreToolUse": [
                {"matcher": "Bash", "hooks": [
                    {"type": "command",
                     "command": "python .claude/hooks/%s.py" % hook_name}]}]}}))
    return path


# -- the archive year, and the wall that is not moved -----------------------------------------------


def test_an_archive_year_that_is_no_year_is_refused_before_anything_is_written(v1_state):
    """`--archive-year` reached `ProjectState.archive_path` with whatever `int` accepted.

    The value becomes a DIRECTORY NAME, and this module's own reader of a record's dates takes a
    year to be four digits (`_DATE_RE`). The flag was judged by `int` alone, so `12` would have
    filed items under `archive/<type>/12/` and a negative value produced a path segment no reader
    of the archive expects.

    RED without `_archive_year_of`: `build_plan` accepts all three and the plan promises the paths.
    """
    for bad in (12, -2026, 20260):
        with pytest.raises(migrate.MigrationError) as refusal:
            migrate.build_plan(v1_state, {}, bad)
        assert "archive year" in str(refusal.value), refusal.value
    # ...and the counter-direction: a four-digit year is still accepted
    assert migrate.build_plan(v1_state, {}, _ARCHIVE_YEAR)["archive_year"] == _ARCHIVE_YEAR


def test_a_document_a_registered_gate_reads_is_never_moved_to_legacy(v1_state):
    """SR-0005 moves a fully absorbed V1 store; a WALL is not one, whatever its records did.

    A wall is a kit document whose CONTENT a registered, refusal-capable hook reads
    (`layout.gated_documents`). Moving one under `legacy/` takes it out from under its gate, and
    what a fail-closed gate does with an absent file is not this command's to provoke. Measured on
    the three field copies (2026-08-05): no absorbed document is a wall in any of them, so nothing
    in the field reaches this and the test builds the installation that does -- a registered
    PreToolUse hook that composes the document's path and can refuse.

    RED without the `gated_documents` clause in `absorbed_documents`: `process_definitions.yaml`
    is moved to `legacy/` although a registered gate of this installation reads it.
    """
    _install_wall_gate(v1_state, "process_definitions.yaml")
    plan = _planned(v1_state)
    assert "process_definitions.yaml" in plan["gated_documents"], plan["gated_documents"]
    assert "process_definitions.yaml" not in migrate.absorbed_documents(plan), (
        "a document a registered gate reads was planned for the move to legacy/")
    assert _migrated(v1_state) == 0
    assert os.path.exists(os.path.join(v1_state.root, "process_definitions.yaml"))
    assert not os.path.exists(os.path.join(v1_state.root, "legacy",
                                           "process_definitions.yaml"))


# -- what the run PRINTS about itself ---------------------------------------------------------


def _archive_directories_on_disk(state):
    """Every state-relative directory that holds an archived item, spelled as the OS spells it.

    Walked from the state root rather than composed from a type name, because composing it is
    exactly the mistake under test: on Windows and APFS `os.path.relpath` of a path this test
    BUILT would hand back the case this test typed, and the measurement would be of itself.
    """
    found = set()
    archive = os.path.join(state.root, "archive")
    for current, _dirs, files in os.walk(archive):
        if any(name.endswith(".yaml") for name in files):
            found.add(os.path.relpath(current, state.root).replace(os.sep, "/") + "/")
    return found


def test_the_archive_directory_the_dry_run_prints_is_the_one_the_run_creates(v1_state, capsys):
    """A path in the output has to be the path on the disk, on every filesystem the installers
    support.

    The dry run composed `archive/<type>/<year>/` out of `v2_type.lower()` while
    `ProjectState.archive_path` keys the directory by the id's own TYPE, so the run created
    `archive/PROC/2026/` and told the reader `archive/proc/2026/`. Windows and APFS open both, so
    the difference is invisible where this repo is developed and is a path that does not exist on
    the systems `install.sh` also serves.

    RED without `migrate.archive_location`: the directory this run creates does not appear in the
    text this run printed. Both halves are read where they run -- the text from the command, the
    directory from the disk after the write.
    """
    _run(v1_state, "migrate", "--dry-run", "--map", "PROC.roles=owner",
         "--archive-year", str(_ARCHIVE_YEAR))
    printed = capsys.readouterr().out
    assert _migrated(v1_state) == 0
    created = _archive_directories_on_disk(v1_state)
    assert created, "this fixture archived nothing, so the test measures nothing"
    for directory in sorted(created):
        assert directory in printed, (
            "the run created %r and the dry run printed no such path: %s"
            % (directory, [line for line in printed.splitlines() if "archive" in line]))


def test_the_legacy_path_the_dry_run_prints_is_the_one_the_run_moves_the_document_to(
        v1_state, capsys, monkeypatch):
    """The same defect as the archive path above, one directory further on, and still latent.

    The dry run composed its target as the literal `legacy/` + the document's path while the move
    goes through `ProjectState.legacy_path`. On today's tree the two spell the same thing, so no
    input can tell them apart -- which is exactly why it is measured through the BUILDER instead
    of through a spelling: the directory is moved here (as a real project's would be by a kernel
    that renamed it), and the printed path has to follow. It does not follow a hand-composed one.

    RED without `migrate.legacy_location`: the dry run prints `legacy/process_definitions.yaml`
    while the run moves the file to `retired_v1/process_definitions.yaml`.

    Both ends are read where they happen: the text from the command, the path from the disk after
    the write.
    """
    monkeypatch.setattr(ProjectState, "legacy_root",
                        lambda self: os.path.join(self.root, "retired_v1"))
    _run(v1_state, "migrate", "--dry-run", "--map", "PROC.roles=owner",
         "--archive-year", str(_ARCHIVE_YEAR))
    printed = capsys.readouterr().out
    assert _migrated(v1_state) == 0
    moved = {os.path.relpath(os.path.join(current, name), v1_state.root).replace(os.sep, "/")
             for current, _dirs, files in os.walk(os.path.join(v1_state.root, "retired_v1"))
             for name in files}
    assert moved, "this run absorbed no document, so the test measures nothing"
    for path in sorted(moved):
        assert path in printed, (
            "the run moved a document to %r and the dry run named no such path: %s"
            % (path, [line for line in printed.splitlines() if "->" in line]))


def test_moving_the_kernels_own_contract_table_alone_moves_the_digest(
        v1_state, capsys, monkeypatch):
    """The digest's FOURTH kind of input -- and both places the refusal named are silent about it.

    The message listed three causes and sent the reader to `state_fingerprint` (which is
    byte-identical here) and to `layout.gated_documents` (unchanged here). What moved is the
    kernel's own field contract: half of every record's classification is read out of it, so a
    kit update between the dry run and the run can change the plan with nothing in the project
    touched at all. A reader following either pointer finds nothing and has no next step.

    RED without the third KIND in `cli`'s mismatch message: the refusal names no code and no
    place that reports which harness this project is running.

    THE COUNTER-DIRECTION IS IN THE SAME RUN, because "the digest moves when the kit moves" would
    be the opposite lie: a kernel constant the plan draws no VERDICT from leaves it exactly where
    it was. The digest is over the plan, not over the harness's version -- and what a kit update
    changes BELOW the plan (how `execute` writes what the plan describes) it does not cover. That
    last half is the entry `L22` in `docs/POST_V2_WISHLIST.md`.
    """
    from kernel import layout
    repo = os.path.dirname(v1_state.root)
    before = migrate.plan_digest(_planned(v1_state))
    fingerprint = migrate.state_fingerprint(v1_state)
    walls = layout.gated_documents(repo, v1_state.root)

    monkeypatch.setattr(migrate, "ITEM_MAX_LINES", migrate.ITEM_MAX_LINES + 300)
    assert migrate.plan_digest(_planned(v1_state)) == before, (
        "a budget no record of this state comes near moved the digest, so this measures the "
        "harness's identity rather than the plan")

    monkeypatch.setattr(migrate, "OPTIONAL_FIELDS", dict(
        migrate.OPTIONAL_FIELDS,
        PROC=tuple(migrate.OPTIONAL_FIELDS.get("PROC", ())) + ("owner",)))
    after = migrate.plan_digest(_planned(v1_state))
    assert migrate.state_fingerprint(v1_state) == fingerprint, (
        "the contract change touched the state directory, so this measures two things at once")
    assert layout.gated_documents(repo, v1_state.root) == walls
    assert after != before, (
        "the plan carries no verdict this table decides, so there is no fourth kind to name")

    assert _run(v1_state, "migrate", "--plan", before, "--map", "PROC.roles=owner",
                "--archive-year", str(_ARCHIVE_YEAR)) == 2
    refusal = capsys.readouterr().err
    assert "CODE AND TABLES" in refusal, refusal
    assert "kit_version" in refusal, (
        "the message names the cause and no place that answers which harness computed the plan: "
        "%s" % refusal)


def test_a_registration_change_alone_moves_the_digest_and_the_refusal_says_where_to_look(
        v1_state, capsys):
    """The digest's third cause, and the one no reader could find from the message.

    The plan carries the WALLS (`layout.gated_documents`), which are derived from the project's
    hook REGISTRATION and not from the state directory. So registering one more refusal-capable
    hook that reads a kit document invalidates a presented plan while every file under the state
    directory stays byte-identical -- measured here on both halves at once. The refusal used to
    name two causes and send the reader to `state_fingerprint`, "which also names what it leaves
    out"; the fingerprint says nothing about hooks, so the reader arrives with nothing to look at.

    RED without the third cause in `cli`'s mismatch message: the message names no registration and
    no place that answers which hooks count.
    """
    before = migrate.plan_digest(_planned(v1_state))
    fingerprint = migrate.state_fingerprint(v1_state)
    _install_wall_gate(v1_state, "process_definitions.yaml")
    assert migrate.state_fingerprint(v1_state) == fingerprint, (
        "installing the hook touched the state directory, so this measures two things at once")
    after = migrate.plan_digest(_planned(v1_state))
    assert after != before, (
        "the plan does not record the walls, so this refusal has no third cause to name")
    assert _run(v1_state, "migrate", "--plan", before, "--map", "PROC.roles=owner",
                "--archive-year", str(_ARCHIVE_YEAR)) == 2
    refusal = capsys.readouterr().err
    assert "REGISTRATION" in refusal, refusal
    assert "layout.gated_documents" in refusal, (
        "the message names a cause and not the place that answers which hooks count: %s" % refusal)


# -- the shipped texts that describe the run ---------------------------------------------------


def _shipped_prose():
    """(path, text) for every Markdown document that DESCRIBES this harness to a reader.

    Derived rather than listed: everything Markdown a kit ships is what a role reads inside a
    project, and `README.md` is what a person reads about the harness. A document added to a kit
    tomorrow is covered without anyone remembering this file -- which is the whole point, because
    the claim the test below exists for survived in the one text nobody had listed (DEC-0015).

    `docs/HARNESS_V2_SPEC.md` is deliberately NOT in here, and the reason is a difference in kind
    rather than a document somebody left out: the spec PRESCRIBES, and its II.10 principles
    paragraph is the demand that imported items keep their regular initial status. Where the build
    departs from a demand, the spec's discipline is a NAMED deviation beside it (II.10 addendum),
    not a rewritten demand -- so measuring it against the run would ask it to stop being a spec.
    Nothing here checks that those addenda are complete; that is a residual of this test.
    """
    paths = sorted(
        os.path.join(current, name)
        for current, _dirs, files in os.walk(os.path.join(ROOT, "team-kits"))
        for name in files if name.endswith(".md"))
    paths.append(os.path.join(ROOT, "README.md"))
    for path in paths:
        yield (os.path.relpath(path, ROOT).replace(os.sep, "/"),
               io.open(path, encoding="utf-8").read())


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_SAYS_IMPORT = re.compile(r"\bimport(s|ed|ing)?\b|\bmigrat", re.IGNORECASE)
_SAYS_INITIAL_STATUS = re.compile(r"\binitial(en)?\s+status|\banfangsstatus\b", re.IGNORECASE)
_SAYS_THE_OTHER_DOOR = re.compile(r"archiv|\bmapped\b|\bgemappte", re.IGNORECASE)


def test_no_shipped_text_says_an_import_arrives_at_its_initial_status_full_stop(v1_state):
    """The claim is measured against a real run first, and only then looked for in the prose.

    THE MEASUREMENT: a completed import writes items at a status that is NOT their type's initial
    one -- that is what the first archive door is for, and it is the majority outcome on the field
    data (SR-0004). This asserts it against the run in this fixture rather than against a number
    quoted from elsewhere.

    WHAT THE PROSE HALF DECIDES, and it is not what this paragraph used to claim. It said the
    check was about "the pairing: whoever states the one half may not omit the other in the same
    breath". What it does is ask three WORD LISTS about one sentence: does an import word occur,
    does an initial-status word occur, and does no word of the other door occur. Measured
    2026-08-07 against these three regexes, one probe per direction:

      * `Imports arrive at their INITIAL status, never at the mapped one.` -- FALSE about this
        harness and it PASSES: any occurrence of the other door's vocabulary exempts, and a denial
        of it is an occurrence.
      * `A record the table calls unfinished is imported at its initial status.` -- TRUE, harmless
        and FLAGGED.
      * `Importierte Items kommen im Anfangsstatus an und tragen keine Freigabe.` -- the same
        claim in German, and it PASSES: `Importierte` ends no `import` word for `_SAYS_IMPORT`.
      * `Every imported PROC arrives in DRAFT and carries no approval.` -- the same claim with the
        status NAMED instead of described, and it PASSES.

    So this closes ONE spelling of the claim, in one language, and the sentence in the test name
    is about that spelling. More words would not make it a pairing: whether a sentence ASSERTS the
    half or denies it is a reading, and a checker that flags a correct sentence is worse than none
    -- the second probe above already is that, and it is the price the second buys the first.

    HOW MUCH IT LOOKS AT, measured over the same derived corpus on the same day: 2704 sentences in
    70 documents, 56 with an import word, 2 with an initial-status word, and exactly ONE that
    passes both and is therefore judged at all. The count is asserted below rather than left in
    this paragraph, because a sweep that looks at nothing is not a green light -- and the sentence
    it looks at today is one a rewrite of `README.md` could take away without anyone noticing that
    the instrument went blind.

    WHAT THIS DOES NOT DO, said here rather than discovered later: it reads Markdown, so a claim
    made in a docstring or in a printed line is out of its reach, and a sentence that states the
    half in one paragraph and the exception three paragraphs later reads as two sentences to it.
    Its strength is that no reader has to know WHICH document carries the claim.

    RED before this round: the sentence in all three constitutions -- `Imports arrive at their
    INITIAL status carrying no approval, so nothing an import writes opens a gate.`

    What the three word lists cannot decide is the entry `L21` in `docs/POST_V2_WISHLIST.md`.
    """
    assert _migrated(v1_state) == 0
    arrived = [(item["id"], item["status"], initial_status(parse_id(item["id"])[0]))
               for item in _archived_items(v1_state, "PROC")]
    arrived += [(item["id"], item["status"], initial_status(parse_id(item["id"])[0]))
                for item in [yaml.safe_load(io.open(path, encoding="utf-8"))
                             for _name, path in v1_state.iter_active_items("PROC")]]
    assert [one for one in arrived if one[1] != one[2]], (
        "no imported item of this run arrived anywhere but at its initial status, so the claim "
        "under test would be true and this test measures nothing: %s" % arrived)
    offenders, judged = [], []
    for path, text in _shipped_prose():
        for sentence in _SENTENCE_END.split(re.sub(r"\s+", " ", text)):
            if not (_SAYS_IMPORT.search(sentence) and _SAYS_INITIAL_STATUS.search(sentence)):
                continue
            judged.append("%s: %s" % (path, sentence.strip()))
            if not _SAYS_THE_OTHER_DOOR.search(sentence):
                offenders.append("%s: %s" % (path, sentence.strip()))
    assert not offenders, (
        "a shipped text states the initial-status half without the other half:\n%s"
        % "\n".join(offenders))
    assert judged, (
        "no shipped sentence uses both vocabularies any more, so this sweep judged NOTHING and "
        "its green light means only that the words are gone. Either the claim is now made in a "
        "spelling these three regexes do not know -- the docstring lists four such spellings -- "
        "or the sentence they were written for was rewritten away; read the corpus before "
        "widening anything.")


# -- what the SR-0001 scan will spend --------------------------------------------------------


def _v1_records_text(count=1, first=1):
    """A V1 procedure store payload -- what the scan below is looking for."""
    return "processes:\n" + "".join(
        "  PROC-%04d:\n    title: \"a process\"\n    owner: clerk\n    status: ACTIVE\n"
        % number for number in range(first, first + count))


def _reads_recorded(monkeypatch):
    """Record which documents `validate` actually PARSES -- the scan's own reader, not a proxy."""
    from kernel import migrate as migrate_module
    seen = []
    original = migrate_module._read_document

    def recording(state, rel):
        seen.append(rel)
        return original(state, rel)

    monkeypatch.setattr(migrate_module, "_read_document", recording)
    return seen


def _receipt_source_prefix():
    """The `source` a run RECEIPT carries, asked of the function that writes it.

    Not a string typed here: `migrate._receipt_fields` is the one producer, so a receipt that starts
    naming itself differently moves this reader with it. The digest is the only variable part, so a
    sample with a known digest gives the constant half.
    """
    sample = migrate._receipt_fields(
        {"records": [], "documents": [], "field_map": {}, "moved": [], "carried": [],
         "sources": []}, [], "DIGEST")
    return sample["source"].split("DIGEST")[0]


def test_the_receipt_filter_drops_the_receipt_and_nothing_else(v1_state):
    """N3-B1: the filter above must NARROW the check, not switch it off.

    MEASURED before this test existed: the filter read `iter_active_items(migrate.RECEIPT_TYPE)`,
    and `RECEIPT_TYPE` is `"DEC"` -- so every active decision counted as a receipt and a second
    carrier-less decision disappeared with the run's own. The ten `assert not findings` sites of this
    suite then measured nothing at all.

    BOTH DIRECTIONS IN ONE STORE: after a real import there is a receipt (silenced) and a
    hand-written decision with no carrier (reported).
    """
    assert _migrated(v1_state) == 0
    receipts = [stem for stem, _path in v1_state.iter_active_items("DEC")]
    assert receipts, "the run wrote no receipt, so this test measures nothing"

    other = v1_state.capture("DEC", {
        "title": "a decision nobody carries", "context": "c", "decision": "d",
        "consequences": "y", "source": "a round log, not a plan digest"})
    from kernel import report
    warned = {one["item"] for one in report.validate_state(v1_state)
              if "without a carrier" in one["message"]}
    assert other["id"] in warned, warned
    survived = {one["item"] for one in findings_beside_the_receipts_carrier(v1_state)
                if "without a carrier" in one["message"]}
    assert survived == {other["id"]}, (
        "the filter must drop the receipt and keep every other carrier-less decision: %s" % survived)

    # AND IT IS NARROWED ON THE MESSAGE, not on the item (verifier round 4, N4-1): the assertions
    # above read carrier warnings only, so a filter that dropped EVERY finding about the receipt
    # would satisfy them while switching this suite off again. A second finding about the SAME
    # receipt -- `supersedes` naming an id no item carries, which is `report._check_dec_supersedes`
    # and not the carrier line -- has to come through.
    from kernel.backlog_types import DEC_SUPERSEDES_FIELD
    v1_state.update_item(receipts[0], {DEC_SUPERSEDES_FIELD: ["DEC-9999"]})
    beside = [one for one in findings_beside_the_receipts_carrier(v1_state)
              if one["item"] == receipts[0]]
    assert beside, (
        "every finding about the receipt was dropped, not only its carrier warning -- the filter "
        "reads the item and not the message")
    assert all("without a carrier" not in one["message"] for one in beside), beside


def test_the_run_receipt_carries_work_none_and_owes_no_carrier_warning(v1_state):
    """The seam TSK-0131 handed to the merge (N11), closed: the receipt answers DEC-0083 itself.

    `report._check_decision_carriers` asks every decision in force who carries its work; the import's
    own RECEIPT records what a run did and commits nobody, so its honest answer is `work: none` -- and
    `migrate._receipt_fields` is the one place that may write it, because the importer never passes
    the capture door that asks a role (DEC-0021 refused a reader of the import mark there).

    RED without the line in `_receipt_fields`: the receipt carries no `work`, and the validator names
    it as a decision without a carrier. Read off `validate_state` directly, NOT through
    `findings_beside_the_receipts_carrier` below -- that filter would hide exactly this regression.
    """
    from kernel import report
    from kernel.backlog_types import DEC_WORK_FIELD, work_is_none
    assert _migrated(v1_state) == 0
    prefix = _receipt_source_prefix()
    receipts = [stem for stem, _path in v1_state.iter_active_items(migrate.RECEIPT_TYPE)
                if str(v1_state.read_item(stem).get("source") or "").startswith(prefix)]
    assert receipts, "the run wrote no receipt, so this test measures nothing"
    for stem in receipts:
        assert work_is_none(v1_state.read_item(stem).get(DEC_WORK_FIELD)), (
            "%s does not say `%s: none`" % (stem, DEC_WORK_FIELD))
    carrier = [one for one in report.validate_state(v1_state)
               if one["item"] in receipts and "without a carrier" in one["message"]]
    assert not carrier, carrier


def findings_beside_the_receipts_carrier(state):
    """`validate_state` minus a carrier warning about the run receipt -- which, since the merge
    wrote `work: none` into `migrate._receipt_fields`, the shipped receipt no longer produces.

    WHY IT STAYS: the ten `assert not findings` sites of this suite were written against this
    reader, and `test_the_receipt_filter_drops_the_receipt_and_nothing_else` above measures its
    NARROWNESS in both directions (verifier rounds 3 and 4) by planting the warning it would drop.
    What it must not become is a place that hides a regression of the receipt's own line: that line
    is held by `test_the_run_receipt_carries_work_none_and_owes_no_carrier_warning`, which reads
    `validate_state` without this filter.

    THE RECEIPT IS FOUND BY ITS IDENTITY, NOT BY ITS TYPE, and that correction is verifier round 3
    (N3-B1): `iter_active_items(migrate.RECEIPT_TYPE)` reads `RECEIPT_TYPE == "DEC"`, so the first
    version dropped the warning for EVERY active decision -- measured with a receipt plus a second
    carrier-less decision in the store, the filter returned `[]` and this suite's ten `assert not
    findings` sites were switched off rather than narrowed. A receipt is now the decision whose
    `source` is the one `migrate._receipt_fields` writes.

    THIS FILTER IS NARROW: it drops the carrier warning for the receipts of this run and nothing
    else. Any other finding -- a SECOND decision without a carrier, a second finding about the
    receipt itself -- comes through, and the claim is held by
    `tools/test_migrate.py::test_the_receipt_filter_drops_the_receipt_and_nothing_else` above, which
    fails in BOTH directions -- a filter that keeps too much and one that drops everything.
    """
    from kernel import report
    prefix = _receipt_source_prefix()
    receipts = set()
    for stem, _path in state.iter_active_items(migrate.RECEIPT_TYPE):
        if str(state.read_item(stem).get("source") or "").startswith(prefix):
            receipts.add(stem)
    return [one for one in report.validate_state(state)
            if not (one["item"] in receipts and "without a carrier" in one["message"])]


def test_a_document_too_large_to_search_is_reported_as_unsearched_and_not_read(v1_state,
                                                                              monkeypatch):
    """The completion-criterion scan runs inside a BLOCKING gate, so it may not be unbounded.

    `gate_memory_complete` calls `report.validate_state` on the PreToolUse path in front of `git
    merge`/`git push`, and a hook that outruns the host's budget is killed -- which the provider
    reads as "carry on". What this reader spends, and on which parser, is measured at
    `report.DOCUMENT_MAX_BYTES` and is not quoted here: one large document disarms the gate it is
    part of. Its three neighbours in the hook layer carry caps for exactly that reason and this one
    carried none.

    BOTH HALVES ARE MEASURED, because a cap that merely skips is the same silence one storey
    lower: the oversized document is never handed to the parser (recorded off the scan's own
    reader), AND it comes back as a finding of its own rather than as nothing.

    RED without `report.DOCUMENT_MAX_BYTES`: the document is parsed and the run reports it as a
    document that HOLDS records -- an answer, from a reader that had no bound.

    What the cap costs in the other direction is the entry `L17` in `docs/POST_V2_WISHLIST.md`.
    """
    from kernel import report
    path = os.path.join(v1_state.root, "old_procs.yaml")
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        _v1_records_text() + "padding: |\n"
        + "  the V1 monolith of a project that has been running for years\n"
        * (report.DOCUMENT_MAX_BYTES // 60))
    assert os.path.getsize(path) > report.DOCUMENT_MAX_BYTES
    io.open(os.path.join(v1_state.root, "small_procs.yaml"), "w", encoding="utf-8",
            newline="\n").write(_v1_records_text(first=99))
    read = _reads_recorded(monkeypatch)
    findings = {one["item"]: one for one in report.validate_state(v1_state)}
    assert "old_procs.yaml" not in read, (
        "the oversized document was parsed after all, so nothing bounds this reader")
    assert "old_procs.yaml" in findings, "a document this scan could not look at was passed over"
    assert findings["old_procs.yaml"]["severity"] == "error"
    assert "NOT SEARCHED" in findings["old_procs.yaml"]["message"], findings["old_procs.yaml"]
    # the counter-direction, in the same run: a document within the cap is still SEARCHED, and the
    # V1 record in it still comes back as one -- a cap that answered "unsearched" for everything
    # would satisfy the half above and retire SR-0001's bolt.
    assert "small_procs.yaml" in read
    assert "PROC-0099" in findings["small_procs.yaml"]["message"], findings["small_procs.yaml"]


def test_the_whole_scan_budget_names_the_documents_it_did_not_reach(v1_state, monkeypatch):
    """A per-document cap says nothing about a thousand documents, so there are two.

    The budget is lowered here rather than met with 8 MB of fixtures: what this measures is the
    property (a document the budget did not reach is NAMED, not skipped), and the VALUE is pinned
    against the other blocking readers in `tools/test_hooks.py`.

    RED without `report.DOCUMENT_SCAN_MAX_BYTES`: every document is read whatever the ones before
    it cost, and the reader's total spend is a fact about the project rather than a bound.
    """
    from kernel import report
    for number in range(3):
        io.open(os.path.join(v1_state.root, "store_%d.yaml" % number), "w", encoding="utf-8",
                newline="\n").write(_v1_records_text(count=8, first=100 + 10 * number))
    monkeypatch.setattr(report, "DOCUMENT_SCAN_MAX_BYTES", 1000)
    read = _reads_recorded(monkeypatch)
    findings = {one["item"]: one for one in report.validate_state(v1_state)}
    unreached = [rel for rel in ("store_0.yaml", "store_1.yaml", "store_2.yaml")
                 if rel not in read]
    assert unreached, "the lowered budget stopped nothing, so this measures nothing"
    for rel in unreached:
        assert rel in findings and "NOT SEARCHED" in findings[rel]["message"], (
            "%s was not reached and not reported: %s" % (rel, sorted(findings)))


# The probe that measures WHICH DOCUMENTS a `validate_state` run opens, in its own process for the
# same reason as `_WHO_OPENED_IT`: `sys.addaudithook` cannot be taken off again.
#
# WHY IT IS THE `open` EVENT AND NOT THE SCAN'S OWN READER. `_reads_recorded` wraps
# `migrate._read_document`, which answers "was it parsed"; the question here is whether the BYTES
# were ever in this process's hand, and a second opener beside that reader would be invisible to a
# wrapper around it.
_WHICH_DOCUMENTS_THE_VALIDATOR_OPENS = '''\
import json
import os
import sys

STATE, KERNEL = sys.argv[1], sys.argv[2]
sys.path.insert(0, KERNEL)

_MARKER = os.path.normcase(os.path.abspath(STATE))
_armed = []
_seen = set()


def _state_relative(target):
    """`target` as a path under the state root, or None -- INDEPENDENT OF THE PATH'S SPELLING.

    The kernel composes paths through `ext_path`, so one and the same document arrives at this
    hook extended-length from one caller and plain from another -- measured on this host, the root
    item and the lock came extended, the scanned document plain. Anchored with `startswith` every
    extended-length open falls out of the measurement, and that is the direction which makes a file
    that WAS read look like one that was never opened. So the root is looked for inside the
    resolved path, where the prefix cannot sit in front of it.
    """
    resolved = os.path.normcase(os.path.abspath(target))
    at = resolved.find(_MARKER)
    if at < 0:
        return None
    return resolved[at + len(_MARKER):].lstrip(os.sep).replace(os.sep, "/")


def _hook(event, args):
    if event != "open" or not _armed:
        return
    if not isinstance(args[0], str):
        return                                  # a file descriptor names no path
    rel = _state_relative(args[0])
    if rel:
        _seen.add(rel)


sys.addaudithook(_hook)
from kernel import report                                               # noqa: E402
from kernel.state import ProjectState                                   # noqa: E402

_armed.append(True)
state = ProjectState(STATE)
findings = report.validate_state(state)
_armed.pop()
print(json.dumps({"opened": sorted(_seen), "findings": findings}))
'''


def test_the_two_remedies_that_still_move_a_file_differ_in_whether_the_file_was_read(tmp_path):
    """Two remedies say "take the file out of the state directory", and only ONE of them cannot
    name a destination.

    WHAT THIS IS UNDER. `L35` in `docs/POST_V2_WISHLIST.md` names a constructed destination
    (`migrate.overflow_deposit_of`) for the one remedy that makes a reader remove a file, and
    carries the other two as rests. The reason it recorded for both was that they "deliberately do
    not read the file", so no sha256 for the name exists -- and for one of the two that was false:
    a document that fails to PARSE has been read, one line earlier, by `migrate._read_document`.
    An entry may be a rest, but not for a reason the code contradicts.

    SO THE PROPERTY IS MEASURED INSTEAD OF ASSERTED, and it is the one the split rests on: the
    document over `DOCUMENT_MAX_BYTES` is never opened at all -- there the digest really is only
    available for the price of the unbounded reader the bound exists against -- while the
    unparsable one is opened before it fails, so its bytes were in hand.

    RED in either direction: it goes red if the bounded branch starts reading (measured in a clone
    outside this repo by moving the read in front of the size question -- `big.yaml` then appears
    among the opened paths), and red if the parse branch stops reading, which is what would make
    the sentence it corrects true again.
    """
    from kernel import report
    state = _state_with_a_root_item(tmp_path, "what_validate_opens")
    _write_document(state, "broken.yaml", "processes:\n  PROC-0001: {\n")
    big = _write_document(state, "big.yaml",
                          "padding: |\n"
                          + "  the V1 monolith of a project that has been running for years\n"
                          * (report.DOCUMENT_MAX_BYTES // 60 + 200))
    assert os.path.getsize(big) > report.DOCUMENT_MAX_BYTES, os.path.getsize(big)
    probe = tmp_path / "what_validate_opens.py"
    io.open(str(probe), "w", encoding="utf-8", newline="\n").write(
        _WHICH_DOCUMENTS_THE_VALIDATOR_OPENS)
    done = subprocess.run([sys.executable, "-B", str(probe), state.root,
                           os.path.join(ROOT, "team-kits")],
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout + done.stderr
    seen = json.loads(done.stdout.strip().splitlines()[-1])
    opened = set(seen["opened"])
    findings = {one["item"]: one for one in seen["findings"]}

    # WHICH REMEDIES THIS IS ABOUT, taken off the run rather than listed here: every finding whose
    # remedy still sends the reader out of the state directory. A third one appearing is a change
    # `L35` has to answer for, so it fails here rather than passing unnoticed.
    moves = sorted(rel for rel, one in findings.items()
                   if "out of the state directory" in one["remedy"])
    assert moves == ["big.yaml", "broken.yaml"], moves
    # THE COUNTER-DIRECTION FIRST: this run really did open files under the state root, so "not
    # opened" below is an answer and not an empty measurement.
    assert [rel for rel in opened if rel.startswith("product/active/")], sorted(opened)
    assert "big.yaml" not in opened, (
        "the document over the per-document bound was opened after all, so `_bounded` stands where "
        "a digest for its name would cost nothing and L35's reason for it is gone")
    assert "broken.yaml" in opened, (
        "the unparsable document was never opened, so the parse failed without bytes and the "
        "reason L35 used to give for both remedies would be true again")


def _gate_memory_complete(repo, item_id="PR-0001"):
    """The shipped merge gate as a PROCESS, against `repo`. rc 2 = refused, 0 = the merge proceeds.

    The gate is what makes SR-0001's bolt a bolt: `validate_state` only returns findings, and a
    finding nothing blocks on is a report. So the question "does an unsearchable document still
    stop a merge" is asked of the thing that stops merges.
    """
    return subprocess.run(
        [sys.executable, os.path.join(ROOT, "team-kits", "dev-team", "hooks",
                                      "gate_memory_complete.py")],
        input=json.dumps({"tool_name": "Bash", "cwd": repo,
                          "tool_input": {"command": "git merge feat/%s-x" % item_id}}),
        capture_output=True, text=True,
        env=dict(os.environ, CLAUDE_PROJECT_DIR=repo,
                 HARNESS_KERNEL_PATH=os.path.join(ROOT, "team-kits")),
        timeout=120)


def _state_with_a_root_item(tmp_path, name):
    """A clean V2 state that a merge gate actually looks at.

    `gate_memory_complete` stands down before the first root item (`_root.has_root_item`), so a
    state without one answers rc 0 to everything and would make the measurement below vacuous.
    `technical_enabler` keeps the validator's `user_story` warning out of it; warnings do not
    block, but a fixture that produces findings of its own makes an rc 2 unreadable.
    """
    state = _plain_state(tmp_path, name)
    state.capture("PR", {"title": "the project as it is", "class": "technical_enabler",
                         "problem": "p", "goal": "g", "acceptance_criteria": [],
                         "invariants": [], "out_of_scope": [], "priority": "high"})
    assert not [one for one in report_module().validate_state(state)
                if one["severity"] == "error"], "the fixture itself is not clean"
    return state


def report_module():
    from kernel import report
    return report


def test_an_unparsable_document_is_unsearched_and_still_refuses_the_merge(tmp_path):
    """"Could not look" is not "looked and found none" -- for the SECOND way of not looking too.

    The two budgets above were reported; an unparsable document was skipped in silence, and the
    scan is the only thing between a V1 monolith copied back in and a project holding the same
    records twice (SR-0001). Measured 2026-08-07 on the shipped gate as a process, in a scaffolded
    project outside this repo with a valid root item: a document with one V1 record refused the
    merge (rc 2), the SAME document with one unparsable line appended -- the record still in it,
    in plain text -- allowed it (rc 0). One syntax error retired the bolt, silently, while the dry
    run reported the same file under UNREADABLE and refused its own run. Validator and dry run
    contradicted each other about one file.

    RED without the parse branch in `report._check_no_v1_records_outside_the_archive`: the last
    two assertions fail -- no finding, and the merge gate exits 0.

    BOTH COUNTER-DIRECTIONS ARE IN THE SAME RUN, because each alone is satisfiable by the wrong
    implementation: with no such document the gate lets the merge through (so rc 2 is not the
    fixture), and with a readable one it refuses for the RECORD rather than for a reading failure.
    """
    state = _state_with_a_root_item(tmp_path, "unparsable")
    repo = os.path.dirname(state.root)
    assert _gate_memory_complete(repo).returncode == 0

    _write_document(state, "old_procs.yaml", _v1_records_text())
    holding = _gate_memory_complete(repo)
    assert holding.returncode == 2 and "V1 backlog record" in holding.stderr, holding.stderr

    path = _write_document(state, "old_procs.yaml", _v1_records_text() + "  PROC-0002: {\n")
    assert "PROC-0001" in io.open(path, encoding="utf-8").read(), (
        "the record is gone from the file, so its silence would cost nothing")
    findings = {one["item"]: one for one in report_module().validate_state(state)}
    assert "old_procs.yaml" in findings, (
        "a document this scan could not read was passed over: %s" % sorted(findings))
    assert findings["old_procs.yaml"]["severity"] == "error"
    assert "NOT SEARCHED" in findings["old_procs.yaml"]["message"], findings["old_procs.yaml"]
    refused = _gate_memory_complete(repo)
    assert refused.returncode == 2, (
        "one unparsable line switched SR-0001's bolt off: %s" % (refused.stderr or "(rc 0)"))


def test_the_dry_run_and_the_validator_name_an_unreadable_document_the_same_way(tmp_path):
    """The two readers of one file may not disagree about whether it was searched.

    `migrate._read_document` is the reader both ends use, and its reason now names no path -- each
    caller composes the name it already has. This asserts that the same file is named by both, so
    a future split into two readers (which is what let them disagree in the first place) shows up
    here rather than in a project.
    """
    state = _state_with_a_root_item(tmp_path, "agree")
    _write_document(state, "old_procs.yaml", _v1_records_text() + "  PROC-0002: {\n")
    plan = migrate.build_plan(state)
    assert plan["unreadable"] and plan["unreadable"][0][0] == "old_procs.yaml", plan
    assert not migrate.plan_is_executable(plan)
    finding = [one for one in report_module().validate_state(state)
               if one["item"] == "old_procs.yaml"]
    assert len(finding) == 1 and finding[0]["severity"] == "error", finding
    assert "UNREADABLE" in finding[0]["remedy"], (
        "the finding does not send the reader to the half that says the same thing: %s" % finding)


# -- what ends a read, and what the run-up to the search lets through ---------------------------


def _write_bytes(state, name, blob):
    """A document written as BYTES -- the only way to put a real encoding on the disk."""
    path = os.path.join(state.root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(blob)
    return path


def _umlaut_records_text():
    """A V1 record store whose text does not survive being decoded as the wrong 8-bit codec."""
    return ("processes:\n"
            "  PROC-0001:\n    title: \"Beläge prüfen\"\n"
            "    owner: clerk\n    status: ACTIVE\n")


def test_a_kit_document_in_the_encoding_a_windows_editor_writes_is_named_not_a_traceback(tmp_path):
    """What ends the reading of a document ends it NAMED -- for the class that was neither.

    `_read_document` caught `(OSError, yaml.YAMLError)`. A kit document a Windows editor saved as
    UTF-16 or as ANSI raises `UnicodeDecodeError`, which is neither, so it went straight through
    the plan, the validator and the merge gate. Measured 2026-08-07 on the shipped
    `gate_memory_complete` as a process, in a scaffolded project outside this repo with a valid
    root item: rc 2 as an INTERNAL ERROR carrying a Python traceback and NOT the document's name,
    `validate` exit 1 printing one codec line and no finding at all, `build_plan` raising. The road
    there is the remedy the neighbouring refusals print themselves -- repair the file outside the
    session -- and on a German Windows the usual editor writes ANSI back.

    BOTH DIRECTIONS IN ONE RUN, because each alone is satisfiable by the wrong fix:

      * UTF-16 with a BOM is a YAML stream and now READS. The bytes go to `yaml.safe_load`
        unchanged, so the encoding question is answered by the YAML reader rather than by a codec
        this module picks -- and the record in it is found, which is what SR-0001's bolt is for.
      * ANSI is not a YAML stream in any declaration, so it stays a refusal -- but a NAMED one:
        the file's name is in the gate's message, the message is not an internal error, and
        `validate` makes a finding about that file instead of dying.

    RED WITHOUT THE BYTE-READING in `_read_document` -- and NOT without the widened `except`, which
    is what the previous version of this line claimed. Both directions measured 2026-08-08 in a
    clone outside this repo: with `except (OSError, yaml.YAMLError)` restored, this test and the
    reader's contract test stay GREEN (a `ReaderError` IS a `YAMLError`, so the encoding class was
    never the one the widening carries); with the read put back into text mode with a codec chosen
    in the module, this test fails -- the UTF-16 half first, because a stream the format declares
    stops being read. What the widened `except` does carry is measured one test further on,
    `test_a_document_nested_deeper_than_the_reader_can_follow_is_named_not_a_crash`.
    """
    state = _state_with_a_root_item(tmp_path, "encodings")
    repo = os.path.dirname(state.root)

    _write_bytes(state, "old_procs.yaml", _umlaut_records_text().encode("utf-16"))
    utf16 = _gate_memory_complete(repo)
    assert utf16.returncode == 2, "a V1 record in a UTF-16 document stopped refusing the merge"
    assert "PROC-0001" in (utf16.stdout + utf16.stderr), (
        "a UTF-16 YAML stream is a YAML stream and its record must be found: %s" % utf16.stderr)
    utf16_findings = {one["item"]: one for one in report_module().validate_state(state)}
    assert "V1 backlog record" in utf16_findings["old_procs.yaml"]["message"]
    assert migrate.build_plan(state)["records"], "the dry run reads no record out of UTF-16"

    _write_bytes(state, "old_procs.yaml", _umlaut_records_text().encode("cp1252"))
    ansi = _gate_memory_complete(repo)
    message = ansi.stdout + ansi.stderr
    assert ansi.returncode == 2, message
    assert "internal error" not in message, (
        "the gate still answers a document it cannot decode with its crash handler: %s" % message)
    assert "Traceback" not in message, message
    assert "old_procs.yaml" in message, (
        "the refusal does not name the file the reader is supposed to repair: %s" % message)
    ansi_findings = {one["item"]: one for one in report_module().validate_state(state)}
    assert ansi_findings["old_procs.yaml"]["severity"] == "error"
    assert "NOT SEARCHED" in ansi_findings["old_procs.yaml"]["message"]
    plan = migrate.build_plan(state)
    assert plan["unreadable"] and plan["unreadable"][0][0] == "old_procs.yaml", plan
    assert not migrate.plan_is_executable(plan)


def test_the_readers_contract_holds_for_an_empty_document_and_for_every_failure(tmp_path):
    """`_read_document`'s docstring, measured -- the sentence and the reason, both.

    TWO CLAIMS USED TO STAND THERE AND NEITHER HELD. "Exactly one of the two is None" is false for
    an EMPTY document, which parses to `None` with no problem -- so both were, and the contract a
    caller can actually rely on is about the READ. And "the reason names no PATH" was false for
    every parse failure: `yaml.safe_load` names its stream in every mark, so reading through an
    open file put the absolute path in the reason, and `report`'s finding -- whose `item` IS the
    path -- then said the name twice.

    RED without the fix: the two failure cases below either raise out of this test (the
    undecodable one) or come back carrying `state.root`, and the one-line assertion fails on the
    multi-line YAML mark.
    """
    state = _plain_state(tmp_path, "contract")
    _write_document(state, "empty.yaml", "")
    payload, problem = migrate._read_document(state, "empty.yaml")
    assert (payload, problem) == (None, None), (
        "an empty document is READ; a caller that treats `payload is None` as a failure is "
        "reading a contract this function does not have")

    # ...and what the YAML format calls a stream really is one here, which is the other half of
    # handing the bytes over unchanged rather than decoding them with a codec chosen in here
    for codec in ("utf-8", "utf-8-sig", "utf-16"):
        _write_bytes(state, "%s.yaml" % codec, _umlaut_records_text().encode(codec))
        payload, problem = migrate._read_document(state, "%s.yaml" % codec)
        assert problem is None, "%s: %s" % (codec, problem)
        assert payload["processes"]["PROC-0001"]["title"] == "Beläge prüfen", (codec, payload)

    _write_document(state, "syntax.yaml", "processes:\n  PROC-0001: {\n")
    _write_bytes(state, "ansi.yaml", _umlaut_records_text().encode("cp1252"))
    _write_bytes(state, "binary.yaml", bytes(range(256)))
    for rel in ("syntax.yaml", "ansi.yaml", "binary.yaml", "never_written.yaml"):
        payload, problem = migrate._read_document(state, rel)
        assert payload is None and problem, "%s produced no reason" % rel
        assert "\n" not in problem, "%s: the reason is not one line: %r" % (rel, problem)
        assert state.root not in problem and rel not in problem, (
            "%s: the reason names the path its caller already holds: %r" % (rel, problem))


def test_the_readers_docstring_names_every_caller_it_has():
    """A list of callers in a docstring is a claim about the code, so it is read off the code.

    The paragraph said "three callers"; there were four, and the uncounted one -- the wall listing
    in `render` -- was the one that DISCARDED the reason. A sentence that is wrong about who reads
    a function is how a caller comes to be forgotten when its contract changes.

    RED without keeping the list current: a call site whose enclosing function the paragraph does
    not name.
    """
    import ast

    named, missing, seen = migrate._read_document.__doc__, [], []
    for module in (migrate, report_module()):
        source = io.open(module.__file__, encoding="utf-8").read()
        tree = ast.parse(source, filename=module.__file__)
        owner = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for inner in ast.walk(node):
                    owner[id(inner)] = node.name
        for node in ast.walk(tree):
            called = (node.func.attr if isinstance(node.func, ast.Attribute)
                      else getattr(node.func, "id", None)) if isinstance(node, ast.Call) else None
            if called != "_read_document":
                continue
            caller = owner.get(id(node), "<module level>")
            seen.append(caller)
            if caller not in named:
                missing.append("%s.%s" % (os.path.basename(module.__file__), caller))
    assert len(set(seen)) > 1, (
        "this test found %s call site(s), so it is measuring nothing" % len(seen))
    assert not missing, (
        "`_read_document` is called from %s, and its own docstring names none of them"
        % sorted(set(missing)))


def _seven_placements(state, text):
    """One V1 record laid down in seven places of one state -- the 2026-08-07 field reading.

    Seven WRITES rather than seven states, because what is measured is that the two readers agree
    about each file, and a reader that answers per file has to meet them all at once.

    Returns the record of what it wrote. That record is an ORACLE the readers under test do not
    share: it is built while writing, so nothing about it depends on being able to walk the tree
    afterwards.
    """
    written = []
    for rel in ("old_procs.yaml", "sub/old_procs.yaml", "old_procs.yml", "old_procs.json",
                "old_procs.yaml.bak", ".legacy/old_procs.yaml",
                "staging/PR-0001/old_procs.yaml"):
        _write_document(state, rel, text)
        written.append(rel)
    return written


def test_every_file_under_the_state_root_gets_exactly_one_search_verdict(tmp_path):
    """The run-up to the record search is TOTAL -- that is the property, not the exclusion list.

    A file the run-up skips with a `continue` is a file no reader can distinguish from one that
    was searched and found empty, and that was the shape one storey below the loop this round's
    predecessor made a property of: `report` decided which files reach the search with three
    conditions of its own while `migrate` decided it with three others.

    THE ORACLE IS THE FIXTURE'S OWN WRITES, not a walk. The previous version of this test compared
    `search_coverage` against an `os.walk` of the same tree -- the same call whose blindness it was
    supposed to measure -- so both sides went silent together over a directory the walk could not
    open, and the test stayed green through it (measured 2026-08-08; see
    `test_a_directory_the_walk_cannot_open_is_named_and_refuses_the_run`). What is written below is
    recorded as it is written, and the coverage is held against that record.

    RED without `search_coverage`: there is no single answer to compare, which is the point --
    with the run-up restored to two implementations the agreement test below fails and this one
    cannot be written at all.

    The residual measured at the end -- a dotted path that is no YAML document is in no report --
    is carried by `L19` in `docs/POST_V2_WISHLIST.md`.
    """
    state = _plain_state(tmp_path, "total")
    written = _seven_placements(state, _v1_records_text())
    coverage = migrate.search_coverage(state)
    assert [rel for rel, _v, _w in coverage] == sorted(written), (
        "the coverage and what this fixture put on the disk are not the same set of files")
    assert len({rel for rel, _v, _w in coverage}) == len(coverage), "a file was classified twice"
    verdicts = {migrate.SEARCHED, migrate.UNSEARCHED, migrate.KERNEL, migrate.MACHINERY,
                migrate.UNLISTABLE}
    assert {verdict for _rel, verdict, _why in coverage} <= verdicts
    assert all(why for _rel, verdict, why in coverage if verdict != migrate.SEARCHED), (
        "a verdict other than SEARCHED came back without a reason")
    # THE RESIDUAL THE DOCSTRING STATES, measured so the sentence is answerable: a file under a
    # dotted path that is not YAML is MACHINERY -- neither searched nor named to a reader -- and
    # that is what keeps `.kernel.lock`, `.audit/hook_events.jsonl` and one `.gitkeep` per item
    # directory out of both reports. A V1 record hidden there is in neither.
    _write_document(state, ".legacy/old_procs.json", _v1_records_text())
    _write_document(state, "tasks/active/.gitkeep", "")
    verdict_of = {rel: verdict for rel, verdict, _why in migrate.search_coverage(state)}
    assert verdict_of[".legacy/old_procs.json"] == migrate.MACHINERY
    assert verdict_of["tasks/active/.gitkeep"] == migrate.MACHINERY, (
        "the machinery every item directory ships would be named to a reader once per directory")


def test_the_dry_run_and_the_validator_answer_the_same_about_every_file(tmp_path, capsys,
                                                                       monkeypatch):
    """Two readers of one question, measured over one state that holds all of its answers.

    Measured 2026-08-07, before this: the same `PROC-0001` in seven places of one state came back
    in three different combinations. Three placements (a kit document, one a directory down, one
    spelled `.yml`) were reported by both readers; the other four -- another suffix, a dotted path,
    the proposal area, and a dotted path spelled a second way -- were named by the dry run only, or
    by neither, depending on which of the two run-ups they fell out of.

    WHAT IS ASSERTED IS DERIVED FROM THE COVERAGE, not from the list above: whatever
    `search_coverage` calls unsearched must be named by BOTH readers with the same reason, and
    whatever it calls searched must produce the same verdict about its records in both. A class
    nobody thought of is therefore measured too, as soon as it exists.

    RED with the run-up split back in two: `.legacy/old_procs.yaml`, `old_procs.json`,
    `old_procs.yaml.bak` and `staging/PR-0001/old_procs.yaml` are unsearched and the validator's
    coverage names none of them.
    """
    state = _state_with_a_root_item(tmp_path, "agreement")
    _seven_placements(state, _v1_records_text())
    coverage = migrate.search_coverage(state)
    plan = migrate.build_plan(state)
    _run(state, "migrate", "--dry-run")
    printed = capsys.readouterr().out
    reported = report_module().record_scan_coverage(state)
    # the documents the validator's loop really OPENS, recorded off its own reader rather than
    # off the answer it publishes -- a second run-up that agreed with the first only by
    # coincidence would show up here and nowhere else
    opened = _reads_recorded(monkeypatch)
    findings = {one["item"]: one for one in report_module().validate_state(state)}

    unsearched = dict(migrate.unsearched_notes(coverage))
    assert len(unsearched) >= 4, ("the fixture no longer reaches the classes this measures: %s"
                                  % sorted(unsearched))
    assert {entry["path"]: entry["why"] for entry in reported["not_searched"]} == unsearched, (
        "the validator's coverage and the dry run's run-up are two answers again")
    for rel, why in unsearched.items():
        assert any(rel in note and why in note for note in plan["unscanned"]), (
            "%s is unsearched and the dry run's plan does not name it" % rel)
        assert rel in printed, "%s is unsearched and the dry run does not print it" % rel
        assert rel not in findings, (
            "%s was never read and the validator makes a finding about its content" % rel)

    searched = [rel for rel, verdict, _why in coverage if verdict == migrate.SEARCHED]
    holding = sorted({entry["source"] for entry in plan["records"]})
    assert holding, "the fixture holds no readable record, so the counter-direction is vacuous"
    for rel in holding:
        assert rel in searched
        assert "V1 backlog record" in findings[rel]["message"], (
            "%s holds a record the dry run read and the validator reports nothing" % rel)
    assert set(reported["searched"]) == set(searched)
    assert sorted(opened) == sorted(searched), (
        "the validator opened %s and the shared run-up says the searched set is %s"
        % (sorted(opened), sorted(searched)))

    # WHY THE PROPOSAL AREA IS OUT OF THE SEARCH RATHER THAN IN IT, which `_coverage_of` states as
    # its reason: a body staged for capture carries an id and a status, so it reads as a V1 record
    # by the same recogniser -- searching there would report every staged item as the double
    # SR-0001 forbids. The reason is measured rather than asserted in prose.
    _write_document(state, "staging/PR-0001/proposal.yaml",
                    "id: TSK-0001\nstatus: DRAFT\ntitle: \"what this task would do\"\n")
    staged = migrate.scan_document(yaml.safe_load(
        io.open(os.path.join(state.root, "staging", "PR-0001", "proposal.yaml"),
                encoding="utf-8")))
    assert [key for _o, key, record in staged
            if migrate._declares_status(record)
            and migrate._is_backlog_type(migrate.V1_ID_RE.match(key).group(1))] == ["TSK-0001"]
    assert not [one for one in report_module().validate_state(state)
                if one["item"].startswith("staging/")], (
        "the proposal area is reported as holding V1 backlog records")

    # WHAT THE COVERAGE DOES NOT DO, measured because `report.record_scan_coverage` says it in so
    # many words: an unsearched file is NAMED and stops nothing. A V1 store renamed out of the
    # search's reach passes the merge gate, and the reason it is not an error is that a project
    # cannot be blocked out of the `README.md` and `product/masterplan.md` its own kit ships. The
    # entry that has to carry this is `L19` in `docs/POST_V2_WISHLIST.md`.
    alone = _state_with_a_root_item(tmp_path, "renamed_out_of_reach")
    _write_document(alone, "old_procs.yaml.bak", _v1_records_text())
    assert [entry["path"] for entry
            in report_module().record_scan_coverage(alone)["not_searched"]] \
        == ["old_procs.yaml.bak"]
    assert _gate_memory_complete(os.path.dirname(alone.root)).returncode == 0, (
        "the merge is refused over an unsearched file -- if that is now intended, the sentence in "
        "`report.record_scan_coverage` and the hole entry behind it are what is out of date")


@contextlib.contextmanager
def _unlistable(directory):
    """`directory` unopenable to THIS process for the body, and back to normal afterwards.

    THE MECHANISM IS PER PLATFORM AND THE PROPERTY IS ASSERTED, which is the whole difference
    between measuring the thing under test and measuring the test's own environment: the body only
    ever runs under a directory `os.listdir` really refuses, and if this host will not produce one
    the test FAILS here instead of skipping. A skip is indistinguishable from a pass in a summary
    line, and this is a tripwire for a silence.
    """
    who = getpass.getuser()
    if os.name == "nt":
        subprocess.run(["icacls", directory, "/deny", "%s:(OI)(CI)(RD,RA)" % who],
                       capture_output=True, text=True, timeout=60)
        undo = ["icacls", directory, "/remove:d", who]
    else:                                    # pragma: no cover -- this suite runs on Windows
        os.chmod(directory, 0)
        undo = None
    try:
        try:
            os.listdir(directory)
        except OSError:
            pass
        else:
            raise AssertionError(
                "%s is still listable to %s, so nothing below measures a walk that goes blind"
                % (directory, who))
        yield
    finally:
        if undo:
            subprocess.run(undo, capture_output=True, text=True, timeout=60)
        else:                                # pragma: no cover -- see above
            os.chmod(directory, 0o755)
        os.listdir(directory)


def test_a_directory_the_walk_cannot_open_is_named_and_refuses_the_run(tmp_path):
    """Totality is a claim about the WALK, and `os.walk` is silent about what it cannot open.

    Measured 2026-08-08 in a state outside this repo whose `hidden/` directory was denied read
    access to the running user, with a `PROC-0001` (`status: ACTIVE`) inside it: `search_coverage`
    came back with two rows and named neither the directory nor the file, `build_plan` was
    executable, `validate` had no finding, and the shipped `gate_memory_complete` answered `git
    merge` with rc 0. The classifier answered for every file it was handed; nobody handed it that
    subtree. Both the run-up and its own tripwire were blind in the same way, because the tripwire's
    oracle was another `os.walk`.

    THE ORACLE HERE IS WHAT THE FIXTURE WROTE. The file inside the denied directory is known
    because this test put it there, so its absence from the coverage is measurable without asking
    the walk anything.

    RED without the `onerror` in `search_coverage`: the coverage names the directory nowhere, the
    plan is executable, `validate` reports nothing, and the merge gate answers rc 0 over a V1 store
    it never saw.

    WHAT THE ROW COSTS IN THE OTHER DIRECTION is not measured here and is carried as `L28` in
    `docs/POST_V2_WISHLIST.md`: the row is produced for EVERY walk error, including directories
    nothing would have searched even when readable.
    """
    state = _state_with_a_root_item(tmp_path, "blind")
    repo = os.path.dirname(state.root)
    hidden = os.path.join(state.root, "hidden")
    inside = _write_document(state, "hidden/old_procs.yaml", _v1_records_text())
    assert os.path.isfile(inside)
    assert _gate_memory_complete(repo).returncode == 2, (
        "the fixture's own record does not stop a merge while it is READABLE, so nothing below "
        "measures what hiding it costs")

    with _unlistable(hidden):
        coverage = migrate.search_coverage(state)
        classified = {rel for rel, _v, _why in coverage}
        assert "hidden/old_procs.yaml" not in classified, (
            "the walk reached the denied directory after all, so this measures nothing")
        named = dict(migrate.unlistable_notes(coverage))
        assert list(named) == ["hidden/"], (
            "a subtree nothing could look into is not in the coverage: %s" % sorted(classified))
        assert "could not be listed" in named["hidden/"]
        plan = migrate.build_plan(state)
        assert "hidden/" in migrate._unreadable_paths(plan), plan["unreadable"]
        assert not migrate.plan_is_executable(plan), (
            "the dry run promises a run over a state it could not read all of")
        findings = {one["item"]: one for one in report_module().validate_state(state)}
        assert findings["hidden/"]["severity"] == "error", sorted(findings)
        # ONE CONDITION, ONE ANSWER, and this is the assertion that says the two printers agree.
        # Until round 9 the validator offered a second step of its own -- "or take it out of the
        # state directory" -- which is exactly the alternative the migration's own row had just
        # been stripped of, on a row that can name the canonical directory (`L28`, `L35`). A
        # sentence removed at one printer and standing at the other is the same defect with a
        # longer path to it, so the validator hands the migration's constant through. What that
        # constant may SAY is pinned literally, one test down, off this module.
        assert findings["hidden/"]["remedy"] == migrate.THE_ONLY_UNLISTABLE_STEP, (
            "the validator answers an unlistable directory with a step of its own: %r"
            % findings["hidden/"]["remedy"])
        refused = _gate_memory_complete(repo)
        assert refused.returncode == 2, (
            "a directory nobody could list let the merge through: %s" % (refused.stderr or "rc 0"))
        assert "hidden" in (refused.stdout + refused.stderr)

    # ...and the counter-direction, in the same run: with the directory readable again the same
    # state has no such finding, so the refusal above is the denial and not the fixture.
    assert not [one for one in report_module().validate_state(state)
                if one["item"] == "hidden/"]
    assert migrate.unlistable_notes(migrate.search_coverage(state)) == []


def test_the_remedy_for_a_directory_nobody_can_list_offers_no_step_that_moves_it(tmp_path):
    """DEC-0024's second clause -- an instruction may not destroy, not even its own source.

    THE ROW IS PRODUCED FOR EVERY WALK ERROR (`L28` in `docs/POST_V2_WISHLIST.md`), so the directory
    it names can be the canonical one the root item lives in. Until round 8 the printed remedy
    offered two steps and the second was "take the directory out of the state directory": a reader
    who followed it on THIS row carried off the root item, and after the install no writer for it
    exists -- `gate_write_scope` refuses every tool write under the state directory and the kernel
    captures typed items only.

    BOTH ENDS, out of one real run of the shipped command:

      * the row's remedy is the ONE step and nothing after it, so an alternative added back is a
        difference this test sees rather than prose it agrees with;
      * that step IS a step: carrying it out -- the access comes back -- makes the row and the
        refusal it caused go away, so the remedy is not merely short.

    AND THE PRICE OF THE REMOVED ALTERNATIVE IS CARRIED OUT rather than argued: move this very
    directory out of the state directory, as the old sentence said, and the dev kit's `gate_git`,
    which refused a merge a moment earlier, answers rc 0 -- the project has no root item any more,
    so the gate that guards it stands down. That is the state nothing in this harness can undo.

    AND THE SAME DENIAL IS MEASURED AGAINST THE GATE, in the same run, because until round 9 it was
    the cheaper way to the same loss: `_root.has_root_item` answered a directory it could not list
    with "no root item yet", and five gates read that as "this project is still being set up".
    `gate_git` therefore let the merge through without anybody moving anything. It refuses now, and
    an rc 0 here says that predicate has gone back to `glob` -- see `L36` in
    `docs/POST_V2_WISHLIST.md`, which carries the chain.

    WHAT THIS TEST DOES NOT CLOSE, measured in the same run: `report.validate_state` raises
    `PermissionError` instead of a finding, which is `L37` in `docs/POST_V2_WISHLIST.md`.

    RED with the second step back in `migrate.THE_ONLY_UNLISTABLE_STEP`: the row no longer ends at
    the sentence pinned below. RED, in the other direction, if the step stops working: the run
    still names the directory after the access is back.
    """
    state = _state_with_a_root_item(tmp_path, "canonical_blind")
    repo = os.path.dirname(state.root)
    root_item = state.active_path("PR-0001")
    canonical = os.path.dirname(root_item)
    assert os.path.isfile(root_item), "the fixture's root item is not where this test looks"
    rel = os.path.relpath(canonical, state.root).replace(os.sep, "/") + "/"

    def merge():
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "team-kits", "dev-team", "hooks", "gate_git.py")],
            input=json.dumps({"tool_name": "Bash", "cwd": repo,
                              "tool_input": {"command": "git merge feat/PR-0001-x"}}),
            capture_output=True, text=True,
            env=dict(os.environ, CLAUDE_PROJECT_DIR=repo,
                     HARNESS_KERNEL_PATH=os.path.join(ROOT, "team-kits")),
            timeout=120)

    guarded = merge()
    assert guarded.returncode == 2, (
        "this project is not guarded while its root item stands, so losing the item below would "
        "cost nothing measurable: rc %s %s" % (guarded.returncode, guarded.stdout + guarded.stderr))

    with _unlistable(canonical):
        rows = dict(migrate.unlistable_notes(migrate.search_coverage(state)))
        assert list(rows) == [rel], (
            "this run does not report the canonical directory as unlistable, so nothing below is "
            "about the row under test: %s" % sorted(rows))
        # THE SENTENCE IS PINNED HERE AND NOT READ BACK OFF THE MODULE THAT PRINTS IT. What
        # DEC-0024's second clause forbids is what this remedy does NOT offer, and an absence
        # cannot be read out of prose by any rule. Comparing against `migrate.
        # THE_ONLY_UNLISTABLE_STEP` would make this assertion agree with whatever that constant
        # holds -- measured in round 8: with the removed alternative put back INTO the constant,
        # the assertion was still green. So a change to the offer has to come through this line.
        assert rows[rel].endswith("Remedy: give the session read access to it"), (
            "the remedy for a directory that may be the canonical one offers more than the single "
            "step that changes nothing the state directory holds (DEC-0024): %r" % rows[rel])

        # ...AND THE GATE OVER THE SAME DENIAL, which is the second way to the same loss and the
        # one that needed no remedy at all: the predicate five gates share.
        blind = merge()
        assert blind.returncode == 2, (
            "`gate_git` stands down over a canonical directory it cannot list, so a permission "
            "problem switches off the gates that guard the root item (`_root.has_root_item`): "
            "rc %s %s" % (blind.returncode, blind.stdout + blind.stderr))
        with pytest.raises(PermissionError):
            report_module().validate_state(state)      # `L37`, same file

    # THE ONE STEP, CARRIED OUT: `_unlistable` gave the access back on the way out.
    assert migrate.unlistable_notes(migrate.search_coverage(state)) == [], (
        "the only step this command offers does not clear the finding it is offered for")

    # ...AND THE ALTERNATIVE THAT NO LONGER STANDS THERE, carried out on the same directory.
    shutil.move(canonical, str(tmp_path / "taken_out_of_the_state_directory"))
    opened = merge()
    assert opened.returncode == 0 and not os.path.exists(root_item), (
        "following the removed alternative was supposed to leave the project without its root "
        "item and the merge gate standing down; it did not, so this half measures nothing: rc %s"
        % opened.returncode)


@contextlib.contextmanager
def _unreadable(path):
    """`path` unopenable to THIS process for the body, and back to normal afterwards.

    The same discipline as `_unlistable` one class up, for the same reason: the body only ever runs
    while `open` really refuses, and a host that will not produce that FAILS here instead of
    skipping, because a skip and a pass look the same in a summary line.
    """
    who = getpass.getuser()
    if os.name == "nt":
        subprocess.run(["icacls", path, "/deny", "%s:(RD,RA)" % who],
                       capture_output=True, text=True, timeout=60)
        undo = ["icacls", path, "/remove:d", who]
    else:                                    # pragma: no cover -- this suite runs on Windows
        os.chmod(path, 0)
        undo = None
    try:
        try:
            with open(path, "rb") as handle:
                handle.read()
        except OSError:
            pass
        else:
            raise AssertionError(
                "%s is still readable to %s, so nothing below measures a read that fails"
                % (path, who))
        yield
    finally:
        if undo:
            subprocess.run(undo, capture_output=True, text=True, timeout=60)
        else:                                # pragma: no cover -- see above
            os.chmod(path, 0o644)
        with open(path, "rb") as handle:
            handle.read()


def _cli_process(state, *argv):
    """The kernel CLI as its own PROCESS -- the only place a traceback is distinguishable.

    `_run` calls `cli.main`, so an exception it does not handle arrives in the test as an
    exception; what a user meets is an exit code and whatever went to stderr. The claim measured
    with this is about the second.
    """
    return subprocess.run(
        [sys.executable, "-B", "-m", "kernel.cli", "--root", state.root] + list(argv),
        capture_output=True, text=True, timeout=300,
        env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "team-kits")))


def test_a_document_the_run_cannot_open_is_named_and_refuses_instead_of_crashing(tmp_path):
    """The same blindness one storey lower: a file the walk LISTS and nobody can open.

    Measured 2026-08-08 on this host, `icacls /deny <user>:(RD,RA)` on ONE kit document of an
    otherwise clean state, the shipped commands as real processes:

        `validate`           rc 1 with a finding naming the document -- and a remedy telling the
                             reader that the dry run "names it under UNREADABLE and refuses the
                             run for the same reason"
        `migrate --dry-run`  rc 1 with a `PermissionError` TRACEBACK out of `_file_facts`

    So two shipped texts promised what the second command did not do: that remedy, and this
    module's own head ("an unreadable one refuses the run"). The walk was not blind here at all --
    the classifier answered SEARCHED for the file; the two callers that HASH it opened without a
    handler.

    BOTH OF THEM ARE MEASURED, and separately, because they answer different questions and either
    could be fixed alone: the document inventory (`_file_facts`, which is what the receipt's source
    list is built from) and the digest (`state_fingerprint`, whose rows are what an executing run
    is handed back).

    RED without either handler: `build_plan` raises `PermissionError` out of this test, and the dry
    run answers a process with a traceback instead of a refusal.
    """
    state = _state_with_a_root_item(tmp_path, "denied")
    repo = os.path.dirname(state.root)
    doc = _write_document(state, "handbook.yaml", "note: an ordinary kit document\n")
    assert migrate.plan_is_executable(migrate.build_plan(state)), (
        "this state is not migratable while the document is READABLE, so nothing below measures "
        "what denying it costs")
    assert _gate_memory_complete(repo).returncode == 0, "the fixture already refuses the merge"

    with _unreadable(doc):
        verdicts = {rel: verdict for rel, verdict, _why in migrate.search_coverage(state)}
        assert verdicts.get("handbook.yaml") == migrate.SEARCHED, (
            "the walk itself went blind, so this measures the directory case again: %s" % verdicts)

        facts, problem = migrate._file_facts(state, "handbook.yaml")
        assert facts is None and problem, "the inventory produced a row for a file it cannot read"
        rows, notes = migrate.state_fingerprint(state)
        assert "handbook.yaml" not in [rel for rel, _sha in rows], (
            "the fingerprint hashed a file nobody can open")
        assert [one for one in notes if one[0] == "handbook.yaml"], (
            "the digest is short one file and says nothing about it: %s" % notes)

        plan = migrate.build_plan(state)
        assert [one for one in plan["unreadable"] if one[0] == "handbook.yaml"], plan
        assert not migrate.plan_is_executable(plan), (
            "the dry run promises a run over a state it could not read all of")
        assert "handbook.yaml" not in [row["path"] for row in plan["documents"]]

        # ONE FILE, TWO TRUE SENTENCES ABOUT IT, and a refusal that counts DOCUMENTS may not read
        # that as two. Both halves are asserted, because collapsing them would be the other error.
        assert len([one for one in plan["unreadable"] if one[0] == "handbook.yaml"]) > 1, (
            plan["unreadable"])
        assert migrate._unreadable_paths(plan) == {"handbook.yaml"}, plan["unreadable"]
        with pytest.raises(migrate.MigrationError) as refused:
            migrate.execute(state, plan, migrate.plan_digest(plan))
        assert "1 path(s) unreadable" in str(refused.value), str(refused.value)

        done = _cli_process(state, "migrate", "--dry-run")
        said = done.stdout + done.stderr
        assert done.returncode == 1, said
        assert "Traceback" not in said, (
            "the dry run answers an unreadable document with a crash rather than a refusal: %s"
            % said)
        assert "handbook.yaml" in said, said

        findings = {one["item"]: one for one in report_module().validate_state(state)}
        assert findings["handbook.yaml"]["severity"] == "error", sorted(findings)
        assert _gate_memory_complete(repo).returncode == 2

    # ...and the counter-direction in the same run: readable again, the same state is migratable,
    # so the refusal above is the denial and not the fixture.
    assert migrate.plan_is_executable(migrate.build_plan(state))
    assert migrate.state_fingerprint(state)[1] == []
    assert _gate_memory_complete(repo).returncode == 0

    # ...AND EVERY PRODUCER OF THE `unreadable` LIST NAMES ITS PATH AS A PATH. The list used to be
    # sentences and the count recovered the path with `line.split(" ")[0]`, which rests on "a line
    # BEGINS with its path" -- true of every producer, and silent about where the path ENDS. THE
    # NAMES HERE CARRY SPACES for exactly that reason: measured 2026-08-09 with two denied documents
    # so named, `_unreadable_paths` answered `{'my'}` and `execute` refused with "1 path(s)
    # unreadable" for two files. Four of the five producers are reached in one state here; the fifth
    # (`_read_document` out of `execute`) writes into a refusal message and not into this list.
    many = _state_with_a_root_item(tmp_path, "many_producers")
    _write_document(many, "my broken procedures.yaml", "processes:\n  PROC-0001: {\n")
    denied_doc = _write_document(many, "my denied procedures.yaml", "note: a document\n")
    _write_document(many, "my shut away/inside.yaml", "note: another\n")
    item = [path for _name, path in many.iter_active_items("PR")][0]
    expected = {"my broken procedures.yaml", "my denied procedures.yaml", "my shut away/",
                os.path.relpath(item, many.root).replace(os.sep, "/")}
    with _unreadable(denied_doc), _unreadable(item), \
            _unlistable(os.path.join(many.root, "my shut away")):
        entries = migrate.build_plan(many)["unreadable"]
        assert len(entries) > len(expected), (
            "one path per entry, so no producer is measured twice over: %s" % entries)
        for path, why in entries:
            assert os.path.exists(os.path.join(many.root, *path.rstrip("/").split("/"))), (
                "an entry of `unreadable` does not name a path of this state: %r" % (path,))
            assert why, "an entry of `unreadable` carries no reason: %r" % (path,)
        assert migrate._unreadable_paths({"unreadable": entries}) == expected, sorted(
            migrate._unreadable_paths({"unreadable": entries}))
        with pytest.raises(migrate.MigrationError) as refused:
            migrate.execute(many, migrate.build_plan(many), "unchecked")
        assert "%d path(s) unreadable" % len(expected) in str(refused.value), str(refused.value)


# The probe that measures WHO opened a file, run as its own process because `sys.addaudithook`
# cannot be taken off again and every `open` of the pytest session would pay for it.
#
# THE ASKER IS DEFINED, NOT LISTED: walking out from the `open` event, the first frame that is
# neither in the standard library nor in this probe is the code that wanted the file. That is why
# `pathlib.Path.read_bytes`, `codecs.open`, `os.open` and `io.open` are all covered without being
# named -- each of them is stdlib frames on top of the frame that asked.
_WHO_OPENED_IT = '''\
import json
import os
import sys
import sysconfig

STATE, KERNEL = sys.argv[1], sys.argv[2]
sys.path.insert(0, KERNEL)

_SELF = os.path.normcase(os.path.abspath(__file__))
_STDLIB = tuple(sorted({os.path.normcase(os.path.abspath(where))
                        for key in ("stdlib", "platstdlib")
                        for where in [sysconfig.get_paths().get(key)] if where}))
_ROOT = os.path.normcase(os.path.abspath(STATE)) + os.sep
_armed = []
_seen = []


def _machinery(filename):
    if not filename or filename.startswith("<"):
        return True
    resolved = os.path.normcase(os.path.abspath(filename))
    return resolved == _SELF or resolved.startswith(_STDLIB)


def _asker():
    depth = 1
    while True:
        try:
            frame = sys._getframe(depth)
        except ValueError:
            return ("", "")
        if not _machinery(frame.f_code.co_filename):
            return (os.path.abspath(frame.f_code.co_filename), frame.f_code.co_name)
        depth += 1


def _hook(event, args):
    if event != "open" or not _armed:
        return
    target = args[0]
    if not isinstance(target, str):
        return                      # a file descriptor names no path
    if not os.path.normcase(os.path.abspath(target)).startswith(_ROOT):
        return
    _seen.append(_asker())


sys.addaudithook(_hook)
from kernel import migrate                                              # noqa: E402
from kernel.state import ProjectState                                   # noqa: E402

# WHICH FUNCTIONS THIS RUN WALKS, collected in the same process as the opens above so the two
# answers are about ONE run. `None` back from the tracer means the frame is not traced line by
# line -- the question is only whether the function was entered at all.
_MIGRATE = os.path.normcase(os.path.abspath(migrate.__file__))
_entered = set()


def _trace(frame, event, arg):
    if event == "call" and os.path.normcase(
            os.path.abspath(frame.f_code.co_filename)) == _MIGRATE:
        _entered.add(frame.f_code.co_name)
    return None


sys.settrace(_trace)
state = ProjectState(STATE)
_armed.append(True)
plan = migrate.build_plan(state, {}, 2026)
migrate.render(plan, state)
migrate.execute(state, plan, migrate.plan_digest(plan))

# A DOCUMENT NOBODY CAN PARSE, planned on its own: the failing-read path is where the reason for
# an unreadable file is composed, and a run that never fails a read never walks it. Written with
# the hook disarmed, so this probe's own `open` is not one of the opens it measures.
_armed.pop()
io_handle = open(os.path.join(STATE, "unparsable.yaml"), "w", encoding="utf-8", newline="\\n")
io_handle.write("processes:\\n  PROC-0001: {\\n")
io_handle.close()
_armed.append(True)
migrate.build_plan(state, {}, 2026)
during = list(_seen)

# THE COUNTER-DIRECTION: a reader that really is in `migrate.py` and really is not `_read_bytes`.
# Compiled with that filename so the frame the detector walks to is a frame of that module -- the
# spelling is `pathlib`, which the rule this replaces could not see at all.
del _seen[:]
exec(compile("import pathlib\\n"
             "def a_second_reader(path):\\n"
             "    return pathlib.Path(path).read_bytes()\\n",
             migrate.__file__, "exec"), globals())
a_second_reader(os.path.join(STATE, "project_config.yaml"))             # noqa: F821
planted = list(_seen)
_armed.pop()
sys.settrace(None)


def rows(seen):
    return sorted({(os.path.basename(where), what) for where, what in seen})


print(json.dumps({"module": os.path.basename(migrate.__file__),
                  "during": rows(during), "planted": rows(planted),
                  "entered": sorted(_entered)}))
'''


def test_every_state_file_this_module_opens_it_opens_through_read_bytes(tmp_path):
    """`_read_bytes`'s own claim, measured as a PROPERTY of the run instead of as a spelling.

    WHAT THE CLAIM IS FOR: a file nobody can open had three different stories in this module until
    every read was funnelled through one function that REPORTS the failure. A second reader added
    later is a second story, and it is the shape in which `migrate --dry-run` answered a denied kit
    document with a `PermissionError` traceback while the validator named it.

    THE RULE THIS REPLACES WAS WRONG IN BOTH DIRECTIONS, and both were measured (2026-08-09, in a
    clone outside this repo): it counted `ast.Call` nodes whose `func.id` was `open`.

        a real second reader, `io.open(...)` in `_retire_absorbed_documents`, unhandled
            -> the AST rule stayed GREEN
        a behaviour-preserving rewrite INSIDE `_read_bytes`, `io.open` instead of `open`
            -> the AST rule went RED, with a message that was then untrue

    `pathlib.Path.read_bytes`, `codecs.open` and `os.open` were outside it as well. So the question
    is asked of the RUNNING process: `sys.addaudithook` sees the `open` event every one of those
    spellings raises, and the frame that asked for the file is derived (see `_WHO_OPENED_IT`) rather
    than matched against a list of opener names.

    TWO RESIDUALS, AND THE SECOND ONE IS WHY THIS TEST IS ONE OF A PAIR.

      * the asker is the first frame outside the standard library, so a THIRD-PARTY library opening
        a state file on this module's behalf would be attributed to that library. Nothing does that
        today -- `yaml` is handed bytes, never a path. It is the entry `L31` in
        `docs/POST_V2_WISHLIST.md`.
      * this measurement is total over the SPELLING and only over the path this one run walks. A
        second reader planted in a branch this run never enters is invisible here, and the old AST
        rule -- wrong as it was -- would have found it. What covers that direction is
        `test_nothing_but_these_functions_can_name_a_file_of_the_state_directory`, which is total
        over the FILE and says nothing about spellings. The two are the two directions of one
        question, and neither is the other's duplicate.

    WHERE THEY MEET IS MEASURED HERE RATHER THAN STATED: the same process records which functions
    of the module it entered (`sys.settrace`), and every function the static rule licences has to be
    one of them. That is what turns "the two cover each other" into a claim with a red state -- a
    licensed function this run never enters is a hole in exactly the middle, and the assertion names
    it. What is left after both, said as narrowly as it is true: a second reader INSIDE one of the
    licensed functions, in a branch this run does not enter.

    BOTH ENDS IN ONE RUN. The planted second reader is what makes the empty violation list mean
    something: it is in a frame of `migrate.py`, it is not `_read_bytes`, it is spelled with
    `pathlib`, and the probe has to report it. And the run has to have opened state files through
    `_read_bytes` at all, or "no violations" would only say that nothing was read.
    """
    state = _state_with_a_root_item(tmp_path, "who_opened_it")
    _write_document(state, "project_config.yaml", "name: demo\nstacks: [python]\n")
    _write_document(state, "procedures.yaml",
                    "processes:\n"
                    "  PROC-0001:\n"
                    "    title: \"file the post\"\n"
                    "    status: ACTIVE\n"
                    "    roles: [clerk]\n"
                    "    trigger: \"inbox\"\n"
                    "    steps: [\"file it\"]\n"
                    "    source: \"the V1 store\"\n")
    # AN ARCHIVE-BOUND RECORD BESIDE THE ACTIVE ONE, and it is here for the coverage and not for
    # the records: without it `archive_location` is the one path-composing function of the module
    # this run never enters, and the static rule below rests on all of them being entered.
    _write_document(state, "tasks.yaml",
                    "tasks:\n"
                    "  TSK-0001:\n"
                    "    title: \"a task that was finished in V1\"\n"
                    "    status: DONE\n"
                    "    closed: \"2025-03-04\"\n")
    probe = tmp_path / "who_opened_it.py"
    io.open(str(probe), "w", encoding="utf-8", newline="\n").write(_WHO_OPENED_IT)
    done = subprocess.run([sys.executable, "-B", str(probe), state.root,
                           os.path.join(ROOT, "team-kits")],
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout + done.stderr
    seen = json.loads(done.stdout.strip().splitlines()[-1])

    module = seen["module"]
    through = [what for where, what in seen["during"] if where == module]
    assert through == ["_read_bytes"], (
        "`%s` opened a file under the state directory somewhere other than `_read_bytes`, so a "
        "file nobody can read has more than one story again: %s" % (module, seen["during"]))
    assert seen["during"], (
        "the run opened no state file at all, so an empty violation list says nothing")
    assert [what for where, what in seen["planted"] if where == module] == ["a_second_reader"], (
        "the probe cannot see a second reader of a state file even when one is planted in a frame "
        "of `%s`, so its silence above measures nothing: %s" % (module, seen["planted"]))

    # ...AND THE TWO RULES MEET WHERE THIS SAYS THEY DO. Every function the static rule licences to
    # compose a state path is entered by THIS run, so the spelling-total measurement above covers
    # every function the file-total one licences. Both ends: a licensed function this run never
    # enters is named, and the run has to have entered more of the module than just those.
    entered = set(seen["entered"])
    missing = sorted(set(_NAMES_A_STATE_FILE) - entered)
    assert not missing, (
        "these functions may compose a state path and this run never enters them, so a second "
        "reader in one of them is invisible to BOTH tripwires at once: %s" % missing)
    assert len(entered) > len(_NAMES_A_STATE_FILE), (
        "this run walks no more of the module than the licensed functions themselves, so the "
        "sentence above about where the two rules meet says nothing: %s" % sorted(entered))


# EVERY FUNCTION OF `kernel/migrate.py` THAT CAN NAME A FILE OF THE STATE DIRECTORY AT ALL, with
# what it does with the name. This is an enumeration, and it is one of the module's OWN functions --
# a closed set that changes only when somebody edits that file -- rather than of opener spellings,
# which is the enumeration the rule before this one died of. Both ends are measured by the test
# below: an entry that no longer composes a path is dead, and a function that composes one without
# an entry is the thing the rule exists to catch.
_NAMES_A_STATE_FILE = {
    "_relative": "turns an absolute path back into a state-relative one; it opens nothing, and it "
                 "is therefore also the one call a composed path may be HANDED to -- what comes "
                 "back is a state-relative name and the flow rule below stops there",
    "_state_path": "the module's ONE composer of an absolute path under the state root",
    "_read_bytes": "the one function that opens a state file, which is the claim itself",
    "_without_path": "composes the path only to STRIP it out of a failure message; it takes `rel` "
                     "and composes rather than being handed the path, FOR THIS RULE -- a function "
                     "that only RECEIVES a path names nothing this rule can see",
    "_is_occupied": "asks `os.path.lexists`, whose answer is a yes or a no and never bytes",
    "documents": "walks the state root for the inventory and hands names on",
    "search_coverage": "walks the state root for the coverage and hands names on",
    "imported_legacy_ids": "walks the item store and reads each item through `_read_document`",
    "state_fingerprint": "walks the state root and hashes each file through `_read_bytes`",
    "_classify": "hands `state.root` to `layout.is_kernel_written`, which answers from names",
    "walls_of": "hands the repository root to `layout.gated_documents`",
    "archive_location": "composes against a throwaway `ProjectState(os.curdir)`, so it names no "
                        "file of any state directory",
    "legacy_location": "the same throwaway probe, for the `legacy/` target",
    "_retire_absorbed_documents": "moves a document with `os.replace`; its hash comes from "
                                  "`_file_facts`, which reads through `_read_bytes`",
}


def _names_a_state_file(node, stashed=()):
    """Is this expression a way of naming a file under the state root?

    THE DEFINITION, and it is about the PATH and not about the opening: to read a file of the
    state directory a caller must first name it, and there are exactly two shapes for that in this
    module -- the module's own composer, and a path builder of the state object. `ProjectState`
    spells every one of the latter `root`, `..._path` or `..._root`, and
    `test_the_path_builders_of_the_state_object_all_carry_one_of_two_name_shapes` measures that
    the shape really covers them.

    `stashed` is the third: a module-level name a function PARKED a path in (`_stashed_names`).
    Reading it back names the file just as much, and the reader would compose nothing.
    """
    if isinstance(node, ast.Name) and (node.id == "_state_path" or node.id in stashed):
        return node.id
    if isinstance(node, ast.Attribute) and (
            node.attr == "root" or node.attr.endswith(("_path", "_root"))):
        return "." + node.attr
    return None


def _by_function(tree, stashed=()):
    """{function name: [(what it named, line)]} for one parsed module, innermost function wins."""
    found = {}

    def walk(node, holder):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(child, child.name)
                continue
            named = _names_a_state_file(child, stashed)
            if named:
                found.setdefault(holder, []).append((named, child.lineno))
            walk(child, holder)

    walk(tree, "<module>")
    return found


def _module_own_names(tree):
    """Every name through which control can reach code of THIS module.

    WHY THE LINE IS DRAWN AT THE IMPORT. A call that mentions one of these can transfer control into
    THIS file -- it is a function of it, a class of it, or an object of one -- and this file is where
    a second reader would be added and where `_NAMES_A_STATE_FILE` is the only thing that accounts
    for one. A name an import bound belongs to another module: what `os.path.join` or `open` does
    with a path is not what this rule claims, and `_read_bytes` says so in its own words.

    A `def` NESTED IN A FUNCTION IS CODE OF THIS FILE TOO, and reading only the top level was
    measured blind (B1, round 8): a helper `def` inside the host function took the state bytes into
    a real reader while both halves of the rule reported nothing. So the walk descends into every
    body, but it collects only the names a `def` or a `class` binds there; a LOCAL of a body is not
    a way into this file's code and stays out.

    WHAT COLLECTING THE NAME DOES NOT BUY, and it is the same shape one turn further (DEC-0029): a
    nested `def` that reads the path out of the CLOSURE rather than through an argument hands
    nothing over, so no call expression carries a state path into it and the rule reports `[]` --
    measured in round 8's review with a real reader that returned the bytes it had read. Being in
    this set is what makes a receiver ASKABLE; it is not what makes a hand-over visible.
    """
    imported = {(alias.asname or alias.name).split(".")[0]
                for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names}
    # A `global` declaration binds at the top level wherever it stands, so it belongs here as much
    # as a `def` does -- and it is the only way a module name can exist without a module-level
    # statement writing it, which is exactly the shape `_stashed_names` is about.
    bound = {name for node in ast.walk(tree) if isinstance(node, ast.Global) for name in node.names}

    def walk(node, inside_a_body):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bound.add(child.name)
                walk(child, True)
                continue
            if not inside_a_body and isinstance(child, ast.Name) \
                    and isinstance(child.ctx, ast.Store):
                bound.add(child.id)
            walk(child, inside_a_body)

    walk(tree, False)
    return bound - imported


def _root_name(node):
    """The name a callee expression starts at -- `os` for `os.path.join`, `_SIDECAR` for
    `_SIDECAR.read`, `functools` for `functools.partial`, the function's own name for a bare call.

    WHICH SHAPE THE CALLEE HAS is exactly what this rule must not depend on: the rule before it
    looked at `ast.Name` callees only, and `_SIDECAR.read(_state_path(state, rel))` walked past it.
    """
    if isinstance(node, (ast.Attribute, ast.Subscript, ast.Starred)):
        return _root_name(node.value)
    if isinstance(node, ast.Call):
        return _root_name(node.func)
    return node.id if isinstance(node, ast.Name) else None


def _binds(node):
    """(what is computed, what it is bound to) for every shape that binds a name inside a function.

    Assignment, annotated and augmented assignment, walrus, `for` target, comprehension target and
    `with ... as`. A value that reaches a name through any of them is the same value.
    """
    if isinstance(node, ast.Assign):
        return node.value, node.targets
    if isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
        return node.value, [node.target]
    if isinstance(node, ast.NamedExpr):
        return node.value, [node.target]
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return node.iter, [node.target]
    if isinstance(node, ast.comprehension):
        return node.iter, [node.target]
    if isinstance(node, ast.withitem) and node.optional_vars is not None:
        return node.context_expr, [node.optional_vars]
    return None, []


def _carries_a_state_path(expr, tainted, own, stashed):
    """What in `expr` can answer with a path under the state root, or None -- the FLOW, not a shape.

    THE ONE PLACE THE FLOW STOPS is a call into this file's own code: the path went in, whether that
    was allowed is `_handed_a_finished_path`'s question, and what comes back is that function's own
    answer -- `_relative` hands back a state-relative name, and its licence entry says so. The
    composer is the exception, and it is not one written here: `_state_path` is a naming node by
    `_names_a_state_file`, so its call answers with a path wherever it stands.

    Everything else is followed: `os.path.join`, `str`, a slice, a format, a tuple. That is the
    direction the rule before this one was blind in -- it read the call SHAPE, so a path in a local
    variable, in a wrapper's argument list or behind one `os.path.dirname` was invisible.
    """
    named = _names_a_state_file(expr, stashed)
    if named:
        return named
    if isinstance(expr, ast.Name):
        return expr.id if expr.id in tainted else None
    if isinstance(expr, ast.Call) and _root_name(expr.func) in own:
        return _carries_a_state_path(expr.func, tainted, own, stashed)
    for child in ast.iter_child_nodes(expr):
        found = _carries_a_state_path(child, tainted, own, stashed)
        if found:
            return found
    return None


def _tainted_in(scope, own, stashed):
    """Every name of `scope` that can hold a path under the state root, to a fixed point.

    The fixed point is what covers a loop: a name bound from another name that is only tainted later
    in the body is tainted on the second pass, and the walk repeats until nothing grows.
    """
    tainted = set()
    while True:
        grown = set(tainted)
        for node in ast.walk(scope):
            value, targets = _binds(node)
            if value is None or not _carries_a_state_path(value, grown, own, stashed):
                continue
            grown.update(name.id for target in targets for name in ast.walk(target)
                         if isinstance(name, ast.Name))
        if grown == tainted:
            return tainted
        tainted = grown


def _stashed_names(tree, own):
    """The module-level names a function of this file parks a state path in.

    A PATH DOES NOT HAVE TO BE PASSED TO LEAVE THE FUNCTION THAT COMPOSED IT. Parked where a name of
    the module reaches it, it is in reach of every other function, and a reader there composes
    nothing and is handed nothing -- so both halves of the rule would be silent.

    WHAT MAKES A STORE REACH THE MODULE IS THE TARGET'S ROOT NAME, and asking the STATEMENT instead
    was measured blind (F1, round 7): `global _STASHED; _STASHED = path` was the only spelling read,
    while `_A_DICT["parked"] = path`, `_A_LIST[0] = path` and `_SIDECAR.parked = path` bind no name
    at all and reach exactly as far -- they mutate an object a module name answers with, and each of
    them carried the state bytes into a reader that this rule then named nowhere. So a store counts
    when its target is a bare name the scope declares `global`, or an attribute or subscript rooted
    in a name of this module. A local shadowing such a name is over-reported by that, which is the
    harmless direction: it costs a licence entry, never a silence.

    EMPTY IN THE SHIPPED FILE, which is why the corpus of
    `test_the_rule_against_handing_a_state_path_on_follows_the_value_and_not_the_call_shape`
    carries every one of those spellings: an addition nothing can make red is a claim, not a defence.
    """
    stashed = set()
    while True:
        grown = set(stashed)
        for scope in ast.walk(tree):
            if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            tainted = _tainted_in(scope, own, grown)
            grown |= tainted & {name for node in ast.walk(scope) if isinstance(node, ast.Global)
                                for name in node.names}
            for node in ast.walk(scope):
                value, targets = _binds(node)
                if value is None or not _carries_a_state_path(value, tainted, own, grown):
                    continue
                grown |= {_root_name(reached) for target in targets
                          for reached in ast.walk(target)
                          if isinstance(reached, (ast.Attribute, ast.Subscript))} & own
        if grown == stashed:
            return stashed
        stashed = grown


def _value_leads_to(expr, aliases, own):
    """{(name of THIS module, whether the value came OUT OF a call of it)} for the value of `expr`.

    WHAT A VALUE LEADS TO, with the one distinction the rule below needs recorded rather than
    decided here. `_SIDECAR.read` leads to `_SIDECAR` and IS that object's code; `_a_reader_factory()`
    leads to `_a_reader_factory` but is not that function -- it is whatever the function returned.
    Which of the two a name holds decides nothing on its own, so both are carried and the ANSWER is
    given at the place the value is used (`_receives`, and its `invoked` argument).

    Deciding it HERE was measured wrong in both directions (B1, round 8): dropping calls entirely
    made `reader = _a_reader_factory(); reader(path)` invisible while a real reader took the state
    bytes, and keeping them made the shipped module report `absorbed_documents` as receiving a path
    it never gets -- `for rel in absorbed_documents(plan, written)` binds a string, and `rel` then
    stands in the argument list of `state.legacy_path(rel)`.
    """
    if isinstance(expr, ast.Call):
        return {(name, True) for name, _out_of_a_call
                in _value_leads_to(expr.func, aliases, own)}
    if isinstance(expr, (ast.Attribute, ast.Subscript, ast.Starred)):
        return _value_leads_to(expr.value, aliases, own)
    if isinstance(expr, ast.Name):
        return ({(expr.id, False)} if expr.id in own else set()) | set(aliases.get(expr.id, ()))
    found = set()
    for child in ast.iter_child_nodes(expr):
        found |= _value_leads_to(child, aliases, own)
    return found


def _receives(expr, aliases, own, invoked=False):
    """Which names of THIS module an expression standing in a call can hand control to.

    THE OTHER HALF OF A HAND-OVER, followed like the path is (F1, round 7): a rule that reads the
    callee's SPELLING is blind to `reader = _a_second_reader`, which is ordinary code and hid the
    receiver completely while the reader really took the state bytes. `_root_name` reduces the
    spelling -- `_SIDECAR.read`, `_HANDLERS[kind]` and `_make_reader()` all answer with the name
    this file binds -- and `aliases` answers for a local that was bound from one.

    `invoked` IS THE CALLEE POSITION, and it is the one place a value that came OUT OF a call of
    this module counts as that call's code: there the program itself says the value is callable. In
    an argument position the same value is data -- a function of this file that returns a string
    returns a string -- and reading its producer's name off it there is the false positive measured
    on the shipped module (`_value_leads_to`). What is left over by that split is named in
    `_handed_a_finished_path`.
    """
    root = _root_name(expr)
    if root is None:
        return set()
    return (({root} if root in own else set())
            | {name for name, out_of_a_call in aliases.get(root, ())
               if invoked or not out_of_a_call})


def _aliases_in(scope, own):
    """{name of `scope`: what its value can lead to} -- to a fixed point, `_value_leads_to`'s pairs.

    The receiver half of `_tainted_in`, and it repeats for the same reason that one does: a name
    bound from a name that only becomes an alias later in the body is an alias on the second pass.
    """
    aliases = {}
    while True:
        grown = {name: set(what) for name, what in aliases.items()}
        for node in ast.walk(scope):
            value, targets = _binds(node)
            if value is None:
                continue
            leads_to = _value_leads_to(value, grown, own)
            if not leads_to:
                continue
            for target in targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name):
                        grown.setdefault(name.id, set()).update(leads_to)
        if grown == aliases:
            return aliases
        aliases = grown


def _handed_a_finished_path(tree):
    """[(where, what it hands over, to whom, line)] -- every call that lets a state path leave.

    THE HALF OF THE RULE THAT IS ABOUT THE VALUE AND NOT ABOUT THE BODY. `_by_function` asks who
    NAMES a path, and a function that is HANDED one names nothing: it is invisible there, and a
    reader inside it is licensed by nothing. That is not hypothetical -- `_unreadable_because(exc,
    _state_path(state, rel))` and `_without_path(text, path)` were exactly that shape, and a real
    second reader planted in the first of them left both tripwires green while the audit probe's run
    never entered the branch.

    THE VERSION BEFORE THIS ONE ASKED THE QUESTION OF THE CALL SYNTAX and was measured to see only
    one spelling of it: the callee had to be a bare `ast.Name` of a function of this module, and the
    composition had to stand inside the argument expression itself. A local variable in between, a
    method of an object of this module, and a wrapper carrying the reader along all walked past it
    (F1, round 6). So the question is asked of the VALUE: `_carries_a_state_path` follows what a
    name holds, and the callee's shape is read only to answer WHO receives it (`_root_name`).

    WHO RECEIVES IT is this file's own code, and that half is asked of the VALUE as well
    (`_value_leads_to`): the callee, or a callee's alias, or a function travelling along as an
    argument, which is how a wrapper reaches the same place. Reading the CALLEE'S SPELLING alone was
    measured blind to a local alias (F1, round 7) -- `reader = _a_second_reader` is ordinary code and
    it hid the receiver completely. A receiver the licence list names is allowed, because a reader
    inside it is accounted for.

    WHERE THE VALUE CAME FROM DECIDES NOTHING; WHERE IT STANDS DOES. A name holding the result of a
    call of this module is code of this module in the CALLEE position and data in an argument
    position, and hanging that difference on the BINDING site instead was measured wrong in both
    directions at once (B1, round 8): `reader = _a_reader_factory(); reader(path)` fed a real reader
    while the rule said nothing, and the opposite setting made the shipped module report
    `absorbed_documents`. So `_receives` answers it, once per position.

    A CALL CARRIES A PATH WHEREVER THE PATH STANDS IN IT, the expression that says WHO is called
    included. A path parked in an attribute of a function of this module -- `_a_reader.__defaults__
    = (path,)` -- is carried by nothing the argument list holds, and `_a_reader()` then reads it
    while naming nothing (measured, B1 round 8: the bytes arrive, the rule reports an empty list).
    The stashed name IS the callee there, so the callee is read as a carrier like every other word.

    WHAT THIS IS AND WHAT IT IS NOT (DEC-0029). It is a SET OF MEASURED ROUTES, each one carried by
    a real reader in `_HOW_A_PATH_TRAVELS`, and it is NOT a proof that a path under the state root
    reaches no unlicensed code. Whether a value in arbitrary Python can arrive somewhere is not
    statically decidable, and the count of routes this has bought -- six, then twelve, then sixteen,
    with a seventeenth found in the same review as the sixteenth -- is what that undecidability looks
    like from inside. A callee that needs a path takes `(state, rel)` and asks `_state_path` itself,
    which puts it back in front of `_by_function`.

    THE OTHER HALF OF THE PROTECTION IS THE ONE THAT IS TOTAL, and in the opposite direction:
    `test_every_state_file_this_module_opens_it_opens_through_read_bytes` runs a plan under an audit
    hook and sees EVERY open of a state file, however the path got there -- and is blind to every
    branch that run does not enter. This rule is the static half of that pair, not its guarantee.

    THE MECHANISM, so that what is left over can be read off it rather than guessed: a hand-over is
    seen where a path and a name of THIS module meet -- in one call expression, following both
    values through the locals of the scope, or in a store whose target is rooted in such a name
    (`_stashed_names`, which puts the reading end back in front of `_by_function`). WHAT IS LEFT
    OVER is therefore a receiver this module's own names do not lead to at the place it is used, and
    that is NOT the same as "another module's object". Five shapes of it are measured rather than
    assumed and all five are carried as `L34` in `docs/POST_V2_WISHLIST.md`: a receiver fetched out
    of `sys.modules` or with `getattr`; a callee that reduces to no name at all, such as a lambda
    applied on the spot; a path parked in an object of ANOTHER module; a call RESULT of this module
    handed on as an ARGUMENT to a foreign wrapper that then calls it (`reader = _a_reader_factory();
    functools.partial(reader, path)()`), which is the price of the split above; and a nested `def`
    that takes the path out of the CLOSURE instead of through an argument, where there is no call
    expression to see at all. Every one of them reaches a real reader. DEC-0022 is why they are left
    standing, and DEC-0029 is why no further ones are hunted.
    """
    own = _module_own_names(tree)
    stashed = _stashed_names(tree, own)
    handed = []
    for scope in ast.walk(tree):
        if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        tainted = _tainted_in(scope, own, stashed)
        aliases = _aliases_in(scope, own)
        for node in ast.walk(scope):
            if not isinstance(node, ast.Call):
                continue
            words = list(node.args) + [pair.value for pair in node.keywords]
            carried = next((found for found in
                            (_carries_a_state_path(word, tainted, own, stashed)
                             for word in [node.func] + words) if found), None)
            if not carried:
                continue
            receivers = set().union(*([_receives(node.func, aliases, own, invoked=True)]
                                      + [_receives(word, aliases, own) for word in words]))
            for who in sorted(receivers - set(_NAMES_A_STATE_FILE)):
                handed.append((scope.name, carried, who, node.lineno))
    return sorted(set(handed))


def test_the_path_builders_of_the_state_object_all_carry_one_of_two_name_shapes():
    """The half of the rule above that is about `ProjectState` rather than about `migrate.py`.

    `_names_a_state_file` reads a name shape -- `root`, `*_path`, `*_root` -- and a shape is a
    claim about the class it is read off. So the claim is asked of the class: every public
    attribute of `ProjectState` that answers with a path under a state root has to carry one of
    those spellings, or `migrate.py` could name a state file through a member this rule is blind
    to.

    RED if `ProjectState` gains a path builder spelled otherwise -- which is exactly the day the
    rule above would start missing a reader.
    """
    state = ProjectState(os.path.join(os.path.dirname(os.path.abspath(__file__)), "no_such_state"))
    builders = []
    for name in sorted(dir(state)):
        if name.startswith("_"):
            continue
        member = getattr(state, name)
        answer = member
        if callable(member):
            try:
                answer = member("PR-0001")
            except Exception:                                            # noqa: BLE001
                continue
        if isinstance(answer, str) and os.path.isabs(answer) \
                and os.path.normcase(answer).startswith(os.path.normcase(state.root)):
            builders.append(name)
    assert builders, "nothing on `ProjectState` answers with a path, so this measures nothing"
    astray = [name for name in builders
              if not (name == "root" or name.endswith(("_path", "_root")))]
    assert not astray, (
        "`ProjectState` names a path builder in a shape `migrate.py`'s static rule cannot see, so "
        "that rule is blind to any reader going through it: %s" % astray)


def test_nothing_but_these_functions_can_name_a_file_of_the_state_directory():
    """The SECOND tripwire under `_read_bytes`'s claim -- total over the FILE, silent about spelling.

    WHY THERE ARE TWO. The audit-hook rule above sees every SPELLING of an open and only the code
    this one run walks. A second reader put in a branch that run never enters is green there. This
    rule reads the whole file and never runs it, so the two blind spots are each other's opposite --
    and neither is the enumeration of opener names that the rule before both of them died of,
    because this one asks how a file can be NAMED at all, one step before anything can be opened.

    THE THIRD ASSERTION IS WHAT MAKES THE FIRST TWO A RULE INSTEAD OF A LIST OF THE FUNCTIONS THAT
    HAPPEN TO COMPOSE TODAY. A function can also be HANDED a finished path, and then it names
    nothing here: `_unreadable_because(exc, _state_path(state, rel))` and `_without_path(text,
    path)` were that shape, they were invisible to this rule, and they sit in a failure branch. A
    real second reader planted in the first of them left BOTH tripwires green, measured
    (2026-08-09, in a clone outside this repo). So the property is not "these functions compose"
    but "a state path reaches no code of this module that is not named here" -- how the value is
    followed, and what is left over when it is, is `_handed_a_finished_path`.

    BOTH ENDS OF THE ENUMERATION, because an enumeration in this repo owes both: a function that
    composes a state path and is not named here fails the first assertion, and a name here that no
    longer composes one fails the second -- so a deleted or renamed function cannot leave a dead
    licence standing.

    RED three ways: a second reader `io.open(_state_path(state, path))` in `render`'s wall branch --
    a branch the audit probe's run does not enter -- puts `render` in the first list; a removed
    entry leaves a name in the second; and handing a composed path to a function of this module
    again puts it in the third. That third way is measured in every spelling it has by
    `test_the_rule_against_handing_a_state_path_on_follows_the_value_and_not_the_call_shape`, which
    is where this assertion's own blindness is kept honest.
    """
    source = io.open(migrate.__file__, encoding="utf-8").read()
    tree = ast.parse(source, migrate.__file__)
    found = _by_function(tree, _stashed_names(tree, _module_own_names(tree)))
    unlicensed = {where: named for where, named in found.items()
                  if where not in _NAMES_A_STATE_FILE}
    assert not unlicensed, (
        "these parts of `%s` can name a file of the state directory and are not accounted for, so "
        "a read from them would be a second story about a file nobody can open: %s"
        % (os.path.basename(migrate.__file__), unlicensed))
    dead = sorted(set(_NAMES_A_STATE_FILE) - set(found))
    assert not dead, (
        "these names carry a licence to compose a state path and compose none, so the list above "
        "is a claim about code that is gone: %s" % dead)
    handed = _handed_a_finished_path(tree)
    assert not handed, (
        "these calls let a composed state path reach code of `%s` that is not licensed above, so "
        "that code can read a state file while naming nothing this rule sees -- take `(state, "
        "rel)` and compose there instead: %s" % (os.path.basename(migrate.__file__), handed))


# A REAL SECOND READER, and everything a planted one needs to be more than a shape in a parse tree:
# it opens the file it is given and keeps the bytes, so a run can show that it read the state. Every
# place a path can be parked in has its own reader for the same reason -- each of them has to be
# able to reach the file, or the corpus below would be measuring text. `_STASHED` is deliberately
# NOT bound here: a `global` declaration is the only thing that makes it a name of the module, which
# is the harder of the two shapes for `_module_own_names` and therefore the one worth planting.
_A_PLANTED_READER = '''

import functools

_PLANTED = []
_A_DICT = {}
_A_LIST = [None]


def _a_second_reader(path):
    _PLANTED.append(open(path, "rb").read())


def _a_reader_of_the_stash():
    _PLANTED.append(open(_STASHED, "rb").read())


def _a_reader_of_the_dict():
    _PLANTED.append(open(_A_DICT["parked"], "rb").read())


def _a_reader_of_the_list():
    _PLANTED.append(open(_A_LIST[0], "rb").read())


class _Sidecar(object):
    def read(self, path):
        _a_second_reader(path)


_SIDECAR = _Sidecar()


def _a_reader_of_the_member():
    _PLANTED.append(open(_SIDECAR.parked, "rb").read())


def _a_reader_factory():
    return _a_second_reader


def _a_reader_of_the_default(parked=None):
    _PLANTED.append(open(parked, "rb").read())
'''

# HOW A COMPOSED PATH CAN TRAVEL from the function that composed it to one that reads it, and who
# ends up holding it. These are AXES of one property -- the value moves -- and not a list of
# offending syntaxes: the rule follows the value, so each entry only has to show that a different
# route reaches the same place. What each one is worth is measured in the test below, twice: the
# route really carries the bytes when it runs, and the rule really names the holder.
#
# THE TWO AXES ARE THE TWO HALVES OF A HAND-OVER, and round 7 measured that only one of them had
# been walked: five ordinary routes -- three ways of PARKING the path where a module name reaches
# it, two of hiding the RECEIVER behind a local -- carried the state bytes while the rule named
# nobody. So the corpus crosses the axes instead of listing syntaxes.
#
# AND ROUND 8 MEASURED THE CROSSING ITSELF. A corpus that walks two axes but never multiplies them
# is a list again: `out of a factory` and `behind a local alias` were both covered while their
# PRODUCT -- a factory result put in a local and called from there -- fed a real reader with the
# rule silent, and so did a `def` nested in the host and a path parked in a callee's own defaults.
# So each axis appears alone AND crossed with the other, and the two entries that cost nothing to
# add (the ones asking the CALLEE with the value rule) stay, because an entry nothing can make red
# is a claim.
#
# AND WHAT IT IS, AFTER ALL OF THAT, IS SIXTEEN MEASURED ROUTES (DEC-0029). Round 9 stopped driving
# this towards completeness: six, then twelve, then sixteen, and the review that measured the
# sixteenth found a seventeenth in the same sitting. Whether a value in arbitrary Python reaches a
# place is not statically decidable, so this corpus says "these routes are seen", never "the others
# do not exist". The ones that are seen and NOT covered are `L34` in `docs/POST_V2_WISHLIST.md`; the
# audit-hook test beside this one is the half that is total over what a run executes.
_HOW_A_PATH_TRAVELS = {
    "in the argument itself": ("_a_second_reader(_state_path(state, rel))", "_a_second_reader"),
    "through a local name": ("path = _state_path(state, rel)\n"
                             "_a_second_reader(path)", "_a_second_reader"),
    "through a computation": ("path = _state_path(state, rel)\n"
                              "_a_second_reader(os.path.join(os.path.dirname(path),\n"
                              "                              os.path.basename(path)))",
                              "_a_second_reader"),
    "beside the reader in a wrapper": ("functools.partial(_a_second_reader,\n"
                                       "                  _state_path(state, rel))()",
                                       "_a_second_reader"),
    "through a member of this module": ("_SIDECAR.read(_state_path(state, rel))", "_SIDECAR"),
    "parked in a name of the module": ("global _STASHED\n"
                                       "_STASHED = _state_path(state, rel)\n"
                                       "_a_reader_of_the_stash()", "_a_reader_of_the_stash"),
    "parked in an attribute of a member of this module": (
        "_SIDECAR.parked = _state_path(state, rel)\n"
        "_a_reader_of_the_member()", "_a_reader_of_the_member"),
    "parked in a mapping of this module": ('_A_DICT["parked"] = _state_path(state, rel)\n'
                                           "_a_reader_of_the_dict()", "_a_reader_of_the_dict"),
    "parked in a list of this module": ("_A_LIST[0] = _state_path(state, rel)\n"
                                        "_a_reader_of_the_list()", "_a_reader_of_the_list"),
    "behind a local alias of the reader": ("reader = _a_second_reader\n"
                                           "reader(_state_path(state, rel))", "_a_second_reader"),
    "out of a factory of this module": ("_a_reader_factory()(_state_path(state, rel))",
                                        "_a_reader_factory"),
    "behind a local alias, with the path in a local too": ("reader = _a_second_reader\n"
                                                           "path = _state_path(state, rel)\n"
                                                           "reader(path)", "_a_second_reader"),
    "out of a factory and called from a local": ("reader = _a_reader_factory()\n"
                                                 "reader(_state_path(state, rel))",
                                                 "_a_reader_factory"),
    "out of a factory, called from a local, path in a local too": (
        "reader = _a_reader_factory()\n"
        "path = _state_path(state, rel)\n"
        "reader(path)", "_a_reader_factory"),
    "into a def nested in the host function": ("def _a_nested_reader(one):\n"
                                               "    _PLANTED.append(open(one, 'rb').read())\n"
                                               "_a_nested_reader(_state_path(state, rel))",
                                               "_a_nested_reader"),
    "parked in the defaults of a function of this module": (
        "_a_reader_of_the_default.__defaults__ = (_state_path(state, rel),)\n"
        "_a_reader_of_the_default()", "_a_reader_of_the_default"),
}


def _with_a_second_reader(source, flow):
    """`migrate.py` with a real second reader planted in `_read_bytes`, reached by `flow`.

    THE HOST IS A LICENSED FUNCTION ON PURPOSE. Its licence covers a reader that COMPOSES, so
    whatever the rule says about this source it says about the hand-over and about nothing else --
    plant the same flow in an unlicensed function and the first assertion fires for the host, which
    would make every entry of the corpus pass for the wrong reason.

    WHERE THE FLOW GOES IS READ OFF THE PARSE -- the end of that function's docstring -- rather than
    matched against a line quoted from another file, so nothing here rots when it is edited.
    """
    tree = ast.parse(source, "<migrate>")
    host = next(node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == "_read_bytes")
    lines = source.splitlines(True)
    planted = "".join("    %s\n" % one for one in flow.splitlines())
    return ("".join(lines[:host.body[0].end_lineno] + [planted]
                    + lines[host.body[0].end_lineno:]) + _A_PLANTED_READER)


def _what_the_rule_names(source):
    """Every piece of unlicensed code the two halves of the rule report about one module source."""
    tree = ast.parse(source, "<migrate>")
    own = _module_own_names(tree)
    stashed = _stashed_names(tree, own)
    named = {where for where in _by_function(tree, stashed) if where not in _NAMES_A_STATE_FILE}
    return named | {who for _where, _what, who, _line in _handed_a_finished_path(tree)}


_READS_ONE_STATE_FILE = '''
import json
import sys

from kernel import migrate
from kernel.state import ProjectState

migrate._read_bytes(ProjectState(sys.argv[1]), "project_config.yaml")
print(json.dumps([one.decode("utf-8") for one in migrate._PLANTED]))
'''


def test_the_rule_against_handing_a_state_path_on_follows_the_value_and_not_the_call_shape(tmp_path):
    """`_handed_a_finished_path`'s own claim, measured on a reader that really reads the state.

    WHY THIS EXISTS. The rule this replaces asked the question of the CALL SYNTAX: the callee had to
    be a bare name of a function of the module, and the composition had to stand inside the argument
    expression. Measured (2026-08-09, in a clone outside this repo) against a real reader printing
    the state bytes it got, three of the four routes below walked past it -- a local variable, a
    member of the module, and a wrapper carrying the reader along -- while the rule's own docstring
    and three sentences in this file claimed the property in full.

    AND THE ROUND AFTER THAT MEASURED THE OTHER HALF OF THE SAME MISTAKE. Following the PATH was not
    enough: five ordinary routes handed the state bytes to a real reader while the rule reported an
    empty list -- a path parked in an attribute, in a mapping or in a list of this module (a store,
    so nothing is ever passed and `ast.Global` sees none of them), and a receiver behind a local
    alias, with or without the path in a local as well (F1, round 7). So `_value_leads_to` follows
    the RECEIVER the way `_carries_a_state_path` follows the path, and `_stashed_names` asks a
    store's target for its root name instead of asking the statement for a `global`.

    AND THE ROUND AFTER THAT MEASURED THE CROSSING OF THE TWO AXES. Four more ordinary routes fed
    the same real reader with the rule silent (B1, round 8): a factory result put in a LOCAL and
    called from there -- the product of the two axes above, with and without the path in a local as
    well -- a `def` nested in the host function, and a path parked in a callee's own `__defaults__`.
    So the asymmetry between "this value IS module code" and "this value CAME OUT OF module code"
    moved from the binding site to the USE site (`_receives`, `invoked`), a nested `def` counts as
    code of this file (`_module_own_names`), and the callee is read as a carrier like every other
    word of the call.

    SO THE QUESTION IS ASKED OF THE VALUE, on both ends. `_carries_a_state_path` follows what a name
    holds and `_value_leads_to` follows who a name is; the callee's shape is read by neither. The
    corpus is the routes a value can take, and every entry of it is measured from both ends in one
    run:

      * IT REALLY READS THE STATE. The planted module is written into a copy of the kernel outside
        this file's own tree and run as a process; the reader opens what it was handed and hands the
        bytes back, and they have to be the marker this test wrote. A route that cannot carry the
        path is a route this test would otherwise be scoring as caught.
      * THE RULE REALLY NAMES THE HOLDER. Not "something was reported" -- the piece of code that
        ends up with the path is named, so an entry cannot pass on a finding about its neighbour.

    AND THE SHIPPED FILE IS SILENT, which is what makes the findings mean anything.

    WHAT THIS TEST THEREFORE CLAIMS, and DEC-0029 is where the line was drawn: that these sixteen
    routes are seen. Not that a seventeenth does not exist -- one was measured in the same review as
    the sixteenth (a nested `def` reading the path out of its CLOSURE, `L34`), and "no value in
    arbitrary Python reaches this place" is not a question a parse can answer. The routes that are
    seen and NOT covered stand in `L34`; the guarantee lives next door, in
    `test_every_state_file_this_module_opens_it_opens_through_read_bytes`, which is total over what
    a run executes and blind to what it does not.

    RED with the syntax rule back: `through a local name`, `through a member of this module`,
    `beside the reader in a wrapper` and `parked in a name of the module` report nothing. RED with
    the value rule but round 6's two blind spots back -- a `global`-only `_stashed_names` and
    `_root_name(node.func)` as the receiver: the three parked routes and the two aliased ones report
    nothing, which is the state this test was in when it was green. RED with round 7's asymmetry
    back, the one that sat on the BINDING site (`_value_leads_to` dropping calls outright): the two
    `out of a factory ... from a local` routes report nothing. RED with the top-level-only
    `_module_own_names`: `into a def nested in the host function` reports nothing. RED with the
    callee left out of the carriers: `parked in the defaults of a function of this module` reports
    nothing. And RED in the other direction -- on the FIRST assertion, about the shipped file -- if
    the argument position resolves a call result too: `absorbed_documents` is reported as receiving
    a path it never gets.
    """
    source = io.open(migrate.__file__, encoding="utf-8").read()
    assert not _what_the_rule_names(source), (
        "the shipped module already trips this rule, so nothing the corpus below reports can be "
        "read as the corpus's doing: %s" % sorted(_what_the_rule_names(source)))

    marker = "name: a-state-file-only-a-planted-reader-would-open\n"
    state = tmp_path / "state"
    os.makedirs(str(state))
    io.open(str(state / "project_config.yaml"), "w", encoding="utf-8", newline="\n").write(marker)
    package = str(tmp_path / "importable")
    shutil.copytree(os.path.join(ROOT, "team-kits", "kernel"), os.path.join(package, "kernel"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    probe = str(tmp_path / "reads_one_state_file.py")
    io.open(probe, "w", encoding="utf-8", newline="\n").write(_READS_ONE_STATE_FILE)

    for route, (flow, holder) in sorted(_HOW_A_PATH_TRAVELS.items()):
        planted = _with_a_second_reader(source, flow)
        assert planted != source, route
        io.open(os.path.join(package, "kernel", "migrate.py"), "w",
                encoding="utf-8", newline="\n").write(planted)
        environment = dict(os.environ, PYTHONPATH=package)
        done = subprocess.run([sys.executable, "-B", probe, str(state)], env=environment,
                              capture_output=True, text=True, timeout=300)
        assert done.returncode == 0, "%s: %s" % (route, done.stdout + done.stderr)
        assert json.loads(done.stdout.strip().splitlines()[-1]) == [marker], (
            "the reader planted %s never got the state file's bytes, so this route measures a "
            "shape and not a reader: %r" % (route, done.stdout))
        assert holder in _what_the_rule_names(planted), (
            "a state path travels %s into `%s` and the rule does not name it, so a reader there is "
            "licensed by nothing and reported by nothing: %s"
            % (route, holder, sorted(_what_the_rule_names(planted))))


def test_every_verdict_the_run_up_can_produce_is_named_where_it_is_documented(tmp_path):
    """DEC-0019: the seam between what `search_coverage` says about itself and what it does.

    The docstring of a classifier is a claim about its answers, and this file has twice been the
    place where such a claim went stale one round after it was written -- the paragraph said "the
    four answers ... and there is no fifth" while a fifth was what the round was adding. So both
    ends are read off the running thing: the verdicts are collected from a state built to reach
    every one of them, and the names are looked up in the module's own constants.

    RED in both directions: a verdict the code produces and the docstring does not name, and a
    verdict name the docstring carries that no state can produce any more.
    """
    state = _plain_state(tmp_path, "verdicts")
    _seven_placements(state, _v1_records_text())          # searched and unsearched
    _write_document(state, ".audit/hook_events.jsonl", "{}\n")        # machinery
    _write_document(state, "generated/index.yaml", "items: []\n")     # kernel
    _write_document(state, migrate.deposit_of("gone.yaml"), "x\n")    # deposit (BUG-0028)
    hidden = os.path.join(state.root, "denied")
    _write_document(state, "denied/old_procs.yaml", _v1_records_text())
    with _unlistable(hidden):                             # unlistable
        produced = {verdict for _rel, verdict, _why in migrate.search_coverage(state)}
    named = {name: value for name, value in vars(migrate).items()
             if name.isupper() and isinstance(value, str) and value in produced}
    assert len(named) == len(produced), (
        "a verdict this module produces is not one of its own named constants: %s" % sorted(
            produced - set(named.values())))
    documented = {word for word in re.findall(r"\b[A-Z][A-Z_]{3,}\b",
                                              migrate.search_coverage.__doc__)
                  if isinstance(getattr(migrate, word, None), str)}
    assert documented == set(named), (
        "the docstring names %s and the code produces %s"
        % (sorted(documented), sorted(named)))


def _proposal_area_spellings():
    """Every case spelling of the proposal area's directory name -- the product, not a sample.

    Derived from `layout.STAGING_DIRNAME` rather than listed, so a renamed directory is measured in
    all of its spellings on the day it is renamed.
    """
    from kernel import layout
    return sorted({"".join(letters) for letters in itertools.product(
        *[(one.lower(), one.upper()) for one in layout.STAGING_DIRNAME])})


def test_every_spelling_of_the_proposal_area_gets_one_answer_from_both_readers(tmp_path, capsys,
                                                                               monkeypatch):
    """One directory, one verdict -- for every way this filesystem lets it be spelled.

    Measured 2026-08-08, before this: a state holding `Staging/PR-0001/old_procs.yaml` (the same
    directory this filesystem opens under either spelling) had the run-up call it SEARCHED while
    `documents` -- which folds case, because `layout._relative` does -- called it no document at
    all. So the dry run read it nowhere, named it nowhere and printed nothing about it, and the
    validator reported a V1 backlog record in it and refused the merge. The one answer the round
    before had built was split again by a capital letter.

    WHAT IS ASSERTED IS THE IMPLICATION, not the verdict: whatever the run-up calls SEARCHED must be
    a file the dry run's own inventory holds, in every spelling. A future rule that answers
    differently is caught by that rather than by this list of spellings.

    AND THE COUNTER-DIRECTION IS WHY THE ANSWER IS *UNSEARCHED* AND NOT *SEARCHED*: an item body
    staged for capture carries an id and a status, so the recogniser cannot tell it from a V1
    record. Two of them in one state are measured below through the recogniser itself -- searching
    the proposal area would turn every proposal into a finding no run can clear, in a project whose
    proposals are the normal way of working.

    RED without the folded predicate in `_coverage_of`: the capitalised spelling is SEARCHED and in
    no inventory, and the assertion in the loop fails for 127 of the 128 spellings.

    What the proposal area costs in the other direction -- a V1 store moved there is named and
    blocks nothing -- is the entry `L19` in `docs/POST_V2_WISHLIST.md`. WHAT THIS DOES NOT MEASURE
    is the rest of the folding: case is only one of the things a filesystem folds, and a trailing
    dot is one it folds while `str.lower` does not -- the entry `L29` in
    `docs/POST_V2_WISHLIST.md`.
    """
    from kernel import layout
    spellings = _proposal_area_spellings()
    assert len(spellings) > 1, "the proposal area's name has no second spelling to measure"
    for index, spelling in enumerate(spellings):
        state = _plain_state(tmp_path, "spelling_%03d" % index)
        rel = "%s/PR-0001/old_procs.yaml" % spelling
        _write_document(state, rel, _v1_records_text())
        coverage = migrate.search_coverage(state)
        inventory = set(migrate.documents(state))
        for path, verdict, _why in coverage:
            assert (verdict == migrate.SEARCHED) == (path in inventory), (
                "%s: the run-up says %s and the document inventory says %s"
                % (path, verdict, path in inventory))
        verdict = dict((path, one) for path, one, _why in coverage)[rel.replace("//", "/")] \
            if rel in [path for path, _v, _why in coverage] else None
        assert verdict in (None, migrate.UNSEARCHED), (
            "%s is searched, and the proposal area is not searched under its own name" % rel)

    # one spelling end to end, through the readers a project actually meets
    state = _state_with_a_root_item(tmp_path, "capitalised")
    repo = os.path.dirname(state.root)
    alternative = next(one for one in spellings if one != layout.STAGING_DIRNAME)
    rel = "%s/PR-0001/old_procs.yaml" % alternative
    _write_document(state, rel, _v1_records_text())
    walked = {path for path, _v, _why in migrate.search_coverage(state)}
    spelled = next(path for path in walked if path.endswith("PR-0001/old_procs.yaml"))
    opened = _reads_recorded(monkeypatch)
    findings = {one["item"]: one for one in report_module().validate_state(state)}
    assert spelled not in opened, "%s was searched by the validator" % spelled
    assert spelled not in findings, (
        "the validator reports a record in the proposal area: %s" % findings.get(spelled))
    _run(state, "migrate", "--dry-run")
    printed = capsys.readouterr().out
    assert spelled in printed, "the dry run says nothing at all about %s" % spelled
    assert _gate_memory_complete(repo).returncode == 0, (
        "a proposal under a differently spelled proposal area refuses the merge")

    # the counter-direction: what the recogniser makes of two ordinary staged item bodies
    for number in (1, 2):
        _write_document(state, "%s/PR-0001/proposal_%d.yaml" % (alternative, number),
                        "id: TSK-000%d\nstatus: DRAFT\ntitle: \"what this task would do\"\n"
                        % number)
    staged = [key for path in ("proposal_1.yaml", "proposal_2.yaml")
              for _ordinal, key, record in migrate.scan_document(yaml.safe_load(io.open(
                  os.path.join(state.root, alternative, "PR-0001", path), encoding="utf-8")))
              if migrate._declares_status(record)
              and migrate._is_backlog_type(migrate.V1_ID_RE.match(key).group(1))]
    assert staged == ["TSK-0001", "TSK-0002"], (
        "the recogniser no longer reads a staged item body as a record, so the reason the "
        "proposal area is out of the search has changed: %s" % staged)
    assert _gate_memory_complete(repo).returncode == 0, (
        "two staged proposals refuse the merge, which is what searching the proposal area costs")


def test_the_remedy_for_an_unsearched_file_names_every_condition_that_keeps_it_out(tmp_path):
    """An answer that names one of two conditions describes the file only half.

    Measured 2026-08-07 and left standing: `staging/PR-0001/old_procs.yaml.bak` was answered with
    "it is no YAML document ... rename it back if it is a V1 store". Renaming it produces
    `staging/PR-0001/old_procs.yaml`, which is unsearched for the OTHER reason -- one nothing in
    the message had mentioned. The reader ends up where they started, having done what they were
    told.

    THE THIRD CONDITION IS IN HERE FOR THE SAME REASON, and it is the one the first cut of that fix
    left behind: a dotted path was decided by an early return, so `staging/.bak/old_procs.yaml`
    named the dotted condition alone. The same half-description, one branch over.

    WHAT CHANGED UNDER DEC-0024 and what did not. The per-condition STEPS are gone -- each of them
    was a move a reader could follow onto a file that was there -- so this no longer measures that
    two steps are joined. The conditions themselves are what the reader needs in order to decide
    anything at all, and a file kept out by two of them still has to carry both.

    RED without the composed reason: the answer for a doubly-excluded file names one condition.
    """
    state = _plain_state(tmp_path, "both_reasons")
    singly = ("old_procs.yaml.bak", "staging/PR-0001/old_procs.yaml", ".bak/old_procs.yaml")
    doubly = ("staging/PR-0001/old_procs.yaml.bak", "staging/.bak/old_procs.yaml")
    for rel in singly + doubly:
        _write_document(state, rel, _v1_records_text())
    why = dict(migrate.unsearched_notes(migrate.search_coverage(state)))
    # every condition a singly excluded file names, derived from its own text rather than from a
    # sentence somebody wrote here
    heads = {rel: why[rel].split(", so nothing here can say")[0] for rel in singly}
    for rel in doubly:
        both = why[rel]
        carried = [head for head in heads.values() if head in both]
        assert len(carried) == 2, (
            "%s is kept out by two conditions and its answer names %d: %r"
            % (rel, len(carried), both))


def _remedy_corpus(state):
    """Every shape a file can be kept out of the search in, over THIS state's own kernel areas.

    DERIVED IN BOTH HALVES. The areas come from `layout.kernel_written_subtrees`, which asks the
    writers' own path builders -- so an area the kernel gains is in the corpus on the day a writer
    starts landing there, which a list of directory names could not be. The shapes are the product
    of the conditions `migrate._classify` can hold at once, so a fourth condition makes this corpus
    twice as large by itself.
    """
    from kernel import layout
    subtrees = layout.kernel_written_subtrees(state.root)
    areas = sorted(set(subtrees) | {one.split("/")[0] for one in subtrees} | {"", "docs"})
    corpus = set()
    for area, dotted, renamed, staged in itertools.product(areas, (0, 1), (0, 1), (0, 1)):
        name = "old_procs.yaml.bak" if renamed else "old_procs.yaml"
        parts = [one for one in area.split("/") if one]
        if dotted and parts:
            parts[0] = "." + parts[0]
        elif dotted:
            name = "." + name
        if staged:
            parts.insert(0, layout.STAGING_DIRNAME)
        corpus.add("/".join(parts + [name]))
    return sorted(corpus)


# EVERY WAY TWO DIFFERENT STRINGS CAN BECOME ONE FILE NAME that this corpus knows about -- each with
# the way to SPELL it and the way to UNDO it. It is an enumeration, and what it owes at BOTH ends is
# only what the code below can pay: a folding this host does not actually perform is not put into the
# model (the pair stays two files on disk), and a folding that changes no subject of the corpus is
# reported as never asked.
#
# WHAT IT DOES NOT PAY -- and the claim that it did was itself the defect (B5, round 8): a folding
# this host performs that this list does not KNOW is reported by nothing here, because the corpus of
# subjects is generated out of `_FOLDINGS` itself. Measured 2026-08-09: removing `"upper case"`
# leaves this test green on NTFS. So the risk of the list is that it is short, and a short list makes
# this measure LESS than it claims rather than wrong.
#
# WHAT LIMITS THE SHORTNESS is not a longer list but the escape: `deposit_of` writes into
# `migrate._NAME_ALPHABET`, on which every folding of this list is the identity. The last assertion
# below is the half of this test that does NOT depend on the list at all -- it creates the deposit
# name of every corpus entry on the real disk and counts the files, so whatever this host folds
# decides that count. A subject the corpus never contains is still outside it; that is the price.
#
# THE UNDO HALF IS NEW IN ROUND 7 AND SO IS THE REASON FOR IT. The model used to be written down --
# `name.rstrip(". ").lower()`, which is what this host does -- and that wired one platform into the
# measurement: on ext4 (WSL `/tmp`, measured 2026-08-09) it disagreed with the disk about 18 pairs of
# this corpus and the corpus folded nothing at all, so both assertions of the test below failed on a
# platform this repo's CI runs (`.github/workflows/ci.yml` runs `ubuntu-latest` and `windows-
# latest`). The PROPERTY is the same on both -- the model agrees with the disk, and a deposit name
# survives whatever this host folds -- only the answer differs, so the answer is asked of the disk.
_FOLDINGS = {
    "upper case": (lambda one: one.upper(), lambda one: one.lower()),
    "a trailing dot": (lambda one: one + ".", lambda one: one.rstrip(".")),
    "a trailing space": (lambda one: one + " ", lambda one: one.rstrip(" ")),
    "a decomposed accent": (lambda one: unicodedata.normalize("NFD", one),
                            lambda one: unicodedata.normalize("NFC", one)),
    "a composed accent": (lambda one: unicodedata.normalize("NFC", one),
                          lambda one: unicodedata.normalize("NFC", one)),
}

# WHAT THE FOLDINGS ARE APPLIED TO, and the reason there is more than one: a folding has to be the
# ONLY difference in at least one pair, or the corpus scores an encoder as injective for a reason
# that has nothing to do with it. Measured 2026-08-09: with an accented name as the only subject,
# the encoder that lost `PROC-0811a` against `PROC-0811A` passed this test, because upper-casing
# that name also changes the accent's own escape and the two names stay apart by accident.
# The decomposed spelling is a subject and not only a folding, because a folding that changes
# nothing about any subject is one the corpus never reaches -- and the assertion in the test says so.
_FOLDING_SUBJECTS = ("old_procs.yaml", "Proçedures.yaml",
                     unicodedata.normalize("NFD", "Proçedures.yaml"))


def _foldings_this_filesystem_performs(where):
    """Which entries of `_FOLDINGS` THIS filesystem really performs -- asked of it, not written down.

    Both spellings of a pair are created in a directory of their own, and the folding is one this
    host performs exactly when one file is left. That is the same question the test below asks of
    the whole corpus; it is asked here first because the MODEL has to be built out of the answer,
    and a model built out of one host's answer is what round 7 found hard-wired.
    """
    performed = []
    for ordinal, name in enumerate(sorted(_FOLDINGS)):
        spell, _undo = _FOLDINGS[name]
        subject = next((one for one in _FOLDING_SUBJECTS if spell(one) != one), None)
        assert subject is not None, (
            "no subject of the corpus is changed by %r, so this host is never asked about it and "
            "the entry measures nothing" % name)
        probe = os.path.join(where, "performs_%d" % ordinal)
        os.makedirs(probe)
        for spelling in (subject, spell(subject)):
            io.open(os.path.join(probe, spelling), "w", encoding="utf-8", newline="\n").write("x")
        if len(os.listdir(probe)) == 1:
            performed.append(name)
    return performed


def _folded(name, performed):
    """What this filesystem makes of a file name before it decides WHICH FILE it is -- a model.

    It is a model of another program's behaviour, so it is built from what that program answered
    (`_foldings_this_filesystem_performs`) and never used anywhere it has not been measured:
    `test_two_sources_this_filesystem_would_fold_together_get_two_deposits` creates both names of
    every pair of a corpus and requires this answer and the filesystem's own to agree, in both
    directions. On a host that folds nothing this is the identity, which is the right model there.

    TO A FIXED POINT, because one undo step can expose what another one strips: `x. ` loses the dot
    only after the space is gone, and in the other order only after a second pass. Which steps are
    in the list at all is the disk's answer rather than an order somebody wrote here, so no order
    they are applied in may decide the result.
    """
    while True:
        after = name
        for one in performed:
            after = _FOLDINGS[one][1](after)
        if after == name:
            return name
        name = after


def test_two_sources_this_filesystem_would_fold_together_get_two_deposits(tmp_path):
    """`deposit_of`'s injectivity, asked AFTER the filesystem instead of of the string.

    THE CLASS, IN THE ENCODER'S OWN WORDS: two names a filesystem folds into one are one name, so
    injectivity has to hold after the folding and not only in the string. It has been closed twice
    for ONE folding and reopened by the next: the trailing dot was escaped, and then a document
    holding `PROC-0811a` and `PROC-0811A` produced two instructions of one report landing on one
    file -- measured 2026-08-09 on a real dry run, `instructions: 2, deposit files afterwards: 1`.
    A YAML key tells the two records apart; this filesystem does not tell their deposits apart.

    SO THE ANSWER IS THE ALPHABET AND NOT A THIRD ESCAPE (`migrate._NAME_ALPHABET`): every character
    a deposit name can carry is one on which the folding is the identity. That is a property, and
    this measures the property rather than the pairs that produced it -- the corpus is generated by
    applying every folding this test knows to a seed that carries something for each of them.

    BOTH ENDS, AND BOTH READ OFF THE FILESYSTEM:

      * the sources themselves are created, so a folding this host does not perform cannot be
        counted as one that was survived -- and `_folded`, the model the report's own collision
        check uses, has to give the same answer as the disk for every pair.
      * the deposit names are created, and there have to be as many files as there were distinct
        sources.

    RED with `urllib.parse.quote(rel, safe="").replace(".", "%2E")` back: the upper-case pair gives
    two names, the disk gives one file, and the count is short.

    ON A HOST THAT FOLDS NOTHING -- a case-sensitive filesystem, which is what this repo's CI runs
    on `ubuntu-latest` -- the first assertion is the identity on both sides and the second falls
    back to injectivity in the string. That is less, and it says so instead of failing.

    THERE IS NO THIRD ASSERTION, and its absence is the round-8 correction (B4). It read
    `bool(folded_here) == bool(performed)` and could not fail: `disagreed` is asserted empty
    directly above it, the corpus holds the probe's own pair by construction, and the coupling then
    follows in both directions from what has already been asserted -- measured on ext4, where the
    first two assertions are vacuous, a host answer of `[]` was GREEN. Asking the same two sources
    per folding and per subject instead was tried and dropped for the same reason: whenever a
    folding is in `performed`, `_folded` collapses its pair by construction, so `disagreed` already
    decides it; the pairs where the two could part company need two undos of this list to coincide
    on one pair, which happens on neither filesystem this repo runs on. A longer spelling of the
    same vacuum is not an improvement on it.

    WHAT REALLY CARRIES THE HOST'S ANSWER is that the model is BUILT from it: an error in
    `_foldings_this_filesystem_performs` moves `_folded`, and `disagreed` reports it against the
    disk. That is one measurement with one authority, and it is the one that goes red.
    """
    corpus = {spell(subject) for subject in _FOLDING_SUBJECTS
              for spell, _undo in _FOLDINGS.values()}
    corpus |= set(_FOLDING_SUBJECTS)
    asked = str(tmp_path / "asked")
    os.makedirs(asked)
    performed = _foldings_this_filesystem_performs(asked)

    # WHAT THIS HOST REALLY FOLDS, pair by pair, and whether the model built from its answer agrees.
    disagreed = []
    for ordinal, (one, other) in enumerate(sorted(itertools.combinations(sorted(corpus), 2))):
        where = str(tmp_path / ("pair%d" % ordinal))
        os.makedirs(where)
        for name in (one, other):
            io.open(os.path.join(where, name), "w", encoding="utf-8", newline="\n").write(name)
        on_disk = len(os.listdir(where)) == 1
        if on_disk != (_folded(one, performed) == _folded(other, performed)):
            disagreed.append((one, other, "one file" if on_disk else "two files"))
    assert not disagreed, (
        "`_folded` and this filesystem disagree about which names are one name, so the collision "
        "check that uses the model is measuring something else: %s" % disagreed)

    deposits = str(tmp_path / "deposits")
    os.makedirs(deposits)
    for source in sorted(corpus):
        name = migrate.deposit_of(source).split("/")[-1]
        io.open(os.path.join(deposits, name), "w", encoding="utf-8", newline="\n").write(source)
    assert sorted(os.listdir(deposits)) and len(os.listdir(deposits)) == len(corpus), (
        "%d sources this filesystem tells apart were given deposit names it does not, so a copy "
        "would land on a copy of something else: %d file(s) for %s"
        % (len(corpus), len(os.listdir(deposits)), sorted(corpus)))


_THE_INSTRUCTION = "COPY it -- the original stays where it is -- to "


def _instruction(why):
    """The path the printed answer tells a reader to put a COPY at, taken out of the message.

    THE SEAM THIS WHOLE FAMILY LIVED IN is between what the code derives and what a reader is told,
    so the destination is parsed back out of the sentence rather than asked of `deposit_of`. A
    message whose instruction half names no path, or more than one, is a failure of the caller
    rather than something to skip.
    """
    _head, marker, tail = why.partition(_THE_INSTRUCTION)
    if not marker:
        return None
    return re.findall(r"`([^`]+)`", tail)


def test_the_instruction_this_module_prints_has_exactly_one_composer():
    """`copy_instruction`'s own claim -- that there is one shape and one place that makes it.

    THE CLAIM IS WHAT THE REST OF THIS FAMILY RESTS ON. Two printed instructions -- the coverage
    note for a file out of reach and the refusal of a record too large -- used to be two sentences,
    and the second of them named a bare directory while the first named a constructed file. If a
    third sentence composed the phrase itself, the tests that parse it (`_instruction`) would read
    it and the composer's guarantees (a constructed name, the note about a name too long) would not
    apply to it. So the claim is asked of the shipped code rather than left in a docstring.

    RED with a second composer: any other literal carrying the phrase puts its file and line here.
    """
    composers = []
    for base, directories, files in os.walk(os.path.join(ROOT, "team-kits")):
        directories[:] = [one for one in directories if one != "__pycache__"]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            for node in ast.walk(ast.parse(io.open(path, encoding="utf-8").read(), path)):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                        and _THE_INSTRUCTION in node.value:
                    composers.append(
                        (os.path.relpath(path, ROOT).replace(os.sep, "/"), node.lineno))
    assert len(composers) == 1, (
        "the instruction this harness prints is composed in %d places, so what one of them "
        "guarantees says nothing about the others: %s" % (len(composers), composers))
    assert migrate.copy_instruction("staging/x").startswith(_THE_INSTRUCTION), (
        "the one composer no longer produces the phrase the tests read it by")


def _carry_out(state, source, target):
    """Do to the state exactly what the instruction says: copy, and leave the original alone."""
    destination = os.path.join(state.root, *target.split("/"))
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copy(os.path.join(state.root, *source.split("/")), destination)


def test_no_instruction_this_command_prints_can_take_a_file_away(tmp_path):
    """DEC-0024, measured by CARRYING OUT every instruction of one report at once.

    WHY THE WHOLE REPORT AND NOT ONE LINE. Three review rounds closed this family one clause at a
    time -- the target was a kernel area, then a wall, then an occupied path -- and the fourth
    round found the shape no per-line clause can see: TWO answers of ONE run named one free path.
    Measured 2026-08-09, three hiding places of one name, each held out of the search by a
    different condition:

        .legacy/old_procs.yaml           -> old_procs.yaml          taken=False
        old_procs.yaml.bak               -> old_procs.yaml          taken=False
        staging/PR-0001/old_procs.yaml   -> PR-0001/old_procs.yaml  taken=False

    A reader who followed the first two lost a V1 store to a silent `mv`, and every authority the
    derivation had been taught to ask answered "free".

    WHAT REPLACES IT IS A CONSTRUCTION AND NOT A FOURTH AUTHORITY (`migrate.deposit_of`): a COPY,
    into an area under `staging/` this command owns, under a name that is the source path itself,
    percent-encoded. So this measures the three properties that construction has, and it measures
    them by doing what the report says instead of by reading what it says:

      * every named destination lies inside that area -- never a wall, never a kernel path, never
        anything a gate or another command owns;
      * no two lines of one report name one file -- asked after the FOLDING and not of the strings,
        because two names this filesystem folds together are one file. That the model of the folding
        used here is the filesystem's own is measured separately, in
        `test_two_sources_this_filesystem_would_fold_together_get_two_deposits`, which is also where
        the encoder's injectivity under it lives; `unquote` inverting the encoding is asserted here
        rather than assumed;
      * after every instruction of the report has been carried out, every file that was there
        before is byte-for-byte the file it was -- the sources included.

    WHICH INSTRUCTIONS THIS IS OVER, said because the test's name is wider than its corpus: the
    coverage notes of one report. The dry run prints ONE further instruction that is deliberately
    not in it -- the occupied landing place, whose second step removes the original on purpose
    (`L35`, the user's decision of 2026-08-09). Its own measurement is
    `test_the_place_a_taken_landing_is_freed_to_is_named_and_lies_outside_the_state_directory`, and
    it is a different claim: not "nothing is taken away" but "the file is somewhere else first".

    RED without the construction: with the derivation restored, the corpus below produces two lines
    naming one destination, and the byte comparison at the end reports the source that was lost.
    """
    from kernel import layout
    state = _plain_state(tmp_path, "one_report")
    corpus = _remedy_corpus(state)
    assert len(corpus) > 50, "the corpus collapsed to %d paths" % len(corpus)
    for ordinal, rel in enumerate(corpus):
        _write_document(state, rel, "# %d\n%s" % (ordinal, _v1_records_text()))
    before = _snapshot(state.root)

    answers = migrate.unsearched_notes(migrate.search_coverage(state))
    assert len(answers) > 20, "only %d paths of the corpus are unsearched" % len(answers)
    asked = str(tmp_path / "asked")
    os.makedirs(asked)
    performed = _foldings_this_filesystem_performs(asked)
    told = {}
    for rel, why in answers:
        named = _instruction(why)
        assert named is not None, (
            "%s is named and the answer tells the reader nothing: %r" % (rel, why))
        assert len(named) == 1, (
            "%s: the instruction half names %d paths, so a reader has to choose: %r"
            % (rel, len(named), why))
        target = named[0]
        assert migrate.in_deposit(target), (
            "%s: the instruction names %s, which is outside the area this command owns"
            % (rel, target))
        assert layout.is_in_proposal_area(target), target
        assert not layout.is_kernel_written(state.root, target), target
        assert urllib.parse.unquote(target.split(migrate._DEPOSIT_MARK, 1)[1]) == rel, (
            "%s: the deposit name does not carry its own source back, so two sources could share "
            "one name: %s" % (rel, target))
        # ...AND THE COLLISION IS ASKED AFTER THE FOLDING AND NOT BEFORE IT. Two names this
        # filesystem folds into one ARE one place, so comparing the strings would pass over exactly
        # the pair that costs a file. What the folding is was asked of this host above; that the
        # model agrees with it is `test_two_sources_this_filesystem_would_fold_together_get_two_
        # deposits`.
        folded = _folded(target, performed)
        assert folded not in told, (
            "COLLISION: two answers of one report land on %s -- for %s and for %s"
            % (folded, told.get(folded)[0], rel))
        told[folded] = (rel, target)

    for _folded_target, (rel, target) in sorted(told.items()):
        _carry_out(state, rel, target)
    after = _snapshot(state.root)
    for path, blob in sorted(before.items()):
        assert after.get(path) == blob, (
            "carrying out the answers of ONE report changed %s -- the report cost the reader a "
            "file it told them about" % path)

    # ...AND THE COPY IS NOT ANSWERED WITH A COPY OF ITSELF. A deposit file is still under
    # `staging/`, so the run-up still gives it a verdict -- its OWN class now (`DEPOSIT`, BUG-0028),
    # counted rather than named one `NOT SEARCHED` line each -- and pointing it at a deposit again
    # would nest one level per run, the step-that-changes-nothing this module prints nowhere.
    coverage_again = migrate.search_coverage(state)
    again = dict(migrate.deposit_notes(coverage_again))
    unsearched_again = dict(migrate.unsearched_notes(coverage_again))
    for _folded_target, (rel, target) in sorted(told.items()):
        assert target in again, (
            "%s is not named at all, so the coverage is no longer total" % target)
        assert target not in unsearched_again, (
            "%s is a deposit copy still listed one `NOT SEARCHED` line at a time (BUG-0028)" % target)
        assert _instruction(again[target]) is None, (
            "%s is a deposit copy and the report tells the reader to deposit it again: %r"
            % (target, again[target]))


def test_applied_deposit_remedies_are_counted_not_a_not_searched_line_each(tmp_path):
    """BUG-0028: a deposit is a copy this command's own remedy made, and one appears per remedy a
    reader applies -- so listing each in the "did not search" section grows it without bound as the
    project follows the report (synaipse: 26 remedies applied -> 62 NOT SEARCHED lines).

    RED without the DEPOSIT verdict: every deposit is UNSEARCHED, so `unsearched_notes` (and the
    `NOT SEARCHED` lines the dry run and `validate` print from it) grows by one for each applied
    remedy, and there is no count to read instead.
    """
    state = _plain_state(tmp_path, "deposits")
    # one genuinely unsearched V1 store -- the baseline the deposits must NOT be added to
    _write_document(state, "old_store.yaml.bak", _v1_records_text())
    baseline = len(migrate.unsearched_notes(migrate.search_coverage(state)))
    assert baseline >= 1, "the baseline reaches no unsearched file, so growth cannot be measured"

    applied = 6
    for n in range(applied):
        _write_document(state, migrate.deposit_of("doc%02d.yaml" % n), "x\n")

    coverage = migrate.search_coverage(state)
    assert len(migrate.unsearched_notes(coverage)) == baseline, (
        "applying %d deposit remedies grew the `did not search` section, so a project that follows "
        "the report accumulates a line per remedy (BUG-0028)" % applied)
    assert len(migrate.deposit_notes(coverage)) == applied, (
        "the deposit copies are not counted as their own class: %s"
        % migrate.deposit_notes(coverage))

    # the two readers of the coverage carry the count, not the lines
    scan = report_module().record_scan_coverage(state)
    assert len(scan["deposits"]) == applied, scan
    assert not any(migrate.in_deposit(one["path"]) for one in scan["not_searched"]), scan["not_searched"]


def _staging_keys_of(state):
    """What each reader of `staging/` calls a KEY -- the validator's findings and the brief's list.

    ONE QUESTION, ASKED OF EVERY READER THERE IS. The comment at `migrate._DEPOSIT_MARK` argues that
    a deposit is a file name because a DIRECTORY there is a staging key, and it used to ask that of
    `validate_state` alone. `generate_session_brief` reads the same directory, and it listed every
    entry -- so it announced `staging/.gitkeep/` to every session of every fresh project, and a
    deposit copy on top of that as soon as the migration started naming one.
    """
    findings = [one["item"] for one in report_module().validate_state(state)
                if "orphaned staging dir" in one["message"]]
    brief = yaml.safe_load(io.open(
        report_module().generate_session_brief(state, "dev-team", "0", "hard"),
        encoding="utf-8").read())
    return sorted(findings), sorted(brief["staging_pointers"])


def test_a_deposit_name_too_long_to_create_says_so_where_it_is_printed(tmp_path):
    """The price of an injective name, said in the message that charges it.

    THE REST THAT STAYS OPEN is the entry `L32` in `docs/POST_V2_WISHLIST.md`: the name cannot be
    shortened without giving two sources one place, so past the limit the printed instruction is not
    executable at all. This measures the half that is closed -- that the message says so.

    THE CONSTRUCTION NEVER SHORTENS -- that is what makes two sources two names -- so a long enough
    source produces a deposit name this filesystem will not take. Measured 2026-08-09 on this host:
    a source of 248 characters is created without complaint, its deposit name is 262, and creating
    THAT answers `OSError: [Errno 22] Invalid argument`. Until now the instruction was printed with
    nothing said about it, so the reader met the refusal instead of the report.

    THE PAIRING IS THE MEASUREMENT, and it is deliberately a coupling to the host rather than a
    restatement of `_NAME_MAX_CHARS`: the clause has to appear exactly when the filesystem refuses
    the name. On a host with a different limit this goes red -- which is the right answer, because
    then the constant is what is wrong.

    RED without the clause: the instruction for the long source carries no sentence about itself
    while the name it names cannot be created.
    """
    state = _state_with_a_root_item(tmp_path, "long_names")
    for length, expected in ((248, True), (100, False)):
        rel = "a" * (length - len(".yaml")) + ".yaml"
        _write_document(state, rel, _v1_records_text())
        target = migrate.deposit_of(rel)
        name = target.split("/")[-1]
        try:
            io.open(os.path.join(str(tmp_path), name), "w").close()
            refused = False
        except OSError:
            refused = True
        assert refused is expected, (
            "a deposit name of %d characters is %s by this filesystem, which is not what "
            "`_NAME_MAX_CHARS` (%d) says" % (len(name), "refused" if refused else "taken",
                                             migrate._NAME_MAX_CHARS))
        assert bool(migrate.deposit_note(target)) is refused, (
            "the note about the name and the filesystem's answer disagree for a name of %d "
            "characters: %r" % (len(name), migrate.deposit_note(target)))

    # ...AND IT REACHES THE READER WHERE THE NAME IS PRINTED, not only where it is composed.
    long_source = "a" * (248 - len(".yaml")) + ".yaml"
    told = dict(migrate.unsearched_notes(migrate.search_coverage(state)))
    assert long_source not in told, (
        "a `.yaml` document at the top level is searchable, so this fixture measures the wrong file")
    renamed = long_source + ".bak"
    _write_document(state, renamed, _v1_records_text())
    told = dict(migrate.unsearched_notes(migrate.search_coverage(state)))
    clause = migrate.deposit_note(migrate.deposit_of(renamed))
    assert clause, "this fixture no longer produces an over-long deposit name, so the line below is "\
                   "an empty string in a haystack and measures nothing"
    assert clause in told[renamed], (
        "the printed instruction names a file this filesystem cannot take and says nothing about "
        "it: %r" % told[renamed])


def test_the_deposit_an_instruction_names_is_no_staging_key_either_reader_reports(tmp_path):
    """Why the deposit is a file NAME under `staging/` and not a directory under it.

    A DIRECTORY under `staging/` is a staging KEY: `report.validate_state` walks them and reports
    every one that is no active item as an orphaned staging dir, and `report.generate_session_brief`
    lists them as the session's staging pointers. A deposit directory would therefore make this
    command's own printed instruction produce a finding in another command -- the reader does what
    one part of the harness says and another part reports them for it.

    BOTH READERS, because the claim is about the directory and not about one function: until this
    round only the validator was asked, and the brief was announcing the template's own
    `staging/.gitkeep` as a key in every project.

    BOTH DIRECTIONS IN ONE STATE, because the claim is about the difference: the deposit file is
    carried without a finding, and a directory of the same name in the same place produces one.

    RED if `deposit_of` composes a directory (the first half fails with the finding the second half
    asserts), and RED without the brief's own `isdir` filter (the deposit and `.gitkeep` come back
    as staging pointers).
    """
    state = _state_with_a_root_item(tmp_path, "deposit_is_no_key")
    _write_document(state, ".legacy/old_procs.yaml", _v1_records_text())
    os.makedirs(state.staging_root(), exist_ok=True)
    io.open(os.path.join(state.staging_root(), ".gitkeep"), "w").close()
    why = dict(migrate.unsearched_notes(migrate.search_coverage(state)))
    target = _instruction(why[".legacy/old_procs.yaml"])[0]
    _carry_out(state, ".legacy/old_procs.yaml", target)

    orphans, pointers = _staging_keys_of(state)
    assert not orphans, (
        "the deposit this command's own instruction names is reported as an orphaned staging key: "
        "%s" % orphans)
    assert pointers == [], (
        "a session is told that files under `staging/` are staging keys -- the deposit this "
        "command's instruction names among them: %s" % pointers)

    os.makedirs(os.path.join(state.root, *target.split("/")) + "-as-a-directory")
    orphans, pointers = _staging_keys_of(state)
    assert orphans and pointers, (
        "a directory under `staging/` is no longer reported by both readers, so the sentences "
        "above about why the deposit is a file name measure nothing: %s / %s"
        % (orphans, pointers))


def _state_paths_in(text, state):
    """Every backticked word of `text` that names a place inside this state directory.

    THE SEGMENTS COME FROM THE STATE ITSELF, not from a list written here: what a kernel writer
    lands in (`layout.kernel_written_subtrees`), the proposal area, and whatever the directory
    really holds. A word with a space in it is a command line and not a path.
    """
    from kernel import layout
    heads = {one.split("/")[0] for one in layout.kernel_written_subtrees(state.root)}
    heads.add(layout.STAGING_DIRNAME)
    heads.update(name.lower() for name in os.listdir(state.root))
    found = []
    for word in re.findall(r"`([^`]+)`", text or ""):
        if " " in word.strip():
            continue
        head = word.strip().replace("\\", "/").strip("/").split("/")[0].lower()
        if head in heads:
            found.append(word)
    return found


def test_the_place_an_oversized_record_is_sent_to_is_constructed_and_costs_nothing(v1_state):
    """DEC-0024 for the refusal that is NOT about the coverage: a record too large for one item.

    THIS LINE SAID "move its bulk to `staging/`", and it is the shape the whole family has: a
    DIRECTORY, so the reader picks the file name, and a picked name can already be taken. Measured
    2026-08-09 as a real chain rather than as a worry: `gate_write_scope` answers rc 0 for a tool
    write onto an EXISTING file under `staging/` -- the one place under `project_memory/` it lets
    through -- so a followed instruction overwrites inside the session, with no shell outside it.
    And `move` is the second half: what a reader moves out of a V1 file is gone from it.

    WHAT REPLACES IT IS THE SAME CONSTRUCTION THE COVERAGE NOTE USES, which is the point of
    `migrate.copy_instruction` -- two printed instructions, one shape, one composer. The name is
    `record_deposit_of`, so it belongs to ONE record of ONE document and can collide with nothing
    else this report prints; the verb is COPY, so the V1 record stays whole; and the shortening
    happens in the reader's own V1 document, which is the one file the whole remedy asks them to
    touch.

    RED with the old sentence back: `_instruction` finds no destination, and the assertion that the
    remedy names a deposit fails on `staging/`.
    """
    bulk = "x" * 40000
    io.open(os.path.join(v1_state.root, "bulky.yaml"), "w", encoding="utf-8", newline="\n").write(
        "processes:\n"
        "  PROC-0811:\n"
        "    title: \"a record that inlines its own detail\"\n"
        "    owner: bookkeeper\n"
        "    steps: [\"%s\"]\n"
        "    status: PROPOSED\n"
        "    created: 2026-01-06\n" % bulk)
    before = _snapshot(v1_state.root)
    entry = next(one for one in _planned(v1_state)["records"] if one["legacy_id"] == "PROC-0811")
    assert entry["verdict"] == "blocked", entry

    named = _instruction(entry["reason"])
    assert named and len(named) == 1, (
        "the refusal for a record too large names no single place to copy its bulk to: %r"
        % entry["reason"])
    target = named[0]
    assert migrate.in_deposit(target), (
        "the bulk is sent somewhere this command did not construct, so the reader picks the name: "
        "%s" % target)
    # THE LOCATOR HALF OF THE NAME IS THE DOCUMENT AND THE RECORD, and the tail is the body digest
    # (BUG-0026). Decoded rather than rebuilt with a hand-computed digest, so this asserts the shape
    # the reader is handed without re-deriving the content hash the code takes.
    prefix = "%s/%s" % (migrate.layout.STAGING_DIRNAME, migrate._DEPOSIT_MARK)
    assert target.startswith(prefix), target
    decoded = urllib.parse.unquote(target[len(prefix):])
    assert decoded.startswith("bulky.yaml/PROC-0811/"), decoded
    assert len(decoded.rsplit("/", 1)[1]) == 64, (
        "the record deposit name carries no body digest, so a re-run with a shortened record would "
        "overwrite this copy (BUG-0026): %s" % decoded)
    # ...AND IT COLLIDES WITH NO DOCUMENT'S OWN DEPOSIT, which is the argument in
    # `record_deposit_of`'s docstring: a document is a file, so no path of this state has it as a
    # directory component. Asked of every document this state really holds, not of the one.
    inventory = migrate.documents(v1_state)
    assert "bulky.yaml" in inventory, (
        "the document holding the record is not in the inventory, so the comparison below is over "
        "the wrong set: %s" % inventory)
    clash = [rel for rel in inventory if migrate.deposit_of(rel) == target]
    assert not clash, (
        "one record's bulk and a whole document are sent to one place: %s" % clash)

    # ...AND THE PROSE IS A SENTENCE. `_too_large` answers with a whole clause, and it used to be
    # dropped into the middle of another one ("the item would be N bytes ... as an error does not
    # fit in one item: ..."). A remedy a reader cannot parse is a remedy nobody follows.
    assert "as an error does not fit" not in entry["reason"], entry["reason"]

    # ...AND CARRYING IT OUT COSTS NOTHING, which is the whole of DEC-0024 in one line.
    _carry_out(v1_state, "bulky.yaml", target)
    after = _snapshot(v1_state.root)
    for path, blob in sorted(before.items()):
        assert after.get(path) == blob, (
            "following the refusal's own remedy changed %s" % path)


def test_two_records_of_one_document_that_differ_only_in_case_get_two_deposits(v1_state):
    """The chain F2 came back through, carried out end to end instead of argued about.

    A V1 DOCUMENT CAN HOLD BOTH `PROC-0811a` AND `PROC-0811A`, because a YAML key is case-sensitive
    and V1 numbered by hand (`migrate.V1_ID_RE` reads the discriminator for exactly that reason).
    This filesystem is not case-sensitive, so while the deposit name carried the record id in its own
    case, ONE report printed TWO instructions that landed on ONE file. Measured 2026-08-09 on a real
    dry run, before the alphabet: `instructions: 2, deposit files afterwards: 1`.

    WHY THAT IS A LOST RECORD AND NOT A TIDINESS PROBLEM. The instruction says to copy the bulk out
    and then shorten the record IN THE V1 FILE -- so a reader who follows both loses the first
    record's body from the V1 file and from the deposit, and the deposit they are left with is the
    other record's. That is the whole of DEC-0024's "no printed remedy can take a file away",
    reached through the encoder rather than through a derived target.

    RED with `quote(rel, safe="").replace(".", "%2E")` back: two instructions, one file.
    """
    bulk = "x" * 40000
    io.open(os.path.join(v1_state.root, "bulky.yaml"), "w", encoding="utf-8", newline="\n").write(
        "processes:\n"
        + "".join("  PROC-0811%s:\n"
                  "    title: \"a hand-numbered record that inlines its own detail\"\n"
                  "    owner: bookkeeper\n"
                  "    steps: [\"%s\"]\n"
                  "    status: PROPOSED\n"
                  "    created: 2026-01-06\n" % (discriminator, bulk)
                  for discriminator in ("a", "A")))
    records = [one for one in _planned(v1_state)["records"]
               if one["legacy_id"].startswith("PROC-0811")]
    assert sorted(one["legacy_id"] for one in records) == ["PROC-0811A", "PROC-0811a"], (
        "the two hand-numbered records are not read as two, so this measures one record: %s"
        % [one["legacy_id"] for one in records])

    told = []
    for entry in records:
        assert entry["verdict"] == "blocked", entry
        named = _instruction(entry["reason"])
        assert named and len(named) == 1, entry["reason"]
        told.append(named[0])
    assert len(told) == 2, told

    from kernel import layout
    for target in told:
        _carry_out(v1_state, "bulky.yaml", target)
    landed = [one for one in os.listdir(v1_state.staging_root())
              if migrate.in_deposit("%s/%s" % (layout.STAGING_DIRNAME, one))]
    assert len(landed) == len(told), (
        "one report printed %d instructions and this filesystem holds %d file(s) afterwards, so a "
        "reader who follows both keeps one record's bulk and loses the other's: %s -> %s"
        % (len(told), len(landed), told, landed))


def _oversized_record_document(state, steps):
    """One oversized V1 procedure whose bulk is `steps` list-items -- the reader's own shorten knob."""
    io.open(os.path.join(state.root, "bulky.yaml"), "w", encoding="utf-8", newline="\n").write(
        "processes:\n"
        "  PROC-0811:\n"
        "    title: \"a record that inlines its own detail\"\n"
        "    owner: bookkeeper\n"
        "    steps:\n%s"
        "    status: PROPOSED\n"
        "    created: 2026-01-06\n"
        % "".join('      - "%s"\n' % ("x" * 300) for _ in range(steps)))


def _oversized_target(state):
    """The single COPY place the dry run names for PROC-0811, as the reader is handed it."""
    entry = next(one for one in _planned(state)["records"] if one["legacy_id"] == "PROC-0811")
    assert entry["verdict"] == "blocked", entry
    named = _instruction(entry["reason"])
    assert named and len(named) == 1, entry["reason"]
    return named[0]


def test_an_oversized_record_shortened_too_little_earns_a_second_deposit_not_an_overwrite(v1_state):
    """BUG-0026: the remedy for an oversized RECORD changes its own source, so the deposit name has
    to move with the content or a re-run destroys the first copy.

    THE CHAIN, CARRIED OUT (real synaipse ADR-0013 in shape): the dry run blocks PROC-0811 and says
    "COPY it to <deposit>. Then shorten the record in the V1 file." A reader copies it, shortens the
    record TOO LITTLE -- it is still oversized -- and re-runs. The message states the ITEM size, not
    the record-text size, so shortening iteratively is the normal case, not a mistake. If the second
    dry run hands back the SAME deposit name, the reader's second COPY lands on the first, and the
    bulk they took out of the V1 file (1604 bytes on the real record) is then in NEITHER place.

    RED without `_body_digest` in `record_deposit_of`: the two contents earn one name, `_carry_out`
    overwrites, and one deposit file stands where two records' bulk was -- exactly the loss DEC-0024
    forbids, reached through a source that does not stay put rather than through a picked name.
    """
    from kernel import layout
    _oversized_record_document(v1_state, steps=140)
    first = _oversized_target(v1_state)
    _carry_out(v1_state, "bulky.yaml", first)
    first_bytes = os.path.getsize(os.path.join(v1_state.root, *first.split("/")))

    # the reader shortens the record -- but not enough; it still does not fit in one item
    _oversized_record_document(v1_state, steps=90)
    second = _oversized_target(v1_state)
    assert second != first, (
        "a shortened-but-still-oversized record is handed the same deposit name as its longer self, "
        "so the reader's second copy overwrites the first and the removed bulk is lost: %s" % second)

    _carry_out(v1_state, "bulky.yaml", second)
    landed = sorted(one for one in os.listdir(v1_state.staging_root())
                    if migrate.in_deposit("%s/%s" % (layout.STAGING_DIRNAME, one)))
    assert len(landed) == 2, (
        "the two contents left %d deposit file(s), so following the two instructions overwrote one: "
        "%s" % (len(landed), landed))
    # the FIRST copy still holds its own bytes -- nothing the second run did reached back to it
    assert os.path.getsize(os.path.join(v1_state.root, *first.split("/"))) == first_bytes, (
        "the first deposit's size changed, so the second copy landed on it after all")


def test_no_remedy_the_validator_prints_names_a_place_inside_the_state_directory(tmp_path):
    """The OTHER report's half of DEC-0024, executed rather than read.

    The migration's instructions are carried out by the tests above. `report.validate_state` prints
    remedies too, on the same documents and to the same reader, and until this round they had only
    been read. So they are produced here from a state that reaches each of them, and the question is
    asked of the answer: a remedy that names a place inside the state directory is a place the
    reader has to create or overwrite, and this validator offers none -- it sends every one of them
    OUT of the state directory or to a command.

    RED if a remedy here starts naming a landing place: the finding's own text carries it.
    """
    state = _state_with_a_root_item(tmp_path, "validator_remedies")
    _write_document(state, "broken.yaml", "processes:\n  PROC-0001: {\n")
    _write_document(state, "big.yaml", "notes: \"%s\"\n" % ("x" * (report_module().
                                                                  DOCUMENT_MAX_BYTES + 10)))
    _write_document(state, "still_v1.yaml",
                    "processes:\n  PROC-0002:\n    title: t\n    status: ACTIVE\n")
    os.makedirs(os.path.join(state.staging_root(), "TSK-9999"))
    findings = report_module().validate_state(state)
    assert len(findings) > 3, "this state reaches too few remedies to measure anything: %s" % findings
    for finding in findings:
        named = _state_paths_in(finding.get("remedy", ""), state)
        assert not named, (
            "the validator's remedy for %s sends the reader to a place inside the state directory, "
            "which is a name they have to pick or overwrite: %s -- %r"
            % (finding["item"], named, finding["remedy"]))

    # ...AND THE READER ABOVE IS NOT BLIND, measured on the one place this harness really does name:
    # the migration's own instruction for the same state. Without this the loop's silence would say
    # only that `_state_paths_in` found nothing anywhere.
    _write_document(state, ".legacy/old_procs.yaml", _v1_records_text())
    notes = dict(migrate.unsearched_notes(migrate.search_coverage(state)))
    told = _state_paths_in(notes[".legacy/old_procs.yaml"], state)
    assert told and all(migrate.in_deposit(one) for one in told), (
        "the check above cannot see a place inside the state directory even where one is named, so "
        "its silence measures nothing: %s" % told)


def _parameter_names(tree):
    """{function name: [parameter names]} for every `def` in one parsed module.

    Nested definitions included, because a helper defined inside a function is called the same way
    from inside it. A name defined twice in one module keeps the LAST definition, which is what the
    call sites below it see.
    """
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found[node.name] = [one.arg for one in
                                list(node.args.posonlyargs) + list(node.args.args)]
    return found


def _remedy_literals(tree, module, signatures):
    """[(how it is one, the constant)] -- every string this module ships AS a remedy.

    THREE WAYS A STRING BECOMES ONE, and all three are the product's own convention read off the
    parse rather than a spelling guessed here:

      * it carries the WORD `Remedy` itself -- the shape a message composes for its own reader;
      * it stands in a `remedy` SLOT: the keyword argument `_kernel.block` prints under
        `"\\nRemedy: %s"`, or the `remedy` key of a `report.validate_state` finding. The word is
        added by the printer, so the literal never carries it.
      * it is BOUND to a parameter called `remedy` by its POSITION. Which parameter a positional
        argument lands in is a fact about the callee, so it is read off the callee's own `def`
        (`signatures`) rather than off the call: `_finding(severity, item, message, remedy)`,
        `_refuse(pipeline, what, why, remedy)`, `_fail(message, remedy)`.

    EVERY NARROWING OF THIS DOMAIN SO FAR WAS MEASURED TO BE A DOMAIN AND NOT A PROPERTY, three
    times. Round 7: the spelling `Remedy:` missed `Remedy, per document:` (221 literals under the
    colon, 224 under the word), and the one offender only the punctuation kept out named a
    kernel-written area. Round 8 (B2): the word missed the slots outright -- 95 shipped slot values
    at the time of the finding, NONE of which carries a `Remedy` of its own, so the whole `remedy=`
    half of the product was outside the rule while seven of those values named a place inside a
    state directory. Round 9: the KEYWORD spelling missed every remedy handed over by position --
    57 of them, `report.validate_state`'s whole set among them, and two of those were the round's
    blocking product findings.

    WHERE THE CALLEE IS LOOKED UP, and what that costs: a bare name against the module being read,
    a dotted one against the module of that name (`_kernel.block` against `_kernel.py`). A remedy
    parameter of a function reached under any other spelling -- an alias, an attribute of an object,
    an import that renames -- is outside this domain, and the counters below only say that no half
    of it has collapsed, never that it is complete.
    """
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and re.search(r"\bRemedy\b", node.value):
            found.append(("the word", node))
        if isinstance(node, ast.Call):
            found += [("a `remedy=` slot", pair.value) for pair in node.keywords
                      if pair.arg == "remedy" and isinstance(pair.value, ast.Constant)
                      and isinstance(pair.value.value, str)]
            if isinstance(node.func, ast.Name):
                parameters = signatures.get(module, {}).get(node.func.id, [])
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                parameters = signatures.get(node.func.value.id, {}).get(node.func.attr, [])
            else:
                parameters = []
            found += [("a remedy parameter", argument)
                      for index, argument in enumerate(node.args)
                      if index < len(parameters) and parameters[index] == "remedy"
                      and isinstance(argument, ast.Constant) and isinstance(argument.value, str)]
        if isinstance(node, ast.Dict):
            found += [("a `remedy` key", value) for key, value in zip(node.keys, node.values)
                      if isinstance(key, ast.Constant) and key.value == "remedy"
                      and isinstance(value, ast.Constant) and isinstance(value.value, str)]
    return found


def _places_inside_a_state_directory(text, heads):
    """Every path-shaped word of `text` that lies inside a state directory.

    PATH-SHAPED IS A PROPERTY OF THE WORD -- it holds a separator -- and NOT of the punctuation
    around it. Requiring backticks was measured to be the whole difference between a rule and a
    silence (B2, round 8): `cli.py`'s "put the bulk in staging/<key>/" is the very defect DEC-0024
    was written for, and it went unreported for as long as the backticks were absent; putting them
    back made this test red without changing a single character of the offer.

    EVERY COMPONENT IS ASKED, not the first: `project_memory/staging/<task-id>/` puts the state
    root's own name in front, and reading only the head answered `project_memory` -- a name that is
    in no list here -- about seven shipped slot values that all end inside `staging/`.

    AND THE SEPARATOR IS COUNTED BEFORE ANY OF IT IS TAKEN AWAY, which is round 9's correction. The
    strip of the surrounding slashes used to happen FIRST, so `evidence/` -- a directory named the
    only way a sentence can name one -- lost the very character that makes it path-shaped and fell
    out one line later. Three shipped kit remedies were sending readers into a canonical directory
    behind that silence (`guard_memory_budget`), and the offer read exactly like a pass here.
    """
    found = []
    for word in re.findall(r"[^\s`'\"()\[\]{},;]+", text):
        cleaned = word.strip().replace("\\", "/")
        if "/" not in cleaned:
            continue
        if {one.lower().rstrip(".,;:") for one in cleaned.strip("/").split("/") if one} & heads:
            found.append(word)
    return found


def test_no_remedy_literal_this_repo_ships_names_a_place_inside_a_state_directory():
    """The same question asked of every remedy LITERAL this repo ships, one step before anything runs.

    WHY BOTH. The test above runs two commands and sees the remedies those two runs reach; this one
    reads the shipped string CONSTANTS and sees the ones no fixture happens to produce. Neither is
    the other's duplicate: a remedy no state reaches is invisible there, and a remedy whose place is
    composed at runtime is invisible here.

    THAT SECOND BLINDNESS IS NOT HYPOTHETICAL AND IS NOT CLOSED. `state.py` and `approvals.py` each
    build a remedy that names a path inside the state directory through a format placeholder and
    proposes `git restore` onto it -- in the approval case discarding the user's edit is the point.
    Neither is a literal, so neither is in this domain, and the name of this test says LITERAL for
    that reason. It is carried as `L33` in `docs/POST_V2_WISHLIST.md` with the mechanism and the
    reason it is a rest rather than a blocker.

    WHAT A REMEDY IS and WHERE IT MAY NOT SEND ANYONE are both properties, and each of them has its
    own reader here: `_remedy_literals` for the domain, `_places_inside_a_state_directory` for the
    offence. Both were narrowed by a SPELLING until round 8, and both silences were measured.

    THE RULE IS ASKED OF THE PLACE AND NOT OF THE INTENT, and that is a deliberate over-reach.
    Telling a reader to LOOK at `generated/index.yaml` endangers nothing; telling them to PUT
    something in `staging/<key>/` is the defect DEC-0024 exists for. Nothing here can tell the two
    apart -- the difference is a verb, and a rule that read verbs would be a list of them. So the
    rule refuses both, and the shipped messages that only wanted the reader to look now name the
    THING instead of the path (`the generated index`, `the archive`). That costs a path in four
    kernel messages and buys a rule with no spelling in it.

    WHAT IT DOES NOT ASK is whether a remedy proposes a MOVEMENT at all. Two shipped remedies of
    `report.validate_state` still tell the reader to take a file out of the state directory and name
    no destination -- `L35` in `docs/POST_V2_WISHLIST.md` carries both, with a reason PER REMEDY:
    unavailable for one of them, available and not built for the other, which is not the same
    sentence and stood as one until round 10. This rule is about the place a remedy NAMES, and a
    place it does not name is outside it by construction.

    RED for any new one like it, and RED with any of the five narrowings back -- three measured in
    round 8, two in round 9: the backtick requirement (`cli.py`'s `staging/<key>/` disappears), the
    first-component-only reading (the seven `project_memory/staging/...` slot values disappear), the
    word-only domain (the whole `remedy=` half of the product disappears), the KEYWORD-only domain
    (`report.py`'s `staging/evidence` and three siblings disappear -- 56 literals), and stripping a
    word's separators before asking whether it is path-shaped (three kits' `evidence/` disappears).
    """
    from kernel import layout
    heads = {one.split("/")[0] for one in layout.kernel_written_subtrees(os.curdir)}
    heads.add(layout.STAGING_DIRNAME)
    shipped = []
    for base, directories, files in os.walk(os.path.join(ROOT, "team-kits")):
        directories[:] = [one for one in directories if one != "__pycache__"]
        shipped += [os.path.join(base, name) for name in sorted(files) if name.endswith(".py")]
    # THE CALLEES ARE COLLECTED BEFORE ANY CALL IS READ, because a positional remedy is a fact
    # about the `def` and the `def` is regularly in another file than the call.
    parsed = {path: ast.parse(io.open(path, encoding="utf-8").read(), path) for path in shipped}
    signatures = {}
    for path, tree in parsed.items():
        signatures.setdefault(os.path.splitext(os.path.basename(path))[0], {}).update(
            _parameter_names(tree))
    seen, offending = collections.Counter(), []
    for path in shipped:
        module = os.path.splitext(os.path.basename(path))[0]
        for how, node in _remedy_literals(parsed[path], module, signatures):
            seen[how] += 1
            offending += [(os.path.relpath(path, ROOT).replace(os.sep, "/"), node.lineno, how,
                           word)
                          for word in _places_inside_a_state_directory(node.value, heads)]
    assert not offending, (
        "these shipped remedies name a place inside a state directory, so the name the reader puts "
        "there is one they picked and one that can already be taken (DEC-0024): %s" % offending)
    # ...AND THE READER IS NOT BLIND TO THE SHAPE THAT HID THREE SHIPPED OFFERS UNTIL ROUND 9: a
    # directory named the only way a sentence can name one, with its single separator at the end.
    # An absence proves nothing about a reader that cannot see the thing, so the reader is asked
    # directly -- the silence above and this line together are the claim.
    bare = "%s/" % sorted(heads)[0]
    assert _places_inside_a_state_directory("put it in %s and move on" % bare, heads) == [bare], (
        "a word whose only separator is the trailing one is not read as a path any more, so an "
        "offer naming a bare state directory reads exactly like a pass: %r" % bare)
    # ALL THREE HALVES OF THE DOMAIN, counted apart: each round that added one found the ones
    # before it carrying the whole rule, and a collapse of any of them would be a silence that
    # reads exactly like a pass.
    assert seen["the word"] > 100 and seen["a `remedy=` slot"] + seen["a `remedy` key"] > 50 \
        and seen["a remedy parameter"] > 40, (
        "the collector above has collapsed on one part of its domain: %s" % dict(seen))


def _scaffolded_kit(tmp_path, name, kit="dev-team"):
    """A project the way the scaffold leaves it -- the kit's own state templates, hooks, settings.

    WHICH FILES ARE WALLS IS A PROPERTY OF AN INSTALLATION and not of a document, so the one
    measured with this is the installation a kit really ships: its `templates/project_memory/` as
    the state, its `hooks/` and its `settings/settings.json` as the `.claude/` beside it. A hook
    this file writes (`_install_wall_gate`) reaches the same condition and answers a different
    question -- whether the RULE holds -- while this one answers what a user's own project gets.
    """
    repo = str(tmp_path / name)
    base = os.path.join(ROOT, "team-kits", kit)
    shutil.copytree(os.path.join(base, "templates", "project_memory"),
                    os.path.join(repo, "project_memory"))
    shutil.copytree(os.path.join(base, "hooks"), os.path.join(repo, ".claude", "hooks"))
    shutil.copy(os.path.join(base, "settings", "settings.json"),
                os.path.join(repo, ".claude", "settings.json"))
    return ProjectState(os.path.join(repo, "project_memory"))


def test_a_document_a_registered_gate_reads_is_offered_no_way_to_move_or_rename_it(tmp_path):
    """The SOURCE end of the family: the answer for a WALL, and what following it does to its gate.

    A wall is a kit document whose content a registered, refusal-capable hook reads. Two of the
    three a dev kit ships are prose, and prose has no document suffix -- so a wall is UNSEARCHED,
    and the answer used to be "rename it back to a .yaml document". Measured 2026-08-09 on a real
    scaffolded dev-team project: `product/masterplan.md` was answered with exactly that. A reader
    who does it leaves `gate_memory_complete` reading a file that is not there, and nothing in this
    harness writes that file afterwards.

    THE ORACLE IS THE INSTALLATION'S OWN WALL LIST, run before and after: `layout.gated_documents`
    walks the state directory, so a document a gate reads that is no longer there is a document
    that has dropped out of it. Both directions are here -- following what this command prints
    leaves the list and the bytes exactly as they were, and following the step it used to print
    takes the wall out of the list.

    RED without the deposit construction: the answer for `product/masterplan.md` names a rename,
    and carrying it out empties the wall list.
    """
    from kernel import layout
    state = _scaffolded_kit(tmp_path, "wall_source")
    repo = os.path.dirname(state.root)
    walls = layout.gated_documents(repo, state.root)
    unsearched = dict(migrate.unsearched_notes(migrate.search_coverage(state)))
    prose_walls = sorted(set(walls) & set(unsearched))
    assert prose_walls, (
        "no wall of this installation is unsearched, so nothing here reaches the case: walls=%s"
        % sorted(walls))

    before = _snapshot(state.root)
    for rel in prose_walls:
        named = _instruction(unsearched[rel])
        assert named and len(named) == 1, (rel, unsearched[rel])
        assert migrate.in_deposit(named[0]), (rel, named)
        assert named[0] not in walls, (
            "%s: the instruction names another document a gate of this installation reads (%s)"
            % (rel, named[0]))
        _carry_out(state, rel, named[0])
    assert layout.gated_documents(repo, state.root) == walls, (
        "following the printed answers changed which documents this installation's gates read")
    after = _snapshot(state.root)
    for rel in prose_walls:
        assert after[rel] == before[rel], "%s was rewritten by its own answer" % rel

    # ...AND THE COUNTER-DIRECTION: the step this command used to print, carried out on the same
    # wall. Nothing here asserts a message; it renames the file the way the old sentence said and
    # asks the installation what its gates now read.
    victim = prose_walls[0]
    renamed = os.path.splitext(victim)[0] + migrate._DOCUMENT_SUFFIXES[0]
    os.replace(os.path.join(state.root, *victim.split("/")),
               os.path.join(state.root, *renamed.split("/")))
    assert victim not in layout.gated_documents(repo, state.root), (
        "renaming %s left it in the wall list, so this state cannot measure what the old step "
        "cost" % victim)


def test_a_document_nested_deeper_than_the_reader_can_follow_is_named_not_a_crash(tmp_path):
    """What the unconditional `except` in `_read_document` carries, measured at the one class that
    is neither an `OSError` nor a `yaml.YAMLError`.

    THE ENCODING CASE IS NOT THAT CLASS, which is what this test exists to separate: bytes handed
    to `yaml.safe_load` come back as `yaml.reader.ReaderError` for anything that is not a stream,
    and a `ReaderError` IS a `YAMLError`. So the encoding test's own claim that it goes red without
    the widened `except` was wrong about its own code; what it goes red without is the byte-reading.

    THE CLASS THAT IS NEITHER: `yaml`'s composer recurses once per nesting level, so a document
    nested deeper than this interpreter allows raises `RecursionError` -- a `RuntimeError`. The
    depth is derived from `sys.getrecursionlimit()` rather than typed, because it is a fact about
    the running interpreter and not about this file.

    AND THE COUNTER-DIRECTION AT THE BOUNDARY: `scan_document` walks recursively too, so "the
    parser gives up first" is a claim that has to be measured where it is decided. The deepest
    document that still READS is scanned in the same run.

    RED with `except (OSError, yaml.YAMLError)` restored: the `RecursionError` leaves the reader,
    `validate_state` raises out of this test, and the shipped merge gate answers with its crash
    handler instead of a finding that names the file.
    """
    state = _state_with_a_root_item(tmp_path, "deep")
    repo = os.path.dirname(state.root)
    deep = sys.getrecursionlimit() * 4
    _write_bytes(state, "deep.yaml", b"a: " + b"[" * deep + b"]" * deep)
    payload, problem = migrate._read_document(state, "deep.yaml")
    assert payload is None and problem, "a document this deep parsed after all"
    assert "RecursionError" in problem, problem
    findings = {one["item"]: one for one in report_module().validate_state(state)}
    assert findings["deep.yaml"]["severity"] == "error"
    assert "NOT SEARCHED" in findings["deep.yaml"]["message"]
    refused = _gate_memory_complete(repo)
    said = refused.stdout + refused.stderr
    assert refused.returncode == 2, said
    assert "internal error" not in said and "Traceback" not in said, said
    assert "deep.yaml" in said, said
    assert not migrate.plan_is_executable(migrate.build_plan(state))

    # THE BOUNDARY ITSELF: the deepest document this reader still returns a payload for is one the
    # record walk survives. Bisected here rather than assumed, because both readers recurse and
    # the one that gives up first decides whether the other is ever reached.
    low, high = 1, deep
    while low < high:
        middle = (low + high + 1) // 2
        _write_bytes(state, "boundary.yaml", b"a: " + b"[" * middle + b"]" * middle)
        if migrate._read_document(state, "boundary.yaml")[1] is None:
            low = middle
        else:
            high = middle - 1
    assert low > 1, "no depth reads at all, so there is no boundary to measure"
    _write_bytes(state, "boundary.yaml", b"a: " + b"[" * low + b"]" * low)
    payload, problem = migrate._read_document(state, "boundary.yaml")
    assert problem is None, problem
    assert migrate.scan_document(payload) == [], (
        "the deepest readable document is one this walk cannot follow -- the parser is no longer "
        "the tighter bound, and `scan_document` needs its own answer")


def test_a_v1_store_inside_a_kernel_written_area_is_in_no_report(tmp_path):
    """The entry is `L20` in `docs/POST_V2_WISHLIST.md`.

    `KERNEL` is a verdict about an AREA, not about who wrote a file: everything under a kernel
    writer's directory is taken to be the kernel's own writing. A V1 store copied into `generated/`
    is therefore in neither report -- not searched, and not named as unsearched either -- and the
    merge gate answers rc 0 over it. The same file one directory up is a finding and refuses the
    merge, which is what makes the silence a silence rather than a policy.

    WHICH AREAS THIS REALLY COVERS is asked of the areas themselves rather than assumed, and the
    answer is smaller than "everything the kernel writes": under an ITEM directory the same file is
    caught, by the item validator, as an item missing every required field. The message is about
    something else, but the merge does stop -- so the hole is the kernel-written areas no item
    validator walks, and the loop below is what keeps that distinction measured instead of stated.

    What limits it is not this classifier: `gate_write_scope` refuses every tool write under the
    state directory, so putting a file there takes a shell outside the session or a checkout.
    """
    state = _state_with_a_root_item(tmp_path, "kernel_area")
    repo = os.path.dirname(state.root)
    silent, caught = [], []
    for area in ("generated", "archive/PROC/2026", "product/active"):
        rel = "%s/old_procs.yaml" % area
        _write_document(state, rel, _v1_records_text())
        verdicts = dict((one, verdict) for one, verdict, _why in migrate.search_coverage(state))
        assert verdicts[rel] == migrate.KERNEL, rel
        coverage = report_module().record_scan_coverage(state)
        assert rel not in [one["path"] for one in coverage["not_searched"]], (
            "%s is named as unsearched after all, so it is not in this silent class" % rel)
        assert not [one for one in report_module().validate_state(state)
                    if "V1 backlog record" in one["message"]], (
            "%s was searched for V1 records after all" % rel)
        (silent if _gate_memory_complete(repo).returncode == 0 else caught).append(rel)
        os.remove(os.path.join(state.root, *rel.split("/")))
    assert silent, (
        "no kernel-written area hides a V1 store from every reader any more -- L20 is closed and "
        "the entry is what is out of date")
    assert caught == ["product/active/old_procs.yaml"], (
        "which areas stop the merge for an unrelated reason has moved: silent=%s caught=%s"
        % (silent, caught))
    # the counter-direction: one directory up, the same bytes are a V1 finding and a refusal
    _write_document(state, "old_procs.yaml", _v1_records_text())
    refused = _gate_memory_complete(repo)
    assert refused.returncode == 2 and "V1 backlog record" in refused.stderr, refused.stderr


def test_two_item_bodies_outside_the_kernels_own_areas_refuse_every_merge(tmp_path):
    """The entry is `L25` in `docs/POST_V2_WISHLIST.md`.

    A V2 item body NAMES ITSELF -- `id: SR-0001` with a `status`, in a file of that name -- which is
    exactly the shape `migrate.scan_document` recognises a V1 backlog record by. The two are
    indistinguishable to the recogniser, and the only thing keeping a project's own items out of the
    SR-0001 scan is WHERE they lie: the kernel's own areas are skipped wholesale, and the proposal
    area is skipped for this very reason. A body that ends up anywhere else -- a copy, a hand-saved
    item, a proposal lifted out of `staging/` -- is read as a V1 record.

    Measured here: two of them turn `git merge` into a refusal that names them, and nothing inside a
    session can clear it, because `gate_write_scope` refuses every tool write under the state
    directory. That is L16's shape one document over.
    """
    state = _state_with_a_root_item(tmp_path, "self_naming")
    repo = os.path.dirname(state.root)
    assert _gate_memory_complete(repo).returncode == 0
    for number in (1, 2):
        _write_document(
            state, "notes/SR-000%d.yaml" % number,
            "id: SR-000%d\nproduct_requirement: PR-0001\ntitle: t\nstatus: PROPOSED\n"
            "revision: 1\napproval_ref: null\n" % number)
    findings = [one for one in report_module().validate_state(state)
                if "V1 backlog record" in one["message"]]
    assert len(findings) == 2, findings
    refused = _gate_memory_complete(repo)
    assert refused.returncode == 2 and "SR-0001" in refused.stderr, refused.stderr
    # ...and the counter-direction, which is why the exclusion is where it is: the same two bodies
    # in the proposal area say nothing at all.
    for number in (1, 2):
        os.remove(os.path.join(state.root, "notes", "SR-000%d.yaml" % number))
        _write_document(
            state, "staging/PR-0001/SR-000%d.yaml" % number,
            "id: SR-000%d\nproduct_requirement: PR-0001\ntitle: t\nstatus: PROPOSED\n"
            "revision: 1\napproval_ref: null\n" % number)
    assert _gate_memory_complete(repo).returncode == 0, (
        "a staged item body refuses the merge, which is what searching the proposal area costs")


def test_the_import_mark_says_where_an_item_came_from_and_claims_no_lever(v1_state):
    """DEC-0021, measured on both halves: what the mark is called, and what reads it.

    The field was `migration_confirmation_required`, a name that promises a confirmation duty. Two
    rounds measured that nothing enforces it. A name is a claim like a docstring is, so the seam
    between the two is measured here rather than argued: every imported item carries the mark, and
    NOTHING in the shipped kernel, hooks or scripts reads it -- while `approval_ref`, the bolt that
    is read, stays null.

    THE SECOND HALF IS READ OFF THE CODE, not off a list: every shipped Python file is parsed and
    every place that takes the mark OUT of a mapping is collected. Naming the field in a printed
    sentence is not reading it, which is why the rule is about the operation and not about the
    occurrence: `render` and `_receipt_fields` both tell a reader that the mark is written, and
    neither asks any item for it.

    WHICH OPERATIONS COUNT AS READING IS AN ENUMERATION OF TWO -- a subscript that loads it and a
    `.get` of it -- and it does not cover the ways a reader would most naturally be written.
    Measured 2026-08-08, one real reader inserted at a time: `IMPORT_MARK in item`, `item.pop(
    IMPORT_MARK)`, a key comparison inside a field loop and `getattr` all stay GREEN; only the
    subscript is red. So this is a tripwire for the shape DEC-0021 was written against, not for
    every reader -- the gap is the entry `L27` in `docs/POST_V2_WISHLIST.md`.

    RED without the rename: the written field is the old name, and the name itself claims a lever
    the harness does not build.
    """
    import ast

    from kernel.backlog_types import IMPORT_MARK
    assert _migrated(v1_state) == 0
    items = [yaml.safe_load(io.open(path, encoding="utf-8"))
             for _name, path in v1_state.iter_active_items("PROC")]
    items += _archived_items(v1_state, "PROC")
    assert items, "this run imported nothing, so there is no mark to measure"
    for item in items:
        assert item[IMPORT_MARK] is True, item
        assert item["approval_ref"] is None, item
        assert "confirmation" not in " ".join(item), (
            "an imported item carries a field whose name promises a confirmation: %s" % sorted(item))

    def names_the_mark(node):
        return ((isinstance(node, ast.Name) and node.id == "IMPORT_MARK")
                or (isinstance(node, ast.Constant) and node.value == IMPORT_MARK))

    readers, writes = [], []
    for current, dirs, files in os.walk(os.path.join(ROOT, "team-kits")):
        dirs[:] = [one for one in dirs if one != "__pycache__"]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(current, name)
            source = io.open(path, encoding="utf-8").read()
            if IMPORT_MARK not in source and "IMPORT_MARK" not in source:
                continue
            tree = ast.parse(source, filename=path)
            owner = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for inner in ast.walk(node):
                        owner[id(inner)] = node.name
            for node in ast.walk(tree):
                where = "%s.%s" % (name, owner.get(id(node), "<module level>"))
                if isinstance(node, ast.Subscript) and names_the_mark(node.slice):
                    (writes if isinstance(node.ctx, ast.Store) else readers).append(where)
                elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "get"
                        and any(names_the_mark(one) for one in node.args)):
                    readers.append(where)
    assert sorted(set(writes)) == ["migrate.py._with_legacy",
                                   "state.py.capture_migrated_archive",
                                   "state.py.capture_migrated_unresolved"], sorted(set(writes))
    assert not readers, (
        "the mark has a reader again (%s). DEC-0021 decided against one: a second bolt beside "
        "`approval_ref` is two answers to one question." % sorted(set(readers)))


def test_a_broken_document_says_what_broke_before_it_says_which_check_it_took_down(tmp_path):
    """A refusal names the CAUSE that fired it, not the check that fell over because of it.

    `project_config.yaml` is a kit document a user fills by hand, so a YAML typo in it is an
    ordinary accident -- and it lands in the same scan as a V1 monolith. The refusal was right and
    its framing was not: the message opened with "NOT SEARCHED for V1 backlog records", so a
    project whose config had one bad line was refused a merge AND a push with a sentence about a
    V1 backlog it never had. The direction stays: the file is unreadable, whether it holds records
    is unknown, and unknown is not empty.

    RED without the reordered message: the finding and the gate's own text open with the check
    instead of the cause.
    """
    state = _state_with_a_root_item(tmp_path, "framing")
    repo = os.path.dirname(state.root)
    _write_document(state, "project_config.yaml", "name: demo\nstacks: [python\n")
    finding = {one["item"]: one for one in report_module().validate_state(state)}
    message = finding["project_config.yaml"]["message"]
    assert message.startswith("It could not be read ("), message
    assert message.index("could not be read") < message.index("NOT SEARCHED"), message
    assert "UTF-8" in finding["project_config.yaml"]["remedy"], (
        "the remedy does not name the encoding a repair has to save in, which is how the file "
        "got here: %s" % finding["project_config.yaml"]["remedy"])
    refused = _gate_memory_complete(repo)
    assert refused.returncode == 2
    said = refused.stdout + refused.stderr
    assert said.index("could not be read") < said.index("NOT SEARCHED"), said


def test_an_unreadable_item_refuses_the_run_instead_of_importing_its_record_again(v1_state):
    """The idempotency scan may not skip a file in silence -- what it cannot read, it names.

    `imported_legacy_ids` is the whole of "has this record already been imported": it reads every
    item the kernel wrote and collects the `legacy_fields.legacy_id` they carry. A file it skipped
    was a `legacy_id` the plan did not know, so the record it came from was planned as NEW -- and a
    second run would write a second item for one V1 record, which is exactly the state the plan
    refuses elsewhere with a message about two items claiming one id.

    RED without the named reason in `imported_legacy_ids`: the plan comes back executable, with
    the record classified `translatable` rather than `already_imported`.
    """
    # the V1 store stays where it is, so a re-run READS its records again and has to recognise
    # them: SR-0005 would otherwise move a fully absorbed document to `legacy/` and there would be
    # nothing left for the idempotency scan to be asked about
    _install_wall_gate(v1_state, "process_definitions.yaml")
    assert _migrated(v1_state) == 0
    done = _planned(v1_state)
    assert {entry["verdict"] for entry in done["records"]} == {"already_imported"}, (
        "the fixture did not import cleanly, so nothing here measures a re-run")
    live = sorted(name for name, _path in v1_state.iter_active_items("PROC"))
    assert live, "no active item carries a legacy id, so the scan below has nothing to lose"
    # the LEGACY id the chosen item vouches for, read off the item itself: the V2 id it was
    # allocated is a different name that happens to look alike in an empty store
    blinded_record = v1_state.read_item(live[0])["legacy_fields"]["legacy_id"]

    item = os.path.join("procedures", "active", live[0] + ".yaml")
    with open(os.path.join(v1_state.root, item), "ab") as handle:
        handle.write(b"\nthis: [\n")
    blinded = _planned(v1_state)
    assert not migrate.plan_is_executable(blinded), (
        "an item the idempotency scan could not read left the run executable, so the record it "
        "holds would be imported a second time: %s"
        % sorted({entry["verdict"] for entry in blinded["records"]}))
    assert item.replace(os.sep, "/") in migrate._unreadable_paths(blinded), blinded["unreadable"]
    assert any(entry["legacy_id"] == blinded_record and entry["verdict"] != "already_imported"
               for entry in blinded["records"]), (
        "the record whose item became unreadable is still recognised as imported, so this "
        "measures the refusal and not the blindness it exists for")


def _wall_lines(printed):
    """Every line of the dry run's WALLS section, stripped -- one document per line.

    Its own reader because a wall's name also appears under CARRIED, NOT TRANSLATED: matching on
    the name alone matches two lines and makes an assertion depend on which came first.
    """
    lines = printed.splitlines()
    start = lines.index(next(line for line in lines if line.startswith("WALLS (")))
    return [line.strip() for line in lines[start + 1:]
            if len(line.split()) > 1 and line.split()[1].endswith(".py")]


def _wall_line(printed):
    """The one WALLS line of a dry run -- taken from the section, not from the document name.

    The same file also appears under CARRIED, NOT TRANSLATED, so matching the name alone matches
    two lines and would make the assertion below depend on which came first.
    """
    lines = printed.splitlines()
    start = lines.index(next(line for line in lines if line.startswith("WALLS (")))
    found = [line for line in lines[start + 1:]
             if len(line.split()) > 1 and line.split()[1].endswith(".py")]
    assert len(found) == 1, printed
    return found[0]


def test_a_wall_that_does_not_parse_is_not_printed_as_a_wall_with_nothing_in_it(v1_state):
    """The fourth caller of the reader discarded the reason, so two states looked alike.

    The dry run prints each wall with its top-level keys, and that listing is the ONE place a
    wall's own bytes are read: a wall is never searched for records, never imported and never
    moved, so nothing else in the run says anything about its content. An unparsable wall and an
    empty one both printed `top-level keys: -`, and the difference between them is whether the
    gate standing in front of a merge can read the file it blocks on.

    RED without the reason in `render`: the unparsable wall prints the same line as an empty one.
    """
    _install_wall_gate(v1_state, "compliance_register.yaml")
    plan = migrate.build_plan(v1_state)
    assert "compliance_register.yaml" in plan["gated_documents"], plan["gated_documents"]
    _write_document(v1_state, "compliance_register.yaml", "obligations:\n  - {\n")
    wall = _wall_line(migrate.render(migrate.build_plan(v1_state), v1_state))
    assert "NOT READ" in wall, (
        "a wall this run could not read is printed as one with no keys: %r" % wall)
    # the counter-direction, in the same run: a wall that DOES parse still shows its keys
    _write_document(v1_state, "compliance_register.yaml", "obligations: []\nreviewed: 2026-07-01\n")
    readable = _wall_line(migrate.render(migrate.build_plan(v1_state), v1_state))
    assert "top-level keys: obligations, reviewed" in readable, readable


def test_a_wall_that_is_prose_is_not_reported_as_a_document_that_failed_to_parse(v1_state):
    """An alarm about a healthy shipped file is the same defect as silence about a broken one.

    Two of the three walls a kit ships are PROSE -- `product/masterplan.md` is the one every
    project's user fills in -- and the wall listing handed each of them to `yaml.safe_load`.
    Measured 2026-08-08 with the dev kit's own shipped masterplan template: `NOT READ: could not be
    read (ScannerError: while scanning a simple key ...)`, printed about a file that is exactly as
    it should be, in the section whose purpose is to tell a reader which files a gate blocks on.

    RED without `_is_yaml_document` in `render`: the prose wall's line carries `NOT READ` and a
    parser's exception class, and a reader is sent to repair a file with nothing wrong with it.
    """
    shipped = io.open(os.path.join(ROOT, "team-kits", "dev-team", "templates", "project_memory",
                                   "product", "masterplan.md"), encoding="utf-8").read()
    _write_document(v1_state, "product/masterplan.md", shipped)
    _install_wall_gate(v1_state, "product/masterplan.md")
    plan = migrate.build_plan(v1_state)
    assert "product/masterplan.md" in plan["gated_documents"], plan["gated_documents"]
    walls = _wall_lines(migrate.render(plan, v1_state))
    wall = next(line for line in walls if line.split()[0] == "product/masterplan.md")
    assert "NOT READ" not in wall, (
        "the dry run reports a shipped prose wall as a document that failed to parse: %r" % wall)
    assert "not a YAML document" in wall, wall
    # ...and the counter-direction in the same state: a wall that IS a YAML document and does not
    # parse still says so, so this is not a rule that stopped reading walls.
    _write_document(v1_state, "compliance_register.yaml", "obligations:\n  - {\n")
    _install_wall_gate(v1_state, "compliance_register.yaml", hook_name="gate_procs")
    walls = _wall_lines(migrate.render(migrate.build_plan(v1_state), v1_state))
    broken = [line for line in walls if line.startswith("compliance_register.yaml")]
    assert len(broken) == 1 and "NOT READ" in broken[0], walls


def test_doctor_says_why_it_cannot_name_the_kit_of_a_project_with_only_a_version(tmp_path):
    """BUG-0029: a migrated/V1 project carries a kit_version but no kit_state.json, so doctor cannot
    name the kit -- and a bare `unknown` beside a known version reads as a defect rather than a
    determinable gap. The kit NAME lives in `.claude/kit_state.json` (the scaffold writes it);
    `kit_version` is a date plus a content hash and carries no kit name, so doctor states the gap.

    RED without `kit_reason`: doctor reports `kit: unknown` with no reason, and a reader cannot tell a
    determinable gap from a determinable kit reported wrong.
    """
    report = report_module()
    state = _plain_state(tmp_path, "only_version")
    claude = os.path.join(os.path.dirname(state.root), ".claude")
    os.makedirs(claude)
    io.open(os.path.join(claude, "kit_version"), "w", encoding="utf-8", newline="\n").write(
        "version: 2026.07.18-3\ncontent: abc\n")
    result = report.doctor(state)
    assert result["kit"] == "unknown", result["kit"]
    assert result["kit_version"] == "2026.07.18-3", result["kit_version"]
    assert result["kit_reason"], "doctor names no reason the kit is unknown (BUG-0029)"
    assert "kit_state.json" in result["kit_reason"], result["kit_reason"]
    # ...AND ONCE THE KIT IS RECORDED THE REASON IS EMPTY, so this is not a constant that is always on
    io.open(os.path.join(claude, "kit_state.json"), "w", encoding="utf-8").write(
        '{"kit": "dev-team", "state": "active"}')
    named = report.doctor(state)
    assert named["kit"] == "dev-team", named["kit"]
    assert named["kit_reason"] == "", named["kit_reason"]


# -- the holes this round NAMES and does not close --------------------------------------------
#
# Each of these measures the harness AS IT STANDS, so each one goes red the day its hole is
# closed -- which is the intended reading: the entry in the hole list is then the thing that is
# out of date. Every one of them names its entry, and
# `test_every_hole_a_test_measures_is_carried_by_the_hole_list` is what keeps the pair together.


def _plain_state(tmp_path, name="held"):
    """An empty V2 state directory -- the shortest state a V1 document can be dropped into."""
    root = str(tmp_path / name / "project_memory")
    os.makedirs(root)
    return ProjectState(root)


def _write_document(state, name, text):
    path = os.path.join(state.root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(text)
    return path


def test_a_type_the_field_contract_knows_and_the_table_does_not_has_no_way_out(tmp_path, capsys):
    """The entry is `L13` in `docs/POST_V2_WISHLIST.md`.

    A type in `REQUIRED_FIELDS` with no row in spec II.10's mapping table is a HARNESS gap, and
    the dry run says so correctly. What it cannot do is offer a way through: the run refuses while
    the record stands, and `validate` reports the document holding it -- each pointing at the
    other. The types this can happen to are derived here rather than typed, so the day the table
    grows a row the set shrinks with it.
    """
    from kernel import report
    gap = sorted(set(REQUIRED_FIELDS) - set(migrate.v1_types()))
    assert gap, "every capturable type has a mapping-table row now -- L13 is closed"
    state = _plain_state(tmp_path)
    _write_document(state, "old_store.yaml",
                    "%s-0001:\n  status: ACTIVE\n  title: \"a record of a known type\"\n" % gap[0])
    assert _run(state, "migrate", "--dry-run") == 1
    printed = capsys.readouterr().out
    assert "HARNESS gap" in printed, printed
    assert "capture DEC" in printed, "the dry run's remedy is not the one this entry records"
    finding = [one for one in report.validate_state(state) if one["item"] == "old_store.yaml"]
    assert len(finding) == 1 and finding[0]["severity"] == "error", finding
    assert "migrate --dry-run" in finding[0]["remedy"], (
        "validate no longer sends the reader back to the dry run, so the circle is broken and "
        "L13 needs re-measuring")


def test_a_sub_mapping_of_a_record_collides_with_its_own_parent(tmp_path):
    """The entry is `L14` in `docs/POST_V2_WISHLIST.md`.

    `scan_document` counts the NAMES a mapping gives itself per object, and `build_plan` counts
    the CLAIMANTS of an id per key. A mapping nested inside a record that repeats the parent's id
    is a second object with one name each, so the two-names branch stays silent and the collision
    branch fires -- twice, over one V1 record, with a remedy that is about two different records.
    """
    state = _plain_state(tmp_path)
    _write_document(state, "procedures.yaml",
                    "processes:\n"
                    "  PROC-0001:\n"
                    "    title: \"file the post\"\n"
                    "    status: ACTIVE\n"
                    "    detail:\n"
                    "      id: PROC-0001\n"
                    "      status: ACTIVE\n")
    plan = migrate.build_plan(state)
    verdicts = [(entry["legacy_id"], entry["verdict"]) for entry in plan["records"]]
    assert verdicts == [("PROC-0001", "blocked"), ("PROC-0001", "blocked")], verdicts
    assert "appears 2 times in this run" in plan["records"][0]["reason"]
    assert not migrate.plan_is_executable(plan)


def test_a_hook_that_refuses_without_the_recognised_spelling_is_no_wall(v1_state):
    """The entry is `L15` in `docs/POST_V2_WISHLIST.md`.

    `layout._can_refuse` asks whether a module calls `<x>.block(...)` -- an ATTRIBUTE NAME, not the
    property of being able to refuse. A hook that ends the tool call another way reads its document
    unseen, so the document is not a wall, so a fully absorbed one is MOVED out from under it. The
    counter-direction is measured in the same test: the same hook with the recognised spelling
    makes the same document a wall.
    """
    from kernel import layout
    repo = os.path.dirname(v1_state.root)
    hooks = os.path.join(repo, ".claude", "hooks")
    os.makedirs(hooks, exist_ok=True)
    io.open(os.path.join(hooks, "gate_other.py"), "w", encoding="utf-8", newline="\n").write(
        "import os\n"
        "import sys\n"
        "HOOK = 'gate_other'\n"
        "def refuse(message):\n"
        "    sys.stderr.write(message)\n"
        "    sys.exit(2)\n"
        "def main():\n"
        "    path = os.path.join('project_memory', 'process_definitions.yaml')\n"
        "    if not os.path.exists(path):\n"
        "        refuse('the store this gate reads is gone')\n"
        "    return 0\n")
    io.open(os.path.join(repo, ".claude", "settings.json"), "w", encoding="utf-8",
            newline="\n").write(json.dumps({"hooks": {"PreToolUse": [
                {"matcher": "Bash", "hooks": [
                    {"type": "command", "command": "python .claude/hooks/gate_other.py"}]}]}}))
    walls = layout.gated_documents(repo, v1_state.root)
    assert "process_definitions.yaml" not in walls, (
        "the recogniser sees this refusal now, so L15 is closed and the entry is out of date")
    assert "process_definitions.yaml" in migrate.absorbed_documents(_planned(v1_state)), (
        "the document is held back for some other reason, so this measures nothing")
    # the counter-direction: the one spelling it does see
    _install_wall_gate(v1_state, "process_definitions.yaml", hook_name="gate_other")
    assert "process_definitions.yaml" in layout.gated_documents(repo, v1_state.root)


def test_a_wall_that_holds_v1_records_is_a_finding_no_run_can_clear(v1_state):
    """The entry is `L16` in `docs/POST_V2_WISHLIST.md`.

    A wall is never moved to `legacy/` (that is right: its gate would then read an absent file),
    and importing a record does not remove it from its V1 file. So a wall whose records are all
    imported keeps them, `validate` reports SR-0001 over it, and no further run changes anything --
    the second dry run has nothing left to do.
    """
    from kernel import report
    _install_wall_gate(v1_state, "process_definitions.yaml")
    assert _migrated(v1_state) == 0
    findings = [one for one in report.validate_state(v1_state)
                if one["item"] == "process_definitions.yaml"]
    assert len(findings) == 1 and findings[0]["severity"] == "error", findings
    again = _planned(v1_state)
    assert migrate.plan_is_executable(again) and not migrate._importable(again), (
        "a second run still has something to do, so this is not the standstill L16 records")
    assert [one for one in report.validate_state(v1_state)
            if one["item"] == "process_definitions.yaml"] == findings


def test_the_root_warning_is_silent_for_a_project_that_held_no_root_item_before(tmp_path, capsys):
    """The entry is `L18` in `docs/POST_V2_WISHLIST.md`.

    `root_item_warnings` speaks when a run ARCHIVES the last root item. A project that held none
    to begin with ends the run in the same state -- the setup-phase predicate answers no, and the
    gates built on it do not apply -- and hears nothing, because the warning is keyed to the
    change rather than to the state the run leaves behind.
    """
    state = _plain_state(tmp_path)
    _write_document(state, "procedures.yaml",
                    "processes:\n"
                    "  PROC-0001:\n"
                    "    title: \"file the post\"\n"
                    "    status: ACTIVE\n"
                    "    roles: [clerk]\n"
                    "    trigger: \"inbox\"\n"
                    "    steps: [\"file it\"]\n"
                    "    source: \"the V1 store\"\n")
    plan = migrate.build_plan(state)
    assert [entry["verdict"] for entry in plan["records"]] == ["translatable"]
    assert all(live == 0 for live, _archiving in plan["root_items_after"].values()), (
        plan["root_items_after"])
    assert migrate.root_item_warnings(plan) == [], (
        "the warning speaks for this project now, so L18 is closed")
    assert _run(state, "migrate", "--plan", migrate.plan_digest(plan)) == 0
    printed = capsys.readouterr().out
    assert "HOLDS NO ACTIVE" not in printed, printed


_HOLE_REFERENCE = re.compile(r"`(L\d+)` in `docs/POST_V2_WISHLIST\.md`")
_HOLE_SECTION_HEADING = "## 11. "
_HOLE_ENTRY = re.compile(r"^### (L\d+)\b")


def _hole_list_entries():
    """{L<n>: the lines of its entry} for the hole list's kit section."""
    path = os.path.join(ROOT, "docs", "POST_V2_WISHLIST.md")
    lines = io.open(path, encoding="utf-8").read().splitlines()
    start = next(index for index, line in enumerate(lines)
                 if line.startswith(_HOLE_SECTION_HEADING))
    end = next((index for index, line in enumerate(lines[start + 1:], start + 1)
                if line.startswith("## ")), len(lines))
    entries, current = {}, None
    for line in lines[start:end]:
        found = _HOLE_ENTRY.match(line)
        if found:
            current = found.group(1)
            entries[current] = []
        elif current:
            entries[current].append(line)
    return entries


def _tests_of_this_suite():
    """{module name: {test function names}} for every test module beside this one.

    DERIVED, and that is the correction of a reach this test claimed and did not have. It read ONE
    file, so an entry measured from `test_kernel.py` or `test_disposition.py` was in the list with
    nothing holding it, and a test there could name an entry that did not exist -- the same shape
    as the rule this round found one directory over (`L24`). What the pair is about is the
    MEASUREMENT and the entry, not which file the measurement happens to sit in.
    """
    found = {}
    here = os.path.dirname(os.path.abspath(__file__))
    for name in sorted(os.listdir(here)):
        if not (name.startswith("test_") and name.endswith(".py")):
            continue
        source = io.open(os.path.join(here, name), encoding="utf-8").read()
        found[name[: -len(".py")]] = (source, set(re.findall(r"^def (test_\w+)", source, re.M)))
    return found


def test_every_hole_a_test_measures_is_carried_by_the_hole_list():
    """A measured hole and the entry that records it are one thing, so neither may go alone.

    THE PAIRING IS WHAT MAKES BOTH ANSWERABLE. A tripwire without an entry is a measurement nobody
    reads; an entry without a tripwire is a claim that rots -- and this repo has had both. So a
    test that names an entry requires that entry to EXIST and to carry the two things the hole
    list's own rule asks for: a verdict, and -- unless it is closed -- what limits the damage
    instead.

    WHICH DIRECTIONS THIS REALLY CLOSES, and the paragraph that stood here said "BOTH" over a loop
    that runs across ONE of them. The loop is over the entries a TEST NAMES, so it catches a test
    that names an entry the list does not carry, a named entry without a verdict, and a citation
    pointing at a test no module of this suite defines. What it does NOT catch is an entry the list
    carries that no test names at all -- an orphan is green here. Measured 2026-08-08 in a clone:
    a missing entry is red, a dead citation is red, an orphaned entry is GREEN. That gap and its
    second one -- the reference is matched in one spelling, so an entry cited as "carried by `L19`"
    is not seen -- are the entry `L26` in `docs/POST_V2_WISHLIST.md`.

    ACROSS THE WHOLE SUITE, not across this file -- see `_tests_of_this_suite`.

    RED when an entry a test names is deleted or renamed, when a test names one without either
    half, and when a tripwire cited in the list is renamed without the list following.
    """
    entries = _hole_list_entries()
    suite = _tests_of_this_suite()
    named = sorted({one for source, _defined in suite.values()
                    for one in _HOLE_REFERENCE.findall(source)})
    assert named, "no test names a hole-list entry any more, so this pin measures nothing"
    for name in named:
        assert name in entries, (
            "%s is measured in this suite and the hole list carries no such entry" % name)
        body = "\n".join(entries[name])
        assert "**Urteil:" in body, "%s carries no verdict" % name
        if "GESCHLOSSEN" not in body:
            assert "**Was stattdessen begrenzt:" in body, (
                "%s is open and does not say what limits it instead" % name)
        cited = set(re.findall(r"`(test_\w+)\.(test_\w+)`", body))
        assert cited, "%s names no measurement in this suite" % name
        for module, test in sorted(cited):
            assert module in suite, "%s cites %s, which is no module of this suite" % (name, module)
            assert test in suite[module][1], (
                "%s cites %s.%s, which that module does not define" % (name, module, test))


_A_CITATION = re.compile(r"\A(?:([A-Za-z_]\w*)\.)?(test_\w+)\Z")


def _prose_of(path):
    """Every block of PROSE a shipped module carries -- its comments and its docstrings.

    Read as the parser reads them and not off the raw lines: a comment is a token, a docstring is a
    node. Consecutive comment lines are joined into one block because a name in backticks may be
    wrapped across them, and the join keeps no whitespace for the same reason.
    """
    source = io.open(path, encoding="utf-8").read()
    blocks, run, previous = [], [], None
    with io.open(path, encoding="utf-8") as handle:
        for token in tokenize.generate_tokens(handle.readline):
            if token.type != tokenize.COMMENT:
                continue
            if previous is not None and token.start[0] != previous + 1:
                blocks.append("".join(run))
                run = []
            run.append(token.string.lstrip("#"))
            previous = token.start[0]
    if run:
        blocks.append("".join(run))
    for node in ast.walk(ast.parse(source, path)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            written = ast.get_docstring(node, clean=False)
            if written:
                blocks.append(written)
    return blocks


def test_every_test_the_shipped_code_cites_by_name_is_a_test_that_exists():
    """A citation nothing resolves is a claim that rots, so every one of them is resolved.

    WHY THIS IS A DEFINITION AND NOT A FIX OF ONE WORD. `migrate.py` cited
    `test_the_deposit_a_remedy_names_...` while the test was named
    `test_the_deposit_an_instruction_names_...`: one word, in a comment that carries the whole
    argument for why a deposit is a file name and not a directory. Renaming that one word would have
    left every OTHER citation of the product resting on nothing -- and the assertion below reports
    how many there are rather than this sentence claiming a number. What a reader does with such a
    comment is look the test up, so the test is looked up here.

    WHAT COUNTS AS A CITATION IS THE PRODUCT'S OWN CONVENTION, read rather than guessed: a name in
    backticks, optionally with its module in front. A span that is only a module name resolves
    against the suite's file list and is not a citation of a test. Names wrapped across two lines of
    one comment or docstring are joined, which is why `_prose_of` reads tokens and nodes instead of
    lines.

    ITS DOMAIN IS WHAT THIS REPO SHIPS (`team-kits/`), which is where a rotten citation reaches a
    user. The suite's own citations are not in it, and the reason is not tidiness: `tools/test_hooks`
    carries a tombstone for a test that was deliberately removed, and an obituary is prose no rule
    should be able to tell from a citation.

    RED with the defect restored: the one-word mismatch above puts that name in the failure list.
    """
    suite = _tests_of_this_suite()
    defined = {name: module for module, (_source, names) in suite.items() for name in names}
    dangling, seen = [], 0
    for base, directories, files in os.walk(os.path.join(ROOT, "team-kits")):
        directories[:] = [one for one in directories if one != "__pycache__"]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            for block in _prose_of(path):
                for span in re.findall(r"`([^`]*)`", block, re.S):
                    token = "".join(span.split())
                    if token in suite:
                        continue
                    found = _A_CITATION.match(token)
                    if not found:
                        continue
                    seen += 1
                    module, test = found.group(1), found.group(2)
                    where = os.path.relpath(path, ROOT).replace(os.sep, "/")
                    if test not in defined:
                        dangling.append((where, token, "no test of this suite has that name"))
                    elif module in suite and defined[test] != module:
                        dangling.append(
                            (where, token, "that module does not define it; %s does" % defined[test]))
    assert not dangling, (
        "shipped code names tests that cannot be looked up, so the argument each of those comments "
        "carries rests on nothing: %s" % dangling)
    assert seen > 50, (
        "only %d citations were found in what this repo ships, so the collector above has "
        "collapsed and its silence measures nothing" % seen)
    assert len(defined) > seen, (
        "the suite defines %d tests and the product cites %d, which is not a corpus this rule can "
        "have resolved against" % (len(defined), seen))


# -- the goal-size vocabulary migration (DEC-0103) ---------------------------------------------

def _goal(state, title, klass):
    """A root goal, written past the vocabulary door the way a store from before DEC-0103 holds it."""
    item = state.capture("PR", {"title": title, "class": "normal", "problem": "p", "goal": "g",
                                "acceptance_criteria": [{"id": "AC-1", "text": "t"}],
                                "invariants": [], "out_of_scope": [], "priority": "high",
                                "user_story": "As the lead"})
    if klass != "normal":
        stored = state.active_path(item["id"])
        body = state._read_yaml(stored)
        body["class"] = klass
        state._write_yaml_atomic(stored, body)
    return item["id"]


def test_the_goal_class_plan_reads_every_stored_goal_and_writes_only_the_active_strays(tmp_path):
    """BUG-0237 / H155, DEC-0103's migration door: the before/after list, and what it refuses to
    touch.

    THREE ANSWERS IN ONE WALK, and each is a different decision: a word the vocabulary knows is
    left alone, a stray the caller maps is rewritten through the EDIT path (so the new value meets
    the same vocabulary check), and a stray nobody mapped is reported and left -- "nothing to do"
    and "I could not decide" must not read alike, which is why the command exits non-zero on the
    third.

    AND THE ARCHIVE IS READ, NOT WRITTEN: an archived record is a protocol of what happened
    (DEC-0004), and every reader that DECIDES from a class reads the ACTIVE item -- an order is
    leased against `state.read_item(root_id)`. RED when the plan marks archived rows writable:
    the archived goal below comes back rewritten.
    """
    state = _plain_state(tmp_path, "classes")
    known = _goal(state, "a known goal", "large")
    stray = _goal(state, "a stray goal", "feature")
    archived_stray = _goal(state, "an archived stray", "feature")
    state.transition(archived_stray, "SUPERSEDED")
    state.archive(archived_stray)

    plan = migrate.goal_class_plan(state, {})
    rows = {row["id"]: row for row in plan}
    assert set(rows) == {known, stray, archived_stray}, sorted(rows)
    assert rows[known]["target"] is None and rows[known]["current"] == "large"
    assert rows[archived_stray]["archived"] and rows[archived_stray]["target"] is None
    assert [row["id"] for row in migrate.unmapped_goal_classes(plan)] == [stray], (
        "the archived stray is not something this door could write")

    rendered = migrate.render_goal_class_plan(plan)
    for item_id in (known, stray, archived_stray):
        assert item_id in rendered, (item_id, rendered)
    assert "UNDECIDED" in rendered and stray in rendered.split("UNDECIDED")[1]

    mapped = migrate.goal_class_plan(state, {"feature": "small"})
    assert not migrate.unmapped_goal_classes(mapped)
    assert migrate.execute_goal_classes(state, mapped) == [(stray, "feature", "small")]
    assert state.read_item(stray)["class"] == "small"
    assert state.read_anywhere(archived_stray)[0]["class"] == "feature", (
        "the archive was rewritten by a door that says it only reads it")


def test_the_goal_class_door_refuses_a_mapping_the_vocabulary_does_not_know(tmp_path):
    """The migration writes through `update_item`, so its own target passes the closed vocabulary.

    A door that wrote the file itself would take `--map feature=feature-ish` and leave the store in
    exactly the shape the vocabulary was closed to prevent. RED with a direct file write.
    """
    state = _plain_state(tmp_path, "refused")
    stray = _goal(state, "a stray goal", "feature")
    plan = migrate.goal_class_plan(state, {"feature": "feature-ish"})
    with pytest.raises(Exception) as refusal:
        migrate.execute_goal_classes(state, plan)
    assert "unknown PR class" in str(refusal.value), str(refusal.value)
    assert state.read_item(stray)["class"] == "feature", "the refused rewrite landed anyway"


def test_an_imported_goal_keeps_the_class_its_v1_store_held(tmp_path):
    """DEC-0103 closes the goal-size vocabulary at the doors a ROLE writes through -- not at the
    importer.

    A V1 store had no vocabulary to have obeyed, and the import is a PROTOCOL of what it held
    (DEC-0004's argument, applied to the size). Measured when the vocabulary first bound every
    door: `test_a_binding_to_a_record_of_this_run_is_never_reported_as_free_text` turned the
    imported goal `blocked`, with a remedy (`--map PR.class=<field>`) that only exists where some
    V1 field happens to carry one of the four words -- so the import of every real V1 goal would
    have stopped.

    WHAT MAKES A BODY AN IMPORT is the record of where it came from (`LEGACY_FIELD`), not a flag a
    caller may set: the same property `capture_migrated_archive_preflight` demands before it writes
    outside the field contract. And the exemption is the SIZE alone -- `TSK.type` stays closed on
    every path, because it decides a gate.

    RED without the `imported` branch: the import blocks; RED if the branch widened to every closed
    field: the imported task type below would be taken.
    """
    state = _plain_state(tmp_path, "imported")
    body = {"title": "an imported goal", "class": "feature", "problem": "p", "goal": "g",
            "acceptance_criteria": [{"id": "AC-1", "text": "t"}], "invariants": [],
            "out_of_scope": [], "priority": "high", "user_story": "As the lead",
            migrate.LEGACY_FIELD: {"legacy_id": "PRD-0014b", "legacy_type": "PRD"}}
    goal = state.capture("PR", body, imported=True)
    assert state.read_item(goal["id"])["class"] == "feature"
    # ...and the SAME body through the ordinary door is refused twice over: the class, because the
    # exemption is the path and not the body, and the provenance field itself
    with pytest.raises(Exception, match="unknown PR class"):
        state.capture("PR", body)
    with pytest.raises(Exception, match="written by the import path alone"):
        state.capture("PR", dict(body, **{"class": "normal"}))

    # ...and the door that makes it a member afterwards is the one that exists for it
    plan = migrate.goal_class_plan(state, {"feature": "normal"})
    assert migrate.execute_goal_classes(state, plan) == [(goal["id"], "feature", "normal")]

    # ...while a gate input stays closed even for an import
    with pytest.raises(Exception, match="unknown TSK type"):
        state.capture("TSK", {
            "product_requirement": goal["id"], "derives_from": goal["id"],
            "type": "whatever-v1-called-it", "assigned_role": "backend-developer",
            "acceptance_refs": ["AC-1"], "required_inputs": [], "allowed_scope": ["src/"],
            "forbidden_scope": [], "root_revision": 1, "expected_outputs": ["src/x.py"],
            "dependencies": [],
            migrate.LEGACY_FIELD: {"legacy_id": "TSK-0017b", "legacy_type": "TSK"},
        }, imported=True)
