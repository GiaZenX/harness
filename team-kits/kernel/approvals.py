"""Two-phase approval provenance (HARNESS_V2_SPEC.md II.2) -- step 1.4b.

A manual `approved_by: user` proves nothing. The kernel:
1. writes an immutable PENDING request (request_id, item, revision,
   content hash, kind, expiry, per-request MINT CODE) and generates the
   COMPLETE approval question deterministically -- text, header AND the three
   options, marker `[APR-REQ:<id>]` in the text
2. the PreToolUse hook (phase 2) enforces exact string equality of marked
   questions against `build_question`
3. `mint` creates the APR ONLY when the answer equals the kernel-generated
   approval label VERBATIM, including its per-request mint code
   (`Freigeben [7f3a2c]`); never for expired/mismatched requests; the item
   must still be at the requested revision AND content hash (out-of-band
   edits kill the mint)

MINT CODE, and why (empirical finding 2026-07-24, spike S2b): Claude Code
2.1.219 reports answers as `toolUseResult.answers = {question: answer_STRING}`
-- a clicked option and text typed into the always-present "Other" row are
INDISTINGUISHABLE (verified against real session transcripts). The spec's
original demand ("bind the token to the option identity, never the string")
is therefore not implementable on this platform. The mint code restores the
practical guarantee: the label carries per-request entropy that lives ONLY in
the option, so casual free text ("ok", "ja", "freigeben") can never mint.
Residual, documented honestly: a user who deliberately transcribes the code
mints -- but that user IS the approving authority, and the MODEL cannot
produce `answers` at all (the platform writes them, and the PreToolUse hook
pins the question the user saw).
The guarantee is CONDITIONAL on two things NEITHER library code NOR any
in-process check can establish (measured 2026-07-25, see
_assert_minting_caller): (i) only a RECOGNISED minting route reaches `mint` --
but the hook is meant to be run with a payload on stdin, so anyone able to
execute `python <hooks>/gate_approval.py < forged.json` mints, and the forged
payload is assembled from the readable pending request; and (ii)
`approvals/pending/` is kernel-only territory (the codes sit there in cleartext,
and the question text even names the path). BOTH need a Bash/PowerShell-level
guard, because `guard_harness_selfmod` gates only Edit|Write|MultiEdit. Until
that guard exists, `approval_provenance` is `unverified` and the enforcement mode
is `audited` -- and `python scripts/harness.py doctor` must compute that rather than assert it.

THERE ARE TWO ROUTES SINCE FR-0083, and (i) says "a recognised route" rather than
"the hook" for that reason: the approval hook, which means a human answered the
provider's question, and `kernel.sdk_approval`, which an embedding program calls
from the Agent SDK's `canUseTool` callback. Which one minted is STAMPED on the
approval (`MINTED_VIA_FIELD`) and read back by `approval_card`, because the
sentence "a token exists, so a human answered" stops holding the day a project
embeds the SDK. What the second route widens, and what still bounds it, is
measured and named as `H133` in `docs/POST_V2_WISHLIST.md`.

Bundling (user decision 2026-07-24): one analysis/scope APR may cover several
analysis tasks LISTED in its subject manifest.
"""
from __future__ import annotations

import inspect
import os
import posixpath
import re
import sys
import time
import unicodedata
import uuid

from .backlog_types import (
    AUTOMATA,
    HASHED_FIELDS,
    HOLE_EXCEPTION_STATUS,
    HOLE_LIMIT_FIELD,
    HOLE_NUMBER_FIELD,
    ROOT_TYPE_BY_KIT,
    confirming_edge,
    is_terminal,
    parse_id,
)
from . import naming_tests
from .hashing import subject_manifest_hash
from .state import ProjectState, StateError, _now_iso, names_a_drive

APR_KINDS = ("analysis", "scope", "delivery", "acceptance", "routine", "push", "preset",
             "kit_update", "filing_correction", "filing_rule", "document_proposal",
             "document_revision", "plan", "hole_exception", "verification")
# THE KIND IN THE USER'S WORDS (BUG-0271, PR-0011 AC-7): what `build_question` puts where the enum
# value used to stand -- "Freigabe erbeten: scope für PR-0001" asked a non-developer to sign an
# English field value. ONE table beside the enum, read by the question and by nothing else, with a
# two-sided tripwire: a kind without a label and a label without a kind are both red
# (`tools/test_light_kit.py::test_every_approval_kind_has_one_plain_word_label_and_no_label_is_orphaned`).
# The labels say what is being permitted, not how the kernel files it.
KIND_LABELS = {
    "analysis": "Untersuchung (nur lesen)",
    "scope": "Arbeitsbereich",
    "delivery": "Lieferung",
    "acceptance": "Abnahme",
    "routine": "Dauer-Erlaubnis für eine wiederkehrende Prüfung",
    "push": "Veröffentlichung (Push)",
    "preset": "Teamgröße",
    "kit_update": "Kit-Aktualisierung",
    "filing_correction": "Ablage-Korrektur",
    "filing_rule": "Ablage-Regel",
    "document_proposal": "Dokument-Ergänzung",
    "document_revision": "Dokument-Überarbeitung",
    "plan": "Plan",
    "hole_exception": "Ausnahme für eine bekannte Lücke",
    "verification": "Abschluss behobener Fehler",
}
# THE MANIFEST KEYS IN THE USER'S WORDS, for the kinds whose manifest the generic branch of
# `build_question` renders key by key (a routine, an analysis, a kit update; every kind with a
# `TARGET_FORMS` entry writes its own sentence). A key this table does not know is rendered under
# its own name -- and `tools/test_light_kit.py::test_no_approval_question_shows_an_english_enum_word_a_hash_or_a_path`
# renders every kind and refuses an English key in the sentence, so a new manifest key arrives
# here or turns that test red.
MANIFEST_LABELS = {
    "role": "Rolle",
    "scope": "Lesebereich",
    "read_only_scope": "Lesebereich",
    "trigger": "Auslöser",
    "cadence": "Takt",
    "expires": "gültig bis",
    "question": "Frage",
    "expected_result": "erwartetes Ergebnis",
    "tasks": "Aufträge",
    "kit": "Kit",
    "from_version": "von Version",
    "from_content": "bisheriger Inhalt (Prüfsumme)",
    "to_version": "auf Version",
    "to_content": "neuer Inhalt (Prüfsumme)",
}
# The one line kind that HANGS FROM AN ITEM: a routine approval is built from flags (role, scope,
# trigger, cadence) and minted FOR a root, because `dispatch._covering_routine_apr` reads it off
# that root's approvals. `cli` treats it as both -- an item id AND the flags -- which no other kind
# is.
ROUTINE_KIND = "routine"
# THE USER ACCEPTING A MEASURED GAP (FR-0087, DEC-0073). A hole that will not be closed ends in
# `ACCEPTED_EXCEPTION`, and that ending is a USER statement about risk -- so it is bound to a mint
# and not to a status the apparatus can set for itself. A kind of its own rather than `scope`,
# because a kind binds exactly one edge and `scope` already binds BUG's TRIAGED -> APPROVED: one
# kind on two edges would let an approval given for a fix walk an item into an exception instead.
# Its manifest is item-derived (`item_subject_manifest`), so what the user signs is the gap's own
# description AND the sentence that says what limits instead.
HOLE_EXCEPTION_KIND = "hole_exception"
# THE PLAN-LEVEL APPROVAL (FR-0074). One answer for the confirmed list of product goals, after
# which the per-goal scope question is not asked again. Measured before it existed, over the
# shipped automata: a root goal carries THREE user approvals -- `scope`, `delivery`, `acceptance`
# -- so a plan of ten goals is thirty approval questions from the automaton alone, and the user
# counted them himself (FR-0074, Canyon audit 2026-08-30).
PLAN_KIND = "plan"
# THE ONE KIND A PLAN APPROVAL STANDS IN FOR, and it is a property rather than a preference: a
# plan approval can only answer the question the PLAN ITSELF answers -- "is this goal, with these
# acceptance criteria, wanted" -- because that is the content its manifest hashes. `delivery` and
# `acceptance` ask about work that has HAPPENED (their manifests name `planned_tasks`, `risks`,
# `delivered_commit`, `evidence_refs`), and no plan can settle that in advance. So the delivery
# side stays per goal, which is what FR-0074 (4) demands as the counterweight to the wider
# approval. Both ends are measured against the running manifests --
# `tools/test_approvals_dispatch.py::test_a_plan_can_only_stand_in_for_the_question_a_plan_answers`
# turns red both if this kind stops existing and if another kind ever becomes plan-derivable.
PLAN_COVERED_KIND = "scope"
# THE BATCH CLOSING OF REPAIRED DEFECTS (PR-0012 AC-1, decided in DEC-0100). Its predecessor
# settled the ROUTE -- a user mint
# per repaired bug, relayed in one sitting -- and left the COST where it was: the shipped chain
# TRIAGED -> APPROVED needs an approval per bug, so the ~100 defects this repo had already measured
# as repaired needed ~100 clicks and got none, and the stock went on lying upward by that many.
# This kind is that route's batch form and not a second route: the user still signs, the mint still
# walks every listed item through its own automaton (`_close_what_the_batch_lists`), and every
# listed bug still needs the passing test Evidence that names it (BUG-0090's rule, re-asked at mint
# time). What collapses is the number of QUESTIONS, not the number of proofs.
VERIFICATION_KIND = "verification"
# HOW MANY ITEMS ONE QUESTION MAY CARRY, and the number is a MEASUREMENT of the mint rather than a
# taste. TWO bounds meet here and the smaller one wins:
#   * READABILITY of the compared carrier -- the ids and their evidence ride in the APPROVING
#     OPTION's description (`_verification_option_form`), because that is the text `gate_approval`
#     compares character for character, so the whole list has to survive the provider's echo of one
#     option description. An entry is `BUG-nnnn (EVD-nnnn)`, ~20 characters.
#   * THE KERNEL LOCK'S CLOCK, which is the binding one: the whole walk runs inside ONE held lock
#     (`ProjectState(lock_ttl=...)`), and a run that outlives that TTL can have its lock broken as
#     stale by another kernel process -- `KernelLock.release` then raises `LockLost` over writes
#     that may have raced. The size was set from a process measurement of a batch this long against
#     a copy of the largest store this project has, at roughly half that TTL
#     (`project_memory/staging/TSK-0138/protocol.md`). NOT from the hook's budget, which is the
#     mistake the first cut of this comment made: a kit hook runs against
#     `_kernel.DEFAULT_WINDOW_SECONDS` minus its reserve, and the same batch spends about a
#     twentieth of that. The cost per defect GROWS with the Evidence store, because the coverage
#     walk recomputes an Evidence's ancestors once per target (`report.evidence_covers` ->
#     `state.read_anywhere`); the same protocol carries that as a measured, unclosed finding with
#     its route, and it is why the bound is a measurement to redo rather than a constant to trust
#     forever.
#     WHAT AN OVERRUN OR A KILL DOES NOT DO is lose the batch, and that was measured with a real
#     kill rather than hoped: the approval keeps covering every id it still lists, so `transition`
#     finishes them with no second question
#     (`tools/test_approvals_dispatch.py::test_a_batch_approval_stays_in_force_for_every_id_it_lists_after_the_minting_process_ended`).
#     A killed hook does leave the kernel lock behind; it ages out on its own TTL.
# RE-MEASURED 2026-09-12 (TSK-0140) on this repository's own store, which is the largest one
# this project has: a `verification` batch of SIX cost 34.7 s end to end, i.e. ~5.8 s per
# entry -- so ten entries land at roughly 58 s against the 60 s lock ttl the size was derived
# from. The number is therefore AT its bound rather than under it, and the cost per entry
# grows with the Evidence store (`report.evidence_covers` walks an Evidence's ancestors once
# per target). A batch that outlives the ttl does not lose the user's answer -- the approval
# keeps covering every id it lists -- but the walk has to be finished with `transition`. The
# `hole_exception` batch is cheaper per entry (no Evidence walk at all) and is not what this
# measurement bounds. Left at 10 deliberately: lowering it multiplies the questions, and the
# number to redo is this measurement, not the constant.
# ONE NUMBER, ONE PLACE: `tools/close_measured_pass.py` cuts its batches by importing this, and
# `verification_subject_manifest` refuses a longer one.
BATCH_LIMIT = 10
# kinds that are time-boxed rather than content-invalidated (spec II.2 APR field
# list: "expires (routine/analysis)")
# `push` expires like the others, and for the sharpest reason of the three: a
# push token that outlives its session is a standing permission to publish.
# `preset` on the same ground as `push` and one step further: what it authorises
# is the installation of the roles a project may spawn, i.e. a change to the
# enforcement layer itself (BUG-0041). An unused one that lingers is a standing
# permission to rewrite that layer, so it carries a clock like the other three.
# `kit_update` is the same argument at its strongest: it authorises REPLACING that
# layer -- hooks, kernel, settings and constitution -- with another release
# (FR-0006), and an unused one lingering past the conversation is a standing
# permission to do that.
# `filing_correction` for the same reason once more, and against the one wall a business archive
# has: it is the single door through which a document of record may leave its place or cease to
# exist at all (FR-0050). It is already bound to the document's own bytes, so the clock only bounds
# how long an UNUSED one lingers -- and an unused permission to delete an archived document that
# outlives the conversation it was given in is exactly the standing permission this kit refuses.
# `filing_rule` for the mirror-image reason: it authorises a WRITE into the one document that says
# where every future document belongs (FR-0049 step 5, `kernel.filing`), so an unused one lingering
# past the conversation is a standing permission to change the Aktenplan.
# `document_proposal` for the same reason across every remaining kit document (BUG-0071,
# `kernel.documents`): it is bound to one before-and-after, so the clock only bounds how long an
# UNUSED one lingers -- and that is a standing permission to write into the project's own
# configuration and reference documents.
# `document_revision` (FR-0067) for `document_proposal`'s reason and one step further: it is
# the only route that may REPLACE or DELETE something a kit document already records, so an
# unused one lingering past the conversation is a standing permission to unsay what the
# project decided.
EXPIRING_KINDS = frozenset(("routine", "analysis", "push", "preset", "kit_update",
                            "filing_correction", "filing_rule", "document_proposal",
                            "document_revision"))
# kinds that may authorise a specialist dispatch through the ROOT item's
# approval_ref ALONE, i.e. on nothing but the fact that the root presents them.
# analysis/routine deliberately excluded and NOT because they authorise nothing:
# they are read-only permissions bound to something OTHER than the root's content
# (II.2/II.3), so each has its own route in `dispatch` that checks that binding --
# the listed task for `analysis`, the role and the read-only scope for `routine`.
# Granting them the blanket route instead would authorise unlimited IMPLEMENTATION
# work under a still-DRAFT root, and because their manifests are not item-derived
# no content hash could catch an out-of-band edit of that root either.
# `plan` rides here for the same reason `scope` does and by the same route: it is the approval the
# root PRESENTS for the very question `scope` answers, so a root covered by a live plan approval
# authorises the same specialist dispatch a per-goal scope approval would. Leaving it out would
# build the plan approval and then refuse every task under the goals it covers.
ROOT_DISPATCH_KINDS = frozenset(("scope", "delivery", PLAN_KIND))

# WHAT A `routine` APPROVAL IS BOUND TO. Spec II.2: "`routine` (z. B. Auditor-Takt) ist gebunden
# an Rolle, Read-only-Scope, Trigger, Ablaufdatum und jederzeit widerrufbar"; II.10a: the approval
# "hasht Rolle, Read-only-Scope, Trigger, Takt und Ablaufdatum". `expires` is not in this tuple
# because `create_pending_request` puts it into the manifest itself for every EXPIRING_KIND -- it
# is the one field the caller must NOT be able to leave out or spell differently.
#
# REQUIRED AT CREATION, not merely read later, and that is the point of naming them here: a
# routine manifest that carries none of them is a standing permission bound to nothing, and the
# user would be asked to sign it. `dispatch` reads the same names back out of the MINTED request
# and fails closed on a missing one, so the two ends read one contract rather than two lists.
# The one of them a gate can act on -- the role a routine dispatch must be spawned as -- named
# once and then PART OF the contract below, so the key `dispatch` reads and the key
# `create_pending_request` demands cannot become two spellings of one field.
ROUTINE_ROLE_FIELD = "role"
ROUTINE_MANIFEST_FIELDS = (ROUTINE_ROLE_FIELD, "scope", "trigger", "cadence")
# The fifth thing II.10a hashes, and the one the CALLER does not write: `create_pending_request`
# puts it into the manifest itself for every EXPIRING_KIND, `proven_expiry` reads it back from
# there (the only tamper-evident copy), `mint` carries it into the APR as a display value, and the
# approval question renders it. Five readers of one key, spelled once.
EXPIRY_FIELD = "expires"
_CHANGE_LABEL = "Ändern"
_REJECT_LABEL = "Ablehnen"
# HOW MUCH OF A HASH A HUMAN IS SHOWN, in one place: `build_question` prints this many characters
# of the subject-manifest hash, and `_render_manifest_value` shortens a hashed VALUE to the same
# length so one question does not show two conventions. A digest is recognised by BEING one --
# hex, and at least as long as the shortest algorithm anything here uses (sha1) -- rather than by
# the field name carrying it, which would be a list that the next hashed field is missing from.
DIGEST_SHOWN = 12
_DIGEST = re.compile(r"\A[0-9a-f]{40,}\Z")

# THE TWO EXITS FROM A REFUSED MINT, in the language of the person who clicked. A branch picks the
# one its own situation allows; there is no third, and no branch may invent one (BUG-0039). Which
# one is NOT interchangeable: sending a user back to re-ask a question whose request is already
# gone is a loop, and that mismatch between a state and its advice is the defect TSK-0057/BUG-0036
# closed one report earlier. German because these strings are read by the user, like the approval
# question `build_question` writes a few functions down.
NEXT_ASK_AGAIN = ("Dein Assistent muss die Freigabe-Frage noch einmal stellen — unverändert, Wort "
                  "für Wort so, wie das Programm sie ausgibt.")
NEXT_START_OVER = ("Dein Assistent muss den Freigabe-Vorgang neu starten; diese Anfrage ist "
                   "verbraucht und kann nichts mehr freigeben.")


def approve_label(mint_code: str) -> str:
    """The ONE answer string that mints -- entropy-carrying by design."""
    return "Freigeben [%s]" % mint_code

# WHICH TRANSITION AN APPROVAL COMMITS, per (item_type, kind). Read forwards it is the status
# side-effect of a successful mint -- everything else only sets approval_ref (spec II.2/II.3).
# Read BACKWARDS it is the answer to "which transitions may only be walked when a user approved
# them", and `required_approval_kinds` reads it that way. One table, both directions: a pair added
# here arrives gated at `transition` with no second list to keep in step.
APPROVAL_TRANSITIONS = {
    ("PR", "scope"): ("DRAFT", "APPROVED"),
    ("RQ", "scope"): ("DRAFT", "APPROVED"),
    ("PR", "delivery"): ("APPROVED", "IN_DELIVERY"),
    ("RQ", "delivery"): ("APPROVED", "IN_DELIVERY"),
    ("PR", "acceptance"): ("DELIVERED", "ACCEPTED"),
    ("RQ", "acceptance"): ("DELIVERED", "ACCEPTED"),
    ("CR", "scope"): ("DRAFT", "APPROVED"),
    ("BUG", "scope"): ("TRIAGED", "APPROVED"),
    # THE SAME EDGE, ASKED FOR A LIST (PR-0012 AC-1). It is the identical transition `scope`
    # commits, which is what makes the batch form a form of the per-bug route (DEC-0100) rather than a
    # second route: `required_approval_kinds` reads this table backwards, so TRIAGED -> APPROVED
    # now answers "scope or verification", and everything downstream of it (the chain to VERIFIED,
    # the confirming Evidence) is unchanged.
    ("BUG", VERIFICATION_KIND): ("TRIAGED", "APPROVED"),
    ("BUG", HOLE_EXCEPTION_KIND): ("TRIAGED", HOLE_EXCEPTION_STATUS),
    ("PROC", "scope"): ("DRAFT", "APPROVED"),
    ("EXP", "delivery"): ("DESIGNED", "APPROVED"),
}

# fields hashed into the subject manifest per kind for ITEM-bound approvals
# (spec II.2 subject_manifest lists)
#
# WHAT THIS COVERS AND WHAT IT DOES NOT. A scope approval reads as "the user signed this item's
# content", and the honest question is how much of that content the manifest actually carries.
# `backlog_types.HASHED_FIELDS[item_type]` is the kernel's own answer to "which fields of this
# type are approval-relevant", so the coverage of a manifest is the overlap between the two --
# a DERIVATION, not a count, and the count this comment first carried ("for two types it does
# not") was wrong. Measured 2026-07-31 over all TEN (item type, kind) pairs in
# `APPROVAL_TRANSITIONS`: exactly two of them cover their type's hashed fields in full -- PR/scope
# 6 of 6 and RQ/scope 5 of 5 -- and the other EIGHT cover one field or none:
#   BUG/scope 1 of 5 . CR/scope 1 of 4 . PROC/scope 0 of 2 (steps, roles) . EXP/delivery 0 of 3 .
#   PR|RQ delivery and acceptance 0 of 6|5, because those manifests name fields (`risks`,
#   `delivered_commit`, ...) that no type's contract declares at all.
# `SR` is not in that list because it is in no pair: nothing approves an SR, which is the
# neighbouring finding in `required_approval_kinds`.
# The consequence is exact: a change THROUGH THE KERNEL still invalidates (`HASHED_FIELDS` bumps
# the revision, and the revision IS in every manifest), while an out-of-band edit past the kernel
# leaves the hash matching -- the one thing the content hash exists to catch. Widening this tuple
# is not a fix that can be slipped in: every stored hash would change and every live approval
# would die, so it is a spec decision with a migration attached. Named here so nobody reads the
# hash as wider than it is.
_SCOPE_FIELDS = ("problem", "goal", "question", "motivation",
                 "acceptance_criteria", "invariants", "out_of_scope",
                 "design_refs")


class ApprovalError(StateError):
    """Approval-protocol violation -- message carries the remedy.

    `user_text` is the SAME refusal addressed to the person who clicked, and it exists because the
    message above is addressed to a role: it names spec sections, file paths and request ids, and
    pilot 3 (BUG-0039) is what a user gets out of that -- nothing. The branch that refuses writes
    it, so the sentence is as specific as the branch is; the alternative, one text chosen by
    whoever reports the error, is the blanket reason BUG-0036 cost a round.

    Optional in the signature and NOT optional where it matters:
    `tools/test_hooks_v2.py::test_every_approval_refusal_the_hook_can_surface_speaks_to_the_user`
    derives the reachable raise sites from the approval hook's own calls and fails on one without.
    """

    def __init__(self, message, user_text=None):
        super().__init__(message)
        self.user_text = user_text


def _pending_dir(state: ProjectState) -> str:
    return os.path.join(state.root, "approvals", "pending")


def _consumed_dir(state: ProjectState) -> str:
    return os.path.join(state.root, "approvals", "consumed")


def _revoked_dir(state: ProjectState) -> str:
    return os.path.join(state.root, "approvals", "revoked")


def _request_path(state: ProjectState, request_id: str, consumed: bool = False,
                  revoked: bool = False) -> str:
    if revoked:
        base = _revoked_dir(state)
    else:
        base = _consumed_dir(state) if consumed else _pending_dir(state)
    return os.path.join(base, request_id + ".yaml")


def push_subject_manifest(remote: str, branch: str, head: str) -> dict:
    """R1 (parity row 29, a MINIMUM-KEEP rule): what a push approval is bound to.

    "Push nur nach expliziter Userfreigabe" was prose only, so it died with every
    context window. It is now the same two-phase protocol as an APR, with the
    same mint code -- Amendment 2026-07-24 records why the option IDENTITY cannot
    carry it (spike S2b: a clicked option and typed text are indistinguishable in
    the payload), so the entropy lives in the option LABEL.

    Bound to remote + branch + HEAD, which makes the token single-use without any
    "used" flag to keep honest: approve HEAD abc123, push it, and the next commit
    moves HEAD so the same approval no longer matches. Re-running the identical
    push is a git no-op, so nothing is lost by allowing it. The alternative --
    a consumed marker -- would be one more piece of writable state deciding an
    enforcement question, which is the mistake the ledger gate spent four rounds
    unlearning.
    """
    return {
        "remote": str(remote or ""),
        "branch": str(branch or ""),
        "head": str(head or ""),
    }


def preset_subject_manifest(preset: str, roles, removes) -> dict:
    """What a preset change is bound to: the OUTCOME the user is asked to sign (BUG-0041).

    The user is not shown a preset NAME and asked to trust it -- `duo` and `team` say nothing to
    the person pilot 3 measured. The manifest carries the resulting specialist set and, separately,
    the roles this project has installed that the new preset drops, because a downgrade takes work
    capacity away and that is the half a name hides completely.

    BOUND TO THE OUTCOME AND NOT TO THE STEP: `kernel.presets.change_manifest` derives these same
    three values from the kit staging and the installed role manifest, and `set-preset` re-derives
    them and refuses unless the hash still matches. So an approval signed for one role set cannot
    install another -- not after a kit staging changed underneath it, and not for a preset the
    user was never shown.
    """
    return {
        "preset": str(preset or ""),
        "roles": list(roles or []),
        "removes": list(removes or []),
    }


# THE OTHER HALF OF THE KIND SPLIT, and the reason B2 was a wall: `item_derived_kinds` names the
# kinds a command line can open because it can carry an item id, and `cli` asked ONLY for those.
# `push` is in `APR_KINDS`, has its manifest builder above, and `gate_push_token` refuses
# every push without one -- but nothing could create the request, so no project could ever push.
# Measured 2026-08-02 before this: `approvals/pending/` never held a push request, and the gate's
# own remedy pointed at a command the parser did not have.
#
# A kind belongs here when its subject is a handful of facts a COMMAND LINE can put together --
# typed on it, or resolved from the project by `cli.LINE_MANIFEST_RESOLVERS` (the shape `head` has
# always had, and the one `preset`'s role lists need: a role typing them would be typing what the
# kit's own preset file decides). The CLI reads the flags off the builder's SIGNATURE (the pattern
# `cli.freeze_parameters` already uses for the freeze bodies), so a second line kind arrives on
# the command line with the right flags and no edit there.
def kit_update_subject_manifest(kit, from_version, from_content, to_version, to_content) -> dict:
    """What a kit update is bound to: the two RELEASES, each as the kit's own identity statement.

    THE VERSION STAMP ALONE WOULD NOT DO IT, and the case is not hypothetical: the session briefing
    has been able to report "the same version stamp over different content" since 2026-08-02 and
    nothing could act on that reading. `content:` is the hash `tools/bump_kit_version.py` writes
    over everything a scaffold reads or installs, so the pair (version, content) is what tells two
    trees apart that call themselves one release -- and it is what makes an approval survive
    exactly as long as the staging it was given for.

    BOTH ENDS, because "update A to B" and "update C to B" are different decisions: the FROM side is
    what the user is told the project is losing. `kernel.kitupdate.change_manifest` derives all five
    values from the two VERSION files and `update-kit` re-derives them before it acts, refusing
    unless the hash still matches (`tools/test_kitupdate.py::test_an_approval_for_one_release_pair_
    does_not_cover_another`).
    """
    return {
        "kit": str(kit or ""),
        "from_version": str(from_version or ""),
        "from_content": str(from_content or ""),
        "to_version": str(to_version or ""),
        "to_content": str(to_content or ""),
    }


def filed_position(value) -> str:
    """One repo-relative path, spelled the ONE way this approval's two ends spell it.

    Both ends have to produce the same string or the approval matches nothing: the REQUEST side
    gets it from a role typing a path on a command line, the GATE side from `_filing.position`
    resolving an operand against the working directory a shell command left behind. Windows
    separators, a leading `./`, a `..` segment and a trailing slash are all spellings of one
    position, and normalising them in one function is what keeps the two sides from disagreeing
    about it. The empty string stays empty -- see `filing_correction_operation`, where it is the
    absence of a destination and therefore the whole difference between a move and a deletion.

    WHAT IT NO LONGER DOES IS MAKE AN ABSOLUTE PATH LOOK RELATIVE. It used to `strip("/")`, so
    `/etc/passwd` came back as `etc/passwd` -- a position that reads like one inside the project and
    is not, which is how an approval could be minted for a spelling the gate can never produce
    (verifier finding F5). Only a TRAILING separator is dropped now, and `is_project_position` is
    what decides whether the result is a place this project has at all.
    """
    raw = str(value or "").replace("\\", "/").strip()
    if not raw:
        return ""
    normalised = posixpath.normpath(raw)
    return "" if normalised == "." else (normalised.rstrip("/") or normalised)


def is_project_position(value) -> bool:
    """Is this a place INSIDE the project that a question can honestly show?

    Three properties, and each is one measured way an approval became unusable or unreadable:
      * it names something -- an empty position is the absence of a destination, never a place;
      * it stays inside the project: no drive letter, no leading separator, no `..` climb. The gate
        only ever produces repo-relative positions (`_filing.position` refuses everything else), so
        an approval for any other spelling is one nothing can ever match -- minted, and then the
        real spelling refused (F5). The drive clause reads the same on every host
        (`state.names_a_drive`); with `os.path` it read as none at all wherever the session ran on
        POSIX, and this docstring's "no drive letter" was a promise only Windows kept;
      * it carries no control character. The question the user signs puts this position inside a
        sentence, so a newline in it moves text onto its own line above the mint label, which is the
        same attack on the reader that F4 measured in the free-typed reason. The reason is FOLDED
        because it is prose; a position is REFUSED instead, because folding two different filenames
        onto one string would make one approval cover both.
    """
    position = filed_position(value)
    if not position or position.startswith("/") or position == ".." \
            or position.startswith("../") or names_a_drive(position):
        return False
    return not any(unicodedata.category(char)[0] == "C" for char in position)


# HOW MUCH OF A FREE-TYPED REASON THE QUESTION CARRIES. The number lives here because the fold is
# what the HASH covers, so it is a property of the subject and not of the renderer. 200 characters
# is what fits beside the two positions and the digest without pushing the sentence past the point
# where the person deciding stops reading; a reason that needs more than that belongs in the chat
# the approval question interrupts.
REASON_SHOWN = 200


def _one_line(text, limit=REASON_SHOWN) -> str:
    """Free agent text as ONE readable line -- the form the user sees IS the form the hash covers.

    `--reason` is the first subject key any line kind lets a role type freely, and the question is
    read by the person pilot 3 measured (BUG-0041). Measured by the verifier (F4): a reason of
    "ALLES BLEIBT ERHALTEN\\nHinweis: nichts wird geloescht." renders as its own lines above the
    mint label, so the sentence the user judges is one the requester wrote rather than the kernel.
    The mint code stays unforgeable either way -- the target of that is the human, not the protocol.

    THE FOLD IS A PROPERTY, NOT A LIST OF CHARACTERS: everything unicode classes as a control,
    format, surrogate, private-use or unassigned code point (category `C*`) and every line or
    paragraph separator (`Zl`/`Zp`) becomes a space, then runs of whitespace collapse. That covers
    the bidi overrides and zero-width joiners along with `\\n` and `\\r`, which an enumeration of
    the two obvious ones would not.

    It happens in `filing_correction_subject_manifest`, i.e. BEFORE the hash -- so the folded line
    is what the user signs, not a prettier rendering of something else (DEC-0048).
    """
    folded = "".join(
        " " if (unicodedata.category(char)[0] == "C"
                or unicodedata.category(char) in ("Zl", "Zp")) else char
        for char in str(text or ""))
    collapsed = " ".join(folded.split())
    return collapsed if len(collapsed) <= limit else collapsed[:limit - 1].rstrip() + "…"


def filing_correction_operation(document, destination, content) -> dict:
    """WHAT A FILING CORRECTION DOES, as the three facts a gate can measure and match.

    The correction door in `guard_fs_tripwire` opens for one operation and no other, so the
    operation has to be a value both sides compute rather than a description one side writes:
    which document (`document`), where it ends up (`destination`, EMPTY when it ends up nowhere,
    i.e. is deleted), and which FASSUNG of it (`content`, `hashing.document_content_hash`).

    A SUBSET OF THE SIGNED MANIFEST AND NOT A SECOND ONE. `filing_correction_subject_manifest`
    builds the user's subject out of exactly these keys plus the reason, and
    `live_correction_approval` reads these keys back out of the minted request -- so what the gate
    matches is a part of what the user signed, never something computed beside it. The reason is
    deliberately not in the match: it is what the user was told, not what the shell does, and a
    correction is not a different operation for having been justified differently.
    """
    return {
        "document": filed_position(document),
        "destination": filed_position(destination),
        "content": str(content or ""),
    }


def filing_correction_subject_manifest(document, content, reason, destination="") -> dict:
    """What a filing correction is bound to: this document, this version, this outcome, this why.

    THE DEFAULT IS THE WALL AND THIS IS ITS ONLY DOOR (FR-0050). `guard_fs_tripwire` blocks every
    delete under `inbox/` or `archive/` and every move that takes a document OUT of `archive/`,
    which is right until a document is filed in the wrong place -- and then it was wrong for good,
    because nothing inside the kit could correct it. What the user approves here is one correction:
    one document, in the version they were shown, to one place or to none.

    `destination` CARRIES THE DIFFERENCE BETWEEN THE TWO CORRECTIONS, and carries it as an absence
    rather than as a word: a document either ends up somewhere, and the manifest says where, or it
    ends up nowhere. That is why it is the parameter with a default -- `cli._line_manifest` reads
    the builder's own signature to decide which subject keys a command line may leave out, so
    omitting `--destination` is what asks for a deletion, and the question `_filing_correction_
    target_form` renders says so in words nobody can misread.

    WHAT IT COVERS, stated as the derivation and not as an outcome: THESE BYTES AT THIS POSITION,
    WHILE THEY LIE THERE. `content` binds the document's bytes, so the approval applies exactly as
    long as a file with those bytes is at `document` -- which is what makes the approved correction
    stop being covered the moment it has run (nothing is left to hash), and equally what makes it
    cover a file restored to that position with byte-identical content. Both halves are the same
    sentence, and the earlier wording ("single-use") said only the first
    (`tools/test_hooks.py::test_a_correction_approval_stops_matching_once_the_document_is_gone`,
    `…::test_a_correction_approval_covers_the_bytes_again_when_they_are_put_back`). The question the
    user signs says this in words -- "gilt nur für genau diese Fassung" -- and does not promise a
    one-shot. A "used" marker would have been one more piece of writable state deciding an
    enforcement question, which is the mistake the office ledger gate spent four rounds unlearning.

    TWO REFUSALS BEFORE ANYTHING IS SIGNED, because a subject that cannot be shown honestly must not
    reach a user: a position that is not a place inside this project (`is_project_position` -- an
    absolute or climbing path would mint an approval the gate can never match, F5), and a
    destination that was GIVEN and names no position at all (`.`, `/`, whitespace -- it would
    silently become a DELETION request in the question, F7). Leaving `--destination` out entirely
    stays the way to ask for a deletion; the empty string is the one spelling of that absence, and
    it is accepted as the absence it is.
    """
    document_position = filed_position(document)
    if not is_project_position(document_position):
        raise ApprovalError(
            "a filing correction names a document INSIDE this project, and %r is not one (an "
            "absolute path, a climb out of the project, or a name carrying control characters). "
            "The gate only ever produces project-relative positions, so an approval for this "
            "spelling could never match anything. Remedy: name the document with its path relative "
            "to the project root." % str(document or ""),
            user_text="Es wurde keine Freigabe erteilt: der genannte Ablageort liegt nicht in "
                      "diesem Projekt, deshalb könnte die Freigabe nie greifen. " + NEXT_START_OVER)
    destination_position = filed_position(destination)
    if destination and not destination_position:
        raise ApprovalError(
            "the destination %r names no position. Leaving the destination out is how a DELETION is "
            "requested, and this value would have become one silently -- refused, because the user "
            "would have been asked to sign a deletion nobody meant to request. Remedy: name where "
            "the document should land, or leave the destination out to request the deletion "
            "deliberately." % str(destination),
            user_text="Es wurde keine Freigabe erteilt: das genannte Ziel ist kein Ablageort. "
                      + NEXT_START_OVER)
    if destination_position and not is_project_position(destination_position):
        raise ApprovalError(
            "a filing correction moves a document to a place INSIDE this project, and %r is not one. "
            "Remedy: name the destination with its path relative to the project root."
            % str(destination),
            user_text="Es wurde keine Freigabe erteilt: das genannte Ziel liegt nicht in diesem "
                      "Projekt. " + NEXT_START_OVER)
    manifest = filing_correction_operation(document, destination, content)
    manifest["reason"] = _one_line(reason)
    return manifest


# A rule id, in the shape the shipped plan template uses for its examples (`FP-001`). Held to a
# pattern rather than taken free-form because this value is the handle the user, the clerk and the
# Verfahrensdokumentation all name a rule by: an id carrying whitespace or a control character
# would make one rule unfindable under two spellings, and the question the user signs prints it.
RULE_ID_RX = re.compile(r"\A[A-Za-z][A-Za-z0-9_-]{0,31}\Z")
# THE SEPARATOR A COMMAND LINE PACKS A LIST INTO. `document_types` is a LIST in the plan and one
# flag on the line, and the two need one conversion or the question shows something the file will
# not carry. A comma, because that is what the plan's own examples read like
# (`[invoice, credit_note]`) and because a document class name may legitimately contain a space.
_LIST_SEPARATOR = ","


def _typed_list(value) -> list:
    """A command line's comma-separated value as the LIST the manifest hashes and the plan carries.

    Idempotent over a real list, so a caller that already has one (a test, a future resolver) may
    pass it: what comes back is always the normalised list, which is what makes the hash the same
    whichever side built it.
    """
    items = value if isinstance(value, (list, tuple)) else str(value or "").split(_LIST_SEPARATOR)
    return [_one_line(item, 120) for item in items if str(item).strip()]


def filing_rule_subject_manifest(rule_id, path_template, document_types, filename_template,
                                 retention, reason) -> dict:
    """What a NEW Aktenplan rule is bound to: which documents, where, named how, kept how long, why.

    THE SUBJECT IS THE RULE ITSELF, every field of it, because this approval does not authorise an
    action on an existing thing -- it IS the content that gets written (`kernel.filing.apply`
    re-derives this manifest and writes exactly `filing.rule_from` of it). So there is no key in
    the hash the question does not show and no sentence in the question the hash does not cover,
    which is DEC-0048's rule taken in its constructive direction, and it is why every one of them is
    typed on the line rather than resolved: each is a decision the USER makes with the clerk
    (FR-0049 step 5), not a fact the project already holds.

    THE FIRST SEGMENT OF `path_template` MUST BE A LITERAL DIRECTORY NAME, and that refusal is the
    correction of a measured hole rather than tidiness. `gate_filing` matches a rule by translating
    each `<...>` into "a run of characters inside one segment", so a template that BEGINS with a
    placeholder names no tray at all -- it matches every directory at its depth. Measured
    2026-08-21 against the shipped gate: with `<a>/<b>` minted into the plan,
    `mv inbox/rechnung.pdf archive/erfunden/x.pdf` went from rc 2 to rc 0, i.e. the wall was gone
    for the whole level. The chain runs inside one session: a role proposes `<Bereich>/<Jahr>`, the
    question renders it beside the plan's own examples, and the BUG-0041 reader signs a wildcard.

    IT IS A DEFINITION AND NOT A SECOND PARSER OF THE PLACEHOLDER SYNTAX. What is required is that
    the first segment be literal -- it may carry no `<` or `>` at all -- and every reading of every
    syntax agrees about a segment that contains neither. So this does not become a second answer to
    "what is a placeholder"; `gate_filing.PLACEHOLDER_RX` stays the only one, and the kernel still
    does not need to know which directory is the archive.

    WHAT IS STILL NOT CHECKED, said rather than implied: whether the literal first segment is the
    filing tray. Which top-level directory that is remains the KIT's fact (`hooks/_filing.ARCHIVE`,
    the kit's own `document_trays.txt`), and a rule naming another one simply matches nothing --
    `gate_filing` only ever asks about a destination that lands in the archive. That is an unusable
    rule, not an open wall.
    """
    identifier = _one_line(rule_id, 40)
    if not RULE_ID_RX.match(identifier):
        raise ApprovalError(
            "a filing rule is named by an id like the plan's own examples (`FP-001`): a letter, "
            "then up to 31 more letters, digits, `-` or `_`. %r is not one, and the id is what "
            "the user, the clerk and the Verfahrensdokumentation all name this rule by. Remedy: "
            "give the rule a plain id." % str(rule_id or ""),
            user_text="Es wurde keine Freigabe erteilt: die Kennung der neuen Ablage-Regel ist "
                      "nicht verwendbar. " + NEXT_START_OVER)
    position = filed_position(path_template)
    if not is_project_position(position):
        raise ApprovalError(
            "a filing rule says where documents live INSIDE this project, and %r is not such a "
            "place (an absolute path, a climb out of the project, or a name carrying control "
            "characters). Remedy: give the location relative to the project root, spelled the way "
            "the filing plan's own commented examples spell one." % str(path_template or ""),
            user_text="Es wurde keine Freigabe erteilt: der genannte Ablageort liegt nicht in "
                      "diesem Projekt. " + NEXT_START_OVER)
    if any(bracket in position.split("/", 1)[0] for bracket in "<>"):
        raise ApprovalError(
            "the FIRST part of a filing rule's location has to be a real directory name, and %r "
            "starts with a placeholder. A rule that begins with one names no tray at all: the "
            "filing gate reads a placeholder as 'any characters within this segment', so such a "
            "rule matches EVERY directory at that depth and approving it would take the wall down "
            "for the whole level instead of adding a place for one class of document. Remedy: name "
            "the tray literally and put the placeholders below it."
            % str(path_template or ""),
            user_text="Es wurde keine Freigabe erteilt: der Ablageort beginnt mit einem "
                      "Platzhalter und wuerde damit auf JEDEN Ordner dieser Ebene passen, nicht "
                      "nur auf den gemeinten. " + NEXT_START_OVER)
    types = _typed_list(document_types)
    if not types:
        raise ApprovalError(
            "a filing rule says WHICH documents it covers, and no document type was given -- the "
            "user would be asked to approve a location for nothing in particular. Remedy: name the "
            "class, e.g. `--document-types \"invoice,credit_note\"`.",
            user_text="Es wurde keine Freigabe erteilt: es wurde nicht gesagt, für welche "
                      "Dokumente die neue Regel gilt. " + NEXT_START_OVER)
    naming = _one_line(filename_template, 200)
    # NOT SAID AND SAID-TO-BE-EMPTY ARE TWO ANSWERS (BUG-0213). The refusal below exists so the
    # kernel never FILLS IN a decision the user owes, and that is a question about whether the
    # value was given at all -- `None` is the flag nobody typed, `""` is the flag typed empty,
    # which is the second honest form `filing.retention_refusal` allows for a drawer whose clock
    # does not start at the end of a year. Read as "falsy", the two were one answer and the empty
    # form the plan's own header documents could not be asked for through the sanctioned command.
    # `tools/test_kernel.py::test_a_filing_rule_with_no_countable_retention_can_be_asked_for`
    kept = None if retention is None else _one_line(retention, 200)
    if not naming or retention is None:
        raise ApprovalError(
            "a filing rule says how its documents are NAMED and how long they are KEPT; %s is "
            "missing. Both are decisions the user makes -- a rule the kernel filled in for them "
            "would be signed and not chosen. Remedy: name it on the line (pass an EMPTY "
            "`--retention \"\"` for a drawer that really has no span to count)."
            % ("the filename template" if not naming else "the retention"),
            user_text="Es wurde keine Freigabe erteilt: zur neuen Ablage-Regel fehlt noch eine "
                      "Angabe. " + NEXT_START_OVER)
    return {"rule_id": identifier, "path_template": position, "document_types": types,
            "filename_template": naming, "retention": kept, "reason": _one_line(reason)}


# HOW MANY DISTINCT PLACES ONE DOCUMENT PROPOSAL MAY TOUCH. The user has to READ what they sign,
# and every one of these descriptors lands inside the question text beside the two paths, two
# checksums, the reason and the expiry -- and a descriptor now carries the FILLED VALUE or the
# ADDED COMMENT itself (verifier finding B2), not just its place. Eight is what a question at the
# fold's own bound still leaves readable for the person BUG-0041 describes; the round that set it
# reports the two lengths it measured. A proposal touching more places is REFUSED with the
# count rather than summarised, because a summary is the one thing an approval may not be. It
# bounds the number of PLACES and not the amount: fifteen new categories in one list are ONE.
MAX_PROPOSAL_CHANGES = 8
# The proposal area, spelled as a command line spells it. `kernel.documents` composes the real path
# through the freeze chokepoint; this is only the prefix the SUBJECT must carry, so the user sees a
# position that is a proposal and never a file from somewhere no gate has ever seen.
_PROPOSAL_PREFIX = "staging/"


def document_proposal_subject_manifest(kit_document, proposal, base, proposed, changes,
                                       reason) -> dict:
    """What applying a staged proposal is bound to: this document, this version, this proposal, why.

    THE SUBJECT IS ONE BEFORE-AND-AFTER. `base` is the document's bytes as they stand and `proposed`
    is the staged file's, so the approval covers exactly the transition the user was shown -- and
    stops covering anything the moment either file moves. That is also what makes it single-use in
    the derived way `filing_correction_subject_manifest` describes: after the write the document
    hashes to `proposed`, so the same approval no longer matches. No "used" flag in writable state
    has to be kept honest for it.

    `changes` IS WHAT THE USER READS, and it names PLACES rather than values: which key gained an
    entry, which empty field was filled. The values are in the file the question names, bound by its
    checksum -- a question that quoted them would be a summary of a document rather than a binding
    on it, and a long one would be unreadable exactly where reading IS the safeguard. The
    descriptors arrive in the user's language (`kernel.documents.compare`), because a value a
    non-technical user has to judge is German where it lands in an approval card (BUG-0073).
    """
    document = filed_position(kit_document)
    staged = filed_position(proposal)
    if not is_project_position(document):
        raise ApprovalError(
            "a document proposal names a file INSIDE this project's state directory, and %r is not "
            "one (an absolute path, a climb out of it, or a name carrying control characters). "
            "Remedy: name it relative to the state directory, e.g. `--kit-document "
            "master_data.yaml`." % str(kit_document or ""),
            user_text="Es wurde keine Freigabe erteilt: die genannte Datei liegt nicht in diesem "
                      "Projekt. " + NEXT_START_OVER)
    if not is_project_position(staged) or not staged.lower().startswith(_PROPOSAL_PREFIX):
        raise ApprovalError(
            "a proposal is a file in the task's own proposal area (`%s<TSK-ID>/<name>`), and %r is "
            "not one. Everything else in the project is either canonical state or a place no gate "
            "ever saw written. Remedy: stage the document as it should stand and name it there."
            % (_PROPOSAL_PREFIX, str(proposal or "")),
            user_text="Es wurde keine Freigabe erteilt: der genannte Vorschlag liegt nicht im "
                      "Vorschlagsbereich des Vorgangs. " + NEXT_START_OVER)
    described = [_one_line(one, 120) for one in _typed_list(changes)]
    if not described:
        raise ApprovalError(
            "a document proposal says WHAT it would add, and nothing was given -- the user would "
            "be asked to approve a write with no description of it. Remedy: this list is derived "
            "by the command from the two files; report the gap if it arrived empty.",
            user_text="Es wurde keine Freigabe erteilt: es wurde nicht gesagt, was der Vorschlag "
                      "am Dokument ändert. " + NEXT_START_OVER)
    if len(described) > MAX_PROPOSAL_CHANGES:
        raise ApprovalError(
            "this proposal changes %d places in %s, and an approval question the user cannot read "
            "through is not an approval -- at most %d are shown, and shortening the list would ask "
            "them to sign what they were not told. Remedy: split the proposal into steps and ask "
            "for each; the command only ever adds, so the steps are independent."
            % (len(described), document, MAX_PROPOSAL_CHANGES),
            user_text="Es wurde keine Freigabe erteilt: der Vorschlag ändert zu viele Stellen auf "
                      "einmal, um sie in einer Frage lesbar zu zeigen. " + NEXT_START_OVER)
    if not str(base or "") or not str(proposed or ""):
        raise ApprovalError(
            "a document proposal is bound to the bytes of both files, and %s could not be hashed. "
            "Remedy: report the gap and name the file."
            % ("the document" if not base else "the staged proposal"),
            user_text="Es wurde keine Freigabe erteilt: eine der beiden Dateien konnte nicht "
                      "gelesen werden. " + NEXT_START_OVER)
    return {"kit_document": document, "proposal": staged, "base": str(base),
            "proposed": str(proposed), "changes": described, "reason": _one_line(reason)}


def document_revision_subject_manifest(kit_document, proposal, base, proposed, replacements,
                                       deletions, additions, reason) -> dict:
    """What revising a kit document is bound to: this document, this version, and EVERY spot.

    THE SPOTS ARE THE SUBJECT, and that is the difference to its additive sibling. There the
    question may name a place and leave the value in the file the checksum binds, because nothing
    that stands is being unsaid. Here something IS: a value the project recorded is replaced, or
    it goes. So every spot carries the old text and the new one, and the card shows them -- an
    approval to unsay something that did not say what is being unsaid would be a signature on a
    file, not on a change.

    THEREFORE NEVER SUMMARISED. `MAX_PROPOSAL_CHANGES` bounds how many spots one question may
    carry, and a revision with more is REFUSED with the number -- exactly as the additive route
    refuses, and for the sharper reason: "n Einträge geändert" is the one card this project may
    never print (FR-0067's own condition, and the reason the prose channel of H76(a) does not
    widen here -- the values shown are the document's own, folded to one line each like every
    other descriptor, and their number is capped rather than their content trimmed).

    THREE LISTS, because the card is louder about the deletions and reads their kind off the
    structure rather than out of the descriptor text. Both directions are measured by
    `tools/test_approvals_dispatch.py::test_a_revision_card_shows_every_spot_and_is_never_a_count`.
    """
    document = filed_position(kit_document)
    staged = filed_position(proposal)
    if not is_project_position(document):
        raise ApprovalError(
            "a document revision names a file INSIDE this project's state directory, and %r is not "
            "one. Remedy: name it relative to the state directory, e.g. `--kit-document "
            "content_guidelines.yaml`." % str(kit_document or ""),
            user_text="Es wurde keine Freigabe erteilt: die genannte Datei liegt nicht in diesem "
                      "Projekt. " + NEXT_START_OVER)
    if not is_project_position(staged) or not staged.lower().startswith(_PROPOSAL_PREFIX):
        raise ApprovalError(
            "a revision is a file in the task's own proposal area (`%s<TSK-ID>/<name>`), and %r is "
            "not one. Remedy: stage the document as it should stand and name it there."
            % (_PROPOSAL_PREFIX, str(proposal or "")),
            user_text="Es wurde keine Freigabe erteilt: der genannte Vorschlag liegt nicht im "
                      "Vorschlagsbereich des Vorgangs. " + NEXT_START_OVER)
    shown = {name: [_one_line(one, 120) for one in _typed_list(value)]
             for name, value in (("replacements", replacements), ("deletions", deletions),
                                 ("additions", additions))}
    if not shown["replacements"] and not shown["deletions"]:
        raise ApprovalError(
            "a document revision REPLACES or DELETES something, and neither was given -- an "
            "addition goes through the route whose question promises that nothing existing "
            "changes. Remedy: this list is derived by the command from the two files; report the "
            "gap if it arrived empty.",
            user_text="Es wurde keine Freigabe erteilt: es wurde nicht gesagt, was die Revision am "
                      "Dokument ersetzt oder löscht. " + NEXT_START_OVER)
    total = sum(len(one) for one in shown.values())
    if total > MAX_PROPOSAL_CHANGES:
        raise ApprovalError(
            "this revision touches %d places in %s, and an approval question the user cannot read "
            "through is not an approval -- at most %d are shown, and shortening the list would ask "
            "them to sign what they were not told. Remedy: split it into steps and ask for each."
            % (total, document, MAX_PROPOSAL_CHANGES),
            user_text="Es wurde keine Freigabe erteilt: die Revision ändert zu viele Stellen auf "
                      "einmal, um sie in einer Frage lesbar zu zeigen. " + NEXT_START_OVER)
    if not str(base or "") or not str(proposed or ""):
        raise ApprovalError(
            "a document revision is bound to the bytes of both files, and %s could not be hashed. "
            "Remedy: report the gap and name the file."
            % ("the document" if not base else "the staged revision"),
            user_text="Es wurde keine Freigabe erteilt: eine der beiden Dateien konnte nicht "
                      "gelesen werden. " + NEXT_START_OVER)
    return {"kit_document": document, "proposal": staged, "base": str(base),
            "proposed": str(proposed), "replacements": shown["replacements"],
            "deletions": shown["deletions"], "additions": shown["additions"],
            "reason": _one_line(reason)}


# THE RECORD KEYS OF ONE ITEM INSIDE A LIST-BOUND SUBJECT MANIFEST. They are named `GOAL_*`
# because the plan approval (FR-0074) was the first kind whose subject was a list, and they are
# NOT renamed for the second one: the keys are the contract of the SHAPE, not of that kind, and
# one spelling read by both is the whole reason `listed_items` and `_assert_the_list_covers` can
# serve `plan` and `verification` without a table of kinds. `verification` writes the same two and
# adds `LISTED_EVIDENCE_FIELD`.
GOAL_ITEM_FIELD = "item"
GOAL_SCOPE_HASH_FIELD = "scope_hash"
# WHAT MEASURED A LISTED BUG (PR-0012 AC-1, BUG-0090's rule). It is inside the hashed manifest and
# printed beside the id in the approving option, so what the user signs is "this defect, proven by
# THAT run" and not a bare list of ids.
LISTED_EVIDENCE_FIELD = "evidence"


def plan_goals(state: ProjectState) -> list:
    """The product goals a plan approval would cover, as hashable records (FR-0074).

    WHICH ITEMS ARE GOALS is derived twice over and listed nowhere: a type is a product root when
    `backlog_types.ROOT_TYPE_BY_KIT` names it (the same map the delivery-verdict rule and the
    scaffold read), and a root is still ASKING its scope question when it stands in the source
    status of its own `(type, PLAN_COVERED_KIND)` edge. A goal whose scope is already settled is
    therefore not in the list -- putting it in would let a later edit of a finished goal kill the
    approval covering the unfinished ones.

    WHAT EACH RECORD CARRIES, and why each of the three: the id, so the user reads WHICH goals;
    the revision, so an item the kernel has moved on stops being covered; and
    `subject_manifest_hash(item_subject_manifest(item, PLAN_COVERED_KIND))` -- the SAME hash a
    single scope approval binds to, which is what makes the plan approval cover exactly as much of
    a goal's content as the per-goal one did, no more. The title rides along because the user has
    to be able to read the list; it is inside the hash like everything else here, so a retitled
    goal re-opens the question.

    SORTED BY ID, because the manifest is hashed and a directory listing is not an order.
    `tools/test_approvals_dispatch.py::test_the_plan_covers_every_open_goal_and_only_those`.
    """
    goals = []
    for item_type in sorted(set(ROOT_TYPE_BY_KIT.values())):
        edge = APPROVAL_TRANSITIONS.get((item_type, PLAN_COVERED_KIND))
        if edge is None:
            continue
        for stem, path in state.iter_active_items(item_type):
            try:
                item = state._read_yaml(path)
            except Exception:  # noqa: BLE001 -- an unreadable file is no goal; validate reports it
                continue
            if not isinstance(item, dict) or item.get("status") != edge[0]:
                continue
            goals.append({
                GOAL_ITEM_FIELD: str(item.get("id") or stem),
                "title": str(item.get("title") or ""),
                "revision": item.get("revision"),
                GOAL_SCOPE_HASH_FIELD: listed_content_hash(item),
            })
    return sorted(goals, key=lambda goal: goal[GOAL_ITEM_FIELD])


def content_question(kind: str) -> str:
    """The per-ITEM approval kind whose content question a list-bound approval of `kind` binds.

    DERIVED AND NOT TABLED, so a third list-bound kind still needs no entry anywhere: a kind that
    HAS an item-derived manifest asks its own content question about each entry, and one that has
    none (a `plan`, a `verification` batch) binds the per-item scope question its entries would
    otherwise have been asked separately (`PLAN_COVERED_KIND`).

    WHY IT MATTERS, measured while the second batch kind was built (PR-0012 AC-4): a hole exception
    is an acceptance of a DESCRIBED gap, and the description it is about -- the mechanism, the
    severity and above all the sentence that says what limits the gap instead (`HOLE_LIMIT_FIELD`)
    -- is what `item_subject_manifest` hashes for that kind and is NOT in `_SCOPE_FIELDS`. Binding
    such an entry to the scope hash would have let the bound sentence be rewritten under a standing
    acceptance. `tools/test_approvals_dispatch.py::test_a_batch_stops_covering_a_hole_whose_bound_moved`
    """
    return kind if kind in item_derived_kinds() else PLAN_COVERED_KIND


def listed_content_hash(item: dict, kind: str = PLAN_COVERED_KIND) -> str:
    """The content a LIST-bound approval of `kind` binds ONE listed item to.

    It is the very manifest that kind's per-item approval binds to, so one answer over a list
    covers exactly as much of each item as its own approval would -- no more, and with the same
    limit that manifest has (for a `scope` on a `BUG`, one of five hashed fields). Which manifest
    that is, is `content_question`'s answer and not this function's.

    ONE SPELLING FOR THREE READERS -- `plan_goals`, `verification_batch` and `hole_exception_batch`
    write the hash into the record the user signs, `_assert_the_list_covers` recomputes it when the
    approval is later asked to authorise something. A second spelling is how the two ends of a
    content binding drift apart, and here they would drift silently: the cover check would simply
    stop matching.
    """
    return subject_manifest_hash(item_subject_manifest(item, content_question(kind)))


def plan_subject_manifest(goals) -> dict:
    """The subject of a plan approval: the confirmed goal list, whole.

    ONE KEY, and it holds the list rather than a count or a digest of it: what the user signs has
    to be what the question shows (`_plan_target_form` renders every entry), and a plan
    approval that hashed only a summary would let the list change under a matching hash.

    A PLAN WITH NO OPEN GOAL IS REFUSED, at the builder, before anybody is asked to sign it: an
    empty list is a permission bound to nothing -- exactly what `create_pending_request` refuses a
    routine approval for -- and it would go on covering every goal captured afterwards, which is
    the opposite of what the hash is for.
    """
    # FAIL-CLOSED ON A SUBJECT THIS CANNOT READ: anything that is not a goal record is dropped
    # here, so a caller handing over a string or a half-built list lands on the refusal below
    # rather than on a manifest describing something nobody can check.
    goals = [dict(goal) for goal in (goals or []) if isinstance(goal, dict)]
    if not goals:
        raise ApprovalError(
            "a plan approval covers the confirmed product goals and this project has none whose "
            "scope is still open, so there is nothing to approve. Remedy: capture the goals first "
            "-- a plan approval bound to an empty list would cover every goal captured after it.",
            user_text="Es wurde keine Freigabe erteilt: es gibt noch keine Produktziele, die "
                      "freigegeben werden könnten. " + NEXT_START_OVER)
    return {"goals": goals}


def _plan_target_form(manifest: dict) -> str:
    """The plan as the user reads it: EVERY goal by id and title, never a count.

    The same rule a revision card follows (`_document_revision_target_form`): this is the one
    approval whose whole point is that one answer covers several items, so a question saying
    "10 Ziele" would be asking for a signature on a number.
    """
    goals = manifest.get("goals") or []
    return "den Plan aus %s" % "; ".join(
        "%s „%s“ (Revision %s)" % (goal.get(GOAL_ITEM_FIELD), goal.get("title") or "ohne Titel",
                                   goal.get("revision"))
        for goal in goals)


def batch_closing_types(kind: str) -> frozenset:
    """The item types whose OWN edge a list-bound `kind` commits -- empty when it commits none.

    THE LINE BETWEEN THE TWO LIST-BOUND KINDS, derived from `APPROVAL_TRANSITIONS` instead of
    written down: `plan` is a STAND-IN (it answers `PLAN_COVERED_KIND`'s question for goals that
    keep their own edges), so no pair names it and its mint moves nothing by itself; `verification`
    is paired with `BUG`, so its mint walks every bug its subject lists. A third list-bound kind
    added with a pair starts closing, one added without a pair does not, and neither needs a second
    statement here. `tools/test_approvals_dispatch.py::test_only_a_list_kind_paired_with_a_type_closes_what_it_lists`
    """
    return frozenset(typ for (typ, listed) in APPROVAL_TRANSITIONS if listed == kind)


def batch_walk_blockers(state: ProjectState, kind: str, item_ids, request: dict = None) -> list:
    """Why each listed item could NOT be walked by a mint of `kind` -- [] when every one can.

    ONE READER FOR THE TWO MOMENTS THAT MUST AGREE, and that is the point of the function rather
    than of two checks: `request-approval` asks it BEFORE the user is shown a question (a defect
    whose test never passed, or one already past the edge, is refused BY NAME and never reaches the
    batch), and `mint` asks it again before it writes anything, because the store can move between
    the question and the answer. With two readers the second one would fire halfway through the
    walk -- after the APR exists and after some of the listed items had already moved.

    THE FOUR REASONS ARE DERIVED, not enumerated per type: the item has to be readable, its type
    has to be one this kind commits an edge for (`batch_closing_types`), its status has to sit on
    that type's chain no further than the edge's source (past it, the approval would authorise
    nothing this item still needs), and -- where the walk crosses the type's confirming edge -- the
    proof that edge demands has to be in force already (`state.CONFIRMING_EVIDENCE` read through
    `report.qa_verdicts`, which is the same reader `_assert_confirmed` uses, so the two cannot
    answer differently). For `BUG` that fourth line IS BUG-0090's rule: VERIFIED only on a passing
    test Evidence naming the bug.

    AND A FIFTH ONCE THE BATCH IS SIGNED (`request` given): every way `_assert_the_list_covers`
    can refuse -- the item is not in the list, the kernel moved it to another revision, its signed
    content changed. Those three are the ONLY reasons the walk itself can still refuse, because
    `state._transition_locked` proves the approval through that same check, and the first cut of
    this function did not ask any of them: measured as a process, an `update` on one listed defect's
    `acceptance_criteria` between question and click left BUG-0001 VERIFIED and archived, BUG-0002
    at TRIAGED carrying an `approval_ref`, BUG-0003 untouched, the request consumed, and the hook
    saying "no approval was created". All-or-nothing is the whole promise of a batch, so it is asked
    HERE, before the first write -- not by the walk, which has none of its writes back.
    At REQUEST time there is no signed list yet (the records are being built FROM the current
    content), which is why the parameter is optional rather than a second function.
    """
    from .state import CONFIRMING_EVIDENCE, PASSING_RESULT

    types = batch_closing_types(kind)
    if not types:
        # A LIST-BOUND KIND WHOSE MINT WALKS NOTHING (`plan`) CAN BE BLOCKED BY NOTHING. Measured
        # the moment `mint` began asking this of every listed subject: a plan approval over two
        # goals was refused with "a plan approval commits no transition of a PR", i.e. the check
        # answered a question nobody had asked -- whether the goals could be WALKED -- about an
        # approval that only stands in for their own scope question.
        return []
    # ONE PASS over the Evidence store for the whole list -- see `proofs_naming` for why the batch
    # asks a NARROWER question than `report.qa_verdicts`, and for the store that measured it.
    naming = proofs_naming(
        state, item_ids,
        CONFIRMING_EVIDENCE.get(sorted(types)[0]) if len(types) == 1 else None)
    if len(types) > 1:
        naming = {}
        for one in sorted(types):
            naming.update(proofs_naming(state, item_ids, CONFIRMING_EVIDENCE.get(one)))
    blockers = []
    for item_id in item_ids:
        try:
            item_type, _number = parse_id(str(item_id))
        except Exception:  # noqa: BLE001 -- an id nothing can parse names no item
            blockers.append("%s: not an item id" % (item_id,))
            continue
        if item_type not in types:
            blockers.append(
                "%s: a %s approval commits no transition of a %s (%s). Remedy: take it out of the "
                "batch." % (item_id, kind, item_type,
                            "it commits %s" % "/".join(sorted(types)) if types
                            else "it commits none at all"))
            continue
        try:
            item = state.read_item(str(item_id))
        except Exception as exc:  # noqa: BLE001 -- unreadable, absent, already archived
            blockers.append("%s: %s" % (item_id, exc))
            continue
        if request is not None:
            try:
                _assert_the_list_covers(request, item)
            except ApprovalError as exc:
                blockers.append("%s: %s" % (item_id, exc))
                continue
        chain = AUTOMATA[item_type].chain
        source = APPROVAL_TRANSITIONS[(item_type, kind)][0]
        status = str(item.get("status") or "")
        if status not in chain:
            blockers.append(
                "%s is %s, which is off the %s chain -- nothing walks out of it. Remedy: take it "
                "out of the batch." % (item_id, status or "without a status", item_type))
            continue
        if chain.index(status) > chain.index(source):
            blockers.append(
                "%s is already %s, past the %s -> %s this approval commits, so it would authorise "
                "nothing it still needs. Remedy: take it out of the batch and finish it with "
                "`transition`." % (item_id, status, source,
                                   APPROVAL_TRANSITIONS[(item_type, kind)][1]))
            continue
        end = batch_walk_end(item_type, kind)
        confirming = confirming_edge(item_type)
        proof = CONFIRMING_EVIDENCE.get(item_type)
        if proof and confirming and confirming[1] == end:
            verdict = naming.get(str(item_id))
            if not verdict or verdict.get("result") != PASSING_RESULT:
                blockers.append(
                    "%s has no passing %r Evidence naming it (%s), and %s -> %s needs one -- the "
                    "status would say the defect is gone with nothing having measured that. "
                    "Remedy: re-run the test that covers it and record the run "
                    "(`evidence --kind %s --result pass --related %s --run-scope selection "
                    "--run-command <the node>`), then ask again."
                    % (item_id, proof,
                       "the current verdict is %r" % verdict.get("result") if verdict
                       else "there is none",
                       confirming[0], confirming[1], proof, item_id))
                continue
            # ...AND THAT EVIDENCE HAS TO HAVE MEASURED THIS DEFECT (DEC-0100 (3), round 1 F2).
            # A passing `test` evidence related to the item was the whole test until here, and it
            # is not enough: measured, a TRIAGED bug whose evidence carried a run command naming a
            # node that exists nowhere in the tree was walked to VERIFIED and archived by ONE
            # click. `naming_tests` is the one reader of "a test names this item", shared with
            # `tools/close_measured_pass.py` so the search that PROPOSES a batch and the check that
            # accepts one cannot disagree about what naming means.
            why = naming_tests.coverage_blocker(
                os.path.dirname(state.root), str(item_id), verdict.get("run_command"))
            if why:
                blockers.append(
                    "%s cannot be closed by this approval: %s. Remedy: re-run the test that NAMES "
                    "the defect and record that run (`evidence --kind %s --result pass --related "
                    "%s --run-scope selection --run-command <the node>`); a defect no test names "
                    "needs a closing test, not a click."
                    % (item_id, why, proof, item_id))
    return blockers


def _recorded_at(record) -> tuple:
    """The order two Evidences were recorded in -- see `proofs_naming` for why the id is in it."""
    return (str(record.get("created") or ""), str(record.get("id") or ""))


def proofs_naming(state: ProjectState, item_ids, proof: str) -> dict:
    """{item id: the NEWEST `proof` Evidence whose `related` NAMES it} -- direct only, any result.

    NOT `report.qa_verdicts`, and that difference is the whole point. `evidence_covers` accepts an
    INDIRECT hop -- an evidence about something that hangs from the item -- which is right for the
    delivery question ("does this body of work ship") and wrong for this one ("is THIS defect
    repaired"). Measured on the real store while round 1's F2 was being closed: `BUG-0082` carries
    `related_pr: BUG-0075`, so the passing run that measured the metacharacter fix answered as
    BUG-0075's current verdict too, and the batch would have offered the user a defect whose proof
    is about a different one. DEC-0100 (3) says the evidence has to NAME the bug; a parent closed
    on its child's green run is that rule broken one level up.

    ONE PASS over the Evidence store for the WHOLE batch, because the caller has the whole list: a
    per-item scan of ~300 records times 31 items is ~10 000 YAML reads at request time.

    `tools/test_approvals_dispatch.py::test_a_parent_defect_is_not_closed_by_its_childs_green_run`
    """
    wanted = {str(one) for one in (item_ids or [])}
    newest = {}
    for _stem, path in state.iter_active_items("EVD"):
        try:
            record = state._read_yaml(path)
        except Exception:  # noqa: BLE001 -- an unreadable record proves nothing
            continue
        if not isinstance(record, dict):
            continue
        # ANY RESULT, and the caller judges it. Keeping only the passing ones would make a FAIL
        # recorded after a PASS invisible -- which is the regression reading `_newest_per_kind`
        # exists for, and a batch that closed a defect whose newest run is red would be the false
        # verdict this whole route avoids. Measured: with a passing-only scan,
        # `test_a_batch_that_moved_since_the_question_closes_nothing_at_all` reached the WALK and
        # was refused there by `_assert_confirmed` instead of by the blocker list.
        if record.get("kind") != proof:
            continue
        related = record.get("related") or []
        related = list(related) if isinstance(related, (list, tuple)) else [related]
        for reference in related:
            item_id = str(reference)
            if item_id not in wanted:
                continue
            previous = newest.get(item_id)
            # (created, id) AND NOT created ALONE: `_now_iso` has second resolution, so two
            # Evidences recorded in the same second compare equal and the winner is whichever the
            # directory listing yielded last. Measured -- a `fail` captured right after a `pass`
            # lost the comparison and the batch reached the WALK, where the refusal arrives after
            # the APR exists. The id is monotonic in capture order, which is the tie-break
            # `report._newest_per_kind` gets from its own iteration order.
            if previous is None or _recorded_at(record) > _recorded_at(previous):
                newest[item_id] = record
    return newest


def batch_walk_end(item_type: str, kind: str) -> str:
    """The status a batch mint of `kind` walks a listed item of `item_type` TO.

    THREE ANSWERS, and the first one is what the second batch kind needed (PR-0012 AC-4): an edge
    whose target is NOT ON THE TYPE'S CHAIN ends there and nowhere further. `BUG`'s
    `ACCEPTED_EXCEPTION` is that case -- a terminal beside the chain, reachable only from TRIAGED
    (`backlog_types`) -- so a batch of accepted exceptions walks to it and stops. Reading the
    confirming end for it would have walked a gap the user ACCEPTED to VERIFIED, i.e. said the gap
    was measured gone, which is the opposite statement.

    Otherwise: the type's CONFIRMING end when it has one (`backlog_types.confirming_edge` -- for
    `BUG` that is VERIFIED), the approved edge's own target when it has none. Derived, because the
    two halves of the walk have different guards and only the derivation keeps them honest: the
    approval opens the edge it commits, and every step after it is either free or carries its own
    proof, which the caller has already required (`batch_walk_blockers`). A hard-coded "VERIFIED"
    here would be this kernel's third statement of the BUG chain.
    `tools/test_approvals_dispatch.py::test_a_batch_of_accepted_exceptions_ends_on_the_off_chain_terminal`
    """
    target = APPROVAL_TRANSITIONS[(item_type, kind)][1]
    if target not in AUTOMATA[item_type].chain:
        return target
    confirming = confirming_edge(item_type)
    return confirming[1] if confirming else target


def verification_batch(state: ProjectState, item_ids) -> list:
    """The records a verification approval would close -- refusing BY NAME what it cannot.

    THE EVIDENCE IS READ, NEVER TYPED, for the reason every entry of `LINE_MANIFEST_RESOLVERS`
    exists: what the hash covers has to be what the user is shown, and an evidence id typed on a
    command line could only differ from the record that actually measured the defect. The verdict
    comes from the SAME reader the confirming edge itself consults (`report.qa_verdicts` with
    `CONFIRMATION_QUESTION`), so the id in the question is the id that will walk the item.

    REFUSED AS A WHOLE, and with every offender named at once: a batch is put to the user in one
    question, so a role fixing one id at a time would ask the store the same question 25 times.
    `tools/test_approvals_dispatch.py::test_a_bug_without_a_passing_test_evidence_is_refused_from_the_batch_by_name`
    """
    from .state import CONFIRMING_EVIDENCE

    ids = [str(one) for one in (item_ids or [])]
    duplicates = sorted({one for one in ids if ids.count(one) > 1})
    if duplicates:
        raise ApprovalError(
            "a batch names %s twice -- an item cannot be closed two times by one answer. Remedy: "
            "list every id once." % ", ".join(duplicates),
            user_text="Es wurde keine Freigabe erteilt: in der Liste steht derselbe Eintrag "
                      "mehrfach. " + NEXT_START_OVER)
    blockers = batch_walk_blockers(state, VERIFICATION_KIND, ids)
    if blockers:
        raise ApprovalError(
            "%d of %d listed items cannot be closed by this approval, so the question is not "
            "asked: %s" % (len(blockers), len(ids), " | ".join(blockers)),
            user_text="Es wurde keine Freigabe erteilt: %d der %d Einträge in der Liste sind noch "
                      "nicht abschließbar — dein Assistent muss sie aus der Liste nehmen oder die "
                      "fehlende Messung nachholen. %s"
                      % (len(blockers), len(ids), NEXT_START_OVER))
    records = []
    # THE SAME RECORD THE BLOCKERS JUDGED, and that identity is the whole point: `batch_walk_blockers`
    # accepts the batch on the Evidence whose `related` NAMES the item, so storing a different one
    # in the question would show the user a proof nobody checked. Measured on the real store: with
    # `report.qa_verdicts` here, BUG-0075's line carried EVD-0312 -- the run that measured its
    # CHILD BUG-0082, which `evidence_covers` accepts through the hop and this question must not.
    naming = {}
    for one in sorted({parse_id(one)[0] for one in ids}):
        naming.update(proofs_naming(state, ids, CONFIRMING_EVIDENCE.get(one)))
    for item_id in ids:
        item = state.read_item(item_id)
        verdict = naming.get(item_id, {})
        records.append({
            GOAL_ITEM_FIELD: item_id,
            "revision": item.get("revision"),
            GOAL_SCOPE_HASH_FIELD: listed_content_hash(item),
            LISTED_EVIDENCE_FIELD: str(verdict.get("id") or ""),
        })
    return sorted(records, key=lambda record: record[GOAL_ITEM_FIELD])


def verification_subject_manifest(bugs) -> dict:
    """The subject of a verification approval: the repaired defects, each with its proof.

    ONE KEY holding the list itself, for `plan_subject_manifest`'s reason -- what the user signs has
    to be what the question shows, and a hash over a count would let the list change underneath a
    matching digest.

    BOUNDED AT `BATCH_LIMIT`, at the builder, before anybody is asked: the ids and their evidence
    ride in the approving option's description, which is the text the gate compares character for
    character, and a question whose list the person answering cannot read through is a reflex click
    on a hundred defects. An EMPTY one is refused for the reason a routine bound to nothing is --
    it would be a permission bound to no item at all.
    """
    bugs = [dict(record) for record in (bugs or []) if isinstance(record, dict)]
    if not bugs:
        raise ApprovalError(
            "a verification approval closes the defects it lists and this batch lists none. "
            "Remedy: name the ids on the command line -- an approval bound to an empty list would "
            "approve nothing and still be minted.",
            user_text="Es wurde keine Freigabe erteilt: die Liste der abzuschließenden Fehler ist "
                      "leer. " + NEXT_START_OVER)
    if len(bugs) > BATCH_LIMIT:
        raise ApprovalError(
            "a batch carries at most %d items and this one carries %d -- refused at the builder. "
            "Remedy: cut the list into batches of %d (`tools/close_measured_pass.py` prints them "
            "that way) and ask one question per batch."
            % (BATCH_LIMIT, len(bugs), BATCH_LIMIT),
            user_text="Es wurde keine Freigabe erteilt: die Liste ist zu lang, um sie in einer "
                      "Frage zu lesen. " + NEXT_START_OVER)
    return {"bugs": bugs}


def _listed_entry(record) -> str:
    """One entry of a list-bound subject as the user reads it in the approving option.

    Tolerant of a record that is not one, and deliberately so: this text is composed from a STORED
    manifest, so a request written before a key existed -- or by anything but the builder -- must
    still render a question rather than raise out of the gate that was about to compare it.
    """
    if not isinstance(record, dict):
        return str(record)
    proof = record.get(LISTED_EVIDENCE_FIELD)
    return ("%s (%s)" % (record.get(GOAL_ITEM_FIELD), proof) if proof
            else str(record.get(GOAL_ITEM_FIELD)))


def _numerus(count: int, one: str, many: str) -> str:
    """The German sentence for this count -- the singular form, or the plural with the number.

    A LIST-BOUND APPROVAL CAN CARRY EXACTLY ONE ENTRY, and German does not let a number stand in
    front of a plural noun for it: "diese 1 Fehler" and "1 Lücken bleiben offen" are what the
    surface printed, in the very sentence a non-developer has to judge -- which is the whole of
    BUG-0271. Both forms are written out by the caller because only the caller knows the nouns;
    what is shared is the rule that the SINGULAR carries no digit at all, which is what
    `tools/test_light_kit.py::test_a_list_bound_question_reads_in_the_right_numerus_and_names_the_same_subject_as_its_card`
    measures.
    """
    return one if count == 1 else many % count


def _verification_target_form(manifest: dict) -> str:
    """The batch as the SENTENCE names it: how many defects, and where their list stands.

    The opposite choice to `_plan_target_form`, and on a measured ground rather than a preference:
    a plan carries a handful of goals and the sentence can hold them, while a verification batch
    carries up to `BATCH_LIMIT` ids WITH their evidence ids. Both texts are compared character for
    character by `gate_approval`, and the one that has to survive the provider's echo whole is the
    approving option -- so the list rides there (`_verification_option_form`) and the sentence says
    how many and where to look. The user is not asked to sign a number: the option beside the
    sentence is the thing that mints, and it names every id.
    """
    bugs = manifest.get("bugs") or []
    return _numerus(
        len(bugs),
        "diesen einen Fehler mit dem Testlauf, der ihn misst — welcher das ist, steht in der "
        "Freigabe-Option darunter",
        "diese %d Fehler, jeder mit dem Testlauf, der ihn misst — welche das sind, steht "
        "Eintrag für Eintrag in der Freigabe-Option darunter")


def _verification_option_form(manifest: dict) -> str:
    """The batch as the APPROVING OPTION carries it: every id with the Evidence that measured it.

    This is the compared carrier (`build_question`'s option description, `gate_approval._mismatch`
    walks every option key), so a relay that drops one id or renames one Evidence changes the text
    and nothing mints. `tools/test_hooks_v2.py::test_a_tampered_option_description_is_blocked_too`
    is that comparison; what this function owes is that every listed id is IN the text at all,
    which is `tools/test_approvals_dispatch.py::test_the_batch_option_names_every_listed_bug_and_its_evidence`.
    """
    bugs = manifest.get("bugs") or []
    listed = "; ".join(_listed_entry(record) for record in bugs)
    return "%s: %s" % (_numerus(len(bugs), "einen gemessen behobenen Fehler",
                                "%d gemessen behobene Fehler"), listed)


# HOW MUCH OF A GAP'S BOUND RIDES IN THE COMPARED OPTION. The option description is the text
# `gate_approval` compares character for character and the provider has to echo whole, and a
# `limits` sentence in this store runs to ~450 characters -- ten of them unabridged is a wall
# nobody reads and a long echo to compare. So the option carries the bound CUT to this width (the
# fold is `_one_line`'s, which is the same one `--reason` goes through), and the sentence beside it
# says where the full one stands. The FULL text is inside the hash either way, through
# `listed_content_hash(item, HOLE_EXCEPTION_KIND)`: a bound edited past the kernel kills the
# acceptance whether or not the edit is inside the shown part.
HOLE_BOUND_SHOWN = 150
# WHAT THE USER READS BESIDE EACH ID, spelled once because two readers need it: the builder writes
# it into the record and the option form prints it.
LISTED_BOUND_FIELD = "bound"


def hole_exception_batch(state: ProjectState, item_ids) -> list:
    """The gaps a hole-exception approval would accept -- refusing BY NAME what it cannot accept.

    THE SECOND BATCH KIND (PR-0012 AC-4), built on `verification`'s shape rather than beside it:
    the same duplicate refusal, the same `batch_walk_blockers` before anybody is asked, the same
    all-or-nothing re-check at mint time, the same `BATCH_LIMIT`. What differs is what each entry
    carries and what the user is therefore signing.

    WHAT MAKES AN ITEM ACCEPTABLE IS THE BOUND AND NOT A HOLE NUMBER, and the first cut of this
    function had it wrong: it refused anything without `HOLE_NUMBER_FIELD`, which would have locked
    out the two defects this very order has to put to the user (BUG-0055 needs a spec decision with
    a migration, BUG-0056 a rule no `PreToolUse` hook can ask today) -- both measured unclosable,
    both with a bound, neither a numbered hole. The shipped per-item form never asked for the number
    either (`item_subject_manifest` hashes it only `if field in item`), so the number was a
    requirement invented here.

    WHAT IS REFUSED, by name and before the question exists: an item with no `HOLE_LIMIT_FIELD`.
    Accepting one would be the user signing "this stays open" with nothing beside it saying what
    takes the place of the protection -- exactly the third state CLAUDE.md's house rule forbids.
    That sentence is also the PROPERTY that tells a gap from a defect: an item states a bound when
    somebody has judged it unclosable and written down what limits it instead.
    `tools/test_approvals_dispatch.py::test_a_gap_without_a_bound_is_refused_from_the_exception_batch_by_name`

    NO EVIDENCE IS ASKED, and that is derived rather than decided here: `batch_walk_blockers` asks
    for the confirming proof only where the walk crosses the type's confirming edge, and this one
    ends on the off-chain terminal instead (`batch_walk_end`). An accepted exception is a USER
    statement about risk; a test would be the other verdict.
    """
    ids = [str(one) for one in (item_ids or [])]
    duplicates = sorted({one for one in ids if ids.count(one) > 1})
    if duplicates:
        raise ApprovalError(
            "a batch names %s twice -- an exception cannot be accepted two times by one answer. "
            "Remedy: list every id once." % ", ".join(duplicates),
            user_text="Es wurde keine Freigabe erteilt: in der Liste steht derselbe Eintrag "
                      "mehrfach. " + NEXT_START_OVER)
    blockers = batch_walk_blockers(state, HOLE_EXCEPTION_KIND, ids)
    if blockers:
        raise ApprovalError(
            "%d of %d listed items cannot be accepted by this approval, so the question is not "
            "asked: %s" % (len(blockers), len(ids), " | ".join(blockers)),
            user_text="Es wurde keine Freigabe erteilt: %d der %d Einträge in der Liste können "
                      "so nicht angenommen werden — dein Assistent muss sie aus der Liste nehmen. "
                      "%s" % (len(blockers), len(ids), NEXT_START_OVER))
    records, unfit = [], []
    for item_id in ids:
        item = state.read_item(item_id)
        stated = item.get(HOLE_LIMIT_FIELD)
        # A BOUND IS A SENTENCE, so a non-string is refused BEFORE it is folded: `_one_line` turns
        # a list or a mapping into its `str()` and the user would sign `['a', 'b']` as the thing
        # that limits the gap. The field has no schema of its own (`backlog_types` declares the
        # name, not the type), so the type question is asked exactly here, where the value becomes
        # text a person reads.
        if stated is not None and not isinstance(stated, str):
            unfit.append("%s states a %s that is not a sentence but a %s -- what the user signs "
                         "has to be readable text. Remedy: give it one through the kernel, the "
                         "body on stdin -- `echo '{\"%s\": \"<what bounds it today>\"}' | ... "
                         "update %s` -- then ask again"
                         % (item_id, HOLE_LIMIT_FIELD, type(stated).__name__,
                            HOLE_LIMIT_FIELD, item_id))
            continue
        bound = _one_line(stated, HOLE_BOUND_SHOWN)
        if not bound:
            # THE REMEDY NAMES THE SHAPE `update` REALLY HAS, and the first cut of this sentence
            # did not: it offered a `--set` flag the parser does not carry, so a role following it
            # got a usage error instead of a route (measured 2026-09-12 against a copy of this
            # repo's own store). `update` reads a JSON body on stdin -- `cli`, the `update` branch.
            unfit.append("%s states no %s -- what takes the place of the protection is the one "
                         "thing an acceptance is FOR, so there is nothing here to sign. Remedy: "
                         "give it one through the kernel, the body on stdin -- "
                         "`echo '{\"%s\": \"<what bounds it today>\"}' | ... update %s` -- then ask "
                         "again" % (item_id, HOLE_LIMIT_FIELD, HOLE_LIMIT_FIELD, item_id))
            continue
        records.append({
            GOAL_ITEM_FIELD: item_id,
            "revision": item.get("revision"),
            GOAL_SCOPE_HASH_FIELD: listed_content_hash(item, HOLE_EXCEPTION_KIND),
            LISTED_BOUND_FIELD: bound,
        })
    if unfit:
        raise ApprovalError(
            # NO SECOND REMEDY HERE: each entry above carries the one that fits it, and a blanket
            # "take them out of the batch" appended to them contradicted the line before it
            # (measured 2026-09-12 against a copy of this repo's store: the refusal told a reader
            # to write the bound AND to drop the item, in one breath).
            "%d of %d listed items are not acceptable gaps, so the question is not asked: %s"
            % (len(unfit), len(ids), " | ".join(unfit)),
            user_text="Es wurde keine Freigabe erteilt: %d der %d Einträge sind keine gemessenen "
                      "Lücken mit einer Begrenzung — dein Assistent muss sie aus der Liste "
                      "nehmen. %s" % (len(unfit), len(ids), NEXT_START_OVER))
    return sorted(records, key=lambda record: record[GOAL_ITEM_FIELD])


def hole_exception_subject_manifest(holes) -> dict:
    """The subject of a hole-exception approval: the gaps, each with what bounds it today.

    `verification_subject_manifest`'s two refusals, for its two reasons -- an EMPTY list would be a
    permission bound to no item at all, and a list longer than `BATCH_LIMIT` is a question the
    person answering cannot read through, which on THIS kind is worse than on the other: what they
    are signing is not "these are repaired" but "these stay open, and this is what limits them".
    """
    holes = [dict(record) for record in (holes or []) if isinstance(record, dict)]
    if not holes:
        raise ApprovalError(
            "a hole-exception approval accepts the gaps it lists and this batch lists none. "
            "Remedy: name the ids on the command line -- an approval bound to an empty list would "
            "accept nothing and still be minted.",
            user_text="Es wurde keine Freigabe erteilt: die Liste der Lücken ist leer. "
                      + NEXT_START_OVER)
    if len(holes) > BATCH_LIMIT:
        raise ApprovalError(
            "a batch carries at most %d items and this one carries %d -- refused at the builder. "
            "Remedy: cut the list into batches of %d and ask one question per batch."
            % (BATCH_LIMIT, len(holes), BATCH_LIMIT),
            user_text="Es wurde keine Freigabe erteilt: die Liste ist zu lang, um sie in einer "
                      "Frage zu lesen. " + NEXT_START_OVER)
    return {"holes": holes}


def _hole_exception_target_form(manifest: dict) -> str:
    """The batch as the SENTENCE names it -- `_verification_target_form`'s reason, one step louder.

    What the user is about to sign is that these gaps STAY OPEN, so the sentence says that in plain
    words rather than counting records, and points at the option where each one stands with its
    bound.
    """
    holes = manifest.get("holes") or []
    return _numerus(
        len(holes),
        "diese eine gemessene Lücke, die damit offen bleibt — mit dem, was an die Stelle des "
        "Schutzes tritt; welche das ist, steht in der Freigabe-Option darunter",
        "diese %d gemessenen Lücken, die damit offen bleiben — je mit dem, was an die Stelle "
        "des Schutzes tritt; welche das sind, steht Eintrag für Eintrag in der Freigabe-Option "
        "darunter")


def _hole_exception_option_form(manifest: dict) -> str:
    """The batch as the APPROVING OPTION carries it: every id with the bound it stands on.

    The compared carrier (`build_question`'s option description, `gate_approval._mismatch` walks
    every option key), so a relay that drops one id or rewrites one bound changes the text and
    nothing mints. What this function owes is that every listed id and its bound are IN the text at
    all: `tools/test_approvals_dispatch.py::test_the_exception_option_names_every_listed_hole_and_its_bound`
    """
    holes = manifest.get("holes") or []
    listed = "; ".join("%s (%s)" % (record.get(GOAL_ITEM_FIELD), record.get(LISTED_BOUND_FIELD))
                       if isinstance(record, dict) else str(record) for record in holes)
    # A NOUN PHRASE, like its twin above -- the card reads "Erteilt die Freigabe ... FÜR <this>",
    # so a main clause lands inside a prepositional phrase: "für 2 Lücken bleiben offen: ..." is
    # what the surface printed (round 2 of TSK-0141's verification, R4). The numerus is the same
    # rule as everywhere else here.
    return "%s: %s" % (_numerus(len(holes), "eine Lücke, die offen bleibt",
                                "%d Lücken, die offen bleiben"), listed)


def routine_subject_manifest(role: str, scope: str, trigger: str, cadence: str) -> dict:
    """What a recurring read-only run is bound to (spec II.2, II.10a): the ROLE the dispatcher
    holds the spawn to, the READ scope, the trigger and the cadence -- the four
    `ROUTINE_MANIFEST_FIELDS`, typed on the `request-approval routine <ROOT>` line; the expiry is
    the kernel's (`create_pending_request`). Built here so the entry point can produce the kind at
    all: until PR-0011 AC-8 it could not (BUG-0266 / H184), and the auditor ran as an ordinary
    order with a writable scope.
    """
    return {ROUTINE_ROLE_FIELD: str(role or ""), "scope": str(scope or ""),
            "trigger": str(trigger or ""), "cadence": str(cadence or "")}


LINE_MANIFEST_BUILDERS = {"push": push_subject_manifest, "preset": preset_subject_manifest,
                          ROUTINE_KIND: routine_subject_manifest,
                          "kit_update": kit_update_subject_manifest,
                          "filing_correction": filing_correction_subject_manifest,
                          "filing_rule": filing_rule_subject_manifest,
                          "document_proposal": document_proposal_subject_manifest,
                          "document_revision": document_revision_subject_manifest,
                          PLAN_KIND: plan_subject_manifest,
                          VERIFICATION_KIND: verification_subject_manifest,
                          HOLE_EXCEPTION_KIND: hole_exception_subject_manifest}

# How long an approval minted from a command-line manifest stays valid, FOR THE KINDS THAT CARRY A
# CLOCK AT ALL. Which those are is `EXPIRING_KINDS` and the caller asks it (`cli`, the
# `request-approval` branch) rather than assuming every line kind expires: `plan` does not, because
# what invalidates it is its own content -- each goal's revision and scope hash -- and
# `create_pending_request` refuses an expiry on a kind that takes none. For the kinds that do, the
# caller must not be the one to choose how long, or the supervised party decides how long its own
# permission lasts.
# One hour, on the reason those kinds share: each is ALREADY bound to content that moves -- a
# push token to HEAD (see `push_subject_manifest`), a preset approval to the role set it names, a
# kit update to the two release identities -- so this clock only bounds how long an UNUSED one
# lingers, and an unused authorisation that outlives the working session is a standing permission
# to publish, to reinstall the project's roles, or to replace its enforcement layer.
LINE_APPROVAL_VALIDITY = 3600.0


def line_manifest_kinds() -> tuple:
    """The APR kinds whose subject manifest a COMMAND LINE can build -- see LINE_MANIFEST_BUILDERS."""
    return tuple(sorted(LINE_MANIFEST_BUILDERS))


def item_subject_manifest(item: dict, kind: str) -> dict:
    """Deterministic manifest for an item-bound approval kind."""
    if kind == "scope":
        manifest = {k: item.get(k) for k in _SCOPE_FIELDS if k in item}
        manifest["item"] = item["id"]
        manifest["revision"] = item.get("revision")
        return manifest
    if kind == "acceptance":
        return {
            "item": item["id"],
            "revision": item.get("revision"),
            "delivered_commit": item.get("delivered_commit"),
            "evidence_refs": item.get("evidence_refs", []),
        }
    if kind == HOLE_EXCEPTION_KIND:
        # WHAT THE USER IS SIGNING, and it is deliberately more than the id: an acceptance of a gap
        # is an acceptance of a described gap. The mechanism (`observed`), what should happen
        # instead (`expected`), how serious it is (`severity`) and -- the field this kind exists
        # for -- what takes the place of the protection (`HOLE_LIMIT_FIELD`) are all in the hash,
        # so an edit to any of them past the kernel kills the acceptance rather than riding on it.
        manifest = {field: item.get(field)
                    for field in ("title", "observed", "expected", "severity",
                                  HOLE_LIMIT_FIELD, HOLE_NUMBER_FIELD)
                    if field in item}
        manifest["item"] = item["id"]
        manifest["revision"] = item.get("revision")
        return manifest
    if kind == "delivery":
        return {
            "item": item["id"],
            "root_revision": item.get("revision"),
            "system_requirements": item.get("system_requirements", []),
            "architecture": item.get("architecture_refs", []),
            "tasks": item.get("planned_tasks", []),
            "risks": item.get("risks", []),
        }
    raise ApprovalError(
        "kind %r is not item-derived (analysis/routine/push take an explicit "
        "manifest -- for push, build it with `push_subject_manifest`). Remedy: "
        "pass `manifest=` to create_pending_request." % kind,
        user_text="Es wurde keine Freigabe erteilt: die gespeicherte Freigabe-Anfrage nennt eine "
                  "Freigabe-Art, zu der das Programm keinen Inhalt bilden kann. " + NEXT_START_OVER
    )


# -- which transitions a Freigabe GUARDS (spec II.2 Statusautomaten + Freigaben) ----------------

def required_approval_kinds(item_type: str, from_status: str, to_status: str) -> frozenset:
    """The approval kinds that COMMIT this transition -- i.e. the ones whose mint walks it.

    DERIVED BY INVERTING `APPROVAL_TRANSITIONS`, and that is the whole design. That map already
    answers "which approval kind commits which edge" -- `mint` walks the edge with it the moment
    the user approves -- so the same table read the other way round answers "which edge may only
    be walked when such an approval exists". A constant of the shape `{"APPROVED": "scope"}` would
    be a SECOND statement of the same fact, and every second statement in this kernel has fallen
    behind its original: a new (item type, kind) pair added above therefore arrives here gated,
    and a pair removed there stops gating, with nothing to remember.

    AN EDGE NO KIND MAPS TO IS NOT APPROVAL-BOUND, and that is the same derivation rather than a
    list of exemptions. Checked against spec II.2 rather than assumed, the answers are:
      * no edge of the TSK automaton -- no kind's manifest describes a task's progress; those
        edges are moved by the lease lifecycle and `submit_result`, and the one rule that does
        guard a TSK edge (FAILED -> READY only on an approved retry) lives in `state.transition`
        because its evidence is a caller argument, not an APR.
      * SR (PROPOSED -> ACCEPTED) -- an SR is a technical contract under a root, and no manifest
        in `item_subject_manifest` describes one. Reported, not bridged: if accepting an SR is to
        need a user approval, it needs a KIND with a manifest first, and that is a spec decision.
      * no edge INTO a terminal state except `ACCEPTED` -- discarding work is not approving it,
        and gating a terminal would make an item unabandonable. The cost of that is real and is
        named where a role reads it (`scripts/harness.py`): a root item can still be dropped.
      * nothing on DEC or INV -- they are `_NON_AUTOMATON_INITIAL_STATUS`, so `assert_transition`
        refuses every transition on them before this is ever asked.

    WHAT "COMMITS" IS NOT, and the difference is measurable: the map pairs a kind with an edge, it
    does not promise that the kind's manifest describes the item's content. For `PROC` and `SR` it
    does not (see `_SCOPE_FIELDS`), so a scope approval there binds to `{item, revision}` -- the
    gate still holds, the CONTENT hash behind it is thinner than the name suggests.
    """
    return frozenset(kind for (typ, kind), edge in APPROVAL_TRANSITIONS.items()
                     if typ == item_type and edge == (from_status, to_status))


# The item field the kernel stamps with `approved_content_hash` at mint time. Spec II.2 lists it
# among a PROC's fields; nothing there forbids another type carrying it, and the kernel writes it
# wherever it is computable (see `approved_content_hash`) rather than for one type by name.
APPROVED_CONTENT_HASH_FIELD = "approved_hash"


def approved_statuses(item_type: str) -> frozenset:
    """The statuses an item stands in BECAUSE a user approved it, and has not left again.

    DERIVED FROM `APPROVAL_TRANSITIONS` AND THE TYPE'S OWN CHAIN, for the reason
    `required_approval_kinds` gives one function up: a hand-written `("APPROVED", "ACTIVE")` beside
    the automaton is a second statement of what the automaton already says, and every second
    statement in this kernel has fallen behind its original. Read this way the answer is one
    sentence of graph: an approval walks the item onto some status of its chain, and every LATER
    chain status is still that same approved run of the item -- `PROC` DRAFT -> APPROVED -> ACTIVE
    is exactly the "approved, then in use" pair the office gate needs, with nothing enumerated.

    A TERMINAL IS SUBTRACTED ONLY WHEN NO APPROVAL PUT IT THERE, and getting that condition wrong
    made this function contradict its own first sentence for five types out of six. Subtracting
    every terminal is right for `RETIRED` (a procedure the project stopped running, and a gate that
    let a work order execute it would read a tombstone as a permission) and wrong for `ACCEPTED`,
    which is exactly the status an `acceptance` approval commits -- so a blanket subtraction
    answered "a PR is not in an approved status" about the one status a user signed for. `PROC` is
    the only type whose terminals all lie OFF its chain, which is why the mistake was latent: its
    consumer today is the office spawn gate, and there the two readings agree.

    A type nothing approves, or one with no automaton at all (`DEC`, `INV`), answers with the empty
    set -- there is no status it holds because of an approval.
    """
    auto = AUTOMATA.get(item_type)
    if auto is None:
        return frozenset()
    reached = set()
    approved_targets = set()
    for (typ, _kind), (_source, target) in APPROVAL_TRANSITIONS.items():
        if typ != item_type:
            continue
        approved_targets.add(target)
        # THE TARGET ITSELF, whether or not it lies on the chain. Until 2026-09-04 only chain
        # targets were collected, because every approved edge then ended on one -- so the first
        # approval committing an OFF-CHAIN status (`BUG` -> `ACCEPTED_EXCEPTION`, FR-0087) made
        # this function answer "no approval put it there" about the one status a user had just
        # signed for. That is the same contradiction of its own first sentence the paragraph above
        # records for the blanket terminal subtraction, one edge shape further out.
        # `tools/test_approvals_dispatch.py::test_a_status_an_approval_commits_is_an_approved_status`
        reached.add(target)
        if target in auto.chain:
            reached.update(auto.chain[auto.chain.index(target):])
    return frozenset(reached) - (auto.terminals - approved_targets)


def approved_content_hash(item_type: str, item: dict):
    """The canonical hash over the fields whose change invalidates this item's approval, or None.

    THE SUBJECT IS `HASHED_FIELDS`, which is the kernel's own answer to "which fields of this type
    are approval-relevant". So this is not a second opinion about what an approval covers -- it is
    the same list, hashed, and a type that declares none (`INV`, `DEC`, `FR`, `TSK`, `EVD`) has
    nothing to record and gets None.

    WHY IT EXISTS BESIDE `subject_manifest_hash(item_subject_manifest(...))`, which looks like the
    same thing and is not: the scope manifest carries `_SCOPE_FIELDS`, and the comment there
    measures the overlap -- for `PROC` it is 0 of 2, so an approved PROC's `steps` and `roles` sit
    outside every hash the approval record itself keeps. Widening `_SCOPE_FIELDS` would change
    every stored hash and kill every live approval, which is the migration that comment refuses to
    slip in. A SEPARATE field changes no stored hash at all: the approval record stays exactly as
    it was, and the item gains a stamp of what was approved.

    WHAT THAT BUYS, stated no wider than it is: an out-of-band edit -- one that goes past the
    kernel, so no revision is bumped and no approval is invalidated -- leaves the stamp behind
    disagreeing with the content. `gate_proc_approved` refuses a spawn on that disagreement and
    `report.validate_state` reports it. It is NOT read by `assert_apr_in_force`, so such an edit
    does not by itself stop a dispatch or a transition; that would be a widening of the
    authorisation path and is named here rather than done quietly.

    AND WHAT IT DOES NOT BUY, because the sentence above is exactly the shape that gets read as
    more: this is an UNKEYED hash of public content by a public function, so anyone who can write
    the item file can write the matching stamp with it. Measured: edit an approved PROC's steps,
    recompute, write both -- spawn rc 0 and `validate` rc 0, no finding anywhere. It detects an
    edit that did not bother, not an edit that did. The same limit `proven_expiry` records for the
    approval manifest, and it closes the same way: by keeping the state directory kernel-only for
    tool writes (gate layer 3), never by arithmetic.
    """
    fields = HASHED_FIELDS.get(item_type)
    if not fields:
        return None
    return subject_manifest_hash({name: item.get(name) for name in fields})


def listed_items(request: dict) -> tuple:
    """The item ids this subject manifest LISTS, in the order it lists them -- () when it lists none.

    WHAT MAKES A VALUE A LIST OF ITEMS is a property of the record, not a table of kinds: an entry
    counts when it carries the item id AND the content hash the user signed FOR that id
    (`GOAL_ITEM_FIELD`, `GOAL_SCOPE_HASH_FIELD`). That pair is exactly what turns a mapping inside a
    manifest into a signed statement about an item, and no other builder here produces one -- the
    lists the other kinds carry hold strings (`tasks`, `roles`, `document_types`) or records of
    something that is not an item. So `assert_apr_in_force` can ask the record in front of it
    whether this approval binds a LIST or one item, and a third list-bound kind needs no entry
    anywhere. `tools/test_approvals_dispatch.py::test_only_a_manifest_of_signed_item_records_reads_as_a_list`

    THE HASH-COVERED COPY IS THE ONE READ in every caller: they pass the CONSUMED request, which is
    what `consumed_request` proves provenance from, so the list walked here is the list the user
    signed rather than a copy anybody could edit afterwards.
    """
    listed = []
    for value in (request.get("subject_manifest") or {}).values():
        if not isinstance(value, (list, tuple)):
            continue
        for record in value:
            if (isinstance(record, dict) and record.get(GOAL_ITEM_FIELD)
                    and record.get(GOAL_SCOPE_HASH_FIELD)):
                listed.append(str(record[GOAL_ITEM_FIELD]))
    return tuple(listed)


def _assert_the_list_covers(request: dict, item: dict) -> None:
    """Raise unless the LIST behind `request` still covers `item` at its current content.

    THE HASH-COVERED COPY IS THE ONE READ. `request` is the CONSUMED request, which is what
    `consumed_request` proves the approval's provenance from and which spec II.2 keeps forever --
    the APR file itself carries only the digest. So the list this walks is the list the user
    signed, not a copy anybody could edit afterwards.

    THREE WAYS A COVERED ITEM STOPS BEING ONE, and each is the same invalidation a per-item
    approval has: the item is not in the list at all (captured after the list was approved), the
    kernel has moved it to another revision, or its scope content changed -- the last one measured
    with `listed_content_hash`, i.e. the very hash a single scope approval binds to. What that
    leaves open is what it leaves open there too (see `_SCOPE_FIELDS`): an out-of-band edit of a
    field the scope manifest does not carry.

    ONE CHECK FOR BOTH LIST-BOUND KINDS (`plan` since FR-0074, `verification` since PR-0012), which
    is why it reads `listed_items` rather than the key `goals`: two copies of an invalidation rule
    is how the second list-bound kind would come to be invalidated less than the first, and the
    difference would show only as an approval that went on covering an item it no longer described.
    `tools/test_approvals_dispatch.py::test_a_plan_stops_covering_a_goal_the_moment_its_scope_moves`
    and `::test_a_batch_stops_covering_a_bug_whose_content_moved_after_the_question`.
    """
    listed = {}
    for value in (request.get("subject_manifest") or {}).values():
        if not isinstance(value, (list, tuple)):
            continue
        for record in value:
            if isinstance(record, dict) and record.get(GOAL_ITEM_FIELD):
                listed[str(record[GOAL_ITEM_FIELD])] = record
    # EVERY ONE OF THE THREE SPEAKS TO THE USER TOO. These refusals reach the person who just
    # CLICKED -- a list approval is answered by a human, and the walk then stops -- so a message
    # addressed only to a role leaves them with a screen full of ids and no idea what happened.
    # Measured: all three stood without a `user_text` and `test_every_approval_refusal_the_hook_can
    # _surface_speaks_to_the_user` named them by line number.
    record = listed.get(item["id"])
    if record is None:
        raise ApprovalError(
            "the approved list does not name %s (it names %s), so it approves nothing about this "
            "item. Remedy: an item captured after the list was approved needs its own approval, "
            "or a fresh one over the current list."
            % (item["id"], ", ".join(sorted(listed)) or "no item at all"),
            user_text="Es wurde nichts abgeschlossen: einer der Punkte stand gar nicht auf der "
                      "Liste, die du freigegeben hast — er ist erst danach dazugekommen. Dein "
                      "Assistent muss dir die Liste noch einmal vorlegen. " + NEXT_START_OVER)
    if record.get("revision") != item.get("revision"):
        raise ApprovalError(
            "the approved list covers %s at revision %s and the item is at %s -- it no longer "
            "describes it. Remedy: re-run the approval over the current list."
            % (item["id"], record.get("revision"), item.get("revision")),
            user_text="Es wurde nichts abgeschlossen: einer der Punkte auf deiner Liste ist "
                      "inzwischen in einer neueren Fassung — die Liste beschreibt ihn nicht mehr. "
                      "Dein Assistent muss dir die aktuelle Liste noch einmal vorlegen. "
                      + NEXT_START_OVER)
    if listed_content_hash(item, request.get("kind")) != record.get(GOAL_SCOPE_HASH_FIELD):
        raise ApprovalError(
            "the content of %s changed since the list was approved -- an out-of-band edit "
            "invalidated its cover for this item (spec II.4 gate 4). Remedy: re-run the "
            "approval, or restore the approved content." % item["id"],
            user_text="Es wurde nichts abgeschlossen: der Inhalt eines Punktes wurde geaendert, "
                      "nachdem du die Liste freigegeben hattest — deine Zustimmung galt dem alten "
                      "Text. Dein Assistent muss dir die Liste neu vorlegen. " + NEXT_START_OVER)


def live_list_approval(state: ProjectState, item: dict, kind: str):
    """The list-bound approval of `kind` in force for this item, or None.

    ONE VALIDITY TEST, not a second one: this walks the stored approvals and asks
    `assert_apr_in_force`, exactly as `assert_transition_approved` does for the item-bound kinds.
    An approval that is revoked, unprovable, expired or no longer describing this item simply does
    not answer, and the caller reports "no approval in force" the way it always did.
    """
    for apr in _stored_approvals(state):
        if apr.get("kind") != kind:
            continue
        try:
            assert_apr_in_force(state, apr, item)
        except ApprovalError:
            continue
        return apr
    return None


def live_plan_approval(state: ProjectState, item: dict):
    """The plan approval in force for this item, or None -- the FR-0074 stand-in for `scope`.

    NOT ASKED FIRST. `assert_transition_approved` looks for the item's OWN approval before it comes
    here, so a per-goal approval still wins where one exists -- the plan is the fallback that makes
    the goal walkable without one, never a replacement for the specific record.
    """
    return live_list_approval(state, item, PLAN_KIND)


def assert_apr_in_force(state: ProjectState, apr: dict, item: dict) -> dict:
    """Raise unless this approval authorises anything about this item RIGHT NOW; return its request.

    ONE definition of "in force", because two readers need it and they used to be one reader with
    a private copy: the dispatch gate asking whether a root's current approval still authorises a
    spawn (`dispatch._assert_root_approval_locked`), and the status automaton asking whether an
    approval of the required kind exists for an edge (`assert_transition_approved`). The questions
    differ -- which APR is looked at, and whether the kind is fixed -- but the validity test is the
    same one, and a copy of it would drift exactly as `report._parents_of` did.

    The five ways an approval that EXISTS still grants nothing, in the order a reader wants them:
    it was revoked; its provenance cannot be proven (`consumed_request` -- a hand-written APR is
    just a file); it belongs to another item; its clock ran out; the item's hashed content moved
    since it was minted. The messages stay fact-first and remedy-second, and the callers add their
    own consequence ("dispatch blocked", "transition refused") around them -- a message that names
    one caller's consequence inside a shared check is how the last such helper became two.
    """
    apr_ref = apr.get("id")
    if apr.get("revoked"):
        raise ApprovalError(
            "approval %s is revoked. Remedy: obtain a fresh approval." % apr_ref)
    # provenance first: an approval that cannot show its minted request is not a user approval at
    # all, whatever else it says (spec II.12)
    request = consumed_request(state, apr)
    if listed_items(request):
        # AN APPROVAL BOUND TO A LIST, NOT TO ONE ITEM (`plan` FR-0074, `verification` PR-0012), so
        # the item test is the one below and the content test is inside it -- each listed item's own
        # scope hash. Everything else about "in force" is the same for both shapes, which is why
        # this is a branch here rather than a second function beside it. The condition asks the
        # stored MANIFEST whether it lists signed item records, not which kind wrote it, so the
        # next such kind arrives covered.
        _assert_the_list_covers(request, item)
    elif str(apr.get("item") or "") != item["id"]:
        raise ApprovalError(
            "approval %s belongs to %r, not to %s. Remedy: obtain an approval for this item."
            % (apr_ref, apr.get("item"), item["id"]))
    expires = proven_expiry(request)
    if expires is not None and expires < time.time():
        raise ApprovalError(
            "approval %s expired (spec II.10a: an expired approval blocks). Remedy: renew the "
            "approval." % apr_ref)
    kind = apr.get("kind")
    if kind in ("scope", "acceptance", "delivery"):
        current = subject_manifest_hash(item_subject_manifest(item, kind))
        if current != apr.get("subject_manifest_hash"):
            raise ApprovalError(
                "content hash of %s no longer matches approval %s -- an out-of-band edit "
                "invalidated the approval (spec II.4 gate 4). Remedy: re-approve the current "
                "revision, or `git restore %s` to return to the approved content."
                % (item["id"], apr_ref,
                   os.path.relpath(state.active_path(item["id"]), state.root)))
    return request


def _names_the_item(state: ProjectState, apr: dict, item: dict) -> bool:
    """Is this approval's own subject about this item at all -- the id test, for BOTH shapes.

    The cheap pre-filter `assert_transition_approved` walks the approval store with, generalised
    from `apr["item"] == item["id"]` the moment an approval could bind a list instead (PR-0012). It
    is deliberately only the ID test: whether such an approval is still IN FORCE is
    `assert_apr_in_force`'s answer, and the caller wants the two apart so a revoked or invalidated
    approval that really does name this item lands in its refusal message by name instead of being
    skipped in silence.

    THE ITEM FIELD IS ASKED FIRST because it also bounds the cost: an item-BOUND approval never
    carries a list, so only the item-less ones pay for reading their consumed request back.
    `tools/test_approvals_dispatch.py::test_a_batch_approval_authorises_only_the_bugs_it_lists`
    """
    if apr.get("item"):
        return str(apr["item"]) == item["id"]
    try:
        request = consumed_request(state, apr)
    except ApprovalError:
        return False        # no provable request, no subject -- fail-closed
    return item["id"] in listed_items(request)


def assert_transition_approved(state: ProjectState, item: dict, item_type: str,
                               from_status: str, to_status: str):
    """Refuse a transition the user has to authorise and did not. Returns the APR, or None.

    THE HOLE THIS CLOSES, measured 2026-07-29 in a scaffolded project: `python
    scripts/harness.py transition PR-0002 APPROVED` walked a root item out of its DRAFT past all
    eight PreToolUse gates, with a specialist's `agent_type` in the payload as readily as without
    one -- while `gate_git` refuses a merge for an item still in its initial status ON THE GROUND
    THAT NOTHING APPROVED THE WORK. A status the supervised party can set itself proves nothing,
    so the gate that reads it was resting on a value its own subject could write.

    Called from `state._transition_locked`, i.e. from EVERY transition including the one `mint`
    performs -- there is deliberately no parameter that turns it off. Spec II.4 is explicit that
    bootstrap "ist kein Config-Flag (der Lead könnte sein eigenes Gate umgehen)", and a `force=` a
    caller may pass is that flag with a different name. The mint passes this check the ordinary
    way, because it writes the APR and consumes its request BEFORE it walks the edge.

    THE SEARCH IS OVER THE APPROVAL STORE, not over `item.approval_ref`, and the two are different
    questions. `approval_ref` holds the LAST approval minted for an item -- an item legitimately
    collects several of different kinds, and the newest one overwrites the field -- so reading it
    would answer "was the most recent approval of this kind" instead of "is an approval of this
    kind in force", which is what spec II.2 binds to (kind + item + revision + content hash).

    WHAT THAT LEAVES OPEN, named because the same property is what makes it possible: the SEQUENCE
    spec II.3 builds is not enforced. An approval binds to (kind, item, revision, content hash)
    and to nothing about WHEN it was given, so all three of a root's approvals can be minted while
    the item is still DRAFT -- `delivery` and `acceptance` have no status effect there (their
    source states are APPROVED and DELIVERED), `scope` then walks DRAFT -> APPROVED, and
    IN_DELIVERY / DELIVERED / ACCEPTED follow with no further question. Measured 2026-07-31, each
    step rc 0, and since `request-approval` shipped the whole sequence is reachable FROM A ROLE'S
    COMMAND LINE -- three request/answer cycles in DRAFT, then three transitions. Before that
    command it needed a library call, which is worth saying plainly: closing the entry hole made
    this one walkable.
    It is not a forgery: a user really answered three questions. It is that the questions were
    answerable at a moment when their subject could not have been meaningful -- `delivery`'s
    manifest names `system_requirements`, `architecture_refs`, `planned_tasks`, `risks` and
    `acceptance`'s names `delivered_commit`, `evidence_refs`, and NO command on this surface
    produces any of them, so what the user signs in DRAFT is byte-identical to what they would
    sign after delivery.

    THE OBVIOUS CLOSURE -- "an approval authorises an edge only if it was minted while the item
    stood in that edge's SOURCE status" -- is derivable and NOT taken here, on ONE ground: the
    minting status would have to live inside the HASHED manifest to be tamper-evident, and adding
    a field to a manifest changes every stored hash and kills every live approval, so it is a spec
    decision with a migration attached rather than an implementation detail.
    A second ground was offered and does not hold, so it is retracted rather than left standing:
    "it would forbid a legitimate re-approval". It would not. The rule binds only
    `assert_transition_approved`, which runs when an edge is WALKED; re-approving an already
    walked edge authorises nothing either way, and after an invalidation `INVALIDATION_TARGET`
    puts the item back into the source status anyway. What the rule would really forbid is
    pre-minting -- which is the thing to forbid.
    """
    kinds = required_approval_kinds(item_type, from_status, to_status)
    if not kinds:
        return None
    rejected = []
    approvals_dir = os.path.join(state.root, "approvals")
    names = sorted(os.listdir(approvals_dir)) if os.path.isdir(approvals_dir) else []
    for name in names:
        if not (name.startswith("APR-") and name.endswith(".yaml")):
            continue
        try:
            apr = state._read_yaml(os.path.join(approvals_dir, name))
        except Exception:
            continue        # an unreadable approval authorises nothing (fail-closed)
        if not isinstance(apr, dict) or apr.get("kind") not in kinds:
            continue
        if not _names_the_item(state, apr, item):
            continue
        try:
            assert_apr_in_force(state, apr, item)
        except ApprovalError as exc:
            # named rather than swallowed: a revoked or content-invalidated approval is the case a
            # role hits most often, and "no approval at all" would send it looking for the wrong
            # thing
            rejected.append("%s (%s): %s" % (apr.get("id") or name[:-5], apr.get("kind"), exc))
            continue
        return apr
    if PLAN_COVERED_KIND in kinds:
        # THE PLAN-LEVEL STAND-IN (FR-0074), and it is reached only after the item's OWN approvals
        # were looked for and found wanting: a per-goal approval is the more specific record and
        # keeps winning. What a plan approval may stand in for is `PLAN_COVERED_KIND` and nothing
        # else -- the delivery side of every goal keeps asking the user, which is the counterweight
        # this decision's own consequences name.
        plan = live_plan_approval(state, item)
        if plan is not None:
            return plan
    # THE REMEDY NAMES THE COMMAND AND THE KIND, and the second half is not decoration: the KIND
    # is derived per edge, and a role that guesses it guesses wrong on the edges where the name of
    # the status does not match the name of the kind. `EXP DESIGNED -> APPROVED` is committed by a
    # `delivery` approval, and "run the approval flow" sent a role to `request-approval scope EXP-…`
    # -- a request that opens, mints, and still does not walk the edge. Spelled from `kinds`, so an
    # (item type, kind) pair added to APPROVAL_TRANSITIONS arrives here correctly named.
    wanted = sorted(kinds)
    raise ApprovalError(
        "%s %s -> %s is the transition a %s approval commits, and none is in force for %s at "
        "revision %s -- refused (fail-closed). A status the supervised party can set itself is a "
        "status no gate may read as approval.%s Remedy: run `python scripts/harness.py "
        "request-approval %s %s`%s and relay the printed question to the user VERBATIM -- their "
        "answer mints the approval AND walks this transition, so there is nothing left to "
        "transition by hand afterwards.%s%s"
        % (item["id"], from_status, to_status, "/".join(wanted), item["id"],
           item.get("revision"),
           (" The approvals that name this item do not count: %s." % "; ".join(rejected))
           if rejected else "",
           wanted[0], item["id"],
           "" if len(wanted) == 1
           else " (or %s in place of %s -- either kind commits this edge)"
                % ("/".join(wanted[1:]), wanted[0]),
           # THE OTHER ROUTE TO THE SAME EDGE, named last so the per-goal command stays the first
           # thing a role reads: a plan approval covers this transition for every goal it lists
           # (FR-0074), which is the one question a whole plan can answer at once.
           (" One `%s` approval over the confirmed goal list covers this edge for every goal it "
            "lists (`python scripts/harness.py request-approval %s`), and after it the scope "
            "question is not asked per goal again." % (PLAN_KIND, PLAN_KIND)
            if PLAN_COVERED_KIND in kinds else ""),
           _unwired_mint_note(state))
    )


def _unwired_mint_note(state: ProjectState) -> str:
    """The sentence a project earns when the remedy above cannot reach its own end -- or "".

    WHY IT IS APPENDED RATHER THAN REPLACING THE REMEDY: the first half of that route runs
    everywhere. `request-approval` is pure kernel and writes the pending request in any project.
    It is the SECOND half -- "their answer mints the approval" -- that is a promise about a hook,
    and where the provider runs no such hook the user can answer all day and nothing reads it.
    Measured 2026-08-30 in this harness repository, which registers no approval gate:
    `request-approval scope BUG-nnnn` rc 0, question printed, and no surface anywhere that consumes
    an `AskUserQuestion` answer.

    THE READER IS THE REGISTRATION, not the presence of a file (`report.approval_mint_is_wired`),
    because a hook that is installed and unregistered is a hook the provider never runs. That the
    two answers really differ is `tools/test_report.py::
    test_the_mint_is_wired_by_the_registration_and_not_by_the_file_lying_there`.

    IT SAYS WHAT DOES NOT HAPPEN AND CLAIMS NOTHING ABOUT WHAT CANNOT, and the sentence below is
    held to exactly that: an unwired project is one that does not tell the provider to run the
    minting hook, so no ANSWER of the user's reaches one. It does not say a mint is impossible.
    Whether some other caller can still reach `mint` is `_assert_minting_caller`'s subject -- its
    docstring records that a hand-run hook with a stdin payload does, and the shipped `known_hole`
    tests assert it.

    BOTH DIRECTIONS THE READER USED TO GET WRONG ARE CLOSED (BUG-0173): a quoted absolute path
    containing a SPACE is one word to it now, so this sentence is no longer printed at a project
    that mints; and a path that RESOLVES to a file which is not there reads `False`, so the
    sentence is printed where nothing runs. What stays undecided is stated where it is decided --
    `report._runs_no_file` leaves a word carrying a variable other than the project directory
    alone, because the shell state that word belongs to is not this process's.
    """
    from . import report      # deferred: `report` imports this module at its own scope
    if report.approval_mint_is_wired(os.path.dirname(state.root)):
        return ""
    return (" THAT ROUTE DOES NOT REACH ITS END HERE: this project's own hook registration runs no "
            "%s on %s(%s), so nothing is set up to read the answer the user gives -- the request "
            "opens and the question prints, and that is all. Report the gap instead of walking the "
            "item by hand; what a delivery has already closed is derived from the Evidence "
            "(DEC-0051)." % (APPROVAL_HOOK, APPROVAL_MINT_EVENT, APPROVAL_QUESTION_TOOL))


def item_derived_kinds() -> tuple:
    """The APR kinds whose subject manifest can be built from an ITEM ALONE.

    Asked of `item_subject_manifest` rather than restated: that function is what decides it, by
    raising for every kind it cannot derive. `cli` needs exactly this set (a command line can
    carry an item id; it cannot carry an analysis question, a read-only scope and a cadence), and
    the alternative spelling -- `APR_KINDS - EXPIRING_KINDS` -- is a THIRD statement of the same
    split that happens to agree today. One probe item, no list.
    """
    probe = {"id": "PR-0001", "revision": 1}
    derived = []
    for kind in APR_KINDS:
        try:
            item_subject_manifest(probe, kind)
        except Exception:
            # EVERY exception, not just ApprovalError, and the difference is the whole CLI. This
            # runs inside `build_parser()`, so anything escaping it kills every command including
            # `doctor` -- measured with a manifest that reads a field the probe lacks: `KeyError:
            # 'contract'` out of `build_parser()` and out of `main([..., "doctor"])`. A diagnosis
            # command that dies on the thing it diagnoses is the failure `cli.py`'s own docstring
            # is written against. A kind that cannot be built from an id alone is simply not
            # item-derived, which is what this function was asked.
            continue
        derived.append(kind)
    return tuple(derived)


def _assert_the_pair_commits_an_edge(item_id: str, kind: str) -> None:
    """An item-derived approval exists only where `APPROVAL_TRANSITIONS` pairs its type with it.

    FAIL-CLOSED, and the measurement is a hypothesis (BUG-0084): on a scaffolded research project
    `request-approval scope HYP-0001` returned rc 0, the mint produced APR-0003, and dispatch
    opened on it. That approval covered nothing at all, and each of the three reasons is a
    property of this pair rather than of that project:
      * (HYP, scope) is in no row of `APPROVAL_TRANSITIONS`, so the mint walked no edge -- the
        approval bought a stamp, not a state;
      * `item_subject_manifest(kind="scope")` intersects `_SCOPE_FIELDS` with the item's fields
        and a HYP shares none, so the user signed a hash over `{item, revision}` and no content;
      * `HASHED_FIELDS` names no HYP field, so `state` never bumps that revision -- every later
        edit of the hypothesis left the signature standing.
    The three compound: an approval that covers no content and can never be invalidated, on an
    item whose automaton nothing gates. Refusing the REQUEST is where it costs least -- the user
    is never shown a question whose answer buys nothing (the shape BUG-0039 records).

    WHAT THIS DOES NOT CLAIM, because the same table says so a few lines up: a pair that IS listed
    still only promises the EDGE, not that its manifest describes the item's content. `PROC/scope`
    and both `delivery` manifests cover one field of their type's hashed set or none -- named at
    `_SCOPE_FIELDS` and at `APPROVAL_TRANSITIONS`, measured over all ten pairs there, and NOT
    closed by this check.

    `tools/test_approvals_dispatch.test_no_item_type_can_be_approved_on_a_kind_that_commits_no_edge`
    holds it against every type of all three kits' automata.
    """
    item_type, _number = parse_id(item_id)
    if (item_type, kind) in APPROVAL_TRANSITIONS:
        return
    available = sorted({pair[1] for pair in APPROVAL_TRANSITIONS if pair[0] == item_type})
    remedy = ("this type carries no user approval at all -- its authorisation rides on the item "
              "it hangs from, so request the approval there"
              if not available else
              "%s takes %s" % (item_type, "/".join(available)))
    raise ApprovalError(
        "no %s approval exists for a %s: the pair commits no transition, so minting one would "
        "record a signature over content nothing re-checks and open nothing. Remedy: %s."
        % (kind, item_type, remedy),
        user_text="Es wurde keine Freigabe erteilt: für diesen Eintrag gibt es diese Art von "
                  "Freigabe nicht. " + NEXT_START_OVER,
    )


def create_pending_request(
    state: ProjectState,
    kind: str,
    item_id: str = None,
    manifest: dict = None,
    ttl_seconds: float = 24 * 3600.0,
    approval_expires: float = None,
) -> dict:
    """Phase 1 of the protocol: persist the immutable pending request.

    `ttl_seconds` bounds how long the QUESTION stays answerable; `approval_expires`
    (epoch seconds, routine/analysis only per spec II.10a) bounds how long the
    resulting APPROVAL stays valid. Two different clocks -- conflating them would
    either expire live approvals or leave routine approvals standing forever.
    """
    if kind not in APR_KINDS:
        raise ApprovalError(
            "unknown APR kind %r. Remedy: use one of %s." % (kind, "/".join(APR_KINDS))
        )
    if kind in EXPIRING_KINDS and approval_expires is None:
        # spec II.2: a routine approval "ist gebunden an Rolle, Read-only-Scope,
        # Trigger, Ablaufdatum und jederzeit widerrufbar", and II.10a: an expired
        # routine approval blocks the audit dispatch. With an OPTIONAL expiry the
        # natural call mints an approval that never expires -- a standing spawn
        # permission, i.e. the one thing the revocable time-boxed design exists
        # to prevent. So it is required.
        raise ApprovalError(
            "kind %r must carry an expiry (spec II.2 Ablaufdatum / II.10a: an "
            "expired routine approval blocks the dispatch). Remedy: pass "
            "approval_expires=<epoch seconds>." % kind
        )
    if approval_expires is not None and kind not in EXPIRING_KINDS:
        raise ApprovalError(
            "only %s approvals carry an expiry (spec II.2); kind %r does not. "
            "Remedy: drop approval_expires -- a scope or delivery approval is "
            "invalidated by content change, not by the clock."
            % ("/".join(sorted(EXPIRING_KINDS)), kind)
        )
    with state.lock:
        revision = None
        if item_id is not None:
            item = state.read_item(item_id)
            revision = item.get("revision")
            if manifest is None:
                # the manifest FIRST, so a kind that is not item-derived at all keeps its own
                # refusal (`item_subject_manifest`) instead of being reported as an unapprovable
                # pair; neither branch has written anything yet
                manifest = item_subject_manifest(item, kind)
                _assert_the_pair_commits_an_edge(item_id, kind)
        if manifest is None:
            raise ApprovalError(
                "kind %r needs an explicit manifest (analysis: question/scope/"
                "expected result/listed tasks; routine: %s plus the expiry; push: "
                "remote/branch/head via `push_subject_manifest`). Remedy: pass "
                "`manifest=`." % (kind, "/".join(ROUTINE_MANIFEST_FIELDS))
            )
        if kind == "routine":
            # see ROUTINE_MANIFEST_FIELDS: a routine bound to nothing is a standing spawn
            # permission, which is the one thing the revocable time-boxed design exists to
            # prevent -- so it is refused before the user is ever asked to sign it
            missing = [field for field in ROUTINE_MANIFEST_FIELDS if not manifest.get(field)]
            if missing:
                raise ApprovalError(
                    "a routine approval must name %s (spec II.2: bound to role, read-only "
                    "scope, trigger and cadence; II.10a hashes all four) -- %s missing. "
                    "Remedy: pass them in `manifest=`; an unbound routine would be a standing "
                    "spawn permission."
                    % ("/".join(ROUTINE_MANIFEST_FIELDS), ", ".join(missing))
                )
        if approval_expires is not None:
            # spec II.10a: the routine approval HASHES role, read-only scope,
            # trigger, cadence AND the expiry date -- so the expiry has to sit
            # inside the hashed manifest, not merely beside it. Otherwise the
            # date could be moved without invalidating the approval.
            manifest = dict(manifest, **{EXPIRY_FIELD: float(approval_expires)})
        request = {
            "request_id": uuid.uuid4().hex,
            "kind": kind,
            "item": item_id,
            "revision": revision,
            # THE ITEM'S TITLE, frozen into the request so the question can name it (BUG-0271:
            # "Freigabe erbeten: scope für PR-0001" showed the user an id) while staying
            # deterministic from the request alone -- the gate rebuilds the question from THIS
            # record, and an item retitled between question and answer must not make the two
            # differ. Absent on requests stored before this field; those show the id.
            "item_title": str(item.get("title") or "") if item_id is not None else "",
            "subject_manifest": manifest,
            "subject_manifest_hash": subject_manifest_hash(manifest),
            "created": _now_iso(),
            "expires_at_epoch": time.time() + ttl_seconds,
            # entropy that lives ONLY in the approval option label (S2b)
            "mint_code": uuid.uuid4().hex[:6],
        }
        state._write_yaml_atomic(_request_path(state, request["request_id"]), request)
        return request


def _render_manifest_value(field: str, value) -> str:
    """One manifest value as the user reads it in the approval question.

    A list is joined rather than repr'd (`['a', 'b']` in a sentence a human has to judge is
    noise), and a missing value is shown as missing rather than as `None`.

    The EXPIRY is rendered as a date, in UTC. As an epoch float it is the one field a human
    cannot judge at all, and it is the field that decides how long a standing spawn permission
    lasts. UTC rather than local time because this string is compared CHARACTER FOR CHARACTER by
    the PreToolUse gate, in a different process: a machine whose timezone changed between the
    request and the answer would otherwise render a different question and the approval could not
    be completed.

    A DIGEST IS SHORTENED, for the expiry's reason and to the same length the sentence around it
    already uses for one: `build_question` prints the subject-manifest hash as twelve characters
    and an ellipsis, so a hashed VALUE reading out in full made the question unreadable exactly
    where a non-technical user has to judge it -- measured on the `kit_update` manifest, whose two
    content hashes are 128 of its ~180 characters. It is a property of the value, not a list of
    fields that carry one, and it is deterministic, which is all the PreToolUse comparison needs.
    The full value stays in the pending request the question names.
    """
    if field == EXPIRY_FIELD:
        try:
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(value)))
        except (TypeError, ValueError, OSError, OverflowError):
            return "unreadable (%r)" % (value,)
    if isinstance(value, (list, tuple)):
        return " / ".join(str(entry) for entry in value) or "-"
    if value is None:
        return "-"
    return "%s…" % str(value)[:DIGEST_SHOWN] if _DIGEST.match(str(value)) else str(value)


def _push_target_form(manifest: dict) -> str:
    """A push approval as the human reads it: WHAT gets published, and where.

    The generic target would read "push" and the human would be asked to authorise publishing
    without being told what. The manifest is already in the request and is hash-covered, so naming
    it here is deterministic (the PreToolUse gate compares this text character for character) and it
    is the whole point of the rule: "explizite Userfreigabe" means the user knew what they released.
    """
    # in the user's words (BUG-0271): what leaves the machine, from which branch, to where
    return "den Stand %s des Zweigs „%s“ nach %s" % (str(manifest.get("head", "?"))[:8],
                                                     manifest.get("branch", "?"),
                                                     manifest.get("remote", "?"))


def _preset_target_form(manifest: dict) -> str:
    """A preset change as the person deciding it reads it: the team AFTERWARDS, and what goes.

    THE GENERIC FORM WAS LITERALLY TRUE AND STILL MISREAD (FR-0027). It rendered the manifest's own
    keys -- `[preset: duo, removes: -, roles: <six names>]` -- and on the upgrade solo->duo most of
    those names are already installed, so a non-technical user reads a list of arrivals and a dash.
    Named as the team the project HAS afterwards, the same list is what the approval actually
    guarantees, and "entfernt" is the half a preset NAME hides completely.

    WHAT IT DELIBERATELY DOES NOT SAY IS WHICH ROLES ARE NEW (DEC-0048), and that is not a wording
    choice. The added set is the target minus what is installed, and WHICH OF THE TARGET ROLES ARE
    ALREADY INSTALLED is the one thing the hashed manifest does not carry. The removed ones it does:
    `removes` is derived from the installation too (`kernel.presets._plan`), so the hash moves with
    the installed state -- just not with the part a delta would be computed from.

    Measured against the shipped dev-team presets: `duo` requested from a solo installation and from
    one that has all the target roles but two produces the SAME subject_manifest_hash while the
    added set differs, and `set-preset` accepts that one approval in either state
    (`test_the_added_roles_are_not_what_a_preset_approval_binds` measures both halves -- the
    manifest, and a real minted approval that still applies after the installation moved). A delta
    printed here would be the one sentence in this question the user signs and the hash does not
    cover.
    """
    return ("die Rollen-Aufstellung '%s' -- danach im Team: %s; entfernt: %s"
            % (str(manifest.get("preset") or "?"),
               ", ".join(str(role) for role in (manifest.get("roles") or [])) or "keine",
               ", ".join(str(role) for role in (manifest.get("removes") or [])) or "keine"))


def _filing_correction_target_form(manifest: dict) -> str:
    """A filing correction as the person deciding it reads it: what happens to which document.

    THE AUDIENCE IS BUG-0041's, and this is the question with the sharpest consequence any of these
    forms carries -- the other side of it is a business document that is gone. So the two outcomes
    are named as what they DO ("wird verschoben nach", "wird gelöscht und ist danach weg") and
    never as the manifest key that distinguishes them (`destination`, empty or not), which would
    ask a non-technical user to notice an absence.

    EVERY HASHED KEY IS RENDERED, which is more than `_push_target_form` and `_preset_target_form`
    manage and is the point of the form existing here at all: the document, the outcome, the reason
    the user was given, the FASSUNG the approval binds (shortened by `_render_manifest_value` like
    every other digest in this question), and the expiry the kernel put into the manifest itself.
    So there is no sentence in this question the hash does not cover, and no key in the hash the
    question does not show -- DEC-0048's rule, taken in its constructive direction.

    The bracket states what the approval is worth and no more: it covers this version of this
    document, and only until its clock runs out. It does NOT promise the command can be run only
    once -- a command that FAILS leaves the document where it was, and there the approval still
    stands. Everything after the outcome is inside ONE bracket because `build_question` puts this
    text into the middle of two sentences of its own; a form built out of full stops read as
    fragments in both of them.
    """
    document = manifest.get("document") or "?"
    destination = manifest.get("destination") or ""
    reason = manifest.get("reason") or "kein Grund angegeben"
    outcome = ("wird verschoben nach »%s«" % destination if destination
               else "wird GELÖSCHT und ist danach weg")
    return ("eine Korrektur der Ablage: das Dokument »%s« %s (Grund: %s; die Freigabe gilt nur für "
            "genau diese Fassung des Dokuments, Prüfsumme %s, und nur bis %s)"
            % (document, outcome, reason,
               _render_manifest_value("content", manifest.get("content")),
               _render_manifest_value(EXPIRY_FIELD, manifest.get(EXPIRY_FIELD))))


# WHICH KINDS GET A FORM BUILT FOR READING, keyed by kind because that is what such a form belongs
# to: each of these manifests is a different subject, and the readable shape of one says nothing
# about another. The generic branch in `build_question` renders the manifest's own keys and stays
# the honest default for every kind with no entry here -- so an entry may only ever shorten the
# distance between what the hash covers and what the user reads, never add to it.
# `test_every_target_form_names_a_live_apr_kind` keeps an entry from outliving its kind.
def _filing_rule_target_form(manifest: dict) -> str:
    """A new Aktenplan rule as the person deciding it reads it: what lands where, named how, kept.

    THE AUDIENCE IS BUG-0041's, and this question is the one that decides where every FUTURE
    document of a class goes -- so it is written as what will happen ("werden ab jetzt … abgelegt")
    rather than as the five manifest keys that say it. EVERY hashed key is rendered, including the
    id (the handle an amendment later names) and the expiry the kernel put into the manifest
    itself: no sentence here the hash does not cover, no key in the hash this does not show.

    The bracket states what the approval is worth and no more: ONE rule ADDED to the plan. It does
    not change an existing rule and it files no document -- `gate_filing` still decides every move
    against the plan as it then stands, which is what makes this a small permission rather than a
    standing one.
    """
    return ("eine neue Regel im Ablageplan (%s): %s werden ab jetzt unter »%s« abgelegt und nach "
            "dem Muster »%s« benannt, Aufbewahrung: %s (Grund: %s; die Freigabe FÜGT diese eine "
            "Regel HINZU, ändert keine bestehende und legt selbst kein Dokument ab, und sie gilt "
            "nur bis %s)"
            % (manifest.get("rule_id") or "?",
               ", ".join(manifest.get("document_types") or []) or "Dokumente",
               manifest.get("path_template") or "?",
               manifest.get("filename_template") or "?",
               # The empty retention is the plan's second honest form and it has to READ like a
               # decision, not like a missing answer -- the question is what the user signs
               # (BUG-0213). `?` stays for a manifest that carries no key at all.
               ("keine zählbare Frist" if "retention" in manifest and not manifest["retention"]
                else manifest.get("retention") or "?"),
               manifest.get("reason") or "kein Grund angegeben",
               _render_manifest_value(EXPIRY_FIELD, manifest.get(EXPIRY_FIELD))))


def _document_proposal_target_form(manifest: dict) -> str:
    """A staged proposal as the person deciding it reads it: which document gains what, and why.

    THE AUDIENCE IS BUG-0041's, and what this question replaces is that user COPYING the staged file
    into the document by hand, four times in one day (BUG-0071). So it is written as what will
    happen to which file, EVERY hashed key is rendered -- both paths, every change descriptor, the
    reason, both checksums and the expiry the kernel put into the manifest -- and no sentence here
    is one the hash does not cover.

    THE BRACKET SAYS WHAT THE APPROVAL IS WORTH AND NO MORE, and one clause of it is a LIMIT rather
    than a reassurance. THE LIMIT IS NARROWER THAN IT READ, and that correction is the point of this
    paragraph: it holds for ENTRIES ADDED TO A LIST and for nothing else. `documents.compare` shows
    a newly FILLED field and a NEW KEY with their value, and a new COMMENT in its wording; only a
    list is summarised as a count, because showing every field of every added record would put the
    file into the card. The sentence used to say "WELCHE Werte hinzukommen" about all of them, so
    one card could carry `tone: gefüllt mit <sentence>` two lines above a clause telling the user
    that no value is in this question -- an untrue reassurance standing beside the very value it
    denied (verifier finding F2, measured on one card).

    WHAT IS NOT UNDER THAT LIMIT IS PROSE, and it is now said in the same clause rather than after
    it. A comment the proposal ADDS stands in the list above in full (folded like every other
    descriptor), because these documents are read by roles as instructions: verifier finding B2
    staged a legitimate fill plus a comment line addressed to "JEDE ROLLE, DIE DIESE DATEI LIEST",
    and the card named the fill and nothing else. A record in a list the user can look up in the
    file; a word written to steer the next reader has to be in the question that authorises it.

    Both directions are measured by
    `tools/test_kernel.py::test_the_card_only_claims_a_value_is_missing_where_the_value_really_is`.
    """
    return ("eine Ergänzung des Dokuments »%s« aus dem Vorschlag »%s«: %s (Grund: %s; die Freigabe "
            "FÜGT nur HINZU -- sie ändert nichts Bestehendes und löscht nichts, auch keinen "
            "Kommentar; sie gilt für genau diese Fassung des Dokuments (Prüfsumme %s) und genau "
            "diesen Vorschlag (Prüfsumme %s), und nur bis %s. WELCHE EINTRÄGE zu einer Liste "
            "hinzukommen, steht in der Vorschlagsdatei und nicht in dieser Frage -- die Freigabe "
            "bindet deren Prüfsumme; alles andere, was neu ist, steht oben im Wortlaut: ein neu "
            "GEFÜLLTES Feld, ein NEUER Schlüssel und ein neu hinzukommender KOMMENTAR, weil ein "
            "Satz in so einer Datei von jeder Rolle gelesen wird, die damit arbeitet)"
            % (manifest.get("kit_document") or "?", manifest.get("proposal") or "?",
               ", ".join(manifest.get("changes") or []) or "nichts",
               manifest.get("reason") or "kein Grund angegeben",
               _render_manifest_value("base", manifest.get("base")),
               _render_manifest_value("proposed", manifest.get("proposed")),
               _render_manifest_value(EXPIRY_FIELD, manifest.get(EXPIRY_FIELD))))


def _document_revision_target_form(manifest: dict) -> str:
    """A staged revision as the person deciding it reads it: what is UNSAID, then what changes.

    THE DELETIONS COME FIRST AND ARE NAMED AS SUCH. A replaced value still leaves a value in the
    document that the user can look at afterwards; a deleted one exists nowhere any more -- there
    is no second copy and no revision number to go back to. That is the loudness FR-0067 asks for,
    and it is structure rather than tone: the card reads the deletions out of their own key of the
    manifest, so a spot cannot be quietly filed under the softer heading.

    EVERY SPOT STANDS IN THE QUESTION, in full and never as a number. That is this card's whole
    reason to exist -- the additive card may name a place because nothing is being unsaid, and
    here it would ask the user to sign the disappearance of a sentence they were never shown. Both
    halves are measured:
    `tools/test_approvals_dispatch.py::test_a_revision_card_shows_every_spot_and_is_never_a_count`
    for the order and the refusal over the bound, and
    `tools/test_kernel.py::test_the_question_a_document_revision_asks_shows_every_field_the_hash_covers`
    for the rule that nothing the hash binds may be missing from the sentence.
    """
    deletions = manifest.get("deletions") or []
    replacements = manifest.get("replacements") or []
    additions = manifest.get("additions") or []
    return ("eine Überarbeitung des Dokuments »%s« aus dem Vorschlag »%s«: %s%s%s (Grund: %s; "
            "diese Freigabe ist die einzige, die etwas ÜBERSCHREIBT oder LÖSCHT, was in dem "
            "Dokument schon steht -- was gelöscht wird, steht danach nirgendwo mehr, und jede "
            "betroffene Stelle steht oben im Wortlaut, alt und neu, niemals als Anzahl. Sie gilt "
            "für genau diese Fassung des Dokuments (Prüfsumme %s) und genau diesen Vorschlag "
            "(Prüfsumme %s), und nur bis %s)"
            % (manifest.get("kit_document") or "?", manifest.get("proposal") or "?",
               ("GELÖSCHT WIRD: %s. " % "; ".join(deletions)) if deletions else "",
               ("ERSETZT WIRD: %s. " % "; ".join(replacements)) if replacements else "",
               ("Außerdem kommt hinzu: %s." % "; ".join(additions)) if additions else "",
               manifest.get("reason") or "kein Grund angegeben",
               _render_manifest_value("base", manifest.get("base")),
               _render_manifest_value("proposed", manifest.get("proposed")),
               _render_manifest_value(EXPIRY_FIELD, manifest.get(EXPIRY_FIELD))))


TARGET_FORMS = {"push": _push_target_form, "preset": _preset_target_form,
                PLAN_KIND: _plan_target_form,
                "filing_correction": _filing_correction_target_form,
                "filing_rule": _filing_rule_target_form,
                "document_proposal": _document_proposal_target_form,
                "document_revision": _document_revision_target_form,
                VERIFICATION_KIND: _verification_target_form,
                HOLE_EXCEPTION_KIND: _hole_exception_target_form}
# WHERE A SUBJECT IS TOO LONG FOR THE SENTENCE, and what carries it instead. `build_question` puts
# the sentence's target into the approving option too, which is right for every kind whose subject
# fits in one line; a kind listed here renders a SECOND, fuller form for the option -- the text
# `gate_approval` compares character for character -- while the sentence stays readable. A kind
# absent from this table renders one text in both places, exactly as before, which is what
# `tools/test_approvals_dispatch.py::test_only_a_kind_with_its_own_option_form_reads_differently_in_the_two_places`
# holds from both ends.
OPTION_FORMS = {VERIFICATION_KIND: _verification_option_form,
                HOLE_EXCEPTION_KIND: _hole_exception_option_form}


def kind_label(kind: str) -> str:
    """The plain-words label of an APR kind, from `KIND_LABELS` -- refused, never invented, for a
    kind the table does not carry (the two-sided tripwire is the test named on the table)."""
    try:
        return KIND_LABELS[kind]
    except KeyError:
        raise ApprovalError(
            "kind %r has no plain-words label in KIND_LABELS, so no question can be composed for "
            "it (BUG-0271: the user is never shown the enum value). Remedy: add the label beside "
            "the kind." % kind,
            user_text="Es wurde keine Freigabe erteilt: für diese Art von Freigabe fehlt dem "
                      "Programm die Bezeichnung in Klartext. " + NEXT_START_OVER) from None


def _item_target(request: dict) -> str:
    """The item as the user reads it: its title in quotation marks with the id behind it, or the id
    alone for a request stored before titles travelled in it."""
    title = str(request.get("item_title") or "")
    return "„%s“ (%s)" % (title, request["item"]) if title else str(request["item"])


def build_question(request: dict) -> dict:
    """The COMPLETE approval question, deterministic from the request alone.

    The model must relay this verbatim; the PreToolUse hook enforces string
    equality of question text, header AND all options for marked questions.

    WHAT STANDS IN THE SENTENCE AND WHAT MOVED OUT OF IT (BUG-0271, PR-0011 AC-7): the sentence
    names the kind in plain words (`KIND_LABELS`), the item by its title (`_item_target`) or the
    manifest with German labels (`MANIFEST_LABELS`), the revision, and the request marker the
    gate resolves the request by -- the one machine token that cannot leave, because
    `gate_approval.MARKER_RX` reads it off the question. The manifest hash and the request's file
    path moved into the DESCRIPTION of the approving option, where the same gate still compares
    them character for character (`_mismatch` walks every option key) --
    `tools/test_hooks_v2.py::test_a_tampered_option_description_is_blocked_too`.
    """
    label = kind_label(request["kind"])
    target = _item_target(request) if request["item"] else label
    # THE KIND'S OWN FORM WINS OVER AN ITEM STANDING BESIDE IT (BUG-0271, round 1 of TSK-0141's
    # verification). This asked "is there an item" first, so a request of a LIST-BOUND kind that
    # carried one described THE ITEM in the sentence while the approving option bound THE LIST --
    # two different subjects in one question, and the option is the thing that mints. A kind with
    # an entry in `TARGET_FORMS` has a form because its subject is not an item; asking the table
    # first is what keeps the two texts about one thing.
    # `tools/test_light_kit.py::test_a_list_bound_question_reads_in_the_right_numerus_and_names_the_same_subject_as_its_card`
    form = TARGET_FORMS.get(request["kind"])
    if form is not None:
        target = form(request.get("subject_manifest") or {})
    elif request["kind"] == ROUTINE_KIND or request["item"] is None:
        # WHAT THE HASH COVERS IS WHAT THE USER IS SHOWN, and the condition is that property rather
        # than the kinds it happens to hold for today. A request whose subject is a MANIFEST -- a
        # routine permission hanging from an item it is not about, or any kind with no item at all
        # -- renders that manifest, because the generic line would otherwise ask the user to sign a
        # bare kind name. This used to name `routine` alone, so every future item-less kind
        # inherited the bare line; `preset` is the one that would have asked a non-technical user
        # to approve the word "team" (BUG-0041). A kind with an entry in `TARGET_FORMS` never
        # reaches here, which is why this branch may widen without changing those questions.
        # A routine approval is a STANDING, recurring spawn permission, and
        # what the dispatch route binds it to is the manifest -- the role first of all. Asked as
        # "Freigabe erbeten: routine für PR-0001" the user was signing a role they were never
        # shown, for a period they were never shown either.
        # EVERY KEY OF THE HASHED MANIFEST is rendered, sorted, rather than the four of
        # `ROUTINE_MANIFEST_FIELDS`: those are what a CALLER must provide, while the manifest also
        # carries the expiry the kernel adds -- and for a time-boxed permission that is the field
        # the user most needs to judge. Reading the manifest itself makes "what the hash covers"
        # literally what is shown, and a key added on either side appears with no second edit.
        # Deterministic from the request alone, which the PreToolUse gate needs (it rebuilds this
        # text and compares it character for character), and it carries no mint code -- that lives
        # only in the option label.
        manifest = request.get("subject_manifest") or {}
        rendered = "[%s]" % ", ".join(
            "%s: %s" % (MANIFEST_LABELS.get(field, field), _render_manifest_value(field, manifest[field]))
            for field in sorted(manifest))
        # The kind is already the first half of the sentence this goes into, so an item-less
        # request shows the manifest ALONE -- naming the kind again in front of it says the word
        # twice and reads like a machine to the person who has to judge it. With an item, the
        # item stays in front of the manifest: that is what a routine approval hangs from.
        target = ("%s %s" % (target, rendered)) if request["item"] else rendered
    revision = ("" if request["revision"] is None
                else " (Revision %s)" % request["revision"])
    question = "Freigabe erbeten: %s für %s%s. [APR-REQ:%s]" % (
        label, target, revision, request["request_id"])
    # THE OPTION MAY CARRY MORE THAN THE SENTENCE (`OPTION_FORMS`), never less: it is the compared
    # carrier of everything a sentence a human has to read cannot hold -- the manifest hash and the
    # request's path already, and for a list-bound subject the list itself.
    option_form = OPTION_FORMS.get(request["kind"])
    option_target = (option_form(request.get("subject_manifest") or {})
                     if option_form is not None else target)
    return {
        "question": question,
        "header": "Freigabe",
        "multiSelect": False,
        "options": [
            {
                "label": approve_label(request["mint_code"]),
                "description": "Erteilt die Freigabe „%s“ für %s in exakt dieser Fassung -- nur "
                "diese Option prägt sie. Gebunden an Prüfsumme %s… (Anfrage "
                "approvals/pending/%s.yaml)."
                % (label, option_target, request["subject_manifest_hash"][:DIGEST_SHOWN],
                   request["request_id"]),
            },
            {
                "label": _CHANGE_LABEL,
                "description": "Keine Freigabe -- Änderungswünsche folgen im Chat.",
            },
            {
                "label": _REJECT_LABEL,
                "description": "Keine Freigabe -- der Vorgang wird verworfen.",
            },
        ],
    }


APPROVAL_HOOK = "gate_approval.py"
# THE TWO EVENTS OF THE PROTOCOL AND THE ONE TOOL THEY HANG FROM, spelled once each. The hook file
# above is the only caller `mint` accepts (`_assert_minting_caller`), and the kits register it on
# BOTH events of that one tool -- two pairs, with different jobs: QUESTION_EVENT is the half that
# PREVENTS (it compares the asked question against the kernel's and can refuse), MINT_EVENT is the
# half that moves state. Only the second one can mint, which is why "can an answer mint here" is a
# question about that pair alone (`report.approval_mint_is_wired`) while the enforcement matrix
# asks about both (`report.capability_matrix`). Spelled here so neither reader writes the names a
# second time -- a swapped pair is caught by `tools/test_hooks.py -k "approval or mint or verdict"`.
APPROVAL_QUESTION_TOOL = "AskUserQuestion"
APPROVAL_QUESTION_EVENT = "PreToolUse"
APPROVAL_MINT_EVENT = "PostToolUse"

# WHO ANSWERED, RECORDED ON THE APPROVAL ITSELF (FR-0083, wishlist section 10). Until this field
# existed the store held one kind of approval and one sentence about it -- "a token exists, so a
# human answered" -- and that sentence was true only because `AskUserQuestion` can show a question
# to nobody but a human. The Claude Agent SDK's `canUseTool` callback answers the SAME tool with
# `{behavior: "allow", updatedInput: {questions, answers}}`, so the premise stops holding the day
# a project embeds the SDK: a token then means "the embedding PROGRAM decided". The SDK does not
# solve the trust question, it MOVES it -- out of the provider and into our code -- and the answer
# to "who was the judge" has to survive in the record rather than in a sentence about the record.
#
# NOT A CLAIM THE CALLER MAKES. The route is derived from WHO IS RUNNING (`_assert_minting_caller`)
# and stamped by `mint`; there is no parameter with which a caller could name its own provenance,
# because that would be the supervised party writing its own credential -- the same defect as a
# status the supervised party can set itself.
MINTED_VIA_FIELD = "minted_via"
# A human answered the provider's own approval question and the approval hook relayed that answer.
INTERACTIVE_MINT = "user_answer_via_approval_hook"
# An embedding program answered it through the Agent SDK's `canUseTool` callback
# (`kernel.sdk_approval`). What it proves is exactly what it says: a program decided.
PROGRAMMATIC_MINT = "program_answer_via_agent_sdk"

# THE ACTS THIS PROJECT DOES NOT LET A PROGRAM DECIDE FOR THE USER, as a property and not a taste:
# an act the project cannot take back out of its own resources. Publishing to a remote leaves the
# machine; reinstalling the roles, replacing the kit release, writing the Aktenplan rule, moving or
# deleting a document of record and unsaying something a kit document already records all change
# the layer that does the enforcing, or the archive that is the record. Everything else this
# kernel approves -- the scope, the delivery and the acceptance of a goal -- is a decision the
# project can revisit inside itself.
# TWO ENDS ARE MEASURED, because a set of names beside a vocabulary is exactly the shape that
# outlives it: no member here is missing from `APR_KINDS`, and every kind of `APR_KINDS` is
# classified one way or the other --
# `tools/test_approvals_dispatch.py::test_every_approval_kind_is_classified_as_takeable_back_or_not`.
# `verification` is judged REVISABLE (PR-0012, 2026-09-11), on `hole_exception`'s reading: what it
# does is close defects of this project's own store -- the items are archived, never deleted, and a
# defect closed wrongly is re-filed as a new item with its own measurement. Nothing leaves the
# machine and no enforcement layer is rewritten. That it closes MANY items at once does not change
# the class: the number is bounded by `BATCH_LIMIT` and every one of them needed a passing Evidence
# before the question could be asked.
IRREVERSIBLE_KINDS = frozenset(("push", "preset", "kit_update", "filing_correction",
                                "filing_rule", "document_proposal", "document_revision"))


def _assert_the_route_may_decide_this(route: str, kind: str) -> None:
    """Refuse a PROGRAMMATIC mint of a permission the project cannot take back (FR-0083).

    THE PROPERTY IS `IRREVERSIBLE_KINDS` and the rule is one line, because it is the same property
    FR-0074 leaves as a question after a plan approval: what a program may not decide for the user
    is what the user could not undo afterwards. Everything else the SDK route may mint -- and does,
    which is the point of having it.

    A KERNEL REFUSAL AND NOT A GATE ONE, because the token must not come into existence: a stored
    `push` approval is read by `gate_push_token` in three kits, and a rule that let it be written
    and then hoped every reader would check the provenance is the shape this kernel keeps removing.
    The neighbouring half -- acting irreversibly on an item whose approval a program gave -- is a
    gate question and is where `gate_git` asks it.
    `tools/test_approvals_dispatch.py::test_a_program_cannot_mint_a_permission_the_project_cannot_take_back`.
    """
    if route == PROGRAMMATIC_MINT and kind in IRREVERSIBLE_KINDS:
        raise ApprovalError(
            "a %r approval authorises something this project cannot take back out of its own "
            "resources, so a program may not mint it -- this request came through the Agent SDK "
            "route and was refused. Remedy: ask the USER through the approval question; the "
            "programmatic route mints the kinds a project can revisit inside itself (%s)."
            % (kind, ", ".join(sorted(set(APR_KINDS) - IRREVERSIBLE_KINDS))),
            user_text="Es wurde keine Freigabe erteilt: diese Freigabe kann nur ein Mensch geben "
                      "— sie erlaubt einen Schritt, den das Projekt nicht selbst rückgängig "
                      "machen kann. " + NEXT_START_OVER
        )


def minted_via(apr: dict) -> str:
    """Which route minted this approval -- `INTERACTIVE_MINT` for a record that does not say.

    THE DEFAULT IS NOT A GUESS AND NOT FAIL-OPEN: the programmatic route and this field arrived in
    the same change, so an approval without the field was written when no program could mint at
    all. What that costs is one thing and it is stated where it is measured -- a HAND-WRITTEN APR
    file also carries no field, and reads as interactive here; it is worthless for a different
    reason (`assert_apr_in_force` -> `consumed_request` cannot show its minted request), and this
    function is not the place that check happens.
    """
    return str((apr or {}).get(MINTED_VIA_FIELD) or INTERACTIVE_MINT)


def presented_approval_a_program_minted(state: ProjectState, item: dict):
    """The approval an item PRESENTS when a program minted it -- otherwise None (FR-0083).

    THE OTHER HALF OF `_assert_the_route_may_decide_this`. That one keeps a program from minting a
    permission the project cannot take back; this one answers the question a gate asks about an
    ITEM: was the authorisation this piece of work stands on given by a human. `gate_git` decides
    on it before it merges or pushes, because a merge is exactly where an internally revisable
    decision becomes an external fact.

    `approval_ref` and not a store scan, deliberately, and the difference is the same one
    `assert_transition_approved` names: `approval_ref` is the approval the item PRESENTS, which is
    what the dispatch gate already reads and what a human sees on the item. An item that presents
    nothing is not this function's finding -- "no approval at all" is the neighbouring gate's
    business and its message is the useful one.

    AN UNREADABLE OR MISSING APR IS NOT REPORTED AS PROGRAMMATIC. It proves nothing either way, and
    the state validator reports a stale `approval_ref` as its own error; answering "a program did
    it" on a missing file would be this function inventing a fact.
    """
    apr_ref = str((item or {}).get("approval_ref") or "")
    if not apr_ref:
        return None
    try:
        apr = read_apr(state, apr_ref)
    except (ApprovalError, StateError, OSError):
        return None
    if not isinstance(apr, dict) or minted_via(apr) != PROGRAMMATIC_MINT:
        return None
    return apr


def approval_card(apr: dict, state: ProjectState = None) -> str:
    """What a minted approval says about itself, for the surfaces that announce one.

    ONE COMPOSER, so the hook and the SDK bridge cannot come to describe the same record
    differently -- the difference between them is precisely what the card has to make visible.
    German, like every other line of this kernel a non-technical reader may end up in front of
    (`build_question`, `ApprovalError.user_text`).

    IT READS THE RECORD, it does not take the route as an argument: the provenance is a stored
    field, so what the card says is what a later auditor reading the same file would say.
    `tools/test_approvals_dispatch.py::test_the_card_names_the_route_that_minted_the_approval`.
    """
    route = minted_via(apr)
    if route == PROGRAMMATIC_MINT:
        origin = ("Erteilt von einem PROGRAMM (Agent SDK, canUseTool) — nicht von einem Menschen. "
                  "Für Handlungen, die dieses Projekt nicht selbst zurücknehmen kann, zählt sie "
                  "nicht (%s)." % ", ".join(sorted(IRREVERSIBLE_KINDS)))
    else:
        origin = "Erteilt von einem Menschen, über die Freigabe-Frage des Programms."
    # A LIST-BOUND APPROVAL HAS NO `item`, and reading that as "keinen Vorgang" told the user the
    # opposite of the truth: `plan`, `verification` and `hole_exception` bind a LIST, and the
    # record carries only its digest -- the list itself lives in the consumed request, which is
    # what `listed_items` reads. Asked only when a state is at hand, and answered from the
    # PROVENANCE rather than from a count typed anywhere: the same record a later auditor opens.
    # `tools/test_approvals_dispatch.py::test_the_card_of_a_list_bound_approval_counts_what_it_binds`
    subject = apr.get("item")
    if not subject and state is not None:
        try:
            listed = listed_items(consumed_request(state, apr))
        except (ApprovalError, StateError, OSError):
            listed = ()
        if listed:
            subject = "die %d Einträge ihrer Liste" % len(listed)
    return "Freigabe %s (%s) für %s. %s" % (
        apr.get("id"), apr.get("kind"), subject or "keinen Vorgang", origin)


def _is_same_file(left, right) -> bool:
    if not left or not right:
        return False
    try:
        return (os.path.normcase(os.path.realpath(left))
                == os.path.normcase(os.path.realpath(right)))
    except OSError:
        return False


SDK_BRIDGE_MODULE = "sdk_approval.py"


def _assert_minting_caller() -> str:
    """The mint must come from a recognised minting route -- and it RETURNS which one.

    TWO ROUTES, and the return value is the whole point of there being two (FR-0083): the approval
    hook, run as itself, which means a human answered the provider's question; and this package's
    own `sdk_approval` bridge, which an embedding program calls from the Agent SDK's `canUseTool`
    callback. The route is not something either caller may state -- it is read off WHO IS RUNNING
    and stamped by `mint`, so no caller can write its own credential.

    The hook route keeps all three conditions, each closing a measured accidental path (phase-2
    review 2026-07-25):
    1. a `_kernel` bridge module is loaded, and the hook path we accept is
       derived from ITS `__file__`;
    2. the immediate caller's file IS that hook -- realpath+normcase, so a
       crafted `compile(src, "<real hook path>")` filename does not suffice;
    3. `__main__` is that same file, so importing the hook as a module and
       calling its handler, or `runpy.run_path`, does not either.

    WHAT THIS IS WORTH, measured rather than hoped: no ACCIDENTAL path mints. A
    deliberate one does, and cheaply -- every input above is in-process state the
    caller may rewrite. Assigning `sys.modules["__main__"].__file__`, or
    registering a synthetic `_kernel` module whose `__file__` points at a path
    that need not even exist, satisfies all three; so does a two-file directory
    containing any `gate_approval.py` next to an EMPTY `_kernel.py`; and the hook
    is meant to be run with a payload on stdin, so
    `python <hooks>/gate_approval.py < forged.json` mints outright, with the
    forged `answers` + `questions` echo assembled from the readable pending
    request. The cheapest of these never runs the hook, so it does not even leave
    the hook's audit note.

    So user condition (i) ("only the PostToolUse hook may call mint") is NOT
    established by library code, and cannot be: this is in-process state
    checking in-process state. It needs a guard that stops an agent from invoking
    the hooks, or python against the kernel, at all -- a Bash/PowerShell-level
    check, since `guard_harness_selfmod` gates only Edit|Write|MultiEdit. Until
    that exists, `python scripts/harness.py doctor` must report `approval_provenance: unverified`
    and the mode stays `audited`.

    THE SDK ROUTE CANNOT CARRY CONDITION 3 AND DOES NOT PRETEND TO: the entry point of an
    embedding program is that program, by construction, so only the immediate caller can be
    checked. It is therefore WEAKER than the hook route by exactly one condition -- and since the
    hook route was already worth nothing against a deliberate forger (see the paragraph above),
    what the second route really widens is the ACCIDENTAL surface: any program that imports this
    package and calls the bridge mints. That is the price of the SDK route rather than a defect in
    it, it is why the stamp exists, and it is measured and named as `H133` in
    `docs/POST_V2_WISHLIST.md`.

    Deliberately the LAST check in `mint`: every content refusal (wrong label,
    expired request, out-of-band edit, replay) is reported on its own terms
    first, so a caller-provenance failure never masks the real reason. No APR is
    written before it either way.
    """
    frames = inspect.stack()
    # [0] this function, [1] mint, [2] whoever called mint
    caller = frames[2].filename if len(frames) > 2 else ""
    if _is_same_file(caller, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          SDK_BRIDGE_MODULE)):
        return PROGRAMMATIC_MINT
    bridge = getattr(sys.modules.get("_kernel"), "__file__", None)
    if not bridge:
        raise ApprovalError(
            "an approval can only be minted from the %s hook, and this process "
            "has no hook bridge loaded at all -- refused. Remedy: approvals "
            "happen through the AskUserQuestion flow; nothing else creates an "
            "APR." % APPROVAL_HOOK,
            user_text="Es wurde keine Freigabe erteilt: der Versuch kam nicht aus dem "
                      "Freigabe-Dialog, und nur von dort zählt ein Ja. " + NEXT_START_OVER
        )
    expected = os.path.join(os.path.dirname(bridge), APPROVAL_HOOK)
    entry = getattr(sys.modules.get("__main__"), "__file__", None)
    if not _is_same_file(caller, expected) or not _is_same_file(entry, expected):
        raise ApprovalError(
            "only %s may mint an approval, run as itself -- this call came from "
            "%s (entry point %s) and was refused. A mint is a USER decision; any "
            "other caller would be manufacturing one. Remedy: approvals happen "
            "through the AskUserQuestion flow."
            % (expected, caller or "<unknown>", entry or "<none>"),
            user_text="Es wurde keine Freigabe erteilt: die Freigabe wurde von einer anderen "
                      "Stelle als dem Freigabe-Dialog angefordert. " + NEXT_START_OVER
        )
    return INTERACTIVE_MINT


def _stored_approvals(state: ProjectState):
    """Every readable APR record in the store, in name order -- the ONE scan of it.

    Three readers need it (the replay guard in `mint`, `_gone_request_user_text` telling a user her
    yes is already recorded, and `live_line_approval`), and a second copy of a store scan is how
    `report._parents_of` became two. An unreadable file is skipped: it proves nothing either way,
    and every caller here is asking "is there one that grants this", never "is the store sound".
    """
    approvals_dir = os.path.join(state.root, "approvals")
    if not os.path.isdir(approvals_dir):
        return
    for name in sorted(os.listdir(approvals_dir)):
        if not (name.startswith("APR-") and name.endswith(".yaml")):
            continue
        try:
            record = state._read_yaml(os.path.join(approvals_dir, name))
        except Exception:
            continue        # an unreadable approval proves nothing either way (fail-closed)
        if isinstance(record, dict):
            yield record


def _approval_of_request(state: ProjectState, request_id: str):
    """The APR minted from this request, or None."""
    for existing in _stored_approvals(state):
        if existing.get("request_id") == request_id:
            return existing
    return None


def _in_force_approvals(state: ProjectState, kind: str):
    """(approval, its minted request) for every approval of `kind` that grants anything RIGHT NOW.

    THE ONE DEFINITION OF "IN FORCE" FOR A LINE KIND, because two readers ask it with different
    follow-up questions: `live_line_approval` wants the one whose manifest matches EXACTLY, and
    `live_correction_approval` the one whose OPERATION keys match while the reason beside them is
    the user's business, not the shell's. Splitting the loop was how `gate_push_token` and
    `set-preset` nearly ended up with two answers about whether a lapsed permission still works;
    what differs between the two callers is the match, and only the match.

    Three ways an approval that EXISTS grants nothing here, in the order they are cheap to check:
    it was revoked; its provenance cannot be proven, because the APR file carries only the hash and
    the manifest lives in the consumed REQUEST that `revoke` MOVES out of the way
    (`consumed_request`); its clock -- read off the HASH-COVERED side (`proven_expiry`), never off
    the APR file -- has run out.
    """
    for apr in _stored_approvals(state):
        if apr.get("kind") != kind or apr.get("revoked"):
            continue
        try:
            request = consumed_request(state, apr)
            expires = proven_expiry(request)
        except ApprovalError:
            continue        # unprovable provenance or an unreadable expiry grants nothing
        if expires is not None and expires <= time.time():
            continue
        yield apr, request


def live_line_approval(state: ProjectState, kind: str, manifest: dict):
    """A minted, unrevoked, unexpired approval of `kind` whose REQUEST carries exactly `manifest`.

    The expiry is dropped from the STORED manifest before hashing because `create_pending_request`
    puts it there and no caller can know the minute it was minted; everything else must match key
    for key. Everything about whether the approval is in force at all is `_in_force_approvals`.
    """
    wanted_hash = subject_manifest_hash(dict(manifest))
    for apr, request in _in_force_approvals(state, kind):
        stored = dict(request.get("subject_manifest") or {})
        stored.pop(EXPIRY_FIELD, None)
        if subject_manifest_hash(stored) == wanted_hash:
            return apr
    return None


FILING_CORRECTION_KIND = "filing_correction"


def correction_operation_key(document, destination, content) -> str:
    """The lookup value of ONE correction operation -- computed identically on both sides.

    THE COMPARISON GOES THROUGH `subject_manifest_hash` AND NOT THROUGH `==`, and that is not a
    formality: a document called `Müller GmbH.pdf` reaches the request as the path a role typed and
    the gate as the path a filesystem handed back, and unicode gives that name two byte spellings.
    `canonical_json` NFC-normalises before hashing, so one filename is one operation -- which a
    byte-wise dict comparison would not deliver
    (`tools/test_hooks.py::test_a_correction_of_an_umlaut_document_is_one_operation_in_both_
    normalisations`).

    ONE function for both ends, and that is the point of it existing beside the builder: the stored
    manifest is keyed through it and so is the gate's question, so the two cannot come to normalise
    a position differently. `filed_position` is idempotent, so passing already-normalised values
    through it again changes nothing.
    """
    return subject_manifest_hash(filing_correction_operation(document, destination, content))


def live_correction_approvals(state: ProjectState) -> dict:
    """{operation key: approval} for every filing correction in force RIGHT NOW -- one store read.

    THE SHAPE IS A MAP BECAUSE THE CALLER ASKS ABOUT MANY OPERATIONS, and asking per operation was
    a denial of service with a docstring over it (verifier finding F3). `_in_force_approvals` walks
    the whole approval store and resolves each record back to its consumed request; called once per
    operand of a command line, that is a full store scan per operand. Measured by the verifier:
    300 operands against 204 approvals took 69.8 s, and an 8000-document `rm` took 114 s -- one and
    two minutes in which the wall has said nothing and the session cannot move, bought by writing a
    longer command line (what a deadline does and does not do to a hook here is measured in
    `_compat.HOOK_DEADLINE_SECONDS`). One scan, then a dictionary lookup per operation, makes the
    store size a constant instead of a factor.

    The match itself is unchanged and is still a SUBSET of what the user signed: the operation keys
    only. The reason sits beside them in the manifest and is deliberately not matched -- it is what
    the user was told, not what the shell does, and a correction is not a different operation for
    having been justified differently. The expiry, the revocation and the provenance are what
    `_in_force_approvals` already decides.

    First writer wins on a duplicate key: two live approvals for the identical operation authorise
    the identical thing, so which of them is reported changes nothing but the id in the journal.
    """
    found = {}
    for apr, request in _in_force_approvals(state, FILING_CORRECTION_KIND):
        stored = request.get("subject_manifest") or {}
        found.setdefault(correction_operation_key(stored.get("document"),
                                                  stored.get("destination"),
                                                  stored.get("content")), apr)
    return found


def live_correction_approval(state: ProjectState, operation: dict):
    """The in-force approval for exactly this filing correction, or None.

    `operation` is what `filing_correction_operation` builds. Kept beside the map above for the
    single-operation caller (and for the tests): one question, one answer, and no second statement
    of what the match is -- it is the map's own key.
    """
    return live_correction_approvals(state).get(correction_operation_key(**operation))


def _gone_request_user_text(state: ProjectState, request_id: str) -> str:
    """What to tell the USER about a request that is no longer pending -- read off the store.

    THREE OUTCOMES, TOLD APART BY WHERE THE REQUEST WENT: `mint` moves it to
    `approvals/consumed/` and `revoke` to `approvals/revoked/`, so its location is the answer and
    nothing has to be inferred from the absence alone. Measured while building BUG-0039's fix: with
    one blanket sentence here, a second click on an already-minted question told the user her
    approval had not happened and sent her to start over -- an alarm as wrong as the silence the
    fix is about, in the other direction
    (`test_a_second_click_on_an_already_minted_question_does_not_alarm_the_user`).
    """
    if os.path.exists(_request_path(state, request_id, consumed=True)):
        apr = _approval_of_request(state, request_id)
        return ("Deine Freigabe zu dieser Frage ist bereits erteilt%s — es fehlt nichts, und du "
                "musst nichts wiederholen."
                % (" (%s)" % apr.get("id") if isinstance(apr, dict) and apr.get("id") else ""))
    if os.path.exists(_request_path(state, request_id, revoked=True)):
        return ("Es wurde keine Freigabe erteilt: die Freigabe zu dieser Frage wurde "
                "zurückgezogen. " + NEXT_START_OVER)
    return ("Es wurde keine Freigabe erteilt: zu dieser Frage ist keine Freigabe-Anfrage mehr "
            "offen — sie ist abgelaufen oder wurde nie angelegt. " + NEXT_START_OVER)


def mint(state: ProjectState, request_id: str, answer: str) -> dict:
    """Phase 3: create the APR -- only for the verbatim approval label.

    `answer` is the raw string from `toolUseResult.answers[<question>]`. It
    mints ONLY if it equals `approve_label(request["mint_code"])` exactly.
    The platform gives no structural option identity (spike S2b), so the
    per-request mint code carries the proof instead: any other text --
    "Ändern", "Ablehnen", "ok", a plain "Freigeben" typed into "Other" --
    never mints.
    """
    with state.lock:
        path = _request_path(state, request_id)
        try:
            request = state._read_yaml(path)
        except FileNotFoundError:
            raise ApprovalError(
                "no pending approval request %s (consumed, expired-and-cleaned, "
                "or never created). Remedy: run the kernel approval flow again "
                "-- an invented request ID never mints. (A hand-WRITTEN pending "
                "file with a self-chosen mint_code would mint; keeping the "
                "pending-request area kernel-only is the write-scope gate's job, "
                "and the state validator flags hand edits.)" % request_id,
                user_text=_gone_request_user_text(state, request_id)
            ) from None
        if has_expired(request):
            raise ApprovalError(
                "approval request %s expired. Remedy: create a fresh request "
                "and ask again -- expired requests never mint." % request_id,
                user_text="Es wurde keine Freigabe erteilt: die Freigabe-Anfrage war schon "
                          "abgelaufen, als deine Antwort ankam. " + NEXT_START_OVER
            )
        # format check, not mere presence: `mint_code: null` / "" would yield a
        # guessable label like "Freigeben [None]" (Opus check 2026-07-24)
        if not re.fullmatch(r"[0-9a-f]{6}", str(request.get("mint_code") or ""), flags=re.ASCII):
            raise ApprovalError(
                "pending request %s carries no valid mint_code (pre-amendment "
                "or hand-written file) -- refusing to mint (fail-closed). "
                "Remedy: create a fresh approval request." % request_id,
                user_text="Es wurde keine Freigabe erteilt: die gespeicherte Freigabe-Anfrage "
                          "trägt keinen gültigen Freigabe-Code. " + NEXT_START_OVER
            )
        expected = approve_label(request["mint_code"])
        if answer != expected:
            raise ApprovalError(
                "answer %r does not mint: only the exact approval label of "
                "THIS request mints (it carries a per-request code shown in "
                "the option). Casual free text never approves. The pending "
                "request stays until TTL." % (answer,),
                user_text="Es wurde keine Freigabe erteilt: der angeklickte Text gehört nicht zu "
                          "dieser Freigabe-Anfrage — jede Frage trägt ihren eigenen Code in "
                          "eckigen Klammern, und nur der Freigeben-Knopf DIESER Frage zählt. "
                          + NEXT_ASK_AGAIN
            )
        item = None
        if request["item"] is not None:
            item = state.read_item(request["item"])
            if item.get("revision") != request["revision"]:
                raise ApprovalError(
                    "item %s moved to revision %s since the request (requested "
                    "%s) -- out-of-band change, no mint. Remedy: re-run the "
                    "approval flow on the current revision."
                    % (request["item"], item.get("revision"), request["revision"]),
                    user_text="Es wurde keine Freigabe erteilt: der Vorgang wurde geändert, "
                              "nachdem die Frage gestellt wurde — du hättest eine andere Fassung "
                              "freigegeben als die, die jetzt vorliegt. " + NEXT_START_OVER
                )
            if request["kind"] in ("scope", "acceptance", "delivery"):
                current_hash = subject_manifest_hash(
                    item_subject_manifest(item, request["kind"])
                )
                if current_hash != request["subject_manifest_hash"]:
                    raise ApprovalError(
                        "subject manifest of %s changed since the request -- "
                        "no mint. Remedy: re-run the approval flow."
                        % request["item"],
                        user_text="Es wurde keine Freigabe erteilt: der Inhalt des Vorgangs hat "
                                  "sich geändert, nachdem die Frage gestellt wurde. "
                                  + NEXT_START_OVER
                    )
        # THE WHOLE LIST IS RE-ASKED BEFORE ANYTHING IS WRITTEN, and the position is the whole
        # point: the store can move between the question and the click -- an Evidence retracted, a
        # listed defect walked by hand, a listed defect EDITED -- while
        # `_close_what_the_batch_lists` runs AFTER the APR exists and after the request is consumed.
        # A refusal down there leaves a real approval, a spent request and a batch closed halfway,
        # which is measured and is why the coverage of every listed item is asked here too
        # (`batch_walk_blockers(..., request)`, whose docstring carries the measurement). All or
        # nothing: one blocker stops the mint, and the pending request survives for a fresh answer.
        blocked = batch_walk_blockers(state, request["kind"], listed_items(request), request)
        if blocked:
            raise ApprovalError(
                "the batch cannot be closed as it was asked -- %d of its items moved since the "
                "question: %s. Remedy: ask again over the current list; nothing was minted."
                % (len(blocked), " | ".join(blocked)),
                user_text="Es wurde keine Freigabe erteilt: an %d der aufgelisteten Einträge hat "
                          "sich etwas geändert, seit die Frage gestellt wurde. " % len(blocked)
                          + NEXT_START_OVER)
        # idempotency guard (Fable-Check 8/#2): a crash between APR write and
        # request consume would leave the request pending -- a replayed mint
        # must not create a SECOND approval for the same request
        existing = _approval_of_request(state, request_id)
        if existing is not None:
            raise ApprovalError(
                "request %s already minted %s -- replay blocked. "
                "Remedy: run `python scripts/harness.py validate` to reconcile the "
                "half-consumed request." % (request_id, existing.get("id")),
                # THE ONE BRANCH THAT MUST NOT SAY "no approval was created", because one was:
                # this is the crash window between the APR write and the request consume (see the
                # ordering note below). An alarm here would be as wrong as the silence BUG-0039 is
                # about, in the other direction.
                user_text="Deine Freigabe zu dieser Frage steht bereits (%s) — es fehlt nichts "
                          "und du musst nichts wiederholen. Dein Assistent sollte einmal den "
                          "Zustand prüfen lassen, damit der Vorgang die Freigabe auch sichtbar "
                          "trägt." % existing.get("id")
            )
        # LAST gate before the approval exists: provenance of the CALLER (see
        # _assert_minting_caller). Everything above refuses on content grounds and
        # says so; this refuses on "who is asking" -- and it ANSWERS it, because which route
        # minted is what the record has to carry from here on (FR-0083).
        route = _assert_minting_caller()
        _assert_the_route_may_decide_this(route, request["kind"])
        apr_id = state.allocate_id("APR")
        apr = {
            "id": apr_id,
            "kind": request["kind"],
            "item": request["item"],
            "revision": request["revision"],
            # only the HASH, exactly as spec II.2 lists the APR fields. An
            # earlier cut stored the manifest here too, so a bundled analysis
            # approval could answer "do you cover TSK-0007?" -- but the consumed
            # request already carries the manifest and is kept forever ("move,
            # never delete"), so the copy created a second canonical home AND
            # let a HAND-WRITTEN APR answer that question with no minted request
            # behind it. Coverage is read from the consumed request instead
            # (kernel/dispatch.py), which carries the provenance with it.
            "subject_manifest_hash": request["subject_manifest_hash"],
            "request_id": request_id,
            "mint_code": request["mint_code"],
            # WHO ANSWERED (FR-0083). Stamped from `_assert_minting_caller`'s answer and never from
            # an argument -- see `MINTED_VIA_FIELD`. Written for BOTH routes, including the
            # interactive one: a field present only on the programmatic half would make "no field"
            # mean two different things a year from now.
            MINTED_VIA_FIELD: route,
            "approved_at": _now_iso(),
            # DERIVED DISPLAY VALUE, not the authority: spec II.2 lists `expires`
            # among the APR fields and humans/dashboards read it here, but every
            # gate reads `proven_expiry(request)` instead -- the hash-covered copy
            # inside the minted manifest. Duty for the 1.4c validator: assert the
            # two agree, so a human can never read "valid until 2030" from a
            # record the gate correctly refuses.
            EXPIRY_FIELD: (request.get("subject_manifest") or {}).get(EXPIRY_FIELD),
            "revoked": False,
        }
        state._write_yaml_atomic(
            os.path.join(state.root, "approvals", apr_id + ".yaml"), apr
        )
        # CONSUME BEFORE THE ITEM MOVES, and the order is load-bearing rather than tidy. The
        # transition below runs the same `assert_transition_approved` every other caller runs
        # (there is no bypass parameter -- spec II.4), and that check proves an approval through
        # its CONSUMED request. Written afterwards, as it used to be, the mint would refuse its
        # own transition: the approval it had just created would still be unprovable.
        # What the reordering costs, stated rather than glossed: a crash between here and the item
        # write leaves a fully valid approval whose item carries no `approval_ref`. That item is
        # transitionable (the approval is real -- the user did approve) but NOT dispatchable
        # (`_assert_root_approval_locked` reads `approval_ref`), so the window fails closed on the
        # side that grants a spawn. NOTHING REPORTS THE PAIR, and that is worth knowing rather than
        # implying: `report.validate_state` walks items that HAVE an approval_ref, so an approval
        # whose item forgot it produces no finding -- only the two files in git say so. The old
        # order could not be kept either way, because a check that reads the store cannot be
        # satisfied by a store write that has not happened yet.
        state._write_yaml_atomic(_request_path(state, request_id, consumed=True), request)
        os.remove(path)
        if item is not None and presents(parse_id(apr["item"])[0], request["kind"]):
            item["approval_ref"] = apr_id
            item_type, _ = parse_id(apr["item"])
            # STAMP WHAT WAS APPROVED. The mint is the only moment at which a user has just said
            # yes to this exact content, so it is the only honest producer of that stamp -- and
            # before this line there was none at all: `report.validate_state` demanded a PROC's
            # `approved_hash` as an ERROR while the sole writer of it was a V1 script that opened a
            # deleted monolith and died. A rule whose only route to compliance is a command that
            # cannot run is a rule the project can never satisfy.
            # It is deliberately NOT a `--update` flag on a script either: "run this to make the
            # tamper check pass again" is the same permission the check exists to withhold.
            content_hash = approved_content_hash(item_type, item)
            if content_hash is not None:
                item[APPROVED_CONTENT_HASH_FIELD] = content_hash
            edge = APPROVAL_TRANSITIONS.get((item_type, request["kind"]))
            state._write_yaml_atomic(state.active_path(item["id"]), item)
            if edge and item.get("status") == edge[0]:
                # THROUGH the automaton, not around it. `state.transition` is documented as the
                # only status writer and this line used to disprove it: a direct `item["status"] =`
                # skipped `assert_transition` and would skip the approval check too, which is one
                # bypass in the one place a bypass would be invisible.
                item = state._transition_locked(item["id"], edge[1])
        _close_what_the_batch_lists(state, request, apr)
        state._regenerate_index_locked()
        return apr


def _close_what_the_batch_lists(state: ProjectState, request: dict, apr: dict) -> list:
    """Walk every item this approval LISTS to the end its mint commits, and archive it there.

    THE SECOND HALF OF PR-0012 AC-1, and it runs where it does for `mint`'s own documented reason:
    after the request is consumed, because `state._transition_locked` proves the approval through
    that consumed request and there is no bypass parameter. Whether it runs at all is
    `batch_closing_types` -- a list-bound kind that commits no edge of its own (`plan`) moves
    nothing here, which is why this needs no kind name.

    THE WALK IS THE TYPE'S OWN CHAIN, sliced from where the item stands to `batch_walk_end`, and
    every step goes through `_transition_locked`: the approved edge is authorised by the approval
    just minted (`_names_the_item` finds it through the list), the free steps are free, and the
    confirming edge demands its Evidence exactly as it does for a hand-walked bug. So this closes
    the item on the same guards a single mint plus three typed transitions would, with the same
    refusals -- and `batch_walk_blockers` has already established, twice, that each guard will
    pass.

    ARCHIVED ONLY WHERE THE END IS TERMINAL, asked of the automaton rather than assumed: closing a
    defect ends on a terminal and the item leaves `bugs/active/`, but a future type whose batch end
    is mid-chain stays where the chain left it.
    `tools/test_approvals_dispatch.py::test_the_batch_mint_walks_every_listed_bug_to_verified_and_archives_it`
    """
    kind = request["kind"]
    types = batch_closing_types(kind)
    walked = []
    for item_id in listed_items(request):
        item_type, _number = parse_id(item_id)
        if item_type not in types:
            continue
        item = state.read_item(item_id)
        # WHAT THE ITEM PRESENTS AND WHAT WAS APPROVED, written for the same two reasons the
        # single-item branch of `mint` writes them: the approval is the item's own authorisation
        # record from here on, and the mint is the one moment a user has just signed this content.
        item["approval_ref"] = apr["id"]
        content_hash = approved_content_hash(item_type, item)
        if content_hash is not None:
            item[APPROVED_CONTENT_HASH_FIELD] = content_hash
        state._write_yaml_atomic(state.active_path(item_id), item)
        chain = AUTOMATA[item_type].chain
        end = batch_walk_end(item_type, kind)
        standing = chain.index(str(item.get("status")))
        if end in chain:
            steps = list(chain[standing + 1:chain.index(end) + 1])
        else:
            # AN OFF-CHAIN ENDING (`BUG` -> `ACCEPTED_EXCEPTION`): climb the chain to the edge's
            # SOURCE first and take the ending as the last step. The climb is not decoration -- the
            # automaton allows that terminal only from the source status (`terminal_from`), so a
            # listed gap standing at OPEN has to reach TRIAGED before the edge exists at all, and
            # those steps are free ones. Measured without the climb: a hole captured OPEN was
            # refused mid-walk, after the APR existed.
            source = APPROVAL_TRANSITIONS[(item_type, kind)][0]
            steps = list(chain[standing + 1:chain.index(source) + 1]) + [end]
        # THE INDEX IS REBUILT ONCE FOR THE WHOLE MINT, not once per step -- `mint` regenerates
        # unconditionally after this returns, and the rule is `_transition_locked`'s own: once per
        # operation, not once per item it touches. Measured before it: a batch of 25 on a
        # repo-sized store spent 100 rebuilds inside one hook call.
        for status in steps:
            item = state._transition_locked(item_id, status, regenerate=False)
        if is_terminal(item_type, str(item.get("status"))):
            state._archive_locked(item_id, regenerate=False)
        walked.append(item_id)
    if walked:
        # THE WRITER IS THE REFRESHER, once for the whole batch. `mint` regenerates after this
        # returns as well, and that one is not redundant for the paths that walk no batch -- what
        # would be wrong is a function that moves a hundred items and leaves the index and the
        # board to a caller it does not control.
        # `tools/test_board.py::test_no_kernel_writer_of_a_rendered_file_leaves_the_board_behind`
        # derives that duty from the package rather than trusting this sentence.
        state._regenerate_index_locked()
    return walked


def presents(item_type: str, kind: str) -> bool:
    """Does an approval of `kind` become the item's PRESENTED approval (`approval_ref`)?

    THE PROPERTY, not a list of kinds: an approval that binds the item's own state -- one that
    commits an edge of its automaton (`APPROVAL_TRANSITIONS`) or that a root's dispatch route
    reads off `approval_ref` (`ROOT_DISPATCH_KINDS`) -- is the approval the item presents. One
    that merely HANGS from the item and is found by its own reader (a routine, read by
    `dispatch._covering_routine_apr` out of the approvals directory; an analysis with an item id,
    read by the analysis route out of its listing) is not, and leaves the presented one standing.

    WHY THIS EXISTS (PR-0011 AC-8): until it, `mint` wrote `approval_ref` for EVERY item-bound
    approval, so the routine approval the auditor's route is written for MOVED a goal's scope
    approval out of the root's field and every builder under that goal stopped dispatching until
    the scope question was asked again -- at every weekly renewal. Measured and pinned as current
    behaviour in `tools/test_approvals_dispatch.py::test_minting_a_routine_on_a_live_root_leaves_its_approval_ref_alone`,
    which now measures the opposite, with the builder's next lease as the proof.
    `report._check_dispatch_approval_presented` keeps warning about stores where the older mint
    left that state behind.
    """
    return (item_type, kind) in APPROVAL_TRANSITIONS or kind in ROOT_DISPATCH_KINDS


def revoke(state: ProjectState, apr_id: str) -> dict:
    """Withdraw an approval — recorded where the APR file is NOT the evidence.

    The flag on the approval stays, because it is what a human reads. But the
    fact that actually blocks is the MOVE of the minted request out of
    `approvals/consumed/`: `consumed_request` then finds no provenance and
    refuses, so flipping `revoked` back to false achieves nothing.
    """
    with state.lock:
        path = os.path.join(state.root, "approvals", apr_id + ".yaml")
        try:
            apr = state._read_yaml(path)
        except FileNotFoundError:
            raise ApprovalError(
                "no approval %s. Remedy: check the id against the generated index, "
                "which lists every approval this project holds." % apr_id
            ) from None
        # ORDER MATTERS, do not "clean this up": the flag is written FIRST and is
        # checked first in both authorisation routes, so a crash between the two
        # writes can leave the flag without the move -- never the move without the
        # flag, which would be an approval that still authorises.
        apr["revoked"] = True
        state._write_yaml_atomic(path, apr)
        request_id = str(apr.get("request_id") or "")
        if request_id:
            consumed = _request_path(state, request_id, consumed=True)
            if os.path.exists(consumed):
                request = state._read_yaml(consumed)
                request["revoked_at"] = _now_iso()
                state._write_yaml_atomic(
                    _request_path(state, request_id, revoked=True), request)
                os.remove(consumed)
        # The APR file is a rendered item (`backlog_types.ACTIVE_DIRS["APR"]`), and `revoked` is a
        # field the index does not carry -- so before this line the board went on showing the
        # approval as in force while the file said otherwise, and nothing said the view was behind
        # (TSK-0071 verifier finding B2). The regeneration is on the rare branch: revoking is a
        # user act, and it already writes two files here.
        state._regenerate_index_locked()
        return apr


def has_expired(request: dict, now=None) -> bool:
    """Is this request past its clock -- the ONE definition of "can never mint again".

    The readers may not disagree: `pending_request`, which refuses to hand out an expired request;
    `sweep_expired_requests`, which DELETES exactly what that refusal has made permanent; the
    session brief, which counts an expired request instead of listing it; and the board, which
    leaves it off the "waiting on you" strip. A missing or unreadable stamp answers True by the
    same arithmetic the mint uses -- a request whose clock cannot be read never mints either, so
    calling it live would leave a file that nothing can ever redeem and nothing may ever remove.
    That every one of those readers asks THIS function rather than spelling the comparison again
    is `tools/test_approvals_dispatch.py::test_every_reader_of_the_expiry_rule_asks_this_one`.

    `now` exists because the readers legitimately stand on TWO clocks and only the RULE is shared:
    the hooks and the brief read the wall clock at the moment they run, the board reads the stamp
    of the state write it was rendered from, so that the page stays a pure function of the state
    (`board._clock`). Left out, the wall clock answers -- which is what every caller before
    TSK-0120 did. The seam and its measurement are `H126` in `docs/POST_V2_WISHLIST.md`.
    """
    try:
        return (time.time() if now is None else now) > float((request or {}).get("expires_at_epoch") or 0)
    except (TypeError, ValueError):
        return True


def sweep_expired_requests(state: ProjectState) -> dict:
    """Remove the pending requests that can never mint again. `{"removed", "kept", "unreadable"}`.

    THE MEASURED GAP (pilot 4, `P4-12`): an office project ended with three requests in
    `approvals/pending/` that nobody had answered. They were already inert -- `pending_request`
    refuses an expired one, `open_requests` leaves it out and the session brief counts it under
    `expired_requests` rather than listing it as open -- but the user asked what those files were,
    and the honest answer was that the apparatus offers no command to clear them. A store that only
    ever grows is one a user cannot keep, and `pending_request`'s own refusal already spoke of a
    request that was "expired-and-cleaned".

    WHAT IT MAY REMOVE is a property and not a judgement: `has_expired`, the same reader that makes
    the request unusable in the first place. A live request is kept (answering it still mints), and
    one that cannot be READ is kept and REPORTED -- deleting what you could not judge is how a
    cleanup becomes a data loss. Nothing else is touched: `approvals/consumed/` is the provenance
    every approval is checked against, and `approvals/revoked/` is the record that a permission was
    taken back.
    """
    directory = _pending_dir(state)
    removed, kept, unreadable = [], [], []
    with state.lock:
        names = sorted(os.listdir(directory)) if os.path.isdir(directory) else []
        for name in names:
            if not name.endswith(".yaml"):
                continue
            request_id = name[: -len(".yaml")]
            try:
                request = state._read_yaml(os.path.join(directory, name))
            except Exception:                       # noqa: BLE001 -- unjudgeable, so untouched
                unreadable.append(name)
                continue
            if not isinstance(request, dict):
                unreadable.append(name)
                continue
            if not has_expired(request):
                kept.append(str(request.get("request_id") or request_id))
                continue
            os.remove(_request_path(state, request_id))
            removed.append({"request_id": str(request.get("request_id") or request_id),
                            "kind": str(request.get("kind") or ""),
                            "item": str(request.get("item") or "")})
    return {"removed": removed, "kept": kept, "unreadable": unreadable}


def pending_request(state: ProjectState, request_id: str, now=None) -> dict:
    """A PENDING approval request, or ApprovalError — the reader the hooks use.

    The PreToolUse(AskUserQuestion) gate resolves `[APR-REQ:<id>]` back to its
    request and rebuilds `build_question(request)` for the string comparison, so
    that lookup needs one public, fail-closed home rather than a hook reaching
    into a private path helper. The TTL check lives here too, for the same reason.

    `now` is handed straight to `has_expired`; left out, the wall clock answers. Its reason is
    that function's, not this one's.
    """
    try:
        request = state._read_yaml(_request_path(state, request_id))
    except FileNotFoundError:
        raise ApprovalError(
            "no pending approval request %s (consumed, expired-and-cleaned, or "
            "never created). Remedy: run the kernel approval flow again -- an "
            "invented request id never mints." % request_id,
            user_text=_gone_request_user_text(state, request_id)
        ) from None
    except Exception as exc:
        raise ApprovalError(
            "pending request %s is unreadable (%s) -- fail-closed. Remedy: "
            "re-run the approval flow." % (request_id, type(exc).__name__),
            user_text="Es wurde keine Freigabe erteilt: die gespeicherte Freigabe-Anfrage lässt "
                      "sich nicht mehr lesen. " + NEXT_START_OVER
        ) from None
    if not isinstance(request, dict):
        raise ApprovalError(
            "pending request %s is not a mapping -- fail-closed." % request_id,
            user_text="Es wurde keine Freigabe erteilt: die gespeicherte Freigabe-Anfrage hat "
                      "nicht die Form, die das Programm erwartet. " + NEXT_START_OVER
        )
    if has_expired(request, now):
        raise ApprovalError(
            "approval request %s expired -- expired requests never mint. "
            "Remedy: create a fresh request and ask again." % request_id,
            user_text="Es wurde keine Freigabe erteilt: die Freigabe-Frage war abgelaufen, als du "
                      "geantwortet hast. " + NEXT_START_OVER
        )
    return request


def open_requests(state: ProjectState, now=None) -> list:
    """Every approval request this project is still WAITING ON -- answerable right now.

    "Still open" is asked of `pending_request` per file rather than re-tested here, so the TTL and
    the unreadable case have one spelling: a request whose clock ran out is not something a user
    can still answer, and counting it would make the approval hook announce a request nobody could
    complete. Both ends of that -- the expired file is excluded HERE, and the hook that reads this
    goes quiet BECAUSE of it -- are measured in
    `tools/test_hooks_v2.py::test_an_expired_request_is_not_open_and_a_reworded_relay_goes_silent`,
    whose docstring also carries what the exclusion costs.

    WHAT READS THIS AND WHY IT IS STATE AND NOT SPELLING: `gate_approval` announces a non-mint when
    an approval is outstanding and the question that got answered was not that request's. That
    trigger has to survive a relay in the model's own words -- "Ja, freigeben" / "Nein" -- which is
    exactly what a test on the LABEL's wording does not
    (`tools/test_hooks_v2.py::test_a_relay_in_the_models_own_words_still_reaches_the_user`).

    `now` is optional, and OPTIONAL IS THE POINT: the three `gate_approval.py` of the kits call
    this with one argument, so a REQUIRED second one turns their call into a TypeError. Stream A's
    verifier measured the literal form first proposed for this seam: two red nodes in
    `tools/test_hooks_v2.py`, while the board's parity test -- the only arbiter the seam named at
    the time -- stayed green and saw nothing. Hence two arbiters, and the second is
    `tools/test_hooks_v2.py::test_an_expired_request_is_not_open_and_a_reworded_relay_goes_silent`.
    """
    directory = _pending_dir(state)
    if not os.path.isdir(directory):
        return []
    requests = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".yaml"):
            continue
        try:
            requests.append(pending_request(state, name[: -len(".yaml")], now))
        except ApprovalError:
            continue
    return requests


def declining_labels(request: dict) -> tuple:
    """The labels of THIS request's own question that do NOT approve.

    Read off `build_question`, so a renamed or added option arrives here with no second edit and no
    list of spellings. That is a claim about the DERIVATION and not about today's two words, so it
    is measured against a kernel whose question renames one of them:
    `tools/test_hooks_v2.py::test_a_renamed_decline_option_needs_no_second_edit`. What it is FOR:
    telling a DELIBERATE decline from a click that meant yes and achieved nothing. The first needs
    no notice -- the user chose it, on the kernel's own question, and a message there is noise on a
    correct outcome; the second is BUG-0039.

    Anything that is not one of these strings exactly -- free text, the approve label with a
    trailing space, a list -- is NOT a decline and is announced. That direction is the deliberate
    one: an unnecessary notice costs a sentence, a missing one cost pilot 3 a lost approval
    (`tools/test_hooks_v2.py::test_only_the_requests_own_decline_options_stay_quiet`).
    """
    approve = approve_label(request["mint_code"])
    return tuple(str(option["label"]) for option in build_question(request)["options"]
                 if str(option["label"]) != approve)


def consumed_request(state: ProjectState, apr: dict) -> dict:
    """The minted request behind an approval — its PROVENANCE (spec II.12).

    "manuell geschriebene APR ohne Provider-gepraegten Token -> Block": an
    approval file on its own proves nothing, because anything that can write
    YAML can write one. What cannot be forged is a CONSUMED REQUEST: the kernel
    is the only writer of `approvals/consumed/`, it lands there only through
    `mint`, and mint only runs on the verbatim approval label carrying that
    request's mint code. So every authorisation check resolves the approval back
    to its request and compares the two.

    Raises ApprovalError when the request is missing or disagrees with the
    approval — fail-closed, because "cannot prove provenance" must never read as
    "approved".

    REVOCATION lives here too, not in the APR file: `revoke` MOVES the request to
    `approvals/revoked/`, so a revoked approval simply has no consumed request
    and this refuses. Keeping `revoked: true` only inside the APR made revocation
    the least protected fact in the record — flipping one boolean back
    resurrected a withdrawn permission, and II.2 makes revocability load-bearing
    for exactly the kind that carries standing permissions.
    """
    request_id = str(apr.get("request_id") or "")
    if not request_id:
        raise ApprovalError(
            "approval %s names no request_id -- refusing to treat it as a user "
            "approval (spec II.12: a hand-written APR without a provider-minted "
            "token blocks). Remedy: obtain the approval through the kernel "
            "approval flow." % apr.get("id"),
            user_text="Es wurde keine Freigabe erteilt: zu dieser Freigabe gehoert kein Antrag, "
                      "mit dem sie belegt werden koennte. Eine Freigabe-Datei allein ist kein Ja "
                      "von dir -- sie muss auf eine Frage zurueckgehen, die dir gestellt wurde.",
        )
    try:
        request = state._read_yaml(_request_path(state, request_id, consumed=True))
    except FileNotFoundError:
        revoked = os.path.exists(_request_path(state, request_id, revoked=True))
        raise ApprovalError(
            "approval %s %s -- it grants nothing (spec II.12/II.10a). Remedy: %s"
            % (apr.get("id"),
               "was REVOKED" if revoked else "has no consumed request %s, so its "
               "provenance cannot be proven" % request_id,
               "obtain a fresh approval." if revoked else
               "obtain the approval through the kernel approval flow; `python scripts/harness.py "
               "validate` reports approvals without a request."),
            user_text="Es wurde keine Freigabe erteilt: diese Freigabe wurde %s."
                      % ("von dir zurueckgezogen, also gilt sie nicht mehr" if revoked else
                         "nie durch eine Frage an dich belegt, und ohne diesen Nachweis gilt sie "
                         "nicht"),
        ) from None
    except Exception as exc:
        raise ApprovalError(
            "consumed request %s for approval %s is unreadable (%s) -- "
            "fail-closed. Remedy: `git restore` the approvals directory."
            % (request_id, apr.get("id"), type(exc).__name__),
            user_text="Es wurde keine Freigabe erteilt: der Nachweis zu dieser Freigabe laesst "
                      "sich nicht mehr lesen. Solange unklar ist, worauf du Ja gesagt hast, wird "
                      "nichts gemacht.",
        ) from None
    if not isinstance(request, dict):
        raise ApprovalError(
            "consumed request %s is not a mapping -- fail-closed." % request_id,
            user_text="Es wurde keine Freigabe erteilt: der Nachweis zu dieser Freigabe hat nicht "
                      "die Form, in der er angelegt wird. Er wird als unbrauchbar behandelt, nicht "
                      "als Zustimmung.",
        )
    for field in ("mint_code", "subject_manifest_hash", "kind", "item", "revision"):
        if request.get(field) != apr.get(field):
            raise ApprovalError(
                "approval %s disagrees with its minted request on %s -- the "
                "approval was altered after minting, so it grants nothing "
                "(fail-closed). Remedy: re-run the approval flow."
                % (apr.get("id"), field),
                user_text="Es wurde keine Freigabe erteilt: diese Freigabe weicht von der Frage "
                          "ab, die dir gestellt wurde -- sie wurde nachtraeglich geaendert. Es "
                          "wird neu gefragt statt eine veraenderte Zustimmung zu verwenden.",
            )
    # the hash is RECOMPUTED from the request's own manifest, not merely compared
    # between two stored copies: both stored hashes survive an edit of the
    # manifest, and the expiry lives inside that manifest (II.10a hashes the
    # Ablaufdatum), so without this an expired approval could be resurrected by
    # editing one field
    if subject_manifest_hash(request.get("subject_manifest")) != request.get(
            "subject_manifest_hash"):
        raise ApprovalError(
            "consumed request %s does not hash to its own recorded hash -- the "
            "minted record was tampered with, so the approval grants nothing "
            "(fail-closed). Remedy: re-run the approval flow." % request_id,
            user_text="Es wurde keine Freigabe erteilt: der Nachweis zu dieser Freigabe passt "
                      "nicht mehr zu seiner eigenen Pruefsumme, wurde also nach deiner Zustimmung "
                      "veraendert. Es wird neu gefragt.",
        )
    return request


def proven_expiry(request: dict):
    """The approval's expiry, taken from the HASH-COVERED side.

    Read from the request's `subject_manifest`, not from `request.approval_expires`
    and never from the APR file. All three carry the same value, but only the
    manifest is inside the hash that `consumed_request` RECOMPUTES, so only there
    is the value tamper-evident. Reading it anywhere else made expiry a one-line
    edit away from resurrecting a lapsed permission, while II.10a demands the
    opposite ("Abgelaufene ... Routinefreigabe blockiert den Audit-Dispatch
    (fail-closed)").

    Honest limit: an editor that changes the manifest AND recomputes the hash in
    the request AND matches it in the approval file still passes -- the hash
    function is public. What is gone is every SINGLE-field edit. The remaining
    surface is closed by making the state directory kernel-only for tool writes
    (gate layer 3), not by arithmetic.
    """
    expires = (request.get("subject_manifest") or {}).get(EXPIRY_FIELD)
    if expires is None:
        return None
    try:
        return float(expires)
    except (TypeError, ValueError):
        raise ApprovalError(
            "minted request %s carries an unreadable expiry %r -- fail-closed; "
            "an approval whose validity cannot be read grants nothing. Remedy: "
            "re-run the approval flow." % (request.get("request_id"), expires)
        ) from None


def read_apr(state: ProjectState, apr_id: str) -> dict:
    path = os.path.join(state.root, "approvals", apr_id + ".yaml")
    try:
        return state._read_yaml(path)
    except FileNotFoundError:
        raise ApprovalError(
            "no approval %s. Remedy: the item's approval_ref is stale -- run "
            "`python scripts/harness.py validate`." % apr_id
        ) from None
