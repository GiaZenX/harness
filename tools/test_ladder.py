#!/usr/bin/env python3
"""The model ladder the dispatcher derives at every lease (DEC-0034, DEC-0047, DEC-0076, DEC-0077,
DEC-0078) -- one red-first test per rule, measured against the kernel, never against a copy of it.

WHAT IS MEASURED: `kernel.dispatch.ladder_for_order` and everything `create_lease` /
`validate_dispatch` do with its answer, on projects built the way the scaffold builds them (a
scaffold record naming the kit, a kit store under HOME with the kit's `ladder.yaml` and the store's
`model_tiers.yaml`, installed role definitions with a `model:` pin). The kit-less project of the
rest of this suite (no record) is measured too, because it is the shape this repository itself runs
in and the one that must keep dispatching without a ladder.

THE SHIPPED DECLARATIONS are measured against the kits' own role trees in both directions and
against the decisions that dictated them (DEC-0078 (1)/(2) for office, DEC-0047 for dev/research),
so a declaration that quietly stops saying what the user decided is red here and not in a pilot.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

TEAM_KITS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "team-kits")
sys.path.insert(0, TEAM_KITS)

from conftest import approve, drive_task_to, satisfy_the_architect_step  # noqa: E402 -- shared suite helpers
from kernel import dispatch  # noqa: E402
from kernel.backlog_types import AUTOMATA  # noqa: E402
from kernel.dispatch import DispatchError  # noqa: E402
from kernel.state import ProjectState  # noqa: E402

yaml = pytest.importorskip("yaml")

PR_FIELDS = {
    "title": "Checkout flow", "class": "normal", "problem": "no checkout",
    "goal": "working checkout", "acceptance_criteria": [{"id": "AC-1", "text": "order completes"}],
    "invariants": [], "out_of_scope": [], "priority": "high",
}
TSK_FIELDS = {
    "type": "implementation", "assigned_role": "backend-developer", "acceptance_refs": ["AC-1"],
    "required_inputs": [], "allowed_scope": ["src/"], "forbidden_scope": ["secrets/"],
    "expected_outputs": ["src/x.py"], "dependencies": [],
}

# A declaration in the shape the kits ship, small enough to mutate one field at a time. The kit
# name is the test's own, so nothing here rides on today's catalogue.
LADDER = {
    "rungs": ["sonnet", "opus", "fable"],
    "top": "fable",
    "effort": {"default": "high", "large": "xhigh"},
    # One rung per failed run and NO effort escalation -- the pre-DEC-0096 shape, kept here on
    # purpose so the rule-2 tests below still measure the rung axis alone. The DEC-0096 shape is
    # declared per test (`ESCALATES_EFFORT_FIRST`) and by the shipped kits.
    "escalation": {"failed_runs_per_rung": 1, dispatch.EFFORT_STEPS_KEY: 0},
    "classes": {"planning": "top", "architecture": "top", "design": "opus", "qa": "opus",
                "build": "pin"},
    "roles": {"project-manager": "planning", "software-architect": "architecture",
              "product-designer": "design", "quality-engineer": "qa",
              "backend-developer": "build"},
    "exceptions": {},
}


def kit_dirs():
    """Every shipped kit -- the directories under team-kits/ that carry a constitution."""
    return sorted(os.path.join(TEAM_KITS, name) for name in os.listdir(TEAM_KITS)
                  if os.path.isfile(os.path.join(TEAM_KITS, name, "constitution", "AGENTS.md")))


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


class Store:
    """A kit store under a HOME of its own, and projects scaffolded against it -- the shape the
    installer leaves, built by hand so one field at a time can be wrong."""

    def __init__(self, tmp_path, monkeypatch):
        self.home = tmp_path / "home"
        self.root = self.home / ".claude" / "team-kits"
        self.tmp_path = tmp_path
        monkeypatch.setenv("HOME", str(self.home))
        monkeypatch.setenv("USERPROFILE", str(self.home))
        self.root.mkdir(parents=True)
        # the store's own tiers table, so an alias pin resolves the way it does on a real machine
        shutil.copy(os.path.join(TEAM_KITS, dispatch.TIERS_FILE), str(self.root / dispatch.TIERS_FILE))

    def kit(self, name, ladder=LADDER, with_architect_step=False):
        """A kit in the store: a template tree (with or without the architect step's home) and a
        ladder declaration; `ladder=None` ships none."""
        template = self.root / name / "templates" / "project_memory"
        (template / ("system/active" if with_architect_step else "product/active")).mkdir(parents=True)
        if ladder is not None:
            write(str(self.root / name / dispatch.LADDER_FILE), yaml.safe_dump(ladder, sort_keys=False))
        return self.root / name

    def project(self, name, kit, roles, goal_class="normal", record=True):
        """A project the scaffold left behind: record, installed roles with pins, an approved goal."""
        repo = self.tmp_path / name
        (repo / ".claude" / "agents").mkdir(parents=True)
        if record:
            write(str(repo / ".claude" / "team_kit_roles.txt"),
                  "# agents-and-skills:team-kit-roles v1 team=%s count=%d\n%s\n"
                  % (kit, len(roles), "\n".join(roles)))
        for role, pin in roles.items():
            write(str(repo / ".claude" / "agents" / (role + ".md")),
                  "---\nname: %s\nmodel: %s\neffort: high\ntools: Read\n---\nbody\n" % (role, pin))
        (repo / "project_memory").mkdir()
        state = ProjectState(str(repo / "project_memory"))
        pr = state.capture("PR", dict(PR_FIELDS, **{"class": goal_class}))
        approve(state, pr["id"], "scope")
        return state, pr

    @staticmethod
    def order(state, pr, role="backend-developer", **overrides):
        fields = dict(TSK_FIELDS, product_requirement=pr["id"], derives_from=pr["id"],
                      assigned_role=role,
                      allowed_scope=["src/order-%d/**" % (len(list(state.iter_active_items("TSK"))) + 1)])
        fields.update(overrides)
        task = dispatch.create_task(state, fields)
        state.transition(task["id"], "READY")
        # the architect step, where the KERNEL says the order owes one (a kit-less project is
        # asked, DEC-0079 (4)); the fake kits above ship no home for it and are not
        satisfy_the_architect_step(state, state.read_item(task["id"]), pr)
        return state.read_item(task["id"])


@pytest.fixture
def store(tmp_path, monkeypatch):
    return Store(tmp_path, monkeypatch)


def lease_of(state, task):
    lease = dispatch.create_lease(state, task["id"])
    return lease, state.read_item(task["id"])


# -- the shipped declarations -------------------------------------------------------------------

def test_every_kit_ships_a_declaration_the_kernel_accepts():
    """DEC-0078 (3): every kit declares its OWN ladder, and the kernel's validator accepts each.

    Through `_valid_ladder`, the reader the dispatcher runs -- a declaration that parses but would
    be refused at the first lease is exactly what this catches before a pilot does.
    """
    for kit in kit_dirs():
        path = os.path.join(kit, dispatch.LADDER_FILE)
        assert os.path.isfile(path), "%s ships no %s" % (os.path.basename(kit), dispatch.LADDER_FILE)
        with io.open(path, encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
        accepted = dispatch._valid_ladder(os.path.basename(kit), raw)
        assert accepted["top"] in accepted["rungs"]


def test_every_kit_role_has_a_class_and_every_classed_role_ships():
    """Both ends of `roles:` against the kit's own agents directory.

    A role without a class is refused at its first dispatch (`ladder_for_order`); a class for a
    role the kit does not ship is a dead line that would hide the first case behind a typo. Neither
    can be read off the declaration alone, so the agents directory is the second reader.
    """
    for kit in kit_dirs():
        with io.open(os.path.join(kit, dispatch.LADDER_FILE), encoding="utf-8") as handle:
            declared = set(yaml.safe_load(handle)["roles"])
        shipped = {name[:-3] for name in os.listdir(os.path.join(kit, "agents"))
                   if name.endswith(".md")}
        assert declared == shipped, (
            "%s: roles without a class %s; classes without a role %s"
            % (os.path.basename(kit), sorted(shipped - declared), sorted(declared - shipped)))


def test_the_shipped_declarations_say_what_the_decisions_decided():
    """DEC-0047 / DEC-0078 as data: dev and research climb to fable at high/xhigh; office tops at
    opus at medium/high, the office-developer alone climbs to fable, the filing pair runs low.

    The decisions name the kits, so this test does too -- it is the one place the user's words are
    compared with the file, and a declaration that drifted from them is a finding for the user, not
    a kernel defect.
    """
    ladders = {}
    for kit in kit_dirs():
        with io.open(os.path.join(kit, dispatch.LADDER_FILE), encoding="utf-8") as handle:
            ladders[os.path.basename(kit)] = dispatch._valid_ladder(kit, yaml.safe_load(handle))
    for name in ("dev-team", "research-team"):
        assert ladders[name]["top"] == "fable", name
        assert ladders[name]["effort"] == {"default": "high", "large": "xhigh"}, name
    office = ladders["office-team"]
    assert office["top"] == "opus"
    assert office["effort"] == {"default": "medium", "large": "high"}
    assert office["exceptions"]["office-developer"] == {"top": "fable"}
    for role in ("records-clerk", "filing-reviewer"):
        assert office["exceptions"][role] == {"effort": "low"}, role
    assert not any(rule.get("top") == "fable" for role, rule in office["exceptions"].items()
                   if role != "office-developer"), "a second office role climbs to fable"
    for name, ladder in ladders.items():
        assert ladder["rungs"] == ["sonnet", "opus", "fable"], name


def shipped_ladder(kit):
    """One kit's declaration AS DECLARED -- the shipped file, never a copy, and never the
    normalised form: `_valid_ladder` flattens `escalation:` into its result, so a store stocked
    with that form would be a declaration no kit ships. Validated on the way through, so a file
    the kernel would refuse cannot reach a fixture."""
    with io.open(os.path.join(TEAM_KITS, kit, dispatch.LADDER_FILE), encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    dispatch._valid_ladder(kit, json.loads(json.dumps(raw)))
    return raw


def test_the_build_starts_on_opus_and_only_the_architecture_starts_on_the_top_rung(store):
    """DEC-0095 (1)/(2)/(4a) as the kits declare it AND as the kernel answers it.

    The decision names the two kits it moved, so this test does too (like
    `test_the_shipped_declarations_say_what_the_decisions_decided` above): the builder default is a
    USER decision on cost, and a declaration that quietly drifts back is a finding for the user.
    OFFICE IS THE THIRD CASE AND IS ASSERTED UNCHANGED: DEC-0095's consequences name it as
    untouched because its top is opus already (DEC-0078 (1)), so `build: pin` there is a decision
    and not the drift this test is looking for.

    THE SECOND HALF IS THE KERNEL'S ANSWER, not the file: a project scaffolded against the real
    dev declaration, with a builder pinned to the worker rung, is dispatched on opus -- which is
    what `build: opus` is FOR, since a class floor lifts a pin and never lowers it.

    RED ON THE OLD `build: pin`: the declaration half fails on dev and research, and the lease
    half comes back `sonnet` -- the builder tier DEC-0095 replaced.
    """
    for kit in ("dev-team", "research-team"):
        ladder = dispatch._valid_ladder(kit, shipped_ladder(kit))
        assert ladder["classes"]["build"] == "opus", kit
        assert ladder["classes"]["planning"] == "opus", kit
        assert ladder["classes"]["architecture"] == dispatch.CLASS_TOP, kit
        assert ladder["top"] == "fable", kit
        assert [name for name, rule in ladder["classes"].items() if rule == dispatch.CLASS_TOP] \
            == ["architecture"], (
            "%s: a class other than the architecture starts on the top rung, which DEC-0095 (4) "
            "keeps for that one step and for the escalation: %s" % (kit, ladder["classes"]))
    office = dispatch._valid_ladder("office-team", shipped_ladder("office-team"))
    assert office["classes"]["build"] == dispatch.CLASS_PIN and office["top"] == "opus", (
        "office-team's floors are DEC-0078's and DEC-0095 left them alone: %s" % office["classes"])
    store.kit("dev-like", ladder=shipped_ladder("dev-team"))
    state, pr = store.project("p", "dev-like", {"backend-developer": "sonnet"})
    lease = dispatch.create_lease(state, store.order(state, pr)["id"])
    assert lease[dispatch.RUNG_KEY] == "opus", lease[dispatch.LADDER_KEY]
    assert lease[dispatch.LADDER_KEY]["pin"] == "sonnet", lease[dispatch.LADDER_KEY]


def new_goal(state, title, **fields):
    """A second (third, fourth) approved goal in the same project -- what a test needs whenever it
    wants two BUILD leases that DEC-0092 (2)'s second-builder rule must not judge."""
    goal = state.capture("PR", dict(PR_FIELDS, title=title, **fields))
    approve(state, goal["id"], "scope")
    return goal


def _class_spellings():
    """Per shipped kit, the classes written as a BARE RUNG and those written as a `default`/`floor`
    pair -- read off the RAW declarations, because `_valid_ladder` normalises the two into one."""
    scalar, banded = {}, {}
    for kit in kit_dirs():
        name = os.path.basename(kit)
        for role_class, start in shipped_ladder(name)["classes"].items():
            (banded if isinstance(start, dict) else scalar).setdefault(name, []).append(role_class)
    return scalar, banded


def test_both_class_spellings_ship_and_the_scalar_still_means_default_equals_floor(store):
    """DEC-0097 (1): a class start is a PAIR (`default` where an unasked order starts, `floor` how
    far an ask may take it down), and a BARE RUNG is the pair whose two ends coincide -- which is
    why nothing shipped before this round changes behaviour.

    TWO-ENDED, because a spelling no kit ships is a branch no kit measures: the shipped
    declarations are asked which form they use, and BOTH have to be in use -- office writes the
    scalar for every class, dev and research write the pair for their `build`. If the kits ever
    drop one of the two, this fails on that end instead of leaving a dead branch in the validator
    (scalar gone) or a spelling no shipped file walks (pair gone).

    THE SCALAR'S BEHAVIOUR is measured and not inferred from the normalisation: a synthetic kit
    whose build class is the bare rung `opus` reads back floor == default == opus and refuses an
    ask below it even when the acceptance carries a test -- a class with no band has none to give.

    RED WITHOUT the scalar branch in `_valid_ladder`: every office class is "neither `top`, `pin`
    nor one of its rungs". RED WITHOUT the pair branch: dev's `build:` mapping is refused the same
    way, and both kits stop dispatching.
    """
    scalar, banded = _class_spellings()
    assert scalar, ("no shipped kit writes a class start as a bare rung any more -- the scalar "
                    "branch of `_valid_ladder` has no reader left: %s" % banded)
    assert banded, ("no shipped kit writes a class start as a `default`/`floor` pair any more -- "
                    "DEC-0097 (1)'s band is declared nowhere and only this synthetic half of the "
                    "test still walks it: %s" % scalar)
    assert set(banded) == {"dev-team", "research-team"} and set(scalar) >= {"office-team"}, \
        (scalar, banded)
    for kit, classes in banded.items():
        assert classes == [dispatch.BUILD_CLASS], (
            "%s gives a band to a class other than the build; DEC-0097 (1) bought it for the "
            "builder default alone: %s" % (kit, classes))
    both = dispatch._valid_ladder("mixed", dict(
        LADDER, classes=dict(LADDER["classes"], build="opus",
                             design={"default": "fable", "floor": "opus"})))
    assert (both["classes"]["build"], both["class_floors"]["build"]) == ("opus", "opus")
    assert (both["classes"]["design"], both["class_floors"]["design"]) == ("fable", "opus")
    store.kit("scalar-build", ladder=dict(LADDER, classes=dict(LADDER["classes"], build="opus")))
    state, pr = store.project("p", "scalar-build", {"backend-developer": "sonnet"})
    order = store.order(state, pr, expected_outputs=["tools/test_thing.py"],
                        **{dispatch.RUNG_KEY: "sonnet"})
    lease, _item = lease_of(state, order)
    answer = lease[dispatch.LADDER_KEY]
    assert (answer["default"], answer["floor"]) == ("opus", "opus"), answer
    assert lease[dispatch.RUNG_KEY] == "opus", answer
    assert "below the floor opus" in answer["why"], answer["why"]


def test_an_ask_below_the_default_is_granted_only_for_a_test_shaped_acceptance(store):
    """DEC-0097 (2), the three cases, on the SHIPPED dev declaration and on the shipped office one.

    The occasion is measured (DEC-0097's context, TSK-0136 protocol residue 5): with `build: opus`
    as a single value the PM's `--rung sonnet` on a mechanical slice came back opus, so the cheap
    rung was unreachable for every builder in dev and research.

    (a) an ask of sonnet on an order whose `expected_outputs` name a test file -> sonnet;
    (b) the SAME ask on an order whose outputs are a document -> opus, and the `why` says the
        acceptance names no test;
    (c) an ask below the class FLOOR -> never granted, and carrying a test does not buy it: the
        QA class starts and floors on opus, so its band is empty by declaration;
    (d) a criterion whose sentence DENIES a test ("no test needed for this rename") -> opus;
    (e) an expected output that is a DOCUMENT named after tests (`docs/test-plan.md`) -> opus.
    The acceptance CRITERION is the second feed and is measured too: an order whose outputs are
    prose but whose referenced AC names a test is case (a).

    (d) AND (e) ARE THE VERIFIER'S B1 OF ROUND 1, measured on this same shipped declaration: the
    first reader searched for the WORD and granted the cheap rung to both. The reader's own two
    ends are `test_the_acceptance_reader_reads_a_test_and_not_the_word` and
    `test_the_acceptance_reader_needs_a_verdict_word_and_every_listed_one_earns_its_place`.

    OFFICE IS THE UNCHANGED THIRD KIT: its build class is the bare rung `pin`, so its builder
    leases sonnet with or without an ask and no band sentence appears in the answer at all.

    RED WITHOUT the band: (a) and the criterion row come back `opus` -- the state TSK-0136
    measured and DEC-0097 answers. RED WITHOUT the test condition: (b) comes back `sonnet` and
    the cheap rung is handed to an order with no pass/fail oracle, which is what FR-0091
    precision 2 forbids.
    """
    store.kit("dev-like", ladder=shipped_ladder("dev-team"))
    state, first = store.project("p", "dev-like", {"backend-developer": "sonnet",
                                                   "quality-engineer": "sonnet"})

    def asking_sonnet(goal, **overrides):
        """One build order under a goal of its OWN, so DEC-0092 (2)'s second-builder rule is not
        what this measures, leased with the ask the three cases share."""
        order = store.order(state, goal, **dict(overrides, **{dispatch.RUNG_KEY: "sonnet"}))
        return lease_of(state, order)[0]

    granted = asking_sonnet(first, expected_outputs=["src/x.py", "tools/test_x.py"])
    answer = granted[dispatch.LADDER_KEY]
    assert granted[dispatch.RUNG_KEY] == "sonnet", answer
    assert (answer["default"], answer["floor"]) == ("opus", "sonnet"), answer
    assert "asks sonnet below the default opus; allowed: the acceptance names a test" in answer["why"], \
        answer["why"]
    kept = asking_sonnet(new_goal(state, "described only"), expected_outputs=["docs/design.md"])
    assert kept[dispatch.RUNG_KEY] == "opus", kept[dispatch.LADDER_KEY]
    assert "refused: the acceptance names no test, only a description" in \
        kept[dispatch.LADDER_KEY]["why"], kept[dispatch.LADDER_KEY]["why"]
    # THE SECOND FEED is the goal's AC text, reached through this order's `acceptance_refs`: the
    # same ask and the same prose output, decided by the criterion alone.
    plain = new_goal(state, "criterion without a test")
    by_criterion = asking_sonnet(plain, expected_outputs=["docs/other.md"])
    assert by_criterion[dispatch.RUNG_KEY] == "opus", (
        "PR_FIELDS' AC-1 says 'order completes' and names no test, so this row is case (b): %s"
        % by_criterion[dispatch.LADDER_KEY]["why"])
    testing = new_goal(state, "criterion with a test",
                       acceptance_criteria=[{"id": "AC-1", "text": "the regression test goes green"}])
    from_criterion = asking_sonnet(testing, expected_outputs=["docs/third.md"])
    assert from_criterion[dispatch.RUNG_KEY] == "sonnet", from_criterion[dispatch.LADDER_KEY]
    # (d) a criterion that DENIES a test, in the sentence that carries the word -- the first
    # reader granted this one (verifier round 1, B1)
    denied = new_goal(state, "a denial",
                      acceptance_criteria=[{"id": "AC-1", "text": "no test needed for this rename"}])
    refused = asking_sonnet(denied, expected_outputs=["src/renamed.py"])
    assert refused[dispatch.RUNG_KEY] == "opus", refused[dispatch.LADDER_KEY]
    assert "refused: the acceptance names no test, only a description" in \
        refused[dispatch.LADDER_KEY]["why"], refused[dispatch.LADDER_KEY]["why"]
    # (e) a DOCUMENT named after tests -- the second case the first reader granted
    named_after = asking_sonnet(new_goal(state, "a plan about tests"),
                                expected_outputs=["docs/test-plan.md"])
    assert named_after[dispatch.RUNG_KEY] == "opus", named_after[dispatch.LADDER_KEY]
    assert "refused: the acceptance names no test, only a description" in \
        named_after[dispatch.LADDER_KEY]["why"], named_after[dispatch.LADDER_KEY]["why"]
    # (c) below the FLOOR, with a test-shaped acceptance: the QA class has no band to give
    below = asking_sonnet(first, role="quality-engineer", type="review",
                          expected_outputs=["tools/test_qa.py"])
    floored = below[dispatch.LADDER_KEY]
    assert below[dispatch.RUNG_KEY] == "opus", floored
    assert (floored["default"], floored["floor"]) == ("opus", "opus"), floored
    assert "asks sonnet below the floor opus; refused: a floor is not a band" in floored["why"], \
        floored["why"]
    store.kit("office-like", ladder=shipped_ladder("office-team"))
    office, proc = store.project("o", "office-like", {"bookkeeper": "worker"})
    for outputs in (["tools/test_books.py"], ["docs/books.md"]):
        goal = proc if outputs[0].startswith("tools") else new_goal(office, "second office goal")
        order = store.order(office, goal, role="bookkeeper", expected_outputs=outputs,
                            **{dispatch.RUNG_KEY: "sonnet"})
        unchanged = lease_of(office, order)[0]
        shown = unchanged[dispatch.LADDER_KEY]
        assert unchanged[dispatch.RUNG_KEY] == "sonnet", shown
        assert (shown["default"], shown["floor"]) == ("sonnet", "sonnet"), shown
        assert "below the default" not in shown["why"] and "below the floor" not in shown["why"], \
            shown["why"]


def test_the_acceptance_reader_reads_a_test_and_not_the_word():
    """`dispatch.acceptance_is_test_shaped`'s two ends, as the unit the derivation above calls.

    A TEST IS A THING THAT IS RUN AND YIELDS A VERDICT. The rows below are the two ends of that
    property: on one side an artefact or an action that really is one, on the other a word that
    merely occurs -- a document NAMED after tests, a compound, a sentence that DENIES a test. The
    second column is what verifier round 1 measured green on the first reader (B1): both
    `docs/test-plan.md` and "no test needed for this rename" bought the cheap rung.

    WHY A UNIT AND NOT ONLY THE LEASE ROWS: the derivation above can only afford five goals, and a
    vocabulary needs more rows than a derivation has occasions. The lease rows keep the two cases
    that were actually measured wrong.
    """
    grants = [
        ({"expected_outputs": ["tools/test_x.py"]}, {}),
        ({"expected_outputs": ["tests/whatever.py"]}, {}),
        ({"expected_outputs": ["pkg/x_test.go"]}, {}),
        ({"expected_outputs": ["web/x.test.ts"]}, {}),
        ({"expected_outputs": ["lib/x_spec.rb"]}, {}),
        ({"acceptance_refs": ["AC-1"]},
         {"acceptance_criteria": [{"id": "AC-1", "text": "der Test wird rot"}]}),
        ({"acceptance_refs": ["AC-1"]},
         {"acceptance_criteria": [{"id": "AC-1", "text": "pytest tools/test_x.py passes"}]}),
        ({"acceptance_refs": ["AC-1"]},
         {"acceptance_criteria": [{"id": "AC-1", "text": "it renames one symbol. "
                                                         "the regression test goes green."}]}),
    ]
    refusals = [
        ({"expected_outputs": ["docs/test-plan.md"]}, {}),
        ({"expected_outputs": ["docs/testimonials.md"]}, {}),
        ({"expected_outputs": ["docs/latest.md"]}, {}),
        ({"expected_outputs": ["src/x/unittest.py"]}, {}),
        ({"expected_outputs": ["docs/tests.md"]}, {}),
        ({"acceptance_refs": ["AC-1"]},
         {"acceptance_criteria": [{"id": "AC-1", "text": "no test needed for this rename"}]}),
        ({"acceptance_refs": ["AC-1"]},
         {"acceptance_criteria": [{"id": "AC-1", "text": "kein Test noetig, nur ein Rename"}]}),
        ({"acceptance_refs": ["AC-1"]},
         {"acceptance_criteria": [{"id": "AC-1", "text": "a test plan is written"}]}),
        ({"acceptance_refs": ["AC-2"]},
         {"acceptance_criteria": [{"id": "AC-1", "text": "the test goes red"}]}),
        # THE TWO ROWS THE DENIAL GUARD ALONE REFUSES: word AND verdict AND a negation in the same
        # sentence. Without them the guard was dead -- rig row 16 stayed green on its removal,
        # because the other denial rows carry no verdict word and fail the action half anyway.
        ({"acceptance_refs": ["AC-1"]},
         {"acceptance_criteria": [{"id": "AC-1", "text": "no test goes red after this rename"}]}),
        ({"acceptance_refs": ["AC-1"]},
         {"acceptance_criteria": [{"id": "AC-1", "text": "kein Test schlaegt fehl nach dem Rename"}]}),
        # THE COMPOUND, refused ON PURPOSE and measured rather than claimed: a German compound
        # tail cannot be told from `latest` by any rule this reader could carry, and the direction
        # it fails in is the expensive one -- the order keeps the default rung.
        ({"acceptance_refs": ["AC-1"]},
         {"acceptance_criteria": [{"id": "AC-1", "text": "der Regressionstest wird rot"}]}),
    ]
    for task, root in grants:
        assert dispatch.acceptance_is_test_shaped(task, root), (task, root)
    for task, root in refusals:
        assert not dispatch.acceptance_is_test_shaped(task, root), (task, root)


def test_the_acceptance_reader_needs_a_verdict_word_and_every_listed_one_earns_its_place():
    """`dispatch._VERDICT_WORDS` is the one ENUMERATION in the reader, and it is held at BOTH ends.

    END ONE -- the vocabulary is NEEDED: a sentence with the word `test` and no verdict at all is
    refused, so the list is what carries the action half rather than decorating it.
    END TWO -- no entry is DEAD and none is redundant: for every entry a sentence built from that
    entry is accepted, and the SAME sentence with the entry taken out of the vocabulary is refused.
    The vocabulary is read off the module, never copied here, so an entry added tomorrow is walked
    the day it ships and an entry nobody needs fails the second half.
    """
    assert not dispatch._sentence_names_a_test("the test is described here")
    original = dispatch._VERDICT_RX
    try:
        for word in dispatch._VERDICT_WORDS:
            sentence = "der Test %s" % word
            assert dispatch._sentence_names_a_test(sentence), (
                "%r is in the vocabulary and carries no sentence" % word)
            rest = [other for other in dispatch._VERDICT_WORDS if other != word]
            assert rest, dispatch._VERDICT_WORDS
            dispatch._VERDICT_RX = re.compile(
                r"(?<![a-z0-9])(?:%s)(?![a-z0-9])"
                % "|".join(other.replace(" ", r"\s+") for other in rest), re.IGNORECASE)
            assert not dispatch._sentence_names_a_test(sentence), (
                "%r earns nothing: %r still counts without it" % (word, sentence))
    finally:
        dispatch._VERDICT_RX = original
    assert dispatch._sentence_names_a_test("der Test wird rot")


def test_a_declared_pin_default_is_clamped_up_to_the_floor_and_the_answer_says_the_clamped_rung(store):
    """The `max(floor, default)` of `ladder_for_order`, measured (verifier round 1, N-a).

    `pin` and `top` resolve per ROLE, so `_valid_ladder` cannot place them on the rung order and
    refuses no inverted pair that carries one -- the derivation clamps instead. A class declaring
    `{default: pin, floor: opus}` for a role pinned sonnet therefore has NO band: both ends come
    out at opus.

    AND THE `why` ECHOES THE CLAMPED RUNG, not the file's word (N-b): a sentence saying "starts on
    pin" would name a rung this order is not starting on. The declared word stands beside it, so
    the reader can still find the line in the file.

    RED WITHOUT the clamp: `default` comes back `sonnet`, below its own floor, and an ask of sonnet
    is granted as if the class had a band.
    """
    store.kit("inverted", ladder=dict(
        LADDER, classes=dict(LADDER["classes"],
                             build={"default": dispatch.CLASS_PIN, "floor": "opus"})))
    state, pr = store.project("p", "inverted", {"backend-developer": "sonnet"})
    lease, _item = lease_of(state, store.order(state, pr, expected_outputs=["tools/test_x.py"],
                                               **{dispatch.RUNG_KEY: "sonnet"}))
    answer = lease[dispatch.LADDER_KEY]
    assert (answer["default"], answer["floor"]) == ("opus", "opus"), answer
    assert lease[dispatch.RUNG_KEY] == "opus", answer
    assert "class build starts on opus (declared pin)" in answer["why"], answer["why"]
    assert "below the floor opus" in answer["why"], answer["why"]


# A ladder with room on BOTH axes, so the ORDER of the two is visible: three effort steps of
# headroom (low -> xhigh) instead of the single step every shipped kit has (its pair is the
# ceiling, DEC-0078 (2)), and two rung steps below its `top` -- three rungs and not six ON PURPOSE,
# because the cap has to be REACHABLE inside a test: the rows past it are where an effort cycle
# keyed on the derived climb runs backwards (verifier round 1, F1). A six-rung fixture would have
# hidden exactly that.
ESCALATES_EFFORT_FIRST = dict(
    LADDER, rungs=["r1", "r2", "r3"], top="r3",
    effort={"default": "low", "large": "xhigh"},
    escalation={"failed_runs_per_rung": 3, dispatch.EFFORT_STEPS_KEY: 2},
    classes=dict(LADDER["classes"], design="r2", qa="r2", build=dispatch.CLASS_PIN))


def walk_the_failed_runs(state, task, leases):
    """(rung, effort) per lease, FAIL 0 upwards -- and the monotonicity DEC-0096 owes on the way.

    A lease whose RUNG did not climb may not come back at a lower EFFORT than the one before it: a
    retry that buys nothing is a retry, a retry that buys a WEAKER model is the defect of verifier
    round 1 (F1). A drop where the rung DID climb is the reset DEC-0096 (1) asks for and is exempt.
    """
    walked = []
    for position in range(leases):
        if position:
            drive_task_to(state, task["id"], "FAILED")
            state.transition(task["id"], "READY", approved_retry=True)
        lease = dispatch.create_lease(state, task["id"])
        rung, effort = lease[dispatch.RUNG_KEY], lease[dispatch.EFFORT_KEY]
        assert lease[dispatch.LADDER_KEY]["escalation"].startswith("FAIL %d:" % position), (
            lease[dispatch.LADDER_KEY]["escalation"])
        if walked and rung == walked[-1][0]:
            assert dispatch.EFFORT_LEVELS.index(effort) >= dispatch.EFFORT_LEVELS.index(walked[-1][1]), (
                "FAIL %d came back on the same rung %s at a WEAKER effort than FAIL %d (%s -> %s): "
                "%s" % (position, rung, position - 1, walked[-1][1], effort,
                        lease[dispatch.LADDER_KEY]["escalation"]))
        walked.append((rung, effort))
    return walked


def test_a_failed_run_raises_the_effort_before_it_raises_the_rung(store):
    """DEC-0096 (1): FAIL 1 and FAIL 2 buy an effort step on the SAME rung, FAIL 3 buys the rung
    and the effort starts over at the kit's default -- derived from the declaration's two
    thresholds, never from a constant.

    ONE ROW PER FAIL COUNT, past the cap in both fixtures, on a synthetic ladder with headroom on
    both axes and on the SHIPPED dev declaration. RED ON TODAY'S ONE-RUNG-PER-FAIL
    (`failed_runs_per_rung: 1`, no effort threshold): every row's first failed run comes back one
    rung higher and at the unchanged effort -- which for an Opus builder is the top rung at the
    first verification round, the standing cost DEC-0095 had just removed.

    THE ROWS PAST THE CAP ARE THE OTHER HALF, and they are the verifier's F1 of round 1: once the
    rung sits on `top`, no further rung step is GRANTED, so the effort cycle may not reset either
    -- keyed on the derived climb it did, and the seventh run came back strictly weaker than the
    sixth (measured: dev FAIL 5 fable/xhigh, FAIL 6 fable/high). Below the cap the two spellings
    are identical, which is why the rows up to FAIL 5 read the same either way. RED WITH
    `on_this_rung = failed_runs % per_rung`: the last rows fall back to the kit's default effort.

    THE MONOTONICITY IS ASSERTED AS A PROPERTY beside the literal rows, because the rows are a
    sequence somebody will extend: a lease that did NOT climb a rung may not come back at a lower
    effort than the lease before it. A drop where the rung DID climb is the intended reset.

    WHAT THE SYNTHETIC LADDER DECIDES THAT THE SHIPPED ONES CANNOT: with two effort steps declared
    and only one step of headroom in every shipped pair, "one step per failed run up to the
    threshold" and "one step in total" give the same answer on all three kits. The cycle reading is
    the one the two threshold NAMES express (`effort_steps_before_rung` steps inside a cycle of
    `failed_runs_per_rung` runs), and the row at FAIL 2 below is the only place it is measured;
    DEC-0096 (1) narrates that case off the shipped kits, where the ceiling decides it.
    """
    store.kit("headroom", ladder=ESCALATES_EFFORT_FIRST)
    state, pr = store.project("p", "headroom", {"backend-developer": "r1"})
    task = store.order(state, pr)
    rows = [("r1", "low"), ("r1", "medium"), ("r1", "high"),          # FAIL 0-2: the effort axis
            ("r2", "low"), ("r2", "medium"), ("r2", "high"),          # FAIL 3-5: one rung, reset
            ("r3", "low"), ("r3", "medium"), ("r3", "high"),          # FAIL 6-8: the top, reset once
            ("r3", "high")]                                          # FAIL 9: past the cap, held
    measured = walk_the_failed_runs(state, task, len(rows))
    assert measured == rows, measured
    # ...and the same four counts against the SHIPPED dev declaration, whose pair (high/xhigh)
    # leaves one step of headroom: the second effort step lands on the ceiling.
    store.kit("dev-like", ladder=shipped_ladder("dev-team"))
    other, goal = store.project("d", "dev-like", {"backend-developer": "sonnet"})
    order = store.order(other, goal)
    shipped = walk_the_failed_runs(other, order, 7)
    assert shipped == [("opus", "high"), ("opus", "xhigh"), ("opus", "xhigh"),
                       ("fable", "high"), ("fable", "xhigh"), ("fable", "xhigh"),
                       ("fable", "xhigh")], shipped


# -- the three ways a project meets the declaration ----------------------------------------------

def test_a_project_without_a_scaffold_record_gets_no_rung_and_no_refusal(tmp_path):
    """A kit-less project -- this repository's own shape, and every fixture of this suite -- leases
    without a ladder: the lease says why, carries no rung, and the header carries none either.

    RED WITHOUT THE BRANCH: with `kit_installation` refusing on a missing record, this project
    (and ~100 fixtures) cannot lease at all.
    """
    (tmp_path / "project_memory").mkdir()
    state = ProjectState(str(tmp_path / "project_memory"))
    pr = state.capture("PR", dict(PR_FIELDS))
    approve(state, pr["id"], "scope")
    task = Store.order(state, pr)
    lease = dispatch.create_lease(state, task["id"])
    assert "absent" in lease[dispatch.LADDER_KEY], lease
    assert dispatch.RUNG_KEY not in lease and dispatch.EFFORT_KEY not in lease
    header = json.loads(dispatch.dispatch_header(lease)[len(dispatch.HEADER_PREFIX):])
    assert dispatch.RUNG_KEY not in header and dispatch.EFFORT_KEY not in header
    assert dispatch.LEASE_RUNG_FIELD not in state.read_item(task["id"])
    assert "no rung" in dispatch.ladder_line(lease)


def test_a_kit_without_a_ladder_declaration_is_refused_at_dispatch(store):
    """DEC-0078 (4): a kit that is known and ships no `ladder.yaml` dispatches nothing, with a
    sentence naming the file, the kit and the decision -- no default ladder in the kernel."""
    store.kit("bare-kit", ladder=None)
    state, pr = store.project("bare", "bare-kit", {"backend-developer": "sonnet"})
    task = store.order(state, pr)
    with pytest.raises(DispatchError) as refusal:
        dispatch.create_lease(state, task["id"])
    message = str(refusal.value)
    assert dispatch.LADDER_FILE in message and "bare-kit" in message and "DEC-0078" in message, message
    assert state.read_item(task["id"])["status"] == "READY", "a refused lease moved the task"
    assert dispatch.FAILED_RUNS not in state.read_item(task["id"]), "a refused lease wrote the count"


def test_a_record_that_is_present_but_unreadable_is_refused_not_ignored(store):
    """The line `kit_installation` draws: only the ABSENCE of the record means 'no kit'. A record
    that is there and broken, or names a kit the store does not hold, is refused -- the fail-closed
    direction of DEC-0079 (4), and the mutation that would make this reader read less than it
    claims is `os.path.exists` -> `presets.installation` succeeding."""
    store.kit("some-kit")
    state, pr = store.project("broken", "some-kit", {"backend-developer": "sonnet"})
    write(str(store.tmp_path / "broken" / ".claude" / "team_kit_roles.txt"), "not the record\n")
    task = store.order(state, pr)
    with pytest.raises(DispatchError) as refusal:
        dispatch.create_lease(state, task["id"])
    assert "present but cannot be read" in str(refusal.value), refusal.value

    state, pr = store.project("unstaged", "no-such-kit", {"backend-developer": "sonnet"})
    task = store.order(state, pr)
    with pytest.raises(DispatchError) as refusal:
        dispatch.create_lease(state, task["id"])
    assert "not in the kit store" in str(refusal.value) and "no-such-kit" in str(refusal.value)


@pytest.mark.parametrize("mutation, fragment", [
    (lambda d: d.pop("rungs"), "`rungs:`"),
    (lambda d: d.update(rungs=["sonnet", "sonnet"]), "`rungs:`"),
    (lambda d: d.update(top="haiku"), "`top:`"),
    (lambda d: d["effort"].pop("large"), "`effort:`"),
    (lambda d: d["escalation"].update(failed_runs_per_rung=0), "failed_runs_per_rung"),
    (lambda d: d["escalation"].update(failed_runs_per_rung=True), "failed_runs_per_rung"),
    (lambda d: d["escalation"].pop(dispatch.EFFORT_STEPS_KEY), dispatch.EFFORT_STEPS_KEY),
    (lambda d: d["escalation"].update(**{dispatch.EFFORT_STEPS_KEY: -1}), dispatch.EFFORT_STEPS_KEY),
    (lambda d: d["classes"].update(qa="haiku"), "class 'qa'"),
    # DEC-0097 (1): the pair carries exactly two ends, both from the same vocabulary, and the
    # default is never below the floor where both ends can be placed on the rung order
    (lambda d: d["classes"].update(build={"default": "opus"}), "the key(s) default"),
    (lambda d: d["classes"].update(build={"default": "opus", "floor": "pin", "ceiling": "fable"}),
     "the key(s) ceiling, default, floor"),
    (lambda d: d["classes"].update(build={"default": "opus", "floor": "haiku"}), "the floor 'haiku'"),
    (lambda d: d["classes"].update(build={"default": "sonnet", "floor": "opus"}),
     "the default 'sonnet' BELOW its floor 'opus'"),
    (lambda d: d["roles"].update(**{"backend-developer": "nowhere"}), "role 'backend-developer'"),
    (lambda d: d.update(exceptions={"nobody": {"top": "opus"}}), "excepts role 'nobody'"),
    (lambda d: d.update(exceptions={"backend-developer": {"colour": "blue"}}), "keys other than"),
    (lambda d: d.update(exceptions={"backend-developer": {"rung": "haiku"}}), "`rung`"),
])
def test_a_malformed_declaration_names_the_field_it_refuses(store, mutation, fragment):
    """One mutation per rule of `_valid_ladder`, each refused at the lease with the field named.

    The mutations are the direction the reader's docstring denies: a declaration that parses and
    would still be guessed at. With any single rule removed, its row here leases instead.
    """
    ladder = json.loads(json.dumps(LADDER))
    mutation(ladder)
    store.kit("odd-kit", ladder=ladder)
    state, pr = store.project("odd", "odd-kit", {"backend-developer": "sonnet"})
    task = store.order(state, pr)
    with pytest.raises(DispatchError) as refusal:
        dispatch.create_lease(state, task["id"])
    assert fragment in str(refusal.value) and "DEC-0078" in str(refusal.value), refusal.value


def test_a_role_without_a_class_and_a_role_without_a_readable_pin_are_refused(store):
    """Two more readers, both fail-closed: the role must be classed, and its installed definition
    must carry a `model:` -- the rung hangs on both (DEC-0034 rules 1/4/5, DEC-0077 (1))."""
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    stranger = store.order(state, pr, role="devops-engineer")
    with pytest.raises(DispatchError) as refusal:
        dispatch.create_lease(state, stranger["id"])
    assert "no class" in str(refusal.value) and "devops-engineer" in str(refusal.value)

    os.remove(str(store.tmp_path / "p" / ".claude" / "agents" / "backend-developer.md"))
    unpinned = store.order(state, pr)
    with pytest.raises(DispatchError) as refusal:
        dispatch.create_lease(state, unpinned["id"])
    assert "could not be read or pins no" in str(refusal.value), refusal.value


def test_a_pin_that_is_an_alias_resolves_through_the_stores_tiers_table(store):
    """A kit's own source tree still says `worker`; the store's `model_tiers.yaml` resolves it.

    RED WITHOUT `_store_aliases`: the pin is refused as 'neither a rung nor an alias'. And the
    other direction: a pin no alias resolves IS refused, with the rungs named.
    """
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "worker", "product-designer": "haiku"})
    lease, _task = lease_of(state, store.order(state, pr))
    assert lease[dispatch.RUNG_KEY] == "sonnet" and lease[dispatch.LADDER_KEY]["base"] == "sonnet"
    with pytest.raises(DispatchError) as refusal:
        dispatch.create_lease(state, store.order(state, pr, role="product-designer")["id"])
    assert "neither a rung" in str(refusal.value) and "sonnet, opus, fable" in str(refusal.value)


# -- DEC-0034 rules 1-5 and the effort axis --------------------------------------------------------

def test_planning_and_architecture_start_on_the_top_rung_and_the_build_on_its_pin(store):
    """Rule 1. An architecture-class role pinned to the worker rung is dispatched on the top rung;
    a build-class role with the same pin is dispatched on that pin."""
    store.kit("kit")
    state, pr = store.project("p", "kit", {"software-architect": "sonnet", "backend-developer": "sonnet"})
    architect, _ = lease_of(state, store.order(state, pr, role="software-architect", type="architecture"))
    builder, _ = lease_of(state, store.order(state, pr))
    assert architect[dispatch.RUNG_KEY] == "fable", architect[dispatch.LADDER_KEY]
    assert builder[dispatch.RUNG_KEY] == "sonnet", builder[dispatch.LADDER_KEY]


def test_a_build_order_reaches_the_ladder_only_after_the_phase_its_class_assumes(store):
    """Rule 1's SECOND half, which no declaration states and every declaration relies on: `build:
    pin` says nothing about scope approval or a frozen architecture because an order that owes
    either never reaches the derivation. `create_lease` asserts both BEFORE it derives, so the
    same order is refused with the architect step's sentence while the step is owed -- and the
    refusal costs nothing, the failed-run count is not written -- and leases on its pin once the
    step is accepted. The three `ladder.yaml` comments name this test for that claim.

    RED IF THE DERIVATION MOVES ABOVE THE TWO ASSERTIONS: the first lease then answers `sonnet` for
    an order in a phase the kit's declaration does not describe, and counts a run for it.
    """
    store.kit("kit", with_architect_step=True)
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    early = dispatch.create_task(state, dict(
        TSK_FIELDS, product_requirement=pr["id"], derives_from=pr["id"], allowed_scope=["src/early/"]))
    state.transition(early["id"], "READY")
    assert dispatch.architect_step_owed(state, state.read_item(early["id"]), pr), (
        "the fixture kit does not owe the step, so the refusal below would prove nothing")
    with pytest.raises(DispatchError) as refusal:
        dispatch.create_lease(state, early["id"])
    assert dispatch.LADDER_FILE not in str(refusal.value), refusal.value
    assert dispatch.FAILED_RUNS not in state.read_item(early["id"])
    satisfy_the_architect_step(state, state.read_item(early["id"]), pr)
    lease = dispatch.create_lease(state, early["id"])
    assert lease[dispatch.RUNG_KEY] == "sonnet", lease[dispatch.LADDER_KEY]


def test_an_order_that_failed_climbs_one_rung_per_failed_run_capped_at_the_top(store):
    """Rule 2. The same order, dispatched after each FAILED run, climbs sonnet -> opus -> fable and
    stays on fable; the count and the climb are on the lease and the task.

    RED WITHOUT `count_failed_run_locked` (the count stays 0 and the rung stays sonnet) and RED
    with the cap removed (the third retry indexes past the rungs).
    """
    store.kit("kit")
    ladder_rungs = LADDER["rungs"]
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    task = store.order(state, pr)
    lease, item = lease_of(state, task)
    assert (lease[dispatch.RUNG_KEY], item[dispatch.FAILED_RUNS]) == ("sonnet", 0)
    for expected, count in (("opus", 1), ("fable", 2), ("fable", 3)):
        drive_task_to(state, task["id"], "FAILED")
        state.transition(task["id"], "READY", approved_retry=True)
        lease, item = lease_of(state, task)
        assert lease[dispatch.RUNG_KEY] == expected, lease[dispatch.LADDER_KEY]
        assert item[dispatch.FAILED_RUNS] == count and item[dispatch.LEASE_RUNG_FIELD] == expected
        assert lease[dispatch.LADDER_KEY]["failed_runs"] == count
        # ...and the sentence the lease and the checkpoint show counts the steps GRANTED, never the
        # steps the thresholds derived: at the cap the third failed run buys nothing, and a line
        # that said "rung +3" there would name a model the order is not running on (DEC-0096 (4)).
        # RED with the derived count in `escalation_line`: the last row reads `rung +3`.
        granted = ladder_rungs.index(expected) - ladder_rungs.index("sonnet")
        assert "FAIL %d: rung +%d," % (count, granted) in lease[dispatch.LADDER_KEY]["escalation"], (
            lease[dispatch.LADDER_KEY]["escalation"])


def test_a_lease_that_produced_no_child_counts_no_failed_run(store):
    """The other direction of the count: a lease whose spawn never started (LEASED -> READY) is not
    a failed run, and a run counted once is not counted again by the next lease.

    RED WITH THE `pop` REPLACED BY A `get` IN `count_failed_run_locked`: the lease after the
    no-child lease finds the old stamp still there and counts the same run twice.
    """
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    task = store.order(state, pr)
    dispatch.create_lease(state, task["id"])
    dispatch.spawn_outcome(state, task["id"], ok=False)                 # LEASED -> READY, no child
    lease, item = lease_of(state, task)
    assert item[dispatch.FAILED_RUNS] == 0 and lease[dispatch.RUNG_KEY] == "sonnet"
    drive_task_to(state, task["id"], "FAILED")
    state.transition(task["id"], "READY", approved_retry=True)
    lease, item = lease_of(state, task)
    assert item[dispatch.FAILED_RUNS] == 1 and lease[dispatch.RUNG_KEY] == "opus"
    dispatch.spawn_outcome(state, task["id"], ok=False)                 # again no child
    lease, item = lease_of(state, task)
    assert item[dispatch.FAILED_RUNS] == 1, "the same started run was counted twice"
    assert lease[dispatch.RUNG_KEY] == "opus"


def test_every_way_from_a_started_run_back_to_ready_passes_failed():
    """The premise of `count_failed_run_locked`, derived from the automaton and not assumed: from
    IN_PROGRESS (the status `started` is stamped in) no walk reaches READY without FAILED.

    Would go red the day the TSK automaton gains an edge like IN_PROGRESS -> READY, which is exactly
    when the count would start lying.
    """
    edges = AUTOMATA["TSK"].allowed
    seen, frontier = set(), ["IN_PROGRESS"]
    while frontier:
        here = frontier.pop()
        for src, dst in edges:
            if src == here and dst != "FAILED" and dst not in seen:
                assert dst != "READY", "IN_PROGRESS reaches READY without FAILED via %s" % here
                seen.add(dst)
                frontier.append(dst)
    assert seen, "IN_PROGRESS has no outgoing edges at all -- the walk measured nothing"


def test_a_change_touching_the_architecture_lifts_that_order_to_the_top_and_the_next_build_falls_back(store):
    """Rule 3. An architecture-class order deriving from a CR runs on the top rung; the build order
    dispatched after it runs on its pin -- nothing stored on the goal carries the climb over."""
    store.kit("kit")
    state, pr = store.project("p", "kit", {"software-architect": "opus", "backend-developer": "sonnet"})
    cr = state.capture("CR", {"title": "change", "target_pr": pr["id"], "target_revision": pr["revision"],
                              "change_description": "touches the architecture",
                              "acceptance_criteria": [{"id": "AC-1", "text": "changed"}]})
    lifted, _ = lease_of(state, store.order(state, pr, role="software-architect", type="architecture",
                                            derives_from=cr["id"]))
    assert lifted[dispatch.RUNG_KEY] == "fable"
    builder, _ = lease_of(state, store.order(state, pr))
    assert builder[dispatch.RUNG_KEY] == "sonnet"


def test_design_and_qa_start_above_the_build_floor_and_a_floor_never_lowers_a_pin(store):
    """Rules 4 and 5, and the clause between them: a design or QA role pinned to the worker rung
    starts on opus; a role pinned ABOVE its class floor keeps its pin (the floor is a floor).

    THE SECOND CLAUSE NEEDS A PIN ABOVE A NAMED FLOOR to be able to fail: a first cut measured it
    on a fable-pinned BUILDER, whose class floor IS the pin, and the mutation `start = floor` stayed
    green (mutation rig R5, 2026-09-05 21:59). The second QA project below pins the QA role to fable
    over its opus floor; with the `max` gone it is lowered to opus and this is red.
    """
    store.kit("kit")
    state, pr = store.project("p", "kit", {"product-designer": "sonnet", "quality-engineer": "sonnet",
                                           "backend-developer": "fable"})
    designer, _ = lease_of(state, store.order(state, pr, role="product-designer", type="design"))
    qa, _ = lease_of(state, store.order(state, pr, role="quality-engineer", type="review"))
    high_builder, _ = lease_of(state, store.order(state, pr))
    assert designer[dispatch.RUNG_KEY] == "opus" and qa[dispatch.RUNG_KEY] == "opus"
    assert high_builder[dispatch.RUNG_KEY] == "fable", high_builder[dispatch.LADDER_KEY]
    above, goal = store.project("above", "kit", {"quality-engineer": "fable"})
    senior_qa, _ = lease_of(above, store.order(above, goal, role="quality-engineer", type="review"))
    assert senior_qa[dispatch.RUNG_KEY] == "fable", senior_qa[dispatch.LADDER_KEY]
    assert senior_qa[dispatch.LADDER_KEY]["start"] == "fable"


def test_the_filing_pair_starts_on_its_pin_at_low_effort_and_still_climbs(store):
    """DEC-0047's office filing floor, as the SHIPPED declaration really behaves (B1 of the round 1
    verification): `sonnet` is the pair's PIN and only `low` is the named exception, so the pair
    starts on sonnet at low effort -- and failed runs climb the RUNG to opus while the effort
    stays low, because rule 2 knows no exception and the declaration names none.

    HOW MANY FAILED RUNS IS THE DECLARATION'S, not this test's: DEC-0096 made the threshold a
    config value and the office kit now declares 3, so the count is read off the shipped file. The
    effort is the half that stands still HERE and nowhere else -- the pair's fixed `low` is floor
    and ceiling at once, so the effort steps DEC-0096 spends before the rung buy nothing for it.

    The office `ladder.yaml` and the office constitution both say this in words; until 2026-09-06
    they said the pair "keeps sonnet/low as the named exception", which the climb makes false. The
    shipped declaration is loaded here rather than a copy of it, so the sentence and the file cannot
    drift apart: a `top: sonnet` line added to the pair (the open user question) turns this red and
    the two texts with it.
    """
    with io.open(os.path.join(TEAM_KITS, "office-team", dispatch.LADDER_FILE),
                 encoding="utf-8") as handle:
        office = yaml.safe_load(handle)
    store.kit("office", ladder=office)
    state, pr = store.project("office", "office", {"records-clerk": "worker",
                                                   "filing-reviewer": "worker"})
    for role in ("records-clerk", "filing-reviewer"):
        task = store.order(state, pr, role=role, type="review")
        lease, _item = lease_of(state, task)
        assert (lease[dispatch.RUNG_KEY], lease[dispatch.EFFORT_KEY]) == ("sonnet", "low"), (
            role, lease[dispatch.LADDER_KEY])
        assert lease[dispatch.LADDER_KEY]["base"] == "sonnet"
        for _run in range(office["escalation"]["failed_runs_per_rung"]):
            drive_task_to(state, task["id"], "FAILED")
            state.transition(task["id"], "READY", approved_retry=True)
            climbed, _item = lease_of(state, task)
            assert climbed[dispatch.EFFORT_KEY] == "low", (
                "%s: the exception fixes the effort as floor AND ceiling, so no escalation step "
                "may move it: %s" % (role, climbed[dispatch.LADDER_KEY]))
        assert climbed[dispatch.RUNG_KEY] == "opus", (
            "%s: the shipped declaration gives the pair no `top`, so rule 2 climbs it -- if that "
            "changed, the two texts that describe it have to change with it: %s"
            % (role, climbed[dispatch.LADDER_KEY]))
        # ...AND AN ORDER'S ASK DOES NOT LIFT THE FLOOR EITHER (DEC-0091 (2) with DEC-0047's
        # reason): the exception is floor and ceiling. Measured lifted to `high` at TSK-0135's
        # mid-goal check (B2) before this line; the answer names the ask and the exception both.
        asked, _item = lease_of(state, store.order(state, pr, role=role, type="review",
                                                   **{dispatch.EFFORT_KEY: "high"}))
        assert asked[dispatch.EFFORT_KEY] == "low", (role, asked[dispatch.LADDER_KEY])
        assert "the order asks high, but the exception fixes low" in asked[dispatch.LADDER_KEY]["why"], (
            asked[dispatch.LADDER_KEY]["why"])


def test_a_top_below_a_pin_lowers_it_and_the_answer_says_so(store):
    """The one direction in which the ladder DOES lower a pin (finding F4 of the round-1
    verification): a class floor never lowers one, but the kit's `top` caps downwards, so a role
    pinned above its kit's top runs on the top.

    Both halves are the point: the value is lowered, AND the lease's `why` names the pin and the top
    that did it, so `python scripts/harness.py ladder <TSK>` and the `dispatch` stderr line answer
    the FR-0047 question ("which model am I really getting") without the session brief. No shipped
    kit reaches the case -- `test_the_shipped_declarations_say_what_the_decisions_decided` would be
    red if one did -- but a hand-written `model_map` does.
    """
    ladder = json.loads(json.dumps(LADDER))
    ladder["top"] = "sonnet"
    store.kit("low-top", ladder=ladder)
    state, pr = store.project("lowtop", "low-top", {"backend-developer": "opus"})
    lease, item = lease_of(state, store.order(state, pr))
    assert lease[dispatch.RUNG_KEY] == "sonnet", lease[dispatch.LADDER_KEY]
    assert item[dispatch.LEASE_RUNG_FIELD] == "sonnet"
    why = lease[dispatch.LADDER_KEY]["why"]
    assert "pin opus" in why and "top sonnet" in why, why
    assert "rung sonnet" in dispatch.ladder_line(lease) and "pin opus" in dispatch.ladder_line(lease)


def test_the_effort_follows_the_goals_class_and_an_exception_fixes_it(store):
    """DEC-0077 (1): `default` on an ordinary goal, `large` on a large one; a role whose exception
    fixes the effort keeps it on either (the office filing floor, DEC-0047)."""
    ladder = json.loads(json.dumps(LADDER))
    ladder["exceptions"] = {"backend-developer": {"effort": "low"}}
    store.kit("kit", ladder=ladder)
    roles = {"backend-developer": "sonnet", "quality-engineer": "sonnet"}
    normal, pr = store.project("normal", "kit", roles)
    large, big = store.project("large", "kit", roles, goal_class="large")
    for state, goal, expected in ((normal, pr, "high"), (large, big, "xhigh")):
        qa, _ = lease_of(state, store.order(state, goal, role="quality-engineer", type="review"))
        fixed, _ = lease_of(state, store.order(state, goal))
        assert qa[dispatch.EFFORT_KEY] == expected, qa[dispatch.LADDER_KEY]
        assert fixed[dispatch.EFFORT_KEY] == "low", fixed[dispatch.LADDER_KEY]


def test_an_exception_moves_one_roles_top_and_the_climb_stops_there(store):
    """DEC-0078 (1) in the kernel's own terms: a role whose exception names a higher top climbs past
    the kit's top; every other role's climb stops at the kit's."""
    ladder = json.loads(json.dumps(LADDER))
    ladder["top"] = "opus"
    ladder["exceptions"] = {"backend-developer": {"top": "fable"}}
    store.kit("kit", ladder=ladder)
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet", "quality-engineer": "sonnet"})
    climber, capped = store.order(state, pr), store.order(state, pr, role="quality-engineer", type="review")
    for task in (climber, capped):
        dispatch.create_lease(state, task["id"])
        for _ in range(2):
            drive_task_to(state, task["id"], "FAILED")
            state.transition(task["id"], "READY", approved_retry=True)
        lease, _ = lease_of(state, task)
        assert lease[dispatch.LADDER_KEY]["failed_runs"] == 2
        assert lease[dispatch.RUNG_KEY] == ("fable" if task is climber else "opus"), lease[dispatch.LADDER_KEY]


# -- the answer on the lease, in the header, at the spawn -----------------------------------------

def test_the_header_and_the_task_carry_the_rung_and_effort(store):
    """DEC-0077 (5): the two values reach the lead in the header it copies and the task item the
    brief reads; the derivation itself stays on the lease.

    ON THE TASK THEY LAND UNDER THE `LEASE_*` NAMES and never under `rung`/`effort`, because those
    two on a task are the PM's ASK (DEC-0091 (1)) -- written back there, the derived value would
    be the next lease's floor and an order that climbed once would climb twice
    (`test_an_order_rung_lifts_the_start_and_the_climb_begins_there` measures the climb from the
    ask). The class rides along for the distribution (DEC-0092 (4)).
    """
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    lease, item = lease_of(state, store.order(state, pr))
    header = json.loads(dispatch.dispatch_header(lease)[len(dispatch.HEADER_PREFIX):])
    assert (header[dispatch.RUNG_KEY], header[dispatch.EFFORT_KEY]) == ("sonnet", "high")
    assert (item[dispatch.LEASE_RUNG_FIELD], item[dispatch.LEASE_EFFORT_FIELD]) == ("sonnet", "high")
    assert item[dispatch.LEASE_CLASS_FIELD] == "build"
    assert dispatch.RUNG_KEY not in item and dispatch.EFFORT_KEY not in item, (
        "the lease wrote its answer under the ask's name: %s" % item)
    assert lease[dispatch.LADDER_KEY]["why"].startswith("sonnet: pin sonnet")
    assert "rung sonnet, effort high" in dispatch.ladder_line(lease)


def test_an_answer_that_moved_between_lease_and_spawn_is_refused(store):
    """`validate_dispatch` derives again: a role re-pinned (here) or a declaration restaged between
    lease and spawn is refused with both answers named, and a lease without an answer is refused
    too. RED WITHOUT `_assert_the_ladder_answer_holds_locked`: the stale header spawns."""
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    task = store.order(state, pr)
    lease = dispatch.create_lease(state, task["id"])
    header = dispatch.parse_header(dispatch.dispatch_header(lease))
    assert dispatch.validate_dispatch(state, header, "backend-developer")["lease"][dispatch.RUNG_KEY] == "sonnet"
    write(str(store.tmp_path / "p" / ".claude" / "agents" / "backend-developer.md"),
          "---\nname: backend-developer\nmodel: opus\neffort: high\ntools: Read\n---\nbody\n")
    with pytest.raises(DispatchError) as refusal:
        dispatch.validate_dispatch(state, header, "backend-developer", claim=True)
    assert "moved between lease and spawn" in str(refusal.value) and "rung opus" in str(refusal.value)
    assert state.read_item(task["id"])["status"] == "LEASED"

    stale = dict(lease)
    stale.pop(dispatch.LADDER_KEY)
    state._write_yaml_atomic(dispatch._lease_path(state, task["id"]), stale)
    with pytest.raises(DispatchError) as refusal:
        dispatch.validate_dispatch(state, header, "backend-developer", claim=True)
    assert "carries no ladder answer" in str(refusal.value)


NOT_GIVEN = object()
DEV_HOOKS = os.path.join(TEAM_KITS, "dev-team", "hooks")


def spawn_payload(state, header, role, model=NOT_GIVEN):
    """The PreToolUse payload of an Agent call carrying `header`, with or without a `model`."""
    tool_input = {"subagent_type": role, "run_in_background": False,
                  "prompt": header + "\nobjective: build\noutput: summary"}
    if model is not NOT_GIVEN:
        tool_input["model"] = model
    return {"hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": os.path.dirname(state.root),
            "session_id": "session-1", "prompt_id": "prompt-1", "tool_input": tool_input}


def shipped_spawn_gate(store, payload):
    """The kit's own `gate_dispatch.py`, as a process, against the project the payload names."""
    env = dict(os.environ, CLAUDE_PROJECT_DIR=payload["cwd"], HARNESS_KERNEL_PATH=TEAM_KITS,
               HOME=str(store.home), USERPROFILE=str(store.home))
    return subprocess.run([sys.executable, "-B", os.path.join(DEV_HOOKS, "gate_dispatch.py")],
                          input=json.dumps(payload), capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=60)


def test_a_spawn_below_the_lease_rung_is_refused_and_one_that_names_it_passes(store, tmp_path):
    """`spawn_model_refusal`, all three cases and both directions, through `validate_dispatch`:
    a climb the spawn does not name is refused, a wrong model is refused, the rung passes, a rung
    that IS the pin needs no model, a kit-less project holds nothing -- and a refusal spends no
    claim. RED WITHOUT the `spawn_model` branch: every case below passes and the child runs on
    the pin the state climbed away from."""
    store.kit("kit")
    state, pr = store.project("p", "kit", {"software-architect": "sonnet", "backend-developer": "sonnet"})
    lifted = store.order(state, pr, role="software-architect", type="architecture")
    lease = dispatch.create_lease(state, lifted["id"])
    assert lease[dispatch.RUNG_KEY] == "fable"
    header = dispatch.parse_header(dispatch.dispatch_header(lease))
    for wrong, fragment in ((None, "names no model"), ("opus", "names model 'opus'")):
        with pytest.raises(DispatchError) as refusal:
            dispatch.validate_dispatch(state, header, "software-architect", claim=True, spawn_model=wrong)
        assert fragment in str(refusal.value) and "model: fable" in str(refusal.value), refusal.value
    assert "dispatched_at" not in dispatch._read_lease(state, lifted["id"]), "a refusal spent the claim"
    dispatch.validate_dispatch(state, header, "software-architect")           # no payload: not held
    assert dispatch.validate_dispatch(state, header, "software-architect", claim=True,
                                      spawn_model="fable")["lease"][dispatch.RUNG_KEY] == "fable"

    builder = store.order(state, pr)
    header = dispatch.parse_header(dispatch.dispatch_header(dispatch.create_lease(state, builder["id"])))
    dispatch.validate_dispatch(state, header, "backend-developer", spawn_model=None)   # pin == rung
    with pytest.raises(DispatchError):
        dispatch.validate_dispatch(state, header, "backend-developer", spawn_model="opus")

    (tmp_path / "kitless" / "project_memory").mkdir(parents=True)
    bare = ProjectState(str(tmp_path / "kitless" / "project_memory"))
    goal = bare.capture("PR", dict(PR_FIELDS))
    approve(bare, goal["id"], "scope")
    header = dispatch.parse_header(dispatch.dispatch_header(
        dispatch.create_lease(bare, Store.order(bare, goal)["id"])))
    dispatch.validate_dispatch(bare, header, "backend-developer", spawn_model="opus")


def test_the_shipped_spawn_gate_holds_the_rung_as_a_process(store):
    """The kit dispatch path: the shipped `gate_dispatch.py`, PreToolUse on an Agent call, refuses
    the spawn that names no model for a climbed order (rc 2, the remedy names the rung), refuses
    the wrong one, and lets the one naming the rung through (rc 0, the lease is claimed)."""
    store.kit("kit")
    state, pr = store.project("p", "kit", {"software-architect": "sonnet"})
    order = store.order(state, pr, role="software-architect", type="architecture")
    header = dispatch.dispatch_header(dispatch.create_lease(state, order["id"]))
    silent = shipped_spawn_gate(store, spawn_payload(state, header, "software-architect"))
    assert silent.returncode == 2 and "model: fable" in silent.stderr, silent.stderr
    wrong = shipped_spawn_gate(store, spawn_payload(state, header, "software-architect", "sonnet"))
    assert wrong.returncode == 2 and "names model 'sonnet'" in wrong.stderr, wrong.stderr
    assert "dispatched_at" not in dispatch._read_lease(state, order["id"])
    right = shipped_spawn_gate(store, spawn_payload(state, header, "software-architect", "fable"))
    assert right.returncode == 0, right.stderr
    assert "dispatched_at" in dispatch._read_lease(state, order["id"]), "the passing spawn did not claim"


def test_the_entry_point_shows_the_answer_and_the_dispatch_line_carries_it(store):
    """The command surface: `ladder <TSK>` prints the derivation without minting, `dispatch` prints
    the rung in its header and the why on stderr -- as processes, the way a lead runs them."""
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    task = store.order(state, pr)
    env = dict(os.environ, HOME=str(store.home), USERPROFILE=str(store.home), PYTHONPATH=TEAM_KITS)

    def kernel(*args):
        return subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root", state.root] + list(args),
                              capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)

    shown = kernel("ladder", task["id"])
    assert shown.returncode == 0, shown.stdout + shown.stderr
    answer = json.loads(shown.stdout)
    assert (answer[dispatch.RUNG_KEY], answer[dispatch.EFFORT_KEY]) == ("sonnet", "high")
    assert state.read_item(task["id"])["status"] == "READY", "`ladder` minted a lease"
    leased = kernel("dispatch", task["id"])
    assert leased.returncode == 0, leased.stdout + leased.stderr
    header = json.loads(leased.stdout.strip()[len(dispatch.HEADER_PREFIX):])
    assert header[dispatch.RUNG_KEY] == "sonnet"
    assert "ladder: rung sonnet, effort high" in leased.stderr, leased.stderr


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
