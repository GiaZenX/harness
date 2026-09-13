"""Tests for session brief, state validator and doctor (spec II.4/II.5, step 1.4c)."""
import glob
import io
import json
import os
import re
import subprocess
import sys
import time

import pytest
import yaml

TEAM_KITS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "team-kits")
REPO_ROOT = os.path.dirname(TEAM_KITS)
sys.path.insert(0, TEAM_KITS)

from conftest import (  # noqa: E402 -- ONE mint helper for the suite
    drive_task_to,
    mint_via_hook,
    satisfy_the_architect_step,
    walk_to_status,
)
from kernel import approvals, board, cli, dispatch, plan_diagram, report, staging  # noqa: E402
from kernel.hashing import hook_bundle_hash  # noqa: E402 -- THE definition of the bundle hash
from kernel import state as kernel_state  # noqa: E402 -- the module, for its naming rule
from kernel.backlog_types import (  # noqa: E402
    PARENT_FIELDS,
    QA_EVIDENCE_KINDS,
    REQUIRED_FIELDS,
)
from kernel.lock import PORTABLE_PATH_MAX_CHARS, ext_path  # noqa: E402
from kernel.state import ProjectState  # noqa: E402


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


@pytest.fixture
def state(tmp_path):
    root = tmp_path / "project_memory"
    root.mkdir()
    return ProjectState(str(root))


def errors(findings):
    return [f for f in findings if f["severity"] == "error"]


# -- validator -----------------------------------------------------------------

def test_clean_state_has_no_errors(state):
    state.capture("PR", dict(PR_FIELDS))
    assert errors(report.validate_state(state)) == []


def test_out_of_band_hand_edit_detected_via_hash(state):
    """D/4: an IDE edit past the kernel invalidates the approval VISIBLY.

    THE REMEDY IS ASSERTED BY ITS TWO MOVES, not by its wording. It used to be spelled here
    ("re-approve or revert") because the validator wrote its own; since the validator asks
    `approvals.assert_apr_in_force`, the sentence is the kernel branch's -- one text instead of
    two -- and a test pinned to the old spelling would be pinning the copy that was removed.
    Both ways out have to be offered either way, and that is what is read.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", pr["id"])
    mint_via_hook(state, request)
    assert errors(report.validate_state(state)) == []
    # hand-edit: bypass the kernel entirely (same revision, changed content)
    path = state.active_path(pr["id"])
    item = yaml.safe_load(open(path, encoding="utf-8"))
    item["goal"] = "sneakily changed in the IDE"
    yaml.safe_dump(item, open(path, "w", encoding="utf-8"), sort_keys=False, allow_unicode=True)
    found = errors(report.validate_state(state))
    assert any("content hash" in f["message"] for f in found)
    remedies = [f["remedy"] for f in found]
    assert any("re-approve" in remedy for remedy in remedies), remedies
    assert any("restore" in remedy for remedy in remedies), remedies


def test_manually_written_apr_ref_detected(state):
    """II.12: manually written APR without kernel token -> flagged."""
    pr = state.capture("PR", dict(PR_FIELDS))
    path = state.active_path(pr["id"])
    item = yaml.safe_load(open(path, encoding="utf-8"))
    item["approval_ref"] = "APR-0042"  # no such APR file
    yaml.safe_dump(item, open(path, "w", encoding="utf-8"), sort_keys=False, allow_unicode=True)
    found = errors(report.validate_state(state))
    assert any("no APR file" in f["message"] for f in found)


def test_status_dependent_duties(state):
    fr = state.capture("FR", {"title": "wish", "request_text": "please add X"})
    state.transition(fr["id"], "TRIAGED")
    found = errors(report.validate_state(state))
    assert any("triage_result" in f["message"] for f in found)


def test_inv_text_value_one_of(state):
    inv = state.capture("INV", {
        "scope": "frontend", "source": "PR-0001",
        "check": {"kind": "test", "ref": "t.py::test_x"},
    })
    found = errors(report.validate_state(state))
    assert any(inv["id"] == f["item"] and "text|value" in f["message"] for f in found)


def test_item_budget_enforced(state):
    pr = state.capture("PR", dict(PR_FIELDS, problem="x" * 13000))
    found = errors(report.validate_state(state))
    assert any(pr["id"] == f["item"] and "budget" in f["message"] for f in found)


def test_a_state_tree_past_the_portable_path_limit_is_warned_once(tmp_path):
    """FR-0037: spec II.4 promised this warning and only the extended-length half was built.

    Measured before the check existed: a state tree copied under a 309-character root produced
    exactly one finding from `validate_state`, and it was about `user_story` -- nothing named a
    path length, while the kernel happily kept writing through `lock.ext_path`.

    Three properties in one place, because each of them was a way to get this wrong: it is a
    WARNING (a merge that stops on tree depth gets worked around), it fires ONCE for a tree
    rather than once per item, and it reads only the paths the scan already opened -- a render
    deeper inside a staging directory is the named blind spot, measured in the second half.
    """
    deep = os.path.join(str(tmp_path), *(["a-directory-with-a-long-name"] * 8))
    root = os.path.join(deep, "project_memory")
    os.makedirs(ext_path(root))
    deep_state = ProjectState(root)
    deep_state.capture("PR", dict(PR_FIELDS))
    deep_state.capture("PR", dict(PR_FIELDS, title="second requirement"))
    findings = report.validate_state(deep_state)
    named = [f for f in findings if "longer than %d characters" % PORTABLE_PATH_MAX_CHARS
             in f["message"]]
    assert len(named) == 1, [f["message"] for f in findings]
    assert named[0]["severity"] == "warning", named[0]
    assert errors(findings) == [], errors(findings)

    shallow = ProjectState(str(tmp_path / "pm"))
    os.makedirs(ext_path(shallow.root))
    pr = shallow.capture("PR", dict(PR_FIELDS))
    buried = os.path.join(shallow.staging_root(), pr["id"],
                          *(["a-directory-with-a-long-name"] * 8))
    os.makedirs(ext_path(buried))
    with io.open(ext_path(os.path.join(buried, "render.tex")), "w", encoding="utf-8") as fh:
        fh.write("x")
    assert len(os.path.abspath(os.path.join(buried, "render.tex"))) > PORTABLE_PATH_MAX_CHARS
    assert not [f for f in report.validate_state(shallow)
                if "longer than" in f["message"]], "the blind spot named above closed silently"


def test_a_bug_may_name_the_system_requirement_it_hit_but_only_under_its_own_root(state):
    """FR-0054: `related_sr`, optional, and judged on ROOT MEMBERSHIP rather than existence.

    The FR names the residue it must not repeat: `related_pr` and `target_pr` are checked for
    resolvability and for nothing else, so they accept a requirement out of a foreign tree. The
    third assertion below is that difference -- an SR that exists, resolves, and belongs to
    another root.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    elsewhere = state.capture("PR", dict(PR_FIELDS, title="Another product"))
    sr = state.capture("SR", {"title": "prices round half up", "derives_from": pr["id"],
                              "contract": "half up", "affected_components": ["pricing"]})
    stray = state.capture("SR", {"title": "foreign contract", "derives_from": elsewhere["id"],
                                 "contract": "x", "affected_components": ["y"]})
    named = state.capture("BUG", {
        "title": "rounds down", "related_pr": pr["id"], "related_sr": sr["id"],
        "observed": "o", "expected": "e", "repro": "r", "severity": "low",
        "acceptance_criteria": ["fixed"]})
    make_bug(state, pr["id"])          # the field stays optional: no stored item is forced to it
    assert errors(report.validate_state(state)) == []

    crossed = state.capture("BUG", {
        "title": "wrong tree", "related_pr": pr["id"], "related_sr": stray["id"],
        "observed": "o", "expected": "e", "repro": "r", "severity": "low",
        "acceptance_criteria": ["fixed"]})
    found = [f for f in errors(report.validate_state(state)) if f["item"] == crossed["id"]]
    assert found, [f["message"] for f in report.validate_state(state)]
    assert "related_sr" in found[0]["message"] and stray["id"] in found[0]["message"]
    assert pr["id"] in found[0]["remedy"]
    # ...and the bug that named the right one is not the one being complained about
    assert not [f for f in errors(report.validate_state(state)) if f["item"] == named["id"]]


# A REQUIREMENT THE SIZE OF A REAL ONE. The hint refuses to compare items with less content
# than `report.DUPLICATE_HINT_MIN_WORDS`, and the fixtures these tests used to carry were smaller
# than the smallest item in any real store -- which is why an earlier version of this test scored
# two DIFFERENT requirements at 0.429 and had to be argued with. Measured against prose of the
# length a project really writes, the same pair is noise.
RICH_PR = dict(
    PR_FIELDS,
    title="Bezahlvorgang mit gespeicherten Zahlungsmitteln",
    problem=("Kundinnen brechen den Bezahlvorgang ab, weil sie ihre Kartendaten bei jeder "
             "Bestellung neu eintippen muessen; die Abbruchquote steigt vor allem auf dem "
             "Telefon, wo das Formular ueber mehrere Bildschirme laeuft."),
    goal=("Ein einmal bestaetigtes Zahlungsmittel steht bei der naechsten Bestellung bereit, "
          "sodass der Bezahlvorgang aus einer Bestaetigung besteht und nicht aus einem Formular."),
    acceptance_criteria=[
        {"id": "AC-1", "text": "Ein gespeichertes Zahlungsmittel erscheint im Bezahlvorgang"},
        {"id": "AC-2", "text": "Das Loeschen eines Zahlungsmittels wirkt sofort"},
    ],
    out_of_scope=["Rechnungskauf", "Ratenzahlung", "Gutscheine"],
    user_story=("Als wiederkehrende Kundin moechte ich mit einem gespeicherten Zahlungsmittel "
                "bezahlen, damit die Bestellung nicht an der Tastatur haengt."),
)


def test_the_duplicate_hint_stays_quiet_on_ordinary_neighbours(state):
    """FR-0018 makes silence the condition: "only build it if it grips without nagging".

    THREE PAIRS, AND EACH HOLDS ONE THING. An unrelated requirement of the same project is silent
    -- that is what a backlog looks like, and a hint firing there is the nagging the FR forbids.
    A NEIGHBOUR that shares the subject and asks something else is silent too, and it is the LOWER
    edge of the band: it sits between the two candidate thresholds, so a threshold low enough to
    nag turns this test red. A RE-REQUEST -- the same requirement written again in other words --
    is found, and it is the UPPER edge: a threshold high enough to go quiet turns it red as well.

    Both edges are on the THRESHOLD and not on the word floor, which is the correction this test
    needed: after the fixtures grew to real prose, the neighbour pair had drifted so far apart
    that the lower mutation stayed green here and only the floor test still caught anything, while
    this docstring went on claiming both edges (measured 2026-09-02, verification of rework 1).
    The scores of the three pairs are in the TSK-0106 protocol; the band they sit in is
    `report.DUPLICATE_HINT_SIMILARITY`.
    """
    state.capture("PR", dict(RICH_PR))
    unrelated = dict(
        RICH_PR, title="Ruecksendungen ohne Anruf beim Kundendienst",
        problem=("Wer etwas zurueckschicken will, muss beim Kundendienst anrufen; die Leitung "
                 "ist morgens besetzt und die Pakete bleiben tagelang liegen."),
        goal=("Eine Ruecksendung wird im Konto angemeldet, das Etikett kommt per Mail, und der "
              "Kundendienst sieht den Vorgang ohne Anruf."),
        acceptance_criteria=[{"id": "AC-1", "text": "Etikett kommt ohne Anruf"}],
        out_of_scope=["Reparaturen", "Umtausch im Laden"],
        user_story=("Als Kaeuferin moechte ich eine Ruecksendung selbst anmelden, damit ich "
                    "niemanden anrufen muss."))
    assert report.similar_items(state, "PR", unrelated) == []

    # THE LOWER EDGE: the same subject, a different requirement -- the shape of the closest pair
    # this project's own store holds. Silent here, and loud under any threshold below the band.
    neighbour = dict(
        RICH_PR, title="Abgelaufene Zahlungsmittel im Bezahlvorgang",
        problem=("Kundinnen brechen den Bezahlvorgang ab, weil ein gespeichertes Zahlungsmittel "
                 "abgelaufen ist und die Bestellung ohne Hinweis stehen bleibt; die Abbruchquote "
                 "steigt vor allem auf dem Telefon, wo die stille Ablehnung gar nicht auffaellt."),
        goal=("Ein abgelaufenes Zahlungsmittel wird im Bezahlvorgang gezeigt, sodass die "
              "Bestellung nicht an einer stillen Ablehnung haengt."),
        acceptance_criteria=[{"id": "AC-1", "text": "Ein abgelaufenes Zahlungsmittel wird gezeigt"}],
        out_of_scope=["Rechnungskauf", "Ratenzahlung", "Gutscheine"],
        user_story=("Als Kundin moechte ich sehen, dass mein gespeichertes Zahlungsmittel "
                    "abgelaufen ist, bevor ich die Bestellung abschicke."))
    assert report.similar_items(state, "PR", neighbour) == []

    # THE UPPER EDGE: the same requirement asked a second time, worded freshly rather than copied
    # -- which is the case the FR describes (an agent whose context ran over). Found here, and
    # silent under any threshold above the band.
    again = dict(
        RICH_PR, title="Zahlungsmittel merken und beim naechsten Kauf anbieten",
        problem=("Kundinnen brechen den Bezahlvorgang ab, weil sie ihre Kartendaten bei jeder "
                 "Bestellung neu eintippen muessen; auf dem Telefon zieht sich das Formular ueber "
                 "mehrere Bildschirme."),
        goal=("Ein bestaetigtes Zahlungsmittel steht bei der naechsten Bestellung bereit, sodass "
              "aus dem Formular eine Bestaetigung wird."))
    near = report.similar_items(state, "PR", again)
    assert [row["id"] for row in near] == ["PR-0001"], near
    assert near[0]["score"] >= report.DUPLICATE_HINT_SIMILARITY


def test_the_duplicate_hint_reads_a_word_in_any_script_not_only_in_ascii(state):
    """The tokenizer decides what a WORD is, and `[a-z0-9]` decided it for one alphabet.

    A German word came apart at its umlauts -- `Prüfung` read as `fung`, `Größe` as `e` and `Gr`,
    both under the length floor -- so the comparison ran on fragments nobody wrote, and two items
    were as similar as their leftovers happened to be. Read off the running function rather than
    off the regex, so a second reader spelled differently but broken the same way is still red.

    THE LIMIT THIS DOES NOT CLOSE, measured in the same test rather than promised away: a script
    that does not separate words -- Japanese here -- yields ONE token per phrase, so such a store
    stays under `DUPLICATE_HINT_MIN_WORDS` and the hint is SILENT for it. Silence is the safe
    direction (no false alarm, nothing refused), and it is named in the TSK-0106 protocol; what
    would close it is a segmenter, which is not a thing a kernel three kits share should carry.
    """
    words = report._content_words({"title": "Prüfung der Größe"}, ())
    assert words == {"prüfung", "der", "größe"}, words

    phrase = report._content_words({"title": "支払い方法の保存"}, ())
    assert len(phrase) == 1, phrase          # one run of letters: no word boundaries to find
    assert len(phrase) < report.DUPLICATE_HINT_MIN_WORDS


def test_the_duplicate_hint_says_nothing_about_items_too_small_to_compare(state):
    """A ratio over a handful of words is decided by a single shared one.

    Measured on two unrelated bugs of four content words each -- "404 -> 200" and "500 -> 200":
    they share the response code and the severity and score 0.5, over a threshold calibrated on
    items that carry fifty words and more. Nothing about the tokenizer fixes that; the pair simply
    does not say enough to be compared.

    Both edges of the floor, and the band between them is wide: the noise cases live at four to
    eight content words, the SMALLEST item in this project's own store carries 49 and the smallest
    union of an honest pair is 93 (measured 2026-09-02).
    """
    tiny = {"related_pr": "PR-0001", "severity": "high", "repro": "1 2 3",
            "acceptance_criteria": [{"id": "AC-1", "text": "x"}]}
    state.capture("PR", dict(RICH_PR))
    state.capture("BUG", dict(tiny, title="404", observed="404", expected="200"))
    other = dict(tiny, title="500", observed="500", expected="200", repro="4 5 6")
    assert report.similar_items(state, "BUG", other) == []

    # ...and the floor is a floor and not a mute: a bug that says as much as a real one is found
    wordy = {"related_pr": "PR-0001", "severity": "high",
             "observed": ("Der Bezahlvorgang bricht mit einer leeren Seite ab, sobald ein "
                          "gespeichertes Zahlungsmittel gewaehlt wird; im Protokoll steht nur eine "
                          "Zeitueberschreitung ohne Angabe des Dienstes."),
             "expected": ("Der Bezahlvorgang laeuft mit einem gespeicherten Zahlungsmittel durch, "
                          "und eine Zeitueberschreitung nennt den Dienst, der nicht geantwortet "
                          "hat."),
             "repro": ("Bestellung anlegen, gespeichertes Zahlungsmittel waehlen, bestaetigen; "
                       "die leere Seite erscheint nach etwa dreissig Sekunden."),
             "acceptance_criteria": [{"id": "AC-1", "text": "Der Bezahlvorgang laeuft durch"}]}
    stored = state.capture("BUG", dict(wordy, title="Leere Seite beim Bezahlen"))
    again = dict(wordy, title="Bezahlen endet auf einer leeren Seite")
    assert [row["id"] for row in report.similar_items(state, "BUG", again)] == [stored["id"]]


def test_the_duplicate_hint_covers_every_type_whose_content_the_kernel_defines(state):
    """Both ends of a derivation, because the alternative was a list of two type names.

    `HASHED_FIELDS` is the kernel's own answer to "what is this item's substance" -- the fields
    whose change invalidates an approval -- so the hint covers exactly the types that have one and
    guesses for none. The counter-direction is what makes it a derivation rather than a filter
    that happens to agree today: a type with no such definition yields nothing even when two of
    its items are byte-identical.

    Items are written into the store directly. The hint reads files, not automata, and building a
    contract-valid pair for seven types would measure the fixtures instead of the rule.
    """
    from kernel.backlog_types import ACTIVE_DIRS, HASHED_FIELDS
    covered, uncovered = [], []
    for item_type, directory in sorted(ACTIVE_DIRS.items()):
        if item_type in ("WFR", "DSN"):
            continue                    # stored per revision, not as one active file
        target = os.path.join(state.root, *directory.split("/"))
        os.makedirs(target, exist_ok=True)
        fields = HASHED_FIELDS.get(item_type) or ("title",)
        # AS MUCH CONTENT AS A REAL ITEM: the hint refuses to compare anything smaller
        # (`report.DUPLICATE_HINT_MIN_WORDS`), so a one-line fixture would measure that floor
        # instead of the type coverage this test is about.
        body = {"id": "%s-0001" % item_type,
                "title": "a rounding rule for prices in every currency"}
        for field in fields:
            body[field] = ("prices are rounded half up in every currency, and the rounded amount "
                           "is what the invoice shows, what the ledger records and what the "
                           "customer pays; a difference between them is a defect regardless of "
                           "which of the three is closer to the calculated value")
        yaml.safe_dump(body, open(os.path.join(target, body["id"] + ".yaml"), "w",
                                  encoding="utf-8"), sort_keys=False)
        twin = dict(body, id="%s-0002" % item_type)
        found = [row["id"] for row in report.similar_items(state, item_type, twin)]
        (covered if item_type in HASHED_FIELDS else uncovered).append((item_type, found))
    assert covered and all(found == ["%s-0001" % t] for t, found in covered), covered
    assert uncovered and all(found == [] for _t, found in uncovered), uncovered


def test_an_invariant_whose_check_resolves_to_no_test_is_an_error_and_a_resolving_one_is_not(
        tmp_path):
    """FR-0039/II.12, the validator half: three states, and only one of them stops a merge.

    An invariant is what a project's guards read to decide which code they govern, so one whose
    check names no test is a rule with nothing behind it -- an ERROR, which is what makes it a
    merge blocker (`gate_memory_complete.state_errors`; measured through the real hook in
    `test_hooks.test_an_invariant_whose_check_names_no_test_blocks_the_merge`).

    The other two are deliberately NOT errors: a check that resolves while the item still reads
    `unverified` is bookkeeping, so it is a warning naming the command that fixes it, and a
    verified item with a resolving check is silent. An error there would block every merge of
    every project the day it captured its first invariant.
    """
    root = tmp_path / "project_memory"
    root.mkdir()
    st = ProjectState(str(root))
    st.capture("PR", dict(PR_FIELDS))
    inv = st.capture("INV", {"scope": "compounder/", "source": "PR-0001", "text": "pure",
                             "check": {"kind": "test", "ref": "tests/test_rules.py::test_pure"}})
    blocking = [f for f in errors(report.validate_state(st)) if f["item"] == inv["id"]]
    assert blocking, report.validate_state(st)
    assert "does not exist" in blocking[0]["message"]
    assert "verify-invariants" in blocking[0]["remedy"]

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_rules.py").write_text(
        "def test_pure():\n    pass\n", encoding="utf-8")
    findings = report.validate_state(st)
    assert not [f for f in errors(findings) if f["item"] == inv["id"]], findings
    stale = [f for f in findings if f["item"] == inv["id"]]
    assert stale and stale[0]["severity"] == "warning"
    assert "verify-invariants" in stale[0]["remedy"]

    st.record_invariant_verification(inv["id"])
    assert not [f for f in report.validate_state(st) if f["item"] == inv["id"]]


def test_an_invariant_whose_check_this_kernel_cannot_read_blocks_nothing(tmp_path):
    """The third answer, and the reason it exists: a rule nobody can satisfy is not a rule.

    The kernel decides "is this test there" by PARSING the file, and that reaches Python. A dev
    project whose tests are TypeScript would otherwise have every one of its invariants reported
    as unverifiable -- an ERROR, and `gate_memory_complete` blocks a push on those -- with no
    command in the project that could ever clear it. Measured while building this: with the
    unreadable case answered as "not resolved", exactly that happened.

    So the answer is UNDECIDED: a warning that says whose question it is, no error, and the
    producer leaves the item unverified rather than verifying it on a shrug. The limit is `H110`.
    """
    root = tmp_path / "project_memory"
    root.mkdir()
    st = ProjectState(str(root))
    st.capture("PR", dict(PR_FIELDS))
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "rules.test.ts").write_text("test('is pure', () => {});\n",
                                                    encoding="utf-8")
    inv = st.capture("INV", {"scope": "src/", "source": "PR-0001", "text": "pure",
                             "check": {"kind": "test", "ref": "src/rules.test.ts::is pure"}})
    findings = [f for f in report.validate_state(st) if f["item"] == inv["id"]]
    assert findings and findings[0]["severity"] == "warning", findings
    assert "cannot read as a test file" in findings[0]["message"]
    assert not errors(report.validate_state(st))

    item, resolved, reason = st.record_invariant_verification(inv["id"])
    assert item["status"] == "unverified", reason
    assert resolved is None, reason


def test_a_check_whose_test_is_skipped_resolves_to_nothing_it_can_run(tmp_path):
    """BUG-0193: a definition the runner is told not to execute counted as a check that exists.

    Three readings in one test, because the whole point is WHO decides. A `skip` marker and a
    parametrisation with no cases are decided by the SOURCE, so the check does not resolve and the
    validator blocks -- and a module-level `pytestmark` carries the same declaration for every test
    in the file. A `skipif` is decided by the runner when it evaluates the condition, so the answer
    is the module's third one, undecided, and no merge is blocked on it. The counterweight is the
    plain test in the same file: a reader that called everything unrunnable would satisfy the first
    three assertions and break every project.
    """
    root = tmp_path / "project_memory"
    root.mkdir()
    st = ProjectState(str(root))
    st.capture("PR", dict(PR_FIELDS))
    (tmp_path / "tests").mkdir()

    def write(body):
        (tmp_path / "tests" / "test_rules.py").write_text(body, encoding="utf-8")

    def resolution(ref):
        return report.invariant_check_resolution(st, {"check": {"kind": "test", "ref": ref}})

    write("import pytest\n\n\n"
          "@pytest.mark.skip(reason='flaky')\n"
          "def test_skipped():\n    pass\n\n\n"
          "@pytest.mark.skipif(sys.platform == 'win32', reason='posix')\n"
          "def test_conditional():\n    pass\n\n\n"
          "@pytest.mark.parametrize('case', [])\n"
          "def test_no_cases(case):\n    pass\n\n\n"
          "def test_plain():\n    pass\n")
    resolved, reason = resolution("tests/test_rules.py::test_skipped")
    assert resolved is False and "skip" in reason, reason
    resolved, reason = resolution("tests/test_rules.py::test_no_cases")
    assert resolved is False and "empty case list" in reason, reason
    resolved, reason = resolution("tests/test_rules.py::test_conditional")
    assert resolved is None and "runner evaluates" in reason, reason
    assert resolution("tests/test_rules.py::test_plain")[0] is True

    # ...and the declaration that stands once for the whole file reaches every test in it
    write("import pytest\n\npytestmark = pytest.mark.skip(reason='whole file')\n\n\n"
          "def test_plain():\n    pass\n")
    resolved, reason = resolution("tests/test_rules.py::test_plain")
    assert resolved is False and "skip" in reason, reason

    # ...and a decorator of the project's OWN that merely ends in the same word is not a marker
    write("def skip(fn):\n    return fn\n\n\n@skip\ndef test_plain():\n    pass\n")
    assert resolution("tests/test_rules.py::test_plain")[0] is True

    inv = st.capture("INV", {"scope": "tests/", "source": "PR-0001", "text": "pure",
                             "check": {"kind": "test", "ref": "tests/test_rules.py::test_plain"}})
    write("import pytest\n\n\n@pytest.mark.skip\ndef test_plain():\n    pass\n")
    blocking = [f for f in errors(report.validate_state(st)) if f["item"] == inv["id"]]
    assert blocking and "does not execute" in blocking[0]["message"], report.validate_state(st)


def test_a_hand_edited_diagram_is_reported_and_a_missing_one_is_not(tmp_path):
    """BUG-0211: `plan_diagram.is_pristine` had no caller but its own test, so nobody was told.

    Three states, three answers, in one test because a reader that reported everything would
    satisfy the first two and make every project noisy. A freshly written store is SILENT; a hand
    edit is a warning that says the next write takes it away; a picture rendered from a state that
    has moved on is a warning of its own, because between two writes a reader is looking at a plan
    the store no longer holds. Never an error: nothing about the STATE is wrong in either case.
    """
    root = tmp_path / "project_memory"
    root.mkdir()
    st = ProjectState(str(root))

    # ...a store with no generated picture is not judged at all
    assert [f for f in report.validate_state(st) if f["item"] == "generated"] == []

    st.capture("PR", dict(PR_FIELDS))
    assert [f for f in report.validate_state(st) if f["item"] == "generated"] == [], (
        "a freshly written store is silent")

    picture = os.path.join(st.generated_path(""), plan_diagram.PLAN_FILENAME)
    with open(picture, encoding="utf-8") as handle:
        rendered = handle.read()
    with open(picture, "w", encoding="utf-8") as handle:
        handle.write(rendered.replace("</svg>", "<!-- moved a box in draw.io --></svg>"))
    edited = [f for f in report.validate_state(st) if f["item"] == "generated"]
    assert len(edited) == 1 and edited[0]["severity"] == "warning", edited
    assert "edited by hand" in edited[0]["message"] and "save the edit" in edited[0]["remedy"]

    # ...and the same bytes against a state that has moved on are the OTHER warning
    _rows, entries = st.board_entries()
    with open(picture, "w", encoding="utf-8") as handle:
        handle.write(dict(plan_diagram.render_all(entries))[plan_diagram.PLAN_FILENAME])
    st.capture("PR", dict(PR_FIELDS))
    with open(picture, "w", encoding="utf-8") as handle:
        handle.write(dict(plan_diagram.render_all(entries))[plan_diagram.PLAN_FILENAME])
    stale = [f for f in report.validate_state(st) if f["item"] == "generated"]
    assert len(stale) == 1 and stale[0]["severity"] == "warning", stale
    assert "older than the state it shows" in stale[0]["message"]
    assert not errors(report.validate_state(st)), "neither verdict blocks a merge"


def test_a_board_that_could_not_be_rewritten_is_reported_as_older_than_the_index(tmp_path):
    """BUG-0140: a page the operating system would not let the kernel replace froze the display.

    The write is fail-soft on purpose -- a viewer holding the file open must not fail a state
    write -- and it says so ONCE, on stderr, in the session that hit it. This is the standing line
    the item names as its closing direction, and it fails in the harmless direction: a warning, so
    no merge is blocked on a picture.

    The counterweight is the freshly written store in the same test: a reader that reported every
    board would make every project noisy, and a store with no page at all is not judged.
    """
    root = tmp_path / "project_memory"
    root.mkdir()
    st = ProjectState(str(root))
    st.capture("PR", dict(PR_FIELDS))
    assert [f for f in report.validate_state(st) if f["item"] == "generated"] == [], (
        "a board written with the index is silent")

    page = st.generated_path(board.FILENAME)
    index = st.generated_path("index.yaml")
    os.utime(page, (os.path.getmtime(index) - 60, os.path.getmtime(index) - 60))
    stale = [f for f in report.validate_state(st)
             if f["item"] == "generated" and board.FILENAME in f["message"]]
    assert len(stale) == 1 and stale[0]["severity"] == "warning", stale
    assert "older than" in stale[0]["message"] and "index.yaml" in stale[0]["message"]
    assert not errors(report.validate_state(st)), "a frozen display blocks no merge"

    os.remove(page)
    assert [f for f in report.validate_state(st)
            if f["item"] == "generated" and board.FILENAME in f["message"]] == []


def test_an_unreadable_file_in_the_archive_is_a_finding_and_not_a_silence(tmp_path):
    """BUG-0236, second residue: a stored item whose YAML broke vanished from every reader.

    The active walk reports a corrupt item and never reaches the archive; the walk that does reach
    it is asked for ITEMS and skips what it cannot read. Measured on H156 with its YAML destroyed:
    all three hole checkers exited 0 and said nothing.

    The counterweight is the second half of the same test: a broken ACTIVE item is reported ONCE,
    not twice, because the two walks would otherwise both claim it.
    """
    root = tmp_path / "project_memory"
    root.mkdir()
    st = ProjectState(str(root))
    pr = st.capture("PR", dict(PR_FIELDS))
    dec = st.capture("DEC", dict(DEC_FIELDS))
    st.archive(dec["id"])

    archived = [path for path in st._walk_stored_files() if os.path.basename(path).startswith("DEC")]
    assert len(archived) == 1, archived
    with open(archived[0], "w", encoding="utf-8") as handle:
        handle.write("id: DEC-0001\n  broken: [unclosed\n")
    found = [f for f in report.validate_state(st) if "does not read" in f["message"]]
    assert len(found) == 1 and found[0]["severity"] == "error", report.validate_state(st)
    assert "dec" in found[0]["message"].lower()

    active = os.path.join(st.root, "product", "active", pr["id"] + ".yaml")
    with open(active, "w", encoding="utf-8") as handle:
        handle.write("id: PR-0001\n  broken: [unclosed\n")
    about_the_root = [f for f in report.validate_state(st) if f["item"] == pr["id"]]
    assert len(about_the_root) == 1, about_the_root
    assert "corrupt item file" in about_the_root[0]["message"], about_the_root


def test_an_item_file_too_big_to_open_is_reported_and_is_not_opened(tmp_path):
    """The bound on the stored-file walk, at BOTH ends: not opened, and not silent either.

    THE DEFECT THIS CLOSES was found by the generation-6 merge full run, one reader against
    another: `state._walk_stored_files` opened EVERY stored `*.yaml` for
    `unreadable_stored_files`, while the document scan in this same validator was refusing to open
    the very same over-sized file and saying why -- so a business export in the state directory was
    read in full on every merge, on a hook path with a time budget
    (`tools/test_migrate.py::test_the_two_remedies_that_still_move_a_file_differ_in_whether_the_file_was_read`
    is the node that caught it).

    BOTH ENDS, because either alone is passed by a broken reader: the file is NOT opened (asked of
    the walk itself, which is what does the opening), and it IS reported by name with the remedy the
    bound implies -- a skip nobody reports is the silence the walk exists against. The subject is an
    ARCHIVED item, because that is the one class no other reader of this validator reaches.
    """
    root = tmp_path / "project_memory"
    root.mkdir()
    st = ProjectState(str(root))
    st.capture("PR", dict(PR_FIELDS))
    dec = st.capture("DEC", dict(DEC_FIELDS))
    st.archive(dec["id"])
    archived = [path for path in st._walk_stored_files()
                if os.path.basename(path).startswith("DEC")]
    assert len(archived) == 1, archived
    with open(archived[0], "a", encoding="utf-8") as handle:
        handle.write("padding: |\n" + "  an export nobody meant to put here\n" * 60000)
    assert os.path.getsize(archived[0]) > report.DOCUMENT_MAX_BYTES, os.path.getsize(archived[0])

    assert archived[0] not in list(st._walk_stored_files()), (
        "the walk that OPENS what it yields still yields a file over the bound")
    assert [path for path, _size in st.oversized_stored_files()] == [archived[0]], \
        st.oversized_stored_files()
    reported = [f for f in report.validate_state(st) if "was NOT READ" in f["message"]]
    assert len(reported) == 1 and reported[0]["severity"] == "error", report.validate_state(st)
    assert dec["id"] in reported[0]["item"], reported[0]
    assert "state directory" in reported[0]["remedy"], reported[0]


def test_a_staging_dir_an_active_record_points_into_is_not_an_orphan(tmp_path):
    """BUG-0032: the orphan heuristic asked the directory's NAME and not the store's references.

    An Evidence's `artifact_refs` is where its raw proof lives -- the record IS the pointer -- so
    reporting the directory as orphaned tells a reader to remove what the record stands for. The
    case is live rather than hypothetical: the generation-6 streams wrote
    `staging/<task-id>/protocol.md` into their evidence, and every one of those directories became
    an "orphan" the moment its task closed.

    THREE ROWS, because a reader that stopped warning would be as wrong as the one that warned at
    everything: a directory nobody points into is still an orphan, a directory whose item is active
    is silent as before, and a directory an ACTIVE record points into is silent with the pointer as
    the reason. A mention in PROSE is deliberately not a reference -- the last row holds that end.
    """
    root = tmp_path / "project_memory"
    root.mkdir()
    st = ProjectState(str(root))
    pr = st.capture("PR", dict(PR_FIELDS))

    def orphans():
        return sorted(f["item"] for f in report.validate_state(st) if "orphaned staging" in f["message"])

    for key in ("TSK-0999", "TSK-0998", "TSK-0997"):
        os.makedirs(os.path.join(st.staging_root(), key), exist_ok=True)
    assert orphans() == ["staging/TSK-0997", "staging/TSK-0998", "staging/TSK-0999"]

    st.capture("EVD", {"kind": "test", "related": [pr["id"]], "result": "pass",
                       "summary": "the round's protocol",
                       "artifact_refs": ["staging/TSK-0999/protocol.md"]})
    assert orphans() == ["staging/TSK-0997", "staging/TSK-0998"], "the pointer holds the directory"

    st.capture("EVD", {"kind": "test", "related": [pr["id"]], "result": "pass",
                       "summary": "names staging/TSK-0998/protocol.md in prose only",
                       "artifact_refs": ["staging/TSK-0999/protocol.md"]})
    assert orphans() == ["staging/TSK-0997", "staging/TSK-0998"], (
        "a mention in prose is not a reference")


def test_the_brief_counts_the_qa_runs_by_the_scope_they_declare(tmp_path):
    """BUG-0190: "how often did the suite run, and over how much" was prose in a role text.

    The reason given for leaving it there was that an `EVD` is immutable -- true of the RECORD, and
    nothing about a ROLLUP. Every record already declares its run scope (`RUN_SCOPES`), so the
    number is a derivation over what the store holds, exactly like every other rollup this module
    makes, and it lands where a lead and the user meet the project: the session brief.

    THREE BUCKETS AND THE THIRD IS THE POINT: a record that declares NO scope is counted apart
    rather than folded into `full`, because that silence is BUG-0192 and a rollup that hid it would
    be the second place where an undeclared run counts as a whole one. The counterweight is the
    AUDIT evidence in the same store: it judges the project and not a delivery, so it is not a QA
    run and must not be counted.
    """
    root = tmp_path / "project_memory"
    root.mkdir()
    st = ProjectState(str(root))
    pr = st.capture("PR", dict(PR_FIELDS))

    def evidence(**overrides):
        body = {"kind": "test", "related": [pr["id"]], "result": "pass", "summary": "a run",
                "artifact_refs": ["staging/x/report.md"]}
        body.update(overrides)
        st.capture("EVD", body)

    evidence(run_command="pytest tools/", run_scope="full")
    evidence(run_command="pytest tools/", run_scope="full")
    evidence(run_command="pytest tools/test_report.py::test_x", run_scope="selection")
    evidence()
    evidence(kind="audit", summary="a project audit")

    brief = yaml.safe_load(open(report.generate_session_brief(st, "dev-team", "x", "hard"),
                                encoding="utf-8"))
    assert brief["budget_status"]["qa_runs"] == {"full": 2, "selection": 1, "undeclared": 1}, brief


def test_no_new_evidence_can_stay_silent_about_the_run_it_records(tmp_path, capsys):
    """BUG-0192: an Evidence that declares no run scope counts as a full run, in silence.

    The READING end cannot be tightened: an `EVD` is immutable, so demanding the declaration of
    records a project already holds turns each of them into a validator error no command can
    repair. What is left is the surface that records NEW ones, and that is the parser -- a partial
    run can no longer open a merge by saying nothing, because it can no longer be recorded saying
    nothing.

    THE SHIPPED PARSER IS WHAT IS ASKED, not a copy of its argument list: `build_parser` is the
    object argparse evaluates, and the run below drives `cli.main` so the refusal measured is the
    one a role meets. The counterweight is the second half: the same call WITH both flags is
    accepted, so this is a duty and not a wall.
    """
    required = {action.option_strings[0]
                for action in cli.build_parser()._subparsers._group_actions[0]
                .choices["evidence"]._actions if action.option_strings and action.required}
    assert {"--run-command", "--run-scope"} <= required, required

    root = tmp_path / "project_memory"
    root.mkdir()
    st = ProjectState(str(root))
    pr = st.capture("PR", dict(PR_FIELDS))
    silent = ["--root", st.root, "evidence", "--kind", "test", "--result", "pass",
              "--related", pr["id"], "--summary", "a run", "--artifact-ref", "staging/x/report.md"]

    with pytest.raises(SystemExit) as refused:
        cli.main(list(silent))
    assert refused.value.code != 0
    assert "--run-scope" in capsys.readouterr().err

    assert cli.main(silent + ["--run-command", "pytest tools/test_report.py::test_x",
                              "--run-scope", "selection"]) == 0
    assert "EVD-0001" in capsys.readouterr().out


def test_one_scan_parses_each_test_file_once(tmp_path, monkeypatch):
    """`validate_state` runs inside a merge gate, so what it costs is not a detail.

    Invariants of one project point at the same few test files, and the resolution parses the file
    the check names. Measured without the cache: 30 invariants against one 0.5 MB test file cost
    6.1-6.9 s per scan; with it, 0.22-0.26 s. The kits register NO timeout for the gate that waits
    for this (measured on a scaffolded project), and a hook the provider kills reads as "carry on"
    -- so the cost is an enforcement question, not a comfort one.

    Counted at `ast.parse` itself rather than timed: a stopwatch measures the machine, a call
    count measures the rule.
    """
    root = tmp_path / "project_memory"
    root.mkdir()
    st = ProjectState(str(root))
    st.capture("PR", dict(PR_FIELDS))
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_rules.py").write_text(
        "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n\n\ndef test_c():\n    pass\n",
        encoding="utf-8")
    for name in ("a", "b", "c"):
        st.capture("INV", {"scope": "%s/" % name, "source": "PR-0001", "text": "rule %s" % name,
                           "check": {"kind": "test",
                                     "ref": "tests/test_rules.py::test_%s" % name}})
    parses = []
    real = report.ast.parse

    def counted(*args, **kwargs):
        parses.append(kwargs.get("filename") or (args[1] if len(args) > 1 else "?"))
        return real(*args, **kwargs)

    monkeypatch.setattr(report.ast, "parse", counted)
    findings = report.validate_state(st)
    assert not errors(findings), findings
    mine = [one for one in parses if str(one).endswith("test_rules.py")]
    assert len(mine) == 1, mine


def test_orphaned_staging_flagged(state):
    os.makedirs(os.path.join(state.root, "staging", "TSK-0099"))
    findings = report.validate_state(state)
    assert any("orphaned staging" in f["message"] for f in findings)


def test_dangling_reference_flagged(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    dispatch.create_task(state, {
        "product_requirement": pr["id"], "derives_from": pr["id"],
        "type": "implementation", "assigned_role": "backend-developer",
        "acceptance_refs": ["AC-1"], "required_inputs": [],
        "allowed_scope": ["src/"], "forbidden_scope": [],
        "expected_outputs": ["out"], "dependencies": ["TSK-1234"],
    })
    found = errors(report.validate_state(state))
    assert any("TSK-1234" in f["message"] for f in found)


def test_a_scalar_dependency_is_reported_once_not_once_per_letter(state):
    """BUG-0015 on the validator's half of `dependencies`: the field itself was iterated.

    A missing dependency written as a bare string became ONE FINDING PER LETTER — `dependency T
    does not exist`, `dependency S does not exist`, and so on for every character — which buries
    the one real finding under a wall and makes the count meaningless. Counted rather than
    matched: `any("TSK-1234" in ...)` stays green while eight bogus findings stand beside it."""
    pr = state.capture("PR", dict(PR_FIELDS))
    dispatch.create_task(state, {
        "product_requirement": pr["id"], "derives_from": pr["id"],
        "type": "implementation", "assigned_role": "backend-developer",
        "acceptance_refs": ["AC-1"], "required_inputs": [],
        "allowed_scope": ["src/"], "forbidden_scope": [],
        "expected_outputs": ["out"], "dependencies": "TSK-1234",
    })
    about_dependencies = [f for f in errors(report.validate_state(state))
                          if "dependency" in f["message"]]
    assert len(about_dependencies) == 1, about_dependencies
    assert "TSK-1234" in about_dependencies[0]["message"]


def test_staging_dir_keyed_by_active_root_not_flagged(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    os.makedirs(os.path.join(state.root, "staging", pr["id"]))
    assert not any("orphaned staging" in f["message"] for f in report.validate_state(state))


def test_terminal_unarchived_item_warned(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    state.transition(pr["id"], "REJECTED")
    findings = report.validate_state(state)
    assert any("awaiting archive" in f["message"] and pr["id"] == f["item"] for f in findings)


def test_related_pr_to_archived_item_is_no_error(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    state.transition(pr["id"], "REJECTED")
    state.archive(pr["id"])
    state.capture("BUG", {
        "title": "regression", "related_pr": pr["id"], "observed": "x",
        "expected": "y", "repro": "steps", "severity": "high",
        "acceptance_criteria": [{"id": "AC-1", "text": "fixed"}],
    })
    assert not any("related_pr" in f["message"] for f in errors(report.validate_state(state)))


def test_a_parent_binding_pointing_nowhere_is_an_error_for_every_type_that_has_one(state):
    """The reference-graph layer judged three field names and `derives_from` was not one.

    So an `SR`, `HYP` or `EXP` bound to an id that exists nowhere was reported by NOBODY -- in
    the layer whose entire job is the reference graph. The kernel refuses such a binding at
    capture, which is why each item here is written the only way one can exist: by hand, past
    the kernel. That is exactly the case a validator is for.

    Asserted over `PARENT_FIELDS` rather than over the types that had a binding when this was
    written, because "a type nobody added to the list" is the defect itself.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    expected = set()
    for item_type, fields in sorted(PARENT_FIELDS.items()):
        for number, field in enumerate(fields, start=1):
            item_id = "%s-%04d" % (item_type, number)
            item = {"id": item_id, field: "PR-0099"}
            item.update({other: root["id"] for other in fields if other != field})
            os.makedirs(os.path.dirname(state.active_path(item_id)), exist_ok=True)
            state._write_yaml_atomic(state.active_path(item_id), item)
            expected.add((item_id, field))
    # ` -> ` is the reference check's own message shape, and reading it is what keeps this
    # measuring THAT check: the origin check speaks about the same hand-written items in prose
    # ("... names no parent binding at all ..."), and without the shape its whole sentence
    # arrived here as a field name.
    reported = {(f["item"], field) for f in errors(report.validate_state(state))
                for field in [f["message"].split(" ->")[0]]
                if "PR-0099" in f["message"] and " ->" in f["message"]}
    assert reported == expected, (
        "the validator judged %s of the parent bindings; %s went unreported"
        % (sorted(reported), sorted(expected - reported)))


# -- session brief -------------------------------------------------------------

def test_session_brief_generated_and_schema_valid(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", pr["id"])  # left open
    path = report.generate_session_brief(state, "dev-team", "2026.07.24-rc1", "audited")
    brief = yaml.safe_load(open(path, encoding="utf-8"))
    assert brief["active_roots"][0]["id"] == pr["id"]
    assert brief["active_roots"][0]["next_step"] == "Scope-Freigabe einholen"
    assert brief["open_approvals"][0]["request_id"] == request["request_id"]
    assert brief["enforcement_mode"] == "audited"


def test_session_brief_reports_validator_budget(state):
    state.capture("PR", dict(PR_FIELDS, problem="x" * 13000))
    path = report.generate_session_brief(state, "dev-team", "v", "audited")
    brief = yaml.safe_load(open(path, encoding="utf-8"))
    assert brief["budget_status"]["validator_errors"] >= 1


def test_expired_request_not_listed_as_open(state):
    import time as _time
    pr = state.capture("PR", dict(PR_FIELDS))
    approvals.create_pending_request(state, "scope", pr["id"], ttl_seconds=0.01)
    _time.sleep(0.05)
    path = report.generate_session_brief(state, "dev-team", "v", "audited")
    brief = yaml.safe_load(open(path, encoding="utf-8"))
    assert brief["open_approvals"] == []
    assert brief["budget_status"]["expired_requests"] == 1


def test_the_session_brief_shows_the_rung_and_effort_a_lease_wrote_on_the_task(state):
    """PR-0010 AC-6, the brief half (DEC-0077 (5)), and the measurement that closes BUG-0249 /
    H167: the values the lease wrote on the task reach the row a lead reads, and a task that was
    never dispatched carries no invented ones.

    MEASURED 2026-09-06 on a dev pilot before this line existed: the task item
    carried `rung: fable` / `effort: xhigh` and the freshly generated brief's row carried `id`,
    `status`, `assigned_role` and nothing else. The stream that built the lease (TSK-0130) was
    forbidden `kernel/report.py` by its own item, so the line and this test are the merge's.

    The field names are the dispatcher's own (`dispatch.LEASE_RUNG_FIELD` / `LEASE_EFFORT_FIELD`
    for what the lease derived, `RUNG_KEY` / `EFFORT_KEY` for what the PM asked, DEC-0091), read
    rather than spelled here, so a renamed key moves this test with it instead of leaving it green.
    """
    from kernel.dispatch import EFFORT_KEY, LEASE_EFFORT_FIELD, LEASE_RUNG_FIELD, RUNG_KEY
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    dispatched = make_task(state, root["id"], bug["id"])
    asked = make_task(state, root["id"], bug["id"], **{RUNG_KEY: "opus", EFFORT_KEY: "xhigh"})
    idle = make_task(state, root["id"], bug["id"])
    # the shape `create_lease` leaves behind, written the way the lease writes it -- on the item
    path = state.active_path(dispatched["id"])
    stored = state._read_yaml(path)
    stored[LEASE_RUNG_FIELD], stored[LEASE_EFFORT_FIELD] = "opus", "xhigh"
    state._write_yaml_atomic(path, stored)

    brief = yaml.safe_load(open(report.generate_session_brief(state, "dev-team", "v", "audited"),
                                encoding="utf-8"))
    rows = {row["id"]: row for row in brief["active_tasks"]}
    assert rows[dispatched["id"]][LEASE_RUNG_FIELD] == "opus", rows[dispatched["id"]]
    assert rows[dispatched["id"]][LEASE_EFFORT_FIELD] == "xhigh", rows[dispatched["id"]]
    assert (rows[asked["id"]][RUNG_KEY], rows[asked["id"]][EFFORT_KEY]) == ("opus", "xhigh"), (
        "the PM's ask does not reach the row: %s" % rows[asked["id"]])
    assert LEASE_RUNG_FIELD not in rows[asked["id"]], "an ask nobody leased shows a lease answer"
    for key in (RUNG_KEY, EFFORT_KEY, LEASE_RUNG_FIELD, LEASE_EFFORT_FIELD):
        assert key not in rows[idle["id"]], (
            "a task nobody dispatched shows a rung or an effort it was never given: %s"
            % rows[idle["id"]])


def test_the_session_brief_carries_the_lease_distribution_line(state):
    """DEC-0092 (4) with DEC-0097 (4): the brief shows the last-N leases as the habit they reveal --
    builders per goal, and per RUNG and per EFFORT both the count and the runs to the hand-back --
    and says "no lease yet" instead of showing zeros.

    The rows are written in the shape `create_lease` leaves on a task (the three `LEASE_*` fields
    plus `leased_at` and `failed_runs`), one of them ARCHIVED, because the reading has to outlive
    the lease and the active tray. RED WITHOUT `lease_distribution` in the brief: the schema is
    strict and the key is required, so the brief refuses to validate -- and RED with the archive
    half dropped: the archived order's rung is missing from `rungs`.

    THE EFFORT HALF IS NOT THE RUNG HALF UNDER ANOTHER NAME, and the rows are cut so that it
    cannot be: the two archived-and-done orders share a rung but not an effort, so `high 2.0,
    xhigh 1.0` is a grouping no rung-keyed counter can produce. RED WITHOUT the second axis
    (DEC-0097 (4)): `efforts` and `runs_to_hand_back_per_effort` are absent from the section and
    the line names neither.
    """
    from kernel.dispatch import FAILED_RUNS, LEASE_CLASS_FIELD, LEASE_EFFORT_FIELD, LEASE_RUNG_FIELD

    empty = yaml.safe_load(open(report.generate_session_brief(state, "dev-team", "v", "audited"),
                                encoding="utf-8"))
    assert empty["lease_distribution"]["orders"] == 0
    assert "no lease" in empty["lease_distribution"]["line"], empty["lease_distribution"]

    root = state.capture("PR", dict(PR_FIELDS))
    second = state.capture("PR", dict(PR_FIELDS, title="second goal"))
    bug = make_bug(state, root["id"])
    rows = [
        (make_task(state, root["id"], bug["id"]), "sonnet", "high", "build", "2026-09-01T10:00:00", 1, "DONE"),
        (make_task(state, root["id"], bug["id"]), "fable", "xhigh", "build", "2026-09-01T11:00:00", 0, "DONE"),
        (make_task(state, root["id"], bug["id"]), "opus", "xhigh", "qa", "2026-09-01T12:00:00", 0, "IN_PROGRESS"),
        (make_task(state, second["id"], second["id"]), "sonnet", "xhigh", "build", "2026-09-02T10:00:00", 0, "VALIDATED"),
    ]
    for task, rung, effort, role_class, at, failed, status in rows:
        path = state.active_path(task["id"])
        stored = state._read_yaml(path)
        stored.update({LEASE_RUNG_FIELD: rung, LEASE_EFFORT_FIELD: effort, LEASE_CLASS_FIELD: role_class,
                       "leased_at": at, FAILED_RUNS: failed, "status": status})
        state._write_yaml_atomic(path, stored)
    state.archive(rows[-1][0]["id"])

    brief = yaml.safe_load(open(report.generate_session_brief(state, "dev-team", "v", "audited"),
                                encoding="utf-8"))
    shown = brief["lease_distribution"]
    assert shown["orders"] == 4 and shown["goals_with_builders"] == 2, shown
    assert shown["builders_per_goal"] == {"2": 1, "1": 1}, shown
    assert shown["rungs"] == {"sonnet": 2, "fable": 1, "opus": 1}, shown
    assert shown["efforts"] == {"high": 1, "xhigh": 3}, shown
    # sonnet: the DONE order needed 2 runs, the archived VALIDATED one 1 -> mean 1.5; the QA order
    # is still running and counts for no rung's runs
    assert shown["runs_to_hand_back_per_rung"] == {"sonnet": 1.5, "fable": 1.0}, shown
    # the same four orders grouped by the OTHER axis, and the groups do not coincide: the two
    # sonnet orders sit on different efforts, so no rung-keyed counter yields these two means
    assert shown["runs_to_hand_back_per_effort"] == {"high": 2.0, "xhigh": 1.0}, shown
    assert "4 order(s)" in shown["line"] and "2 builder(s) x 1 goal(s)" in shown["line"], shown["line"]
    assert "runs to hand-back per rung fable 1.0, sonnet 1.5" in shown["line"], shown["line"]
    assert "efforts high x 1, xhigh x 3" in shown["line"], shown["line"]
    assert "per effort high 2.0, xhigh 1.0" in shown["line"], shown["line"]


# -- doctor --------------------------------------------------------------------

def test_doctor_reports_lock_leases_and_findings(state):
    """The expiry half waits for the PREDICATE `report.doctor` reads, not for a duration.

    A 10 ms TTL and an immediate call is a race the fast host loses: the hosted ubuntu runner
    reached that line inside the TTL and reported `expired: False` (BUG-0069). The lease says when
    it expires, so that is what is waited for.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", pr["id"])
    mint_via_hook(state, request)
    task = dispatch.create_task(state, {
        "product_requirement": pr["id"], "derives_from": pr["id"],
        "type": "implementation", "assigned_role": "backend-developer",
        "acceptance_refs": ["AC-1"], "required_inputs": [],
        "allowed_scope": ["src/"], "forbidden_scope": [],
        "expected_outputs": ["out"], "dependencies": [],
    })
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]), state.read_item(pr["id"]))
    lease = dispatch.create_lease(state, task["id"], ttl=0.01)
    expires_at = float(lease["created_epoch"]) + float(lease["ttl"])
    while time.time() <= expires_at:
        time.sleep(0.001)
    result = report.doctor(state, kit="dev-team", kit_version="rc1")
    assert result["lock"] == {"state": "free"}
    assert result["leases"][0]["task_id"] == task["id"]
    assert result["leases"][0]["expired"] is True
    assert result["index_present"] is True
    assert result["kit"] == "dev-team"


def test_doctor_reports_held_lock(state):
    state.lock.acquire(timeout=1)
    try:
        result = report.doctor(state)
        assert result["lock"]["held_by_pid"] == os.getpid()
    finally:
        state.lock.release()


def test_doctor_never_writes_state(state):
    state.capture("PR", dict(PR_FIELDS))
    before = {}
    for base, _dirs, files in os.walk(state.root):
        for name in files:
            p = os.path.join(base, name)
            before[p] = os.path.getmtime(p)
    report.doctor(state)
    after = {}
    for base, _dirs, files in os.walk(state.root):
        for name in files:
            p = os.path.join(base, name)
            after[p] = os.path.getmtime(p)
    assert before == after  # read-only: no file added, removed or touched


# -- step 7: the graph duties the validator owns (spec II.4 gate 4) -----------

RQ_FIELDS = {
    "title": "Retry semantics", "class": "normal", "question": "How long should retries wait?",
    "motivation": "Throughput drops under load", "acceptance_criteria": ["measured"],
    "out_of_scope": ["ui"], "priority": "high",
}


def make_bug(state, root_id):
    return state.capture("BUG", {
        "title": "b", "related_pr": root_id, "observed": "o", "expected": "e", "repro": "r",
        "severity": "low", "acceptance_criteria": ["fixed"]})


def make_task(state, root_id, origin_id, **fields):
    root = state.read_item(root_id)
    return state.capture("TSK", dict({
        "product_requirement": root_id, "root_revision": root.get("revision"),
        "derives_from": [origin_id], "type": "bugfix", "assigned_role": "backend-developer",
        "acceptance_refs": ["AC-1"], "required_inputs": [], "allowed_scope": ["src/**"],
        "forbidden_scope": [], "expected_outputs": ["patch"], "dependencies": []}, **fields))


def warnings_of(findings):
    return [f for f in findings if f["severity"] == "warning"]


def test_a_modified_consumed_request_is_detected(state, tmp_path):
    """The ONE forgery `consumed_request` cannot detect arithmetically: the hash function is
    public, so a consistently re-hashed request verifies. It cannot hide from git — a minted
    request is immutable once written, and `approvals/**` is committed, so any diff on it IS the
    tampering. That turns the documented residual from "undetectable" into "detected at the next
    validate or merge"."""
    repo = os.path.dirname(state.root)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, timeout=60)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    item = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", item_id=item["id"])
    mint_via_hook(state, request)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, timeout=60)
    subprocess.run(["git", "commit", "-qm", "state"], cwd=repo, check=True, timeout=60)
    assert errors(report.validate_state(state)) == []

    consumed = os.path.join(state.root, "approvals", "consumed")
    name = sorted(os.listdir(consumed))[0]
    path = os.path.join(consumed, name)
    body = open(path, encoding="utf-8").read()
    open(path, "w", encoding="utf-8", newline="\n").write(body + "\ntampered: true\n")
    found = errors(report.validate_state(state))
    assert any("MODIFIED after it was minted" in f["message"] for f in found), found


def test_a_repo_without_git_says_nothing_about_consumed_requests(state):
    """The rule can only speak about files git is tracking — it must not turn "no git here" into
    a finding, or every scratch project would fail validation."""
    item = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", item_id=item["id"])
    mint_via_hook(state, request)
    assert errors(report.validate_state(state)) == []


def test_a_displayed_expiry_that_disagrees_with_the_request_is_an_error(state):
    """The APR copy is a DISPLAY value; the gate reads expiry only from the hash-covered manifest.
    When the two disagree a human reads a validity the gate correctly refuses — or believes an
    approval is still live when it is not."""
    item = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", item_id=item["id"])
    mint_via_hook(state, request)
    assert errors(report.validate_state(state)) == []
    apr_ref = state.read_item(item["id"])["approval_ref"]
    apr_path = os.path.join(state.root, "approvals", apr_ref + ".yaml")
    apr = yaml.safe_load(open(apr_path, encoding="utf-8"))
    apr["expires"] = 99999999999.0
    with open(apr_path, "w", encoding="utf-8", newline="\n") as fh:
        yaml.safe_dump(apr, fh, sort_keys=False, allow_unicode=True)
    found = errors(report.validate_state(state))
    assert any("hash-covered request says" in f["message"] for f in found), found


def test_a_task_deriving_from_another_roots_tree_is_an_error(state):
    """The dispatch gate resolves `acceptance_refs` against the ORIGIN, so an origin belonging to
    an unrelated root lets a task be judged against borrowed criteria. Authorisation is unaffected
    — that comes only from the root's approval — which is exactly why the mislabel survives the
    hot path and has to be caught by the graph walk."""
    root_a = state.capture("PR", dict(PR_FIELDS))
    root_b = state.capture("PR", dict(PR_FIELDS, title="Other root"))
    bug = make_bug(state, root_b["id"])
    task = make_task(state, root_a["id"], bug["id"])
    found = errors(report.validate_state(state))
    assert any(f["item"] == task["id"] and "belongs to" in f["message"] for f in found), found


def test_a_task_deriving_from_its_own_roots_tree_is_fine(state):
    """The counterpart, so the rule cannot decay into "no task may derive from anything"."""
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    make_task(state, root["id"], bug["id"])
    assert errors(report.validate_state(state)) == []


RQ_FIELDS = {
    "title": "Chunk size", "class": "normal",
    "question": "Does a dynamic chunk size lower the error rate?",
    "motivation": "every misfiling costs rework",
    "acceptance_criteria": [{"id": "AC-1", "text": "error rate of both arms with interval"}],
    "out_of_scope": [], "priority": "high",
}


def make_question(state, title="Chunk size"):
    return state.capture("RQ", dict(RQ_FIELDS, title=title))


def make_hypothesis(state, question_id):
    return state.capture("HYP", {
        "derives_from": question_id, "statement": "dynamic beats fixed",
        "testable_prediction": "at least 5 points lower, alpha = 0.05"})


def make_experiment(state, parents):
    return state.capture("EXP", {
        "derives_from": parents, "design": "within-subject over 400 documents",
        "variables": {"independent": ["chunking"], "dependent": ["error rate"]},
        "success_criteria": ["difference of the error rates with a 95% interval"],
        "evidence_refs": []})


def test_a_task_on_an_origin_two_levels_under_its_root_is_fine(state):
    """The research kit's own chain RQ -> HYP -> EXP -> TSK, on the validator side (BUG-0083).

    The dev kit cannot show this: every dev task origin sits ONE level under the root, which is
    why a check that resolved the single immediate parent passed there for a year and made the
    documented research chain uncreatable. Its refusing counterpart at creation is
    `test_approvals_dispatch.test_a_task_may_derive_from_an_experiment_two_levels_under_its_root`.
    """
    question = make_question(state)
    hypothesis = make_hypothesis(state, question["id"])
    experiment = make_experiment(state, hypothesis["id"])
    make_task(state, question["id"], experiment["id"])
    assert errors(report.validate_state(state)) == []


def test_an_origin_that_reaches_the_root_through_only_one_of_its_parents_is_refused(state):
    """Ambiguous parentage fails CLOSED -- the second half of the same two functions (BUG-0086).

    Measured before the fix on a scaffolded research project: an EXP with two parents resolved to
    NO root at all, both callers read that as "nothing to compare" and a task under a FOREIGN root
    was created with rc 0 and validated with zero errors. The finding names the parent that leaves
    the root, because "ambiguous" without it is not actionable.
    """
    question = make_question(state)
    other = make_question(state, title="Another question")
    hypothesis = make_hypothesis(state, question["id"])
    stray = make_hypothesis(state, other["id"])
    experiment = make_experiment(state, [hypothesis["id"], stray["id"]])
    task = make_task(state, question["id"], experiment["id"])
    found = errors(report.validate_state(state))
    mine = [f for f in found if f["item"] == task["id"] and "ambiguous origin" in f["message"]]
    assert mine, found
    assert stray["id"] in mine[0]["message"] and other["id"] in mine[0]["message"], mine


def test_an_origin_whose_only_parent_hangs_from_two_roots_is_refused(state):
    """The level the `all` in `_reaches_on_every_path` really guards -- and it had no test.

    `origin_root_conflict` walks the ORIGIN's own parents itself, so an origin with two parents is
    refused whatever the recursion does. The `all` starts deciding one level further in: an origin
    with a SINGLE parent whose own parentage straddles two roots. Measured 2026-09-02 with `any` in
    its place: seven modules, 645 passed -- nothing saw it.

    The message is measured too, because counting strays said both things at once here ("belongs to
    RQ-0001/RQ-0002, not to RQ-0001"): every parent strays, and the root is nevertheless among the
    ends. Which sentence is true is decided by where the paths END.
    """
    question = make_question(state)
    other = make_question(state, title="Another question")
    straddling = make_hypothesis(state, [question["id"], other["id"]])
    experiment = make_experiment(state, [straddling["id"]])
    conflict = report.origin_root_conflict(state, experiment["id"], question["id"])
    assert conflict, "an origin whose grandparent straddles two roots was accepted"
    assert "ambiguous origin" in conflict, conflict
    assert straddling["id"] in conflict and other["id"] in conflict, conflict
    assert "not to %s" % question["id"] not in conflict, conflict

    # ...and the same state seen through the validator, so the finding a role reads is the one
    task = make_task(state, question["id"], experiment["id"])
    mine = [f for f in errors(report.validate_state(state))
            if f["item"] == task["id"] and "ambiguous origin" in f["message"]]
    assert mine, report.validate_state(state)


def test_an_origin_whose_parents_all_hang_from_the_root_is_still_accepted(state):
    """The counter-direction of the ambiguity rule: several parents are not a defect by themselves.

    Without this the fail-closed half could be satisfied by refusing every multi-parent origin --
    and that would refuse the chain the research kit's own end-to-end test walks, where an
    experiment hangs from the hypothesis it tests AND the question that pays for it.
    """
    question = make_question(state)
    hypothesis = make_hypothesis(state, question["id"])
    experiment = make_experiment(state, [hypothesis["id"], question["id"]])
    make_task(state, question["id"], experiment["id"])
    assert errors(report.validate_state(state)) == []


def test_a_task_deriving_from_a_terminal_origin_is_flagged(state):
    """A task deriving from a REJECTED bug is stale: its criteria left the active context."""
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    task = make_task(state, root["id"], bug["id"])
    state.transition(bug["id"], "REJECTED")
    found = warnings_of(report.validate_state(state))
    assert any(f["item"] == task["id"] and "terminal" in f["message"] for f in found), found


def test_an_analyzed_experiment_without_evidence_is_incomplete(state):
    """R7 / parity row 84: "Report pro EXP sofort nach PASS; sonst incomplete." Without it the
    research loop can close an experiment whose result exists only in a chat message."""
    root = state.capture("RQ", dict(RQ_FIELDS))
    hyp = state.capture("HYP", {"statement": "s", "derives_from": root["id"],
                                "testable_prediction": "p"})
    exp = state.capture("EXP", {"derives_from": hyp["id"], "design": "d",
                                "variables": "v", "success_criteria": "c", "evidence_refs": []})
    walk_to_status(state, exp, "ANALYZED")
    found = errors(report.validate_state(state))
    assert any(f["item"] == exp["id"] and "ANALYZED without evidence_refs" in f["message"]
               for f in found), found


def test_a_decision_with_invalidation_triggers_asks_for_a_recheck(state):
    """R8 / parity row 87. A WARNING deliberately: whether a trigger actually FIRED is a judgement
    no pattern can make, and the user's "maximal härten" decision says heuristics warn and never
    fail closed."""
    state.capture("DEC", {"title": "d", "context": "c", "decision": "use X",
                          "consequences": "y", "source": "adr", "work": "none",
                          "premise_invalidation_triggers": ["throughput above 1k/s"]})
    item = state.capture("PR", dict(PR_FIELDS))
    walk_to_status(state, item, "APPROVED")
    found = warnings_of(report.validate_state(state))
    assert any("premise re-check" in f["message"] for f in found), found


def test_recording_the_recheck_clears_it(state):
    """...and recording the outcome — even "nothing changed" — is what clears it. A warning with
    no way to satisfy it is noise, and noise gets filtered out."""
    dec = state.capture("DEC", {"title": "d", "context": "c", "decision": "use X",
                                "consequences": "y", "source": "adr", "work": "none",
                                "premise_invalidation_triggers": ["throughput above 1k/s"]})
    item = state.capture("PR", dict(PR_FIELDS))
    walk_to_status(state, item, "APPROVED")
    state.update_item(item["id"], {"premise_rechecks": [dec["id"]]})
    found = warnings_of(report.validate_state(state))
    assert not [f for f in found if "premise re-check" in f["message"]], found


def test_a_premise_recheck_naming_a_phantom_is_flagged(state):
    """BUG-0004: `premise_rechecks` is written through the generic `update` path, which takes the
    value blind. A re-check that clears the warning with an id no decision carries is a claim resting
    on nothing, so the validator makes it an error -- the field's writer contract."""
    item = state.capture("PR", dict(PR_FIELDS))
    walk_to_status(state, item, "APPROVED")
    state.update_item(item["id"], {"premise_rechecks": ["DEC-9999"]})
    found = errors(report.validate_state(state))
    assert any(f["item"] == item["id"] and "DEC-9999" in f["message"] for f in found), found


def _fr_to(state, target):
    fr = state.capture("FR", {"title": "wish", "request_text": "please add X"})
    state.transition(fr["id"], "TRIAGED")
    if target != "TRIAGED":
        state.transition(fr["id"], target)
    return fr


def test_a_converted_fr_must_name_its_result(state):
    """BUG-0009(a): a CONVERTED request became another item; the state has to say WHICH. Without
    `resulting_item` the trail ends where "what came of this wish" begins."""
    fr = _fr_to(state, "CONVERTED")
    found = errors(report.validate_state(state))
    assert any(f["item"] == fr["id"] and "resulting_item" in f["message"] for f in found), found


def test_a_converted_fr_naming_its_result_is_clean(state):
    """...and naming a real item clears it. A duty with no way to satisfy it is noise."""
    pr = state.capture("PR", dict(PR_FIELDS))
    fr = _fr_to(state, "CONVERTED")
    state.update_item(fr["id"], {"resulting_item": pr["id"]})
    found = errors(report.validate_state(state))
    assert not [f for f in found if f["item"] == fr["id"]], found


def test_a_converted_fr_naming_a_phantom_result_is_flagged(state):
    """The named result must EXIST -- a link to a phantom is the same lie as no link."""
    fr = _fr_to(state, "CONVERTED")
    state.update_item(fr["id"], {"resulting_item": "PR-9999"})
    found = errors(report.validate_state(state))
    assert any(f["item"] == fr["id"] and "PR-9999" in f["message"] for f in found), found


# `work` is here because the capture door asks a NEW decision who carries it (DEC-0083); a fixture
# without it measures the refusal instead of the rule it was written for.
DEC_FIELDS = {"title": "d", "context": "c", "decision": "use X", "consequences": "y",
              "source": "adr", "work": "none"}


def test_a_superseding_decision_marks_the_older_one(state):
    """BUG-0009(b): DEC-A supersedes DEC-B, so "which decisions still hold" is answerable from the
    state -- B is superseded, A holds -- without anyone reading `context` prose."""
    old = state.capture("DEC", dict(DEC_FIELDS, title="old", decision="use X"))
    new = state.capture("DEC", dict(DEC_FIELDS, title="new", decision="use Y instead",
                                    supersedes=[old["id"]]))
    standing, superseded = report.standing_decisions(state)
    assert old["id"] not in standing
    assert new["id"] in standing
    assert superseded.get(old["id"]) == new["id"]


def test_a_superseded_decision_is_flagged_for_archive(state):
    """A DEC has no automaton, so nothing else moves a replaced decision out of the active context;
    the validator warns, the DEC analogue of "terminal item awaiting archive"."""
    old = state.capture("DEC", dict(DEC_FIELDS, title="old"))
    state.capture("DEC", dict(DEC_FIELDS, title="new", supersedes=[old["id"]]))
    found = warnings_of(report.validate_state(state))
    assert any(f["item"] == old["id"] and "superseded by" in f["message"] for f in found), found


def test_a_decision_superseding_a_phantom_is_flagged(state):
    """The superseded id must resolve to a real decision -- otherwise "which still hold" rests on a
    phantom. Backward-compatible: the field is optional, so a DEC that supersedes nothing is clean."""
    state.capture("DEC", dict(DEC_FIELDS, supersedes=["DEC-9999"]))
    found = errors(report.validate_state(state))
    assert any("DEC-9999" in f["message"] for f in found), found


def test_a_decision_superseding_nothing_stays_valid(state):
    """Every DEC captured before this field existed carries no `supersedes` and must stay clean."""
    state.capture("DEC", dict(DEC_FIELDS))
    assert errors(report.validate_state(state)) == []


# -- BUG-0038 / H43: the fields no capture contract declares --------------------

def test_a_scalar_supersedes_retires_the_decision_it_names(state):
    """`supersedes` written as a bare id, which is what "point it at the decision this one
    replaces" invites and what `capture`/`update` both take unchanged.

    MEASURED BEFORE THE FIX: `_superseded_decisions` iterated the value directly, so the eight
    LETTERS of `DEC-0001` became the superseded ids -- the replaced decision kept counting as
    holding in `standing_decisions` and in every session brief built on it, and
    `_check_dec_supersedes` filed eight errors naming `D`, `E`, `C`, `-`, `0`, `0`, `0`, `1`
    instead of resolving the one link.
    """
    old = state.capture("DEC", dict(DEC_FIELDS, title="old"))
    new = state.capture("DEC", dict(DEC_FIELDS, title="new", supersedes=old["id"]))
    standing, superseded = report.standing_decisions(state)
    assert superseded.get(old["id"]) == new["id"]
    assert old["id"] not in standing and new["id"] in standing
    assert errors(report.validate_state(state)) == []


def test_a_scalar_premise_recheck_is_one_recheck_not_its_letters(state):
    """The same class on `premise_rechecks`, and both of its readers.

    MEASURED BEFORE THE FIX: the existence check reported eight phantom errors (one per letter of
    the id), and the trigger check -- which asks whether the DEC is among the ids the item names --
    still warned "no premise re-check recorded", so recording the outcome did not clear the warning
    it exists to clear. Both halves are asserted here because they read the field separately.
    """
    dec = state.capture("DEC", dict(DEC_FIELDS,
                                    premise_invalidation_triggers=["throughput above 1k/s"]))
    item = state.capture("PR", dict(PR_FIELDS))
    walk_to_status(state, item, "APPROVED")
    state.update_item(item["id"], {"premise_rechecks": dec["id"]})
    found = report.validate_state(state)
    assert errors(found) == []
    assert not [f for f in warnings_of(found) if "premise re-check" in f["message"]], found


def test_validate_names_a_scalar_reference_list_field(state):
    """AC-4 of BUG-0038: the shape is named instead of passing silently.

    A WARNING and not an error, and that is the measurement rather than timidity: every kernel
    reader of these fields goes through `field_elements` now, so a scalar resolves as the one
    reference it spells and no gate decides differently. What it still is, is a shape the store
    should not carry -- so the validator names it and the remedy is the kernel's own edit path,
    because `project_memory/**` has no other writer.
    """
    dec = state.capture("DEC", dict(DEC_FIELDS))
    item = state.capture("PR", dict(PR_FIELDS))
    state.update_item(item["id"], {"premise_rechecks": dec["id"]})
    found = report.validate_state(state)
    named = [f for f in warnings_of(found)
             if f["item"] == item["id"] and "premise_rechecks is a single str" in f["message"]]
    assert named, found
    assert "update %s" % item["id"] in named[0]["remedy"]
    # ...and the list spelling of the SAME content is clean, or the check would be a warning
    # nobody can satisfy
    state.update_item(item["id"], {"premise_rechecks": [dec["id"]]})
    assert not [f for f in warnings_of(report.validate_state(state))
                if "is a single" in f["message"]]


def test_validate_names_design_refs_that_resolve_to_nothing(state):
    """The half the reader fix cannot reach: an item ALREADY written by the BUG-0038 chain.

    Its `design_refs` is a LIST -- of 34 one-letter entries -- so the shape check above passes it,
    and before this nothing else in `validate_state` looked at the field at all: the measured chain
    ended in "0 error(s), 0 warning(s)" over exactly that item while `dispatch` refused every UI
    task under it. The resolver is `dispatch._design_ref_resolves`, the one the II.6a tooth uses,
    so the validator and the gate cannot disagree about what resolves.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    state.update_item(pr["id"], {"design_refs": list("design/revisions/DSN-0001.r01.html")})
    found = errors(report.validate_state(state))
    named = [f for f in found if f["item"] == pr["id"] and "design_refs" in f["message"]]
    assert named, found
    assert "34 reference(s)" in named[0]["message"], named[0]["message"]
    # a really frozen reference resolves, so the check is not "any design_refs is an error"
    stage = staging.staging_dir(state, pr["id"])
    os.makedirs(stage, exist_ok=True)
    with open(os.path.join(stage, "preview.html"), "w", encoding="utf-8") as handle:
        handle.write("<html><body>x</body></html>")
    state.update_item(pr["id"], {"design_refs": []})
    staging.freeze_design(state, pr["id"], "DSN-0001", pr["id"], "preview.html")
    assert not [f for f in errors(report.validate_state(state)) if "design_refs" in f["message"]]


def test_validate_names_an_inv_scope_spelled_as_several_things(state):
    """H42's other half: the item the capture refusal came too late for (DEC-0043).

    THE FIXTURE IS WRITTEN PAST THE KERNEL ON PURPOSE, and that is not a shortcut: since
    `state._assert_single_value_fields` no door into the active store takes this body any more, so
    the only way a project HAS such an item is that it was written before the fix -- which is
    exactly the case under test. `_write_yaml_atomic` is the same call the neighbouring approval
    tests use to stage a state no current command produces.

    AN ERROR AND NOT A WARNING, unlike the reference-list shape beside it: a gate DECIDES
    DIFFERENTLY here (`gate_test_coverage` refuses an untested governed area under the scalar and
    allows it under the list -- measured in
    `test_hooks.test_the_shipped_readers_of_a_single_value_field_still_read_one_value`), so the
    project's own rule is off while the item stands.

    RED without `report._check_single_value_fields`: `validate` over exactly this state was
    "0 error(s), 0 warning(s)".
    """
    inv = state.capture("INV", {"scope": "compounder/", "source": "PR-0001",
                                "check": {"kind": "test", "ref": "t.py::t"},
                                "text": "pure, no I/O"})
    with state.lock:
        raw = state.read_item(inv["id"])
        raw["scope"] = ["compounder/", "engine/"]
        state._write_yaml_atomic(state.active_path(inv["id"]), raw)
    found = errors(report.validate_state(state))
    named = [f for f in found if f["item"] == inv["id"] and "scope" in f["message"]]
    assert named, found
    assert "ONE value" in named[0]["message"], named[0]["message"]
    assert "TWO INV items" in named[0]["remedy"] and "update %s" % inv["id"] in named[0]["remedy"]
    # ...and the one-area spelling is clean, or this would be a finding nobody can satisfy
    state.update_item(inv["id"], {"scope": "compounder/"})
    assert not [f for f in report.validate_state(state) if "ONE value" in f["message"]]


# -- BUG-0005: the last decision rides into the next session via the brief ------

def test_session_brief_carries_the_newest_standing_decision(state):
    """BUG-0005: the last call the previous session made rides into the next one WITH ITS CONTENT
    (title + decision, not just the id), so a PM does not begin blind -- and does not reach for the
    raw transcript to recover it (BUG-0019). Measured on a real generate-session-brief run."""
    state.capture("PR", dict(PR_FIELDS))
    dec = state.capture("DEC", dict(DEC_FIELDS, title="Local-only storage",
                                    decision="Ship with SQLite, no cloud sync"))
    path = report.generate_session_brief(state, "dev-team", "v", "audited")
    brief = yaml.safe_load(open(path, encoding="utf-8"))
    rows = {d["id"]: d for d in brief["standing_decisions"]}
    assert dec["id"] in rows, brief["standing_decisions"]
    assert rows[dec["id"]]["title"] == "Local-only storage"
    assert rows[dec["id"]]["decision"] == "Ship with SQLite, no cloud sync"


def test_a_superseded_decision_is_absent_from_the_brief(state):
    """The Gegenprobe for the link mechanism: a decision another one replaced does not ride along --
    the brief carries what HOLDS, not the whole history."""
    old = state.capture("DEC", dict(DEC_FIELDS, title="old", decision="use X"))
    new = state.capture("DEC", dict(DEC_FIELDS, title="new", decision="use Y instead",
                                    supersedes=[old["id"]]))
    path = report.generate_session_brief(state, "dev-team", "v", "audited")
    brief = yaml.safe_load(open(path, encoding="utf-8"))
    ids = {d["id"] for d in brief["standing_decisions"]}
    assert old["id"] not in ids, ids
    assert new["id"] in ids, ids


def test_a_status_superseded_decision_neither_holds_nor_rides_the_brief(state):
    """The Gegenprobe for the OTHER retirement mechanism: a DEC whose own status is SUPERSEDED (a
    migrated ADR) does not hold and must not appear -- the supersedes link is not the only way a
    decision is retired. Written by hand past the kernel, the only way a SUPERSEDED DEC exists
    (transition refuses a type with no automaton)."""
    dec = state.capture("DEC", dict(DEC_FIELDS, title="retired", decision="old call"))
    p = state.active_path(dec["id"])
    item = state._read_yaml(p)
    item["status"] = "SUPERSEDED"
    state._write_yaml_atomic(p, item)
    standing, _superseded = report.standing_decisions(state)
    assert dec["id"] not in standing
    path = report.generate_session_brief(state, "dev-team", "v", "audited")
    brief = yaml.safe_load(open(path, encoding="utf-8"))
    assert dec["id"] not in {d["id"] for d in brief["standing_decisions"]}


def test_the_brief_decision_section_is_bounded_in_count_and_bytes(state):
    """The section may not grow without bound: a decision log longer than the limit yields only the
    newest few, clipped, so the brief never breaks its own byte budget -- which would make
    generate_session_brief raise. The newest are the ones kept (created, then id number)."""
    ids = []
    for n in range(report._BRIEF_MAX_DECISIONS + 4):
        d = state.capture("DEC", dict(DEC_FIELDS, title="t%d" % n, decision="x" * 5000))
        ids.append(d["id"])
    path = report.generate_session_brief(state, "dev-team", "v", "audited")  # must not raise
    brief = yaml.safe_load(open(path, encoding="utf-8"))
    rows = brief["standing_decisions"]
    assert len(rows) == report._BRIEF_MAX_DECISIONS
    assert {r["id"] for r in rows} == set(ids[-report._BRIEF_MAX_DECISIONS:])
    assert all(len(r["decision"]) <= report._BRIEF_DECISION_MAX_CHARS for r in rows)


def test_a_second_user_visible_slice_may_not_enter_delivery(state):
    """R12 / parity row 107, the 4-slices incident. The point of the sequence rule is that the
    user SEES a slice before the next is built on its assumptions."""
    first = state.capture("PR", dict(PR_FIELDS))
    second = state.capture("PR", dict(PR_FIELDS, title="Second slice"))
    walk_to_status(state, first, "DELIVERED")
    walk_to_status(state, second, "IN_DELIVERY")
    found = errors(report.validate_state(state))
    assert any(f["item"] == second["id"] and "not yet ACCEPTED" in f["message"]
               for f in found), found


def test_a_technical_enabler_may_run_alongside(state):
    """The rule is about USER-VISIBLE slices: a technical enabler shows the user nothing, so
    holding it back buys nothing and would stall the work that unblocks the review."""
    first = state.capture("PR", dict(PR_FIELDS))
    enabler = state.capture("PR", dict(PR_FIELDS, title="Build pipeline",
                                       **{"class": "technical_enabler"}))
    walk_to_status(state, first, "DELIVERED")
    walk_to_status(state, enabler, "IN_DELIVERY")
    found = errors(report.validate_state(state))
    assert not [f for f in found if "not yet ACCEPTED" in f["message"]], found


# -- qa_verdicts: the definition the merge gate reads (spec II.2 Evidence) -----

def evd(state, kind="test", result="pass", related=("PR-0001",), created=None, **run):
    """An Evidence item, optionally back-dated so ORDER can be asserted independently of clock.

    `**run` carries the optional run record (`run_command`/`run_scope`); left out it produces the
    record shape every project already holds, which is what most callers here are about.
    """
    item = state.capture("EVD", {"kind": kind, "result": result, "related": list(related),
                                 "summary": "s",
                                 "artifact_refs": ["staging/TSK-0001/run.log"], **run})
    if created is not None:
        path = state.active_path(item["id"])
        stored = state._read_yaml(path)
        stored["created"] = created
        state._write_yaml_atomic(path, stored)
    return item["id"]


def test_qa_verdicts_reports_the_newest_evidence_of_each_kind(state):
    """"Current verdict" is per kind and newest-wins — the property "any pass anywhere" lacks.

    `created` is set explicitly here because the kernel stamps it to the SECOND: without it the
    two items below would carry the same timestamp and the test would be measuring the id
    tiebreaker rather than the ordering rule it claims to check.
    """
    state.capture("PR", dict(PR_FIELDS))
    old = evd(state, kind="test", result="pass", created="2026-01-01T00:00:00")
    new = evd(state, kind="test", result="fail", created="2026-02-01T00:00:00")
    review = evd(state, kind="review", result="pass", created="2026-01-15T00:00:00")
    verdicts = report.qa_verdicts(state, "PR-0001")
    assert verdicts["test"]["id"] == new and verdicts["test"]["result"] == "fail"
    assert verdicts["review"]["id"] == review
    assert old not in [v["id"] for v in verdicts.values()]


def test_qa_verdicts_breaks_a_same_second_tie_by_id(state):
    """The NORMAL case, not an edge one: `created` is second-resolution, so two verdicts recorded
    in one QA run share a timestamp. Ordering by time alone would make the winner arbitrary."""
    state.capture("PR", dict(PR_FIELDS))
    stamp = "2026-03-01T12:00:00"
    evd(state, result="fail", created=stamp)
    newer = evd(state, result="pass", created=stamp)
    assert report.qa_verdicts(state, "PR-0001")["test"]["id"] == newer


def test_a_task_accepted_without_a_qa_verdict_is_reported(state):
    """BUG-0060: work booked as finished with nothing in the project that measured it.

    THE MEASUREMENT THIS EXISTS FOR: the evidence drawer was empty after both dev pilots, and
    the two moments that ask for a verdict were never reached -- pilot 3 ended with 11 tasks at
    the accepted status and none confirmed, and this repository's own 81 archived tasks are
    CANCELLED to the last one. So the drawer's emptiness was never SAID anywhere. This asserts
    that it is now said, on the status the runs really reach, per missing kind, and that it is a
    warning rather than an error -- standing here is what a task does between the handback and QA.

    RED WITHOUT THE FIX: `validate_state` produced no finding for such a task at all.

    The negative half is the one that keeps this from being satisfiable by warning always: with a
    passing verdict of EVERY delivery kind, the finding is gone.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    task = make_task(state, root["id"], bug["id"])
    drive_task_to(state, task["id"], "DONE")

    found = [f for f in warnings_of(report.validate_state(state)) if f["item"] == task["id"]]
    assert len(found) == 1, found
    assert not errors(report.validate_state(state))
    for kind in QA_EVIDENCE_KINDS:
        assert kind in found[0]["message"], (kind, found[0])
    assert "harness.py evidence" in found[0]["remedy"], found[0]

    for kind in sorted(QA_EVIDENCE_KINDS)[:-1]:
        evd(state, kind=kind, result="pass", related=(task["id"],))
    still = [f for f in warnings_of(report.validate_state(state)) if f["item"] == task["id"]]
    assert len(still) == 1 and sorted(QA_EVIDENCE_KINDS)[-1] in still[0]["message"], still

    evd(state, kind=sorted(QA_EVIDENCE_KINDS)[-1], result="pass", related=(task["id"],))
    assert not [f for f in warnings_of(report.validate_state(state)) if f["item"] == task["id"]]


def test_a_failing_verdict_does_not_count_as_one_and_an_unaccepted_task_is_not_asked(state):
    """The two boundaries of the rule above, both of which a laxer or a louder cut would miss.

    A `fail` is a verdict that was recorded, and reading it as coverage would let the one shape
    this check exists for -- work called finished that nothing supports -- pass on a measurement
    that says the opposite. And a task that has NOT been accepted yet owes nothing: asking for a
    verdict at SUBMITTED would put the finding on every task the moment it is handed back.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    early = make_task(state, root["id"], bug["id"])
    drive_task_to(state, early["id"], "SUBMITTED")
    assert not [f for f in warnings_of(report.validate_state(state)) if f["item"] == early["id"]]

    task = make_task(state, root["id"], bug["id"])
    drive_task_to(state, task["id"], "DONE")
    for kind in QA_EVIDENCE_KINDS:
        evd(state, kind=kind, result="fail", related=(task["id"],))
    found = [f for f in warnings_of(report.validate_state(state)) if f["item"] == task["id"]]
    assert len(found) == 1, found
    for kind in QA_EVIDENCE_KINDS:
        assert kind in found[0]["message"], (kind, found[0])


def test_a_task_of_a_kit_that_produces_no_delivery_verdict_is_not_asked_for_one(state):
    """The office case, and the reason this check carries a term for it at all.

    MEASURED on the shipped kit: `grep -rn "harness.py evidence" team-kits/office-team/` finds one
    producing role, the project-auditor, and it records `--kind audit` — which is no delivery
    verdict (`QA_EVIDENCE_KINDS` excludes it). That kit creates tasks like every other, so without
    the root-type term every completed office task would carry a debt nothing in the kit can pay.

    The property is `ROOT_TYPE_BY_KIT`: a project of that kit hangs from no PR/RQ, so its tasks
    hang from something else. Here the same task shape is built under a PROC root and under a PR
    root, and only the second is asked.

    RED WITHOUT THE FIX: the first half reports a warning an office project can never clear.
    """
    proc = state.capture("PROC", {"title": "file the inbox", "steps": ["read it"],
                                  "roles": ["records-clerk"]})
    task = state.capture("TSK", {
        "product_requirement": proc["id"], "root_revision": proc.get("revision"),
        "derives_from": [proc["id"]], "type": "implementation", "assigned_role": "records-clerk",
        "acceptance_refs": ["AC-1"], "required_inputs": [], "allowed_scope": ["inbox/"],
        "forbidden_scope": [], "expected_outputs": ["filed"], "dependencies": []})
    drive_task_to(state, task["id"], "DONE")
    assert not [f for f in warnings_of(report.validate_state(state)) if f["item"] == task["id"]]

    root = state.capture("PR", dict(PR_FIELDS))
    delivered = make_task(state, root["id"], make_bug(state, root["id"])["id"])
    drive_task_to(state, delivered["id"], "DONE")
    assert [f for f in warnings_of(report.validate_state(state))
            if f["item"] == delivered["id"]], "the PR-rooted task is the control and must be asked"


def test_a_task_under_every_kit_root_is_asked_for_its_delivery_verdict(state):
    """The other direction of the same term (BUG-0084 AC-3): the RESEARCH root is asked too.

    Its sibling above measures the exclusion an office project needs; nothing measured the
    inclusion, and an enumeration `{"PR"}` would have passed it -- a research project would then
    have booked accepted work with no verdict and no finding, which is precisely the blindness
    BUG-0060 recorded for the dev kit. Both roots of `ROOT_TYPE_BY_KIT` are walked here through
    `validate_state`, so a kit that gains a root type arrives asked.
    """
    from kernel.backlog_types import ROOT_TYPE_BY_KIT
    assert set(ROOT_TYPE_BY_KIT.values()) == {"PR", "RQ"}, (
        "a new kit root type needs a branch in this test's builder below: %s" % ROOT_TYPE_BY_KIT)
    question = make_question(state)
    experiment = make_experiment(state, make_hypothesis(state, question["id"])["id"])
    task = make_task(state, question["id"], experiment["id"])
    drive_task_to(state, task["id"], "DONE")
    assert [f for f in warnings_of(report.validate_state(state)) if f["item"] == task["id"]], (
        "an accepted research task carries no QA debt -- the filter dropped the RQ root")


def test_a_pass_from_a_partial_run_is_not_merge_evidence_and_a_fail_still_is(state):
    """FR-0040: an Evidence that says what its run covered, and a merge that reads it.

    Until this pair of fields, `REQUIRED_FIELDS["EVD"]` named the verdict, the summary and the
    artefacts and nothing named the RUN -- so a pass from `pytest -k one_test` and a pass from the
    whole suite were the same record, while the `EVIDENCE_RESULTS` vocabulary comment as it then
    stood and `gate_git`'s refusal text both told the reader that a partial run is not merge
    evidence.

    BOTH DIRECTIONS, because the rule is an asymmetry and not a filter: a partial PASS is dropped
    (it cannot show the absence of a defect), a partial FAIL is kept (it can show one), and an
    Evidence that declares no scope is unchanged -- which is the half the field's optionality
    leaves open and H108 carries.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    partial = dict(run_command="python -m pytest tools/ -k checkout", run_scope="selection")

    evd(state, kind="test", result="pass", related=(root["id"],), **partial)
    assert "test" not in report.qa_verdicts(state, root["id"]), (
        "a pass from a selection opened the merge")

    evd(state, kind="test", result="fail", related=(root["id"],), **partial)
    assert report.qa_verdicts(state, root["id"])["test"]["result"] == "fail", (
        "a FAIL from a selection was dropped with the passes -- a partial run can show a defect")

    evd(state, kind="test", result="pass", related=(root["id"],),
        run_command="python -m pytest tools/", run_scope="full")
    assert report.qa_verdicts(state, root["id"])["test"]["result"] == "pass"

    evd(state, kind="review", result="pass", related=(root["id"],))
    assert report.qa_verdicts(state, root["id"])["review"]["result"] == "pass", (
        "an Evidence that declares no scope stopped counting -- that is a contract change")


def test_a_selection_that_passes_confirms_the_item_it_names_and_ships_nothing(state):
    """BUG-0090 / DEC-0071: ONE derivation, two questions -- and both ends of the split.

    The delivery question is unchanged (the sibling test above is the tripwire for that half); this
    measures the OTHER question, the one `state._assert_confirmed` asks. A passing Evidence that
    declares `run_scope: selection` and names the item answers "is the defect this item names gone"
    and does NOT answer "does this body of work ship".

    AND THE COVERAGE RULE IS UNTOUCHED, which is what keeps the confirmation question from being a
    hole: the same record does not confirm an item it never named.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    other = state.capture("PR", dict(PR_FIELDS, title="Another goal"))
    partial = dict(run_command="python -m pytest tools/test_x.py -k the_defect",
                   run_scope="selection")
    evd(state, kind="test", result="pass", related=(root["id"],), **partial)

    assert "test" not in report.qa_verdicts(state, root["id"]), (
        "a passing selection opened the merge -- the delivery reading moved")
    confirming = report.qa_verdicts(state, root["id"], report.CONFIRMATION_QUESTION)
    assert confirming["test"]["result"] == "pass", (
        "a passing selection that names the item did not confirm it")
    assert report.qa_verdicts(state, other["id"], report.CONFIRMATION_QUESTION) == {}, (
        "the confirmation question stopped asking whether the evidence covers the item")

    with pytest.raises(ValueError, match="unknown evidence question"):
        report.qa_verdicts(state, root["id"], "whatever")


def test_the_inbox_counter_sees_an_archived_work_order_and_the_validator_only_a_live_one(state):
    """BUG-0091 / DEC-0066: the relapse detector, and the reason it has two readers of one rule.

    MEASURED ON THIS REPO before it was built: 21 of 120 work orders hang from an `FR`, and every
    one of them is ARCHIVED -- so a reader of the active items alone answers "none" about exactly
    the practice DEC-0066 was written against. `report.tasks_under_an_inbox_item` therefore counts
    over the whole store, while `validate_state` -- which runs on the merge and push line -- judges
    only what is live. Both read `_inbox_origins_of`, so they cannot disagree about what an inbox
    origin is.

    THE ARCHIVED ORDER STAYS VALID, which is the other end: DEC-0066 (4) keeps the history, so the
    validator must NOT report it.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    walk_to_status(state, root, "APPROVED")
    wish = state.capture("FR", {"title": "a wish", "request_text": "please"})

    # a work order under the wish -- captured directly, the way the 21 historical ones were, since
    # `dispatch.create_task` refuses this shape now
    stale = make_task(state, wish["id"], wish["id"])
    healthy = make_task(state, root["id"], root["id"])

    counted = report.tasks_under_an_inbox_item(state)
    assert counted == {stale["id"]: wish["id"]}, counted
    assert healthy["id"] not in counted, "a task under a goal was counted as inbox work"

    findings = [f for f in report.validate_state(state) if f["item"] == stale["id"]
                and "inbox item" in f["message"]]
    assert len(findings) == 1 and findings[0]["severity"] == "warning", findings
    assert "CONVERTED" in findings[0]["remedy"] or "resulting_item" in findings[0]["remedy"], (
        "the remedy does not name the triage route: %r" % findings[0]["remedy"])

    state.transition(stale["id"], "CANCELLED")
    state.archive(stale["id"])
    assert report.tasks_under_an_inbox_item(state) == {stale["id"]: wish["id"]}, (
        "the counter lost the archived order -- which is where all 21 of this repo's are")
    assert not [f for f in report.validate_state(state) if f["item"] == stale["id"]
                and "inbox item" in f["message"]], (
        "the validator reports an ARCHIVED order, and DEC-0066 (4) keeps those valid")


def test_qa_verdicts_ignores_audit_evidence_and_other_items(state):
    """`audit` judges the project (II.10a) and evidence for another item judges another item."""
    state.capture("PR", dict(PR_FIELDS))
    state.capture("PR", dict(PR_FIELDS, title="Second"))
    evd(state, kind="audit", result="pass")
    evd(state, kind="test", result="pass", related=("PR-0002",))
    assert report.qa_verdicts(state, "PR-0001") == {}
    # ...and the unbound view keeps the same two exclusions, per item instead of per project
    by_subject = report.qa_verdicts_by_subject(state)
    assert by_subject["PR-0002"]["test"]["result"] == "pass"
    assert "audit" not in by_subject.get("PR-0001", {})


def test_qa_verdicts_by_subject_keeps_every_items_verdict_apart(state):
    """The unbound view must not collapse the store into one newest-per-kind.

    That collapse is the V1 file-level false accept rebuilt out of typed items: PR-0002's fresh
    PASS is the newest `test` in the store, and a flat reading would let it answer for PR-0001,
    whose own FAIL is still open. Grouped, both verdicts survive — which is what lets a merge that
    named no item ask "is anything failing" instead of "was the last thing green".
    """
    state.capture("PR", dict(PR_FIELDS))
    state.capture("PR", dict(PR_FIELDS, title="Second"))
    stale = evd(state, kind="test", result="fail", related=("PR-0001",),
                created="2026-01-01T00:00:00")
    fresh = evd(state, kind="test", result="pass", related=("PR-0002",),
                created="2026-02-01T00:00:00")
    by_subject = report.qa_verdicts_by_subject(state)
    # The whole entry, not a field of it: which keys a verdict carries is part of what the merge
    # gate reads, so the comparison stays exact. `blocked_reason` is `None` here because both
    # records ran (FR-0082) -- see `report._newest_per_kind` for why it travels with every verdict
    # rather than being re-read by the caller.
    assert by_subject["PR-0001"]["test"] == {"id": stale, "result": "fail",
                                             "created": "2026-01-01T00:00:00",
                                             "blocked_reason": None}
    assert by_subject["PR-0002"]["test"] == {"id": fresh, "result": "pass",
                                             "created": "2026-02-01T00:00:00",
                                             "blocked_reason": None}


def test_qa_verdicts_by_subject_files_evidence_under_every_item_it_names(state):
    """One QA run may judge two items at once; each of them gets that verdict.

    And newest-wins applies INSIDE a subject, not across the store: PR-0002's later pass does not
    supersede the earlier joint fail for PR-0001, although it is the newer `test` item.
    """
    state.capture("PR", dict(PR_FIELDS))
    state.capture("PR", dict(PR_FIELDS, title="Second"))
    joint = evd(state, kind="test", result="fail", related=("PR-0001", "PR-0002"),
                created="2026-01-01T00:00:00")
    later = evd(state, kind="test", result="pass", related=("PR-0002",),
                created="2026-02-01T00:00:00")
    by_subject = report.qa_verdicts_by_subject(state)
    assert by_subject["PR-0001"]["test"]["id"] == joint
    assert by_subject["PR-0002"]["test"]["id"] == later


# -- what a delivery has already closed (DEC-0051 / FR-0058) -------------------

def test_a_passing_delivery_closes_every_item_it_names(state):
    """The derivation DEC-0051 decided on: "closed" is read off the evidence, not off the status.

    The measured occasion is FR-0058: the store said 26 of 66 bug entries were open work that had
    shipped, because a status field is set by hand and a delivery verdict is written by the kernel.
    One delivery names several items -- the task it judged AND the bug and the wish it closed -- so
    all of them are closed by it, which is what "for BUG and FR alike" means.

    RED WITHOUT THE FIX: `report.closed_by_delivery` did not exist, and no surface answered the
    question at all.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    wish = state.capture("FR", {"title": "wish", "request_text": "please add X"})
    task = make_task(state, root["id"], bug["id"])
    verdict = evd(state, kind="review", result="pass",
                  related=(task["id"], bug["id"], wish["id"]))

    closed = report.closed_by_delivery(state)
    for item_id in (task["id"], bug["id"], wish["id"]):
        assert closed.get(item_id) == [verdict], (item_id, closed)
    assert root["id"] not in closed, "a delivery closes what it NAMES, nothing else"


def test_a_later_fail_reopens_what_an_earlier_pass_had_closed(state):
    """"Any pass wins" is the reading this must not have: a regression re-opens the item.

    Which of several verdicts counts is `_newest_per_kind`, the same supersession the merge gate
    reads -- so a FAIL recorded after a PASS closes the gate again there and un-closes the item
    here. The second half is the other direction of the same rule: a fail of ANOTHER kind, recorded
    at any time, means not every kind that judged the item passed.

    RED WITHOUT THE FIX: a derivation asking "does any passing Evidence name it" keeps the item
    closed in both halves.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    evd(state, kind="review", result="pass", related=(bug["id"],),
        created="2026-01-01T00:00:00")
    assert bug["id"] in report.closed_by_delivery(state)

    evd(state, kind="review", result="fail", related=(bug["id"],),
        created="2026-02-01T00:00:00")
    assert bug["id"] not in report.closed_by_delivery(state)

    other = make_bug(state, root["id"])
    evd(state, kind="review", result="pass", related=(other["id"],))
    evd(state, kind="test", result="fail", related=(other["id"],))
    assert other["id"] not in report.closed_by_delivery(state)


def test_a_task_verdict_does_not_close_the_item_the_task_hangs_from(state):
    """The two readers of one store reach different sets, and the difference is the SUBJECT.

    `closed_by_delivery` groups by the ids an Evidence WRITES; `gate_git` asks `qa_verdicts`, which
    walks the reference graph (`evidence_covers` -> `_hangs_from`) and therefore travels from a task
    up to BOTH items it hangs from -- the item its criteria came from AND the root it is filed
    under. Putting this derivation on that walk would close a whole product requirement because one
    of its tasks passed; measured against this repository's own store, the walk reports four such
    items green that no delivery closed. So both ends are asserted here: the walk really does reach
    the root (or this test would prove nothing about a difference), and the derivation really does
    not.

    RED WITHOUT THE FIX: with `closed_by_delivery` put on `qa_verdicts`/`evidence_covers`, the two
    `not in` assertions fail -- the root and the origin are closed by a verdict about the task.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    task = make_task(state, root["id"], bug["id"])
    for kind in QA_EVIDENCE_KINDS:
        evd(state, kind=kind, result="pass", related=(task["id"],))

    closed = report.closed_by_delivery(state)
    assert task["id"] in closed, "the item the verdict NAMES is closed"
    assert root["id"] not in closed, "a task's verdict may not close the root it is filed under"
    assert bug["id"] not in closed, "nor the item its criteria were cut from"

    for other in (root["id"], bug["id"]):
        verdicts = report.qa_verdicts(state, other)
        assert {entry["result"] for entry in verdicts.values()} == {"pass"}, (
            "the merge gate's reader must reach %s, or there is no difference to measure" % other)


def test_archiving_a_verdict_reopens_the_item_it_had_closed(state):
    """`_delivery_evidence` reads ACTIVE Evidence only, so retiring a verdict un-closes its item.

    Spec II.2 retires a superseded verdict by archiving it, which is exactly right when a newer run
    replaced it -- and surprising when the archive is housekeeping on a verdict that still stands.
    The behaviour is inherited rather than chosen here, so it is pinned instead of described: a
    reader who plans follow-up Evidence records (the closure route this derivation was built for)
    has to know that the same route can be undone by an archive.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    verdict = evd(state, kind="review", result="pass", related=(bug["id"],))
    assert report.closed_by_delivery(state).get(bug["id"]) == [verdict]

    state.archive(verdict)
    assert bug["id"] not in report.closed_by_delivery(state)
    assert bug["id"] not in report.delivered_but_open(state)


def test_a_verdict_that_judges_no_lifecycle_closes_nothing(state):
    """Two subjects that carry no story to close, both dropped by ONE condition.

    `audit` judges the project (II.10a) and is no delivery verdict at all -- `_delivery_evidence`
    never yields it. And an Evidence that names another EVIDENCE names a record: a record type has
    no automaton, so "closed" is not a thing it can be. The second half is what keeps the answer
    from filing evidence under itself, which `qa_verdicts_by_subject` does by design for a record
    that names no item.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    evd(state, kind="audit", result="pass", related=(bug["id"],))
    assert bug["id"] not in report.closed_by_delivery(state)

    judged = evd(state, kind="review", result="pass", related=(bug["id"],))
    evd(state, kind="review", result="pass", related=(judged,))
    assert judged not in report.closed_by_delivery(state)
    assert bug["id"] in report.closed_by_delivery(state), "the control half"


def test_an_item_already_in_a_terminal_status_is_not_reported_as_open(state):
    """`delivered_but_open` is the DIFFERENCE between the two readings, so a closed item leaves it.

    An item standing in a terminal already carries `validate_state`'s own "awaiting archive"
    warning, and reporting it a second time as a bookkeeping debt would be an entry nothing clears.
    """
    wish = state.capture("FR", {"title": "wish", "request_text": "please add X"})
    evd(state, kind="review", result="pass", related=(wish["id"],))
    assert wish["id"] in report.delivered_but_open(state)

    state.update_item(wish["id"], {"triage_result": "delivered under another number"})
    state.transition(wish["id"], "TRIAGED")
    state.transition(wish["id"], "REJECTED")
    assert wish["id"] in report.closed_by_delivery(state)
    assert wish["id"] not in report.delivered_but_open(state)


def test_a_failing_verdict_contradicts_a_confirmed_item(state):
    """The cross-check DEC-0051 stage 2 asks for: the status says confirmed, the records say not.

    `delivered_but_open` reports the other direction as COVERAGE, because a project may be unable to
    clear it. This direction is a FINDING, and the difference is reachability: nobody can arrive
    here by failing to act. The item was walked to the end of its chain and a delivery verdict about
    it says the work did not hold -- one of the two statements is false, and the store must say
    which.

    THE SECOND HALF IS THE VALIDATOR, not only the reader: `contradicted_confirmations` answering
    correctly while nothing asked it would be a derivation with no consumer, which is how the
    disagreement stayed invisible in the first place.

    RED WITHOUT THE FIX: with `_check_confirmations_agree_with_the_verdicts` removed from
    `validate_state` the error assertion fails; with `contradicted_confirmations` absent the module
    has no such reader at all.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    evd(state, kind="test", result="pass", related=(bug["id"],), created="2026-01-01T00:00:00")
    walk_to_status(state, bug, "VERIFIED")
    assert report.contradicted_confirmations(state) == {}, "the control half: confirmed and green"

    regression = evd(state, kind="test", result="fail", related=(bug["id"],),
                     created="2026-02-01T00:00:00")
    assert report.contradicted_confirmations(state) == {bug["id"]: [regression]}
    named = [f for f in errors(report.validate_state(state)) if f["item"] == bug["id"]]
    assert named, "the disagreement is a finding of the validator, not only of a reader"

    # ...AND THE ANSWER IS NOT ABOUT `BUG`. Only that type has a kernel-enforced proof on its
    # confirming edge (`state.CONFIRMING_EVIDENCE`), so a reader narrowed to it would pass
    # everything above while every other confirmed type went unchecked. A root walked to the end of
    # ITS chain is the second positive case, and its confirming status is a different word.
    delivered = state.capture("PR", dict(PR_FIELDS, title="a second root"))
    walk_to_status(state, delivered, "ACCEPTED")
    broke = evd(state, kind="review", result="fail", related=(delivered["id"],))
    assert report.contradicted_confirmations(state).get(delivered["id"]) == [broke]
    assert [f for f in errors(report.validate_state(state))
            if f["item"] == delivered["id"]], "the finding is produced for every confirmed type"


def test_a_terminal_that_does_not_mean_confirmed_is_no_contradiction(state):
    """A failing verdict beside DROPPED work AGREES with the record — both directions of that.

    Two shapes, one condition (`backlog_types.confirming_edge`), and reading it as "the item is in
    some terminal" would report both as defects: a `BUG` put down as `REJECTED` says the work was
    abandoned, so a failing verdict is what one expects there; and an `FR` has no confirming edge at
    all, because its chain ends off a terminal and which of the three it takes is a judgement no
    automaton makes.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    state.transition(bug["id"], "TRIAGED")
    state.transition(bug["id"], "REJECTED")
    evd(state, kind="test", result="fail", related=(bug["id"],))

    wish = state.capture("FR", {"title": "wish", "request_text": "please add X"})
    state.update_item(wish["id"], {"triage_result": "folded into another request"})
    state.transition(wish["id"], "TRIAGED")
    state.update_item(wish["id"], {"resulting_item": root["id"]})
    state.transition(wish["id"], "MERGED")
    evd(state, kind="test", result="fail", related=(wish["id"],))

    assert report.contradicted_confirmations(state) == {}
    assert [f for f in errors(report.validate_state(state))
            if f["item"] in (bug["id"], wish["id"])] == []


def _register_approval_hook(repo, event=None, suffix="", hook_dir=(".claude", "hooks"),
                            matcher=None, command=None, disable_all=False):
    """Install the approval hook in `repo` and register it on `event`, or on nothing.

    The FILE is placed either way, because that is one distinction under test: a helper that wrote
    only the settings would make every `is False` below pass for the wrong reason. The keywords are
    the registration shapes the two tests below tell apart: `suffix` appends to the command
    (`" ; exit 0"` throws the exit status away) and `hook_dir` moves the file -- neither decides
    whether a registration can MINT; `matcher`, `command` and `disable_all` are three that do.
    """
    hook = os.path.join(repo, *hook_dir, approvals.APPROVAL_HOOK)
    os.makedirs(os.path.dirname(hook), exist_ok=True)
    with open(hook, "w", encoding="utf-8") as handle:
        handle.write("# a file is not a registration\n")
    if command is None:
        command = ('python "$CLAUDE_PROJECT_DIR/%s/%s"%s'
                   % ("/".join(hook_dir), approvals.APPROVAL_HOOK, suffix))
    hooks = {} if event is None else {event: [
        {"matcher": approvals.APPROVAL_QUESTION_TOOL if matcher is None else matcher,
         "hooks": [{"type": "command", "command": command, "timeout": 60}]}]}
    settings = {"hooks": hooks}
    if disable_all:
        settings["disableAllHooks"] = True
    path = os.path.join(repo, ".claude", "settings.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(settings, handle)


def test_the_mint_is_wired_by_the_registration_and_not_by_the_file_lying_there(tmp_path):
    """Whether a USER'S ANSWER can mint is decided by what the provider is told to run.

    The hook file being present says nothing: an installed, unregistered hook is one the provider
    never starts, and a registration on the event that only VERIFIES the question
    (`APPROVAL_QUESTION_EVENT`) mints nothing either -- that event can refuse, it cannot write an
    approval. Three states, one reader.
    """
    repo = str(tmp_path)
    _register_approval_hook(repo, event=None)
    assert report.approval_mint_is_wired(repo) is False, "installed is not registered"
    _register_approval_hook(repo, event=approvals.APPROVAL_QUESTION_EVENT)
    assert report.approval_mint_is_wired(repo) is False, "the verifying event never mints"
    _register_approval_hook(repo, event=approvals.APPROVAL_MINT_EVENT)
    assert report.approval_mint_is_wired(repo) is True


def test_a_quoted_path_with_a_space_runs_and_a_named_missing_file_does_not(tmp_path):
    """BUG-0173, both directions: the mint reader read a quoted path wrong and a missing file wrong.

    The two halves fail in OPPOSITE directions, so they are asserted together: a registration
    written out as a quoted absolute path with a space in it mints (over-warning if read `False`),
    and a registration whose path this reader can resolve to a file that is not there mints nothing
    (under-warning if read `True`). The counterweight in the same test is the word this reader
    must NOT judge -- a path behind a variable it cannot resolve keeps its `True`, because a wrong
    "missing" suppresses the warning at a project that really mints.
    """
    spaced = tmp_path / "a directory with spaces"
    hook = spaced / approvals.APPROVAL_HOOK
    os.makedirs(str(spaced), exist_ok=True)
    with open(str(hook), "w", encoding="utf-8") as handle:
        handle.write("# a file is not a registration\n")
    repo = str(tmp_path)

    _register_approval_hook(repo, event=approvals.APPROVAL_MINT_EVENT,
                            command='python -B "%s"' % str(hook).replace("\\", "/"))
    assert report.approval_mint_is_wired(repo) is True, "a quoted path with a space still runs"
    assert report._invoked_scripts('python -B "%s"' % str(hook).replace("\\", "/")) == [
        approvals.APPROVAL_HOOK], "the quoted span is ONE word"

    _register_approval_hook(repo, event=approvals.APPROVAL_MINT_EVENT,
                            command='python -B "$CLAUDE_PROJECT_DIR/nowhere/%s"'
                                    % approvals.APPROVAL_HOOK)
    assert report.approval_mint_is_wired(repo) is False, (
        "a path that resolves to no file starts nothing, and the reader must say so")

    _register_approval_hook(repo, event=approvals.APPROVAL_MINT_EVENT,
                            command='python -B "$SOME_OTHER_ROOT/%s"' % approvals.APPROVAL_HOOK)
    assert report.approval_mint_is_wired(repo) is True, (
        "a variable this reader cannot resolve is not judged -- a wrong 'missing' is reassuring")


def test_the_entry_point_warns_before_the_question_is_put_to_the_user(state, tmp_path, capsys):
    """The warning has to arrive BEFORE the click, not at the transition afterwards.

    `request-approval` is where a role learns what to relay, and the transition refusal that
    carries the same fact only runs once the user has already answered -- BUG-0039's shape, where
    a yes evaporates and no surface says so. Both halves are asserted: the warning appears, and
    stdout stays the question ALONE, because that is what gets relayed verbatim.

    RED WITHOUT THE FIX: with the stderr branch gone the first `err` assertion fails; with it
    written unconditionally the wired half fails.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    argv = ["--root", state.root, "request-approval", "scope", bug["id"]]

    assert cli.main(list(argv)) == 0
    unwired = capsys.readouterr()
    assert "[APR-REQ:" in json.loads(unwired.out)["question"], "stdout is the question alone"
    assert approvals.APPROVAL_HOOK in unwired.err and "approve nothing" in unwired.err

    _register_approval_hook(str(tmp_path), event=approvals.APPROVAL_MINT_EVENT)
    assert cli.main(list(argv)) == 0
    wired = capsys.readouterr()
    assert "[APR-REQ:" in json.loads(wired.out)["question"]
    assert wired.err == "", "a project that CAN mint is not warned about minting"


def test_a_registration_that_could_not_block_still_mints(state, tmp_path):
    """"Could this refuse" and "could this mint" are different questions about one registration.

    A mint is a SIDE EFFECT -- the hook writes the APR on its way out -- so it happens whatever the
    exit status is and wherever the file lies. `_wired_hooks` drops both shapes because it answers
    the first question, and reading this one through it told a project it could not mint while the
    shipped hook minted for it. Measured 2026-08-30 against the real hook process; the assertion
    below drives that same process rather than repeating the claim.

    THE COST OF GETTING IT WRONG IS THE SENTENCE: `approvals._unwired_mint_note` would tell a role
    that no answer of the user's mints here, at a project where one does -- an over-claim in the
    direction that makes the apparatus look weaker than it is, which is as wrong as the reassuring
    kind.

    THE COUNTERWEIGHTS BELOW ARE HALF OF IT: a reader that answered `True` to everything would
    satisfy every positive assertion here, so the three registrations under which the provider never
    starts the hook are asserted in the same test rather than trusted to a separate one. All three
    fail in the REASSURING direction -- they suppress the warning at a project where no answer of
    the user's mints -- which is the direction a warning must not fail in quietly.

    RED WITHOUT THE FIX: with `approval_mint_is_wired` reading through
    `_fires_for(_wired_hooks(...))` both `is True` assertions fail and the refusal carries the note;
    with each of the kill switch, the matcher and the `_invoked_scripts` term dropped from the walk,
    one counterweight fails.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    state.transition(bug["id"], "TRIAGED")
    repo = str(tmp_path)

    _register_approval_hook(repo, event=approvals.APPROVAL_MINT_EVENT, suffix=" ; exit 0")
    assert report.approval_mint_is_wired(repo) is True, "a wrapper that cannot block still mints"
    _register_approval_hook(repo, event=approvals.APPROVAL_MINT_EVENT,
                            hook_dir=("tools", "approval"))
    assert report.approval_mint_is_wired(repo) is True, "the hook need not live in .claude/hooks"

    with pytest.raises(Exception) as refused:
        state.transition(bug["id"], "APPROVED")
    assert approvals.APPROVAL_HOOK not in str(refused.value), (
        "a project whose registration DOES mint must not be told that nothing reads the answer")

    # ...AND THE COUNTERWEIGHTS, because a reader that answered True to everything would satisfy
    # every line above. Each of these is a registration under which the provider never starts the
    # hook, so each must still read as unwired -- and each fails in the REASSURING direction, by
    # suppressing the warning at a project where no answer of the user's mints anything.
    _register_approval_hook(repo, event=approvals.APPROVAL_MINT_EVENT, disable_all=True)
    assert report.approval_mint_is_wired(repo) is False, "the documented kill switch stops it"
    _register_approval_hook(repo, event=approvals.APPROVAL_MINT_EVENT, matcher="Bash|Edit")
    assert report.approval_mint_is_wired(repo) is False, "a matcher that excludes the tool"
    _register_approval_hook(repo, event=approvals.APPROVAL_MINT_EVENT,
                            command='echo "see %s"' % approvals.APPROVAL_HOOK)
    assert report.approval_mint_is_wired(repo) is False, "naming the hook is not running it"

    _register_approval_hook(repo, event=approvals.APPROVAL_MINT_EVENT, suffix=" ; exit 0")
    mint_via_hook(state, approvals.create_pending_request(state, "scope", bug["id"]))
    assert state.read_item(bug["id"])["status"] == "APPROVED", (
        "the premise of this test: the shipped hook mints for this project")


def test_the_approval_remedy_does_not_promise_a_mint_the_project_cannot_make(state, tmp_path):
    """A refusal may not send a role to relay a question whose answer nothing in the project reads.

    The remedy's first half runs everywhere (`request-approval` is pure kernel), so it stays; what
    is conditional is the promise that the user's answer finishes the job. Measured 2026-08-30 in
    this repository, whose registration carries no approval gate: without this the refusal told the
    role to relay and wait for a mint that no surface here can produce.

    RED WITHOUT THE FIX: `_unwired_mint_note` returning "" unconditionally leaves the first
    assertion without its sentence.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    state.transition(bug["id"], "TRIAGED")

    with pytest.raises(Exception) as unwired:
        state.transition(bug["id"], "APPROVED")
    assert approvals.APPROVAL_HOOK in str(unwired.value)
    assert approvals.APPROVAL_MINT_EVENT in str(unwired.value)
    assert "request-approval scope" in str(unwired.value), "the half that does work stays"

    _register_approval_hook(str(tmp_path), event=approvals.APPROVAL_MINT_EVENT)
    with pytest.raises(Exception) as wired:
        state.transition(bug["id"], "APPROVED")
    assert approvals.APPROVAL_HOOK not in str(wired.value), (
        "a project that CAN mint must not be told it cannot")
    assert "request-approval scope" in str(wired.value)


def test_the_route_says_or_between_approval_kinds_and_and_before_the_evidence():
    """The rollup line is read by a role deciding what to obtain, so the join words carry a claim:
    the approval kinds that commit one edge are ALTERNATIVES, the confirming Evidence is demanded on
    top of whichever was given.

    Measured on the running composer over the edge that really has two kinds since PR-0012 AC-1
    (`BUG TRIAGED -> APPROVED` takes `scope` or `verification`) and over the edge that has one kind
    and an Evidence -- both ends, so a fix that turns every join into "or" is as red as the "and"
    it replaced.

    RED WITHOUT the split in `_needs`: the line reads "needs a 'scope' approval and a
    'verification' approval", which tells a role to obtain two approvals where one walks.
    """
    sentence = report._route_sentence("BUG", "TRIAGED")
    assert "a 'scope' approval or a 'verification' approval" in sentence, sentence
    assert "approval and a 'verification'" not in sentence, sentence
    # the other end: what is NOT an alternative keeps its "and"
    assert "VERIFIED (needs a passing 'test' Evidence)" in sentence, sentence
    both = report._needs({"approvals": ("scope", "verification"), "evidence": "test"})
    assert both == (" (needs a 'scope' approval or a 'verification' approval and a passing "
                    "'test' Evidence)"), both


def test_the_closing_route_of_a_bug_names_both_guards_between_it_and_verified(state):
    """H39, made visible: a repaired BUG passes a MINTED approval and a PASSING test Evidence.

    Both guards are read from the maps the transition path itself consults, and both are measured
    against the running kernel here rather than against the route text: the mint is what walks
    TRIAGED -> APPROVED (`state.transition` refuses that edge outright), and FIXED -> VERIFIED is
    refused while no `test` verdict covers the bug. A workshop that can produce neither has no
    honest terminal for a repaired bug, which is why the derivation above is the truth about its
    state and the status field is not.
    """
    route = report.closing_route("BUG", "OPEN")
    assert [edge["to"] for edge in route["steps"]] == ["TRIAGED", "APPROVED", "FIXED", "VERIFIED"]
    assert route["choices"] == [], "VERIFIED ends the chain, so nothing is left to choose"
    guards = {edge["to"]: (edge["approvals"], edge["evidence"]) for edge in route["steps"]}
    # BOTH kinds that commit this edge, by membership rather than as an ordered tuple: since
    # PR-0012 AC-1 a `verification` approval commits the same TRIAGED -> APPROVED as `scope` does
    # (one answer over a batch instead of one per defect), and the route is derived from
    # `required_approval_kinds`, so it has to show both. Naming them here rather than comparing
    # against that function keeps the assertion falsifiable instead of tautological.
    assert "scope" in guards["APPROVED"][0] and guards["APPROVED"][1] is None, guards["APPROVED"]
    assert approvals.VERIFICATION_KIND in guards["APPROVED"][0], guards["APPROVED"]
    assert guards["VERIFIED"] == ((), "test")
    assert guards["TRIAGED"] == ((), None) and guards["FIXED"] == ((), None)

    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    state.transition(bug["id"], "TRIAGED")
    with pytest.raises(Exception) as unapproved:
        state.transition(bug["id"], "APPROVED")
    assert "approval" in str(unapproved.value).lower(), unapproved.value

    walk_to_status(state, state.read_item(bug["id"]), "FIXED")
    with pytest.raises(Exception) as unproven:
        state.transition(bug["id"], "VERIFIED")
    assert "'test' Evidence" in str(unproven.value), unproven.value
    evd(state, kind="test", result="pass", related=(bug["id"],))
    assert state.transition(bug["id"], "VERIFIED")["status"] == "VERIFIED"


def test_the_closing_route_of_a_request_offers_the_terminals_it_may_become(state):
    """An FR's chain does NOT end in a terminal, so the route offers rather than picks.

    Which of MERGED, CONVERTED and REJECTED a delivered wish takes is a judgement no automaton
    makes -- the route may not invent it, and a route function that only knew a confirming chain
    (BUG, TSK) would have said nothing at all about the type this round is mostly about.
    """
    route = report.closing_route("FR", "OPEN")
    assert [edge["to"] for edge in route["steps"]] == ["TRIAGED"]
    assert sorted(edge["to"] for edge in route["choices"]) == ["CONVERTED", "MERGED", "REJECTED"]
    assert all(edge["from"] == "TRIAGED" for edge in route["choices"])
    assert report.closing_route("FR", "MERGED") == {"steps": [], "choices": []}
    assert report._route_sentence("FR", "MERGED") == ""


def test_the_delivery_rollup_is_printed_beside_the_findings_and_is_none_of_them(state, tmp_path):
    """The rollup is COVERAGE: it must reach a reader, and it must not become a finding.

    A finding is something a project can clear. A repaired BUG in a project that cannot mint an
    approval carries this row for good (the test above measures both guards), so as an error it
    would block every merge for ever and as a warning it would be an alarm nobody can leave. Both
    halves are asserted against what RUNS: the finding list of `validate_state`, and the real
    `kernel.cli validate` process, whose stdout is where a reader meets it.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    verdict = evd(state, kind="review", result="pass", related=(bug["id"],))

    assert not [f for f in report.validate_state(state) if f["item"] == bug["id"]]
    rows = {row["item"]: row for row in report.delivery_closure_rollup(state)}
    assert rows[bug["id"]]["evidence"] == [verdict]
    assert rows[bug["id"]]["status"] == "OPEN"
    assert "VERIFIED (needs a passing 'test' Evidence)" in rows[bug["id"]]["route"]

    environment = dict(os.environ, PYTHONPATH=TEAM_KITS, PYTHONIOENCODING="utf-8")
    run = subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root", state.root,
                          "validate"], capture_output=True, text=True, encoding="utf-8",
                         errors="replace", env=environment, cwd=str(tmp_path), timeout=300)
    assert run.returncode == 0, run.stderr
    printed = [line for line in run.stdout.splitlines() if bug["id"] in line]
    assert len(printed) == 1, run.stdout
    assert verdict in printed[0] and "VERIFIED" in printed[0], printed
    assert "[WARNING]" not in printed[0] and "[ERROR]" not in printed[0], printed


def test_evidence_against_a_system_requirement_covers_the_root_it_derives_from(state):
    """The hop `_parents_of` did not have, and an `SR` is the natural subject of a review.

    The graph enumerated its derived types (TSK/BUG/CR/HYP/EXP) instead of reading the field
    contracts, and `SR` -- given a REQUIRED `derives_from` in this lockstep -- was not in the
    list. So a reviewer who recorded the review against the CONTRACT they reviewed produced an
    Evidence that resolved to no root, and `gate_git` refused the merge of that root with
    "nothing judges this work" at the role that had just judged it. Fail-closed, and false
    about the fact.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    sr = state.capture("SR", {"title": "Pay API", "derives_from": pr["id"],
                              "contract": "POST /pay returns 200",
                              "affected_components": ["api"]})
    evd(state, kind="review", related=(sr["id"],))
    assert report.qa_verdicts(state, pr["id"])["review"]["result"] == "pass"


def test_the_reference_graph_walks_every_binding_field_a_contract_declares():
    """Asserted over the DEFINITION, not over the types that happened to have one today.

    A test naming the five types the old `_parents_of` knew would have stayed green through the
    very defect above -- `SR` was added to the field contracts and to nothing else. So this
    reads `PARENT_FIELDS`, which is derived from those contracts: a type joins the graph the day
    its contract gives it a binding field, and this walks whatever is in there.

    Both spellings of a binding are asserted, because the contracts use both: `SR.derives_from`
    is a single id, `TSK.derives_from` a list, and a hop that only understood one of them would
    lose exactly the types the other belongs to.
    """
    for item_type, fields in sorted(PARENT_FIELDS.items()):
        assert fields, item_type
        ids = {field: "PR-%04d" % (n + 1) for n, field in enumerate(fields)}
        assert report._parents_of(item_type, ids) == list(ids.values()), item_type
        listed = {field: [value] for field, value in ids.items()}
        assert report._parents_of(item_type, listed) == list(ids.values()), item_type
        assert report._parents_of(item_type, {}) == [], item_type


# The item-id shape as a SCHEMA declares one, written out here rather than imported: this
# section judges `PARENT_FIELDS`, and the three assertions it used to make all built their
# expectation out of `PARENT_FIELDS` itself. Measured 2026-07-28: with `derives_from` deleted
# from `backlog_types._BINDING_FIELD_NAMES` -- the defect on the definition level -- they stayed
# GREEN and simply measured less. So the reader below re-derives one of the two contract sources
# with its own eyes.
_SCHEMA_ID_RX = re.compile(r"\^?\(?([A-Z]{2,4}(?:\|[A-Z]{2,4})*)\)?-\\d\{4,\}\$?")


def _bindings_the_shipped_schemas_declare():
    """(item type, field) for every schema field held to the id of ANOTHER item.

    The kernel freezes ARC/WFR/DSN instead of capturing them, so `REQUIRED_FIELDS` says nothing
    about their fields -- their contract is the schema `staging.freeze_*` validates against, and
    that is the second source `PARENT_FIELDS` has to be derived from.

    An `APR` reference is deliberately NOT a binding: an approval is a stamp ON this item, not
    the item this one hangs from, and walking it would make every approved item a child of its
    own approval. The item's own `id` field is excluded for the same reason it is in
    `generate_dashboard.relations` -- it would make every item its own parent.
    """
    directory = os.path.join(TEAM_KITS, "kernel", "schemas")
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".yaml"):
            continue
        with open(os.path.join(directory, name), encoding="utf-8") as handle:
            fields = (yaml.safe_load(handle) or {}).get("fields") or {}

        def types_named(spec):
            found = set()
            for key in ("pattern", "item_pattern"):
                match = _SCHEMA_ID_RX.fullmatch((spec or {}).get(key) or "")
                if match:
                    found.update(match.group(1).split("|"))
            return found

        owner = types_named(fields.get("id"))
        if len(owner) != 1:
            continue                       # not an item schema (session_brief, result_envelope)
        for field, spec in fields.items():
            if field == "id":
                continue
            if types_named(spec) - {"APR"}:
                yield next(iter(owner)), field


def _required_fields_the_shipped_schemas_declare():
    """{item type -> required field names}, read out of the schema files by this test."""
    contracts = {}
    directory = os.path.join(TEAM_KITS, "kernel", "schemas")
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".yaml"):
            continue
        with open(os.path.join(directory, name), encoding="utf-8") as handle:
            fields = (yaml.safe_load(handle) or {}).get("fields") or {}
        owner = _SCHEMA_ID_RX.fullmatch(((fields.get("id") or {}).get("pattern")) or "")
        if not owner or "|" in owner.group(1):
            continue
        contracts[owner.group(1)] = {field for field, spec in fields.items()
                                     if (spec or {}).get("required")}
    return contracts


def test_the_validator_holds_a_frozen_item_to_the_duties_its_schema_declares(state):
    """The field-duty loop read the CAPTURE contract, and ran zero times for the frozen types.

    `ARC`, `WFR` and `DSN` never pass `capture`, so `REQUIRED_FIELDS` says nothing about them --
    and the validator, which judges FILES rather than capture calls, therefore judged the one
    kind of item a person can only produce by hand against no duties at all. Spec II.8 names the
    consequence outright ("ARC ohne derives_from -> Validator-Flag"), and the graph fix above
    would have been half a fix without it: an architecture companion with a DANGLING
    `derives_from` was reported, one with none at all was not.

    The duties are read out of the schema files here, not off the kernel's derived map.
    """
    declared = _required_fields_the_shipped_schemas_declare()
    assert len(declared) >= 3, declared
    for item_type, fields in sorted(declared.items()):
        item_id = "%s-0001" % item_type
        os.makedirs(os.path.dirname(state.active_path(item_id)), exist_ok=True)
        state._write_yaml_atomic(state.active_path(item_id), {"id": item_id})
        reported = {f["message"].split("'")[1] for f in errors(report.validate_state(state))
                    if f["item"] == item_id and "missing required field" in f["message"]}
        assert reported == fields - {"id"}, (
            "%s: the validator asked for %s, its schema requires %s"
            % (item_type, sorted(reported), sorted(fields - {"id"})))
        os.remove(state.active_path(item_id))


def test_parent_fields_holds_every_binding_a_shipped_schema_declares():
    """`PARENT_FIELDS` answered to ONE of its two contract sources, and the other half went missing.

    Derived from `REQUIRED_FIELDS` alone, the map knew the captured types and none of the frozen
    ones -- so an `ARC` carrying `derives_from: PR-0001`, required and item-id-patterned in its
    own companion schema, hung from nothing: a review Evidence recorded against the architecture
    resolved to no root and `gate_git` refused the merge with "nothing judges this work", at the
    architect who had just judged it. The identical damage the `SR` fix was written for, one type
    over, because the fix replaced a list of types with a smaller list of types.

    Read straight out of the shipped schema files, so this assertion shares nothing with the
    derivation it judges.
    """
    declared = sorted(set(_bindings_the_shipped_schemas_declare()))
    assert len(declared) >= 3, (
        "the shipped schemas declare almost no item bindings (%s) -- the reader above stopped "
        "matching the patterns rather than the schemas losing their `derives_from`" % declared)
    missing = [(item_type, field) for item_type, field in declared
               if field not in PARENT_FIELDS.get(item_type, ())]
    assert not missing, (
        "%s declare(s) a field naming another item, and the reference graph does not walk it. "
        "Every consumer of `PARENT_FIELDS` -- the merge gate's root resolution, the validator's "
        "reference check, the kernel's write-path check -- is blind to that binding, and each "
        "answers a role that recorded a correct judgement with 'nothing judges this work'."
        % sorted(missing))


_SPEC_PATH = os.path.join(os.path.dirname(TEAM_KITS), "docs", "HARNESS_V2_SPEC.md")
# A spec bullet or header that declares one type's field list. Both spellings II.2 uses:
# `**PR-Pflichtfelder:** id, title, ...` and `- PROC: id, title, status, derives_from (optional), ...`,
# the latter sometimes with a parenthetical about the storage form (`- DSN (Manifest-YAML ...): ...`).
_SPEC_TYPE_RX = re.compile(r"^(?:\*\*([A-Z]{2,4})-Pflichtfelder:\*\*|- ([A-Z]{2,4})(?: \([^)]*\))?:)")


def _fields_the_spec_declares():
    """{item type -> the field names spec II.2 declares for it}, required and optional alike.

    THE SOURCE OUTSIDE THE KERNEL. The two readers above re-derive the FROZEN types' contract
    from the schema files; the CAPTURED types' contract has no file of its own -- it is
    `backlog_types`, the thing under test -- so an independent assertion about it has to come
    from the document the kernel implements.

    Every declared field is collected, not only the mandatory ones, because that distinction is
    exactly what went wrong: `PARENT_FIELDS` was derived from `REQUIRED_FIELDS`, which by
    construction cannot mention a field an item may omit, and spec II.2 declares two bindings as
    optional (`PROC.derives_from`, `FR.related_pr`). A field's MEANING does not depend on whether
    the item carrying it is allowed to leave it out.

    Read leniently on purpose: the leading identifier of each comma-separated part. The spec is
    prose and its parentheticals contain commas, so this over-collects tokens like `ref` -- which
    costs nothing, since the question asked of the result is only whether a field name the graph
    binds by appears in some type's list.

    COVERS THE TYPES II.2 NAMES BY CODE (twelve today, all nine bindings among them). The two it
    spells out -- `Evidence`, `Decision` -- are not matched, and are not silently uncovered
    either: `EVD.related` is required, so `REQUIRED_FIELDS` carries it and the corpus test
    exercises it end to end. The floor below is what notices if this reader stops matching.
    """
    declared, current = {}, None
    with open(_SPEC_PATH, encoding="utf-8") as handle:
        for raw in handle:
            match = _SPEC_TYPE_RX.match(raw)
            if match:
                current = match.group(1) or match.group(2)
                rest = raw[match.end():]
            elif current and raw.startswith("  ") and raw.strip():
                rest = raw                      # a wrapped continuation of the bullet above
            else:
                current = None
                continue
            for part in rest.split(","):
                head = re.match(r"\s*`?([a-z_]+)\b", part)
                if head:
                    declared.setdefault(current, set()).add(head.group(1))
    return declared


_IMPORT_WITHOUT_YAML = """
import sys

class _NoYaml:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] == "yaml":
            raise ImportError("yaml unavailable")
        return None

sys.meta_path.insert(0, _NoYaml())
import kernel.backlog_types as bt
assert "yaml" not in sys.modules, "importing backlog_types pulled PyYAML in"
assert bt.AUTOMATA and bt.REQUIRED_FIELDS and bt.ACTIVE_DIRS
print("ok")
"""


def test_backlog_types_imports_without_pyyaml():
    """The type map has to stay loadable where the parser is not, and that is a hot-path rule.

    Spec II.7 keeps the integrity gates stdlib-first, with no PyYAML import load on the hot path,
    and `guard_no_adhoc` held its item-type list as a LITERAL partly for that reason -- "importing
    the kernel to learn the type names would pull PyYAML into that path, and a guard that cannot
    load must not stop guarding". `backlog_types` is the module that could serve such a guard --
    and for one round it could not, because `PARENT_FIELDS` and `DECLARED_REQUIRED_FIELDS` were
    derived at module scope from `kernel/schemas/*.yaml`, which closed the door and made every
    import of the type names read six files. They are computed on first access instead, and the
    guard's comment now names resilience rather than PyYAML as its reason.

    Measured in a FRESH interpreter with `yaml` blocked at the finder, because the suite has
    PyYAML loaded long before any test runs and would report the opposite in-process.
    """
    proc = subprocess.run([sys.executable, "-c", _IMPORT_WITHOUT_YAML], cwd=TEAM_KITS,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, (
        "`import kernel.backlog_types` needs PyYAML. A gate that cannot afford the parser can no "
        "longer learn the type names from the kernel, so it goes back to a literal list that "
        "drifts.\n%s%s" % (proc.stdout, proc.stderr))


def test_parent_fields_holds_every_binding_the_spec_declares_for_a_captured_type():
    """The capture contract's OPTIONAL half is part of the contract, and the graph must read it.

    `REQUIRED_FIELDS` was the whole capture-time source for one round, and it is structurally
    incapable of reporting an optional field. Spec II.2 declares `derives_from (optional)` on
    `PROC` and `related_pr (optional)` on `FR`; both are item ids when present, so both are hops
    the reference graph has to walk. It did not: a `PROC` captured against a phantom parent was
    reported by no one (`state._assert_origins_resolve` reads this same map), and an Evidence
    recorded against a `PROC` or an `FR` resolved to no root, so `gate_git` answered the role that
    had judged the work with "nothing judges this work" -- the `SR` defect, two types further on.

    Judged against the SPEC, so it shares no source with the derivation it judges.
    """
    declared = _fields_the_spec_declares()
    assert len(declared) >= 8, (
        "the spec reader stopped matching II.2's field declarations (%s)" % sorted(declared))
    from kernel.backlog_types import _BINDING_FIELD_NAMES
    missing = sorted((item_type, field)
                     for item_type, fields in declared.items()
                     for field in sorted(fields & set(_BINDING_FIELD_NAMES))
                     if field not in PARENT_FIELDS.get(item_type, ()))
    assert not missing, (
        "spec II.2 declares %s as a field naming another item, and the reference graph does not "
        "walk it. Every consumer of `PARENT_FIELDS` is blind to that binding: the merge gate "
        "finds no root for an Evidence recorded against such an item, and the kernel's write-path "
        "check lets it be captured against an id that does not exist." % missing)


def test_the_reference_graph_claims_no_binding_a_frozen_types_schema_does_not_declare():
    """The other direction of the schema check: an INVENTED hop is as wrong as a missing one.

    For the types whose whole contract is a schema file, the shipped schema is the complete
    answer -- so `PARENT_FIELDS` must hold exactly the bindings it declares. A field the graph
    walks and the contract does not have makes the validator demand a parent no writer can supply
    and lets `_hangs_from` follow a value that means something else.
    """
    from kernel.schemas import item_field_contracts
    frozen = set(item_field_contracts()) - set(REQUIRED_FIELDS)
    assert frozen >= {"ARC", "WFR", "DSN"}, sorted(frozen)
    declared = {}
    for item_type, field in _bindings_the_shipped_schemas_declare():
        declared.setdefault(item_type, set()).add(field)
    for item_type in sorted(frozen):
        assert set(PARENT_FIELDS.get(item_type, ())) == declared.get(item_type, set()), (
            "%s: the graph walks %s, its schema declares %s"
            % (item_type, sorted(PARENT_FIELDS.get(item_type, ())),
               sorted(declared.get(item_type, set()))))


def test_every_captured_type_that_hangs_from_a_root_reaches_it(state):
    """The graph, asked the question a merge asks, over REAL items of every captured type.

    A corpus and deliberately concrete: each item is captured through the kernel and bound to
    the root the way its own contract binds it, then the walk has to find the root. Nothing here
    reads `PARENT_FIELDS` for its EXPECTATION -- that is the map under test, and an assertion
    built from it stays green through a defect in it (measured: deleting `derives_from` from
    `_BINDING_FIELD_NAMES` left three such assertions passing).

    Coverage is asserted the other way round, against the map: a captured type that gains a
    binding and no corpus entry fails here, so the concreteness cannot go stale.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, pr["id"])
    task = make_task(state, pr["id"], bug["id"])
    sr = state.capture("SR", {"title": "Pay API", "derives_from": pr["id"],
                              "contract": "POST /pay returns 200", "affected_components": ["api"]})
    change = state.capture("CR", {"title": "c", "target_pr": pr["id"], "target_revision": 1,
                                  "change_description": "d", "acceptance_criteria": ["ac"]})
    hypothesis = state.capture("HYP", {"statement": "s", "derives_from": pr["id"],
                                       "testable_prediction": "p"})
    experiment = state.capture("EXP", {"derives_from": hypothesis["id"], "design": "d",
                                       "variables": "v", "success_criteria": "c",
                                       "evidence_refs": []})
    # FR and PROC bind through a field spec II.2 marks OPTIONAL, which is why they were missing
    # from the graph for a round: `REQUIRED_FIELDS` cannot report a field an item may omit.
    request = state.capture("FR", {"title": "make it faster", "request_text": "t",
                                   "related_pr": pr["id"]})
    procedure = state.capture("PROC", {"title": "onboarding", "steps": ["s"], "roles": ["r"],
                                       "derives_from": pr["id"]})
    # A milestone binds through `derives_from` like the rest (DEC-0064), so the graph has to reach
    # the root from it too -- otherwise a deadline recorded against a goal is a record no rollup
    # over that goal can see.
    milestone = state.capture("MST", {"title": "Release 2026.10", "due": "2026-10-01",
                                      "derives_from": [pr["id"]]})
    corpus = {"BUG": bug["id"], "TSK": task["id"], "SR": sr["id"], "CR": change["id"],
              "HYP": hypothesis["id"], "EXP": experiment["id"], "FR": request["id"],
              "PROC": procedure["id"], "MST": milestone["id"],
              "EVD": evd(state, kind="review", related=(task["id"],))}
    for item_type, item_id in sorted(corpus.items()):
        assert report._hangs_from(state, item_id, pr["id"], set()), (
            "%s %s is bound to the root through its contract and the graph does not get there"
            % (item_type, item_id))
    captured = {item_type for item_type in PARENT_FIELDS if item_type in REQUIRED_FIELDS}
    assert set(corpus) == captured, (
        "the corpus and the map disagree about which captured types hang from a root: "
        "%s carry a binding and are not exercised here" % sorted(captured - set(corpus)))


def test_qa_verdicts_resolves_evidence_through_the_reference_graph(state):
    """A BUG under the PR, a task under the BUG: QA judges the task, the merge is of the PR."""
    pr = state.capture("PR", dict(PR_FIELDS))
    bug = state.capture("BUG", {"title": "500 on checkout", "related_pr": pr["id"],
                                "observed": "500", "expected": "200", "repro": "post /pay",
                                "severity": "high", "acceptance_criteria": [{"id": "AC-1",
                                                                             "text": "no 500"}]})
    task = state.capture("TSK", {
        "product_requirement": pr["id"], "root_revision": 1, "derives_from": [bug["id"]],
        "type": "bugfix", "assigned_role": "backend-developer", "acceptance_refs": ["AC-1"],
        "required_inputs": [], "allowed_scope": ["src/**"], "forbidden_scope": [],
        "expected_outputs": ["src/pay.py"], "dependencies": []})
    evd(state, related=(task["id"],))
    assert report.qa_verdicts(state, pr["id"])["test"]["result"] == "pass"


def test_doctor_reads_its_identity_off_the_installation(state, tmp_path):
    """Spec II.4 lists kit / kit_version / lead_role / provider_config, and all four were `unknown`.

    THE PREDECESSOR COULD NOT FAIL FOR THE SHIPPED PATH: it called
    `report.doctor(state, kit="dev-team", kit_version="rc1")` and then asserted the report said
    "dev-team" -- it handed in its own expected value. Meanwhile `cli` passes neither argument, so
    a correctly installed project reported `unknown` for its own kit while `.claude/kit_state.json`
    named it two directories away. This calls doctor the way the CLI does -- NO arguments -- and
    builds the `.claude` an installation really has.
    """
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "kit_state.json").write_text(
        json.dumps({"kit": "office-team", "state": "active"}), encoding="utf-8")
    (claude / "kit_version").write_text("version: 2026.07.31-4\ncontent: abc\n", encoding="utf-8")
    (claude / "settings.json").write_text(
        json.dumps({"agent": "office-manager", "hooks": {}}), encoding="utf-8")

    result = report.doctor(state)
    assert result["kit"] == "office-team", result["kit"]
    assert result["kit_version"] == "2026.07.31-4", result["kit_version"]
    assert result["lead_role"] == "office-manager", result["lead_role"]
    assert "claude" in result["provider_config"], result["provider_config"]
    # ...and an explicit argument still wins, which is what the SessionStart path needs
    assert report.doctor(state, kit="dev-team")["kit"] == "dev-team"


def test_doctor_says_unknown_only_where_it_really_cannot_tell(state):
    """`unknown` is the spec's answer for what cannot be determined -- not a default."""
    result = report.doctor(state)
    assert result["kit"] == "unknown" and result["kit_version"] == "unknown"
    assert result["lead_role"] == "unknown"


# -- per-revision items: ONE reading of one directory (disposition row 6.5) ----

def _freeze_wireframe(state, wfr_id, root_id, apr_ref, body):
    """Freeze one wireframe revision through the kernel -- the only producer of these files."""
    key = "%s-%s" % (root_id, body)
    directory = staging.staging_dir(state, key)
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, wfr_id + ".drawio.svg"), "w", encoding="utf-8") as handle:
        handle.write('<svg xmlns="http://www.w3.org/2000/svg"><g>%s</g></svg>' % body)
    return staging.freeze_wireframe(state, key, wfr_id, apr_ref, [root_id], "Checkout wireframe")


def _approved_root(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    mint_via_hook(state, approvals.create_pending_request(state, "scope", pr["id"]))
    return state.read_item(pr["id"])


def test_a_second_frozen_revision_is_one_item_and_not_a_duplicate_id(state):
    """THE merge-blocking defect of disposition row 6.5, measured at the validator.

    A second `freeze_wireframe` is the normal course of design work, and it wrote
    `WFR-0001.r02.yaml` beside `WFR-0001.r01.yaml`. `_iter_active` read every `*.yaml` as its own
    item, so the validator reported `WFR-0001 duplicate id` -- an ERROR, which
    `gate_memory_complete` turns into a blocked merge for the whole project, with no remedy a role
    is allowed to take: a frozen revision is immutable and deleting one is exactly what II.6a
    forbids.

    Both files stay on disk. The older revision is HISTORY, not garbage -- the fix is a reading
    rule, not a cleanup.
    """
    pr = _approved_root(state)
    apr_ref = pr["approval_ref"]
    _freeze_wireframe(state, "WFR-0001", pr["id"], apr_ref, "first")
    _freeze_wireframe(state, "WFR-0001", pr["id"], apr_ref, "second")
    directory = state.active_dir("WFR")
    assert sorted(n for n in os.listdir(directory) if n.endswith(".yaml")) == [
        "WFR-0001.r01.yaml", "WFR-0001.r02.yaml"]
    assert errors(report.validate_state(state)) == []
    # ...and the ONE item it is, is the newest revision -- the reading `read_anywhere` already had
    item, archived = state.read_anywhere("WFR-0001")
    assert (item["revision"], archived) == (2, False)


def test_the_generated_index_lists_a_per_revision_item_once(state):
    """The index is the second reader that had its own copy of the rule.

    `_regenerate_index_locked` listed a twice-frozen wireframe as TWO rows carrying one id, which
    is what the dashboard and every "what is open" reader work from. It now reads the same
    `iter_active_items` the validator does, so the row count follows from the definition rather
    than from a second implementation of it.
    """
    pr = _approved_root(state)
    for body in ("first", "second", "third"):
        _freeze_wireframe(state, "WFR-0001", pr["id"], pr["approval_ref"], body)
    index = state._read_yaml(os.path.join(state.root, "generated", "index.yaml"))
    rows = [row for row in index["items"] if row["id"] == "WFR-0001"]
    assert len(rows) == 1 and rows[0]["revision"] == 3, rows


def test_every_active_item_is_the_one_its_own_id_resolves_to(state):
    """The property behind both fixes, asserted over the running readers rather than per type.

    `read_anywhere` and `_iter_active` are the kernel's two answers to "which file is this item",
    and disposition row 6.5 is what happens when they differ: the validator judged a file that
    `read_anywhere` says is not the item, and reported the disagreement as a duplicate id. Stated
    as a property it needs no list of per-revision types -- a type frozen that way tomorrow is
    covered by the same assertion.
    """
    pr = _approved_root(state)
    for body in ("first", "second"):
        _freeze_wireframe(state, "WFR-0001", pr["id"], pr["approval_ref"], body)
    dispatch.create_task(state, dict(
        product_requirement=pr["id"], derives_from=pr["id"], type="implementation",
        assigned_role="backend-developer", acceptance_refs=["AC-1"], required_inputs=[],
        allowed_scope=["src/"], forbidden_scope=[], expected_outputs=["src/x.py"],
        dependencies=[]))
    seen = 0
    for _item_type, _stem, item, path, exc in report._iter_active(state):
        assert exc is None, (path, exc)
        resolved, _archived = state.read_anywhere(item["id"])
        assert resolved == item, (
            "%s is judged as %s, but its id resolves to a different file" % (item["id"], path))
        seen += 1
    assert seen >= 3, seen   # the PR, the wireframe and the task -- not the superseded revision


def test_two_different_items_claiming_one_id_are_still_a_duplicate(state):
    """The counter-direction: the revision rule must PRECISE the duplicate rule, not abolish it.

    Two frozen files that differ in more than their `.rNN` are two items, and one id between them
    is the thing gate 5 exists to catch. Written by hand because the kernel cannot produce it --
    which is exactly why the validator has to.
    """
    pr = _approved_root(state)
    _freeze_wireframe(state, "WFR-0001", pr["id"], pr["approval_ref"], "first")
    _freeze_wireframe(state, "WFR-0002", pr["id"], pr["approval_ref"], "other")
    path = os.path.join(state.active_dir("WFR"), "WFR-0002.r01.yaml")
    forged = state._read_yaml(path)
    forged["id"] = "WFR-0001"
    state._write_yaml_atomic(path, forged)
    assert [f["message"] for f in errors(report.validate_state(state))
            if "duplicate id" in f["message"]], report.validate_state(state)


def test_a_plain_file_beside_a_revision_file_is_still_a_duplicate(state):
    """One directory claiming two homes for one id is a contradiction, not a revision.

    `read_anywhere` silently prefers the plain `<ID>.yaml`, so collapsing this into "the newest
    revision" would hide the disagreement instead of reporting it. Only files that differ in
    nothing but their `.rNN` are revisions of one another.
    """
    pr = _approved_root(state)
    _freeze_wireframe(state, "WFR-0001", pr["id"], pr["approval_ref"], "first")
    companion = state._read_yaml(os.path.join(state.active_dir("WFR"), "WFR-0001.r01.yaml"))
    state._write_yaml_atomic(os.path.join(state.active_dir("WFR"), "WFR-0001.yaml"), companion)
    assert [f["message"] for f in errors(report.validate_state(state))
            if "duplicate id" in f["message"]], report.validate_state(state)


def test_the_name_the_kernel_composes_is_the_name_it_reads_back():
    """Compose and parse are one rule, so a change to either cannot pass this by halves.

    `staging` writes `<ID>.rNN` with three different suffixes and three readers take it apart
    again; the round trip is what makes "an item stored per revision IS its newest revision" a
    definition instead of four agreeing implementations.
    """
    for suffix in (".yaml", ".drawio.svg", ".html"):
        for revision in (1, 9, 10, 137):
            name = kernel_state.revision_name("WFR-0001", revision, suffix)
            assert kernel_state.split_revision(name) == ("WFR-0001", revision, suffix), name
    # a name that is NOT one of these carries no revision -- the answer the readers fall back on
    for plain in ("WFR-0001.yaml", "notes.yaml", "WFR-0001.rXX.yaml", "WFR-0001.r.yaml"):
        assert kernel_state.split_revision(plain) == (None, None, None), plain
    # ...and the two conditions `item_revision` adds on top, each one a sentence the docstrings
    # promise and neither of which had a test: a base that is no item id is not an item stored per
    # revision (`notes.r01.yaml` and `notes.r02.yaml` stay two files), and a NON-ASCII digit is not
    # a number -- `re.ASCII` is why `WFR-0001.r١٢.yaml` is not revision 12.
    assert kernel_state.split_revision("notes.r01.yaml") == ("notes", 1, ".yaml")
    assert kernel_state.item_revision("notes.r01.yaml") == (None, None)
    assert kernel_state.item_revision("WFR-0001.r١٢.yaml") == (None, None)
    assert kernel_state.item_revision("WFR-0001.r02.drawio.yaml") == (None, None)
    assert kernel_state.item_revision("WFR-0001.r02.yaml") == ("WFR-0001", 2)


def test_a_revision_file_carrying_a_second_suffix_is_not_the_active_revision(state):
    """The defect the FIRST cut of THIS fix introduced, measured before it shipped.

    `_frozen_revision_path` demanded that the `.rNN` be followed by exactly the item suffix;
    `iter_active_items` accepted any suffix. So `WFR-0001.r03.backup.yaml` -- a name a hand or a
    half-finished copy produces, never the kernel -- was the ACTIVE item for the validator and the
    index while `read_anywhere` still resolved the id to `r02`: the identical two-readings defect
    disposition row 6.5 is about, one file shape further along. Both readers ask
    `state.item_revision` now, so the stray file is not a revision at all -- it is a second file
    claiming an id, which is what the duplicate rule is for.
    """
    pr = _approved_root(state)
    for body in ("first", "second"):
        _freeze_wireframe(state, "WFR-0001", pr["id"], pr["approval_ref"], body)
    stray = os.path.join(state.active_dir("WFR"), "WFR-0001.r03.backup.yaml")
    state._write_yaml_atomic(stray, state._read_yaml(
        os.path.join(state.active_dir("WFR"), "WFR-0001.r02.yaml")))
    assert os.path.basename(state._frozen_revision_path("WFR-0001")) == "WFR-0001.r02.yaml"
    assert "WFR-0001.r02" in [stem for stem, _path in state.iter_active_items("WFR")]
    assert [f for f in errors(report.validate_state(state)) if "duplicate id" in f["message"]]


def test_a_root_presenting_a_non_dispatching_approval_is_reported(state):
    """The blind spot behind the `approval_ref` move -- nothing reported it at all.

    `mint` writes `approval_ref` for every item-bound approval and the dispatch gate's root route
    reads that one field, so minting a routine (or analysis) approval for a root that already
    carries a valid scope approval silently stops every implementation task under it. The project
    used to learn that at the next spawn, as a refusal -- and since a routine is time-boxed and
    recurring by construction, it recurs at EVERY renewal, on a root long since APPROVED.

    A WARNING: the state is legal and the remedy is a user action. The counter-direction is
    asserted in the same test, so "warn always" cannot satisfy it.

    SINCE PR-0011 AC-8 THE MINT NO LONGER PRODUCES THE STATE (`approvals.presents` keeps a hanging
    kind out of `approval_ref`), so the routine mint below is asserted to leave the field alone,
    and the state the validator still has to report -- a root presenting a non-dispatching
    approval, which older stores hold and a hand written past the kernel can still make -- is
    written the way that hand writes it.
    """
    pr = _approved_root(state)
    scope_apr = state.read_item(pr["id"])["approval_ref"]
    assert not [f for f in report.validate_state(state) if "presents" in f["message"]]
    mint_via_hook(state, approvals.create_pending_request(
        state, "routine", pr["id"],
        manifest={"role": "project-auditor", "scope": ["project_memory/**"],
                  "trigger": "weekly", "cadence": "weekly"},
        approval_expires=time.time() + 3600))
    assert state.read_item(pr["id"])["approval_ref"] == scope_apr, "the routine mint moved approval_ref"
    assert not [f for f in report.validate_state(state) if "presents" in f["message"]]
    routine = sorted(name for name in os.listdir(os.path.join(state.root, "approvals"))
                     if name.startswith("APR-") and name.endswith(".yaml"))[-1][:-5]
    displaced = state.read_item(pr["id"])
    displaced["approval_ref"] = routine
    state._write_yaml_atomic(state.active_path(pr["id"]), displaced)
    reported = [f for f in report.validate_state(state) if "presents" in f["message"]]
    assert len(reported) == 1, report.validate_state(state)
    assert reported[0]["severity"] == "warning"
    assert "routine" in reported[0]["message"] and "scope" in reported[0]["message"]
    assert "re-run the scope approval flow" in reported[0]["remedy"]


# -- BUG-0036: one hook_trust reason per state, and per what that state actually costs ---------

_NO_STATE = object()

# Every record this round answers for: spec II.8's own names (taken from the kernel's tuple, whose
# agreement with the spec text is measured below), a name no version of the machine ever defined,
# and a record with no `state` field at all.
TRUST_STATES = list(report.SPEC_II8_STATES) + ["a_name_nobody_defined", _NO_STATE]

_TRANSITION_PROBE = """
import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import kit_trust_state
print(json.dumps([kit_trust_state.transition(case["data"], case["actual"])[0]
                  for case in json.loads(sys.argv[2])]))
"""


def _trust_repo(root, state, hashes="match", extra=None, registered=True, bundle=True):
    """A minimal installation plus the `kit_state.json` record under test; returns the repo root.

    `hashes="match"` records the hash of the bundle that is really on disk -- the shape every fresh
    scaffold leaves behind and the one the TSK-0054 pilot ran into. "stale" records some other
    bundle's hash; "missing" records none at all.

    `registered` writes the SessionStart entry the way the kits' own settings.json spells it, with
    the hook file beside it, because that is what decides whether "start a new session" is advice
    that can work. `bundle=False` leaves `.claude` without a hashable subtree, which is the only
    way to reach the branch where the bundle cannot be measured at all.
    """
    root = str(root)
    claude = os.path.join(root, ".claude")
    os.makedirs(claude, exist_ok=True)
    if bundle:
        hooks = os.path.join(claude, "hooks")
        os.makedirs(hooks, exist_ok=True)
        for name in ("gate_x.py", "kit_trust_state.py"):
            with io.open(os.path.join(hooks, name), "w", encoding="utf-8") as handle:
                handle.write("# a hook\n")
    session_start = [{"hooks": [{"type": "command", "command":
                                 'python -B "${CLAUDE_PROJECT_DIR}/.claude/hooks/'
                                 'kit_trust_state.py"'}]}] if registered else []
    with io.open(os.path.join(claude, "settings.json"), "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"hooks": {"SessionStart": session_start}}))
    record = dict(extra or {})
    if state is not _NO_STATE:
        record["state"] = state
    if hashes == "match":
        record["hook_bundle_hash"] = hook_bundle_hash(claude)
    elif hashes == "stale":
        record["hook_bundle_hash"] = "de" * 32
    with io.open(os.path.join(claude, "kit_state.json"), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(record))
    return root


def _shipped_transitions(cases):
    """What the kits' SessionStart trust hook DOES with these records -- by RUNNING it.

    A subprocess and not an import: the hook puts its own directory on `sys.path` and imports its
    neighbours out of it, and three kits ship a copy each. Every copy is run and the answers must
    agree, so the result is a property of the shipped hook rather than of one kit -- a copy that
    answered differently would be named here rather than averaged away.
    """
    copies = sorted(glob.glob(os.path.join(TEAM_KITS, "*-team", "hooks", "kit_trust_state.py")))
    assert len(copies) >= 3, copies
    answers = {}
    for path in copies:
        proc = subprocess.run([sys.executable, "-B", "-c", _TRANSITION_PROBE,
                               os.path.dirname(path), json.dumps(cases)],
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        answers[path] = json.loads(proc.stdout)
    assert len({json.dumps(value) for value in answers.values()}) == 1, answers
    return answers[copies[0]]


def test_the_spawn_veto_is_not_claimed_for_a_provider_this_report_cannot_read(tmp_path):
    """BUG-0057: on a `claude+codex` install `doctor` reported `capabilities.spawn_veto: verified`
    with the reason "gate_dispatch fires on PreToolUse for Agent/Task" -- a line about the CLAUDE
    registrations, offered as an answer about the project, while the Codex path has no veto at all
    and `spawn_veto` stood in no `enforcement_blockers` entry either.

    BOTH DIRECTIONS IN ONE REPOSITORY, one directory apart: the same wiring answers `verified`
    while only `.claude` is configured and `unverified` the moment a `.codex` layer stands beside
    it. Without the first half this would also pass for a matrix that never says `verified`.

    The reason is asserted too, because `unverified` alone is what a project with no registration
    at all produces -- what has to be readable is WHY, and the provider it names.
    """
    root = tmp_path / "project_memory"
    root.mkdir()
    state = ProjectState(str(root))
    repo = str(tmp_path)
    claude = tmp_path / ".claude"
    (claude / "hooks").mkdir(parents=True)
    (claude / "hooks" / "gate_dispatch.py").write_text("# a gate\n", encoding="utf-8")
    (claude / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Agent|Task", "hooks": [{"type": "command", "timeout": 60, "command":
         'python -B "${CLAUDE_PROJECT_DIR}/.claude/hooks/gate_dispatch.py"'}]}]}}),
        encoding="utf-8")

    matrix, reasons = report.capability_matrix(state, repo)
    assert matrix["spawn_veto"] == "verified", reasons["spawn_veto"]

    (tmp_path / ".codex").mkdir()
    matrix, reasons = report.capability_matrix(state, repo)
    assert matrix["spawn_veto"] == "unverified", reasons["spawn_veto"]
    assert "codex" in reasons["spawn_veto"], reasons["spawn_veto"]


def test_every_provider_marker_says_whether_this_report_reads_its_registrations():
    """The tripwire the pair in `PROVIDER_MARKERS` owes (BUG-0057, house rule 1).

    At least one provider must be MEASURED, or the capability could never read `verified` and the
    row above would be measuring a constant; and at least one must be UNMEASURED, or the whole
    derivation is dead code that no future provider would wake up.
    """
    measured = [name for name, _marker, ok in report.PROVIDER_MARKERS if ok]
    unmeasured = [name for name, _marker, ok in report.PROVIDER_MARKERS if not ok]
    assert measured and unmeasured, report.PROVIDER_MARKERS


def test_the_headless_stop_point_is_measured_and_is_not_the_approval_gate():
    """BUG-0017: "the approval/mint mechanism does not work headless" -- closed as MEASURED BY
    DESIGN rather than fixed, because the measurement says the PM never reaches a gate at all.

    TSK-0135 finding B1, two real `claude -p` runs against a prepared kit project: zero
    `AskUserQuestion` blocks, `stop_reason: end_turn` in both, the PM handing the decision back in
    PROSE. So there is no broken mint to repair -- an unattended run stands still BEFORE its first
    approval, which is a property of the turn model and not of the approval chain.

    THE RECORD IS PARSED, not the prose that cites it: `docs/POST_V2_WISHLIST.md` section 10 names
    this test, and a paragraph nothing reads is a claim that rots. What is asserted is the shape a
    reader needs -- both runs measured, the stop point stated, and the negative that carries the
    whole verdict present in each run's own line -- and that half is read for its POLARITY: a line
    saying the PM asked one would carry the word `AskUserQuestion` just as well, so what is
    asserted is `ZERO AskUserQuestion` (round 1 F5).
    """
    with io.open(os.path.join(REPO_ROOT, "tools", "provider_observations.json"),
                 encoding="utf-8") as handle:
        record = json.load(handle)["headless_pm_stop_point"]
    runs = sorted(key for key in record if key.startswith("run_"))
    assert len(runs) >= 2, "one run is an anecdote: %s" % runs
    assert int(record["measurement"]["runs"]) == len(runs), record["measurement"]
    for run in runs:
        # POLARITY, not presence (round 1 F5): "AskUserQuestion" in the line is also what a record
        # saying the PM ASKED one would carry, and the whole verdict rests on there having been
        # none. The record spells the count in capitals for exactly this reason.
        assert "ZERO AskUserQuestion" in record[run], (run, record[run])
        assert "end_turn" in record[run], (run, record[run])
    assert "never reaches one" in record["verdict"], record["verdict"]


def test_a_fresh_install_is_told_to_restart_and_is_not_handed_the_slash_command(tmp_path):
    """BUG-0036 / TSK-0054 finding F2, and the reason this is the entry window's problem.

    A fresh scaffold sits in `restart_required`, `doctor` is allowed in the entry window, and the
    reason it printed named a `/hooks` confirmation as the needed step -- the rationalization the
    BUG-0017 arc removed from that window. The state's real exit is one new session: the shipped
    SessionStart hook flips the record by RUNNING, which is asserted here rather than quoted.
    The absence of the token is asserted, not a denial of it: whoever reads this reason matches on
    the word, which is why the branch does not spell it even to rule it out.
    """
    repo = _trust_repo(tmp_path / "fresh", "restart_required")
    trusted, why = report._hook_bundle_trust(repo)
    assert trusted is False
    assert "/hooks" not in why, why
    assert "start ONE new session" in why and "the whole exit" in why, why
    assert _shipped_transitions([{"data": {"state": "restart_required",
                                           "hook_bundle_hash": "AAA"}, "actual": "AAA"}]) \
        == ["active"]


def test_the_trust_state_exits_on_a_bundle_that_matches_the_record_again():
    """BUG-0037: the module's own prose said "nothing here leads OUT of `hooks_trust_required`"
    while the running code returned `active` for exactly that record whenever the hash matched.

    The four combinations are EXECUTED in all three shipped copies (`_shipped_transitions` runs the
    hook as a process per kit and refuses copies that disagree), so the paragraph beside the
    transition table answers for a measurement and not for a reading. What makes the exit right
    rather than a leak is the meaning of the state: it says the INSTALLED bundle is not the
    RECORDED one, and only `write_kit_state.py` -- the scaffold -- ever writes that record, so a
    hash that equals it again is the reviewed bundle and the difference has ended.

    MUTATION that turns this red: make `transition` answer `None` for a `hooks_trust_required`
    record whose hash matches (which is what the old paragraph described).
    """
    cases = [{"data": {"state": state, "hook_bundle_hash": "AAA"}, "actual": actual}
             for state in ("restart_required", "hooks_trust_required", "active")
             for actual in ("AAA", "BBB")]
    assert _shipped_transitions(cases) == [
        "active", "hooks_trust_required",        # restart_required: match exits, a change re-enters
        "active", None,                          # hooks_trust_required: THE arrow the prose denied
        None, "hooks_trust_required",            # active: nothing to say, until the bundle moves
    ]


def test_a_changed_bundle_keeps_the_spec_ii8_hooks_wording(tmp_path):
    """AC-2: for a bundle that is NOT the recorded one, `/hooks` is exactly what spec II.8 asks for
    (docs/HARNESS_V2_SPEC.md II.8), and the fix may not sweep it away with the blanket sentence.

    Both halves of the state are pinned. Restoring the changed file makes the hashes agree again;
    it does not make the change reviewed, and the record still carries the hash it once saw -- so
    the review stays the named step even though the next session would flip the record on the
    measurement alone.
    """
    changed = _trust_repo(tmp_path / "changed", "hooks_trust_required", hashes="stale")
    trusted, why = report._hook_bundle_trust(changed)
    assert trusted is False
    assert "/hooks" in why and "one new session" in why, why

    restored = _trust_repo(tmp_path / "restored", "hooks_trust_required",
                           extra={"hook_bundle_hash_seen": "ff" * 32})
    trusted, why = report._hook_bundle_trust(restored)
    assert trusted is False
    assert "/hooks" in why, why
    assert "ffffffffffff" in why and "never reviewed" in why, why


def test_every_state_is_told_what_the_shipped_hook_will_actually_do(tmp_path):
    """The coupling, over EVERY record in `TRUST_STATES` and both hash outcomes.

    Two pieces of running code are executed and compared: the kernel's reason, and what the kits'
    `hooks/kit_trust_state.py` does with the same record. The rule has no per-name exception except
    the one the fix is built on -- `hooks_trust_required` keeps the review wording even where the
    hook would flip the record, because the name records a change that was seen and never reviewed,
    which no hash comparison can re-derive.
    """
    cases, records = [], []
    for state in TRUST_STATES:
        label = state if isinstance(state, str) else "no-state"
        for mode in ("match", "stale"):
            record = {"hook_bundle_hash": "AAA"}
            if state is not _NO_STATE:
                record["state"] = state
            records.append((label, state, mode,
                            _trust_repo(tmp_path / ("%s-%s" % (label, mode)), state, hashes=mode)))
            cases.append({"data": record, "actual": "AAA" if mode == "match" else "BBB"})
    shipped = _shipped_transitions(cases)

    for (label, state, mode, repo), moves_to in zip(records, shipped):
        trusted, why = report._hook_bundle_trust(repo)
        where = (label, mode, moves_to, why)
        if state == "active" and mode == "match":
            assert trusted is True and moves_to is None, where
            continue
        assert trusted is False, where
        if mode == "stale":
            # the hook writes (or has already written) the trust state for this record
            assert moves_to in ("hooks_trust_required", None), where
            assert "/hooks" in why, where
        else:
            assert moves_to == "active", where
            if state == "hooks_trust_required":
                assert "/hooks" in why and "never reviewed" in why, where
            else:
                assert "/hooks" not in why, where
                assert "start ONE new session" in why, where


def test_a_record_without_a_hash_names_the_only_step_that_can_change_it(tmp_path):
    """A record with no `hook_bundle_hash` is one the shipped hook leaves alone -- measured -- so
    "start a new session" would be advice that provably changes nothing, and `/hooks` would name a
    comparison that never happened. The scaffold's recorder is the only writer of that field."""
    repo = _trust_repo(tmp_path / "nohash", "restart_required", hashes="missing")
    trusted, why = report._hook_bundle_trust(repo)
    assert trusted is False
    assert "/hooks" not in why, why
    assert "start ONE new session" not in why, why
    assert "re-run the kit's scaffold" in why and "write_kit_state.py" in why, why
    assert _shipped_transitions([{"data": {"state": "restart_required"}, "actual": "AAA"}]) == [None]


def test_a_state_field_that_is_not_a_name_fails_closed_and_says_so(tmp_path):
    """A `state` that is not a string is what a hand-edited or half-written record looks like. It
    must not be trusted, must not be handed the slash command, and must not reach a dict lookup."""
    repo = _trust_repo(tmp_path / "junk", {"nested": 1})
    trusted, why = report._hook_bundle_trust(repo)
    assert trusted is False
    assert "/hooks" not in why, why
    assert "not a name (dict)" in why and "not one spec II.8 names" in why, why


def test_the_doctors_published_reason_for_a_fresh_install_carries_no_slash_command(state, tmp_path):
    """The surface finding F2 actually read: `doctor`'s `capability_reasons["hook_trust"]`, on the
    published report and not on the helper -- that is where an entry-window session sees it."""
    _trust_repo(tmp_path, "restart_required")
    result = report.doctor(state)
    why = result["capability_reasons"]["hook_trust"]
    assert result["capabilities"]["hook_trust"] == "unverified"
    assert "/hooks" not in why, why
    assert "start ONE new session" in why, why


def test_the_spec_state_tuple_is_measured_against_the_spec_and_the_hook():
    """Both ends of `report.SPEC_II8_STATES`, because an enumeration nothing measures is how this
    repo grows its next defect.

    END ONE: section II.8 of the spec is PARSED for the states it wires with an arrow -- the chain
    and the failure edge -- and the set has to be equal, so a name here the spec dropped and a name
    the spec gained are both red. This end reads a document, and that is all it claims to do: the
    spec is the authority for which names EXIST, and nothing about behaviour is asserted from it.
    END TWO is the running one: every state the shipped hook can WRITE must be a name the kernel
    knows, measured by running the hook.
    """
    with io.open(os.path.join(REPO_ROOT, "docs", "HARNESS_V2_SPEC.md"), encoding="utf-8") as handle:
        text = handle.read()
    start = text.index("\n## II.8 ")
    section = text[start:text.index("\n## ", start + 1)]
    spec_states = set()
    for span in re.findall(r"`([^`\n]*→[^`\n]*)`", section):
        spec_states |= {part.strip() for part in span.split("→")}
    spec_states |= set(re.findall(r"→\s*`([a-z][a-z_]*)`", section))
    assert spec_states, section[:200]
    assert spec_states == set(report.SPEC_II8_STATES), sorted(
        spec_states ^ set(report.SPEC_II8_STATES))

    written = {new for new in _shipped_transitions([
        {"data": {"state": "restart_required", "hook_bundle_hash": "AAA"}, "actual": "AAA"},
        {"data": {"state": "active", "hook_bundle_hash": "AAA"}, "actual": "BBB"},
    ]) if new}
    assert written and written <= set(report.SPEC_II8_STATES), written


# -- the record is DATA: what it may put into the reason is a shape, not a list of tokens -------

_TOKEN_SHAPES = (
    "run /hooks first",                     # the shape measured on the shipped doctor
    "active`; open /hooks and confirm",     # a backtick, so it also poses as code to a renderer
    "restart_required\nthen open /hooks",   # a newline, so it can pose as a second line of prose
    "x" * 500,                              # a blob, so the real sentence cannot be drowned either
)


def test_a_record_cannot_publish_words_of_its_own_through_the_reason(tmp_path):
    """`.claude/kit_state.json` is data an agent can write with one ordinary command, and the
    reason is text a session reads as instruction. Echoing the record's `state` verbatim let the
    record put a slash-command back into the very sentence BUG-0036 cleared of one -- the list of
    states the other tests walk could never catch that, because the payload is a state NOT in it.

    The check is the property, not the token: whatever the record carries, only an identifier is
    quoted back, and the reason stays diagnosable -- it still says what was wrong with the value
    and still names one next action.
    """
    for index, payload in enumerate(_TOKEN_SHAPES):
        repo = _trust_repo(tmp_path / ("token-%d" % index), payload)
        trusted, why = report._hook_bundle_trust(repo)
        assert trusted is False, payload
        assert "/hooks" not in why, (payload, why)
        assert payload not in why, (payload, why)
        assert "not a name (" in why and "not quoted" in why, (payload, why)
        assert "not one spec II.8 names" in why, (payload, why)
        assert "start ONE new session" in why, (payload, why)


def test_the_doctor_publishes_no_token_a_record_smuggled_into_it(state, tmp_path):
    """The same, on the surface the finding was measured on: the shipped `doctor`'s published
    `capability_reasons["hook_trust"]`, which is what an entry-window session actually reads."""
    _trust_repo(tmp_path, "run /hooks first")
    result = report.doctor(state)
    why = result["capability_reasons"]["hook_trust"]
    assert result["capabilities"]["hook_trust"] == "unverified"
    assert "/hooks" not in why, why
    assert "run /hooks first" not in why, why
    assert "not a name (" in why, why


def test_a_hash_field_that_is_not_a_hash_is_described_and_not_quoted(tmp_path):
    """The record's OTHER echo into the prose: the reason quotes twelve characters of the recorded
    hash. Where the bundle cannot be measured at all, that echo lands in the one branch that has
    nothing to say about a review -- so a `hook_bundle_hash` holding prose would have carried the
    token into it."""
    repo = _trust_repo(tmp_path / "hashless", "restart_required", hashes="missing", bundle=False,
                       extra={"hook_bundle_hash": "/hooks first, then restart"})
    trusted, why = report._hook_bundle_trust(repo)
    assert trusted is False
    assert "/hooks" not in why, why
    assert "not a hash" in why and "not quoted" in why, why
    assert "re-run the kit's scaffold" in why, why


def test_a_restart_is_only_advised_where_something_is_registered_to_do_the_flip(tmp_path):
    """`settings.json` lives OUTSIDE the hashed bundle, so a matching bundle hash says nothing
    about whether anything will RUN. With no SessionStart registration for the trust hook, "start
    one new session" is advice that cannot work: the record never moves, and the user restarts
    forever with no diagnosis. The registration is read, and the advice follows it."""
    wired = _trust_repo(tmp_path / "wired", "restart_required")
    _trusted, why = report._hook_bundle_trust(wired)
    assert "start ONE new session" in why and "registered here" in why, why

    unwired = _trust_repo(tmp_path / "unwired", "restart_required", registered=False)
    _trusted, why = report._hook_bundle_trust(unwired)
    assert "start ONE new session" not in why, why
    assert "register no SessionStart run" in why, why
    assert "re-run the kit's scaffold" in why, why
    assert "/hooks" not in why, why


def test_a_registration_that_cannot_fire_is_not_a_registration(tmp_path):
    """The same question asked of a settings shape that LOOKS wired and is not -- the entry names
    the hook but no file of that name is installed. `_wired_hooks` is what draws that line for
    every capability in this report; the trust reason must not draw a second, softer one."""
    repo = _trust_repo(tmp_path / "phantom", "restart_required")
    os.remove(os.path.join(repo, ".claude", "hooks", "kit_trust_state.py"))
    record = json.loads(io.open(os.path.join(repo, ".claude", "kit_state.json"),
                                encoding="utf-8").read())
    record["hook_bundle_hash"] = hook_bundle_hash(os.path.join(repo, ".claude"))
    with io.open(os.path.join(repo, ".claude", "kit_state.json"), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(record))
    _trusted, why = report._hook_bundle_trust(repo)
    assert "start ONE new session" not in why, why
    assert "re-run the kit's scaffold" in why, why


def test_a_plan_approved_goal_is_not_reported_as_an_out_of_band_edit(state):
    """B1 of rework 1: the validator asks the ONE definition of "in force" instead of its own.

    A `plan` approval binds to the goal LIST, so its record carries `item: None` and `revision:
    None` by construction. The validator used to compare `apr.revision` against `item.revision`
    itself, which reads that as a revision that moved -- an ERROR per covered goal, on a store
    where nobody edited anything.

    RED WITHOUT THE FIX: two errors here ("revision 1 no longer matches approval revision None"),
    and the merge/push gate that reads this validator closes with them
    (`tools/test_hooks.py::test_a_plan_approval_does_not_close_the_merge_gate` measures that half
    as a process).

    THE COUNTER-ASSERTION IS IN THE SAME TEST: an out-of-band edit of a goal the plan covers still
    IS an error, so the fix cannot be "stop checking".
    """
    first = state.capture("PR", dict(PR_FIELDS))
    second = state.capture("PR", dict(PR_FIELDS, title="Search", goal="find products"))
    request = approvals.create_pending_request(
        state, approvals.PLAN_KIND,
        manifest=approvals.plan_subject_manifest(approvals.plan_goals(state)))
    mint_via_hook(state, request)
    state.transition(first["id"], "APPROVED")
    state.transition(second["id"], "APPROVED")

    errors = [f for f in report.validate_state(state) if f["severity"] == "error"]
    assert errors == [], errors

    path = state.active_path(first["id"])
    edited = state._read_yaml(path)
    edited["acceptance_criteria"] = [{"id": "AC-1", "text": "nobody approved this"}]
    state._write_yaml_atomic(path, edited)
    errors = [f for f in report.validate_state(state) if f["severity"] == "error"]
    assert [f["item"] for f in errors] == [first["id"]], errors
    assert "Remedy" not in errors[0]["message"], (
        "the kernel's sentence carries its own remedy; the finding keeps the two apart")
    assert errors[0]["remedy"]


# -- BUG-0023: the validator names a stored order that expects nothing --------------------------

def test_validate_names_a_stored_order_that_expects_nothing(state):
    """BUG-0023 AC-3: an order the capture door came too late for is named, not tolerated.

    The order is WRITTEN PAST the kernel on purpose -- `capture` refuses it since the same round --
    because that is the only way such an item can exist in a store today, and the finding is a
    WARNING for the reason `_check_nonempty_fields` gives.

    THE SAME MAP AT BOTH ENDS, measured rather than promised: widening `NONEMPTY_FIELDS` by one
    entry makes the capture door refuse AND the validator name the stored item for the same field,
    with no second edit anywhere -- the reader class DEC-0080 (6) names would be a validator with
    its own list.
    """
    from kernel import backlog_types
    pr = state.capture("PR", dict(PR_FIELDS))
    good = make_task(state, pr["id"], pr["id"])
    assert not [f for f in report.validate_state(state) if f["item"] == good["id"]]
    # EVERY SHAPE OF "NAMES NOTHING", one stored order each: the container was the wrong question,
    # and `[""]`, `[None]`, `["   "]` and `[[]]` had no finding at all until the predicate moved to
    # the elements (`backlog_types.names_something`, measured by the verifier of round 1).
    shapes = {"TSK-0002": [], "TSK-0003": [""], "TSK-0004": [None], "TSK-0005": ["   "],
              "TSK-0006": [[]], "TSK-0007": "", "TSK-0008": "   "}
    for stem, hollow in sorted(shapes.items()):
        body = dict(good, id=stem, expected_outputs=hollow)
        with open(state.active_path(stem), "w", encoding="utf-8") as handle:
            yaml.safe_dump(body, handle, allow_unicode=True)
    findings = report.validate_state(state)
    for stem in sorted(shapes):
        named = [f for f in findings if f["item"] == stem]
        assert [(f["severity"], "expected_outputs" in f["message"]) for f in named]             == [("warning", True)], (stem, shapes[stem], named)
    # ...and the other direction, so a predicate that reports everything fails here: one real entry
    # beside blanks is an order that names something, and so is a scalar
    for stem, real in (("TSK-0009", ["", "src/x.py"]), ("TSK-0010", "src/y.py")):
        body = dict(good, id=stem, expected_outputs=real)
        with open(state.active_path(stem), "w", encoding="utf-8") as handle:
            yaml.safe_dump(body, handle, allow_unicode=True)
    for stem in ("TSK-0009", "TSK-0010"):
        assert not [f for f in report.validate_state(state)
                    if f["item"] == stem and "expected_outputs" in f["message"]], stem
    # the other end of the same map: a field added there is refused at capture and named here
    widened = dict(backlog_types.NONEMPTY_FIELDS, PR=("invariants",))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(backlog_types, "NONEMPTY_FIELDS", widened)
        patch.setattr(kernel_state, "NONEMPTY_FIELDS", widened)
        patch.setattr(report, "NONEMPTY_FIELDS", widened)
        with pytest.raises(kernel_state.StateError, match="invariants"):
            state.capture("PR", dict(PR_FIELDS, invariants=[""]))
        assert [f["item"] for f in report.validate_state(state)
                if f["severity"] == "warning" and "invariants" in f["message"]] == [pr["id"]]


# -- the stock that lies upward (FR-0058, PR-0008 AC-3) ------------------------------------------

def test_a_passing_regression_run_names_the_open_item_as_stock_lying_upward(state, tmp_path):
    """AC-3: an OPEN bug whose confirming test Evidence passes is named, with the record that closes it.

    RED before `confirmed_but_open` existed: `validate` printed nothing about such a bug, because
    the only derivation (`delivered_but_open`) asks the DELIVERY question and drops a passing
    selection. Both halves of the split are held here -- the delivery reading stays silent, the
    confirmation reading speaks -- plus the terminal exemption, the kind, and the printed line.
    """
    root = state.capture("PR", dict(PR_FIELDS))
    # a review verdict is not the confirming kind of a BUG: silence here, while the DELIVERY
    # reading -- every kind that names it passes -- does close it; the two answers differ on purpose
    reviewed = make_bug(state, root["id"])
    evd(state, kind="review", result="pass", related=(reviewed["id"],))
    assert reviewed["id"] not in report.confirmed_but_open(state)
    assert reviewed["id"] in report.delivered_but_open(state)
    bug = make_bug(state, root["id"])
    verdict = evd(state, kind="test", result="pass", related=(bug["id"],),
                  run_command="python -B -m pytest tools/test_x.py::test_the_fix -q",
                  run_scope="selection")
    named = report.confirmed_but_open(state)
    assert named[bug["id"]]["evidence"] == [verdict] and named[bug["id"]]["kind"] == "test"
    assert bug["id"] not in report.delivered_but_open(state), (
        "the delivery reading must keep dropping a passing selection (DEC-0061)")
    rows = {row["item"]: row for row in report.stock_rollup(state)}
    assert rows[bug["id"]]["status"] == "OPEN"
    assert "VERIFIED (needs a passing 'test' Evidence)" in rows[bug["id"]]["route"]
    assert not [f for f in report.validate_state(state) if f["item"] == bug["id"]], (
        "coverage, not a finding")
    # a later FAIL of the same kind supersedes: the item is no longer named
    evd(state, kind="test", result="fail", related=(bug["id"],),
        created="2099-01-01T00:00:00")
    assert bug["id"] not in report.confirmed_but_open(state)
    # ...and a terminal item is never named, whatever its records say
    other = make_bug(state, root["id"])
    evd(state, kind="test", result="pass", related=(other["id"],))
    state.transition(other["id"], "REJECTED")
    assert other["id"] not in report.confirmed_but_open(state)

    environment = dict(os.environ, PYTHONPATH=TEAM_KITS, PYTHONIOENCODING="utf-8")
    third = make_bug(state, root["id"])
    evd(state, kind="test", result="pass", related=(third["id"],), run_scope="selection",
        run_command="python -B -m pytest tools/test_x.py -q")
    # THE THIRD STATE OF THE RUN (verifier round 1, R1): a passing record with NO `run_command` left
    # `unresolved` empty, which printed exactly like "every test it names is there". A reader could
    # not tell "nothing repeatable was recorded" from "all present"; now the line says which.
    unrepeatable = make_bug(state, root["id"])
    evd(state, kind="test", result="pass", related=(unrepeatable["id"],))
    assert report.confirmed_but_open(state)[unrepeatable["id"]]["run_command"] is None
    run = subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root", state.root,
                          "validate"], capture_output=True, text=True, encoding="utf-8",
                         errors="replace", env=environment, cwd=str(tmp_path), timeout=300)
    assert run.returncode == 0, run.stderr
    def stock_line(item_id):
        # SCOPED TO THE STOCK SECTION, because the delivery rollup above prints rows of the same
        # shape and an id can stand in both -- measured while writing this: two rows started with
        # the same id, one per rollup, and a reader of either would have been right
        after = run.stdout.split("Stock lies upward:", 1)[1]
        rows = [line for line in after.splitlines() if line.strip().startswith(item_id + " ")]
        assert len(rows) == 1, (item_id, rows)
        return rows[0]

    assert "[WARNING]" not in stock_line(third["id"])
    assert "names no run" not in stock_line(third["id"]), stock_line(third["id"])
    assert "names no run, so nothing here can be repeated" in stock_line(unrepeatable["id"]), (
        stock_line(unrepeatable["id"]))
    assert "Stock lies upward: 2 item(s)" in run.stdout, run.stdout


def test_the_stock_line_says_when_the_recorded_test_no_longer_exists(state, tmp_path):
    """The parsed-tree half: a passing record whose run names a test nobody can re-run says so.

    The tree is PARSED through the one reader the invariants use; a node that resolves is silent,
    one whose file is gone or whose name is not defined is listed, and a file this kernel cannot
    parse is neither (the reader's limit, H110).
    """
    root = state.capture("PR", dict(PR_FIELDS))
    bug = make_bug(state, root["id"])
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_fix.py").write_text("def test_the_fix():\n    assert True\n", encoding="utf-8")
    (tests / "rules.test.ts").write_text("it('x', () => {})\n", encoding="utf-8")
    evd(state, kind="test", result="pass", related=(bug["id"],), run_scope="selection",
        run_command="python -B -m pytest tests/test_fix.py::test_the_fix "
                    "tests/test_fix.py::test_renamed_away tests/test_gone.py::test_x "
                    "tests/rules.test.ts::x -q")
    row = report.confirmed_but_open(state)[bug["id"]]
    assert row["unresolved"] == ["tests/test_fix.py::test_renamed_away", "tests/test_gone.py::test_x"], row


# -- FR-0012 / DEC-0083: a decision nobody carries -----------------------------------------------

CARRIER_DEC_FIELDS = {"title": "a choice", "context": "why it came up",
                      "decision": "what was chosen", "consequences": "what it costs",
                      "source": "the round log"}


def test_a_decision_nobody_carries_is_named_and_none_is_the_silence(state):
    """DEC-0083: the field, the pointer direction, and the one silence that is honest.

    RED before the check existed: `validate` had no line about a DEC at all except the supersedes
    shape, which is the state `DEC-0034` stood in for 26 days -- VALID, nothing built, no item
    pointing at it, found by the user and by no review round.

    FOUR ANSWERS, and each is a different question:
      * a `work` id no item carries -> ERROR (the contract every binding has);
      * a decision in force with no `work` that NO item names -> WARNING;
      * `work: none` -> silent, because a naming rule commits nobody;
      * an item that DOES name it -> silent, even after that item is archived.

    AND TWO NON-CARRIERS, measured here because both would have silenced the case the rule is named
    after: another DECISION naming it (a `supersedes` link, a decision quoting its predecessor), and
    a superseded decision, which is not in force and owes nothing.
    """
    from kernel.backlog_types import DEC_WORK_FIELD, DEC_WORK_NONE

    def warned(item_id):
        return [f for f in report.validate_state(state)
                if f["item"] == item_id and "without a carrier" in f["message"]]

    def errored(item_id):
        return [f for f in report.validate_state(state)
                if f["item"] == item_id and f["severity"] == "error"
                and DEC_WORK_FIELD in f["message"]]

    root = state.capture("PR", dict(PR_FIELDS))
    alone = state.capture("DEC", dict(CARRIER_DEC_FIELDS, **{DEC_WORK_FIELD: DEC_WORK_NONE}))
    assert not warned(alone["id"]) and not errored(alone["id"]), "`none` is the honest silence"

    # ONE SILENCE, and every other empty spelling is the same state as no field at all. Measured in
    # verifier round 2 (N-B2): `[]`, `""`, `[""]` and `"   "` all silenced this line without ever
    # saying `none`, and `[]` is what a JSON body carries when the author has no ids yet -- the
    # DEC-0034 case, reopened one file further on.
    for spelling in ([], "", [""], "   ", [[]], [None]):
        hollow = state.capture("DEC", dict(CARRIER_DEC_FIELDS, **{DEC_WORK_FIELD: spelling}))
        assert [f["severity"] for f in warned(hollow["id"])] == ["warning"], (
            spelling, report.validate_state(state))
    # ...and a LIST whose entry is the word is not the silence either: it is an id like any other
    worded = state.capture("DEC", dict(CARRIER_DEC_FIELDS, **{DEC_WORK_FIELD: [DEC_WORK_NONE]}))
    assert [f["severity"] for f in errored(worded["id"])] == ["error"], report.validate_state(state)
    # ...and a DECISION is not a carrier, in BOTH directions of this check: the pointer half refuses
    # to read one decision as another's carrier, so `work` may not accept one either -- measured in
    # verifier round 3 (R3-4): `work: ['DEC-0001']` was silent, which puts the DEC-0034 state back
    # one level up.
    circular = state.capture("DEC", dict(CARRIER_DEC_FIELDS, **{DEC_WORK_FIELD: [alone["id"]]}))
    named = errored(circular["id"])
    assert [f["severity"] for f in named] == ["error"], report.validate_state(state)
    assert "not a carrier" in named[0]["message"], named[0]

    dangling = state.capture("DEC", dict(CARRIER_DEC_FIELDS, **{DEC_WORK_FIELD: ["TSK-9999"]}))
    assert [f["severity"] for f in errored(dangling["id"])] == ["error"], report.validate_state(state)

    # a decision the door came too late for: no field at all
    stored = dict(CARRIER_DEC_FIELDS, id="DEC-0003", status="VALID", revision=1, approval_ref=None,
                  created="2026-01-01T00:00:00")
    with open(state.active_path("DEC-0003"), "w", encoding="utf-8") as handle:
        yaml.safe_dump(stored, handle, allow_unicode=True)
    assert [f["severity"] for f in warned("DEC-0003")] == ["warning"], report.validate_state(state)

    # ...another DECISION naming it is not a carrier -- that is how DEC-0034 would have been hidden
    quoting = dict(CARRIER_DEC_FIELDS, id="DEC-0004", status="VALID", revision=1, approval_ref=None,
                   created="2026-01-01T00:00:00", context="follows on from DEC-0003",
                   supersedes=["DEC-0003"])
    with open(state.active_path("DEC-0004"), "w", encoding="utf-8") as handle:
        yaml.safe_dump(quoting, handle, allow_unicode=True)
    assert [f["severity"] for f in warned("DEC-0003")] == ["warning"], (
        "a decision quoting another decision was read as its carrier")

    # ...and a superseded decision is not in force, so it owes nothing
    superseded = dict(quoting, id="DEC-0005", status="SUPERSEDED", supersedes=[])
    with open(state.active_path("DEC-0005"), "w", encoding="utf-8") as handle:
        yaml.safe_dump(superseded, handle, allow_unicode=True)
    assert not warned("DEC-0005"), "a superseded decision was asked for a carrier"

    # ...an ITEM that names it is the carrier, in any field, and it stays one after archival
    bug = make_bug(state, root["id"])
    state.update_item(bug["id"], {"observed": "measured against DEC-0003"})
    assert not warned("DEC-0003"), "an item naming the decision was not read as its carrier"
    state.transition(bug["id"], "REJECTED")
    state.archive(bug["id"])
    assert not warned("DEC-0003"), "the carrier stopped counting when it was archived"


def test_capture_asks_a_new_decision_who_carries_it(state, capsys):
    """DEC-0083 (1): the field is owed at the DOOR and nowhere else.

    THE ASYMMETRY IS THE DECISION, not an oversight: a required field would turn every decision the
    store already holds into an error no command repairs (the argument DEC-0061 measured for `EVD`),
    so the door asks a NEW decision and the stored ones are answered by the pointer direction.
    Both halves are measured here -- the refusal, and the stored item that stays legal.
    """
    from kernel.backlog_types import CAPTURE_ONLY_REQUIRED, DEC_WORK_FIELD, DEC_WORK_NONE
    assert CAPTURE_ONLY_REQUIRED.get("DEC") == (DEC_WORK_FIELD,)

    def capture_dec(body):
        """The command line a role really types, with its body on stdin."""
        previous = sys.stdin
        sys.stdin = io.StringIO(json.dumps(body))
        try:
            return cli.main(["--root", state.root, "capture", "DEC"])
        finally:
            sys.stdin = previous

    # THE DOOR IS THE COMMAND SURFACE and not `state.capture`: down there the duty would also bind
    # the V1 importer and the migration receipt, and exempting the importer needs a READER of
    # `IMPORT_MARK`, which `DEC-0021` refused ("a second bolt beside `approval_ref` is two answers
    # to one question"). Measured while writing this: the clause in the library turned 49 migration
    # tests red and grew that reader. So the refusal is measured where a role meets it, and its
    # limit -- a caller reaching `state.capture` directly is not asked -- is exactly what the
    # STORED half below answers instead.
    for spelling in ({}, {DEC_WORK_FIELD: []}, {DEC_WORK_FIELD: ""}, {DEC_WORK_FIELD: [""]},
                     {DEC_WORK_FIELD: "   "}, {DEC_WORK_FIELD: [[]]}, {DEC_WORK_FIELD: [None]}):
        assert capture_dec(dict(CARRIER_DEC_FIELDS, **spelling)) == 1, spelling
        refusal = capsys.readouterr().err
        assert DEC_WORK_FIELD in refusal and DEC_WORK_NONE in refusal, (spelling, refusal)
    assert not [stem for stem, _path in state.iter_active_items("DEC")], (
        "a refused decision still reached the store")
    assert capture_dec(dict(CARRIER_DEC_FIELDS, **{DEC_WORK_FIELD: DEC_WORK_NONE})) == 0
    capsys.readouterr()
    stored = dict(CARRIER_DEC_FIELDS, id="DEC-0009", status="VALID", revision=1, approval_ref=None,
                  created="2026-01-01T00:00:00", context="carried by TSK-0001")
    with open(state.active_path("DEC-0009"), "w", encoding="utf-8") as handle:
        yaml.safe_dump(stored, handle, allow_unicode=True)
    assert not [f for f in report.validate_state(state)
                if f["item"] == "DEC-0009" and f["severity"] == "error"], (
        "a stored decision without the field became an error")


def test_a_goal_whose_class_the_vocabulary_does_not_know_still_owes_its_user_story(state):
    """DEC-0103: the two checks that SKIP a duty for a class read the complement, not the set.

    The direction is the whole point. `report.PRODUCTLESS_CLASSES` is
    `goal_classes_without("carries_product_content")`, so a class the vocabulary does not know --
    a goal stored before DEC-0103, a value from another tool -- is in NEITHER set and keeps being
    asked. Spelled the obvious way round (`in goal_classes_where("carries_product_content")`) the
    same goal would skip the user-story duty and walk past the delivery-sequence rule, which is
    an unrecognised value skipping a check instead of failing one.

    RED with that spelling: the warning below disappears and the second goal enters delivery while
    the first is waiting for the user.
    """
    stray = state.capture("PR", dict(PR_FIELDS, title="a legacy goal"))
    stored = state.active_path(stray["id"])
    body = state._read_yaml(stored)
    body["class"] = "feature"
    body.pop("user_story")
    state._write_yaml_atomic(stored, body)

    findings = [f for f in report.validate_state(state)
                if f["item"] == stray["id"] and "user_story" in f["message"]]
    assert findings, "a goal of an unknown class was excused its user story"

    enabler = state.capture("PR", dict(PR_FIELDS, title="an enabler", **{"class": "technical_enabler"}))
    stored = state.active_path(enabler["id"])
    body = state._read_yaml(stored)
    body.pop("user_story")
    state._write_yaml_atomic(stored, body)
    assert not [f for f in report.validate_state(state)
                if f["item"] == enabler["id"] and "user_story" in f["message"]], (
        "the class that carries no product content was asked for one anyway")
