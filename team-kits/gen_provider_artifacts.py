#!/usr/bin/env python3
"""
gen_provider_artifacts.py — generate per-provider agent artifacts from the INSTALLED kit state.

Called by scaffold_team.(ps1|sh) AFTER agents/hooks/settings/constitution are installed, when the
project's project_config.yaml lists extra providers (`providers: [claude, codex]`). Single source
of truth = the installed `.claude/**` + the repo `AGENTS.md`; nothing generated here is ever
hand-maintained per provider (a real agent once hand-cloned the whole kit into `.codex/` — byte
copies that expected the wrong payloads and referenced paths that did not exist).

Generates:
  codex:    .codex/config.toml          (foreground lead model/instructions + permission profile)
            .codex/hooks.json           (supported registrations translated from Claude settings;
                                         hook trust is required)
            .codex/agents/<role>.toml   (one per installed specialist; NEVER the project lead)
            .agents/skills/<role>/      (native Codex skill discovery, including the lead skill)

Copilot generation was REMOVED (the kits target Claude Code + Codex only); the .github/* ownership
patterns below remain solely so stale Copilot artifacts from older scaffolds are still cleaned up.

Codex runs the SAME .claude/hooks/*.py scripts (hooks/_compat.py absorbs payload differences).
Codex hook commands resolve the Git root explicitly because the official hook contract runs
commands from the session cwd, which may be a repository subdirectory. Event contracts (verified
2026-07-14 against learn.chatgpt.com/docs/hooks + the openai/codex source): exit 2 + stderr blocks
PreToolUse/PostToolUse/UserPromptSubmit/SubagentStop; PostToolUse/SubagentStop/Stop additionally
consume a `decision: block` JSON (which _compat.stop() emits for the post/stop events, while
PreToolUse guards keep plain exit 2). Deterministic pipelines and permission profiles remain
defense in depth. Models are translated per tier via model_tiers.yaml (next to this script).
PyYAML is required for project-config parsing.
"""
import argparse
import atexit
import base64
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile


HERE = os.path.dirname(os.path.abspath(__file__))

# Claude matcher -> Codex matcher (Codex tool vocabulary: Bash, apply_patch, mcp__*).
# None = do not register on Codex (documented gap, see parity matrix in the README):
#   Agent|Task  — Codex exposes SubagentStart, but it cannot stop a spawn and does not carry the
#                 Claude work-order payload. Built-in Codex roles also remain available.
#   Notification — no such Codex event.
CODEX_MATCHER = {"Write": "apply_patch", "Edit|Write": "apply_patch",
                 "Bash|PowerShell": "Bash", "Agent|Task": None}
CODEX_EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "SubagentStart",
                "SubagentStop", "Stop")

ROLE_PREAMBLE = (
    "You are the specialist role described below inside a team-kit governed repository.\n"
    "First resolve <repo-root> with `git rev-parse --show-toplevel`; before git init, walk upward "
    "from the current directory until AGENTS.md and .claude/ are found. Interpret every relative "
    "repository path below against that root.\n"
    "MANDATORY, in this order: (1) follow <repo-root>/AGENTS.md — the team constitution — completely;\n"
    "(2) read <repo-root>/.agents/skills/%(role)s/SKILL.md BEFORE starting (your native Codex playbook);\n"
    "(3) validate that the work order names objective, read_first, output, and boundaries. If it "
    "does not, make no changes and return needs_input;\n"
    "(4) translate Claude-specific tool vocabulary in shared text to the available Codex-native "
    "equivalent while preserving the behavioral invariant;\n"
    "(5) end with your YAML output contract (`summary:` — see the skill), never prose-only.\n"
    "Reply to the user in German; ALL artifacts/code (names, comments, YAML keys) in English.\n"
)

LEAD_PREAMBLE = (
    "You are the FOREGROUND %(role)s for this team-kit governed repository. Never spawn another "
    "%(role)s. First resolve <repo-root> with `git rev-parse --show-toplevel`; before git init, walk "
    "upward until AGENTS.md and .claude/ are found, and resolve every relative repository path "
    "against that root. Follow <repo-root>/AGENTS.md completely and read "
    "<repo-root>/.agents/skills/%(role)s/SKILL.md before acting; it is your full lead playbook. "
    "Translate Claude-specific tool vocabulary in the "
    "shared source to the available Codex-native tool with the same behavioral invariant. "
    "Delegate specialist work only to exact roles installed in .codex/agents and wait for every "
    "required result before advancing the phase. Reply to the user in German; write all code and "
    "artifacts in English.\n"
)

GENERATED_MARKER = "agents-and-skills:generated-codex-config"
NATIVE_SKILL_MARKER = ".team-kit-generated"
MANIFEST_REL = os.path.join(".claude", "provider_artifacts.json")
# .github/* patterns are LEGACY-ONLY: never generated anymore, kept so removal/cleanup of old
# Copilot artifacts stays possible without widening what a tampered manifest may name.
_MANAGED_FILE_RX = (
    re.compile(r"^\.codex/agents/[A-Za-z0-9_-]+\.toml$"),
    re.compile(r"^\.github/agents/[A-Za-z0-9_-]+\.agent\.md$"),
)
_MANAGED_DIR_RX = re.compile(r"^\.agents/skills/[A-Za-z0-9_-]+$")
_MANAGED_FILES = {".codex/config.toml", ".codex/hooks.json",
                  ".github/hooks/team-kit-hooks.json"}


def read(path):
    with open(path, encoding="utf-8-sig") as fh:
        return fh.read()


def parse_frontmatter(text):
    """Parse agent frontmatter with the same YAML semantics as the source provider."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        import yaml  # type: ignore[import-untyped]
        meta = yaml.safe_load(parts[1]) or {}
    except Exception as exc:
        raise SystemExit("Invalid agent frontmatter; provider artifacts were left untouched: %s" % exc)
    if not isinstance(meta, dict):
        raise SystemExit("Agent frontmatter must be a mapping; provider artifacts were left untouched")
    return meta, parts[2].lstrip("\n")


def load_tiers():
    """Parse model_tiers.yaml with a stdlib mini-parser (file is kit-owned, flat two-level)."""
    tiers, aliases, section, prov = {}, {}, "", ""
    for raw in read(os.path.join(HERE, "model_tiers.yaml")).splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        m = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_.-]*):\s*(.*)$", line)
        if not m:
            continue
        indent, key, val = len(m.group(1)), m.group(2), m.group(3).strip().strip('"')
        if indent == 0:
            section, prov = key, ""
        elif section == "aliases" and val:
            aliases[key] = val
        elif section == "tiers" and indent == 2:
            prov = key
            tiers[prov] = {}
        elif section == "tiers" and prov and val:
            tiers[prov][key] = val
    return tiers, aliases


def tier_of(model, aliases):
    """Canonical claude-vocabulary tier of a model_map/frontmatter value."""
    return aliases.get(model, model)  # lead->opus etc.; opus/sonnet/haiku pass through


def provider_model(model, provider, tiers, aliases):
    canon = tier_of(model, aliases)             # opus | sonnet | haiku
    rev = {"opus": "lead", "sonnet": "worker", "haiku": "light"}
    tier = rev.get(canon)
    if not tier:
        return model  # unknown/explicit model id — pass through untouched
    return tiers.get(provider, {}).get(tier, model)


def providers_from_project_config(path):
    """Parse the YAML provider list without shell regexes that can misread valid YAML as empty."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        raise SystemExit("PyYAML is required to parse project_config.yaml")
    try:
        source = read(path)
        root = yaml.compose(source, Loader=yaml.SafeLoader)
        stack = [root] if root is not None else []
        visited, duplicates = set(), []
        while stack:
            node = stack.pop()
            if id(node) in visited:
                continue
            visited.add(id(node))
            if isinstance(node, yaml.MappingNode):
                seen = set()
                for key, value in node.value:
                    if isinstance(key, yaml.ScalarNode):
                        if key.value in seen:
                            duplicates.append("%s (line %d)" %
                                              (key.value, key.start_mark.line + 1))
                        seen.add(key.value)
                    stack.extend((key, value))
            elif isinstance(node, yaml.SequenceNode):
                stack.extend(node.value)
        if duplicates:
            raise ValueError("duplicate YAML key(s): %s" % ", ".join(duplicates))
        data = yaml.safe_load(source)
    except Exception as exc:
        raise SystemExit("Invalid project_config.yaml; provider artifacts were left untouched: %s"
                         % exc)
    if not isinstance(data, dict):
        raise SystemExit("Invalid project_config.yaml mapping; provider artifacts were left untouched")
    if "providers" not in data:
        # Legacy project_config predating the providers key: default to the full pair so a
        # mid-development CLI switch never needs a config edit first. A PRESENT key stays strict.
        print("  [note] project_config.yaml has no providers: line; defaulting to "
              "[claude, codex] - add the line to make it explicit")
        raw = ["claude", "codex"]
    elif data["providers"] is None:
        raise SystemExit("project_config.yaml providers must not be empty; use "
                         "[claude] or [claude, codex]; provider artifacts were left untouched")
    else:
        raw = data["providers"]
    if (not isinstance(raw, list) or not raw
            or any(not isinstance(item, str) for item in raw)):
        raise SystemExit("project_config.yaml providers must be a non-empty YAML list of provider "
                         "names; use [claude] to remove generated extra-provider artifacts; "
                         "provider artifacts were left untouched")
    normalized = [item.strip().lower() for item in raw]
    if "copilot" in normalized:
        raise SystemExit("Provider 'copilot' is no longer supported (the kits target Claude Code "
                         "and Codex only). Remove it from providers:; stale .github artifacts are "
                         "cleaned up on the next scaffold run. Provider artifacts were left "
                         "untouched")
    allowed = {"claude", "codex"}
    unknown = sorted({item for item in normalized if not item or item not in allowed})
    if unknown:
        raise SystemExit("Unknown project provider(s) %s; provider artifacts were left untouched"
                         % ", ".join(unknown))
    if len(set(normalized)) != len(normalized):
        raise SystemExit("project_config.yaml providers must not contain duplicates; provider "
                         "artifacts were left untouched")
    project = data.get("project")
    if not isinstance(project, dict):
        raise SystemExit("project_config.yaml project must be a mapping; provider artifacts were "
                         "left untouched")
    preset = project.get("preset")
    if (not isinstance(preset, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]+", preset)):
        raise SystemExit("project_config.yaml project.preset must be a non-empty simple preset "
                         "name; provider artifacts were left untouched")
    for map_name in ("model_map", "effort_map"):
        values = data.get(map_name, {})
        if not isinstance(values, dict):
            raise SystemExit("project_config.yaml %s must be a mapping; provider artifacts were "
                             "left untouched" % map_name)
        # This map is stamped into Claude frontmatter and Codex TOML, so accept only the shared
        # effort vocabulary documented by the kits rather than a provider-only value such as ultra.
        allowed_efforts = {"low", "medium", "high", "xhigh", "max"}
        portable_models = {"lead", "worker", "light", "opus", "sonnet", "haiku"}
        if any(not isinstance(role, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", role)
               or not isinstance(value, str)
               or (map_name == "model_map" and value not in portable_models)
               or (map_name == "effort_map" and value not in allowed_efforts)
               for role, value in values.items()):
            raise SystemExit("project_config.yaml %s contains an invalid role/value; provider "
                             "artifacts were left untouched" % map_name)
    return [item for item in normalized if item == "codex"]


def hook_entries(settings, event):
    for group in settings.get("hooks", {}).get(event, []) or []:
        matcher = group.get("matcher", "")
        for h in group.get("hooks", []) or []:
            if h.get("type") == "command" and h.get("command"):
                yield matcher, h


def agent_hook_entries(path, role):
    """Read Claude agent-frontmatter hooks so Codex retains role-scoped enforcement."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        raise SystemExit("PyYAML is required to translate role-scoped agent hooks")
    source = read(path)
    parts = source.split("---", 2)
    if len(parts) < 3 or parts[0].strip():
        return []
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except Exception as exc:
        raise SystemExit("Invalid agent frontmatter in %s: %s" % (path, exc))
    found = []
    for event, groups in (meta.get("hooks", {}) or {}).items():
        if event not in CODEX_EVENTS or not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            matcher = str(group.get("matcher", ""))
            for hook in group.get("hooks", []) or []:
                if (isinstance(hook, dict) and hook.get("type") == "command"
                        and hook.get("command")):
                    found.append((event, matcher, hook, role))
    return found


def rel_command(command):
    """Remove Claude's project-dir token for providers that do not define it."""
    return command.replace("${CLAUDE_PROJECT_DIR}/", "").replace("${CLAUDE_PROJECT_DIR}\\", "")


def hook_bundle_hash(repo):
    """Hash every installed hook dependency so Codex trust changes when executable code changes."""
    root = os.path.join(repo, ".claude", "hooks")
    digest = hashlib.sha256()
    if not os.path.isdir(root):
        raise SystemExit("Missing .claude/hooks; Codex hook trust cannot be bound to the bundle")
    assert_tree_no_reparse(repo, ".claude/hooks")
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(directory for directory in dirs if directory != "__pycache__")
        for filename in sorted(files):
            if filename.endswith((".pyc", ".pyo")):
                continue
            path = os.path.join(current, filename)
            relative = os.path.relpath(path, root).replace("\\", "/")
            digest.update(relative.encode("utf-8") + b"\0")
            with open(path, "rb") as fh:
                digest.update(fh.read())
            digest.update(b"\0")
    return digest.hexdigest()


def hook_bundle_verifier_b64():
    """Return trusted inline verifier code; its bytes live in the hook definition Codex hashes."""
    code = r'''import hashlib
import os
import sys

root, expected = sys.argv[1], sys.argv[2]
digest = hashlib.sha256()
try:
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(item for item in dirs if item != "__pycache__")
        for filename in sorted(files):
            if filename.endswith((".pyc", ".pyo")):
                continue
            path = os.path.join(current, filename)
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            digest.update(relative.encode("utf-8") + b"\0")
            with open(path, "rb") as handle:
                digest.update(handle.read())
            digest.update(b"\0")
except Exception as exc:
    sys.stderr.write("Team-kit hook bundle verification failed: %s\n" % exc)
    sys.exit(2)
if digest.hexdigest() != expected:
    sys.stderr.write("Team-kit hook bundle changed after scaffold/trust; rerun the full scaffold and review /hooks.\n")
    sys.exit(2)
'''
    return base64.b64encode(code.encode("utf-8")).decode("ascii")


def codex_hook_commands(command, agent_types=(), bundle_hash=""):
    """Return repo-root-stable POSIX and Windows hook commands.

    Codex runs hook commands from the session cwd. The official docs explicitly warn that this
    may be a nested directory, so a plain `.claude/hooks/x.py` path is not safe. Git is the fast
    path; a parent walk keeps greenfield repositories working before `git init`.
    """
    relative = rel_command(command).replace("\\", "/")
    match = re.search(r"(?:^|[\"'])((?:\.claude|\.codex)/hooks/[^\"']+\.py)(?:[\"']|$)", relative)
    if not match:
        return relative, relative
    script = match.group(1)
    roles = ",".join(sorted(set(agent_types)))
    verifier = hook_bundle_verifier_b64()
    posix_env = ('CLAUDE_PROJECT_DIR="$root" TEAM_KIT_PROVIDER=codex '
                 'TEAM_KIT_HOOK_BUNDLE_SHA256=%s' % bundle_hash)
    windows_env = ("$env:TEAM_KIT_PROVIDER='codex'; "
                   "$env:TEAM_KIT_HOOK_BUNDLE_SHA256='%s'; " % bundle_hash)
    if roles:
        posix_env += " TEAM_KIT_AGENT_TYPES=%s" % roles
        windows_env += "$env:TEAM_KIT_AGENT_TYPES='%s'; " % roles
    posix = ('root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; '
             'while [ ! -f "$root/%(script)s" ] && [ "$root" != "/" ]; '
             'do root="$(dirname "$root")"; done; '
             'py="$(command -v python3 || command -v python)"; [ -n "$py" ] || exit 1; '
             '"$py" -c "import base64;exec(base64.b64decode(\'%(verify)s\'))" '
             '"$root/.claude/hooks" "%(hash)s" || exit $?; '
             '%(env)s "$py" "$root/%(script)s"' % {
                 "script": script, "env": posix_env, "verify": verifier,
                 "hash": bundle_hash})
    windows = ('powershell -NoProfile -Command "%(env)s'
                '$root = git rev-parse --show-toplevel 2>$null; '
                'if (-not $root) { $root = (Get-Location).Path }; '
                'while (-not (Test-Path -LiteralPath (Join-Path $root \'%(script)s\'))) { '
                '$parent = Split-Path -Parent $root; '
                'if (-not $parent -or $parent -eq $root) { break }; $root = $parent }; '
                '$env:CLAUDE_PROJECT_DIR = $root; '
                '$py = Get-Command python -ErrorAction SilentlyContinue; '
                'if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }; '
                'if (-not $py) { throw \'Python 3 is required for team-kit hooks\' }; '
                '$verify = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(\'%(verify)s\')); '
                '$verify | & $py.Source - (Join-Path $root \'.claude/hooks\') \'%(hash)s\'; '
                'if ($LASTEXITCODE -ne 0) { exit 2 }; '
                '& $py.Source (Join-Path $root \'%(script)s\')"'
               % {"script": script, "env": windows_env, "verify": verifier,
                  "hash": bundle_hash})
    return posix, windows


def gen_codex_hooks(settings, role_hooks=(), repo=None):
    registrations = {}
    global_keys = set()
    for event in CODEX_EVENTS:
        for matcher, hook in hook_entries(settings, event):
            cm = CODEX_MATCHER.get(matcher, matcher) if matcher else ""
            if matcher and cm is None:
                continue
            key = (event, cm, hook["command"], hook.get("timeout"))
            registrations[key] = {"hook": hook, "roles": None}
            global_keys.add(key)
    # Codex has a native, non-blocking lifecycle event. Reuse the shared audit hook so spawn-side
    # accounting exists even though Claude's Agent|Task pre-spawn guard has no Codex equivalent.
    for _matcher, hook in hook_entries(settings, "SubagentStop"):
        if "notify_agent_events.py" in hook["command"]:
            key = ("SubagentStart", "", hook["command"], hook.get("timeout"))
            registrations[key] = {"hook": hook, "roles": None}
            global_keys.add(key)
    for event, matcher, hook, role in role_hooks:
        cm = CODEX_MATCHER.get(matcher, matcher) if matcher else ""
        if matcher and cm is None:
            continue
        key = (event, cm, hook["command"], hook.get("timeout"))
        if key in global_keys:
            continue
        item = registrations.setdefault(key, {"hook": hook, "roles": set()})
        item["roles"].add(role)

    out = {}
    grouped = {}
    bundle_hash = hook_bundle_hash(repo) if repo else "unbound"
    for (event, matcher, _command, _timeout), item in registrations.items():
        hook = item["hook"]
        roles = item["roles"] or ()
        command, command_windows = codex_hook_commands(hook["command"], roles, bundle_hash)
        entry = {"type": "command", "command": command,
                 "commandWindows": command_windows}
        if hook.get("timeout"):
            entry["timeout"] = hook["timeout"]
        grouped.setdefault((event, matcher), []).append(entry)
    for event in CODEX_EVENTS:
        event_groups = [(matcher, hooks) for (registered_event, matcher), hooks
                        in grouped.items() if registered_event == event]
        if event_groups:
            out[event] = [({"matcher": matcher, "hooks": hooks} if matcher else {"hooks": hooks})
                          for matcher, hooks in event_groups]
    return {"hooks": out}


def toml_str(s):
    return '"""\n' + s.replace('\\', '\\\\').replace('"""', '\\"\\"\\"') + '\n"""'


# The sanctioned divergence valve: a Codex-only capability the Claude-native source format cannot
# express goes into a namespaced `codex:` frontmatter mapping (Claude ignores unknown keys) and is
# merged into the generated TOML here — no schema migration, no second hand-maintained source.
# Identity/instruction keys stay generator-owned; scalars only (lists/tables = future schema step).
CODEX_OVERLAY_RESERVED = ("name", "description", "developer_instructions")


def codex_overlay(meta, role):
    overlay = meta.get("codex")
    if overlay is None:
        return {}
    if not isinstance(overlay, dict):
        raise SystemExit("Agent %s: codex: overlay must be a mapping; provider artifacts were "
                         "left untouched" % role)
    for key, value in overlay.items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise SystemExit("Agent %s: invalid codex: overlay key %r; provider artifacts were "
                             "left untouched" % (role, key))
        if key in CODEX_OVERLAY_RESERVED:
            raise SystemExit("Agent %s: codex: overlay must not override '%s'; provider artifacts "
                             "were left untouched" % (role, key))
        if key in ("model", "model_reasoning_effort") and not isinstance(value, str):
            raise SystemExit("Agent %s: codex: overlay '%s' must be a string; provider artifacts "
                             "were left untouched" % (role, key))
        if not isinstance(value, (str, int, float, bool)):
            raise SystemExit("Agent %s: codex: overlay values must be scalars; provider artifacts "
                             "were left untouched" % role)
    return dict(overlay)


def toml_scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value)


def codex_text(text):
    """Apply only unambiguous path translations to generated Codex copies."""
    translated = (text.replace("./CLAUDE.md", "./AGENTS.md")
                  .replace(".claude/skills/", ".agents/skills/"))
    return re.sub(
        r"Consult\s+your agent memory\s+before,\s*update it after\.",
        "Consult checked-in project_memory and your native skill before acting; record durable "
        "project facts only in the designated project_memory files.",
        translated,
        flags=re.IGNORECASE,
    )


def claude_read_denies(settings):
    """Translate Claude Read(...) deny entries to Codex permission-profile paths."""
    paths = []
    for item in (settings.get("permissions", {}).get("deny", []) or []):
        match = re.fullmatch(r"Read\((.+)\)", str(item).strip())
        if not match:
            continue
        path = match.group(1).replace("\\", "/")
        if path.startswith("./"):
            path = path[2:]
        if path and path not in paths:
            paths.append(path)
    return paths


def gen_codex_config(settings, lead, tiers, aliases):
    """Generate the trusted-project Codex equivalent of the Claude session-agent settings."""
    role, meta, body = lead
    if meta.get("codex") is not None:
        raise SystemExit("Agent %s: codex: overlay is specialist-only — the lead's Codex surface "
                         "is .codex/config.toml (generated from settings + frontmatter); provider "
                         "artifacts were left untouched" % role)
    model = provider_model(meta.get("model", settings.get("model", "opus")),
                           "codex", tiers, aliases)
    effort = meta.get("effort", "high")
    instructions = (LEAD_PREAMBLE % {"role": role}) + "\n" + codex_text(body)
    lines = [
        "# %s" % GENERATED_MARKER,
        "# Generated by team-kits/gen_provider_artifacts.py; scaffold backs this file up.",
        'model = "%s"' % model,
        'model_reasoning_effort = "%s"' % effort,
        'plan_mode_reasoning_effort = "%s"' % effort,
        'approval_policy = "on-request"',
        'default_permissions = "team-kit"',
        "project_doc_max_bytes = 65536",
        "developer_instructions = " + toml_str(instructions),
        "",
        "[features]",
        "hooks = true",
        "multi_agent = true",
        "memories = false",
        "",
        "[memories]",
        "generate_memories = false",
        "use_memories = false",
        "",
        "[agents]",
        "max_threads = 6",
        "max_depth = 1",
        "",
        "[permissions.team-kit.filesystem]",
        "glob_scan_max_depth = 8",
        '\":minimal\" = \"read\"',
        "",
        '[permissions.team-kit.filesystem.\":workspace_roots\"]',
        '"." = "write"',
        '"AGENTS.md" = "read"',
        '"AGENTS.override.md" = "read"',
        '"CLAUDE.md" = "read"',
        '".claude/agents" = "read"',
        '".claude/agent-memory" = "read"',
        '".claude/backups" = "read"',
        '".claude/hooks" = "read"',
        '".claude/skills" = "read"',
        '".claude/settings.json" = "read"',
        '".claude/settings.local.json" = "read"',
        '".claude/kit_version" = "read"',
        '".claude/provider_artifacts.json" = "read"',
        '".claude/team_kit_roles.txt" = "read"',
        '".codex" = "read"',
        '".agents/skills" = "read"',
        '".github/hooks" = "read"',
        '".github/agents" = "read"',
    ]
    for path in claude_read_denies(settings):
        lines.append("%s = \"deny\"" % json.dumps(path))
    lines += [
        "",
        "[permissions.team-kit.network]",
        "enabled = false",
    ]
    return "\n".join(lines) + "\n"


def gen_codex_agent(role, meta, body, tiers, aliases):
    overlay = codex_overlay(meta, role)
    lines = ['name = "%s"' % role,
             'description = "%s"' % str(meta.get("description", role)).replace('"', "'")]
    if "model" in overlay:
        model = overlay.pop("model")
    else:
        model = provider_model(meta.get("model", "sonnet"), "codex", tiers, aliases)
    lines.append('model = "%s"' % model)
    if "model_reasoning_effort" in overlay:
        effort = overlay.pop("model_reasoning_effort")
    else:
        effort = meta.get("effort", "high")
    lines.append('model_reasoning_effort = "%s"' % effort)
    for key in sorted(overlay):
        lines.append("%s = %s" % (key, toml_scalar(overlay[key])))
    instructions = (ROLE_PREAMBLE % {"role": role}) + "\n" + codex_text(body)
    lines.append("developer_instructions = " + toml_str(instructions))
    return "\n".join(lines) + "\n"


def safe_repo_path(repo, relative):
    path = os.path.abspath(os.path.join(repo, relative))
    if os.path.commonpath((repo, path)) != os.path.abspath(repo):
        raise ValueError("generated path escapes repository: %s" % relative)
    return path


def is_link_or_reparse(path):
    """Detect POSIX symlinks and Windows junction/reparse points without following them."""
    if os.path.islink(path):
        return True
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is not None and isjunction(path):
        return True
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def assert_path_no_reparse(repo, relative, include_leaf=True):
    """Reject any existing link/reparse component before a controlled read or mutation."""
    path = safe_repo_path(repo, relative)
    parts = os.path.relpath(path, os.path.abspath(repo)).replace("\\", "/").split("/")
    if not include_leaf:
        parts = parts[:-1]
    current = os.path.abspath(repo)
    for component in parts:
        if component in ("", "."):
            continue
        current = os.path.join(current, component)
        if os.path.lexists(current) and is_link_or_reparse(current):
            raise SystemExit(
                "Refusing symlink/reparse path %s; provider artifacts were left untouched"
                % str(relative).replace("\\", "/"))
    return path


def assert_tree_no_reparse(repo, relative):
    """Reject links anywhere in a kit-owned source tree before copying or hashing it."""
    root = assert_path_no_reparse(repo, relative)
    if not os.path.lexists(root) or not os.path.isdir(root):
        return
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            entries = list(os.scandir(current))
        except OSError as exc:
            raise SystemExit("Cannot inspect controlled path %s; provider artifacts were left "
                             "untouched: %s" % (relative, exc))
        for entry in entries:
            if is_link_or_reparse(entry.path):
                shown = os.path.relpath(entry.path, repo).replace("\\", "/")
                raise SystemExit("Refusing symlink/reparse path %s; provider artifacts were left "
                                 "untouched" % shown)
            if entry.is_dir(follow_symlinks=False):
                pending.append(entry.path)


def is_managed_output(relative, directory=False):
    """Accept only paths the generator itself can emit, even if its manifest was tampered with."""
    normalized = str(relative).replace("\\", "/").strip("/")
    if directory:
        return bool(_MANAGED_DIR_RX.fullmatch(normalized))
    return normalized in _MANAGED_FILES or any(rx.fullmatch(normalized)
                                               for rx in _MANAGED_FILE_RX)


def load_provider_manifest(repo):
    """Load and strictly validate ownership before any provider artifact is changed."""
    path = assert_path_no_reparse(repo, MANIFEST_REL)
    if not os.path.isfile(path):
        return None
    try:
        data = json.loads(read(path))
    except Exception as exc:
        raise SystemExit("Invalid %s; provider artifacts were left untouched: %s"
                         % (MANIFEST_REL.replace("\\", "/"), exc))
    valid_shape = (isinstance(data, dict) and data.get("version") == 1
                   and isinstance(data.get("files"), list)
                   and isinstance(data.get("dirs"), list))
    if not valid_shape:
        raise SystemExit("Invalid %s schema; provider artifacts were left untouched"
                         % MANIFEST_REL.replace("\\", "/"))
    invalid_files = [item for item in data["files"]
                     if not isinstance(item, str) or not is_managed_output(item)]
    invalid_dirs = [item for item in data["dirs"]
                    if not isinstance(item, str) or not is_managed_output(item, directory=True)]
    if invalid_files or invalid_dirs:
        raise SystemExit("Invalid ownership path(s) in %s; provider artifacts were left untouched"
                         % MANIFEST_REL.replace("\\", "/"))
    return data


def legacy_owned_outputs(repo):
    """Return pre-manifest outputs whose stable markers prove generator ownership."""
    role_marker = "team-kit governed repository"
    files, dirs = set(), set()
    for relative in (".codex/config.toml", ".codex/agents", ".codex/hooks.json",
                     ".github/agents", ".github/hooks/team-kit-hooks.json",
                     ".agents/skills"):
        assert_path_no_reparse(repo, relative)
    config = os.path.join(repo, ".codex", "config.toml")
    if os.path.isfile(config):
        try:
            generated_config = GENERATED_MARKER in read(config)
        except (OSError, UnicodeError):
            generated_config = False
        if generated_config:
            files.add(".codex/config.toml")
    for relative_dir, suffix in ((".codex/agents", ".toml"),
                                 (".github/agents", ".agent.md")):
        directory = os.path.join(repo, relative_dir)
        if not os.path.isdir(directory):
            continue
        for filename in os.listdir(directory):
            path = os.path.join(directory, filename)
            if filename.endswith(suffix) and os.path.isfile(path):
                try:
                    generated = role_marker in read(path)
                except (OSError, UnicodeError):
                    generated = False
                if generated:
                    relative = "%s/%s" % (relative_dir, filename)
                    files.add(relative)
    for relative in (".codex/hooks.json", ".github/hooks/team-kit-hooks.json"):
        path = os.path.join(repo, relative)
        if not os.path.isfile(path):
            continue
        try:
            generated = ".claude/hooks/" in read(path).replace("\\", "/")
        except (OSError, UnicodeError):
            generated = False
        if generated:
            files.add(relative)
    native_skills = os.path.join(repo, ".agents", "skills")
    if os.path.isdir(native_skills):
        for role in os.listdir(native_skills):
            marker = os.path.join(native_skills, role, NATIVE_SKILL_MARKER)
            if os.path.isfile(marker):
                try:
                    generated = GENERATED_MARKER in read(marker)
                except (OSError, UnicodeError):
                    generated = False
                if generated:
                    dirs.add(".agents/skills/%s" % role)
    return files, dirs


def remove_owned_outputs(repo, files, dirs):
    """Remove a validated, generator-owned output set."""
    for relative in sorted(files):
        path = assert_path_no_reparse(repo, relative)
        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path)
    for relative in sorted(dirs, key=lambda item: item.count("/"), reverse=True):
        path = assert_path_no_reparse(repo, relative)
        if os.path.islink(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)


def validate_output_collisions(repo, files, dirs, owned_files, owned_dirs):
    """Fail before mutation if generation would replace a path not proven to be ours."""
    collisions = []
    for relative in sorted(set(files) | set(dirs) | set(owned_files) | set(owned_dirs)):
        assert_path_no_reparse(repo, relative)
    for relative in sorted(set(owned_files)):
        path = safe_repo_path(repo, relative)
        if os.path.lexists(path) and not os.path.isfile(path):
            collisions.append(relative + " (owned file has wrong type)")
    for relative in sorted(set(owned_dirs)):
        path = safe_repo_path(repo, relative)
        if os.path.lexists(path) and not os.path.isdir(path):
            collisions.append(relative + " (owned directory has wrong type)")
    for relative in sorted(set(files) - set(owned_files)):
        if os.path.lexists(safe_repo_path(repo, relative)):
            collisions.append(relative)
    for relative in sorted(set(dirs) - set(owned_dirs)):
        if os.path.lexists(safe_repo_path(repo, relative)):
            collisions.append(relative)
    if collisions:
        raise SystemExit(
            "Provider output collision at %s; files are user-owned or ownership is ambiguous. "
            "Move them aside or restore a valid %s; provider artifacts were left untouched"
            % (", ".join(collisions), MANIFEST_REL.replace("\\", "/")))


def snapshot_outputs(repo, snapshot, files, dirs):
    """Copy the owned set before replacement so an I/O failure can restore it."""
    for relative in sorted(files):
        source = assert_path_no_reparse(repo, relative)
        if not os.path.lexists(source):
            continue
        target = safe_repo_path(snapshot, relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.islink(source):
            os.symlink(os.readlink(source), target)
        elif os.path.isfile(source):
            shutil.copy2(source, target)
    for relative in sorted(dirs):
        source = assert_path_no_reparse(repo, relative)
        if not os.path.lexists(source):
            continue
        target = safe_repo_path(snapshot, relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.islink(source):
            os.symlink(os.readlink(source), target, target_is_directory=True)
        elif os.path.isdir(source):
            shutil.copytree(source, target, symlinks=True)


def restore_snapshot(repo, snapshot, files, dirs):
    """Restore a previously copied ownership snapshot, replacing partial new output."""
    remove_owned_outputs(repo, files, dirs)
    for relative in sorted(dirs):
        source = safe_repo_path(snapshot, relative)
        if not os.path.lexists(source):
            continue
        target = assert_path_no_reparse(repo, relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.islink(source):
            os.symlink(os.readlink(source), target, target_is_directory=True)
        else:
            shutil.copytree(source, target, symlinks=True)
    for relative in sorted(files):
        source = safe_repo_path(snapshot, relative)
        if not os.path.lexists(source):
            continue
        target = assert_path_no_reparse(repo, relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.islink(source):
            os.symlink(os.readlink(source), target)
        else:
            shutil.copy2(source, target)


def install_staged_outputs(stage, repo, files, dirs):
    """Atomically replace individual staged paths (same filesystem) after validation."""
    for relative in sorted(dirs):
        source = safe_repo_path(stage, relative)
        target = assert_path_no_reparse(repo, relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        os.replace(source, target)
    for relative in sorted(files):
        source = safe_repo_path(stage, relative)
        target = assert_path_no_reparse(repo, relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        os.replace(source, target)


def prune_empty(path, stop):
    stop = os.path.abspath(stop)
    path = os.path.abspath(path)
    while path != stop and os.path.commonpath((stop, path)) == stop:
        try:
            os.rmdir(path)
        except OSError:
            break
        path = os.path.dirname(path)


def write_manifest(repo, files, dirs):
    path = assert_path_no_reparse(repo, MANIFEST_REL)
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    data = {"version": 1, "files": sorted(files), "dirs": sorted(dirs)}
    fd, temporary = tempfile.mkstemp(prefix=".provider_artifacts.", suffix=".tmp",
                                     dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def managed_role_names(repo):
    manifest = os.path.join(repo, ".claude", "team_kit_roles.txt")
    if not os.path.isfile(manifest):
        return None
    lines = read(manifest).splitlines()
    header = lines[0].strip() if lines else ""
    match = re.fullmatch(
        r"# agents-and-skills:team-kit-roles v1 team=[A-Za-z0-9_-]+ count=([0-9]+)",
        header)
    roles = [line.strip() for line in lines[1:] if line.strip()]
    if (not match or int(match.group(1)) < 1 or len(roles) != int(match.group(1))
            or len(set(roles)) != len(roles)
            or any(not re.fullmatch(r"[A-Za-z0-9_-]+", role) for role in roles)):
        raise SystemExit("Invalid/truncated .claude/team_kit_roles.txt; provider artifacts untouched")
    return set(roles)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    provider_source = ap.add_mutually_exclusive_group(required=True)
    provider_source.add_argument("--providers", help="comma list; currently only: codex")
    provider_source.add_argument("--project-config",
                                 help="project_config.yaml whose providers list is authoritative")
    ap.add_argument("--check-config-only", action="store_true",
                    help="validate provider configuration and existing ownership without changes")
    ap.add_argument("--lead", default="project-manager",
                    help="lead role — carried by AGENTS.md, never generated as a spawnable agent")
    args = ap.parse_args()
    repo = os.path.realpath(os.path.abspath(args.repo))
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.lead):
        raise SystemExit("Lead role must match [A-Za-z0-9_-]+; provider artifacts were left untouched")
    if args.project_config:
        providers = providers_from_project_config(args.project_config)
    else:
        raw_providers = [p.strip().lower() for p in (args.providers or "").split(",")
                         if p.strip()]
        if "copilot" in raw_providers:
            raise SystemExit("Provider 'copilot' is no longer supported (the kits target Claude "
                             "Code and Codex only)")
        unknown = sorted({p for p in raw_providers if p != "codex"})
        if unknown:
            raise SystemExit("Unknown provider(s): %s" % ", ".join(unknown))
        providers = raw_providers
    for relative in ("AGENTS.override.md", ".claude/provider_artifacts.json"):
        assert_path_no_reparse(repo, relative)
    if "codex" in providers and os.path.isfile(os.path.join(repo, "AGENTS.override.md")):
        raise SystemExit(
            "Repository AGENTS.override.md takes precedence over the generated AGENTS.md team "
            "constitution. Merge/remove the override only after explicit user review; provider "
            "artifacts were left untouched")
    previous_manifest = load_provider_manifest(repo)
    if args.check_config_only:
        if previous_manifest is not None:
            validate_output_collisions(repo, set(), set(), set(previous_manifest["files"]),
                                       set(previous_manifest["dirs"]))
        return 0
    if not providers:
        if previous_manifest is None:
            owned_files, owned_dirs = legacy_owned_outputs(repo)
        else:
            owned_files = set(previous_manifest["files"])
            owned_dirs = set(previous_manifest["dirs"])
        validate_output_collisions(repo, set(), set(), owned_files, owned_dirs)
        transaction = tempfile.mkdtemp(prefix=".provider-transaction.", dir=repo)
        snapshot = os.path.join(transaction, "snapshot")
        os.makedirs(snapshot)
        snapshot_outputs(repo, snapshot, owned_files, owned_dirs)
        try:
            remove_owned_outputs(repo, owned_files, owned_dirs)
            write_manifest(repo, [], [])
        except Exception:
            restore_snapshot(repo, snapshot, owned_files, owned_dirs)
            raise
        finally:
            shutil.rmtree(transaction, ignore_errors=True)
        for parent in (os.path.join(repo, ".codex", "agents"), os.path.join(repo, ".codex"),
                       os.path.join(repo, ".agents", "skills"), os.path.join(repo, ".agents"),
                       os.path.join(repo, ".github", "agents"), os.path.join(repo, ".github", "hooks")):
            assert_path_no_reparse(repo, os.path.relpath(parent, repo))
            if os.path.isdir(parent):
                prune_empty(parent, repo)
        return 0

    for relative in (".claude/settings.json", ".claude/agents", ".claude/skills",
                     ".claude/hooks", ".claude/team_kit_roles.txt"):
        assert_tree_no_reparse(repo, relative)
    settings = json.loads(read(os.path.join(repo, ".claude", "settings.json")))
    tiers, aliases = load_tiers()
    agents_dir = os.path.join(repo, ".claude", "agents")
    selected = managed_role_names(repo)
    if selected is None:
        raise SystemExit("Missing .claude/team_kit_roles.txt; non-empty provider generation requires "
                         "a full scaffold so only manifest-owned roles can be translated")
    roles = []
    role_hooks = []
    if os.path.isdir(agents_dir):
        for fn in sorted(os.listdir(agents_dir)):
            if fn.endswith(".md") and fn[:-3] in selected:
                agent_path = os.path.join(agents_dir, fn)
                meta, body = parse_frontmatter(read(agent_path))
                role_name = fn[:-3]
                if meta.get("name") != role_name:
                    raise SystemExit("Agent frontmatter name/source mismatch for %s; provider "
                                     "artifacts were left untouched" % role_name)
                if meta.get("model") not in {"lead", "worker", "light", "opus", "sonnet", "haiku"}:
                    raise SystemExit("Agent %s uses a non-portable model tier; provider artifacts "
                                     "were left untouched" % role_name)
                if meta.get("effort") not in {"low", "medium", "high", "xhigh", "max"}:
                    raise SystemExit("Agent %s uses an unsupported shared effort; provider artifacts "
                                     "were left untouched" % role_name)
                if (not isinstance(meta.get("description"), str)
                        or not meta["description"].strip()):
                    raise SystemExit("Agent %s needs a non-empty string description; provider "
                                     "artifacts were left untouched" % role_name)
                # YAML folded/literal scalars commonly retain their final line break. It must not
                # leak into a TOML basic string.
                meta["description"] = meta["description"].strip()
                roles.append((fn[:-3], meta, body))
                role_hooks.extend(agent_hook_entries(agent_path, fn[:-3]))

    loaded_roles = {role for role, _meta, _body in roles}
    if selected is not None and loaded_roles != selected:
        missing = sorted(selected - loaded_roles)
        unexpected = sorted(loaded_roles - selected)
        raise SystemExit("Role manifest/source mismatch (missing: %s; unexpected: %s); provider "
                         "artifacts were left untouched" %
                         (", ".join(missing) or "none", ", ".join(unexpected) or "none"))
    missing_skills = [role for role in sorted(loaded_roles)
                      if not os.path.isfile(os.path.join(repo, ".claude", "skills", role,
                                                        "SKILL.md"))]
    if missing_skills:
        raise SystemExit("Missing required native skill source for role(s) %s; provider artifacts "
                         "were left untouched" % ", ".join(missing_skills))

    leads = [role for role in roles if role[0] == args.lead]
    if "codex" in providers and not leads:
        raise SystemExit("Codex generation requires installed lead agent %s" % args.lead)
    specialists = [role for role in roles if role[0] != args.lead]

    desired_files, desired_dirs = set(), set()
    if "codex" in providers:
        desired_files.update((".codex/config.toml", ".codex/hooks.json"))
        desired_files.update(".codex/agents/%s.toml" % role for role, _meta, _body in specialists)
        desired_dirs.update(
            ".agents/skills/%s" % role for role, _meta, _body in roles
            if os.path.isdir(os.path.join(repo, ".claude", "skills", role)))

    if previous_manifest is None:
        owned_files, owned_dirs = legacy_owned_outputs(repo)
    else:
        owned_files = set(previous_manifest["files"])
        owned_dirs = set(previous_manifest["dirs"])
    validate_output_collisions(repo, desired_files, desired_dirs, owned_files, owned_dirs)

    # Render and validate the complete replacement in a same-filesystem staging tree. The old
    # provider layer remains intact until every new file has been produced successfully.
    transaction = tempfile.mkdtemp(prefix=".provider-transaction.", dir=repo)
    atexit.register(shutil.rmtree, transaction, ignore_errors=True)
    stage_repo = os.path.join(transaction, "new")
    snapshot = os.path.join(transaction, "snapshot")
    os.makedirs(stage_repo)
    os.makedirs(snapshot)
    generated_files, generated_dirs = [], []

    if "codex" in providers:
        cdir = os.path.join(stage_repo, ".codex")
        os.makedirs(os.path.join(cdir, "agents"), exist_ok=True)
        config_rel = ".codex/config.toml"
        with open(os.path.join(stage_repo, config_rel), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(gen_codex_config(settings, leads[0], tiers, aliases))
        generated_files.append(config_rel)
        hooks_rel = ".codex/hooks.json"
        with open(os.path.join(cdir, "hooks.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(gen_codex_hooks(settings, role_hooks, repo), fh, indent=2)
            fh.write("\n")
        generated_files.append(hooks_rel)
        for role, meta, body in specialists:
            rel = ".codex/agents/%s.toml" % role
            with open(os.path.join(stage_repo, rel), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(gen_codex_agent(role, meta, body, tiers, aliases))
            generated_files.append(rel)
        for role, _meta, _body in roles:
            source = os.path.join(repo, ".claude", "skills", role)
            if not os.path.isdir(source):
                continue
            relative = ".agents/skills/%s" % role
            target = os.path.join(stage_repo, relative)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.isdir(target):
                shutil.rmtree(target)
            shutil.copytree(source, target)
            with open(os.path.join(target, NATIVE_SKILL_MARKER), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(GENERATED_MARKER + "\n")
            for root, _dirs, files in os.walk(target):
                for filename in files:
                    path = os.path.join(root, filename)
                    try:
                        original = read(path)
                        translated = codex_text(original)
                    except (OSError, UnicodeError):
                        continue
                    if translated != original:
                        with open(path, "w", encoding="utf-8", newline="\n") as fh:
                            fh.write(translated)
            generated_dirs.append(relative)

    if set(generated_files) != desired_files or set(generated_dirs) != desired_dirs:
        raise SystemExit("Internal provider staging mismatch; old provider artifacts were left untouched")
    snapshot_outputs(repo, snapshot, owned_files, owned_dirs)
    try:
        remove_owned_outputs(repo, owned_files, owned_dirs)
        install_staged_outputs(stage_repo, repo, generated_files, generated_dirs)
        write_manifest(repo, generated_files, generated_dirs)
    except Exception:
        remove_owned_outputs(repo, generated_files, generated_dirs)
        restore_snapshot(repo, snapshot, owned_files, owned_dirs)
        raise
    finally:
        shutil.rmtree(transaction, ignore_errors=True)
    if "codex" in providers:
        print("  [ok] codex artifacts: .codex/config.toml + hooks.json + %d specialist "
              "agent(s) + %d native skill(s) (trust the project, then run /hooks to trust changed "
              "hooks; current Codex builds block the generated Pre/Post guards, while deterministic "
              "pipeline gates remain defense in depth)"
              % (len(specialists), len(generated_dirs)))
    for parent in (os.path.join(repo, ".codex", "agents"), os.path.join(repo, ".codex"),
                   os.path.join(repo, ".agents", "skills"), os.path.join(repo, ".agents"),
                   os.path.join(repo, ".github", "agents"), os.path.join(repo, ".github", "hooks")):
        assert_path_no_reparse(repo, os.path.relpath(parent, repo))
        if os.path.isdir(parent):
            prune_empty(parent, repo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
