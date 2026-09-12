#!/usr/bin/env python3
"""BUG-0011 / DEC-0039: the handover marker counts ONLY as the shim line on line 1.

The global entry file (`user/claude/CLAUDE.md` -> `~/.claude/CLAUDE.md`) used to route handover on
whether `./CLAUDE.md` *contains* the substring `agents-and-skills:team-kit` anywhere. A sentence
that merely mentioned the marker -- documentation, an error message, a negation ("this repo carries
no such marker") -- triggered the handover (2026-08-04, real).

DEC-0039: the marker counts only at the fixed SHIM FORM `scaffold_team` writes on line 1
(`<!-- agents-and-skills:team-kit <team> -->`, with `@AGENTS.md` on line 2). A bare occurrence of the
marker on line 1 -- a quote, prose, a negation, a `#` comment -- is NOT a shim and must NOT hand over.

This module measures the RUNNING structural condition, not a string search over prose. The harness's
own kit detection is `session_status.py` (`re.match(<shim-form>, first_line)` after stripping a BOM);
that is the executed mirror of the handover rule. It is exercised as a real process against a project
OUTSIDE this repo:

  * a genuine shim -- plain, and with a leading space, CRLF, or a UTF-8 BOM (the forms real installs
    ship) -- IS detected -> the kit-update banner fires (handover analogue).
  * a line-1 MENTION of the marker (quote / prose / negation / `#` comment) is NOT detected -> no
    banner. This goes RED under the pre-fix loose predicate (`re.search(<marker>, line)`), which
    matched the marker anywhere on line 1 -- exactly BUG-0011's mechanism.

The process runs also validate the `_structural_kit` helper (helper-empty <=> process-silent,
helper-kit <=> process-banner), so the shipped-document scans below rest on the running behaviour.
See `test_hooks.py` (the real `scaffold_team` run) for the SHIM-GENERATION side: it pins that the
installed shim's line 1 is the marker and line 2 is `@AGENTS.md`.
"""

import glob
import io
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM_KITS = os.path.join(ROOT, "team-kits")
SESSION_STATUS = os.path.join(TEAM_KITS, "dev-team", "hooks", "session_status.py")

# The exact structural predicate the running hook applies to the FIRST line of ./CLAUDE.md: the
# shim FORM `<!-- agents-and-skills:team-kit <team> -->`, not a bare occurrence of the marker on the
# line. Kept here so the shipped-document scans use one predicate; the process runs below prove it
# agrees with session_status. BOM is stripped first, exactly as the hook does.
_SHIM_LINE = re.compile(r"\s*<!--\s*agents-and-skills:team-kit\s+([\w-]+)\s*-->\s*$")

# The kit-update block fires this exact head only when a kit was detected from CLAUDE.md AND the
# staged version is newer than the installed stamp -- an observable proxy for "a kit was detected".
_KIT_DETECTED_BANNER = "KIT UPDATE AVAILABLE"


def _structural_kit(text):
    """The kit a shim declares, read the way the harness reads it: the shim form on the FIRST line."""
    lines = text.splitlines()
    first_line = lines[0].lstrip("\ufeff") if lines else ""
    match = _SHIM_LINE.match(first_line)
    return match.group(1) if match else ""


def _run_session_status(repo, home):
    """Run the SHIPPED session_status hook as a process and return its additionalContext."""
    environment = dict(
        os.environ,
        CLAUDE_PROJECT_DIR=str(repo),
        HOME=str(home),
        USERPROFILE=str(home),
        CLAUDE_CONFIG_DIR=os.path.join(str(home), ".claude"),
        # A REACHABLE KERNEL, because a scaffolded project has one at `.claude/kernel` and this
        # fixture builds only the two files its own subject needs. The banner below is the kit
        # COMPARISON, and since FR-0006 that comparison is the kernel's (`kitupdate.relation`) --
        # without this the hook would answer "the kernel could not be reached" and the proxy would
        # measure the fixture's incompleteness instead of the detection under test.
        HARNESS_KERNEL_PATH=TEAM_KITS,
    )
    environment.pop("TEAM_KIT_PROVIDER", None)
    body = {"cwd": str(repo), "hook_event_name": "SessionStart", "session_id": "s"}
    result = subprocess.run(
        [sys.executable, SESSION_STATUS],
        input=json.dumps(body),
        capture_output=True,
        text=True,
        env=environment,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


def _project(base, claude_md):
    """A project whose only variable is the ./CLAUDE.md content. dev-team is staged NEWER than the
    installed stamp, so the kit-update banner is what the detection block emits WHEN it detects a
    kit -- and stays silent when it does not. `claude_md` may be str or raw bytes (bytes let a test
    control the exact CRLF/BOM the file carries on disk)."""
    home, repo = base / "home", base / "repo"
    os.makedirs(str(home / ".claude" / "team-kits" / "dev-team"), exist_ok=True)
    (home / ".claude" / "team-kits" / "dev-team" / "VERSION").write_text(
        "version: 2026.08.01-1\ncontent: staged\n", encoding="utf-8")
    os.makedirs(str(repo / ".claude"), exist_ok=True)
    (repo / ".claude" / "kit_version").write_text(
        "version: 2026.07.01-1\ncontent: local\n", encoding="utf-8")
    data = claude_md if isinstance(claude_md, bytes) else claude_md.encode("utf-8")
    with open(str(repo / "CLAUDE.md"), "wb") as handle:
        handle.write(data)
    return home, repo


# ---- fixtures the marker rule must SEPARATE -----------------------------------------------------
# Real installs -- every one must still be read as the dev-team kit.
_SHIM_TRIGGERS = {
    "plain": b"<!-- agents-and-skills:team-kit dev-team -->\n@AGENTS.md\n",
    "leading_space": b"   <!-- agents-and-skills:team-kit dev-team -->\n@AGENTS.md\n",
    "crlf": b"<!-- agents-and-skills:team-kit dev-team -->\r\n@AGENTS.md\r\n",
    "utf8_bom": b"\xef\xbb\xbf<!-- agents-and-skills:team-kit dev-team -->\n@AGENTS.md\n",
    # trailing whitespace after `-->` (but no further TEXT) is still a shim: `\s*$` swallows it.
    "trailing_ws": b"<!-- agents-and-skills:team-kit dev-team -->   \n@AGENTS.md\n",
}
# Line-1 MENTIONS -- each names the marker on line 1 but is not a shim, so none may hand over. The
# negation is the exact 2026-08-04 shape that started BUG-0011.
_LINE1_MENTIONS = {
    "quote": b'"agents-and-skills:team-kit dev-team"\n',
    "prose": b"See agents-and-skills:team-kit dev-team for details.\n",
    "negation": b"Note: the agents-and-skills:team-kit dev-team marker is not present here.\n",
    "hash_comment": b"# agents-and-skills:team-kit dev-team\n",
    # the shim FORM on line 1 but with text after the `-->` -- excluded by the end anchor `\s*$`,
    # which the entry prose ("@AGENTS.md on line 2 and nothing else") and the hook comment demand.
    "trailing_text": b"<!-- agents-and-skills:team-kit dev-team --> this is NOT an install\n",
}


@pytest.mark.parametrize("name", sorted(_SHIM_TRIGGERS))
def test_real_shim_forms_trigger_kit_detection(tmp_path, name):
    """Real kit direction: a genuine shim (incl. leading space / CRLF / UTF-8 BOM) IS read as a kit
    -> handover fires. Guards that anchoring to the shim form did not break real installs."""
    payload = _SHIM_TRIGGERS[name]
    home, repo = _project(tmp_path, payload)
    said = _run_session_status(repo, home)
    assert _KIT_DETECTED_BANNER in said, said
    assert _structural_kit(payload.decode("utf-8")) == "dev-team"


@pytest.mark.parametrize("name", sorted(_LINE1_MENTIONS))
def test_line1_mention_of_marker_does_not_trigger_kit_detection(tmp_path, name):
    """BUG-0011 direction: a marker MENTION on line 1 (quote / prose / negation / `#` comment) is
    NOT read as a kit -> no banner.

    Goes RED under the pre-fix loose predicate (`re.search(<marker>, first_line)`), which matched the
    marker anywhere on line 1: every one of these mentions would then fire the banner.
    """
    payload = _LINE1_MENTIONS[name]
    home, repo = _project(tmp_path, payload)
    said = _run_session_status(repo, home)
    assert _KIT_DETECTED_BANNER not in said, said
    # The mention IS present as a substring on line 1 -- so the check is not vacuous -- yet counts
    # as nothing.
    assert b"agents-and-skills:team-kit" in payload
    assert _structural_kit(payload.decode("utf-8")) == ""


def test_marker_below_line1_does_not_trigger(tmp_path):
    """Control: the same marker under line 1 is likewise no shim (the pre-fix predicate already
    handled this one -- kept so the line-1 cases above are the measured delta)."""
    payload = (b"# Notes\n\nThis repo carries no agents-and-skills:team-kit dev-team shim.\n")
    home, repo = _project(tmp_path, payload)
    said = _run_session_status(repo, home)
    assert _KIT_DETECTED_BANNER not in said, said
    assert _structural_kit(payload.decode("utf-8")) == ""


def _shipped_claude_md_files():
    """Every ./CLAUDE.md shipped in this repo (the repo root + the global entry file)."""
    return sorted(
        path for path in glob.glob(os.path.join(ROOT, "**", "CLAUDE.md"), recursive=True)
        if ".git" + os.sep not in path
    )


def test_shipped_claude_md_files_carry_the_marker_only_at_the_structural_position():
    """No shipped ./CLAUDE.md triggers handover except a genuine shim: its FIRST line is not the
    shim marker line, however freely it may mention the marker in prose elsewhere."""
    files = _shipped_claude_md_files()
    assert files, "no shipped CLAUDE.md found -- the scan would be vacuous"
    for path in files:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        assert _structural_kit(text) == "", (
            "%s would structurally trigger handover (shim marker on its first line)" % path)


def test_the_entry_file_explains_the_marker_without_triggering():
    """The exact defence DEC-0039 buys: the global entry file NAMES the marker in prose and, because
    the rule is structural, does not route itself. Both halves are asserted, or the claim is empty."""
    entry = os.path.join(ROOT, "user", "claude", "CLAUDE.md")
    with open(entry, encoding="utf-8") as handle:
        text = handle.read()
    assert "agents-and-skills:team-kit" in text, "the entry file no longer explains the marker"
    assert _structural_kit(text) == "", "the entry file's first line is the marker -- it self-routes"


# The two global entry files -- one per provider. Both decide handover, so both answer the same
# question, and the pair is what the test below reads: a rule that moves on one side alone is what
# BUG-0031 was.
ENTRY_FILES = (os.path.join(ROOT, "user", "claude", "CLAUDE.md"),
               os.path.join(ROOT, "user", "codex", "AGENTS.md"))

_MARKER = "agents-and-skills:team-kit"
# The COMPLETE shim, with the team name left open -- what `scaffold_team` writes on line 1 and the
# only shape in which an entry file may name the marker at all.
_SHIM_SPELLING = re.compile(r"<!--\s*" + re.escape(_MARKER) + r"\s+.*?-->")


@pytest.mark.parametrize("entry", ENTRY_FILES, ids=lambda path: os.path.basename(os.path.dirname(path)))
def test_an_entry_file_names_the_marker_only_as_the_whole_shim(entry):
    """BUG-0031: the Codex entry gate routed handover on whether `./AGENTS.md` CONTAINS the marker
    -- the occurrence-versus-mention flaw DEC-0039 had already closed for the Claude entry gate.

    THE PROPERTY, rather than a search for the word "first line": in a file that DECIDES handover,
    every occurrence of the marker stands inside the complete shim `<!-- ... -->`. A rule quoting
    the bare marker is a rule about a substring, which is the defect itself; a rule quoting the
    whole shim is a rule about line 1's FORM, and it also cannot route the file it stands in --
    which the second assertion measures against the same structural predicate `session_status`
    executes. Asked of BOTH entry files as one parametrized pair, so neither provider's half can
    drift alone again.

    Measured on fd7e2fa before the fix: the Claude file's two occurrences were both whole shims,
    the Codex file's single occurrence (`user/codex/AGENTS.md`, the detect-state step 1) was bare.
    """
    with io.open(entry, encoding="utf-8") as handle:
        text = handle.read()
    assert _MARKER in text, "%s no longer explains the marker at all" % entry
    bare = [line.strip() for line in text.splitlines()
            if _MARKER in line and not _SHIM_SPELLING.search(line)]
    assert not bare, (
        "%s names the marker outside the shim form -- a `contains` rule routes on a mention "
        "(BUG-0011/BUG-0031):\n  %s" % (entry, "\n  ".join(bare)))
    assert _structural_kit(text) == "", "%s's first line is the marker -- it self-routes" % entry


def test_kit_constitution_shim_source_carries_the_marker_on_line_one():
    """The other direction of the shipped scan: every kit's constitution (the shim SOURCE
    scaffold_team copies line 1 from) DOES declare its kit in the shim form -> real installs hand
    over. This is the same invariant validate.py enforces at build time (DEC-0039)."""
    constitutions = sorted(
        glob.glob(os.path.join(TEAM_KITS, "*", "constitution", "AGENTS.md")))
    assert constitutions, "no kit constitutions found"
    for path in constitutions:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        kit = os.path.basename(os.path.dirname(os.path.dirname(path)))
        assert _structural_kit(text) == kit, (
            "%s line 1 is not the shim marker for its kit (scaffold_team's shim source)" % path)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
