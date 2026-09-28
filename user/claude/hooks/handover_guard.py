#!/usr/bin/env python3
"""
Global handover guard — BUG-0016, DEC-0032 (soft variant, user-approved 2026-08-10).

WHY THIS IS GLOBAL AND NOT A KIT HOOK. After the entry gate installs a kit and asks the user to
restart, the freshly installed PROJECT hooks are inactive in that same session: Claude Code's
settings watcher covers only directories that existed when the session started, and Auto-Init
creates `.claude/` fresh (measured, staging/BUG-0016/messung-2026-08-10.md). So the only hook that
can act inside that window is one that was already registered before the session began — a hook in
`~/.claude/settings.json`. This file is that hook.

MARKER-GATED, so it is INVISIBLE outside a handover. The scaffold writes `.claude/HANDOVER_PENDING`
into the project as its last act; a project-owned `SessionStart(startup)` hook deletes it on the
next REAL process start (measured: the startup matcher fires only on source=startup, not on
resume/reconnect, so the marker survives a reattach and clears on a genuine restart). With no marker
in the cwd this hook exits 0 immediately — no classification, no cost beyond one `os.path.exists`.

SOFT VARIANT, what it refuses and what it never touches (DEC-0032):
  * ALLOWED even with the marker: writes to the PLAN ARTEFACTS the entry gate hand-writes, because
    the user may keep refining the plan up to the restart (global CLAUDE.md Auto-Init step 3):
    `project_memory/product/masterplan.md`, `project_memory/project_config.yaml`, and the root item
    `project_memory/product/active/PR-0001*`.
  * REFUSED with the marker: product-code writes/edits (any file write that is not a plan artefact),
    specialist SPAWNS (Task/Agent), DERIVATION through the work engine on the shell
    (`scripts/harness.py` / `kernel.cli` for anything other than a read like `doctor`/`--help`):
    creating items, dispatching, running the lifecycle, and — BUG-0017 / TSK-0054 — an
    AskUserQuestion that INITIATES the scope-approval flow, recognised by the kernel's
    approving label `Freigeben [<code>]` in its input (FR-0095 took the `[APR-REQ:<id>]` marker off
    the card). These are the post-handover PM's acts:
    the scope approval is requested and minted by the restarted Project Manager AFTER the restart,
    once the kit hooks are live; here the mint would fail, and the entry agent has been measured to
    re-invent a nonexistent `/hooks` step from that failure (docs/reviews/2026-08-12-bug0017-live-confirm.md).

WHAT THE SHELL READING DOES, exactly — no more (`_handle_shell` and the helpers it names):
  * line continuations are JOINED first, on the raw text, because the shell joins across them;
  * the line is cut into segments at UNQUOTED separator characters (`_SEPARATORS`), and each
    segment is judged on its own, so a read in one never excuses derivation in another;
  * quoted spans are data, and so is the body of a here-document whose TERMINATOR is present in
    the same call — an unterminated one is judged as commands, which over-refuses rather than let
    anything that merely looked like a `<<` swallow the rest (measured, L39);
  * a segment's verb is its first token that is a command NAME — `VAR=value` assignments, a
    leading `(`/`{`, the POSIX reserved words of a compound command and a small wrapper set are
    stepped over, so `do python … ; done` and `(python …)` are judged on `python`; a `case`
    pattern and a function header (`a)`, `f()`) open a second name position after them;
  * a work-engine invocation counts as a READ when a help FLAG appears anywhere (that is what the
    engine does with it) or when a read SUBCOMMAND stands in subcommand position — `capture doctor`
    is not a read. NOT stepped over, and this is the boundary rather than an oversight: see below.
  * THE MARKER ITSELF is refused: a segment that names it with anything other than a known read
    verb, and a file-tool write onto it. Without that, the cheapest way past this hook was to
    switch it off — `rm .claude/HANDOVER_PENDING` and every later call is a no-op (measured).
  * NEVER touched: reading, and NORMAL asking/answering/explaining/plan-refinement. The ONLY
    AskUserQuestion this hook refuses is the one carrying the approving label above; every
    ordinary question (including the entry gate's own "structured PM?" prompt) stays allowed. This
    hook refuses individual TOOL calls only; it never ends the session (Read, Grep, ... stay open).

FAIL-OPEN BY DESIGN, and deliberately so — this is a belt on a WELL-INTENTIONED entry agent that
merely keeps working, not an adversarial sandbox (the true boundary is the restart). Anything it
cannot classify (no marker, a malformed payload, an unresolved path) exits 0. It is NOT a shell
parser and does not claim to see every way a line can start a process. NAMED, unclosed gaps, each
measured (TSK-0031/0032, chains in docs/POST_V2_WISHLIST.md L39):
  * product code written through a raw shell redirect (`echo x > src/foo.py`) — the same class of
    shell write-verb hole the far larger `gate_write_scope` also leaves open. The measured
    product-code vector is the Write/Edit tool, which IS covered.
  * ONE class, several spellings: the verb position is occupied by something this reader does not
    follow into. A shell that runs the string later (`sh -c '…'`, `bash -lc '…'`), a SUBSTITUTION
    that produces the command (`$(…)`, backticks, `<(…)`), a launcher word outside `_WRAPPERS`
    (`nohup`, `timeout 60`, `uv run`, `xargs -I{}`, `eval`), or an encoded/obfuscated form. All of
    these are rc 0 today; `test_handover_guard_wrapped_engine_forms_are_the_named_residue` pins
    them so the boundary cannot move without somebody correcting this paragraph and L39 too.
    Closing them means answering "what will this string later execute", which is the shell-parser
    rabbit hole DEC-0029 decided against — no promised protection without code.
  * SELF-DISABLE THROUGH THE PRECONDITION, the part of that class that is left after the marker
    rule above: the marker is reached without its NAME appearing as a word — `mv .claude
    .claude_off`, `rm .claude/HANDOVER*`, `rm -f .claude/*`, `find .claude -name 'HANDOVER*'
    -delete`, or a path assembled by a substitution. A rule that saw those would have to model the
    file system rather than read words. Measured and pinned by
    `test_handover_guard_marker_residue_is_named_not_closed`; L39 carries the severity.
  * A HALLUCINATED approval question that OMITS the label (BUG-0017 / TSK-0054): the approval-flow
    refusal is keyed on the approving label `Freigeben [<code>]` (until FR-0095 on the `[APR-REQ:<id>]`
    marker), so an approval-looking question that carries no label cannot be told apart from an
    ordinary question and is allowed. Narrow BY DESIGN — the
    alternative is to model intent from free text, which would refuse the entry gate's own questions.
    ONE live entry session has been measured relaying the kernel's approval question into
    `tool_input` with the `[APR-REQ:<id>]` marker byte-faithful, and this hook refused it
    (2026-08-13, docs/reviews/2026-08-13-tsk0054-live-confirm.md). That is one measured relay, not a
    property of relaying, and the older pilot adds nothing here: the entry-session run behind
    EVD-0020 (docs/reviews/2026-08-12-bug0017-live-confirm.md) records only that the approval was
    REQUESTED and that the mint FAILED — whether ITS question carried the marker is recorded
    nowhere, and that run's raw log is gone. So a markerless or mangled relay stays named residue,
    not built protection.
"""
import json
import os
import re
import sys

MARKER = os.path.join(".claude", "HANDOVER_PENDING")

FILE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
SHELL_TOOLS = ("Bash", "PowerShell")
SPAWN_TOOLS = ("Task", "Agent")
ASK_TOOLS = ("AskUserQuestion",)

# The approving label of the kernel's two-phase approval protocol; `gate_approval.py` is its
# authority (`APPROVE_LABEL_RX = Freigeben [<6 hex>]`, the mint code that names the request since
# FR-0095 took the `[APR-REQ:<id>]` marker off the card). Recognised here by the label's SHAPE
# anywhere in the input, not anchored to an option: the entry session has no live kernel to mint a
# real request, so an approval question it raises carries an invented code wherever the model put
# it -- refusing the flow is the point, not validating the code. A normal question never carries this
# protocol token, so this stays narrow (BUG-0017).
_APR_REQUEST_MARKER = re.compile(r"Freigeben \[[0-9a-f]{6}\]")

# The plan artefacts the entry gate writes by hand (global CLAUDE.md Auto-Init step 3; DEC-0032).
# Exact matches for the two singletons; a prefix for the root item so PR-0001.yaml (and any sidecar
# the entry gate writes beside it) is covered. This is the entry-gate contract's own closed set, not
# an open list of special cases.
_PLAN_FILES = ("project_memory/product/masterplan.md", "project_memory/project_config.yaml")
_PLAN_ROOT_PREFIX = "project_memory/product/active/pr-0001"

# What makes a work-engine invocation a READ, split by WHERE it may stand (TSK-0032 round 3 N4).
# A help FLAG counts wherever it appears, because that is measurably what the engine does with it:
# `kernel.cli --root project_memory capture --help` exits 0 printing help, it captures nothing
# (argparse). A read SUBCOMMAND only counts in subcommand position — `capture doctor` runs a capture
# with a stray word, and reading `doctor` anywhere turned that into an allowed "read".
# Matched as whole tokens, never as substrings: `-h` inside `--header` must not excuse a dispatch.
_HELP_FLAGS = frozenset(("--help", "-h"))
_READ_SUBCOMMANDS = frozenset(("doctor", "help"))
# Wrapper tokens to skip when finding the command verb. This one IS an open enumeration and cannot
# be closed — `nohup`, `timeout`, `uv`, `xargs`, `eval` and every future launcher put themselves in
# verb position too. That is why an unlisted wrapper is NAMED as residue in the docstring and in
# POST_V2_WISHLIST L39 rather than answered by lengthening this set. A `VAR=value` assignment is
# recognised structurally instead of listed.
_WRAPPERS = frozenset(("sudo", "env", "command", "exec", "time", "nice"))

# THE GUARD'S OWN PRECONDITION IS A TARGET: delete the marker and every later call is a no-op, so a
# line that touches it is refused unless its verb is a KNOWN READ. The direction of this enumeration
# is what makes it safe rather than the next under-by-one list — an unlisted verb is REFUSED, so a
# reader nobody thought of costs friction, never the guard itself. Measured 2026-08-11 on the
# running hook: `rm`, `rm -f`, `del`, `mv`, `Remove-Item`, `Move-Item` and a redirect onto the
# marker were all rc 0.
_MARKER_WORD = os.path.basename(MARKER).lower()
_READ_VERBS = frozenset((
    "cat", "type", "ls", "dir", "head", "tail", "grep", "egrep", "fgrep", "less", "more", "stat",
    "file", "wc", "find", "test", "get-content", "get-childitem", "get-item", "select-string",
    "test-path", "resolve-path"))

# The reserved words of the POSIX shell command language (Shell & Utilities, 2.9). A compound
# command puts one of these where a simple command puts its NAME, so `do python ... ; done` has
# `python` as its verb and `do` as syntax. The set is closed by the standard — a definition, not a
# list of forms seen so far. Skipping it is what makes for/while/until/if reach their inner command;
# `case` needs the second half as well, because its PATTERN (`a)`) is not a reserved word — that is
# `_name_positions`, and the same half carries a function header (`f()`).
_RESERVED_WORDS = frozenset((
    "!", "{", "}", "case", "do", "done", "elif", "else", "esac", "fi", "for", "if", "in",
    "then", "until", "while"))

# The characters a shell breaks a command line at when they are not quoted. SINGLE characters only:
# `&&`, `||` and `|&` need no entry of their own, because two adjacent separators simply yield an
# empty segment between them, and an empty segment names no engine. Writing them out as well was
# measured to be behaviour-neutral (TSK-0032 rework), so they are gone rather than kept as untested
# decoration. `\r` carries a lone-CR line; a CRLF line is already carried by `\n`.
_SEPARATORS = frozenset(";&|\n\r")

# A line continuation: backslash, optional trailing blanks, end of line. The shell JOINS across it,
# so it must be joined away BEFORE `_norm` — `_norm` turns every backslash into `/` and the
# continuation would become invisible, leaving the engine call in a segment of its own without an
# interpreter in verb position (measured bypass, TSK-0032 rework F1).
_CONTINUATION = re.compile(r"\\[ \t]*\r?\n")

# A here-document redirection and the delimiter word behind it. Three guards on the left, each one
# a measured false body start (TSK-0032 round 3 N1): `(?<![^\s;&|])` demands a REDIRECTION BOUNDARY
# — start of line, a blank, or a separator — which is what keeps the `<<` of an arithmetic shift
# (`$((1<<2))`) out; `(?!<)` keeps the here-STRING `<<<` out, which has no body at all. The right
# side takes the word as written, so a quoted delimiter is recognised AS quoted: the shell does not
# join line continuations inside a `<<'EOF'` body, and it does inside a `<<EOF` one.
_HEREDOC_START = re.compile(r"(?<![^\s;&|])<<(?!<)-?[ \t]*")
_HEREDOC_WORD = re.compile(r"""\A(?:'([^']*)'|"([^"]*)"|([^\s;&|<>()]+))""")
# An unquoted `#` that opens a comment: at the start of a word, so `foo#bar` is not one. The shell
# never runs what follows, and a `<<` inside it starts no here-document.
_COMMENT = re.compile(r"(?:(?<=\s)|\A)#")


def _norm(text):
    return str(text).replace("\\", "/").lower()


def _allow():
    sys.exit(0)


def _refuse(reason):
    sys.stderr.write(
        "[handover] refused: %s\n"
        "A team kit was just installed and you asked the user to restart the session "
        "(.claude/HANDOVER_PENDING is set). Until that restart, this session only refines the plan "
        "and talks — it does not produce the product or derive further work; the freshly installed "
        "project hooks are not active yet (settings-watcher gap, BUG-0016). Report what is still "
        "needed and let the restarted Project Manager do it. Reading, asking and answering are not "
        "affected; the marker clears itself on the next real restart.\n" % reason)
    sys.exit(2)


def _refuse_approval_request():
    """Refuse an AskUserQuestion that initiates the scope-approval flow (BUG-0017 / TSK-0054).

    Its own message, not `_refuse`'s: the reader must be told (a) that scope approval is requested and
    minted by the restarted PM AFTER the restart, and (b) EXPLICITLY that there is no `/hooks` step to
    run — only the restart. The live pilot measured the entry agent inventing `/hooks` from the failed
    mint (docs/reviews/2026-08-12-bug0017-live-confirm.md), so naming it here is the structural answer.
    """
    sys.stderr.write(
        "[handover] refused: this AskUserQuestion initiates the scope-approval flow while a team "
        "kit was just installed and the session is waiting to be restarted (.claude/HANDOVER_PENDING "
        "is set). Scope approval is NOT requested or minted in THIS session: the freshly installed "
        "project hooks are not active yet (settings-watcher gap, BUG-0016), so the mint cannot run "
        "here. The restarted Project Manager requests the scope approval and the kernel mints it "
        "AFTER the restart, once the hooks are live. Do NOT run /hooks — there is no /hooks step and "
        "no hook-bundle, trust or permission ceremony to perform; the ONLY thing to ask of the user "
        "is to restart the session. Normal questions and plan refinement stay allowed; the marker "
        "clears itself on the next real restart.\n")
    sys.exit(2)


def _cwd(data):
    return data.get("cwd") or os.getcwd()


def _marker_present(cwd):
    return os.path.exists(os.path.join(cwd, MARKER))


def _targets(tool_input):
    for key in ("file_path", "notebook_path"):
        value = tool_input.get(key)
        if value:
            yield value


def _rel(path, cwd):
    """The write target relative to the project root, normalised — or None when it will not resolve.

    None fails OPEN (see the module docstring): an unresolvable path is not classified as product
    code, it is simply not judged.
    """
    try:
        absolute = path if os.path.isabs(path) else os.path.join(cwd, path)
        rel = os.path.relpath(os.path.abspath(absolute), os.path.abspath(cwd))
    except (OSError, ValueError):
        return None
    rel = _norm(rel)
    if rel.startswith("../"):
        return None
    return rel


def _is_plan_artifact(rel):
    return rel in _PLAN_FILES or rel.startswith(_PLAN_ROOT_PREFIX)


def _handle_file_write(tool_input, cwd):
    for path in _targets(tool_input):
        rel = _rel(path, cwd)
        if rel is None:
            continue  # unresolvable: not judged (fail-open)
        # Named separately from the line below although both refuse: a write here is aimed at the
        # guard's own precondition, and a refusal that calls it "product code" would send the
        # reader looking for the wrong thing.
        if os.path.basename(rel) == _MARKER_WORD:
            _refuse("'%s' is this guard's own handover marker" % rel)
        if not _is_plan_artifact(rel):
            _refuse("'%s' is product code / derived state, not a plan artefact" % rel)


def _verb(tokens):
    """The command verb: the first token that is a command NAME rather than shell syntax.

    Skipped on the way: `VAR=value` assignments (structural, not listed), the POSIX reserved words
    that open a compound command, and the small wrapper set. A leading `(` or `{` is stripped off
    the token itself, because `(python x)` writes the subshell's opening bracket against the name.
    """
    for token in tokens:
        bare = token.strip("\"'").lstrip("({")
        if not bare:
            continue  # a bare bracket: syntax, not a name
        if "=" in bare and not bare.startswith("-"):
            continue  # VAR=value prefix
        low = os.path.basename(bare).lower()
        if low in _WRAPPERS or low in _RESERVED_WORDS:
            continue
        return low
    return ""


def _blank_quoted(text):
    """`text` with the CONTENT of quoted spans blanked out, plus whether every quote was closed.

    Length-preserving on purpose: an offset in the result is the same offset in the original, so
    every reader below can ask "is this character quoted?" without a second pass. Both callers need
    that — the separator scan (a `;` inside quotes is data, not a separator) and the here-document
    scan (a `<<` inside quotes opens no body).

    The second return value is the honest part: when a quote never closes, this reading is not
    trustworthy, and the callers fall back to the quote-BLIND text.

    THE DIRECTION OF THAT FALLBACK IS NOT THE SAME FOR BOTH CALLERS, and pretending it was is what
    round 3 caught. For the separator scan it means MORE splitting, so more is judged. For the
    here-document scan it means a quoted `<<EOF` becomes visible and opens a body that is not one —
    which would have made the rest of the command disappear. What holds that direction is not this
    function but `_without_heredoc_bodies`, which drops a body only once its terminator has been
    SEEN; with the fallback the terminator is not there, so nothing is dropped.
    """
    out, quote = [], ""
    for char in text:
        if quote:
            out.append(char if char == quote else " ")
            if char == quote:
                quote = ""
        else:
            if char in "'\"":
                quote = char
            out.append(char)
    return "".join(out), not quote


def _heredoc_delimiter(line):
    """The delimiter word of the here-document this line opens, or None.

    Read off the line's QUOTE MASK with comments cut away, so a `<<` that is quoted data or sits in
    a comment opens nothing. The delimiter word itself is then read from the line as written; the
    quotes around it are stripped because they decide EXPANSION inside the body, and this reader
    never expands anything.
    """
    mask = _quote_mask(line)
    comment = _COMMENT.search(mask)
    if comment:
        mask = mask[:comment.start()]
    found = _HEREDOC_START.search(mask)
    if not found:
        return None
    word = _HEREDOC_WORD.match(line[found.end():])
    if not word:
        return None
    return next((group for group in word.groups() if group is not None), None)


def _without_heredoc_bodies(command):
    """`command` with the BODY of every TERMINATED here-document removed — it is data, not commands.

    A body line is not executed by the shell, so judging it is an over-refusal: it hit the ALLOWED
    plan-artefact path (`cat > project_memory/product/masterplan.md <<'EOF' ...`), measured in the
    TSK-0032 rework. The redirection LINE itself stays and is still judged.

    THE TERMINATOR IS REQUIRED, and that is the whole safety of this function (TSK-0032 round 3 N1).
    A body is only dropped once its delimiter line has actually been SEEN; when the input ends
    first, every buffered line is given back and judged. Otherwise anything that merely looked like
    a `<<` swallowed the entire rest of the command — three measured spellings, one of which was a
    QUOTED `<<EOF` made visible again by the unbalanced-quote fallback. The price is an
    over-refusal, and it is the direction this hook wants: a here-document whose terminator is not
    in the same tool call has its body judged as commands.

    THE BODY IS READ LINE BY LINE, never joined across a continuation — measured against a real
    bash (round 3): inside a `<<'EOF'` body a trailing backslash is literal and the next `EOF`
    closes the document (the command after it RUNS, so it must be judged: that was N2), while
    inside a `<<EOF` body the shell joins and swallows further. Stopping at the first delimiter
    line is therefore never earlier than the shell stops and never later — this reader can only
    judge MORE than the shell executes, which is the safe direction and the over-refusal named in
    POST_V2_WISHLIST L39.
    """
    lines = command.split("\n")
    kept, index = [], 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        delimiter = _heredoc_delimiter(line)
        if delimiter is None:
            continue
        body = []
        while index < len(lines):
            candidate = lines[index]
            body.append(candidate)
            index += 1
            if candidate.strip() == delimiter:
                # terminator seen: the buffered body was data after all. Replace it with BLANK
                # lines, not nothing — the line COUNT has to survive, or a later continuation join
                # would bridge the cut this made and glue a real command onto the `cat` segment
                # (round 4 R3-1: the redirection line itself ended on a `\`). Blanks name no engine.
                body = [""] * len(body)
                break
        kept.extend(body)  # blanks when terminated, the whole buffer when the input ran out
    return "\n".join(kept)


def _quote_mask(text):
    """`text` with quoted content blanked when the quoting is readable, and `text` itself when not."""
    blanked, balanced = _blank_quoted(text)
    return blanked if balanced else text


def _segments(command):
    """The command's top-level segments: the spans between UNQUOTED separator characters.

    Two adjacent separators (`&&`, `||`, `|&`) simply yield an empty span between them, which names
    no engine — so the separator set needs single characters only.
    """
    mask = _quote_mask(command)
    found, start = [], 0
    for index, char in enumerate(mask):
        if char in _SEPARATORS:
            found.append(command[start:index])
            start = index + 1
    found.append(command[start:])
    return found


def _tokens(segment):
    """Split a segment at UNQUOTED whitespace, keeping a quoted span whole.

    A quoted argument is one word to the shell, so `"a (b) c"` is a single token that ends in `"`,
    not in `)`, and a `--help` inside it is not a flag of its own (TSK-0032 round 4 R3-2/R3-3 —
    both were the mask going unconsulted at tokenisation). When the quoting does not close,
    tokenising cannot be trusted, so it falls back to a naive split, which judges MORE.
    """
    if not _blank_quoted(segment)[1]:
        return segment.split()
    tokens, current, quote = [], [], ""
    for char in segment:
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
            current.append(char)
        elif char.isspace():
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        tokens.append("".join(current))
    return tokens


def _name_positions(tokens):
    """Every index in a segment where a command NAME can begin.

    The beginning, and whatever follows a token that CLOSES a header rather than being a command:
    a `case` pattern (`a)`) and a function definition (`f()`) both put a word ending in `)` where a
    command name would otherwise stand, and the command comes after it (TSK-0032 round 3 N3). The
    tokens are quote-respecting (`_tokens`), so a `)` in the prose of a quoted argument ends its
    token in a quote, not in `)`, and opens no position (round 4 R3-2).
    """
    yield 0
    for index, token in enumerate(tokens):
        if token.endswith(")") and index + 1 < len(tokens):
            yield index + 1


def _reads_the_engine(tokens):
    """True when this invocation only READS the engine instead of driving it.

    A help FLAG counts wherever it stands (measured: argparse prints help and exits 0 even after a
    subcommand). A read SUBCOMMAND counts only in SUBCOMMAND POSITION — the first word after the
    engine path that is neither an option nor the value of the option before it. That is what the
    shipped read forms look like (`harness.py doctor`, `kernel.cli --root project_memory doctor`),
    and it is what `capture doctor` is not.

    The tokens are quote-respecting (`_tokens`), so a help flag inside a quoted VALUE
    (`--body "see --help for details"`) is one token with the quotes still on it and is not read as
    a flag — argparse would not either (round 4 R3-3).
    """
    bare = [token.strip("\"'") for token in tokens]
    if any(token in _HELP_FLAGS for token in bare):
        return True
    engine = next((index for index, token in enumerate(bare)
                   if token.endswith("harness.py") or token == "kernel.cli"), None)
    if engine is None:
        return False
    after_option = False
    for token in bare[engine + 1:]:
        if token.startswith("-"):
            after_option = "=" not in token  # `--root x` carries its value in the next word
            continue
        if after_option:
            after_option = False
            continue
        return token in _READ_SUBCOMMANDS
    return False


def _segment_drives_engine(segment):
    """True when this single command segment RUNS the work engine (not just names or reads it)."""
    if "harness.py" not in segment and "kernel.cli" not in segment:
        return False  # does not name the work engine
    tokens = _tokens(segment)
    for start in _name_positions(tokens):
        rest = tokens[start:]
        verb = _verb(rest)
        # names the engine but does not RUN it (e.g. `cat scripts/harness.py`, `grep x harness.py`):
        # reading is never derivation. Only a python interpreter or the script itself in verb
        # position drives it.
        if not (verb.startswith("python") or verb in ("py", "pythonw", "harness.py")):
            continue
        if _reads_the_engine(rest):
            continue  # doctor / --help: a read of the engine, not derivation
        return True
    return False


def _segment_touches_the_marker(segment):
    """True when this segment names the guard's own marker with anything but a known READ verb.

    The allowlist runs the other way round from every other set in this file, and that is the point:
    an unlisted verb is refused, so the cost of a reader nobody listed is friction, while the cost
    of a remover nobody listed would be the guard switching itself off.
    """
    if _MARKER_WORD not in segment:
        return False
    for start in _name_positions(segment.split()):
        if _verb(segment.split()[start:]) not in _READ_VERBS:
            return True
    return False


def _handle_ask(tool_input):
    """Refuse only the AskUserQuestion that INITIATES the scope-approval flow (marker present).

    NARROW: keyed on the approval-request marker, so normal asking/answering/plan-refinement — the
    whole point of the soft variant — stays allowed. The residue is named in the module docstring: a
    hallucinated approval question that OMITS the marker cannot be told apart from an ordinary one.
    Fail-open: a payload that will not serialise is not classified.
    """
    try:
        blob = json.dumps(tool_input, default=str)
    except (TypeError, ValueError):
        return  # unserialisable: not judged (fail-open, module docstring)
    if _APR_REQUEST_MARKER.search(blob):
        _refuse_approval_request()


def _handle_shell(tool_input):
    raw = str(tool_input.get("command") or "")
    if not raw.strip():
        _allow()
    # ORDER IS LOAD-BEARING. Here-document bodies are cut out FIRST, on the raw text, because that
    # is where a delimiter is still readable as quoted or unquoted and the shell's own joining rule
    # depends on it (round 3 N2). Only then are continuations joined, and only then does `_norm`
    # run — it turns every backslash into `/`, which would hide both (rework F1).
    command = _norm(_CONTINUATION.sub(" ", _without_heredoc_bodies(raw)))
    # Judge EACH segment on its own (TSK-0031): a routine `cd x && python harness.py capture` or
    # `cat foo | python harness.py capture` must not slip past because the first word is benign,
    # and a read in one segment must not excuse derivation in another.
    for segment in _segments(command):
        if _segment_drives_engine(segment):
            _refuse("this command drives the work engine (item capture / dispatch / lifecycle)")
        if _segment_touches_the_marker(segment):
            _refuse("this command removes or rewrites the handover marker this guard runs on")


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:  # noqa: BLE001 — a guard that cannot read its payload must not block a session
        _allow()
    if not isinstance(data, dict):
        _allow()
    if str(data.get("hook_event_name") or "PreToolUse") != "PreToolUse":
        _allow()
    cwd = _cwd(data)
    if not _marker_present(cwd):
        _allow()  # no handover in progress: invisible no-op
    tool = data.get("tool_name")
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        _allow()
    if tool in FILE_TOOLS:
        _handle_file_write(tool_input, cwd)
    elif tool in SPAWN_TOOLS:
        _refuse("spawning a specialist derives work — that is the restarted PM's act")
    elif tool in SHELL_TOOLS:
        _handle_shell(tool_input)
    elif tool in ASK_TOOLS:
        _handle_ask(tool_input)
    _allow()


if __name__ == "__main__":
    main()
