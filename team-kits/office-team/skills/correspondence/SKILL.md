---
name: correspondence
description: >
  REFERENCE skill (no role owns it): how an offer, a reminder (Mahnung) or a customer letter
  leaves this office -- as a DRAFT `scripts/letter_draft.py` renders from the ledger, the
  business profile and `correspondence.yaml` into `outbox/`, read once against `/humanizer`,
  and handed to the USER, who sends. Open it when a work order names it, or as the manager
  before the first letter of a session. NOT loaded at session start: `/correspondence`, and on
  Codex `.agents/skills/correspondence/SKILL.md`.
# WHICH ORDERS NAME THIS SKILL -- read by `kernel.references.for_task` (both axes must match).
# The manager, because `DEC-0082` decided FR-0033's open question in favour of a WORKFLOW the
# manager runs rather than a role of its own -- so this skill IS the procedure, not a role's
# reference; the bookkeeper, because a reminder's figures are the ledger's and a second run of that
# role is the second reader a Mahnung gets when the PROC asks for one. Should the user ever want a
# correspondence role, it lists this skill as its procedure and nothing here changes.
reference_for:
  roles: [office-manager, bookkeeper]
  task_types: [docs]
---

# Correspondence -- offers, reminders, letters that leave the house as drafts

## What this is, and what it is not

The kit writes letters and sends none (constitution §2.2). `scripts/letter_draft.py` renders one
draft per call into `outbox/<role>/`, from the data the business has already recorded -- the
sender from `business_profile.yaml`, the VAT treatment from its `tax.kleinunternehmer`, the payment
term from `receivables.payment_terms_days`, a reminder's figures from the ledger row it names, and
the terms every letter carries (form of address, closing, offer validity, the dunning ladder) from
`correspondence.yaml`. It invents no fee, no term and no address (measured:
`tools/test_office_package.py::test_a_term_the_business_never_recorded_is_refused_with_its_route`),
and a value it cannot USE is a refusal and never a traceback -- unreadable as a number or a
date (`::test_a_value_letter_draft_cannot_read_is_refused_and_never_crashes`) and readable but
unwritable, a NaN, an infinity or a negative rate
(`::test_a_number_letter_draft_cannot_write_into_a_letter_is_refused`): where the profile carries none it
prints a placeholder that says so, and where the business declared no payment term it refuses to
call an invoice overdue.

It is not an invoice writer. Outgoing invoices are the invoice application's (DEC-0075); the
kit's half of that is `scripts/invoice_intake.py`, not this.

## The route, step by step

1. **The occasion.** A reminder's occasion is the session-start duty register: it names the
   income rows older than the payment term (`_duties.receivable_duties`), and the PROC that
   covers reminders says which level the business sends when. An offer's or a letter's occasion
   is the user's request, or a PROC step that names it.
2. **The draft.** One script call per letter:
   - `python scripts/letter_draft.py offer --to "<Kunde>" --line "<Leistung>;<Menge>;<Einzelpreis netto>" [...]`
   - `python scripts/letter_draft.py reminder --entry <Lnnnn-nnnn> [--level n]`
   - `python scripts/letter_draft.py letter --to "<Kunde>" --subject "<Betreff>" --body-file <text.md>`
   The path it prints is the only place the draft exists. The first line of the file says it is a
   draft and what has to happen before it may leave.
3. **The reading.** Before the draft goes to the user, read it against `/humanizer` -- the whole
   text, on the properties that skill states (sentence-length variance, dash and colon density,
   hedging, discourse markers, the German layer). The script writes for the countable half of that
   bar and a test holds it there
   (`tools/test_office_package.py::test_the_three_drafts_pass_the_countable_half_of_the_humanizer_bar`);
   the other half is yours, and it is where a real customer hears a machine or does not. Leave the
   one line of trace `/humanizer` asks for in your envelope, never in the letter.
   A letter whose FACTS are wrong -- a figure, a date, a name -- is not a style question: correct
   the source (the ledger row, the profile, the terms document through their kernel routes) and
   render again. Never edit a number into a draft by hand.
4. **The hand-over.** Put the draft in front of the USER with its path and one sentence on what it
   is; the user sends. A reminder that the user decides not to send is not deleted -- the outbox is
   theirs -- and a row that turns out to be paid is booked with its payment date so the register
   stops naming it.

## Duties this route carries, and what enforces them

- **Nothing sends.** No script, no hook and no role of this kit sends mail; `gate_write_scope`
  and the outbound rules of the constitution stand around it, and the tray is the user's.
- **The reading before the hand-over is a DUTY, not a gate.** No hook reads a draft in `outbox/`,
  and none is built: a check over prose would be a heuristic (`DEC-0056`). The duty is carried
  by whoever hands the draft over, and this skill is where it is written down.
- **WHAT THIS WORKFLOW DOES NOT GIVE YOU** (`DEC-0082` (3)), said here because the alternative it
  was chosen over did give it: **no second run reads a letter before it leaves** -- the manager
  reviews its own draft and the USER is the second reader; and **no parallel production** -- one
  script run and one review pass per letter, in order. Both were what a correspondence ROLE would
  have added, and the user chose the workflow knowing that. Neither is a gap to work around: a
  reminder that warrants two pairs of eyes gets them from a PROC (next bullet).
- **A second run for a reminder** is the PROC's decision: dispatch the bookkeeper with the row id
  and this skill, without the first draft, and put both readings in front of the user when they
  differ. The kit ships no such requirement by default; for the same reason the ladder in
  `correspondence.yaml` ships EMPTY -- after how many days a business writes, what it calls the
  letter and whether it charges a fee are the user's terms, and a reminder run before they are
  declared is refused with the route named (bullet below).
- **The terms document grows through the kernel.** A new dunning level, a changed closing, a
  longer offer validity: stage `correspondence.yaml` as it should stand in `staging/<TSK-ID>/`
  and ask for `apply-proposal` (an addition) or `revise-document` (a changed term); the user
  approves exactly that, the kernel writes it (constitution §6).

## Output to the manager (when dispatched)

The result envelope as every specialist writes it: `summary`, the draft paths under `outputs`,
the `/humanizer` trace line under `evidence`, and under `followups` every fact you could not read
off the sources -- an address the profile does not carry, a row without a payment term -- as a
question, never as a value you filled in.
