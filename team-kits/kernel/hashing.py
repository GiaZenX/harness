"""Canonical subject-manifest hashing (HARNESS_V2_SPEC.md II.2 "Hash-Kanonisierung").

Canonical JSON -- sorted keys, NFC-normalized unicode, compact separators, explicit
hash_schema_version -- deliberately NOT yaml.safe_dump: PyYAML dump output is
version-dependent and un-normalized (the V1 proc_hash.py breakage class this
replaces; verified in the 2026-07-24 review).

Fail-closed: non-JSON types and NaN/Infinity raise instead of being coerced --
a hash over silently-mangled content would defeat approval invalidation.
"""
from __future__ import annotations

import hashlib
import importlib.machinery
import json
import os
import shutil
import unicodedata


HASH_SCHEMA_VERSION = 1

# WHAT THE ENFORCEMENT BUNDLE IS: the code that decides whether a call is allowed. Both of these
# subtrees, and only these — named rather than "everything under .claude", because that directory
# also holds files that change during ordinary use (`kit_state.json` is rewritten by the very hook
# that reads this hash) and a bundle whose hash changes every session cannot be trusted against.
#
# THAT IS A LIMIT ON THE HASH, NOT ON THE DEFINITION, and reading it as both left a hole for a
# round. `.claude` itself is a `sys.path` entry while the kernel is imported, so a `.claude/yaml.py`
# is code that decides whether a call is allowed by the definition above while sitting outside every
# subtree named here — hash unchanged, no stranger, executed by the SessionStart hook. What follows
# from "it cannot be hashed" is only that it cannot be hashed; `foreign_importables` scans it
# instead, which needs no stable hash to name an intruder.
BUNDLE_SUBTREES = ("hooks", "kernel")

# THE ONE QUESTION THIS MODULE ANSWERS: is the thing that is HASHED the thing that RUNS? Two
# enumerations follow from it, and they are deliberately different sets:
#
#   MEASURED (`_bundle_files`) — every file that EXISTS under an installed bundle subtree, with no
#   exclusion by name or extension. Anything less is an execution path outside the measurement.
#
#   SHIPPED (`_shipped_files`, `kit_hash`) — the files the SCAFFOLD copies out of the kit. This is
#   what an installation is compared against, so it must not demand files the scaffold does not
#   install.
#
# Bytecode is most of the distance between the two, and it used to be excluded from both. It cannot
# be excluded from the measured set: `.claude/hooks` is `sys.path[0]` in every gate process, so a
# bare `yaml.pyc` there is an importable SOURCELESS MODULE that owns the YAML parser of every gate,
# and a forged `__pycache__/state.cpython-313.pyc` replaces the executed code of a module whose
# source is hashed. Excluding it removed those two paths from the measurement rather than from the
# system. It is excluded from the shipped set instead, and that exclusion is made TRUE at both
# ends: `prune_transient` takes it out of what a scaffold installs, and the routes that start code
# inside a hashed tree each refuse to cache into it.
#
# THAT SECOND HALF IS A PROPERTY OF EVERY ROUTE, NOT OF THE INTERPRETER, and saying otherwise was
# wrong for a release. Stated as the class it is: ANY WAY OF STARTING AN INTERPRETER OVER A HASHED
# OR STAGED TREE has to refuse to cache into it, whether it says so as `python -B` on a command line
# or as `sys.dont_write_bytecode` in the module that gets started, and whether the tree is an
# installed `.claude` bundle, the `~/.claude/team-kits` staging or this repo's own `team-kits/`. A
# new route is a new obligation, and the obligation does not travel: a Codex command is REBUILT from
# a Claude registration, so the flag has to be written again there.
#
# WHICH routes exist is not written down here on purpose — a naming of three of them was incomplete
# on the day it shipped. It is answered by the section of `tools/test_hooks_v2.py` headed "is the
# thing that is HASHED the thing that RUNS?", whose checks derive their subjects from the
# registrations, the shipped tree and the repo's tools rather than from a list, so a route that is
# added without its refusal turns one of them red. A route that is missed is not a theoretical
# worry: until 2026-07-27 the documented CLI invocation carried no such flag, so running `doctor`
# against an installed project cached eleven `.pyc` into `.claude/kernel` and then reported, in the
# same run, that the bundle had changed since trust was recorded.
BYTECODE_SUFFIXES = (".pyc", ".pyo")
BYTECODE_DIR = "__pycache__"

# WHAT NEVER TRAVELS: directories a Python toolchain regenerates from the sources beside them.
# Bytecode caches are one of them; the linter and type-checker caches are the same kind of thing and
# were the same defect one directory deeper. `kit_hash` skipped all four, but the scaffolds' prune
# removed only the bytecode from what their recursive copy had brought along — so a
# `team-kits/kernel/.ruff_cache/evil.py` was installed into `.claude/kernel`, counted as SHIPPED
# (hence not a stranger), was blessed into the recorded bundle hash — and left `kit_hash`
# byte-identical, so no stamp had to be regenerated for it.
#
# Four spellings of this idea existed and only two agreed. There is now one: `is_transient` decides,
# `prune_transient` makes it true on disk where source becomes installation, and
# `transient_ignore_globs` does the same where the installer stages the tree.
TRANSIENT_DIRS = frozenset((BYTECODE_DIR, ".ruff_cache", ".mypy_cache", ".pytest_cache"))

# The stand-in a directory symlink contributes to the measurement instead of its contents — see
# `_bundle_files`. A constant because two independent readers have to produce it identically: the
# canonical enumeration below and the inline verifier `gen_provider_artifacts` embeds in every Codex
# hook command. That verifier cannot import this module while it RUNS, but the generator reads it
# while it WRITES, and interpolates this value (and `BUNDLE_SUBTREES`) into the source it emits — so
# what the copy repeats is the algorithm, and no constant is spelled out twice.
SYMLINK_MARKER = "<symlink>"


def is_transient(relative_posix_path: str) -> bool:
    """Is this a tool leftover rather than something a kit ships? (see TRANSIENT_DIRS)

    Asked of a RELATIVE path with `/` separators, because its consumers walk different trees — the
    kit hash walks a kit source, the shipped set walks an installed subtree, the prune walks an
    installation — and the answer must not depend on which. A leftover is a file with a bytecode
    suffix, or anything at any depth under a cache directory: `kernel/__pycache__/state.pyc` and
    `.ruff_cache/content/9f/02` are both regenerated from the sources beside them, and neither is
    ever copied on purpose.
    """
    parts = relative_posix_path.split("/")
    return (parts[-1].endswith(BYTECODE_SUFFIXES)
            or any(part in TRANSIENT_DIRS for part in parts))


def transient_ignore_globs():
    """The same rule as `shutil.copytree(ignore=...)` name globs, for a copy that creates none.

    `install.{sh,ps1}` stages `team-kits/` with `copytree`, which asks per directory ENTRY rather
    than per relative path, so the rule has to arrive as globs. Generated here so the installers
    carry no second list — theirs was the one of the four that happened to be complete, which is
    exactly why nobody noticed the other three were not.
    """
    return sorted(TRANSIENT_DIRS) + ["*" + suffix for suffix in BYTECODE_SUFFIXES]


def prune_transient(*roots):
    """Delete every tool leftover under each root — what makes the SHIPPED set true on disk.

    Both scaffolds call this on `.claude/hooks` and `.claude/kernel` after copying and BEFORE the
    trust recorder, so the hash that gets recorded and the tree the Codex binding is built from see
    the same, already-pruned bundle. Without it a scaffold installs whatever the staging happened to
    accumulate, and the two shapes that takes are not equally harmless: a `.pyc` is an importable
    module on `sys.path[0]` of every gate, while a cache directory is merely a file the recorder
    would bless although no kit stamp covers it.

    ONE IMPLEMENTATION FOR BOTH PLATFORMS, deliberately. The prune used to be four lines of shell
    written twice, and only the Windows copy was ever executed by a test; the POSIX one was read.
    Errors propagate: a bundle that could not be cleaned is one the recorder must not bless. A
    missing root is not an error — not every kit ships both subtrees.
    """
    for root in roots:
        if not os.path.isdir(root):
            continue
        for current, dirs, files in os.walk(root, topdown=True):
            for name in sorted(dirs):
                if name in TRANSIENT_DIRS:
                    path = os.path.join(current, name)
                    # a LINK named `__pycache__` is one directory entry, not a tree: rmtree refuses
                    # it, and following it would delete somebody else's files
                    if os.path.islink(path):
                        os.unlink(path)
                    else:
                        shutil.rmtree(path)
            dirs[:] = [name for name in dirs if name not in TRANSIENT_DIRS]
            for name in files:
                if name.endswith(BYTECODE_SUFFIXES):
                    os.remove(os.path.join(current, name))


def transient_entries(root: str):
    """The tool leftovers `prune_transient` would take out of `root`, as relative posix names.

    The same walk and the same two conditions, asked without deleting -- so a door that prunes can
    say what it removed, and a caller can tell "nothing to prune" from "pruned". A cache directory
    is one entry (its contents go with it), exactly as the prune treats it.
    """
    found = []
    if not os.path.isdir(root):
        return found
    for current, dirs, files in os.walk(root, topdown=True):
        for name in sorted(dirs):
            if name in TRANSIENT_DIRS:
                found.append(os.path.relpath(os.path.join(current, name), root).replace(os.sep, "/"))
        dirs[:] = [name for name in dirs if name not in TRANSIENT_DIRS]
        for name in sorted(files):
            if name.endswith(BYTECODE_SUFFIXES):
                found.append(os.path.relpath(os.path.join(current, name), root).replace(os.sep, "/"))
    return sorted(found)


def is_kit_dir(path: str) -> bool:
    """Is this `team-kits/` entry a KIT — a team of its own — rather than shared harness input?

    A kit ships `agents/`: that is what makes it a team rather than machinery, and it is true of a
    new kit from its first commit. Deciding it by the presence of a stamped VERSION instead would
    make a brand-new kit shared input for every OTHER kit until somebody stamped it, and the stamp
    would then move every hash a second time.

    `tools/bump_kit_version.discover_kits` is the same question and now asks it here, because the
    hash is where getting it wrong costs something: `kit_hash` derives the SHARED half from this
    predicate, so a directory both sides classify differently would be hashed into itself.
    """
    return os.path.isdir(os.path.join(path, "agents"))


def hook_bundle_hash(claude_dir: str):
    """SHA-256 over the installed enforcement bundle, or None when there is nothing to hash.

    THE definition, singular, deliberately. There were two — this one and a second in
    `gen_provider_artifacts` — over the same directory, and they disagreed: that one walked the
    tree and hashed every file, this one hashed only top-level `*.py`. Whichever answer
    `python scripts/harness.py doctor` gave, it could not be the value the Codex trust binding was built from, so
    `hook_trust` compared two things that were never the same measurement. Two implementations of
    one concept is the defect; picking the "better" one and leaving both would only have delayed
    it. Callers that need extra guarantees (a missing directory is fatal for the Codex artifact
    generator, a reparse point is a security question there) keep those checks around the call.

    SCOPE IS `.claude/hooks` PLUS `.claude/kernel`, not the hooks alone. The gates are thin; the
    decisions live in the kernel they import. Hashing only the hooks would have let `hook_trust`
    report `verified` over a bundle whose `report.validate_state` had been rewritten to return
    `[]` — a claim far wider than the measurement, which is the one thing the capability matrix
    exists to prevent. A subtree that is absent contributes nothing rather than failing: not every
    kit ships both, and "missing" is a different question from "changed".

    Properties that make this hash mean "the executable bundle", each load-bearing:
      * RECURSIVE and ALL FILE TYPES. A hook can read a `.json` config or a `.txt` allowlist next
        to it; a top-level-`*.py`-only hash calls an edited allowlist "unchanged".
      * the RELATIVE PATH participates — INCLUDING the subtree name, so moving a file between
        `hooks/` and `kernel/` changes the hash — NUL-separated from the content. Concatenating
        name+content with no delimiter lets two different bundles produce one byte stream.
      * NOTHING is skipped, bytecode least of all — see BYTECODE_SUFFIXES for why an exclusion
        here is an exclusion of an execution path.

    One copy of this algorithm survives on purpose: the inline verifier that
    `gen_provider_artifacts.hook_bundle_verifier_b64` embeds in the Codex hook command, which
    cannot import anything (its bytes are what Codex hashes). A copy that may not be deleted has to
    be PINNED, and the pin is only ever as wide as the tree it runs on: the test compares the two
    over `_adversarial_bundle`, so every disagreement that tree can express is covered and nothing
    else is. It grew a directory symlink on 2026-07-27 after the copy had silently kept the old
    symlink-blind walk through a whole release — the pin was green the entire time, because the
    fixture had no link in it.

    WHAT THE COPY MEASURES IS NOT PINNED THAT WAY AT ALL, because no fixture can contain a subtree
    that does not exist yet: `BUNDLE_SUBTREES` is interpolated into the generated verifier instead
    of written out inside it, and `test_the_inline_verifiers_scope_is_read_from_the_definition`
    extends this tuple to prove the generated code followed.
    """
    return _hash_subtrees([(name, os.path.join(claude_dir, name)) for name in BUNDLE_SUBTREES])


class BundleSourceMissing(ValueError):
    """A source tree to compare against is absent — see `modified_bundle_files`."""


def kit_hash(kit_dir: str) -> str:
    """SHA-256 over a kit's own files plus the shared harness inputs, CRLF-normalized.

    Lives in the KERNEL, which ships, because two things need it and only one of them used to be
    able to reach it: `tools/bump_kit_version.py` writes it into `<kit>/VERSION` as `content:`,
    and `write_kit_state.py` checks that the kit it is about to compare against is that kit. The
    tools directory does not travel to a staging, so a copy there would have been the third
    duplicated hash in this file's history.

    THE SUBJECT IS EVERYTHING A SCAFFOLD RUN READS OR INSTALLS — enumerated by `kit_hash_inputs`,
    which derives it rather than listing it, and `tools/validate.py` reads the same enumeration to
    demand that all of it is git-tracked. Reads AND installs, because the two are equally able to
    change an installation: `registry.yaml` and the scaffold scripts themselves are never copied
    into a project but decide what ends up there. Tool leftovers are in neither category
    (`is_transient`) — `prune_transient` takes them out of every install, so nothing ships them and
    nothing may demand them.

    CRLF normalization keeps the value identical across Windows and Linux checkouts of one commit.
    The kit's own top-level VERSION is excluded — it carries the result.
    """
    digest = hashlib.sha256()
    for name, path in kit_hash_inputs(kit_dir):
        # NUL-separated, exactly as in `hook_bundle_hash` and for the same reason: name and content
        # concatenated raw let two different trees produce one byte stream (a root file `ab` holding
        # `c` against a root file `a` holding `bc`), and the `@shared/` namespace only widened the
        # set of cuts that collide.
        digest.update(name.encode("utf-8") + b"\0")
        if path is not None:                  # a directory link contributes its name, see `_kit_files`
            with open(path, "rb") as handle:
                digest.update(handle.read().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def kit_hash_inputs(kit_dir: str):
    """(name in the hash, absolute path) for every file `kit_hash` covers, in hash order.

    THE SHARED HALF IS DERIVED, NOT LISTED, and that is the whole point of this function existing.
    A kit whose own files are untouched but whose shared half changed is a different installation,
    so the shared inputs are hashed with it — and the list of them missed `kernel/`, the tree the
    scaffold installs as `.claude/kernel` and every gate imports. Tampering with it needed no
    re-stamp (`hashing.py`, which DEFINES this hash, was itself outside it), and a kernel-only
    release bumped no kit VERSION, so `session_status` announced no update and a security fix to
    the kernel never reached an installed project. Replacing the list with a second list would have
    left the next omission exactly as cheap.

    So: SHARED IS EVERYTHING AT THE `team-kits/` ROOT THAT IS NOT A KIT (`is_kit_dir`) and not a
    tool leftover (`is_transient`) — files under `@shared/<name>`, directories walked under
    `@shared/<name>/…`. Over-inclusion is the safe direction here: a stray file at that root costs
    one bump, while a missed one costs a stamp that means less than it claims.

    THE SUBJECT IS NEVER ITS OWN SHARED HALF. Excluding `kit_dir` explicitly rather than trusting
    `is_kit_dir` to recognise it is what keeps the hash a FUNCTION: a directory being hashed as a
    kit that the predicate does not call one would be hashed twice, once including its own VERSION
    — so stamping it would change the value it was stamped with, forever.
    """
    kit_dir = os.path.abspath(kit_dir)
    root = os.path.dirname(kit_dir)
    for relative, path in _kit_files(kit_dir):
        if relative != "VERSION":
            yield relative, path
    for entry in sorted(os.listdir(root)):
        path = os.path.join(root, entry)
        if path == kit_dir or is_transient(entry) or is_kit_dir(path):
            continue
        if os.path.isdir(path):
            for relative, inner in _kit_files(path):
                yield "@shared/" + entry + "/" + relative, inner
        elif os.path.isfile(path):
            yield "@shared/" + entry, path


def _kit_files(base: str):
    """(relative posix path, absolute path or None) for what a source tree contributes to `kit_hash`.

    One definition for the kit's own tree and for the shared trees, so the two cannot drift into
    skipping different things. Tool leftovers are out (`is_transient`) because `prune_transient`
    keeps them out of every installation; everything else is in.

    A DIRECTORY LINK IS NAMED AND NOT DESCENDED INTO, exactly as in `_bundle_files` and for the
    reason given there at length — `os.walk` walks past one, so a plain walk answers "nothing
    changed" about a tree that now reaches somewhere else entirely. This half was written blind for
    a release while the bundle half was being fixed, which left one directory with two answers: a
    `team-kits/kernel/evil -> <elsewhere>` moved no kit stamp although the kernel is IN the stamp
    (measured 2026-07-27), while the installed copy of it was reported as a stranger. Downstream
    that was fail-closed rather than exploitable; the asymmetry is the defect.
    """
    for dirpath, dirnames, filenames in os.walk(base):
        kept = sorted(d for d in dirnames if d not in TRANSIENT_DIRS)
        linked = [d for d in kept if _is_directory_link(os.path.join(dirpath, d))]
        dirnames[:] = [d for d in kept if d not in linked]
        for name in linked:
            relative = os.path.relpath(os.path.join(dirpath, name), base).replace("\\", "/")
            yield relative + "/" + SYMLINK_MARKER, None
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            relative = os.path.relpath(path, base).replace("\\", "/")
            if not is_transient(relative):
                yield relative, path


def recorded_kit_hash(kit_dir: str):
    """The `content:` hash `<kit>/VERSION` claims, or None when there is no such stamp."""
    try:
        with open(os.path.join(kit_dir, "VERSION"), encoding="utf-8-sig") as handle:
            for line in handle:
                if line.startswith("content:"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def modified_bundle_files(kit_dir: str, kernel_dir: str, claude_dir: str):
    """Kit files whose INSTALLED copy differs from the source — empty when the bundle is the kit's.

    RAISES `BundleSourceMissing` when a source tree is absent, and that is the whole difference
    between this function and the one it replaced. The first version simply skipped a missing
    source and returned `[]`, so "could not compare" and "compared, all equal" were the same
    answer — fail-open at the bottom of a fail-closed layer. Demonstrated end to end: replace two
    gates with `sys.exit(0)`, watch the next session drop to `hooks_trust_required`, run the
    recorder with a `--kit-root` that does not exist, and one session later `python scripts/harness.py doctor`
    reports `hook_trust: verified` over a bundle whose spawn veto is a no-op. A typo in the flag
    reaches the same place by accident.

    Exists so `write_kit_state.py` can refuse to bless a bundle that is not the kit's. Without it,
    recording trust was a plain shell command an agent could run: edit a hook, watch the next
    session report `hooks_trust_required`, re-run the recorder, and the tampered bundle is
    `restart_required` → `active` on the following start — no user, no `/hooks`, no confirmation,
    which is exactly what spec II.8 requires for a changed bundle. Running the real SCAFFOLD is
    safe by comparison, because it re-copies the kit files and thereby undoes the tampering it
    would otherwise bless; this is how the recorder inherits that property.

    FILE BY FILE, not hash against hash. A whole-bundle hash comparison was tried first and was
    wrong: the scaffold copies over `.claude/hooks` without pruning, so any file a project has
    accumulated — an older kit's hook, a rename left behind — made the two hashes differ, and the
    scaffold then threw on a perfectly untampered install. The question this answers is "is the
    kit's enforcement code as the kit shipped it", and an extra file is a different question.

    Note what that other question is NOT: `hook_trust` does not cover it. The recorder rewrites
    the bundle hash INCLUDING the stranger, so the next report calls that bundle trusted. It
    matters more than it sounds, because GATE_PREAMBLE puts the hooks directory on `sys.path[0]`
    — a `.claude/hooks/yaml.py` shadows PyYAML for the kernel in every gate process. So the
    recorder NAMES strangers on stderr, and closing it properly means the scaffold pruning what it
    did not install, which belongs to phase 3.

    Sources match what the scaffold installs: `$kit/hooks/*` (top-level files) and the whole
    `kernel/` tree, minus the bytecode the scaffold prunes (`_shipped_files`). A source file
    MISSING from the install counts as modified.
    """
    modified = []
    for subtree, root, flat in (("hooks", kit_dir, True), ("kernel", kernel_dir, False)):
        if not os.path.isdir(root):
            # Keyed on WHAT IS INSTALLED, not on what was asked for. Missing source while
            # something is installed is the dangerous half: it is the shape in which "could not
            # compare" used to be reported as "compared, all equal". Missing source with nothing
            # installed is a kit that ships no such subtree, and there is nothing to be wrong
            # about. (In practice the recorder cannot even start without a kernel beside it, so
            # that second branch is defensive rather than load-bearing — it is kept because the
            # condition should describe the situation, not the current call graph.)
            if os.path.isdir(os.path.join(claude_dir, subtree)):
                raise BundleSourceMissing(
                    "%s/ is installed but there is no source to compare it against at %s — "
                    "refusing to answer 'unmodified' about a comparison that did not happen"
                    % (subtree, root))
            continue
        for relative, source in _shipped_files(root, flat):
            installed = os.path.join(claude_dir, subtree, relative.replace("/", os.sep))
            if source is None:            # the source itself is a symlinked directory
                modified.append(subtree + "/" + relative)
                continue
            try:
                with open(source, "rb") as left, open(installed, "rb") as right:
                    if left.read() != right.read():
                        modified.append(subtree + "/" + relative)
            except OSError:
                modified.append(subtree + "/" + relative)
    return sorted(modified)


def strangers_in_the_bundle(claude_dir: str, kit_dir: str, kernel_dir: str):
    """Installed enforcement files the kit did not ship — reported, not refused.

    Separate from `modified_bundle_files` because the answer is different: a stranger is usually
    an older kit's hook the scaffold never pruned, which is a mess rather than an attack. It is
    still worth naming, since `.claude/hooks` is `sys.path[0]` for every gate process.

    AN INSTALLED TOOL LEFTOVER IS ALWAYS A STRANGER, and that falls out of the two enumerations
    rather than being a rule of its own: a scaffold ships none (`_shipped_files` over a pruned
    install), so nothing that is found (`_bundle_files`) can match one. That is the correct answer
    for both readings of a `.pyc` in `.claude/hooks` — a planted sourceless module, or a cache some
    process wrote where the harness takes care never to write one.
    """
    known = set()
    for subtree, root, flat in (("hooks", kit_dir, True), ("kernel", kernel_dir, False)):
        if os.path.isdir(root):
            known.update(subtree + "/" + rel for rel, _ in _shipped_files(root, flat))
    found = []
    for subtree in BUNDLE_SUBTREES:
        installed_root = os.path.join(claude_dir, subtree)
        if not os.path.isdir(installed_root):
            continue
        # NOT flat, even for `hooks`: `modified_bundle_files` is flat because the scaffold
        # installs only top-level files, but a STRANGER can be a package — and
        # `hooks/yaml/__init__.py` shadows PyYAML for the kernel exactly as `hooks/yaml.py` does,
        # while a flat scan cannot see it.
        for relative, _path in _bundle_files(installed_root, False):
            name = subtree + "/" + relative
            if name not in known:
                found.append(name)
    return sorted(found)


def resolves_to_module(path: str) -> bool:
    """Would Python's import machinery load CODE from this path, given its parent on `sys.path`?

    ASK THE MACHINERY, DO NOT SPELL THE EXTENSIONS OUT. `importlib.machinery.all_suffixes()` is the
    running interpreter's own answer — source, bytecode, and the platform's extension-module
    suffixes — so `.pyd` on Windows and `.so` on POSIX are covered on the platform where they
    actually load, and both would have been missing from a hand-written `(".py", ".pyc")`. It also
    omits `.pyo`, which stopped being importable in 3.5: this list tracks what the interpreter
    imports today, while `BYTECODE_SUFFIXES` deliberately still names `.pyo` because that question
    is "what did somebody leave lying around", not "what would load".

    A DIRECTORY counts when it directly contains such a file. That is one condition for both
    shapes Python offers — a regular package (`__init__.py`) and a namespace package with a module
    inside it — and it stops one level down on purpose: a directory whose own children are only
    further directories (a `backups/<timestamp>/…` tree) becomes a namespace package that resolves
    to no code at all, and calling that an executable foreign body would make the check cry wolf
    over the scaffold's own bookkeeping. A directory that cannot be listed counts, because "cannot
    look" is not "looked and found nothing". Symlinks are followed here, unlike in the hash: the
    question is what an IMPORT would reach, and an import follows them.
    """
    try:
        if os.path.isdir(path):
            return any(_has_module_suffix(entry) for entry in os.listdir(path))
    except OSError:
        return True
    return _has_module_suffix(os.path.basename(path))


def _has_module_suffix(name: str) -> bool:
    """Does this bare filename carry a suffix the import machinery loads a module from?"""
    return any(name.endswith(suffix) and len(name) > len(suffix)
               for suffix in importlib.machinery.all_suffixes())


def foreign_importables(claude_dir: str, kit_dir: str, kernel_dir: str):
    """Code on the enforcement layer's IMPORT PATH that the kit did not ship — a refusal, not a note.

    THE SUBJECT IS THE IMPORT PATH, WHICH IS NOT THE HASHED BUNDLE. Two directories end up on
    `sys.path` for gate processes and they arrive by different routes: `GATE_PREAMBLE` puts
    `.claude/hooks` at `sys.path[0]`, and `_kernel.import_kernel` puts `.claude` ITSELF there while
    it imports the kernel — which is when `kernel.state` runs its module-scope `import yaml`. So a
    file the hash never sees can still own the YAML parser of every gate, measured: a planted
    `.claude/yaml.py` leaves the bundle hash untouched, produces no stranger, and is EXECUTED by
    the shipped SessionStart hook that then records the bundle `active`.

    Hence the two halves, and why they ask different questions of their directories:

      * inside the kit-owned subtrees, every foreign file is already named by
        `strangers_in_the_bundle`; this narrows that list to the ones that would load. A directory
        SYMLINK is included by its target's contents — `hooks/yaml -> <elsewhere>` imports exactly
        as `hooks/yaml/` would.
      * `.claude` itself is shared with the provider and the project (settings, backups, the
        update-pending files), so listing everything foreign there would be noise. Only what
        RESOLVES TO A MODULE is categorically wrong, because nothing but the kernel package — a
        bundle subtree, excluded here and covered above — has any business being importable from
        that directory.

    Nothing is hashed by this: `.claude` holds `kit_state.json`, which the trust hook rewrites, so
    a hash over that directory could not be stable. Naming the intruder does not require hashing
    the room.
    """
    found = [name for name in strangers_in_the_bundle(claude_dir, kit_dir, kernel_dir)
             if resolves_to_module(_installed_path(claude_dir, name))]
    if os.path.isdir(claude_dir):
        for entry in sorted(os.listdir(claude_dir)):
            if entry not in BUNDLE_SUBTREES and resolves_to_module(
                    os.path.join(claude_dir, entry)):
                found.append(entry)
    return sorted(found)


def _installed_path(claude_dir: str, name: str) -> str:
    """The path on disk a stranger's reported name refers to.

    The marker is stripped rather than joined: `hooks/yaml/<symlink>` is how the MEASUREMENT names
    a directory link it refused to descend into, and the thing that exists on disk is the link.
    """
    if name.endswith("/" + SYMLINK_MARKER):
        name = name[:-len(SYMLINK_MARKER) - 1]
    return os.path.join(claude_dir, name.replace("/", os.sep))


def _shipped_files(root: str, flat: bool):
    """`_bundle_files` minus the tool leftovers no scaffold installs — the SHIPPED set.

    The counterpart to the measured set, and the only place the two differ. Used where the question
    is "what did the kit deliver": comparing an installation against its source, and deciding what
    counts as a stranger. Asking for a leftover here would make every install look modified, since
    `prune_transient` removes them on the way in — and the exclusion has to match that prune
    exactly, which is why both read `is_transient` instead of spelling a set out. While they
    disagreed, a `.ruff_cache` under the source kernel was demanded of the installation and blessed
    when found there.
    """
    for relative, path in _bundle_files(root, flat):
        if not is_transient(relative):
            yield relative, path


def _is_directory_link(path: str) -> bool:
    """Is this entry a link that behaves like a DIRECTORY — the one thing that gets the stand-in?

    Both branches of `_bundle_files` ask this and neither may answer it its own way. `os.walk`
    decides `dirs` against `files` by following the entry (`os.path.isdir`), so following it is
    what "directory" has to mean here too; `os.path.islink` alone would call a link to a FILE a
    directory in the flat branch while the walk called it a file, which is one entry with two names
    in the same hash. A broken link is a directory to neither and lands with the files, where the
    read that fails is itself the answer.
    """
    return os.path.isdir(path) and os.path.islink(path)


def _bundle_files(root: str, flat: bool):
    """(relative posix path, absolute path or None) for every entry the bundle takes from `root`.

    EVERY file, with no exclusion by name or extension — the MEASURED set (see BYTECODE_SUFFIXES).

    A DIRECTORY LINK IN THE SENSE OF `_is_directory_link` yields `(name + "/" + SYMLINK_MARKER, None)`
    and is not descended into. `os.walk` does not follow directory links by default, so before this
    such a link was invisible to the hash, to the stranger scan and to doctor — while Python
    imports through it perfectly well. Measured: `.claude/hooks/yaml -> <elsewhere>` shadows PyYAML
    for the kernel in every gate process, and `.claude/hooks/_compat -> <elsewhere>` makes
    `guard_harness_selfmod` wave through a write to `.claude/hooks/` — with the bundle hash
    UNCHANGED and `hook_trust` still `verified`. Following the link instead would invite cycles and
    would hash whatever it points at; naming it is enough, because a name in the hash is a hash
    that changes.

    A LINK TO A FILE IS A FILE, and `flat` used to disagree with the walk about that. The walk gets
    the answer from `os.walk`, which sorts by `os.path.isdir` and therefore hands a file link over
    as a file whose content is read; the flat branch asked bare `os.path.islink` and gave the same
    entry the directory stand-in instead. One directory, two names for one file — the exact defect
    this module exists to end, and it hit both sides of the shipped/measured pair at once. Measured
    2026-07-27 on a kit shipping `<kit>/hooks/gate_git.py -> <elsewhere>` and an installation
    holding exactly the bytes that link points at: `modified_bundle_files` answered
    `['hooks/gate_git.py/<symlink>']` (the shipped side contributed a marker no installation can
    match, so the gate was permanently "modified" and the recorder permanently refused) and
    `strangers_in_the_bundle` answered `['hooks/gate_git.py']` (the installed file matched no
    shipped name) — one file, two names, two wrong answers. `_is_directory_link` is now the single
    condition both branches ask, so they cannot drift apart again.

    A WINDOWS JUNCTION takes the other road, and the difference is worth stating because this
    docstring is the template the Codex verifier is written against. `os.path.islink` is False for
    a junction (measured, 2026-07-27: `mklink /J` needs no privilege and produces
    `islink() == False` with the reparse attribute set), so `os.walk` descends and the linked
    contents are hashed under their apparent names. The measurement stays honest either way — a
    junction's payload is IN the hash rather than named beside it — which is why the two branches
    may differ here at all; what may not differ is the two implementations of this branch.
    """
    if flat:
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if _is_directory_link(path):
                yield name + "/" + SYMLINK_MARKER, None
            elif not os.path.isdir(path):
                # a real subdirectory is what `flat` exists to leave out; everything else is a file
                yield name, path
        return
    for current, dirs, files in os.walk(root):
        linked = sorted(d for d in dirs if _is_directory_link(os.path.join(current, d)))
        dirs[:] = sorted(d for d in dirs if d not in linked)
        for name in linked:
            path = os.path.join(current, name)
            yield os.path.relpath(path, root).replace(os.sep, "/") + "/" + SYMLINK_MARKER, None
        for name in sorted(files):
            path = os.path.join(current, name)
            yield os.path.relpath(path, root).replace(os.sep, "/"), path


def _hash_subtrees(subtrees):
    """SHA-256 over named subtrees, each walked in full.

    Enumeration is delegated to `_bundle_files` rather than repeated here. The two used to walk
    separately and the difference was not academic: the copy in this function had no symlink
    handling, so a link planted in `.claude/hooks` left the hash untouched while the stranger scan
    (once fixed) reported it — one directory, two answers, which is the defect this module was
    written to end.

    THE MEASUREMENT IS NEVER FLAT. A `flat_first` switch survived the consolidation, dead: no caller
    ever passed it, and one that did would have hashed only the top level of `.claude/hooks` — the
    very shape (`top-level *.py only`) whose removal is what made a single definition possible. The
    flatness that does exist belongs to the SHIPPED side, where `modified_bundle_files` compares
    against what a scaffold copies; it has no business in what is measured.
    """
    digest = hashlib.sha256()
    seen = False
    for subtree, root in subtrees:
        if not os.path.isdir(root):
            continue
        for relative, path in _bundle_files(root, False):
            digest.update((subtree + "/" + relative).encode("utf-8") + b"\0")
            if path is not None:
                try:
                    with open(path, "rb") as handle:
                        digest.update(handle.read())
                except OSError:
                    # a file that cannot be read is not a bundle that can be trusted
                    return None
            digest.update(b"\0")
            seen = True
    return digest.hexdigest() if seen else None


def _nfc(obj):
    """Recursively NFC-normalize every string (keys and values).

    Fail-closed on the two silent-collision classes (Fable-Check 4, BUG-2/3):
    non-string dict keys (json.dumps would coerce {1: x} into {"1": x}) and
    sibling keys that collide after NFC normalization (a dict comprehension
    would silently merge them -- two different manifests, one hash).
    """
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                raise TypeError(
                    "subject_manifest dict key %r is not a string -- canonical "
                    "hashing is only defined over JSON objects (string keys). "
                    "Remedy: convert the key explicitly before hashing." % (k,)
                )
            nk = unicodedata.normalize("NFC", k)
            if nk in out:
                raise ValueError(
                    "subject_manifest contains sibling keys that collide after "
                    "NFC normalization (%r) -- refusing to hash a silently "
                    "merged manifest. Remedy: deduplicate the keys." % nk
                )
            out[nk] = _nfc(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [_nfc(v) for v in obj]
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj
    raise TypeError(
        "subject_manifest contains non-JSON type %r -- hashes are only defined "
        "over plain JSON data (str/int/float/bool/None/list/dict). Remedy: "
        "serialize the value explicitly before hashing." % type(obj).__name__
    )


def canonical_json(obj) -> str:
    """Deterministic JSON text: sorted keys, NFC unicode, compact, no NaN."""
    return json.dumps(
        _nfc(obj),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def subject_manifest_hash(manifest) -> str:
    """SHA-256 hex over the canonical envelope {hash_schema_version, subject_manifest}.

    The version field participates in the hash: a future canonicalization change
    bumps HASH_SCHEMA_VERSION and thereby visibly invalidates old approvals
    instead of silently colliding with them.
    """
    envelope = {
        "hash_schema_version": HASH_SCHEMA_VERSION,
        "subject_manifest": manifest,
    }
    return hashlib.sha256(canonical_json(envelope).encode("utf-8")).hexdigest()


# HOW MUCH OF A DOCUMENT `document_content_hash` WILL READ, and why there is a bound at all. The
# hash is computed inside a PreToolUse guard, so an unbounded read lets the SIZE OF A FILE decide
# how long the session stands still on one command -- and, past the window such a guard is killed
# at, whether it is checked at all: a killed hook is read as a pass, which for a large enough file
# would put the wall's own door on the attacker's side. The kits' `_compat.HOOK_DEADLINE_SECONDS`
# carries what was measured about those windows. Measured on this host 2026-08-18, warm cache, 1 MiB chunks: 16 MiB in
# 0.021 s, 64 MiB in 0.050 s, 256 MiB in 0.217 s.
# What a document past the bound gets is a REFUSAL, not a pass: no hash means no approval can name
# it, and every caller here treats "cannot be hashed" as "not covered" (see
# `tools/test_hooks.py::test_a_document_too_large_to_bind_cannot_be_corrected_by_approval`).
DOCUMENT_HASH_LIMIT = 256 * 1024 * 1024


def on_disk_position(root: str, relative: str):
    """The project-relative path spelled the way the FILESYSTEM spells it, or None.

    WHY A LEXICAL COMPARISON IS NOT ENOUGH, measured (verifier round 2, R2): on a case-insensitive
    filesystem `ARCHIVE/1-Finanzen/2026/x.pdf` opens the same file as `archive/…`, resolves to the
    same absolute path, and normalises back to itself -- so it round-trips, mints a real user
    approval, and then matches nothing, because the gate reads the position out of a command that
    spells it the way the archive does. A burned approval is worse than a refusal: the user answered
    a question for nothing.

    So each segment is looked up in its parent and the entry's REAL name is used. `None` when a
    segment does not exist or the parent cannot be listed -- the caller's other checks then refuse
    with their own message. Nothing here compares case itself: the comparison belongs to the caller,
    and the case-insensitive filesystem is only the reason the two spellings could differ at all.
    """
    current = root
    spelled = []
    for segment in str(relative or "").split("/"):
        if not segment:
            return None
        try:
            entries = os.listdir(current)
        except OSError:
            return None
        wanted = os.path.normcase(segment)
        found = next((entry for entry in entries if os.path.normcase(entry) == wanted), None)
        if found is None:
            return None
        spelled.append(found)
        current = os.path.join(current, found)
    return "/".join(spelled)


def document_content_hash(path: str, limit: int = DOCUMENT_HASH_LIMIT):
    """SHA-256 hex of ONE file's bytes, or None when it cannot be bound.

    THE FASSUNG, NOT THE NAME. An approval that named only a path would still apply after the file
    at that path had been replaced -- and in a business archive "the document at this place" is
    exactly the thing that changes without the path moving. Hashing the bytes is what makes the
    user's signature cover the document they were shown.

    IT IS ALSO WHAT MAKES A FILING-CORRECTION APPROVAL SINGLE-USE, in the same derived way a push
    token is (`approvals.push_subject_manifest`): once the approved move or delete has run, there is
    no file at the source path any more, this returns None, and the same approval matches nothing.
    No "used" flag in writable state has to be kept honest for that.

    None -- never an exception and never a partial digest -- for every reason the bytes cannot be
    read in full: the file is absent, is a directory, is unreadable, or is larger than `limit`.
    Callers are gates, and for a gate "I could not measure it" and "it is not covered" have to be
    one answer.
    """
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > limit:
            return None
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None
