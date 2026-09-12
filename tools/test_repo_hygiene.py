#!/usr/bin/env python3
"""Repo hygiene: git must not TRACK a file it also IGNORES, a file name must not lie about whose
report it holds, a test must not leave its `sys.path` entry to the next test, a PowerShell
launcher must not be started where nobody asked whether this host has one, a shipped kit file
must not point at a decision this store no longer holds, and a statement that answers for a claim by
naming a test must name one that exists. One member of this file REPORTS instead of judging --
prose under `docs/` that nothing reads any more -- and says so in its own name.

WHY THIS IS THE RIGHT SUBJECT, and not "is ModuleAnalysisCache absent". A `.gitignore` rule has no
effect on a path git already tracks, so a tool trace that was committed once (a PowerShell module
cache under `Microsoft/`, a kit audit log under `project_memory/.audit/` -- both in b32ec98) stays
in every future commit no matter how many rules name it. That is precisely the state BUG-0008 was
in: the rule existed and the file was tracked anyway, so the rule was a promise the tree did not
keep. The invariant that catches it is git's own: the set of TRACKED files and the set of
IGNORED files must be disjoint. Measured with `git ls-files --cached --ignored --exclude-standard`,
which is git resolving `.gitignore` against its own index -- the running behaviour, not a string
search over the file.

THE ONE EXCLUSION IS SCOPED AND REASONED, not an allowlist of paths. `project_memory/` is canonical
state under gate 1 (`gate_lead_write_scope.py`), which refuses every tool write there for every
caller, so a `project_memory/.audit/hook_events.jsonl` that a kit hook subprocess committed cannot
be untracked from a harness session -- `git rm --cached` on it is refused before it runs. It is the
open remainder H37 Rest 2 in `docs/POST_V2_WISHLIST.md`, and the repair belongs in the kit. Anything
tracked-and-ignored OUTSIDE that tree is a new tool trace that must be untracked.
"""
import ast
import fnmatch
import glob
import io
import os
import re
import shutil
import subprocess
import sys
import time
import warnings

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESEARCH = os.path.join(ROOT, "docs", "research")

sys.path.insert(0, os.path.join(ROOT, "tools"))
from test_model_pins import under_an_agents_directory  # noqa: E402 -- ONE role predicate, shared
# THE CHECK AND ITS REMEDY SHARE THIS PREDICATE, they do not each carry one. The first cut had
# the exclusion here and not in the tool, so the sweep excused canonical state while
# `--apply` would have rewritten it -- a protection the round protocol claimed and the code
# did not build. It lives with the remedy because that is the side that acts.
from normalise_line_endings import repairable  # noqa: E402


def _tracked_and_ignored():
    """Paths git both TRACKS and IGNORES, straight from git's own index/attribute resolution."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--ignored", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    assert result.returncode == 0, result.stderr
    return [line for line in result.stdout.splitlines() if line.strip()]


def test_git_tracks_no_ignored_file_outside_canonical_state():
    """A tracked-and-ignored file is a dead ignore rule (BUG-0008): the file ships regardless.

    Goes red while `Microsoft/Windows/PowerShell/ModuleAnalysisCache` is tracked, which is the
    exact state the `Microsoft/` rule was added into and could not fix on its own -- the file had
    to be untracked (`git rm --cached`) for the rule to mean anything. `project_memory/` is excluded
    because it is gate-protected canonical state a harness session cannot untrack (H37).
    """
    _require_git()
    offenders = [path for path in _tracked_and_ignored()
                 if not path.startswith("project_memory/")]
    assert not offenders, (
        "git tracks these files while a .gitignore rule ignores them, so the rule is a no-op and "
        "the tool trace ships in every commit -- untrack each with `git rm --cached <path>`: %s"
        % offenders)


def test_the_known_out_of_scope_trace_is_still_the_only_exception():
    """The tripwire on the exclusion above, so it cannot quietly widen or go stale.

    The exclusion earns its place only as long as the audit log is the one thing it covers. If that
    file gets untracked in the kit (H37 closed), this asserts the exception is no longer needed and
    should be removed; if a SECOND ignored file appears under project_memory/, it surfaces here
    rather than hiding behind the prefix.
    """
    _require_git()
    excused = [path for path in _tracked_and_ignored()
               if path.startswith("project_memory/")]
    assert excused == ["project_memory/.audit/hook_events.jsonl"], (
        "the project_memory/ exclusion in test_git_tracks_no_ignored_file_outside_canonical_state "
        "no longer covers exactly the audit log H37 names -- update the exclusion and H37: %s"
        % excused)


# ---------------- the checkout obeys .gitattributes (BUG-0025) --------------------------------

# WHY GIT IS ASKED AND NOTHING IS SCANNED. `.gitattributes` pins `* text=auto eol=lf`, and whether a
# given file is TEXT under that rule is decided by BYTES -- git looks for a NUL in the first 8000 of
# them. `git ls-files --eol` is that resolution running: `i/` is what the index holds, `w/` what the
# file on disk carries, and `-text` is git saying "binary, I do not convert this". A scan of our own
# would be a second answer to the question the tool under test already answers, and it would have to
# invent the binary rule this repo has decided to take from git. The one place a scan of our OWN
# belongs is where the AGREEMENT between the two is the property being held:
# `test_git_decides_binary_by_bytes_and_pins_every_text_file_to_lf` measures it, and the figures
# behind it live in the round protocol rather than in a comment that ages.


# What binary looks like to git under `text=auto`, and the window it looks in: one NUL byte in
# the first 8000. Spelled here because the readings below are the one place in this suite that
# answers that question itself instead of asking git.
NUL = b"\x00"
NUL_WINDOW = 8000
# `git check-attr --stdin` reads one path per record; the separator is stated so no reader of
# this file has to know which one a text-mode pipe would have substituted for it.
SEPARATOR = "\n"


def _binary_by_bytes():
    """(binary, text) as the BYTES decide -- a NUL in the first `NUL_WINDOW` of a tracked file.

    The one reading in this section that is deliberately NOT git's, because the property it serves
    is the AGREEMENT of the two. Everything else here asks git.
    """
    binary, plain = set(), set()
    for relative in _tracked_files():
        full = os.path.join(ROOT, relative.replace("/", os.sep))
        if not os.path.isfile(full):
            continue
        with open(full, "rb") as handle:
            (binary if NUL in handle.read(NUL_WINDOW) else plain).add(relative)
    return binary, plain


def _attributes(paths, *names):
    """{path: {attribute: value}} straight out of `git check-attr` -- the resolution a checkout runs.

    One process for the whole set, and BYTES down the pipe, for the reason the binary tripwire below
    carries: in text mode this interpreter rewrites the record separator, git then reads a path with
    a trailing CR and answers about a file nobody has.
    """
    resolved = subprocess.run(["git", "check-attr", "--stdin"] + list(names), cwd=ROOT,
                              input=(SEPARATOR.join(sorted(paths)) + SEPARATOR).encode("utf-8"),
                              capture_output=True, timeout=180)
    assert resolved.returncode == 0, resolved.stderr.decode("utf-8", "replace")
    answer = {}
    for line in resolved.stdout.decode("utf-8", "replace").splitlines():
        if ": " not in line:
            continue
        parts = line.rsplit(": ", 2)
        if len(parts) == 3:
            answer.setdefault(parts[0], {})[parts[1]] = parts[2]
    return answer


def test_git_decides_binary_by_bytes_and_pins_every_text_file_to_lf():
    """The line the whole of BUG-0025 rests on -- `* text=auto eol=lf` in .gitattributes -- measured.

    WHY THIS EXISTS BESIDE THE SWEEP, and it is the gap the first verification round found: the
    sweep and the binary tripwire both read the WORKING TREE (`git ls-files --eol`, column `w/`),
    and that stays LF when the pin disappears, because the files on disk are already LF. Both went
    green with the pin deleted, while a fresh clone on a `core.autocrlf=true` host then checks out
    CRLF again -- so the line everything else in this section depends on was carried by nothing.

    THE EFFECT IS ASKED, NOT THE TEXT. `git check-attr` is the resolution a checkout performs, so
    this is red for a pin that is gone, for one a later line shadows, and for one that never
    matched -- none of which a search over the file would notice.

    THE TWO READINGS DO NOT SEE THE SAME BYTES, and pretending they did was the defect of the first
    cut: this file stops at `NUL_WINDOW`, git reads the whole blob. For a binary whose first NUL
    sits BEYOND that window the two disagree -- and that is not an edge, it is literally the class
    the `binary` lines exist for. Measured on a fixture of 8500 filler bytes and then a NUL: without
    a pin the tripwire below demands one ("no binary line covers them"), with the pin this
    assertion refused it, so NO state of `.gitattributes` made both green. Git's own answer is
    therefore taken off the text side FIRST, and such a file is REPORTED at the end rather than
    asserted about -- which is what the sentence about it always said.

    TWO HALVES, ONE SUBJECT -- the tracked files that both readings call text:

      * every one of them resolves to `text: auto` AND `eol: lf`, and BOTH attributes are asserted
        because each catches a different mutation: deleting the pin leaves both unspecified, while a
        blanket `* binary` leaves `eol: lf` standing and only `text` turns to `unset` -- measured, a
        `binary` attribute does not take the eol answer away;
      * every tracked file that is BINARY BY BYTES is one git also refuses to convert (`-text`).
        Only that direction: the reverse is the `binary` lines doing their work, and it is reported.
    """
    _require_git()
    binary, plain = _binary_by_bytes()
    assert binary and plain, (
        "the byte reading found no text or no binary at all -- it stopped matching the tree")
    endings = _worktree_line_endings()
    # WHAT GIT READS AS BINARY CONTENT IS NOT THIS ASSERTION'S SUBJECT, whatever the first
    # `NUL_WINDOW` bytes said -- see the docstring. This is the `w/` column, i.e. git's reading of
    # the CONTENT, not of the attribute: a text file pinned `binary` still reports `w/lf` and stays
    # in the subject, which is why pinning one turns this red rather than hiding it. Kept for the
    # report at the end, because a file that lands here is the one the `binary` lines were added for.
    pinned_without_a_nul = sorted(path for path in plain if endings.get(path) == "-text")
    subject = plain - set(pinned_without_a_nul)
    assert subject, (
        "not one tracked file is text to BOTH readings, so the pin has nothing to be measured on: "
        "every file with no NUL in its first %d bytes is one git reports as `w/-text`. Either this "
        "tree carries no text at all, or one of the two readings stopped matching." % NUL_WINDOW)
    attributes = _attributes(subject, "text", "eol")
    unpinned = sorted(path for path in subject
                      if attributes.get(path, {}).get("eol") != "lf"
                      or attributes.get(path, {}).get("text") != "auto")
    assert not unpinned, (
        "%d tracked file(s) carry no NUL in their first %d bytes -- text by the rule this repo took "
        "from git -- and git resolves them to something other than `text: auto` / `eol: lf`, so a "
        "clone on a core.autocrlf=true host checks them out with CRLF and BUG-0025 is back. The "
        "line that pins them is `* text=auto eol=lf` in .gitattributes. Files: %s"
        % (len(unpinned), NUL_WINDOW, unpinned[:20]))
    convertible = sorted(path for path in binary if endings.get(path) != "-text")
    assert not convertible, (
        "git is prepared to line-ending-convert these files although their first %d bytes carry a "
        "NUL, which is what binary looks like here -- a conversion would corrupt them: %s"
        % (NUL_WINDOW, convertible[:20]))
    if pinned_without_a_nul:
        warnings.warn(
            "git treats these as binary although their first %d bytes carry no NUL -- that is "
            "either a `binary` line doing work the heuristic alone would not do, or a file that "
            "still needs one (the tripwire below is the half that says which): %s"
            % (NUL_WINDOW, pinned_without_a_nul[:20]), UserWarning)


def _worktree_line_endings():
    """{tracked path: git's `w/` reading} -- `lf`, `crlf`, `mixed`, `none` or `-text` (binary)."""
    result = subprocess.run(["git", "ls-files", "--eol"], cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
    assert result.returncode == 0, result.stderr
    reading = {}
    for line in result.stdout.splitlines():
        if "\t" not in line:
            continue
        fields, path = line.split("\t", 1)
        for field in fields.split():
            if field.startswith("w/"):
                reading[path] = field[2:]
    assert reading, "git listed no line endings at all -- the reader stopped matching its output"
    return reading


def test_no_tracked_text_file_checks_out_with_crlf():
    """BUG-0025: `.gitattributes` says LF and this host's git config says otherwise -- who won?

    `core.autocrlf=true` stands in this repo's LOCAL config and in the host's SYSTEM config
    (measured 2026-09-04), and `eol=lf` overrides it on CHECKOUT -- but nothing overrides an editor,
    a generator or a shell redirection that writes CRLF into a tracked file afterwards. That is not
    cosmetic here: `lead_package.size` and the mirror comparison in `tools/validate.py` read raw
    on-disk bytes, so one such file inflates the lead instruction package past its recorded size and
    `install.sh` aborts before it installs a single hook -- which is BUG-0025 end to end.

    THE FILE IS NAMED, because "somewhere in this tree" is not a repair anyone can carry out; the
    remedy is one command and it stands in the message. `docs/line-endings.md` carries the cause and
    what this repo deliberately does NOT do about it.

    WHAT IT EXCUSES IT REPORTS. The canonical part of `project_memory/` is left out because no tool
    write reaches it (`_repairable`), and an exclusion that is also silent is how a set grows -- so
    those files are warned about here, in the same fail-open shape `_report_stale` uses one section
    down, and never blocked on.
    """
    _require_git()
    endings = _worktree_line_endings()
    drifted = sorted(path for path, ending in endings.items() if ending in ("crlf", "mixed"))
    excused = [path for path in drifted if not repairable(path)]
    if excused:
        warnings.warn(
            "these files carry CRLF in canonical state, which no tool write reaches (gate 1), so "
            "the sweep below cannot ask for them -- they are repaired where they are written, in "
            "the kit: %s" % excused, UserWarning)
    offenders = [path for path in drifted if repairable(path)]
    assert not offenders, (
        "%d tracked text file(s) carry CRLF on disk while .gitattributes pins every text file to "
        "eol=lf, so a byte-size or byte-identity check reads a number no LF checkout can "
        "reproduce (BUG-0025). Remedy: `python tools/normalise_line_endings.py --apply`, which "
        "rewrites only files whose normalised bytes equal the committed blob exactly. Files: %s"
        % (len(offenders), offenders))


def test_the_line_ending_sweep_excuses_canonical_state_and_nothing_else():
    """The floor under `normalise_line_endings.repairable`, so the exclusion cannot quietly widen.

    It is the SAME function the remedy filters with, imported at the top of this file -- so this
    floor holds the tool's behaviour and not a second copy of the rule.

    It is a floor and NOT a claim that the exclusion still earns its keep: whether a canonical-state
    file carries CRLF right now depends on the checkout (a fresh clone of this repo has none, this
    developer host has one), so a test that asserted the exception is still needed would be red for
    the checkout rather than for the repo. What can be held is the shape: staging is inside the
    sweep, the canonical part is outside it, and nothing above `project_memory/` is touched.
    """
    assert repairable("project_memory/staging/TSK-0125/note.md"), (
        "staging holds proposals that are ordinary files -- it must stay inside the sweep")
    assert repairable("docs/note.md") and repairable("team-kits/dev-team/VERSION"), (
        "the exclusion has grown past the tree gate 1 refuses a tool write to")
    assert not repairable("project_memory/.audit/hook_events.jsonl"), (
        "canonical state is what the exclusion is for")


def test_a_crlf_blob_in_head_is_not_reported_as_an_uncommitted_change(tmp_path, monkeypatch):
    """The remedy must not name a cause `git status` refutes (BUG-0025, verification round 1).

    When the blob in `HEAD` carries CRLF ITSELF, the working tree is not what is wrong: the file is
    unchanged, `git status` is empty for it, and normalising it would differ from the blob for a
    reason that has nothing to do with an edit. The first cut answered "it carries a real
    uncommitted change" there -- a sentence the tool cannot support and the caller cannot act on.
    What needs rewriting is the INDEX, and the command for that is `git add --renormalize`.

    AND THE TWO ARE NOT EXCLUSIVE. A CRLF blob PLUS a hand edit is a real state, and the second cut
    answered it with the renormalise sentence alone -- while `git status` does report such a file
    and `git add --renormalize` would take the foreign edit into the index with it. That case is the
    fourth below, and it is why the tool compares against the blob AS NORMALISED instead of ordering
    two questions as if only one could be true.

    THE CLASS IS EMPTY IN THIS REPO TODAY, which is why the wrong sentence could stand unnoticed
    twice, and why this is measured here instead of on the tree: `_committed` is the one door to
    `HEAD` and it is the door this test stands in. Red without either fix -- the verdict then reads
    "uncommitted change" for a file nobody changed, or the renormalise sentence for a file somebody
    did change.
    """
    import normalise_line_endings as tool

    drifted = tmp_path / "keeps-its-crlf.md"
    drifted.write_bytes(b"one\r\ntwo\r\n")
    monkeypatch.setattr(tool, "ROOT", str(tmp_path))
    monkeypatch.setattr(tool, "_committed", lambda path: b"one\r\ntwo\r\n")
    verdict, normalised = tool._verdict("keeps-its-crlf.md")
    assert normalised is None, "a file whose blob carries CRLF must not be rewritten by this tool"
    assert "the blob HEAD holds carries CRLF itself" in verdict, verdict
    assert "git add --renormalize" in verdict, (
        "the refusal names no remedy the caller can carry out: %s" % verdict)
    assert "uncommitted change" not in verdict, (
        "the refusal still claims a change git would not report: %s" % verdict)

    monkeypatch.setattr(tool, "_committed", lambda path: b"one\ntwo\nthree\n")
    changed, normalised = tool._verdict("keeps-its-crlf.md")
    assert normalised is None and "uncommitted change" in changed, (
        "the ordinary refusal lost its own reason: %s" % changed)

    monkeypatch.setattr(tool, "_committed", lambda path: b"one\ntwo\n")
    ok, normalised = tool._verdict("keeps-its-crlf.md")
    assert ok == "ok" and normalised == b"one\ntwo\n", (
        "the accepting branch is gone, so the two refusals above hold over nothing: %r" % ok)

    # BOTH AT ONCE, which is the state an ordered pair of questions answers with the wrong half:
    # the blob carries CRLF *and* the file has an edit the blob does not know.
    drifted.write_bytes(b"one\r\ntwo\r\nTHREE-a-real-edit\r\n")
    monkeypatch.setattr(tool, "_committed", lambda path: b"one\r\ntwo\r\n")
    both, normalised = tool._verdict("keeps-its-crlf.md")
    assert normalised is None, "a file with an uncommitted edit must not be rewritten either"
    assert "TWO things are wrong at once" in both, (
        "the combination is answered with one of the two single reasons: %s" % both)
    assert "git status` DOES report it" in both and "neither command is the answer on its own" in both, (
        "the combination still recommends a command that would swallow the other change: %s" % both)
    assert "says nothing about this file" not in both, (
        "the combination still claims git would be silent about a file git reports: %s" % both)


def test_the_remedy_leaves_canonical_state_to_the_place_that_writes_it(tmp_path, monkeypatch):
    """`drifted_files` splits by the same predicate the sweep excuses with -- and says so.

    Red without the fix: the tool took every drifting path, so `--apply` offered to rewrite
    `project_memory/.audit/hook_events.jsonl`, which gate 1 refuses to any caller. Nothing but that
    file's size stopped it.
    """
    import normalise_line_endings as tool

    # THE RECORD SHAPE IS GIT'S OWN, copied off a real `git ls-files --eol` line of this repo
    # (`i/none  w/lf    attr/text=auto eol=lf <TAB>docs/line-endings.md`): the columns are separated
    # by SPACES and exactly one TAB stands in front of the path. A stub with tabs throughout made
    # the parser find nothing and this test pass over a shape the tool never meets.
    listing = ("i/lf    w/crlf   attr/text=auto eol=lf \tdocs/note.md\n"
               "i/lf    w/crlf   attr/text=auto eol=lf \tproject_memory/.audit/hook_events.jsonl\n"
               "i/lf    w/mixed  attr/text=auto eol=lf \tproject_memory/staging/TSK-0125/p.md\n")
    monkeypatch.setattr(tool, "_git", lambda *argv: listing)
    mine, out_of_reach = tool.drifted_files()
    assert mine == ["docs/note.md", "project_memory/staging/TSK-0125/p.md"], mine
    assert out_of_reach == ["project_memory/.audit/hook_events.jsonl"], out_of_reach


_BINARY_PIN_RX = re.compile(r"(?m)^\s*(\S+)\s+binary\s*$")


def _binary_pins():
    """The patterns `.gitattributes` pins to `binary`, out of the file git itself reads."""
    with io.open(os.path.join(ROOT, ".gitattributes"), encoding="utf-8") as handle:
        return _BINARY_PIN_RX.findall(handle.read())


def test_every_binary_pin_names_a_kind_the_tree_has_and_every_kind_is_pinned():
    """The two-ended tripwire on the one enumeration `.gitattributes` carries.

    `* text=auto` already decides binary BY BYTES, so these lines are insurance for the expensive
    direction only -- a binary whose first 8000 bytes hold no NUL. Insurance written as a list of
    extensions goes wrong in two ways, and both are measured here rather than trusted: an entry
    that names nothing in this tree any more (`*.woff2` stood alone while every `.png` beside it was
    binary, which is the state this test was written into), and a binary kind no entry names.

    THE EFFECT IS ASKED OF GIT, not of the pattern: `git check-attr binary` is the resolution the
    checkout runs, so a pattern that matches nothing because of where it stands in the file shows up
    here. What is read out of the file is only WHICH patterns to hold to that answer -- the same
    division `tools/test_ci_lint_pinned.py` makes between parsing `ruff.toml` and running ruff.
    """
    _require_git()
    pins = _binary_pins()
    assert pins, ".gitattributes pins nothing to `binary` -- this test's subject is gone"
    binaries = sorted(path for path, ending in _worktree_line_endings().items()
                      if ending == "-text")
    assert binaries, "git calls no tracked file binary -- the reader stopped matching"
    # BYTES down the pipe, not text: in text mode this interpreter translates every `\n` into the
    # platform's line separator, and git then reads a path with a trailing CR and answers about a
    # file nobody has (measured here -- every `.png` of the tree came back "unspecified" under names ending in
    # `\r`). The one place in this suite where a line ending decides an answer is the one this
    # section is about.
    resolved = subprocess.run(["git", "check-attr", "--stdin", "binary"], cwd=ROOT,
                              input=("\n".join(binaries) + "\n").encode("utf-8"),
                              capture_output=True, timeout=120)
    assert resolved.returncode == 0, resolved.stderr.decode("utf-8", "replace")
    answers = resolved.stdout.decode("utf-8", "replace").splitlines()
    unpinned = sorted(line.rsplit(": binary: ", 1)[0] for line in answers
                      if line.strip() and not line.endswith(": binary: set"))
    assert not unpinned, (
        "git reads these files as binary by their bytes, but no `binary` line in .gitattributes "
        "covers them, so they rely on the NUL heuristic alone and a line-ending conversion would "
        "corrupt them: %s" % unpinned[:20])
    dead = [pin for pin in pins
            if not any(fnmatch.fnmatch(path, pin) or fnmatch.fnmatch(os.path.basename(path), pin)
                       for path in binaries)]
    assert not dead, (
        "these `binary` lines match no binary file this repo carries any more, so they are a claim "
        "about a tree that has moved on -- drop them: %s" % dead)


# ---------------- nothing a client parses from byte zero may start with a BOM ------------------

BOM = b"\xef\xbb\xbf"


def _tracked_files():
    """Repo-relative paths git TRACKS -- what actually ships, rather than what a walk turns up."""
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=60)
    assert result.returncode == 0, result.stderr
    return [path for path in result.stdout.split("\0") if path]


def read_from_byte_zero(relative, head):
    """Why a machine reads this file's FIRST bytes as structure -- or None when it does not.

    A PROPERTY OF THE FILE, not of its location, and that is the point: a role definition, a skill,
    a settings file and a kit shim are all files whose opening bytes are a token some parser has to
    match exactly, and those trees are not enumerated anywhere here. The classification takes a BOM
    off FIRST, so a file that carries one is still recognised as the kind of file that must not --
    otherwise the byte that breaks the reader would also hide the file from this check.
    """
    body = head[len(BOM):] if head.startswith(BOM) else head
    first = body.split(b"\n", 1)[0].strip()
    if relative.endswith(".json"):
        return "a JSON parser starts at byte 0"
    if first == b"---":
        return "the frontmatter delimiter has to be the first line"
    if first.startswith(b"<!-- agents-and-skills:team-kit"):
        return "the kit marker is read off line 1"
    return None


def _heads():
    """(relative path, first bytes) for every tracked file, small reads only."""
    for relative in _tracked_files():
        path = os.path.join(ROOT, relative.replace("/", os.sep))
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            yield relative, handle.read(400)


def test_no_file_a_parser_reads_from_byte_zero_starts_with_a_bom():
    """FR-0060: an editor's UTF-8 BOM turns a definition into a file some reader cannot open.

    WHAT IS MEASURED AND WHAT IS NOT, because the two point in opposite directions and the honest
    version is the mixed one: on the client this round ran against, a role file WITH a BOM loaded
    and spawned fine. The floor below which it is silently skipped comes from the radar item, not
    from a run here. What was measured is the other reason -- our own `.claude/hooks/_harness.py`
    opens `.claude/settings.json` with `json.load`, which a BOM breaks. Both, with the attribution
    on each, in `docs/reviews/2026-09-02-model-pin-and-bom-measurement.md` (findings 5 to 7).

    The subject is DERIVED (`read_from_byte_zero`), so the JSON a hook registration lives in and the
    kit marker on line 1 of a constitution are covered by the same sentence as the role files.
    """
    if not shutil.which("git"):
        pytest.skip("git not on PATH")
    offenders = [(relative, reason) for relative, head in _heads()
                 for reason in [read_from_byte_zero(relative, head)]
                 if reason and head.startswith(BOM)]
    assert not offenders, (
        "these files begin with a UTF-8 BOM, which the reader that opens them cannot see past: %s"
        % ", ".join("%s (%s)" % pair for pair in offenders))


# The two loaders whose subject this is, named once so the counter-check can assert that BOTH are
# still represented -- a predicate that quietly lost one half would otherwise stay green on the
# other. The strings are the reason each file is in the subject, and they read out in the failure.
ROLE_LOADER = "the file sits under an agents directory"
SKILL_LOADER = "the file is named SKILL.md"


def is_a_definition_a_client_loads(relative):
    """Why this tracked file is a definition whose first bytes a parser matches -- or None.

    ONE CLAUSE PER LOADER, and each is a key the path carries in its own right: a role is any `.md`
    below an `agents` directory (`under_an_agents_directory`, imported from `test_model_pins`
    rather than restated -- a second definition of THAT NAME here is caught by `ruff` (F811), a
    second function under another name is caught by nothing), a skill is the file NAMED `SKILL.md`.

    THE SUBJECT IS WIDER THAN WHAT THE CLIENT LOADS, and that is the trade rather than an oversight.
    The measurement is section 5a of
    `docs/reviews/2026-09-02-model-pin-and-bom-measurement.md`: of five opening shapes placed under
    `agents/`, the client's own `init` list named the one whose first line is the frontmatter
    delimiter and dropped the other four without a word. Making that rule the subject would be
    circular -- the file this check exists for is a role that LOST its delimiter, and it would
    classify itself out. So the subject stays the location, and the price is friction, named here
    rather than discovered: a document filed between the roles is asked for a delimiter no loader
    wants from it. The remedy for such a file is to move it, not to widen this.

    A ROUND BEFORE THIS ONE SUBTRACTED "opens as prose" here to buy that friction back. It bought
    nothing: on the tracked tree it removed no file at all, disabling it changed no test result,
    and it recognised one spelling of "document" out of the four the client drops.
    """
    if os.path.basename(relative) == "SKILL.md":
        return SKILL_LOADER
    if under_an_agents_directory(relative):
        return ROLE_LOADER
    return None


def test_every_shipped_role_and_skill_definition_is_a_file_that_check_looks_at():
    """The other end: a definition that lost its delimiter drops OUT of the check above silently.

    Both halves are derived from the tracked tree (`is_a_definition_a_client_loads`), so a fourth
    kit and a role in a new subdirectory join the subject by existing. Red when a definition stops
    opening the way its loader expects, and red when the classifier stops recognising one.

    BOTH LOADERS HAVE TO BE REPRESENTED, asserted rather than assumed: the predicate carries two
    clauses, and a version that silently lost one would still find enough files to pass a count.
    """
    if not shutil.which("git"):
        pytest.skip("git not on PATH")
    definitions = [(relative, head, reason) for relative, head in _heads()
                   for reason in [is_a_definition_a_client_loads(relative)] if reason]
    assert len(definitions) > 20, (
        "only %d role/skill definitions found -- the tracked-file reader stopped matching the tree"
        % len(definitions))
    for loader in (ROLE_LOADER, SKILL_LOADER):
        assert any(reason == loader for _relative, _head, reason in definitions), (
            "no tracked file is in the subject because %r -- that half of the predicate now "
            "matches nothing" % loader)
    unseen = [relative for relative, head, _reason in definitions
              if not read_from_byte_zero(relative, head)]
    assert not unseen, (
        "these definitions do not open the way their loader expects, so the BOM check above never "
        "looks at them: %s" % unseen)


def _shipped_roles():
    """The role names this repo ships, off the kit's own skill directories — never typed here.

    Longest first, so a role whose name is a prefix of another cannot swallow the longer one when
    the two are searched as alternatives.
    """
    skills = os.path.join(ROOT, "team-kits", "dev-team", "skills")
    roles = [name for name in os.listdir(skills) if os.path.isdir(os.path.join(skills, name))]
    assert len(roles) > 3, roles
    return sorted(roles, key=len, reverse=True)


def _role_reports():
    """(file name, role the NAME claims) for every research report named after a shipped role."""
    roles = _shipped_roles()
    for name in sorted(os.listdir(RESEARCH)):
        if not name.endswith(".md") or not os.path.isfile(os.path.join(RESEARCH, name)):
            continue
        claimed = [role for role in roles if name[:-len(".md")].endswith(role)]
        if claimed:
            yield name, claimed[0]


def test_every_research_role_report_is_named_after_the_role_its_own_text_is_about():
    """FR-0009: five of these six carried the name of the NEXT role in the ring.

    THE CONTENT DECIDES, and the rule is one rule for all of them: the FIRST role name a report
    mentions is the role it is about. Every one of these reports opens by naming its subject — in a
    title (`# Rolle \\`product-designer\\``) or in the `Datei:`/`Gelesen:` line that says which
    SKILL.md was read — and the six shipped files agree with that reading unanimously today, which
    is what makes it a rule rather than a guess. The role vocabulary comes from the kit's skill
    directories, so a renamed or a new role moves this check with it.

    WHY A FILE NAME IS WORTH A TEST HERE. These reports are cited by role, opened by role, and
    nothing inside them repeats the file name — so a shifted name is silent: whoever looks up one
    role's findings reads the neighbour's and has no way to notice. The shift survived from
    2026-07-27 until this check, in a repo that measures nearly everything else.

    THE WAY OUT IS NOT OPEN TODAY, and claiming it was would be the over-alarming half of the same
    house rule. A report renamed to something that is not a role name does leave the subject — but
    as long as the shipped set is exactly the floor's size, the floor is an equality in effect and
    that rename trips it. The gap opens with the FIRST report ABOVE the floor, and then silently:
    the count still holds while the renamed one sits unjudged. Both directions are measured in
    `docs/reviews/2026-08-18-tsk0076-measurements.md`. So the floor counts, it does not identify —
    whoever adds a report above it inherits this sentence.
    """
    roles = _shipped_roles()
    pattern = re.compile("|".join(re.escape(role) for role in roles), re.IGNORECASE)
    reports, offences = list(_role_reports()), []
    for name, claimed in reports:
        with open(os.path.join(RESEARCH, name), encoding="utf-8") as handle:
            match = pattern.search(handle.read())
        found = match.group(0).lower() if match else None
        if found != claimed:
            offences.append(
                "%s is filed under `%s` and its own text is about `%s`" % (name, claimed, found))
    assert len(reports) >= 6, (
        "only %d research reports are named after a shipped role — the set was six when this was "
        "written, and a subject that shrinks to nothing is how this check passes over the next "
        "shift: %s" % (len(reports), [name for name, _ in reports]))
    assert not offences, (
        "a research report is filed under the wrong role, so looking up one role's findings hands "
        "over another's and nothing in the file says so:\n  " + "\n  ".join(offences))


_LEAK_SUITE = '''\
import sys

LEAK = "/tsk-0088-leaked-import-path"


def test_one_leaks_an_import_path():
    sys.path.insert(0, LEAK)
    assert LEAK in sys.path


def test_two_must_not_inherit_it():
    assert LEAK not in sys.path, "the previous test's sys.path entry survived into this one"
'''


def test_no_test_in_this_suite_leaks_an_import_path(tmp_path):
    """A test may put a directory on `sys.path`; it may not leave it there for the next test.

    WHY THIS IS THE RIGHT SUBJECT and not "is sys.path short enough": the length that broke is a
    consequence, the leak is the cause. This suite inserts its kits directory from ~100 places with
    a bare `sys.path.insert`, and a dozen tests hand the resulting list to a child process as
    PYTHONPATH; Linux refuses an envp string past MAX_ARG_STRLEN, so on the hosted ubuntu runner
    every scaffold and installer test after the crossing point died with `OSError: [Errno 7]
    Argument list too long: 'bash'` while the Windows leg -- where those tests skip for want of a
    POSIX shell -- reported the same tree green (BUG-0069).

    MEASURED THROUGH A REAL PYTEST PROCESS over this suite's own `conftest.py`, copied rather than
    imported, so what is asserted is the fixture as it ships and not an in-process re-enactment of
    it. Red without `conftest._no_test_leaks_an_import_path`: the second generated test then sees
    the first one's entry.
    """
    shutil.copy(os.path.join(ROOT, "tools", "conftest.py"), str(tmp_path / "conftest.py"))
    with open(str(tmp_path / "test_leak.py"), "w", encoding="utf-8") as handle:
        handle.write(_LEAK_SUITE)
    result = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tmp_path)],
        cwd=str(tmp_path), capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300)
    assert result.returncode == 0, (
        "a test left an entry on `sys.path` for the next one, which is the unbounded growth that "
        "made the hosted ubuntu leg refuse its own PYTHONPATH:\n%s%s"
        % (result.stdout, result.stderr))


_ENVIRONMENT_LEAK_SUITE = '''\
import os

LEAK = "HARNESS_KERNEL_PATH"


def test_one_leaks_an_environment_variable():
    os.environ[LEAK] = "/tsk-0091-leaked-kernel-redirect"
    assert LEAK in os.environ


def test_two_must_not_inherit_it():
    assert LEAK not in os.environ, "the previous test's environment variable survived into this one"
'''


def test_no_test_in_this_suite_leaks_an_environment_variable(tmp_path):
    """A test may set a variable; it may not leave it for the next test -- or its subprocesses.

    THE VARIABLE IN THE FIXTURE IS THE ONE THAT DID IT: `$HARNESS_KERNEL_PATH` redirects the
    entry point at another kernel and is authoritative by design, so a leaked one silently answers
    later tests out of this repo instead of out of the project they built. Measured on pristine
    HEAD: `test_kitupdate.py::test_the_bridge_reads_the_route_off_the_projects_own_entry_point`
    and its neighbour failed in every session where `test_hooks.py` ran first and passed alone.

    MEASURED THROUGH A REAL PYTEST PROCESS over this suite's own `conftest.py`, copied rather than
    imported, like the import-path leak above -- what is asserted is the fixture as it ships. Red
    without `conftest._no_test_leaks_an_environment_variable`: the second generated test sees the
    first one's variable.
    """
    shutil.copy(os.path.join(ROOT, "tools", "conftest.py"), str(tmp_path / "conftest.py"))
    with open(str(tmp_path / "test_env_leak.py"), "w", encoding="utf-8") as handle:
        handle.write(_ENVIRONMENT_LEAK_SUITE)
    result = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tmp_path)],
        cwd=str(tmp_path), capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300)
    assert result.returncode == 0, (
        "a test left an environment variable behind for the next one; every subprocess a later "
        "test starts inherits it, which is how a kernel redirect from one file decided another "
        "file's result:\n%s%s" % (result.stdout, result.stderr))


_LAUNCHERS = ("run", "Popen", "call", "check_call", "check_output")

# The floor under the sweep below. A reader that stops recognising the form finds nothing and
# reports every module clean, which is the shape of check this repo has been burned by twice; the
# number is here so that a narrowing shows up as a failure rather than as silence. It is a FLOOR
# and not an equality on purpose -- sites come and go, blindness does not (BUG-0069).
_POWERSHELL_LAUNCH_FLOOR = 12


def _argv_head(node):
    """The list a command line starts with, past any `[...] + list(args)` concatenation."""
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        node = node.left
    return node


def _unambiguous(assigned, node):
    """`node`, or -- when it is a name this scope assigns exactly one value -- that value."""
    if isinstance(node, ast.Name):
        values = assigned.get(node.id, [])
        return values[0] if len(values) == 1 else node
    return node


def _is_powershell_argv(node, assigned):
    node = _argv_head(_unambiguous(assigned, node))
    if not isinstance(node, (ast.List, ast.Tuple)) or not node.elts:
        return False
    first = _unambiguous(assigned, node.elts[0])
    return (isinstance(first, ast.Constant) and isinstance(first.value, str)
            and os.path.basename(first.value).lower().rsplit(".exe", 1)[0] == "powershell")


def _powershell_launches(tree):
    """Every `subprocess.*` call in `tree` whose program is the literal `powershell`.

    A name is followed only when every value assigned to it in that scope is such a command line.
    Ambiguity is left OUT rather than guessed at, and both directions of that are deliberate: a
    `command = <ps1 line> if nt else <sh line>` is chosen by the very `os.name` branch the sweep
    would look for, so nothing is lost, while treating it as a subject would flag every
    gate-payload runner that happens to reuse the name `command`.

    A parametrize row whose first element is the TOOL name `PowerShell` is not a command line and
    never reaches here -- the subject is what is handed to `subprocess`, not what looks like it.

    WHERE THIS READER STOPS, said rather than left to be discovered: the program has to be
    READABLE in the source, as a literal or as a name this scope binds to one. A launcher assembled
    at run time -- off a mapping, out of an environment variable, from a `which` result computed
    elsewhere -- is not a subject, and the sweep says nothing about it.
    """
    sites, seen = [], set()
    for scope in [tree] + [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        assigned = {}
        for node in ast.walk(scope):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assigned.setdefault(target.id, []).append(node.value)
        for node in ast.walk(scope):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in _LAUNCHERS and node.args) or id(node) in seen:
                continue
            argv = node.args[0]
            values = assigned.get(argv.id, []) if isinstance(argv, ast.Name) else [argv]
            if values and all(_is_powershell_argv(value, assigned) for value in values):
                seen.add(id(node))
                sites.append(node)
    return sites


def _asks_this_host_for_powershell(scope):
    """Does this function decide, from the HOST, whether a `powershell` exists to launch?

    Two shapes, and both are real answers rather than two spellings of one: `shutil.which
    ("powershell")` asks for the executable, and `os.name` -- in a `skipif` decorator as much as in
    an `if` -- asks for the platform that ships it. `powershell_or_skip()` needs no clause here: it
    leaves no literal command line, so it is not a subject at all.
    """
    for inner in ast.walk(scope):
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) \
                and inner.func.attr == "which":
            for argument in inner.args:
                if isinstance(argument, ast.Constant) and "powershell" in str(argument.value):
                    return True
        if isinstance(inner, ast.Attribute) and inner.attr == "name" \
                and isinstance(inner.value, ast.Name) and inner.value.id == "os":
            return True
    return False


def test_no_powershell_launch_in_this_suite_runs_without_asking_the_host_for_one():
    """A `.ps1` launcher may only be started where somebody asked whether this host has one.

    Four call sites spelled `powershell` out with no such question, and on the hosted ubuntu leg --
    which carries `pwsh`, a different product, and no `powershell` -- they died with
    `FileNotFoundError` while measuring nothing (BUG-0069). Every OTHER site in this suite already
    asked, which is why this is a sweep and not a rule about one helper: the duty is the question,
    not which helper answers it.

    THE QUESTION MAY STAND ONE LEVEL UP. A helper that carries no clause of its own is accepted
    when every caller of it in the same module does -- which is what `_scaffolded` in
    `test_kitupdate.py` and `test_presets.py` rely on, and what a rule demanding the clause AT the
    launch would have called a defect in working code.
    """
    offenders, sites = [], 0
    for path in sorted(glob.glob(os.path.join(ROOT, "tools", "*.py"))):
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), os.path.basename(path))
        parents = {child: node for node in ast.walk(tree)
                   for child in ast.iter_child_nodes(node)}
        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        guarded = {f for f in functions if _asks_this_host_for_powershell(f)}
        callers = {}
        for function in functions:
            for inner in ast.walk(function):
                if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
                    callers.setdefault(inner.func.id, set()).add(function)
        for site in _powershell_launches(tree):
            sites += 1
            chain, walker = [], site
            while walker in parents:
                walker = parents[walker]
                if isinstance(walker, ast.FunctionDef):
                    chain.append(walker)
            asked = any(function in guarded for function in chain)
            if not asked and chain:
                who = callers.get(chain[-1].name, set())
                asked = bool(who) and who <= guarded
            if not asked:
                offenders.append("%s:%d (in %s)" % (
                    os.path.basename(path), site.lineno,
                    "->".join(f.name for f in reversed(chain)) or "module level"))
    assert sites >= _POWERSHELL_LAUNCH_FLOOR, (
        "this sweep found only %d PowerShell launch(es) in tools/ -- it has stopped recognising "
        "the form, and a check that sees nothing reports everything clean" % sites)
    assert not offenders, (
        "these start a PowerShell launcher without anything on the way to them asking whether this "
        "host HAS one, so on a runner without it they report FileNotFoundError instead of saying "
        "they could not measure (BUG-0069). Remedy: `test_hooks_v2.powershell_or_skip()`, or a "
        "`shutil.which(\"powershell\")` / `os.name` clause in the test or its callers:\n  "
        + "\n  ".join(offenders))


# =================== a shipped text may not point at a decision this store does not hold (FR-0052)
_DEC_ID_RX = re.compile(r"\bDEC-\d{4}\b")
# A delimited literal: a code span, or a double-quoted span. Pairing is positional, the way
# CommonMark pairs a code span; `guard_memory_budget._CODE_SPAN_RX` pairs backticks only, and the
# double quote is added here because this corpus quotes offending PROSE as well as code.
#
# NO SINGLE-QUOTE ALTERNATIVE, and it is not an oversight. It was here for one round: in English
# prose `'…'` pairs ordinary APOSTROPHES, so a possessive opens a span that runs to the next
# apostrophe and blinds the reader to everything between. A delimiter a language also uses as a
# letter cannot mark a literal. Measured over the shipped tree 2026-08-29, the alternative was the
# ONLY thing hiding one span -- and it was `team-kits/model_tiers.yaml` line 31, "DEC-0034's T3
# rung", in the very file this reader cites as the pointer form it generalises (126 pointers judged
# without it, 125 with).
_DELIMITED_RX = re.compile(r"`[^`\n]*`|\"[^\"\n]*\"")


def _dec_citations(text):
    """Every match in `text` that CITES a decision of this repo's store, as match objects.

    THE DEFINITION, because "every DEC id" is not it. A shipped kit file also EXHIBITS ids: the file
    name inside a measured command line, the literal in a byte measurement, the quoted prose a
    guard's docstring shows as its own false positive. Those are DATA the sentence is about, and in
    this tree data is written inside a delimiter. So an id is a CITATION unless it sits inside a
    delimited literal whose content is MORE than the id itself; a span that is exactly the id stays a
    citation, because that is the pointer form this round generalises (`team-kits/model_tiers.yaml`
    writes its two that way).

    WHAT THIS DOES NOT READ, said here rather than discovered later, and stated as the MECHANISM
    rather than as an example of it: ANY id inside a delimiter longer than itself is unjudged,
    whatever the delimited text is. Measured on the shipped tree 2026-08-29, twenty-two double-quoted
    spans carry an id. Six of them are the DATA this exemption is for (three measured command paths,
    three quoted illustrations). The other sixteen are text somebody READS -- thirteen kernel refusal
    and briefing messages (`kernel/cli.py`, `kernel/migrate.py`, `kernel/state.py`,
    `kernel/dispatch.py`, `kernel/checkpoints.py`) and three handover-marker literals -- and a
    pointer that rots in one of those rots in front of a user at the moment a gate refuses. The other
    direction: in bare prose the reader cannot tell a citation from an illustration, so an
    illustrative id written without delimiters is reported although nothing rots -- the same error
    direction `guard_memory_budget` chose for the same ambiguity, with the same remedy: delimit it.
    """
    exempt = [(span.start(), span.end()) for span in _DELIMITED_RX.finditer(text)
              if not _DEC_ID_RX.fullmatch(span.group(0)[1:-1].strip())]
    return [hit for hit in _DEC_ID_RX.finditer(text)
            if not any(start <= hit.start() < end for start, end in exempt)]


def _shipped_kit_files():
    """(relative path, text) for every readable file under `team-kits/` -- the shipped tree."""
    kits = os.path.join(ROOT, "team-kits")
    for base, subdirs, names in os.walk(kits):
        subdirs[:] = [name for name in subdirs if name != "__pycache__"]
        for name in sorted(names):
            path = os.path.join(base, name)
            try:
                with open(path, encoding="utf-8") as handle:
                    yield os.path.relpath(path, ROOT).replace(os.sep, "/"), handle.read()
            except (OSError, UnicodeDecodeError):
                continue


def _decisions_in_the_store():
    """The DEC ids this repo holds, off the KERNEL's own layout rather than a path typed here.

    `ProjectState.active_dir` and `archive_root` are the builders every kernel write uses, so a store
    that reorganises moves this reader with it. Read rather than asked item by item: the kernel's own
    `exists_anywhere` wants the lock held, and a test that takes the state lock writes a lock file
    into canonical state to answer a read-only question.
    """
    sys.path.insert(0, os.path.join(ROOT, "team-kits"))
    from kernel.state import ProjectState
    store = ProjectState(os.path.join(ROOT, "project_memory"))
    found = set()
    for pattern in (os.path.join(store.active_dir("DEC"), "DEC-*.yaml"),
                    os.path.join(store.archive_root(), "DEC", "*", "DEC-*.yaml")):
        found.update(os.path.basename(path)[:-len(".yaml")] for path in glob.glob(pattern))
    return found


def test_every_decision_pointer_in_a_shipped_kit_file_resolves():
    """A kit file that names a DEC as its reason must name one this store still has (FR-0052).

    WHY THE SUBJECT IS DEC AND NOT EVERY ITEM TYPE, measured rather than assumed. This round adds
    pointers in the direction `team-kits/model_tiers.yaml` already goes -- a shipped line naming the
    decision behind it -- and a pointer nobody can follow is the failure this repo keeps re-learning.
    Widening the same reader to all eighteen id prefixes was run over the tree on 2026-08-29: 59
    non-resolving spans, of which the large majority are PLACEHOLDER ids of a PROJECT's store (the
    `project_memory/README.md` layout tables, the migration fixtures, a `proc_hash.py` usage line) --
    a different question, answered by a different store. DEC is the type a kit file cites as a
    REASON, and this repo's decisions are the store that answers.

    MEASURED RED before the repair of this round, over the shipped tree: three sites, seven spans.
    `kernel/kitupdate.py` cited DEC-0001 as the decision behind the update flow, and both
    `gate_write_scope.py` comments (in all three kits) named the same id -- which BUG-0020 deleted
    from this store the night it was measured and nobody restored. The id is unallocatable, so those
    three pointers could never be followed again.
    """
    store = _decisions_in_the_store()
    assert len(store) >= 40, (
        "only %d decision items found -- the store layout moved and this reader is judging every "
        "pointer against an empty set" % len(store))
    judged, offenders = 0, []
    for rel, text in _shipped_kit_files():
        for hit in _dec_citations(text):
            judged += 1
            if hit.group(0) not in store:
                offenders.append("%s:%d %s" % (rel, text[:hit.start()].count("\n") + 1,
                                               hit.group(0)))
    assert not offenders, (
        "these shipped kit files cite a decision that is in neither decisions/active/ nor "
        "archive/DEC/, so the reason they point at cannot be read:\n  " + "\n  ".join(offenders))
    assert judged >= 100, (
        "only %d decision pointers judged across team-kits/ -- the reader stopped matching, and "
        "then every assertion above is vacuously true" % judged)


def test_the_decision_pointer_reader_can_tell_a_citation_from_a_literal():
    """The floor under `_dec_citations`, so "return every id" and "return none" both fail here.

    Without it the test above rests on nothing: a reader that yielded nothing would look identical to
    a clean tree, and one that yielded everything would go red on the four measured places where a
    kit file EXHIBITS an id instead of citing one. Each probe below is the shape of one of them.
    """
    def found(text):
        return [hit.group(0) for hit in _dec_citations(text)]

    assert found("the reason is DEC-0034") == ["DEC-0034"]          # bare prose: a citation
    assert found("`DEC-0034` records the ladder") == ["DEC-0034"]   # the model_tiers.yaml form
    # A POSSESSIVE IS NOT A DELIMITER. With `'…'` among the alternatives this line read as one
    # literal and the pointer vanished -- the regression that cost model_tiers.yaml:31 a round.
    assert found("the kit's endpoints sit on DEC-0034's ladder") == ["DEC-0034"]
    assert found("`project_memory/decisions/active/DEC-0001.yaml`") == []   # a measured path
    assert found("the literals `id: DEC-0000` and `status: VALID`") == []   # a byte measurement
    assert found('"a DEC-2100 controller" reads as a decision id') == []    # quoted prose
    assert found("`rm -f \"x/DEC-0001.yaml\"` rc 0") == []                  # a measured command


# ============ a shipped kit file may not point at a test that does not exist (SR-0008) ==========
#
# The pointer form the house rule asks for on the OTHER side of the line. `.claude/hooks/` has its
# own reader for this (`test_gates._points_into_this_file`), and it only ever resolves names into
# ONE file -- its own suite. A kit hook cites across files, so the shape it can be held to is the
# FULLY QUALIFIED one: a file plus a name in it. That is also the only shape that is unambiguous
# here -- a bare `test_something` in kit prose is as often a fixture, a directory or a suite name.
#
# WHAT STAYS UNREAD, named rather than discovered later: a citation that gives only the test NAME,
# and a name written outside backticks. Measured over the shipped tree with the wider reader (every
# `test_*` word, backticks or not): 114 distinct names, 136 sites that resolve to nothing -- almost
# all of them suite FILE names (`test_hooks_v2`) or halves of a name broken across a line. A reader
# that reported those would be a reader nobody could keep green, and it is the qualified half that
# carries a rotting claim to a reviewer anyway.
#
# THE NAME MUST BE A TEST NAME, which is the difference between a node id and a module-qualified
# CONSTANT written with the same separator (`test_gates.py::RESERVED_WORD_CELLS`). The subject here
# is a claim answered for by a TEST; a constant cited that way points at something this reader has
# no business resolving.
_NODE_ID_RX = re.compile(r"\A(?P<path>[\w./-]*test_[\w-]+\.py)::(?P<name>test_\w*)\Z")
# THE CONTINUATION FORM, and it is the shape the sentences this round landed are written in:
# a first citation gives the file, every further one gives only `::<name>`. Measured
# 2026-09-05 (merge verify round 1, M1): with the file part demanded, mutating
# `::test_a_seam_both_orders_declare_lets_the_second_lease_through` to a name that does not
# exist left the sweep green, so the arbiter the merge protocol names covered half of what
# it claimed.
#
# WHAT IT IS READ AGAINST is the last file citation ANYWHERE ABOVE IT IN THE SAME FILE, not in
# the same sentence or paragraph -- there is no paragraph boundary in this reader, and saying
# there was one was this comment's own error (merge verify round 2, R2-M2). The cost of the
# wider carry is over-refusal: a continuation far below an unrelated citation is resolved
# against that file and reports as unresolved when the name lives elsewhere. It can also read
# a citation as resolved when the carried file happens to define the same name -- so a shipped
# text that writes the form keeps it next to the citation it continues.
# A span of this form with NO file citation before it stays unread, which is the same line the
# module comment above draws for a bare name.
_CONTINUATION_RX = re.compile(r"\A::(?P<name>test_\w*)\Z")
# A CODE SPAN THAT MAY CROSS LINES, which is why `_DELIMITED_RX` above is not reused: that one is
# line-bounded, and a line-bounded reader is blind to the wrapped citation -- which is the shape the
# one real offender of this round was written in. Measured: with the line-bounded span the sweep
# below found 0 offenders over the unrepaired tree; with this one, 1.
_CODE_SPAN_RX = re.compile(r"`([^`]+)`", re.DOTALL)
# WHERE A SUITE FILE LIVES when the citation gives no directory -- the two directories this repo
# collects tests from. `.claude/hooks/test_gates.py` is not run by `pytest tools/` and is still a
# suite of this repo, so a hole entry citing it must resolve here too.
_SUITE_DIRS = ("tools", ".claude/hooks")


def _test_citations(text):
    """(offset, file, test name) for every pytest node id `text` cites, out of its backtick spans.

    GLUED BEFORE IT IS READ, and whitespace is not the only thing taken out: these names are long
    enough that they wrap, and the next line continues with a comment marker of its own. A name read
    as two halves resolves to nothing, and the check would then depend on where an editor broke the
    line rather than on what the statement claims. Citations in the shipped tree are written that
    way, the round's own offender among them.

    THE DECORATION AROUND A NODE ID IS NOT PART OF IT: a parametrised case is cited by its case id,
    and a span at the end of a sentence carries the punctuation. Both are cut, which is what makes
    `test_the_test_pointer_reader_reads_the_shapes_a_kit_file_writes` a floor rather than a
    restatement.
    """
    found = []
    carried = None
    for span in _CODE_SPAN_RX.finditer(text):
        glued = re.sub(r"[\s#]+", "", span.group(1))
        glued = re.sub(r"\[[^\]]*\]\Z", "", glued).rstrip(".,;:)")
        hit = _NODE_ID_RX.match(glued)
        if hit:
            carried = hit.group("path")
            found.append((span.start(), carried, hit.group("name")))
            continue
        more = _CONTINUATION_RX.match(glued)
        if more and carried:
            found.append((span.start(), carried, more.group("name")))
    return found


def _defined_in(cited):
    """The function names the suite file `cited` names, or `None` when there is no such file.

    A citation without a directory is looked for in the suite directories, because that is how these
    sentences are written -- the hole list says `test_gates.py::…` and means the one file of that
    name this repo has.

    Parsed, never searched: a name that appears in a docstring is not a test, and a check satisfied
    by its own prose is the failure mode this repo has hit twice.
    """
    candidates = [cited] if "/" in cited else ["%s/%s" % (one, cited) for one in _SUITE_DIRS]
    for candidate in candidates:
        path = os.path.join(ROOT, *candidate.split("/"))
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        return {node.name for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return None


def _texts_that_answer_for_a_claim():
    """(relative path, text) for every file of this repo that answers for a claim with a test.

    The shipped kit tree, plus this repo's own `docs/` -- the hole list is where "here is the test
    that would notice" carries the most weight, and `.claude/hooks/test_gates.py` already holds the
    UNQUALIFIED half of that claim (a bare name there must resolve inside test_gates.py itself). The
    two readers do not overlap: that one skips any span carrying a dot, this one requires the file.

    `docs/research/` is out, and the reason is what it holds: field notes ABOUT other projects,
    which cite those projects' suites (`tests/perf/test_pricing.py::test_p95` is one). A pointer
    into a suite this repo does not have is not a claim this repo can keep. That ONE directory, by
    its full path and not by its name -- `research-team/templates/project_memory/research/` is a
    shipped state directory and has nothing to do with it.
    """
    excluded = os.path.join(ROOT, "docs", "research")
    for top in ("team-kits", "docs"):
        for base, subdirs, names in os.walk(os.path.join(ROOT, top)):
            subdirs[:] = [name for name in subdirs
                          if name != "__pycache__"
                          and os.path.join(base, name) != excluded]
            for name in sorted(names):
                path = os.path.join(base, name)
                try:
                    with open(path, encoding="utf-8") as handle:
                        yield os.path.relpath(path, ROOT).replace(os.sep, "/"), handle.read()
                except (OSError, UnicodeDecodeError):
                    continue


def test_every_test_pointer_this_repo_writes_resolves():
    """A statement that answers for a claim by naming a test must name one that exists (SR-0008).

    A property claim becomes a test and the sentence NAMES it -- that is the whole mechanism by which
    a claim rots visibly instead of quietly. A named test that does not exist puts the mechanism back
    where it started, and worse: the sentence now reads as measured.

    MEASURED RED on the tree before the repair of this round: 122 node ids judged in `team-kits/`,
    ONE unresolved -- `office-team/hooks/_duties.py` gave the session-start budget arithmetic to
    `tools/test_hooks_v2.py`, while the test lives in `tools/test_office_duties.py`. The claim it
    carries ("raising either turns red") was true; the file it sent a reader to was not.
    """
    judged, offenders = 0, []
    for rel, text in _texts_that_answer_for_a_claim():
        for offset, path, name in _test_citations(text):
            judged += 1
            defined = _defined_in(path)
            if defined is None or name not in defined:
                offenders.append("%s:%d cites %s::%s -- %s"
                                 % (rel, text[:offset].count("\n") + 1, path, name,
                                    "no such suite file" if defined is None else "no such test"))
    assert not offenders, (
        "these statements answer for a claim with a test nobody can run, so the claim reads as "
        "measured and is not:\n  " + "\n  ".join(offenders))
    assert judged >= 150, (
        "only %d test pointers judged -- the reader stopped matching, and then the assertion "
        "above is vacuously true" % judged)


def test_the_test_pointer_reader_reads_the_shapes_a_kit_file_writes():
    """The floor under the sweep, so "read nothing" and "read every word" both fail here.

    Each probe is the shape of a citation that really stands in the shipped tree, plus the two
    non-citations the reader must stay quiet on: a suite FILE named without a test in it, and a bare
    name, which this reader deliberately does not judge.
    """
    def read(text):
        return [(path, name) for _offset, path, name in _test_citations(text)]

    one = ("tools/test_office_duties.py", "test_a_project_that_owes_nothing_gets_no_paragraph")
    assert read("measured by `%s::%s`" % one) == [one]
    assert read("measured by `%s::\n    # %s` today" % one) == [one], "a wrapped node id"
    assert read("`%s::%s[Bash]` covers it." % one) == [one], "a parametrised case id"
    assert read("see `%s::%s`." % one) == [one], "a full stop inside the span"
    assert read("the budget lives in `tools/test_office_duties.py`") == [], "a file is not a name"
    assert read("held by `test_a_project_that_owes_nothing_gets_no_paragraph`") == [], (
        "an unqualified name is the half this reader does not judge -- see the comment above")
    assert read("`test_gates.py::RESERVED_WORD_CELLS` is a table") == [], (
        "a module-qualified constant is not a test pointer")
    second = (one[0], "test_the_session_start_hook_names_the_tax_deadline_the_profile_declares")
    assert read("held by `%s::%s` and `::%s`" % (one[0], one[1], second[1])) == [one, second], (
        "the CONTINUATION form -- a second citation in one statement that gives only `::<name>` "
        "-- is the shape the constitutions and the parallel-streams skills write, and it went "
        "unread until 2026-09-05 (merge verifier round 1, M1)")
    assert read("held by `::%s`" % one[1]) == [], (
        "a continuation with no file citation before it names no file, so it stays unread")
    assert one[1] in _defined_in(one[0])
    assert _defined_in("test_gates.py"), "a bare suite file name must resolve in a suite directory"
    assert _defined_in("tools/test_no_such_suite.py") is None
    assert _defined_in("test_no_such_suite.py") is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))


# ---------------- a hole lives in three places, and they answer to each other -------------------

# One row of the hole index: the first cell as the renderer writes it -- a linked H-number where a
# prose file exists, the bare number where none does (`kernel.holes._prose_link`) -- and the item id.
_HOLE_ROW_RX = re.compile(
    r"^\|\s*(\[H\d+\]\(docs/holes/H\d+\.md\)|H\d+)\s*\|\s*(BUG-\d+)\s*\|", re.MULTILINE)
_HOLE_LINK_RX = re.compile(r"^\[(H\d+)\]\(docs/holes/(H\d+)\.md\)$")


def _hole_order(name):
    """H10 must not sort before H2 in a message a human reads."""
    return int(name[1:])


def _holes_in_the_store():
    """{hole number: item id} over every BUG this store holds, active or archived.

    Off the KERNEL's own layout for the reason `_decisions_in_the_store` gives, and reading the
    FIELD rather than the id: `hole_number` is what makes a bug a hole (`backlog_types`), so a
    renumbering or a re-filing moves this reader with it.
    """
    sys.path.insert(0, os.path.join(ROOT, "team-kits"))
    import yaml
    from kernel.state import ProjectState
    store = ProjectState(os.path.join(ROOT, "project_memory"))
    found = {}
    for pattern in (os.path.join(store.active_dir("BUG"), "BUG-*.yaml"),
                    os.path.join(store.archive_root(), "BUG", "*", "BUG-*.yaml")):
        for path in sorted(glob.glob(pattern)):
            with io.open(path, encoding="utf-8") as handle:
                body = yaml.safe_load(handle) or {}
            if body.get("hole_number"):
                found[str(body["hole_number"])] = body.get("id")
    return found


def test_every_hole_is_one_index_row_one_prose_file_and_one_item():
    """The hole index of `docs/POST_V2_WISHLIST.md`, its prose files, and the items -- all three
    ways, and the reader that closes BUG-0258 / H176: the guard that stood here was RED from
    b7f282e on because the migration had removed both of its subjects, so nothing held entry and
    overview against each other at all.

    WHY THIS SUBJECT AND NOT THE OLD ONE: until the migration (TSK-0126, `migrate-holes`) a hole was
    a `### H<n>` section of that document plus a row in a summary table, and the guard here compared
    those two. The migration made every hole an ITEM (`BUG` with `hole_number`), moved the full text
    to `docs/holes/H<n>.md` and replaced the table with an index of links -- so the old guard's two
    subjects both stopped existing, it found zero entries against a floor of 90, and it was red on
    every run from b7f282e on. Measured on that commit: 0 `### H<n>` headings, 155 index rows.

    HELD IN FOUR DIRECTIONS, since any one alone rots: a row that LINKS at a prose file which is
    gone points into nothing, a prose file with no row is invisible in the index a reader opens, an
    item with no row is a gap nobody sees there, and a row naming a different item than the item
    itself claims is two answers to one question. The subjects are DERIVED each time -- the rows out
    of the document, the files out of the directory, the numbers out of the items' own `hole_number`
    field -- so nothing here is a list that has to be maintained.

    AN UNLINKED ROW IS NOT A FINDING, and that is the second half of this round's repair: only the
    migration writes a prose file, so a hole captured afterwards has none and its row carries the
    bare number (`kernel.holes._prose_link`). Measured before that repair: nine rows of this
    document linked at files that were never written (H166-H173).
    """
    path = os.path.join(ROOT, "docs", "POST_V2_WISHLIST.md")
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    rows, linked, mislinked = {}, set(), []
    for hit in _HOLE_ROW_RX.finditer(text):
        link = _HOLE_LINK_RX.match(hit.group(1))
        number = link.group(1) if link else hit.group(1)
        rows[number] = hit.group(2)
        if link:
            linked.add(number)
            if link.group(1) != link.group(2):
                mislinked.append(number)
    files = {os.path.basename(name)[:-len(".md")]
             for name in glob.glob(os.path.join(ROOT, "docs", "holes", "H*.md"))}
    items = _holes_in_the_store()
    assert len(rows) >= 90, (
        "only %d index rows found -- the reader stopped matching the document" % len(rows))
    assert not mislinked, (
        "these rows link at a prose file of another hole: %s" % ", ".join(sorted(mislinked)))
    assert not sorted(linked - files, key=_hole_order), (
        "these index rows link at a prose file that does not exist: %s"
        % ", ".join(sorted(linked - files, key=_hole_order)))
    assert not sorted(files - set(rows), key=_hole_order), (
        "these prose files have no row in the index, so a reader of it never finds them: %s"
        % ", ".join(sorted(files - set(rows), key=_hole_order)))
    assert not sorted(files - linked, key=_hole_order), (
        "these prose files exist while their row does not link at them: %s"
        % ", ".join(sorted(files - linked, key=_hole_order)))
    assert not sorted(set(items) - set(rows), key=_hole_order), (
        "these hole ITEMS have no row in the index: %s"
        % ", ".join("%s (%s)" % (name, items[name]) for name in sorted(set(items) - set(rows),
                                                                       key=_hole_order)))
    disagreeing = sorted((name for name, bug in rows.items() if items.get(name) != bug),
                         key=_hole_order)
    assert not disagreeing, (
        "the index and the store name different items for these holes: %s"
        % ", ".join("%s: index %s, store %s" % (name, rows[name], items.get(name))
                    for name in disagreeing))


# ---------------- prose under docs/ that nothing reads any more (FR-0036) ----------------------

# How long a docs file may sit unread before the hint names it. The reporter must not nag a file
# that is still going to be read: this repo has a docs report that lay unreferenced for weeks and
# then became the source a SHIPPED skill cites. The interval that was measured, and the reason this
# number stands above it rather than at it, are in FR-0036's round protocol -- not repeated here,
# because a number in a second place is the defect SR-0008 is about.
_DOCS_GRACE_DAYS = 60


def _is_a_record(rel):
    """True where this file lies in an ARCHIVE, so what it names it records rather than reads.

    One rule for both archives this repo keeps -- the item store's and `docs/archive/` -- because
    they are the same thing said about two kinds of paper. An archived item RECORDS the decision
    that once named a document; the archive's own index RECORDS the move it carried out. Neither
    reads the file today, and if either counted as reading, nothing could ever be archived at all:
    the index a move writes would keep its own subject alive for ever.

    It also decides what the hint may NAME: a file inside an archive is unread on purpose, and it
    is where this reporter's own remedy puts things, so naming it again would make the hint grow
    without end. Both halves are measured -- `test_the_docs_wire_reader_answers_both_ways` for the
    pointer half, `test_every_archived_file_is_named_by_the_index_above_it` for the file half.
    """
    return "archive" in rel.split("/")

# A pointer is a WHOLE file name, and both ends of it have to be said. On the left, a name may be
# preceded by anything a file name is not -- which is how `docs/pilot/x.md` counts for `x.md` while
# `prefix-x.md` does not. On the right the dot is deliberately allowed through, so a name at the end
# of a sentence still reads, while a longer suffix does not: without this half `run.json` matched
# inside `run.jsonl`, and the live-log files under `docs/reviews/` were reported unread while a
# review protocol cited every one of them (measured for FR-0036; how many they are and how big
# that block is belongs in the round protocol, because both grow).
_NAME_BOUNDARY = r"(?<![A-Za-z0-9_.-])"
_NAME_END = r"(?![A-Za-z0-9_-])"


def _carried_under(prefix):
    """Every file the repo CARRIES under `prefix`, repo-relative.

    Both subjects in this section -- the documents the hint may name and the archive the tripwire
    judges -- are the files the REPO carries, never the files the filesystem happens to hold, and
    they read it through the same door as the corpus does. A walk with a skip list was the defect:
    an ignored artifact under `docs/archive/` (a `*.log` a tool leaves behind, a `Thumbs.db` the
    Explorer writes -- both refused by `.gitignore`) is neither archived prose nor a document, and
    it turned `test_every_archived_file_is_named_by_the_index_above_it` hard red on a tree nobody
    had changed. Measured before and after in FR-0036's rework rig (`rework1/b2_ignored.py`).
    """
    prefix = prefix.rstrip("/") + "/"
    return [rel for rel in _carried_files() if rel.startswith(prefix)]


def _docs_candidates():
    """Every file the repo carries under `docs/`, outside an archive, that the hint may name."""
    return sorted(rel for rel in _carried_under("docs") if not _is_a_record(rel))


def _wire_class(rel):
    """Which kind of wire a pointer FROM this file would be, or None where it is a record.

    Derived from what the file is FOR, never from a list of names. The four kinds are FR-0036's,
    and one of them is WIDER than the work order's wording -- named here rather than left to be
    believed: CODE under `tools/` or `.claude/hooks/` that spells the name, which INCLUDES a test
    that reads the file and is not limited to one. Measured for FR-0036 on this tree, documents
    exist whose CODE class comes from no test at all: two review protocols under `docs/reviews/`
    are named only by `.claude/hooks/_harness.py` -- the gates' shared body -- and one of them also
    by `gate_lead_write_scope.py` (`rework1/n3_code_class.py`). Both carry other wires besides;
    what they do NOT have is a test. Calling this class TEST was a claim the reader does not build,
    which is why it is called CODE. Then the hole list; canonical state (an Evidence
    `artifact_ref` or a living item's `source:`); and -- added because the measurement found it and
    the work order did not -- a SHIPPED kit file, which is code that ships rather than a note
    somebody may drop.

    EVERYTHING ELSE THE REPO CARRIES IS PROSE, and that is the fifth kind rather than a hole: a
    document named only in `README.md`, in a role definition under `.claude/agents/` or in a
    round protocol is named, and the hint has to stay quiet about it. Falling through to None
    instead would have made the reader narrower than the pass that decided FR-0036's first move
    set, which read the whole tree by hand -- and narrower in the loud direction.

    `project_memory/staging/` is PROSE and not ITEM for the same honesty: staging holds proposals
    that are not state yet (CLAUDE.md, "Der Zustand dieses Projekts"). Either way it keeps a file
    out of the hint; the class is what the failure message claims, so it may not claim canon.
    """
    if _is_a_record(rel):
        return None
    if rel.endswith(".py") and (rel.startswith("tools/") or rel.startswith(".claude/hooks/")):
        return "CODE"
    if rel == "docs/POST_V2_WISHLIST.md":
        return "HOLE"
    if rel.startswith("project_memory/staging/"):
        return "PROSE"
    if rel.startswith("project_memory/"):
        return "ITEM"
    if rel.startswith("team-kits/"):
        return "KIT"
    return "PROSE"


def _joined_literals(tree):
    """Every path an `os.path.join(...)` in `tree` spells out in literals.

    WHY THIS IS NOT OPTIONAL, and it is the half a text search cannot have: the wire that keeps the
    six role reports alive is `RESEARCH = os.path.join(ROOT, "docs", "research")` in this very file
    -- a test that reads the DIRECTORY and never writes any single file's path. A reader that only
    looked for spelled-out paths would report all six as unread and invite somebody to archive the
    subject of `test_every_research_role_report_is_named_after_the_role_its_own_text_is_about`.

    The literals are the leading RUN after any non-literal head (`ROOT`), and the run stops at the
    first non-literal, so a `join(ROOT, "docs", name, "x.md")` contributes `docs` and not a spliced
    path no call ever produces.

    A FIXTURE PATH IS READ HERE TOO and cannot be told apart -- `os.path.join(snapshot, "docs",
    "legacy.md")` in `test_kitupdate.py` builds a path inside a temporary tree, and this reader sees
    the same two literals a real pointer would leave. Today those name files and wire nothing; a
    fixture that named a real directory would wire everything under it. That error makes the hint
    say LESS, which is the direction it is allowed to be wrong in.
    """
    out = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "join"):
            continue
        run, started = [], False
        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                run.append(argument.value)
                started = True
            elif started:
                break
        if run:
            out.add("/".join(part.strip("/") for part in run).strip("/"))
    return out


def _wires_over(candidates, corpus, directories=()):
    """{docs path: {wire class, ...}} for `candidates`, read out of `corpus` and `directories`.

    `corpus` is (relative path, text) pairs; `directories` are path fragments a RUNNING test builds
    with `os.path.join`, which wire every file beneath them as CODE. Both are parameters rather than read
    inside, so the floor test below can hand this reader a corpus it controls and see both answers.

    THE SUBJECT IS THE FILE NAME, and there is deliberately no second reader for the full path. An
    earlier draft had both, and the path half turned out to decide nothing: a pointer that spells
    the path contains the name, so every wire the path half found the name half found too, and no
    mutation of it could go red. It also needed a list of file EXTENSIONS to know what a name looks
    like -- an enumeration, and the wrong kind: the alternation here is built from the candidates
    themselves, so it can never be short by a suffix nobody thought of.

    WHAT IT COSTS, stated rather than left to be found: a candidate whose name is generic enough
    to turn up in a sentence about something else is wired by that sentence -- `docs/` does carry
    such names. Which ones they are on a given day is a measurement and belongs in FR-0036's round
    protocol, not in a comment that would rot; what belongs here is the direction of the error,
    which is the hint saying LESS, and that is the one it may err in.
    """
    wires = {rel: set() for rel in candidates}
    if not candidates:
        return wires
    by_name = {}
    for rel in candidates:
        by_name.setdefault(os.path.basename(rel), []).append(rel)
    reader = re.compile(_NAME_BOUNDARY + "(?:%s)" % "|".join(
        re.escape(name) for name in sorted(by_name)) + _NAME_END)
    for holder, text in corpus:
        klass = _wire_class(holder)
        if klass is None:
            continue
        for name in set(reader.findall(text)):
            for rel in by_name.get(name, ()):
                if rel != holder:
                    wires[rel].add(klass)
    for fragment in directories:
        prefix = fragment.rstrip("/") + "/"
        for rel in candidates:
            if rel.startswith(prefix):
                wires[rel].add("CODE")
    return wires


# Beyond this a file is not prose anybody points with, and reading it would cost the round more
# than the answer is worth. One constant, two readers: the corpus and the test that checks it drops
# nothing else.
_TOO_BIG_FOR_PROSE = 4_000_000


def _require_git():
    """Skip unless git can answer at all: on PATH, and standing in a work tree.

    ONE ANSWER TO ONE QUESTION, and the second half was bought with a false promise. The corpus is
    git's own answer to what this repo carries, so where git cannot answer there is no reader --
    and a reader that found nothing reports every document as unread. The hint above calls itself
    fail-open; measured on a `git archive` extract (a tree with no `.git` at all), four members of
    this file FAILED instead of skipping, the hint among them. The two members that predate this
    section asked the fuller question already and skipped cleanly, so the file held two answers to
    one question -- they now ask it here, in one place.
    """
    if not shutil.which("git"):
        pytest.skip("git not on PATH")
    if subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT,
                      capture_output=True, text=True).returncode != 0:
        pytest.skip("not a git work tree")


def _carried_files():
    """Every path this repo CARRIES, repo-relative: tracked, or new and not ignored.

    The subject is git's own answer to "is this file part of me", and it is that rather than a walk
    with a skip list for the same reason the wire classes are derived: a list of caches to step over
    is an enumeration, and a build tool nobody has installed yet adds the next entry to it.
    """
    result = subprocess.run(
        ["git", "ls-files", "-c", "-o", "--exclude-standard", "-z"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if result.returncode != 0:
        raise AssertionError(
            "git could not list what this repo carries, so nothing below has a subject: %s"
            % result.stderr.strip()[:300])
    # `-z` because a path is not a line: git quotes anything else, and a quoted path is a path this
    # reader would then have to un-quote.
    return sorted(part for part in result.stdout.split(chr(0)) if part)


def _reference_corpus():
    """(relative path, text) for everything this repo CARRIES that can hold a pointer into `docs/`.

    WHY THE WHOLE REPO AND NOT THE DIRECTORIES THAT OBVIOUSLY HOLD POINTERS: the first cut read
    five named tops (`tools`, `.claude/hooks`, `team-kits`, `docs`, `project_memory`), while the
    manual pass that decided FR-0036's move set read the whole tree -- so the instrument that
    SHIPS was blind to `README.md`, `HARNESS_LOG.md`, `.claude/agents/` and `install.sh`, and a
    document cited only from one of those would have been reported as unread. Measured on the tree
    of 2026-09-02, the wider corpus changes one file's wire set and no move decision; the reason to
    widen it is not today's answer but that the narrow one errs in the LOUD direction, which is the
    one this hint may not err in.
    """
    for rel in _carried_files():
        full = os.path.join(ROOT, rel.replace("/", os.sep))
        try:
            if os.path.getsize(full) > _TOO_BIG_FOR_PROSE:
                continue
            with io.open(full, encoding="utf-8") as handle:
                text = handle.read()
        except (OSError, UnicodeDecodeError):
            continue
        yield rel, text


def _directory_wires():
    """Path fragments the RUNNING tests build with `os.path.join`, off their parsed source."""
    fragments = set()
    for pattern in (os.path.join(ROOT, "tools", "*.py"),
                    os.path.join(ROOT, ".claude", "hooks", "*.py")):
        for path in sorted(glob.glob(pattern)):
            try:
                with io.open(path, encoding="utf-8") as handle:
                    tree = ast.parse(handle.read(), os.path.basename(path))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            fragments |= {f for f in _joined_literals(tree) if f.startswith("docs/")}
    return fragments


def _age_in_days(rel):
    """Days since the last commit that touched `rel`, or None when git cannot say."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%ct", "--", rel],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    stamp = result.stdout.strip()
    if result.returncode != 0 or not stamp.isdigit():
        return None
    return (time.time() - int(stamp)) / 86400.0


def _stale_unwired(wires, age_of):
    """The files the hint names: no wire at all, and last touched longer ago than the grace period.

    Split out of the report below with `age_of` as a parameter for one reason: on the tree as it
    stands the list is EMPTY, so a threshold left inside the report would be a rule nothing ever
    exercised -- `test_the_docs_hint_fires_only_past_the_grace_period` hands it two ages and reads
    both answers.
    """
    named = []
    for rel in sorted(wires):
        if wires[rel]:
            continue
        age = age_of(rel)
        if age is not None and age > _DOCS_GRACE_DAYS:
            named.append("%s (%d days)" % (rel, age))
    return named


def _report_stale(stale):
    """Emit the hint. A warning and not an assertion, on purpose -- see the report test."""
    if stale:
        warnings.warn(
            "docs prose nothing reads any more, last touched over %d days ago -- candidates for "
            "docs/archive/<year>/, to be judged one by one and never moved on doubt (FR-0036):\n  "
            % _DOCS_GRACE_DAYS + "\n  ".join(stale), UserWarning)


def test_docs_prose_nothing_reads_any_more_is_reported_not_failed():
    """A hint for the lead, deliberately FAIL-OPEN over WHAT it finds: it names files, and no
    finding of its own ever blocks a round.

    IT DOES BLOCK WHEN THE REPO ITSELF CANNOT BE READ, and that is the honest half of the sentence:
    fewer than 20 candidates under `docs/`, or `git ls-files` failing while git is on PATH and a
    work tree is there, are not judgements about a document -- they say this reader has no subject,
    and a reader without a subject would otherwise report every file as unread
    (`test_a_corpus_that_cannot_be_listed_says_so_instead_of_reading_as_empty`). Where git cannot
    answer at all, `_require_git` skips instead.

    WHY A REPORT AND NOT A GATE (DEC-0056, no scaffolding beyond the house): whether a document is
    still wanted is a judgement. FR-0036's own pass found a handback whose patches no longer apply
    but which still names two OPEN bugs, and a research report that lay unread for weeks and then
    became a shipped skill's source. A check that failed on either would have been wrong both times,
    and the remedy for a wrong failure is to weaken it until it says nothing. So this warns.

    THE SUBJECT IS DERIVED, not listed: every file under `docs/` outside `docs/archive/` that
    NOTHING THE REPO CARRIES names -- no code under `tools/` or `.claude/hooks/`, no hole entry, no
    living item, no shipped kit file and no other prose either -- and whose last commit is older
    than `_DOCS_GRACE_DAYS`. Prose counts, although it is the weakest of the five kinds
    `_wire_class` knows, for the same reason as the grace period: any of them keeps a file out of
    the hint. `docs/archive/` is out because it is where this hint's own remedy puts things.

    "WHAT THE REPO CARRIES" IS GIT'S ANSWER, AND THAT IS THE LIMIT OF THE SENTENCE: a mention in a
    file git ignores -- a run log, an audit trail, a generated dashboard -- is invisible here, so
    what this reporter may claim is "nothing git carries names it" and never "nothing names it".
    Measured on this tree for FR-0036: outside the tool caches there is no uncarried file at all,
    so the blind spot is empty today rather than merely small (`rework1/n1_ignored_corpus.py`).

    WHAT THIS DOES NOT SEE, said here rather than left to be discovered. A pointer BUILT at run time
    is invisible to it, except for the one built form it does read -- an `os.path.join` of literals,
    which is how a test names a whole directory. And it reads text, so a file named in a sentence
    that calls it obsolete counts as read. Both errors point the same way: towards saying nothing.
    That is the direction a fail-open hint should err in.
    """
    _require_git()
    candidates = _docs_candidates()
    assert len(candidates) >= 20, (
        "only %d files under docs/ -- this reporter is looking at the wrong tree" % len(candidates))
    wires = _wires_over(candidates, _reference_corpus(), _directory_wires())
    _report_stale(_stale_unwired(wires, _age_in_days))


_WIRE_PROBE_CORPUS = [
    ("tools/test_something.py", 'path = "docs/pilot/read-by-a-test.md"'),
    ("docs/POST_V2_WISHLIST.md", "die Messung steht in `docs/pilot/read-by-a-hole.md`"),
    ("project_memory/evidence/EVD-0001.yaml", "artifact_refs:\n- ../docs/pilot/read-by-an-evd.md"),
    ("project_memory/decisions/active/DEC-0001.yaml",
     "source: docs/pilot/read-by-a-decision.md, Abschnitt 2"),
    ("project_memory/archive/DEC/2026/DEC-0002.yaml",
     "source: docs/pilot/named-only-by-an-archived-item.md"),
    ("team-kits/dev-team/skills/x/SKILL.md", "see docs/pilot/read-by-a-shipped-skill.md"),
    ("docs/pilot/some-other-note.md", "compare docs/pilot/read-by-nothing-but-prose.md"),
    # Holders OUTSIDE the directories that obviously hold pointers. Both are real places this repo
    # keeps prose in, and both were invisible to the first cut of the corpus below.
    ("README.md", "der Werkstattbericht nennt docs/pilot/read-by-the-repo-readme.md"),
    (".claude/agents/harness-verifier.md", "lies docs/pilot/read-by-a-role-definition.md"),
    # The spelling a review protocol and a kit skill really use: the file name, no path.
    ("tools/test_something_else.py", 'REPORT = "named-only-by-its-file-name.md"'),
    # A name that only LOOKS like a pointer because a longer name ends with it.
    ("docs/POST_V2_WISHLIST.md", "siehe irgendwas-suffix-of-a-longer-name.md"),
    # ... and the other end: a name that is a PREFIX of the one actually cited.
    ("tools/test_logs.py", 'LOG = "run.jsonl"'),
    # A document naming ITSELF is not a reader of itself.
    ("docs/pilot/names-only-itself.md", "dies ist docs/pilot/names-only-itself.md"),
]
_WIRE_PROBE_FILES = [
    "docs/pilot/read-by-a-test.md", "docs/pilot/read-by-a-hole.md",
    "docs/pilot/read-by-an-evd.md", "docs/pilot/read-by-a-decision.md",
    "docs/pilot/named-only-by-an-archived-item.md", "docs/pilot/read-by-a-shipped-skill.md",
    "docs/pilot/read-by-nothing-but-prose.md", "docs/pilot/read-by-nothing.md",
    "docs/research/under-a-directory-a-test-walks.md",
    "docs/pilot/named-only-by-its-file-name.md", "docs/pilot/suffix-of-a-longer-name.md",
    "docs/pilot/names-only-itself.md", "docs/logs/run.json", "docs/logs/run.jsonl",
    "docs/pilot/read-by-the-repo-readme.md", "docs/pilot/read-by-a-role-definition.md",
]


def test_the_docs_wire_reader_answers_both_ways():
    """The floor under the report above, because a fail-open hint cannot fail on its own.

    A reader that found NOTHING would name every document in the repo; one that found EVERYTHING
    would name none -- and the second failure is silent, which is the shape this repo has been
    burned by. Both are asserted against a corpus this test writes, so the answers do not move when
    the tree does.

    THE DECISION SOURCE IS ITS OWN PROBE and not an example of the others. CLAUDE.md answers a
    question about the INTENDED state from `decisions/active/` first, so prose a DEC's `source:`
    points at is load-bearing exactly the way a test's subject is; FR-0036's work order asked for
    that half to be measured rather than assumed, and `read-by-a-decision.md` is the measurement.
    The counter-probe beside it is the ARCHIVED decision: a closed item's pointer is a record, not
    a reader, and a file kept alive by one could never be archived at all.
    """
    wires = _wires_over(_WIRE_PROBE_FILES, _WIRE_PROBE_CORPUS, {"docs/research"})
    assert wires["docs/pilot/read-by-a-test.md"] == {"CODE"}
    assert wires["docs/pilot/read-by-a-hole.md"] == {"HOLE"}
    assert wires["docs/pilot/read-by-an-evd.md"] == {"ITEM"}
    assert wires["docs/pilot/read-by-a-decision.md"] == {"ITEM"}
    assert wires["docs/pilot/read-by-a-shipped-skill.md"] == {"KIT"}
    assert wires["docs/research/under-a-directory-a-test-walks.md"] == {"CODE"}
    # An archived item RECORDS a decision that was made; it does not read the file today. This is
    # the one class the reader deliberately drops, and dropping it is what makes archiving possible
    # at all -- an archived TSK naming a document would otherwise keep it alive for ever.
    assert wires["docs/pilot/named-only-by-an-archived-item.md"] == set()
    # Prose naming prose is a KIND OF ITS OWN and still keeps the file out of the hint, because the
    # hint's whole job is to err towards silence. Two dead notes naming each other are a false
    # negative this accepts; a round still writing around a document is the case it buys.
    assert wires["docs/pilot/read-by-nothing-but-prose.md"] == {"PROSE"}
    # A file the repo's own README or a role definition names is NAMED. Everything the repo carries
    # can hold a pointer, so PROSE is the class a holder falls through to rather than a hole -- the
    # measured defect was a reader blind to both of these, which makes the hint speak too much.
    assert wires["docs/pilot/read-by-the-repo-readme.md"] == {"PROSE"}
    assert wires["docs/pilot/read-by-a-role-definition.md"] == {"PROSE"}
    assert wires["docs/pilot/read-by-nothing.md"] == set()
    # A pointer that spells only the FILE NAME is how a review protocol and a kit skill cite, and
    # it is the ONLY form the reader has: every assertion above is also a name hit, so without this
    # one an empty reader would still look right for the wrong reason.
    assert wires["docs/pilot/named-only-by-its-file-name.md"] == {"CODE"}
    # BOTH ENDS OF A NAME, and each one has cost this repo something. A longer name that ENDS with
    # a candidate's name is a different file; and a candidate whose name is a PREFIX of the one
    # actually cited is a different file too -- that second direction is the defect an extension
    # list had here, where `run.json` matched inside `run.jsonl`.
    assert wires["docs/pilot/suffix-of-a-longer-name.md"] == set()
    assert wires["docs/logs/run.jsonl"] == {"CODE"}
    assert wires["docs/logs/run.json"] == set()
    assert wires["docs/pilot/names-only-itself.md"] == set()


def test_the_directory_reader_takes_the_literal_run_and_stops_at_the_first_hole():
    """`_joined_literals`, on parsed source rather than on a claim about it.

    The `directories` argument above is handed in ready-made, so nothing there reaches the parser
    that produces it in the running suite. These three shapes are the ones the tree actually has: a
    directory built off `ROOT`, a single file built the same way, and a join with a variable in the
    middle -- which must contribute the run BEFORE the variable and never a spliced path.
    """
    tree = ast.parse(
        "RESEARCH = os.path.join(ROOT, 'docs', 'research')\n"
        "SPEC = os.path.join(ROOT, 'docs', 'HARNESS_V2_SPEC.md')\n"
        "OTHER = os.path.join(ROOT, 'docs', name, 'x.md')\n")
    found = _joined_literals(tree)
    assert "docs/research" in found
    assert "docs/HARNESS_V2_SPEC.md" in found
    assert "docs/x.md" not in found, (
        "a path was spliced across a variable, so a fixture could wire a file no call names: %s"
        % sorted(found))


def test_the_docs_hint_fires_only_past_the_grace_period():
    """The floor under the threshold, which the tree cannot exercise: today nothing is old enough.

    Three answers are read, because each of them has failed somewhere in this repo before: a wired
    file is never named however old it is, an unwired file YOUNGER than the grace period is not
    named either -- that is the whole point of the period, and a report without it would have nagged
    `docs/research/2026-07-27-adoption-anthropic.md` off the tree weeks before a shipped skill began
    citing it -- and an unwired file past the period reaches the warning, not an assertion.
    """
    wires = {"docs/pilot/old-and-unread.md": set(),
             "docs/pilot/young-and-unread.md": set(),
             "docs/pilot/old-but-read.md": {"CODE"}}
    ages = {"docs/pilot/old-and-unread.md": _DOCS_GRACE_DAYS + 1,
            "docs/pilot/young-and-unread.md": _DOCS_GRACE_DAYS - 1,
            "docs/pilot/old-but-read.md": _DOCS_GRACE_DAYS * 10}
    stale = _stale_unwired(wires, ages.get)
    assert stale == ["docs/pilot/old-and-unread.md (%d days)" % (_DOCS_GRACE_DAYS + 1)], stale
    with pytest.warns(UserWarning, match="old-and-unread"):
        _report_stale(stale)
    with warnings.catch_warnings(record=True) as quiet:
        warnings.simplefilter("always")
        _report_stale([])
    assert not quiet, "the hint spoke with nothing to report: %s" % [str(w.message) for w in quiet]


def test_the_running_tree_shows_every_wire_kind_this_reader_claims_to_see():
    """The second floor, on the REAL tree: each kind must occur, or it is untested here.

    The probe above proves the reader can recognise a kind; this proves the kind exists in this
    repo, so a reader that quietly stopped matching one of them cannot hide behind a corpus that
    never had it.
    """
    _require_git()
    candidates = _docs_candidates()
    wires = _wires_over(candidates, _reference_corpus(), _directory_wires())
    seen = set().union(*wires.values()) if wires else set()
    missing = {"CODE", "HOLE", "ITEM", "KIT", "PROSE"} - seen
    assert not missing, (
        "no file under docs/ is reached by a %s pointer any more -- either the tree changed or this "
        "reader stopped matching that kind, and the hint above then reports too much"
        % ", ".join(sorted(missing)))


# ---------------- the archive is accountable: what may lie there, and what may not ------------

# Where the reporter above sends prose nothing reads any more, and the one place in this file that
# spells it: `_is_a_record` decides membership everywhere else.
_ARCHIVE = "docs/archive"

# An entry in an archive index is the first backticked token in the SECOND cell of a table row,
# spelled relative to the index. THE COLUMN IS FIXED HERE AND NO HEADER IS PARSED: each index says
# in its own prose that column two holds the file, and that sentence is a promise made TO this
# reader, not one it checks. Prose beside the table is not an entry: the reason column names
# directories and tools, and a reader that took every backticked word would call each of them a
# line pointing at nothing. A pipe INSIDE a cell would split it wrongly; no index carries one, and
# this is the reader's stated limit.
_INDEX_CELL_TOKEN = re.compile(r"`([^`]+)`")


def _archive_files():
    """Every file the repo carries under `docs/archive/`, repo-relative."""
    return sorted(_carried_under(_ARCHIVE))


def _index_entries(text):
    """The files an index accounts for, as it spells them."""
    entries = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = line.split("|")
        if len(cells) < 4:
            continue
        hit = _INDEX_CELL_TOKEN.search(cells[2])
        if hit:
            entries.append(hit.group(1).strip())
    return entries


def _index_verdict(index_dir, entries, files):
    """(files no entry accounts for, entries naming a file the repo does not carry) -- both ends.

    An index is an ENUMERATION, and this repo's rule for one is that it gets a tripwire measuring
    BOTH ends: the entry that has gone dead, and the entry that was never written. A file that
    arrived in the archive with no line saying why is the second end, and it is not hypothetical --
    the four files under `docs/archive/staging-of-archived-items/` sat there for three weeks with
    no record in the archive at all, and the reason had to be recovered from a review protocol.

    Pure, and parameters rather than a walk inside, so `test_the_index_reader_answers_both_ways`
    can read both answers off a set it controls.
    """
    prefix = index_dir.rstrip("/") + "/"
    named = {entry.strip("/") for entry in entries}
    present = {rel[len(prefix):] for rel in files if rel.startswith(prefix)}
    return sorted(present - named), sorted(named - present)


def _indexed_archive():
    """{index path: (its directory, its entries, the files it is responsible for)}.

    A file belongs to the NEAREST index at or above it, so a year folder's own index accounts for
    that year and the archive's top index accounts for what lies outside one -- no file is owed
    twice and none is owed nowhere. An index never accounts for itself or for another index: an
    index is the archive's apparatus, not archived prose.
    """
    files = _archive_files()
    indexes = [rel for rel in files if os.path.basename(rel) == "README.md"]
    out = {}
    for index in indexes:
        directory = os.path.dirname(index)
        deeper = [os.path.dirname(other) + "/" for other in indexes
                  if other != index and os.path.dirname(other).startswith(directory + "/")]
        owed = [rel for rel in files
                if rel.startswith(directory + "/") and rel not in indexes
                and not any(rel.startswith(sub) for sub in deeper)]
        with io.open(os.path.join(ROOT, index.replace("/", os.sep)), encoding="utf-8") as handle:
            entries = _index_entries(handle.read())
        out[index] = (directory, entries, owed)
    return out


def test_every_archived_file_is_named_by_the_index_above_it():
    """Moving a document is the one act in this repo that makes a file hard to find again.

    WHAT ERROR THIS CATCHES, and it has occurred here (DEC-0056 asks both questions of a check;
    its point (c) keeps thoroughness maximal exactly for archived documents). On 2026-08-13 the
    closure round moved five staging directories into `docs/archive/`; one of them, TSK-0022, had
    to be brought back because three Evidence records point their `artifact_refs` into it, and an
    EVD is immutable -- `docs/reviews/2026-08-13-tsk0055-closure-round.md` records the round. The
    other four stayed, and until this index existed nothing in the archive said they were there or
    why. The cost to the legitimate path is one table row per move.

    THE SUBJECT IS WHAT GIT CARRIES, ON BOTH SIDES, and the window that leaves is measured rather
    than guessed: a deleted archive file whose deletion is not staged is still listed by
    `git ls-files`, so this passes until the deletion is staged (measured for FR-0036 -- green
    unstaged, red staged). Reading the disk beside it would answer a question this file has decided
    twice already; the archive's subject is the repo, not the filesystem.

    THE ARCHIVE IS NOT SEARCHED FOR POINTERS INTO IT, and that limit is deliberate rather than
    missed: a round protocol or a hole entry may name an archived path perfectly legitimately while
    describing the move, so a check refusing every mention would fire on the honest case. What must
    not dangle is a POINTER THAT HAS TO RESOLVE, and that is the neighbouring test on
    `artifact_ref`s.
    """
    _require_git()
    accounted = _indexed_archive()
    assert accounted, "docs/archive/ carries no index at all -- nothing here judges anything"
    for index, (directory, entries, owed) in sorted(accounted.items()):
        orphans, dead = _index_verdict(directory, entries, owed)
        assert not orphans, (
            "%s does not account for what lies under it: %s -- an archived file with no line "
            "saying why it is here is a file nobody will dare to touch again"
            % (index, ", ".join(orphans)))
        assert not dead, (
            "%s names files this repo does not carry: %s -- the subject here is what git carries, "
            "so a deletion shows up once it is staged" % (index, ", ".join(dead)))
    covered = {rel for _, (_, _, owed) in accounted.items() for rel in owed}
    stray = [rel for rel in _archive_files()
             if rel not in covered and os.path.basename(rel) != "README.md"]
    assert not stray, (
        "no index above these files accounts for them -- a new archive folder needs its own "
        "README.md index: %s" % ", ".join(stray))


def test_the_index_reader_answers_both_ways():
    """The floor under the tripwire above: it has to say YES and NO on a set this test controls.

    A comparator that returned nothing would pass on any archive at all, which is the silent half
    of an enumeration going wrong. Three answers: the matched case, the file no entry names, and
    the entry naming a file that is not there.
    """
    entries = _index_entries(
        "| verschoben am | Datei | Grund |\n"
        "|---|---|---|\n"
        "| 2026-09-02 | `pilot/moved.md` (aus `docs/pilot/`) | kein Verweis |\n"
        "| 2026-09-02 | `pilot/gone.md` | kein Verweis |\n"
        "beside the table, `tools/test_repo_hygiene.py` is named and is not an entry\n")
    assert entries == ["pilot/moved.md", "pilot/gone.md"], entries
    orphans, dead = _index_verdict(
        "docs/archive/2026", entries,
        ["docs/archive/2026/pilot/moved.md", "docs/archive/2026/pilot/arrived-silently.md"])
    assert orphans == ["pilot/arrived-silently.md"], orphans
    assert dead == ["pilot/gone.md"], dead
    assert _index_verdict("docs/archive/2026", ["pilot/moved.md"],
                          ["docs/archive/2026/pilot/moved.md"]) == ([], [])


# ---------------- evidence must name a file that is there (FR-0036) --------------------------

_STORE = os.path.join(ROOT, "project_memory")

# An `artifact_ref` value, in the two shapes the store writes: a block list under the key, and the
# inline list on the key's own line. The key name is read whole -- singular and plural are the same
# field with the same duty, and a reader that knew only one would call the other one absent.
_YAML_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):")
_YAML_ITEM = re.compile(r"^\s*-\s+(\S.*?)\s*$")


def _refs_in(text):
    """Every `artifact_ref`/`artifact_refs` value in one YAML document, as written.

    The key is read at the document's top level, which is where the kernel writes it: when this was
    measured for FR-0036, not one document in the store carried an indented one. How many carry it
    at all is in the round protocol -- that count grows with every round, and a growing number in a
    comment is a number that will be wrong.
    """
    out, collecting = [], False
    for line in text.splitlines():
        key = _YAML_KEY.match(line)
        if key:
            collecting = key.group(1) in ("artifact_ref", "artifact_refs")
            rest = line.split(":", 1)[1].strip()
            if collecting and rest and rest != "[]":
                out.extend(part.strip().strip("'\"")
                           for part in rest.strip("[]").split(",") if part.strip())
                collecting = False
            continue
        if collecting:
            item = _YAML_ITEM.match(line)
            if item:
                out.append(item.group(1).strip("'\""))
            elif line.strip():
                collecting = False
    return [ref for ref in out if ref and ref != "null"]


def _store_refs():
    """(holder, ref) for every artifact_ref the item store carries, archived records included.

    An archived item is not a READER (`_is_a_record`), but its evidence is still a record of what
    was measured, and a record pointing at nothing is the same defect one shelf further back.
    """
    out = []
    for dirpath, subdirs, names in os.walk(_STORE):
        subdirs[:] = [name for name in subdirs if name != "__pycache__"]
        for name in sorted(names):
            if not name.endswith((".yaml", ".yml")):
                continue
            path = os.path.join(dirpath, name)
            holder = os.path.relpath(path, ROOT).replace(os.sep, "/")
            try:
                with io.open(path, encoding="utf-8") as handle:
                    text = handle.read()
            except (OSError, UnicodeDecodeError):
                continue
            out.extend((holder, ref) for ref in _refs_in(text))
    return out


def _ref_candidates(ref):
    """(rooting, absolute path) for every place this store has really meant by an `artifact_ref`.

    TWO ROOTINGS OCCUR AND BOTH ARE LOAD-BEARING: some refs are repo-relative (`docs/reviews/...`),
    the others resolve under the state root (`staging/...`, and `../docs/...` which climbs back out
    of it). Nothing enforces either spelling, so a reader that knew one convention would call most
    of the store dangling -- and one that knew only the other would call the rest of it dangling.
    That both rootings are REACHABLE is asserted on synthetic input in
    `test_a_ref_that_climbs_out_of_the_repo_resolves_nowhere`, deliberately NOT against the store:
    a store that one day writes one spelling everywhere is the repair of that split, not a defect,
    and a check that reddened on it would send the reader to this file instead of to the store.

    A ROOTING COUNTS ONLY WHERE IT STAYS INSIDE THIS REPO, so a ref that climbs out of the tree
    resolves NOWHERE instead of being satisfied by whatever happens to sit beside the repo -- a
    check answered by its own environment rather than by the change under it. That property is
    `test_a_ref_that_climbs_out_of_the_repo_resolves_nowhere`; today's store holds no such ref, so
    without that test the clause would be a claim nothing exercises.
    """
    ref = ref.replace("\\", "/")
    for rooting, base in (("state", _STORE), ("repo", ROOT)):
        full = os.path.normpath(os.path.join(base, ref))
        if _inside(full, ROOT):
            yield rooting, full


def _inside(path, tree):
    """True where `path` lies under `tree` -- compared as paths, never as strings."""
    return os.path.normcase(os.path.normpath(path)).startswith(
        os.path.normcase(os.path.normpath(tree)) + os.sep)


def test_every_artifact_ref_still_resolves_where_it_points():
    """A moved document must not leave evidence pointing at nothing -- it has here.

    WHY THIS FAILS INSTEAD OF WARNING, next to a reporter that only warns: whether a document is
    still wanted is a judgement, but whether the file an Evidence record names is THERE is a fact.
    An EVD is immutable, so a broken ref cannot be repaired by editing the record; the move has to
    be undone or the file restored. `docs/archive/README.md` carries the case measured for this
    round -- a staging directory that went into the archive on 2026-08-13 and had to come back,
    because three EVDs point into it. `FR-0036` records a second occurrence, which this round did
    not re-measure and does not claim.

    WHAT IT DOES NOT COVER: a ref that resolves to the WRONG file of the right name, and prose
    pointers, which no ref discipline reaches. The reporter above is the reader for those, and it
    warns rather than judging.
    """
    refs = _store_refs()
    dangling, answered = [], set()
    for holder, ref in refs:
        rooting = next((label for label, full in _ref_candidates(ref) if os.path.exists(full)),
                       None)
        if rooting is None:
            dangling.append("%s -> %s" % (holder, ref))
        else:
            answered.add(rooting)
    assert not dangling, (
        "artifact_refs that resolve nowhere in this repo: %s" % ", ".join(dangling))
    assert answered, (
        "%d refs were read and not one of them resolved anywhere -- this reader has no subject, "
        "and a check without a subject cannot report a broken ref" % len(refs))


def test_the_corpus_drops_a_carried_file_only_where_it_cannot_be_read():
    """Every file this repo carries is offered to the wire reader, and the exceptions are physical.

    THE DEFECT THIS REFUSES WAS THIS FILE'S OWN. The first cut of `_reference_corpus` read five
    named top-level directories, while the manual pass that decided FR-0036's move set read the
    whole tree -- so a document cited only from `README.md`, from `HARNESS_LOG.md` or from a role
    definition under `.claude/agents/` was invisible to the instrument that SHIPS, and the hint
    would have named it as unread. A directory filter is what this test exists to catch: the only
    reasons a carried file may be missing from the corpus are that it is not UTF-8 text or that it
    is larger than prose gets.
    """
    _require_git()
    carried = _carried_files()
    assert len(carried) > 100, "git listed %d files -- this is not the repo" % len(carried)
    read = {rel for rel, _ in _reference_corpus()}
    dropped = []
    for rel in carried:
        if rel in read:
            continue
        full = os.path.join(ROOT, rel.replace("/", os.sep))
        try:
            if not os.path.isfile(full) or os.path.getsize(full) > _TOO_BIG_FOR_PROSE:
                continue
            with io.open(full, encoding="utf-8") as handle:
                handle.read()
        except (OSError, UnicodeDecodeError):
            continue
        dropped.append(rel)
    assert not dropped, (
        "the wire reader is not offered these files, and each of them can hold a pointer into "
        "docs/: %s" % ", ".join(dropped[:20]))


def test_a_ref_that_climbs_out_of_the_repo_resolves_nowhere():
    """The containment half of `_ref_candidates`, which the store itself does not exercise.

    A ref may climb out of the state root -- `../docs/...` is how a record in `project_memory/`
    names a file in the repo, and it is the reason two rootings exist at all. Climbing out of the
    REPO is a different thing: nothing this repo carries answers it, so it must dangle rather than
    be resolved by a sibling directory on the same disk. The `..`-form is asserted alive in the
    same breath, because a containment clause that swallowed it would silence the check by making
    every state-relative ref dangle in the opposite direction.

    IT ALSO CARRIES THE BOTH-ROOTINGS FLOOR, on input this test writes rather than on the store:
    the reader offers `state` and `repo` for a plain relative ref, and only `state` for one that
    climbs. The test above used to read that floor off the store instead, which made the store's
    two spellings load-bearing -- repairing them into one convention reddened a reader that was
    perfectly correct (measured on 57 files / 59 refs, `rework1/m1_refs.py`).
    """
    assert [rooting for rooting, _ in
            _ref_candidates("staging/TSK-0110/round-protocol.md")] == ["state", "repo"]
    assert [rooting for rooting, _ in
            _ref_candidates("../docs/reviews/phase0-disposition.md")] == ["state"]
    assert list(_ref_candidates("../../somewhere-else/note.md")) == []
    assert list(_ref_candidates("../../../note.md")) == []


def test_the_subjects_are_what_the_repo_carries_not_what_lies_on_the_disk(monkeypatch):
    """Both subjects read git, and a filesystem walk would not notice this test at all.

    THE DEFECT THIS HOLDS DOWN, measured rather than imagined: while `_archive_files` walked the
    disk with a skip list, an ignored file under `docs/archive/2026/` -- a `*.log` a tool leaves
    behind, the `Thumbs.db` the Explorer writes, both refused by `.gitignore` -- turned
    `test_every_archived_file_is_named_by_the_index_above_it` hard red on a tree nobody had
    changed. Nothing in the suite CREATES such a file, so nothing in the suite would have caught
    the walk coming back; this test is what does, because a walk ignores the stub below and
    answers with the real tree.
    """
    monkeypatch.setitem(globals(), "_carried_files", lambda: [
        "docs/note.md", "docs/archive/2026/README.md", "docs/archive/2026/pilot/moved.md",
        "tools/test_repo_hygiene.py", "README.md"])
    assert _docs_candidates() == ["docs/note.md"]
    assert _archive_files() == ["docs/archive/2026/README.md",
                                "docs/archive/2026/pilot/moved.md"]


def test_a_corpus_that_cannot_be_listed_says_so_instead_of_reading_as_empty(monkeypatch):
    """A reader that cannot list is not a reader that found nothing.

    The branch below is unreachable while git works, so nothing on a healthy host exercises it --
    and an unreachable branch that returns an EMPTY list is the shape this file is built against:
    every subject downstream (the documents, the archive, the corpus) would silently become empty,
    the hint would say nothing, and the archive tripwire would report "no index at all" while the
    real cause is that `git ls-files` failed.
    """
    class _Failed:
        returncode = 128
        stdout = ""
        stderr = "fatal: not a git repository"

    monkeypatch.setitem(globals(), "subprocess",
                        type("_Stub", (), {"run": staticmethod(lambda *a, **k: _Failed())}))
    with pytest.raises(AssertionError, match="git could not list"):
        _carried_files()


# -- BUG-0087: an assertion that cannot be false claims coverage --------------------------------

def _assert_statements_that_cannot_fail(tree):
    """The `assert` nodes whose test is statically true -- `assert True`, `assert x or True`."""
    def truthy(node):
        if isinstance(node, ast.Constant):
            return bool(node.value)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            return any(truthy(value) for value in node.values)
        return False
    return [node for node in ast.walk(tree) if isinstance(node, ast.Assert) and truthy(node.test)]


def test_no_assertion_in_the_suites_is_statically_true():
    """BUG-0087: `assert <x> or True` stood in the hook time-budget family and was true for every input.

    MEASURED RED before the line was removed: the sweep below named
    `tools/test_hooks_v2.py` at the `TOTAL_BUDGET + VALIDATE_TIMEOUT <= 60 or True` line, and nothing
    else in either suite tree. The reader is the AST, so an `assert True` inside a STRING a test
    writes into a fixture file is not one (three such strings stand in the suites today).
    """
    offenders = []
    for path in sorted(glob.glob(os.path.join(ROOT, "tools", "test_*.py"))
                       + glob.glob(os.path.join(ROOT, ".claude", "hooks", "test_*.py"))):
        with io.open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in _assert_statements_that_cannot_fail(tree):
            offenders.append("%s:%d" % (os.path.relpath(path, ROOT).replace(os.sep, "/"), node.lineno))
    assert not offenders, "assertions that cannot be false:\n  " + "\n  ".join(offenders)
    # the reader's floor: it sees both shapes, and it does not see a string
    probe = ast.parse("assert x or True\nassert True\nassert x\nwrite('assert True')\n")
    assert [node.lineno for node in _assert_statements_that_cannot_fail(probe)] == [1, 2]


# ---------------- the suite's own writes: nothing of a run lands in canonical state ------------
REPO_AUDIT_LOG = os.path.join(ROOT, "project_memory", ".audit", "hook_events.jsonl")


def _audit_bytes(path):
    """The log's current content, or None when it is not there -- both are a legitimate before."""
    try:
        with io.open(path, "rb") as handle:
            return handle.read()
    except FileNotFoundError:
        return None


def test_no_hook_started_by_this_suite_can_write_this_repos_audit_log(tmp_path):
    """BUG-0052: a kit gate this suite started appended its refusal to the REPO's canonical
    `project_memory/.audit/hook_events.jsonl`, and the lead committed those lines with the package.

    MEASURED on fd7e2fa before the fix: one `tools/test_hooks_v2.py` run took the file from 697 to
    699 lines (md5 09b9875a... -> 92d2f0d7...), the two added records being a `gate_needs` parse
    error at 18:55:14 and the `OtherDB`/`neighbour-stack` compose fixture at 19:06:31. The sink is
    `<_root.find_repo_root()>/project_memory/.audit/`, and that resolver answers `$CLAUDE_PROJECT_DIR`
    first -- so any hook started WITHOUT an explicit project dir inherits the session's, which in
    this repository is this repository. `tools/conftest.py` redirects the ambient variable; this
    measures the result against a hook started exactly the way the leaking fixture started one.

    BOTH ENDS, because "the log did not grow" is also what a hook that recorded NOTHING produces:
    the record has to arrive in the ambient sink. Without that half the test would stay green if
    `_audit` silently stopped writing, which is a different defect wearing this one's face.
    """
    gate = os.path.join(ROOT, "team-kits", "dev-team", "hooks", "gate_shell_hygiene.py")
    sink = os.path.join(os.environ["CLAUDE_PROJECT_DIR"], "project_memory", ".audit",
                        "hook_events.jsonl")
    before_repo, before_sink = _audit_bytes(REPO_AUDIT_LOG), _audit_bytes(sink)
    # An unparseable payload is the shortest route into `_kernel.payload`'s fail-closed block, which
    # is what calls `_audit.record` -- and it is the shape the measured leak had. The environment is
    # passed through UNCHANGED on purpose: the defect is exactly the call site that names no project.
    proc = subprocess.run([sys.executable, gate], input="not json at all",
                          capture_output=True, text=True, env=dict(os.environ),
                          cwd=str(tmp_path), timeout=120)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "could not be read or parsed" in proc.stderr, proc.stderr
    assert _audit_bytes(REPO_AUDIT_LOG) == before_repo, (
        "a hook this suite started appended to the repo's canonical audit log (BUG-0052)")
    after_sink = _audit_bytes(sink)
    assert after_sink is not None and after_sink != before_sink, (
        "the refusal was recorded nowhere -- the redirection cannot be read off a log that never "
        "grows, so this assertion is the one that keeps the check above honest")


def _test_modules_outside_the_default_surface():
    """Every `test_*.py` of this repository that `python -m pytest tools/` does NOT collect.

    Derived by walking the tree, not listed: a module added next to an existing one is covered the
    day it ships. `.git`, `node_modules` and the scratch trees a run leaves behind are not the
    repository's source.
    """
    found = []
    for base, directories, names in os.walk(ROOT):
        directories[:] = [d for d in directories
                          if d not in (".git", "node_modules", "__pycache__", ".pytest_cache")]
        rel_base = os.path.relpath(base, ROOT).replace(os.sep, "/")
        if rel_base == "tools" or rel_base.startswith("tools/"):
            continue
        for name in names:
            if name.startswith("test_") and name.endswith(".py"):
                prefix = "" if rel_base == "." else rel_base + "/"
                found.append(prefix + name)
    return sorted(found)


def test_a_suite_the_default_run_does_not_collect_is_named_with_its_own_run_command():
    """BUG-0014: `.claude/hooks/test_gates.py` stood red for at least a whole round because nothing
    noticed -- it is the one suite `python -m pytest tools/` does not collect, and no text tied its
    existence to a command anybody runs.

    THE PROPERTY IS THE PAIR, not the file name: whatever test module this repository grows outside
    the default surface must appear in `CLAUDE.md` TOGETHER with a pytest line that names it, so the
    round that has to run it can find out that it has to. A second such module added tomorrow turns
    this red on the day it ships, which is the half BUG-0014's AC-3 asks for and a list of names
    would not give.

    What this does NOT claim, and the reason it is worded as it is: it cannot make anybody RUN the
    suite, and it does not pretend to -- it measures that the suite is documented with its command,
    which is what was missing when the red survived. The red itself is caught by running it.
    """
    outside = _test_modules_outside_the_default_surface()
    assert outside, "the scan found no suite outside tools/ -- it would be vacuous"
    with io.open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8") as handle:
        governing = handle.read()
    runs = [line for line in governing.splitlines() if "pytest" in line]
    unnamed = [module for module in outside
               if not any(module in line for line in runs)]
    assert not unnamed, (
        "CLAUDE.md carries no pytest line that names these suites, so a round has no way to learn "
        "they exist: %s" % unnamed)


def _top_level_modules_of(directory):
    """The names `import <name>` resolves to when `directory` is on the path -- modules and packages.

    Both shapes, because both shadow: a `<name>.py` beside the entry point and a `<name>/` package
    with an `__init__.py` are the same name to the import system.
    """
    found = set()
    for entry in sorted(os.listdir(directory)):
        path = os.path.join(directory, entry)
        if entry.endswith(".py") and os.path.isfile(path):
            found.add(entry[:-len(".py")])
        elif os.path.isdir(path) and os.path.isfile(os.path.join(path, "__init__.py")):
            found.add(entry)
    return found


def test_no_module_under_tools_shadows_one_of_the_kit_tree(): # noqa: D401
    """BUG-0276 / H192: a module added under `tools/` shadows the `team-kits/` module of the same
    name for every `python tools/<script>.py` entry point, and nothing measured the collision.

    THE MECHANISM IS PYTHON'S OWN PATH ORDER, not a defect of any script: a script started as
    `python tools/validate.py` puts `tools/` at the FRONT of `sys.path`, ahead of the `team-kits/`
    the script then adds -- so `import gen_provider_artifacts` finds the neighbour rather than the
    kit's. Measured 2026-09-11 in a `.git`-less copy (`_round-scratch/TSK-0134/tree`): a five-line
    stub written to `tools/gen_provider_artifacts.py` turned `python tools/validate.py` from
    `all structural checks passed` into `ImportError: cannot import name 'load_tiers'` before a
    single structural check ran. The LOUD direction is the lucky one; a stub that happened to define
    the names the entry point imports would have been used with no error at all.

    THE SUBJECTS ARE DERIVED from the two directories, so a module added on either side is compared
    with no edit here, and the check is over NAMES rather than over imports: importing the kit tree
    to find out would be the very shadowing this measures.
    """
    tools_modules = _top_level_modules_of(os.path.join(ROOT, "tools"))
    kit_modules = _top_level_modules_of(os.path.join(ROOT, "team-kits"))
    assert kit_modules, "no importable module found under team-kits/ -- this would be vacuous"
    assert tools_modules, "no importable module found under tools/ -- this would be vacuous"
    collisions = sorted(tools_modules & kit_modules)
    assert not collisions, (
        "these names exist under BOTH tools/ and team-kits/, so every `python tools/<script>.py` "
        "entry point resolves them to the tools/ copy: %s. Remedy: rename the tools/ one, or load "
        "the kit module BY PATH as `tools/radar_routine.py::_kit_generator` does." % collisions)
