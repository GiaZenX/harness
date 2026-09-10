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
            .agents/skills/<name>/      (native Codex skill discovery -- every skill directory the
                                         project carries, role or not; see `native_skill_sources`)

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
import json
import os
import re
import shutil
import stat
import sys
import tempfile

# This script imports `kernel.hashing` out of the team-kit staging (see `kernel_hashing`) and runs
# during a scaffold — and it is the script that BINDS Codex trust to a bundle hash. Writing a
# `.pyc` into a hashed tree while computing that hash is the one thing it must not do. No harness
# process writes bytecode into a tree the harness hashes or installs from: see
# `kernel.hashing.BYTECODE_SUFFIXES`, and `tools/validate.py` for the repo-side statement of it.
sys.dont_write_bytecode = True


HERE = os.path.dirname(os.path.abspath(__file__))

# Claude matcher -> Codex matcher (Codex tool vocabulary: Bash, apply_patch, mcp__*).
# Absent from the table = do not register on Codex, and then only if `CODEX_UNSUPPORTED_TOOLS`
# declares it (documented gap, see parity matrix in the README). A TOOL is what this list is about;
# an EVENT Codex does not have (`Notification`) is a gap of a different kind and is declared by its
# absence from `CODEX_EVENTS`, which is where the reader has to look for it — it used to stand here
# among the tools, in the paragraph that says how a tool is declared, and no tool declaration
# covers it:
#   Agent|Task  — Codex exposes SubagentStart, but it cannot stop a spawn and does not carry the
#                 Claude work-order payload; upstream closed the request for that payload as
#                 "not planned" (openai/codex#32753, radar/2026-09-05-codex.md item 4), so the gap
#                 is durable rather than pending. Built-in Codex roles also remain available.
#   AskUserQuestion — Codex asks via request_user_input (root-only, different payload shape);
#                 guard_question_context cannot hook it, so the self-contained-question rule
#                 binds Codex PMs through the SKILL alone (audit: the fallthrough used to
#                 register the Claude tool name verbatim — a dead entry in .codex/hooks.json).
# Translated from the TOOL SET, not from the matcher string. The string table was a lookup over
# exact spellings with a verbatim fallthrough, and widening two Claude matchers from `Edit|Write`
# to `Edit|Write|MultiEdit|NotebookEdit` silently dropped `guard_pm_scope` — the lead's write-scope
# veto — and `guard_guidelines` off Codex entirely: the new spelling was not in the table, so it
# was emitted verbatim, and Codex knows no such matcher. That is the same "dead entry" the comment
# above already records, reached again through a change nobody expected to touch this file.
CODEX_TOOL_MATCHER = (
    (frozenset(("Edit", "Write", "MultiEdit", "NotebookEdit")), "apply_patch"),
    (frozenset(("Bash", "PowerShell")), "Bash"),
)
# Tools Codex has no equivalent for, DECLARED — the whole point of naming them is that dropping
# them is a decision somebody made and wrote down (the reasons are in the comment above), not the
# accident of a lookup that found nothing. `codex_matchers` refuses anything absent from both this
# set and the table above, so the difference between "deliberately not on Codex" and "nobody has
# translated this yet" is a message at generation time instead of a registration that never fires.
CODEX_UNSUPPORTED_TOOLS = frozenset(("Agent", "Task", "AskUserQuestion"))
# Codex's own tool vocabulary reaches a Claude matcher unchanged through this prefix: an MCP tool is
# called `mcp__<server>__<tool>` on both sides, so the name IS the translation.
MCP_TOOL_PREFIX = "mcp__"


def codex_matchers(matcher):
    """Every Codex matcher a TOOL matcher translates to — one per distinct Codex tool it names.

    ONLY FOR THE EVENTS WHOSE MATCHERS NAME TOOLS (`TOOL_MATCHED_EVENTS`); see that constant for
    what a matcher is on the other events and why asking this function about one is a category
    error rather than a lookup failure.

    A MATCHER NAMES A SET OF TOOLS, SO THE ANSWER IS A SET. The previous version returned the first
    table entry the set intersected, which meant a mixed matcher lost everything after it — and one
    is shipped: `gate_filing` is registered `Bash|PowerShell|Edit|Write|MultiEdit`, because the
    office kit's filing rule applies to a shell command that moves a document exactly as it applies
    to writing one. On Codex it arrived as `apply_patch` alone, so the shell half of that gate has
    been absent on that provider for as long as the kit has existed (measured 2026-07-27).

    THREE OUTCOMES PER TOOL, and the third is why this can raise. A tool the table knows becomes
    its Codex name; a tool Codex has no equivalent for (`CODEX_UNSUPPORTED_TOOLS`) contributes
    nothing, which is the DECLARED gap; anything else is refused, because the alternative has
    already shipped once — widening two Claude matchers to include `NotebookEdit` fell through a
    lookup, got emitted verbatim, and left the lead's write-scope veto registered under a matcher
    Codex does not know, i.e. never firing, in a file that reads as enforcement. A generator that
    stops with a name is the only version of that event anybody notices.

    An empty matcher (or `*`) is a registration for every call and translates to itself.
    """
    if not matcher or matcher == "*":
        return (matcher or "",)
    translated, unknown = [], []
    for tool in sorted({part for part in re.split(r"[|,]", matcher) if part}):
        if tool in CODEX_UNSUPPORTED_TOOLS:
            continue
        if tool.startswith(MCP_TOOL_PREFIX):
            name = tool
        else:
            name = next((codex for group, codex in CODEX_TOOL_MATCHER if tool in group), None)
        if name is None:
            unknown.append(tool)
        elif name not in translated:
            translated.append(name)
    if unknown:
        raise SystemExit(
            "Claude matcher %r names tool(s) with no Codex translation and no declared gap: %s. "
            "Add them to CODEX_TOOL_MATCHER (they have a Codex equivalent) or to "
            "CODEX_UNSUPPORTED_TOOLS (they have none) in gen_provider_artifacts.py; emitting the "
            "registration anyway would put a hook into .codex/hooks.json that can never fire. "
            "Provider artifacts were left untouched" % (matcher, ", ".join(unknown)))
    return tuple(sorted(translated))


CODEX_EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "SubagentStart",
                "SubagentStop", "Stop")
# A CODEX-ONLY EVENT HAS NO VEHICLE IN THE SOURCE FORMAT, and that is tolerated, not translated: a
# kit source registers hooks in Claude's `settings.json` vocabulary, and an event Claude Code does
# not have (`Interrupt`, Codex CLI 0.150.0 -- radar/2026-09-05-codex.md item 4) cannot be named
# there, so nothing here emits it and nothing here refuses a kit for not naming it. The `codex:`
# frontmatter overlay reaches per-agent TOML fields only, never a hook registration; the day a kit
# needs such an event is the neutral-source trip-wire of HARNESS_LOG 2026-07-14.

# WHAT A MATCHER SELECTS ON IS A PROPERTY OF THE EVENT, not of the string. The tool events match on
# TOOL NAMES; every other event matches in a vocabulary of its own, and the kits ship one:
# `Notification` is registered `agent_completed|agent_needs_input` in all three, which are
# notification kinds. `codex_matchers` refuses anything that is not a known tool, so handing it that
# matcher stops the generator with a message about an untranslatable TOOL — the honest answer to the
# wrong question.
#
# That this has never happened rests on `Notification` being absent from `CODEX_EVENTS`, i.e. on an
# unwritten agreement between two tuples, and Codex does have notification-shaped events. So the
# condition is stated where it belongs: the tool table is asked about tool matchers and nothing
# else. `test_every_registration_a_kit_writes_survives_the_codex_translation` translates every
# event EVERY kit registers — not only the ones that reach Codex today — so the shipped
# `Notification` matcher is a measured case whether or not it is ever added to `CODEX_EVENTS`.
#
# THE OTHER EVENTS' MATCHERS ARE NOT TRANSLATED, because the tool namespace is the only thing this
# generator knows to differ between the two providers: a notification kind or a session source is
# named by the shared event contract, not by the provider's tool vocabulary. Today every such
# registration in every kit is `""` or `*` (measured 2026-07-28), for which "carry it over" and
# "translate it" are the same answer anyway.
TOOL_MATCHED_EVENTS = frozenset(("PreToolUse", "PostToolUse", "PermissionDenied",
                                 "PostToolUseFailure"))


def codex_matchers_for(event, matcher):
    """The Codex matchers a Claude REGISTRATION translates to — the event decides the vocabulary."""
    if event in TOOL_MATCHED_EVENTS:
        return codex_matchers(matcher)
    return (matcher,)

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


# The platform whose model vocabulary model_tiers.yaml uses as the canonical one; every other
# provider's ids are looked up against its tier names. Named once because three readers below ask
# "is this the reference platform" and a fourth spelling of the word would be the drift.
REFERENCE_PROVIDER = "claude"


def tier_of(model, aliases):
    """Canonical claude-vocabulary rung of a model_map/frontmatter value."""
    return aliases.get(model, model)  # lead->opus etc.; a rung name passes through


# The one row of a provider block that is not a rung: the frontmatter key that provider reads its
# effort from. Named so `rungs` can leave it out by its own name instead of by a list of rung names.
EFFORT_FIELD_KEY = "effort_field"


def rungs(tiers, provider):
    """rung name -> model id for `provider`: its block minus the effort-field row."""
    return {key: value for key, value in tiers.get(provider, {}).items()
            if key != EFFORT_FIELD_KEY}


def provider_model(model, provider, tiers, aliases):
    """The model id `provider` runs for a model_map/frontmatter value -- or the value untouched.

    THE ROW IS THE RUNG, read off the table and not off a map kept here: an alias becomes its
    canonical rung (`tier_of`), the reference platform keeps the literal value, every other
    provider answers with its row for that rung. Until DEC-0076 a dict in this function said
    which row each canonical name meant and sent `fable` to the LEAD row, because the table had no
    top row to point at; the table now carries one per provider. A value that is no rung and no
    alias comes back unchanged, which is what `provider_neutral_model` and
    `tools/test_model_pins.the_table_can_place` read as "the table cannot place this".
    """
    canon = tier_of(model, aliases)
    if provider == REFERENCE_PROVIDER:
        return model  # claude keeps the literal value (incl. fable)
    return rungs(tiers, provider).get(canon, model)


def table_places(model, tiers, aliases):
    """Can the table turn this value into a rung EVERY provider it knows has a row for?

    The question the generator asks of an INSTALLED frontmatter value (already alias-resolved
    by the scaffold, so `opus`/`sonnet` are ordinary here) and the one `tools/test_model_pins`
    asks of a shipped pin. A retired rung (`light`, `haiku`, `luna`) is not a row anywhere and
    is refused with `unplaceable_pin_sentence` naming DEC-0076.
    """
    canon = tier_of(str(model), aliases)
    return bool(tiers) and all(canon in rungs(tiers, provider) for provider in tiers)


def unplaceable_pin_sentence(where, model, tiers, aliases):
    """The refusal for a pin no provider block has a row for -- one sentence, one decision."""
    top = [name for name in rungs(tiers, REFERENCE_PROVIDER) if name not in set(aliases.values())]
    return ("%s pins model %r, which team-kits/model_tiers.yaml does not place: the ladder has "
            "exactly three rungs per provider and no `light`/haiku row (DEC-0076). Pin an alias (%s)"
            "%s. Provider artifacts were left untouched"
            % (where, model, ", ".join(sorted(aliases)),
               (" or the top rung %s" % ", ".join(sorted(top))) if top else ""))


def provider_neutral_model(model, tiers=None, aliases=None):
    """May a KIT SOURCE carry this model value — does it still resolve on every provider?

    TWO WAYS TO QUALIFY, both read off `model_tiers.yaml` instead of listed. The value is a rung
    ALIAS (`aliases:`), or it is no alias TARGET AND `provider_model` still translates it for every
    other provider. The second half is what lets the top-rung pin `fable` stand in a kit source —
    Claude keeps it literally, every other provider gets its own top row (DEC-0076) — while keeping
    `opus`/`sonnet` out of a SOURCE: a kit source spells the rung the way the project's `model_map`
    does, so the scaffold's rewrite and the map agree in one vocabulary, and a literal target in a
    source is a second spelling of the same rung.

    `tools/validate.py` is the caller; the derivation lives here because this module is the one
    that reads the tiers file, and the enumeration it replaces ("lead/worker/light") was a list
    that refused a value the generator has carried since a real project map contained it.
    """
    if tiers is None or aliases is None:
        tiers, aliases = load_tiers()
    value = str(model)
    if value in aliases:
        return True
    if value in set(aliases.values()):
        return False
    others = [provider for provider in tiers if provider != REFERENCE_PROVIDER]
    return bool(others) and all(
        provider_model(value, provider, tiers, aliases) != value for provider in others)


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
        # ...and only a model value the TABLE places (DEC-0076): an alias or a rung name. This was
        # a set of seven spellings that still knew `light` and `haiku`.
        tiers, aliases = load_tiers()
        for role, value in values.items():
            if (not isinstance(role, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", role)
                    or not isinstance(value, str)
                    or (map_name == "effort_map" and value not in allowed_efforts)):
                raise SystemExit("project_config.yaml %s contains an invalid role/value; provider "
                                 "artifacts were left untouched" % map_name)
            if map_name == "model_map" and not table_places(value, tiers, aliases):
                raise SystemExit(unplaceable_pin_sentence(
                    "project_config.yaml model_map role %s" % role, value, tiers, aliases))
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
    """Hash every installed hook dependency so Codex trust changes when executable code changes.

    The ALGORITHM lives in `kernel.hashing.hook_bundle_hash` and is shared with `python scripts/harness.py doctor`,
    which used to compute a different hash over this same directory — so doctor's `hook_trust`
    could never match the value this generator bound Codex to. Only the two guarantees specific to
    generating a trust binding stay here: a missing directory is fatal (Codex trust must not be
    bound to nothing), and the tree must be free of reparse points (a junction inside the bundle
    would let the hashed bytes and the executed bytes diverge).
    """
    if not os.path.isdir(os.path.join(repo, ".claude", "hooks")):
        raise SystemExit("Missing .claude/hooks; Codex hook trust cannot be bound to the bundle")
    for subtree in kernel_hashing().BUNDLE_SUBTREES:
        if os.path.isdir(os.path.join(repo, ".claude", subtree)):
            assert_tree_no_reparse(repo, ".claude/" + subtree)
    digest = kernel_hashing().hook_bundle_hash(os.path.join(repo, ".claude"))
    if digest is None:
        raise SystemExit("Could not hash .claude/hooks; Codex hook trust cannot be bound to it")
    return digest


def kernel_hashing():
    """The kernel's hashing module, imported from wherever this script is installed.

    This script ships INSIDE `team-kits/`, so the kernel package is its sibling — the same
    directory the hooks resolve it from. Imported lazily and by path rather than at module scope
    because the generator is also run straight from the harness checkout.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    from kernel import hashing
    return hashing


def hook_bundle_verifier_b64():
    """Return trusted inline verifier code; its bytes live in the hook definition Codex hashes.

    The one surviving copy of `kernel.hashing.hook_bundle_hash`, and it has to be a copy: Codex
    hashes these bytes as part of the hook definition, so the verifier cannot import the thing it
    is verifying. `argv[1]` is the `.claude` DIRECTORY, not the hooks directory, because the scope
    is `kernel.hashing.BUNDLE_SUBTREES` — every subtree it names, whichever those are on the day
    the artifacts are generated (see the last paragraph) — and it skips NOTHING inside them,
    bytecode included, for the reason `kernel.hashing.BYTECODE_SUFFIXES` gives.

    ON CODEX THIS IS THE ENFORCED MEASUREMENT, so a divergence here is not a reporting defect but
    an unfixed hole. It happened: the canonical function learned to name a directory symlink
    instead of walking past it, this copy did not, and for one release R5-F2 was simply not fixed
    on that provider — a `.claude/hooks/yaml -> <elsewhere>` that replaces PyYAML for the kernel of
    every gate process passed every Codex hook with rc 0 while the canonical hash had long since
    changed (measured end to end, 2026-07-27).

    The other direction is real too, but it lands earlier and more gently than it first looks:
    `assert_tree_no_reparse` refuses to GENERATE artifacts for a bundle containing any reparse
    point, so a legitimate directory link does not produce Codex hooks that refuse an unchanged
    bundle — it produces no Codex hooks at all, with a readable message. What survives generation
    is a link planted afterwards, which is the security half.

    `test_the_inline_codex_verifier_agrees_with_the_canonical_hash` runs both over
    `_adversarial_bundle`, which since 2026-07-27 contains a real directory symlink for exactly
    this reason; a junction would not do, because `os.path.islink` is False for one and both sides
    then agree by descending into it.

    WHAT IS COPIED IS THE ALGORITHM; THE CONSTANTS ARE INTERPOLATED. The scope of the measurement
    and the stand-in a symlink contributes are values, and a value written out here a second time
    is the same drift class as the walk above with none of its excuse — the copy cannot import
    `kernel.hashing` at RUN time, but this function reads it at GENERATION time and can simply
    write today's answer into the source it emits. That matters most for the scope: a bundle
    subtree added to `BUNDLE_SUBTREES` would otherwise be hashed by the canonical function and
    ignored by the enforced one, and no fixture-based pin could notice, because a tree that does
    not yet exist expresses no disagreement. Substituted by name rather than with `%` because the
    emitted code contains a `%s` of its own.
    """
    hashing = kernel_hashing()
    code = r'''import hashlib
import os
import sys

root, expected = sys.argv[1], sys.argv[2]
digest = hashlib.sha256()
try:
    for subtree in __SUBTREES__:
        base = os.path.join(root, subtree)
        if not os.path.isdir(base):
            continue
        for current, dirs, files in os.walk(base):
            # A directory symlink contributes its NAME plus the marker and no content, and is not
            # descended into -- byte for byte what kernel.hashing._bundle_files does, including
            # emitting the links of a level before its files. os.walk would otherwise skip the
            # link entirely and the hash would not notice a shadowing package.
            linked = sorted(d for d in dirs if os.path.islink(os.path.join(current, d)))
            dirs[:] = sorted(d for d in dirs if d not in linked)
            for dirname in linked:
                path = os.path.join(current, dirname)
                relative = subtree + "/" + os.path.relpath(path, base).replace(os.sep, "/")
                digest.update((relative + "/" + __MARKER__).encode("utf-8") + b"\0")
                digest.update(b"\0")
            for filename in sorted(files):
                path = os.path.join(current, filename)
                relative = subtree + "/" + os.path.relpath(path, base).replace(os.sep, "/")
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
    code = (code.replace("__SUBTREES__", repr(tuple(hashing.BUNDLE_SUBTREES)))
                .replace("__MARKER__", repr(hashing.SYMLINK_MARKER)))
    return base64.b64encode(code.encode("utf-8")).decode("ascii")


def codex_hook_commands(command, agent_types=(), bundle_hash=""):
    """Return repo-root-stable POSIX and Windows hook commands.

    Codex runs hook commands from the session cwd. The official docs explicitly warn that this
    may be a nested directory, so a plain `.claude/hooks/x.py` path is not safe. Git is the fast
    path; a parent walk keeps greenfield repositories working before `git init`.

    BOTH interpreter invocations carry `-B`, and the verifier's is the one that must not be
    forgotten: it is the process that runs FIRST on every Codex tool call, so a `.pyc` written by
    it would change the bundle between the verification and the next one. The `-B` in the kits'
    settings.json does not reach here — this function rebuilds the command from the script path
    rather than passing the original string through — so it is stated again rather than inherited.
    See `kernel.hashing.BYTECODE_SUFFIXES` for what the bundle hash now covers.
    """
    relative = rel_command(command).replace("\\", "/")
    match = re.search(r"(?:^|[\"'])((?:\.claude|\.codex)/hooks/[^\"']+\.py)(?:[\"']|$)", relative)
    if not match:
        return relative, relative
    script = match.group(1)
    # ...and whatever follows it. Every V2 gate is now registered as `_gate.py gate_x.py`, and a
    # translation that kept only the first `.py` would hand Codex a launcher with no gate to run —
    # which the launcher correctly refuses, so EVERY gated call on that provider would be blocked
    # by a harness defect. `script` stays the launcher because the root-walk below needs a file
    # that exists; the argument rides along separately.
    tail = relative[match.end():].strip().strip("\"'")
    script_args = " ".join(
        part for part in re.findall(r"[^\s\"']+\.py", tail) if "/" not in part and "\\" not in part)
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
             '"$py" -B -c "import base64;exec(base64.b64decode(\'%(verify)s\'))" '
             '"$root/.claude" "%(hash)s" || exit $?; '
             '%(env)s "$py" -B "$root/%(script)s"%(args)s' % {
                 "script": script, "env": posix_env, "verify": verifier,
                 "args": (" " + script_args) if script_args else "",
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
                '$verify | & $py.Source -B - (Join-Path $root \'.claude\') \'%(hash)s\'; '
                'if ($LASTEXITCODE -ne 0) { exit 2 }; '
                # `powershell -Command` collapses a native child's exit code to 1, and 1 is what
                # Claude Code and Codex both read as "non-blocking error" = ALLOW. Without this
                # line every Windows block became a pass — the same failure class the launcher
                # exists to close, one layer out in the shell.
                '& $py.Source -B (Join-Path $root \'%(script)s\')%(args)s; '
                'if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"'
               % {"script": script, "env": windows_env, "verify": verifier,
                  "args": (" " + script_args) if script_args else "",
                  "hash": bundle_hash})
    return posix, windows


def gen_codex_hooks(settings, role_hooks=(), repo=None):
    registrations = {}
    global_keys = set()
    for event in CODEX_EVENTS:
        for matcher, hook in hook_entries(settings, event):
            # one registration per Codex matcher: a Claude matcher naming tools from two Codex
            # vocabularies is two Codex registrations, not a choice between them
            for cm in codex_matchers_for(event, matcher):
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
        for cm in codex_matchers_for(event, matcher):
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


# THE ROLE-MEMORY DUTY, as the one pattern that decides what it IS. Codex has no per-role memory
# feature, so a role text carrying this sentence has to be rewritten on the way out -- which makes
# this regex the running definition of "this text prescribes the memory duty", and the only one.
# `tools/test_role_contracts.py::test_the_memory_duty_is_only_prescribed_where_the_role_has_memory`
# reads it from here to ask the CLAUDE side of the same question: a role told to consult a memory
# its own frontmatter does not enable has nothing to consult (BUG-0047). Two readers, one pattern,
# so a reworded duty that slips past the Codex rewrite is caught on the Claude side too.
MEMORY_DUTY_RX = re.compile(
    r"Consult\s+your agent memory\s+before,\s*update it after\.", re.IGNORECASE)
# The frontmatter key that turns the provider's role memory ON. A role without it has no memory
# directory to consult, whatever its prose says.
MEMORY_FRONTMATTER_KEY = "memory"


def codex_text(text):
    """Apply only unambiguous path translations to generated Codex copies."""
    translated = (text.replace("./CLAUDE.md", "./AGENTS.md")
                  .replace(".claude/skills/", ".agents/skills/"))
    return MEMORY_DUTY_RX.sub(
        "Consult checked-in project_memory and your native skill before acting; record durable "
        "project facts only in the designated project_memory files.",
        translated,
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
        # The kernel the hooks import, and the record `hook_trust` is measured against. The
        # Claude side of this pair (`guard_harness_selfmod.BLOCKED`) gained both when the scaffold
        # started installing the kernel into the project; leaving the Codex profile behind would
        # have made the thin gates read-only and the code they delegate to writable.
        '".claude/kernel" = "read"',
        '".claude/kit_state.json" = "read"',
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


def native_skill_sources(repo):
    """Every skill directory this project carries -- the one subject of the Codex mirror.

    A SKILL IS A DIRECTORY WITH A `SKILL.md` IN IT. That is what both providers discover, it is
    what this generator already refuses a role for (`missing_skills` above), and it is a definition
    rather than a list -- so a reference skill, which belongs to no role by construction
    (constitution §1a), is covered the day it ships instead of the day somebody remembers it.

    UNTIL TSK-0104 THIS WALKED THE ROLE LIST, so a real `team` install left both reference skills
    out of the mirror entirely while three shipped texts pointed a Codex session at them. The
    directory counts of that measurement live in `H83` and only there -- one of them was taken over
    a project with a design-system bundle dropped in, which is a qualification a second copy of the
    number here would lose (SR-0008).

    WHAT IT ALSO COVERS, said rather than discovered later: a bundle the USER unpacked there --
    `FR-0045` invites exactly that -- is a skill directory by this definition and is mirrored too.
    That is the wanted direction (the two providers see the same skills), and it is the reason this
    reads the disk instead of any list the kit keeps.
    """
    base = os.path.join(repo, ".claude", "skills")
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return []
    return [name for name in names
            if os.path.isfile(os.path.join(base, name, "SKILL.md"))]


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
                if not table_places(meta.get("model"), tiers, aliases):
                    raise SystemExit(unplaceable_pin_sentence(
                        "Agent %s" % role_name, meta.get("model"), tiers, aliases))
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
        desired_dirs.update(".agents/skills/%s" % name for name in native_skill_sources(repo))

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
        for name in native_skill_sources(repo):
            source = os.path.join(repo, ".claude", "skills", name)
            relative = ".agents/skills/%s" % name
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
