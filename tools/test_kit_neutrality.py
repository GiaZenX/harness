"""A kit is bound to RULES, never to a tool or a product group (FR-0028).

The user's steer, verbatim in the item: the office team must not be tied to Shopify, because other
people use WooCommerce or something else, and it must not be trimmed to one kind of product. What a
project actually uses belongs in ITS `project_memory/` — master data, the product catalogue, taught
PROC items — never in a shipped kit text.

TWO PROPERTIES, because the binding can happen in two different places:
  * a ROLE TEXT that names a platform in its own prose tells the role which platform this is;
  * a shipped DATA TEMPLATE that arrives with entries in it hands every business somebody else's
    assortment.
Each has its own test below, and each has a reader whose two directions are measured separately.
"""
import ast
import glob
import io
import os
import re

import pytest

import conftest

TEAM_KITS = conftest.TEAM_KITS
KITS = ("dev-team", "office-team", "research-team")

# THE NAMES, and this is the one enumeration here. It cannot be a derivation — "is this word a
# commercial platform" is world knowledge — so it carries the tripwire every enumeration in this
# repo owes: `test_the_binding_reader_can_tell_a_binding_from_an_illustration` measures that the
# reader fires on a planted binding and stays quiet on the shapes a kit text legitimately uses, so
# a pattern that stopped matching anything cannot pass by matching nothing.
_PLATFORMS = re.compile(
    r"\b(Shopify|WooCommerce|Magento|Shopware|PrestaShop|BigCommerce|Squarespace|Wix|Etsy|eBay|"
    r"Amazon|Kaufland|Otto|Zalando|Alibaba|AliExpress|Temu|Lexoffice|DATEV|sevDesk)\b", re.I)

# A DELIMITED LITERAL: an inline code span or a double-quoted span. The same convention
# `test_repo_hygiene._dec_citations` argues at length — in this tree a name that is DATA is written
# inside a delimiter, and a name in bare prose is the text speaking. No single-quote alternative,
# for the reason given there: in English prose an apostrophe would open a span that swallows the
# rest of the sentence.
_DELIMITED = re.compile(r"`[^`\n]*`|\"[^\"\n]*\"")

# WHAT IS STILL BOUND TODAY, with the reason and the owner. This is a RATCHET, not an exemption
# list: `test_no_role_text_binds_a_kit_to_a_named_platform` fails both ways — a NEW binding is
# reported, and an entry here that has stopped binding must be deleted, so the list can only shrink.
# Every entry names who closes it, because `agents/` and `skills/` are one stream's files and this
# measurement is another's. EMPTY since TSK-0114, and it got there the way the ratchet promises:
# the one entry was closed at its source and the second assertion below then demanded its deletion.
KNOWN_BINDINGS = {}


def _role_texts():
    """(relative path, the text a ROLE or the ROUTER really reads) for every shipped role text.

    An agent definition is judged through its PARSED frontmatter rather than as raw file text: the
    `description` is one YAML scalar, so its outer quotes are syntax and not a literal marker, and a
    reader that took them for one would exempt exactly the field the platform routes work on.
    """
    yaml = pytest.importorskip("yaml")
    for kit in KITS:
        directory = os.path.join(TEAM_KITS, kit)
        for pattern in (("constitution", "*.md"), ("skills", "*", "*.md")):
            for path in sorted(glob.glob(os.path.join(directory, *pattern))):
                with open(path, encoding="utf-8") as handle:
                    yield os.path.relpath(path, conftest.ROOT).replace(os.sep, "/"), handle.read()
        for path in sorted(glob.glob(os.path.join(directory, "agents", "*.md"))):
            with open(path, encoding="utf-8") as handle:
                raw = handle.read()
            front, body = ({}, raw)
            if raw.startswith("---") and raw.count("---") >= 2:
                front = yaml.safe_load(raw.split("---", 2)[1]) or {}
                body = raw.split("---", 2)[2]
            spoken = "\n".join([str(front.get("name") or ""), str(front.get("description") or ""),
                                body])
            yield os.path.relpath(path, conftest.ROOT).replace(os.sep, "/"), spoken


def bindings_in(text):
    """Every platform name in `text` that the TEXT ITSELF asserts, as strings.

    A name inside a delimited literal is DATA the sentence is about — an example value, a
    counterparty as it appears on a statement, a command somebody types. A name in bare prose is the
    kit saying which platform this is, and that is the binding FR-0028 forbids.
    """
    exempt = [(span.start(), span.end()) for span in _DELIMITED.finditer(text)]
    return [hit.group(0) for hit in _PLATFORMS.finditer(text)
            if not any(start <= hit.start() < end for start, end in exempt)]


def test_the_binding_reader_can_tell_a_binding_from_an_illustration():
    """The floor under the test below: "return everything" and "return nothing" must both fail here.

    Without it the measurement rests on nothing — a pattern that had stopped matching would look
    exactly like a clean tree, and one that matched inside every literal would report the places a
    kit text legitimately EXHIBITS a name.
    """
    assert bindings_in("export the orders from Shopify") == ["Shopify"]
    assert bindings_in("Keywords: shop, SEO, Shopify.") == ["Shopify"]
    assert bindings_in('normalise "Amazon EU S.a r.l." to its canonical name') == []
    assert bindings_in("the channel key `amazon` in the profile") == []
    assert bindings_in("whatever shop system the business runs") == []


def test_no_role_text_binds_a_kit_to_a_named_platform():
    """No shipped role text may tell a role which commerce platform this business uses (FR-0028).

    MEASURED ON THE SHIPPED TREE the day this test was written: one site, one span —
    `office-team/agents/shop-curator.md`, whose routing description ended "…, audit, Shopify.". A
    description is what the platform matches a request against, so that one word made the shop role
    the SHOPIFY role for the router, in a kit whose own item says it must not be one. It was
    recorded in `KNOWN_BINDINGS` rather than edited on the spot, because role texts belong to
    another stream; the seam was written in TSK-0114 and the entry deleted in the same change,
    which is the shrinking this list is for.
    """
    offenders, judged = {}, 0
    for relative, text in _role_texts():
        judged += 1
        found = bindings_in(text)
        if found:
            offenders[relative] = found
    assert judged >= 30, ("only %d role texts read — the walk stopped finding them and every "
                          "assertion below is vacuous" % judged)
    new = {path: names for path, names in offenders.items() if path not in KNOWN_BINDINGS}
    assert not new, (
        "these shipped role texts name a commerce platform in their own prose, which binds the kit "
        "to it (FR-0028). Write the name into the project's own records instead, or record it here "
        "with its owner:\n  " + "\n  ".join("%s: %s" % (path, names)
                                            for path, names in sorted(new.items())))
    closed = sorted(set(KNOWN_BINDINGS) - set(offenders))
    assert not closed, (
        "these are recorded as still bound and are not any more — delete the entry so the list "
        "keeps shrinking: %s" % ", ".join(closed))


# A LIST A KIT TEMPLATE MAY SHIP FILLED, with the reason. Same ratchet in both directions as above:
# a name here whose list has become empty is an exception nobody needs.
FILLED_TEMPLATE_LISTS = {
    "project_config.yaml:providers":
        "the apparatus' own provider names, not anything about the business",
    "master_data.yaml:categories":
        "the expense and income classes of the Anlage EUeR, keyed to its line numbers "
        "(FR-0076) -- a tax form is not a business, and the list that WOULD carry one "
        "(`counterparties`) still ships empty. Held by the row check below, so the "
        "exception cannot quietly grow into an assortment",
    "chart_of_accounts.yaml:accounts":
        "the two standard German chart-of-accounts numberings (FR-0081), each row an account "
        "number of a PUBLISHED chart and a line of the same form the categories above are keyed "
        "to -- a numbering standard is not a business either, and the document ships "
        "`active: null`, so nothing of it reaches a booking until the business names its "
        "framework. Held by the same row check below",
}

# WHAT MAKES A SHIPPED CATEGORY NOT CONTENT: it belongs to a LINE of the form, so it is a
# statement about the Anlage EUeR and not about anybody's trade. A row without one would be a
# category somebody invented, which is exactly what FR-0028 keeps out of a template. The
# provenance of the numbers themselves is `H131` in docs/POST_V2_WISHLIST.md.
CATEGORY_LINE_FIELD = "euer_line"
# ...and what makes a shipped ACCOUNT not content: it carries the number the published
# chart gives it. The same question as the line above, asked of the other document.
ACCOUNT_FIELD = "account"


def _lists_in(node, path):
    if isinstance(node, dict):
        for key, value in node.items():
            for found in _lists_in(value, "%s:%s" % (path, key) if ":" not in path else path):
                yield found
    elif isinstance(node, list):
        if node:
            yield path, node
        for value in node:
            for found in _lists_in(value, path):
                yield found


def test_every_office_state_template_ships_its_lists_empty():
    """The kit ships STRUCTURE, never CONTENT (FR-0028).

    A template that arrived with product categories, channels or counterparties in it would hand
    every business the assortment of the one it was written from — which is exactly what the item
    forbids, and what the field survey found the kit's own source project to be full of. Asked as a
    PROPERTY over every shipped state template rather than as a list of the keys somebody thought
    of: a key added tomorrow is covered on the day it ships.
    """
    yaml = pytest.importorskip("yaml")
    base = os.path.join(TEAM_KITS, "office-team", "templates", "project_memory")
    filled, judged = {}, 0
    for path in sorted(glob.glob(os.path.join(base, "*.yaml"))):
        judged += 1
        with open(path, encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
        for where, value in _lists_in(document, os.path.basename(path)):
            filled[where] = value
    assert judged >= 5, "only %d state templates read — the walk found nothing to judge" % judged
    new = {where: value for where, value in filled.items() if where not in FILLED_TEMPLATE_LISTS}
    assert not new, (
        "these shipped office templates arrive with entries in them, so a fresh project inherits "
        "somebody else's business (FR-0028): %s" % new)
    closed = sorted(set(FILLED_TEMPLATE_LISTS) - set(filled))
    assert not closed, (
        "recorded as shipping filled and now empty — drop the exception: %s" % ", ".join(closed))
    # THE EXCEPTION IS NOT A FREE PASS. `master_data.yaml:categories` is excused because every
    # row names a line of the form; a row that names none is an assortment and is refused here,
    # so the excused list cannot grow into the thing the rule forbids. Read off the DOCUMENT and
    # not off the walk above: that walk keys every list under a document by its outermost key, so
    # `categories.income` and `categories.expense` collapse into one entry and a check on it
    # would judge whichever of the two came last.
    with open(os.path.join(base, "master_data.yaml"), encoding="utf-8") as handle:
        categories = (yaml.safe_load(handle) or {}).get("categories") or {}
    rows = [row for side in categories.values() for row in side]
    assert len(rows) >= 10, "the shipped vocabulary shrank to %d rows -- judged nothing" % len(rows)
    invented = [row for row in rows
                if not isinstance(row, dict) or not row.get(CATEGORY_LINE_FIELD)]
    assert not invented, (
        "these shipped categories name no line of the form, so they are somebody's assortment "
        "rather than the form's own vocabulary (FR-0028): %s" % invented)
    # THE SECOND EXCEPTION, held the same way and for the same reason. An account row is excused
    # because it names an account NUMBER of a published chart and a LINE of the form; a row that
    # names either of them not is a chart somebody invented, and that is the assortment this rule
    # keeps out. Read off the document, for the reason one paragraph up: the walk keys
    # `accounts.SKR03` and `accounts.SKR04` alike and a check on the walk would judge one of them.
    with open(os.path.join(base, "chart_of_accounts.yaml"), encoding="utf-8") as handle:
        frameworks = (yaml.safe_load(handle) or {}).get("accounts") or {}
    entries = [row for one in frameworks.values() for row in one]
    assert len(entries) >= 20, "the shipped chart shrank to %d rows -- judged nothing" % len(entries)
    unanchored = [row for row in entries
                  if not isinstance(row, dict) or not str(row.get(ACCOUNT_FIELD) or "").isdigit()
                  or not row.get(CATEGORY_LINE_FIELD)]
    assert not unanchored, (
        "these shipped accounts name no account number of a published chart or no line of the "
        "form, so they are somebody's own bookkeeping rather than the standard's (FR-0028): %s"
        % unanchored)


# ============================ the same question asked of the TEMPLATES, read raw =================

def _template_files():
    """(relative path, text) for every file the office kit ships as a TEMPLATE.

    Everything under `templates/`, not just the state YAMLs: a project script, a `.gitignore` and a
    dashboard shell are copied into the business's repo exactly like a state document is.
    """
    base = os.path.join(TEAM_KITS, "office-team", "templates")
    for directory, subdirs, names in os.walk(base):
        subdirs[:] = [name for name in subdirs if name != "__pycache__"]
        for name in sorted(names):
            path = os.path.join(directory, name)
            try:
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
            except (OSError, UnicodeDecodeError):
                continue          # a shipped binary is not text and asserts nothing
            yield os.path.relpath(path, conftest.ROOT).replace(os.sep, "/"), text


def names_in_a_template(text):
    """Every platform name in `text`, WITH NO SPAN EXEMPT — comments and quoted values included.

    The exemption `bindings_in` grants a delimited span is an argument about PROSE: there, a name
    inside quotes is the sentence's subject rather than the sentence's claim. A template is not
    prose. It is COPIED into a business's own repository, where a quoted example value is the value
    the field arrives with and a `#` comment is the instruction beside it — measured: the one site
    this reading was written for was `business_profile.yaml`'s `detail: "<platform> order export
    CSV, monthly"`, which the prose reader passed twice over, once for the quotes and once for the
    comment marker.
    """
    return [hit.group(0) for hit in _PLATFORMS.finditer(text)]


def pilot_business():
    """The name of the business this kit was surveyed from, READ OUT of the survey.

    Derived and not typed, because the one thing a shipped kit text may never carry is the pilot's
    own identity, and a name typed here would keep passing after the survey moved on. The survey
    names the copy it measured in its own header (`v2-pilot/<name>-KOPIE`); finding nothing there is
    a failure of this reader, not a clean tree, and it says so.
    """
    path = os.path.join(conftest.ROOT, "docs", "office-kit-from-field.md")
    with open(path, encoding="utf-8") as handle:
        found = re.search(r"v2-pilot/([A-Za-z0-9][A-Za-z0-9_-]*)-KOPIE", handle.read())
    assert found, (
        "%s no longer names the pilot copy it was measured against, so this test cannot tell which "
        "business must not appear in a shipped text" % path)
    return found.group(1)


def test_the_raw_template_reader_reads_what_the_prose_reader_is_allowed_to_skip():
    """The floor under the sweep below: it must fire exactly where `bindings_in` deliberately does
    not, and it must still stay quiet on a template that names no platform at all."""
    quoted = 'detail: "Shopify order export CSV, monthly"'
    assert bindings_in(quoted) == [], "the prose reader's exemption is the thing being replaced"
    assert names_in_a_template(quoted) == ["Shopify"]
    assert names_in_a_template("#  channels: [own-shop, ebay, local]") == ["ebay"]
    assert names_in_a_template("detail: \"monthly order export CSV from the shop system\"") == []


def test_no_shipped_office_template_names_a_platform_or_the_pilot_business():
    """A template is COPIED into the business's own repository, so what it names, that business
    inherits (FR-0028).

    TWO CLASSES, and each is only as good as its own derivation says: a commerce platform by name
    (the enumeration `_PLATFORMS`, whose two ends
    `test_the_binding_reader_can_tell_a_binding_from_an_illustration` measures), and the PILOT
    BUSINESS this kit was surveyed from, read out of the survey rather than typed here.

    MEASURED on the tree the day this was written: three sites, all in state templates — an example
    `channels` list naming two marketplaces, a revenue-source `detail` naming a shop platform, and a
    counterparty-normalisation example built from a real marketplace subsidiary. No exception map:
    the answer over the shipped templates is zero, and an entry here would be the first.
    """
    pilot = pilot_business()
    offenders, judged = {}, 0
    for relative, text in _template_files():
        judged += 1
        found = names_in_a_template(text)
        if re.search(re.escape(pilot), text, re.I):
            found = found + [pilot]
        if found:
            offenders[relative] = sorted(set(found))
    assert judged >= 20, ("only %d shipped templates read — the walk stopped finding them and the "
                          "assertion below is vacuous" % judged)
    assert not offenders, (
        "these shipped office templates name a commerce platform or the pilot business this kit was "
        "surveyed from, so every project created from them inherits it (FR-0028). Put the name into "
        "the project's own records instead:\n  "
        + "\n  ".join("%s: %s" % (path, names) for path, names in sorted(offenders.items())))


def test_no_shipped_office_role_text_names_the_pilot_business():
    """The other half of the same question, over the corpus `test_no_role_text_binds_a_kit_to_a_named_platform`
    already walks: a constitution, a skill or a role definition that named the business this kit was
    written from would hand every project that business's habits as the kit's own.

    Read raw here rather than through `bindings_in`: the pilot's name is not a word a role text
    could legitimately be ABOUT, so the delimited-span argument does not apply to it.
    """
    pilot = pilot_business()
    offenders, judged = [], 0
    for relative, text in _role_texts():
        judged += 1
        if re.search(re.escape(pilot), text, re.I):
            offenders.append(relative)
    assert judged >= 30, "only %d role texts read" % judged
    assert not offenders, (
        "these shipped role texts name the pilot business %r this kit was surveyed from: %s"
        % (pilot, offenders))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))


# THE LETTER WRITER ITSELF, as the source of what a term IS. `letter_draft.a_term` is the one
# reader of `correspondence.yaml`, and it refuses with the route when a term is missing -- so the
# set of terms is exactly the set of `a_term(...)` calls in that script, and this test derives it
# from the script's own source instead of listing keys.
LETTER_WRITER = os.path.join(TEAM_KITS, "office-team", "templates", "repo", "scripts",
                             "letter_draft.py")
CORRESPONDENCE = os.path.join(TEAM_KITS, "office-team", "templates", "project_memory",
                              "correspondence.yaml")


def _terms_the_letter_writer_reads():
    """[(parent key or None, key)] for every `a_term(...)` the shipped letter writer calls."""
    with io.open(LETTER_WRITER, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "a_term" and len(node.args) >= 2):
            continue
        key = node.args[1]
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            continue
        parents = [inner.value for inner in ast.walk(node.args[0])
                   if isinstance(inner, ast.Constant) and isinstance(inner.value, str)]
        found.append((parents[0] if parents else "", key.value))
    return sorted(set(found))


def test_every_term_the_letter_writer_reads_ships_empty():
    """BUG-0259: a value a CUSTOMER reads is one the user chose, whatever shape it ships in.

    The neutrality rule beside this one walks LISTS, so a scalar was never judged, and
    `correspondence.yaml` shipped three terms the kit decided for the business:
    `offer.valid_days: 14` became "Dieses Angebot gilt bis zum <date>", `address: "Sie"` decided the
    form of address of every letter, and `closing` was its last line. The dunning ladder of the SAME
    file was refused as content on the argument that after how many days a business writes is its
    own decision -- and how long an offer stands is the same decision, only spelled as a scalar.

    DERIVED FROM THE WRITER, not listed here: a term is whatever `letter_draft.a_term` reads, and
    that function already refuses a missing one with the route that fills it
    (`request-approval` + `apply-proposal`). So a term added to the script tomorrow is under this
    rule the day it ships, and a term dropped from the script stops being claimed.

    BOTH ENDS: every term the writer reads has to be empty in the shipped template (a filled one is
    the defect), and the writer has to read at least the terms the template names -- a walk that
    found nothing would make this vacuous, so the count is asserted.
    """
    yaml = pytest.importorskip("yaml")
    terms = _terms_the_letter_writer_reads()
    assert len(terms) >= 3, "only %d terms read out of the letter writer -- the walk is broken" % len(terms)
    with io.open(CORRESPONDENCE, encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}
    filled = {}
    for parent, key in terms:
        node = document if not parent else (document.get(parent) or {})
        value = node.get(key) if isinstance(node, dict) else None
        if value is not None and str(value).strip():
            filled["%s.%s" % (parent, key) if parent else key] = value
    assert not filled, (
        "these terms ship with a value the KIT chose, and `scripts/letter_draft.py` writes each of "
        "them verbatim into a letter a customer reads (BUG-0259): %s" % filled)
