"""Shared pytest configuration for the harness's own test suite.

It carries the `known_hole` marker and the V1 monolith inventory below — what more than one test
module has to agree on. That inventory was a PAIR for a round, the second half naming the stores
whose shipped readers another group still owned; it is one dict again because those readers were
rewritten and the names moved across. See the comment above `V1_MONOLITHS`.

The `known_hole` marker: a place where a documented, still-open gap is
ASSERTED as current behaviour rather than promised in prose. `pytest -m known_hole` enumerates
them, and `python scripts/harness.py doctor` (phase-2 step 8) must cross-check that enumeration against the
capability matrix's `unverified` entries — so "step 4 will close this" stops being a note someone
has to remember and becomes something the harness checks about itself.

A known_hole test PASSES while the hole exists and turns into a loud failure the day it is closed,
with its own docstring saying to invert it. That is deliberately not an xfail: a non-strict xfail
would be silent in both directions, and a strict one would file a working exploit under "expected
failure", which is the one label a reader must not walk away with.
"""


import ast
import io
import os
import sys

import pytest


def sibling_import_closure(start, source):
    """`start` plus every sibling module it imports, TRANSITIVELY — file names, `start` first.

    ONE HOME for the derivation two test modules need (`test_hooks._stage_kernel_bridge`,
    `test_hooks_v2._stage_launcher`): a hook helper that is copied into a scaffolded `.claude/hooks`
    for a real-process test has to travel with everything it imports, or the launcher/bridge meets
    its own fail-closed refusal instead of the behaviour under test. Both stagers wrote out the
    list by hand and both were one dependency short the day one grew — `_kernel` gained
    `_stdlib_guard` (BUG-0013) and nine real-process tests reported the bridge ABSENT while it was
    present. DERIVED, and TRANSITIVE, so a grandchild import is covered too; a cycle terminates
    because each name is followed once. Only siblings that EXIST in `source` are followed —
    stdlib and package imports are not siblings and drop out.
    """
    order, pending = [], [start]
    while pending:
        name = pending.pop(0)
        if name in order or not os.path.isfile(os.path.join(source, name)):
            continue
        order.append(name)
        with io.open(os.path.join(source, name), encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), name)
        for node in ast.walk(tree):
            modules = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                       else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            pending.extend(module.partition(".")[0] + ".py" for module in modules)
    return order

# NO BYTECODE IN THE SOURCE TREES. tools/validate.py states the principle for itself ("validation
# must never create __pycache__ that the installer could pick up") and the suite kept breaking it one
# import site at a time: three by-path loaders (only one of which was shielded), a plain
# `import kit_browser_checks` after a sys.path insert, and in principle every child process that runs
# a shipped script where it lies. Redirecting the cache is the only form of the rule that needs no
# list of import sites — `sys.pycache_prefix` covers this process, `PYTHONPYCACHEPREFIX` the ones it
# spawns. `.pytest_cache/` is already gitignored, so the caching benefit survives.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYCACHE_DIR = os.path.join(REPO_ROOT, ".pytest_cache", "pycache")
os.makedirs(PYCACHE_DIR, exist_ok=True)
sys.pycache_prefix = PYCACHE_DIR
os.environ["PYTHONPYCACHEPREFIX"] = PYCACHE_DIR


# AND NO SUITE RUN WRITES INTO THIS REPO'S OWN STATE EITHER (BUG-0052), by the same move and for
# the same reason. A kit gate records every refusal through `_audit.record`, whose sink is
# `<find_repo_root()>/project_memory/.audit/hook_events.jsonl`, and `_root.find_repo_root` answers
# `$CLAUDE_PROJECT_DIR` FIRST — correct in a session, wrong here: a hook this suite starts without
# an explicit project dir inherits the session's, which in this repository is this repository. The
# lines then land in canonical state, and the lead commits them with the package.
#
# THE ENVIRONMENT IS REDIRECTED, NOT THE CALL SITES. A fixture that forgets the override is the
# defect's shape, so a list of fixtures to repair would be one entry short again the next time one
# is written; every child process inherits from exactly one place and this is it. A test that
# passes its own project dir still wins, because `dict(os.environ, CLAUDE_PROJECT_DIR=...)` is
# applied after this. The sink is a real tree rather than a nonexistent path on purpose: `_audit`
# drops the record when the root holds no `project_memory/`, and a swallowed event would make this
# redirection unmeasurable — here the event is kept, next to the run that produced it.
# `test_no_hook_started_by_this_suite_can_write_this_repos_audit_log` measures both halves.
AMBIENT_PROJECT_DIR = os.path.join(REPO_ROOT, ".pytest_cache", "ambient-project")
os.makedirs(os.path.join(AMBIENT_PROJECT_DIR, "project_memory", ".audit"), exist_ok=True)
os.environ["CLAUDE_PROJECT_DIR"] = AMBIENT_PROJECT_DIR


# THE V1 STATE MONOLITHS. A monolith is a state store that lived directly at the ROOT of
# `project_memory/` and held MANY items at once. V2 gives every item its own file in a typed
# directory (`kernel.backlog_types.ACTIVE_DIRS`) and regenerates every rollup into `generated/`, so
# no ITEM lives at the V2 state root any more. What still does is reference MATERIAL — the config
# and the kits' own reference files (`master_data.yaml`, `literature.yaml`, `filing_plan.yaml`, …),
# which hold no items and have no status automaton, and are therefore not monoliths under this
# definition however many rows they carry.
#
# The names are historical fact — nothing in the V2 code can derive them — so they are written down
# exactly once, here, and every check that needs them reads this dict. The value says where the
# state went, because "gone" and "moved" need different treatment: `masterplan.md` still exists at
# `product/masterplan.md`, which is why the lockstep sweep judges the PATH and not the name.
#
# THIS DICT IS NOW COMPLETE ABOUT V1, and for one round it was not. A second inventory
# (`V1_ROOT_STORES_NOT_YET_MIGRATED`) stood beside it holding three stores whose SHIPPED READERS
# another group still owned — the office PROC registry and the two guidelines files — because
# sweeping them here would have painted that group's open work as this group's regression. Those
# readers were rewritten (`gate_proc_approved` and the two office scripts onto PROC items,
# `guard_guidelines` / `gate_test_coverage` / the kit scripts onto INV items), so the three names
# moved in here and the second inventory went with them, together with the test that asserted the
# couplings were exactly those. That is the bargain that inventory was written under: an entry
# disappears WITH the repair, and the completion proof below then owns the name — which is the
# stronger check, since it fails for ANY new path rather than for a departure from a recorded list.
V1_MONOLITHS = {
    "product_requirements.yaml": "every PRD in one file -> product/active/PR-nnnn.yaml",
    "system_requirements.yaml": "every SR in one file -> system/active/SR-nnnn.yaml",
    "tasks.yaml": "every task in one file -> tasks/active/TSK-nnnn.yaml",
    "design.yaml": "design decisions -> frozen DSN revisions plus INV items",
    "architecture.yaml": "components/data flow -> ARC items plus SRs; packaging -> the ARC item",
    "progress.yaml": "the narrative status log -> the items' own status plus generated/index.yaml",
    "filing_log.yaml": "the office filing log -> the archive tree itself; a scan index over it "
                       "would be regenerated into generated/, never kept at the state root",
    "masterplan.md": "the discovery artifact -> product/masterplan.md, frozen and status-free",
    "research_questions.yaml": "every RQ in one file -> research/active/RQ-nnnn.yaml",
    "hypotheses.yaml": "every hypothesis in one file -> hypotheses/active/HYP-nnnn.yaml",
    "experiment_designs.yaml": "every experiment in one file -> experiments/active/EXP-nnnn.yaml",
    # A GLOB rather than a name, because that is literally what the V1 merge gate looked for: the
    # store was "whichever report file happens to be there". It moved last, on its own disposition
    # rows (115/338/507), when `gate_git` was rewritten to read the Evidence store instead.
    "*report*.yaml": "the QA/validation reports -> evidence/EVD-nnnn.yaml, one typed item per "
                     "verdict (spec II.2 Evidence)",
    "coding_guidelines.yaml": "the language rule book -> invariants/active/INV-nnnn.yaml: a rule "
                              "is an INV with `text`, a kit-script knob is an INV with `value`, "
                              "and a source area is any INV whose `scope` names a directory",
    "testing_guidelines.yaml": "the test rule book -> invariants/active/INV-nnnn.yaml, the same "
                               "way: `coverage_gate` and `browser_smoke` are value-INVs, and the "
                               "EXTRA coverage areas are the scopes that name directories",
    "process_definitions.yaml": "the office PROC registry -> procedures/active/PROC-nnnn.yaml, "
                                "one typed item per procedure (spec II.2/II.9). It moved LAST, "
                                "with the gate and the two repo scripts that opened it: "
                                "`gate_proc_approved` now reads the items and refuses an empty "
                                "store (spec II.4), and the `approved_hash` those scripts could "
                                "not produce is stamped by the approval mint.",
}


# THE EVIDENCE PRODUCER IS INSTALLED, AND THE TWO CONSTANTS THAT SAID OTHERWISE CAME OUT HERE.
# `NO_INSTALLED_EVIDENCE_PRODUCER_CLAIM` ("entry point is not installed") and
# `EVIDENCE_PRODUCER_CLAIM_SCOPE` ("what the harness INSTALLS") pinned one measured fact across
# twenty shipped documents, with the promise written into their own comment: they would go RED the
# day the shim shipped, and the constants, the four tests and the caveat in every shipped text
# would then come out TOGETHER. That day is 2026-07-29 — the kits install
# `templates/repo/scripts/harness.py` kit-owned, and the acceptance measurement lives in
# `test_the_evidence_the_merge_gate_demands_has_an_installed_producer` (merge refused for want of
# Evidence, the entry point's command line through every registered shell gate and then executed,
# the same merge allowed).
#
# WHAT REPLACED THEM, because the derivation was the valuable half and the fact was only its
# subject. The old constants existed so that ~20 documents could not each grow their own account
# of one fact; the new fact — there is exactly ONE spelling of the entry point, and its surface is
# smaller than spec II.4 asks for — needs the same holding-together across ~150 places, so it is
# derived the same way in `test_hooks.py`:
#   * `test_every_shipped_text_spells_the_entry_point_the_one_way` — the spelling comes from
#     `kernel.cli.INVOCATION`, and no shipped text may spell a command as the bare word, whether
#     in a code span or in front of a subcommand.
#   * `test_every_command_a_role_is_handed_is_on_the_entry_points_surface` — every command named in
#     a shipped text is checked against the SHIPPED PARSER, or its block says it is not on the
#     surface. The two run over ONE corpus (every shipped text, plus the AST-folded refusal texts);
#     they did not, and an uncovered `capture` planted in `session_status.py` was measured passing
#     the narrower one.
# Neither needs a constant here: both read the kernel, which is the one place the answer is built.
# Both read their corpus through `_reading_view`, because a command does not stop at a line break —
# the split-string form that hid this very fact from a `rg` in `gate_write_scope.py` also hid a
# planted `("run harness " / "doctor first")` from the first cut of these checks.


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM_KITS = os.path.join(ROOT, "team-kits")


def repo_spells(relative, root=None):
    """Does this repo carry that path, spelled EXACTLY like that?

    Segment by segment against `os.listdir` of the parent, because the question is what the tree
    calls its files — not whether the filesystem is willing to find them under another spelling.
    `os.path.exists` answers the second question, and on NTFS/APFS the two answers differ, so a
    dead reference stays green on both developer platforms and breaks the `ubuntu-latest` leg.

    HERE rather than in one test module because a second module needed the same question: the
    document sweep in `test_shortening_net.py` asks it of the disposition, and the entry-gate sweep
    in `test_hooks.py` asks it of the two global instruction files. Two copies of "what does the
    tree call this" is the drift this file exists to prevent.
    """
    current = root or ROOT
    for segment in str(relative).replace("\\", "/").split("/"):
        try:
            names = os.listdir(current)
        except OSError:
            return False
        if segment not in names:
            return False
        current = os.path.join(current, segment)
    return True


def mint_via_hook(state, request, answer=None, expect_success=True):
    """Mint an approval through the REAL PostToolUse hook — the only caller the kernel accepts.

    `approvals.mint` refuses any other caller (user condition (i), 2026-07-25): it is a plain
    function, and anything that can read `approvals/pending/<id>.yaml` would otherwise be able to
    pass the label it found there and manufacture a user approval. So every test that expects a
    SUCCESSFUL mint drives the hook, which also means the mint path is exercised end to end rather
    than in a library call no production code makes. Refusal tests keep calling `mint` directly:
    the caller check is deliberately last, so content refusals still report on their own terms.

    HERE rather than in one test module, because a second module needed it the day
    `state.transition` started demanding an approval: the fixtures that walk a root item along its
    chain now have to MINT, and a private copy of this in each of them is the drift this file
    exists to prevent.
    """
    import json
    import subprocess

    sys.path.insert(0, TEAM_KITS)
    from kernel import approvals

    repo = os.path.dirname(state.root)
    question = approvals.build_question(request)
    if answer is None:
        answer = approvals.approve_label(request["mint_code"])
    payload = {
        "hook_event_name": "PostToolUse", "tool_name": "AskUserQuestion", "cwd": repo,
        "tool_input": {"questions": [question]},
        "tool_response": {"answers": {question["question"]: answer},
                          "questions": [question]},
    }
    env = dict(os.environ, CLAUDE_PROJECT_DIR=repo, HARNESS_KERNEL_PATH=TEAM_KITS)
    result = subprocess.run(
        [sys.executable, os.path.join(TEAM_KITS, "dev-team", "hooks", "gate_approval.py")],
        input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=120)
    assert result.returncode == 0, result.stderr
    if expect_success:
        assert "recorded for" in result.stderr, result.stderr
    return result


def approve(state, item_id, kind="scope"):
    """Give an item a real, minted approval of `kind` — request + hook mint, nothing hand-written."""
    sys.path.insert(0, TEAM_KITS)
    from kernel import approvals
    mint_via_hook(state, approvals.create_pending_request(state, kind, item_id))
    return approvals.read_apr(state, state.read_item(item_id)["approval_ref"])


def walk_to_status(state, item, target):
    """Walk an item along its OWN chain to `target`, the way a real session walks it.

    WHICH edges need an approval is asked of the kernel (`approvals.required_approval_kinds`) and
    never listed here — that is the whole point of the fixture. A gated edge is walked by MINTING
    its approval, because `state.transition` refuses it and the mint performs the edge itself; an
    ungated one is walked by `transition`. So the day another edge becomes gated, every fixture
    built on this one keeps walking the sanctioned route instead of quietly measuring a hole.

    There is deliberately no shortcut past the mint. Spec II.4 forbids a bootstrap FLAG ("der Lead
    könnte sein eigenes Gate umgehen"), and a test fixture that could set one would be exactly the
    caller the rule is about — the suite would then prove the gate on a path production never
    takes. A target OFF the chain (a terminal such as REJECTED) is a single transition, which is
    what its automaton says it is.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel.approvals import create_pending_request, required_approval_kinds
    from kernel.backlog_types import AUTOMATA, UNVERIFIED_ANSWER_FIELD, parse_id

    item_type, _ = parse_id(item["id"])
    chain = AUTOMATA[item_type].chain
    current = state.read_item(item["id"])
    if target in chain:
        steps = chain[chain.index(current["status"]) + 1: chain.index(target) + 1]
    else:
        steps = (target,)
    for step in steps:
        current = state.read_item(item["id"])
        kinds = required_approval_kinds(item_type, current["status"], step)
        if kinds:
            kind = sorted(kinds)[0]
            # DEC-0113: an ACCEPTANCE request refuses to go out until the user has been asked once
            # whether accepting a goal nobody verified is intended. A fixture walking the
            # SANCTIONED route answers that question exactly as the PM does; skipping it would
            # make every fixture built on this one measure a route production cannot take. WHETHER
            # it is owed is asked of the kernel, never assumed -- a goal that carries its runs is
            # not asked, and passing an answer there is refused.
            answer = None
            if kind == "acceptance" and not current.get(UNVERIFIED_ANSWER_FIELD):
                from kernel.report import verification_missing_for_goal

                if verification_missing_for_goal(state, item["id"]):
                    answer = "ja, so gewollt (Fixture: dieses Ziel hat keinen Prueflauf)"
            mint_via_hook(state, create_pending_request(state, kind, item["id"],
                                                        unverified_answer=answer))
        else:
            state.transition(item["id"], step)
    return state.read_item(item["id"])


def satisfy_the_architect_step(state, task, root):
    """Give `root` the ACCEPTED technical requirement a dispatch owes it, if the KERNEL says so.

    ONE HELPER FOR EVERY FIXTURE THAT LEASES, and the condition is asked of
    `dispatch.architect_step_owed` rather than restated here (FR-0085): a fixture with its own copy
    of the duty is a fixture that can walk past it, which is the one thing the dispatch fixtures of
    this suite are built never to do. `SR PROPOSED -> ACCEPTED` is in no row of
    `approvals.APPROVAL_TRANSITIONS`, so it is a plain transition and no mint is involved.

    Returns the requirement it created, or None when none was owed -- so a test can assert on the
    difference instead of guessing.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import dispatch

    if not dispatch.architect_step_owed(state, task, root):
        return None
    requirement = state.capture("SR", {
        "title": "technical requirement for %s" % root["id"],
        "derives_from": root["id"],
        "contract": "what the goal needs from the system, derived by the architect",
        "affected_components": ["src"]})
    state.transition(requirement["id"], dispatch._accepted_requirement_status())
    return state.read_item(requirement["id"])


def drive_task_to(state, task_id, target):
    """Walk a TSK to `target` the HONEST way (DEC-0038): LEASED and IN_PROGRESS come from the real
    dispatch lifecycle, never from a bare transition, exactly as `walk_to_status` mints an approval
    on a gated chain edge instead of transitioning past it.

    `create_lease` mints the lease (READY -> LEASED) and `spawn_outcome` records the spawn
    (LEASED -> IN_PROGRESS); everything from SUBMITTED on -- and an off-chain terminal such as
    FAILED or CANCELLED -- is a plain chain/back edge the guard does not touch. Leasing needs the
    ROOT to carry a dispatch approval, so this mints a scope approval when the root has none. There
    is deliberately no shortcut past `create_lease`, for the same reason `walk_to_status` has none
    past the mint: a fixture that hand-wrote a lease would prove the guard on a path production never
    takes.

    AND IT WALKS THE ARCHITECT STEP THE SAME WAY (FR-0085): a lease under a goal whose class asks
    for a technical requirement needs an ACCEPTED `SR` under that goal, so this captures and accepts
    one when the KERNEL says the order still owes it (`dispatch.architect_step_owed`). Asked of the
    kernel and never re-decided here, for the reason the mint above is not re-decided either -- a
    fixture with its own copy of the rule is a fixture that can walk past it. A test that MEASURES
    the duty calls `create_lease` itself; this one exists so ~100 tests about something else do not
    each have to state the same precondition.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import dispatch
    from kernel.backlog_types import AUTOMATA

    chain = AUTOMATA["TSK"].chain          # DRAFT,READY,LEASED,IN_PROGRESS,SUBMITTED,DONE,VALIDATED
    order = {status: index for index, status in enumerate(chain)}

    def now():
        return state.read_item(task_id)["status"]

    # off-chain targets (FAILED, CANCELLED) ride from their chain predecessor; on the shipped TSK
    # automaton that predecessor is IN_PROGRESS or later, so walk the chain to IN_PROGRESS first.
    chain_target = target if target in order else "IN_PROGRESS"
    if order[chain_target] >= order["LEASED"]:
        root = state.read_item(state.read_item(task_id)["product_requirement"])
        if not root.get("approval_ref"):
            approve(state, root["id"], "scope")
        satisfy_the_architect_step(state, state.read_item(task_id), root)
    if order[now()] < order["READY"] <= order[chain_target]:
        state.transition(task_id, "READY")
    if order[now()] < order["LEASED"] <= order[chain_target]:
        dispatch.create_lease(state, task_id)               # READY -> LEASED (mints the lease)
    if order[now()] < order["IN_PROGRESS"] <= order[chain_target]:
        dispatch.spawn_outcome(state, task_id, ok=True)     # LEASED -> IN_PROGRESS
    while order[now()] < order[chain_target]:
        state.transition(task_id, chain[order[now()] + 1])  # SUBMITTED..VALIDATED: plain edges
    if target not in order:
        state.transition(task_id, target)                   # the single off-chain edge
    return state.read_item(task_id)


def load_kit_module(name, path):
    """Import a shipped kit script by path, without polluting the kit tree or `sys.path`.

    ONE loader for the whole suite: there were three (`generate_dashboard.py`, `kit_checks.py`
    twice) plus a plain import, and the `__pycache__` shielding had been applied to exactly one of
    them. The cache redirection above is what actually guarantees the tree stays clean — this
    function's own `dont_write_bytecode` is the belt to that braces, and it also keeps the module
    out of `sys.modules` under a name a later real import could pick up.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = previous
    return mod


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "known_hole(capability): asserts a documented-open gap as current behaviour; the named "
        "capability must be reported `unverified` while this test passes",
    )


@pytest.fixture(autouse=True)
def _isolated_user_settings(monkeypatch, tmp_path_factory):
    """Point `CLAUDE_CONFIG_DIR` at an empty directory for every test.

    `report._settings_layers` reads the USER layer (`~/.claude/settings.json`) because Claude Code
    merges it and `disableAllHooks` most often lives there. That is correct in production and
    poison in a test suite: without this the results depend on whose machine runs them, and a
    developer with hooks disabled globally would watch the enforcement tests fail for a reason
    that has nothing to do with the code. Tests that care about the user layer create the file
    inside this directory.
    """
    monkeypatch.setenv(
        "CLAUDE_CONFIG_DIR", str(tmp_path_factory.mktemp("claude-config", numbered=True)))
    yield


@pytest.fixture(autouse=True)
def _no_test_leaks_an_import_path():
    """Hand every test back the `sys.path` it started with.

    WHY, and it is a measured defect rather than tidiness: the helpers above and ~100 test bodies
    put their kits directory on the path with a bare `sys.path.insert`, which appends ANOTHER copy
    on every call, and the scaffold and installer tests then hand that same list to a child
    process as PYTHONPATH.
    Linux refuses an envp string longer than MAX_ARG_STRLEN, so past the crossing point every
    scaffold and installer test on the hosted ubuntu runner died with `OSError: [Errno 7] Argument
    list too long: 'bash'` -- while the Windows leg, where those tests skip for want of a POSIX
    shell, stayed green and hid it (BUG-0069).

    Restoring HERE rather than de-duplicating at each reader of the path: the growth is the defect
    and the readers are only where it becomes visible.
    `test_repo_hygiene.test_no_test_in_this_suite_leaks_an_import_path` is the measurement.
    """
    before = list(sys.path)
    yield
    if sys.path != before:
        sys.path[:] = before


@pytest.fixture(autouse=True)
def _no_test_leaks_an_environment_variable():
    """Hand every test back the environment it started with, for the same reason as `sys.path`.

    An environment variable is inherited by every subprocess a LATER test starts, so a leak here
    does not stay in the process that made it. Measured 2026-08-29 on pristine HEAD: two tests in
    `test_hooks.py` set `$HARNESS_KERNEL_PATH` with a bare assignment, the entry point treats that
    variable as authoritative by design, and every `test_kitupdate.py` run in the same session then
    watched an "old stock" project answer out of THIS repo's kernel -- two tests red whenever
    `test_hooks.py` went first, green whenever they ran alone, which reads as flakiness and cost a
    round a wrong diagnosis.

    RESTORED rather than asserted, like the path above: an assertion here fires during teardown,
    where `monkeypatch` has not undone its own work yet, and would report the tests that did it
    RIGHT. `test_repo_hygiene.test_no_test_in_this_suite_leaks_an_environment_variable` is the
    measurement.
    """
    before = dict(os.environ)
    yield
    if os.environ != before:
        os.environ.clear()
        os.environ.update(before)
