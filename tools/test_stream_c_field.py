"""Field repairs of order 7, stream C (TSK-0155): bugs the synaipse project hit, each measured
on the path that runs -- a REAL scaffolded project, the installed hooks as processes, the shipped
entry point -- and each test names the bug it closes (DEC-0100).

The scaffold helpers are `tools/test_kitupdate.py`'s, so an installation here is made exactly the
way that suite makes one. BUG-0317's test builds V1 stores and lives in `tools/test_migrate.py`,
the file the V1-monolith path sweep of `tools/test_hooks.py` exempts for exactly that.
"""
import json
import os
import shutil
import subprocess
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM_KITS = os.path.join(ROOT, "team-kits")
sys.path.insert(0, TEAM_KITS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kernel import hashing, kitupdate  # noqa: E402
from test_kitupdate import KITS, TWINS, _kit_hook_module, _run_installer, _scaffolded  # noqa: E402

WINDOWS_ONLY = pytest.mark.skipif(
    os.name != "nt" or not shutil.which("powershell"),
    reason="the scaffold's PowerShell twin runs on Windows")


def _env(home):
    return dict(os.environ, HOME=str(home), USERPROFILE=str(home))


def _harness(repo, home, *argv):
    """The shipped entry point of the installed project, as a role types it."""
    return subprocess.run([sys.executable, "-B", os.path.join(str(repo), "scripts", "harness.py")]
                          + list(argv), cwd=str(repo), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=600, env=_env(home))


def _installed_hook(repo, name, payload, home=None):
    """One INSTALLED hook of the project as a process -- its own kernel, nothing borrowed."""
    environment = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))
    environment.pop("HARNESS_KERNEL_PATH", None)
    if home is not None:
        environment.update(_env(home))
    return subprocess.run([sys.executable, "-B", os.path.join(str(repo), ".claude", "hooks", name)],
                          input=json.dumps(payload), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=str(repo), timeout=120,
                          env=environment)


def _shell(repo, name, command, agent=None):
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(repo),
               "tool_input": {"command": command}}
    if agent:
        payload.update(agent_type=agent, agent_id="a0001")
    return _installed_hook(repo, name, payload)


def _restamp(home, kit):
    """Re-stamp a STAGED kit after the test edited it -- what `bump_kit_version` does to a release."""
    directory = os.path.join(str(home), ".claude", "team-kits", kit)
    path = os.path.join(directory, "VERSION")
    with open(path, "rb") as handle:
        lines = handle.read().decode("utf-8").splitlines()
    lines = [("version: 2099.01.01-1" if line.startswith("version:") else
              "content: " + hashing.kit_hash(directory) if line.startswith("content:") else line)
             for line in lines]
    with open(path, "wb") as handle:
        handle.write(("\n".join(lines) + "\n").encode("utf-8"))


def _pyc_under(directory):
    return sorted(os.path.relpath(os.path.join(current, name), str(directory))
                  for current, _dirs, files in os.walk(str(directory)) for name in files
                  if name.endswith(hashing.BYTECODE_SUFFIXES))


# -- BUG-0310: bytecode in the installed kernel ---------------------------------------------------

@pytest.mark.parametrize("spelling", [".claude", ".CLAUDE"])
def test_importing_the_installed_kernel_without_b_writes_no_bytecode_bug_0310(tmp_path, spelling):
    """AC-1: ANY importer, not only the routes the kit starts. The field route was a project's own
    process putting `.claude` on its path without `-B`; this is that process, with the interpreter's
    own switch and environment variable both off, over an installed copy of the kernel.

    AND ANY SPELLING OF THAT PATH the filesystem resolves to the same directory: through `.CLAUDE`
    the name comparison `kernel/__init__.py` used to make cached the package on this host
    (TSK-0156 verify round 1, F5). Where the filesystem tells the two spellings apart there is no second
    route to measure, and the case is skipped for that reason, read off the filesystem itself.
    """
    claude = tmp_path / ".claude"
    shutil.copytree(os.path.join(TEAM_KITS, "kernel"), str(claude / "kernel"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if not (tmp_path / spelling).is_dir():
        pytest.skip("this filesystem keeps %s and .claude apart" % spelling)
    environment = dict(os.environ)
    environment.pop("PYTHONDONTWRITEBYTECODE", None)
    environment.pop("PYTHONPYCACHEPREFIX", None)
    result = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, %r); import kernel; "
         "import kernel.backlog_types, kernel.hashing; print(sys.dont_write_bytecode)" % spelling],
        cwd=str(tmp_path), capture_output=True, text=True, env=environment, timeout=120)
    assert result.returncode == 0, result.stderr
    assert _pyc_under(claude / "kernel") == [], _pyc_under(claude / "kernel")


@WINDOWS_ONLY
def test_a_session_prunes_bundle_caches_and_the_spawn_check_trusts_again_bug_0310(tmp_path):
    """AC-2: the door removes ONLY tool leftovers and the bundle check is green again -- asked of
    the installed `_kernel.bundle_trust`, which is what the spawn gate refuses on. A planted `.py`
    is not a leftover: it stays, and the door says the bundle still differs (rc 1).
    """
    home, repo, _environment = _scaffolded(tmp_path)
    cache = repo / ".claude" / "kernel" / "__pycache__"
    cache.mkdir()
    (cache / "state.cpython-313.pyc").write_bytes(b"\x00" * 16)
    (repo / ".claude" / "hooks" / "stray.pyc").write_bytes(b"\x00" * 16)
    probe = ("import sys; sys.path.insert(0, sys.argv[1]); import _kernel; "
             "print(_kernel.bundle_trust(sys.argv[2]).withdrawn)")

    def withdrawn():
        out = subprocess.run([sys.executable, "-B", "-c", probe,
                              str(repo / ".claude" / "hooks"), str(repo)],
                             capture_output=True, text=True, cwd=str(repo), timeout=120)
        assert out.returncode == 0, out.stderr
        return out.stdout.strip().splitlines()[-1]

    assert withdrawn() == "True", "the planted cache did not move the bundle -- nothing measured"
    pruned = _harness(repo, home, kitupdate.UPKEEP_COMMAND, kitupdate.PRUNE_CACHES)
    assert pruned.returncode == 0, pruned.stdout + pruned.stderr
    assert "MATCHES" in pruned.stdout, pruned.stdout
    assert not cache.exists() and not (repo / ".claude" / "hooks" / "stray.pyc").exists()
    assert withdrawn() == "False"

    planted = repo / ".claude" / "kernel" / "planted.py"
    planted.write_text("print('not a cache')\n", encoding="utf-8")
    refused = _harness(repo, home, kitupdate.UPKEEP_COMMAND, kitupdate.PRUNE_CACHES)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert planted.exists(), "the door deleted something that is not a tool leftover"
    assert "kernel/planted.py" in refused.stdout, refused.stdout
    assert withdrawn() == "True"


# -- BUG-0311: a directory where the installer parses a file ---------------------------------------

@pytest.mark.parametrize("twin", TWINS)
def test_update_over_a_directory_where_a_file_belongs_bug_0311(tmp_path, twin):
    """AC-1 on the installer both update routes start (`update-kit` runs this very scaffold): an
    EMPTY directory at `.claude/settings.local.json` is removed and the run completes; a full one
    is refused with a remedy line and left exactly as it was.
    """
    home, repo, _environment = _scaffolded(tmp_path)
    staging = home / ".claude" / "team-kits"
    local = repo / ".claude" / "settings.local.json"
    local.mkdir()
    done = _run_installer(staging, repo, "dev-team", home, twin)
    assert done.returncode == 0, done.stdout + done.stderr
    assert not local.exists(), "the empty directory is still there"

    local.mkdir()
    (local / "keep.txt").write_text("somebody's", encoding="utf-8")
    refused = _run_installer(staging, repo, "dev-team", home, twin)
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert "Remedy:" in refused.stderr + refused.stdout, refused.stderr + refused.stdout
    assert (local / "keep.txt").read_text(encoding="utf-8") == "somebody's"


# -- BUG-0316: a CRLF checkout of the hashed bundle ------------------------------------------------

def _git(cwd, *argv):
    return subprocess.run(["git"] + list(argv), cwd=str(cwd), capture_output=True, text=True,
                          timeout=300)


@WINDOWS_ONLY
def test_an_autocrlf_clone_keeps_the_trusted_bundle_hash_bug_0316(tmp_path):
    """AC-1 as the field met it: the scaffolded project committed and cloned with
    `core.autocrlf=true` on both sides. The installed `.gitattributes` keeps git from converting the
    hashed paths, so the clone's bundle hashes to the value the project trusts, and a frozen
    diagram keeps its bytes.
    """
    if not shutil.which("git"):
        pytest.skip("no git on this machine")
    home, repo, _environment = _scaffolded(tmp_path)
    diagram = repo / "project_memory" / "staging" / "WFR-0001.r01.drawio.svg"
    diagram.parent.mkdir(parents=True, exist_ok=True)
    diagram.write_bytes(b"<svg>\n<g/>\n</svg>\n")
    recorded = json.loads((repo / ".claude" / "kit_state.json").read_text(
        encoding="utf-8-sig"))["hook_bundle_hash"]
    assert recorded == hashing.hook_bundle_hash(str(repo / ".claude"))
    for argv in (("init", "-q"), ("config", "core.autocrlf", "true"),
                 ("config", "user.email", "t@example.invalid"), ("config", "user.name", "t"),
                 ("add", "-A"), ("commit", "-q", "-m", "install")):
        assert _git(repo, *argv).returncode == 0, argv
    clone = tmp_path / "clone"
    made = _git(tmp_path, "-c", "core.autocrlf=true", "clone", "-q", "--config",
                "core.autocrlf=true", str(repo), str(clone))
    assert made.returncode == 0, made.stderr
    assert hashing.hook_bundle_hash(str(clone / ".claude")) == recorded
    assert (clone / "project_memory" / "staging" / "WFR-0001.r01.drawio.svg").read_bytes() == \
        diagram.read_bytes()


@WINDOWS_ONLY
def test_reading_git_attributes_of_a_protected_path_is_not_a_write_bug_0316(tmp_path):
    """The over-refusal of the same field entry: `git check-attr` / `git check-ignore` print how git
    reads a path and write nothing, so the installed write gate lets them name `.claude`."""
    _home, repo, _environment = _scaffolded(tmp_path)
    for command in ("git check-attr -a -- .claude/hooks/_kernel.py",
                    "git check-ignore -v .claude/kit_state.json"):
        assert _shell(repo, "gate_write_scope.py", command).returncode == 0, command
    assert _shell(repo, "gate_write_scope.py", "git rm --cached .claude/kit_state.json"
                  ).returncode == 2, "the read-only set now lets a WRITING git line through"


# -- BUG-0319: the kit-update merge backlog --------------------------------------------------------

def _edit_template(home, relative, extra):
    path = os.path.join(str(home), ".claude", "team-kits", "dev-team", "templates", "repo",
                        *relative.split("/"))
    with open(path, "ab") as handle:
        handle.write(extra)
    _restamp(home, "dev-team")
    return path


@WINDOWS_ONLY
def test_an_update_that_changed_no_template_lists_nothing_bug_0319(tmp_path):
    """AC-1, the list half: a template the PROJECT customised and the KIT did not change is no
    merge task; one the kit changed is listed (without a byte-order mark); one the project never
    touched is simply updated."""
    home, repo, _environment = _scaffolded(tmp_path)
    staging = home / ".claude" / "team-kits"
    pending = repo / kitupdate.PENDING_TEMPLATES
    with open(str(repo / "ruff.toml"), "ab") as handle:
        handle.write(b"\n# customised here\n")
    again = _run_installer(staging, repo, "dev-team", home, "powershell")
    assert again.returncode == 0, again.stdout + again.stderr
    assert not pending.exists(), pending.read_text(encoding="utf-8")

    _edit_template(home, "ruff.toml", b"\n# the kit moved this one\n")
    template = _edit_template(home, "requirements-dev.txt", b"\n# and this one\n")
    moved = _run_installer(staging, repo, "dev-team", home, "powershell")
    assert moved.returncode == 0, moved.stdout + moved.stderr
    assert not pending.read_bytes().startswith(b"\xef\xbb\xbf"), "the list carries a BOM"
    assert kitupdate.pending_entries(str(pending)) == ["ruff.toml"]
    with open(template, "rb") as handle:
        assert (repo / "requirements-dev.txt").read_bytes() == handle.read(), \
            "a template nobody customised was not updated"


@WINDOWS_ONLY
def test_the_merge_backlog_has_doors_a_session_can_walk_bug_0319(tmp_path):
    """AC-1, the door half: adopt the kit's template for a listed path, resolve the list, untrack a
    file the kit's .gitignore now ignores -- all through the shipped entry point, which names no
    protected path, and each checked on disk afterwards."""
    home, repo, _environment = _scaffolded(tmp_path)
    staging = home / ".claude" / "team-kits"
    pending = repo / kitupdate.PENDING_TEMPLATES
    for name in ("ruff.toml", "requirements-dev.txt"):
        with open(str(repo / name), "ab") as handle:
            handle.write(b"\n# customised here\n")
    _edit_template(home, "ruff.toml", b"\n# kit change\n")
    _edit_template(home, "requirements-dev.txt", b"\n# kit change\n")
    assert _run_installer(staging, repo, "dev-team", home, "powershell").returncode == 0
    assert sorted(kitupdate.pending_entries(str(pending))) == ["requirements-dev.txt", "ruff.toml"]
    assert _shell(repo, "gate_write_scope.py", "python scripts/harness.py upkeep adopt-template "
                  "ruff.toml").returncode == 0

    adopted = _harness(repo, home, kitupdate.UPKEEP_COMMAND, kitupdate.ADOPT_TEMPLATE, "ruff.toml")
    assert adopted.returncode == 0, adopted.stdout + adopted.stderr
    with open(str(staging / "dev-team" / "templates" / "repo" / "ruff.toml"), "rb") as handle:
        assert (repo / "ruff.toml").read_bytes() == handle.read()
    assert kitupdate.pending_entries(str(pending)) == ["requirements-dev.txt"]
    outside = _harness(repo, home, kitupdate.UPKEEP_COMMAND, kitupdate.ADOPT_TEMPLATE, "../elsewhere.txt")
    assert outside.returncode != 0, outside.stdout

    resolved = _harness(repo, home, kitupdate.UPKEEP_COMMAND, kitupdate.RESOLVE_PENDING)
    assert resolved.returncode == 0, resolved.stdout + resolved.stderr
    assert not pending.exists() and "requirements-dev.txt" in resolved.stdout

    if not shutil.which("git"):
        return
    for argv in (("init", "-q"), ("config", "user.email", "t@example.invalid"),
                 ("config", "user.name", "t"), ("add", "-A"),
                 ("add", "-f", ".claude/kit_state.json"), ("commit", "-q", "-m", "install")):
        assert _git(repo, *argv).returncode == 0, argv
    assert ".claude/kit_state.json" in _git(repo, "ls-files").stdout
    untracked = _harness(repo, home, kitupdate.UPKEEP_COMMAND, kitupdate.UNTRACK_IGNORED)
    assert untracked.returncode == 0, untracked.stdout + untracked.stderr
    assert ".claude/kit_state.json" not in _git(repo, "ls-files").stdout.splitlines()
    assert (repo / ".claude" / "kit_state.json").is_file(), "untracking deleted the file"


# -- BUG-0320: the test's own compose project ------------------------------------------------------

@WINDOWS_ONLY
def test_a_test_stack_named_by_the_convention_is_cleanable_bug_0320(tmp_path):
    """AC-1: a compose project named `<this repo><mark><anything>` is this repo's and may be taken
    down with its volumes; the field's `qa-tsk0431` and a neighbour stay refused."""
    _home, repo, _environment = _scaffolded(tmp_path)
    ours = os.path.basename(str(repo)).lower()
    sys.path.insert(0, str(repo / ".claude" / "hooks"))
    try:
        import gate_shell_hygiene
        mark = gate_shell_hygiene.OWN_TEST_PROJECT_MARK
    finally:
        sys.path.remove(str(repo / ".claude" / "hooks"))
        sys.modules.pop("gate_shell_hygiene", None)
    allowed = _shell(repo, "gate_shell_hygiene.py",
                     "docker compose -p %s%stsk0431 down -v" % (ours, mark))
    assert allowed.returncode == 0, allowed.stderr
    for foreign in ("qa-tsk0431", ours + "x" + mark + "tsk0431", ours + mark):
        refused = _shell(repo, "gate_shell_hygiene.py", "docker compose -p %s down -v" % foreign)
        assert refused.returncode == 2, (foreign, refused.stderr)


# -- BUG-0323: craft memory ----------------------------------------------------------------------

def _posix_spelling(path):
    """The Git Bash spelling of an absolute Windows path (`C:/x` -> `/c/x`)."""
    drive, rest = os.path.splitdrive(str(path))
    return "/" + drive.rstrip(":").lower() + rest.replace("\\", "/")


@WINDOWS_ONLY
def test_a_shell_write_after_an_absolute_cd_into_craft_memory_is_refused_bug_0323(tmp_path):
    """AC-1, the gate half, with the two lines the field transcripts carry: an absolute `cd` into a
    role's memory directory, in both spellings, then an append by a RELATIVE name. Ordinary work
    after an absolute `cd` stays open, and a move no word states refuses the write after it."""
    _home, repo, _environment = _scaffolded(tmp_path)
    memory = repo / ".claude" / "agent-memory" / "backend-developer"
    memory.mkdir(parents=True)
    for spelling in (str(memory).replace("\\", "/"), _posix_spelling(memory)):
        line = "cd \"%s\" && printf '%%s\\n' x >> MEMORY.md" % spelling
        result = _shell(repo, "gate_write_scope.py", line, agent="backend-developer")
        assert result.returncode == 2, (line, result.stderr)
    (repo / "src").mkdir()
    for spelling in (str(repo / "src").replace("\\", "/"), _posix_spelling(repo / "src")):
        line = "cd \"%s\" && python -m pytest" % spelling
        assert _shell(repo, "gate_write_scope.py", line, agent="backend-developer"
                      ).returncode == 0, line
    assert _shell(repo, "gate_write_scope.py", "cd - && echo x > notes.txt",
                  agent="backend-developer").returncode == 2


def _topic(directory, index, when):
    path = os.path.join(str(directory), "topic-%03d.md" % index)
    with open(path, "wb") as handle:
        handle.write(b"# craft %d\n" % index)
    os.utime(path, (when, when))
    return path


def _write_payload(repo, path, content, agent="backend-developer"):
    return {"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(repo),
            "agent_type": agent, "agent_id": "a0001",
            "tool_input": {"file_path": str(path), "content": content}}


@WINDOWS_ONLY
def test_an_over_budget_memory_can_be_brought_back_under_it_bug_0323(tmp_path):
    """AC-1, the door half: a 103-topic memory refuses every new topic; the prune door (kernel,
    through the shipped entry point) keeps the newest and drops the index lines that point at
    nothing -- the retired topics and the field's dangling lines; afterwards a new topic is allowed
    again. The index that still holds an item id is repaired the way the refusal says: one Write of
    the whole file without any, which passes."""
    home, repo, _environment = _scaffolded(tmp_path)
    memory = repo / ".claude" / "agent-memory" / "backend-developer"
    memory.mkdir(parents=True)
    now = time.time()
    for index in range(103):
        _topic(memory, index, now - 1000 + index)
    index_lines = ["- [t%d](topic-%03d.md) craft\n" % (n, n) for n in range(103)]
    (memory / "MEMORY.md").write_bytes(("see TSK-0145\n" + "".join(index_lines)
                                        + "- [dangling](never-written.md)\n").encode("utf-8"))
    fresh = memory / "new-topic.md"
    before = _installed_hook(repo, "guard_memory_budget.py",
                             _write_payload(repo, fresh, "# craft\n"))
    assert before.returncode == 2, "103 topics did not refuse a new one -- nothing measured"

    pruned = _harness(repo, home, kitupdate.UPKEEP_COMMAND, kitupdate.PRUNE_MEMORY, "backend-developer",
                      "--keep-newest", "19")
    assert pruned.returncode == 0, pruned.stdout + pruned.stderr
    left = sorted(name for name in os.listdir(str(memory)) if name.startswith("topic-"))
    assert left == ["topic-%03d.md" % n for n in range(84, 103)], left
    text = (memory / "MEMORY.md").read_text(encoding="utf-8")
    assert "topic-000.md" not in text and "topic-102.md" in text and "TSK-0145" in text
    assert "never-written.md" not in text, "the dangling line survived the prune"
    after = _installed_hook(repo, "guard_memory_budget.py",
                            _write_payload(repo, fresh, "# craft\n"))
    assert after.returncode == 0, after.stderr

    kept_line = "- [t102](topic-102.md) craft\n"
    shrink = {"hook_event_name": "PreToolUse", "tool_name": "Edit", "cwd": str(repo),
              "agent_type": "backend-developer", "agent_id": "a0001",
              "tool_input": {"file_path": str(memory / "MEMORY.md"),
                             "old_string": kept_line, "new_string": ""}}
    assert _installed_hook(repo, "guard_memory_budget.py", shrink).returncode == 2, \
        "the id rule no longer reads the result -- the repair sentence below is then not the route"
    without_ids = text.replace("see TSK-0145\n", "")
    assert _installed_hook(repo, "guard_memory_budget.py", _write_payload(
        repo, memory / "MEMORY.md", without_ids)).returncode == 0
    refused = _harness(repo, home, kitupdate.UPKEEP_COMMAND, kitupdate.PRUNE_MEMORY, "backend-developer",
                       "--retire", "MEMORY.md")
    assert refused.returncode != 0 and (memory / "MEMORY.md").is_file()


def test_the_prune_door_reads_the_index_the_kit_hook_polices_bug_0323():
    """The door never retires the index, and which file that is comes from the hook that polices
    it -- read out of the running module of every kit that ships the hook."""
    seen = 0
    for kit in KITS:
        if not os.path.isfile(os.path.join(TEAM_KITS, kit, "hooks", "guard_memory_budget.py")):
            continue
        seen += 1
        hook = _kit_hook_module(kit, "guard_memory_budget")
        assert (kitupdate.MEMORY_INDEX_STEM,) == tuple(hook.INDEX_STEMS), (
            "%s polices the index stems %r; the prune door protects %r"
            % (kit, hook.INDEX_STEMS, kitupdate.MEMORY_INDEX_STEM))
    assert seen, "no kit ships guard_memory_budget any more -- this test's subject is gone"
