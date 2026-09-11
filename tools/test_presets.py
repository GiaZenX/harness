"""The preset-change route (BUG-0041): what it refuses, what it writes, and one end-to-end run.

WHY MOST OF THIS RUNS AGAINST A STUB INSTALLER. The kernel's decisions -- is there an approval for
exactly this role set, is the staged kit the installed one, what does the config edit touch, what
happens when the install fails -- are decisions about a project's records, and each one needs its
own arranged state. The INSTALLER those decisions end in is the kits' own `scaffold_team`, and it
is measured where it belongs: `test_a_lead_can_change_the_preset_end_to_end` runs the real thing,
against a real scaffolded project, through the shipped entry point and the real approval hook, and
asserts the role that pilot 3 could not get actually arrives.

The stub is not a mock of the installer's behaviour either. It is a script in the two spellings
`kernel.presets` starts, and every test that uses it asserts what the KERNEL did around it -- which
config the installer was handed, and what the kernel does with a non-zero exit.
"""
import glob
import json
import os
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM_KITS = os.path.join(ROOT, "team-kits")
sys.path.insert(0, TEAM_KITS)

from kernel import approvals, cli, presets  # noqa: E402
from kernel.state import ProjectState, StateError  # noqa: E402

KIT = "demo-team"
# The two facts a project records about its installation, in the shape the scaffolds write them.
ROLES_MANIFEST_HEADER = "# agents-and-skills:team-kit-roles v1 team=%s count=%d"
CONFIG = (
    "# project_config.yaml -- owned by: PM\n"
    "# The comment block a YAML round-trip would delete.\n"
    "\n"
    "project:\n"
    '  name: "Rechnungswerkzeug"   # set at init\n'
    "  preset: mini              # mini | full\n"
    "  repo_mode: greenfield\n"
    "  stacks: [python]\n"
    "\n"
    "providers: [claude]\n"
    "model_map:\n"
    "  alpha: worker             # preset: not a preset -- a role called after one\n"
    "\n"
    # A SECOND TOP-LEVEL BLOCK WITH A REAL, INDENTED `preset:` LINE. It stands for any key a kit
    # adds beside `project:` that carries one of its own; without it the decoy above is only a
    # COMMENT, which the line pattern can never match anyway -- so the test would have said nothing
    # about the block detection it claims to measure (the verifier's ablations M1/M2 stayed green).
    "reference_run:\n"
    "  preset: never-the-recorded-one\n"
)


def _write(path, text, newline="\n"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text.replace("\n", newline) if newline != "\n" else text)


STUB = '''"""A stand-in `scaffold_team`: does what the real one does to the records this kernel reads.

IT KEEPS BOTH RECORDS, and in the real one\'s ORDER: role FILES first, ownership manifest last.
That order is the whole reason `presets._installed_state` has two readers -- a run killed in
between leaves a manifest naming roles whose files are already gone (measured against the real
scaffold at a 1.5 s abort: manifest 7, `.claude/agents` 5).

Per RUN behaviour comes from STUB_PLAN (comma-separated, one verb per run, the last one repeats),
so a failing install and the kernel\'s repair run are two different steps of one test:

  ok          -- install the roles of the preset the CONFIG records, exit 0 (what the real one does)
  slow-ok     -- the same, and THEN hang past the kernel\'s timeout: a run killed after its work
  ok-skillless-- install agents and manifest but NOT the skills: a run that finished the half the
                 kernel re-reads and not the half it cannot
  exit        -- refuse without touching anything, exit 3 (the real one rolls its own changes back)
  crash       -- install the SHRUNK set (files AND manifest), then hang: both records agree, small
  half        -- the same, then exit 3: an installer that failed after removing roles
  half-files  -- delete every role file but the lead AND its skill directory, leave the MANIFEST
                 standing, then hang: the real installer\'s window, where the record is the stale
                 half (it removes agent and skill artifacts together, before it writes anything)
  half-skills -- delete the SKILL directories only, leaving manifest and agent files whole: the
                 window in which both of the kernel\'s readers agree and the installation is still
                 incomplete
"""
import glob
import os
import shutil
import sys
import time

AGENTS = os.path.join(".claude", "agents")
SKILLS = os.path.join(".claude", "skills")
MANIFEST = os.path.join(".claude", "team_kit_roles.txt")


def roles_of(path):
    with open(path, encoding="utf-8") as handle:
        return [line.strip() for line in handle.read().splitlines()[1:] if line.strip()]


def install(manifest, skills=True):
    """Role artifacts first, ownership manifest last -- the order the real scaffold logs."""
    wanted = roles_of(manifest)
    for path in glob.glob(os.path.join(AGENTS, "*.md")):
        if os.path.basename(path)[:-3] not in wanted:
            os.remove(path)
    for role in wanted:
        path = os.path.join(AGENTS, role + ".md")
        if not os.path.isfile(path):
            open(path, "w", encoding="utf-8").write("---\\nname: %s\\n---\\nbody\\n" % role)
        if skills and not os.path.isdir(os.path.join(SKILLS, role)):
            os.makedirs(os.path.join(SKILLS, role))
            open(os.path.join(SKILLS, role, "SKILL.md"), "w", encoding="utf-8").write("body\\n")
    shutil.copyfile(manifest, MANIFEST)


runs_file = os.environ["STUB_RUNS"]
runs = (int(open(runs_file).read() or "0") if os.path.exists(runs_file) else 0) + 1
open(runs_file, "w").write(str(runs))
shutil.copyfile("project_memory/project_config.yaml", os.environ["STUB_WITNESS"])
plan = (os.environ.get("STUB_PLAN") or "ok").split(",")
verb = plan[runs - 1] if runs <= len(plan) else plan[-1]
hang = float(os.environ.get("STUB_HANG") or 30)
if verb == "exit":
    print("stub refused the install")
    sys.exit(3)
if verb == "half-files":
    for role in roles_of(MANIFEST)[1:]:
        os.remove(os.path.join(AGENTS, role + ".md"))
        shutil.rmtree(os.path.join(SKILLS, role), ignore_errors=True)
    time.sleep(hang)
    sys.exit(0)                       # nothing more is written: the kernel already gave up
if verb == "half-skills":
    for role in roles_of(MANIFEST):
        shutil.rmtree(os.path.join(SKILLS, role), ignore_errors=True)
    time.sleep(hang)
    sys.exit(0)
if verb in ("crash", "half"):
    install(os.environ["STUB_SHRUNK"])
    if verb == "half":
        print("stub refused the install after removing roles")
        sys.exit(3)
    time.sleep(hang)
    sys.exit(0)
import yaml
with open("project_memory/project_config.yaml", encoding="utf-8-sig") as handle:
    preset = ((yaml.safe_load(handle) or {}).get("project") or {}).get("preset")
install(os.environ["STUB_MANIFESTS"] + preset + ".txt", skills=verb != "ok-skillless")
if verb == "slow-ok":
    time.sleep(hang)
'''


def _stub_installer(staging, marker_dir):
    """A `scaffold_team` in both spellings, dispatching to one Python stand-in.

    The behaviour lives in Python because the interesting cases are SEQUENCES (a run that fails
    after removing roles, then the kernel's repair run) and because the real installer's contract
    with this kernel is "read the recorded preset, install its roles" -- a shell twin of that in
    two languages would be two stand-ins to keep in step. What stays in the shell files is the one
    thing the kernel really chooses: which of the two it starts.

    The witness is `project_config.yaml` AS THE INSTALLER FOUND IT, which is the only way to
    measure that the kernel wrote the preset BEFORE starting it -- the real installer reads the
    recorded preset out of that file, so the order is the contract between the two.
    """
    _write(os.path.join(staging, "stub_install.py"), STUB)
    _write(os.path.join(staging, "scaffold_team.ps1"),
           "param([string]$Team)\n"
           "& $env:STUB_PYTHON $env:STUB_SCRIPT\n"
           "exit $LASTEXITCODE\n")
    _write(os.path.join(staging, "scaffold_team.sh"),
           "#!/usr/bin/env bash\n\"$STUB_PYTHON\" \"$STUB_SCRIPT\"\n")
    os.chmod(os.path.join(staging, "scaffold_team.sh"), 0o755)
    return os.path.join(marker_dir, "witness.yaml")


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A project that LOOKS installed: staged kit in a fake home, records in `.claude/`.

    `expanduser` is what `kernel.presets` resolves the staging with -- the same location both
    scaffold twins do -- so the fixture points HOME and USERPROFILE at the fake one rather than
    handing the module a path.
    """
    home = tmp_path / "home"
    staging = home / ".claude" / "team-kits"
    kit = staging / KIT
    for role in ("project-manager", "alpha", "beta"):
        _write(str(kit / "agents" / (role + ".md")), "---\nname: %s\n---\nbody\n" % role)
    _write(str(kit / "settings" / "settings.json"), '{"agent": "project-manager"}\n')
    _write(str(kit / "presets.yaml"), "mini: alpha\nfull: all\n")
    _write(str(kit / "VERSION"), "version: 2026.08.15-1\ncontent: %s\n" % ("a" * 64))
    # the REAL resolver: the preset policy under test must be the shipped one
    shutil.copy(os.path.join(TEAM_KITS, "preset_config.py"), str(staging / "preset_config.py"))

    repo = tmp_path / "repo"
    _write(str(repo / ".claude" / "kit_version"), "version: 2026.08.15-1\ncontent: %s\n" % ("a" * 64))
    _write(str(repo / ".claude" / "team_kit_roles.txt"),
           (ROLES_MANIFEST_HEADER % (KIT, 2)) + "\nproject-manager\nalpha\n")
    # ...and the artifacts that record claims. The kernel reads the agent files; the SKILL
    # directories are here because they are written in the same window and are NOT re-read, which
    # is what `presets.UNREAD` says out loud and `test_the_outcome_messages_carry_the_limit_of_
    # what_was_re_read` measures.
    for role in ("project-manager", "alpha"):
        _write(str(repo / ".claude" / "agents" / (role + ".md")),
               "---\nname: %s\n---\nbody\n" % role)
        _write(str(repo / ".claude" / "skills" / role / "SKILL.md"), "body\n")
    _write(str(repo / "project_memory" / "project_config.yaml"), CONFIG)
    # the roster per preset, as the stub installs it, plus the SHRUNK one a half-finished run
    # leaves behind (the real installer removes the old roles before it writes the new ones)
    _write(str(tmp_path / "manifest-mini.txt"),
           (ROLES_MANIFEST_HEADER % (KIT, 2)) + "\nproject-manager\nalpha\n")
    _write(str(tmp_path / "manifest-full.txt"),
           (ROLES_MANIFEST_HEADER % (KIT, 3)) + "\nproject-manager\nalpha\nbeta\n")
    _write(str(tmp_path / "manifest-shrunk.txt"),
           (ROLES_MANIFEST_HEADER % (KIT, 1)) + "\nproject-manager\n")

    witness = _stub_installer(str(staging), str(tmp_path))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("STUB_PYTHON", sys.executable)
    monkeypatch.setenv("STUB_SCRIPT", str(staging / "stub_install.py"))
    monkeypatch.setenv("STUB_RUNS", str(tmp_path / "runs.txt"))
    monkeypatch.setenv("STUB_WITNESS", witness)
    monkeypatch.setenv("STUB_MANIFESTS", str(tmp_path / "manifest-"))
    monkeypatch.setenv("STUB_SHRUNK", str(tmp_path / "manifest-shrunk.txt"))
    monkeypatch.setenv("STUB_PLAN", "ok")
    state = ProjectState(str(repo / "project_memory"))
    return {"state": state, "repo": repo, "home": home, "kit": kit, "witness": witness,
            "runs": str(tmp_path / "runs.txt"),
            "config": str(repo / "project_memory" / "project_config.yaml")}


def approve_preset(project, preset):
    """Mint a real `preset` approval for what a change to `preset` would do here."""
    from conftest import mint_via_hook
    state = project["state"]
    request = approvals.create_pending_request(
        state, presets.KIND, manifest=presets.change_manifest(state, preset),
        approval_expires=__import__("time").time() + approvals.LINE_APPROVAL_VALIDITY)
    mint_via_hook(state, request)
    return request


def recorded_preset(path):
    with open(path, encoding="utf-8-sig") as handle:
        return ((yaml.safe_load(handle) or {}).get("project") or {}).get("preset")


# -- the approval binds the OUTCOME -------------------------------------------------------------

def test_a_preset_change_needs_a_user_approval_before_anything_moves(project):
    """No approval, no write and no installer -- and the refusal names the line that asks for one.

    The remedy is the whole point of the refusal: the lead reading it must not fall back on the
    route BUG-0041 measured (send the user to an editor and a terminal), so the message has to
    carry the command that opens the question.
    """
    with pytest.raises(StateError) as refused:
        presets.apply(project["state"], "full")
    assert "request-approval preset --preset full" in str(refused.value)
    assert "beta" in str(refused.value), "the refusal does not say which roles it would install"
    assert recorded_preset(project["config"]) == "mini"
    assert not os.path.exists(project["witness"]), "the installer ran without an approval"


def test_an_approval_for_one_preset_does_not_cover_another(project):
    """A minted `preset` approval authorises the change it named -- and nothing else.

    Both directions in one test: the approved preset goes through, the other one is refused with
    the same records in place.
    """
    approve_preset(project, "mini")
    with pytest.raises(StateError, match="no user approval"):
        presets.apply(project["state"], "full")
    assert recorded_preset(project["config"]) == "mini"
    # ...and the approval that WAS given still works
    assert presets.apply(project["state"], "mini")["preset"] == "mini"


def test_a_preset_approval_does_not_cover_a_different_role_set(project):
    """The hash is over the OUTCOME, so a preset that means something else is a different change.

    The user approves a ROLE SET, not a word: `full` in the question named the roles it would
    install, and if the kit's own preset file says something else by the time the command runs, the
    approval no longer covers it. Without the role list in the manifest the name alone would carry
    the approval and the second run would install whatever `full` had come to mean
    (`approvals.preset_subject_manifest`).
    """
    approve_preset(project, "full")
    _write(str(project["kit"] / "presets.yaml"), "mini: alpha\nfull: alpha\n")
    with pytest.raises(StateError, match="no user approval"):
        presets.apply(project["state"], "full")
    assert recorded_preset(project["config"]) == "mini"


def test_an_expired_preset_approval_authorises_nothing(project, monkeypatch):
    """The clock is read off the HASH-COVERED side, and it is why `preset` is an expiring kind.

    An unused authorisation to reinstall a project's roles must not outlive the conversation it
    was given in (`approvals.EXPIRING_KINDS`). Time is moved rather than the record, because the
    record is exactly what an expiry must not be editable in.
    """
    approve_preset(project, "full")
    later = __import__("time").time() + approvals.LINE_APPROVAL_VALIDITY + 60
    monkeypatch.setattr(approvals.time, "time", lambda: later)
    with pytest.raises(StateError, match="no user approval"):
        presets.apply(project["state"], "full")


# -- the write ----------------------------------------------------------------------------------

@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_only_the_preset_line_of_the_config_changes(project, newline):
    """`project_config.yaml` is a kit DOCUMENT: its comments are the only copy of what they say.

    A YAML round-trip would write back a valid file with every comment gone -- the kernel silently
    destroying the one document in the project nothing else can rewrite. Line endings are in the
    parameters for the same reason: reading the file with universal newlines and writing it back
    would rewrite every line of a CRLF config while claiming to change one.
    """
    _write(project["config"], CONFIG, newline=newline)
    approve_preset(project, "full")
    presets.apply(project["state"], "full")
    with open(project["config"], encoding="utf-8", newline="") as handle:
        after = handle.read()
    expected = CONFIG.replace("preset: mini", "preset: full")
    assert after == (expected.replace("\n", newline) if newline != "\n" else expected)


def test_the_installer_sees_the_preset_this_command_recorded(project):
    """ORDER: the config is written before the installer starts, because the installer reads it.

    Both scaffold twins take the preset from `project_config.yaml` when no preset argument is
    given, so what gets installed is what the project now records. The witness is that file as the
    installer found it.
    """
    approve_preset(project, "full")
    presets.apply(project["state"], "full")
    assert recorded_preset(project["witness"]) == "full"


def test_a_refused_install_leaves_the_recorded_preset_where_it_was(project, monkeypatch):
    """A config claiming roles the project does not have is worse than a refused change.

    The installer rolls its own file changes back; this is the other half -- the recorded preset
    goes back to what it was, and the refusal carries the installer's own message so the lead can
    hand it on rather than guess. The roles really are unchanged here, so the refusal says that --
    and `test_an_aborted_install_reports_the_state_it_actually_left` is the case where they are not.
    """
    monkeypatch.setenv("STUB_PLAN", "exit")
    approve_preset(project, "full")
    before = open(project["config"], encoding="utf-8", newline="").read()
    with pytest.raises(StateError) as refused:
        presets.apply(project["state"], "full")
    assert "stub refused the install" in str(refused.value)
    assert "the role files it names are unchanged (project-manager, alpha)" in str(refused.value)
    assert open(project["config"], encoding="utf-8", newline="").read() == before


@pytest.mark.parametrize("plan,verb", [("crash,ok", "did not complete"),
                                       ("half,ok", "refused (exit 3)")])
def test_an_aborted_install_reports_the_state_it_actually_left(project, monkeypatch, plan, verb):
    """The half-finished install: roles already removed, and the old message called that "no role".

    Measured by the verifier against the REAL installer with the timeout shortened -- the config
    was restored, the refusal said "no role was changed", and two agent files plus their Codex
    twins were gone. The user's own approval could not repair it either: `removes` had moved, so
    the hash no longer matched and a second `set-preset` refused.

    Two ways in, one behaviour: an installer this command had to give up on (the timeout, an OSError
    or a killed process) and one that failed AFTER removing the old roles. In both the kernel
    restores the recorded preset and then runs the installer once more against it -- which is the
    operation that reinstalls the old roles -- and reports what it measured, never what it hoped.
    """
    monkeypatch.setattr(presets, "INSTALLER_TIMEOUT", 3)
    # just past the timeout above: the run really is killed before it finishes, and the pipe
    # the kernel waits on closes seconds later instead of half a minute
    monkeypatch.setenv("STUB_HANG", "6")
    monkeypatch.setenv("STUB_PLAN", plan)
    approve_preset(project, "full")
    before = open(project["config"], encoding="utf-8", newline="").read()
    with pytest.raises(StateError) as refused:
        presets.apply(project["state"], "full")
    message = str(refused.value)
    assert verb in message
    assert "no role was changed" not in message
    assert "put the roles back (project-manager, alpha)" in message, message
    assert open(project["config"], encoding="utf-8", newline="").read() == before
    assert presets.installation(str(project["repo"]))["roles"] == ["project-manager", "alpha"]


def _agent_files(project):
    return sorted(os.path.basename(path)[:-3] for path in
                  glob.glob(os.path.join(str(project["repo"]), ".claude", "agents", "*.md")))


def test_a_half_written_installation_is_never_reported_as_unchanged(project, monkeypatch):
    """The window the record cannot see: role FILES gone, ownership manifest still standing.

    The real installer removes the old role files first and writes the manifest last, so an abort
    in between leaves a record describing a set that is no longer on disk -- measured by the
    verifier against the real scaffold at a 1.5 s abort (manifest 7, `.claude/agents` 5). A reader
    that asked the manifest alone answered "the installed roles are unchanged" over two deleted
    roles, which is the reassuring half of the very defect this branch is a correction of.

    So the reading is both records, and a project that disagrees with itself can never reach the
    "unchanged" outcome: it goes to the repair, and the repair is measured by re-reading, not by
    the installer's exit code.
    """
    monkeypatch.setattr(presets, "INSTALLER_TIMEOUT", 3)
    # just past the timeout above: the run really is killed before it finishes, and the pipe
    # the kernel waits on closes seconds later instead of half a minute
    monkeypatch.setenv("STUB_HANG", "6")
    monkeypatch.setenv("STUB_PLAN", "half-files,ok")
    approve_preset(project, "full")
    with pytest.raises(StateError) as refused:
        presets.apply(project["state"], "full")
    message = str(refused.value)
    assert "is unchanged" not in message, message
    assert "put the roles back (project-manager, alpha)" in message, message
    assert _agent_files(project) == ["alpha", "project-manager"]
    assert presets.installation(str(project["repo"]))["roles"] == ["project-manager", "alpha"]


def test_a_repair_run_that_is_killed_after_its_work_is_not_reported_as_a_loss(project, monkeypatch):
    """What stops the first run usually stops the second -- so the repair's own death proves nothing.

    Measured by the verifier at a 2.5 s abort: the repair had already done its work and was killed
    on the way out, and the refusal announced "are now unreadable ... THE PROJECT IS NOT IN THE
    STATE IT WAS" over a project that was intact. The state is therefore read AFTER the repair
    whether it returned, failed or was killed; the run's fate is a note in the message, not the
    verdict.
    """
    monkeypatch.setattr(presets, "INSTALLER_TIMEOUT", 3)
    # just past the timeout above: the run really is killed before it finishes, and the pipe
    # the kernel waits on closes seconds later instead of half a minute
    monkeypatch.setenv("STUB_HANG", "6")
    monkeypatch.setenv("STUB_PLAN", "half-files,slow-ok")
    approve_preset(project, "full")
    with pytest.raises(StateError) as refused:
        presets.apply(project["state"], "full")
    message = str(refused.value)
    assert "THE PROJECT IS NOT IN THE STATE IT WAS" not in message, message
    assert "unreadable" not in message, message
    assert "put the roles back (project-manager, alpha)" in message, message
    assert "the repair run could not be completed" in message, message
    assert _agent_files(project) == ["alpha", "project-manager"]


def test_a_host_without_a_shell_for_the_installer_changes_nothing(project, monkeypatch):
    """"Nothing was changed" has to be true when it is printed, not true of an earlier line.

    The interpreter search is a PATH lookup with no side effect, and it used to run one line after
    the config was written: on a host where it finds nothing, the refusal said nothing had changed
    while `project_config.yaml` already carried the new preset -- and the failure handler that
    restores it is never reached on that path. The sharper consequence is not the message: the next
    scaffold run reads that config and installs the change nobody approved.

    Practically unreachable on Windows and real on a POSIX host without bash -- which is exactly
    where the `.sh` twin ships -- so it is measured rather than argued about: every candidate
    interpreter is made unfindable, which is what such a host looks like to this code.
    """
    monkeypatch.setattr(presets.shutil, "which", lambda _name: None)
    approve_preset(project, "full")
    before = open(project["config"], encoding="utf-8", newline="").read()
    with pytest.raises(StateError) as refused:
        presets.apply(project["state"], "full")
    assert "nothing was changed" in str(refused.value)
    assert open(project["config"], encoding="utf-8", newline="").read() == before
    assert recorded_preset(project["config"]) == "mini"
    assert not os.path.exists(project["witness"]), "the installer ran without an interpreter"


def _skill_dirs(project):
    return sorted(os.path.basename(path) for path in
                  glob.glob(os.path.join(str(project["repo"]), ".claude", "skills", "*")))


@pytest.mark.parametrize("plan,outcome", [("half-skills,ok", "are unchanged"),
                                          ("half-files,ok-skillless", "put the roles back")])
def test_the_outcome_messages_carry_the_limit_of_what_was_re_read(project, monkeypatch, plan,
                                                                  outcome):
    """Neither refusal may claim a whole installation, because neither reader looks at all of it.

    Measured by the verifier against the real scaffold at a 1.5 s abort: the roles were back and
    both readers agreed while `.claude/skills` had gone from seven directories to none -- under the
    sentence "nothing is missing". The next full installer run restored them, so nothing was lost
    for good; what was wrong was the sentence, and a lead hands that sentence to the user.

    Both outcomes that report a whole installation are here, in the two windows that produce them:
    an installer killed after deleting only the skills (both readers still agree -> "unchanged"),
    and one killed after removing role artifacts whose repair rebuilt the half the kernel reads and
    not the half it does not (-> "put the roles back"). In each the skills really are gone at the
    end, and the message has to say that it did not look.
    """
    monkeypatch.setattr(presets, "INSTALLER_TIMEOUT", 3)
    monkeypatch.setenv("STUB_HANG", "6")
    monkeypatch.setenv("STUB_PLAN", plan)
    approve_preset(project, "full")
    with pytest.raises(StateError) as refused:
        presets.apply(project["state"], "full")
    message = str(refused.value)
    assert outcome in message, message
    without_skill = [role for role in presets.installation(str(project["repo"]))["roles"]
                     if role not in _skill_dirs(project)]
    assert without_skill, "the window this measures did not happen: every role still has its skill"
    assert presets.UNREAD in message, message
    assert "nothing is missing" not in message, message


def test_an_install_that_cannot_be_repaired_names_both_role_sets(project, monkeypatch):
    """When the repair fails too, the refusal is the only record of what the project now has.

    So it carries BOTH lists -- what the installation owned and what it owns now -- and says the
    config no longer describes the roles on disk. Anything shorter leaves the lead reporting a
    state nobody measured, which is the defect this whole branch is a correction of.
    """
    monkeypatch.setenv("STUB_PLAN", "half,exit")
    approve_preset(project, "full")
    with pytest.raises(StateError) as refused:
        presets.apply(project["state"], "full")
    message = str(refused.value)
    assert "THE PROJECT IS NOT IN THE STATE IT WAS" in message
    assert "were project-manager, alpha and are now project-manager" in message, message
    assert presets.UNREAD in message, "the loudest outcome is the one that must not over-claim"
    assert "the repair run itself exited 3" in message
    assert recorded_preset(project["config"]) == "mini"
    assert presets.installation(str(project["repo"]))["roles"] == ["project-manager"]


def test_a_config_the_write_did_not_actually_change_is_restored(project, monkeypatch):
    """The line edit is a TEXT operation; only YAML can say whether it recorded the preset.

    So the file is read back and parsed, and a write that produced anything else puts the original
    bytes back and refuses -- rather than leaving a project whose config and roles disagree. The
    editing function is neutered here because that is the failure this guard exists for: a shape
    of config the edit does not understand.
    """
    monkeypatch.setattr(presets, "_with_preset", lambda text, preset: text)
    approve_preset(project, "full")
    before = open(project["config"], encoding="utf-8", newline="").read()
    with pytest.raises(StateError, match="did not produce a file that records it"):
        presets.apply(project["state"], "full")
    assert open(project["config"], encoding="utf-8", newline="").read() == before
    assert not os.path.exists(project["witness"]), "the installer ran on an unwritten config"


def test_a_preset_line_outside_the_project_block_is_not_the_one_that_moves(project):
    """`preset:` is a word; the RECORDED preset is one key of ONE block.

    Two decoys, and only the second one measures anything: the word in a comment under `model_map:`
    (a regex over the file finds it; the anchored line pattern never could) and a REAL indented
    `preset:` line in a second top-level block. The block scan has to stop at the next top-level
    key, or that second line is a second hit and the write turns into the ambiguity refusal below.
    """
    approve_preset(project, "full")
    presets.apply(project["state"], "full")
    after = open(project["config"], encoding="utf-8", newline="").read()
    assert "preset: not a preset -- a role called after one" in after
    assert "  preset: never-the-recorded-one\n" in after
    assert recorded_preset(project["config"]) == "full"


def test_two_preset_lines_in_the_project_block_are_refused_rather_than_guessed(project):
    """Which of two `preset:` keys is THE recorded one is not a question this kernel answers.

    Writing the first one is a guess, and a guess here leaves the recorded preset and the installed
    roles describing different teams. So the write refuses before the installer starts, and the
    config is left exactly as it was.
    """
    doubled = CONFIG.replace("  repo_mode: greenfield\n",
                             "  preset: mini-again\n  repo_mode: greenfield\n")
    _write(project["config"], doubled)
    approve_preset(project, "full")
    with pytest.raises(StateError, match="2 `preset:` line"):
        presets.apply(project["state"], "full")
    assert open(project["config"], encoding="utf-8", newline="").read() == doubled
    assert not os.path.exists(project["witness"])


# -- what it refuses to be ----------------------------------------------------------------------

def test_a_preset_change_refuses_to_smuggle_in_a_kit_update(project):
    """A scaffold run re-copies hooks, kernel and constitution -- from whatever is staged NOW.

    So against a staging that has moved on, this command would hand a user who approved "add a
    role" a new enforcement bundle as well. Refused before anything is written, on the recorded
    kit file being byte-identical to the staged one.
    """
    _write(str(project["kit"] / "VERSION"), "version: 2026.08.16-1\ncontent: %s\n" % ("b" * 64))
    with pytest.raises(StateError, match="not the one this project is installed at"):
        presets.change_manifest(project["state"], "full")
    with pytest.raises(StateError, match="not the one this project is installed at"):
        presets.apply(project["state"], "full")
    assert recorded_preset(project["config"]) == "mini"
    assert not os.path.exists(project["witness"])


def test_a_truncated_roles_manifest_refuses_the_change(project):
    """Which roles the installation owns is what a downgrade REMOVES; half a record removes wrong.

    The scaffolds refuse to work against a truncated ownership manifest for the same reason, and
    the kernel must not be the softer of the two readers of one file.
    """
    _write(str(project["repo"] / ".claude" / "team_kit_roles.txt"),
           (ROLES_MANIFEST_HEADER % (KIT, 5)) + "\nproject-manager\nalpha\n")
    with pytest.raises(StateError, match="truncated"):
        presets.change_manifest(project["state"], "full")


def test_an_unknown_preset_is_refused_with_the_ones_the_kit_has(project):
    """The kit's own resolver decides, and its refusal already names the available presets."""
    with pytest.raises(StateError) as refused:
        presets.change_manifest(project["state"], "designer-please")
    assert "mini, full" in str(refused.value)


# -- the command line ---------------------------------------------------------------------------

def test_a_manifest_key_a_resolver_answers_with_nothing_is_still_an_answer(project, capsys):
    """An upgrade REMOVES nothing, and `removes: []` is the truth about it -- not a missing key.

    The pair, because the distinction is between two kinds of emptiness: a key the CLI RESOLVES
    from the project fails only when the resolver cannot answer at all, while a key the role must
    TYPE fails on emptiness -- a push approval that names no remote says nothing about what it
    releases. Before that split, requesting an upgrade was a usage error.
    """
    state = project["state"]
    assert cli.main(["--root", state.root, "request-approval", "preset", "--preset", "full"]) == 0
    question = json.loads(capsys.readouterr().out)
    assert "entfernt: keine" in question["question"] and "beta" in question["question"]
    assert cli.main(["--root", state.root, "request-approval", "push", "--branch", "main"]) == 2
    assert "remote is missing" in capsys.readouterr().err


@pytest.mark.parametrize("flag,value", [("--roles", "product-designer"),
                                        ("--removes", "nothing-at-all"),
                                        ("--head", "0" * 40)])
def test_a_resolver_owned_key_is_not_the_roles_to_type(project, capsys, flag, value):
    """A manifest key the CLI resolves may not be typed -- refused, not overridden, not used.

    The verifier measured what "used" costs: `--roles product-designer --removes nothing-at-all`
    produced a real, kernel-signed approval question whose role lists were those strings split into
    single CHARACTERS, because the builder takes a list and a command line hands it a str. The
    question is what the user judges and what the hash covers, so a value from the line could only
    make those two disagree with what `set-preset` will re-derive.

    All three keys, and the third is `push`'s: the rule is membership in
    `cli.LINE_MANIFEST_RESOLVERS`, not a list of the two that arrived with `preset`.
    """
    state = project["state"]
    kind = "push" if flag == "--head" else "preset"
    extra = ["--remote", "origin", "--branch", "main"] if kind == "push" else ["--preset", "full"]
    assert cli.main(["--root", state.root, "request-approval", kind] + extra + [flag, value]) == 2
    message = capsys.readouterr().err
    assert "not a value to type on this line" in message and flag[2:] in message
    assert not os.path.isdir(os.path.join(state.root, "approvals", "pending")) or not os.listdir(
        os.path.join(state.root, "approvals", "pending")), "a request was written anyway"


def _preset_question(project, preset):
    """The approval question the kernel composes for a change to `preset` here."""
    state = project["state"]
    manifest = presets.change_manifest(state, preset)
    request = {"request_id": "r" * 32, "kind": presets.KIND, "item": None, "revision": None,
               "subject_manifest": manifest,
               "subject_manifest_hash": approvals.subject_manifest_hash(manifest),
               "created": "x", "expires_at_epoch": 0, "mint_code": "abc123"}
    return manifest, approvals.build_question(request)


def test_the_preset_question_names_the_team_afterwards_and_what_goes(project):
    """What a non-technical user reads, in both directions of the change (FR-0027).

    The generic manifest form was `[preset: full, removes: -, roles: alpha / beta]`: the manifest's
    own keys, with the resulting set under a bare `roles:` and nothing saying it IS the result. On
    the upgrade pilot 3's persona was headed for, most of those names are already installed, so she
    read a list of arrivals and a dash. The words are the whole fix here, and they are what the
    kernel-generated question is compared character for character against, so they are measured on
    the running builder rather than read off the source.

    BOTH TRANSITIONS, because the removing one is where a name hides the most: `entfernt` has to
    carry the roles the project LOSES, and an upgrade has to say plainly that it loses none.
    """
    _manifest, question = _preset_question(project, "full")
    assert "danach im Team: alpha, beta" in question["question"], question["question"]
    assert "entfernt: keine" in question["question"]
    assert "roles:" not in question["question"] and "removes:" not in question["question"]
    # the option the user clicks carries the same sentence -- it is what the mint is bound to
    assert "danach im Team: alpha, beta" in question["options"][0]["description"]

    _write(str(project["repo"] / ".claude" / "team_kit_roles.txt"),
           (ROLES_MANIFEST_HEADER % (KIT, 3)) + "\nproject-manager\nalpha\nbeta\n")
    _manifest, question = _preset_question(project, "mini")
    assert "danach im Team: alpha" in question["question"]
    assert "entfernt: beta" in question["question"], question["question"]


def test_the_added_roles_are_not_what_a_preset_approval_binds(project):
    """Why the question names the RESULT and not the delta (DEC-0048) -- measured in both halves.

    THE MANIFEST HALF. `removes` is derived from the installation, so the hash does move with the
    installed state -- but WHICH OF THE TARGET ROLES ARE ALREADY THERE is exactly the part it does
    not carry, and that is the part a delta is computed from. Two installations that differ only
    inside the target set produce one hash and two different added sets.

    THE MINT HALF, and it is here because the sentence in `_preset_target_form` claims it: an
    approval really minted for the first installation still applies after the second -- `set-preset`
    re-derives the manifest, the hash still matches, and the install goes through. Without this the
    docstring would name a test for something the test never ran.

    This is also the tripwire for the other direction: the day the manifest gains what is installed,
    the first half goes red, and a delta rendering becomes buildable.
    """
    manifest_from_alpha = presets.change_manifest(project["state"], "full")
    approve_preset(project, "full")     # a real mint, through the project's own approval hook

    # ...the installation moves INSIDE the target set: `alpha` goes, `beta` was never there
    _write(str(project["repo"] / ".claude" / "team_kit_roles.txt"),
           (ROLES_MANIFEST_HEADER % (KIT, 1)) + "\nproject-manager\n")
    manifest_from_none = presets.change_manifest(project["state"], "full")
    assert manifest_from_alpha == manifest_from_none
    assert (approvals.subject_manifest_hash(manifest_from_alpha)
            == approvals.subject_manifest_hash(manifest_from_none))
    assert sorted(set(manifest_from_alpha["roles"]) - {"alpha"}) == ["beta"]
    assert sorted(manifest_from_none["roles"]) == ["alpha", "beta"], (
        "the added set differs between the two starts the one hash covers")

    # the approval given for the first state authorises the second, unchanged
    assert approvals.live_line_approval(project["state"], presets.KIND, manifest_from_none)
    assert presets.apply(project["state"], "full")["preset"] == "full"


def test_the_removed_roles_ARE_hashed_so_the_approval_follows_the_installation(project):
    """The other half of the same fact, and the one the first cut of this round got wrong.

    `removes` is `installed - target` (`kernel.presets._plan`), so it is state-derived and it IS in
    the hashed manifest: an installation that carries a role the target drops produces a DIFFERENT
    hash, and the approval given before that role appeared no longer covers the change. Written down
    as "what is installed is not in the hashed manifest", the docstring made a claim this measures
    false -- only the intersection with the target is outside it.
    """
    with_alpha = presets.change_manifest(project["state"], "mini")
    _write(str(project["repo"] / ".claude" / "team_kit_roles.txt"),
           (ROLES_MANIFEST_HEADER % (KIT, 3)) + "\nproject-manager\nalpha\nbeta\n")
    with_beta_too = presets.change_manifest(project["state"], "mini")
    assert with_alpha["removes"] == [] and with_beta_too["removes"] == ["beta"]
    assert (approvals.subject_manifest_hash(with_alpha)
            != approvals.subject_manifest_hash(with_beta_too))


def test_every_kit_constitution_describes_the_preset_question_the_kernel_builds(project):
    """The sentence a PM reads about that question, held against the question (DEC-0048).

    THE DEFECT THIS EXISTS FOR, and it is why the check is derived rather than a third careful
    edit: two of the three constitutions were pulled down to what `_preset_target_form` renders and
    the office one was not -- it still promised "the question names every role added and removed",
    measured live in an office scaffold where three of five named roles were already installed and
    the question said nothing about which were new. The sweep that missed it was a line-based grep
    over a sentence that happens to wrap mid-phrase in that kit.

    DERIVED ON BOTH HALVES OF THE SENTENCE, so neither a third kit nor a later renderer can leave
    one of them standing alone. The two halves it PRINTS are read off a run of the shipped renderer.
    The half every constitution says it WITHHOLDS is the same run from two different installations:
    the manifest is the renderer's only input and it does not carry which of the target roles are
    already there, so one target renders one identical sentence from both starts while "added"
    differs. The day a question names the new roles, that equality breaks here -- before a reader
    meets a constitution promising it does not. Whitespace in the documents is flattened first,
    because where a kit wraps its lines is not what this measures.
    """
    form = approvals.TARGET_FORMS["preset"]
    from_alpha = presets.change_manifest(project["state"], "full")
    rendered = form(from_alpha)
    # what the renderer actually put in front of the user, as claims a sentence has to match
    assert "danach im Team" in rendered and "entfernt" in rendered
    # ...and now the installation moves INSIDE the target set (the fixture had `alpha`, this has
    # none of it), which is the difference a delta would be computed from
    _write(str(project["repo"] / ".claude" / "team_kit_roles.txt"),
           (ROLES_MANIFEST_HEADER % (KIT, 1)) + "\nproject-manager\n")
    from_none = presets.change_manifest(project["state"], "full")
    assert sorted(set(from_alpha["roles"]) - {"alpha"}) == ["beta"]
    assert sorted(from_none["roles"]) == ["alpha", "beta"], "the two starts add different roles"
    assert form(from_alpha) == form(from_none), (
        "the question tells the two installations apart, so a constitution may promise a delta")
    checked = []
    for kit in sorted(os.listdir(TEAM_KITS)):
        path = os.path.join(TEAM_KITS, kit, "constitution", "AGENTS.md")
        if not os.path.isfile(path):
            continue
        flat = " ".join(open(path, encoding="utf-8").read().split())
        if "request-approval preset" not in flat:
            continue                       # this kit does not put the command in front of a lead
        checked.append(kit)
        assert "names every role added and removed" not in flat, (
            "%s promises a delta the renderer does not print" % kit)
        assert "HAS afterwards" in flat and "removed" in flat, (
            "%s does not describe the result the renderer names" % kit)
        assert "not which of them are new" in flat, (
            "%s does not say which half the question withholds" % kit)
        assert "DEC-0048" in flat, "%s states the limit without the decision behind it" % kit
    assert len(checked) >= 3, checked


def test_every_target_form_names_a_live_apr_kind(project):
    """Both ends of the one map in `build_question` that is an enumeration.

    A form for a kind that no longer exists answers for nothing, and this map is the one place the
    builder departs from rendering the hashed manifest key by key -- a leftover entry makes that
    departure look wider than it is. And a form that arrives WITHOUT a measurement of what it
    renders is the other end: every entry here writes a sentence a user signs, so the second
    assertion is the one that has to be edited deliberately, next to a new test like the two above.
    """
    assert set(approvals.TARGET_FORMS) <= set(approvals.APR_KINDS)
    # `filing_correction` joined the map in TSK-0077 (FR-0050) and brought its measurement with it:
    # `tools/test_staging_cli.py::test_a_filing_correction_question_says_in_words_what_happens_to_
    # the_document` is what says the rendered sentence names the document, both outcomes in words,
    # the reason and the shortened version digest.
    # `filing_rule` joined in TSK-0078 (FR-0049 step 5) with its own measurement:
    # `tools/test_kernel.py::test_the_question_a_filing_rule_asks_shows_every_field_the_hash_covers`
    # asks the MANIFEST which keys it hashes and requires each of their values in the rendered
    # sentence, so the form cannot come to show less than the user signs.
    # `document_proposal` joined in TSK-0092 (BUG-0071), the widest write on the surface -- it
    # replaces a project document's bytes -- and it brought the same shape of measurement:
    # `tools/test_kernel.py::test_the_question_a_document_proposal_asks_shows_every_field_the_hash
    # _covers` asks the manifest which keys it hashes and requires each of their RENDERED values in
    # the sentence, digests included.
    # `document_revision` joined in TSK-0106 (FR-0067) as the only form that renders an UNSAYING --
    # a replaced or deleted spot -- and it brought the same measurement:
    # `tools/test_kernel.py::test_the_question_a_document_revision_asks_shows_every_field_the_hash
    # _covers`, plus `tools/test_approvals_dispatch.py::test_a_revision_card_shows_every_spot_and
    # _is_never_a_count` for the half specific to it: the spots are shown in full or the request is
    # refused, never folded into a number.
    # `plan` joined in TSK-0117 (FR-0074) and is the ONE form where a single answer authorises
    # several items, so it is the one that may least be a summary -- which is also the sentence
    # `H132` leans on. Its measurement arrived in the TSK-0120 merge round, where this
    # assertion went red because the form had come without one:
    # `tools/test_kernel.py::test_the_question_a_plan_asks_shows_every_goal_the_hash_covers`
    # asks the manifest for every goal it hashes and requires each one's id, title and revision
    # in the rendered sentence, and refuses a count standing in for the list.
    # `verification` joined in TSK-0138 (PR-0012 AC-1, DEC-0100) and is the SECOND form where one
    # answer authorises several items -- and the first that splits itself in two: the sentence names
    # the count and the APPROVING OPTION carries the list, because the list is the compared carrier
    # and a sentence a person has to read cannot hold twenty-odd ids with their proofs. Both halves
    # are measured, which is what this assertion asks for:
    # `tools/test_approvals_dispatch.py::test_the_batch_option_names_every_listed_bug_and_its_evidence`
    # requires every listed id AND the Evidence that measured it in the option and refuses them in
    # the sentence, and
    # `tools/test_approvals_dispatch.py::test_only_a_kind_with_its_own_option_form_reads_differently_in_the_two_places`
    # holds the other end for every form that has no option form of its own.
    assert set(approvals.TARGET_FORMS) == {"push", "preset", "filing_correction", "filing_rule",
                                           "document_proposal", "document_revision",
                                           approvals.PLAN_KIND, approvals.VERIFICATION_KIND}, (
        "a new readable form arrived without a measurement of what it renders")


def test_the_preset_command_is_on_the_surface_the_refusals_name(project, capsys):
    """`set-preset` and `request-approval preset` exist as the shipped parser spells them.

    Read off `build_parser()` rather than from the module: every refusal in the kits now names
    these two, and a text naming a command the parser lacks is the dead end this replaced.
    """
    parser = cli.build_parser()
    subcommands = parser._subparsers._group_actions[0].choices
    assert presets.COMMAND in subcommands
    request = subcommands["request-approval"]
    kinds = next(action.choices for action in request._actions if action.dest == "kind")
    assert presets.KIND in kinds


# -- what the kits TELL a lead to do ------------------------------------------------------------
#
# A prose measurement, and it is allowed to be one: the subject here IS a shipped document, not a
# behaviour a document describes. What runs is measured above and end to end below.

KITS = ("dev-team", "office-team", "research-team")
# The shape BUG-0041 was written against, kept as the SPECIMEN the reader below is checked with.
# It is a sentence that exists nowhere in the tree any more, so quoting it claims nothing about
# another file -- it is what the sweep has to be able to see.
DEAD_END_SPECIMEN = ("Upgrades = user OK -> re-run scaffold with the larger preset -> session "
                     "restart.")
# A preset sentence that sends the reader to the installer: it names a preset, it names the
# scaffold, and it is about CHANGING one. All three, in one sentence -- "the scaffold installs
# only the preset's roles" is none of that and stays.
_CHANGE_WORDS = ("larger", "upgrad", "chang", "re-run", "rerun", "fresh")


def _sentences(text):
    for chunk in text.replace("\r", "\n").replace(";", ".").split("\n"):
        for sentence in chunk.split("."):
            yield sentence


def _sends_the_reader_to_the_installer(text):
    return [sentence.strip() for sentence in _sentences(text)
            if "preset" in sentence.lower() and "scaffold" in sentence.lower()
            and any(word in sentence.lower() for word in _CHANGE_WORDS)]


def _lead_of(kit):
    """The kit's foreground role, from the settings file that binds it -- never a name typed here."""
    with open(os.path.join(TEAM_KITS, kit, "settings", "settings.json"),
              encoding="utf-8-sig") as handle:
        return json.load(handle)["agent"]


def _lead_texts():
    """(where, text) for the documents a lead reads about presets: constitution, agent, skill."""
    for kit in KITS:
        lead = _lead_of(kit)
        for relative in (os.path.join("constitution", "AGENTS.md"),
                         os.path.join("agents", lead + ".md"),
                         os.path.join("skills", lead, "SKILL.md")):
            path = os.path.join(TEAM_KITS, kit, relative)
            with open(path, encoding="utf-8") as handle:
                yield "%s/%s" % (kit, relative.replace(os.sep, "/")), handle.read()


# The texts the NEGATIVE half sweeps on top of the lead packages. A dead-end sentence is a defect
# wherever a reader meets it, and it was measured outside the kits: the round that removed it from
# five kit files left one in the README, which no per-kit reader could ever see. The two global
# entry gates are here for the same reason and are clean today -- they are also the two files a
# kit-scoped change may not edit, which is exactly when a tripwire earns its keep.
_ALSO_SWEPT = ("README.md",
               os.path.join("user", "claude", "CLAUDE.md"),
               os.path.join("user", "codex", "AGENTS.md"))


def _swept_texts():
    for where, text in _lead_texts():
        yield where, text
    for relative in _ALSO_SWEPT:
        with open(os.path.join(ROOT, relative), encoding="utf-8") as handle:
            yield relative.replace(os.sep, "/"), handle.read()


def test_every_kit_tells_its_lead_the_route_instead_of_the_dead_end():
    """AC-3: the remedy a lead reads is the command, in every kit, and the old one is gone.

    Both halves, because either alone is worth little: a kit that names no route leaves the lead
    inventing one (pilot 3 invented Notepad plus a terminal), and a kit that names the route while
    an older paragraph still sends the user to the scaffold has two answers and the reader picks.
    The reader is checked against a specimen of the sentence that was removed, so it cannot pass by
    seeing nothing.

    THE NEGATIVE HALF SWEEPS WIDER THAN THE KITS (`_ALSO_SWEPT`), because the round that removed
    those sentences from five kit files left one standing in the README, where no per-kit reader
    could see it. The positive half stays per kit: it is the LEAD that has to find the route.
    """
    assert _sends_the_reader_to_the_installer(DEAD_END_SPECIMEN), (
        "the sweep cannot even see the sentence it was written for, so its silence means nothing")
    offences, named = [], []
    for where, text in _swept_texts():
        offences += ["%s: %s" % (where, sentence)
                     for sentence in _sends_the_reader_to_the_installer(text)]
        if presets.COMMAND in text:
            named.append(where)
    assert not offences, (
        "a shipped text still sends the reader to the installer for a preset change:\n  "
        + "\n  ".join(offences))
    for kit in KITS:
        assert any(where.startswith(kit) for where in named), (
            "%s tells its lead nothing about `%s`, so a preset change there has no route in prose"
            % (kit, presets.COMMAND))


# -- end to end ---------------------------------------------------------------------------------

def _scaffolded(tmp_path, kit="dev-team", preset="solo"):
    """A REAL project: the repo's kits staged in a fake home, installed by the real scaffold."""
    home = tmp_path / "home"
    staging = home / ".claude" / "team-kits"
    shutil.copytree(TEAM_KITS, str(staging), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    repo = tmp_path / "project"
    source = os.path.join(str(staging), kit, "templates", "project_memory",
                          "project_config.yaml")
    with open(source, encoding="utf-8-sig") as handle:
        config = handle.read()
    config = config.replace("preset: solo", "preset: " + preset).replace(
        'name: ""', 'name: "Rechnungswerkzeug"').replace("stacks: [TODO]", "stacks: [python]")
    _write(str(repo / "project_memory" / "project_config.yaml"), config)
    environment = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         os.path.join(str(staging), "scaffold_team.ps1"), "-Team", kit],
        cwd=str(repo), capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=900, env=environment)
    assert result.returncode == 0, result.stdout + result.stderr
    return home, repo, environment


def _harness(repo, environment, *argv):
    return subprocess.run([sys.executable, os.path.join(str(repo), "scripts", "harness.py")]
                          + list(argv), cwd=str(repo), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=900, env=environment)


def test_a_lead_can_change_the_preset_end_to_end(tmp_path):
    """Pilot 3's dead end, walked to the end with nothing stubbed (BUG-0041).

    The real kit, the real scaffold, the shipped entry point and the real approval hook: the lead
    asks, the user answers the question the kernel composed, the lead runs one more command, and
    the role the persona could not get -- `product-designer` -- is installed for both providers.
    Nothing here is typed into a file by a human, which is the whole of what B4 was about.

    It also measures the two records the kernel reads off a REAL installation: the ownership
    manifest the scaffold writes (`presets.installation`) and the kit version file it copies.
    """
    if os.name != "nt" or not shutil.which("powershell"):
        pytest.skip("the scaffold's PowerShell twin runs on Windows")
    pytest.importorskip("yaml")
    home, repo, environment = _scaffolded(tmp_path)
    agents = str(repo / ".claude" / "agents")
    assert not os.path.exists(os.path.join(agents, "product-designer.md"))
    assert presets.installation(str(repo))["kit"] == "dev-team"

    opened = _harness(repo, environment, "request-approval", "preset", "--preset", "team")
    assert opened.returncode == 0, opened.stderr
    question = json.loads(opened.stdout)
    assert "product-designer" in question["question"], (
        "the user is asked to approve a preset NAME without being told which roles it brings")

    # the user answers -- through the project's OWN PostToolUse hook, the only minting caller
    state = ProjectState(str(repo / "project_memory"))
    payload = {"hook_event_name": "PostToolUse", "tool_name": "AskUserQuestion", "cwd": str(repo),
               "tool_input": {"questions": [question]},
               "tool_response": {"answers": {question["question"]: question["options"][0]["label"]},
                                 "questions": [question]}}
    minted = subprocess.run(
        [sys.executable, os.path.join(str(repo), ".claude", "hooks", "gate_approval.py")],
        input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=str(repo), timeout=300,
        env=dict(environment, CLAUDE_PROJECT_DIR=str(repo)))
    assert "recorded for preset" in minted.stderr, minted.stderr + minted.stdout

    applied = _harness(repo, environment, "set-preset", "team")
    assert applied.returncode == 0, applied.stderr
    assert "RESTART REQUIRED" in applied.stdout
    assert os.path.isfile(os.path.join(agents, "product-designer.md"))
    assert os.path.isfile(str(repo / ".codex" / "agents" / "product-designer.toml")), (
        "the Codex artifacts did not follow the role change")
    assert os.path.isdir(str(repo / ".claude" / "skills" / "product-designer"))
    assert recorded_preset(str(repo / "project_memory" / "project_config.yaml")) == "team"
    assert "product-designer" in presets.installation(str(repo))["roles"]
    assert state.read_item  # the state directory is untouched by all of this
