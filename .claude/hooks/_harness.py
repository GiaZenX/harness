#!/usr/bin/env python3
"""
Shared body of this repo's four PreToolUse gates (SR-0009, DEC-0003).

WHY THIS REPO HAS ITS OWN GATES AT ALL. It builds the team kits, so it cannot install one:
`gate_write_scope` refuses every write-capable command line that names `team-kits`, and here every
change is one. DEC-0003 records that decision and its cost -- the enforcement the kits ship is
replaced by gates written for this repo, plus a bound session agent so the payload shape the
kits' `calling_subagent` depends on is exercised here too.

WHAT IS BORROWED AND WHAT IS NOT. The reading of a hook payload and of a shell command line is the
kits': `team-kits/<kit>/hooks/_compat.py` for the payload, the invocations and the word readings,
and the kits' `gate_write_scope` MODULE ITSELF for the tokeniser, the pipeline split, the read-only
classification and the redirect shape (`shell_reader`, `written_paths`). Imported, not copied -- a
second regex for "does this line run git commit" or a second answer to "is this stage read-only" is
exactly the drift this repo keeps paying for, and that gate's own docstring records three rewrites
of the same rule. WHICH paths are protected is NOT borrowed: the kits ask a regex about `.claude`
and `project_memory`, this file asks `ProtectedArea`, which is derived. Neither is the REFUSAL --
`_compat.stop()` appends a pointer to the kit's own `ENFORCEMENT.md`, and that table documents the
kit gates, not these four. A pointer that names the wrong document is a claim nothing checks.

FAIL-CLOSED, INCLUDING ON THIS FILE'S OWN ERRORS -- IN TWO PLACES, BECAUSE ONE CANNOT COVER BOTH.
`guarded()` turns any unexpected exception raised INSIDE a gate's decision into a refusal. It
cannot cover the import of this module, which happens before any gate function runs: a missing or
truncated `_harness.py` used to raise at module level, and the provider reads a non-zero exit other
than 2 as "hook error, carry on", i.e. as an ALLOW. Measured 2026-08-05 with this file deleted:
all four gates answered rc 1. So every gate opens with a preamble that imports this module inside
its own `try` and exits 2 on failure -- the first statements of each `gate_*.py`, and
`test_gates.py::test_a_gate_whose_shared_body_is_gone_still_refuses` is what keeps them there.

AND ONE FAILURE NEITHER OF THEM COVERS: being KILLED. A gate that is still deciding when the
provider's timeout expires never reaches either guard, and the provider reads the kill the same way
it reads a crash -- carry on, i.e. allow. `Deadline` is that third place, and unlike the other two
it needs a number the code cannot invent: the one the registration states.

That is deliberate and it is expensive: a defect here stops every tool call the gate is registered
on, and no tool call can repair it, because gate 1 refuses writes to `.claude/` from the session.
The way out is named in every refusal (`ESCAPE_NOTE`) and it is the same one the kits assume: a
shell outside the provider, then a session restart.
"""
import functools
import hashlib
import importlib
import importlib.machinery
import importlib.util
import json
import os
import queue
import re
import shlex
import subprocess
import sys
import threading
import time

# BEFORE anything is imported out of `team-kits/`. That tree is the source side of the kit hash and
# of the staging the installer builds, and `kernel/hashing.py` (BYTECODE_SUFFIXES) states the
# obligation as a property of every ROUTE that starts an interpreter over it: refuse to cache into
# it. These gates are such a route. The registration in `.claude/settings.json` says `python -B` as
# well -- belt and braces, because the flag on the command line does not survive being rebuilt.
sys.dont_write_bytecode = True

# The kernel's state root in this repo. ONE structural fact, not a list of special cases: CLAUDE.md
# documents `kernel.cli --root project_memory` as the only way state is written here, and gate 3
# excludes exactly this directory from the diff it hashes -- an evidence record that has to be
# written INTO the subject it certifies can never certify it.
STATE_ROOT = "project_memory"
# The one subtree of it that is NOT canonical state. Spec II.4 calls it the proposal area, and the
# kits' `gate_write_scope` carves out exactly this name for the same reason: a draft nobody may
# write is a draft that cannot be handed over.
STAGING = "staging"

# The directory a provider reads to decide WHAT runs, WHO runs it and WHAT IT MAY DO -- hooks,
# their registration, the bound session role and its definition, the permission overlay. Named as
# that PROPERTY, which is the whole directory and is what SR-0009 puts in the protected area. The
# enumeration of provider files that stood in its place was a file short twice: `.claude/agents/**`
# (gate 2 reads a spawned role's own frontmatter out of it, and reads it FRESH on every call) and
# `.claude/settings.local.json` (a permission overlay the provider merges) both decide what these
# gates do and neither was in it.
PROVIDER_DIR = ".claude"

# Where a provider looks up the definition of an agent it is asked to spawn. A convention of the
# tool rather than of this repo; gate 2 reads the spawned agent's own frontmatter there.
AGENTS_DIR = os.path.join(PROVIDER_DIR, "agents")

# The provider's PreToolUse contract: this exit code, and only this one, is a refusal.
REFUSAL = 2

ESCAPE_NOTE = (
    "\nIf this gate is itself wrong or broken, it cannot be repaired from inside this session: it "
    "binds at session start, and gate 1 refuses writes to .claude/ from the session instance. Run "
    "the fix from a shell OUTSIDE Claude Code and start a new session.\n"
)


# -- the deadline the registration sets ---------------------------------------


# When this module was LOADED, which is the earliest clock a gate has of its own -- the provider
# started the process before that, and no process can measure the part of its own start that
# happened before its first line ran. The deadline is counted from HERE, so everything this run has
# needed since is spent out of the budget rather than added to it.
_LOADED_AT = time.monotonic()

# What a hook registration calls the time the provider waits for a gate, and the file it stands in.
TIMEOUT_KEY = "timeout"
SETTINGS_FILE = "settings.json"

# How much of the registered time this gate may spend before it has to have answered. A SHARE AND
# NOT A DERIVATION, said plainly: the only quantity in this problem a process can read is the
# registration, and the two it would need to derive a reserve from -- the start that happened
# before its first line ran, and the moment the provider actually stops listening -- it cannot see.
_SPENDABLE_SHARE = 0.8
# ...WHICH IS WHY THE SHARE IS NOT THE WHOLE RESERVE. What has to hold is that the reserve exceeds
# the process start, and a fifth of a SHORT registration does not: the share alone left this gate
# planning past its own start, and a gate that is still deciding when the provider gives up is
# killed -- which the provider reads as "hook error, carry on", i.e. as an ALLOW. So the reserve is
# the larger of the two, and this is the floor. Measured 2026-08-05 on this host over seven runs of
# a probe that reports `time.monotonic() - _LOADED_AT` while its parent times the whole process:
# 0.52 s to 0.81 s happen before this module's first line. The floor stands above the worst of them
# AND above the one span nothing here can measure -- from this process's exit to the provider
# noticing it. Its cost is named rather than hidden: under a registration shorter than this floor
# the budget is nil and the gate refuses every call it would have to ask the filesystem about.
_RESERVE_FLOOR = 1.5


def _matches(matcher, tool):
    """Could the provider apply a group with this matcher to a call on `tool`?

    EVERY READING THAT COULD APPLY COUNTS, and the direction is what makes that right: a group that
    applies states a deadline this gate has to survive, so one group too many can only SHORTEN the
    budget, while one too few is how a gate plans past the moment it is killed.

    The provider reads a matcher as an EXPRESSION; this repo's own registration spells alternations
    of tool names. Both readings are asked, because an expression matches calls no alternation of
    names does -- and one this reader cannot compile at all could match anything, so it counts too.
    """
    text = str(matcher or "")
    if not text.strip():
        return True
    if str(tool or "") in {part.strip() for part in text.split("|") if part.strip()}:
        return True
    try:
        return re.search(text, str(tool or "")) is not None
    except re.error:
        return True


def registered_timeout(root, script, tool):
    """The seconds the REGISTRATION gives `script` for a call on `tool`, or None if it states none.

    READ OFF THE FILE THE PROVIDER READS, AND THAT IS NOT THE SAME AS THE MOMENT IT KILLS. This is
    read on every call; the provider bound its own timeout when the session started. The two are
    therefore decoupled for as long as a session lasts, and whoever may write the registration can
    raise what this gate allows itself without touching the moment it is killed. `.claude/` is
    refused to the session agent and open to a subagent (H12), so that is a chain and not a
    theory -- `docs/POST_V2_WISHLIST.md` H25 carries it, measured, with what limits it instead. What
    IS gained by reading the file is the other direction: a number copied into this module would be
    the one that goes stale when the registration is lowered.

    THE SMALLEST APPLYING ENTRY ANSWERS: one script may be registered in several groups, any of
    them can be the one that is asked, so the shortest is the deadline it has to survive.
    `_matches` decides what applies.
    """
    path = os.path.join(root, PROVIDER_DIR, SETTINGS_FILE)
    with open(path, encoding="utf-8") as handle:
        settings = json.load(handle)
    stated = []
    for groups in (settings.get("hooks") or {}).values():
        for group in groups:
            if not _matches(group.get("matcher"), tool):
                continue
            for hook in group.get("hooks") or []:
                if any(os.path.basename(word.replace("\\", "/")) == script
                       for word in re.findall(r"[^\s\"']+", str(hook.get("command") or ""))):
                    stated.append(hook.get(TIMEOUT_KEY))
    if not stated or any(value is None for value in stated):
        return None
    return min(float(value) for value in stated)


class Deadline(object):
    """When this gate has to have answered, so that a SUBJECT cannot decide the call by taking long.

    A gate still working when the provider's timeout expires is killed, and a killed hook is an
    ALLOW. That makes every slow answer a route past the gate, and the filesystem hands one out for
    free: measured 2026-08-05 on this host, one question about a path on an unroutable UNC host
    costs 42.1 s, and a decision asks several per candidate. Gate 1 before this, against its
    registered 120: one candidate rc 0 after 21.8 s, three after 85.0 s, five after 211.3 s -- the
    last one past the deadline, rc 0, with no stderr at all.

    WHAT IS NOT SPENT is the reserve, and it is the LARGER of a share of the registered time and a
    floor -- `_SPENDABLE_SHARE` and `_RESERVE_FLOOR` carry both numbers and the measurement behind
    the second. The quantities a reserve would have to be derived from (the process start before
    this module's first line, and the moment the provider really stops listening) are outside what
    a process can read, so the floor is where that admission lives.

    A REGISTRATION THAT STATES NO TIMEOUT leaves this undecidable, and the fail-closed answer to
    that is a refusal: a gate that cannot know when it will be killed cannot promise to answer
    first. A registration SHORTER than the reserve is the same admission with a number: the budget
    is nil, and then EVERY call of that gate is refused -- not only one that asks the filesystem
    something. `_the_budget_is_spent` is what widened that, and deliberately: it stands beside the
    whole decision rather than inside the places that can take long (H35), so a spent budget is a
    refusal wherever the decision happens to be.

    WHAT THIS DOES NOT PROMISE is that the number read here is the one the provider kills by --
    see `registered_timeout`, whose boundary that is.
    """

    __slots__ = ("_at",)

    def __init__(self):
        self._at = None

    def start(self, root, data):
        script = os.path.basename(str(sys.argv[0] or ""))
        allowed = registered_timeout(root, script, data.get("tool_name"))
        if allowed is None:
            refuse(
                "this call could not be judged, because this gate cannot know how long it may "
                "take: no entry in %s/%s registers %r for tool %r with a `%s`.\n"
                "A hook still deciding when the provider's timeout expires is killed, and a killed "
                "hook is read as an allow -- so a gate without a stated deadline refuses rather "
                "than race one it cannot see.\n"
                "Remedy: give every registration of this gate an explicit `%s` in seconds."
                % (PROVIDER_DIR, SETTINGS_FILE, script, data.get("tool_name"), TIMEOUT_KEY,
                   TIMEOUT_KEY))
        reserve = max(allowed * (1.0 - _SPENDABLE_SHARE), _RESERVE_FLOOR)
        self._at = _LOADED_AT + max(0.0, allowed - reserve)

    def remaining(self):
        """Seconds left before the verdict has to be out -- None while no deadline has been set."""
        return None if self._at is None else self._at - time.monotonic()


_DEADLINE = Deadline()


class _Probes(object):
    """One worker thread for every question this apparatus puts to the filesystem.

    ONE, and not one per question: a question that does not come back in time IS the verdict, so
    after the first one the gate is leaving anyway and a second worker would have nothing to do.
    Measured 2026-08-05: a thread per question cost 0.18 s on a decision that asks 607 of them --
    paid by every ordinary call to buy an answer only the pathological one needs.
    """

    __slots__ = ("_asked", "_answered", "_worker")

    def __init__(self):
        self._asked = None
        self._answered = None
        self._worker = None

    def _serve(self):
        while True:
            question, subject = self._asked.get()
            try:
                self._answered.put((True, question(subject)))
            except BaseException as error:  # noqa: BLE001 -- the caller decides what an error means
                self._answered.put((False, error))

    def ask(self, question, subject, seconds):
        """(True, outcome) if the answer came back inside `seconds`, (False, None) if it did not."""
        if self._worker is None:
            self._asked, self._answered = queue.Queue(), queue.Queue()
            self._worker = threading.Thread(target=self._serve, daemon=True)
            self._worker.start()
        self._asked.put((question, subject))
        try:
            return True, self._answered.get(timeout=max(seconds, 0.0))
        except queue.Empty:
            return False, None


_PROBES = _Probes()


def probe(question, subject):
    """Ask the filesystem `question` about `subject` without letting it decide the call.

    THE CALL CANNOT BE CANCELLED -- `os.stat` on an unreachable host blocks inside the operating
    system, and no timeout reaches it there. What CAN be bounded is the WAIT: the question is
    handed to a worker and the answer waited for only as long as the deadline allows. A worker left
    standing in a blocked call is a daemon, so it does not hold the process open, and the process is
    leaving anyway -- a question that does not come back in time IS the verdict here.

    NOT A LIST OF PATHS THAT MIGHT BE SLOW. Which host answers in what time is not readable from a
    path, and a prefix table would have to claim that `\\\\localhost\\C$\\` is fine while the next
    share is not -- a statement about the network, written down in a gate. What IS decidable is how
    long this gate may take, so that is what bounds it.

    BEFORE A DEADLINE EXISTS the question is asked directly, and what that leaves unbounded is
    named rather than implied: until the payload has been read there is no registration to read a
    deadline out of, and the probes in that window are of `sys.path` ENTRIES -- `StandardLibraryWins`
    asking which of them may answer for a standard-library name. An entry on an unreachable host
    would block there, outside every bound this class puts on the rest.
    """
    left = _DEADLINE.remaining()
    if left is None:
        return question(subject)
    answered, outcome = _PROBES.ask(question, subject, left)
    if not answered:
        refuse(
            "this tool call could not be inspected within the time its registration allows: the "
            "filesystem did not answer for %r before this gate's budget was spent.\n"
            "An unreachable host answers a single question in tens of seconds, and a gate that "
            "waits for it is killed by the provider -- which reads that as an allow. So the gate "
            "refuses instead.\n"
            "Remedy: name paths this host can reach, or run the call from a shell OUTSIDE Claude "
            "Code." % (subject,))
    ok, value = outcome
    if ok:
        return value
    raise value


# -- one file, however it is spelled ------------------------------------------


@functools.lru_cache(maxsize=None)
def _identity(path):
    """What the filesystem calls this file -- `(st_dev, st_ino)` -- or None if it has no name yet."""
    try:
        info = probe(os.stat, path)
    except (OSError, ValueError):
        return None
    return info.st_dev, info.st_ino


def _resolved(path):
    """`path` made absolute with every link followed -- under the deadline, like every question here.

    RESOLVING IS A FILESYSTEM QUESTION TOO, and that is not obvious from its name: on Windows
    `os.path.realpath` goes through `nt._getfinalpathname`, which blocks on an unreachable host
    exactly as `stat` does. Measured 2026-08-05 with only `stat` bounded: the refusal fired on
    time and the process still took 42.7 s against a 5 s budget, because the wait was here.
    """
    return probe(os.path.realpath, os.path.abspath(str(path)))


@functools.lru_cache(maxsize=None)
def _anchored(path):
    """`(anchor, tail)`: the identity of the deepest EXISTING ancestor, and the text below it.

    "The same file" is a question for the filesystem, not for a comparison of spellings, and the
    identity is what the filesystem answers with. Measured 2026-08-05 (TSK-0008): the plain path,
    the extended-length `\\\\?\\` form, the administrative share `\\\\localhost\\C$\\`, `\\\\?\\UNC\\`
    and the 8.3 alias of one kit file all report ONE `(st_dev, st_ino)` pair, while `realpath`
    leaves the prefix and the UNC host standing -- so nine of eleven measured CALLS through those
    spellings were allowed while the same file spelled plainly was refused.

    A path that does not exist yet has no identity, and gate 1 exists for exactly those (a Write
    that CREATES a kit file). Its position is what answers instead: the identity of the nearest
    ancestor that does exist, plus the segments below it. The climb ends at a root of any of the
    four forms, which is `os.path.split` reporting `head == text`.
    """
    text = _resolved(path)
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


@functools.lru_cache(maxsize=None)
def _ancestor_identities(path):
    """Every existing directory at or above `path`, as identities."""
    text = _resolved(path)
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
    """Is `path` `base` itself, or inside it?

    Two questions, because `base` may be a file that exists and may be one that does not:
    an existing `base` is found by its IDENTITY among `path`'s ancestors, which is what makes every
    spelling of it the same answer; a `base` that does not exist yet can only be compared as
    position -- same anchor, and its segments a prefix of `path`'s.
    """
    anchor, tail = _anchored(path)
    other, other_tail = _anchored(base)
    if other_tail:
        return anchor == other and tail[:len(other_tail)] == other_tail
    return other in _ancestor_identities(path)


# The two directions a path can meet an area from. They are different facts about the call, so a
# refusal that cannot tell them apart says something false about one of them.
INSIDE = "inside"
CONTAINS = "contains"


def reaches(path, base):
    """How `path` reaches `base`: it IS or is inside it, it CONTAINS it, or it does not.

    BOTH DIRECTIONS, because a command line names a subject either way and only one of them is a
    containment test. `> team-kits/dev-team/hooks/gate_new.py` names a file INSIDE the protected
    tree that does not exist yet; `rm -rf team-kits` names every protected file under it without
    spelling a single one. A test in one direction only answers the first and reads the second as
    an unrelated path.

    THE ANSWER IS KEPT rather than collapsed to a yes, and that is this round's correction: a
    candidate that merely CONTAINS the state directory -- a bare drive letter, a `..`, the repo
    root itself -- was refused with the words "this is canonical project state", which it is not.
    `ProtectedArea.verdict` words the two cases differently now; `docs/POST_V2_WISHLIST.md` H19
    carries what the containment direction costs.
    """
    if under(path, base):
        return INSIDE
    if under(base, path):
        return CONTAINS
    return None


def touches(path, base):
    """Does `path` reach `base` at all, in either direction? (see `reaches`)"""
    return reaches(path, base) is not None


# -- reaching the kit modules -------------------------------------------------


class StandardLibraryWins(object):
    """Keeps a file in this apparatus's own directories from answering for a standard-library name.

    THE SUBJECT IS EVERY DIRECTORY THIS DECISION RUNS OUT OF -- this file's own (`sys.path[0]`,
    because the provider starts a gate as a script and its preamble inserts it as well) and
    `team-kits/`, which the kits are reached through. The kit hooks directory needs no entry of its
    own: it lies INSIDE `team-kits/`, and `owns` asks about containment, not about equality. All of
    them carry code a gate loads while deciding, and all of them are writable by SOMEBODY in the
    change circle.

    A FINDER AND NOT `sys.path` HYGIENE, because the shadow is created DURING an import this
    module is in the middle of: `team-kits/<kit>/hooks/gate_write_scope.py` and
    `tools/bump_kit_version.py` each insert their own directory at `sys.path[0]` while they load,
    so a `sys.path` restored afterwards is restored too late. Measured 2026-08-05 (TSK-0008, B2):
    a `shlex.py` in any of the three answered `import shlex` for the kits' tokeniser,
    and a stub that raises nothing left `written_paths` empty -- gate 1 allowed `sed -i` into
    `team-kits/kernel/state.py` with rc 0 and no stderr at all.

    WHAT IT MAY NOT DO is refuse a legitimate import out of those directories, so it answers for
    one property only: a name the running interpreter itself declares to be standard library
    (`sys.stdlib_module_names`) that one of them is currently in front of.
    `test_no_module_of_this_apparatus_is_named_after_a_standard_library_module` pins that end.

    WHICH DIRECTORY THE ATTACK ACTUALLY NEEDS THIS FOR IS MEASURED, and it is one of them, not
    three: ablated 2026-08-05 (finder removed, stub planted, real gate process), only the KIT HOOKS
    directory changes its answer -- because `gate_write_scope.py` inserts it at `sys.path[0]` while
    it loads. A stub in the gate's own directory is refused either way, but for a different reason
    (the payload reader is stubbed too, so the call comes out uninspectable), and one in the kit
    root is refused either way because by the time `tools/bump_kit_version.py` puts THAT at
    position 0, every module the reader needs is already in `sys.modules`.
    `test_a_planted_module_cannot_answer_for_a_standard_library_name` asserts the REASON for that
    difference rather than the exit code alone.
    """

    def __init__(self):
        self.directories = ()

    def owns(self, entry):
        if not entry:
            return False
        return any(under(entry, directory) for directory in self.directories)

    def find_spec(self, fullname, path=None, target=None):
        if path is not None or fullname.partition(".")[0] not in sys.stdlib_module_names:
            return None
        clean = [entry for entry in sys.path if not self.owns(entry)]
        if len(clean) == len(sys.path):
            return None
        return importlib.machinery.PathFinder.find_spec(fullname, clean, target)


_STANDARD_LIBRARY_WINS = StandardLibraryWins()


def _guard_the_standard_library(directories):
    """Put the finder in front of the one importer that consults `sys.path`."""
    _STANDARD_LIBRARY_WINS.directories = tuple(directories)
    if _STANDARD_LIBRARY_WINS in sys.meta_path:
        return
    try:
        index = sys.meta_path.index(importlib.machinery.PathFinder)
    except ValueError:
        # nothing here reads `sys.path`, so nothing on it can shadow anything
        return
    sys.meta_path.insert(index, _STANDARD_LIBRARY_WINS)


def repo_root(data=None):
    """This repo's root, resolved the way every kit hook resolves it.

    Through the kits' own `_root.find_repo_root`, so `CLAUDE_PROJECT_DIR` and the cwd-drift
    fallback behave identically here and there. Bootstrapping it needs a root already, and that
    one is read off THIS file's location (`.claude/hooks/_harness.py`), which is the only anchor
    available before any kit module is importable.
    """
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _add_kit_paths(here)
    return _from_kit("_root").find_repo_root(str((data or {}).get("cwd") or "") or here)


def kit_hooks_directories(root):
    """Every directory under `team-kits/` that ships a kit's hooks, in a stable order.

    DERIVED, and the derivation is the point: the three kits ship `_compat.py` byte-identical
    (`tools/test_hooks.py` KIT_SPECIFIC_HOOKS names the exceptions, and this is not one), so
    naming one kit here would be an enumeration of one that goes stale the day that kit is
    renamed. A directory that IS a kit's and ships that helper is a directory the provider of a
    scaffolded project starts programs out of, which is the property both callers below want.

    WHAT A KIT IS COMES FROM THE KERNEL and is not repeated here. The predicate stood spelled out
    below its own docstring's claim that `kernel.hashing.is_kit_dir` decides -- two answers to one
    question, which is the drift this apparatus keeps paying for. It is reachable at this point
    because `team-kits/` alone is enough to import the kernel from, and this function puts it on
    `sys.path` before it asks.
    """
    kits = os.path.join(root, "team-kits")
    _guard_the_standard_library((kits, os.path.dirname(os.path.abspath(__file__))))
    if kits not in sys.path:
        sys.path.append(kits)
    is_kit_dir = _from_kit("kernel.hashing").is_kit_dir
    found = []
    for entry in sorted(os.listdir(kits)):
        candidate = os.path.join(kits, entry, "hooks")
        if (is_kit_dir(os.path.join(kits, entry))
                and os.path.isfile(os.path.join(candidate, "_compat.py"))):
            found.append(candidate)
    return found


def _kit_hooks_dir(root):
    """The kit hooks directory these gates borrow their payload reader from -- the first that is
    one. Which of the mirrored kits answers is immaterial; that they are mirrored is what
    `kit_hooks_directories` rests on."""
    found = kit_hooks_directories(root)
    if not found:
        raise RuntimeError("no kit under %s ships hooks/_compat.py"
                           % os.path.join(root, "team-kits"))
    return found[0]


def _add_kit_paths(root):
    """Put `team-kits/` and one kit's `hooks/` on `sys.path`, once, and guard the standard library.

    APPENDED, never inserted at 0: the kit hooks directory holds modules named for their job
    (`_compat`, `_root`, `gate_*`), and putting it in FRONT of the standard library would let a
    future kit file shadow a stdlib module for these gates. Appending is not sufficient on its own
    -- see `StandardLibraryWins` for what inserts at 0 anyway, and when. `_kit_hooks_dir` does the
    first half (the kit root, and the guard) because it needs the kernel to answer at all.
    """
    hooks = _kit_hooks_dir(root)
    if hooks not in sys.path:
        sys.path.append(hooks)


def _from_kit(name):
    """Import a kit module, and leave `sys.path` as it was found.

    The kit hooks put their own directory at `sys.path[0]` as they load (`gate_write_scope.py`),
    and that entry outlives the import: a later `import yaml` here would then be answered out of a
    kit directory. `StandardLibraryWins` covers the names the interpreter calls standard library;
    this covers the rest, for as long as the entry is not one `_add_kit_paths` put there itself.
    """
    saved = list(sys.path)
    try:
        return importlib.import_module(name)
    finally:
        sys.path[:] = saved


def compat(data=None):
    """The kits' payload/shell reader, with `sys.path` prepared."""
    _add_kit_paths(repo_root(data))
    return _from_kit("_compat")


# -- the payload --------------------------------------------------------------


def payload():
    """The hook payload, normalized by the kits' reader.

    `tolerate_overflow=True` and the overflow handled HERE, not by `_compat.stop()`: the kit's
    refusal ends with a pointer to the kit's `ENFORCEMENT.md`, which does not describe these four
    gates. The verdict is the same one the kits reach -- an oversized payload could not be
    inspected, and for an integrity gate "not inspected" is not "allowed".
    """
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _add_kit_paths(here)
    module = _from_kit("_compat")
    data = module.load(tolerate_overflow=True)
    if data.get("_stdin_overflow"):
        refuse("This tool call could not be inspected: the hook payload exceeded the "
               "%d-byte stdin bound, so the gate refused rather than waved it through.\n"
               "Remedy: split the call." % module.STDIN_LIMIT)
    # HERE, because the deadline depends on the payload: the registration states a timeout per
    # TOOL, and which tool this is only the payload says.
    _DEADLINE.start(here, data)
    return data


def is_session_instance(data):
    """True when this call comes from the SESSION agent rather than from a subagent.

    Delegated to `_compat.calling_subagent`, whose docstring carries the definition and the
    regression that produced it: the question is whether the payload names an agent OTHER than the
    role `.claude/settings.json` binds as `agent:`, not whether it names one at all. That
    distinction is why this repo binds a session agent -- measured in a fixture that bound none,
    the wrong reading looked correct for a month.
    """
    return not compat(data).calling_subagent(data)


def refuse(message, note=""):
    """Block the call: exit 2 with the reason on stderr (the provider's PreToolUse contract)."""
    sys.stderr.write("[harness gate] " + message.rstrip() + "\n" + note + ESCAPE_NOTE)
    raise SystemExit(REFUSAL)


# How often the backstop below looks at the clock. What it bounds is how far past its budget a
# decision may run, and it is deliberately larger than nothing: an in-decision check that can name
# WHAT was slow (`probe`) fires on the budget itself, so one step of grace lets the precise refusal
# win the race against the blunt one.
_WATCH_STEP = 0.05

_OUT_OF_TIME = (
    "this tool call could not be inspected within the time its registration allows: reading it "
    "spent this gate's whole budget and it is still not decided.\n"
    "A gate that is still deciding when the provider gives up is killed, and a killed hook is read "
    "as an allow -- so it refuses instead.\n"
    "Remedy: split the call. What a command line costs this gate grows faster than its length.")


def _the_budget_is_spent():
    """Refuse from a thread of its own once the registration's time is gone.

    THE BOUND SITS OUTSIDE THE DECISION, because the decision is where the cost is. A check written
    into one surface bounds that surface and nothing else: `substituted_lines` held one, and the
    whole time went into a SINGLE call of it -- measured 2026-08-07, 2444 characters of command line
    cost gate 1 150.6 s against its registered 120, with the write in the same line really made
    (`docs/POST_V2_WISHLIST.md` H35).

    WHAT IT CANNOT INTERRUPT is one call into C that keeps the interpreter to itself, and that is
    measured rather than assumed: beside the kits' heredoc regex a thread of this shape ran ONCE in
    8.07 s, beside the substitution scan 517 times in 32.61 s. That half is not closed here; H36
    carries it with its chain.
    """
    while True:
        left = _DEADLINE.remaining()
        if left is not None and left <= -_WATCH_STEP:
            sys.stderr.write("[harness gate] " + _OUT_OF_TIME + ESCAPE_NOTE)
            sys.stderr.flush()
            os._exit(REFUSAL)
        time.sleep(_WATCH_STEP if left is None else max(min(left, _WATCH_STEP), 0.0))


def guarded(decide):
    """Run a gate's decision; turn anything unexpected into a refusal, never into an allow.

    A gate that crashes exits non-zero-but-not-2, which the provider reads as "hook error, carry
    on" -- an ALLOW. For an integrity gate that is the one outcome that must not follow from a
    defect, so the crash is converted into the refusal it should have been.

    A `SystemExit` IS SUCH A DEFECT UNLESS IT CARRIES THE REFUSAL CODE, and that is decidable
    rather than guessed: this function's own success exit stands AFTER `decide()`, and the only
    other exit this repo's gates raise is `refuse()`. Every remaining `SystemExit` was raised by
    somebody else -- measured 2026-08-05 (TSK-0008, B2): a module ending the process with
    code 0 while gate 1 was deciding made the gate answer rc 0 with no stderr at all.

    TAKING TOO LONG IS SUCH A DEFECT TOO, and it is the one that reads as an allow without any exit
    code at all: `_the_budget_is_spent` runs beside the decision and ends the process with the
    refusal code when the registration's time is gone.
    """
    threading.Thread(target=_the_budget_is_spent, daemon=True).start()
    try:
        decide()
    except SystemExit as ending:
        if ending.code == REFUSAL:
            raise
        refuse("this gate could not decide and therefore refused (fail-closed): something it "
               "loaded ended the process with exit code %r before a verdict was reached, and an "
               "exit this gate did not make is not a verdict it made." % (ending.code,))
    except BaseException as error:  # noqa: BLE001 -- see the docstring: an error is a refusal
        import traceback
        refuse("this gate could not decide and therefore refused (fail-closed):\n%s\n%s"
               % (error, traceback.format_exc()))
    raise SystemExit(0)


# -- what goes into a kit version --------------------------------------------


def _bump_tool(root):
    """`tools/bump_kit_version.py`, imported from its file.

    THE SAME TOOL, not a second answer. SR-0009 puts everything that enters a kit content hash
    inside gate 1's protected area, and that set already has exactly one producer: this script
    stamps `<kit>/VERSION` from it and `tools/validate.py` re-computes it. Loading it by path
    rather than copying `discover_kits` means a change to WHICH directories are kits is followed
    here on the day it is made; if the script is moved or renamed, this raises and `guarded()`
    turns that into a refusal rather than into a silently unprotected tree.
    """
    path = os.path.join(root, "tools", "bump_kit_version.py")
    spec = importlib.util.spec_from_file_location("_harness_bump_kit_version", path)
    module = importlib.util.module_from_spec(spec)
    # REGISTERED before it is executed, which `module_from_spec` does not do on its own. Two
    # reasons and the second is load-bearing: a module that imports itself needs it, and
    # `decision_inputs` derives the protected producer set from what the interpreter has loaded --
    # a producer missing from `sys.modules` would be a producer nothing protects.
    sys.modules[spec.name] = module
    saved = list(sys.path)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = saved
    return module


def kit_version_directories(root):
    """Every directory that contributes a file to some kit's VERSION hash.

    THE FILE LIST CANNOT BE THE ANSWER ON ITS OWN, and that is the whole reason this returns
    directories. `kit_hash_inputs` enumerates files that EXIST; a Write that CREATES
    `team-kits/dev-team/hooks/gate_new.py` names a path in no enumeration, and a gate that asks
    only "is this path in the set" waves through every new kit file -- the one shape a session
    agent would actually use to add enforcement code.

    So the question `covers()` asks is about the position: a path whose ANCESTOR is a directory
    the hash reads from is a path the hash would read, whatever its own name. Ancestor and not
    "nearest existing ancestor": `team-kits/<kit>/VERSION` and `team-kits/<kit>/newdir/x.py` both
    have `team-kits/` above them (the shared inputs at that root put it in this set), and a
    nearest-ancestor rule would have let both through.

    OVER-INCLUSION IS THE DIRECTION THIS ERRS IN, named rather than implied: `<kit>/VERSION` is
    excluded from the hash (it carries the result) and tool leftovers are excluded by
    `is_transient`, yet both come out protected here. Neither is a file a session agent has any
    business writing by hand -- the stamper writes the first and a toolchain the second.
    """
    directories = set()
    _add_kit_paths(root)
    bump = _bump_tool(root)
    kit_hash_inputs = _from_kit("kernel.hashing").kit_hash_inputs
    for kit in bump.discover_kits(root):
        for _name, path in kit_hash_inputs(os.path.join(root, "team-kits", kit)):
            if path is not None:
                directories.add(os.path.dirname(path))
    return directories


def decision_inputs(root):
    """Every file INSIDE this repo that this gate's own answer was computed from.

    MEASURED, NOT LISTED, and that is the whole point. The protected area is derived from
    `tools/bump_kit_version.py` (`_bump_tool` executes it) and from `kernel.hashing`, so whoever
    may rewrite those decides what gate 1 protects: measured 2026-08-05, two `Write` calls that
    made `discover_kits()` return `[]` left every kit file writable, without touching one
    protected path. A derivation that does not protect its own producer protects nothing.

    So this asks the interpreter which modules it ACTUALLY loaded while deriving the area, and
    keeps the ones inside the repo. A producer that is renamed, split or given a new helper is
    followed on the day it changes; a list here would be the next stale tuple. CALL IT AFTER
    everything the answer is computed from has run -- which for gate 1 includes the SUBJECTS, since
    the shell reader that says what a command line writes is as much a producer as the stamper is.
    The set is therefore payload-dependent by construction, and rightly so: a `Write` payload never
    loads the shell reader, so for that call the shell reader decided nothing.

    WHAT IT DOES NOT REACH, named rather than implied: files, not directories. A module that
    `bump_kit_version.py` imports lazily inside a function this gate never calls is not loaded and
    therefore not protected, and neither is a NEW file placed beside it. Only `tools/` as a whole
    would cover those, and `tools/` is not derivable from anything this gate reads.
    """
    files = set()
    for module in list(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if not name:
            continue
        try:
            if under(name, root):
                files.add(name)
        except (OSError, ValueError):  # pragma: no cover -- an unresolvable module path
            continue
    return files


# The audiences a refusal can have. They are different questions, so they are different answers:
# WHO writes decides one of them and nothing decides the other. The third is not an area at all --
# it is the answer for a subject that names no path this gate can compare (`Unplaceable`), and it
# refuses everyone because what it might name includes what everyone is refused.
EVERYONE = "everyone"
SESSION_ONLY = "the session agent"
NOWHERE_KNOWN = "everyone, and for a subject this gate cannot place"


class ProtectedArea(object):
    """What may not be written here, and by whom.

    FOUR AREAS, THREE OF THEM DERIVED, and the fourth (`.claude/`) is a definition -- the whole
    directory, which is what SR-0009 names; see `PROVIDER_DIR` for what an enumeration of provider
    files kept missing.

    THE AUDIENCE IS PART OF THE ANSWER. Kit content, the provider tree and the producer are
    refused to the SESSION INSTANCE only: a subagent writing kit code is the point of the change
    circle, and the implementer's own work order routinely names `.claude/hooks/**`. Canonical
    state is refused to EVERYONE, because it is the subject gate 3 certifies: a hand-written
    `evidence/active/EVD-*.yaml` with `result: pass` and the current digest in it opens `git
    commit` outright (measured 2026-08-05, rc 0 before this), and it does so whoever wrote it.
    That is the kits' rule too (`gate_write_scope`: "project_memory has exactly one writer, the
    kernel"), including its one carve-out -- `staging/**`, which spec II.4 defines as explicitly
    non-canonical.
    """

    __slots__ = ("root", "kit_directories", "producer_files", "provider_tree", "state_root",
                 "staging", "hook_directories")

    def __init__(self, root):
        self.root = root
        self.kit_directories = kit_version_directories(root)
        # AFTER the line above: `decision_inputs` reads what has been loaded
        self.producer_files = decision_inputs(root)
        self.provider_tree = os.path.join(root, PROVIDER_DIR)
        self.state_root = os.path.join(root, STATE_ROOT)
        self.staging = os.path.join(root, STATE_ROOT, STAGING)
        # Where a hook is STARTED from, for the `Executed` position only: this repo's provider tree
        # and the hook directory of every kit it ships. Both are places a provider runs programs
        # out of -- here at every tool call, there in every scaffolded project -- which is the
        # property `hand_driven` turns on.
        self.hook_directories = [self.provider_tree] + kit_hooks_directories(root)

    def hand_driven(self, path):
        """(audience, reason) for a file a command line would START, or (None, None).

        A HOOK IS A PROGRAM THE PROVIDER STARTS, on a payload the provider wrote. Started from a
        command line it runs on a payload the CALLER wrote, and that is the whole of an approval's
        provenance: `approvals.mint` accepts the approval hook run as itself, so a payload
        assembled from the readable pending request mints an approval nobody gave -- measured end
        to end in TSK-0097, and the same line is rc 2 in every scaffolded project because
        `gate_write_scope` reads a stage that names the enforcement layer as write-capable.

        REFUSED TO EVERYONE, and that is a different audience from the one the same file gets as a
        WRITTEN path. Who may EDIT enforcement code is the change circle's question and a subagent
        may; who may PLAY THE PROVIDER is not a question of role at all. Measured in TSK-0097: the
        hand-driven mint was rc 0 for the session instance AND for an implementer subagent, and
        `test_gate1_refuses_starting_a_hook_from_every_caller` is where both audiences are held to
        it -- the counter-direction, that a file OUTSIDE these directories stays startable, is
        `test_gate1_leaves_a_file_outside_the_hook_directories_startable`.

        STRICTLY INSIDE, and both halves of that were measured. Never CONTAINS: a word that merely
        holds a hook directory (`team-kits`, the repo root) stands in this position on every
        `PYTHONPATH=team-kits python ...` line this repo runs. And never the directory ITSELF:
        `under` answers yes for equality, so the first cut refused the word `.claude` -- a
        directory nothing starts -- and a verifier met it while copying a tree (measured
        2026-08-31, a PowerShell payload naming `.claude` in a list, rc 2). Equality is ruled out
        the way this file already spells containment, by asking the other direction too.
        """
        for directory in self.hook_directories:
            if under(path, directory) and not under(directory, path):
                return EVERYONE, (
                    "this file is started by the PROVIDER, on a payload the provider wrote -- it "
                    "is enforcement code, and %s is a place hooks are run out of. From a command "
                    "line it would run on a payload this caller wrote instead, which is how an "
                    "approval nobody gave gets minted (H80 in docs/POST_V2_WISHLIST.md carries "
                    "the chain and what it leaves open)." % _shown(self.root, directory))
        return None, None

    def verdict(self, path):
        """(audience, reason) for a path this call would write or start, or (None, None)."""
        if isinstance(path, Unplaceable):
            return NOWHERE_KNOWN, path.reason
        if isinstance(path, Executed):
            # BEFORE every area below, and that ordering is the answer to "why is `python
            # tools/bump_kit_version.py` still allowed": what a started program WRITES cannot be
            # read off a command line (`_runs_a_program`, H11), so this position is judged on
            # where the file is STARTED FROM and on nothing else.
            return self.hand_driven(path)
        if under(path, self.staging):
            return None, None
        reach = reaches(path, self.state_root)
        if reach is not None:
            return EVERYONE, _worded(reach, (
                "this is canonical project state. It has exactly one writer, the kernel "
                "(`PYTHONPATH=team-kits python -B -m kernel.cli --root %s <command>`), and gate 3 "
                "certifies a commit against Evidence items that live HERE -- so a tool write into "
                "this tree writes the very record that is supposed to judge it. Proposals that "
                "are not state yet go to %s/%s/<item-id>/."
                % (STATE_ROOT, STATE_ROOT, STAGING)))
        reach = reaches(path, self.provider_tree)
        if reach is not None:
            return SESSION_ONLY, _worded(reach, (
                "this is the enforcement layer of this repo -- the hooks, the file that registers "
                "them, the definitions of the roles they read and the permission overlay the "
                "provider merges. A session does not change the rules it is running under, so "
                "there is no tool call that edits them. The consequence is deliberate: a hook "
                "that is broken is NOT repairable from inside this session."))
        for name in sorted(self.producer_files):
            reach = reaches(path, name)
            if reach is not None:
                return SESSION_ONLY, _worded(reach, (
                    "this file is where the protected area itself comes from -- gate 1 derives "
                    "what it protects by executing it. Rewriting it switches the protection off "
                    "without touching a single protected path, which is what makes it part of "
                    "the enforcement layer rather than of the toolchain."))
        reach = goes_into_a_kit_version(path, self.kit_directories)
        if reach is not None:
            return SESSION_ONLY, _worded(reach, (
                "this path goes into a kit's content hash -- it is versioned product, and the "
                "protected area is read from `tools/bump_kit_version.py` plus "
                "`kernel.hashing.kit_hash_inputs`, not from a list kept here."))
        return None, None


# What a refusal has to say FIRST when the candidate is not the protected thing but something that
# holds it. Without it the reason described the area and claimed it OF the candidate, and a bare
# drive letter was told it was canonical project state (measured 2026-08-05: `cp -r docs C:/`).
CONTAINS_NOTE = (
    "this path is refused for what stands UNDER it, not for what it is: it CONTAINS the area "
    "described below, and a command that writes a directory writes what is in it. This gate "
    "cannot tell a copy of a tree from a write into it, so it refuses the wider path -- an "
    "over-refusal by construction, carried with its measured chain as H19 in "
    "docs/POST_V2_WISHLIST.md. What it contains:\n")


def _worded(reach, reason):
    """The reason, prefixed when the candidate merely CONTAINS the area (see `reaches`)."""
    return reason if reach == INSIDE else CONTAINS_NOTE + reason


def _shown(root, path):
    """`path` as a reader of this repo would name it -- relative to the root where that is possible.

    A refusal that spells the checkout's absolute path says nothing the reader did not already
    know and hides the part that identifies the area.
    """
    try:
        return os.path.relpath(path, root).replace("\\", "/")
    except ValueError:  # pragma: no cover -- a different drive; then the absolute path IS the name
        return path


def goes_into_a_kit_version(path, directories):
    """How this path reaches a kit's content hash, or None (see `kit_version_directories`)."""
    for directory in directories:
        reach = reaches(path, directory)
        if reach is not None:
            return reach
    return None


# -- what a command line would write ------------------------------------------
#
# WHY THIS EXISTS AT ALL. Until 2026-08-05 gate 1 sat on the write TOOLS only, and the shell was
# gated by gate 3 alone -- which asks about `git commit` and nothing else. Measured, all rc 0:
# `python -c "open('team-kits/dev-team/hooks/gate_git.py','w')..."`, the same for
# `team-kits/kernel/state.py`, `.claude/hooks/gate_todo_items.py`, `.claude/settings.json` and
# `tools/bump_kit_version.py`, plus `sed -i` on a kit hook and PowerShell `Set-Content` on a gate.
# Together with the import defect above, two tool calls switched all four gates off.
#
# WHAT IS BORROWED. The READING of the command line is the kits' `gate_write_scope`, imported as a
# module and used through its own helpers -- not copied. A second tokeniser, a second redirect
# shape and a second read-only classification are exactly the drift this repo keeps paying for,
# and that gate's own docstring records three rewrites of the same rule. If one of those helpers
# is renamed, the import or the attribute access raises and `guarded()` turns it into a refusal;
# it cannot degrade into a silent allow.
#
# WHAT IS NOT BORROWED. WHICH paths are protected: the kits ask a regex about `.claude` and
# `project_memory`, this gate asks `ProtectedArea`, which is derived. And the kits' rule -- "a
# write-capable pipeline that NAMES the tree" -- cannot be used here at all: in a scaffolded
# project nobody legitimately names `team-kits` in a writing pipeline, while in THIS repo the
# documented commands do it constantly (`PYTHONPATH=team-kits python -B -m kernel.cli --root
# project_memory ...`, `python -B -m pytest .claude/hooks/test_gates.py -q`,
# `python tools/bump_kit_version.py`). A gate that refuses the session's own documented commands
# is not a stricter gate, it is a broken one.

# Every substring of a word that could be a path. Deliberately generous: the point is to find a
# protected path INSIDE an opaque argument (`open('team-kits/x.py','w')`), and a candidate that is
# not a path resolves to something nothing protects, which costs nothing.
_PATHISH = re.compile(r"[A-Za-z0-9_.\-/\\:~]+")
# The character a shell expands a word by, and what ends the prefix it expands (`_tilde_prefix`).
_TILDE = "~"
_PATH_SEPARATORS = "/\\"
# The OTHER characters that make a shell hand a program a word this line does not state: the
# introducer of a parameter or command expansion, the three pathname-matching characters, and the
# opener of a brace expansion. An enumeration, unavoidably -- nothing this file reads derives a
# shell's word grammar -- so it carries a tripwire measuring BOTH ends
# (`test_gates.UNRESOLVED_WORDS`): a real shell has to hand back something other than the literal
# word for each of them, and the gate has to refuse each of them. Quoting is deliberately NOT read
# here, unlike for the tilde: the four constructions are suppressed by different quotings (`$`
# expands inside double quotes, the others do not), and one reader that got that wrong in either
# direction is worse than a refusal too many -- H80 in `docs/POST_V2_WISHLIST.md` carries what it
# costs, and H33 the same answer for the tilde.
_UNRESOLVED = "$*?[{"
# The flag that turns an interpreter's argument from a program to RUN into a program to BE.
_INLINE_PROGRAM_FLAG = "c"
# ...and the flag that makes it run a program the IMPORT SYSTEM finds instead of one this command
# line names. Both mean the same thing for `_executed_words`: no word of this stage is a file the
# interpreter starts, so no word of it is judged in that position -- which is what keeps this
# repo's own documented lines runnable (`python -B -m pytest .claude/hooks/test_gates.py -q`,
# `PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory <command>`, both measured
# rc 0 in the round that added the position). What it costs is named rather than implied: a module
# that takes a path and runs it (`-m runpy <hook>`) starts a hook this reader then does not see,
# and so does any script the caller wrote first -- the same boundary `_runs_a_program` carries,
# H11 in `docs/POST_V2_WISHLIST.md`. That the daily lines really survive is held to
# `test_gate1_leaves_a_file_outside_the_hook_directories_startable` rather than to this sentence.
_MODULE_FLAG = "m"
# The keyword form of a function declaration. A word of the shell's own grammar rather than a
# spelling somebody happens to use -- `_declares_a_function` reads both forms the grammar has.
_FUNCTION_KEYWORD = "function"
# The shell's word for "the directory I came from". It is an OPERAND, not a flag, which is the
# whole reason `_destination_word` cannot filter every word that starts with a dash.
_PREVIOUS_DIRECTORY = "-"
# The answer of `_destination_word` when the operand list is one it cannot account for. It is a
# value of its own and not None, because None is a destination too (a bare `cd` goes home) -- and a
# reader that answered "no operand" here walked into the home directory on a line the shell
# refuses to run at all, which is the shape DEC-0014 records as the proof that the axes of a test
# table have to be derived from what the code claims.
_UNACCOUNTABLE = ("an operand list this reader cannot account for",)
# POSIX Utility Syntax Guideline 10: this word ends the options and everything behind it is an
# operand, whatever it starts with. A definition of the shell's grammar rather than a flag of any
# one builtin -- which is why `cd -- <target>` can be accounted for while `cd -L <target>` cannot
# (H29 in `docs/POST_V2_WISHLIST.md` carries what is left of that entry).
_END_OF_OPTIONS = "--"
# The position of a shell that ran a directory verb this reader could not follow. It is neither a
# directory nor None: None is a position too (a base that is None used to DROP every relative word,
# which turns a doubt into a pass), and from here every relative word is refused instead -- see
# `WorkingDirectory.follow` for which moves reach it and for the measurement that widened them from
# `popd` to every move whose effect this reader cannot compute.
_UNKNOWN_POSITION = ("a position this reader could not follow",)
# What a directory verb does to the shell's position. The ROLE is one question; WHICH WORD IS A VERB
# AT ALL is a second one, and it belongs to the shell that runs the line -- see `_directory_role`.
_ENTER, _PUSH, _POP = "enter", "push", "pop"
# The verbs a POSIX shell runs itself, and the two facts that go with the shell rather than with the
# word: whether it compares command names case-insensitively, and what else it calls a directory
# verb. PowerShell's set is the POSIX one plus its own cmdlet, because `cd`/`pushd`/`popd` are
# aliases there; its cmdlet spellings `Push-Location`/`Pop-Location` are in NEITHER set, and that
# gap is named as H21 in `docs/POST_V2_WISHLIST.md` rather than closed here, because the repair
# belongs in the kit -- a second vocabulary in this file is the drift H15 describes.
_POSIX_VERBS = {"cd": _ENTER, "pushd": _PUSH, "popd": _POP}
# ...and the third fact that goes with the shell: what it reads as a COMMAND SUBSTITUTION, i.e. the
# pair that opens a command line inside a word and puts its output back in the word's place. An
# enumeration of spellings, unavoidably -- no reader this file borrows from has one, so there is
# nothing to derive it from -- and it therefore carries a tripwire that measures BOTH ends: every
# pair is a cell of the crossed table `test_gates.LINE_SHAPES`, and that cell asserts that a real
# shell REALLY runs the substitution (`test_the_shell_writes_where_the_table_of_line_shapes_says` --
# a dead entry says so) and that the gate refuses the write inside it
# (`test_gate1_refuses_a_line_exactly_where_the_shell_would_write` -- a missing entry says so).
_SUBSTITUTIONS = (("$(", ")"), ("`", "`"))
SHELLS = {
    "Bash": {"folds_case": False, "verbs": _POSIX_VERBS, "substitutions": _SUBSTITUTIONS},
    "PowerShell": {"folds_case": True, "verbs": dict(_POSIX_VERBS, **{"set-location": _ENTER}),
                   # a backtick is PowerShell's ESCAPE character and opens nothing; `@(` is its
                   # array subexpression, which runs its content exactly as `$(` does
                   "substitutions": (("$(", ")"), ("@(", ")"))},
}
# The characters a shell reads as SYNTAX rather than as part of a word: the tokeniser's own set
# (`shlex(punctuation_chars=True)`, which is what the kits' `_lex` uses) plus the brace group, which
# shlex hands back as an ordinary word while the shell groups with it. Used to decide whether a word
# stands in FRONT of the command name -- see `_is_the_command_name`.
_SYNTAX_CHARACTERS = frozenset(shlex.shlex("", punctuation_chars=True).punctuation_chars) | set("{}")


def shell_reader(data):
    """The kits' `gate_write_scope`, as a module -- the reading of a command line, once."""
    _add_kit_paths(repo_root(data))
    return _from_kit("gate_write_scope")


def _runs_a_program(verb):
    """Does this stage EXECUTE its operands rather than modify them?

    The distinction the shell half turns on, and the one the kits' `_stage_is_read_only` already
    makes for the same verb: `python <path>` and `python -m pytest <path>` hand a path to an
    interpreter as CODE or as INPUT, `cp <path> x` and `Set-Content -Path <path>` act on it. A
    command line does not say which of the two an arbitrary program does, so this answers for the
    one family this repo actually runs -- CLAUDE.md spells every command of this project as
    `python ...` -- and everything else falls into the writing half, i.e. into a refusal that a
    user can report.

    WHAT THIS COSTS, and it is the largest hole in the shell half: an interpreter runs code the
    gate cannot read. `python <script-in-a-free-area>` writes anything the script writes, and a
    conftest under `pytest` does too. That is the kits' boundary as well (`gate_write_scope`:
    "It does NOT refuse a script the agent wrote to an ordinary path and then ran"), it is not
    closable from a command line, and what bounds it is the permission posture rather than a
    bigger vocabulary. `docs/POST_V2_WISHLIST.md` H11 carries it with a measured chain.
    """
    return verb.startswith("python") or verb in ("py", "pythonw")


def _carries_flag(token, letter):
    """Is this token a short-flag cluster carrying `letter` (`python -Bc "..."`)?

    The token's own text is enough here and no reading loop is needed: `_tokenise` is
    `_compat.shell_words`, which already hands back the RESOLVED word, so `python "-c" "..."` and
    `python -''c "..."` arrive as the token `-c`. Measured, not assumed -- an earlier cut of this
    function scanned every reading for that case, and the mutation that removed it stayed green,
    which is the sign that the code was answering a question something else had already answered.
    """
    text = str(token)
    return (text.startswith("-") and not text.startswith("--")
            and letter in text[1:].lower())


def _flag_words(stage, letter):
    """Every token of a stage carrying short flag `letter`, plus the token behind each.

    Both tokens are taken, because the value can be glued to the flag or stand beside it.
    """
    words = []
    for index, token in enumerate(stage):
        if not _carries_flag(token, letter):
            continue
        words.append(token)
        if index + 1 < len(stage):
            words.append(stage[index + 1])
    return words


def _inline_program_words(stage):
    """The tokens of an interpreter stage that are a PROGRAM rather than a path to one."""
    return _flag_words(stage, _INLINE_PROGRAM_FLAG)


def _resolves_the_verb_at_runtime(tool, token):
    """Does a COMMAND SUBSTITUTION stand where the program name goes?

    Then what this stage starts is whatever the substitution prints, and no reader of the command
    line can say whether that is an interpreter -- so its operands stand in the START position.
    Measured 2026-08-31: `$(which python) <hook>` came out rc 0 for a subagent while
    `python <hook>` was rc 2; the outer pipeline keeps the substitution's own tokens, so its verb
    reads as the opener and the file behind it stood in no position at all.

    ABLATED ONCE AND BROUGHT BACK, which is the more useful half of this docstring. While
    `_unresolved_at` still answered for a bare `$`, this branch changed no verdict anywhere in the
    round's battery and was removed as unreachable. It became reachable again the moment that
    reader stopped answering for one-character words -- `$(printf 'pyt'; printf 'hon') <hook>` cuts
    at the `;`, so the hook stands behind a stage whose verb is `printf`, which the kits classify as
    a read. The lesson is not about substitutions: a branch is unreachable only against the reader
    standing beside it, and both have to be measured again when either moves.
    """
    text = str(token)
    return bool(text) and any(opener.startswith(text)
                              for opener, _closer in _substitution_pairs(tool))


def _after_an_unopened_closer(tool, body):
    """Where the OUTER stage's words resume, when this body ends a substitution it never opened.

    A SUBSTITUTION WITH A `;` IN IT IS CUT WHERE THE SHELL CUTS IT, and the last piece then carries
    the closer plus everything the outer stage wrote behind it -- with the INNER command's verb in
    front. Measured 2026-08-31: `$(printf 'pyt'; printf 'hon') <hook>` arrives here as
    `['printf', 'hon', ')', '<hook>']`, verb `printf`, which the kits classify as a read, so the
    hook stood in no position at all while bash started it. What follows an unopened closer belongs
    to a command whose name this reader never saw, so it is judged like any other unknown program's
    operand list.

    The openers are matched by PREFIX because the tokeniser splits `$(` into `$` and `(`, which is
    the same reading `_resolves_the_verb_at_runtime` uses.

    A CLOSER WITH NOTHING BEHIND IT IS NOT THIS SHAPE, and saying so is not tidiness: the last
    pipeline of a SUBSHELL ends in exactly such a token (`(cd <hooks> && python gate_approval.py)`
    arrives as `['python', 'gate_approval.py', ')']`), and answering for it handed the caller an
    empty operand list -- so the hook standing right there was judged in no position at all.
    Measured 2026-08-31: rc 0 in all four combinations while the flat spelling was rc 2.
    """
    pairs = _substitution_pairs(tool)
    openers = {opener for opener, _closer in pairs}
    closers = {closer for _opener, closer in pairs}
    opened = False
    for index, token in enumerate(body):
        text = str(token)
        if text and any(opener.startswith(text) for opener in openers):
            opened = True
        elif text in closers and not opened and index + 1 < len(body):
            return index + 1
    return None


def _executed_words(module, tool, body, verb):
    """The tokens of a stage that could name a file it STARTS.

    THREE POSITIONS, because a shell starts a program in three ways, and each of the last two was
    measured as a way past the first:
      * the stage's own VERB -- `./.claude/hooks/gate_approval.py` needs no interpreter in front
        of it, and `_verb_as_a_file` says when a verb names a file at all;
      * the OPERANDS of an interpreter, whether it is the verb, or a WRAPPER starts it
        (`timeout`, `nohup`, `stdbuf`), or another shell is handed it as a line of its own
        (`bash -lc "python <hook>"`) -- `_command_positions` carries which stages that reaches and
        why a read is not one of them;
      * every operand of a stage whose verb this reader cannot name as a program at all, which is
        the fail-closed remainder and the branch below.

    A FOURTH STOOD HERE FOR ONE ROUND -- the operands of a stage whose verb is a command
    SUBSTITUTION -- and it was ablated on 2026-08-31 without a single verdict changing across the
    round's whole measured battery in both shells: such a verb is never read-only and never an
    interpreter, so the remainder answers it, and in bash the substitution's own token is a word
    `_UNRESOLVED` already refuses. A branch no measurement can reach is a claim, not a wall.

    EVERY OPERAND, not the first one, and that direction is the one this file already takes for a
    stage it cannot classify (`written_paths` hands the WHOLE body to the area when the verb is not
    read-only). An interpreter's grammar has flags that take a value of their own
    (`python -W ignore <file>`), so "the first word that is not a flag" is the script for some
    lines and the value of a flag for others -- and reading it that way stops at the value and
    never sees the file behind it. Over-inclusion costs a refusal for a path handed to a script as
    an ARGUMENT; under-inclusion costs the wall.

    A stage that runs a MODULE or an inline program of its own names no file to start, so it has
    no operand in this position -- see `_MODULE_FLAG`, which carries what that leaves open.
    """
    at = _verb_position(module, body, verb)
    if at is None:
        return [], []
    words = _verb_as_a_file(body[at])
    if _resolves_the_verb_at_runtime(tool, body[at]):
        return words + _operands(body[at + 1:]), []
    resumes = _after_an_unopened_closer(tool, body)
    if resumes is not None:
        return words + _operands(body[resumes:]), []
    positions = _command_positions(module, body, verb, at)
    if not positions and not module._stage_is_read_only(body):
        # THE VERB IS A PROGRAM THIS READER CANNOT NAME, and the stage is not one it can call a
        # read either -- so what the operands are FOR is unknown, and "an argument" is only one of
        # the answers. Measured 2026-08-31 with a real PowerShell as arbiter: `& ('pyt'+'hon')
        # <hook>` really starts the hook (the call operator with a parenthesised expression), the
        # verb came out as `pyt+hon`, no word of the stage was an interpreter, and the line was
        # rc 0 for a subagent. The same branch takes the relocation with it: `cp -r <hooks> copy`
        # is a stage of this kind, and its operands are now judged in the start position for every
        # caller. What it costs is that no shell line maintains a hook file any more -- a copy, a
        # move, a removal or an in-place edit of one is refused to everyone, which is the rule the
        # kits state for their own layer and the door the Write and Edit tools keep open.
        #
        # THE SECOND LIST, AND WHY IT IS A SECOND ONE: these words stand where a program COULD be,
        # not where one demonstrably is, so a word among them that only a shell can resolve is not
        # by itself a subject -- `[ $i -ge 3 ]` is a stage of exactly this kind, and reading `$i`
        # as an unplaceable start refused every polling loop this repo measures with (measured
        # 2026-08-31, rc 2 on the round's own wait line). `_could_name_a_path` is where that split
        # is made.
        return words, _operands(body[at + 1:])
    for index in sorted(positions):
        rest = body[index + 1:]
        options = _option_part(rest)
        if _flag_words(options, _MODULE_FLAG) or _flag_words(options, _INLINE_PROGRAM_FLAG):
            continue
        started = _operands(rest)
        if not started and index != at:
            words.append(Unplaceable(str(body[index]), _handed_a_program_from_elsewhere()))
            continue
        words += started
    return words, []


def _handed_a_program_from_elsewhere():
    """Why an interpreter a WRAPPER starts with no program is a start this reader cannot place.

    IT WILL RUN SOMETHING, and the line does not say what: another program turns data into its
    argument list. Measured 2026-08-31 with a real shell against a real kernel:
    `echo <hook> > list.txt; xargs -a list.txt python < forged.json` minted `APR-0001` and left the
    item `APPROVED`, while neither `python` nor any word beside it named the hook.

    ONLY WHERE THE INTERPRETER IS NOT THE STAGE'S OWN VERB, and that boundary is the mechanism
    rather than a concession to convenience: an interpreter standing first with no operand reads
    its PROGRAM from standard input, which spends the one channel the hook needs for its payload --
    measured, `cat <hook> | python < forged.json` cannot have both and mints nothing. A wrapper is
    the shape that leaves stdin free, and it is the one refused here. So `python - <<'PY'`, the
    form this repo works in, stays rc 0.
    """
    return ("a program starts this interpreter WITHOUT naming a program for it, so what it runs "
            "comes from a channel this line does not carry -- a file another program turns into "
            "its argument list. A reader of command lines cannot follow that, and what it can "
            "then start includes the enforcement layer: measured, `xargs -a <list> python` with a "
            "forged payload on standard input minted an approval nobody gave.\n"
            "Remedy: name the program on the line (`python <path>`), or run it from a script and "
            "report that -- this gate reads a command line and says so.")


def _program_name(token):
    """The word a shell would compare against a program name -- the kits' reading of a verb."""
    return os.path.basename(str(token).lower().replace("\\", "/"))


def _verb_as_a_file(token):
    """The stage's verb, but only when it names a FILE this line places.

    A SEPARATORLESS VERB IS RESOLVED OVER `PATH`, NEVER AGAINST THE WORKING DIRECTORY, and reading
    it as a file in the current directory is not a stricter answer, it is a wrong one: measured
    2026-08-31, from inside a hooks directory EVERY command came out rc 2 -- `cat`, `ls`, `grep` --
    and the refusal called `grep` enforcement code. `./x.py` and `dir/x.py` are the shapes that DO
    name a file, and the shell tells them apart by exactly this character.
    """
    text = str(token)
    return [token] if any(separator in text for separator in _PATH_SEPARATORS) else []


def _option_part(words):
    """The words a program reads as OPTIONS: everything up to its first operand.

    THE QUESTION "does this stage run a module instead of a file" IS ABOUT THE INTERPRETER'S OWN
    OPTIONS, and asking it of every word behind the interpreter answers it with the SCRIPT's
    arguments too. Measured 2026-08-31: `python <hook> -c` was rc 0, and so were `-m`, `-abc` and
    `-M`, while the control `-x` was rc 2 -- a single option-looking word behind the script deleted
    the operand scan, and the hook does not read `sys.argv`, so the extra word cost the caller
    nothing. The chain ran to `APPROVED` again.

    WHERE THIS ERRS is the safe direction and it is named: a flag that takes a value of its own
    (`python -W ignore -m pytest x`) ends the option part at the VALUE, so a `-m` behind it is not
    seen and the operands are scanned -- a refusal too many, never one too few.
    """
    out = []
    for token in words:
        if not str(token).startswith("-"):
            return out
        out.append(token)
    return out


def _command_positions(module, body, verb, at):
    """Every position of this stage at which a program name this reader KNOWS stands.

    TWO: the verb itself when it is an interpreter, and an interpreter ANYWHERE in a stage whose
    verb this reader can classify as neither read-only nor an interpreter -- a wrapper, or another
    shell handed a line of its own, whose words the kits' tokeniser gives back as ordinary words of
    this stage. Measured 2026-08-31, each rc 0 for a subagent before this: `timeout 60 python
    <hook>`, `nohup python <hook>`, `stdbuf -o0 python <hook>`, `bash -lc "python <hook>"`.

    THE READ-ONLY CONDITION IS WHAT KEEPS A READ FREE. `grep -rn python .claude/hooks/` carries the
    word `python` in an operand and stays rc 0 because the kits classify `grep` as read-only -- not
    because the word stands in a particular place. A THIRD condition stood here for exactly one
    round, taking the position behind an inline-program flag whatever the verb; the mutation run
    that removed it changed no verdict, because every stage it could fire on that really runs
    something is already a wrapper -- and on a read-only verb it produced refusals of reads
    (`grep -c python <hook>`) and nothing else. A verb this reader cannot classify at all is not
    read-only, so it lands here, which is the fail-closed direction.
    """
    out = set()
    if _runs_a_program(verb):
        out.add(at)
    elif not module._stage_is_read_only(body):
        for position in range(at + 1, len(body)):
            if _runs_a_program(_program_name(body[position])):
                out.add(position)
    return out


def _operands(words):
    """The words of a stage that are not flags -- what a program is given rather than told."""
    return [token for token in words if not str(token).startswith("-")]


def _declares_a_function(module, head):
    """Is `head` the head of a function DECLARATION -- the thing a `{` behind it opens a body of?

    THE GRAMMAR HAS TWO FORMS AND THIS ASKS FOR EXACTLY THEM: a name followed by an empty parameter
    list (`dec () { ... }`), and the keyword form (`function dec { ... }`, with an optional `()`).
    What stood here asked whether a `(` appeared ANYWHERE in the head, which is a different
    question and answers yes for heads that declare nothing -- measured 2026-08-05, `sed -i ...
    <kit file> $(true) {` and `arr=(a b) sed -i ... <kit file> {` each had the write in front of
    the brace cut away and came out rc 0.

    The parameter list is read through `_operator`, so a QUOTED bracket is not one: `dec '(' ')' {`
    runs a command and declares nothing, and its operands stay operands.
    """
    words = list(head)
    if words and module._operator(words[0]).lower() == _FUNCTION_KEYWORD:
        words = words[1:]
        if len(words) == 1:
            return True
    return len(words) > 1 and "".join(module._operator(t) for t in words[1:]) == "()"


def stage_body(module, stage):
    """The tokens of a stage that a shell RUNS, without the header that only declares a name.

    `_stage_verb` reads a declared NAME as the verb, and a verb nothing recognises is not
    read-only -- so every word of the body became a write candidate and this repo's own documented
    kernel prefix was refused the moment it was wrapped in a function (BUG-0012, measured rc 2
    against rc 0 for the same line unwrapped).

    WHAT STANDS IN FRONT OF A BRACE THAT DECLARES NOTHING KEEPS ITS CANDIDATES: `sed -i s/a/b/
    <kit file> {` has a brace token too, and cutting at it loses the write in front of it.
    `_declares_a_function` is the whole of that distinction.

    A BRACE GROUP WITHOUT A HEAD (`{ ... ; }`) IS NOT CUT AND NEEDS NO CUTTING -- an exception that
    stood here and decided nothing: `_stage_verb` skips the brace already, and a brace names no
    path. Ablated 2026-08-05 through the real gate process, no answer changed, so it is gone rather
    than kept as a branch no measurement can reach.
    """
    for index, token in enumerate(stage):
        if module._operator(token) != "{":
            continue
        if _declares_a_function(module, stage[:index]):
            return stage[index + 1:]
        return stage
    return stage


class Unplaceable(str):
    """A word a line would write, and that nothing on this line says where it lands.

    NOT A PATH, AND THAT IS THE POINT: a word this reader cannot place can name any file on the
    host, canonical state included, so there is nothing to compare against an area and nothing that
    may be allowed. `ProtectedArea.verdict` answers it for EVERYONE, in the same place where every
    other subject is judged, so the answer cannot be forgotten by a caller.

    IT CARRIES ITS OWN REASON, because there is more than one way to be one and they are different
    questions -- a position `WorkingDirectory` could not follow, and a tilde prefix only the shell
    can resolve (`_candidates`). A single reason would have named the wrong cause for one of them,
    which is the kind of sentence this repo counts as a defect of its own.
    """

    def __new__(cls, word, reason):
        self = str.__new__(cls, word)
        self.reason = reason
        return self


class Executed(str):
    """A path an interpreter stage would START, rather than one it would change.

    A SUBJECT OF ITS OWN, and not a written path with a different name, because it is judged
    against a different area and for a different reason. What a program WRITES is unreadable from a
    command line (`_runs_a_program` carries that boundary and H11 its chain), so a path in this
    position is not refused for being protected: `python tools/bump_kit_version.py` and
    `python tools/validate.py` are how this repo is delivered. What IS refused is starting a file
    out of the enforcement layer, and `ProtectedArea.verdict` decides that -- here there is only
    the position.
    """


def _lost_the_position(why):
    """Why a relative word written from a position this reader gave up is one it cannot place."""
    return ("this word is spelled relative to a position this reader could not follow. `%s` "
            "moved the shell somewhere this gate cannot compute, and STAYING where it stood is "
            "not the careful answer for a move whose direction is unknown -- it may be the one "
            "that goes back INTO a protected tree. From an unknown position a relative word "
            "can name any file on this host, canonical project state included." % (why,))


def _cannot_resolve_the_word(character, reading):
    """Why a word carrying a construction only a shell can resolve is one this reader cannot place.

    THE SAME ANSWER AS THE TILDE'S AND FOR THE SAME REASON (`_cannot_expand_the_tilde`, DEC-0020):
    the shell builds the word out of state or out of the filesystem, this reader holds neither, and
    what the word can then name includes every protected path. It was measured as a hole in BOTH
    directions on 2026-08-31 -- the START position (`python "$PWD/<hook>"` and
    `python te*m-kits/.../gate_approval.py`, each rc 0 and each run to an approval nobody gave) and
    the WRITE position, where it had been open since the shell half was built
    (`sed -i "s/a/b/" "$PWD/team-kits/kernel/state.py"` rc 0 against rc 2 for the relative spelling).
    """
    return ("this word carries `%s`, and what stands from there on is built by the SHELL: out of "
            "its own state (a parameter or command expansion) or out of the filesystem (a pathname "
            "or brace expansion). This reader holds neither, so the word it will really hand to "
            "the program is one nothing on this line states -- and what it can name includes "
            "canonical project state and the enforcement layer. The whole reading was %r."
            % (character, reading))


def _unresolved_at(text):
    """Where a construction only a shell can resolve begins in `text`, or None (see `_UNRESOLVED`).

    WHICH WORDS THIS IS ASKED OF is decided by the caller and not here, and that is the whole
    reason this stayed usable: `_candidates` asks it of a word that could name a PATH (it carries a
    separator) and of one standing where a PROGRAM is started, and of nothing else. A shell
    variable used as DATA (`[ $i -ge 3 ]`, `$((i + 1))`) is then not a subject at all, which is the
    difference between a gate and a lockout -- measured the hard way, the first cut refused this
    round's own polling line.

    A SECOND CONDITION STOOD HERE AND WAS ABLATED: "a word of one character is punctuation, not a
    construction" (`[` as the `test` builtin, `{` as a group). With the caller's question in place
    it changed no verdict anywhere in the round's battery, because a one-character word carries no
    separator and stands in no program position.
    """
    positions = [text.find(character) for character in _UNRESOLVED]
    found = [position for position in positions if position >= 0]
    return min(found) if found else None


def _cannot_expand_the_tilde(prefix):
    """Why a word whose tilde prefix carries anything is one this reader cannot place (DEC-0020)."""
    return ("this word carries the tilde prefix `%s%s`, and a shell resolves a prefix that is not "
            "empty out of state this reader does not hold: where the shell stands, where it came "
            "from, its directory stack, its user database. The library function that expands a "
            "tilde answers a DIFFERENT question and answers it for every prefix -- it turns each "
            "of them into a directory under the home directory, which is a path the shell never "
            "uses and nothing here protects. So the answer is not taken, and what this word names "
            "includes canonical project state." % (_TILDE, prefix))


# The word attribute carrying the spelling a shell EXPANDED: the token as it stood BEFORE the
# quoting was taken out of it, with every balanced span still marked as one. `tokenise` puts it
# there and `readings` decides the tilde question on it -- `_compat.ShellWord` carries the resolved
# text and whether SOME span was spliced into it, which is a different question (see
# `_expands_a_tilde`).
TYPED_READING = "typed_reading"


def tokenise(module, compat_module, text):
    """The kits' own tokens, each carrying the spelling the shell read before it removed quoting.

    BORROWED, NOT COPIED, like every other reading this gate makes of a command line: the
    composition is the kits' `_tokenise` itself (`_compat.shell_words` with that gate's lexer), and
    what is added is the one fact a `ShellWord` does not keep -- WHERE in the word the quoting
    stood. `shell_words` hands its splitter the MASKED text and builds one word per token it gets
    back, in order, so the tokens the splitter saw are exactly the typed readings of the words.
    A renamed helper raises here and `guarded()` turns that into a refusal, never into an allow;
    that the composition is still the kits' own is measured in
    `test_the_words_this_reader_reads_are_the_kits_own_tokens`.
    """
    typed = []

    def split(masked):
        tokens = module._lex(masked)
        typed.extend(tokens)
        return tokens

    words = compat_module.shell_words(text, split)
    for word, token in zip(words, typed):
        setattr(word, TYPED_READING, token)
    return words


def _quoting_in(compat_module, span):
    """Does this span of a TYPED reading carry quoting -- asked with the kits' own reader.

    ONE SPELLING REACHES HERE AND IT IS NOT SPELLED AGAIN: `_compat._MASK_RX` finds where
    `shell_words` masked a balanced span. The shell's OTHER way of keeping a character literal, the
    escape, cannot stand in a span this is ever called with -- `_PATH_SEPARATORS` carries the
    backslash, so `_tilde_prefix` ENDS the prefix at it and hands back what stood in front. A
    condition for it here would be one that cannot fire.

    WHAT THAT COSTS, since a shell reads it differently: to bash `~\\+/x` is a prefix carrying a
    quoted character and therefore literal, to this reader it is the EMPTY prefix, which it expands
    into the home directory. Neither names the other's path, and measured 2026-08-07 through the
    real gate with a real bash as arbiter over the file, no such line reaches the protected file --
    `~\\+`, `~\\0`, `~\\+0`, `\\~+` and `~\\-` after a move, all "shell writes: False". What the
    VERDICT is varies with something else entirely and is not decided here: where the prefix
    character is one `_PATHISH` does not carry, the substring scan leaves the bare home directory as
    a candidate of its own, and in a stand-in project that lives UNDER the home directory that is an
    ancestor of protected state (rc 2 for `~\\+`, rc 0 for `~\\0`). The check set crosses the shape
    for every prefix (`test_gates._quotings`, `with the rest of the tilde prefix escaped`).

    A quote mark that survived UNBALANCED quoting is not a mask either, so this answers "no" for it
    -- the refusing direction, and a line whose quoting does not balance is one no shell runs.
    """
    return bool(compat_module._MASK_RX.search(span))


def _expands_a_tilde(compat_module, typed):
    """Does a shell expand a tilde of the word it read as `typed` -- the spelling BEFORE quoting was
    taken out of it?

    QUOTING SUPPRESSES AN EXPANSION WHERE IT STANDS, NOT WHEREVER IT STANDS IN THE WORD. A shell
    removes quoting character by character and expands the tilde PREFIX -- everything up to the
    first separator (`_tilde_prefix`) -- so only quoting inside that span suppresses anything.
    Asking instead whether the word carried a spliced span ANYWHERE was H33's second half, and it
    let the whole class back in: measured 2026-08-07 through the real gate with a real bash as
    arbiter over the file, `sed -i "s/a/b/" ~+/"team-kits"/kernel/state.py` was rc 0 while bash
    rewrote the protected file, and so were the same shape with the quoting around `kernel`, around
    `state.py`, and pointing at `.claude/settings.json` and `project_memory/`.

    A TILDE THAT DOES NOT START THE WORD IS ANSWERED YES, and that is a direction rather than an
    answer: a shell expands one after the `=` and the `:` of an assignment, and this reader cannot
    see WHERE inside a word a path-like substring stood (`_candidates` scans the resolved reading,
    which no longer says where its quoting was). So it claims no suppression it cannot see, and
    what that costs is over-refusal -- a word whose tilde stands behind quoting, `""~+/x`, is
    refused although a shell keeps it literal (`docs/POST_V2_WISHLIST.md` H33).
    """
    prefix = _tilde_prefix(typed)
    if prefix is None:
        return _TILDE in typed
    return not _quoting_in(compat_module, prefix)


def readings(compat_module, word):
    """`(text, may a tilde in it be expanded)` for every value a shell could hand a program.

    THE SECOND HALF IS AN ORDER THE READINGS THEMSELVES NO LONGER SHOW. A shell EXPANDS a word and
    then removes its quoting; `_compat.shell_readings` hands back the result of the second step, so
    a reader that expands what it gets makes exactly the expansion the quoting was there to
    suppress. Measured 2026-08-07 through the real gate with a real bash as arbiter over the file
    (`docs/POST_V2_WISHLIST.md` H31): `cd "~" ; <relative write>` was rc 0 -- this reader walked
    into the home directory while bash said `~: No such file or directory`, stayed in the tree and
    let the write rewrite the protected file. `'~'`, `\\~` and `"~/"` are the same word, and the
    chain needs no preparation: end to end the same shape emptied `.claude/settings.json`, which is
    the registration of every gate this repo runs.

    SO THE QUESTION IS PUT TO THE SPELLING THE SHELL EXPANDED (`TYPED_READING`, `_expands_a_tilde`)
    and not to the text a program receives. Two things come out of that, and the first was the
    defect the second correction of this line introduced: WHERE the quoting stands decides, so
    quoting anywhere BEHIND the prefix leaves the expansion exactly as it was, and only a prefix
    that itself carries quoting stays literal (H31, H33).

    AND ONLY THE FIRST READING, whatever its text: the further readings are the same word with the
    kits' backslash taken out (`_compat.shell_words`), and a backslash is quoting too -- `\\~/x` is
    a literal `~/x` to a shell. The kits keep the same distinction at the same place and for the
    same reason (`gate_write_scope._operator`: once the marks are gone, `echo '>' file` and
    `echo > file` spell the same three characters and only the second one redirects).

    A WORD THIS READER DID NOT TOKENISE reads its resolved text as its own typed spelling, which is
    the pre-H31 answer for that word. Nothing produces one today -- every word here comes from
    `tokenise` through `command_line` -- and the cell that would notice is `cd to a tilde the
    quoting keeps` in `test_gates.LINE_SHAPES`, which turns from a refusal into an allow the moment
    a word arrives without it.
    """
    out = compat_module.shell_readings(word)
    typed = getattr(word, TYPED_READING, None)
    expands = _expands_a_tilde(compat_module, str(word) if typed is None else typed)
    return [(text, expands and index == 0) for index, text in enumerate(out)]


def _tilde_prefix(text):
    """What stands between a leading `~` and the first path separator -- None without a leading `~`.

    A SPAN, NOT A SET OF SPELLINGS. A shell reads everything from the tilde to the first separator
    as ONE prefix and resolves it out of its own state; the EMPTY prefix is the only one whose
    answer is "the home directory", which is also the only question the library expansion below
    answers. Anything else is a question this reader cannot put to anybody.
    """
    if not text.startswith(_TILDE):
        return None
    cut = next((index for index, character in enumerate(text)
                if character in _PATH_SEPARATORS), len(text))
    return text[len(_TILDE):cut]


def _expanded(text, expandable):
    """`text` with the expansions a shell makes on a word it may expand (see `readings`) -- or None
    where the expansion is one this reader cannot make.

    A DELEGATED ANSWER COUNTS ONLY AS FAR AS IT AGREES WITH THE SUBJECT'S (DEC-0020). The expansion
    of a tilde is delegated, and the delegate answers "the home directory of a user" while the shell
    answers "the directory this prefix names", which is the same thing for exactly one prefix -- the
    empty one. For every other prefix the delegate does not decline: it hands back an absolute path
    under the home directory, which nothing protects, while the shell names its own working
    directory or an entry of its stack. `docs/POST_V2_WISHLIST.md` H33 carries the measured chain.

    So the error direction is turned round: where the delegate would answer a question that was not
    asked, this returns None, and the caller makes the word an `Unplaceable` -- refused for
    everyone. What that costs is over-refusal on every word whose prefix a shell CAN resolve and
    this reader will not (a login name is the one a POSIX host meets first); the same entry carries
    it.
    """
    if not expandable:
        return text
    if _tilde_prefix(text):
        return None
    return os.path.expanduser(text)


def _could_name_a_path(reading, starts):
    """Is this word one whose SHELL-BUILT value could be a path at all? (see `_unresolved_at`)

    TWO WAYS TO BE ONE, and the second is the position rather than the text: a word carrying a path
    separator is being spelled as a path, and a word standing where a program is STARTED is a path
    whatever it looks like (`H=<hook>; python $H` -- one variable, no separator, and it started the
    hook). Everything else is data as far as this reader can tell, and refusing data is how a gate
    becomes a lockout: `[ $i -ge 3 ]` and `$((i + 1))` carry an expansion and name nothing.
    """
    return starts or any(separator in str(reading) for separator in _PATH_SEPARATORS)


def _candidates(compat_module, word, position, starts=False):
    """Every path a word could name, resolved against where the line stands.

    EVERY READING of the word (`readings`: `'.cl'aude/hooks/x` and `.claude/hooks/x` are one file
    in a real shell), and then TWO questions per reading, because one of them alone
    misses a case this repo has by construction:

      * the WHOLE reading as a path -- a quoted path may contain a SPACE, and this repo's own
        checkout does (`C:/Offline Repos/AgentAndSkills`). A substring scan splits it at the space
        and neither half names anything, so `sed -i "<repo with a space>/team-kits/..."` came out
        unprotected while the relative spelling was refused;
      * every path-like SUBSTRING -- because the word may be an opaque program text with the path
        buried in it (`open('team-kits/x.py','w')`), where the whole word is no path at all.

    A candidate that names nothing costs nothing: it resolves to a path no area protects.

    THE POSITION IS EITHER A DIRECTORY OR UNKNOWN, and never None. `base = None` used to mean "we
    cannot say where we are", and a relative word was then DROPPED -- the one direction that turns a
    doubt into a pass. Where `WorkingDirectory` cannot follow a move away from here it stays; where
    it cannot follow one BACK it says so, and a relative word from there is an `Unplaceable`.

    AND THE EXPANSION ITSELF CAN BE UNPLACEABLE, which is not a property of the position at all
    (`_expanded`, DEC-0020): a tilde prefix a shell resolves out of its own state names a directory
    nothing on this line says. The two reasons are different sentences, so the word carries the one
    that applies.
    """
    out = []
    for reading, expandable in readings(compat_module, word):
        unresolved = _unresolved_at(str(reading)) if _could_name_a_path(reading, starts) else None
        parts = [(str(reading), 0)] + [(match.group(0), match.start())
                                       for match in _PATHISH.finditer(reading)]
        for found, begins in parts:
            # THE POSITION DECIDES, and it has to: `_PATHISH` carries none of the characters of
            # `_UNRESOLVED`, so the path-like part of `$PWD/team-kits/x` is the SUBSTRING behind the
            # expansion -- and that substring starts with a separator, i.e. it read as an absolute
            # path and landed under nothing. A part that stands in FRONT of the construction is a
            # real prefix of a real path and keeps its answer.
            if unresolved is not None and begins >= unresolved:
                out.append(Unplaceable(reading, _cannot_resolve_the_word(
                    str(reading)[unresolved], str(reading))))
                break
            text = _expanded(found, expandable)
            if text is None:
                out.append(Unplaceable(reading, _cannot_expand_the_tilde(_tilde_prefix(found))))
                break
            if not text:
                continue
            if os.path.isabs(text):
                out.append(text)
            elif position.base is _UNKNOWN_POSITION:
                # once per reading: the substrings of a word this reader cannot place say nothing
                # more than the word does
                out.append(Unplaceable(reading, _lost_the_position(position.why)))
                break
            else:
                out.append(os.path.join(position.base, text))
    return out


# The character that ends a STAGE rather than a command. The words behind it are a command of their
# own with a verb of their own; only their input comes through a channel instead of from a terminal.
_STAGE_CUT = "|"


def _starts_a_stage(text):
    """Does a run of punctuation like this hand the words BEHIND it to a program of their own?

    THE CHARACTERS DECIDE, in the same order as in `_cuts`, because both are answers about the same
    run of punctuation: what ends the whole command is no stage cut, and what is left carrying a
    `|` is a pipe. That covers three spellings this used to miss by comparing the token to `|`
    itself -- the pipe glued to a bracket (`(echo hi)|<write>`, measured 2026-08-05: rc 0 while
    bash rewrote the protected file, because the words behind it stayed with the verb in front),
    the pipe that also carries stderr (`|&`), and the two glued together.
    """
    if ";" in text or "<" in text or ">" in text:
        return False
    if "&&" in text or "||" in text:
        return False
    return _STAGE_CUT in text


def stages(module, pipeline):
    stages, current = [], []
    for token in pipeline:
        if _starts_a_stage(module._operator(token)):
            stages.append(current)
            current = []
        else:
            current.append(token)
    stages.append(current)
    return stages


# What a cut between two commands does to the LIST they stand in. Three answers, because that is
# what the shell does with a finished list: go on with it conditionally, run it, or hand it to a
# child and go on. The third is what makes this more than a set of separators.
_CONTINUES, _ENDS, _ENDS_ASYNC = "continues", "ends", "ends in a child"


def _cuts(text):
    """How this token ends the command in front of it -- or None when it ends none.

    ASKED OF THE CHARACTERS, not of a table of spellings, and that is what makes it answer for a
    RUN. `shlex` returns adjacent punctuation as ONE token, and the shell reads that run as a
    SEQUENCE of operators: measured 2026-08-05 through the real gate, `(echo hi);sed -i <kit file>`
    and `(echo hi)&&sed -i <kit file>` were rc 0 while the same lines with a space in front of the
    separator were rc 2, because `);` and `)&&` matched no separator and the whole rest of the line
    stayed with the verb in front of it. The `&` had the same effect on its own
    (`echo hi & sed -i <kit file>`, rc 0) and cost gate 3 its ordering as well
    (`echo more >> docs/note.md & git commit -m wip`, rc 0).

    THE CHARACTERS DECIDE, and each answer is a property of the alphabet rather than of a case:

      * a `;` is always a list terminator, and it is asked FIRST: no redirection and no conditional
        operator is spelled with one, so a run carrying it ends a command whatever else it carries.
        Measured 2026-08-05, with the redirection asked first instead: `echo hi;>team-kits/<file>`
        came out rc 0 and really truncated the file, because `;>` matched no separator and no
        redirect operator either;
      * a run carrying a REDIRECTION character and no `;` owns its `&` and `|` (`>&`, `&>`, `>|`),
        so it ends no command -- and the kits' reader is what reads it, which is where redirects
        belong;
      * a doubled `&` or `|` is the conditional operator;
      * a run that still carries a `|` is a PIPE and ends no command -- it ends a STAGE, which is
        `_starts_a_stage`, and it is asked BEFORE the `&` below so that `|&` (the pipe that also
        carries stderr) is read as the pipe it is. Read as an asynchronous terminator instead, it
        moved the base on the command behind it: measured 2026-08-05, `echo hi |& cd <outside> ;
        <relative write>` came out rc 0 while bash kept its position -- `cd` in a pipeline runs in
        a child -- and rewrote the protected file;
      * a single `&` is the asynchronous terminator.

    `commands()` states what a spelling this cannot place AT ALL costs, and checks the kits' own
    separator tuple against it.
    """
    if ";" in text:
        return _ENDS
    if "<" in text or ">" in text:
        return None
    if "&&" in text or "||" in text:
        return _CONTINUES
    if _STAGE_CUT in text:
        return None
    if "&" in text:
        return _ENDS_ASYNC
    return None


def _placed_by_this_reader(text):
    """Do the words behind a token like this get a verb of their OWN in this reading?

    The property `commands()` needs of a separator, and it is wider than "this reader cuts the
    command list here": a stage cut ends no command and still hides nothing, because
    `written_paths` walks every stage with its own verb.
    """
    return _cuts(text) is not None or _starts_a_stage(text)


def commands(module, tokens):
    """Every pipeline of a command line, in the order the shell reaches them, with two facts.

    BOTH FACTS ARE ABOUT THE LIST A PIPELINE STANDS IN rather than about its own words, and neither
    is readable from the pipeline alone -- which is why this walks the token stream once instead of
    asking a question per pipeline:

      * the group depth its first token stands at, because a group opens in one pipeline and closes
        in another (`( true ; cd <elsewhere> )`);
      * whether the shell runs its list in a child, because the `&` that decides it stands behind
        the LAST pipeline of the list (`cd <elsewhere> && true &`) and applies to all of them.

    WHERE THE CUTS ARE IS `_cuts`, and what it cannot place stays inside the command in front of it
    -- one command too few, so the words behind it are judged with the verb in front of them. That
    direction is not safe by itself, which is why the kits' own separators are checked against it
    here: a separator they gain and this reader cannot place raises, and `guarded()` turns that
    into a refusal rather than into a line read as one command.

    THE TRIPWIRE ASKS FOR THAT CONSEQUENCE AND NOT FOR THE CUT, because they are not the same
    question: a `|` ends no command here and the words behind it still get a verb of their own,
    since `stages()` places it. Asking `_cuts` alone therefore refused a separator this reader
    reads perfectly well -- and what such a refusal costs is every line, this repo's own kernel
    call included, measured with the tuple extended in a clone
    (`docs/reviews/2026-08-05-tsk0015-measurements.md`, section 4). `_placed_by_this_reader` is the
    predicate the claim above is made of.
    """
    unplaceable = [text for text in module._PIPELINE_SEPARATORS if not _placed_by_this_reader(text)]
    if unplaceable:
        raise LookupError(
            "the kits' shell reader separates commands at %s, and this reader cannot place %s: it "
            "would read what follows as part of the command in front of it."
            % (", ".join(map(repr, module._PIPELINE_SEPARATORS)), ", ".join(map(repr,
                                                                                unplaceable))))
    out, listed, current, depth, start = [], [], [], 0, 0
    for token in tokens:
        text = module._operator(token)
        depth += text.count("(") - text.count(")")
        cut = _cuts(text)
        if cut is None:
            current.append(token)
            continue
        listed.append((current, start))
        current, start = [], depth
        if cut != _CONTINUES:
            out.extend((pipeline, at, cut == _ENDS_ASYNC) for pipeline, at in listed)
            listed = []
    listed.append((current, start))
    out.extend((pipeline, at, False) for pipeline, at in listed)
    return [(pipeline, at, child) for pipeline, at, child in out if pipeline]


def _substitution_pairs(tool):
    """The (opener, closer) pairs that open a command line INSIDE a word, for the shell `tool`.

    THE UNION WHERE THE TOOL NAMES NO SHELL THIS READER KNOWS, and that is the opposite direction
    from `_directory_role` on purpose: a verb this reader does not apply leaves the base standing,
    which refuses MORE, while a substitution it does not read hides a command entirely. Not knowing
    the shell therefore has to mean reading every pair.
    """
    shell = SHELLS.get(str(tool or ""))
    if shell is not None:
        return tuple(shell["substitutions"])
    return tuple(dict.fromkeys(pair for entry in SHELLS.values()
                               for pair in entry["substitutions"]))


def _closings(body, opener, closer):
    """Where a substitution opened in front of `body` could end -- the BALANCED closer and the LAST.

    TWO READINGS AND NOT ONE, because at this level a closer cannot be told from a character inside
    the body's own quoting: quoting is resolved per WORD by the kits' reader, and a substitution is
    found in the raw line, one level above the words. Measured 2026-08-07 through the real gate with
    a real bash as arbiter (`docs/POST_V2_WISHLIST.md` H22): `echo $(sed -i "s/a/)/" <kit file>)`
    balances at the `)` inside the substitution's own script, so the balanced reading loses the file
    name while bash rewrites it.

    A READING THAT IS TOO LONG only adds words to a command, and words only add refusals; one that
    is too short loses the command, which is the direction that passes. So both are read and the
    caller judges each.
    """
    ends, depth, index = [], 0, 0
    while index < len(body):
        if opener != closer and body.startswith(opener, index):
            depth += 1
            index += len(opener)
            continue
        if body.startswith(closer, index):
            if depth == 0:
                ends.append(index)
                break
            depth -= 1
            index += len(closer)
            continue
        index += 1
    last = body.rfind(closer)
    if last >= 0 and last not in ends:
        ends.append(last)
    return ends


def substituted_lines(text, tool):
    """Every command line a SUBSTITUTION introduces in `text`, outermost first.

    THIS COSTS MORE THAN THE TEXT IS LONG, and nothing here counts anything to stop it: an opener
    multiplies the readings of `_closings`, and those recurse. What stops it is the gate's budget,
    and the check that enforces it does NOT stand here -- a check at the top of this function is one
    per CALL, while the cost is inside a call, and that is what let a 2444-character line run
    150.6 s against a registered 120 (`docs/POST_V2_WISHLIST.md` H35). It is
    `_the_budget_is_spent`, beside the whole decision, that ends this.
    """
    out = []
    for opener, closer in _substitution_pairs(tool):
        start = text.find(opener)
        while start >= 0:
            body = text[start + len(opener):]
            for end in _closings(body, opener, closer):
                inner = body[:end]
                if inner.strip():
                    out.append(inner)
                    out.extend(substituted_lines(inner, tool))
            start = text.find(opener, start + len(opener))
    return out


def _prose_removed(module, compat_module, text):
    """`text` without the spans a shell runs nothing of, and with its continuations joined.

    The kits' own preprocessing, reached through their objects: heredoc BODIES and message
    ARGUMENTS are prose, a continuation is not a line break, and a line break is a separator.
    """
    text = module._HEREDOC_RX.sub(" ", module._MESSAGE_ARG_RX.sub(" ", text))
    return compat_module.join_line_continuations(text).replace("\n", " ; ")


def command_line(module, compat_module, data, command):
    """Every command a shell would run for this call, in the order it reaches them, with the two
    facts `commands()` reads off the list -- INCLUDING the ones a SUBSTITUTION introduces.

    A COMMAND A SUBSTITUTION INTRODUCES IS PLACED BY THE SAME DECOMPOSITION AS EVERY OTHER: its text
    goes through `commands()` too, and its stages through the same verb and read-only questions one
    level up. Without that it was invisible to both gates -- measured 2026-08-07, `echo $(sed -i
    "s/a/b/" <kit file>)` rc 0 while bash rewrote the protected file, and with a valid verdict in the
    tree `git commit -m wip $(sed -i s/prose/POISON/ docs/note.md)` rc 0 with the poison in the
    commit.

    TWO THINGS ABOUT WHERE IT STANDS ARE STATED RATHER THAN COMPUTED, both in the refusing
    direction:
      * it runs BEFORE the line it is written in, because the shell expands a word before it runs
        the command the word belongs to. A substitution written BEHIND a commit is therefore judged
        as if it stood in front of one;
      * it runs in a CHILD, which is the group depth of 1 below: no directory verb inside a
        substitution moves the base of the line around it.

    WHAT IT DOES NOT SEE is what the kits' prose removal took out first, and that is TWO spans, not
    one -- `_prose_removed` applies both of that gate's expressions, and
    `test_gates.py::test_every_span_the_kits_prose_removal_takes_out_is_named_where_it_is
    _documented` reads them out of that function rather than out of this sentence:

      * `gate_write_scope._MESSAGE_ARG_RX` deletes a quoted span behind one of several flag
        spellings ANYWHERE on the line, whatever the verb -- so an ordinary write operand
        disappears with it, without any substitution and without a commit (H34, with the
        substitution inside a message argument as its special case, H32);
      * `gate_write_scope._HEREDOC_RX` deletes every here-document BODY, and a body is not only
        where a message is written: it is also how a shell is handed a PROGRAM, so a program
        written into one is invisible to both gates (H38, measured 2026-08-08 -- one tool call,
        no preparation, no commit, and bash really rewrites the protected file).

    Reading inside either span would be a second answer to "what is prose", which is the drift H15
    describes; both chains are measured and carried in `docs/POST_V2_WISHLIST.md`.
    """
    text = _prose_removed(module, compat_module, compat_module.unwrap_shell_payload(command))
    out = []
    for inner in dict.fromkeys(substituted_lines(text, data.get("tool_name"))):
        for pipeline, _depth, asynchronous in commands(module,
                                                       tokenise(module, compat_module, inner)):
            out.append((pipeline, 1, asynchronous))
    out.extend(commands(module, tokenise(module, compat_module, text)))
    return out


def _entered_and_left(path):
    """Make `path` this process's working directory and go back. True when the entry succeeded.

    THE MOVE IS REAL, because that is the whole point: entering is the one thing about a directory
    that cannot be read off it, and the process asks it the way every process does. Nothing runs
    beside it while it is out -- `probe` hands the question to the one worker thread and the caller
    waits for that answer -- so the position is back before the next candidate is resolved.

    ONLY THE ENTRY IS ANSWERED WITH False. The way back is not caught here and not in
    `_can_be_entered` either: a process that cannot return to where it stood has no position left
    to judge anything from, and `guarded()` turns that into a refusal.
    """
    here = os.getcwd()
    try:
        os.chdir(path)
    except (OSError, ValueError):
        return False
    os.chdir(here)
    return True


def _can_be_entered(path):
    """Is this a place a process really lands -- asked by ENTERING it? (deadline)

    THE QUESTION A PROCESS ASKS IN ORDER TO GO SOMEWHERE IS THE ONE THAT ANSWERS FOR GOING THERE,
    and every question ABOUT the directory answers something else. Measured 2026-08-05 on this host
    against a directory with a single right revoked (`icacls /deny <user>:(X)` -- traverse, so it
    can still be listed): `os.path.isdir` True, `os.stat` fine, `os.stat` of its `.` fine,
    `os.access(X_OK)` True, `os.scandir` fine -- while both `os.chdir` and a real bash answered
    `Permission denied` and the shell stayed in the tree. With only the LIST right revoked
    (`(RD)`) the two split the other way: `os.scandir` raises while `os.chdir` and bash both go in.
    Opening the directory therefore answered wrong in BOTH directions, and it was here -- one hole
    (gate rc 0 while the shell rewrote the protected file) and one friction. The run is in
    `docs/reviews/2026-08-05-tsk0015-measurements.md` (section 2).
    """
    return bool(probe(_entered_and_left, path))


def _verb_position(module, pipeline, verb):
    """Where the word stands that the kits' `_stage_verb` read as `verb`, or None.

    ONE ANSWER FOR THREE QUESTIONS. What the verb DOES (`_directory_role`), whether the shell runs
    it itself (`_runs_in_the_shell_itself`) and which words are its operands (`_destination_word`)
    are all asked about the same token, and each of them used to find it again on its own. The
    comparison is the kits' own: `_stage_verb` lowercases the word and takes its basename, so
    finding it again means spelling that reading once more here -- and finding it is all this does.
    The word's own TEXT is read off the token by the caller, because that reading is exactly what
    the two questions below must not inherit.
    """
    for index, token in enumerate(pipeline):
        if os.path.basename(str(token).lower().replace("\\", "/")) == verb:
            return index
    return None


def _directory_role(tool, word):
    """What this WORD does to the position of the shell `tool` names, or None -- for it, not for a
    shell somebody else is running.

    THE WORD IS COMPARED THE WAY THE SHELL COMPARES COMMAND NAMES, and that is the whole of this
    function. The reading the kits' `_stage_verb` hands out is folded to lower case and cut down to
    a basename, which are two readings a POSIX shell does not make: measured 2026-08-05 through the
    real gate with a real bash as arbiter over the file, `CD`, `Cd`, `cD`, `PUSHD`, `PushD`,
    `set-location`, `Set-Location` and `/usr/bin/cd` each came out rc 0 while the shell answered
    `command not found` / `No such file or directory`, STAYED in the tree and let the relative write
    behind it rewrite the protected file. A shell whose name this does not know moves nothing, which
    is the fail-closed direction and the reason `SHELLS` is checked against the registration
    (`test_gates.py::test_the_shells_this_reader_knows_are_the_ones_the_registration_names`).
    """
    shell = SHELLS.get(str(tool or ""))
    if shell is None:
        return None
    return shell["verbs"].get(word.lower() if shell["folds_case"] else word)


def _is_the_command_name(module, pipeline, position):
    """Is the word at `position` the one the shell resolves as the command name of this stage?

    ASKED OF WHAT STANDS IN FRONT OF IT, and asked as a property rather than against the kits' list
    of words `_stage_verb` skips: a word in front of the command name is a command of its own, and
    what it then does with the rest of the line is that command's business, not this reader's.
    Measured 2026-08-05 through the real gate, with a real bash as arbiter over the file: `env cd
    <outside>`, `nice cd <outside>` and `sudo cd <outside>` were rc 0 while the shell answered
    `No such file or directory`, stayed, and the relative write behind them rewrote the protected
    file -- `cd` is a builtin, and a word that hands the next word to a CHILD never reaches it.

    WHAT MAY STAND THERE IS SYNTAX (`_SYNTAX_CHARACTERS`) AND NOTHING ELSE, which keeps the brace
    group moving the base as the shell does (`{ cd <outside> ; } ; <write>` really moves it) and
    stops everything else -- including the three words that DO leave the builtin in the shell
    (`command cd`, `time cd`, `! cd`, measured in the same run: the shell moves and this reader
    stays). That is over-refusal, it is the price of not keeping a list of words here, and it is
    carried as H30 in `docs/POST_V2_WISHLIST.md` with the measured chain.
    """
    for token in pipeline[:position]:
        text = module._operator(token)
        if not text or not set(text) <= _SYNTAX_CHARACTERS:
            return False
    return True


def _the_move_in_a_later_stage(module, tool, pipeline):
    """`(stage, verb, position in the pipeline)` for a directory verb the pipeline's own verb hides.

    ONLY THE LAST STAGE, because that is the one whose position can outlive its own stage: a group
    in it holds the commands that follow inside the same child. A `cd` in an EARLIER stage of a
    pipe ends with that stage, and `_group_depth` says so on its own -- outside a group the answer
    is 0 and the multi-stage guard of `_runs_in_the_shell_itself` keeps the base where it is.

    The stage comes back with the verb, because what stands in FRONT of a command name is a
    question about the stage: `true | ( cd …` has `true` and `|` in front of the group, and neither
    says anything about the group's own first word.
    """
    parts = stages(module, pipeline)
    if len(parts) < 2:
        return pipeline, "", None
    head = stage_body(module, parts[-1])
    verb = module._stage_verb(head)
    at = _verb_position(module, head, verb)
    if at is None or _directory_role(tool, str(head[at])) is None:
        return pipeline, "", None
    return head, verb, _verb_position(module, pipeline, verb)


def _group_depth(module, pipeline, position, depth):
    """How many groups stand open where this verb is -- `commands()`' count plus this pipeline's.

    ONE READING FOR TWO QUESTIONS. `_runs_in_the_shell_itself` asks whether the count is nil,
    because that is what decides the PARENT's position; `WorkingDirectory.follow` asks for the
    number, because that is the scope the move really belongs to (`WorkingDirectory.settle`). Both
    were counting it separately, and one of them was counting it only to throw it away.
    """
    for token in pipeline[:position]:
        text = module._operator(token)
        depth += text.count("(") - text.count(")")
    return depth


def _runs_in_the_shell_itself(module, pipeline, position, depth, asynchronous):
    """Does the SHELL ITSELF run this verb, so that where it goes stays with it?

    ASKED AS A PROOF AND NOT AS A SEARCH FOR DANGER, which is this round's correction: the previous
    cut asked whether the verb stood inside a bracket, and every childhood spelled some other way
    answered "no". Measured 2026-08-05 in a real bash, eight such lines rewrote the protected file
    they named relatively while the gate had followed the move out of the tree
    (`docs/reviews/2026-08-05-tsk0013-measurements.md`, section 1, the entry H27). So the position
    has to EARN the move, and three things have to hold at once for it:

      * the verb's list is not run asynchronously -- an `&` anywhere behind it hands the whole list
        to a child, and it may stand behind the LAST pipeline of the list (`cd <elsewhere> &&
        true &`), which is why `commands()` answers this and not a look at one pipeline;
      * its pipeline is the only stage in itself -- every stage of a multi-stage pipeline runs in a
        child;
      * no group is still open where the verb stands -- `depth` is what `commands()` counted up to
        the pipeline, and the rest is counted here, because a group can open in the same pipeline
        (`( cd <elsewhere> )`) or in an earlier one (`( true ; cd <elsewhere> )`).

    Anything that does not prove all three keeps the base where it is, and that is the fail-closed
    direction: a base that has not moved keeps every relative candidate inside the protected tree.
    A brace group is NOT a child and is not treated as one -- measured in the same run, `{ cd
    <elsewhere> ; } ; <write>` really moves the shell and the write lands outside.
    """
    if asynchronous or len(stages(module, pipeline)) > 1:
        return False
    return _group_depth(module, pipeline, position, depth) == 0


def _moves_inside_an_inline_program(tool, pipeline):
    """Does this pipeline hand ANOTHER shell a line that changes where it stands?

    THE MOVE IS THEN NOT THIS PIPELINE'S VERB, so nothing that reads the verb sees it, while the
    real shell really moves -- and the words of everything after it are resolved against a position
    that no longer exists. `WorkingDirectory.follow` carries the measurement.

    ASKED OF WHAT STANDS BEHIND AN INLINE-PROGRAM FLAG, because that is the one place a command
    line carries another command line. What it costs is a read whose own flag cluster happens to
    carry the same letter with a directory verb behind it (`grep -c cd file`), which loses the
    position for the rest of the call -- an over-refusal in the H20 class, and the safe direction.
    """
    behind = False
    for token in pipeline:
        if behind and _directory_role(tool, str(token)) is not None:
            return True
        behind = behind or _carries_flag(token, _INLINE_PROGRAM_FLAG)
    return False


def _redirections_removed(module, words):
    """`words` without what belongs to the SHELL rather than to the verb's operand list.

    A redirection is the shell's own syntax and it is gone before the verb ever sees its operands,
    so the operator and the word it consumes are not part of the list this reader has to account
    for. Both directions are asked through the kits' own shapes (`_REDIRECT_RX`,
    `_INPUT_REDIRECT_RX`), because a second regex for "is this a redirect" is the drift H15
    describes. Without this, `cd <elsewhere> > /dev/null` counted three operands and stopped moving
    a shell that really moves.

    WHAT IS DELIBERATELY LEFT IN THE LIST is a FILE DESCRIPTOR standing in front of an operator
    (`cd <elsewhere> 2> /dev/null`): the kits' shape carries it (`[0-9]*>`), but the tokeniser
    hands it back as a word of its own, and a word of digits is also a directory somebody may have
    named `2`. Dropping it would move the base home on `cd 2 > log` while the shell went into `2/`,
    which is the direction that passes; keeping it makes the whole list unaccountable, which is the
    direction that refuses. H29 carries that friction, together with the descriptor DUPLICATION
    (`2>&1`) the kits' shape does not match either.
    """
    out, skip = [], False
    for token in words:
        text = module._operator(token)
        if skip:
            skip = False
            continue
        if module._REDIRECT_RX.match(text) or module._INPUT_REDIRECT_RX.match(text):
            skip = True
            continue
        out.append(token)
    return out


def _destination_word(module, pipeline, position):
    """The word a directory verb names as its destination -- with THREE answers, not two.

    THE THIRD IS THE ONE THIS ROUND ADDS: an operand list this reader cannot account for
    (`_UNACCOUNTABLE`). "No operand" is a destination of its own -- a bare `cd` goes home, a bare
    `pushd` swaps the stack -- so a list this reader cannot read must not answer with it. Measured
    2026-08-05 through the real gate: `cd <elsewhere> x ; <relative write>` and
    `cd -q <elsewhere> ; <relative write>` came out rc 0 and the write landed in the protected
    file, because the second operand was thrown away and the unknown flag skipped, while bash
    answered `cd: too many arguments` / `cd: -q: invalid option` and STAYED. One tool call, no
    preparation. `docs/reviews/2026-08-05-tsk0015-measurements.md` (section 1) carries the run.

    WHAT THIS READER CAN ACCOUNT FOR IS ONE WORD, and that boundary is a property of the reader
    rather than a table of flags: which options a builtin accepts is known to the builtin alone, so
    a word offered as an option is a word this reader cannot place -- `cd -L <elsewhere>` moves a
    real shell and leaves this base standing. That is the fail-closed direction and it is named as
    H29 in `docs/POST_V2_WISHLIST.md`.

    A LONE DASH IS A DESTINATION, NOT AN OPTION: `-` on its own is the shell's word for "where I
    was". Filtering every word that starts with a dash removed it too, so the comparison that read
    it could never be true -- measured 2026-08-05 (TSK-0011): `cd <outside> ; cd -` landed in the
    HOME directory, and both mutations of that dead branch left all 111 tests green.

    AND `--` IS NEITHER, because the shell's grammar says so: POSIX Utility Syntax Guideline 10 ends
    the options there, so what follows is an operand however it is spelled. That is a definition and
    not a flag this reader claims to know, which is why it closes one of the three spellings H29
    used to carry while `cd -L <target>` stays open.
    """
    words = _redirections_removed(module, pipeline[position + 1:])
    if words and str(words[0]) == _END_OF_OPTIONS:
        words = words[1:]
        if not words:
            return None
        return words[0] if len(words) == 1 else _UNACCOUNTABLE
    if not words:
        return None
    if len(words) > 1 or (str(words[0]).startswith("-") and str(words[0]) != _PREVIOUS_DIRECTORY):
        return _UNACCOUNTABLE
    return words[0]


class WorkingDirectory(object):
    """Where the shell IS while a command line is walked, and what actually moves it.

    FOUR THINGS MOVE IT AND ALL FOUR HAVE TO HOLD, and each of them was once the whole answer:

      * the shell runs the WORD as the verb this reader takes it for -- which is two questions, the
        shell's own vocabulary and spelling (`_directory_role`) and the word standing where the
        shell resolves a command name (`_is_the_command_name`),
      * the shell runs it ITSELF rather than in a child (`_runs_in_the_shell_itself`),
      * the operand list is one this reader can ACCOUNT FOR (`_destination_word`), because a list
        the shell rejects is a line where nothing moves at all,
      * and the move SUCCEEDS (`_enter`).

    Each round that had one of them measured the same failure with another: lines that rewrote the
    protected file they named relatively while the gate had already followed them out of the tree.
    Every one of them is an axis of `test_gates.LINE_SHAPES`, crossed with the others; the column of
    that table is taken from a real shell (`test_the_shell_writes_where_the_table_of_line_shapes
    _says`) and the gate is held to it cell by cell
    (`test_gate1_refuses_a_line_exactly_where_the_shell_would_write`) -- which is what DEC-0014 asks
    for and what this docstring is held to. The VALUES of those axes are generated by the
    enumerations this reader decides from, which is DEC-0016.

    A MOVE THIS READER CANNOT COMPUTE MAKES THE POSITION UNKNOWN, AND THAT IS NOT A PROPERTY OF THE
    VERB. "Staying" was the answer for everything except `popd`, on the ground that a base which has
    not moved keeps every relative candidate inside the protected tree -- which holds only while the
    base IS in it. The moment a line has stepped out, every move this reader cannot compute may be
    the one that steps back IN, and then staying is the PASSING direction. Measured 2026-08-07
    through the real gate with a real bash as arbiter over the file, seven spellings, one cause, all
    rc 0 while bash wrote the protected file: with `cd <outside> ;` in front and a relative write
    behind, `cd "$R"`, `command cd <here>`, `time cd <here>`, `! cd <here>`, `x=1 cd <here>`,
    `cd -L <here>` and `cd <here> 2>&1`. And the boundary that matters is not the REPO's: measured
    in the same run, `cd docs ; command cd .. ; <relative write>` rewrites the protected file from a
    base that never left the repo at all, and was rc 0. So the answer is the same for every
    direction -- what cannot be computed makes
    the position `_UNKNOWN_POSITION`, from which every relative word is an `Unplaceable` refused for
    everyone (`_candidates`, `ProtectedArea.verdict`). An absolute word still resolves, and an
    absolute `cd` ends the state.

    WHAT THAT COSTS is friction on every line whose move this reader cannot follow -- including the
    ones where the shell stays exactly where it was, and including a write into a FREE path behind
    such a move. `docs/POST_V2_WISHLIST.md` H20 carries that cost with its measured chain, H24, H29
    and H30 the shapes that pay it.

    WHAT DOES NOT COST IT is a move this reader CAN compute and that does not happen: a verb the
    shell runs in a child, a directory that cannot be entered, an empty stack it has seen in full.
    Those are answers, not doubts, and the base stays because the shell's does.
    """

    __slots__ = ("base", "why", "_previous", "_stack", "_scopes")

    def __init__(self, base):
        self.base = base
        self.why = ""
        self._previous = base
        # The directory stack, or None for "this reader has not seen every push the shell made".
        # An empty stack and an unseen one answer the next pop differently, and only the second of
        # them was a hole -- see `follow`.
        self._stack = []
        # Where this reader stood before it walked into a GROUP -- see `settle` and `follow`.
        self._scopes = []

    def settle(self, depth):
        """Come back out of every group whose move this reader followed and that has now closed.

        A SUBSHELL MOVES A SHELL THAT ENDS, and both halves of that were wrong here. `( cd <deeper>
        && <command> )` does not move the PARENT -- which `_runs_in_the_shell_itself` had right --
        but the command INSIDE the same brackets runs from the moved directory, and this reader
        resolved it against the base the parent never left. Measured 2026-08-31, real shell as
        arbiter, every one of them rc 0 while the flat spelling of the same line was rc 2:
        `(cd <hooks> && python gate_approval.py)` started the hook and minted `APR-0001`, and in
        the WRITE direction -- open since the shell half was built, not introduced by this round --
        `(cd .claude/hooks && rm gate_todo_items.py)` was rc 0 for EVERY caller, as were
        `(cd project_memory && sed -i … <item>)` and `(cd team-kits && sed -i … kernel/state.py)`.
        That is the dual of H27: that entry closed the write AFTER the closing bracket, this one is
        the write INSIDE it.

        SO THE ANSWER IS A SCOPE AND NOT A REFUSAL. `follow` walks into the group and remembers
        where it stood; when a later pipeline stands at a smaller depth, the group has closed and
        the base comes back. Losing the position instead -- the shorter fix -- would have refused
        `(cd tools && python bump_kit_version.py)`, i.e. a line of this repo's own delivery, and a
        gate that refuses those is broken rather than stricter.
        """
        while self._scopes and self._scopes[-1][0] > depth:
            _at, base, previous, stack = self._scopes.pop()
            self.base, self._previous, self._stack = base, previous, stack

    def _open_scope(self, at):
        """Remember where the shell stands before a move made INSIDE a group at depth `at`."""
        self._scopes.append((at, self.base, self._previous,
                             None if self._stack is None else list(self._stack)))

    def follow(self, module, compat_module, pipeline, depth, asynchronous, tool):
        """Move as this pipeline would move a shell -- or stay, which is most of the answer.

        `depth` and `asynchronous` are what `commands()` read off the LIST this pipeline stands in,
        and neither has a default: the values a forgetful caller would get are "top level" and
        "synchronous", which is the one combination that lets the base move. `tool` is the same
        question the kits' `_null_sinks` already asks of a payload -- which shell is this line for.
        """
        verb = module._stage_verb(pipeline)
        position = _verb_position(module, pipeline, verb)
        if position is None:
            return
        said = " ".join(str(token) for token in pipeline)[:120]
        # FIRST, BEFORE ANY SEARCH FOR A VERB THIS PIPELINE MIGHT CARRY: a line handed to another
        # shell is one this reader does not decompose at all, so nothing it finds in the tokens can
        # be trusted to be the move. Ordering it after the search cost the `sh -c "cd <hooks> && …"`
        # refusal for a subagent -- measured, 2 -> 0, while building the paragraph below.
        if _moves_inside_an_inline_program(tool, pipeline):
            # A LINE HANDED TO ANOTHER SHELL MOVES A SHELL THIS ONE IS NOT WATCHING. The move is
            # not this pipeline's verb, so nothing below would look at it, and the words of the
            # NEXT pipeline are then resolved against a position the real shell has left. Measured
            # 2026-08-31 with a real shell against a real kernel: `sh -c "cd <hooks> && python
            # gate_approval.py"` was rc 0 for a subagent and minted `APR-0001` -- the reader cut at
            # the `&&`, saw `python gate_approval.py` from the repo root, and placed it nowhere
            # near a hook directory.
            self._lose(said)
            return
        head = pipeline
        role = _directory_role(tool, str(pipeline[position]))
        if role is None:
            # THE MOVE MAY BE IN A LATER STAGE OF THE PIPE, and then this pipeline's own verb is
            # not it. `true | (cd <hooks> && python gate_approval.py)` puts the whole group in the
            # receiving stage, so the `cd` and the command it applies to are in the SAME child --
            # measured 2026-08-31, rc 0 in all four combinations while the same group without the
            # pipe was rc 2. Read from the last stage; `head` keeps that stage, because what stands
            # in front of the verb is a question about the stage and not about the pipeline (a
            # `true |` in front of a group says nothing about the group's own first word).
            head, verb, position = _the_move_in_a_later_stage(module, tool, pipeline)
            if position is None:
                return
            role = _directory_role(tool, str(pipeline[position]))
        inside = _group_depth(module, pipeline, position, depth)
        if inside > 0:
            # INSIDE A GROUP THE MOVE IS REAL FOR EVERY COMMAND OF THAT GROUP, and only the parent
            # keeps its place. `_runs_in_the_shell_itself` answers the parent's question and
            # answers it correctly; what was missing is the group's own. `settle` carries the
            # measurement and what the shorter fix would have cost.
            self._open_scope(inside)
        elif not _runs_in_the_shell_itself(module, pipeline, position, depth, asynchronous):
            return
        if not _is_the_command_name(module, head, _verb_position(module, head, verb)):
            # A word in FRONT of the command name is a command of its own, and what it does with
            # the rest is its business: `command cd` leaves the builtin in the shell, `env cd`
            # never reaches it. Which of the two this is, is not readable from here.
            self._lose(said)
            return
        operand = _destination_word(module, head, _verb_position(module, head, verb))
        if operand is _UNACCOUNTABLE:
            self._lose(said)
            return
        if role == _POP:
            if operand is not None or self._stack is None:
                # A pop with ANY operand -- this reader tracks entries, not their indices, so
                # `popd +0` and `popd +9` are one word to it and only one of them moves -- and a
                # pop whose stack it has not seen in full.
                self._lose(said)
            elif self._stack:
                if not self._enter(self._stack.pop()):
                    self._lose(said)
            # An empty stack this reader HAS seen in full is an error in the shell too, and the
            # shell stays.
            return
        if role == _PUSH and operand is None:
            # `pushd` with no operand swaps the top of the stack with where we are; with an empty
            # stack there is nothing to swap with, and that is an error, not a move
            if self._stack is None:
                self._lose(said)
            elif self._stack:
                leaving = self.base
                if self._enter(self._stack.pop()):
                    self._stack.append(leaving)
                else:
                    self._lose(said)
            return
        leaving = self.base
        target = self._resolve(module, compat_module, head, operand,
                               _verb_position(module, head, verb))
        if target is None or not self._enter(target):
            # TWO WAYS TO FAIL AND ONE ANSWER. This reader could not name a directory from the word
            # (a variable, a target `_walk` walks out of the tracked point), or it could name one
            # and no process can land there. The second is NOT the same as "the shell stayed": a
            # text this reader cannot enter is also what a word looks like whose value the shell
            # computed and this reader did not, and the two are not separable from here. Measured
            # 2026-08-07: `cd <outside> ; R=<here> ; cd "$R" ; <relative write>` was rc 0 and bash
            # rewrote the protected file -- `_walk` had named a directory `$R` under the base, which
            # cannot be entered, and staying left the base outside.
            self._lose(said)
            return
        if role == _PUSH and self._stack is not None:
            self._stack.append(leaving)

    def _lose(self, said):
        """Give up the position, naming the pipeline that took it (see the class docstring)."""
        self.base = self._previous = _UNKNOWN_POSITION
        self._stack = None
        self.why = said

    def _enter(self, directory):
        """Land in `directory` if a shell could land there. True when the position moved."""
        if directory is None or directory is _UNKNOWN_POSITION or not _can_be_entered(directory):
            return False
        self._previous, self.base = self.base, directory
        self.why = ""
        return True

    def _resolve(self, module, compat_module, pipeline, operand, position=0):
        """The absolute directory this word names, or None when nothing here can name it.

        `_walk` stays the answer for the relative case, fed with the absolute point we stand on --
        one reading of a path walk, not a second. From an UNKNOWN position only an absolute word
        names anything, and naming nothing keeps the position unknown.

        THE PIPELINE IS HANDED OVER FROM THE VERB ON, because that is where the kits' `_walk`
        starts reading (`pipeline[1:]` are its arguments). Everything in front of the verb is shell
        syntax by then -- `_is_the_command_name` has said so -- but it still COUNTS: measured
        2026-08-31, `( cd team-kits/dev-team/hooks && …` handed `_walk` a pipeline whose first
        token was `(`, so it read `cd` itself as the destination and answered `<base>/cd`, a
        directory nothing can enter. The position was then given up on a line this reader can
        follow perfectly well.

        A TILDE THIS READER MAY NOT EXPAND NAMES NOTHING HERE EITHER (`_expanded`, DEC-0020), and
        the caller reads that as a move it could not compute -- so the position is given up rather
        than left standing on a guess. `cd ~+` is the shape: the shell goes to its own working
        directory, and the delegate would have answered with a directory under the home one.
        """
        if operand is None:
            return _expanded(_TILDE, True)
        if str(operand) == _PREVIOUS_DIRECTORY:
            return self._previous
        for reading, expandable in readings(compat_module, operand):
            expanded = _expanded(reading, expandable)
            if expanded is None:
                return None
            if os.path.isabs(expanded):
                return expanded
        if self.base is _UNKNOWN_POSITION:
            return None
        walked = module._walk(pipeline[position:], str(self.base).replace("\\", "/"))
        if walked is None:
            return None
        walked = walked.replace("/", os.sep)
        return walked if os.path.isabs(walked) else None


def _started(candidate):
    """One candidate of the START position, as the kind of subject that makes it.

    An `Unplaceable` keeps its own kind: a word nothing on the line places can name any file on the
    host, so it is the wider answer of the two and the position does not narrow it.
    """
    return candidate if isinstance(candidate, Unplaceable) else Executed(candidate)


def written_paths(data):
    """Every path this command line would WRITE, plus every file it would START.

    FOUR POSITIONS, and they are the four a command line has:
      * the target of an output redirect that RETAINS what is written (`_null_sinks` decides what
        retains; a redirect into the discard device is output suppression, not a write),
      * every word of a stage whose verb carries a WRITE FLAG (`sed -i`, `find -delete`, ...),
      * every word of a stage whose verbs are not read-only and that does not merely RUN what it
        is given -- for an interpreter only the inline program text (`-c`) is read as a write,
        since its other operands are code to execute, not files to change,
      * and the file the stage STARTS (`_executed_words`), which is a subject of its own kind
        (`Executed`) because it is judged against the enforcement layer and not against the whole
        protected area -- `python tools/bump_kit_version.py` is how this repo is stamped.

    A stage with no verb at all (`$env:PYTHONPATH="team-kits"`) runs no program and writes
    nothing, which is why the PowerShell spelling of this repo's own kernel call survives.

    WHERE A RELATIVE WORD IS RESOLVED: the directory the call runs in -- the payload's `cwd`, and
    when the payload does not say, this process's own, which is the only other thing that could
    answer. Every payload recorded from a real hook process in
    `docs/reviews/2026-08-05-tsk0007-measurements.md` (section 6) carries `cwd`, so the fallback is
    not a shape this repo has seen. A directory verb moves it only where a shell would really land,
    which is `WorkingDirectory` and is where this round's correction sits.

    THE LINE IS CUT WHERE THE SHELL CUTS IT (`command_line()`), not where the kits' separator tuple
    does. One command too few is not a smaller answer here, it is a wrong one: the words behind the
    missed cut are then judged with the verb in FRONT of them, and a read-only verb hides them
    (`echo hi & sed -i <kit file>`, measured rc 0) -- and a command a SUBSTITUTION introduces is one
    of those, which is why it is placed by the same decomposition.
    """
    module = shell_reader(data)
    compat_module = compat(data)
    command = str((data.get("tool_input") or {}).get("command") or "")
    sinks = module._null_sinks(data.get("tool_name"))
    directory = WorkingDirectory(str(data.get("cwd") or "") or os.getcwd())
    out = []
    for pipeline, depth, asynchronous in command_line(module, compat_module, data, command):
        # BEFORE THE WORDS ARE PLACED, not after: a group that has closed took its move with it,
        # and the next pipeline's relative words belong to the shell that stands outside it again
        # (`WorkingDirectory.settle`).
        directory.settle(depth)
        for target in module._redirect_targets(pipeline, sinks):
            out.extend(_candidates(compat_module, target, directory))
        for stage in stages(module, pipeline):
            body = stage_body(module, stage)
            verb = module._stage_verb(body)
            if not verb:
                continue
            if module._has_write_flag(verb, body[1:]):
                words = body
            elif _runs_a_program(verb):
                words = _inline_program_words(body)
            elif module._stage_is_read_only(body):
                words = []
            else:
                words = body
            for word in words:
                out.extend(_candidates(compat_module, word, directory))
            started, handed = _executed_words(module, data.get("tool_name"), body, verb)
            for word, starts in [(word, True) for word in started] + \
                                [(word, False) for word in handed]:
                # an `Unplaceable` from this position is not a word to resolve -- it is the
                # verdict already (`_handed_a_program_from_elsewhere`), and resolving it would turn
                # the interpreter's own name into a path nothing protects
                if isinstance(word, Unplaceable):
                    out.append(word)
                    continue
                out.extend(_started(candidate)
                           for candidate in _candidates(compat_module, word, directory,
                                                        starts=starts))
        directory.follow(module, compat_module, pipeline, depth, asynchronous,
                         data.get("tool_name"))
    return out


# -- the typed state ----------------------------------------------------------


def project_state(root):
    """The kernel's reader for this repo's `project_memory/`."""
    _add_kit_paths(root)
    return _from_kit("kernel.state").ProjectState(os.path.join(root, STATE_ROOT))


def id_scanner(root):
    """A regex proposing item ids in free text, built from the kernel's own type registry.

    A PROPOSAL, not a verdict: the type names come from `ACTIVE_DIRS` (so a type the kernel gains
    is recognised without an edit here) and the number is left wide, because `parse_id` is what
    decides whether a candidate is an id at all. Reading `TSK-3` as "no id present" would let a
    mistyped reference count as the one entry a list may leave unbound.
    """
    _add_kit_paths(root)
    active = _from_kit("kernel.backlog_types").ACTIVE_DIRS
    return re.compile(r"(?<![A-Za-z0-9])(?:%s)-\d+" % "|".join(sorted(active)))


class Reference(object):
    """One `<TYPE>-nnnn` found in text, together with what the store says about it."""

    __slots__ = ("text", "item_type", "status", "found", "archived")

    def __init__(self, text, item_type, status, found, archived):
        self.text = text
        self.item_type = item_type
        self.status = status
        self.found = found
        self.archived = archived

    def carries_work(self, automata):
        """Can this type LEAD work at all?

        THE PROPERTY IS "HAS A LIFECYCLE", i.e. membership in the kernel's `AUTOMATA`. SR-0009
        clause 4 asks two things of an entry's item, and only the first is a question about its
        TYPE: that it CAN CARRY WORK. (Whether the item is terminal is the second, and `terminal()`
        answers it.) A `DEC` has no automaton, so it has no state to move and nothing to be
        non-terminal about: pointing a task list entry at one names a decision, not work.

        WHAT THAT ADMITS, said plainly because the clause names no type at all: every type with an
        automaton passes, so `PR`, `RQ`, `SR`, `CR`, `PROC`, `HYP` and `EXP` do besides `TSK`,
        `BUG` and `FR`. `test_the_types_a_task_list_carries_work_in_are_the_ones_the_derivation
        _accepts` pins both ends of that -- the three types a task list here is written with must
        pass, `DEC` must fail -- so a rename or a `DEC` that grew a lifecycle turns it red instead
        of quietly changing what this gate means.
        """
        return self.item_type in automata

    def terminal(self, automata):
        """Is this item finished?

        TWO SOURCES, because the kernel has two. A type WITH an automaton is terminal when its
        status is one of that automaton's terminals. A type without one has no terminals to
        declare -- `state.archive()` takes automaton-less types unconditionally -- so for those the
        archive IS the terminal signal, and `read_anywhere` already reports which half answered.

        WHAT IT DOES NOT ASK is whether an item in a NON-terminal status still has work in it:
        `SR` reaches `ACCEPTED` and stays there for good, so it counts as open work for ever
        (`docs/POST_V2_WISHLIST.md` H7). Closing that needs a "done" notion the kernel's `AUTOMATA`
        does not have.
        """
        if self.archived:
            return True
        automaton = automata.get(self.item_type)
        return automaton is not None and self.status in automaton.terminals


def resolve_references(root, text):
    """Every item id `text` proposes, resolved against `project_memory/`."""
    state = project_state(root)
    _add_kit_paths(root)
    parse_id = _from_kit("kernel.backlog_types").parse_id
    out = []
    for candidate in dict.fromkeys(id_scanner(root).findall(text or "")):
        try:
            item_type, _number = parse_id(candidate)
        except Exception:  # noqa: BLE001 -- a candidate the kernel does not read as an id
            out.append(Reference(candidate, None, None, False, False))
            continue
        try:
            item, archived = state.read_anywhere(candidate)
        except Exception:  # noqa: BLE001 -- unreadable store: "cannot say" is not "resolves"
            item, archived = None, False
        if not isinstance(item, dict):
            out.append(Reference(candidate, item_type, None, False, False))
            continue
        out.append(Reference(candidate, item_type, str(item.get("status") or ""), True, archived))
    return out


def automata(root):
    _add_kit_paths(root)
    return _from_kit("kernel.backlog_types").AUTOMATA


# -- the working tree, as a subject a verdict can name ------------------------


def _git(root, arguments):
    """git, run in `root`, output as BYTES. Raises on a non-zero exit.

    BOUNDED BY THE GATE'S OWN BUDGET rather than by a number of its own: a git that hangs costs
    this gate the same thing an unreachable path does -- being killed, which the provider reads as
    an allow. The bound that stood here equalled the registered timeout, so it could only ever
    expire after the provider had already given up.
    """
    done = subprocess.run(["git"] + arguments, cwd=root, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=_DEADLINE.remaining())
    if done.returncode != 0:
        raise RuntimeError("git %s failed (rc %d): %s"
                           % (" ".join(arguments), done.returncode,
                              done.stderr.decode("utf-8", "replace")))
    return done.stdout


def git_command_names(root):
    """Every command name the RUNNING git answers to, lower-cased.

    THE ONE THING GIT DOES NAME. It does not name its history-recording subcommands (measured:
    `docs/reviews/2026-08-13-tsk0056-history-recording-design.md`, section 1), but it names its own
    command set, and that is what tells an alias from a command: a resolved verb git does not list
    here is an alias, an external `git-<name>` on PATH, or a typo -- and the first of those runs a
    command no reader of the LINE can see (`git -c alias.z='!git merge --no-ff other' z` reads as
    the subcommand `z`, measured through the kits' reader).

    ASKED OF THE RUNNING GIT, so a git that gains or loses a command is followed on the day it is
    installed. A failure to answer raises, and `guarded()` turns that into a refusal -- on a host
    whose git does not answer `--list-cmds`, every git line with a verb outside the author set is
    refused rather than waved through.

    COST, measured on this host: 0.042 s for the first call and ~0.05 s for each further one,
    against a registered 120 s. It is asked at most once per gate PROCESS and only for a line that
    invokes git, and a gate process answers one call and exits -- so the memo below has no
    invalidation story to get wrong, it lives exactly as long as the question.
    """
    if root not in _GIT_COMMAND_NAMES:
        _GIT_COMMAND_NAMES[root] = frozenset(
            word.decode("utf-8", "replace").strip().lower()
            for word in _git(root, ["--list-cmds=main"]).split())
    return _GIT_COMMAND_NAMES[root]


_GIT_COMMAND_NAMES = {}


DIFF_PREFIX = "diff:"


def working_tree_digest(root):
    """`diff:<sha256>` over what a commit here WOULD record, minus the state store.

    WHAT IS IN IT: the commit this working tree sits on (`rev-parse HEAD`), the full binary diff
    from that commit to the working tree, and every untracked, non-ignored file with the hash of
    its content. Staged and unstaged changes are one subject here, because a commit records the
    tree either way once it is added.

    WHAT IS OUT, and this exclusion is what makes the whole gate reachable rather than a paradox:
    `project_memory/`. The evidence that certifies a state is WRITTEN into the state store, so a
    digest covering the store changes the moment the certificate exists, and no evidence could
    ever cover the tree it was recorded for. Excluding the store is therefore not a convenience --
    it is the only fixpoint this construction has. What it costs is stated rather than hidden: a
    change to `project_memory/` alone does not invalidate a verdict, so the gate says nothing
    about bookkeeping edits made after the review.

    WHAT ELSE IT DOES NOT COVER: anything git ignores. `.gitignore` decides, which is the same
    answer a commit gives, and it means a change confined to an ignored path is invisible here --
    as it is to the commit.

    THE DIGEST MOVES WHENEVER THE PACKAGE DOES, on purpose. `python tools/bump_kit_version.py`
    rewrites VERSION files and therefore moves it, so the stamp has to be taken BEFORE the verdict
    is recorded -- which is the order the repo's own finishing sequence already prescribes.
    """
    exclude = ":(exclude)" + STATE_ROOT
    digest = hashlib.sha256()
    digest.update(_git(root, ["rev-parse", "HEAD"]))
    digest.update(b"\0")
    digest.update(_git(root, ["diff", "--binary", "--no-color", "--no-ext-diff", "HEAD",
                              "--", ".", exclude]))
    digest.update(b"\0")
    listing = _git(root, ["ls-files", "--others", "--exclude-standard", "-z",
                          "--", ".", exclude])
    for name in sorted(part for part in listing.split(b"\0") if part):
        digest.update(name)
        digest.update(b"\0")
        try:
            with open(os.path.join(root, name.decode("utf-8", "surrogateescape")), "rb") as handle:
                for block in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(block)
        except OSError as error:
            # a file that cannot be read is not a subject that can be certified
            raise RuntimeError("cannot read untracked file %r: %s" % (name, error)) from None
        digest.update(b"\0")
    return DIFF_PREFIX + digest.hexdigest()


def _strings(value):
    """Every string anywhere inside a parsed item -- values, list members, nested mappings."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for inner in value.values():
            for text in _strings(inner):
                yield text
    elif isinstance(value, (list, tuple)):
        for inner in value:
            for text in _strings(inner):
                yield text


def evidence_naming(root, token):
    """The id of a passing Evidence item that NAMES `token`, or None.

    ANY FIELD, because the record is data and the question is whether it names the subject it
    judged -- not which key the reviewer reached for. `--summary` is the field the refusal's own
    remedy fills, `--artifact-ref` is where a reviewer who prefers a reference would put it, and
    pinning one of them would make the other silently not count.

    `result: pass` is the verdict half. A failing report that names the same digest is a review
    that happened and said no; opening a commit on the existence of a report rather than on its
    verdict is the false-accept `backlog_types.REQUIRED_FIELDS` documents for `EVD.result`.
    """
    import yaml
    state = project_state(root)
    for stem, path in state.iter_active_items("EVD"):
        try:
            with open(path, encoding="utf-8") as handle:
                item = yaml.safe_load(handle)
        except Exception:  # noqa: BLE001 -- an unreadable record judges nothing
            continue
        if not isinstance(item, dict):
            continue
        if str(item.get("result") or "").strip().lower() != "pass":
            continue
        if any(token in text for text in _strings(item)):
            return str(item.get("id") or stem)
    return None


# -- agent definitions --------------------------------------------------------

ITEM_REQUIRED = "required"
ITEM_NONE = "none"
ITEM_KEY = "harness_item"


def spawn_needs_an_item(root, agent_name):
    """Does a spawn of `agent_name` have to name an item? (frontmatter `harness_item:`)

    ASKED OF THE AGENT'S OWN DEFINITION, so no gate carries a list of role names. Two agents in
    this repo genuinely have no item -- the watchers write only into
    `radar/` -- and an enumeration of those two would be wrong the day a third watcher ships or
    one of them is renamed. Their definitions say `harness_item: none` instead; everything else,
    including a definition that says nothing, needs one.

    THE DEFAULT IS "REQUIRED", AND SO IS EVERY FAILURE. A missing file, an unparsable frontmatter
    or an unexpected value all answer `required`: the exemption has to be stated, never inferred.

    WHAT THIS EXEMPTION COSTS, named rather than implied: it is SELF-DECLARED, and this function
    opens the file on EVERY call. It is not the provider loading a role at session start -- it is
    this gate reading a file -- so a definition written a moment ago is in force at the next spawn.
    Measured 2026-08-05 in one run: a spawn without an item rc 2, `harness_item: none` written into
    the frontmatter, the same spawn rc 0. The sentence that stood here said the opposite ("read at
    session start, so the definition cannot be used by the session that wrote it") and was the
    protection nothing built.

    What stands against it now is gate 1, which refuses `.claude/**` to the SESSION instance
    (`ProtectedArea`). A SUBAGENT is not refused there and cannot be: an implementer's work order
    routinely names `.claude/hooks/**`, and this repo has no dispatch to check a subagent's scope
    against. So the remaining route is "spawn a subagent, have it write the exemption, spawn
    again" -- carried with its chain in `docs/POST_V2_WISHLIST.md` H12 rather than closed here.
    """
    path = os.path.join(root, AGENTS_DIR, str(agent_name or "").strip() + ".md")
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return True
    if not text.startswith("---"):
        return True
    parts = text.split("\n---", 2)
    if len(parts) < 2:
        return True
    import yaml
    try:
        front = yaml.safe_load(parts[0].lstrip("-").lstrip("\n"))
    except Exception:  # noqa: BLE001 -- unreadable frontmatter states no exemption
        return True
    if not isinstance(front, dict):
        return True
    return str(front.get(ITEM_KEY) or "").strip().lower() != ITEM_NONE


def spawned_agent(data):
    """The role a spawn payload asks for, across the spellings the providers use."""
    tool_input = data.get("tool_input") or {}
    for field in ("subagent_type", "agent_type", "subagent", "agent"):
        value = tool_input.get(field)
        if value:
            return str(value).strip()
    return ""


def spawn_text(data):
    """Everything a spawn payload says, as one text to scan for item ids."""
    tool_input = data.get("tool_input") or {}
    return "\n".join(str(value) for value in tool_input.values() if isinstance(value, str))
