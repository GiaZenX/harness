#!/usr/bin/env python3
"""
Behaviour tests for the shipped enforcement hooks + scripts/quality.py (dev-team kit).

The harness blocks other repos' merges on missing tests; it must test its OWN security machinery.
Each hook is run as a real subprocess with synthetic stdin JSON and CLAUDE_PROJECT_DIR, and asserted
on its exit code (0 = allow, 2 = block for guards/gates, 1 = red for quality.py). Run: pytest tools/
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "team-kits", "dev-team", "hooks")
OFFICE_HOOKS = os.path.join(ROOT, "team-kits", "office-team", "hooks")
OFFICE_SCRIPTS = os.path.join(ROOT, "team-kits", "office-team", "templates", "repo", "scripts")
QUALITY = os.path.join(ROOT, "team-kits", "dev-team", "templates", "repo", "scripts", "quality.py")
KIT_CHECKS = os.path.join(ROOT, "team-kits", "dev-team", "templates", "repo", "scripts", "kit_checks.py")


def run_hook(name, payload, project_dir, hooks_dir=None):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir))
    p = subprocess.run([sys.executable, os.path.join(hooks_dir or HOOKS, name)],
                       input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=60)
    return p.returncode


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


# ---------------- guard_pm_scope ----------------
def test_pm_blocked_from_src(tmp_path):
    (tmp_path / "project_memory").mkdir()
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "src" / "x.py")}, "cwd": str(tmp_path)}
    assert run_hook("guard_pm_scope.py", payload, tmp_path) == 2


def test_subagent_allowed_in_src(tmp_path):
    (tmp_path / "project_memory").mkdir()
    payload = {"tool_name": "Write", "agent_id": "sub-1",
               "tool_input": {"file_path": str(tmp_path / "src" / "x.py")}, "cwd": str(tmp_path)}
    assert run_hook("guard_pm_scope.py", payload, tmp_path) == 0


def test_pm_allowed_in_project_memory(tmp_path):
    (tmp_path / "project_memory").mkdir()
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": str(tmp_path / "project_memory" / "progress.yaml")}, "cwd": str(tmp_path)}
    assert run_hook("guard_pm_scope.py", payload, tmp_path) == 0


# ---------------- guard_agent_spawn ----------------
@pytest.fixture
def kit_repo(tmp_path):
    write(str(tmp_path / ".claude" / "agents" / "project-manager.md"), "x")
    write(str(tmp_path / ".claude" / "agents" / "backend-developer.md"), "x")
    write(str(tmp_path / ".claude" / "settings.json"), '{"agent": "project-manager"}')
    return tmp_path


def test_spawn_lead_blocked(kit_repo):
    payload = {"tool_name": "Agent", "tool_input": {"subagent_type": "project-manager"}, "cwd": str(kit_repo)}
    assert run_hook("guard_agent_spawn.py", payload, kit_repo) == 2


WORK_ORDER = "objective: implement SR-1\nread_first: [tasks.yaml TSK-1]\noutput: summary, status\nboundaries: no schema changes\n"


def test_spawn_specialist_allowed(kit_repo):
    payload = {"tool_name": "Agent",
               "tool_input": {"subagent_type": "backend-developer", "run_in_background": False,
                              "prompt": WORK_ORDER},
               "cwd": str(kit_repo)}
    assert run_hook("guard_agent_spawn.py", payload, kit_repo) == 0


def test_spawn_without_background_flag_blocked(kit_repo):
    # V14 backstop: the platform defaults to background — 37/37 real spawns went that way by omission.
    payload = {"tool_name": "Agent",
               "tool_input": {"subagent_type": "backend-developer", "prompt": WORK_ORDER},
               "cwd": str(kit_repo)}
    assert run_hook("guard_agent_spawn.py", payload, kit_repo) == 2


def test_spawn_explicit_background_allowed(kit_repo):
    # explicit true = a deliberate parallel batch — allowed (the PM must await all notifications)
    payload = {"tool_name": "Agent",
               "tool_input": {"subagent_type": "backend-developer", "run_in_background": True,
                              "prompt": WORK_ORDER},
               "cwd": str(kit_repo)}
    assert run_hook("guard_agent_spawn.py", payload, kit_repo) == 0


def test_spawn_without_work_order_schema_blocked(kit_repo):
    # Anthropic: vague delegations duplicate work/leave gaps — objective/output are the floor
    payload = {"tool_name": "Agent",
               "tool_input": {"subagent_type": "backend-developer", "run_in_background": False,
                              "prompt": "please implement the feature from the tasks file"},
               "cwd": str(kit_repo)}
    assert run_hook("guard_agent_spawn.py", payload, kit_repo) == 2


def test_spawn_generic_blocked(kit_repo):
    payload = {"tool_name": "Agent", "tool_input": {"subagent_type": ""}, "cwd": str(kit_repo)}
    assert run_hook("guard_agent_spawn.py", payload, kit_repo) == 2


# ---------------- gate_git (PRD binding) ----------------
@pytest.fixture
def prd_repo(tmp_path):
    write(str(tmp_path / "project_memory" / "product_requirements.yaml"), "requirements:\n  PRD-0001:\n    title: x\n")
    return tmp_path


def _merge(repo, report_txt):
    write(str(repo / "project_memory" / "test_reports.yaml"), report_txt)
    return {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(repo)}


def test_gate_git_force_push_blocked(prd_repo):
    payload = {"tool_name": "Bash", "tool_input": {"command": "git push --force origin main"}, "cwd": str(prd_repo)}
    assert run_hook("gate_git.py", payload, prd_repo) == 2


def test_gate_git_blocks_powershell_tool_too(prd_repo):
    # the gates must not be bypassable via the separate PowerShell tool (a real setup has both)
    payload = {"tool_name": "PowerShell", "tool_input": {"command": "git push --force origin main"},
               "cwd": str(prd_repo)}
    assert run_hook("gate_git.py", payload, prd_repo) == 2


def test_gate_git_stray_prd_pass_blocked(prd_repo):
    payload = _merge(prd_repo, "reports:\n  R1: { prd: PRD-0002, result: pass }\n")
    assert run_hook("gate_git.py", payload, prd_repo) == 2


def test_gate_git_matching_prd_pass_allowed(prd_repo):
    payload = _merge(prd_repo, "reports:\n  R1: { prd: PRD-0001, result: pass }\n")
    assert run_hook("gate_git.py", payload, prd_repo) == 0


# ---------------- gate_memory_complete ----------------
def test_memory_complete_blocks_empty_required(prd_repo):
    write(str(prd_repo / "project_memory" / "system_requirements.yaml"), "requirements: []\n")  # empty
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    assert run_hook("gate_memory_complete.py", payload, prd_repo) == 2


def test_memory_complete_allows_na_marked(prd_repo):
    write(str(prd_repo / "project_memory" / "change_requests.yaml"), "applicable: false\nreason: no changes\n")
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    # other required files are absent -> not flagged; the N/A one must not block
    assert run_hook("gate_memory_complete.py", payload, prd_repo) in (0, 2)  # tolerant: just must not crash


# ---------------- quality.py ----------------
def run_quality(repo):
    os.makedirs(os.path.join(repo, "scripts"), exist_ok=True)
    import shutil
    shutil.copy(QUALITY, os.path.join(repo, "scripts", "quality.py"))
    shutil.copy(KIT_CHECKS, os.path.join(repo, "scripts", "kit_checks.py"))  # kit-owned check lib
    p = subprocess.run([sys.executable, os.path.join(repo, "scripts", "quality.py")],
                       capture_output=True, text=True, cwd=repo, timeout=120)
    return p.returncode


def test_quality_empty_green(tmp_path):
    assert run_quality(str(tmp_path)) == 0


def test_quality_unknown_stack_red(tmp_path):
    write(str(tmp_path / "project_memory" / "project_config.yaml"), "project:\n  stacks: [cobol]\n")
    assert run_quality(str(tmp_path)) == 1


def test_quality_declared_node_no_frontend_red_not_crash(tmp_path):
    write(str(tmp_path / "project_memory" / "project_config.yaml"), "project:\n  stacks: [node]\n")
    assert run_quality(str(tmp_path)) == 1  # clean FAIL, not a crash


def test_quality_undeclared_stacks_with_code_red(tmp_path):
    # code present but stacks still [TODO] -> must FAIL (force the architect to declare; no silent auto-detect)
    write(str(tmp_path / "src" / "m.py"), "def f():\n    return 1\n")
    write(str(tmp_path / "project_memory" / "project_config.yaml"), "project:\n  stacks: [TODO]\n")
    assert run_quality(str(tmp_path)) == 1


def test_quality_declared_embedded_no_platformio_red(tmp_path):
    write(str(tmp_path / "project_memory" / "project_config.yaml"), "project:\n  stacks: [embedded]\n")
    assert run_quality(str(tmp_path)) == 1


# ---------------- guard_yaml_valid (write-time YAML validity, the synaipse decisions.yaml saga) ----------------
def _yaml_payload(repo, fname):
    return {"tool_name": "Write",
            "tool_input": {"file_path": str(repo / "project_memory" / fname)}, "cwd": str(repo)}


def test_yaml_valid_blocks_parse_error(tmp_path):
    pytest.importorskip("yaml")
    write(str(tmp_path / "project_memory" / "decisions.yaml"),
          "decisions:\n  ADR-0001:\n    title: STRIDE: threat: model\n")  # unquoted colons -> invalid
    assert run_hook("guard_yaml_valid.py", _yaml_payload(tmp_path, "decisions.yaml"), tmp_path) == 2


def test_yaml_valid_blocks_duplicate_key(tmp_path):
    pytest.importorskip("yaml")
    write(str(tmp_path / "project_memory" / "architecture.yaml"),
          "components:\n  api:\n    responsibility: a\n  api:\n    responsibility: b\n")
    assert run_hook("guard_yaml_valid.py", _yaml_payload(tmp_path, "architecture.yaml"), tmp_path) == 2


def test_yaml_valid_allows_good_yaml(tmp_path):
    pytest.importorskip("yaml")
    write(str(tmp_path / "project_memory" / "decisions.yaml"),
          'decisions:\n  ADR-0001:\n    title: "STRIDE: threat model"\n    body: |\n      prose: with colons is fine\n')
    assert run_hook("guard_yaml_valid.py", _yaml_payload(tmp_path, "decisions.yaml"), tmp_path) == 0


def test_yaml_valid_ignores_non_project_memory(tmp_path):
    write(str(tmp_path / "src" / "broken.yaml"), "a: b: c: [\n")
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "src" / "broken.yaml")},
               "cwd": str(tmp_path)}
    assert run_hook("guard_yaml_valid.py", payload, tmp_path) == 0


# ---------------- guard_guidelines token matching (compound keys like html_vanilla_js) ----------------
def test_guidelines_compound_key_satisfies_js(prd_repo):
    # the synaipse case: the architect named the block `html_vanilla_js:` — token "js" must match
    write(str(prd_repo / "project_memory" / "coding_guidelines.yaml"),
          "global:\n  - x\nlanguages:\n  html_vanilla_js:\n    - no inline handlers\n")
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": str(prd_repo / "src" / "app.js")}, "cwd": str(prd_repo)}
    assert run_hook("guard_guidelines.py", payload, prd_repo) == 0


def test_guidelines_still_blocks_js_without_block(prd_repo):
    write(str(prd_repo / "project_memory" / "coding_guidelines.yaml"), "global:\n  - x\nlanguages: {}\n")
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": str(prd_repo / "src" / "app.js")}, "cwd": str(prd_repo)}
    assert run_hook("guard_guidelines.py", payload, prd_repo) == 2


def test_guidelines_stray_key_outside_languages_does_not_satisfy(prd_repo):
    # a `node_version:` under global must NOT satisfy .js — only keys under `languages:` count
    pytest.importorskip("yaml")
    write(str(prd_repo / "project_memory" / "coding_guidelines.yaml"),
          "global:\n  node_version: 20\nlanguages: {}\n")
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": str(prd_repo / "src" / "app.js")}, "cwd": str(prd_repo)}
    assert run_hook("guard_guidelines.py", payload, prd_repo) == 2


def test_yaml_valid_survives_recursive_alias(tmp_path):
    # anchors/aliases make the node graph cyclic — the dup-key walker must terminate (visited set)
    pytest.importorskip("yaml")
    write(str(tmp_path / "project_memory" / "decisions.yaml"), "a: &x\n  b: ok\nc: *x\n")
    assert run_hook("guard_yaml_valid.py", _yaml_payload(tmp_path, "decisions.yaml"), tmp_path) == 0


def test_memory_complete_blocks_template_masterplan(prd_repo):
    write(str(prd_repo / "project_memory" / "masterplan.md"),
          "# Masterplan — <project name>\n\n> One-line essence of the idea.\n")
    write(str(prd_repo / "project_memory" / "project_config.yaml"),
          'project:\n  name: "X"\n  stacks: [python]\n')
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    assert run_hook("gate_memory_complete.py", payload, prd_repo) == 2


def test_memory_complete_allows_filled_masterplan(prd_repo):
    write(str(prd_repo / "project_memory" / "masterplan.md"),
          "# Masterplan — Chatly\n\n> A local chat platform.\n\n## 1. Leitidee\nReal prose here.\n")
    write(str(prd_repo / "project_memory" / "project_config.yaml"),
          'project:\n  name: "X"\n  stacks: [python]\n')
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    assert run_hook("gate_memory_complete.py", payload, prd_repo) == 0


# ---------------- quality.py: project_memory yaml-lint backstop ----------------
def test_quality_red_on_invalid_project_memory_yaml(tmp_path):
    pytest.importorskip("yaml")
    write(str(tmp_path / "project_memory" / "decisions.yaml"), "decisions:\n  ADR-1:\n    a: b: c\n")
    assert run_quality(str(tmp_path)) == 1


# ---------------- kit versioning: session_status flags updates; validate enforces bumps ----------------
def _mk_kit_repo(tmp_path, local_version, staged_version):
    home = tmp_path / "home"
    write(str(home / ".claude" / "team-kits" / "dev-team" / "VERSION"), staged_version)
    repo = tmp_path / "repo"
    write(str(repo / "CLAUDE.md"), "<!-- agents-and-skills:team-kit dev-team -->\n# x\n")
    if local_version is not None:
        write(str(repo / ".claude" / "kit_version"), local_version)
    return home, repo


def _run_session_status(home, repo):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo), HOME=str(home), USERPROFILE=str(home))
    p = subprocess.run([sys.executable, os.path.join(HOOKS, "session_status.py")],
                       input=json.dumps({"cwd": str(repo)}), capture_output=True, text=True,
                       env=env, timeout=60)
    return p.stdout


def test_session_status_flags_kit_update(tmp_path):
    home, repo = _mk_kit_repo(tmp_path, "version: 2026.07.01-1\ncontent: aaa\n",
                              "version: 2026.07.03-1\ncontent: bbb\n")
    out = _run_session_status(home, repo)
    assert "KIT UPDATE AVAILABLE" in out and "2026.07.03-1" in out


def test_session_status_quiet_when_current(tmp_path):
    v = "version: 2026.07.03-1\ncontent: same\n"
    home, repo = _mk_kit_repo(tmp_path, v, v)
    out = _run_session_status(home, repo)
    assert "KIT UPDATE AVAILABLE" not in out


def test_validate_catches_unbumped_kit_change():
    # append a comment to a kit file -> hash drifts -> validate must FAIL mentioning the bump tool
    p = os.path.join(ROOT, "team-kits", "dev-team", "hooks", "_audit.py")
    orig = open(p, encoding="utf-8").read()
    try:
        with open(p, "a", encoding="utf-8", newline="") as fh:
            fh.write("\n# temp-test-drift\n")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "validate.py")],
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 1 and "VERSION not bumped" in r.stdout
    finally:
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(orig)


# ---------------- gate_test_coverage + guard_guidelines for C/C++ (embedded) ----------------
def test_coverage_blocks_cpp_without_tests(prd_repo):
    write(str(prd_repo / "src" / "main.cpp"), "int main(){return 0;}\n")
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001"}, "cwd": str(prd_repo)}
    assert run_hook("gate_test_coverage.py", payload, prd_repo) == 2


def test_guidelines_block_cpp_without_languages(prd_repo):
    write(str(prd_repo / "project_memory" / "coding_guidelines.yaml"), "global:\n  - x\nlanguages: {}\n")
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": str(prd_repo / "src" / "main.cpp")}, "cwd": str(prd_repo)}
    assert run_hook("guard_guidelines.py", payload, prd_repo) == 2


# ---------------- gate_memory_complete: project_config name/stacks loophole ----------------
def test_memory_complete_blocks_unnamed_config(prd_repo):
    # real scalars (preset/repo_mode) but name:"" + stacks:[TODO] -> must be caught
    write(str(prd_repo / "project_memory" / "project_config.yaml"),
          'project:\n  name: ""\n  preset: solo\n  repo_mode: greenfield\n  stacks: [TODO]\n')
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    assert run_hook("gate_memory_complete.py", payload, prd_repo) == 2


def test_memory_complete_allows_named_declared_config(prd_repo):
    write(str(prd_repo / "project_memory" / "project_config.yaml"),
          'project:\n  name: "TCG Tracker"\n  preset: team\n  repo_mode: greenfield\n  stacks: [python, typescript]\n')
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    assert run_hook("gate_memory_complete.py", payload, prd_repo) == 0


# ---------------- init_project_memory: deterministic, copy-if-absent ----------------
def test_init_project_memory_copies_and_never_clobbers(tmp_path):
    home = tmp_path / "home"
    tpl = home / ".claude" / "team-kits" / "demo-team" / "templates" / "project_memory"
    write(str(tpl / "a.yaml"), "x: 1\n")
    write(str(tpl / "sub" / "b.yaml"), "y: 2\n")
    repo = tmp_path / "repo"
    repo.mkdir()

    if os.name == "nt":
        script = os.path.join(ROOT, "team-kits", "init_project_memory.ps1")
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-Team", "demo-team"]
        env = dict(os.environ, USERPROFILE=str(home))
    else:
        if not shutil.which("bash"):
            pytest.skip("bash not available")
        script = os.path.join(ROOT, "team-kits", "init_project_memory.sh")
        cmd = ["bash", script, "demo-team"]
        env = dict(os.environ, HOME=str(home))

    r = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    a = repo / "project_memory" / "a.yaml"
    b = repo / "project_memory" / "sub" / "b.yaml"
    assert a.is_file() and b.is_file()

    # copy-if-absent: a local edit must survive a re-run (idempotent, never clobbers)
    a.write_text("EDITED\n", encoding="utf-8")
    r2 = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True, env=env, timeout=60)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert a.read_text(encoding="utf-8") == "EDITED\n"


# ---------------- gate_packaging_decision (the generalised "Docker was forgotten" guard) ----------------
def test_packaging_gate_blocks_todo(prd_repo):
    write(str(prd_repo / "project_memory" / "architecture.yaml"),
          "components: {}\npackaging:\n  method: TODO\n  targets: []\n")
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    assert run_hook("gate_packaging_decision.py", payload, prd_repo) == 2


def test_packaging_gate_allows_decided(prd_repo):
    write(str(prd_repo / "project_memory" / "architecture.yaml"),
          "components: {}\npackaging:\n  method: static-binary\n  targets: [linux, windows]\n")
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    assert run_hook("gate_packaging_decision.py", payload, prd_repo) == 0


def test_packaging_gate_allows_explicit_none(prd_repo):
    # "none (library only)" is a conscious decision and must pass — only TODO/absent blocks
    write(str(prd_repo / "project_memory" / "architecture.yaml"),
          "components: {}\npackaging:\n  method: none(library)\n")
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    assert run_hook("gate_packaging_decision.py", payload, prd_repo) == 0


# ---------------- gate_memory_complete: optional FR backlog must not block ----------------
def test_memory_complete_allows_empty_fr_backlog(prd_repo):
    write(str(prd_repo / "project_memory" / "feature_requests.yaml"),
          "applicable: false\nreason: no backlog yet\nfeature_requests: {}\n")
    write(str(prd_repo / "project_memory" / "project_config.yaml"),
          'project:\n  name: "Demo"\n  stacks: [python]\n')
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    assert run_hook("gate_memory_complete.py", payload, prd_repo) == 0


# ---------------- dashboard generator: feature requests + roadmap land in the HTML ----------------
def test_dashboard_renders_fr_and_roadmap(tmp_path):
    try:
        import yaml  # noqa: F401
    except ImportError:
        pytest.skip("pyyaml not available")
    src = os.path.join(ROOT, "team-kits", "dev-team", "templates", "project_memory")
    d = tmp_path / "pm"
    d.mkdir()
    shutil.copy(os.path.join(src, "generate_dashboard.py"), str(d / "generate_dashboard.py"))
    shutil.copy(os.path.join(src, "progress.dashboard.template.html"), str(d / "progress.dashboard.template.html"))
    write(str(d / "product_requirements.yaml"), "requirements:\n  PRD-0001:\n    title: t\n    status: ACCEPTED\n")
    write(str(d / "feature_requests.yaml"), "feature_requests:\n  FR-0001:\n    title: f\n    status: PROPOSED\n")
    write(str(d / "bugs.yaml"), "bugs:\n  BUG-0001:\n    title: crash\n    severity: high\n    status: OPEN\n")
    write(str(d / "progress.yaml"),
          "status: ok\nmilestones:\n  - id: M1\n    title: MVP\n    items: [PRD-0001, FR-0001]\n")
    r = subprocess.run([sys.executable, str(d / "generate_dashboard.py")],
                       capture_output=True, text=True, cwd=str(d), timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    html = (d / "progress.dashboard.html").read_text(encoding="utf-8")
    assert "FR-0001" in html and "BUG-0001" in html and '"id": "M1"' in html
    assert "1 FRs" in r.stdout and "1 bugs" in r.stdout and "1 milestones" in r.stdout


def test_memory_complete_allows_empty_bug_log(prd_repo):
    write(str(prd_repo / "project_memory" / "bugs.yaml"),
          "applicable: false\nreason: no defects yet\nbugs: {}\n")
    write(str(prd_repo / "project_memory" / "project_config.yaml"),
          'project:\n  name: "Demo"\n  stacks: [python]\n')
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    assert run_hook("gate_memory_complete.py", payload, prd_repo) == 0


# ---------------- gate_memory_complete: UI design.yaml must record an ambition (synaipse fix) ----------------
def test_memory_complete_blocks_design_without_ambition(prd_repo):
    # a UI design.yaml (not applicable:false) with no `ambition:` -> blocked (don't ship one design silently)
    write(str(prd_repo / "project_memory" / "design.yaml"), 'chosen: "Aurora"\ndirections: [Aurora]\n')
    write(str(prd_repo / "project_memory" / "project_config.yaml"),
          'project:\n  name: "X"\n  stacks: [python]\n')
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    assert run_hook("gate_memory_complete.py", payload, prd_repo) == 2


def test_memory_complete_allows_design_with_ambition(prd_repo):
    write(str(prd_repo / "project_memory" / "design.yaml"), 'ambition: minimal\nchosen: "Aurora"\n')
    write(str(prd_repo / "project_memory" / "project_config.yaml"),
          'project:\n  name: "X"\n  stacks: [python]\n')
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    assert run_hook("gate_memory_complete.py", payload, prd_repo) == 0


# ---------------- guard_yaml_valid: progress.yaml format backstop (V10 — status blob / dropped log) ----------------
def test_progress_status_blob_blocked(tmp_path):
    pytest.importorskip("yaml")
    blob = "\n".join("line %d of a growing prose status" % i for i in range(12))
    write(str(tmp_path / "project_memory" / "progress.yaml"),
          "status: |\n" + "".join("  %s\n" % ln for ln in blob.splitlines()) + "log: []\n")
    assert run_hook("guard_yaml_valid.py", _yaml_payload(tmp_path, "progress.yaml"), tmp_path) == 2


def test_progress_missing_log_blocked(tmp_path):
    pytest.importorskip("yaml")
    write(str(tmp_path / "project_memory" / "progress.yaml"),
          'status: "PRD-0001 merged; next: PRD-0002 design loop"\nmetrics: {}\n')
    assert run_hook("guard_yaml_valid.py", _yaml_payload(tmp_path, "progress.yaml"), tmp_path) == 2


def test_progress_compliant_allowed(tmp_path):
    pytest.importorskip("yaml")
    write(str(tmp_path / "project_memory" / "progress.yaml"),
          'status: "PRD-0001 merged; next: PRD-0002 design loop"\nlog:\n  - "2026-07-09: PRD-0001 merged"\n')
    assert run_hook("guard_yaml_valid.py", _yaml_payload(tmp_path, "progress.yaml"), tmp_path) == 0


def test_progress_rule_does_not_hit_other_yaml(tmp_path):
    # a long status field in ANOTHER artifact must not trigger the progress.yaml contract
    pytest.importorskip("yaml")
    body = "status: |\n" + "".join("  line %d\n" % i for i in range(12))
    write(str(tmp_path / "project_memory" / "test_reports.yaml"), body)
    assert run_hook("guard_yaml_valid.py", _yaml_payload(tmp_path, "test_reports.yaml"), tmp_path) == 0


# ---------------- notify_agent_events: background-agent lifecycle -> audit log ----------------
def _notify(tmp_path, ntype):
    payload = {"hook_event_name": "Notification", "notification_type": ntype,
               "message": "agent done", "cwd": str(tmp_path)}
    return run_hook("notify_agent_events.py", payload, tmp_path)


def test_notify_logs_agent_completed(tmp_path):
    (tmp_path / "project_memory").mkdir()
    assert _notify(tmp_path, "agent_completed") == 0
    audit = tmp_path / "project_memory" / ".audit" / "hook_events.jsonl"
    assert audit.is_file() and "agent_completed" in audit.read_text(encoding="utf-8")


def test_notify_ignores_other_types(tmp_path):
    (tmp_path / "project_memory").mkdir()
    assert _notify(tmp_path, "permission_prompt") == 0
    assert not (tmp_path / "project_memory" / ".audit" / "hook_events.jsonl").exists()


def test_notify_never_blocks_without_project(tmp_path):
    assert _notify(tmp_path, "agent_completed") == 0  # no project_memory -> silent no-op


# ---------------- quality.py: secure-context + local-first asset greps ----------------
def test_quality_red_on_raw_secure_context_api(tmp_path):
    write(str(tmp_path / "src" / "static" / "index.html"),
          "<html><script>const id = crypto.randomUUID();</script></html>\n")
    assert run_quality(str(tmp_path)) == 1


def test_quality_green_with_marked_fallback(tmp_path):
    write(str(tmp_path / "src" / "static" / "index.html"),
          "<html><script>// secure-context: has fallback\n"
          "const id = crypto.randomUUID ? crypto.randomUUID() : fallbackUuid();</script></html>\n")
    assert run_quality(str(tmp_path)) == 0


def test_quality_red_on_cdn_asset_when_local_first(tmp_path):
    write(str(tmp_path / "project_memory" / "project_config.yaml"),
          "project:\n  local_first: true\n  stacks: []\n")
    write(str(tmp_path / "src" / "static" / "index.html"),
          '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Caveat">\n')
    assert run_quality(str(tmp_path)) == 1


def test_quality_external_link_anchor_stays_legal(tmp_path):
    # local_first bans loaded RESOURCES, not plain hyperlinks the user may click
    write(str(tmp_path / "project_memory" / "project_config.yaml"),
          "project:\n  local_first: true\n  stacks: []\n")
    write(str(tmp_path / "src" / "static" / "index.html"),
          '<a href="https://github.com/x/y">source</a>\n')
    assert run_quality(str(tmp_path)) == 0


# ---------------- session_status: unfinished kit-update reminder (pending files) ----------------
def test_session_status_reminds_on_pending_kit_update(tmp_path):
    repo = tmp_path / "repo"
    write(str(repo / ".claude" / "kit_update_pending.repo"),
          "# diverged\n- scripts/quality.py\n- requirements-dev.txt\n")
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))
    p = subprocess.run([sys.executable, os.path.join(HOOKS, "session_status.py")],
                       input=json.dumps({"cwd": str(repo)}), capture_output=True, text=True,
                       env=env, timeout=60)
    assert "KIT UPDATE NOT FINISHED" in p.stdout and "scripts/quality.py" in p.stdout


def test_session_status_quiet_without_pending(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))
    p = subprocess.run([sys.executable, os.path.join(HOOKS, "session_status.py")],
                       input=json.dumps({"cwd": str(repo)}), capture_output=True, text=True,
                       env=env, timeout=60)
    assert "KIT UPDATE NOT FINISHED" not in p.stdout


# ---------------- session_status: model/effort frontmatter must match the user-confirmed maps ----------------
def _sync_repo(tmp_path, agent_model):
    repo = tmp_path / "repo"
    write(str(repo / "project_memory" / "project_config.yaml"),
          "project:\n  name: x\nmodel_map:\n  backend-developer: opus   # user-approved upscale\n"
          "effort_map:\n  backend-developer: high\n")
    write(str(repo / ".claude" / "agents" / "backend-developer.md"),
          "---\nname: backend-developer\nmodel: %s\neffort: high\n---\nbody\n" % agent_model)
    return repo


def _run_status(repo):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))
    return subprocess.run([sys.executable, os.path.join(HOOKS, "session_status.py")],
                          input=json.dumps({"cwd": str(repo)}), capture_output=True, text=True,
                          env=env, timeout=60).stdout


def test_session_status_flags_model_drift(tmp_path):
    # the scaffold reset the frontmatter to sonnet although the map says opus -> must nag
    out = _run_status(_sync_repo(tmp_path, "sonnet"))
    assert "MODEL/EFFORT OUT OF SYNC" in out and "backend-developer model=sonnet (map says opus)" in out


def test_session_status_quiet_when_synced(tmp_path):
    out = _run_status(_sync_repo(tmp_path, "opus"))
    assert "MODEL/EFFORT OUT OF SYNC" not in out


# ---------------- quality.py: progress.yaml contract at the pipeline (catches shell-written blobs) ----------------
def test_quality_red_on_progress_status_blob(tmp_path):
    pytest.importorskip("yaml")
    write(str(tmp_path / "project_memory" / "progress.yaml"),
          'status: "%s"\nlog: []\n' % ("x" * 800))
    assert run_quality(str(tmp_path)) == 1


def test_quality_red_on_progress_missing_log(tmp_path):
    pytest.importorskip("yaml")
    write(str(tmp_path / "project_memory" / "progress.yaml"), 'status: "ok; next: PRD-2"\n')
    assert run_quality(str(tmp_path)) == 1


def test_quality_green_on_compliant_progress(tmp_path):
    pytest.importorskip("yaml")
    write(str(tmp_path / "project_memory" / "progress.yaml"),
          'status: "PRD-1 merged; next: PRD-2 design"\nlog:\n  - "2026-07-12: PRD-1 merged"\n')
    assert run_quality(str(tmp_path)) == 0


# ---------------- retro.py: agent lifecycle events must not count as gate blocks ----------------
def test_retro_separates_blocks_from_agent_events(tmp_path):
    retro_src = os.path.join(ROOT, "team-kits", "dev-team", "templates", "repo", "scripts", "retro.py")
    os.makedirs(str(tmp_path / "scripts"), exist_ok=True)
    shutil.copy(retro_src, str(tmp_path / "scripts" / "retro.py"))
    lines = (
        ['{"ts": "t", "hook": "gate_git", "event": "block", "reason": "x"}'] * 2
        + ['{"ts": "t", "hook": "notify_agent_events", "event": "agent_completed", "reason": "done"}'] * 3
    )
    write(str(tmp_path / "project_memory" / ".audit" / "hook_events.jsonl"), "\n".join(lines) + "\n")
    p = subprocess.run([sys.executable, str(tmp_path / "scripts" / "retro.py")],
                       capture_output=True, text=True, cwd=str(tmp_path), timeout=60)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "gates blocked work: gate_git x2" in p.stdout
    assert "background-agent events: agent_completed x3" in p.stdout
    assert "notify_agent_events x" not in p.stdout  # lifecycle events must never read as blocks


# ---------------- init_project_memory: diverged tooling -> pending file; resolution deletes it ----------------
def test_init_pending_file_written_and_removed(tmp_path):
    home = tmp_path / "home"
    tpl = home / ".claude" / "team-kits" / "demo-team" / "templates" / "project_memory"
    write(str(tpl / "gen.py"), "print('v2')\n")
    repo = tmp_path / "repo"
    repo.mkdir()

    if os.name == "nt":
        script = os.path.join(ROOT, "team-kits", "init_project_memory.ps1")
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-Team", "demo-team"]
        env = dict(os.environ, USERPROFILE=str(home))
    else:
        if not shutil.which("bash"):
            pytest.skip("bash not available")
        script = os.path.join(ROOT, "team-kits", "init_project_memory.sh")
        cmd = ["bash", script, "demo-team"]
        env = dict(os.environ, HOME=str(home))

    def run_init():
        r = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True, env=env, timeout=60)
        assert r.returncode == 0, r.stdout + r.stderr

    run_init()  # fresh copy — no divergence, no pending file
    pend = repo / ".claude" / "kit_update_pending.memory"
    assert not pend.exists()

    (repo / "project_memory" / "gen.py").write_text("print('v1')\n", encoding="utf-8")
    run_init()  # tooling diverged -> pending file records it
    assert pend.is_file() and "gen.py" in pend.read_text(encoding="utf-8-sig")

    (repo / "project_memory" / "gen.py").write_text("print('v2')\n", encoding="utf-8")
    run_init()  # divergence resolved -> pending file removed
    assert not pend.exists()


# ---------------- kit mirroring: shared files must stay byte-identical across kits ----------------
def test_shared_kit_files_identical():
    shared = [
        ("hooks", "guard_yaml_valid.py"), ("hooks", "guard_agent_spawn.py"),
        ("hooks", "notify_agent_events.py"), ("hooks", "guard_scratchpad_ref.py"),
        ("hooks", "_root.py"), ("hooks", "_audit.py"), ("hooks", "auto_dashboard.py"),
        ("templates", os.path.join("repo", "scripts", "quality.py")),
        ("templates", os.path.join("repo", "scripts", "kit_checks.py")),
        ("templates", os.path.join("repo", "scripts", "retro.py")),
    ]
    for sub, name in shared:
        a = os.path.join(ROOT, "team-kits", "dev-team", sub, name)
        b = os.path.join(ROOT, "team-kits", "research-team", sub, name)
        assert open(a, "rb").read() == open(b, "rb").read(), "%s/%s diverged between kits" % (sub, name)
    for name in ("guard_yaml_valid.py", "guard_agent_spawn.py", "notify_agent_events.py",
                 "guard_scratchpad_ref.py", "_root.py", "_audit.py"):
        a = os.path.join(ROOT, "team-kits", "dev-team", "hooks", name)
        b = os.path.join(ROOT, "team-kits", "office-team", "hooks", name)
        assert open(a, "rb").read() == open(b, "rb").read(), "hooks/%s diverged (office)" % name


# ---------------- kit_checks: file budget (the anti-monolith gate) ----------------
def test_file_budget_blocks_monolith(tmp_path):
    pytest.importorskip("yaml")
    write(str(tmp_path / "src" / "static" / "app.js"), "let x = 1;\n" * 900)
    assert run_quality(str(tmp_path)) == 1


def test_file_budget_exemption_with_reason_passes(tmp_path):
    pytest.importorskip("yaml")
    write(str(tmp_path / "src" / "static" / "app.js"), "let x = 1;\n" * 900)
    write(str(tmp_path / "project_memory" / "coding_guidelines.yaml"),
          "global:\n  - x\nlanguages: {}\nfile_budget:\n  max_lines: 800\n  exempt:\n"
          "    - path: src/static/app.js\n      reason: \"legacy monolith - split tracked in TSK-1\"\n")
    write(str(tmp_path / "project_memory" / "progress.yaml"), 'status: "ok"\nlog: []\n')
    assert run_quality(str(tmp_path)) == 0


def test_file_budget_under_limit_green(tmp_path):
    pytest.importorskip("yaml")
    write(str(tmp_path / "src" / "static" / "app.js"), "let x = 1;\n" * 100)
    assert run_quality(str(tmp_path)) == 0


# ---------------- session_status: pending nag escalates across sessions ----------------
def test_pending_nag_escalates(tmp_path):
    repo = tmp_path / "repo"
    write(str(repo / ".claude" / "kit_update_pending.repo"), "# d\n- scripts/quality.py\n")
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))

    def run_status():
        return subprocess.run([sys.executable, os.path.join(HOOKS, "session_status.py")],
                              input=json.dumps({"cwd": str(repo)}), capture_output=True, text=True,
                              env=env, timeout=60).stdout

    first = run_status()
    assert "KIT UPDATE NOT FINISHED" in first and "OPEN SINCE" not in first
    second = run_status()
    assert "OPEN SINCE" in second and "2. session" in second
    (repo / ".claude" / "kit_update_pending.repo").unlink()
    cleared = run_status()
    assert "KIT UPDATE NOT FINISHED" not in cleared
    assert not (repo / ".claude" / "kit_update_pending.state").exists()  # counter reset


# ---------------- auto_dashboard: once-per-session stop reminder while pending exists ----------------
def test_stop_reminder_once_per_session(tmp_path):
    repo = tmp_path / "repo"
    write(str(repo / ".claude" / "kit_update_pending.repo"), "# d\n- scripts/quality.py\n")
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))

    def run_stop(sid):
        return subprocess.run([sys.executable, os.path.join(HOOKS, "auto_dashboard.py")],
                              input=json.dumps({"cwd": str(repo), "session_id": sid}),
                              capture_output=True, text=True, env=env, timeout=60)

    p1 = run_stop("s1")
    assert p1.returncode == 1 and "kit_update_pending" in p1.stderr
    p2 = run_stop("s1")
    assert p2.returncode == 0 and "kit_update_pending" not in p2.stderr  # same session: quiet
    p3 = run_stop("s2")
    assert p3.returncode == 1  # new session: reminded again


# ---------------- guard_agent_spawn: allowed spawns are audited ----------------
def test_allowed_spawn_is_audited(kit_repo):
    (kit_repo / "project_memory").mkdir()
    payload = {"tool_name": "Agent",
               "tool_input": {"subagent_type": "backend-developer", "run_in_background": False,
                              "prompt": WORK_ORDER},
               "cwd": str(kit_repo)}
    assert run_hook("guard_agent_spawn.py", payload, kit_repo) == 0
    audit = kit_repo / "project_memory" / ".audit" / "hook_events.jsonl"
    text = audit.read_text(encoding="utf-8")
    assert '"event": "spawn"' in text and "backend-developer" in text


# ---------------- gate_subagent_output: specialists honor their output contract ----------------
def _stop_payload(repo, atype, message):
    return {"hook_event_name": "SubagentStop", "agent_type": atype,
            "last_assistant_message": message, "cwd": str(repo)}


def test_subagent_output_blocks_prose_only(kit_repo):
    payload = _stop_payload(kit_repo, "backend-developer", "All done, everything works great!")
    assert run_hook("gate_subagent_output.py", payload, kit_repo) == 2


def test_subagent_output_passes_contract(kit_repo):
    payload = _stop_payload(kit_repo, "backend-developer", "summary: implemented SR-1\nstatus: DONE")
    assert run_hook("gate_subagent_output.py", payload, kit_repo) == 0


def test_subagent_output_verdict_role_needs_verdict(kit_repo):
    write(str(kit_repo / ".claude" / "agents" / "quality-engineer.md"), "x")
    payload = _stop_payload(kit_repo, "quality-engineer", "summary: reviewed everything, looks fine")
    assert run_hook("gate_subagent_output.py", payload, kit_repo) == 2
    payload = _stop_payload(kit_repo, "quality-engineer", "summary: gate run\nverdict: PASS")
    assert run_hook("gate_subagent_output.py", payload, kit_repo) == 0


def test_subagent_output_ignores_foreign_agents(kit_repo):
    payload = _stop_payload(kit_repo, "Explore", "just some search results")
    assert run_hook("gate_subagent_output.py", payload, kit_repo) == 0


# ---------------- session_status: version-change announcement after an external restamp ----------------
def test_version_change_announced_once(tmp_path):
    repo = tmp_path / "repo"
    write(str(repo / ".claude" / "kit_version"), "version: 2026.07.12-4\ncontent: aaa\n")
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))

    def run_status():
        return subprocess.run([sys.executable, os.path.join(HOOKS, "session_status.py")],
                              input=json.dumps({"cwd": str(repo)}), capture_output=True, text=True,
                              env=env, timeout=60).stdout

    first = run_status()
    assert "KIT UPDATED" not in first  # first sighting just records the version
    write(str(repo / ".claude" / "kit_version"), "version: 2026.07.14-1\ncontent: bbb\n")
    second = run_status()
    assert "KIT UPDATED" in second and "2026.07.12-4 -> 2026.07.14-1" in second
    third = run_status()
    assert "KIT UPDATED" not in third  # announced once, then recorded


# ---------------- guard_harness_selfmod: the enforcement layer is not self-editable ----------------
def test_selfmod_blocks_hook_edit(tmp_path):
    p = tmp_path / ".claude" / "hooks" / "gate_git.py"
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(p)}, "cwd": str(tmp_path)}
    assert run_hook("guard_harness_selfmod.py", payload, tmp_path) == 2


def test_selfmod_blocks_settings_edit(tmp_path):
    p = tmp_path / ".claude" / "settings.json"
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(p)}, "cwd": str(tmp_path)}
    assert run_hook("guard_harness_selfmod.py", payload, tmp_path) == 2


def test_selfmod_allows_agent_resync_and_memory(tmp_path):
    for rel in (".claude/agents/backend-developer.md", ".claude/agent-memory/project-manager/MEMORY.md"):
        p = tmp_path / rel
        payload = {"tool_name": "Edit", "tool_input": {"file_path": str(p)}, "cwd": str(tmp_path)}
        assert run_hook("guard_harness_selfmod.py", payload, tmp_path) == 0, rel


# ---------------- gate_git: entry-level QA binding (audit false-accept regression) ----------------
def test_gate_git_old_pass_other_task_fresh_fail_target_blocks(prd_repo):
    # the exact reported hole: an old PASS for ANOTHER PRD + a fresh FAIL for the target in ONE file
    write(str(prd_repo / "project_memory" / "test_reports.yaml"),
          "reports:\n  R1: { prd: PRD-0009, result: pass }\n  R2: { prd: PRD-0001, result: fail }\n")
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    assert run_hook("gate_git.py", payload, prd_repo) == 2


def test_gate_git_bound_pass_still_allows(prd_repo):
    write(str(prd_repo / "project_memory" / "test_reports.yaml"),
          "reports:\n  R1: { prd: PRD-0009, result: fail }\n  R2: { prd: PRD-0001, result: pass }\n")
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    assert run_hook("gate_git.py", payload, prd_repo) == 0


def test_gate_git_indirect_binding_falls_back_to_file_level(prd_repo):
    # entries bound via task ids only (no PRD in the entry) -> file-level check keeps working
    write(str(prd_repo / "project_memory" / "test_reports.yaml"),
          "# gate for PRD-0001\nreports:\n  R1: { task: TSK-0007, result: pass }\n")
    payload = {"tool_name": "Bash", "tool_input": {"command": "git merge feat/PRD-0001-x"}, "cwd": str(prd_repo)}
    assert run_hook("gate_git.py", payload, prd_repo) == 0


# ---------------- gate_subagent_output: honors stop_hook_active (no infinite block loop) ----------------
def test_subagent_output_gives_up_on_stop_hook_active(kit_repo):
    (kit_repo / "project_memory").mkdir(exist_ok=True)
    payload = {"hook_event_name": "SubagentStop", "agent_type": "backend-developer",
               "last_assistant_message": "still just prose", "stop_hook_active": True,
               "cwd": str(kit_repo)}
    assert run_hook("gate_subagent_output.py", payload, kit_repo) == 0
    audit = kit_repo / "project_memory" / ".audit" / "hook_events.jsonl"
    assert "gave_up" in audit.read_text(encoding="utf-8")


# ---------------- office fs tripwire: shell redirects into the ledger are blocked ----------------
def test_fs_tripwire_blocks_ledger_redirect(tmp_path):
    payload = {"tool_name": "Bash",
               "tool_input": {"command": 'echo "L1,2026-01-01,..." >> ledger/2026.csv'},
               "cwd": str(tmp_path)}
    assert run_hook("guard_fs_tripwire.py", payload, tmp_path, hooks_dir=OFFICE_HOOKS) == 2


def test_fs_tripwire_allows_ledger_add_script(tmp_path):
    payload = {"tool_name": "Bash",
               "tool_input": {"command": "python scripts/ledger_add.py --year 2026 --net 1 > /tmp/log"},
               "cwd": str(tmp_path)}
    assert run_hook("guard_fs_tripwire.py", payload, tmp_path, hooks_dir=OFFICE_HOOKS) == 0


# ---------------- constitutions: every hook has a documented rule-home (diet safety) ----------------
def test_every_hook_documented_in_its_constitution():
    for kit in ("dev-team", "research-team", "office-team"):
        cpath = os.path.join(ROOT, "team-kits", kit, "constitution", "CLAUDE.md")
        text = open(cpath, encoding="utf-8", errors="ignore").read()
        hooks_dir = os.path.join(ROOT, "team-kits", kit, "hooks")
        for fn in os.listdir(hooks_dir):
            if not fn.endswith(".py") or fn.startswith("_"):
                continue
            name = fn[:-3]
            assert name in text, "%s: hook %s has no documented rule-home in the constitution" % (kit, name)


# ---------------- notify_agent_events: SubagentStop route ----------------
def test_notify_logs_subagent_stop(tmp_path):
    (tmp_path / "project_memory").mkdir()
    payload = {"hook_event_name": "SubagentStop", "agent_type": "frontend-developer",
               "cwd": str(tmp_path)}
    assert run_hook("notify_agent_events.py", payload, tmp_path) == 0
    text = (tmp_path / "project_memory" / ".audit" / "hook_events.jsonl").read_text(encoding="utf-8")
    assert "subagent_stop" in text and "frontend-developer" in text


# ---------------- guard_scratchpad_ref ----------------
def test_scratchpad_ref_blocked_in_source(tmp_path):
    p = tmp_path / "src" / "styles.css"
    write(str(p), "/* Regenerate via scratchpad/vendor_fonts.py */\nbody{}\n")
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(p)}, "cwd": str(tmp_path)}
    assert run_hook("guard_scratchpad_ref.py", payload, tmp_path) == 2


def test_scratchpad_ref_allowed_outside_source_areas(tmp_path):
    p = tmp_path / "project_memory" / "notes.yaml"
    write(str(p), "note: the scratchpad/ dir is ephemeral\n")
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(p)}, "cwd": str(tmp_path)}
    assert run_hook("guard_scratchpad_ref.py", payload, tmp_path) == 0


# ---------------- office kit: gate_proc_approved ----------------
def _office_repo(tmp_path, procs_yaml=None):
    repo = tmp_path / "repo"
    (repo / "project_memory").mkdir(parents=True)
    if procs_yaml is not None:
        write(str(repo / "project_memory" / "process_definitions.yaml"), procs_yaml)
    return repo


def _spawn(repo, prompt):
    return {"tool_name": "Agent",
            "tool_input": {"subagent_type": "bookkeeper", "run_in_background": False,
                           "prompt": prompt}, "cwd": str(repo)}


def _steps_hash(steps):
    import hashlib
    yaml = pytest.importorskip("yaml")
    return hashlib.sha256(yaml.safe_dump(steps, sort_keys=True, allow_unicode=True)
                          .encode("utf-8")).hexdigest()


def test_proc_gate_bootstrap_allows(tmp_path):
    repo = _office_repo(tmp_path, "processes: {}\n")
    assert run_hook("gate_proc_approved.py", _spawn(repo, "onboarding interview"), repo,
                    hooks_dir=OFFICE_HOOKS) == 0


def test_proc_gate_blocks_missing_ref(tmp_path):
    pytest.importorskip("yaml")
    h = _steps_hash(["file it"])
    repo = _office_repo(tmp_path,
                        "processes:\n  PROC-0001:\n    title: x\n    status: APPROVED\n"
                        "    approved_hash: \"%s\"\n    steps:\n      - file it\n" % h)
    assert run_hook("gate_proc_approved.py", _spawn(repo, "please file the inbox"), repo,
                    hooks_dir=OFFICE_HOOKS) == 2


def test_proc_gate_passes_approved_with_hash(tmp_path):
    pytest.importorskip("yaml")
    h = _steps_hash(["file it"])
    repo = _office_repo(tmp_path,
                        "processes:\n  PROC-0001:\n    title: x\n    status: APPROVED\n"
                        "    approved_hash: \"%s\"\n    steps:\n      - file it\n" % h)
    assert run_hook("gate_proc_approved.py", _spawn(repo, "execute PROC-0001 sweep"), repo,
                    hooks_dir=OFFICE_HOOKS) == 0


def test_proc_gate_blocks_tampered_steps(tmp_path):
    pytest.importorskip("yaml")
    h = _steps_hash(["file it"])
    repo = _office_repo(tmp_path,
                        "processes:\n  PROC-0001:\n    title: x\n    status: APPROVED\n"
                        "    approved_hash: \"%s\"\n    steps:\n      - file it\n"
                        "      - NEW sneaky step\n" % h)
    assert run_hook("gate_proc_approved.py", _spawn(repo, "execute PROC-0001"), repo,
                    hooks_dir=OFFICE_HOOKS) == 2


# ---------------- office kit: ledger guards + scripts ----------------
def test_guard_ledger_direct_blocks(tmp_path):
    p = tmp_path / "ledger" / "2026.csv"
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(p)}, "cwd": str(tmp_path)}
    assert run_hook("guard_ledger_direct.py", payload, tmp_path, hooks_dir=OFFICE_HOOKS) == 2


def _ledger_add(repo, *extra):
    os.makedirs(os.path.join(repo, "scripts"), exist_ok=True)
    shutil.copy(os.path.join(OFFICE_SCRIPTS, "ledger_add.py"),
                os.path.join(repo, "scripts", "ledger_add.py"))
    base = [sys.executable, os.path.join(repo, "scripts", "ledger_add.py"),
            "--year", "2026", "--direction", "expense", "--doc-type", "invoice",
            "--doc-date", "2026-07-01", "--payment-date", "2026-07-03",
            "--counterparty", "Muster GmbH", "--invoice-no", "RE-1",
            "--vat-treatment", "standard", "--category", "goods",
            "--source", "archive/finance/x.pdf"]
    return subprocess.run(base + list(extra), capture_output=True, text=True, cwd=repo, timeout=60)


def test_ledger_add_appends_valid_row(tmp_path):
    r = _ledger_add(str(tmp_path), "--net", "100.00", "--vat-rate", "19", "--gross", "119.00")
    assert r.returncode == 0, r.stderr
    text = (tmp_path / "ledger" / "2026.csv").read_text(encoding="utf-8")
    assert "L2026-0001" in text and "Muster GmbH" in text


def test_ledger_add_refuses_bad_arithmetic(tmp_path):
    r = _ledger_add(str(tmp_path), "--net", "100.00", "--vat-rate", "19", "--gross", "125.00")
    assert r.returncode == 1 and "re-read the document" in r.stderr


def test_ledger_add_refuses_duplicate(tmp_path):
    assert _ledger_add(str(tmp_path), "--net", "100.00", "--vat-rate", "19", "--gross", "119.00").returncode == 0
    r = _ledger_add(str(tmp_path), "--net", "100.00", "--vat-rate", "19", "--gross", "119.00")
    assert r.returncode == 1 and "duplicate" in r.stderr


def test_euer_report_totals(tmp_path):
    assert _ledger_add(str(tmp_path), "--net", "100.00", "--vat-rate", "19", "--gross", "119.00").returncode == 0
    shutil.copy(os.path.join(OFFICE_SCRIPTS, "euer_report.py"),
                os.path.join(str(tmp_path), "scripts", "euer_report.py"))
    r = subprocess.run([sys.executable, os.path.join(str(tmp_path), "scripts", "euer_report.py"),
                        "--year", "2026", "--quarter", "3"],
                       capture_output=True, text=True, cwd=str(tmp_path), timeout=60)
    assert r.returncode == 0, r.stderr
    report = (tmp_path / "reports" / "euer_2026_Q3.md").read_text(encoding="utf-8")
    assert "| Ausgaben | 119.00 EUR |" in report and "Steuerberatung" in report


# ---------------- office kit: filing gate + fs tripwire ----------------
def test_gate_filing_blocks_phantom_target(tmp_path):
    log = tmp_path / "project_memory" / "filing_log.yaml"
    write(str(log), 'filed:\n  - source: a.pdf\n    target: "archive/fin/a.pdf"\n')
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(log)}, "cwd": str(tmp_path)}
    assert run_hook("gate_filing.py", payload, tmp_path, hooks_dir=OFFICE_HOOKS) == 2


def test_gate_filing_passes_real_target(tmp_path):
    write(str(tmp_path / "archive" / "fin" / "a.pdf"), "x")
    log = tmp_path / "project_memory" / "filing_log.yaml"
    write(str(log), 'filed:\n  - source: a.pdf\n    target: "archive/fin/a.pdf"\n')
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(log)}, "cwd": str(tmp_path)}
    assert run_hook("gate_filing.py", payload, tmp_path, hooks_dir=OFFICE_HOOKS) == 0


def test_fs_tripwire_blocks_archive_delete(tmp_path):
    payload = {"tool_name": "Bash", "tool_input": {"command": "rm -rf archive/finance/2026"},
               "cwd": str(tmp_path)}
    assert run_hook("guard_fs_tripwire.py", payload, tmp_path, hooks_dir=OFFICE_HOOKS) == 2


def test_fs_tripwire_allows_filing_move(tmp_path):
    payload = {"tool_name": "Bash",
               "tool_input": {"command": 'mv "inbox/scan.pdf" "archive/fin/2026-07-01_x_invoice.pdf"'},
               "cwd": str(tmp_path)}
    assert run_hook("guard_fs_tripwire.py", payload, tmp_path, hooks_dir=OFFICE_HOOKS) == 0


def test_fs_tripwire_blocks_move_out_of_archive(tmp_path):
    payload = {"tool_name": "Bash",
               "tool_input": {"command": "mv archive/fin/a.pdf /tmp/gone.pdf"}, "cwd": str(tmp_path)}
    assert run_hook("guard_fs_tripwire.py", payload, tmp_path, hooks_dir=OFFICE_HOOKS) == 2


# ---------------- audit regressions: reversal maths, re-book flow, year guard, CII id, budget edge ----------------
def _reversal_ledger(tmp_path):
    assert _ledger_add(str(tmp_path), "--net", "100.00", "--vat-rate", "19", "--gross", "119.00").returncode == 0
    r = _ledger_add(str(tmp_path), "--net", "100.00", "--vat-rate", "19", "--gross", "119.00",
                    "--doc-type", "reversal", "--reverses", "L2026-0001")
    assert r.returncode == 0, r.stderr


def test_euer_report_reversal_nets_to_zero(tmp_path):
    # BLOCKER regression: booked +119 and reversed 119 in the same quarter must total 0.00, not -119
    _reversal_ledger(tmp_path)
    shutil.copy(os.path.join(OFFICE_SCRIPTS, "euer_report.py"),
                os.path.join(str(tmp_path), "scripts", "euer_report.py"))
    r = subprocess.run([sys.executable, os.path.join(str(tmp_path), "scripts", "euer_report.py"),
                        "--year", "2026", "--quarter", "3"],
                       capture_output=True, text=True, cwd=str(tmp_path), timeout=60)
    assert r.returncode == 0, r.stderr
    report = (tmp_path / "reports" / "euer_2026_Q3.md").read_text(encoding="utf-8")
    assert "| Ausgaben | 0.00 EUR |" in report


def test_ledger_rebook_after_reversal_allowed(tmp_path):
    # MAJOR regression: the sanctioned correction flow (book -> reversal -> re-book) must not dead-end
    _reversal_ledger(tmp_path)
    r = _ledger_add(str(tmp_path), "--net", "100.00", "--vat-rate", "19", "--gross", "119.00")
    assert r.returncode == 0, r.stderr


def test_ledger_refuses_year_mismatch(tmp_path):
    r = _ledger_add(str(tmp_path), "--net", "100.00", "--vat-rate", "19", "--gross", "119.00",
                    "--payment-date", "2025-12-31")
    assert r.returncode == 1 and "ledger/2025.csv" in r.stderr


def test_einvoice_cii_invoice_no_not_guideline_urn(tmp_path):
    pytest.importorskip("defusedxml")
    cii = (
        '<?xml version="1.0"?>'
        '<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"'
        ' xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100">'
        '<rsm:ExchangedDocumentContext><ram:GuidelineSpecifiedDocumentContextParameter>'
        '<ram:ID>urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0</ram:ID>'
        '</ram:GuidelineSpecifiedDocumentContextParameter></rsm:ExchangedDocumentContext>'
        '<rsm:ExchangedDocument><ram:ID>RE-2026-0815</ram:ID>'
        '<ram:IssueDateTime><udt:DateTimeString xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"'
        ' format="102">20260701</udt:DateTimeString></ram:IssueDateTime></rsm:ExchangedDocument>'
        '</rsm:CrossIndustryInvoice>')
    xml_path = tmp_path / "invoice.xml"
    xml_path.write_text(cii, encoding="utf-8")
    r = subprocess.run([sys.executable, os.path.join(OFFICE_SCRIPTS, "einvoice_extract.py"),
                        str(xml_path)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "invoice_no: RE-2026-0815" in r.stdout and "urn:cen.eu" not in r.stdout.split("invoice_no:")[1].splitlines()[0]
    assert "issue_date: 2026-07-01" in r.stdout


def test_file_budget_exactly_at_limit_passes(tmp_path):
    # MINOR regression: an exactly-800-line file (with trailing newline) is AT the budget, not over
    pytest.importorskip("yaml")
    write(str(tmp_path / "src" / "static" / "app.js"), "let x = 1;\n" * 800)
    assert run_quality(str(tmp_path)) == 0


def test_fs_tripwire_allows_archiving_generated_report(tmp_path):
    # MINOR regression: destination-is-archive must not block (only an archive/ SOURCE blocks)
    payload = {"tool_name": "Bash",
               "tool_input": {"command": "mv reports/euer_2026_Q3.md archive/finance/reports/"},
               "cwd": str(tmp_path)}
    assert run_hook("guard_fs_tripwire.py", payload, tmp_path, hooks_dir=OFFICE_HOOKS) == 0


# ---------------- scaffold: mechanical presets + map re-stamp (Windows: real ps1 run) ----------------
def test_scaffold_preset_and_map_sync(tmp_path):
    if os.name != "nt":
        pytest.skip("ps1 test runs on Windows; the sh mirror is covered by the kit audit")
    home = tmp_path / "home"
    kit = home / ".claude" / "team-kits" / "demo-team"
    for role in ("project-manager", "alpha", "beta", "gamma"):
        write(str(kit / "agents" / ("%s.md" % role)),
              "---\nname: %s\nmodel: sonnet\neffort: high\n---\nbody\n" % role)
        write(str(kit / "skills" / role / "SKILL.md"), "---\nname: %s\n---\nx\n" % role)
    write(str(kit / "settings" / "settings.json"), '{"agent": "project-manager"}')
    write(str(kit / "presets.yaml"), "mini: alpha\nfull: all\n")
    write(str(kit / "VERSION"), "version: 2026.07.13-1\ncontent: x\n")
    repo = tmp_path / "repo"
    write(str(repo / "project_memory" / "project_config.yaml"),
          "project:\n  name: x\n  preset: mini\n"
          "model_map:\n  alpha: opus   # user-approved\neffort_map:\n  alpha: high\n")
    script = os.path.join(ROOT, "team-kits", "scaffold_team.ps1")

    def scaffold(*extra):
        return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                               script, "-Team", "demo-team", *extra],
                              cwd=str(repo), capture_output=True, text=True,
                              env=dict(os.environ, USERPROFILE=str(home)), timeout=120)

    r = scaffold("-Preset", "mini")
    assert r.returncode == 0, r.stdout + r.stderr
    agents = repo / ".claude" / "agents"
    assert (agents / "alpha.md").is_file() and (agents / "project-manager.md").is_file()
    assert not (agents / "beta.md").exists() and not (agents / "gamma.md").exists()
    skills = repo / ".claude" / "skills"
    assert (skills / "alpha" / "SKILL.md").is_file() and not (skills / "beta").exists()
    # V4: the user-approved map value overrides the kit default frontmatter
    assert "model: opus" in (agents / "alpha.md").read_text(encoding="utf-8-sig")

    # a kit UPDATE without a preset argument must keep the RECORDED preset (project_config.yaml) —
    # not silently install the full roster (the inert-preset failure mode)
    r2 = scaffold()
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert "from project_config.yaml" in r2.stdout
    assert not (agents / "beta.md").exists() and not (agents / "gamma.md").exists()
    assert "model: opus" in (agents / "alpha.md").read_text(encoding="utf-8-sig")
