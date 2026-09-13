#!/usr/bin/env python3
"""
Shared helper: the ONE bridge from a hook process to the V2 state kernel (spec II.4).

Every V2 integrity gate needs the same four things, and each of them has exactly one correct
answer — so none of them is left to the individual hook:

  1. WHERE the kernel package is (it travels with the enforcement layer, but the harness repo
     runs its own hooks straight from the checkout — see kernel_parents()),
  2. WHERE the canonical state lives (`<repo>/project_memory`),
  3. what "empty or unreachable state" means (BLOCK — spec II.4 fail-closed; the V1
     `gate_proc_approved` bootstrap hole, where an empty store let every spawn through, is
     exactly the failure this closes),
  4. what an INTERNAL error means (also BLOCK: a hook that crashes is treated by Claude Code as
     a hook that permitted the call, so a bare traceback silently disarms the gate).

FAIL-CLOSED IS ABOUT EXIT CODE 2, NOT ABOUT "non-zero". Claude Code blocks on 2 and treats every
other code as a non-blocking error — the call proceeds. An uncaught exception exits 1, i.e.
ALLOW. That is why this module does three things a single try/except cannot:
  * `fail_closed()` catches BaseException (re-raising only SystemExit), so KeyboardInterrupt and
    MemoryError block instead of exiting 1 or 3221225786;
  * a `sys.excepthook` installed at import time turns anything raised outside the guard —
    module-level code in the gate, a failed kernel import, a half-finished kit update — into an
    exit 2 as well;
  * `block()` degrades to `os._exit(2)` if even the stderr write fails.

That covers everything AFTER `import _kernel` has SUCCEEDED — and the gap is not academic: this
module imports `_root`, `_audit` and `_compat` itself, so a half-written sibling helper (the most
likely artifact of exactly the interrupted kit update cited above) breaks `import _kernel`, the
excepthook is never installed, and the process exits 1 = allow. Nothing inside this file can fix
that, because it is not running. Every V2 gate therefore OPENS with the GATE_PREAMBLE constant
defined below — the only construct that survives its own HELPERS being broken. Copy it from the
constant, never retyped from prose; `tools/test_hooks_v2.py` asserts that every shipped V2 gate
starts with it verbatim, so it cannot be forgotten.

One boundary remains open, and it is named here so it stays a decision rather than a discovery:
the preamble cannot cover the GATE FILE ITSELF failing to compile. A gate truncated mid-write —
just as plausible an artifact of an interrupted kit update as a truncated helper — raises
SyntaxError before its first statement runs, so neither preamble nor excepthook is reached, and
the process exits 1 = allow. Nothing inside a Python file can close that; it closes one level up,
by invoking gates through a launcher whose own compile is the only one that must succeed. That
belongs to the settings.json wiring, not here.

Fail-open stays legal for COMFORT hooks only (formatting, notifications, dashboards, spec II.4);
they must not use `fail_closed()` and pass `tolerate_overflow=True` to `_compat.load()`.

LATENCY, deliberately traded (spec II.5): importing the kernel pulls in PyYAML (~tens of ms).
The spec asks integrity gates to be stdlib-first "wo vermeidbar" and puts latency at a MEASURED
p95 target (~300 ms, warn 500 ms) that is explicitly NOT a blocking gate. Hand-rolling a YAML
subset parser inside a fail-closed path would trade a measurable few tens of milliseconds for an
unmeasurable correctness risk in the one code path that must never be wrong. If the CI bench
shows the p95 target missed, the fix is a JSON sidecar written by the kernel — not a second
parser for the same files.
"""
import os
import sys

# THE GATE PREAMBLE PUT THIS DIRECTORY AT sys.path[0], and it outlives the preamble. Every stdlib
# name a gate imports AFTER `import _kernel` (`re`, `shlex` in gate_write_scope) and every one the
# sibling helpers below pull in (`re` in _compat) would otherwise be answerable by a file planted
# in this directory -- measured 2026-08-05 (BUG-0013): a no-op `re.py`/`shlex.py` here left the
# tokeniser empty, `written_paths` empty, and gate 1 allowed `sed -i` into
# `team-kits/kernel/state.py` with rc 0 and no stderr.
#
# THE GUARD ITSELF LIVES IN `_stdlib_guard`, which is also what `_gate.py` installs BEFORE it
# executes any gate -- one definition, two positions, and the launcher's is the one that covers the
# hooks which never import this module. What THIS position adds is the direct run: a hook started
# without the launcher is guarded if it uses the bridge.
#
# WHAT RUNS AHEAD OF THE GUARD IS `os`, `sys` AND `_stdlib_guard`, AND NOTHING ELSE -- which is the
# correction of 2026-08-11. This paragraph used to name `importlib` among them and call all three
# "already in sys.modules"; measured, `importlib` is NOT preloaded, so `import importlib` ahead of
# the guard really did execute a planted `importlib.py` (the process still ended in rc 2, but
# through the preamble's fail-closed bracket, not because the plant was refused). `os` and `sys`
# ARE preloaded by interpreter start-up, and `_stdlib_guard` imports nothing beyond them and
# reaches `PathFinder` through `sys.meta_path` instead of importing it -- see its docstring.
_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOKS_DIR)

import _stdlib_guard  # noqa: E402

_stdlib_guard.install((_HOOKS_DIR,))

import contextlib  # noqa: E402 -- after the guard on purpose (see above)
import importlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402

from _root import find_repo_root  # noqa: E402
import _audit  # noqa: E402
import _compat  # noqa: E402

STATE_DIRNAME = "project_memory"
KIT_STATE_FILE = "kit_state.json"
# every hook process that reaches the kernel must agree on this name; the package uses relative
# imports, so what goes on sys.path is always the PARENT of the `kernel` directory
KERNEL_PKG = "kernel"
# a bootstrap window is minutes of installer work, never a standing permission (spec II.4)
BOOTSTRAP_MAX_TTL = 3600.0
# extensions a canonical state artifact can carry (spec II.2 file structure): typed items and
# approvals are YAML, frozen design revisions are HTML, ARC/WFR diagrams are .drawio.svg
CANONICAL_SUFFIXES = (".yaml", ".yml", ".html", ".drawio.svg")


class KernelUnavailable(RuntimeError):
    """The state kernel could not be located or imported — integrity gates BLOCK on this."""


def _same_file(left, right):
    """Path identity for TWO PATHS TO ONE FILE.

    Deliberately realpath+normcase, unlike `_root.find_repo_root`, which stays lexical on
    purpose (resolving junctions would change path identity for prefix-comparing guards). Here
    the question is the opposite one — "is this the same file?" — and case matters: _root
    uppercases the drive letter while a sys.path entry keeps whatever case it was given, so a
    plain string compare reports the SAME kernel as a foreign installation.
    """
    if not left or not right:
        return False
    try:
        return (os.path.normcase(os.path.realpath(left))
                == os.path.normcase(os.path.realpath(right)))
    except OSError:
        return False


def kernel_parents(repo_root):
    """Candidate sys.path entries holding the `kernel` package, most specific first.

    - $HARNESS_KERNEL_PATH: explicit override (tests, installers, side-by-side V2 RC). It is
                            AUTHORITATIVE, not merely first: an override that silently falls back
                            to some other installation is the "enforced against the wrong state"
                            hazard in a different costume.
    - <repo>/.claude:       scaffolded project — the kernel travels with hooks + settings, so a
                            project always runs the kernel its hook bundle was hashed against
    - <repo>/team-kits:     the harness repo itself, running its own kits from the checkout
    - ~/.claude/team-kits:  the installed kit bundle
    """
    override = os.environ.get("HARNESS_KERNEL_PATH")
    if override:
        return [override]
    candidates = []
    if repo_root:
        candidates.append(os.path.join(repo_root, ".claude"))
        candidates.append(os.path.join(repo_root, "team-kits"))
    candidates.append(os.path.join(os.path.expanduser("~"), ".claude", "team-kits"))
    return candidates


def import_kernel(repo_root=None):
    """Import and return the `kernel` package. Raises KernelUnavailable with a remedy."""
    repo_root = repo_root or find_repo_root()
    overridden = bool(os.environ.get("HARNESS_KERNEL_PATH"))
    tried = []
    for parent in kernel_parents(repo_root):
        init = os.path.join(parent, KERNEL_PKG, "__init__.py")
        tried.append(parent)
        if not os.path.isfile(init):
            continue
        existing = sys.modules.get(KERNEL_PKG)
        if existing is not None:
            # a hook process imports the kernel exactly once; a DIFFERENT kernel already in
            # sys.modules means two installations are in play, and silently preferring either
            # one would enforce against state the other wrote
            found = getattr(existing, "__file__", None)
            if found and not _same_file(found, init):
                raise KernelUnavailable(
                    "kernel already imported from %s but this repo resolves to %s — refusing to "
                    "enforce with a foreign kernel. Remedy: run `python scripts/harness.py doctor`; a stale "
                    "$HARNESS_KERNEL_PATH or a half-finished kit update is the usual cause."
                    % (found, init)
                )
            # re-import of an already-loaded module is a no-op, but it repairs the one state
            # Python leaves behind after a FAILED `import kernel.state` (package present,
            # submodule absent) — without it open_state() degrades to a bare AttributeError
            _import_kernel_state(init)
            return existing
        # INSERT, then pop again in `finally`. Both halves are load-bearing. Inserting at 0 is
        # what makes the resolved kernel win the import; appending instead (tried once) let any
        # earlier sys.path entry with a `kernel` package take over — a decoy planted via
        # PYTHONPATH, a site-packages distribution of that name, a stray `.claude/hooks/kernel/`
        # — and gates were handed a foreign ProjectState with no error at all. Popping it right
        # after closes the window in which `<repo>/.claude` would shadow a stdlib module for the
        # rest of the process; submodules keep resolving afterwards via the package's own
        # __path__, so `kernel_module()` is unaffected.
        added = parent not in sys.path
        if added:
            sys.path.insert(0, parent)
        try:
            _import_kernel_state(init)
        finally:
            if added:
                with contextlib.suppress(ValueError):
                    sys.path.remove(parent)
        module = sys.modules[KERNEL_PKG]
        # belt and braces: prove what we got is what we resolved. `isfile(init)` only proved a
        # kernel EXISTS there; nothing so far proved the import produced that one.
        if not _same_file(getattr(module, "__file__", None), init):
            raise KernelUnavailable(
                "resolved the kernel at %s but the import produced %s — refusing to enforce with "
                "a kernel this repo did not install. Remedy: something earlier on sys.path "
                "(PYTHONPATH, a site-packages package named `kernel`, a stray copy inside the "
                "repo) shadows it; remove it, then re-run `python scripts/harness.py doctor`."
                % (init, getattr(module, "__file__", None) or "<unknown>")
            )
        return module
    if overridden:
        raise KernelUnavailable(
            "$HARNESS_KERNEL_PATH points at %s, which holds no `kernel` package — refusing to "
            "enforce without a kernel. Remedy: fix or unset $HARNESS_KERNEL_PATH; while it is "
            "set it is the ONLY candidate, by design." % tried[0]
        )
    raise KernelUnavailable(
        "no state kernel found (looked in: %s). Remedy: re-run the team scaffold for this repo "
        "— the kernel travels with the enforcement layer; without it no integrity gate can "
        "verify anything, so every gated call is refused." % ", ".join(tried)
    )


def _import_kernel_state(init):
    """Import `kernel.state` eagerly (every caller needs it) with an accurate failure message."""
    try:
        importlib.import_module(KERNEL_PKG + ".state")
    except ImportError as exc:
        raise KernelUnavailable(
            "found the kernel at %s but a dependency is missing (%s: %s). Remedy: the kernel "
            "needs PyYAML — `pip install pyyaml` in the interpreter that runs the hooks "
            "(`python -c \"import yaml\"` reproduces it)." % (init, type(exc).__name__, exc)
        ) from None
    except Exception as exc:
        raise KernelUnavailable(
            "found the kernel at %s but importing it failed (%s: %s) — the kernel itself is "
            "damaged. Remedy: `git status` on the kit; a half-finished kit update or a partial "
            "checkout is the usual cause, and re-running the scaffold restores it."
            % (init, type(exc).__name__, exc)
        ) from None


def kernel_module(name, repo_root=None):
    """Import one kernel submodule on demand (`dispatch`, `approvals`, `report`, ...).

    Kept lazy per module so a gate pays only for what it actually needs — the whole point of the
    latency note above is that the import cost is bounded and known, not that it is free.
    """
    import_kernel(repo_root)
    return importlib.import_module("%s.%s" % (KERNEL_PKG, name))


def state_dir(repo_root=None):
    """Absolute path of the canonical state directory (may not exist yet)."""
    return os.path.join(repo_root or find_repo_root(), STATE_DIRNAME)


def state_is_empty(repo_root=None):
    """True when there is no canonical state at all — the ONE precondition for bootstrap.

    Defined as "no canonical artifact anywhere", not as a list of allowed top-level names:
    everything the kernel writes ALONGSIDE the state carries a non-canonical extension
    (`.kernel.lock` and its `.stale-*` remnants, `.audit/*.jsonl`) and `generated/**` is
    regenerable by definition. Name-listing was tried first and was wrong twice over — it
    excluded a `.lock` the kernel never creates, and an empty typed directory tree left by the
    scaffold would have closed the installer's own gate before it wrote its first item.

    CANONICAL_SUFFIXES covers more than the YAML items on purpose: spec II.2 puts frozen design
    revisions (`design/revisions/DSN-0001.html`) and the draw.io ARC/WFR artifacts in the state
    too, and a project whose YAML items were archived but whose approved revisions remain is
    emphatically not a greenfield install.

    `staging/**` is COUNTED, although spec II.4 calls it explicitly non-canonical. Deliberate:
    the question here is not "is this canonical?" but "is this a greenfield repo?", and a
    proposal in staging proves work in flight. The error direction is the safe one — it can only
    ever close the bootstrap window, never open it.
    """
    root = state_dir(repo_root)
    if not os.path.isdir(root):
        return True
    generated = os.path.join(root, "generated")
    for directory, _subdirs, files in os.walk(root):
        if directory == generated or directory.startswith(generated + os.sep):
            continue
        if any(name.lower().endswith(CANONICAL_SUFFIXES) for name in files):
            return False
    return True


def bootstrap_active(repo_root=None):
    """True only during an explicit, still-valid installer/migration bootstrap (spec II.4).

    Spec: "aktivierbar nur über den expliziten Installer-/Migrationsbefehl mit Lock, leerem
    Zielzustand und Userbestätigung" — deliberately NOT a config flag the lead could set to
    unblock itself. Enforced here:
      * the target state must be empty (the real teeth: once one canonical item exists, no
        marker re-opens the gate),
      * the marker must record an installer run and an explicit user confirmation,
      * its TTL is capped at BOOTSTRAP_MAX_TTL, so a marker cannot grant standing permission,
      * `.claude/kit_state.json` is on guard_harness_selfmod's blocked list, so an agent cannot
        write the marker with an ordinary Edit/Write in the first place.
    """
    repo_root = repo_root or find_repo_root()
    if not state_is_empty(repo_root):
        return False
    try:
        with open(os.path.join(repo_root, ".claude", KIT_STATE_FILE), encoding="utf-8") as fh:
            marker = (json.load(fh) or {}).get("bootstrap")
    except Exception:
        return False
    if not isinstance(marker, dict):
        return False  # a truthy non-dict must not raise its way past the caller's error handling
    if marker.get("user_confirmed") is not True:
        return False
    if not str(marker.get("installer_run") or "").strip():
        return False
    try:
        expires = float(marker.get("expires_at_epoch", 0))
    except (TypeError, ValueError):
        return False
    now = time.time()
    return now < expires <= now + BOOTSTRAP_MAX_TTL


class BundleTrust(object):
    """What this project's own record says about the enforcement bundle that is installed NOW.

    `withdrawn` is the only field a caller acts on, and what it means is stated as a PROPERTY
    rather than as a state name: the project recorded which bundle it trusts, and the bundle
    running today is not that one. `hooks_trust_required` is merely the name `kit_trust_state`
    gives the same finding at session start; deciding on the measurement instead of on the name
    means the finding also holds for a bundle changed DURING a session, which that hook cannot
    see, and does not depend on a comfort hook having run.

    WHAT IS DELIBERATELY NOT THIS CLASS. `restart_required` is what `write_kit_state` leaves
    behind after every scaffold — the honest verdict that hooks were installed but are not yet
    running — and only the SessionStart comfort hook clears it. It carries the SAME hash as the
    installed bundle, so it never reaches `withdrawn` here, and that is the point: a project whose
    SessionStart never ran (or whose comfort hook somebody killed) must still be able to delegate,
    or one fail-open hook's absence would silently become a total stop.

    `reason` is None when trust holds, and otherwise says which of the two findings it is.
    """

    def __init__(self, withdrawn, reason=None):
        self.withdrawn = withdrawn
        self.reason = reason


def bundle_trust(repo_root=None):
    """Measure the installed enforcement bundle against the hash this project recorded.

    THE UNMEASURABLE CASE BLOCKS. A recorded hash plus a bundle whose hash cannot be computed
    (an unreadable file, a broken link under `.claude/hooks`) is an integrity gate that cannot
    verify what it is standing on — spec II.4's fail-closed direction, and the same verdict
    `write_kit_state` reaches for the same input.

    THE UNRECORDED CASE DOES NOT BLOCK, and this is a hole with a name rather than an oversight:
    a project with no `kit_state.json`, or one whose record carries no `hook_bundle_hash`, has
    never had a trust measurement made about it — there is nothing this function could compare,
    and refusing there would strand every project scaffolded before the recorder existed.
    `python scripts/harness.py doctor` is what reports `hook_trust` as unverified for such a
    project.

    THE COST IS STATED WHERE IT IS PAID, and this paragraph has been wrong twice — first in both
    directions ("no gate sees a shell `rm`"), then too NARROW, by saying the record could be
    deleted when it can equally be REWRITTEN. Measured 2026-08-01 as real hook processes in all
    three kits: `rm`, `rm -f`, `del`, `Remove-Item`, an inline
    `python -c "os.remove('.claude/kit_state.json')"` and `cd .claude && rm kit_state.json` are
    every one of them refused rc 2 by `gate_write_scope`, on top of `guard_harness_selfmod`
    refusing the Edit/Write path. What gets through is the COMPLEMENT, and that is a class rather
    than a verb: a shell command whose COMMAND LINE does not NAME the enforcement layer —
    `find . -name kit_state.json -delete`, a glob (`mv ./.cla*/kit_state.json /tmp/`), `git clean
    -xfd`, or any script the agent runs.

    AND THE WORSE HALF OF THAT CLASS IS RE-BLESSING, NOT DELETING. Measured: append one byte to
    `.claude/hooks/_audit.py` and the next spawn is refused with the bundle reason; then rewrite
    `kit_state.json` with the hash OF THE TAMPERED BUNDLE — through the same unnamed command line
    — and the refusal is gone. A re-blessed bundle is indistinguishable from a legitimate one
    here, because the comparison is then between two values the guarded party chose. `write_kit_
    state` refuses exactly this (it re-copies the kit and compares), but nothing forces a role to
    go through it. `kit_state.json` cannot move into the hashed set — it CONTAINS that set's hash
    — so this is a limit of the record, not something a better location fixes. It is the reason
    `hook_trust` is a doctor CAPABILITY rather than a proof.

    WHAT IT SPENDS, because this now sits on a BLOCKING path and a cost nobody measured is how a
    gate gets disarmed by a timeout: 6.0 ms per call over a real installed bundle (`.claude/hooks`
    + `.claude/kernel`, 20 runs, 2026-08-01). The walk covers what EXISTS under those two
    subtrees, not what the kit shipped — an earlier line here claimed the latter and was simply
    false. Measured with a 512 MB stranger dropped in: 0.54 s, and past what fits in memory
    `_hash_subtrees` raises, which lands in the `actual is None` branch above, i.e. fail-closed.
    So the unbounded direction ends in a REFUSAL rather than in an answer, which is why no cap is
    needed here while `guard_guidelines`, whose oversize case must not block every write, carries
    two.
    """
    repo_root = repo_root or find_repo_root()
    claude_dir = os.path.join(repo_root, ".claude")
    try:
        with open(os.path.join(claude_dir, KIT_STATE_FILE), encoding="utf-8-sig") as fh:
            record = json.load(fh)
        recorded = (record or {}).get("hook_bundle_hash") if isinstance(record, dict) else None
    except Exception:
        recorded = None
    if not recorded:
        return BundleTrust(False)
    try:
        actual = kernel_module("hashing", repo_root).hook_bundle_hash(claude_dir)
    except Exception:
        actual = None
    if actual is None:
        return BundleTrust(True, "the installed enforcement bundle could not be measured at all, "
                                 "so it cannot be compared with the one this project trusts")
    if actual != recorded:
        return BundleTrust(True, "the installed enforcement bundle (%s) is not the one this "
                                 "project trusts (%s)" % (str(actual)[:12], str(recorded)[:12]))
    return BundleTrust(False)


def open_state(repo_root=None):
    """The ProjectState for this repo. Raises KernelUnavailable when there is no state dir."""
    repo_root = repo_root or find_repo_root()
    kernel = import_kernel(repo_root)
    root = state_dir(repo_root)
    if not os.path.isdir(root):
        raise KernelUnavailable(
            "no canonical state at %s — refusing to authorise anything against a state that "
            "does not exist (spec II.4 fail-closed). Remedy: initialise the project state via "
            "the installer/scaffold, which is the only path that may run with an empty state."
            % root
        )
    return kernel.state.ProjectState(root)


# The protocol a WALL GATE offers: a module-level `unfilled_documents(root)` returning
# {state-relative path: why}, derived from the same condition the gate refuses on. It is a
# protocol and not a list of gate names on purpose -- `kernel.layout.gated_documents` says WHICH
# hook stands in front of WHICH document, and this asks whichever hook that turns out to be. A
# gate that grows a new wall is answered here the day it ships; one that offers no such function
# is simply not asked, and its document is reported without a verdict.
WALL_VERDICT_ATTR = "unfilled_documents"


def unfilled_gated_documents(repo_root=None):
    """[(document, hook, why)] for every wall whose OWN gate says it is still the template.

    WHY THIS LIVES ON THE HOOK SIDE. The condition belongs to the gate -- it is the same code that
    refuses the push or the filing -- and only a process that is already a hook may import a gate
    module: importing one installs `_kernel`'s exit-2 excepthook and runs the gate's module-level
    `sys.path` surgery. `kernel.report.gated_documents` therefore reports the wall and its
    registration (parsed, never imported) and leaves the verdict to this function, which the
    SessionStart briefing calls.

    NEVER RAISES AND NEVER BLOCKS. Its caller is a comfort hook whose whole contract is that it
    cannot refuse a call: a wall the session was not told about costs a paragraph, a briefing hook
    that exits 2 costs the briefing. A gate that offers no verdict function, or raises while
    answering, is skipped rather than guessed at.
    """
    repo_root = repo_root or find_repo_root()
    try:
        layout = kernel_module("layout", repo_root)
        walls = layout.gated_documents(repo_root, state_dir(repo_root))
    except BaseException:  # noqa: BLE001 -- see the contract above
        return []
    out = []
    for document in sorted(walls):
        module_name = os.path.splitext(walls[document]["hook"])[0]
        try:
            # the hooks directory is on sys.path from this module's own import (top of file), so
            # the gate resolves as the sibling it is
            gate = importlib.import_module(module_name)
            ask = getattr(gate, WALL_VERDICT_ATTR, None)
            verdicts = ask(repo_root) if callable(ask) else None
        except BaseException:  # noqa: BLE001
            continue
        if isinstance(verdicts, dict) and document in verdicts:
            out.append((document, walls[document]["audit_name"], str(verdicts[document])))
    return out


def partial_write_routes(document, repo_root=None):
    """[(field, command)] a kernel COMMAND writes inside this kit document -- asked, never listed.

    THE STATE DIRECTORY IS PASSED with it, which is what makes the answer right for a writer that
    owns no single named file: `apply-proposal` writes any kit document it can COMPARE and refuses
    one it cannot (BUG-0071), a fact about the file and not about its name. A caller that cannot
    reach the kernel still names nothing.

    THE SAME DERIVATION `gate_write_scope._partial_writers` USES: `kernel.layout.partial_writers`,
    which asks the writing modules themselves. It is here because the SessionStart briefing and
    `kernel.report.doctor` both stated the OPPOSITE as a blanket fact, and a briefing that denies a
    route the harness HAS is BUG-0041's failure form for the next document. Measured 2026-08-21
    against a fresh office scaffold: the briefing did not mention `add-filing-rule` for
    `filing_plan.yaml` and doctor printed `kernel_writer: null` beside the same prose, one round
    after that command shipped.

    Empty on any failure, because `unfilled_gated_documents`' contract binds here too: the caller
    is a comfort hook that may not raise.
    """
    try:
        root = repo_root or find_repo_root()
        layout = kernel_module("layout", root)
        return [(entry["field"], entry["command"])
                for entry in layout.partial_writers(document, state_dir(root))]
    except BaseException:  # noqa: BLE001 -- see the contract above
        return []


def _route_clause(document, repo_root):
    """The ' — what CAN be written into it: …' half of a wall's sentence, or ''.

    Built per document from `partial_write_routes`, so a wall with no writer reads exactly as it
    did before and one with a writer stops being reported as a dead end. It no longer says "one
    PART of it": `apply-proposal` writes whatever a user-approved proposal adds, so the clause
    states the route and leaves what it covers to the route's own words.
    """
    routes = partial_write_routes(document, repo_root)
    if not routes:
        return ""
    return " — what CAN be written into it: %s" % ", ".join(
        "`python scripts/harness.py %s` writes `%s`, on a user-minted approval"
        % (command, field) for field, command in routes)


def gated_document_briefing(repo_root=None):
    """The SessionStart sentence about unfilled walls, or None -- ONE text, three kits.

    Written here rather than in `session_status`, which is kit-specific and exists three times: a
    sentence copied three times is a sentence that will differ three ways, and this one has to stay
    exact.

    EVERY CLAUSE IS DERIVED OR QUOTED, and the sentence claims nothing beyond them. That a
    registered gate reads the file and can refuse comes from `kernel.layout.gated_documents`; that
    it is still unfilled is the gate's own verdict, quoted verbatim rather than paraphrased; that no
    TOOL write reaches it is `is_project_document`; and what a COMMAND can write into it is
    `partial_write_routes`, per document -- which is the clause that used to be missing and is the
    one a role acts on. What the message does NOT say is that the write is PREVENTED --
    `gate_write_scope` refuses the tool routes and the constitution binds the shell one as policy,
    and neither fact is measured here. `doctor` is read-only and every role can run it; a message
    that named a route the session cannot take, or DENIED one it has, is the failure this text has
    now been rewritten for twice.
    """
    walls = unfilled_gated_documents(repo_root)
    if not walls:
        return None
    listed = "; ".join("%s (%s: %s)%s" % (document, hook, why,
                                          _route_clause(document, repo_root))
                       for document, hook, why in walls)
    return (
        "UNFILLED PROJECT DOCUMENT%s — a WALL, not a to-do: %s. A registered gate reads each of "
        "those files and refuses work over its content, and no TOOL write reaches one — the kernel "
        "has no path builder that can name it. What a COMMAND can write into a file is named "
        "beside it above, and that command asks the user first; a file with no such clause is the "
        "USER's to fill, in an editor outside this session. Say so in your FIRST paragraph, name "
        "the file and what it needs, do not retry the refused operation, and do not start work "
        "that depends on the file. `python scripts/harness.py doctor` lists these under "
        "`gated_documents`." % ("S" if len(walls) > 1 else "", listed))


def kit_update_verdict(repo_root, kit):
    """(verdict, installed version, staged version, why) for the session briefing's kit paragraph.

    THE DECISION IS THE KERNEL'S. `kernel.kitupdate.relation` is what `update-kit` refuses on, so a
    briefing that ordered the two stamps itself could OFFER an update that command then REFUSES --
    which is why that ordering rule left `_compat` (FR-0006). What this adds is the mapping onto the
    four sentences a briefing has, and it lives here rather than in `session_status` for the reason
    `gated_document_briefing` does: one derivation, three kits, and the WORDING stays per kit.

    A KERNEL THAT CANNOT BE REACHED IS AN ANSWER HERE, NOT SILENCE, and that is measured: with the
    module unreachable the whole paragraph vanished, so the one sentence that tells a lead a newer
    release exists at all would be missing in exactly the project whose kernel is damaged -- the
    project that most needs the update. `unclear` is what such a project gets, with the reason, and
    `tools/test_kitupdate.py::test_a_briefing_whose_kernel_is_unreachable_still_reports_the_kit_
    comparison` runs the hook without one.

    Verdicts: `unclear` / `downgrade` / `content` / `update` / `pinned` / `none` (nothing to say).
    """
    try:
        kitupdate = kernel_module("kitupdate", repo_root)
        answer = kitupdate.relation(repo_root, kit)
        pin = kitupdate.pin_in_force(repo_root)
    except BaseException as exc:  # noqa: BLE001 -- see above: no kernel is an answer, not silence
        return ("unclear", "unreadable", "unreadable",
                "the state kernel that decides which is newer could not be reached (%s)" % exc)
    sentences = {kitupdate.UNREADABLE: "unclear", kitupdate.UNREADABLE_ORDER: "unclear",
                 kitupdate.DOWNGRADE: "downgrade", kitupdate.CONTENT_MISMATCH: "content",
                 kitupdate.UPDATE_AVAILABLE: "update"}
    verdict = sentences.get(answer["verdict"], "none")
    why = "at least one of the two stamps carries no readable version"
    # THE PIN CHANGES EXACTLY ONE SENTENCE, and picking which one is why this lives beside the
    # verdict rather than in a kit's wording. Three of the four sentences already say "do NOT
    # install"; only `update` ASKS the user for an OK, and on a pinned project that question is one
    # nobody can answer usefully -- measured 2026-09-01 (TSK-0101): a pinned project was told "On
    # their OK you install it YOURSELF", the user said yes, the approval was minted, and only
    # `update-kit` then refused. The offer is not silenced (that is BUG-0078's marker class); it is
    # replaced by the same fact one step earlier. `H87` carries the measurement.
    if verdict == "update" and pin is not None:
        verdict = "pinned"
        why = "%s says:\n%s" % (kitupdate.PIN_FILE.replace(os.sep, "/"), pin["text"])
    return (verdict,
            answer["from"].get("version") or "no version stamp",
            answer["to"].get("version") or "unreadable",
            why)


def pending_merge_backlog(repo_root):
    """{suffix: [entries that still differ]} for the kit-update merge backlog, or None.

    THE DECISION IS THE KERNEL'S (`kitupdate.outstanding_pending`), for the reason
    `kit_update_verdict` gives above and one more that is specific to this list: the report
    `update-kit` prints reads the same function, so the command's count and the briefing's nag
    cannot disagree about how much work is left.

    None means the question could not be ASKED -- no kernel to reach. The caller then nags on the
    file as WRITTEN, which is the behaviour that existed before this reader and is the fail-closed
    direction: a project whose kernel is damaged keeps its backlog rather than losing it.
    """
    try:
        kitupdate = kernel_module("kitupdate", repo_root)
        return kitupdate.outstanding_pending(repo_root)
    except BaseException:  # noqa: BLE001 -- no kernel is an answer, not silence (see above)
        return None


def unverified_delivery_briefing(repo_root=None):
    """The SessionStart sentence about work booked as finished that nothing measured, or None.

    ONE text, three kits, for the reason `gated_document_briefing` gives above. The DECISION is
    `kernel.report.accepted_without_a_verdict`, which is also what the state validator turns into
    findings -- so the briefing and `validate` cannot answer this differently.

    WHY A SESSION START IS THE PLACE. BUG-0060: across two dev pilots the evidence drawer stayed
    empty, and nothing anywhere said so -- the only two moments that ask for a verdict lie behind
    a merge and behind the confirming status, and neither run reached either. A validator finding
    alone would repeat that: the session brief carries the COUNT of warnings, not their text. This
    is the surface a lead reads whether or not it asks.

    NEVER RAISES AND NEVER BLOCKS -- same contract as the two briefings around it.
    """
    repo_root = repo_root or find_repo_root()
    try:
        report = kernel_module("report", repo_root)
        state = open_state(repo_root)
        with state.lock:
            owed = report.accepted_without_a_verdict(state)
    except BaseException:  # noqa: BLE001 -- see the contract above
        return None
    if not owed:
        return None
    listed = "; ".join("%s owes %s" % (task_id, ", ".join(kinds))
                       for task_id, kinds in sorted(owed.items()))
    return (
        "WORK BOOKED AS FINISHED THAT NOTHING MEASURED: %s. Those tasks stand at the status that "
        "means the work is done and not yet confirmed, and the project holds no passing Evidence "
        "of the named kinds for them. This is a DEBT, not a refusal -- it blocks nothing here; the "
        "merge gate asks the same question for itself, at the merge. What clears it is the quality "
        "role's run recorded through `python scripts/harness.py evidence`. Say it in your first "
        "paragraph if the user is about to be told the work is done." % listed)


def filing_coverage_briefing(repo_root=None):
    """The SessionStart sentence about paper the business has and the plan does not, or None.

    ONE text, three kits, for the reason `gated_document_briefing` gives above; it produces
    nothing in a project whose profile carries no `document_sources`, which is every project of a
    kit that has no such document. The DECISION is `kernel.filing.uncovered_document_sources` --
    see it for the derivation and for why an unwalked interview is not reported as a broken plan.

    WHY A SESSION START (BUG-0061): the plan is written before the kit is installed, by a session
    that is over by the time anyone could notice a gap, and the gap only shows itself as a refused
    filing weeks later. In pilot 4 the owner found four of them herself, one document at a time.

    NEVER RAISES AND NEVER BLOCKS -- same contract as the briefings around it.
    """
    repo_root = repo_root or find_repo_root()
    try:
        filing = kernel_module("filing", repo_root)
        uncovered = filing.uncovered_document_sources(open_state(repo_root))
    except BaseException:  # noqa: BLE001 -- see the contract above
        return None
    if not uncovered:
        return None
    listed = "; ".join("%s (no rule for %s)" % (what, ", ".join(types))
                       for what, types in uncovered)
    return (
        "PAPER THIS BUSINESS HAS AND THE FILING PLAN DOES NOT: %s. Those came from the owner's own "
        "answers in `business_profile.yaml`; a document of one of those kinds reaches `gate_filing` "
        "and stops there, unfiled, because no rule covers it. The way to close one is the ordinary "
        "one: propose the rule to the user and let them sign it -- `python scripts/harness.py "
        "add-filing-rule`. Name this in your first paragraph rather than waiting for the document."
        % listed)


def orphaned_dispatch_briefing(repo_root=None, session_id=None):
    """Sweep the dispatches no child of THIS session can be behind, and say what was measured.

    DEC-0044 half (1), and the reason it runs HERE: a session start is the only moment at which
    "the session that asked for this child is not the session asking now" is decidable at all, and
    the session id arrives in this event's payload. The kernel does the deciding
    (`dispatch.sweep_orphaned_dispatches`); this composes the sentence, once for three kits, for the
    same reason `gated_document_briefing` is not written in `session_status`.

    NEVER RAISES AND NEVER BLOCKS -- same contract as the wall briefing above: its caller is a
    comfort hook. Without a session id nothing is swept: every dispatch would then look foreign, and
    sweeping on a missing field is the one direction that destroys work rather than reporting it.

    WHAT THE TEXT MAY CLAIM. Only what was measured -- which task stood in which status, which
    session asked for it, and where it was moved to. It must NOT claim the other session is over
    (nothing here can see a process), and it must not claim a checkpoint is good work; the verdict
    sentence comes from `checkpoints.Verdict.summary`, which is scoped for that reason.
    """
    repo_root = repo_root or find_repo_root()
    if not str(session_id or "").strip():
        return None
    try:
        state = open_state(repo_root)
        dispatch = kernel_module("dispatch", repo_root)
        swept, left = dispatch.sweep_orphaned_dispatches(state, str(session_id))
    except BaseException:  # noqa: BLE001 -- see the contract above
        return None
    if not swept and not left:
        return None
    parts = []
    if swept:
        parts.append(
            "ORPHANED DISPATCH%s SWEPT AT SESSION START -- measured: %s. A subagent is a child of "
            "the session that asked for it and cannot outlive it, so no child of these can be "
            "running here; the kernel moved each one along its own automaton and dropped its lease. "
            "WHAT THAT COVERS is exactly the dispatches that RECORDED an asking session and named "
            "another one -- a dispatch that recorded none is reported below and left standing, so "
            "do not read this as \"nothing claims to run any more\". NOT measured either: whether "
            "the other session is over -- a second session open in this project right now would "
            "look exactly the same from here. A task in FAILED goes back to work only on the "
            "USER's approved retry (`python scripts/harness.py transition <TSK-ID> READY "
            "--approved-retry`), so ask before you re-order anything, and say all of this in your "
            "FIRST paragraph."
            % ("ES" if len(swept) > 1 else "",
               "; ".join("%s was %s under a dispatch session %s asked for, now %s"
                         % (row["task_id"], row["status"], row["asked_by"], row["moved_to"])
                         for row in swept)))
        parts.append(_checkpoint_briefing(repo_root, [row["task_id"] for row in swept]))
    if left:
        parts.append(
            "DISPATCH%s LEFT ALONE by that sweep, reported rather than acted on: %s. Nothing was "
            "changed about %s; `python scripts/harness.py sweep-leases` and the lease TTL remain "
            "the backstop."
            % ("ES" if len(left) > 1 else "",
               "; ".join("%s (%s) -- %s" % (row["task_id"], row["status"], row["why"])
                         for row in left),
               "them" if len(left) > 1 else "it"))
    return " ".join(part for part in parts if part)


def _checkpoint_briefing(repo_root, task_ids):
    """The per-task adoption verdicts for the swept tasks, or "" when none can be produced.

    Separate from the sweep sentence because it answers the other half of DEC-0044: what the
    successor may pick up. Each line is the kernel's own `Verdict.summary`, quoted rather than
    paraphrased -- a paraphrase of a scoped sentence is how the scope gets lost.
    """
    try:
        state = open_state(repo_root)
        checkpoints = kernel_module("checkpoints", repo_root)
        return " ".join(checkpoints.verify(state, task_id).summary for task_id in task_ids)
    except BaseException:  # noqa: BLE001
        return ""


_PAYLOAD_CACHE = []

# WHAT A COMMAND LINE LOSES BEFORE ITS SHELL PARSES IT — the one thing that makes a gate's whole
# reading worthless, because the text it judges is then not the text that runs. Measured 2026-08-24
# by having each gated shell print a string back and comparing the BYTES, over every C0 control
# character, DEL, U+0085, U+2028 and U+2029: exactly ONE character of that class does not arrive,
# the CARRIAGE RETURN on the `Bash` rail. PowerShell keeps all of them. A CR that is part of a CRLF
# is not in this class of trouble: it is dropped and the LF that follows it stays the break it was,
# so the gate's reading and the shell's agree — measured, `A<CRLF>B` arrives as `A<LF>B`.
#
# WHO DELETES IT IS THE SHELL'S OWN INPUT READER, not the tool — and this line used to say the
# opposite, which hid a PLATFORM BINDING. Measured with no tool involved at all: `bash -c <line>`,
# the line on stdin with and without `-s`, and a script FILE all print `AB`, while a CR that bash
# BUILDS itself survives as `A<CR>B`. That was msys bash 5.2.37 on Windows, which is the only bash
# this host has; the scaffold also installs on macOS and Linux, where a POSIX bash keeps a bare CR
# as an ordinary character of a word. THE REFUSAL IS RIGHT ON BOTH, for two different reasons, and
# only the first is measured here: where the CR is deleted, two words WELD (`project_mem<CR>ory/...`
# is one canonical path to that bash and two harmless words to this reader — rc 0 through the whole
# registered chain, rc 0 from bash, the item overwritten); where it is kept, this reader still ends
# a statement at it and the shell does not, so the two disagree the other way round. On such a
# platform the entry is an OVER-refusal rather than a closed weld, and the key is the TOOL because
# that is what says which shell receives the line.
#
# WHY THIS IS A REFUSAL AND NOT A REPAIR. Deleting the CR here would give this reader that bash's
# view and lose PowerShell's, and it cannot be had both ways in one text, because a weld crosses a
# WORD boundary — the second reading would be a second tokenisation of the whole line, which is a
# change in the gates and not in this door. A bare CR in a command line is also not a thing a person
# writes: it is not how any editor spells a line end. So the honest answer is that the call could
# not be inspected — the same door, one step further in, that `payload` already refuses an
# unreadable payload through.
_EATEN_IN_FLIGHT = {"Bash": re.compile(r"\r(?!\n)")}


def payload(hook, event="PreToolUse"):
    """Bounded, normalized hook payload for an integrity gate.

    `hook` is required and comes first: with an optional name the natural positional call
    `payload("gate_dispatch")` would bind the hook NAME to `event` and silently lose the gate's
    identity. Overflow blocks inside `_compat.load()`; see STDIN_LIMIT there.

    Two properties beyond a plain `_compat.load()`, both for the same reason — every gate in this
    repo is shaped `if data.get("tool_name") != X: sys.exit(0)`, which turns an empty dict into
    ALLOW:

    * an UNREADABLE payload blocks. `_compat.load()` returns `{}` for unparseable stdin, and
      "could not be inspected" must not read as "permitted" (spec II.4: "leerer, beschädigter
      oder unbekannter Zustand blockiert"). This is the same door as the overflow case, one step
      further in.
    * the result is MEMOISED. stdin can only be drained once, so a gate that grows a helper
      calling `payload()` a second time — and a dispatch gate with a header to parse, a task to
      resolve and a scope to check is exactly that shape — would otherwise get `{}` from the
      second read and decide on it.
    """
    if not _PAYLOAD_CACHE:
        _PAYLOAD_CACHE.append(_compat.load())
    data = _PAYLOAD_CACHE[0]
    if not data:
        block(hook,
              "the hook payload could not be read or parsed, so this call could not be "
              "inspected — refused rather than waved through (spec II.4 fail-closed).",
              event=event,
              remedy="run `python scripts/harness.py doctor`; a provider sending a payload this hook cannot parse "
                     "is a harness defect worth reporting, not something to work around.")
    eaten = _eaten_in_flight(data)
    if eaten:
        block(hook,
              "this command line carries a character its shell will never see (%s), so what this "
              "hook can read is not what would run — refused rather than waved through "
              "(spec II.4 fail-closed)." % eaten,
              event=event,
              remedy="write the line without that character. It is not how any editor spells a "
                     "line end; a command in several steps is spelled with a real newline or with "
                     "`;`, `&&`, `||`.")
    return data


def _eaten_in_flight(data):
    """How the character this call's tool deletes on the way to its shell reads, or "".

    A property of the TOOL, not of the text: `_EATEN_IN_FLIGHT` carries which characters those are
    and the measurement behind them. Answers "" for every payload without a shell command, so an
    `Edit` or a spawn passes through untouched.
    """
    rx = _EATEN_IN_FLIGHT.get(_compat.gated_shell(data.get("tool_name")))
    if rx is None:
        return ""
    match = rx.search(str((data.get("tool_input") or {}).get("command") or ""))
    return "" if match is None else "U+%04X" % ord(match.group()[0])


def record_note(hook, message):
    """Audit something WITHOUT claiming to have prevented it.

    For the events whose exit code cannot block (PostToolUse, PostToolUseFailure, SubagentStart —
    hooks reference, exit-code-2 table). A gate on those events protects state by refusing to
    MUTATE it, and this is how that refusal reaches the audit trail. Using `block()` there would
    exit 2 and look like enforcement in the log while the action went through regardless.
    """
    with contextlib.suppress(BaseException):
        _audit.record_event(hook, "note", message)


# Events whose exit code 2 actually blocks (hooks reference, "exit code 2 behavior" table). The
# rest only surface stderr, so a refusal on them is a REPORT, and the audit line must say so —
# otherwise the log claims prevention that never happened, which is the failure V2 exists to end.
BLOCKING_EVENTS = frozenset((
    "PreToolUse", "PermissionRequest", "UserPromptSubmit", "UserPromptExpansion", "Stop",
    "SubagentStop", "TeammateIdle", "TaskCreated", "TaskCompleted", "ConfigChange",
    "PostToolBatch", "PreCompact", "Elicitation", "ElicitationResult", "WorktreeCreate",
))


def block(hook, message, event="PreToolUse", remedy=None):
    """Refuse the call: audit it, then use this event's provider-specific blocking contract."""
    text = "[team-kit %s] %s" % (hook, message)
    if remedy:
        text += "\nRemedy: %s" % remedy
    if not text.endswith("\n"):
        text += "\n"
    try:
        # labelled from the EVENT, not from the call site: on a non-blocking event this exits 2 and
        # the action still proceeds, so recording it as "block" would put a prevention in the log
        # that did not occur
        _audit.record_event(hook, "block" if event in BLOCKING_EVENTS else "refused-nonblocking",
                            message)
        _compat.stop(text, event)
    except SystemExit:
        raise
    except BaseException:
        # last resort: a block that cannot be written must still BE a block. os._exit skips
        # flushing, so stderr is flushed by hand first.
        with contextlib.suppress(BaseException):
            sys.stderr.write(text)
            sys.stderr.flush()
        os._exit(2)


@contextlib.contextmanager
def fail_closed(hook, event="PreToolUse"):
    """Integrity-gate body guard: ANY internal error becomes a block, never a silent pass.

    Catches BaseException, not Exception: KeyboardInterrupt (a Ctrl-C, a cancelled call) and
    MemoryError are exactly the "everything is already going wrong" moments where an unblocked
    call is worst, and they exit 1 or 3221225786 — both of which Claude Code reads as ALLOW.
    SystemExit passes through untouched; that is how allow (0) and block (2) are signalled.
    """
    try:
        yield
    except SystemExit:
        raise
    except BaseException as exc:
        # NEGATIVE limit: the INNERMOST frames. A positive limit keeps the outermost ones, where
        # frame 1 is always this contextmanager's `yield` — the line that actually failed would
        # be the first thing dropped, which is not a diagnosis.
        detail = traceback.format_exc(limit=-3).strip().replace("\n", " | ")
        block(hook,
              "internal error (%s: %s) — refused rather than passed, because a crashing hook "
              "would otherwise let the call through (spec II.4 fail-closed).\nDiagnosis: %s"
              % (type(exc).__name__, exc, detail),
              event=event,
              remedy="run `python scripts/harness.py doctor` for the state view; if the kernel or its state is "
                     "damaged, the doctor output names the file to restore.")


# The literal preamble every V2 gate must open with (see the module docstring for why). Kept
# here as data so the test that enforces it and the gates that carry it cannot drift apart.
GATE_PREAMBLE = '''import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import _kernel
except BaseException as exc:  # noqa: BLE001 — a hook that cannot load must not mean "allow"
    sys.stderr.write("[team-kit hook] refused: could not load hook helpers (%r). Remedy: run "
                     "`python scripts/harness.py doctor`; a partial checkout or half-finished kit update is the "
                     "usual cause.\\n" % (exc,))
    sys.exit(2)
'''


# -- the window the registration gives a gate, and the budget it may spend inside it -------------
#
# WHAT IS LEFT OF THE CONSTRUCTION HERE, and where the rest went (BUG-0153/H61): `_compat` holds
# it now. This module is imported by 10 of 27 shipped dev hooks, 14 of 27 office and 9 of 24
# research (measured 2026-09-12), while `_compat` is imported by all of them -- so a bound that
# lives here is a bound the other 45 hooks do not have, which is what H61 was. What stays is the
# DELIVERY: `block` writes an audit record and speaks the refusal contract of the event this gate
# was registered on, and `_compat.stop` can do neither, because at the moment the deadline is armed
# no payload has been read and the event is not known. The sentences and the numbers are
# `_compat`'s, so one rule does not grow two vocabularies.


def start_the_deadline(hook, event="PreToolUse"):
    """Arm the deadline for this gate, with this event's refusal in front of `_compat.stop`.

    Idempotent through `_compat`: one process arms once, whether it got here through `run_gate` or
    through the payload funnel every hook passes.
    """
    _compat.start_the_deadline(
        hook + ".py",
        refuse=lambda message, remedy: block(hook, message, event=event, remedy=remedy))


def run_gate(hook, main, event="PreToolUse"):
    """Entry point for an integrity gate: `_kernel.run_gate("gate_x", main)`.

    Everything the gate does after its preamble — module-level code included, via the excepthook
    — is covered. See GATE_PREAMBLE for the one statement that has to defend itself.

    TAKING TOO LONG IS SUCH A DEFECT TOO, and it is the one that reads as an allow without any exit
    code at all: `start_the_deadline` runs beside the decision and ends the process with the refusal
    code when the registration's window is about to close.
    """
    start_the_deadline(hook, event)
    with fail_closed(hook, event):
        main()
    sys.exit(0)


def reset_payload():
    """Forget the memoised payload (see `payload`).

    The companion to `disarm()`, and for the same constituency: hook processes are one-shot, so
    the memo is invisible to them, but an in-process consumer — a test, a long-lived CLI — would
    otherwise be handed the FIRST payload it ever read for the rest of its life.

    There are TWO memos of one payload since `_gate.py` learned to run a chain (`_compat` now
    remembers the raw stdin so the second gate of a chain reads the same bytes as the first), and
    forgetting one of them would hand a caller the previous payload through the other. So this
    forgets both, and stays the ONE thing to call.
    """
    del _PAYLOAD_CACHE[:]
    _compat.forget_stdin()


def disarm():
    """Restore the interpreter's normal excepthook.

    For the non-hook consumers of this bridge (a CLI, the dashboard generator, migration
    tooling): armed, an ordinary ValueError would be reported as "the hook itself failed to run"
    and exit via os._exit(2), skipping atexit handlers and buffered-stdout flushes. Arming stays
    the IMPORT-TIME default because the alternative — arming inside run_gate() — would leave a
    gate's own module-level code uncovered, and that is the more dangerous of the two mistakes.
    """
    sys.excepthook = sys.__excepthook__


def _install_excepthook():
    """Turn ANY escaping exception into exit 2, not the default exit 1 (= allow).

    Covers what a context manager structurally cannot: exceptions raised at module scope before
    the gate body runs. It does NOT cover a failure of `import _kernel` itself — see
    GATE_PREAMBLE, which is the part of the answer that cannot live in this file.
    """
    def _hook(exc_type, exc, tb):
        detail = "".join(traceback.format_exception(exc_type, exc, tb, limit=-3))
        with contextlib.suppress(BaseException):
            sys.stderr.write(
                "[team-kit hook] refused: the hook itself failed to run (%s: %s) — a hook that "
                "cannot execute must not be read as permission (spec II.4 fail-closed).\n"
                "Diagnosis: %s\n"
                "Remedy: run `python scripts/harness.py doctor`; a partial checkout or a half-finished kit update "
                "is the usual cause.\n" % (exc_type.__name__, exc, detail.strip())
            )
            sys.stderr.flush()
        os._exit(2)

    sys.excepthook = _hook


_install_excepthook()
