#!/usr/bin/env python3
"""
PreToolUse(Bash|PowerShell) — deletes under inbox/ or archive/, and moves that take a document OUT
of archive/, are blocked unless the USER approved that exact correction.

Business documents are irreplaceable: "originals are moved, never deleted" must not depend on
discipline. Filing INTO archive/ stays free (`gate_filing` is what makes that opening safe);
deleting anything under inbox/ or archive/, or moving something out of archive/, blocks.
Reorganisation inside the archive runs as a user-approved migration PROC — if this guard fires on
legitimate reorg, that is the signal to get the user's OK first, not to work around it.

THE ONE DOOR IN THAT WALL, and why it exists (FR-0050). The wall was right as a default and wrong
as a life sentence: a document filed in the wrong place stayed wrong, because nothing inside the
kit could move it back and nothing could remove a duplicate scan. The user's steering was "löschen
und verschieben darf möglich sein, aber erst nach Freigabe", so the correction runs on the kit's
own approval machinery rather than on a new one: the clerk opens the question with `python
scripts/harness.py request-approval filing_correction --document <path> [--destination <path>]
--reason <why>`, the USER mints it by answering, and `open_the_door` below lets through the one
operation that approval names — the same document, the same version of it, the same destination or
the same deletion.

WHAT THE DOOR IS WORTH, AS THE FOUR CONDITIONS IT REALLY CHECKS, because a shorter sentence here
was measured false. The door opens for a COMMAND LINE, so all four are about the line:

  1. this guard placed EVERYTHING on it — every invocation, every operand of one, and every
     REDIRECT TARGET, which is none of the two and had to be read on its own (`>` is shell syntax,
     so no reader of arguments can see it), WHEREVER on the line the redirect stands. An invocation
     it does not read (`python -c "os.remove(...)"`, `tar --remove-files`, an `echo`, a `tee` behind
     a pipe), an operand or a redirect target the shell rewrites (`$A`, a glob, `~/…`), one that
     names no place in this project, a `cd` it cannot follow, a redirect writing INTO a tray of
     record: any one of them and NOTHING on the line is let through. Each of those rode through
     beside an approved operation before the condition existed (verifier findings F1/F2 and round 2
     R1, all measured rc 0), and a redirect written FIRST hid its own invocation from every reader
     until `_filing._tokens` stopped ending the argument list at it (round 3, V1/V2);
  2. it asks for at most `CORRECTION_CAP` corrections — see that constant for why a bound is part
     of the protection rather than a limitation of it;
  3. every operation on it carries a LIVE user approval (minted, unrevoked, unexpired, provenance
     provable) naming exactly that operation;
  4. and the approval binds the document's BYTES (`kernel.hashing.document_content_hash`), so what
     it covers is those bytes at that position while they lie there: once the approved command has
     run there is nothing at the source to hash and the approval matches nothing. That is the push
     token's derivation, not a "used" flag anyone has to keep honest — and it means a byte-identical
     file put back at that position is covered again, which the question the user signs says
     ("gilt nur für genau diese Fassung") rather than promising a one-shot.

Everything else this guard refuses, it goes on refusing — a different document under the same
approval, a different destination, a deletion where a move was approved, one approved document
beside one that is not.

AND WHAT IT NEVER SAW IT STILL NEVER SEES, which is the honest limit of all four conditions: they
decide whether the DOOR opens, never what the WALL notices. A `python -c "os.remove(...)"` or a
bare `> inbox/x.pdf` ALONE on its own command line is refused by nothing here, exactly as before
this door existed — the trays' own residual list at the end of this docstring is where those live.
What the conditions buy is that none of them can be carried through by something the guard DID
see.

WHAT IS RECORDED, stated no wider than it is: the durable record of a correction is the minted
request the kernel keeps forever under `approvals/consumed/` — it carries the document, the version
hash, the destination or its absence, the reason the user was shown, and the mint code. This guard
adds one line to `project_memory/.audit/hook_events.jsonl` naming the approval it honoured and the
command it let through; that file is local diagnostics (see `_audit`), and it says the call was
ALLOWED, never that it succeeded — a PreToolUse hook runs before the command and cannot know.

WHAT "OUT OF ARCHIVE" MEANS, and this is the correction of 2026-08-03. The question is about the
RESOLVED POSITION of the source and of the destination, not about the string `archive/` appearing
in a token. Reading the token was wrong in both directions at once, measured against these hooks: a
move from one archive folder to another was refused (the source token carried the word), and a move
that really emptied the archive was allowed as soon as the source token did not. The audited
project had written the second spelling into an APPROVED procedure, because it was the shape that
got its work done, and two of the refusals in its audit log are moves that never left the archive
at all.

So the fix is not a pattern for that spelling. Source and destination are resolved against the
working directory the command line actually left behind (`_filing`, shared with `gate_filing`, so
the two sides of the wall cannot disagree about where it stands), which reads every spelling whose
TEXT IS THE PATH the same way — a relative path after a `cd` or a `pushd`, a `../` climb, a
wrapper payload. The spellings whose text is NOT the path are the residual, and they are listed at
the end of this docstring rather than implied to be covered.

The DELETE rule keeps its token reading and gains the resolved one on top: the two are a union, so
a `cd archive/x && rm y.pdf` is caught while nothing that was refused before becomes allowed. It is
deliberately NOT the same replacement as the move rule — there is no legitimate delete under these
trays to protect, so there is no false positive to remove.

WHAT THIS DOES NOT SEE, so each stays a decision rather than a discovery:

  * a removal performed inside another program (`python -c "os.remove(...)"`). Its command word is
    the interpreter and the removal is inside a string this guard does not parse;
  * a removal whose word carries none of the stems in `NAMING_DESTRUCTION` / `SWEEPING_DESTRUCTION`.
    That is the honest residue of H125 and it is `H129` in docs/POST_V2_WISHLIST.md with its
    measurement. What is NO LONGER in this list, because the stems are now read over every word of
    an invocation: a removal asked for with a FLAG (`find archive -name '*.pdf' -delete`,
    `tar --remove-files … archive/…`) and one asked for with a SUBCOMMAND (`git clean -fdx`);
  * (CLOSED, `BUG-0207`) a copier flag that deletes in the DESTINATION rather than the source —
    `robocopy inbox archive/… /MIR`, `rsync --delete inbox/ archive/2026/`. It survived H125
    because of the ORDER of the readings below: `_filing` reads those invocations as copies, so the
    copy/move branch answered them and returned before any destroying word was looked for. The
    branch no longer returns unconditionally — a copier that carries a destroying word and is NOT
    relocating destroys in its DESTINATION, which is then the reach — and a word introduced with a
    SLASH is read as the flag it is;
  * a token, or a `cd` argument, the shell rewrites before use — a variable, a glob, `~`. `_filing`
    resolves none of them and this guard blocks on none; uncertainty -> exit 0 is this guard's
    contract, and a guess about an unresolvable name would break it;
  * an operand a PIPE hands to the destruction (`ls archive | xargs rm -rf`, `find . -print0 |
    xargs -0 rm -rf`, `Get-ChildItem -Recurse | Remove-Item -Force`). The destroying word stands on
    the line, but the paths it will act on are the previous stage's OUTPUT and no word of the line
    names them, so the reach reads as "names nothing" and a NAMING word that names nothing destroys
    nothing. Measured rc 0 through all eight registered hooks, unchanged from HEAD, and named in
    `H125`;
  * a directory LINK that stands in for a tray (a junction `belege/ -> archive/`). `_filing`
    normalises a path, it does not RESOLVE it, so `rm belege/finance/2026/invoice.pdf` is rc 0 while
    the same document through its real path is rc 2 (measured). The paragraph "WHAT OUT OF ARCHIVE
    MEANS" above speaks of every spelling whose TEXT IS THE PATH; a link's text is not the path.
    IT REACHES THROUGH THE WORKING DIRECTORY TOO, which is the worse half and is measured: `cd
    belege ; rm -rf .`, `cd belege/finance ; rm -rf .` and `cd belege ; git clean -fdx` are rc 0
    while `cd archive ; rm -rf .` is rc 2 -- the shell stands in the archive and the ancestor form
    costs the whole tray;
  * the GLOB spelling of the ancestor form (`rm -rf *`, `rm -rf ./*`, `git clean -fdx *`). It is the
    bullet above this one -- a token the shell rewrites -- and it is called out again here because
    it is the most ordinary spelling of the destruction `H125` closes;
  * (CLOSED in TSK-0120, kept here for the direction it names) a directory change whose EFFECT the
    line does not settle -- a short-circuiting `&&`, a `cd` in a pipe stage or behind `&` (both
    subshells), a `popd` this reader cannot compute. The sweep is judged against every position the
    shell could be standing in, and EVERY one of them is carried forward: a change is computed FROM
    EACH candidate (a relative target means something different from each), a certain in-shell
    change then replaces the set with the results, any other change adds them beside it, and a
    destruction is refused when any candidate holds a tray of record. Two earlier cuts fell short
    and both are measured: skipping the uncertain change only -- `cd outbox && cd .. && rm -rf .`
    was ALLOW while `rm -rf .` alone was rc 2 (merge-verifier B1) -- and computing the next change
    from the NEWEST candidate only -- `cd docs | true ; cd ../outbox ; rm -rf .` was ALLOW while a
    real bash stands on the root (B2). What this BUYS is not certainty about the shell, only doubt
    answered fail-closed, and the price is four named over-refusals --
    `true && cd outbox ; rm -rf .`, `cd outbox ; cd .. | true ; rm -rf .`,
    `cd outbox ; cd $X ; rm -rf .` and `pushd outbox ; pushd sub ; popd ; rm -rf .` -- each refused
    although that shell may really be standing outside every tray. A FIFTH belongs to PowerShell
    and comes out of a rule that is right for the other shell: a one-character `|` is read as a
    subshell because a bash pipeline is one, while a PowerShell pipeline runs in the same process --
    so `Set-Location docs | Out-Null ; Set-Location ../outbox ; rm -rf .` is rc 2 with the shell
    really in `outbox`. `H144` and `H150` carry the chains and all five prices;
  * an output REDIRECT into a tray of record ON ITS OWN (`echo x > inbox/y.pdf`), which truncates a
    document of record as surely as a delete. This guard's two rules read a DESTROYING WORD and a
    move OUT of the archive, and a redirect is neither, so nothing here refuses it — `gate_filing`
    catches the `archive/` half (it reads redirect targets among the paths a command CREATES) and
    the `inbox/` half is refused by nothing. Named here rather than closed, because closing it is a
    new WALL rule for every office project and not a property of this round's door; what the door
    does do is refuse such a redirect when it rides on a line asking for a correction (R1);
  * a COPIER told to relocate IS now read as one: a source-deleting flag (`robocopy /MOVE`, `rsync
    --remove-source-files` and its alias `--remove-sent-files`) makes `_filing.relocating` true, so
    emptying the archive with it is refused (BUG-0002, `SOURCE_DELETING_FLAGS`). What stays open is
    the neighbouring case that deletes in the DESTINATION rather than the source — `robocopy inbox
    archive/… /MIR` (which /PURGEs the archive) is not a move OUT of it, and is refused as a DELETE
    under the destination instead (`BUG-0207`) — that is the copier-flag
    residue named three bullets up, and it is one entry rather than two.
"""
import os
import re
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _audit
import _compat  # noqa: F401 — UTF-8 stream pinning (import side effect)
import _filing
import _root


# The two trays whose contents are DOCUMENTS OF RECORD: what arrived (inbox) and what is filed
# (archive). `outbox/` is the kit's third tray and is deliberately not here — it holds drafts the
# project produces and may discard, so a delete there is ordinary work.
INBOX = "inbox"
PROTECTED_TRAYS = (_filing.ARCHIVE, INBOX)
# ---------------------------------------------------------------- WHAT COUNTS AS A DESTRUCTION
# THE RULE IS A PROPERTY OF THE LINE AND NOT A LIST OF VERBS (H125). Until 2026-09-03 this was
# `DELETE_VERBS = ("rm", "rmdir", "del", "erase", "rd", "remove-item", "ri")` and the question was
# "is the command word in that tuple". Measured against a scaffolded pilot with a real document
# under `archive/`, through all eight registered office hooks as processes: `unlink`, `git clean
# -fdx` (with and without a path), `Clear-Content` and `find archive -delete` were ALLOW while `rm`
# on the same document was rc 2. `git clean` is the worst of them and is the accident in its purest
# form -- the documents under `archive/` are untracked AND ignored by the kit's own `.gitignore`,
# which is exactly the set `-fdx` removes.
#
# The property has TWO HALVES and only one of them is a definition. That is said here rather than
# implied, because the honest half is what a reader has to know before relying on this wall:
#
#   WHERE (a definition, and the half that closes `git clean`): a destruction REACHES a set of
#   positions. A destruction that NAMES paths reaches those; a SWEEPING one that names none reaches
#   the working directory it runs in. That reach meets a tray of record in TWO directions, and both
#   are read: the position lies INSIDE a tray (`_protected_readings`, an approvable document), or a
#   tray lies INSIDE the position (`swallows_a_tray`, which is no document at all and therefore a
#   sweep). The second direction is verifier finding B1 of rework 1: with only the first,
#   `git clean -fdx .`, `rm -rf .`, `find . -name '*.pdf' -delete` and `Remove-Item -Recurse -Force
#   .` were rc 0 while the same lines without the dot were rc 2 -- so the wall taught its own
#   bypass, which is the opposite of what a guard against an ACCIDENT is for (`DEC-0056`).
#   The tray has to EXIST for the second direction, and that is the over-refusal weighing: it is
#   why `git clean -fdx` in a project without an archive is not refused.
#
#   WHAT (a vocabulary, and it stays one): whether a program removes or empties a file is a fact
#   about that program and cannot be derived from the command line -- a `PreToolUse` hook runs
#   BEFORE the line and has no filesystem answer to compare against. What changed is the SHAPE of
#   the vocabulary: it is read over every word of the invocation instead of over the command word
#   only (so a flag like `-delete` and a subcommand like `clean` are seen), and by word STEM
#   instead of by exact spelling (so `Remove-Item`, `Clear-Content` and any other verb-noun
#   compound are seen without being listed). The residue -- a destroying program whose name carries
#   none of these stems -- is `H129` in docs/POST_V2_WISHLIST.md, with its measurement. Both ends of
#   every stem are measured rather than trusted:
#   `tools/test_hooks.py::test_every_destroying_stem_is_load_bearing_at_both_ends` plants a line for
#   each one and asks (a) that the guard refuses it and (b) that removing the stem lets it through.
#
# THE TWO ROLES A DESTROYING WORD CAN HAVE, and they are not interchangeable. A NAMING word
# destroys what the invocation names, so with no operand it destroys nothing -- which is why plain
# `clear` (the terminal) is not a refusal while `Clear-Content archive/x.pdf` is. A SWEEPING word
# destroys whatever it finds, so its reach is the working directory unless a path narrows it; that
# is the whole of `git clean`.
NAMING_DESTRUCTION = ("rm", "rmdir", "rd", "ri", "del", "erase", "unlink", "remove", "delete",
                      "clear", "clc", "shred", "truncate")
# `mir`/`mirror` are here for the same reason `purge` is, and it is a fact about the operation and
# not about a spelling: making a destination EQUAL to a source removes whatever the source does not
# have, so a mirror destroys what it does not name -- which is exactly what "sweeping" means here.
# `robocopy inbox archive/2026 /MIR` is the measured line (`H123`); it is `/PURGE` plus `/E`.
SWEEPING_DESTRUCTION = ("clean", "purge", "wipe", "mir", "mirror")
# THE WORKING DIRECTORY, WRITTEN AS THE PATH THAT NAMES IT. A sweeping destruction with no operand
# and one whose operand is `.` are the same destruction -- measured with the command's own dry run,
# `git clean -ndx` and `git clean -ndx .` printing character-identical output -- so they are asked
# the same question here instead of through two branches that can drift apart.
WORKING_DIRECTORY = "."
# A FLAG WHOSE VALUE IS A PATTERN THE COMMAND MUST **NOT** TOUCH. Its word is therefore not a path
# the line acts on and cannot narrow a sweep: `git clean -fdx -e docs` still sweeps everything
# except `docs`, and reading `docs` as "the sweep is confined to docs" made that line rc 0 over a
# real archive (verifier finding B1). Which flag means "exclude" is a fact about each command and
# cannot be derived from the line, so this is an unavoidable enumeration -- kept honest the same way
# the destruction stems are, by a tripwire that measures BOTH of its ends
# (`tools/test_hooks.py::test_an_exclusion_flag_does_not_narrow_a_sweep`).
#
# WHAT THIS COSTS THE CAREFUL SPELLING, measured and kept: `git clean -fdx -e archive` -- somebody
# excluding the archive ON PURPOSE -- is refused too, because the exclusion is not read as a
# narrowing and the sweep is then judged against the working directory. That is an over-refusal by
# construction, and it costs a correction and never a document: reading the exclusion instead would
# mean reading each command's pattern grammar, which is a second parser per command and the thing
# `H123` records the price of.
EXCLUDING_FLAGS = ("e", "exclude")
# WHY THERE IS NO EXCEPTION HERE FOR THE COPIER FAMILY'S SOURCE-DELETING FLAGS, and it was measured
# rather than reasoned: `rsync --remove-source-files inbox/x archive/2026/x` carries the word
# `remove` and is the kit's ORDINARY filing move, so an exception for those flags looked necessary.
# It is not, and one that catches nothing is the enumeration this round exists to remove. What
# answers that line is the ORDER of the readings in `read_the_line`: `_filing` recognises rsync as a
# copier by calling convention, so the copy/move branch judges the invocation and returns before any
# destroying word is looked for. Measured on both ends by
# `tools/test_hooks.py::test_a_filing_move_with_a_source_deleting_copier_flag_is_judged_as_a_move`:
# the shipped guard allows that line, and a guard whose `_filing` no longer knows rsync as a copier
# refuses it.
# A word that could be a bare SUBCOMMAND (`git clean`) rather than a path. Anything carrying a path
# separator, an extension or an assignment is a path or an environment prefix and is read as one --
# `ls archive/clean-room/` must not become a destruction because a folder is called that.
_BARE_WORD_RX = re.compile(r"\A[A-Za-z][A-Za-z0-9_-]*\Z")
# The trays of record as they appear in the RAW text of an invocation. The second reading of the
# delete rule keeps working the way it always has -- see `read_the_line` -- and it is built from
# `PROTECTED_TRAYS` rather than re-typed, so a tray added to one reading cannot be missing from the
# other.
TRAY_IN_TEXT_RX = re.compile(r"\b(%s)(\b|[/\\])" % "|".join(PROTECTED_TRAYS), re.I)
# shell redirects into the ledger bypass the Edit/Write guard (audit finding: `echo >> ledger/x.csv`).
# The TARGET is read through `_filing.redirect_targets`, which resolves quoting and lifts wrapper
# payloads the same way the write-scope gate reads a state path — a raw scan of the command text saw
# neither `led'g'er/x.csv` nor `"ledger"/x.csv`, both of which name this file (BUG-0003). This
# pattern therefore runs against an already-resolved single word, not the raw line.
LEDGER_CSV_RX = re.compile(r"\bledger[/\\][^\s]*\.csv", re.I)
# The exemption is for INVOKING the script, not for MENTIONING it. A substring test let
# `echo garbage >> ledger/2026.csv # via ledger_add.py` through -- a comment disabled the rule.
LEDGER_ADD_RX = re.compile(r"(?:^|[;&|(]|\bpython[0-9.]*\s+|\bpy\s+)\s*\S*ledger_add\.py\b", re.I)
# WHAT ONE CORRECTION COSTS THE DOOR TO DECIDE, as a budget rather than as a stopwatch reading: a
# file read for the version the approval binds, plus a dictionary lookup. The figure is deliberately
# an order of magnitude above anything measured on a developer host, because it has to hold on the
# slowest machine this kit runs on -- and being wrong in the SLOW direction only makes the cap
# smaller, i.e. only ever refuses earlier. The per-round measurements sit in
# docs/reviews/2026-08-18-tsk0077-measurements.md, not here: a number measured for one round belongs
# in that round's report, never in a second copy beside the code.
CORRECTION_COST_SECONDS = 0.2
# HOW MUCH OF THE HOOK'S DEADLINE THIS ONE DECISION MAY SPEND. A tenth, because the door is not
# what the process is: starting the interpreter, reading the payload, walking the command line and
# reading the approval store all come first, and the size of that store is not something the door
# controls at all (see the report's residue on it). A gate that finishes exactly on the deadline has
# not finished.
CORRECTION_BUDGET_SHARE = 0.1


def budget_cap():
    """The most corrections the door could consider and still decide inside its budget.

    THE BUDGET IS `_compat.HOOK_DEADLINE_SECONDS` and is not restated here (R4). What passing it
    costs is no longer a kill -- BUG-0062 measured that away, and that constant carries the finding
    -- but a door that decides for two minutes is a session that stands still for two minutes with
    the user watching. Measured before any bound existed (verifier finding F3): one `rm` naming 8000
    archive documents took 114 s where the wall alone took 0.54 s.

    This is a CEILING, not the cap. `CORRECTION_CAP` is smaller and is chosen for a product reason;
    what this function exists for is that the choice cannot quietly drift past what the budget
    supports -- `tools/test_hooks.py::test_the_cap_stays_inside_the_budget_it_exists_for` recomputes
    it and goes red if it ever does.
    """
    return int(_compat.HOOK_DEADLINE_SECONDS * CORRECTION_BUDGET_SHARE / CORRECTION_COST_SECONDS)


# HOW MANY CORRECTIONS THE DOOR WILL EVEN CONSIDER ON ONE COMMAND LINE. 25 for a reason about the
# WORK and not about the clock: a correction is a single-document act -- the clerk asks the user per
# document and the question the user signs names one -- so a line past this is not the shape the
# door is for. Above it the door does not open and the wall answers as it always did, so the cap can
# only ever REFUSE. That it also sits under `budget_cap()` is the safety half, and it is measured
# rather than assumed.
CORRECTION_CAP = 25
# THE WAY OUT, in both refusals, because a refusal that names no route is what made a mis-filed
# document permanent (FR-0050). It is written once: the two refusals differ in what they refuse and
# not in how a correction is obtained, and a second copy of this sentence is how the delete half and
# the move half would come to name two different commands.
CORRECTION_REMEDY = (
    "Remedy, if this really has to happen: it needs the USER, not a workaround. Run `python "
    "scripts/harness.py request-approval filing_correction --document <path-from-the-project-root> "
    "--destination <where-it-should-land> --reason <why>` -- leave `--destination` out to ask for a "
    "DELETION instead -- and relay the printed question to the user VERBATIM with AskUserQuestion. "
    "Their Freigeben answer mints the approval, and this guard then lets through exactly the "
    "operation it names: the same document, the same version of its bytes, the same destination. "
    "Then run that correction ON A LINE OF ITS OWN (a `cd` in front of it is fine): the approval "
    "covers one correction and not the command line around it, so anything else on the line -- "
    "another program, an operand the shell rewrites, a second document -- refuses the whole call. "
    "The approval stops covering the document as soon as those bytes are no longer at that "
    "position, so ask again if the command did not run.\n")


def says_destruction(word, compound):
    """`"naming"`, `"sweeping"` or None for ONE word — see the two tuples above.

    `compound` is true where a word may be a verb-noun or a multi-part flag (`Remove-Item`,
    `--delete-after`): there the FIRST segment carries the verb. It is false for a bare word in
    operand position, where only the whole word may be the verb -- otherwise a folder called
    `clean-room` would read as `git clean`.
    """
    normalised = str(word).strip().lower()
    if not normalised:
        return None
    spellings = [normalised]
    if compound:
        head = re.split(r"[-_]", normalised)[0]
        if head and head != normalised:
            spellings.append(head)
    for spelling in spellings:
        if spelling in NAMING_DESTRUCTION:
            return "naming"
        if spelling in SWEEPING_DESTRUCTION:
            return "sweeping"
    return None


def destruction_of(tokens):
    """`"naming"`, `"sweeping"` or None for one invocation — which word says it decides the role.

    THREE POSITIONS A DESTROYING WORD CAN STAND IN, and each was measured to be necessary:
    the command word (`unlink …`), a FLAG (`find archive -delete`, which is `H123`'s shape and is
    now covered), and a bare word anywhere after the command word -- a subcommand (`git clean`) or
    the real verb behind a prefix (`env FOO=1 rm x`, `sudo rm x`), which is why this scans instead
    of looking at index 1. A sweeping word wins over a naming one on the same line, because a sweep
    is the wider reach and the refusal has to describe the wider thing.
    """
    found = None
    for index, token in enumerate(tokens):
        text = str(token)
        if not index:
            said = says_destruction(_filing.command_name(text), True)
        elif text.startswith("-") or text.startswith("/"):
            # A FLAG IS A WORD WITH A FLAG INTRODUCER, and the Windows family this kit gates spells
            # one with a SLASH: `robocopy … /PURGE` and `/MIR` carried a destroying word that no
            # position of this reader looked at -- not index 0, not a `-` flag, and not a bare word
            # (`_BARE_WORD_RX` refuses the slash). That is the `H123` half the ORDER did not
            # explain. What it costs is measured rather than argued: a POSIX ABSOLUTE PATH also
            # begins with a slash, and stripping it leaves `archive/2026/x.pdf`, which carries no
            # stem and is therefore no destruction -- only a word that IS a destroying stem after
            # the slash is read as one.
            said = says_destruction(text.lstrip("-/"), True)
        elif _BARE_WORD_RX.match(text):
            said = says_destruction(text, False)
        else:
            said = None
        if said == "sweeping":
            return said
        found = found or said
    return found


def excludes_its_value(token):
    """Is this token a flag that takes the NEXT word OUT of the operation? — see `EXCLUDING_FLAGS`.

    A glued value (`--exclude=docs`) carries its own word and consumes nothing after it, which is
    why the separator is looked at rather than only the name.
    """
    text = str(token)
    if not text.startswith("-") or "=" in text:
        return False
    return text.lstrip("-").split(":", 1)[0].lower() in EXCLUDING_FLAGS


def destruction_operands(tokens):
    """The path-shaped tokens a destroying invocation acts on.

    Everything that is not the command word, not a flag, not the VALUE of an excluding flag and not
    one of the words that SAYS the destruction — so `git clean -fdx` names none (its reach is the
    working directory), `git clean -fdx archive` names one, and `git clean -fdx -e docs` names none
    again, because an exclusion is not a path the line acts on. The old reading took the tokens
    after the delete verb (`_filing.operands_of`), which cannot see a line whose destroying word
    stands last.
    """
    found, skip = [], False
    for index, token in enumerate(tokens):
        text = str(token)
        if not index:
            continue
        if text.startswith("-"):
            skip = excludes_its_value(token)
            continue
        if skip:
            skip = False
            continue
        if _BARE_WORD_RX.match(text) and says_destruction(text, False):
            continue
        found.append(token)
    return found


# A WORD THE SHELL SETS BEFORE THE COMMAND WORD (`FOO=1 cmd`). It is not the command and it is not
# a path, so the reader below steps over it while looking for the word that names the invocation.
_ASSIGNMENT_RX = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")


def moves_the_working_directory(root, tokens, base):
    """Where this invocation really leaves the working directory, or None.

    THE COMMAND WORD HAS TO BE THE DIRECTORY CHANGE, and that is the whole of verifier finding B4.
    `_filing` looks for a `cd` ANYWHERE in an invocation, on purpose: for the readers that ask "does
    any base land in the archive", a misreading can only ADD a reading and the worst it costs is an
    over-refusal. The sweep reader NARROWS, so there the same misreading costs a document --
    measured: `echo cd outbox ; rm -rf .`, `grep -r cd outbox ; rm -rf .` and
    `ls cd outbox && rm -rf .` were rc 0 while `rm -rf .` alone was rc 2. So this reader asks the
    narrower question, and only for the base it hands to `swallows_a_tray`; every other reading in
    this guard keeps `_filing`'s wider one.

    UNCOMPUTABLE YIELDS NO TARGET, and what the CALLER does with that is where the cost sits. A
    `cd $DIR`, a bare `cd`, a `popd`: `_filing.directory_change` reports those as "not computed",
    so this function returns None rather than guessing -- which keeps the sweep judged against a
    directory that can actually be named. Until TSK-0120 the caller then simply kept the position
    it had, and that is the half this sentence used to leave out: `pushd outbox >/dev/null ; popd ;
    rm -rf .` swept the project root at rc 0, because `outbox` was still standing (`H150`, measured
    at `e45c0ca` too). The caller now adds the project root back to the candidates instead, and the
    price is named there.

    AND NEITHER DOES A CHANGE THAT DOES NOT LAND, which is verifier finding B5. Asking "is the
    command word a `cd`" and "can the target be computed" is not the same as asking whether the
    shell really ends up there: `cd nichtda ; rm -rf .` and `cd docs2 ; rm -rf .` (a typo -- the
    accident `DEC-0056` names) were rc 0 while `rm -rf .` alone was rc 2, because the base moved to
    a directory that does not exist and nothing there contains a tray. So the target has to BE a
    directory, and it has to lie INSIDE the project: `cd .. ; rm -rf .` lands above the project,
    where "no tray under this base" is the wrong answer -- everything of the project is under it --
    so the base stays put and the sweep is judged against the root.

    WHETHER THE CHANGE TAKES EFFECT AT ALL IS NOT THIS FUNCTION'S QUESTION and never was: it
    answers "where would this invocation leave the working directory", and the caller asks
    `_filing.changes_the_calling_shell` first, because that answer lives in the SEPARATORS around
    the invocation and this function is handed tokens. Until TSK-0120 nobody asked, and a `cd`
    behind a short-circuiting `&&`, inside a pipe stage or behind `&` moved the sweep base out of
    reach -- `H144` in docs/POST_V2_WISHLIST.md carries the four measured forms.

    NEITHER IS "FROM WHICH POSITION": `base` is ONE of the candidates the caller holds, and the
    caller asks this question once per candidate, because a relative target means something
    different from each of them. Asking it once, from the newest, was merge-verifier finding B2.
    """
    names_chdir, computed = _filing.directory_change(tokens)
    if not names_chdir or not computed:
        return None
    words = [token for token in tokens
             if not str(token).startswith("-") and not _ASSIGNMENT_RX.match(str(token))]
    if not words or _filing.command_name(words[0]) not in _filing.CHDIR:
        return None
    argument = next((token for token in words[1:]
                     if not _filing.rewritten_by_the_shell(token)), None)
    if argument is None:
        return None
    moved = os.path.normpath(os.path.join(base, str(argument).replace("\\", "/")))
    if not os.path.isdir(moved):
        return None
    return moved if _filing.position(root, moved, WORKING_DIRECTORY) is not None else None


def where_it_runs(root, bases):
    """The directory an invocation really runs in, out of the readings `_filing` offers.

    THE DEEPEST READING, and it is a definition rather than a position in the list -- which is what
    this had to be measured to learn. The two producers put the real directory in different places:
    `_filing.reading_bases` yields `[root, cwd]` (the real one LAST) while `_filing._bases_after`
    yields `[the cd target, ..., root]` (the real one FIRST), so `current[-1]` answered `docs/` for
    a payload whose cwd was `docs` and `root` for a line that had just done `cd docs` -- the same
    destruction measured rc 0 and rc 2.

    THIS ANSWERS THE START OF A LINE, never a `cd` inside it: `read_the_line` tracks that itself
    through `moves_the_working_directory`, because `_filing`'s own progression follows a `cd` that
    is only an ARGUMENT and a narrowing reader may not (verifier finding B4).
    """
    deepest, depth = root, -1
    for base in bases or [root]:
        try:
            here = os.path.relpath(base, root).replace("\\", "/")
        except (OSError, ValueError):
            continue
        if here.startswith(".."):
            continue
        found = 0 if here == "." else len(here.split("/"))
        if found > depth:
            deepest, depth = base, found
    return deepest


def swallows_a_tray(root, base, token):
    """Does what this ONE operand names CONTAIN a tray of record? — the second reach direction.

    ONE READER FOR TWO SHAPES that are one destruction: an operand that names the project root or
    the directory the line runs in (`.`, `./`, an absolute spelling of either), and the SWEEP that
    names nothing at all — the caller asks that one with `WORKING_DIRECTORY`. Splitting them into
    two branches is what verifier finding B1 measured: the branch for "no operand" existed, the one
    for "an operand that is the working directory" did not, and `git clean -fdx .` was rc 0 beside
    `git clean -fdx` at rc 2.

    THE TRAY HAS TO EXIST, and that is the over-refusal weighing rather than an optimisation:
    `rm -rf .` in a project that has no `archive/` and no `inbox/` destroys nothing this guard
    exists for, and refusing it there would be a wall with nothing behind it.

    THE BASE IS THE ONE THE LINE REALLY RUNS IN, and `where_it_runs` picks it (verifier finding M1). The
    readers beside this one try EVERY base a relative token could be meant against, because there
    over-refusal costs a correction and under-refusal costs a document; here it is the other way
    round — every base includes the project root, so asking all of them made `git clean -fdx`
    inside `docs/` a refusal, which is exactly the over-refusal that teaches a user to reach for the
    spelling B1 is about.
    """
    if not root:
        return False
    relative = _filing.position(root, base, token)
    if relative is None:
        return False
    here = "" if relative == "." else relative
    return any(os.path.isdir(os.path.join(root, tray))
               and (not here or _filing.under(tray, here))
               for tray in PROTECTED_TRAYS)


def writes_the_ledger(command):
    """Does any output redirect in `command` write to a `ledger/*.csv`? — reading every value a
    shell could hand the target (`_compat.shell_readings`), so the POSIX backslash spelling resolves
    too, exactly as the write-scope gate answers the same question for a state path."""
    return any(LEDGER_CSV_RX.search(reading)
               for target in _filing.redirect_targets(command)
               for reading in _compat.shell_readings(target))


def in_a_protected_tray(root, base, token):
    """The repo-relative path this token names, if it lies in a tray of record — else None."""
    relative = _filing.position(root, base, token)
    return relative if any(_filing.under(relative, tray) for tray in PROTECTED_TRAYS) else None


def _landing(destination, is_directory, source):
    """Where the document ENDS UP: the destination, or a file inside it when that names a folder.

    `mv archive/…/x.pdf outbox/` and `mv archive/…/x.pdf outbox/x.pdf` are one operation spelled
    two ways, and the approval names the position the document ends up at. Without this the first
    spelling asked for an approval on `outbox`, which is a folder and not the document — measured
    2026-08-18 in the refusal text of that very command ("moves archive/1-Finanzen/2026/x.pdf to
    outbox"). None stays None: a destination outside the repository has no position to approve.
    """
    if destination is None:
        return None
    if not is_directory:
        return destination
    name = os.path.basename(str(source).replace("\\", "/").rstrip("/"))
    return (destination + "/" + name) if name else destination


def _protected_readings(root, bases, token):
    """Every position inside a tray of record this ONE operand could be meant against."""
    readings = []
    for base in bases:
        relative = in_a_protected_tray(root, base, token)
        if relative and relative not in readings:
            readings.append(relative)
    return readings


def _move_readings(root, move):
    """{source token: [(source, landing, shown), …]} for the documents this move takes out of
    archive/ — every base tried, and source and destination always read against the SAME one."""
    readings, order = {}, []
    for base in move.bases:
        destination, is_directory = _filing.resolve(root, base, move.destination)
        if _filing.under(destination, _filing.ARCHIVE):
            continue
        for source in move.sources:
            relative = _filing.position(root, base, source)
            if not _filing.under(relative, _filing.ARCHIVE):
                continue
            landing = _landing(destination, is_directory or move.destination_is_directory, source)
            reading = (relative, landing, landing or destination or move.destination)
            if source not in readings:
                readings[source] = []
                order.append(source)
            if reading not in readings[source]:
                readings[source].append(reading)
    return [readings[source] for source in order]


class Line(object):
    """What one command line does, as far as THIS guard can place it.

    `deletes` and `moves` are the operations the two rules judge, one entry per document, each
    holding every position that document could be meant at (several bases may be in play, and only
    one of them is the real file — see `read_the_line`). `unplaced` is the first thing on the line
    this guard could NOT place, or None.

    WHY THE THIRD FIELD EXISTS AT ALL, and it is the correction of verifier finding F1. The refusal
    only ever needed the first two: something protected is being destroyed, so refuse. The DOOR
    needs the third, because a user approval names ONE correction and the door decides about the
    whole COMMAND LINE. With "every operation I recognised is approved" as the pass condition, an
    approved move carried through everything the reader did not recognise beside it — measured by
    the verifier as rc 0, where the wall alone answered rc 2, for a `python -c "os.remove(...)"` of
    another archive file, a `tar --remove-files`, a `rm $A`, and `rm inbox/a.pdf ~/archive/x.pdf`
    (F2). None of those is newly seen now; what changed is that they stop the DOOR instead of
    riding through it.
    """

    def __init__(self, deletes, moves, unplaced, sweeps=(), delete_in_text=False):
        self.deletes = deletes
        self.moves = moves
        self.unplaced = unplaced
        # A SWEEP IS A DESTRUCTION WITHOUT A DOCUMENT, so it can never be an approvable operation:
        # `sweeps` carries the reasons for the refusal and closes the door rather than joining
        # `deletes`. `delete_in_text` is the second, raw-text reading of the delete rule -- the
        # invocation carries a naming destruction and its text mentions a tray of record, while the
        # resolving reader placed nothing protected in it.
        self.sweeps = list(sweeps)
        self.delete_in_text = delete_in_text


def read_the_line(root, command, bases):
    """The whole command line, invocation by invocation — see `Line`.

    THE WALK IS OVER EVERY INVOCATION, not over the ones a filter kept (`_filing.invocations`).
    Each is placed as exactly one of four things and there is no fifth: a directory change this
    reader could compute; a relocation/copy; a delete; or something else. "Something else" is the
    honest answer for a program that does its own file handling (`python -c`, `tar`), and it is what
    keeps an approval from covering it.

    AN OPERAND HAS TO BE PLACEABLE IN TWO DIFFERENT SENSES, and each caught a case the other did
    not, which is why both are here:

      * its TEXT has to be the path (`_filing.rewritten_by_the_shell`). `rm inbox/a.pdf
        ~/archive/secret.pdf` places the first operand and resolves the second to a position under
        the project -- but the SHELL expands the `~` and deletes a file in the user's home, so the
        position the guard resolved is not the file that goes (F2). Same for a variable, a glob, a
        `%VAR%`;
      * and it has to RESOLVE to a position inside the project. `../archive/x.pdf` and
        `/etc/passwd` are ordinary text that names no place this guard can speak about; each was
        simply dropped, so an approved operand beside them made the line "fully approved".

    THE RAW-TEXT DELETE READING IS THE LAST WORD, per invocation: if the invocation carries a
    NAMING destruction and its raw text mentions a tray of record (`TRAY_IN_TEXT_RX`) while the
    resolving reader placed no PROTECTED position in it, the two readings disagree about what is
    being destroyed and the guard believes the one that says something is. That is an over-refusal
    by construction -- `rm outbox/archive-copy.txt` is a perfectly ordinary delete the text makes
    look protected -- and it costs a correction on that line, never a document.

    A SWEEP IS THE THIRD READING AND IT IS NOT AN OPERATION (H125). It is the reach read in the
    OTHER direction: a position that CONTAINS a tray of record rather than lying inside one, which
    is the project root, the directory the line runs in, or any ancestor of a tray. A sweeping word
    that names no path at all is that same question asked about `WORKING_DIRECTORY`.
    `swallows_a_tray` answers it, and only where the tray really exists -- which is what makes
    `git clean -fdx` a refusal in a project with an archive, no refusal in one without, and no
    refusal at all when it runs inside `docs/`.

    AN UNPLACEABLE OPERAND CLOSES THE DOOR AND NEVER HIDES AN OPERATION, and this paragraph is here
    because the first cut of it did exactly that: it `continue`d past an invocation carrying one, so
    the operations that invocation DID place never reached the caller and the WALL stopped seeing
    them. `mv archive/fin/a.pdf /tmp/gone.pdf` -- a move that empties the archive to a destination
    outside the project, the plainest case this guard exists for -- went from rc 2 to rc 0, caught by
    `tools/test_hooks.py::test_fs_tripwire_blocks_move_out_of_archive`, a test older than this door.
    So `unplaced` is recorded and the reading CONTINUES: the refusal keeps everything it ever saw,
    and only `open_the_door` consults `unplaced`.
    """
    deletes, moves, unplaced, sweeps, delete_in_text = [], [], None, [], False
    # WHERE THE LINE COULD BE STANDING -- a SET and not a single value, and that is the whole of
    # merge-verifier finding B1. Only an invocation whose COMMAND WORD is a directory change may
    # move it (B4), and a change the shell may never perform may not move it either (`H144`) -- but
    # "may not move it" was written as "leave the old value alone", and a stale value is only
    # fail-closed while the ignored change leads AWAY from a tray. Leading BACK, it left a harmless
    # base standing: `cd outbox && cd .. && rm -rf .` was ALLOW while `rm -rf .` alone was rc 2.
    # So an uncertain change ADDS a candidate instead of replacing one, and the sweep below is
    # refused when ANY candidate contains a tray of record.
    standing = [where_it_runs(root, bases)]

    def unreadable(reason):
        return reason if unplaced is None else unplaced

    def unplaceable(operands, current):
        """The first operand of this invocation this guard cannot speak about, or None."""
        for operand in operands:
            if _filing.rewritten_by_the_shell(operand):
                return "%s -- the shell rewrites it before the command sees it" % operand
            if not any(_filing.position(root, base, operand) for base in current):
                return "%s -- it names no place inside this project" % operand
        return None

    walked = _filing.invocations(command, bases)
    for index, (text, tokens, current, separator_before) in enumerate(walked):
        separator_after = walked[index + 1][3] if index + 1 < len(walked) else ""
        # A REDIRECT IS PART OF WHAT THE LINE DOES, and it is not an operand of anything: `>` is
        # shell syntax, so the argument readers below cannot see it. `> inbox/b.pdf` TRUNCATES a
        # document of record to nothing, which is the class these trays exist for -- and behind an
        # approved move the whole line answered rc 0 (verifier round 2, R1). A target in a tray is
        # never an approvable OPERATION either: a `filing_correction` binds bytes that exist at a
        # position, and the bytes a redirect will write do not exist when the user is asked. So it
        # closes the door, like anything else this guard cannot place.
        #
        # READ BEFORE THE TOKEN CHECK BELOW, and that ordering is the whole of verifier round 3.
        # `_tokens` cuts an invocation at its first redirect operator, so an invocation whose
        # redirect comes FIRST has no tokens at all -- `> outbox/log.txt rm archive/…/y.pdf` is one
        # tokenless invocation carrying a delete. Skipped before this scan, the line knew of no
        # operation AND of nothing unplaced, so the delete rule was disabled outright: HEAD rc 2,
        # measured rc 0 (V1), and the same shape rode an approved move through the door (V2).
        for target in _filing.redirects_of(text):
            if _filing.rewritten_by_the_shell(target):
                unplaced = unreadable("a redirect target the shell rewrites before use (%s)"
                                      % str(target)[:80])
            elif any(in_a_protected_tray(root, base, target) for base in current):
                unplaced = unreadable(
                    "a redirect that writes into a tray of record (%s) -- no approval can name the "
                    "bytes a redirect has not written yet" % str(target)[:80])
            elif not any(_filing.position(root, base, target) for base in current):
                unplaced = unreadable("a redirect target this guard cannot place (%s)"
                                      % str(target)[:80])
        if not tokens:
            # AN INVOCATION WITH NO COMMAND WORD IS NOW EXACTLY ONE THING: redirects and whitespace.
            # `_tokens` cuts the redirects OUT rather than ending the argument list at them, so
            # anything else would have produced a word -- and the scan above has already judged
            # every one of those redirects. Marking it unplaced on top was measured as pure
            # over-refusal (`… && > outbox/log.txt`, a fully placed redirect outside the trays,
            # became rc 2 with no protection behind the refusal), so it is not done.
            continue
        names_chdir, computed = _filing.directory_change(tokens)
        if names_chdir:
            if not computed:
                unplaced = unreadable("a directory change this guard cannot follow (%s)"
                                      % " ".join(str(token) for token in tokens)[:80])
            # A CHANGE THE SHELL MAY NEVER PERFORM DECIDES NOTHING (`H144`): the separators
            # around this invocation say whether it is certain to run and whether it runs in THIS
            # shell. The reader is `_filing.changes_the_calling_shell`, and it lives there because
            # the separator is a property of the decomposition, not of this guard.
            #
            # THE CHANGE IS APPLIED TO EVERY CANDIDATE, and that is merge-verifier finding B2. A
            # RELATIVE target means something different from each of them -- `cd ../outbox` lands
            # in the project's own `outbox` from `docs` and OUTSIDE the project from the root --
            # so computing it from one candidate answers for one shell only. Reading it from the
            # newest one is the worst of the choices: after an uncertain change the newest is the
            # position the shell may never have reached, and a CERTAIN change then replaced the
            # whole set with a target derived from it. Measured against a real bash as arbiter
            # (`_round-scratch/TSK-0120/verify_tools/shell_truth.py`), which stands on the ROOT for
            # all three of `cd docs | true ; cd ../outbox ; rm -rf .`,
            # `false && cd docs ; cd ../outbox ; rm -rf .` and
            # `cd docs | true ; cd ../docs/inner ; rm -rf .`, while every hook answered rc 0.
            #
            # A candidate the change cannot be computed FROM keeps its own position: that is the
            # `H150` half -- an uncomputable change (`popd`, a bare `cd`) yields no target at all,
            # so every candidate stays and the project root joins them, because from an unknown
            # position the shell may be anywhere and the root contains every tray of record.
            mapped = [(moves_the_working_directory(root, tokens, one) or one) for one in standing]
            if not computed and standing[-1] != where_it_runs(root, bases):
                mapped = mapped + [where_it_runs(root, bases)]
            if _filing.changes_the_calling_shell(separator_before, separator_after):
                standing = list(dict.fromkeys(mapped))
            else:
                standing = list(dict.fromkeys(standing + mapped))
            continue
        move = _filing.move_of(tokens, current)
        if move is not None:
            operands = list(move.sources) + ([move.destination] if move.destination else [])
            beyond = unplaceable(operands, current)
            if beyond:
                unplaced = unreadable("a copy/move operand this guard cannot place (%s)"
                                      % beyond[:100])
            if _filing.relocating(move) and move.destination:
                moves += _move_readings(root, move)
            elif move.destination and destruction_of(tokens) is not None:
                # A COPIER THAT DESTROYS IN ITS DESTINATION (`H123`). `_filing` reads `robocopy
                # inbox archive/2026 /MIR` and `rsync --delete inbox/ archive/2026/` as copies, and
                # this branch used to answer them and return before any destroying word was looked
                # for -- so a copy INTO the archive purged it and nothing noticed. The distinction
                # that decides is the one `_filing` already makes: a RELOCATING flag deletes in the
                # SOURCE and is the kit's ordinary filing move (`rsync --remove-source-files`,
                # above); any other destroying word on a copier acts on the DESTINATION, so the
                # destination is the reach
                # (`tools/test_hooks.py::test_a_copier_that_destroys_in_its_destination_is_a_delete_there`).
                placed = _protected_readings(root, current, move.destination)
                if placed:
                    deletes.append(placed)
            continue
        destruction = destruction_of(tokens)
        if destruction is not None:
            operands = destruction_operands(tokens)
            beyond = unplaceable(operands, current)
            if beyond:
                unplaced = unreadable("a delete operand this guard cannot place (%s)" % beyond[:100])
            placed = [readings for readings in
                      (_protected_readings(root, current, operand) for operand in operands)
                      if readings]
            if not placed and TRAY_IN_TEXT_RX.search(text) and destruction == "naming":
                delete_in_text = True
                unplaced = unreadable(
                    "a delete that names a tray of record in its text while this guard could place "
                    "no protected operand in it (%s)" % text.strip()[:80])
            # THE SECOND REACH DIRECTION, and it is ONE question asked of one list. What the line
            # names is the reach; a SWEEPING word that names nothing reaches the directory it runs
            # in, which is written as the path that names it rather than as a second branch. A
            # position that CONTAINS a tray of record is no document -- no approval can be minted
            # for it -- so it is recorded as a sweep and not as a delete.
            reach = operands or ([WORKING_DIRECTORY] if destruction == "sweeping" else [])
            if any(swallows_a_tray(root, one, word)
                   for one in standing for word in reach):
                sweeps.append(text.strip()[:80])
                unplaced = unreadable(
                    "a destruction whose reach contains a tray of record, so it destroys documents "
                    "of record without naming one (%s)" % text.strip()[:80])
            deletes += placed
            continue
        unplaced = unreadable("an invocation this guard does not read as a filing operation (%s)"
                              % str(tokens[0])[:80])
    return Line(deletes, moves, unplaced, sweeps, delete_in_text)


def correction_authority(root):
    """(kernel approvals module, {operation key: approval}) for this call — or None. ONE store read.

    THE KERNEL BRIDGE IS IMPORTED HERE AND NOWHERE ELSE IN THIS PROCESS, and that placement is the
    whole reason this guard may ask an approval question at all. `_filing`'s docstring records why
    the bridge stays out of this hook: importing it arms an excepthook that turns any escaping error
    into exit 2, which is right for a fail-closed gate and is NOT this guard's contract —
    uncertainty leaves the command alone. This runs only on a branch that has ALREADY decided to
    refuse, so there the two contracts agree: anything that goes wrong while looking for an approval
    means none was found, and the refusal stands. `disarm()` puts the interpreter's own excepthook
    back before returning.

    ONCE PER CALL, NOT ONCE PER OPERAND, and that is verifier finding F3 rather than an optimisation.
    Opening the state and scanning the approval store per operand made a REFUSAL cost time
    proportional to the line: 8000 documents on one `rm` took 114 s where the wall alone took 0.54 s.
    That was written when a kill at the registration's deadline was believed to be what came next;
    BUG-0062 measured that no registration of this kit names one and none is killed, so what 114 s
    really buys is a session frozen on one command with no sign of why. The store is read once into
    a map here; the door then does dictionary lookups.

    ANY failure is None on purpose — no kernel, no state directory, an unreadable store. "I could
    not check" and "there is no approval" have to be one answer in a guard, and it is the one that
    keeps the documents.
    """
    try:
        import _kernel
        try:
            if not os.path.isdir(_kernel.state_dir(root)):
                return None
            approvals = _kernel.kernel_module("approvals", root)
            hashing = _kernel.kernel_module("hashing", root)
            live = approvals.live_correction_approvals(_kernel.open_state(root))
            return approvals, hashing, live
        finally:
            _kernel.disarm()
    except BaseException:       # noqa: BLE001 — see the contract above
        return None


def open_the_door(root, line):
    """(corrections let through, why not, which operation) — ONE decision about the WHOLE line.

    Four things have to hold, and the first two are about the line rather than about any operation:
    the guard placed everything on it (`Line.unplaced`), it asks for no more corrections than
    `CORRECTION_CAP`, a live user approval exists for every operation, and each approval names that
    operation exactly — the document, the version of it that lies there now, and the destination or
    its absence.

    THE CAP IS A REFUSAL AND NOT A TRUNCATION. Above it the door does not open at all, so the wall
    answers as it always did; what the cap buys is that it answers FAST. It is a bound on the work a
    PreToolUse hook may do while deciding, and the reason is the one `correction_authority` gives:
    past the provider's deadline a refusal becomes a pass.

    THE FIRST UNCOVERED OPERATION ENDS IT, and it is also the one the refusal NAMES. Every
    operation costs a file read (the version hash), so carrying on after the answer is settled is
    time spent on a call that is already refused — and naming the FIRST operation instead of the
    uncovered one sent a role back to the user for an approval it already held
    (`tools/test_hooks.py::test_a_refusal_names_the_document_that_is_missing_its_approval`).

    AN EMPTY ANSWER IS "THE DOOR DID NOT OPEN", NEVER "THE DOOR OPENED FOR NOTHING". This function
    is only ever asked when one of the two rules has fired, so a line it can name no operation on is
    a line whose two readings disagree — the raw-text delete reading saw something the resolving one
    could not place. Returning `[]` there made `if honoured is None` in `main` fall through to the
    ALLOW, which is verifier round 3's V1 in its second half.

    IT IS THE FIRST CHECK AND IT IS MEASURED DIRECTLY, because on a real command line the `unplaced`
    branch below now answers every case that reaches it first: after `_filing._tokens` stopped
    ending the argument list at a redirect, no line was left that has no operation AND nothing
    unplaced. So the branch is kept for what it MEANS rather than for a chain that reaches it, and
    `tools/test_hooks.py::test_the_door_answers_an_empty_line_as_closed_not_as_open` asks this
    function for that shape outright instead of pretending a command line produces it.
    """
    operations = [(readings, False) for readings in line.deletes] \
        + [(readings, True) for readings in line.moves]
    if line.sweeps:
        # ASKED BEFORE ANYTHING ELSE because a sweep is the one refusal no approval can ever cover:
        # a `filing_correction` binds ONE document by its bytes, and a destruction that names no
        # path names no document to bind. Answering it through the "no operation" branch below
        # would have told the user their two readings disagree, which is not what happened here.
        return None, ("this command line destroys without naming a single document, and its reach "
                      "contains a tray of record: %s. No user approval can cover it -- a correction "
                      "is minted for ONE document and this line names none. THIS IS NOT A SPELLING "
                      "PROBLEM: naming the project root or the working directory (`.`, `./`) is the "
                      "same destruction and is refused the same way, so re-spelling the line is not "
                      "the way out. Ask the USER what is really to be removed; anything under "
                      "inbox/ or archive/ then goes one document at a time through the route below"
                      % "; ".join(line.sweeps)), None
    if not operations:
        return None, ("this guard could place no operation on this command line at all, so there is "
                      "nothing a user approval could cover — its own two readings of the line "
                      "disagree about what is being destroyed, and it believes the one that says "
                      "something is"), None
    if line.unplaced:
        return None, ("this command line also does something this guard could not place: %s. An "
                      "approval names ONE correction and cannot cover what nobody can read, so "
                      "nothing on this line is let through. Run the approved correction on a line "
                      "of its own." % line.unplaced), None
    if len(operations) > CORRECTION_CAP:
        return None, ("this command line would correct %d documents at once, and the door opens for "
                      "at most %d — a gate that is still deciding when its deadline passes is read "
                      "as a gate that allowed the call, so the work it may do is bounded. Ask for "
                      "the corrections in smaller batches."
                      % (len(operations), CORRECTION_CAP)), None
    authority = correction_authority(root)
    if authority is None:
        return None, ("no user approval could be looked up for this project at all (no state "
                      "directory, or it could not be read)"), None
    approvals, hashing, live = authority
    honoured, versions = [], {}
    for readings, is_move in operations:
        found = None
        for reading in readings:
            document, target = (reading[0], reading[1]) if is_move else (reading, "")
            if is_move and not target:
                continue      # a destination outside the project has no position to approve
            if document not in versions:
                versions[document] = hashing.document_content_hash(
                    os.path.join(root, document)) or ""
            if not versions[document]:
                continue      # bytes that cannot be read cannot be the bytes anybody approved
            approval = live.get(approvals.correction_operation_key(
                document, target, versions[document]))
            if approval is not None:
                found = (approval, document, target)
                break
        if found is None:
            offender = (readings[0][0], readings[0][2]) if is_move else (readings[0], "")
            return None, ("%s carries no live user approval for exactly this correction"
                          % offender[0]), offender
        honoured.append(found)
    return honoured, None, None


def record_corrections(command, honoured):
    """Journal the corrections this call was let through on — see the module docstring's last
    paragraph for what that record does and does not claim.

    CALLED ONCE, AFTER EVERY CHECK HAS PASSED, and that is not tidiness. A command line can delete
    one document and move another out, and the two used to be judged in sequence: writing the note
    inside the first branch put "allowed under APR-000n" into the journal for a call the SECOND
    branch then refused. A record of a passage that never happened is worse than no record
    (`tools/test_hooks.py::test_a_refused_call_leaves_no_note_claiming_a_correction_was_let_through`).

    AND NOTHING IS WRITTEN FOR AN EMPTY LIST, which is the same rule one shape further down. With
    no correction honoured the sentence came out as "allowed under user approval : " -- an empty id
    list and an empty operation list, a claim of a passage under an approval that does not exist
    (verifier round 3, V4). The caller no longer reaches here with an empty list; this is the second
    lock, because the first one has now been picked twice
    (`tools/test_hooks.py::test_a_journal_line_never_claims_a_passage_under_no_approval_at_all`).
    """
    if not honoured:
        return
    _audit.record_event(
        "guard_fs_tripwire", "correction-allowed",
        "allowed under user approval %s: %s | %s"
        % (", ".join(str((approval.get("id") or "?")) for approval, _d, _t in honoured),
           "; ".join("%s -> %s" % (document, target or "DELETED")
                     for _a, document, target in honoured),
           command[:120]))


def main():
    # BOUNDED read (spec II.4). A raw `json.load(sys.stdin)` will happily buffer a
    # payload of any size, and an oversized one is the shape that turns a hook into
    # a memory event rather than a decision. `_compat.load` caps it at STDIN_LIMIT
    # and exits 2, because a gate that cannot read its input has not judged it.
    data = _compat.load()
    if data.get("tool_name") not in ("Bash", "PowerShell"):
        sys.exit(0)
    cmd = str((data.get("tool_input") or {}).get("command") or "")
    cwd = str(data.get("cwd") or "")
    root = _root.find_repo_root(cwd)
    bases = _filing.reading_bases(root, cwd)
    if writes_the_ledger(cmd) and not LEDGER_ADD_RX.search(cmd):
        _audit.record("guard_fs_tripwire", "shell redirect into ledger: %s" % cmd[:120])
        _compat.stop(
            "[team-kit guard] A blind shell redirect into ledger/*.csv is BLOCKED — `>>` writes "
            "whatever it is handed, with no schema, no arithmetic check and no way to tell a row "
            "from a fragment. Editing the ledger IS allowed (user decision V2 I.3/1): use Edit, or "
            "`python scripts/ledger_add.py ...` for a new entry. Either way the whole file is "
            "re-validated afterwards and a failure marks the ledger invalid.\n", "PreToolUse")
    # ONE READING OF THE LINE, ONE DECISION ABOUT IT. The two rules keep their own refusal texts --
    # they refuse different things and a role has to be told which -- but whether the DOOR opens is
    # a question about the whole command line and is asked once (`open_the_door`). Asking it per
    # rule is what let an approved delete carry an unapproved move through, and the journal note
    # then claimed a passage the second rule refused.
    line = read_the_line(root, cmd, bases)
    # THE THREE WAYS THE DELETE RULE FIRES, all read per invocation by `read_the_line`: a protected
    # position an operand resolved to, a sweep whose reach meets a tray, and the raw-text reading
    # that fires where those two disagree. Until H125 the third one was a regex over the WHOLE
    # command asked here, built from a tuple of verbs; the reading now lives with the invocation it
    # belongs to, so one vocabulary answers both readings.
    breaks_the_delete_rule = bool(line.deletes or line.sweeps or line.delete_in_text)
    if not breaks_the_delete_rule and not line.moves:
        sys.exit(0)
    honoured, refused, offender = open_the_door(root, line)
    # `not honoured`, NOT `honoured is None`. An empty list is a door that opened for nothing, and
    # `[] is not None` walked straight past this branch into the ALLOW while one of the two rules had
    # fired -- verifier round 3, V1: a leading redirect made the line tokenless, so no operation was
    # placed, and `rm archive/…/y.pdf` behind it went from rc 2 to rc 0. `open_the_door` no longer
    # RETURNS that shape, so this is the second lock on one door and no test can tell it from the
    # first -- it is here because the first lock has now been picked twice, not because anything
    # measures it.
    if not honoured:
        if breaks_the_delete_rule:
            _audit.record("guard_fs_tripwire",
                          "delete on inbox/archive (%s): %s"
                          % (refused, cmd[:120]))
            _compat.stop(
                "[team-kit guard] Deleting under inbox/ or archive/ is BLOCKED — business documents "
                "are moved (with a filing/migration manifest), never deleted. Duplicates get a "
                "_dupNN suffix and a flag.\nWhy this call is not covered by a user approval: %s.\n"
                % refused + CORRECTION_REMEDY, "PreToolUse")
        # the move the refusal NAMES is the one that is missing its approval; a refusal about the
        # line as a whole (unplaced, cap) has no such operation and names the first move instead
        source, shown = offender if (offender and offender[1]) \
            else (line.moves[0][0][0], line.moves[0][0][2])
        _audit.record("guard_fs_tripwire",
                      "move out of archive (%s -> %s): %s" % (source, shown, cmd[:120]))
        _compat.stop(
            "[team-kit guard] Moving files OUT of archive/ is BLOCKED — the archive is the "
            "system of record. This command moves %s to %s, which is outside it. "
            "Reorganisation runs as a user-approved migration PROC (dry-run -> OK -> move + "
            "manifest); ask the manager/user instead of working around this. A move that STAYS "
            "inside archive/ is not this rule and is not blocked, whichever way it is spelled.\n"
            "Why this call is not covered by a user approval: %s.\n"
            % (source, shown, refused) + CORRECTION_REMEDY, "PreToolUse")
    record_corrections(cmd, honoured)
    sys.exit(0)


if __name__ == "__main__":
    main()
