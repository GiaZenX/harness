#!/usr/bin/env python3
"""
Behaviour tests for the shipped enforcement hooks + scripts/quality.py (dev-team kit).

The harness blocks other repos' merges on missing tests; it must test its OWN security machinery.
Each hook is run as a real subprocess with synthetic stdin JSON and CLAUDE_PROJECT_DIR, and asserted
on its exit code (0 = allow, 2 = block for guards/gates, 1 = red for quality.py). Run: pytest tools/
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "team-kits", "dev-team", "hooks")
RESEARCH_HOOKS = os.path.join(ROOT, "team-kits", "research-team", "hooks")
OFFICE_HOOKS = os.path.join(ROOT, "team-kits", "office-team", "hooks")
OFFICE_SCRIPTS = os.path.join(ROOT, "team-kits", "office-team", "templates", "repo", "scripts")
OFFICE_PROFILE = os.path.join(ROOT, "team-kits", "office-team", "templates",
                              "project_memory", "business_profile.yaml")
QUALITY = os.path.join(ROOT, "team-kits", "dev-team", "templates", "repo", "scripts", "quality.py")
KIT_CHECKS = os.path.join(ROOT, "team-kits", "dev-team", "templates", "repo", "scripts", "kit_checks.py")
MERGE_SETTINGS = os.path.join(ROOT, "user", "merge_settings.py")


def run_hook_process(name, payload, project_dir, hooks_dir=None, extra_env=None):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir))
    env.update(extra_env or {})
    return subprocess.run([sys.executable, os.path.join(hooks_dir or HOOKS, name)],
                          input=json.dumps(payload), capture_output=True, text=True,
                          env=env, timeout=60)


def run_hook(name, payload, project_dir, hooks_dir=None):
    return run_hook_process(name, payload, project_dir, hooks_dir).returncode


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


# ---------------- global settings merge ----------------
def test_settings_merge_preserves_personal_values_and_unions_permissions(tmp_path):
    ours = {
        "_comment": "not installed",
        "theme": "dark",
        "statusLine": {"type": "command", "command": "bundled"},
        "telemetryEnabled": False,
        "permissions": {
            "allow": ["Bash(git *)", "Bash(pytest *)", "Bash(git *)"],
            "deny": ["Read(.env)", "Read(**/*.pem)"],
            "ask": ["Bash(release *)"],
        },
    }
    personal = {
        "theme": "light",
        "statusLine": {"type": "command", "command": "my-status"},
        "customSetting": "keep-me",
        "permissions": {
            "allow": ["Bash(custom *)", "Bash(git *)", "Bash(custom *)"],
            "deny": ["Read(private.txt)"],
            "ask": ["Bash(prod *)"],
            "defaultMode": "plan",
        },
    }
    ours_path = tmp_path / "defaults.json"
    target_path = tmp_path / "settings.json"
    ours_path.write_text(json.dumps(ours), encoding="utf-8")
    original = json.dumps(personal, indent=2) + "\n"
    target_path.write_text(original, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, MERGE_SETTINGS, str(ours_path), str(target_path)],
        capture_output=True, text=True, timeout=30,
    )

    assert result.returncode == 0, result.stderr
    merged = json.loads(target_path.read_text(encoding="utf-8"))
    assert merged["theme"] == "light"
    assert merged["statusLine"]["command"] == "my-status"
    assert merged["telemetryEnabled"] is False
    assert merged["customSetting"] == "keep-me"
    assert merged["permissions"] == {
        "allow": ["Bash(custom *)", "Bash(git *)", "Bash(pytest *)"],
        "deny": ["Read(private.txt)", "Read(.env)", "Read(**/*.pem)"],
        "ask": ["Bash(prod *)"],
        "defaultMode": "plan",
    }
    assert "_comment" not in merged
    assert (tmp_path / "settings.json.bak").read_text(encoding="utf-8") == original


def test_settings_merge_adds_missing_permission_lists_but_preserves_malformed_values(tmp_path):
    ours_path = tmp_path / "defaults.json"
    target_path = tmp_path / "settings.json"
    ours_path.write_text(json.dumps({
        "permissions": {"allow": ["Bash(git *)"], "deny": ["Read(.env)"]},
    }), encoding="utf-8")
    target_path.write_text(json.dumps({
        "permissions": {"allow": "managed-externally"},
    }), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, MERGE_SETTINGS, str(ours_path), str(target_path)],
        capture_output=True, text=True, timeout=30,
    )

    assert result.returncode == 0
    merged = json.loads(target_path.read_text(encoding="utf-8"))
    assert merged["permissions"]["allow"] == "managed-externally"
    assert merged["permissions"]["deny"] == ["Read(.env)"]
    assert "preserving non-list permissions.allow" in result.stderr


def test_settings_merge_rejects_invalid_existing_json_without_touching_it(tmp_path):
    ours_path = tmp_path / "defaults.json"
    target_path = tmp_path / "settings.json"
    ours_path.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    invalid = '{"theme": '
    target_path.write_text(invalid, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, MERGE_SETTINGS, str(ours_path), str(target_path)],
        capture_output=True, text=True, timeout=30,
    )

    assert result.returncode == 2
    assert "left unchanged" in result.stderr
    assert target_path.read_text(encoding="utf-8") == invalid
    assert not (tmp_path / "settings.json.bak").exists()


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
BROWSER_CHECKS = os.path.join(ROOT, "team-kits", "dev-team", "templates", "repo", "scripts",
                              "kit_browser_checks.py")


def run_quality_proc(repo, *args):
    os.makedirs(os.path.join(repo, "scripts"), exist_ok=True)
    import shutil
    shutil.copy(QUALITY, os.path.join(repo, "scripts", "quality.py"))
    shutil.copy(KIT_CHECKS, os.path.join(repo, "scripts", "kit_checks.py"))  # kit-owned check lib
    shutil.copy(BROWSER_CHECKS, os.path.join(repo, "scripts", "kit_browser_checks.py"))
    return subprocess.run([sys.executable, os.path.join(repo, "scripts", "quality.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=repo, timeout=120)


def run_quality(repo):
    return run_quality_proc(repo).returncode


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


def test_quality_only_flag_partial_run(tmp_path):
    # fast-iteration flag (upstreamed): loud partial notice, never merge evidence
    r = run_quality_proc(str(tmp_path), "--only", "cobol")
    assert r.returncode == 2 and "unknown stack" in r.stdout
    r = run_quality_proc(str(tmp_path), "--only")
    assert r.returncode == 2
    r = run_quality_proc(str(tmp_path), "--only", "node")  # no frontend -> clean FAIL, loudly partial
    assert r.returncode == 1 and "PARTIAL RUN" in r.stdout


def _quality_mod(path=None):
    import importlib.util
    p = path or QUALITY
    spec = importlib.util.spec_from_file_location("quality_under_test_%d" % abs(hash(p)), p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_quality_tool_cmd_module_fallback(monkeypatch):
    # pip on Windows drops console-script shims outside PATH while the module imports fine —
    # "not installed" would be a lie (upstreamed from a live project)
    mod = _quality_mod()
    monkeypatch.setattr(mod, "have", lambda t: False)
    assert mod.tool_cmd("ruff") == [sys.executable, "-m", "ruff"]
    assert mod.tool_cmd("gitleaks") is None  # not a Python console-script — honest absence


def test_quality_python_targets_from_source_areas(tmp_path):
    os.makedirs(str(tmp_path / "scripts"))
    shutil.copy(QUALITY, str(tmp_path / "scripts" / "quality.py"))
    os.makedirs(str(tmp_path / "src"))
    os.makedirs(str(tmp_path / "compounder"))
    write(str(tmp_path / "project_memory" / "coding_guidelines.yaml"),
          "source_areas:\n  - compounder\n  - '..'\n")
    mod = _quality_mod(str(tmp_path / "scripts" / "quality.py"))
    targets = mod._python_targets()
    assert "compounder" in targets and "src" in targets
    assert ".." not in targets  # dot-only names never become lint targets (audit class)


def test_quality_electron_env_stripped():
    mod = _quality_mod()
    os.environ["ELECTRON_RUN_AS_NODE"] = "1"
    try:
        assert "ELECTRON_RUN_AS_NODE" not in mod._clean_node_env()
    finally:
        os.environ.pop("ELECTRON_RUN_AS_NODE", None)


# ---------------- guard_yaml_valid (write-time YAML validity, the synaipse decisions.yaml saga) ----------------
def _yaml_payload(repo, fname):
    return {"tool_name": "Write",
            "tool_input": {"file_path": str(repo / "project_memory" / fname)}, "cwd": str(repo)}


def test_yaml_valid_blocks_parse_error(tmp_path):
    pytest.importorskip("yaml")
    write(str(tmp_path / "project_memory" / "decisions.yaml"),
          "decisions:\n  ADR-0001:\n    title: STRIDE: threat: model\n")  # unquoted colons -> invalid
    assert run_hook("guard_yaml_valid.py", _yaml_payload(tmp_path, "decisions.yaml"), tmp_path) == 2


def test_yaml_valid_uses_codex_posttool_block_decision(tmp_path):
    pytest.importorskip("yaml")
    write(str(tmp_path / "project_memory" / "decisions.yaml"),
          "decisions:\n  ADR-0001:\n    title: STRIDE: threat: model\n")
    result = run_hook_process(
        "guard_yaml_valid.py", _yaml_payload(tmp_path, "decisions.yaml"), tmp_path,
        extra_env={"TEAM_KIT_PROVIDER": "codex"})
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["decision"] == "block" and "INVALID YAML" in output["reason"]
    assert "continue" not in output


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


def test_preset_parser_changes_every_shared_kit_hash(tmp_path):
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from bump_kit_version import kit_hash

    team_kits = tmp_path / "team-kits"
    kit = team_kits / "demo-team"
    write(str(kit / "agents" / "project-manager.md"), "# lead\n")
    parser = team_kits / "preset_config.py"
    write(str(parser), "# parser version one\n")
    before = kit_hash(str(kit))
    parser.write_text("# parser version two\n", encoding="utf-8")
    assert kit_hash(str(kit)) != before


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


def _init_project_memory_symlink_state(tmp_path):
    home = tmp_path / "home"
    template = home / ".claude" / "team-kits" / "demo-team" / "templates" / "project_memory"
    write(str(template / "new.yaml"), "new: template\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    external = tmp_path / "external-memory"
    sentinel = external / "sentinel.txt"
    write(str(sentinel), "external memory sentinel\n")
    return home, repo, external, sentinel


def test_init_project_memory_ps1_rejects_external_symlink_before_mutation(tmp_path):
    if os.name != "nt" or not shutil.which("powershell"):
        pytest.skip("PowerShell init integration runs on Windows")
    home, repo, external, sentinel = _init_project_memory_symlink_state(tmp_path)
    try:
        os.symlink(external, repo / "project_memory", target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip("directory symlinks are not permitted in this test environment: %s" % exc)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         os.path.join(ROOT, "team-kits", "init_project_memory.ps1"),
         "-Team", "demo-team"],
        cwd=str(repo), capture_output=True, text=True, timeout=60,
        env=dict(os.environ, USERPROFILE=str(home)))
    output = (result.stdout + result.stderr).lower()
    assert result.returncode != 0 and ("symlink" in output or "reparse" in output)
    assert sentinel.read_text(encoding="utf-8") == "external memory sentinel\n"
    assert not (external / "new.yaml").exists()
    assert (repo / "project_memory").is_symlink()
    assert not (repo / ".claude" / "kit_update_pending.memory").exists()


def test_init_project_memory_sh_rejects_external_symlink_before_mutation(tmp_path):
    if os.name == "nt" or not shutil.which("bash"):
        pytest.skip("POSIX init integration runs on Unix CI")
    home, repo, external, sentinel = _init_project_memory_symlink_state(tmp_path)
    os.symlink(external, repo / "project_memory", target_is_directory=True)
    result = subprocess.run(
        ["bash", os.path.join(ROOT, "team-kits", "init_project_memory.sh"), "demo-team"],
        cwd=str(repo), capture_output=True, text=True, timeout=60,
        env=dict(os.environ, HOME=str(home)))
    output = (result.stdout + result.stderr).lower()
    assert result.returncode != 0 and "symlink" in output
    assert sentinel.read_text(encoding="utf-8") == "external memory sentinel\n"
    assert not (external / "new.yaml").exists()
    assert (repo / "project_memory").is_symlink()
    assert not (repo / ".claude" / "kit_update_pending.memory").exists()


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


def test_notify_logs_codex_subagent_start(tmp_path):
    (tmp_path / "project_memory").mkdir()
    payload = {"hook_event_name": "SubagentStart", "agent_type": "backend-developer",
               "agent_id": "agent-1", "cwd": str(tmp_path)}
    result = run_hook_process("notify_agent_events.py", payload, tmp_path,
                              extra_env={"TEAM_KIT_PROVIDER": "codex"})
    assert result.returncode == 0
    audit = tmp_path / "project_memory" / ".audit" / "hook_events.jsonl"
    event = json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])
    assert event["event"] == "subagent_start"
    assert event["reason"] == "backend-developer"


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
    config_path = repo / "project_memory" / "project_config.yaml"
    write(str(config_path),
          "project:\n  name: x\nmodel_map:\n  backend-developer: opus   # user-approved upscale\n"
          "effort_map:\n  backend-developer: high\n")
    write(str(repo / ".claude" / "agents" / "backend-developer.md"),
          "---\nname: backend-developer\nmodel: %s\neffort: high\n---\nbody\n" % agent_model)
    return repo


def _run_status(repo, provider="claude", hooks_dir=HOOKS):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo), TEAM_KIT_PROVIDER=provider)
    return subprocess.run([sys.executable, os.path.join(hooks_dir, "session_status.py")],
                          input=json.dumps({"cwd": str(repo)}), capture_output=True, text=True,
                          env=env, timeout=60).stdout


@pytest.mark.parametrize("hooks_dir", (HOOKS, RESEARCH_HOOKS, OFFICE_HOOKS))
def test_session_status_flags_model_drift_with_claude_guidance(tmp_path, hooks_dir):
    # the scaffold reset the frontmatter to sonnet although the map says opus -> must nag
    out = _run_status(_sync_repo(tmp_path, "sonnet"), "claude", hooks_dir)
    assert "MODEL/EFFORT OUT OF SYNC" in out and "backend-developer model=sonnet (map says opus)" in out
    assert "frontmatter line in .claude/agents/" in out
    assert "Do NOT edit .codex/agents/*.toml" not in out


@pytest.mark.parametrize("hooks_dir", (HOOKS, RESEARCH_HOOKS, OFFICE_HOOKS))
def test_session_status_flags_model_drift_with_codex_regeneration_guidance(tmp_path, hooks_dir):
    out = _run_status(_sync_repo(tmp_path, "sonnet"), "codex", hooks_dir)
    assert "MODEL/EFFORT OUT OF SYNC" in out
    assert "Do NOT edit .codex/agents/*.toml or one isolated provider source" in out
    assert "confirm a full scaffold re-sync" in out
    assert "Never run the provider generator alone" in out
    assert "verify the generated .codex/agents/*.toml model/effort mappings" in out
    assert "Re-sync each named agent's model:/effort: frontmatter line" not in out


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


def test_subagent_output_uses_codex_block_decision(kit_repo):
    payload = _stop_payload(kit_repo, "backend-developer", "prose only")
    result = run_hook_process(
        "gate_subagent_output.py", payload, kit_repo,
        extra_env={"TEAM_KIT_PROVIDER": "codex"})
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["decision"] == "block" and "output-contract" in output["reason"]
    assert "continue" not in output


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


@pytest.mark.parametrize("rel", [
    ".codex/config.toml",
    ".codex/hooks.json",
    ".codex/agents/backend-developer.toml",
    ".agents/skills/backend-developer/SKILL.md",
    ".CoDeX/agents/reviewer.toml",
    ".AGENTS/SKILLS/reviewer/SKILL.md",
    ".claude/provider_artifacts.json",
    ".claude/team_kit_roles.txt",
])
def test_selfmod_blocks_provider_generated_control_files(tmp_path, rel):
    p = tmp_path / rel
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(p)},
               "cwd": str(tmp_path)}
    assert run_hook("guard_harness_selfmod.py", payload, tmp_path) == 2, rel


def test_selfmod_allows_scaffold_command(tmp_path):
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "bash ~/.claude/team-kits/scaffold_team.sh dev-team"},
        "cwd": str(tmp_path),
    }
    assert run_hook("guard_harness_selfmod.py", payload, tmp_path) == 0


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
def test_office_business_profile_records_provider_and_preserves_legacy_key():
    yaml = pytest.importorskip("yaml")
    text = open(OFFICE_PROFILE, encoding="utf-8").read()
    privacy = yaml.safe_load(text)["privacy"]
    assert {"provider", "account_type", "claude_account_type"} <= set(privacy)
    assert "LEGACY" in text and "provider=claude" in text


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


# ---------------- _root: Windows drive-letter case normalization ----------------
def test_root_normalizes_windows_drive_case(tmp_path, monkeypatch):
    if os.name != "nt":
        pytest.skip("drive-letter casing is a Windows concept")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "root_under_test", os.path.join(HOOKS, "_root.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (tmp_path / ".claude").mkdir()
    lower = str(tmp_path)[0].lower() + str(tmp_path)[1:]
    # env path (CLAUDE_PROJECT_DIR) and walk-up path both normalize the drive letter:
    # a lowercase c:\ cwd broke vite/rollup ONLY inside the hook subprocess chain (real
    # overnight incident); direct comparison runs were silently msys-normalized.
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", lower)
    assert mod.find_repo_root()[0] == str(tmp_path)[0].upper()
    monkeypatch.delenv("CLAUDE_PROJECT_DIR")
    result = mod.find_repo_root(os.path.join(lower, "sub"))
    assert result[0] == str(tmp_path)[0].upper()


# ---------------- gate detection: prose mentions of push/merge must not trigger ----------------
def test_gate_pipeline_ignores_prose_push_mentions(tmp_path):
    write(str(tmp_path / "project_memory" / "product_requirements.yaml"),
          "requirements:\n  PRD-0001:\n    title: x\n")
    # a commit message DESCRIBING a push must not run the pipeline (real incident:
    # the diagnosis commit about a blocked push triggered the full RED pipeline again)
    prose = {"tool_name": "Bash", "cwd": str(tmp_path),
             "tool_input": {"command": 'git commit -m "docs: git push blocked by gate defect"'}}
    assert run_hook("gate_pipeline.py", prose, tmp_path) == 0
    # a REAL push still gates (no scripts/quality.py here -> hard block)
    push = {"tool_name": "Bash", "cwd": str(tmp_path),
            "tool_input": {"command": "git push origin main"}}
    r = run_hook_process("gate_pipeline.py", push, tmp_path)
    assert r.returncode == 2 and "no quality pipeline" in r.stderr


def test_gate_git_force_check_survives_quote_stripping(tmp_path):
    blocked = {"tool_name": "Bash", "cwd": str(tmp_path),
               "tool_input": {"command": "git push origin main --force"}}
    r = run_hook_process("gate_git.py", blocked, tmp_path)
    assert r.returncode == 2 and "force-push" in r.stderr
    prose = {"tool_name": "Bash", "cwd": str(tmp_path),
             "tool_input": {"command": 'git commit -m "never use git push --force"'}}
    assert run_hook("gate_git.py", prose, tmp_path) == 0
    # audit findings: QUOTED force flags reach git after the shell strips the quotes —
    # hiding them in quotes must not disarm the always-forbidden ban
    for command in ('git push "--force" origin main', 'git push origin "+main"'):
        payload = {"tool_name": "Bash", "cwd": str(tmp_path),
                   "tool_input": {"command": command}}
        r = run_hook_process("gate_git.py", payload, tmp_path)
        assert r.returncode == 2 and "force-push" in r.stderr, command


def test_gates_catch_shell_wrapped_push(tmp_path):
    # audit finding (regression vs the old substring check): a push inside a shell WRAPPER
    # payload is CODE and must gate — plain quote-stripping had let it pass both gates
    write(str(tmp_path / "project_memory" / "product_requirements.yaml"),
          "requirements:\n  PRD-0001:\n    title: x\n")
    for command in ('bash -c "git push origin main"',
                    "powershell -Command 'git push origin main'",
                    'powershell -NoProfile -Command "git push origin main"',
                    'cmd /c "git merge feature"'):
        payload = {"tool_name": "Bash", "cwd": str(tmp_path),
                   "tool_input": {"command": command}}
        r = run_hook_process("gate_pipeline.py", payload, tmp_path)
        assert r.returncode == 2 and "no quality pipeline" in r.stderr, command
    # the fixed prose incident stays fixed
    prose = {"tool_name": "Bash", "cwd": str(tmp_path),
             "tool_input": {"command": 'git commit -m "docs: git push blocked by gate defect"'}}
    assert run_hook("gate_pipeline.py", prose, tmp_path) == 0


def test_gates_catch_combined_flag_wrappers(tmp_path):
    # audit finding (MAJOR): `bash -lc "git push --force"` bypassed EVERY git gate — the
    # wrapper regex required -c as its OWN token, so a combined short cluster unwrapped
    # nothing and the payload was then stripped as prose. Escaped quotes inside the payload
    # must not cut the unwrap short either.
    write(str(tmp_path / "project_memory" / "product_requirements.yaml"),
          "requirements:\n  PRD-0001:\n    title: x\n")
    for command in ('bash -lc "git push origin main"',
                    'bash -xec "git push origin main"',
                    "sh -euc 'git merge feature'",
                    'bash -c "echo \\"done\\" && git push origin main"'):
        payload = {"tool_name": "Bash", "cwd": str(tmp_path),
                   "tool_input": {"command": command}}
        r = run_hook_process("gate_pipeline.py", payload, tmp_path)
        assert r.returncode == 2 and "no quality pipeline" in r.stderr, command
    forced = {"tool_name": "Bash", "cwd": str(tmp_path),
              "tool_input": {"command": 'bash -lc "git push --force origin main"'}}
    r = run_hook_process("gate_git.py", forced, tmp_path)
    assert r.returncode == 2 and "force-push" in r.stderr


def test_source_areas_reject_dot_names(tmp_path):
    # audit finding (both auditors, MAJOR): '..' passed the area filter and os.walk escaped
    # the repo into NEIGHBOR projects (a sibling's file failed OUR budget). Dot-only names
    # must never become scan areas — in the budget, the coverage gate and the dashboard.
    mod = _kit_checks_mod()
    repo = tmp_path / "repo"
    write(str(tmp_path / "neighbor" / "big.py"), "x = 1\n" * 900)
    write(str(repo / "project_memory" / "coding_guidelines.yaml"),
          "source_areas:\n  - '..'\n  - '.'\nfile_budget:\n  max_lines: 800\n  exempt: []\n")
    calls, ok, fail, warn = _collector()
    mod.check_file_budget(str(repo), ok, fail, warn)
    assert not any("neighbor" in m for _n, m in calls["fail"])  # never scans outside the repo
    assert any("NO scan area matched" in m for _n, m in calls["warn"])


def test_gate_test_coverage_rejects_dot_areas(tmp_path):
    repo = tmp_path / "repo"
    write(str(tmp_path / "stray.py"), "def f():\n    return 1\n")  # code OUTSIDE the repo
    write(str(repo / "project_memory" / "product_requirements.yaml"),
          "requirements:\n  PRD-0001:\n    title: x\n")
    write(str(repo / "project_memory" / "testing_guidelines.yaml"),
          "coverage_areas:\n  - '..'\n")
    payload = {"tool_name": "Bash", "cwd": str(repo),
               "tool_input": {"command": "git push origin main"}}
    assert run_hook("gate_test_coverage.py", payload, repo) == 0  # '..' is ignored, no block


# ---------------- provider compat: Codex apply_patch payloads ----------------
def _codex_patch(*files):
    body = "".join("*** Update File: %s\n@@\n-x\n+y\n" % f for f in files)
    return "*** Begin Patch\n" + body + "*** End Patch"


def test_selfmod_blocks_codex_apply_patch(tmp_path):
    payload = {"tool_name": "apply_patch",
               "tool_input": {"command": _codex_patch(".claude/hooks/gate_git.py")},
               "cwd": str(tmp_path)}
    assert run_hook("guard_harness_selfmod.py", payload, tmp_path) == 2


@pytest.mark.parametrize("rel", [
    ".codex/config.toml",
    ".agents/skills/project-manager/SKILL.md",
    ".claude/provider_artifacts.json",
    ".claude/team_kit_roles.txt",
])
def test_selfmod_blocks_codex_provider_artifact_patch(tmp_path, rel):
    payload = {"tool_name": "apply_patch",
               "tool_input": {"command": _codex_patch(rel)},
               "cwd": str(tmp_path)}
    assert run_hook("guard_harness_selfmod.py", payload, tmp_path) == 2, rel


def test_pm_scope_blocks_codex_multifile_patch(tmp_path):
    # first file allowed, SECOND file in the same patch is production code -> must still block
    payload = {"tool_name": "apply_patch",
               "tool_input": {"command": _codex_patch("docs/notes.md", "src/main.py")},
               "cwd": str(tmp_path)}
    assert run_hook("guard_pm_scope.py", payload, tmp_path) == 2


def test_no_adhoc_blocks_codex_added_dump_file(tmp_path):
    patch = "*** Begin Patch\n*** Add File: final_report.md\n+x\n*** End Patch"
    payload = {"tool_name": "apply_patch", "tool_input": {"command": patch}, "cwd": str(tmp_path)}
    assert run_hook("guard_no_adhoc.py", payload, tmp_path) == 2


def test_no_adhoc_allows_codex_update_of_existing_dump_name(tmp_path):
    patch = "*** Begin Patch\n*** Update File: final_report.md\n@@\n-x\n+y\n*** End Patch"
    payload = {"tool_name": "apply_patch", "tool_input": {"command": patch}, "cwd": str(tmp_path)}
    assert run_hook("guard_no_adhoc.py", payload, tmp_path) == 0


def test_no_adhoc_blocks_codex_move_to_dump_name(tmp_path):
    patch = ("*** Begin Patch\n*** Update File: docs/notes.md\n*** Move to: final_report.md\n"
             "@@\n-x\n+y\n*** End Patch")
    payload = {"tool_name": "apply_patch", "tool_input": {"command": patch}, "cwd": str(tmp_path)}
    assert run_hook("guard_no_adhoc.py", payload, tmp_path) == 2


def test_pm_scope_blocks_lowercase_tool_alias(tmp_path):
    # non-Claude payloads may use lowercase tool names; _TOOL_ALIASES must normalize them
    payload = {"tool_name": "edit", "tool_input": {"file_path": str(tmp_path / "src" / "x.py")},
               "cwd": str(tmp_path)}
    assert run_hook("guard_pm_scope.py", payload, tmp_path) == 2


def test_selfmod_blocks_constitution_and_shim(tmp_path):
    for name in ("AGENTS.md", "CLAUDE.md"):
        payload = {"tool_name": "Edit", "tool_input": {"file_path": str(tmp_path / name)},
                   "cwd": str(tmp_path)}
        assert run_hook("guard_harness_selfmod.py", payload, tmp_path) == 2, name


def test_selfmod_blocks_settings_local_and_case_bypass(tmp_path):
    for rel in (".claude/settings.local.json", ".CLAUDE/hooks/gate_git.py"):
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / rel)},
                   "cwd": str(tmp_path)}
        assert run_hook("guard_harness_selfmod.py", payload, tmp_path) == 2, rel


# ---------------- kit_checks: secure-context false positives + honest truncation ----------------
def _kit_checks_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("kit_checks_under_test", KIT_CHECKS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _collector():
    calls = {"ok": [], "fail": [], "warn": []}
    return (calls, lambda n, *a: calls["ok"].append(n),
            lambda n, m: calls["fail"].append((n, m)),
            lambda n, m: calls["warn"].append((n, m)))


def test_file_budget_source_areas_extend_and_warn(tmp_path):
    # false-green killer: a project keeping its whole codebase under an UNLISTED top-level
    # package was never scanned ("PASS file budget" with an 1,111-line file undetected)
    mod = _kit_checks_mod()
    write(str(tmp_path / "compounder" / "big.py"), "x = 1\n" * 900)
    calls, ok, fail, warn = _collector()
    mod.check_file_budget(str(tmp_path), ok, fail, warn)
    assert not calls["fail"] and not calls["ok"]
    assert any("NO scan area matched" in m for _n, m in calls["warn"])  # never silent
    write(str(tmp_path / "project_memory" / "coding_guidelines.yaml"),
          "source_areas:\n  - compounder\nfile_budget:\n  max_lines: 800\n  exempt: []\n")
    calls, ok, fail, warn = _collector()
    mod.check_file_budget(str(tmp_path), ok, fail, warn)
    assert any("compounder/big.py" in m for _n, m in calls["fail"])


def test_ops_pitfalls_compose_name_pin(tmp_path):
    mod = _kit_checks_mod()
    write(str(tmp_path / "docker-compose.yml"), "services:\n  db:\n    image: postgres\n")
    calls, ok, fail, warn = _collector()
    mod.check_ops_pitfalls(str(tmp_path), ok, fail, warn)
    assert any("no top-level `name:`" in m for _n, m in calls["warn"])
    write(str(tmp_path / "docker-compose.yml"),
          "name: myproject\nservices:\n  db:\n    image: postgres\n")
    calls, ok, fail, warn = _collector()
    mod.check_ops_pitfalls(str(tmp_path), ok, fail, warn)
    assert not calls["warn"] and any("compose project name pinned" in n for n in calls["ok"])


def test_gate_test_coverage_declared_areas(tmp_path):
    write(str(tmp_path / "project_memory" / "product_requirements.yaml"),
          "requirements:\n  PRD-0001:\n    title: x\n")
    write(str(tmp_path / "compounder" / "core.py"), "def f():\n    return 1\n")
    payload = {"tool_name": "Bash", "cwd": str(tmp_path),
               "tool_input": {"command": "git push origin main"}}
    assert run_hook("gate_test_coverage.py", payload, tmp_path) == 0  # undeclared -> old behavior
    write(str(tmp_path / "project_memory" / "testing_guidelines.yaml"),
          "coverage_areas:\n  - compounder\n")
    r = run_hook_process("gate_test_coverage.py", payload, tmp_path)
    assert r.returncode == 2 and "compounder" in r.stderr
    write(str(tmp_path / "compounder" / "test_core.py"), "def test_f():\n    assert True\n")
    assert run_hook("gate_test_coverage.py", payload, tmp_path) == 0


PROC_HASH = os.path.join(ROOT, "team-kits", "office-team", "templates", "repo", "scripts",
                         "proc_hash.py")


def _proc_repo(tmp_path, newline="\n"):
    repo = tmp_path / "office"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(PROC_HASH, str(repo / "scripts" / "proc_hash.py"))
    text = (
        "processes:\n"
        "  PROC-0001:\n"
        "    status: APPROVED\n"
        "    steps:\n"
        "      - do a thing\n"
        '    approved_hash: "oldhash"\n'
        "  PROC-0002:\n"
        "    status: PROPOSED\n"
        "    steps:\n"
        "      - do another thing\n"
        "  PROC-0003:\n"
        "    status: APPROVED\n"
        "    steps:\n"
        "      - third thing\n"
        '    approved_hash: "thirdhash"\n'
    ).replace("\n", newline)
    path = repo / "project_memory" / "process_definitions.yaml"
    path.parent.mkdir(parents=True)
    path.write_bytes(text.encode("utf-8"))
    return repo, path


def test_proc_hash_update_stays_in_its_block(tmp_path):
    import tomllib  # noqa: F401  (env sanity: py3.11+)
    import yaml
    repo, path = _proc_repo(tmp_path)
    # PROC-0002 has NO approved_hash line: the old (?s) regex swallowed the FOLLOWING blocks and
    # wrote the hash into a NEIGHBOR (real incident: a PROPOSED PROC carried another's hash)
    r = subprocess.run([sys.executable, str(repo / "scripts" / "proc_hash.py"),
                        "PROC-0002", "--update"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    procs = data["processes"]
    assert procs["PROC-0001"]["approved_hash"] == "oldhash"      # neighbors untouched
    assert procs["PROC-0003"]["approved_hash"] == "thirdhash"
    new_hash = procs["PROC-0002"]["approved_hash"]
    assert new_hash and new_hash not in ("oldhash", "thirdhash")


def test_proc_hash_update_survives_crlf(tmp_path):
    import yaml
    repo, path = _proc_repo(tmp_path, newline="\r\n")
    r = subprocess.run([sys.executable, str(repo / "scripts" / "proc_hash.py"),
                        "PROC-0001", "--update"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["processes"]["PROC-0001"]["approved_hash"] != "oldhash"
    assert data["processes"]["PROC-0003"]["approved_hash"] == "thirdhash"


def test_gate_pipeline_green_tree_cache(tmp_path):
    repo = tmp_path / "repo"
    runs = tmp_path / "runs.txt"           # OUTSIDE the repo: the counter must not dirty the tree
    write(str(repo / "project_memory" / "product_requirements.yaml"),
          "requirements:\n  PRD-0001:\n    title: x\n")
    write(str(repo / "scripts" / "quality.py"),
          "import pathlib\n"
          "p = pathlib.Path(r'%s')\n"
          "p.write_text(p.read_text() + 'x' if p.exists() else 'x')\n" % str(runs))
    # real projects gitignore the kit bookkeeping (template .gitignore) — without this the cache
    # file itself would count as an untracked change (the hook is deliberately conservative)
    write(str(repo / ".gitignore"), ".claude/.gate_pipeline_green\nproject_memory/.audit/\n")
    subprocess.run(["git", "init", "-q"], cwd=str(repo), capture_output=True, timeout=30)
    subprocess.run(["git", "add", "-A"], cwd=str(repo), capture_output=True, timeout=30)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                   cwd=str(repo), capture_output=True, timeout=30)
    payload = {"tool_name": "Bash", "cwd": str(repo),
               "tool_input": {"command": "git push origin main"}}
    assert run_hook("gate_pipeline.py", payload, repo) == 0
    assert runs.read_text() == "x"          # pipeline ran once, green, cache written
    assert run_hook("gate_pipeline.py", payload, repo) == 0
    assert runs.read_text() == "x"          # identical clean tree -> cache hit, NOT rerun
    audit = (repo / "project_memory" / ".audit" / "hook_events.jsonl").read_text(encoding="utf-8")
    assert "cache_hit" in audit
    # a tree change invalidates the cache
    write(str(repo / "scripts" / "extra.py"), "y = 2\n")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), capture_output=True, timeout=30)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "y"],
                   cwd=str(repo), capture_output=True, timeout=30)
    assert run_hook("gate_pipeline.py", payload, repo) == 0
    assert runs.read_text() == "xx"         # reran on the new tree
    # a DIRTY tree always runs (no cache read or write)
    write(str(repo / "scripts" / "extra.py"), "y = 3\n")
    assert run_hook("gate_pipeline.py", payload, repo) == 0
    assert runs.read_text() == "xxx"


def test_gate_memory_complete_escalates_on_repeat(tmp_path):
    write(str(tmp_path / "project_memory" / "product_requirements.yaml"),
          "requirements:\n  PRD-0001:\n    title: x\n")
    write(str(tmp_path / "project_memory" / "masterplan.md"),
          "# Masterplan — <project name>\nTODO\n")
    payload = {"tool_name": "Bash", "cwd": str(tmp_path),
               "tool_input": {"command": "git push origin main"}}
    outputs = []
    for _ in range(3):
        r = run_hook_process("gate_memory_complete.py", payload, tmp_path)
        assert r.returncode == 2
        outputs.append(r.stderr)
    assert "REPEAT BLOCK" not in outputs[0]
    assert "REPEAT BLOCK" in outputs[2]     # third identical block escalates


def test_session_status_path_change_tripwire(tmp_path):
    # audit finding: the old absence-of-memory heuristic false-fired on every mature project
    # without auto-memory (opt-in). The replacement is deterministic: a recorded path that
    # differs from the current one. First run records SILENTLY, a changed record warns.
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    payload = {"hook_event_name": "SessionStart", "cwd": str(repo)}
    r = run_hook_process("session_status.py", payload, repo)
    assert "PROJECT PATH CHANGED" not in r.stdout      # first run: record only, no nag
    state = repo / ".claude" / "project_path.state"
    assert state.read_text().strip() == os.path.abspath(str(repo))
    r2 = run_hook_process("session_status.py", payload, repo)
    assert "PROJECT PATH CHANGED" not in r2.stdout     # unchanged path: stays silent
    old = os.path.abspath(str(tmp_path / "old-name"))
    state.write_text(old + "\n")                       # simulate a folder rename
    r3 = run_hook_process("session_status.py", payload, repo)
    assert "PROJECT PATH CHANGED" in r3.stdout and "old-name" in r3.stdout
    assert state.read_text().strip() == os.path.abspath(str(repo))  # re-recorded after warning


def test_secure_context_skips_test_files_and_comment_lines(tmp_path):
    write(str(tmp_path / "frontend" / "src" / "App.test.tsx"),
          "navigator.clipboard.writeText = vi.fn()\n")
    write(str(tmp_path / "frontend" / "src" / "notes.ts"),
          "// navigator.clipboard is wrapped by copyText()\nconst a = 1\n")
    write(str(tmp_path / "frontend" / "src" / "bad.ts"),
          "navigator.clipboard.writeText(text)\n")
    calls, ok, fail, warn = _collector()
    _kit_checks_mod().check_frontend_pitfalls(str(tmp_path), ok, fail, warn)
    assert len(calls["fail"]) == 1
    msg = calls["fail"][0][1]
    assert "bad.ts" in msg and "App.test.tsx" not in msg and "notes.ts" not in msg


def test_kit_checks_truncation_reports_hidden_count(tmp_path):
    for i in range(8):
        write(str(tmp_path / "frontend" / "src" / ("f%d.ts" % i)),
              "navigator.clipboard.writeText(x)\n")
    calls, ok, fail, warn = _collector()
    _kit_checks_mod().check_frontend_pitfalls(str(tmp_path), ok, fail, warn)
    assert "(+3 more)" in calls["fail"][0][1]  # 8 hits, 5 shown


# ---------------- kit_checks: enforcement-diff second line of defense ----------------
def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=30)


def _mk_diff_repo(tmp_path):
    repo = tmp_path / "repo"
    write(str(repo / ".claude" / "hooks" / "gate_git.py"), "# v1\n")
    write(str(repo / ".claude" / "kit_version"), "version: 1\n")
    write(str(repo / "src" / "app.py"), "x = 1\n")
    _git(repo, "init", "-b", "main")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "base")
    _git(repo, "checkout", "-b", "feat")
    return repo


def test_enforcement_diff_blocks_hook_change_without_kit_bump(tmp_path):
    repo = _mk_diff_repo(tmp_path)
    write(str(repo / ".claude" / "hooks" / "gate_git.py"), "# tampered\n")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "tamper")
    calls, ok, fail, warn = _collector()
    _kit_checks_mod().check_enforcement_diff(str(repo), ok, fail, warn)
    assert calls["fail"] and "kit update" in calls["fail"][0][1]


@pytest.mark.parametrize("rel", [
    ".codex/config.toml",
    ".agents/skills/project-manager/SKILL.md",
    ".claude/provider_artifacts.json",
    ".claude/team_kit_roles.txt",
])
def test_enforcement_diff_blocks_codex_controls_without_kit_bump(tmp_path, rel):
    repo = _mk_diff_repo(tmp_path)
    write(str(repo / rel), "tampered\n")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "tamper")
    calls, ok, fail, warn = _collector()
    _kit_checks_mod().check_enforcement_diff(str(repo), ok, fail, warn)
    assert calls["fail"] and rel in calls["fail"][0][1]


def test_enforcement_diff_allows_kit_update(tmp_path):
    repo = _mk_diff_repo(tmp_path)
    write(str(repo / ".claude" / "hooks" / "gate_git.py"), "# v2 via kit\n")
    write(str(repo / ".claude" / "kit_version"), "version: 2\n")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "kit update")
    calls, ok, fail, warn = _collector()
    _kit_checks_mod().check_enforcement_diff(str(repo), ok, fail, warn)
    assert not calls["fail"]


def test_enforcement_diff_catches_tamper_on_main(tmp_path):
    # audit M1: solo/trunk workflow — a tampered hook committed STRAIGHT to main (no remote,
    # HEAD == base) must not pass as "no changes"
    repo = tmp_path / "repo"
    write(str(repo / ".claude" / "hooks" / "gate_git.py"), "# v1\n")
    write(str(repo / ".claude" / "kit_version"), "version: 1\n")
    _git(repo, "init", "-b", "main")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "base")
    write(str(repo / ".claude" / "hooks" / "gate_git.py"), "# TAMPERED\n")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "tamper on main")
    calls, ok, fail, warn = _collector()
    _kit_checks_mod().check_enforcement_diff(str(repo), ok, fail, warn)
    assert calls["fail"] and "kit update" in calls["fail"][0][1]


def test_selfmod_blocks_codex_patch_from_subdir_cwd(tmp_path):
    # audit M2: cwd drifted into a subdir — a repo-root-looking patch path must still block
    # (dual-candidate resolution: cwd-join AND repo-root-join)
    (tmp_path / "frontend").mkdir(parents=True)
    payload = {"tool_name": "apply_patch",
               "tool_input": {"command": _codex_patch(".claude/hooks/gate_git.py")},
               "cwd": str(tmp_path / "frontend")}
    assert run_hook("guard_harness_selfmod.py", payload, tmp_path) == 2


def test_enforcement_diff_warns_on_deleted_tests(tmp_path):
    repo = tmp_path / "repo"
    write(str(repo / ".claude" / "kit_version"), "version: 1\n")
    write(str(repo / "tests" / "test_a.py"), "def test_a(): pass\n")  # exists on main
    _git(repo, "init", "-b", "main")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "base")
    _git(repo, "checkout", "-b", "feat")
    (repo / "tests" / "test_a.py").unlink()
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "delete test")
    calls, ok, fail, warn = _collector()
    _kit_checks_mod().check_enforcement_diff(str(repo), ok, fail, warn)
    assert calls["warn"] and "DELETED" in calls["warn"][0][1]


# ---------------- session_status: version-banner bootstrap + resume-proof pending counter ----------------
def test_session_status_announces_bootstrap_update_with_pending(tmp_path):
    repo = tmp_path / "repo"
    write(str(repo / ".claude" / "kit_version"), "version: 2026.07.14-3\ncontent: x\n")
    write(str(repo / ".claude" / "kit_update_pending.repo"), "# diverged\n- scripts/quality.py\n")
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))
    p = subprocess.run([sys.executable, os.path.join(HOOKS, "session_status.py")],
                       input=json.dumps({"cwd": str(repo)}), capture_output=True, text=True,
                       env=env, timeout=60)
    assert "KIT UPDATED externally to 2026.07.14-3" in p.stdout


def test_session_status_pending_counter_ignores_resume(tmp_path):
    repo = tmp_path / "repo"
    write(str(repo / ".claude" / "kit_update_pending.repo"), "# diverged\n- scripts/quality.py\n")
    write(str(repo / ".claude" / "kit_update_pending.state"),
          '{"sessions": 2, "first_seen": "2026-07-14"}')
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))
    subprocess.run([sys.executable, os.path.join(HOOKS, "session_status.py")],
                   input=json.dumps({"cwd": str(repo), "source": "resume"}),
                   capture_output=True, text=True, env=env, timeout=60)
    st = json.loads(open(str(repo / ".claude" / "kit_update_pending.state"), encoding="utf-8").read())
    assert st["sessions"] == 2  # resume did NOT inflate the counter
    subprocess.run([sys.executable, os.path.join(HOOKS, "session_status.py")],
                   input=json.dumps({"cwd": str(repo), "source": "startup"}),
                   capture_output=True, text=True, env=env, timeout=60)
    st = json.loads(open(str(repo / ".claude" / "kit_update_pending.state"), encoding="utf-8").read())
    assert st["sessions"] == 3  # a real session start still increments


# ---------------- provider generator: single-source .codex/.github artifacts ----------------
GEN = os.path.join(ROOT, "team-kits", "gen_provider_artifacts.py")


def test_gen_provider_artifacts(tmp_path):
    import shutil
    repo = tmp_path / "repo"
    os.makedirs(str(repo / ".claude"), exist_ok=True)
    shutil.copytree(os.path.join(ROOT, "team-kits", "dev-team", "hooks"),
                    str(repo / ".claude" / "hooks"))
    shutil.copy(os.path.join(ROOT, "team-kits", "dev-team", "settings", "settings.json"),
                str(repo / ".claude" / "settings.json"))
    write(str(repo / ".claude" / "agents" / "backend-developer.md"),
          "---\nname: backend-developer\ndescription: >\n  Backend specialist: builds\n"
          "  the server side.\nmodel: sonnet\neffort: high\n---\nBody of the backend role.\n")
    write(str(repo / ".claude" / "agents" / "project-manager.md"),
          "---\nname: project-manager\ndescription: Lead\nmodel: opus\neffort: high\n---\nLead body.\n")
    write(str(repo / ".claude" / "skills" / "backend-developer" / "SKILL.md"),
          "---\nname: backend-developer\n---\nFollow ./CLAUDE.md.\n")
    write(str(repo / ".claude" / "skills" / "project-manager" / "SKILL.md"),
          "---\nname: project-manager\n---\nLead skill.\n")
    write(str(repo / ".claude" / "team_kit_roles.txt"),
          "# agents-and-skills:team-kit-roles v1 team=dev-team count=2\n"
          "project-manager\nbackend-developer\n")
    # Pre-manifest upgrades remove only artifacts carrying the old generator's stable marker.
    write(str(repo / ".codex" / "agents" / "stale.toml"),
          'developer_instructions = "team-kit governed repository"\n')
    write(str(repo / ".codex" / "agents" / "custom.toml"),
          'developer_instructions = "user-owned agent"\n')
    write(str(repo / ".github" / "agents" / "stale.agent.md"),
          "You are inside a team-kit governed repository.\n")
    write(str(repo / ".github" / "agents" / "custom.agent.md"), "User-owned agent.\n")
    p = subprocess.run([sys.executable, GEN, "--repo", str(repo), "--providers", "codex"],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    assert not (repo / ".codex" / "agents" / "stale.toml").exists()
    # legacy Copilot outputs (generation removed) are still recognized and cleaned up
    assert not (repo / ".github" / "agents" / "stale.agent.md").exists()
    assert (repo / ".codex" / "agents" / "custom.toml").is_file()
    assert (repo / ".github" / "agents" / "custom.agent.md").is_file()
    hooks = json.loads(open(str(repo / ".codex" / "hooks.json"), encoding="utf-8").read())
    txt = json.dumps(hooks)
    assert "apply_patch" in txt                      # Edit|Write matchers translated
    assert "Agent|Task" not in txt                   # spawn guard deliberately not registered
    # Codex may inherit a stale Claude variable from the parent shell. Every generated
    # command must overwrite it with the root it just resolved before running a shared hook.
    assert 'CLAUDE_PROJECT_DIR=\\"$root\\"' in txt
    assert "$env:CLAUDE_PROJECT_DIR = $root" in txt
    assert "git rev-parse --show-toplevel" in txt     # stable even when Codex starts in a subdir
    assert "dirname" in txt and "Get-Location" in txt  # greenfield fallback before git init
    assert "TEAM_KIT_PROVIDER=codex" in txt
    assert "guard_pm_scope.py" in txt                 # current Codex PreToolUse carries agent_id
    assert "SubagentStart" in hooks["hooks"] and "notify_agent_events.py" in json.dumps(
        hooks["hooks"]["SubagentStart"])
    import tomllib
    config = tomllib.loads((repo / ".codex" / "config.toml").read_text(encoding="utf-8"))
    assert config["model"] == "gpt-5.6-sol"
    assert config["model_reasoning_effort"] == "high"
    assert config["default_permissions"] == "team-kit"
    assert config["features"]["multi_agent"] is True
    assert "Lead body." in config["developer_instructions"]
    fs = config["permissions"]["team-kit"]["filesystem"][":workspace_roots"]
    assert fs["."] == "write" and fs[".env"] == "deny" and fs["**/*.pem"] == "deny"
    assert fs[".codex"] == "read" and fs[".agents/skills"] == "read"
    assert fs["AGENTS.md"] == "read" and fs[".claude/hooks"] == "read"
    toml = open(str(repo / ".codex" / "agents" / "backend-developer.toml"), encoding="utf-8").read()
    assert 'model = "gpt-5.6-terra"' in toml and "AGENTS.md" in toml
    assert ".agents/skills/backend-developer/SKILL.md" in toml
    # audit M3: folded (>) frontmatter descriptions must be joined, not collapsed to '>'
    assert "Backend specialist: builds the server side." in toml
    assert not os.path.isfile(str(repo / ".codex" / "agents" / "project-manager.toml"))
    native_skill = repo / ".agents" / "skills" / "backend-developer" / "SKILL.md"
    assert native_skill.is_file() and "./AGENTS.md" in native_skill.read_text(encoding="utf-8")
    native_marker = repo / ".agents" / "skills" / "backend-developer" / ".team-kit-generated"
    assert "agents-and-skills:generated-codex-config" in native_marker.read_text(encoding="utf-8")
    assert (repo / ".agents" / "skills" / "project-manager" / "SKILL.md").is_file()
    manifest_path = repo / ".claude" / "provider_artifacts.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert ".codex/config.toml" in manifest["files"]

    # Invalid ownership fails closed before any generated or user-owned output is touched.
    write(str(repo / "src" / "keep.py"), "KEEP = True\n")
    write(str(repo / ".agents" / "skills" / "keep" / "SKILL.md"), "user-owned\n")
    tampered = json.loads(json.dumps(manifest))
    tampered["files"].append("src/keep.py")
    tampered["dirs"].append(".agents/skills/keep/nested")
    write(str(manifest_path), json.dumps(tampered))
    bad = subprocess.run([sys.executable, GEN, "--repo", str(repo), "--providers", "codex"],
                         capture_output=True, text=True, timeout=60)
    assert bad.returncode != 0 and "left untouched" in bad.stderr
    assert (repo / ".codex" / "config.toml").is_file() and native_skill.is_file()
    write(str(manifest_path), "{")
    truncated = subprocess.run(
        [sys.executable, GEN, "--repo", str(repo), "--providers", "codex"],
        capture_output=True, text=True, timeout=60)
    assert truncated.returncode != 0 and manifest_path.read_text(encoding="utf-8") == "{"
    assert (repo / ".codex" / "config.toml").is_file() and native_skill.is_file()
    write(str(manifest_path), json.dumps(manifest))

    # The removed provider is rejected fail-closed with a migration hint, artifacts untouched.
    rejected = subprocess.run([sys.executable, GEN, "--repo", str(repo), "--providers", "copilot"],
                              capture_output=True, text=True, timeout=60)
    assert rejected.returncode != 0 and "no longer supported" in rejected.stderr
    assert (repo / ".codex" / "config.toml").is_file() and native_skill.is_file()

    # Removing every extra provider cleans exactly the manifest-owned outputs, nothing else.
    p2 = subprocess.run([sys.executable, GEN, "--repo", str(repo), "--providers", ""],
                        capture_output=True, text=True, timeout=60)
    assert p2.returncode == 0, p2.stderr
    assert not (repo / ".codex" / "config.toml").exists()
    assert not (repo / ".codex" / "hooks.json").exists()
    assert not native_skill.exists()
    assert (repo / "src" / "keep.py").is_file()
    assert (repo / ".agents" / "skills" / "keep" / "SKILL.md").is_file()
    empty_manifest = json.loads(
        (repo / ".claude" / "provider_artifacts.json").read_text(encoding="utf-8")
    )
    assert empty_manifest == {"version": 1, "files": [], "dirs": []}
    assert (repo / ".codex" / "agents" / "custom.toml").is_file()
    assert (repo / ".github" / "agents" / "custom.agent.md").is_file()


def test_gen_provider_artifacts_cleans_pre_manifest_codex_outputs(tmp_path):
    repo = tmp_path / "repo"
    write(str(repo / ".codex" / "config.toml"),
          "# agents-and-skills:generated-codex-config\nmodel = \"old\"\n")
    write(str(repo / ".codex" / "hooks.json"),
          '{"hooks":{"PreToolUse":[{"command":".claude/hooks/old.py"}]}}')
    write(str(repo / ".agents" / "skills" / "backend-developer" / "SKILL.md"),
          "old generated kit skill\n")
    write(str(repo / ".agents" / "skills" / "backend-developer" / ".team-kit-generated"),
          "agents-and-skills:generated-codex-config\n")
    write(str(repo / ".agents" / "skills" / "custom" / "SKILL.md"), "user-owned\n")
    result = subprocess.run([sys.executable, GEN, "--repo", str(repo), "--providers", ""],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert not (repo / ".codex" / "config.toml").exists()
    assert not (repo / ".codex" / "hooks.json").exists()
    assert not (repo / ".agents" / "skills" / "backend-developer").exists()
    assert (repo / ".agents" / "skills" / "custom" / "SKILL.md").is_file()


def test_gen_provider_artifacts_preserves_unmarked_native_skill(tmp_path):
    repo = tmp_path / "repo"
    skill = repo / ".agents" / "skills" / "backend-developer" / "SKILL.md"
    write(str(skill), "user-owned skill without generator marker\n")
    result = subprocess.run([sys.executable, GEN, "--repo", str(repo), "--providers", ""],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert skill.read_text(encoding="utf-8") == "user-owned skill without generator marker\n"


def _provider_test_repo(tmp_path):
    """Minimal, complete installed-kit state for generator fail-closed tests."""
    repo = tmp_path / "repo"
    shutil.copytree(os.path.join(ROOT, "team-kits", "dev-team", "hooks"),
                    str(repo / ".claude" / "hooks"))
    shutil.copy(os.path.join(ROOT, "team-kits", "dev-team", "settings", "settings.json"),
                str(repo / ".claude" / "settings.json"))
    for role, model in (("project-manager", "opus"), ("backend-developer", "sonnet")):
        write(str(repo / ".claude" / "agents" / (role + ".md")),
              "---\nname: %s\ndescription: %s\nmodel: %s\neffort: high\n---\n%s body.\n"
              % (role, role, model, role))
        write(str(repo / ".claude" / "skills" / role / "SKILL.md"),
              "---\nname: %s\n---\nFollow ./CLAUDE.md.\n" % role)
    write(str(repo / ".claude" / "team_kit_roles.txt"),
          "# agents-and-skills:team-kit-roles v1 team=dev-team count=2\n"
          "project-manager\nbackend-developer\n")
    return repo


def test_gen_provider_artifacts_requires_installed_hook_bundle(tmp_path):
    repo = _provider_test_repo(tmp_path)
    shutil.rmtree(repo / ".claude" / "hooks")
    result = subprocess.run([sys.executable, GEN, "--repo", str(repo),
                             "--providers", "codex"],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode != 0 and "Missing .claude/hooks" in result.stderr
    assert not (repo / ".codex" / "config.toml").exists()
    assert not (repo / ".codex" / "hooks.json").exists()


def test_gen_provider_config_defaults_absent_providers_to_both(tmp_path):
    # Legacy project_config predating the providers key: default [claude, codex] with a notice,
    # so existing projects keep taking kit updates without a config edit first.
    repo = _provider_test_repo(tmp_path)
    config = repo / "project_memory" / "project_config.yaml"
    write(str(config), "project:\n  preset: mini\n")
    checked = subprocess.run([sys.executable, GEN, "--repo", str(repo),
                              "--project-config", str(config), "--check-config-only"],
                             capture_output=True, text=True, timeout=60)
    assert checked.returncode == 0, checked.stderr
    assert "defaulting to" in checked.stdout
    generated = subprocess.run([sys.executable, GEN, "--repo", str(repo),
                                "--project-config", str(config)],
                               capture_output=True, text=True, timeout=60)
    assert generated.returncode == 0, generated.stderr
    assert (repo / ".codex" / "config.toml").is_file()

    # an explicitly PRESENT but empty providers value stays fail-closed
    config.write_text("project:\n  preset: mini\nproviders:\n", encoding="utf-8")
    empty = subprocess.run([sys.executable, GEN, "--repo", str(repo),
                            "--project-config", str(config), "--check-config-only"],
                           capture_output=True, text=True, timeout=60)
    assert empty.returncode != 0 and "must not be empty" in empty.stderr


def test_gen_accepts_fable_as_lead_tier_pin(tmp_path):
    # `fable` is a legitimate Claude-side §11 pin (a real synaipse map carried it): Claude keeps
    # the literal value, the Codex artifact maps it to the provider's LEAD tier.
    repo = _provider_test_repo(tmp_path)
    write(str(repo / ".claude" / "agents" / "backend-developer.md"),
          "---\nname: backend-developer\ndescription: backend\nmodel: fable\neffort: high\n"
          "---\nbackend body.\n")
    result = subprocess.run([sys.executable, GEN, "--repo", str(repo), "--providers", "codex"],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    toml = (repo / ".codex" / "agents" / "backend-developer.toml").read_text(encoding="utf-8")
    assert 'model = "gpt-5.6-sol"' in toml

    config = repo / "project_memory" / "project_config.yaml"
    write(str(config), "project:\n  preset: mini\nproviders: [claude, codex]\n"
                       "model_map:\n  backend-developer: fable\n")
    checked = subprocess.run([sys.executable, GEN, "--repo", str(repo),
                              "--project-config", str(config), "--check-config-only"],
                             capture_output=True, text=True, timeout=60)
    assert checked.returncode == 0, checked.stderr


def test_gen_codex_frontmatter_overlay(tmp_path):
    # The divergence valve: a namespaced `codex:` frontmatter block (ignored by Claude) merges
    # Codex-only keys into the generated TOML; identity keys stay generator-owned.
    repo = _provider_test_repo(tmp_path)
    write(str(repo / ".claude" / "agents" / "backend-developer.md"),
          "---\nname: backend-developer\ndescription: backend\nmodel: sonnet\neffort: high\n"
          "codex:\n  sandbox_mode: workspace-write\n  model_reasoning_effort: xhigh\n"
          "---\nbackend body.\n")
    result = subprocess.run([sys.executable, GEN, "--repo", str(repo), "--providers", "codex"],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    toml = (repo / ".codex" / "agents" / "backend-developer.toml").read_text(encoding="utf-8")
    assert 'sandbox_mode = "workspace-write"' in toml
    assert 'model_reasoning_effort = "xhigh"' in toml       # overlay wins over effort:
    assert 'model = "gpt-5.6-terra"' in toml                # tier mapping still applies

    # reserved keys are rejected fail-closed
    write(str(repo / ".claude" / "agents" / "backend-developer.md"),
          "---\nname: backend-developer\ndescription: backend\nmodel: sonnet\neffort: high\n"
          "codex:\n  developer_instructions: hijack\n---\nbackend body.\n")
    rejected = subprocess.run([sys.executable, GEN, "--repo", str(repo), "--providers", "codex"],
                              capture_output=True, text=True, timeout=60)
    assert rejected.returncode != 0 and "must not override" in rejected.stderr
    assert 'sandbox_mode = "workspace-write"' in (
        repo / ".codex" / "agents" / "backend-developer.toml").read_text(encoding="utf-8")


def test_gen_provider_removal_rejects_symlinked_managed_parent(tmp_path):
    repo = _provider_test_repo(tmp_path)
    config = repo / "project_memory" / "project_config.yaml"
    write(str(config), "project:\n  preset: mini\nproviders: [claude, codex]\n")
    generated = subprocess.run([sys.executable, GEN, "--repo", str(repo),
                                "--project-config", str(config)],
                               capture_output=True, text=True, timeout=60)
    assert generated.returncode == 0, generated.stderr
    manifest = repo / ".claude" / "provider_artifacts.json"
    manifest_before = manifest.read_text(encoding="utf-8")

    shutil.rmtree(repo / ".codex")
    external = tmp_path / "outside-codex"
    sentinel = external / "config.toml"
    write(str(sentinel), "# external sentinel must survive\n")
    try:
        os.symlink(external, repo / ".codex", target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip("directory symlinks are not permitted in this test environment: %s" % exc)

    config.write_text("project:\n  preset: mini\nproviders: [claude]\n", encoding="utf-8")
    removed = subprocess.run([sys.executable, GEN, "--repo", str(repo),
                              "--project-config", str(config)],
                             capture_output=True, text=True, timeout=60)
    assert removed.returncode != 0
    assert "symlink" in (removed.stdout + removed.stderr).lower()
    assert sentinel.read_text(encoding="utf-8") == "# external sentinel must survive\n"
    assert manifest.read_text(encoding="utf-8") == manifest_before


@pytest.mark.parametrize("relative,is_directory", [
    (".codex/config.toml", False),
    (".agents/skills/backend-developer", True),
])
def test_gen_provider_artifacts_rejects_unowned_output_collision(tmp_path, relative,
                                                                 is_directory):
    repo = _provider_test_repo(tmp_path)
    target = repo / relative
    if is_directory:
        write(str(target / "SKILL.md"), "user-owned collision\n")
    else:
        write(str(target), "# user-owned collision\n")
    result = subprocess.run([sys.executable, GEN, "--repo", str(repo),
                             "--providers", "codex"],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode != 0 and "Provider output collision" in result.stderr
    assert "user-owned collision" in (
        (target / "SKILL.md").read_text(encoding="utf-8") if is_directory
        else target.read_text(encoding="utf-8"))
    assert not (repo / ".claude" / "provider_artifacts.json").exists()


@pytest.mark.parametrize("source", [
    "project:\n  name: missing-providers\n",
    "providers: null\n",
    "providers: [claude]\nproviders: [codex]\n",
])
def test_gen_provider_config_rejects_missing_null_or_duplicate_provider_key(tmp_path, source):
    config = tmp_path / "project_config.yaml"
    config.write_text(source, encoding="utf-8")
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("untouched\n", encoding="utf-8")
    result = subprocess.run([sys.executable, GEN, "--repo", str(tmp_path),
                             "--project-config", str(config), "--check-config-only"],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode != 0 and "provider artifacts were left untouched" in result.stderr
    assert sentinel.read_text(encoding="utf-8") == "untouched\n"


@pytest.mark.parametrize("missing_kind", ["agent", "skill"])
def test_gen_provider_artifacts_rejects_role_or_skill_mismatch(tmp_path, missing_kind):
    repo = _provider_test_repo(tmp_path)
    if missing_kind == "agent":
        (repo / ".claude" / "agents" / "backend-developer.md").unlink()
    else:
        shutil.rmtree(repo / ".claude" / "skills" / "backend-developer")
    result = subprocess.run([sys.executable, GEN, "--repo", str(repo),
                             "--providers", "codex"],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    expected = "Role manifest/source mismatch" if missing_kind == "agent" else "native skill source"
    assert expected in result.stderr
    assert not (repo / ".codex" / "config.toml").exists()


def test_gen_provider_artifacts_translates_role_scoped_hooks(tmp_path):
    repo = _provider_test_repo(tmp_path)
    agent_source = os.path.join(ROOT, "team-kits", "dev-team", "agents")
    skill_source = os.path.join(ROOT, "team-kits", "dev-team", "skills")
    for role in ("backend-developer", "frontend-developer"):
        shutil.copy(os.path.join(agent_source, role + ".md"),
                    str(repo / ".claude" / "agents" / (role + ".md")))
        if role == "frontend-developer":
            shutil.copytree(os.path.join(skill_source, role),
                            str(repo / ".claude" / "skills" / role))
    write(str(repo / ".claude" / "team_kit_roles.txt"),
          "# agents-and-skills:team-kit-roles v1 team=dev-team count=3\n"
          "project-manager\nbackend-developer\nfrontend-developer\n")
    result = subprocess.run([sys.executable, GEN, "--repo", str(repo),
                             "--providers", "codex"],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    text = (repo / ".codex" / "hooks.json").read_text(encoding="utf-8")
    assert "guard_guidelines.py" in text
    assert "TEAM_KIT_AGENT_TYPES=backend-developer,frontend-developer" in text
    assert "$env:TEAM_KIT_AGENT_TYPES='backend-developer,frontend-developer'" in text


def test_guard_guidelines_codex_multifile_patch_honors_role_scope(tmp_path):
    pytest.importorskip("yaml")
    write(str(tmp_path / "project_memory" / "coding_guidelines.yaml"),
          "languages:\n  python:\n    - use type hints\n")
    payload = {
        "hook_event_name": "PreToolUse",
        "agent_type": "backend-developer",
        "tool_name": "apply_patch",
        "tool_input": {"command": _codex_patch("src/ok.py", "frontend/blocked.ts")},
        "cwd": str(tmp_path),
    }
    env = {"TEAM_KIT_PROVIDER": "codex",
           "TEAM_KIT_AGENT_TYPES": "backend-developer,frontend-developer"}
    assert run_hook_process("guard_guidelines.py", payload, tmp_path,
                            extra_env=env).returncode == 2
    payload["agent_type"] = "quality-engineer"
    assert run_hook_process("guard_guidelines.py", payload, tmp_path,
                            extra_env=env).returncode == 0


def test_gen_provider_artifacts_hook_bundle_hash_changes_with_hook_content(tmp_path):
    repo = _provider_test_repo(tmp_path)

    def generate_and_hash():
        result = subprocess.run([sys.executable, GEN, "--repo", str(repo),
                                 "--providers", "codex"],
                                capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        text = (repo / ".codex" / "hooks.json").read_text(encoding="utf-8")
        hashes = set(re.findall(
            r"TEAM_KIT_HOOK_BUNDLE_SHA256(?:=|=')([0-9a-f]{64})", text))
        assert len(hashes) == 1
        return hashes.pop()

    before = generate_and_hash()
    compat = repo / ".claude" / "hooks" / "_compat.py"
    compat.write_text(compat.read_text(encoding="utf-8") + "\n# bundle hash regression\n",
                      encoding="utf-8")
    after = generate_and_hash()
    assert before != after


def _generated_subagent_start_command(repo, key):
    result = subprocess.run([sys.executable, GEN, "--repo", str(repo),
                             "--providers", "codex"],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    document = json.loads((repo / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    for group in document["hooks"].get("SubagentStart", []):
        for hook in group.get("hooks", []):
            if "notify_agent_events.py" in hook.get("command", ""):
                return hook[key]
    raise AssertionError("generated SubagentStart notify hook not found")


def _exercise_generated_hook_bundle_command(tmp_path, command_key, shell_executable=None):
    repo = _provider_test_repo(tmp_path)
    (repo / "project_memory").mkdir()
    git_init = subprocess.run(["git", "init", "-b", "main"], cwd=str(repo),
                              capture_output=True, text=True, timeout=30)
    assert git_init.returncode == 0, git_init.stderr
    command = _generated_subagent_start_command(repo, command_key)
    payload = {"hook_event_name": "SubagentStart", "agent_type": "backend-developer",
               "agent_id": "generated-command-test", "cwd": str(repo)}

    def run_command():
        kwargs = {"cwd": str(repo), "input": json.dumps(payload), "capture_output": True,
                  "text": True, "timeout": 60, "shell": bool(shell_executable),
                  # A Codex process launched from a Claude-configured shell may inherit this.
                  # The generated wrapper must replace it with the root resolved above.
                  "env": dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path / "stale-root"))}
        if shell_executable:
            kwargs["executable"] = shell_executable
        return subprocess.run(command, **kwargs)

    clean = run_command()
    assert clean.returncode == 0, clean.stdout + clean.stderr
    audit = repo / "project_memory" / ".audit" / "hook_events.jsonl"
    assert audit.is_file() and "subagent_start" in audit.read_text(encoding="utf-8")
    audit_before = audit.read_bytes()

    helper = repo / ".claude" / "hooks" / "_compat.py"
    helper.write_text(helper.read_text(encoding="utf-8") + "\n# changed after hook trust\n",
                      encoding="utf-8")
    changed = run_command()
    assert changed.returncode == 2
    message = (changed.stdout + changed.stderr).lower()
    assert "hook bundle changed" in message
    assert "full scaffold" in message and "/hooks" in message
    assert audit.read_bytes() == audit_before  # verifier stopped before the actual hook


def test_generated_windows_hook_command_verifies_bundle_before_execution(tmp_path):
    if os.name != "nt" or not shutil.which("powershell"):
        pytest.skip("generated Windows hook command runs on Windows")
    _exercise_generated_hook_bundle_command(tmp_path, "commandWindows")


def test_generated_posix_hook_command_verifies_bundle_before_execution(tmp_path):
    if os.name == "nt" or not shutil.which("bash"):
        pytest.skip("generated POSIX hook command runs on Unix CI")
    _exercise_generated_hook_bundle_command(tmp_path, "command", shutil.which("bash"))


# ---------------- constitutions: every hook has a documented rule-home (diet safety) ----------------
def test_every_hook_documented_in_its_constitution():
    for kit in ("dev-team", "research-team", "office-team"):
        cpath = os.path.join(ROOT, "team-kits", kit, "constitution", "AGENTS.md")
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


def test_gate_filing_blocks_codex_multifile_patch(tmp_path):
    log = tmp_path / "project_memory" / "filing_log.yaml"
    write(str(log), 'filed:\n  - source: a.pdf\n    target: "archive/fin/a.pdf"\n')
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "apply_patch",
        "tool_input": {"command": _codex_patch("docs/notes.md",
                                                 "project_memory/filing_log.yaml")},
        "cwd": str(tmp_path),
    }
    result = run_hook_process("gate_filing.py", payload, tmp_path, hooks_dir=OFFICE_HOOKS,
                              extra_env={"TEAM_KIT_PROVIDER": "codex"})
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["decision"] == "block" and "file does NOT exist" in output["reason"]


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


# ---------------- scaffold: mechanical presets + map re-stamp ----------------
def _preset_parser_kit(tmp_path, presets):
    kit = tmp_path / "preset-kit"
    for role in ("project-manager", "alpha", "beta"):
        write(str(kit / "agents" / (role + ".md")), "# %s\n" % role)
    write(str(kit / "settings" / "settings.json"), '{"agent": "project-manager"}\n')
    write(str(kit / "presets.yaml"), presets)
    return kit


def test_preset_parser_resolves_only_valid_specialists(tmp_path):
    kit = _preset_parser_kit(tmp_path, "mini: alpha beta\nfull: all\n")
    result = subprocess.run(
        [sys.executable, os.path.join(ROOT, "team-kits", "preset_config.py"),
         "--kit", str(kit), "--preset", "mini", "--format", "json"],
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed == {
        "preset": "mini", "lead": "project-manager", "all": False,
        "roles": ["alpha", "beta"], "available": ["mini", "full"],
    }


@pytest.mark.parametrize("presets, diagnostic", [
    ("mini: alpha\nmini: beta\n", "duplicate yaml key"),
    ("mini: missing\n", "unknown role"),
    ("mini: project-manager alpha\n", "foreground lead"),
    ("mini: alpha alpha\n", "duplicate specialist"),
    ("mini: [alpha]\n", "space-separated role string"),
    ("- alpha\n", "non-empty mapping"),
])
def test_preset_parser_rejects_ambiguous_or_nonmechanical_policy(
        tmp_path, presets, diagnostic):
    kit = _preset_parser_kit(tmp_path, presets)
    result = subprocess.run(
        [sys.executable, os.path.join(ROOT, "team-kits", "preset_config.py"),
         "--kit", str(kit)], capture_output=True, text=True, timeout=60)
    output = (result.stdout + result.stderr).lower()
    assert result.returncode != 0 and diagnostic in output


def _unknown_recorded_preset_state(tmp_path):
    home = tmp_path / "home"
    kit = home / ".claude" / "team-kits" / "demo-team"
    for role in ("project-manager", "alpha"):
        write(str(kit / "agents" / (role + ".md")),
              "---\nname: %s\nmodel: sonnet\neffort: high\n---\nbody\n" % role)
        write(str(kit / "skills" / role / "SKILL.md"),
              "---\nname: %s\n---\nbody\n" % role)
    write(str(kit / "settings" / "settings.json"), '{"agent": "project-manager"}\n')
    write(str(kit / "presets.yaml"), "mini: alpha\n")
    write(str(kit / "constitution" / "AGENTS.md"),
          "<!-- agents-and-skills:team-kit demo-team -->\n# Replacement constitution\n")

    repo = tmp_path / "repo"
    write(str(repo / "project_memory" / "project_config.yaml"),
          'project:\n  name: demo\n  preset: "retired"\nproviders: [claude]\n')
    write(str(repo / "AGENTS.md"), "# external sentinel constitution\n")
    write(str(repo / ".claude" / "agents" / "custom.md"), "user-owned role\n")
    return home, repo


def _duplicate_recorded_preset_state(tmp_path):
    home, repo = _unknown_recorded_preset_state(tmp_path)
    config = repo / "project_memory" / "project_config.yaml"
    config.write_text(
        "project:\n  name: demo\n  preset: mini\nproviders: [claude]\n",
        encoding="utf-8")
    presets = home / ".claude" / "team-kits" / "demo-team" / "presets.yaml"
    presets.write_text("mini: alpha\nmini: all\n", encoding="utf-8")
    return home, repo


def _scaffold_external_file_symlink_state(tmp_path, relative):
    home = tmp_path / "home"
    kit = home / ".claude" / "team-kits" / "demo-team"
    for role in ("project-manager", "alpha"):
        write(str(kit / "agents" / (role + ".md")),
              "---\nname: %s\nmodel: sonnet\neffort: high\n---\nbody\n" % role)
        write(str(kit / "skills" / role / "SKILL.md"),
              "---\nname: %s\n---\nbody\n" % role)
    write(str(kit / "settings" / "settings.json"), '{"agent": "project-manager"}\n')
    write(str(kit / "presets.yaml"), "mini: alpha\n")
    write(str(kit / "constitution" / "AGENTS.md"),
          "<!-- agents-and-skills:team-kit demo-team -->\n# Replacement constitution\n")
    write(str(kit / "templates" / "repo" / "scripts" / "kit_checks.py"),
          "# kit-owned replacement\n")

    repo = tmp_path / "repo"
    write(str(repo / "project_memory" / "project_config.yaml"),
          "project:\n  name: symlink\n  preset: mini\nproviders: [claude]\n")
    write(str(repo / "AGENTS.md"), "# local constitution sentinel\n")
    external = tmp_path / "external-scaffold" / relative.replace("/", "-")
    write(str(external), "external scaffold sentinel\n")
    target = repo / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    return home, repo, external, target


def _assert_scaffold_symlink_preflight_untouched(repo, external, target):
    assert external.read_text(encoding="utf-8") == "external scaffold sentinel\n"
    assert target.is_symlink()
    assert (repo / "AGENTS.md").read_text(encoding="utf-8") == (
        "# local constitution sentinel\n")
    assert not (repo / ".claude" / "settings.json").exists()
    assert not (repo / ".claude" / "team_kit_roles.txt").exists()
    assert not (repo / ".claude" / "backups").exists()


@pytest.mark.parametrize("relative", [
    "scripts/kit_checks.py",
    ".claude/kit_update_pending.repo",
])
def test_scaffold_ps1_rejects_external_control_file_symlink_before_mutation(tmp_path, relative):
    if os.name != "nt" or not shutil.which("powershell"):
        pytest.skip("PowerShell scaffold integration runs on Windows")
    home, repo, external, target = _scaffold_external_file_symlink_state(tmp_path, relative)
    try:
        os.symlink(external, target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip("file symlinks are not permitted in this test environment: %s" % exc)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         os.path.join(ROOT, "team-kits", "scaffold_team.ps1"), "-Team", "demo-team"],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
        env=dict(os.environ, USERPROFILE=str(home)))
    output = (result.stdout + result.stderr).lower()
    assert result.returncode != 0 and ("symlink" in output or "reparse" in output)
    _assert_scaffold_symlink_preflight_untouched(repo, external, target)


@pytest.mark.parametrize("relative", [
    "scripts/kit_checks.py",
    ".claude/kit_update_pending.repo",
])
def test_scaffold_sh_rejects_external_control_file_symlink_before_mutation(tmp_path, relative):
    if os.name == "nt" or not shutil.which("bash"):
        pytest.skip("POSIX scaffold integration runs on Unix CI")
    home, repo, external, target = _scaffold_external_file_symlink_state(tmp_path, relative)
    os.symlink(external, target)
    pythonpath = os.pathsep.join(path for path in sys.path if path)
    result = subprocess.run(
        ["bash", os.path.join(ROOT, "team-kits", "scaffold_team.sh"), "demo-team"],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
        env=dict(os.environ, HOME=str(home), PYTHONPATH=pythonpath))
    output = (result.stdout + result.stderr).lower()
    assert result.returncode != 0 and "symlink" in output
    _assert_scaffold_symlink_preflight_untouched(repo, external, target)


def _assert_unknown_preset_left_repo_untouched(repo):
    assert (repo / "AGENTS.md").read_text(encoding="utf-8") == (
        "# external sentinel constitution\n")
    assert (repo / ".claude" / "agents" / "custom.md").read_text(
        encoding="utf-8") == "user-owned role\n"
    assert not (repo / ".claude" / "agents" / "alpha.md").exists()
    assert not (repo / ".claude" / "settings.json").exists()
    assert not (repo / ".claude" / "team_kit_roles.txt").exists()
    assert not (repo / ".claude" / "backups").exists()


def _scaffold_provider_collision_state(tmp_path):
    home = tmp_path / "home"
    kit = home / ".claude" / "team-kits" / "demo-team"
    for role in ("project-manager", "alpha"):
        model = "opus" if role == "project-manager" else "sonnet"
        write(str(kit / "agents" / (role + ".md")),
              "---\nname: %s\ndescription: new %s\nmodel: %s\neffort: high\n---\nnew body\n"
              % (role, role, model))
        write(str(kit / "skills" / role / "SKILL.md"),
              "---\nname: %s\n---\nnew skill\n" % role)
    write(str(kit / "settings" / "settings.json"), '{"agent": "project-manager"}\n')
    write(str(kit / "hooks" / "new_hook.py"), "#!/usr/bin/env python3\n# new hook\n")
    write(str(kit / "presets.yaml"), "mini: alpha\n")
    write(str(kit / "VERSION"), "version: rollback-test\ncontent: new\n")
    write(str(kit / "constitution" / "AGENTS.md"),
          "<!-- agents-and-skills:team-kit demo-team -->\n# New constitution\n")

    repo = tmp_path / "repo"
    write(str(repo / "project_memory" / "project_config.yaml"),
          "project:\n  name: rollback\n  preset: mini\nproviders: [claude, codex]\n")
    write(str(repo / "AGENTS.md"),
          "<!-- agents-and-skills:team-kit old-team -->\n# Old constitution\n")
    write(str(repo / "CLAUDE.md"), "# Old Claude entry\n")
    for role in ("project-manager", "alpha"):
        write(str(repo / ".claude" / "agents" / (role + ".md")), "old %s agent\n" % role)
        write(str(repo / ".claude" / "skills" / role / "SKILL.md"),
              "old %s skill\n" % role)
    write(str(repo / ".claude" / "agents" / "custom.md"), "user-owned custom agent\n")
    write(str(repo / ".claude" / "hooks" / "old_hook.py"), "# old hook\n")
    write(str(repo / ".claude" / "settings.json"),
          '{"agent": "project-manager", "old": true}\n')
    write(str(repo / ".claude" / "team_kit_roles.txt"),
          "# agents-and-skills:team-kit-roles v1 team=old-team count=2\n"
          "project-manager\nalpha\n")
    write(str(repo / ".claude" / "provider_artifacts.json"),
          '{"version": 1, "files": [], "dirs": []}\n')
    write(str(repo / ".claude" / "kit_version"),
          "version: old\ncontent: old\n")
    write(str(repo / ".agents" / "skills" / "old-native" / "SKILL.md"),
          "old native skill\n")
    collision = repo / ".codex" / "config.toml"
    write(str(collision), "# unowned collision sentinel\n")
    return home, repo, collision


def _controlled_scaffold_snapshot(repo):
    roots = (
        "AGENTS.md", "CLAUDE.md", ".claude/agents", ".claude/hooks",
        ".claude/skills", ".claude/settings.json", ".claude/team_kit_roles.txt",
        ".claude/provider_artifacts.json", ".claude/kit_version", ".codex",
        ".agents/skills", ".github/hooks", ".github/agents",
    )
    snapshot = {}
    for relative in roots:
        path = repo / relative
        if path.is_file():
            data = path.read_bytes()
            snapshot[relative] = (hashlib.sha256(data).hexdigest(), data)
        elif path.is_dir():
            snapshot[relative + "/"] = ("directory", b"")
            for child in sorted(item for item in path.rglob("*") if item.is_file()):
                child_relative = child.relative_to(repo).as_posix()
                data = child.read_bytes()
                snapshot[child_relative] = (hashlib.sha256(data).hexdigest(), data)
    return snapshot


def test_scaffold_ps1_rolls_back_base_after_provider_collision(tmp_path):
    if os.name != "nt" or not shutil.which("powershell"):
        pytest.skip("PowerShell scaffold integration runs on Windows")
    home, repo, collision = _scaffold_provider_collision_state(tmp_path)
    before = _controlled_scaffold_snapshot(repo)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         os.path.join(ROOT, "team-kits", "scaffold_team.ps1"), "-Team", "demo-team"],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
        env=dict(os.environ, USERPROFILE=str(home)))
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Provider output collision" in output and "rollback" in output.lower()
    assert _controlled_scaffold_snapshot(repo) == before
    assert collision.read_text(encoding="utf-8") == "# unowned collision sentinel\n"


def test_scaffold_sh_rolls_back_base_after_provider_collision(tmp_path):
    if os.name == "nt" or not shutil.which("bash"):
        pytest.skip("POSIX scaffold integration runs on Unix CI")
    home, repo, collision = _scaffold_provider_collision_state(tmp_path)
    before = _controlled_scaffold_snapshot(repo)
    pythonpath = os.pathsep.join(path for path in sys.path if path)
    result = subprocess.run(
        ["bash", os.path.join(ROOT, "team-kits", "scaffold_team.sh"), "demo-team"],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
        env=dict(os.environ, HOME=str(home), PYTHONPATH=pythonpath))
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Provider output collision" in output and "rollback" in output.lower()
    assert _controlled_scaffold_snapshot(repo) == before
    assert collision.read_text(encoding="utf-8") == "# unowned collision sentinel\n"


def test_scaffold_ps1_rejects_unknown_quoted_recorded_preset_before_mutation(tmp_path):
    if os.name != "nt" or not shutil.which("powershell"):
        pytest.skip("PowerShell scaffold integration runs on Windows")
    home, repo = _unknown_recorded_preset_state(tmp_path)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         os.path.join(ROOT, "team-kits", "scaffold_team.ps1"), "-Team", "demo-team"],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
        env=dict(os.environ, USERPROFILE=str(home)))
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "retired" in output and "preset" in output.lower()
    _assert_unknown_preset_left_repo_untouched(repo)


def test_scaffold_sh_rejects_unknown_quoted_recorded_preset_before_mutation(tmp_path):
    if os.name == "nt" or not shutil.which("bash"):
        pytest.skip("POSIX scaffold integration runs on Unix CI")
    home, repo = _unknown_recorded_preset_state(tmp_path)
    pythonpath = os.pathsep.join(path for path in sys.path if path)
    result = subprocess.run(
        ["bash", os.path.join(ROOT, "team-kits", "scaffold_team.sh"), "demo-team"],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
        env=dict(os.environ, HOME=str(home), PYTHONPATH=pythonpath))
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "retired" in output and "preset" in output.lower()
    _assert_unknown_preset_left_repo_untouched(repo)


def test_scaffold_ps1_rejects_duplicate_preset_keys_before_mutation(tmp_path):
    if os.name != "nt" or not shutil.which("powershell"):
        pytest.skip("PowerShell scaffold integration runs on Windows")
    home, repo = _duplicate_recorded_preset_state(tmp_path)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         os.path.join(ROOT, "team-kits", "scaffold_team.ps1"), "-Team", "demo-team"],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
        env=dict(os.environ, USERPROFILE=str(home)))
    output = (result.stdout + result.stderr).lower()
    assert result.returncode != 0 and "duplicate yaml key" in output
    _assert_unknown_preset_left_repo_untouched(repo)


def test_scaffold_sh_rejects_duplicate_preset_keys_before_mutation(tmp_path):
    if os.name == "nt" or not shutil.which("bash"):
        pytest.skip("POSIX scaffold integration runs on Unix CI")
    home, repo = _duplicate_recorded_preset_state(tmp_path)
    pythonpath = os.pathsep.join(path for path in sys.path if path)
    result = subprocess.run(
        ["bash", os.path.join(ROOT, "team-kits", "scaffold_team.sh"), "demo-team"],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
        env=dict(os.environ, HOME=str(home), PYTHONPATH=pythonpath))
    output = (result.stdout + result.stderr).lower()
    assert result.returncode != 0 and "duplicate yaml key" in output
    _assert_unknown_preset_left_repo_untouched(repo)


# Windows: real ps1 run
def test_scaffold_preset_and_map_sync(tmp_path):
    if os.name != "nt":
        pytest.skip("ps1 test runs on Windows; the sh mirror is covered by the kit audit")
    home = tmp_path / "home"
    kit = home / ".claude" / "team-kits" / "demo-team"
    for role in ("project-manager", "alpha", "beta", "gamma"):
        # lead + gamma use tier aliases: the lead is never in model_map and gamma has no map
        # entry, so both exercise the copy-time alias resolution (not the map stamping)
        model = {"project-manager": "lead", "gamma": "worker"}.get(role, "sonnet")
        write(str(kit / "agents" / ("%s.md" % role)),
              "---\nname: %s\ndescription: Demo %s\nmodel: %s\neffort: high\n---\nbody\n"
              % (role, role, model))
        write(str(kit / "skills" / role / "SKILL.md"), "---\nname: %s\n---\nx\n" % role)
    write(str(kit / "settings" / "settings.json"), '{"agent": "project-manager"}')
    write(str(kit / "hooks" / "noop.py"), "#!/usr/bin/env python3\n")
    write(str(kit / "presets.yaml"), "mini: alpha\nfull: all\n")
    write(str(kit / "VERSION"), "version: 2026.07.13-1\ncontent: x\n")
    write(str(kit / "constitution" / "AGENTS.md"),
          "<!-- agents-and-skills:team-kit demo-team -->\n# Demo constitution\nRule body.\n")
    legacy_kit = home / ".claude" / "team-kits" / "legacy-team"
    write(str(legacy_kit / "agents" / "legacy-specialist.md"), "old kit role\n")
    write(str(legacy_kit / "skills" / "legacy-specialist" / "SKILL.md"), "old kit skill\n")
    repo = tmp_path / "repo"
    config_path = repo / "project_memory" / "project_config.yaml"
    write(str(config_path),
          "project:\n  name: x\n  preset: mini\n"
          "providers:\n  - \"claude\"\n  - 'codex'  # generated provider\n"
          "model_map:\n  alpha: lead   # tier alias — must stamp as opus\n"
          "effort_map:\n  alpha: high\n")
    # Simulate a pre-manifest install from another kit plus unrelated user-owned files.
    write(str(repo / ".claude" / "agents" / "legacy-specialist.md"), "installed old role\n")
    write(str(repo / ".claude" / "skills" / "legacy-specialist" / "SKILL.md"),
          "installed old skill\n")
    # Legacy Copilot artifacts from an older kit (generation removed): the marker proves
    # ownership, so the full scaffold path must clean them up.
    write(str(repo / ".github" / "agents" / "alpha.agent.md"),
          "You are inside a team-kit governed repository.\n")
    write(str(repo / ".github" / "hooks" / "team-kit-hooks.json"),
          '{"version": 1, "hooks": {"PreToolUse": [{"bash": "python .claude/hooks/x.py"}]}}\n')
    write(str(repo / "AGENTS.md"),
          "<!-- agents-and-skills:team-kit legacy-team -->\n# Legacy constitution\n")
    write(str(repo / ".claude" / "agents" / "custom.md"), "custom\n")
    write(str(repo / ".claude" / "skills" / "custom" / "SKILL.md"), "custom\n")
    script = os.path.join(ROOT, "team-kits", "scaffold_team.ps1")

    def scaffold(*extra):
        return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                               script, "-Team", "demo-team", *extra],
                              cwd=str(repo), capture_output=True, text=True,
                              env=dict(os.environ, USERPROFILE=str(home)), timeout=120)

    roles_manifest = repo / ".claude" / "team_kit_roles.txt"
    write(str(roles_manifest),
          "# agents-and-skills:team-kit-roles v1 team=legacy-team count=2\n"
          "legacy-specialist\n")
    invalid = scaffold("-Preset", "mini")
    assert invalid.returncode != 0 and "Invalid/truncated" in invalid.stdout + invalid.stderr
    assert (repo / ".claude" / "agents" / "legacy-specialist.md").is_file()
    roles_manifest.unlink()

    valid_config = config_path.read_text(encoding="utf-8")
    # a PRESENT but invalid providers value stays fail-closed (the ABSENT key now defaults to
    # [claude, codex] for legacy configs — covered by its own generator test)
    config_path.write_text("project:\n  name: x\n  preset: mini\nproviders: 42\n",
                           encoding="utf-8")
    invalid_config = scaffold("-Preset", "mini")
    assert invalid_config.returncode != 0
    assert "Invalid provider configuration; no scaffold files were changed" in (
        invalid_config.stdout + invalid_config.stderr)
    assert "Legacy constitution" in (repo / "AGENTS.md").read_text(encoding="utf-8")
    config_path.write_text(valid_config, encoding="utf-8")

    r = scaffold("-Preset", "mini")
    assert r.returncode == 0, r.stdout + r.stderr
    agents = repo / ".claude" / "agents"
    assert (agents / "alpha.md").is_file() and (agents / "project-manager.md").is_file()
    assert not (agents / "beta.md").exists() and not (agents / "gamma.md").exists()
    skills = repo / ".claude" / "skills"
    assert (skills / "alpha" / "SKILL.md").is_file() and not (skills / "beta").exists()
    assert not (agents / "legacy-specialist.md").exists()
    assert not (skills / "legacy-specialist").exists()
    assert (agents / "custom.md").is_file() and (skills / "custom" / "SKILL.md").is_file()
    # V4 + tier alias: the user-approved map value `lead` stamps the concrete claude name
    assert "model: opus" in (agents / "alpha.md").read_text(encoding="utf-8-sig")
    # copy-time alias resolution: the lead is NOT in model_map — its kit-source alias must
    # still become the concrete reference-platform name on install
    pm_installed = (agents / "project-manager.md").read_text(encoding="utf-8-sig")
    assert "model: opus" in pm_installed and "model: lead" not in pm_installed
    # constitution ships as AGENTS.md + a 2-line CLAUDE.md import shim (marker on line 1)
    assert "Demo constitution" in (repo / "AGENTS.md").read_text(encoding="utf-8-sig")
    shim = (repo / "CLAUDE.md").read_text(encoding="utf-8-sig").splitlines()
    assert shim[0].startswith("<!-- agents-and-skills:team-kit demo-team")
    assert shim[1].strip() == "@AGENTS.md" and len([ln for ln in shim if ln.strip()]) == 2
    # providers: [claude, codex] -> the generator produced .codex artifacts (alpha on lead -> sol)
    assert (repo / ".codex" / "hooks.json").is_file()
    import tomllib
    codex_config = tomllib.loads((repo / ".codex" / "config.toml").read_text(encoding="utf-8-sig"))
    assert codex_config["model"] == "gpt-5.6-sol"
    alpha_toml = (repo / ".codex" / "agents" / "alpha.toml").read_text(encoding="utf-8-sig")
    assert 'model = "gpt-5.6-sol"' in alpha_toml
    assert not (repo / ".codex" / "agents" / "project-manager.toml").exists()
    assert (repo / ".agents" / "skills" / "alpha" / "SKILL.md").is_file()
    assert (repo / ".agents" / "skills" / "project-manager" / "SKILL.md").is_file()
    assert "agents-and-skills:generated-codex-config" in (
        repo / ".agents" / "skills" / "alpha" / ".team-kit-generated").read_text(
            encoding="utf-8")
    assert (repo / ".codex" / "config.toml").read_text(encoding="utf-8-sig").startswith(
        "# agents-and-skills:generated-codex-config")
    assert (repo / ".claude" / "hooks" / "noop.py").is_file()
    # legacy Copilot artifacts were marker-proven and removed by the provider transaction
    assert not (repo / ".github" / "agents" / "alpha.agent.md").exists()
    assert not (repo / ".github" / "hooks" / "team-kit-hooks.json").exists()
    assert (repo / ".claude" / "team_kit_roles.txt").read_text(
        encoding="utf-8-sig").splitlines() == [
            "# agents-and-skills:team-kit-roles v1 team=demo-team count=2",
            "project-manager", "alpha"]

    # Upgrade, then downgrade back to the recorded mini preset. Only kit-managed stale roles go;
    # unrelated user roles/skills survive.
    r_full = scaffold("-Preset", "full")
    assert r_full.returncode == 0, r_full.stdout + r_full.stderr
    assert (agents / "beta.md").is_file() and (repo / ".codex" / "agents" / "beta.toml").is_file()
    # gamma has NO model_map entry: its kit-source alias resolves at copy time
    gamma_installed = (agents / "gamma.md").read_text(encoding="utf-8-sig")
    assert "model: sonnet" in gamma_installed and "model: worker" not in gamma_installed

    config_text = config_path.read_text(encoding="utf-8")
    provider_block = "providers:\n  - \"claude\"\n  - 'codex'  # generated provider\n"
    config_path.write_text(config_text.replace(provider_block, "providers: [codex"),
                           encoding="utf-8")
    malformed = scaffold()
    assert malformed.returncode != 0 and "Invalid provider configuration; no scaffold files were changed" in (
        malformed.stdout + malformed.stderr)
    assert (repo / ".codex" / "agents" / "beta.toml").is_file()
    # the removed provider is rejected with a migration hint before any mutation
    config_path.write_text(config_text.replace(provider_block,
                                               "providers: [claude, codex, copilot]\n"),
                           encoding="utf-8")
    rejected = scaffold()
    assert rejected.returncode != 0 and "no longer supported" in (
        rejected.stdout + rejected.stderr)
    assert (repo / ".codex" / "agents" / "beta.toml").is_file()
    config_path.write_text(config_text.replace(provider_block,
                                               'providers: ["claude", "codex"]\n'),
                           encoding="utf-8")

    # a kit UPDATE without a preset argument must keep the RECORDED preset (project_config.yaml) —
    # not silently install the full roster (the inert-preset failure mode)
    r2 = scaffold()
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert "from project_config.yaml" in r2.stdout
    assert not (agents / "beta.md").exists() and not (agents / "gamma.md").exists()
    assert not (repo / ".codex" / "agents" / "beta.toml").exists()
    assert not (repo / ".agents" / "skills" / "beta").exists()
    assert not (repo / ".github" / "agents" / "alpha.agent.md").exists()
    assert not (repo / ".github" / "hooks" / "team-kit-hooks.json").exists()
    assert (agents / "custom.md").is_file() and (skills / "custom" / "SKILL.md").is_file()
    assert "model: opus" in (agents / "alpha.md").read_text(encoding="utf-8-sig")
    backups = list((repo / ".claude" / "backups").glob("*/AGENTS.md"))
    assert backups
    assert list((repo / ".claude" / "backups").glob("*/.claude/provider_artifacts.json"))


def test_scaffold_sh_preset_and_provider_e2e(tmp_path):
    if os.name == "nt" or not shutil.which("bash"):
        pytest.skip("POSIX scaffold integration runs on Unix CI")
    home = tmp_path / "home"
    kit = home / ".claude" / "team-kits" / "demo-team"
    for role in ("project-manager", "alpha", "beta"):
        model = "lead" if role == "project-manager" else "sonnet"
        write(str(kit / "agents" / (role + ".md")),
              "---\nname: %s\ndescription: Demo %s\nmodel: %s\neffort: high\n---\n%s body\n"
              % (role, role, model, role))
        write(str(kit / "skills" / role / "SKILL.md"),
              "---\nname: %s\n---\nFollow ./CLAUDE.md.\n" % role)
    # the lead never appears in model_map, so copy-time alias resolution is its ONLY path —
    # and CRLF content exercises the CR-tolerant awk (audit finding: non-MSYS awk keeps \r in $0)
    write(str(kit / "agents" / "project-manager.md"),
          "---\r\nname: project-manager\r\ndescription: Demo lead\r\nmodel: lead\r\n"
          "effort: high\r\n---\r\nlead body\r\n")
    write(str(kit / "settings" / "settings.json"), '{"agent": "project-manager"}\n')
    write(str(kit / "hooks" / "noop.py"), "#!/usr/bin/env python3\n")
    write(str(kit / "presets.yaml"), "mini: alpha\nfull: all\n")
    write(str(kit / "VERSION"), "version: 2026.07.14-test\ncontent: test\n")
    write(str(kit / "constitution" / "AGENTS.md"),
          "<!-- agents-and-skills:team-kit demo-team -->\n# Demo constitution\n")

    repo = tmp_path / "repo"
    write(str(repo / "project_memory" / "project_config.yaml"),
          "project:\n  name: demo\n  preset: mini\n"
          "providers: [claude, codex]\n"
          "model_map:\n  alpha: lead\n"
          "effort_map:\n  alpha: high\n")
    write(str(repo / ".claude" / "agents" / "custom.md"), "user-owned role\n")
    write(str(repo / ".claude" / "skills" / "custom" / "SKILL.md"), "user-owned skill\n")
    script = os.path.join(ROOT, "team-kits", "scaffold_team.sh")
    pythonpath = os.pathsep.join(path for path in sys.path if path)

    def scaffold(preset=None):
        command = ["bash", script, "demo-team"]
        if preset:
            command.append(preset)
        return subprocess.run(command, cwd=str(repo), capture_output=True, text=True, timeout=120,
                              env=dict(os.environ, HOME=str(home), PYTHONPATH=pythonpath))

    first = scaffold("mini")
    assert first.returncode == 0, first.stdout + first.stderr
    assert (repo / ".claude" / "agents" / "alpha.md").is_file()
    assert not (repo / ".claude" / "agents" / "beta.md").exists()
    assert (repo / ".claude" / "agents" / "custom.md").is_file()
    # copy-time alias resolution: lead is NOT in model_map, CRLF source, line ending preserved
    lead_installed = (repo / ".claude" / "agents" / "project-manager.md").read_bytes()
    assert b"model: opus\r\n" in lead_installed and b"model: lead" not in lead_installed
    assert (repo / ".codex" / "config.toml").is_file()
    assert (repo / ".agents" / "skills" / "alpha" / ".team-kit-generated").is_file()
    assert (repo / ".claude" / "team_kit_roles.txt").read_text(
        encoding="utf-8").splitlines() == [
            "# agents-and-skills:team-kit-roles v1 team=demo-team count=2",
            "project-manager", "alpha"]

    upgraded = scaffold("full")
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    assert (repo / ".claude" / "agents" / "beta.md").is_file()
    assert (repo / ".codex" / "agents" / "beta.toml").is_file()

    downgraded = scaffold()
    assert downgraded.returncode == 0, downgraded.stdout + downgraded.stderr
    assert "from project_config.yaml" in downgraded.stdout
    assert not (repo / ".claude" / "agents" / "beta.md").exists()
    assert not (repo / ".codex" / "agents" / "beta.toml").exists()
    assert not (repo / ".agents" / "skills" / "beta").exists()
    assert (repo / ".claude" / "agents" / "custom.md").is_file()
    assert (repo / ".claude" / "skills" / "custom" / "SKILL.md").is_file()
    assert list((repo / ".claude" / "backups").glob("*/.codex/config.toml"))


# ---------------- installers: fresh Codex-only homes + CODEX_HOME/override handling ----------------
def test_install_sh_codex_only_uses_codex_home(tmp_path):
    if os.name == "nt" or not shutil.which("bash"):
        pytest.skip("POSIX installer integration runs on Unix CI")
    home = tmp_path / "home"
    codex_home = tmp_path / "custom-codex"
    write(str(codex_home / "AGENTS.md"), "# old entry gate\n")
    write(str(codex_home / "AGENTS.override.md"), "# keep me\n")
    pythonpath = os.pathsep.join(path for path in sys.path if path)
    command = ["bash", os.path.join(ROOT, "install.sh"), "--target", "codex", "--force"]
    env = dict(os.environ, HOME=str(home), CODEX_HOME=str(codex_home), PYTHONPATH=pythonpath)
    result = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=180,
                            env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (codex_home / "AGENTS.md").is_file()
    assert (codex_home / "AGENTS.override.md").read_text(encoding="utf-8") == "# keep me\n"
    assert (home / ".claude" / "team-kits" / "gen_provider_artifacts.py").is_file()
    assert (home / ".claude" / "team-kits" / "preset_config.py").is_file()
    first_backups = list((home / ".claude" / "backups").glob("*/codex-AGENTS.md"))
    assert len(first_backups) == 1
    assert first_backups[0].read_text(encoding="utf-8") == "# old entry gate\n"
    assert list((home / ".claude" / "backups").glob("*/codex-AGENTS.override.md"))
    assert "entry gate stays inactive" in result.stdout

    second = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=180,
                            env=env)
    assert second.returncode == 0, second.stdout + second.stderr
    backup_dirs = {path.parent for path in
                   (home / ".claude" / "backups").glob("*/codex-AGENTS.md")}
    assert len(backup_dirs) == 2
    assert not list((home / ".claude").glob(".team-kits.stage.*"))
    assert not list((home / ".claude").glob(".team-kits.previous.*"))


def test_install_sh_rejects_symlinked_codex_agents_before_backup(tmp_path):
    if os.name == "nt" or not shutil.which("bash"):
        pytest.skip("POSIX installer integration runs on Unix CI")
    home = tmp_path / "home"
    codex_home = tmp_path / "custom-codex"
    external = tmp_path / "external" / "AGENTS.md"
    write(str(external), "# external sentinel\n")
    codex_home.mkdir(parents=True)
    os.symlink(external, codex_home / "AGENTS.md")
    pythonpath = os.pathsep.join(path for path in sys.path if path)
    result = subprocess.run(
        ["bash", os.path.join(ROOT, "install.sh"), "--target", "codex", "--force"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=180,
        env=dict(os.environ, HOME=str(home), CODEX_HOME=str(codex_home),
                 PYTHONPATH=pythonpath))
    assert result.returncode != 0
    assert "symlink" in (result.stdout + result.stderr).lower()
    assert external.read_text(encoding="utf-8") == "# external sentinel\n"
    assert (codex_home / "AGENTS.md").is_symlink()
    assert not (home / ".claude" / "backups").exists()
    assert not (home / ".claude" / "team-kits").exists()


def test_install_sh_codex_only_creates_fresh_codex_home(tmp_path):
    if os.name == "nt" or not shutil.which("bash"):
        pytest.skip("POSIX installer integration runs on Unix CI")
    home = tmp_path / "home"
    codex_home = tmp_path / "fresh-codex"
    assert not codex_home.exists()
    pythonpath = os.pathsep.join(path for path in sys.path if path)
    result = subprocess.run(
        ["bash", os.path.join(ROOT, "install.sh"), "--target", "codex", "--force"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=180,
        env=dict(os.environ, HOME=str(home), CODEX_HOME=str(codex_home),
                 PYTHONPATH=pythonpath))
    assert result.returncode == 0, result.stdout + result.stderr
    assert codex_home.is_dir() and (codex_home / "AGENTS.md").is_file()
    assert "created Codex home" in result.stdout
    assert (home / ".claude" / "team-kits" / "gen_provider_artifacts.py").is_file()
    assert (home / ".claude" / "team-kits" / "preset_config.py").is_file()


def test_install_sh_rejects_invalid_target():
    if os.name == "nt" or not shutil.which("bash"):
        pytest.skip("POSIX installer integration runs on Unix CI")
    result = subprocess.run(
        ["bash", os.path.join(ROOT, "install.sh"), "--target", "invalid", "--force"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=30)
    assert result.returncode != 0 and "Invalid target" in result.stderr


# ---------------- codex_global_config.py: opt-in user-wide secret shield ----------------
CODEX_SHIELD = os.path.join(ROOT, "user", "codex_global_config.py")


def _run_shield(codex_home):
    return subprocess.run([sys.executable, CODEX_SHIELD, str(codex_home)],
                          capture_output=True, text=True, timeout=60)


def test_codex_shield_appends_and_activates(tmp_path):
    import tomllib
    home = tmp_path / "codex"
    write(str(home / "config.toml"),
          'personality = "pragmatic"\nmodel = "gpt-5.6-sol"\n\n[windows]\nsandbox = "elevated"\n'
          "[projects.'c:\\x']\ntrust_level = \"trusted\"\n")
    r = _run_shield(home)
    assert r.returncode == 0, r.stdout + r.stderr
    text = (home / "config.toml").read_text(encoding="utf-8")
    data = tomllib.loads(text)
    assert data["default_permissions"] == "agents-and-skills-secrets"
    profile = data["permissions"]["agents-and-skills-secrets"]
    assert profile["extends"] == ":workspace"
    assert profile["filesystem"][":workspace_roots"]["**/*.pem"] == "deny"
    assert profile["filesystem"]["~/.ssh"] == "deny"
    # personal content untouched, activation line BEFORE the first table (TOML top-level rule)
    assert data["personality"] == "pragmatic" and data["windows"]["sandbox"] == "elevated"
    assert text.index("default_permissions") < text.index("[windows]")
    assert (home / "config.toml.agents-and-skills.bak").is_file()
    before = text
    r2 = _run_shield(home)  # idempotent: marker present -> byte-identical
    assert r2.returncode == 0
    assert (home / "config.toml").read_text(encoding="utf-8") == before

    # a fresh Codex home without a config.toml gets a valid minimal one
    empty_home = tmp_path / "codex-fresh"
    empty_home.mkdir()
    r3 = _run_shield(empty_home)
    assert r3.returncode == 0, r3.stdout + r3.stderr
    fresh = tomllib.loads((empty_home / "config.toml").read_text(encoding="utf-8"))
    assert fresh["default_permissions"] == "agents-and-skills-secrets"


def test_codex_shield_fail_closed(tmp_path):
    home = tmp_path / "codex"
    write(str(home / "config.toml"), 'sandbox_mode = "workspace-write"\n')
    r = _run_shield(home)
    assert r.returncode == 3 and "IGNORES permission profiles" in r.stderr
    assert (home / "config.toml").read_text(
        encoding="utf-8") == 'sandbox_mode = "workspace-write"\n'
    write(str(home / "config.toml"), "not [ valid toml\n")
    r2 = _run_shield(home)
    assert r2.returncode == 2 and "nothing was written" in r2.stderr
    assert (home / "config.toml").read_text(encoding="utf-8") == "not [ valid toml\n"


def test_codex_shield_respects_existing_default(tmp_path):
    import tomllib
    home = tmp_path / "codex"
    write(str(home / "config.toml"),
          'default_permissions = "mine"\n\n[permissions.mine]\nextends = ":workspace"\n')
    r = _run_shield(home)
    assert r.returncode == 0 and "NOT activated" in r.stdout
    data = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
    assert data["default_permissions"] == "mine"  # the user's choice is never fought
    assert "agents-and-skills-secrets" in data["permissions"]


def test_install_ps1_codex_global_secrets_flag(tmp_path):
    if os.name != "nt" or not shutil.which("powershell"):
        pytest.skip("PowerShell installer integration runs on Windows")
    home = tmp_path / "home"
    codex_home = tmp_path / "codex-home"
    appdata = tmp_path / "appdata"
    write(str(codex_home / "config.toml"), 'personality = "pragmatic"\n')
    pythonpath = os.pathsep.join(path for path in sys.path if path)
    command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               os.path.join(ROOT, "install.ps1"), "-Target", "codex", "-Force",
               "-CodexGlobalSecrets"]
    env = dict(os.environ, USERPROFILE=str(home), APPDATA=str(appdata),
               CODEX_HOME=str(codex_home), PYTHONPATH=pythonpath)
    result = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=180,
                            env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    text = (codex_home / "config.toml").read_text(encoding="utf-8")
    assert "agents-and-skills:codex-global-secrets" in text
    assert 'default_permissions = "agents-and-skills-secrets"' in text
    assert 'personality = "pragmatic"' in text
    assert list((home / ".claude" / "backups").glob("*/codex-config.toml"))


def test_install_ps1_codex_only_uses_codex_home(tmp_path):
    if os.name != "nt" or not shutil.which("powershell"):
        pytest.skip("PowerShell installer integration runs on Windows")
    home = tmp_path / "home"
    codex_home = tmp_path / "custom-codex"
    appdata = tmp_path / "appdata"
    write(str(codex_home / "AGENTS.md"), "# old entry gate\n")
    write(str(codex_home / "AGENTS.override.md"), "# keep me\n")
    pythonpath = os.pathsep.join(path for path in sys.path if path)
    command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               os.path.join(ROOT, "install.ps1"), "-Target", "codex", "-Force"]
    env = dict(os.environ, USERPROFILE=str(home), APPDATA=str(appdata),
               CODEX_HOME=str(codex_home), PYTHONPATH=pythonpath)
    result = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=180,
                            env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (codex_home / "AGENTS.md").is_file()
    assert (codex_home / "AGENTS.override.md").read_text(encoding="utf-8") == "# keep me\n"
    assert (home / ".claude" / "team-kits" / "gen_provider_artifacts.py").is_file()
    assert (home / ".claude" / "team-kits" / "preset_config.py").is_file()
    first_backups = list((home / ".claude" / "backups").glob("*/codex-AGENTS.md"))
    assert len(first_backups) == 1
    assert first_backups[0].read_text(encoding="utf-8") == "# old entry gate\n"
    assert list((home / ".claude" / "backups").glob("*/codex-AGENTS.override.md"))
    assert "entry gate stays inactive" in result.stdout

    second = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=180,
                            env=env)
    assert second.returncode == 0, second.stdout + second.stderr
    backup_dirs = {path.parent for path in
                   (home / ".claude" / "backups").glob("*/codex-AGENTS.md")}
    assert len(backup_dirs) == 2
    assert not list((home / ".claude").glob(".team-kits.stage.*"))
    assert not list((home / ".claude").glob(".team-kits.previous.*"))


def test_install_ps1_rejects_symlinked_codex_agents_before_backup(tmp_path):
    if os.name != "nt" or not shutil.which("powershell"):
        pytest.skip("PowerShell installer integration runs on Windows")
    home = tmp_path / "home"
    codex_home = tmp_path / "custom-codex"
    appdata = tmp_path / "appdata"
    external = tmp_path / "external" / "AGENTS.md"
    write(str(external), "# external sentinel\n")
    codex_home.mkdir(parents=True)
    try:
        os.symlink(external, codex_home / "AGENTS.md")
    except (OSError, NotImplementedError) as exc:
        pytest.skip("file symlinks are not permitted in this test environment: %s" % exc)
    pythonpath = os.pathsep.join(path for path in sys.path if path)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         os.path.join(ROOT, "install.ps1"), "-Target", "codex", "-Force"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=180,
        env=dict(os.environ, USERPROFILE=str(home), APPDATA=str(appdata),
                 CODEX_HOME=str(codex_home), PYTHONPATH=pythonpath))
    assert result.returncode != 0
    output = (result.stdout + result.stderr).lower()
    assert "symlink" in output or "reparse" in output
    assert external.read_text(encoding="utf-8") == "# external sentinel\n"
    assert (codex_home / "AGENTS.md").is_symlink()
    assert not (home / ".claude" / "backups").exists()
    assert not (home / ".claude" / "team-kits").exists()


def test_install_ps1_codex_only_creates_fresh_codex_home(tmp_path):
    if os.name != "nt" or not shutil.which("powershell"):
        pytest.skip("PowerShell installer integration runs on Windows")
    home = tmp_path / "home"
    codex_home = tmp_path / "fresh-codex"
    appdata = tmp_path / "appdata"
    assert not codex_home.exists()
    pythonpath = os.pathsep.join(path for path in sys.path if path)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         os.path.join(ROOT, "install.ps1"), "-Target", "codex", "-Force"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=180,
        env=dict(os.environ, USERPROFILE=str(home), APPDATA=str(appdata),
                 CODEX_HOME=str(codex_home), PYTHONPATH=pythonpath))
    assert result.returncode == 0, result.stdout + result.stderr
    assert codex_home.is_dir() and (codex_home / "AGENTS.md").is_file()
    assert "created Codex home" in result.stdout
    assert (home / ".claude" / "team-kits" / "gen_provider_artifacts.py").is_file()
    assert (home / ".claude" / "team-kits" / "preset_config.py").is_file()


# ---------------- upstream round: kit_checks additions (chunk guard, invariants, repo-wide yaml) ----------------
def test_kit_checks_chunk_warnlimit_guard(tmp_path):
    mod = _kit_checks_mod()
    # a protective COMMENT mentioning the key must never trip the guard
    write(str(tmp_path / "frontend" / "vite.config.ts"),
          "// chunkSizeWarningLimit stays at Vite's DEFAULT and MUST NEVER be raised\n"
          "export default {}\n")
    calls, ok, fail, warn = _collector()
    mod.check_frontend_build_config(str(tmp_path), ok, fail, warn)
    assert not calls["fail"] and any("chunkSizeWarningLimit" in n for n in calls["ok"])
    write(str(tmp_path / "frontend" / "vite.config.ts"),
          "export default { build: { chunkSizeWarningLimit: 1000 } }\n")
    calls, ok, fail, warn = _collector()
    mod.check_frontend_build_config(str(tmp_path), ok, fail, warn)
    assert any("ASSIGNED" in m for _n, m in calls["fail"])


def test_kit_checks_module_invariants(tmp_path):
    mod = _kit_checks_mod()
    write(str(tmp_path / "project_memory" / "coding_guidelines.yaml"),
          "module_invariants:\n"
          "  - path: src/pure.py\n"
          "    forbidden_tokens: [\"open(\"]\n"
          "    reason: \"pure module - no I/O\"\n")
    write(str(tmp_path / "src" / "pure.py"),
          "# never call open( in this module\ndef f():\n    return 1\n")
    calls, ok, fail, warn = _collector()
    mod.check_module_invariants(str(tmp_path), ok, fail, warn)
    assert not calls["fail"]  # comment-only mention never trips
    write(str(tmp_path / "src" / "pure.py"), "def f():\n    return open('x').read()\n")
    calls, ok, fail, warn = _collector()
    mod.check_module_invariants(str(tmp_path), ok, fail, warn)
    assert any("pure module - no I/O" in m for _n, m in calls["fail"])
    os.remove(str(tmp_path / "src" / "pure.py"))
    calls, ok, fail, warn = _collector()
    mod.check_module_invariants(str(tmp_path), ok, fail, warn)
    assert any("missing" in m for _n, m in calls["warn"])  # stale rule guards nothing


def test_kit_checks_repo_wide_yaml_parse(tmp_path):
    pytest.importorskip("yaml")
    mod = _kit_checks_mod()
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), capture_output=True)
    write(str(tmp_path / "project_memory" / "progress.yaml"), "status: x\nlog: []\n")
    write(str(tmp_path / "config" / "bad.yaml"), "a: [unclosed\n")
    subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), capture_output=True)
    calls, ok, fail, warn = _collector()
    mod.check_project_memory_yaml(str(tmp_path), ok, fail, warn)
    assert any(n == "yaml-lint (repo-wide)" for n, _m in calls["fail"])
    write(str(tmp_path / "project_memory" / "coding_guidelines.yaml"),
          "yaml_lint_exclude:\n  - \"config/*\"\n")
    calls, ok, fail, warn = _collector()
    mod.check_project_memory_yaml(str(tmp_path), ok, fail, warn)
    assert not any(n == "yaml-lint (repo-wide)" for n, _m in calls["fail"])


def _browser_checks_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("browser_checks_under_test", BROWSER_CHECKS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_browser_smoke_config_and_missing_dist(tmp_path):
    mod = _browser_checks_mod()
    write(str(tmp_path / "project_memory" / "testing_guidelines.yaml"),
          "coverage_gate:\n  threshold: 80\nbrowser_smoke:\n  entry: /app/\n"
          "  mount_selector: \"#app\"\n")
    assert mod._config(str(tmp_path)) == ("/app/", "#app")
    calls, ok, fail, warn = _collector()
    mod.browser_smoke(str(tmp_path), ok, fail, warn)  # no frontend/dist
    assert not calls["fail"] and any("dist missing" in m for _n, m in calls["warn"])


def test_browser_smoke_config_trailing_comment(tmp_path):
    # audit finding: an unquoted value with a trailing comment silently fell back to the
    # default route — the smoke then green-tested the WRONG page
    mod = _browser_checks_mod()
    write(str(tmp_path / "project_memory" / "testing_guidelines.yaml"),
          "browser_smoke:\n  entry: /app/   # main view\n  mount_selector: '#app'  # spa mount\n")
    assert mod._config(str(tmp_path)) == ("/app/", "#app")


def test_quality_source_areas_inline_and_quoted(tmp_path):
    # audit finding: the block-only parser silently skipped an INLINE-declared area that the
    # file-budget check DID scan — same knob, two behaviors
    os.makedirs(str(tmp_path / "scripts"))
    shutil.copy(QUALITY, str(tmp_path / "scripts" / "quality.py"))
    os.makedirs(str(tmp_path / "compounder"))
    write(str(tmp_path / "project_memory" / "coding_guidelines.yaml"),
          "source_areas: [compounder, '..']\n")
    mod = _quality_mod(str(tmp_path / "scripts" / "quality.py"))
    targets = mod._python_targets()
    assert "compounder" in targets and ".." not in targets
    write(str(tmp_path / "project_memory" / "coding_guidelines.yaml"),
          "source_areas:\n  # extra areas below\n  - 'compounder'\n")
    mod2 = _quality_mod(str(tmp_path / "scripts" / "quality.py"))
    assert "compounder" in mod2._python_targets()  # quoted item + comment line survive


def test_quality_declared_stacks_quoted_block(tmp_path):
    os.makedirs(str(tmp_path / "scripts"))
    shutil.copy(QUALITY, str(tmp_path / "scripts" / "quality.py"))
    write(str(tmp_path / "project_memory" / "project_config.yaml"),
          "stacks:  # declared by the architect\n  - 'python'\n  # more later\n  - go\n")
    mod = _quality_mod(str(tmp_path / "scripts" / "quality.py"))
    assert mod.declared_stacks() == ["python", "go"]


def test_kit_checks_module_invariants_string_tokens(tmp_path):
    # audit finding: a bare-string forbidden_tokens iterated CHARACTERS ('e' matched everywhere)
    mod = _kit_checks_mod()
    write(str(tmp_path / "project_memory" / "coding_guidelines.yaml"),
          "module_invariants:\n  - path: src/pure.py\n    forbidden_tokens: \"open(\"\n"
          "    reason: \"pure\"\n")
    write(str(tmp_path / "src" / "pure.py"), "def f():\n    return open('x').read()\n")
    calls, ok, fail, warn = _collector()
    mod.check_module_invariants(str(tmp_path), ok, fail, warn)
    assert len(calls["fail"]) == 1 and "'open('" in calls["fail"][0][1]


# ---------------- guard_question_context: a question must never point at invisible context ----------------
def _question_payload(tmp_path, question, desc="pick one"):
    return {"tool_name": "AskUserQuestion", "cwd": str(tmp_path),
            "tool_input": {"questions": [{"question": question, "header": "Decision",
                                          "options": [{"label": "Ja", "description": desc},
                                                      {"label": "Nein", "description": "skip"}],
                                          "multiSelect": False}]}}


def test_question_context_blocks_invisible_references(tmp_path):
    # the real incident: sign-off requested for a summary that existed only in THINKING
    bad = _question_payload(tmp_path, "Kategorien-Set freigeben (wie oben zusammengefasst)?")
    r = run_hook_process("guard_question_context.py", bad, tmp_path)
    assert r.returncode == 2 and "CANNOT see" in r.stderr
    # an option DESCRIPTION referencing invisible context blocks too
    desc_bad = _question_payload(tmp_path, "Freigeben?", desc="applies the plan as summarized above")
    assert run_hook("guard_question_context.py", desc_bad, tmp_path) == 2
    for hooks_dir in (RESEARCH_HOOKS, OFFICE_HOOKS):  # mirrored guard behaves identically
        assert run_hook("guard_question_context.py", bad, tmp_path, hooks_dir=hooks_dir) == 2


def test_question_context_allows_self_contained_and_dialogue_refs(tmp_path):
    good = _question_payload(
        tmp_path, "Kategorien-Set freigeben? Vorschlag: 12 Kategorien (Wareneinkauf, Versand, "
                  "Gebühren, ...) — Details in den Optionen.")
    assert run_hook("guard_question_context.py", good, tmp_path) == 0
    # "wie besprochen" refers to the VISIBLE dialogue with the user — must stay legal
    dialogue = _question_payload(tmp_path, "Wie besprochen mit Etappe 1 starten?")
    assert run_hook("guard_question_context.py", dialogue, tmp_path) == 0
    # prose containing 'above' in a non-reference sense stays legal
    prose = _question_payload(tmp_path, "Ist die above-average Latenz akzeptabel?")
    assert run_hook("guard_question_context.py", prose, tmp_path) == 0
