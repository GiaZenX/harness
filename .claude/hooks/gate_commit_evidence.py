#!/usr/bin/env python3
"""
Gate 3 (SR-0009 clause 3): no RECORDING OF HISTORY without a verifier's verdict on THIS state.

TWO ANSWERS, NOT ONE, and which one a line gets depends on whether a verdict about it could exist
at all. `git commit` records a tree that is already there when this hook is asked, so it is GATED:
an Evidence item naming that tree's digest opens it. Every other subcommand that AUTHORS a commit
(`merge`, `revert`, `cherry-pick`, `am`, `rebase` and the rest of `AUTHORS_A_COMMIT`) builds its
result in the same step that records it -- the digest cannot exist beforehand, so no verdict can
name it and the line is REFUSED, with the remedy that produces the state first without recording
it. Until 2026-08-13 this gate asked `Invocation.runs("commit")` and nothing else, and
`git merge --no-ff other`, `git revert --no-edit HEAD`, `git cherry-pick`, `git am`,
`git rebase --continue` and `git pull` were each measured rc 0 with a valid verdict in the tree
(`docs/POST_V2_WISHLIST.md` H2).

WHAT IT READS. `_compat.git_invocations` -- the kits' shell reader, not a second regex. It resolves
wrapper payloads (`bash -lc "..."`), here-strings, line continuations and both shells' escapes, and
it reports a verb the text does not fix as UNRESOLVED. Such a verb could be any subcommand, an
authoring one included, so it is refused with the kits' own `UNRESOLVED_VERB_NOTE` ("spell the
subcommand literally"). That is stricter than what stood here: an unresolved verb used to take the
evidence route, and `git ${VERB} --no-ff other` was measured rc 0 with a valid verdict in the tree.
The price is the reader's own over-trigger class (`ls git*`, `echo git$VERSION`, `grep -rn "git$"
.`) becoming an unconditional refusal, and the remedy for those is compliable: spell it otherwise.

WHAT IT DEMANDS. An active Evidence item with `result: pass` that NAMES the digest of the current
working tree (`_harness.working_tree_digest`). Naming, not describing: the digest is the identity
of the subject, so a verdict recorded on an earlier state stops covering the tree the moment the
tree moves -- which is the whole point, and the reason `python tools/bump_kit_version.py` has to
run BEFORE the verdict is recorded rather than after.

THE LOCK THIS PUTS ON THE DOOR IS REAL, so the way through it is measured rather than asserted. The
refusal below prints the exact `kernel.cli evidence` line with the digest already substituted, and
`test_gate3_remedy_is_executable_and_opens_the_commit` reads that digest OUT of the refusal, runs
the command as printed, and repeats the same call -- so the remedy stops working the moment it is
edited into something unrunnable. A gate whose remedy cannot be executed is worse than no gate.

THE DIGEST IS TAKEN BEFORE THE LINE RUNS, which is all a PreToolUse hook can do -- so a line that
moves the tree and THEN commits was certified against a state that no longer exists when the commit
happens (`echo x >> docs/note.md && git commit -m wip`, measured rc 0 on 2026-08-05 with a valid
verdict recorded). That is closed by asking about the SHAPE of the line rather than about the
future: every command the line does not put AFTER the commit must be read-only, judged by the kits'
own classification -- and what the line puts after a commit it does not wait for is nothing.
`git add -A && git commit` survives it -- staging moves no byte the digest reads, because the
digest is `diff HEAD`, which covers staged and unstaged alike.

WHAT IT DOES NOT COVER, named rather than implied:
  * a commit object AUTHORED SOMEWHERE ELSE and pointed at from here. `git fetch` (open per AC-2)
    brings such objects in, and `git unpack-objects` / `git index-pack` / `git clone` /
    `git bundle` install one from a packfile or bundle; `git update-ref` / `git branch -f` /
    `git reset --hard` / `git checkout -B` (all measured to author nothing) then make it branch
    history. This gate refuses at the AUTHOR end, so it closes the one-call chain that fabricates a
    NEW commit here (`hash-object -t commit`, `commit-tree`, `fast-import` -- all refused) but NOT
    the installation of a commit that already exists in some real repository. The measured chain
    and why the one-call fabricate-and-install route stays closed are design note section 8.1; the
    residue is that an object authored in a prior call, outside this repo, can be installed here.
  * `git commit --amend`, which authors a new commit for the tree the digest DOES describe and
    replaces the parent chain the digest says nothing about. It stays on the evidence route, so
    what is certified is the tree, not the history it is hung into.
  * a subcommand this repo's git does not know and this gate therefore refuses rather than reads
    (an alias, an external `git-<name>`): the refusal says to spell the git command out. What it
    would run is invisible to every reader of the line.
  * `git hash-object` used to write a BLOB (`git hash-object -w <file>`), which this gate refuses
    too -- the verb is the subject, not its `-t` type, because the type can be spelled where the
    gate cannot see it. That over-refusal is named in design note section 8.
  * a commit made from a shell OUTSIDE the provider. Hooks gate tool calls, nothing else -- and
    that is the same door every refusal here names as the way to repair a broken gate.
  * a lead that WANTS past it. The refusal prints the command that lifts it, on purpose: this gate
    makes committing without a verdict an explicit, recorded act, not an impossible one.
"""
import os
import sys

# THE IMPORT IS INSIDE THE PROTECTION -- see the same block in `gate_lead_write_scope.py` and the
# measurement in `_harness.py`'s header: a module-level import failure exits 1, and the provider
# reads that as an allow.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import _harness
except BaseException as error:  # noqa: BLE001 -- a gate that cannot load must not mean "allow"
    sys.stderr.write(
        "[harness gate] refused: the shared body of this repo's gates (.claude/hooks/_harness.py) "
        "could not be loaded (%r), so this call could not be judged. A gate that cannot decide "
        "refuses.\nRemedy: repair the file from a shell OUTSIDE Claude Code and start a new "
        "session -- it cannot be repaired from inside this one.\n" % (error,))
    sys.exit(2)


# -- which subcommands record history (SR-0009 clause 3) ----------------------
#
# THE PROPERTY, in the words the refined SR-0009 gives it: this line can AUTHOR a commit object out
# of the state at hand -- porcelain OR plumbing -- so a following (open) ref move can install it
# into branch history. It is read at the AUTHORING end, not the ref-moving end, because the two can
# be one line: `git update-ref refs/heads/main $(git commit-tree -m x HEAD^{tree})` -- measured,
# one commit object authored and HEAD plus refs/heads/main pointing at it afterwards, the same with
# `git stash create` and the same with the PLUMBING form that does not even need a subcommand git
# calls a commit-maker:
#   git update-ref refs/heads/main $(printf 'tree %s\n...\n' $(git rev-parse HEAD^{tree})
#                                    | git hash-object -t commit -w --stdin)
# -- measured rc 0, no verdict in the tree, `refs/heads/main` moved onto a freshly authored commit
# object (TSK-0056 verifier F1). `git hash-object -t commit -w --stdin` writes a commit object out
# of an existing tree exactly as `commit-tree` does, so it is an author and it is in this set.
# Closing this at the MOVER end means refusing `update-ref`, `branch -f`, `reset --hard`,
# `checkout -B`, and the ordinary path to a commit has to stay open -- so the refusal sits at the
# author end, which is also exactly where clause 3's own reason holds: the state such a command
# records does not exist before it runs, so no digest can name it.
#
# THE VERB IS THE SUBJECT, NOT ITS FLAGS. `hash-object` is refused whole -- not only with
# `-t commit`. Reading `-t commit` as the thing to refuse is the fail-OPEN direction (the type can
# be spelled where this gate cannot see it), and over-refusing `git hash-object -w <blob>` is the
# safe one; that over-refusal is named as a residue in the design note (section 8).
#
# AN ENUMERATION, BECAUSE THE RUNNING GIT DOES NOT NAME THIS SET. `git --list-cmds=list-history` is
# git's HELP grouping and it is wrong in both directions at once -- it carries `branch`, `switch`,
# `reset`, `tag`, `backfill` (measured: no commit authored) and misses `revert`, `cherry-pick`,
# `am`, `pull`, `commit-tree`, `hash-object`, `stash`, `notes`, `replay`, `filter-branch`,
# `subtree`, `fast-import`. That is section 1 of
# `docs/reviews/2026-08-13-tsk0056-history-recording-design.md`, and the classification of every
# candidate with its numbers is section 3 of it.
#
# WHAT IS NOT HERE, AND NAMED: the commands that INSTALL a commit object authored ELSEWHERE --
# `git unpack-objects`, `git index-pack`, `git bundle`/`git clone` and `git fetch` (open per AC-2).
# Measured (design note section 8.1): each can put a commit object into the store that a ref move
# then installs, but only from a packfile or bundle whose commit was authored somewhere first -- and
# every command that AUTHORS one is in the set above and refused, whatever the `-C <dir>` it is
# pointed at. So no NEW fabricated commit reaches the store through them in one call; what does is a
# commit that already exists in some real repository, which is the `fetch` class the contract keeps
# open. That is the "authored-elsewhere / imported object" residue, carried with its measured chain.
#
# SO THIS CARRIES A TRIPWIRE THAT MEASURES BOTH ENDS against the installed git, and each end is a
# test rather than a sentence here (SR-0008): every entry here must author a commit object in a real
# repo (`test_every_subcommand_the_gate_calls_an_author_authors_one` -- a dead entry says so), every
# entry of the near-miss table must author none
# (`test_the_commands_the_gate_leaves_open_author_nothing` -- a recorder that slipped out of this set
# says so), and every name git DOES put in its own history group has to be classified on one side or
# the other (`test_every_command_git_itself_calls_history_is_classified` -- a newcomer says so).
AUTHORS_A_COMMIT = frozenset((
    # authors the commit AND makes it branch history in the same step
    "commit", "merge", "pull", "rebase", "revert", "cherry-pick", "am", "filter-branch",
    "subtree", "fast-import",
    # authors a commit object that lands outside refs/heads -- one open ref move away from branch
    # history, and that move is measured. `hash-object` and `commit-tree` are the PLUMBING forms:
    # they write a commit object from a tree and stdin, land it nowhere, and a ref move installs it
    "stash", "commit-tree", "hash-object", "notes", "replay",
    # authors by construction, not demonstrable in this suite -- see NOT_DEMONSTRABLE
    "quiltimport", "svn", "p4", "citool", "gui",
))

# The one author whose subject EXISTS before it runs, and therefore the one that can be certified
# rather than refused. Everything the remedy routes through ends here.
CERTIFIABLE = "commit"

# Why five entries of the set above have no scenario in the tripwire. A dict and not a comment,
# because `test_every_author_is_either_demonstrated_or_says_why_it_cannot_be` pins these keys: an
# entry that joins this bucket has to say what stops it being demonstrated, and one that joins the
# set without either a scenario or a reason turns that test red.
NOT_DEMONSTRABLE = {
    "quiltimport": "applies a quilt series and commits each patch; the harness could not build a "
                   "series it accepted (rc 0, nothing authored)",
    "svn": "a Subversion bridge -- `dcommit`/`rebase` author commits, and no svn server is here",
    "p4": "a Perforce bridge -- `sync`/`submit` author commits, and no p4 server is here",
    "citool": "git's commit UI; it needs a display",
    "gui": "git's UI, `git gui citool` included; it needs a display",
}

# The option that tells an authoring subcommand to produce the state and NOT record it -- the
# "produce first" half of clause 3's remedy. It has to stay RUNNABLE: a refusal whose remedy is
# itself refused cannot be complied with, which is the failure mode `_compat.UNRESOLVED_VERB_NOTE`
# exists for.
SUPPRESSOR = "--no-commit"
# ...and its counterpart, DERIVED rather than paired up by hand: git spells a negation with a `no-`
# prefix, and the last spelling of an option wins. Measured: `git merge --no-commit --commit
# --no-ff other` records a commit, `git merge --commit --no-commit --no-ff other` does not, and the
# same for `revert` and `cherry-pick`.
COUNTERPART = "--" + SUPPRESSOR[len("--no-"):]
# Which authors the option really stops FOR EVERY SPELLING AND CONFIGURATION of the same
# invocation, which is what the refined SR-0009 requires of an exemption -- MEASURED, not assumed.
# `git rebase --no-commit other` and `git am --no-commit patch.mbox` record a commit anyway (rc 0,
# one object, branch ref moved), so they are not here. `pull` is NOT here either, and that is this
# round's correction (TSK-0056 verifier F2): `git pull --no-commit --rebase`, `--no-commit -r`,
# `--no-commit --rebase=true` and `-c pull.rebase=true pull --no-commit` were each measured to
# author a commit and move refs/heads/main (design note section 3). `--no-commit` suppresses pull's
# recording only in its MERGE mode, so it does not suppress for every configuration -- and an
# option that suppresses only sometimes is no exemption. The produce-first route for pull is a
# subcommand that DOES suppress unconditionally: `git fetch` then `git merge --no-commit` (`_remedy`
# says so). This is a tripwire cell -- `test_gates.SUPPRESSED` crosses the option with every verb it
# is asked of (`test_the_produce_first_option_is_exempted_exactly_where_it_works`) and
# `test_no_spelling_of_a_rebase_pull_survives_the_suppressor` drives the rebase spellings, so an
# exemption that grew back to cover pull turns them red.
HONOURS_THE_SUPPRESSOR = frozenset(("merge", "revert", "cherry-pick"))


def _produces_without_recording(call):
    """Does THIS invocation carry the one shape that produces the state without recording it?

    THREE CONDITIONS, EACH OF THEM A MEASUREMENT, and all three fail closed:

      * the subcommand is one the option was measured to stop (`HONOURS_THE_SUPPRESSOR`);
      * the option stands FIRST after the subcommand. Anywhere else is not enough:
        `git merge -m "--no-commit" other` really records a commit (measured, one object, branch
        ref moved) while the token stands in the line, because there it is the VALUE of `-m`.
        Nothing can swallow the token directly after the subcommand, because a subcommand takes no
        value;
      * the counterpart is spelled nowhere in the same invocation (see `COUNTERPART`).

    THE TOKENS ARE THE KITS' RESOLVED WORDS, not the raw text: `git merge "--no-commit" other`,
    `'--no-commit'` and `--no-com"mit"` all arrive here as `--no-commit`, exactly as
    `_compat.git_invocations` resolves `git pu''sh` into a push. A word the text does NOT fix
    (`git merge $FLAG other`) arrives as `$flag`, is not the suppressor, and the line is refused.
    What a resolution this reader gets wrong costs is bounded by git itself: a word the shell does
    not turn into `--no-commit` reaches git as an option it does not know, and git exits without
    recording anything.
    """
    if call.subcommand not in HONOURS_THE_SUPPRESSOR:
        return False
    arguments = [str(token).lower() for token in call.arguments]
    return bool(arguments) and arguments[0] == SUPPRESSOR and COUNTERPART not in arguments


# The produce-first route for a subcommand whose own `--no-commit` is NOT unconditional. A verb
# here is refused even with the suppressor, and its remedy routes through a subcommand that DOES
# suppress for every configuration. `pull` is the measured case: its `--no-commit` records under
# `--rebase`/`-c pull.rebase=true`, so the state is reached with `fetch` (authors nothing, AC-2)
# and then `merge --no-commit` (suppresses unconditionally).
_PRODUCE_FIRST_ELSEWHERE = {
    "pull": "    git fetch <remote>; then git merge %s <remote>/<branch>   (pull's own %s does "
            "NOT suppress under --rebase or -c pull.rebase=true, measured -- so it is not a "
            "produce-first form)\n",
}


def _remedy(verb):
    """The produce-first route for `verb`, as a line somebody can run."""
    if verb in HONOURS_THE_SUPPRESSOR:
        return ("    git %s %s ...        (the option FIRST after the subcommand, and no `%s` "
                "on the line)\n" % (verb, SUPPRESSOR, COUNTERPART))
    if verb in _PRODUCE_FIRST_ELSEWHERE:
        return _PRODUCE_FIRST_ELSEWHERE[verb] % (SUPPRESSOR, SUPPRESSOR)
    return ("    `git %s` has no produce-first form here -- reach the state with commands that "
            "author nothing (`git apply` for a patch, `git checkout <ref> -- <paths>`, "
            "`git restore --source <ref>`), or run this step from a shell OUTSIDE Claude Code.\n"
            % verb)


def _moves_the_tree_first(data, command):
    """Does this line change the working tree before the commit is recorded?

    Read as a sequence of commands, with the kits' own reader (`_harness.commands`): the commit is
    located, and everything that is not provably AFTER it must be a command whose verbs cannot
    modify anything and that redirects nothing into a file that retains it. A commit the reader
    cannot LOCATE (a wrapper payload, a verb the text does not fix) leaves the position unknown,
    and unknown is answered by requiring the whole line to be read-only -- the fail-closed
    direction, and the same one `Invocation.runs` takes for an unresolved verb.

    "NOT PROVABLY AFTER" IS WHAT THE ORDER OF THE TEXT CAN SHOW, and it shows nothing behind a
    commit the shell does not WAIT for: `git commit &` hands the commit to a child and goes on, so
    what follows runs while the commit reads the tree. Measured 2026-08-05 through this gate, with
    a valid verdict recorded: `echo more >> docs/note.md & git commit -m wip` rc 0 and
    `sed -i "s/a/b/" docs/note.md & git commit -m wip` rc 0, while the same lines with `;` or `&&`
    in that position were rc 2.

    A PIPE IS NO ORDERING EITHER, and that is the same sentence one level down: the stages of a
    pipeline run BESIDE each other, so a write in the committing pipeline is as unordered against
    the commit as one handed to the background. Measured 2026-08-05 with a valid verdict recorded:
    `sed -i "s/a/b/" docs/note.md | git commit -m wip` rc 0 and
    `(echo more >> docs/note.md)|git commit -m wip` rc 0, while the same writes with `;`, `&&` or
    `&` in that position were rc 2 (`docs/reviews/2026-08-05-tsk0015-measurements.md`, section 4).
    So the committing pipeline is examined too -- every stage of it EXCEPT the one that carries the
    commit.

    A COMMAND A SUBSTITUTION INTRODUCES IS ONE OF THE COMMANDS, and it is one the shell runs BEFORE
    the word it stands in reaches `git`. `_harness.command_line` places it like every other, which
    is what makes a write inside the COMMITTING stage visible at all -- that stage is dropped as a
    whole here, and a substitution is neither its verb nor its redirection. Measured 2026-08-07 with
    a valid verdict in the tree: `git commit -m wip $(sed -i s/prose/POISON/ docs/note.md)` was
    rc 0, the file read `POISON` afterwards and the commit carried it.

    ONLY THE VERB OF A STAGE IS THE COMMIT; ITS REDIRECTION IS THE SHELL. The shell sets a redirect
    up BEFORE it starts the program, so a redirect standing in the committing stage truncates its
    target while the commit is still to come. Measured 2026-08-05 through this gate with a valid
    verdict recorded: `git commit -am wip > docs/note.md` was rc 0, and end to end the file was
    EMPTY afterwards while the commit recorded a tree no verdict had ever seen -- `-am` puts the
    truncated file into the commit. So the committing pipeline is examined for its redirect targets
    as a whole, and only its VERBS are read stage by stage.

    A STAGE WITH NO VERB RUNS NOTHING, so it moves nothing -- the same reading `written_paths`
    already makes one level up. Without it the PowerShell spelling of this repo's own environment
    prefix (`$env:PYTHONPATH="team-kits"; git commit ...`) was refused as a line that changes the
    tree before it commits (measured rc 2, TSK-0008 R-a, and
    `test_gate3_leaves_an_environment_prefix_in_front_of_a_commit` is what keeps it open), and
    `_harness.stage_body` is here for the same reason: a declaration header is not the command
    (BUG-0012, and this gate's own use of that cut is measured by
    `test_gate3_reads_a_declaration_head_with_the_same_cut_as_gate1` -- ablated 2026-08-14 in a
    clone outside this repo, every other gate-3 test stayed green without it).
    """
    module = _harness.shell_reader(data)
    compat = _harness.compat(data)
    sinks = module._null_sinks(data.get("tool_name"))
    read = _harness.command_line(module, compat, data, command)

    def records_a_commit(tokens):
        return any(call.runs(CERTIFIABLE)
                   for call in compat.git_invocations(" ".join(str(token) for token in tokens)))

    at = next((index for index, (pipeline, _depth, _child) in enumerate(read)
               if records_a_commit(pipeline)), len(read))
    waited_for = not (at < len(read) and read[at][2])
    for index, (pipeline, _depth, _child) in enumerate(read):
        if index == at:
            stages = [stage for stage in _harness.stages(module, pipeline)
                      if not records_a_commit(stage)]
            # THE WHOLE PIPELINE, INCLUDING THE COMMITTING STAGE -- see "ONLY THE VERB OF A STAGE IS
            # THE COMMIT" in the module docstring.
            targets = module._redirect_targets(pipeline, sinks)
        elif index < at or not waited_for:
            stages = _harness.stages(module, pipeline)
            targets = module._redirect_targets(pipeline, sinks)
        else:
            continue
        bodies = [_harness.stage_body(module, stage) for stage in stages]
        bodies = [body for body in bodies if module._stage_verb(body)]
        if targets or not all(module._stage_is_read_only(body) for body in bodies):
            return " ".join(str(token) for token in pipeline)[:120]
    return ""


def decide():
    data = _harness.payload()
    compat = _harness.compat(data)
    command = str((data.get("tool_input") or {}).get("command") or "")
    if not command.strip():
        # A CALL THIS GATE CANNOT READ IS NOT A CALL IT MAY ALLOW: this gate is registered on the
        # shell tools only, and every shell call carries a command line. One that carries none
        # could not be inspected, which is not the same as "harmless".
        _harness.refuse(
            "this tool call could not be inspected: the payload of a shell tool carries no "
            "command line, so there is nothing to read.\n"
            "Remedy: if this is a legitimate call in a shape the gate does not read, report it -- "
            "the gate refuses rather than guessing, and a guess here is a silent allow.")
    calls = compat.git_invocations(command)
    if not calls:
        return
    note = compat.unresolved_verb_note(command)
    if any(not call.resolved for call in calls):
        _harness.refuse(
            "no recording of history without a verdict: a `git` call in this line has a "
            "SUBCOMMAND the text does not fix, so this gate cannot tell it from one that authors "
            "a commit.\n"
            "The subject of a verdict is a STATE, and a subcommand that authors its result in the "
            "same step records a state no digest could name beforehand -- so an unreadable verb "
            "is refused rather than routed through the evidence check. Measured before this: "
            "`git ${VERB} --no-ff other` was allowed while a valid verdict covered the tree.\n"
            "Remedy: spell the subcommand literally -- unless this line is longer than %d "
            "characters, which is the reader's own limit (`_compat.GIT_READ_LIMIT`): past it no "
            "verb is readable at all and no spelling helps, so there the remedy is to split the "
            "call." % compat.GIT_READ_LIMIT, note=note)
    authoring = [call for call in calls
                 if call.subcommand != CERTIFIABLE and call.subcommand in AUTHORS_A_COMMIT
                 and not _produces_without_recording(call)]
    if authoring:
        verb = str(authoring[0].subcommand)
        _harness.refuse(
            "no recording of history without a verdict: `git %s` can AUTHOR a new commit out of "
            "the state at hand, and a hook is asked BEFORE the line runs -- so the state that "
            "commit would record does not exist yet and no Evidence item can name its digest.\n"
            "Remedy -- three steps, because the middle one needs a subject that already exists:\n"
            "  1. produce the state WITHOUT recording it:\n"
            "%s"
            "  2. let the verifier record a passing Evidence for the resulting tree (the refusal "
            "of a plain `git commit` prints that command with the digest already filled in);\n"
            "  3. record it through the one form whose subject exists beforehand: `git commit`.\n"
            "A ref MOVE is not recording and stays open (`git branch`, `git checkout`, "
            "`git switch`, `git reset`, `git update-ref`), and so does everything on the way to a "
            "commit (`git add`, `git status`, `git diff`, `git fetch`)." % (verb, _remedy(verb)),
            note=note)
    root = _harness.repo_root(data)
    known = _harness.git_command_names(root)
    strangers = [call for call in calls if str(call.subcommand) not in known]
    if strangers:
        _harness.refuse(
            "no recording of history without a verdict: this line runs `git %s`, and the git "
            "installed here does not name %r among its own commands (`git --list-cmds=main`).\n"
            "A name git does not know is an ALIAS, an external `git-<name>` on PATH, or a typo -- "
            "and an alias runs a command no reader of this LINE can see, so this gate cannot tell "
            "whether it records history. Measured: "
            "`git -c alias.z='!git merge --no-ff other' z` reads as the subcommand `z` and "
            "nothing else.\n"
            "Remedy: spell the git command out (`git merge %s --no-ff <ref>`, `git status`, ...)."
            % (str(strangers[0].subcommand), str(strangers[0].subcommand), SUPPRESSOR),
            note=note)
    if not any(call.runs(CERTIFIABLE) for call in calls):
        return
    moving = _moves_the_tree_first(data, command)
    if moving:
        _harness.refuse(
            "no commit: this line changes the working tree before the commit records it (`%s`).\n"
            "The subject of a verdict is a STATE, and a hook is asked BEFORE the line runs -- so "
            "the digest this gate could check describes the tree as it is NOW, not the tree the "
            "commit would record. A verdict on the first cannot cover the second.\n"
            "A command the shell does not wait for counts as being in front of the commit wherever "
            "it stands, because nothing orders it against one.\n"
            "Remedy: split the call. Run the change, then let the verifier judge the result, then "
            "commit on its own line. `git add` is not a change in this sense and stays allowed: "
            "the digest is the diff to HEAD, which covers staged and unstaged alike." % moving,
            note=compat.unresolved_verb_note(command))
    root = _harness.repo_root(data)
    token = _harness.working_tree_digest(root)
    found = _harness.evidence_naming(root, token)
    if found:
        return
    _harness.refuse(
        "no commit: this working tree carries no passing Evidence.\n"
        "The subject of a verdict is a STATE, and this one is\n"
        "    %s\n"
        "(HEAD, the full diff to the working tree, and every untracked non-ignored file; "
        "`%s/` is excluded, because the record is written into it).\n"
        "No active Evidence item with `result: pass` names that digest.\n"
        "\n"
        "Remedy -- the verifier records its verdict, then the commit is open:\n"
        "    PYTHONPATH=team-kits python -B -m kernel.cli --root %s evidence \\\n"
        "        --kind review --result pass --related <ITEM-ID> \\\n"
        "        --summary \"verifier PASS for %s\" \\\n"
        "        --artifact-ref <path/relative/to/%s> \\\n"
        "        --run-command \"<the line the verdict was produced by>\" \\\n"
        "        --run-scope <full|selection>\n"
        "(PowerShell: $env:PYTHONPATH=\"team-kits\"; python -B -m kernel.cli --root %s evidence "
        "...)\n"
        "The digest moves with the package, so run `python tools/bump_kit_version.py` BEFORE "
        "recording the verdict, not after."
        % (token, _harness.STATE_ROOT, _harness.STATE_ROOT, token, _harness.STATE_ROOT,
           _harness.STATE_ROOT),
        note=compat.unresolved_verb_note(command))


if __name__ == "__main__":
    _harness.guarded(decide)
