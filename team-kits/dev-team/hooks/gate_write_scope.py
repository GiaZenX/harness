#!/usr/bin/env python3
"""
Write-scope gate — gate layer 3 of spec II.4, and the home of both preconditions the approval
protocol depends on.

Three jobs, all on PreToolUse — the only event that can actually refuse. Registered
PreToolUse(Edit|Write|MultiEdit|NotebookEdit) for the tool writes and PreToolUse(Bash|PowerShell)
for the shell that writes the same files; the table below says which job belongs to which, and it
says it that way round because the matcher spelling belongs in settings.json, where a test reads
it, and not a second time here, where the last widening of it left this table a tool short:

  the write tools        1. `project_memory/**` is KERNEL-ONLY: no tool writes canonical state,
                            not even the orchestrator's. The one exception is `staging/**`, which
                            spec II.4 defines as explicitly non-canonical — and there a bound
                            specialist may write only under ITS OWN task's key.
                         2. a bound specialist writes only inside its task's `allowed_scope` and
                            never inside `forbidden_scope`; an UNBOUND subagent writes nothing,
                            because there is no scope to check it against.
                         6. ...with ONE window through rule 2, and only one: a role's OWN craft
                            memory directory, and only for a call whose content
                            `guard_memory_budget` really judges. `_own_craft_memory` is the whole
                            of it — the reason, the four derived conditions and the two
                            measurements that forced them (BUG-0047) are there, not here.
  the shell              3. RULE 1, plus RULE 4 below, for the shell — shell writes bypass
                            Edit/Write hooks entirely (guard_harness_selfmod has said so
                            since V1), and the
                            approval protocol's condition (i) is exactly "an agent cannot invoke
                            the hooks or the kernel directly". `handle_shell` decides on what the
                            COMMAND LINE names; it never resolves the bound task, so RULE 2 —
                            `allowed_scope`/`forbidden_scope` — does not exist on this path.
                            Measured 2026-07-31 with a bound specialist whose `allowed_scope` is
                            empty: `echo pwned > src/x.py`, `rm -rf src` and `git commit -am wip`
                            pass all eight registered Bash gates, while the same target refuses
                            through Write. The line above said "the same two rules" and had said
                            it since the gate shipped. The gap is pinned, not merely written
                            down: `tools/test_hooks_v2.py` asserts it as a `known_hole` on
                            `state_write_protection.shell`, which is what keeps
                            `python scripts/harness.py doctor` from reporting that capability
                            green.
                         4. a SUBAGENT may not run the harness commands that ORDER work, nor the
                            ones that INSTALL THE ENFORCEMENT LAYER. Two derived classes, one
                            rule: see `_ORDERING_COMMANDS` and `_INSTALLING_COMMANDS` for what
                            each is and how narrow it is. The constitution row the first makes
                            true is the DELEGATE/ROUTE step of every kit's work loop, which
                            reserves creating the `TSK` to the lead.
                         5. the LEAD lands no production code through a shell REDIRECT. Same file
                            property `guard_pm_scope` applies to the write tools, asked of the
                            same function; what a redirect is, is shell syntax and not a verb
                            list — `_assert_the_lead_lands_no_code`.

WHY THE STATE DIR IS ABSOLUTE, no orchestrator exemption: `approvals/pending/**` holds mint codes
in cleartext, and a writable pending file mints a real approval with a self-consistent consumed
request behind it — the one forgery the provenance check cannot detect. `guard_pm_scope` still
ALLOWS `project_memory/**` for the lead, because in V1 the lead was the state's writer; in V2 the
kernel is, and this gate closes the tool paths to it — every Edit/Write/MultiEdit/NotebookEdit
and every shell write a command line reveals.

WHAT THIS CANNOT CLOSE, measured rather than assumed: an agent that may execute arbitrary code
can always reach the kernel. This gate refuses what a command LINE reveals — an enforcement hook in
an execution position, a copy of the enforcement layer, `python -c` importing the kernel, a
write-capable command naming the state dir. It does NOT refuse a script the agent wrote (or copied)
to an ordinary path and then ran, nor an interpreter reached indirectly (`$(which python)`, `xargs`,
a heredoc).

AND IT DOES NOT REFUSE A WRITE VERB OF THE TOOL'S OWN LANGUAGE. Measured 2026-08-03:
`sed -n 'w kk/g.py' .claude/hooks/gate_approval.py` copies a shipped gate and exits 0 here. The
`_PROGRAM_ARG_VERBS` branch catches a shell REDIRECT OPERATOR hidden inside a quoted program
(`awk 'BEGIN{print > "f"}'`), which is the same `>` this gate already reasons about; `sed`'s `w`,
`awk`'s `print > f` variants, `jq`'s output builtins, `perl -e open`, `python -c` — those are
write verbs of five different LANGUAGES, and the only way to refuse them from a command line is a
list of each language's writing words, which is the shape of check this repo keeps proving wrong
one release later. It stays open on purpose, on the same footing as the rest of this paragraph:
the containment is the permission posture, not a bigger vocabulary. `tools/test_hooks_v2.py`
asserts it as a `known_hole` on `state_write_protection.shell`, so `python scripts/harness.py
doctor` cannot report that capability green while it stands.

RULE 4 REACHES EXACTLY AS FAR AS A COMMAND LINE DOES, which is the same boundary as everything
above it and is worth saying beside the constitution row it backs: a subagent that writes a script
into its own `allowed_scope` and runs it reaches the same kernel functions, and this gate sees a
script name. What IS closed is the typed route and the `python -c` one (`_INLINE_KERNEL_RX`), and
the spawn that a self-made task would exist for is refused outright by `guard_agent_spawn`. So the
row is enforced against the surface a role actually uses and remains policy against a determined
one — not "prevented".

So condition (i) is bounded by the project's PERMISSION posture (settings.json `deny`),
not by hook logic, and `python scripts/harness.py doctor` must weigh that rather than treat this gate's presence as
sufficient. The `known_hole`-marked tests in tools/test_hooks_v2.py enumerate what is still open,
for BOTH capabilities.

NO EXIT FOR A KIT DOCUMENT, AND THE REFUSAL NOW SAYS SO. The entry gate writes the masterplan, the
first root item and `project_config.yaml` by hand, BEFORE the scaffold, when this hook is not
installed yet. It needs no exemption because of that timing — but what follows is a gap, not a
protected window, and until 2026-08-02 the refusal below described it wrongly. Measured in a
scaffolded dev project, all three routes to `product/masterplan.md`: Write rc 2, shell heredoc rc 2,
and `grep -rn masterplan .claude/kernel/*.py` finds no writer at all — while the remedy sent the
role to `python scripts/harness.py <command>`, a surface that has none. `gate_memory_complete`
meanwhile blocks merge AND push for as long as the file carries its template line, and the office
kit's `filing_plan.yaml` is the same class of file.

So the refusal distinguishes the two cases with `kernel.layout.is_project_document` — a definition
derived from the kernel writers' own path builders, not a list of file names. For canonical state
the remedy is the entry point, as before; for a kit document the TOOL route stays refused, which is
what §0 of all three constitutions already instructs ("a gap you report, not an edit you make").
What that document's own COMMAND route is comes from `kernel.layout.partial_writers` (see
`_partial_writers`) and is never restated here — `set-preset` and `project.preset` were the route
out of BUG-0041's dead end, `apply-proposal` is the one out of BUG-0071's, and the sentence that
counted them would be the one that rots. Whether the closing line reads "no route from inside this
session" is that answer's to decide, because both halves of it have now been the wrong one: a
refusal that denies a route the harness has, and one that promises a route it does not. The
permission itself is unchanged: §0 is a constitutional rule that this gate is the enforcement of,
and widening it is a constitution change, not a hook change.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import _kernel
except BaseException as exc:  # noqa: BLE001 — a hook that cannot load must not mean "allow"
    sys.stderr.write("[team-kit hook] refused: could not load hook helpers (%r). Remedy: run "
                     "`python scripts/harness.py doctor`; a partial checkout or half-finished kit update is the "
                     "usual cause.\n" % (exc,))
    sys.exit(2)

import bisect  # noqa: E402
import glob  # noqa: E402
import posixpath  # noqa: E402
import re  # noqa: E402
import shlex  # noqa: E402 — everything after GATE_PREAMBLE, which must stay verbatim

import _compat  # noqa: E402
# The FILE PROPERTY of rule 5, imported rather than restated: `guard_pm_scope` owns "what is
# production code" for the write tools, and a second copy here would be a door with its own idea
# of it. The import is cheap (`_root`, `_audit`, `_compat`, all loaded by then) and runs no code —
# that module's body is constants and defs.
import guard_pm_scope  # noqa: E402
# ...and for the same reason, the directory NAME that makes a path role memory: `guard_memory_budget`
# is the guard that owns agent memory (its budgets, its content rule), so rule 6 below asks it what
# a memory path is instead of carrying a second spelling. Same cost: constants and defs.
import guard_memory_budget  # noqa: E402

HOOK = "gate_write_scope"
# NotebookEdit included: a notebook write is a file write, and a gate that does not see it scopes
# everything except notebooks (`_compat.file_paths` reads `notebook_path` for the same reason).
FILE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
SHELL_TOOLS = ("Bash", "PowerShell")
# the ONE non-canonical subtree inside the state dir (spec II.4 "Vorschlagsbereich")
STAGING = "staging"

# inline python reaching into the kernel LIBRARY. An import/attribute shape, not a bare word, so
# `python -c "print('kernel panic')"` is not a forgery accusation.
_INTERPRETER = r"(?:^|[\s|&;=(\"'/\\])(?:python[0-9.]*|py|pythonw)(?:\.exe)?"
_INLINE_KERNEL_RX = re.compile(
    _INTERPRETER + r"\s+(?:-[^\s]+\s+)*-c\b[^\n]*"
    r"(?:\b(?:from|import)\s+kernel\b|\bkernel\.(?:approvals|state|dispatch|staging)\b)",
    re.IGNORECASE)
# A commit/tag/issue MESSAGE is prose, and prose naming a protected path is not a write into it —
# but ONLY where the VERB in front of the flag actually takes a message. Binding the removal to the
# flag spelling alone was BUG-0020/H34: under `re.IGNORECASE` the `-F` alternative folds onto `rm`'s
# `-f`, `-b` is `cp`'s backup, and the removal deleted the quoted PATH behind them from EVERY reader
# at once — measured as the loss of a canonical item (`rm -f "project_memory/.../DEC-0001.yaml"`
# rc 0, the file gone). `_MESSAGE_FLAG_RX` still finds the flag+span; `_VerbBoundMessageRemoval.sub`
# is what decides, per segment, whether the verb is one that takes a message before it blanks.
# `--body`/`-F`/`--description` stay for the forge CLIs (`gh`/`hub`/`glab`): a refusal's own remedy
# asks the agent to REPORT the defect, and an issue body quoting the command would otherwise be
# refused by the gate it is reporting.
_MESSAGE_FLAG_RX = re.compile(
    r"(?:-m|--message|-Message|--description|--body|-b|--notes|-F)\s*=?\s*"
    r"""(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')""",
    re.IGNORECASE)
# What ends a command SEGMENT on a shell line, so the verb in front of a flag can be read off the
# segment the flag sits in. `&&`/`||` are covered by the single characters; a `cd` movement is not
# a segment break (it does not change WHICH verb owns the following flag).
_SEGMENT_BREAK = "|&;\n\r"


def _segment_break_positions(text):
    """Indices where a command segment BEGINS: 0, and just after every UNQUOTED separator.

    Quote-aware, so a separator inside a message does not split the segment it belongs to
    (`git commit --author "a;b" -m "…"` is one segment, not three) — the same reason the tokeniser
    masks quoted spans before it splits. A backslash escapes the next character only inside a
    double-quoted span, which is where the POSIX shell keeps its escaping meaning.
    """
    starts = [0]
    quote = None
    index, length = 0, len(text)
    while index < length:
        char = text[index]
        if quote:
            if char == quote:
                quote = None
            elif char == "\\" and quote == '"':
                index += 1  # skip the escaped character
        elif char in "'\"":
            quote = char
        elif char in _SEGMENT_BREAK:
            starts.append(index + 1)
        index += 1
    return starts


class _VerbBoundMessageRemoval:
    """The kits' message-argument prose removal, bound to the VERB and not to the flag spelling.

    Quacks like a compiled pattern for the ONE method its two callers use — `.sub(repl, text)`, so
    it drops in where `re.compile(...)` stood without either caller changing. `handle_shell` below
    calls it, and so does the repo's `_harness._prose_removed`, which IMPORTS this object: that gate
    is the one BUG-0020 walked through when it deleted a canonical decision item, so binding the
    removal here closes the hole for it too, without a second answer to "what is prose" living
    in `.claude/` (H15).

    The verb test lives INSIDE `.sub` rather than in a lookbehind the regex engine cannot express
    (a verb is variable-width): the span is blanked, the verb and flag around it are LEFT for the
    readers (so `gate_commit_evidence` still locates the commit and orders the tree writes around
    it), and after a non-message verb the quoted operand stays visible and is refused.
    """

    def sub(self, repl, text):
        text = text or ""
        if not _MESSAGE_FLAG_RX.search(text):
            return text
        starts = _segment_break_positions(text)

        def _blank(match):
            begin = starts[bisect.bisect_right(starts, match.start()) - 1]
            stage = _compat.shell_words(text[begin:match.start()], _lex)
            return repl if _stage_takes_a_message(stage) else match.group(0)

        return _MESSAGE_FLAG_RX.sub(_blank, text)


_MESSAGE_ARG_RX = _VerbBoundMessageRemoval()


def _norm(path):
    """Case-folded, then forward-slashed — in that ORDER.

    The FS on Windows is case-insensitive, so a lexical comparison that is not was no comparison at
    all (`Project_Memory/**` was writable). And `ntpath.normcase` turns a forward slash back into
    a backslash, so slashing first and normcasing second silently undoes the slashing.
    """
    # .lower() as well as normcase: normcase is IDENTITY on darwin, and APFS is
    # case-insensitive by default, so a Windows-only fold would leave macOS exposed
    # (guard_harness_selfmod uses an unconditional .lower() for the same reason).
    return os.path.normcase(str(path)).replace("\\", "/").lower()


def _repo_relative(path, root, fold=True):
    """(rel, undecidable). `rel` is the repo-relative path; `undecidable` says the comparison could
    not be made at all.

    REALPATH, not abspath: a directory junction (`mklink /J pm project_memory`, no admin needed)
    and an extended-length `\\\\?\\C:\\...` spelling both reach the same file while looking like
    another path. `_root.find_repo_root` stays lexical on purpose — only the TARGET side needs
    resolving, exactly as `_kernel._same_file` argues.

    `fold=False` keeps the SPELLING. Every consumer of the folded form compares against a
    normcased entry or an `IGNORECASE` pattern, but rule 5 hands its answer to
    `guard_pm_scope.production_code`, whose ALLOW list is case-SENSITIVE on purpose (folding it
    would widen it on Linux, where `Docs/` really is a different directory) — a folded `Docs`
    would have read as the lead's own area and let a code write through.
    """
    try:
        target = os.path.realpath(os.path.abspath(str(path)))
        rel = os.path.relpath(target, os.path.realpath(root))
    except (OSError, ValueError):
        return None, True
    rel = _norm(rel) if fold else str(rel).replace("\\", "/")
    if rel.startswith("../"):
        return None, False  # genuinely outside the repo -- other guards own that
    return rel, False


def _state_relative(rel):
    """The path relative to the state dir, or None when it is outside."""
    state = _norm(_kernel.STATE_DIRNAME)
    if rel == state:
        return ""
    prefix = state + "/"
    return rel[len(prefix):] if rel.startswith(prefix) else None


def _scope_entries(task, field):
    """Scope entries, normalised. Refuses a blank entry rather than reading it as "everything".

    `allowed_scope: [""]` (or `"."`, or `"/"`) used to grant the whole repo, while the
    empty-LIST case correctly blocked -- one stray `- ""` in a YAML list silently switched gate
    layer 3 off for that task, which is the opposite of the author's intent two lines away.

    HOW MANY ENTRIES THE FIELD HOLDS is `backlog_types.field_elements` and not `for raw in value`
    (BUG-0015): a scope written as a bare string became one entry per LETTER, and a letter matches
    no path -- so `forbidden_scope: secrets` forbade nothing while the task kept writing, measured
    `secrets/keys` rc 0 against rc 2 for the same task with `[secrets]`. A word carrying `/` or
    `*` hid that: those letters are themselves unusable entries, so the refusal below fired for
    the wrong reason. Both directions are in
    `test_hooks_v2.test_a_scalar_scope_decides_like_a_one_element_list`.

    The kernel is asked for the answer rather than a fourth copy of it. Every caller resolves its
    task through the kernel, so it is loaded here. Where it is NOT, `kernel_module` raises
    `KernelUnavailable` and the direction is refusal, from two arms that are both live by the time
    this runs: `_kernel.fail_closed()` wraps the handler and answers `internal error
    (KernelUnavailable: ...)` with exit 2, and for anything raised outside that guard the
    `sys.excepthook` installed by `import _kernel` does the same. Measured with
    `$HARNESS_KERNEL_PATH` pointed at an empty directory: rc 2 on every write payload.
    """
    entries = []
    field_elements = _kernel.kernel_module("backlog_types").field_elements
    for raw in field_elements(task.get(field)):
        entry = str(raw).replace("\\", "/")
        # strip a literal "./" prefix -- `lstrip("./")` strips a character SET, which turned
        # ".env" into "env" and ".github/workflows/" into "github/workflows/"
        while entry.startswith("./"):
            entry = entry[2:]
        entry = _norm(entry).strip().rstrip("/")
        if entry in ("", ".", "*"):
            _kernel.block(
                HOOK,
                "%s has an unusable %s entry (%r): blank, `.`, `/` and a bare `*` cannot "
                "mean anything definite, and were read as 'the whole repository' -- refused "
                "instead (spec II.4 is fail-closed). Write `**` if that is really the intent."
                % (task["id"], field, raw),
                remedy="name real paths; re-plan the task in DRAFT to fix its work order.")
        entries.append(entry)
    return entries


def _matches(rel, entry):
    """Prefix match, or glob match when the entry uses `*`.

    Globs are supported rather than rejected because `**` is the notation everywhere a PM reads it
    -- the constitution row, guard_pm_scope's message and this gate's own docstring all write
    `project_memory/**`. Treating it as literal text made `allowed_scope: ["src/**"]` a dead task
    and `forbidden_scope: ["secrets/**"]` silently unprotected.
    """
    if "*" not in entry:
        return rel == entry or rel.startswith(entry + "/")
    pattern = "".join(
        ".*" if part == "**" else ("[^/]*" if part == "*" else re.escape(part))
        for part in re.split(r"(\*\*|\*)", entry))
    # no trailing `(?:/.*)?`: with it, `src/*` matched `src/sub/deep/a.py` and a bare `*`
    # granted the whole repo at any depth -- only `**` may widen.
    return re.fullmatch(pattern, rel) is not None


def _bound_task(data, root):
    """The task the calling agent is bound to, or None.

    `agent_id` is present only inside a subagent call (verified in a real run and by spike S3), so
    a missing one means the ORCHESTRATOR -- scoped by guard_pm_scope, not here.
    """
    if not os.path.isdir(_kernel.state_dir(root)):
        return None
    agent_id = data.get("agent_id")
    if not agent_id:
        return None
    dispatch = _kernel.kernel_module("dispatch")
    return dispatch.task_for_agent(_kernel.open_state(root), agent_id)


def _assert_not_forbidden(rel, task):
    """`forbidden_scope` is checked BEFORE the staging exemption.

    Otherwise the two branches were exclusive and a forbid could never reach a state path, so a
    `forbidden_scope` naming the state dir was a silent no-op. A PM must be able to deny staging to
    a task -- and does so by naming it: `project_memory/staging/`, or `project_memory/` for the
    whole tree. Note that forbidding `project_memory/` therefore denies STAGING too, which is the
    honest reading; canonical state is already unconditional, so a forbid there would be redundant
    if it meant anything less.
    """
    if task is None:
        return
    for entry in _scope_entries(task, "forbidden_scope"):
        if _matches(rel, entry):
            _kernel.block(HOOK, "'%s' is in %s's forbidden_scope (%s)." % (rel, task["id"], entry),
                          remedy="this path is out of bounds for this task; report it instead of "
                                 "working around it.")


def _is_project_document(root, inside):
    """Is this state-relative path a kit DOCUMENT rather than canonical state?

    Asked of `kernel.layout`, which derives it from the kernel writers' own path builders — this
    gate must not carry a second opinion about what the kernel writes, and least of all a list of
    the three file names that surfaced the dead end.

    A kernel that cannot be reached answers NO, which keeps the refusal: `_kernel.kernel_module`
    raises `KernelUnavailable` and the preamble turns that into exit 2 anyway, but the explicit
    fallback says which direction this predicate fails in.
    """
    try:
        layout = _kernel.kernel_module("layout")
    except Exception:  # noqa: BLE001 — no kernel, no carve-out (fail-closed)
        return False
    return layout.is_project_document(_kernel.state_dir(root), inside)


def _partial_writers(root, inside):
    """The sentence naming any command that writes a declared part of this document, or "".

    The refusal below used to end "and NO `harness.py` command writes it either", which was true of
    every kit document until `set-preset` began writing `project.preset` (BUG-0041). A refusal that
    denies a route the harness HAS teaches a role to stop believing refusals, so the answer is
    asked of `kernel.layout.partial_writers` — which asks the writing module itself — instead of
    being restated here. No writer, no sentence: the ordinary document refusal is unchanged.

    THE STATE DIRECTORY IS PASSED, and that is what makes the answer right for a writer that owns no
    single named file: `apply-proposal` writes any kit document it can COMPARE and refuses one it
    cannot (BUG-0071), which is a fact about the file rather than about its name. Without the root
    such a route is left out of the answer, so an unreachable kernel still names nothing.
    """
    try:
        layout = _kernel.kernel_module("layout")
        writers = layout.partial_writers(inside, _kernel.state_dir(root))
    except Exception:  # noqa: BLE001 — an unreachable kernel names no route (fail-closed)
        return ""
    if not writers:
        return ""
    return (" WHAT DOES HAVE A ROUTE, and it is not this write: %s -- and that command asks the "
            "USER first."
            % "; ".join("`python scripts/harness.py %s` writes %s into it"
                        % (writer["command"], writer["field"]) for writer in writers))


def _assert_state_write_allowed(rel, inside, task, data, root):
    """The state dir is the kernel's. Only `staging/<own key>/` is an agent's to write."""
    parts = [p for p in inside.split("/") if p]
    if not parts or parts[0] != _norm(STAGING):
        if _is_project_document(root, inside):
            # A KIT DOCUMENT, and the honest refusal for one. Sending a role to the entry point
            # here was the measured defect: no `harness.py` command writes this file, so the
            # remedy named a route that does not exist and the merge gate that reads the file
            # blocked forever. §0 of every constitution already says what to do instead.
            #
            # AND THE MIRROR IMAGE OF IT, once such a route existed (BUG-0041, then BUG-0071): the
            # closing sentence and the remedy are DERIVED from `_partial_writers` now, because
            # "this write has no route" was a blanket claim that had become false for every
            # document the kernel can compare — and a refusal that hides the one command a role
            # needs sends it to the user's text editor for the fifth time this month.
            routes = _partial_writers(root, inside)
            _kernel.block(
                HOOK,
                "'%s' is a kit DOCUMENT inside the write-locked state directory — prose or "
                "configuration, not a typed item. Being a document is no exception: this gate "
                "refuses the write (constitution §0), and the TOOL route into such a file does "
                "not exist — the kernel has a path builder for every canonical file and none for "
                "this one.%s"
                % (rel, routes or " No `python scripts/harness.py` command writes this one "
                                  "either, so this write has no route from inside this session, "
                                  "and this refusal is not one to work around."),
                remedy=("take the route named above: stage what the file should say and run that "
                        "command, which asks the USER before it writes. Anything it does not "
                        "cover is the user's own edit, outside this session — report that as the "
                        "gap it is, and say in the same breath if a merge gate is blocking on the "
                        "file, because retrying the write changes nothing." if routes else
                        "report the gap to the user and name this file. It is filled by the entry "
                        "gate BEFORE the kit is installed, or by the user in an editor outside "
                        "this session; `init_project_memory` is copy-if-absent and will not "
                        "overwrite what they write. If a merge gate is blocking on its content, "
                        "say that in the same breath — retrying the write or the push changes "
                        "nothing."))
        _kernel.block(
            HOOK,
            "'%s' is canonical project state — only the kernel writes it (spec II.4). A tool write "
            "here would bypass the status automaton, the approval hashes and the index; and "
            "`approvals/pending/**` in particular holds mint codes, so a writable one forges a "
            "user approval outright." % rel,
            remedy="write it through the entry point: `python scripts/harness.py <command>`, "
                   "run from the project root and never with `--root` (this gate refuses a "
                   "write-capable pipeline that NAMES the state directory, and the entry point "
                   "resolves it itself). `python scripts/harness.py --help` lists the surface it "
                   "HAS, and is the ONLY authority on it -- this message used to name the members "
                   "and went stale the day three commands shipped, which is how a role learns that "
                   "an operation with a command has none. "
                   "`approve` is SPLIT rather than absent: `request-approval` opens the "
                   "kernel-generated question and the USER mints it by answering, which is "
                   "why no command mints. Proposals that are not canonical yet belong in the "
                   "staging area, under the key this agent's own task owns.")
    if len(parts) < 2:
        # THE PLACE IS COMPOSED WHERE IT IS KNOWN AND NAMED NOWHERE WHERE IT IS NOT (DEC-0024): a
        # remedy that spells the key as a slot for the reader to fill is a name the reader picks.
        _kernel.block(HOOK, "'%s' would write the staging ROOT — staging is keyed per task or per "
                            "root item (spec II.4)." % rel,
                      remedy=("write under project_memory/staging/%s/." % task["id"]
                              if task is not None else
                              "write one directory below the staging root, under the key this "
                              "agent's own task owns; the staging root itself holds no files."))
    key = parts[1]
    if task is not None:
        # spec II.4 names BOTH keys: `staging/<task_id>/` for a specialist's proposal and
        # `staging/<ROOT-ID>/` for a pre-task artefact (the class-small WFR before scope approval)
        own = {_norm(task["id"]), _norm(task.get("product_requirement") or "")}
        if key not in own:
            _kernel.block(
                HOOK,
                "'%s' writes another task's staging area: this agent holds %s (root %s), not %s. "
                "Staging is per task so one specialist's proposal cannot be mistaken for another's."
                % (rel, task["id"], task.get("product_requirement"), key),
                remedy="write under project_memory/staging/%s/." % task["id"])
    elif data.get("agent_id"):
        _kernel.block(
            HOOK,
            "'%s': this subagent is not bound to any task, so there is no staging key it owns "
            "(spec II.4 gate 3). It was either started outside the dispatch gate, or two same-role "
            "dispatches made its binding ambiguous and the kernel refused to guess." % rel,
            remedy="dispatch the specialist through the harness; dispatch tasks of the SAME role "
                   "sequentially.")


# THE HALF OF THIS BRANCH'S REFUSAL THAT WAS SIMPLY WRONG (BUG-0047, hole list L6). A role updating
# its own craft memory from a shell met "hooks and settings are maintained by the scaffold ... a copy
# of the layer runs outside every path check" — a reason that is false of `agent-memory/`, which is
# neither settings nor code, and a remedy that named no route while the role's own text prescribed
# the write. The DECISION is unchanged and stays: `handle_shell` never resolves a role, so a command
# line cannot be scoped to one role's directory, and a window here would open every role's memory to
# every caller. What changes is that the refusal now names the door that exists. Written as a
# CONDITIONAL sentence rather than decided per path: this branch would have to re-read the line to
# tell a memory path from a hook path, and a second path reader in this gate is the thing that keeps
# going wrong — a conditional is true of every refusal it is appended to.
_CRAFT_MEMORY_HAS_A_DOOR = (
    "If what you are writing is a SUBAGENT's own craft memory (the `agent-memory/<its role>/` tree "
    "beside the installed role definitions), that has a door and this is not it: the Write/Edit "
    "TOOL, where this gate scopes a subagent to its own role's directory — and there only to the "
    "craft topics `guard_memory_budget` judges, so a `notes.txt` beside them is refused through "
    "that door too. A shell line carries no role identity for it to scope by, which is why the "
    "shell stays shut for everyone. (The lead is not scoped to one role there through EITHER door "
    "— rule 2 never bound it and rule 6 does not either.)")


def _own_craft_memory(rel, path, data, root):
    """RULE 6 — is this the CALLING ROLE's OWN craft memory?

    THE ONE THING OUTSIDE A TASK SCOPE **AND OUTSIDE THE STATE DIRECTORY** a specialist writes.
    The other exception is inside it and belongs to rule 1 (`staging/<its own key>/`), so this is
    not "the only path a work order does not name" — saying that was measurably wrong in this
    gate's own first cut. It is a window rather than an exemption: it opens for one directory, the
    one belonging to the role this very call runs as.

    Measured before it existed (BUG-0047, pilot 3 B6), in a scaffolded project against the
    project's own hooks: a bound backend-developer writing
    `.claude/agent-memory/backend-developer/MEMORY.md` was rc 2 "outside TSK-0001's allowed_scope"
    while its task ran, and rc 2 "this subagent is not bound to a task" once it had submitted —
    so the duty its role text prescribes ("consult your agent memory before, update it after") had
    no moment at which it could be discharged, and the two specialists of that run ended with zero
    memory files. Nothing else refused the write: the other four registered Write gates returned 0
    and `guard_harness_selfmod` exempts this tree by name.

    FOUR CONDITIONS, ALL DERIVED. The first three bound WHO and WHERE, because the risk this window
    carries is one role writing ANOTHER's memory — craft prose the other loads at its next spawn,
    i.e. an instruction channel. The fourth bounds WHAT, and it is the one this gate first left
    out:

      * the ROLE is the one the payload names (`agent_type`), which the provider sets and the model
        does not; `tools/provider_observations.json` records that a subagent's PreToolUse payload
        carries it non-empty, and `_compat.calling_subagent` already decides rule 4 on the same
        field. A single path segment, or nothing — a name with a separator in it would compose a
        prefix pointing elsewhere.
      * the role EXISTS as one of ours, by the predicate `gate_subagent_output` uses: an installed
        definition. WHERE those live comes from the installer that puts them there
        (`kernel.presets.AGENTS_DIR`), so a kit that moved them moves this with it.
      * the DIRECTORY is that role's memory directory beside them — `guard_memory_budget.MEMORY_DIR`
        under the same provider directory the definitions sit in. That anchoring is what keeps an
        invented `src/agent-memory/<role>/` outside the window: there is no role definition beside
        it, so it is an ordinary write and the task scope judges it.
      * the CONTENT GUARD REALLY JUDGES THIS CALL — `guard_memory_budget.judges_this_write`, which
        is where that question and its measurement live. This gate widened WHO may write on the
        stated ground that the budget guard still owns WHAT lands there; the first cut asserted
        that ground instead of asking for it, and the shapes that guard does not model went through
        both gates at once. Asking makes the two fail in the same direction.

    An unreachable kernel answers NO and the write falls back to the scope check, which refuses it.
    `tools/test_hooks.py::test_a_role_writes_its_own_craft_memory_and_only_its_own` holds every
    direction of this in a scaffolded project, including the ones the window must NOT open.
    """
    role = str(data.get("agent_type") or "").strip()
    if not role or "/" in role or "\\" in role or role in (".", ".."):
        return False
    try:
        agents = _kernel.kernel_module("presets").AGENTS_DIR.replace("\\", "/")
    except Exception:  # noqa: BLE001 — no kernel, no window (fail-closed)
        return False
    if not os.path.isfile(os.path.join(root, *(agents.split("/") + [role + ".md"]))):
        return False
    own = _norm(posixpath.join(posixpath.dirname(agents),
                               guard_memory_budget.MEMORY_DIR, role))
    if not (rel == own or rel.startswith(own + "/")):
        return False
    # THE NAME IS THAT GUARD'S TO DERIVE, not this one's to hand over. `rel` here is
    # realpath-resolved (`_repo_relative`) and that module resolves with `abspath`, so passing
    # `rel` asked it about a string it would never judge — measured as an open window under an
    # NTFS alternate data stream and an 8.3 short name. `guard_relative` carries both.
    return guard_memory_budget.judges_this_write(data, path)


def _assert_in_scope(rel, task):
    """A bound specialist writes only where its work order says (spec II.4 gate 3)."""
    allowed = _scope_entries(task, "allowed_scope")
    if not allowed:
        _kernel.block(HOOK, "%s has an empty allowed_scope, so nothing is in scope for it "
                            "(fail-closed)." % task["id"],
                      remedy="re-plan the task in DRAFT with an allowed_scope.")
    if any(_matches(rel, entry) for entry in allowed):
        return
    _kernel.block(
        HOOK,
        "'%s' is outside %s's allowed_scope (%s) — refused. A specialist writes what its work "
        "order says it writes; anything else is a scope change, and scope changes are the user's."
        % (rel, task["id"], ", ".join(allowed)),
        remedy="if this file really belongs to the task, re-plan it in DRAFT; otherwise report the "
               "gap rather than widening it.")


def handle_file_write(data):
    root = _kernel.find_repo_root(data.get("cwd"))
    paths = _compat.file_paths(data)
    if not paths:
        sys.exit(0)
    task = _bound_task(data, root)
    for path in paths:
        rel, undecidable = _repo_relative(path, root)
        if undecidable:
            _kernel.block(
                HOOK,
                "'%s' cannot be resolved against this repo, so it cannot be checked against the "
                "state directory or a task scope — refused rather than skipped (spec II.4 "
                "fail-closed)." % path,
                remedy="use a normal path inside the project.")
        if rel is None:
            continue  # genuinely outside the repo -- other guards own that question
        _assert_not_forbidden(rel, task)
        inside = _state_relative(rel)
        if inside is not None:
            _assert_state_write_allowed(rel, inside, task, data, root)
        elif _own_craft_memory(rel, path, data, root):
            # RULE 6 — the role's own craft memory, and it stays open on BOTH sides of the
            # hand-back: `submit-result` removes the lease, so after it there is no task to scope
            # against and this is the only path outside the state directory the role still has.
            # `forbidden_scope` was already asked above, so a work order can still deny it.
            continue
        elif task is not None:
            _assert_in_scope(rel, task)
        elif data.get("agent_id"):
            _kernel.block(
                HOOK,
                "'%s': this subagent is not bound to a task, so it has no write scope at all "
                "(spec II.4 gate 3 is fail-closed — an unattributable write is refused rather "
                "than allowed)." % rel,
                remedy="dispatch specialists through the harness so their writes can be attributed "
                       "to a task; dispatch same-role tasks sequentially.")
    sys.exit(0)


# --- shell analysis -----------------------------------------------------------
#
# Three designs deep, and each rewrite was forced by a measurement rather than taste:
#   1. a list of write VERBS  -> lost to the next verb every time (`cp -r .claude/hooks` refused,
#      `cp -r .claude` allowed one token away)
#   2. inverted, regex-split  -> a PIPE was read as a segment boundary, so `cat <hook> | tee copy`
#      and `ls .claude/hooks/*.py | xargs rm -f` passed — the second DELETES the enforcement layer
#   3. this one: TOKENISE first, then judge a whole PIPELINE as one unit.
# Tokenising also fixes the mirror-image failure: a quoted `|` (`grep -E 'PR|SR' project_memory/x`)
# was split into nonsense and refused, i.e. the gate blocked the exact inspection its own message
# promises stays allowed.

# Protected trees, derived from ONE list so the shell rule and guard_harness_selfmod cannot drift:
# these are the paths that guard already refuses to Edit/Write.
_ENFORCEMENT_PATHS = (".claude", ".codex", ".agents/skills", ".github/hooks", ".github/agents")
# `.github/workflows` is deliberately NOT here: guard_harness_selfmod allows it, and a shell rule
# stricter than the file rule teaches an agent to route around the shell.
_ENFORCEMENT_RX = re.compile(
    r"(?:^|[\s\"'=(/\\])(?:%s|team-kits)(?=[\\/\s\"';|&]|$)"
    % "|".join(re.escape(p).replace("/", r"[\\/]") for p in _ENFORCEMENT_PATHS),
    re.IGNORECASE)
_STATE_RX = re.compile(r"\bproject_memory\b", re.IGNORECASE)

# THE VERBS THAT MOVE THE SHELL'S BASE, and what each of them does to it. ONE mapping instead of
# the three enumerations this used to be -- a tuple of spellings in `handle_shell`, a `== "popd"`
# in `_walk`, and four of the same words inside `_READ_ONLY_VERBS` -- because each of those was a
# separate place to forget a spelling, and each of them HAD forgotten the same two: PowerShell's
# written-out `Push-Location` and `Pop-Location` (`BUG-0285`). `cd`'s cmdlet name is
# `Set-Location`; its aliases are `cd`, `chdir` and `sl`, and `pushd`/`popd` are the aliases of
# `Push-Location`/`Pop-Location`. The kind is what `_walk` asks about, so no reader has to know
# which spelling is which alias.
#
# AN ENUMERATION IT REMAINS -- nothing in a command line says whether a program changes the
# directory -- so it carries the tripwire CLAUDE.md asks for, measuring BOTH ends: every spelling
# here really moves this gate's base, and a word that is not here does not
# (`tools/test_hooks.py::test_every_directory_verb_moves_this_gates_base_and_no_other_word_does`).
_DIRECTORY_VERBS = {
    "cd": "set", "chdir": "set", "sl": "set", "set-location": "set",
    "pushd": "push", "push-location": "push",
    "popd": "pop", "pop-location": "pop",
}
# Verbs that cannot modify anything. Everything NOT here counts as write-capable — the fail-closed
# direction: a tool nobody has classified is refused until someone decides it is safe.
_READ_ONLY_VERBS = frozenset(tuple(_DIRECTORY_VERBS) + (
    "cat", "type", "bat", "head", "tail", "less", "more", "wc", "nl", "od", "xxd", "strings",
    "grep", "egrep", "fgrep", "rg", "ag", "ack", "diff", "cmp", "comm", "file", "stat",
    "ls", "dir", "tree", "basename", "dirname", "realpath", "readlink", "pwd", "du", "df",
    "sort", "uniq", "cut", "tr", "jq", "yq", "test", "echo", "printf", "base64", "awk",
    # conditionally read-only -- see _WRITE_FLAGS, which is what actually decides for these
    "sed", "find",
    "md5sum", "sha1sum", "sha256sum",
    # PowerShell
    "get-content", "get-childitem", "select-string", "test-path", "get-item", "resolve-path",
    "get-filehash", "compare-object", "measure-object", "select-object",
    # `Out-Null` is the null device in cmdlet form — the same definition `_null_sinks` states for
    # the redirect form, reached through a pipe instead of a `>`, and retaining just as little.
    "out-null",
    # analysers
    "ruff", "mypy", "pylint", "flake8", "yamllint",
))
# ...but three of them write when given the right flag, so the verb alone is not the answer.
_WRITE_FLAGS = {
    # long forms spelled out: `"--in-place".startswith("-i")` is False, so the short-flag test
    # alone let `sed --in-place` rewrite canonical state -- and a LIVE hook, which disarms the
    # gate rather than merely copying it
    "sed": ("-i", "--in-place"),
    "find": ("-delete", "-exec", "-execdir", "-fprint", "-fls", "-ok"),
    "awk": ("-i", "--in-place"),
    "sort": ("-o", "--output"),
}
# verbs whose PROGRAM is an argument, so a redirect can hide inside a quoted token where no `>`
# token ever appears (`awk 'BEGIN{print "x" > "state.yaml"}'`)
_PROGRAM_ARG_VERBS = frozenset(("awk", "gawk", "mawk", "sed", "perl", "ruby", "jq"))


# An OUTPUT REDIRECT OPERATOR, as a shape rather than as the spellings that happened to be listed:
# an optional file descriptor or `&` (both streams), then `>` or `>>`, then bash's optional
# force-clobber `|` — OR the `>&` form (an optional descriptor, then `>&`). The tuple that stood
# here knew `>`, `>>` and `2>` and knew neither `&>` nor `>|`, so `cat <hook> &> copy.py` and
# `... >| copy.py` produced no target at all — a read-only verb, no redirect, allowed — while the
# very same relocation spelled `>` was refused.
#
# `>&` MATCHES BUT IS NOT ALWAYS A FILE, and that distinction is `_is_descriptor`, applied where
# the target is read (`_output_redirect_targets`) rather than folded into this pattern: in bash
# `>& WORD` duplicates a DESCRIPTOR only when WORD is a number (`>&2`) or the close form (`>&-`);
# for anything else it is the csh spelling of `&> file` and BOTH streams land in the file. The
# note that used to stand here — "`>&` deliberately does not match: its right-hand side is a
# stream number" — was false for the csh case, and it measured as the heavy hole: `echo hi >&
# services/pay.py`, and the same `>&` onto `.claude/**` and `project_memory/approvals/pending/**`,
# named no target at all, so rules 1, 2 and 5 every one ran empty (rc 0 for every caller).
#
# THIS SHAPE FAILS OPEN, and that is the opposite of `_null_sinks` below — read the two together.
# There, a spelling the code does not know stays a WRITE, so the set can only be too small and the
# cost is a false refusal. Here, a form the shape does not match is not a redirect at all, the
# pipeline looks read-only, and the bytes land wherever they were sent. So this shape must stay
# WIDER than any spelling in use, over-matching is the safe direction (`>>|` is meaningless to
# bash and matches anyway), and every future shell operator that lands bytes in a file is a hole
# until it is added here. The one class still outside it is the write verbs a TOOL's own language
# carries — see the module docstring, which says why that is not this regex's problem to solve.
_REDIRECT_RX = re.compile(r"^(?:(?:[0-9]*|&)>>?\|?|[0-9]*>&)$")


def _is_descriptor(word):
    """A `>&` right-hand side that duplicates or closes a DESCRIPTOR rather than naming a FILE.

    `>&2` sends the stream to descriptor 2 and `>&-` closes it — no file receives anything. Every
    other word after `>&` is the csh spelling of `&> file`, so this is the whole of the
    file-vs-descriptor decision and it lives in ONE place (`_output_redirect_targets`). A quoted
    right-hand side is never a descriptor to bash, so a non-digit reading stays a file — the
    over-refusing direction, consistent with the rest of this gate.
    """
    text = str(word)
    return text == "-" or text.isdigit()


def _output_redirect_targets(tokens):
    """(target_index, target_token) for every output redirect on `tokens` that lands in a FILE.

    THE ONE READER of "which words are output-redirect file targets", so the three callers below
    cannot drift on the `>&` question. A `>&`/`N>&` operator (`_operator(token).endswith("&")`) is
    a descriptor duplication when its right-hand side is one (`_is_descriptor`); anything else is a
    file. `&>`/`&>>` do NOT end with `&` and are always a file (both streams into it). The leading
    descriptor of `N>&` is a token of its own — the lexer splits it — so it never reaches here.
    """
    for index, token in enumerate(tokens[:-1]):
        operator = _operator(token)
        if not _REDIRECT_RX.match(operator):
            continue
        target = tokens[index + 1]
        if operator.endswith("&") and _is_descriptor(target):
            continue
        yield index + 1, target


def _has_write_flag(verb, tokens):
    writers = _WRITE_FLAGS.get(verb)
    if not writers:
        return False
    for token in tokens:
        low = token.lower()
        for writer in writers:
            if low == writer or low.startswith(writer + "="):
                return True
            # short-flag cluster (`sed -ni`), but only for real single-letter flags
            if (len(writer) == 2 and writer.startswith("-") and low.startswith("-")
                    and not low.startswith("--") and writer[1] in low[1:]):
                return True
    return False
# `git` is read-only in these subcommands. `add` is included deliberately: it writes the INDEX, not
# the worktree, and refusing `git add .claude/agents/x.md` while `git add -A` stages the same file
# is an artefact, not a policy — it also blocked the documented model:/effort: resync from ever
# being committed.
_READ_ONLY_GIT = frozenset((
    "diff", "log", "show", "status", "grep", "ls-files", "blame", "cat-file", "rev-parse",
    "describe", "shortlog", "config", "add",
))
# git's global options that CONSUME an argument -- without skipping them, `git -C project_memory
# log` read the subcommand as "project_memory"
_GIT_OPTS_WITH_ARG = ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path")
# `python -m <analyser>`: the analysers cannot write. `pytest` is absent from BOTH this and
# _READ_ONLY_VERBS -- it executes arbitrary code, and allowing one spelling while refusing the
# other was the inconsistency, not the strictness.
_READ_ONLY_MODULES = frozenset(("mypy", "ruff", "flake8", "pylint", "pydoc", "json.tool"))
_PIPELINE_SEPARATORS = ("&&", "||", ";")
# `\n` is NOT in that tuple, and must not be: shlex treats a newline as whitespace, so it never
# becomes a token. A newline entry there was dead code, and multi-line commands merged into ONE
# pipeline -- prefixing any refused command with `echo start` defeated the whole rule. Newlines are
# rewritten to `;` before tokenising instead (heredoc bodies are already gone by then). The line
# CONTINUATION that is not a separator comes from `_compat.join_line_continuations` — one rule,
# one place, and it covers the PowerShell backtick this hook's own copy never did.
_HEREDOC_RX = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?^\2\s*$",
                         re.MULTILINE | re.DOTALL)
# A COMMAND SUBSTITUTION OPENS A COMMAND, and WHICH SPELLINGS open one is a property of the SHELL
# and not of the text. `$(` is both shells'; the BACKTICK is POSIX's older spelling and PowerShell's
# ESCAPE character; `@(` is PowerShell's array subexpression, which runs its content exactly as
# `$(` does. One set per shell, because the union is not the safe direction here: with the backtick
# in the PowerShell set, that shell's own LINE CONTINUATION (a backtick before the break) opened a
# substitution that never closed, and the rest of the line became its own pipeline -- measured, and
# it turned `test_a_continuation_the_named_shell_does_not_honour_is_not_joined[PowerShell-backtick
# + LF]` red while the repair for `BUG-0288` was being made.
_SUBSTITUTIONS_BY_SHELL = {
    "PowerShell": {"$(": ")", "@(": ")"},
    # ...and POSIX for everything else, including a payload whose tool this gate cannot name: this
    # project spells its commands for a POSIX shell, and the backtick there is a substitution.
    # PROCESS SUBSTITUTION (`<(`, `>(`) belongs here for the same
    # reason `$(` does and for no weaker one: the shell runs its content as a command and hands the
    # word a file name. Measured by the verifier of this round: `cat <(cp evil.py
    # .claude/hooks/g.py)` was rc 0 at every registered hook of a scaffolded pilot while
    # `echo $(cp …)` was rc 2 -- and the office ledger gate one file away already carried the whole
    # class (`gate_ledger_valid._SUBSTITUTION_OPEN_RX`), which is what made this an omission rather
    # than a boundary.
    "Bash": {"$(": ")", "<(": ")", ">(": ")", "`": "`"},
}
_SUBSTITUTION_OPEN_RX_BY_SHELL = {
    shell: re.compile("|".join(re.escape(opening) for opening in sorted(closers)))
    for shell, closers in _SUBSTITUTIONS_BY_SHELL.items()
}


def substitution_bodies(text, tool=None):
    """Every command a substitution introduces in `text`, outermost first.

    A SUBSTITUTION IS A COMMAND IN A WORD, and the shell runs it BEFORE the word reaches the
    command it stands in. The decomposition this gate works on knows list separators, stage cuts
    and parentheses; a command inside a word appeared in none of them, so `echo $(cp evil.py
    .claude/hooks/g.py)` was a reading stage (`echo`) with an argument, rc 0 -- and inside a `-m`
    payload the prose removal deleted the whole span before any reader saw it, which is the half
    `BUG-0288` was left with.

    JUDGED AS ITS OWN LINE rather than spliced into this one, which is why this returns the bodies
    instead of rewriting the text: a separator written INTO the text lands inside the quoted span
    the substitution usually stands in, where the tokeniser masks it and the cut never happens --
    measured on the office ledger gate in this same round. Appended as extra pipelines the bodies
    are outside every quote, and every rule of this gate then reads them
    (`tools/test_hooks.py::test_a_command_a_substitution_introduces_is_judged_as_a_command`).

    Nesting is followed, so the body of a substitution inside a substitution is returned too.
    """
    shell = "PowerShell" if _compat.gated_shell(tool) == "PowerShell" else "Bash"
    closers = _SUBSTITUTIONS_BY_SHELL[shell]
    opener_rx = _SUBSTITUTION_OPEN_RX_BY_SHELL[shell]
    bodies, index = [], 0
    while True:
        opening = opener_rx.search(text, index)
        if opening is None:
            return bodies
        closer = closers[opening.group(0)]
        start, depth, position = opening.end(), 1, opening.end()
        while position < len(text):
            if closer == ")" and text.startswith("(", position):
                depth += 1
            elif text.startswith(closer, position):
                depth -= 1
                if depth == 0:
                    break
            position += 1
        body = text[start:position]
        bodies.append(body)
        bodies.extend(substitution_bodies(body, tool))
        index = position + 1


# WHAT THE KIT WORKSHOP'S OWN GATES BORROW FROM THIS MODULE, declared here rather than discovered
# at a session start. Those gates do not answer "does this stage write" a second time -- a second
# answer to that question is the drift this apparatus has paid for repeatedly -- so they import
# this module and use its reader. The price was a dependency on UNDERSCORED names that nothing on
# this side knew about: a rename here made the borrow raise, and a gate that cannot execute refuses
# every call of the session. That direction is loud and closed, but it arrives at a session start
# rather than in a test, and it arrived exactly that way once while this line was being written.
#
# So the surface is NAMED, and both ends are measured
# (`tools/test_hooks.py::test_the_harness_borrows_only_what_this_kit_declares`): every name here
# has to exist in all three kits, and every private name the workshop reaches on this module has to
# be here. Adding a name is a decision with a reason; removing one is a rename that now goes red in
# a test instead of in a session (`BUG-0107`).
HARNESS_BORROWS = (
    "_HEREDOC_RX", "_INPUT_REDIRECT_RX", "_MESSAGE_ARG_RX", "_PIPELINE_SEPARATORS",
    "_REDIRECT_RX", "_has_write_flag", "_lex", "_null_sinks", "_operator", "_redirect_targets",
    "_stage_is_read_only", "_stage_verb", "_walk",
)


def prose_removed_view(command, tool=None):
    """`command` with its PROSE gone and every command it really runs still in it.

    THE PUBLIC NAME OF THIS KIT'S READING, and it is public because a second reader exists: the
    harness gates of the kit's own workshop borrow this module rather than answering "does this
    line write" a second time (`BUG-0107`). What they borrowed were UNDERSCORED names, so the two
    prose removals had to be re-assembled on the other side -- and every correction here then had
    to be made there again. This is the assembly, once.

    THREE RULES, and the order between them is the fix of two defects:

      * a HERE-DOCUMENT body is prose unless a command PARSER is fed it. That is
        `_compat.prose_heredoc_free`'s question and not a second one: a body handed to `sh`,
        `bash` or `eval` IS the command, and every other body is data the program on the left
        receives. Removing every body unconditionally made `bash <<'EOF'` with a write to
        canonical state inside it rc 0 (`BUG-0289`); removing only the INERT ones -- the
        neighbouring question, about what the shell expands -- broke the prose end instead, and
        both halves are measured beside that reader.
      * a SUBSTITUTION body is a command and is appended as its own pipeline, so the removal of
        the prose around it cannot take it with it (`BUG-0288`, `substitution_bodies`).
      * the MESSAGE payload of a prose-taking flag is removed last, and only then, because by then
        whatever it carried that the shell executes has already been lifted out of it.

    `tool` says which shell will run the line, and BOTH the substitution spellings and the
    line-continuation character depend on it -- a union over the two shells is not the safe
    direction, because PowerShell's continuation IS the POSIX substitution opening.
    """
    heredoc_free = _compat.prose_heredoc_free(command or "")
    bodies = [body for body in substitution_bodies(heredoc_free, tool) if body.strip()]
    view = _MESSAGE_ARG_RX.sub(" ", heredoc_free)
    if bodies:
        view = view + " ; " + " ; ".join(bodies)
    return view


# Every value an ordinary shell could hand the program for a word — `_compat.shell_readings`, which
# is where the two readings and the reason for them are stated. Aliased rather than wrapped: a
# second name for one rule is how the two copies of the last one drifted.
_readings = _compat.shell_readings


def _operator(token):
    """`token` when the shell would read it as PUNCTUATION, "" when quoting produced it.

    The mirror of `_tokenise`: once the quote marks are gone, `echo '>' file` and `echo > file`
    spell the same three characters, and only the second one redirects. Every punctuation test in
    this gate goes through here, so the two questions ("what does this word SAY" and "is this word
    SYNTAX") cannot drift apart.
    """
    return "" if getattr(token, "spliced", False) else str(token)


def _lex(masked):
    """The masked line split into tokens, with shell punctuation as tokens of its own.

    `punctuation_chars=True` makes `&&`, `||`, `;`, `|`, `>`, `>>` their own tokens even without
    surrounding spaces, and the masked spans keep `'PR|SR'` and `'%h -> %s'` one token each — a
    quoted pipe is not a pipeline and a quoted arrow is not a redirect.
    """
    try:
        lexer = shlex.shlex(masked, posix=False, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return masked.split()  # unbalanced quotes: fall back rather than crash


def _tokenise(command):
    """Tokens as the SHELL resolves them — `_compat.shell_words` with this gate's lexer.

    THE COMPARISON READS THE RESOLVED STRING, NOT THE TYPED ONE, and `_compat` carries why, with
    the measurement: a splice anywhere in the DIRECTORY part of a path defeated every prefix check
    in this gate at once (`echo x > '.cl'aude/hooks/gate_write_scope.py` — allowed by all
    registered gates, file overwritten in a real bash), while the same path spelled plainly was
    refused. `$C/hooks/...` looked covered only because the assignment `C=.claude` names the tree
    in the same line.

    What the resolution costs this gate is one distinction it has to keep making for itself: a word
    that RESOLVES to `>` is not a redirect. `_operator` is that, and every punctuation test here
    goes through it.
    """
    return _compat.shell_words(command, _lex)


def _pipelines(tokens):
    """Group tokens into pipelines. A `|` does NOT start a new pipeline: it is a data channel, so
    stage 1 may name a protected path while stage 2 does the writing."""
    current, out = [], []
    for token in tokens:
        if _operator(token) in _PIPELINE_SEPARATORS:
            if current:
                out.append(current)
            current = []
        else:
            current.append(token)
    if current:
        out.append(current)
    return out


def _stage_verb(stage):
    for token in stage:
        low = str(token).lower()
        if "=" in low and not low.startswith("-"):
            continue  # VAR=value prefix
        if low in ("sudo", "env", "command", "exec", "time", "nice", "!"):
            continue
        if _operator(token).lower() in ("(", ")", "{", "}", "&", "&&", "||", ";", "|"):
            continue  # grouping punctuation is not a verb
        return os.path.basename(low.replace("\\", "/"))
    return ""


# The verbs whose FLAGGED argument can be a free-text message rather than a path this line touches —
# the pivot of BUG-0020/H34. The forge CLIs carry an issue/PR/release body a refusal's own remedy
# asks the agent to quote; `git` carries a message only in the subcommands that actually take one.
# Everything NOT here — `rm`, `cp`, `mv`, `Remove-Item`, `git rm`, `git clean` — treats the quoted
# operand behind a `-f`/`-b`/`-F` as the FILE it is, which is what the removal must not erase.
_PROSE_MESSAGE_VERBS = frozenset(("gh", "hub", "glab"))
_GIT_MESSAGE_SUBCOMMANDS = frozenset(("commit", "tag", "merge", "notes", "stash"))


def _stage_takes_a_message(stage):
    """Does this stage's verb take a free-text message as a flagged argument? (see the sets above)

    This is the whole of what BUG-0020 got wrong: a quoted span is prose only where a message-
    bearing command stands in front of it. `git rm -f "project_memory/x"` is NOT here — its
    subcommand is `rm`, not `commit`, so the quoted path behind `-f` stays visible and is refused.
    """
    verb = _stage_verb(stage)
    if verb in _PROSE_MESSAGE_VERBS:
        return True
    if verb != "git":
        return False
    # the subcommand is the first positional after git's own value-consuming options (`git -C x
    # commit …`), the same skip `_stage_is_read_only` makes for the read-only-git question
    rest = [str(token) for token in stage[1:]]
    while rest and rest[0].startswith("-"):
        option = rest.pop(0)
        if option in _GIT_OPTS_WITH_ARG and rest:
            rest.pop(0)
    return bool(rest) and rest[0].lower() in _GIT_MESSAGE_SUBCOMMANDS


def _stage_is_read_only(stage):
    verb = _stage_verb(stage)
    if _has_write_flag(verb, stage[1:]):
        return False
    # a REDIRECT OPERATOR hiding INSIDE the quoted program, where no `>` token ever appears. The
    # shell's OWN redirect operators are excluded from the search, or this branch would answer for
    # them too and answer wrongly: `awk '{print $1}' .claude/settings.json 2>/dev/null` has a `>`
    # token and no embedded redirect at all, and calling the stage write-capable for it put these
    # six verbs outside the null-sink rule that every other read-only verb now follows.
    # An operator is ALL this looks for: `sed -n 'w kk/g.py'` writes a file with no `>` anywhere
    # and passes — see the module docstring, which states why that stays open.
    if verb in _PROGRAM_ARG_VERBS and any(">" in t for t in stage[1:]
                                          if not _REDIRECT_RX.match(_operator(t))):
        return False
    if verb.startswith("python") or verb in ("py", "pythonw"):
        for index, token in enumerate(stage[:-1]):
            if token == "-m":
                return stage[index + 1].strip("\"'").lower() in _READ_ONLY_MODULES
        return False
    if verb == "git":
        rest = list(stage[1:])
        while rest and rest[0].startswith("-"):
            option = rest.pop(0)
            if option in _GIT_OPTS_WITH_ARG and rest:
                rest.pop(0)
        return bool(rest) and rest[0].lower() in _READ_ONLY_GIT
    return verb in _READ_ONLY_VERBS


# --- rule 4: ordering work, and installing enforcement, are the orchestrator's acts -----------
#
# TWO CLASSES, ONE SHAPE, and both are DERIVED FROM THE KERNEL rather than typed: each map's keys
# are the `args.command` branches of `kernel/cli.py` that reach a named PRODUCER, and a test
# parses the kernel to assert exactly that. A route added to the CLI turns that test red on the
# day it ships, which is what keeps either map from becoming the next stale tuple. In both maps
# the VALUE narrows a command by its first positional (`capture` reaches the task producer only
# for `TSK`; `capture EVD` is an ordinary item and stays allowed); an empty value means the
# subcommand qualifies on its own.
#
# WHAT MAKES A SUBCOMMAND "ORDERING" rather than "writing", because the wider split does not
# survive contact: the commands a specialist hands its OWN finished work back with write too, and
# it has to be able to run them — so "the writing ones, except those" would be two lists holding
# each other up. The property is narrower and it is the one the work loop states: an ordering
# command CREATES THE WORK ORDER somebody executes, or LEASES one for a spawn. In kernel terms
# that is the two producers `dispatch.create_task` and `dispatch.create_lease`.
# Pinned by `tools/test_hooks_v2.py::test_the_ordering_commands_are_the_cli_routes_to_the_task_producers`.
_ORDERING_COMMANDS = {"create-task": (), "capture": ("tsk",), "dispatch": ()}

# ...AND THE SECOND CLASS, which the first could not see because it orders nothing: a command that
# REINSTALLS THE ENFORCEMENT LAYER — the hooks, the settings, the role set this session is judged
# by. Measured by the verifiers of TSK-0064 and TSK-0067 as real hook processes: a subagent ran
# `set-preset` and `update-kit` past all eight registered `Bash|PowerShell` gates, while the
# ordering class above stayed rc 2 for that same caller. The user's approval covers the CONTENT of
# such a change; what a subagent took was the TIMING and, for the preset one, the repetition.
# THE PROPERTY, so a third such command joins by itself: the kernel starts the kit's installer
# exactly one way — `presets.installer_command` builds that invocation and both `apply` functions
# hand it to a child process. So the class is "the CLI branches that reach that producer", at any
# call depth and across kernel modules, and
# `tools/test_hooks_v2.py::test_the_installing_commands_are_the_cli_routes_to_the_installer`
# derives it. A command that shelled out to the scaffold on its own would be outside the
# derivation — the same boundary `_ORDERING_COMMANDS` has against a hand-written task.
_INSTALLING_COMMANDS = {"set-preset": (), "update-kit": ()}
# `os.path.basename(kernel.cli.ENTRY_POINT)` and the module spelling of the same CLI. Both are
# pinned against the kernel by the same test — the gate keeps its own copy so that a Bash call does
# not pay for importing argparse and every field schema just to answer "is this the harness".
_HARNESS_SCRIPT = "harness.py"
_KERNEL_CLI_MODULE = "kernel.cli"


def _harness_argv(stage):
    """The argument list a stage hands to the kernel CLI, or None when it is not a CLI invocation.

    STRUCTURAL, never a bare word anywhere in the line: `grep -rn create-task docs/` and
    `cat scripts/harness.py` name the same strings and order nothing, and refusing a role's own
    reading is how a gate teaches people to route around it. So the entry point has to be in an
    EXECUTION position — the stage's verb is a python, or the script itself is the verb.
    """
    tokens = [str(t) for t in stage]
    verb = _stage_verb(stage)
    pythonish = verb.startswith("python") or verb in ("py", "pythonw")
    if not pythonish and verb != _HARNESS_SCRIPT:
        return None
    for index, token in enumerate(stage):
        # EVERY reading, for the reason `_tokenise` gives: `scripts/'har'ness.py` and
        # `scripts/har\\ness.py` both start the entry point, and rule 4 read neither as it.
        if any(os.path.basename(reading.replace("\\", "/")).lower() == _HARNESS_SCRIPT
               for reading in _readings(token)):
            return tokens[index + 1:]
    if pythonish:
        for index, token in enumerate(tokens[:-1]):
            if token == "-m" and tokens[index + 1].lower() == _KERNEL_CLI_MODULE:
                return tokens[index + 2:]
    return None


def _reserved_command(stage, reserved):
    """The subcommand of `reserved` this stage would run, or "".

    ONE reader for both classes of rule 4: they differ in which kernel producer their map is
    derived from, never in how a command line is read, and a second copy of this function is how
    the second class would start deciding differently from the first.

    The subcommand is the FIRST POSITIONAL, which is what argparse reads too. A `--root
    project_memory` in front of it shifts that position and this returns nothing — deliberately
    not compensated for here: the installed shim refuses `--root` outright, and a pipeline naming
    the state directory is already refused by rule 1, so compensating would be a second opinion
    about a line that never reaches the kernel.
    """
    argv = _harness_argv(stage)
    if not argv:
        return ""
    positional = [str(token) for token in argv if not token.startswith("-")]
    if not positional:
        return ""
    command = positional[0].lower()
    if command not in reserved:
        return ""
    qualifiers = reserved[command]
    if not qualifiers:
        return command
    if len(positional) > 1 and positional[1].lower() in qualifiers:
        return "%s %s" % (command, positional[1].lower())
    return ""


def _null_sinks(tool):
    """The redirect targets that RETAIN NOTHING for this shell on this host.

    The question a redirect raises is not which operator was used but whether the bytes end up
    somewhere a reader can pick them up. Exactly one target is DEFINED to keep nothing — the
    operating system's discard device — so redirecting into it is the shell suppressing output,
    which is a read-side concern; every other target keeps the bytes and is a write, including an
    unprotected one (`cat <hook> > copy.py` is the relocation this gate exists to refuse).

    PER SHELL AND PER HOST, because the same word is a device in one and an ordinary FILE in
    another, and getting that backwards would open the hole this closes. Measured 2026-08-03 on
    this Windows host: PowerShell has no `/dev/null` — it resolves a leading-slash path against the
    CURRENT DRIVE, and a redirect into one landed its bytes in a real file there, so `> /dev/null`
    on any host carrying `C:\\dev` is the relocation this gate refuses, spelled to look harmless.
    Git Bash meanwhile discarded both `> /dev/null` and `> NUL`, the latter because `nul` is a
    Win32 reserved device name no file can be created under. On POSIX the reverse holds: `> NUL`
    there is an ordinary file in the working directory.

    A SPELLING THIS DOES NOT KNOW STAYS A WRITE (`nul:`, `\\\\.\\NUL`, a shell alias), so the set can
    only be too small — the cost of that is a false refusal a user can report, not a route out of
    the tree.
    """
    # `os.devnull` is Python's name for the device of the host this gate runs on — `/dev/null` on
    # POSIX, `nul` on Windows — so the base of the set is a definition rather than a spelling.
    names = {_norm(os.devnull)}
    if tool == "PowerShell":
        names.add("$null")
    elif os.name == "nt":
        names.add("/dev/null")  # the Bash tool on Windows is a POSIX shell over a Win32 filesystem
    return names


def _redirect_targets(tokens, sinks):
    """Targets of an output redirect that RETAIN what is written — see `_null_sinks`.

    PER TARGET, not per pipeline: `cat <hook> > /dev/null > copy.py` still has one retaining
    target and is still refused. The `sinks` argument has no default on purpose — a caller that
    forgot it would silently get the old, over-refusing behaviour back.
    """
    return [target for _index, target in _output_redirect_targets(tokens)
            if _norm(target) not in sinks]


def _names(rx, tokens):
    """Does any word of `tokens` name this tree, under ANY reading a shell could give it?"""
    return any(rx.search(reading) for token in tokens for reading in _readings(token))


# The characters with which a word stops being the path it spells and becomes a QUESTION to the
# filesystem. `{` is not among them: brace expansion produces its alternatives out of the word
# itself, and `_readings` already hands both halves of a quoted word to the comparison above.
_GLOB_CHARS = "*?["


def _glob_readings(word, base):
    """Every path this word can already resolve to on disk, relative to `base` -- () for a word
    that asks the filesystem nothing.

    THE SHELL'S OWN EXPANSION, PERFORMED HERE. A pattern is not a guess about what a word might
    mean: the shell resolves it against the same filesystem this gate is standing in, so the gate
    can resolve it too and compare the ANSWER. Measured 2026-08-31 and again for TSK-0139 against
    a scaffolded proxy project: `python .claude/hooks/gate_approval.py` rc 2 while
    `python .cla*de/hooks/gate_approval.py`, `cp .cla*de/... /tmp/x.py` and
    `rm -f .cla*de/hooks/gate_approval.py` were rc 0 -- the shell expanded the metacharacter, this
    reader compared the literal token, and the protected name was never spelled (BUG-0082).

    EXPANDED PER COMPONENT, and that is the half a plain `glob.glob` of the whole word does not
    give: a pattern only matches what EXISTS, so `cp evil.py .cla*de/hooks/gate_new.py` -- a file
    that is not there yet -- would answer nothing while naming the layer perfectly well. Every
    PREFIX of the word that carries a metacharacter is expanded on its own and the untouched tail
    is put back on, so the DIRECTORY the word reaches is compared whether or not its leaf exists.

    WHAT IS RETURNED IS RELATIVE, deliberately: an absolute answer would carry the project's own
    location into the comparison, and a checkout that happens to live under a directory called
    `.claude` (a provider's project store is exactly that) would then refuse every write in it.

    THE PRICE IS MEASURED AND IT IS NONE for ordinary work: a pattern that resolves to no protected
    path adds no refusal. `cp src/*.js dist/`, `rm -rf dist/*` and `pytest tests/test_*.py` were
    measured rc 0 before and after. What stays open is the OTHER half of the unresolvable class --
    a word whose value comes from the shell's own state (`$VAR`, `${VAR}`, `$(cmd)`, a backtick) --
    which no filesystem question can answer; that residue is BUG-0082's own entry and this gate's
    `_names` says nothing about it.
    """
    if not any(char in word for char in _GLOB_CHARS):
        return ()
    parts = str(word).replace("\\", "/").split("/")
    found = set()
    for count in range(1, len(parts) + 1):
        prefix = "/".join(parts[:count])
        if not any(char in prefix for char in _GLOB_CHARS):
            continue
        try:
            matches = glob.glob(os.path.join(base, prefix) if base else prefix)
        except (OSError, ValueError):
            continue
        tail = parts[count:]
        for match in matches:
            try:
                relative = os.path.relpath(match, base) if base else match
            except ValueError:
                continue                    # another drive: it names nothing under this one
            found.add("/".join([relative.replace("\\", "/")] + tail))
    return tuple(found)


def _names_expanded(rx, tokens, base):
    """`_names`, asked of what the SHELL will really hand the program -- see `_glob_readings`."""
    return any(rx.search(expanded)
               for token in tokens for reading in _readings(token)
               for expanded in _glob_readings(reading, base))


# A `NAME=value` word, and a `$NAME`/`${NAME}` reference to one. Used to resolve a redirect target
# the shell would expand from the SAME command line before rule 5 judges it.
_ASSIGNMENT_RX = re.compile(r"^([A-Za-z_]\w*)=(.*)$", re.DOTALL)
_VAR_REF_RX = re.compile(r"\$\{(\w+)\}|\$(\w+)")


def _line_assignments(tokens):
    """{NAME: value} for every `NAME=value` word on the command line — a best-effort static map.

    STATIC AND ORDER-BLIND ON PURPOSE, because this is not a shell: it exists to close the ONE
    decidable case rule 5 was measured to miss — a plain `F=services/pay.py; … > $F`, rc 0 before
    — and no more. A value that is itself an expansion is left unresolved, and the target is then
    judged by its readable part in `_lead_target`. `export F=x` and a command-prefix `F=x cmd`
    both put the assignment in a `NAME=value` word, so scanning every token catches them.
    """
    found = {}
    for token in tokens:
        match = _ASSIGNMENT_RX.match(str(token))
        if match:
            found[match.group(1)] = match.group(2)
    return found


def _resolve(text, assignments):
    """`text` with every `$NAME`/`${NAME}` the line assigned substituted in; the rest left as is.

    A reference the map does not carry stays verbatim, so `$(cmd)` and `$UNSET` do not resolve and
    the target falls to the readable-part judgement below — the named residue, not a false pass.
    """
    if not assignments or "$" not in text:
        return text
    return _VAR_REF_RX.sub(
        lambda m: assignments.get(m.group(1) or m.group(2), m.group(0)), text)


def _lead_target(reading, cwd, root, assignments):
    """A redirect target as the path rule 5 judges, or None when there is nothing to judge.

    A `$NAME` the SAME LINE assigned is resolved first (`_resolve`): `F=services/pay.py; … > $F`
    is decidable and was measured rc 0 while this returned the literal `$F` (no extension, no
    refusal). Then, in order:

      * a target this reader can PLACE and that lands outside the repo is not this project's
        production code — None, the same exit `guard_pm_scope.repo_relative` takes for it;
      * a target whose TILDE prefix only a shell can resolve — it needs that shell's `HOME`, or
        its `PWD` for `~+` — is judged by the part of it that IS readable, the file name. Skipping
        the word is what this did first, and `~+/` is the WORKING DIRECTORY, so that version let
        the repo's own code be written through a prefix. The price of judging it is the opposite
        error and it is the cheaper one: a code file the lead writes into its own home directory
        is refused too, while an ordinary document there is not.

    A reference the line did NOT assign (`$(cmd)`, an unset or externally-exported var) stays
    unresolved and lands in the relative branch, judged as spelled — a named residue, not a false
    pass. All of these sit in the batteries of `test_the_lead_cannot_land_code_through_a_shell_redirect`
    and `test_the_shell_rule_leaves_the_leads_own_work_alone`, one entry per direction.
    """
    text = _resolve(str(reading), assignments).replace("\\", "/")
    if not text:
        return None
    if text.startswith("~"):
        return posixpath.basename(text) or None
    if text.startswith("/") or (len(text) > 1 and text[1] == ":"):
        return _repo_relative(text, root, fold=False)[0]
    rel = posixpath.normpath(posixpath.join(cwd or "", text))
    return None if rel == ".." or rel.startswith("../") else rel


def _assert_the_lead_lands_no_code(targets, cwd, root, assignments):
    """RULE 5 — the lead writes no production code, whichever door it uses.

    WHAT A WRITE POSITION IS HERE, and why this is not the verb list L4 refuses: the SHELL itself
    lands the bytes of an output redirect in the target, so `>`/`>>`/`>&`-to-a-file and their
    forms name a file being written without anyone classifying a tool's language.
    `_redirect_targets` (with `_null_sinks` and the descriptor test in `_output_redirect_targets`)
    already decides which of them RETAIN what is written, so this rule inherits that answer instead
    of asking again. What the file IS, is `guard_pm_scope.production_code` — the same predicate the
    write tools are judged by, so the two doors cannot drift apart.

    WHAT IT DOES NOT REACH, all measured and named beside the tripwire that pins them
    (`test_the_shell_writes_no_command_line_can_decide_stay_the_named_residue`): a write a TOOL
    performs from inside its own language or arguments (`cp`, `mv`, `tee`, `sed -i`,
    `python -c "open(...)"`, and the PowerShell `Out-File`/`Set-Content`/`Add-Content`/`Tee-Object`
    cmdlets), and a redirect target built by an expansion the line does not assign (`$(cmd)`, an
    unset or externally-exported variable) — see `_lead_target`.
    """
    for token in targets:
        for reading in _readings(token):
            rel = _lead_target(reading, cwd, root, assignments)
            if rel is None or not guard_pm_scope.production_code(rel):
                continue
            _kernel.block(
                HOOK,
                "'%s' is production code and this command line LANDS bytes in it. You are the "
                "lead: you do not write production code — that is any file in a programming "
                "language outside your own areas, at any depth, and the DOOR does not change the "
                "answer (`guard_pm_scope` refuses the same file through Write/Edit; this is the "
                "shell half of it)." % rel,
                remedy="delegate it to the matching specialist subagent, whose work order carries "
                       "the scope, and let QA gate the result. Your own areas stay open: docs/, "
                       "plans/, .claude/** and root configuration. If this refusal is wrong, it is "
                       "an infrastructure defect worth reporting rather than working around.")


# An INPUT redirect, and only the file form of it: `<`, `0<`. `<<` opens a here-document and `<<<`
# a here-string — neither names a file to read — and `<&` duplicates a descriptor.
_INPUT_REDIRECT_RX = re.compile(r"^[0-9]*<$")
# The one subtree of the state directory a proposal legitimately comes OUT of. Spec II.4 defines
# `staging/**` as explicitly non-canonical: what is written there is a draft, and the only thing
# anyone can do with a draft is hand it to the kernel.
_STAGING_SOURCE_RX = re.compile(r"project_memory[\\/]+staging[\\/]", re.IGNORECASE)


def _read_sources(pipeline, stages):
    """The tokens of this pipeline that name a file it READS rather than one it writes.

    Two shapes, and they are the two the shell has: the operand of an INPUT redirect, and an
    argument of a stage whose verbs cannot modify anything (`_stage_is_read_only`, which already
    answers for a write FLAG on an otherwise read-only verb). A read-only stage's own redirect
    TARGETS are excluded — `cat a > b` reads `a` and writes `b`, and counting `b` here would hand
    the carve-out below exactly the relocation it must refuse.
    """
    sources = set()
    for index, token in enumerate(pipeline[:-1]):
        if _INPUT_REDIRECT_RX.match(_operator(token)):
            sources.add(str(pipeline[index + 1]))
    for stage in stages:
        if not stage or not _stage_is_read_only(stage):
            continue
        written = {target_index for target_index, _target in _output_redirect_targets(stage)}
        sources.update(str(token) for index, token in enumerate(stage)
                       if index and index not in written)
    return sources


def _only_reads_staging(pipeline, stages):
    """Is EVERY mention of the state directory in this pipeline a read of `staging/**`?

    THE ROUTE OUT OF `staging/` IS THIS ONE, and without it there is none. The architect role has
    no shell to run the kernel with by design: it leaves a proposal in `staging/<task-id>/` and the
    lead books it in. Both spellings the kits document for that hand the file to the entry point as
    STANDARD INPUT — `python scripts/harness.py capture SR < project_memory/staging/…` and
    `cat project_memory/staging/… | python scripts/harness.py capture SR` — and both were refused,
    measured against the real hook: the pipeline can write (the entry point is not a read-only
    verb) and it names the state directory, which is all rule 1 asked. So the proposal directory
    the spec puts inside the state tree had no exit at all.

    A READ IS NOT A WRITE, and that is the whole of the widening — the direction every part of it
    keeps narrow:
      * only `staging/**`, never a canonical path. `capture < project_memory/product/active/…`
        stays refused: reading canonical state INTO a writing pipeline is how a forged item would
        be smuggled back in through the entry point's own door.
      * only when the state directory is named NOWHERE ELSE. One redirect TARGET, one `cp`
        destination, one argument of a writing verb, and this answers no.
      * a word that is a read source AND a redirect target is not a read: `capture < staging/a.json
        > staging/a.json` names one string twice, and membership alone would have read the second
        mention off the first and opened a shell write INTO the state tree.
      * never once a `cd` has put the pipeline inside the state tree, because a relative target
        there names nothing this reader can compare (see the caller).
    """
    named = [token for token in pipeline if _names(_STATE_RX, [token])]
    if not named:
        return False
    sources = _read_sources(pipeline, stages)
    written = {str(target) for _target_index, target in _output_redirect_targets(pipeline)}
    return all(str(token) in sources and str(token) not in written
               and all(_STAGING_SOURCE_RX.search(reading) for reading in _readings(token)
                       if _STATE_RX.search(reading))
               for token in named)


def _walk(pipeline, cwd):
    """The working directory a `cd`/`pushd`/`popd` leaves us in, or None when it is unknown.

    Tracking the PATH rather than a depth, because the two cheaper models each got a real case
    wrong: a boolean could not tell "left the tree" from "went deeper into it", and a depth counter
    could not enter a TWO-SEGMENT tree in two steps (`cd .github && cd hooks` armed nothing,
    because `.github` alone is not a protected path) nor unwind inside one argument
    (`cd project_memory/../src` counted as entering). A path answers all three by construction:
    whether we are inside a protected tree is then the same question the direct-naming check asks.

    None means "somewhere we cannot name" -- an absolute target, a bare `cd`, `cd -`, or `popd`.
    Conservatively treated as outside: over-blocking every command after a `popd` would refuse
    ordinary work, and the direct-naming check still covers anything that spells the path out.
    """
    verb = _stage_verb(pipeline)
    if _DIRECTORY_VERBS.get(verb) == "pop":
        return None
    args = [t for t in pipeline[1:] if not t.startswith("-")]
    if not args or args[0] == "-":
        return None  # bare `cd` (home) or `cd -` (previous)
    # OF THE READINGS THIS WORD HAS, THE ONE THAT LANDS IN A PROTECTED TREE. Same doctrine as
    # `_names`: the text does not say which shell runs it, and a gate that is unsure must see the
    # reading that matters — `cd .cl\\aude` really enters the enforcement layer in a POSIX shell,
    # and reading it as an ordinary directory name armed nothing for the write that followed.
    readings = _readings(args[0])
    target = next((r for r in readings
                   if _ENFORCEMENT_RX.search(r) or _STATE_RX.search(r)), readings[0])
    target = target.replace("\\", "/")
    if (target.startswith("/") or target.startswith("~")
            or (len(target) > 1 and target[1] == ":")):
        return None  # absolute: outside anything we can reason about relatively
    segments = [] if cwd is None else [p for p in cwd.split("/") if p]
    for segment in [p for p in target.split("/") if p not in ("", ".")]:
        if segment == "..":
            if not segments:
                return None  # walked out above the point we were tracking from
            segments.pop()
        else:
            segments.append(segment)
    return "/".join(segments)


def _inside(rx, cwd):
    return bool(cwd) and rx.search(cwd) is not None


def handle_shell(data):
    command = str((data.get("tool_input") or {}).get("command") or "")
    if not command.strip():
        sys.exit(0)
    # message ARGUMENTS and heredoc BODIES removed: both are prose. Stripping ALL quoted spans
    # would remove the target path of every real write (`echo x > "project_memory/a.yaml"`), and
    # leaving heredoc bodies in made each of their LINES look like a command. The message removal is
    # bound to the VERB (`_MESSAGE_ARG_RX` is `_VerbBoundMessageRemoval`): a quoted span behind a
    # `-f`/`-b`/`-F` is prose after `git commit`/`gh`, but the FILE after `rm`/`cp`/`mv` (BUG-0020).
    code_view = prose_removed_view(command, data.get("tool_name"))
    # a continued line is ONE command; every break the shell honours is a command separator that
    # shlex would otherwise swallow as whitespace. WHICH characters those are, and that the
    # continuation is removed rather than spaced, both come from the shared preparation — this hook
    # kept its own copy of the continuation rule and its own copy of the bug (`echo x >
    # project_mem\<newline>ory/approvals/APR-0001.yaml` read as two words and named no state path),
    # and it then kept its own copy of the SEPARATOR rule and the next one: the `\n` below was the
    # only break it rewrote, so a break spelled CR stayed whitespace and the write behind it was
    # judged as an argument of the harmless verb in front (BUG-0066, and `_compat` carries the
    # measurement).
    code_view = _compat.join_line_continuations(
        code_view, tool=data.get("tool_name")).replace("\n", " ; ")
    # DEPTH, not a boolean: assigning a flag on every `cd` could not tell "left the tree" from
    # "went deeper into it", so `cd project_memory && cd approvals && echo x > a.yaml` wiped the
    # very flag that should have blocked it.
    # the working directory, relative to the repo root, as the pipelines walk it. UNFOLDED: rule 5
    # compares against a case-sensitive ALLOW list, while every other consumer of this value is an
    # `IGNORECASE` pattern — see `_repo_relative`.
    root = _kernel.find_repo_root(data.get("cwd"))
    cwd = _repo_relative(data.get("cwd") or ".", root, fold=False)[0] or ""
    # WHICH SHELL decides which redirect targets keep the bytes — see `_null_sinks`.
    sinks = _null_sinks(data.get("tool_name"))
    # WHO IS ASKING (rule 4). One definition for the whole kit — `_compat.calling_subagent` carries
    # the measurement and the reason it tests truthiness rather than key presence.
    caller = _compat.calling_subagent(data)
    # ...and rule 5 asks the MIRRORED question, from the guard that owns it: "is this the lead?"
    # is not "is this not a subagent", and `_compat.calling_subagent` states why the two must not
    # be merged (they fail in opposite directions).
    lead = guard_pm_scope.gates_this_caller(data)
    all_tokens = _tokenise(code_view)
    # WHOLE-LINE assignments, resolved once: `F=x` and its use `> $F` can sit in different
    # pipelines (a `;` between them), so rule 5's target resolver needs the map of the entire line,
    # not of the pipeline it is judging.
    assignments = _line_assignments(all_tokens)
    for pipeline in _pipelines(all_tokens):
        stages, current = [], []
        for token in pipeline:
            if _operator(token) == "|":
                stages.append(current)
                current = []
            else:
                current.append(token)
        stages.append(current)
        if caller:
            for stage in stages:
                ordered = stage and _reserved_command(stage, _ORDERING_COMMANDS)
                if ordered:
                    _kernel.block(
                        HOOK,
                        "`%s` ORDERS work, and this call comes from a subagent (%s). Creating the "
                        "task or leasing one for a spawn is the orchestrator's act: the work "
                        "order, its `allowed_scope` and the lease are the lead's judgements "
                        "to make, and a specialist that makes them for itself is authorising "
                        "itself." % (ordered, caller),
                        remedy="hand the need BACK instead: name it in `followups` of your "
                               "result envelope and let the lead order it. Nothing you run to "
                               "report, prove or return your OWN work is affected by this rule; "
                               "`python scripts/harness.py --help` is the authority on what the "
                               "surface has.")
                installs = stage and _reserved_command(stage, _INSTALLING_COMMANDS)
                if installs:
                    _kernel.block(
                        HOOK,
                        "`%s` REINSTALLS THE ENFORCEMENT LAYER — it runs the kit's installer, "
                        "which rewrites the hooks, the settings and the role set this session is "
                        "judged by — and this call comes from a subagent (%s). The user's "
                        "approval covers WHAT such a change contains; WHEN it happens, and how "
                        "often, is the orchestrator's act, and a specialist cannot judge whether "
                        "the session is at a point where the rule set may move." % (installs,
                                                                                    caller),
                        remedy="hand it BACK: name it in `followups` of your result envelope and "
                               "let the lead run it. The approval you may already hold stays "
                               "valid — nothing about it is spent by this refusal.")
        verbs_read_only = all(_stage_is_read_only(stage) for stage in stages if stage)
        redirects = _redirect_targets(pipeline, sinks)
        if lead:
            # RULE 5, on the targets `_redirect_targets` already resolved: where the SHELL lands
            # bytes, the lead lands no production code.
            _assert_the_lead_lands_no_code(redirects, cwd, root, assignments)
        # a redirect that RETAINS makes a pipeline write-capable whatever its verbs: `echo x > f`
        # writes. A redirect into the null device retains nothing and is therefore not one — see
        # `_null_sinks` for why that is a property of the target and not a list of harmless forms.
        writes = not verbs_read_only or bool(redirects)
        names_enforcement = (_names(_ENFORCEMENT_RX, pipeline)
                             or _names_expanded(_ENFORCEMENT_RX, pipeline, cwd)
                             or _inside(_ENFORCEMENT_RX, cwd))
        names_state = (_names(_STATE_RX, pipeline)
                       or _names_expanded(_STATE_RX, pipeline, cwd)
                       or _inside(_STATE_RX, cwd))
        if names_enforcement and writes:
            # a RETAINING redirect counts even to an unprotected target: `cat <hook> > copy.py` IS
            # the relocation this refuses. Suppressing output is not that, and this branch used to
            # make no distinction — measured three times in one lifecycle run, each on a pure read
            # (`ls .claude/agents/ 2>/dev/null`), each costing the role a detour. What separates
            # the two is `_null_sinks`, and NOT the state branch's `captures_out` carve-out: that
            # one allows a read-only pipeline to redirect into any unprotected file, which is
            # precisely `cat <hook> > copy.py`.
            _refuse(pipeline, "the enforcement layer",
                    "Hooks and settings are maintained by the scaffold, never by hand — and a copy "
                    "of the layer runs outside every path check, which is the shortest measured "
                    "route to a forged approval.",
                    "reading it (cat/grep/diff/ruff/mypy) stays allowed, including with the output "
                    "suppressed (`2>/dev/null`, `> NUL`, `> $null`); what is refused is the bytes "
                    "LANDING somewhere — a copy, a redirect into a real file, an in-place edit. "
                    + _CRAFT_MEMORY_HAS_A_DOOR +
                    " If a gate blocks something legitimate, that is an infrastructure defect "
                    "worth reporting.")
        if names_state and writes:
            # ONE carve-out: a read-only command capturing state to a scratch file outside both
            # protected trees. `git diff project_memory > /tmp/state.diff` is how an agent reports
            # on state, and refusing it teaches nothing except to work around the gate.
            # ...but NOT once a `cd` has put us inside the state dir: there a relative redirect
            # target names nothing and still lands in canonical state
            # the two `_names_expanded` terms are not decoration: the carve-out asks whether the
            # TARGET is outside both trees, and a target the shell expands answered "outside" by
            # spelling nothing -- `echo x > project_mem*ry/bugs/active/BUG-9999.yaml` was rc 0
            # with the refusal above already in place (BUG-0082's class one level down).
            captures_out = (verbs_read_only and redirects and not _inside(_STATE_RX, cwd)
                            and not _inside(_ENFORCEMENT_RX, cwd)
                            and not _names(_ENFORCEMENT_RX, redirects)
                            and not _names_expanded(_ENFORCEMENT_RX, redirects, cwd)
                            and not _names(_STATE_RX, redirects)
                            and not _names_expanded(_STATE_RX, redirects, cwd))
            # ...and the mirror of it on the way IN: a proposal being handed to the entry point.
            # Both carve-outs stand down inside the state tree for the same reason — there a
            # relative path names the tree without spelling it, so nothing here can compare it.
            reads_staging = (not _inside(_STATE_RX, cwd) and not _inside(_ENFORCEMENT_RX, cwd)
                             and _only_reads_staging(pipeline, stages))
            if not captures_out and not reads_staging:
                _refuse(pipeline, "the canonical state directory",
                        "project_memory has exactly one writer, the kernel — and a shell write is "
                        "the path that bypasses every Edit/Write guard.",
                        "use the entry point (`python scripts/harness.py <command>`, from the "
                        "project root; `python scripts/harness.py --help` lists the surface); a "
                        "non-canonical proposal goes into the task's own proposal area (spec "
                        "II.4), which is the one place under the state directory a tool write "
                        "reaches.")
        if _stage_verb(pipeline) in _DIRECTORY_VERBS:
            # everything after `cd project_memory` is inside it, and the later pipelines no longer
            # NAME it -- that shape walked straight past a path-only check. Mirrored for the
            # enforcement layer, whose `cd .claude && cp -r hooks /tmp` had no carry-over at all.
            cwd = _walk(pipeline, cwd)
    if _INLINE_KERNEL_RX.search(code_view):
        _kernel.block(
            HOOK,
            "this command reaches into the state kernel with inline python. The kernel's vetted "
            "surface is the installed entry point, which goes through the status automaton and "
            "the approval checks; an ad-hoc import goes around them.",
            remedy="use `python scripts/harness.py <command>` — installed kit-owned in every "
                   "scaffolded project and run from the project root. Do NOT add `--root`: this "
                   "gate refuses a write-capable pipeline that names the state directory, and "
                   "the entry point resolves it itself. Importing the kernel package by its own "
                   "name is no alternative either — it installs under `.claude/`, so that import "
                   "fails in a project. `python scripts/harness.py --help` lists the surface; a "
                   "command spec II.4 names and the surface lacks is a gap to report, never one "
                   "to route around this gate for.")
    sys.exit(0)


def _refuse(pipeline, what, why, remedy):
    _kernel.block(HOOK, "this command names %s in a pipeline that can write (`%s`). %s"
                  % (what, " ".join(pipeline)[:160], why), remedy=remedy)


def main():
    data = _kernel.payload(HOOK)
    # The early exit is what makes the missing `fail_closed(HOOK, event)` re-entry safe: every
    # reachable block() below really is a PreToolUse block, so the audit label cannot lie. Widening
    # this filter (e.g. registering the gate on PermissionRequest) MUST add the re-entry, or the
    # mislabelling gate_dispatch documents comes back.
    if str(data.get("hook_event_name") or "PreToolUse") != "PreToolUse":
        sys.exit(0)
    tool = data.get("tool_name")
    if tool in FILE_TOOLS:
        handle_file_write(data)
    elif tool in SHELL_TOOLS:
        handle_shell(data)
    sys.exit(0)


if __name__ == "__main__":
    _kernel.run_gate(HOOK, main)
