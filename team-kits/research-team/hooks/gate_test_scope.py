#!/usr/bin/env python3
"""
PreToolUse(Bash|PowerShell) — a full run of the project's DECLARED test surface happens ONCE, and
the line says so (FR-0086, the kit side of DEC-0050).

THE ERROR IT CATCHES IS MEASURED, which is what DEC-0056 asks of a gate before it is built, and it
was measured in the workshop rather than guessed at here: DEC-0050 recorded six full-suite runs
inside ONE item's rounds, 35 to 39 minutes each, with no finding out of any of them; DEC-0070
recorded five more occurrences in one generation, about five hours, and noted that every role NAMED
the rule and none was stopped by it. FR-0057 is the same question asked of a user's project: a
quality-engineer whose only instruction is "run the tests" runs everything on every task, and in a
grown project that is the same explosion at the user's cost.

THE RULE:

    A command line that runs the WHOLE declared test surface is refused — unless the line itself
    says it is the delivery run, by carrying `DELIVERY_RUN=<ITEM-ID>` in front of the runner. That
    prefixed line is the one `harness.py evidence --run-scope full` records (DEC-0061), which is
    the Evidence `gate_git` reads before it opens a merge. So the run the merge needs and the run
    this gate allows are the same run, once. A second one for the same item is refused unless the
    first FAILED — a full run that yielded findings is exactly the case that sends the work back
    into the suites.

A RUNNER NOBODY DECLARED IS NOT JUDGED, and that is the whole applicability rule. This gate carries
no list of runner names and no idea of what a test command looks like: it reads an `INV` item whose
`scope: test_surface`, the same way `gate_test_coverage` reads the areas a project governs and
`scripts/kit_checks.py` reads its knobs. A project without that item is judged by nothing here, and
`session_status.py` says so once per session rather than leaving the silence to be mistaken for
coverage.

  scope: test_surface
  value:
    judged_above_seconds: 60        # below this a full run costs nothing worth refusing
    surfaces:
      - runner: pytest              # the program the project's test command runs
        root: tests                 # the path that IS the whole surface
        seconds: 900                # what a full run of it was measured to cost
    options_that_narrow:
      pytest: ["-k", "-m", "--deselect", "--collect-only"]

WHAT "RUNS THE WHOLE DECLARED SURFACE" MEANS, as a property:
  * the stage RUNS the declared runner — its verb's basename is the runner, or the runner is the
    word an interpreter's `-m` hands it. A runner name anywhere else is text (`grep pytest tests/`
    runs grep);
  * the positional words handed to that runner include the declared root or an ANCESTOR of it, and
    a stage that hands it none names the runner's own working directory, which is an ancestor of
    everything. A word strictly INSIDE the root — a sub-path, a node id — narrows the run;
  * and none of those words is an option the project declared as one after which the line no
    longer runs the whole surface.

WHAT IT DOES NOT SEE, named rather than implied: a runner word the text does not fix
(`$RUNNER tests/`), because the cheap pre-filter looks for the declared name in the line before
anything else is read; and an option that narrows and is not declared, which leaves the line
reading as a full run and REFUSED — over-refusal, answerable on the line.

A `timeout` ON ITS REGISTRATION LIKE EVERY OTHER ENTRY, and since 2026-09-12 that is the shipped
rule rather than an exception: a window used to be nothing but the moment the provider KILLS a gate,
and a killed gate is a silent allow -- so an entry named one only where the gate's own bound was
longer than the default (measured 2026-08-23, `tools/provider_observations.json` ->
`hook_deadlines`). `_compat.start_the_deadline` refuses BEFORE the window now (BUG-0153/H61), so the
window is what this gate answers inside rather than what kills it, and
`tools/test_hooks.py::test_every_registration_names_a_window_its_gate_can_answer_inside` derives the
value from this file's own `timeout=` keywords and the budget a hook process gives itself.
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

import glob as globmodule  # noqa: E402 -- the reader of a positional glob
import posixpath  # noqa: E402 -- AFTER the preamble, which must stay byte-identical to
import re         # noqa: E402 -- `_kernel.GATE_PREAMBLE` (test_context_budget strips it)

import gate_write_scope as shell  # noqa: E402

HOOK = "gate_test_scope"
SHELL_TOOLS = ("Bash", "PowerShell")

# The `INV` scope a project declares its test surface under. One word, and it is the same
# mechanism every other knob of this kit uses (`scripts/kit_checks.invariant_knob`).
SURFACE_SCOPE = "test_surface"

# The typed home of `INV` items, as `kernel.backlog_types.ACTIVE_DIRS["INV"]` spells it — a literal
# for the reason spec II.7 gives (an integrity gate stays stdlib-first and keeps guarding when the
# kernel cannot load), pinned against the kernel by
# `test_the_hooks_that_name_a_typed_directory_spell_it_as_the_kernel_does`.
INVARIANTS_DIR = ("invariants", "active")
EVIDENCE_DIR = ("evidence",)

# The same two caps `gate_test_coverage` and `guard_guidelines` read their stores under, and for
# the reason spelled out there: this reader runs on a BLOCKING PreToolUse hook, and the size of the
# store may not decide how long that hook takes to answer.
ITEM_MAX_BYTES = 2_000_000
SCAN_MAX_BYTES = 8_000_000
# How much of an item is read to decide whether it is the one being looked for -- see
# `_could_declare`. Generous enough that the kernel's own field order puts a top-level key inside
# it, small enough that reading it for every item of a store at the cap is noise.
SCOPE_HEAD_BYTES = 4096

# How a line says it is THE delivery run. An ASSIGNMENT, because that is the one shape both shells
# can put in front of a program without changing what the program is: a POSIX shell reads
# `NAME=value cmd` as an environment prefix, PowerShell writes the same intent as a command of its
# own (`$env:NAME="value"; cmd`), and both are read below.
DELIVERY_MARKER = "DELIVERY_RUN"

# The kernel's vocabulary for a recorded run (DEC-0061).
RUN_SCOPE_FIELD = "run_scope"
FULL = "full"

# The interpreter option that makes the following word the program.
MODULE_FLAG = "-m"


def _items(base, worth_parsing=None):
    """Every item dict under one typed directory, read under this hook's budget.

    `worth_parsing` is asked of the PATH before the file is parsed, so a caller that is looking for
    one item does not pay for parsing the rest -- see `_could_declare` for the measurement that
    makes that worth having and for the direction it fails in.

    Anything unreadable yields nothing: an unparsable item is the state validator's finding, and a
    gate that bricked on one would cost more than the rule it adds — the same answer
    `gate_test_coverage._governed_source_areas` gives.
    """
    if not os.path.isdir(base):
        return []
    try:
        import yaml  # type: ignore[import-untyped]
        names = [name for name in sorted(os.listdir(base)) if name.endswith(".yaml")]
    except Exception:  # noqa: BLE001
        return []
    out, spent = [], 0
    for name in names:
        path = os.path.join(base, name)
        try:
            size = os.path.getsize(path)
            if size > ITEM_MAX_BYTES:
                continue
            spent += size
            if spent > SCAN_MAX_BYTES:
                break
            if worth_parsing is not None and not worth_parsing(path):
                continue
            with open(path, encoding="utf-8", errors="ignore") as handle:
                item = yaml.safe_load(handle.read())
        except Exception:  # noqa: BLE001
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def _could_declare(path):
    """Could this item be the declaration, decided WITHOUT parsing the whole of it?

    THIS GATE SITS ON EVERY SHELL CALL, which is what separates it from its neighbours: the two
    other readers of the invariant store fire on a code write and on a merge, and a full parse of a
    store at the shipped cap costs ~3 s (measured 2026-09-04, six items just under
    `ITEM_MAX_BYTES`). Paying that on every `git status` would be a gate charging the legitimate
    path more than the rule is worth (DEC-0056).

    So the HEAD of the file decides, and it decides in the fail-closed direction: a top-level
    `scope:` key inside the first `SCOPE_HEAD_BYTES` answers outright, and a head that shows NO
    top-level `scope:` at all is "cannot say", which is answered by parsing the item in full rather
    than by skipping it. `test_the_declaration_is_found_even_when_its_scope_key_sits_past_the_head`
    is the half that keeps that fallback honest.
    """
    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            head = handle.read(SCOPE_HEAD_BYTES)
    except Exception:  # noqa: BLE001
        return True
    for line in head.splitlines():
        if not line.startswith("scope:"):
            continue
        return line.split(":", 1)[1].strip().strip("\"'") == SURFACE_SCOPE
    return True


def declared(pm):
    """What this project declares as its test surface, or None when it declares none."""
    for item in _items(os.path.join(pm, *INVARIANTS_DIR), _could_declare):
        if str(item.get("scope") or "").strip() != SURFACE_SCOPE:
            continue
        value = item.get("value")
        if isinstance(value, dict):
            return value
    return None


def judged_surfaces(value):
    """The declared surfaces still worth judging — DEC-0056's cost clause, as the project's data.

    A surface whose declared duration is at or under the threshold is dropped: repeating it is not
    the cost DEC-0050 measured, and refusing it would charge the legitimate path for nothing. A
    surface that declares NO duration is judged — silence is not a claim of cheapness.
    """
    floor = value.get("judged_above_seconds")
    floor = float(floor) if isinstance(floor, (int, float)) else 0.0
    out = []
    for entry in value.get("surfaces") or []:
        if not isinstance(entry, dict) or not entry.get("runner") or not entry.get("root"):
            continue
        seconds = entry.get("seconds")
        if isinstance(seconds, (int, float)) and float(seconds) <= floor:
            continue
        out.append(entry)
    return out


def _normalised(text):
    """A path word as this gate compares it: forward slashes, `.`/`..` segments resolved.

    RESOLVED AND NOT MERELY TRIMMED: comparing the raw word let every spelling that MEANS the
    declared root without spelling it walk past — measured 2026-09-05 on a scaffolded pilot,
    `pytest tests/.`, `pytest tests/../tests`, `pytest ..` and the ABSOLUTE path were each rc 0
    while `pytest tests/` was rc 2. `posixpath`, not `os.path`: the comparison is on forward
    slashes and `os.path.normpath` hands back backslashes on Windows.
    """
    word = str(text or "").replace("\\", "/").strip()
    if not word:
        return "."
    return posixpath.normpath(word).rstrip("/") or "."


def is_absolute(word):
    """Does this word name a place without help from a working directory?

    Three shapes and not one, because `posixpath.isabs` answers only the first: a POSIX root
    (`/x`), a Windows drive (`C:/x`) and a UNC share (`//host/share`).
    """
    here = str(word or "").replace("\\", "/")
    return here.startswith("/") or bool(re.match(r"^[A-Za-z]:/", here))


def drive_relative(word):
    """`C:tests` — a drive letter with no separator behind it.

    A place this reader cannot compute: it names the current directory OF THAT DRIVE, which is
    per-drive state of the shell and not something a payload carries. Measured 2026-09-05 on a
    pilot: `pytest C:tests` collected what `pytest tests` collects, and this gate was rc 0.
    """
    here = str(word or "").replace("\\", "/")
    return bool(re.match(r"^[A-Za-z]:(?!/)", here))


def _identity(path):
    """What the filesystem calls this place — `(st_dev, st_ino)` — or None if it has no name yet."""
    try:
        info = os.stat(path)
    except (OSError, ValueError):
        return None
    return info.st_dev, info.st_ino


def _anchored(path):
    """`(anchor, tail)`: the identity of the deepest EXISTING ancestor, and the text below it.

    THE KIT'S OWN COPY OF A PROPERTY THE WORKSHOP ALREADY BUILT, and that is said plainly rather
    than hidden: the workshop's `.claude/hooks/_harness.py` (`_anchored`, `_ancestor_identities`,
    `under`) answers exactly this question for its own gates, with the measurement behind it
    (TSK-0007/TSK-0008). A kit ships without `_harness`, so the property is rebuilt here — the two
    are pinned against each other by
    `tools/test_hooks.py::test_the_kit_reader_and_the_workshops_agree_on_what_one_place_is`,
    so they cannot drift apart in silence.

    WHAT IT IS NOT is the workshop's version in full: `_harness` puts every filesystem question
    under its gate's deadline (`probe`). Here the bound is the watchdog in
    `_kernel.start_the_deadline`, which turns a filesystem that does not answer into a refusal
    rather than into a kill. (The tail is case-folded in BOTH -- an earlier version of this
    sentence named that as a difference and it is not one.)
    """
    text = os.path.realpath(os.path.abspath(str(path)))
    names = []
    while True:
        identity = _identity(text)
        if identity is not None:
            return identity, tuple(reversed(names))
        head, name = os.path.split(text)
        if head == text or not name:
            return os.path.normcase(text), tuple(reversed(names))
        names.append(os.path.normcase(name))
        text = head


def _ancestor_identities(path):
    """Every existing directory at or above `path`, as identities."""
    text = os.path.realpath(os.path.abspath(str(path)))
    out = []
    while True:
        identity = _identity(text)
        if identity is not None:
            out.append(identity)
        head, name = os.path.split(text)
        if head == text or not name:
            return tuple(out)
        text = head


def under(path, base):
    """Is `path` `base` itself, or inside it? — asked of the filesystem, not of two strings."""
    anchor, tail = _anchored(path)
    other, other_tail = _anchored(base)
    if other_tail:
        return anchor == other and tail[:len(other_tail)] == other_tail
    return other in _ancestor_identities(path)


def placed(word, cwd):
    """Where on this filesystem the word points, or None when this reader cannot compute it."""
    if drive_relative(word):
        return None
    if is_absolute(word):
        return str(word).replace("\\", "/")
    if not cwd:
        return None
    return posixpath.join(_normalised(cwd), _normalised(word))


def _brace_expanded(word):
    """Every word a shell's BRACE expansion makes of this one, or None when this reader cannot say.

    THE SECOND EXPANSION. A shell performs two on a positional path word: pathname expansion, which
    `glob.has_magic` answers for, and brace expansion, whose whole syntax is one character. Reading
    only the first is what let `<root>/{test_*,conftest}.py` through -- measured with the real shell
    and a shim that logs the runner's argv: 41 `.py` paths handed over, the whole surface, rc 0
    (merge verify round 2, R2-B4).

    WHAT IT DOES NOT DO, and says so by answering None: a brace group with no top-level comma.
    Measured with the real shell (merge verify round 3, R3-M1), those are TWO different words and
    this reader cannot tell them apart: Git Bash leaves `<root>/{test_*}.py` literal -- one
    positional -- and expands `{1..9}` to nine. Deciding that needs a range grammar this reader
    does not have, so the word is one whose expansion is unknown, and the refusal says exactly
    that. An unmatched `{` is not an expansion at all -- a shell leaves it literal -- so the word
    comes back unchanged.

    `.claude/hooks/test_gates.py::test_gate5_reads_the_brace_expansion_a_shell_would_perform`
    """
    text = str(word)
    start = text.find("{")
    if start < 0:
        return [text]
    depth, end = 0, -1
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                end = index
                break
    if end < 0:
        return [text]                       # an unmatched brace stays literal in a shell too
    parts, level, current = [], 0, ""
    for char in text[start + 1:end]:
        if char == "{":
            level += 1
        elif char == "}":
            level -= 1
        if char == "," and level == 0:
            parts.append(current)
            current = ""
            continue
        current += char
    parts.append(current)
    if len(parts) < 2:
        return None                         # a range or a single word: not this reader's syntax
    out = []
    for part in parts:
        deeper = _brace_expanded(text[:start] + part + text[end + 1:])
        if deeper is None:
            return None
        out.extend(deeper)
    return out


def expansion_covers(word, root, project_root, cwd, members):
    """A positional the SHELL expands: does the match set hand the runner the whole surface?

    THE HOLE THIS CLOSES, measured as a process 2026-09-05: `pytest <root>/test_*.py` was rc 0
    against a surface declared at 3465 s while the root held 40 matching files — the whole run,
    waved through, because the reader placed the word as ONE path, found it inside the root, and
    read "inside the root" as "narrows the run". A glob narrows nothing; the shell replaces it with
    everything it matches, and this gate has the same filesystem.

    WHAT DECIDES IS THE DECLARATION, not a rule about any runner: a surface may declare `members`,
    the glob relative to its root that picks the files a bare run of that root would hand the
    runner. The word covers the surface when its expansion holds every one of them. A surface that
    declares no `members` gets the fail-closed direction and its own sentence — this reader cannot
    tell such a glob from the whole surface, so it does not wave it through.

    Returns (covers, why_unplaceable, glob_word).
    """
    spellings = _brace_expanded(str(word))
    if spellings is None:
        return True, None, (str(word), "this reader cannot compute that "
                            "expansion -- a brace group with no top-level comma "
                            "is either left literal or a range, and it does not "
                            "decide which")
    # EACH SPELLING GETS THE QUESTION IT DESERVES, and the WORD covers when any of them does.
    # A spelling without pathname magic is an ordinary positional -- `{tools,docs}` expands to
    # `tools`, which IS a declared root, and asking the members comparison about a directory said
    # "selection" (measured after the first cut of this branch).
    for one in spellings:
        if globmodule.has_magic(one):
            continue
        hit, why = covers(one, root, project_root, cwd)
        if hit:
            return True, why, None
    globs = [one for one in spellings if globmodule.has_magic(one)]
    if not globs:
        return False, None, None
    here = [placed(one, cwd) for one in globs]
    if any(one is None for one in here):
        return True, str(word), None
    target = os.path.join(project_root, *_normalised(root).split("/"))
    matched = {os.path.normcase(os.path.abspath(one))
               for spelling in here
               for one in globmodule.glob(spelling.replace("/", os.sep))}
    if not os.path.isdir(target):
        # A ROOT THAT IS A FILE is covered exactly when the expansion holds that file. No members
        # question arises -- a bare run of such a surface runs one file -- and asking one anyway
        # made a selection aimed at ANOTHER surface meet this surface's fail-closed sentence.
        return os.path.normcase(os.path.abspath(target)) in matched, None, None
    if not members:
        return True, None, (str(word), "the declared surface %r says nothing about which files a "
                                       "full run of it covers" % str(root))
    declared = {os.path.normcase(os.path.abspath(one))
                for one in globmodule.glob(os.path.join(target, *str(members).split("/")))}
    if not declared:
        return True, None, (str(word), "the declared surface %r says nothing about which files a "
                                       "full run of it covers" % str(root))
    return declared <= matched, None, None


def covers(word, root, project_root, cwd):
    """Does this positional hand the runner the WHOLE of `root`? — `(covers, why_unplaceable)`.

    THE BASE IS THE PROJECT ROOT, not the shell's working directory, because that is what the
    declared surfaces are relative to. Measured 2026-09-05 on a pilot with a payload `cwd` one
    level above the project: `pytest "<abs>/tests"` and `pytest <name>/tests` were both rc 0 while
    the same lines from inside were rc 2.

    FOUR OUTCOMES. The word is the root or an ancestor of it (covers); it lies INSIDE the project
    and is not the root (a selection); it is a place this reader CAN find and that is not this
    project at all (a selection too — see `placeable`); or it cannot be placed at all — a
    drive-relative word, an unmounted drive, a UNC share nobody serves, or no `cwd` in the payload.
    Only the last COVERS, and it carries its own sentence: claiming that a line naming another
    machine runs this project's test surface is a claim that is not true.
    """
    here = placed(word, cwd)
    if here is None:
        return True, str(word)
    target = os.path.join(project_root, *_normalised(root).split("/"))
    if under(target, here):
        return True, None
    if under(here, project_root):
        return False, None
    if placeable(here):
        # A PLACE THIS READER CAN FIND, AND IT IS NOT THIS PROJECT -- decidably not the declared
        # surface, so a selection. Refusing it fell on every run against a scratch tree outside the
        # project, which is how a role is told to reproduce a defect. A LINK from outside INTO the
        # project does not slip through: the identity reader above answers first.
        return False, None
    return True, str(word)


def placeable(here):
    """Can this reader say WHERE this word is at all — or only that it looks like a path?

    THE DEEPEST EXISTING ANCESTOR DECIDES, and a filesystem ROOT does not count as one. That is the
    line between "a suite somewhere else on this machine" and a spelling this process cannot
    resolve: a POSIX-style path a Windows process turns into a directory nobody has, a drive that is
    not mounted, a UNC share nobody serves — all of them climb to a root without finding anything
    and stay unplaceable; a scratch suite under a real directory is found at its first step.
    """
    text = os.path.abspath(str(here).replace("/", os.sep))
    while True:
        head = os.path.dirname(text)
        if head == text:
            return False
        if _identity(text) is not None:
            return True
        text = head


def _names_the_runner(word, runner):
    return os.path.basename(_normalised(word)) in (runner, runner + ".exe")


def handed_to(words, runner):
    """The words this stage hands `runner`, or None when it does not run `runner`.

    THE WORDS AFTER IT, and that boundary is load-bearing: `-m` belongs to two programs at once —
    the interpreter's module flag in `python -m pytest` and pytest's own marker filter in
    `pytest -m slow`. Read over the whole stage, the first of those makes every `python -m` line
    look like a selection.
    """
    if not words:
        return None
    if _names_the_runner(words[0], runner):
        return list(words[1:])
    for index, word in enumerate(words[:-1]):
        if str(word) == MODULE_FLAG and _names_the_runner(words[index + 1], runner):
            return list(words[index + 2:])
    return None


def narrowing_option(handed, declared_options):
    """The first word handed to the runner that the project declared as one after which the line no
    longer runs the whole surface, or None. Compared on the option NAME, so `-k=x` counts.

    A VALUE THAT IS EMPTY IS NOT A SELECTION, and that is measured rather than reasoned: `-k ""`
    and `-m ""` leave the runner selecting nothing away — three of three fixture tests still ran
    (2026-09-05).

    THE LAST OCCURRENCE OF A NAME DECIDES, because that is what the runner does with it: argparse
    keeps the last value. Reading the FIRST hit was fail-open and measured so — `-k alpha -k ""`
    ran three of three tests while this gate answered rc 0.

    WHAT THIS CANNOT DECIDE, named rather than implied: a value that is well-formed and happens to
    match nothing (`--deselect does::not::exist`). Telling that apart needs a collection, which is
    the cost this gate exists to avoid.
    """
    words = [str(word) for word in handed]
    last = {}
    for index, text in enumerate(words):
        if not text.startswith("-"):
            continue
        name, joined, value = text.partition("=")
        if name not in declared_options:
            continue
        if joined:
            last[name] = text if value.strip() else None    # `-k=` is an empty expression
            continue
        following = words[index + 1] if index + 1 < len(words) else None
        empty = (following is not None and not following.startswith("-")
                 and not following.strip())
        last[name] = None if empty else text                # `-k ""` is an empty WORD
    for text in last.values():
        if text is not None:
            return text
    return None


def _assignment(word):
    """(name, value) when this word is an environment assignment in either shell, else None."""
    text = str(word)
    if "=" not in text or text.startswith("-"):
        return None
    name, _sep, value = text.partition("=")
    name = name.strip()
    for prefix in ("$env:", "env:"):
        if name.lower().startswith(prefix):
            name = name[len(prefix):]
            break
    return name.strip(), value.strip().strip("\"'")


def _stages(pipeline):
    """A pipeline cut into the stages a shell runs beside each other."""
    out, current = [], []
    for token in pipeline:
        if shell._operator(token) == "|":
            out.append(current)
            current = []
        else:
            current.append(token)
    out.append(current)
    return out


def delivery_value(pipelines, runner_stage):
    """What `DELIVERY_RUN` is set to in front of the runner, or None.

    Two places, because the two shells write the same intent differently: an assignment among the
    runner stage's own words, and a command of the line that runs nothing but assignments — which
    is what PowerShell's `$env:NAME="v"; cmd` looks like once the `;` has cut it.
    """
    for word in runner_stage:
        pair = _assignment(word)
        if pair is not None and pair[0] == DELIVERY_MARKER:
            return pair[1]
    for pipeline in pipelines:
        for stage in _stages(pipeline):
            if shell._stage_verb(stage):
                continue
            for word in stage:
                pair = _assignment(word)
                if pair is not None and pair[0] == DELIVERY_MARKER:
                    return pair[1]
    return None


def open_item(repo_root, pm, named):
    """Is `named` an id of this project that can carry work and is not finished?

    Asked of the kernel's own automata, so this gate carries no status vocabulary. A kernel that
    will not load leaves the question unanswerable, and the answer to that is "not open" — the
    prefix is what lifts a refusal, so an unverifiable prefix must not lift one.
    """
    try:
        types = _kernel.kernel_module("backlog_types", repo_root)
        state = _kernel.open_state(repo_root)
        item, _archived = state.read_anywhere(named)
    except Exception:  # noqa: BLE001
        return False
    if not isinstance(item, dict):
        return False
    try:
        item_type, _number = types.parse_id(named)
    except Exception:  # noqa: BLE001
        return False
    automaton = types.AUTOMATA.get(item_type)
    if automaton is None:
        return False
    return str(item.get("status") or "") not in automaton.terminals


def recorded_full_run(pm, item_id):
    """(evidence id, result) of the newest Evidence for `item_id` that records a full run."""
    found = []
    for item in _items(os.path.join(pm, *EVIDENCE_DIR)):
        if str(item.get(RUN_SCOPE_FIELD) or "").strip().lower() != FULL:
            continue
        related = item.get("related")
        related = related if isinstance(related, (list, tuple)) else [related]
        if item_id not in [str(one).strip() for one in related if one]:
            continue
        found.append((str(item.get("id") or ""), str(item.get("result") or "").strip().lower()))
    return sorted(found)[-1] if found else None


def _delivery_line(tool, command):
    if str(tool or "") == "PowerShell":
        return '$env:%s="<ITEM-ID>"; %s' % (DELIVERY_MARKER, command.strip())
    return "%s=<ITEM-ID> %s" % (DELIVERY_MARKER, command.strip())


def _mentions(command, runners):
    """Cheap pre-filter — see the module docstring for what it does not see."""
    flat = "".join(char for char in str(command or "") if char not in "\"'\\`")
    return any(runner in flat for runner in runners)


def main():
    data = _kernel.payload(HOOK)
    if data.get("tool_name") not in SHELL_TOOLS:
        sys.exit(0)
    command = str((data.get("tool_input") or {}).get("command") or "")
    if not command.strip():
        sys.exit(0)
    repo_root = _kernel.find_repo_root(data.get("cwd"))
    pm = _kernel.state_dir(repo_root)
    if not os.path.isdir(pm):
        sys.exit(0)
    value = declared(pm)
    if not value:
        sys.exit(0)
    surfaces = judged_surfaces(value)
    if not surfaces:
        sys.exit(0)
    if not _mentions(command, {str(entry["runner"]) for entry in surfaces}):
        sys.exit(0)
    options = value.get("options_that_narrow") or {}

    pipelines = shell._pipelines(shell._tokenise(command))
    for pipeline in pipelines:
        for stage in _stages(pipeline):
            words = [str(word) for word in stage]
            for entry in surfaces:
                runner = str(entry["runner"])
                handed = handed_to(words, runner)
                if handed is None:
                    continue
                if narrowing_option(handed, set(options.get(runner) or ())) is not None:
                    continue
                targets = [word for word in handed if not word.startswith("-")]
                verdicts = []
                for word in targets:
                    if globmodule.has_magic(str(word)) or "{" in str(word):
                        verdicts.append(expansion_covers(
                            word, entry["root"], repo_root, data.get("cwd"),
                            entry.get("members")))
                        continue
                    hit, why = covers(word, entry["root"], repo_root, data.get("cwd"))
                    verdicts.append((hit, why, None))
                if targets and not any(hit for hit, _why, _glob in verdicts):
                    continue
                unplaceable = next((why for hit, why, _glob in verdicts if hit and why), None)
                unreadable_glob = next((one for hit, _why, one in verdicts if hit and one), None)
                _judge(data, repo_root, pm, command, entry, pipelines, stage, unplaceable,
                       unreadable_glob)
    sys.exit(0)


def _judge(data, repo_root, pm, command, entry, pipelines, runner_stage,
           unplaceable=None, unreadable_glob=None):
    """This stage runs the whole of one declared surface — the three answers, in FR-0086's order."""
    named = delivery_value(pipelines, runner_stage)
    if named is None and unreadable_glob:
        # ITS OWN SENTENCE, for the reason the unplaceable branch has one: saying "this runs the
        # whole surface" about `<root>/test_x*.py` would be a claim this reader has not made.
        _kernel.block(
            HOOK,
            "this line hands the runner a word the SHELL expands (%r), and %s -- so this gate "
            "cannot tell the expansion apart from the whole surface.\n"
            "It is read as one that MIGHT run it, which is the fail-closed direction.\n"
            "Remedy: name the files without a wildcard, or add `members` to that surface in the "
            "`%s` invariant -- the glob, relative to the root, that picks the files a bare run of "
            "it would run."
            % (unreadable_glob[0], unreadable_glob[1], SURFACE_SCOPE))
    if named is None and unplaceable:
        # ITS OWN SENTENCE: a word on another drive does not run this project's test surface, and
        # saying it does sends the reader to a knob for a problem that is not there.
        _kernel.block(
            HOOK,
            "this line could not be placed against this project: %r names no position this gate "
            "can compare with the declared test surface `%s` — another drive, a UNC share, a "
            "drive-relative word, or a shell whose working directory the payload does not carry. "
            "It is therefore read as one that MIGHT run the whole surface, which is the "
            "fail-closed direction." % (unplaceable, entry["root"]),
            remedy="spell the target as a path inside this project, or run it from a shell whose "
                   "working directory lies inside the project it belongs to.")
    if named is None:
        _kernel.block(
            HOOK,
            "this line runs the WHOLE declared test surface `%s` (%s), and nothing on it says "
            "this is the delivery run.\n"
            "During a task only the tests that read what the task changed are run; the FULL run is "
            "a DELIVERY criterion and happens once, after the last rework and before the merge. "
            "The project declares this surface at %g s per run."
            % (entry["root"], entry["runner"], float(entry.get("seconds") or 0)),
            remedy="run the tests that read what you changed (a path, a node id, or a filter "
                   "option this project declared) -- or, if this IS the delivery run, say so on "
                   "the line and record it as the Evidence the merge reads:\n"
                   "    %s\n"
                   "    python scripts/harness.py evidence --kind test --result pass "
                   "--related <ITEM-ID> --run-scope full --run-command \"<the line above>\" "
                   "--artifact-ref <the run log> --summary \"<what it showed>\"\n"
                   "If a full run of this surface is not worth judging, lower "
                   "`judged_above_seconds` in the project's `%s` invariant."
                   % (_delivery_line(data.get("tool_name"), command), SURFACE_SCOPE))
    if not open_item(repo_root, pm, named):
        _kernel.block(
            HOOK,
            "this line calls itself the delivery run (`%s=%s`), but %r is not an open item of this "
            "project. The delivery run is the run one item's merge rests on, so the prefix names "
            "that item -- a prefix that names nothing is a full run with a word in front of it."
            % (DELIVERY_MARKER, named, named),
            remedy="put the id of the open item this delivery run belongs to in the prefix.")
    recorded = recorded_full_run(pm, named)
    if recorded is not None and recorded[1] == "pass":
        _kernel.block(
            HOOK,
            "%s already has a PASSING full run on record (%s, `%s: %s`), so this would be the "
            "second one for the same item. The full run happens once, after the last rework; when "
            "it yields findings, their fixes are followed by full runs of the tests that READ the "
            "changed files, not by another whole-surface run."
            % (named, recorded[0], RUN_SCOPE_FIELD, FULL),
            remedy="run the tests that read what changed since %s in full and record them; a "
                   "second whole-surface run is the alternative, not the default." % recorded[0])


if __name__ == "__main__":
    _kernel.run_gate(HOOK, main)
