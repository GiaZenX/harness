"""Tests for kernel schema validation (HARNESS_V2_SPEC.md II.5 contracts)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "team-kits"))

from kernel.schemas import SchemaError, load_schema, validate  # noqa: E402


def make_envelope(**overrides):
    envelope = {
        "task_id": "TSK-0042",
        "role": "backend-developer",
        "status_proposal": "SUBMITTED",
        "summary": "implemented the API endpoint per SR-0007",
        "outputs": ["src/api/checkout.py"],
        "evidence": ["evidence/EVD-0003.yaml"],
        "scope_touched": ["src/api/checkout.py", "tests/test_checkout.py"],
        "followups": [],
    }
    envelope.update(overrides)
    return envelope


def make_brief(**overrides):
    brief = {
        "kit": "dev-team",
        "kit_version": "2026.07.18-3",
        "enforcement_mode": "audited",
        "generated_at": "2026-07-24T12:00:00",
        "active_roots": [
            {"id": "PR-0001", "title": "Checkout", "status": "IN_DELIVERY", "next_step": "QA"}
        ],
        "active_tasks": [{"id": "TSK-0042", "status": "IN_PROGRESS", "assigned_role": "backend-developer"}],
        "open_approvals": [{"request_id": "req-1", "kind": "scope", "item": "PR-0002"}],
        "staging_pointers": ["staging/PR-0002/"],
        "standing_decisions": [{"id": "DEC-0001", "title": "Local-only", "decision": "SQLite, no cloud"}],
        # the shape `report.lease_distribution` writes (DEC-0092 (4)); required, like every section
        "lease_distribution": {"window": 10, "orders": 0, "goals_with_builders": 0,
                               "counted_provider": [], "by_provider": {},
                               "builders_per_goal": {}, "rungs": {}, "efforts": {},
                               "runs_to_hand_back_per_rung": {}, "runs_to_hand_back_per_effort": {},
                               "line": "no lease recorded in this project yet -- no habit to show"},
        "budget_status": {"memory_md": "ok"},
    }
    brief.update(overrides)
    return brief


# -- result envelope -----------------------------------------------------------

def test_valid_envelope_passes():
    validate(make_envelope(), "result_envelope")


def test_envelope_missing_field_fails():
    envelope = make_envelope()
    del envelope["evidence"]
    with pytest.raises(SchemaError, match="evidence"):
        validate(envelope, "result_envelope")


def test_envelope_unknown_field_fails_strict():
    with pytest.raises(SchemaError, match="unknown field"):
        validate(make_envelope(raw_log="... 200 lines ..."), "result_envelope")


def test_envelope_bad_status_enum_fails():
    with pytest.raises(SchemaError, match="enum"):
        validate(make_envelope(status_proposal="DONE"), "result_envelope")


def test_envelope_bad_task_id_pattern_fails():
    with pytest.raises(SchemaError, match="pattern"):
        validate(make_envelope(task_id="TSK-42"), "result_envelope")


def test_envelope_size_budget_enforced():
    with pytest.raises(SchemaError, match="budget 4096"):
        validate(make_envelope(summary="x" * 1999, outputs=["y" * 3000]), "result_envelope")


def test_envelope_list_item_type_checked():
    with pytest.raises(SchemaError, match="outputs"):
        validate(make_envelope(outputs=[42]), "result_envelope")


def test_envelope_task_id_trailing_newline_fails():
    """Fable-Check 6/BUG-2: `$` matches before a trailing newline -- fullmatch must not."""
    with pytest.raises(SchemaError, match="pattern"):
        validate(make_envelope(task_id="TSK-0042\n"), "result_envelope")


# -- session brief -------------------------------------------------------------

def test_valid_brief_passes():
    validate(make_brief(), "session_brief")


def test_the_briefs_distribution_sample_is_the_shape_the_producer_writes(tmp_path):
    """The `lease_distribution` sample in `make_brief` above carries the keys
    `report.lease_distribution` really writes -- asked of the producer, never typed twice.

    WHY IT MATTERS HERE AND NOT ONLY IN test_report.py: the schema declares this section as a bare
    `dict`, so a sample that drifted from the producer would keep validating and this module would
    go on asserting a shape nothing writes. RED WITHOUT the DEC-0097 (4) keys in the sample
    (`efforts`, `runs_to_hand_back_per_effort`): the producer names two keys the sample does not.
    """
    from kernel import report
    from kernel.state import ProjectState

    empty = ProjectState(str(tmp_path / "project_memory"))
    assert set(make_brief()["lease_distribution"]) == set(report.lease_distribution(empty))


def test_brief_enforcement_enum():
    with pytest.raises(SchemaError, match="enum"):
        validate(make_brief(enforcement_mode="hopeful"), "session_brief")


def test_brief_item_required_keys():
    with pytest.raises(SchemaError, match="next_step"):
        validate(
            make_brief(active_roots=[{"id": "PR-0001", "title": "x", "status": "DRAFT"}]),
            "session_brief",
        )


def test_brief_size_budget():
    with pytest.raises(SchemaError, match="budget 25600"):
        validate(
            make_brief(staging_pointers=["p" * 100] * 300),
            "session_brief",
        )


def test_brief_decision_item_required_keys():
    """A standing-decision row owes id, title AND decision -- an id alone is the loss BUG-0005 is
    about (the PM would read a pointer with no content)."""
    with pytest.raises(SchemaError, match="decision"):
        validate(
            make_brief(standing_decisions=[{"id": "DEC-0001", "title": "x"}]),
            "session_brief",
        )


# -- ARC / WFR companions ------------------------------------------------------

def make_arc(**overrides):
    arc = {
        "id": "ARC-0001",
        "title": "System overview",
        "scope": "whole-system",
        "derives_from": ["PR-0001", "SR-0002"],
        "revision": 1,
        "approval_ref": None,
        "diagram_hash": "a" * 64,
        "assets": {"mode": "self_contained"},
        "render_check": True,
    }
    arc.update(overrides)
    return arc


def test_valid_arc_passes():
    validate(make_arc(), "arc_companion")


def test_arc_approval_ref_nullable_but_patterned():
    validate(make_arc(approval_ref="APR-0007"), "arc_companion")
    with pytest.raises(SchemaError, match="pattern"):
        validate(make_arc(approval_ref="user-said-yes"), "arc_companion")


def test_arc_derives_from_item_pattern():
    with pytest.raises(SchemaError, match="pattern"):
        validate(make_arc(derives_from=["TSK-0001"]), "arc_companion")


def test_arc_assets_requires_mode():
    with pytest.raises(SchemaError, match="mode"):
        validate(make_arc(assets={}), "arc_companion")


def test_arc_assets_mode_enum_enforced():
    with pytest.raises(SchemaError, match="enum"):
        validate(make_arc(assets={"mode": "whatever"}), "arc_companion")


def test_arc_assets_manifest_requires_hashed_files():
    with pytest.raises(SchemaError, match="files"):
        validate(make_arc(assets={"mode": "manifest"}), "arc_companion")
    with pytest.raises(SchemaError, match="pattern"):
        validate(
            make_arc(assets={"mode": "manifest", "files": {"logo.png": "nothex"}}),
            "arc_companion",
        )
    validate(  # good manifest passes
        make_arc(assets={"mode": "manifest", "files": {"logo.png": "c" * 64}}),
        "arc_companion",
    )


def test_datetime_value_raises_schema_error_not_typeerror():
    """Fable-Check 6/NIT-4: non-JSON values in unchecked positions surface as
    the curated SchemaError, never a raw TypeError."""
    import datetime

    with pytest.raises(SchemaError, match="non-JSON"):
        validate(make_brief(budget_status={"last_run": datetime.date(2026, 7, 24)}), "session_brief")


def test_arc_revision_bool_rejected():
    with pytest.raises(SchemaError, match="revision"):
        validate(make_arc(revision=True), "arc_companion")


def make_wfr(**overrides):
    wfr = {
        "id": "WFR-0001",
        "title": "Checkout layout",
        "derives_from": ["PR-0001"],
        "revision": 1,
        "diagram_hash": "b" * 64,
        "render_check": True,
        "scope_apr_ref": None,
    }
    wfr.update(overrides)
    return wfr


def test_valid_wfr_passes():
    validate(make_wfr(), "wfr_companion")


def test_wfr_scope_apr_ref_nullable_but_patterned():
    validate(make_wfr(scope_apr_ref="APR-0003"), "wfr_companion")
    with pytest.raises(SchemaError, match="pattern"):
        validate(make_wfr(scope_apr_ref="user-said-yes"), "wfr_companion")


# -- loader --------------------------------------------------------------------

def test_all_shipped_schemas_load():
    for name in ("result_envelope", "session_brief", "arc_companion", "wfr_companion"):
        schema = load_schema(name)
        assert schema["schema"] == name
        assert schema["fields"]


def test_unknown_schema_raises():
    with pytest.raises(KeyError, match="unknown schema"):
        load_schema("no_such_contract")


# -- an item VOCABULARY inside a list (item_enums, FR-0049) --------------------
def make_verdict(**overrides):
    verdict = {
        "task_id": "TSK-0042",
        "role": "filing-reviewer",
        "reviewed": "TSK-0041",
        "verdicts": [{"source": "inbox/a.pdf", "verdict": "accept",
                      "reason": "Betrag lesbar, Empfaenger stimmt"}],
    }
    verdict.update(overrides)
    return verdict


def test_a_valid_verdict_file_passes():
    validate(make_verdict(), "filing_verdict")


def test_an_item_enum_refuses_a_word_the_schema_does_not_declare():
    """The vocabulary of a per-entry key is the schema's, and `validate` is what refuses a fourth.

    `item_enums` is the list-item counterpart of `enum`, and it was added for exactly one subject:
    the filing reviewer's three answers, which the user named (FR-0049) and which the manager routes
    on. Without this test the branch had no measurement at all -- ablated, the whole schema suite
    stayed green -- and a schema key nothing exercises is a promise, not a check.

    WHAT THIS DOES NOT SAY, because the schema's own header says it: nothing in the shipped tree
    CALLS `validate` for a file of this shape, so this refusal happens where somebody asks for it
    and nowhere else. The vocabulary's runtime hold is the role texts plus the review itself.
    """
    for invented in ("maybe", "ACCEPT", "", "accepted"):
        with pytest.raises(SchemaError, match="enum"):
            validate(make_verdict(verdicts=[{"source": "inbox/a.pdf", "verdict": invented,
                                             "reason": "x"}]),
                     "filing_verdict")


def test_the_item_enum_reader_still_lets_every_declared_word_through():
    """The floor under the test above: a reader that refused everything would look identical.

    The three words come from the SCHEMA rather than from this file, so a vocabulary change moves
    both halves at once.
    """
    declared = load_schema("filing_verdict")["fields"]["verdicts"]["item_enums"]["verdict"]
    assert len(declared) >= 3, declared
    for word in declared:
        validate(make_verdict(verdicts=[{"source": "inbox/a.pdf", "verdict": word,
                                         "reason": "geprueft"}]),
                 "filing_verdict")


def test_a_proposal_entry_owes_every_key_the_pipeline_reads():
    """The sibling contract, same reason: the clerk's entry and the reviewer's entry are one object.

    `item_required` is what makes an entry answerable at all -- a proposal without a `destination`
    is one the reviewer cannot judge and the manager cannot execute.
    """
    whole = {"source": "inbox/a.pdf", "document_class": "incoming invoice",
             "destination": "archive/finance/2026/2026-01-01_ACME.pdf", "rule_id": "FP-001",
             "findings": ["Betrag 119,00 EUR"]}
    validate({"task_id": "TSK-0041", "role": "records-clerk", "proposals": [whole]},
             "filing_proposal")
    for missing in sorted(whole):
        partial = {key: value for key, value in whole.items() if key != missing}
        with pytest.raises(SchemaError, match=missing):
            validate({"task_id": "TSK-0041", "role": "records-clerk", "proposals": [partial]},
                     "filing_proposal")
