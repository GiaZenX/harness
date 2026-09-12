"""Tests for staging/freeze operations + the harness CLI (spec II.4/II.6a, step 1.6)."""
import io
import json
import os
import subprocess
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "team-kits"))

from conftest import approve  # noqa: E402 -- the ONE minting helper for the suite
from conftest import satisfy_the_architect_step  # noqa: E402 -- the dispatch duty
from kernel import approvals, cli, dispatch, report, staging  # noqa: E402
from conftest import walk_to_status  # noqa: E402
from kernel.backlog_types import ACTIVE_DIRS, TransitionError  # noqa: E402
from kernel.schemas import SchemaError  # noqa: E402
from kernel.staging import StagingError  # noqa: E402
from kernel.state import ProjectState, StateError  # noqa: E402


PR_FIELDS = {
    "title": "Checkout flow",
    "class": "normal",
    "problem": "no checkout",
    "goal": "working checkout",
    "acceptance_criteria": [{"id": "AC-1", "text": "order completes"}],
    "invariants": [],
    "out_of_scope": [],
    "priority": "high",
    "user_story": "As a buyer I can pay",
}

DRAWIO_SVG = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" content="&lt;mxfile&gt;&lt;/mxfile&gt;">'
    "<rect width='10' height='10'/></svg>\n"
)


@pytest.fixture
def state(tmp_path):
    root = tmp_path / "project_memory"
    root.mkdir()
    return ProjectState(str(root))


def stage_file(state, key, name, content=DRAWIO_SVG):
    directory = staging.staging_dir(state, key)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


# -- wireframe freeze ----------------------------------------------------------

def test_freeze_wireframe_happy_path(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    stage_file(state, pr["id"], "WFR-0001.drawio.svg")
    result = staging.freeze_wireframe(
        state, pr["id"], "WFR-0001", scope_apr_ref="APR-0001",
        derives_from=[pr["id"]], title="Checkout layout",
    )
    assert result["frozen"].endswith(os.path.join("design", "wireframes", "WFR-0001.r01.drawio.svg"))
    assert os.path.exists(result["frozen"])
    companion = yaml.safe_load(open(result["frozen"][:-len(".drawio.svg")] + ".yaml", encoding="utf-8"))
    assert companion["scope_apr_ref"] == "APR-0001"
    assert len(companion["diagram_hash"]) == 64
    # THE ARTIFACT is consumed on promotion, the WORKSPACE is not (BUG-0074). This line used to
    # assert the directory was gone -- the contract that deleted three unfrozen wireframes in the
    # user's real project -- and `test_freezing_one_artifact_leaves_the_other_staged_files_alone`
    # is what measures the difference over all three freeze commands.
    assert os.path.isdir(staging.staging_dir(state, pr["id"]))
    assert result["staging"]["consumed"] and not result["staging"]["remaining"]


def test_freeze_second_revision_gets_r02(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    for expected in ("r01", "r02"):
        stage_file(state, pr["id"], "WFR-0001.drawio.svg")
        result = staging.freeze_wireframe(
            state, pr["id"], "WFR-0001", "APR-0001", [pr["id"]], "layout"
        )
        assert expected in result["frozen"]


def test_malformed_xml_blocks_promotion(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    stage_file(state, pr["id"], "WFR-0001.drawio.svg", content="<svg><unclosed>")
    with pytest.raises(StagingError, match="well-formed XML"):
        staging.freeze_wireframe(state, pr["id"], "WFR-0001", "APR-0001", [pr["id"]], "t")
    # staging untouched on failure
    assert os.path.isdir(staging.staging_dir(state, pr["id"]))


# -- architecture freeze -------------------------------------------------------

def test_freeze_architecture_writes_active_and_revision(state):
    stage_file(state, "TSK-0001", "ARC-0001.drawio.svg")
    result = staging.freeze_architecture(
        state, "TSK-0001", "ARC-0001", title="System overview", scope="whole-system",
        derives_from=["PR-0001"],
    )
    assert os.path.exists(result["frozen"])
    active = os.path.join(state.root, "architecture", "active")
    assert os.path.exists(os.path.join(active, "ARC-0001.drawio.svg"))
    companion = yaml.safe_load(open(os.path.join(active, "ARC-0001.yaml"), encoding="utf-8"))
    assert companion["assets"] == {"mode": "self_contained"}
    assert companion["approval_ref"] is None  # empty until frozen via delivery


def test_freezing_the_architecture_again_devalues_the_delivery_approval(state):
    """BUG-0054: `architecture_refs` is HASHED into the delivery manifest and had no producer, so
    a second `freeze_architecture` left the approval saying STILL IN FORCE and the root revision
    at 1 -- the field the user signed against could not move, because nothing ever wrote it.

    THE COUNTER-PROBE IS IN THE SAME TEST and it is what makes the first half mean anything: the
    design freeze, whose field DOES have a writer, kills the approval in the same repository and
    in the same breath. Without it "in force" and "not in force" could both be explained by a
    fixture that never had a live approval at all.

    The frozen revision is read out of the freeze's own answer rather than composed here: what the
    field must point at is the file that was just written, and a path typed a second time is the
    drift `freeze_design`'s comment about composing from one constant is about.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    stage_file(state, pr["id"], "ARC-0001.drawio.svg")
    first = staging.freeze_architecture(
        state, pr["id"], "ARC-0001", title="System overview", scope="whole-system",
        derives_from=[pr["id"]])
    expected = os.path.relpath(first["frozen"], state.root).replace(os.sep, "/")
    assert first["root"]["architecture_refs"] == [expected], first["root"]

    # signed AFTER the first freeze, which is the only order in which the question is the one the
    # item asks: what the user puts a name to is the architecture that stands.
    approve(state, pr["id"], kind="delivery")
    apr = approvals.read_apr(state, state.read_item(pr["id"])["approval_ref"])
    approvals.assert_apr_in_force(state, apr, state.read_item(pr["id"]))   # the control

    stage_file(state, pr["id"], "ARC-0001.drawio.svg")
    staging.freeze_architecture(
        state, pr["id"], "ARC-0001", title="System overview", scope="whole-system",
        derives_from=[pr["id"]])
    with pytest.raises(approvals.ApprovalError):
        approvals.assert_apr_in_force(state, apr, state.read_item(pr["id"]))


def test_an_architecture_that_hangs_off_no_root_writes_no_refs(state):
    """The other direction of the derivation: `derives_from` naming no product root leaves the
    field alone rather than guessing at one (BUG-0054).

    `SR-0001` is an id the companion schema accepts and whose TYPE is not a product root, so this
    measures the root-type question and not "the reference was unreadable".
    """
    stage_file(state, "TSK-0001", "ARC-0002.drawio.svg")
    result = staging.freeze_architecture(
        state, "TSK-0001", "ARC-0002", title="System overview", scope="whole-system",
        derives_from=["SR-0001"])
    assert result["root"] is None, result["root"]


# -- design freeze -------------------------------------------------------------

def test_freeze_design_updates_design_refs_and_invalidation_semantics(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    stage_file(state, pr["id"], "preview.html", content="<html><body>design</body></html>")
    result = staging.freeze_design(state, pr["id"], "DSN-0001", pr["id"], "preview.html")
    assert os.path.exists(result["frozen"])
    assert result["root"]["design_refs"] == ["design/revisions/DSN-0001.r01.html"]
    # design_refs is a HASHED field: on an approved root this goes through
    # update_item and would invalidate -- here the root was DRAFT, revision stays
    assert result["root"]["revision"] == 1


def test_freeze_design_empty_file_blocks(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    stage_file(state, pr["id"], "preview.html", content="")
    with pytest.raises(StagingError, match="missing or empty"):
        staging.freeze_design(state, pr["id"], "DSN-0001", pr["id"], "preview.html")


def test_freeze_design_refuses_a_manifest_that_contradicts_the_declared_contract(state):
    """The manifest is VALIDATED before it is written, and this is the guard, not its consequence.

    `dsn_manifest.yaml` says `root` is a `PR|RQ` id, and that declaration is a source
    `backlog_types.PARENT_FIELDS` derives the reference graph from -- so the graph walks
    `DSN.root` believing it names a root. A manifest written past the schema would make the
    stored record say something else while every reader still follows the declaration.

    Measured with the validate call deleted: the whole kernel suite stayed green, and only a
    SECOND mutation (writing a wrong key as well) turned a test red. A guard whose removal costs
    nothing is not tested, so this drives the guard directly: `root_id` is a caller-supplied
    parameter that nothing else in `freeze_design` type-checks.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    task = state.capture("TSK", {
        "product_requirement": pr["id"], "root_revision": 1, "derives_from": [pr["id"]],
        "type": "implementation", "assigned_role": "backend-developer",
        "acceptance_refs": ["AC-1"],
        "required_inputs": [], "allowed_scope": ["src/"], "forbidden_scope": [],
        "expected_outputs": ["code"], "dependencies": []})
    stage_file(state, "design", "preview.html", content="<html><body>x</body></html>")
    with pytest.raises(SchemaError, match="root"):
        staging.freeze_design(state, "design", "DSN-0001", task["id"], "preview.html")
    assert not os.path.exists(
        os.path.join(state.root, "design", "revisions", "DSN-0001.r01.yaml")), (
        "the manifest was written despite failing its own schema")


def test_frozen_design_manifest_validates_against_its_schema(state):
    """The written record, read back off disk and held to the contract the graph derives from."""
    from kernel.schemas import validate
    pr = state.capture("PR", dict(PR_FIELDS))
    stage_file(state, "design", "preview.html", content="<html><body>x</body></html>")
    staging.freeze_design(state, "design", "DSN-0001", pr["id"], "preview.html")
    path = os.path.join(state.root, "design", "revisions", "DSN-0001.r01.yaml")
    validate(yaml.safe_load(open(path, encoding="utf-8")), "dsn_manifest")


def test_freeze_design_preserves_existing_refs(state):
    """Fable-Check 11/BUG-1: refs computed from the FRESH root -- no lost update."""
    pr = state.capture("PR", dict(PR_FIELDS))
    state.update_item(pr["id"], {"design_refs": ["design/revisions/DSN-0000.r01.html"]})
    stage_file(state, pr["id"], "preview.html", content="<html>x</html>")
    result = staging.freeze_design(state, pr["id"], "DSN-0001", pr["id"], "preview.html")
    assert result["root"]["design_refs"] == [
        "design/revisions/DSN-0000.r01.html",
        "design/revisions/DSN-0001.r01.html",
    ]


def test_frozen_revision_numbers_never_reused(state):
    """Fable-Check 11/NIT-1: max-parse -- deleting r01 must not recycle its number."""
    pr = state.capture("PR", dict(PR_FIELDS))
    stage_file(state, pr["id"], "WFR-0001.drawio.svg")
    first = staging.freeze_wireframe(state, pr["id"], "WFR-0001", "APR-0001", [pr["id"]], "t")
    os.remove(first["frozen"])  # simulate manual out-of-band deletion
    stage_file(state, pr["id"], "WFR-0001.drawio.svg")
    second = staging.freeze_wireframe(state, pr["id"], "WFR-0001", "APR-0001", [pr["id"]], "t")
    assert ".r02." in second["frozen"]


# -- report freeze (BUG-0085) --------------------------------------------------

RQ_FIELDS = {"title": "Chunk size", "class": "normal", "question": "does it help?",
             "motivation": "rework costs", "out_of_scope": [], "priority": "high",
             "acceptance_criteria": [{"id": "AC-1", "text": "error rate with interval"}]}


def _research_subject(state):
    """An RQ with an EXP under it, plus the tray the research kit ships."""
    state.capture("RQ", dict(RQ_FIELDS))
    state.capture("HYP", {"derives_from": "RQ-0001", "statement": "s",
                          "testable_prediction": "p"})
    state.capture("EXP", {"derives_from": "HYP-0001", "design": "d", "variables": ["v"],
                          "success_criteria": [{"id": "SC-1", "text": "s"}], "evidence_refs": []})
    os.makedirs(os.path.join(state.root, staging.REPORTS_DIRNAME), exist_ok=True)


def test_a_report_is_filed_by_the_kernel_and_never_overwrites_one(state):
    """BUG-0085: the rendered report had no write route at all, and now has exactly one.

    Measured on a scaffolded research project 2026-09-01: `Write project_memory/reports/EXP-0002
    .tex` came back rc 2 while the same bytes under `staging/<task>/` were rc 0, so §6's owner
    could render a report and never file it, and §17 made that report a completeness condition.

    Three properties in one place because they are one operation: the bytes land in the tray, the
    subject records them where its own contract has a field for it, and a second file of the same
    name is REFUSED -- a filed report is delivered material, and this is the class DEC-0056 keeps
    at maximum thoroughness. The refusal leaves the staged bytes where they were, which is what
    makes it a refusal rather than a loss.
    """
    _research_subject(state)
    stage_file(state, "TSK-0001", "EXP-0001.tex", content="Der Arm zeigt 5 Punkte.")
    filed = staging.freeze_report(state, "TSK-0001", "EXP-0001", "EXP-0001.tex")

    assert filed["filed"] == "reports/EXP-0001.tex"
    with open(os.path.join(state.root, "reports", "EXP-0001.tex"), encoding="utf-8") as handle:
        assert handle.read() == "Der Arm zeigt 5 Punkte."
    assert state.read_item("EXP-0001")["evidence_refs"] == ["reports/EXP-0001.tex"]
    assert filed["recorded_on"] == "evidence_refs"
    assert not os.path.exists(os.path.join(staging.staging_dir(state, "TSK-0001"),
                                           "EXP-0001.tex")), "the staged copy was not consumed"

    stage_file(state, "TSK-0001", "EXP-0001.tex", content="ein zweiter Lauf")
    with pytest.raises(StagingError) as exc:
        staging.freeze_report(state, "TSK-0001", "EXP-0001", "EXP-0001.tex")
    assert "already exists" in str(exc.value), exc.value
    with open(os.path.join(state.root, "reports", "EXP-0001.tex"), encoding="utf-8") as handle:
        assert handle.read() == "Der Arm zeigt 5 Punkte.", "the standing report was replaced"
    assert os.path.exists(os.path.join(staging.staging_dir(state, "TSK-0001"), "EXP-0001.tex")), (
        "the refusal consumed the staged bytes it refused to file")


def test_a_report_for_a_subject_without_the_field_is_filed_and_says_so(state):
    """The funding report §17 names is written for the QUESTION, and an RQ has no `evidence_refs`.

    Which item can RECORD the reference is read off the field contracts
    (`backlog_types.DECLARED_REQUIRED_FIELDS`), so this needs no type list -- and the command must
    not imply a binding it did not write, which is why `recorded_on` is None here and the CLI
    prints that in words rather than an empty list that reads like an empty field.
    """
    _research_subject(state)
    stage_file(state, "TSK-0001", "fzulg_application_RQ-0001.md", content="# Antrag")
    filed = staging.freeze_report(state, "TSK-0001", "RQ-0001", "fzulg_application_RQ-0001.md")
    assert filed["recorded_on"] is None
    assert os.path.isfile(os.path.join(state.root, "reports",
                                       "fzulg_application_RQ-0001.md"))
    assert "evidence_refs" not in state.read_item("RQ-0001")


def test_a_project_whose_kit_ships_no_reports_tray_is_refused_rather_than_given_one(state):
    """The tray is a KIT decision: the research kit ships it with its render templates, and a dev
    project has none. Creating one here would file a report where nothing in that project reads it
    -- `scripts/report_lint.py` is shipped by the research kit alone -- so the refusal names the
    route a project without the tray does have."""
    state.capture("PR", dict(PR_FIELDS))
    stage_file(state, "TSK-0001", "result.md", content="# result")
    with pytest.raises(StagingError) as exc:
        staging.freeze_report(state, "TSK-0001", "PR-0001", "result.md")
    assert "no reports/ tray" in str(exc.value) and "evidence" in str(exc.value), exc.value


# -- rejection path ------------------------------------------------------------

def test_rejected_staging_is_archived_never_deleted(state):
    stage_file(state, "TSK-0007", "ARC-0002.drawio.svg")
    target = staging.clear_staging(state, "TSK-0007", mode="rejected")
    assert os.path.isdir(target)
    assert "archive" in target and "staging" in target
    assert os.path.exists(os.path.join(target, "ARC-0002.drawio.svg"))
    assert not os.path.isdir(staging.staging_dir(state, "TSK-0007"))


# -- CLI -----------------------------------------------------------------------

def run_cli(state, *argv):
    return cli.main(["--root", state.root, *argv])


def test_cli_validate_exit_codes(state, capsys):
    state.capture("PR", dict(PR_FIELDS))
    assert run_cli(state, "validate") == 0
    state.capture("INV", {"scope": "s", "source": "PR-0001",
                          "check": {"kind": "test", "ref": "t"}})  # text/value missing
    assert run_cli(state, "validate") == 1
    assert "text|value" in capsys.readouterr().out


def test_cli_transition_and_archive(state, capsys):
    pr = state.capture("PR", dict(PR_FIELDS))
    assert run_cli(state, "transition", pr["id"], "REJECTED") == 0
    assert run_cli(state, "archive", pr["id"]) == 0
    out = capsys.readouterr().out
    assert "REJECTED" in out and "archive" in out


def test_cli_illegal_transition_exits_1(state, capsys):
    pr = state.capture("PR", dict(PR_FIELDS))
    assert run_cli(state, "transition", pr["id"], "ACCEPTED") == 1
    assert "illegal transition" in capsys.readouterr().err


def test_cli_doctor_and_index(state, capsys):
    state.capture("PR", dict(PR_FIELDS))
    assert run_cli(state, "doctor") == 0
    assert '"state_version"' in capsys.readouterr().out
    assert run_cli(state, "generate-index") == 0


def test_cli_session_brief(state, capsys):
    state.capture("PR", dict(PR_FIELDS))
    assert run_cli(state, "generate-session-brief", "--kit", "dev-team",
                   "--kit-version", "rc1", "--enforcement", "audited") == 0
    assert "session_brief.yaml" in capsys.readouterr().out


# -- evidence: the producer the merge gate reads (spec II.2 Evidence) -----------

def test_cli_evidence_captures_a_typed_item_the_merge_gate_can_read(state, capsys):
    """The one command that turns a QA verdict into canonical state.

    Everything the gate needs is asserted on the ITEM, not on the printed line: the store it
    lands in comes from `ACTIVE_DIRS["EVD"]`, the verdict from `--result`, and the binding from
    `--related`. Evidence carries no project status (II.2), so its absence is asserted too --
    a status would put it on an automaton it has no place on.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    assert run_cli(state, "evidence", "--kind", "test", "--result", "pass",
                   "--related", pr["id"], "--summary", "full suite green",
                   "--artifact-ref", "staging/TSK-0001/coverage.html", "--run-command", "pytest -q", "--run-scope", "selection") == 0
    out = capsys.readouterr().out
    assert "EVD-0001" in out and "pass" in out
    path = os.path.join(state.root, *ACTIVE_DIRS["EVD"].split("/"), "EVD-0001.yaml")
    with open(path, encoding="utf-8") as handle:
        item = yaml.safe_load(handle)
    assert item["kind"] == "test" and item["result"] == "pass"
    assert item["related"] == [pr["id"]]
    assert item["artifact_refs"] == ["staging/TSK-0001/coverage.html"]
    assert "status" not in item


def test_capture_names_the_neighbours_it_found_and_captures_the_item_anyway(state, capsys):
    """FR-0018 at the surface: a HINT, on the one occasion a machine can give one for free.

    Three properties, and every one of them is a way this could have become the hard block the FR
    forbids: the exit code is 0, the id is on stdout where a caller parses it, and the neighbours
    are on stderr. The fourth is that the new item does not match itself -- the comparison runs
    before the capture, so a hint naming the id that was just minted is impossible rather than
    filtered.
    """
    # AS LONG AS A REAL REQUIREMENT: below `report.DUPLICATE_HINT_MIN_WORDS` the hint says
    # nothing at all, and a fixture under that floor would measure the floor instead of the route.
    rich = dict(PR_FIELDS,
                problem=("Kundinnen brechen den Bezahlvorgang ab, weil sie ihre Kartendaten bei "
                         "jeder Bestellung neu eintippen muessen; die Abbruchquote steigt vor "
                         "allem auf dem Telefon, wo das Formular ueber mehrere Bildschirme "
                         "laeuft."),
                goal=("Ein einmal bestaetigtes Zahlungsmittel steht bei der naechsten Bestellung "
                      "bereit, sodass der Bezahlvorgang aus einer Bestaetigung besteht und nicht "
                      "aus einem Formular."),
                out_of_scope=["Rechnungskauf", "Ratenzahlung", "Gutscheine"],
                user_story=("Als wiederkehrende Kundin moechte ich mit einem gespeicherten "
                            "Zahlungsmittel bezahlen, damit die Bestellung nicht an der Tastatur "
                            "haengt."))
    state.capture("PR", dict(rich))
    again = dict(rich, title="Checkout flow, second attempt")
    assert run_cli_with_body(state, json.dumps(again), "capture", "PR") == 0
    out = capsys.readouterr()
    assert out.out.startswith("PR-0002 "), out.out
    listed = [line for line in out.err.splitlines() if line.startswith("[similar] ")
              and ": " in line]
    assert listed == ["[similar] PR-0001: Checkout flow"], out.err
    assert "PR-0002" in out.err and "nothing here was refused" in out.err

    # ...and an item that resembles nothing says nothing at all
    other = dict(
        rich, title="Warehouse restocking",
        problem=("Ware geht aus, ohne dass jemand es merkt: der Bestand wird von Hand gezaehlt "
                 "und die Nachbestellung faellt aus, wenn der Zaehltag auf einen Feiertag faellt."),
        goal=("Der Bestand loest die Nachbestellung selbst aus, sobald er unter die Menge faellt, "
              "die eine Woche Verkauf deckt."),
        out_of_scope=["Lieferantenwechsel", "Preisverhandlung"],
        user_story=("Als Inhaber moechte ich, dass nachbestellt wird, bevor das Regal leer ist, "
                    "damit kein Verkauf ausfaellt."),
        acceptance_criteria=[{"id": "AC-1", "text": "Nachbestellung wird ausgeloest"}])
    assert run_cli_with_body(state, json.dumps(other), "capture", "PR") == 0
    assert "[similar]" not in capsys.readouterr().err


def test_verify_invariants_records_what_the_check_resolves_to_and_exits_on_the_gap(
        tmp_path, capsys):
    """FR-0039 at the surface: the producer takes no status, only which invariants to re-measure.

    The exit code is the same convention `validate` uses -- 1 means there is something to fix --
    and it rests on the same condition the merge blocker reads, so a role running this and a gate
    reading the store cannot disagree.
    """
    root = tmp_path / "project_memory"
    root.mkdir()
    st = ProjectState(str(root))
    assert run_cli(st, "verify-invariants") == 0
    assert "no active invariants" in capsys.readouterr().out

    inv = st.capture("INV", {"scope": "compounder/", "source": "PR-0001", "text": "pure",
                             "check": {"kind": "test", "ref": "tests/test_rules.py::test_pure"}})
    assert run_cli(st, "verify-invariants") == 1
    printed = capsys.readouterr().out
    assert inv["id"] in printed and "unverified" in printed

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_rules.py").write_text("def test_pure():\n    pass\n",
                                                      encoding="utf-8")
    assert run_cli(st, "verify-invariants", inv["id"]) == 0
    assert "verified" in capsys.readouterr().out
    assert st.read_item(inv["id"])["status"] == "verified"

    # ...and an invariant this kernel cannot READ is neither met nor unmet: it gets its own line
    # and does NOT set the exit code. Measured before it did: an undecidable check made this
    # command exit 1 while `validate` exited 0 with a warning, on the same store in the same
    # second -- so the comment claiming the two "cannot disagree" was false where it mattered,
    # and a project whose tests are not Python got a permanent non-zero from the command its own
    # role text sends it to (H110).
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "rules.spec.js").write_text("test('is pure', () => {});\n",
                                                    encoding="utf-8")
    other = st.capture("INV", {"scope": "web/", "source": "PR-0001", "text": "pure",
                               "check": {"kind": "test", "ref": "web/rules.spec.js::is pure"}})
    assert run_cli(st, "verify-invariants") == 0
    printed = capsys.readouterr().out
    assert "%s undecided" % other["id"] in printed, printed
    assert "could not be decided" in printed and "H110" in printed, printed
    assert run_cli(st, "validate") == 0


def test_capture_shows_the_outline_when_a_body_invents_a_new_level(state, capsys):
    """FR-0017's protection, at the moment the FR's own rule is about.

    "A new heading only when a requirement really fits none of the existing ones" is a judgement
    no machine makes; what a machine can do is put the outline in front of the writer at the
    moment they invent a level. So the hint fires on a level nobody uses yet and stays silent on
    one that exists -- the second half is what keeps it from being noise on every capture.
    """
    state.capture("PR", dict(PR_FIELDS, area="Frontend/Checkout"))
    body = dict(PR_FIELDS, title="Refunds", area="Payments/Refunds")
    assert run_cli_with_body(state, json.dumps(body), "capture", "PR") == 0
    err = capsys.readouterr().err
    assert "[outline] Payments/Refunds is a new level" in err, err
    assert "Frontend/Checkout" in err

    again = dict(PR_FIELDS, title="More refunds", area="Payments/Refunds")
    assert run_cli_with_body(state, json.dumps(again), "capture", "PR") == 0
    assert "[outline]" not in capsys.readouterr().err

    # ...and a body the kernel REFUSES gets no advice about a level it never created: the hint
    # sits behind the write, and a third outline level is refused there.
    refused = dict(PR_FIELDS, title="Too deep", area="Payments/Refunds/Partial")
    assert run_cli_with_body(state, json.dumps(refused), "capture", "PR") == 1
    printed = capsys.readouterr()
    assert "[outline]" not in printed.err, printed.err
    assert "at most 2" in printed.err


def test_cli_evidence_records_the_run_behind_the_verdict_and_refuses_a_half_of_it(state, capsys):
    """FR-0040 at the surface a role types, and BUG-0192 made both halves required there.

    The pair is the statement -- the scope is what the merge reads and the command is what an
    auditor re-runs it against. Since BUG-0192 the parser demands BOTH: a record that declared
    nothing counted as a full run, so a partial run opened a merge in silence, and the reading end
    could not be tightened (an `EVD` is immutable). What the declaration then BUYS is measured one
    layer down, in `test_report.test_a_pass_from_a_partial_run_is_not_merge_evidence_and_a_fail_
    still_is`; here the question is only whether the surface carries it at all.

    THREE ROWS AND EACH ONE A DIFFERENT REFUSER: the parser refuses a call that declares NEITHER
    half; the KERNEL still refuses a half-declared pair, which is what keeps the rule for a caller
    that does not come through this parser; and a declared run is recorded with both keys. The
    legal call runs after each refusal for the reason its neighbour below states -- a bare "it
    exited non-zero" would be satisfied by argparse rejecting the whole subcommand.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    common = ("evidence", "--kind", "test", "--result", "pass", "--related", pr["id"],
              "--summary", "suite green", "--artifact-ref", "staging/TSK-0001/run.log")

    with pytest.raises(SystemExit):
        run_cli(state, *common)
    printed = capsys.readouterr().err
    assert "--run-command" in printed and "--run-scope" in printed, printed

    # ...the kernel's own half of the rule, for a caller that never met the parser
    with pytest.raises(StateError) as refused:
        state.capture("EVD", {"kind": "test", "related": [pr["id"]], "result": "pass",
                              "summary": "suite green", "artifact_refs": ["staging/x/run.log"],
                              "run_scope": "full"})
    assert "run_command" in str(refused.value), refused.value

    assert run_cli(state, *common, "--run-scope", "selection",
                   "--run-command", "python -m pytest tools/ -k checkout") == 0
    capsys.readouterr()
    path = os.path.join(state.root, *ACTIVE_DIRS["EVD"].split("/"), "EVD-0001.yaml")
    with open(path, encoding="utf-8") as handle:
        item = yaml.safe_load(handle)
    assert item["run_scope"] == "selection"
    assert item["run_command"] == "python -m pytest tools/ -k checkout"


def test_cli_evidence_will_not_record_a_verdict_with_nothing_to_point_at(state, capsys):
    """`--artifact-ref` is required, because the whole group's claim is proof over assertion.

    Every role text and every refusal `gate_git` prints presents that flag as THE proof, and it
    was optional: `python scripts/harness.py evidence --kind test --result pass --related PR-0001 --summary "sieht
    gut aus"` recorded a verdict pointing nowhere and opened the merge (measured). Argparse is
    only the front door — the kernel refuses the empty list as well (test_state.py), which is what
    makes the rule hold for a caller that does not come through this parser.
    """
    state.capture("PR", dict(PR_FIELDS))
    with pytest.raises(SystemExit):
        run_cli(state, "evidence", "--kind", "test", "--result", "pass",
                "--related", "PR-0001", "--summary", "sieht gut aus")
    assert "--artifact-ref" in capsys.readouterr().err
    assert run_cli(state, "evidence", "--kind", "test", "--result", "pass",
                   "--related", "PR-0001", "--summary", "sieht gut aus",
                   "--artifact-ref", "staging/TSK-0001/suite.log", "--run-command", "pytest -q", "--run-scope", "selection") == 0


def test_cli_evidence_refuses_a_binding_that_names_nothing(state, capsys):
    """Evidence bound to a phantom id is bound to nothing, and would look like proof anyway."""
    state.capture("PR", dict(PR_FIELDS))
    assert run_cli(state, "evidence", "--kind", "test", "--result", "pass",
                   "--related", "PR-0099", "--summary", "s",
                   "--artifact-ref", "staging/x.log", "--run-command", "pytest -q", "--run-scope", "selection") == 1
    assert "does not exist" in capsys.readouterr().err


def test_evidence_can_judge_a_frozen_item_and_reaches_its_root(state):
    """A frozen item is stored per REVISION, and by its plain id it did not exist at all.

    `freeze_wireframe` and `freeze_design` write `WFR-0001.r01.yaml` / `DSN-0001.r01.yaml`, while
    `active_path` composes `<id>.yaml`. So the two readers that answer "does this id name an
    item" answered no: the kernel REFUSED an Evidence recorded against a wireframe ("does not
    exist"), and the merge gate's walk stopped at the id. The designer's review could not be
    recorded, and the reviewing role would then have been told by `gate_git` that nothing judges
    the work — the same refusal the reference-graph fix was written for, at the one item type
    whose file name carries a revision.

    Asserted as the merge gate asks it: the verdict has to arrive at the ROOT.
    """
    from kernel import report
    pr = state.capture("PR", dict(PR_FIELDS))
    stage_file(state, "wire", "WFR-0001.drawio.svg")
    staging.freeze_wireframe(state, "wire", "WFR-0001", scope_apr_ref="APR-0001",
                             derives_from=[pr["id"]], title="Checkout layout")
    stage_file(state, "design", "preview.html", content="<html><body>x</body></html>")
    staging.freeze_design(state, "design", "DSN-0001", pr["id"], "preview.html")
    for target, kind in (("WFR-0001", "review"), ("DSN-0001", "acceptance")):
        assert state.exists_anywhere(target), "%s does not resolve by its own id" % target
        evidence = state.capture("EVD", {
            "kind": kind, "result": "pass", "related": [target], "summary": "judged",
            "artifact_refs": ["staging/TSK-0001/notes.md"]})
        assert report.evidence_covers(state, state.read_item(evidence["id"]), pr["id"]), target
    verdicts = report.qa_verdicts(state, pr["id"])
    assert {kind: entry["result"] for kind, entry in verdicts.items()} == {
        "review": "pass", "acceptance": "pass"}


# -- the four commands spec II.4 named and the surface lacked (capture/create-task/
#    dispatch/submit-result) --------------------------------------------------------------

def run_cli_with_body(state, body, *argv):
    """Run the CLI with a JSON body on stdin, the way a heredoc or a pipe delivers one."""
    previous = sys.stdin
    sys.stdin = io.StringIO(body)
    try:
        return run_cli(state, *argv)
    finally:
        sys.stdin = previous


def test_cli_capture_creates_a_typed_item_from_a_json_body(state, capsys):
    body = json.dumps(PR_FIELDS)
    assert run_cli_with_body(state, body, "capture", "PR") == 0
    assert "PR-0001 DRAFT" in capsys.readouterr().out
    item = state.read_item("PR-0001")
    assert item["title"] == PR_FIELDS["title"] and item["revision"] == 1
    # the kernel stamps its own fields -- a body may not carry them (`_KERNEL_SET`)
    assert item["approval_ref"] is None and item["created"]


def test_cli_capture_carries_a_list_of_mappings_no_flag_surface_could(state):
    """The reason the body is stdin at all: `acceptance_criteria` is [{id, text}].

    A flag surface would have to invent an encoding for it, and the encoding would then be a
    second grammar between the role and the hash. The mapping arrives unchanged here.
    """
    assert run_cli_with_body(state, json.dumps(PR_FIELDS), "capture", "PR") == 0
    assert state.read_item("PR-0001")["acceptance_criteria"] == PR_FIELDS["acceptance_criteria"]


def test_cli_capture_refuses_a_body_it_did_not_read(state, capsys):
    """rc 2, not 1: the kernel never looked, so reporting a refusal would be a lie about what
    happened. Both shapes a role produces by accident are covered -- nothing on stdin, and YAML
    typed where JSON was asked for."""
    assert run_cli_with_body(state, "", "capture", "PR") == 2
    assert "JSON object on STDIN" in capsys.readouterr().err
    assert run_cli_with_body(state, "title: x\nclass: normal\n", "capture", "PR") == 2
    assert "not JSON" in capsys.readouterr().err
    assert run_cli_with_body(state, "[1, 2]", "capture", "PR") == 2
    assert "JSON OBJECT" in capsys.readouterr().err


def test_cli_capture_of_a_task_goes_through_the_task_constructor(state, capsys):
    """`root_revision` has ONE producer, and `capture TSK` is not a second one.

    The field decides whether a lease is allowed at all (`create_lease` compares it against the
    root's current revision), so a body that carried it by hand would be a role choosing its own
    answer to that question. `dispatch.create_task` refuses the field and denormalizes it instead
    -- and `capture TSK` routes there, so both spellings get the same one.
    """
    state.capture("PR", dict(PR_FIELDS))
    fields = {"product_requirement": "PR-0001", "derives_from": "PR-0001",
              "type": "implementation", "assigned_role": "backend-developer",
              "acceptance_refs": ["AC-1"], "required_inputs": [], "allowed_scope": ["src/"],
              "forbidden_scope": [], "expected_outputs": ["out"], "dependencies": []}
    assert run_cli_with_body(state, json.dumps(fields), "capture", "TSK") == 0
    capsys.readouterr()
    assert state.read_item("TSK-0001")["root_revision"] == 1
    assert run_cli_with_body(state, json.dumps(dict(fields, root_revision=99)),
                             "capture", "TSK") == 1
    assert "kernel-set" in capsys.readouterr().err


def test_cli_create_task_writes_the_work_order_the_gates_read(state, capsys):
    state.capture("PR", dict(PR_FIELDS))
    assert run_cli(state, "create-task",
                   "--product-requirement", "PR-0001", "--derives-from", "PR-0001",
                   "--type", "implementation", "--assigned-role", "backend-developer",
                   "--acceptance-ref", "AC-1", "--allowed-scope", "src/",
                   "--allowed-scope", "tests/", "--forbidden-scope", "secrets/",
                   "--expected-output", "src/checkout.py") == 0
    assert "TSK-0001 DRAFT (backend-developer)" in capsys.readouterr().out
    task = state.read_item("TSK-0001")
    assert task["allowed_scope"] == ["src/", "tests/"]         # gate layer 3's only input
    assert task["forbidden_scope"] == ["secrets/"]
    assert task["root_revision"] == 1 and task["dependencies"] == []


def test_cli_create_task_refuses_a_type_outside_the_closed_vocabulary(state, capsys):
    state.capture("PR", dict(PR_FIELDS))
    with pytest.raises(SystemExit) as exited:
        run_cli(state, "create-task", "--product-requirement", "PR-0001",
                "--derives-from", "PR-0001", "--type", "frontend-work",
                "--assigned-role", "frontend-developer", "--acceptance-ref", "AC-1",
                "--allowed-scope", "src/")
    assert exited.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def _approved_ready_task(state):
    """A PR with a real scope approval and a READY task under it -- the dispatch precondition."""
    pr = state.capture("PR", dict(PR_FIELDS))
    approve(state, pr["id"], "scope")
    assert run_cli(state, "create-task", "--product-requirement", pr["id"],
                   "--derives-from", pr["id"], "--type", "implementation",
                   "--assigned-role", "backend-developer", "--acceptance-ref", "AC-1",
                   "--allowed-scope", "src/", "--expected-output", "src/x.py") == 0
    state.transition("TSK-0001", "READY")
    satisfy_the_architect_step(state, state.read_item("TSK-0001"), state.read_item(pr["id"]))
    return pr, state.read_item("TSK-0001")


def test_cli_dispatch_leases_the_task_and_prints_only_the_header(state, capsys):
    """The header is copied into the spawn prompt character for character, so stdout carries it
    and nothing else -- anything printed beside it is something a role might copy along."""
    _pr, task = _approved_ready_task(state)
    capsys.readouterr()
    assert run_cli(state, "dispatch", task["id"]) == 0
    printed = capsys.readouterr().out.strip()
    assert printed.startswith(dispatch.HEADER_PREFIX), printed
    header = dispatch.parse_header(printed)
    assert header["task_id"] == task["id"] and header["root_revision"] == 1
    assert state.read_item(task["id"])["status"] == "LEASED"
    # the nonce is the lease's, not the model's: the gate validates the printed header as-is
    assert dispatch.validate_lease(state, header)["nonce"] == header["lease"]


def test_cli_dispatch_refuses_a_second_claim_and_an_unapproved_root(state, capsys):
    _pr, task = _approved_ready_task(state)
    assert run_cli(state, "dispatch", task["id"]) == 0
    capsys.readouterr()
    assert run_cli(state, "dispatch", task["id"]) == 1      # not READY any more
    assert "not READY" in capsys.readouterr().err

    other = state.capture("PR", dict(PR_FIELDS, title="Unapproved"))
    assert run_cli(state, "create-task", "--product-requirement", other["id"],
                   "--derives-from", other["id"], "--type", "implementation",
                   "--assigned-role", "backend-developer", "--acceptance-ref", "AC-1",
                   "--allowed-scope", "src/", "--expected-output", "src/x.py") == 0
    state.transition("TSK-0002", "READY")
    capsys.readouterr()
    assert run_cli(state, "dispatch", "TSK-0002") == 1
    assert "no subagent without a user approval" in capsys.readouterr().err


def test_cli_dispatch_has_no_ttl_flag(state):
    """"Kurzlebige Lease" is the property spec II.4 names, so the supervised party does not get to
    choose how short short is. Asserted off the parser, which is what argparse evaluates."""
    parser = cli.build_parser()
    lease = parser._subparsers._group_actions[0].choices["dispatch"]
    options = [option for action in lease._actions for option in action.option_strings]
    assert not [option for option in options if "ttl" in option.lower()], options


def test_cli_submit_result_moves_the_task_and_stores_the_envelope(state, capsys):
    _pr, task = _approved_ready_task(state)
    header = dispatch.parse_header(_dispatch_line(state, task["id"], capsys))
    dispatch.validate_dispatch(state, header, "backend-developer", claim=True)
    dispatch.spawn_outcome(state, task["id"], True)
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS"

    assert run_cli(state, "submit-result", "--task-id", task["id"],
                   "--role", "backend-developer", "--status-proposal", "SUBMITTED",
                   "--summary", "checkout implemented", "--output", "src/checkout.py",
                   "--scope-touched", "src/checkout.py") == 0
    assert "%s -> SUBMITTED" % task["id"] in capsys.readouterr().out
    envelope = state._read_yaml(os.path.join(state.root, "tasks", "results",
                                             task["id"] + ".envelope.yaml"))
    assert envelope["outputs"] == ["src/checkout.py"] and envelope["followups"] == []


def test_cli_submit_result_holds_the_envelope_to_its_schema(state, capsys):
    """The 4 KB cap and the field contract are the schema's, and the CLI does not soften them:
    raw logs are REFERENCED (spec II.5), so an inlined one is refused at the kernel boundary."""
    _pr, task = _approved_ready_task(state)
    header = dispatch.parse_header(_dispatch_line(state, task["id"], capsys))
    dispatch.validate_dispatch(state, header, "backend-developer", claim=True)
    dispatch.spawn_outcome(state, task["id"], True)
    assert run_cli(state, "submit-result", "--task-id", task["id"],
                   "--role", "backend-developer", "--status-proposal", "SUBMITTED",
                   "--summary", "x" * 3000) == 1
    assert "max_len" in capsys.readouterr().err
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS"


def _dispatch_line(state, task_id, capsys):
    capsys.readouterr()
    assert run_cli(state, "dispatch", task_id) == 0
    return capsys.readouterr().out.strip()


# -- request-approval: the walkable counterpart to the transition gate -------------------------

def test_cli_request_approval_opens_the_question_the_gate_will_pin(state, capsys):
    """Without this command the transition gate had no counterpart at all.

    `create_pending_request` had no caller in the shipped tree, so no `[APR-REQ:<id>]` question
    could exist, so nothing could ever mint -- and a gated edge would refuse forever. What is
    asserted is the whole chain the gate needs: a pending request on disk, a question carrying
    that request's marker, and a question BYTE-IDENTICAL to what `build_question` rebuilds from
    the stored request (which is what `gate_approval` compares against).
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    assert run_cli(state, "request-approval", "scope", pr["id"]) == 0
    printed = json.loads(capsys.readouterr().out)

    pending = os.path.join(state.root, "approvals", "pending")
    files = sorted(os.listdir(pending))
    assert len(files) == 1, files
    request_id = files[0][:-5]
    assert "[APR-REQ:%s]" % request_id in printed["question"]
    stored = approvals.pending_request(state, request_id)
    assert printed == approvals.build_question(stored)
    # the mint code lives ONLY in the approval option's label (spec II.2 / spike S2b)
    assert stored["mint_code"] in printed["options"][0]["label"]
    assert stored["mint_code"] not in printed["question"] + printed["header"]


# A SUBJECT KEY WHOSE VALUE HAS TO BE MORE THAN A LETTER, keyed by the parameter name the builders
# share. `"x"` is a legal value for almost every subject key, and the test below leans on that; a
# builder that REFUSES a subject it could not show the user honestly needs a sample that gets past
# its own refusal, or this test would measure that refusal instead of the manifest. `proposal` is
# such a key: `kernel.documents` only ever reads from the proposal area, so a bare name is refused
# by `approvals.document_proposal_subject_manifest` (see its `_PROPOSAL_PREFIX`).
SUBJECT_SAMPLES = {
    "proposal": "staging/TSK-0001/x.yaml",
    # A plan's subject is a LIST of goal records rather than a scalar (FR-0074), so the sample is
    # shaped the way `approvals.plan_goals` builds one -- with the kernel's own key names, since a
    # retyped key here would make this fixture describe a manifest the builder does not produce.
    "goals": [{approvals.GOAL_ITEM_FIELD: "PR-0001", "title": "Checkout", "revision": 1,
               approvals.GOAL_SCOPE_HASH_FIELD: "0" * 64}],
    # The second list-bound subject (PR-0012 AC-1): a verification approval's subject is the batch
    # of repaired defects, each with the Evidence that measured it. Same rule as `goals` above --
    # the kernel's own key names, because a retyped key would make this fixture describe a manifest
    # the builder does not produce -- and a record rather than a scalar, because the builder refuses
    # a batch that lists nothing (an approval bound to no defect at all).
    "bugs": [{approvals.GOAL_ITEM_FIELD: "BUG-0001", "revision": 1,
              approvals.GOAL_SCOPE_HASH_FIELD: "0" * 64,
              approvals.LISTED_EVIDENCE_FIELD: "EVD-0001"}],
}


def test_cli_request_approval_offers_exactly_the_kinds_a_manifest_builder_exists_for(state, capsys):
    """The surface is the kinds SOMETHING can build a subject manifest for -- and only those.

    The predecessor said `APR_KINDS - EXPIRING_KINDS` and called that "the item-derived kinds".
    Two properties in one sentence, agreeing by accident: `push` is time-boxed AND has a manifest
    builder, so the moment the CLI grew `request-approval push` -- the gap that made every project
    unable to publish -- the sentence was wrong about both halves. The property that actually
    decides the surface is whether a manifest for that kind can be BUILT without a caller who
    types an analysis question, a read-only scope and a cadence; the two families that can are
    `item_derived_kinds` (from an item id) and `line_manifest_kinds` (from flags).

    Not a set comparison alone, which would only prove somebody wrote the same expression twice.
    Every offered kind is put through the builder its family names and has to return a manifest,
    and every kind of the vocabulary that NO family claims has to be refused by the real parser.
    So a kind added to the surface without a builder fails on the equality, a kind whose builder
    stopped producing a manifest fails on the call, and a builder family that grew a name outside
    `APR_KINDS` fails on the vocabulary assertion.

    WHAT THIS CANNOT SAY, measured rather than guessed: adding a kind to `APR_KINDS` with no
    builder anywhere leaves this green, because the parser then refuses it and the loop below
    asserts exactly that. Whether such a kind SHOULD have become requestable is a reading -- it is
    the state `routine` and `analysis` are deliberately in. The `push` shape, a kind that HAS a
    builder while the surface ignores it, is the one this test is red for.
    """
    parser = cli.build_parser()
    offered = parser._subparsers._group_actions[0].choices["request-approval"]._actions
    kinds = [action.choices for action in offered if action.dest == "kind"][0]
    item_built = set(approvals.item_derived_kinds())
    line_built = set(approvals.line_manifest_kinds())
    buildable = item_built | line_built

    assert set(kinds) == buildable
    assert buildable <= set(approvals.APR_KINDS), (
        "a manifest builder names a kind the approval vocabulary does not have: %s"
        % sorted(buildable - set(approvals.APR_KINDS)))

    for kind in sorted(kinds):
        if kind in item_built:
            manifest = approvals.item_subject_manifest({"id": "PR-0001", "revision": 1}, kind)
        else:
            builder = approvals.LINE_MANIFEST_BUILDERS[kind]
            # the flags the parser really carries for this kind, read off the same signature the
            # parser read -- a builder whose keys moved takes its command line with it
            manifest = builder(**{name: SUBJECT_SAMPLES.get(name, "x")
                                  for name in cli.manifest_parameters(builder)})
        assert isinstance(manifest, dict) and manifest, (
            "`request-approval %s` is offered, but its manifest builder returns nothing to hash"
            % kind)

    # ...and every kind no family can build stays OFF the command line, judged by the parser
    # rather than named here (`routine`/`analysis` today, whatever the split says tomorrow).
    state.capture("PR", dict(PR_FIELDS))
    unbuildable = sorted(set(approvals.APR_KINDS) - buildable)
    assert unbuildable, "every kind is buildable, so this half of the split measures nothing"
    for kind in unbuildable:
        with pytest.raises(SystemExit) as exited:
            run_cli(state, "request-approval", kind, "PR-0001")
        assert exited.value.code == 2
        assert "invalid choice" in capsys.readouterr().err


# -- FR-0050: the filing-correction request, from the command line the clerk is handed ----------

def _document(state, relative, text="rechnung\n"):
    """Put real bytes at a repo-relative path of this state's project — the approval binds them."""
    path = os.path.join(os.path.dirname(state.root), *relative.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _correction_question(state, capsys, *argv):
    assert run_cli(state, "request-approval", "filing_correction", *argv) == 0
    return json.loads(capsys.readouterr().out)


def test_a_line_kind_without_a_defaulted_subject_key_still_demands_every_one(state, capsys):
    """The optional-key rule is READ OFF THE BUILDER, so it widens nothing that was closed.

    `cli.optional_manifest_parameters` is what lets `filing_correction` be requested without a
    `--destination` (the absence is the deletion). This measures the other end of that derivation:
    every older line kind declares no default, so it still refuses a subject key the line left out —
    which is the property that makes a push question say what it releases.
    """
    for kind, builder in sorted(approvals.LINE_MANIFEST_BUILDERS.items()):
        optional = cli.optional_manifest_parameters(builder)
        assert optional <= set(cli.manifest_parameters(builder))
        if kind != "filing_correction":
            assert not optional, "%s grew a defaulted subject key without a measurement" % kind
    assert cli.optional_manifest_parameters(
        approvals.filing_correction_subject_manifest) == {"destination"}
    assert run_cli(state, "request-approval", "push", "--remote", "origin") == 2
    assert "branch is missing" in capsys.readouterr().err


def test_a_filing_correction_question_says_in_words_what_happens_to_the_document(state, capsys):
    """BUG-0041's audience decides this one, and it is the question with the sharpest consequence.

    Both outcomes are named as what they DO, never as the manifest key that tells them apart: a
    reader must not have to notice that `destination` is empty to learn that a document is about to
    be destroyed. Everything the hash covers is in the sentence -- the document, the outcome, the
    reason, the version, the expiry -- and the version is SHORTENED like every other digest in this
    question (`_render_manifest_value`), because a 64-character hex string in the middle of it is
    what made the `kit_update` question unreadable.
    """
    _document(state, "archive/1-Finanzen/2026/x.pdf")
    moved = _correction_question(state, capsys, "--document", "archive/1-Finanzen/2026/x.pdf",
                                 "--destination", "outbox/x.pdf", "--reason", "falsch abgelegt")
    text = moved["question"]
    assert "archive/1-Finanzen/2026/x.pdf" in text and "outbox/x.pdf" in text
    assert "verschoben" in text and "falsch abgelegt" in text
    assert "GELÖSCHT" not in text

    _document(state, "inbox/a.pdf", "scan\n")
    deleted = _correction_question(state, capsys, "--document", "inbox/a.pdf",
                                   "--reason", "Doppelscan")
    assert "GELÖSCHT" in deleted["question"] and "danach weg" in deleted["question"]
    assert "destination" not in deleted["question"]

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "team-kits"))
    from kernel import hashing
    digest = hashing.document_content_hash(
        os.path.join(os.path.dirname(state.root), "inbox", "a.pdf"))
    assert digest[:approvals.DIGEST_SHOWN] in deleted["question"]
    assert digest not in deleted["question"], "the full digest makes the question unreadable"


def test_a_document_the_kernel_cannot_hash_is_refused_where_the_clerk_types_it(state, capsys):
    """"Which file?" is answered at the command line or nowhere.

    The two causes a clerk really hits are a mistyped path and a document past
    `hashing.DOCUMENT_HASH_LIMIT`, and neither is helped by the generic "a subject key is missing"
    remedy that lists four flags. So the resolver refuses with the path it looked for.
    """
    assert run_cli(state, "request-approval", "filing_correction",
                   "--document", "archive/nope.pdf", "--reason", "weg damit") == 2
    error = capsys.readouterr().err
    assert "archive/nope.pdf" in error and "bytes" in error


def test_a_document_outside_the_project_is_refused_rather_than_bound_to_an_approval_that_cannot_match(
        state, capsys, tmp_path):
    """An approval nothing can ever match is a dead end handed over without a word.

    `guard_fs_tripwire` asks only about positions relative to the project root, so a document named
    absolutely — or one that climbs out — could be hashed and signed and would then cover nothing at
    all. It is refused where the clerk types it, with the same message the missing-file case gets.
    """
    outside = tmp_path.parent / "elsewhere.pdf"
    outside.write_text("nicht in diesem Projekt\n", encoding="utf-8")
    for spelling in (str(outside), "../elsewhere.pdf"):
        assert run_cli(state, "request-approval", "filing_correction",
                       "--document", spelling, "--reason", "weg damit") == 2
        assert "bytes" in capsys.readouterr().err, spelling


def test_a_document_named_in_a_spelling_the_gate_cannot_produce_is_refused_at_the_command_line(
        state, capsys):
    """Verifier finding F5: the earlier check asked whether the FILE is inside, not the SPELLING.

    An absolute path to a document that really lies inside the project passed it, minted a real
    approval — and then the same document named the way `guard_fs_tripwire` names it was refused,
    because the manifest carried a position the gate can never produce. That is the M15 dead end one
    spelling further in. The typed spelling now has to round-trip: resolved against the project root
    and normalised back, it must come out as what was typed.

    Both directions, because a refusal that also refuses the legitimate spelling is the other defect.
    """
    document = _document(state, "archive/1-Finanzen/2026/x.pdf")
    for dead_end in (document, os.path.abspath(document), "archive/../archive/../../x.pdf"):
        assert run_cli(state, "request-approval", "filing_correction",
                       "--document", dead_end, "--reason", "falsch abgelegt") == 2, dead_end
        assert "bytes" in capsys.readouterr().err, dead_end
    assert run_cli(state, "request-approval", "filing_correction",
                   "--document", "./archive/1-Finanzen/../1-Finanzen/2026/x.pdf",
                   "--reason", "falsch abgelegt") == 0
    question = json.loads(capsys.readouterr().out)
    assert "archive/1-Finanzen/2026/x.pdf" in question["question"]


def test_a_document_named_in_the_wrong_case_is_refused_by_its_real_name(state, capsys):
    """Verifier round 2, R2: the round-trip was lexical, so a case-flip minted a dead approval.

    On a case-insensitive filesystem `ARCHIVE/…/x.pdf` opens the same file, resolves to the same
    absolute path and normalises back to itself — it round-trips perfectly. The gate, though, reads
    the position out of the command that touches the document, and the archive spells it
    `archive/…`. So the user answered a question, an approval was minted, and it matched nothing:
    a burned approval, which is worse than a refusal.

    Measured on both ends: the deviant spelling is refused BY the real name (so the clerk can copy
    it out of the message), and the real name still works.

    THE PREMISE IS A PROPERTY OF THE FILESYSTEM, and it is asked of the very file the fixture just
    wrote rather than of `os.name`. On a case-sensitive one the case-flip opens nothing, the burned
    approval this measures cannot arise, and the refusal that does arrive is the ordinary
    unreadable-document one -- which is a different check's subject. The hosted ubuntu runner is
    such a host, and this test failed there while measuring nothing (BUG-0069).
    """
    document = _document(state, "archive/1-Finanzen/2026/x.pdf")
    flipped = os.path.join(os.path.dirname(state.root), "ARCHIVE", "1-Finanzen", "2026", "x.pdf")
    if not os.path.isfile(flipped):
        pytest.skip("this filesystem is case-sensitive, so %s opens nothing and the case-flip "
                    "cannot mint the dead approval this measures" % os.path.basename(document))
    assert run_cli(state, "request-approval", "filing_correction",
                   "--document", "ARCHIVE/1-Finanzen/2026/x.pdf", "--reason", "Doppelscan") == 2
    error = capsys.readouterr().err
    assert "archive/1-Finanzen/2026/x.pdf" in error and "ARCHIVE/" in error, error
    assert run_cli(state, "request-approval", "filing_correction",
                   "--document", "archive/1-Finanzen/2026/x.pdf", "--reason", "Doppelscan") == 0
    assert "archive/1-Finanzen/2026/x.pdf" in json.loads(capsys.readouterr().out)["question"]


@pytest.mark.parametrize("spelling", [".", "./", "/", "   ", "C:/elsewhere", "../out"])
def test_a_destination_that_names_no_place_in_this_project_is_refused(state, capsys, spelling):
    """Verifier finding F7: a destination that normalises empty became a DELETION, silently.

    `--destination .` produced a question saying the document "wird GELÖSCHT und ist danach weg" —
    the user would have signed a deletion nobody asked for. Leaving the flag OUT stays the way to
    request one, because an absence is a decision and a mistyped path is not. The absolute and
    climbing spellings are the same refusal one property further on: a destination the gate can
    never produce would mint an approval that matches nothing (F5's half for the other key).
    """
    _document(state, "archive/1-Finanzen/2026/x.pdf")
    assert run_cli(state, "request-approval", "filing_correction",
                   "--document", "archive/1-Finanzen/2026/x.pdf",
                   "--destination", spelling, "--reason", "falsch abgelegt") == 2
    assert capsys.readouterr().err.strip(), spelling
    # ...and the deliberate deletion, asked for by leaving the flag out, still works
    assert run_cli(state, "request-approval", "filing_correction",
                   "--document", "archive/1-Finanzen/2026/x.pdf", "--reason", "Doppelscan") == 0
    assert "GELÖSCHT" in json.loads(capsys.readouterr().out)["question"]


def test_the_missing_key_remedy_names_the_flags_this_command_really_takes(state, capsys):
    """Verifier finding F8: the remedy contradicted the command it was the remedy for.

    It printed EVERY manifest key as a flag to type, so it named `--content` — which this same
    function refuses when typed — and `--destination` as required, whose omission is the documented
    way to ask for a deletion. Derived now from the two statements the loop itself decides on, so a
    fourth reader of `optional_manifest_parameters` cannot disagree with it.
    """
    assert run_cli(state, "request-approval", "filing_correction",
                   "--destination", "outbox/x.pdf") == 2
    error = capsys.readouterr().err
    assert "--content" not in error, error
    assert "--document <document>" in error and "[--destination <destination>]" in error, error
    assert "--reason <reason>" in error, error


def test_the_correction_hash_binds_the_operation_and_the_reason_beside_it(state):
    """DEC-0048 in its constructive direction: the signature covers exactly what happens.

    The user signs document + version + outcome + reason, so a changed reason is a different
    subject and a different question. What the GATE matches is the operation alone
    (`filing_correction_operation`) -- an approval is not for a different correction because its
    justification was worded differently -- and every one of the three operation keys moves that
    match, which is what makes the approval single-use and document-bound.
    """
    base = dict(document="archive/a.pdf", content="a" * 64, reason="falsch abgelegt",
                destination="outbox/a.pdf")
    signed = approvals.subject_manifest_hash(
        approvals.filing_correction_subject_manifest(**base))
    assert signed != approvals.subject_manifest_hash(
        approvals.filing_correction_subject_manifest(**dict(base, reason="anderer Grund")))
    operation = approvals.filing_correction_operation(
        base["document"], base["destination"], base["content"])
    assert approvals.subject_manifest_hash(operation) == approvals.subject_manifest_hash(
        {key: approvals.filing_correction_subject_manifest(
            **dict(base, reason="anderer Grund"))[key] for key in operation})
    for changed in (dict(document="archive/b.pdf"), dict(destination="outbox/b.pdf"),
                    dict(destination=""), dict(content="b" * 64)):
        other = dict(base, **changed)
        assert approvals.subject_manifest_hash(operation) != approvals.subject_manifest_hash(
            approvals.filing_correction_operation(
                other["document"], other["destination"], other["content"])), changed


def test_one_position_has_one_spelling_on_both_sides_of_a_correction(state):
    """The request side types a path and the gate side resolves one; they have to meet.

    `approvals.filed_position` is where they meet, and it is one function for that reason -- a
    Windows separator, a leading `./`, a `..` segment and a trailing slash are spellings of one
    position, and two normalisations would make an approved correction match nothing. The empty
    string stays empty, because that absence is what distinguishes a deletion from a move.

    AN ABSOLUTE PATH STAYS ABSOLUTE, and that is the correction of verifier finding F5: it used to
    be `strip("/")`, so `/etc/passwd` came back as the project-looking `etc/passwd`. Deciding
    whether the result is a place this project HAS is `is_project_position`'s job, and it is a
    separate function because the gate needs the normalisation without the verdict.
    """
    for spelling in ("archive/1-Finanzen/x.pdf", "archive\\1-Finanzen\\x.pdf",
                     "./archive/1-Finanzen/x.pdf", "archive/2026/../1-Finanzen/x.pdf",
                     "  archive/1-Finanzen/x.pdf  "):
        assert approvals.filed_position(spelling) == "archive/1-Finanzen/x.pdf", spelling
        assert approvals.is_project_position(spelling), spelling
    for nothing in ("", None, ".", "./", "   "):
        assert approvals.filed_position(nothing) == "", nothing
        assert not approvals.is_project_position(nothing), nothing
    assert approvals.filed_position("outbox/") == "outbox"
    # ...and every spelling the GATE can never produce is a place this project does not have
    for outside in ("/", "/etc/passwd", "C:/Windows/win.ini", "..", "../elsewhere.pdf",
                    "archive/../../elsewhere.pdf", "archive/x\ny.pdf", "archive/x\u202ey.pdf"):
        assert not approvals.is_project_position(outside), outside


def test_the_installer_position_prints_utf8_whatever_the_console_codepage_is(state, tmp_path):
    """The PRE-INSTALL position is the one `_pin_utf8` saves, and this measures that position.

    Measured with the function removed: the INSTALLED entry point still prints UTF-8, because the
    shim imports `_kernel` -> `_compat`, which pins both streams at import. The installer position
    (`python -B -m kernel.cli …`, what the entry gate uses) loads no hook helper and was cp1252.
    So the subject here is that command, run with `PYTHONIOENCODING=cp1252` to stand in for a
    console that is not UTF-8 -- and the bytes it writes have to decode as UTF-8, because
    `gate_approval` compares the question character for character.

    The predecessor of this test asserted only that `_pin_utf8()` calls `reconfigure` twice; it
    could not go red for any other reason and never touched the path its docstring described.
    """
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pr = state.capture("PR", dict(PR_FIELDS))
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONUTF8")}
    env["PYTHONPATH"] = os.path.join(root, "team-kits")
    env["PYTHONIOENCODING"] = "cp1252"
    opened = subprocess.run(
        [sys.executable, "-B", "-m", "kernel.cli", "--root", state.root,
         "request-approval", "scope", pr["id"]],
        capture_output=True, env=env, timeout=120)
    assert opened.returncode == 0, opened.stderr.decode("utf-8", "replace")
    question = json.loads(opened.stdout.decode("utf-8"))     # strict: mojibake fails here
    assert "für" in question["question"], question["question"]
    assert question == approvals.build_question(
        approvals.pending_request(state, question["question"].split("[APR-REQ:")[1][:32]))


def test_cli_capture_refuses_a_body_over_the_item_budget(state, capsys):
    """`capture` went around the budget every other writer into this tree obeys.

    Measured before this: a 2 MB body was accepted, the item written, and only `validate` said so
    afterwards -- about a file nothing can edit any more (`update_item` refuses hashed-field
    surgery, and there is no edit command at all). The cap is `report.ITEM_MAX_BYTES`, read from
    the validator's own constant so the two cannot drift.

    THE REFUSAL NAMES NO LANDING PLACE, and the word `staging` used to be asserted here. DEC-0024
    took it out of the message: a place a remedy prints is a place the reader completes, and what
    they put there can already be taken. So what is asserted is the number and the direction the
    refusal gives -- an item REFERENCES its detail --, measured on the printed line rather than on
    the module's constant. `test_migrate.test_no_remedy_literal_this_repo_ships_names_a_place_
    inside_a_state_directory` is what keeps a place from coming back.
    """
    body = dict(PR_FIELDS, problem="x" * (report.ITEM_MAX_BYTES + 1))
    assert run_cli_with_body(state, json.dumps(body), "capture", "PR") == 2
    err = capsys.readouterr().err
    assert str(report.ITEM_MAX_BYTES) in err and "REFERENCES its detail" in err
    assert not os.path.exists(state.active_path("PR-0001"))


def _recurses(depth):
    """Does `json.loads` give up on a list nested `depth` deep on THIS interpreter?

    The search below bisects, and a single negative answer at the budget's own depth is what lets
    it skip, so both rest on deeper nesting being more parser recursion and never less. That is
    not asserted here as prose: the search checks its own result against the depth one shallower,
    which is where a host on which it does not hold would show up.
    """
    try:
        json.loads("[" * depth + "]" * depth)
    except RecursionError:
        return True
    return False


def test_cli_capture_survives_a_body_no_parser_can_bound(state, capsys):
    """A RecursionError is not a usage message; a role hitting one learns nothing.

    THE DEPTH COMES FROM THE INTERPRETER AND THE BUDGET TOGETHER, never from a number that looked
    deep enough. The first version sent 400 brackets, which `json.loads` parses without complaint --
    so it never reached the branch it was written for and passed on the LIST refusal instead
    (mutation-measured: `except RecursionError` -> `except ZeroDivisionError` stayed green). The
    second doubled up from `sys.getrecursionlimit()` and only THEN asked whether the result still
    fit `report.ITEM_MAX_BYTES`, which made the fixture its own subject: on CPython 3.14 neither
    hosted runner gives up anywhere near the budget, so both reported as a defect what was this
    test's own arithmetic (BUG-0069).

    The BUDGET bounds the search now, so whatever comes out is a body this command accepts. If the
    deepest affordable body does not recurse, no reachable one does -- and that is a fact about the
    interpreter, said as a skip. `test_the_too_deep_refusal_is_what_the_parser_giving_up_produces`
    keeps the arm itself measured where that happens.
    """
    affordable = report.ITEM_MAX_BYTES // 2          # a body of N brackets is 2N bytes
    if not _recurses(affordable):
        pytest.skip(
            "this interpreter's json parser follows %d nesting levels without giving up, and a "
            "deeper body no longer fits the %d-byte item budget -- so no body that reaches the "
            "parser at all can raise RecursionError here" % (affordable, report.ITEM_MAX_BYTES))
    low, high = 1, affordable
    while low < high:                                # the shallowest body that still recurses
        middle = (low + high) // 2
        if _recurses(middle):
            high = middle
        else:
            low = middle + 1
    assert low == 1 or not _recurses(low - 1), (
        "the search calls %d the shallowest recursing depth and %d recurses as well, so deeper "
        "nesting is not strictly more recursion on this host and neither the bisection nor the "
        "skip above may be trusted" % (low, low - 1))
    body = "[" * low + "]" * low
    assert run_cli_with_body(state, body, "capture", "PR") == 2
    assert "nests too deeply" in capsys.readouterr().err


def test_the_too_deep_refusal_is_what_the_parser_giving_up_produces(state, capsys, monkeypatch):
    """The same arm where no affordable body can reach it -- both hosted runners, on CPython 3.14.

    The measurement above needs an interpreter that gives up inside the item budget, and skips
    where none does. The arm stays shipped code a role can land on -- a smaller budget, another
    parser, a thread with less stack -- so what it PRINTS is measured here with the whole command
    running for real and only the raiser substituted: a stand-in that IS `json` apart from `loads`,
    which raises exactly the error the arm names.
    """
    class _ParserThatGivesUp:
        def __getattr__(self, name):
            return getattr(json, name)

        def loads(self, raw):
            raise RecursionError("maximum recursion depth exceeded while decoding a JSON object")

    monkeypatch.setattr(cli, "json", _ParserThatGivesUp())
    assert run_cli_with_body(state, json.dumps(PR_FIELDS), "capture", "PR") == 2
    assert "nests too deeply" in capsys.readouterr().err


def test_a_design_ref_that_names_nothing_does_not_open_a_spawn(state):
    """`design_refs` is the II.6 gate's input and nothing resolved it.

    Measured: `capture PR … "design_refs":["DSN-9999"]` then a UI task naming that ref -> SPAWN
    ALLOWED. The field is not a binding (`PARENT_FIELDS`), so no write path ever looked; the gate
    that CLAIMS to ask whether the reference resolves is where it is asked now.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    state.update_item(pr["id"], {"design_refs": ["DSN-9999"]})
    approve(state, pr["id"], "scope")
    task = dispatch.create_task(state, {
        "product_requirement": pr["id"], "derives_from": pr["id"], "type": "ui",
        "assigned_role": "frontend-developer", "acceptance_refs": ["AC-1"],
        "required_inputs": [], "allowed_scope": ["src/"], "forbidden_scope": [],
        "expected_outputs": ["out"], "dependencies": [], "design_ref": "DSN-9999"})
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]),
                               state.read_item(pr["id"]))
    header = dispatch.parse_header(
        dispatch.dispatch_header(dispatch.create_lease(state, task["id"])))
    with pytest.raises(dispatch.DispatchError, match="exist nowhere"):
        dispatch.validate_dispatch(state, header, "frontend-developer")


def test_a_design_ref_may_not_escape_the_state_root_or_name_any_file(state, tmp_path):
    """The first fix closed the phantom-ID shape and left every PATH open.

    Measured against the running resolver before this: `README.md`, `generated/index.yaml`,
    `staging`, `.`, `..`, `../scripts/harness.py` and `../.claude/settings.json` all resolved
    True, and the last of them opened a real spawn end to end. Three conditions decide now --
    containment after `normpath`, it must be a FILE, and it must lie in a directory a freezer
    writes into (`staging.frozen_design_dirs`) -- and each row below is one of the measured cases.
    """
    frozen = os.path.join(state.root, *ACTIVE_DIRS["DSN"].split("/"))
    os.makedirs(frozen, exist_ok=True)
    with open(os.path.join(frozen, "DSN-0001.r01.html"), "w", encoding="utf-8") as handle:
        handle.write("<html/>")
    os.makedirs(os.path.join(state.root, "generated"), exist_ok=True)
    with open(os.path.join(state.root, "generated", "index.yaml"), "w", encoding="utf-8") as h:
        h.write("x")
    outside = os.path.join(os.path.dirname(state.root), ".claude")
    os.makedirs(outside, exist_ok=True)
    with open(os.path.join(outside, "settings.json"), "w", encoding="utf-8") as handle:
        handle.write("{}")

    resolves = dispatch._design_ref_resolves
    assert resolves(state, ACTIVE_DIRS["DSN"] + "/DSN-0001.r01.html")
    # THE ID FORM, on an id that really was frozen. The first cut of the resolver could not reach
    # its own id branch at all -- a bare identifier is a relative path under the root, so it left
    # through the path branch as "not a file" -- and replacing that whole branch with `return
    # False` changed no test. A phantom in the refused list cannot catch that; a real one can.
    pr = state.capture("PR", dict(PR_FIELDS))
    stage_file(state, pr["id"], "preview.html", content="<html><body>d</body></html>")
    staging.freeze_design(state, pr["id"], "DSN-0003", pr["id"], "preview.html")
    assert state.exists_anywhere("DSN-0003")
    assert resolves(state, "DSN-0003"), "the id of a really frozen design does not resolve"
    for refused in ("DSN-9999",                                   # the original phantom id
                    ACTIVE_DIRS["DSN"] + "/DSN-0002.r01.html",    # right place, no such file
                    "generated/index.yaml",                       # exists, wrong place
                    "staging", ".", "..", "../../..",             # directories / walk-ups
                    "../.claude/settings.json",                   # the measured escape
                    "../scripts/harness.py", ""):
        assert not resolves(state, refused), refused


def test_bump_kit_version_check_mode_writes_nothing(tmp_path):
    """`--check` was argv-blind: it would have STAMPED the tree it was being asked about.

    A reviewer relied on it as a read-only probe, which is exactly the way a flag like this gets
    trusted. Measured on a copy of `team-kits/` so the repo's own VERSION files are not the
    subject: with a kit file changed, `--check` reports a due bump, returns 1, and leaves every
    byte of VERSION alone; the stamping mode then writes.
    """
    import hashlib
    import shutil
    import subprocess

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    copy = tmp_path / "repo"
    shutil.copytree(root, str(copy), ignore=shutil.ignore_patterns(
        ".git", "__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache", "radar"))
    version = copy / "team-kits" / "dev-team" / "VERSION"
    marker = copy / "team-kits" / "dev-team" / "hooks" / "gate_git.py"
    marker.write_text(marker.read_text(encoding="utf-8") + "\n# probe\n", encoding="utf-8")
    before = hashlib.sha256(version.read_bytes()).hexdigest()

    checked = subprocess.run(
        [sys.executable, "-B", str(copy / "tools" / "bump_kit_version.py"), "--check"],
        capture_output=True, text=True, timeout=300)
    assert checked.returncode == 1, checked.stdout + checked.stderr
    assert "BUMP DUE" in checked.stdout, checked.stdout
    assert hashlib.sha256(version.read_bytes()).hexdigest() == before, "--check WROTE the stamp"

    stamped = subprocess.run(
        [sys.executable, "-B", str(copy / "tools" / "bump_kit_version.py")],
        capture_output=True, text=True, timeout=300)
    assert stamped.returncode == 0, stamped.stdout + stamped.stderr
    assert hashlib.sha256(version.read_bytes()).hexdigest() != before
    again = subprocess.run(
        [sys.executable, "-B", str(copy / "tools" / "bump_kit_version.py"), "--check"],
        capture_output=True, text=True, timeout=300)
    assert again.returncode == 0 and "unchanged" in again.stdout, again.stdout


def test_a_design_ref_cannot_leave_the_state_root_through_a_link(state, tmp_path):
    """`normpath` is textual and `isfile` follows links -- so containment needs `realpath`.

    Measured on Windows with `mklink /J project_memory/design/revisions/out .claude`: the entry
    `design/revisions/out/settings.json` resolved True while its real path lay outside the state
    root. This repo has paid for a symlink-blind path comparison once already
    (`hashing._bundle_files`); the fix is the same word in both places.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "settings.json").write_text("{}", encoding="utf-8")
    frozen = os.path.join(state.root, *ACTIVE_DIRS["DSN"].split("/"))
    os.makedirs(frozen, exist_ok=True)
    link = os.path.join(frozen, "out")
    try:
        os.symlink(str(outside), link, target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("this platform/user cannot create a directory link")
    assert os.path.isfile(os.path.join(link, "settings.json")), "the fixture built no live link"
    assert not dispatch._design_ref_resolves(state, ACTIVE_DIRS["DSN"] + "/out/settings.json")


def test_a_frozen_wireframe_is_a_design_reference_the_scope_hash_moves_on(state):
    """BUG-0055: `freeze_wireframe` wrote a file nothing referred to.

    `design_refs` is what the scope manifest hashes (`approvals._SCOPE_FIELDS`) and what
    `HASHED_FIELDS` bumps a revision on, and the wireframe freeze never touched it. Two measured
    consequences, E17 and E18: a SECOND freeze of the same wireframe invalidated no approval, and
    "does this UI scope name a wireframe at all" was a question with no field to read. The producer
    is what was missing -- `staging.DESIGN_REF_TYPE`'s own note said so, and said that the day the
    freeze appends, the resolver follows.

    NOT BY WIDENING `_SCOPE_FIELDS`, which is one of the two shapes the item's `expected` offers:
    that tuple is a spec decision with a migration attached -- every stored hash would change and
    every live approval would die -- and nothing of the sort is needed, because `design_refs` is
    already in it. The chosen shape is the PRODUCER, and this is the measurement of it.

    THE COUNTERWEIGHT is the freeze with no product root to write to: `derives_from` naming none
    leaves every item alone rather than inventing a reference, and the frozen file is still
    written -- a wireframe under a non-root parent is not an error.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    # PAST DRAFT FIRST: a draft is still being written, so a hashed-field change there is not a
    # revision anybody signed away -- the bump this test is about is the one that DROPS a scope
    # approval, and that needs an item that has one.
    walk_to_status(state, pr, "APPROVED")
    before = state.read_item(pr["id"])["revision"]

    stage_file(state, pr["id"], "WFR-0001.drawio.svg")
    first = staging.freeze_wireframe(state, pr["id"], "WFR-0001", "APR-0001", [pr["id"]], "t")
    updated = state.read_item(pr["id"])
    assert ACTIVE_DIRS["WFR"] in " ".join(updated["design_refs"]), updated["design_refs"]
    assert dispatch._design_ref_resolves(state, updated["design_refs"][-1]), updated["design_refs"]
    assert updated["revision"] > before, "a new design reference is a hashed-field change"
    assert first["root"]["id"] == pr["id"]

    # ...and a SECOND freeze of the same wireframe adds its own revision to the list, so what the
    # scope hash covers really moved -- E17. MEASURED, and it narrows the claim honestly: the
    # revision number does not climb a second time, because the first bump already took the item
    # out of the status a scope approval stands in, which is the effect E17 asked for.
    stage_file(state, pr["id"], "WFR-0001.drawio.svg")
    staging.freeze_wireframe(state, pr["id"], "WFR-0001", "APR-0001", [pr["id"]], "t")
    refreshed = state.read_item(pr["id"])
    assert len(refreshed["design_refs"]) == len(updated["design_refs"]) + 1, refreshed["design_refs"]
    assert refreshed["design_refs"][-1].endswith("WFR-0001.r02.drawio.svg"), refreshed["design_refs"]

    # ...and a freeze whose named root is not IN this store writes the file and touches no item.
    # Measured while writing this: the companion schema already refuses a `derives_from` that is
    # not a product id at all, so the reachable shape of "no root" is a root that does not exist.
    stage_file(state, pr["id"], "WFR-0002.drawio.svg")
    orphan = staging.freeze_wireframe(state, pr["id"], "WFR-0002", "APR-0001", ["PR-0099"], "t")
    assert orphan["root"] is None and os.path.isfile(orphan["frozen"])


def test_a_probe_failure_cannot_take_the_whole_command_surface_down(state, monkeypatch, capsys):
    """`item_derived_kinds()` runs inside `build_parser()`, so anything it lets escape kills EVERY
    command -- `doctor` included.

    The probe is `{"id": ..., "revision": ...}`, and a future item-derived kind whose manifest
    reads a real field raises `KeyError`, not `ApprovalError`. Measured before the widening:
    `KeyError: 'contract'` out of `build_parser()` and out of `main([..., "doctor"])` -- exactly
    the shape `cli.py`'s own docstring is written against ("a diagnosis command that destroys what
    it diagnoses"). A kind that cannot be built from an id alone is simply not item-derived.
    """
    original = approvals.item_subject_manifest

    def hostile(item, kind):
        if kind == "acceptance":
            raise KeyError("contract")
        return original(item, kind)

    monkeypatch.setattr(approvals, "item_subject_manifest", hostile)
    kinds = approvals.item_derived_kinds()
    assert "acceptance" not in kinds and "scope" in kinds, kinds
    assert cli.build_parser() is not None
    assert run_cli(state, "doctor") == 0
    assert '"state_version"' in capsys.readouterr().out


# -- the freeze commands: the promotion path a role can reach ------------------------------

BUG_FIELDS = {
    "title": "checkout 500s", "related_pr": "PR-0001", "observed": "500 on POST /pay",
    "expected": "200 and an order", "repro": "post /pay with a valid cart", "severity": "high",
    "acceptance_criteria": [{"id": "AC-1", "text": "no 500 on /pay"}],
}


def test_the_freeze_body_contract_is_read_off_the_operations_own_signature(state, capsys):
    """The three freeze commands validate their stdin body against `inspect.signature`, not a list.

    That is what makes the surface follow the kernel: `FREEZE_OPERATIONS` is one mapping, and the
    subcommand names, the `--help` text, the required keys, the optional keys and the type each
    key must carry are all derived from it. Renaming a parameter of `staging.freeze_architecture`
    moves every one of them together.

    All four refusals are rc 2 and not 1: the kernel never looked, so calling it a state refusal
    would tell the role its freeze was rejected when it was never attempted.
    """
    contract = cli.freeze_parameters(staging.freeze_architecture)
    assert contract["derives_from"] == (True, list)
    assert contract["packaging"] == (False, dict)
    assert "state" not in contract, "the CLI holds the state; a body may never carry it"

    stage_file(state, "PR-0001", "ARC-0001.drawio.svg")
    body = {"staging_key": "PR-0001", "arc_id": "ARC-0001", "title": "t", "scope": "s",
            "derives_from": ["PR-0001"]}

    missing = dict(body)
    missing.pop("scope")
    assert run_cli_with_body(state, json.dumps(missing), "freeze-architecture") == 2
    assert "is missing scope" in capsys.readouterr().err

    unknown = dict(body, packagng={"method": "docker"})
    assert run_cli_with_body(state, json.dumps(unknown), "freeze-architecture") == 2
    assert "no parameter for" in capsys.readouterr().err

    mistyped = dict(body, derives_from="PR-0001")
    assert run_cli_with_body(state, json.dumps(mistyped), "freeze-architecture") == 2
    err = capsys.readouterr().err
    assert "derives_from" in err and "list" in err

    smuggled = dict(body, state="somewhere else")
    assert run_cli_with_body(state, json.dumps(smuggled), "freeze-architecture") == 2
    assert "no parameter for" in capsys.readouterr().err


def test_the_freeze_commands_write_the_state_no_other_producer_can(state, capsys):
    """The measured hole this closes: `capture` refuses `ARC`, `project_memory/**` is kernel-only
    for tool writes, and `staging.freeze_*` had no caller a role could reach -- so an ARC item, a
    frozen wireframe and a `design_refs` entry were all unreachable in a shipped project.

    The printed path is STATE-RELATIVE on purpose: the absolute one names `project_memory`, and
    `gate_write_scope` refuses a write-capable pipeline whose command line does.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    stage_file(state, pr["id"], "ARC-0001.drawio.svg")
    assert run_cli_with_body(state, json.dumps({
        "staging_key": pr["id"], "arc_id": "ARC-0001", "title": "Deployment",
        "scope": "whole system", "derives_from": [pr["id"]],
        "packaging": {"method": "docker"}}), "freeze-architecture") == 0
    printed = capsys.readouterr().out.strip()
    # FIRST line, because the freeze also reports what it did to the proposal area (BUG-0074);
    # the path a role pastes onward is still the whole of that first line.
    assert printed.splitlines()[0] == "architecture/revisions/ARC-0001.r01.drawio.svg", printed
    assert "project_memory" not in printed
    companion = os.path.join(state.root, "architecture", "active", "ARC-0001.yaml")
    with open(companion, encoding="utf-8") as handle:
        assert yaml.safe_load(handle)["packaging"] == {"method": "docker"}

    stage_file(state, pr["id"], "WFR-0001.drawio.svg")
    apr = approve(state, pr["id"])
    assert run_cli_with_body(state, json.dumps({
        "staging_key": pr["id"], "wfr_id": "WFR-0001", "scope_apr_ref": apr["id"],
        "derives_from": [pr["id"]], "title": "Checkout screen"}), "freeze-wireframe") == 0
    assert (capsys.readouterr().out.strip().splitlines()[0]
            == "design/wireframes/WFR-0001.r01.drawio.svg")


def test_freeze_design_is_the_only_thing_that_can_fill_design_refs(state, capsys):
    """Minimum-keep 9 end to end: freeze -> `design_refs` -> the spawn tooth that reads it.

    `dispatch.validate_dispatch` -- the one function `gate_dispatch` calls at a spawn -- refuses
    a UI task whose `design_ref` is not one of the root's
    CONFIRMED refs -- but only once that list is non-empty, and `staging.freeze_design` is the only
    function in the harness that appends to it. Without a command for it the rule could not fire in
    any shipped project, so it existed as prose. Both directions are measured here: the wrong ref
    is refused, the frozen one dispatches.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    assert not state.read_item(pr["id"]).get("design_refs")
    stage_file(state, pr["id"], "preview.html", content="<html><body>x</body></html>")
    assert run_cli_with_body(state, json.dumps({
        "staging_key": pr["id"], "dsn_id": "DSN-0001", "root_id": pr["id"],
        "source_name": "preview.html"}), "freeze-design") == 0
    out = capsys.readouterr().out
    assert "design/revisions/DSN-0001.r01.html" in out
    assert "PR-0001 design_refs: design/revisions/DSN-0001.r01.html" in out
    frozen = state.read_item(pr["id"])["design_refs"]
    assert frozen == ["design/revisions/DSN-0001.r01.html"]

    walk_to_status(state, state.read_item(pr["id"]), "IN_DELIVERY")
    order = {"product_requirement": pr["id"], "derives_from": pr["id"], "type": "ui",
             "assigned_role": "frontend-developer", "acceptance_refs": ["AC-1"],
             "allowed_scope": ["frontend/"], "forbidden_scope": [], "required_inputs": [],
             "expected_outputs": ["out"], "dependencies": []}
    # DISJOINT SCOPES, because both leases run at once here and the kernel now refuses a
    # second dispatch onto a file a running order owns (DEC-0062 (1)). The scope is
    # incidental to what this test measures -- the design_ref is the subject.
    wrong = dispatch.create_task(state, dict(order, design_ref="DSN-9999",
                                            allowed_scope=["frontend/wrong/"]))
    state.transition(wrong["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(wrong["id"]),
                               state.read_item(pr["id"]))
    header = json.loads(dispatch.dispatch_header(
        dispatch.create_lease(state, wrong["id"])).split(" ", 1)[1])
    with pytest.raises(dispatch.DispatchError) as refused:
        dispatch.validate_dispatch(state, header, order["assigned_role"])
    assert "design_ref" in str(refused.value)

    good = dispatch.create_task(state, dict(order, design_ref=frozen[0],
                                           allowed_scope=["frontend/good/"]))
    state.transition(good["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(good["id"]),
                               state.read_item(pr["id"]))
    header = json.loads(dispatch.dispatch_header(
        dispatch.create_lease(state, good["id"])).split(" ", 1)[1])
    assert dispatch.validate_dispatch(state, header, order["assigned_role"])


def test_a_scalar_design_ref_survives_the_freeze_as_one_reference(state, capsys):
    """BUG-0038 / H43: the one reader of this class that WRITES its misreading into the state.

    MEASURED BEFORE THE FIX, over the shipped commands and nothing else: `capture PR` with
    `design_refs` as a bare string is accepted (no contract declares the field, and `capture` takes
    a body's extra keys unchanged), and `freeze-design` then ran `list(root.get("design_refs") or [])`
    and handed the result to `_update_item_locked` -- 35 entries in the ACTIVE PR, 34 letters plus
    the new reference, revision unchanged at 1, and `validate` said "0 error(s), 0 warning(s)". The
    confirmation line read `PR-0001 design_refs: d, e, s, i, g, n, /, ...` and the II.6a tooth then
    refused a UI task against the design that had just been frozen ("references that exist nowhere:
    d, e, s, ...").

    All three ends are here, because they are three different readers: the CANONICAL item
    (`staging.py`), the printed line (`cli.py`, which the field-read derivation in
    `test_backlog_types` deliberately cannot see -- it reads the freeze's RETURN value) and the
    spawn (`dispatch.py`). The captured scalar names the revision this freeze produces, so the
    repaired list carries that path TWICE; two entries and thirty-five are the measurement, the
    duplicate is not de-duplicated by anything and is not claimed to be.
    """
    reference = "design/revisions/DSN-0001.r01.html"
    pr = state.capture("PR", dict(PR_FIELDS, design_refs=reference))
    assert state.read_item(pr["id"])["design_refs"] == reference, "capture no longer takes the scalar"
    stage_file(state, pr["id"], "preview.html", content="<html><body>x</body></html>")
    assert run_cli_with_body(state, json.dumps({
        "staging_key": pr["id"], "dsn_id": "DSN-0001", "root_id": pr["id"],
        "source_name": "preview.html"}), "freeze-design") == 0

    refs = state.read_item(pr["id"])["design_refs"]
    assert refs == [reference, reference], refs
    assert run_cli(state, "validate") == 0
    printed = capsys.readouterr().out
    assert "PR-0001 design_refs: %s, %s" % (reference, reference) in printed
    assert "design_refs: d, e, s" not in printed

    walk_to_status(state, state.read_item(pr["id"]), "IN_DELIVERY")
    task = dispatch.create_task(state, {
        "product_requirement": pr["id"], "derives_from": pr["id"], "type": "ui",
        "assigned_role": "frontend-developer", "acceptance_refs": ["AC-1"],
        "allowed_scope": ["frontend/"], "forbidden_scope": [], "required_inputs": [],
        "expected_outputs": ["out"], "dependencies": [], "design_ref": reference})
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]),
                               state.read_item(pr["id"]))
    header = json.loads(dispatch.dispatch_header(
        dispatch.create_lease(state, task["id"])).split(" ", 1)[1])
    assert dispatch.validate_dispatch(state, header, "frontend-developer")


def test_a_bug_cannot_be_verified_without_the_regression_evidence(state, capsys):
    """Minimum-keep 8. The constitution says the regression test's Evidence is what moves a bug
    from FIXED to VERIFIED; measured before this, `transition BUG-0001 VERIFIED` ran with no
    Evidence in the project at all and `validate` then reported 0 errors.

    Four steps, because the rule is about a CURRENT PASSING TEST verdict and each of the three
    near-misses is a way of not being one: nothing at all, a failing test, and a passing review
    (which judges the code, not the repro).
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    bug = state.capture("BUG", dict(BUG_FIELDS, related_pr=pr["id"]))
    walk_to_status(state, bug, "FIXED")

    with pytest.raises(TransitionError) as refused:
        state.transition(bug["id"], "VERIFIED")
    message = str(refused.value)
    assert "'test' Evidence that PASSES" in message and "there is none" in message
    assert "--related %s" % bug["id"] in message, "the remedy must be a line the role can type"

    assert run_cli(state, "evidence", "--kind", "test", "--result", "fail",
                   "--related", bug["id"], "--summary", "red",
                   "--artifact-ref", "staging/x/run.log", "--run-command", "pytest -q", "--run-scope", "selection") == 0
    capsys.readouterr()
    with pytest.raises(TransitionError) as still:
        state.transition(bug["id"], "VERIFIED")
    assert "verdict is 'fail'" in str(still.value)

    assert run_cli(state, "evidence", "--kind", "review", "--result", "pass",
                   "--related", bug["id"], "--summary", "looks fine",
                   "--artifact-ref", "staging/x/review.md", "--run-command", "pytest -q", "--run-scope", "selection") == 0
    capsys.readouterr()
    with pytest.raises(TransitionError):
        state.transition(bug["id"], "VERIFIED")

    assert run_cli(state, "evidence", "--kind", "test", "--result", "pass",
                   "--related", bug["id"], "--summary", "regression green",
                   "--artifact-ref", "staging/x/run2.log", "--run-command", "pytest -q", "--run-scope", "selection") == 0
    capsys.readouterr()
    assert state.transition(bug["id"], "VERIFIED")["status"] == "VERIFIED"


def _tree_state(path):
    """Every file under `path`, as {relative path: sha256} — the canary a freeze must not touch."""
    import hashlib
    state = {}
    for current, _dirs, files in os.walk(path):
        for name in sorted(files):
            full = os.path.join(current, name)
            try:
                with open(full, "rb") as handle:
                    state[os.path.relpath(full, path)] = hashlib.sha256(handle.read()).hexdigest()
            except OSError:
                state[os.path.relpath(full, path)] = "<unreadable>"
    return state


CANARY = "OUTSIDE-CANARY-8f2a"
ARTEFACTS = ("WFR-0001.drawio.svg", "ARC-0001.drawio.svg")
VALID_FREEZE_BODY = {
    "staging_key": "PR-0001", "wfr_id": "WFR-0001", "arc_id": "ARC-0001", "dsn_id": "DSN-0001",
    "root_id": "PR-0001", "subject_id": "PR-0001", "source_name": "preview.html",
    "title": "t", "scope": "s",
    "derives_from": ["PR-0001"], "scope_apr_ref": None, "approval_ref": None,
}


def _freeze_fixture(work, sibling):
    """A state root under `work`, with the artefacts a freeze looks for placed BOTH inside the
    staging key and at every place a traversal would land.

    That second placement is what makes this an exploit reproduction rather than a spelling test:
    without a source file at the traversal target the operation stops at `FileNotFoundError`, the
    canary survives, and the test would pass over the unfixed kernel. Only the copies OUTSIDE the
    state root carry `CANARY`, so "did something from outside get in" is decidable.
    """
    root = os.path.join(str(work), "project_memory")
    os.makedirs(os.path.join(root, "staging", "PR-0001"), exist_ok=True)
    # the tray `freeze_report` files into: it is shipped by the research kit, and the freeze
    # refuses outright where it is absent, so a fixture without it would take that command out of
    # both parametrisations below without saying so
    os.makedirs(os.path.join(root, staging.REPORTS_DIRNAME), exist_ok=True)
    state = ProjectState(root)
    state.capture("PR", dict(PR_FIELDS))
    for directory, preview in ((os.path.join(root, "staging", "PR-0001"), "<html>inside</html>"),
                               (root, "<html>inside</html>"),
                               (str(work), "<html>%s</html>" % CANARY),
                               (sibling, "<html>%s</html>" % CANARY)):
        os.makedirs(directory, exist_ok=True)
        for name in ARTEFACTS:
            with open(os.path.join(directory, name), "w", encoding="utf-8") as handle:
                handle.write(DRAWIO_SVG)
        with open(os.path.join(directory, "preview.html"), "w", encoding="utf-8") as handle:
            handle.write(preview)
    with open(os.path.join(str(work), "keepme.txt"), "w", encoding="utf-8") as handle:
        handle.write(CANARY)
    return state


def _outside_state(work):
    """Everything under the repo that is NOT canonical state — what a freeze may never touch."""
    return {key: value for key, value in _tree_state(str(work)).items()
            if not key.replace("\\", "/").startswith("project_memory/")}


# THE ESCAPE SHAPES, in one place because two batteries below feed them to two different callers
# of the SAME chokepoint. A shape added here is asked of both on the day it is written; two tuples
# would have been the usual drift, with the newer caller carrying the shorter list.
ESCAPE_SHAPES = ("..", "../..", r"..\..", "sub/deep", "../../../preview.html")


def _contained_child_callers():
    """Every kernel function that names `staging.contained_child`, off the kernel's own AST.

    THE FLOOR UNDER BOTH BATTERIES BELOW, and the reason it is a ONE-HOP scan rather than a
    call-graph walk: `contained_child` IS the chokepoint, so a caller is by definition the function
    that names it. A helper three hops away does not compose a path from a role's string; the
    function holding this call does.

    Parsed rather than grepped for the usual reason — the name appears in prose in this very file.
    """
    import ast
    callers = set()

    def walk(node, owner, module):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(child, child.name, module)
                continue
            if isinstance(child, ast.Call):
                func = child.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
                if name == "contained_child":
                    callers.add((module, owner))
            walk(child, owner, module)

    directory = os.path.dirname(os.path.abspath(staging.__file__))
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(directory, name)
        with io.open(path, encoding="utf-8") as handle:
            walk(ast.parse(handle.read(), path), "<module>", name[:-3])
    return callers


def test_every_caller_that_composes_a_staged_path_has_an_escape_battery():
    """A new caller of the containment chokepoint may not ship without one of the batteries below.

    THE DEFECT THIS EXISTS FOR was measured by the verifier of TSK-0073: `submit-result --from`
    claimed `staging.contained_child` in its own docstring, the shipped code was right (all six
    escape shapes rc 1), and NOTHING went red when the call was mutated to a bare `os.path.join` —
    63 tests passed and `--from ../../../outside.json` submitted. A protection claim with no
    red-capable test is the failure mode this repo is built against, one layer out from the code
    being correct.

    WHAT IS COVERED AND HOW: `staging_dir` is reached by every caller that names a staging KEY and
    is exercised through both batteries; the freeze operations are covered per PARAMETER by the
    derived battery below; `_submitted_envelope` by the one after it. A caller appearing here that
    is in neither list is red, which is the whole point.
    """
    covered = {("staging", "staging_dir"), ("staging", "freeze_design"),
               ("staging", "freeze_report"), ("cli", "_submitted_envelope"),
               ("documents", "proposal_path")}
    found = _contained_child_callers()
    assert found, "the derivation found no caller at all — staging.py's shape changed"
    assert found == covered, (
        "these functions compose a path through `staging.contained_child` and no escape battery in "
        "this module feeds them: %s (gone: %s)" % (sorted(found - covered), sorted(covered - found)))


# The ABSOLUTE shape cannot be a module constant: it names a directory the fixture creates per
# run. Both batteries append it themselves, which is the asymmetry this placeholder removes — the
# freeze one appended a real path and this one appended nothing, so the drive-letter branch of
# `contained_child` was reached by only one of the two callers.
ABSOLUTE_ESCAPE = "<absolute-sibling>"


@pytest.mark.parametrize("escape", ESCAPE_SHAPES + (ABSOLUTE_ESCAPE, "preview.html"))
def test_no_staged_envelope_name_can_reach_outside_the_tasks_own_staging(tmp_path, escape, capsys):
    """`submit-result --from <NAME>` is a NAME, and this is what makes that sentence checkable.

    The same four universal invariants the freeze battery asserts, plus the one this caller adds:
    the task must NOT have moved. An envelope read from outside its task's own staging directory
    would be a result the specialist did not stage, booked in under a task it was not written for.

    MEASURED RED with `contained_child` replaced by a bare `os.path.join` in a clone outside this
    repo: `--from ../../../outside.json` reaches the file and the task goes to SUBMITTED.
    """
    sibling = os.path.join(str(tmp_path), "sibling")
    work = tmp_path / ("from-%s" % abs(hash(escape)))
    os.makedirs(str(work), exist_ok=True)
    state = _freeze_fixture(work, sibling)
    if escape == ABSOLUTE_ESCAPE:
        escape = os.path.join(sibling, "outside.json")
    _pr, task = _approved_ready_task(state)
    header = dispatch.parse_header(_dispatch_line(state, task["id"], capsys))
    dispatch.validate_dispatch(state, header, "backend-developer", claim=True)
    dispatch.spawn_outcome(state, task["id"], True)
    # a VALID envelope at every traversal target, so the refusal cannot be "no such file" — that
    # is the same trap `_freeze_fixture` documents for the canary copies.
    envelope = {"task_id": task["id"], "role": "backend-developer",
                "status_proposal": "SUBMITTED", "summary": CANARY, "outputs": [],
                "evidence": [], "scope_touched": [], "followups": []}
    for directory in (str(work), sibling, os.path.dirname(state.root), state.root,
                      os.path.join(state.root, "staging")):
        os.makedirs(directory, exist_ok=True)
        for name in ("preview.html", "outside.json"):
            with open(os.path.join(directory, name), "w", encoding="utf-8") as handle:
                json.dump(envelope, handle)
    before, before_sibling = _outside_state(work), _tree_state(sibling)

    run_cli(state, "submit-result", "--task-id", task["id"], "--from", escape)

    where = "--from %r" % escape
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS", (
        "%s booked in an envelope from outside the task's own staging directory" % where)
    assert _outside_state(work) == before, "%s changed the repo outside the state dir" % where
    assert _tree_state(sibling) == before_sibling, "%s changed a sibling directory" % where
    assert os.path.isfile(state.active_path("PR-0001")), "%s destroyed canonical state" % where
    stored = os.path.join(state.root, "tasks", "results", task["id"] + ".envelope.yaml")
    assert not os.path.exists(stored), "%s stored an envelope from outside" % where


JUNCTION_ESCAPE = "<junction-key>"


def _junction(link, target):
    """A directory junction, or None where this host will not make one.

    `mklink /J` rather than `os.symlink`: a junction needs no privilege on Windows, which is what
    makes it the escape shape a role could really create. Output is decoded with `errors="replace"`
    for `presets.CHILD_TEXT`'s measured reason -- this shell answers in the console codepage.
    """
    if os.name != "nt":
        return None
    result = subprocess.run(["cmd", "/c", "mklink", "/J", link, target], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=60)
    return link if result.returncode == 0 and os.path.isdir(link) else None


@pytest.mark.parametrize("escape", ESCAPE_SHAPES + (ABSOLUTE_ESCAPE, JUNCTION_ESCAPE,
                                                    "master_data.yaml"))
def test_no_proposal_path_can_reach_outside_the_tasks_own_staging(tmp_path, escape, capsys):
    """`apply-proposal --proposal` names a file in the task's proposal area, and only there.

    THE THIRD CALLER of the containment chokepoint (BUG-0071), measured with the same battery as
    the other two rather than trusted: this one READS a file and copies its bytes over a document
    of the project, so an escaping value would file content from anywhere on the disk into a kit
    document, under an approval whose question named a staging path. A valid proposal lies at every
    traversal target, so no refusal here can be "no such file".

    THE REFUSAL IS READ, not just the exit code, and that is what makes the battery red-capable.
    Nothing here mints an approval, so a shape that walked straight past the containment would
    still be stopped by the approval check and every "did the tree move" assertion would stay
    green -- the shape of a test that cannot fail. So each escape must be refused AS A PATH, and
    the last case, a real staged proposal, must be refused as an APPROVAL: that is the floor under
    the other seven.

    THE JUNCTION IS THE CASE `staging.contained_child` ASKED FOR. Its own docstring records that
    each half of the guard alone catches every shape in `ESCAPE_SHAPES`, that only a link needs the
    realpath half, and that no escape list contained one -- "the fix is a junction in the fixture".
    Here it is: a staging KEY that is one legal segment and resolves into a sibling directory.
    """
    sibling = os.path.join(str(tmp_path), "sibling")
    work = tmp_path / ("proposal-%s" % abs(hash(escape)))
    os.makedirs(str(work), exist_ok=True)
    state = _freeze_fixture(work, sibling)
    if escape == ABSOLUTE_ESCAPE:
        escape = os.path.join(sibling, "master_data.yaml")
    # a valid proposal at every traversal target EXCEPT the document's own place -- writing there
    # would be this fixture clobbering the very file the assertion reads
    for directory in (str(work), sibling, os.path.dirname(state.root),
                      os.path.join(state.root, "staging"),
                      os.path.join(state.root, "staging", "PR-0001")):
        os.makedirs(directory, exist_ok=True)
        for name in ("master_data.yaml", "preview.html"):
            with open(os.path.join(directory, name), "w", encoding="utf-8", newline="") as handle:
                handle.write("# the document\ncategories: [%s]\n" % CANARY)
    document = os.path.join(state.root, "master_data.yaml")
    with open(document, "w", encoding="utf-8", newline="") as handle:
        handle.write("# the document\ncategories: []\n")
    original = _tree_state(state.root)[os.path.basename(document)]

    staged = escape
    if escape == JUNCTION_ESCAPE:
        link = _junction(os.path.join(state.root, "staging", "outside"), sibling)
        if link is None:
            pytest.skip("this host does not create directory junctions")
        staged = "staging/outside/master_data.yaml"
    elif escape == "master_data.yaml":
        staged = "staging/PR-0001/master_data.yaml"
    before, before_sibling = _outside_state(work), _tree_state(sibling)
    capsys.readouterr()

    run_cli(state, "apply-proposal", "--kit-document", "master_data.yaml",
            "--proposal", staged, "--reason", "battery")

    where = "--proposal %r" % staged
    refused = capsys.readouterr().err
    if escape == "master_data.yaml":
        assert "no live user approval" in refused, (
            "the floor is gone: a real staged proposal must reach the approval check, or every "
            "assertion above it is vacuous -- %s said %r" % (where, refused))
    else:
        assert "no live user approval" not in refused and refused.strip(), (
            "%s was refused by the approval check rather than as a path, so this shape never "
            "reached the containment: %r" % (where, refused))
    assert _tree_state(state.root)[os.path.basename(document)] == original, (
        "%s wrote into the kit document" % where)
    assert _outside_state(work) == before, "%s changed the repo outside the state dir" % where
    assert _tree_state(sibling) == before_sibling, "%s changed a sibling directory" % where
    assert os.path.isfile(state.active_path("PR-0001")), "%s destroyed canonical state" % where


@pytest.mark.parametrize("command", sorted(cli.FREEZE_COMMANDS))
def test_freezing_one_artifact_leaves_the_other_staged_files_alone(tmp_path, command, capsys):
    """BUG-0074, and it is measured for ALL THREE freezes rather than for the one that bit.

    THE LOSS, live 2026-08-29 in the user's real dev project: freezing a wireframe emptied
    `staging/TSK-0001/` whole -- WFR-0002/0003/0004, still unfrozen work, went with the one being
    frozen. They were recoverable only because an unrelated chore commit happened to carry them.
    `staging/<key>/` is the ONE tool-writable area under the state directory, so what lies there is
    by definition work no other route holds.

    That the three commands share `clear_staging` was the FINDING and not the assumption, which is
    why the parametrisation is over `cli.FREEZE_COMMANDS` -- the mapping the surface is derived
    from -- and not over the one command that was reported. A fourth freeze is measured on the day
    it is written.

    The bystanders are compared by CONTENT HASH (`_tree_state`) and not merely by existence,
    because "a file of that name is there" is what a delete-then-rewrite would also satisfy.
    """
    sibling = os.path.join(str(tmp_path), "sibling")
    work = tmp_path / ("survive-" + command)
    os.makedirs(str(work), exist_ok=True)
    state = _freeze_fixture(work, sibling)
    contract = cli.freeze_parameters(cli.FREEZE_COMMANDS[command])
    body = {key: value for key, value in VALID_FREEZE_BODY.items() if key in contract}

    staging_key = os.path.join(state.root, "staging", "PR-0001")
    bystanders = {"WFR-0002.drawio.svg": DRAWIO_SVG, "WFR-0003.drawio.svg": DRAWIO_SVG,
                  "notes.md": "# unfrozen thinking\n"}
    for name, content in bystanders.items():
        with open(os.path.join(staging_key, name), "w", encoding="utf-8") as handle:
            handle.write(content)
    before = _tree_state(staging_key)

    assert run_cli_with_body(state, json.dumps(body), command) == 0, capsys.readouterr().err
    printed = capsys.readouterr().out

    assert os.path.isdir(staging_key), (
        "%s removed the task's whole staging directory" % command)
    after = _tree_state(staging_key)
    for name in bystanders:
        assert name in after, "%s deleted the unfrozen %s" % (command, name)
        assert after[name] == before[name], "%s rewrote the unfrozen %s" % (command, name)
    # EXACTLY ONE file left the workspace, and it is the one the freeze says it consumed. Derived
    # from the directory rather than from the body's key names: which parameter names the source
    # differs per command (`source_name` for design, an id for the other two), and a per-command
    # branch here would be the enumeration this parametrisation exists to avoid.
    gone = sorted(set(before) - set(after))
    said = [line.split()[1] for line in printed.splitlines() if line.startswith("staging: ")]
    assert len(gone) == 1 and said == gone, (
        "%s consumed %s and reported %s" % (command, gone, said))
    assert "still staged" in printed, printed
    for name in bystanders:
        assert name in printed, "the freeze does not name what it left behind: %s" % printed


def test_no_freeze_command_empties_the_tasks_staging_area():
    """No freeze may reach the recursive delete again -- read off the kernel's own AST.

    The sibling of the behavioural test above, and it exists because that one can only measure the
    files a fixture happens to place: this reads WHICH function each freeze calls, so a freeze that
    starts emptying the directory again is caught even where a test's fixture staged nothing else.
    `clear_staging(..., mode="promoted")` is `shutil.rmtree` on the task's workspace; the lifecycle
    step itself stays reachable for a caller that means the whole directory (spec II.4).
    """
    import ast

    with io.open(staging.__file__, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=staging.__file__)
    freezers = {operation.__name__ for operation in cli.FREEZE_COMMANDS.values()}
    assert freezers, "the freeze surface is empty -- the reader stopped matching"
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in freezers:
            continue
        for call in ast.walk(node):
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                    and call.func.id == "clear_staging"):
                offenders.append(node.name)
    assert not offenders, (
        "these freeze operations empty the task's whole staging area again (BUG-0074): %s"
        % sorted(set(offenders)))


@pytest.mark.parametrize("command", sorted(cli.FREEZE_COMMANDS))
def test_no_freeze_parameter_can_reach_outside_the_state_root(tmp_path, command):
    """THE MECHANISM, not two parameter names: a freeze body arrives on STDIN, so no hook sees it —
    `gate_write_scope` reads command LINES — and every freeze ends in
    `clear_staging(..., mode="promoted")`, which is `shutil.rmtree(<root>/staging/<key>)`.

    Measured before `staging.contained_child`: `{"staging_key": "../.."}` on stdin DELETED THE
    WHOLE REPOSITORY (`.git`, `.claude`, `scripts`, everything), `".."` deleted the whole state
    directory, and `freeze-design` with an absolute `source_name` copied any file on the disk into
    `design/revisions/` and pointed the root's `design_refs` at it — all three command lines
    passing all eight registered shell gates.

    THE PARAMETER SET IS DERIVED from `cli.freeze_parameters`, so the next freeze parameter that
    happens to reach a path join is covered on the day it is written. Every `str` parameter of the
    command is substituted in turn with every escape shape, and FOUR universal invariants are
    asserted, none of which needs to know which parameter is path-bearing:
      * the repo outside the state directory is unchanged — same files, same hashes;
      * a sibling directory outside the repo is unchanged;
      * the root ITEM still exists (this is what `staging_key: ".."` destroyed: the whole state
        directory, which the first two checks cannot see because they look past it);
      * nothing from outside got IN — the canary content appears in no file under the state root,
        which is the `source_name` case a deletion check cannot see.
    """
    sibling = os.path.join(str(tmp_path), "sibling")
    contract = cli.freeze_parameters(cli.FREEZE_COMMANDS[command])
    for name, (_required, declared) in sorted(contract.items()):
        if declared is not str:
            continue
        for escape in ESCAPE_SHAPES + (os.path.join(sibling, "preview.html"),):
            work = tmp_path / ("%s-%s-%s" % (command, name, abs(hash(escape))))
            os.makedirs(str(work), exist_ok=True)
            state = _freeze_fixture(work, sibling)
            before, before_sibling = _outside_state(work), _tree_state(sibling)

            body = {key: value for key, value in VALID_FREEZE_BODY.items() if key in contract}
            body[name] = escape
            run_cli_with_body(state, json.dumps(body), command)

            where = "%s %s=%r" % (command, name, escape)
            assert _outside_state(work) == before, "%s changed the repo outside the state dir" % where
            assert _tree_state(sibling) == before_sibling, "%s changed a sibling directory" % where
            assert os.path.isfile(state.active_path("PR-0001")), (
                "%s destroyed canonical state" % where)
            for current, _dirs, files in os.walk(state.root):
                for entry in files:
                    with open(os.path.join(current, entry), encoding="utf-8",
                              errors="ignore") as handle:
                        assert CANARY not in handle.read(), (
                            "%s pulled a file from outside the state root into %s" % (where, entry))


def test_the_freeze_refusal_names_the_parameter_a_role_typed(state, capsys):
    """The refusal has to be actionable: a role that typed `staging_key: "../.."` needs to read
    which field it was, not `[Errno 2]`."""
    stage_file(state, "PR-0001", "WFR-0001.drawio.svg")
    body = {"staging_key": "../..", "wfr_id": "WFR-0001", "scope_apr_ref": None,
            "derives_from": ["PR-0001"], "title": "t"}
    assert run_cli_with_body(state, json.dumps(body), "freeze-wireframe") == 1
    err = capsys.readouterr().err
    assert "staging key" in err and "single name" in err


def test_a_nullable_companion_field_may_be_sent_as_null(state, capsys):
    """`freeze_wireframe` takes `scope_apr_ref` as a REQUIRED parameter whose companion field is
    `nullable: true` — so "no scope approval yet" must have a spelling. The body check is about
    SHAPE (a list stays a list); nullability is the strict companion schema's question, and the
    first cut of `_freeze_body` refused this legitimate body."""
    pr = state.capture("PR", dict(PR_FIELDS))
    stage_file(state, pr["id"], "WFR-0001.drawio.svg")
    assert run_cli_with_body(state, json.dumps({
        "staging_key": pr["id"], "wfr_id": "WFR-0001", "scope_apr_ref": None,
        "derives_from": [pr["id"]], "title": "Checkout"}), "freeze-wireframe") == 0
    assert "design/wireframes/WFR-0001.r01.drawio.svg" in capsys.readouterr().out
