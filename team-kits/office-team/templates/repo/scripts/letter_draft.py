#!/usr/bin/env python3
"""
letter_draft.py — an offer, a reminder (Mahnung) or a customer letter as a DRAFT in outbox/ (FR-0033).

    python scripts/letter_draft.py offer --to "Kunde GmbH" --line "Beratung (Tag);2;450.00"
    python scripts/letter_draft.py reminder --entry L2026-0007 [--level 2] [--today 2026-09-05]
    python scripts/letter_draft.py letter --to "Kunde GmbH" --subject "Ihre Anfrage" --body-file t.md

WHAT IT READS, and it invents none of it: the SENDER from `business_profile.yaml` (`business.name`,
`business.billing_address`), the VAT of an offer from `tax.kleinunternehmer` there, the payment
term of a reminder from `receivables.payment_terms_days`, the reminder's figures from the ledger
row `--entry` names, the terms every letter carries -- form of address, closing, offer validity,
the dunning ladder -- from `correspondence.yaml`, and the tone line from `content_guidelines.yaml`,
which it prints into the draft's header as the bar the reviewer reads the text against.

WHAT IT WRITES: one Markdown file, `outbox/<role>/<date>_<recipient>_<kind>.md`, and nothing
else -- no ledger row, no item, no send. The first line of the file says it is a draft and names
the two steps between it and the customer: the manager's reading against `/humanizer`, and the
USER's send (constitution §2.2, `skills/correspondence/SKILL.md`). Neither is a gate; both are
duties, and the file says so rather than implying a check that does not run.

WHAT IT REFUSES rather than guesses -- and this is a DEFINITION, not a list: every value that
reaches the customer's letter is one somebody recorded, so where the record is missing the script
refuses and names the route that fills it, and where the record is unreadable it refuses and names
the field. That covers the sender, the payment term, the dunning ladder, the form of address, the
closing, an offer's validity and an offer's VAT rate. Until 2026-09-06 four of them had a fallback
in the code (`or 14`, `or "Sie"`, `or "Mit freundlichen Gruessen"`, argparse `default="19"`), so a
letter left the house with four values the kit had chosen while three shipped texts said it chose
none; and five numbers and dates went into `int()`, `Decimal()` and `fromisoformat()` unguarded, so
a typo in the document the user fills through `apply-proposal` ended in a Python traceback. The
FOURTH default (`--vat-rate`, argparse `default="19"`) survived the first repair while three texts
said it had not, and the reader that replaced the unguarded reads turned out to be weaker than the
one it stood beside -- `NaN` a traceback, `-19` a negative tax line in a customer's letter. Both are
closed now: `a_number` is the file's one numeric reader (readable, finite, signed as the caller
allows, printed plain), `a_date` the one date reader, `money` is `a_number` plus the cent, and no
value reaches a letter through anything else. Measured, all of it, and held by
`tools/test_office_package.py::test_a_value_letter_draft_cannot_read_is_refused_and_never_crashes`,
`::test_a_number_letter_draft_cannot_write_into_a_letter_is_refused` and
`::test_a_term_the_business_never_recorded_is_refused_with_its_route`.

THE TEXTS ARE WRITTEN FOR THE COUNTABLE HALF OF THE HUMANIZER BAR, and that half is measured
(`tools/test_office_package.py::test_the_three_drafts_pass_the_countable_half_of_the_humanizer_bar`):
sentence lengths that vary, no unspaced em dash, no "nicht nur … sondern auch", no closing
summary, one form of address. The other half -- whether a person reads it as written by one --
is the reviewer's, and no script claims it.

Exit 0 = draft written (path printed). Exit 1 = refused (reason on stderr), nothing written.
"""
import argparse
import csv
import datetime
import os
import re
import sys
from decimal import ROUND_HALF_UP, Decimal

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "project_memory")
PROFILE = os.path.join(STATE, "business_profile.yaml")
TERMS = os.path.join(STATE, "correspondence.yaml")
GUIDELINES = os.path.join(STATE, "content_guidelines.yaml")
CENT = Decimal("0.01")
ADDRESS_FORMS = {"Sie": ("Sehr geehrte Damen und Herren,", "Sie", "Ihre", "Ihnen"),
                 "du": ("Hallo,", "du", "deine", "dir")}
NAME_SAFE_RX = re.compile(r"[^A-Za-z0-9._-]+")


def refuse(message):
    sys.stderr.write("[letter_draft] REFUSED: %s\n" % message)
    sys.exit(1)


# THE ROUTE THAT FILLS `correspondence.yaml`, written once and printed by every refusal about it.
# A missing term is only not a dead end while the refusal carries this line (BUG-0041's class).
# The staged copy is named as the THING and not as a path inside the state directory: a remedy
# that spells `staging/<key>/<name>` picks the reader's place for them (DEC-0024), and the kernel
# refuses any proposal that is not in the task's own proposal area anyway
# (`tools/test_migrate.py::test_no_remedy_literal_this_repo_ships_names_a_place_inside_a_state_directory`,
# red on the generation-5 merge's first delivery run with the path spelled here).
TERMS_ROUTE = ("Remedy: the manager stages correspondence.yaml with it in the task's own proposal "
               "area (the file's own comments show the fields) and runs `request-approval "
               "document_proposal --kit-document correspondence.yaml --proposal <the staged copy> "
               "--reason <reason>`; the USER answers it, and `apply-proposal` writes exactly that.")


def a_value(text, what, read, shape):
    """`text` read by `read`, or a refusal naming WHERE it came from and what shape was needed.

    Every number and every date this script prints comes from something a person wrote: a command
    line, a ledger row, or `correspondence.yaml` -- the document the kit tells a NON-DEVELOPER to
    fill through `apply-proposal`. Until 2026-09-06 five of them went straight into `int()`,
    `Decimal()` or `date.fromisoformat()`, so a typo there ended in a Python traceback where the
    line below promises "Exit 1 = refused (reason on stderr), nothing written".

    IT ANSWERS ONLY THE "CAN IT BE READ" HALF, which is why nothing calls it directly any more: as
    the whole answer for a NUMBER it was measured weaker than `money`, the reader it stood beside --
    `Decimal("NaN")` and `Decimal("Infinity")` are valid Decimals, so `--vat-rate NaN` came out of
    `eur()` as a traceback, and nobody asked about the sign, so `--vat-rate -19` rendered
    "zuzueglich -19 % Umsatzsteuer" into a letter to a customer. `a_number` and `a_date` below are
    the two readers this file has, and both go through here for the reading itself.
    """
    try:
        return read(str(text).strip())
    except (ValueError, ArithmeticError):
        refuse("%s is %r, and this script needs %s there" % (what, str(text), shape))


def a_number(text, what, negative=False):
    """`text` as the number it has to be: readable, FINITE, and negative only where that is allowed.

    THE ONE NUMERIC READER OF THIS FILE. Two of them had come to answer one question differently:
    `money` refused a non-finite and a negative amount, `a_value` refused neither, and `--vat-rate`
    went through the second -- so both classes this script exists to keep out of a customer's letter
    came back in through the newer reader (measured 2026-09-06: `NaN` a traceback, `-19` a negative
    tax line and a total of 81,00 EUR on a 100,00 EUR offer). `einvoice_extract._amount` carries the
    non-finite half of the lesson with its own measurement on the INCOMING side; this is it on the
    outgoing one. `money` is this reader plus the cent, and nothing else parses a number here
    (`tools/test_office_package.py::test_a_number_letter_draft_cannot_write_into_a_letter_is_refused`).
    """
    value = a_value(text, what, lambda one: Decimal(one.replace(",", ".")), "a number")
    if not value.is_finite():
        refuse("%s is %r, which is not a finite number and cannot stand in a letter" % (what,
                                                                                        str(text)))
    if value < 0 and not negative:
        refuse("%s is %r, and this script writes no negative %s into a letter to a customer"
               % (what, str(text), what))
    return value


def a_count(text, what):
    """A whole, non-negative number -- days, a dunning level -- through the one numeric reader."""
    value = a_number(text, what)
    if value != value.to_integral_value():
        refuse("%s is %r, and this script needs a whole number there" % (what, str(text)))
    return int(value)


def a_date(text, what):
    """A calendar date in the one spelling the ledger and the command line use."""
    return a_value(text, what, datetime.date.fromisoformat, "a YYYY-MM-DD date")


def plain(value):
    """A decimal AS A GERMAN TEXT SETS IT: `1E+2` -> `100`, `19.00` -> `19`, `19.50` -> `19,5`.

    Two rules in one function because they answer one question -- what a number looks like in this
    letter -- and both were measured wrong in it. `Decimal.normalize` alone keeps the exponent, so
    `--vat-rate 1e2` wrote `zuzueglich 1E+2 % Umsatzsteuer` (verify round 2, R7); and the decimal
    POINT it then kept put two conventions in one sentence, beside an amount `eur()` had already
    set German -- `zuzueglich 19.5 % Umsatzsteuer: 19,50 EUR` (verify round 3, V3-2). `eur()` is the
    same rule for money; this is it for everything else a letter prints
    (`tools/test_office_package.py::test_a_rate_a_person_wrote_in_exponent_form_reads_as_a_number_in_the_letter`).
    """
    value = value.normalize()
    whole = value.quantize(Decimal(1)) if value == value.to_integral_value() else value
    return ("%s" % whole).replace(".", ",")


def a_term(terms, key, what, read=None):
    """The term `key` of `correspondence.yaml`, or a refusal naming it and the route that fills it.

    NO DEFAULT, ever: a term is what the business decided, and a default is the kit deciding for
    it in a letter to a customer -- measured 2026-09-06 with the terms removed, four kit-chosen
    values stood in the draft while three shipped texts said the kit invents none.
    """
    value = terms.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        refuse("correspondence.yaml carries no `%s`, and this script invents no %s. %s"
               % (key, what, TERMS_ROUTE))
    return read(value, "correspondence.yaml `%s`" % key) if read else value


def _load(path, what):
    try:
        import yaml
    except ImportError as exc:
        refuse("PyYAML is missing (%s): pip install -r requirements-office.txt" % exc)
    if not os.path.isfile(path):
        refuse("%s is missing, and a letter needs %s from it"
               % (os.path.relpath(path, ROOT).replace(os.sep, "/"), what))
    with open(path, encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}
    return document if isinstance(document, dict) else {}


def money(text, what):
    """An amount: the one numeric reader, rounded to the cent. No second answer about NaN or sign."""
    return a_number(text, what).quantize(CENT, rounding=ROUND_HALF_UP)


def eur(value):
    """German money: 1.234,56 EUR."""
    whole, _dot, cents = ("%.2f" % value).partition(".")
    whole = "{:,}".format(int(whole)).replace(",", ".")
    return "%s,%s EUR" % (whole, cents)


def sender_block(profile):
    business = profile.get("business") or {}
    name = str(business.get("name") or "").strip()
    if not name:
        refuse("business_profile.yaml carries no `business.name`; a letter without a sender is "
               "not a draft anybody can send")
    address = str(business.get("billing_address") or "").strip()
    if not address or address.lower().startswith("see "):
        address = "[Anschrift ergänzen — steht bewusst nicht in business_profile.yaml]"
    return name, [name, address]


def terms_of():
    terms = _load(TERMS, "the form of address and the closing")
    form = str(a_term(terms, "address", "form of address")).strip()
    if form not in ADDRESS_FORMS:
        refuse("correspondence.yaml `address` is %r; the two forms this script writes are Sie and "
               "du" % form)
    a_term(terms, "closing", "closing line")
    return terms, form


def tone_line():
    guidelines = _load(GUIDELINES, "the tone") if os.path.isfile(GUIDELINES) else {}
    return str(guidelines.get("tone") or "").strip() or "(content_guidelines.yaml nennt keinen Ton)"


def header(kind, tone, sender):
    return ("<!-- ENTWURF %s, erzeugt von scripts/letter_draft.py am %s für %s. NICHT versendet: "
            "der Büro-Manager liest den Text gegen /humanizer (Ton laut content_guidelines.yaml: "
            "%s), dann versendet der NUTZER (AGENTS.md §2.2). -->"
            % (kind, datetime.date.today().isoformat(), sender, tone))


def frame(lines_sender, recipient, date, subject, body, closing, signer):
    """The letter as one Markdown text: sender, recipient, date, subject, body, closing."""
    out = list(lines_sender) + ["", recipient, "", date.strftime("%d.%m.%Y"), "",
                                "**%s**" % subject, ""]
    out += body
    out += ["", closing, signer]
    return out


def write_draft(role, recipient, kind, lines):
    directory = os.path.join(ROOT, "outbox", role)
    os.makedirs(directory, exist_ok=True)
    stem = "%s_%s_%s" % (datetime.date.today().isoformat(), _slug(recipient), kind)
    path = os.path.join(directory, stem + ".md")
    counter = 2
    while os.path.exists(path):
        path = os.path.join(directory, "%s-%d.md" % (stem, counter))
        counter += 1
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


def _slug(text):
    return NAME_SAFE_RX.sub("-", str(text or "").strip()).strip("-") or "unbekannt"


# ---------------- offer -------------------------------------------------------------------------
def offer(args, profile, terms, form):
    signer, sender = sender_block(profile)
    salutation, _you, _your, _to_you = ADDRESS_FORMS[form]
    positions, total_net = [], Decimal("0")
    for index, raw in enumerate(args.line or [], start=1):
        parts = [part.strip() for part in raw.split(";")]
        if len(parts) != 3:
            refuse("--line %r: three parts separated by ';' -- text;quantity;unit price net" % raw)
        text, quantity, unit = parts
        amount = money(quantity, "quantity") * money(unit, "unit price")
        positions.append((index, text, quantity, money(unit, "unit price"),
                          amount.quantize(CENT, rounding=ROUND_HALF_UP)))
        total_net += positions[-1][4]
    if not positions:
        refuse("an offer needs at least one --line")
    kleinunternehmer = (profile.get("tax") or {}).get("kleinunternehmer")
    valid_days = a_term(terms.get("offer") or {}, "valid_days", "offer validity", read=a_count)
    today = datetime.date.today()
    valid_until = today + datetime.timedelta(days=valid_days)
    body = [salutation, "",
            "vielen Dank für %s Anfrage. Wir bieten %s an:" % (
                "Ihre" if form == "Sie" else "deine", "Ihnen" if form == "Sie" else "dir"), "",
            "| Pos. | Leistung | Menge | Einzelpreis (netto) | Betrag (netto) |",
            "|---|---|---|---|---|"]
    body += ["| %d | %s | %s | %s | %s |" % (index, text, quantity, eur(unit), eur(amount))
             for index, text, quantity, unit, amount in positions]
    body += ["", "Summe netto: %s" % eur(total_net)]
    if kleinunternehmer is True:
        body += ["Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.",
                 "**Gesamtbetrag: %s**" % eur(total_net)]
    else:
        if not str(args.vat_rate).strip():
            refuse("this business is not a Kleinunternehmer (business_profile.yaml `tax."
                   "kleinunternehmer`), so an offer states a VAT rate and this script invents "
                   "none. Remedy: `--vat-rate 19` (or the rate that applies to this service).")
        rate = a_number(args.vat_rate, "--vat-rate")
        vat = (total_net * rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        body += ["zuzüglich %s %% Umsatzsteuer: %s" % (plain(rate), eur(vat)),
                 "**Gesamtbetrag: %s**" % eur(total_net + vat)]
    body += ["", "Dieses Angebot gilt bis zum %s." % valid_until.strftime("%d.%m.%Y"),
             "Bei Fragen rufen %s uns an. Wir freuen uns auf den Auftrag."
             % ("Sie" if form == "Sie" else "du")]
    if args.note:
        body += ["", args.note]
    lines = [header("Angebot", tone_line(), signer), ""]
    lines += frame(sender, args.to, today, "Angebot vom %s" % today.strftime("%d.%m.%Y"), body,
                   str(terms["closing"]), signer)
    return write_draft(args.role, args.to, "angebot", lines)


# ---------------- reminder ----------------------------------------------------------------------
def level_of(step):
    """A ladder step's `level` as the whole number it is sorted, picked and named by.

    FOUR readers used to spell `int(one.get("level") or 0)` for themselves; `correspondence.yaml`
    is the user's own document, so `level: "zwei"` ended each of them in a traceback.
    """
    return a_count(step.get("level"), "a reminder step's `level`")


def ledger_row(entry_id):
    directory = os.path.join(ROOT, "ledger")
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        names = []
    for name in names:
        if not re.match(r"^[0-9]{4}\.csv$", name):
            continue
        with open(os.path.join(directory, name), encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if (row.get("id") or "").strip() == entry_id:
                    return row
    refuse("no ledger row carries the id %r" % entry_id)


def reminder(args, profile, terms, form):
    signer, sender = sender_block(profile)
    salutation, you, your, to_you = ADDRESS_FORMS[form]
    row = ledger_row(args.entry)
    if row.get("direction") != "income":
        refuse("%s is not an income row; a reminder is written to a customer who owes us" % args.entry)
    if (row.get("payment_date") or "").strip():
        refuse("%s is paid (%s); nothing to remind" % (args.entry, row.get("payment_date")))
    days = (profile.get("receivables") or {}).get("payment_terms_days")
    if not isinstance(days, int) or isinstance(days, bool) or days <= 0:
        refuse("business_profile.yaml sets no `receivables.payment_terms_days`; the kit invents "
               "no payment term, so it cannot say that one ran out")
    today = a_date(args.today, "--today") if args.today else datetime.date.today()
    doc_date = a_date(row.get("doc_date"), "%s's doc_date in the ledger" % args.entry)
    recipient = str(row.get("counterparty") or "").strip()
    if not recipient:
        refuse("%s names no counterparty, so there is nobody to address the reminder to; a "
               "letter without a recipient is not a draft anybody can send" % args.entry)
    due = doc_date + datetime.timedelta(days=days)
    overdue = (today - due).days
    if overdue < 0:
        refuse("%s is due on %s, %d day(s) from %s; a reminder before the term ran out is not one"
               % (args.entry, due.isoformat(), -overdue, today.isoformat()))
    ladder = sorted((one for one in terms.get("reminders") or [] if isinstance(one, dict)),
                    key=level_of)
    if not ladder:
        refuse("correspondence.yaml carries no `reminders` ladder, and this script invents no "
               "step: after how many days you write, what you call the letter and whether it "
               "carries a fee are yours and your advisor's to decide. Remedy: the manager "
               "stages correspondence.yaml with the steps in the task's own proposal area (the "
               "file's own comment shows the fields) and runs `request-approval "
               "document_proposal --kit-document correspondence.yaml --proposal <the staged "
               "copy> --reason "
               "<reason>`; you answer it, and `apply-proposal` writes exactly that.")
    reached = [one for one in ladder
               if a_count(one.get("days_after_due"),
                          "a reminder step's `days_after_due`") <= overdue] or ladder[:1]
    step = reached[-1]
    if args.level:
        matching = [one for one in ladder if level_of(one) == args.level]
        if not matching:
            refuse("no reminder level %d in correspondence.yaml" % args.level)
        step = matching[0]
    gross = money(row.get("gross"), "gross")
    fee = money(step.get("fee") or "0", "fee")
    pay_by = today + datetime.timedelta(days=7)
    title = str(step.get("title") or "").strip()
    if not title:
        refuse("reminder level %d in correspondence.yaml carries no `title`, and this script "
               "invents no name for a letter that goes to a customer. %s"
               % (level_of(step), TERMS_ROUTE))
    body = [salutation, "",
            "zu unserer Rechnung %s vom %s über %s haben wir bis heute keinen Zahlungseingang "
            "festgestellt." % (row.get("invoice_no") or args.entry, doc_date.strftime("%d.%m.%Y"),
                               eur(gross)),
            "Das Zahlungsziel von %d Tagen ist am %s abgelaufen. Das sind heute %d Tage."
            % (days, due.strftime("%d.%m.%Y"), overdue), ""]
    if fee > 0:
        body += ["Für diese Mahnung berechnen wir eine Mahngebühr von %s." % eur(fee),
                 "Der offene Betrag beläuft sich damit auf %s." % eur(gross + fee), ""]
    body += ["Bitte überweisen %s den Betrag bis zum %s auf das %s bekannte Konto."
             % (you, pay_by.strftime("%d.%m.%Y"), to_you),
             "Hat sich %s Zahlung mit diesem Schreiben überschnitten, ist es gegenstandslos."
             % your.capitalize()]
    lines = [header(title, tone_line(), signer), ""]
    lines += frame(sender, recipient, today,
                   "%s: Rechnung %s vom %s" % (title, row.get("invoice_no") or args.entry,
                                               doc_date.strftime("%d.%m.%Y")),
                   body, str(terms["closing"]), signer)
    return write_draft(args.role, recipient, "mahnung-%d" % level_of(step), lines)


# ---------------- letter ------------------------------------------------------------------------
def letter(args, profile, terms, form):
    signer, sender = sender_block(profile)
    salutation = ADDRESS_FORMS[form][0]
    if not os.path.isfile(args.body_file):
        refuse("--body-file %s does not exist" % args.body_file)
    with open(args.body_file, encoding="utf-8") as handle:
        text = handle.read().strip()
    if not text:
        refuse("the body file is empty")
    lines = [header("Brief", tone_line(), signer), ""]
    lines += frame(sender, args.to, datetime.date.today(), args.subject,
                   [salutation, ""] + text.splitlines(),
                   str(terms["closing"]), signer)
    return write_draft(args.role, args.to, "brief", lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("kind", choices=("offer", "reminder", "letter"))
    parser.add_argument("--to", default="", help="the recipient as it stands on the letter")
    parser.add_argument("--line", action="append", help="offer: 'text;quantity;unit price net'")
    # NO DEFAULT (R1 of verify round 2): three texts said this one was gone while it stood, and
    # an offer run without the flag put the kit's 19 % into a customer's letter. The refusal in
    # `offer` names the flag and an example rate.
    parser.add_argument("--vat-rate", default="", help="offer: the VAT rate unless § 19 UStG")
    parser.add_argument("--note", default="", help="offer: one closing paragraph of your own")
    parser.add_argument("--entry", default="", help="reminder: the ledger row id (L2026-0007)")
    parser.add_argument("--level", type=int, default=0, help="reminder: force a ladder level")
    parser.add_argument("--today", default="", help="reminder: the date to count from (tests)")
    parser.add_argument("--subject", default="", help="letter: the subject line")
    parser.add_argument("--body-file", default="", help="letter: a file with the body text")
    parser.add_argument("--role", default="office-manager",
                        help="the outbox subfolder (the role handing the draft over)")
    args = parser.parse_args(argv)
    profile = _load(PROFILE, "the sender")
    terms, form = terms_of()
    if args.kind == "offer":
        if not args.to:
            refuse("--to is required for an offer")
        path = offer(args, profile, terms, form)
    elif args.kind == "reminder":
        if not args.entry:
            refuse("--entry is required for a reminder")
        path = reminder(args, profile, terms, form)
    else:
        if not (args.to and args.subject and args.body_file):
            refuse("--to, --subject and --body-file are required for a letter")
        path = letter(args, profile, terms, form)
    print("[letter_draft] draft written: %s (not sent -- review, then the user sends)"
          % os.path.relpath(path, ROOT).replace(os.sep, "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
