#!/usr/bin/env python3
"""What a specialist hands back, HOW it hands it back, and what a role text may claim.

FOUR SUBJECTS, ONE HABIT: each is asked of the running code and never of a list in this file.

  * THE HAND-BACK CONTRACT. `kernel/schemas/result_envelope.yaml` is the only definition of what a
    specialist gives the orchestrator; `dispatch.submit_result` validates against it before it moves
    a task, and the schema is `strict`, so a ninth key is a refusal and not a courtesy. Six office
    SKILLs still prescribed the V1 shape (`summary`, `proc`, plus per-role keys). Measured before
    the repair, by handing that shape to `kernel.schemas.validate`: eight errors — two unknown
    fields and six missing required ones. The field names therefore come from `load_schema` here,
    and the ROLES that owe the contract come from the same predicate `gate_subagent_output` uses
    (an `agents/<role>.md` exists), minus the kit's session agent.

  * WHO CAN WALK THE HAND-BACK. `submit-result` is a COMMAND LINE, and some shipped specialists
    grant no tool that runs one. Pilot 3 met that three times and reported it as a gap (BUG-0048).
    `kernel.dispatch.hand_back_path` is now the one answer — derived per role from its own
    definition — and the checks below hold the shipped contract texts to it. WHICH roles those are
    is deliberately not written here: AC-1 asks for a derivation, and a count or a name list in
    this docstring is the thing that rots the day a role ships. The measurement of the day belongs
    in the round's report; each test names its own floor instead.

  * A DUTY THAT NEEDS A FEATURE. Role texts tell their role to consult its craft memory, and some
    of them enabled no role memory at all, so there was nothing to consult (BUG-0047). What COUNTS
    as that duty is not a sentence copied here: it is the pattern the Codex generator rewrites
    (`gen_provider_artifacts.MEMORY_DUTY_RX`), because Codex has no such feature — so the running
    code already owns the definition and this file borrows it.

  * A CLAIM ABOUT THE PIPELINE. The QA SKILL said the merge pipeline enforces "coverage >= threshold
    globally AND per source area". `scripts/quality.py` builds ONE `--cov=` base and ONE
    `--cov-fail-under=`, which is read off its AST below rather than off its prose. That made the
    line the failure mode this repo is built against — a text promising protection the code does not
    build — and the correction is pinned here so it cannot quietly return.

WHAT THESE CHECKS DO NOT DO, said here rather than discovered later. They read the shipped SKILL
TEXT, which is the artifact the role receives, so they can tell a missing field name from a present
one and cannot tell a good instruction from a bad one. The second test judges only the sentences
that ENUMERATE the envelope — a sentence naming no envelope field at all (records-clerk's line about
`product_requirement`) is prose about the contract, not a prescription of it, and is deliberately out
of scope. And the coverage test's negative half matches the shipped spelling and near paraphrases of
it, not every possible false claim; its positive half — the block must still name the mechanism that
DOES hold per area — is what carries the weight when someone rewrites the sentence.
"""
import ast
import glob
import io
import json
import os
import re
import shutil
import sys

import pytest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM_KITS = os.path.join(ROOT, "team-kits")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TEAM_KITS)

import lead_package                                                  # noqa: E402


# A backticked span is a NAME only when it is a plain lower-case identifier. `INV`, `UNCLEAR` and
# `verdict: PASS|FAIL` are backticked in shipped output blocks and none of them is an envelope key —
# an item type, a status word and a printed line respectively. Restricting to the spelling a YAML
# key actually has is what keeps this reader from inventing offenders out of prose.
_BACKTICKED_RX = re.compile(r"`([^`]+)`")
_IDENTIFIER_RX = re.compile(r"^[a-z][a-z0-9_]*$")
_SENTENCE_SPLIT_RX = re.compile(r"(?<=\.)\s+")


def _reading_view(text):
    """The text as it READS — a field name in a wrapped list does not stop at the line break."""
    return re.sub(r"\s+", " ", text).strip()


def _kit_dirs():
    """Every shipped kit, taken from the tree by the file that makes it one."""
    return sorted(os.path.dirname(os.path.dirname(path)) for path in
                  glob.glob(os.path.join(TEAM_KITS, "*", "constitution", "AGENTS.md")))


def _specialist_skills():
    """(kit dir, role, SKILL.md) for every role that can be SPAWNED and ships a skill.

    DERIVED THE WAY THE GATE DERIVES IT. `gate_subagent_output` calls a stopping subagent "one of
    ours" when `.claude/agents/<agent_type>.md` exists, so the same question is asked of the kit
    source. The kit's session agent (`settings/settings.json` `agent`, through
    `lead_package.lead_role`) is excluded because it is bound as the lead and never stops as a
    subagent — a kit that renames its lead moves this set with it, and no reader has to be told.
    """
    for kit in _kit_dirs():
        lead = lead_package.lead_role(kit)
        for path in sorted(glob.glob(os.path.join(kit, "skills", "*", "SKILL.md"))):
            role = os.path.basename(os.path.dirname(path))
            if role == lead:
                continue
            if not os.path.isfile(os.path.join(kit, "agents", role + ".md")):
                continue
            yield kit, role, path


def _output_section(path):
    """The `## Output to the …` section of a SKILL, as one reading view.

    The heading wording differs by kit (`to the PM` / `to the manager`), so what is matched is the
    heading's SUBJECT — the hand-back — and not either spelling.
    """
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r"(?m)^##\s+Output to the .*$", text)
    if not match:
        return None
    rest = text[match.end():]
    following = re.search(r"(?m)^##\s", rest)
    return _reading_view(rest[:following.start()] if following else rest)


def _envelope_fields():
    from kernel.schemas import load_schema
    return load_schema("result_envelope")["fields"]


def _valid_envelope():
    """A minimal envelope the kernel accepts — the probe base for the key test below."""
    return {"task_id": "TSK-0001", "role": "probe", "status_proposal": "SUBMITTED",
            "summary": "probe", "outputs": [], "evidence": [], "scope_touched": [],
            "followups": []}


def _kernel_accepts_key(name):
    """Does the KERNEL accept `name` as a top-level envelope key? Asked by running the validator.

    Not by comparing against the fields dict: the question is what `submit_result` will do with the
    key a SKILL told a role to hand over, and that answer is produced by `schemas.validate`, which
    is the code that runs.
    """
    from kernel.schemas import validate, SchemaError
    probe = _valid_envelope()
    probe[name] = "probe" if name not in probe else probe[name]
    try:
        validate(probe, "result_envelope")
    except SchemaError:
        return False
    return True


# ============================================================ 1. the hand-back contract
def test_the_specialist_set_is_the_one_the_gate_would_judge():
    """A floor under both tests below: they are vacuous over a set that stopped matching.

    Twenty-two specialists ship today across three kits (8 dev, 8 office, 7 research, minus each
    kit's lead — the leads carry no hand-back section because they never hand back). The floor sits
    under that so a renamed role cannot trip it, and far enough over zero that losing the derivation
    cannot pass unnoticed.
    """
    found = list(_specialist_skills())
    assert len(found) >= 18, [role for _kit, role, _path in found]
    leads = {lead_package.lead_role(kit) for kit in _kit_dirs()}
    assert leads and None not in leads, leads
    assert not [role for _kit, role, _path in found if role in leads], "a lead leaked into the set"


def test_every_specialist_skill_hands_back_the_whole_result_envelope():
    """Every specialist's output section names every field the envelope schema REQUIRES.

    THE LIST IS THE SCHEMA'S, not this file's: `result_envelope.yaml` is what
    `dispatch.submit_result` validates against and what the orchestrator types as `submit-result`
    flags, so a SKILL that names a different set sends the role to a refusal.

    MEASURED RED before the repair of 2026-08-03, over a copy of the tree outside this repo with the
    six V1 blocks restored: bookkeeper, compliance-researcher, marketing-planner, product-editor and
    shop-curator were each missing seven of the eight fields (they named only `summary`), and
    office-developer six (it happened to spell `outputs`, meaning its dashboard paths). The other
    sixteen specialists — including the two office roles already converted, records-clerk and
    project-auditor — were green in the same run, which is what makes this a check on the six and
    not on the reader.
    """
    required = tuple(name for name, spec in _envelope_fields().items() if (spec or {}).get("required"))
    assert len(required) >= 6, required
    offenders = []
    for kit, role, path in _specialist_skills():
        section = _output_section(path)
        if section is None:
            offenders.append("%s/%s: no `## Output to the …` section at all"
                             % (os.path.basename(kit), role))
            continue
        absent = [name for name in required if ("`%s`" % name) not in section]
        if absent:
            offenders.append("%s/%s: %s" % (os.path.basename(kit), role, ", ".join(absent)))
    assert not offenders, (
        "these specialist SKILLs describe a hand-back that is not the result envelope "
        "(kernel/schemas/result_envelope.yaml requires %s):\n  %s"
        % (", ".join(required), "\n  ".join(offenders)))


def test_no_specialist_skill_prescribes_an_envelope_key_the_kernel_rejects():
    """A field name a SKILL hands a role must survive the validator that receives it.

    WHICH sentences are read: the ones that ENUMERATE the envelope, defined as naming at least one
    of its fields. That definition is what separates a prescription from prose about it —
    records-clerk's closing sentence names `product_requirement` and no envelope field, and it is
    explaining why `proc` is NOT a key rather than asking for one.

    WHAT REJECTION MEANS is asked of `kernel.schemas.validate` with a probe envelope, so the answer
    comes from the code `submit_result` calls rather than from a copy of the field list here.

    MEASURED RED before the repair, same restored copy as the sibling test: 30 offending
    (role, key) pairs over the six office SKILLs, 19 distinct spellings — `proc` in all six, plus
    `booked`, `open_items`, `unclear`, `category_proposals`, `anomalies`, `entries_added_updated`,
    `flags`, `tasks_for_user`, `plan_changes`, `drafts`, `accounts_needed`, `tools`, `verified`,
    `products`, `guideline_additions`, `findings`, `copy_proposals`, `open_questions`.
    """
    fields = set(_envelope_fields())
    judged, offenders = 0, []
    for kit, role, path in _specialist_skills():
        section = _output_section(path) or ""
        for sentence in _SENTENCE_SPLIT_RX.split(section):
            names = [span for span in _BACKTICKED_RX.findall(sentence)
                     if _IDENTIFIER_RX.match(span)]
            if not (set(names) & fields):
                continue        # prose about the contract, not an enumeration of it
            for name in names:
                judged += 1
                if not _kernel_accepts_key(name):
                    offenders.append("%s/%s: `%s`" % (os.path.basename(kit), role, name))
    assert not offenders, (
        "these SKILLs enumerate a hand-back key the kernel refuses (the envelope schema is "
        "strict, so `submit-result` rejects it):\n  %s" % "\n  ".join(sorted(set(offenders))))
    # A floor: every assertion above is vacuously true over a reader that found no names.
    assert judged >= 100, "only %d enumerated key names found — the reader stopped matching" % judged


def test_the_envelope_key_reader_can_tell_a_stranger_from_a_field():
    """The floor under `_kernel_accepts_key`, so "return True" is not a way out.

    Without it the offending half of the test above rests on nothing once the tree is green: a
    reader that accepted everything would look identical. The probe uses the two spellings the
    repaired tree actually contains — a real field and the V1 key that was removed from six SKILLs.
    """
    assert _kernel_accepts_key("summary") is True
    assert _kernel_accepts_key("scope_touched") is True
    assert _kernel_accepts_key("proc") is False
    assert _kernel_accepts_key("open_questions") is False


# ================================================== 2. who can walk the hand-back (BUG-0048)
def _specialist_roles(kit):
    """Every role of `kit` that can be SPAWNED, by the predicate `gate_subagent_output` uses.

    The same derivation as `_specialist_skills` and deliberately NOT that function: a role owes the
    hand-back contract because it can be dispatched, not because it happens to ship a SKILL.
    """
    lead = lead_package.lead_role(kit)
    return sorted(os.path.basename(path)[:-3]
                  for path in glob.glob(os.path.join(kit, "agents", "*.md"))
                  if os.path.basename(path)[:-3] != lead)


def _hand_back(kit, role):
    from kernel import dispatch
    return dispatch.hand_back_path(os.path.join(kit, "agents"), role)


def _settings_command_line_tools(kit):
    """The tools this kit registers `gate_write_scope` on as a COMMAND LINE, off its own wiring.

    Two PreToolUse groups register that gate: the one that judges file writes and the one that
    judges a shell line. Which is which is decided by the gate's OWN `FILE_TOOLS` tuple rather
    than by a matcher spelling here — the group disjoint from it is the command-line group.
    """
    with io.open(os.path.join(kit, "settings", "settings.json"), encoding="utf-8") as handle:
        settings = json.load(handle)
    file_tools = {name.lower() for name in _gate_tuple("FILE_TOOLS")}
    found = set()
    for group in settings["hooks"]["PreToolUse"]:
        if not any(os.path.basename(entry["command"].split()[-1].strip('"')) ==
                   "gate_write_scope.py" for entry in group["hooks"]):
            continue
        tools = [part for part in (group.get("matcher") or "").split("|") if part]
        if not {name.lower() for name in tools} & file_tools:
            found.update(tools)
    return found


def _gate_tuple(name, path=None):
    """A module-level tuple of a shipped hook, read off its AST (`gate_write_scope` by default).

    PARSED, not imported: the hook's import of `_kernel` resolves against a project, and a gate
    that fails closed on an absent kernel would make this reader measure the fixture. Parsed, not
    grepped, for the reason this repo keeps re-learning — a string search finds the tuple in a
    docstring too.
    """
    path = path or os.path.join(TEAM_KITS, "dev-team", "hooks", "gate_write_scope.py")
    with io.open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("%s no longer defines %s" % (os.path.basename(path), name))


def test_the_command_running_tools_are_one_fact_in_three_places():
    """The kernel, the gate and every kit's wiring must name the SAME command-running tools.

    THE UNAVOIDABLE ENUMERATION AND ITS TRIPWIRE. Which provider tools run a command line is
    provider knowledge; nothing in this repo can derive it, so it is written down — once in
    `kernel.dispatch.COMMAND_TOOLS`, because the kernel is what has to ACT on it, and once in
    `gate_write_scope.SHELL_TOOLS`, because that gate must keep routing in a project whose kernel
    is unreachable. This measures BOTH ends and the kits' own `settings.json` matcher as a third,
    so a tool added to one of them cannot sit there alone: the kernel would keep telling a role it
    may run a command the gate never judges, or the reverse.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import dispatch
    kernel_side = {name.lower() for name in dispatch.COMMAND_TOOLS}
    gate_side = {name.lower() for name in _gate_tuple("SHELL_TOOLS")}
    assert kernel_side and kernel_side == gate_side, (kernel_side, gate_side)
    for kit in _kit_dirs():
        wired = {name.lower() for name in _settings_command_line_tools(kit)}
        assert wired == kernel_side, (os.path.basename(kit), wired, kernel_side)
    # A FOURTH statement joined the three in TSK-0099: `gate_design_sighted` decides whose stop it
    # judges by asking whether that role's own frontmatter grants a command-running tool, and it is
    # stdlib-only by spec II.7 — so it cannot import the kernel for the answer either. Same
    # tripwire, same file, rather than a second one somewhere else.
    sighted = _gate_tuple("COMMAND_TOOLS",
                          os.path.join(TEAM_KITS, "dev-team", "hooks", "gate_design_sighted.py"))
    assert {name.lower() for name in sighted} == kernel_side, (sighted, kernel_side)


def test_every_shipped_specialist_is_told_a_path_its_toolset_can_walk():
    """AC-1 of BUG-0048: contract and toolset agree for EVERY shipped specialist, derived.

    TWO HALVES, and both read the shipped artefacts rather than a list:

      * the KERNEL's answer per role is `self` exactly when that role's own frontmatter grants a
        command-running tool. A role added tomorrow is judged the day it ships.
      * a role the kernel puts on the `lead` path may not be handed a command line by its OWN
        texts (its `agents/<role>.md` and its SKILL) — those are addressed to that one role, so a
        `python scripts/harness.py …` in them is a demand it cannot meet. The corpus reader is the
        invocation the shim installs (`kernel.cli.INVOCATION`), so a renamed entry point moves this
        with it.

    MEASURED before the repair over the shipped tree: eight roles come back `lead` and none of
    them names the entry point in its own texts — the contradiction pilot 3 hit lived in the
    CONSTITUTION, which is every role's text at once, and that is the sibling test below.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import cli, dispatch
    call = re.compile(re.escape(cli.INVOCATION) + r"\s+[a-z]")
    shell_less, offenders = [], []
    for kit in _kit_dirs():
        for role in _specialist_roles(kit):
            granted = dispatch.role_tools(os.path.join(kit, "agents"), role)
            assert granted, "%s/%s ships no readable `tools:` frontmatter" % (kit, role)
            runs = {name.lower() for name in granted} & {
                name.lower() for name in dispatch.COMMAND_TOOLS}
            expected = dispatch.HAND_BACK_SELF if runs else dispatch.HAND_BACK_LEAD
            answered = _hand_back(kit, role)
            assert answered == expected, (kit, role, answered, expected, granted)
            if answered != dispatch.HAND_BACK_LEAD:
                continue
            shell_less.append("%s/%s" % (os.path.basename(kit), role))
            for path in (os.path.join(kit, "agents", role + ".md"),
                         os.path.join(kit, "skills", role, "SKILL.md")):
                if not os.path.isfile(path):
                    continue
                with io.open(path, encoding="utf-8") as handle:
                    if call.search(_reading_view(handle.read())):
                        offenders.append("%s/%s: %s" % (os.path.basename(kit), role,
                                                        os.path.basename(path)))
    assert not offenders, (
        "these role texts hand a command line to a role whose own definition grants no tool that "
        "runs one (BUG-0048). Either give the role the tool or name the path it CAN walk:\n  %s"
        % "\n  ".join(offenders))
    # A floor: every assertion above is vacuous over a tree where no role is shell-less.
    assert len(shell_less) >= 4, shell_less


def _role_definition(kit, role):
    """(frontmatter mapping, body) of a shipped role definition."""
    import yaml
    path = os.path.join(kit, "agents", role + ".md")
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    end = text.find("\n---", 3)
    assert text.startswith("---") and end > 0, path
    return yaml.safe_load(text[3:end]) or {}, text[end:]


def test_the_memory_duty_is_only_prescribed_where_the_role_has_memory():
    """A role told to consult its craft memory must be a role that HAS one (BUG-0047).

    THE DUTY IS DEFINED BY RUNNING CODE, not by a sentence copied into this file:
    `gen_provider_artifacts.MEMORY_DUTY_RX` is the pattern the Codex generator rewrites, because
    Codex has no per-role memory — so that pattern already IS this repo's answer to "does this
    text prescribe the memory duty", and a reworded duty that escaped it would escape the Codex
    rewrite too. The other side is the role's own frontmatter, read as YAML rather than searched
    for a spelling.

    MEASURED before the repair over the shipped tree: two offenders, dev `devops-engineer` and
    research `researcher` — both carrying the sentence, neither carrying the frontmatter key, so
    both were told to consult a directory the provider never gives them. The kit's OTHER five
    duty-carrying roles were green in the same run, which is what makes this a check on the two
    and not on the reader.
    """
    sys.path.insert(0, TEAM_KITS)
    import gen_provider_artifacts
    prescribed, offenders = [], []
    for kit in _kit_dirs():
        for path in sorted(glob.glob(os.path.join(kit, "agents", "*.md"))):
            role = os.path.basename(path)[:-3]
            front, body = _role_definition(kit, role)
            if not gen_provider_artifacts.MEMORY_DUTY_RX.search(_reading_view(body)):
                continue
            prescribed.append("%s/%s" % (os.path.basename(kit), role))
            if not front.get(gen_provider_artifacts.MEMORY_FRONTMATTER_KEY):
                offenders.append("%s/%s" % (os.path.basename(kit), role))
    assert not offenders, (
        "these role texts prescribe the craft-memory duty to a role whose own definition enables "
        "no role memory, so there is nothing to consult and nowhere the update lands (`%s:` is "
        "the key). Either enable it or drop the duty:\n  %s"
        % (gen_provider_artifacts.MEMORY_FRONTMATTER_KEY, "\n  ".join(offenders)))
    # A floor: the assertion above is vacuous over a reader that stopped matching the duty at all.
    assert len(prescribed) >= 6, prescribed


def test_the_lead_of_every_kit_with_a_shell_less_role_carries_the_relay(kit=None):
    """The OTHER half of the `lead` path, and it needs its own reader (BUG-0048).

    A relay has two ends. The specialist's end is checked twice above; the lead's end — actually
    running `submit-result --from` on the envelope the specialist staged — lived only in the lead
    role texts, and nothing went red when it was removed from all three: a section pin notices a
    CHANGE, never a GAP, and the constitution paragraph is the specialist's text, not the lead's.

    WHAT IS ASKED, both ends derived: for every kit in which ANY dispatched role resolves to
    `dispatch.HAND_BACK_LEAD`, that kit's own lead — `lead_package.lead_role`, the same source
    `_specialist_skills` excludes by — must name the relay in its role text, and "name the relay"
    is the FLAG the kernel's parser actually carries (read off `build_parser`, so a rename moves
    this with it) standing behind the invocation `kernel.cli` installs. A kit whose roles all carry
    a shell owes nothing, and says so by not entering the loop.

    MEASURED RED in a clone outside this repo with the `--from` bullet cut from all three lead role
    texts: three offenders. `kit` is a parameter only so the failure names one; the loop is over
    the derived set.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import cli, dispatch
    flags = [option for action in cli.build_parser()._subparsers._group_actions[0]
             .choices["submit-result"]._actions for option in action.option_strings]
    relay = next(option for option in flags if option.lstrip("-") == "from")
    judged, offenders = 0, []
    for directory in _kit_dirs():
        if kit and os.path.basename(directory) != kit:
            continue
        if not [role for role in _specialist_roles(directory)
                if _hand_back(directory, role) == dispatch.HAND_BACK_LEAD]:
            continue
        judged += 1
        lead = lead_package.lead_role(directory)
        with io.open(os.path.join(directory, "agents", lead + ".md"), encoding="utf-8") as handle:
            text = _reading_view(handle.read())
        if not re.search(re.escape(cli.INVOCATION) + r"[^`]*" + re.escape(relay) + r"\b", text):
            offenders.append("%s/%s" % (os.path.basename(directory), lead))
    assert not offenders, (
        "these kits dispatch a role that cannot run a command, and their lead's own text never "
        "says how to book its result in (`%s %s`). The specialist's half of the relay is written "
        "and the lead's half is not:\n  %s" % (cli.INVOCATION, relay, "\n  ".join(offenders)))
    assert judged >= 1, "no kit ships a shell-less dispatched role — this check judged nothing"


def _constitution_block(kit, pattern):
    """The paragraph of a kit constitution that matches `pattern`, as one reading view."""
    path = os.path.join(kit, "constitution", "AGENTS.md")
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    for block in re.split(r"\n\s*\n", text):
        if re.search(pattern, block):
            return _reading_view(block)
    return None


def test_the_checkpoint_duty_binds_only_the_roles_that_could_run_it():
    """The constitution may not demand a COMMAND of every dispatched role (BUG-0048).

    THE DEMAND IS REAL AND IT IS THE ONE PLACE THAT ADDRESSES EVERY ROLE AT ONCE: §6 tells "a
    dispatched role" to run `python scripts/harness.py checkpoint <TSK-ID>`, and eight shipped
    specialists grant no tool that runs a command line. So the run-up to that command has to name
    WHICH roles it binds, and the block has to say what happens to the others.

    WHAT IS ASKED OF THE TEXT, defined rather than spelled: the two values the KERNEL emits in the
    dispatch header (`dispatch.HAND_BACK_SELF` / `HAND_BACK_LEAD`), each in a code span — the
    qualifier in front of the command, and the fallback somewhere in the same block. Renaming
    either value in the kernel moves this requirement with it; a block that keeps the demand and
    drops the qualifier goes red.

    MEASURED RED before the repair, over a copy of the tree outside this repo carrying the shipped
    "A dispatched role therefore CHECKPOINTS — `python scripts/harness.py checkpoint <TSK-ID>`":
    three offenders, one per kit, on the run-up half.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import cli, dispatch
    demand = re.escape(cli.INVOCATION) + r"\s+checkpoint\b"
    offenders, judged = [], 0
    for kit in _kit_dirs():
        shell_less = [role for role in _specialist_roles(kit)
                      if _hand_back(kit, role) == dispatch.HAND_BACK_LEAD]
        if not shell_less:
            continue
        block = _constitution_block(kit, demand)
        assert block, "%s no longer states the checkpoint duty at all" % os.path.basename(kit)
        judged += 1
        run_up = block[:re.search(demand, block).start()]
        if ("`%s`" % dispatch.HAND_BACK_SELF) not in run_up:
            offenders.append("%s: the demand is unqualified — %s cannot run it"
                             % (os.path.basename(kit), ", ".join(shell_less)))
        if ("`%s`" % dispatch.HAND_BACK_LEAD) not in block:
            offenders.append("%s: the block names no outcome for the roles it does not bind"
                             % os.path.basename(kit))
    assert not offenders, (
        "the constitution demands a command line of roles whose toolset grants no way to run "
        "one:\n  %s" % "\n  ".join(offenders))
    assert judged >= 3, "only %d kits judged — every kit lost its shell-less roles?" % judged


# ============================================================ 3. a claim about the pipeline
def _quality_py():
    return os.path.join(TEAM_KITS, "dev-team", "templates", "repo", "scripts", "quality.py")


def _coverage_bases_and_floors():
    """(coverage bases, floor flags) `quality.py` can hand pytest, read off its AST.

    The BASE is the operand `--cov=` is concatenated with; if the script ever measured several
    areas, there would be several distinct operands (or one built inside a loop). Reading the AST
    rather than the file text is the point: the shipped module's own docstring says "tests+coverage"
    and says nothing about how many bases that is.
    """
    with io.open(_quality_py(), encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=_quality_py())
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "check_python")
    bases, floors = set(), set()
    for node in ast.walk(function):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add) \
                and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
            if node.left.value == "--cov=":
                bases.add(ast.dump(node.right))
            elif node.left.value.startswith("--cov-fail-under"):
                floors.add(node.left.value)
    return bases, floors


def _block_naming_the_coverage_threshold():
    """The QA SKILL's markdown block that states the coverage floor, as one reading view.

    A BLOCK and not a sentence: the correction and the pointer to what really holds per area are two
    sentences of one numbered step, and a sentence-sized window would have demanded both in the same
    breath — which is how a check starts dictating prose instead of judging a claim. The step is the
    unit, not the paragraph: the shipped `## Do` list runs its numbered items together without blank
    lines, so a paragraph-sized window reached into step 3 and read QA's own per-area coverage MAP
    (a thing it writes into its Evidence) as a claim about the pipeline.
    """
    path = os.path.join(TEAM_KITS, "dev-team", "skills", "quality-engineer", "SKILL.md")
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    for block in re.split(r"(?m)^(?=\d+\.\s)", text):
        if re.search(r"coverage\s*(?:≥|>=)\s*threshold", block):
            return _reading_view(block)
    raise AssertionError("the QA SKILL no longer names the coverage threshold at all")


def test_the_qa_coverage_claim_matches_what_quality_py_measures():
    """The QA SKILL may not promise a coverage floor per source area, because there is none.

    THE FACT COMES FROM THE RUNNING CODE: `check_python` concatenates `--cov=` with exactly ONE
    operand and passes exactly one `--cov-fail-under=`, so the pipeline measures one base against
    one number. `gate_test_coverage` is what holds per AREA, and its own docstring says what that
    is: "this hook only catches the 'whole area untested' failure that a global % can mask".

    MEASURED RED before the repair, over a copy outside this repo carrying the shipped line
    "coverage >= threshold globally AND per source area (src/, frontend/src/ ...)": one offender.

    WHAT THIS CANNOT DO: it matches the shipped spelling and close paraphrases of it, not every way
    a false claim could be phrased. The half that survives a rewrite is the second assertion — the
    block that names the threshold must, in the same breath, name the mechanism that really holds
    per area, so a reader who deletes the correction also deletes the pointer and this goes red.
    """
    bases, floors = _coverage_bases_and_floors()
    assert len(bases) == 1, (
        "quality.py builds %d coverage bases — the SKILL text below was written against one" % len(bases))
    assert len(floors) == 1, floors

    block = _block_naming_the_coverage_threshold()
    # AN AFFIRMED PER-AREA THRESHOLD, defined rather than spelled: a mention of "per (source) area"
    # whose run-up talks about a threshold, floor or percentage AND carries no negation. Both halves
    # are needed and both were measured. Without the threshold half, "what holds per AREA is weaker"
    # — the sentence that states the correction — reads as the defect. Without the negation half,
    # "there is NO percentage floor per source area" does. What survives is the shape of the old
    # claim: a floor, bound to areas, asserted.
    liars = []
    for match in re.finditer(r"per[\s-](?:source[\s-])?area", block):
        run_up = block[max(0, match.start() - 80):match.start()]
        if not re.search(r"threshold|floor|percentage|%", run_up):
            continue
        if re.search(r"\b(?:no|not|never|nothing|without)\b", run_up):
            continue
        liars.append(block[max(0, match.start() - 80):match.end()])
    assert not liars, (
        "the QA SKILL binds the coverage threshold to source areas and quality.py measures ONE "
        "base against ONE floor:\n  %s" % "\n  ".join(liars))
    assert "gate_test_coverage" in block, (
        "the QA SKILL states the coverage floor without naming what DOES hold per source area — "
        "a reader then reads the silence as 'nothing', which is as wrong as the old over-claim")


# ================================== 4. the filing pipeline's two artifacts (FR-0049)
def _pipeline_schemas():
    """(schema name, writer role, required per-entry keys) for every schema that names its writer.

    DERIVED FROM THE SCHEMAS, not listed here: a schema declares `writer_role` when it describes an
    artifact a ROLE produces, so a third pipeline artifact joins this check the day it names its
    writer and a schema that describes something else (`result_envelope`, `session_brief`) stays out
    without being excluded anywhere.
    """
    from kernel.schemas import _SCHEMA_DIR, load_schema
    for name in sorted(os.listdir(_SCHEMA_DIR)):
        if not name.endswith(".yaml"):
            continue
        schema = load_schema(name[:-5]) or {}
        role = schema.get("writer_role")
        if role:
            yield name[:-5], role, schema


def test_the_pipeline_texts_name_the_fields_their_own_schema_declares():
    """A role told to write an artifact must be told its FIELDS -- from the schema, once.

    THE DEFECT SHAPE THIS IS AGAINST is the one `test_every_specialist_skill_hands_back_the_whole_
    result_envelope` was written for: six office SKILLs prescribed a hand-back shape the kernel
    rejects, because the shape lived in prose beside the contract instead of being read off it. The
    filing pipeline has the same structure twice over -- the clerk WRITES the proposal list and the
    reviewer READS it, so a drift in either text is two roles describing different objects.

    WHAT IS ASKED: the writer's own SKILL names every top-level field the schema requires and every
    per-entry key of its list (`item_required`), each in a code span; and where the schema declares a
    VOCABULARY for an entry key (`item_enums` -- the three verdicts), the SKILL names each word.
    Nothing here asks for a sentence: a check on prose would start dictating it.

    MEASURED RED in a copy of the tree outside this repo with the `filing_verdicts` step cut out of
    the reviewer's SKILL: one offender, five missing names.

    WHERE THE FLOOR LIVES, and it moved twice. It was `len(wanted) >= 8` PER SCHEMA, which is a claim
    that every pipeline contract is at least that big -- and `filing_reading` (FR-0035) declares six
    names because that is its whole shape, so a correct third contract turned this red for being
    small. The first correction dropped the per-schema floor to "yields something", which was too
    loose in the other direction: one schema could shrink from ten names to one and the aggregate
    would not notice. So BOTH, and both as floors under the measured stand rather than at it (the run
    extracts 24 names today; the numbers below are the level at which the reader is provably still
    reading, not a record of what it finds).
    """
    judged, offenders, total = 0, [], []
    for name, role, schema in _pipeline_schemas():
        paths = [path for path in glob.glob(os.path.join(TEAM_KITS, "*", "skills", role,
                                                         "SKILL.md"))]
        assert paths, "%s names %s as its writer and no kit ships that role's SKILL" % (name, role)
        wanted = [field for field, spec in (schema.get("fields") or {}).items()
                  if (spec or {}).get("required")]
        for field, spec in (schema.get("fields") or {}).items():
            wanted += list((spec or {}).get("item_required") or [])
            for values in ((spec or {}).get("item_enums") or {}).values():
                wanted += list(values)
        assert len(wanted) >= 3, (
            "%s yielded %d field names -- below the smallest contract this pipeline has (a task id, "
            "a writer and one list), so the reader has stopped matching: %s"
            % (name, len(wanted), wanted))
        total += wanted
        for path in paths:
            with io.open(path, encoding="utf-8") as handle:
                text = _reading_view(handle.read())
            judged += 1
            absent = [word for word in wanted if ("`%s`" % word) not in text]
            if absent:
                offenders.append("%s (%s): %s" % (role, name, ", ".join(sorted(set(absent)))))
    assert not offenders, (
        "these role texts prescribe an artifact whose contract they do not spell out, so the two "
        "ends of the pipeline can drift apart (the contracts are team-kits/kernel/schemas/):\n  %s"
        % "\n  ".join(offenders))
    assert judged >= 2, "only %d pipeline SKILLs judged -- the derivation stopped matching" % judged
    assert len(total) >= 20, (
        "only %d field names were extracted from all pipeline schemas together -- the reader "
        "narrowed: %s" % (len(total), sorted(set(total))))


# ============================ 5. the answering rule, and where it has to stand (FR-0052)
def _markdown_sections(text):
    """The `##` sections of a markdown text, heading included, as raw slices.

    Raw and not a reading view: the two texts below are compared BYTE for byte across kits, and a
    whitespace-flattened slice would call two differently wrapped copies the same block.
    """
    starts = [match.start() for match in re.finditer(r"(?m)^##\s", text)]
    return [text[start:(starts[index + 1] if index + 1 < len(starts) else len(text))]
            for index, start in enumerate(starts)]


def _answering_sections(path, names):
    """The sections of the file at `path` that name every string in `names`.

    TWO RULES USE THIS NOW, so it says nothing about either one: which strings identify a block is
    the caller's question, and each answers it from running code (`_rule_anchors`,
    `_value_language_anchors`). What this function contributes is only the shape -- a `##` section
    is the unit, and a block matches when it names EVERY anchor, so a rule identified by a heading
    whose text drifted is found missing rather than matched by accident.
    """
    if not os.path.isfile(path):
        return []
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    return [block for block in _markdown_sections(text)
            if all(name in block for name in names)]


def _rule_anchors():
    """(brief decision field, decisions directory) -- the two names the rule must send a reader to.

    WHICH SECTION IS "THE ANSWERING RULE" is decided by the two artifacts it sends the reader to,
    and both spellings come from running code (the session_brief schema and
    `backlog_types.ACTIVE_DIRS`). So a renamed field or a moved directory makes the reader go
    looking for a block that no longer exists, rather than quietly matching a heading whose text
    drifted. (This paragraph stood in `_answering_sections` while that helper had one caller; it
    belongs to the anchors, not to the section reader.)
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import backlog_types
    from kernel.schemas import load_schema
    field = "standing_decisions"
    assert field in (load_schema("session_brief").get("fields") or {}), (
        "the session brief no longer carries a `%s` field. The answering rule in every kit's lead "
        "texts points at it by name, so the rename has to move both." % field)
    return field, backlog_types.ACTIVE_DIRS["DEC"]


def _enforcement_words(kit):
    """The words that name this kit's enforcement layer, off its own wiring rather than typed here.

    Two sources, both running: the provider's registration key in `settings/settings.json` (`hooks`),
    and the prefix carried by more than one of the hook FILES that key registers (`gate_…`,
    `guard_…`). A one-off prefix is dropped because it names a single mechanism rather than the
    apparatus -- `session_status` is not a word a text uses to claim enforcement. A kit that renames
    its mechanisms moves this vocabulary with it.
    """
    with io.open(os.path.join(kit, "settings", "settings.json"), encoding="utf-8") as handle:
        settings = json.load(handle)
    words = {key[:-1].lower() for key, value in settings.items()
             if key.endswith("s") and isinstance(value, dict)}
    prefixes = {}
    for groups in settings.get("hooks", {}).values():
        for group in groups:
            for entry in group.get("hooks", []):
                base = os.path.basename(entry["command"].split()[-1].strip('"'))
                if "_" in base:
                    prefixes[base.split("_")[0].lower()] = prefixes.get(
                        base.split("_")[0].lower(), 0) + 1
    words.update(name for name, count in prefixes.items() if count > 1)
    return words


# THE WORDS THAT TURN A MENTION INTO ITS OPPOSITE. A vocabulary and therefore finite, which is the
# limit named in the tests that use it; what it must at least cover is the language the blocks it
# guards are written in.
#
# GERMAN IS IN HERE SINCE TSK-0093, and it was a measured miss rather than a hypothetical: that
# round writes a rule PRESCRIBING German values, and an honest German limit sentence in one of these
# blocks ("Kein Gate liest das.") was classified AFFIRMED -- the guard would have reported the one
# shape it exists to permit. The particles are spelled out rather than stemmed, because a stem
# matches words that negate nothing (`nie` inside `Niederlage`), and `\b` on both ends is what keeps
# each of them a word.
_NEGATION_RX = re.compile(
    r"\b(?:no|not|never|nothing|none|cannot|can't|invisible|without"
    r"|kein|keine|keinen|keinem|keiner|keines|nicht|nichts|nie|niemals|ohne|unsichtbar)\b",
    re.IGNORECASE)
# Where a clause ends. The run-up in front of a mention is cut here, so a negation belonging to
# ANOTHER sentence cannot excuse it.
_CLAUSE_END = ".;:\n"


def _enforcement_claims(block, words):
    """(affirmed, negated) mentions of the enforcement apparatus inside `block`.

    A mention is NEGATED when its OWN CLAUSE carries a negation, and AFFIRMED when it does not --
    the shape `test_the_qa_coverage_claim_matches_what_quality_py_measures` uses for the same
    question one subject over.

    THE RUN-UP IS CUT AT A CLAUSE BOUNDARY AND NOT AFTER N CHARACTERS, and that correction is why
    this docstring exists. A fixed 90-character window was measured dead against the block it
    guards: the delivered text is saturated with negation words, so from the second line on every
    window already contains one, and an overclaim sentence inserted anywhere below the first line
    classified as NEGATED. Measured 2026-08-29 on the shipped dev SKILL block with the honesty
    sentences REPLACED by "A gate refuses an answer that skipped this step.": affirmed=0, negated=1
    -- the check passed over exactly the claim it exists to catch. With the boundary cut the same
    text is affirmed=1, negated=0.

    THE NEGATION VOCABULARY IS FINITE (`_NEGATION_RX`) and covers English and German; a limit
    phrased with neither -- a symbol, another language, an ironic reading -- lands in `affirmed`.
    That direction is the safe one (a false alarm is read by a human), and the floor under both
    directions is `test_the_enforcement_reader_hears_a_negation_in_the_languages_these_blocks_use`.
    """
    affirmed, negated = [], []
    for word in sorted(words):
        for match in re.finditer(r"\b%s\b" % re.escape(word), block, re.IGNORECASE):
            head = block[:match.start()]
            cut = max(head.rfind(char) for char in _CLAUSE_END)
            run_up = head[cut + 1:]
            (negated if _NEGATION_RX.search(run_up) else affirmed).append(
                run_up + match.group(0))
    return affirmed, negated


@pytest.mark.parametrize("sentence,negated_expected", [
    ("A gate refuses an answer that skipped this step.", False),
    ("Ein Gate verweigert eine Antwort, die diesen Schritt übersprungen hat.", False),
    ("No gate reads this -- free text never reaches one.", True),
    ("Kein Gate liest das; Freitext erreicht keines.", True),
    ("Nichts erzwingt das, und keine Regel dahinter ist ein Hook.", True),
    # the TSK-0089 lesson, in one probe: an honest limit followed by an overclaim. The second
    # mention has its own clause and must not inherit the first one's negation.
    ("Nothing enforces this. A gate refuses it anyway.", False),
])
def test_the_enforcement_reader_hears_a_negation_in_the_languages_these_blocks_use(
        sentence, negated_expected):
    """The floor under both honesty guards: the reader itself, driven over one sentence at a time.

    WHY IT EXISTS AT ALL: the two tests above can only fail when a shipped block is wrong, so a
    reader that classified everything as NEGATED would keep them green forever while measuring
    nothing -- the shape this repo calls a test that cannot fail. Here the reader is the subject.

    THE VOCABULARY IS THE KIT'S OWN, not a word typed here: `_enforcement_words` off a shipped
    `settings.json`, and the probes are built from a word it really yields, so a kit that renames
    its mechanisms moves these probes with it instead of leaving them measuring a dead string.

    GERMAN IS HALF THE TABLE because TSK-0093 writes a rule prescribing German values, and an
    honest German limit ("Kein Gate liest das") was measured AFFIRMED before `_NEGATION_RX` learned
    the particles -- i.e. the guard would have refused the one shape it exists to allow.
    """
    words = _enforcement_words(_kit_dirs()[0])
    word = next(one for one in sorted(words) if re.search(r"\b%s\b" % one, sentence, re.I))
    affirmed, negated = _enforcement_claims(sentence, {word})
    assert bool(negated) == negated_expected and bool(affirmed) != negated_expected, (
        "%r -> affirmed=%s negated=%s" % (sentence, affirmed, negated))


def test_every_kit_lead_is_told_to_answer_from_the_decisions_before_the_code():
    """FR-0052: a WHY/target question is answered from the record first -- in every kit, and in the
    text that actually LOADS.

    TWO SURFACES, both derived. `lead_package.on_demand_files` is the lead SKILL, which the item
    asks for; `lead_package.files` is what a session loads and never unloads -- measured 2026-08-02,
    the SKILL is registered and NOT injected, so a rule that stood only there would not be in front
    of the lead at the moment a user asks. Both must carry the rule, and one copy of it must be
    identical across kits: skills are not mirrored files and no `KIT_SPECIFIC` mechanism covers them,
    so that identity IS the mirror for this block.

    WHAT IS ASKED IS AN INTERSECTION, NOT A COUNT, and that is the correction of 2026-08-29. Demanding
    EXACTLY ONE matching section per surface forced more than this round decided: the day any kit's
    constitution names both anchors in a section of its own -- a legitimate thing for a later round to
    do -- this test went red with a message about the lead SKILL. Asked as "the kits share a block",
    an extra kit-specific section is none of this test's business and a missing or drifted rule still
    is.

    MEASURED RED before this round, over the shipped tree: six offenders, one per kit per surface.
    Nothing in any lead SKILL, lead agent file or constitution directed a decisions-first lookup --
    every "question" and "answer" in them is about the lead ASKING the user or about the user
    answering an approval.

    WHAT THIS CANNOT DO, and the second sentence is sharper than the one that stood here. It reads
    PROSE, so it cannot tell whether the lead obeyed the rule -- NO HOOK CAN: free text is invisible
    to every gate. And of the block's CONTENT it reads only the two anchors: measured 2026-08-29, the
    rule INVERTED in all six texts ("the code before the decisions", limit sentence kept) passes this
    test and its sibling, because both anchors are still named and direction is not something either
    of them asks about.
    """
    anchors = _rule_anchors()
    loaded, on_demand = {}, {}
    for kit in _kit_dirs():
        name = os.path.basename(kit)
        skill = {block for path in lead_package.on_demand_files(kit)
                 for block in _answering_sections(path, anchors)}
        package = {block for path in lead_package.files(kit)
                   for block in _answering_sections(path, anchors)}
        assert skill, (
            "%s: no section of its lead SKILL names both %s and %s -- the answering rule is not "
            "there" % (name, anchors[0], anchors[1]))
        assert package, (
            "%s: no section of the LOADED package (%s) names both %s and %s. The lead SKILL is "
            "registered, not injected, so a rule that stands only in it is not in front of the lead "
            "when the user asks" % (name,
                                    ", ".join(os.path.basename(p) for p in lead_package.files(kit)),
                                    anchors[0], anchors[1]))
        on_demand[name], loaded[name] = skill, package
    assert set.intersection(*on_demand.values()), (
        "the kits' lead SKILLs share no identical answering rule -- one copy has drifted: %s"
        % sorted(on_demand))
    assert set.intersection(*loaded.values()), (
        "the kits' loaded lead texts share no identical answering rule -- one copy has drifted: %s"
        % sorted(loaded))
    assert len(on_demand) >= 3, sorted(on_demand)


def test_the_answering_rule_claims_no_enforcement_it_does_not_have():
    """The rule is about honest answering, so the rule itself may not overclaim (FR-0052).

    THE HONEST LIMIT IS THE SUBJECT: no hook can enforce search-before-answer, because free text
    never reaches a gate. A block that named a gate as its backing would be exactly the failure this
    repo is built against, and a block that dropped the limit would leave the next reader to assume
    one. So both halves are asked: every mention of the apparatus stands in a CLAUSE that negates it,
    and at least one such mention is there.

    MEASURED RED 2026-08-29 in a clone outside this repo, four runs, both surfaces and both shapes an
    overclaim can take. Honesty sentences REPLACED by "A gate refuses an answer that skipped this
    step.": SKILL affirmed=1/negated=0, agent file affirmed=1/negated=0. The same sentence merely
    ADDED, the honesty kept -- the harder shape, because the block still reads honest: SKILL
    affirmed=1/negated=2, agent affirmed=1/negated=2. Honesty sentences cut without replacement:
    negated=0 on both. The shipped blocks are affirmed=0/negated=2 in the same run.

    THE RESIDUE, because the vocabulary is derived and therefore finite: an overclaim phrased without
    naming the apparatus -- "the harness refuses an answer that skipped this" -- carries no word
    `_enforcement_words` yields and is not caught here. Nor is one caught by the sibling test, which
    asks only that the three copies AGREE; what makes such an edit visible at all is
    `test_shortening_net.test_no_section_of_a_pinned_instruction_file_disappears_unnoticed`, whose
    digest over this section then demands a re-pin with a written note. That is visibility, not a
    refusal, and the difference is the whole point of this docstring.
    """
    anchors = _rule_anchors()
    judged = 0
    for kit in _kit_dirs():
        words = _enforcement_words(kit)
        assert words, "%s registers no hooks -- the vocabulary came out empty" % kit
        for path in lead_package.files(kit) + lead_package.on_demand_files(kit):
            for block in _answering_sections(path, anchors):
                judged += 1
                affirmed, negated = _enforcement_claims(block, words)
                assert not affirmed, (
                    "%s/%s: the answering rule names the enforcement layer without a negation, and "
                    "nothing enforces search-before-answer -- free text reaches no gate:\n  %s"
                    % (os.path.basename(kit), os.path.basename(path), "\n  ".join(affirmed)))
                assert negated, (
                    "%s/%s: the answering rule states no limit at all. A reader then assumes a "
                    "mechanism behind it, and there is none" % (os.path.basename(kit),
                                                                os.path.basename(path)))
    assert judged >= 6, "only %d rule blocks judged -- the reader stopped finding them" % judged


# ====================== 6. the language of the values a lead types into an approval (BUG-0073)
def _positioned_manifest_parameters():
    """Every manifest parameter a builder in `kernel.approvals` turns into a FILE POSITION.

    Read off the running module's own source: a parameter handed to `filed_position` is a path the
    kernel resolves against the project, which is what distinguishes it from prose a user reads.
    Derived rather than named, because the pair this exists for (`kit_document`, `proposal`) grew
    from one approval kind to two in a single round, and a list here would have had to be reopened
    in exactly that round.
    """
    import ast

    from kernel import approvals as approvals_module
    with io.open(approvals_module.__file__, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    found = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "filed_position"):
            found |= {argument.id for argument in node.args if isinstance(argument, ast.Name)}
    assert found, "no manifest parameter is turned into a position -- this reader stopped matching"
    return found


def _value_language_anchors():
    """The two names the value-language rule must send a reader to, both read off the shipped CLI.

    THE COMMAND, asked of the parser by the property that identifies it rather than by its spelling:
    it is the subcommand carrying a POSITIONAL whose choices are exactly the approval kinds
    (`item_derived_kinds` + `line_manifest_kinds`). A rename moves this reader with it, and a second
    command growing the same positional is a finding rather than a silent second answer.

    THE VALUE, asked of the same surface: `cli._line_manifest` types a manifest key on the line
    unless `LINE_MANIFEST_RESOLVERS` derives it, so the typed keys ARE what a role writes into an
    approval card. The subject here is the ones MORE THAN ONE kind asks for -- a value the rule
    cannot dismiss as one command's peculiarity. Today that is one key; a second one arriving is a
    second free-typed value the rule owes the user a sentence about, and it arrives here demanding
    it instead of passing unnoticed.

    A POSITION IS NOT SUCH A VALUE, and that exception is a measurement rather than a convenience:
    on 2026-09-02 a second document approval kind (`document_revision`, FR-0067) shipped, which
    made `kit_document` and `proposal` typed by more than one kind -- and this reader, anchored on
    all three names at once, matched ZERO sections in every kit and reported the rule as missing
    everywhere. Both are file positions: the builders hand them to `approvals.filed_position`,
    which is what makes them paths rather than prose, and a rule about which LANGUAGE a value is
    written in has nothing to say about a path. So the exception is read off the builders
    themselves -- a parameter a builder positions is not a free-typed value -- and a genuinely new
    PROSE key still arrives here demanding its sentence.

    BOTH ARE READ IN THEIR BACKTICKED SPELLING, and that is a measurement rather than a taste. Bare,
    these two names are ordinary English: run over the shipped tree on 2026-08-30 the bare pair
    matched FOURTEEN sections that have nothing to do with this rule -- every work loop, every
    preset section, both startup gates -- so a reader anchored on them would have called the rule
    present while it was nowhere written. Backticked the same run matches nothing at all, which is
    what makes the red below the absence of the rule and not a coincidence of vocabulary. What this
    reader therefore does NOT see is a rule that names its two anchors in prose only.
    """
    import argparse
    import collections
    from kernel import approvals, cli
    parser = cli.build_parser()
    subs = [action for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)]
    assert subs, "the shipped CLI has no subcommands -- this reader stopped matching"
    kinds = set(approvals.item_derived_kinds()) | set(approvals.line_manifest_kinds())
    assert kinds, "the kernel offers no approval kinds -- this reader stopped matching"
    commands = sorted(name for name, sub in subs[0].choices.items()
                      for action in sub._actions
                      if not action.option_strings and set(action.choices or ()) == kinds)
    assert len(commands) == 1, (
        "exactly one subcommand opens an approval question; the parser offers %s" % commands)
    typed = collections.Counter(
        key for builder in approvals.LINE_MANIFEST_BUILDERS.values()
        for key in cli.manifest_parameters(builder)
        if key not in cli.LINE_MANIFEST_RESOLVERS)
    positions = _positioned_manifest_parameters()
    shared = sorted(key for key, count in typed.items()
                    if count > 1 and key not in positions)
    assert shared, (
        "no manifest value is typed on the line by more than one approval kind -- the subject this "
        "reader anchors on is gone: %s" % sorted(typed))
    return tuple("`%s`" % name for name in commands + shared)


def test_every_kit_lead_is_told_which_language_an_approval_value_is_written_in():
    """BUG-0073: the values a lead types into an approval card are German where the user judges them.

    THE MEASURED DEFECT: the kernel writes the approval question in German and shows every typed
    value verbatim, so a card is half kernel and half lead. On the user's own office project a
    `filing_rule` card arrived with its naming pattern, its retention and its reason in English
    inside the German frame, because nothing in any lead text says which language a VALUE carries --
    and this is the one surface where the user's reading IS the protection.

    TWO SURFACES, both derived, for `test_every_kit_lead_is_told_to_answer_from_the_decisions_
    before_the_code`'s measured reason: `lead_package.files` is what a session loads and never
    unloads, `lead_package.on_demand_files` is the lead SKILL, which is registered and NOT injected
    (measured 2026-08-02). A rule standing only in the SKILL is not in front of the lead at the
    moment it composes a `request-approval` line.

    ONE COPY PER SURFACE MUST BE IDENTICAL ACROSS THE KITS: skills are not mirrored files and no
    `KIT_SPECIFIC` mechanism covers them, so that identity IS the mirror for these two blocks. An
    intersection and not a count, for the reason the sibling test records: a kit growing a section
    of its own that happens to name both anchors is none of this test's business.

    MEASURED RED 2026-08-30 over the shipped tree, before the rule was written: six offenders, one
    per kit per surface -- no section of any lead agent file, constitution or lead SKILL named both
    anchors.

    WHAT IT CANNOT DO: it reads PROSE, so it cannot tell whether a lead obeyed the rule, and of the
    block's content it reads only the two anchors -- the rule INVERTED ("English values, German
    keys") names them both and passes. That is the same residue the answering rule carries, and the
    same reason it is stated rather than papered over.
    """
    anchors = _value_language_anchors()
    loaded, on_demand = {}, {}
    for kit in _kit_dirs():
        name = os.path.basename(kit)
        skill = {block for path in lead_package.on_demand_files(kit)
                 for block in _answering_sections(path, anchors)}
        package = {block for path in lead_package.files(kit)
                   for block in _answering_sections(path, anchors)}
        assert skill, (
            "%s: no section of its lead SKILL names %s -- the value-language rule is not there"
            % (name, " and ".join(anchors)))
        assert package, (
            "%s: no section of the LOADED package (%s) names %s. The lead SKILL is registered, not "
            "injected, so a rule that stands only in it is not in front of the lead when it drafts "
            "the approval" % (name,
                              ", ".join(os.path.basename(p) for p in lead_package.files(kit)),
                              " and ".join(anchors)))
        on_demand[name], loaded[name] = skill, package
    assert set.intersection(*on_demand.values()), (
        "the kits' lead SKILLs share no identical value-language rule -- one copy has drifted: %s"
        % sorted(on_demand))
    assert set.intersection(*loaded.values()), (
        "the kits' loaded lead texts share no identical value-language rule -- one copy has "
        "drifted: %s" % sorted(loaded))
    assert len(on_demand) >= 3, sorted(on_demand)


def test_the_value_language_rule_claims_no_enforcement_it_does_not_have():
    """A round about language honesty may not itself overclaim (BUG-0073, AC-3).

    NOTHING CAN ENFORCE THIS: a value is free text on a command line, no gate reads free text, and
    the kernel folds and prints a value without ever asking which language it is in. A block naming
    the apparatus as its backing would be the failure this repo is built against; a block dropping
    the limit leaves the next reader to assume one. So both halves are asked, with the SAME reader
    the answering rule uses -- `_enforcement_claims`, whose run-up is cut at a clause boundary
    because a fixed window was measured dead against a negation-saturated block (TSK-0089).

    MEASURED RED 2026-08-30 in a clone outside this repo, both shapes an overclaim can take, over
    both surfaces of all three kits -- the numbers are in the round's report.

    THE RESIDUE, because the vocabulary is derived and therefore finite, and it has TWO doors here
    rather than the sister test's one. An overclaim that names no word `_enforcement_words` yields
    passes, measured 2026-08-30 in a clone with the sentence added to all six blocks and the suite
    still green: "The harness refuses a value in the wrong language." and "Die Verfassung erzwingt
    das." The vocabulary is the kit's mechanism names, and those stay English whatever language the
    sentence around them is, so neither door is narrower. The German one is the one this
    round opened by writing a rule about German at all, and it is stated rather than closed: what
    would close it is a vocabulary of CLAIM verbs, which is a second enumeration and a worse one.
    What makes such an edit visible at all is the section pin
    (`test_shortening_net.test_no_section_of_a_pinned_instruction_file_disappears_unnoticed`),
    whose digest over this block then demands a re-pin with a written note -- visibility, not a
    refusal.
    """
    anchors = _value_language_anchors()
    judged = 0
    for kit in _kit_dirs():
        words = _enforcement_words(kit)
        assert words, "%s registers no hooks -- the vocabulary came out empty" % kit
        for path in lead_package.files(kit) + lead_package.on_demand_files(kit):
            for block in _answering_sections(path, anchors):
                judged += 1
                affirmed, negated = _enforcement_claims(block, words)
                assert not affirmed, (
                    "%s/%s: the value-language rule names the enforcement layer without a negation, "
                    "and nothing enforces the language of a free-typed value:\n  %s"
                    % (os.path.basename(kit), os.path.basename(path), "\n  ".join(affirmed)))
                assert negated, (
                    "%s/%s: the value-language rule states no limit at all. A reader then assumes a "
                    "mechanism behind it, and there is none"
                    % (os.path.basename(kit), os.path.basename(path)))
    assert judged >= 6, "only %d rule blocks judged -- the reader stopped finding them" % judged


def _question_tools(kit):
    """The tools this kit registers its user-question guard on, off its own wiring.

    Same derivation as `_settings_command_line_tools`: which tool ASKS THE USER is provider
    knowledge, and the place this repo already writes it down is the registration that puts a guard
    on that event. Reading it here means a provider's second question tool arrives with the rule
    applied rather than with a list to update.
    """
    with io.open(os.path.join(kit, "settings", "settings.json"), encoding="utf-8") as handle:
        settings = json.load(handle)
    found = set()
    for group in settings["hooks"].get("PreToolUse", []):
        if not any(os.path.basename(entry["command"].split()[-1].strip('"')) ==
                   "guard_question_context.py" for entry in group["hooks"]):
            continue
        found.update(part for part in (group.get("matcher") or "").split("|") if part)
    return found


def test_no_role_text_names_a_user_question_tool_its_own_definition_denies():
    """A role told to ask the user must BE able to ask the user (the BUG-0048 shape, one tool over).

    MEASURED on the shipped tree before this round: ONE offender. `records-clerk.md` told the clerk
    to "Relay the printed question VERBATIM with AskUserQuestion" for the FR-0050 correction door,
    and that role's frontmatter grants `Read, Grep, Glob, Bash, Edit, Write` -- no question tool at
    all. A subagent's reply reaches the MANAGER and not the user, so the instruction could not be
    followed by any route: the correction the user is supposed to decide would have been decided by
    a paraphrase, or not at all. Every kit's own constitution says the same thing from the other
    side (one customer-facing role), which is exactly why the contradiction survived reading.

    THE RULE IS "DOES NOT NAME IT", not "does not prescribe it", and that is deliberate over-strict:
    telling a prescription from a description is a judgement about prose, and a text that needs to
    describe the manager's half can say "the manager asks the user" instead. The cost is a wording;
    the alternative is a predicate nobody can measure. The tool set comes from the kit's own
    registration (`_question_tools`) and the grants from the role's frontmatter, so neither end is a
    list in this file.
    """
    judged, offenders = 0, []
    for kit in _kit_dirs():
        tools = _question_tools(kit)
        assert tools, "%s registers no user-question guard at all" % os.path.basename(kit)
        for path in sorted(glob.glob(os.path.join(kit, "agents", "*.md"))):
            role = os.path.basename(path)[:-3]
            front, _body = _role_definition(kit, role)
            granted = {str(name).strip() for name in (front.get("tools") or "").split(",")} \
                if isinstance(front.get("tools"), str) else {str(name) for name
                                                             in (front.get("tools") or [])}
            texts = [path, os.path.join(kit, "skills", role, "SKILL.md")]
            for text_path in texts:
                if not os.path.isfile(text_path):
                    continue
                judged += 1
                with io.open(text_path, encoding="utf-8") as handle:
                    text = handle.read()
                for tool in sorted(tools - granted):
                    if re.search(r"\b%s\b" % re.escape(tool), text):
                        offenders.append("%s/%s: %s names %s"
                                         % (os.path.basename(kit), role,
                                            os.path.basename(text_path), tool))
    assert not offenders, (
        "these role texts name a tool that ASKS THE USER, and the role's own definition grants no "
        "such tool -- a subagent's reply reaches the lead, never the user, so the instruction "
        "cannot be followed by any route. Either grant the tool or route the question through the "
        "lead:\n  %s" % "\n  ".join(sorted(set(offenders))))
    assert judged >= 20, "only %d role texts read -- the walk stopped matching" % judged


def test_the_product_editor_can_research_and_says_what_that_costs():
    """FR-0066: the role responsible for product research gets web access, WITH the honest note.

    THE GAP, live 2026-08-29 in the user's real office project: the new-product process names the
    product editor as responsible for CPU/manufacturer research, and its definition granted no web
    tool at all. The compliance researcher correctly REFUSED the out-of-domain assignment, so the
    task had no owner; the user decided to give the editor web access.

    A WRITING ROLE WITH WEB ACCESS CAN BE STEERED BY WHAT IT READS, so the grant and the note are
    measured together -- a permission widened without the note is the half that would rot first.
    Both halves are read off the shipped artifacts: the grant from the role's own frontmatter, and
    the two gates the note names from the kit's hook directory, so a note that pointed at a gate
    this kit does not ship would be red rather than reassuring.

    WHAT IS NOT MEASURED HERE, and it is the residue the round names rather than hides: that the
    OTHER web-capable writing roles of this kit (compliance-researcher, marketing-planner,
    shop-curator) carry no such note. Making that a property would widen prose the round was not
    asked to touch; it is reported instead, which is why this test pins the role FR-0066 decided
    and does not pretend to a rule the tree does not keep.
    """
    kit = os.path.join(TEAM_KITS, "office-team")
    front, body = _role_definition(kit, "product-editor")
    granted = {name.strip() for name in str(front.get("tools") or "").split(",")}
    assert {"WebSearch", "WebFetch"} <= granted, granted

    # the CONTAINED half and the NOT-contained half, each named
    assert "gate_second_reading" in body and "gate_write_scope" in body, body
    assert "NOT CONTAINED" in body, (
        "the role gained web access without the sentence that says what is not contained by it")
    for gate in ("gate_second_reading", "gate_write_scope"):
        assert os.path.isfile(os.path.join(kit, "hooks", gate + ".py")), (
            "the note points at %s and this kit does not ship it" % gate)


def test_the_product_designer_can_look_at_its_own_draft_and_says_what_that_costs():
    """BUG-0076: the role that must SIGHT a draft gets the tool that renders it, WITH the note.

    THE GAP, live 2026-08-30 in the user's real project: a design revision reached the user twice
    unrendered, and the designer could not have rendered it even if told to -- its definition
    granted `Read, Edit, Write, Grep, Glob`, no command-running tool at all, which its own skill
    stated as the reason the PM runs every kernel command for it.

    THE GRANT AND ITS PRICE ARE MEASURED TOGETHER, because a permission widened without the note is
    the half that rots first (the same shape as `test_the_product_editor_can_research_and_says_what
    _that_costs` one role over). Two consequences, both read off the shipped tree rather than
    asserted in prose: the containment that DOES hold is named and its gates exist in this kit, and
    the kernel's own `hand_back` answer for the role flips to `self` -- so the entry point is
    reachable from the designer's session, and "the PM freezes, never you" is a rule with nothing
    behind it. The skill has to say that in the sentence that used to derive it from the toolset.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import dispatch
    kit = os.path.join(TEAM_KITS, "dev-team")
    front, body = _role_definition(kit, "product-designer")
    granted = {name.strip() for name in str(front.get("tools") or "").split(",")}
    assert "Bash" in granted, granted
    assert {"Read", "Write"} <= granted, (
        "the sighting role also needs the tool that DISPLAYS an image; a render nobody opens is "
        "worse than none")

    assert "NOT CONTAINED" in body, (
        "the role gained a command line without the sentence that says what is not contained by it")
    for gate in ("gate_write_scope", "gate_git", "gate_push_token", "gate_shell_hygiene",
                 "gate_design_sighted"):
        assert gate in body, gate
        assert os.path.isfile(os.path.join(kit, "hooks", gate + ".py")), (
            "the note points at %s and this kit does not ship it" % gate)
    # THE HALF THE FIRST CUT GOT BACKWARDS, and it is the reason this assertion exists rather than
    # only the one above: the note said `gate_write_scope` "keeps your writes inside your task's
    # allowed_scope", full stop. Measured by a verifier as a bound subagent through all eight
    # registered shell gates: the Write TOOL onto `src/app.py` is rc 2, and `echo x > src/app.py`,
    # `sed -i`, `cp` and `python -c open(...)` are all rc 0. The role whose own text says it NEVER
    # writes production code could do exactly that from its new shell, while its note said it
    # could not. The kit's `ENFORCEMENT.md` already named that residue correctly, so the note has
    # to point there instead of summarising it a second time (house rule: a quotation nothing
    # checks is a claim that rots).
    assert "keeps your writes inside" not in body, (
        "the containment note is back to claiming a scope binding that a shell line does not have")
    assert "ENFORCEMENT.md" in body, (
        "the note bounds a shell without pointing at the table that states each gate's real reach")

    assert dispatch.hand_back_path(os.path.join(kit, "agents"), "product-designer") == \
        dispatch.HAND_BACK_SELF
    with io.open(os.path.join(kit, "skills", "product-designer", "SKILL.md"),
                 encoding="utf-8") as handle:
        skill = handle.read()
    assert "grants no command-running tool" not in skill, (
        "the skill still derives 'the PM runs the freeze' from a toolset that now runs commands -- "
        "the rule is fine, the reason is false")
    assert "hand_back: self" in skill or "hand_back: self" in body


# ================ 7. the route that WRITES a kit document, and who is told it (BUG-0075)
def _installed(kit, root):
    """`kit`'s shipped template tree as an installed project at `root`.

    The tree a role really faces after the scaffold, so every question below is asked of files that
    exist rather than of names: `documents.accepts` reads the FILE, and a predicate answered against
    a path that is not there answers about nothing.
    """
    shutil.copytree(os.path.join(kit, "templates", "project_memory"), root)
    return root


def _writable_documents(root):
    """Every path in an installed project that `apply-proposal` would WRITE.

    THE PREDICATE IS THE COMMAND'S OWN. `documents.accepts` is what `layout.partial_writers` asks
    before a refusal names the route, and it reads the file: a document has to parse as a YAML
    mapping to be compared at all. So the prose documents drop out here without a suffix or a name
    appearing anywhere in this file, which is the half that carries the weight -- a role sent at
    `apply-proposal` for a document the command refuses is BUG-0041's dead end pointed the other
    way (`test_no_document_owner_is_routed_at_one_the_command_would_refuse`).
    """
    from kernel import documents
    found = []
    for dirpath, _dirs, files in os.walk(root):
        rel = os.path.relpath(dirpath, root).replace("\\", "/")
        for name in files:
            at = name if rel == "." else "%s/%s" % (rel, name)
            if documents.accepts(root, at):
                found.append(at)
    return sorted(found)


def _split_row(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _ownership_table(kit, root):
    """[(cells, owner column index)] of the constitution table that assigns CONTENT to a role.

    FOUND BY TWO PROPERTIES AND NOT BY A SECTION NUMBER: its header names an OWNER column, and its
    rows name at least one file the INSTALLED project really has. BUG-0075's occasion is §6 in all
    three kits, and the number is exactly the thing that rots when a constitution grows a section.
    The second property is not decoration: a constitution can carry a SECOND table with an `Owner`
    column -- the dev and research work-loop tables do, office's does not -- and that kind assigns a
    STEP to a role rather than a file to one, which is visible in the rows themselves: they name no
    file the project holds. Exactly one table may match, so none and two are one answer here:
    unreadable, and said so.

    THE THREE TABLES DO NOT RHYME, which is why nothing below reads a fixed column count: office
    writes its owners in plain text and the other two in bold, and one research row carries three
    cells where the header declares two. Reading the owner by its HEADER index, with the last cell
    as the fallback, is what survives that.
    """
    path = os.path.join(kit, "constitution", "AGENTS.md")
    with io.open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    tables, current = [], []
    for line in lines + [""]:
        if line.strip().startswith("|"):
            current.append(line)
            continue
        if current:
            tables.append(current)
        current = []
    found = []
    for table in tables:
        if len(table) < 3:
            continue
        header = _split_row(table[0])
        columns = [index for index, cell in enumerate(header) if re.search(r"owner", cell, re.I)]
        if not columns:
            continue
        rows = [(_split_row(line), min(columns[0], len(_split_row(line)) - 1))
                for line in table[2:]]
        if any(os.path.isfile(os.path.join(root, *span.split("/")))
               for cells, owner_index in rows
               for index, cell in enumerate(cells) if index != owner_index
               for span in _BACKTICKED_RX.findall(cell)):
            found.append(rows)
    assert len(found) == 1, (
        "%s: %d of its constitution tables name an OWNER column over rows that name a file this "
        "project has -- the ownership table is found by those two properties, so none and two are "
        "the same answer: unreadable" % (os.path.basename(kit), len(found)))
    return found[0]


def _role_aliases(kit):
    """{role: [word set, ...]} -- every spelling a role of `kit` answers to, off its own frontmatter.

    TWO SOURCES, BOTH THE ROLE'S OWN: the file name the provider spawns it by, and the `Keywords:`
    tail its `description` ends with. The ownership tables call the same role `Bookkeeper`,
    `Records-Clerk` and -- in two kits -- `PM`, and the last of those is in no file name while it is
    in both project managers' keyword lists.

    THE FREE PROSE OF A DESCRIPTION IS DELIBERATELY NOT READ: dev's architect describes itself as
    "invoked by the Project Manager", so a reader that searched the whole description would hand
    every dev document a second owner. What is read is the two places a role NAMES itself.
    """
    import yaml
    aliases = {}
    for path in sorted(glob.glob(os.path.join(kit, "agents", "*.md"))):
        role = os.path.basename(path)[:-3]
        with io.open(path, encoding="utf-8") as handle:
            text = handle.read()
        end = text.find("\n---", 3)
        front = yaml.safe_load(text[3:end]) or {}
        spellings = [set(role.replace("-", " ").split())]
        keywords = re.search(r"Keywords:\s*(.*)$", str(front.get("description") or ""), re.S)
        for word in (keywords.group(1).split(",") if keywords else []):
            cleaned = set(re.sub(r"[^a-z0-9]+", " ", word.lower()).split())
            if cleaned:
                spellings.append(cleaned)
        aliases[role] = spellings
    return aliases


def _owner_roles(kit, cell):
    """[(token, [role, ...])] for every owner an ownership cell names.

    A cell can name more than one role -- research partitions one row between two -- so the split is
    on the separators the tables use and each token is resolved on its own. A token matches a role
    when its words are contained in one of that role's own spellings, which is what lets `Manager`
    reach `office-manager` without a mapping table standing here.
    """
    aliases = _role_aliases(kit)
    plain = re.sub(r"\(.*?\)", " ", re.sub(r"[*`]", " ", cell))
    resolved = []
    for token in re.split(r"[/,·]|\band\b", plain):
        words = set(re.sub(r"[^a-z0-9]+", " ", token.lower()).split())
        if not words:
            continue
        resolved.append((token.strip(),
                         sorted(role for role, spellings in aliases.items()
                                if any(words <= spelling for spelling in spellings))))
    return resolved


def _document_owners(kit, root, writable=None):
    """{role: [document, ...]} -- who owns which WRITABLE kit document, off the constitution.

    A row's documents are the backticked spans of its non-owner cells that name a document
    `apply-proposal` would write. A row naming none is not about this route and never reaches the
    owner side, so a prose document drops out where it stands -- office's first row names the
    masterplan beside two writable documents -- without being excluded anywhere. And a document a
    kit stops shipping takes its row's duty with it, which is AC-1's second direction at the source.

    `writable` is a parameter only so a caller that already walked the project does not walk it
    twice; the answer is the same either way.
    """
    writable = set(_writable_documents(root) if writable is None else writable)
    owned = {}
    for cells, owner_index in _ownership_table(kit, root):
        named = sorted({span for index, cell in enumerate(cells) if index != owner_index
                        for span in _BACKTICKED_RX.findall(cell)} & writable)
        if not named:
            continue
        for token, roles in _owner_roles(kit, cells[owner_index]):
            assert len(roles) == 1, (
                "%s: the ownership row for %s calls its owner %r, and that resolves to %s. The "
                "table and the shipped role files have drifted apart -- one of the two moved"
                % (os.path.basename(kit), ", ".join(named), token, roles or "no role at all"))
            owned.setdefault(roles[0], set()).update(named)
    return {role: sorted(documents) for role, documents in owned.items()}


def _staged_spelling(root):
    """`staging/<TSK-ID>/` as the KERNEL spells it when it refuses something that is not a proposal.

    READ OUT OF THE REFUSAL rather than typed here: that message is what a role meets when it stages
    in the wrong place, so the shape the role texts are held to below is the shape the command
    itself names. A renamed proposal area or a re-worded placeholder moves this reader with it.
    """
    from kernel import documents
    from kernel.state import ProjectState
    try:
        documents.proposal_path(ProjectState(root), "not-a-proposal")
    except documents.DocumentError as exc:
        found = re.search(r"`([^`]*/<[^`>]+>/)<[a-z]+>`", str(exc))
        assert found, "the refusal no longer spells the proposal position: %s" % exc
        return found.group(1)
    raise AssertionError("the kernel took a bare word for a staged proposal")


def _bullets(body):
    """The top-level bullets of a role definition, one reading view each.

    THE BULLET IS THE UNIT and not the paragraph: these files write their whole body as one
    unseparated list, so a paragraph-sized window is the entire role definition and every question
    about "what the route block says" would be answered by the rest of the text.
    """
    return [_reading_view(chunk) for chunk in re.split(r"(?m)^(?=-\s)", body)
            if chunk.lstrip().startswith("- ")]


def _route_bullets(kit, role):
    from kernel import documents
    _front, body = _role_definition(kit, role)
    return [bullet for bullet in _bullets(body) if ("`%s`" % documents.COMMAND) in bullet]


def test_every_role_that_owns_a_kit_document_carries_the_route_that_writes_it(tmp_path):
    """AC-1/AC-4 of BUG-0075: knowing the route is a PROPERTY of owning a document, in every kit.

    THE DEFECT, live on 2026-08-30 in the user's real office project one day after `apply-proposal`
    shipped: the product editor reworked a content rule, staged it as PROSE under a NEW name in
    `staging/<TSK>/claims_policy.proposed.md`, and told the user to paste it into
    `content_guidelines.yaml` by hand -- a second authority beside the kit document, and the dead end
    BUG-0071 had closed the day before. Of the roles that own a document in §6, most had never heard
    of the command in their own definition; the one that had carried it inside a paragraph about web
    content, where it reads as a warning rather than as "this is how you write your document".

    BOTH ENDS ARE DERIVED, which is what makes this a property rather than a list. The owners come
    from the constitution's own ownership table crossed with `documents.accepts`, so a role that
    stops owning a document stops owing the route on the same day, and a document a kit stops
    shipping takes its duty with it. What the route must SAY is derived too:

      * the staged file for every document it owns, spelled `staging/<TSK-ID>/<the document's own
        name>` -- which is the live case's defect stated mechanically. It gives a role that names
        the file it must stage no OCCASION to invent a second one beside it; it does not make that
        impossible, and the limit is the last paragraph here.
      * NO staged file for a document it does not own, so the route cannot be copied around.
      * every OTHER command `layout.partial_writers` names for those documents. `apply-proposal`
        refuses a change at a field a named writer owns (`documents._owned_elsewhere`), so a route
        that named only this command would send the filing clerk at a refusal for the one part of
        the plan it most wants to change.

    AND TWO DIRECTIONS BACK, on every role and every document of every kit: a definition that names
    the command while the table gives it no writable document is an offender -- that is the day a
    role's ownership moved and its text did not -- and so is a document the command WOULD write that
    the table gives no owner, because then the route is owed to nobody and the next role to touch
    that file is back where the live case started.

    MEASURED RED against the shipped tree on 2026-08-30, before any role file was touched -- the
    numbers are in the round's report, not here.

    WHAT THIS CANNOT DO: it reads prose, so it cannot tell a good instruction from a bad one, and
    what it reads of the route are the names -- a staged file whose path carries no `staging/`
    prefix is invisible to it. Those limits and the two beside them are one entry in
    `docs/POST_V2_WISHLIST.md`. What it holds is the two ends: who owes the route, and which files
    and commands the route names. That the SHAPE behind those names is stated once and does not
    drift is the sibling test `test_the_document_route_is_one_text_wherever_it_stands`.
    """
    from kernel import documents, layout
    per_kit, offenders, judged = {}, [], 0
    for kit in _kit_dirs():
        name = os.path.basename(kit)
        root = _installed(kit, str(tmp_path / name / "project_memory"))
        writable = _writable_documents(root)
        owners = _document_owners(kit, root, writable)
        staged = _staged_spelling(root)
        per_kit[name] = owners
        # THE DOCUMENT SIDE OF THE SAME PROPERTY. A document the command would write and the table
        # names no owner for is a route owed to nobody: the next role that needs it is exactly where
        # the live case started, and every check below would pass while saying nothing about it.
        orphans = sorted(set(writable) - {one for owned in owners.values() for one in owned})
        if orphans:
            offenders.append(
                "%s: %s would be written by `%s` and the ownership table names no owner for it, so "
                "no role is told the route" % (name, ", ".join(orphans), documents.COMMAND))
        for path in sorted(glob.glob(os.path.join(kit, "agents", "*.md"))):
            role = os.path.basename(path)[:-3]
            owned, route = owners.get(role, []), _route_bullets(kit, role)
            where = "%s/%s" % (name, role)
            if not owned:
                # THE WHOLE DEFINITION AND NOT ITS BULLETS, and only on this side. A role that owns
                # nothing may not carry the route ANYWHERE in its text, so reading only the bullets
                # would leave the same sentence in a heading or a closing paragraph unseen. On the
                # owner's side the bullet is the unit, because there the question is what one block
                # says (`_bullets`).
                _front, body = _role_definition(kit, role)
                if ("`%s`" % documents.COMMAND) in _reading_view(body):
                    offenders.append(
                        "%s: its definition names `%s` and the ownership table gives it no document "
                        "the command would write" % (where, documents.COMMAND))
                continue
            judged += 1
            if len(route) != 1:
                offenders.append(
                    "%s: owns %s, and %d of its bullets name `%s` -- the route is missing or it is "
                    "said twice" % (where, ", ".join(owned), len(route), documents.COMMAND))
                continue
            block, wanted = route[0], {"%s%s" % (staged, one) for one in owned}
            absent = sorted(one for one in wanted if ("`%s`" % one) not in block)
            if absent:
                offenders.append("%s: its route names no staged file for %s"
                                 % (where, ", ".join(absent)))
            # A span that IS the proposal area and names no file in it is prose about the route, not
            # a second document staged into it -- the reason this compares against the prefix and
            # then requires something behind it.
            stray = sorted(span for span in _BACKTICKED_RX.findall(block)
                           if span.startswith(staged) and span != staged and span not in wanted)
            if stray:
                offenders.append("%s: its route stages %s, which this role does not own"
                                 % (where, ", ".join(stray)))
            for document in owned:
                for entry in layout.partial_writers(document, root):
                    if ("`%s`" % entry["command"]) not in block:
                        offenders.append(
                            "%s: `%s` writes part of %s (%s) and the route does not name it, so the "
                            "role meets a refusal there"
                            % (where, entry["command"], document, entry["field"]))
    assert not offenders, (
        "a role that OWNS a kit document must be told, in its own definition, how that document is "
        "written -- and no other role may carry that route (BUG-0075):\n  %s"
        % "\n  ".join(offenders))
    assert len(per_kit) >= 3 and all(per_kit.values()), (
        "a kit contributed no document owner at all -- the derivation stopped matching: %s" % per_kit)
    # A floor under everything above, which is vacuous over an empty owner set. It sits well under
    # the tree's stand rather than at it: a renamed role must not trip it, and a derivation that
    # collapsed to one owner per kit must not pass.
    assert judged >= 6, sorted(per_kit.items())


def test_the_document_route_is_one_text_wherever_it_stands(tmp_path):
    """AC-2 of BUG-0075: the SHAPE is written once, identically, because nothing can derive it.

    WHAT THE SIBLING TEST CANNOT ASK. That a proposal must be the WHOLE document as it should stand,
    that it must still parse, that a new file beside a kit document is not a proposal, and that what
    the command refuses stays the user's own editor step -- none of those is a name a reader can
    look up. They are prose. What can be measured is that they are ONE prose: role definitions are
    per-kit files and no `KIT_SPECIFIC` mechanism covers them, so an identical block IS the mirror
    here, exactly as it is for the two lead rules above.

    WHAT IS COMPARED IS THE RUN-UP, and it is a comparison of EQUALS rather than an intersection.
    Every route bullet is cut at its first sentence that names a staged file -- everything before
    that is the shape, everything from there on is this role's own business (which documents it
    stages, who runs the command for it, which field of its document another writer owns). Those
    run-ups have to be one text.

    THE INTERSECTION IT REPLACED WAS TOO WEAK, and that was measured rather than reasoned. This test
    first asked "the bullets share at least one sentence". In the round's own clone one claim of the
    shape was then reworded in ONE kit -- "a new file beside a kit document is fine" -- and all
    three tests stayed green: the other sentences were still shared and the floor still held. Cut at
    the staged file and compared as equals, that same mutation is red.

    A SIDE EFFECT WORTH HAVING: the shape therefore stands FIRST in every route bullet, before the
    file names. A reader who stops early has read the rule and not the list.

    MEASURED RED against the shipped tree on 2026-08-30: most owners named the command nowhere, and
    the definitions that did name it carried no run-up like this. The counts are in the report.

    THE RESIDUE, stated rather than discovered: one text that says the WRONG thing in every owner's
    definition passes this. It is the same residue the answering rule and the value-language rule
    carry, and the same answer -- what makes such an edit visible is that it has to be made in every
    one of them at once, and that the section pin watches the lead files among them.
    """
    from kernel import documents
    run_ups = {}
    for kit in _kit_dirs():
        name = os.path.basename(kit)
        root = _installed(kit, str(tmp_path / name / "project_memory"))
        staged = _staged_spelling(root)
        for role in sorted(_document_owners(kit, root)):
            route = _route_bullets(kit, role)
            assert len(route) == 1, (
                "%s/%s owns a kit document and %d of its bullets name `%s`"
                % (name, role, len(route), documents.COMMAND))
            sentences = _SENTENCE_SPLIT_RX.split(route[0])
            names_a_file = [index for index, one in enumerate(sentences) if staged in one]
            assert names_a_file, (
                "%s/%s: its route bullet names no staged file at all" % (name, role))
            run_ups["%s/%s" % (name, role)] = " ".join(sentences[:names_a_file[0]])
    assert len(run_ups) >= 6, sorted(run_ups)
    distinct = sorted(set(run_ups.values()))
    if len(distinct) > 1:
        # WHERE THE TEXTS PART, not their first 160 characters: the drift this catches is a reworded
        # claim in the MIDDLE of a shared paragraph, and a head-of-string excerpt of two such texts
        # is the same excerpt twice -- measured while writing this test.
        parted = next((position for position in range(min(len(one) for one in distinct))
                       if len({one[position] for one in distinct}) > 1),
                      min(len(one) for one in distinct))
        raise AssertionError(
            "the document route is written %d different ways across %d owners, so the shape will "
            "drift one file at a time. They agree up to %d characters and then read:\n  %s"
            % (len(distinct), len(run_ups), parted,
               "\n  ".join("%s\n    ...%s" % (
                   ", ".join(sorted(role for role, text in run_ups.items() if text == one)),
                   one[parted:parted + 120]) for one in distinct)))
    text = distinct[0]
    assert ("`%s`" % documents.COMMAND) in text, (
        "the shared part of the route does not name `%s`; what the roles have in common is prose "
        "around the command rather than the route itself" % documents.COMMAND)
    # A floor under the shared run-up, so "one text" cannot be bought by making it one clause. The
    # shape is four claims -- the whole document, its own name, still parseable, and what the
    # command refuses -- and none of them fits in a sentence fragment.
    assert len(text) >= 300, text


def test_no_document_owner_is_routed_at_one_the_command_would_refuse(tmp_path):
    """The other failure form, and it is BUG-0041's: a route named where the command says no.

    THE KITS SHIP PROSE DOCUMENTS WITH OWNERS IN THE SAME TABLE -- `product/masterplan.md` stands in
    every kit's first row -- and `apply-proposal` writes no document it cannot COMPARE. A role told
    to stage one of those would meet a refusal about the file's shape with nothing behind it, which
    is the dead end this whole line of work exists to end, arriving from the other side.

    SO TWO THINGS ARE ASKED, and the first is what keeps the second from being vacuous: every kit's
    ownership table must still NAME at least one document the command refuses (otherwise this test
    is judging an empty set and should say so), and no such document may reach an owner's list or a
    route bullet's staged files.
    """
    from kernel import documents
    for kit in _kit_dirs():
        name = os.path.basename(kit)
        root = _installed(kit, str(tmp_path / name / "project_memory"))
        writable, staged = set(_writable_documents(root)), _staged_spelling(root)
        named = {span for cells, owner_index in _ownership_table(kit, root)
                 for index, cell in enumerate(cells) if index != owner_index
                 for span in _BACKTICKED_RX.findall(cell)}
        refused = sorted(span for span in named - writable
                         if os.path.isfile(os.path.join(root, *span.split("/"))))
        assert refused, (
            "%s: its ownership table names no document `%s` would refuse, so this check judged "
            "nothing" % (name, documents.COMMAND))
        owners = _document_owners(kit, root)
        for role, owned in sorted(owners.items()):
            assert not set(owned) & set(refused), (name, role, owned, refused)
            for block in _route_bullets(kit, role):
                for one in refused:
                    assert ("`%s%s`" % (staged, one)) not in block, (
                        "%s/%s is told to stage %s, and `%s` refuses that document -- it is not a "
                        "YAML mapping this command can compare"
                        % (name, role, one, documents.COMMAND))


# ---------------------------------------------------------------------------------------------
# FR-0064 / FR-0057 / FR-0007 (TSK-0105): which roles must read FRESH, what a verdict role says
# about the scope of its runs, and which constitution paragraphs are ONE text across the kits.
# ---------------------------------------------------------------------------------------------

def _verdict_roles(kit):
    """The roles `gate_subagent_output` demands a `verdict:` from, read off the constant the
    shipped hook decides on -- the part that runs, not a name list kept here."""
    path = os.path.join(kit, "hooks", "gate_subagent_output.py")
    with io.open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "VERDICT_ROLES"
                for target in node.targets):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("%s decides on no VERDICT_ROLES constant" % path)


def _four_eyes_writers():
    """Every role a kernel schema names as `writer_role`: the record it writes is what another run
    or another role is judged against (the filing and booking loops), so its reading has to be its
    own. Read off the schemas, which is where the loops are defined."""
    import yaml
    out = set()
    for path in glob.glob(os.path.join(TEAM_KITS, "kernel", "schemas", "*.yaml")):
        with io.open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if isinstance(data, dict) and data.get("writer_role"):
            out.add(str(data["writer_role"]))
    return out


def test_no_role_whose_reading_must_be_fresh_carries_a_craft_memory():
    """A role that judges, or reads for a four-eyes gate, starts every run with nothing (FR-0064).

    WHICH ROLES, derived twice from running code and never listed: the verdict roles
    `gate_subagent_output` demands a `verdict:` from, and the `writer_role` of every kernel schema
    -- the roles whose record a gate counts per run or a second role judges. A role memory is
    loaded at the start of every run of that role, so for these it is a channel from the last run
    into the next one: a verdict that remembers the last round's clearances is not a fresh reading,
    and a bookkeeper's second reading is a second run of the SAME role.

    MEASURED, both halves. In a real project on the shipped dev kit the quality-engineer's memory
    held eleven topics, three of them gating decisions (how to re-gate a fix round, when a green
    static check is overruled by the page). And the office channel was measured OPEN on the
    shipped hooks: a bookkeeper memory note carrying a document's figures (gross, net, VAT, the
    invoice number) passed every one of the six `Write`-registered hook stages of the office
    settings at rc 0, key or no key -- the budget guard refuses an item id in such a note and
    nothing about figures. The key is what turns the platform's loading on, so the key is what
    this test holds; the write side stays open and is H105's named remainder.

    What it cannot see: a memory tree an OLDER kit version wrote for such a role -- no installer,
    no scaffold and no kernel path names `agent-memory`, so an update takes the key and leaves
    the tree (H105 b) -- and whether the platform loads such a tree without the key, which is
    outside the shipped tree and unmeasured.
    """
    import gen_provider_artifacts
    writers = _four_eyes_writers()
    judged, offenders = {"verdict": [], "four-eyes": []}, []
    for kit in _kit_dirs():
        verdict = set(_verdict_roles(kit))
        for role in sorted(verdict | writers):
            if not os.path.isfile(os.path.join(kit, "agents", role + ".md")):
                continue
            front, body = _role_definition(kit, role)
            name = "%s/%s" % (os.path.basename(kit), role)
            judged["verdict" if role in verdict else "four-eyes"].append(name)
            if front.get(gen_provider_artifacts.MEMORY_FRONTMATTER_KEY):
                offenders.append("%s carries `%s:`" % (
                    name, gen_provider_artifacts.MEMORY_FRONTMATTER_KEY))
            if gen_provider_artifacts.MEMORY_DUTY_RX.search(_reading_view(body)):
                offenders.append("%s is told to consult a memory" % name)
    assert not offenders, (
        "these roles judge or read for a four-eyes gate and still carry state from their last "
        "run into the next:\n  " + "\n  ".join(offenders))
    # both sources have to have contributed a shipped role, or one of the two readers has
    # stopped reading and the assertion above judged half the subject
    for source, names in judged.items():
        assert names, "no shipped role came out of the %s source -- its reader found nothing" % source


# The two halves of the scope a verdict role owes (DEC-0050, FR-0057): the AFFECTED tests while
# the round is open, and the FULL run ONCE before the verdict. Read as words because the subject
# is the text the role receives; what the role then does is measured by nobody here.
_AFFECTED_RX = re.compile(r"\baffected\b", re.IGNORECASE)
_FULL_ONCE_RX = re.compile(r"\bfull\b.{0,200}?\bonce\b|\bonce\b.{0,200}?\bfull\b", re.IGNORECASE)


def _do_section(path):
    """The `## Do` section of a skill, as it reads."""
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    blocks = [block for block in _markdown_sections(text) if block.startswith("## Do")]
    assert len(blocks) == 1, (path, len(blocks))
    return _reading_view(blocks[0])


def test_every_verdict_role_states_the_scope_of_its_runs():
    """The verdict roles carry DEC-0050's measure where they act, in both texts they receive.

    FR-0057 measured the gap: the quality-engineer's description said `run the tests` -- no
    scope, no moment -- and the skill's staged-testing line stood alone, so the description a
    session reads at the spawn and the procedure it opens later disagreed about what a gate
    costs. What is held here is the SPLIT itself, in the description (frontmatter, parsed) and in
    the procedure's `## Do` section: the affected tests while the round is open, the full run
    once before the verdict. A role that names only one half has a rule with no other end.

    MEASURED where it acts, in a real project on the shipped kit: a re-gate after a fix round ran
    fifteen instruments and the full pipeline exactly once (141 s), and the developers' own
    verification runs stayed on the affected stack (`quality.py --only liquid`) -- so the text is
    holding what the roles already do, and the explosion FR-0057 feared has a rule against it in
    the place a session reads first. Not seen here: whether a run obeyed; no gate reads a run's
    scope, and that limit stands in the hole list.
    """
    judged, offenders = [], []
    for kit in _kit_dirs():
        for role in _verdict_roles(kit):
            if not os.path.isfile(os.path.join(kit, "agents", role + ".md")):
                continue
            front, _body = _role_definition(kit, role)
            texts = {"description": _reading_view(str(front.get("description", ""))),
                     "skill `## Do`": _do_section(os.path.join(kit, "skills", role, "SKILL.md"))}
            for label, text in texts.items():
                judged.append("%s/%s %s" % (os.path.basename(kit), role, label))
                missing = [name for name, pattern in (("affected", _AFFECTED_RX),
                                                      ("full ... once", _FULL_ONCE_RX))
                           if not pattern.search(text)]
                if missing:
                    offenders.append("%s/%s %s lacks %s" % (
                        os.path.basename(kit), role, label, ", ".join(missing)))
    assert not offenders, "\n  ".join(["a verdict role names only half of its scope:"] + offenders)
    assert len(judged) >= 4, judged


# A paragraph the constitutions SHARE is one text in all three, or this table says why it is
# not. The rule is a definition -- a bold lead-in that opens a paragraph in AT LEAST TWO of the
# constitutions marks shared text, and shared text stands in all three, byte-identical -- and this
# is its exception list, each entry with the reason, measured at both ends by the test below: an
# entry whose paragraph has become identical in all three is dead, and one whose lead-in opens a
# paragraph in fewer than two files never needed to be here. Two kinds of reason live here: a
# paragraph the three kits carry in kit-specific wording, and one only two kits carry as a
# paragraph of its own.
KIT_SPECIFIC_PARAGRAPHS = {
    "**A dispatch does not survive a session end**":
        "names the kit's own lead title (lead / manager) in the relay sentence",
    "**READ**":
        "the work-loop list is one block, and each kit's loop names its own items and roles",
    "**Single source of truth.**":
        "the hard-enforcement list is one block, and each kit lists its own directories and gates",
    "**WHO BOOKS THAT ENVELOPE IN depends on your toolset, and your dispatch header says "
    "which path is yours**":
        "names the kit's own lead title (lead / manager)",
    "**Your procedure document is NOT in your context.**":
        "names the kit's own lead skill",
    "**A place you name is a place you wrote to.**":
        "office carries the same rule inline in its one-paragraph Behavior section, not as a "
        "paragraph of its own",
    "**Presets are MECHANICAL**":
        "office carries the preset rule inline in its Models & presets paragraph",
    "**This local constitution is AUTHORITATIVE for this repository**":
        "office spells the lead-in with the full stop inside the bold, and the section 0 block "
        "is kit-specific in every kit",
    "**Two-level acceptance:**":
        "office has no two-level acceptance -- its unit of approval is the PROC",
    "**User = customer**":
        "office describes its roles in section 5 in its own shape",
    "**ONE question for the whole plan, not one per goal (`DEC-0068`).**":
        "the office kit has no plan approval to describe: `approvals.plan_goals` reads the "
        "product roots out of `ROOT_TYPE_BY_KIT`, which names PR and RQ and no office type, "
        "so a PROC can never be covered by one -- measured in the TSK-0120 merge round",
}

_LEAD_IN_RX = re.compile(r"\A\s*(?:[-*]\s+|\d+\.\s+)?(\*\*[^*\n]+?\*\*)")


def _paragraphs_by_lead_in(path):
    """{bold lead-in: paragraph} for every blank-line-separated block that opens with one.

    THE FIRST OCCURRENCE PER FILE is the one kept. No constitution opens two paragraphs with the
    same lead-in today; if one did, the second would be invisible here, and that is a limit of
    this reader rather than a rule about the text.
    """
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    out = {}
    for block in re.split(r"\n[ \t]*\n", text):
        found = _LEAD_IN_RX.match(block)
        if found:
            out.setdefault(found.group(1), block.strip("\n"))
    return out


def test_a_paragraph_the_constitutions_share_is_one_text():
    """Shared constitution text stands in ALL kits, byte-identical, as the mirrored hooks do.

    THE SUBJECT IS DERIVED: a paragraph that opens with the same bold lead-in in at least two
    constitutions is shared text, and shared text drifts one file at a time -- the report-gap
    duty (FR-0062) stood in the office constitution alone for one release while the other two
    named the command in their surface list and sent nobody to it, and the comment rule
    (FR-0007) is three copies of one paragraph by construction. `KIT_SPECIFIC_PARAGRAPHS` names
    the shared lead-ins that legitimately differ or legitimately stop at two kits, with the
    reason, and both of ITS ends are measured here too.

    WHY "AT LEAST TWO" AND NOT "ALL THREE" -- the verifier's measurement (TSK-0105, mut/m4): with
    "all three" as the subject, deleting a shared paragraph from ONE kit removed it from the
    subject instead of failing it, and the only thing that noticed was a floor on the number of
    shared lead-ins -- a count that grows, so inserting one more shared paragraph and deleting
    the comment rule from office left the test green. A paragraph two kits open the same way is
    the property; the third kit's copy is what is held.
    """
    kits = _kit_dirs()
    per_kit = {os.path.basename(kit): _paragraphs_by_lead_in(
        os.path.join(kit, "constitution", "AGENTS.md")) for kit in kits}
    carriers = {}
    for kit, paragraphs in per_kit.items():
        for lead in paragraphs:
            carriers.setdefault(lead, set()).add(kit)
    shared = {lead for lead, kits_with_it in carriers.items() if len(kits_with_it) >= 2}
    assert shared, "no two constitutions share a bold lead-in, so this test judged nothing"
    never_needed = [lead for lead in KIT_SPECIFIC_PARAGRAPHS if lead not in shared]
    assert not never_needed, (
        "these exceptions name a lead-in that opens a paragraph in fewer than two constitutions: %s"
        % never_needed)
    missing, drifted, identical_exceptions = [], [], []
    for lead in sorted(shared):
        bodies = {kit: per_kit[kit][lead] for kit in carriers[lead]}
        everywhere = carriers[lead] == set(per_kit)
        one_text = len(set(bodies.values())) == 1
        if lead in KIT_SPECIFIC_PARAGRAPHS:
            if everywhere and one_text:
                identical_exceptions.append(lead)
            continue
        if not everywhere:
            missing.append("%s stands in %s and not in %s" % (
                lead, ", ".join(sorted(carriers[lead])),
                ", ".join(sorted(set(per_kit) - carriers[lead]))))
            continue
        if not one_text:
            parted = next((position for position in range(min(map(len, bodies.values())))
                           if len({body[position] for body in bodies.values()}) > 1),
                          min(map(len, bodies.values())))
            drifted.append("%s -- the copies agree up to %d characters, then read:\n    %s" % (
                lead, parted, "\n    ".join("%s: ...%s" % (kit, body[parted:parted + 100])
                                            for kit, body in sorted(bodies.items()))))
    assert not identical_exceptions, (
        "these exceptions are dead: the paragraph is one text in all three kits now: %s"
        % identical_exceptions)
    assert not missing, "\n  ".join(
        ["shared constitution text is absent from a kit and no exception says why:"] + missing)
    assert not drifted, "\n  ".join(["shared constitution text differs between kits:"] + drifted)


# ================== 8. the two duties DEC-0095 put into the texts (PR-0011 AC-3)

_READING_DUTY_LEAD_IN = "**READ THE END OF A LOG, NEVER THE LOG"


def _scope_manifest_fields():
    """The fields a scope approval really hashes -- read out of the kernel that hashes them."""
    sys.path.insert(0, TEAM_KITS)
    from kernel import approvals
    return set(approvals._SCOPE_FIELDS)


def test_no_kit_text_puts_an_artifact_into_the_scope_manifest_the_kernel_does_not_hash():
    """BUG-0077: the PM skill required the approved WIREFRAME to be part of the scope manifest
    while `gate_dispatch` refused the designer spawn that would draw it until the scope approval
    existed -- two duties a project cannot satisfy at once, hit live at Canyon's first UI goal.

    The wireframe was never in the manifest either (`approvals._SCOPE_FIELDS` holds no reference to
    one, which is BUG-0055's subject), so the text asked for something that could not be produced
    AND could not have been carried if it had been.

    THE CHECK IS THE PAIR, and the kernel is the authority: whatever a kit text names as belonging
    to the scope manifest must be a field the kernel actually hashes. The artifact vocabulary is
    derived from the kit's own freeze commands rather than typed here, so a fourth frozen artifact
    is covered the day it ships -- and the day `_SCOPE_FIELDS` legitimately grows one, this test
    stops objecting to the text that names it.
    """
    hashed = _scope_manifest_fields()
    artifacts = {"wireframe": "wireframe", "architecture": "architecture", "design": "design"}
    claims, offences = [], []
    for path in sorted(glob.glob(os.path.join(TEAM_KITS, "*", "skills", "*", "SKILL.md"))
                       + glob.glob(os.path.join(TEAM_KITS, "*", "constitution", "AGENTS.md"))):
        with io.open(path, encoding="utf-8") as handle:
            text = handle.read()
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if "scope manifest" not in sentence.lower():
                continue
            claims.append(sentence)
            lower = sentence.lower()
            manifest = lower.find("scope manifest")
            for word, field in artifacts.items():
                found = re.search(r"(?<![\w-])%s(?![\w-])" % word, lower)
                if not found or "%s_refs" % field in hashed:
                    continue
                # THE NEGATION HAS TO BIND TO THIS ARTEFACT, and round 1's F6 is what a loose one
                # costs: any `not` in the sentence excused the whole sentence, so "the wireframe is
                # part of the manifest, which is not unusual" would have passed. The denial must
                # stand BETWEEN the artefact word and the words it is being attached to -- that
                # span IS the claim, and prose outside it is about something else.
                span = lower[min(found.start(), manifest):max(found.end(), manifest + 14)]
                if re.search(r"(?<![\w-])(not|cannot|never|no)(?![\w-])", span):
                    continue        # a sentence that DENIES the membership is the fix, not the bug
                offences.append("%s: %s" % (os.path.relpath(path, ROOT), " ".join(
                    sentence.split())[:180]))
    assert claims, "no kit text speaks about the scope manifest at all -- the scan is vacuous"
    assert not offences, (
        "a kit text puts an artifact into the scope manifest that the kernel does not hash "
        "(BUG-0077; the hashed set is %s):\n  %s" % (sorted(hashed), "\n  ".join(offences)))


def test_no_constitution_promises_that_a_specialists_voice_stays_out_of_the_users_view():
    """BUG-0046: the kits ASSURED the user that jargon stays between agents, and the apparatus does
    not build that -- 132 of 256 relayed assistant blocks in pilot 3 were specialist transcripts the
    provider stores separately and the rig relayed unfiltered, and the PM's own mixing was ONE
    one-word case in 112 kit-PM blocks.

    So the defect was never the PM's language; it was an assurance about voices the kit does not
    control. What must stand in its place, in every kit, is the MECHANISM with its measured limit:
    a specialist dispatched with `run_in_background: true` writes into the same stream (measured on
    the SDK stream; what a terminal client collapses of it is not measured), and the lead answers
    the complaint once and plainly instead of promising to switch it off.

    THE PARAGRAPH IS FOUND BY ITS SUBJECT, not by a line number: it is the block that names the
    dispatch flag, which is the mechanism the whole claim now rests on. A kit whose block stops
    naming the flag has stopped saying what it is talking about, and a kit that re-adds a promise
    has to delete the sentence this asserts.
    """
    for kit in _kit_dirs():
        path = os.path.join(kit, "constitution", "AGENTS.md")
        with io.open(path, encoding="utf-8") as handle:
            text = handle.read()
        blocks = [block for block in re.split(r"\n[ \t]*\n", text)
                  if "run_in_background: true" in block]
        where = os.path.relpath(path, ROOT)
        assert len(blocks) == 1, (
            "%s: %d blocks speak about the background dispatch's own stream, expected one"
            % (where, len(blocks)))
        block = blocks[0]
        assert "measured on the SDK stream" in block, (
            "%s: the block names the mechanism and not what was MEASURED about it" % where)
        assert "is not" in block.split("measured on the SDK stream", 1)[1][:120], (
            "%s: the measurement stands without the half it does NOT cover" % where)
        assert "never promise to switch it off" in block, (
            "%s: nothing stops the lead promising the user an assurance the kit does not build "
            "(BUG-0046)" % where)


_HAND_DUTY_LEAD_IN = "**THE USER'S HAND IS NEVER THE ROUTE AROUND A GATE.**"


def _hand_duty_blocks(path):
    """Every blank-line-separated block of this file that OPENS with the hand duty's lead-in."""
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    return [block.strip("\n") for block in re.split(r"\n[ \t]*\n", text)
            if block.lstrip().startswith(_HAND_DUTY_LEAD_IN)]


def test_every_constitution_forbids_handing_the_user_a_line_around_a_gate():
    """BUG-0081 and BUG-0080: twice in one week a lead did everything right up to the last sentence
    and then handed the USER a command line -- a `git push -u origin pr/PR-0001-redesign` the merge
    gate had refused it, and a `cp` into a staging directory the write gate had refused it.

    Both leads named the refusal correctly and neither edited a gate. What was missing was the rule
    that the user's terminal is not the remaining route, and it was missing from the document every
    role of a kit is sent to. ONE text, in the constitution, next to the gap route it sends people
    to instead -- the same carrier and the same shape as the reading-discipline duty above, so
    `test_a_paragraph_the_constitutions_share_is_one_text` holds the three copies byte-identical
    and this holds presence: exactly one block per kit, because a second version outlives the first.

    WHAT THIS CANNOT DO, and it is the same limit every duty in a constitution has: it cannot read
    whether a lead obeyed it. What closes the two cases in CODE is elsewhere and measured there --
    BUG-0081's gate now distinguishes a work-branch push from a delivery
    (`tools/test_hooks.py::test_the_first_work_branch_push_is_not_refused_for_a_verdict_the_push_has_to_produce`),
    and BUG-0080's missing in-apparatus writer for a re-freeze input is carried as an open item
    rather than claimed here.
    """
    carriers = [os.path.join(kit, "constitution", "AGENTS.md") for kit in _kit_dirs()]
    assert len(carriers) >= 3, carriers
    for path in carriers:
        where = os.path.relpath(path, ROOT)
        found = _hand_duty_blocks(path)
        assert len(found) == 1, (
            "%s carries %d statement(s) of the hand duty, expected exactly one" % (where, len(found)))
        assert "BUG-0081" in found[0] and "BUG-0080" in found[0], (
            "%s: the duty names neither measured case, so it reads as taste" % where)
        assert "carries its one-sentence explanation WITH the line" in found[0], (
            "%s: the duty no longer says what a legitimate handed line owes" % where)


def _reading_duty_blocks(path):
    """Every blank-line-separated block of this file that OPENS with the reading duty's lead-in."""
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    return [block.strip("\n") for block in re.split(r"\n[ \t]*\n", text)
            if block.lstrip().startswith(_READING_DUTY_LEAD_IN)]


def test_every_constitution_carries_the_reading_discipline_duty():
    """DEC-0095 (6): the cost rule -- read the end of a log and not the log, report short -- is a
    duty of every kit, in ONE text, in the constitution, and of this repo's implementer role.

    WHY THE CONSTITUTION and not the specialist role files: it is the document every role of a kit
    is sent to and the one that arrives in a scaffolded project as `AGENTS.md`. A role definition
    is per role, and the duty is not -- it is what makes a long context affordable for all of them.
    This is the same carrier the comment rule uses
    (`tools/test_review_procedure.py::test_every_constitution_carries_the_comment_discipline_duty`).

    HELD TWICE, like that rule: here for PRESENCE -- one block per kit, never two, because the
    second version is what outlives the first -- and by
    `test_a_paragraph_the_constitutions_share_is_one_text` above for byte-equality, which takes any
    bold lead-in two constitutions share and demands the third and equal bodies.

    THIS REPO'S OWN TWO ROLES ARE CARRIERS TOO (DEC-0097 (5)), and for them the byte-equality has
    to be held HERE: the test above reads constitutions only, so the implementer's copy and the
    verifier's could drift with nothing measuring it -- and the verifier is the role that reads the
    most, which is why residue 4 of TSK-0136 named the gap in the first place. RED ON A COPY that
    is edited on one side: the two blocks differ and the diff position is named.

    WHAT THIS CANNOT DO: read whether an agent obeyed it. Nothing can -- there is no record of what
    a model read. What the duty asks instead is that a whole file read be NAMED in the report, and
    that is the lead's to check.
    """
    carriers = [os.path.join(kit, "constitution", "AGENTS.md") for kit in _kit_dirs()]
    repo_roles = [os.path.join(ROOT, ".claude", "agents", name + ".md")
                  for name in ("harness-implementer", "harness-verifier")]
    carriers.extend(repo_roles)
    assert len(carriers) >= 5, carriers
    for path in carriers:
        where = os.path.relpath(path, ROOT)
        found = _reading_duty_blocks(path)
        assert len(found) == 1, (
            "%s carries %d statement(s) of the DEC-0095 (6) reading duty, expected exactly one"
            % (where, len(found)))
        assert "DEC-0095" in found[0], "%s: the duty points at no decision" % where
        assert "never from the top and never whole" in found[0], (
            "%s: the duty no longer says what it forbids" % where)
    bodies = {os.path.relpath(path, ROOT): _reading_duty_blocks(path)[0] for path in repo_roles}
    one, other = sorted(bodies)
    if bodies[one] != bodies[other]:
        parted = next((position for position in range(min(len(bodies[one]), len(bodies[other])))
                       if bodies[one][position] != bodies[other][position]),
                      min(len(bodies[one]), len(bodies[other])))
        raise AssertionError(
            "the two harness role texts carry different copies of the DEC-0095 (6) duty; they "
            "agree up to %d characters, then read:\n    %s"
            % (parted, "\n    ".join("%s: ...%s" % (where, bodies[where][parted:parted + 100])
                                     for where in (one, other))))


def _lead_role_of(kit):
    """The role a kit binds as its SESSION agent, asked of the kit rather than typed."""
    sys.path.insert(0, TEAM_KITS)
    from kernel import presets

    lead = presets.lead_role(kit) if hasattr(presets, "lead_role") else None
    if lead:
        return lead
    for candidate in ("project-manager", "office-manager"):
        if os.path.isfile(os.path.join(kit, "agents", candidate + ".md")):
            return candidate
    return None


def test_every_kit_lead_pins_the_rung_its_own_planning_class_starts_on():
    """DEC-0095 (2): the kits' leads pin OPUS, and they pin it because their own `planning` class
    says so -- the two are held against each other rather than both typed here.

    WHY THE PIN AND NOT THE LADDER for this one role: the lead is the bound SESSION agent and is
    never dispatched, so `ladder_for_order` never lifts it. Its frontmatter `model:` is what the
    foreground really runs on (measured 2026-08-21,
    docs/reviews/2026-08-21-tsk0078-measurements.md), which makes the pin the price the user pays
    per session -- the single biggest item DEC-0095 was answering.

    RED ON A `fable` PM PIN, which is what all three kits shipped before this round: the pin
    resolves to the top rung and the planning class starts on opus. Red the other way too -- a
    `planning` class moved back to `top` while the pin stays opus is the same disagreement seen
    from the other side.

    THE ALIAS IS RESOLVED, not compared as a word, and that is not a convenience: `tools/validate.py`
    REFUSES a rung name in a kit source that is an alias TARGET, so `lead` is the only spelling a
    kit may use for this rung -- while the scaffold rewrites it to `opus` in the installed
    frontmatter (`tools/test_hooks.py`, the scaffold's alias-rewrite rows). Comparing the word
    would therefore compare the two ends of that rewrite.
    """
    sys.path.insert(0, TEAM_KITS)
    import yaml as _yaml
    from kernel import dispatch as _dispatch
    import gen_provider_artifacts as _gpa

    _tiers, aliases = _gpa.load_tiers()
    judged = 0
    for kit in _kit_dirs():
        name = os.path.basename(kit)
        lead = _lead_role_of(kit)
        assert lead, "%s binds no session role this reader can find" % name
        with io.open(os.path.join(kit, _dispatch.LADDER_FILE), encoding="utf-8") as handle:
            ladder = _dispatch._valid_ladder(kit, _yaml.safe_load(handle))
        role_class = ladder["roles"][lead]
        rule = ladder["classes"][role_class]
        starts_on = ladder["top"] if rule == _dispatch.CLASS_TOP else rule
        assert starts_on in ladder["rungs"], (
            "%s: its lead's class %r starts on %r, which is not a rung -- a lead that started on "
            "its own pin would make this check compare a value with itself" % (name, role_class, rule))
        pinned = _gpa.tier_of(str(_dispatch.role_pin(os.path.join(kit, "agents"), lead)), aliases)
        assert pinned == starts_on, (
            "%s: %s pins %r while its %r class starts on %r -- the session runs on the PIN, so the "
            "declaration and the seat the user pays for disagree (DEC-0095 (2))"
            % (name, lead, pinned, role_class, starts_on))
        assert pinned == "opus", (
            "%s: DEC-0095 (2) puts every kit's orchestrator on opus and this one runs on %r"
            % (name, pinned))
        judged += 1
    assert judged == len(_kit_dirs()) >= 3, judged


def test_the_report_writer_is_told_the_command_that_files_its_render():
    """BUG-0186: the render HAS a write path, and the text the Report-Writer reads now names it.

    The kit built `freeze-report` in TSK-0106 and measured it, and no shipped text said so. The
    role's own page told it the opposite -- render into staging, hand the paths back, and "report
    the missing promotion step as the infrastructure defect it is" -- so a Report-Writer either
    found the command in the kernel's `--help` or filed a defect report about a command that
    existed. Constitution section 17 makes the rendered report a completeness condition and section
    0 refuses every tool write under the state directory, which is what left the role with no
    route it could read.

    WHERE IT STANDS IS MEASURED, not chosen: the research LEAD PACKAGE is at its recorded ceiling
    (`tools/validate.py` spec II.5; the number lives in `tools/lead_package_sizes.json` and nowhere
    else, so a re-measurement moves it in one place), so the constitution cannot carry one more
    sentence without a raised record -- and the role's own SKILL is where a Report-Writer looks
    anyway. That is the second half of this test: the skill names it, and the false sentence is
    gone.

    BOTH ENDS, and neither is a string search for a slogan: the command is read off the SHIPPED
    PARSER (`kernel.cli`), so renaming it there is red here.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import cli

    surface = set(cli.build_parser()._subparsers._group_actions[0].choices)
    assert "freeze-report" in surface, sorted(surface)

    # BOTH PAGES THE ROLE READS, and the role file first: it is INJECTED at every spawn while the
    # skill is registered-not-injected (the role file says so itself). The verifier of TSK-0142
    # measured the first cut of this test reading only the skill, while `agents/report-writer.md`
    # still told the role to stage the render and "report that gap" (B3) -- the withdrawn sentence
    # standing exactly where the role looks first.
    for relative in (("skills", "report-writer", "SKILL.md"), ("agents", "report-writer.md")):
        path = os.path.join(TEAM_KITS, "research-team", *relative)
        with io.open(path, encoding="utf-8") as handle:
            text = handle.read()
        where = "/".join(relative)
        assert "freeze-report" in text, (
            "%s names no command that files a render" % where)
        for withdrawn in ("the missing promotion step as the infrastructure defect",
                          "report that gap"):
            assert withdrawn not in text, (
                "%s still calls the built route a missing step (%r)" % (where, withdrawn))


def _roles_that_type_an_approval_value():
    """[(kit, role file path, the manifest keys its own text types)] -- read off both running ends.

    WHICH KEYS a role could type comes from the kernel (`LINE_MANIFEST_BUILDERS` minus the ones
    `LINE_MANIFEST_RESOLVERS` derives, which is the same derivation `_value_language_anchors` uses
    for the lead); WHICH ROLES type one comes from the shipped role pages, by the option spelling
    the page really carries. Neither end is a list here: a kind that grows a new typed key, and a
    role page that starts telling its role to request an approval, both arrive in this test.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import approvals, cli
    typed = {key for builder in approvals.LINE_MANIFEST_BUILDERS.values()
             for key in cli.manifest_parameters(builder)
             if key not in cli.LINE_MANIFEST_RESOLVERS}
    assert typed, "no approval value is typed on the line -- this reader stopped matching"
    found = []
    for kit in _kit_dirs():
        folder = os.path.join(kit, "agents")
        for name in sorted(os.listdir(folder) if os.path.isdir(folder) else []):
            path = os.path.join(folder, name)
            with io.open(path, encoding="utf-8") as handle:
                text = handle.read()
            if "request-approval" not in text:
                continue
            keys = sorted(key for key in typed
                          if re.search(r"--%s\b" % re.escape(key.replace("_", "-")), text))
            if keys:
                found.append((os.path.basename(kit), path, keys))
    assert found, "no role page types an approval value -- this reader stopped matching"
    return found


def test_every_role_that_types_an_approval_value_carries_the_language_rule():
    """BUG-0169 (H77): the value-language rule stood on the LEAD surfaces only, while four other
    role pages tell their role to type a free value into an approval card the user then signs.

    MEASURED on the shipped tree, 2026-09-12, by the derivation below: the office `records-clerk`
    types `--reason` (plus two paths) on a `filing_correction`, and the `project-auditor` of ALL
    THREE kits types `--trigger`, `--cadence`, `--role` and `--scope` on a routine. `BUG-0169`
    named the records-clerk alone; the auditors came out of the derivation, which is the reason it
    is one.

    THE RULE IS ONE TEXT, not a retelling per page. What this asks of a role page is a contiguous
    span it SHARES with the rule the leads carry -- so a page whose copy drifts goes red here
    rather than teaching a second rule -- plus a section of its own naming the command and one of
    the values IT types, because a rule the reader cannot connect to their own line is a rule about
    somebody else's work.

    WHAT IT CANNOT DO is what the lead's own test says of itself: it reads PROSE, so it measures
    that the rule is in front of the role and never that the role obeyed it. No gate can read a
    value's language (`test_the_value_language_rule_claims_no_enforcement_it_does_not_have`).
    """
    import difflib
    shared = None
    for kit in _kit_dirs():
        blocks = {block for path in lead_package.files(kit)
                  for block in _answering_sections(path, _value_language_anchors())}
        shared = blocks if shared is None else (shared & blocks)
    assert shared, "the kits' loaded lead texts share no value-language rule to hold anyone to"
    rule = max(shared, key=len)

    for kit, path, keys in _roles_that_type_an_approval_value():
        with io.open(path, encoding="utf-8") as handle:
            text = handle.read()
        if any(block in shared for block in _markdown_sections(text)):
            continue                      # this IS a lead surface: its own test holds it
        match = difflib.SequenceMatcher(None, rule, text, autojunk=False).find_longest_match(
            0, len(rule), 0, len(text))
        assert match.size >= 300, (
            "%s/%s types %s into an approval card and shares only %d characters with the rule the "
            "leads carry -- the value-language rule is not on the page that writes the value"
            % (kit, os.path.basename(path), keys, match.size))
        sections = [block for block in _markdown_sections(text)
                    if "request-approval" in block and "`BUG-0073`" in block
                    and any(re.search(r"`-?-?%s`" % re.escape(key.replace("_", "-")), block)
                            for key in keys)]
        assert sections, (
            "%s/%s carries the rule's words but no section that names `request-approval`, its "
            "occasion and one of its OWN values %s" % (kit, os.path.basename(path), keys))
