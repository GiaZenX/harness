"""Staging lifecycle + freeze operations (HARNESS_V2_SPEC.md II.4/II.6/II.6a) -- 1.6.

Specialists (and the orchestrator for small-WFRs) propose into
staging/<task_id>/ or staging/<ROOT-ID>/ -- non-canonical, never loaded at
session start. The KERNEL alone promotes:

- freeze_wireframe: on scope mint, staging WFR -> design/wireframes/
  WFR-nnnn.rNN.drawio.svg + schema-validated companion (diagram_hash,
  scope_apr_ref); the DSN derives from the frozen WFR (II.6a)
- freeze_architecture: staging ARC -> architecture/revisions/ + companion in
  architecture/active/ (II.6a; no own automaton -- state = location +
  approval_ref)
- freeze_design: staging DSN html -> design/revisions/ + manifest (file hash +
  root revision + timestamp), updates the root's design_refs (II.6)
- clear_staging: rejection ARCHIVES the whole directory (never silently deleted
  -- history-prune means archive). `mode="promoted"` EMPTIES it and no freeze
  calls it any more -- see `consume_staged_artifact` for the measured reason.

Fail-closed validation: .drawio.svg must parse as XML (well-formedness; a true
browser render check is phase-2 tooling -- the companions' `render_check: True`
currently attests EXACTLY that well-formedness, nothing more) and companions
must pass their schema.
Crash notes: a crash between the frozen copy and the staging clear leaves both
copies -- harmless (the canonical copy exists; a re-freeze produces rNN+1);
`python scripts/harness.py validate`/doctor surface leftovers.
Wiring note: WHO calls freeze at mint time is phase-2 hook/orchestrator logic;
the kernel provides the operations.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import time
import xml.etree.ElementTree as ET

from .backlog_types import (
    ACTIVE_DIRS,
    DECLARED_REQUIRED_FIELDS,
    ROOT_TYPE_BY_KIT,
    field_elements,
    parse_id,
)
from .lock import ext_path
from .schemas import validate
from .state import (
    STAGING_DIRNAME,
    ProjectState,
    StateError,
    _now_iso,
    names_a_drive,
    revision_name,
    split_revision,
)


class StagingError(StateError):
    """Staging/freeze operation refused -- message carries the remedy."""


# The ONE directory a `design_refs` entry can point into, named where the entry is PRODUCED.
# `freeze_design` (below) is the only function in the harness that appends to `design_refs`, and
# it appends a path under `ACTIVE_DIRS[DESIGN_REF_TYPE]` -- so the constant is what that function
# composes its own target from, and `dispatch` reads it rather than carrying a second copy.
#
# WFR IS NOT IN HERE, and the first cut of this was wider than any producer: `freeze_wireframe`
# writes a frozen wireframe but never touches `design_refs`, so no entry pointing into
# `design/wireframes/` is ever created -- accepting one would have been a rule about a shape
# nothing produces. Spec II.2 does say the scope manifest's design references include approved
# wireframes (II.6a), so the ABSENCE OF THAT PRODUCER is an open gap and not a decision taken
# here; the day `freeze_wireframe` appends, it appends through this constant and the resolver
# follows. ARC stays out for a different reason: an architecture revision is not a design
# reference (II.6 makes `design_ref` the binding IMPLEMENTATION reference for a UI task).
DESIGN_REF_TYPE = "DSN"


def frozen_design_dirs():
    """The state-relative directories a FROZEN design reference may point into."""
    return (ACTIVE_DIRS[DESIGN_REF_TYPE],)


def architecture_revisions_dir(state: ProjectState) -> str:
    """Where `freeze_architecture` lands a frozen ARC diagram.

    A builder rather than an inline join, for the reason `ProjectState.generated_path` is one:
    `kernel.layout` asks each writer where it writes, and this is the one canonical directory no
    other builder in the kernel composes -- it is under `architecture/` but beside, not inside,
    `ACTIVE_DIRS["ARC"]`.
    """
    return os.path.join(state.root, "architecture", "revisions")


# The tray a RENDERED report is filed into, and the field an item records it in.
#
# WHY THIS DIRECTORY HAS A KERNEL WRITER AT ALL (BUG-0085). The research kit assigns the rendered
# report to the report-writer (constitution §6), makes it a completeness condition (§17), ships the
# tray with its render templates -- and every route into it was refused: measured 2026-09-01 on a
# scaffolded project, `Write project_memory/reports/EXP-0002.tex` came back rc 2, while the same
# bytes under `staging/<task>/` were rc 0. `apply-proposal` cannot cover it by its own contract
# (both sides must parse as a YAML mapping, and it never creates a document), so the report was
# required and unwritable at once. This is the second half of the move the role can already do:
# it stages the render, and `freeze_report` files it.
#
# WHICH ITEM RECORDS THE REFERENCE is derived from the field contracts, not from a type: an item
# whose contract declares `evidence_refs` gets the filed path appended, which today is the `EXP`
# whose ANALYZED state the validator refuses without one (`report._check_experiment_reports`). A
# subject without the field -- the `RQ` a funding report is written for -- is filed all the same
# and the return says where the reference did NOT go, rather than the command implying a binding
# it did not write.
REPORTS_DIRNAME = "reports"
REPORT_REF_FIELD = "evidence_refs"


def reports_dir(state: ProjectState) -> str:
    """Where `freeze_report` lands a rendered report -- asked by `kernel.layout`, like the sibling
    above, so the tray is declared as kernel-written rather than left looking like a kit document
    with no writer."""
    return os.path.join(state.root, REPORTS_DIRNAME)


def contained_child(base: str, name: str, what: str) -> str:
    """`base/name`, refused unless `name` is ONE segment that really stays inside `base`.

    THE CHOKEPOINT FOR EVERY PATH A FREEZE COMPOSES FROM A CALLER'S STRING, and it exists because
    the day those strings became reachable from a command line they became a `shutil.rmtree` on any
    directory: every freeze then ended in `clear_staging(..., mode="promoted")`, which is
    `rmtree(<root>/staging/<key>)`, and `staging_dir` used to be a bare `os.path.join` -- so
    `{"staging_key": "../.."}` on stdin deleted the whole repository, and `".."` deleted the whole
    state directory. The body travels on STDIN, so no hook sees it: `gate_write_scope` reads command
    LINES, and all three of those command lines pass all eight registered shell gates.

    THE RECURSIVE DELETE IS GONE (BUG-0074) AND THIS GUARD IS NOT. A freeze now ends in
    `consume_staged_artifact`, an `os.remove` of ONE composed path, and it still opens the composed
    source, hashes it and COPIES it into canonical state -- so an escaping value still deletes a
    file nobody named and still pulls one in from anywhere on the disk. What changed is the blast
    radius of the delete half, not whether the composition is guarded.

    TWO CHECKS, AS DEFENCE IN DEPTH, and that wording is what the measurement supports rather than
    the stronger one this paragraph first carried ("neither alone is the answer"). The SEGMENT
    check refuses the text that names another place -- a separator, `.`, `..`, a drive letter
    (`ntpath.join("D:\\\\a", "C:x")` returns `C:x`, so an absolute second argument silently replaces
    the first on Windows). The REALPATH check refuses the link that goes somewhere else while
    spelling ONE segment; a junction needs no admin rights to create, and
    `gate_write_scope._repo_relative` resolves the target side for exactly this reason.

    WHAT THE TEST ACTUALLY DISTINGUISHES, so nobody reads the pair as two measured teeth: against
    the six escape shapes `test_no_freeze_parameter_can_reach_outside_the_state_root` feeds, EACH
    HALF ALONE catches all of them -- deleting the realpath check, the drive-letter clause, the
    `.`/`..` clause or the backslash normalisation each leaves that test GREEN. Only the whole
    guard going away turns it red. The junction is the one case that needs the realpath half and
    the escape list contains no such form; it was verified by hand and not pinned. That is the
    mechanism to fix, and the fix is a junction in the fixture -- a symlink guard without a test
    has rotted twice in this repo, and a docstring claiming two independent teeth would have been
    the third time.

    A LATENT EDGE, not exploitable today and written down before it becomes one: the containment
    check accepts `resolved == container`, so a name Windows normalises AWAY (`".."` with trailing
    spaces, `"..."`, `"   "`) passes the segment check and resolves to the container itself.

    THE SENTENCE THAT USED TO FOLLOW HERE HAS EXPIRED, and it is written down rather than quietly
    repaired: "every caller today appends a FILE NAME afterwards" was true until `submit-result
    --from` (BUG-0048) began OPENING the composed path directly. Measured 2026-08-17 for both
    normalised-away names on this host: `--from '...'` and `--from '.. '` reach `open()` on the
    staging DIRECTORY and stop there with a permission error (rc 2, nothing read, nothing written)
    — so the edge is still not exploitable, for a different reason than before. The condition
    under which it becomes one is unchanged and now has two ways in: a caller that hands this
    result to a DIRECTORY operation, or a host on which opening a directory succeeds. Either needs
    `resolved != container` here.

    `what` names the parameter in the refusal, because the role typed it.
    """
    text = str(name or "")
    normalised = text.replace("\\", "/")
    if (not normalised or "/" in normalised or normalised in (".", "..")
            or names_a_drive(text)):
        raise StagingError(
            "%s %r is not a single name inside %s -- refused. A staging key and a staged file name "
            "are NAMES, not paths: the kernel joins them onto the state directory and then empties "
            "what it promoted, so a value that walks out of that directory deletes or copies "
            "somewhere nobody asked for. Remedy: pass the bare name (e.g. `TSK-0007`, "
            "`preview.html`)." % (what, text, base))
    target = os.path.join(base, text)
    resolved = os.path.realpath(ext_path(target))
    container = os.path.realpath(ext_path(base))
    if resolved != container and not resolved.startswith(container + os.sep):
        raise StagingError(
            "%s %r resolves to %s, which is outside %s -- refused. A link may spell one name and "
            "lead anywhere. Remedy: remove the link, or stage the artefact in the real directory."
            % (what, text, resolved, container))
    return target


def staging_dir(state: ProjectState, key: str) -> str:
    return contained_child(state.staging_root(), key, "staging key")


def consume_staged_artifact(state: ProjectState, source: str) -> dict:
    """Take the ONE file a freeze has just copied into canonical state out of the staging area.

    THE DATA LOSS THIS EXISTS TO END (BUG-0074), measured 2026-08-29 in the user's real dev
    project: freezing one wireframe ran `clear_staging(..., mode="promoted")` on the task's staging
    directory, which is `shutil.rmtree`, and three UNFROZEN wireframes went with it. They came back
    only because an unrelated chore commit happened to carry them. `staging/<key>/` is the one
    tool-writable area under the state directory, so whatever lies there is by definition work no
    other route holds -- a freeze that treats the directory as consumed deletes work nobody
    promoted.

    So a freeze consumes exactly what it froze. The removed file is the source of a copy that has
    already landed in canonical state under a revision name, with its hash in the companion, so
    this is the second half of a MOVE and not a deletion of the only copy.

    IT NEVER RAISES, and that is the honest shape rather than laziness: at the moment it runs the
    frozen copy and its companion already exist, so a file the OS will not let go of (a lock, a
    permission) must not turn a completed freeze into a refusal that describes a state the project
    is not in -- the same reading `presets._after_a_failed_install` was corrected into. What it
    could not do it REPORTS: `consumed` is false and the caller prints what is still there.

    `remaining` is what the staging directory still holds afterwards, and the CLI prints it
    (`tools/test_staging_cli.py::test_freezing_one_artifact_leaves_the_other_staged_files_alone`).
    A directory is not removed when it falls empty: it is the task's workspace, not the freeze's.
    """
    directory = os.path.dirname(source)
    consumed = True
    try:
        os.remove(ext_path(source))
    except OSError:
        consumed = False
    try:
        remaining = sorted(os.listdir(ext_path(directory)))
    except OSError:
        remaining = []
    return {"consumed": consumed, "artifact": os.path.basename(source), "remaining": remaining}


def _file_hash(path: str) -> str:
    digest = hashlib.sha256()
    with open(ext_path(path), "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_xml_wellformed(path: str) -> None:
    try:
        ET.parse(ext_path(path))
    except ET.ParseError as exc:
        raise StagingError(
            "%s is not well-formed XML (%s) -- promotion blocked (fail-closed, "
            "spec II.6a). Remedy: fix the .drawio.svg in the draw.io extension "
            "and retry." % (os.path.basename(path), exc)
        ) from None
    except FileNotFoundError:
        raise StagingError(
            "staged file %s does not exist. Remedy: check the staging dir."
            % path
        ) from None


def _next_frozen_revision(target_dir: str, item_id: str) -> int:
    """Max-parse over EVERY file carrying this item's `.rNN` (frozen file AND
    companion/manifest, whatever the suffix): a manually deleted frozen revision must
    never cause an rNN number to be REUSED (Fable-Check 11/NIT-1).

    Through `state.split_revision`, the same reader `_frozen_revision_path` and
    `iter_active_items` use, so "which number has been used" and "which revision IS the
    item" cannot come apart -- and the names this module COMPOSES (`revision_name`) are
    read back by that same rule.
    """
    highest = 0
    if os.path.isdir(ext_path(target_dir)):
        for name in os.listdir(ext_path(target_dir)):
            found, revision, _suffix = split_revision(name)
            if found == item_id:
                highest = max(highest, revision)
    return highest + 1


def freeze_wireframe(
    state: ProjectState, staging_key: str, wfr_id: str, scope_apr_ref: str,
    derives_from: list, title: str,
) -> dict:
    """Freeze staging/<key>/<WFR-id>.drawio.svg into design/wireframes/ (II.6a)."""
    parse_id(wfr_id)
    source = os.path.join(staging_dir(state, staging_key), wfr_id + ".drawio.svg")
    with state.lock:
        _assert_xml_wellformed(source)
        target_dir = os.path.join(state.root, "design", "wireframes")
        revision = _next_frozen_revision(target_dir, wfr_id)
        frozen = os.path.join(target_dir, revision_name(wfr_id, revision, ".drawio.svg"))
        companion = {
            "id": wfr_id,
            "title": title,
            "derives_from": list(derives_from),
            "revision": revision,
            "diagram_hash": _file_hash(source),
            "render_check": True,
            "scope_apr_ref": scope_apr_ref,
        }
        validate(companion, "wfr_companion")
        os.makedirs(ext_path(target_dir), exist_ok=True)
        shutil.copyfile(ext_path(source), ext_path(frozen))
        state._write_yaml_atomic(
            os.path.join(target_dir, revision_name(wfr_id, revision, ".yaml")), companion
        )
        staged = consume_staged_artifact(state, source)
        state._regenerate_index_locked()
        return {"frozen": frozen, "companion": companion, "staging": staged}


def _root_of(state: ProjectState, derives_from) -> str:
    """The product root among `derives_from`, or None -- see `freeze_architecture` (BUG-0054).

    A type is a product root when `backlog_types.ROOT_TYPE_BY_KIT` names it, which is the ONE
    derivation the plan approval, the delivery verdict and the scaffold already share. The entry
    also has to EXIST in this store: a reference to an archived or foreign id is not a root this
    freeze may write to, and `_update_item_locked` would raise on it anyway.
    """
    roots = frozenset(ROOT_TYPE_BY_KIT.values())
    for entry in field_elements(derives_from):
        text = str(entry).strip()
        try:
            item_type, _number = parse_id(text)
        except Exception:  # noqa: BLE001 -- a malformed reference is not a root
            continue
        if item_type in roots and os.path.exists(ext_path(state.active_path(text))):
            return text
    return None


def freeze_architecture(
    state: ProjectState, staging_key: str, arc_id: str, title: str, scope: str,
    derives_from: list, approval_ref: str = None, assets: dict = None,
    packaging: dict = None,
) -> dict:
    """Freeze staging ARC into architecture/revisions/ + active companion (II.6a).

    `packaging` is the optional {method: ...} block the packaging gate reads. It is
    a PARAMETER rather than something the architect writes afterwards because this
    is the only path that creates an ARC item: `capture` refuses the type, and
    `project_memory/**` is kernel-only for tool writes. Without it the gate had a
    reader and no producer, which blocks every merge with no way out.

    AND IT POINTS THE ROOT'S `architecture_refs` AT THE FROZEN REVISION, which is the
    same move `freeze_design` makes for `design_refs` and for the same reason
    (BUG-0054). The delivery manifest HASHES `architecture_refs`
    (`approvals.item_subject_manifest`, kind `delivery`), so a re-frozen architecture
    is supposed to invalidate a delivery approval that was signed against the old
    one -- measured before this with a counter-probe that CAN fail: a second
    `freeze_architecture` left `assert_apr_in_force` saying STILL IN FORCE and the
    root revision at 1, while the same second `freeze_design` killed the approval,
    because that one writes its field and this one wrote only the companion. No hash
    is redefined here and no live approval dies for the change itself: the field
    merely gains the writer it never had.

    WHICH ITEM IS THE ROOT is derived, not passed: it is the entry of `derives_from`
    whose TYPE is a product root (`backlog_types.ROOT_TYPE_BY_KIT`, the same map the
    plan approval and the scaffold read), so a kit that gains a root type is covered
    without a second list here. `derives_from` naming no root leaves the field alone
    -- an ARC that hangs off nothing has no root to point.
    """
    parse_id(arc_id)
    source = os.path.join(staging_dir(state, staging_key), arc_id + ".drawio.svg")
    with state.lock:
        _assert_xml_wellformed(source)
        revisions_dir = architecture_revisions_dir(state)
        revision = _next_frozen_revision(revisions_dir, arc_id)
        frozen = os.path.join(revisions_dir, revision_name(arc_id, revision, ".drawio.svg"))
        companion = {
            "id": arc_id,
            "title": title,
            "scope": scope,
            "derives_from": list(derives_from),
            "revision": revision,
            "approval_ref": approval_ref,
            "diagram_hash": _file_hash(source),
            "assets": assets or {"mode": "self_contained"},
            "render_check": True,
        }
        if packaging is not None:
            # absent, not null: the schema is strict and `packaging` is optional,
            # so a `None` value would fail validation instead of meaning "not
            # stated here"
            companion["packaging"] = packaging
        validate(companion, "arc_companion")
        os.makedirs(ext_path(revisions_dir), exist_ok=True)
        shutil.copyfile(ext_path(source), ext_path(frozen))
        active_dir = os.path.join(state.root, "architecture", "active")
        os.makedirs(ext_path(active_dir), exist_ok=True)
        shutil.copyfile(ext_path(source), ext_path(os.path.join(active_dir, arc_id + ".drawio.svg")))
        state._write_yaml_atomic(os.path.join(active_dir, arc_id + ".yaml"), companion)
        staged = consume_staged_artifact(state, source)
        # Inside the SAME lock hold as everything above, for the reason `freeze_design`'s own
        # comment gives: the refs are computed from the fresh root read, so a parallel append
        # cannot be lost. `field_elements` and not `list()`, because this line writes what it
        # read and `list()` over a scalar is that scalar's letters (BUG-0038).
        updated_root = None
        root_id = _root_of(state, derives_from)
        if root_id is not None:
            root = state.read_item(root_id)
            refs = field_elements(root.get("architecture_refs"))
            refs.append(os.path.relpath(frozen, state.root).replace(os.sep, "/"))
            updated_root = state._update_item_locked(root_id, {"architecture_refs": refs})
        state._regenerate_index_locked()
        return {"frozen": frozen, "companion": companion, "staging": staged,
                "root": updated_root}


def freeze_design(
    state: ProjectState, staging_key: str, dsn_id: str, root_id: str, source_name: str,
) -> dict:
    """Freeze a self-contained HTML preview into design/revisions/ and point the
    root's design_refs at it (II.6). NOTE: updating design_refs is a hashed-field
    change -- on an approved root this invalidates the approval by design.
    Everything happens in ONE lock hold (Fable-Check 11/BUG-1): the refs are
    computed from the FRESH root read, so no parallel append is lost."""
    parse_id(dsn_id)
    # `source_name` is the ONLY freeze parameter that names a file rather than deriving it from an
    # id (`parse_id` bounds `wfr_id`/`arc_id` to `<TYP>-nnnn`, so those two compose nothing a caller
    # chose). It goes through the same chokepoint: an absolute value would have replaced the staging
    # directory outright under `os.path.join`, and the copy would have frozen any file on the disk
    # into `design/revisions/` and pointed the root's `design_refs` at it.
    source = contained_child(staging_dir(state, staging_key), source_name, "staged file name")
    with state.lock:
        if not os.path.exists(ext_path(source)) or os.path.getsize(ext_path(source)) == 0:
            raise StagingError(
                "staged design %s is missing or empty. Remedy: let the designer "
                "re-stage the self-contained preview." % source
            )
        root = state.read_item(root_id)
        # composed from the same constant the resolver reads, so "the directory a freezer writes
        # into" is one fact rather than a literal here and a tuple there
        revisions_dir = os.path.join(state.root, *ACTIVE_DIRS[DESIGN_REF_TYPE].split("/"))
        revision = _next_frozen_revision(revisions_dir, dsn_id)
        frozen = os.path.join(revisions_dir, revision_name(dsn_id, revision, ".html"))
        os.makedirs(ext_path(revisions_dir), exist_ok=True)
        shutil.copyfile(ext_path(source), ext_path(frozen))
        manifest = {
            "id": dsn_id,
            "revision": revision,
            "file_hash": _file_hash(frozen),
            "root": root_id,
            "root_revision": root.get("revision"),
            "frozen_at": _now_iso(),
        }
        # validated like the two companions, for the reason the manifest has a schema at all:
        # `root` is this item's parent binding, and `backlog_types.PARENT_FIELDS` derives the
        # reference graph from the declared contracts. An unvalidated dict would let the written
        # record and the declared contract drift, and the graph would walk the declaration.
        validate(manifest, "dsn_manifest")
        state._write_yaml_atomic(
            os.path.join(revisions_dir, revision_name(dsn_id, revision, ".yaml")), manifest
        )
        staged = consume_staged_artifact(state, source)
        # hashed design_refs change through the kernel edit path -- invalidates
        # an existing approval atomically (spec II.6a scope-manifest semantics)
        #
        # THROUGH `field_elements`, because this line WRITES what it read: `list()` over a scalar
        # is that scalar's letters, and `_update_item_locked` then put them in the canonical item
        # (BUG-0038). It is the one site of its class that damages the STATE instead of only
        # mis-answering a question, which is why the normalisation is here and not only in the
        # readers -- `backlog_types.REFERENCE_LIST_FIELDS` carries the class.
        # `test_staging_cli.test_a_scalar_design_ref_survives_the_freeze_as_one_reference`.
        refs = field_elements(root.get("design_refs"))
        refs.append("%s/%s" % (ACTIVE_DIRS[DESIGN_REF_TYPE],
                               revision_name(dsn_id, revision, ".html")))
        updated_root = state._update_item_locked(root_id, {"design_refs": refs})
        return {"frozen": frozen, "manifest": manifest, "root": updated_root, "staging": staged}


def freeze_report(
    state: ProjectState, staging_key: str, subject_id: str, source_name: str,
) -> dict:
    """File a rendered report out of a task's staging area into `reports/` -- see REPORTS_DIRNAME.

    THE NAME IS THE WRITER'S and is carried over unchanged, because it is read by something: the
    kit's `scripts/report_lint.py` discovers a report by its POSITION (a file lying directly in a
    directory called `reports`) and prints that name at every finding, and §17's own examples are
    per-experiment names. A revision suffix here would be a second naming convention for one file,
    with the lint, the constitution and this function each holding a copy.

    AN EXISTING REPORT IS NEVER OVERWRITTEN, and that is the one place this is stricter than its
    siblings: a frozen design gets the next revision number, so nothing it wrote can be lost. Here
    the name comes from the caller, so the same name twice would replace a delivered artifact --
    the class DEC-0056 keeps at maximum thoroughness (an irreversible change to the user's own
    material). The refusal names the standing file and leaves the staged bytes where they are.

    `tools/test_staging_cli.py::test_a_report_is_filed_by_the_kernel_and_never_overwrites_one`
    holds both halves; the end-to-end route is
    `tools/test_research_chain.py::test_a_rendered_report_reaches_the_tray_through_the_kernel`.
    """
    subject_type, _number = parse_id(subject_id)
    source = contained_child(staging_dir(state, staging_key), source_name, "staged file name")
    with state.lock:
        tray = reports_dir(state)
        if not os.path.isdir(ext_path(tray)):
            raise StagingError(
                "this project has no %s/ tray, so there is nowhere to file a report -- refused. "
                "The tray is shipped by the kit that renders reports; a project of another kit "
                "delivers its results as Evidence artefacts instead. Remedy: record the artefact "
                "as Evidence: `python scripts/harness.py evidence --kind "
                "<test|review|acceptance> --related <item-id> --result <pass|fail|blocked> "
                "--summary "
                "\"what it shows\" --artifact-ref <staged path>`."
                % REPORTS_DIRNAME)
        if not os.path.exists(ext_path(source)) or os.path.getsize(ext_path(source)) == 0:
            raise StagingError(
                "staged report %s is missing or empty. Remedy: let the report-writer render it "
                "into the task's staging directory first." % source)
        subject = state.read_item(subject_id)
        target = contained_child(tray, source_name, "staged file name")
        if os.path.exists(ext_path(target)):
            raise StagingError(
                "%s/%s already exists -- refused rather than replaced. A filed report is a "
                "delivered artefact, and this command would overwrite it with no second copy "
                "anywhere. Remedy: render under a name that says which run it is, or let the "
                "user retire the standing report first."
                % (REPORTS_DIRNAME, source_name))
        shutil.copyfile(ext_path(source), ext_path(target))
        filed = "%s/%s" % (REPORTS_DIRNAME, source_name)
        recorded = None
        if REPORT_REF_FIELD in DECLARED_REQUIRED_FIELDS.get(subject_type, ()):
            refs = field_elements(subject.get(REPORT_REF_FIELD))
            refs.append(filed)
            subject = state._update_item_locked(subject_id, {REPORT_REF_FIELD: refs})
            recorded = REPORT_REF_FIELD
        staged = consume_staged_artifact(state, source)
        return {"frozen": target, "filed": filed, "file_hash": _file_hash(target),
                "subject": subject, "recorded_on": recorded, "staging": staged}


def clear_staging(state: ProjectState, key: str, mode: str, _locked: bool = False) -> str:
    """promoted -> EMPTY the dir; rejected -> ARCHIVE it (never silent delete).

    NO FREEZE CALLS THE `promoted` HALF ANY MORE (BUG-0074): a freeze consumes the artifact it
    froze (`consume_staged_artifact`) and leaves the rest of the task's workspace alone. The mode
    stays because emptying a promoted proposal area is a lifecycle step spec II.4 names -- what it
    may not be is the tail of an operation about ONE file. A caller that wants it is asking for the
    whole directory to go, and what keeps a freeze from becoming such a caller again is
    `test_no_freeze_command_empties_the_tasks_staging_area` in `tools/test_staging_cli.py` -- named
    on ONE line, because a test name broken across two is one nobody can copy or resolve.
    """
    if mode not in ("promoted", "rejected"):
        raise StagingError("mode must be promoted|rejected, got %r" % mode)
    if not _locked:
        with state.lock:
            return clear_staging(state, key, mode, _locked=True)
    source = staging_dir(state, key)
    if not os.path.isdir(ext_path(source)):
        return source
    if mode == "rejected":
        year = time.strftime("%Y")
        target = os.path.join(state.archive_root(), STAGING_DIRNAME, year, key)
        os.makedirs(ext_path(os.path.dirname(target)), exist_ok=True)
        if os.path.isdir(ext_path(target)):
            raise StagingError(
                "archive target %s already exists -- refusing to overwrite. "
                "Remedy: inspect and merge manually." % target
            )
        shutil.move(ext_path(source), ext_path(target))
        return target
    shutil.rmtree(ext_path(source))
    return source
