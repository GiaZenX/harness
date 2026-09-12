#!/usr/bin/env python3
"""The pointer sweep (FR-0007, PR-0008 AC-7) -- the MECHANICAL half of the comment duty.

WHAT THIS FILE HOLDS. `kernel.report.pointer_sweep` reads the files a project's own roles wrote and
reports every backtick citation that resolves at nothing: a test node the tree does not define, an
item id the store holds neither active nor archived. The duty it serves is DEC-0008 / SR-0008 -- a
comment carries the WHY as a pointer, a property claim becomes a test the comment NAMES -- and the
half no machine can decide (did a property claim name a test AT ALL) stays with the roles, which the
constitutions say in the same breath.

EVERY TEST HERE DRIVES THE RUNNING CODE over a real store the kernel wrote, and the pilot tests run
the SHIPPED command through the project's own entry point -- never the function with a dictionary,
because what has to hold is what a role's command line answers.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

import conftest

ROOT = conftest.ROOT
TEAM_KITS = conftest.TEAM_KITS

sys.path.insert(0, TEAM_KITS)
from kernel import report  # noqa: E402
from kernel.state import ProjectState  # noqa: E402

PR_FIELDS = {"title": "The workbench", "class": "normal", "problem": "p", "goal": "g",
             "acceptance_criteria": [{"id": "AC-1", "text": "t"}], "invariants": [],
             "out_of_scope": [], "priority": "high", "user_story": "As the lead"}
KITS = ("dev-team", "office-team", "research-team")


def _write(path, text, binary=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if binary:
        with io.open(path, "wb") as handle:
            handle.write(text)
        return
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _git(repo, *argv):
    return subprocess.run(["git"] + list(argv), cwd=repo, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


def _tracked_project(tmp_path):
    """A git repository with a kernel-written store -- the shape the sweep asks git about."""
    repo = str(tmp_path / "project")
    os.makedirs(os.path.join(repo, "project_memory"), exist_ok=True)
    state = ProjectState(os.path.join(repo, "project_memory"))
    state.capture("PR", dict(PR_FIELDS))
    assert _git(repo, "init", "-q").returncode == 0
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    return repo, state


def _commit_everything(repo):
    assert _git(repo, "add", "-A").returncode == 0
    _git(repo, "commit", "-q", "-m", "state")


def test_a_dead_test_pointer_and_a_dead_item_pointer_are_both_reported(tmp_path):
    """The two finding classes the sweep reads, and the silences beside them.

    THE TWO FINDINGS: a `<path>::<test>` whose test the tree does not define, and an item id this
    store holds neither active nor archived. Both are written the way a role writes them -- in a
    backtick span inside a source file -- and both name the FILE they stand in, because that is what
    somebody has to open.

    THE SILENCES ARE MEASURED IN THE SAME RUN, and each is a decision `pointer_sweep` states rather
    than an accident: a pointer that RESOLVES, a test cited by bare file name (the resolver reads a
    path from the project root and would have to guess), a span that is not either shape at all, a
    span carrying a space (pasted runner output, not a citation), and a file git does not track.
    Without the silences this reader would be a grep, and a grep over prose is what the house rule
    forbids.
    """
    repo, state = _tracked_project(tmp_path)
    _write(os.path.join(repo, "tests", "test_real.py"), "def test_here():\n    assert True\n")
    _write(os.path.join(repo, "src", "service.py"), "\n".join([
        '"""The reason is `PR-0001`, and the property is held by',
        '`tests/test_real.py::test_here`.',
        "",
        "Gone: `tests/test_real.py::test_renamed_away` and `BUG-0404`.",
        "Not read: `test_real.py::test_here` (bare name), `just/a/path.py`, `--flag`,",
        "`FAILED tests/test_real.py::test_here` (a run, not a citation).",
        '"""',
        "value = 1",
    ]))
    _commit_everything(repo)
    # written AFTER the commit, so git does not carry it: "the project's own code" is what the
    # project committed, and a file nobody tracks is not part of that answer
    _write(os.path.join(repo, "untracked.py"), "# `TSK-0404`\n")

    findings = report.pointer_sweep(state)
    assert [(f["item"], f["severity"]) for f in findings] == [
        ("src/service.py", "error"), ("src/service.py", "error")], findings
    messages = " | ".join(f["message"] for f in findings)
    assert "tests/test_real.py::test_renamed_away" in messages, messages
    assert "BUG-0404" in messages, messages
    for silent in ("test_here`", "just/a/path.py", "--flag", "FAILED", "TSK-0404", "PR-0001"):
        assert messages.count(silent) == 0, (
            "the sweep reported %r, which it states it does not read" % silent)


def test_the_decoration_around_a_citation_is_not_part_of_it(tmp_path):
    """`**DEC-0008**`, `PR-0001.`, a wrapped name and a parametrised case are all one pointer.

    A READER THAT SEES FEWER SPELLINGS THAN IT CLAIMS is the finding class of the last generation,
    so both ends are measured here: the decorated forms are SEEN (an id that rots inside `**...**`
    would otherwise be silent), and a leading `.` or `/` SURVIVES -- stripping every non-word
    character from the left turned `.claude/hooks/test_gates.py::x` into a path that does not exist
    and the sweep reported its own docstring.
    """
    undecorated = report._undecorated_citation
    for decorated in ("**PR-0001**", "PR-0001.", "PR-0001,", "(PR-0001)", "PR-0001;", "'PR-0001'"):
        assert undecorated(decorated) == "PR-0001", decorated
    assert undecorated("tools/t.py::test_x[case-2]") == "tools/t.py::test_x"
    for path in (".claude/hooks/test_gates.py::x", "/abs/t.py::x", "./rel/t.py::x"):
        assert undecorated(path) == path, path
    glued = report._CITATION_GLUE_RX.sub("", "tools/test_x.py::test_a_very_long\n    # _name_here")
    assert glued == "tools/test_x.py::test_a_very_long_name_here", glued
    assert report._CITATION_GLUE_RX.sub("", "FAILED tools/t.py::x") == "FAILED tools/t.py::x", (
        "a plain space is glued out, so pasted runner output becomes a citation shape")


def test_a_project_git_cannot_list_refuses_instead_of_sweeping_clean(tmp_path):
    """No subject is NOT no findings -- and the two print the same unless one of them refuses.

    The reassuring answer is the dangerous one here: a sweep over zero files reports zero dead
    pointers, which reads exactly like a clean project. `PointerSweepUnavailable` is why the command
    exits 1 with a sentence instead.
    """
    repo = str(tmp_path / "loose")
    os.makedirs(os.path.join(repo, "project_memory"), exist_ok=True)
    state = ProjectState(os.path.join(repo, "project_memory"))
    state.capture("PR", dict(PR_FIELDS))
    _write(os.path.join(repo, "src", "x.py"), "# `BUG-0404`\n")
    with pytest.raises(report.PointerSweepUnavailable) as refusal:
        report.pointer_sweep(state)
    assert "git could not list" in str(refusal.value), refusal.value

    environment = dict(os.environ, PYTHONPATH=TEAM_KITS, PYTHONIOENCODING="utf-8")
    run = subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root",
                          os.path.join(repo, "project_memory"), "sweep-pointers"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         env=environment, cwd=repo, timeout=300)
    assert run.returncode == 1, run.stdout + run.stderr
    assert "has no subject" in run.stdout, run.stdout
    assert "0 dead pointer" not in run.stdout, run.stdout


def test_a_kit_tree_inside_the_project_is_not_the_projects_own_code(tmp_path):
    """The kit's source repository sweeps its own code, not the kits checked out inside it.

    MEASURED before this rule, over the kit's source repository: of 118 findings, 100 were the
    placeholder ids of an EXAMPLE project in kernel docstrings (`PROC-0001`, `WFR-0001`) -- ids no
    store is meant to answer. A directory that HOLDS a kit is a kits root, decided by the kernel's
    own `hashing.is_kit_dir`, and everything under it is kit material for the same reason the
    installed `.claude/` is.
    """
    repo, state = _tracked_project(tmp_path)
    _write(os.path.join(repo, "src", "own.py"), "# `BUG-0404`\n")
    kit_source = os.path.join(repo, "team-kits", "demo-team")
    _write(os.path.join(kit_source, "VERSION"), "2026.01.01-1\n")
    os.makedirs(os.path.join(kit_source, "agents"), exist_ok=True)
    os.makedirs(os.path.join(kit_source, "constitution"), exist_ok=True)
    _write(os.path.join(kit_source, "constitution", "AGENTS.md"), "# `BUG-0405`\n")
    _write(os.path.join(repo, "team-kits", "kernel", "shared.py"), "# `BUG-0406`\n")
    _commit_everything(repo)

    from kernel.hashing import is_kit_dir
    assert is_kit_dir(kit_source), "the fixture is not a kit by the kernel's own predicate"
    named = " | ".join(f["message"] for f in report.pointer_sweep(state))
    assert "BUG-0404" in named, named
    assert "BUG-0405" not in named and "BUG-0406" not in named, (
        "a kit tree inside the project was swept as the project's own code: %s" % named)


def _scaffolded_pilot(tmp_path, kit):
    """A REAL installation of `kit` under `tmp_path` -- (repo path, environment).

    ONE spelling of the two-step install for every pilot in this file, because the order is a
    precondition and not a convention: the scaffold refuses a project with no
    `project_memory/project_config.yaml`, which is the order a real entry session walks too. The
    PowerShell twin is the one asked for here; the POSIX twin needs the probe
    `tools/test_hooks.py::_scaffold_shell` performs (a bash that can see a Windows path AND reach an
    interpreter with PyYAML), and that probe lives with the tests that own the launchers. THE COST
    IS NAMED: on a machine without PowerShell every pilot in this file skips, so the acceptance
    lines they hold are measured on the developer host and on no CI that lacks it.
    """
    if os.name != "nt" or not shutil.which("powershell"):
        pytest.skip("the scaffold's PowerShell twin runs on Windows")
    home = tmp_path / "home"
    staging = home / ".claude" / "team-kits"
    shutil.copytree(TEAM_KITS, str(staging), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    repo = str(tmp_path / "project")
    os.makedirs(repo, exist_ok=True)
    environment = dict(os.environ, HOME=str(home), USERPROFILE=str(home),
                       PYTHONIOENCODING="utf-8")
    for script, flag in (("init_project_memory.ps1", "-Team"), ("scaffold_team.ps1", "-Team")):
        done = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             os.path.join(str(staging), script), flag, kit],
            cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=900, env=environment)
        assert done.returncode == 0, script + ":" + done.stdout + done.stderr
    return repo, environment


def test_a_projects_own_script_is_swept_while_the_kits_copy_beside_it_is_not(tmp_path):
    """`BUG-0265` / `H183` AC-1, the READING end: what the sweep skips is the FILES the installer
    recorded, not the DIRECTORY they lie in.

    THE DEFECT: `installed_kit_paths` could only name `INSTALLER_SCRIPT_DIRS = ("scripts", "tools")`,
    so a project that put its own script next to the kit's had it unswept and no finding said so.
    The installer now writes `.claude/kit_repo_files.json`
    (`tools/test_hooks.py::test_the_installer_records_which_files_it_places_outside_the_hook_bundle`
    measures the WRITING end, on both twins); this is the reading end, through the project's own
    entry point, with the exit code a role sees.

    BOTH ENDS IN ONE RUN, because either alone is passed by a broken reader:
      * the project's own file under `scripts/` AND under `tools/` is reported -- red before the
        change, where the sweep answered rc 0 and 0 dead pointers;
      * not one of the files the record names is reported, and that silence is worth something
        because at least one of them WOULD speak when it is read -- asked with
        `report.findings_in_text`, the reader that RUNS, never a copy of its loop. A fix that simply
        dropped the exclusion would pass the first end and fail this one.

    THE KIT IS `office-team` because it is the one whose templates fill BOTH script directories;
    the same record is written by every kit, and the sibling pilot above walks all three.
    """
    repo, environment = _scaffolded_pilot(tmp_path, "office-team")
    recorded = json.loads(io.open(os.path.join(repo, ".claude", "kit_repo_files.json"),
                                  encoding="utf-8-sig").read())
    assert recorded.get("kit") == "office-team", recorded
    in_script_dirs = sorted(one for one in (recorded.get("repo_files") or [])
                            if one.split("/")[0] in report.INSTALLER_SCRIPT_DIRS)
    assert in_script_dirs, (
        "this kit records no file in %s, so the exclusion this test is about has no subject"
        % (report.INSTALLER_SCRIPT_DIRS,))

    assert _git(repo, "init", "-q").returncode == 0
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    _commit_everything(repo)
    state = ProjectState(os.path.join(repo, "project_memory"))
    speaking = [one for one in in_script_dirs if _reading_would_speak(state, repo, one)]
    assert speaking, (
        "not one of the recorded files in %s produces a finding when it IS read, so their absence "
        "from the sweep measures nothing" % (report.INSTALLER_SCRIPT_DIRS,))

    clean = _shipped_sweep(repo, environment)
    assert (clean.returncode, _dead_pointers(clean.stdout)) == (0, 0), (
        "the kit's own copies are reported: rc %d, %s -- %s"
        % (clean.returncode, _dead_pointers(clean.stdout), clean.stdout[:3000]))

    own = ["%s/a_file_this_project_wrote.py" % one for one in report.INSTALLER_SCRIPT_DIRS]
    for rel in own:
        _write(os.path.join(repo, *rel.split("/")),
               '"""The reason is `DEC-9999`, and the property is held by\n'
               '`src/test_nothing.py::test_gone`.\n"""\nVALUE = 1\n')
    _commit_everything(repo)
    planted = _shipped_sweep(repo, environment)
    assert (planted.returncode, _dead_pointers(planted.stdout)) == (1, 2 * len(own)), (
        "the project's own scripts were not swept: rc %d, %s -- %s"
        % (planted.returncode, _dead_pointers(planted.stdout), planted.stdout[:3000]))
    for rel in own:
        assert rel in planted.stdout, planted.stdout[:3000]
    reported = [one for one in in_script_dirs if one in planted.stdout]
    assert not reported, (
        "a file the installer recorded as its own was reported: %r" % (reported,))


@pytest.mark.parametrize("kit", KITS)
def test_the_root_files_the_sweep_skips_are_installed_and_would_be_noisy(tmp_path, kit):
    """The tripwire on `SCAFFOLDED_ROOT_FILES`, at BOTH ends, on a REAL scaffold of every kit.

    THE ENUMERATION IS UNAVOIDABLE for the ROOT FILES -- the kernel holds no other reader for the
    files an installer copies to the project root -- so it owes both measurements the house rule
    asks for (`INSTALLER_SCRIPT_DIRS` is since `BUG-0265` the fallback for a project installed
    before the record existed, and the ends below hold for it in exactly that role):

      * NOT DEAD: every name in the tuple that the scaffold really writes is there afterwards, and
        at least one is (a tuple none of whose entries ever appears would silently skip nothing);
      * NOT NEEDLESS: reading one of them would really produce findings against a fresh store,
        because the constitution cites the items and tests of the kit's SOURCE repository -- asked
        with `report.findings_in_text`, the reader that RUNS, never with a copy of its loop.

    AND THE ACCEPTANCE LINE OF THE WHOLE MECHANIC, through the project's own entry point in every
    kit (the reach `DEC-0080` (1) asks to be measured in three places rather than one): a freshly
    scaffolded project with no line of its own code answers rc 0 and ZERO dead pointers, and one
    real dead pointer planted in its own `src/` answers rc 1 and exactly two, naming the file and
    both shapes. Both ends, because either alone is passed by a broken sweep: the first by one that
    reports everything, the second by one that reports nothing.
    """
    repo, environment = _scaffolded_pilot(tmp_path, kit)

    present = [name for name in report.SCAFFOLDED_ROOT_FILES
               if os.path.isfile(os.path.join(repo, name))]
    assert present, (
        "%s: not one name in SCAFFOLDED_ROOT_FILES exists after a real scaffold, so the tuple "
        "skips nothing and every entry in it is dead" % kit)
    script_dirs = [name for name in report.INSTALLER_SCRIPT_DIRS
                   if os.path.isdir(os.path.join(repo, name))]
    assert script_dirs, (
        "%s: not one name in INSTALLER_SCRIPT_DIRS exists after a real scaffold" % kit)
    assert report.INSTALLER_SCRIPT_DIRS[0] == os.path.dirname(report_entry_point()), (
        "the first script directory is meant to BE the one the entry point lies in, so it cannot "
        "rot; it says %r while the entry point is %r"
        % (report.INSTALLER_SCRIPT_DIRS[0], report_entry_point()))

    assert _git(repo, "init", "-q").returncode == 0
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    _commit_everything(repo)
    state = ProjectState(os.path.join(repo, "project_memory"))

    # THE ACCEPTANCE LINE: a project with no line of its own code sweeps to ZERO, through the
    # SHIPPED command and with the exit code a role sees. Measured before the derivation of
    # `installed_kit_paths` existed: 39 (dev) / 27 (office) / 30 (research) findings here, all of
    # them inside `.agents/`, `.codex/`, `scripts/` or `tools/`.
    clean = _shipped_sweep(repo, environment)
    assert (clean.returncode, _dead_pointers(clean.stdout)) == (0, 0), (
        "%s: a freshly scaffolded project is not clean: rc %d, %s\n%s"
        % (kit, clean.returncode, _dead_pointers(clean.stdout), clean.stdout[:3000]))
    assert not report.pointer_sweep(state), report.pointer_sweep(state)

    # ...and it is not clean because it reads nothing: one real dead pointer in the project's OWN
    # code turns it red, names the file, and names both shapes.
    own = os.path.join(repo, "src", "pricing.py")
    _write(own, '"""The reason is `DEC-9999`, and the property is held by\n'
                '`src/test_nothing.py::test_gone`.\n"""\nVALUE = 1\n')
    _commit_everything(repo)
    planted = _shipped_sweep(repo, environment)
    assert (planted.returncode, _dead_pointers(planted.stdout)) == (1, 2), (
        "%s: the planted pointers did not arrive: rc %d, %s\n%s"
        % (kit, planted.returncode, _dead_pointers(planted.stdout), planted.stdout[:3000]))
    assert "src/pricing.py" in planted.stdout and "DEC-9999" in planted.stdout, planted.stdout
    assert "src/test_nothing.py::test_gone" in planted.stdout, planted.stdout
    os.remove(own)
    _commit_everything(repo)

    # NOT NEEDLESS: each skipped name really would speak when it IS read -- asked with the reader
    # that RUNS (`report.findings_in_text`), never with a copy of its loop
    would_speak = [name for name in present + script_dirs
                   if _reading_would_speak(state, repo, name)]
    assert would_speak, (
        "%s: none of %s produces a finding when it IS read, so skipping them buys nothing"
        % (kit, present + script_dirs))
    assert not [f for f in report.pointer_sweep(state)
                if f["item"].split("/")[0] in present + script_dirs], (
        "%s: a path the sweep says it skips was reported anyway" % kit)


def report_entry_point():
    """Where the kernel itself says the entry point is installed -- never a second spelling."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.cli import ENTRY_POINT
    return ENTRY_POINT


def _shipped_sweep(repo, environment):
    return subprocess.run([sys.executable, "-B", os.path.join(repo, "scripts", "harness.py"),
                           "sweep-pointers"],
                          cwd=repo, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=environment, timeout=900)


def _dead_pointers(stdout):
    """The COUNT the command printed, or None -- so a sweep that prints nothing is not read as 0."""
    found = re.search(r"(\d+) dead pointer\(s\)", stdout)
    return int(found.group(1)) if found else None


def _reading_would_speak(state, repo, name):
    """Would reading this file (or this directory) produce a finding? -- with the reader that RUNS.

    `report.findings_in_text` and not a copy of its loop: a copy answers for itself, so a narrowing
    of the sweep would leave this tripwire saying "this entry is needed" about a reader that no
    longer reads that way (verifier round 1, R3).
    """
    path = os.path.join(repo, name)
    files = [path]
    if os.path.isdir(path):
        files = [os.path.join(base, one)
                 for base, _dirs, names in os.walk(path) for one in sorted(names)]
    for one in files:
        try:
            with io.open(one, encoding="utf-8") as handle:
                text = handle.read()
        except (OSError, UnicodeDecodeError):
            continue
        if report.findings_in_text(state, os.path.relpath(one, repo), text):
            return True
    return False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
