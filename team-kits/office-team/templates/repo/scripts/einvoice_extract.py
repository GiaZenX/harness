#!/usr/bin/env python3
"""
einvoice_extract.py — structured invoice data from e-invoices (XRechnung XML / ZUGFeRD PDF).

E-invoice FIRST: since 2025 German B2B invoices arrive as structured XML (XRechnung, or embedded
in a ZUGFeRD/Factur-X PDF). Parsing XML is deterministic — no OCR guessing, no hallucinated
amounts. It reads the CII (CrossIndustryInvoice) and UBL (Invoice/CreditNote) syntaxes and
nothing else: a plain PDF or a scan carries no structured data and is not parsed here. Anything
not found prints as MISSING (the bookkeeper treats it as UNCLEAR, never invents it).

Every field is read from the element its syntax puts it in — never via a name a line item can
answer too. That shortcut returned the FIRST LINE ITEM's total as the document net on a real
12-line invoice, silently and with exit 0 (BUG-0072).

Usage: python scripts/einvoice_extract.py <file.xml|file.pdf>
Output: key: value lines (seller, invoice_no, issue_date, currency, net, tax, gross).
Exit 0 = extracted, and the money triple adds up.
Exit 1 = no structured data found (fall back to careful reading + the arithmetic check in
         ledger_add.py).
Exit 2 = extracted, but the money triple does not add up or is incomplete. The three figures are
         printed marked UNRECONCILED and must not be booked. That check is ARITHMETIC ONLY: a
         triple that adds up can still be the wrong document's — no reader here can see that.
"""
import os
import re
import sys
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

try:
    # supplier XML is UNTRUSTED input: defusedxml neutralizes XXE/billion-laughs, which the
    # stdlib parser does not fully — no silent fallback to an unsafe parser.
    import defusedxml.ElementTree as ET  # type: ignore[import-untyped]
    from xml.etree.ElementTree import ParseError
except ImportError:
    ET = None
    ParseError = Exception

# One cent, in both of its roles: the quantum every amount is rounded to and the tolerance the
# reconciliation allows (inclusive — one cent off still passes, two do not). ROUND_HALF_UP is the
# commercial rounding a German invoice is written with; EN 16931 amounts carry at most two
# decimals, so the rounding only ever bites on a document that does not conform to it.
# `tools/test_hooks.py::test_einvoice_reconciliation_tolerance_is_one_cent_inclusive` measures
# both sides of that edge.
CENT = Decimal("0.01")
UNRECONCILED = "(UNRECONCILED - do not book)"


# THE TWO SYNTAXES THIS READER KNOWS, by the local name of their root element. ONE declaration,
# TWO readers: `parse_xml` branches on it to decide which spellings to read, and `_is_an_einvoice`
# asks whether an embedded attachment is an invoice at all. Written here because a second answer to
# "is this an e-invoice" was measured to be wider than this one and to refuse a legitimate PDF.
CII_ROOT = "CrossIndustryInvoice"
UBL_ROOTS = ("Invoice", "CreditNote")
EINVOICE_ROOTS = (CII_ROOT,) + UBL_ROOTS


def _local(el):
    """The element name without the namespace ElementTree expands into the tag."""
    return el.tag.rsplit("}", 1)[-1]


def _text(el):
    return (el.text or "").strip() if el is not None else ""


def _child(parent, name):
    """First DIRECT child with this local name, or None."""
    if parent is None:
        return None
    for el in parent:
        if _local(el) == name:
            return el
    return None


def _count(root, name):
    """How many elements ANYWHERE under root carry this local name (BR-16: at least one line)."""
    return sum(1 for el in root.iter() if _local(el) == name) if root is not None else 0


def _anchor(root, name):
    """First element ANYWHERE under root with this local name, or None.

    Called only with names their syntax scopes to the DOCUMENT level, which is what makes a
    whole-tree search safe here: CII spells the line-level counterparts differently
    (`SpecifiedLineTradeSettlement` beside `ApplicableHeaderTradeSettlement`), and UBL keeps the
    line ones inside `InvoiceLine`. The amounts are then read from WITHIN that element, so a name a
    line item also answers to (`LineTotalAmount`, `TaxAmount`) cannot reach the caller:
    `test_einvoice_reads_the_document_element_not_a_line_of_the_same_name` is what holds that, and
    it is a different question from the name-order preference `_pick` below owns.
    """
    for el in root.iter():
        if _local(el) == name:
            return el
    return None


def _pick(parents, *names, currency="", deep=False):
    """Text of the first non-empty match, in the ORDER OF THE NAMES — not in document order.

    Document order is half of BUG-0072: `_txt(root, "TaxBasisTotalAmount", "LineTotalAmount")`
    matched either name and took whichever came first in the file, so even inside one summation
    the pre-discount `LineTotalAmount` won over the `TaxBasisTotalAmount` two lines below it
    (`tools/test_hooks.py::test_einvoice_cii_document_allowance_net_is_the_tax_basis`).

    `currency` picks between amounts stated more than once: EN 16931 lets the tax total appear a
    second time in the accounting currency, and the two are different numbers. An amount that
    names no `currencyID` is in the document currency by definition, so it beats a foreign-tagged
    one. `parents` may be several elements, because UBL states each currency's tax total in its
    own `TaxTotal`.
    """
    if parents is None:
        return ""
    if not isinstance(parents, list):
        parents = [parents]
    for name in names:
        found = []
        for parent in parents:
            found += [el for el in (parent.iter() if deep else parent)
                      if _local(el) == name and _text(el)]
        if not found:
            continue
        if currency:
            for el in found:
                if el.get("currencyID") == currency:
                    return _text(el)
            for el in found:
                if not el.get("currencyID"):
                    return _text(el)
            # Every candidate names a DIFFERENT currency: this document states no figure in its
            # own, so there is none to return. Falling back on document order handed out a foreign
            # amount, and foreign amounts reconcile with each other -- a wrong number the guard
            # cannot see. Measured in
            # `test_einvoice_refuses_rather_than_return_an_amount_in_a_foreign_currency`.
            return ""
        return _text(found[0])
    return ""


def _amount(text):
    """The XML amount as an exact decimal rounded to the cent, or None if absent/not a number.

    Decimal and not float, because these figures are booked. EN 16931 writes an amount with a dot
    and no thousands separator; anything else is a document this reader does not understand, and
    a number it does not understand is None (which the guard below turns into a refusal) rather
    than a guess.
    """
    try:
        value = Decimal((text or "").strip())
        # "NaN" and "Infinity" are valid Decimal literals, and a quiet NaN survives quantize
        # unharmed -- it was the COMPARISON in the guard that raised, so an amount spelled NaN
        # ended the run with a traceback and exit 1 ("no structured data") instead of the refusal
        # this reader owes. A figure that is not finite is not a figure
        # (`test_einvoice_refuses_an_amount_that_is_not_a_finite_number`).
        return value.quantize(CENT, rounding=ROUND_HALF_UP) if value.is_finite() else None
    except (InvalidOperation, ValueError, ArithmeticError):
        return None


def reconciliation_failure(out):
    """The refusal a money triple that does not add up earns, or None if it reconciles.

    The identity is the document's OWN (EN 16931 BR-CO-15: BT-112 grand total = BT-109 tax basis
    total + BT-110 tax total). It therefore holds for one VAT rate and for several alike: a
    multi-rate invoice has no single rate to multiply with, and this check needs none — which is
    why it is stated as a sum and not as net x (1 + rate).

    A ROUNDING AMOUNT IS NOT PART OF IT. BT-114 belongs to the amount DUE, not to the grand total
    (BR-CO-16: BT-115 = BT-112 - BT-113 + BT-114), so it enters here in exactly one case: the
    document stated no grand total and the amount due stood in for it. Adding it to a grand total
    refused a norm-valid invoice and blessed a norm-invalid one, both measured
    (`test_einvoice_a_rounding_amount_is_not_part_of_the_grand_total`).

    What it does NOT see: whether these are the right document's figures. Three amounts read from
    the wrong invoice reconcile perfectly. That second reader is a different job (FR-0065).
    """
    net, tax, gross = (_amount(out.get(key)) for key in ("net", "tax", "gross"))
    figures = "net %s, tax %s, gross %s" % tuple(
        out.get(key) or "MISSING" for key in ("net", "tax", "gross"))
    if net is None or tax is None or gross is None:
        return ("the money triple is incomplete or unreadable — %s. Nothing here invents the "
                "missing figure (a zero-tax invoice states its 0.00): read the document and book "
                "by hand." % figures)
    rounding = _amount(out.get("rounding")) or Decimal("0")
    stated = "%s%s" % (figures, "" if not rounding else ", rounding %s" % out.get("rounding"))
    difference = net + tax + rounding - gross
    if abs(difference) > CENT:
        return ("the money triple does not add up — %s: net + tax%s = %s, which is %s away from "
                "the stated gross (tolerance one cent). One of the three is not the figure the "
                "document states: read it and book by hand."
                % (stated, "" if not rounding else " + rounding", net + tax + rounding,
                   abs(difference)))
    return None


BREAKDOWN_RULE = ("BR-CO-14", "BT-110 = the sum of BT-117 over the VAT breakdown")


def breakdown_failure(out):
    """The refusal a tax total its own VAT breakdown contradicts earns, or None.

    EN 16931 BR-CO-14. The document states the tax total TWICE -- once as BT-110 in the header
    summation, once as the sum of BT-117 over the breakdown (BG-23) -- and until 2026-09-12 only
    the first one was ever read. A head that is internally consistent (BR-CO-15 holds) while its
    own breakdown says another number went through at rc 0, so the ledger would have carried a tax
    amount the document itself denies (`H75`, BUG-0167).

    WHAT MAKES IT SILENT is stated as a property, not as an exception list: this reader judges what
    the document STATES. No breakdown at all, or one whose amounts it cannot read as figures, is
    not a contradiction -- it is an absent second statement, and inventing one is the failure mode
    this module exists to avoid. The three directions are measured in
    `tools/test_hooks.py::test_einvoice_a_tax_total_its_own_breakdown_contradicts_is_refused`.

    THE TOLERANCE IS ONE CENT PER STATED CATEGORY and not one cent overall: every BT-117 is itself
    a rounded figure, so a document with several categories may legitimately be a cent per category
    away from its own total. A tighter bound would refuse norm-valid invoices, which is the
    direction that costs a bookkeeper an evening.
    """
    stated = _amount(out.get("tax"))
    amounts = [_amount(one) for one in (out.get("tax_breakdown") or [])]
    if stated is None or not amounts or any(one is None for one in amounts):
        return None
    total = sum(amounts, Decimal("0"))
    if abs(total - stated) <= CENT * len(amounts):
        return None
    return ("%s (%s): the tax total and its own VAT breakdown state different numbers — the "
            "header says %s and the %d breakdown entries add up to %s. One of the two is not this "
            "document's tax: read it and book by hand."
            % (BREAKDOWN_RULE[0], BREAKDOWN_RULE[1], out.get("tax"), len(amounts), total))


def parse_xml(data):
    if ET is None:
        sys.stderr.write("[einvoice] defusedxml not installed (pip install -r "
                         "requirements-office.txt) — refusing to parse untrusted supplier XML "
                         "with an XXE-vulnerable parser\n")
        return None
    try:
        root = ET.fromstring(data)
    except (ParseError, ValueError) as e:
        sys.stderr.write("[einvoice] XML parse error: %s\n" % e)
        return None
    tag = _local(root)
    out = {"syntax": tag}
    if tag == CII_ROOT:                          # CII (ZUGFeRD/XRechnung-CII)
        document = _anchor(root, "ExchangedDocument")
        # ExchangedDocument's own ID. The first ID in the document is the guideline URN in
        # `GuidelineSpecifiedDocumentContextParameter` — a confidently WRONG invoice number that
        # would poison the ledger's duplicate detection.
        out["invoice_no"] = _pick(document, "ID")
        out["issue_date"] = _text(_child(_child(document, "IssueDateTime"), "DateTimeString"))
        out["seller"] = _pick(_anchor(root, "SellerTradeParty"), "Name")
        settlement = _anchor(root, "ApplicableHeaderTradeSettlement")
        out["currency"] = _pick(settlement, "InvoiceCurrencyCode")
        totals = _child(settlement, "SpecifiedTradeSettlementHeaderMonetarySummation")
        out["net"] = _pick(totals, "TaxBasisTotalAmount", "LineTotalAmount",
                           currency=out["currency"])
        out["tax"] = _pick(totals, "TaxTotalAmount", currency=out["currency"])
        out["gross"] = _pick(totals, "GrandTotalAmount", currency=out["currency"])
        out["rounding"] = ""
        if not out["gross"]:
            # BT-112 carries no rounding. Only where the document states none does the amount DUE
            # stand in for it, and then BT-113/BT-114 come with it -- the split
            # `reconciliation_failure` explains, made the same way in the UBL branch below.
            out["gross"] = _pick(totals, "DuePayableAmount", currency=out["currency"])
            out["rounding"] = _pick(totals, "RoundingAmount", currency=out["currency"])
        # THE DOCKING POINT'S FIELDS (DEC-0075, `scripts/invoice_intake.py`), read here so the
        # app-produced invoice goes through the ONE reader BUG-0072 hardened; `main` prints none
        # of them, so the bookkeeper's output stays what it was.
        out["guideline"] = _pick(_anchor(root, "GuidelineSpecifiedDocumentContextParameter"), "ID")
        out["type_code"] = _pick(document, "TypeCode")
        seller = _anchor(root, "SellerTradeParty")
        buyer = _anchor(root, "BuyerTradeParty")
        out["buyer"] = _pick(buyer, "Name")
        out["seller_country"] = _pick(_child(seller, "PostalTradeAddress"), "CountryID")
        out["buyer_country"] = _pick(_child(buyer, "PostalTradeAddress"), "CountryID")
        out["line_count"] = _count(root, "IncludedSupplyChainTradeLineItem")
        out["preceding_invoice"] = _pick(_child(settlement, "InvoiceReferencedDocument"),
                                         "IssuerAssignedID")
        out["tax_categories"] = [
            (_pick(tax, "CategoryCode"), _pick(tax, "RateApplicablePercent"))
            for tax in (settlement if settlement is not None else ())
            if _local(tax) == "ApplicableTradeTax"]
        # BT-117 per category, for BR-CO-14. Read with the same currency filter as every other
        # amount: a breakdown restated in the accounting currency is a different number.
        out["tax_breakdown"] = [
            _pick(tax, "CalculatedAmount", currency=out["currency"])
            for tax in (settlement if settlement is not None else ())
            if _local(tax) == "ApplicableTradeTax"]
    elif tag in UBL_ROOTS:                        # UBL (XRechnung-UBL)
        out["invoice_no"] = _pick(root, "ID")     # the invoice's own ID, not a party's
        out["issue_date"] = _pick(root, "IssueDate")
        out["seller"] = _pick(_anchor(root, "AccountingSupplierParty"),
                              "RegistrationName", "Name", deep=True)
        out["currency"] = _pick(root, "DocumentCurrencyCode")
        totals = _anchor(root, "LegalMonetaryTotal")
        out["net"] = _pick(totals, "TaxExclusiveAmount", "LineExtensionAmount",
                           currency=out["currency"])
        out["tax"] = _pick([el for el in root if _local(el) == "TaxTotal"], "TaxAmount",
                           currency=out["currency"])
        out["gross"] = _pick(totals, "TaxInclusiveAmount", currency=out["currency"])
        out["rounding"] = ""
        if not out["gross"]:
            # The same split as the CII branch above. Falling back on BT-115 holds the identity
            # only while prepaid is zero — where it is not, the guard refuses instead of
            # reconstructing a figure the document never states.
            out["gross"] = _pick(totals, "PayableAmount", currency=out["currency"])
            out["rounding"] = _pick(totals, "PayableRoundingAmount", currency=out["currency"])
        # the docking point's fields, UBL spelling -- see the CII branch
        out["guideline"] = _pick(root, "CustomizationID")
        out["type_code"] = _pick(root, "InvoiceTypeCode", "CreditNoteTypeCode")
        supplier = _anchor(root, "AccountingSupplierParty")
        customer = _anchor(root, "AccountingCustomerParty")
        out["buyer"] = _pick(customer, "RegistrationName", "Name", deep=True)
        out["seller_country"] = _pick(_anchor(supplier, "PostalAddress"),
                                      "IdentificationCode", deep=True)
        out["buyer_country"] = _pick(_anchor(customer, "PostalAddress"),
                                     "IdentificationCode", deep=True)
        out["line_count"] = _count(root, "InvoiceLine") + _count(root, "CreditNoteLine")
        out["preceding_invoice"] = _pick(_anchor(root, "InvoiceDocumentReference"), "ID")
        out["tax_categories"] = [
            (_pick(_child(subtotal, "TaxCategory"), "ID"),
             _pick(_child(subtotal, "TaxCategory"), "Percent"))
            for total in root if _local(total) == "TaxTotal"
            for subtotal in total if _local(subtotal) == "TaxSubtotal"]
        # BT-117 per category, UBL spelling -- see the CII branch.
        out["tax_breakdown"] = [
            _pick(subtotal, "TaxAmount", currency=out["currency"])
            for total in root if _local(total) == "TaxTotal"
            for subtotal in total if _local(subtotal) == "TaxSubtotal"]
    else:
        sys.stderr.write("[einvoice] unknown root element <%s> — not a known e-invoice syntax\n" % tag)
        return None
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", out.get("issue_date") or "")
    if m:
        out["issue_date"] = "%s-%s-%s" % m.groups()   # CII format 102 -> ISO
    return out


def _is_an_einvoice(data):
    """The root element name when `data` IS one of the two syntaxes this reader knows, else None.

    The PROPERTY, not a list of file names: an attachment is the invoice when it IS one. The
    alternative was a table of the names the norms prescribe (`factur-x.xml`, `zugferd-invoice.xml`,
    `xrechnung.xml`, `order-x.xml`), and a table would have to grow with every profile while saying
    nothing about a file that carries a prescribed name and something else inside.

    THE PROPERTY IS `EINVOICE_ROOTS`, which is the same statement `parse_xml` branches on twenty
    lines down -- not a second one. The first cut asked only whether the bytes PARSE as XML, and
    that is a different question: measured 2026-09-06, a PDF/A-3 carrying `factur-x.xml` plus an
    ordinary `<note>hello</note>` attachment (which PDF/A-3 allows) was refused as "carries 2
    embedded e-invoice XML files", while the contract page promises the app project that the kit
    "takes the one that IS an e-invoice"
    (`tools/test_office_package.py::test_a_pdf_carrying_two_invoice_attachments_is_refused_not_guessed`).
    """
    try:
        tag = _local(ET.fromstring(data))
    except Exception:                       # noqa: BLE001 -- anything unparseable is not one
        return None
    return tag if tag in EINVOICE_ROOTS else None


def extract_pdf_xml(path):
    """The embedded e-invoice XML of a PDF, or None -- and never a guess between two of them.

    WHICH ATTACHMENT, decided by what it is. Until 2026-09-06 this returned the first `.xml`
    attachment pypdf handed back, and pypdf hands them back in NAME-TREE order, not attachment
    order: measured that day with `factur-x.xml` (the real figures) attached first and
    `aaa-invoice.xml` (999.00) attached second, the second one won and the run was accepted with
    its figures. That is BUG-0072's class -- a wrong figure passing silently -- reached through a
    file name. Now every attachment is parsed, exactly one that IS an e-invoice is taken, and two
    are refused with both names, because which of them the PDF is about is not this reader's guess
    (`tools/test_office_package.py::test_a_pdf_carrying_two_invoice_attachments_is_refused_not_guessed`).
    """
    try:
        from pypdf import PdfReader  # type: ignore[import-untyped]
    except ImportError:
        sys.stderr.write("[einvoice] pypdf not installed (pip install pypdf) — cannot check the "
                         "PDF for embedded e-invoice XML\n")
        return None
    if ET is None:
        # The SELECTION parses, so it needs the same parser `parse_xml` refuses to work
        # without -- and a missing dependency must not read as "this PDF carries no
        # e-invoice", which is what returning None on its own would say.
        sys.stderr.write("[einvoice] defusedxml not installed (pip install -r "
                         "requirements-office.txt) — refusing to parse untrusted "
                         "supplier XML with an XXE-vulnerable parser\n")
        return None
    found = []
    try:
        reader = PdfReader(path)
        for name, f in (reader.attachments or {}).items():
            data = bytes(f[0] if isinstance(f, list) else f)
            if _is_an_einvoice(data):
                found.append((name, data))
    except Exception as e:
        sys.stderr.write("[einvoice] PDF attachment read failed: %s\n" % e)
        return None
    if len(found) > 1:
        sys.stderr.write("[einvoice] this PDF carries %d embedded e-invoice XML files (%s); which "
                         "one the document is about is not this reader's guess — refused\n"
                         % (len(found), ", ".join(name for name, _ in found)))
        return None
    return found[0][1] if found else None


def main():
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: einvoice_extract.py <file.xml|file.pdf>\n")
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.isfile(path):
        sys.stderr.write("[einvoice] not found: %s\n" % path)
        sys.exit(1)
    if path.lower().endswith(".xml"):
        data = open(path, "rb").read()
    elif path.lower().endswith(".pdf"):
        data = extract_pdf_xml(path)
        if data is None:
            sys.stderr.write("[einvoice] no embedded XML — plain PDF: read carefully; UNCLEAR "
                             "fields stay UNCLEAR (ledger_add's arithmetic check is the net)\n")
            sys.exit(1)
    else:
        sys.stderr.write("[einvoice] unsupported extension (xml/pdf)\n")
        sys.exit(1)

    out = parse_xml(data)
    if not out:
        sys.exit(1)
    failure = reconciliation_failure(out) or breakdown_failure(out)
    for key in ("syntax", "seller", "invoice_no", "issue_date", "currency", "net", "tax", "gross"):
        value = out.get(key) or "MISSING"
        if failure and key in ("net", "tax", "gross"):
            # the mark travels WITH the figure: one line of this output gets copied on its own.
            value = "%s %s" % (value, UNRECONCILED)
        print("%s: %s" % (key, value))
    if failure:
        sys.stderr.write("[einvoice] REFUSED: %s\n" % failure)
        sys.exit(2)


if __name__ == "__main__":
    main()
