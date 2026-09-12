#!/usr/bin/env python3
"""The review procedure and the reading a work order gets — held in the texts that carry them.

FOUR SUBJECTS, and every one of them is asked of the text a ROLE really receives, parsed into the
unit that text is written in (a `##` section, a numbered step, a bullet) and never as a string
search over a whole file. Two checks of generation 3 were satisfied by a window that also matched
their own prose; a section reader cannot be, because the block it returns is a block somebody wrote
as a block.

  * THE RETROSPECTIVE IS A STEP, NOT A MOOD (PR-0006 AC-1, FR-0084). The auditing role of every kit
    gets one step of its `## Do` list that poses a numbered list of QUESTIONS, and that step is ONE
    text across the kits. Which role that is comes from the shipped hook that schedules it
    (`hooks/_routine.AUDIT_ROLE`), so a kit that renames the role moves this subject with it.

  * A DUTY THAT STANDS ONLY IN A SKILL MAY NEVER ARRIVE. The kits' own role definitions record the
    measurement: a role's `skills:` frontmatter delivers nothing to a session bound to it, and the
    SUBAGENT-spawn path is unmeasured (`tools/provider_observations.json`). So the occasion rule is
    held in the role DEFINITION too — the file a spawn does load — and held there as one text.

  * THE ORDER GETS A READING BEFORE IT IS SENT (AC-2, AC-3). Every kit's LEAD skill carries one
    section that lays out the ways a work-order line goes wrong as NUMBERED forms, each with the
    decision that recorded its case; the same section carries the smaller-plan reading, and the work
    loop points at it, because a step outside the sequence is a step nobody runs. Which skill is the
    lead's comes from `lead_package.on_demand_files`, off each kit's own `settings.json`.

  * A POINTER IN THIS REPO'S OWN ROLE TEXTS RESOLVES (AC-4). `.claude/agents/` is read by no other
    suite: `test_repo_hygiene._texts_that_answer_for_a_claim` walks `team-kits/` and `docs/`, and
    `.claude/hooks/test_gates.py` judges the UNQUALIFIED half of the same claim inside its own
    directory. So the three harness role texts had no reader at all, and the rules DEC-0070 puts
    into them are pointers by construction.

WHAT THIS MODULE DOES NOT ESTABLISH, said here rather than discovered later. It reads instruction
PROSE, so it can tell a missing step from a present one and cannot tell whether anybody performed
it — no gate reads free text, which is why the blocks below have to state their own limit and why
that statement is what the honesty checks measure. The honesty READER is the one
`test_role_contracts` already owns; its VOCABULARY is widened here by the names of the hook files a
kit ships (`_mechanism_words`), because a word boundary does not fall inside `gate_dispatch` and
that is the spelling these blocks use. It stays finite all the same: an overclaim phrased without
naming any mechanism at all is not caught here either, and that limit is the one the protocol
names.
"""
import ast
import glob
import io
import json
import os
import re
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM_KITS = os.path.join(ROOT, "team-kits")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TEAM_KITS)

import lead_package                                                        # noqa: E402
from test_repo_hygiene import _defined_in, _test_citations                 # noqa: E402
from test_role_contracts import (_enforcement_claims, _enforcement_words,  # noqa: E402
                                 _kit_dirs, _markdown_sections, _reading_view)

# The decision whose rules and whose worked example these texts carry. It is an ANCHOR in the sense
# `test_role_contracts._rule_anchors` uses: the block is identified by the pointer it exists to
# carry, so a dead id makes this reader go looking for a block that is no longer there instead of
# quietly matching a heading whose wording drifted. That it resolves is asserted where it is read.
VERDICT_DECISION = "DEC-0070"


def _rule_pointer_rx(decision):
    """A pointer that names WHICH rule of `decision` the statement beside it carries.

    NOT DECORATION, and the correction that put it here was measured on the shipped text before a
    verifier could ask: a role text cites ONE decision from several statements -- the rules it was
    given, plus the worked example the same decision also is -- so a reader that counts every
    MENTION answers "are the rules still there" with a number that deleting one rule does not move.
    Counting the pointers that name a rule is what makes that deletion visible; the floor test below
    drives the reader over both shapes. A line break is allowed inside the pointer because these
    texts wrap.
    """
    return re.compile(r"`%s`,?\s*\n?\s*rule\s+(?P<number>\d+)" % re.escape(decision))


# WHICH rules of that decision this role text was given, by their number in it. AC-4 names them,
# and an enumeration is what a numbered rule is -- so it carries a tripwire at BOTH ends: a number
# here that no bullet carries is a rule nobody reads any more, and a bullet carrying a number that
# is not here is a rule nobody decided to put in this file. Verifier round 1 (B3) measured why a
# floor is not enough: deleting rule 2 and duplicating rule 1 keeps the count at three.
ORCHESTRATOR_RULES = (1, 2, 5)


# A step of a `## Do` list, and a bullet of a role definition — the units these texts are written
# in. Both are anchored at the start of a line, so a mention inside a sentence is not a step.
_STEP_SPLIT_RX = re.compile(r"(?m)^(?=\d+\. )")
_FORM_SPLIT_RX = re.compile(r"(?m)^(?=\d+\. \*\*)")
_BULLET_SPLIT_RX = re.compile(r"(?m)^(?=- )")
# A line that poses a question inside a numbered sub-list: indented, numbered, ending in `?`.
_QUESTION_RX = re.compile(r"(?m)^[ \t]+\d+\..*\?[ \t]*$")
# An occasion marker `(a)` … `(d)` — the shape the occasions are listed in.
_OCCASION_RX = re.compile(r"\([a-z]\) ")


# ============================================================ the store, and the pointers into it
def _item_ids(pattern):
    return {os.path.basename(path)[:-len(".yaml")] for path in glob.glob(pattern)}


def _items_in_the_store():
    """Every item id this repo holds, off the KERNEL's own layout rather than a path typed here.

    `ProjectState.active_dir` and `archive_root` are the builders every kernel write uses, so a
    store that reorganises moves this reader with it. The archive is globbed by SHAPE rather than
    per type, because the archive directory of a type is not spelled the same way for every type
    (`archive/dec/<year>/` beside `archive/FR/<year>/`) and this reader has no business knowing
    which is which.
    """
    from kernel import backlog_types
    from kernel.state import ProjectState
    store = ProjectState(os.path.join(ROOT, "project_memory"))
    found = set()
    for prefix in backlog_types.ACTIVE_DIRS:
        found |= _item_ids(os.path.join(store.active_dir(prefix), "%s-*.yaml" % prefix))
    found |= _item_ids(os.path.join(store.archive_root(), "*", "*", "*-*.yaml"))
    return found


def _handback_field():
    """The envelope field a run's own words come back in — off the schema the kernel validates with.

    THE ANCHOR FOR A REQUIREMENT THAT IS OTHERWISE ONLY FORM (verifier round 1, R2): the three lines
    for the user are the one half of the retrospective a form check cannot see — deleting them in
    all three kits left every count intact. They have a DESTINATION, and the destination is a field
    of a running contract, so naming it is what a check can hold.
    """
    from kernel.schemas import load_schema
    fields = load_schema("result_envelope")["fields"]
    assert "summary" in fields, (
        "the result envelope no longer carries a `summary` field; the retrospective's three lines "
        "point at it by name, so the rename has to move both")
    return "summary"


def _decision_type():
    """The item type a recorded choice becomes, off the kernel's own type vocabulary."""
    from kernel import backlog_types
    assert "DEC" in backlog_types.ACTIVE_DIRS, backlog_types.ACTIVE_DIRS
    return "DEC"


def _item_id_rx():
    """The id shape, over the kernel's own type vocabulary — a definition, never a typed list."""
    from kernel import backlog_types
    return re.compile(r"\b(?:%s)-\d{4}\b"
                      % "|".join(sorted(backlog_types.ACTIVE_DIRS, key=len, reverse=True)))


def _item_citations(text):
    """Every item id `text` names, as match objects — WITHOUT the delimited-literal exemption.

    `test_repo_hygiene._dec_citations` exempts an id inside a longer delimited span, because a
    SHIPPED KIT file exhibits ids as data: template stores, migration fixtures, a quoted refusal
    message. The three files this reader is pointed at carry no such data. Every id in them is a
    pointer, including one inside a path — `project_memory/staging/TSK-0120/…` rots at exactly the
    moment the item id does, and that is the rot this check exists for. Narrowing this reader to
    bare prose would drop the pointers that are hardest to notice.
    """
    return list(_item_id_rx().finditer(text))


def _mechanism_words(kit_dir):
    """The kit's enforcement vocabulary PLUS the names of the hooks it REGISTERS.

    WHY THE NAMES ARE IN HERE, and it was measured rather than reasoned (verifier round 1, R1):
    `test_role_contracts._enforcement_words` yields `gate`, `guard`, `hook` — bare words — and a
    word boundary does not fall inside `gate_dispatch`, because an underscore is a word character.
    An overclaim written as "gate_dispatch refuses an order that skipped either reading", inserted
    into all three lead skills, therefore passed the honesty check while the bare-word form failed
    it. The blocks this module guards name their mechanics in exactly that spelling, so the
    vocabulary they are read with has to contain it.

    REGISTERED, NOT SHIPPED, and that is verifier round 2 (N2). The first cut globbed `hooks/*.py`
    and swept in every helper beside the hooks (`_root`, `_compat`, `_stdlib_guard`); a plausible
    new file `hooks/reading.py`, registered nowhere, then turned two untouched and honest blocks
    red. The direction was the safe one, but the message would have blamed the text for a stranger's
    file name. What makes a name part of the enforcement apparatus is that the kit RUNS it, and
    `settings.json` is where that stands — the same source the base vocabulary already comes from.

    EVERY `.py` WORD OF THE COMMAND LINE, not its last one, and that is verifier round 3 (N3). A
    registration is a command line, and a kit's runner takes the hooks it drives as ARGUMENTS
    (`_gate.py gate_ledger_valid.py gate_second_booking.py`), so reading only the last word dropped
    the runner and every chained hook but one — measured, "guard_agent_spawn refuses an order that
    skipped either reading" passed the honesty check in all three lead skills.

    WHAT THIS DOES NOT LOOK AT: the filesystem. A registration naming a file the kit does not ship
    contributes its name here and is neither a crash nor a signal — whether a registered hook exists
    is a different question, and `test_shortening_net` is where it is asked.
    """
    names = set(_enforcement_words(kit_dir))
    with io.open(os.path.join(kit_dir, "settings", "settings.json"), encoding="utf-8") as handle:
        settings = json.load(handle)
    for groups in settings.get("hooks", {}).values():
        for group in groups:
            for entry in group.get("hooks", []):
                for word in entry["command"].split():
                    base = os.path.basename(word.strip('"'))
                    if base.endswith(".py"):
                        names.add(base[:-len(".py")].lower())
    return names


def _harness_role_texts():
    """(relative path, text) for this repo's own role definitions — the ones no other suite reads."""
    for path in sorted(glob.glob(os.path.join(ROOT, ".claude", "agents", "harness-*.md"))):
        with io.open(path, encoding="utf-8") as handle:
            yield os.path.relpath(path, ROOT).replace(os.sep, "/"), handle.read()


def test_every_item_pointer_the_harness_role_texts_write_resolves():
    """A rule in a role text answers for itself by naming its item; the item has to be there.

    THE ROLE TEXTS OF THIS REPO HAD NO READER. `test_repo_hygiene` sweeps `team-kits/` and `docs/`;
    `.claude/hooks/test_gates.py` sweeps its own directory. `.claude/agents/` is in neither, and
    DEC-0070 asks for three rules in `harness-lead.md` that ARE pointers — a rule whose reason
    cannot be opened is a rule that reads as decided and is not.
    """
    store = _items_in_the_store()
    assert len(store) >= 200, (
        "only %d items found — the store layout moved and every pointer below is being judged "
        "against an almost empty set" % len(store))
    judged, offenders = 0, []
    for rel, text in _harness_role_texts():
        for hit in _item_citations(text):
            judged += 1
            if hit.group(0) not in store:
                offenders.append("%s:%d %s" % (rel, text[:hit.start()].count("\n") + 1,
                                               hit.group(0)))
    assert not offenders, (
        "these role texts point at an item this store does not hold, so the reason they name "
        "cannot be read:\n  " + "\n  ".join(offenders))
    assert judged >= 10, (
        "only %d item pointers judged across .claude/agents/ — the reader stopped matching, and "
        "then the assertion above is vacuously true" % judged)


def test_every_test_pointer_the_harness_role_texts_write_resolves():
    """The same rule for the other pointer currency: a named test must be a test that exists.

    The reader is `test_repo_hygiene._test_citations`, which has its own floor test there; what is
    new here is the corpus. A role text that answers for a property by naming a test, and names one
    nobody can run, puts the claim back where it started and makes it read as measured.
    """
    offenders = []
    for rel, text in _harness_role_texts():
        for offset, path, name in _test_citations(text):
            defined = _defined_in(path)
            if defined is None or name not in defined:
                offenders.append("%s:%d cites %s::%s — %s"
                                 % (rel, text[:offset].count("\n") + 1, path, name,
                                    "no such suite file" if defined is None else "no such test"))
    assert not offenders, (
        "these role texts answer for a claim with a test nobody can run:\n  "
        + "\n  ".join(offenders))


_BRACE_RX = re.compile(r"[{]([^{}]*)[}]")


def _path_pointers(text):
    """Every repo-relative PATH a text points at in a backtick span, with its offset.

    THE THIRD CURRENCY of these role texts, and the one BUG-0241 / H159 measured as unread: an item
    id resolves against the store, a node id against the suite, and a PATH against nothing at all.
    Four mutations of the three files came back rc 0 for that reason.

    WHAT COUNTS AS A PATH, as a property and not a list of directories: a span with no whitespace
    that carries a separator, is not a pytest node id, does not open with a redirection or with the
    separator itself (`>/dev/null` is a redirect, `/model` is a command of the client), and names
    MORE THAN ONE segment. The last clause is what keeps `staging/` out: a single top-level word is
    one whose parent the sentence supplies, and this reader has no sentence -- judging it would
    report an honest phrase as a dead pointer.

    A BRACE SPAN IS EXPANDED, because that is what it means: `team-kits/{dev,office}-team/` is two
    paths and both have to be there.
    """
    for hit in re.finditer(r"`([^`" + chr(92) + "s]+)`", text):
        span = hit.group(1).rstrip(".,;:)")
        if "/" not in span or "::" in span or span[0] in ">< /":
            continue
        if span.rstrip("/").count("/") < 1 or len(span.rstrip("/").split("/")) < 2:
            continue
        yield hit.start(), span


def _expanded(span):
    """The words a brace span stands for -- one pass, which is what these texts write."""
    found = _BRACE_RX.search(span)
    if not found:
        return [span]
    return [span[:found.start()] + one + span[found.end():] for one in found.group(1).split(",")]


def test_every_path_pointer_the_harness_role_texts_write_resolves():
    """BUG-0241 / H159: the third kind of pointer these role texts write -- a PATH -- was resolved
    against nothing, so a file that moved left the sentence reading as if it still stood there.

    THE READER IS DRIVEN AT BOTH ENDS on paths built here, because a sweep whose only subject is a
    tree that happens to be tidy cannot tell "nothing is wrong" from "nothing was looked at": a
    path this repo really carries has to be found, an invented one has to be reported, and the four
    shapes that are NOT paths (a node id, a redirect, a command of the client, a single top-level
    word) have to stay unread.

    WHAT STAYS OPEN, and it is the rest of BUG-0241 rather than an omission: a test name written
    WITHOUT backticks, and a property claim that names no test at all. Both are deliberate -- a
    reader without the decoration goes red at prose -- and CLAUDE.md says so for the whole repo.
    """
    def read(text):
        return [span for _offset, span in _path_pointers(text)]

    assert read("see `tools/validate.py` for it") == ["tools/validate.py"]
    assert read("the hooks in `.claude/hooks/` decide") == [".claude/hooks/"]
    assert read("`team-kits/{dev,office}-team/`") == ["team-kits/{dev,office}-team/"]
    assert read("held by `tools/test_review_procedure.py::test_a_name`") == [], "a node id"
    assert read("stdout goes to `>/dev/null`") == [], "a redirection is not a path"
    assert read("type `/model` to switch") == [], "a command of the client is not a path"
    assert read("proposals live in `staging/`") == [], (
        "a single top-level word is one whose parent the sentence supplies, and this reader has "
        "no sentence")
    assert _expanded("a/{b,c}/d") == ["a/b/d", "a/c/d"]
    judged, offenders = 0, []
    for rel, text in _harness_role_texts():
        for offset, span in _path_pointers(text):
            for word in _expanded(span):
                judged += 1
                if not glob.glob(os.path.join(ROOT, *word.split("/"))):
                    offenders.append("%s:%d points at %s, and nothing of that name is here"
                                     % (rel, text[:offset].count(chr(10)) + 1, word))
    assert not offenders, (
        "these role texts send a reader to a path this repo does not carry:" + chr(10) + "  "
        + (chr(10) + "  ").join(offenders))
    assert judged >= 10, (
        "only %d path pointers judged across .claude/agents/ -- the reader stopped matching, and "
        "then the assertion above is vacuously true" % judged)


def test_the_item_pointer_reader_can_tell_an_id_from_the_prose_around_it():
    """The floor under the sweep, so "match everything" and "match nothing" both fail here.

    Each probe is a shape that really stands in the three files: a backticked id, a bare one in
    prose, an id inside a path, and the two non-ids the reader must stay quiet on — a type name
    without a number, and a number that is not an id.
    """
    def found(text):
        return [hit.group(0) for hit in _item_citations(text)]

    assert found("(`DEC-0070`, rule 1)") == ["DEC-0070"]
    assert found("the whole trade DEC-0003 makes") == ["DEC-0003"]
    assert found("`project_memory/staging/TSK-0120/merge-protocol.md`") == ["TSK-0120"]
    assert found("the contract is `SR-0008`, the occasion `DEC-0008`") == ["SR-0008", "DEC-0008"]
    assert found("a DEC without a number is not a pointer") == []
    assert found("about five hours of a generation's critical path") == []


# ================================================== 1. the retrospective the auditing role runs
def _audit_role(kit_dir):
    """The role a kit's own scheduling hook names as the one it audits with.

    Read off `hooks/_routine.AUDIT_ROLE` — the constant the shipped hook decides on — so a kit that
    renames the role moves this subject rather than leaving this file measuring a dead name.
    """
    path = os.path.join(kit_dir, "hooks", "_routine.py")
    with io.open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "AUDIT_ROLE"
                for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("%s decides on no AUDIT_ROLE constant" % path)


def _do_steps(path):
    """The numbered steps of a skill's `## Do` section, raw — the unit that section is written in.

    Raw and not a reading view, because these steps are compared BYTE for byte across kits below
    and a whitespace-flattened slice would call two differently wrapped copies the same text.
    """
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    blocks = [block for block in _markdown_sections(text) if block.startswith("## Do")]
    assert len(blocks) == 1, (path, len(blocks))
    return [step.rstrip("\n") for step in _STEP_SPLIT_RX.split(blocks[0])[1:]]


def _question_steps(path):
    """The steps that pose a numbered list of questions — the retrospective, found by its shape.

    No heading word and no phrase: a step whose sub-list is questions is doing one thing, and that
    shape survives a rewording of the step's own lead-in.
    """
    return [step for step in _do_steps(path) if len(_QUESTION_RX.findall(step)) >= 4]


def _auditing_role_files():
    """(kit dir, role definition, skill) for every kit that ships the role its hook schedules."""
    for kit in _kit_dirs():
        role = _audit_role(kit)
        definition = os.path.join(kit, "agents", role + ".md")
        skill = os.path.join(kit, "skills", role, "SKILL.md")
        if os.path.isfile(definition) and os.path.isfile(skill):
            yield kit, definition, skill


def test_the_auditing_role_of_every_kit_runs_a_retrospective_and_it_is_one_text():
    """FR-0084: reflection is a STEP bound to occasions, in every kit, in one wording.

    MEASURED RED on the tree before this round: no `## Do` step of any kit's auditing skill posed a
    question list at all, so `_question_steps` returned nothing for all three — reflection existed
    where a procedure demanded a measurement and nowhere else, which is the measurement FR-0084 was
    filed on.

    WHAT IS HELD: exactly one such step per kit, the same text in all of them, at least four
    occasions named in it, and its own honest limit. WHAT IS NOT: whether the auditor answered the
    questions, or answered them with a measurement. Nothing can read that — the answers are free
    text in an Evidence item.
    """
    steps, judged = {}, 0
    for kit, _definition, skill in _auditing_role_files():
        name = os.path.basename(kit)
        found = _question_steps(skill)
        assert len(found) == 1, (
            "%s: %d steps of the auditing skill pose a question list, expected exactly one — the "
            "retrospective is one step, and two of them means one of the two is not it"
            % (name, len(found)))
        judged += 1
        steps[name] = found[0]
        occasions = _OCCASION_RX.findall(found[0])
        assert len(occasions) >= 4, (
            "%s: the retrospective step names %d occasions; it is bound to occasions and not to a "
            "cadence, so the occasions are the half that makes it a step at all"
            % (name, len(occasions)))
        assert "`%s`" % _handback_field() in found[0], (
            "%s: the retrospective step no longer names the field its three lines for the user go "
            "into, so the half that reaches the user is gone and every count above is unchanged"
            % name)
    assert judged >= 3, "only %d kits judged — the auditing role is shipped by more" % judged
    assert len(set(steps.values())) == 1, (
        "the kits' retrospective steps have drifted apart; this block is one text: %s"
        % sorted(steps))


def test_the_retrospective_step_states_the_limit_it_runs_under():
    """The step names four occasions and THREE of them nothing fires, so the step has to say so
    (SR-0008).

    A reader who finds four occasions and no limit assumes something watches for all of them. Since
    `BUG-0240`/`H158` (TSK-0144) exactly ONE is watched — a record that reached the end of its own
    chain since the last run makes the run due and the duty names it, which
    `tools/test_review_procedure.py::test_a_delivery_since_the_last_run_makes_the_audit_due_and_names_it`
    measures in three states per kit. The other three are not facts a file carries. So the limit
    this node reads is the one that is still true, and it is read in both directions — every mention
    of the enforcement layer stands in a clause that negates it, and at least one such mention is
    there. The watched occasion names its reader as a module path
    (`hooks/_routine.delivery_occasions`) and therefore carries no bare enforcement word at all,
    which is why an affirmative sentence about it is not an overclaim here; the reader below is
    what decides that, not this paragraph. Same reader as
    `test_role_contracts.test_the_answering_rule_claims_no_enforcement_it_does_not_have` uses, and
    the same finite vocabulary it names as its own limit.

    THE READING VIEW, not the raw block: a line break is a clause boundary to that reader, so a
    negation and the word it negates would have to share a source line by accident of wrapping.
    """
    judged = 0
    for kit, _definition, skill in _auditing_role_files():
        words = _mechanism_words(kit)
        assert words, "%s registers no hooks — the vocabulary came out empty" % kit
        for step in _question_steps(skill):
            judged += 1
            affirmed, negated = _enforcement_claims(_reading_view(step), words)
            assert not affirmed, (
                "%s: the retrospective step names the enforcement layer without a negation, and "
                "nothing fires this step:\n  %s" % (os.path.basename(kit), "\n  ".join(affirmed)))
            assert negated, (
                "%s: the retrospective step states no limit at all, so a reader assumes a trigger "
                "behind it" % os.path.basename(kit))
    assert judged >= 3, judged


def _pointing_bullets(path, pointer):
    """The bullets of a role definition that carry `pointer`, raw."""
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    return [bullet.rstrip("\n") for bullet in _BULLET_SPLIT_RX.split(text)[1:]
            if pointer in bullet]


def test_the_occasion_rule_stands_in_the_file_a_spawn_actually_loads():
    """A duty that lives only in a SKILL may never reach a subagent — the kits say so themselves.

    Every one of these role definitions carries the measurement in its own last paragraph: a role's
    `skills:` frontmatter delivers nothing to a session bound to it, and the subagent-spawn path is
    unmeasured. So the occasion half of the retrospective is held in the definition too, as one
    text across the kits, and it points at the decision it is the shape of.

    MEASURED RED before this round: no bullet of any of the three role definitions carried the
    pointer, so this test found nothing to judge in any kit.
    """
    assert VERDICT_DECISION in _items_in_the_store(), (
        "%s is not in this store any more; the bullets below point at it, so the anchor has to "
        "move with it" % VERDICT_DECISION)
    bullets, judged = {}, 0
    for kit, definition, _skill in _auditing_role_files():
        name = os.path.basename(kit)
        found = _pointing_bullets(definition, "`%s`" % VERDICT_DECISION)
        assert len(found) == 1, (
            "%s: %d bullets of the auditing role definition point at %s, expected exactly one"
            % (name, len(found), VERDICT_DECISION))
        judged += 1
        bullets[name] = found[0]
        affirmed, negated = _enforcement_claims(_reading_view(found[0]), _mechanism_words(kit))
        assert not affirmed and negated, (
            "%s: the occasion bullet claims a trigger nothing builds (affirmed=%s, negated=%s)"
            % (name, affirmed, negated))
    assert judged >= 3, judged
    assert len(set(bullets.values())) == 1, (
        "the kits' occasion bullets have drifted apart; this is one text: %s" % sorted(bullets))


# ============================== 2. the reading a work order gets before it is sent (AC-2, AC-3)
def _lead_skill(kit_dir):
    """The kit's lead SKILL, off `settings.json` through `lead_package`, or None."""
    found = lead_package.on_demand_files(kit_dir)
    return found[0] if found else None


def _numbered_forms(block):
    """The numbered, bold-opened items of `block` — the forms a work-order line can take."""
    return [item.rstrip("\n") for item in _FORM_SPLIT_RX.split(block)[1:]]


def _order_reading_sections(path):
    """The `##` sections that lay out numbered forms, each answering for itself with an item.

    FOUND BY SHAPE, not by a heading word: a section whose numbered items each point at the record
    of the case that produced them is doing this one job, and no other section of a lead skill is
    written that way. The heading may be reworded without this reader losing it, and a section that
    keeps the heading while losing the pointers is found missing — which is the direction that
    matters, because the pointers are the part that rots.
    """
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    out = []
    for block in _markdown_sections(text):
        forms = _numbered_forms(block)
        if len(forms) >= 5 and all(_item_citations(form) for form in forms):
            out.append(block.rstrip("\n"))
    return out


def test_every_kit_lead_is_given_the_ways_a_work_order_line_goes_wrong():
    """FR-0010/AC-3: the forms are a PROCEDURE in the lead's own text, each with its case.

    THE SUBJECT IS DERIVED: whichever role a kit's `settings.json` binds as its session agent writes
    that kit's work orders, and `lead_package.on_demand_files` is the procedure document that role
    opens. A kit that renames its lead moves this subject with it.

    MEASURED RED before this round: `_order_reading_sections` returned nothing for all three lead
    skills — the five forms lived in three decision items of the workshop and in no shipped text.

    WHAT IS HELD: one such section per lead skill, the same text in all three, every form pointing
    at an item this store holds, and the smaller-plan reading beside them with its three conditions.
    WHAT IS NOT: whether the lead performed either reading. No gate reads a work order's wording,
    which is why the section states that itself and why the statement is measured below.
    """
    store = _items_in_the_store()
    sections, judged = {}, 0
    for kit in _kit_dirs():
        skill = _lead_skill(kit)
        assert skill, "%s binds no session agent, so nothing owns its work orders" % kit
        name = os.path.basename(kit)
        found = _order_reading_sections(skill)
        assert len(found) == 1, (
            "%s: %d sections of the lead skill lay out the forms of a work-order line, expected "
            "exactly one" % (name, len(found)))
        judged += 1
        sections[name] = found[0]
        for form in _numbered_forms(found[0]):
            dangling = [hit.group(0) for hit in _item_citations(form)
                        if hit.group(0) not in store]
            assert not dangling, (
                "%s: a form points at an item this store does not hold (%s), so the case behind it "
                "cannot be read" % (name, ", ".join(dangling)))
        conditions = _BULLET_SPLIT_RX.split(found[0])[1:]
        assert len(conditions) >= 3, (
            "%s: the smaller-plan reading carries %d conditions. Without them a critic that never "
            "agrees, and one that judges instead of planning, are both still allowed"
            % (name, len(conditions)))
        assert "`%s`" % _decision_type() in found[0], (
            "%s: the section no longer names the item type the choice is recorded as, so the "
            "comparison is made and forgotten and the same question comes back next round" % name)
    assert judged >= 3, "only %d lead skills judged" % judged
    assert len(set(sections.values())) == 1, (
        "the kits' order-reading sections have drifted apart; this is one text: %s"
        % sorted(sections))


# What a line of this prose looks like when it has ENDED a sentence, after the markup that can
# trail one is taken off. The set is the punctuation a sentence closes with, not a list of
# spellings somebody collected: a line that stops anywhere else is a line the next line continues.
_SENTENCE_END = ".!?"
_TRAILING_MARKUP = "*`\"')_ \t"


def _ends_a_sentence(line):
    stripped = line.rstrip(_TRAILING_MARKUP)
    return bool(stripped) and stripped[-1] in _SENTENCE_END


def _statement_around(lines, index):
    """The index at which the bold-lead statement containing line `index` begins.

    A statement of this prose opens with a bold lead-in -- the same unit `test_role_contracts`
    reads the constitutions by -- so the nearest such line at or above `index` is where it starts.
    """
    while index > 0 and not lines[index].lstrip().startswith("**"):
        index -= 1
    return index


def _torn_sentence_above(block, names):
    """Does ANY bold-lead statement naming `names` cut into the sentence above it?

    THE DEFECT THIS EXISTS FOR (verifier round 1, B1): the pointer was inserted between
    `Verify outputs against REALITY` and its own parenthesis, so the sentence lost its second half
    and the parenthesis opened a paragraph. Nothing saw it -- the test beside this one asks only
    whether the heading is named ANYWHERE in the work loop, and a torn sentence names it just as
    well as an intact one. The question a reader CAN answer is the POSITION: an inserted statement
    belongs where the line above it has finished saying something.

    EVERY MENTION, NOT THE FIRST, and that is verifier round 2 (N1): with `next(...)` a clean
    pointer at the top made a second, torn one further down invisible. Measured there, rc 0.

    WHAT IT STILL CANNOT SEE, said here and in the protocol rather than left to the next round: an
    insertion that is NOT bold-led. `_statement_around` climbs to the nearest bold lead-in, which is
    the shape a statement of this prose has, so an unbolted paragraph dropped into the middle of a
    sentence climbs past its own start and is judged at somebody else's boundary.
    """
    lines = block.splitlines()
    for named, line in enumerate(lines):
        if names not in line:
            continue
        start = _statement_around(lines, named)
        if start > 0 and not _ends_a_sentence(lines[start - 1]):
            return True
    return False


def test_the_order_reading_is_a_step_of_the_work_loop_and_not_an_appendix():
    """A step outside the sequence is a step nobody runs (FR-0005), and it does not tear one.

    The work loop is where a lead reads what to do next, so the section has to be named THERE, by
    its heading, before the order goes out. Measured red before this round in the trivial
    direction: there was no section and no pointer.

    THE SECOND HALF IS THE VERIFIER'S FINDING B1: naming the heading somewhere in the work loop is
    not enough, because a pointer dropped into the middle of a sentence names it just as well. So
    the POSITION is asked too -- the line above the pointer has to have finished a sentence. What
    this cannot judge is whether the position is the RIGHT one among the boundaries; that is a
    reading, and it is named as such in the protocol.
    """
    judged = 0
    for kit in _kit_dirs():
        skill = _lead_skill(kit)
        with io.open(skill, encoding="utf-8") as handle:
            text = handle.read()
        loops = [block for block in _markdown_sections(text) if block.startswith("## Work loop")]
        assert len(loops) == 1, (skill, len(loops))
        heading = _order_reading_sections(skill)[0].splitlines()[0].lstrip("# ").rstrip()
        assert heading in _reading_view(loops[0]), (
            "%s: the work loop never names %r, so the reading has no place in the sequence"
            % (os.path.basename(kit), heading))
        assert not _torn_sentence_above(loops[0], heading), (
            "%s: the pointer at the order reading is inserted where the line above it has not "
            "finished a sentence, so it cuts that sentence in half" % os.path.basename(kit))
        judged += 1
    assert judged >= 3, judged


def test_the_position_reader_can_tell_a_sentence_boundary_from_the_middle_of_one():
    """The floor under the position check, so "always fine" and "never fine" both fail here.

    The probes are the two real positions of verifier round 1: the office kit's torn sentence
    (`Verify outputs against REALITY` continues into a parenthesis on the next line) and the dev
    kit's clean one (`... with a confirmed design.`), plus the markup a line of this prose really
    ends with.
    """
    torn = ("   files to read, and the scope it may write. Verify outputs against REALITY\n"
            "   **Before this order goes out it gets ONE reading**, the section below —\n"
            "   \"Before the order goes out\".\n")
    clean = ("   and `design_ref` for a UI task with a confirmed design.\n"
             "   **Before this order goes out it gets ONE reading**, the section below —\n"
             "   \"Before the order goes out\".\n")
    assert _torn_sentence_above(torn, "Before the order goes out")
    assert not _torn_sentence_above(clean, "Before the order goes out")
    assert _torn_sentence_above(clean + torn, "Before the order goes out"), (
        "a clean mention above a torn one must not hide it -- verifier round 2, N1")
    assert _ends_a_sentence("never trust \"done\" strings.")
    assert _ends_a_sentence("before the spawn — never the specialist.**")
    assert _ends_a_sentence("open it with `/parallel-streams`.")
    assert not _ends_a_sentence("Verify outputs against REALITY")
    assert not _ends_a_sentence("the trigger, the cadence and the read")
    assert not _ends_a_sentence("")


def test_the_order_reading_claims_no_enforcement_it_does_not_have():
    """The section is about honest orders, so it may not overclaim about itself (SR-0008).

    Nothing refuses an order that skipped either reading: the dispatch gate validates the header
    against the lease and free prompt prose is evidence of nothing. Both halves are asked, as in the
    retrospective's limit above — no affirmed mention of the enforcement layer, and at least one
    negated one, so a reader can neither assume a mechanism nor be left without the limit.
    """
    judged = 0
    for kit in _kit_dirs():
        words = _mechanism_words(kit)
        for section in _order_reading_sections(_lead_skill(kit)):
            judged += 1
            affirmed, negated = _enforcement_claims(_reading_view(section), words)
            assert not affirmed, (
                "%s: the order-reading section names the enforcement layer without a negation:\n"
                "  %s" % (os.path.basename(kit), "\n  ".join(affirmed)))
            assert negated, (
                "%s: the order-reading section states no limit, so a reader assumes something "
                "refuses an order that skipped it" % os.path.basename(kit))
    assert judged >= 3, judged


# The wish whose second half this paragraph is: EVERY plan names in one line the alternative it
# rejected. It is the ANCHOR of the paragraph in the same sense `VERDICT_DECISION` is the anchor of
# the rules — the pointer the paragraph exists to carry, so a dead id sends this reader looking for
# a block that is no longer there rather than matching a heading whose wording drifted.
PLAN_WISH = "FR-0084"


def _rejection_paragraphs(path):
    """The bold-lead paragraphs of a constitution that answer for themselves with `PLAN_WISH`."""
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    return [unit for unit in _lead_in_units(text)
            if PLAN_WISH in {hit.group(0) for hit in _item_citations(unit)}]


def test_every_constitution_asks_a_plan_for_the_way_it_rejected():
    """FR-0084, second half: the rejected-alternative line is a duty of EVERY plan, in every kit.

    WHY THE CONSTITUTION AND NOT A SKILL: the duty binds whoever BUILDS, and a kit ships many
    building roles whose procedure documents are not this stream's to write. The constitution is the
    one text every role of a kit is sent to, it is the place the wish itself names, and it is the
    text that reaches a scaffolded project as its `AGENTS.md`.

    MEASURED RED before verifier round 1 closed it: the duty stood as a single bullet in this repo's
    own implementer role text and in none of the three kits — `grep -rn "rejected" team-kits/*/
    constitution/` found nothing, and no test named it.

    ONE TEXT IN ALL THREE, held twice over: here, and by
    `tools/test_role_contracts.py::test_a_paragraph_the_constitutions_share_is_one_text`, which
    takes any bold lead-in shared by two constitutions and demands the third and byte-equality.

    WHAT THIS CANNOT DO: see whether a plan really carried the line. No gate reads a specialist's
    prose, which is why the paragraph says so itself and why that statement is measured below.
    """
    assert PLAN_WISH in _items_in_the_store(), (
        "%s is not in this store any more; the paragraph points at it" % PLAN_WISH)
    paragraphs, judged = {}, 0
    for kit in _kit_dirs():
        name = os.path.basename(kit)
        found = _rejection_paragraphs(os.path.join(kit, "constitution", "AGENTS.md"))
        assert len(found) == 1, (
            "%s: %d constitution paragraphs answer for the rejected-alternative duty with %s, "
            "expected exactly one" % (name, len(found), PLAN_WISH))
        paragraphs[name] = found[0]
        judged += 1
    assert judged >= 3, judged
    assert len(set(paragraphs.values())) == 1, (
        "the kits' rejected-alternative paragraphs have drifted apart; this is one text: %s"
        % sorted(paragraphs))


def test_the_rejected_alternative_rule_claims_no_enforcement_it_does_not_have():
    """The duty has no gate behind it, so the paragraph that states it may not suggest one.

    Same reader and same two halves as the other honesty checks in this module: no affirmed mention
    of the enforcement layer, and at least one negated mention, so a reader can neither assume a
    mechanism nor be left without the limit.
    """
    judged = 0
    for kit in _kit_dirs():
        words = _mechanism_words(kit)
        for paragraph in _rejection_paragraphs(os.path.join(kit, "constitution", "AGENTS.md")):
            judged += 1
            affirmed, negated = _enforcement_claims(_reading_view(paragraph), words)
            assert not affirmed, (
                "%s: the rejected-alternative paragraph names the enforcement layer without a "
                "negation:\n  %s" % (os.path.basename(kit), "\n  ".join(affirmed)))
            assert negated, (
                "%s: the rejected-alternative paragraph states no limit, so a reader assumes a "
                "plan check behind it" % os.path.basename(kit))
    assert judged >= 3, judged


# ================================================ 3. this repo's own orchestrator rules (AC-4)
def _lead_role_text():
    path = os.path.join(ROOT, ".claude", "agents", "harness-lead.md")
    with io.open(path, encoding="utf-8") as handle:
        return path, handle.read()


def _numbered_rules(text, decision):
    """{rule number: bullet} for every bullet of `text` that points at a numbered rule."""
    pointer = _rule_pointer_rx(decision)
    found = {}
    for bullet in _BULLET_SPLIT_RX.split(text)[1:]:
        hit = pointer.search(bullet)
        if hit:
            found[int(hit.group("number"))] = bullet
    return found


def _mechanism_terms(bullet):
    """The backticked terms of `bullet` that are NOT item ids — what the rule is ABOUT.

    A rule that says which mechanism it binds names it; one reworded into a slogan does not. That
    is the half a pointer cannot carry: the pointer says WHY the rule exists and survives any
    rewriting of the sentence around it, which is exactly how verifier round 1 replaced rule 5 with
    "Send whatever, whenever" and kept the test green.
    """
    identifier = _item_id_rx()
    return [span.group(1) for span in re.finditer(r"`([^`]+)`", bullet)
            if not identifier.fullmatch(span.group(1).strip())]


def test_the_lead_role_text_carries_the_orchestrator_rules_with_their_pointers():
    """DEC-0070 (1), (2) and (5) live in the role text, because no other surface holds them.

    WHY HERE AND NOT IN A GATE: the decision says it itself — rule 5 is enforced "by the harness-lead
    role text (an implementer edits it, gate 1 refuses the lead)". A rule in a role text is a rule
    somebody reads, and what a check can hold is that each rule is THERE, that its reason can be
    opened, and that it still names the mechanism it is about.

    MEASURED RED before this round: `harness-lead.md` carried no bullet pointing at the decision at
    all — the three rules stood in the decision item and in a round log, which is the state PR-0006
    was filed on.

    TWO CORRECTIONS ARE BUILT INTO THIS, and both were measured on the shipped text rather than
    argued. The first was mine: counting MENTIONS gave a number that deleting one rule could not
    move, because a fourth bullet names the same decision as the retrospective's worked example.
    The second is verifier round 1 (B3): counting RULE POINTERS is still a count — deleting rule 2
    and duplicating rule 1 kept three of them, and rule 5 could be replaced by a slogan as long as
    its pointer stayed. So the numbers are read as a SET and compared with the rules this file was
    given, and each rule must still name a mechanism in backticks.

    WHAT THIS STILL CANNOT DO: judge whether the sentence around the pointer says the right thing.
    A rewording that keeps both the number and a mechanism name passes, and that limit is named in
    the protocol rather than left for the next round to find.
    """
    assert VERDICT_DECISION in _items_in_the_store(), (
        "%s is not in this store any more" % VERDICT_DECISION)
    path, text = _lead_role_text()
    where = os.path.relpath(path, ROOT)
    found = _numbered_rules(text, VERDICT_DECISION)
    assert set(found) == set(ORCHESTRATOR_RULES), (
        "%s carries the rules %s of %s; it was given %s. A missing one is a rule nobody reads any "
        "more, an extra one is a rule nobody decided to put here"
        % (where, sorted(found), VERDICT_DECISION, sorted(ORCHESTRATOR_RULES)))
    bare = [number for number, bullet in found.items() if not _mechanism_terms(bullet)]
    assert not bare, (
        "%s: rule(s) %s point at %s and name no mechanism at all, so the pointer is the whole of "
        "the rule and the sentence around it can say anything"
        % (where, sorted(bare), VERDICT_DECISION))


def test_the_rule_reader_can_tell_a_rule_from_a_mention_and_a_slogan_from_a_rule():
    """The floor under the reading above, so every way of not reading it fails here.

    The probes are the shapes that really stand in `harness-lead.md` plus the two mutations
    verifier round 1 used: the bare mention beside the rules (the worked example, not a rule) and a
    rule reworded into a slogan while its pointer stays.
    """
    pointer = _rule_pointer_rx(VERDICT_DECISION)
    assert pointer.search("(`%s`, rule 1). Before a spawn" % VERDICT_DECISION)
    assert pointer.search(
        "round, not a stream** (`%s`,\n  rule 2). Each narrowing" % VERDICT_DECISION)
    assert not pointer.search("(`%s` is the worked example). Four occasions" % VERDICT_DECISION)
    assert not pointer.search("the rule 5 of a decision nobody named")
    assert not pointer.search("(`DEC-0063`, rule 2) is another decision entirely")

    numbers = _numbered_rules(
        "- **one** (`%s`, rule 1) with `check-scopes`\n"
        "- **two** (`%s`, rule 5) with `ListAgents`\n"
        "- **not a rule** (`%s` is the worked example)\n"
        % (VERDICT_DECISION, VERDICT_DECISION, VERDICT_DECISION), VERDICT_DECISION)
    assert sorted(numbers) == [1, 5], sorted(numbers)
    assert _mechanism_terms(numbers[1]) == ["check-scopes"]
    assert _mechanism_terms("- **Send whatever, whenever** (`%s`, rule 5)." % VERDICT_DECISION) == []
    assert _mechanism_terms("- **x** (`%s`, rule 5) and `SR-0008`." % VERDICT_DECISION) == [], (
        "an item id is a pointer, not the mechanism a rule binds")
    assert not pointer.search("(`DEC-0063`, rule 2) is another decision entirely")


# WHICH generation-3 lesson each worker text was given, named by the RECORD that holds its case:
# the wish for the plan's rejected alternative, the verdict for "a named test must be able to fail",
# the merge round for the rig that writes binary and stays in its own directory. An enumeration, and
# it carries a tripwire at both ends -- a record here that no statement of that file cites is a
# lesson that has gone missing, and one that no longer resolves in the store is a dead entry. It
# does NOT claim to be every pointered statement of those files; they carry others, older than this
# round.
LESSONS_BY_ROLE = {
    "harness-implementer": ("FR-0084", VERDICT_DECISION, "TSK-0120"),
    "harness-verifier": ("TSK-0120",),
}

# A statement of these texts opens with a bold lead-in, as a bullet or as a paragraph -- the same
# unit `test_role_contracts._LEAD_IN_RX` reads the constitutions by.
_UNIT_START_RX = re.compile(r"(?m)^(?:- )?\*\*")


def _lead_in_units(text):
    """Every bold-lead statement of `text`, as its own block, stopping at the next `##` heading."""
    starts = [match.start() for match in _UNIT_START_RX.finditer(text)]
    units = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(text)
        block = text[start:end]
        heading = re.search(r"(?m)^##\s", block)
        units.append((block[:heading.start()] if heading else block).rstrip("\n"))
    return units


def test_every_harness_role_text_answers_for_the_lessons_it_was_given():
    """AC-4: each generation-3 lesson is a STATEMENT of its own, answering for itself.

    The lessons themselves are prose and stay prose — "mutate it and watch it go red" is a habit,
    not a property a check can read. What a check can hold is that each lesson is still THERE as its
    own statement and still names the record its case comes from.

    MEASURED RED before this round: two of the three files named no record at all.

    THE CORRECTION OF VERIFIER ROUND 1 (B2) IS THE READING ITSELF. The first cut asked whether the
    verdict was named ANYWHERE in the file — a string search over the whole text, against this
    module's own docstring — and the implementer text named it once, in a heading. Measured there:
    all three lessons deleted with the heading kept, one of three deleted, and a lesson replaced by
    nonsense while the pointer stayed were all rc 0. Now the unit is the bold-lead statement, each
    lesson carries its own record, and no two lessons may hide behind one statement.

    WHAT THIS STILL CANNOT DO: read what the statement SAYS. A lesson reworded around its own
    pointer passes, and that limit is named in the protocol.
    """
    store = _items_in_the_store()
    judged = 0
    for rel, text in _harness_role_texts():
        expected = LESSONS_BY_ROLE.get(os.path.basename(rel)[:-len(".md")])
        if not expected:
            continue
        units = _lead_in_units(text)
        carriers = {}
        for record in expected:
            assert record in store, (
                "%s is named as a lesson's record and is not in this store" % record)
            carriers[record] = [unit for unit in units
                                if record in {hit.group(0) for hit in _item_citations(unit)}]
        missing = sorted(record for record, found in carriers.items() if not found)
        assert not missing, (
            "%s no longer carries a statement answering for %s — the lesson is gone, or it lost the "
            "record its case comes from" % (rel, ", ".join(missing)))
        shared = [one for one in units
                  if sum(1 for found in carriers.values() if one in found) > 1]
        assert not shared, (
            "%s: one statement carries several lessons' records, so deleting a lesson would not "
            "show here:\n  %s" % (rel, "\n  ".join(_reading_view(one)[:90] for one in shared)))
        judged += 1
    assert judged == len(LESSONS_BY_ROLE), (
        "%d of %d worker role texts judged — a file named here was not found"
        % (judged, len(LESSONS_BY_ROLE)))


def test_the_statement_reader_splits_a_role_text_where_its_statements_begin():
    """The floor under the reading above, so "one unit" and "no units" both fail here.

    The probes are the two shapes these files really use — a bullet and a paragraph, both opening
    with a bold lead-in — plus the heading that must not be swallowed into the statement above it.
    """
    text = ("intro prose nobody reads as a statement\n\n"
            "- **first lesson** (`FR-0084`) says a thing.\n"
            "- **second lesson** (`DEC-0070`) says another.\n\n"
            "## Next section\n\n"
            "**a paragraph lesson** (`TSK-0120`) with its own record.\n")
    units = _lead_in_units(text)
    assert len(units) == 3, units
    assert units[0].startswith("- **first lesson**") and "second lesson" not in units[0]
    assert "## Next section" not in units[1], "a statement stops at the next heading"
    assert units[2].startswith("**a paragraph lesson**")
    assert _lead_in_units("no bold lead-in anywhere here.\n") == []


# ==================================== 4. the two limits, measured on a project outside this repo
def test_a_delivery_since_the_last_run_makes_the_audit_due_and_names_it(tmp_path, monkeypatch):
    """`BUG-0240` / `H158`: the retrospective's trigger, measured — a DELIVERY since the last run
    makes the run due, and the duty names it.

    THIS TEST USED TO PIN THE SEAM and said so in its own docstring — the duty register knew
    PERIODS and no occasions, so two projects on the same day, one of them having just delivered a
    goal, gave the identical duty. That was closed across two owners in one change
    (TSK-0144): `hooks/_routine.delivery_occasions` derives the occasion, this node turned around,
    and the honest-limit sentence in every kit's auditing SKILL and `project-auditor` definition was
    corrected in the same change. What is measured here is therefore the transition the old
    docstring announced.

    FOUR STATES PER KIT, and the middle ones are the whole point:
      * no run recorded — both projects are due, on the PERIOD, and nothing about a delivery yet;
      * a run recorded AFTER the delivery — the plain project clears, and so does the delivered
        one, because the occasion is older than the run;
      * a delivery recorded AFTER that run — the delivered project is due AGAIN and the duty NAMES
        the record, while the plain project stays clear. Without the third state a register that
        never clears would pass the first two;
      * the same record ARCHIVED — it is out of `active/` now, and the duty must still name it.
        That arm is `read_anywhere`, and without this state it was load-bearing and uncovered: the
        verifier cut it out in all three kits and the node stayed green (round 1, B3), because a
        `PR` at `DELIVERED` is not terminal and never leaves the active tree.

    `test_routine_feed` keeps the period half (a run in the period clears, the boundary is the ISO
    week); this file holds the occasion half, because the occasion is what the retrospective step
    of the auditing skill claims about itself.
    """
    import datetime
    from kernel.state import ProjectState
    from conftest import walk_to_status
    from test_parallel_streams import PR_FIELDS
    from test_routine_feed import event, routine_module

    # the hook helper resolves the kernel the way a hook does; in a tmp project there is none to
    # find, and this is the same variable `run_hook_process` sets for the same reason
    monkeypatch.setenv("HARNESS_KERNEL_PATH", os.path.join(ROOT, "team-kits"))
    today = datetime.date.today()
    judged = 0
    for kit in ("dev-team", "office-team", "research-team"):
        routine = routine_module(kit)
        roots, states = {}, {}
        for name in ("plain", "delivered"):
            root = tmp_path / kit / name / "project_memory"
            os.makedirs(str(root), exist_ok=True)
            roots[name] = os.path.dirname(str(root))
            states[name] = ProjectState(str(root))
        walk_to_status(states["delivered"], states["delivered"].capture("PR", dict(PR_FIELDS)),
                       "DELIVERED")

        due = {name: routine.routine_duties(root, today)[0] for name, root in roots.items()}
        assert all(one and routine.AUDIT_ROLE in one[0]["what"] for one in due.values()), due

        def record_run(at):
            for root in roots.values():
                path = os.path.join(root, "project_memory", ".audit", "hook_events.jsonl")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with io.open(path, "w", encoding="utf-8") as handle:
                    handle.write(json.dumps(event(routine.AUDIT_ROLE, at)) + "\n")

        # a run AFTER the delivery clears both: an occasion older than the run is not an occasion
        recorded = datetime.datetime.now() + datetime.timedelta(seconds=1)
        record_run(recorded)
        cleared = {name: routine.routine_duties(root, today)[0] for name, root in roots.items()}
        assert not any(cleared.values()), (
            "%s: a run after the delivery must clear the duty in both projects: %s" % (kit, cleared))

        # ...and a delivery AFTER that run makes exactly the delivered project due again, by name.
        # WAITED OUT rather than stamped by hand: the run record carries SECONDS (that is the
        # event log's format), so "after the run" is only a fact once the wall clock has passed
        # that second — and a test that set the file's time itself would measure its own os.utime
        # instead of what a capture really leaves behind.
        while datetime.datetime.now() <= recorded:
            time.sleep(0.05)
        walk_to_status(states["delivered"], states["delivered"].capture("PR", dict(PR_FIELDS)),
                       "DELIVERED")
        again = {name: routine.routine_duties(root, today)[0] for name, root in roots.items()}
        assert not again["plain"], (
            "%s: nothing happened in the plain project, so nothing may be due there: %s"
            % (kit, again))
        assert again["delivered"], (
            "%s: a goal delivered since the last run left the register silent -- the seam H158 "
            "closed has come back" % kit)
        what = again["delivered"][0]["what"]
        assert "PR-0002" in what and "DELIVERED" in what, (
            "%s: the duty must NAME the occasion, not just fire on it: %s" % (kit, what))

        # ...and the SAME record once it has been ARCHIVED. The terminal taken here is `SUPERSEDED`
        # and not `ACCEPTED`, for a measured reason rather than a taste: `DELIVERED -> ACCEPTED` is
        # the confirming edge and the kernel refuses it without an acceptance approval ("a status the
        # supervised party can set itself is a status no gate may read as approval"), while an
        # abandonment terminal needs none. What is under test here is the ARCHIVE arm of the
        # occasion reader -- which terminal took the record out of `active/` is not part of it, and
        # `delivery_occasions` reads the end of the automaton rather than a chosen status.
        states["delivered"].transition("PR-0002", "SUPERSEDED")
        states["delivered"].archive("PR-0002")
        assert not os.path.isfile(os.path.join(roots["delivered"], "project_memory", "product",
                                               "active", "PR-0002.yaml")), "still in active/"
        archived = {name: routine.routine_duties(root, today)[0] for name, root in roots.items()}
        assert not archived["plain"], archived
        assert archived["delivered"], (
            "%s: an archived record is out of `active/`, and an occasion reader that only knows "
            "the active tree goes silent on exactly the records it exists for" % kit)
        moved = archived["delivered"][0]["what"]
        assert "PR-0002" in moved and "SUPERSEDED" in moved, (
            "%s: the archived record must still be NAMED, with the status it reached: %s"
            % (kit, moved))
        judged += 1
    assert judged >= 3, judged


def test_nothing_reads_what_a_work_order_LINE_says(tmp_path):
    """The limit the order-reading section states about itself, measured on the running dispatch.

    An order whose `expected_outputs` names a building block NO requirement of its goal names — the
    mechanical trigger of the smaller-plan reading — is captured, leased and dispatched by the
    kernel like any other. The reading is therefore the lead's and nothing else's, which is what
    the section says and what `docs/POST_V2_WISHLIST.md` carries as `H157`.

    THIS TEST IS WRITTEN TO GO RED the day a reader over an order's wording is built; then the
    section's limit sentence is the one to correct.
    """
    from kernel.state import ProjectState
    from conftest import drive_task_to, walk_to_status
    from test_parallel_streams import PR_FIELDS, TSK_FIELDS

    root = tmp_path / "pilot" / "project_memory"
    os.makedirs(str(root), exist_ok=True)
    state = ProjectState(str(root))
    goal = state.capture("PR", dict(PR_FIELDS))
    walk_to_status(state, goal, "APPROVED")
    unrequested = "src/capture_migrated_archive.py"
    assert not [criterion for criterion in goal["acceptance_criteria"]
                if unrequested in criterion["text"]], goal["acceptance_criteria"]
    order = state.capture("TSK", dict(TSK_FIELDS, product_requirement=goal["id"],
                                      derives_from=goal["id"], root_revision=goal["revision"],
                                      expected_outputs=[unrequested]))
    drive_task_to(state, order["id"], "LEASED")
    assert state.read_item(order["id"])["status"] == "LEASED", state.read_item(order["id"])


# ================================ 4. the comment-discipline duty in the kits (PR-0008 AC-7)

COMMENT_WISH = "FR-0007"
# The two records the duty points at: the rule itself and the contract that states it. Named here
# so a paragraph that keeps the wish but drops the rule is visible -- the wish is only the occasion.
COMMENT_RULE = ("DEC-0008", "SR-0008")
GENERATION_4_VERDICT = "DEC-0080"
# WHICH rules of the generation-4 verdict each harness role text was given. The same tripwire at
# both ends as `ORCHESTRATOR_RULES`: a number here that no statement carries is a rule nobody reads,
# a statement carrying a number that is not here is a rule nobody decided to put in that file.
GENERATION_4_RULES_BY_ROLE = {
    "harness-lead": (1, 2, 3, 7),
    "harness-verifier": (6,),
}

# A STATEMENT of these texts: a bullet, or a paragraph. `_numbered_rules` above reads bullets only,
# which is right for the file it was written for; the verifier's rule 6 is a paragraph, and a reader
# that saw only bullets would report it missing while it stands there.
_STATEMENT_SPLIT_RX = re.compile(r"(?m)^(?=- )|\n{2,}")


def _statements_with_a_rule(text, decision):
    """{rule number: statement} over BOTH units these texts are written in."""
    pointer = _rule_pointer_rx(decision)
    found = {}
    for statement in _STATEMENT_SPLIT_RX.split(text):
        hit = pointer.search(statement)
        if hit:
            found[int(hit.group("number"))] = statement
    return found


def _comment_duty_paragraphs(path):
    """The bold-lead paragraphs of a text that answer for themselves with the comment RULE.

    Read by the rule (`DEC-0008`), not by the wish: the wish is cited by the older sentences in the
    role SKILLS too, so a reader keyed on it would find those and call the duty present in a file
    that never carries it.
    """
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    return [unit for unit in _lead_in_units(text)
            if COMMENT_RULE[0] in {hit.group(0) for hit in _item_citations(unit)}]


def test_every_constitution_carries_the_comment_discipline_duty():
    """PR-0008 AC-7: the comment rule is a duty of every kit, in ONE text, in the constitution.

    WHY THE CONSTITUTION: it is the text that reaches a scaffolded project as its `AGENTS.md` and the
    one document every role of a kit is sent to. The SKILLS carried a sentence about comments before
    this round and still do -- but a SKILL is REGISTERED, not injected (the constitutions say so
    themselves), so a role that never opens it never met the rule.

    MEASURED before this round: the kits carried a paragraph naming the wish `FR-0007` and holding
    two of the four clauses -- a comment carries a WHY as a pointer, and no sentence claims what the
    code does not build. The two that were missing are the ones the last generations paid for: a
    PROPERTY claim becomes a test the comment NAMES, and that named test has to RESOLVE.

    ONE TEXT IN ALL THREE, held twice over: here, and by
    `tools/test_role_contracts.py::test_a_paragraph_the_constitutions_share_is_one_text`, which
    takes any bold lead-in shared by two constitutions and demands the third and byte-equality.

    WHAT THIS CANNOT DO: read whether a comment in a project really followed the rule. Half of that
    is mechanical (`kernel.report.pointer_sweep`, measured in
    `tools/test_pointer_sweep.py::test_a_dead_test_pointer_and_a_dead_item_pointer_are_both_reported`)
    and half is not, and the paragraph says which half is which -- which the honesty check below
    measures.
    """
    store = _items_in_the_store()
    for pointer in (COMMENT_WISH,) + COMMENT_RULE:
        assert pointer in store, (
            "%s is not in this store any more; the duty points at it" % pointer)
    paragraphs, judged = {}, 0
    for kit in _kit_dirs():
        name = os.path.basename(kit)
        found = _comment_duty_paragraphs(os.path.join(kit, "constitution", "AGENTS.md"))
        assert len(found) == 1, (
            "%s: %d constitution paragraphs answer for the comment duty with %s, expected exactly "
            "one -- two of them is the second version that outlives the first"
            % (name, len(found), COMMENT_RULE[0]))
        paragraph = found[0]
        for pointer in (COMMENT_WISH,) + COMMENT_RULE:
            assert pointer in paragraph, (
                "%s: the comment duty does not point at %s" % (name, pointer))
        assert "sweep-pointers" in paragraph, (
            "%s: the duty names no mechanical half, so a reader cannot run the one that exists"
            % name)
        paragraphs[name] = paragraph
        judged += 1
    assert judged >= 3, judged
    assert len(set(paragraphs.values())) == 1, (
        "the kits' comment-duty paragraphs have drifted apart; this is one text: %s"
        % sorted(paragraphs))


def test_the_comment_duty_says_which_half_is_mechanical_and_which_is_not():
    """The duty names a COMMAND, so the honesty question is sharper than for a duty with none.

    A paragraph that names a mechanism may not let it read as a gate: `sweep-pointers` is a report
    somebody runs, nothing waits on it, and a reader who took it for enforcement would stop looking
    at the half nothing reads -- whether a property claim named a test at all. So both halves are
    measured: no AFFIRMED mention of the enforcement layer, and a statement of the limit.
    """
    judged = 0
    for kit in _kit_dirs():
        words = _mechanism_words(kit)
        for paragraph in _comment_duty_paragraphs(os.path.join(kit, "constitution", "AGENTS.md")):
            judged += 1
            name = os.path.basename(kit)
            affirmed, negated = _enforcement_claims(_reading_view(paragraph), words)
            assert not affirmed, (
                "%s: the comment duty names the enforcement layer without a negation:\n  %s"
                % (name, "\n  ".join(affirmed)))
            assert negated, (
                "%s: the comment duty states no limit, so `sweep-pointers` reads as a gate" % name)
    assert judged >= 3, judged


def _implementing_roles(kit_dir):
    """The roles of a kit that WRITE CODE -- derived from the kit, not listed here.

    A role whose SKILL states the comment rule is a role that writes code in that kit: the kits put
    that sentence exactly there and nowhere else. So a kit that gains or loses a building role moves
    this reader with it, and a kit that stops stating the rule in a skill is reported by the floor
    below rather than silently judged against an empty set.
    """
    roles = []
    for skill in sorted(glob.glob(os.path.join(kit_dir, "skills", "*", "SKILL.md"))):
        with io.open(skill, encoding="utf-8") as handle:
            if COMMENT_WISH not in handle.read():
                continue
        role = os.path.basename(os.path.dirname(skill))
        definition = os.path.join(kit_dir, "agents", role + ".md")
        if os.path.isfile(definition):
            roles.append((role, definition))
    return roles


def test_every_implementing_role_definition_carries_the_comment_duty():
    """PR-0008 AC-7: the duty is in the file that ARRIVES, not only in the one that is registered.

    THE MEASURED REASON is the constitutions' own sentence: a SKILL appears under `skills` and is
    not injected -- measured in both kits in 2026-08, three sessions with no file tools, where the
    constitution and the agent file arrived verbatim and the SKILL did not. The nine roles that
    write code carried the comment rule only in their skill until this round.

    ONE SENTENCE FOR ALL OF THEM, byte-identical, because it is one rule; a per-role rewording is
    the drift this repository keeps paying for.
    """
    sentences, judged = {}, 0
    for kit in _kit_dirs():
        name = os.path.basename(kit)
        roles = _implementing_roles(kit)
        assert roles, (
            "%s: no role's skill states %s, so this reader judges an empty set and the duty could "
            "be missing from every definition without a word" % (name, COMMENT_WISH))
        for role, definition in roles:
            with io.open(definition, encoding="utf-8") as handle:
                text = handle.read()
            carried = [unit for unit in _lead_in_units(text) if "sweep-pointers" in unit]
            assert len(carried) == 1, (
                "%s/%s: %d statements of the role definition carry the comment duty, expected "
                "exactly one" % (name, role, len(carried)))
            for pointer in (COMMENT_WISH,) + COMMENT_RULE:
                assert pointer in carried[0], (
                    "%s/%s: the duty does not point at %s" % (name, role, pointer))
            sentences["%s/%s" % (name, role)] = carried[0]
            judged += 1
    assert judged >= 9, judged
    assert len(set(sentences.values())) == 1, (
        "the role definitions' comment duty has drifted apart; this is one sentence: %s"
        % sorted(sentences))


def test_the_harness_role_texts_carry_the_generation_4_rules_with_their_pointers():
    """DEC-0080 rules 1, 2, 3 and 7 in the lead's text, rule 6 in the verifier's -- as the decision says.

    WHY HERE AND NOT IN A GATE: the decision states its own enforcement -- "rules 1-3 and 7 by the
    harness-lead role text (an implementer edits it under PR-0008 or PR-0010; gate 1 refuses the
    lead), rule 6 in the harness-verifier role text". A rule in a role text is a rule somebody reads,
    and what a check can hold is that each rule is THERE, that its reason can be opened, and that it
    still names the mechanism it is about.

    MEASURED RED before this round: neither file carried a pointer at `DEC-0080` at all -- the eight
    rules stood in the decision item and in a round log, which is the state PR-0008 was cut on.

    THE READING IS THE SET, not a count, for the reason `ORCHESTRATOR_RULES` gives: deleting one
    rule and duplicating another keeps any count. And it reads BOTH units these files are written in
    -- the lead states its rules as bullets, the verifier states rule 6 as a paragraph, and a reader
    that saw only bullets would report a rule missing that stands right there.

    WHAT THIS STILL CANNOT DO: judge whether the sentence around the pointer says the right thing.
    A rewording that keeps the number and a mechanism name passes.
    """
    assert GENERATION_4_VERDICT in _items_in_the_store(), (
        "%s is not in this store any more" % GENERATION_4_VERDICT)
    for role, expected in sorted(GENERATION_4_RULES_BY_ROLE.items()):
        path = os.path.join(ROOT, ".claude", "agents", role + ".md")
        with io.open(path, encoding="utf-8") as handle:
            text = handle.read()
        where = os.path.relpath(path, ROOT)
        found = _statements_with_a_rule(text, GENERATION_4_VERDICT)
        assert set(found) == set(expected), (
            "%s carries the rules %s of %s; it was given %s. A missing one is a rule nobody reads "
            "any more, an extra one is a rule nobody decided to put here"
            % (where, sorted(found), GENERATION_4_VERDICT, sorted(expected)))
        bare = [number for number, statement in found.items() if not _mechanism_terms(statement)]
        assert not bare, (
            "%s: rule(s) %s point at %s and name no mechanism at all, so the pointer is the whole "
            "of the rule and the sentence around it can say anything"
            % (where, sorted(bare), GENERATION_4_VERDICT))


def test_the_statement_reader_sees_a_paragraph_and_a_bullet_and_nothing_else():
    """The floor under the reader above: both units, and no false positive from a bare mention."""
    text = ("- **a bullet** (`DEC-0080`, rule 1) with `check-scopes`\n"
            "- **another** (`DEC-0080`, rule 2) with `pytest`\n"
            "\n"
            "**a paragraph** (`DEC-0080`, rule 6) with `pytest`, over two\nlines.\n"
            "\n"
            "`DEC-0080` is also the worked example, and names no rule here.\n")
    found = _statements_with_a_rule(text, GENERATION_4_VERDICT)
    assert sorted(found) == [1, 2, 6], sorted(found)
    assert "a paragraph" in found[6] and "a bullet" not in found[6], found[6]
    assert _mechanism_terms(found[1]) == ["check-scopes"]
    assert _statements_with_a_rule(text, "DEC-0070") == {}

# THE RETIRED RULE IN WORDS, for the half a token reader cannot see (verifier round 2, N-B1): the
# mechanism it names is a ladder the USER gates and a climb the first failed check triggers, and a
# procedure that tells its lead what the KERNEL derives is keeping the same copy from the other side.
# Measured: with the token reader alone, the rule written back as prose left the guard green.
# WHAT MAKES A PARAGRAPH THE LADDER PARAGRAPH: it states BOTH axes -- a rung of the reference
# vocabulary AS A VALUE, and the effort axis by the field name `model_tiers.yaml` gives it. Not the
# word "ladder", which round 3 measured as too weak (two units of the dev constitution carry it,
# one only in passing, so deleting the real one stayed green). Neither axis is typed here: the
# field name and the rungs are read off that file, and the effort VALUES -- needed by the negative
# half below, not by this one -- come from `_effort_vocabulary`.
# The one key of the tier table that names a FIELD and not a model -- without dropping it, `effort`
# lands in the rung vocabulary and every ``effort: high`` reads as a rung (measured, round 3).
_EFFORT_KEY_FIELD = "effort_field"
# The frontmatter key a kit agent pins its rung in. A key name, not a vocabulary: which VALUES may
# stand there is `_rung_vocabulary`, and that every pinned one is covered is
# `test_the_rung_vocabulary_covers_every_model_a_kit_agent_pins`.
_MODEL_KEY_FIELD = "model"


def _rung_vocabulary():
    """(rungs, effort field) of `team-kits/model_tiers.yaml` -- derived, with the file's own reader.

    Two readings, both of that file: the reference platform's tier table, and the function the tier
    file's own header points at as the authority on whether a kit source may carry a value at all
    (`team-kits/gen_provider_artifacts.py`, `provider_neutral_model`). The second is what reaches
    `fable`: that rung has no `aliases:` entry on purpose, so a table reading alone stops one rung
    below the top.

    THE OCCASION (round 4, self-found): `fable` stood here as a typed tuple whose comment claimed
    the exactly-one assertion below kept it honest. Measured in the rig: emptying the tuple, taking
    the word out of the tier file, and giving it an alias entry all three left this file GREEN --
    a protection claim with nothing behind it. What is behind the derivation now is
    `test_the_rung_vocabulary_covers_every_model_a_kit_agent_pins`.
    """
    sys.path.insert(0, TEAM_KITS)
    import gen_provider_artifacts as gpa
    tiers, aliases = gpa.load_tiers()
    table = tiers.get(gpa.REFERENCE_PROVIDER) or {}
    rungs = {str(value).strip().lower() for key, value in table.items()
             if key != _EFFORT_KEY_FIELD and isinstance(value, str)
             and str(value).strip().isalpha()}
    with io.open(os.path.join(ROOT, "team-kits", "model_tiers.yaml"), encoding="utf-8") as handle:
        text = handle.read()
    rungs |= {hit.group(1).lower() for hit in re.finditer(r"`([a-z][a-z0-9]*)`", text)
              if gpa.provider_neutral_model(hit.group(1).lower(), tiers, aliases)}
    return rungs, table.get(_EFFORT_KEY_FIELD)


def _agent_frontmatter_values(field):
    """{value: where} for every kit agent definition whose FRONTMATTER carries this key.

    Parsed rather than matched line by line: a body line that shows `model: fable` as an example is
    not a pin, and it is the pins this file judges.
    """
    from test_reference_skills import _frontmatter
    found = {}
    for kit in _kit_dirs():
        for path in sorted(glob.glob(os.path.join(kit, "agents", "*.md"))):
            front, _body = _frontmatter(path)
            value = front.get(field)
            if isinstance(value, str) and value.strip():
                found.setdefault(value.strip().lower(), os.path.relpath(path, ROOT))
    return found


# A block ends where MARKDOWN ends it: the first later line that opens a sibling item or a new
# block at column 0, or the blank line that closes a paragraph. An indented continuation line
# belongs to the statement and stays.
_BLOCK_BREAK_RX = re.compile(r"^(?:[-*+]\s|#|\s*$)")


def _own_block(unit):
    """The bold statement's OWN block, not the span up to the next bold one.

    THE OCCASION (verifier round 4, N4-2): `_lead_in_units` cuts at the next BOLD lead-in, so a
    unit carries the plain list items that follow it -- ten lines in the dev constitution, where a
    later bullet mentions `effort:` in passing. Keyed on the span, the ladder paragraph kept
    qualifying after its OWN effort axis was gone, and
    `test_no_lead_skill_keeps_its_own_copy_of_the_scaling_rule` below stayed green -- so taking the
    axis out of that one paragraph is the mutation this block reader has to make red.
    """
    lines = unit.split("\n")
    for position, line in enumerate(lines[1:], start=1):
        if _BLOCK_BREAK_RX.match(line):
            return "\n".join(lines[:position])
    return unit


_SENTENCE_END_RX = re.compile(r"(?<=[.!?])\s+")
_BOLD_LEAD_IN_RX = re.compile(r"^\s*(?:[-*+]\s+)?\*\*(.+?)\*\*", re.DOTALL)


def _states_the_scaling_rule(unit, rungs, effort_field):
    """True where this bold statement carries the rung/effort RULE itself -- BOTH axes in one
    breath: together in the bold lead-in, or together in ONE sentence of the block.

    THE OCCASION (TSK-0133 verify round 1, B4): read over the whole block, the dev ladder statement
    kept qualifying after its effort RULE ("effort high by default and xhigh when the goal's class
    is large") was gone, because three incidental mentions of the word stood elsewhere in the same
    1424-character bullet -- a mention is not a rule. A rule states both axes in one breath; that
    is what a lead following the pointer is sent to read, and it is the unit asked here.

    ONE BREATH MEANS ONE SPAN, and the lead-in branch used to be wider than that sentence said: it
    wanted the effort axis in the lead-in and the rung anywhere in the block, so moving the bare
    word into the lead-in and deleting the effort RULE kept a constitution qualifying (BUG-0275,
    measured by the merge verifier of TSK-0133, round 2 N2). Both axes now stand in whichever span
    is read -- the lead-in or the sentence. Driven by
    `test_the_ladder_reader_wants_both_axes_in_the_same_breath`.
    """
    block = " ".join(line.strip() for line in _own_block(unit).split("\n"))
    rung_rx = re.compile(r"`(?:%s)\b" % "|".join(re.escape(one) for one in rungs))
    effort_rx = re.compile(r"\b%s\b" % re.escape(effort_field), re.IGNORECASE)
    lead_in = _BOLD_LEAD_IN_RX.match(block)
    spans = [lead_in.group(1)] if lead_in else []
    spans += _SENTENCE_END_RX.split(block)
    return any(rung_rx.search(span) and effort_rx.search(span) for span in spans)


def _effort_vocabulary(text):
    """The effort values `team-kits/model_tiers.yaml` writes as an ALTERNATION.

    The table writes that vocabulary beside each platform's effort field, and the two platforms
    introduce it with different words -- which is why the pipe-separated ALTERNATION is the subject
    here and not the sentence in front of it. Read rather than typed: the same words stood
    hand-written in two places in this file, one of them carrying `default`, which neither the
    table nor any kit ships.

    WHAT IT DELIBERATELY DOES NOT READ: a value the table mentions in prose alone, outside any
    alternation -- there is one such value in the file today, provider-only. Whether that gap
    matters is measured rather than assumed:
    `test_the_effort_vocabulary_the_kits_write_is_the_one_the_tier_table_states` fails the moment a
    kit agent actually carries a value no alternation states.
    """
    return {word for hit in re.finditer(r"[a-z]+(?:\|[a-z]+){2,}", text)
            for word in hit.group(0).split("|")}


_LADDER_PROSE_RX = re.compile(
    r"[^\n.]*(?:user-gated|user-confirmed only|first QA fail|first validation FAIL"
    r"|the kernel derives (?:it|the rung))[^\n.]*", re.IGNORECASE)


# ============================= 5. what the LEAD SKILLs prescribe (PR-0008 AC-7, G5-2 seam)

def _lead_skills():
    """(kit name, path, text) for the ONE procedure skill of each kit's lead.

    The lead is read off the kit rather than typed: `presets` names the role a kit binds as its
    session agent, and its procedure skill is the one named after it (constitution §1a: exactly one
    procedure skill per role, named after the role).
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import presets
    for kit in _kit_dirs():
        name = os.path.basename(kit)
        lead = presets.lead_role(kit) if hasattr(presets, "lead_role") else None
        candidates = [lead] if lead else ["project-manager", "office-manager"]
        for role in candidates:
            path = os.path.join(kit, "skills", role, "SKILL.md")
            if os.path.isfile(path):
                with io.open(path, encoding="utf-8") as handle:
                    yield name, path, handle.read()
                break
        else:
            raise AssertionError("%s: no lead procedure skill found under skills/" % name)


def test_every_lead_skill_says_who_carries_a_decision():
    """DEC-0083 (3): the field is asked at the DEC step, in the text the lead really opens.

    WHY THE SKILL AND NOT ONLY THE KERNEL: `capture DEC` refuses a decision without the field from
    this round on, and a refusal a role meets without having been told what the field is for is the
    kind of wall this repository has paid for before. The kernel enforces, the skill explains, and
    the two say the same thing.

    MEASURED RED before this round: `grep -c "work: none"` over the three lead skills was 0/0/0.
    """
    judged = 0
    for name, path, text in _lead_skills():
        judged += 1
        assert "`work: none`" in text, (
            "%s (%s) never tells its lead what `work: none` is, while `capture DEC` refuses a "
            "decision without the field" % (name, os.path.relpath(path, ROOT)))
        assert "DEC-0083" in text, (
            "%s states the duty without the decision that made it, so a reader cannot open the "
            "reason" % name)
    assert judged >= 3, judged


def test_no_lead_skill_keeps_its_own_copy_of_the_scaling_rule():
    """The lead SKILL points at the constitution's ladder paragraph and keeps NO copy of the rule.

    WHAT IS REALLY MEASURED AT b7f282e, corrected after verifier round 2 (N-B1): the two lead skills
    prescribed `sonnet-high -> sonnet-xhigh -> opus-high -> opus-xhigh/max` AND the constitutions of
    the same release prescribe the same user-gated ladder (dev `constitution/AGENTS.md` around the
    `Escalation ladder (user-gated, ...)` line, research the same). The release was CONSISTENT. The
    earlier docstring here said the constitutions said the opposite, which was false about the file
    it cited -- and the version of this text that claimed a derived rung made the SKILL contradict
    the paragraph it called "the whole rule".

    SO THE SUBJECT IS THE COPY, not one of the two wordings. Whichever ladder a kit decides on, the
    rule lives in ONE place -- the constitution -- and the procedure points at it. That is true of
    this release and of the one that replaces the paragraph (`DEC-0076`/`DEC-0077`/`DEC-0078`), and
    it is the only sentence that is true of both.

    READ AS A CLAIM AND NOT AS ONE TOKEN FORM, which is exactly what round 2 measured: the previous
    reader saw only `<rung>-<effort>` and stayed green when the retired RULE was written back in
    prose. So a copy is any of three things -- a `<rung>-<effort>` step (vocabulary off
    `team-kits/model_tiers.yaml`), the words that name the retired mechanism (`user-gated`, a ladder
    triggered by the first QA/validation fail), or a sentence that tells the lead what the KERNEL
    derives, which is the constitution's business and not the procedure's.

    AND THE POINTER IS FOLLOWED, by what the paragraph CARRIES rather than by a word in it: the
    constitution must hold exactly ONE bold paragraph that states both axes -- a rung of
    `team-kits/model_tiers.yaml` as a value, and that file's effort field. Measured (verifier round
    3, N3-B2): keyed on the word "ladder", TWO units of the dev constitution qualified and one of
    them only mentions the word in passing, so deleting the REAL paragraph left this green. Keyed on
    the two axes, exactly one statement qualifies in each constitution that owes one.

    THE SUBJECT IS THE STATEMENT'S OWN BLOCK (`_own_block`), and that correction is verifier round
    4 (N4-2): read as the span up to the next BOLD lead-in, the ladder statement carried the plain
    bullets behind it, one of which mentions the effort field in passing -- so the axis could leave
    the ladder statement itself and this stayed green. What a kit therefore owes is ONE bold
    statement carrying BOTH axes IN ITSELF, which is what the release that replaces this paragraph
    writes as well.
    """
    rungs, effort_field = _rung_vocabulary()
    assert rungs, "team-kits/model_tiers.yaml yields no rung vocabulary at all"
    assert effort_field, (
        "the reference tier table names no %r any more, so the effort axis of the paragraph below "
        "cannot be recognised" % _EFFORT_KEY_FIELD)
    with io.open(os.path.join(ROOT, "team-kits", "model_tiers.yaml"), encoding="utf-8") as handle:
        efforts = _effort_vocabulary(handle.read())
    assert efforts, (
        "team-kits/model_tiers.yaml states no effort vocabulary any more, so every `<rung>-<effort>` "
        "copy below would read as prose and this half would measure nothing")
    steps = re.compile(r"\b(%s)-(%s)\b"
                       % ("|".join(sorted(re.escape(one) for one in rungs)),
                          "|".join(sorted(re.escape(one) for one in efforts))))
    # The three shapes a COPY of the rule takes, each read for what it claims rather than for one
    # spelling. `_LADDER_PROSE_RX` is the half round 2 measured missing: the retired rule written
    # back in words, with no `<rung>-<effort>` token in sight.
    judged, spoke = 0, 0
    for name, path, text in _lead_skills():
        judged += 1
        where = os.path.relpath(path, ROOT)
        copies = sorted({hit.group(0) for hit in steps.finditer(text)})
        copies += sorted({hit.group(0).strip() for hit in _LADDER_PROSE_RX.finditer(text)})
        assert not copies, (
            "%s (%s) keeps its own copy of the scaling rule; the constitution's ladder paragraph is "
            "the one place it lives: %s" % (name, where, "; ".join(copies)))
        if "scaling" not in text.lower():
            # A lead skill that never instructs its lead about model scaling owes no pointer.
            # Measured: the office lead skill names neither a model nor a rung anywhere -- the
            # office kit's ladder is its constitution's business alone. The NEGATIVE half above
            # still binds it, so a copy cannot appear there either.
            continue
        spoke += 1
        assert "constitution's ladder paragraph" in text, (
            "%s took the rule out without telling its lead where it lives now" % name)
        # ...AND THE POINTER RESOLVES: the paragraph really stands in that kit's constitution
        # up three levels: <kit>/skills/<role>/SKILL.md -> <kit>
        constitution = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(path))),
                                    "constitution", "AGENTS.md")
        with io.open(constitution, encoding="utf-8") as handle:
            paragraphs = [unit for unit in _lead_in_units(handle.read())
                          if _states_the_scaling_rule(unit, rungs, effort_field)]
        assert len(paragraphs) == 1, (
            "%s sends its lead to the constitution's ladder paragraph, and %s holds %d that state "
            "the rule (a rung and an effort); it has to be one"
            % (name, os.path.relpath(constitution, ROOT), len(paragraphs)))
    assert judged >= 3, judged
    assert spoke >= 2, (
        "only %d lead skill(s) instruct their lead about scaling at all -- the positive half of "
        "this check then measures almost nothing" % spoke)



def test_the_ladder_reader_wants_both_axes_in_the_same_breath():
    """BUG-0275 / H191: a statement counts as the scaling RULE only when it names a rung AND the
    effort axis in ONE span -- the bold lead-in, or one sentence of the block.

    THE OCCASION IS THE MERGE VERIFIER'S PROBE (TSK-0133, round 2 N2): the lead-in branch wanted the
    effort word in the lead-in and the rung anywhere in the same 1424-character bullet, so deleting
    the effort RULE and moving the bare word into the lead-in left a constitution qualifying while
    it no longer stated an effort rule at all. The docstring beside the branch said "in one breath"
    and the branch did not build it -- which is a claim of strictness that has to become a test.

    THE VOCABULARY IS THE SHIPPED ONE, so this drives the reader a kit is really read with; the
    units are built here, because a reader whose only subject is the tree it runs over cannot tell
    "nothing is wrong" from "nothing was looked at".
    """
    rungs, effort_field = _rung_vocabulary()
    assert rungs and effort_field, (
        "team-kits/model_tiers.yaml yields no rung vocabulary or no effort field, so this drives "
        "a reader that recognises nothing")
    rung = sorted(rungs)[0]
    lead_in = ("- **Die Leiter: `%s` und %s** -- der Rest des Absatzes sagt nichts weiter."
               % (rung, effort_field))
    sentence = "- **Die Leiter** -- ein Satz nennt `%s` mit %s zusammen." % (rung, effort_field)
    apart = ("- **Die Leiter und %s** -- ein Satz ohne Achse. Ein zweiter nennt `%s` als Wert."
             % (effort_field, rung))
    assert _states_the_scaling_rule(lead_in, rungs, effort_field), (
        "both axes in the bold lead-in is not read as the rule, so a paragraph that states it that "
        "way would have to write it twice")
    assert _states_the_scaling_rule(sentence, rungs, effort_field), (
        "both axes in one sentence is not read as the rule, which is the strict branch the shipped "
        "constitutions satisfy")
    assert not _states_the_scaling_rule(apart, rungs, effort_field), (
        "the axes a whole sentence apart are read as a rule stated in one breath -- which is the "
        "shape that let an effort rule be deleted unnoticed")


def test_the_effort_vocabulary_the_kits_write_is_the_one_the_tier_table_states():
    """Both ends of the one vocabulary this file reads instead of typing.

    `_effort_vocabulary` lifts the accepted effort values out of `team-kits/model_tiers.yaml`, and
    `test_no_lead_skill_keeps_its_own_copy_of_the_scaling_rule` refuses a `<rung>-<effort>` copy
    with it. A reading is only as good as its source, so this measures the source from both sides:
    the table states something, and every value a kit AGENT actually carries in the field the table
    names is one the table stated. A kit that adopts `ultra` while the table still lists five values
    is the drift that would otherwise let a copy through unnamed.

    THE OCCASION (verifier round 4, self-found): the vocabulary was a tuple typed twice in this
    file, and one of its six words -- `default` -- appears in neither the table nor any kit.
    """
    with io.open(os.path.join(ROOT, "team-kits", "model_tiers.yaml"), encoding="utf-8") as handle:
        text = handle.read()
    sys.path.insert(0, TEAM_KITS)
    import yaml as _yaml
    tiers = _yaml.safe_load(text) or {}
    stated = _effort_vocabulary(text)
    assert stated, "model_tiers.yaml states no effort vocabulary beside its effort fields"
    fields = {str(table.get(_EFFORT_KEY_FIELD)) for table in (tiers.get("tiers") or {}).values()
              if isinstance(table, dict) and table.get(_EFFORT_KEY_FIELD)}
    assert fields, "no platform of the tier table names its effort field"
    written = {}
    for field in fields:
        written.update(_agent_frontmatter_values(field))
    assert written, (
        "no kit agent carries an effort value at all -- the reading below then measures nothing")
    unstated = sorted("%s (%s)" % (one, where) for one, where in written.items()
                      if one not in stated)
    assert not unstated, (
        "these kit agents carry an effort value model_tiers.yaml never states, so a `<rung>-<effort>` "
        "copy written with it reads as prose: %s" % "; ".join(unstated))


def test_the_rung_vocabulary_covers_every_model_a_kit_agent_pins():
    """The other axis, from the same side: what the kits PIN has to be in the derived vocabulary.

    `_rung_vocabulary` is a derivation, and a derivation can quietly stop reaching a value -- which
    is exactly what a hand-written `("fable",)` was covering up until round 4. The kits pin their
    rungs in agent frontmatter, so those pins are the independent measure: every one of them is a
    rung the derivation reaches, or the paragraph reader below stops recognising the paragraph that
    names it.

    WHAT THIS DOES NOT MEASURE: whether the derivation reaches a rung nobody pins yet. That gap is
    the price of not listing them, and it closes itself the moment a kit uses one.
    """
    rungs, _effort_field = _rung_vocabulary()
    pinned = _agent_frontmatter_values(_MODEL_KEY_FIELD)
    assert len(pinned) >= 2, (
        "only %d distinct model pin(s) across the kits' agent definitions -- this measures almost "
        "nothing" % len(pinned))
    missing = sorted("%s (%s)" % (one, where) for one, where in pinned.items()
                     if one not in rungs)
    assert not missing, (
        "these kit agents pin a model the rung vocabulary derived from team-kits/model_tiers.yaml "
        "does not reach: %s" % "; ".join(missing))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
