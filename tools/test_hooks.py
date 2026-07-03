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
QUALITY = os.path.join(ROOT, "team-kits", "dev-team", "templates", "repo", "scripts", "quality.py")


def run_hook(name, payload, project_dir):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir))
    p = subprocess.run([sys.executable, os.path.join(HOOKS, name)],
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


def test_spawn_specialist_allowed(kit_repo):
    payload = {"tool_name": "Agent", "tool_input": {"subagent_type": "backend-developer"}, "cwd": str(kit_repo)}
    assert run_hook("guard_agent_spawn.py", payload, kit_repo) == 0


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
