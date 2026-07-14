#!/usr/bin/env python3
"""codex_global_config.py — OPT-IN user-wide secret shield for Codex ($CODEX_HOME/config.toml).

The Claude side gets user-wide secret-read denies via the settings.json merge; Codex has no merge
layer, so this OPT-IN installer step (install.ps1 -CodexGlobalSecrets / install.sh
--codex-global-secrets) adds the counterpart: a clearly marked permission profile denying reads of
secret files in every Codex session outside team projects (inside them, the generated project
profile takes precedence on the CLI).

Verified facts this design rests on (learn.chatgpt.com/docs/permissions + openai/codex source,
2026-07-14):
  * Profiles are CLOSED-WORLD (unlisted paths are denied) -> a deny-only profile would lock
    everything; the profile below `extends = ":workspace"` to keep normal behavior + denies.
  * `[permissions]` profiles WITHOUT any `default_permissions` are a Codex config ERROR -> the
    activation line is only skipped when the user already has their own `default_permissions`.
  * `default_permissions` is a TOP-LEVEL key: TOML requires it BEFORE the first [table], so it is
    surgically inserted there; the profile block itself is appended at the end.
  * Legacy `sandbox_mode`/`[sandbox_workspace_write]` in ANY loaded config level silently disables
    `default_permissions` entirely -> fail-closed abort with guidance instead of writing an inert
    shield.
  * Honest behavior change: with the shield active, folders WITHOUT a trust decision start with
    the `:workspace` baseline instead of `:read-only` (approval prompts are a separate layer and
    stay as they are).

Fail-closed rules: unparseable TOML -> exit 2, nothing written. Legacy sandbox keys -> exit 3,
nothing written. No tomllib (Python < 3.11) -> exit 4, nothing written. Every write goes to a
temp file, is re-parsed with tomllib, then atomically replaces config.toml (backup made first).
Removal: delete the two marked regions.
"""
import os
import shutil
import sys
import tempfile

MARKER = "agents-and-skills:codex-global-secrets"
PROFILE = "agents-and-skills-secrets"
ACTIVATION_BLOCK = (
    "# >>> %s (activation) — delete together with the marked block at the end >>>\n"
    'default_permissions = "%s"\n'
    "# <<< %s (activation) <<<\n"
) % (MARKER, PROFILE, MARKER)
# Mirrors the Claude-side user-wide permissions.deny Read() list; `~/.ssh` is a top-level entry
# because :workspace_roots globs only reach into workspace roots, never the home directory.
PROFILE_BLOCK = (
    "\n"
    "# >>> %s v1 — user-wide secret shield (opt-in; delete this block AND the activation\n"
    "# line near the top to remove; team projects override it with their generated profile) >>>\n"
    "[permissions.%s]\n"
    'extends = ":workspace"   # closed-world profiles need a baseline; approvals stay separate\n'
    "\n"
    "[permissions.%s.filesystem]\n"
    "glob_scan_max_depth = 8\n"
    '"~/.ssh" = "deny"\n'
    "\n"
    '[permissions.%s.filesystem.":workspace_roots"]\n'
    '"**/.env" = "deny"\n'
    '"**/.env.*" = "deny"\n'
    '"**/secrets/**" = "deny"\n'
    '"**/*.key" = "deny"\n'
    '"**/*.pem" = "deny"\n'
    "# <<< %s <<<\n"
) % (MARKER, PROFILE, PROFILE, PROFILE, MARKER)


def fail(code, message):
    sys.stderr.write(message + "\n")
    sys.exit(code)


def parse_or_fail(text, label):
    try:
        import tomllib
    except ImportError:
        fail(4, "Python 3.11+ is required for safe TOML reading; the Codex secret shield was "
                "NOT installed.")
    try:
        return tomllib.loads(text)
    except Exception as exc:
        fail(2, "%s is not valid TOML (%s); nothing was written." % (label, exc))


def main():
    if len(sys.argv) != 2:
        fail(1, "usage: codex_global_config.py <codex_home>")
    codex_home = sys.argv[1]
    if not os.path.isdir(codex_home):
        fail(1, "Codex home does not exist: %s" % codex_home)
    path = os.path.join(codex_home, "config.toml")
    original = ""
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            original = fh.read()
    data = parse_or_fail(original, path) if original else {}

    if "sandbox_mode" in data or "sandbox_workspace_write" in data:
        fail(3, "Your %s sets legacy sandbox_mode/[sandbox_workspace_write]. Codex then IGNORES "
                "permission profiles entirely (upstream precedence), so installing the shield "
                "would only pretend to protect you. Remove/migrate that legacy setting yourself, "
                "then rerun with the flag. Nothing was written." % path)

    if MARKER in original:
        print("  [ok]   Codex secret shield already installed (marker present) - nothing to do.")
        return 0

    existing_default = data.get("default_permissions")
    activate = existing_default is None
    if not activate:
        print("  [note] default_permissions is already set to %r - the shield profile is "
              "appended but NOT activated. To use it, point default_permissions at \"%s\" "
              "(or extend your own profile with the deny list)."
              % (existing_default, PROFILE))

    lines = original.splitlines(keepends=True)
    if activate:
        # TOML requires top-level keys BEFORE the first table header — insert there.
        insert_at = len(lines)
        for index, line in enumerate(lines):
            if line.lstrip().startswith("["):
                insert_at = index
                break
        lines.insert(insert_at, ACTIVATION_BLOCK)
    body = "".join(lines)
    if body and not body.endswith("\n"):
        body += "\n"
    body += PROFILE_BLOCK

    parsed = parse_or_fail(body, "the updated config")  # never install something Codex rejects
    assert PROFILE in parsed.get("permissions", {})

    if original:
        shutil.copy2(path, path + ".agents-and-skills.bak")
    fd, temporary = tempfile.mkstemp(prefix=".config.toml.", dir=codex_home)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)

    print("  [ok]   Codex secret shield installed into %s%s" % (
        path, "" if activate else " (inactive - see note above)"))
    if activate:
        print("  [note] honest behavior change: folders WITHOUT a trust decision now start with "
              "the :workspace baseline instead of :read-only (approval prompts stay unchanged); "
              "team projects keep their generated profile.")
        print("  [note] Windows caveat: glob denies match case-sensitively and ** patterns are "
              "snapshot-expanded at session start.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
