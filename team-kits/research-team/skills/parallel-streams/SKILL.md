---
name: parallel-streams
description: >
  REFERENCE skill (no role owns it): how to let SEVERAL specialists work at the same time without
  breaking each other's checks — cutting the work by FILE OWNERSHIP, grouping requirements that
  share files, one tree per order, what an order runs and what it does not, and the merge that is a
  verification of its own. Open it BEFORE you cut a round into parallel orders, not after the first
  collision. NOT loaded at session start and named by no role's `skills:` frontmatter — open it with
  `/parallel-streams`. On Codex the generated mirror carries every skill directory, so it is also at
  `.agents/skills/parallel-streams/SKILL.md`.
# WHICH ORDERS NAME THIS SKILL (FR-0071) — read by `kernel.references.for_task`, which requires a
# match on BOTH axes.
#
# ROLES: the one role that cuts a round into orders at all. It is this kit's SESSION AGENT
# (`settings/settings.json`, key `agent`), and a session agent is bound without a lease while the
# reference names ride ON a lease (`kernel/dispatch.create_lease`, `REFERENCES_KEY`) — so no
# dispatch header will ever hand this declaration to the role it names. What delivers the skill is
# the lead's own procedure text, and that this end is wired too is
# `tools/test_parallel_streams.py::test_a_reference_skill_named_for_a_session_agent_is_named_by_a_text_it_reads`.
#
# TASK TYPES: the WHOLE vocabulary, because the cut is made before the orders are typed — a lead
# reading this has not yet decided what any of them will be. That the list stays the whole
# vocabulary as the vocabulary grows is
# `tools/test_parallel_streams.py::test_the_parallel_procedure_is_declared_for_every_task_type`.
reference_for:
  roles: [project-manager]
  task_types: [analysis, architecture, bugfix, design, docs, implementation, ops, research, review,
               test, ui]
---

# Parallel streams — several specialists at once, and the cut that makes it possible

> **What this is about.** Not "can I spawn two agents" — the kernel mints a lease per task and two
> tasks lease at the same time without complaint. The hard part is what they SHARE: one repository,
> one set of checks, one version stamp, one hole list. Two writers on genuinely different files
> still broke each other's check runs, because the checks span both halves of the tree. That
> measurement is the reason this procedure exists (`DEC-0057`), and the rules below are derived
> from it rather than invented.

## 1. Cut by FILE OWNERSHIP, and bundle at the GOAL — never inside a work order

Read each wish, **list the files it would touch**, and draw the GOALS around those lists. A cut by
subject ("the reporting work", "the approval work") reads well and is not a cut: two subjects meet
in the same file constantly, and the collision surfaces at the end, in the merge, where it is most
expensive.

**Wishes whose file lists overlap are merged into ONE approved goal at triage.** The wish ends
terminal with its pointer to the goal it joined, and what it asked for becomes part of what that
goal is measured against — your kit's requirement hierarchy already has that step, and its own
constitution names the item types. That goal then gets ONE work order, whose `allowed_scope` is
its ownership.

**Bundling one level lower — several requirements inside one work order — is the move this
procedure forbids.** The kernel gives a work order exactly one goal (`product_requirement`,
held by `tools/test_parallel_streams.py::test_a_work_order_carries_exactly_one_product_requirement`),
so every further requirement stuffed into it lives in prose fields: no index entry, no board
row, no rollup. `DEC-0067` retired that shape after a whole generation of streams had been cut the other
way.

**What bundling buys and what it costs.** The shared file is read once — one specialist builds
it, one verifier measures one contract — where two orders would have collided over it. The cost
is paid in one place: a blocking finding holds the whole goal, which is what the two caps below
bound.

**Two caps, and neither is a number.** A GOAL is only as large as one build pass and one
verification pass can carry; where it would exceed that, split it along the next file boundary and
record the split as a seam BEFORE the orders go out, because a split discovered in the merge is a
collision with a nicer name. And no more goals run AT ONCE than you can carry through their
rework rounds — the orders are cheap, your attention is not, and it is the measured ceiling.

## 2. Check the cut before you dispatch — and know what is checking it

The check runs over the WORK ORDERS of the goals you cut in §1 — one order per goal — and two of
them may not own a common file. "Own" is `allowed_scope` minus `forbidden_scope`, resolved
against the tree the same way `gate_write_scope` resolves it when it refuses a write: entries
without a wildcard match by prefix, `**` widens across directories, a single `*` does not, and BOTH
sides are case-folded before they are compared, so `Tools/**` and `tools/**` are one scope to the
door and have to be one scope to you. Comparing the scope TEXTS instead is not the check —
`src/**` and `src/api/handlers.py` share no characters and every file of the second lies in the
first.

**The kernel refuses the overlap it can SEE, and that is not all of it.** It mints one lease per
order and refuses the second when that order owns a file a RUNNING order already owns, with the
seam both orders declare subtracted first
(`tools/test_parallel_streams.py::test_the_second_lease_is_refused_when_the_scopes_overlap`,
`::test_a_seam_both_orders_declare_lets_the_second_lease_through`); `gate_write_scope` holds each
specialist inside its OWN order and has no opinion about the neighbour's. What the refusal compares
against are RUNNING leases only, so two orders that never run at the same time collide at the merge
and nothing here sees them. Your reading before the dispatch is what answers THAT, and
`python scripts/harness.py check-scopes` is the command that does it — and since generation 6 it
also leaves the RECORD a second BUILD lease under one goal needs (`DEC-0092` (2)): the kernel
refuses that lease until a record names the pair disjoint as the orders stand now, and writes the
record it admitted the builder on onto the lease (`measured_disjoint`).

Read the two orders side by side and answer three questions:

1. Does a file exist today that BOTH orders own? Resolve, do not compare strings.
2. Would a file one order **creates** fall into the other's scope? An empty directory both orders
   claim is a collision that has not happened yet.
3. Is what remains shared **declared**? See §5 — a shared file that is named in advance is a seam;
   the same file unnamed is a defect in the cut.

## 3. One tree per order

Each order works in its own checkout, so a check run for one order never judges the other's
half-finished edit. That is the half separate scopes do NOT buy: file lists can be disjoint while
the checks read the whole tree, and then neither order can produce a clean run while the other is
working.

Inside its own tree an order runs **only the checks that read the files it changed** — derived
from the changed files and the checks that read them, never from the topic of the work. The full
run belongs to the merge, once, on the united tree; a full run inside an order measures a tree
nobody will ever ship.

## 4. An order does not close itself

Only the united tree can be judged, so an order **hands back its changes and its record** rather
than declaring itself done: what it changed, what it measured, what it deliberately did not close,
and every shared file it touched. Version stamps an order makes are provisional — the release
carries exactly one, made after the merge, because a stamp is a fingerprint of the whole and two
orders stamping separately produce a third fingerprint nobody wrote.

## 5. Name the shared files BEFORE the work starts

Some files no order can own alone: the ones every order appends to, the texts that must agree with
each other, the stamps. Name them at cut time, with **who applies which half and in what order**,
and put that table into every order. Two things follow from having it: an order knows it must
REPORT a change to such a file instead of making it, and a collision the table did not predict is a
finding against the CUT — the one signal that says the ownership reading was wrong, and the only
one you get.

## 6. The merge is a verification of its own

Bringing the orders together is not bookkeeping. Contracts that cross orders are invisible from
inside any single one of them: a route one order registers and a check another order wrote about
it, a text one order changed and a check another order shipped for that text. Those findings can
only be seen on the united tree, and only by somebody looking. So the merge gets its own build
pass, its own verification pass and its own record — and it is where the seam table above is
applied, the stamp is made, and the full run happens.

## 7. What this procedure does NOT give you

Said here so nobody reads more into it than is built:

* **No refusal.** Nothing in this kit stops two overlapping orders from being dispatched (§2).
* **No isolation for the state directory.** The kernel writes the project's items in one place; an
  order proposes into its own staging area and the lead books the result. Two orders capturing
  items at the same time are two writers on one store.
* **No knowledge of a second tree anywhere in the kernel.** A lease names a task, not a checkout,
  so nothing can tell you which tree an order is working in — you carry that yourself, in the
  order and in the record.
