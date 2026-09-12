#!/usr/bin/env python3
"""
PreToolUse(Bash|PowerShell) gate — protects merge and push.

Teeth that answer different questions, in the order a role is best told them: may this history be
rewritten at all, who authorised the work, is the item in a state a delivery can follow, and what
does QA currently say about it.

FORCE-PUSH is refused unconditionally. The constitution forbids rewriting published history and
no project state can make it right, so this half decides before anything is read.

MERGE/PUSH NEEDS QA EVIDENCE — and in V2 that is a different sentence than it was. V1 looked for
`project_memory/*report*.yaml`, i.e. "whichever report file happens to be there", and matched
text inside it. Nothing in V2 writes such a file, so the gate had stopped being a QA rule and had
become an unconditional block on every merge and push in a scaffolded project (measured; phase-0
disposition rows 115/338/507). V2 has a typed store for exactly this question — Evidence
(spec II.2: a test/review/acceptance/audit record that carries no project status of its own),
living in `kernel.backlog_types.ACTIVE_DIRS["EVD"]` — and `kernel.report` is the ONE definition of
what that store SAYS. What this gate adds is only the DECISION taken on it (below); reading the
store for itself would give the harness two answers to the question the harness and CI must answer
the same way.

WHO AUTHORISED THE WORK is asked before any of that, and it is one question rather than the whole
approval protocol: an approval a PROGRAM minted through the Agent SDK does not carry a merge
(`_refuse_an_authorisation_a_program_gave_itself`, FR-0083). Whether an approval exists at all, and
whether it still binds, stays with the kernel and with the gates that own it.

THE RULE, in one sentence: the merge opens when every item it is about could still be delivered,
has a current verdict from EVERY delivery-judging Evidence kind, and has no current verdict that is
a fail or a `blocked`. "Current verdict of a kind" is the newest Evidence of that kind covering the
item — see
`report.qa_verdicts` for why newest-wins rather than any-pass-wins, and for what "covering" means.
"Every kind" is `backlog_types.QA_EVIDENCE_KINDS`, read at run time and never listed here, so the
gate owes exactly what the kernel calls a delivery verdict.

WHAT THE MERGE IS ABOUT is every root item the git invocation NAMES, and the gate requires all of
them rather than picking one. Picking would need a rule for which token is the ref being merged,
i.e. knowledge of which options carry a value, and that rule is one option away from wrong: the
first cut read the first id anywhere in the raw command, so `git merge -m "see PR-0002"
feat/PR-0001-x` judged PR-0002 and merged a failing PR-0001 (measured, audit finding of round 7).
Requiring every named item is the fail-closed reading of the same text: a merely mentioned id adds
a requirement, it can never substitute for one. Which text that reading is taken over is decided
by shell syntax rather than by a word list, and `_compat.git_argument_text` is that definition: a
`#` comment and everything past a `&&`/`|`/`;` was never handed to this git command, while a
QUOTED span WAS — quoting changes how the shell splits words, not what git receives, so the ref in
`git merge "feat/PR-0001-x"` counts exactly as the bare spelling does. (There was once a second
reader that deleted quoted spans as prose to answer "is this line a git invocation at all";
borrowing it for THIS question unbound every quoted merge, and answering the OTHER question with
it deleted the verb — `git "push" --force origin main` matched no gate whatsoever. Both are gone:
applicability is now read off the SUBCOMMAND, `_compat.git_invocations`.) A ref the shell only
builds at run time (`git merge "$B"`) is one no reading of the text can resolve, so it widens the
search to the whole line instead of being read as "this merge names nothing".

Every tooth the V1 gate had is kept, including the false accept an audit found — an old PASS for
another item together with a fresh FAIL for this one lifting the gate. That was possible because
binding was a text match inside one shared file. In V2 each Evidence is its own item with a
`related` field, so once an item could be determined, evidence for another item is not read as
evidence for this one. The qualifier is load-bearing: when NO item could be determined the gate
falls back to the whole store (below), and there the binding is only as specific as the branch
name.

Two situations are handled deliberately rather than by the main rule:
  * NO ROOT ITEM YET (`_root.has_root_item`) — the gate does not apply at all. A repo before
    its first PR/RQ is still being set up, and a quality gate firing there blocks the setup it
    exists to protect. "No root item" means the directory answered; a canonical directory that
    exists and refuses to be listed is not an answer, and that predicate says so — otherwise a
    permission problem would switch off this gate and four others.
  * NO ITEM NAMED (no id in the command, none in the branch name) — the gate still applies, but
    it has nothing to bind evidence to, so it asks the weaker question the store can still answer:
    is anything currently failing, ANYWHERE. Refusing outright for the missing binding would block
    every push on a branch that is not named after an item, which is most of them; that would move
    the V1 blockage rather than remove it. Naming the item in the branch is what makes the gate
    specific — unnamed, a green run on one item does not silence another item's open FAIL, but
    neither does this gate know which of them the push carries.
    THE COMPLETENESS HALF IS NOT ASKED HERE, and the limit is stated rather than left to be
    discovered: with no item, "every kind has answered" has no subject, and demanding it per
    subject over the whole store would refuse every push while ANY item in the project is still
    mid-flight — the V1 blockage in a new spelling. So an unnamed merge is judged on open failures
    alone, which is strictly weaker than the named case. Naming the item is what buys the strict
    reading; nothing in this gate makes an unnamed push carry it.
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

import re  # noqa: E402

import _compat  # noqa: E402
import _root  # noqa: E402

HOOK = "gate_git"

# The item a merge/push can be ABOUT: a root item id, spelled in the command or in the branch
# name. Assembled from `_root.ROOT_ITEM_TYPES`, so a kit that introduces a root type reaches this
# gate with it instead of leaving a third place for someone to remember. `\d{4,}` is the id
# convention (`kernel.backlog_types.parse_id`) — which is also what stops a leftover V1 `PRD-0001`
# branch from half-matching and being treated as a `PR`.
TARGET_RX = re.compile(r"\b(?:%s)-\d{4,}\b" % "|".join(_root.ROOT_ITEM_TYPES), re.IGNORECASE)

# Force-push in every spelling. BOUND, not copied: this is `_compat.names_force_push` itself, and
# the name exists here because a gate should say under its own roof which rule it decides on. The
# definition moved out of this file because `gate_git` is not installed in the office kit, and a
# rule that kit also needs cannot live in a module it never runs — see `_compat.FORCE_PUSH_RX` for
# the two readings and for what the over-trigger costs.
names_force_push = _compat.names_force_push

# A ref the shell EXPANDS at run time — `$B`, `${B}`, `$(git …)`, `$env:B`, `%B%` — is a ref this
# gate cannot read, and "cannot read" must not become "names nothing". Seeing one means the item is
# spelled somewhere the segment does not show, so the search widens to the whole line, where
# `B=feat/PR-0001-x; git merge "$B"` does spell it. Widening only ADDS requirements, which is the
# same fail-closed direction as collecting every named id in the first place.
EXPANSION_RX = re.compile(r"\$\w|\$\{|\$\(|%\w+%")


def target_items(command, repo_root):
    """Every root item this merge/push is about, as a sorted list; empty when it names none.

    Read from the git invocation — see the module docstring for why this collects rather than
    picks, and why the reading keeps quoted argument text. The command wins over the branch:
    `git merge feat/PR-0002-x` run while standing on `feat/PR-0001-x` is about PR-0002, and reading
    the branch first would judge the wrong item. The branch is consulted only when the command
    names nothing at all.
    """
    text = _compat.git_argument_text(command)
    named, unresolved = set(), False
    for invocation in _compat.git_invocations(command):
        if invocation.runs("push", "merge"):
            named.update(match.group(0).upper()
                         for match in TARGET_RX.finditer(invocation.segment))
            unresolved = unresolved or EXPANSION_RX.search(invocation.segment) is not None
    if unresolved:
        named.update(match.group(0).upper() for match in TARGET_RX.finditer(text))
    if not named:
        named.update(match.group(0).upper()
                     for match in TARGET_RX.finditer(current_branch(repo_root)))
    return sorted(named)


def current_branch(repo_root):
    """The branch HEAD is on, or "" when there is none to read.

    A function because TWO rules need the same answer and they must not disagree about it: which
    item a line is ABOUT when the command names none (`target_items`), and where a bare `git push`
    would land (`_destinations_of`). It was inline in the first of those until the BUG-0081 round,
    and the second one reading it separately is how the two would drift.
    """
    try:
        return _compat.run_captured(
            ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"], timeout=5).stdout or ""
    except Exception:  # noqa: BLE001 — no git, detached head, timeout: simply no branch name
        return ""


def _describe(subject, verdicts):
    return "%s: %s" % (subject, ", ".join(
        "%s %s (%s)" % (kind, verdicts[kind]["result"], verdicts[kind]["id"])
        for kind in sorted(verdicts)))


def _blocked(types, verdicts):
    """The current verdicts whose run did not happen at all — {kind: entry}, empty when none.

    `types.BLOCKED_RESULT`, asked of the kernel at run time like every other vocabulary this gate
    decides on. The entry already carries the sentence that says WHAT stopped the run
    (`report._newest_per_kind`), so this gate never re-reads the Evidence store to say it.
    """
    return {kind: entry for kind, entry in verdicts.items()
            if entry.get("result") == types.BLOCKED_RESULT}


def _refuse_a_run_that_never_happened(types, subject, blocked):
    """Refuse on a `blocked` verdict, and say that nothing was checked (FR-0082).

    THE SAME DECISION AS A FAIL and a different sentence. Both close the merge -- everything that
    is not `types.PASSING_RESULT` does, which is why this function decides nothing the fail branch
    would not have decided. What it changes is what the role is told: a `fail` says the work is
    red and sends the role to fix it, while a `blocked` says the run never ran, so "fix what the
    Evidence names" would send it looking for a defect nobody measured.

    WHAT THE SENTENCE IS WORTH, and the gate says it out loud rather than implying it: the kernel
    does not verify that the browser was really missing (`backlog_types.EVIDENCE_RESULTS`). A
    `blocked` is an honest role's record of an unrun check, not a measurement of one -- so the
    surface that reports it names the claim as a claim.
    """
    _kernel.block(
        HOOK,
        "the current QA verdict records a run that did NOT happen — %s. Nothing was checked: "
        "%s. A blocked verdict closes this merge exactly as a failing one does, and the "
        "harness does not verify the reason — it is what the recording role stated."
        % (_describe(subject, blocked),
           "; ".join("%s (%s): %s" % (kind, blocked[kind]["id"],
                                      blocked[kind].get(types.BLOCKED_REASON_FIELD)
                                      or "<no sentence recorded>")
                     for kind in sorted(blocked))),
        remedy="remove what blocked the run and record the run that then HAPPENED (`python "
               "scripts/harness.py evidence --kind <test|review|acceptance> --result pass "
               "--related %s --summary ... --artifact-ref <path to the raw proof>`); the newer "
               "verdict supersedes this one. If the run cannot be made to happen here, that is "
               "the merge arriving early — say so to the user rather than re-recording the same "
               "block." % subject + _FROM_THE_ROOT)


# Every remedy below hands a blocked role a command line, and since the entry point shipped that
# command line RUNS: the scaffold installs `scripts/harness.py` kit-owned in every project
# (`kernel.cli.ENTRY_POINT`), and `python scripts/harness.py evidence ...` was measured recording
# an Evidence through all eight PreToolUse gates and opening the merge this gate had closed. What
# this constant used to carry — that no installation provided the command — came out with the
# shim. What replaces it is the only thing the command still needs from the role: WHERE to run it
# and which argument not to add. Both halves are measured refusals, not caution.
_FROM_THE_ROOT = (
    " Run it from the project root: the entry point resolves the state directory itself, and a "
    "`--root` argument is refused twice over — by `gate_write_scope`, because a write-capable "
    "pipeline that NAMES the state directory is refused, and by the entry point, which reads the "
    "flag off its own parser and says so.")


def _evidence_home(types):
    return "%s/%s" % (_kernel.STATE_DIRNAME, types.ACTIVE_DIRS["EVD"])


def _remedy(target):
    return ("fix what the Evidence names, then have QA record the re-run (`python scripts/harness.py evidence "
            "--kind <test|review|acceptance> --result pass --related %s --summary ... "
            "--artifact-ref <path to the raw proof>`). Recording the newer verdict is what "
            "supersedes the old one — the kernel refuses to EDIT an Evidence, because a verdict "
            "changed in place leaves no item behind to notice. Archiving the failing Evidence is "
            "equally visible in git, but it retires a verdict without REPLACING it: the merge then "
            "opens only if an older passing Evidence of that same kind is left to become the "
            "current verdict, and with none left the kind is simply unanswered and this gate stays "
            "closed on that. So archiving belongs after a newer run, not instead of one. The proof "
            "itself goes under %s/staging/<task-id>/."
            % (target or "<ITEM-ID>", _kernel.STATE_DIRNAME)) + _FROM_THE_ROOT


def _refuse_a_status_no_delivery_can_follow(state, types, target):
    """Refuse a merge ABOUT an item whose own automaton says there is no delivery to merge.

    The type-appropriate half of the binding (disposition rows 115/343: "branch↔item + a status
    appropriate to the TYPE"). Which statuses those are is read off the item's automaton instead
    of being named here, so a kit that adds a root type brings the rule with it:

    * the INITIAL status is the draft in which the item is still being written. Nothing has
      authorised work on it — the dispatch gate will not even lease a task for it — so a merge
      claiming to deliver it is delivering something the project has not agreed to.
    * a TERMINAL status that is NOT the end of the chain is a life that ended without delivery
      (REJECTED, SUPERSEDED). The project decided against this work; merging it ships what was
      dropped. The chain's own last status is the opposite case — the delivery having been
      accepted — so a later fix merged against it is legitimate and is left alone.

    An id that names no item is not judged here: it binds to nothing, which is precisely what the
    evidence half below refuses it for, with the more useful message.
    """
    item, _archived = state.read_anywhere(target)
    if not isinstance(item, dict):
        return
    try:
        item_type, _number = types.parse_id(target)
    except ValueError:
        return
    automaton = types.AUTOMATA.get(item_type)
    if automaton is None:
        return
    status = item.get("status")
    if status == automaton.initial:
        _kernel.block(
            HOOK,
            "%s is still %s — nothing has approved this work, so there is no delivery to merge."
            % (target, status),
            remedy="obtain the user's approval for %s first (`python scripts/harness.py "
                   "request-approval scope %s`, relay the question verbatim) — the MINT walks "
                   "this transition itself, so there is no `transition` to run afterwards and the "
                   "kernel refuses one. If this merge is not about %s, name the item it IS about "
                   "in the branch." % (target, target, target))
    if status in automaton.terminals and status != automaton.chain[-1]:
        _kernel.block(
            HOOK,
            "%s is %s — the project closed this item without delivering it, so merging it ships "
            "work that was dropped." % (target, status),
            remedy="if the decision changed, that is a new item (a `CR` against the root, or a "
                   "fresh root item) — a reopened terminal status is not a transition the "
                   "automaton has. If this merge is about something else, name that item in the "
                   "branch.")


def _refuse_an_authorisation_a_program_gave_itself(state, approvals, target):
    """Refuse a merge/push about an item whose PRESENTED approval a program minted (FR-0083).

    THE HALF OF THE PROPERTY THAT BELONGS TO A GATE. The kernel keeps a program from minting a
    permission the project cannot take back at all (`approvals.IRREVERSIBLE_KINDS`); what it may
    mint are the decisions a project can revisit inside itself -- the scope of a goal, its
    delivery. A merge is where such a decision stops being internal: it is the line after which
    the work is in the branch other clones pull. So the question this gate asks is not "is there
    an approval" -- that is the evidence teeth's and the dispatch gate's question -- but "was the
    one this item PRESENTS given by a human".

    ASKED OF THE KERNEL (`approvals.presented_approval_a_program_minted`), like every other
    approval question a hook decides on: a second reading of `approval_ref` and the provenance
    field here would be a second answer to a question `gate_push_token` and the dispatch route
    already take from that module.

    WHAT IT DOES NOT REACH, stated because the honest limit is narrow: an item that presents NO
    approval, and an approval written before the provenance field existed, both read as
    not-programmatic -- the first is the neighbouring refusal's subject, the second is what
    `approvals.minted_via` says about a record from before the stamp.
    """
    item, _archived = state.read_anywhere(target)
    if not isinstance(item, dict):
        return
    apr = approvals.presented_approval_a_program_minted(state, item)
    if apr is None:
        return
    _kernel.block(
        HOOK,
        "%s stands on approval %s, and a PROGRAM minted it (Agent SDK, canUseTool) — not a "
        "human. A merge or push is where a decision this project could still revisit becomes one "
        "it cannot: it puts the work into the branch other clones pull. So this line needs an "
        "authorisation a person gave." % (target, apr.get("id")),
        remedy="ask the user for the approval through the approval question (`python "
               "scripts/harness.py request-approval %s %s`, relayed verbatim), then merge. If "
               "this run has no human to ask, that is the answer: the merge is not this run's to "
               "make." % (apr.get("kind"), target))


# WHICH QA KIND HAS NO SUBJECT UNTIL THE WORK IS PUBLISHED (BUG-0081).
#
# The Canyon case, live 2026-08-31: a Shopify theme's acceptance check can only run against pages
# RENDERED in a preview theme, and the preview theme is created BY the first push of the work
# branch. The gate demanded the acceptance verdict before that push, the PM refused to fake it and
# refused to edit the gate -- both correct -- and then asked the USER to run the push from his own
# terminal. A gate whose only exit is the user's hand is the gesture the gates exist to prevent.
#
# WHAT WAS WRONG WAS THE OCCASION, NOT THE DEMAND, and that is why nothing here is packaging-
# specific: a push whose DESTINATION is a work branch is not a delivery. It publishes unfinished
# work -- that is what a work branch is for -- while delivery is the MERGE, and a push to the
# TRUNK, which this file gates unchanged either way. So the distinction is one the gate can make
# out of what is on the line (`_destinations_of` plus `TARGET_RX`), and it needs no
# `packaging.method` list, no new field and no second vocabulary. A theme preview, a mobile build
# a store has to install, a staging deployment: all the same shape, none of them enumerated.
#
# THE DESTINATION AND NOT THE BRANCH YOU STAND ON. The first cut of this rule asked `target_items`,
# which answers "which item is this line about" -- it scans the segment and falls back to the
# current branch -- and three lines that deliver to the trunk answered "a work branch" with it:
# `git push origin HEAD:main`, `git push origin feat/PR-0001-x:main` and `git push --all origin`,
# all rc 2 before the softening and rc 0 after it (measured on a scaffolded pilot, verification
# round 1 F1).
#
# AN ENUMERATION WITH A TRIPWIRE AT BOTH ENDS, because this one cannot be derived from anywhere
# else: `tools/test_hooks.py::test_the_kind_outstanding_at_a_work_branch_push_is_a_real_qa_kind`
# measures that every name here is a QA kind the kernel has (a dead entry says so) and that it is a
# PROPER subset (an entry added for every kind would switch the rule off and say so).
OUTSTANDING_UNTIL_PUBLISHED = frozenset(("acceptance",))


# What a push option does to the DESTINATION, when the destination is the whole question.
#
# `--all`, `--mirror` and `--tags` push refs the line does not name -- every branch, the whole ref
# space, every tag -- so no reading of the positionals can say where they land, and one of the refs
# they carry is the trunk. `--delete` removes a ref instead of publishing to it, which is not the
# act this softening is about either.
#
# AN ENUMERATION, and it is one this gate cannot derive: git's option table is git's. Its tripwire
# is `tools/test_hooks.py::test_every_push_option_that_spreads_past_its_refspecs_is_refused_the_softening`,
# which drives each spelling through the running gate, so an entry that stops mattering and a
# spelling git adds are both a failing row rather than a silent pass.
_SPREADS_PAST_ITS_REFSPECS = frozenset((
    "--all", "--mirror", "--tags", "--follow-tags", "--delete", "-d"))

# Push options that EAT THE NEXT WORD, so that word is neither the remote nor a refspec. Without
# them `git push -o ci.skip origin feat/PR-0001-x` reads `ci.skip` as the remote and the real
# remote as a refspec -- a misreading toward MORE softening, which is the wrong direction. The
# options that take a value only as `--flag=value` (`--force-with-lease`, `--force-if-includes`)
# are deliberately absent: they never consume a separate word, and the `=` form is handled by the
# name split above. `-u`/`--set-upstream` take nothing at all.
_PUSH_OPTIONS_WITH_A_VALUE = frozenset((
    "-o", "--push-option", "--repo", "--receive-pack", "--exec"))


def _destinations_of(invocation):
    """(the refs this push WRITES TO, whether it spreads past them) -- BUG-0081's F1.

    THE DESTINATION IS THE QUESTION, and the first cut of this rule asked a different one. It read
    `target_items`, which scans the whole segment for an item id and otherwise falls back to the
    branch HEAD is on -- so `git push origin HEAD:main`, `git push origin feat/PR-0001-x:main` and
    `git push --all origin` all answered "a work branch", because the SOURCE side named the item or
    the current branch did. All three were rc 2 before the softening and rc 0 after it, measured on
    a scaffolded pilot with review and test verdicts and no acceptance. A push to the trunk is a
    delivery however the branch you are standing on is called.

    A refspec's destination is what stands after the colon, and a refspec without one pushes to the
    ref of the same name. A leading `+` is a force marker and not part of the name -- stripped here
    as a belt and not as a claim about anything that arrives: the force-push ban above refuses
    every `+refspec` before this reader is reached (measured, `git push origin +feat/PR-0001-x:main`
    is rc 2 with the force-push reason). A push with NO
    refspec at all lands on the current branch's upstream, which git's own `simple` default makes
    the like-named remote branch -- so the caller supplies the current branch for that case, and
    the LIMIT is named rather than hidden: a project configured `push.default = matching` or an
    upstream deliberately given another name is not read here, and the answer is then the branch
    name rather than the true ref.
    """
    arguments, destinations, spreads = list(invocation.arguments), [], False
    expect_value, seen_remote = False, False
    for token in arguments:
        word = str(token).strip("\"'")
        if expect_value:
            expect_value = False
            continue
        if word.startswith("-"):
            name = word.split("=", 1)[0].lower()
            if name in _SPREADS_PAST_ITS_REFSPECS:
                spreads = True
            elif "=" not in word and name in _PUSH_OPTIONS_WITH_A_VALUE:
                expect_value = True
            continue
        if not seen_remote:
            seen_remote = True          # the repository, not a ref
            continue
        refspec = word.lstrip("+")
        destinations.append(refspec.split(":", 1)[1] if ":" in refspec else refspec)
    return destinations, spreads


def _publishes_a_work_branch(command, targets, repo_root):
    """Is this line a PUSH whose DESTINATION names the work it carries, rather than a delivery?

    Three halves, and each is read off something that is on the line or under it. NO MERGE may be
    in the line -- `git push && git merge main` is a delivery with a push in front of it, and a
    reading that looked only for the push would hand the whole line the lighter rule. NOTHING may
    spread past the refspecs (`_SPREADS_PAST_ITS_REFSPECS`). And EVERY DESTINATION must NAME an
    item: the trunk names none, so this cannot soften a push to it under any spelling, and a ref
    that names an item is by construction the place unfinished work for that item is published to.

    The item-naming test is `TARGET_RX`, the same reader `target_items` decides with, so "a ref
    that names an item" is one fact here and there. `targets` still has to be non-empty because the
    caller needs an item to speak about; a line whose destination names one always gives it one.
    """
    invocations = list(_compat.git_invocations(command))
    if not targets or not invocations:
        return False
    standing_on = None
    for invocation in invocations:
        if not invocation.runs("push") or invocation.runs("merge"):
            return False
        destinations, spreads = _destinations_of(invocation)
        if spreads:
            return False
        if not destinations:
            if standing_on is None:
                standing_on = current_branch(repo_root)
            destinations = [standing_on]
        if not all(TARGET_RX.search(str(ref)) for ref in destinations):
            return False
    return True


def _say_what_stays_outstanding(target, outstanding):
    """Not a refusal and not silence: the kind is named as owed, and the audit line says so.

    A gate that simply stood down here would leave the acceptance verdict owed by nobody until the
    merge refused it much later. This is the only channel a PreToolUse gate has for that -- it may
    not write state, and the marker BUG-0081 AC-2 asks the validator to show needs a stored field
    with a producer (the BUG-0054 class), which is named as not closed rather than implied here.
    """
    message = (
        "%s is pushed WITHOUT the %s verdict, and this gate is letting it through: a work-branch "
        "push publishes unfinished work, and for this item the %s check has no subject until it is "
        "published (BUG-0081). It stays OWED -- the merge refuses without it."
        % (target, "/".join(sorted(outstanding)), "/".join(sorted(outstanding))))
    _kernel.record_note(HOOK, message)
    sys.stderr.write("[team-kit note] %s\n" % message)


def _refuse_unless_the_item_is_green(types, target, verdicts, publishing=False):
    """The main rule for ONE item: a current verdict of EVERY delivery-judging kind, none a fail.

    "Every kind" is `types.QA_EVIDENCE_KINDS`, asked of the kernel at run time. Not a tuple here,
    and that is the whole point of taking it from there: it is the same set
    `report._delivery_evidence` filters the store with, so a kind the kernel starts calling a
    delivery verdict is owed the day it exists, instead of becoming a verdict a role records in
    good faith and no merge ever waits for.

    WHY COMPLETENESS rather than "at least one". The kinds ask different questions — today,
    whether the work was read, whether the suite was run, whether the criteria were walked one by
    one — and under the weaker rule any one answer stood in for the others: a merge opened on a
    green test run that no reviewer had looked at, and on a reviewer's nod with no suite behind
    it. The QA/reviewer role skill of the kit this hook ships in is where the role is told which
    kinds it owes; this is the same demand at the moment it is collected.

    A `fail` is reported BEFORE a blocked run and both before an unanswered kind, so a role that
    has one of each is sent to fix the red verdict first and meets the next refusal on the next
    attempt. Deliberate: the three are different work -- a measured defect, a check that never ran,
    a verdict nobody recorded -- and one message that mixed them would bury the failing verdict.

    WHAT IT DOES NOT REACH is decided one caller up in `main`: only a merge that NAMES a root item
    reaches this function at all (module docstring, NO ITEM NAMED).
    """
    blocked = _blocked(types, verdicts)
    failing = {kind: entry for kind, entry in verdicts.items()
               if entry["result"] != types.PASSING_RESULT and kind not in blocked}
    if failing:
        _kernel.block(
            HOOK,
            "the current QA verdict is not a pass — %s. A newer Evidence of the same kind "
            "supersedes an older one, so this is what QA says about the work RIGHT NOW."
            % _describe(target, failing),
            remedy=_remedy(target))
    if blocked:
        _refuse_a_run_that_never_happened(types, target, blocked)
    if not verdicts:
        _kernel.block(
            HOOK,
            "no QA Evidence for %s — nothing in %s judges this work, so there is no proof to "
            "merge on (spec II.10a: a partial run is not merge evidence either)."
            % (target, _evidence_home(types)),
            remedy="run the QA gate and have the reviewing role record the outcome as an Evidence "
                   "item: `python scripts/harness.py evidence --kind <test|review|acceptance> --result pass "
                   "--related %s --summary ... --artifact-ref <path to the raw proof>`." % target
                   + _FROM_THE_ROOT)
    unanswered = sorted(set(types.QA_EVIDENCE_KINDS) - set(verdicts))
    # A WORK-BRANCH PUSH IS NOT A DELIVERY (BUG-0081). Only the kinds whose subject does not exist
    # until the work is published stand down, and only for a push -- a failing or blocked verdict
    # above still refuses, and the merge below still asks for all of them.
    if publishing and unanswered:
        outstanding = [kind for kind in unanswered if kind in OUTSTANDING_UNTIL_PUBLISHED]
        unanswered = [kind for kind in unanswered if kind not in OUTSTANDING_UNTIL_PUBLISHED]
        if outstanding and not unanswered:
            _say_what_stays_outstanding(target, outstanding)
    if unanswered:
        _kernel.block(
            HOOK,
            "QA has judged %s only in part — %s, and no %s Evidence covers it at all. Each kind "
            "answers a question the others do not, so a delivery merge rests on all of them (%s); "
            "an unanswered kind is work not finished, not a verdict to leave out."
            % (target, _describe(target, verdicts), "/".join(unanswered),
               ", ".join(sorted(types.QA_EVIDENCE_KINDS))),
            remedy="have the judging role record the missing verdict — one Evidence per kind, each "
                   "naming the run that produced it: `python scripts/harness.py evidence --kind "
                   "<test|review|acceptance> --result pass --related %s --summary ... "
                   "--artifact-ref <path to the raw proof>`. A kind that cannot be answered yet is "
                   "the merge arriving early; it is not this gate to route around." % target
                   + _FROM_THE_ROOT)


def _refuse_unless_nothing_is_failing(types, by_subject):
    """The fallback for a merge that named no item: no OPEN failure anywhere in the store.

    Per (item, kind), never collapsed to one newest-per-kind for the whole project. Collapsing
    would rebuild the V1 false accept out of typed items: the newest verdict in the store is some
    item's, and if it is green it would speak for an unrelated item whose own FAIL is still open.
    Since this branch cannot tell which item the push carries, the only honest reading is that
    every open failure counts against it.
    """
    failing, blocked = {}, {}
    for subject, verdicts in by_subject.items():
        for kind, entry in verdicts.items():
            if entry["result"] == types.BLOCKED_RESULT:
                blocked.setdefault(subject, {})[kind] = entry
            elif entry["result"] != types.PASSING_RESULT:
                failing.setdefault(subject, {})[kind] = entry
    if failing:
        _kernel.block(
            HOOK,
            "this merge names no item — not in the command and not in the branch — so the gate "
            "cannot tell which work it carries, and QA currently reports a failure: %s."
            % "; ".join(_describe(subject, failing[subject]) for subject in sorted(failing)),
            remedy="name the item in the branch (`feat/PR-0001-…`) so the gate judges that item "
                   "alone, or clear the failing verdict by recording the re-run "
                   "(`python scripts/harness.py evidence --kind <test|review|acceptance> --result pass --related "
                   "<ITEM-ID> --summary ... --artifact-ref <path to the raw proof>`)."
                   + _FROM_THE_ROOT)
    # The same order as the named case, and the same reason: a measured defect outranks a check
    # that never ran. `subject` here is whatever the Evidence named, since this branch has no item.
    for subject in sorted(blocked):
        _refuse_a_run_that_never_happened(types, subject, blocked[subject])
    if not by_subject:
        _kernel.block(
            HOOK,
            "no QA Evidence in this project — nothing in %s judges any work, so there is no "
            "proof to merge on (spec II.10a: a partial run is not merge evidence either)."
            % _evidence_home(types),
            remedy="run the QA gate and have the reviewing role record the outcome as an Evidence "
                   "item: `python scripts/harness.py evidence --kind <test|review|acceptance> --result pass "
                   "--related <ITEM-ID> --summary ... --artifact-ref <path to the raw proof>`; "
                   "name the item in the branch too, so the next merge is judged on it alone."
                   + _FROM_THE_ROOT)


def main():
    # No `hook_event_name` guard: this gate is registered on PreToolUse and nowhere else, so the
    # event is settled by settings.json. Re-checking a field a provider may omit would turn the
    # gate into a silent exit 0.
    data = _kernel.payload(HOOK)
    if data.get("tool_name") not in ("Bash", "PowerShell"):
        sys.exit(0)
    command = str((data.get("tool_input") or {}).get("command") or "")
    # Detection lives in _compat.wants_push_or_merge (single home): applicability is decided on the
    # git SUBCOMMAND of a `git` word the shell would execute, so `git "push"`, `git pu''sh`,
    # `git pu\<newline>sh`, `git $'push'` and `sudo "git" push` are the push they are, a verb the
    # shell only builds at run time counts as every verb, and `git commit -m "merge later"` stays
    # a commit because its `merge` is inside an argument, not a word git was handed.
    if not _compat.wants_push_or_merge(command):
        sys.exit(0)

    if (any(invocation.runs("push") for invocation in _compat.git_invocations(command))
            and names_force_push(command)):
        # NAMES NO SOURCE DOCUMENT, and that is structural rather than a wording taste. This file
        # is byte-identical in the dev and research kits (the mirror rule), so a refusal that cites
        # "the team constitution" cites a DIFFERENT text in each of them and can be wrong in one
        # while right in the other -- measured after II.11/3 redeemed parity licence 30 for dev:
        # the dev constitution stopped naming force-push and this message still sent its reader
        # there. The one document a refusal may point at is appended by `_compat.stop` from
        # `_compat.REFERENCE_NAME`, ships inside the hashed bundle beside this hook, and does name
        # force-push. So the message states the FACT and lets that pointer carry the authority.
        _kernel.block(HOOK, "force-push is refused: it rewrites history other clones already have.",
                      remedy="push without --force; if history really has to be rewritten, that "
                             "is a user decision, not a task decision.")

    repo_root = _kernel.find_repo_root(data.get("cwd"))
    if not os.path.isdir(_kernel.state_dir(repo_root)):
        sys.exit(0)  # nothing to gate yet
    if not _root.has_root_item(repo_root):
        sys.exit(0)

    state = _kernel.open_state(repo_root)
    report = _kernel.kernel_module("report", repo_root)
    types = _kernel.kernel_module("backlog_types", repo_root)
    approvals = _kernel.kernel_module("approvals", repo_root)
    targets = target_items(command, repo_root)

    # WHO AUTHORISED THIS WORK IS ASKED BEFORE WHAT QA SAYS ABOUT IT, and the order is the
    # argument: an item nobody with standing approved is not a merge with a missing verdict, it is
    # a merge that should not be assembled at all -- so the role is told that first rather than
    # sent to collect evidence for work it may not merge either way.
    for target in targets:
        _refuse_an_authorisation_a_program_gave_itself(state, approvals, target)
    for target in targets:
        _refuse_a_status_no_delivery_can_follow(state, types, target)
    if targets:
        publishing = _publishes_a_work_branch(command, targets, repo_root)
        for target in targets:
            _refuse_unless_the_item_is_green(types, target, report.qa_verdicts(state, target),
                                             publishing)
    else:
        _refuse_unless_nothing_is_failing(types, report.qa_verdicts_by_subject(state))
    sys.exit(0)


if __name__ == "__main__":
    _kernel.run_gate(HOOK, main)
