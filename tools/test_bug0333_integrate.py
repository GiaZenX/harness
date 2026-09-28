"""BUG-0333 / DEC-0125: one goal's parallel work branches reach ONE united branch through the kit.

The field circle (synaipse, 2026-09-27/28): `gate_git` reads every `git merge` naming a goal as its
delivery and refuses it before the goal's full verdict, while that verdict can only be taken on the
united tree. The route DEC-0125 builds is a kernel door, `integrate <GOAL>`, that unites the goal's
branches on `integrate/<GOAL>` in a worktree of its own and never writes the delivery base; the
delivery merge of that branch keeps the full verdict rule, and gate_git's refusal names the door.

Everything here runs the part that RUNS: the door through `kernel.cli.main` against a real git
repository, the gate as a hook PROCESS with JSON on stdin (`test_hooks.run_hook_process`).
"""
import importlib.util
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_hooks import (HOOKS, ROOT, _bash, capture_evidence, capture_root_item,  # noqa: E402
                        qa_kinds, run_hook_process)

sys.path.insert(0, os.path.join(ROOT, "team-kits"))
from kernel import cli, integrate  # noqa: E402

pytest.importorskip("yaml")

GOAL = "PR-0001"


def _git(repo, *args, check=True):
    result = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=60)
    if check:
        assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result


def _commit_file(repo, branch, name, text, start="main"):
    """A work branch off `start` carrying one committed file; the checkout goes back to main."""
    _git(repo, "checkout", "-q", "-B", branch, start)
    with open(os.path.join(str(repo), name), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    _git(repo, "add", name)
    _git(repo, "commit", "-qm", "work on %s" % branch)
    _git(repo, "checkout", "-q", "main")


def _tip(repo, ref):
    return _git(repo, "rev-parse", ref).stdout.strip()


def _refs(repo):
    """Every ref and every worktree -- what "git did not move" is measured on."""
    return (_git(repo, "for-each-ref", "--format=%(refname) %(objectname)").stdout,
            _git(repo, "worktree", "list", "--porcelain").stdout)


def _files_on(repo, ref):
    return set(_git(repo, "ls-tree", "-r", "--name-only", ref).stdout.split())


def _door(repo, *args):
    return cli.main(["--root", os.path.join(str(repo), "project_memory"),
                     integrate.COMMAND] + list(args))


@pytest.fixture
def goal_repo(tmp_path):
    """A project with goal PR-0001 committed on `main`, and the checkout standing on `main`.

    The repo sits one level down so the door's sibling worktree lands inside this test's own
    temporary directory.
    """
    repo = tmp_path / "project"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "core.autocrlf", "false")
    capture_root_item(repo)
    with open(str(repo / "app.txt"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("base\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    return repo


def test_a_goal_with_two_work_branches_reaches_one_united_branch(goal_repo):
    """BUG-0333 AC-1: two parallel branches of one goal -> one branch holding both, base untouched.

    Also the field detail that made a plain merge fail in synaipse (forensics section 3): an
    untracked file in the MAIN checkout with the name a work branch adds. The door merges in its
    own worktree, so the main tree's clutter is not in the way and is left as it was.
    """
    _commit_file(goal_repo, "feat/PR-0001-a", "a.txt", "a\n")
    _commit_file(goal_repo, "feat/PR-0001-b", "b.txt", "b\n")
    with open(str(goal_repo / "a.txt"), "w", encoding="utf-8") as handle:
        handle.write("untracked in the main checkout\n")
    base = _tip(goal_repo, "main")

    assert _door(goal_repo, GOAL) == 0

    united = integrate.integration_branch(GOAL)
    assert {"a.txt", "b.txt", "app.txt"} <= _files_on(goal_repo, united)
    for branch in ("feat/PR-0001-a", "feat/PR-0001-b", "main"):
        assert _git(goal_repo, "merge-base", "--is-ancestor", branch, united,
                    check=False).returncode == 0, branch
    assert _tip(goal_repo, "main") == base, "the door wrote the delivery base"
    assert _git(goal_repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"
    with open(str(goal_repo / "a.txt"), encoding="utf-8") as handle:
        assert handle.read() == "untracked in the main checkout\n"
    worktree = integrate.default_worktree(str(goal_repo), GOAL)
    assert os.path.isfile(os.path.join(worktree, "b.txt"))

    # ...and a second run, after one branch moved on, reuses the branch and adds only the new work
    _commit_file(goal_repo, "feat/PR-0001-b", "b2.txt", "b2\n", start="feat/PR-0001-b")
    assert _door(goal_repo, GOAL) == 0
    assert "b2.txt" in _files_on(goal_repo, united)
    assert _tip(goal_repo, "main") == base


def test_a_branch_of_another_goal_is_never_pulled_in(goal_repo):
    """Attribution by the goal id in the branch name -- exact id, any case, and never a branch
    that names a second goal as well (whose work that carries is not decidable)."""
    _commit_file(goal_repo, "feat/PR-0001-a", "a.txt", "a\n")
    _commit_file(goal_repo, "feat/PR-0002-x", "x.txt", "x\n")
    _commit_file(goal_repo, "feat/PR-00011-longer", "z.txt", "z\n")
    _commit_file(goal_repo, "fix/PR-0001-and-PR-0002", "y.txt", "y\n")
    _commit_file(goal_repo, "integrate/PR-0002", "i.txt", "i\n")
    _commit_file(goal_repo, "pr/pr-0001-lowercase", "l.txt", "l\n")

    assert _door(goal_repo, GOAL) == 0

    files = _files_on(goal_repo, integrate.integration_branch(GOAL))
    assert {"a.txt", "l.txt"} <= files
    assert not files & {"x.txt", "z.txt", "y.txt", "i.txt"}, files

    chosen, skipped = integrate.sources_for(
        ["main", "feat/PR-0001-a", "feat/PR-0002-x", "feat/PR-00011-longer",
         "fix/PR-0001-and-PR-0002", "integrate/PR-0001", "integrate/PR-0002"], GOAL, "main")
    assert chosen == ["feat/PR-0001-a"]
    assert list(skipped) == ["fix/PR-0001-and-PR-0002"]


def test_a_conflict_stops_cleanly_and_leaves_nothing_of_the_run_behind(goal_repo):
    """A conflict: exit 1, the file named, the branch where this run found it -- also when an
    EARLIER source of the same run had already merged (all or nothing)."""
    _commit_file(goal_repo, "feat/PR-0001-a", "a.txt", "a\n")
    assert _door(goal_repo, GOAL) == 0
    united = integrate.integration_branch(GOAL)
    before = _tip(goal_repo, united)
    worktree = integrate.default_worktree(str(goal_repo), GOAL)

    # b merges cleanly (sorted before c), c then collides with b on the same file
    _commit_file(goal_repo, "feat/PR-0001-b", "shared.txt", "from b\n")
    _commit_file(goal_repo, "feat/PR-0001-c", "shared.txt", "from c\n")
    base = _tip(goal_repo, "main")
    assert _door(goal_repo, GOAL) == 1

    assert _tip(goal_repo, united) == before, "a half-merged run was left on the branch"
    assert _git(worktree, "status", "--porcelain").stdout.strip() == ""
    assert _git(worktree, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).returncode != 0
    assert _tip(goal_repo, "main") == base


def test_a_conflict_on_the_first_run_removes_the_branch_and_worktree_it_made(goal_repo, capsys):
    _commit_file(goal_repo, "feat/PR-0001-b", "shared.txt", "from b\n")
    _commit_file(goal_repo, "feat/PR-0001-c", "shared.txt", "from c\n")
    before = _refs(goal_repo)

    assert _door(goal_repo, GOAL) == 1

    assert "shared.txt" in capsys.readouterr().err
    assert _refs(goal_repo) == before
    assert not os.path.exists(integrate.default_worktree(str(goal_repo), GOAL))


@pytest.mark.parametrize("args, setup, reason", [
    (["BUG-0001"], None, "is not a goal"),
    (["PR-0009"], "branch", "no active item PR-0009"),
    ([GOAL], None, "no local branch carries"),
    ([GOAL, "--base", "feat/PR-0001-a"], "branch", "names a goal"),
    ([GOAL, "--base", "nowhere"], "branch", "is no local branch"),
    ([GOAL], "dirty", "is not clean"),
], ids=["not-a-goal", "no-item", "no-branch", "base-names-a-goal", "no-base", "dirty-worktree"])
def test_the_door_refuses_before_git_moves(goal_repo, capsys, args, setup, reason):
    """Each refusal by its OWN reason: a later check refusing the same line would otherwise stand
    in for a missing earlier one (measured: an rc-only version let mutations survive)."""
    if setup in ("branch", "dirty"):
        _commit_file(goal_repo, "feat/PR-0001-a", "a.txt", "a\n")
        _commit_file(goal_repo, "feat/PR-0001-b", "b.txt", "b\n")
    if setup == "dirty":
        assert _door(goal_repo, GOAL) == 0
        _commit_file(goal_repo, "feat/PR-0001-c", "c.txt", "c\n")
        with open(os.path.join(integrate.default_worktree(str(goal_repo), GOAL), "stray.txt"),
                  "w", encoding="utf-8") as handle:
            handle.write("uncommitted\n")
    before = _refs(goal_repo)
    capsys.readouterr()

    assert _door(goal_repo, *args) == 1

    assert reason in capsys.readouterr().err
    assert _refs(goal_repo) == before


def _hook(repo, command):
    return run_hook_process("gate_git.py", _bash(repo, command), repo)


def test_the_delivery_merge_of_the_integration_branch_still_needs_the_full_verdict(goal_repo):
    """DEC-0125 (3): the door changes nothing about delivery. The merge of `integrate/<GOAL>` into
    the base names the goal, so it is judged on the goal's full verdict -- refused with a partial
    one, opened with a complete one."""
    _commit_file(goal_repo, "feat/PR-0001-a", "a.txt", "a\n")
    assert _door(goal_repo, GOAL) == 0
    delivery = "git merge --no-ff %s" % integrate.integration_branch(GOAL)

    assert _hook(goal_repo, delivery).returncode == 2
    kinds = qa_kinds()
    for kind in kinds[:-1]:
        capture_evidence(goal_repo, kind=kind)
    refused = _hook(goal_repo, delivery)
    assert refused.returncode == 2 and kinds[-1] in refused.stderr, refused.stderr
    capture_evidence(goal_repo, kind=kinds[-1])
    assert _hook(goal_repo, delivery).returncode == 0


def _blocked(repo):
    assert cli.main(["--root", os.path.join(str(repo), "project_memory"), "evidence",
                     "--kind", qa_kinds()[0], "--result", "blocked", "--related", GOAL,
                     "--summary", "qa run", "--artifact-ref", "staging/TSK-0001/run.log",
                     "--run-command", "python -m pytest tests/ -q", "--run-scope", "full",
                     "--blocked-reason", "no browser on this host"]) == 0


@pytest.mark.parametrize("verdicts, command, goal", [
    ("none", "git merge --no-ff feat/PR-0001-b", GOAL),
    ("fail", "git merge --no-ff feat/PR-0001-b", GOAL),
    ("blocked", "git merge --no-ff feat/PR-0001-b", GOAL),
    ("partial", "git merge --no-ff feat/PR-0001-b", GOAL),
    # the field's P3 line: the goal named only in the message
    ("fail", 'git merge --no-ff feat/other -m "merge (PR-0001)"', GOAL),
    # nothing named: the any-fail fallback
    ("fail", "git merge --no-ff feat/other", "<GOAL>"),
    ("blocked", "git merge --no-ff feat/other", "<GOAL>"),
], ids=["none", "fail", "blocked", "partial", "named-in-message", "unnamed-fail", "unnamed-blocked"])
def test_every_verdict_refusal_of_a_merge_names_the_door(goal_repo, verdicts, command, goal):
    """DEC-0125 (2): the merge is still refused; the refusal now names the route that unites."""
    if verdicts == "fail":
        capture_evidence(goal_repo, kind=qa_kinds()[0], result="fail")
    elif verdicts == "blocked":
        _blocked(goal_repo)
    elif verdicts == "partial":
        capture_evidence(goal_repo, kind=qa_kinds()[0])

    refused = _hook(goal_repo, command)

    assert refused.returncode == 2, refused.stderr
    assert "scripts/harness.py %s %s" % (integrate.COMMAND, goal) in refused.stderr, refused.stderr
    assert "integrate/%s" % goal in refused.stderr


def test_a_push_refusal_does_not_send_the_role_to_the_door(goal_repo):
    """The route is for a MERGE; a refused push to the trunk has no use for it."""
    capture_evidence(goal_repo, kind=qa_kinds()[0], result="fail")
    refused = _hook(goal_repo, "git push origin main")
    assert refused.returncode == 2
    assert integrate.BRANCH_PREFIX not in refused.stderr, refused.stderr


def test_the_door_and_the_gate_read_a_branch_name_the_same_way():
    """The door's attribution and the gate's `TARGET_RX` are one reading of a branch name, asked
    of the SHIPPED gate module (loaded from the hooks directory), over names that split them if
    either changes case handling, id width or word boundaries."""
    spec = importlib.util.spec_from_file_location("gate_git_under_test",
                                                  os.path.join(HOOKS, "gate_git.py"))
    sys.path.insert(0, HOOKS)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    names = ["feat/PR-0001-a", "pr/pr-0001-x", "feat/PR-00011", "feat/PR-0001_x", "RQ-0003",
             "xPR-0001", "fix/PR-0001-and-PR-0002", "feat/PRD-0001", "main", "PR-123",
             "integrate/PR-0001", "feat/rq-12345-long"]
    for name in names:
        door = [match.group(0).upper() for match in integrate.ROOT_ID_RX.finditer(name)]
        gate_reads = [match.group(0).upper() for match in gate.TARGET_RX.finditer(name)]
        assert door == gate_reads, (name, door, gate_reads)
