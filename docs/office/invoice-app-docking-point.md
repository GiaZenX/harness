# The docking point: how an invoice application hands its invoices to an office-kit project

**Who this is for.** The team building the invoice application (its own project; see the
decision record `DEC-0075` in the kit repository if you have access, and otherwise read on --
nothing below requires it). You produce outgoing invoices for one or more businesses; the office
kit **files, checks and books** them and writes none itself. This page is the whole interface:
what you drop, where, and what you get back.

**What the office kit is, in one paragraph.** A folder on the owner's machine that a small
business runs its back office from: an `inbox/` for documents, an `archive/` tree whose layout a
machine-readable filing plan decides, a CSV ledger per year, generated reports, and a set of
scripts a team of assistants runs. Nothing in it sends mail or talks to a tax office. Two rules of
that folder reach you: **a document is filed only under a rule the plan carries**, and **a number
range, once declared, is unbroken** -- a gap or a repeat is refused, not smoothed.

---

## 1. What you drop

One file per invoice document, in one of two shapes:

| Shape | File | What the kit reads |
|---|---|---|
| **ZUGFeRD / Factur-X** | a PDF/A-3 with the invoice XML embedded as an attachment (`factur-x.xml`, `zugferd-invoice.xml`, `xrechnung.xml` are the usual names, but the kit does not go by the name: it parses every attachment and takes the one that IS an e-invoice). Embed exactly one -- a PDF carrying two is refused with both names, never guessed between | the embedded XML; the PDF pages themselves are never read |
| **XRechnung** | the XML on its own | the XML |

The XML is EN 16931 in one of its two syntaxes: **UN/CEFACT CII** (root `CrossIndustryInvoice`)
or **UBL 2.1** (root `Invoice` or `CreditNote`). A PDF without an embedded XML, a scan, or an
XML of another shape is refused as *not judgeable* (exit 1), never guessed at.

**Type codes the kit books** (BT-3, UNTDID 1001):

| Code | Meaning | What the kit does |
|---|---|---|
| `380` | commercial invoice | books an `invoice` row |
| `381` | credit note | books a `credit_note` row; **must** carry the number it cancels in the preceding-invoice reference (BT-25), and that number must already be booked in the same range |
| `384` | corrected invoice | **refused by name** -- see the three cases below |
| anything else | | refused, the code named |

**Fields the kit requires** (a subset of the EN 16931 business rules; your own validator owns the
full rule set, the kit does not re-run it):

| Rule | Term | What has to be there |
|---|---|---|
| BR-01 | BT-24 | the specification identifier (CII `GuidelineSpecifiedDocumentContextParameter/ID`, UBL `CustomizationID`) |
| BR-02 | BT-1 | the invoice number |
| BR-03 | BT-2 | the issue date (CII format 102 `YYYYMMDD` or ISO) |
| BR-04 | BT-3 | the type code |
| BR-05 | BT-5 | the currency code |
| BR-06 | BT-27 | the seller's name -- **exactly the business name the range is declared with** (see §2) |
| BR-07 | BT-44 | the buyer's name |
| BR-09 | BT-40 | the seller's country code (postal address) |
| BR-11 | BT-55 | the buyer's country code |
| BR-13 | BT-109 | the total without VAT |
| BR-14 | BT-112 | the total with VAT |
| BR-16 | BG-25 | at least one invoice line |
| BR-CO-15 | BT-112 = BT-109 + BT-110 | **the money triple reconciles**: net + tax = gross, within one cent. A document that fails this is refused with all three figures named; the kit never takes one figure and derives the others |

The tax breakdown (BG-23) is read for the VAT rate and category: the kit books **one rate per
document** (its ledger row carries one), so an invoice with two VAT rates is accepted by the norm
check and then refused for booking with the sentence "book by hand". Category `S` books as
standard VAT, `AE` as reverse charge, `E`/`Z`/`K`/`G`/`O`/`L`/`M` as exempt; a seller the profile
marks as *Kleinunternehmer* (§ 19 UStG) with a zero tax total books as such.

**A category code outside that set is refused**, with the code and the set named, and so is a
VAT rate that does not read as a number. Both figures go into the ledger row, so both are read
off your document or the document is not booked -- the kit never fills either from the other.

**No breakdown at all and a VAT amount is refused too** (BG-23 is mandatory in EN 16931): without
it neither the rate nor the category of that amount stands anywhere in the document, and the kit
does not derive them from the total. And whatever the document says, the booking line the verdict
prints is handed to the ledger's OWN row check before you ever see it -- a document whose figures
would produce a row the ledger refuses (`net x (1 + rate) != gross`, a rate that is not 0 on an
exempt treatment) is refused HERE, with the ledger's own sentence, rather than accepted and then
stuck. Measured before that check existed: a document stating `19 %` with a tax of 0.00 came back
accepted and its booking failed one step later.
## 2. Where you drop it, and how the kit knows whose invoice it is

**Location:** the project's `inbox/` folder, **flat** -- no subfolders (the kit's inbox has none by
definition; a folder inside it is a document nobody files). The file name is yours; the invoice
number in the XML is what counts, not the name.

**Whose it is:** the kit does not look at folders or file names for that. The business's
bookkeeper declares every number range once, in the project's `master_data.yaml` under
`number_ranges`, and the kit picks **the one range whose pattern the invoice number matches in
full**:

```yaml
number_ranges:
  - key: shop_a                                   # the name every verdict prints
    business: "Muster Handel e.K."                # the seller name the document MUST carry
    pattern: "RE-(?P<year>\\d{4})-(?P<number>\\d{4})"   # (?P<number>) counts; (?P<year>) restarts per year
    issued_by: app                                # app | marketplace  (see §4)
    document_type: sales_invoice                  # the filing-plan class it files under
    category: sales_taxable                       # the ledger category it books under
    first: 1                                      # the first number of a fresh series
```

Two businesses are two entries with two patterns that cannot both match one number. A number no
range matches is **refused (exit 2)** -- the document carries a number nobody issued. Two ranges
matching one number is **not judgeable (exit 1)**: the declarations are ambiguous, and that is the
business's file, not yours. A document whose seller name is not the range's
`business` is refused ("issued in the name …") -- this is what keeps a supplier's invoice from ever
being booked as your customer's.

**Continuity.** For the matched range the kit reads every ledger year file and collects the
numbers already booked in the same series (the same `year` group, if the pattern has one). Where
the series **stands** is the highest number already booked, or -- with nothing booked in it yet --
the range's `first`; the verdict always says which of the two it read. The arriving number has to
be the stand + 1, or the `first` itself for an untouched series. Otherwise:

| Arriving number | Range `issued_by: app` | Range `issued_by: marketplace` |
|---|---|---|
| already booked | refused ("already booked", the row named) | refused |
| below where the series stands | refused, with the stand and its origin named | refused |
| above the stand + 1 | **refused**, with the stand, the arriving number and the missing ones named | **accepted**, the gap is reported in the verdict |

`(?P<number>...)` has to capture something that reads as a **decimal number** -- that capture is
what the series is ordered by, and a capture the kit cannot order is refused rather than sorted
as text. The same holds for `first`. Zero-padding is fine (`0042` is 42).

So the application never needs to ask the kit for the next number: it issues numbers without a
gap, and the kit's refusal is the tripwire if it did not.

## 3. What the kit answers

The bookkeeper (or the office manager) runs, from the project root:

```
python scripts/invoice_intake.py inbox/<file> [--task TSK-nnnn] [--json]
```

**Which code a NO carries is a definition, and you can branch on it:** a no about the DOCUMENT is
`2` -- your side fixes the document; a no about the BUSINESS's own records is `1` -- the business
fixes its records and the very same file then passes unchanged. Retrying an exit 1 with a changed
document is wasted work.

| Exit | Meaning | What is on stdout / stderr |
|---|---|---|
| `0` | **accepted** | the range and business, the continuity sentence, the archive destination the filing plan's rule gives the document, and the exact booking line; with `--json` the same as one object (`verdict`, `range`, `business`, `continuity`, `filing`, `booking`, `norm_rules_checked`) |
| `2` | **refused -- your document** | `[intake] REFUSED <file>: <the rule id, or the figures>` on stderr; nothing was staged or booked. With `--json` an object `{"verdict": "refused", "reasons": [...]}`. A missing mandatory field, a triple that does not reconcile, a type code the kit does not book, a number that continues no declared range, two VAT rates, a VAT category or rate the kit cannot read |
| `1` | **not judgeable -- the business's records** | no structured data in the file, or something on the project side: no ranges declared, two ranges matching one number, no filing rule (or two) for the class, a placeholder in the rule the intake cannot fill, a ledger category the vocabulary does not know, a `first` written as a word, a destination that is already taken |

**Accepted is not yet filed and not yet booked.** The kit's filing is a reviewed pipeline: the
verdict stages a proposal, two independent readings by two assistant runs have to agree on the
destination, then the file moves; then `invoice_intake.py <archive path> --book` writes the ledger
row (`income`, `invoice` or `credit_note`, the buyer as counterparty, your invoice number, net /
VAT rate / gross, `--open` unless a payment date is given). Your application sees none of that: for
you the contract ends at the verdict. If you want a machine-readable receipt, run the intake with
`--json` and keep the object.

**The kit does not answer** "what is the next number", "is this customer known", or "was this
paid". The first is yours by construction (§2), the other two are the business's own records.

## 4. The three marketplace cases, separated by law

These are not three configurations of one thing; the German VAT code treats them differently,
and the kit refuses the shapes that blur them (`DEC-0075 (5)`).

1. **Create** (the marketplace issues no invoice -- Kaufland). Your application issues the
   invoice: a `380` with the next number of the business's own range (`issued_by: app`). The kit
   accepts it exactly when the number continues the series.

2. **Cancel and reissue** (the marketplace issued an invoice in the seller's name that has to be
   replaced -- eBay). A "nicer version" of an invoice that already exists is **a second invoice
   over one delivery**, and § 14c UStG makes the VAT owed twice. So the correction is **two
   documents**: a `381` credit note whose BT-25 names the original number (the original must
   already be booked -- import it first, §4.3), then a **new `380` with the next number and no
   preceding-invoice reference**. The kit refuses a `380` that carries BT-25, and it refuses `384`
   outright: a "corrected invoice" is exactly the one-document shape that hides which number was
   cancelled.

3. **Import only** (the marketplace issues the invoice under its own numbering -- Shopify). Declare
   the marketplace's series as its own range with `issued_by: marketplace`. The kit files and books
   such a `380` and **reports** a gap instead of refusing it, because a missing number in a series
   another system issues may be that system's own cancellation and not your gap. It still refuses a
   repeat and a number issued in another name.

## 5. Worked example

Business "Muster Handel e.K.", range `shop_a` with pattern `RE-(?P<year>\d{4})-(?P<number>\d{4})`,
ledger already holds `RE-2026-0001` … `RE-2026-0003`.

```
$ python scripts/invoice_intake.py inbox/RE-2026-0004.xml
[intake] ACCEPTED RE-2026-0004: CrossIndustryInvoice, issued by Muster Handel e.K. (range shop_a),
         range shop_a / 2026: 4 continues the series (last issued 3)
[intake] filing:  mv inbox/RE-2026-0004.xml archive/finance/outgoing/2026/2026-09-01_Kaeufer-GmbH_sales_invoice.xml   (rule FP-002)
[intake] booking: python scripts/ledger_add.py --year 2026 --direction income --doc-type invoice ... --open

$ python scripts/invoice_intake.py inbox/RE-2026-0006.xml
[intake] REFUSED inbox/RE-2026-0006.xml: gap in range shop_a / 2026: last issued 3, arriving 6,
         2 number(s) missing in between (4..5) -- refused. Remedy: the application issues numbers
         without a gap; if the missing ones were cancelled, their cancellation documents arrive first.

$ python scripts/invoice_intake.py inbox/broken.xml
[intake] REFUSED inbox/broken.xml: BR-CO-15 (BT-112 = BT-109 + BT-110): the money triple does not
         add up — net 214.20, tax 40.70, gross 300.00: net + tax = 254.90, which is 45.10 away from
         the stated gross (tolerance one cent). ...
```

## 6. What is measured, and where

Every sentence above that says "refused" or "accepted" is held by a test that runs the shipped
script against a project built outside the kit repository. Each is named as a pytest node id, so
the name is a claim that rots visibly rather than a reassurance:

* `tools/test_office_package.py::test_an_app_produced_invoice_is_accepted_with_its_filing_and_booking_named`
  -- the three file shapes of §1, and that nothing is moved or booked;
* `::test_a_planted_violation_is_refused_with_the_figures_named` -- every refusal of §1 and §4, and
  the two of §2 that a booked series produces;
* `::test_a_project_side_gap_is_not_judgeable_and_a_document_fault_is_refused` -- the exit-code
  table of §3, case by case;
* `::test_the_intake_refuses_a_document_whose_booking_line_the_ledger_would_refuse` -- the two
  paragraphs of §1 on the breakdown and the ledger's row check, in BOTH directions: an accepted
  document's printed booking line is handed to the ledger and taken;
* `::test_the_gap_refusal_names_an_order_this_script_actually_walks` -- the cancelled-number order
  of §4.2, executed rather than read;
* `::test_a_series_the_intake_cannot_order_is_refused_and_never_crashes` -- the rest of §2's
  continuity: a number below where an untouched series stands, and a counting part the kit cannot
  order;
* `::test_two_documents_never_render_one_filing_destination` and
  `::test_a_pdf_carrying_two_invoice_attachments_is_refused_not_guessed` -- the two ways §1 and §2
  could have let one document overwrite or impersonate another;
* `::test_a_marketplace_range_reports_a_gap_and_a_credit_note_cancels_a_booked_invoice` -- cases 2
  and 3 of §4;
* `::test_the_docking_point_files_through_the_registered_chain_and_books` -- the pipeline after the
  verdict, through the office kit's registered hook chain.

Until 2026-09-06 these nine stood as bare names in their own code spans, which the repo's pointer
check does not read at all -- nine claims about coverage that nothing could contradict. The reader
behind the intake is the kit's e-invoice extractor, `scripts/einvoice_extract.py`, the same one
every incoming supplier invoice goes through.

## 7. What this contract does not cover

- **Your side of the norm.** The kit checks the rules in §1 and nothing else -- no XML schema, no
  Schematron, no code lists beyond the type codes it books. Validate before you drop.
- **Several VAT rates on one invoice.** Accepted by the norm check, refused for booking; the
  business books such a document by hand.
- **Payment.** An accepted invoice is booked as open. Payment dates come from the business's bank
  statements, not from you.
- **Delivery matching.** Three figures that reconcile off the wrong order pass the kit as they
  pass any arithmetic; the second reading in the kit's booking pipeline is the human catch for
  that, not a rule you can satisfy.
- **A change of the contract.** The range list is the project's (a kernel-written document on a
  user approval); the rule table in §1 is the script's `NORM_RULES`. A rule added to either side
  is a change to this page.
