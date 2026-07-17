#!/usr/bin/env python3
"""
Shared helper: provider payload adapter — ONE place that normalizes hook payloads.

Claude Code and Codex CLI send similar hook JSON (`tool_name`/`tool_input`/`cwd`/
`hook_event_name`), but their enforcement contracts differ. Claude documents exit 2 + stderr as
blocking. Codex documents exit 2 + stderr for PreToolUse/PostToolUse/UserPromptSubmit/SubagentStop
AND a structured `decision: block` JSON for the post/stop events; stop() below uses the JSON form
there because it carries the reason back to the model (verified 2026-07-14, official docs+source).
The differences this shim absorbs:

  * Codex file edits arrive as tool_name "apply_patch" with the patch envelope in
    tool_input.command (no file_path). load() normalizes that to tool_name "Edit" and extracts
    EVERY touched file from the `*** Add|Update|Delete File:` and `*** Move to:` headers; path guards iterate
    file_paths() so a multi-file patch cannot smuggle a blocked path past a single-path check.
  * Lowercase/alternate tool names from non-Claude payloads are normalized to the Claude names
    every guard filters on (see _TOOL_ALIASES).

Uncertainty -> return the payload unchanged; a guard that cannot parse stays fail-open (exit 0),
same philosophy as every other hook.
"""
import json
import os
import re
import sys

try:
    from _root import find_repo_root
except Exception:  # standalone import (tests) — same fallback _audit uses
    def find_repo_root(start=None):
        return os.environ.get("CLAUDE_PROJECT_DIR") or start or os.getcwd()


_PATCH_FILE_RX = re.compile(r"(?m)^\*{3} (Add|Update|Delete) File: (.+?)\s*$")
_PATCH_MOVE_RX = re.compile(r"(?m)^\*{3} Move to: (.+?)\s*$")
# providers use different tool vocabularies — normalize the KNOWN aliases to the Claude names
# every guard filters on; unknown names pass through untouched (guards then fail open, by design).
_TOOL_ALIASES = {"edit": "Edit", "write": "Write", "bash": "Bash", "powershell": "PowerShell",
                 "str_replace": "Edit", "create_file": "Write", "shell": "Bash"}


def load(stream=None):
    """Read + normalize the hook payload from stdin. Never raises; returns {} on garbage."""
    try:
        data = json.load(stream or sys.stdin)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    ti = data.get("tool_input")
    if not isinstance(ti, dict):
        ti = {}
        data["tool_input"] = ti
    tn = str(data.get("tool_name") or "")
    if tn in _TOOL_ALIASES:
        data["tool_name"] = _TOOL_ALIASES[tn]
    if data.get("tool_name") == "apply_patch":
        patch = str(ti.get("command") or ti.get("input") or "")
        raw_operations = _PATCH_FILE_RX.findall(patch)
        raw_operations += [("Move", path) for path in _PATCH_MOVE_RX.findall(patch)]
        # patch paths are CWD-relative (Codex applies the patch against the session cwd). Join
        # against cwd for the file the edit REALLY touches, and ADDITIONALLY against the repo
        # root when the two differ: block-guards then catch either interpretation (fail-closed
        # against cwd drift — the failure class _root.py exists for), while isfile-based checks
        # simply skip the nonexistent candidate. (Audit finding: cwd in a subdir made a
        # repo-root-looking patch path miss every prefix check.)
        base = str(data.get("cwd") or "")
        root = find_repo_root(base or None)
        operations = []
        for operation, q in raw_operations:
            p = q.replace("\\", "/")
            if os.path.isabs(p):
                operations.append({"operation": operation, "path": p})
                continue
            operations.append({"operation": operation,
                               "path": os.path.join(base, p) if base else p})
            if root and os.path.abspath(root) != os.path.abspath(base or root):
                cand = os.path.join(root, p)
                if not any(item["path"] == cand and item["operation"] == operation
                           for item in operations):
                    operations.append({"operation": operation, "path": cand})
        paths = [item["path"] for item in operations]
        data["tool_name"] = ("Write" if operations and
                             all(item["operation"] == "Add" for item in operations) else "Edit")
        data["_file_operations"] = operations
        data["_file_paths"] = paths
        if paths and not ti.get("file_path"):
            ti["file_path"] = paths[0]
    return data


def file_paths(data):
    """Every file this tool call touches (list of str; may be empty). Path guards MUST iterate
    this instead of reading tool_input.file_path once — a Codex multi-file patch is one call."""
    if isinstance(data.get("_file_paths"), list) and data["_file_paths"]:
        return [str(p) for p in data["_file_paths"]]
    ti = data.get("tool_input") or {}
    p = ti.get("file_path") or ti.get("path") or ""
    return [str(p)] if p else []


def created_file_paths(data):
    """Paths newly created by apply_patch (`Add File` or a `Move to` destination)."""
    operations = data.get("_file_operations")
    if isinstance(operations, list):
        return [str(item.get("path")) for item in operations
                if isinstance(item, dict) and item.get("operation") in ("Add", "Move")
                and item.get("path")]
    return file_paths(data) if data.get("tool_name") == "Write" else []


# Shared push/merge detection for every git gate (single home — six hook-local copies drifted:
# an audit had to fix the same regression twice). Shell-WRAPPER payloads are CODE
# (`bash -c "git push"` must gate), remaining quoted spans are PROSE (a commit MESSAGE describing
# a push must not). Unquoted prose may still over-trigger — the safe direction for a gate.
# The c-flag may sit in a COMBINED short cluster (`bash -lc`, `-xec` — audit: `-lc` bypassed
# every gate) and quoted payloads may contain ESCAPED quotes — both are handled below.
_WRAPPER_RX = re.compile(
    r'((?:bash|sh|zsh|dash|pwsh|powershell|cmd)(?:\.exe)?\s+(?:[-/]{1,2}[\w-]+\s+)*'
    r'[-/]{1,2}(?:[A-Za-z]*c|command)\s+)("((?:\\.|[^"\\])*)"|\'((?:\\.|[^\'\\])*)\')',
    re.IGNORECASE | re.DOTALL)
_QUOTED_RX = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')


def git_invocation_text(command):
    """Lowercased command text with wrapper payloads unwrapped and prose quotes stripped."""
    unwrapped = _WRAPPER_RX.sub(
        lambda m: m.group(1) + " " + (m.group(3) if m.group(3) is not None else m.group(4) or "")
        + " ", command or "")
    return _QUOTED_RX.sub(" ", unwrapped.lower())


def wants_push_or_merge(command):
    """True when the command really invokes `git push`/`git merge` (not merely mentions it)."""
    return re.search(r"\bgit\b[^&|;\n]*\b(push|merge)\b", git_invocation_text(command)) is not None


def stop(message, event):
    """Block a post/stop event using the current provider's event-specific contract.

    Codex PostToolUse/SubagentStop consume `decision: block` + `reason`. Claude uses exit 2 with
    stderr for these events. PreToolUse guards should keep using exit 2 directly; current Codex
    builds support that contract and include `agent_id` for subagent tool calls.
    """
    if (os.environ.get("TEAM_KIT_PROVIDER", "").lower() == "codex"
            and event in ("PostToolUse", "SubagentStop")):
        sys.stdout.write(json.dumps({"decision": "block", "reason": message}) + "\n")
        sys.exit(0)
    sys.stderr.write(message)
    sys.exit(2)
