#!/usr/bin/env python3
"""The RESEARCH chain end to end — RQ → HYP → EXP → report — on a SCAFFOLDED project.

A file of its own rather than more scenarios in `tools/test_e2e.py`, because the surface differs:
everything here runs against a project the SHIPPED installers built (`init_project_memory.sh` +
`scaffold_team.sh` against a throwaway HOME), so what is driven is the INSTALLED entry point
`scripts/harness.py`, the installed `.claude/hooks/` and the installed `.claude/kernel`. The dev
chain takes the cheaper route (`HARNESS_KERNEL_PATH` plus the kit's hooks directory in this repo);
the research chain cannot, because two of its links exist only after a scaffold — the entry point,
and the `project_memory/reports/` tray the report lint reads.

The scaffold is paid ONCE per module and every test works on a COPY of it, so no test sees another
test's writes.

No `known_hole` marker on the gap this file asserts as current behaviour: `tools/gen_known_holes.py`
collects markers out of the two hook modules its `SOURCES` names, so a marker here would reach
neither the sidecar nor `harness.py doctor`. The gap is carried by an assertion and by its own
docstring instead.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = "research-team"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="the research chain runs the shipped installers, which are POSIX shell, over a git repo")


# ---------------------------------------------------------------- the scaffolded project
def _run(args, cwd, env, stdin=None):
    return subprocess.run(args, cwd=cwd, env=env, input=stdin, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=900)


def _hook_process(proj, env, name, payload, launched=True):
    """Run a hook the way the kit's own `settings.json` registers it: behind `_gate.py`, raw UTF-8.

    `launched=False` is for the SessionStart entries, which that file registers directly.
    """
    hooks = os.path.join(proj, ".claude", "hooks")
    argv = [sys.executable, "-B", os.path.join(hooks, "_gate.py"), name] if launched else \
           [sys.executable, "-B", os.path.join(hooks, name)]
    done = subprocess.run(argv, cwd=proj, env=env,
                          input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                          capture_output=True, timeout=900)
    return done.returncode, done.stderr.decode("utf-8", "replace")


def _install(work):
    """A research project as a user gets one: the two shipped installers, against a THROWAWAY HOME.

    The whole `team-kits/` tree is copied into that home rather than the one kit, because that is
    what the installers read — `scaffold_team.sh` resolves `$HOME/.claude/team-kits/<team>` and the
    kernel beside it — and a curated copy would be this file's idea of the store rather than the
    store. The user's own `~/.claude` is never read and never written.
    """
    home = os.path.join(work, "home")
    proj = os.path.join(work, "proj")
    store = os.path.join(home, ".claude", "team-kits")
    os.makedirs(os.path.dirname(store))
    shutil.copytree(os.path.join(ROOT, "team-kits"), store,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".ruff_cache"))
    os.makedirs(proj)
    env = dict(os.environ, HOME=home, USERPROFILE=home, CLAUDE_PROJECT_DIR=proj)
    for script in ("init_project_memory.sh", "scaffold_team.sh"):
        done = _run([shutil.which("bash"), os.path.join(store, script), KIT], proj, env)
        assert done.returncode == 0, script + "\n" + done.stdout + done.stderr
    _run(["git", "init", "-q"], proj, env)

    # The scaffold leaves `.claude/HANDOVER_PENDING` and asks for a session restart; until a
    # SessionStart clears it, `gate_dispatch` refuses EVERY spawn — so a chain test that skipped
    # this step would be measuring the marker instead of the chain. This is that restart.
    _hook_process(proj, env, "clear_handover_marker.py",
                  {"hook_event_name": "SessionStart", "cwd": proj, "source": "startup"},
                  launched=False)
    assert not os.path.exists(os.path.join(proj, ".claude", "HANDOVER_PENDING"))
    return proj, home


@pytest.fixture(scope="module")
def _pristine(tmp_path_factory):
    return _install(str(tmp_path_factory.mktemp("research-install")))


class Project:
    """A scaffolded research project, driven only through surfaces a role really has."""

    def __init__(self, path, home):
        self.path = path
        self.env = dict(os.environ, HOME=home, USERPROFILE=home, CLAUDE_PROJECT_DIR=path)
        sys.path.insert(0, os.path.join(path, ".claude"))

    def harness(self, *args, stdin=None):
        """`python scripts/harness.py …` from the project root — the ONE spelling §0 names."""
        return _run([sys.executable, "-B", os.path.join("scripts", "harness.py"), *args],
                    self.path, self.env, stdin=stdin)

    def hook(self, name, payload, launched=True):
        return _hook_process(self.path, self.env, name, payload, launched=launched)

    def state(self):
        from kernel.state import ProjectState
        return ProjectState(os.path.join(self.path, "project_memory"))

    def status(self, item_id):
        return self.state().read_anywhere(item_id)[0]["status"]

    def mint(self, kind, item_id):
        """Open the approval question and answer it through the INSTALLED PostToolUse hook.

        Not `conftest.mint_via_hook`: that one runs `dev-team/hooks/gate_approval.py` out of THIS
        repo, and what is under test here is the hook the scaffold put into the project.
        """
        from kernel import approvals
        asked = self.harness("request-approval", kind, item_id)
        assert asked.returncode == 0, asked.stdout + asked.stderr
        state = self.state()
        pending = os.path.join(state.root, "approvals", "pending")
        request = None
        for name in sorted(os.listdir(pending)):
            if not name.endswith(".yaml"):
                continue
            entry = state._read_yaml(os.path.join(pending, name))
            if isinstance(entry, dict) and entry.get("item") == item_id \
                    and entry.get("kind") == kind:
                request = entry
        assert request is not None, "no pending %s request for %s" % (kind, item_id)
        question = approvals.build_question(request)
        return self.hook("gate_approval.py", {
            "hook_event_name": "PostToolUse", "tool_name": "AskUserQuestion", "cwd": self.path,
            "tool_input": {"questions": [question]},
            "tool_response": {"questions": [question], "answers": {
                question["question"]: approvals.approve_label(request["mint_code"])}}})


@pytest.fixture
def project(_pristine, tmp_path):
    """A copy of the installed project per test — the HOME stays the one the install ran against.

    Copied rather than re-installed because the install is the expensive step; the home is shared
    because nothing under test writes into it, and pointing it somewhere else would quietly change
    what a hook resolves.
    """
    pristine, home = _pristine
    work = str(tmp_path / "proj")
    shutil.copytree(pristine, work)
    return Project(work, home)


# ---------------------------------------------------------------- the chain's own material
_RQ = {
    "title": "Senkt eine dynamische Chunk-Größe die Fehlerrate der Beleg-Zuordnung?",
    "class": "normal",
    "question": "Senkt eine inhaltsabhängig bestimmte Chunk-Größe die Fehlerrate der "
                "Beleg-Zuordnung gegenüber einer festen Größe von 512 Token?",
    "motivation": "Jede Fehlzuordnung kostet die Kanzlei Nacharbeit; ob die Chunk-Größe der "
                  "Hebel ist, weiß niemand.",
    "acceptance_criteria": [{"id": "AC-1", "text": "Fehlerrate beider Arme mit Intervall"}],
    "out_of_scope": ["Produktivbetrieb"], "priority": "high",
}
_HYP = {
    "derives_from": "RQ-0001",
    "statement": "Eine dynamische Chunk-Größe senkt die Fehlerrate gegenüber einer festen.",
    "testable_prediction": "Der dynamische Arm liegt mindestens 5 Prozentpunkte tiefer, α = 0,05.",
}


def _experiment(parents):
    return {"derives_from": parents, "design": "Within-subject über 400 Belege, randomisiert",
            "variables": {"independent": ["chunking"], "dependent": ["Fehlerrate"]},
            "success_criteria": ["Differenz der Fehlerraten mit 95-%-Intervall"],
            "evidence_refs": []}


def _approved_question(project):
    """RQ captured → scope approval → delivery approval → HYP, all through installed surfaces."""
    captured = project.harness("capture", "RQ", stdin=json.dumps(_RQ, ensure_ascii=False))
    assert captured.returncode == 0, captured.stdout + captured.stderr
    assert project.status("RQ-0001") == "DRAFT"      # a fresh question is a draft, not a plan
    for kind in ("scope", "delivery"):
        code, err = project.mint(kind, "RQ-0001")
        assert code == 0, err
    assert project.status("RQ-0001") == "IN_DELIVERY"
    hypothesis = project.harness("capture", "HYP", stdin=json.dumps(_HYP, ensure_ascii=False))
    assert hypothesis.returncode == 0, hypothesis.stdout + hypothesis.stderr
    assert project.status("HYP-0001") == "PROPOSED"
    return project


# ---------------------------------------------------------------- scenario 1: the whole chain
def test_the_research_chain_runs_from_the_question_to_a_merge_through_the_shipped_hooks(project):
    """RQ → HYP → EXP → task → child → Evidence → the merge, each link eating the one before it.

    The counterpart of `test_e2e.test_e2e_the_draft_to_dispatch_chain_runs_through_the_shipped_hooks`
    for the kit whose chain is two levels deeper, and the thing the unit suite around the kernel
    cannot show: those exercise the links, this walks the chain. German item text throughout,
    because every link here crosses a process boundary as raw UTF-8.

    The experiment hangs from the hypothesis ALONE, which is the chain §4 of the kit's
    constitution documents. Until BUG-0083 it had to name the question as a second parent to be
    creatable at all, and that detour worked by making the origin check give up rather than pass;
    both halves are measured by
    `test_a_task_may_name_an_experiment_two_levels_under_the_question_it_serves`.
    """
    _approved_question(project)
    captured = project.harness("capture", "EXP",
                              stdin=json.dumps(_experiment("HYP-0001"), ensure_ascii=False))
    assert captured.returncode == 0, captured.stdout + captured.stderr
    code, err = project.mint("delivery", "EXP-0001")
    assert code == 0, err
    assert project.status("EXP-0001") == "APPROVED"

    task = project.harness(
        "create-task", "--product-requirement", "RQ-0001", "--derives-from", "EXP-0001",
        "--type", "research", "--assigned-role", "researcher", "--acceptance-ref", "AC-1",
        "--allowed-scope", "src/", "--forbidden-scope", "project_memory/",
        "--required-input", "EXP-0001", "--expected-output", "src/messlauf.py")
    assert task.returncode == 0, task.stdout + task.stderr
    assert project.harness("transition", "TSK-0001", "READY").returncode == 0
    dispatched = project.harness("dispatch", "TSK-0001")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr

    from kernel import dispatch
    state = project.state()
    lease = state._read_yaml(os.path.join(state.root, "tasks", "leases", "TSK-0001.lease.yaml"))
    header = dispatch.dispatch_header(lease)
    # THE MODEL THE LEASE ASKS FOR, read off the lease rather than typed -- this project has a kit
    # installed, so its lease carries a derived rung and a spawn that names no model is refused for
    # the climb alone (DEC-0077 (2)). The chain under test is the question-to-merge one, so that
    # refusal has to be out of the way rather than measured here; it is measured in
    # `tools/test_ladder.py::test_a_spawn_below_the_lease_rung_is_refused_and_one_that_names_it_passes`.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from test_hooks import model_the_lease_requires
    tool_input = {"subagent_type": "researcher",
                  "prompt": "objective: beide Arme messen\n%s\noutput: Diff" % header}
    wanted = model_the_lease_requires(lease)
    if wanted:
        tool_input["model"] = wanted
    spawn = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": project.path,
             "tool_input": tool_input}
    code, err = project.hook("gate_dispatch.py", spawn)
    assert code == 0, err
    # the counter-direction on the same lease: an INSTALLED role this task was not planned for is
    # refused, so the pass above measures the chain rather than a gate that waves everything
    # through. Installed, because a role the preset left out would be refused for being absent —
    # which is a different gate and would not show that the lease is bound to a role at all.
    roles = open(os.path.join(project.path, ".claude", "team_kit_roles.txt"),
                 encoding="utf-8").read().split()
    assert "methodologist" in roles, roles
    other = dict(spawn, tool_input=dict(spawn["tool_input"], subagent_type="methodologist"))
    assert project.hook("gate_dispatch.py", other)[0] == 2

    # PostToolUse on the spawn is what moves the task, and only for a status the gate recognises
    code, err = project.hook("gate_dispatch.py", dict(
        spawn, hook_event_name="PostToolUse",
        tool_response={"status": "completed", "agentId": "child-1"}))
    assert code == 0, err
    assert project.status("TSK-0001") == "IN_PROGRESS"

    os.makedirs(os.path.join(project.path, "src"), exist_ok=True)
    with open(os.path.join(project.path, "src", "messlauf.py"), "w", encoding="utf-8") as handle:
        handle.write("# beide Arme, Seed 20260831\n")
    handed_back = project.harness(
        "submit-result", "--task-id", "TSK-0001", "--role", "researcher",
        "--status-proposal", "SUBMITTED", "--summary", "Beide Arme gelaufen, Seeds notiert.",
        "--output", "src/messlauf.py", "--scope-touched", "src/")
    assert handed_back.returncode == 0, handed_back.stdout + handed_back.stderr
    for target in ("DONE", "VALIDATED"):
        moved = project.harness("transition", "TSK-0001", target)
        assert moved.returncode == 0, moved.stdout + moved.stderr

    merge = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": project.path,
             "tool_input": {"command": "git merge rq/RQ-0001-chunkgröße"}}
    shut, err = project.hook("gate_git.py", merge)
    assert shut == 2 and "no QA Evidence" in err, err

    from kernel.backlog_types import QA_EVIDENCE_KINDS
    for kind in sorted(QA_EVIDENCE_KINDS):
        recorded = project.harness(
            "evidence", "--kind", kind, "--result", "pass", "--related", "TSK-0001",
            "--summary", "Messlauf geprüft", "--artifact-ref", "staging/TSK-0001/lauf.log")
        assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    # the Evidence names the TASK; the branch names the QUESTION two levels above it, and the gate
    # opens because the binding is resolved transitively (`report.evidence_covers`)
    opened, err = project.hook("gate_git.py", merge)
    assert opened == 0, err


# ---------------------------------------------------------------- scenario 2: the deep origin
def test_a_task_may_name_an_experiment_two_levels_under_the_question_it_serves(project):
    """The kit's OWN hierarchy (constitution §4: RQ → HYP → EXP → TSK) is creatable — BUG-0083.

    This test used to assert the opposite as CURRENT BEHAVIOUR and to say in its own docstring
    that it must be inverted the day the origin check resolves transitively; this is that day.
    What it measured was a kernel that answered "which item does this one hang from" twice: with
    the SINGLE immediate parent at `create-task`, and transitively at the merge gate — so an EXP
    under a HYP had root HYP-0001 for the one and RQ-0001 for the other, and the research kit is
    the only shipped kit whose chain is deep enough for the two answers to differ.

    Driven through the INSTALLED entry point rather than against the kernel in this repo, because
    that difference was invisible in every unit fixture the dev chain provides.

    The refusal is measured in the same breath, so the pass above cannot be a check that stopped
    checking: an experiment under ANOTHER question is still refused, and the refusal names it.
    """
    _approved_question(project)
    captured = project.harness("capture", "EXP",
                               stdin=json.dumps(_experiment("HYP-0001"), ensure_ascii=False))
    assert captured.returncode == 0, captured.stdout + captured.stderr

    from kernel.report import _hangs_from, origin_root_conflict
    state = project.state()
    assert _hangs_from(state, "EXP-0001", "RQ-0001", set())
    assert origin_root_conflict(state, "EXP-0001", "RQ-0001") is None

    created = project.harness(
        "create-task", "--product-requirement", "RQ-0001", "--derives-from", "EXP-0001",
        "--type", "research", "--assigned-role", "researcher", "--acceptance-ref", "AC-1",
        "--allowed-scope", "src/", "--expected-output", "src/messlauf.py")
    assert created.returncode == 0, created.stdout + created.stderr
    assert project.status("TSK-0001") == "DRAFT"

    second = project.harness("capture", "RQ", stdin=json.dumps(
        dict(_RQ, title="Zweite Frage", question="Senkt ein Cache die Laufzeit?"),
        ensure_ascii=False))
    assert second.returncode == 0, second.stdout + second.stderr
    refused = project.harness(
        "create-task", "--product-requirement", "RQ-0002", "--derives-from", "EXP-0001",
        "--type", "research", "--assigned-role", "researcher", "--acceptance-ref", "AC-1",
        "--allowed-scope", "src/", "--expected-output", "src/messlauf.py")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "belongs to RQ-0001" in refused.stderr, refused.stderr


def test_an_experiment_hanging_from_two_questions_is_refused_as_an_origin(project):
    """Ambiguous parentage fails CLOSED, on the surface where it was measured — BUG-0086.

    An EXP naming two parents resolved to NO root, and both readers took that for "nothing to
    compare": on a scaffolded project this exact `create-task` returned rc 0 and `validate`
    reported zero errors, while the single-parent control was correctly refused. The unit-level
    twins are `test_kernel.test_an_origin_with_a_parent_outside_the_root_is_refused_at_creation`
    and `test_report.test_an_origin_that_reaches_the_root_through_only_one_of_its_parents_is_refused`.
    """
    _approved_question(project)
    second = project.harness("capture", "RQ", stdin=json.dumps(
        dict(_RQ, title="Zweite Frage", question="Senkt ein Cache die Laufzeit?"),
        ensure_ascii=False))
    assert second.returncode == 0, second.stdout + second.stderr
    stray = project.harness("capture", "HYP", stdin=json.dumps(
        dict(_HYP, derives_from="RQ-0002"), ensure_ascii=False))
    assert stray.returncode == 0, stray.stdout + stray.stderr
    captured = project.harness("capture", "EXP", stdin=json.dumps(
        _experiment(["HYP-0001", "HYP-0002"]), ensure_ascii=False))
    assert captured.returncode == 0, captured.stdout + captured.stderr

    refused = project.harness(
        "create-task", "--product-requirement", "RQ-0001", "--derives-from", "EXP-0001",
        "--type", "research", "--assigned-role", "researcher", "--acceptance-ref", "AC-1",
        "--allowed-scope", "src/", "--expected-output", "src/messlauf.py")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "HYP-0002" in refused.stderr and "RQ-0002" in refused.stderr, refused.stderr


# ---------------------------------------------------------------- scenario 3: the two claims §4 makes
def test_every_experiment_needs_a_delivery_approval_whatever_its_size(project):
    """`DESIGNED -> APPROVED` is gated for EVERY experiment, and nothing about one says otherwise.

    There is no size, class or scale anywhere in an `EXP` — `backlog_types.REQUIRED_FIELDS["EXP"]`
    and `OPTIONAL_FIELDS` declare none — so a rule that applied to large ones only would have
    nothing to read. The kernel gates the edge unconditionally.

    §4 of `research-team/constitution/AGENTS.md` said "at class `large`" until this round and now
    says "every"; the constitution cites no test (it has no room for one — its lead package sits on
    its recorded ceiling), so this is the measurement behind that sentence and not a pointer it
    holds.
    """
    from kernel.backlog_types import OPTIONAL_FIELDS, REQUIRED_FIELDS
    declared = set(REQUIRED_FIELDS["EXP"]) | set(OPTIONAL_FIELDS.get("EXP", ()))
    assert "class" not in declared, declared

    _approved_question(project)
    assert project.harness("capture", "EXP",
                           stdin=json.dumps(_experiment(["HYP-0001", "RQ-0001"]),
                                            ensure_ascii=False)).returncode == 0
    refused = project.harness("transition", "EXP-0001", "APPROVED")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "delivery approval commits" in refused.stderr, refused.stderr
    code, err = project.mint("delivery", "EXP-0001")
    assert code == 0, err
    assert project.status("EXP-0001") == "APPROVED"


def test_an_experiment_reaches_analyzed_unrefused_and_the_merge_is_where_the_report_is_demanded(
        project):
    """The report is demanded at the MERGE, not at the transition — which is a real difference.

    `transition EXP ANALYZED` succeeds with an empty `evidence_refs`. What refuses is the state
    validator, and the gate that reads it is `gate_memory_complete` on the merge command, so an
    experiment stands in `ANALYZED` with no report for as long as nobody merges. §2 (point 4) of
    `research-team/constitution/AGENTS.md` said "may not reach `ANALYZED`" until this round and now
    names the merge; same standing as the sibling above — the measurement, not a pointer the
    constitution holds.

    What the merge reads is the FIELD, not a file: an `evidence_refs` naming anything satisfies it.
    So this measures the empty one, and claims nothing about the report behind an entry.
    """
    _approved_question(project)
    assert project.harness("capture", "EXP",
                           stdin=json.dumps(_experiment(["HYP-0001", "RQ-0001"]),
                                            ensure_ascii=False)).returncode == 0
    assert project.mint("delivery", "EXP-0001")[0] == 0
    for target in ("RUNNING", "COMPLETED", "ANALYZED"):
        moved = project.harness("transition", "EXP-0001", target)
        assert moved.returncode == 0, moved.stdout + moved.stderr
    assert project.state().read_item("EXP-0001")["evidence_refs"] == []

    merge = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": project.path,
             "tool_input": {"command": "git merge rq/RQ-0001-chunkgröße"}}
    shut, err = project.hook("gate_memory_complete.py", merge)
    assert shut == 2, err
    assert "ANALYZED without evidence_refs" in err, err


# ---------------------------------------------------------------- scenario 4: the report itself
def test_a_rendered_report_reaches_the_tray_through_the_kernel(project):
    """BUG-0085: §6 assigns the report, §17 demands it, and nothing could write it.

    The whole chain on the scaffolded project, in the order a report-writer meets it: the tray is
    closed to the write tools (rc 2 -- that refusal is correct and stays), the task's staging
    directory is open (rc 0), and `freeze-report` is the move between the two. What makes it the
    END of the chain rather than a file copy: the filed path lands in the experiment's
    `evidence_refs`, which is the field `gate_memory_complete` blocks the merge on -- so before
    this route the report was required and unwritable at the same time.

    The lint is run on the filed report because it is the second reader of that tray and finds a
    report by POSITION: the kernel constant and `scripts/report_lint.py`'s shape have to agree,
    and nothing but a run through both would say so.
    """
    _approved_question(project)
    assert project.harness("capture", "EXP", stdin=json.dumps(_experiment("HYP-0001"),
                                                              ensure_ascii=False)).returncode == 0
    assert project.mint("delivery", "EXP-0001")[0] == 0
    created = project.harness(
        "create-task", "--product-requirement", "RQ-0001", "--derives-from", "EXP-0001",
        "--type", "research", "--assigned-role", "report-writer", "--acceptance-ref", "AC-1",
        "--allowed-scope", "project_memory/staging/", "--expected-output", "reports/EXP-0001.tex")
    assert created.returncode == 0, created.stdout + created.stderr

    report_name = "EXP-0001-Größe.tex"
    tray_write = {"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": project.path,
                  "tool_input": {"file_path": os.path.join(
                      project.path, "project_memory", "reports", report_name),
                      "content": "x"}}
    shut, err = project.hook("gate_write_scope.py", tray_write)
    assert shut == 2, "the tray is open to the write tools: %s" % err

    staged = os.path.join(project.path, "project_memory", "staging", "TSK-0001")
    open_here = dict(tray_write, tool_input={"file_path": os.path.join(staged, report_name),
                                             "content": "x"})
    assert project.hook("gate_write_scope.py", open_here)[0] == 0, "staging is closed too"
    os.makedirs(staged, exist_ok=True)
    with open(os.path.join(staged, report_name), "w", encoding="utf-8") as handle:
        handle.write("Der dynamische Arm proves die Hypothese bei 400 Belegen.")

    filed = project.harness("freeze-report", stdin=json.dumps(
        {"staging_key": "TSK-0001", "subject_id": "EXP-0001", "source_name": report_name}))
    assert filed.returncode == 0, filed.stdout + filed.stderr
    assert "reports/" + report_name in filed.stdout, filed.stdout
    assert os.path.isfile(os.path.join(project.path, "project_memory", "reports", report_name))
    assert not os.path.exists(os.path.join(staged, report_name)), "the staged copy stayed behind"
    assert project.state().read_item("EXP-0001")["evidence_refs"] == ["reports/" + report_name]

    # the second reader of the same tray: the lint finds the filed report by its position
    lint = _run([sys.executable, "-B", os.path.join("scripts", "report_lint.py")],
                project.path, project.env)
    assert lint.returncode == 0, lint.stdout + lint.stderr
    assert report_name in lint.stdout, lint.stdout

    # ...and the merge is no longer blocked on the field the route just filled
    for target in ("RUNNING", "COMPLETED", "ANALYZED"):
        assert project.harness("transition", "EXP-0001", target).returncode == 0
    merge = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": project.path,
             "tool_input": {"command": "git merge rq/RQ-0001-chunk"}}
    code, err = project.hook("gate_memory_complete.py", merge)
    assert "ANALYZED without evidence_refs" not in err, err


def test_a_rendered_report_is_found_where_the_kit_actually_renders_it(project):
    """§17's report, linted where §6 puts it: `project_memory/reports/EXP-*.{tex,pdf,html}`.

    The last link of the chain, and the one with no kernel behind it: the report-writer renders a
    file into the state directory's `reports/` tray, and `scripts/report_lint.py` is the only
    thing in the kit that ever reads it. Driven as a PROCESS in the scaffolded project, because
    which files the lint discovers is a question about that project's layout.

    Both entry points, because they select their targets separately: the stand-alone `main()` a
    role runs, and the `--quality-stage` call `scripts/quality.py` makes.
    """
    tray = os.path.join(project.path, "project_memory", "reports")
    assert os.path.isdir(tray), "the scaffold ships no reports tray"
    # The name is deliberately hostile, and one file measures the whole way in and out: git escapes
    # a non-ASCII path unless it is asked not to, and the escaped spelling opens no file; the Greek
    # pair is outside the Windows codepage, so an unreconfigured stdout raises on the way back out
    # and the stage dies before any finding is printed.
    report = "EXP-0001-Größe-αβ.tex"
    with open(os.path.join(tray, report), "w", encoding="utf-8") as handle:
        handle.write("Der dynamische Arm proves die Hypothese.\n")

    lint = _run([sys.executable, "-B", os.path.join("scripts", "report_lint.py")],
                project.path, project.env)
    assert lint.returncode == 0, lint.stdout + lint.stderr
    assert "causal claim without a hedge" in lint.stdout, lint.stdout
    assert report in lint.stdout, lint.stdout

    staged = _run([sys.executable, "-B", os.path.join("scripts", "report_lint.py"),
                   "--quality-stage"], project.path, project.env)
    assert staged.returncode == 1, staged.stdout + staged.stderr
    assert report in staged.stdout, staged.stdout

    # ...and the machinery the same tray ships is not a report: a subdirectory of the tray holds
    # the render's inputs, and linting them would flood every run with findings about KaTeX.
    assert "katex" not in lint.stdout.lower(), lint.stdout


def test_the_stylesheet_of_a_rendered_html_report_is_not_read_as_a_result(project):
    """§17's experiment report is HTML, so a rendered one carries a stylesheet — and `width: 100%`
    is a percentage with no denominator, which is precisely the shape the "result without an n"
    pattern exists to catch. Measured on the tray the scaffold ships: without this, the shipped
    `experiment_report.template.html` alone puts one finding into every pipeline run, for ever.

    Both directions in one file, because "found nothing" and "read nothing" look the same: the
    style block must be silent and the sentence beneath it must not be.
    """
    tray = os.path.join(project.path, "project_memory", "reports")
    # The second percentage sits in a start tag whose attributes WRAP. A renderer breaks a long tag
    # over two lines, and a reader that ended a tag at the newline handed that one straight to the
    # patterns — so the style block and the wrapped tag are the same rule seen from two sides.
    with open(os.path.join(tray, "EXP-0001.html"), "w", encoding="utf-8") as handle:
        handle.write("<html><head><style>\n"
                     "  table { width: 100%; }\n"
                     "</style></head><body>\n"
                     "<table\n"
                     "   style=\"width: 100%\">\n"
                     "<tr><td>x</td></tr>\n"
                     "</table>\n"
                     "<p>Der dynamische Arm proves die Hypothese.</p>\n"
                     "</body></html>\n")
    lint = _run([sys.executable, "-B", os.path.join("scripts", "report_lint.py")],
                project.path, project.env)
    assert lint.returncode == 0, lint.stdout + lint.stderr
    assert "result without an n" not in lint.stdout, lint.stdout
    assert "causal claim without a hedge" in lint.stdout, lint.stdout
    # the shipped template travels the same road, and it is the file that measured this
    assert "experiment_report.template.html" not in lint.stdout, lint.stdout


def test_prose_with_an_inequality_pair_is_not_read_as_markup(project):
    """A research report is full of `<` and `>`, and both belong to the claim, not to a tag.

    The counter-direction of the test above, and the one that costs a FINDING rather than adding a
    false one: a reader that treated every `<`…`>` on a line as markup blanked the middle of the
    sentence, and the number the lint exists to ask about went with it. Two shapes, because they
    fail through different patterns — a percentage between two bounds, and a LaTeX inline formula
    around a causal verb.

    Each case carries a control without the brackets: without one, asserting that a finding appears
    proves nothing about the brackets.
    """
    tray = os.path.join(project.path, "project_memory", "reports")
    cases = {
        "EXP-0001.md": "Bei Werten < 30 stieg der Anteil auf 95% in Gruppen > 10 Personen.\n",
        "EXP-0002.md": "Bei Werten unter 30 stieg der Anteil auf 95% in vielen Gruppen.\n",
        "EXP-0003.tex": "Fuer $n < 400$ proves der Arm die Wirkung, $d > 0{,}8$.\n",
        "EXP-0004.tex": "Fuer n gleich 400 proves der Arm die Wirkung.\n",
    }
    for name, text in cases.items():
        with open(os.path.join(tray, name), "w", encoding="utf-8") as handle:
            handle.write(text)
    lint = _run([sys.executable, "-B", os.path.join("scripts", "report_lint.py")],
                project.path, project.env)
    assert lint.returncode == 0, lint.stdout + lint.stderr
    for name in sorted(cases):
        assert name in lint.stdout, (name, lint.stdout)


def test_a_bom_in_front_of_a_heading_does_not_turn_it_into_a_claim(project):
    """`lint` skips a heading because it starts with `#` — and a BOM read as text stands in front
    of that `#`, so the line stops being a heading and its numbers become claims.

    An editor writing a BOM is ordinary on Windows, which is where the report-writer runs, so this
    is the shape a first false finding really arrives in. The sentence in the body is the control:
    the file must still be READ, not skipped whole.
    """
    tray = os.path.join(project.path, "project_memory", "reports")
    with open(os.path.join(tray, "EXP-0001.md"), "w", encoding="utf-8-sig") as handle:
        handle.write("# Ergebnisse: 95% besser\n\nDer Arm proves die Wirkung.\n")
    lint = _run([sys.executable, "-B", os.path.join("scripts", "report_lint.py")],
                project.path, project.env)
    assert lint.returncode == 0, lint.stdout + lint.stderr
    assert "result without an n" not in lint.stdout, lint.stdout
    assert "\ufeff" not in lint.stdout, lint.stdout   # nor into the output
    assert "causal claim without a hedge" in lint.stdout, lint.stdout
