"""Order 7, stream A (TSK-0153): the calm approval card, the collected scope card, DEC-0119's texts.

What each test holds is named in its docstring; the decisions behind them are FR-0095 (the card),
FR-0096 (the collected scope card), FR-0090 (the readable expiry) and DEC-0119 (an approval is an
understanding check, never a permission to continue).
"""
import ast
import json
import os
import re
import subprocess
import sys
import time

import pytest
import yaml

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
TEAM_KITS = os.path.join(REPO, "team-kits")
sys.path.insert(0, TEAM_KITS)

from conftest import mint_via_hook, satisfy_the_architect_step  # noqa: E402
from kernel import approvals, cli, dispatch  # noqa: E402
from kernel.approvals import ApprovalError  # noqa: E402
from kernel.dispatch import DispatchError  # noqa: E402
from kernel.state import ProjectState  # noqa: E402

KITS = ("dev-team", "office-team", "research-team")

PR_FIELDS = {
    "title": "Kasse mit Rechnung",
    "class": "normal",
    "problem": "no checkout",
    "goal": "working checkout",
    "acceptance_criteria": [{"id": "AC-1", "text": "order completes"}],
    "invariants": [],
    "out_of_scope": [],
    "priority": "high",
}
NOTE = "Du wolltest es so; ich habe es so verstanden."


@pytest.fixture
def state(tmp_path):
    root = tmp_path / "project_memory"
    root.mkdir()
    return ProjectState(str(root))


def _goal(state, title="Kasse mit Rechnung"):
    return state.capture("PR", dict(PR_FIELDS, title=title))


def _change_wish(state, goal, title="Suchfeld oben rechts"):
    return state.capture("CR", {"title": title, "target_pr": goal["id"],
                                "target_revision": goal.get("revision"),
                                "change_description": "ein Suchfeld",
                                "acceptance_criteria": [{"id": "AC-11", "text": "es sucht"}]})


def _bug(state, goal, title="Rechnung ohne Datum", hole_bound=None):
    fields = {"title": title, "related_pr": goal["id"], "observed": "o", "expected": "e",
              "repro": "r", "severity": "low",
              "acceptance_criteria": [{"id": "AC-1", "text": "t"}]}
    if hole_bound is not None:
        fields[approvals.HOLE_LIMIT_FIELD] = hole_bound
    bug = state.capture("BUG", fields, hole=hole_bound is not None)
    if bug["status"] != "TRIAGED":
        state.transition(bug["id"], "TRIAGED")
    return state.read_item(bug["id"])


def _record(item_id, **extra):
    """A signed list record of the shape every list builder writes (`approvals.listed_items`)."""
    return dict({approvals.GOAL_ITEM_FIELD: item_id, "title": "Kurztitel von %s" % item_id,
                 "revision": 2, approvals.GOAL_SCOPE_HASH_FIELD: "ab" * 32}, **extra)


def _real_request(state, sample):
    """A PENDING request built through `create_pending_request` for one card sample -- see
    `_every_card`, which names the kind each sample is for."""
    kind = sample.split(" ")[0]
    later = time.time() + 7 * 86400
    goal = _goal(state)
    if sample == "scope --batch":
        other = _goal(state, "Suche im Shop")
        return approvals.create_pending_request(
            state, kind, manifest=approvals.scope_batch_subject_manifest(
                approvals.scope_batch(state, [goal["id"], other["id"]])), note=NOTE)
    if kind in ("scope", "delivery"):
        return approvals.create_pending_request(state, kind, goal["id"], note=NOTE)
    if kind == "acceptance":
        return approvals.create_pending_request(state, kind, goal["id"], note=NOTE,
                                                unverified_answer="ja, so gewollt")
    if sample == "hole_exception":
        hole = _bug(state, goal, "Lücke im Tor", hole_bound="die Rolle hält es ein")
        return approvals.create_pending_request(state, kind, hole["id"], note=NOTE)
    if sample == "hole_exception --batch":
        holes = [_bug(state, goal, "Lücke %d" % n, hole_bound="Begrenzung %d" % n)
                 for n in range(2)]
        return approvals.create_pending_request(
            state, kind, manifest=approvals.hole_exception_subject_manifest(
                approvals.hole_exception_batch(state, [h["id"] for h in holes])), note=NOTE)
    if kind == "routine":
        return approvals.create_pending_request(
            state, kind, goal["id"], manifest=approvals.routine_subject_manifest(
                "project-auditor", "project_memory/**", "wöchentlich", "wöchentlich"),
            approval_expires=later, note=NOTE)
    if kind == "analysis":
        return approvals.create_pending_request(
            state, kind, manifest={"question": "Was fehlt?", "read_only_scope": "src/**",
                                   "expected_result": "eine Liste", "tasks": ["TSK-0001"]},
            approval_expires=later, note=NOTE)
    manifests = {
        "plan": lambda: approvals.plan_subject_manifest([_record("PR-0001"), _record("PR-0002")]),
        "verification": lambda: approvals.verification_subject_manifest(
            [_record("BUG-0001", **{approvals.LISTED_EVIDENCE_FIELD: "EVD-0007"})]),
        "push": lambda: approvals.push_subject_manifest("origin", "feat/kasse", "0123abcd" * 5),
        "preset": lambda: approvals.preset_subject_manifest("duo", ["project-manager", "builder"],
                                                            []),
        "kit_update": lambda: approvals.kit_update_subject_manifest(
            "dev-team", "2026.09.13-6", "cd" * 32, "2026.09.26-5", "ef" * 32),
        "filing_correction": lambda: approvals.filing_correction_subject_manifest(
            "belege/2026/rechnung.pdf", "12" * 32, "falsch abgelegt", "belege/2025"),
        "filing_rule": lambda: approvals.filing_rule_subject_manifest(
            "rechnungen", "belege/{jahr}", "invoice", "{datum}_{absender}", "10 Jahre",
            "Rechnungen gehören zusammen"),
        "document_proposal": lambda: approvals.document_proposal_subject_manifest(
            "business_profile.yaml", "staging/TSK-0001/profile.yaml", "34" * 32, "56" * 32,
            ["tone: gefüllt mit freundlich"], "der Ton fehlte"),
        "document_revision": lambda: approvals.document_revision_subject_manifest(
            "business_profile.yaml", "staging/TSK-0001/profile.yaml", "34" * 32, "56" * 32,
            ["tone: alt -> neu"], ["legacy: weg"], [], "der Ton ist anders"),
    }
    return approvals.create_pending_request(
        state, kind, manifest=manifests[kind](),
        approval_expires=later if kind in approvals.EXPIRING_KINDS else None, note=NOTE)


# EVERY APR KIND, plus the list forms of the two kinds that also exist per item. A kind added to
# `APR_KINDS` without a sample here fails `test_every_kind_has_a_card_sample` -- the tripwire.
CARD_SAMPLES = sorted(approvals.APR_KINDS) + ["scope --batch", "hole_exception --batch"]


def test_every_kind_has_a_card_sample(state):
    """The sample list is not allowed to fall behind the vocabulary: every kind builds a request."""
    for kind in approvals.APR_KINDS:
        assert _real_request(ProjectState(state.root), kind)["kind"] == kind


# A request id, a checksum, a commit id: a hex run the user cannot read. The approving label's
# mint code is six characters and is the one token FR-0095 leaves on the card.
_MACHINE_HEX = re.compile(r"[0-9a-f]{8,}")
_ISO_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}|\d{2}:\d{2}:\d{2}Z")


@pytest.mark.parametrize("sample", CARD_SAMPLES)
def test_every_kind_reads_as_a_calm_card(state, sample):
    """FR-0095, per kind: the header line, one list line per thing approved, the assistant's note --
    and nothing the user cannot read.

    Built through `create_pending_request`, so the note travels the path that runs and is bound in
    the request (`NOTE_HASH_FIELD`). The shape: the first paragraph is exactly `Freigabe erbeten für
    <KIND_LABELS[kind]>`, the second is `- ` lines only, the last is the note marked as the
    assistant's. Refused anywhere on the card: a hex run of eight or more (request id, checksum,
    commit), the request's path, an ISO timestamp (FR-0090), and a manifest or record key under its
    English name. RED WITHOUT `_is_digest` in `_manifest_lines` (the kit_update checksums show),
    without the request id's removal, or with a new manifest key missing from `MANIFEST_LABELS`.
    """
    request = _real_request(state, sample)
    question = approvals.build_question(request)
    text = question["question"]
    blocks = text.split("\n\n")
    assert blocks[0] == "Freigabe erbeten für %s" % approvals.KIND_LABELS[request["kind"]], text
    lines = blocks[1].split("\n")
    assert lines and all(line.startswith("- ") and len(line) > 2 for line in lines), text
    assert blocks[-1] == "Erklärung deines Assistenten: %s" % NOTE, text
    assert len(blocks) == 3, text
    assert request[approvals.NOTE_HASH_FIELD] == approvals._note_hash(NOTE)

    approve, *declines = question["options"]
    assert approvals.APPROVE_LABEL_RX.match(approve["label"]).group(1) == request["mint_code"]
    read = [text, question["header"], approve["description"]] + [
        part for option in declines for part in (option["label"], option["description"])]
    for part in read:
        assert not _MACHINE_HEX.search(part), (sample, part)
        assert not _ISO_TIME.search(part), (sample, part)
        assert request["request_id"] not in part and "approvals/" not in part, (sample, part)
        assert request["mint_code"] not in part, (sample, part)
    manifest = request["subject_manifest"]
    keys = set(manifest) | {key for record in approvals._signed_records(manifest) for key in record}
    for key in keys:
        if approvals.MANIFEST_LABELS.get(key, key) == key:
            assert "%s:" % key not in text, (sample, key, text)


def test_an_unsigned_item_record_reads_as_a_list_line():
    """An item record WITHOUT its scope hash is still a list entry on an item-less card -- never
    `goals: {'item': ...}` -- and beside an item it does not replace the item's own line.

    The shape `tools/test_light_kit.py::_placeholder_manifest` builds, and the shape of any record a
    caller hands a list builder unsigned. RED WHEN `_card_lines` reads `_signed_records` only (the
    record falls to `_manifest_lines` and shows as a dict under its English key), and red the other
    way when the unsigned list is let in beside an item.
    """
    unsigned = {approvals.GOAL_ITEM_FIELD: "PR-0001", "title": "Kasse", "revision": 1}
    request = {"kind": "plan", "mint_code": "a1b2c3", "request_id": "0" * 32, "item": None,
               "subject_manifest": {"goals": [unsigned]}}
    lines = approvals.build_question(request)["question"].split("\n\n")[1].split("\n")
    assert lines == ["- PR-0001 „Kasse“"], lines

    beside_an_item = dict(request, kind="scope", item="PR-0002", item_title="Suche")
    lines = approvals.build_question(beside_an_item)["question"].split("\n\n")[1].split("\n")
    assert lines == ["- PR-0002 „Suche“"], lines


def test_every_key_a_formless_line_builder_writes_has_a_label():
    """A line kind with no `SUBJECT_LINES` form reads its manifest through `_manifest_lines`, so
    every key its builder writes needs a German label -- read off the builder's own signature, the
    way `tools/test_light_kit.py::_placeholder_manifest` builds its manifests. RED WITH any of the
    four list keys (`goals`, `bugs`, `holes`, `items`) taken out of `MANIFEST_LABELS`.
    """
    import inspect

    missing = {kind: [key for key in inspect.signature(builder).parameters
                      if key not in approvals.MANIFEST_LABELS]
               for kind, builder in approvals.LINE_MANIFEST_BUILDERS.items()
               if kind not in approvals.SUBJECT_LINES}
    assert not any(missing.values()), missing


def test_an_expiry_reads_as_a_german_date_with_its_zone_named(state):
    """FR-0090: `25.09.2026, 14:30 UTC` instead of `2026-09-25T14:30:00Z`, on every kind that has a
    clock -- the one value on the card that decides how long a standing permission lasts.

    RED WITH the old `%Y-%m-%dT%H:%M:%SZ` format in `_render_expiry`.
    """
    assert approvals._render_expiry(1758810600) == "25.09.2025, 14:30 UTC"
    for kind in sorted(approvals.EXPIRING_KINDS):
        request = _real_request(ProjectState(state.root), kind)
        text = approvals.build_question(request)["question"]
        expected = "- %s: %s" % (approvals.MANIFEST_LABELS[approvals.EXPIRY_FIELD], time.strftime(
            "%d.%m.%Y, %H:%M UTC", time.gmtime(request["subject_manifest"][approvals.EXPIRY_FIELD])))
        assert expected in text.split("\n"), (kind, text)
        assert not _ISO_TIME.search(text), (kind, text)


def test_the_assistants_note_is_signed_and_a_rewritten_note_grants_nothing(state):
    """FR-0095: the PM's note stands on the card and INSIDE what is signed.

    Process: the card is minted through the real hook; the approval carries the note's hash and
    stays in force. Then the consumed request's note is rewritten after the click -- what the user
    read is no longer what the record says -- and the approval grants nothing, through the same
    `assert_apr_in_force` every gate uses. A note is folded onto one line, and one past
    `NOTE_LIMIT` is refused rather than cut.
    RED WITHOUT the note re-check in `consumed_request`.
    """
    goal = _goal(state)
    request = approvals.create_pending_request(state, "scope", goal["id"],
                                               note="  Du wolltest\n eine Kasse.  ")
    assert request[approvals.NOTE_FIELD] == "Du wolltest eine Kasse."
    mint_via_hook(state, request)
    item = state.read_item(goal["id"])
    apr = approvals.read_apr(state, item["approval_ref"])
    assert apr[approvals.NOTE_HASH_FIELD] == approvals._note_hash("Du wolltest eine Kasse.")
    approvals.assert_apr_in_force(state, apr, item)

    consumed = approvals._request_path(state, request["request_id"], consumed=True)
    record = state._read_yaml(consumed)
    record[approvals.NOTE_FIELD] = "Du wolltest eine ganz andere Kasse."
    state._write_yaml_atomic(consumed, record)
    with pytest.raises(ApprovalError) as refused:
        approvals.assert_apr_in_force(state, apr, item)
    assert "note" in str(refused.value)

    with pytest.raises(ApprovalError) as long_note:
        approvals.create_pending_request(state, "delivery", goal["id"],
                                         note="x" * (approvals.NOTE_LIMIT + 1))
    assert "refused rather than cut" in str(long_note.value)


def test_a_card_is_found_by_its_mint_code_and_an_answered_one_says_so(state, monkeypatch):
    """FR-0095 moved the request id off the card, so the hooks resolve a card by its mint code.

    Three answers from `pending_request_by_code`: the open request; for a card already answered,
    the refusal that tells the user her yes is recorded (not "expired"); for a code nobody issued,
    the gone sentence. And the code is unique among the open requests: a clash is re-rolled at
    creation. RED WITHOUT the re-roll in `_fresh_mint_code` (the second request takes the first
    one's code and `pending_request_by_code` refuses both as ambiguous).
    """
    goal = _goal(state)
    first = approvals.create_pending_request(state, "scope", goal["id"])
    assert approvals.pending_request_by_code(
        state, first["mint_code"])["request_id"] == first["request_id"]

    import uuid as uuid_module
    real = uuid_module.uuid4
    # the request id is drawn first, then the code: the second draw clashes, the third is fresh
    codes = iter(["f" * 32, first["mint_code"] + "0" * 26, "c0ffee" + "0" * 26])

    class _Fixed:
        def __init__(self, hex_value):
            self.hex = hex_value

    def fake():
        try:
            return _Fixed(next(codes))
        except StopIteration:
            return real()

    monkeypatch.setattr(approvals.uuid, "uuid4", fake)
    second = approvals.create_pending_request(state, "delivery", goal["id"])
    monkeypatch.setattr(approvals.uuid, "uuid4", real)
    assert second["mint_code"] == "c0ffee", "the clashing draw was not re-rolled"
    assert approvals.pending_request_by_code(
        state, second["mint_code"])["request_id"] == second["request_id"]

    mint_via_hook(state, first)
    with pytest.raises(ApprovalError) as answered:
        approvals.pending_request_by_code(state, first["mint_code"])
    assert "bereits erteilt" in answered.value.user_text
    with pytest.raises(ApprovalError) as invented:
        approvals.pending_request_by_code(state, "abcdef")
    assert "nie angelegt" in invented.value.user_text


def _pattern_in(path, name):
    """The regex source a module assigns to `name`, read from the shipped file's syntax tree."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in tree.body:
        if (isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name
                                                   for t in node.targets)):
            return node.value.args[0].value
    raise AssertionError("%s assigns no %s" % (path, name))


def _constant_in(path, name):
    """The string constant a module assigns to `name`, read from the shipped file's syntax tree."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in tree.body:
        if (isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name
                                                   for t in node.targets)):
            return node.value.value
    raise AssertionError("%s assigns no %s" % (path, name))


def test_every_reader_of_the_approve_label_spells_it_as_the_kernel_writes_it():
    """The approving label is what a hook recognises an approval card BY since FR-0095, and it is
    spelled four times: `approvals.approve_label` writes it, `approvals.APPROVE_LABEL_RX` and the
    stdlib copies in every kit's `gate_approval.py` and `guard_question_context.py` read it. A drift
    makes a card that one hook recognises and another does not -- the guard would advise a reword on
    a card the gate compares character for character (pilot 3, B15).
    RED WHEN any copy differs from the kernel's pattern, or the pattern stops matching the label.
    """
    code = "0a1b2c"
    assert approvals.APPROVE_LABEL_RX.match(approvals.approve_label(code)).group(1) == code
    assert not approvals.APPROVE_LABEL_RX.match(approvals.approve_label(code) + " ")
    request = {"request_id": "ab" * 16, "kind": "plan", "item": None, "revision": None,
               "item_title": "", "mint_code": code, "subject_manifest": {},
               "subject_manifest_hash": "cd" * 32}
    assert approvals.build_question(request)["question"].startswith(approvals.CARD_PREFIX)
    for kit in KITS:
        hooks = os.path.join(TEAM_KITS, kit, "hooks")
        assert _pattern_in(os.path.join(hooks, "gate_approval.py"),
                           "APPROVE_LABEL_RX") == approvals.APPROVE_LABEL_RX.pattern, kit
        assert _pattern_in(os.path.join(hooks, "guard_question_context.py"),
                           "_APPROVE_LABEL_RX") == approvals.APPROVE_LABEL_RX.pattern, kit
        assert _constant_in(os.path.join(hooks, "gate_approval.py"),
                            "CARD_PREFIX") == approvals.CARD_PREFIX, kit


def _run_gate(state, event, question, answer=None):
    repo = os.path.dirname(state.root)
    payload = {"hook_event_name": event, "tool_name": "AskUserQuestion", "cwd": repo,
               "tool_input": {"questions": [question]}}
    if answer is not None:
        payload["tool_response"] = {"answers": {question["question"]: answer},
                                    "questions": [question]}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=repo, HARNESS_KERNEL_PATH=TEAM_KITS)
    return subprocess.run(
        [sys.executable, os.path.join(TEAM_KITS, "dev-team", "hooks", "gate_approval.py")],
        input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=120)


def _aprs(state):
    return sorted(n for n in os.listdir(os.path.join(state.root, "approvals"))
                  if n.startswith("APR-"))


def test_the_gate_mints_only_from_the_approving_option_of_the_calm_card(state):
    """The guard stays (DEC-0119 (5)): the card carries no request id any more, and the hook still
    refuses a card that is not the kernel's and mints only from the approving option.

    Process, the shipped hook with a JSON payload: PreToolUse passes the kernel's card and refuses
    one whose list line was edited, one whose approving label was relabelled (found by its exact
    text through `CARD_PREFIX`) and a question dressed as a card that no request has; an ordinary
    question is none of its business.
    PostToolUse mints nothing for `Ändern`, for a bare `Freigeben`, for the right label on an edited
    echo -- and mints for the approving option. RED WITH the retired marker lookup (the card is
    unmarked, so nothing is compared and nothing mints).
    """
    goal = _goal(state)
    request = approvals.create_pending_request(state, "scope", goal["id"], note=NOTE)
    card = approvals.build_question(request)
    assert _run_gate(state, "PreToolUse", card).returncode == 0
    edited = dict(card, question=card["question"].replace("Kasse", "Kassen"))
    refused = _run_gate(state, "PreToolUse", edited)
    assert refused.returncode == 2 and "NOT the one the kernel generated" in refused.stderr
    plain = {"question": "Welche Farbe?", "header": "Farbe", "multiSelect": False,
             "options": [{"label": "Rot", "description": "r"}, {"label": "Blau", "description": "b"}]}
    assert _run_gate(state, "PreToolUse", plain).returncode == 0
    # the card with its approving label relabelled: found by its text, refused before it is shown
    relabelled = dict(card, options=[dict(card["options"][0], label="Freigeben")]
                      + card["options"][1:])
    refused = _run_gate(state, "PreToolUse", relabelled)
    assert refused.returncode == 2 and "option 0 label differs" in refused.stderr, refused.stderr
    dressed = dict(plain, question=approvals.CARD_PREFIX + "etwas, das niemand angefragt hat")
    refused = _run_gate(state, "PreToolUse", dressed)
    assert refused.returncode == 2 and "no open request has this card" in refused.stderr

    for answer in ("Ändern", "Freigeben"):
        assert _run_gate(state, "PostToolUse", card, answer).returncode == 0
        assert _aprs(state) == [], answer
    label = approvals.approve_label(request["mint_code"])
    assert _run_gate(state, "PostToolUse", edited, label).returncode == 0
    assert _aprs(state) == []
    minted = _run_gate(state, "PostToolUse", card, label)
    assert "recorded for" in minted.stderr, minted.stderr
    assert len(_aprs(state)) == 1
    assert state.read_item(goal["id"])["status"] == "APPROVED"


def _cli(state, capsys, *argv):
    code = cli.main(["--root", state.root, *argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_a_collected_scope_card_refuses_a_done_item_a_foreign_type_and_an_eleventh_id(state, capsys):
    """FR-0096's batch form, refused BY NAME before anybody is asked: an item already past its scope
    edge (a DONE one authorises nothing any more), an id of a type no scope approval commits an edge
    for, more than `BATCH_LIMIT` ids, one id twice, and an id plus a list at once. The same line with
    good ids prints the card.
    RED WITHOUT the `BATCH_LIMIT` check in `scope_batch_subject_manifest` (eleven ids print a card),
    and without `batch_walk_blockers` in `scope_batch` (the done item and the task are listed).
    """
    goal = _goal(state)
    wish = _change_wish(state, goal)
    done = _change_wish(state, goal, "schon freigegeben")
    mint_via_hook(state, approvals.create_pending_request(state, "scope", done["id"]))
    assert state.read_item(done["id"])["status"] == "APPROVED"
    wish_of_the_inbox = state.capture("FR", {"title": "ein Wunsch", "request_text": "bitte"})

    code, _out, err = _cli(state, capsys, "request-approval", "scope", "--batch", wish["id"],
                           done["id"])
    assert code != 0 and done["id"] in err and "already APPROVED" in err, err
    code, _out, err = _cli(state, capsys, "request-approval", "scope", "--batch",
                           wish_of_the_inbox["id"])
    assert code != 0 and "commits no transition of a FR" in err, err
    many = [_goal(state, "Ziel %d" % n)["id"] for n in range(approvals.BATCH_LIMIT + 1)]
    code, _out, err = _cli(state, capsys, "request-approval", "scope", "--batch", *many)
    assert code != 0 and "at most %d" % approvals.BATCH_LIMIT in err, err
    code, _out, err = _cli(state, capsys, "request-approval", "scope", "--batch", wish["id"],
                           wish["id"])
    assert code != 0 and "twice" in err, err
    code, _out, err = _cli(state, capsys, "request-approval", "scope", goal["id"], "--batch",
                           wish["id"])
    assert code != 0 and "not both" in err, err
    assert approvals.open_requests(state) == []

    code, out, err = _cli(state, capsys, "request-approval", "scope", "--batch", wish["id"],
                          goal["id"], "--note", NOTE)
    assert code == 0, err
    card = json.loads(out)
    assert card["question"].split("\n\n")[1].split("\n") == [
        "- %s „%s“" % (wish["id"], wish["title"]), "- %s „%s“" % (goal["id"], goal["title"])]
    assert "withdraw-request" in err


def test_a_collected_scope_card_walks_each_entry_across_its_own_edge_and_no_further(state):
    """ONE answer approves every listed item (FR-0096): a new goal, a change wish and a bug each walk
    their OWN scope edge to `APPROVED` and stop -- the bug is not walked to `VERIFIED`, because the
    card said "understood", never "repaired" -- and the goal's builder dispatches on it.

    RED WITHOUT the own-kind branch of `batch_walk_end` (the bug is refused for want of a test
    Evidence), and WITHOUT `assert_apr_in_force` skipping the per-item hash for a list (the walk of
    the first item is refused after the approval exists).
    """
    goal = _goal(state)
    wish = _change_wish(state, goal)
    bug = _bug(state, goal)
    request = approvals.create_pending_request(
        state, "scope", manifest=approvals.scope_batch_subject_manifest(
            approvals.scope_batch(state, [bug["id"], wish["id"], goal["id"]])))
    mint_via_hook(state, request)
    apr_ids = set()
    for item_id in (goal["id"], wish["id"], bug["id"]):
        item = state.read_item(item_id)
        assert item["status"] == "APPROVED", (item_id, item["status"])
        apr_ids.add(item["approval_ref"])
    assert len(apr_ids) == 1

    task = dispatch.create_task(state, {
        "product_requirement": goal["id"], "derives_from": goal["id"], "type": "implementation",
        "assigned_role": "backend-developer", "acceptance_refs": ["AC-1"], "required_inputs": [],
        "allowed_scope": ["src/"], "forbidden_scope": [], "expected_outputs": ["src/x.py"],
        "dependencies": []})
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]), state.read_item(goal["id"]))
    assert dispatch.create_lease(state, task["id"])


def _edit_past_the_kernel(state, item_id, **fields):
    path = state.active_path(item_id)
    body = state._read_yaml(path)
    body.update(fields)
    state._write_yaml_atomic(path, body)


def test_the_per_entry_hash_is_rechecked_at_use(state):
    """Each entry of a collected card is bound to its OWN scope hash, and that hash is asked again
    whenever the card is used: between the question and the click (the mint refuses and moves
    NOTHING -- all or nothing), and after the mint (the approval stops covering the edited item and
    its builder is refused, while the other entry stays covered).
    RED WITHOUT `_assert_the_list_covers` in the list branch of `assert_apr_in_force`.
    """
    first, second = _goal(state), _goal(state, "Suche im Shop")
    asked = approvals.create_pending_request(
        state, "scope", manifest=approvals.scope_batch_subject_manifest(
            approvals.scope_batch(state, [first["id"], second["id"]])))
    _edit_past_the_kernel(state, second["id"],
                          acceptance_criteria=[{"id": "AC-1", "text": "etwas anderes"}])
    mint_via_hook(state, asked, expect_success=False)
    assert _aprs(state) == []
    assert [state.read_item(i)["status"] for i in (first["id"], second["id"])] == ["DRAFT"] * 2

    third = _goal(state, "Versand")
    request = approvals.create_pending_request(
        state, "scope", manifest=approvals.scope_batch_subject_manifest(
            approvals.scope_batch(state, [first["id"], third["id"]])))
    mint_via_hook(state, request)
    apr = approvals.read_apr(state, state.read_item(first["id"])["approval_ref"])
    approvals.assert_apr_in_force(state, apr, state.read_item(first["id"]))
    _edit_past_the_kernel(state, first["id"], goal="ein anderes Ziel")
    with pytest.raises(ApprovalError) as moved:
        approvals.assert_apr_in_force(state, apr, state.read_item(first["id"]))
    assert "content of %s changed" % first["id"] in str(moved.value)
    approvals.assert_apr_in_force(state, apr, state.read_item(third["id"]))

    task = dispatch.create_task(state, {
        "product_requirement": first["id"], "derives_from": first["id"],
        "type": "implementation", "assigned_role": "backend-developer",
        "acceptance_refs": ["AC-1"], "required_inputs": [], "allowed_scope": ["src/"],
        "forbidden_scope": [], "expected_outputs": ["src/x.py"], "dependencies": []})
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]), state.read_item(first["id"]))
    with pytest.raises(DispatchError):
        dispatch.create_lease(state, task["id"])


def test_an_acceptance_is_not_asked_while_a_change_wish_of_the_goal_is_unconfirmed(state):
    """DEC-0119 (4): a change wish may be worked at once, and its understanding card is answered
    BEFORE the goal's acceptance -- built, not asked of the PM: the acceptance request is refused by
    name while a `CR` of the goal still waits in `DRAFT`, and asked once the card is answered. A
    wish of ANOTHER goal does not hold this one up.
    RED WITHOUT `_assert_no_change_wish_waits` in `create_pending_request`.
    """
    goal, other = _goal(state), _goal(state, "Versand")
    wish = _change_wish(state, goal)
    _change_wish(state, other, "gehört zum anderen Ziel")
    with pytest.raises(ApprovalError) as waiting:
        approvals.create_pending_request(state, "acceptance", goal["id"],
                                         unverified_answer="ja, so gewollt")
    assert wish["id"] in str(waiting.value) and "scope --batch" in str(waiting.value)
    assert approvals.unanswered_change_wishes(state, goal["id"]) == [wish["id"]]

    mint_via_hook(state, approvals.create_pending_request(
        state, "scope", manifest=approvals.scope_batch_subject_manifest(
            approvals.scope_batch(state, [wish["id"]]))))
    assert approvals.unanswered_change_wishes(state, goal["id"]) == []
    assert approvals.create_pending_request(state, "acceptance", goal["id"],
                                            unverified_answer="ja, so gewollt")["kind"] == \
        "acceptance"


def test_only_the_scope_kind_takes_an_id_or_a_list(state, capsys):
    """`cli.EITHER_FORM_KINDS` both ends: every entry is a kind that has a list form AND a per-item
    manifest (no dead entry), `scope` really takes an id and a list on the shipped parser, and
    `hole_exception` -- the other item-derived list kind -- keeps its single form retired (PR-0012
    AC-4) and sends an id to --batch.
    """
    batched = cli.kinds_reading_argument(cli.BATCH_ARGUMENT)
    assert cli.EITHER_FORM_KINDS <= batched & set(approvals.item_derived_kinds())
    goal, other = _goal(state), _goal(state, "Versand")
    code, out, err = _cli(state, capsys, "request-approval", "scope", goal["id"])
    assert code == 0, err
    code, out, err = _cli(state, capsys, "request-approval", "scope", "--batch", other["id"])
    assert code == 0, err
    code, _out, err = _cli(state, capsys, "request-approval", approvals.HOLE_EXCEPTION_KIND,
                           "BUG-0001")
    assert code != 0 and "--batch" in err, err


# -- DEC-0119 in the kits' lead texts ------------------------------------------------------------

LEAD_SKILL = {"dev-team": "project-manager", "research-team": "project-manager",
              "office-team": "office-manager"}
# WHAT A LEAD IS TOLD TO REQUEST, per kit -- the expected values of the structural test below.
# DEC-0119 (2): the plan, the collected scope card, the acceptance (and, per the order, the
# delivery), plus the kinds that are the user's by nature -- push, kit update, routine, preset.
# `verification` stays because DEC-0100 (1) is in force: the user's click closes a bug (the order's
# list of eight left it out; the deviation is reported, not hidden). The office kit has no root
# goal (`backlog_types.ROOT_TYPE_BY_KIT`), so no plan, delivery or acceptance -- and its own
# archive and document kinds are the user's by nature (`approvals.IRREVERSIBLE_KINDS`).
_GOAL_KITS_KINDS = {("plan", ""), ("scope", "batch"), ("delivery", ""), ("acceptance", ""),
                    ("verification", "batch"), ("push", ""), ("kit_update", ""), ("routine", ""),
                    ("preset", "")}
EXPECTED_KINDS = {
    "dev-team": _GOAL_KITS_KINDS,
    "research-team": _GOAL_KITS_KINDS,
    "office-team": {("scope", "batch"), ("verification", "batch"), ("push", ""),
                    ("kit_update", ""), ("routine", ""), ("preset", ""), ("filing_rule", ""),
                    ("filing_correction", ""), ("document_proposal", ""),
                    ("document_revision", "")},
}
_FENCE = re.compile(r"^```yaml\n(.*?)^```", re.MULTILINE | re.DOTALL)
_SPAN = re.compile(r"`(?:python scripts/harness\.py )?request-approval ([^`]*)`")


def _kind_block(text):
    """The `approval_kinds` list of the one fenced yaml block that carries it."""
    found = [yaml.safe_load(block) for block in _FENCE.findall(text)]
    found = [block["approval_kinds"] for block in found
             if isinstance(block, dict) and "approval_kinds" in block]
    assert len(found) == 1, "expected exactly one approval_kinds block, found %d" % len(found)
    return found[0]


@pytest.mark.parametrize("kit", KITS)
def test_the_approval_kinds_a_lead_is_told_to_request_are_the_decided_ones(kit):
    """DEC-0119 as a structural contract (DEC-0116): the lead skill's `approval_kinds` block -- parsed,
    never searched as prose -- names exactly the decided kinds, each a real kind with a form the
    command line really has. And the other direction: every `request-approval <kind>` command the
    lead's skill or constitution spells in code names a (kind, form) of that block, so no text can
    tell the lead to ask a per-item scope question or a kind the list does not carry.
    RED WHEN the block gains or loses a kind, or when a text keeps `request-approval scope PR-nnnn`.
    """
    skill = open(os.path.join(TEAM_KITS, kit, "skills", LEAD_SKILL[kit], "SKILL.md"),
                 encoding="utf-8").read()
    constitution = open(os.path.join(TEAM_KITS, kit, "constitution", "AGENTS.md"),
                        encoding="utf-8").read()
    listed = {(entry["kind"], entry.get("form", "")) for entry in _kind_block(skill)}
    assert listed == EXPECTED_KINDS[kit], listed ^ EXPECTED_KINDS[kit]
    batched = cli.kinds_reading_argument(cli.BATCH_ARGUMENT)
    offered = set(approvals.item_derived_kinds()) | set(approvals.line_manifest_kinds())
    for kind, form in listed:
        assert kind in offered, kind
        assert form in ("", "batch") and (form != "batch" or kind in batched), (kind, form)
    for span in _SPAN.findall(skill + constitution):
        words = span.split()
        if not words or words[0].startswith("<"):
            continue                     # the generic `request-approval <kind> …` names no kind
        form = "batch" if "--batch" in words else ""
        assert (words[0], form) in listed, (kit, span)


def test_a_program_holding_only_the_card_finds_its_request(state):
    """The SDK door (FR-0083) after FR-0095: an embedding program gets the CARD from the entry point
    and no request id any more, so `sdk_approval.request_id_of_card` resolves the card the way the
    approval hook does -- by the approving label's code -- and refuses a card that names no single
    request. RED WITHOUT the helper (the program has no way from the card to `mint_from_can_use_tool`).
    """
    from kernel import sdk_approval

    goal = _goal(state)
    request = approvals.create_pending_request(state, "scope", goal["id"])
    card = approvals.build_question(request)
    assert sdk_approval.request_id_of_card(state, card) == request["request_id"]
    stripped = dict(card, options=card["options"][1:])
    with pytest.raises(ApprovalError):
        sdk_approval.request_id_of_card(state, stripped)
