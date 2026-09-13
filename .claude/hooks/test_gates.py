#!/usr/bin/env python3
"""
The measurement for the hooks this repo registers on its own provider (SR-0009, TSK-0003).

HOW IT MEASURES. Every gate is started as a REAL PROCESS with a JSON payload on stdin, against a
project built OUTSIDE this repo, and the verdict read off the exit code -- 2 is a refusal, 0 is an
allow. Nothing here imports a gate to call a function inside it, and nothing searches a file for a
sentence: two tests in this repo's history were satisfied by their own docstring, and one measured
its own environment instead of the thing under test.

BOTH DIRECTIONS, EVERY GATE. A gate that only refuses is indistinguishable from a gate that refuses
everything, and that failure is the expensive one here -- these hooks sit on the delegation path of
the session that builds the kits.

WHERE IT DOES NOT RUN. `python -m pytest tools/ -q` does not collect this file; it lives beside the
gates, not in the suite, because the gates are not part of any kit and `tools/` is the kits' suite.
Run it explicitly:  python -B -m pytest .claude/hooks/test_gates.py -q
"""
import ast
import concurrent.futures
import glob as globmodule
import hashlib
import inspect
import io
import json
import math
import os
import queue
import random
import re
import shlex
import shutil
import stat
import string
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import tokenize

import pytest

HOOKS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HOOKS))
TEAM_KITS = os.path.join(ROOT, "team-kits")


def _copy(source, target, ignore=None):
    if os.path.isdir(source):
        shutil.copytree(source, target, dirs_exist_ok=True, ignore=ignore)
    else:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(source, target)


def build_project(base):
    """A stand-in for this repo at `base`, with a real git history and a real diff.

    A function and not only a fixture, because one test needs the SAME project under a directory
    whose name contains a space (`test_gate1_refuses_a_protected_path_spelled_absolutely_through_a
    _space`) -- and a project whose path has no space cannot measure that.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import transient_ignore_globs
    ignore = shutil.ignore_patterns(*transient_ignore_globs())
    _copy(TEAM_KITS, os.path.join(base, "team-kits"), ignore)
    _copy(os.path.join(ROOT, "tools", "bump_kit_version.py"),
          os.path.join(base, "tools", "bump_kit_version.py"))
    # gate 5 decides on this DECLARATION and on nothing else, so a stand-in without it is a
    # project that declares no test surface -- and every gate-5 case would measure that instead
    # (`gate_test_scope.declaration` returns None and the gate stands down).
    _copy(os.path.join(ROOT, "tools", "test_surface.json"),
          os.path.join(base, "tools", "test_surface.json"))
    _copy(os.path.join(ROOT, "project_memory"), os.path.join(base, "project_memory"), ignore)
    _copy(HOOKS, os.path.join(base, ".claude", "hooks"), ignore)
    _copy(os.path.join(ROOT, ".claude", "settings.json"),
          os.path.join(base, ".claude", "settings.json"))
    _copy(os.path.join(ROOT, ".claude", "agents"), os.path.join(base, ".claude", "agents"))
    _copy(os.path.join(ROOT, "CLAUDE.md"), os.path.join(base, "CLAUDE.md"))
    os.makedirs(os.path.join(base, "docs"), exist_ok=True)
    os.makedirs(os.path.join(base, "radar"), exist_ok=True)
    with open(os.path.join(base, "docs", "note.md"), "w", encoding="utf-8") as handle:
        handle.write("prose\n")
    with open(os.path.join(base, "radar", "note.md"), "w", encoding="utf-8") as handle:
        handle.write("radar\n")
    for arguments in (["init", "-q", "."], ["config", "user.email", "t@t.t"],
                      ["config", "user.name", "t"], ["add", "-A"],
                      ["-c", "commit.gpgsign=false", "commit", "-qm", "base"]):
        subprocess.run(["git"] + arguments, cwd=base, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # an uncommitted change, so the working tree gate has a non-empty subject to hash
    with open(os.path.join(base, "docs", "note.md"), "a", encoding="utf-8") as handle:
        handle.write("an uncommitted change\n")
    return base


def _digest(path):
    """What this file holds, or None when there is none."""
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return None


def _sandbox_module():
    """The sandbox discipline this suite and the scripts beside it share, imported once."""
    sys.path.insert(0, HOOKS)
    import _sandbox
    return _sandbox


def _reader():
    """The module under test, imported once -- table axes are GENERATED out of it.

    UP HERE because two tables are built at import time from what it answers, and a module-level
    parametrisation runs before the definitions further down exist.
    """
    sys.path.insert(0, HOOKS)
    import _harness
    return _harness


def _a_sandbox_as_a_line_leaves_it(base):
    """`(the probe tree, the relative paths it holds)` -- the watch list, built WITHOUT a shell.

    BOTH FILES ARE MADE HERE, IN PYTHON, and that is the whole of BUG-0137 (a): `_sandbox` makes
    the free file, and the protected one used to be made by handing an EMPTY line (`:`) to an
    arbitrated shell. The line did nothing -- the helper writes the file before it runs anything --
    so a guard that runs no line of its own made the entire suite depend on this host carrying a
    shell that reads this filesystem back. Measured by the verifier of TSK-0063 on a PATH without
    Git: rc 1 with four ERRORs, and those four were the registration checks, which read
    `.claude/settings.json` and nothing else. The shell requirement belongs where a line really
    runs, and there it stands (`_can_arbitrate`).

    Held by `test_the_session_guards_watch_list_is_built_without_a_shell`.
    """
    probe = _sandbox(base, 0)
    subject = os.path.join(probe, *RELATIVE_TARGET.split("/"))
    os.makedirs(os.path.dirname(subject), exist_ok=True)
    with open(subject, "w", encoding="utf-8") as handle:
        handle.write("a")
    return probe, sorted(
        os.path.relpath(os.path.join(root, name), probe).replace("\\", "/")
        for root, _dirs, names in os.walk(probe) for name in names)


@pytest.fixture(scope="session", autouse=True)
def the_repo_is_not_a_sandbox(tmp_path_factory):
    """This suite runs REAL shell lines, and every one of them names its target RELATIVELY.

    THAT IS THE ONE THING THAT CANNOT BE LEFT TO CARE. `_changes_the_protected_file` hands
    `sed -i "s/a/b/" team-kits/kernel/state.py` to a real shell with `cwd` set to a sandbox AND the
    directory state that shell reads out of its environment kept inside that sandbox
    (`_sandbox.sandbox_environment`); the line is safe only because of both, and a line meant to
    PROVE a refusal is dangerous exactly when the proof fails -- if the gate does not refuse it,
    something runs it.
    Measured 2026-08-07 in this repo's working tree: `team-kits/kernel/state.py` came out with the
    first `a` of each of its 928 lines replaced by `b`, which is that payload run once, and the
    kernel stopped importing. Nothing in this suite would have noticed.

    SO THE SUBJECT IS THE REPO ITSELF, and the watch list is DERIVED rather than typed: a sandbox is
    built and walked, and every path it contains is looked up in `ROOT`. Whatever a line shape can
    write inside a sandbox is exactly what it would write here if its `cwd` were wrong.

    WHAT IT CANNOT TELL APART is this suite writing the tree and somebody else writing it while the
    suite runs -- this repo is worked on by more than one agent. The message says both; either way
    the run measured a tree that moved under it.
    """
    # BOTH FILES A SANDBOX HOLDS, and why neither of them is left to a shell, is
    # `_a_sandbox_as_a_line_leaves_it`. Without the second file the walk found only `docs/note.md`,
    # which this repo does not have -- measured 2026-08-07, the guard was green while the escaping
    # run really rewrote the tree.
    _probe, watched = _a_sandbox_as_a_line_leaves_it(str(tmp_path_factory.mktemp("canary")))
    before = {relative: _digest(os.path.join(ROOT, *relative.split("/")))
              for relative in watched}
    assert [relative for relative in watched if before[relative] is not None], (
        "none of the files a sandbox holds (%s) exists in %s, so this guard is watching nothing "
        "that a run of this suite could damage" % (watched, ROOT))
    yield
    moved = [relative for relative in watched
             if _digest(os.path.join(ROOT, *relative.split("/"))) != before[relative]]
    assert not moved, (
        "these files of THIS repo changed while the suite ran: %s.\n"
        "Every line shape here names its target relatively, so the first thing to rule out is a "
        "run of this suite that escaped its sandbox. "
        "The other possibility is another agent writing the same tree at the same time; both mean "
        "the run measured a tree that moved under it." % moved)


def _base_outside_the_home_directory():
    """A writable directory the path a bare `~` names does not contain.

    THE HOME DIRECTORY IS AN ANCESTOR, AND AN ANCESTOR ANSWERS FOR THE PROPERTY. A word whose
    path-like substring is a bare `~` gives this gate ONE candidate -- the home directory -- and a
    stand-in project built under it is then something that directory CONTAINS, so the gate refuses
    for the containment (H19) and not for the word. Measured 2026-08-08 with two projects that
    differ in nothing else: `sed -i "s/a/b/" x=~+/team-kits/kernel/state.py` is rc 0 against a
    project outside the home directory and rc 2 against one under it, while bash writes nothing
    either way. Three lines of the hole list stood on the second answer and said "over-refusal".

    THE CANDIDATES ARE DERIVED AND ORDERED BY WHAT THEY COST, not by host: the system temporary
    directory first, because on a host where it is not under the home directory nothing else is
    needed; then the anchor of this repo's own path; then the directory this repo stands in. A host
    where none of them is writable has no place to measure this property and says so.
    """
    home = os.path.realpath(os.path.expanduser("~"))
    for candidate in (tempfile.gettempdir(), os.path.splitdrive(ROOT)[0] + os.sep,
                      os.path.dirname(ROOT)):
        if not candidate or not os.path.isdir(candidate):
            continue
        resolved = os.path.realpath(candidate)
        if _under(resolved, home) or _under(resolved, os.path.realpath(ROOT)):
            continue
        try:
            probe = tempfile.mkdtemp(prefix="harness-probe-", dir=candidate)
        except OSError:
            continue
        os.rmdir(probe)
        return candidate
    raise AssertionError(
        "no writable directory on this host stands outside %s, so every stand-in project would be "
        "measured through an ancestor rather than through the property under test" % home)


def _under(path, base):
    """Is `path` `base` itself or inside it -- asked on resolved paths, across drives."""
    try:
        return os.path.commonpath([path, base]) == base
    except ValueError:
        return False


@pytest.fixture(scope="session")
def outside_the_home_directory():
    """The base every stand-in project is built under, and why it is not `tmp_path`.

    `tmp_path` is under the home directory on this host, and a project there turns a whole class of
    cells into refusals that measure the containment rather than the word (`_base_outside_the_home
    _directory`). Nothing else about the placement matters, so this is the only thing it changes.
    """
    base = tempfile.mkdtemp(prefix="harness-gates-", dir=_base_outside_the_home_directory())
    yield base
    _removed(base)
    assert not os.path.exists(base), (
        "%s survived the run. This base is not `tmp_path`, so nothing else cleans it up, and a "
        "suite that leaves a stand-in project behind on every run is a suite that fills the "
        "directory it measures from" % base)


def _removed(tree):
    """Delete `tree`, including the read-only files a `.git` directory is made of.

    `ignore_errors=True` is what this replaced, and it hid the whole problem: git object files are
    read-only, Windows refuses to unlink a read-only file, and every run left its stand-in projects
    behind -- measured 2026-08-08, seven of them at the base after one suite run.
    """
    def writable(function, path, _excinfo):
        os.chmod(path, stat.S_IWRITE)
        function(path)

    if sys.version_info >= (3, 12):
        shutil.rmtree(tree, onexc=writable)
    else:  # `onexc` is 3.12; this repo's floor is 3.11 (`kernel/report.py` states it)
        shutil.rmtree(tree, onerror=writable)


@pytest.fixture(scope="session")
def project(outside_the_home_directory):
    """The shared stand-in, built OUTSIDE this repo.

    Outside, because a gate that refuses writes and commits must not be measured by pointing it at
    the working tree it is protecting -- and because gate 3 hashes that working tree, so measuring
    in place would make every run depend on whatever else is uncommitted. And outside the HOME
    directory, because a bare `~` is a candidate this gate resolves and a project under it is one
    the home directory contains (`_base_outside_the_home_directory`).
    """
    return build_project(os.path.join(outside_the_home_directory, "project"))


@pytest.fixture(scope="session")
def open_item(project):
    """An id that RESOLVES, can carry work and is not terminal -- looked up, never typed.

    `TSK-0003` stood spelled out in eight tests, which quietly made them a precondition of that
    one item's status: the day it is validated, gate 2's allow-case, gate 4's allow-case and all
    three of gate 3's remedy tests go red for a reason that has nothing to do with any gate. The
    PROPERTY is what those tests need, so the property is what is looked up; if the store holds no
    such item, one is captured through the kernel, so the branch is measured either way.
    """
    import yaml
    sys.path.insert(0, TEAM_KITS)
    from kernel.backlog_types import ACTIVE_DIRS, AUTOMATA, REQUIRED_FIELDS
    from kernel.state import ProjectState
    state = ProjectState(os.path.join(project, "project_memory"))
    for item_type in sorted(set(AUTOMATA) & set(ACTIVE_DIRS)):
        for stem, path in state.iter_active_items(item_type):
            with open(path, encoding="utf-8") as handle:
                item = yaml.safe_load(handle) or {}
            if str(item.get("status") or "") not in AUTOMATA[item_type].terminals:
                return str(item.get("id") or stem)
    fields = {"title": "probe", "request_text": "probe"}
    candidates = [name for name in sorted(REQUIRED_FIELDS)
                  if name in ACTIVE_DIRS and name in AUTOMATA
                  and set(REQUIRED_FIELDS[name]) <= set(fields)]
    assert candidates, "no open item exists and none can be captured -- widen `fields`"
    done = subprocess.run(
        [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture",
         candidates[0]],
        input=json.dumps({key: fields[key] for key in REQUIRED_FIELDS[candidates[0]]}),
        cwd=project, env=dict(os.environ, PYTHONPATH=os.path.join(project, "team-kits")),
        capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-600:]
    return done.stdout.split()[0]


def _script_path(project, gate):
    """Where the provider would start `gate` FROM -- read off the registration, never assumed.

    Not every gate this repo registers lives in `.claude/hooks/`: the approval hook is the kits'
    own file, referenced where it ships (`settings.json` carries why). A helper that joined
    `.claude/hooks/` to every name would start a file that is not there, and a missing file is a
    silent allow -- which is exactly what the tests using this are here to catch.
    """
    with open(os.path.join(project, ".claude", "settings.json"), encoding="utf-8") as handle:
        settings = json.load(handle)
    for groups in (settings.get("hooks") or {}).values():
        for group in groups:
            for hook in group.get("hooks") or []:
                for word in re.findall(r"\$\{CLAUDE_PROJECT_DIR\}(/[^\"\s]+)",
                                       str(hook.get("command") or "")):
                    if os.path.basename(word) == gate:
                        return os.path.join(project, word.lstrip("/").replace("/", os.sep))
    return os.path.join(project, ".claude", "hooks", gate)


def run(project, gate, payload, hooks=None):
    """Start `gate` as the provider starts it and return (rc, stderr)."""
    script = os.path.join(hooks, gate) if hooks else _script_path(project, gate)
    environment = dict(os.environ, CLAUDE_PROJECT_DIR=project)
    environment.pop("PYTHONPATH", None)
    done = subprocess.run([sys.executable, "-B", script],
                          input=json.dumps(payload).encode("utf-8"), cwd=project,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=environment, timeout=300)
    return done.returncode, done.stderr.decode("utf-8", "replace")


def write_payload(project, relative, **extra):
    data = {"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": project,
            "tool_input": {"file_path": os.path.join(project, *relative.split("/")),
                           "content": "x"}}
    data.update(extra)
    return data


def spawn_payload(project, agent, prompt):
    return {"hook_event_name": "PreToolUse", "tool_name": "Task", "cwd": project,
            "tool_input": {"subagent_type": agent, "description": "d", "prompt": prompt}}


def bash_payload(project, command, tool="Bash"):
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": project,
            "tool_input": {"command": command}}


def todo_payload(project, *entries):
    return {"hook_event_name": "PreToolUse", "tool_name": "TodoWrite", "cwd": project,
            "tool_input": {"todos": [{"content": text, "status": "pending", "activeForm": text}
                                     for text in entries]}}


# -- what is registered, read off the registration ----------------------------


def _registered(settings_path):
    """{event: {matcher: [command, ...]}} as the provider reads it."""
    with open(settings_path, encoding="utf-8") as handle:
        settings = json.load(handle)
    out = {}
    for event, groups in (settings.get("hooks") or {}).items():
        for group in groups:
            entry = out.setdefault(event, {}).setdefault(group.get("matcher", ""), [])
            entry.extend(hook.get("command", "") for hook in group.get("hooks") or [])
    return out


def _registered_tools(settings_path):
    """{script: {(event, tool_name), ...}} -- which CALLS each hook is actually wired to.

    THE EVENT IS PART OF THE ANSWER, and leaving it out cost a whole half of a registration its
    tripwire: the approval hook sits on two events of the same tool and the two do different jobs
    (one prevents, one mints), so a table keyed on tool names alone was satisfied by either. The
    verifier's mutation deleted the `PreToolUse` half and nothing went red.

    The matcher is an alternation of tool names, which is how the provider reads it, so the tool
    names are what comes back. A matcher naming a tool that does not exist (`NeverFires`) shows up
    here as that name and fails the comparison below rather than quietly firing on nothing.
    """
    out = {}
    for event, matchers in _registered(settings_path).items():
        for matcher, commands in matchers.items():
            tools = {(event, part.strip()) for part in matcher.split("|") if part.strip()}
            for command in commands:
                for relative in re.findall(r"\$\{CLAUDE_PROJECT_DIR\}(/[^\"\s]+\.py)", command):
                    out.setdefault(os.path.basename(relative), set()).update(tools)
    return out


# SR-0009's trigger, spelled onto the tool names this provider has -- {gate script: the names it
# must see}. AN ENUMERATION, and the only one in this file, because nothing in the repo derives a
# provider's tool names: the contract states the trigger as a PROPERTY (every surface through which
# a gate's subject can be reached), and a property cannot be compared with a registration until
# somebody writes down which surfaces exist. So it carries a tripwire at BOTH ends
# (`test_the_registration_is_the_one_the_contract_asks_for`): every gate that is registered must
# appear here, and every gate here must be registered on exactly these tools -- and a second test
# drives each of those names through the real process, so a name that is registered and does
# nothing is not the same as one that decides.
#
# WHAT NEITHER END REACHES, named rather than implied: a NEW write-capable surface the provider
# gains. Both ends compare this table with the registration, and neither of them knows the
# provider's inventory; SR-0009 puts a new surface into the registration the day it appears, and
# nothing here notices if it does not.
#
# WHERE EACH LINE COMES FROM:
#   gate 1  -- clause 1: a write is a write whichever tool makes it, so both the write tools and
#              the two shells.
#   gate 2  -- clause 2: the spawn tools.
#   gate 3  -- clause 3: recording history is a shell act.
#   gate 4  -- clause 4: the list tool.
#   gate 5  -- NOT an SR-0009 clause: `gate_test_scope.py` enforces the cost rule of DEC-0050 that
#              CLAUDE.md says no gate could enforce, because the place is `.claude/` -- closed to
#              the session agent, open to an implementer under an item (FR-0086). Its subject is a
#              command line, so it sits on the two shells, and on both for the reason gate 3 does:
#              a line reaches the runner through either.
#   gate_approval -- NOT an SR-0009 gate and not this repo's file: it is the KIT's approval hook,
#              registered here so that a user's answer can mint what the kernel refuses without
#              one (H39). The kits pair its two events and so does this repo; the tool name is the
#              one the kernel spells (`approvals.APPROVAL_QUESTION_TOOL`), and
#              `test_the_approval_hook_is_the_kits_own_file_where_it_ships` measures that the path
#              in the registration really is a kit's hooks directory rather than one kit's name
#              that outlived it.
EXPECTED_TOOLS = {
    "gate_lead_write_scope.py": {("PreToolUse", name) for name in
                                 ("Write", "Edit", "MultiEdit", "NotebookEdit",
                                  "Bash", "PowerShell")},
    "gate_spawn_needs_item.py": {("PreToolUse", "Agent"), ("PreToolUse", "Task")},
    "gate_commit_evidence.py": {("PreToolUse", "Bash"), ("PreToolUse", "PowerShell")},
    "gate_todo_items.py": {("PreToolUse", "TodoWrite")},
    "gate_test_scope.py": {("PreToolUse", "Bash"), ("PreToolUse", "PowerShell")},
    "gate_approval.py": {("PreToolUse", "AskUserQuestion"), ("PostToolUse", "AskUserQuestion")},
}

# The call each gate must REFUSE, per class of tool it is registered on. Used to drive every
# registered tool name through the real process -- see
# `test_each_gate_refuses_on_every_tool_name_it_is_registered_for`.
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}

# WHAT A RECORDED VERDICT OWES SINCE GENERATION 6, in ONE place because nine calls in this file
# make it. `kernel.cli evidence` requires `--run-command` and `--run-scope`: an evidence that does
# not say what was run records a verdict nobody can repeat, and `naming_tests.coverage_blocker`
# reads exactly that field when a batch tries to close a defect on it. Measured when the flags
# became required and this file had not followed: `-k commit` was 3 failed / 31 errors, all of them
# the kernel refusing the call these fixtures make.
#
# THESE ARE REVIEW VERDICTS OF A WORKING TREE AT A NAMED DIGEST, so the pair says that and nothing
# grander: what a reviewer runs to see such a tree is `git diff`, and it covers this one tree --
# a `selection`, never a declared surface. A fixture that claimed a full run here would be the
# same lie the gate it drives exists against.
REVIEWED_BY = ("--run-command", "git diff", "--run-scope", "selection")


def _refusable(project, script, tool):
    """A payload `script` must refuse, shaped as tool `tool` would deliver it."""
    if script == "gate_lead_write_scope.py":
        if tool in SHELL_TOOLS:
            return bash_payload(project, "sed -i 's/a/b/' team-kits/kernel/state.py", tool=tool)
        return write_payload(project, "team-kits/kernel/state.py", tool_name=tool)
    if script == "gate_spawn_needs_item.py":
        payload = spawn_payload(project, "harness-implementer", "Bau mal was.")
        payload["tool_name"] = tool
        return payload
    if script == "gate_commit_evidence.py":
        return bash_payload(project, "git commit -m wip", tool=tool)
    if script == "gate_test_scope.py":
        # A bare run of a declared surface -- the shortest refusable shape, and it needs no state
        # planted: `tools/test_surface.json` travels with the stand-in project.
        return bash_payload(project, "python -B -m pytest tools/ -q", tool=tool)
    if script == "gate_approval.py":
        # A question that CLAIMS to be an approval for a request this project does not hold. The
        # marker is what makes the hook look at all (a markerless question is none of its
        # business, by its own docstring), and an id no pending request answers is the shortest
        # refusable shape -- it needs no state planted and cannot pass by accident.
        question = {"question": "Freigabe? [APR-REQ:%s]" % ("0" * 32), "header": "Freigabe",
                    "multiSelect": False,
                    "options": [{"label": "Freigeben [aaaaaa]", "description": "d"}]}
        return {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": project,
                "tool_input": {"questions": [question]}}
    payload = todo_payload(project, "eins", "zwei")
    payload["tool_name"] = tool
    return payload


# The DISTINCT (script, tool) calls to drive through a real process. The event is what the
# registration table above compares; here it would only run the same payload twice, and the
# payloads below carry their own `hook_event_name`.
REGISTERED_PAIRS = sorted({
    (script, tool)
    for script, calls in _registered_tools(os.path.join(ROOT, ".claude", "settings.json")).items()
    for _event, tool in calls})


def test_the_registration_is_the_one_the_contract_asks_for():
    """WHICH gate sits on WHICH event, read off the file the provider reads.

    Nothing measured this before, and four mutations of `settings.json` left all 38 tests green:
    gate 1's matcher narrowed to `Write`, gate 3's stripped of `PowerShell`, gate 1's registration
    pointed at `gate_todo_items.py` (so gate 1 was not registered at all) and gate 2's matcher set
    to a tool name that does not exist. Both ends, because either alone rots: a gate that is
    registered but not in the table is a gate nobody decided about, and a table entry that is not
    registered is a gate that does not run.

    THE EVENT IS PART OF EACH ENTRY since round TSK-0098, and that was a gap of its own: keyed on
    tool names alone, the approval hook's two events were one entry, and deleting the `PreToolUse`
    half -- the one that refuses a relayed question the kernel did not write -- turned nothing red.
    """
    actual = _registered_tools(os.path.join(ROOT, ".claude", "settings.json"))
    assert set(actual) == set(EXPECTED_TOOLS), (
        "registered gates %s, contract table %s -- one of the two is stale"
        % (sorted(actual), sorted(EXPECTED_TOOLS)))
    for script, tools in sorted(EXPECTED_TOOLS.items()):
        assert actual[script] == tools, (
            "%s is registered on %s but SR-0009's trigger asks for %s"
            % (script, sorted(actual[script]), sorted(tools)))


def _gate_scripts_of_this_repo(settings_path):
    """The gate scripts `settings.json` registers OUT OF THIS REPO'S OWN `.claude/hooks/`.

    A PROPERTY OF THE REGISTERED PATH, not a list: the kit's `gate_approval.py` is registered where
    it SHIPS (`settings.json`'s own comment says why it may not be copied), so "this repo's own
    gates" is exactly "the registered command names a file under `.claude/hooks/`". A second gate
    borrowed from a kit tomorrow is excluded by the same rule with no edit here.
    """
    found = set()
    for _event, matchers in _registered(settings_path).items():
        for _matcher, commands in matchers.items():
            for command in commands:
                for relative in re.findall(r"\$\{CLAUDE_PROJECT_DIR\}(/[^\"\s]+\.py)", command):
                    if relative.startswith("/.claude/hooks/"):
                        found.add(os.path.basename(relative))
    return found


_CLAUDE_MD_GATE_ROW_RX = re.compile(r"^\|\s*`(gate_[A-Za-z0-9_]+\.py)`\s*\|", re.MULTILINE)


def test_the_gate_table_of_this_file_is_the_registration_itself():
    """BUG-0268 / H185: `CLAUDE.md` said "die vier Gates dieses Repos" while five were registered
    and its table listed four rows -- a reader who met gate 5's refusal found no row for it.

    BOTH ENDS, because either alone rots: a gate registered out of `.claude/hooks/` with no row is
    a gate the overview hides, and a row for a script nothing registers is a gate that does not
    run. The count is what aged, so this table is the one place in `CLAUDE.md` that says how many
    there are. ONE count still stands elsewhere in this layer and it is already wrong: the docstring
    of `_harness._expands_a_tilde` calls the registration "the registration of all four gates"
    (measured 2026-09-12, five are registered). That file is forbidden to every role of this
    repository, so the one-word repair is in the user's shell patch; until it is applied, a
    tripwire over the whole layer would be red for a line nobody here may write.

    THE PARSED SIDES, not a substring search over either file: the registration comes from the JSON
    the provider reads (`_registered`, the same reader the contract test uses), and the rows come
    from the document's own table syntax. A sentence in `CLAUDE.md` that merely MENTIONS a gate
    name is not a row and does not satisfy this.
    """
    registered = _gate_scripts_of_this_repo(os.path.join(ROOT, ".claude", "settings.json"))
    with io.open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8") as handle:
        rows = set(_CLAUDE_MD_GATE_ROW_RX.findall(handle.read()))
    assert registered, "no gate of this repo is registered at all -- read the settings, not this"
    assert rows == registered, (
        "CLAUDE.md's gate table lists %s, `.claude/settings.json` registers %s out of "
        ".claude/hooks/ -- the table with no row is the overview a refused reader is sent to"
        % (sorted(rows), sorted(registered)))


@pytest.mark.parametrize("script,tool", REGISTERED_PAIRS)
def test_each_gate_refuses_on_every_tool_name_it_is_registered_for(project, script, tool):
    """The registered name is not the claim -- the process is.

    A tool name in a matcher only means something if the gate DECIDES when a payload arrives under
    it. So every registered pair is driven through the real process with a call that gate must
    refuse; a gate that reads `tool_name` and stands down for one of its own names goes red here,
    and so does a matcher naming an event the gate never handles.
    """
    rc, err = run(project, script, _refusable(project, script, tool))
    assert rc == 2, "%s allowed a refusable call arriving as %s (stderr: %s)" % (
        script, tool, err[:400])


def test_every_registered_gate_names_a_file_that_exists_and_refuses_to_cache():
    """The registration is the subject -- not a list of filenames kept in this test.

    Two properties at once, because both are invisible until they break: a command naming a hook
    that is not there is a silent ALLOW on every call of that event, and an interpreter started
    without `-B` over `.claude/hooks` (which imports out of `team-kits/`, the source side of the
    kit hash) drops bytecode into a hashed tree -- the obligation `kernel/hashing.py`
    (BYTECODE_SUFFIXES) states for every route.
    """
    import re
    registered = _registered(os.path.join(ROOT, ".claude", "settings.json"))
    commands = [command for matchers in registered.values()
                for group in matchers.values() for command in group]
    assert commands, "this repo registers no hooks at all"
    for command in commands:
        assert " -B " in command, "%r starts an interpreter without -B" % command
        named = re.findall(r"\$\{CLAUDE_PROJECT_DIR\}(/[^\"\s]+\.py)", command)
        assert named, "no project-relative script in %r" % command
        for relative in named:
            path = os.path.join(ROOT, relative.lstrip("/").replace("/", os.sep))
            assert os.path.isfile(path), "registered but missing: %s" % path


def test_the_session_agent_is_bound_and_the_repo_carries_no_kit_marker():
    """Both halves of DEC-0003, read off the files that decide them.

    The binding is what makes `_compat.calling_subagent` able to tell the lead from a subagent at
    all -- the fixture blindness that let the July regression live for a month was exactly a
    project that bound none.

    THE MARKER HALF IS A SUBSTRING TEST BECAUSE THE RULE IT MIRRORS IS ONE. The global entry file
    routes on "does ./CLAUDE.md CONTAIN the marker", with no notion of quoting or of a sentence
    saying the opposite -- so a line explaining that this repo carries no marker, with the marker
    spelled out in it, IS a marker. That is not hypothetical: this file said exactly that until
    2026-08-04, which would have handed the repo to a Project Manager of a project that is not one.
    """
    with open(os.path.join(ROOT, ".claude", "settings.json"), encoding="utf-8") as handle:
        bound = json.load(handle).get("agent")
    assert bound, "no session agent bound"
    assert os.path.isfile(os.path.join(ROOT, ".claude", "agents", bound + ".md")), (
        "settings.json binds `%s` but there is no definition for it" % bound)
    with open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8") as handle:
        text = handle.read()
    assert "agents-and-skills:team-kit" not in text, (
        "CLAUDE.md contains the team-kit marker -- the global handover rule routes on the bare "
        "substring, so even a sentence denying it triggers the handover")


def test_todowrite_is_gated_here_and_by_no_kit():
    """Gate 4 has no counterpart in the kits, and this pins BOTH ends of that claim.

    Asked of the registrations the providers read, not of a grep: a kit that starts gating
    `TodoWrite` turns this red so the claim in `gate_todo_items.py` is corrected rather than left
    to rot, and a repo that stops gating it turns it red too.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import is_kit_dir
    kits = [name for name in sorted(os.listdir(TEAM_KITS))
            if is_kit_dir(os.path.join(TEAM_KITS, name))]
    assert kits, "no kits found"
    for kit in kits:
        matchers = _registered(os.path.join(TEAM_KITS, kit, "settings", "settings.json"))
        for event, groups in matchers.items():
            for matcher in groups:
                assert "TodoWrite" not in matcher, (
                    "%s now gates TodoWrite on %s (%s) -- gate_todo_items.py claims no kit does"
                    % (kit, event, matcher))
    here = _registered(os.path.join(ROOT, ".claude", "settings.json"))
    assert any("TodoWrite" in matcher for matcher in here.get("PreToolUse", {})), (
        "this repo no longer gates TodoWrite")


# -- gate 1 -------------------------------------------------------------------


@pytest.mark.parametrize("relative", [
    "team-kits/dev-team/hooks/gate_git.py",     # an existing kit file
    "team-kits/dev-team/hooks/gate_new.py",     # a NEW file in an existing kit directory
    "team-kits/newkit/agents/x.md",             # a NEW kit, no directory on disk yet
    "team-kits/kernel/state.py",                # the shared half of every kit hash
    ".claude/hooks/gate_todo_items.py",         # the enforcement layer itself
    ".claude/settings.json",                    # ...and the file that registers it
    ".claude/agents/harness-lead.md",           # ...and the roles it binds (gate 2 reads these)
    ".claude/settings.local.json",              # ...and the permission overlay it merges
    "tools/bump_kit_version.py",                # ...and the producer of the protected area
])
def test_gate1_refuses_the_session_agent(project, relative):
    """The areas `_harness.ProtectedArea` names, including the paths no enumeration could hold.

    The NEW-file cases are the ones that decide whether the protected area is a position rule or a
    file list: `kit_hash_inputs` enumerates files that EXIST, so a list-based gate waves through
    exactly the write a session agent would use to add kit code.

    The last three are the ones the contract's own enumeration missed, each measured as an open
    route on 2026-08-05: an agent definition carries gate 2's exemption and is re-read on every
    call, `settings.local.json` is a permission overlay, and `bump_kit_version.py` is what gate 1
    derives its protected area FROM -- two `Write` calls to it left every kit file writable.
    """
    rc, err = run(project, "gate_lead_write_scope.py", write_payload(project, relative))
    assert rc == 2, "allowed %s (stderr: %s)" % (relative, err[:400])


@pytest.mark.parametrize("relative", ["docs/note.md", "CLAUDE.md", "radar/note.md",
                                      "project_memory/staging/TSK-0007/proposal.md"])
def test_gate1_leaves_prose_and_bookkeeping_free(project, relative):
    """The counter-direction: a gate that only refuses is a gate that has stopped working.

    `project_memory/staging/**` is here rather than the state root: spec II.4 defines staging as
    explicitly non-canonical, and it is the only route a proposal has out of an agent's hands.
    """
    rc, err = run(project, "gate_lead_write_scope.py", write_payload(project, relative))
    assert rc == 0, "refused %s (stderr: %s)" % (relative, err[:400])


@pytest.mark.parametrize("caller", [{}, {"agent_id": "sub-1", "agent_type": "harness-implementer"}])
def test_gate1_refuses_canonical_state_from_every_caller(project, caller):
    """Canonical state has one writer, and WHO asks does not change that.

    Measured before this existed: a `Write` of
    `project_memory/evidence/active/EVD-9999.yaml` carrying `result: pass` and the current digest
    was allowed (rc 0) and opened `git commit` on the spot -- gate 3's subject certified by a file
    the same session had just typed. Both callers, because a subagent's forgery is the lead's
    forgery one spawn later.
    """
    payload = write_payload(project, "project_memory/evidence/active/EVD-9999.yaml", **caller)
    rc, err = run(project, "gate_lead_write_scope.py", payload)
    assert rc == 2, "a hand-written Evidence item was allowed (%s): %s" % (caller, err[:300])


def test_gate1_reads_a_junction_as_the_tree_it_points_at(project, tmp_path):
    """R4: a second spelling of the same directory is the same directory.

    `mklink /J` needs no administrator rights on Windows, so this is a route a session agent
    really has. Measured with `abspath` in place: the write through the junction was allowed while
    the same file spelled directly was refused.
    """
    work = str(tmp_path / "junction")
    shutil.copytree(project, work)
    link = os.path.join(work, "kits")
    target = os.path.join(work, "team-kits")
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError):
        subprocess.run(["cmd", "/c", "mklink", "/J", link, target], capture_output=True)
    if not os.path.isdir(link):
        pytest.skip("this host allows neither a symlink nor a junction")
    rc, err = run(work, "gate_lead_write_scope.py",
                  write_payload(work, "kits/dev-team/hooks/gate_git.py"))
    assert rc == 2, "a write through a junction into the kit tree was allowed: %s" % err[:300]


# -- gate 1, the shell half ---------------------------------------------------


@pytest.mark.parametrize("tool,command", [
    ("Bash", "python -c \"open('team-kits/dev-team/hooks/gate_git.py','w').write('')\""),
    ("Bash", "python -c \"open('team-kits/kernel/state.py','w').write('')\""),
    ("Bash", "python -c \"open('.claude/hooks/gate_todo_items.py','w').write('')\""),
    ("Bash", "python -c \"open('.claude/settings.json','w').write('')\""),
    ("Bash", "python -c \"open('tools/bump_kit_version.py','w').write('')\""),
    ("Bash", "sed -i 's/a/b/' team-kits/dev-team/hooks/gate_git.py"),
    ("PowerShell", "Set-Content -Path .claude/hooks/gate_todo_items.py -Value ''"),
    ("Bash", "echo x > .claude/settings.json"),                 # the shell's own redirect
    ("Bash", "rm -rf team-kits"),                               # names the tree, not a file in it
    ("Bash", "cd .claude/hooks && rm gate_todo_items.py"),      # the path is never spelled out
    ("Bash", "bash -lc \"rm -f .claude/settings.json\""),       # code one level down
    ("Bash", "python -c \"open('project_memory/evidence/active/EVD-9999.yaml','w')\""),
])
def test_gate1_refuses_a_shell_write_into_a_protected_area(project, tool, command):
    """The eight measured lines of 2026-08-05, plus the four shapes they generalise to.

    Registered on the write tools alone, every one of these answered rc 0 while the same target
    was refused through `Write` -- so the protected area was a property of the TOOL, not of the
    path. `_harness.written_paths` is what answers now, through the kits' own shell reader.
    """
    rc, err = run(project, "gate_lead_write_scope.py", bash_payload(project, command, tool=tool))
    assert rc == 2, "allowed %r (stderr: %s)" % (command, err[:400])


def test_gate1_refuses_a_protected_path_spelled_absolutely_through_a_space(
        outside_the_home_directory):
    """The spelling the first cut of the shell half missed, and it is the ordinary one HERE.

    This repo's own checkout is `C:/Offline Repos/AgentAndSkills`, and the lead's command lines
    start with `cd "<that>"`. A scan for path-like SUBSTRINGS splits such a path at the space and
    neither half names anything -- so the quoted absolute spelling came out allowed while the same
    file spelled relatively was refused. The project is therefore rebuilt under a directory that
    HAS a space: measured in a path without one, this test measures nothing.
    """
    holder = os.path.join(outside_the_home_directory, "a path with spaces")
    os.makedirs(holder, exist_ok=True)
    work = build_project(os.path.join(holder, "repo"))
    target = os.path.join(work, "team-kits", "dev-team", "hooks", "gate_git.py")
    command = 'sed -i "s/a/b/" "%s"' % target.replace("\\", "/")
    rc, err = run(work, "gate_lead_write_scope.py", bash_payload(work, command))
    assert rc == 2, "allowed %r (stderr: %s)" % (command, err[:400])


@pytest.mark.parametrize("tool,command", [
    # every command CLAUDE.md prescribes for this repo, plus the reads a refusal must not cost
    ("Bash", "PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory generate-index"),
    ("PowerShell", '$env:PYTHONPATH="team-kits"; python -B -m kernel.cli --root project_memory '
                   'generate-index'),
    ("Bash", "python -B -m pytest .claude/hooks/test_gates.py -q"),
    ("Bash", "python -B -m pytest tools/ -q"),
    ("Bash", "python tools/bump_kit_version.py"),
    ("Bash", "python -m ruff check ."),
    ("Bash", "git status --short"),
    ("Bash", "git add -A"),
    ("Bash", "cat .claude/hooks/gate_todo_items.py"),
    ("Bash", "grep -rn STATE_ROOT team-kits/"),
])
def test_gate1_leaves_the_sessions_own_commands_runnable(project, tool, command):
    """The counter-error, and it is the expensive one.

    The kits' rule is "a write-capable pipeline that NAMES the protected tree", which works in a
    scaffolded project and would be a lockout here: every one of these lines names `team-kits`,
    `.claude` or `project_memory` and every one of them is prescribed by CLAUDE.md. A gate that
    refuses the session's own documented commands is not stricter, it is broken.
    """
    rc, err = run(project, "gate_lead_write_scope.py", bash_payload(project, command, tool=tool))
    assert rc == 0, "refused %r (stderr: %s)" % (command, err[:400])


# -- gate 1, the START position: nobody plays the provider (H80) --------------------------------
#
# A pipeline stage that hands a FILE to an interpreter starts it. The shapes below are how a
# command line does that; nothing in this repo derives a shell's grammar, so this IS an
# enumeration, and it carries a tripwire at both ends: `test_a_start_shape_really_starts_a_program`
# runs each one through a real shell and fails for an entry that starts nothing, and
# `test_gate1_refuses_starting_a_hook_from_every_caller` fails for one the gate lets through.
# `{program}` is the path of the file to start, spelled relative to the project.
#
# NOT IN THE TABLE, measured rather than forgotten: the shape where the file IS the verb
# (`./x.py`). No shell on this host starts a `.py` that way -- measured 2026-08-31 in Git Bash with
# `#!/usr/bin/env python3` and with an absolute shebang, both no start -- so it has no witness
# here; `test_gate1_refuses_a_hook_started_as_the_verb_itself` carries that half with what it costs.
START_SHAPES = {
    "an interpreter": "python {program}",
    "an interpreter with a flag": "python -B {program}",
    "a flag that takes a value of its own first": "python -W ignore {program}",
    "a shell one level down": 'bash -lc "python {program}"',
    "the receiving end of a pipe": "cat /dev/null | python {program}",
    # A substitution whose text does not CONTAIN the interpreter's name, which is what makes this
    # shape measure `_resolves_the_verb_at_runtime` rather than the wrapper branch: with
    # `$(echo python)` the word `python` stands in the stage and the wrapper branch alone already
    # answers, so the mutation that removed the runtime branch stayed green. And not
    # `$(which python)` either -- that answers with this host's absolute interpreter path, whose
    # SPACE the shell splits the word at, so it starts nothing here (both measured 2026-08-31, each
    # by the witness below).
    "a command substitution in the verb": "$(printf 'pyt%s' hon) {program}",
    # ...and the same substitution with a `;` in it, which the reader cuts THROUGH: the last piece
    # then carries the closing bracket plus the outer stage's own words, with the INNER command's
    # verb in front of them (`_after_an_unopened_closer`)
    "a command substitution cut in two": "$(printf 'pyt'; printf 'hon') {program}",
    "after entering the directory": "cd {directory} && python {name}",
    # -- the shapes the first cut of this position let through, each measured to an approval
    #    nobody gave before it was closed (round TSK-0098, verifier findings B1/B3 and the
    #    wrapper that hands an interpreter its program out of a file)
    "an option-looking word behind the script": "python {program} -c",
    "a wrapper in front of the interpreter": "timeout 60 python {program}",
    "another wrapper": "nohup python {program}",
    "a wrapper that buffers": "stdbuf -o0 python {program}",
    "a shell one level down that moves first": 'sh -c "cd {directory} && python {name}"',
    "an argument list built out of a file": "echo {program} > list.txt; xargs -a list.txt python",
    # -- and the group: the move is real for every command INSIDE it, which is the half
    #    `_runs_in_the_shell_itself` deliberately does not answer (`WorkingDirectory.settle`)
    "a subshell that moves first": "(cd {directory} && python {name})",
    "a subshell with a semicolon": "(cd {directory}; python {name})",
    "two subshells, one inside the other": "(cd {directory} && (cd . && python {name}))",
    "a subshell on the receiving end of a pipe": "true | (cd {directory} && python {name})",
    "a subshell in the background": "(cd {directory} && python {name}) &",
}


def _shaped(shape, program):
    """One line of `START_SHAPES`, filled in for a project-relative `program`."""
    return shape.format(program=program, directory=os.path.dirname(program),
                        name=os.path.basename(program))


# How a shell can build a word out of something this command line does not state. `%s` is the
# rest of the path. An enumeration of the shell's grammar, like `START_SHAPES`, and with the same
# tripwire at both ends: `test_an_unresolved_word_really_changes_in_a_shell` hands each one to a
# real shell and fails for a shape the shell keeps literal, and
# `test_gate1_refuses_a_word_it_cannot_resolve` fails for one the gate places anyway. Each of these
# reached an approval nobody gave in round TSK-0098 before `_harness._UNRESOLVED` existed.
UNRESOLVED_WORDS = {
    "a parameter expansion": '"$PWD/%s"',
    "a braced parameter expansion": '"${PWD}/%s"',
    "a command substitution": '"$(pwd)/%s"',
    "a pathname wildcard": "%s",          # filled by `_wildcarded`, which needs the real name
    "a single-character wildcard": "%s",
    "a character class": "%s",
    "a brace expansion": "%s",
}

# ...and how the three filesystem-matching shapes are made out of a real relative path: the first
# segment is the one that is made unreadable, because every one of them has to still MATCH the
# path for the shell to hand back something -- a shape that matches nothing is handed back
# literally and would be a dead entry.
_WILDCARDS = {
    "a pathname wildcard": lambda head: head[:1] + "*" + head[2:],
    "a single-character wildcard": lambda head: head[:-1] + "?",
    "a character class": lambda head: head[:-1] + "[" + head[-1] + "]",
    "a brace expansion": lambda head: "{%s,other}" % head,
}


def _unresolved(shape, relative):
    """One line of `UNRESOLVED_WORDS`, filled in for a project-relative path."""
    make = _WILDCARDS.get(shape)
    if make is None:
        return UNRESOLVED_WORDS[shape] % relative
    head, _, tail = relative.partition("/")
    return "%s/%s" % (make(head), tail)


def _hook_directories():
    """Every directory this repo's provider or a scaffolded project's provider starts hooks from.

    DERIVED for the kit half (`_harness.kit_hooks_directories`, which asks the kernel what a kit
    is), so a fourth kit is covered on the day it ships. The provider tree is the definition
    `_harness.PROVIDER_DIR` states, not a path spelled here.
    """
    harness = _reader()
    return ([os.path.join(ROOT, harness.PROVIDER_DIR, "hooks")]
            + harness.kit_hooks_directories(ROOT))


def _a_hook_in(directory):
    """One real file of `directory`, picked by a rule and not by a name that could go stale."""
    names = sorted(name for name in os.listdir(directory) if name.endswith(".py"))
    assert names, "no hook file under %s" % directory
    return os.path.join(directory, names[0])


HOOK_SUBJECTS = sorted(
    os.path.relpath(_a_hook_in(directory), ROOT).replace("\\", "/")
    for directory in _hook_directories())


@pytest.mark.parametrize("program", HOOK_SUBJECTS)
@pytest.mark.parametrize("shape", sorted(START_SHAPES))
@pytest.mark.parametrize("caller", ["lead", "subagent"])
def test_gate1_refuses_starting_a_hook_from_every_caller(project, program, shape, caller):
    """H80: a hook is a program the PROVIDER starts, and a command line may not stand in for it.

    THE MEASURED CHAIN this closes ran in one session (TSK-0097): the kernel's own
    `request-approval` writes the pending request, its mint code stands in that file in cleartext,
    and `python <kit hooks>/gate_approval.py < forged.json` then mints an approval nobody gave --
    rc 0 under gate 1 for the session instance AND for an implementer subagent, while the identical
    line is rc 2 in every scaffolded project.

    BOTH CALLERS, and that is the point of the parameter. Who may EDIT enforcement code is the
    change circle's question and a subagent may; who may PLAY THE PROVIDER is not a question of
    role at all, so this is the one area gate 1 refuses to everyone that is not canonical state.
    """
    payload = bash_payload(project, _shaped(START_SHAPES[shape], program))
    if caller == "subagent":
        payload.update(agent_id="sub-1", agent_type="harness-implementer")
    rc, err = run(project, "gate_lead_write_scope.py", payload)
    assert rc == 2, "allowed %r for the %s (stderr: %s)" % (
        _shaped(START_SHAPES[shape], program), caller, err[:400])


@pytest.mark.parametrize("shape", sorted(START_SHAPES))
def test_a_start_shape_really_starts_a_program(outside_the_home_directory, shape):
    """The other end of `START_SHAPES`: a line the gate refuses that starts nothing proves nothing.

    A REAL SHELL IS THE ARBITER, against a marker script in a sandbox -- the same discipline
    `the_repo_is_not_a_sandbox` applies to the write shapes. A dead entry here is a refusal this
    suite has been counting as a wall.
    """
    work = os.path.join(outside_the_home_directory, "start-shapes", shape.replace(" ", "-"))
    os.makedirs(os.path.join(work, "sub"), exist_ok=True)
    marker = os.path.join(work, "sub", "marker.txt")
    with open(os.path.join(work, "sub", "prog.py"), "w", encoding="utf-8") as handle:
        handle.write("import os\nopen(%r, 'a').write('x')\n" % marker.replace("\\", "/"))
    shell = next((candidate for candidate in _posix_shells()
                  if _sees_this_filesystem(candidate, work)), None)
    assert shell is not None, (
        "no shell on this host reads back a file this process writes under %s, so nothing here "
        "arbitrates: %s" % (work, _posix_shells()))
    subprocess.run([shell, "-c", _shaped(START_SHAPES[shape], "sub/prog.py")], cwd=work,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    # A SHELL CAN RETURN BEFORE THE PROGRAM IT STARTED HAS RUN -- a shape ending in `&` hands the
    # whole list to a child and comes straight back. Waiting is the difference between "started
    # nothing" and "had not finished yet", and the wait is for every shape rather than for the one
    # that showed it, because nothing here says which shapes are synchronous.
    for _ in range(50):
        if os.path.isfile(marker):
            break
        time.sleep(0.1)
    assert os.path.isfile(marker), (
        "%r started no program in a real shell, so the refusal this suite asserts for it is a wall "
        "in front of nothing" % _shaped(START_SHAPES[shape], "sub/prog.py"))


@pytest.mark.parametrize("shape", sorted(UNRESOLVED_WORDS))
@pytest.mark.parametrize("caller", ["lead", "subagent"])
def test_gate1_refuses_a_word_it_cannot_resolve(project, shape, caller):
    """A word the SHELL builds is a word this reader cannot place -- the same answer as the tilde's.

    Measured 2026-08-31, each of these rc 0 before and each run through to `APPROVED` with an
    `approval_ref`: the path-like part of `$PWD/<hook>` is the SUBSTRING BEHIND the expansion, and
    it starts with a separator, so it read as an absolute path and landed under no protected tree
    at all. The wildcard shapes reach the same place by a different route.

    BOTH POSITIONS, because the class is wider than the round that found it: the write direction
    (`test_gate1_refuses_a_word_it_cannot_resolve_in_the_write_position`) had been open since the
    shell half was built.
    """
    command = "python " + _unresolved(shape, HOOK_SUBJECTS[0])
    payload = bash_payload(project, command)
    if caller == "subagent":
        payload.update(agent_id="sub-1", agent_type="harness-implementer")
    rc, err = run(project, "gate_lead_write_scope.py", payload)
    assert rc == 2, "allowed %r for the %s (stderr: %s)" % (command, caller, err[:400])


@pytest.mark.parametrize("shape", sorted(UNRESOLVED_WORDS))
def test_gate1_refuses_a_word_it_cannot_resolve_in_the_write_position(project, shape):
    """The half that is not about hooks at all, and that was open before this position existed.

    `sed -i "s/a/b/" "$PWD/team-kits/kernel/state.py"` was rc 0 while the relative spelling of the
    same file was rc 2 (measured 2026-08-31). The fix sits in `_candidates`, which both positions
    go through, so closing one closed the other -- this is what holds that true.
    """
    command = 'sed -i "s/a/b/" %s' % _unresolved(shape, "team-kits/kernel/state.py")
    rc, err = run(project, "gate_lead_write_scope.py", bash_payload(project, command))
    assert rc == 2, "allowed %r (stderr: %s)" % (command, err[:400])


@pytest.mark.parametrize("shape", sorted(UNRESOLVED_WORDS))
def test_an_unresolved_word_really_changes_in_a_shell(outside_the_home_directory, shape):
    """The other end of `UNRESOLVED_WORDS`: a shape a shell keeps LITERAL is a refusal for nothing.

    The arbiter is a real shell and a program that reports the word it was handed. A dead entry
    here is a refusal this suite has been counting as a wall -- and the wildcard shapes are the
    ones that go dead easily, because a pattern matching nothing is handed back unchanged.
    """
    work = os.path.join(outside_the_home_directory, "unresolved", shape.replace(" ", "-"))
    os.makedirs(os.path.join(work, "sub"), exist_ok=True)
    with open(os.path.join(work, "sub", "prog.py"), "w", encoding="utf-8") as handle:
        handle.write("import sys\nprint(sys.argv[1])\n")
    shell = next((candidate for candidate in _posix_shells()
                  if _sees_this_filesystem(candidate, work)), None)
    assert shell is not None, "no shell on this host arbitrates under %s" % work
    word = _unresolved(shape, "sub/prog.py")
    done = subprocess.run([shell, "-c", "python sub/prog.py %s" % word], cwd=work,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    handed = done.stdout.decode("utf-8", "replace").strip()
    assert handed and handed != word.strip('"'), (
        "a shell handed the program %r for the word %r, i.e. it kept it literal -- the gate's "
        "refusal of this shape stands in front of nothing (stderr: %s)"
        % (handed, word, done.stderr.decode("utf-8", "replace")[:200]))


@pytest.mark.parametrize("caller", ["lead", "subagent"])
def test_gate1_refuses_the_line_that_minted_an_approval_nobody_gave(project, caller):
    """Step 3 of the H80 chain, spelled exactly as it ran, against both callers.

    The generalised property is measured above; this is the LINE, kept because a defect's own
    command is the one thing a later refactor can walk past while every derived case still passes.
    Measured rc 0 on 2026-08-30 for both callers, and the item stood at `APPROVED` with an
    `approval_ref` afterwards.
    """
    command = "python team-kits/dev-team/hooks/gate_approval.py < forged.json"
    payload = bash_payload(project, command)
    if caller == "subagent":
        payload.update(agent_id="sub-1", agent_type="harness-implementer")
    rc, err = run(project, "gate_lead_write_scope.py", payload)
    assert rc == 2, "allowed the self-mint line for the %s (stderr: %s)" % (caller, err[:400])


def test_the_approval_hook_is_the_kits_own_file_where_it_ships():
    """The registration names ONE kit, and this is what keeps that spelling from outliving it.

    A settings file cannot derive a path, so the kit is named there; here the name is compared
    with what `_harness.kit_hooks_directories` answers, which asks the kernel what a kit is. A
    renamed or dropped kit turns this red instead of leaving a registration pointing at nothing --
    and a hook the provider cannot find is a silent allow on every call of its event.

    WHY NOT A COPY UNDER `.claude/hooks/`: `approvals.mint` accepts the approval hook only when it
    runs as itself beside its own `_kernel.py`, so a copy would have to bring that helper too, and
    a wrapper would have to reproduce what the kits' `_gate.py` already does.
    """
    directories = {os.path.normcase(os.path.abspath(path))
                   for path in _reader().kit_hooks_directories(ROOT)}
    path = _script_path(ROOT, "gate_approval.py")
    assert os.path.isfile(path), "the registered approval hook is not there: %s" % path
    assert os.path.normcase(os.path.dirname(os.path.abspath(path))) in directories, (
        "%s is registered but does not lie in a kit's hooks directory (%s)"
        % (path, sorted(directories)))


def test_a_users_answer_can_mint_in_this_repo_and_the_kernel_says_so(tmp_path):
    """H39's own condition, asked of the reader that decides it rather than of this file.

    `report.approval_mint_is_wired` is what appends the "nothing here reads your answer" sentence
    to a refused transition and warns before a question is put to the user. It answers off the
    REGISTRATION, so it says True from the moment the file says so -- while the provider binds
    hooks at session start, which is why the user has to restart before an answer really mints.
    Both directions, so a reader stuck on either answer fails: the entry removed from a copy of the
    registration reads False.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import report
    assert report.approval_mint_is_wired(ROOT) is True, (
        "this repo registers no approval hook on the minting event, so no answer of the user's "
        "can mint here (H39)")
    work = str(tmp_path / "without")
    os.makedirs(os.path.join(work, ".claude"))
    with open(os.path.join(ROOT, ".claude", "settings.json"), encoding="utf-8") as handle:
        settings = json.load(handle)
    settings["hooks"].pop("PostToolUse", None)
    with open(os.path.join(work, ".claude", "settings.json"), "w", encoding="utf-8") as handle:
        json.dump(settings, handle)
    assert report.approval_mint_is_wired(work) is False, (
        "the reader says a user's answer mints even where nothing is registered on the minting "
        "event -- then its True above says nothing either")


def _reachable_without(automaton, closed):
    """Every status an automaton reaches from its initial one when no edge INTO `closed` is walkable.

    A WALK OVER THE EDGES THE KERNEL DECLARES, so what this repo can and cannot reach is derived
    from the automaton rather than listed here: a chain that grew a state, or a guard that stopped
    closing one, changes this answer without anything being edited.
    """
    seen, frontier = {automaton.initial}, [automaton.initial]
    while frontier:
        here = frontier.pop()
        for source, target in automaton.allowed:
            if source == here and target not in closed and target not in seen:
                seen.add(target)
                frontier.append(target)
    return seen


def test_the_end_states_this_repo_reaches_are_measured_against_the_kernel(tmp_path):
    """BUG-0290 / H206: which end states this workshop can honestly reach is MEASURED here -- the
    approval half was an unreachability until TSK-0098 and is one no longer, the lease half is a
    decision (DEC-0041) and not a gap, and both are read off the running kernel.

    THE APPROVAL HALF. `BUG TRIAGED -> APPROVED` is bound to an approval in force, and an approval
    is minted by the kits' hook on the answer event. Until TSK-0098 this repo registered only its
    own gates, so the remedy printed at that refusal had no listener here. It registers the hook
    now, and `report.approval_mint_is_wired` is the reader that says so.

    THE LEASE HALF. A lease-bearing status is established by a real dispatch lease, never by a
    status write (DEC-0038/BUG-0010), and this repo runs no dispatch (DEC-0003: it installs no kit).
    So the question is a graph one: with the edges into those statuses closed, which terminals does
    each automaton still reach? For `TSK` that is `CANCELLED` and not `DONE`/`VALIDATED` -- which is
    exactly how this project's generations have been closed, and DEC-0041 is where that was decided.

    BOTH ENDS: the same walk with nothing closed has to reach `DONE`, so the closure above is about
    the lease and not about an automaton that leads nowhere; and the guard itself is driven in both
    directions, on a status it must refuse and one it must let through.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import backlog_types, dispatch, report
    from kernel import state as kernel_state
    assert report.approval_mint_is_wired(ROOT) is True, (
        "this repo registers no approval hook on the minting event, so the edge into APPROVED is "
        "unreachable here and no BUG can be walked to its end state at all")
    closed = frozenset(dispatch.LEASE_BEARING_STATUSES)
    assert closed, "the kernel names no lease-bearing status, so nothing here is closed at all"
    empty = kernel_state.ProjectState(str(tmp_path / "no-dispatch-here"))
    for status in sorted(closed):
        with pytest.raises(dispatch.DispatchError):
            dispatch.assert_lease_backed_transition_locked(empty, "TSK-0001", status)
    open_status = next(status for status in backlog_types.AUTOMATA["TSK"].chain
                       if status not in closed)
    dispatch.assert_lease_backed_transition_locked(empty, "TSK-0001", open_status)
    tasks = backlog_types.AUTOMATA["TSK"]
    here = _reachable_without(tasks, closed)
    everywhere = _reachable_without(tasks, frozenset())
    assert tasks.terminals & everywhere, (
        "the task automaton reaches no terminal even with every edge open, so this walk measures "
        "the reader and not the workshop")
    assert tasks.terminals - here, (
        "every task terminal is reachable without a dispatch, so the lease guard closes nothing "
        "and DEC-0041 describes a workshop that does not exist")
    assert tasks.terminals & here, (
        "no task terminal at all is reachable here, so a task of this project could not even be "
        "closed as cancelled -- and every generation of it has been")
    defects = backlog_types.AUTOMATA["BUG"]
    assert defects.terminals <= _reachable_without(defects, closed), (
        "a defect of this project cannot be walked to %s without a dispatch lease, so DEC-0100's "
        "'a bug closes on a passing test that names it' has no end state to close into"
        % sorted(defects.terminals - _reachable_without(defects, closed)))


@pytest.mark.parametrize("caller", ["lead", "subagent"])
def test_gate1_refuses_a_hook_started_as_the_verb_itself(project, caller):
    """The start position that needs no interpreter in front of it.

    THE SUBJECT IS A KIT HOOK AND THE CALLER IS A PARAMETER, both because the first cut of this
    test measured neither: it used a file under `.claude/` with a lead payload, and BOTH of those
    are refused by the older write rule on their own -- the mutation that removed the verb position
    left it green while a direct probe showed the gap ([2, 2] against [2, 0]).

    WITHOUT A WITNESS ON THIS HOST, said plainly rather than implied: no shell here starts a `.py`
    by its own name (see `START_SHAPES`), so this measures the gate and not the reachability. It is
    kept because the reachability is a property of the HOST -- an executable bit and an interpreter
    the shebang resolves are all it takes -- and the gate is the same either way.
    """
    program = next(name for name in HOOK_SUBJECTS if name.startswith("team-kits/"))
    payload = bash_payload(project, "./%s" % program)
    if caller == "subagent":
        payload.update(agent_id="sub-1", agent_type="harness-implementer")
    rc, err = run(project, "gate_lead_write_scope.py", payload)
    assert rc == 2, "allowed ./%s for the %s (stderr: %s)" % (program, caller, err[:400])


# PowerShell's call operator with an expression in place of the program name. Its own table,
# because the arbiter for it is PowerShell and not the POSIX shell every other shape here is
# measured against -- and because three neighbouring spellings are NOT commands at all on this
# host: `@('pyt'+'hon') x`, `$(('pyt'+'hon')) x` and `@(python) x` are each a parse error
# (measured 2026-08-31, powershell.exe 5.1, all three rc 1 and nothing started), so a table that
# carried them would be refusing what nobody can run.
POWERSHELL_START = "& ('pyt'+'hon') %s"


@pytest.mark.parametrize("caller", ["lead", "subagent"])
def test_gate1_refuses_a_powershell_call_operator_starting_a_hook(project, caller):
    """The verb is then an EXPRESSION, and no word of the stage is a program name this reader knows.

    Found by measurement in this repo rather than reported: `& ('pyt'+'hon') <hook>` came out rc 0
    for a subagent while a real PowerShell started the program (both measured 2026-08-31). The
    reader's verb for it is `pyt+hon`, the stage is not read-only, and nothing in it is an
    interpreter -- which is the case `_harness._executed_words` now answers by putting the whole
    operand list in the start position.
    """
    command = POWERSHELL_START % HOOK_SUBJECTS[0]
    payload = bash_payload(project, command, tool="PowerShell")
    if caller == "subagent":
        payload.update(agent_id="sub-1", agent_type="harness-implementer")
    rc, err = run(project, "gate_lead_write_scope.py", payload)
    assert rc == 2, "allowed %r for the %s (stderr: %s)" % (command, caller, err[:400])


def test_the_powershell_call_operator_really_starts_a_program(outside_the_home_directory):
    """The other end of the shape above -- PowerShell as its own arbiter.

    A host without PowerShell has not measured it, and this says so as a failure rather than as a
    silent pass: the refusal above would then stand in front of something nobody here can run.
    """
    shell = shutil.which("powershell") or shutil.which("pwsh")
    assert shell, "no PowerShell on this host, so the shape above was not measured at all"
    work = os.path.join(outside_the_home_directory, "powershell-start")
    os.makedirs(os.path.join(work, "sub"), exist_ok=True)
    marker = os.path.join(work, "sub", "marker.txt")
    with open(os.path.join(work, "sub", "prog.py"), "w", encoding="utf-8") as handle:
        handle.write("open(%r, 'a').write('x')\n" % marker.replace("\\", "/"))
    subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command",
                    POWERSHELL_START % "sub/prog.py"], cwd=work, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=180)
    assert os.path.isfile(marker), (
        "PowerShell started no program for %r, so the refusal of that shape stands in front of "
        "nothing" % (POWERSHELL_START % "sub/prog.py"))


@pytest.mark.parametrize("caller", ["lead", "subagent"])
@pytest.mark.parametrize("command", [
    # the flat spelling and the same line inside a group -- a shell maintains no hook file, and a
    # bracket around it changes nothing (`WorkingDirectory.settle`)
    "sed -i s/a/b/ .claude/hooks/gate_todo_items.py",
    "cd .claude/hooks && rm gate_todo_items.py",
    "(cd .claude/hooks && rm gate_todo_items.py)",
    '(cd .claude/hooks && sed -i "s/a/b/" gate_todo_items.py)',
    "cp -r .claude/hooks copy",
])
def test_gate1_refuses_maintaining_a_hook_file_from_a_shell(project, command, caller):
    """The WRITE half of the start position, and the half that DEC-0056 keeps: it catches a mistake.

    A stage whose verb this reader can call neither read-only nor an interpreter does something to
    its operands that it cannot name, so those operands stand in the start position too -- and
    inside a hook directory that is refused to EVERYONE, the same rule the kits state for their own
    layer. What keeps the change circle open is the OTHER door: `Edit` and `Write` reach the same
    file for a subagent, and this gate does not touch them.

    Measured 2026-08-31: without this, all five drop to rc 0 for a subagent, and the three
    bracketed ones were rc 0 for EVERY caller -- open since the shell half was built and found by
    the verifier, not by this round.
    """
    payload = bash_payload(project, command)
    if caller == "subagent":
        payload.update(agent_id="sub-1", agent_type="harness-implementer")
    rc, err = run(project, "gate_lead_write_scope.py", payload)
    assert rc == 2, "allowed %r for the %s (stderr: %s)" % (command, caller, err[:400])


@pytest.mark.parametrize("command", [
    # a group is LEFT again when it closes, and what follows belongs to the shell outside it
    "(cd docs && cat note.md)",
    "(cd tools && python bump_kit_version.py)",
    "(cd .claude/hooks && cat _harness.py)",
    "(cd /c/tmp && ls)",
    "(cd . && PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory generate-index)",
    "(ls && cat docs/note.md)",
    "(cd team-kits/dev-team/hooks && ls) && cat docs/note.md",
    '(cd team-kits && ls) && sed -i "s/a/b/" docs/note.md',
])
def test_gate1_comes_back_out_of_a_group_it_walked_into(project, command):
    """The counter-direction of `WorkingDirectory.settle`, and the reason it is a scope.

    The shorter fix for the subshell hole -- give up the position, as for a move inside an inline
    program -- would have refused the second line here, which is how this repo stamps its kits.
    The last two lines are the other end: what stands AFTER the closing bracket belongs to the
    shell that never moved, and reading it from inside the group would be the H27 defect again.
    """
    rc, err = run(project, "gate_lead_write_scope.py", bash_payload(project, command))
    assert rc == 0, "refused %r (stderr: %s)" % (command, err[:400])


@pytest.mark.parametrize("command", [
    "timeout 900 python -B -m pytest .claude/hooks/test_gates.py -q",
    "nohup python -B -m pytest tools/ -q",
])
def test_gate1_leaves_a_wrapped_module_run_alone(project, command):
    """What keeps the wrapper branch NARROW, and the reason it is not the fallback beside it.

    A stage this reader can classify as neither read-only nor an interpreter falls back to reading
    EVERY operand as a start; for a wrapper it does not have to, because the interpreter is right
    there and its own options say it runs a MODULE. Without the wrapper branch these two lines
    would be refused for the path `pytest` was given.

    THE CALLER IS A SUBAGENT, and that is not a convenience: for the SESSION agent both lines are
    rc 2 whatever this position does, because a stage with an unclassified verb hands its whole
    body to the write rule and both name a protected path there. Measured against HEAD, unchanged
    by this round: lead 2, subagent 0.
    """
    payload = bash_payload(project, command)
    payload.update(agent_id="sub-1", agent_type="harness-implementer")
    rc, err = run(project, "gate_lead_write_scope.py", payload)
    assert rc == 0, "refused %r for a subagent (stderr: %s)" % (command, err[:400])


@pytest.mark.parametrize("command", [
    # a shell variable used as DATA names no path, and refusing it refuses every polling loop
    'i=0; until [ $i -ge 3 ]; do i=$((i+1)); done; echo done',
    'if [ -f probe.py ]; then cat probe.py; fi',
    "{ cat probe.py ; }",
])
def test_gate1_leaves_a_shell_variable_that_names_no_path_alone(project, command):
    """The cost the unresolvable-word class must NOT have, measured on this round's own wait line.

    `_UNRESOLVED` answers for a word a shell BUILDS, and the first cut asked it of every word: the
    `until … [ $i -ge 12 ]` loop this round polled its own background runs with came out rc 2, and
    so did every `if [ … ]`. What decides is `_harness._could_name_a_path` -- a word carrying a
    path separator, or one standing where a program is started, and nothing else.
    """
    rc, err = run(project, "gate_lead_write_scope.py", bash_payload(project, command))
    assert rc == 0, "refused %r (stderr: %s)" % (command, err[:400])


def test_gate1_does_not_read_a_directory_as_a_started_file(project):
    """A hook DIRECTORY is not a file anything starts, and naming one is not playing the provider.

    `under` answers yes for equality, so the first cut of `hand_driven` refused the bare word
    `.claude` -- a verifier met it while copying a tree (measured 2026-08-31, a PowerShell payload
    naming the directory in a list, rc 2). The candidate here stands in the START position, which
    is what makes this measure `hand_driven` and not the write rule: a hook FILE in the same
    position is refused two tests up.
    """
    for command in ("python probe.py team-kits/dev-team/hooks",
                    "python probe.py .claude"):
        rc, err = run(project, "gate_lead_write_scope.py", bash_payload(project, command))
        assert rc == 0, "refused %r (stderr: %s)" % (command, err[:400])


@pytest.mark.parametrize("command", [
    # a bare verb is looked up over PATH, so standing INSIDE a hook directory says nothing about it
    "cd .claude/hooks && cat _harness.py",
    "cd .claude/hooks && ls",
    "cd team-kits/dev-team/hooks && grep -rn python .",
    # ...and a directory is not a file anything starts
    "ls team-kits/dev-team/hooks",
    "python -m ruff check .claude/hooks/",
    # a move this reader cannot compute costs the position, not every command afterwards
    'cd "does-not-exist-yet" && ls',
])
def test_gate1_does_not_read_a_bare_verb_as_a_file_in_the_working_directory(project, command):
    """The over-refusal the first cut of the START position introduced, and its two neighbours.

    Measured 2026-08-31, HEAD rc 0 against rc 2 here: from inside a hook directory EVERY command
    was refused -- `cat`, `ls`, `grep` -- because a separatorless verb was resolved against the
    working directory, and the refusal then called `grep` enforcement code. A shell looks such a
    word up over `PATH` and never against the working directory; `_harness._verb_as_a_file` is that
    distinction, and it also takes the third case with it (a move into a directory that does not
    exist yet used to lose the position and refuse every relative word behind it).
    """
    rc, err = run(project, "gate_lead_write_scope.py", bash_payload(project, command))
    assert rc == 0, "refused %r (stderr: %s)" % (command, err[:400])


@pytest.mark.parametrize("command", [
    # the delivery lines of this repo that START a file rather than a module -- the counter-error
    # the START position could make, and the one that would make the repo unusable
    "python tools/bump_kit_version.py",
    "python tools/validate.py",
    "python -B -m pytest .claude/hooks/test_gates.py -q",
    "PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory generate-index",
])
def test_gate1_leaves_a_file_outside_the_hook_directories_startable(project, command):
    """`python tools/bump_kit_version.py` starts a file gate 1 PROTECTS, and must stay rc 0.

    That is the whole boundary of the START position, and it is why it is judged against the hook
    directories rather than against the protected area: what a started program writes cannot be
    read off a command line at all (H11), so a position that refused every protected file would
    refuse the stamper, the validator and the suite -- the three lines this repo delivers with.
    The kits' own rule, measured against these four lines on 2026-08-31, refuses three of them.
    """
    rc, err = run(project, "gate_lead_write_scope.py", bash_payload(project, command))
    assert rc == 0, "refused %r (stderr: %s)" % (command, err[:400])


def test_gate1_leaves_paths_outside_the_repo_free(project, tmp_path):
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": project,
               "tool_input": {"file_path": str(tmp_path / "scratch.md"), "content": "x"}}
    rc, err = run(project, "gate_lead_write_scope.py", payload)
    assert rc == 0, err[:400]


def test_gate1_lets_a_subagent_write_what_it_refuses_the_lead(project):
    """The gate is about WHO writes; a subagent writing kit code is the point of the loop."""
    payload = write_payload(project, "team-kits/dev-team/hooks/gate_git.py",
                            agent_id="sub-1", agent_type="harness-implementer")
    rc, err = run(project, "gate_lead_write_scope.py", payload)
    assert rc == 0, err[:400]


def test_gate1_reads_the_lead_naming_its_own_role_as_the_lead(project):
    """The regression `_compat.calling_subagent` documents, measured from this side.

    A session instance's payload carries `agent_type` equal to the bound role and no `agent_id`.
    A gate that reads "names an agent" as "is a subagent" waves this write through; a gate that
    reads it as "is the lead" -- which is what the two-field definition does -- refuses it.
    """
    with open(os.path.join(project, ".claude", "settings.json"), encoding="utf-8") as handle:
        lead = json.load(handle)["agent"]
    payload = write_payload(project, "team-kits/kernel/state.py", agent_type=lead)
    rc, err = run(project, "gate_lead_write_scope.py", payload)
    assert rc == 2, "the lead naming its own role was read as a subagent: %s" % err[:400]


# -- gate 2 -------------------------------------------------------------------


def test_gate2_refuses_a_spawn_with_no_item(project):
    rc, err = run(project, "gate_spawn_needs_item.py",
                  spawn_payload(project, "harness-implementer", "Bau mal was."))
    assert rc == 2, err[:400]


def test_gate2_refuses_an_id_that_does_not_resolve(project):
    rc, err = run(project, "gate_spawn_needs_item.py",
                  spawn_payload(project, "harness-implementer", "Auftrag: TSK-9999."))
    assert rc == 2, err[:400]
    assert "TSK-9999" in err


def test_gate2_allows_a_spawn_that_names_an_open_item(project, open_item):
    rc, err = run(project, "gate_spawn_needs_item.py",
                  spawn_payload(project, "harness-implementer",
                                "Dein Auftrag ist %s in tasks/active." % open_item))
    assert rc == 0, err[:400]


def test_gate2_exempts_only_what_its_own_definition_exempts(project, tmp_path):
    """BOTH ENDS of the exemption, which is the whole reason it is not a list of role names.

    End one: an agent whose definition declares `harness_item: none` is spawned without an item.
    End two: the SAME definition with that line removed is refused -- so the exemption is really
    read off the file and is not something the gate hands out for other reasons.
    """
    import _harness
    exempt = [name[:-3] for name in sorted(os.listdir(os.path.join(project, ".claude", "agents")))
              if name.endswith(".md")
              and not _harness.spawn_needs_an_item(project, name[:-3])]
    assert exempt, "no agent declares %s: %s" % (_harness.ITEM_KEY, _harness.ITEM_NONE)
    for agent in exempt:
        rc, err = run(project, "gate_spawn_needs_item.py",
                      spawn_payload(project, agent, "Weekly run."))
        assert rc == 0, "%s is declared exempt but was refused: %s" % (agent, err[:400])
    stripped = str(tmp_path / "agents-without-the-key")
    shutil.copytree(os.path.join(project, ".claude", "agents"), stripped)
    definition = os.path.join(stripped, exempt[0] + ".md")
    with open(definition, encoding="utf-8") as handle:
        text = handle.read()
    lines = [line for line in text.splitlines(True)
             if not line.strip().startswith(_harness.ITEM_KEY + ":")]
    assert len(lines) < len(text.splitlines(True)), "the key was not found to remove"
    with open(definition, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(lines))
    live = os.path.join(project, ".claude", "agents")
    backup = str(tmp_path / "agents-backup")
    shutil.copytree(live, backup)
    try:
        shutil.rmtree(live)
        shutil.copytree(stripped, live)
        rc, err = run(project, "gate_spawn_needs_item.py",
                      spawn_payload(project, exempt[0], "Weekly run."))
        assert rc == 2, ("%s stayed exempt after its own declaration was removed -- the exemption "
                         "does not come from the definition" % exempt[0])
    finally:
        shutil.rmtree(live, ignore_errors=True)
        shutil.copytree(backup, live)


# -- gate 3 -------------------------------------------------------------------


def test_gate3_ignores_a_command_that_does_not_commit(project):
    rc, err = run(project, "gate_commit_evidence.py", bash_payload(project, "git status"))
    assert rc == 0, err[:400]


@pytest.mark.parametrize("command", [
    'git commit -m "wip"',
    'bash -lc "git commit -m wip"',      # the payload is code one level down
])
def test_gate3_refuses_a_commit_without_evidence(project, command):
    rc, err = run(project, "gate_commit_evidence.py", bash_payload(project, command))
    assert rc == 2, "allowed %r" % command
    assert "diff:" in err, "the refusal names no subject digest"


def test_gate3_refuses_a_verb_it_cannot_read_without_asking_about_evidence(project):
    """A verb the text does not fix is refused OUTRIGHT, and no longer routed past the digest.

    `git $V -m wip` used to be refused here for the missing Evidence, which reads as "record a
    verdict and this line is fine" -- and it was: with a verdict in the tree the same line was
    measured rc 0, whatever `$V` would have expanded to. Since SR-0009 clause 3 the answer is that
    an unreadable verb could be one that authors a commit, so the refusal is unconditional and its
    remedy is to spell the subcommand out.
    """
    rc, err = run(project, "gate_commit_evidence.py", bash_payload(project, "git $V -m wip"))
    assert rc == 2, "allowed a line whose git subcommand the text does not fix"
    assert "spell the subcommand literally" in err, (
        "the refusal does not say how to comply: %s" % err[:400])
    # THE HALF THAT MAKES THIS A MEASUREMENT AND NOT A PIN: the old gate refused this line too,
    # for the missing Evidence, and printed the digest of the tree with the command that records a
    # verdict for it -- i.e. it told the caller how to make the line RUN. A digest in this refusal
    # means the line is still on the evidence route.
    assert "diff:" not in err, (
        "the line was routed past the working tree's digest, so recording a verdict would open "
        "it -- whatever the verb turns out to be: %s" % err[:400])


def test_gate3_remedy_is_executable_and_opens_the_commit(project, tmp_path, open_item):
    """The remedy's own SHAPE, run against the real kernel, must make the next call pass.

    THIS IS THE TEST THAT KEEPS THE GATE HONEST. A gate whose remedy cannot be executed locks the
    repo out of its own history, and this one is on `git commit`. The digest is read out of the
    refusal and handed to `kernel.cli evidence`, and the same call is repeated. Against a COPY of
    the project, because recording evidence changes it.

    WHAT IT DOES NOT DO, and the sentence that stood here said it did: the argv below is BUILT, not
    parsed out of the printed text. So this measures that the kernel accepts the shape the remedy
    describes -- it does not measure that the LINE the gate prints is the line that runs. Today
    those two differ by exactly the pair `--run-command`/`--run-scope`: the kernel made them
    required this generation, the calls here carry them (`REVIEWED_BY`), and the gate's remedy text
    does not yet -- the repair is the user's shell patch, `project_memory/staging/TSK-0141/
    s4-gate-commit-evidence-patch.md`, because `.claude/hooks/gate_commit_evidence.py` is refused to
    every role here. A check that really executes the printed line is the strengthening that closes
    the difference: `test_gate3_prints_a_remedy_that_runs_as_printed` is it, and it is RED until
    that patch is applied.
    """
    import re
    work = str(tmp_path / "remedy")
    shutil.copytree(project, work)
    payload = bash_payload(work, 'git commit -m "wip"')
    rc, err = run(work, "gate_commit_evidence.py", payload)
    assert rc == 2
    digest = re.search(r"diff:[0-9a-f]{64}", err).group(0)
    environment = dict(os.environ, PYTHONPATH=os.path.join(work, "team-kits"))
    done = subprocess.run(
        [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "evidence",
         "--kind", "review", "--result", "pass", "--related", open_item,
         "--summary", "verifier PASS for " + digest,
         "--artifact-ref", "staging/verdict.md", *REVIEWED_BY],
        cwd=work, env=environment, capture_output=True, text=True)
    assert done.returncode == 0, "the remedy command failed: %s" % done.stderr[-800:]
    rc, err = run(work, "gate_commit_evidence.py", payload)
    assert rc == 0, "the recorded verdict did not open the commit: %s" % err[:600]


_PLACEHOLDER_RX = re.compile(r"<([^<>]+)>")


def _printed_command(refusal, opens_with):
    """The command line a refusal PRINTS, joined the way the shell joins it -- at the backslash.

    A DEFINITION AND NOT A LINE NUMBER: the remedy is whatever the refusal itself printed, so this
    takes the first line that OPENS with the given word and keeps taking the next one for as long
    as the previous one ended in a continuation mark. A remedy that grows a line is followed; a
    remedy that moves in the text is followed; a remedy that disappears comes back empty, and the
    caller says so rather than measuring nothing.
    """
    lines = refusal.splitlines()
    for at, line in enumerate(lines):
        if not line.strip().startswith(opens_with):
            continue
        parts = []
        while at < len(lines):
            piece = lines[at].strip()
            if piece.endswith("\\"):
                parts.append(piece[:-1].strip())
                at += 1
                continue
            parts.append(piece)
            break
        return " ".join(parts)
    return ""


def _remedy_with_values(command, item, artifact):
    """The printed remedy with every `<placeholder>` filled -- by the FLAG it follows, not its text.

    TWO VALUES HAVE TO EXIST OUTSIDE THE LINE for the kernel to take them: the item a verdict
    relates to and the artifact it points at. Those two are handed in. Everything else a remedy can
    ask for is either an enumeration the placeholder spells out itself (`<full|selection>` -- the
    first alternative is as good as any) or free text, where the words ARE the value. A placeholder
    that is neither stops this test instead of travelling into the argv as a literal `<...>`, which
    would turn a remedy this test cannot fill into a green run.
    """
    def value(hit):
        before = command[:hit.start()].rsplit("--", 1)
        flag = "--" + before[1].split()[0] if len(before) > 1 and before[1].split() else ""
        if flag == "--related":
            return item
        if flag == "--artifact-ref":
            return artifact
        inside = hit.group(1)
        if "|" in inside:
            return inside.split("|")[0]
        assert all(letter.isalnum() or letter in " -_" for letter in inside), (
            "the remedy asks for a value this test cannot invent (%r): it is neither an item, nor "
            "an artifact path, nor an enumeration, nor free text" % inside)
        return inside.replace(" ", "-")
    return _PLACEHOLDER_RX.sub(value, command)


def test_gate3_prints_a_remedy_that_runs_as_printed(project, tmp_path, open_item):
    """`BUG-0297` / `H213`: the line gate 3 prints at every blocked hand-over is rc 2 -- it was
    written before `kernel.cli evidence` made `--run-command`/`--run-scope` required, and nobody
    measured the PRINTED text because the sibling test above builds its argv instead of parsing it.

    THIS TEST IS RED ON PURPOSE UNTIL THE USER RUNS THE PATCH, and that is the whole point of it:
    `.claude/hooks/gate_commit_evidence.py` is refused to every role in this repository, so the
    repair is `project_memory/staging/TSK-0141/s4-gate-commit-evidence-patch.md`, applied from a
    shell OUTSIDE Claude Code. A red test is the only honest state for a defect whose fix no role
    here may write; the alternative -- writing the check after the patch -- is how the difference
    survived two rounds unmeasured.

    WHAT IT MEASURES, so the red says something: every token of the argv comes out of the refusal
    itself (`_printed_command` joins it at the continuation marks, `_remedy_with_values` fills the
    placeholders and refuses to invent anything else), the line runs through a REAL SHELL rather
    than through a hand-built argv, and the commit that was refused before is open afterwards. A
    remedy missing any required flag fails at the kernel's own parser, which is exactly the state
    of the text today.
    """
    shell = shutil.which("bash")
    if not shell:
        pytest.skip("no bash on this host: the printed line is a POSIX one and needs a real shell "
                    "as its arbiter -- a hand-split argv would measure this test's own parser")
    work = str(tmp_path / "printed-remedy")
    shutil.copytree(project, work)
    payload = bash_payload(work, 'git commit -m "wip"')
    rc, err = run(work, "gate_commit_evidence.py", payload)
    assert rc == 2, "gate 3 did not refuse, so there is no printed remedy to run: %s" % err[:400]
    printed = _printed_command(err, "PYTHONPATH=")
    assert "kernel.cli" in printed and "evidence" in printed, (
        "the refusal prints no evidence command at all -- then this check measures nothing:\n%s"
        % err[:800])
    line = _remedy_with_values(printed, open_item, "staging/verdict.md")
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)      # the printed line sets it; nothing else may
    done = subprocess.run([shell, "-c", line], cwd=work, env=environment,
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, (
        "the line gate 3 PRINTS does not run (BUG-0297 / H213). Run\n  %s\nand it answers\n  %s\n"
        "The repair is the user's shell patch project_memory/staging/TSK-0141/"
        "s4-gate-commit-evidence-patch.md -- this file's gates may not be written from inside a "
        "session, so this test stays red until it is applied."
        % (line, (done.stderr or done.stdout).strip()[-400:]))
    rc, err = run(work, "gate_commit_evidence.py", payload)
    assert rc == 0, (
        "the verdict the printed line recorded did not open the commit, so the remedy runs and "
        "still does not remedy: %s" % err[:600])


def test_gate3_verdict_stops_covering_a_tree_that_moved(project, tmp_path, open_item):
    """The digest is an identity, so a package that moves after the review is refused again.

    And the counter-direction, which is what makes the construction reachable at all: a change
    confined to `project_memory/` does NOT invalidate the verdict -- it cannot, because the
    verdict is written there.
    """
    import re
    work = str(tmp_path / "moved")
    shutil.copytree(project, work)
    payload = bash_payload(work, "git commit -m wip")
    rc, err = run(work, "gate_commit_evidence.py", payload)
    digest = re.search(r"diff:[0-9a-f]{64}", err).group(0)
    subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory",
                    "evidence", "--kind", "review", "--result", "pass", "--related", open_item,
                    "--summary", "verifier PASS for " + digest,
                    "--artifact-ref", "staging/verdict.md", *REVIEWED_BY],
                   cwd=work, env=dict(os.environ, PYTHONPATH=os.path.join(work, "team-kits")),
                   check=True, capture_output=True, text=True)
    assert run(work, "gate_commit_evidence.py", payload)[0] == 0
    with open(os.path.join(work, "project_memory", "README.md"), "a", encoding="utf-8") as handle:
        handle.write("\nbookkeeping\n")
    assert run(work, "gate_commit_evidence.py", payload)[0] == 0, (
        "a change under the state store invalidated the verdict -- then no verdict could ever "
        "cover the tree it is recorded for")
    with open(os.path.join(work, "docs", "note.md"), "a", encoding="utf-8") as handle:
        handle.write("\none more line\n")
    assert run(work, "gate_commit_evidence.py", payload)[0] == 2, (
        "the verdict still covers a working tree that has moved since")


def test_gate3_sees_a_file_git_does_not_track_yet(project, tmp_path, open_item):
    """R10: the UNTRACKED half of the digest, which no test reached.

    `working_tree_digest` hashes HEAD, the diff to the working tree AND every untracked,
    non-ignored file -- and only the first two were ever measured, so deleting the third loop left
    the suite green while a whole new file could be added to a certified tree. A new file is the
    ordinary shape of "work happened since the review", which makes this the half most worth
    having.
    """
    work = str(tmp_path / "untracked")
    shutil.copytree(project, work)
    payload = bash_payload(work, "git commit -m wip")
    digest = re.search(r"diff:[0-9a-f]{64}",
                       run(work, "gate_commit_evidence.py", payload)[1]).group(0)
    subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory",
                    "evidence", "--kind", "review", "--result", "pass", "--related", open_item,
                    "--summary", "verifier PASS for " + digest,
                    "--artifact-ref", "staging/verdict.md", *REVIEWED_BY],
                   cwd=work, env=dict(os.environ, PYTHONPATH=os.path.join(work, "team-kits")),
                   check=True, capture_output=True, text=True)
    assert run(work, "gate_commit_evidence.py", payload)[0] == 0, "wrong precondition"
    with open(os.path.join(work, "docs", "brand-new.md"), "w", encoding="utf-8") as handle:
        handle.write("a file git has never seen\n")
    rc, err = run(work, "gate_commit_evidence.py", payload)
    assert rc == 2, "an untracked file was added and the verdict still covered the tree: %s" % (
        err[:300])


def test_gate3_reads_the_digest_in_any_field_of_the_record(project, tmp_path, open_item):
    """R10: `evidence_naming` searches EVERY string of the item, and only `--summary` was measured.

    The reviewer decides which field carries the reference; pinning one silently makes the other
    not count. Here the digest is put in `--artifact-ref` and nowhere else.
    """
    work = str(tmp_path / "any-field")
    shutil.copytree(project, work)
    payload = bash_payload(work, "git commit -m wip")
    digest = re.search(r"diff:[0-9a-f]{64}",
                       run(work, "gate_commit_evidence.py", payload)[1]).group(0)
    subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory",
                    "evidence", "--kind", "review", "--result", "pass", "--related", open_item,
                    "--summary", "verifier PASS",
                    "--artifact-ref", "staging/%s.md" % digest, *REVIEWED_BY],
                   cwd=work, env=dict(os.environ, PYTHONPATH=os.path.join(work, "team-kits")),
                   check=True, capture_output=True, text=True)
    rc, err = run(work, "gate_commit_evidence.py", payload)
    assert rc == 0, "a verdict naming the digest outside --summary did not count: %s" % err[:300]


def test_gate3_reads_the_verdict_and_not_merely_the_record(project, tmp_path, open_item):
    """`result: fail` naming the same digest is a review that said NO."""
    import re
    work = str(tmp_path / "failing")
    shutil.copytree(project, work)
    payload = bash_payload(work, "git commit -m wip")
    digest = re.search(r"diff:[0-9a-f]{64}",
                       run(work, "gate_commit_evidence.py", payload)[1]).group(0)
    subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory",
                    "evidence", "--kind", "review", "--result", "fail", "--related", open_item,
                    "--summary", "verifier FAIL for " + digest,
                    "--artifact-ref", "staging/verdict.md", *REVIEWED_BY],
                   cwd=work, env=dict(os.environ, PYTHONPATH=os.path.join(work, "team-kits")),
                   check=True, capture_output=True, text=True)
    assert run(work, "gate_commit_evidence.py", payload)[0] == 2, (
        "a FAILING report opened the commit")


# -- gate 4 -------------------------------------------------------------------


def test_gate4_refuses_a_second_entry_without_an_item(project):
    rc, err = run(project, "gate_todo_items.py",
                  todo_payload(project, "Gates bauen", "Bericht schreiben"))
    assert rc == 2, err[:400]


def test_gate4_allows_exactly_one_unbound_entry(project, open_item):
    rc, err = run(project, "gate_todo_items.py",
                  todo_payload(project, "laufender Schritt", "%s: Gates bauen" % open_item,
                               "%s: Vertrag pruefen" % open_item))
    assert rc == 0, err[:400]


def test_gate4_refuses_an_id_that_does_not_resolve(project, open_item):
    rc, err = run(project, "gate_todo_items.py",
                  todo_payload(project, "%s: a" % open_item, "TSK-9999: b"))
    assert rc == 2, err[:400]


def test_gate4_refuses_a_type_that_carries_no_work(project, open_item):
    """A decision has no lifecycle, so a task list entry pointing at one leads nothing."""
    rc, err = run(project, "gate_todo_items.py",
                  todo_payload(project, "%s: a" % open_item, "DEC-0003: b"))
    assert rc == 2, err[:400]
    assert "DEC-0003" in err


def test_gate4_refuses_an_item_in_a_terminal_status(project, tmp_path, open_item):
    """A finished item is no open work -- the AUTOMATON half of `Reference.terminal`.

    THE SUBJECT IS BUILT, NOT LOOKED UP, and that is what makes this measure the branch it names.
    Every item this project has already archived is BOTH archived and terminal, so either branch
    answers for it and removing one changes nothing -- the first cut of this test was green with
    the automaton test deleted. So an item is captured and driven to a terminal status while
    staying in `active/`: then the archive branch cannot answer, and only the automaton can.

    Its type, and the route to a terminal, come from the kernel (`REQUIRED_FIELDS`, `AUTOMATA`),
    so a renamed type or a changed chain re-derives instead of going stale. The precondition is
    measured too: while the same item is still OPEN, the same list is allowed.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel.backlog_types import ACTIVE_DIRS, AUTOMATA, REQUIRED_FIELDS
    fields = {"title": "probe", "request_text": "probe"}
    candidates = [name for name in sorted(REQUIRED_FIELDS)
                  if name in ACTIVE_DIRS and name in AUTOMATA
                  and set(REQUIRED_FIELDS[name]) <= set(fields)]
    assert candidates, "no automaton type can be captured from this body -- widen `fields`"
    item_type = candidates[0]
    automaton = AUTOMATA[item_type]
    work = str(tmp_path / "terminal")
    shutil.copytree(project, work)
    environment = dict(os.environ, PYTHONPATH=os.path.join(work, "team-kits"))

    def kernel(*arguments, **kw):
        return subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root",
                               "project_memory"] + list(arguments), cwd=work, env=environment,
                              capture_output=True, text=True, **kw)

    done = kernel("capture", item_type,
                  input=json.dumps({key: fields[key] for key in REQUIRED_FIELDS[item_type]}))
    assert done.returncode == 0, done.stderr[-600:]
    item_id = done.stdout.split()[0]
    entries = todo_payload(work, "%s: a" % open_item, item_id + ": b")
    assert run(work, "gate_todo_items.py", entries)[0] == 0, (
        "%s was refused while still open -- wrong precondition" % item_id)
    for status in list(automaton.chain)[1:]:
        assert kernel("transition", item_id, status).returncode == 0
    reached = [status for status in sorted(automaton.terminals)
               if kernel("transition", item_id, status).returncode == 0]
    assert reached, "no terminal status of %s could be reached" % item_type
    state = os.path.join(work, "project_memory", *ACTIVE_DIRS[item_type].split("/"))
    assert os.path.isfile(os.path.join(state, item_id + ".yaml")), (
        "%s left active/ -- then this measures the archive branch, not the automaton" % item_id)
    rc, err = run(work, "gate_todo_items.py", entries)
    assert rc == 2, "%s in %s counted as open work: %s" % (item_id, reached[0], err[:400])


def test_gate2_refuses_an_archived_item_whose_type_declares_no_terminals(project, tmp_path):
    """The ARCHIVE half of `Reference.terminal`, measured where it is the only answer.

    A type without an automaton declares no terminal status at all, so for it the archive IS the
    end of the line -- `state.archive()` accepts such a type unconditionally. Gate 2 is where that
    matters: unlike gate 4 it does not additionally demand that the type can carry work, so an
    automaton-less item reaches the terminal question instead of being rejected before it.

    Built rather than looked up: the item is captured and archived through the kernel in a COPY,
    because a project that happens to have no archived decision today would otherwise silently
    skip the only case this branch decides.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel.backlog_types import (ACTIVE_DIRS, AUTOMATA, CAPTURE_ONLY_REQUIRED, DEC_WORK_NONE,
                                      REQUIRED_FIELDS)
    # `work` is what the CAPTURE DOOR asks of a decision on top of its required fields (DEC-0083,
    # `CAPTURE_ONLY_REQUIRED`): a body without it was rc 1 here on the generation-5 merge's gate run,
    # the door having reached this suite from a stream that never ran it in full (TSK-0133, M13).
    # The probe decision commits nobody, so it says the one silence the door accepts.
    fields = {"title": "probe", "context": "c", "decision": "d", "consequences": "x",
              "source": "probe", "scope": "probe", "check": "probe", "work": DEC_WORK_NONE}
    # the types are CHOSEN by what this body can fill, so a type list that changes shape makes the
    # test pick other subjects instead of failing on a body written for the old one -- and EVERY
    # candidate is walked, with `DEC` required among them: choosing `candidates[0]` let a body that
    # no longer filled the decision's door fall silently to the next type and stay green (TSK-0133
    # verify round 1, B2: with `work` the candidates were DEC and INV, without it INV alone).
    candidates = [name for name in sorted(REQUIRED_FIELDS)
                  if name in ACTIVE_DIRS and name not in AUTOMATA
                  and set(REQUIRED_FIELDS[name]) | set(CAPTURE_ONLY_REQUIRED.get(name, ()))
                  <= set(fields)]
    assert candidates, "no automaton-less type can be captured -- the branch is unreachable"
    assert "DEC" in candidates, (
        "the decision type dropped out of the candidates -- the body no longer fills what its "
        "capture door asks, so the archive branch would be measured on %s alone" % candidates)
    for item_type in candidates:
        work = str(tmp_path / ("archived-" + item_type))
        shutil.copytree(project, work)
        environment = dict(os.environ, PYTHONPATH=os.path.join(work, "team-kits"))
        body = json.dumps({key: value for key, value in fields.items()
                           if key in REQUIRED_FIELDS[item_type]
                           or key in CAPTURE_ONLY_REQUIRED.get(item_type, ())})
        done = subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root",
                               "project_memory", "capture", item_type], input=body, cwd=work,
                              env=environment, capture_output=True, text=True)
        assert done.returncode == 0, (item_type, done.stderr[-600:])
        item_id = done.stdout.split()[0]
        rc, _err = run(work, "gate_spawn_needs_item.py",
                       spawn_payload(work, "harness-implementer", "Auftrag: " + item_id))
        assert rc == 0, "%s was refused while still active -- wrong precondition" % item_id
        subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory",
                        "archive", item_id], cwd=work, env=environment, check=True,
                       capture_output=True, text=True)
        rc, err = run(work, "gate_spawn_needs_item.py",
                      spawn_payload(work, "harness-implementer", "Auftrag: " + item_id))
        assert rc == 2, "an ARCHIVED %s still counted as open work: %s" % (item_type, err[:400])


def test_the_types_a_task_list_carries_work_in_are_the_ones_the_derivation_accepts():
    """The tripwire on the widened predicate, at BOTH ends.

    `_harness.Reference.carries_work` asks the kernel whether a type has a LIFECYCLE. SR-0009
    clause 4 states that as a property and names no type at all, so the derivation cannot be
    compared with a list -- what keeps it honest are the two ends it must not move: the three types
    a task list here is written with must pass, and `DEC`, which has no automaton and can therefore
    lead nothing, must fail. A rename kills the first, a `DEC` that grew an automaton kills the
    second, and either turns this red instead of quietly changing what gate 4 means.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel.backlog_types import ACTIVE_DIRS, AUTOMATA
    for named in ("TSK", "BUG", "FR"):
        assert named in ACTIVE_DIRS, "%s is no longer a kernel type" % named
        assert named in AUTOMATA, (
            "%s has no automaton, so gate 4 would refuse an item type this repo's task lists "
            "carry work in" % named)
    assert "DEC" in ACTIVE_DIRS and "DEC" not in AUTOMATA, (
        "DEC now has a lifecycle -- the reason a decision cannot lead work no longer holds and "
        "gate 4's derivation has to be revisited")


# -- fail-closed --------------------------------------------------------------


def _picture(tree):
    """`{path relative to `tree`: what it holds}` -- what a tree looks like, file by file."""
    out = {}
    for root, _dirs, names in os.walk(tree):
        for name in names:
            path = os.path.join(root, name)
            out[os.path.relpath(path, tree)] = _digest(path)
    return out


def _audit_journals(names):
    """The kits' audit JOURNAL among `names` -- the file, not the directory that holds it.

    THE ONE FILE OF A JUDGED TREE A HOOK MAY GROW. A kit gate records the calls it refuses
    (`_audit`, whose own docstring calls the tree local diagnostics rather than project state), and
    this repo now registers one of those hooks. The record decides nothing: no gate of this repo or
    of a kit reads it back. The journal's NAME comes from the kit module rather than from a
    spelling here, so a rename lands as an empty set -- and then the fixture below fails loudly
    instead of excluding the wrong thing quietly.

    THE FILE AND NOT ITS DIRECTORY, because the two are different exemptions: excusing the
    directory excuses anything a hook might put beside the journal, which is the shape of a hole
    rather than of a named remainder. A rotated generation carries the journal's name inside its
    own (`_audit._rotate`), which is why the comparison is a containment and not an equality.
    """
    sys.path.insert(0, _reader()._kit_hooks_dir(ROOT))
    import _audit
    return {name for name in names if _audit.LOG_NAME in os.path.basename(name)}


@pytest.fixture(scope="session")
def without_the_shared_body(project, tmp_path_factory):
    """A copy of the stand-in whose `_harness.py` is gone -- ONE of it, for every registered pair.

    The pairs differ in which gate is started and with which payload, not in the copy they are
    started against, and copying the whole stand-in is the most expensive thing this file does per
    case (docs/reviews/2026-08-29-tsk0090-measurements.md, section 2).

    SHARING IT IS ONLY SOUND WHILE A GATE LEAVES THE TREE IT JUDGES ALONE, and that is a property
    of the gates, not of this file -- so it is CHECKED HERE rather than stated. A picture of the
    copy is taken before the pairs run and again after, and a file that moved fails this fixture.
    Without that check the class is silent: a gate that started writing anything into the project
    it judges -- an audit line, a lock, a cache -- would leave every pair after the first measuring
    a tree the ones before it had changed, and each pair asserts only its own `rc == 2`. Before
    this round every pair had its own copy and the question could not arise.

    ONE FILE IS EXEMPT AND IT IS NAMED, not waved through: the kits' audit journal, which a kit
    gate appends to whenever it blocks. `_audit_journals` carries why that decides nothing and
    where the name comes from.
    """
    work = str(tmp_path_factory.mktemp("no-shared-body") / "project")
    shutil.copytree(project, work)
    os.remove(os.path.join(work, ".claude", "hooks", "_harness.py"))
    before = _picture(work)
    yield work
    after = _picture(work)
    seen = set(before) | set(after)
    journals = _audit_journals(seen)
    moved = sorted(name for name in seen
                   if after.get(name) != before.get(name) and name not in journals)
    assert not moved, (
        "these files of the shared copy changed while the registered pairs were judged against it: "
        "%s. Every pair after the first then measured a tree an earlier one had moved, and each of "
        "them asserts only its own return code -- so this fixture is where it has to be said. Give "
        "the pairs a copy each again, or take the write out of the gate that makes it." % moved)


@pytest.mark.parametrize("script,tool", REGISTERED_PAIRS)
def test_a_gate_whose_shared_body_is_gone_still_refuses(without_the_shared_body, script, tool):
    """The import is INSIDE the protection, and this is the measurement that says so.

    `guarded()` cannot cover the import of `_harness`, because that happens before any gate
    function runs. Measured on 2026-08-05 with the file deleted: all four gates exited 1, and the
    provider reads a non-zero exit other than 2 as "hook error, carry on" -- an ALLOW on every
    call. Together with gate 1 not being registered on the shell, that was two tool calls to
    switch the whole layer off.

    Driven over the REGISTERED pairs rather than over a list of filenames, so a gate that is added
    to `settings.json` without the preamble is measured on the day it is registered.
    """
    work = without_the_shared_body
    rc, err = run(work, script, _refusable(work, script, tool))
    assert rc == 2, "%s answered rc=%d without its shared body (stderr: %s)" % (
        script, rc, err[:400])


@pytest.mark.parametrize("script,payload_key", [
    ("gate_lead_write_scope.py", "Write"),
    ("gate_commit_evidence.py", "Bash"),
    ("gate_todo_items.py", "TodoWrite"),
])
def test_a_payload_a_gate_cannot_read_is_refused(project, script, payload_key):
    """"Nothing to check" is not "nothing to worry about".

    Each of these three stood down on a payload it could not map to the shape it asks for -- no
    file path, no command line, no `todos` list -- and standing down is an ALLOW. The direction is
    the one `_harness.payload` already takes for a payload over the stdin bound: a call that could
    not be inspected is refused, and the refusal says how to report it if the shape is legitimate.

    An EMPTY todo list is deliberately not in here: clearing the list is a real call and passes.
    """
    payload = {"hook_event_name": "PreToolUse", "tool_name": payload_key, "cwd": project,
               "tool_input": {}}
    rc, err = run(project, script, payload)
    assert rc == 2, "%s allowed a payload it could not read: %s" % (script, err[:300])


def test_gate4_allows_an_empty_list(project):
    """The counter-direction of the test above -- clearing the task list is not an unreadable call."""
    payload = {"hook_event_name": "PreToolUse", "tool_name": "TodoWrite", "cwd": project,
               "tool_input": {"todos": []}}
    assert run(project, "gate_todo_items.py", payload)[0] == 0


def test_gate3_refuses_a_line_that_moves_the_tree_before_it_commits(project, tmp_path, open_item):
    """R1: the digest is taken BEFORE the line runs, so the line must not move the tree.

    Measured with a valid verdict recorded: `echo more >> docs/note.md && git commit -m wip` was
    allowed (rc 0) -- the commit recorded a tree no verdict had ever seen. Both counter-directions
    are measured in the same run, because a rule that also refuses the ordinary flow is not a
    fix: a plain commit and `git add -A && git commit` must stay open, and staging really does
    move nothing the digest reads (`diff HEAD` covers staged and unstaged alike).

    "BEFORE" IS WHAT THE LINE CAN SHOW, and three spellings put a change where nothing orders it
    against the commit -- measured 2026-08-05 with the same valid verdict, all three rc 0: the
    change handed to the background (`... & git commit`), the change glued to its separator
    (`(...);git commit`), and a commit the shell does not wait for, with the change behind it
    (`git commit & ...`). The last one is why the rule is not simply "everything in front of it":
    a background command has no front.

    A PIPE IS THE FOURTH SUCH SPELLING and it was open until TSK-0015: the stages of a pipeline run
    beside each other, so `sed -i ... docs/note.md | git commit -m wip` (rc 0, measured) puts a
    write next to the commit with nothing ordering them. The counter-ends are two: the same shape
    ordered properly (`git commit ; <a write>` stays open, because a write after a commit the shell
    waited for cannot reach it) and a READING stage feeding the commit (`echo wip | git commit -F -`
    stays open, or this rule would refuse a documented flow).

    AND A SUBSTITUTION IS A COMMAND, WHICH IS THE FIFTH: the committing stage is dropped as a whole
    here, and a substitution inside it is neither its verb nor its redirection -- so a write in one
    was invisible. Measured 2026-08-07 with the same valid verdict and end to end:
    `git commit -am wip $(sed -i s/prose/POISON/ docs/note.md)` was rc 0, `docs/note.md` read
    `POISON` afterwards, HEAD moved, and the commit carried it. The counter-end is a READ in the
    same position (`git commit -m "wip $(git rev-parse HEAD)"`), which has to stay open.
    """
    work = str(tmp_path / "before-commit")
    shutil.copytree(project, work)
    payload = bash_payload(work, "git commit -m wip")
    digest = re.search(r"diff:[0-9a-f]{64}",
                       run(work, "gate_commit_evidence.py", payload)[1]).group(0)
    subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory",
                    "evidence", "--kind", "review", "--result", "pass", "--related", open_item,
                    "--summary", "verifier PASS for " + digest,
                    "--artifact-ref", "staging/verdict.md", *REVIEWED_BY],
                   cwd=work, env=dict(os.environ, PYTHONPATH=os.path.join(work, "team-kits")),
                   check=True, capture_output=True, text=True)
    assert run(work, "gate_commit_evidence.py", payload)[0] == 0, "wrong precondition"
    assert run(work, "gate_commit_evidence.py",
               bash_payload(work, "git add -A && git commit -m wip"))[0] == 0, (
        "staging a file was read as moving the tree -- that refuses the ordinary flow")
    assert run(work, "gate_commit_evidence.py",
               bash_payload(work, 'git commit -m wip ; sed -i "s/a/b/" docs/note.md'))[0] == 0, (
        "a write AFTER a commit the shell waits for was read as a write before it")
    assert run(work, "gate_commit_evidence.py",
               bash_payload(work, "echo wip | git commit -F -"))[0] == 0, (
        "a READING stage feeding the commit was read as a write beside it -- that refuses a "
        "documented flow")
    assert run(work, "gate_commit_evidence.py",
               bash_payload(work, "git commit -m wip > /dev/null"))[0] == 0, (
        "a redirect into the discard device was read as a write -- output suppression is not a "
        "change to the tree, and refusing it would refuse the ordinary flow")
    assert run(work, "gate_commit_evidence.py",
               bash_payload(work, 'git commit -m "wip $(git rev-parse HEAD)"'))[0] == 0, (
        "a READ in a substitution of the committing stage was read as a write -- the command a "
        "substitution introduces is judged by the same classification as any other, or this rule "
        "refuses every commit message that quotes the tree it commits")
    unordered = {
        "and then": "echo more >> docs/note.md && git commit -m wip",
        "in the background": "echo more >> docs/note.md & git commit -m wip",
        "glued to its separator": "(echo more >> docs/note.md);git commit -m wip",
        "behind a commit the shell does not wait for":
            'git commit -m wip & sed -i "s/a/b/" docs/note.md',
        # A PIPE IS NO ORDERING: the stages run beside each other, so a write in the committing
        # pipeline reaches the tree while the commit reads it. Two of these were rc 0 before
        # TSK-0015 and are the same mechanism as the four above.
        "in the same pipeline": 'sed -i "s/a/b/" docs/note.md | git commit -m wip',
        "in the same pipeline, glued to a bracket":
            "(echo more >> docs/note.md)|git commit -m wip",
        "in a pipeline that carries stderr too": "echo more >> docs/note.md |& git commit -m wip",
        "behind a commit in the same pipeline":
            'git commit -m wip |& sed -i "s/a/b/" docs/note.md',
        # ONLY THE VERB OF A STAGE IS THE COMMIT -- its REDIRECTION is the shell, and the shell
        # sets it up before git ever starts. Measured 2026-08-07, rc 0 with a valid verdict in the
        # tree, and end to end: `docs/note.md` was EMPTY afterwards and the commit recorded
        # `docs/note.md | 1 -`, a tree no verdict had ever seen.
        "into a file it redirects the commit's own output to": "git commit -am wip > docs/note.md",
        "into a file it appends the commit's own output to": "git commit -m wip >> docs/note.md",
        "into a file it redirects the commit's errors to": "git commit -m wip 2> docs/note.md",
        # A COMMAND A SUBSTITUTION INTRODUCES runs before the word it stands in reaches git, and the
        # stage that carries the commit is dropped as a whole -- so this was the one command in the
        # line that no stage of it ever showed.
        "in a substitution of the committing stage":
            "git commit -am wip $(sed -i s/prose/POISON/ docs/note.md)",
        "in a backtick substitution of the committing stage":
            "git commit -am wip `sed -i s/prose/POISON/ docs/note.md`",
        "in a substitution of a stage beside the commit":
            'echo "$(sed -i s/prose/POISON/ docs/note.md)" | git commit -F -',
    }
    for label, command in sorted(unordered.items()):
        rc, err = run(work, "gate_commit_evidence.py", bash_payload(work, command))
        assert rc == 2, "a line that writes %s was allowed: %s" % (label, err[:300])


def test_gate3_sees_what_the_kits_classification_calls_a_write_and_no_more(project, tmp_path,
                                                                          open_item):
    """WHERE the ordering rule ends, measured -- because a claim of totality would be false.

    Gate 3 asks whether everything the line does not put AFTER the commit is READ-ONLY, and what
    read-only means is the kits' classification (`gate_write_scope._stage_is_read_only`). That is a
    boundary and not a set of exceptions, and it is a boundary in the direction that passes: a verb
    the kits list as reading can still write. Measured here rather than described, in both
    directions in the same run, with a valid verdict recorded:

      * a write the classification SEES (a redirect out of the committing stage itself) is refused;
      * a write it does NOT see -- `sed -n "w <file>"` writes with no redirect operator anywhere,
        which that module's own docstring names as its open edge -- is allowed, and the shell really
        truncates the file.

    So the constitution may not say "every line that changes the tree before the commit"; it names
    this gate and this boundary instead, and `test_the_constitution_names_only_code_that_exists`
    keeps that pointer from rotting. H22 in `docs/POST_V2_WISHLIST.md` carries the boundary itself.
    """
    work = str(tmp_path / "classification-edge")
    shutil.copytree(project, work)
    payload = bash_payload(work, "git commit -m wip")
    digest = re.search(r"diff:[0-9a-f]{64}",
                       run(work, "gate_commit_evidence.py", payload)[1]).group(0)
    subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory",
                    "evidence", "--kind", "review", "--result", "pass", "--related", open_item,
                    "--summary", "verifier PASS for " + digest,
                    "--artifact-ref", "staging/verdict.md", *REVIEWED_BY],
                   cwd=work, env=dict(os.environ, PYTHONPATH=os.path.join(work, "team-kits")),
                   check=True, capture_output=True, text=True)
    assert run(work, "gate_commit_evidence.py", payload)[0] == 0, "wrong precondition"
    seen = 'git commit -am wip > docs/note.md'
    assert run(work, "gate_commit_evidence.py", bash_payload(work, seen))[0] == 2, (
        "the write this gate CAN see was allowed, so the boundary below says nothing")
    unseen = 'sed -n "w docs/note.md" radar/note.md ; git commit -m wip'
    assert run(work, "gate_commit_evidence.py", bash_payload(work, unseen))[0] == 0, (
        "this line is refused now, so the boundary moved: the constitution and H22 describe an "
        "edge that is no longer there, and both have to be corrected rather than left standing")
    shell = next((candidate for candidate in _posix_shells()
                  if _sees_this_filesystem(candidate, work)), None)
    assert shell is not None, (
        "no shell on this host reads back a file this process writes under %s, so what the line "
        "does to the file below was not measured: %s" % (work, _posix_shells()))
    subprocess.run([shell, "-c", 'sed -n "w docs/note.md" radar/note.md'], cwd=work,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    with open(os.path.join(work, "docs", "note.md"), encoding="utf-8") as handle:
        after = handle.read()
    assert after == "radar\n", (
        "the line this gate allows did not move the tree here, so this test measured no boundary "
        "at all: %r" % after)


# -- the constitution points at code, and the pointers are read (TSK-0017 F6) -------------------

CONSTITUTION = os.path.join(ROOT, "CLAUDE.md")
# A backtick-quoted `<module>.<name>` or `<name>.py`, as the constitution spells its pointers.
POINTER_RX = re.compile(r"`([A-Za-z_][\w.]*(?:\.py)?)`")


def _module_names():
    """Every module of the enforcement layer, by the name a pointer would use."""
    return {os.path.splitext(name)[0]: os.path.join(HOOKS, name)
            for name in os.listdir(HOOKS) if name.endswith(".py")}


def test_the_constitution_names_only_code_that_exists():
    """A pointer into the enforcement layer is checkable; a sentence about it is not.

    THE RULE THIS ENFORCES IS THE HOUSE RULE ITSELF -- no comment or document may claim protection
    the code does not build -- turned into something a run can answer. A prose claim ("and every
    line that changes the tree before the commit") cannot be measured and was false: measured
    2026-08-07, `sed -n "w docs/note.md" <file> ; git commit -m wip` is rc 0 and really truncates
    the file (`test_gate3_sees_what_the_kits_classification_calls_a_write_and_no_more`). What CAN be
    measured is a POINTER, so the constitution names the function that decides and this reads that
    name out of the module's syntax tree.

    BOTH ENDS: a pointer that names nothing is a claim that has rotted, and a constitution that
    names no code at all would satisfy the first half by saying nothing -- so the count is asserted
    too.
    """
    with open(CONSTITUTION, encoding="utf-8") as handle:
        text = handle.read()
    modules = _module_names()
    defined, missing = 0, []
    for pointer in sorted(set(POINTER_RX.findall(text))):
        head = pointer.split(".")[0]
        if head not in modules:
            continue
        if pointer.endswith(".py") and pointer.count(".") == 1:
            defined += 1
            continue
        with open(modules[head], encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        names = {node.name for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        names |= {target.id for node in tree.body if isinstance(node, ast.Assign)
                  for target in node.targets if isinstance(target, ast.Name)}
        wanted = pointer.split(".", 1)[1]
        if wanted in names:
            defined += 1
        else:
            missing.append("%s -- %s defines no %s" % (pointer, modules[head], wanted))
    assert not missing, (
        "the constitution points at code that is not there any more:\n%s" % "\n".join(missing))
    assert defined >= 3, (
        "the constitution names %d thing(s) in %s -- a document that points at no code cannot be "
        "held to it, and the prose claims it makes instead are what this test exists to replace"
        % (defined, HOOKS))


@pytest.mark.parametrize("gate", ["gate_lead_write_scope.py", "gate_spawn_needs_item.py",
                                  "gate_commit_evidence.py", "gate_todo_items.py"])
def test_a_gate_that_cannot_decide_refuses(project, tmp_path, gate):
    """A crash must not read as an allow.

    The provider treats a non-zero exit other than 2 as "hook error, carry on". So a gate that
    cannot reach the kernel it decides with has to say so as a REFUSAL, and this measures it by
    taking the kit tree away from a copy rather than by trusting the `try/except` to be there.
    """
    work = str(tmp_path / ("broken-" + gate))
    shutil.copytree(project, work)
    shutil.rmtree(os.path.join(work, "team-kits"))
    payloads = {
        "gate_lead_write_scope.py": write_payload(work, "team-kits/kernel/state.py"),
        "gate_spawn_needs_item.py": spawn_payload(work, "harness-implementer", "x"),
        "gate_commit_evidence.py": bash_payload(work, "git commit -m wip"),
        "gate_todo_items.py": todo_payload(work, "a", "b"),
    }
    rc, err = run(work, gate, payloads[gate])
    assert rc == 2, "%s answered rc=%d instead of refusing (stderr: %s)" % (gate, rc, err[:400])


# -- one file, however it is spelled (TSK-0008 B1) -----------------------------


def spellings(path):
    """Every way THIS host can spell one path, as `{label: spelling}`.

    Asked of the host rather than listed: the 8.3 alias only exists where the volume generates
    one, and a spelling that does not resolve here would measure nothing. The prefixed forms are
    built from the path itself, and each is checked below through the running gate rather than
    trusted.
    """
    full = os.path.abspath(path)
    out = {"plain": full}
    if os.name != "nt" or full[1:3] != ":" + os.sep:
        return out
    drive, rest = full[0], full[2:]
    out["extended-length"] = "\\\\?\\" + full
    out["administrative share"] = "\\\\localhost\\%s$%s" % (drive, rest)
    out["extended UNC"] = "\\\\?\\UNC\\localhost\\%s$%s" % (drive, rest)
    if os.path.exists(full):
        done = subprocess.run(["cmd", "/c", "@for %I in (" + full + ") do @echo %~sI"],
                              capture_output=True, text=True)
        short = done.stdout.strip()
        if short and short != full and os.path.exists(short):
            out["8.3 alias"] = short
    return out


# The routes a candidate path reaches gate 1 by -- the payload field and the command line, on both
# tools the command line arrives on. Not a list of spellings: the spellings are asked of the host
# (`spellings`), and these are the two halves of the gate the docstring below names.
_WRITING_ROUTES = {
    "Write": lambda project, path: {
        "hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": project,
        "tool_input": {"file_path": path, "content": "x"}},
    "sed -i": lambda project, path: bash_payload(project, 'sed -i "s/a/b/" "%s"' % path),
    "Set-Content": lambda project, path: bash_payload(
        project, 'Set-Content -Path "%s" -Value ""' % path, tool="PowerShell"),
}

PROTECTED_SUBJECTS = [
    "team-kits/dev-team/hooks/gate_git.py",             # versioned kit content, exists
    ".claude/hooks/gate_todo_items.py",                 # the enforcement layer, exists
    "project_memory/evidence/active/EVD-9999.yaml",     # canonical state, does NOT exist yet
]


@pytest.mark.parametrize("relative", PROTECTED_SUBJECTS)
def test_gate1_refuses_a_protected_path_however_the_filesystem_spells_it(project, relative):
    """R/B1: "the same file" is what the FILESYSTEM says, not what the text says.

    `realpath` leaves an extended-length prefix, an administrative share and its UNC host
    standing, so each of them was a second name for a protected file that no comparison of text
    recognised: measured 2026-08-05, nine of eleven spellings of a protected path were allowed
    while the plain one was refused -- through `Write`, through `sed -i` and through PowerShell
    `Set-Content` alike.

    Both tool classes per spelling, because the two halves of gate 1 reach the path by different
    routes (a payload field and a command line), and one of them alone leaves the other unmeasured.
    """
    full = os.path.join(project, *relative.split("/"))
    forms = spellings(full)
    if len(forms) < 2:
        pytest.skip("this host spells %s exactly one way" % relative)
    subjects = [(label, route) for label in sorted(forms) for route in sorted(_WRITING_ROUTES)]
    answers = _in_parallel(
        lambda _slot, subject: run(project, "gate_lead_write_scope.py",
                                   _WRITING_ROUTES[subject[1]](project, forms[subject[0]])),
        subjects, GATE_PROCESSES)
    for label, route in subjects:
        rc, err = answers[(label, route)]
        assert rc == 2, "%s allowed the %s spelling of %s: %s" % (route, label, relative, err[:300])


def test_gate1_reads_a_free_path_as_free_in_every_spelling(project):
    """The counter-direction of the test above, and the expensive one.

    An identity comparison that answers "same file" too generously would refuse ordinary prose in
    a second spelling, and a gate that refuses the session's own notes is broken in the direction
    nobody notices until work stops.
    """
    for label, path in sorted(spellings(os.path.join(project, "docs", "note.md")).items()):
        rc, err = run(project, "gate_lead_write_scope.py",
                      {"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": project,
                       "tool_input": {"file_path": path, "content": "x"}})
        assert rc == 0, "the %s spelling of a free file was refused: %s" % (label, err[:300])


# -- the standard library cannot be answered from a gate's own tree (TSK-0008 B2) --------------

# A module that answers every attribute and raises nothing. THE SILENT SHAPE IS THE POINT: a stub
# that fails loudly makes the gate refuse anyway, so it would measure nothing. This one makes the
# tokeniser return nothing, which reads as "this line writes no path".
SILENT_MODULE = '''
class _Anything(object):
    def __init__(self, *a, **k):
        pass

    def __call__(self, *a, **k):
        return _Anything()

    def __getattr__(self, name):
        return _Anything()

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False

    def __str__(self):
        return ""


class _Module(object):
    def __getattr__(self, name):
        return _Anything()


import sys as _sys
_sys.modules[__name__] = _Module()
'''


def _stdlib_names_the_reader_loads(project):
    """Standard-library modules gate 1's own reading of a command line pulls in.

    ASKED OF A RUNNING INTERPRETER, not read out of an import line: the subject of the test below
    has to be the set the code actually depends on, and that set changes when the kits' reader
    does. `sys.stdlib_module_names` is the interpreter's own answer to "is this the standard
    library".
    """
    code = (
        "import os, sys\n"
        "sys.path.insert(0, os.path.join(sys.argv[1], '.claude', 'hooks'))\n"
        "import _harness\n"
        "before = set(sys.modules)\n"
        "_harness.shell_reader({'cwd': sys.argv[1]})\n"
        "fresh = (set(sys.modules) - before) & set(sys.stdlib_module_names)\n"
        "print('\\n'.join(sorted(fresh)))\n")
    done = subprocess.run([sys.executable, "-B", "-c", code, project], cwd=project,
                          capture_output=True, text=True,
                          env=dict(os.environ, CLAUDE_PROJECT_DIR=project))
    assert done.returncode == 0, done.stderr[-600:]
    return [name for name in done.stdout.split() if name]


def _apparatus_directories(project):
    """The directories a gate of this repo runs its own decision out of."""
    sys.path.insert(0, os.path.join(project, ".claude", "hooks"))
    import _harness
    return {"the gate's own directory": os.path.join(project, ".claude", "hooks"),
            "the kit hooks directory": _harness._kit_hooks_dir(project),
            "the kit root": os.path.join(project, "team-kits")}


@pytest.mark.parametrize("where", sorted(["the gate's own directory", "the kit hooks directory",
                                          "the kit root"]))
def test_a_planted_module_cannot_answer_for_a_standard_library_name(project, tmp_path, where):
    """B2: a file in a gate's own tree that is NAMED like a standard-library module.

    Measured 2026-08-05, all three directories, with a stub that raises nothing: the kits'
    tokeniser returned no tokens, `written_paths` came back empty, and gate 1 answered rc 0 with
    an empty stderr for `sed -i` into `team-kits/kernel/state.py`. Appending the kit directories
    to `sys.path` does not prevent it -- `gate_write_scope.py` and `tools/bump_kit_version.py`
    insert their own directory at position 0 while they load, so the shadow exists during an
    import the gate is in the middle of.

    BOTH ENDS IN ONE RUN: the attack must be refused AND the repo's own documented kernel command
    must still be allowed, because a finder that answered too widely would break every kit import
    instead.

    THE REASON IS ASSERTED, NOT ONLY THE EXIT CODE, and that is what makes two of these three
    parameters measure anything. Ablated 2026-08-05 (finder removed, same stub, real gate process):
    the KIT HOOKS directory flips to rc 0 -- it is the one `gate_write_scope.py` puts at
    `sys.path[0]` while it loads. The gate's OWN directory stays rc 2 without the finder, but for
    another reason entirely (the payload reader is stubbed too, so the call comes out
    uninspectable), which the reason assertion below now separates. The KIT ROOT stays rc 2 with
    the same reason either way, because by the time `tools/bump_kit_version.py` puts it at
    position 0 every module the reader needs is already in `sys.modules` -- that parameter is a
    tripwire for the day that order changes, not a measurement of the finder today.
    """
    work = str(tmp_path / ("shadow-" + where.replace(" ", "-").replace("'", "")))
    shutil.copytree(project, work)
    directory = _apparatus_directories(work)[where]
    names = _stdlib_names_the_reader_loads(work)
    assert names, "gate 1 loads no standard-library module while reading a command line"
    for name in names:
        with open(os.path.join(directory, name + ".py"), "w", encoding="utf-8") as handle:
            handle.write(SILENT_MODULE)
    rc, err = run(work, "gate_lead_write_scope.py",
                  bash_payload(work, "sed -i 's/a/b/' team-kits/kernel/state.py"))
    assert rc == 2, "a module planted in %s answered for the standard library: rc=%d %r" % (
        where, rc, err[:300])
    assert "may not write" in err, (
        "refused, but not because the path is protected -- a module planted in %s took the "
        "decision somewhere else: %r" % (where, err[:300]))
    rc, err = run(work, "gate_lead_write_scope.py", bash_payload(
        work, "PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory generate-index"))
    assert rc == 0, "the repo's own kernel command was refused: %s" % err[:300]


def test_no_module_of_this_apparatus_is_named_after_a_standard_library_module():
    """The other end of the finder, and the one that would break work rather than let it through.

    The finder answers for every name the interpreter calls standard library, so a kit -- or this
    hooks directory -- that ever ships `types.py` or `queue.py` would find its own module replaced
    by the standard one. Nothing today does; this turns red on the day something does, which is
    the day the finder needs a narrower question.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import is_kit_dir
    directories = [HOOKS, TEAM_KITS] + [os.path.join(TEAM_KITS, name, "hooks")
                                        for name in sorted(os.listdir(TEAM_KITS))
                                        if is_kit_dir(os.path.join(TEAM_KITS, name))]
    for directory in directories:
        if not os.path.isdir(directory):
            continue
        for entry in sorted(os.listdir(directory)):
            name = entry[:-3] if entry.endswith(".py") else entry
            if not (entry.endswith(".py")
                    or os.path.isfile(os.path.join(directory, entry, "__init__.py"))):
                continue
            assert name not in sys.stdlib_module_names, (
                "%s ships %s, which the interpreter calls standard library -- the finder in "
                "_harness would answer that import from the standard library instead"
                % (directory, entry))


def test_an_exit_this_gate_did_not_make_is_not_a_verdict(project, tmp_path):
    """B2, the second half: `guarded()` lets exactly ONE exit code out of a decision.

    A gate's success exit stands AFTER `decide()` and the only other exit it raises is `refuse()`,
    so every remaining `SystemExit` came from something the decision loaded. Measured 2026-08-05:
    a module ending the process with code 0 during gate 1's decision made the gate answer rc 0 and
    write nothing at all -- the provider reads that as an allow.

    The subject is injected into a module of the KIT the gate loads, and deliberately not into a
    standard-library name: those are covered by the finder above, and a test that measured both at
    once would stay green if either alone were removed.
    """
    work = str(tmp_path / "foreign-exit")
    shutil.copytree(project, work)
    sys.path.insert(0, os.path.join(work, ".claude", "hooks"))
    import _harness
    with open(os.path.join(_harness._kit_hooks_dir(work), "_root.py"), "a",
              encoding="utf-8") as handle:
        handle.write("\nimport sys as _sys\n_sys.exit(0)\n")
    for payload in (write_payload(work, "team-kits/kernel/state.py"),
                    bash_payload(work, "sed -i 's/a/b/' team-kits/kernel/state.py")):
        rc, err = run(work, "gate_lead_write_scope.py", payload)
        assert rc == 2, "a foreign exit(0) during the decision answered rc=%d %r" % (rc, err[:300])


# -- the producer set is measured, and it depends on the payload (TSK-0008 B4) ------------------


def _reason(text):
    """The refusal WITHOUT its subject line -- the branch that answered, as the process states it."""
    return " ".join(line.strip() for line in text.splitlines()[1:] if line.strip())[:400]


def test_gate1_protects_every_reader_its_own_answer_came_from(project):
    """`decision_inputs` promises "every file this answer was computed from", and the shell reader
    is one of them -- it decides WHICH paths a command line writes.

    Measured through the refusals rather than through introspection, and RELATIONALLY so that no
    sentence from another file is quoted here: for a shell payload the kits' `gate_write_scope`
    has to be refused for the same reason `tools/bump_kit_version.py` is (both are where the
    protected area comes from) and for a different one than an ordinary kit file (which is merely
    versioned content). Before the subjects were read first, the shell reader had not been loaded
    when the producer set was taken, and it came out as ordinary kit content.

    THE SET IS PAYLOAD-DEPENDENT, and that is the honest half: a `Write` payload never loads the
    shell reader, so for that call it decided nothing and must NOT be in the set.
    """
    import _harness
    reader = os.path.relpath(os.path.join(_harness._kit_hooks_dir(project),
                                          "gate_write_scope.py"), project).replace("\\", "/")
    stamper = "tools/bump_kit_version.py"
    ordinary = "team-kits/kernel/state.py"

    def shell(relative):
        rc, err = run(project, "gate_lead_write_scope.py",
                      bash_payload(project, "sed -i 's/a/b/' " + relative))
        assert rc == 2, "%s was allowed" % relative
        return _reason(err)

    assert shell(reader) == shell(stamper), (
        "the shell reader is not refused as a producer of the protected area, although gate 1 "
        "computed this very answer with it")
    assert shell(reader) != shell(ordinary), (
        "producer and ordinary kit content answer with the same reason -- then the producer "
        "branch is not what answered")
    rc, err = run(project, "gate_lead_write_scope.py", write_payload(project, reader))
    assert rc == 2, "the shell reader was allowed through a Write"
    assert _reason(err) == shell(ordinary), (
        "a Write payload never loads the shell reader, so it cannot have produced that answer -- "
        "the producer set has to be what the call actually used")


# -- what a shell RUNS, not what it declares (TSK-0008 BUG-0012, R-a, R-b) ----------------------


def test_gate1_reads_a_function_definition_as_the_command_inside_it(project):
    """BUG-0012: this repo's documented kernel prefix, wrapped in a shell function.

    `_stage_verb` reads the declared NAME as the verb, and a verb nothing recognises is not
    read-only -- so every word of the body became a write candidate and `PYTHONPATH=team-kits` put
    the kit tree into the refusal. Measured 2026-08-05: the line below rc 2, the identical line
    without the wrapper rc 0, which stopped items being captured in one go.

    THREE COUNTER-ENDS, because the cut must not swallow a real write: the same wrapper around a
    real write stays refused, so does a bare brace group, and so does a line that writes BEFORE a
    brace token (where the brace is an operand and not a header).
    """
    kernel_line = ("PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory "
                   "generate-index")
    write_line = "sed -i 's/a/b/' team-kits/kernel/state.py"
    assert run(project, "gate_lead_write_scope.py",
               bash_payload(project, "dec () { %s ; }" % kernel_line))[0] == 0, (
        "the repo's own kernel command is refused as soon as it is wrapped in a function")
    for command in ("dec () { %s ; }" % write_line,
                    "{ %s ; }" % write_line,
                    "%s {" % write_line):
        rc, err = run(project, "gate_lead_write_scope.py", bash_payload(project, command))
        assert rc == 2, "a write survived as %r: %s" % (command, err[:300])


def test_gate1_resolves_a_relative_word_where_the_line_really_runs(project, tmp_path):
    """R-b: "we cannot say where we are" and "we are at the repo root" were one answer.

    `_walk` reports None for every absolute target, which is right for a scaffolded project and
    wrong here -- this repo's own lines start with `cd "C:/.../AgentAndSkills"`. Reading None as
    the repo root refused `cd <outside> && sed -i team-kits/...` (measured rc 2) although that
    line writes in another tree entirely, and in the other direction it left a cwd BESIDE the repo
    unread: `sed -i <repo>/team-kits/kernel/state.py` spelled relative to the parent directory was
    allowed (measured rc 0).

    All four ends in one test, because each alone is satisfied by the wrong fix: leaving the
    tracked directory unknown after `popd` would let the last case through again.
    """
    outside = str(tmp_path).replace("\\", "/")
    state = "team-kits/kernel/state.py"
    parent, name = os.path.dirname(project), os.path.basename(project)

    def shell(command, cwd=None):
        payload = bash_payload(project, command)
        payload["cwd"] = cwd or project
        return run(project, "gate_lead_write_scope.py", payload)

    assert shell('cd "%s" && sed -i "s/a/b/" %s' % (outside, state))[0] == 0, (
        "a line that writes outside the repo was refused because the gate assumed the root")
    assert shell('sed -i "s/a/b/" %s' % state, cwd=outside)[0] == 0, (
        "a call whose cwd is outside the repo was judged as if it ran in the repo")
    assert shell('sed -i "s/a/b/" %s/%s' % (name, state), cwd=parent)[0] == 2, (
        "a relative word reaching INTO the repo from beside it was not read")
    assert shell('cd .claude/hooks && rm gate_todo_items.py')[0] == 2, (
        "a relative walk INSIDE the repo stopped being followed")
    assert shell('pushd "%s" ; popd ; sed -i "s/a/b/" %s' % (outside, state))[0] == 2, (
        "the gate lost the directory over pushd/popd and stopped looking")


def test_gate3_leaves_an_environment_prefix_in_front_of_a_commit(project, tmp_path, open_item):
    """R-a: a stage with no verb runs nothing, so it cannot move the tree.

    `_stage_verb` skips a `VAR=value` prefix and reports "", which `written_paths` reads as "this
    stage writes nothing" and the shape check did not -- so the PowerShell spelling of this repo's
    own environment prefix counted as a change to the working tree and every commit behind it was
    refused (measured 2026-08-05, rc 2).

    The counter-end is in the same run: a line that really writes before committing stays refused.
    """
    work = str(tmp_path / "env-prefix")
    shutil.copytree(project, work)
    payload = bash_payload(work, "git commit -m wip")
    digest = re.search(r"diff:[0-9a-f]{64}",
                       run(work, "gate_commit_evidence.py", payload)[1]).group(0)
    subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory",
                    "evidence", "--kind", "review", "--result", "pass", "--related", open_item,
                    "--summary", "verifier PASS for " + digest,
                    "--artifact-ref", "staging/verdict.md", *REVIEWED_BY],
                   cwd=work, env=dict(os.environ, PYTHONPATH=os.path.join(work, "team-kits")),
                   check=True, capture_output=True, text=True)
    assert run(work, "gate_commit_evidence.py", payload)[0] == 0, "wrong precondition"
    prefixed = bash_payload(work, '$env:PYTHONPATH="team-kits"; git commit -m wip',
                            tool="PowerShell")
    rc, err = run(work, "gate_commit_evidence.py", prefixed)
    assert rc == 0, "an environment prefix was read as a change to the working tree: %s" % err[:400]
    assert run(work, "gate_commit_evidence.py",
               bash_payload(work, "echo more >> docs/note.md && git commit -m wip"))[0] == 2, (
        "a line that writes before it commits was allowed")


def test_gate3_reads_a_declaration_head_with_the_same_cut_as_gate1(certified_project):
    """BUG-0012 asks for ONE definition of "what a shell runs" and TWO readers of it.

    `_harness.stage_body` is that definition: the head of a function declaration is not a command,
    so the declared NAME is not the verb of what stands behind the brace. Gate 1's use of it is
    measured (`test_gate1_reads_a_function_definition_as_the_command_inside_it`); gate 3 reads the
    same cut to decide whether a line changes the tree before it commits, and THAT use was measured
    by nothing -- ablated 2026-08-14 in a clone outside this repo (`_moves_the_tree_first` reading
    the raw stages), every other gate-3 test stayed green, while the two shapes below flipped from
    rc 0 to rc 2.

    Without the cut a declared name is a verb nothing recognises, a verb nothing recognises is not
    read-only, and a helper declared in front of a commit reads as a line that changed the tree.
    Both forms the grammar has are driven, because they are two branches of `_declares_a_function`.

    THE COUNTER-END WRITES THROUGH AN OPERAND AND NOT THROUGH A REDIRECT, and that is what makes it
    a counter-end of THIS cut: a redirect target is read off the whole pipeline, one level above
    the stages, so `dec () { echo x >> docs/note.md ; }` is refused whatever the cut does with the
    body -- measured 2026-08-14, with the cut widened to swallow the body it stays rc 2 while
    `sed -i` in the same position comes out rc 0. An operand is only ever seen inside the body, so
    it is the shape that says whether the cut is still narrow.
    """
    for command in ("dec () { echo hi ; } ; git commit -m wip",
                    "function dec { echo hi ; } ; git commit -m wip"):
        rc, err = run(certified_project, "gate_commit_evidence.py",
                      bash_payload(certified_project, command))
        assert rc == 0, (
            "a declaration head was read as the command it declares, so the commit behind it was "
            "refused: %r (%s)" % (command, err[:300]))
    writing = 'dec () { sed -i "s/a/b/" docs/note.md ; } ; git commit -m wip'
    rc, err = run(certified_project, "gate_commit_evidence.py",
                  bash_payload(certified_project, writing))
    assert rc == 2, (
        "a declaration whose body writes the tree through an OPERAND was allowed in front of a "
        "commit -- the cut swallowed the body: %s" % err[:300])


# A module that leaves a trace when it is EXECUTED, and nothing else. The trace is the measurement:
# a planted file that is never imported cannot decide anything, and no exit code says so.
MARKING_MODULE = 'import os\nopen(%r, "w").close()\n'


def test_a_kit_directory_does_not_outlive_its_own_import_on_sys_path(project, tmp_path):
    """The kits' modules put their own directory at `sys.path[0]` while they load, and it stayed.

    `gate_write_scope.py` inserts its directory at position 0 as it is executed, and a gate loads
    it while reading a command line. Everything a gate imports AFTERWARDS -- `yaml`, which parses
    the Evidence record gate 3 judges by -- was then answered out of a kit directory instead of out
    of site-packages. `StandardLibraryWins` does not cover that: `yaml` is not a name the
    interpreter calls standard library. The same restore stands around the stamper's execution in
    `_bump_tool`, which inserts its own directory the same way.

    THE SUBJECT IS THE EXECUTION of the planted file, not an exit code: a module that is imported
    runs, and running is what it would take to decide anything, while both outcomes happen to end
    in a refusal. Measured 2026-08-05 through the real gate process.
    """
    work = str(tmp_path / "path-outlives")
    shutil.copytree(project, work)
    sys.path.insert(0, os.path.join(work, ".claude", "hooks"))
    import _harness
    marker = os.path.join(str(tmp_path), "the-planted-module-ran")
    with open(os.path.join(_harness._kit_hooks_dir(work), "yaml.py"), "w",
              encoding="utf-8") as handle:
        handle.write(MARKING_MODULE % marker)
    rc, err = run(work, "gate_commit_evidence.py", bash_payload(work, "git commit -m wip"))
    assert not os.path.exists(marker), (
        "a file planted in the kit hooks directory answered `import yaml` for gate 3 -- and that "
        "is what decides whether an Evidence record says pass")
    assert rc == 2 and "diff:" in err, (
        "wrong precondition: gate 3 did not reach the Evidence store at all (%s)" % err[:200])


# -- where the shell really is (TSK-0011 F1, F2) -------------------------------


def test_gate1_does_not_follow_a_move_the_shell_would_not_make(project, tmp_path):
    """A directory verb moves the gate's base only where a shell would really land.

    The reading that stood here counted every `cd`, `pushd` and `popd` as done. A shell does not:
    measured 2026-08-05 in a real bash, each of the seven lines below leaves the shell exactly
    where it was and REWRITES the protected file it names relatively -- while the gate had already
    followed the move out of the tree and answered rc 0 for all of them.

    THE COUNTER-DIRECTION IS IN THE SAME RUN, and it is the expensive one: a gate that simply
    stopped following directory verbs would pass the first half and refuse every line that really
    did leave the tree. `cd -` and a bare `cd` are both in it because they are different branches
    that used to be one -- the operand filter dropped every word starting with a dash, `-` among
    them, so `cd -` silently went HOME and no test could see the difference.
    """
    outside = str(tmp_path).replace("\\", "/")
    write = 'sed -i "s/a/b/" team-kits/kernel/state.py'

    def shell(command):
        return run(project, "gate_lead_write_scope.py", bash_payload(project, command))

    stays = {
        "cd into an absolute directory that is not there": "cd /nope-not-there ; " + write,
        "cd into a relative directory that is not there": "cd nope-does-not-exist ; " + write,
        "popd with nothing pushed": "popd ; " + write,
        "pushd with an empty stack": "pushd ; " + write,
        "cd - after a cd that went out": 'cd "%s" ; cd - ; %s' % (outside, write),
        "a cd inside a subshell": '( cd "%s" ) ; %s' % (outside, write),
        "pushd out, then a bare pushd that swaps back": 'pushd "%s" ; pushd ; %s' % (outside,
                                                                                     write),
    }
    for label, command in sorted(stays.items()):
        rc, err = shell(command)
        assert rc == 2, "the gate followed %s and let the write through: %s" % (label, err[:200])
    moves = {
        "cd into a directory that IS there": 'cd "%s" ; %s' % (outside, write),
        "pushd into a directory that IS there": 'pushd "%s" ; %s' % (outside, write),
        "a bare cd, which goes home": "cd ; " + write,
        "cd ~, which is the same place spelled out": "cd ~ ; " + write,
    }
    for label, command in sorted(moves.items()):
        rc, err = shell(command)
        assert rc == 0, "the gate did not follow %s and refused a write outside the repo: %s" % (
            label, err[:200])


def test_gate1_cuts_a_declaration_head_because_it_is_one(project):
    """The head of a function declaration, not "there is a bracket somewhere in front of the brace".

    The cut exists so this repo's own kernel prefix survives being wrapped in a function
    (BUG-0012). Asking for a bracket ANYWHERE in the head answers yes for heads that declare
    nothing, and then the cut throws away the write standing in front of the brace: measured
    2026-08-05, both lines below wrote into a kit file with rc 0.

    THE OTHER END IS THE REASON THE CUT IS NARROW AT ALL: the same wrapper around a real write
    stays refused, and so does a write in front of a brace that is only an operand -- those are
    measured in `test_gate1_reads_a_function_definition_as_the_command_inside_it`. What is new here
    is the keyword form, which the grammar has and the old head test could not see.
    """
    kernel_line = ("PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory "
                   "generate-index")
    write = 'sed -i "s/a/b/" team-kits/kernel/state.py'
    for command in ("%s $(true) {" % write, "arr=(a b) %s {" % write):
        rc, err = run(project, "gate_lead_write_scope.py", bash_payload(project, command))
        assert rc == 2, "a head that declares nothing was cut, losing the write: %r" % command
    for command in ("dec () { %s ; }" % kernel_line, "function dec { %s ; }" % kernel_line):
        rc, err = run(project, "gate_lead_write_scope.py", bash_payload(project, command))
        assert rc == 0, "a real declaration was not recognised: %r (%s)" % (command, err[:200])


# -- what a line writes, measured against the shell itself (TSK-0013 F1, F2) --------------------

# A path inside a protected tree, spelled RELATIVELY, and a write into it. Which tree it lands in is
# decided by where the shell stands when it runs, so it is the subject every shape below is measured
# with.
RELATIVE_TARGET = "team-kits/kernel/state.py"
RELATIVE_WRITE = 'sed -i "s/a/b/" %s' % RELATIVE_TARGET

# WHERE A DIRECTORY VERB STANDS, and whether the SHELL ITSELF is what runs it there. The first
# axis of the table below, and the one `_harness._runs_in_the_shell_itself` answers.
IN_THE_SHELL, IN_A_CHILD = "the shell itself", "a child"
POSITIONS = {
    "run by the shell itself": ("%(move)s ; %(write)s", IN_THE_SHELL),
    "glued to its terminator": ("%(move)s;%(write)s", IN_THE_SHELL),
    "in a brace group, which groups and is no child": ("{ %(move)s ; } ; %(write)s", IN_THE_SHELL),
    "with its own output redirected": ("%(move)s > /dev/null ; %(write)s", IN_THE_SHELL),
    "after a group that closed": ("( true ) ; %(move)s ; %(write)s", IN_THE_SHELL),
    "after a group whose list went to the background":
        ("( true & ) ; %(move)s ; %(write)s", IN_THE_SHELL),
    "behind a backgrounded command": ("true & %(move)s ; %(write)s", IN_THE_SHELL),
    "behind a glued and": ("true&&%(move)s ; %(write)s", IN_THE_SHELL),
    "in a group": ("( %(move)s ) ; %(write)s", IN_A_CHILD),
    "in a group opened before a terminator": ("( true ; %(move)s ) ; %(write)s", IN_A_CHILD),
    "in a group opened before an and": ("( true && %(move)s ) ; %(write)s", IN_A_CHILD),
    "in a group opened before an or": ("( false || %(move)s ) ; %(write)s", IN_A_CHILD),
    "in a group inside a group": ("( ( %(move)s ) ) ; %(write)s", IN_A_CHILD),
    "in a group glued to the terminator behind it": ("(%(move)s);%(write)s", IN_A_CHILD),
    "in a background list": ("%(move)s & %(write)s", IN_A_CHILD),
    "in a background list with a command behind it": ("%(move)s & true ; %(write)s", IN_A_CHILD),
    "in an and-or list backgrounded at its end": ("%(move)s && true & %(write)s", IN_A_CHILD),
    "as the first stage of a pipeline": ("%(move)s | true ; %(write)s", IN_A_CHILD),
    "as the last stage of a pipeline": ("true | %(move)s ; %(write)s", IN_A_CHILD),
}

# WHERE THE MOVE LEAVES EACH OF THE TWO READERS OF THIS LINE -- the SHELL and the gate. Two columns
# and not one, because the reader is knowingly stricter than the shell in places and a single column
# could only be kept by leaving those places out of the table, which is the beschneiden DEC-0016 is
# about.
#
# FOUR LANDINGS, AND THE FOURTH IS THIS ROUND'S AXIS (DEC-0018). Three of them are places a shell
# can be -- at the target the move names, where it already stood, or in the home directory, which is
# neither tree. `LOST` is only ever the READER's: a move it cannot compute leaves it nowhere it can
# name, and every relative word from there is refused. That answer used to be written as a BRANCH
# over the verb (`popd` alone had it), so it had no value here and no cell -- measured 2026-08-07,
# seven line shapes with the base outside the tree were rc 0 while bash rewrote the protected file.
# `UNCLAIMED` is the third answer for the SHELL: this reader makes no claim about what a word in
# FRONT of a command name does with it, so the table does not either.
AT_TARGET, STAYS_PUT, HOME, LOST, UNCLAIMED = (
    "at the target", "nowhere", "the home directory", "nowhere it can name", None)
MOVES = {
    "cd to a directory that is there": ("cd %(to)s", AT_TARGET, AT_TARGET),
    "cd with a second operand the shell rejects": ("cd %(to)s x", STAYS_PUT, LOST),
    "cd with an option the shell rejects": ("cd -q %(to)s", STAYS_PUT, LOST),
    # POSIX Utility Syntax Guideline 10 -- the shell's grammar, so this reader can account for it
    "cd behind the end of the options": ("cd -- %(to)s", AT_TARGET, AT_TARGET),
    # ...and an option the shell ACCEPTS is the friction that costs (H29): the shell moves and this
    # reader gives the position up, and only a table with two columns can carry that cell at all
    "cd with an option the shell accepts": ("cd -L %(to)s", AT_TARGET, LOST),
    "cd into a directory that is not there": ("cd %(to)s/nope-not-there", STAYS_PUT, LOST),
    "cd into a relative directory that is not there": ("cd nope-does-not-exist", STAYS_PUT, LOST),
    "a bare cd, which goes home": ("cd", HOME, HOME),
    # THE QUOTING IS THE WHOLE CELL: a shell expands a tilde and then removes quoting, so a QUOTED
    # tilde is a directory named `~` and nothing else -- while a reader that expands the reading it
    # is handed expands what the quoting was there to suppress (H31).
    "cd to a tilde the quoting keeps": ('cd "~"', STAYS_PUT, LOST),
    "cd to a tilde the shell expands": ("cd ~", HOME, HOME),
    # A TARGET ONLY THE SHELL CAN COMPUTE. The variable is set in the ENVIRONMENT of the arbitrating
    # shell and nowhere else, which is the real shape of it: what the gate is handed is the text,
    # and the text is not what the shell uses. (`_changes_the_protected_file` sets it; the gate
    # process is started without it.)
    "cd to a target this reader cannot name": ('cd "$%(var)s"', AT_TARGET, LOST),
    "pushd to a directory that is there": ("pushd %(to)s", AT_TARGET, AT_TARGET),
    "pushd with a second operand the shell rejects": ("pushd %(to)s x", STAYS_PUT, LOST),
    "popd with nothing pushed": ("popd", STAYS_PUT, STAYS_PUT),
    "pushd with an empty stack": ("pushd", STAYS_PUT, STAYS_PUT),
}

# WHERE THE LINE STANDS WHEN THE MOVE HAPPENS -- the axis DEC-0018 asks for, and the one the table
# had only one value of. It is not a spelling but the only property that decides what a relative
# word names: the base is in the tree the write points into, or it is not. With the base INSIDE,
# staying is the refusing direction; with the base OUTSIDE, every move this reader cannot compute
# may be the one that goes back IN, and staying is the passing one.
BASES = {
    "with the base inside the tree": ("", "%(out)s", "R_OUT"),
    "with the base outside it": ("cd %(out)s ; ", '"%(here)s"', "R_HERE"),
}
# What the arbitrating shell is told about the two trees, and the gate is not. A directory verb
# whose target is only in the environment is the shape H16 carries: the gate is handed the text.
TREE_VARIABLES = {"R_OUT": "outside", "R_HERE": "the sandbox"}


def _other_spellings(word):
    """Spellings that differ from `word` and that a case-folding reader cannot tell from it.

    NOT A LIST OF CASES BUT THE FOLD ITSELF: the kits' `_stage_verb` hands the verb out through
    `str(token).lower()`, so every spelling here is one that reader answers `word` for, and a POSIX
    shell answers `command not found` for. What makes them different words is generated from the
    word, so a verb this repo gains is crossed in its miscased spellings on the day it appears.
    """
    return sorted({word.upper(), word.capitalize(), word.title()} - {word})


def _verb_shapes(harness):
    """One move per verb of every shell this reader knows, per spelling it cannot tell apart.

    DEC-0016: the enumeration the reader decides from (`_harness.SHELLS`) GENERATES the values of
    this axis, so the checked set cannot be narrower than the deciding one. Both columns are derived
    from the same claim -- this line is sent to the Bash tool, so the shell moves exactly where a
    word is spelled exactly like a verb of the POSIX table, and so does the reader.

    A SPELLING THE POSIX TABLE DOES NOT CARRY IS A COMPUTED NON-MOVE ON BOTH SIDES, not a doubt:
    the shell answers `command not found` and stays, and `_harness._directory_role` answers None,
    which is the one branch of `follow` that is an ANSWER rather than a failure to compute.

    A POP HAS NOTHING TO RETURN TO HERE, so its cell stays put in every spelling and carries
    little; the pop shapes that carry the weight are in `LOOSE_SHAPES`, where a stack can be built
    first. Generated all the same, because a value left out is the cut DEC-0016 is about.
    """
    posix = harness.SHELLS["Bash"]["verbs"]
    known = {}
    for shell in sorted(harness.SHELLS):
        known.update(harness.SHELLS[shell]["verbs"])
    out = {}
    for verb, role in sorted(known.items()):
        for spelling in [verb] + _other_spellings(verb):
            runs = posix.get(spelling) == role and role != harness._POP
            where = AT_TARGET if runs else STAYS_PUT
            out["%s spelled %r" % (role, spelling)] = (
                spelling if role == harness._POP else "%s %%(to)s" % spelling, where, where)
    return out


def _substitution_shapes(harness):
    """One line per pair the reader reads as a command substitution, for the shell that arbitrates.

    THE ENUMERATION GENERATES ITS OWN CELLS (DEC-0016), and here it has to: no reader this
    apparatus borrows from knows what a substitution is, so `_harness.SHELLS[...]["substitutions"]`
    is an enumeration with nothing to derive it from. The cell therefore measures BOTH ends of the
    entry -- the shell REALLY runs the command inside the pair (a dead entry writes nothing and the
    first column says so), and the gate refuses the write it hides (a missing entry passes it, and
    the second column says so).

    The verb in front is a READ-ONLY one on purpose: a substitution behind a writing verb is
    refused for the verb's sake, which would make the cell green for a reason that is not this one.
    """
    out = {}
    for opener, closer in harness.SHELLS["Bash"]["substitutions"]:
        out["a write in a %s%s substitution behind a read-only verb" % (opener, closer)] = (
            "echo %s%%(write)s%s" % (opener, closer), True, True)
    return out


def _quoted_write_shapes(harness):
    """The quoting axis over the PLAIN relative write -- the half of it where no tilde is involved.

    WHY IT IS HERE AND NOT ONLY IN THE TILDE CHECK SET: `_quotings` exists because where the quoting
    stands decides whether an expansion happens, and a reader that answered that question by
    refusing quoted words outright would satisfy the tilde half and break every ordinary path. So
    every run of an ordinary relative path is quoted in turn, and every one of these cells has the
    same two columns -- a shell writes the protected file exactly as it does without the quoting
    (`_compat.shell_words` resolves it for the reader, measured there), and the gate refuses.
    """
    out = {}
    for label, word in sorted(_quotings(harness, RELATIVE_TARGET).items()):
        if label != UNQUOTED:
            out["a write into a relative path %s" % label] = (
                'sed -i "s/a/b/" %s' % word, True, True)
    return out


def _steps_over(reader, word):
    """Does the kits' `_stage_verb` really walk past this word to find the verb behind it?"""
    return reader._stage_verb([word, "cd", "x"]) == "cd"


def _witnesses(test):
    """Words a branch's own condition offers as something it steps over.

    THE CONSTANTS THE CONDITION COMPARES AGAINST, in the two shapes a condition can carry them:
    the member of a list (`low in ("sudo", ...)`) and the substring of a test (`"=" in low`). The
    second needs the constant put INTO a word to be one, so both are offered and the caller proves
    each against the function that runs -- a candidate the reader does not step over drops out
    there, and a branch left with none is reported rather than skipped.
    """
    out = []
    for node in ast.walk(test):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value:
            out.extend([node.value, "a%sb" % node.value])
    return out


def _skipped_words(harness):
    """The words the kits' `_stage_verb` steps over while looking for the verb -- from EVERY branch.

    READ OUT OF THE FUNCTION THAT RUNS, never typed here: its source is parsed, every branch whose
    body is a `continue` is one that steps over something, and the words come out of that branch's
    own condition (`_witnesses`) and are then PROVEN by asking the running function.

    DEC-0018, AND THIS IS THE HALF THAT COST A ROUND: a skip written as a PREDICATE generates no
    value the way a skip written as a LIST does. The reader has both -- `low in ("sudo", ...)` and
    `"=" in low and not low.startswith("-")` -- and the second had no cell in 638, so an assignment
    in front of a directory verb was crossed nowhere while `_is_the_command_name` decided about it.
    Reading branches instead of tuples is what makes the difference; proving each witness against
    the function is what keeps the values honest.

    THE PUNCTUATION BRANCH DROPS OUT BY A PROPERTY and not by its position: what it holds is the
    shell's grouping punctuation, and punctuation is what `_harness._SYNTAX_CHARACTERS` defines --
    a word made only of it is syntax and is allowed to stand in front of a command name.
    """
    words, empty = [], []
    for branch, proven in _skip_branches(_kits_reader(harness)):
        if not proven:
            empty.append(branch)
        elif not all(set(word) <= harness._SYNTAX_CHARACTERS for word in proven):
            words.extend(proven)
    assert not empty, (
        "these branches of the kits' `_stage_verb` step over a word this test could not name, so "
        "they are crossed nowhere: %s" % empty)
    return sorted(set(words))


def _kits_reader(harness):
    harness._add_kit_paths(ROOT)
    return harness._from_kit("gate_write_scope")


def _stepping_branches_of(function):
    """The `if ...: continue` branches in one function's source -- a branch that steps over a word."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    return [node for node in ast.walk(tree) if isinstance(node, ast.If)
            and node.body and all(isinstance(step, ast.Continue) for step in node.body)]


def _the_kits_prefix_walk(reader):
    """The kits' function that WALKS PAST the prefix words -- `_stage_verb` or what it delegates to.

    THE NAME WAS THE WRONG THING TO PIN, and that is measured rather than foreseen: this reader
    parsed `_stage_verb` directly until 2026-09-13, when the kits moved the walk one function down
    into `_command_word_at` -- one walk for two facts, which word a stage runs and where its
    operands start. `ast.parse` then found no branch at all and the assert below took the WHOLE
    gate suite down at COLLECTION, which is the loudest possible way to learn that a test encoded
    a neighbour's shape instead of its property.

    THE PROPERTY IS "the function whose source carries the stepping branches", and the way to it
    is the CALL GRAPH from `_stage_verb`, walked breadth-first with a visited set -- not a name and
    not a fixed depth. A fixed depth was tried while writing this and was wrong within the hour:
    `_stage_verb` delegates to `_effective_command_word`, which delegates to `_command_word_at`,
    and the walk sits two hops down. A depth is the same kind of claim as a name.
    """
    queue, seen = [reader._stage_verb], set()
    while queue:
        function = queue.pop(0)
        if id(function) in seen:
            continue
        seen.add(id(function))
        try:
            branches = _stepping_branches_of(function)
            tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
        except (OSError, TypeError, SyntaxError):
            continue
        if branches:
            return function, branches
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            called = getattr(reader, node.func.id, None)
            if callable(called) and id(called) not in seen:
                queue.append(called)
    return reader._stage_verb, []


def _skip_branches(reader):
    """`[(the branch as text, the words it is PROVEN to step over)]` of the kits' prefix walk.

    THE BRANCHES AND NOT THE TUPLES IN THEM, which is what makes a skip written as a predicate
    visible at all (DEC-0018). Kept apart from `_skipped_words` on purpose: the test that asks
    whether every branch has a cell must not ask the function that BUILDS the cells, or the two
    agree by construction and a generator that reads only tuples stays green.

    WHICH function carries the walk is `_the_kits_prefix_walk`'s question -- see it for why the
    name is not pinned here.
    """
    _walk, branches = _the_kits_prefix_walk(reader)
    assert branches, (
        "the kits' `_stage_verb` steps over nothing any more, and neither does anything it calls, "
        "so the axis that crosses what it steps over could not be generated")
    return [(ast.unparse(branch.test),
             sorted({word for word in _witnesses(branch.test) if _steps_over(reader, word)}))
            for branch in branches]


# The value of the quoting axis that leaves the word as it was. Named once, because both the
# generator and the check that the axis measured ANYTHING have to mean the same value by it.
UNQUOTED = "with no quoting in it"


def _quotable_runs(harness, word):
    """[(what this run is, start, stop)] -- the runs of `word` a shell can be told to keep literal.

    TWO DEFINITIONS OF THE READER STRUCTURE A WORD HERE, and neither is a list: the separators cut
    it into spans (`_harness._PATH_SEPARATORS`), and a leading tilde opens a prefix that ENDS at the
    first of them (`_harness._tilde_prefix`) -- so the tilde and the rest of that prefix are two
    runs and not one. That split is the whole point of the axis: quoting either of them keeps the
    word literal in a shell, and quoting anything BEHIND them changes nothing about the expansion.
    """
    runs, start = [], 0
    if harness._tilde_prefix(word) is not None:
        runs.append(("the tilde itself", 0, len(harness._TILDE)))
        start = len(harness._TILDE)
    separators, opened = 0, start
    for index in range(start, len(word) + 1):
        if index < len(word) and word[index] not in harness._PATH_SEPARATORS:
            continue
        if index > opened:
            runs.append(("the rest of the tilde prefix" if runs and not separators
                         else "the span %d separators in" % separators, opened, index))
        opened, separators = index + 1, separators + 1
    return runs


def _quotings(harness, word):
    """{label: `word` with one run of it quoted} -- generated out of what quoting IS, not listed.

    THE AXIS IS WHERE THE QUOTING STANDS. A shell removes quoting character by character and
    expands the tilde prefix BEFORE it does, so a word that carries quoting somewhere is not a word
    whose expansion was suppressed -- only quoting inside the prefix suppresses anything. The
    spellings come from the reader's own alphabet (`shlex.quotes` and its escape) instead of from
    `"` alone, and the places come from `_quotable_runs`.

    THIS IS THE AXIS THAT WAS MISSING, and its absence was a hole rather than a gap in coverage.
    Measured 2026-08-07 through the real gate with a real bash as arbiter over the file: 0 of 1440
    cells and 0 of the 615 tilde subjects carried quoting in the target word, and
    `sed -i "s/a/b/" ~+/"team-kits"/kernel/state.py` was rc 0 while bash rewrote the protected file
    -- the same shape reaching `.claude/settings.json`, `.claude/hooks/_harness.py` and
    `project_memory/` (`docs/POST_V2_WISHLIST.md` H33).
    """
    reader = shlex.shlex("", punctuation_chars=True)
    out = {UNQUOTED: word}
    for what, start, stop in _quotable_runs(harness, word):
        for mark in sorted(set(reader.quotes)):
            out["with %s quoted by %s" % (what, mark)] = (
                word[:start] + mark + word[start:stop] + mark + word[stop:])
        out["with %s escaped" % what] = word[:start] + reader.escape + word[start:]
    return out


def _prefix_shapes(words):
    """One move per word the kits' reader steps over to find the verb.

    THE SECOND HALF OF DEC-0016: the reader decides the verb out of these branches, so the branches
    generate the values. The reader's column is `LOST`, which is what `_harness._is_the_command_name`
    now costs -- a word in front of the command name is a command of its own, and whether it hands
    the verb to a CHILD (`env cd` never reaches the builtin) or leaves it in the shell (`command cd`
    does) is not readable from here, so the position is given up. The shell's column is UNCLAIMED
    for the same reason, from the other side.
    """
    return {"cd behind %r, which the kits' reader steps over" % word:
            ("%s cd %%(to)s" % word, UNCLAIMED, LOST) for word in words}

# What has no directory verb in it at all, or more than one. WHERE A COMMAND ENDS is its own
# question (`_harness._cuts`), and so is a second move that undoes the first -- neither is a cell of
# the cross above, so both stand here with both columns written down and measured like every other.
# `%(here)s` is the tree the line runs in, spelled absolutely: a POP is only dangerous when the top
# of the stack lies OUTSIDE while the position is INSIDE, and that takes two directories.
LOOSE_SHAPES = {
    # a command that has ENDED takes nothing with it: what follows is a command of its own, and the
    # verb in front of it says nothing about the words behind it
    "a write behind a backgrounded read": ("echo hi & %(write)s", True, True),
    "a write behind a backgrounded write": ('sed -i "s/x/y/" docs/note.md & %(write)s', True, True),
    "a write behind a glued terminator": ("(echo hi);%(write)s", True, True),
    "a write behind a glued and": ("(echo hi)&&%(write)s", True, True),
    "a redirect glued to the terminator in front of it": ("echo hi;>%(target)s", True, True),
    "a redirect glued to a terminator behind a group": ("(echo hi);>%(target)s", True, True),
    "a redirect behind a spaced terminator": ("echo hi ; > %(target)s", True, True),
    "a write behind a spaced terminator": ("echo hi ; %(write)s", True, True),
    "a write behind a group that read": ("( echo hi ) ; %(write)s", True, True),
    "a write fed through a pipe": ("echo hi | %(write)s", True, True),
    "a write behind a pipe glued to a bracket": ("(echo hi)|%(write)s", True, True),
    "a write behind a pipe that carries stderr too": ("echo hi |& %(write)s", True, True),
    "a write behind a pipe that carries stderr, glued": ("echo hi|&%(write)s", True, True),
    "a move behind a pipe that carries stderr": ("echo hi |& cd %(out)s ; %(write)s", True, True),
    "a move in front of a pipe that carries stderr": ("cd %(out)s |& true ; %(write)s", True, True),
    "a move behind a pipe glued to a bracket": ("(echo hi)|cd %(out)s ; %(write)s", True, True),
    # two moves, where the second is what decides
    "a move and a move back": ("cd %(out)s ; cd - ; %(write)s", True, True),
    "a move and a second move that stays": ("cd %(out)s ; cd . ; %(write)s", False, False),
    "a move continued conditionally": ("cd %(out)s && cd . ; %(write)s", False, False),
    "a push and a pop": ("pushd %(out)s ; popd ; %(write)s", True, True),
    "a push and a pop of the top by index": ("pushd %(out)s ; popd +0 ; %(write)s", True, True),
    "a push and a bare push that swaps back": ("pushd %(out)s ; pushd ; %(write)s", True, True),
    "a push and one pop too many": ("pushd %(out)s ; popd ; popd ; %(write)s", True, True),
    # A POP WITH THE STACK OUTSIDE AND THE POSITION INSIDE. The one direction in which STAYING is
    # not the careful answer, and it was a hole in one tool call: the shell rejects the operand
    # list, stays inside and rewrites the protected file, while the base had been popped out.
    "a pop whose operand the shell rejects":
        ('cd %(out)s ; pushd "%(here)s" ; popd x ; %(write)s', True, True),
    "a pop with an option the shell rejects":
        ('cd %(out)s ; pushd "%(here)s" ; popd -q ; %(write)s', True, True),
    "a pop of an index the stack does not have":
        ('cd %(out)s ; pushd "%(here)s" ; popd +9 ; %(write)s', True, True),
    "a pop that only drops the entry": ('cd %(out)s ; pushd "%(here)s" ; popd -n ; %(write)s',
                                        True, True),
    "a push that only adds an entry, then a pop":
        ('cd %(out)s ; pushd -n "%(here)s" ; popd ; %(write)s', True, True),
    # A PUSH THIS READER COULD NOT MAKE IS A PUSH THE SHELL MAY WELL HAVE MADE, and then its stack
    # holds an entry this one does not -- so the bare pop behind it goes back INTO the tree while
    # this reader would have stayed outside. Measured 2026-08-07: rc 0 before, and the shell really
    # rewrites the protected file.
    "a push this reader cannot make, and a pop the shell can":
        ('R="%(here)s" ; pushd "$R" ; cd %(out)s ; popd ; %(write)s', True, True),
    # ...and the counter-end, which is what stops "never follow a pop": here the shell really does
    # go back out, and the write must stay allowed
    "a pop the shell really makes, back out of the tree":
        ('cd %(out)s ; pushd "%(here)s" ; popd ; %(write)s', False, False),
    # THE BASE NEVER LEAVES THE REPO HERE, and the write still lands in the protected tree: what
    # decides is the SUBTREE the base stands in, not the repo boundary. Measured 2026-08-07: rc 0
    # before, and bash really rewrites the protected file.
    "a move inside the tree the reader cannot compute":
        ('cd docs ; command cd .. ; %(write)s', True, True),
    # a closer that stands INSIDE the substitution's own quoting -- see `_harness._closings`
    "a write in a substitution whose closer is quoted":
        ('echo $(sed -i "s/a/)/" %(target)s)', True, True),
}


def _reaches_the_tree(landing, base_inside):
    """Does an actor that ended up HERE resolve the relative write into the protected tree?

    The one question both columns are made of, and it needs the base to answer -- which is why the
    base is an axis: `AT_TARGET` is the tree when the line started outside it and is not when it
    started inside, and `STAYS_PUT` is exactly the other way round.
    """
    if landing == HOME:
        return False  # neither tree, whichever direction the line ran in
    return base_inside if landing == STAYS_PUT else not base_inside


def _crossed():
    """`{label: (template, does the shell write the protected file, does the gate refuse)}`.

    THE COLUMNS ARE DERIVED, NOT COLLECTED, and that is DEC-0014 applied to this table: a relative
    write lands in the protected tree UNLESS the shell ran the WORD as the verb this reader takes it
    for, ran it ITSELF, could account for its operands and could make the move -- which are exactly
    the conditions `_harness.WorkingDirectory` claims for itself. Every one of them is an axis here,
    so a cell nobody thought about is still in the table. THE VALUES of those axes are generated by
    the enumerations the reader decides from (`_verb_shapes`, `_prefix_shapes`,
    `_substitution_shapes`), which is DEC-0016.

    AND THE CONDITION THAT WAS WRITTEN AS A BRANCH IS AN AXIS TOO, which is DEC-0018 and this
    round's correction: where the base STANDS decides what "staying" means, so `BASES` crosses every
    shape twice. Of the 32 moves generated before, 25 pointed out of the tree, 7 nowhere and NONE
    back in -- so the direction in which staying is the passing answer had no cell at all, and seven
    line shapes were rc 0 with the shell writing the protected file.

    TWO COLUMNS, because one could only be kept by leaving out every shape the reader is knowingly
    too strict about -- and leaving them out is what made the miscased verb and the word in front of
    it invisible for two rounds. `test_the_shell_writes_where_the_table_of_line_shapes_says` takes
    the first column from a real shell, cell by cell, and says so instead of passing when it
    disagrees; `test_gate1_refuses_a_line_exactly_where_the_shell_would_write` takes the second from
    a real gate process and asserts the invariant that binds them: where the shell writes, the gate
    refuses.

    WHAT IS STILL NOT IN HERE: a directory verb inside `while ... do` or inside `if` (H24 in
    `docs/POST_V2_WISHLIST.md`). Both come out rc 2 while the shell really moves, and they are
    measured as friction in `docs/reviews/2026-08-05-tsk0015-measurements.md` (section 6) instead.
    """
    harness = _reader()
    out = {}
    moves = dict(MOVES)
    moves.update(_verb_shapes(harness))
    moves.update(_prefix_shapes(_skipped_words(harness)))
    for base, (prefix, target, variable) in BASES.items():
        for position, (frame, whose) in POSITIONS.items():
            for move, (line, shell_where, reader_where) in moves.items():
                in_the_shell = whose == IN_THE_SHELL
                # A MOVE THE SHELL RUNS IN A CHILD IS A COMPUTED NON-MOVE FOR BOTH, and that is why
                # the reader does not lose its position there either: `follow` proves the childhood
                # before it asks anything it could fail to compute. UNCLAIMED stays UNCLAIMED in
                # every position, and that is not a convenience: a word this reader says nothing
                # about can make the frame around it something else entirely -- measured,
                # `true | ! cd <target> ; <write>` is a syntax error in bash and NOTHING in the
                # line runs, the write included.
                reader_lands = reader_where if in_the_shell else STAYS_PUT
                base_inside = not prefix
                writes = (UNCLAIMED if shell_where is UNCLAIMED
                          else _reaches_the_tree(shell_where if in_the_shell else STAYS_PUT,
                                                 base_inside))
                refuses = (reader_lands == LOST
                           or _reaches_the_tree(reader_lands, base_inside))
                out["%s -- %s -- %s" % (move, position, base)] = (
                    prefix + frame.replace("%(move)s", line.replace("%(to)s", target)
                                           .replace("%(var)s", variable)),
                    writes, refuses)
    out.update(LOOSE_SHAPES)
    out.update(_substitution_shapes(harness))
    out.update(_quoted_write_shapes(harness))
    return out


LINE_SHAPES = _crossed()


def _line(template, outside, here):
    return template % {"out": '"%s"' % outside, "write": RELATIVE_WRITE,
                       "target": RELATIVE_TARGET, "here": str(here).replace("\\", "/")}


def _posix_shells():
    """Every shell on this host that COULD arbitrate -- candidates, never a decision.

    Which of them sees this filesystem is measured by the caller (`_sees_this_filesystem`) and not
    assumed here: on Windows the first `bash` on PATH is the WSL launcher, and its `C:/...` is a
    different tree. The last candidate is derived rather than typed -- the shell that ships beside
    the version control system this repo already requires.
    """
    out = []
    for directory in (os.environ.get("PATH") or "").split(os.pathsep):
        for name in ("bash.exe", "bash"):
            out.append(os.path.join(directory, name))
    vcs = shutil.which("git")
    if vcs:
        out.append(os.path.join(os.path.dirname(os.path.dirname(vcs)), "bin", "bash.exe"))
    return [path for path in out if os.path.isfile(path)]


def _reads_back(shell, path, nonce):
    """Does this shell hand back `nonce` out of `path`, spelled the way this host writes it?

    THE SHELL'S OWN REDIRECT AND NO PROGRAM: `cat` would answer for what is installed beside the
    shell, and the question here is where the SHELL resolves a path.

    THE CONTENT DECIDES, NOT THE EXIT CODE -- a redirect that finds nothing leaves the `printf`
    after it at rc 0. Measured 2026-08-15 against the WSL launcher: rc 0, empty stdout, `No such
    file or directory` on stderr. An exit code would have called that shell a reader of this
    filesystem, and a path that merely EXISTS is answered by any file of that name in any tree.

    AND THE CHILD IS GIVEN A `cwd`, AND ONLY THAT HALF OF A SHELL'S DIRECTORY STATE: a run of this
    suite stands in THIS repo, so a shell started from it would stand there too. The rest of that
    state -- the names a word like `~-` is resolved out of -- is left INHERITED here, and this line
    carries no such word to point anywhere: one absolute redirect and nothing relative.
    `_changes_the_protected_file` sets those names as well, because the lines it runs do carry them.
    """
    line = 'IFS= read -r seen < "%s"; printf "%%s" "$seen"' % path
    try:
        done = subprocess.run([shell, "-c", line], cwd=os.path.dirname(path), capture_output=True,
                              text=True, timeout=120, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return (done.stdout or "").strip() == nonce


def _sees_this_filesystem(shell, where):
    """Is `where` the same directory for this shell as it is for this process?

    THE ARBITER IS THE MEASUREMENT, and choosing it by "it runs `true`" cost this suite a control
    that could not fail (BUG-0051): since this host registered a WSL distro, the launcher in
    system32 answers `-c true` with rc 0 and stands FIRST on PATH. It is not a shell that fails,
    and it is not one that stays off this tree either: a RELATIVELY named word reaches THIS side
    through the `cwd` it translates, and a payload's `sed -i` really rewrites the file it names.
    The ABSOLUTE spelling alone lands in the distro's own filesystem -- so a check set whose reach
    is spelled absolutely runs, reports nothing wrong and never arrives.

    SO THE PROBE IS A NONCE THIS PROCESS JUST WROTE INTO `where`, read back through the absolute
    spelling: a shell that hands it back resolved that spelling to the very file that was written,
    which is what two trees being one tree means. Both ends of the probe are driven by
    `test_the_arbiter_is_a_shell_that_reads_back_what_this_process_writes`.
    """
    nonce = os.urandom(16).hex()
    path = os.path.join(where, ".sees-this-filesystem-%s" % nonce)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(nonce)
    try:
        return _reads_back(shell, _sandbox_module().posix(path), nonce)
    finally:
        os.remove(path)


def _changes_the_protected_file(shell, sandbox, line, outside=""):
    """Run `line` in `sandbox` and report whether the protected file it names really changed.

    CHANGED, not "holds what the write puts there": a redirect TRUNCATES, and a criterion that
    looked for the new content read an emptied file as untouched -- measured 2026-08-05, which is
    how `echo hi;>team-kits/<file>` looked harmless while it was destroying the file.

    THE TWO TREES ARE ALSO IN THE ENVIRONMENT (`TREE_VARIABLES`), and only here: a line whose target
    stands in a variable is a line whose text says nothing about where it goes, and the gate is
    started without them (`run`).

    AND THE SHELL'S DIRECTORY STATE IS SET, NOT INHERITED, BECAUSE `cwd` IS NOT ALL OF IT -- through
    `_sandbox.sandbox_environment`, which is the same answer the scripts a round writes beside this
    file stand on, so there is one of it rather than two that drift. WHICH names those are is that
    module's answer and not this docstring's: a word that does not name a directory is resolved out
    of the shell's own state, and pieces of that state come in through the ENVIRONMENT -- `~-` reads
    `OLDPWD`, a bare `~` reads `HOME`, a relative `cd` word is looked up along `CDPATH`. A suite
    started in the tree it measures hands the shell that tree in `OLDPWD` -- and `~-` is a subject
    of this check set, so one line
    with a perfectly correct `cwd` rewrote `team-kits/kernel/state.py` of THIS repo. Measured
    2026-08-07 in isolation: with `cwd` a sandbox and `OLDPWD` another tree, `printf "%s\\n" ~-`
    prints the other tree and `sed -i "s/a/b/" ~-/team-kits/kernel/state.py` rewrites the file in
    it. That file has been destroyed that way repeatedly and the damage put down to a script
    standing in the wrong directory; the directory was never the whole answer
    (`docs/POST_V2_WISHLIST.md` H37 carries the damages).
    `test_the_arbiter_cannot_be_pointed_out_of_its_sandbox_by_the_state_a_tilde_reads` measures it.
    """
    subject = os.path.join(sandbox, *RELATIVE_TARGET.split("/"))
    with open(subject, "w", encoding="utf-8") as handle:
        handle.write("a")
    here = str(sandbox).replace("\\", "/")
    subprocess.run([shell, "-c", line], cwd=sandbox, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=120,
                   env=dict(_sandbox_module().sandbox_environment(sandbox),
                            R_OUT=outside, R_HERE=here))
    with open(subject, encoding="utf-8") as handle:
        return handle.read().strip() != "a"


def _claimed(label):
    """What `LINE_SHAPES` says the shell does with this shape, or None where it claims nothing."""
    return LINE_SHAPES[label][1]


def _can_arbitrate(shell, sandbox, outside=None):
    """Does this shell see the trees this measurement is about, as THIS host spells them?

    TWO MEASUREMENTS, and the second is the one the WSL launcher passes on its own: every tree a
    check set names ABSOLUTELY has to be the same tree for this shell (`_sees_this_filesystem`),
    and a RELATIVELY named write has to really land in the sandbox -- which is also where the `sed`
    those lines are written with is measured. The launcher reaches the sandbox through the `cwd` it
    translates and has `sed`, so with the first question left out every move whose word names a
    tree ABSOLUTELY would look like a move that failed, measured against a different filesystem.

    `outside` is the second tree a caller crosses with; a caller whose lines name only its own
    sandbox passes none.
    """
    trees = [sandbox] + ([] if outside is None else [outside])
    if not all(_sees_this_filesystem(shell, tree) for tree in trees):
        return False
    return _changes_the_protected_file(shell, sandbox, RELATIVE_WRITE)


def _sandbox(base, index):
    """One tree the table can be measured in -- `index` of them, so the shapes can run in parallel.

    Every shape needs the protected path to hold a known content while its own line runs, so two
    lines sharing a tree would read each other's answer.
    """
    sandbox = os.path.join(base, "sandbox-%d" % index)
    os.makedirs(os.path.join(sandbox, "team-kits", "kernel"), exist_ok=True)
    # one shape writes a second, unprotected file first -- it has to exist for the line to run
    os.makedirs(os.path.join(sandbox, "docs"), exist_ok=True)
    with open(os.path.join(sandbox, "docs", "note.md"), "w", encoding="utf-8") as handle:
        handle.write("x")
    return sandbox


# THE KINDS OF PROCESS THIS SUITE STARTS, and how many of each are measured at once. Every one of
# them is a real process, and each subject has its own tree (`_sandbox`, `_two_sided_repo`) or, for
# a gate, no tree at all -- so the width changes what a run COSTS and not what it measures.
#
# A NUMBER PER KIND AND NOT ONE FOR ALL. What bounds a run here is how many processes this host will
# start per second rather than how many cores it has, and the kinds do not reach that bound at the
# same width. The rates behind the first two widths, the point each of them saturates at and the
# counter-measurement that says a wider pool stops paying were taken for TSK-0090 and stand in
# docs/reviews/2026-08-29-tsk0090-measurements.md, section 3 -- and beside them, in section 4, how
# far this host's own throughput moved between two hours of the same day. THE THIRD WIDTH IS NOT
# SCANNED and is therefore not a number of its own: it is DERIVED from the gate width below, so it
# cannot drift away from the one measurement it stands on. What pooling those scenarios bought is
# in section 5, which says nothing about where they saturate.
SHELL_LINES, GATE_PROCESSES, REPOSITORIES = ("shell lines", "gate processes",
                                             "repository scenarios")
AT_ONCE = {SHELL_LINES: 16, GATE_PROCESSES: 10}
AT_ONCE[REPOSITORIES] = AT_ONCE[GATE_PROCESSES]


def _slots(width):
    """`width` tokens, each of which stands for one tree a subject may be measured in."""
    slots = queue.Queue()
    for index in range(width):
        slots.put(index)
    return slots


def _all_at_once(batches):
    """`{name: {subject: work(slot, subject)}}` for several batches, measured in ONE run.

    A BATCH IS `(name, kind, work, subjects)`, AND THE KINDS RUN AT THE SAME TIME. The bound on a
    run of this suite is this host's process creation, and the two kinds do not draw on it in the
    same way -- measured for TSK-0090, the same two batches run TOGETHER finish sooner than one
    after the other (docs/reviews/2026-08-29-tsk0090-measurements.md, section 5). Batches of one
    kind share that kind's pool rather than each opening one of their own, so the width below is
    the width of the whole run and not of a caller.

    A SLOT IS HELD, NOT COMPUTED FROM THE POSITION IN THE LIST: with `index % AT_ONCE` the seventh
    subject took the tree the first one was still measuring in, and six shapes of the table came
    back with each other's answers -- caught by the shell arbitration itself, which is what it is
    for. A slot is taken from the queue and given back, so two running subjects OF ONE KIND never
    share one -- and per kind is the whole claim: the kinds have separate queues, and a slot means
    whatever that kind's work makes of it (a tree for a shell line, nothing for a gate process).

    WHAT A BATCH RAISES IS RAISED HERE, in the calling thread, once every kind has been joined --
    a failure that stayed inside a worker thread would leave the caller reading an answer table
    with holes in it as if it were a measurement. `BaseException` and not `Exception`, because the
    outcome pytest itself raises for a skip or a fail is one: with the narrower clause a
    `pytest.skip` inside a work function died in the driving thread and the caller got a SHORT
    table and no word about it. No work function reaches that today; the clause is what makes the
    sentence above true rather than nearly true.

    Both of those and the completeness of the table are driven by
    `test_the_run_that_measures_the_cells_holds_a_slot_answers_every_subject_and_raises`.
    """
    out = {name: {} for name, _kind, _work, _subjects in batches}
    grouped = {}
    for name, kind, work, subjects in batches:
        grouped.setdefault(kind, []).extend((name, work, subject) for subject in subjects)
    raised = []

    def drive(kind, items):
        slots = _slots(AT_ONCE[kind])

        def held(item):
            name, work, subject = item
            slot = slots.get()
            try:
                return name, subject, work(slot, subject)
            finally:
                slots.put(slot)

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=AT_ONCE[kind]) as pool:
                futures = [pool.submit(held, item) for item in items]
                for future in concurrent.futures.as_completed(futures):
                    name, subject, answer = future.result()
                    out[name][subject] = answer
        except BaseException as problem:
            raised.append(problem)

    threads = [threading.Thread(target=drive, args=(kind, items))
               for kind, items in sorted(grouped.items())]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if raised:
        raise raised[0]
    return out


def _in_parallel(work, subjects, kind):
    """`{subject: work(slot, subject)}` for one batch of one kind (`_all_at_once`)."""
    return _all_at_once([("only", kind, work, subjects)])["only"]


def test_the_run_that_measures_the_cells_holds_a_slot_answers_every_subject_and_raises():
    """The three things every check set below is read through `_all_at_once` for.

    A SLOT IS A TREE, FOR THE KIND WHOSE WORK MAKES ONE OF IT. Two subjects of that kind holding
    one at the same time would each read the other's line out of the protected file, and that is
    not a red -- it is a column with wrong values in it, which is how six shapes of the cross table
    once came back with each other's answers. So the work here records what holds a slot of its own
    kind while it holds it, and says so if two ever overlap. ACROSS kinds the numbers are meant to
    repeat: each queue is its own, and what a slot names is that kind's business.

    WHAT A WORKER RAISES HAS TO REACH THE CALLER. A batch that fails inside a thread and leaves an
    answer table with holes in it is the same failure one level up: the caller reads a short table
    as a measurement. The subject is a work function that raises, and what is asserted is that the
    exception comes out here rather than the table.

    AND EVERY SUBJECT IS ANSWERED IN ITS OWN BATCH AND IN NO OTHER, over more subjects than any
    kind has slots, so the queue really has to hand a slot back -- and with one KIND carrying TWO
    batches, because that is the only shape in which an answer can be filed under the wrong batch
    at all. With a single batch per kind the claim was one this test could not have failed.
    """
    holders, overlapped = {}, []
    guard = threading.Lock()

    def work(slot, subject):
        held = (subject.rsplit(" ", 1)[0], slot)
        with guard:
            overlapped.extend([(held, holders[held], subject)] if held in holders else [])
            holders[held] = subject
        time.sleep(0.01)
        with guard:
            holders.pop(held, None)
        return subject

    counts = {kind: 3 * AT_ONCE[kind] for kind in AT_ONCE}
    # every kind once, and the first kind a SECOND time, so one kind carries two batches
    named = [(kind, kind) for kind in sorted(AT_ONCE)] + [("a second batch of one kind",
                                                           sorted(AT_ONCE)[0])]
    batches = [(name, kind, work,
                ["%s %d" % (name, index) for index in range(counts[kind])])
               for name, kind in named]
    answers = _all_at_once(batches)
    assert not overlapped, (
        "two subjects held the same slot at the same time, so each of them measured in a tree the "
        "other was using: %s" % overlapped[:5])
    for name, kind in named:
        wanted = ["%s %d" % (name, index) for index in range(counts[kind])]
        assert sorted(answers[name]) == sorted(wanted), (
            "the %r batch came back with %d of %d subjects answered, and %s under a subject it "
            "never carried"
            % (name, len(answers[name]), len(wanted), sorted(set(answers[name]) - set(wanted))[:3]))
        assert all(answers[name][subject] == subject for subject in wanted), (
            "an answer of the %r batch was filed under another subject" % name)

    def raises(_slot, subject):
        raise RuntimeError("this batch failed on %s" % subject)

    def skips(_slot, _subject):
        pytest.skip("a work function that reports the outcome pytest reports")

    with pytest.raises(RuntimeError):
        _all_at_once([("fails", GATE_PROCESSES, raises, ["one"]),
                      ("runs", SHELL_LINES, work, ["two"])])
    # the same, with the outcome pytest itself raises -- not an `Exception`, and the one a narrower
    # clause let through while the caller read a table with a hole in it as a measurement
    with pytest.raises(BaseException) as outcome:
        _all_at_once([("skips", GATE_PROCESSES, skips, ["one"])])
    assert not isinstance(outcome.value, Exception), (
        "this subject no longer raises the kind of outcome the clause is about (%r), so the half "
        "of it that is not an `Exception` was measured against nothing" % outcome.value)


class _Cells(object):
    """The answer tables of the check sets below, and what the tests need to talk about them."""

    def __init__(self, **columns):
        self.__dict__.update(columns)


# WHICH TEST EACH COLUMN OF THE CELL PHASE IS THE COLUMN OF. The phase is one run so that the kinds
# of process overlap (`_all_at_once`), and this is what stops a run that selected ONE of these tests
# from paying for the columns of the others: a column is measured when its test is in the run. A
# name here that no longer resolves would take a column out silently, so both ends of this table are
# driven by `test_every_column_of_the_cell_phase_is_owned_by_a_test_that_asks_for_it`.
CELL_COLUMNS = {
    "line shapes, by the shell": "test_the_shell_writes_where_the_table_of_line_shapes_says",
    "line shapes, by the gate": "test_gate1_refuses_a_line_exactly_where_the_shell_would_write",
    "tilde subjects, by the shell": "test_gate1_places_a_tilde_word_where_the_shell_puts_it",
    "tilde subjects, by the gate": "test_gate1_places_a_tilde_word_where_the_shell_puts_it",
    "leads, by the shell": "test_gate1_answers_for_a_tilde_that_does_not_start_its_word",
    "leads, by the gate": "test_gate1_answers_for_a_tilde_that_does_not_start_its_word",
}


def test_every_column_of_the_cell_phase_is_owned_by_a_test_that_asks_for_it():
    """`CELL_COLUMNS` is read at both ends, because a wrong name in it is a SILENT loss.

    A column whose owner does not resolve is simply not measured, and the test that reads it then
    finds an empty table -- which raises where it looks a subject up, but only if it looks one up.
    So the names are checked against the tests this module defines, and the tests that ask for the
    phase are checked against the names: a test added to the phase without a column of its own, and
    a column left behind by a rename, both fail here rather than one round later.
    """
    defined = {name for name, value in sorted(globals().items())
               if name.startswith("test_") and inspect.isfunction(value)}
    owners = set(CELL_COLUMNS.values())
    assert owners <= defined, (
        "these columns name a test this module does not define, so nothing would measure them: %s"
        % sorted(owners - defined))
    asking = {name for name in defined
              if "cells" in inspect.signature(globals()[name]).parameters}
    assert asking == owners, (
        "these tests ask for the cell phase and own no column in it %s; these columns are owned by "
        "a test that does not ask for the phase %s"
        % (sorted(asking - owners), sorted(owners - asking)))


@pytest.fixture(scope="session")
def cells(request, project, tmp_path_factory):
    """Every cell of the check sets below, measured ONCE and with both kinds of process running.

    THE MEASUREMENT MOVED HERE, NOT THE ASSERTIONS. Each test below still says what its own property
    is and still fails on its own subjects; what it no longer does is wait for the kind of process
    the test before it was starting. The reason is the bound this suite really runs into -- this
    host's process creation, not its cores -- and that the two kinds do not draw on it in the same
    way (`_all_at_once`, and the A/B in docs/reviews/2026-08-29-tsk0090-measurements.md, section 5).

    THE ARBITER IS STILL CHOSEN BY MEASUREMENT (`_can_arbitrate`) and not by name or by place on
    PATH. A host where no candidate qualifies has no shell column at all, and this says so by
    handing back `shell = None`: the tests that need one fail on their own, naming their own check
    set, and the one that asks only a gate is not dragged down with them.

    THE GATE IS ASKED ABOUT A TILDE SUBJECT ONLY WHERE SOMETHING IS ASSERTED ABOUT IT, which is why
    that column is a second pass: which subjects those are is what the shell column decides.

    THE COLUMNS ARE FILTERED AGAINST WHAT THIS RUN SELECTED (`CELL_COLUMNS`), because one shared
    run is otherwise a shared bill: the alternative that was tried first made a `-k` naming one of
    these tests pay for the columns of the other three. Both ends of that are measured in
    docs/reviews/2026-08-29-tsk0090-measurements.md, section 5.
    """
    harness = _reader()
    selected = {item.function.__name__ for item in request.session.items}

    def asked_for(column):
        return CELL_COLUMNS[column] in selected

    base = str(tmp_path_factory.mktemp("cells"))
    outside = os.path.join(base, "elsewhere")
    os.makedirs(outside)
    outside = outside.replace("\\", "/")
    trees = [_sandbox(base, index) for index in range(AT_ONCE[SHELL_LINES])]
    shell = next((candidate for candidate in _posix_shells()
                  if _can_arbitrate(candidate, trees[0], outside)), None)
    leads = _lead_subjects(harness)

    def shape_line(label, here):
        return _line(LINE_SHAPES[label][0], outside, here)

    def tilde_line(subject):
        return ((TILDE_STATES[subject[0]] % {"out": '"%s"' % outside})
                + 'sed -i "s/a/b/" %s' % TILDE_SUBJECTS[subject])

    def lead_line(subject):
        return 'sed -i "s/a/b/" %s' % leads[subject]

    def judged(line):
        return run(project, "gate_lead_write_scope.py", bash_payload(project, line))

    def shape_writes(slot, label):
        return _changes_the_protected_file(shell, trees[slot], shape_line(label, trees[slot]),
                                           outside)

    def tilde_writes(slot, subject):
        return _changes_the_protected_file(shell, trees[slot], tilde_line(subject), outside)

    def lead_writes(slot, subject):
        return _changes_the_protected_file(shell, trees[slot], lead_line(subject), outside)

    claiming = sorted(label for label in LINE_SHAPES if _claimed(label) is not None)
    binding = sorted(label for label in LINE_SHAPES
                     if _claimed(label) is None and not LINE_SHAPES[label][2])
    lead_order = sorted(leads)
    possible = [
        ("line shapes, by the gate", GATE_PROCESSES,
         lambda _slot, label: judged(shape_line(label, project)), sorted(LINE_SHAPES)),
        ("leads, by the gate", GATE_PROCESSES,
         lambda _slot, subject: judged(lead_line(subject)), lead_order),
        ("line shapes, by the shell", SHELL_LINES, shape_writes, claiming + binding),
        ("tilde subjects, by the shell", SHELL_LINES, tilde_writes, sorted(TILDE_SUBJECTS)),
        ("leads, by the shell", SHELL_LINES, lead_writes, lead_order)]
    measured = _all_at_once([batch for batch in possible if asked_for(batch[0])
                             and (batch[1] is not SHELL_LINES or shell is not None)])
    reached = measured.get("tilde subjects, by the shell", {})
    reaching = sorted(subject for subject in reached if reached[subject])
    free = sorted(subject for subject in reached if not subject[1] and not reached[subject])
    tilde_gate = _in_parallel(
        lambda _slot, subject: judged(tilde_line(subject)),
        sorted(set(reaching) | set(free)) if asked_for("tilde subjects, by the gate") else [],
        GATE_PROCESSES)
    return _Cells(shell=shell, outside=outside, trees=trees, leads=leads,
                  shape_line=shape_line, tilde_line=tilde_line, lead_line=lead_line,
                  shape_shell=measured.get("line shapes, by the shell", {}),
                  shape_gate=measured.get("line shapes, by the gate", {}),
                  tilde_shell=reached, tilde_gate=tilde_gate,
                  lead_shell=measured.get("leads, by the shell", {}),
                  lead_gate=measured.get("leads, by the gate", {}))


def test_the_shell_writes_where_the_table_of_line_shapes_says(cells):
    """The first column of `LINE_SHAPES`, taken from a real shell instead of from anybody's memory.

    THE RETURN CODE OF A GATE IS NO EVIDENCE OF WHERE A SHELL STANDS, so the subject here is the
    FILE: each line runs in a sandbox where the protected path holds `a`, and what counts is
    whether it holds `b` afterwards. Without this the other test would be a reader measured against
    a table written by the same hand that wrote the reader -- and since the column is DERIVED from
    the conditions the reader claims (`_crossed`), this is also what keeps the derivation honest.

    WHERE THE TABLE CLAIMS NOTHING, THE MEASUREMENT IS MADE WHERE IT CAN DECIDE SOMETHING, and that
    is this round's correction. What a word standing in FRONT of a command name does with the rest
    of the line is nothing this reader says anything about (`env cd` never reaches the builtin,
    `command cd` does, `! cd` inside a pipeline is a syntax error and runs nothing at all), so the
    table asserts no value there and the INVARIANT is asserted instead: wherever the shell writes
    the protected file, the gate has to refuse. That invariant can only fire where the table lets
    the gate ALLOW -- and for the unclaimed cells whose gate column is a refusal it was a branch
    that was constantly false, and one real shell process per such cell per run for a question
    already answered. Those are left unmeasured here and bound by the other test, which drives every
    one of them through a real gate process against exactly that constant; the moment such a cell
    turns into an allow it lands in `binding` below and is measured again, without anything being
    edited. How many that is stands nowhere: it is `len(LINE_SHAPES) - len(claiming) - len(binding)`
    and a number written beside it is the one that goes stale, which it did.

    THE SHELL IS CHOSEN BY MEASUREMENT (`_can_arbitrate` in `cells`), not by its name or its place
    on PATH. A host where no candidate qualifies cannot answer this question at all, and a test that
    cannot measure its property reports that as a FAILURE: a silent skip is how a table stopped
    being checked for three rounds while it looked green.
    """
    assert cells.shell is not None, (
        "no shell on this host sees both trees this table is about, so the column of `LINE_SHAPES` "
        "was not measured against anything: %s" % (_posix_shells(),))
    claiming = sorted(label for label in LINE_SHAPES if _claimed(label) is not None)
    assert len(claiming) > len(LINE_SHAPES) // 2, (
        "the table stopped claiming what the shell does in most of its shapes (%d of %d), so this "
        "test measures almost nothing" % (len(claiming), len(LINE_SHAPES)))
    binding = sorted(label for label in LINE_SHAPES
                     if _claimed(label) is None and not LINE_SHAPES[label][2])
    answers = cells.shape_shell
    wrong = ["the table says %r %s the protected file, and %s disagrees: %s"
             % (label, "changes" if _claimed(label) else "does not change", cells.shell,
                cells.shape_line(label, cells.trees[0]))
             for label in claiming if answers[label] != _claimed(label)]
    wrong += ["%s writes the protected file in %r, and the table lets the gate allow it: %s"
              % (cells.shell, label, cells.shape_line(label, cells.trees[0]))
              for label in binding if answers[label]]
    assert not wrong, "\n".join(wrong)


def test_gate1_refuses_a_line_exactly_where_the_shell_would_write(project, cells):
    """The gate answers every shape of `LINE_SHAPES` the way the second column derives.

    ONE PROPERTY, BOTH DIRECTIONS: where this reader keeps its position, the relative write behind
    it is refused; where it really follows the shell out, the same write is allowed. The second
    half is the expensive one -- a reader that stopped following directory verbs altogether would
    satisfy the first and refuse this repo's own commands.

    THE INVARIANT THAT BINDS THE TWO COLUMNS IS ASSERTED HERE, and it is the one that says "no
    hole": wherever the first column says the shell writes the protected file, the second has to
    say the gate refuses. A cell where the gate refuses and the shell writes OUTSIDE is friction,
    named as such in `docs/POST_V2_WISHLIST.md` (H29, H30) -- a cell the other way round would be a
    hole, and this makes it impossible to write one into the table by hand.

    The first column is measured against a real shell in
    `test_the_shell_writes_where_the_table_of_line_shapes_says`, so neither test can be satisfied
    by the reader it is about.
    """
    holes = [label for label in LINE_SHAPES if _claimed(label) and not LINE_SHAPES[label][2]]
    assert not holes, (
        "the table itself says the shell writes the protected file here while the gate allows it, "
        "which is a hole written down rather than measured: %s" % sorted(holes))
    answers = cells.shape_gate
    wrong = []
    for label in sorted(LINE_SHAPES):
        line, refuses = cells.shape_line(label, project), LINE_SHAPES[label][2]
        rc, err = answers[label]
        if refuses and rc != 2:
            wrong.append("%s: this reader keeps its position here, the gate answered rc %d: %s"
                         % (label, rc, line))
        if not refuses and rc != 0:
            wrong.append("%s: this reader follows the move here, the gate refused: %s\n%s"
                         % (label, line, err[:200]))
    assert not wrong, "\n".join(wrong)


# WHAT A SHELL CAN HAVE BEHIND IT when it reads a tilde word, and the axis the six prefixes it
# resolves out of its own state differ in: nothing, a directory it came from, a stack. The last two
# leave the line OUTSIDE the tree, so every relative word there is one the gate allows and only the
# prefix can bring the write back in -- which is what makes those cells measure the prefix and not
# the position.
TILDE_STATES = {
    "with nothing behind it": "",
    "after a move out of the tree": 'cd %(out)s ; ',
    "after a push out of the tree": 'pushd %(out)s > /dev/null ; ',
}


def _tilde_prefixes(harness):
    """Every prefix a tilde word could carry -- generated out of the ALPHABET, not out of a manual.

    A LIST OF THE FORMS A SHELL DOCUMENTS WOULD BE A CLAIM THAT IT HAS NO MORE. What a prefix is,
    is a span (`_harness._tilde_prefix`), so its values come from the characters that may stand in
    one: everything printable except what would stop the word being one word -- whitespace, the
    separators that END the prefix, the shell's own syntax, its quotes, its comment character and
    the openers of the substitutions this reader knows. Each character is also crossed with a digit
    behind it, because the numeric forms carry a sign AND a number and one character cannot show
    that.

    WHAT EACH OF THEM REALLY NAMES IS ASKED OF THE ARBITRATING SHELL and never of the library
    expansion under test, which is the whole point of DEC-0020: the delegate answers for all of
    them, and the two answers agree for one.
    """
    alphabet = _word_alphabet(harness)
    return [""] + alphabet + [letter + "0" for letter in alphabet]


def _word_alphabet(harness):
    """Every character that can stand inside ONE word without ending it or the prefix in it.

    Everything printable except what would stop the word being one word -- whitespace, the
    separators that END a tilde prefix, the shell's own syntax, its quotes, its comment character
    and the openers of the substitutions this reader knows.
    """
    reader = shlex.shlex("", punctuation_chars=True)
    apart = (set(string.whitespace) | set(reader.quotes) | set(reader.commenters)
             | set(harness._PATH_SEPARATORS) | harness._SYNTAX_CHARACTERS
             | {character for pair in harness._SUBSTITUTIONS for part in pair
                for character in part})
    alphabet = sorted(set(string.printable) - apart)
    assert len(alphabet) > 1, "no character is left for a tilde prefix to be made of"
    return alphabet


def _tilde_subjects():
    """`{(state, prefix, quoting): the word the line writes into}` -- three axes, fully crossed.

    THE THIRD AXIS IS THIS ROUND'S CORRECTION AND IT WAS A HOLE, not a gap: the check set had no
    value in which the target word carried quoting at all, and the fix of the round before had been
    built on "does this word carry a spliced span" -- a property of the WHOLE word. Where the
    quoting stands is what a shell reads, so where it stands is an axis (`_quotings`).

    A CHECK SET THAT CAN BE CUT SILENTLY IS THE OTHER HALF. Its size and the values of the axis are
    stated by the hole entry that stands on them and compared with the set itself
    (`test_every_tilde_subject_a_closed_hole_names_is_one_the_check_set_carries`), so a shrunk
    alphabet, a dropped state or a dropped quoting is red rather than green-and-smaller.
    """
    harness = _reader()
    out = {}
    for state in sorted(TILDE_STATES):
        for prefix in _tilde_prefixes(harness):
            word = "%s%s/%s" % (harness._TILDE, prefix, RELATIVE_TARGET)
            for label, quoted in sorted(_quotings(harness, word).items()):
                out[(state, prefix, label)] = quoted
    return out


TILDE_SUBJECTS = _tilde_subjects()
# The values of the quoting axis, over every prefix that generates them -- the set the entry that
# leans on this check set has to name, in both directions.
TILDE_QUOTINGS = sorted({label for _state, _prefix, label in TILDE_SUBJECTS})


def test_gate1_places_a_tilde_word_where_the_shell_puts_it(cells):
    """Where this reader DELEGATES the expansion of a tilde, the delegate is measured against bash.

    THE BRANCH WAS RIGHT AND THE VALUE IT WAS FED WAS NOT (DEC-0020). Whether a reading may be
    expanded at all is decided and crossed elsewhere (`MOVES`, H31); WHAT the expansion is came out
    of `os.path.expanduser`, which answers "the home directory of a user". A shell answers "the
    directory this prefix names", and for a prefix that is not empty that is its own working
    directory, the one it came from or an entry of its stack. The delegate does not decline there --
    it hands back a path under the home directory, which nothing protects. Measured 2026-08-07
    through the real gate, one tool call and no preparation: `sed -i "s/a/b/" ~0/<kit file>` was
    rc 0 while bash rewrote the file, and the same shape reached `.claude/settings.json`,
    `.claude/hooks/_harness.py` and canonical state (`docs/POST_V2_WISHLIST.md` H33).

    THE SUBJECT IS `TILDE_SUBJECTS`: every prefix the alphabet can make, from every state a shell
    can carry, and with the quoting standing in every run of the word it can stand in. Both columns
    are measured rather than claimed: a real shell says which of them reach the protected file from
    where the line stands, and a real gate process says what it answers. The invariant is the one
    the cross table asserts as well -- wherever the shell writes, the gate refuses.

    THE QUOTING AXIS IS THIS ROUND'S CORRECTION AND IT WAS A HOLE. `~+/"team-kits"/kernel/state.py`
    was rc 0 through the real gate on 2026-08-07 while bash rewrote the protected file: the fix of
    the round before asked whether the word carried a spliced span ANYWHERE, and a shell suppresses
    an expansion only where the quoting stands.

    THE GATE IS ASKED WHERE SOMETHING IS ASSERTED, AND NOWHERE ELSE, which is what makes a check
    set this size affordable: the shell column decides where the invariant binds (a subject the
    shell does not write is a subject this test asserted nothing about even when the gate was
    asked), and the both-ends set is generated. Before this the gate ran once per subject and the
    answer was dropped for all but a handful. How many subjects that is stands nowhere here -- it is
    `len(TILDE_SUBJECTS)`, and the count that stood in this sentence had gone stale.

    BOTH ENDS, AND THE THIRD ONE IS NEW. Some prefix other than the empty one has to reach the tree,
    or the arbiter measured nothing at all; some word that CARRIES QUOTING has to reach it, or the
    new axis measured nothing; and the empty prefix -- the one reading the delegate and the shell
    agree on -- has to stay ALLOWED wherever the shell does not take it into the tree, in every
    quoting and every state, or this is a gate that refuses every tilde and the friction it costs is
    unbounded.
    """
    harness = _reader()
    assert cells.shell is not None, (
        "no shell on this host sees the trees this test is about, so what a tilde prefix names was "
        "measured against nothing: %s" % (_posix_shells(),))
    line = cells.tilde_line
    subjects = sorted(TILDE_SUBJECTS)
    reached, answers = cells.tilde_shell, cells.tilde_gate
    reaching = sorted(subject for subject in subjects if reached[subject])
    assert [subject for subject in reaching if subject[1]], (
        "no tilde prefix on this host reaches the protected tree from any of %d states, so the "
        "column this test asserts against was empty: %s"
        % (len(TILDE_STATES), sorted(TILDE_STATES)))
    assert [subject for subject in reaching if subject[2] != UNQUOTED], (
        "no word carrying quoting reaches the protected tree from any state, so the axis that "
        "crosses WHERE the quoting stands measured nothing: %s" % TILDE_QUOTINGS)
    free = [subject for subject in subjects if not subject[1] and not reached[subject]]
    holes = []
    for subject in reaching:
        rc, err = answers[subject]
        if rc != 2:
            holes.append("`%s%s` %s, %s: the shell writes the protected file, the gate answered "
                         "rc %d: %s"
                         % (harness._TILDE, subject[1], subject[0], subject[2], rc, line(subject)))
        elif ("%s%s" % (harness._TILDE, subject[1])) not in err:
            holes.append("`%s%s` %s, %s: refused, but the reason never names the word: %s"
                         % (harness._TILDE, subject[1], subject[0], subject[2], err[:200]))
    assert not holes, "\n".join(holes)
    friction = ["%s, %s: %s\n%s" % (subject[0], subject[2], line(subject),
                                    answers[subject][1][:200])
                for subject in free if answers[subject][0] != 0]
    assert not friction, (
        "the one prefix whose expansion this reader and the shell agree on was refused where the "
        "shell leaves it outside the tree, so the delegate is not measured against the shell here "
        "but switched off:\n%s" % "\n".join(friction))


def _tilde_leads(harness):
    """`{lead: does the shell's quote removal take it away}` -- what can stand BEFORE the tilde.

    TWO CLASSES AND THEY ARE GENERATED, because the difference between them is the whole answer: a
    shell decides whether to expand on the word BEFORE quoting is removed, so a lead it removes
    leaves a word that STARTS with the tilde and is still not expanded, while a lead it keeps
    leaves a word in which the tilde is not the first character at all. The removable ones are the
    empty span each quote character of the reader can make; the kept ones are the same alphabet a
    prefix is made of (`_word_alphabet`), so a character this repo's reader stops treating as
    syntax is crossed here on the day it changes.

    THE ESCAPE IS NOT ONE OF THEM, and that is not an omission: `_PATH_SEPARATORS` carries the
    backslash, which is why it cannot open a lead this reader would read as quoting -- the same
    reason `_harness._quoting_in` gives for not asking about it.
    """
    out = {quote + quote: True for quote in sorted(shlex.shlex("", punctuation_chars=True).quotes)}
    out.update({character: False for character in _word_alphabet(harness)})
    assert any(out.values()) and not all(out.values()), (
        "one of the two classes of lead is empty, so this check set measures no difference")
    return out


def _lead_subjects(harness):
    """`{(lead, prefix): the word}` for a tilde that does not start its word.

    THE PREFIX AXIS IS ITS TWO ENDS AND NOT ALL 157: what a lead changes is whether the word is a
    tilde word at all, and the prefix only decides what the answer then IS -- empty, and this
    reader expands into the home directory, which nothing protects; not empty, and it cannot place
    the word at all. Crossing every prefix would multiply a real shell and a real gate process by
    157 for an axis whose two values are already both here.
    """
    ends = ["", next(prefix for prefix in _tilde_prefixes(harness) if prefix)]
    return {(lead, prefix): "%s%s%s/%s" % (lead, harness._TILDE, prefix, RELATIVE_TARGET)
            for lead in sorted(_tilde_leads(harness)) for prefix in ends}


def test_gate1_answers_for_a_tilde_that_does_not_start_its_word(project, cells):
    """The cell three places of the hole list described from a measurement taken under the home
    directory, where an ancestor answered instead of the property.

    `x=~+/team-kits/kernel/state.py` was written down as measured over-refusal. It is not:
    measured 2026-08-08 against a stand-in project OUTSIDE the home directory it is rc 0, and the
    rc 2 of the round before came from the project living under the directory a bare `~` names --
    the word's only path-like substring that this reader can place is that bare `~`, and a
    directory that CONTAINS protected state is refused for the containment (H19). The other half of
    the sentence was wrong too: bash expands `x=~+/y` (`x=/c/.../y`), it does not keep it literal.

    SO THE CLAIM IS A SUBJECT NOW INSTEAD OF A SENTENCE, and the rule it is measured against is one
    expression rather than a list of spellings: after the shell has removed quoting, the word either
    starts with a tilde carrying a non-empty prefix -- and then this reader cannot place it and
    refuses everyone -- or it does not, and then there is nothing here to refuse. Both classes of
    lead are generated (`_tilde_leads`).

    BOTH ENDS. The control is the same line with NO lead: the shell has to write the protected file
    through it and the gate has to refuse it, or the leads below are compared against nothing. And
    the shell column is measured for every lead rather than assumed -- a lead through which bash
    reaches the protected file while the gate allows is a hole and says so.
    """
    harness = _reader()
    assert cells.shell is not None, (
        "no shell on this host sees the trees this test is about: %s" % (_posix_shells(),))
    control = 'sed -i "s/a/b/" %s%s/%s' % (harness._TILDE, "+", RELATIVE_TARGET)
    assert _changes_the_protected_file(cells.shell, cells.trees[0], control), (
        "the same line without a lead does not reach the protected file on this host, so what a "
        "lead in front of it changes was measured against nothing: %s" % control)
    assert run(project, "gate_lead_write_scope.py", bash_payload(project, control))[0] == 2, (
        "the same line without a lead is not refused, so this test measures the lead against an "
        "answer that is already an allow")

    removable = _tilde_leads(harness)
    subjects = cells.leads
    order = sorted(subjects)
    reached, answers = cells.lead_shell, cells.lead_gate
    wrong = []
    for subject in order:
        lead, prefix = subject
        # what a shell hands the program: a removable lead is gone, a kept one is still in front
        word = subjects[subject][len(lead):] if removable[lead] else subjects[subject]
        head = word[len(harness._TILDE):].split("/")[0] if word.startswith(harness._TILDE) else ""
        # A TILDE PREFIX IS NO LONGER THE ONLY WAY A WORD CAN BE UNPLACEABLE, and the second way is
        # asked of the reader that decides it rather than restated here: some of the leads ARE the
        # characters a shell builds a word out of (`*`, `[`, `{`, `?`), so from TSK-0098 on such a
        # lead makes the word unplaceable on its own -- and this test would otherwise report the
        # gate's correct answer as a defect.
        built = (harness._could_name_a_path(word, False)
                 and harness._unresolved_at(word) is not None)
        rc = answers[subject][0]
        if reached[subject] and rc != 2:
            wrong.append("lead %r, prefix %r: bash writes the protected file through it and the "
                         "gate answered rc %d" % (lead, prefix, rc))
        elif (rc == 2) != bool(head or built):
            wrong.append("lead %r, prefix %r: the shell reads the word as %r, so this gate can "
                         "place it %s -- and it answered rc %d"
                         % (lead, prefix, word,
                            "not at all" if head or built else "as any other word", rc))
    assert not wrong, "\n".join(wrong)


def test_the_arbiter_cannot_be_pointed_out_of_its_sandbox_by_the_state_a_tilde_reads(tmp_path):
    """What keeps this suite off the tree it measures is not `cwd` alone, and that cost real files.

    THE SUBJECT IS THE LAUNCHER, not a gate: `_changes_the_protected_file` runs every line of every
    check set here, and the safety of all of them is one keyword argument -- except that a tilde
    prefix does not read `cwd`. It reads the shell's own state, and `PWD` and `OLDPWD` come in
    through the ENVIRONMENT. A suite started in this repo hands the repo to `OLDPWD`, `~-` is a
    subject of `TILDE_SUBJECTS`, and the line writes the repo with a perfectly correct `cwd`.
    Measured 2026-08-07, three times: `team-kits/kernel/state.py` came out with the first `a` of
    each of its 928 lines replaced by `b`. Twice it was put down to a measuring script standing in
    the wrong directory; the third time the session guard above caught it mid-run and the mechanism
    was isolated -- with `cwd` a sandbox and `OLDPWD` another tree, `printf "%s\\n" ~-` prints the
    other tree.

    SO THE MEASUREMENT IS MADE WITH THAT STATE POINTED SOMEWHERE ELSE ON PURPOSE: every prefix the
    alphabet can make is run at a tree the sandbox has nothing to do with, and that tree has to be
    untouched afterwards. BOTH ENDS: some prefix has to reach the sandbox's OWN protected file, or
    the launcher ran nothing and the first half is empty.
    """
    harness = _reader()
    outside = str(tmp_path / "elsewhere")
    os.makedirs(outside)
    trees = [_sandbox(str(tmp_path), index) for index in range(AT_ONCE[SHELL_LINES])]
    shell = next((candidate for candidate in _posix_shells()
                  if _can_arbitrate(candidate, trees[0], outside.replace("\\", "/"))), None)
    assert shell is not None, (
        "no shell on this host can arbitrate, so the launcher was measured against nothing: %s"
        % (_posix_shells(),))
    other = str(tmp_path / "a-tree-this-suite-must-not-reach")
    subject = os.path.join(other, *RELATIVE_TARGET.split("/"))
    os.makedirs(os.path.dirname(subject))
    with open(subject, "w", encoding="utf-8") as handle:
        handle.write("a")
    saved = {name: os.environ.get(name) for name in ("PWD", "OLDPWD")}
    os.environ["PWD"] = os.environ["OLDPWD"] = other.replace("\\", "/")
    try:
        def measure(index, prefix):
            return _changes_the_protected_file(
                shell, trees[index],
                'sed -i "s/a/b/" %s%s/%s' % (harness._TILDE, prefix, RELATIVE_TARGET))

        reached = _in_parallel(measure, _tilde_prefixes(harness), SHELL_LINES)
    finally:
        for name, value in saved.items():
            os.environ.pop(name, None) if value is None else os.environ.__setitem__(name, value)
    with open(subject, encoding="utf-8") as handle:
        held = handle.read()
    assert held == "a", (
        "a line of this check set reached %s, which is not the sandbox it was given: the shell "
        "resolves a tilde prefix out of state the launcher hands it, and `cwd` does not cover that"
        % other)
    assert any(reached.values()), (
        "no tilde prefix reached the sandbox's own protected file, so the launcher was not running "
        "these lines at all and the assertion above holds for the wrong reason")


def test_gate1_does_not_see_a_program_a_here_document_hands_a_shell(project, tmp_path):
    """WHERE the reading of a command line ends, measured -- the same kind of boundary as H22.

    Both gates read the line only after the KITS' prose removal has run over it
    (`_harness._prose_removed`), and that removal deletes every here-document BODY: a body is where
    a commit message is written, and reading inside one would be a second answer to "what is prose"
    (H15). The consequence is not about messages at all -- a here-document is also how a shell is
    handed a PROGRAM, and that program is then invisible to both gates.

    MEASURED IN BOTH DIRECTIONS IN ONE RUN, one tool call, no preparation and no commit: the same
    payload written as an argument is refused, and written into a here-document it is allowed while
    a real bash really rewrites the protected file. `docs/POST_V2_WISHLIST.md` H38 carries the
    chain and the judgement.

    THIS TEST GOES RED WHEN THE HOLE CLOSES, which is what it is for: the repair site is in the kit
    (`gate_write_scope._HEREDOC_RX`), outside the scope of the item that measured it, so the entry
    stands open -- and the day the kit reads inside a body, H38 and this test have to be corrected
    together rather than one of them left claiming an edge that is no longer there.
    """
    sandbox = _sandbox(str(tmp_path), 0)
    shell = next((candidate for candidate in _posix_shells()
                  if _can_arbitrate(candidate, sandbox)), None)
    assert shell is not None, (
        "no shell on this host sees this sandbox and reaches the protected file in it with %r, so "
        "what the here-document does was measured against nothing" % RELATIVE_WRITE)
    seen = "bash -c '%s'" % RELATIVE_WRITE
    assert run(project, "gate_lead_write_scope.py", bash_payload(project, seen))[0] == 2, (
        "the same program passed as an ARGUMENT is allowed too, so this test is not measuring what "
        "the here-document costs but a gate that sees nothing at all")
    unseen = "bash <<EOF\n%s\nEOF" % RELATIVE_WRITE
    assert run(project, "gate_lead_write_scope.py", bash_payload(project, unseen))[0] == 0, (
        "this line is refused now, so the boundary moved: H38 describes an edge that is no longer "
        "there and has to be corrected rather than left standing")
    assert _changes_the_protected_file(shell, sandbox, unseen), (
        "the line this gate allows does not move the tree here, so what it allows was not measured")


def test_every_span_the_kits_prose_removal_takes_out_is_named_where_it_is_documented():
    """The blind spot of `command_line` is stated where it is read, and the statement is generated.

    A DOCSTRING THAT NAMES ONE OF TWO IS THE CLAIM THIS EXISTS FOR. `command_line` named
    `_MESSAGE_ARG_RX` as what its reading does not reach and said nothing about the here-document
    body, and that second span carries a chain that runs in one tool call (H38) -- so the paragraph
    that was supposed to be the warning was itself the reassurance.

    SO THE NAMES COME OUT OF THE SYNTAX TREE OF THE FUNCTION THAT RUNS. Both directions: a span the
    removal applies and the docstring does not name is a blind spot nobody was told about, and a
    span the docstring names and the removal no longer applies is a warning about something that is
    not there any more.
    """
    harness = _reader()
    applied = {node.attr
               for node in ast.walk(ast.parse(textwrap.dedent(
                   inspect.getsource(harness._prose_removed))))
               if isinstance(node, ast.Attribute) and node.attr.endswith("_RX")}
    assert applied, (
        "`_prose_removed` applies no named expression at all any more, so this test would pass "
        "whatever the docstring says")
    named = {span.rsplit(".", 1)[-1]
             for span in re.findall(r"`([^`]+)`", harness.command_line.__doc__ or "")
             if span.rsplit(".", 1)[-1].endswith("_RX")}
    assert named == applied, (
        "`command_line` names %s as what its reading does not reach; the prose removal it goes "
        "through takes out %s" % (sorted(named), sorted(applied)))


# -- the apparatus a round measures WITH, which is a subject and not a promise ------------------


def _decoy(base, name):
    """A tree the measurement must not reach, holding the file every payload here names."""
    subject = os.path.join(base, name, *RELATIVE_TARGET.split("/"))
    os.makedirs(os.path.dirname(subject), exist_ok=True)
    with open(subject, "w", encoding="utf-8") as handle:
        handle.write("a")
    return os.path.join(base, name), subject


def _directory_words(harness, asked_for):
    """Every line that writes `RELATIVE_TARGET` under a directory the LINE ITSELF never names.

    THE SHAPES ARE THE WAYS A SHELL CAN GET A DIRECTORY WITHOUT BEING TOLD ONE, and there are two:
    a tilde prefix, which it resolves out of its own state -- every prefix the alphabet can make,
    GENERATED (`_tilde_prefixes`) rather than listed -- and a bare relative word, which it looks up
    along a search list once it cannot find it below `cwd`. `asked_for` is what a line of the second
    shape asks for. The `cd` stands in a subshell so no line depends on the order of the ones before
    it, which is what lets the whole set run as one script instead of one process per line.
    """
    for prefix in _tilde_prefixes(harness):
        yield 'sed -i "s/a/b/" %s%s/%s' % (harness._TILDE, prefix, RELATIVE_TARGET)
    yield "( cd %s && %s )" % (asked_for, RELATIVE_WRITE)


def _pointed_at(name, tree):
    """The value that makes the environment name `name` reach `tree` for a child shell.

    A NAME THAT ENDS IN `PATH` HOLDS A SEARCH LIST AND NOT A DIRECTORY: what a shell joins its word
    onto is an ENTRY, so the value that reaches `tree` is its parent -- and it is spelled the way a
    list is read on this host, which is the spelling a colon does not split (`C:/x` is read as `C`
    and then `/x`, measured 2026-08-08, and a `cd` through it finds nothing).
    """
    return os.path.dirname(tree) if name.endswith("PATH") else _sandbox_module().posix(tree)


def test_the_arbiter_is_a_shell_that_reads_back_what_this_process_writes(tmp_path):
    """Every measurement here that runs a real line stands on the shell `_sees_this_filesystem` picks.

    THE PREDICATE IS DRIVEN AT BOTH ENDS, because the way the selection before it failed was silent:
    it asked whether a candidate RUNS, and the WSL launcher runs everything while its absolute words
    name another tree (BUG-0051). So the probe is shown to answer on the CONTENT of a file this
    process wrote -- a shell that hands back something else and a read that finds nothing at all are
    both refused. A predicate that went back to reading an exit code fails HERE, and not in the
    control of some other test that then has nothing left to compare against.

    AND THE OTHER END IS THIS HOST: no candidate qualifying is not a skip. A host on which this
    suite cannot reach the files it writes measures nothing at all, and says so here.
    """
    candidates = _posix_shells()
    assert candidates, "this host carries no POSIX shell at all, so nothing here can be measured"
    shell = next((candidate for candidate in candidates
                  if _sees_this_filesystem(candidate, str(tmp_path))), None)
    assert shell is not None, (
        "no shell of %s reads back a file written under %s, so every measurement in this file that "
        "runs a line has nothing to run it with" % (candidates, tmp_path))
    nonce = os.urandom(16).hex()
    path = os.path.join(str(tmp_path), "written-by-this-process")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(nonce)
    spelled = _sandbox_module().posix(path)
    assert _reads_back(shell, spelled, nonce), (
        "%s does not hand back what stands in %s, so the selection above qualified it for some "
        "other reason than the one it is written for" % (shell, spelled))
    assert not _reads_back(shell, spelled, os.urandom(16).hex()), (
        "the probe accepts a nonce the file does not hold, so it is not reading the file at all")
    os.remove(path)
    assert not _reads_back(shell, spelled, nonce), (
        "the probe accepts a path that holds nothing, which is what an exit code answers here -- "
        "and that is what let a shell on another filesystem arbitrate")


def _runs_a_line(shell):
    """Does this candidate run a line at all -- the question the selection BEFORE BUG-0051 asked."""
    try:
        return subprocess.run([shell, "-c", ":"], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                              timeout=120).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def test_the_session_guards_watch_list_is_built_without_a_shell(tmp_path, monkeypatch):
    """BUG-0137 / H45 (a): the session guard runs no line of its own, so its watch list must not
    need a shell -- it used to, and on a host without one the whole suite fell over, registration
    checks included.

    THE HOST WITHOUT A SEEING SHELL IS MADE HERE rather than waited for: the candidate list the
    guard would ask is emptied, which is what the verifier of TSK-0063 produced with a PATH without
    Git (rc 1, four ERRORs -- the four checks that read `.claude/settings.json` and nothing else).

    BOTH FILES, because the list is what the guard compares against this repo: the free one and the
    protected one both have to stand in it, so a preparation that stops making either is red here
    instead of silently watching a shorter tree.
    """
    monkeypatch.setattr(sys.modules[__name__], "_posix_shells", lambda: [])
    probe, watched = _a_sandbox_as_a_line_leaves_it(str(tmp_path))
    assert RELATIVE_TARGET in watched, (
        "the protected file is not in the watch list built under %s: %s -- the guard would not "
        "notice a run that rewrote it here" % (probe, watched))
    assert [entry for entry in watched if entry != RELATIVE_TARGET], (
        "the watch list holds nothing but the protected file, so the free file a shape writes "
        "first is gone and the shapes that need it measure nothing: %s" % watched)


def test_the_arbiter_refuses_a_shell_that_runs_every_line_on_another_filesystem(tmp_path):
    """BUG-0137 / H45 (b): `_can_arbitrate` itself had no cover that could go red -- the verifier of
    TSK-0063 put the previous form back in a clone and the eight tests around it stayed green.

    WHAT THE PREVIOUS FORM MISSED, and it is the case this host really carries: a launcher that runs
    every line, translates a RELATIVE word onto this tree through its `cwd` and resolves an
    ABSOLUTELY spelled one into a filesystem of its own. Such a shell passes "it runs a line", it
    passes a `cd` probe, and it performs the relative write -- so a selection built out of those
    calls it an arbiter, and every check set whose reach is spelled absolutely then runs, reports
    nothing wrong and never arrives (BUG-0051).

    THE SUBJECT IS A REAL SHELL OF THIS HOST AND NOT A STAND-IN: one is taken from `_posix_shells`
    that runs a line and does NOT read this filesystem back. A host without one cannot show the
    property and is skipped with that sentence rather than passing quietly.

    BOTH ENDS: the shell this suite really arbitrates with has to come back True from the same
    predicate, so a `_can_arbitrate` that turned into one refusing everything fails here too.
    """
    sandbox = _sandbox(str(tmp_path), 0)
    candidates = _posix_shells()
    assert candidates, "this host carries no POSIX shell at all, so nothing here can be measured"
    elsewhere = [candidate for candidate in candidates
                 if _runs_a_line(candidate) and not _sees_this_filesystem(candidate, sandbox)]
    seeing = next((candidate for candidate in candidates
                   if _can_arbitrate(candidate, sandbox)), None)
    assert seeing is not None, (
        "no shell of %s arbitrates over %s, so the predicate refuses everything and every "
        "measurement standing on it is vacuous" % (candidates, sandbox))
    if not elsewhere:
        pytest.skip(
            "not measured here: no shell of %s runs a line while resolving %s into another "
            "filesystem, so the case BUG-0051 was measured on is absent from this host"
            % (candidates, sandbox))
    for shell in elsewhere:
        assert not _can_arbitrate(shell, sandbox), (
            "%s runs every line and does not read %s back, yet it is accepted as this suite's "
            "arbiter -- which is the selection that cost BUG-0051 its control" % (shell, sandbox))


# WHAT A SHELL ON THIS HOST WAS MEASURED TO READ A DIRECTORY BACK OUT OF -- a fact about shells,
# and it is stated HERE rather than taken from `_sandbox` on purpose. A measurement whose hostile
# environment comes out of the module under test cannot fail when that module DROPS a name: it then
# stops pointing that name at the decoy as well, and the attack disappears together with the
# defence. Measured 2026-08-08 in a clone: with the hostile set derived from
# `POINTED_AT_THE_SANDBOX`, deleting `HOME`, `OLDPWD` or `CDPATH` from that tuple left this test
# GREEN. The test below ties this tuple to the running shell in both directions, so it cannot rot
# into a second opinion.
CARRY_A_TREE = ("OLDPWD", "HOME", "CDPATH")


def test_the_measurement_sandbox_leaves_a_child_shell_no_directory_word_that_names_another_tree(
        tmp_path):
    """`_sandbox.pin` is what stands between a payload and this repo, so it is measured, not trusted.

    THE SCRIPTS BESIDE THIS FILE ARE NOT UNDER THE SESSION GUARD. `the_repo_is_not_a_sandbox`
    watches runs of this file; the ad-hoc apparatus a round writes -- a probe, a single try out of
    a shell -- is a Python process of its own, and the hole list says so (H37). What takes the
    place of that guard is that module, and every version of it so far was wrong about WHICH names
    carry a directory: the first pinned `cwd` alone and left `OLDPWD` on the real repo, the second
    added `PWD` and `DIRSTACK` and left `HOME` and `CDPATH` (measured 2026-08-08 against a decoy
    tree: `~/...` wrote the decoy, and so did `cd <decoy> && sed -i ...` through `CDPATH`).

    SO WHAT IS ASKED HERE IS A PROPERTY AND NOT THREE NAMES: does ANY line that names a directory
    without spelling one reach a tree the sandbox has nothing to do with? Every tilde prefix the
    alphabet can make, and the relative word a search list answers.

    THE CONTROL COMES FIRST AND IT REALLY DAMAGES THE DECOY -- with the state INHERITED, which is
    what a process started in the measured tree hands on. Then `pin()`, and the decoy has to be
    untouched while the sandbox's OWN file is not.

    AND THE ENUMERATION IN THAT MODULE IS TRIPPED AT BOTH ENDS, because a list of names is a claim
    that the world has no more of them: each name is put back on its own and measured, so a name
    that carries a tree while the module calls it blind fails here, and so does a name the module
    handles that carries nothing -- which is how `DIRSTACK` and `PWD` came to be marked as carried
    without a chain instead of described as protection. The hostile state itself comes from
    `CARRY_A_TREE` and not from the module, for the reason written there.

    AND THE ARBITER IS MEASURED INSTEAD OF TAKEN FROM THE FRONT OF PATH (BUG-0051). This test used
    to take the first candidate that ran `true`, which on this host is a shell whose absolute words
    land in another filesystem: every line of the check set ran, none of them damaged anything, and
    the control below asserted False. `_sees_this_filesystem` is the property it is chosen by.
    """
    harness = _reader()
    module = _sandbox_module()
    shell = next((candidate for candidate in _posix_shells()
                  if _sees_this_filesystem(candidate, str(tmp_path))), None)
    assert shell is not None, (
        "no shell on this host reads back a file this process writes under %s, so no line of this "
        "check set could reach a decoy of it and nothing below would be measured: %s"
        % (tmp_path, _posix_shells()))
    controlled = set(module.POINTED_AT_THE_SANDBOX) | set(module.DROPPED)
    hostile = controlled | set(CARRY_A_TREE)
    # short subject names on purpose: each of them becomes a directory below `tmp_path`, and this
    # host stops a path at 260 characters
    INHERITED, PINNED = "inherited", "pinned"
    subjects = [INHERITED, PINNED] + sorted(hostile)
    trees = {}
    for subject in subjects:
        work = str(tmp_path / ("box-%s" % subject) / "run")
        os.makedirs(work)
        trees[subject] = (work, ) + _decoy(str(tmp_path), "not-mine-%s" % subject)

    def measure(_slot, subject):
        work, decoy, victim = trees[subject]
        _decoy(work, "")
        script = "\n".join(_directory_words(harness, os.path.basename(decoy)))
        subprocess.run([shell, "-c", script], cwd=work, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600,
                       env=environments[subject])
        with open(victim, encoding="utf-8") as handle:
            reached = handle.read() != "a"
        with open(os.path.join(work, *RELATIVE_TARGET.split("/")), encoding="utf-8") as handle:
            return reached, handle.read() != "a"

    def inherits(subject):
        _work, decoy, _victim = trees[subject]
        return dict(os.environ, **{name: _pointed_at(name, decoy) for name in hostile})

    here, saved = os.getcwd(), dict(os.environ)
    try:
        os.environ.update(inherits(PINNED))
        work = module.pin(os.path.dirname(trees[PINNED][0]), "run")
        environments = {PINNED: dict(os.environ)}
    finally:
        os.chdir(here)
        os.environ.clear()
        os.environ.update(saved)
    assert os.path.realpath(work) == os.path.realpath(trees[PINNED][0]), (
        "`pin()` stood in %s and not in the tree measured here" % work)
    environments[INHERITED] = inherits(INHERITED)
    for name in hostile:
        environments[name] = dict(module.sandbox_environment(trees[name][0]),
                                  **{name: _pointed_at(name, trees[name][1])})
    answers = _in_parallel(measure, subjects, SHELL_LINES)

    assert answers[INHERITED][0], (
        "with the directory state inherited no line reached %s, so this host cannot show the "
        "accident this module exists for and everything below says nothing" % trees[INHERITED][1])
    assert not answers[PINNED][0], (
        "a line run after `pin()` reached %s, which is not the sandbox it was pinned to"
        % trees[PINNED][1])
    assert answers[PINNED][1], (
        "no line reached the sandbox's OWN file either, so nothing ran and the decoy is untouched "
        "for the wrong reason")
    carries = {name for name in hostile if answers[name][0]}
    assert carries == set(CARRY_A_TREE), (
        "the names this host was measured to resolve a directory out of are %s; put back one at a "
        "time, the ones that really reached their decoy are %s. Either a shell here changed or the "
        "hostile state above stopped being hostile -- and the halves before this one are only worth "
        "what it is" % (sorted(CARRY_A_TREE), sorted(carries)))
    assert carries <= controlled, (
        "%s carry a tree on this host and `_sandbox` does not touch them, so `pin()` hands a child "
        "shell a word that names another tree" % sorted(carries - controlled))
    assert controlled - carries == set(module.NOT_MEASURED_TO_CARRY_A_TREE), (
        "`_sandbox` says %s carry no tree; measured on this host the ones that carry none are %s. "
        "A name on the left that is missing on the right is a chain nobody was told about; one on "
        "the right that is missing on the left is handled for nothing and says so"
        % (sorted(module.NOT_MEASURED_TO_CARRY_A_TREE), sorted(controlled - carries)))


def test_the_measurement_watch_list_is_the_area_the_gate_protects(project):
    """What a measurement watches is derived from the gate's authority, not from its own lines.

    THE VERSION THIS REPLACED SCANNED THE PAYLOAD LINES for path-like spans, and a scan answers
    only for the spellings it can read: measured 2026-08-08 on the previous round's own lines, it
    found one of the four protected files those lines named -- the quoting inside a word broke the
    span and a join threw the repo root away -- so `.claude/settings.json`, `_harness.py` and a
    canonical state file were never hashed at all while the run reported everything unchanged.

    SO THE LIST IS THE PROTECTED SET, and the comparison here is a set EQUALITY against an
    independent derivation: every file of the project, walked without asking where the areas are,
    judged by `ProtectedArea.verdict`. Both directions fall out of it -- a file the areas do not
    reach is missing from the list, and a file the verdict allows (`staging/**`) is one the list may
    not carry.
    """
    module = _sandbox_module()
    harness = _reader()
    area = harness.ProtectedArea(project)
    walked = set()
    for here, dirs, names in os.walk(project):
        dirs[:] = [name for name in dirs if name != ".git"]
        walked.update(os.path.abspath(os.path.join(here, name)) for name in names)
    expected = {path for path in walked if area.verdict(path)[0] is not None}
    listed = set(module.protected_files(project))
    assert listed == expected, (
        "watched but not protected: %s -- protected but not watched: %s"
        % (sorted(listed - expected)[:5], sorted(expected - listed)[:5]))
    assert expected, "this project protects no file at all, so the comparison above is empty"
    allowed = walked - expected
    assert allowed, (
        "every file of the stand-in project is protected, so a list that simply returned all of "
        "them would pass this test")


def test_an_index_restore_refuses_a_target_outside_the_pinned_sandbox(tmp_path):
    """The one write-back path an apparatus for measuring writes had, and it checked the process.

    `restore_from_index` takes its destination as an ARGUMENT, so standing in the sandbox says
    nothing about where it writes -- the version it replaced checked only that the process was
    pinned, which makes a mistyped first argument a write into whatever it names, this repo's
    working tree included. That is the same class as the accident the whole module exists for.

    BOTH ENDS: a target under the pinned sandbox really receives the index bytes, and one outside it
    is refused without the file being touched.
    """
    module = _sandbox_module()
    sandbox = str(tmp_path / "sandbox")
    os.makedirs(sandbox)
    elsewhere, subject = _decoy(str(tmp_path), "not-the-sandbox")
    # a repository of its own rather than this one: what is measured is where the bytes GO
    source, _ = _decoy(str(tmp_path), "source")
    for arguments in (["init", "-q", "."], ["config", "user.email", "t@t.t"],
                      ["config", "user.name", "t"], ["add", "-A"]):
        subprocess.run(["git"] + arguments, cwd=source, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    here, saved = os.getcwd(), dict(os.environ)
    try:
        module.pin(sandbox)
        inside = module.restore_from_index(os.path.join(sandbox, "clone"), RELATIVE_TARGET,
                                           root=source)
        with open(inside, "rb") as handle:
            restored = handle.read()
        with pytest.raises(SystemExit) as refusal:
            module.restore_from_index(elsewhere, RELATIVE_TARGET, root=source)
    finally:
        # `pin()` writes the directory state into `os.environ`, which every later test inherits
        os.chdir(here)
        os.environ.clear()
        os.environ.update(saved)
    assert restored, "the index version of %s came back empty, so the half above wrote nothing" % (
        RELATIVE_TARGET,)
    assert "sandbox" in str(refusal.value), (
        "the refusal does not say what was wrong with the target: %s" % refusal.value)
    with open(subject, encoding="utf-8") as handle:
        assert handle.read() == "a", (
            "the refused restore wrote %s anyway, so the check is on the message and not on the "
            "write" % subject)


def test_the_words_this_reader_reads_are_the_kits_own_tokens():
    """`_harness.tokenise` adds a fact to the kits' tokens; it does not become a second tokeniser.

    A SECOND READER OF THE SAME TEXT IS THE DRIFT THIS REPO KEEPS PAYING FOR, and `tokenise` is one
    line away from being one: the kits' `_tokenise` is `_compat.shell_words` with that gate's lexer,
    and this spells the same composition in order to see the tokens BEFORE the quoting was taken out
    of them (`TYPED_READING`). So both are handed every line of both check sets and have to answer
    with the same words, the same splice flags and the same readings.

    THE OTHER END: a typed reading that never differs from the resolved text would make the whole
    round's distinction unmeasurable, so some word of these lines has to carry one that does. And
    the kits' tokeniser must no longer be reached directly from `_harness` -- read off that module's
    SYNTAX TREE, because a word arriving without a typed reading falls back to the pre-H31 answer
    for it, which is a hole rather than a defect anybody would see.
    """
    harness = _reader()
    harness._add_kit_paths(ROOT)
    module, compat = harness._from_kit("gate_write_scope"), harness._from_kit("_compat")
    lines = [_line(LINE_SHAPES[label][0], "/out", "/here") for label in sorted(LINE_SHAPES)]
    lines += ['sed -i "s/a/b/" %s' % word for word in sorted(set(TILDE_SUBJECTS.values()))]
    wrong, differing = [], 0
    for line in lines:
        mine, theirs = harness.tokenise(module, compat, line), module._tokenise(line)
        if [str(word) for word in mine] != [str(word) for word in theirs]:
            wrong.append("different words for %r" % line)
        elif ([(word.spliced, word.readings) for word in mine]
              != [(word.spliced, word.readings) for word in theirs]):
            wrong.append("same words, different facts for %r" % line)
        for word in mine:
            typed = getattr(word, harness.TYPED_READING, None)
            if typed is None:
                wrong.append("a word without a typed reading in %r: %r" % (line, str(word)))
            elif typed != str(word):
                differing += 1
    assert not wrong, "\n".join(sorted(set(wrong))[:20])
    assert differing, (
        "no word of either check set has a typed reading that differs from the text a program "
        "receives, so the distinction this round is built on was measured against nothing")
    with open(os.path.join(HOOKS, "_harness.py"), encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    direct = [node for node in ast.walk(tree)
              if isinstance(node, ast.Attribute) and node.attr == "_tokenise"]
    assert not direct, (
        "`_harness` still reaches the kits' tokeniser directly, so words can arrive at `readings` "
        "without a typed reading -- and those fall back to the answer H31 closed")


def _a_process_can_enter(path):
    """Can a process make this its working directory? Asked by having one TRY."""
    return subprocess.run(
        [sys.executable, "-B", "-c", "import os, sys; os.chdir(sys.argv[1])", path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def _a_process_can_list(path):
    """Can a process read this directory's entries? Asked by having one TRY."""
    return subprocess.run(
        [sys.executable, "-B", "-c", "import os, sys; os.listdir(sys.argv[1])", path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


# The two rights that come apart here. ENTERING and LISTING a directory are separate rights on
# both operating systems, and this test exists because a reader that asked for the wrong one
# answered wrong in BOTH directions -- so the pair is the subject, not a case. Each carries how the
# two systems spell it: the Windows right to deny, and the mode a POSIX directory keeps when that
# right is gone.
ENTRY, LISTING = "entry", "listing"
RIGHTS = {ENTRY: ("(X)", 0o400), LISTING: ("(RD)", 0o100)}


def _right(path, which, revoke):
    """Take `which` right on `path` away, or give it back. Reports nothing -- see the caller.

    Two spellings because the two operating systems have two, and NEITHER is believed: what the
    test acts on is `_a_process_can_enter` / `_a_process_can_list`, which try the thing rather than
    read a permission.

    EXACTLY THE ONE RIGHT IT IS ASKED FOR, and no more. Denying full control also denies the right
    to hand the rights back: measured 2026-08-05, a directory denied `(F)` could no longer be read,
    reset, or owned by the account that had just created it -- `icacls`, `takeown` and `Set-Acl`
    all answered "access denied". `/deny` takes the rights with the principal, `/remove:d` takes
    the principal alone; a restore spelled like the revocation removes nothing.
    """
    windows, mode = RIGHTS[which]
    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if os.name == "nt" and user:
        subprocess.run(["icacls", path] + (["/deny", "%s:%s" % (user, windows)] if revoke
                                           else ["/remove:d", user]),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        os.chmod(path, mode if revoke else 0o700)
    except OSError:
        pass


def test_gate1_follows_a_move_a_process_can_make_and_no_other(project, tmp_path):
    """ENTERING a directory is what a shell does to land in it, and it is a right of its own.

    BOTH DIRECTIONS OF ONE SPLIT, because every question that is not the entry itself gets one of
    them wrong. Measured 2026-08-05 on this host, one right revoked at a time:

      * traverse revoked (`icacls /deny <user>:(X)`) -- `os.scandir` succeeds, `os.path.isdir`,
        `os.stat`, `os.stat` of its `.` and `os.access(X_OK)` all say yes, while `os.chdir` and a
        real bash both answer `Permission denied`. The shell stays in the tree and the relative
        write behind it rewrites the protected file: the gate, asking whether the directory OPENS,
        followed the move and answered rc 0. A hole in one tool call;
      * list revoked (`(RD)`) -- `os.scandir` raises while `os.chdir` and bash go in. The gate
        stayed where it was and refused a write that lands outside the tree. Friction.

    So the pair is the subject here and neither half alone would do: a reader that refuses every
    move passes the first assertion, and one that follows every move passes the second.
    """
    cannot_enter = str(tmp_path / "no-entry")
    cannot_list = str(tmp_path / "no-listing")
    reachable = str(tmp_path / "reachable")
    for path in (cannot_enter, cannot_list, reachable):
        os.makedirs(path)
    _right(cannot_enter, ENTRY, revoke=True)
    _right(cannot_list, LISTING, revoke=True)
    try:
        assert not _a_process_can_enter(cannot_enter), (
            "this host would not take the entry right away from %s, so the half of this test that "
            "measures a hole measured nothing" % cannot_enter)
        assert _a_process_can_enter(cannot_list) and not _a_process_can_list(cannot_list), (
            "this host would not separate listing from entering on %s, so the half of this test "
            "that measures the friction measured nothing" % cannot_list)

        def line(directory):
            return 'cd "%s" ; %s' % (directory.replace("\\", "/"), RELATIVE_WRITE)

        rc, err = run(project, "gate_lead_write_scope.py",
                      bash_payload(project, line(cannot_enter)))
        assert rc == 2, "the gate followed a move into a directory no process can enter"
        rc, err = run(project, "gate_lead_write_scope.py",
                      bash_payload(project, line(cannot_list)))
        assert rc == 0, (
            "the gate did not follow a move a process makes, because the directory cannot be "
            "listed: %s" % err[:300])
        rc, err = run(project, "gate_lead_write_scope.py", bash_payload(project, line(reachable)))
        assert rc == 0, "the gate stopped following moves into ordinary directories: %s" % err[:300]
    finally:
        _right(cannot_enter, ENTRY, revoke=False)
        _right(cannot_list, LISTING, revoke=False)
    for path in (cannot_enter, cannot_list):
        assert _a_process_can_enter(path) and _a_process_can_list(path), (
            "this test took a right away that it could not give back, and %s stays behind: every "
            "later run of this suite trips over it" % path)


def test_the_words_the_kits_reader_steps_over_are_all_crossed():
    """DEC-0016: the enumeration the reader decides from GENERATES the values of its axis.

    The kits' `_stage_verb` walks past a list of words to find the verb, and what it hands back is
    what `_harness` then asks for a directory role. The last round crossed THREE lowercase verbs
    against nineteen positions and never touched that list at all -- two of the two holes it left
    were words out of it (`env cd`, `nice cd`, `sudo cd`: measured rc 0 while a real bash stayed in
    the tree and the relative write behind them rewrote the protected file).

    THE BRANCHES ARE ASKED, NOT THE GENERATOR, and that is DEC-0018 turned into a tripwire: a
    generator that reads the reader's word LIST covers the branch that steps over a word list and
    nothing else, and the branch that steps over an ASSIGNMENT (`"=" in low ...`) then has no cell
    while `_is_the_command_name` decides about it every day. So this walks the branches itself,
    proves a word against the running function and asks whether THAT word has a shape -- which
    stays red if the generator narrows back to tuples.
    """
    harness = _reader()
    words = _skipped_words(harness)
    assert words, "the kits' reader steps over no word at all -- then this axis measures nothing"
    generated = set(_prefix_shapes(words)) | set(_verb_shapes(harness))
    crossed = {label.split(" -- ")[0] for label in LINE_SHAPES}
    assert generated <= crossed, (
        "these values of the two generated axes have no shape in the table: %s"
        % sorted(generated - crossed))
    for branch, proven in _skip_branches(_kits_reader(harness)):
        if not proven or all(set(word) <= harness._SYNTAX_CHARACTERS for word in proven):
            continue  # syntax is what may stand in front of a command name (`_is_the_command_name`)
        assert set(_prefix_shapes(proven)) & crossed, (
            "the kits' `_stage_verb` steps over a word this branch accepts (%s: %s) and no shape "
            "in the table stands behind one" % (branch, proven))
    # The other direction needs no assertion and could not fail: `_crossed` builds its cells out of
    # THESE functions, so a value the enumerations stop producing stops being a cell in the same
    # step. What can go wrong is only the direction above -- a table built once and left behind.
    both = [label for label in LINE_SHAPES if " -- " in label]
    directions = {label.rsplit(" -- ", 1)[1] for label in both}
    assert len(directions) > 1, (
        "the table crosses the moves in one direction only (%s), so the base an uncomputable move "
        "is judged from is a claim again instead of an axis -- which is what DEC-0018 is about"
        % sorted(directions))
    deciding = {label.rsplit(" -- ", 1)[0] for label in both
                if LINE_SHAPES[label][2] != LINE_SHAPES[
                    "%s -- %s" % (label.rsplit(" -- ", 1)[0],
                                  sorted(directions - {label.rsplit(" -- ", 1)[1]})[0])][2]}
    assert deciding, (
        "no shape of the table answers differently in the two directions, so crossing them "
        "decides nothing and one of the two columns is not derived from the base at all")


def test_the_shells_this_reader_knows_are_the_ones_the_registration_names():
    """DEC-0016, the other enumeration: which shell a line is for decides which words are verbs.

    `_harness.SHELLS` says what `cd`, `pushd`, `popd` and `set-location` do and whether command
    names are compared case-insensitively; a tool it has no entry for moves the base at all. That is
    the fail-closed direction and it is silent, so the tripwire is here: the shell tools the
    REGISTRATION names are the ones that reach these gates, and every one of them needs an entry.

    Read off the registration rather than typed, which is the same rule the rest of this file keeps:
    what binds at session start is the file, not anybody's memory of it.
    """
    harness = _reader()
    registered = {tool for _script, tool in REGISTERED_PAIRS} & SHELL_TOOLS
    assert registered, "no shell tool is registered for any gate -- this axis measures nothing"
    assert registered == set(harness.SHELLS), (
        "the registration sends %s to these gates and `_harness.SHELLS` answers for %s; a shell "
        "without an entry moves no base at all, so every directory verb in it is invisible"
        % (sorted(registered), sorted(harness.SHELLS)))
    for tool, shell in sorted(harness.SHELLS.items()):
        assert shell["verbs"], "%s knows no directory verb at all" % tool
        for verb in shell["verbs"]:
            assert verb == verb.lower(), (
                "%s is spelled with capitals in %s's table, and a folding reader would compare it "
                "against a lowercased word forever" % (verb, tool))


def _kit_gains_a_separator(project, tmp_path, name, separator):
    """A copy of `project` whose KIT reader carries one more pipeline separator.

    APPENDED, NOT PATCHED INTO THE SOURCE TEXT: a test that asserts how a line of `team-kits/**` is
    spelled is a test another task's edit turns red for nothing, and `team-kits/**` is forbidden
    ground for the task this file belongs to. The extension is written as code that reads the
    tuple the module really ends up with, so a rename does not silently make it a no-op -- it makes
    the gate refuse with a NameError, which the assertions below see as "not the reason expected".
    """
    work = str(tmp_path / name)
    shutil.copytree(project, work)
    sys.path.insert(0, os.path.join(work, ".claude", "hooks"))
    import _harness
    path = os.path.join(_harness._kit_hooks_dir(work), "gate_write_scope.py")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n_PIPELINE_SEPARATORS = _PIPELINE_SEPARATORS + (%r,)\n" % (separator,))
    return work


def test_a_separator_this_reader_cannot_place_refuses_the_line(project, tmp_path):
    """Where a command ends is the kits' answer; this reader only adds what their tuple lacks.

    The two readings can drift -- that is the price H15 names for borrowing the kits' shell module
    -- and the direction that drift must NOT take is silence: a separator whose words are left with
    the verb in FRONT of them hides a write, which is how `echo hi & sed -i <kit file>` came out
    rc 0. So the check runs on every line, and the subject here is a line the gate otherwise
    ALLOWS, so nothing except the separator can be what refused it.

    THE OTHER END IS WHAT THE TRIPWIRE COSTS WHEN IT IS WRONG, and it is the whole line: a refusal
    here stops every call, this repo's own kernel invocation included. So a separator this reader
    DOES place must not fire it -- measured 2026-08-05 with `|` in the tuple, which `_harness`
    cuts stages at: the words behind it get a verb of their own, nothing is hidden, and the gate
    has to go on deciding. Before that end existed, the predicate refused it.
    """
    kernel_line = ("PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory "
                   "generate-index")
    work = _kit_gains_a_separator(project, tmp_path, "unknown-separator", "NEWLINE-ISH")
    rc, err = run(work, "gate_lead_write_scope.py", bash_payload(work, "echo hi"))
    assert rc == 2, "a separator this reader cannot place was read as an ordinary word"
    assert "cannot place" in err, "refused, but not for the separator: %s" % err[:300]
    placed = _kit_gains_a_separator(project, tmp_path, "known-separator", "|")
    rc, err = run(placed, "gate_lead_write_scope.py", bash_payload(placed, kernel_line))
    assert rc == 0, (
        "a separator this reader places itself stopped a line it has to judge: %s" % err[:300])
    assert run(placed, "gate_lead_write_scope.py",
               bash_payload(placed, "echo hi | " + RELATIVE_WRITE))[0] == 2, (
        "with that separator in the tuple, a write behind it stopped being judged")


# -- the holes keep their own rule -- now as ITEMS (TSK-0013 F5/F6/F7, FR-0087, DEC-0073) -------
#
# WHAT CHANGED AND WHY. Until 2026-09-04 this block read the hole list as a DOCUMENT: it
# found entries by their heading, judged them against a summary table, and fished cited test names
# out of markdown code spans. Every limit of that reader was a claim nobody checked -- a name behind
# a fence, a name wrapped across two lines, a span showing a span, a table cell carrying the column
# separator. The holes are items now (`BUG` with `hole_number`), so the same three questions are
# asked of parsed records: the verdict IS the status, the limit IS a field, and the tests an entry
# names ARE a list. The document keeps a generated pointer index and nothing else.

HOLE_LIST = os.path.join(ROOT, "docs", "POST_V2_WISHLIST.md")
STATE_ROOT = os.path.join(ROOT, "project_memory")
HOLES_PROSE = os.path.join(ROOT, "docs", "holes")


def _kernel():
    """The kernel this repo runs its own state with -- imported, never re-implemented."""
    team_kits = os.path.join(ROOT, "team-kits")
    if team_kits not in sys.path:
        sys.path.insert(0, team_kits)
    from kernel import backlog_types
    from kernel.state import ProjectState
    return backlog_types, ProjectState(STATE_ROOT)


def _holes():
    """{H number: item} for every hole the store carries, active and archived.

    Read through the KERNEL's own iteration over stored items, so "which files are items" has one
    answer here and in every other reader. A hole is recognised by the field the kernel stamps and
    a caller cannot hand in (`state.capture` refuses a body carrying it), which is why this needs
    no marker of its own.
    """
    backlog_types, state = _kernel()
    found = {}
    with state.lock:
        for item in state._iter_every_stored_item():
            number = str(item.get(backlog_types.HOLE_NUMBER_FIELD) or "")
            if number:
                found[number] = item
    return backlog_types, state, found


def test_every_hole_states_a_verdict_and_an_unclosed_one_names_its_limit():
    """The rule the hole list carried in prose, applied to the items that replaced it.

    THE VERDICT IS THE STATUS. A row of a summary table and a sentence inside an entry could
    disagree -- three of them did, measured 2026-08-05 -- and the whole reason a hole is an item is
    that a record has ONE status. So there is nothing left to compare here; what is measured is
    that every hole stands in a status its type's automaton really has.

    AND AN UNCLOSED HOLE NAMES WHAT TAKES THE PLACE OF THE PROTECTION. "Unclosed" is derived from
    the automaton and not from a list of words: a status that is not one of the type's TERMINALS is
    a hole still standing open. `ACCEPTED_EXCEPTION` is a terminal and carries the duty anyway --
    that is `backlog_types.STATUS_DEPENDENT_FIELDS`, enforced by the kernel and by
    `report.validate_state`, and this asserts the same thing from the outside so a store that
    slipped past both is still caught.
    """
    backlog_types, _state, holes = _holes()
    assert holes, (
        "no hole item in %s. The hole list is migrated by `python tools/migrate_holes.py --root "
        "project_memory --related-pr <goal> --apply`, and this test is the reader that replaced "
        "the document" % STATE_ROOT)
    automaton = backlog_types.AUTOMATA["BUG"]
    unlimited = []
    for number, item in sorted(holes.items()):
        status = str(item.get("status") or "")
        assert status in automaton.states, (
            "%s (%s) stands in %r, which is no status of its type" % (number, item["id"], status))
        closed = status in automaton.terminals and status != backlog_types.HOLE_EXCEPTION_STATUS
        if not closed and not str(item.get(backlog_types.HOLE_LIMIT_FIELD) or "").strip():
            unlimited.append("%s (%s, %s)" % (number, item["id"], status))
    assert not unlimited, (
        "these holes are not closed and say nothing about what takes the place of the protection: "
        "%s" % unlimited)


def _tests_by_module():
    """{test name: {module stem, ...}} over every test file a hole-list entry may name.

    THE CORPUS IS WHERE THE TESTS LIVE, and that is not one file: an entry of this list closes a
    defect anywhere in this repo, and the test that would notice a reopening lives where the defect
    lived -- under `tools/` for the kits and the kernel, here for this repo's own gates. Read against
    `test_gates.py` alone, every citation of a `tools/` test was a FALSE RED and the
    module-qualified spelling that avoids it was skipped outright, so the two limits covered for
    each other (measured 2026-09-02, TSK-0109 N11).

    Parsed, never searched as text: a name that only stands in a docstring would otherwise answer
    for itself.
    """
    files = [os.path.join(HOOKS, "test_gates.py")]
    tools = os.path.join(ROOT, "tools")
    files += [os.path.join(tools, name) for name in sorted(os.listdir(tools))
              if name.startswith("test_") and name.endswith(".py")]
    out = {}
    for path in files:
        stem = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                out.setdefault(node.name, set()).add(stem)
    return out


# A CITATION AND WHERE IT CLAIMS TO LIVE. The entries write a test name in four spellings: bare, a
# module name and a dot in front of it, a file path and a double colon in front of it, and an
# ellipsis with a double colon for "the same file as the citation before it". (Written out rather
# than shown, because a backticked example here would be a citation to this file's own readers --
# measured, it turned two of them red.) So the NAME is what stands after the last separator and the
# MODULE is what stands before it, with the ellipsis form carrying no module at all: reading the
# tail is what makes the four one question instead of four cases. WHAT IS NOT READ HERE: a citation
# whose module is abbreviated to an ellipsis is looked up in every test file of this repo, so it
# can resolve against a file the writer did not mean -- the abbreviation says less than the writing
# rule assumes.
_CITATION_SPLIT_RX = re.compile(r"::|\.")
_DECORATION = "…._"


def _cited_test(span):
    """(module stem or None, the cited name) for a span that cites a test, else None.

    TWO SHAPES ARE PROSE ABOUT CITATIONS AND NOT CITATIONS, and both stand in the list today. A span
    whose CONTENT carries a backtick is a span SHOWING a span -- the doubled-backtick idiom an entry
    uses to quote the shape a pointer has -- and a span holding the naming prefix ALONE, with no
    name behind it, describes a convention rather than a test. The reader that pairs by run length
    (2026-09-03) is the first one to see either of them, so both are excluded here rather than
    edited out of the document. (Neither shape is shown here in backticks: this file's own prose is
    read by `test_every_check_this_apparatus_claims_in_its_own_prose_is_one_that_exists`, and an
    example written as a span is a claim to it -- measured, three times in this round.)
    """
    if "`" in span:
        return None
    tail = _CITATION_SPLIT_RX.split(span)[-1]
    if not tail.lstrip(_DECORATION).startswith("test_") or tail.strip(_DECORATION) == "test":
        return None
    qualifier = span[:len(span) - len(tail)].rstrip(":.").strip(_DECORATION)
    if not qualifier:
        return None, tail
    return os.path.splitext(os.path.basename(qualifier.replace("\\", "/")))[0], tail


def test_every_test_a_hole_names_is_one_that_exists():
    """A hole that claims to be closed names what would notice a relapse, and the name resolves.

    READ OFF THE ITEM (`backlog_types.HOLE_TEST_FIELD`), which is the move FR-0087 (c) asked for:
    the predecessor of this test parsed markdown code spans, and its own docstring had to name
    three things it could not read -- a citation inside a fenced block, a module abbreviated to an
    ellipsis, a summary row whose cell carried the column separator. A list on the item has none of
    those readings.

    THE CORPUS IS WHERE THE TESTS LIVE, and that is not one file: a hole closes a defect anywhere
    in this repo, and the test that would notice a reopening lives where the defect lived -- under
    `tools/` for the kits and the kernel, here for this repo's own gates.

    Names are matched loosely on purpose, exactly as before: the items carry the abbreviations the
    entries used, so the name is looked up EXACTLY first and only as a substring when nothing
    answers exactly.
    """
    backlog_types, _state, holes = _holes()
    assert holes, "no hole item in %s -- see the sibling test for the migration command" % STATE_ROOT
    defined = _tests_by_module()
    assert defined, "no test file in this repo defines a test at all"
    named, wrong = 0, []
    for number, item in sorted(holes.items()):
        for span in backlog_types.field_elements(item.get(backlog_types.HOLE_TEST_FIELD)):
            citation = _cited_test(re.sub(r"\s+", "", str(span)))
            if citation is None:
                wrong.append("%s carries %r in %s, which is no test citation at all"
                             % (number, span, backlog_types.HOLE_TEST_FIELD))
                continue
            module, cited = citation
            stem = cited.strip("_.\u2026")
            matching = sorted(name for name, where in defined.items()
                              if (name == stem or (stem not in defined and stem in name))
                              and (module is None or module in where))
            named += 1
            if len(matching) != 1:
                wrong.append("%s names `%s`, and %d tests answer to it in %s"
                             % (number, span, len(matching), module or "any test file of this repo"))
    assert not wrong, "\n".join(wrong)
    assert named >= 5, (
        "the holes name %d test(s) -- a hole that claims to be closed and names nothing that would "
        "notice is the claim this test exists for" % named)


def test_the_hole_index_in_the_document_is_the_one_the_items_generate():
    """The document carries a GENERATED index, and a hand edit is what this reports.

    REGENERATED AND COMPARED, not checked against a digest written beside it: a digest is a second
    statement of the same fact, and a number in two places is what the whole migration exists to
    end. The generator is the shipped `tools/migrate_holes.py`, imported rather than restated --
    a second rendering here would answer a different question than the one the run writes.
    """
    tools = os.path.join(ROOT, "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import migrate_holes

    _backlog_types, state, holes = _holes()
    assert holes, "no hole item in %s -- see the judges test for the migration command" % STATE_ROOT
    lines, start, end = migrate_holes.read_section(HOLE_LIST)
    carried = lines[start:end]
    generated = migrate_holes.render_index(state)
    assert carried == generated, (
        "the hole index in %s is not the one the items generate -- either a hole was captured "
        "without regenerating it, or the section was edited by hand. Remedy: `python "
        "tools/migrate_holes.py --root project_memory --reindex`, which rewrites this "
        "section from the store and writes nothing else -- from a shell OUTSIDE Claude "
        "Code, because gate 1 refuses every tool write into the state tree.\n"
        "first difference at line %d:\n  document: %r\n  items:    %r"
        % (HOLE_LIST,
           next((i for i, (a, b) in enumerate(zip(carried, generated)) if a != b), 0),
           next((a for a, b in zip(carried, generated) if a != b), "<length differs>"),
           next((b for a, b in zip(carried, generated) if a != b), "<length differs>")))


def _hole_prose(number):
    """The full text of one hole: its prose file where the MIGRATION wrote one, else the item itself.

    Only the migration writes `docs/holes/<n>.md` (`kernel.holes.migrate`); `capture --hole` writes
    an item and nothing else, and its `source` is prose (a protocol section, a DEC, a log file) or
    empty. Read as a path, that prose was a FileNotFoundError on the generation-5 merge's first gate
    run (H166, TSK-0133 M14) -- and the 22 holes captured since generation 4 had never been read by
    this helper at all, because every caller happened to name a migrated one. What decides is
    whether the file `docs/holes/<n>.md` exists -- the same question the kernel's index renderer
    asks before it links a row (`holes._prose_link`), asked here of the path directly, not through
    that function, which answers with a table cell -- so a captured hole is judged on the fields its
    measured chain lives in.
    """
    _backlog_types, _state, holes = _holes()
    item = holes[number]
    path = os.path.join(ROOT, "docs", "holes", "%s.md" % number)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    return "\n\n".join(str(item.get(field) or "")
                       for field in ("title", "observed", "expected", "repro", "limits", "source"))


# The hole that says what the cross table's OVER-REFUSAL is made of, and the paragraph it says it
# in. The claim is generated out of the table here rather than read as prose: it stood wrong in both
# directions at once -- two things named that had no such cell, four moves unnamed that were half of
# them -- and it had been corrected by hand the round before that.
OVER_REFUSAL_HOLE = "H30"
COMPOSITION_RX = re.compile(r"\*\*Zusammensetzung[^*]*\*\*(.*?)(?=\n\n|\Z)", re.DOTALL)

# What a closed hole has to name when the cross table is what would notice its defect: the VALUES
# of that table it stands on. Nothing tied the two together before -- measured 2026-08-07, the
# hand-written axes can be cut until 100 of 1440 cells are left and every other test in this file
# stays green, because the tripwires cover the GENERATED axes and not the written-out values.
CELLS_RX = re.compile(r"\*\*Zellen[^*]*\*\*(.*?)(?=\n\n|\Z)", re.DOTALL)
TABLE_TEST = "test_gate1_refuses_a_line_exactly_where_the_shell_would_write"


def _over_refusal():
    """The cells where the gate refuses and the shell does not write the protected file."""
    return {label for label in LINE_SHAPES
            if LINE_SHAPES[label][1] is False and LINE_SHAPES[label][2]}


def test_a_hole_states_the_over_refusal_the_table_carries():
    """What a hole claims about the check set is GENERATED out of the check set.

    Measured 2026-08-07, and the claim had been corrected by hand one round earlier: the entry named
    the descriptor duplication and the words the kits' reader steps over, and neither has an
    over-refusal cell at all. It left four moves unnamed that are exactly half of the count it
    stated. Only the two numbers were right.

    THE PROSE IS WHERE IT ALWAYS WAS, one file further on: the item carries identity, verdict and
    limit, and the measured chain lives in the file its `source` names. That is the split
    CLAUDE.md already prescribes for a wish, and the reason the item cannot carry it is measured --
    three entries of this list are larger than the 12 KB an active item may be.
    """
    body = _hole_prose(OVER_REFUSAL_HOLE)
    found = COMPOSITION_RX.search(body)
    assert found, (
        "%s no longer states what the over-refusal in the cross table is made of, so the claim "
        "this test generates has nowhere to be compared with" % OVER_REFUSAL_HOLE)
    said = found.group(1)
    numbers = [int(number) for number in re.findall(r"\d+", said)]
    friction = _over_refusal()
    assert numbers[:2] == [len(friction), len(LINE_SHAPES)], (
        "%s says %s of the table's cells are over-refusal; the table has %d of %d"
        % (OVER_REFUSAL_HOLE, " of ".join(str(number) for number in numbers[:2]),
           len(friction), len(LINE_SHAPES)))
    named = {re.sub(r"\s+", " ", span).strip()
             for span in re.findall(r"`([^`]+)`", said, re.DOTALL)}
    moves = {label.split(" -- ")[0] for label in friction}
    assert named == moves, (
        "%s names moves that have no over-refusal cell: %s -- and leaves these unnamed: %s"
        % (OVER_REFUSAL_HOLE, sorted(named - moves), sorted(moves - named)))


def test_every_cell_a_closed_hole_names_is_one_the_table_carries():
    """A hole that leans on the cross table names the VALUES of it that carry its chain.

    THE HAND-WRITTEN AXES HAD NO TRIPWIRE. `test_the_words_the_kits_reader_steps_over_are_all
    _crossed` and `test_the_shells_this_reader_knows_are_the_ones_the_registration_names` bind the
    axes that are GENERATED out of the reader; the positions, the moves, the bases and the loose
    shapes are typed here, and deleting them costs nothing -- measured 2026-08-07, cut down to 100
    of 1440 cells with every other test in this file still green, and what was silently removable
    was exactly the values that carry closed holes.

    BOTH ENDS. A value a hole names and the table no longer carries is the cut; a hole that leans
    on the table and names no value at all is the tripwire being dropped instead of the cell. Which
    holes owe one is read off the ITEM -- those whose `regression_tests` cite the table's test --
    rather than off a substring search over prose.
    """
    backlog_types, _state, holes = _holes()
    values = set(POSITIONS) | set(MOVES) | set(BASES) | set(LOOSE_SHAPES)
    owed, wrong, named = [], [], 0
    for number, item in sorted(holes.items()):
        cited = [re.sub(r"\s+", "", str(one))
                 for one in backlog_types.field_elements(item.get(backlog_types.HOLE_TEST_FIELD))]
        if not any(TABLE_TEST in one for one in cited):
            continue
        found = CELLS_RX.search(_hole_prose(number))
        spans = [re.sub(r"\s+", " ", span).strip()
                 for span in re.findall(r"`([^`]+)`", found.group(1), re.DOTALL)] if found else []
        if not spans:
            owed.append(number)
            continue
        for span in spans:
            named += 1
            if span not in values and span not in LINE_SHAPES:
                wrong.append("%s names `%s`, and no value of the cross table is spelled that way"
                             % (number, span))
    assert not owed, (
        "these holes say the cross table is what would notice their defect and name no value of "
        "it, so the values they stand on can be deleted without anything going red: %s" % owed)
    assert not wrong, "\n".join(wrong)
    assert named, (
        "no hole leans on %s any more, so this test measured nothing" % TABLE_TEST)


# What a hole has to state when the TILDE check set is what would notice its defect: how big that
# set is and what the axis it gained is made of. Same reason as `CELLS_RX` above and a worse case --
# the set was not merely shrinkable, it was already too narrow: measured 2026-08-07, none of its
# 471 subjects carried quoting in the target word, and the shape that did was rc 0 through the real
# gate while bash rewrote the protected file.
SUBJECTS_RX = re.compile(r"\*\*Subjekte[^*]*\*\*(.*?)(?=\n\n|\Z)", re.DOTALL)
TILDE_TEST = "test_gate1_places_a_tilde_word_where_the_shell_puts_it"


def test_every_tilde_subject_a_closed_hole_names_is_one_the_check_set_carries():
    """A hole leaning on the tilde check set states its SIZE and the values of its quoting axis.

    GENERATED OUT OF THE SET AND COMPARED WITH IT, in both directions, which is what the same
    treatment of the cross table (`test_a_hole_states_the_over_refusal_the_table_carries`) exists
    for: a number that goes stale says nothing, and an axis named in prose that the set no longer
    carries says less. The set equality is the half that matters here -- the defect that round
    closed was an axis the check set did not have at all, so a hole that names its values cannot be
    satisfied by a set they were dropped from.
    """
    backlog_types, _state, holes = _holes()
    owed, named = [], 0
    prefixes = len(_tilde_prefixes(_reader()))
    for number, item in sorted(holes.items()):
        cited = [re.sub(r"\s+", "", str(one))
                 for one in backlog_types.field_elements(item.get(backlog_types.HOLE_TEST_FIELD))]
        if not any(TILDE_TEST in one for one in cited):
            continue
        found = SUBJECTS_RX.search(_hole_prose(number))
        if not found:
            owed.append(number)
            continue
        said = found.group(1)
        # the numbers OUTSIDE the backticks: the values of the axis carry digits of their own
        numbers = [int(number_) for number_ in re.findall(r"\d+", re.sub(r"`[^`]*`", " ", said))]
        assert numbers[:3] == [len(TILDE_SUBJECTS), len(TILDE_STATES), prefixes], (
            "%s says the tilde check set is %s; it is %d subjects out of %d states and %d prefixes"
            % (number, " / ".join(str(one) for one in numbers[:3]),
               len(TILDE_SUBJECTS), len(TILDE_STATES), prefixes))
        spans = {re.sub(r"\s+", " ", span).strip()
                 for span in re.findall(r"`([^`]+)`", said, re.DOTALL)}
        assert spans == set(TILDE_QUOTINGS), (
            "%s names quotings the check set does not carry: %s -- and leaves these unnamed: %s"
            % (number, sorted(spans - set(TILDE_QUOTINGS)), sorted(set(TILDE_QUOTINGS) - spans)))
        named += 1
    assert not owed, (
        "these holes say the tilde check set is what would notice their defect and state nothing "
        "about it, so it can be cut back to what they were measured against: %s" % owed)
    assert named, (
        "no hole leans on %s any more, so this test measured nothing" % TILDE_TEST)


def _anchors(path):
    """What a document can be cited BY: the hole entries it carries and its numbered sections.

    Read off the document's own headings, so a document gains an anchor by carrying it and not by
    being listed anywhere.
    """
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    # TWO SPELLINGS OF THE SAME ANCHOR, and the second is what the migration left: a hole used to
    # be an `### H<n>` heading in this document and is now a row of the GENERATED pointer index
    # (`[H<n>](docs/holes/H<n>.md)`). Both are read, so a citation resolves before and after the
    # migration and nothing here has to know which of the two the document is in today.
    return (set(re.findall(r"^### (H\d+)\b", text, re.M))
            | set(re.findall(r"^\| \[(H\d+)\]\(", text, re.M)),
            set(re.findall(r"^## (\d+)\.", text, re.M)))


def _said_in(source):
    """Every unit of text a source file states something in: its strings and its comment blocks.

    PARSED, NOT SEARCHED. A docstring, a refusal message and a block of comment lines are the three
    places this apparatus makes claims in, and each of them is one statement -- so a reference and
    the anchor it is made with have to stand in the SAME one. Reading them off `ast` and `tokenize`
    also means a claim inside a string that no longer belongs to any code is not read as if it did.
    """
    out = [node.value for node in ast.walk(ast.parse(source))
           if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    block, previous = [], None
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        if previous is not None and token.start[0] != previous + 1 and block:
            out.append("\n".join(block))
            block = []
        block.append(token.string)
        previous = token.start[0]
    if block:
        out.append("\n".join(block))
    return out


def test_every_reference_to_a_measurement_leads_to_one(project):
    """A reference that names a document has to lead to one that carries what it is cited for.

    Measured 2026-08-05: the hole list assigned entries to the two measurement protocols by NUMBER
    RANGE, and three of the entries in the range were in neither document. A range is a claim about
    a file nobody checks; a reference beside the entry is one that can be. Measured again in the
    round after that: a docstring cited a protocol for six line shapes, three of which were in a
    DIFFERENT protocol -- because this half of the test asked only whether the file existed.

    BOTH DIRECTIONS ARE READ THE SAME WAY, and that is what this round adds: the entries of the
    hole list, and the apparatus itself, whose docstrings, refusal texts and comments point at
    protocols and at the hole list. A reference has to name what it is citing -- an entry (`H<n>`)
    for the hole list, a section for a measurement protocol -- and the document has to carry it.
    Which anchors a document has is read off the document (`_anchors`); a document that carries
    neither kind is cited by its name alone, because there is nothing finer to check it against.
    """
    # THE HOLES' OWN PROSE, one file per entry since the migration (FR-0087): the item carries
    # identity, verdict and limit, and the measured chain -- which is what cites a protocol -- lives
    # in the file its `source` names.
    #
    # THE `assert` IS NOT DECORATION. Without it this test walked an empty loop over an unmigrated
    # store and passed while its five siblings failed -- measured 2026-09-05, "6 failed, 1 passed":
    # a named test that cannot fail, which is the class this repo calls dearer than no test. The
    # local name is `carried` and not `holes` for the same round's reason: `_anchors` hands back a
    # variable of that name below, and the shadowed one was what the second half asserted on.
    _backlog_types, _state, carried = _holes()
    assert carried, (
        "no hole item in %s -- see the judges test for the migration command" % STATE_ROOT)
    for name in sorted(carried):
        body = _hole_prose(name)
        for relative in re.findall(r"docs/reviews/[A-Za-z0-9._-]+\.md", body):
            path = os.path.join(ROOT, *relative.split("/"))
            assert os.path.isfile(path), "%s points at %s, which does not exist" % (name, relative)
            with open(path, encoding="utf-8") as handle:
                assert re.search(r"\b%s\b" % name, handle.read()), (
                    "%s cites %s, and that document does not carry it" % (name, relative))
    for entry in sorted(os.listdir(HOOKS)):
        if not entry.endswith(".py"):
            continue
        with open(os.path.join(HOOKS, entry), encoding="utf-8") as handle:
            source = handle.read()
        for said in _said_in(source):
            for relative in set(re.findall(r"docs/[A-Za-z0-9._/-]+\.md", said)):
                # A PATH THIS SUITE BUILDS IS A SUBJECT, NOT A REFERENCE: the gates' docstrings
                # quote measured command lines, and those name files in the stand-in project. So
                # both trees answer, and neither is a list -- the stand-in is whatever
                # `build_project` writes.
                here = os.path.join(ROOT, *relative.split("/"))
                assert os.path.isfile(here) or os.path.isfile(
                    os.path.join(project, *relative.split("/"))), (
                    "%s names %s, and nothing of that name exists in this repo or in the project "
                    "the suite builds" % (entry, relative))
                if not os.path.isfile(here):
                    continue
                holes, sections = _anchors(here)
                if holes:
                    assert holes & set(re.findall(r"\bH\d+\b", said)), (
                        "%s cites %s without naming an entry of it, so nothing says what the "
                        "reference is for: %r" % (entry, relative, said[:200]))
                elif sections:
                    assert sections & set(re.findall(r"section (\d+)", said)), (
                        "%s cites %s without naming a section of it, so nothing says what the "
                        "reference is for: %r" % (entry, relative, said[:200]))


# -- a claim that says "this is a test" names the test (SR-0008 case b, TSK-0009) ---------------

# This file, under the two spellings a statement beside it points INTO it with: the pytest node
# prefix, and the module prefix a name of this file is qualified by. Both are read off the file's
# own name, so a rename cannot leave a prefix behind that matches nothing.
THIS_FILE = os.path.basename(__file__)
POINTER_PREFIXES = (THIS_FILE + "::", os.path.splitext(THIS_FILE)[0] + ".")
# ...and the two spellings that name the FILE rather than anything in it -- with and without the
# extension, because a statement says both. Derived from the same name for the same reason.
THIS_FILE_ITSELF = (THIS_FILE, os.path.splitext(THIS_FILE)[0])
# What pytest appends to a name to identify ONE case of a parametrised test. The name is what
# stands in front of it, which is a fact of the tool's node ids rather than a spelling somebody
# happens to use.
PARAMETERS = "["


def _defined_here():
    """Every name this file defines at module level -- tests, helpers and the tables they cross."""
    with open(os.path.join(HOOKS, THIS_FILE), encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    names = {node.name for node in tree.body
             if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    names |= {target.id for node in tree.body if isinstance(node, ast.Assign)
              for target in node.targets if isinstance(target, ast.Name)}
    return names


def _can_stand_in_a_name(character):
    """Could this character occur ANYWHERE inside an identifier?

    Asked of the language rather than of a set of punctuation: a digit cannot START an identifier
    but can stand in one, so the question is put with a letter in front of it. That is the whole
    difference between a definition and the list of separators somebody remembers.
    """
    return ("a" + character).isidentifier()


def _undecorated(text):
    """`text` without what cannot be part of a name: the ends, and a parameter id.

    A character an identifier cannot carry at all is decoration wherever it stands at an END --
    a bracket, a comma, a colon, a full stop, the asterisks of a bold span -- so a run of them is
    taken off both sides. What a parametrised case appends is cut instead of stripped, because it
    is not at the end of anything: `name[case]` is pytest's node id and the NAME stands in front of
    the bracket.

    THE INTERIOR IS LEFT ALONE, and that is what makes the qualified spellings survive this: the
    dot of `test_gates.<name>` and the `::` of a node id stand in the middle, so the prefixes are
    stripped by the caller afterwards rather than eaten here.
    """
    head = text.split(PARAMETERS, 1)[0]
    while head and not _can_stand_in_a_name(head[0]):
        head = head[1:]
    while head and not _can_stand_in_a_name(head[-1]):
        head = head[:-1]
    return head


def _spans(said):
    """The backtick spans of a statement -- under EVERY pairing an unpaired backtick leaves open.

    `re.findall` pairs from the left, so ONE stray backtick in front of a real pointer shifts every
    pair behind it: the name is then neither read nor reported, which is the silent direction
    (BUG-0133 (c) / H41; inventory 2026-08-14: 15 statements with an odd count in this directory,
    all of them code string literals, none with a test name behind the stray one).

    WHICH BACKTICK IS THE STRAY ONE IS NOT DECIDABLE, so this does not guess: a statement with an
    odd count is read under BOTH pairings and the readings are unioned -- the reader answers for
    every name the statement could be claiming. A statement with an even count has one pairing and
    this costs it nothing.
    """
    found = list(re.findall(r"`([^`]+)`", said, re.DOTALL))
    if said.count("`") % 2:
        found += re.findall(r"`([^`]+)`", said[said.find("`") + 1:], re.DOTALL)
    return found


def _glued(span):
    """A span with the breaks an EDITOR put in it closed up -- and nothing else.

    ONLY WHERE A LINE ENDED. A long test name wraps across lines, and a comment continues the next
    line with its own marker; a name read as two halves resolves to nothing, which would make the
    check depend on where an editor happened to break the line rather than on what the statement
    claims.

    A SPACE INSIDE ONE LINE IS A SPACE SOMEBODY TYPED, and closing that up too invented pointers:
    a span of prose beginning with the collection prefix glued into an identifier this file never
    defines and was reported as a rotten pointer -- a false-alarm class against honest text
    (BUG-0133 (b) / H41).
    """
    return re.sub(r"\s*\n[\s#]*", "", span.strip())


def _points_into_this_file(said):
    """Every name of this file a statement points at -- read out of its backtick spans.

    HOW A SPAN IS FOUND AND HOW IT IS CLOSED UP are `_spans` and `_glued`, each with the direction
    it was measured wrong in.

    THE DECORATION AROUND A NAME IS NOT PART OF IT, and taking it off is a definition rather than a
    list of the spellings somebody tried: a character that cannot occur in an identifier at all
    cannot be part of the name, so a run of them at either end is stripped, and a parameter id is
    cut at the bracket pytest opens it with. Without that the reader was silent on seven spellings
    at once -- `name()`, a trailing comma, dot or colon inside the span, `**name**`, `name[case]`
    and the node id of a parametrised case -- and silence here is what makes the whole check look
    green while a pointer rots (measured 2026-08-14, the verifier's list).

    WHAT COUNTS AS POINTING AT A NAME, rather than at this file: a span carrying one of the
    prefixes above, or one that is a bare test name (the prefix pytest collects by). This file's
    own name is no pointer into it -- with or without the extension -- because it is a reference
    the reader can follow either way, and demanding a name for it would refuse the honest form of
    "this lives next to the suite".

    WHAT STAYS UNREAD, named rather than implied: a node path through a CLASS
    (`test_gates.py::SomeClass::name`), and anything else that is not an identifier once the
    decoration is off. Nothing in this suite is written that way today -- it collects no test
    classes -- and reading it would mean this reader deciding which half of a path is the name.
    """
    out = set()
    for span in _spans(said):
        glued = _undecorated(_glued(span))
        if glued in THIS_FILE_ITSELF:
            continue
        qualified = False
        for prefix in POINTER_PREFIXES:
            if glued.startswith(prefix):
                glued, qualified = glued[len(prefix):], True
                break
        if not qualified and not glued.startswith("test_"):
            continue
        if glued.isidentifier():
            out.add(glued)
    return out


# HOW A HUMAN WRITES A POINTER, as the shapes a reviewer found this reader silent on (2026-08-14)
# plus the two the prefixes above are for. An enumeration on purpose and with a tripwire at both
# ends: every shape has to READ (a decoration the reader stopped taking off says so) and has to be
# REPORTED when the name is invented (a shape that quietly resolves to nothing says so). The
# reader itself is a definition, so a shape that joins this table needs no change there.
SPELLINGS_OF_A_POINTER = {
    "plainly": "a statement naming `%s`",
    "with the parentheses of a call": "`%s()`",
    "with a comma inside the span": "`%s,`",
    "with a full stop inside the span": "`%s.`",
    "with a colon inside the span": "`%s:`",
    "inside a bold span": "`**%s**`",
    "as the node id of one parametrised case": "`%s[Bash]`",
    "as a pytest node id": "`" + THIS_FILE + "::%s`",
    "as a pytest node id with parameters": "`" + THIS_FILE + "::%s[Bash]`",
    "qualified with this module": "`" + POINTER_PREFIXES[1] + "%s`",
}

# A NODE ID THAT NAMES A FILE, which is how this apparatus points at a check in ANOTHER suite. The
# name is the second half; what stands in front of it is a path, and a path is what makes the
# pointer followable at all.
_NODE_IN_ANOTHER_FILE = re.compile(r"([\w./\\-]+\.py)::([A-Za-z_]\w*)")


def _points_into_another_file(said):
    """Every `<path>.py::<test>` a statement points at, as sorted `(path, name)` pairs.

    THE OTHER HALF OF THE SAME DUTY (BUG-0133 (d) / H41): a pointer at a check in a neighbouring
    suite was skipped by `_points_into_this_file` -- it carries a dot, and a dot could be a file
    name -- so nobody looked it up. Measured 2026-08-14 over the H43 entry: seven such pointers,
    `set()` back from the reader, all seven resolved BY HAND; three more came with H44 and one with
    H70, eleven in all, still by hand. What is outside a watcher's reach accumulates.

    THIS FILE'S OWN UNQUALIFIED PREFIX IS NOT READ HERE, because `_points_into_this_file` already
    answers for it and a bare `test_gates.py` names no path this repo carries.
    """
    out = set()
    for span in _spans(said):
        match = _NODE_IN_ANOTHER_FILE.search(_glued(span))
        if not match:
            continue
        path = match.group(1).replace("\\", "/")
        if path in THIS_FILE_ITSELF:
            continue
        out.add((path, match.group(2)))
    return sorted(out)


def _tests_declared_in(relative):
    """The test names a file of this repo declares, or None when there is no such file to ask.

    PARSED, never searched, and asked of the FILE the pointer names: a node id is a claim that this
    exact path declares this exact test, and only the path's own source can answer it.
    """
    path = os.path.join(ROOT, *relative.split("/"))
    try:
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
    except (OSError, SyntaxError):
        return None
    return {node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _decoration_of(span, name):
    """The SHAPE a pointer span is written in: the name replaced by `%s`, a case id emptied.

    WHAT IS SHAPE AND WHAT IS DATA: pytest's case id is data -- which row of a parametrised test a
    statement means -- so `[Bash]` and `[Write]` are one spelling. Everything else around the name
    is the spelling itself, and that is what `SPELLINGS_OF_A_POINTER` has to carry.
    """
    return re.sub(r"\[[^\]]*\]", "[]", span.replace(name, "%s"))


def _shapes_the_table_carries():
    """The spellings `SPELLINGS_OF_A_POINTER` declares, as spans -- the table read as its own claim."""
    out = set()
    for value in SPELLINGS_OF_A_POINTER.values():
        for span in re.findall(r"`([^`]+)`", value):
            out.add(_decoration_of(span, "%s"))
    return out


def test_every_check_this_apparatus_claims_in_its_own_prose_is_one_that_exists():
    """SR-0008 case (b): a property claim in this directory becomes a TEST, and the pointer says
    WHICH -- so the claim can be followed, and rots visibly instead of quietly.

    THE OCCASION IS MEASURED, in this directory and not borrowed from another: `build_project`
    pointed at `…however_the_line_spells_it` for the reason it is a function rather than a fixture,
    and no test of that name has existed for rounds -- the one that needs a path with a space is
    `test_gate1_refuses_a_protected_path_spelled_absolutely_through_a_space`. Nothing noticed,
    because the holes' pointers were checked (`test_every_test_a_hole_names_is_one_that_exists`,
    which read the document then and reads the items now) and the apparatus's own were not.

    BOTH ENDS, AND NEITHER OF THEM IS THIS DIRECTORY'S OWN TEXT: the reader is driven with
    statements built out of names this file really defines and one it cannot define, so a reader
    that stopped finding anything fails here rather than passing an empty sweep.

    HOW FAR IT REACHES: the `.py` sources of this directory, because those are what `_said_in` can
    parse, and only a pointer spelled in backticks. A test named in `CLAUDE.md`, in a role
    definition under `.claude/agents/` or in the `_comment` of the registration is NOT read here --
    the constitution's pointers into this layer are checked by
    `test_the_constitution_names_only_code_that_exists`, and that check knows modules, not tests.
    """
    defined = _defined_here()
    tests = sorted(name for name in defined if name.startswith("test_"))
    assert tests, "this file defines no tests at all, so there is nothing a pointer could resolve to"
    real, table = tests[0], "LINE_SHAPES"
    absent = max(tests, key=len) + "_and_nothing_of_that_name"
    assert table in defined and _points_into_this_file(
        "`%s%s`" % (POINTER_PREFIXES[1], table)) == {table}, (
        "the reader does not see a qualified pointer at a table, which is how the axes this "
        "apparatus decides from are cited")
    for spelling in THIS_FILE_ITSELF:
        assert not _points_into_this_file("this lives next to `%s`" % spelling), (
            "naming the FILE (%r) is read as a pointer at a name in it -- which is a false alarm "
            "against an honest reference nobody can follow any further" % spelling)
    for label, shape in sorted(SPELLINGS_OF_A_POINTER.items()):
        assert _points_into_this_file(shape % real) == {real}, (
            "the reader does not see a pointer written %s, so a name spelled that way could rot "
            "unnoticed" % label)
        assert _points_into_this_file(shape % absent) == {absent}, (
            "a name this file does not define, written %s, is not reported -- then the sweep "
            "below cannot fail for it" % label)
    assert absent not in defined, (
        "the name built to stand for one that does not exist is defined after all")
    stale, carriers = [], set()
    for entry in sorted(os.listdir(HOOKS)):
        if not entry.endswith(".py"):
            continue
        with open(os.path.join(HOOKS, entry), encoding="utf-8") as handle:
            source = handle.read()
        for said in _said_in(source):
            for cited in sorted(_points_into_this_file(said)):
                carriers.add(entry)
                if cited not in defined:
                    stale.append("%s points at `%s`, and %s defines nothing of that name: %r"
                                 % (entry, cited, THIS_FILE, said[:160]))
    assert not stale, (
        "these statements claim a check that is not there any more:\n%s" % "\n".join(stale))
    # THE SUITE'S OWN PROSE CANNOT ANSWER FOR THE SWEEP, which is what a bare count would have let
    # it do: this file cites tests constantly, so a run in which every gate had stopped naming its
    # checks would still have counted them and looked measured.
    assert carriers - {THIS_FILE}, (
        "no file under %s except %s points at a check any more, so the gates' own prose claims "
        "nothing this run could follow -- and case (b) is exactly what that prose owes"
        % (HOOKS, THIS_FILE))


def _said_in_the_hook_sources():
    """`(file, statement)` for every statement the `.py` sources of this directory make."""
    for entry in sorted(os.listdir(HOOKS)):
        if not entry.endswith(".py"):
            continue
        with open(os.path.join(HOOKS, entry), encoding="utf-8") as handle:
            source = handle.read()
        for said in _said_in(source):
            yield entry, said


def test_the_pointer_reader_answers_for_every_shape_a_statement_here_can_carry():
    """BUG-0133 / H41: the four measured limits of the pointer watcher, each driven in the
    direction it was silent in -- the table against a second source, prose that is not a name, a
    stray backtick, and a pointer at a check in ANOTHER file.

    (a) THE TABLE AGAINST A SECOND SOURCE. `SPELLINGS_OF_A_POINTER` drives its own watcher: a
    shape deleted from it takes the check for that shape with it and the run stays green. So the
    LIVING corpus is the second source -- every decoration a statement in this directory really
    writes a resolved pointer in has to be one the table declares. Shrink the table below what
    people write, and this is red.

    (b) PROSE IS NOT A NAME. A span that begins with the collection prefix and continues in words
    used to be closed up into an identifier nobody defines and reported as rotten -- a false alarm
    against honest text. Only a break an EDITOR made is closed up now (`_glued`).

    (c) A STRAY BACKTICK HID A POINTER. Pairing runs from the left, so one unpaired backtick in
    front of a real pointer made it invisible -- neither read nor reported, which is the silent
    direction. Both pairings are answered now (`_spans`).

    (d) A POINTER AT A CHECK IN ANOTHER FILE IS RESOLVED IN THAT FILE. It carries a dot, so the
    reader for this file's own names skipped it and nobody looked it up; eleven such pointers were
    resolved by hand across three hole entries. Measured here 2026-09-12: the `.py` sources of this
    directory carry two of them, both in `gate_test_scope.py` and both resolving -- and they were
    found by this sweep, not by hand.
    """
    defined = _defined_here()
    real = sorted(name for name in defined if name.startswith("test_"))[0]

    # (b)
    prose = "`%s and then some more words` says nothing about a name" % real
    assert not _points_into_this_file(prose), (
        "a span of words beginning with the collection prefix is closed up into a name and "
        "reported: %r -> %s" % (prose, sorted(_points_into_this_file(prose))))
    wrapped = "`%s\n    #  %s`" % (real[:8], real[8:])
    assert _points_into_this_file(wrapped) == {real}, (
        "a name an editor broke across a line is no longer read as one, so this check would "
        "depend on where the line happened to break: %r" % wrapped)

    # (c)
    hidden = "a stray ` and then `%s`" % real
    assert _points_into_this_file(hidden) == {real}, (
        "one unpaired backtick in front of a pointer hides it from the reader -- neither read nor "
        "reported, which is the direction nobody notices: %r" % hidden)

    # (d)
    neighbour = next(((relative, name) for relative in sorted(globmodule.glob(
        os.path.join(ROOT, "tools", "test_*.py")))
        for name in sorted(_tests_declared_in("tools/" + os.path.basename(relative)) or ())
        if name.startswith("test_")), None)
    assert neighbour, "this repo declares no test under tools/, so (d) has nothing to resolve"
    relative, name = "tools/" + os.path.basename(neighbour[0]), neighbour[1]
    assert _points_into_another_file("`%s::%s`" % (relative, name)) == [(relative, name)], (
        "a node id naming another file of this repo is not read as a pointer at all")
    assert name in (_tests_declared_in(relative) or set()), (
        "the node the drive is built from does not resolve, so this drive proves nothing")
    invented = name + "_and_nothing_of_that_name"
    assert invented not in (_tests_declared_in(relative) or set()), (
        "the name built to stand for one that does not exist is declared after all")
    assert _tests_declared_in(relative + ".not-a-file") is None, (
        "a path this repo does not carry answers with a set of names, so a pointer at a file that "
        "was deleted would resolve")

    # (d), the sweep over this directory's own prose
    unresolved = []
    for entry, said in _said_in_the_hook_sources():
        for relative, cited in _points_into_another_file(said):
            declared = _tests_declared_in(relative)
            if declared is None or cited not in declared:
                unresolved.append("%s points at `%s::%s`, which resolves to nothing: %r"
                                  % (entry, relative, cited, said[:160]))
    assert not unresolved, (
        "these statements point at a check in another file that is not there:\n%s"
        % "\n".join(unresolved))

    # (a)
    declared_shapes, uncovered = _shapes_the_table_carries(), []
    for entry, said in _said_in_the_hook_sources():
        for span in _spans(said):
            glued = _undecorated(_glued(span))
            if glued not in defined or not glued.startswith("test_"):
                continue
            shape = _decoration_of(_glued(span), glued)
            if shape not in declared_shapes:
                uncovered.append("%s writes a pointer as %r, which %s does not declare"
                                 % (entry, shape, "SPELLINGS_OF_A_POINTER"))
    assert not uncovered, (
        "the table of spellings drives its own watcher, and the corpus writes shapes it does not "
        "carry -- so the watcher is not measuring those:\n%s" % "\n".join(sorted(set(uncovered))))


# -- a citation names the record that is IN FORCE (BUG-0035) -------------------


def _contract_types():
    """The item types whose record states a RULE, asked of the kernel's own field contract.

    THE QUESTION THAT SEPARATES A RULE FROM AN EVENT: which types does `REQUIRED_FIELDS` oblige to
    carry a `contract`? A task, a bug, a measurement record something that HAPPENED, and that stays
    true after the item is archived; a contract states what holds NOW, and archiving it is how this
    repo replaces it.

    WHAT IT DOES NOT REACH, named rather than implied: `DEC` states a decision, and an archived
    decision is replaced in the same way -- `DEC-0016` is archived and cited in this directory. A
    second field name here would be the enumeration this repo keeps paying for, and whether an
    archived decision may be cited plainly is undecided, so that half is reported rather than
    quietly answered.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel.backlog_types import REQUIRED_FIELDS
    return {name for name, fields in REQUIRED_FIELDS.items() if "contract" in fields}


def _contract_items(types):
    """(replaced, in force) contract ids -- proposed by the store, CLASSIFIED by the reader.

    The walk only proposes names. Whether an id is archived is answered by
    `_harness.resolve_references`, the same reader gates 2 and 4 decide with; deciding it from the
    directory a file sits in would measure the layout instead of the store.
    """
    import _harness
    proposed = set()
    for _base, _dirs, names in os.walk(os.path.join(ROOT, "project_memory")):
        for name in names:
            stem, extension = os.path.splitext(name)
            if extension == ".yaml" and stem.split("-")[0] in types:
                proposed.add(stem)
    replaced, in_force = [], []
    for ref in _harness.resolve_references(ROOT, " ".join(sorted(proposed))):
        if ref.found:
            (replaced if ref.archived else in_force).append(ref.text)
    return sorted(replaced), sorted(in_force)


def _cited_but_replaced(said, types):
    """The contract ids a statement names that are archived, when it names none that is in force.

    THE RULE: a replaced contract may be discussed, but not alone -- the record that took its place
    stands in the SAME statement, so a reader who follows the citation lands on the rule that binds.
    What "the same statement" means is `_said_in`: one string, or one unbroken block of comment
    lines.

    WHAT IT DOES NOT ASK is whether the prose around the citation leans on the old record as
    authority; a statement that names the one in force passes whatever it then says about the old
    one. The bare citation is what this catches, and that is the shape BUG-0035 was made of.
    """
    import _harness
    cited = [ref for ref in _harness.resolve_references(ROOT, said)
             if ref.found and ref.item_type in types]
    if any(not ref.archived for ref in cited):
        return []
    return sorted({ref.text for ref in cited if ref.archived})


def test_no_statement_here_cites_a_replaced_contract_on_its_own():
    """A comment citing a replaced contract sends its reader to a rule that does not bind.

    THE OCCASION IS MEASURED (BUG-0035): SR-0006 was replaced by SR-0009 and archived, and fourteen
    statements in this directory went on naming the archived one as the contract -- three of them
    the opening line of a gate, two more the opening line of the shared body and of this file.
    Nothing noticed, because nothing ever asked the store what it says about an id a comment names.

    BOTH ENDS, AND NEITHER OF THEM IS THIS DIRECTORY'S OWN TEXT: the predicate is driven with a
    statement built out of ids the store hands over -- a replaced contract alone must be reported,
    the same statement with the one in force beside it must not. A check whose only subject is the
    tree it runs over cannot tell "nothing is wrong" from "nothing was looked at".

    HOW FAR IT REACHES: the `.py` sources of this directory, because those are what `_said_in` can
    parse. A citation in the registration beside them (`.claude/settings.json` carries prose in a
    `_comment`) is not read here, and neither is one in `CLAUDE.md` or under `docs/`.
    """
    types = _contract_types()
    assert types, "no type is obliged to carry a contract, so this test asks about nothing"
    replaced, in_force = _contract_items(types)
    assert replaced, "no replaced contract is in this store, so the rule could not be broken"
    assert in_force, "no contract is in force in this store, so the exemption could not be shown"
    alone = "a statement that names %s and nothing else" % replaced[0]
    assert _cited_but_replaced(alone, types) == [replaced[0]], (
        "the predicate does not report %s standing alone, so what follows measures nothing"
        % replaced[0])
    assert not _cited_but_replaced("%s, replaced by %s" % (alone, in_force[0]), types), (
        "the predicate reports %s even beside %s, so it refuses the honest form of a historical "
        "mention" % (replaced[0], in_force[0]))
    stale = []
    for entry in sorted(os.listdir(HOOKS)):
        if not entry.endswith(".py"):
            continue
        with open(os.path.join(HOOKS, entry), encoding="utf-8") as handle:
            source = handle.read()
        for said in _said_in(source):
            for cited in _cited_but_replaced(said, types):
                stale.append("%s cites %s, which the store reports archived, without naming the "
                             "contract that replaced it: %r" % (entry, cited, said[:160]))
    assert not stale, "\n".join(sorted(set(stale)))


# -- the deadline the registration sets (TSK-0011 F4) --------------------------

# RFC 5737 reserves these three ranges for documentation: no host is assigned in any of them, so
# nothing answers. What makes a question about one SLOW rather than instantly wrong is the SMB
# client's own retry, which is a property of the host running the test -- so the test measures that
# before it relies on it.
UNREACHABLE_NETS = ("192.0.2.%d", "198.51.100.%d", "203.0.113.%d")
# How many addresses those ranges give this test. The last octet stays inside a single subnet on
# purpose: what makes an address slow is that nothing routes to it, and that is a property of the
# range rather than of the number.
UNREACHABLE_ADDRESSES = 250


def _unreachable():
    """A UNC path in a range nothing is assigned in -- a DIFFERENT one every time it is asked.

    THE ADDRESS HAS TO BE ONE NOTHING ASKED ABOUT A MOMENT AGO: Windows remembers for a while that
    a host did not answer -- measured 2026-08-05 on this host, one address costs 42.18 s cold,
    0.00 s when asked again immediately, and 42.15 s again a minute and a half later, while a
    neighbour in the same range is cold throughout. A test that hands its subject an address some
    earlier run has already asked about measures that memory instead of the gate; the cut that
    stood here derived the address from the process id modulo 120, and a suite that starts a
    hundred processes puts the next run within reach of the same number. Drawn at random out of
    750, a repeat inside the window the measurement above shows is not a shape this host produces.
    """
    net = random.choice(UNREACHABLE_NETS)
    return "\\\\%s\\share\\f" % (net % random.randrange(2, UNREACHABLE_ADDRESSES))


def _cost_of_asking_about(path):
    """What this host charges for ONE filesystem question about `path`."""
    started = time.monotonic()
    try:
        os.stat(path)
    except OSError:
        pass
    return time.monotonic() - started


@pytest.fixture(scope="session")
def unreachable_cost():
    """What one question about an unroutable host costs here -- measured ONCE for the session.

    Once, because the address is spent by asking: the operating system remembers for a while that
    it did not answer, so this one is sacrificed to the measurement and every subject takes a fresh
    one (`_unreachable`).
    """
    return _cost_of_asking_about(_unreachable())


# How often a cost is sampled, and what is taken. THE WORST OF SEVERAL, because these numbers are
# what a later assertion is measured against: a run that happened to be fast produces a deadline
# the next run cannot keep, which is a test that fails for the machine's mood rather than for the
# gate. Measured 2026-08-05 on this host, single samples of the two runs below: 0.48 s to 0.87 s
# for a gate that answers at once, 0.67 s to 1.26 s for a whole verdict.
SAMPLES = 3


def _samples_of(sample):
    return [sample() for _ in range(SAMPLES)]


def _worst_of(sample):
    return max(_samples_of(sample))


# How long a gate process needs here before it can answer ANYTHING -- the interpreter start, the
# imports, the payload. Measured through a run that asks the filesystem nothing at all, because
# that is the floor no implementation can go below on this host; a call the gate ALLOWS is not that
# floor, it is the full price of a verdict, and comparing IT against a short registration is what
# made this test skip itself on a busy machine (measured 2026-08-05: 1.12 s against a 1 s
# registration, "no implementation could answer inside", while the gate answers such a call in
# 0.52 s).
def _cost_of_a_gate_that_answers_at_once(project, tmp_path):
    """`(the worst of the samples, the spread between them)`. The spread is this host's own timing
    noise, and it is what decides whether a margin below it can be measured at all."""
    work = str(tmp_path / "bare-cost")
    shutil.copytree(project, work)
    _set_registered_timeout(work, None)

    def once():
        started = time.monotonic()
        rc, _err = run(work, "gate_lead_write_scope.py", write_payload(work, "docs/note.md"))
        assert rc == 2, "the run that measures this host's floor was not the refusal it should be"
        return time.monotonic() - started

    taken = _samples_of(once)
    return max(taken), max(taken) - min(taken)


def _cost_of_one_gate_run(project):
    """What a WHOLE verdict costs here: a call this gate allows, walked to the end. It is the
    quantity a budget has to cover, and it is not the floor above."""
    def once():
        started = time.monotonic()
        run(project, "gate_lead_write_scope.py", write_payload(project, "docs/note.md"))
        return time.monotonic() - started

    return _worst_of(once)


def _register_another_group(work, script, matcher, seconds):
    """Add a SECOND registration of `script` to a copy, under `matcher`, with its own deadline."""
    path = os.path.join(work, ".claude", "settings.json")
    with open(path, encoding="utf-8") as handle:
        settings = json.load(handle)
    event = next(iter(settings["hooks"]))
    settings["hooks"][event].append({
        "matcher": matcher,
        "hooks": [{"type": "command", "timeout": seconds,
                   "command": 'python -B "${CLAUDE_PROJECT_DIR}/.claude/hooks/%s"' % script}]})
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)


def _set_registered_timeout(work, seconds):
    """Rewrite the deadline every hook entry of a COPY states -- or take it away (`None`)."""
    path = os.path.join(work, ".claude", "settings.json")
    with open(path, encoding="utf-8") as handle:
        settings = json.load(handle)
    for groups in settings["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                if seconds is None:
                    hook.pop("timeout", None)
                else:
                    hook["timeout"] = seconds
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)


def _reserve_numbers():
    """The two numbers `_harness` reserves time by -- read from it, never copied into this file."""
    sys.path.insert(0, HOOKS)
    import _harness
    return _harness._SPENDABLE_SHARE, _harness._RESERVE_FLOOR


def _registrations(project, tmp_path):
    """The deadline this test writes into a copy -- DERIVED from what a run costs here.

    `(long, why)`: the registration under which an ordinary verdict still fits in the budget, which
    is what the counter-ends below need. A typed number measures nothing on a machine that is
    faster or slower than the one it was typed on.
    """
    verdict = _cost_of_one_gate_run(project)
    share, floor = _reserve_numbers()
    longer = next((seconds for seconds in range(1, 600)
                   if seconds - max(seconds * (1 - share), floor) >= 2 * verdict), None)
    return longer, ("a whole verdict costs %.2fs here, against a share of %.2f and a floor of "
                    "%.2fs" % (verdict, share, floor))


def _floor_case(bare, share, floor):
    """`(registration, the process start that shows the FLOOR is what keeps it)`, or None.

    THE BAND, AND WHY THERE IS ONE. A gate that kept only the SHARE sets its deadline
    `seconds * share` after its own first line and answers `bare + seconds * share` after the
    provider started it, which is past `seconds` exactly when `bare > seconds * (1 - share)`. A gate
    that keeps the floor answers `min(seconds, reserve)` after its start, which is inside the
    registration when `bare < min(seconds, reserve)`. Both together are a band of process starts,
    and its upper end is the floor itself -- so a host whose own start is past the floor cannot show
    the property at all, and neither can one that is far below the band.

    THAT IS WHY `bare` IS CONTROLLED HERE INSTEAD OF HOPED FOR (`_slowed`): measured under load
    2026-08-05 a bare start of 4.76s against a floor of 1.50s, and idle on this host 0.13s -- the
    test went red for the machine's speed in BOTH directions while the gate was untouched. The
    margin on both sides is maximised rather than hoped for.
    """
    best, margin = None, 0.0
    for seconds in range(1, 60):
        reserve = max(seconds * (1.0 - share), floor)
        low, high = seconds * (1.0 - share), min(float(seconds), reserve)
        want = (low + high) / 2.0
        if high <= low or want < bare or min(high - want, want - low) <= margin:
            continue
        best, margin = (seconds, want), min(high - want, want - low)
    return best and (best[0], best[1], margin)


def _slowed(project, tmp_path, name, seconds):
    """A copy whose gate processes need `seconds` longer BEFORE `_harness` starts its own clock.

    THE ONE QUANTITY IN THIS PROBLEM A PROCESS CANNOT SEE is what happened before its first line,
    and it is the quantity the reserve exists for. Making it a CONTROLLED variable is what stops
    this test from measuring the machine: the sleep goes immediately in front of `_LOADED_AT`, which
    is by definition the part of the start the gate cannot measure, and the line it goes in front of
    is found in the module's syntax tree rather than by matching text -- so a `_harness` that starts
    its clock somewhere else fails this instead of silently sleeping in the wrong place.
    """
    work = str(tmp_path / name)
    shutil.copytree(project, work)
    path = os.path.join(work, ".claude", "hooks", "_harness.py")
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines(True)
    starts = [node.lineno for node in ast.parse("".join(lines)).body
              if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == "_LOADED_AT"
                      for target in node.targets)]
    assert len(starts) == 1, (
        "`_harness` no longer starts its clock in exactly one place (%s), so the part of the "
        "process start this test controls could not be placed" % (starts,))
    lines.insert(starts[0] - 1, "import time as _before; _before.sleep(%r)\n" % (seconds,))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("".join(lines))
    return work


def _without_the_floor(work):
    """The same copy with the reserve reduced to its SHARE -- the counter-end of the floor.

    Appended rather than patched into the text: what is asserted is the NUMBER the module ends up
    with, so a rename raises inside the gate and `guarded()` turns that into a refusal the
    assertions below see as "not the reason expected", never into a quiet pass.
    """
    path = os.path.join(work, ".claude", "hooks", "_harness.py")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n_RESERVE_FLOOR = 0.0\n")
    return work


def _refused_for_the_deadline(work, seconds):
    """Run the gate on a candidate this host cannot answer about, and time it.

    THE ADDRESS IS FRESH AND IT IS TRIED AGAIN IF IT WAS NOT SLOW: an address the operating system
    still remembers costs nothing, and a run against one would report that memory as a verdict. A
    host that hands out three cold addresses in a row and is fast about all of them is a host this
    property cannot be measured on, and the caller says so instead of passing.
    """
    for _ in range(3):
        started = time.monotonic()
        rc, err = run(work, "gate_lead_write_scope.py",
                      bash_payload(work, 'sed -i "s/a/b/" "%s"' % _unreachable()))
        elapsed = time.monotonic() - started
        if rc == 2 and "registration allows" in err:
            return rc, err, elapsed
        if elapsed > seconds:
            return rc, err, elapsed
    return rc, err, elapsed


def test_gate1_answers_before_its_registration_gives_up(project, tmp_path, unreachable_cost):
    """A candidate must not be able to decide the call by taking longer than the provider waits.

    A hook still deciding when its timeout expires is killed, and the provider reads a kill the
    way it reads a crash -- "hook error, carry on", i.e. an ALLOW. Measured 2026-08-05 against
    gate 1's registered 120 s: one candidate on an unroutable host cost 21.6 s, three 85.0 s and
    five 211.3 s -- the last rc 0 with no stderr at all, so the write was never judged.

    THE DEADLINE IS READ FROM THE REGISTRATION, so this moves the registration and expects the gate
    to follow: the copy states a short one, and the verdict has to be out before it. Both
    counter-ends in the same run, because a gate that just refused everything after the change
    would satisfy the first assertion -- under the SAME deadline a protected path is still refused
    for being protected, and a free one is still allowed.

    THE RESERVE IS THE LARGER OF A SHARE AND A FLOOR, and the floor is measured by CONTROLLING the
    quantity it exists for instead of waiting for the host to have it: a fifth of a short
    registration is smaller than a process start, so a gate keeping only the share plans past the
    moment it is killed. `_slowed` puts a known start in front of `_harness`'s own clock,
    `_floor_case` picks the registration that shows the difference with the widest margin on both
    sides, and `_without_the_floor` is the counter-end -- the SAME copy with the floor taken away
    has to MISS the deadline, or the floor is decorating.

    NOTHING HERE SKIPS, AND NOTHING HERE FAILS FOR THE MACHINE'S SPEED. A host that cannot show the
    property -- because it answers about an unroutable address at once, or because a gate process
    costs more before its first line than the floor itself -- has not measured the gate, and this
    says so as a failure that names what stopped it. The number that would have to change in the
    second case is `_harness._RESERVE_FLOOR`, not anything in this file.
    """
    longer, measured = _registrations(project, tmp_path)
    assert longer, ("no registration on this host leaves room for an ordinary verdict: %s"
                    % measured)
    assert unreachable_cost > longer, (
        "this host answers about an unroutable host in %.2fs, so a %ds registration is never at "
        "stake and nothing about the deadline was measured here"
        % (unreachable_cost, longer))
    work = str(tmp_path / "deadline-long")
    shutil.copytree(project, work)
    _set_registered_timeout(work, longer)
    rc, err, elapsed = _refused_for_the_deadline(work, longer)
    assert rc == 2, "a candidate this host cannot answer about was waved through: rc=%d" % rc
    assert "registration allows" in err, "refused, but not for the deadline: %s" % err[:300]
    assert elapsed < longer, (
        "the gate answered after %.2fs while its registration gives it %ds -- the provider would "
        "have killed it, and a killed hook is an allow (%s)" % (elapsed, longer, measured))
    assert run(work, "gate_lead_write_scope.py",
               write_payload(work, "team-kits/kernel/state.py"))[0] == 2, (
        "under a deadline it can keep, the gate stopped protecting anything")
    assert run(work, "gate_lead_write_scope.py", write_payload(work, "docs/note.md"))[0] == 0, (
        "under a deadline it can keep, the gate turned into one that refuses everything")

    bare, noise = _cost_of_a_gate_that_answers_at_once(project, tmp_path)
    share, floor = _reserve_numbers()
    case = _floor_case(bare, share, floor)
    assert case, (
        "a gate process here needs %.2fs before its own first line, and the reserve's floor is "
        "%.2fs -- past the floor there is no registration under which the floor can keep the "
        "deadline either, so nothing about it was measured. What has to change is "
        "`_harness._RESERVE_FLOOR`, not this test." % (bare, floor))
    seconds, wanted, margin = case
    assert margin > noise, (
        "the widest band this host offers is %.2fs wide on either side, and this host's own timing "
        "noise over %d runs of the same gate is %.2fs -- a difference under the noise is not a "
        "measurement, so nothing about the floor was shown here" % (margin, SAMPLES, noise))
    keeps = _slowed(project, tmp_path, "deadline-floor", wanted - bare)
    _set_registered_timeout(keeps, seconds)
    rc, err, elapsed = _refused_for_the_deadline(keeps, seconds)
    assert rc == 2 and "registration allows" in err, (
        "with a start of %.2fs in front of it the gate did not refuse for its deadline: rc=%d %s"
        % (wanted, rc, err[:300]))
    assert elapsed < seconds, (
        "the gate answered after %.2fs while its registration gives it %ds, with %.2fs of that "
        "spent before its own first line" % (elapsed, seconds, wanted))
    misses = _without_the_floor(_slowed(project, tmp_path, "deadline-share-only", wanted - bare))
    _set_registered_timeout(misses, seconds)
    _rc, _err, without = _refused_for_the_deadline(misses, seconds)
    assert without > seconds, (
        "with the reserve cut down to its share the same gate still answered inside %ds (%.2fs), "
        "so this run did not measure the floor at all (%s, start %.2fs)"
        % (seconds, without, measured, wanted))


def _a_line_too_long_to_read_in(harness, seconds):
    """A command line whose READING alone costs more than `seconds`, sized by measuring the growth.

    NOT A TYPED SIZE. What reading a substitution costs grows faster than the text is long, and by
    how much is a property of this host -- so two small samples are taken through the function that
    runs, the exponent between them is read off, and the size is computed from it. A host on which
    the cost does not grow at all is one this property cannot be shown on, and the caller is told
    rather than passed.

    The line is a substitution opener repeated, with one closer: that is the shape whose readings
    `_harness._closings` multiplies (both endings, then recursion), and it is the shape the chain
    behind H35 was measured with.
    """
    def line(count):
        return "echo " + "$(" * count + ")"

    def cost(count):
        started = time.monotonic()
        harness.substituted_lines(line(count), "Bash")
        return max(time.monotonic() - started, 1e-6)

    base = 64
    small, large = cost(base), cost(2 * base)
    growth = math.log(large / small, 2) if large > small else 0.0
    assert growth > 1.0, (
        "reading %d openers costs %.4fs here and reading %d costs %.4fs, so the cost does not grow "
        "with the line at all and no length reaches a deadline" % (base, small, 2 * base, large))
    return line(int(2 * base * (2.0 * seconds / large) ** (1.0 / growth)) + 1)


def test_gate1_answers_before_its_registration_however_long_the_line_takes_to_read(project,
                                                                                   tmp_path):
    """A line must not be able to decide the call by costing more to READ than the provider waits.

    THE BOUND HAS TO SIT OUTSIDE THE READING, and that is what this measures. `substituted_lines`
    checked the budget once per CALL and said in its own docstring that it was bounded by it; the
    cost is inside a call, so the check could not fire. Measured 2026-08-07, one tool call and no
    preparation: 2444 characters of command line -- a `sed -i` on a kit file with the openers behind
    a `#` -- were rc 2 only after 150.6 s against gate 1's registered 120, and bash really rewrote
    the file. Past the registration the hook is killed, and a killed hook is an ALLOW
    (`docs/POST_V2_WISHLIST.md` H35).

    THE SIZE IS DERIVED FROM THE HOST (`_a_line_too_long_to_read_in`) and the registration from what
    a verdict costs here (`_registrations`), so nothing in this test is a number typed on the
    machine it was written on.

    BOTH ENDS, under the SAME registration: a gate that answered "too slow" to everything would pass
    the first half, so a protected path still has to be refused for being protected and a free one
    still allowed.
    """
    harness = _reader()
    seconds, measured = _registrations(project, tmp_path)
    assert seconds, ("no registration on this host leaves room for an ordinary verdict: %s"
                     % measured)
    work = str(tmp_path / "deadline-reading")
    shutil.copytree(project, work)
    _set_registered_timeout(work, seconds)
    # THE LINE IS BUILT BEFORE THE CLOCK STARTS (BUG-0243), for the reason its gate-3 twin below
    # carries with the measurement: sizing reads the clock itself, and work no gate process ever
    # does must not be charged to the gate's registration. Held by
    # `test_no_timed_span_here_pays_for_a_helper_that_reads_the_clock_itself`.
    payload = bash_payload(work, _a_line_too_long_to_read_in(harness, seconds))
    started = time.monotonic()
    rc, err = run(work, "gate_lead_write_scope.py", payload)
    elapsed = time.monotonic() - started
    assert rc == 2, (
        "a line this gate could not read inside its budget was waved through: rc=%d after %.2fs"
        % (rc, elapsed))
    assert "registration allows" in err, (
        "refused after %.2fs, but not for the deadline -- so the line was cheap enough to read and "
        "nothing about the budget was measured: %s" % (elapsed, err[:300]))
    assert elapsed < seconds, (
        "the gate answered after %.2fs while its registration gives it %ds -- the provider would "
        "have killed it, and a killed hook is an allow (%s)" % (elapsed, seconds, measured))
    assert run(work, "gate_lead_write_scope.py",
               write_payload(work, "team-kits/kernel/state.py"))[0] == 2, (
        "under the same registration the gate stopped protecting anything")
    assert run(work, "gate_lead_write_scope.py", write_payload(work, "docs/note.md"))[0] == 0, (
        "under the same registration the gate turned into one that refuses everything")


CLOCK_MODULE = "time"


def _clock_names(tree):
    """`(the module names, the bare names)` this source reaches the clock through -- its IMPORTS.

    THE NAMES COME FROM THE FILE AND NOT FROM A PREFIX, and that correction is the verifier's F1 of
    round 1: the reader below asked for `time.<something>` while its docstring claimed a
    definition, so a source writing `from time import monotonic` or `import time as clock` was read
    as carrying no clock at all -- measured end to end, the H161 defect restored in the first of
    those spellings left this check GREEN while the same defect spelled `time.x` was red. An
    import statement is where a source says how it reaches a module, so that is where this asks.

    BOTH SHAPES, because both reach the same clock: `import time [as x]` binds a MODULE (an
    attribute of it is the reading), `from time import y [as z]` binds the reading directly.
    """
    modules, bare = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == CLOCK_MODULE or alias.name.startswith(CLOCK_MODULE + "."):
                    modules.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module == CLOCK_MODULE:
            for alias in node.names:
                bare.add(alias.asname or alias.name)
    return modules, bare


def _reads_the_clock(node, clock):
    """Is this expression a reading of the clock, under the names this source imports it by?"""
    modules, bare = clock
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id in modules
    if isinstance(node, ast.Name):
        return node.id in bare
    return False


def _touches_the_clock(name, defined, clock, seen=None):
    """Does this file's function `name` reach the clock -- itself or through a call?

    A DEFINITION AND NOT A LIST OF CLOCK FUNCTIONS: anything in `time` is about time, so a helper
    that reaches that module at all has a cost or a behaviour the clock decides. Naming
    `monotonic` and `perf_counter` instead would be an enumeration that goes silent the day a
    helper sizes itself with a third one -- and the NAMES the module is reached by come off the
    source's own imports (`_clock_names`), so the three spellings a file can use are one question.
    The question is asked transitively, because the defect this reads for hides one call deep --
    the sizing helper reads the clock in a nested function.
    """
    seen = set() if seen is None else seen
    if name in seen or name not in defined:
        return False
    seen.add(name)
    node = defined[name]
    for inner in ast.walk(node):
        if _reads_the_clock(inner, clock):
            return True
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) \
                and _touches_the_clock(inner.func.id, defined, clock, seen):
            return True
    return False


def _spans_that_pay_for_a_clock_reading(source):
    """Every measured span in `source` that calls a helper of the same file which reads the clock.

    A SPAN IS FOUND BY ITS SHAPE, not by the name of the test that holds it: a statement binds a
    clock reading to a name, a later statement in the SAME block subtracts that name from a second
    reading. That is what a measurement looks like in this file and in any other, so a test that
    starts timing something tomorrow is read without being added anywhere.

    WHAT IT REPORTS: the helpers called BETWEEN the two readings that reach into `time` themselves.
    Their own cost lands in a quantity whose name says it is the subject's -- and a quantity that
    is not what its name says is not made honest by a wider margin (BUG-0033's measurement on the
    gate-3 twin, BUG-0243 on the gate-1 one).
    """
    tree = ast.parse(source)
    clock = _clock_names(tree)
    defined = {node.name: node for node in tree.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    found = []
    for holder in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(holder, field, None)
            if not isinstance(block, list) or not block or not isinstance(block[0], ast.stmt):
                continue
            for opened, statement in enumerate(block):
                started = _name_bound_to_a_clock_reading(statement, clock)
                if started is None:
                    continue
                closed = _statement_that_closes_the_span(block, opened, started, clock)
                if closed is None:
                    continue
                for between in block[opened + 1:closed]:
                    for call in ast.walk(between):
                        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                            continue
                        if _touches_the_clock(call.func.id, defined, clock):
                            found.append("line %d: the span opened at line %d calls `%s`, which "
                                         "reads the clock itself"
                                         % (between.lineno, statement.lineno, call.func.id))
    return sorted(set(found))


def _name_bound_to_a_clock_reading(statement, clock):
    """`x` for `x = <a clock reading>()`, else None -- the statement that OPENS a measured span.

    WHICH CALLS ARE READINGS is `_clock_names`' answer and not a prefix, for the reason that
    function carries.
    """
    if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
        return None
    target, value = statement.targets[0], statement.value
    if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
        return None
    return target.id if _reads_the_clock(value.func, clock) else None


def _statement_that_closes_the_span(block, opened, started, clock):
    """The index of the statement that subtracts `started` from a second clock reading, or None."""
    for index in range(opened + 1, len(block)):
        for node in ast.walk(block[index]):
            if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Sub):
                continue
            if not isinstance(node.right, ast.Name) or node.right.id != started:
                continue
            if isinstance(node.left, ast.Call) and _reads_the_clock(node.left.func, clock):
                return index
    return None


def test_no_timed_span_here_pays_for_a_helper_that_reads_the_clock_itself():
    """BUG-0243 / H161: a test that times a gate must not build its own probe inside the span it
    measures -- the sizing reads the clock, and its cost is then charged to the subject.

    THE OCCASION IS MEASURED ON THE TWIN: the gate-3 deadline test built its line inside the span
    and ran 4.54-4.62 s against a 4.50 s registration on this host, while the same gate answered in
    3.26-3.31 s with the line built outside (BUG-0033). The gate-1 sibling kept the same shape at a
    tenth of the price, which is a defect that has not fired yet rather than one that is absent --
    a number this small is a property of today's sizing helper, not of the form.

    BOTH ENDS, AND NEITHER OF THEM IS THIS FILE'S GREEN STATE: the reader is driven over a source
    that carries the defect and has to report it, and over one that does not and has to stay
    silent -- so a reader that stopped finding spans fails here instead of passing an empty sweep.

    EVERY SPELLING A SOURCE CAN IMPORT THE CLOCK BY, and that is the verifier's F1 of round 1: the
    reader asked for `time.<x>` and its docstring promised a definition, so the same defect written
    with `from time import monotonic` came back GREEN. The three shapes are driven below, and the
    reader reads the names off the source's own import statements (`_clock_names`).
    """
    spellings = {
        "the module, imported plainly": ("import time", "time.monotonic"),
        "the module under another name": ("import time as clock", "clock.monotonic"),
        "the reading imported by name": ("from time import monotonic", "monotonic"),
    }
    for label, (imported, reading) in sorted(spellings.items()):
        defect = textwrap.dedent('''
            %s

            def _size():
                begin = %s()
                return %s() - begin

            def test_subject():
                started = %s()
                rc = run(_size())
                elapsed = %s() - started
        ''' % (imported, reading, reading, reading, reading))
        assert _measured_spans_in(defect) == 2, (
            "the reader finds %d measured spans where the clock is reached %s, and there are two"
            % (_measured_spans_in(defect), label))
        assert _spans_that_pay_for_a_clock_reading(defect), (
            "the reader is silent on a span that calls a clock-reading helper between its two "
            "readings when the clock is reached %s, so the defect could hide in that spelling"
            % label)
        assert not _spans_that_pay_for_a_clock_reading(
            defect.replace("rc = run(_size())", "rc = run(built)")), (
            "the reader reports a span that calls nothing timing at all (%s), so every timed test "
            "here would be red for the shape rather than for the defect" % label)
    with open(os.path.join(HOOKS, THIS_FILE), encoding="utf-8") as handle:
        source = handle.read()
    assert _measured_spans_in(source) >= 2, (
        "this file holds fewer than two measured spans, so the sweep below has nothing to be "
        "about -- the reader's shape and the file have drifted apart")
    paying = _spans_that_pay_for_a_clock_reading(source)
    assert not paying, (
        "these measured spans charge the subject for work no gate process does:\n%s"
        % "\n".join(paying))


def _measured_spans_in(source):
    """How many measured spans `source` holds -- the count that keeps the sweep from being empty."""
    tree, spans = ast.parse(source), 0
    clock = _clock_names(tree)
    for holder in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(holder, field, None)
            if not isinstance(block, list) or not block or not isinstance(block[0], ast.stmt):
                continue
            for opened, statement in enumerate(block):
                started = _name_bound_to_a_clock_reading(statement, clock)
                if started is not None and _statement_that_closes_the_span(
                        block, opened, started, clock) is not None:
                    spans += 1
    return spans


def test_gate1_answers_before_the_shortest_registration_that_applies(project, tmp_path,
                                                                     unreachable_cost):
    """Which registrations apply to a call is the PROVIDER's reading of the matcher, not a split.

    A matcher was read here as an alternation of tool names. The provider reads it as an
    expression, so a group whose matcher is one (`Ba.h`) applied to a call that this gate did not
    count -- and when that group states the SHORTER deadline, the gate plans with the longer one
    and is killed, which the provider reads as an allow. Measured 2026-08-05: registered 60 s
    literally and 5 s under an expression, the gate answered rc 0 after 43.1 s, eight times past
    the entry that applied; reading the matcher as the provider does, rc 2 after 4.1 s.

    THE COUNTER-END IS A REGISTRATION THAT DOES NOT APPLY, and it is what stops "just take the
    smallest number in the file": a group naming a tool that never fires states 1 s here, and an
    ordinary call still has to be judged rather than refused for a deadline that was never its own.
    """
    longer, measured = _registrations(project, tmp_path)
    seconds = longer
    assert unreachable_cost > seconds, (
        "this host answers about an unroutable host in %.2fs, so a %ds registration is never at "
        "stake and nothing about the matcher was measured here (%s)"
        % (unreachable_cost, seconds, measured))
    work = str(tmp_path / "matcher-expression")
    shutil.copytree(project, work)
    _set_registered_timeout(work, int(unreachable_cost) + 60)
    _register_another_group(work, "gate_lead_write_scope.py", "Ba.h", seconds)
    rc, err, elapsed = _refused_for_the_deadline(work, seconds)
    assert rc == 2 and "registration allows" in err, (
        "the call was not refused for the deadline: rc=%d %s" % (rc, err[:300]))
    assert elapsed < seconds, (
        "the gate answered after %.2fs while a registration that matches this call gives it %ds"
        % (elapsed, seconds))
    other = str(tmp_path / "matcher-that-never-fires")
    shutil.copytree(project, other)
    _set_registered_timeout(other, 60)
    _register_another_group(other, "gate_lead_write_scope.py", "NeverFires", 1)
    assert run(other, "gate_lead_write_scope.py", write_payload(other, "docs/note.md"))[0] == 0, (
        "a registration for a tool this call is not made with decided the deadline anyway")


def test_a_gate_whose_registration_states_no_deadline_refuses(project, tmp_path):
    """The fail-closed half, and the reason every entry has to state one.

    A gate that cannot read its own deadline cannot promise to answer before it, and the direction
    that costs nothing to be wrong in is the refusal. The subject is a call this gate normally
    ALLOWS, so nothing except the missing deadline can be what refused it.
    """
    work = str(tmp_path / "no-deadline")
    shutil.copytree(project, work)
    _set_registered_timeout(work, None)
    rc, err = run(work, "gate_lead_write_scope.py", write_payload(work, "docs/note.md"))
    assert rc == 2, "a gate that cannot know its deadline judged the call anyway"
    assert "timeout" in err, "refused, but not for the missing deadline: %s" % err[:300]


def test_every_registered_hook_states_the_time_it_gets():
    """Read off the registration, which is the file both the provider and the gate read.

    `_harness.Deadline` refuses when it finds no `timeout` for the call it is judging, so an entry
    added without one does not degrade quietly -- it stops every call of that event. This is the
    tripwire that says so before a session finds out.
    """
    with open(os.path.join(ROOT, ".claude", "settings.json"), encoding="utf-8") as handle:
        settings = json.load(handle)
    entries = [hook for groups in settings["hooks"].values() for group in groups
               for hook in group["hooks"]]
    assert entries, "this repo registers no hooks at all"
    for hook in entries:
        assert isinstance(hook.get("timeout"), (int, float)), (
            "%r states no `timeout`, so the gate it starts cannot know when it will be killed"
            % hook.get("command"))


# -- which direction a candidate meets an area from (TSK-0011 F6) --------------


def test_gate1_says_whether_a_path_is_an_area_or_merely_holds_one(project):
    """A refusal that cannot tell the two apart says something false about one of them.

    The containment test answers yes in both directions -- and it must, or `rm -rf team-kits` would
    read as an unrelated path. The reason behind it, though, described the AREA while claiming it
    of the CANDIDATE: measured 2026-08-05, `cp -r docs C:/` was refused with the words "this is
    canonical project state", about a drive letter.

    Both ends, because a note glued onto every refusal would pass the first assertion alone.
    """
    holds = run(project, "gate_lead_write_scope.py", bash_payload(project, "cp -r docs .."))
    assert holds[0] == 2, "a copy whose target holds the whole repo was allowed"
    assert "stands UNDER it" in holds[1], (
        "a candidate that only CONTAINS the protected area was refused as though it were it: %s"
        % holds[1][:300])
    inside = run(project, "gate_lead_write_scope.py",
                 bash_payload(project, 'sed -i "s/a/b/" project_memory/README.md'))
    assert inside[0] == 2, "a write into canonical state was allowed"
    assert "canonical project state" in inside[1]
    assert "stands UNDER it" not in inside[1], (
        "a write INTO canonical state was described as if it merely contained it: %s"
        % inside[1][:300])


# -- what a kit is, asked of the kernel (TSK-0011 F8) --------------------------


def test_the_kit_these_gates_read_is_the_one_the_kernel_calls_a_kit(project, tmp_path):
    """`_kit_hooks_dir` asks `kernel.hashing.is_kit_dir`; it used to spell the predicate out again.

    A COPIED PREDICATE IS MEASURED BY MAKING THE TWO DISAGREE: this clone teaches the kernel a
    different marker for "this directory is a kit" and plants a directory that satisfies only the
    new one. The gates have to follow the kernel; a second opinion kept here answers with the old
    kit and turns this red.

    THE KERNEL IS TAUGHT BY APPENDING TO IT, not by asserting how its predicate is spelled: a test
    that pins a line of `team-kits/**` goes red for an edit that has nothing to do with it, and
    that tree is forbidden ground for the task this file belongs to. The redefinition below is the
    last one the module makes, so it is the one the gates see -- and if the name it replaces ever
    disappears, nothing calls it any more and the assertion below fails rather than passing on a
    prediction nobody checked.
    """
    work = str(tmp_path / "kit-predicate")
    shutil.copytree(project, work)
    hashing = os.path.join(work, "team-kits", "kernel", "hashing.py")
    with open(hashing, "a", encoding="utf-8") as handle:
        handle.write("\n\ndef is_kit_dir(path):\n"
                     "    return os.path.isdir(os.path.join(path, 'roles'))\n")
    planted = os.path.join(work, "team-kits", "aaa-kit")
    os.makedirs(os.path.join(planted, "roles"))
    os.makedirs(os.path.join(planted, "hooks"))
    with open(os.path.join(planted, "hooks", "_compat.py"), "w", encoding="utf-8") as handle:
        handle.write("")
    code = ("import os, sys\n"
            "sys.path.insert(0, os.path.join(sys.argv[1], '.claude', 'hooks'))\n"
            "import _harness\n"
            "print(_harness._kit_hooks_dir(sys.argv[1]))\n")
    done = subprocess.run([sys.executable, "-B", "-c", code, work], cwd=work,
                          capture_output=True, text=True,
                          env=dict(os.environ, CLAUDE_PROJECT_DIR=work))
    assert done.returncode == 0, done.stderr[-600:]
    assert done.stdout.strip() == os.path.join(planted, "hooks"), (
        "the gates read %r as the kit while the kernel calls only %r one"
        % (done.stdout.strip(), os.path.join(planted, "hooks")))


# -- no recording of history without a verdict (TSK-0056 / BUG-0034, SR-0009 clause 3) ----------
#
# Gate 3's subject stopped being the WORD `commit` this round. Two things are measured below and
# they are different subjects: the CLASSIFICATION, against the installed git in real repositories
# (this is the tripwire the gate's enumeration owes -- see
# `docs/reviews/2026-08-13-tsk0056-history-recording-design.md`, section 7), and the REFUSALS, as
# real hook processes against a stand-in project whose tree already carries a passing verdict.
#
# THE VERDICT IN THE TREE IS WHAT MAKES THE REFUSAL TESTS MEASURE THIS ROUND AT ALL. Without one,
# every line below is rc 2 for the OLD reason ("this working tree carries no passing Evidence") and
# the whole block would be green against the very defect it exists for.


def _gate3():
    """Gate 3 as a MODULE, so every table below is the one the running gate decides with.

    Imported rather than read as text: a test that searches the file for a subcommand name is
    satisfied by a comment, and what this round is about is what the gate DOES with a verb.
    """
    sys.path.insert(0, HOOKS)
    import gate_commit_evidence
    return gate_commit_evidence


def _git_in(work, *arguments, **keywords):
    """git in `work`, with the identity a fresh repo has to be given, and with stdin CLOSED.

    Closed stdin is not tidiness. `git fast-import` and `git quiltimport` READ it, and a scenario
    that inherits this process's stdin waits for input instead of measuring anything -- measured
    while this table was built, the first run of it hung past 120 s.
    """
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "user.email=t@t.t", "-c", "user.name=t",
         "-c", "protocol.file.allow=always"] + list(arguments),
        cwd=work, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120,
        **keywords)


def _commit_objects(work):
    """Every commit OBJECT in this repo -- not the reachable ones, and that is the whole point.

    `git stash`, `git commit-tree` and `git replay` author commits no branch reaches, and telling
    those apart from the commands that author nothing at all is exactly what the gate's two halves
    rest on.
    """
    done = subprocess.run(["git", "cat-file", "--batch-all-objects",
                           "--batch-check=%(objectname) %(objecttype)"],
                          cwd=work, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                          timeout=120)
    return {line.split()[0] for line in done.stdout.splitlines()
            if line.split()[1:2] == ["commit"]}


def _two_sided_repo(base, name):
    """A fresh repo where `main` and `other` have diverged by one commit each."""
    work = os.path.join(base, name)
    os.makedirs(work)
    _git_in(work, "init", "-q", "-b", "main", ".")
    with open(os.path.join(work, "a.txt"), "w", encoding="utf-8") as handle:
        handle.write("base\n")
    _git_in(work, "add", "-A")
    _git_in(work, "commit", "-qm", "base")
    _git_in(work, "branch", "other")
    with open(os.path.join(work, "b.txt"), "w", encoding="utf-8") as handle:
        handle.write("main side\n")
    _git_in(work, "add", "-A")
    _git_in(work, "commit", "-qm", "main side")
    _git_in(work, "checkout", "-q", "other")
    with open(os.path.join(work, "c.txt"), "w", encoding="utf-8") as handle:
        handle.write("other side\n")
    _git_in(work, "add", "-A")
    _git_in(work, "commit", "-qm", "other side")
    _git_in(work, "checkout", "-q", "main")
    return work


def _dirtied(work):
    with open(os.path.join(work, "a.txt"), "a", encoding="utf-8") as handle:
        handle.write("dirty\n")
    return work


def _plain(*arguments):
    return lambda work: _git_in(work, *arguments)


def _staged_commit(work):
    _git_in(_dirtied(work), "add", "-A")
    return _git_in(work, "commit", "-qm", "next")


def _stashed(work):
    return _git_in(_dirtied(work), "stash")


def _mailbox(work):
    with open(os.path.join(work, "patch.mbox"), "w", encoding="utf-8") as handle:
        handle.write(_git_in(work, "format-patch", "-1", "other", "--stdout").stdout)
    return work


def _am(work):
    return _git_in(_mailbox(work), "am", "patch.mbox")


def _am_suppressed(work):
    return _git_in(_mailbox(work), "am", _gate3().SUPPRESSOR, "patch.mbox")


def _applied(work):
    return _git_in(_mailbox(work), "apply", "patch.mbox")


def _with_a_remote(work):
    """A second repository as `origin`, with a history of its own."""
    remote = work + "-remote"
    os.makedirs(remote)
    _git_in(remote, "init", "-q", "-b", "main", ".")
    with open(os.path.join(remote, "r.txt"), "w", encoding="utf-8") as handle:
        handle.write("remote\n")
    _git_in(remote, "add", "-A")
    _git_in(remote, "commit", "-qm", "remote base")
    _git_in(work, "remote", "add", "origin", remote.replace("\\", "/"))
    return work


def _pulled(*extra):
    def scenario(work):
        return _git_in(_with_a_remote(work), "pull", "--no-edit", "--no-rebase",
                       "--allow-unrelated-histories", *(list(extra) + ["origin", "main"]))
    return scenario


def _remote_sharing_base(work):
    """A remote at `work + "-remote"` that shares `work`'s history and then advances by one commit.

    A SHARED ANCESTOR is what a rebase pull needs -- an unrelated remote makes `--rebase` fail
    (measured rc 128), so `_pulled` above uses `--no-rebase --allow-unrelated-histories`, which is
    exactly why it could never exercise the case F2 is about. This one can.
    """
    remote = work + "-remote"
    os.makedirs(remote)
    _git_in(remote, "init", "-q", "-b", "main", ".")
    _git_in(remote, "fetch", work.replace("\\", "/"), "main")
    _git_in(remote, "reset", "--hard", "FETCH_HEAD")
    with open(os.path.join(remote, "r.txt"), "w", encoding="utf-8") as handle:
        handle.write("remote advance\n")
    _git_in(remote, "add", "-A")
    _git_in(remote, "commit", "-qm", "remote advance")
    with open(os.path.join(work, "w.txt"), "w", encoding="utf-8") as handle:
        handle.write("local advance\n")
    _git_in(work, "add", "-A")
    _git_in(work, "commit", "-qm", "local advance")
    _git_in(work, "remote", "add", "origin", remote.replace("\\", "/"))
    _git_in(work, "fetch", "-q", "origin")
    return work


def _pulled_rebase(*extra):
    """`git pull --no-commit <rebase-spelling> origin main` against a diverged shared-base remote.

    The rebase mode of pull authors a commit even WITH `--no-commit` -- measured, and the reason
    `pull` is no longer a produce-first form (F2). The spelling is a parameter so the several ways
    to ask for a rebase (`--rebase`, `-r`, `-c pull.rebase=true`) are each a real invocation and
    not a comment.
    """
    def scenario(work):
        return _git_in(_remote_sharing_base(work), "pull", "--no-commit",
                       *(list(extra) + ["origin", "main"]))
    return scenario


def _pulled_rebase_config(work):
    return _git_in(_remote_sharing_base(work), "-c", "pull.rebase=true", "pull", "--no-commit",
                   "origin", "main")


def _hash_object_commit(work):
    """`git hash-object -t commit -w --stdin` -- the plumbing author F1 exposed.

    BYTE stdin, not text: a commit object's header is parsed strictly, and this host's text mode
    turns each `\\n` into `\\r\\n`, which git rejects as `bad sha1` on the tree line. Measured while
    building this: the text form was rc 128, the byte form authors the object.
    """
    tree = _git_in(work, "rev-parse", "HEAD^{tree}").stdout.strip()
    body = ("tree %s\nauthor a <a@a> 1 +0000\ncommitter a <a@a> 1 +0000\n\nfabricated\n"
            % tree).encode("ascii")
    done = subprocess.run(["git", "hash-object", "-t", "commit", "-w", "--stdin"], cwd=work,
                          input=body, capture_output=True, timeout=120)
    return subprocess.CompletedProcess(done.args, done.returncode, "",
                                       done.stderr.decode("utf-8", "replace"))


def _fetched(work):
    return _git_in(_with_a_remote(work), "fetch", "origin")


def _imported(work):
    """`git fast-import`, whose stream is BYTES on purpose: written as text, this host rewrites
    every newline as CRLF and git answers `Branch name doesn't conform to GIT standards`."""
    head = _git_in(work, "rev-parse", "HEAD").stdout.strip()
    stream = ("commit refs/heads/main\ncommitter t <t@t.t> 1700000000 +0000\n"
              "data 8\nimported\nfrom %s\nM 100644 inline i.txt\ndata 6\nhello\n\n" % head)
    done = subprocess.run(["git", "fast-import", "--quiet"], cwd=work,
                          input=stream.encode("utf-8"), capture_output=True, timeout=120)
    return subprocess.CompletedProcess(done.args, done.returncode, "",
                                       done.stderr.decode("utf-8", "replace"))


# One scenario per subcommand the gate calls an author. THE KEYS ARE THE VERBS, so the comparison
# with `AUTHORS_A_COMMIT` below is an equality and not a reading.
RECORDS_HISTORY = {
    "commit": _staged_commit,
    "merge": _plain("merge", "--no-ff", "--no-edit", "other"),
    "pull": _pulled(),
    "rebase": _plain("rebase", "other"),
    "revert": _plain("revert", "--no-edit", "HEAD"),
    "cherry-pick": _plain("cherry-pick", "other"),
    "am": _am,
    "filter-branch": _plain("filter-branch", "-f", "--msg-filter", "sed s/^/x/", "HEAD~1..HEAD"),
    "subtree": _plain("subtree", "add", "--prefix=sub", ".", "other"),
    "fast-import": _imported,
    "stash": _stashed,
    "commit-tree": _plain("commit-tree", "-m", "x", "HEAD^{tree}"),
    "hash-object": _hash_object_commit,
    "notes": _plain("notes", "add", "-m", "x"),
    "replay": _plain("replay", "--onto", "main", "main..other"),
}

# The other end of the same tripwire: commands that must author NOTHING. Two families, and both
# belong here -- the ordinary path to a commit that AC-2 of BUG-0034 keeps open, and the
# near-misses that move a ref or the working tree without authoring anything.
AUTHORS_NOTHING = {
    "branch": _plain("branch", "newbranch"),
    "checkout": _plain("checkout", "-b", "fresh"),
    "switch": _plain("switch", "-c", "fresh2"),
    "fetch": _fetched,
    "status": _plain("status"),
    "diff": _plain("diff"),
    "add": lambda work: _git_in(_dirtied(work), "add", "-A"),
    "reset": _plain("reset", "--hard", "HEAD~1"),
    "tag": _plain("tag", "-a", "v1", "-m", "x"),
    "backfill": _plain("backfill"),
    "update-ref": _plain("update-ref", "refs/heads/side", "other"),
    "replace": _plain("replace", "HEAD", "HEAD~1"),
    "worktree": _plain("worktree", "add", "../wt", "-b", "wtb"),
    "restore": _plain("restore", "."),
    "apply": _applied,
}

# The produce-first option crossed with the authors it is asked of. Both ends in ONE assertion:
# `rebase`, `am` and `pull` accept the option and record anyway (measured), so an exemption that
# grew to cover them turns this red -- and an exempt verb whose git stopped honouring it turns it
# red too. For `pull` the spelling here is a REBASE pull, which is the F2 case: `--no-commit`
# suppresses pull's merge mode but not its rebase mode, so pull is not a produce-first form and a
# gate that treated it as one would let this line record history.
SUPPRESSED = {
    "merge": _plain("merge", "--no-commit", "--no-ff", "--no-edit", "other"),
    "revert": _plain("revert", "--no-commit", "HEAD"),
    "cherry-pick": _plain("cherry-pick", "--no-commit", "other"),
    "pull": _pulled_rebase("--rebase"),
    "rebase": _plain("rebase", "--no-commit", "other"),
    "am": _am_suppressed,
}

# The rebase pull crossed with the SPELLINGS of "rebase" the option cannot survive. Every one is a
# real invocation measured to author a commit with `--no-commit` present -- so the gate must refuse
# all of them (pull is not in HONOURS_THE_SUPPRESSOR), and a check that only looked at `--no-commit`
# being first would pass them. F2's measured chain.
PULL_REBASE_SPELLINGS = {
    "--rebase": _pulled_rebase("--rebase"),
    "-r": _pulled_rebase("-r"),
    "--rebase=true": _pulled_rebase("--rebase=true"),
    "-c pull.rebase=true": _pulled_rebase_config,
}


def _authored_by(tmp_path, label, scenario):
    """(the finished process, the commit objects the scenario AUTHORED) for one scenario.

    AUTHORED, not merely NEW HERE, and the difference is not pedantry: `git fetch` and `git pull`
    carry objects into this repository that were authored in another one, and the property the gate
    decides on is about the commit a command BUILDS out of the state at hand. Measured with the
    difference ignored, `git fetch origin` counted the remote's own base commit as something it had
    authored -- a scenario that would have put `fetch` into the refused set, i.e. exactly the
    over-refusal AC-2 forbids. So whatever the remote already holds is subtracted; a merge commit
    `git pull` builds is in neither of those sets and still counts.
    """
    work = _two_sided_repo(str(tmp_path), re.sub(r"[^a-z0-9]+", "-", label.lower()))
    before = _commit_objects(work)
    done = scenario(work)
    imported = _commit_objects(work + "-remote") if os.path.isdir(work + "-remote") else set()
    return done, sorted(_commit_objects(work) - before - imported)


# The scenario tables, under the prefix each one's repositories are named with. THE PREFIX IS WHAT
# KEEPS TWO TABLES APART when they name the same verb: `pull` stands in three of them.
AUTHORING_TABLES = {"records-": RECORDS_HISTORY, "nothing-": AUTHORS_NOTHING,
                    "suppressed-": SUPPRESSED, "pull-rebase-": PULL_REBASE_SPELLINGS}


@pytest.fixture(scope="session")
def authored(tmp_path_factory):
    """`{(prefix, key): (the finished process, the commits it authored)}` for every scenario.

    EVERY SCENARIO IS ITS OWN REPOSITORY (`_authored_by`), so they do not depend on each other and
    are measured in one run rather than one after the other -- the same reason the cell phase above
    gives, and the same bound (docs/reviews/2026-08-29-tsk0090-measurements.md, section 5). Each
    test below still asserts about its own verb and fails on its own.

    WHAT KEEPS THEM APART IS THE NAME `_authored_by` SANITISES, so that name has to be unique --
    two scenarios that sanitise to one name would run CONCURRENTLY in one repository and each read
    the other's commits. Run one after the other that was a wrong answer waiting for a collision;
    run at the same time it is one, so the names are counted before anything starts.
    """
    base = str(tmp_path_factory.mktemp("authors"))
    subjects = [(prefix, key) for prefix, table in sorted(AUTHORING_TABLES.items())
                for key in sorted(table)]
    named = [re.sub(r"[^a-z0-9]+", "-", (prefix + key).lower()) for prefix, key in subjects]
    assert len(set(named)) == len(named), (
        "two scenarios sanitise to one repository name, so they would be measured in one tree at "
        "the same time: %s" % sorted(name for name in set(named) if named.count(name) > 1))
    return _in_parallel(
        lambda _slot, subject: _authored_by(
            base, subject[0] + subject[1], AUTHORING_TABLES[subject[0]][subject[1]]),
        subjects, REPOSITORIES)


@pytest.mark.parametrize("verb", sorted(RECORDS_HISTORY))
def test_every_subcommand_the_gate_calls_an_author_authors_one(authored, verb):
    """The dead-entry end of the tripwire: an entry that stops recording says so.

    Driven against the INSTALLED git, in a real repository, because that is the only thing that can
    know. A name kept in the set out of caution, or one git has repurposed, turns this red instead
    of quietly refusing lines for a property it no longer has.
    """
    done, made = authored[("records-", verb)]
    assert done.returncode == 0, "the scenario for `git %s` did not run: %s" % (
        verb, (done.stderr or "")[-400:])
    assert made, (
        "`git %s` is in gate 3's AUTHORS_A_COMMIT and this git authored no commit object for it"
        % verb)
    assert verb in _gate3().AUTHORS_A_COMMIT, (
        "`git %s` is measured to author a commit and the gate does not count it" % verb)


@pytest.mark.parametrize("verb", sorted(AUTHORS_NOTHING))
def test_the_commands_the_gate_leaves_open_author_nothing(authored, verb):
    """The missing-recorder end: a command outside the set that starts authoring says so.

    The invocation has to SUCCEED, or this would measure a command that did nothing at all -- the
    shape of a test that cannot fail.
    """
    done, made = authored[("nothing-", verb)]
    assert done.returncode == 0, "the scenario for `git %s` did not run: %s" % (
        verb, (done.stderr or "")[-400:])
    assert not made, (
        "`git %s` authored %s here and gate 3 does not refuse it -- a commit object can be made "
        "without a verdict" % (verb, made))
    assert verb not in _gate3().AUTHORS_A_COMMIT, (
        "`git %s` is measured to author nothing and is refused as an author anyway" % verb)


@pytest.mark.parametrize("verb", sorted(SUPPRESSED))
def test_the_produce_first_option_is_exempted_exactly_where_it_works(authored, verb):
    """`--no-commit` is honoured by some authors and IGNORED by others, and the gate has to match.

    Measured: `git rebase --no-commit other`, `git am --no-commit patch.mbox` and
    `git pull --no-commit --rebase origin main` all exit 0 and record a commit anyway. An exemption
    that grew to cover them would let a line through that records history, and this cell is what
    says so.
    """
    gate = _gate3()
    done, made = authored[("suppressed-", verb)]
    assert done.returncode == 0, "the scenario for the `%s` produce-first cell did not run: %s" % (
        verb, (done.stderr or "")[-400:])
    assert (not made) == (verb in gate.HONOURS_THE_SUPPRESSOR), (
        "the `%s` produce-first cell authored %s, and the gate %s it as a produce-first form"
        % (verb, made,
           "exempts" if verb in gate.HONOURS_THE_SUPPRESSOR else "does not exempt"))


@pytest.mark.parametrize("spelling", sorted(PULL_REBASE_SPELLINGS))
def test_no_spelling_of_a_rebase_pull_survives_the_suppressor(authored, spelling):
    """F2: `git pull --no-commit` records under every way of asking for a rebase.

    The refined SR-0009 exempts a produce-first form ONLY where the option suppresses recording for
    EVERY spelling and configuration of the same invocation. This measures that pull fails that
    bar -- and it is the tripwire the old `_pulled` (hard-wired to `--no-rebase`) could not be: a
    test that only ever passed `--no-rebase` cannot fail on the case that authors.
    """
    done, made = authored[("pull-rebase-", spelling)]
    assert done.returncode == 0, "the `pull --no-commit %s` scenario did not run: %s" % (
        spelling, (done.stderr or "")[-400:])
    assert made, (
        "`git pull --no-commit %s` authored nothing here, so this host cannot show the case F2 is "
        "about" % spelling)
    assert "pull" not in _gate3().HONOURS_THE_SUPPRESSOR, (
        "pull is exempted as a produce-first form while its --no-commit records under %s" % spelling)


def test_every_author_is_either_demonstrated_or_says_why_it_cannot_be():
    """No entry of the set may be there without one of the two, and none may be there twice.

    THE EXCUSED BUCKET IS PINNED, which is what keeps it from becoming the place entries go to
    avoid measurement: an author added without a scenario has to state what stops it being driven
    here, and the equality below is what asks for it.
    """
    gate = _gate3()
    demonstrated, excused = set(RECORDS_HISTORY), set(gate.NOT_DEMONSTRABLE)
    assert not demonstrated & excused, (
        "these entries are both driven and excused: %s" % sorted(demonstrated & excused))
    assert demonstrated | excused == set(gate.AUTHORS_A_COMMIT), (
        "the set the gate refuses on and the tables that measure it have drifted apart: "
        "unmeasured %s, measured but no longer refused %s"
        % (sorted(set(gate.AUTHORS_A_COMMIT) - demonstrated - excused),
           sorted((demonstrated | excused) - set(gate.AUTHORS_A_COMMIT))))
    for verb, reason in sorted(gate.NOT_DEMONSTRABLE.items()):
        assert len(str(reason).split()) >= 5, (
            "%r stands in the set without a scenario and says only %r about why" % (verb, reason))


def _git_names():
    """The command names the running git answers to, and the group IT calls history."""
    harness = _reader()
    return (harness.git_command_names(ROOT),
            {word.decode("utf-8", "replace").strip().lower()
             for word in harness._git(ROOT, ["--list-cmds=list-history"]).split()})


def test_every_name_the_gate_refuses_is_a_command_this_git_has():
    """A typo, or a command git has dropped, would refuse lines for a name nothing can run."""
    known, _history = _git_names()
    unknown = sorted(name for name in _gate3().AUTHORS_A_COMMIT if name not in known)
    assert not unknown, (
        "gate 3 refuses these as history-recording and this git does not name them among its own "
        "commands: %s" % unknown)


def test_every_command_git_itself_calls_history_is_classified():
    """The DERIVED end: git names a history group, and every member of it has to be judged.

    Git does not name the property SR-0009 asks about -- measured, `--list-cmds=list-history`
    carries `branch`, `switch`, `reset` and `tag` (which author nothing here) and misses `revert`,
    `cherry-pick`, `am` and `pull` (which do). What it IS good for is this: a command git ADDS to
    that group is one nobody has classified, and it turns this red until somebody does.
    """
    known, history = _git_names()
    assert history, "this git names no history group, so nothing was derived here"
    assert history <= known, (
        "git's own history group holds names it does not list as commands: %s"
        % sorted(history - known))
    classified = set(_gate3().AUTHORS_A_COMMIT) | set(AUTHORS_NOTHING)
    assert history <= classified, (
        "git counts these in its own history group and neither table here judges them: %s"
        % sorted(history - classified))


@pytest.fixture(scope="session")
def certified_project(outside_the_home_directory, project, open_item):
    """A stand-in project whose CURRENT working tree carries a passing verdict.

    WITHOUT THIS FIXTURE THE REFUSAL TESTS BELOW MEASURE NOTHING. Every line they drive would be
    rc 2 anyway, for the reason gate 3 has always had ("this working tree carries no passing
    Evidence"), and the whole block would stay green with this round's change taken out again --
    measured before the change, with a verdict recorded exactly like this: `git merge --no-ff
    other`, `git revert --no-edit HEAD`, `git cherry-pick`, `git am`, `git rebase --continue`,
    `git pull` and `git update-ref refs/heads/main $(git commit-tree ...)` were all rc 0.

    A COPY, and one that is not written to afterwards: the digest is the identity of this tree, so
    a test that changes it takes the verdict away from every test that runs later.
    """
    work = os.path.join(outside_the_home_directory, "certified")
    shutil.copytree(project, work)
    payload = bash_payload(work, "git commit -m wip")
    rc, err = run(work, "gate_commit_evidence.py", payload)
    assert rc == 2, "the copy already carried a verdict, so nothing here measures one"
    digest = re.search(r"diff:[0-9a-f]{64}", err).group(0)
    done = subprocess.run(
        [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "evidence",
         "--kind", "review", "--result", "pass", "--related", open_item,
         "--summary", "verifier PASS for " + digest, "--artifact-ref", "staging/verdict.md", *REVIEWED_BY],
        cwd=work, env=dict(os.environ, PYTHONPATH=os.path.join(work, "team-kits")),
        capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-600:]
    assert run(work, "gate_commit_evidence.py", payload)[0] == 0, (
        "the verdict did not open the commit, so nothing below is measured against one")
    return work


# The lines this round turns from rc 0 into rc 2, each with the verb whose remedy the refusal owes.
# Every one of them was measured rc 0 through the real gate process with a valid verdict in the
# tree on 2026-08-13, which is what makes each of these a red-without-the-fix case rather than a
# pin.
RECORDS_HISTORY_LINES = {
    "git merge --no-ff other": "merge",
    "git revert --no-edit HEAD": "revert",
    "git cherry-pick 1234abc": "cherry-pick",
    "git am patch.mbox": "am",
    "git rebase --continue": "rebase",
    "git pull origin main": "pull",
    "git stash": "stash",
    "git commit-tree -m x HEAD^{tree}": "commit-tree",
    "git notes add -m x": "notes",
    # F1: the PLUMBING author, and the one-call chain the verifier measured rc 0 before this round.
    # `hash-object` writes a commit object out of a tree and stdin, and update-ref (open) installs
    # it onto refs/heads/main
    "git hash-object -t commit -w --stdin": "hash-object",
    "git update-ref refs/heads/main "
    "$(printf 'tree %s\\n...\\n' $(git rev-parse HEAD^{tree}) "
    "| git hash-object -t commit -w --stdin)": "hash-object",
    # the chain SR-0009's parenthesis alone does not reach: an author whose object lands under no
    # branch, and an open ref move that makes it branch history -- in ONE tool call
    "git update-ref refs/heads/main $(git commit-tree -m x HEAD^{tree})": "commit-tree",
    # F2: a rebase pull records under --no-commit, so pull is not a produce-first form -- every
    # spelling of the rebase is refused
    "git pull --no-commit --rebase origin main": "pull",
    "git pull --no-commit -r origin main": "pull",
    "git -c pull.rebase=true pull --no-commit origin main": "pull",
    # a wrapper payload is the code it carries
    'bash -lc "git merge --no-ff other"': "merge",
    # the produce-first option is only a produce-first form in the shape that was MEASURED to
    # suppress the commit -- these three spellings all record one
    'git merge -m "--no-commit" other': "merge",
    "git merge --no-commit --commit --no-ff other": "merge",
    "git merge --no-ff --no-commit other": "merge",
    # ...and a word the text does not fix is not the option either, whatever it would expand to
    "git merge $FLAG --no-ff other": "merge",
}

# What must NOT become a refusal. AC-2 of BUG-0034 names the first seven; the rest are this repo's
# own documented command lines and the produce-first forms the remedy sends people to -- a gate
# that halts the work it certifies is not enforcement.
LEAVES_OPEN_LINES = [
    "git branch feature",
    "git checkout -b feature",
    "git switch -c feature",
    "git fetch origin",
    "git status",
    "git diff",
    "git add -A",
    "git log --oneline",
    "git reset --hard HEAD",
    "git update-ref refs/heads/side other",
    "git merge --no-commit --no-ff other",
    "git revert --no-commit HEAD",
    "git cherry-pick --no-commit 1234abc",
    "git merge --no-commit --ff-only origin/main",
    # the kits' reader resolves quoting the way a shell does, so these reach git as the same
    # option and are the same produce-first form
    'git merge "--no-commit" --no-ff other',
    "git merge --no-com\"mit\" --no-ff other",
    "PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory generate-index",
    "python -B -m pytest .claude/hooks/test_gates.py -q",
    "python tools/bump_kit_version.py",
    "ls docs",
]


@pytest.mark.parametrize("line", sorted(RECORDS_HISTORY_LINES))
def test_gate3_refuses_a_line_that_records_history_even_with_a_verdict(certified_project, line):
    """BUG-0034 / SR-0009 clause 3, against the running hook: gate 3 asked `Invocation.runs('commit')`,
    so `git merge --no-ff other` and `git revert --no-edit HEAD` recorded a commit into branch
    history at rc 0 with no verdict asked -- here every author other than `commit` is refused.

    Each line of `RECORDS_HISTORY_LINES` was measured rc 0 through this same gate process, with a
    valid verdict in the tree, on 2026-08-13; `certified_project` is the fixture that puts the
    verdict there, without which every line would be rc 2 for the OLD reason and this block would
    be green against the defect it exists for. `LEAVES_OPEN_LINES` is AC-2's other end.

    AND THE REFUSAL HAS TO CARRY THE ROUTE OUT, which is why the remedy is compared with the gate's
    own `_remedy` rather than with a sentence typed here: a refusal that cannot be complied with is
    the failure mode this layer is least allowed to have, and the route it names has to be the one
    the gate would let through.
    """
    verb = RECORDS_HISTORY_LINES[line]
    rc, err = run(certified_project, "gate_commit_evidence.py",
                  bash_payload(certified_project, line))
    assert rc == 2, "a line that can record history ran under a verdict about the tree BEFORE it"
    assert _gate3()._remedy(verb).strip() in err, (
        "the refusal does not name the produce-first route for `git %s`: %s" % (verb, err[:600]))
    assert "git commit" in err, "the refusal names no certifiable way to record the state"


def test_gate3_refuses_a_recording_line_on_the_other_shell_too(certified_project):
    """The trigger is a PROPERTY, not one shell: gate 3 is registered on Bash AND PowerShell.

    The registration test asks whether every registered tool NAME reaches a refusal, with a
    `git commit` payload. This asks it of the rule this round added, because a rule that only ever
    fires on one of the two tools is a rule half the surface does not have.
    """
    rc, err = run(certified_project, "gate_commit_evidence.py",
                  bash_payload(certified_project, "git merge --no-ff other", tool="PowerShell"))
    assert rc == 2, "the same line was refused on Bash and allowed on PowerShell"
    assert _gate3()._remedy("merge").strip() in err, err[:400]


@pytest.mark.parametrize("line", LEAVES_OPEN_LINES)
def test_gate3_leaves_the_ordinary_path_to_a_commit_open(certified_project, line):
    """The counter-end, under the same gate: no over-refusal of the work this gate certifies."""
    rc, err = run(certified_project, "gate_commit_evidence.py",
                  bash_payload(certified_project, line))
    assert rc == 0, "refused a line that records no history: %s" % err[:500]


@pytest.mark.parametrize("line", ["git status", "git branch feature", "git checkout -b feature",
                                  "git switch -c feature", "git fetch origin", "git add -A"])
def test_gate3_asks_for_no_verdict_on_the_way_to_a_commit(project, line):
    """The same lines against a tree that carries NO verdict: they may not need one either."""
    rc, err = run(project, "gate_commit_evidence.py", bash_payload(project, line))
    assert rc == 0, "a line on the way to a commit was made to wait for a verdict: %s" % err[:400]


def test_gate3_reads_a_message_that_mentions_a_subcommand_as_a_message(certified_project):
    """`git commit -m "merge later"` is a commit, and the widening must not make it a merge.

    The kits' reader already answers this (the whole quoted span is one word), and it is pinned
    here because the new rule is the first thing in this gate that acts on a verb OTHER than
    `commit` -- so the false positive it could produce is a refusal of the repo's own commits.
    """
    rc, err = run(certified_project, "gate_commit_evidence.py",
                  bash_payload(certified_project, 'git commit -m "merge later"'))
    assert rc == 0, "a commit whose MESSAGE names a subcommand was read as that subcommand: %s" % (
        err[:400])


def test_gate3_refuses_a_verb_the_running_git_does_not_know(certified_project):
    """An ALIAS hides the command it runs from every reader of the line.

    Measured through the kits' reader: `git -c alias.z='!git merge --no-ff other' z` comes back as
    the single subcommand `z`, and the inner merge is invisible. Defining the alias in one call
    (`git config alias.z ...`, which authors nothing and stays open) and using it in the next is
    the same chain in two steps. What answers is the running git's own command list.
    """
    for line in ("git z", "git -c alias.z='!git merge --no-ff other' z"):
        rc, err = run(certified_project, "gate_commit_evidence.py",
                      bash_payload(certified_project, line))
        assert rc == 2, "a subcommand this git does not have was judged harmless: %r" % line
        assert "--list-cmds" in err, (
            "refused, but not for being unknown to git -- so the derivation was not what "
            "answered: %s" % err[:400])


def test_gate3_refuses_a_verb_the_text_does_not_fix(certified_project):
    """An unresolved verb could be any subcommand, an authoring one included.

    Measured before this round, with a valid verdict in the tree: `git ${VERB} --no-ff other` was
    rc 0, because an unresolved verb took the evidence route and the evidence was there. It is
    refused now, and the refusal carries the kits' own note that says to spell the verb out.
    """
    rc, err = run(certified_project, "gate_commit_evidence.py",
                  bash_payload(certified_project, "git ${VERB} --no-ff other"))
    assert rc == 2, "a line whose git verb the text does not fix ran under a verdict"
    assert "spell the subcommand literally" in err, (
        "the refusal does not say how to comply: %s" % err[:400])


def test_gate3_says_what_to_do_with_a_line_it_cannot_read_at_all(certified_project):
    """Past the kits' reading limit EVERY verb is unresolved, and no spelling can help.

    The refusal for an unreadable verb says "spell the subcommand literally", and over
    `_compat.GIT_READ_LIMIT` that is advice nobody can follow: the reader hands back one unresolved
    invocation for the LENGTH of the line, and the kits' own note stays silent there for exactly
    that reason. So the refusal names the other remedy too, and this is what keeps the two in step.
    """
    harness = _reader()
    limit = harness.compat({"cwd": ROOT}).GIT_READ_LIMIT
    rc, err = run(certified_project, "gate_commit_evidence.py",
                  bash_payload(certified_project, "git status " + "x" * limit))
    assert rc == 2, "a line too long for the reader to judge was waved through"
    assert "split the call" in err, (
        "the refusal for an unreadable verb offers only a remedy this line cannot follow: %s"
        % err[:500])


def test_gate3_still_refuses_a_produce_first_form_in_front_of_a_commit(certified_project):
    """The one line the exemption makes reachable in front of a commit, and it stays refused.

    A PIN, not a red-without-the-fix case: `_moves_the_tree_first` already answered this before the
    exemption existed, because the kits' classification calls `git merge` a stage that is not
    read-only (measured: `_stage_is_read_only` is False for it and True for `git add -A`). It is
    pinned because the exemption is what makes the line reachable at all -- without the pin, a
    later widening of that classification would open a commit over a tree no verdict has seen.
    """
    rc, err = run(certified_project, "gate_commit_evidence.py",
                  bash_payload(certified_project,
                               "git merge --no-commit --no-ff other && git commit -m wip"))
    assert rc == 2, "a merge produced the tree and the commit recorded it under the OLD digest"
    assert "changes the working tree before the commit records it" in err, (
        "refused for the wrong reason: %s" % err[:400])


def _a_git_line_too_costly_to_judge_in(seconds):
    """A git line whose EXEMPTION reading alone costs more than `seconds`, sized by measuring it.

    NOT A TYPED SIZE, for the same reason as `_a_line_too_long_to_read_in`: two samples through the
    code that runs, the exponent between them read off, the size computed from it.

    THE SHAPE IS THE ONE THAT COSTS: k invocations inside ONE segment. `Invocation.arguments`
    rescans to the end of the segment per invocation, so a segment with k `git` words costs
    O(k * n) -- the shape `_compat.GIT_READ_LIMIT` documents for `gate_push_token`, and the one
    this round's exemption reading walks into. Every invocation here is exempt, which is what makes
    the gate read all of them instead of refusing at the first.
    """
    gate, harness = _gate3(), _reader()
    compat = harness.compat({"cwd": ROOT})

    def line(count):
        return " ".join(["git merge --no-commit --no-ff x"] * count)

    def cost(count):
        started = time.monotonic()
        for call in compat.git_invocations(line(count)):
            gate._produces_without_recording(call)
        return max(time.monotonic() - started, 1e-6)

    base = 500
    small, large = cost(base), cost(2 * base)
    growth = math.log(large / small, 2) if large > small else 0.0
    assert growth > 1.0, (
        "reading %d invocations costs %.4fs here and %d costs %.4fs, so the cost does not grow "
        "with the line and no length reaches a deadline" % (base, small, 2 * base, large))
    text = line(int(2 * base * (2.0 * seconds / large) ** (1.0 / growth)) + 1)
    assert len(text) < compat.GIT_READ_LIMIT, (
        "the line this host needs to spend %ss (%d characters) is longer than the reader's own "
        "limit, so it would be refused for its LENGTH and the budget would not be measured"
        % (seconds, len(text)))
    return text


def test_gate3_answers_before_its_registration_however_costly_the_line_is_to_judge(project,
                                                                                    tmp_path):
    """The cost this round adds must not become a way past the gate.

    A hook still deciding when the provider's timeout expires is killed, and a killed hook is an
    ALLOW. The reading `_produces_without_recording` does is per-invocation and rescans the
    segment, so a line can be built that costs more than the budget -- measured on this host
    through the real gate process under a 6 s registration: 2000 invocations rc 0 in 2.66 s, 4000
    rc 2 in 4.75 s with the budget's own refusal, 8000 rc 2 in 4.73 s. What answers is
    `_harness._the_budget_is_spent`, beside the decision (H35 in docs/POST_V2_WISHLIST.md).

    BOTH ENDS UNDER THE SAME REGISTRATION: a gate that answered "too slow" to everything would
    pass the first half, so an ordinary line still has to be judged.

    "HOST TOO NOISY" AND "GATE TOO SLOW" ARE DIFFERENT OUTCOMES HERE (BUG-0033). The last
    assertion compares a wall time this suite took from OUTSIDE the process against the
    registration, and what stands between the two is the part of a process start the gate cannot
    see -- interpreter, imports, payload down a pipe. The reserve exists to cover exactly that, so
    the run is a measurement only while this host's own start FITS in the reserve. Where it does
    not, the same red means "the machine was busy" as often as it means "the gate planned past its
    deadline", and a suite that is red for the first reason hides the second (five occurrences in
    generation 3). So on an overrun the vantage cost is measured AT THAT MOMENT through
    `_cost_of_a_gate_that_answers_at_once` -- the same floor the sister gate-1 test uses -- and the
    outcome is a SKIP naming the figures where it has eaten the reserve, a failure where it has
    not. Nothing here is compared against a typed number: `seconds` and `reserve` are derived from
    the registration `_harness` reads, and the margin is measured on the host.
    """
    ordinary, measured = _registrations(project, tmp_path)
    assert ordinary, ("no registration on this host leaves room for an ordinary verdict: %s"
                      % measured)
    # THE REGISTRATION IS THE ORDINARY ONE PLUS THE RESERVE, and both numbers are read out of
    # `_harness`. The line is sized to cost the WHOLE registration to read, not just the budget --
    # exactly as the sister gate-1 test does -- so the budget guard interrupts it MID-read at
    # `seconds - reserve` and the process ends a full `reserve` below `seconds`, rather than the
    # read finishing right as the guard fires (a race the first cut of this test lost under load).
    # THE MARGIN IS `reserve` (the floor, ~1.5 s here) MINUS this suite's own vantage cost -- the
    # interpreter start and 100+ KB of payload down a pipe, which `_harness`'s own clock does not
    # see because it starts after them. Under heavy PARALLEL load that vantage cost spikes and eats
    # the margin; that is BUG-0033's timing class, not a defect in the gate (the rc-2 "registration
    # allows" assertion below already proves the guard fired inside the budget), and which of the
    # two it is, is measured below rather than left to the reader.
    share, floor = _reserve_numbers()
    seconds = ordinary + floor
    reserve = max(seconds * (1.0 - share), floor)
    work = str(tmp_path / "gate3-deadline")
    shutil.copytree(project, work)
    _set_registered_timeout(work, seconds)
    # THE LINE IS BUILT BEFORE THE CLOCK STARTS, and standing inside it was the whole of BUG-0033
    # on this host: `_a_git_line_too_costly_to_judge_in` reads 1500 invocations through the real
    # reader to size the line, which costs 1.03-1.19 s here (measured over five runs, against 0.03 s
    # for the gate-1 sibling's cheaper sizing) -- work no gate process ever does, charged to the
    # gate's registration. `elapsed` then ran 4.54-4.62 s against a 4.50 s registration in an
    # otherwise IDLE run, while the same gate answered in 3.26-3.31 s when the line was built
    # outside the span. A quantity that is not what its name says is not made honest by a wider
    # margin, so the margin below stayed and the quantity moved.
    payload = bash_payload(work, _a_git_line_too_costly_to_judge_in(seconds))
    started = time.monotonic()
    rc, err = run(work, "gate_commit_evidence.py", payload)
    elapsed = time.monotonic() - started
    assert rc == 2, (
        "a line this gate could not judge inside its budget was waved through: rc=%d after %.2fs"
        % (rc, elapsed))
    assert "registration allows" in err, (
        "refused after %.2fs, but not for the deadline -- so the line was cheap enough to judge "
        "and nothing about the budget was measured: %s" % (elapsed, err[:300]))
    if elapsed >= seconds:
        # ASKED NOW, NOT BEFORE THE RUN: what decides is the load this run met, and a floor taken
        # while the machine was quiet would answer about a different minute. `bare` is the worst of
        # its samples and `noise` their spread, so the pair is this host's start cost at its
        # unluckiest -- which is the quantity the reserve has to cover for `elapsed < seconds` to
        # be about the gate at all.
        bare, noise = _cost_of_a_gate_that_answers_at_once(project, tmp_path)
        if bare + noise >= reserve:
            pytest.skip(
                "not measured here: a gate process needs %.2fs on this host before its own first "
                "line (noise %.2fs over %d runs) and the budget guard only reserves %.2fs of the "
                "%.2fs registration for it, so the %.2fs this run took says the machine was busy "
                "and cannot say the gate was slow (BUG-0033; %s)"
                % (bare, noise, SAMPLES, reserve, seconds, elapsed, measured))
        pytest.fail(
            "the gate answered after %.2fs while its registration gives it %.2fs (budget guard "
            "should have fired ~%.2fs earlier), and this host's own process start is %.2fs with "
            "%.2fs of noise -- that FITS in the reserve, so the overrun is the gate's and not the "
            "machine's (%s)" % (elapsed, seconds, reserve, bare, noise, measured))
    assert run(work, "gate_commit_evidence.py", bash_payload(work, "git status"))[0] == 0, (
        "under the same registration the gate turned into one that refuses everything")


# =============================================================================
# GATE 5 -- the SCOPE of a test run (FR-0086, the cost clause of DEC-0050).
# A block of its own: this file is a seam of generation 4 and G4-2 / G4-4 write their own tests
# into it. Everything gate 5 measures lives here and nowhere above.
# =============================================================================

GATE5 = "gate_test_scope.py"


def _surface_module():
    """The gate under test, imported ONLY for its constants -- every verdict below is a process."""
    sys.path.insert(0, HOOKS)
    import gate_test_scope
    return gate_test_scope


def _declaration_path(project):
    return os.path.join(project, *_surface_module().DECLARATION.split("/"))


def _declaration(project):
    with open(_declaration_path(project), encoding="utf-8") as handle:
        return json.load(handle)


def _declared_roots(project):
    """The surface roots this repo declares -- READ, never typed, so a change to the declaration
    changes what these tests drive rather than leaving them measuring a stale pair."""
    return [entry["root"] for entry in _declaration(project)["surfaces"]]


class _declaring(object):
    """The project's declaration replaced for one test, and put back afterwards.

    The `project` fixture is session-scoped, so a test that edits the declaration and does not
    restore it decides every later one. `finally`, and the file is written back BYTE for byte from
    what was read -- reading and writing binary is how the generation-3 CRLF incident is kept out.
    """

    def __init__(self, project, data):
        self._path = _declaration_path(project)
        self._data = data
        self._before = None

    def __enter__(self):
        with open(self._path, "rb") as handle:
            self._before = handle.read()
        with open(self._path, "wb") as handle:
            handle.write(json.dumps(self._data).encode("utf-8"))
        return self

    def __exit__(self, *_exc):
        with open(self._path, "wb") as handle:
            handle.write(self._before)
        return False


def _an_open_item(project):
    """An id that resolves, can carry work and is not terminal -- the property, looked up.

    The same lookup the `open_item` fixture makes, as a FUNCTION, because the test that needs it
    needs it against a COPY of the project rather than against the session-scoped one.
    """
    import yaml
    sys.path.insert(0, TEAM_KITS)
    from kernel.backlog_types import ACTIVE_DIRS, AUTOMATA
    from kernel.state import ProjectState
    state = ProjectState(os.path.join(project, "project_memory"))
    for item_type in sorted(set(AUTOMATA) & set(ACTIVE_DIRS)):
        for stem, path in state.iter_active_items(item_type):
            with open(path, encoding="utf-8") as handle:
                item = yaml.safe_load(handle) or {}
            if str(item.get("status") or "") not in AUTOMATA[item_type].terminals:
                return str(item.get("id") or stem)
    raise AssertionError("no open item in %s" % project)


def _record_full_run(project, item, line, result):
    """Record the run this gate allowed, the way DEC-0061 says a delivery run is recorded."""
    done = subprocess.run(
        [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "evidence",
         "--kind", "test", "--result", result, "--related", item,
         "--summary", "full run", "--artifact-ref", "staging/x/run.log",
         "--run-scope", "full", "--run-command", line],
        cwd=project, env=dict(os.environ, PYTHONPATH=os.path.join(project, "team-kits")),
        capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-600:]
    return done.stdout.split()[0]


@pytest.mark.parametrize("tool", sorted(SHELL_TOOLS))
def test_gate5_refuses_a_bare_full_run_of_every_declared_surface(project, tool):
    """A line that runs the whole of a declared surface, with nothing on it that says why.

    DRIVEN OVER EVERY DECLARED SURFACE and over both shells, because a gate that refuses the first
    root and not the second is the shape the round after this one deletes half of: the roots come
    out of the declaration, so a surface added there is measured the day it is added.
    """
    for root in _declared_roots(project):
        rc, err = run(project, GATE5,
                      bash_payload(project, "python -B -m pytest %s -q" % root, tool=tool))
        assert rc == 2, "a bare full run of %s was allowed as %s" % (root, tool)
        assert "WHOLE declared test surface" in err and root in err, err[:400]
        assert "DEC-0050" in err, "the refusal does not carry the rule it enforces: %s" % err[:400]


@pytest.mark.parametrize("shape", ["%s/test_hooks.py", "%s/test_hooks.py::test_x", "%s -k a_name",
                                   "%s -m slow", "%s --collect-only"])
def test_gate5_lets_a_selection_through(project, shape):
    """A selection is not judged at all -- the sub-path, the node id and the filter options."""
    root = _declared_roots(project)[0]
    rc, err = run(project, GATE5, bash_payload(project, "python -B -m pytest " + shape % root))
    assert rc == 0, "a selection was refused: %s" % err[:400]


def test_gate5_does_not_judge_a_line_that_only_names_the_runner(project):
    """`grep pytest tools/` runs grep. The runner has to be the VERB or the word `-m` hands it --
    without that boundary every line mentioning the word would be a full run."""
    root = _declared_roots(project)[0]
    for command in ("grep -rn pytest %s" % root, "ls %s" % root, "echo pytest %s" % root):
        rc, err = run(project, GATE5, bash_payload(project, command))
        assert rc == 0, "%r was judged as a test run: %s" % (command, err[:300])


def test_gate5_reads_the_module_flag_as_the_interpreters_and_the_runners_own(project):
    """`-m` belongs to two programs at once, and the boundary between them is what decides.

    `python -B -m pytest tools/ -q` is this repo's own documented full-run line: read over the
    whole stage, its `-m` is a declared narrowing option and the line came out as a selection --
    measured, rc 0 where the refusal belongs. `pytest tools/ -m slow` is the same two characters
    doing the other job and must stay a selection.
    """
    root = _declared_roots(project)[0]
    assert run(project, GATE5, bash_payload(project, "python -B -m pytest %s -q" % root))[0] == 2
    assert run(project, GATE5,
               bash_payload(project, "python -B -m pytest %s -m slow" % root))[0] == 0


@pytest.mark.parametrize("tool", sorted(SHELL_TOOLS))
def test_gate5_lets_the_delivery_prefix_through_in_both_shells(project, open_item, tool):
    """The way through the refusal, in the spelling each shell has for it.

    A POSIX shell puts the assignment in front of the program; PowerShell writes it as a command of
    its own. Both are driven, because the gate is registered on both and a prefix only one of them
    can write is a remedy the other half of this repo cannot use.
    """
    marker = _surface_module().DELIVERY_MARKER
    line = "python -B -m pytest %s -q" % _declared_roots(project)[0]
    prefixed = ('$env:%s="%s"; %s' % (marker, open_item, line) if tool == "PowerShell"
                else "%s=%s %s" % (marker, open_item, line))
    rc, err = run(project, GATE5, bash_payload(project, prefixed, tool=tool))
    assert rc == 0, "the delivery run was refused as %s: %s" % (tool, err[:400])


def test_gate5_prints_a_delivery_line_the_kernel_accepts_as_a_full_run(project, tmp_path):
    """The remedy is EXECUTED, not read -- the same standard gate 3's remedy is held to.

    Two halves, and the second is DEC-0061's coupling: the line the refusal prints has to pass this
    gate once its `<ITEM-ID>` is filled in, AND the kernel has to accept exactly that line as the
    Evidence the merge reads (`run_scope: full`). A remedy that passes the gate but that no
    Evidence can name would leave the allowed run unrecordable.

    On a COPY, because the second half WRITES an Evidence into the store, and one recorded against
    the session-scoped project would close the round for every test after it.
    """
    work = str(tmp_path / "gate5-remedy")
    shutil.copytree(project, work)
    item = _an_open_item(work)
    line = "python -B -m pytest %s -q" % _declared_roots(work)[0]
    _rc, err = run(work, GATE5, bash_payload(work, line))
    printed = [one.strip() for one in err.splitlines()
               if one.strip().startswith(_surface_module().DELIVERY_MARKER + "=")]
    assert printed, "the refusal printed no delivery line: %s" % err[:600]
    filled = printed[0].replace("<ITEM-ID>", item)
    assert run(work, GATE5, bash_payload(work, filled))[0] == 0, (
        "the line this gate prints as the way through is one it refuses: %s" % filled)
    _record_full_run(work, item, line, "pass")


def test_gate5_refuses_a_delivery_prefix_that_leads_no_open_work(project):
    """A prefix that names nothing is a full run with a word in front of it.

    Both halves of "nothing": an id no store resolves, and one that resolves onto a FINISHED item.
    The second is the one that rots quietly -- last round's prefix keeps working.
    """
    line = "python -B -m pytest %s -q" % _declared_roots(project)[0]
    marker = _surface_module().DELIVERY_MARKER
    finished = _a_finished_item(project)
    for named in ("TSK-9999", "not-an-id", finished):
        rc, err = run(project, GATE5, bash_payload(project, "%s=%s %s" % (marker, named, line)))
        assert rc == 2, "%r bought a full run" % named
        assert "leads no open work" in err, err[:400]


def _a_finished_item(project):
    """An id that RESOLVES and is terminal -- looked up, so no test spells a status out."""
    import yaml
    sys.path.insert(0, TEAM_KITS)
    from kernel.backlog_types import ACTIVE_DIRS, AUTOMATA
    from kernel.state import ProjectState
    state = ProjectState(os.path.join(project, "project_memory"))
    for item_type in sorted(set(AUTOMATA) & set(ACTIVE_DIRS)):
        for stem, path in state.iter_active_items(item_type):
            with open(path, encoding="utf-8") as handle:
                item = yaml.safe_load(handle) or {}
            if str(item.get("status") or "") in AUTOMATA[item_type].terminals:
                return str(item.get("id") or stem)
    pytest.skip("this store holds no terminal item, so the stale-prefix half cannot be measured")


@pytest.mark.parametrize("result,expected", [("pass", 2), ("fail", 0)])
def test_gate5_refuses_the_second_full_run_of_a_round_but_not_after_findings(
        project, tmp_path, result, expected):
    """DEC-0063 (4): the full run happens once, and a second one is the alternative, not the default.

    On a COPY, because both cases write Evidence into the store. The two cases are the whole rule:
    a PASSING record closes the round's full run, a FAILING one is exactly the case DEC-0063 (4)
    sends back into the suites and must close nothing.
    """
    marker = _surface_module().DELIVERY_MARKER
    work = str(tmp_path / ("gate5-second-" + result))
    shutil.copytree(project, work)
    item = _an_open_item(work)
    line = "python -B -m pytest %s -q" % _declared_roots(work)[0]
    prefixed = "%s=%s %s" % (marker, item, line)
    assert run(work, GATE5, bash_payload(work, prefixed))[0] == 0, (
        "the FIRST delivery run of %s was already refused" % item)
    recorded = _record_full_run(work, item, line, result)
    rc, err = run(work, GATE5, bash_payload(work, prefixed))
    assert rc == expected, (
        "after a %r full run (%s) the next one came back rc=%d (%s)"
        % (result, recorded, rc, err[:300]))
    if expected == 2:
        assert "DEC-0063" in err and recorded in err, err[:400]


def test_gate5_says_nothing_where_a_project_declares_no_test_surface(project):
    """PR-0004's first invariant, as the gate's own answer: a runner nobody declared is not judged.

    The declaration is REMOVED rather than emptied, because those are two states and only one of
    them is "this project declares nothing" -- an unreadable file is the third and is refused.
    """
    path = _declaration_path(project)
    with open(path, "rb") as handle:
        before = handle.read()
    line = "python -B -m pytest %s -q" % _declared_roots(project)[0]
    try:
        os.remove(path)
        assert run(project, GATE5, bash_payload(project, line))[0] == 0, (
            "a project that declares no test surface was still judged")
        # EVERY SHAPE A JSON PARSER TAKES AND THIS GATE CANNOT USE, not only a syntax error.
        # Measured before the fix (verifier round 1, F5): `[]`, `"tools"`, `7`, `null`, `{}` and
        # `{"surfaces": "tools"}` were each rc 0 -- ALLOWED -- while the docstring promised that a
        # gate which cannot read its own rule refuses. `{}` is the one case that stays an ALLOW and
        # is right: an object with no `surfaces` declares no surface, which is the absent case.
        for body, expected in ((b"{ not json", 2), (b"[]", 2), (b'["tools"]', 2),
                               (b'"tools"', 2), (b"7", 2), (b"null", 2),
                               (b'{"surfaces": "tools"}', 2), (b"{}", 0)):
            with open(path, "wb") as handle:
                handle.write(body)
            rc, err = run(project, GATE5, bash_payload(project, line))
            assert rc == expected, (
                "a declaration holding %r came back rc=%d: %s" % (body, rc, err[:300]))
            if expected == 2:
                assert "could not be judged" in err, (body, err[:300])
    finally:
        with open(path, "wb") as handle:
            handle.write(before)
    assert run(project, GATE5, bash_payload(project, line))[0] == 2, (
        "the declaration was not put back -- every later test in this block would measure a "
        "project that declares nothing")


def test_gate5_charges_nothing_to_a_project_whose_suite_runs_in_seconds(project):
    """AC-4, DEC-0056's cost clause, measured rather than argued.

    The threshold is data, so this drives it: with the declared duration UNDER
    `judged_above_seconds` the same line that is refused above is not judged at all. That is what a
    project whose whole suite runs in seconds pays -- nothing -- and it is the reason the number
    lives in the declaration and not in the gate.
    """
    data = _declaration(project)
    line = "python -B -m pytest %s -q" % data["surfaces"][0]["root"]
    cheap = dict(data, surfaces=[dict(one, seconds=1) for one in data["surfaces"]])
    with _declaring(project, cheap):
        assert run(project, GATE5, bash_payload(project, line))[0] == 0, (
            "a surface declared cheaper than the threshold was still refused")
    assert run(project, GATE5, bash_payload(project, line))[0] == 2, (
        "the declaration was not put back")


def test_every_test_file_of_this_repo_lies_under_a_declared_surface():
    """The declaration is compared with the TREE, at both ends.

    A declaration is a claim about what this repo's test surface IS, and a claim nothing compares
    rots in two directions: a suite added outside every declared root is a surface this gate does
    not judge (and the class FR-0086 exists for comes back), and a declared root with no test file
    under it is an entry that has outlived its suite. Both are asked here.

    `team-kits/` is out on purpose and it is not an omission: what a kit SHIPS into a project is
    that project's suite, not one this repo runs -- the kit half of FR-0086 is measured in
    `tools/test_hooks.py`, against a scaffolded pilot.
    """
    with open(os.path.join(ROOT, "tools", "test_surface.json"), encoding="utf-8") as handle:
        roots = [entry["root"] for entry in json.load(handle)["surfaces"]]
    found = {root: 0 for root in roots}
    orphans = []
    for base, directories, names in os.walk(ROOT):
        directories[:] = [one for one in directories
                          if one not in {".git", "__pycache__", "node_modules", "archive"}]
        for name in names:
            if not (name.startswith("test_") and name.endswith(".py")):
                continue
            relative = os.path.relpath(os.path.join(base, name), ROOT).replace("\\", "/")
            if relative.startswith("team-kits/"):
                continue
            owners = [root for root in roots
                      if relative == root or relative.startswith(root.rstrip("/") + "/")]
            if owners:
                for root in owners:
                    found[root] += 1
            else:
                orphans.append(relative)
    assert not orphans, (
        "these suites lie under no declared surface, so gate 5 judges no run of them: %s" % orphans)
    empty = [root for root, count in found.items() if not count]
    assert not empty, "these declared surfaces hold no test file at all: %s" % empty


# The two-ended tripwire on the ONE enumeration this gate decides on. `options_that_narrow` cannot
# be a property of the text -- what `--deselect` does to a run is a fact about the runner -- so it
# is declared, and both ends of that declaration are measured here.


def _declared_options(project, runner="pytest"):
    return list((_declaration(project).get("options_that_narrow") or {}).get(runner) or ())


def test_every_declared_narrowing_option_is_one_the_runner_still_has(project):
    """END ONE, the dead entry: an option the installed runner no longer knows.

    ASKED OF THE RUNNER, not of a table -- `--help` is the runner's own inventory and it costs no
    collection, which is the whole reason this gate exists. An option that has been renamed or
    dropped would otherwise sit here forever, quietly turning every line that carries it into an
    allowed selection.
    """
    done = subprocess.run([sys.executable, "-B", "-m", "pytest", "--help"],
                          cwd=project, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-400:]
    inventory = done.stdout + done.stderr
    missing = [one for one in _declared_options(project) if one not in inventory]
    assert not missing, (
        "these options are declared as ones that narrow a run, and the installed runner does not "
        "list them any more: %s" % missing)


def test_every_declared_narrowing_option_earns_its_place(project):
    """END TWO, the entry that would not have been needed: one that changes no verdict.

    Driven per option through the REAL gate process: the same line without it must be refused and
    with it must pass. An entry that leaves both answers equal is decorating a list rather than
    deciding anything -- and a list nobody can shrink is how the next enumeration defect gets in.
    """
    root = _declared_roots(project)[0]
    bare = "python -B -m pytest %s -q" % root
    assert run(project, GATE5, bash_payload(project, bare))[0] == 2, (
        "the line these options are measured against is not refused without them")
    idle = []
    for option in _declared_options(project):
        # a value for the ones that take one; a runner reads `-k=x` and `-k x` alike, and the
        # `=` form needs no second word, so one shape drives both kinds
        line = "python -B -m pytest %s -q %s=probe" % (root, option)
        if run(project, GATE5, bash_payload(project, line))[0] != 0:
            idle.append(option)
    assert not idle, (
        "these options are declared as ones after which the line no longer runs the whole surface, "
        "and the gate refuses the line anyway: %s" % idle)


# The target is a PATH, not a piece of text (verifier round 1, B2).
#
# `_covers` compared the raw word, so every spelling that means the declared root without SPELLING
# it walked past the gate: `tools/.`, `tools/../tools`, `..`, and the ABSOLUTE path -- which is the
# spelling gate 1 pushes every caller into ("Remedy: spell the path absolutely and without a tilde
# prefix"). `..` is literally the case `_covers`'s own docstring promises to cover.
B2_SPELLINGS = [
    "%s/.",
    "%s/./",
    "./%s/.",
    "%s/../%s",
    "..",
]
# `%s/../../%s` is NOT in that list, and the reason is the point of the round-2 fix: two levels up
# and down again lands on a `tools` directory OUTSIDE this repo, which is a different place. It is
# measured as the unplaceable case below instead.


@pytest.mark.parametrize("shape", B2_SPELLINGS)
def test_gate5_reads_a_target_as_a_path_and_not_as_text(project, shape):
    """Every spelling that HANDS the runner the whole declared surface is one, however written."""
    root = _declared_roots(project)[0]
    target = shape % ((root,) * shape.count("%s"))
    rc, err = run(project, GATE5, bash_payload(project, "python -B -m pytest %s -q" % target))
    assert rc == 2, "%r reaches the whole of %r and was allowed" % (target, root)
    assert "WHOLE declared test surface" in err, err[:300]


def test_gate5_reads_an_absolute_target_the_way_gate_1_makes_a_caller_spell_it(project):
    """The absolute path, because that is the spelling the other gates of this repo REQUIRE.

    `gate_lead_write_scope` ends every refusal with "Remedy: spell the path absolutely and without a
    tilde prefix". A caller who follows it must not thereby step around gate 5 -- so the word is
    relativised against the payload's own `cwd` before it is compared.
    """
    root = _declared_roots(project)[0]
    absolute = os.path.join(project, *root.split("/")).replace("\\", "/")
    rc, err = run(project, GATE5, bash_payload(project, 'python -B -m pytest "%s" -q' % absolute))
    assert rc == 2, "the absolute spelling of %r was allowed: %s" % (root, err[:200])
    assert "WHOLE declared test surface" in err, err[:300]


def test_gate5_says_so_when_it_cannot_place_a_target_at_all(project):
    """F8: the fail-closed branch gets its OWN sentence, because the ordinary one would be false.

    A word on another drive, a UNC share or a path that resolves outside this repo does not run
    `tools`; saying it does sends the reader to `judged_above_seconds` for a problem that is not
    there. The refusal still REFUSES -- what this gate cannot place, it does not wave through.
    """
    root = _declared_roots(project)[0]
    # `%s/../../%s` is NOT here since the round-3 narrowing: two levels up and down lands on a
    # place this reader CAN find, and a place that is not this repository is a selection, not an
    # unplaceable word. It is measured as such in
    # `test_gate5_lets_a_rig_run_a_suite_that_lies_outside_this_repository`'s sibling below.
    elsewhere = [
        "D:/other-project/tests/test_x.py",
        "//server/share/proj/tests/test_x.py",
        "C:%s" % root,                       # drive-relative: the shell's per-drive directory
    ]
    for target in elsewhere:
        rc, err = run(project, GATE5,
                      bash_payload(project, 'python -B -m pytest "%s"' % target))
        assert rc == 2, "%r was waved through" % target
        assert "could not be placed against this repository" in err, (target, err[:300])
        assert "WHOLE declared test surface" not in err, (
            "the refusal claims this line runs %r, which it does not: %s" % (root, err[:300]))


def test_gate5_still_lets_a_selection_through_however_it_is_spelled(project):
    """The other direction, because a path reader that refuses everything is worth as little as one
    that refuses nothing: a sub-path stays a selection through the same normalisation."""
    root = _declared_roots(project)[0]
    for target in ("%s/./test_hooks.py" % root, "./%s/test_hooks.py" % root,
                   "%s/../%s/test_hooks.py" % (root, root)):
        rc, err = run(project, GATE5, bash_payload(project, "python -B -m pytest %s -q" % target))
        assert rc == 0, "%r is a selection and was refused: %s" % (target, err[:200])


def test_gate5_reads_a_positional_glob_as_what_the_shell_makes_of_it(project):
    """A word the SHELL expands narrows nothing, and this gate has the same filesystem it has.

    MEASURED AS A PROCESS BEFORE THIS EXISTED (merge round TSK-0126, verifier round 1, B2):
    `python -m pytest tools/test_*.py -q` was rc 0 while the root held 40 matching files and the
    surface is declared at 3465 s -- 42 minutes waved through, because the reader placed the word
    as ONE path, found it inside the root, and read "inside the root" as "narrows the run".

    BOTH DIRECTIONS, because a reader that refuses every glob is worth as little as one that
    refuses none: the glob that takes every declared member is a full run, and one that takes a
    strict subset is a selection. The subject is READ from the declaration, so a members line that
    moves moves these cases with it.
    """
    declaration = _declaration(project)
    entry = next(one for one in declaration["surfaces"] if one.get("members"))
    root, members = entry["root"], entry["members"]
    # A GLOB IS ANSWERED BY THE FILESYSTEM, so the members have to be there: the pilot carries the
    # declaration but no suite under the root, and an expansion of nothing is neither direction.
    planted = [os.path.join(str(project), *root.split("/"), name)
               for name in ("test_alpha.py", "test_beta.py")]
    for one in planted:
        os.makedirs(os.path.dirname(one), exist_ok=True)
        with open(one, "wb") as handle:
            handle.write(b"def test_x():\n    assert True\n")
    try:
        everything = "%s/%s" % (root, members)
        rc, err = run(project, GATE5,
                      bash_payload(project, "python -B -m pytest %s -q" % everything))
        assert rc == 2, "a glob over every declared member ran unrefused: %s" % err[:200]
        assert "WHOLE declared test surface" in err, err[:300]

        narrow = "%s/test_a*.py" % root
        rc, err = run(project, GATE5, bash_payload(project, "python -B -m pytest %s -q" % narrow))
        assert rc == 0, "%r takes a strict subset and was refused: %s" % (narrow, err[:300])

        rc, err = run(project, GATE5, bash_payload(
            project, "DELIVERY_RUN=%s python -B -m pytest %s -q"
            % (_an_open_item(project), everything)))
        assert rc == 0, "the delivery prefix did not open the glob: %s" % err[:300]
    finally:
        for one in planted:
            os.remove(one)


def test_gate5_reads_the_brace_expansion_a_shell_would_perform(project):
    """The SECOND expansion, and the three answers it has.

    MEASURED WITH THE REAL SHELL (merge verify round 2, R2-B4, a `python` shim on PATH that logged
    the runner's argv): `pytest <root>/{test_*,conftest}.py -q` hands the runner 41 `.py` paths --
    the whole declared surface plus one -- and the gate was rc 0, because `glob.has_magic` knows
    `*`, `?` and `[` and not `{`.

    Three cases, all against members this test plants, so the subject is the reading and not the
    repository's own file list: a brace whose expansion COVERS the members, one that takes a strict
    subset, and one this reader cannot expand at all (a range), which is not a selection.
    """
    declaration = _declaration(project)
    entry = next(one for one in declaration["surfaces"] if one.get("members"))
    root = entry["root"]
    planted = [os.path.join(str(project), *root.split("/"), name)
               for name in ("test_alpha.py", "test_beta.py")]
    for one in planted:
        os.makedirs(os.path.dirname(one), exist_ok=True)
        with open(one, "wb") as handle:
            handle.write(b"def test_x():\n    assert True\n")
    try:
        covering = "%s/{test_*,conftest}.py" % root
        rc, err = run(project, GATE5, bash_payload(project, "python -B -m pytest %s -q" % covering))
        assert rc == 2, "a brace whose expansion covers every member ran unrefused: %s" % err[:200]
        assert "WHOLE declared test surface" in err, err[:300]

        narrow = "%s/test_{alpha,gamma}.py" % root
        rc, err = run(project, GATE5, bash_payload(project, "python -B -m pytest %s -q" % narrow))
        assert rc == 0, "%r takes a strict subset and was refused: %s" % (narrow, err[:300])

        unreadable = "%s/test_{1..9}.py" % root
        rc, err = run(project, GATE5,
                      bash_payload(project, "python -B -m pytest %s -q" % unreadable))
        assert rc == 2, "a word this reader cannot expand was waved through: %s" % err[:200]
        assert "cannot compute that expansion" in err, err[:300]
    finally:
        for one in planted:
            os.remove(one)


def test_gate5_says_so_when_a_surface_declares_no_members_for_a_glob(project):
    """The fail-closed direction, and its own sentence.

    Without `members` this reader cannot tell `<root>/test_x*.py` from the whole surface -- so it
    refuses, and it says THAT rather than claiming the line runs everything, which would be a claim
    it has not made. The declaration is put back by `_declaring` byte for byte.
    """
    declaration = _declaration(project)
    entry = next(one for one in declaration["surfaces"] if one.get("members"))
    root = entry["root"]
    stripped = json.loads(json.dumps(declaration))
    for one in stripped["surfaces"]:
        one.pop("members", None)
    with _declaring(project, stripped):
        rc, err = run(project, GATE5, bash_payload(
            project, "python -B -m pytest %s/test_h*.py -q" % root))
    assert rc == 2, "a glob under a surface with no members was waved through: %s" % err[:200]
    assert "says nothing about which files" in err, err[:300]
    assert "WHOLE declared test surface" not in err, (
        "the fail-closed branch borrowed the sentence of the other one: %s" % err[:300])


def test_the_declared_members_are_the_files_the_runner_really_collects():
    """The tripwire on `members`, and it asks the RUNNER rather than this gate or this test.

    `members` is a fact about what pytest collects out of a directory, and a fact about a runner
    that only this repo's prose knows is one that rots: a members glob grown too narrow lets the
    whole surface through as a "selection" again, one grown too wide refuses a real selection. So
    the comparison is with the runner's own collection -- `--collect-only`, whose file parts are
    the files it would run -- and both directions are asserted.

    Cheap enough to keep: measured 2026-09-05, `pytest tools/ --collect-only -q` answers in 8.7 s
    for 4697 tests.
    """
    with open(os.path.join(ROOT, "tools", "test_surface.json"), encoding="utf-8") as handle:
        surfaces = json.load(handle)["surfaces"]
    judged = [entry for entry in surfaces if entry.get("members")]
    assert judged, "no surface declares `members`, so this tripwire measures nothing"
    for entry in judged:
        root = os.path.join(ROOT, *str(entry["root"]).split("/"))
        assert os.path.isdir(root), "%s declares members and its root is not a directory" % entry
        collected = subprocess.run(
            [sys.executable, "-B", "-m", "pytest", entry["root"], "--collect-only", "-q"],
            cwd=ROOT, capture_output=True, text=True, timeout=900)
        assert collected.returncode == 0, collected.stdout[-2000:] + collected.stderr[-2000:]
        runs = {os.path.normcase(os.path.abspath(os.path.join(ROOT, line.split("::")[0])))
                for line in collected.stdout.splitlines() if "::" in line}
        assert runs, "the runner collected nothing under %s" % entry["root"]
        declared = {os.path.normcase(os.path.abspath(one))
                    for one in globmodule.glob(
                        os.path.join(root, *str(entry["members"]).split("/")))}
        missing = sorted(os.path.relpath(one, ROOT) for one in runs - declared)
        extra = sorted(os.path.relpath(one, ROOT) for one in declared - runs)
        assert not missing, (
            "`members` of surface %r misses %d file(s) the runner really runs, so a glob over the "
            "declared members reads as a selection while it runs them: %s"
            % (entry["root"], len(missing), missing[:5]))
        assert not extra, (
            "`members` of surface %r names %d file(s) the runner does not run, so a real full run "
            "can fail to cover them and reads as a selection: %s"
            % (entry["root"], len(extra), extra[:5]))


# The tripwire that measures the PROPERTY, not the list (verifier round 1, B1).
#
# The first cut had two ends and neither asked what an option DOES: one grepped `pytest --help`,
# the other asked the gate about the list the gate itself decides from -- a tautology, and the
# verifier's counter-mutation (declaring `-v`, `--tb`, `--durations`) left it green. Seven declared
# entries narrowed nothing, and `python -B -m pytest tools/ --ff` was rc 0 against a surface
# declared at 3465 s: exactly the error class this gate exists for.

PROBE_SUITE = (
    "import os\n"
    "import pytest\n"
    "\n"
    "def _mark(name):\n"
    "    with open(os.environ['PROBE_LOG'], 'a', encoding='utf-8') as handle:\n"
    "        handle.write(name + chr(10))\n"
    "\n"
    "def test_alpha():\n"
    "    _mark('alpha')\n"
    "\n"
    "@pytest.mark.slow\n"
    "def test_beta():\n"
    "    _mark('beta')\n"
    "\n"
    "def test_gamma():\n"
    "    _mark('gamma')\n")


def _probe_project(base):
    """A three-test suite whose tests RECORD that they ran, outside this repo.

    The count is read off a file the tests append to, not off pytest's summary prose: a summary
    line is a rendering that changes with the runner's version, and what this measures is whether
    the tests were EXECUTED.
    """
    os.makedirs(os.path.join(base, "tests"), exist_ok=True)
    with open(os.path.join(base, "tests", "test_probe.py"), "w", encoding="utf-8") as handle:
        handle.write(PROBE_SUITE)
    with open(os.path.join(base, "pytest.ini"), "w", encoding="utf-8") as handle:
        handle.write("[pytest]\nmarkers =\n    slow: a marker the probe uses\n")
    return base


def _executed(base, option=None):
    """How many of the probe's tests actually ran with `option` on the line."""
    log = os.path.join(base, "probe-log.txt")
    if os.path.exists(log):
        os.remove(log)
    cache = os.path.join(base, ".pytest_cache")
    if os.path.isdir(cache):
        shutil.rmtree(cache, ignore_errors=True)
    subprocess.run([sys.executable, "-B", "-m", "pytest", "tests"] + ([option] if option else []),
                   cwd=base, capture_output=True, text=True, timeout=300,
                   env=dict(os.environ, PROBE_LOG=log))
    if not os.path.exists(log):
        return 0
    with open(log, encoding="utf-8") as handle:
        return len([one for one in handle.read().splitlines() if one.strip()])


def test_every_declared_narrowing_option_really_makes_the_runner_run_fewer_tests(
        project, outside_the_home_directory):
    """THE property, asked of the RUNNER: with this option, fewer tests are executed.

    This is the end the first cut did not have. `--ff`/`--nf` reorder and narrow nothing;
    `--lf`/`--sw` narrow only when a cache of failures exists -- measured, three of three tests ran
    under each of them, and the gate let `pytest tools/ --ff` through against a surface declared at
    3465 s.

    An entry with no probe value is red too, and that is what keeps the two tables complete in both
    directions: a new option cannot be declared without saying what it would narrow ON.
    """
    declaration = _declaration(project)
    declared = declaration["options_that_narrow"]["pytest"]
    probes = declaration.get("probe_values", {}).get("pytest", {})
    base = _probe_project(os.path.join(outside_the_home_directory, "narrowing-probe"))
    bare = _executed(base)
    assert bare > 1, "the probe suite ran %d tests, so nothing here could narrow" % bare
    unprobed = [one for one in declared if one not in probes]
    assert not unprobed, (
        "these options are declared as narrowing and carry no probe value, so nothing can measure "
        "what they narrow: %s" % unprobed)
    idle = []
    for option in declared:
        ran = _executed(base, option + probes[option])
        if ran >= bare:
            idle.append("%s%s ran %d of %d" % (option, probes[option], ran, bare))
    assert not idle, (
        "these options are declared as ones after which the line no longer runs the whole surface, "
        "and the runner executed just as many tests with them as without: %s" % idle)


@pytest.mark.parametrize("empty", ['-k ""', "-k=", '-m ""', "-m="])
def test_gate5_reads_an_empty_selector_value_as_no_selection(project, empty):
    """`-k ""` selects nothing away -- three of three fixture tests still ran (measured).

    So the line still runs the whole declared surface and is refused. Read on the VALUE and not on
    the option name, which is what the first cut did.
    """
    root = _declared_roots(project)[0]
    rc, err = run(project, GATE5,
                  bash_payload(project, "python -B -m pytest %s -q %s" % (root, empty)))
    assert rc == 2, "%r bought a full run" % empty
    assert "WHOLE declared test surface" in err, err[:300]


@pytest.mark.parametrize("ordering", ["--ff", "--nf", "--lf", "--sw", "--failed-first",
                                      "--new-first", "--stepwise", "--last-failed"])
def test_gate5_refuses_a_full_run_carrying_only_an_ordering_or_cache_option(project, ordering):
    """The measured error class: an ordinary flag somebody types, and the whole suite runs.

    These are not bypass spellings. `pytest tools/ --ff` is what a reader types who wants the last
    failures first, and until this round it was rc 0 against a surface declared at 3465 s.
    """
    root = _declared_roots(project)[0]
    rc, err = run(project, GATE5,
                  bash_payload(project, "python -B -m pytest %s %s" % (root, ordering)))
    assert rc == 2, "%r bought a full run of %s" % (ordering, root)
    assert "WHOLE declared test surface" in err, err[:300]


def _payload_from(project, command, cwd):
    """A shell payload whose `cwd` is somewhere else than the project root.

    The provider sends the shell's OWN working directory, and in this project that is routinely a
    worktree or a scratch tree one level above the repo -- so the base a target is attached to and
    the base the declared surfaces are relative to are two different things.
    """
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": cwd,
            "tool_input": {"command": command}}


def test_gate5_measures_the_declared_root_against_the_REPO_and_not_against_the_shells_cwd(project):
    """B2' of verifier round 2: the declared roots are repo-relative, so the repo root is the base.

    Measured before this: with a payload `cwd` one level ABOVE the repo,
    `pytest "<abs>/tools"` and `pytest <name>/tools` were both rc 0 against a surface declared at
    3465 s, while the same two lines from inside the repo were rc 2. A shell one level above the
    repo is the ordinary case here, and the absolute spelling is the one gate 1's every refusal
    asks for -- so this was a full run nobody was told about.
    """
    outside = os.path.dirname(project)
    name = os.path.basename(project)
    root = _declared_roots(project)[0]
    for command in ('python -B -m pytest "%s"' % os.path.join(project, root).replace("\\", "/"),
                    "python -B -m pytest %s/%s" % (name, root)):
        rc, err = run(project, GATE5, _payload_from(project, command, outside))
        assert rc == 2, "from a shell above the repo, %r was allowed" % command
        assert "WHOLE declared test surface" in err, err[:300]
    # ...and from INSIDE the surface, where a bare `.` is the whole of it
    inside = os.path.join(project, *root.split("/"))
    if os.path.isdir(inside):
        rc, _err = run(project, GATE5, _payload_from(project, "python -B -m pytest .", inside))
        assert rc == 2, "from inside the declared surface, `.` was allowed"


def test_gate5_asks_the_filesystem_which_place_a_target_is(project):
    """B2'' of verifier round 2: "the same place" is what the filesystem says, not what text says.

    This repo answered that question once already, for gate 1: `_harness.under` compares the
    IDENTITY of the deepest existing ancestor. Gate 5 had built a text normaliser of its own and
    inherited none of it -- measured against the real runner, `pytest TOOLS` collected the same
    4627 node ids as `pytest tools` and was rc 0 here. The reader is REUSED now, so a case variant
    and a junction are the place they are.

    The junction half is skipped where this host cannot make one; the case half is skipped where
    the filesystem really is case-sensitive, because there `TOOLS` IS another place.
    """
    root = _declared_roots(project)[0]
    target = os.path.join(project, *root.split("/"))
    if os.path.isdir(target) and os.path.isdir(os.path.join(project, root.upper())):
        rc, err = run(project, GATE5,
                      bash_payload(project, "python -B -m pytest %s" % root.upper()))
        assert rc == 2, "a case variant of the declared root was allowed: %s" % err[:200]
    link = os.path.join(project, "surface-junction")
    # BYTES, not text: `mklink` answers in the console codepage, and decoding it as cp1252 raised
    # inside pytest's own thread hook. Nothing here reads the output -- only the exit code and
    # whether the link is there.
    made = subprocess.run(["cmd", "/c", "mklink", "/J", link, target],
                          capture_output=True) if os.name == "nt" else None
    if made is None or made.returncode != 0 or not os.path.isdir(link):
        pytest.skip("this host cannot make a junction, so the identity half cannot be measured")
    try:
        rc, err = run(project, GATE5,
                      bash_payload(project, "python -B -m pytest surface-junction"))
        assert rc == 2, (
            "a junction over the declared surface was allowed -- the reader is comparing text "
            "again: %s" % err[:200])
    finally:
        os.rmdir(link)


@pytest.mark.parametrize("line", ["%s -k alpha -k \"\"", "%s -k alpha -k=",
                                  "%s -m slow -m \"\""])
def test_gate5_lets_the_LAST_occurrence_of_an_option_decide(project, line):
    """B1' of verifier round 2: argparse keeps the last value, so the last occurrence decides.

    Measured on the three-test probe: `-k alpha -k ""` runs three of three tests -- the second
    occurrence cancels the first -- while this gate read the FIRST hit and answered rc 0.
    """
    root = _declared_roots(project)[0]
    rc, err = run(project, GATE5,
                  bash_payload(project, "python -B -m pytest " + line % root))
    assert rc == 2, "%r bought a full run" % (line % root)
    assert "WHOLE declared test surface" in err, err[:300]


def test_gate5_still_reads_a_narrowing_last_occurrence_as_a_selection(project):
    """The other direction of the same rule: `-k "" -k alpha` really does narrow."""
    root = _declared_roots(project)[0]
    rc, err = run(project, GATE5,
                  bash_payload(project, 'python -B -m pytest %s -k "" -k alpha' % root))
    assert rc == 0, "a line whose last -k selects was refused: %s" % err[:300]


def _suite_outside(base, name="pytestprobe"):
    """A little pytest suite that lies OUTSIDE the project under test.

    This is the shape CLAUDE.md prescribes for every red-first rig -- "restore the defect in a clone
    OUTSIDE the repo, see red" -- so it is also the shape gate 5 must not refuse: a place this
    reader can find and that is not this repository is decidably not the declared surface.
    """
    suite = os.path.join(base, name, "suite")
    os.makedirs(suite, exist_ok=True)
    with open(os.path.join(suite, "test_1.py"), "w", encoding="utf-8") as handle:
        handle.write("def test_a():\n    pass\n")
    return suite


def test_gate5_lets_a_rig_run_a_suite_that_lies_outside_this_repository(
        project, outside_the_home_directory):
    """F10 of verifier round 3: a place the reader CAN find and that is not this repo is a selection.

    Measured before this: `pytest "<scratch>/suite"` and even a single file in it came back rc 2 as
    UNPLACEABLE -- so once gate 5 is registered, every red-first rig this repo's own CLAUDE.md
    prescribes was refused through the Bash tool. Three shapes, because a rig runs all three.
    """
    suite = _suite_outside(outside_the_home_directory)
    root = _declared_roots(project)[0]
    for target in (suite, os.path.join(suite, "test_1.py"),
                   os.path.join(suite, "test_1.py") + "::test_a",
                   # the same property from the other side: two levels up and down lands on a
                   # `tools` that is NOT this repo's, and the reader can find where it is
                   os.path.join(project, "%s/../../%s" % (root, root))):
        rc, err = run(project, GATE5,
                      bash_payload(project, 'python -B -m pytest "%s"'
                                   % target.replace("\\", "/")))
        assert rc == 0, "a rig run outside this repo was refused (%r): %s" % (target, err[:300])


def test_gate5_still_sees_a_link_from_outside_into_the_declared_surface(
        project, outside_the_home_directory):
    """The claim the narrowing rests on, measured rather than argued.

    Narrowing "outside the repo" to a selection would open a door if a word outside could REACH the
    surface -- a junction is exactly that. It does not: the identity reader answers before the
    outside-ness question is ever asked, so the link is the surface it points at.
    """
    root = _declared_roots(project)[0]
    target = os.path.join(project, *root.split("/"))
    link = os.path.join(outside_the_home_directory, "into-the-surface")
    if os.path.isdir(link):
        os.rmdir(link)
    made = subprocess.run(["cmd", "/c", "mklink", "/J", link, target],
                          capture_output=True) if os.name == "nt" else None
    if made is None or made.returncode != 0 or not os.path.isdir(link):
        pytest.skip("this host cannot make a junction, so this claim cannot be measured here")
    try:
        rc, err = run(project, GATE5,
                      bash_payload(project, 'python -B -m pytest "%s"' % link.replace("\\", "/")))
        assert rc == 2, "a junction from outside INTO the declared surface was allowed"
        assert "WHOLE declared test surface" in err, err[:300]
    finally:
        os.rmdir(link)


def test_gate5_keeps_refusing_only_what_it_really_cannot_place(project):
    """What stays unplaceable after the narrowing -- the H153 list, driven.

    Each of these climbs to a filesystem root without finding anything, or names a position this
    reader cannot compute at all. They stay rc 2 with the unplaceable sentence, which is the
    fail-closed direction: what this gate cannot place, it does not wave through.
    """
    root = _declared_roots(project)[0]
    for target in ("C:%s" % root,                       # drive-relative: per-drive shell state
                   "/c/Offline Repos/AgentAndSkills/%s" % root,   # a shell's path, not Windows'
                   "//server/share/proj/tests",         # a share nobody serves
                   "Q:/not-mounted/tests"):             # a drive that is not there
        rc, err = run(project, GATE5,
                      bash_payload(project, 'python -B -m pytest "%s"' % target))
        assert rc == 2, "%r was waved through" % target
        assert "could not be placed against this repository" in err, (target, err[:300])
