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
import contextlib
import functools
import itertools
import json
import os
import re
import subprocess
import sys
import threading
import time

try:
    from _root import find_repo_root
except Exception:  # standalone import (tests) — same fallback _audit uses
    def find_repo_root(start=None):
        return os.environ.get("CLAUDE_PROJECT_DIR") or start or os.getcwd()

# OUTBOUND half of the encoding family (audit): hooks write block messages to stderr, which
# Windows opens cp1252 — "Käufer" reached a UTF-8-reading provider as mojibake while the
# INBOUND side was already pinned. Import-time side effect on purpose: every hook that imports
# _compat (all of them) gets UTF-8 streams without a per-hook call to forget.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # non-reconfigurable stream (a test runner capturing it) — best effort


# BOUNDED stdin (spec II.4: "Hooks lesen stdin BEGRENZT"). An unbounded read makes every hook a
# memory amplifier for whatever the provider puts in tool_input (a Write of a huge file, a pasted
# dump). The cap is generous — real payloads carry whole file contents — but finite.
#
# Overflow BLOCKS by default, and that default is the whole design. The first cut of this returned
# a sentinel dict for the caller to notice, which silently disarmed ten shipped guards at once:
# they all dispatch on `tool_name`, the sentinel has none, so every one of them exited 0 = ALLOW —
# a 17 MB Write of `.claude/settings.json` walked straight past guard_harness_selfmod. An
# oversized payload means "this call could not be inspected", and for an integrity gate that must
# never read as "allowed" (spec II.4 fail-closed). So the SAFE behaviour is what you get by
# forgetting; comfort hooks (formatting, dashboards, notifications) opt out explicitly and
# greppably via tolerate_overflow=True.
STDIN_LIMIT = 16 * 1024 * 1024

# THE BUDGET ONE HOOK PROCESS GIVES ITSELF, in the one place it may be written down. It is NOT the
# window the provider kills at -- BUG-0062 measured that one and it is an order of magnitude away:
# on claude.exe 2.1.239 a PreToolUse registration naming no `timeout` survived 310 s and 560 s and
# was killed at 900 s, its session dating the kill near 600 s, while one naming `timeout: 5` was
# killed at 5 s and the refused command ran with nothing said to the user
# (tools/provider_observations.json -> `hook_deadlines`; the settings files carry the rule that
# follows, where the entries live). 60 s is comfortably INSIDE every window a shipped entry names,
# so a hook that keeps this budget is never near a kill -- and since BUG-0153/H61 the section below
# is what NOTICES a window arriving, which this paragraph used to say nothing did. The reason to
# keep the budget beside that: a gate that is still deciding is a session standing still, with the
# user looking at it, and the deadline's refusal arrives much later than that.
#
# WHAT ACTUALLY READS IT TODAY, stated exactly rather than generously — and the bracket that used to
# stand above named two bounds as DERIVED from this constant when neither is one:
# `guard_fs_tripwire.budget_cap()` computes a CEILING from it, and `CORRECTION_CAP` is CHECKED
# against that ceiling rather than derived from it: the cap is chosen for a reason about the WORK,
# which its own comment carries, and `test_the_cap_stays_inside_the_budget_it_exists_for` (in
# `tools/test_hooks.py`) recomputes the ceiling and requires the cap to sit under it.
# That is the whole of what reads this constant. `gate_ledger_valid.TOTAL_BUDGET = 40` is a number
# that derives from nothing at all; pointing it here is a sweep of its own and is NOT done here
# (verifier round 3, V5, correcting round 2's claim that they already point here); the residue is
# named in docs/reviews/2026-08-18-tsk0077-measurements.md. Since 2026-09-12 a SECOND reader asks
# it, and from outside this file: the rule that every registered window clears the chain's own child
# bounds PLUS this budget
# (`tools/test_hooks.py::test_every_registration_names_a_window_its_gate_can_answer_inside`), which
# is what makes the shipped windows derived rather than chosen.
HOOK_DEADLINE_SECONDS = 60.0


# THE KERNEL'S ENTRY POINT, in the two spellings a command line can reach it by, and in ONE place
# because two gates now ask "is this the harness": `gate_write_scope` (rule 4, which commands a
# subagent may not order) and `gate_dispatch` (DEC-0107, who may classify a failed run). They are
# kept HERE rather than read off `kernel.cli` so that a Bash call does not pay for importing
# argparse and every field schema to answer it; the pin against the kernel is
# `tools/test_hooks_v2.py::test_the_gate_knows_the_entry_point_the_kernel_installs`, which compares
# both with `kernel.cli.ENTRY_POINT` and the module's own name.
HARNESS_SCRIPT = "harness.py"
KERNEL_CLI_MODULE = "kernel.cli"


def names_the_kernel_entry_point(command):
    """Could this command line reach the kernel CLI at all?

    A CHEAP NECESSARY CONDITION and nothing more, which is exactly what its callers need: a line
    that never spells the entry point cannot hand the kernel anything, so a question that needs the
    kernel imported is not asked of it. Deliberately NOT the structural reading
    `gate_write_scope._harness_argv` performs (the entry point in an execution position): being
    wider here costs one lookup on a line that mentions the harness in passing, while being
    narrower would let a line that really does invoke the CLI past the caller's own rule.
    """
    text = str(command or "").lower()
    return HARNESS_SCRIPT in text or KERNEL_CLI_MODULE in text


# -- the WINDOW the registration gives this hook process, and the refusal that beats the kill -----
#
# WHY THE CONSTRUCTION LIVES HERE AND NOT IN `_kernel`. A hook still deciding when its window closes
# is KILLED, and a killed hook is read as "hook error, carry on" -- an ALLOW. `_kernel` has had this
# since 2026-09-05, and `_kernel` is imported by 10 of 27 shipped dev hooks, 14 of 27 office, 9 of
# 24 research (measured 2026-09-12, BUG-0153/H61): the other 45 -- `format_on_write`,
# `notify_agent_events`, `guard_no_adhoc`, `gate_pipeline` among them -- ran with no bound of their
# own at all. THIS module is the one every shipped hook imports and whose `load()` every shipped
# hook calls, which is what turns the bound from a list of hooks that remembered to ask for it into
# a property of being a hook. `_kernel.start_the_deadline` is a delegation to this now, so a gate
# that arms it explicitly and a hook that arms it by reading its payload get the same budget and
# the same sentences.
PROVIDER_DIR = ".claude"
SETTINGS_FILE = "settings.json"
TIMEOUT_KEY = "timeout"

# When the registration does not govern this process at all (see `registered_window`), the provider
# still has a window. MEASURED and BRACKETED, not pinned: a hook slept 310 s and 560 s and woke with
# its refusal intact, and at 900 s it never woke while the call it was refusing went through; the
# session length dates the kill at about 600 s (2026-08-23, claude.exe 2.1.239). The LONGEST
# SURVIVING run is what everything judges against, because that is the earliest the kill may
# already have come. The workshop keeps the record; a kit cannot read it, so this is where the
# number lives on this side, and
# `tools/test_hooks.py::test_the_kit_deadline_reader_carries_the_measured_default_window` compares
# the two so they cannot drift apart.
DEFAULT_WINDOW_SECONDS = 560.0

# What is NOT spent, so the refusal wins the race against the kill. A FLOOR and not a share of the
# window, and the difference is measured rather than taste: `gate_pipeline` is registered at 1800
# and bounds its own child at 1500, so a one-fifth share would end this process a minute BEFORE the
# gate's own bound could speak. The floor stands above the worst process start measured on this
# apparatus (0.81 s) and above the span nothing here can measure -- from this process's exit to the
# provider noticing it.
DEADLINE_RESERVE_SECONDS = 1.5

# The third answer of `registered_window`, spelled rather than left as a bare string: "this file
# does not govern this process", which is not the same as "this file leaves the window open".
UNBOUND = "unbound"

# When this module was LOADED, which is the earliest clock a hook has of its own: the provider
# started the process before that, and no process can measure the part of its own start that
# happened before its first line ran. The budget is counted from HERE, so everything the imports
# have cost is spent out of the window rather than added to it.
_STARTED_AT = time.monotonic()

# ONE rule, TWO positions -- and the sentences differ by the clause that names the remedy: a budget
# gone before the hook could read anything is a WINDOW to raise, one spent while it was reading is a
# CALL to split. Without that clause the two positions were indistinguishable, and the test that
# claims to measure the watchdog would have stayed green on the synchronous check.
_OUT_OF_TIME = (
    "this call could not be inspected inside the time its registration allows: %s, this hook's "
    "whole budget is spent and the call is still not decided.\n"
    "A hook that is still deciding when the provider gives up is killed, and a killed hook is read "
    "as an allow -- so it refuses instead."
)
_BEFORE_READING = "before it had read anything at all"
_WHILE_READING = "while it was still reading"
_NO_WINDOW = (
    "this call could not be judged, because this hook cannot know how long it may take: %s/%s "
    "registers %s and no entry that names it states a `%s`.\n"
    "A hook that is still deciding when its window closes is killed, and a killed hook is read as "
    "an allow -- so a registration that leaves the window open is refused rather than raced."
)
_NO_WINDOW_REMEDY = ("give every entry that runs %s in %s/%s an explicit `%s` in seconds -- large "
                     "enough that this hook's own bound speaks first.")
_TOO_SHORT = (
    "this call could not be judged: the registration gives this hook %gs, which is not enough time "
    "for it to answer at all (%gs of every window is reserve, so that the refusal leaves this "
    "process before the kill arrives).\n"
    "A hook that is still deciding when its window closes is killed, and a killed hook is read as "
    "an allow -- so a window it cannot answer inside is refused rather than raced."
)
_TOO_SHORT_REMEDY = "raise the `%s` on this entry in %s/%s."

# ONE PROCESS ARMS ONCE. `_gate.py` runs a CHAIN of gates in one process and `_kernel.run_gate`
# arms explicitly on top of the arming `load()` does, so a second arming would hand the process a
# second budget counted from the same start -- harmless only for as long as nobody changes where
# the clock is read.
_ARMED = []


def hook_file():
    """The hook file this process is running, or None when this process is not a hook.

    THE PROPERTY, not a list: a hook process is one whose `__main__` is a file in THIS directory.
    That covers a direct run (`python .claude/hooks/gate_x.py`, which is how the suite and a person
    diagnosing one reach it) and a run through `_gate.py`, which installs the gate it is about to
    run as a real `__main__` module (its docstring says why it must). It excludes every other
    importer of this module -- a test process, the CLI -- and that exclusion is the point: the
    watchdog below ends the process it runs in, and a test process is not a hook process.
    """
    main = sys.modules.get("__main__")
    path = getattr(main, "__file__", None)
    if not path:
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    if os.path.dirname(os.path.abspath(path)) != here:
        return None
    return os.path.basename(path)


def registered_window(repo_root, name):
    """The seconds this project's registration gives the hook `name`: a number, None, or UNBOUND.

    THE SMALLEST NAMED WINDOW ANSWERS: one hook may be registered in several groups and any of them
    can be the one that is asked, so the shortest is the window it has to survive. Read off the file
    the provider reads rather than restated here -- a number copied into this module is the one that
    goes stale the day a registration is lowered.

    THREE ANSWERS AND NOT TWO, because "no number" covers two situations that must not share an
    outcome. A registration that NAMES this hook and states no window for it is an INCOMPLETE
    registration: that is the state 87 of 89 shipped entries were in until 2026-09-12, and it is
    also the state a hand edit reaches by deleting one key, so it is answered with None and refused
    by the caller. A registration that does not name this hook at all -- and an unreadable or absent
    settings file, which is the same thing for this purpose -- did not start this process, so no
    window of that file governs it: UNBOUND is the answer and the caller falls back on the
    provider's own default window. Refusing THAT case would refuse every hook run by hand and every
    hook a second provider's registration started (the Codex artifact is generated from this same
    file by `team-kits/gen_provider_artifacts.py`, so the windows travel, but the file that provider
    reads is not this one).

    WHAT THIS DOES NOT PROMISE is that the number read here is the one the provider really kills by:
    the file is read on every call, while the provider bound its own timeout when the session
    started, so the two are decoupled for as long as a session lasts. What is gained by reading the
    file anyway is the other direction -- a number copied into this module would be the one that
    goes stale silently.
    """
    path = os.path.join(repo_root or ".", PROVIDER_DIR, SETTINGS_FILE)
    try:
        with open(path, encoding="utf-8") as handle:
            settings = json.load(handle)
    except Exception:  # noqa: BLE001
        return UNBOUND
    stated = []
    for groups in (settings.get("hooks") or {}).values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            for hook in (group or {}).get("hooks") or []:
                command = str((hook or {}).get("command") or "")
                if name not in command:
                    continue
                stated.append((hook or {}).get(TIMEOUT_KEY))
    if not stated:
        return UNBOUND
    named = [float(value) for value in stated if value is not None]
    return min(named) if named else None


def start_the_deadline(name=None, refuse=None):
    """Refuse from a thread of its own once this hook's window is about to close.

    EVERY CALL HAS A WINDOW, whether or not the registration names one: a hook nothing in this file
    governs is killed by the provider's own default, measured and bracketed at
    `DEFAULT_WINDOW_SECONDS`. So a budget is derived either way, and being killed is never the
    outcome a hook plans for.

    FOUR ANSWERS, and they differ in WHEN the budget is found to be gone. A registration that names
    this hook without a window is refused before anything is read -- `registered_window` says which
    case that is and why it is not the same as an absent registration. A window this hook cannot
    answer inside at all -- at or under the reserve -- is refused outright rather than raced, with a
    sentence naming the file to change. A budget already spent by this process's own start is
    refused where it is noticed, not raced against the thread. A budget that runs out while the hook
    is reading ends the process with the same refusal code from the watchdog below, with a sentence
    naming the other remedy.

    THE BOUND SITS OUTSIDE THE DECISION, because the decision is where the cost is: a check written
    into one surface bounds that surface and nothing else. What it cannot interrupt is a single call
    into C that keeps the interpreter to itself; that half is not closed here.

    `refuse(message, remedy)` is how a caller with a richer refusal than `stop()` keeps it --
    `_kernel`, which writes an audit record and names the event first. The SENTENCES stay here
    either way, so two callers cannot grow two vocabularies for one rule.
    """
    if _ARMED:
        return
    name = name or hook_file()
    if not name:
        return
    _ARMED.append(name)

    def _refuse(message, remedy):
        if refuse is not None:
            refuse(message, remedy)
        stop("[team-kit %s] refused: %s\nRemedy: %s\n" % (name, message, remedy), "PreToolUse")

    window = registered_window(find_repo_root(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()),
                               name)
    if window is None:
        _refuse(_NO_WINDOW % (PROVIDER_DIR, SETTINGS_FILE, name, TIMEOUT_KEY),
                _NO_WINDOW_REMEDY % (name, PROVIDER_DIR, SETTINGS_FILE, TIMEOUT_KEY))
    if window == UNBOUND:
        window = DEFAULT_WINDOW_SECONDS
    if window <= DEADLINE_RESERVE_SECONDS:
        _refuse(_TOO_SHORT % (window, DEADLINE_RESERVE_SECONDS),
                _TOO_SHORT_REMEDY % (TIMEOUT_KEY, PROVIDER_DIR, SETTINGS_FILE))
    deadline = _STARTED_AT + max(window - DEADLINE_RESERVE_SECONDS, 0.0)
    if deadline - time.monotonic() <= 0:
        # ALREADY SPENT BEFORE THE DECISION BEGINS -- the imports this hook needs cost more than the
        # window leaves it. Answered HERE and not by the watchdog below, because the two would
        # otherwise race for a verdict that is already decided: the thread has to be scheduled, and
        # a hook that finishes its decision first would return an ALLOW under a window it could
        # never have honoured. Same sentence, so a reader cannot tell the two positions apart --
        # they are one rule.
        _refuse(_OUT_OF_TIME % _BEFORE_READING,
                "raise the `%s` on this entry in %s/%s -- the window is shorter than this hook's "
                "own start, so no call of it can ever be judged."
                % (TIMEOUT_KEY, PROVIDER_DIR, SETTINGS_FILE))

    def watch():
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                spent = _OUT_OF_TIME % _WHILE_READING
                with contextlib.suppress(BaseException):
                    import _audit
                    _audit.record(name, spent)
                with contextlib.suppress(BaseException):
                    sys.stderr.write("[team-kit %s] %s\nRemedy: split the call.\n" % (name, spent))
                    sys.stderr.flush()
                os._exit(2)
            time.sleep(min(left, 0.25))

    threading.Thread(target=watch, daemon=True).start()

_OVERFLOW_MESSAGE = (
    "[team-kit guard] Hook payload exceeded the %d-byte stdin bound, so this call could not be "
    "inspected — refused rather than waved through (spec II.4 bounded read + fail-closed).\n"
    "Remedy: split the call; a tool payload this large is never a normal delegation.\n"
)

_PATCH_FILE_RX = re.compile(r"(?m)^\*{3} (Add|Update|Delete) File: (.+?)\s*$")
_PATCH_MOVE_RX = re.compile(r"(?m)^\*{3} Move to: (.+?)\s*$")
# providers use different tool vocabularies — normalize the KNOWN aliases to the Claude names
# every guard filters on; unknown names pass through untouched (guards then fail open, by design).
_TOOL_ALIASES = {"edit": "Edit", "write": "Write", "bash": "Bash", "powershell": "PowerShell",
                 "str_replace": "Edit", "create_file": "Write", "shell": "Bash"}


# THE PAYLOAD THIS PROCESS IS DECIDING ON, remembered for `stop()`. A hook process reads stdin
# exactly once, so "the payload" is a property of the process rather than of a call, and the
# alternative — threading the command through `_kernel.block` into every one of the eight gates —
# is the same nine-call-site thread that `_ESCAPE_CHARS` documents someone forgetting. Cleared at
# the START of every load so an in-process consumer (a test, the CLI) can never be handed the
# previous payload's command.
_LAST_PAYLOAD = []

# THE PROCESS'S STDIN, REMEMBERED AS BYTES — because one process may now hold SEVERAL gates.
# `_gate.py` runs a CHAIN when the registration names more than one gate (see its docstring for
# why the chain exists at all: a gate that CONSUMES state must not decide before every other
# refusal reason for the same call is known). Every gate in that chain reads "the payload", and a
# pipe can only be drained once, so the second one used to get b"" -> {} -> "could not be
# inspected". Caching the RAW BYTES rather than the parsed dict is deliberate: `load()` normalizes
# and its callers mutate what they get (`tool_input`, `_file_paths`), so handing out one shared
# dict would let gate 1 change what gate 2 decides on.
#
# ONLY for the process's own stdin (`stream is None`). An explicit stream is a caller handing over
# a payload it already has — a test, the CLI — and must neither fill nor read this.
_STDIN_BYTES = []


def forget_stdin():
    """Drop the remembered stdin (see `_STDIN_BYTES`) — for in-process consumers only.

    Hook processes are one-shot, so the cache is invisible to them. A test or a long-lived CLI
    that feeds stdin twice would otherwise be answered with the first payload forever;
    `_kernel.reset_payload()` calls this so there is ONE thing to forget rather than two.
    """
    del _STDIN_BYTES[:]


def last_command():
    """The shell command of the payload this process read, or "" — see `_LAST_PAYLOAD`."""
    data = _LAST_PAYLOAD[0] if _LAST_PAYLOAD else {}
    return str((data.get("tool_input") or {}).get("command") or "")


def last_tool():
    """The tool name of the payload this process read, or "" — see `_LAST_PAYLOAD`.

    The same move `last_command` makes, for the same reason and with the same limit: WHICH SHELL
    will run a command line decides how the line is read (`_CONTINUATION_BY_TOOL`), and threading
    that answer down would be the nine-call-site thread `_ESCAPE_CHARS` documents someone
    forgetting. A caller that HAS the payload should still pass its tool explicitly; this is the
    floor under the ones that do not.
    """
    data = _LAST_PAYLOAD[0] if _LAST_PAYLOAD else {}
    return str(data.get("tool_name") or "")


def gated_shell(tool=None):
    """The gated shell tool a command text will run under — the caller's word, else the payload's.

    Normalised through `_TOOL_ALIASES`, so a provider that spells the tool in lower case does not
    silently fall out of every per-shell rule and into the union.
    """
    name = str(tool or last_tool() or "")
    return _TOOL_ALIASES.get(name.lower(), name)


def load(stream=None, limit=None, tolerate_overflow=False):
    """Read + normalize the hook payload from stdin. Returns {} on garbage.

    stdin is read as BYTES and decoded UTF-8: providers send raw UTF-8, but Windows text-mode
    stdin decodes cp1252 — an audit proved non-ASCII payload content (umlauts in question text,
    German file paths) arrived as mojibake and pattern matches silently missed.

    The read is BOUNDED at `limit` bytes, defaulting to STDIN_LIMIT (spec II.4). Beyond it this
    EXITS 2 with a block message — see STDIN_LIMIT for why that is the default rather than a
    return value. Comfort hooks pass tolerate_overflow=True and get the `_stdin_overflow`
    sentinel instead. The limit default is resolved HERE, not in the signature, so the
    module-level cap stays adjustable at runtime (tests, tuning).

    The process's OWN stdin is read once and remembered (`_STDIN_BYTES`), so every gate of a
    chained registration decides on the same bytes; an explicit `stream` bypasses that entirely."""
    # THE ARMING POINT of the deadline above, and the reason it is HERE: every shipped hook of
    # every kit calls this (measured 2026-09-12 over all three kits' `hooks/*.py`), so a hook
    # cannot read its payload without a bound on how long it may take to answer. `hook_file`
    # decides whether this process is a hook at all, so an in-process caller (a test, the CLI)
    # arms nothing.
    start_the_deadline()
    limit = STDIN_LIMIT if limit is None else limit
    del _LAST_PAYLOAD[:]
    raw = None
    if stream is None and _STDIN_BYTES:
        raw = _STDIN_BYTES[0]          # already drained by an earlier gate in this process
    else:
        try:
            source = stream if stream is not None else sys.stdin
            buffer = getattr(source, "buffer", None)
            if stream is None and buffer is not None:
                raw = buffer.read(limit + 1)
            else:
                # text stream (tests): read(n) counts CHARACTERS, so the encoded result may exceed
                # the cap slightly — the overflow check below is on bytes and errs toward blocking
                raw = source.read(limit + 1)
                if isinstance(raw, str):
                    raw = raw.encode("utf-8", "replace")
        except Exception:
            return {}
        if stream is None and raw is not None:
            _STDIN_BYTES.append(raw)
    if raw is None:
        return {}
    if len(raw) > limit:
        if not tolerate_overflow:
            # through `stop()` like every other refusal, so the reference pointer is not something
            # this one path is exempt from: an oversized payload is the refusal a role is LEAST
            # equipped to read, because the gate never got to say what it was judging
            stop(_OVERFLOW_MESSAGE % limit, "PreToolUse")
        return {"_stdin_overflow": True, "tool_input": {}}
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
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
    _LAST_PAYLOAD.append(data)
    return data


def file_paths(data):
    """Every file this tool call touches (list of str; may be empty). Path guards MUST iterate
    this instead of reading tool_input.file_path once — a Codex multi-file patch is one call."""
    if isinstance(data.get("_file_paths"), list) and data["_file_paths"]:
        return [str(p) for p in data["_file_paths"]]
    ti = data.get("tool_input") or {}
    # notebook_path: NotebookEdit is a file write like any other, and a guard that does not see it
    # scopes everything except notebooks
    p = ti.get("file_path") or ti.get("path") or ti.get("notebook_path") or ""
    return [str(p)] if p else []


# The fields by which a hook payload names the agent the call came FROM, and — the half that was
# missing — whether the LEAD can legitimately appear in one. A PROPERTY of the caller, not a list
# of the roles that are subordinate: a role list is 24 entries per kit that every new specialist
# file has to be added to, and it says nothing on a provider whose role names differ.
#
# The two fields answer DIFFERENT questions, which is why one carries an exemption and the other
# must not:
#   * `agent_id` identifies the SPAWN INSTANCE. The session instance is not a spawn, so it has no
#     id to carry — any value here is a subagent whatever it spells, and a forged name buys
#     nothing.
#   * `agent_type` is the caller's ROLE, and the lead HAS a role: the one `settings.json` binds as
#     `agent:`. A role equal to that binding is the lead naming itself, not a subordinate.
_CALLER_FIELDS = (("agent_id", False), ("agent_type", True))

def session_lead(start=None):
    """The role this project binds as its SESSION agent, or "" when that cannot be read.

    ASKED OF THE PROJECT, never of a default: the three kits bind three different roles
    (`project-manager`, `office-manager`), and a hook that carried its own answer would be right
    for the kit it was written in and wrong for the next one. `settings.json` `agent:` is the one
    place the binding exists — it is what makes the provider start the session AS that role.

    "" means UNKNOWN, and every caller must treat it as "no role is the lead here" rather than as a
    guess. That is the direction the callers already fail in, and it is close to unreachable in a
    scaffolded project: `.claude/settings.json`, read below, is the same file that registers the
    hook doing the reading. The two segments are spelled INTO the call rather than held in a
    module constant, because a tuple of literals splatted into a `join` is what
    `test_the_hooks_that_name_a_typed_directory_spell_it_as_the_kernel_does` reads as a path into
    the KERNEL's typed tree — and this one is not that.
    """
    try:
        root = find_repo_root(start or None)
        with open(os.path.join(root, ".claude", "settings.json"), encoding="utf-8") as handle:
            return str(json.load(handle).get("agent") or "").strip()
    except Exception:  # noqa: BLE001 — unreadable settings means UNKNOWN, not a guess
        return ""


def calling_subagent(data):
    """The agent this call came from, or "" for the SESSION INSTANCE (the lead, or a bare session).

    THE DEFINITION IS "NAMES SOMEONE ELSE", NOT "NAMES SOMEONE". Until 2026-08-04 this returned any
    agent name the payload carried, on a measurement taken in a scratch project that bound no
    session agent at all — so "the session instance's payload carries neither field" was a property
    of that FIXTURE. Every scaffolded project binds one (`settings.json` `agent:`), and there the
    session instance's own `PreToolUse` payload carries `agent_type` = that role. Measured in a
    probe project with a bound `agent:`, dumping the raw payload: the lead's Bash call arrived with
    `agent_id` absent and `agent_type` equal to the bound role, so the lead was read as its own
    subagent and `create-task`, `dispatch` and every spawn were refused in every scaffolded
    project. Recorded with its provenance in `tools/provider_observations.json` -> `agent_identity`.

    So the question is whether the payload names an agent OTHER than the bound lead. `_CALLER_FIELDS`
    carries which field can name the lead at all and why; `session_lead` carries where the binding
    is read from.

    TRUTHINESS, NOT KEY PRESENCE, and that is still half the safety of this predicate. The parent
    payload has been seen in BOTH empty shapes -- keys absent and present as null
    (`PostToolUse(Agent).agent_id: null`, spike S3, docs/reviews/evidence/2026-07-24-spike-payloads.md).
    A membership test on the keys would read the second shape as a subagent, and every caller that
    refuses on a subagent would then refuse the LEAD.

    EITHER field is enough to name a subagent: a provider that dropped one while keeping the other
    must not silently hand the subordinate role back its freedom. Codex supplies both, so the
    definition is provider-neutral even where a given hook is not registered.

    WHAT THE EXEMPTION COSTS, named rather than implied: a subagent whose `agent_type` equals the
    bound lead role AND whose payload carries no `agent_id` reads as the lead here. Nothing in this
    file prevents that shape — what stands against it is that a real subagent carries `agent_id`
    (measured, same record), that `guard_agent_spawn` refuses `subagent_type == the bound lead` and
    that the shipped `settings.json` denies `Agent(<lead>)`. If a provider stopped sending
    `agent_id`, spawning the lead role would become the way past this predicate.

    NOT a replacement for `guard_pm_scope`'s own `data.get("agent_id")` test, which asks the
    MIRRORED question ("is this the lead, whom I gate?") and therefore has to fail in the opposite
    direction. Widening that one would make it SKIP more calls; widening this one makes its callers
    REFUSE more. One field, two questions, two failure directions -- merging them would break one.
    """
    lead = session_lead(str(data.get("cwd") or ""))
    for field, may_name_the_lead in _CALLER_FIELDS:
        value = data.get(field)
        if value is None:
            continue
        name = str(value).strip()
        if not name:
            continue
        if may_name_the_lead and lead and name.lower() == lead.lower():
            continue  # the lead naming its own role -- see `_CALLER_FIELDS`
        return name
    return ""


def created_file_paths(data):
    """Paths newly created by apply_patch (`Add File` or a `Move to` destination)."""
    operations = data.get("_file_operations")
    if isinstance(operations, list):
        return [str(item.get("path")) for item in operations
                if isinstance(item, dict) and item.get("operation") in ("Add", "Move")
                and item.get("path")]
    return file_paths(data) if data.get("tool_name") == "Write" else []


# Shared push/merge detection for every git gate (single home — six hook-local copies drifted:
# an audit had to fix the same regression twice). A shell WRAPPER's quoted payload is not an
# argument, it is CODE one level down (`bash -c "git push"` must gate), so it is lifted out of its
# quotes before any reader below sees it. The MEMBERSHIP TEST is that property and not a name:
# "this program is handed a string and hands it straight to a command parser". `eval "git push"`
# does exactly what `sh -c` does; `Invoke-Expression`/`iex` is that same eval for PowerShell —
# which this kit gates as its own tool (`SHELL_TOOLS`), so leaving it out was leaving out one of
# the two shells actually being enforced (measured: `iex "git push --force origin main"` matched
# none of the eight PreToolUse hooks).
#
# HOW the string is handed over is not part of the membership test, so each spelling of the
# handover gets its own reader rather than its own rule: as the ARGUMENT after the c-flag
# (`_WRAPPER_RX`), through a PIPE (`echo "git push --force" | sh` — `_lift_piped_payloads`), or as
# STANDARD INPUT via a here-string (`bash <<< 'git push --force origin main'` — `_HERESTRING_RX`;
# measured as a real push that reached NONE of the eight hooks, because the redirection rule in
# `_argument_scan` is right that a redirection's target never reaches the program and here the
# target IS the code). They are all here because the shell-WORD rule in `git_invocations` would
# otherwise read those payloads as the text they syntactically are. The c-flag may sit in a
# COMBINED short cluster (`bash -lc`, `-xec` — audit: `-lc` bypassed every gate), an option in
# front of it may carry a VALUE either attached after a colon or as the next word (`cmd /v:on /c`,
# `powershell -ExecutionPolicy Bypass -Command` — both measured below), and quoted payloads may
# contain ESCAPED quotes.
#
# A payload that is ITSELF a wrapper is lifted AGAIN — `unwrap_shell_payload` iterates to a
# fixpoint. `bash -c "eval 'git push --force origin main'"` pushes in a real bash 5.2 and measured
# ALL EIGHT hooks ALLOW, as did `bash -c "bash -c '…'"`, `eval "eval '…'"`, `bash -c "sh -c '…'"`
# and the three-deep spelling: the membership test held twice over, and only the outer
# substitution ran. What the shell will execute is written out in the text there, which is exactly
# what separates it from the holes below.
#
# The list below is therefore an inventory of the programs KNOWN to have that property, not the
# definition of it, and an inventory is only ever as complete as the last review. Anything that
# executes text WITHOUT handing it to a parser as one span of THIS text is out of reach of this
# shape entirely, and those are named as holes rather than implied to be covered.
#
# KNOWN HOLES, named rather than implied (a comment must not promise protection the code does not
# implement), each measured as reaching no gate:
#   * a stage that TRANSFORMS or TRANSPORTS the text between its quotes and the shell:
#     `echo "git push --force" | tr a-z A-Z | sh`, a file written and then sourced, and a HEREDOC
#     (`sh <<EOF … EOF`), whose payload is not a quoted span at all but the lines that follow —
#     the newline splits the segment and the payload is then read as its own line, which is why a
#     shell-fed body reaches the gates at all. `literal_heredoc_free` keeps that incidental reach
#     (measured: `sh <<'EOF' … git push --force … EOF` is refused by gate_git and gate_push_token,
#     before and after it shipped) and removes only the bodies nothing parses.
#     The here-STRING above is the opposite case and is closed.
#   * an ENCODED payload: `powershell -EncodedCommand <base64>` carries the same code with no
#     quoted span to lift. ANSI-C encoding (`$'\x67…'`) is the same shape one level down and it
#     survives the lift, because nothing in this file decodes it (`_argument_scan`). It reaches
#     BOTH halves of the reading, and only one of them is closed:
#       - the PROGRAM NAME is open: `bash -c $'\x67it push --force origin main'` pushes for real
#         and reaches none of the eight hooks. After lifting, the text spells `\x67it`, and
#         `_GIT_WORD_RX` looks for the letters `git` — there is no `git` word to find, in either
#         reading, so no invocation exists to be called unresolved.
#       - the VERB was open in the same shape and is closed: `bash -c $'bash -c \'git \x70ush
#         --force\''` ran a real push past all eight hooks. The mechanism is worth writing down
#         because it is not "the reader cannot decode": the OUTER lift leaves the inner wrapper's
#         quotes ESCAPED (`\'`), the fixpoint therefore stopped after one round, and the two
#         readings then blinded each other — the POSIX one ate the payload's backslashes and
#         resolved the harmless verb `x70ush`, the PowerShell one kept them and so read `\'…\'`
#         as a real quote pair, inside which `git` ends no word. `_QUOTED_SPAN` starting at an
#         escaped delimiter is what closed it; the same five lines with a LITERAL verb were open
#         before the fixpoint existed and are closed by it.
#     Resolving an encoded verb rather than widening it needs a decoder this file deliberately
#     does not have, so the program-name half stays open and is named here rather than implied.
#   * a cmd VARIABLE REFERENCE whose name or modifier contains a SPACE. `_CMD_VARIABLE_RX` reads
#     a reference as one token, and after the `cmd /c "…"` payload is lifted its spaces are real
#     word breaks, so such a reference is two tokens and the verb token holds only the first half
#     — which matches no reference form and therefore comes back RESOLVED and harmless. Measured
#     at the reader: `cmd /v:on /c "git !V: =u! …"` reads the verb `!v:` (resolved), and
#     `cmd /v:on /c "git !V A! …"` reads `!v`, while the same lines without the space
#     (`!V:X=u!`, `!V!`) are unresolved and refused by three gates.
#     THE BOUNDARY THAT CAUSES IT IS THE ONE THAT PAYS FOR ITSELF: excluding whitespace from a
#     reference's content is exactly what keeps fourteen lines of ordinary prose out of the gates
#     (`echo "I love git!"`, `echo "git! and git!"`), so widening it here would trade a
#     constructed line for lines people write daily.
#     AND THE RUNNABLE LINE HAS TWO WAYS PAST THE GATES RATHER THAN ONE WITH AN EXTRA HURDLE.
#     Defining a variable whose NAME holds a space needs `set "V A=push"`, i.e. a double quote
#     inside the double-quoted `/c` payload, so the whole line reads
#     `cmd /v:on /c "set "V A=push"& git !V A! --force origin main"`. An earlier wording filed
#     that nesting under "it also needs more setting up", which reads as difficulty for the
#     attacker and hides the second hole. Measured, it is one: the line is a REAL
#     `git push --force` in cmd.exe (`/c` strips only the first and the last quote when the
#     payload holds more than two, so the inner pair survives; verified by running the same line
#     with `status` in place of `push` — it printed `## No commits yet on master`), and it reached
#     NONE of the eight PreToolUse hooks. The two ways are independent:
#       - THE READER, which is the hole named above and would decide if the payload were lifted
#         whole: the reference is two tokens, the verb token is `!v`, that matches no reference
#         form, and it comes back RESOLVED and harmless (measured on
#         `cmd /v:on /c "git !V A! --force origin main"`).
#       - THE LIFT, which is what actually happens here and never reaches that reader at all.
#         `_QUOTED_SPAN` ends at the FIRST unescaped closing quote, so `_WRAPPER_RX` matches
#         `cmd /v:on /c "set "` and lifts the span `set `. The remainder
#         `V A=push"& git !V A! --force origin main"` is left with its quotes unbalanced, the
#         `git` therefore sits INSIDE a quoted span, and quoted whitespace is `\x00` in the word
#         view — so `_ends_word` says no, `_read_invocations` skips it, and `git_invocations`
#         returns an EMPTY list. Not an unresolved invocation that every gate would refuse: no
#         invocation at all. Closing the reader half alone would leave this line exactly where it
#         is. (Without the nesting, `cmd /v:on /c "set V=push& git !V! --force origin main"` lifts
#         cleanly and reads the unresolved verb `!v!`; measured in a scaffolded project, five of
#         the eight refuse it, and the three that refuse it FOR the invocation are gate_git,
#         gate_push_token and gate_shell_hygiene — the other two are state-completeness gates
#         that apply because a push was recognised at all.)
#   * a payload passed as an ARGUMENT VECTOR rather than as one string:
#     `Start-Process git -ArgumentList "push","--force"`.
#   * INDIRECTION through a name the text does not resolve: `alias gp='git push --force'; gp`,
#     `G=git; $G push`.
_SHELL_NAMES = r"(?:bash|sh|zsh|dash|pwsh|powershell|cmd)(?:\.exe)?"
_EVAL_NAMES = r"(?:eval|iex|invoke-expression)"
# A quoted span, optionally carrying the `$` of ANSI-C/locale quoting. The `$` sits OUTSIDE both
# capture groups so the group numbers its users below index by stay what they are. Without it
# the wrapper chain broke on one character: `_WRAPPER_RX` wants the span directly after `-c `, the
# `$` of `bash -c $'git push --force origin main'` stopped the match, the payload was never lifted,
# and — because `$'…'` then reads as ONE word — the `git` inside it ended no word either, so that
# line reached NO gate at all (measured; `eval $'…'` likewise). `$'…'` being quoting rather than
# expansion is stated 250 lines down in `_argument_scan` and was not known here.
#
# THE DELIMITERS MAY THEMSELVES BE ESCAPED, and that is the second round of the fixpoint being
# able to happen at all. Lifting `bash -c $'bash -c \'git push\''` leaves the INNER wrapper's
# quotes standing as `\'`, a span pattern that only starts at a bare quote finds nothing, and the
# fixpoint stops one level too early — measured, five lines of that shape ran a real push/reset/
# merge and reached NONE of the eight hooks. Only the delimiters learn the backslash; the BODY
# stays the unrolled `(?:\\.|[^"\\])*` loop, whose two alternatives cannot both match the same
# character. That is not tidiness: an ambiguous body is the shape that made `_WRAPPER_OPTION`
# exponential, and the first cut of this fix had it. Measured unambiguous: 3200 escaped spans
# (19 KB) cost 0.003 s and the whole unwrap stays linear.
#
# KNOWN IMPRECISION, and it has ONE shape: a payload whose content ENDS in a backslash, directly
# before the closing quote. There the optional backslash of the closing delimiter eats a character
# that belonged to the text, and the PATH-reading callers of `git_argument_text` see the payload
# one backslash short. Measured over twelve over-match candidates, TWO read differently than they
# did before, both of that shape:
#     bash -c "cd C:\src\" ; git push --force origin main      -> lifts `cd C:\src`
#     powershell -Command "Get-ChildItem C:\src\"              -> lifts `Get-ChildItem C:\src`
# The two are not the same case, which is why "unbalanced quotes only" would be wrong: in a POSIX
# shell that backslash really does escape the closing quote, so the first line is unrunnable to
# begin with; in PowerShell it does not, so the second is an ordinary command and the trailing
# separator of a DIRECTORY path is what is lost. Ten real path cases — `echo x >
# "project_memory/a.yaml"`, `mv inbox/a.pdf "archive/2026/Müller GmbH.pdf"`, `sed 's/\\/\//g'`,
# `echo "he said \"hi\""` and the like — are unchanged, and the GIT reading of both lines above is
# unaffected (the push in the first is still detected). Named here rather than fixed: the fix is a
# quote balancer, and the cost is a trailing separator on a directory path, which every prefix
# check in this kit already treats as the same directory.
_QUOTED_SPAN = r'\$?(\\?"((?:\\.|[^"\\])*)\\?"|\\?\'((?:\\.|[^\'\\])*)\\?\')'
# The options a wrapper may carry BEFORE its c-flag, and an option is not just a `-word`: it can
# carry a VALUE, and the two spellings of that were two separate measured bypasses.
#   * ATTACHED after a colon — `cmd /v:on /c "…"`. With `[\w-]` the `:` ended the option token,
#     `/v:on` matched neither this group nor the c-flag alternative, and the payload of
#     `cmd /v:on /c "set V=push& git !V! --force origin main"` was never lifted: a real push
#     (measured through the PowerShell tool) reaching NONE of the eight hooks.
#   * SEPARATE, as the next word — `powershell -ExecutionPolicy Bypass -Command "…"`, the ordinary
#     Windows spelling. `Bypass` starts with no dash, so the option group could not consume it and
#     the c-flag alternative had to match there and failed; measured, that line pushes for real and
#     reached none of the eight hooks, as did `bash -O extglob -c "…"` and `sh -o pipefail -c "…"`.
# The value is spelled as "one word that starts with neither a dash, a slash nor a quote", so a
# payload can never be mistaken for it, and the regex backtracks into the c-flag when the last
# option IS the c-flag (`bash -lc "…"` still matches on the shortest reading).
#
# EVERY PIECE OF THIS IS UNAMBIGUOUS ON PURPOSE, and that is not style — it is the difference
# between linear and exponential. The character after the leading dashes may NOT be a dash, or
# `--no-cache` parses two ways (`--` + `no-cache`, `-` + `-no-cache`); a value may not begin with
# a dash or a slash, or a token could be either the previous option's value or the next option.
# Each ambiguity doubles the work per option when the overall match FAILS, and the pattern this
# replaces had the first one. Measured on `echo bash --a-b×N ; git push --force origin main`,
# medians of three: 0.020 s at 14 options, 0.270 s at 18, 4.011 s at 22, 65.550 s at 26 — a
# factor of ~15 per four options: 26 words buy a minute in which this reader answers nothing, 30
# would buy a quarter of an hour, and past the window the provider does kill at (measured near
# 600 s -- `HOOK_DEADLINE_SECONDS`) the line is not slow but ALLOWED, because a killed hook is a
# pass. So the length of a command line decided first how long the session froze and then whether
# it was checked at all; neither is an outcome a word count may choose. Unambiguous, the same
# input costs 0.0000 s at 26 options and 0.0009 s at four thousand.
_WRAPPER_OPTION = r'[-/]{1,2}[\w:.][\w:.-]*(?:\s+[^\s"\'/-][^\s"\']*)?\s+'
_WRAPPER_RX = re.compile(
    r'((?:' + _SHELL_NAMES + r'\s+(?:' + _WRAPPER_OPTION + r')*'
    r'[-/]{1,2}(?:[A-Za-z]*c|command)|\b' + _EVAL_NAMES + r'\b)\s+)' + _QUOTED_SPAN,
    re.IGNORECASE | re.DOTALL)
# THE SHELL'S OWN WAY OF RUNNING A FILE WITHOUT NAMING A SHELL: `source x` and `. x` read the file
# into the CURRENT shell and execute it. They are not programs, they are builtins, so no list of
# program names can hold them -- and both were measured ALLOWED for
# `cat <<'EOF' > run.sh … EOF ; . run.sh` in two pilots while the same line with `bash run.sh` was
# refused (verifier round 1, F1; the real shell wrote AND executed, `proof_dot.txt`).
_DOT_SOURCE_NAMES = r"(?:source|\.)"
_RUNS_A_FILE_RX = re.compile(r"^(?:%s|%s)$" % (_SHELL_NAMES, _DOT_SOURCE_NAMES), re.IGNORECASE)


def runs_the_file_it_is_handed(word):
    """Would this word EXECUTE a file handed to it as an operand?

    ONE VOCABULARY, HERE, because three readers ask it: `_names_a_stdin_parser` (a body fed to a
    parser is a command, not prose), `_PIPE_TO_SHELL_RX` (a payload piped into one), and
    `gate_write_scope`'s rule that a line must not write a script and run it in the same call
    (BUG-0298/H214). The property is "what follows is a PROGRAM, not data": a shell by any of its
    names, and the dot-source builtins, which are the same act without a program at all.

    WHAT IT DELIBERATELY DOES NOT CLAIM: that these are the only ways a file gets executed. An
    interpreter (`python`, `node`, `perl`) runs a file too, and a caller of THIS reader treats those
    as the H11 remainder rather than pretending to a list nobody can finish -- the bound is that
    such a line names the file twice and stands in the transcript. Adding them here would be the
    enumeration this repository keeps finding the next defect in; what the callers CAN do is say so,
    and `gate_write_scope._refuse_a_script_this_line_writes_and_runs` does.
    """
    return bool(_RUNS_A_FILE_RX.match(str(word or "").strip()))


_PIPE_TO_SHELL_RX = re.compile(r'\s*\|\s*' + _SHELL_NAMES + r'\b', re.IGNORECASE)
# A HERE-STRING hands the shell its COMMANDS on standard input. Same membership test, third way of
# handing over — and the one the rest of this file actively deletes rather than merely fails to
# see: `_argument_scan` drops a redirection operator together with its target, correctly (a target
# never reaches the program), which for `bash <<< 'git push --force origin main'` drops the code.
# Group numbering matches `_WRAPPER_RX` (prefix, span, double, single) so both share one lift.
_HERESTRING_RX = re.compile(
    r'((?<![\w.-])' + _SHELL_NAMES + r'\s+(?:' + _WRAPPER_OPTION + r')*)<<<[ \t]*' + _QUOTED_SPAN,
    re.IGNORECASE | re.DOTALL)

# A line CONTINUATION is not a line END — and it is not a SPACE either. The shell removes
# `\`+newline (PowerShell: backtick+newline) with NOTHING in its place, before it parses anything,
# so `git pu\<newline>sh` is the single word `push` and `git \<newline>  merge x` is one invocation
# of git. Joining with a space got the second case right and the first one wrong, which is not a
# cosmetic difference: `git push --f\<newline>orce origin main` measured ALLOW with the force-push
# ban loaded and blind, and `git mer\<newline>ge feat/PR-0002-x` matched no git gate at all. Every
# reader below decides "which part of this line is this command" with a pattern that stops at a
# newline — correctly, an unescaped newline really does end a command — so the continuation has to
# be resolved before that pattern ever runs.
#
# WHICH character continues, and WHICH break it continues over, are properties of the SHELL, so
# the union below is only what a reader that does not know its shell may use. Both halves measured
# 2026-08-24 against a real `bash.exe` and a real `powershell.exe`, by asking whether
# `echo one<PAIR>echo two` ran ONE command or two:
#
#   pair            bash                            PowerShell
#   `\` + LF        continues                       does NOT — prints `one\`, then `two`
#   `\` + CRLF      continues (the CR is gone       does NOT
#                   before bash parses, below)
#   backtick + LF   opens a substitution, error     continues — the LF is escaped, one command
#   backtick + CRLF error                           does NOT — the backtick escapes the CR and the
#                                                   LF still ends the statement
#
# The union therefore REMOVES a break the named shell honours, and that is a hole rather than a
# nicety: with `tool_name: PowerShell`, `Get-Content README.md \<LF>Set-Content -Path
# .claude/settings.json -Value POISONED` was gate rc 0, `powershell.exe` rc 0 and the file — the one
# the provider reads to learn WHICH hooks run — overwritten, measured with a file witness in the dev
# and office kits. `\`+CRLF the same. Which entries exist is pinned to the tools the gates are
# registered on, from both ends
# (`tools/test_hooks_v2.py::test_every_gated_shell_tool_has_its_own_continuation_rule`).
_CONTINUATION_BY_TOOL = {"Bash": re.compile(r"\\\r?\n"), "PowerShell": re.compile("`\n")}
# The union — the answer for a text whose shell is not one of the two gated ones. NOT the empty
# pattern, because leaving a continuation standing is a hole of its own: without the join
# `echo x >> led\<newline>ger/x.csv` split at the newline and its target was lost (measured rc 0).
#
# WHO ENDS UP HERE, corrected twice and now measured in both directions. It is wider than "outside
# the kits": EVERY payload whose tool is not `Bash` or `PowerShell` takes this branch — `Edit`,
# `Write`, `Task`, a provider's `apply_patch` — plus a process that read no payload at all, which
# today means a test or the CLI. Without consequence, because such a payload carries no `command`
# for these readers to prepare.
# `.claude/hooks/_harness.py` IS NOT ONE OF THEM, and listing it here was the over-alarming half of
# the same mistake — a sentence that gave this repo's own enforcement a weakness it does not have.
# It calls with one argument, but it reads its payload through `load()` in this module, so
# `gated_shell()` answers with the real tool and those gates take the per-shell branch. Measured as
# real gate processes against `project_memory/decisions/active/DEC-0001.yaml`: with `PowerShell`,
# two statements rc 2 and `\`+LF rc 2 while the backtick continuation is rc 0; with `Bash` the
# mirror image, backtick rc 2 and `\`+LF rc 0.
_CONTINUATION_RX = re.compile(r"[\\`]\r?\n")

# WHERE A STATEMENT ENDS — asked of the SHELLS, over the whole class a line break could be spelled
# in, rather than assumed to be the one character everybody types. Probed 2026-08-24 against a real
# `bash.exe` and a real `powershell.exe` with `echo one<CH>echo two`, judged on the RAW bytes by
# whether the second `echo` ran as a command: of every C0 control character, DEL, U+0085, U+2028 and
# U+2029, exactly LF (both shells) and CR (PowerShell only) end a statement. Everything else in that
# class is an ordinary character or mere WORD separation — a tab, U+000B, U+000C, U+0085, U+2028 and
# U+2029 all leave the second `echo` standing in the output as an ARGUMENT, which is the reading
# that makes them look like separators from the outside and is what a first, line-based probe of the
# same question got wrong.
# A character ONE gated shell honours is honoured here, because `tool_name` is the caller's choice:
# a CR was ordinary whitespace to `shlex` and a statement end to PowerShell, so a write to
# `.claude/settings.json` behind one rode into the view of the harmless verb in front of it and all
# three kits answered rc 0 (BUG-0066, measured end to end: gate rc 0, powershell rc 0, file
# poisoned). `\r\n` stays ONE break rather than becoming two.
_STATEMENT_BREAK_RX = re.compile(r"\r\n?")

# WHAT ENDS A SHELL WORD **IN LITERAL TEXT** — and that qualifier is the whole of what the
# previous version of this comment got wrong. Outside a quoted span a word ends at whitespace or at
# a METACHARACTER, and the shell's metacharacters are exactly `| & ; ( ) < > space tab newline` —
# POSIX XCU 2.2, and cmd/PowerShell add none that matter here. Writing the set down closed a real
# hole: `_argument_scan` used to answer for `& | ; ( )` and not for `< >`, and a redirection
# therefore glued itself to the verb — `git push>/dev/null --force origin main` read as the
# subcommand `push>/dev/null`, which is no git command at all, so ALL EIGHT PreToolUse hooks stood
# down on a force-push (measured).
#
# What it then CLAIMED — "there is no eleventh one to discover later" — was false in a way the set
# itself cannot fix, and it cost the layer a class HEAD still held. Word splitting happens AFTER
# expansion (POSIX XCU 2.6.5), so a closed set of characters answers "where does this word end"
# only for text that is already the word. `git${IFS}push --force origin main` runs a force-push in
# a real bash 5.2; the character after `git` is `$`, which is in no metacharacter set, so `git`
# ended no word, the line held no git invocation, and all eight hooks stood down — worse than the
# spelling-based reader this definition replaced. `git$IFS push` and `git{,} push` are the same
# shape. See `_UNDETERMINED_BREAK_RX`: where an expansion begins, the text does not SAY how many
# words come out, and an integrity layer that must be fail-closed (spec II.4) reads "unknown" as
# "possibly a word end", not as "not one".
#
# The set splits three ways by what each member does BEYOND ending the word, and `_argument_scan`
# answers all three:
#   * `& | ; newline` end the COMMAND as well — `_SYNTAX_CHARS`, and `_SEGMENT_SPLIT_RX` cuts there.
#   * `( )` open and close a command context; they belong to no word.
#   * `< >` introduce a REDIRECTION, which takes the following word with it: neither the operator
#     nor its target was ever handed to the program (`git push origin main >/dev/null 2>&1` pushes
#     `origin main`, nothing else).
# `#` is not a metacharacter — it does not end a word, it opens a comment at the start of one.
#
# Inside a quoted span none of them carry any of that meaning — the span is one argument — which is
# why `_argument_scan` neutralises the command separators there instead of passing them on into a
# text that will be split on them.
_SYNTAX_CHARS = "&|;#\n\r"
_SYNTAX_TO_SPACE = {ord(char): " " for char in _SYNTAX_CHARS}
# ...and the whitespace that, INSIDE a quoted span, is not a word break. See `_argument_scan` for
# the parallel "word view" this builds and why a word boundary has to be a separate answer from
# the text itself.
_QUOTED_WHITESPACE_TO_FILLER = {ord(char): "\x00" for char in " \t\n\r\v\f"}


def _lifted_payload(double, single):
    """The content of a wrapper's quoted span, as code the readers below can scan.

    Handed on VERBATIM, and that is a decision rather than an omission. A quoted span's
    BACKSLASHES do change meaning by being lifted, and in both directions:

      * out of a SINGLE-quoted span they become escapes that were not escapes —
        `bash -c 'git pu\\sh --force'` hands git `pu\\sh`, which is no push, while the POSIX
        reading of the lifted text consumes the `\\` and reads `push`. That is an over-trigger,
        i.e. the fail-CLOSED direction, and it costs one refusal on a line nobody writes.
      * out of an ANSI-C span (`$'…'`) they become escapes that bash itself would have decoded
        differently — `bash -c $'git \\x70ush --force'` really pushes, and the POSIX reading of
        the lifted text consumes the `\\` and reads the RESOLVED verb `x70ush` (the escape eats
        exactly one character, the `x`), which no gate asks about. That is the fail-OPEN
        direction, so something has to carry it.

    FOR A ONE-STAGE PAYLOAD, what carries it is the SECOND reading and not a repair here — and
    that qualifier is load-bearing, see below. `_scan_views` produces a PowerShell reading of every
    command containing a backslash, and a payload with a backslash puts one in the command by
    definition; in that reading nothing consumes a backslash, so the verb comes back as
    `\\x70ush`, which `_UNDETERMINED_VALUE_RX` reads as a token the text does not fix. An earlier
    cut doubled the backslash here to force that answer out of the FIRST reading as well;
    measured over all eight single-stage ANSI-C spellings and both readings, it changed no gate's
    verdict on any of them, because the second reading had already answered — and it made one of
    the two readings spell something no shell would produce, which the PATH-reading callers of
    `git_argument_text` also see.

    NESTED, the two readings can blind each other, and no doubling here reaches that. Once the
    payload is itself a wrapper (`bash -c $'bash -c \\'git \\x70ush --force\\''`), the POSIX
    reading eats the payload's backslashes and resolves the harmless verb `x70ush`, while the
    PowerShell reading keeps them — and thereby leaves the inner `\\'` as a real quote pair, so
    the payload becomes ONE quoted word in which `git` ends no word at all. Five such lines run a
    real push/reset/merge. They are closed now, but by `_QUOTED_SPAN` learning to start at an
    ESCAPED delimiter so the fixpoint reaches the inner wrapper — not by anything in this
    function. See the KNOWN HOLES list for what is left of the class.

    Decoding ANSI-C escapes would be the honest way to RESOLVE such a verb instead of widening it;
    this file does not, and does not pretend to.
    """
    return double if double is not None else (single or "")


def _lift_piped_payloads(text):
    """`echo "git push --force" | sh` with the payload lifted out of its quotes.

    A LEFT-TO-RIGHT scan and not one pattern, and the reason is COST — measured, not feared. The
    pattern this replaces opened with the quoted SPAN and asked for the pipe only afterwards, so
    the engine tried to build a span at every quote character in the line and every quote that
    never closes cost it the rest of the line. Medians of five on `bash -c "…\\"…\\""` repeated,
    with ZERO matches found: 0.165 s at 13 KB, 0.688 s at 26 KB, 3.609 s at 52 KB — a factor of
    ~4.2 for every doubling, which puts the reader's own bound (`GIT_READ_LIMIT`, 512 KiB) in the
    minutes -- minutes in which the session stands still on one command and this reader has said
    nothing, and past the window the provider kills at (measured near 600 s, see
    `HOOK_DEADLINE_SECONDS`) it has not said anything and the call goes through. So a bound that
    only bounds the READING does not bound anything.

    This scan, same shapes and same medians: 0.001 s at 13 KB, 0.002 s at 26 KB, 0.004 s at
    52 KB, 0.041 s at the full 512 KiB — and 0.058 s at that size on text that really IS piped,
    i.e. where it does the substituting rather than only proving there is none.

    This visits every character at most twice: a span that closes is skipped past in one step, and
    a quote character that finds no partner is never tried again, because a later start of the
    same quote reads the same tail. (An escape walk can step over a partner that a later start
    would see; that can only cost a lift, never invent one, and a payload behind an unbalanced
    quote is the shape the KNOWN HOLES list already names.)
    """
    result, index, length, unterminated = [], 0, len(text), set()
    while index < length:
        char = text[index]
        if char not in "\"'" or char in unterminated:
            result.append(char)
            index += 1
            continue
        close = index + 1
        while close < length and text[close] != char:
            close += 2 if text[close] == "\\" else 1
        if close >= length:
            unterminated.add(char)
            result.append(char)
            index += 1
            continue
        if _PIPE_TO_SHELL_RX.match(text, close + 1) is None:
            result.append(text[index:close + 1])       # an ordinary quoted argument, untouched
        else:
            if result and result[-1] == "$":
                result.pop()                           # `$'…' | sh` — the `$` is quoting, not text
            result.append(" " + text[index + 1:close] + " ")
        index = close + 1
    return "".join(result)


# How often a payload may be a wrapper again before this reader stops unwrapping. A bound, not a
# depth claim: an unbounded loop over attacker-chosen text is not something a gate may run whatever
# it decides at the end of it, because the length of the text then decides how long the session is
# frozen (`HOOK_DEADLINE_SECONDS`; `GIT_READ_LIMIT` exists for the same reason). Measured after the scan above replaced the quadratic pattern, medians
# of five at the full 512 KiB: 0.494 s for nested wrappers, 0.474 s for the escaped-quote shape
# that is the worst case for the span pattern. Three rounds is already one more than any spelling
# anyone has written down; five is the budget, not a depth claim.
_UNWRAP_ROUNDS = 5


def unwrap_shell_payload(command):
    """Command text with `bash -lc "…"`, `… | sh` and `sh <<< "…"` payloads lifted out of quotes.

    The half of `git_argument_text` that is about SHELL SYNTAX rather than about git: a wrapper
    payload is code one level down, and a gate that tokenises the outer line sees one opaque
    string where the real command is. Case and inner quoting are preserved, because a gate reading
    PATHS needs both (`mv inbox/a.pdf "archive/2026/Müller GmbH.pdf"`) — only the git reader below
    may lowercase and drop the quote marks.

    Lifted to a FIXPOINT, because a payload can be a wrapper again and `re.sub` does not rescan
    what it substituted: `bash -c "eval 'git push --force origin main'"` runs a real push, the
    membership test above holds for `bash -c` AND for `eval`, and one pass lifted only the outer
    one — measured, all eight PreToolUse hooks ALLOWED it, as they did `bash -c "bash -c '…'"`,
    `eval "eval '…'"` and `bash -c "sh -c '…'"`. The loop stops at a text that no longer changes,
    after `_UNWRAP_ROUNDS`, or once the text has grown past what the readers will scan anyway
    (`GIT_READ_LIMIT`, defined below and read at call time) — whichever comes first.
    """
    text = command or ""
    for _round in range(_UNWRAP_ROUNDS):
        lifted = _WRAPPER_RX.sub(
            lambda m: m.group(1) + " " + _lifted_payload(m.group(3), m.group(4)) + " ", text)
        lifted = _HERESTRING_RX.sub(
            lambda m: m.group(1) + " " + _lifted_payload(m.group(3), m.group(4)) + " ", lifted)
        lifted = _lift_piped_payloads(lifted)
        if lifted == text:
            break
        text = lifted
        if len(text) > GIT_READ_LIMIT:
            break
    return text


def join_line_continuations(text, tool=None):
    """`text` with its line continuations removed and every statement break spelled `\\n`.

    Single home for the rule, because three hooks kept their own copy and all three joined with a
    SPACE — see `_CONTINUATION_RX` for what that costs. Exported rather than private so a reader
    that must keep quotes and case (`gate_write_scope`) can share the rule instead of the bug.

    WHICH continuation is removed depends on the SHELL, and `tool` is how a caller says which one
    (`_CONTINUATION_BY_TOOL` carries the table and the measurement). A caller that names none is
    answered from the payload this process read (`gated_shell`), which is what keeps this from
    being the nine-call-site thread; only a process that read no payload at all falls back to the
    union.

    THE TWO REWRITES ARE ONE CALL because a caller must not be able to take the join without the
    break normalisation. `gate_write_scope` took exactly that half and then rewrote `\\n` itself, so
    a break spelled CR was invisible to it in all three kits (`_STATEMENT_BREAK_RX` carries the
    chain). Nothing here enumerates the callers; what they share is that they all decide "which
    part of this line is this command", and none of them can decide it on a text whose breaks are
    not all spelled the same
    (`tools/test_hooks_v2.py::test_the_shared_preparation_spells_every_statement_break_as_a_newline`).

    THE ORDER IS THE SHELL'S, and it BUYS NOTHING TODAY — said that way round because the sentence
    here used to claim it decided a refusal. It follows the shell: a token the shell puts back
    together must not then be cut by the break that join leaves behind. What it no longer decides
    is any verdict this repo can measure: with the continuation tool-dependent above and a line the
    Bash tool mangles refused outright (`_kernel._EATEN_IN_FLIGHT`), the four lines that used to
    separate the two orders are rc 2 under BOTH of them, measured against a real gate process. The
    order therefore stays because it is right, not because something falls over without it — and
    the text-level property it does carry is
    `tools/test_hooks_v2.py::test_a_continuation_is_joined_before_a_break_is_normalised`.
    """
    continuation = _CONTINUATION_BY_TOOL.get(gated_shell(tool), _CONTINUATION_RX)
    return _STATEMENT_BREAK_RX.sub("\n", continuation.sub("", text or ""))


# A HERE-DOCUMENT opener: the operator, an optional `-` (tab-stripping form), and the DELIMITER,
# which may be quoted three ways — `<<'EOF'`, `<<"EOF"`, `<<\EOF`. Whether it is quoted is the
# whole question this reader asks of it; see `literal_heredoc_free`.
_HEREDOC_OPEN_RX = re.compile(
    r"<<-?[ \t]*(?P<esc>\\?)(?P<quote>['\"]?)(?P<delim>[A-Za-z_][\w.+-]*)(?P=quote)")
# The programs that hand their STANDARD INPUT to a command parser — the same property `_SHELL_NAMES`
# and `_EVAL_NAMES` already state for a quoted argument, asked here of a here-document instead.
# THE DOT AND `source` ARE HERE and not in `_EVAL_NAMES`: those two READ a file and run it in the
# CURRENT shell, so `. /dev/stdin <<'EOF'` is a body a parser is fed while nothing on the line is a
# shell name. Measured by the verifier of TSK-0142: that line was rc 0 at all nine registered Bash
# hooks of a scaffolded pilot and wrote a file under `project_memory/`. The dot is required to stand
# as a WORD (a space or a tab behind it), or `./build.sh <<EOF` would match it.
_SOURCE_NAMES = r"(?:source|\.(?=[ \t]))"
# A PATCH APPLIER belongs in the same membership, and the property is what joins them rather than
# the word "parser": for all of these the body is not DATA the program receives, it is what the
# program DOES. A diff is a list of writes with the file names in it, so a body handed to `patch`
# or `git apply` names the paths the stage writes. Measured on this tree before the line below
# carried them: `git apply <<'EOF'` with a diff naming `.claude/hooks/gate_write_scope.py` was
# rc 0 at the write-scope gate, because the body was removed as prose before the first reader
# (`BUG-0286`, the "a patch file carries the path across the stage boundary" half of H22/H202).
_PATCH_APPLIER_NAMES = r"(?:patch|git[ \t]+(?:apply|am))"
_STDIN_PARSER_RX = re.compile(
    r"(?<![\w.-])(?:%s|%s|%s|%s)(?![\w-])"
    % (_SHELL_NAMES, _EVAL_NAMES, _SOURCE_NAMES, _PATCH_APPLIER_NAMES),
    re.IGNORECASE)
# WHERE THE PIPELINE OF THE OPENER ENDS, to its RIGHT. A `|` does NOT end it -- that is the whole
# of this reader's second half: the parser that receives the body may stand in a LATER stage of the
# same pipeline (`cat <<'EOF' | bash`). A `;`, a `&`, a `||` or a line break do end it, because the
# body then reaches nothing on the far side of them. There is no bare `|` alternative below, so a
# single pipe can never match.
_PIPELINE_END_RX = re.compile(r";|\n|&|\|\|")


@functools.lru_cache(maxsize=32)
def _heredoc_end_rx(delimiter):
    """The line that ENDS a here-document: the delimiter alone on it (leading tabs for `<<-`)."""
    return re.compile(r"^[ \t]*%s[ \t]*$" % re.escape(delimiter), re.MULTILINE)


def _fed_to_a_command_parser(text, position, after=None):
    """Does the PIPELINE that opens a here-document at `position` PARSE what it reads?

    THE PIPELINE AND NOT THE STAGE, and that correction is measured: the first cut read only the
    text in FRONT of the opener, where the program name stands for `bash <<'EOF'`. A here-document
    is the standard input of its stage, and a pipeline hands that input on -- so
    `cat <<'EOF' | bash` fed a shell exactly the same body while this reader saw `cat` and answered
    no. Both spellings were rc 0 at every registered Bash hook of a scaffolded pilot and wrote a
    file under `project_memory/` (verifier round 1 of TSK-0142, B1); the rows are in
    `tools/test_hooks.py::test_a_heredoc_body_handed_to_a_shell_is_judged_as_a_command`.

    So the subject is the whole pipeline the opener stands in: from the last separator in front of
    it -- where a `|` DOES end the left part, because a stage's own program name stands there -- to
    the first `;`, `&`, `||` or line break behind it, where a `|` does NOT end it. Unknown answers
    NO... which is the direction that KEEPS a body, and therefore the fail-closed one for
    `literal_heredoc_free`.
    """
    # `after` is the END of the opener where the caller knows it: the DELIMITER is part of the
    # opener, and a here-document opened with `<<'sh'` would otherwise read as a shell of its own.
    left = re.split(r"[&|;\n]", join_line_continuations(text[:position]))[-1]
    right = _PIPELINE_END_RX.split(text[position if after is None else after:])[0]
    return _names_a_stdin_parser(left) or _names_a_stdin_parser(right)


def _names_a_stdin_parser(stage):
    """Does this span of a pipeline name a program that PARSES what it reads?

    THE REDIRECTIONS GO FIRST, and that is the correction of 2026-09-12: the membership was asked
    of the RAW span, where a word can be anything -- a file NAME included. Measured through the
    shipped gate as real processes, `cat > patch.diff <<'EOF'`, `cat > patch/notes.md <<'EOF'`,
    `cat > bash.md <<'EOF'` and `cat > source.txt <<'EOF'` were all **rc 2**: writing a patch to a
    file for review, or a note whose name begins with a member word, was refused as if the body
    were applied. A redirection's target never reaches the program, and `_argument_scan` is this
    file's one reader of that -- asking it here makes the membership a question about the COMMAND
    instead of about the characters of the line.

    WHAT IT STILL OVER-REFUSES, measured and written down rather than claimed away: an ordinary
    OPERAND whose name begins with a member word (`cat patch.diff <<'EOF'`). A word in operand
    position is not a program either, but telling the two apart needs the runner question --
    `nohup bash <<'EOF'`, `timeout 5 bash <<'EOF'`, where the operand IS what executes -- and the
    direction that keeps those refusing is the one this gate has to take. Both ends stand in
    `tools/test_hooks.py::test_a_heredoc_body_handed_to_a_shell_is_judged_as_a_command`, and the
    ledger gate's own reading of the same reader in
    `tools/test_hooks_v2.py::test_a_heredoc_body_an_interpreter_executes_is_not_prose_here`.
    """
    text, _words = _argument_scan(stage)
    return _STDIN_PARSER_RX.search(text) is not None


def literal_heredoc_free(command):
    """`command` with the body of every LITERALLY-QUOTED here-document removed.

    WHY THE QUOTING OF THE DELIMITER DECIDES, and it is a property of the shell rather than a
    convention: `<<'EOF'`, `<<"EOF"` and `<<\\EOF` quote it, and POSIX then performs NO expansion on
    the body — no parameter, no arithmetic, and no COMMAND SUBSTITUTION. A backtick or a `$(` in
    such a body is a character in a document, not a command this line runs. An UNQUOTED delimiter
    is the opposite case and its body STAYS in the view, because there the shell really does run
    what those characters open.

    MEASURED, and the bisection went down to the character: in a scaffolded project,
    `python scripts/harness.py capture SR <<'EOF'` with the body `from git clone to a 200 on
    /health` passed every registered Bash gate, and the same line with backticks around `git clone`
    was refused — the gates lifted the substitution out of prose the shell would never expand. The
    documented route out of `staging/` ran through exactly that line.

    THE BODY A SHELL WOULD PARSE IS KEPT WHATEVER ITS DELIMITER SAYS. `sh <<'EOF' … EOF` hands the
    body to a command parser, so the body IS the command; the quoting only decides whether the
    SHELL expands it first. `_fed_to_a_command_parser` is that test, and it is the same membership
    property `_SHELL_NAMES`/`_EVAL_NAMES` state above rather than a second list.

    WHAT IT DOES NOT COVER, named rather than implied: an INTERPRETER that reads its program from
    standard input and is not a shell (`python <<'EOF'`, `perl <<'EOF'`). Its body is code in
    another language, and what removing it costs depends on WHO is reading. For the gates that
    judge a shell command line it costs an incidental match on a shell word inside that source —
    measured before this shipped, `python <<'EOF'` with a `git push --force` in a python string
    already passed every registered Bash gate, so those gave nothing up.

    FOR THE OFFICE KIT'S `gate_ledger_valid`, WHICH TOOK THIS READER UP IN TSK-0081, IT COSTS A REAL
    REFUSAL, and that is measured rather than reasoned about: `python <<'EOF'` whose body opens
    `scripts/ledger_add.py` for writing was exit 2 through that gate before it used this helper and
    is exit 0 after it — the same for `python3` and `perl`. The gate's own subject is the ledger and
    its judge, so a body it no longer sees is a write it no longer judges. That residue is OPEN, and
    it is named as a hole rather than closed here: closing it would mean this helper deciding which
    PROGRAMS execute their standard input, a question `_STDIN_PARSER_RX` answers only for shells and
    only because their membership is a closed set.
    """
    return heredoc_free(command, lambda literal, fed, head: not literal or fed)


def prose_heredoc_free(command):
    """`command` with every here-document body removed EXCEPT one a command parser is fed.

    THE OTHER QUESTION ABOUT THE SAME SPAN, and the two are not interchangeable. The reader above
    asks what the SHELL EXPANDS, which is what a gate about a ledger path needs. A gate that judges
    a COMMAND LINE asks something narrower: is this body a COMMAND? A body handed to `sh`, `bash`
    or `eval` is -- that is the same `_fed_to_a_command_parser` membership -- and every other body
    is data the program on the left receives, whatever its delimiter's quoting says about
    expansion.

    Measured, and it is why this exists beside its sibling rather than as a caller of it:
    `gate_write_scope` removed every body unconditionally, so `bash <<'EOF'` with a write to
    canonical state inside it was rc 0 (`BUG-0289`). Switching that gate to the sibling closed it
    and broke the other end in the same move -- `cat > /tmp/notes.md <<EOF` with `project_memory`
    in its PROSE became rc 2, because an unquoted delimiter means the shell expands the body and
    the sibling therefore keeps it. Neither reader is wrong; they answer different questions
    (`tools/test_hooks_v2.py::test_a_heredoc_body_is_prose`,
    `tools/test_hooks.py::test_a_heredoc_body_handed_to_a_shell_is_judged_as_a_command`).
    """
    return heredoc_free(command, lambda literal, fed, head: fed)


def heredoc_free(command, keep):
    """`command` with the body of each here-document `keep(literal, fed, head)` rejects removed.

    ONE SCANNER, and the CONDITION is the caller's. Three readers of the same span ask three
    different questions of it -- what the shell expands, what is a command, and what a program
    will EXECUTE -- and a scanner per question is three copies of the one subtlety this has: where
    the scan resumes after a body it keeps. `keep` is handed

      * `literal` -- the delimiter is quoted, so POSIX performs no expansion in the body;
      * `fed` -- a command PARSER is on the left of the opener (`_fed_to_a_command_parser`);
      * `head` -- the text of the line in front of the opener, so a caller can ask its OWN question
        about the program that receives the body. `gate_ledger_valid` does: a body handed to a verb
        that only reads is prose, and a body handed to anything else is a program that may write
        the ledger's judge (`BUG-0149`) -- which is the question this module could not answer for
        it, because "which programs execute their standard input" is not a property of a command
        line and the ledger gate's own read-only classification is the nearest thing to one.
    """
    text = command or ""
    out, index = [], 0
    while True:
        match = _HEREDOC_OPEN_RX.search(text, index)
        if match is None:
            break
        newline = text.find("\n", match.end())
        if newline < 0:
            break                      # an opener with no body in this payload
        end = _heredoc_end_rx(match.group("delim")).search(text, newline + 1)
        stop = len(text) if end is None else end.end()
        literal = bool(match.group("esc") or match.group("quote"))
        head = text[text.rfind("\n", 0, match.start()) + 1:match.start()]
        if keep(literal, _fed_to_a_command_parser(text, match.start(), match.end()), head):
            # the body STAYS — and the scan resumes AFTER its terminator, never inside it. Resuming
            # inside made a body its own hiding place: `sh <<EOF` whose first line merely PRINTS
            # `<<'X'` opened a here-document to this reader, and everything down to a line spelling
            # `X` was then removed from the view — including whatever command stood between them.
            out.append(text[index:stop])
        else:
            out.append(text[index:newline + 1])
        index = stop
    out.append(text[index:])
    return "".join(out)


# --- shell WORDS, with the quoting resolved ----------------------------------
#
# THE COMPARISON HAS TO READ THE RESOLVED STRING, NOT THE TYPED ONE. Every path rule in this kit
# is a comparison against a word of a command line, and shell QUOTING is invisible to the program
# that receives the word: `project'_'memory/…` and `'.cl'aude/hooks/…` reach the filesystem as the
# plain paths, while a reader that keeps the marks compares against a string no program ever sees.
# Measured 2026-08-04 as real hook processes AND as a real bash write — the file was overwritten
# and every registered gate allowed it — for BOTH readers that own a path rule:
#     echo x > '.cl'aude/hooks/gate_write_scope.py       (gate_write_scope: enforcement layer)
#     mv inbox/a.pdf arch'i've/invented/a.pdf            (gate_filing: the office archive)
# A splice in the FILE NAME was caught in both, which is how this stood for so long: the DIRECTORY
# prefix still spelled itself out there.
#
# ONE HOME, TWO SPLITTERS. What differs between the readers is how a line becomes tokens — a lexer
# that also splits punctuation for the shell gate, a regex for the filing reader — and that is the
# argument they pass in. What must NOT differ is the resolution, which is why it lives here.
#
# HOW: the balanced spans are masked out before the caller splits, and put back after. So the
# splitting still happens with the quoting IN PLACE (a quoted `|` is not a pipeline, a quoted space
# does not break a word) while the word handed back is the string the program receives — and two
# fragments the shell joins into one word stay one word, which a lexer given the raw text does not
# manage (`'.cl'aude/x` lexes as two tokens).
_SPAN_RX = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
_MASK = "\x01%d\x02"
_MASK_RX = re.compile("\x01([0-9]+)\x02")
# WHAT THE WORKSHOP'S OWN GATES BORROW FROM THIS MODULE, declared for the reason
# `gate_write_scope.HARNESS_BORROWS` states beside its own list (`BUG-0107`): the borrowing is
# deliberate -- a second answer to "which part of this word is quoted" is the drift this repository
# has paid for -- and what it costs is a dependency on UNDERSCORED names that nothing declared.
# Measured by the verifier of TSK-0142 (B4): renaming `_MASK_RX` here made `gate_lead_write_scope`
# refuse EVERY Bash call of the session, fail-closed and unrepairable from inside, while the
# tripwire stayed green because it read only the other module. The surface is now one declaration
# per BORROWED MODULE, and the tripwire reads all of them
# (`tools/test_hooks.py::test_the_harness_borrows_only_what_this_kit_declares`).
HARNESS_BORROWS = ("_MASK_RX",)
# The POSIX reading of a backslash: it protects the next character and is itself removed. Applied
# to the MASKED token, so a backslash inside a quoted span — where the shell keeps it — is untouched.
_POSIX_ESCAPE_RX = re.compile(r"\\(.)")
_ESCAPE_RX_CACHE = {}


def _escape_rx(escape):
    """`<escape><character>` -> `<character>`, for ONE shell's escape character.

    Built per character rather than written out per shell, because the set of escape characters is
    already stated once (`_ESCAPE_CHARS`, with the measurement for why it has two entries) and a
    second spelling of it is what left `shell_words` resolving only the backslash while its own
    docstring promised every reading (`BUG-0158`).
    """
    if escape not in _ESCAPE_RX_CACHE:
        _ESCAPE_RX_CACHE[escape] = re.compile(re.escape(escape) + r"(.)", re.DOTALL)
    return _ESCAPE_RX_CACHE[escape]


class ShellWord(str):
    """One word of a command line, with its quoting resolved — see `shell_words`.

    A `str`, so a reader that only wants the text keeps working unchanged. Two extra facts:
      * `spliced` — quoting produced part of it, so the shell can never have read it as an
        OPERATOR: `echo '>' file` and `echo > file` spell the same three characters and only the
        second one redirects;
      * `readings` — every value an ordinary shell could hand the program. The two shells this kit
        gates disagree about the backslash, and `shell_readings` is how a caller asks for both.
    """
    spliced = False
    readings = ()


def shell_readings(word):
    """Every value an ordinary shell could hand the program for this word — see `ShellWord`.

    A plain `str` (a caller that never went through `shell_words`, a fallback path) reads as its
    own single reading rather than raising, which keeps this usable as a total function.
    """
    return getattr(word, "readings", None) or (str(word),)


def shell_words(text, split):
    """[ShellWord] — `text` split by `split`, with the shell's quoting resolved.

    `split` takes the masked text and returns raw tokens; see the block comment above for why the
    two are separated and for the measurements that made this necessary.

    THE BACKSLASH GETS BOTH READINGS RATHER THAN ONE, the same answer `_ESCAPE_CHARS` gives the git
    reader and for the same reason: the command text does not say which shell will run it, and the
    two disagree. In PowerShell a backslash is a path SEPARATOR (`.claude\\hooks\\x.py` is one
    ordinary path); in a POSIX shell it protects the next character and vanishes, so
    `echo x > .cl\\aude/hooks/gate_git.py` is a real write into the enforcement layer — measured in
    Git Bash, rc 0 and the file overwritten. A caller that DECIDES on a path must ask
    `shell_readings` and answer over all of them; a path that means nothing under one reading
    simply matches nothing, so consulting both can only refuse more.
    """
    spans = []

    def mask(match):
        spans.append(match.group(0)[1:-1])
        return _MASK % (len(spans) - 1)

    def unmask(match):
        # a mask sequence the masking did not put there (both control characters can be typed) is
        # left standing rather than indexed with — a gate must not crash on its own input
        index = int(match.group(1))
        return spans[index] if index < len(spans) else match.group(0)

    out = []
    for token in split(_SPAN_RX.sub(mask, text or "")):
        kept = _MASK_RX.sub(unmask, token)
        word = ShellWord(kept)
        word.spliced = _MASK_RX.search(token) is not None
        # ONE READING PER ESCAPE CHARACTER, derived from `_ESCAPE_CHARS` rather than from the one
        # spelling somebody built. The docstring above promised "every value an ordinary shell
        # could hand the program" while only the POSIX backslash was resolved, so PowerShell's
        # BACKTICK -- which takes the special meaning away from the next character exactly as the
        # backslash does, and vanishes with it -- produced a path no reader ever saw: measured,
        # `copy-item evil.py scr` + backtick + `ipts/ ; git commit -m x` was rc 0 at the office
        # ledger gate while the same line without the backtick was rc 2 (`BUG-0158`). Deriving the
        # readings from the constant is what makes the promise one the code keeps
        # (`tools/test_hooks.py::test_every_escape_character_of_this_kit_gets_its_own_reading`).
        readings = [kept]
        for escape in _ESCAPE_CHARS:
            resolved = _MASK_RX.sub(unmask, _escape_rx(escape).sub(r"\1", token))
            if resolved not in readings:
                readings.append(resolved)
        word.readings = tuple(readings)
        out.append(word)
    return out


def _shell_normalised(command):
    """Literal here-document bodies removed, line continuations removed, then wrapper payloads
    lifted out — the shell-syntax preface the git reader below shares.

    The here-documents go FIRST, and before the continuations rather than after: inside a quoted
    body a backslash is an ordinary character, so joining continuations there would splice two
    lines of a document the shell keeps apart. Continuations then go before the lift, because one
    may sit between the wrapper and its payload (`bash \\<newline> -lc "git push"`) and
    `_WRAPPER_RX` cannot cross a raw newline."""
    return unwrap_shell_payload(join_line_continuations(literal_heredoc_free(command)))


# The character that takes the special meaning away from the next one is a property of the SHELL,
# not of the text: POSIX shells escape with a backslash, PowerShell with a backtick — and this kit
# gates the `PowerShell` tool on the same eight PreToolUse hooks as `Bash` (`SHELL_TOOLS`). A
# reader that knows only the POSIX spelling is blind to the other one's, and blind in BOTH
# directions: measured as real hook processes with `tool_name: "PowerShell"`,
# `git push --for`ce origin main` reached git as `--force` while the unconditional force-push ban
# saw nothing, and `git pu`sh --force` matched no gate at all — one character, shorter than the
# quoted-verb bypass this whole layer was rebuilt for. In the other direction a POSIX reading of a
# PowerShell payload EATS characters: `C:\path\name` becomes `C:pathname`.
#
# The command text does not say which shell will run it, and `tool_name` is not threaded through
# nine call sites without one of them forgetting. So the readers below produce EVERY reading an
# ordinary shell could give the text and answer over all of them: an integrity gate that is unsure
# which shell it is looking at must see both, because over-triggering costs a retry and silence
# costs the rule (spec II.4 fail-closed). When the text contains neither escape character the two
# readings are provably the same string and only one is produced.
_ESCAPE_CHARS = ("\\", "`")
_STOP_RX_CACHE = {}
_WORD_RX = re.compile(r"\S+")
# WHERE THE TEXT STOPS DETERMINING THE TOKEN — one predicate, asked as TWO questions, because they
# are not the same question and exactly one character tells them apart.
#
# THE PREDICATE: after this character, what the shell finally builds is decided by something the
# command text does not contain — the environment, the filesystem, or an unescaping this file does
# not perform. It is derived per SHELL rather than collected per bug, and there are three of them
# in reach (`SHELL_TOOLS` gates `Bash` and `PowerShell`; either can spawn `cmd /c`):
#   * a POSIX shell substitutes at `$` (parameter, `$(…)`, arithmetic) and at a BACKTICK (the older
#     command substitution), expands `{…}` (brace expansion, `${…}`) and `* ? [ ]` (pathname
#     expansion), and escapes with a BACKSLASH.
#   * PowerShell substitutes at `$` (`$env:X`, `$(…)`), globs with `* ? [ ]`, and escapes with the
#     BACKTICK — a backslash is an ordinary character of a path there.
#   * cmd substitutes `%NAME%`, substitutes `!NAME!` when delayed expansion is on (`cmd /v:on`),
#     and escapes with `^`, which it removes from the line before it splits the line into words.
#
# QUESTION ONE — the VALUE of a token (`_subcommand_candidates`): is this the verb the gates ask
# about? Every character above answers "the text does not say", and so does a BACKSLASH, in BOTH
# readings this file produces: the POSIX one consumes it and hands back a different string than
# bash would (`git $'\x70ush'` is `push` to bash, `x70ush` here — the escape eats exactly the `x`),
# and the PowerShell one (`_ESCAPE_CHARS[1]`) never consumes a backslash at all, so every one of
# them stands in the token it read. Either way the honest answer to "which git command is that" is
# "unknown", not "not a push". Such a token is `resolved=False` and `Invocation.runs` then
# answers YES to every question — measured as a full ALLOW across all eight PreToolUse hooks while
# the literal spelling was refused by three: `git $V --force`, `git $(echo push)`, `git %VERB%`,
# `git pus{h..h}` (a brace sequence with equal ends is ONE word, `push`), `git pus[h]` and
# `git ?ush` (which push the moment a file named `push` sits in the directory — and the directory
# is not in the command text), `cmd /c "git p^ush --force origin main"` and
# `cmd /v:on /c "set V=push& git !V! --force origin main"`.
#
# QUESTION TWO — the WORD BOUNDARY right after the letters `git` (`_ends_word`): may the program
# name END here? That needs a construct which can BECOME a separator or UNCOVER one. Everything
# that substitutes or expands can: `${IFS}` is a space in every ordinary environment, `{,}` splits
# one word into two, a glob into as many as the directory holds, `!V!` and `%V%` into whatever the
# variable holds — `cmd /v:on /c "set ""V= "" & git!V!push --force origin main"` is a real push
# with no space in the line at all. cmd's `^` can too — it is removed and only it, so
# `cmd /c "git^ push --force origin main"` really runs a push (measured through the PowerShell
# tool, which is how a `cmd /c` line reaches cmd at all: Git Bash's msys layer rewrites the `/c`
# into a path).
#
# A BACKSLASH IS THE ONE THAT CANNOT, and that is the whole of the difference. bash removes it
# TOGETHER with the character it protects, and that character then belongs to the same word, so
# `git\ push --force origin main` is bash asking for a program named `git push` and calling no git
# at all (measured: no git process). PowerShell and cmd keep it as an ordinary path character
# (`cd C:\src\git\repo`). No shell turns `git` followed by a backslash into a word of its own, so
# reading it as a possible word end bought no attack and cost the most ordinary Windows lines in
# the repo — `cd C:\git\repo`, `cd "C:\Program Files\Git\bin"`, `robocopy C:\git\a C:\git\b /E`,
# `Copy-Item C:\a\git\x.txt D:\b`, `$env:PATH = "C:\git\bin;" + $env:PATH` — each measured as
# refused by three gates with no git call in them at all. Fail-closed is a rule about what is
# UNKNOWN, and this one is known.
# A VARIABLE REFERENCE has a FORM, and cmd's two forms are both PAIRED — `%NAME%` and, under
# delayed expansion, `!NAME!`. Matching them by their FORM and not by their opening character is
# not a nicety: a lone `!` is no metacharacter in cmd at all (it is one only between a pair), and
# reading it as one cost six ordinary prose lines that hold no git call in any shell —
# `echo "I love git!"`, `echo git!`, `echo 'git!'`, `bash -c "echo git!"`,
# `Write-Output "migrated to git!"`, `echo "git!!"` — each measured as refused by three gates.
#
# WHAT STANDS BETWEEN THE DELIMITERS is the other half of the form, and spelling it `\w+` was an
# enumeration one level below the place the pairing rule got right. cmd's reference is
# `!NAME[:modifier]!`, and a modifier is a SUBSTRING (`:~0,4`) or a REPLACEMENT (`:a=u`) — neither
# is `\w`. Measured in cmd.exe through the PowerShell tool, each of these hands git a real
# `push --force origin main` and each reached NONE of the eight hooks while `!V!` was refused by
# three:
#     cmd /v:on /c "set V=pushXX& git !V:~0,4! --force origin main"
#     cmd /v:on /c "set V=pash&   git !V:a=u! --force origin main"
#     cmd /v:on /c "git !ERRORLEVEL:0=! push --force origin main"
# So the content is a DEFINITION too — everything that is not the delimiter and not a separator —
# and that covers the modifiers, the dynamic variables (`ERRORLEVEL`, `CD`, `RANDOM`) and whatever
# cmd adds next, instead of the next spelling being the next hole.
#
# The paired form is what keeps this cheap: measured over 14 prose lines, including the two the
# form makes tempting to guess about, NONE is refused. `echo "git! and git!"` does open a possible
# word BREAK — inside a quoted span the whitespace is not a separator, so `! and git!` is a
# reference by this definition — but the token it hands the verb question is `! and git!` with its
# spaces intact, which no reference form matches, so the verb resolves to something no gate asks
# about and the line stands.
#
# The CARET is the counter-case that shows this is a rule about FORM and not a preference for
# pairs: cmd's escape really does stand alone, so it stays a single character — and its price is
# one honest false alarm, `echo "use git^ for the first parent"`.
_UNDETERMINED_CHARS = "$`{}*?[]^"      # both questions: can produce text this line does not hold
_VALUE_ONLY_CHARS = "\\"               # the VALUE question only — see the paragraph above
_CMD_VARIABLE_RX = r"%[^%\s]+%|![^!\s]+!"
_UNDETERMINED_BREAK_RX = re.compile(
    "[%s]|%s" % (re.escape(_UNDETERMINED_CHARS), _CMD_VARIABLE_RX))
_UNDETERMINED_VALUE_RX = re.compile(
    "[%s]|%s" % (re.escape(_UNDETERMINED_CHARS + _VALUE_ONLY_CHARS), _CMD_VARIABLE_RX))


def _stop_rx(escape):
    """The characters `_argument_scan` has to look at ONE AT A TIME, for a given escape char.

    Everything between two of them is copied in one C-level slice with one quoting state, which is
    what keeps the scan linear and cheap: the old per-character Python loop cost 6.75 s on a single
    16 MiB command and `gate_git` runs the scan five times."""
    rx = _STOP_RX_CACHE.get(escape)
    if rx is None:
        rx = re.compile("[%s]" % re.escape(escape + "\"'#$`()<>"))
        _STOP_RX_CACHE[escape] = rx
    return rx


_REDIRECT_TAIL_CACHE = {}


def _redirect_tail_rx(escape):
    """The rest of a REDIRECTION once its first character has been seen, for a given escape char.

    Namely: the second operator character where there is one (`>>`, `<<`, `<&`, `>&`, `<>`, `>|`),
    the optional space, and then the TARGET — which is a WORD by the same definition as any other,
    so an escaped character and a quoted span belong to it (`> "C:\\My Logs\\out.txt"`,
    `>out\\ file`). All of it is consumed and none of it reaches the program, which is what makes the
    operator a word boundary rather than a character inside the word beside it. It stops at the next
    metacharacter, so `>out && git push` keeps its `&&` and the second command with it.
    """
    rx = _REDIRECT_TAIL_CACHE.get(escape)
    if rx is None:
        rx = re.compile("[<>&|]?[ \t]*(?:%s.|\"[^\"]*\"|'[^']*'|[^\\s&|;()<>\"'`])*"
                        % re.escape(escape))
        _REDIRECT_TAIL_CACHE[escape] = rx
    return rx


def _terminates_word(char, literal):
    """True when `char` ends a shell WORD, so whatever follows it begins a new one.

    Asked of the last character emitted into the word view, and it is two facts rather than one:
    whitespace ends a word, and OUTSIDE a quoted span so does a command separator (`_SYNTAX_CHARS`
    — `& | ;` and the newline; the `#` in that set never reaches a run, it is a stop character).
    Asking only `.isspace()` was measurably wrong in the direction of noise: `;` is not a stop
    character, so it arrives inside a run, `';'.isspace()` is False, and `git status;# git push
    --force origin main` — which a real bash runs as `git status` and nothing else — was read as
    carrying the push and refused by three gates. Inside a quoted span a separator is data, which
    is why `literal` is a parameter and not something this can infer from the character.
    """
    return char.isspace() or (not literal and char in _SYNTAX_CHARS)


def _reverse_chars(buffer):
    """The characters already emitted into one of the two views, newest first, across chunks."""
    for chunk in reversed(buffer):
        for char in reversed(chunk):
            yield char


def _digits_open_a_word(words, count):
    """True when the last `count` characters of the WORD VIEW are digits that begin a word.

    The other half of the descriptor rule, and it has to be asked on this view rather than on the
    text: an ESCAPED space is still a space in the text and is `\\x00` here, so `echo a\\ 2>x`
    hands the program the single word `a 2` and its `2` is no descriptor — the text-side questions
    alone answered yes and silently dropped a character out of an argument. They are kept beside it
    because they carry the facts this view has thrown away: a quote MARK is gone from the word view,
    so `git push "2">/dev/null` looks word-initial HERE while on the text the digit scan collects
    nothing at all (see `_drop_io_number` for which clause decides which line). Both facts are
    needed and neither view holds both.
    """
    seen = 0
    for char in _reverse_chars(words):
        if seen == count:
            return char.isspace()
        if char not in "0123456789":
            return False
        seen += 1
    return seen == count


def _drop_io_number(text, operator, kept, words):
    """Remove the file DESCRIPTOR in front of a redirection from what has been kept so far.

    `2>&1` is one redirection, not the argument `2` — the digits belong to the operator. Dropping
    them matters in the SAME direction the operator itself does: `git push origin main >/dev/null
    2>&1` is an ordinary push, and reading `2` as a third positional token made `gate_push_token`
    refuse it as "more than one refspec", which teaches people to write the command in a way the
    gate cannot read.

    The rule is the shell's own (POSIX XCU 2.10.2): the digits count as a descriptor only when they
    are UNQUOTED, UNESCAPED and the entire word in front of the operator. Three clauses answer
    that, and which one answers which case matters, because each is the only guard for its own:

      * QUOTED — decided by the digit scan finding nothing (`not count`). The scan runs on `text`,
        which still carries the quote MARKS (they are removed only from the two output views), so
        in `git push "2">/dev/null` the character before the operator is a `"`, no digit is
        collected, and nothing is dropped. The neighbour test below never runs on that line.
      * ESCAPED, or the tail of a longer word — decided by the NEIGHBOUR test: digits preceded by
        anything that is not a separator are part of a word, and a word is an argument.
        `git push2>/dev/null` hands git `push2`, and `git push \\2>/dev/null` hands it the argument
        `2` (bash: the escape makes `\\2` an ordinary word, so the operator has no descriptor).
        This clause is the ONLY thing that keeps that `2`, and removing it left all 81 selected
        tests green until the `\\2>` line was written down.
      * THE ENTIRE WORD — decided by `_digits_open_a_word` on the word view, which is the only
        view that knows an escaped space is not a break (`git push a\\ 2>/dev/null`).
    """
    start = operator
    # ASCII digits by name, not `str.isdigit()`: that also answers yes to `٢` and `²`, which no
    # shell reads as a descriptor — a word character removed from a verb the gates then mis-read
    while start and text[start - 1] in "0123456789":
        start -= 1
    count = operator - start
    # no digits at all in the TEXT (a quote mark stands there), or an escape/word character in
    # front of them: either way these digits are not the operator's — see the docstring
    if not count or (start and text[start - 1] not in " \t\n\r&|;()<>"):
        return
    if not _digits_open_a_word(words, count):
        return
    for buffer in (kept, words):
        remaining = count
        while remaining and buffer:
            chunk = buffer.pop()
            if len(chunk) > remaining:
                buffer.append(chunk[:-remaining])
                break
            remaining -= len(chunk)


def _argument_scan(command, lower=True, escape="\\"):
    """(text, words) — the normalised command text, plus a parallel WORD VIEW of the same length.

    THE ONE VIEW every git reader works on — "what did the shell actually hand to git". The quote
    MARKS are gone and the quoted CONTENT stays, because quoting changes how the shell splits
    words, not what the command receives: `git merge "feat/PR-0001-x"` names the same ref as the
    bare spelling, and `git "push"`, `git pu''sh` and `git pu\\<newline>sh` are all the same
    invocation of push. There USED to be a second reader that DELETED quoted spans as prose before
    deciding whether a line invokes git at all, and deleting the span deleted the VERB with it:
    measured in a scaffolded project, `git "push" --force origin main` matched none of the eight
    PreToolUse(Bash) hooks — the force-push ban, the pipeline, the coverage and the push-token gate
    were all off, with two quote characters.

    A quote MARK is removed with nothing in its place, exactly as the shell removes it, so
    `pu''sh` closes back up into one word. Replacing it with a space instead re-opens the same
    hole from the far side, one spelling further along.

    What that deleted reader was RIGHT about survives as the WORD VIEW instead of as a deletion: a
    commit message TALKING about a push is text and must not read as one. The distinction is not
    lexical and not positional either — it is about WORDS. Whitespace inside a quoted span does not
    break a word, so `-m "docs: git push blocked"` is ONE argument that happens to contain the
    letters; the word view spells that whitespace `\\x00`, which is not whitespace to `_WORD_RX`,
    so the whole span comes back as a single token and `git_invocations` can see that the `git` in
    it does not END a word. A COMMAND SUBSTITUTION is the exception that proves the rule: `"$(git
    push)"` sits inside quotes and still runs, so its spaces are real separators there.

    Five more decisions are made HERE rather than by the caller, because each needs the quoting
    state this single pass already carries — and they are five because the metacharacter set is
    closed (`_SYNTAX_CHARS` above), not because five cases have come up so far:
      * a `#` opens a comment only OUTSIDE quotes AND only at the start of a word. With the marks
        gone, a `#` in a commit message would look like one and would take the rest of the line —
        including the real ref — with it (`git merge -m "fix #3" feat/PR-0001-x`). "Start of a
        word" is a question for the WORD VIEW and was asked on the raw text, where an escaped space
        still looks like a break: `echo a\\ # ; git push --force origin main` prints `a #` and then
        PUSHES in a real bash, while this scan cut the line at the `#` and all eight PreToolUse
        hooks stood down — a class HEAD still caught. `word_start` therefore carries the answer
        forward per branch instead of being re-derived from a view that cannot hold it (a quote
        MARK emits nothing and still opens a word, so the emitted characters alone cannot say it
        either). What ENDS a word is `_terminates_word`, not `.isspace()`: a command separator ends
        one too, and asking only about whitespace made `git status;# git push --force origin main`
        — one `git status` and a comment, in a real bash — read as carrying the push.
      * the command separators are syntax outside quotes and data inside them, so inside they are
        neutralised; otherwise a `|` in a message would split off the very invocation it belongs to.
      * PARENTHESES are syntax outside quotes: they open and close a command context, they are not
        part of any word. Leaving the closing one attached spelled the verb of `$(git push)` as
        `push)`, which is no subcommand at all — the fail-OPEN reading of a command that really
        pushes. The `$(` is kept intact, because `gate_git` reads it as the marker of a ref the
        text cannot resolve.
      * a REDIRECTION is syntax outside quotes, and it is the one metacharacter that swallows the
        word AFTER it as well (`_redirect_tail_rx`, `_drop_io_number`). Leaving `>` attached was
        the same fail-OPEN shape one character further along: `git push>/dev/null --force` had the
        verb `push>/dev/null` and every git gate stood down, while `git push origin main >log`
        handed `gate_push_token` a third positional token and it refused an ordinary push.
      * `$'…'` and `$"…"` are QUOTING, not expansion. Read as an expansion, `git $'push' --force`
        had the subcommand `$push` and every gate stood down; the `$` is dropped and the ordinary
        quote path takes it from there. That path does NOT decode ANSI-C escapes — this file has
        no `\\x70`→`p` decoder and must not read as if it had (the previous wording, "ANSI-C
        quoting is deterministic", explained why one COULD decode and was then cited as proof that
        it DID: `git $'\\x70ush' --force origin main` pushes for real and reached no gate). What
        makes it safe anyway is that a backslash reaches the finished token in at least one of the
        two readings — always in the PowerShell one, which consumes no backslash at all — where
        `_UNDETERMINED_VALUE_RX` reads it as a verb the text does not fix. In the POSIX reading the
        same line resolves to the harmless-looking `x70ush`; one reading answering "unknown" is
        what the gates decide on (`Invocation.runs` over all of them).
    CASE is the caller's decision: lowercasing is right for reading verbs and flags and wrong for
    reading a ref, because a branch is case-sensitive and `gate_push_token` binds its approval
    token to the branch NAME. That caller passes `lower=False`; the subcommand is lowercased by
    `git_invocations` itself, so matching a verb stays case-insensitive either way.
    """
    text = _shell_normalised(command)
    if lower:
        text = text.lower()
    stop, length = _stop_rx(escape), len(text)
    kept, words = [], []
    quote, substitution, index = "", 0, 0
    # "the next character would begin a WORD" — see the `#` bullet above. Carried per branch
    # because no view holds it: a quote mark emits nothing into either one and still opens a word.
    word_start = True
    while index < length:
        match = stop.search(text, index)
        edge = length if match is None else match.start()
        if edge > index:
            run = text[index:edge]
            literal_run = bool(quote) and not substitution
            if literal_run:
                kept.append(run.translate(_SYNTAX_TO_SPACE))
                words.append(run.translate(_QUOTED_WHITESPACE_TO_FILLER))
            else:
                kept.append(run)
                words.append(run)
            word_start = _terminates_word(words[-1][-1], literal_run)
            index = edge
        if match is None:
            break
        char = text[index]
        index += 1
        literal = bool(quote) and not substitution
        following = text[index:index + 1]
        opened = word_start
        word_start = False
        if char == escape and index < length and quote != "'":
            # an ESCAPED character is data, never syntax (single quotes escape nothing in sh), and
            # an escaped space does not break a word either
            char = text[index]
            index += 1
            kept.append(" " if char in _SYNTAX_CHARS else char)
            words.append("\x00" if char.isspace() else char)
        elif quote and char == quote:
            quote = ""                # the MARK is not a word break — `pu''sh` is one word
        elif not quote and char in "\"'":
            quote = char              # ...but it does OPEN one: `''#x` is the word `#x`, not a
                                      # comment, which is exactly what no emitted view can say
        elif char == "$" and not quote and following in ("'", '"'):
            continue                  # `$'…'`/`$"…"` — the quote does the work, the `$` is noise
        elif char == "$" and quote != "'" and following == "(":
            # `$(` opens a command context the shell WILL parse, double quotes or not
            index += 1
            substitution += 1
            kept.append("$(")
            words.append("$(")
            word_start = True         # a command context starts a command, hence a word
        elif char == "`" and quote != "'":
            substitution = 0 if substitution else 1
            kept.append(char)
            words.append(char)
            word_start = True
        elif char in "()" and not literal:
            if char == ")" and substitution:
                substitution -= 1
            kept.append(" ")
            words.append(" ")
            word_start = True
        elif char in "<>" and not literal:
            # a REDIRECTION: the operator, its descriptor and its target are the shell's, never the
            # program's — so the word before it ends here and nothing of the redirection is kept
            _drop_io_number(text, index - 1, kept, words)
            index = _redirect_tail_rx(escape).match(text, index).end()
            kept.append(" ")
            words.append(" ")
            word_start = True
        elif char == "#" and not quote and opened:
            end = text.find("\n", index)
            index = length if end < 0 else end
            word_start = True         # the newline that ends the comment is a break like any other
        else:
            kept.append(" " if literal and char in _SYNTAX_CHARS else char)
            words.append("\x00" if literal and char.isspace() else char)
    return "".join(kept), "".join(words)


@functools.lru_cache(maxsize=2)
def _scan_views(command, lower=True):
    """Every reading of `command` an ordinary shell could produce — see `_ESCAPE_CHARS`.

    Memoised because `gate_git` alone asks for the same view five times per call and the scan is
    the expensive part of a hook whose budget is `HOOK_DEADLINE_SECONDS` and which has no way of
    noticing it run out."""
    views = [_argument_scan(command, lower, _ESCAPE_CHARS[0])]
    if any(char in (command or "") for char in _ESCAPE_CHARS):
        other = _argument_scan(command, lower, _ESCAPE_CHARS[1])
        if other[0] != views[0][0]:
            views.append(other)
    return tuple(views)


def git_argument_text(command, lower=True):
    """The normalised text of `_argument_scan`, for the callers that read WORDS out of a command
    (refs, paths, container names) and need not know which of them the shell would parse as code.

    ONE READING PER LINE, because there is more than one (`_ESCAPE_CHARS`). Every caller of this
    searches the text for something it must not miss, and the honest answer to "does this command
    contain X" is yes when ANY shell reads it that way. A newline is where every one of those
    callers already stops, so the readings cannot bleed into each other.
    """
    if len(command or "") > GIT_READ_LIMIT:
        return (command or "").lower() if lower else (command or "")
    return "\n".join(view[0] for view in _scan_views(command, lower))


# git's OWN options — the ones that may stand between `git` and its subcommand. The subcommand
# reader needs to know one thing about each: whether it takes its value as a SEPARATE token,
# because that token is the value and can never be the subcommand (`git -C /repo push` runs push,
# not `/repo`). The `--option=value` spelling carries its own value and needs no entry, and `-C`
# folds onto `-c` under lowercasing — harmless, both take a value.
_GIT_VALUE_OPTIONS = frozenset((
    "-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env",
    "--attr-source", "--super-prefix"))
# ...and the ones that take NO value, so the next token really is the verb. Both lists together are
# what makes an option UNKNOWN mean something: an option in neither is one whose value behaviour
# this reader does not know, and then the following token is ambiguous — see
# `_subcommand_candidates`. Enumerating only the value-taking half is what let
# `git --attr-source HEAD push --force` read its verb as `head` and match no gate at all: every
# option git ships next is a new hole when a list decides applicability by itself.
_GIT_FLAG_OPTIONS = frozenset((
    "-v", "--version", "-h", "--help", "--html-path", "--man-path", "--info-path",
    "-p", "--paginate", "-P", "--no-pager", "--no-replace-objects", "--no-lazy-fetch",
    "--no-optional-locks", "--no-advice", "--bare", "--literal-pathspecs", "--glob-pathspecs",
    "--noglob-pathspecs", "--no-glob-pathspecs", "--icase-pathspecs", "--no-icase-pathspecs"))
# The word `git` as the shell sees it: not a piece of a longer word (`gitk`, `git-lfs`, `foo.git`),
# but reachable through a path (`/usr/bin/git`, `.\git.exe`).
_GIT_WORD_RX = re.compile(r"(?<![\w.-])git(?:\.exe)?(?![\w.-])", re.IGNORECASE)
_SEGMENT_SPLIT_RX = re.compile(r"[&|;\n]")


class _ProgramReader(object):
    """The three things that differ between one program's command line and another's.

    Everything else about reading a command — which `git`/`docker` is the PROGRAM rather than a
    piece of prose, which token is the VERB, what an expansion in the verb position means — is the
    same question with the same fail-closed answer, and it is answered once below. This class
    exists because the SECOND caller proved it: `gate_shell_hygiene`'s docker rule read its verb
    POSITIONALLY (`docker\\s+(?:compose\\s+)?(stop|kill|…)`) and therefore let every global option
    through as a bypass — measured 2026-07-31 as real `gate_shell_hygiene` processes in a repo
    whose own compose project is `myproject`, and with no docker daemon reachable:
    `docker --context remote system prune -af`, `docker -H tcp://x:2375 system prune -af`,
    `docker --log-level debug volume prune` and `docker compose -p other down` were ALLOWED,
    while `docker system prune -af` one word away was refused. That
    is the same defect the git branch of the same file had fixed one rule earlier, so the fix is
    the same reader rather than a second option list.
    """

    __slots__ = ("word_rx", "value_options", "flag_options")

    def __init__(self, word_rx, value_options, flag_options):
        self.word_rx = word_rx
        self.value_options = frozenset(value_options)
        self.flag_options = frozenset(flag_options)


GIT_READER = _ProgramReader(_GIT_WORD_RX, _GIT_VALUE_OPTIONS, _GIT_FLAG_OPTIONS)

# `docker`, and `docker-compose` because the v1 binary is a second spelling of the same daemon
# reach (`docker-compose -p other down`). The suffix guard is the git one: not a piece of a longer
# word, but reachable through a path.
_DOCKER_WORD_RX = re.compile(r"(?<![\w.-])docker(?:-compose)?(?:\.exe)?(?![\w.-])", re.IGNORECASE)
# docker's own options that CONSUME the next token, so that token can never be the verb
# (`docker --context remote system prune` runs `system prune`, not `remote`).
_DOCKER_VALUE_OPTIONS = frozenset((
    "--config", "-c", "--context", "--host", "-l", "--log-level",
    "--tlscacert", "--tlscert", "--tlskey",
    # compose's own, because for the `docker-compose` spelling compose IS the program and its
    # `-p <project>` stands where a verb otherwise would (`docker-compose -p other down`)
    "-p", "--project-name"))
# ...and the ones that take none. An option in NEITHER set leaves the following token ambiguous,
# and `_subcommand_candidates` then returns both readings rather than guessing -- the same
# fail-closed default that keeps `git --attr-source HEAD push` a push.
#
# `-H` AND `-h` ARE IN NEITHER, deliberately, and that is where docker differs from git. This
# reader case-folds, git's `-C` and `-c` both take a value so the fold is harmless, and docker's do
# not: `-H` is the daemon socket and takes one, `-h` is help and takes none. So the fold makes the
# next token genuinely undecidable, and "undecidable" already has an answer here -- both readings.
# Measured before that: `docker -H tcp://x:2375 system prune -af` read its verb as the SOCKET and
# matched no rule.
_DOCKER_FLAG_OPTIONS = frozenset((
    "-D", "--debug", "--tls", "--tlsverify", "-v", "--version", "--help"))
DOCKER_READER = _ProgramReader(_DOCKER_WORD_RX, _DOCKER_VALUE_OPTIONS, _DOCKER_FLAG_OPTIONS)
class _UnresolvedVerb(object):
    """The verb of an invocation the reader could not resolve — an OBJECT, not a string.

    It used to be the string `"<unresolved>"`, justified by a claim about text ("no shell word
    comes out of `_argument_scan` looking like this"). A justification of that shape is worth
    exactly as much as the reader's completeness on the day it was written, and it was already
    false: `git '<unresolved>'` hands git that very word, quotes and all removed, and it came back
    as a RESOLVED subcommand equal to the sentinel. An identity no text can spell needs no such
    claim — `_read_invocations` only ever builds verbs out of slices of the command, and a slice is
    never this object. Equality is identity, so no verb read out of any command can ever match it.
    """

    __slots__ = ()

    def __eq__(self, other):
        return other is self

    def __ne__(self, other):
        return other is not self

    def __hash__(self):
        return id(self)         # hashable: `git_subcommands` puts verbs in a set

    def __repr__(self):
        return "<unresolved>"

    def __str__(self):
        return "<unresolved>"


UNRESOLVED_SUBCOMMAND = _UnresolvedVerb()
# A command the readers will not finish reading in time is one they must not read as harmless.
# `STDIN_LIMIT` bounds what a hook accepts at all (16 MiB) and answers a different question: an
# 8 MiB Write payload is ordinary, an 8 MiB shell COMMAND is not, and the git reading is per-word
# work a line that size makes unaffordable. Measured as real hook processes before this bound and
# before the quadratic tail-copy below was removed: 120 KB of `git ` words took `gate_git` 125.7 s
# and `gate_push_token` 59.6 s, i.e. one and two minutes of a session standing still, bought with
# 120 KB of one word repeated (`HOOK_DEADLINE_SECONDS`; `gate_ledger_valid.TOTAL_BUDGET` exists for
# the same reason). Over the
# bound the answer is ONE unresolved invocation: "this could be any git command", which every gate
# reads as applicable.
#
# WHAT THIS BOUND DOES NOT BOUND, said here because the sentence above reads as if the quadratic
# class were closed and it is not. The READER is linear; a CALLER that walks `Invocation.arguments`
# for every invocation is not, because each access rescans to the end of the SEGMENT (see the
# property below). `gate_push_token._push_invocations` does exactly that, so a single segment with k
# push invocations costs O(k * n). Measured as real hook processes with `$(git push origin main)`
# repeated inside ONE segment (verified with a git shim that a real shell runs those
# substitutions): 64 KB -> rc 2 in 5.4 s, 128 KB -> 26.1 s, 192 KB -> 58.6 s, 256 KB -> past the
# host's 90 s and therefore an ALLOW on ~11 000 real pushes. On the SAME inputs `gate_git` stayed
# at 0.3-0.5 s, which is what points at the caller rather than at this module. 256 KB is half of
# this limit, so the limit does not reach it. This is HEAD's behaviour and not a regression of the
# generalisation (measured identical at HEAD); it is written down rather than left to be found
# again, and closing it means bounding the WORK per caller, not the text length.
GIT_READ_LIMIT = 512 * 1024


class Invocation(object):
    """One program call the shell will run: which VERB, with which ARGUMENTS, inside which
    segment. Not git-specific -- see `_ProgramReader` for what a second program changes."""

    __slots__ = ("subcommand", "resolved", "segment", "_words", "_start")

    def __init__(self, subcommand, resolved, segment, words, start):
        self.subcommand = subcommand
        self.resolved = resolved
        self.segment = segment
        self._words = words
        self._start = start

    @property
    def arguments(self):
        """The tokens after the subcommand, to the end of the segment.

        Built ON DEMAND. Slicing every invocation's tail eagerly is what made the reader
        quadratic: one segment may hold thousands of `git` words and each was handed its own copy
        of the rest of the line — see `GIT_READ_LIMIT` for what that measured."""
        return [self.segment[match.start():match.end()]
                for match in _WORD_RX.finditer(self._words, self._start)]

    def runs(self, *names):
        """True when this invocation runs one of `names`, INCLUDING when its verb is unresolved.

        THE fail-closed half of the definition, and the reason callers must ask this instead of
        comparing `subcommand` themselves. A verb the shell builds at run time (`git $V --force`,
        `git $(echo push)`, ``git `echo push` ``) is not "some other subcommand" — it is an unknown
        one, and every one of those measured as a full ALLOW across all eight PreToolUse hooks
        while `git push --force` was refused by three. "Could be any of them" is the only honest
        reading, and for an unconditional ban it is the only safe one.
        """
        return not self.resolved or self.subcommand in names

    def __repr__(self):
        return "Invocation(%r, resolved=%r)" % (self.subcommand, self.resolved)


def _ends_word(word_view, position):
    """True when the word before `position` may END there — on the WORD VIEW, fail-closed.

    Two answers in one, and the second is the reason this is a function rather than an
    `.isspace()`: whitespace in the word view is a word break the text HAS (quoted and escaped
    whitespace is spelled `\\x00` there, so it is not one), and a character that can become or
    uncover a separator is a word break the text does not DECIDE — `_UNDETERMINED_BREAK_RX`, and
    see its definition for why a backslash is in the other question and not in this one. Reading
    "unknown" as "no break" is what let `git${IFS}push --force origin main` — a real push in a real
    bash — reach not one of the eight PreToolUse hooks, while HEAD's cruder spelling-based reader
    still caught it.

    The cost is confined AND it is carried rather than merely accepted: the `git` gets a verb token
    that begins with the same character, so `_UNDETERMINED_VALUE_RX` calls it unresolved — and
    every refusal that follows carries `UNRESOLVED_VERB_NOTE`, which is the sentence that says to
    spell the subcommand literally. `stop()` appends it, so no gate has to remember to; without it
    the role read the gate's own reason ("no QA Evidence in this project") and had no way to learn
    that the gate applied because the verb was unreadable.
    """
    return (word_view[position].isspace()
            or _UNDETERMINED_BREAK_RX.match(word_view, position) is not None)


def _subcommand_candidates(segment, words, position, reader):
    """Every token that could be the subcommand of the program word ending at `position`, as
    (verb, argument offset, resolved).

    Normally exactly one: the first token that is neither one of the program's own options nor the
    value of one. TWO when an option this reader does not know stands in front of it — such an
    option may or may not take the following token as its value, so which of the two is the verb
    cannot be decided here, and both are returned rather than guessed (`git --attr-source HEAD push
    --force` really pushes, and reading only `head` switched every gate off).
    """
    matches = _WORD_RX.finditer(words, position)
    ambiguous, found = False, []
    for match in matches:
        token = segment[match.start():match.end()]
        low = token.lower()
        if low in reader.value_options:
            next(matches, None)             # this option's VALUE, never the subcommand
        elif token.startswith("-"):
            if "=" not in token and low not in reader.flag_options:
                ambiguous = True            # unknown option: the next token may be its value
        else:
            found.append((low, match.end(), _UNDETERMINED_VALUE_RX.search(token) is None))
            if not ambiguous or len(found) == 2:
                break
    return found


def git_invocations(command, lower=True):
    """Every git invocation in a RAW command, as `Invocation`s.

    THE DEFINITION every git gate decides applicability on, and it is about two things only.

    WHICH WORD IS THE VERB. What makes a command a push is not that the letters `push` occur
    somewhere after the word `git` — it is that `push` is the SUBCOMMAND: the first token after
    `git` that is neither one of git's own options nor the value of one. So `git "push" --force`,
    `git pu''sh --force`, `git pu\\<newline>sh --force`, `git $'push' --force` and
    `git -c user.name=x push --force` are one and the same push, while `git commit -m "merge
    later"` is a commit, because `merge` is not the first non-option token. That last case is the
    false positive the old prose-stripping existed to prevent, and it survives here WITHOUT
    throwing the message away. A verb the shell only builds at run time is UNRESOLVED and matches
    every question (`Invocation.runs`).

    WHICH `git` IS A COMMAND. A command name is a WORD, and a word is what the shell's own word
    splitting produces — which quoting changes and quote marks do not. So a `git` counts exactly
    when it ENDS a shell word: `"git" push`, `sudo "git" push`, `sudo "g"it push` and
    `/usr/bin/git push` are all the program, because in every one of them the word is `git` (or a
    path ending in it), while `git commit -m "docs: git push blocked by the gate"` invokes commit
    and nothing else, because the whole quoted span is ONE word and the `git` sits in its middle
    (real incident — that diagnosis commit re-ran the whole RED pipeline). This replaced a rule
    that asked whether a quoted `git` was the segment's first token, and that rule was the same
    defect one word further along: `sudo "git" push --force origin main` was measured ALLOW on all
    eight PreToolUse hooks, as were `env`, `nohup`, `command` and `timeout` in front of it. What a
    command IS cannot depend on what happens to stand before it. Command substitution is not
    quoting even inside quotes (`_argument_scan`), and a wrapper payload has already been lifted
    out of its quotes (`unwrap_shell_payload`), so `bash -lc "git push"`, `eval "git push"` and
    `echo "git push" | sh` arrive as the code they are.

    BOTH halves default the SAME way when the text runs out of answers, and that default is the
    point of the whole layer. The reader does not ask "is this a push" and shrug; it asks "does
    this line name git, and does the text fix which command it runs" — and a no to the second
    question is a yes to every gate (`Invocation.runs`, `_UNDETERMINED_VALUE_RX`, `_ends_word`,
    `GIT_READ_LIMIT`). Four rounds of review each found the next spelling that read as a resolved,
    harmless, unknown-to-every-gate verb — `${IFS}`, `pus{h..h}`, `$'\\x70ush'`, `pus[h]`, then
    cmd's `p^ush` and `!V!` — because the reader answered no on unsureness, which is fail-OPEN in a
    layer spec II.4 requires to be fail-closed. It answers yes now, and the class is closed by the
    DEFINITION — one predicate derived per shell — rather than by having listed those six.

    ACCEPTED OVER-TRIGGER, in the fail-closed direction, and it is the price of that default. THE
    RULE, not a list of the lines it happens to catch today: a line reads as an invocation when a
    member of `_UNDETERMINED_BREAK_RX` stands immediately after the letters `git`, because there
    the text says neither where that word ends nor what the next one is. Everything that fires
    without running git has exactly that shape — an expansion (`$`, a backtick), a brace, a glob
    or bracket (`* ? [ ]`), cmd's caret, or a variable reference in either cmd form.

    THE SIZE of that price, measured rather than estimated: over a corpus of 121 ordinary
    developer lines — Windows paths, globs, prose about git, sixty-odd git calls whose verb IS
    fixed, comments and separators, wrappers whose payload is not a git call — FIFTEEN fire, and
    every one of them was cross-checked in a real bash AND a real PowerShell as starting no git
    process. Representative rather than exhaustive: `ls git*`, `echo git$VERSION`,
    `grep -rn "git$" .`, `cat git{a,b}.txt`, `echo git%USERNAME%`,
    `echo "use git^ for the first parent"`. A corpus twice this size would find more of the same
    class and none of another; that is what makes it a rule and not a list.

    The CARET is the one member that is a single character rather than a closed construct, and
    that is a fact about cmd (see `_UNDETERMINED_CHARS`), not a lapse: cmd really does write its
    escape alone, so a `^` after `git` really may be a word end. Its paired neighbours cost
    nothing — reading a lone `!` as a metacharacter used to refuse six lines of ordinary prose
    (`echo "I love git!"` and its kind); matched by its FORM, they are silent and every cmd
    attack still answers yes.

    WHERE THAT FORM HAS ITS EDGE, because a rule is only honest with its edge written down:
    `echo "git!x!"` and `echo "git!push!"` DO fire (verb tokens `!x!` and `!push!`, unresolved).
    Two exclamation marks with no space between them are a reference by the definition, and that
    is the right answer rather than a lapse — the same text in `cmd /v:on` really would expand.
    They sit outside the 121-line corpus because nobody writes them, but they are the shape of
    prose that would be refused, and stating that is cheaper than the next round rediscovering it.

    By the same rule a git call whose verb is written that way fires too (`git $VERB`,
    `git pus{h..h}`, `cmd /c "git p^ush"`, `cmd /v:on /c "git !V:~0,4!"`). Every one of those
    costs one command rewritten with the subcommand spelled out, which is exactly what the refusal
    now says to do (`UNRESOLVED_VERB_NOTE`), while the other direction costs the rule.

    A BACKSLASH is deliberately NOT in that shape: it can make a token's VALUE undetermined and it
    can never end the word `git` (`_UNDETERMINED_BREAK_RX`). Asked at the boundary too, it added
    six lines that hold no git call at all — `cd C:\\git\\repo`, `robocopy C:\\git\\a C:\\git\\b /E`,
    `$env:PATH = "C:\\git\\bin;" + $env:PATH` and the like — and those are gone.

    And narrowly the VERB in the other direction as well: `ls $HOME`, `git commit -m "$MSG"`,
    `git log --format=%H` and `git show HEAD^1:file.txt` are untouched, because an expansion in an
    ARGUMENT leaves the subcommand fixed.

    It takes the RAW command and normalises internally on purpose: a split between "normalise" and
    "read" is exactly the seam at which a caller reached for the wrong view and disarmed its gate.

    The SEGMENT (`&`/`|`/`;`/newline-separated) bounds the arguments — `git push && echo x` hands
    `echo x` to nothing — and is returned alongside them because a caller that reads REFS out of
    the command needs exactly the same boundary (`gate_git.target_items`).
    """
    return invocations(command, GIT_READER, lower)


def docker_invocations(command, lower=True):
    """Every `docker`/`docker-compose` invocation in a RAW command, by the SAME definition.

    See `git_invocations` for the whole of it — which word is the program, which token is the verb,
    and why unsureness answers YES. Only the option table differs (`DOCKER_READER`), because that
    is the only thing about a command line that is program-specific.

    The caller that needs this is `gate_shell_hygiene`'s R10: `docker rm`/`stop`/`prune` reach
    every project on the daemon, and its own reader used to find the verb by POSITION.
    """
    return invocations(command, DOCKER_READER, lower)


def invocations(command, reader, lower=True):
    """Every invocation of `reader`'s program in a RAW command."""
    if len(command or "") > GIT_READ_LIMIT:
        return [Invocation(UNRESOLVED_SUBCOMMAND, False, "", "", 0)]
    found = []
    for text, words in _scan_views(command, lower):
        _read_invocations(text, words, found, reader)
    return found


def _read_invocations(text, words, out, reader):
    """One reading of the command, appended to `out`. Linear in the length of the text:
    `_ends_word` answers "does this program word end a word" from one position in the word view,
    and the tokens after it are scanned lazily from that offset instead of being sliced out per
    match."""
    start = 0
    for boundary in itertools.chain(_SEGMENT_SPLIT_RX.finditer(text), (None,)):
        end = len(text) if boundary is None else boundary.start()
        segment, word_view = text[start:end], words[start:end]
        limit = len(segment)
        for match in reader.word_rx.finditer(segment):
            tail = match.end()
            if tail < limit and not _ends_word(word_view, tail):
                continue                    # inside a longer word, so it is text, not the program
            for verb, position, resolved in _subcommand_candidates(
                    segment, word_view, tail, reader):
                out.append(Invocation(verb, resolved, segment, word_view, position))
        if boundary is None:
            break
        start = boundary.end()


def git_subcommands(command):
    """The set of git subcommands a RAW command invokes, for callers that need nothing else.

    An invocation whose verb could not be resolved contributes `UNRESOLVED_SUBCOMMAND`; a caller
    that tests membership against its own set must therefore use `Invocation.runs` instead of
    this, and every gate does."""
    return {invocation.subcommand for invocation in git_invocations(command)}


def wants_push_or_merge(command):
    """True when the command really invokes `git push`/`git merge` (not merely mentions it)."""
    return any(invocation.runs("push", "merge") for invocation in git_invocations(command))


# WHAT A FORCE PUSH IS -- the flags AND the `+refspec` form (`git push origin +main`), in every
# spelling a shell can build one out of. It lives HERE and not in a gate because two gates decide
# on it and they do not ship to the same kits: `gate_git` is absent from the office kit
# (`settings.json` registers `gate_push_token` there and no `gate_git`), so a definition kept in
# `gate_git` is a definition one of the three kits does not have. The office kit is exactly where
# that mattered -- measured 2026-08-02 with a live push approval, `git push --force origin main`
# was answered rc 0 by the only git gate that kit registers.
#
# Matched on the NORMALISED view (`git_argument_text`) and on the raw command, and each reading
# catches what the other cannot. The NORMALISED one carries the spellings that only become
# `--force` once the shell is done with them: a flag broken over a line continuation
# (`--f\<newline>orce`), the PowerShell escape (`--for`ce`), a flag assembled out of adjacent
# quoted pieces (`--fo''rce`). The RAW one is the belt for the opposite risk -- a normaliser may
# drop characters, it may never invent them -- and it is what covers the quoted flags
# (`git push "--force"`, `"+main"`), because the pattern's own `["']` alternatives match those in
# the raw text.
FORCE_PUSH_RX = re.compile(
    r"--force(-with-lease)?|(^|[\s\"'])-f([\s\"']|$)|[\s\"']\+[\w./-]+(:|[\s\"']|$)")


def names_force_push(command):
    """True when this command LINE spells a force push -- one question, one answer, two gates.

    Deliberately a question about the LINE rather than about one invocation: the two readings above
    are readings of a whole command, and re-deriving a per-invocation normalised view would be a
    second answer to the same question, which is what this module exists to prevent. The cost is an
    over-trigger nobody should read as an accident -- a line that pushes normally AND force-pushes
    is refused as a whole, and so is a line whose comment or unrelated flag spells `-f`. For an
    action that is forbidden either way that is the direction to fail in, and it is the behaviour
    `gate_git` has shipped with all along.
    """
    return bool(FORCE_PUSH_RX.search(git_argument_text(command))
                or FORCE_PUSH_RX.search((command or "").lower()))


# The sentence a refusal owes a command whose git VERB the text does not fix. An unresolvable verb
# is a DIFFERENT reason to refuse than "no QA Evidence" or "no quality pipeline", and until this
# existed no gate said so: `_ends_word` promised in a comment that "the gate refuses with 'spell
# the subcommand literally' rather than silently standing down", and the gates measurably said
# "no quality pipeline found (scripts/quality.py)" and nothing else — leaving the role to guess
# why a line it did not think was a push had reached a push gate at all. That is a refusal that
# cannot be complied with, which is the failure mode this layer is least allowed to have.
UNRESOLVED_VERB_NOTE = (
    "NOTE: a `git` call in this command has a SUBCOMMAND the text does not fix — an expansion, a "
    "glob, a brace, an escape or a delayed variable stands where the verb belongs (`git $V`, "
    "`git pus{h..h}`, `git${IFS}push`, `cmd /c \"git p^ush\"`). This gate does not run the shell, "
    "so it reads that as \"could be any git command\", the guarded ones included, and it applies "
    "whether or not you meant one.\n"
    "Remedy: spell the subcommand literally (`git push origin main`) and the gate judges the call "
    "you actually make.\n")


def unresolved_verb_note(command):
    """`UNRESOLVED_VERB_NOTE` when `command` holds a git call whose verb the text does not fix.

    Asked of `git_invocations`, i.e. of the reader that actually decided it — a second rule here
    would be a second answer to the same question, which is how the six hook-local copies of the
    push detection drifted apart in the first place.

    Silent over `GIT_READ_LIMIT`: there every verb is unresolved (`git_invocations` says so), but
    the reason is the length of the line and not how the verb is spelled, so telling that caller to
    spell the subcommand out would be advice that cannot work.
    """
    if not command or len(command) > GIT_READ_LIMIT:
        return ""
    if any(not invocation.resolved for invocation in git_invocations(command)):
        return UNRESOLVED_VERB_NOTE
    return ""


def run_captured(cmd, cwd=None, timeout=60, **kw):
    """subprocess.run with captured TEXT output decoded UTF-8 (lossy, never a crash).

    THE one place hooks run tools and read their output: git and every provider tool emit
    UTF-8, while Windows' locale codec (cp1252) mojibakes umlauts in filenames, branch names,
    commit messages and tool output — three separate audit findings in one week came from
    per-call-site encoding choices. Raises nothing beyond subprocess's own errors
    (TimeoutExpired etc.) — callers keep their existing try/except semantics."""
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, **kw)


# THE HANDOVER MARKER, spelled once for every hook that acts on it. `clear_handover_marker` removes
# it on a genuine restart and `gate_dispatch` refuses a specialist spawn while it exists; the global
# `~/.claude/hooks/handover_guard.py` and the two scaffolds name it too, which is a boundary between
# languages rather than a second opinion. What its presence MEANS is one sentence: an installer ran
# in this session -- a kit install, a preset change or a kit update (`kernel.kitupdate`) -- and no
# session has started since, so the registration this session is running under is not the one on
# disk.
HANDOVER_MARKER = os.path.join(".claude", "HANDOVER_PENDING")

# WHERE THE VERSION ORDERING WENT, and why this is a pointer rather than a function: a kit version
# stamp is ORDERED, not merely equal or unequal (measured 2026-08-02 against a live machine's
# staging -- a 07-18 kit was offered to an 08-02 project as an update, and accepting it prunes the
# V2 hooks while leaving the V2 kernel in place). That rule now has ONE home, `kernel.kitupdate`,
# because the command that REFUSES a downgrade and the briefing that OFFERS an update have to agree
# about a direction, and two copies of an ordering rule is exactly how they would not. The briefing
# asks it as a whole verdict (`kitupdate.relation`, through `_kernel.kernel_module`).


# The reference the constitution stopped carrying. The §2 hook table moved out of the three
# constitutions because they load at every session start and at every subagent spawn, while a table
# of what each gate refuses is needed at exactly one moment: after a refusal. That trade only works
# if the refusal HANDS OVER the location, so the pointer is part of every block rather than a thing
# a role is expected to remember.
REFERENCE_NAME = "ENFORCEMENT.md"


def reference_note():
    """The line every refusal ends with: where the table explaining this mechanism lives.

    DERIVED FROM THIS FILE'S OWN LOCATION, never spelled as a path. The reference ships in the kit's
    `hooks/` directory and the scaffold copies that directory wholesale, so the directory a hook is
    running out of IS the directory the table sits in — `<repo>/.claude/hooks/` in a project,
    `team-kits/<kit>/hooks/` in this repo, and a relocated or copied bundle without either of those
    spellings being written down anywhere.

    Named unconditionally, without asking whether the file is there. A conditional pointer would be
    silent in exactly the case that needs a word — a bundle installed without its reference — and
    the path is where the file BELONGS either way.
    """
    return ("\nWhat this mechanism refuses, on which event, and the condition under which it does "
            "not refuse at all: %s\n"
            % os.path.join(os.path.dirname(os.path.abspath(__file__)), REFERENCE_NAME))


def stop(message, event):
    """Block a post/stop event using the current provider's event-specific contract.

    Codex PostToolUse/SubagentStop consume `decision: block` + `reason`. Claude uses exit 2 with
    stderr for these events. Claude reads exit 2 + stderr as blocking on PreToolUse as well, so
    every guard routes through here too; current Codex builds support that contract and include
    `agent_id` for subagent tool calls.

    THE ONE FUNNEL every refusal goes through, which is why `UNRESOLVED_VERB_NOTE` and
    `reference_note()` are appended HERE and not by each gate: the verb note is about the READING
    this file did, the command it is read off is the one `load()` just parsed, and eight gates each
    remembering to append it is eight chances to forget. A gate whose payload carries no command (a
    Write, an Agent spawn) gets nothing appended, because there is no git call to be unsure about.
    """
    message += unresolved_verb_note(last_command()) + reference_note()
    if (os.environ.get("TEAM_KIT_PROVIDER", "").lower() == "codex"
            and event in ("PostToolUse", "SubagentStop")):
        sys.stdout.write(json.dumps({"decision": "block", "reason": message}) + "\n")
        sys.exit(0)
    sys.stderr.write(message)
    sys.exit(2)
