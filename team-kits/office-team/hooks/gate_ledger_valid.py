#!/usr/bin/env python3
"""
Ledger-validity gate (office) — spec II.9 after user decision I.3/1.

Append-only is GONE, and with it `guard_ledger_direct`, which refused every hand edit. The user's
reasoning: forbidding edits did not make the data trustworthy, it made corrections cost a reversal
entry even for a typo, and git history plus Evidence is the audit trail. So edits are allowed —
and always validation-required.

  PreToolUse(Bash|PowerShell) on commit/push/merge/tag/report   VALIDATE NOW, then allow or refuse
  PreToolUse(Agent|Task)                                        VALIDATE NOW, then allow or refuse
  PostToolUse(Edit|Write|MultiEdit|Bash|PowerShell)             early warning: validate what changed

ENFORCEMENT VALIDATES SYNCHRONOUSLY. IT DOES NOT TRUST A RECORD.
The first cut derived the block from a marker file that a PostToolUse sweep maintained, with a
size+mtime cache deciding what to re-check. Every one of those pieces turned out to be a way
through, and they were found in one review pass:

  * deleting the marker released the block PERMANENTLY, because the cache still said "seen"
  * writing a forged stamp into the cache made a corrupted file invisible to the sweep
  * `sed -i … && git commit` in ONE call committed before any sweep ran
  * `touch -r` (or plain `cp -p`, `tar -p`, `robocopy /COPY:T`) kept size and mtime, so the sweep
    skipped a rewritten file
  * a marker that could not be WRITTEN failed open while the message said everything was blocked
  * a corrupt marker with no ledger present deadlocked the repo with a remedy that could not work

The pattern is one mistake, not six: a gate whose verdict comes from a document that the guarded
party can influence is a gate on that document, not on the ledger. So the operations II.9 actually
protects — commit, push, merge, reports, dispatch — now run the validator against the ledger AT
THAT MOMENT and decide on the result. They are rare, the cost is one subprocess per ledger file,
and there is nothing left to forge. The stored state is a CACHE for the early-warning path only,
and is never consulted by the enforcing path.

WHY THE POST HALF STILL EXISTS: it cannot block (hooks reference — PostToolUse shows stderr but
does not deny), so it is not enforcement. What it buys is telling the agent that it just broke the
ledger, at the moment it broke it, instead of several tool calls later as an unexplained refusal
to commit. Spec II.9: "Ein Post-Edit-Fehler markiert den Zustand sichtbar ungueltig (behauptet
kein Rollback)."

THE VALIDATION LIVES IN `scripts/ledger_add.py --validate` — the same `validate_row` /
`validate_cross` the write path uses, so there is one definition of "valid ledger". That script is
part of the enforcement layer: `guard_harness_selfmod` blocks Edit/Write on it (verified by
`test_the_validator_is_on_the_enforcement_layer`), and this gate refuses shell writes to it.
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

import json  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

import _compat  # noqa: E402

HOOK = "gate_ledger_valid"
FILE_TOOLS = ("Edit", "Write", "MultiEdit")
SHELL_TOOLS = ("Bash", "PowerShell")
SPAWN_TOOLS = ("Agent", "Task")
# Early-warning cache ONLY. Never read by the enforcing path, so forging it buys nothing; it is on
# guard_harness_selfmod's blocked list anyway, because a stale "everything is fine" note is still
# a lie the next reader believes.
STATE = os.path.join(".claude", "ledger_state.json")
# ...spelled with a FORWARD slash, in the one place both the filesystem and the refusal text read
# it from. `os.path.join` put a backslash here on Windows, and this gate prints the path into its
# own remedy (`python <VALIDATOR> --validate <file>`) beside a findings list that names the ledger
# with forward slashes. That mixed line is one this gate REFUSES: a backslash is consumed by the
# POSIX reading of the word (`_readings_of`), the canonical path is gone in that reading, and what
# is left is a ledger path with an unvouched interpreter run beside it -- measured rc 2 while both
# uniform spellings were rc 0. A remedy has to be safe under EVERY reading, and that is what the
# forward slash is (`tools/test_hooks_v2.py::test_the_remedy_this_gate_prints_is_one_it_accepts`).
# `os.path.join(root, …)` takes it unchanged on both platforms.
VALIDATOR = "scripts/ledger_add.py"
# THE canonical ledger: `ledger/*.csv` at the repo root, nothing else. An earlier cut matched any
# path with a `ledger` component, which meant a bank export dropped in `inbox/ledger/` was judged
# against the accounting schema and blocked the whole project — and the enforcing sweep and the
# edit branch disagreed about which files they covered, so a file could be marked and then never
# re-checked. One definition, used by both.
LEDGER_DIR = "ledger"
# ...and a ledger file is `<4-digit-year>.csv`, because that is what `euer_report.py` reads
# (`ledger/%d.csv`). Any OTHER csv in the directory was an ID SOURCE for the validator's
# cross-file reversal lookup while being invisible to the report: a `scratch.csv` carrying a row
# with the reversed id made a reversal of a booking the report never sees validate clean, and the
# quarter then reported a negative total. A stray `2026 - Kopie.csv` does it by accident.
YEAR_FILE_RX = re.compile(r"^[0-9]{4}\.csv$", re.IGNORECASE)
# A ledger CSV validates in milliseconds; 20s already means something is badly wrong. The number
# used to be argued from the platform's per-hook default, which BUG-0062 measured away (see
# `_compat.HOOK_DEADLINE_SECONDS`): no registration of this gate names a `timeout` any more, so
# nothing outside this process bounds it, and these two constants are the whole bound there is.
VALIDATE_TIMEOUT = 20
# ...and a cap for the WHOLE run, so one broken file cannot turn a gate into a hung session. It is
# the process's own promise and it does not derive from anything: being killed is the one outcome
# this hook cannot turn into a refusal, and not being killed is the one thing it cannot arrange.
TOTAL_BUDGET = 40

# The follow-on operations II.9 names: "Dispatch, Commit, Merge und Reports". `git add` stays
# allowed: staging a CORRECTION is how the block gets resolved. A set of SUBCOMMANDS, matched
# through `_compat.git_invocations` and its `runs` test: the previous version spelled the whole
# invocation as a regex and therefore missed `git "commit"` on both views it searched — the raw
# text (the quotes sit where the pattern wants the verb) and the prose-stripped one (the span with
# the verb in it was deleted). What an operation IS cannot be a question about quoting, about
# which word stands in front of `git` (`sudo "git" commit -m x` reached HEAD with an INVALID
# ledger — measured, rc 0), or about whether the verb is spelled or computed.
_BLOCKED_GIT_SUBCOMMANDS = frozenset((
    "commit", "push", "merge", "rebase", "tag", "revert", "cherry-pick", "am", "format-patch",
    "bundle", "archive", "send-email"))
# ...and the report generators. `einvoice_extract` is deliberately NOT here: extracting a document
# reads nothing from the ledger, so blocking it stops the work that produces the correction.
_BLOCKED_SCRIPT_RX = re.compile(r"\beuer_report\b", re.IGNORECASE)
# The validator and the state file are enforcement, not data.
_PROTECTED_RX = re.compile(r"ledger_add\.py|ledger_state\.json", re.IGNORECASE)
# ...and a write into the DIRECTORY that holds them. `tar -xf evil.tar -C scripts/` names no
# protected FILE, so the file-level pattern saw nothing while the extraction replaced the
# validator — the same directory-destination blind spot the ledger path had in round 7, in the
# other half of the gate. Only used by `_writes_protected`, where a verb has already been judged
# non-reading, so `python scripts/ledger_add.py --validate` is unaffected. That claim held for the
# BARE line and not for the same line inside a substitution until `BUG-0065`; what makes it true
# for both is `_WORD_END` below
# (`tools/test_hooks_v2.py::test_a_closing_paren_ends_a_word_for_this_reader_too`).
# ...as a DESTINATION, not as a mention. Matching any path under `scripts/` refused `ruff check
# scripts/`, `bash scripts/setup.sh` and `chmod +x scripts/tool.sh` — none of which writes the
# validator. A destination is the bare directory after an extraction/output flag, after a copy or
# move, or as a redirect target; everything else is somebody doing ordinary work in that folder.
# WHERE A SHELL WORD ENDS, written once instead of at each closer that needs it. A word ends at
# whitespace or at a shell METACHARACTER; the two closers below enumerated the metacharacters that
# had come up so far, and `)` was not among them — so `echo "$(tar -xf evil.tar -C scripts/)" &&
# git commit` unpacked over the validator's directory and committed, exit 0 (`BUG-0065`). The
# substitution's OPENING becomes a segment separator (`_SUBSTITUTION_OPEN_RX`) while its CLOSING
# paren stays glued to the target word, so the word this reader saw was `scripts/)`. The BACKTICK
# is here for the same reason and was measured missing from the first cut of this line: it opens
# and closes the older command substitution, so `echo "`tar -xf evil.tar -C scripts/`" && git
# commit` left the word as `scripts/` followed by a backtick and stayed exit 0 while the `$(…)`
# spelling of the same attack refused.
#
# THIS SET IS HAND-WRITTEN. It is NOT derived from anything, and a previous version of this line
# said it was `_compat._SYNTAX_CHARS` — which it is not (that set is `&|;#\n\r`: no quotes, no
# parens, no redirection, and it carries a `#` this one does not). Saying "derived" turned the very
# enumeration that was the defect into a claimed definition. What it has instead of a derivation is
# the tripwire CLAUDE.md asks of an unavoidable enumeration, measuring both ends:
# `tools/test_hooks_v2.py::test_every_word_end_character_is_needed_and_no_other_ends_the_word`
# states the set a SECOND time, independently, so dropping an entry here and adding one both show
# up as a disagreement. What it does NOT do is ask a shell whether the set is right; that
# comparison is not built, and this line is hand-written for exactly that reason.
#
# WHAT IT CANNOT SEE, measured rather than argued: a destination word the shell only BUILDS by
# expansion. `cp evil.py scripts/$f` with `f` unset copies into the bare directory — filesystem
# witness, the file lands in `scripts/` — while this reader sees the word `scripts/$f` and no
# destination. Adding `$` to the set does not fix that: it would read `scripts/$f` as the bare
# directory even when `f` names a file, and the word the shell finally builds is not in the text at
# all. The gap is the expansion and not the character, and it is OPEN: nothing below closes it and
# no test here claims it is closed.
_WORD_END_CHARS = r"\s\"'`;|&()<>"
_WORD_END = r"(?=[" + _WORD_END_CHARS + r"]|$)"
# ...and the same set as a plain match, for the one reader that asks whether such a character sits
# INSIDE a word instead of after it (`_as_one_word`). Derived from the class above rather than
# written twice, so the two cannot drift apart; the class itself keeps the tripwire named there.
_A_WORD_END_CHAR_RX = re.compile("[" + _WORD_END_CHARS + "]")
_PROTECTED_DIR_RX = re.compile(
    r"(?:-C|-d|--directory|-o|-O|--output|>|>>)\s*[\"']?(?:\./)?scripts/?" + _WORD_END +
    r"|\b(?:cp|mv|copy-item|move-item|rsync|install)\b[^\n;|&]*?\s(?:\./)?scripts/?" + _WORD_END,
    re.IGNORECASE)
# A SECOND file called `ledger_add.py` outside `scripts/` has no legitimate reason to exist: the
# canonical one is protected, so a decoy is how you get a validator nobody guards.
_DECOY_VALIDATOR_RX = re.compile(
    r"(?<![\w/.-])(?!(?:\./)?scripts/)(?:[^\s;|&]*/)?ledger_add\.py", re.IGNORECASE)
# ...unless the command stepped INTO the directory first. `cd scripts && python ledger_add.py
# --validate …` is the sanctioned way out of a block, typed from inside the folder, and reading
# the bare name there as a decoy refused the remedy itself.
# THE WORD HAS TO BE THAT DIRECTORY, and `\b` does not say so — it is satisfied by `-`, `.` and `/`
# alike, so `cd scripts-evil`, `cd scripts.bak` and `cd scripts/../evil` each bought the exemption
# for a directory nobody guards, and the bare `ledger_add.py` there is the attacker's own program
# (measured rc 0 through the registered chain; at HEAD the same lines were refused only because the
# decoy check stood in front of the exemption, which is the over-refusal `BUG-0064` removed —
# `tools/test_hooks_v2.py::test_only_the_validators_own_directory_forgives_the_bare_name`).
_CD_SCRIPTS_RX = re.compile(r"(?:^|[;&|])\s*cd\s+\.?/?scripts/?" + _WORD_END, re.IGNORECASE)
# ...and that is ALL it forgives: a validator path with no directory part. In `scripts/` the BARE
# name is the canonical file; `tools/ledger_add.py` and `../tools/ledger_add.py` name a different
# file from every working directory there is. The exemption used to be asked of the whole COMMAND
# and then ended the decoy loop outright, so one `cd scripts` anywhere disarmed the rule for every
# segment — `python tools/ledger_add.py && cd "scripts" && git commit` ran a validator nobody
# guards and committed, exit 0, and the quote spelling reached that state only because
# `_readings_of` produced the `cd scripts` the raw text did not have
# (`tools/test_hooks_v2.py::test_stepping_into_the_validators_directory_forgives_only_the_bare_name`).
_ANY_VALIDATOR_PATH_RX = re.compile(r"(?<![\w/.-])(?:[^\s;|&]*/)?ledger_add\.py", re.IGNORECASE)
# A command that writes the ledger AND commits it in one breath. Validating synchronously cannot
# help here: the verdict is already stale when the same command rewrites the file afterwards, and
# the PostToolUse warning arrives after the commit is in HEAD. So this shape is refused outright,
# valid ledger or not — the remedy is to run the two halves as two calls, which costs nothing.
# Two shapes: a named CSV, and the bare DIRECTORY as a destination. The second was missing, and
# `mv export-2027.csv ledger/ && git add -A && git commit -m 'import'` therefore dropped a broken
# file into the ledger and committed it in one call -- verified end to end, with the bad row in
# HEAD. A trailing `ledger/` is the natural way to write "put the corrected export in there", and
# the explicit-filename forms were the only ones ever checked.
_LEDGER_PATH_RX = re.compile(
    # ANYTHING under the directory, not only `*.csv`: `split -l 500 big.csv ledger/part-` writes
    # a family of files whose names the pattern could not predict, and a write into the ledger
    # directory is a write into the ledger whatever the file ends up being called.
    r"\bledger/[^\s;|&]*"
    # ...and the directory named WITHOUT a trailing slash, which `cp file ledger` also writes into.
    # Bounded so it is a whole path token: `(?<![\w/.-])` keeps `/tmp/ledger` and `ledger_add.py`
    # out (`_` is a word character, so there is no boundary inside `ledger_add`).
    #
    # THIS PATTERN ANSWERS "WHICH PATH", NEVER "IS THIS A WRITE". Until TSK-0083 the line above
    # named a write DENYLIST as its precondition -- a constant no code path read any more, the
    # read-only allowlist below having taken that question over. The reader was told this rule was
    # held on a leash that did not exist. What decides whether a segment naming a ledger path
    # WRITES it is `_verb_only_reads`, asked in `_a_reading_writes_the_ledger` of the stages beside
    # the vouched runs (and of the whole segment in the `cd ledger` fallback at its end), plus the
    # redirect targets of that segment.
    r"|(?<![\w/.-])ledger(?=[\s;|&]|$)", re.IGNORECASE)
# ...plus the working-directory form. `gate_write_scope` in this kit already tracks `cd` carry-over
# and directory-form stars; this rule needs only the narrow case, because it decides ONE question:
# does this command write a ledger file. Missed before: `cd ledger && sed -i … 2026.csv`,
# `sed -i … ledger/*.csv`, and `ledger//2026.csv`.
_CD_LEDGER_RX = re.compile(r"(?:^|[;&|]|\bcd\s)\s*cd\s+\.?/?ledger\b", re.IGNORECASE)
# A commit MESSAGE is prose, not code. `git commit -m 'restore ledger/2026.csv from backup'` was
# refused as "this command WRITES a ledger file and then commits in the same call" -- for a command
# that writes nothing, with a remedy ("run it as two calls") that cannot be followed when there is
# only one. Worse, `git restore ledger/2026.csv && git commit -m 'undo bad edit'` -- the remedy this
# gate itself advertises -- was blocked by the same accident.
# The unquoted alternative was dropped for one round: `-m <(sed -i … ledger/2026.csv)` had its
# WRITE VERB stripped away and left the path behind, so the write-and-commit rule found nothing to
# object to -- bash performs process substitution in an unquoted argument, so the `sed` really ran.
# It is back, because `_SHELL_CODE_IN_TEXT_RX` now knows `[<>]\(` and the token no longer strips.
# Without it, `git commit -m restore -- ledger/2026.csv` was refused: a ONE-WORD message that
# happens to be a git write verb, conjoined with the path.
# ...and the FLAG NAMES are case-SENSITIVE inside an otherwise case-insensitive pattern, because a
# flag letter's case is what tells two different flags apart. Measured while widening the
# interpreter-option rule below: `-b` matched `-B`, so `python -B tools/ledger_add.py && git commit`
# had the span `-B tools/ledger_add.py` removed as if it were a commit MESSAGE -- the decoy
# validator disappeared from the view before anything judged it. Nothing here needs the folding:
# these are git's own flags, and git does not accept them in another case.
#
# WHAT A QUOTED SPAN IS, written once. Two readers of this file need it -- the message payload
# here and the syntax view further down -- and the second was written while the first already
# carried the same alternation inline, which is a second place for one rule to rot. It is NOT
# borrowed from `_compat`: that module's copy is a private of its own word splitter, and a gate
# reaching into a sibling's internals is the defect `BUG-0107` is about.
_QUOTED_SPAN = r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'"
_QUOTED_SPAN_RX = re.compile(_QUOTED_SPAN)
_MESSAGE_ARG_RX = re.compile(
    r"(?-i:(?:-m|--message|--body|-b|--notes|--squash-message))(?:=|\s+)"
    r"(" + _QUOTED_SPAN + r"|[^\s;|&]+)", re.IGNORECASE)


# `$(…)`, backticks and `${…}` inside a message payload are EXECUTED by the shell. Stripping the
# payload as prose therefore hid a real write: `git commit -m "$(sed -i s/119/150/
# ledger/2026.csv)"` broke the ledger and committed it in one call, and the gate allowed it —
# verified end to end, with the bad row in HEAD. A payload is prose only if it is inert.
# ...and even a quoted payload is code when the shell will expand it. `<(…)`/`>(…)` are process
# substitution, `$(…)`/backticks command substitution, `${…}`/`$NAME` parameter expansion -- the
# last one cannot write by itself but can carry a path the surrounding logic then misses.
_SHELL_CODE_IN_TEXT_RX = re.compile(r"\$\(|`|\$\{|\$[A-Za-z_]|[<>]\(")


def _payload_is_inert(payload):
    """Can the shell execute anything inside this `-m` argument?

    A SINGLE-quoted payload is inert by construction: bash performs no expansion at all inside
    single quotes -- no `$(…)`, no backticks, no `${…}`, no `$NAME`. Testing it for code shapes
    anyway refused three commit messages that write nothing (`-m 'rm ledger/2026.csv from $HOME
    was wrong'`), which is the false-positive class this whole prose filter exists to remove.
    Double-quoted and unquoted payloads get the full check.
    """
    if payload.startswith("'") and payload.endswith("'"):
        return True
    return not _SHELL_CODE_IN_TEXT_RX.search(payload)


def _without_messages(command):
    """The command with INERT `-m <text>` payloads removed — quoted PATHS and code both survive."""
    return _MESSAGE_ARG_RX.sub(
        lambda m: " " if _payload_is_inert(m.group(1)) else m.group(0),
        command or "")


# `cp ledger/2026.csv /tmp/backup.csv` COPIES OUT: the ledger is the source, the destination is
# elsewhere, and nothing in the ledger changes. Only the two-argument form is recognised, because
# that is where source and destination are unambiguous.
#
# `mv` is NOT in this list, and that is the whole distinction: a move DELETES the source. `mv
# ledger/2026.csv /tmp/ && git commit` took a year's books out of the repo and committed the
# deletion, after which `judge()` found no 2026.csv and every later check was clean -- the data
# was gone and the gate was satisfied. A copy-out is a read; a move-out is a delete.
_COPY_OUT_RX = re.compile(
    r"\b(?:cp|copy-item)\b(?:\s+-{1,2}[\w-]+)*\s+"
    r"(?P<src>[^\s;|&]+)\s+(?P<dst>[^\s;|&]+)", re.IGNORECASE)

# READ-ONLY ALLOWLIST, not a write denylist. Four review rounds in a row, the finding was "another
# spelling the denylist did not have" -- `curl -o`, `wget -O`, `tar -C`, `unzip -d`, `split`,
# `awk -i inplace`, `sort -o`, all writing into `ledger/` and committing in one call. The PATH half
# of this rule stopped generating those the moment it was rewritten from "the shapes I thought of"
# to "what a ledger path IS"; the verb half had kept the old shape. `gate_write_scope` in this same
# kit already decides this the durable way, and this is that decision, scoped to one question:
# a segment that touches a ledger path is a WRITE unless its verb is known to only read.
_READ_ONLY_VERBS = frozenset((
    "cat", "type", "bat", "head", "tail", "less", "more", "wc", "nl", "od", "xxd", "strings",
    "grep", "egrep", "fgrep", "rg", "ag", "ack", "diff", "cmp", "comm", "file", "stat",
    "ls", "dir", "tree", "basename", "dirname", "realpath", "readlink", "pwd", "du", "df",
    "uniq", "cut", "tr", "jq", "yq", "test", "echo", "printf", "base64", "column",
    # conditionally read-only -- `_LEDGER_WRITE_FLAGS` is what actually decides for these
    "sed", "awk", "gawk", "mawk", "sort", "find", "tee",
    "md5sum", "sha1sum", "sha256sum", "cksum", "cd", "pushd", "popd", "true", "false",
    # PowerShell
    "get-content", "get-childitem", "select-string", "test-path", "get-item", "resolve-path",
    "get-filehash", "compare-object", "measure-object", "select-object", "set-location",
    "import-csv", "gc", "sls", "gci", "gi", "ls-object",
))
# ...the flags that turn a reading verb into a writing one (same table `gate_write_scope` learned
# the hard way: `"--in-place".startswith("-i")` is False, so a short-flag test alone missed it)
_LEDGER_WRITE_FLAGS = {
    "sed": ("-i", "--in-place"),
    "awk": ("-i", "--in-place"),
    "gawk": ("-i", "--in-place"),
    "mawk": ("-i", "--in-place"),
    "sort": ("-o", "--output"),
    "find": ("-delete", "-exec", "-execdir", "-fprint", "-fls", "-ok"),
    "tee": ("",),          # tee always writes its argument
}
# git subcommands that cannot modify a working-tree FILE. `checkout`, `restore`, `stash`, `mv`,
# `rm`, `clean` and `apply` are absent because each of them can -- and so are `merge`, `rebase`,
# `revert`, `cherry-pick` and `am`, which a first cut listed here on the false reasoning that they
# "cannot modify a ledger file". They write working-tree files by definition. Nothing needed them
# in this set: whether those operations are permitted at all is `_BLOCKED_GIT_SUBCOMMANDS`'s
# question.
_READ_ONLY_GIT = frozenset((
    "add", "status", "diff", "log", "show", "commit", "push", "fetch", "remote", "branch",
    "config", "rev-parse", "ls-files", "blame", "describe", "tag", "bundle", "format-patch",
    "archive", "send-email", "shortlog", "grep", "cat-file",
))
# A PIPELINE IS ONE UNIT. `|` is deliberately NOT a separator: `find ledger -name 2026.csv |
# xargs sed -i …` puts the path in one stage and the write verb in the next, and judging the
# stages apart called both halves harmless — segment one had a read verb, segment two had no
# ledger path. That is the structural cost of per-segment analysis, and the pipe is the construct
# that pays it. `gate_write_scope` in this kit made the same discovery and treats a pipeline as
# one unit for exactly this reason.
_SEGMENT_SPLIT_RX = re.compile(r"&&|\|\||[;&\n]")
# A substitution OPENS a new command, so it has to open a new SEGMENT. It is part of the CUT
# below rather than a rewrite of the text, because a rewrite has to put its separator somewhere,
# and the only place available was inside the quoted span the substitution stands in -- which is
# what made a quote-aware cut impossible for a round (`BUG-0160`'s `limits`).
_SUBSTITUTION_OPEN_RX = re.compile(r"\$\(|<\(|>\(|`")
# ...and the two together are what ENDS a command context, in one pattern, because the cut below
# has to find them in one pass over one view.
_COMMAND_CUT_RX = re.compile(_SEGMENT_SPLIT_RX.pattern + "|" + _SUBSTITUTION_OPEN_RX.pattern)
# A PIPE cuts a segment into stages, and it is its own pattern for the same reason: the stage cut
# is the same operation on the same view, with a different separator.
_STAGE_CUT_RX = re.compile(r"\|")
# THE CHARACTER AN INERT QUOTED SPAN IS FILLED WITH. It has to be a character that is neither a
# separator nor a word end nor whitespace, so that filling can only ever REMOVE syntax from the
# view and never invent a boundary; and it has to be legal inside a path, so a redirect target
# found in the view has the same extent as the one in the text.
_INERT_FILLER = "x"


def _syntax_view(text):
    """`text` with the CONTENT of every inert quoted span filled — same length, so offsets hold.

    WHICH CHARACTERS OF A COMMAND LINE ARE SYNTAX, asked once for every reader that cuts. A shell
    reads `;`, `|`, `&` and a newline as separators and `>` as a redirection only where they stand
    as CODE; inside a quoted span the same characters are data the program receives. The cutters
    of this gate used the plain text and therefore cut inside argument prose: `grep "a; b"
    ledger/2026.csv && git commit` was rc 2 because the half after the quoted semicolon had the
    ledger path and a verb (`b"`) no read-only table knows, and `grep -n "row > ledger/2026.csv"
    ledger/2026.csv && git commit` was rc 2 because the quoted `>` was read as a redirection into
    the books (`BUG-0160`, `BUG-0156`).

    A SUBSTITUTION OPENING IS NEVER DATA, and that single exception is what the whole view turns
    on. `"$(cp evil.py scripts/)"` is a quoted span whose content the shell RUNS, and the cut at
    its opening is the only reason that line is refused (`BUG-0065`). So the fill skips exactly
    the characters of a `_SUBSTITUTION_OPEN_RX` match and covers everything else in the span.

    IT IS NOT `_payload_is_inert`'S QUESTION, although that is the same distinction one level up,
    and the difference is measured rather than stylistic: this view is taken of a READING, where
    `_as_one_word` has put quote marks around values the shell BUILT. A span-wide inertness test
    short-circuits on a single quote, so the synthesised `'$(tar'` of `echo "$(tar -xf evil.tar -C
    scripts/)"` counted as inert, the opening was filled, and the line went from rc 2 to rc 0 in
    the first cut of this function -- `BUG-0065` reopened by the repair of `BUG-0160`. Skipping the
    opening character-wise cannot have that failure mode, because it never asks a question about
    the span as a whole
    (`tools/test_hooks_v2.py::test_a_quoted_separator_is_argument_text_and_a_substitution_still_cuts`).

    LENGTH-PRESERVING is the whole interface: every caller finds its separators HERE and then cuts
    the ORIGINAL text at those offsets, so no reader downstream ever sees the filler.
    """
    view = list(text)
    for match in _QUOTED_SPAN_RX.finditer(text):
        kept = set()
        for opening in _SUBSTITUTION_OPEN_RX.finditer(match.group(0)):
            kept.update(range(match.start() + opening.start(), match.start() + opening.end()))
        for index in range(match.start() + 1, match.end() - 1):
            if index not in kept:
                view[index] = _INERT_FILLER
    return "".join(view)


def _cut(text, pattern):
    """`text` cut at every `pattern` match that stands in its SYNTAX view — the pieces, in order."""
    view = _syntax_view(text)
    pieces, last = [], 0
    for match in pattern.finditer(view):
        pieces.append(text[last:match.start()])
        last = match.end()
    pieces.append(text[last:])
    return pieces
# NORMALISE BEFORE SPLITTING, rather than adding a separator case per spelling. Four ordinary
# forms tore the pipeline unit apart again and left the path in one segment with the write verb in
# the next: a backslash-newline continuation (which is simply how a long command is FORMATTED), a
# newline after the pipe, a newline inside the first stage, and `|&`. Each is the same pipeline
# written differently, so the answer is to make them one shape first — the same move that ended
# the path and verb enumerations two rounds ago. The continuation AND the break spelling both come
# from `_compat.join_line_continuations` — this hook's own copy of the continuation joined with a
# SPACE, so a continuation INSIDE a token (`led\<newline>ger/2026.csv`) split the very path the
# rule is about, and its own copy of the break rule was a second place for the same rule to rot.
# What that preparation buys this gate: a CARRIAGE RETURN is a break here too, unread it left a
# vouched run and the write behind it in ONE stage — `python scripts/ledger_add.py --validate
# ledger/2026.csv<CR>Set-Content -Path ledger/2026.csv …<CR>git commit -am poisoned` was rc 0 from
# this gate, rc 0 from powershell, and poisoned books in git HEAD, one gated call, one session. It
# arrives spelled `\n` rather than as a case in `_SEGMENT_SPLIT_RX`, so the two rules below that put
# a newline back together (the pipe and the flag continuation) go on seeing it
# (`tools/test_hooks_v2.py::test_a_carriage_return_ends_a_stage_the_way_powershell_ends_a_statement`,
# `tools/test_hooks_v2.py::test_a_carriage_return_does_not_tear_a_command_off_its_own_flag`).
_PIPE_AMP_RX = re.compile(r"\|&")
_NEWLINE_AROUND_PIPE_RX = re.compile(r"\s*\n\s*\|\s*|\s*\|\s*\n\s*")


def _normalise_pipeline(text):
    """One shape for every way a shell can spell the same pipeline.

    A HERE-DOCUMENT BODY IS PROSE WHEN THE PROGRAM THAT RECEIVES IT ONLY READS, and that question
    is this gate's own (`_verb_only_reads`) because no general one exists. Measured in pilot 4
    (`P4-12`): the office manager's `git commit -m "$(cat <<'EOF' … EOF)"` was refused because a
    line of its MESSAGE read "bookkeeper booked ledger entry L2025-0001" -- a ledger path plus a
    word this reader took for a verb. `cat` only reads, so that body is prose and goes.

    WHAT THE BORROWED RULE COST, and why it is not borrowed any more: `_compat.literal_heredoc_free`
    asks what the SHELL EXPANDS, so it removed the body of `python <<'EOF'` too -- and a body
    handed to an INTERPRETER is a program that can rewrite the ledger's own judge. Measured rc 0 on
    a broken ledger, with the validator replaced from inside such a body (`BUG-0149`). `python` is
    not a verb this gate calls read-only, so its body now stays in the view and every rule below
    reads it
    (`tools/test_hooks_v2.py::test_a_heredoc_body_an_interpreter_executes_is_not_prose_here`).
    """
    text = _compat.join_line_continuations(_compat.heredoc_free(
        text, lambda literal, fed, head: fed or not _verb_only_reads(head)))
    text = _PIPE_AMP_RX.sub("|", text)
    text = _NEWLINE_AROUND_PIPE_RX.sub(" | ", text)
    # ...and a newline whose next line begins with a FLAG continues the same command. Splitting
    # there put `find ledger` in one segment and `-name 2026.csv | xargs sed -i` in the next,
    # so the path and the write verb were judged apart again.
    return _NEWLINE_BEFORE_FLAG_RX.sub(" ", text)


_NEWLINE_BEFORE_FLAG_RX = re.compile(r"\s*\n\s+(?=-)")
# A redirection and the word it opens. `>|` is bash's CLOBBER OVERRIDE and redirects exactly like
# `>`; without the `\|?` the target after it was invisible here, and the docstring below said
# EVERY. It cost nothing to measure and nothing to fix, so it is fixed rather than excused
# (`tools/test_hooks_v2.py::test_every_redirect_target_of_a_segment_is_read`). `>&` keeps no target
# on purpose: `2>&1` duplicates a descriptor and writes no file, and `&` stays out of the target
# class for that reason.
_REDIRECT_INTO_RX = re.compile(r">>?\|?\s*[\"']?(?P<target>[^\s\"';|&]+)")


def _as_one_word(word, reading):
    """`reading`, spelled so a word boundary stands only where the shell puts one.

    QUOTE REMOVAL MOVES BOUNDARIES, and that is the price of resolving it. Every character
    `_WORD_END` reads as the end of a word is a legal FILENAME character on Windows and on POSIX,
    and inside a quoted span it is data: `python "scripts/ledger_add.py evil.py" ledger/2026.csv`
    is two argv words, and the sibling in the first of them ran and rewrote the ledger while this
    gate vouched for it — exit 0 through the registered chain, filesystem witness on the sibling
    (`tools/test_hooks_v2.py::test_a_quoted_word_end_character_does_not_end_the_word`). `(`, `>`,
    `<`, `'` and a plain space each spell the same hole.

    So a value the shell BUILT — quote marks removed, or a backslash consumed — keeps a quote mark
    around it whenever it carries such a character. A value the text spells literally is passed
    through untouched: there the characters ARE the shell's own separators, and quoting them here
    would hide a real segment break.

    WHAT THIS BUYS IS THE ANCHORS THAT VOUCH, and it does it at the START of the word rather than
    at its end. `_WORD_END` goes on treating the quoted metacharacter as a boundary -- the quote
    mark this wrapper adds is itself in `_WORD_END_CHARS`, so the reader still stops there. What
    changes is that the word now BEGINS with a quote mark, and the two anchors that hand out an
    exemption leave no room for one: `_canonical_run` ends on `\\s+(?:\\./)?<directory><script>`
    and `_CD_SCRIPTS_RX` on `cd\\s+\\.?/?scripts`, both with the path pressed straight against the
    whitespace. A word the shell BUILT therefore cannot be read as the vouched path, whatever it
    carries inside it.

    SO DO NOT "TIDY UP" AN OPTIONAL QUOTE INTO EITHER ANCHOR. `_PROTECTED_DIR_RX`, which reads the
    same wrapped words, does carry a `[\"']?` in that position -- it is a REFUSING reader, where
    accepting a quote can only add refusals. Copying that into a vouching anchor reopens the hole
    this function closes, and both directions are pinned rather than left to this paragraph
    (`tools/test_hooks_v2.py::test_a_quoted_word_end_character_does_not_end_the_word`,
    `tools/test_hooks_v2.py::test_a_quoted_directory_name_does_not_forgive_the_bare_validator`).

    THE CUTS ARE QUOTE-AWARE NOW, and the quote mark this wrapper adds is what makes that safe to
    say here: both cuts go through `_syntax_view`, so a `;` or a `|` inside an INERT quoted span is
    argument text (`--summary "reversed; see scripts/ledger_add.py"` was rc 2 and is rc 0,
    `BUG-0160`). What used to make a quote-aware cut impossible was that the substitution opening
    was REWRITTEN into a `;` inside what is then a quoted span (`"$(cp evil.py scripts/)"`); it is
    a member of `_COMMAND_CUT_RX` instead, and a span carrying one is not inert, so `BUG-0065`
    stays closed. A word this wrapper quotes is therefore no longer cut apart either -- one argv
    word is one word -- and it still cannot be read as a vouched path, because the anchors leave no
    room for the quote mark it now begins with.

    The mark is one the value does not itself contain, so it cannot be mistaken for the value. When
    the value contains both, the wrapper repeats a character already inside it, which can only make
    a reader stop EARLIER than the word ends — refusals, never permissions.
    """
    if not (getattr(word, "spliced", False) or reading != str(word)):
        return reading
    if not _A_WORD_END_CHAR_RX.search(reading):
        return reading
    return "'%s'" % reading if "'" not in reading else '"%s"' % reading


def _readings_of(command):
    """`command` as each shell this kit gates would read it — one entry per reading.

    THE VIEW THE PATH READERS WORK ON, and the only place quoting is resolved: `_canonical_run`
    and `_DECOY_VALIDATOR_RX` both decide what a PATH TOKEN is, and a shell removes quote marks
    character by character while this gate did not. Measured through the registered chain:
    `python scripts/ledger_add.py'.bak' ledger/2026.csv && git commit` was exit 0 — the sibling
    was vouched for as the canonical validator because `.py` was followed by a quote, which no
    character class of a path can call a continuation. It cuts both ways, which is why one view
    fixes both: `python tools/ledger_add".py"` escaped the decoy rule, and the quoted CANONICAL
    path was refused as a stranger
    (`tools/test_hooks_v2.py::test_quoting_inside_a_word_does_not_change_which_file_it_names`).

    A LIST, one entry per reading, because the two shells this kit gates disagree about the
    backslash (`_compat.shell_readings`) and each caller judges each reading SEPARATELY. Joining
    them into one text and judging that was a refusal-REMOVING construction: `_CD_SCRIPTS_RX`
    matched in the POSIX reading of `echo start ; c\\d scripts ; python ledger_add.py --validate
    ledger/2026.csv ; git commit` and the exemption it granted covered the PowerShell reading too,
    where no `cd` ever happened and the bare name is a validator of the attacker's own — exit 0
    through the registered chain, and PowerShell's `;` runs the rest whatever the failed `cd` did
    (`tools/test_hooks_v2.py::test_a_second_shell_reading_can_only_add_refusals`).

    Backslashes become `/` here rather than in each caller: it is a PATH normalisation and it must
    happen AFTER the readings are taken, since one of the two readings is the one that consumes the
    backslash.

    Quote marks only. Redirection is NOT resolved here: `_compat.git_argument_text` drops the word
    after a `>` (it answers a different question — which words reach the program), and reading the
    ledger path out of a redirect target is exactly what `_redirect_targets` must still do.
    """
    words = _compat.shell_words(_normalise_pipeline(command or ""),
                                lambda chunk: re.split(r"(\s+)", chunk))
    # EVERY reading, and that is a correction: this took the FIRST and the LAST, which was the
    # whole set while a word had at most two. `_compat` derives one reading per escape character
    # now (`BUG-0158`), so a third one appeared in the middle -- and `(0, -1)` would have skipped
    # exactly the POSIX reading that several measured refusals rest on. A pair was never the rule;
    # "each reading on its own" was, and this is that sentence
    # (`tools/test_hooks_v2.py::test_a_second_shell_reading_can_only_add_refusals`).
    width = max((len(_compat.shell_readings(word)) for word in words), default=1)
    readings = []
    for index in range(width):
        joined = "".join(
            _as_one_word(word, _compat.shell_readings(word)[min(index, len(
                _compat.shell_readings(word)) - 1)])
            for word in words).replace("\\", "/")
        if joined not in readings:
            readings.append(joined)
    return readings


def _redirect_targets(segment):
    """EVERY file this segment redirects into, not just the first one.

    A command may carry more than one redirection and a shell opens (and truncates) all of them:
    `cat ledger/2026.csv > /tmp/a > ledger/2026.csv && git commit` emptied the books and committed
    them, exit 0, because both readers asked `_REDIRECT_INTO_RX.search(...)` and stopped at the
    harmless target. Sequence, not existence, is what a single `search` answers
    (`tools/test_hooks_v2.py::test_every_redirect_target_of_a_segment_is_read`).

    A REDIRECTION IS A `>` THE SHELL EXECUTES, so the operator is looked for in the SYNTAX VIEW
    and the target is then read out of the text at the same offsets (`_syntax_view` keeps the
    length for exactly this). A `>` inside inert argument prose is a character the program
    receives: `grep -n "row > ledger/2026.csv" ledger/2026.csv && git commit` was refused as a
    redirection into the books while it wrote nothing (`BUG-0156` --
    `tools/test_hooks_v2.py::test_a_quoted_redirection_sign_in_argument_prose_is_not_a_redirect`).
    A target that is itself quoted is still found: the filler is a legal path character, so the
    match in the view has the extent the word has in the text.
    """
    view = _syntax_view(segment)
    return [segment[match.start("target"):match.end("target")]
            for match in _REDIRECT_INTO_RX.finditer(view)]
# WHICH INTERPRETER OPTIONS MAY STAND BETWEEN THE INTERPRETER AND ITS SCRIPT, as a property rather
# than as the letters somebody had in mind: any option word that carries no `c`/`e`/`m` in it. Those
# three are the ones that make the interpreter read its program from the COMMAND LINE instead of the
# script, which is exactly what these patterns must never step over -- everything else (`-B`, `-E`,
# `-S`, `-u`, `-I`, `-P`, a cluster like `-Bu`) only changes how the named script is run. The old
# class `[EOSuvWx]` was a list, and `-B` was measured missing from it: `python -B scripts/harness.py
# --summary '…ledger_add.py'` stayed refused while the same line without `-B` passed. Case-sensitive
# on purpose (`(?-i:…)`) although the surrounding pattern is not: `-E` is an option, `-e` is a
# payload flag, and folding them together would give up the one distinction this makes.
_INTERPRETER_OPTIONS = r"(?:\s+(?-i:-(?![^\s]*[cem])[^\s]*))*"


# WHAT MAY STAND IN FRONT OF A VOUCHED RUN, as a property of the CUT rather than as a list: a stage
# keeps the whitespace the split left in front of it, and a `(` at the start of a stage is the
# subshell spelling of the same command. A LINE BREAK is not in it -- it is what ENDS a stage
# (`_SEGMENT_SPLIT_RX`, plus the carriage return `_normalise_pipeline` rewrites into one), so no
# caller can hand this pattern a stage that begins with one. Accepting it anyway is not free: the
# acceptance is what a property test then pins, and pinning `\r` as a legal opener is pinning the
# very reading of it that let a PowerShell statement separator pass for argument text. The quantifier
# is `*` and not `?` because openings COMBINE -- `((python …))` and an indented stage are the same
# run (`tools/test_hooks_v2.py::test_only_a_group_opening_stands_in_front_of_a_vouched_run`,
# `tools/test_hooks_v2.py::test_stage_openings_stack_in_front_of_a_vouched_run`).
_STAGE_OPENING = r"(?:[^\S\r\n]|\()*"


# WHERE AN INLINE PAYLOAD CAN STAND IS A POSITION, NOT A SPELLING, and both patterns below used to
# say it twice: each ended in a negative lookahead for a whitespace-preceded `-c`/`-e`/`-m` word
# that scanned everything up to the next newline. An interpreter reads its program from the command
# line only while it is still reading OPTIONS, i.e. before the script argument -- and there
# `_INTERPRETER_OPTIONS` already refuses those letters. After the script name the same letters are
# an argument the script's own parser owns. So the tail added nothing IN FRONT of the script that
# the option class does not already refuse
# (`tools/test_hooks_v2.py::test_a_real_interpreter_payload_before_the_script_is_still_refused`),
# while re-refusing the very shape the exemption exists for: `BUG-0063` measured
# `--summary "fixed the -m flag handling in scripts/ledger_add.py"` back to refused
# (`tools/test_hooks_v2.py::test_prose_about_the_ledger_in_a_body_or_an_argument_is_not_a_write`).
# BEHIND the script it did catch one real direction, by accident and only for those three letters:
# a pipeline NEIGHBOUR of the validator, whose exemption was still segment-wide. That direction is
# now carried where it belongs, by `_stages_beside_the_vouched_runs`, for every neighbour and not
# only the ones that spell a payload letter.
def _canonical_run(script, directory="scripts/"):
    """`python [interpreter options] <directory><script>` — the interpreter running one of OURS.

    ONE construction for all three exemptions, because the defect the tail carried was in both of
    the first two: a second copy of a pattern is a second place for the next correction to miss.
    `directory` is what the third one varies — from INSIDE `scripts/` the guarded program is the
    bare name — and nothing else about "the interpreter runs this file" may vary with it.

    A VOUCHED RUN IS THE BEGINNING OF THE STAGE IT VOUCHES FOR. Every reader of these patterns is
    handed ONE pipeline stage (`_stages_beside_the_vouched_runs`, `_only_the_bare_validator`), and
    by then `;`, `&` and every line break are gone with `_SEGMENT_SPLIT_RX` -- a carriage return
    among them, since `_normalise_pipeline` has made it one -- and `|` with the stage split.
    The prefix used to be the class `[;&|(]`, which therefore carried only its `(` -- and a `(` may
    stand ANYWHERE in a stage, quoted argument prose included, which is exactly the text these
    exemptions exist to allow. So the writing stage could BE the vouched one instead of standing
    beside it: `cd scripts && tee ledger_add.py '(python ledger_add.py --validate ../ledger/2026.csv)'`
    left `_stages_beside_the_vouched_runs` with an empty list and was rc 0 through the registered
    chain, truncating the ledger's own judge, after which the refused commit went through. Measured
    against `tee`, `rm`, `sed -i` and `curl -o`, at the judge and at the ledger, on all three
    vouched runs. So the anchor is the stage START: a run spelled anywhere else in the stage is
    that stage's own argument text, and argument text does not vouch.

    LEADING `(` STAYS, and it is the only thing besides the whitespace a cut can leave there that
    may (`_STAGE_OPENING`): at the START of a stage a paren is the subshell/group spelling of the
    same command, and `(python scripts/…)` is a run this gate vouches for as much as the bare
    spelling. Both ends are measured rather than argued -- which characters may open a vouched
    stage, and that no other character in that position vouches
    (`tools/test_hooks_v2.py::test_a_vouched_run_is_the_start_of_the_stage_it_frees`,
    `tools/test_hooks_v2.py::test_only_a_group_opening_stands_in_front_of_a_vouched_run`).

    THE NAME ENDS WHERE THE PATH TOKEN ENDS, and `\\b` does not say that: a word boundary is
    satisfied by the `.` of `.bak`, so `python scripts/ledger_add.py.bak ledger/2026.csv && git
    commit` and `scripts/harness.py-evil` were vouched for as the canonical files and ran with
    their prose unread (measured exit 0, both, before TSK-0083's second round). A sibling in the
    same directory is a program nobody guards, exactly as a copy under another path is
    (`tools/test_hooks_v2.py::test_quoting_inside_a_word_does_not_change_which_file_it_names`).
    """
    return re.compile(
        r"^" + _STAGE_OPENING + r"(?:python[0-9.]*|py)\b" + _INTERPRETER_OPTIONS +
        r"\s+(?:\./)?" + re.escape(directory) + re.escape(script) + _WORD_END, re.IGNORECASE)


# `python scripts/ledger_add.py …` is the VALIDATED write path: it refuses bad data before it
# writes, so a row it produces is valid by construction. Every other interpreter invocation --
# another script, or any inline `-c`/`-e`/`-m` payload -- is a write this gate cannot vouch for.
# ...and the exemption is anchored to the CANONICAL path. Matching `\S*ledger_add\.py` granted it
# by BASENAME, so `python tools/ledger_add.py && git commit` and even
# `python /tmp/evil/ledger_add.py ledger/2026.csv && git commit` were waved through -- and
# `guard_harness_selfmod` protects exactly `scripts/ledger_add.py`, so writing the decoy was
# allowed. The exemption now names the same file the protection does.
_LEDGER_ADD_RUN_RX = _canonical_run("ledger_add.py")
# ...and the KERNEL'S OWN ENTRY POINT, which is not a shell write either. It carries an envelope,
# a summary and a reason as ARGUMENTS -- prose that names the ledger and its validator whenever the
# work did (measured, pilot 4 `P4-12`: `submit-result --summary "… via ledger_add.py …"` was refused
# as a write to the judge, and the office manager reported a gate blocking a commit "on the word
# ledger"). What it can reach is decided by the kernel and its own gates, not by this one: no
# command of it names `ledger/*.csv`, and the one route it has to `scripts/ledger_add.py` is an
# installer run (`update-kit`/`set-preset`, each on a user-minted approval), which is exactly how
# this gate's own remedy says the validator legitimately changes. A REDIRECT is judged before this
# exemption is reached, so the entry point with its output sent into `ledger/2026.csv` is still a
# write.
_ENTRY_POINT_RUN_RX = _canonical_run("harness.py")
# ...and the SAME validator addressed the way it is addressed from inside its own directory, which
# is the only place a bare `ledger_add.py` names the guarded file.
_BARE_VALIDATOR_RUN_RX = _canonical_run("ledger_add.py", directory="")


def _only_the_bare_validator(stage):
    """Does this pipeline stage RUN `ledger_add.py` by its bare name, and name it no other way?

    A RUN, not a mention, and that distinction is the whole exemption. Asking only whether the name
    appears without a directory part freed every stage that carries the bare name as a TARGET:
    `cd scripts && cp ../evil.py ledger_add.py` replaced the ledger's judge with a stub and was
    exit 0 through the registered chain, after which the same refused commit went through — the
    heaviest chain this gate knows. `rm`, `mv`, `curl -o`, `tee`, `sed -i` and `install` reached it
    the same way, and so did a LEDGER write standing beside the bare name
    (`tools/test_hooks_v2.py::test_the_step_inside_forgives_a_run_and_not_a_target`).

    Both halves are needed, and the example that used to stand here for the first one was refuted
    by the caller: `python ledger_add.py && rm ledger_add.py` is never asked as one unit, because
    `&&` splits it into two segments long before this reader sees either. The half earns its place
    on a stage a split cannot separate -- `python ledger_add.py --validate ../ledger/2026.csv
    ../tools/ledger_add.py` runs the canonical file and hands a decoy to it in the same breath, and
    without the no-directory half the vouching covers the decoy too (measured rc 2, and rc 0 with
    that half removed). The no-directory half alone is the target defect above
    (`tools/test_hooks_v2.py::test_the_step_inside_asks_for_a_run_and_not_for_a_mention`,
    `tools/test_hooks_v2.py::test_a_validator_with_a_directory_part_loses_the_step_inside`).

    A LEADING `./` IS NOT A DIRECTORY PART -- `./x` and `x` name the same file from every working
    directory, and the run pattern accepts both. Without this the two halves disagreed and the
    `./` spelling of the remedy was refused while the run pattern vouched for it, which is a dead
    branch reading as a handled case. `../ledger_add.py` does NOT start with `./` and stays a
    different file.
    """
    names = [name[2:] if name.startswith("./") else name
             for name in _ANY_VALIDATOR_PATH_RX.findall(stage)]
    if not names or any("/" in name for name in names):
        return False
    return _BARE_VALIDATOR_RUN_RX.search(stage) is not None


def _stages_beside_the_vouched_runs(segment, inside_scripts):
    """The pipeline stages of `segment` that are NOT one of this kit's own guarded programs.

    PER STAGE, and that is a correction of an earlier cut rather than a refinement: the exemption
    was first written as `if _ENTRY_POINT_RUN_RX.search(segment): continue`, which threw away the
    whole segment as soon as the entry point appeared ANYWHERE in it -- so every other stage of the
    pipeline came free with it. Measured: `python scripts/harness.py doctor | tee
    scripts/ledger_add.py` was exit 2 before that exemption and exit 0 after it, and the same for
    `| tee .claude/ledger_state.json` and an `xargs cp` in the second stage. What the exemption is
    ABOUT is the prose an invocation carries in its own arguments, and that lives in ITS stage; a
    neighbouring stage is a different command and is judged like any other.

    ALL THREE VOUCHED RUNS ARE DROPPED HERE, and that is the whole reason this function exists as
    one place. Each exemption that arrived later repeated the segment-wide mistake one round after
    it had been corrected for the one before it: the canonical validator still read `if
    _LEDGER_ADD_RUN_RX.search(segment): continue`, and the bare name read `if inside_scripts and
    _only_the_bare_validator(segment): continue` at three call sites. A segment holds a WHOLE
    pipeline (`|` is deliberately not a separator in `_SEGMENT_SPLIT_RX`), so each time the
    neighbour rode along free -- `cd scripts && python ledger_add.py --validate ../ledger/2026.csv
    | tee ledger_add.py && git commit` truncated the ledger's own judge to zero bytes and then
    committed, exit 0 through the registered chain. The property that has to hold for a fourth
    exemption too is that vouching frees the STAGE it stands in and never its neighbours
    (`tools/test_hooks_v2.py::test_a_vouched_run_frees_its_own_stage_and_not_its_neighbours`).

    `inside_scripts` has no default on purpose: it is the caller's finding about the whole command
    (`_CD_SCRIPTS_RX`), and a caller that forgot to pass it would silently lose the remedy or
    silently widen the exemption -- the two failures this parameter is here to prevent.

    WHAT VOUCHING BUYS AND WHAT PAYS FOR IT: the words in a vouched stage stop being read as
    commands, so `--note "cp backup.py scripts/"` is prose here as it already was for the entry
    point. What keeps that from freeing an attacker's stage is where the run has to STAND: it is
    the stage's own opening word (`_canonical_run`), so a run spelled in the argument text of a
    stage that WRITES does not free it. A write into the validator from any OTHER stage is left
    in this list for the callers to judge
    (`tools/test_hooks_v2.py::test_prose_about_the_ledger_in_a_body_or_an_argument_is_not_a_write`,
    `tools/test_hooks_v2.py::test_the_same_constructs_still_refuse_a_real_write`,
    `tools/test_hooks_v2.py::test_a_vouched_run_frees_its_own_stage_and_not_its_neighbours`,
    `tools/test_hooks_v2.py::test_a_vouched_run_is_the_start_of_the_stage_it_frees`).

    AND WHAT IT DOES NOT BUY, written down rather than left to be discovered: inside a stage this
    list drops, a DECOY path is prose too. `python scripts/ledger_add.py --validate ledger/2026.csv
    tools/ledger_add.py` hands a second, unguarded validator to the canonical run in its own
    arguments and is rc 0 -- the segment has no stage left to judge. In a NEIGHBOURING stage the
    decoy survives only as long as that stage READS it (`… --help | cat
    tools/ledger_add.py`, rc 0). A neighbour that WRITES the decoy is refused whatever else the
    line does, because `_writes_protected` is asked of every shell line (`… --help | tee
    tools/ledger_add.py`, rc 2 with and without a commit), and a neighbour that RUNS it is now
    refused whatever else the line does as well: `uses_an_unguarded_validator` is a question of
    its own and `handle_pre_tool_use` puts it to every shell call. It used to be reachable only
    under a `blocked_op`, which is what made `… --help | python tools/ledger_add.py` rc 0 and
    rc 2 only with `&& git commit` behind it (`BUG-0159` --
    `tools/test_hooks_v2.py::test_an_unguarded_validator_is_refused_without_a_blocked_operation`).
    `_only_the_bare_validator` is stricter for its
    OWN exemption -- every validator mention on that stage must be bare
    (`tools/test_hooks_v2.py::test_a_validator_with_a_directory_part_loses_the_step_inside`) -- and
    the other two runs have no such half. Announced price of `H62` while the decoy question had
    two answers in one function; the second, unconditioned one is gone (`BUG-0154`).
    """
    return [stage for stage in _cut(segment, _STAGE_CUT_RX)
            if stage.strip() and not (_ENTRY_POINT_RUN_RX.search(stage)
                                      or _LEDGER_ADD_RUN_RX.search(stage)
                                      or (inside_scripts and _only_the_bare_validator(stage)))]


def _verb_of(segment):
    """The command word of a segment, lowercased and stripped of its path."""
    for token in segment.split():
        cleaned = token.strip("\"'")
        if cleaned.startswith("-"):
            continue
        # `FOO=1 cat x` -- an env-var PREFIX is not the verb. The first cut wrote
        # `"=" in cleaned.split("/")[0][:0]`, and `[:0]` is always the empty string, so the branch
        # could never be true: dead code that read as a handled case.
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", cleaned):
            continue
        # ...and the wrappers that put the real verb one token later
        base = os.path.basename(cleaned.replace("\\", "/")).lower().removesuffix(".exe")
        if base in ("env", "nohup", "command", "time", "stdbuf", "nice"):
            continue
        return base
    return ""


def _verb_only_reads(segment):
    tokens = segment.split()
    verb = _verb_of(segment)
    if verb == "git":
        following = [t for t in tokens[1:] if not t.startswith("-")]
        return bool(following) and following[0].lower() in _READ_ONLY_GIT
    if verb not in _READ_ONLY_VERBS:
        return False
    writers = _LEDGER_WRITE_FLAGS.get(verb)
    if not writers:
        return True
    for flag in writers:
        if flag == "":
            return False
        for token in tokens:
            low = token.lower()
            if low == flag or low.startswith(flag + "="):
                return False
            if (len(flag) == 2 and flag.startswith("-") and low.startswith("-")
                    and not low.startswith("--") and flag[1] in low[1:]):
                return False
    return True


def _writes_protected(command):
    """Does this command WRITE the validator or the state file (rather than read or run them)?

    ANY reading refuses, and each reading is judged on its own (`_readings_of`).
    """
    return any(_a_reading_writes_protected(reading) for reading in _readings_of(command))


def _segments_of(text):
    """(segments, inside_scripts) — the one preparation both decisions below start from.

    The step into `scripts/` is asked of the SEGMENTS and not of the whole text, because
    `_CD_SCRIPTS_RX` anchors on a separator and a cut piece begins exactly where one stood: that
    is what keeps `$(cd scripts && …)` finding the step now that the cut no longer rewrites the
    substitution opening into a `;`.
    """
    segments = _cut(text, _COMMAND_CUT_RX)
    return segments, any(_CD_SCRIPTS_RX.search(segment) for segment in segments)


def _a_reading_writes_protected(reading):
    # ...and `cd scripts && python ledger_add.py --validate …` runs the CANONICAL validator from
    # inside its own directory, which is the sanctioned way out of a block. Which STAGE that buys
    # is `_stages_beside_the_vouched_runs`'s question, not a `continue` here.
    segments, inside_scripts = _segments_of(reading)
    for segment in segments:
        segment = segment.strip()
        if not (_PROTECTED_RX.search(segment) or _PROTECTED_DIR_RX.search(segment)):
            continue
        if any(_PROTECTED_RX.search(target) or _PROTECTED_DIR_RX.search(target)
               for target in _redirect_targets(segment)):
            return True
        # each of this kit's own guarded programs is not a shell write, so ITS stage is dropped --
        # and only its own: every other stage of the pipeline is judged below.
        stages = _stages_beside_the_vouched_runs(segment, inside_scripts)
        if not stages or all(_verb_only_reads(stage) for stage in stages):
            continue
        copy = _COPY_OUT_RX.search(segment)
        if (copy and _PROTECTED_RX.search(copy.group("src"))
                and not _PROTECTED_RX.search(copy.group("dst"))):
            continue          # copying the validator OUT is a read (round-8 NIT-3)
        return True
    return False


def _writes_ledger(command):
    """Does this command write a canonical ledger file?

    PER SEGMENT, so the verb that matters is the one in the same breath as the path -- `grep -r
    ledger . > /tmp/hits && git commit` reads, and judging the whole command at once called it a
    write because `>` appeared somewhere in it.

    Slashes are collapsed first (`ledger//2026.csv` is the same path) and the working-directory
    form is handled separately, because `cd ledger && sed -i 2026.csv` names no `ledger/` path.

    PER READING as well as per segment, and each reading on its own (`_readings_of`).
    """
    return any(_a_reading_writes_the_ledger(reading) for reading in _readings_of(command))


def uses_an_unguarded_validator(command):
    """Does this command do something OTHER THAN READ to a second `ledger_add.py`?

    ITS OWN QUESTION, AND ASKED OF EVERY SHELL LINE. It used to live inside `_writes_ledger`, and
    `handle_pre_tool_use` asks that one only when the same line also carries a commit, a push or a
    report -- so `python tools/ledger_add.py` on its own was rc 0 and the attacker's validator ran;
    the gain became effective with a SECOND, then-checked line (`BUG-0159`). Running a validator
    nobody guards is not a write and has nothing to do with whether this line commits, so the
    question stands on its own and is put to every shell call
    (`tools/test_hooks_v2.py::test_an_unguarded_validator_is_refused_without_a_blocked_operation`).

    The canonical one is protected precisely so that it CAN be vouched for; a second copy elsewhere
    is how you get one that nobody guards. But only where something OTHER than a read happens to
    it: `cat ledger_add.py` reads it, and after a step into `scripts/` the bare name IS the
    canonical file, so `cd scripts && python ledger_add.py --validate …` is the sanctioned way out
    of a block -- refusing either one blocks the remedy.
    """
    return any(_a_reading_uses_an_unguarded_validator(reading)
               for reading in _readings_of(command))


def _a_reading_uses_an_unguarded_validator(reading):
    segments, inside_scripts = _segments_of(re.sub(r"/{2,}", "/", reading))
    for segment in segments:
        # ...asked of the stages BESIDE the vouched runs, so a decoy path named in THEIR arguments
        # is prose while one in a neighbouring stage is still a decoy
        # (`_stages_beside_the_vouched_runs`)
        stages = _stages_beside_the_vouched_runs(segment.strip(), inside_scripts)
        if (any(_DECOY_VALIDATOR_RX.search(stage) for stage in stages)
                and not all(_verb_only_reads(stage) for stage in stages)):
            return True
    return False


def _a_reading_writes_the_ledger(reading):
    # THE SUBSTITUTION OPENING IS A CUT, NOT A REWRITE (`_COMMAND_CUT_RX`). Without the cut, ALL of
    # `git commit -m "$(sed -i … ledger/2026.csv)"` is one segment whose verb is `git commit` --
    # read-only as far as the ledger goes -- and the `sed -i` inside it is never examined. That is
    # the round-6 bypass reappearing through the round-9 rewrite, which is exactly the kind of
    # thing a rewrite is most likely to do.
    text = re.sub(r"/{2,}", "/", reading)
    segments, inside_scripts = _segments_of(text)
    for segment in segments:
        segment = segment.strip()
        if not segment or not _LEDGER_PATH_RX.search(segment):
            continue
        # a redirect INTO a ledger path is a write whatever the verb in front of it
        if any(_LEDGER_PATH_RX.search(target) for target in _redirect_targets(segment)):
            return True
        # Each of this kit's own guarded programs vouches for its OWN stage only, for the reason
        # `_stages_beside_the_vouched_runs` carries. A redirect was decided above, so nothing any
        # of them could carry into the ledger passes here.
        #
        # A DECOY IS NOT RE-ASKED HERE. It was, without the read-only condition its own reader
        # carries, so one question had two answers in one function and the stricter one won
        # wherever the line happened to name a ledger path: `grep "tools/ledger_add.py"
        # ledger/2026.csv && git commit` was refused for a line that reads two files
        # (`BUG-0154` -- `tools/test_hooks_v2.py::test_a_decoy_path_in_a_reading_stage_is_prose`).
        # `uses_an_unguarded_validator` asks it of every segment of every shell line, which is
        # strictly more than this branch ever reached.
        stages = _stages_beside_the_vouched_runs(segment, inside_scripts)
        if not stages or all(_verb_only_reads(stage) for stage in stages):
            continue                          # every stage of the pipeline only reads
        copy = _COPY_OUT_RX.search(segment)
        if (copy and _LEDGER_PATH_RX.search(copy.group("src"))
                and not _LEDGER_PATH_RX.search(copy.group("dst"))):
            continue                          # copying the ledger OUT is a read
        return True
    # ...and the working-directory form, which names no ledger path at all
    if _CD_LEDGER_RX.search(text) and re.search(r"\.csv\b", text, re.IGNORECASE):
        for segment in segments:
            if re.search(r"\.csv\b", segment, re.IGNORECASE) and not _verb_only_reads(segment):
                return True
    return False


# RUNNING the validator is how the agent gets out of the block, so `python scripts/ledger_add.py
# --validate …` must stay allowed. ONLY that shape: an interpreter invoked with `-c`/`-e`/`-m`
# carries its payload inline and is never exempt.
# THE SCRIPT ARGUMENT ENDS WHERE A SHELL WORD ENDS, and `\S+` does not say that. This pattern only
# ever REMOVES text from the pre-filter's view, so a token that runs on past the word swallows
# whatever follows it: `python scripts/ledger_add.py>scripts/ledger_add.py` is one `\S+` run, both
# the run and the REDIRECT TARGET disappeared from `scanned`, no protected path was left in it, and
# the branch that refuses a write to the judge was never reached -- rc 0 from this gate for a line
# that truncates the judge, while the same line with a space around the `>` is rc 2. The word end
# is `_WORD_END`, the same one `_canonical_run` uses, so the two cannot drift
# (`tools/test_hooks_v2.py::test_the_prefilter_sees_everything_the_decision_sees`).
_INTERPRETER_SCRIPT_RX = re.compile(
    r"(?:^|(?<=[;&|(]))\s*(?:python[0-9.]*|py|perl|ruby|node)" + _INTERPRETER_OPTIONS +
    r"\s+([^" + _WORD_END_CHARS + r"]+\.(?:py|pl|rb|js))" + _WORD_END,
    re.IGNORECASE | re.MULTILINE)
_INLINE_CODE_RX = re.compile(r"(?:^|[;&|(])\s*(?:python[0-9.]*|py|perl|ruby|node)\s+"
                             r"[^\s]*-(?:c|e|m)\b", re.IGNORECASE | re.MULTILINE)


def _ledger_csvs_in(root):
    """Every canonical ledger file. One definition for the edit branch and the enforcing path.

    `os.listdir`, NOT `glob`: `glob.escape` fixes the metacharacter case but leaves the failure
    mode intact for the next one. A project at `.../Kunde [GmbH]/proj` made `glob` return ZERO
    files while the directory held one, and `judge()` reads "no files" as "nothing invalid" — so
    commit, push, merge, reports and dispatch were all allowed with a broken ledger in place, on a
    path an office workspace plausibly has (`[`, `]` are legal on Windows and POSIX; `*` and `?`
    extend it on POSIX). Listing the directory cannot be fooled by the project's own name.
    """
    directory = os.path.join(root, LEDGER_DIR)
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    # EVERY csv here, including one whose name is not a year. The validator refuses those (they are
    # invisible to `euer_report.py` while sitting where the ledger lives), and filtering them out
    # HERE would mean the gate never presents the file whose refusal is the whole point: a stray
    # `2026 - Kopie.csv` would then be silently ignored rather than flagged, and the script's rule
    # and the gate's view would disagree again — which is the mistake that produced B6.
    return sorted(os.path.join(directory, name) for name in names
                  if name.lower().endswith(".csv"))


def _is_ledger(path, root):
    """(rel, absolute) when `path` IS one of ours, else None. Path identity, not name matching."""
    try:
        absolute = os.path.abspath(path)
        rel = os.path.relpath(absolute, root).replace("\\", "/")
    except (OSError, ValueError):
        return None
    if rel.startswith("../") or os.path.isabs(rel):
        return None  # outside the repo: not this project's ledger
    parts = rel.split("/")
    if len(parts) != 2 or parts[0].lower() != LEDGER_DIR or not parts[1].lower().endswith(".csv"):
        return None
    return rel, absolute


def _stamp(absolute):
    """Change detection for the EARLY-WARNING path only.

    Deliberately cheap and deliberately not trusted: size+mtime is defeated by `touch -r` and by
    any same-length rewrite. That was a hole while the block depended on it; now the enforcing
    path re-validates unconditionally, so the worst a defeated stamp costs is a late warning.
    """
    try:
        info = os.stat(absolute)
    except OSError:
        return None
    return "%d:%d" % (info.st_size, info.st_mtime_ns)


def _validator_argv(script, absolute):
    """The interpreter invocation, with the SCRIPT DIRECTORY off `sys.path`.

    Python puts the script's own directory at `sys.path[0]`, so running `<root>/scripts/
    ledger_add.py` made `<root>/scripts` the first import location — and `scripts/` is ordinary
    project code an agent may write. One `Write scripts/csv.py` containing `import sys;
    sys.exit(0)` therefore shadowed the stdlib module the validator imports, the validator exited
    0, and every ledger looked clean. No shell involved, and protecting `ledger_add.py` itself did
    nothing, because the bypass never touches it.

    The synchronous design makes this the WHOLE gate rather than a corner: every commit, push,
    merge, report and dispatch decision now runs this interpreter. `-P` (3.11+) drops the script
    directory; `-E` ignores `PYTHONPATH`/`PYTHONSTARTUP`; `-s` drops the user site directory; and
    `-S` skips `site` entirely, which is the only one that stops `.pth` PROCESSING.
    That last one closed a live bypass: `.venv/` is writable (the shipped `.gitignore` invites an
    in-repo venv, and `requirements-office.txt` asks for one), so two Writes — a
    `site-packages/zz_evil.pth` containing `import zz_evil`, and a `zz_evil.py` registering an
    `atexit` hook that calls `os._exit(0)` when `--validate` is in argv — made the validator exit 0
    WHILE STILL PRINTING its findings. `-S` is safe here because the validator imports stdlib only.
    Below 3.11 `-P` does not exist, so it is omitted and `python scripts/harness.py doctor` reports the gap rather
    than this file pretending to close it.
    """
    flags = ["-S", "-E", "-s"]
    if sys.version_info >= (3, 11):
        flags.insert(0, "-P")
    return [sys.executable] + flags + [script, "--validate", absolute]


def _validate(root, absolute):
    """Run the project's own validator. Anything that is not a clean exit 0 is a FINDING.

    A missing validator, a timeout, an interpreter that will not start: "nothing can judge this
    file" and "this file is fine" are the same outcome only if you are willing to ship the
    difference, and this is money data.
    """
    script = os.path.join(root, VALIDATOR)
    if not os.path.isfile(script):
        return ["%s is missing, so this ledger cannot be validated at all" % VALIDATOR]
    try:
        result = _compat.run_captured(_validator_argv(script, absolute),
                                      cwd=root, timeout=VALIDATE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return ["the validator did not finish within %ds, so this file is UNJUDGED"
                % VALIDATE_TIMEOUT]
    except OSError as exc:
        return ["the validator could not be started (%s), so this file is UNJUDGED" % exc]
    # THE OUTPUT IS READ FIRST, and an `INVALID:` line counts even on exit 0. Belt and braces
    # beside `-S`: the `.pth` bypass suppressed the exit CODE while the findings were still on
    # stderr, so anything that only forges the status now has to silence the output too.
    findings = [line.split("INVALID: ", 1)[-1] for line in (result.stderr or "").splitlines()
                if "INVALID:" in line]
    if findings:
        return findings
    if result.returncode == 0:
        return []
    return ["validator exited %d: %s" % (result.returncode, (result.stderr or "").strip()[:200])]


def judge(root):
    """Validate the ledger NOW and return {rel: findings}. The enforcing path calls this.

    No cache is consulted. That is the whole point: the previous design asked a file the guarded
    party could write whether the guarded party had broken anything.

    A TOTAL budget, not just a per-file one: 12 ledger files each taking the full per-file cap is
    241s of a session standing still on one `git add`. Running out of budget is itself a finding,
    because "we did not get to look" is not "it is fine" — and it is a finding this gate can still
    report, which is the difference between a bound it keeps itself and one imposed from outside
    (`_compat.HOOK_DEADLINE_SECONDS` carries what was measured about those).
    """
    verdicts, unreached = {}, []
    started = time.monotonic()
    targets = _ledger_csvs_in(root)
    for absolute in targets:
        rel = os.path.relpath(absolute, root).replace("\\", "/")
        # room for a FULL per-file timeout, not merely "budget left": checking `elapsed >
        # TOTAL_BUDGET` before starting let a file begin at 39.9s and run to 59.9s -- measured at
        # 52.5s for 5 files x a 13s validator, i.e. half again over the cap this line exists to
        # keep. The guaranteed bound is now TOTAL_BUDGET.
        if time.monotonic() - started > TOTAL_BUDGET - VALIDATE_TIMEOUT:
            unreached.append(rel)
            continue
        findings = _validate(root, absolute)
        if findings:
            verdicts[rel] = findings
    return verdicts, unreached


def _read_state(root):
    path = os.path.join(root, STATE)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(root, data):
    path = os.path.join(root, STATE)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp-%d" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False, sort_keys=True)
        os.replace(tmp, path)
    except OSError:
        pass  # an unwritable cache costs a warning, never a released block: see judge()


def _remember(root, rel, findings, stamp):
    state = _read_state(root)
    entry = {"findings": findings[:20]}
    if stamp:
        entry["stamp"] = stamp
    state[rel] = entry
    _write_state(root, state)


# -- the enforcing path -------------------------------------------------------

def _refuse_if_invalid(root, what):
    verdicts, unreached = judge(root)
    if not verdicts and not unreached:
        return
    # BROKEN and NOT-LOOKED-AT are reported as two different things. Listing the unreached files
    # as findings told the operator that all six ledgers were broken when two were slow and four
    # were never opened -- and the remedy ("correct the rows") applied to neither kind.
    detail = []
    for rel in sorted(verdicts):
        detail.append("  %s:" % rel)
        detail.extend("    - " + f for f in verdicts[rel][:6])
    if unreached:
        detail.append("  NOT CHECKED — the %ds budget for the whole ledger ran out before these "
                      "files were opened; they may be fine or broken:" % TOTAL_BUDGET)
        detail.extend("    - " + rel for rel in sorted(unreached))
    remedy = ("correct the rows, or `git restore` the file — as its OWN call, then commit in a "
              "second one; writing and committing in one command is refused separately. Nothing "
              "has to be cleared afterwards: the next attempt re-validates. "
              "`python %s --validate <file>` shows the detail." % VALIDATOR)
    if unreached:
        remedy += (" For the unchecked files, validate them one at a time — a ledger that needs "
                   "more than %ds is a defect in its own right, and this gate stops looking at "
                   "its own budget rather than leaving the session standing still."
                   % VALIDATE_TIMEOUT)
    _kernel.block(
        HOOK,
        # The headline still says INVALID when something IS invalid: splitting "broken" from
        # "not looked at" must not cost the one word that tells the reader what happened.
        "%s — %s is blocked (spec II.9). This was checked against the files just now, not read "
        "from a note.\n%s"
        % ("the ledger is INVALID right now" if verdicts
           else "the ledger could not be fully checked", what, "\n".join(detail[:24])),
        remedy=remedy)


def requires_a_sound_ledger(data):
    """WHAT this call is, when it is one the books have to be sound for — else None.

    ONE READER FOR TWO GATES. `gate_second_booking` (FR-0065) asks a different question of the same
    rows at the same shell moments, and "is this a commit, a push, a merge or a report" answered
    twice is the drift that lets one of the two stand down where the other bites. The string it
    returns is the phrase the refusal names the operation by, so the two gates do not describe one
    call in two ways either.

    WHICH of the moments a caller ACTS on is the caller's own decision and not this reader's, and
    the two differ in one: a DISPATCH. An unsound ledger is a reason not to send a specialist at it,
    but an unread ROW is the opposite — the second reading is written by a second spawn, so refusing
    the spawn would refuse the only way out of the refusal. `gate_second_booking`'s own header
    carries that, and
    `tools/test_hooks.py::test_the_booking_gate_stands_at_the_shell_moments_and_not_at_a_dispatch`
    measures both halves.
    """
    tool = data.get("tool_name")
    if tool in SPAWN_TOOLS:
        return "specialist dispatch"
    if tool not in SHELL_TOOLS:
        return None
    raw = str((data.get("tool_input") or {}).get("command") or "")
    # ONE view, the one the shell hands git: quote marks gone, their content kept. That is
    # what makes `eval "git commit -m x"` visible here without a second search over the raw
    # text — the workaround the deleted prose-stripping reader needed.
    text = _compat.git_argument_text(raw)
    if (any(invocation.runs(*_BLOCKED_GIT_SUBCOMMANDS)
            for invocation in _compat.git_invocations(raw))
            or _BLOCKED_SCRIPT_RX.search(text) or _BLOCKED_SCRIPT_RX.search(raw)):
        return "this command (commit/push/merge/report)"
    return None


def handle_pre_tool_use(data):
    root = _kernel.find_repo_root(data.get("cwd"))
    tool = data.get("tool_name")
    operation = requires_a_sound_ledger(data)
    if tool in SPAWN_TOOLS:
        if operation:
            _refuse_if_invalid(root, operation)
    elif tool in SHELL_TOOLS:
        raw = str((data.get("tool_input") or {}).get("command") or "")
        blocked_op = operation is not None
        if blocked_op and _writes_ledger(_without_messages(raw)):
            _kernel.block(
                HOOK,
                "this command touches a ledger file with a writing command and then "
                "commits/pushes/reports in the SAME call. (It may only be reading it — a shell "
                "command's source and destination are not reliably distinguishable, and for money "
                "data the over-block costs one extra call while the under-block costs a bad "
                "commit.) Checking the ledger first cannot help: the verdict is stale the moment the "
                "command rewrites the file, and the warning afterwards arrives with the bad data "
                "already in HEAD (spec II.9 keeps commit blocked until the books are correct). "
                "`git restore ledger/<year>.csv && git commit` is refused for the same reason and "
                "is NOT an exception — a restored file can be a previously committed broken one.",
                remedy="split it into two calls: write (or restore) the ledger first, then commit "
                       "separately. The second call re-validates and refuses if the write broke "
                       "anything, which is the whole point.")
        if blocked_op:
            _refuse_if_invalid(root, operation)
        # A SECOND `ledger_add.py` is asked about on EVERY shell line, not only on one that also
        # commits: running the attacker's own validator is not a write and does not become one
        # because a commit stands beside it (`BUG-0159`).
        if uses_an_unguarded_validator(_without_messages(raw)):
            _kernel.block(
                HOOK,
                "this command uses a second '%s' -- a validator outside '%s', which is the only "
                "copy this kit protects and therefore the only one whose verdict means anything. "
                "Reading one is fine; running it, writing it or copying over it is not."
                % (os.path.basename(VALIDATOR), VALIDATOR),
                remedy="run the canonical validator instead: `python %s --validate <file>`, or "
                       "`python %s --validate ../ledger/<year>.csv` from inside its own directory."
                       % (VALIDATOR, os.path.basename(VALIDATOR)))
        # a shell write to the judge itself. An interpreter running a SCRIPT is exempt (that is how
        # `--validate` gets run); an interpreter with an inline `-c`/`-e`/`-m` payload never is.
        # ...asked of the SAME VIEWS the decision below works on, and that is what a cheap
        # pre-filter owes: one narrower than the decision it guards is a hole, not a saving. It read
        # the raw text only, where a quote mark can stand between a copy verb and its destination --
        # and `_PROTECTED_DIR_RX`'s copy branch has nowhere to put one. `cp -r evil/. "scripts/" &&
        # git commit`, `rsync -a evil/ "scripts/"` and `mv evil.py "scripts/"` therefore never
        # reached the branch that would have refused them: rc 0 at HEAD and before this line
        # existed, with `_writes_protected` answering True all along
        # (`tools/test_hooks_v2.py::test_the_prefilter_sees_everything_the_decision_sees`). Adding
        # views can only make the branch RUN more often; what it refuses is still the decision's
        # answer.
        scanned = "\n".join(
            view if _INLINE_CODE_RX.search(view) else _INTERPRETER_SCRIPT_RX.sub(
                lambda m: m.group(0)[:m.start(1) - m.start(0)], view)
            for view in [raw] + _readings_of(raw))
        # SAME allowlist decision as `_writes_ledger`. This branch kept the old write DENYLIST
        # for one round longer, so the very verbs just removed from it still worked here:
        # `curl -o scripts/ledger_add.py` installs a WORKING stub and releases the block outright
        # -- the round-3 escape, reachable again through a verb the denylist never knew.
        # the DIRECTORY too, or `tar -xf evil.tar -C scripts/` never reaches the write check at
        # all: it names no protected FILE, and the outer condition was the file pattern alone.
        if ((_PROTECTED_RX.search(scanned) or _PROTECTED_DIR_RX.search(scanned))
                and _writes_protected(raw)):
            _kernel.block(
                HOOK,
                "'%s' and '%s' are the ledger's JUDGE, not project data — a shell write to either "
                "would let the agent under a ledger block rewrite what decides the block."
                % (VALIDATOR, STATE),
                remedy="fix the ledger rows instead. If the validator itself is wrong, that is an "
                       "infrastructure defect: report it to the user; the fix belongs in the KIT "
                       "and arrives via a kit update.")
    sys.exit(0)


# -- the early-warning path ---------------------------------------------------

# The finance page, and the bound on rendering it. Separate from `VALIDATE_TIMEOUT` because it is
# a different program with a different job: the renderer reads the whole year plus two reference
# files and writes one HTML file, where the validator reads one CSV. The number is this process's
# own promise and derives from nothing -- what it has to be is short enough that a POST hook never
# becomes the thing the operator waits for.
RENDERER = "tools/finance_dashboard.py"
RENDER_TIMEOUT = 20


def _render_the_finance_page(root):
    """Re-render `dashboards/finanzen.html` after a ledger change, and never block on it.

    NOTHING STARTED THE GENERATOR (`BUG-0201`). The ledger has no kernel writer: its two write
    paths -- `scripts/ledger_add.py` and the hand edit spec II.9 allows -- pass exactly one place,
    this handler, and it validated the changed file and did nothing else. So the page was as old as
    its last run by hand, and the masthead does not say so: it prints the youngest date the ledger
    carries, which a back-dated booking leaves byte-identical (measured 2026-09-02).

    THE CHANGED-FILE CONDITION IS THE CALLER'S, and it is what makes this affordable: this function
    is reached only where `handle_post_tool_use` has already found a ledger file whose stamp moved,
    so an ordinary shell call in an office repo starts no renderer at all.

    EVERY FAILURE IS A NOTE, NEVER A REFUSAL. This is the early-warning path, which cannot block by
    construction, and a page that failed to render is not a reason to stand between the operator
    and their books -- the ABOUT file in the directory still names the command to run by hand.
    A kit whose project has no renderer (an older stock, or one the user removed) simply has
    nothing to start, which is why the file is asked for rather than assumed
    (`tools/test_finance_dashboard.py::test_a_ledger_write_renders_the_finance_page`).
    """
    script = os.path.join(root, RENDERER)
    if not os.path.isfile(script):
        return
    try:
        result = _compat.run_captured([sys.executable, script], cwd=root,
                                      timeout=RENDER_TIMEOUT)
    except (subprocess.TimeoutExpired, OSError) as exc:
        _kernel.record_note(HOOK, "the finance page was not re-rendered (%s); run `python %s`"
                            % (exc.__class__.__name__, RENDERER))
        return
    if result.returncode != 0:
        _kernel.record_note(HOOK, "the finance page was not re-rendered (renderer exited %d); "
                            "run `python %s`" % (result.returncode, RENDERER))


def handle_post_tool_use(data):
    tool = data.get("tool_name")
    root = _kernel.find_repo_root(data.get("cwd"))
    changed = []
    if tool in FILE_TOOLS:
        for path in _compat.file_paths(data):
            found = _is_ledger(path, root)
            if found:
                changed.append(found[1])
    elif tool in SHELL_TOOLS:
        if not os.path.isdir(os.path.join(root, LEDGER_DIR)):
            sys.exit(0)
        state = _read_state(root)
        for absolute in _ledger_csvs_in(root):
            rel = os.path.relpath(absolute, root).replace("\\", "/")
            if _stamp(absolute) != (state.get(rel) or {}).get("stamp"):
                changed.append(absolute)
    if not changed:
        sys.exit(0)
    _render_the_finance_page(root)

    # EVERY changed file, then ONE report. Reporting inside the loop exited on the first finding,
    # so a patch touching two ledgers left the second unexamined -- and `_compat.file_paths` exists
    # precisely because a multi-file patch must not slip past a single-path check.
    verdicts = {}
    for absolute in changed:
        rel = os.path.relpath(absolute, root).replace("\\", "/")
        findings = _validate(root, absolute)
        _remember(root, rel, findings, _stamp(absolute))
        if findings:
            verdicts[rel] = findings
    if not verdicts:
        sys.exit(0)
    detail = []
    for rel in sorted(verdicts):
        detail.append("  %s:" % rel)
        detail.extend("    - " + f for f in verdicts[rel][:8])
    _kernel.record_note(HOOK, "invalid after a write: %s" % ", ".join(sorted(verdicts)))
    _compat.stop(
        "[team-kit %s] the ledger is INVALID after that write. No rollback was performed; the file "
        "stands as written (spec II.9). Commit, push, merge, reports and specialist dispatch will "
        "be refused until it validates — each of those re-checks the file itself, so there is "
        "nothing to clear once you have fixed it.\n%s\n"
        "Remedy: correct the rows, or `git restore` the file — as its own call; committing in the "
        "same command is refused. `python %s --validate <file>` shows the detail." % (HOOK, "\n".join(detail[:30]), VALIDATOR),
        event="PostToolUse")


HANDLERS = {"PreToolUse": handle_pre_tool_use, "PostToolUse": handle_post_tool_use}


def main():
    data = _kernel.payload(HOOK)
    event = str(data.get("hook_event_name") or "")
    handler = HANDLERS.get(event)
    if handler is None:
        sys.exit(0)
    with _kernel.fail_closed(HOOK, event):
        handler(data)


if __name__ == "__main__":
    _kernel.run_gate(HOOK, main)
