#!/usr/bin/env python3
"""
kit_design_render.py — KIT-OWNED design render + conformance (draft phase). DO NOT EDIT IN THE PROJECT.

Renders every staged design draft of ONE task to PNG at the configured viewports, optionally
beside the reference sites the design ambition names, writes the RECORD `gate_design_sighted`
reads, and CHECKS the rendered draft against the mechanical half of this kit's design standards.
Its subject is the DRAFT — the self-contained HTML the designer stages before anyone has seen it —
where `kit_browser_checks.py` renders the BUILT app after implementation.

THREE EXIT CODES, because "did not render" and "rendered and found something" are different
answers and one code for both makes the caller guess: 0 nothing to report, 2 could not render (no
record written), 3 rendered and recorded but the checks below found something. Only 2 means the
draft was never looked at.

WHAT THE CHECKS ARE, AND WHAT THEY ARE NOT. They read the RENDERED page — CSSOM, computed styles,
the live focus order — never the template text, because a design draft is judged as the browser
resolves it. They are NOT an axe-core run and this file never says a draft is accessible: axe-core
is an npm package and this kit ships no npm manifest to put it in, so what is built is the share
that needs no dependency (contrast, the keyboard path, the reduced-motion fallback, focus
visibility, colour literals, one primary goal per declared view). The report says "the
automatically checkable share" and nothing wider. Where a value cannot be decided at all — text
over a background image, a semi-transparent layer — it is listed as UNDECIDED and is not a finding
either way.

THE FINDINGS ARE NOW REFUSED, and this paragraph used to say the opposite (`BUG-0294` / `H210`).
`gate_design_sighted` asked one question -- was this draft rendered -- and the record answered it,
so a draft with findings kept its provenance and passed the gate: measured, a draft with a
contrast of 1.92:1 was renderer rc 3 and hook rc 0, and a role that ignored the exit code
presented it. The hook reads the `conformance.findings` of the entry for THIS draft now and
refuses on them. What it still does not read is `undecided`: that is this script's own word for a
question it could not decide (text over a background image, a gradient, a translucent layer), and
turning "I could not tell" into a refusal is what the printed NOT DECIDABLE line exists to
prevent.

WHY IT EXISTS: in a real project (Canyon, 2026-08-30) a design revision reached the user twice
without anyone ever rendering it; both rounds were rejected on things only pixels show ("teilweise
linksbuendig statt mittig"). Every screenshot duty in this kit was conditioned on "after
implementation", so the draft phase had the user as its first pair of eyes by construction.

THE COMMAND LINE NAMES A TASK ID, NEVER A PATH INSIDE `project_memory/`, and that is not a
convenience: `gate_write_scope` refuses any write-capable shell pipeline that names the state
directory, so `--source project_memory/staging/<id>/x.html` would be refused before this script
ever started. The id resolves to `project_memory/staging/<id>/` here instead.

  python scripts/kit_design_render.py TSK-0007
  python scripts/kit_design_render.py TSK-0007 --reference https://example.com --reference ...

FAILS LOUD, never silently skips: no Playwright, no browser binary, no staged HTML and no page
that loads are each exit 2 with the command that fixes them. A render that did not happen must not
look like one that did — the record is the evidence a gate consumes, so a half-written record would
buy a presentation nobody sighted. An unreachable REFERENCE is the one degradation: it is recorded
with its error and the run continues, because a site being down is not a reason to stop looking at
your own draft.

WHAT THE RECORD SAYS AND WHAT IT DOES NOT: it TIES a set of images to the exact bytes they were
made from (sha256). It is not evidence that a browser ran — anything with a shell can write the
same file — and it says nothing about anyone having LOOKED. `gate_design_sighted` reads it as
provenance of the bytes and states that boundary in its own row of `hooks/ENFORCEMENT.md`; the
sighting duty is prose in the product-designer skill and stays there (`FR-0035`).

Every kit update OVERWRITES this file (like kit_checks.py), so fixes reach existing projects.
"""
import argparse
import datetime
import hashlib
import json
import os
import sys

# The two widths a design draft is judged at. ONE statement of them: the record repeats what it
# rendered, and every other reader (the gate, the skills) asks the record. Desktop first, because a
# reference site is loaded at the widest configured viewport only -- an external page is the slow
# part of a run, and it is looked at for its craft, not for its breakpoints.
DEFAULT_VIEWPORTS = ("1440x900", "390x844")
RECORD_NAME = "render.json"
REVIEW_DIR = "review"
INSTALL_HINT = ("pip install -r requirements-dev.txt && playwright install chromium")

# ---------------------------------------------------------------------------------------------
# The mechanical half of the design standards, as the browser answers it.
# ---------------------------------------------------------------------------------------------
# WCAG 2.2 contrast, stated once here and read by the page probe through its argument object -- the
# probe carries no number of its own. The spec's own values: 4.5:1 for body text, 3:1 for large
# text, where large is 24 CSS px or 18.66 px at weight 700.
# THE SECOND PLACE THESE RATIOS STAND is the product-designer skill, which teaches them as a
# self-test, and a number in two places is what SR-0008 is about. They are not merged -- one is a
# threshold a machine applies, the other is a habit a role is taught -- so they are COUPLED
# instead:
# `tools/test_design_conformance.py::test_the_numbers_the_check_uses_are_the_wcag_ones_and_live_in_one_place`
# reads the ratios out of that skill's own line and fails if they and these constants disagree.
CONTRAST_BODY_MIN = 4.5
CONTRAST_LARGE_MIN = 3.0
LARGE_TEXT_PX = 24.0
LARGE_BOLD_TEXT_PX = 18.66
BOLD_WEIGHT = 700
# The two attributes a mockup uses to make RANKING checkable: the container that IS one view, and
# the one thing the user is meant to do in it. Spelled once here; `product-designer/SKILL.md` names
# the same two, and
# `tools/test_design_conformance.py::test_the_skill_teaches_the_ranking_PROCEDURE_the_check_demands`
# holds the text to these constants rather than to a copy.
VIEW_ATTR = "data-view"
PRIMARY_ACTION_ATTR = "data-primary-action"
# THE SENTENCE THE DESIGNER OWES PER VIEW, spelled in exactly one place in this kit. The refusal
# below prints it, and `product-designer/SKILL.md` teaches writing it as step 1 of its ranking
# procedure — quoting THIS template, not a paraphrase of it, which is what makes the skill's line a
# procedure instead of an adjective. That is not a hope:
# `tools/test_design_conformance.py::test_the_skill_teaches_the_ranking_PROCEDURE_the_check_demands`
# cuts the skill's ranking section out structurally and requires this exact string inside it.
RANKING_SENTENCE_TEMPLATE = ("Here the user <does one thing>, and they see it first by "
                             "<the one signal>.")
# The attribute the probe stamps on everything the browser puts in the tab order, so the Python
# side can name what Tab reached. Prefixed with the script's own name because it is written INTO
# the page under test: a collision with an author attribute would make the walk read the wrong
# element.
STAMP_ATTR = "data-kit-design-render-focusable"
# How far Tab is pressed: twice round the ring plus slack, so a sequence that cycles early is
# visible as "reached k of n" rather than as a hang. The cap is what stops a page whose focus
# handler keeps creating focusable nodes from running forever.
TAB_SLACK = 5
MAX_TAB_PRESSES = 400

# The page probe. Everything it decides, it decides with this browser's own parser and layout —
# there is no table of colour notations, no list of interactive tags and no text search anywhere
# in it, because every one of those is a claim about what CSS and HTML contain.
#
# WHAT IT READS, in one statement: the DECLARATIVE state of the light DOM, once, at load. Not a
# shadow root, not a state a script produces after load, and not a handler attached by script (the
# markup's own `onclick` is read, `addEventListener` is not). A self-contained design draft is
# exactly that kind of document, which is why the boundary is cheap here — and it is the boundary,
# not an oversight: `H140` in `docs/POST_V2_WISHLIST.md` carries it with its measurement.
_PAGE_PROBE = r"""
(cfg) => {
  const out = {colour_literals: [], focus_visible_rules: 0, animated: [], contrast: [],
               undecided: [], views: [], pointer_only: [], positive_tabindex: [], focusable: 0,
               unreadable_sheets: []};

  const pathOf = (el) => {
    const bits = [];
    for (let n = el; n && n.nodeType === 1 && bits.length < 4; n = n.parentElement) {
      let s = n.tagName.toLowerCase();
      if (n.id) { bits.unshift(s + "#" + n.id); break; }
      if (n.classList.length) s += "." + Array.from(n.classList).slice(0, 2).join(".");
      bits.unshift(s);
    }
    return bits.join(" > ");
  };

  // Taken BEFORE the probe hosts below exist. Those hosts carry an inline `style` of their own,
  // and reading this list afterwards reported the probe's own two colours as findings of the
  // draft -- measured on a draft that had none.
  const inlineStyled = Array.from(document.querySelectorAll("[style]"));

  // ---- WHAT A COLOUR LITERAL IS, decided by four properties and no list of notations ----
  // (1) it is a colour to this CSS parser, (2) it is not a CSS-wide keyword -- which is exactly a
  // value that EVERY property accepts, asked of a property that takes no colour at all --, (3) it
  // resolves the same under two different inherited colours, which is what separates a literal
  // from `currentColor`/`inherit`, and (4) it is not fully transparent, which names no colour.
  const hostA = document.createElement("div"), hostB = document.createElement("div");
  hostA.style.color = "rgb(255, 0, 0)"; hostB.style.color = "rgb(0, 0, 255)";
  const probeA = document.createElement("span"), probeB = document.createElement("span");
  hostA.appendChild(probeA); hostB.appendChild(probeB);
  document.documentElement.appendChild(hostA); document.documentElement.appendChild(hostB);
  const isColourLiteral = (value) => {
    const v = String(value == null ? "" : value).trim();
    if (!v || v.indexOf("var(") >= 0) return false;
    if (!CSS.supports("color", v)) return false;
    if (CSS.supports("border-collapse", v)) return false;
    probeA.style.color = ""; probeB.style.color = "";
    probeA.style.color = v; probeB.style.color = v;
    const a = getComputedStyle(probeA).color;
    if (a !== getComputedStyle(probeB).color) return false;
    const m = a.match(/rgba?\(([^)]+)\)/);
    if (m) { const p = m[1].split(","); if (p.length > 3 && parseFloat(p[3]) === 0) return false; }
    return true;
  };
  // A colour literal is allowed in exactly one position: as the value of a CUSTOM PROPERTY. That
  // IS the token sheet -- not a selector this check knows by name, so a theme block, a media query
  // or a scope the project invents is covered without being enumerated.
  const declare = (where, media, prop, value) => {
    if (prop.slice(0, 2) === "--") return;
    if (!isColourLiteral(value)) return;
    out.colour_literals.push({where: where, media: media, property: prop, value: String(value)});
  };
  const walkRules = (list, media) => {
    for (const rule of list) {
      const inner = rule.conditionText || media;
      // EVERY rule that carries declarations, and the name it goes under is whichever of the two
      // this rule kind has. Keying on `selectorText` alone skipped `@keyframes` steps, which is
      // where a hardcoded colour hides best: it is CSS the author wrote and no `var()` reaches it.
      if (rule.style && typeof rule.style.item === "function") {
        const where = rule.selectorText || (rule.keyText ? "@keyframes step " + rule.keyText : "");
        for (let i = 0; i < rule.style.length; i++) {
          const p = rule.style.item(i);
          declare(where, media, p, rule.style.getPropertyValue(p));
        }
      }
      if (rule.selectorText && rule.selectorText.indexOf(":focus-visible") >= 0) {
        out.focus_visible_rules += 1;
      }
      if (rule.cssRules) walkRules(rule.cssRules, inner);
      // AN `@import` IS A SHEET OF ITS OWN, and it hangs under `styleSheet`, not under `cssRules`
      // -- so the recursion above walked straight past it. Measured: an inline `@import
      // url("theme.css")` carrying the draft's only `:focus-visible` rule and a colour literal
      // produced neither. Worse than a miss: the IMPORTING sheet reads fine, so no entry landed in
      // `unreadable_sheets` either and the absence claim came out UNQUALIFIED. Same try/catch, same
      // record.
      if (rule.styleSheet) {
        try {
          walkRules(rule.styleSheet.cssRules, inner);
        } catch (e) {
          out.unreadable_sheets.push(rule.href || "an imported sheet this document may not read");
        }
      }
    }
  };
  for (const sheet of document.styleSheets) {
    try {
      walkRules(sheet.cssRules, "");
    } catch (e) {
      // A SHEET THIS DOCUMENT MAY NOT READ IS NOT AN EMPTY SHEET. Under `file://` a linked
      // stylesheet throws SecurityError on `cssRules`, and swallowing that silently made its rules
      // INVISIBLE while they were fully in effect: a colour literal in it passed, and a
      // `:focus-visible` rule in it produced "the draft declares no :focus-visible rule at all" --
      // an accusation about a rule that was right there. It is UNDECIDED, and the caller stops
      // making the absence claim once one of these exists (`H145`).
      out.unreadable_sheets.push(sheet.href || "an inline sheet this document may not read");
    }
  }
  for (const el of inlineStyled) {
    const s = el.style;
    for (let i = 0; i < s.length; i++) {
      const p = s.item(i);
      declare(pathOf(el) + " (style attribute)", "", p, s.getPropertyValue(p));
    }
  }
  // PRESENTATION ATTRIBUTES (`<rect fill="#ff0000">`, `<svg stroke="…">`) are CSS the author wrote
  // in another syntax, and they were the one authored place a literal still passed. The rule is not
  // a list of attribute names: an attribute counts when THIS parser accepts its name as a CSS
  // property carrying that value, so `class`, `id` and `d` fall out by themselves.
  for (const el of document.querySelectorAll("*")) {
    for (const attribute of el.attributes) {
      const name = attribute.name.toLowerCase();
      if (name === "style") continue;                 // already read above, as a declaration block
      if (!CSS.supports(name, attribute.value)) continue;
      declare(pathOf(el) + " (" + name + " attribute)", "", name, attribute.value);
    }
  }
  hostA.remove(); hostB.remove();

  // ---- contrast, over the text a person actually reads ----
  const rgba = (s) => {
    const m = String(s).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(",").map((x) => parseFloat(x));
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  };
  const lum = (c) => {
    const f = (x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const over = (fg, bg) => ({r: fg.r * fg.a + bg.r * (1 - fg.a),
                             g: fg.g * fg.a + bg.g * (1 - fg.a),
                             b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1});
  const ratio = (x, y) => {
    const l1 = lum(x), l2 = lum(y);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  };
  const backdrop = (el) => {
    for (let n = el; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.backgroundImage && cs.backgroundImage !== "none") {
        return {why: "a background image or gradient behind the text"};
      }
      const c = rgba(cs.backgroundColor);
      if (c && c.a === 1) return {colour: c};
      if (c && c.a > 0) return {why: "a semi-transparent background layer"};
    }
    return {colour: {r: 255, g: 255, b: 255, a: 1}};
  };
  // "Is this on screen" is asked of the DOM where the DOM can answer it: `checkVisibility` walks
  // the ANCESTORS, so text inside an `opacity: 0` wrapper is out -- the hand-rolled version below
  // reads the element's own opacity only and would have judged the contrast of a tooltip nobody
  // sees. The fallback is for a browser older than that API and says so rather than pretending.
  const rendered = (el, cs) => {
    if (typeof el.checkVisibility === "function") {
      return el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true});
    }
    return el.getClientRects().length > 0 && cs.visibility !== "hidden"
      && parseFloat(cs.opacity) > 0;
  };

  // FADING IS PART OF THE COLOUR THE READER GETS. `opacity` below 1 was read as fully opaque, so
  // `.card { opacity: .05 }` -- text nobody can make out -- was a pass. The product of the whole
  // ancestor chain is folded into the text's alpha instead. Where a faded element ALSO carries a
  // background of its own, the group is composited as a unit and this composition would be a
  // guess: that case is UNDECIDED rather than silently computed (`H146`).
  const fading = (el) => {
    let product = 1, ownBackground = false;
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const cs = getComputedStyle(n);
      const value = parseFloat(cs.opacity);
      if (!isNaN(value) && value < 1) {
        product *= value;
        const own = rgba(cs.backgroundColor);
        if (own && own.a > 0) ownBackground = true;
      }
    }
    return {product: product, ownBackground: ownBackground};
  };
  const judgeContrast = (el, cs, where, sample, extraOpacity) => {
    const fg = rgba(cs.color);
    if (!fg) return;
    // What lies behind THIS text: the box's own background when it is opaque (a pseudo-element
    // paints one the ancestor walk never sees), else the first opaque ancestor.
    const own = rgba(cs.backgroundColor);
    const paints = own && own.a === 1 && (!cs.backgroundImage || cs.backgroundImage === "none");
    const back = paints ? {colour: own} : backdrop(el);
    if (back.why) { out.undecided.push({where: where, why: back.why}); return; }
    const faded = fading(el);
    faded.product *= (isNaN(parseFloat(extraOpacity)) ? 1 : parseFloat(extraOpacity));
    if (faded.product < 1 && faded.ownBackground) {
      out.undecided.push({where: where, why: "a faded element that paints its own background "
                                             + "— the group is composited as a unit"});
      return;
    }
    const size = parseFloat(cs.fontSize) || 0;
    const weight = parseFloat(cs.fontWeight) || 400;
    const large = size >= cfg.largePx || (size >= cfg.largeBoldPx && weight >= cfg.boldWeight);
    const need = large ? cfg.largeMin : cfg.bodyMin;
    const seen = {r: fg.r, g: fg.g, b: fg.b, a: fg.a * faded.product};
    const got = ratio(over(seen, back.colour), back.colour);
    // The tolerance is the display precision below, not a softened floor: the ratio is reported to
    // two decimals, so a value that ROUNDS to exactly the required one must not be refused with a
    // number that reads as passing.
    if (got + 0.005 < need) {
      out.contrast.push({where: where, ratio: Math.round(got * 100) / 100, need: need,
                         colour: cs.color + (faded.product < 1
                           ? " at opacity " + Math.round(faded.product * 1000) / 1000 : ""),
                         background:
                           "rgb(" + [back.colour.r, back.colour.g, back.colour.b].join(", ") + ")",
                         sample: sample});
    }
  };
  // The text a `content` property generates, or null when it generates none: `none`/`normal`
  // generate nothing, a bare `url(...)` generates an image, and `content: ""` generates a box with
  // no text in it.
  const generatedText = (style) => {
    const raw = (style.content || "").trim();
    if (!raw || raw === "none" || raw === "normal") return null;
    if (/^url\(/.test(raw)) return null;
    return raw.replace(/^["']|["']$/g, "").trim() || null;
  };
  const PSEUDO_TEXT = {
    "::before": (el, style) => generatedText(style),
    "::after": (el, style) => generatedText(style),
    // Its text is the ATTRIBUTE, never `content` -- measured: `content` computes to `normal` here.
    // The attribute is also what keeps this off every element that has no placeholder at all,
    // because `getComputedStyle` hands back the element's own style for a pseudo it does not have.
    "::placeholder": (el) => ((el.getAttribute("placeholder") || "").trim() || null),
    // Its text is the LIST STYLE -- `content` computes to `normal` for an ordinary bullet, so the
    // question is whether this element renders a marker at all.
    "::marker": (el, style) => {
      const own = generatedText(style);
      if (own) return own;
      const cs = getComputedStyle(el);
      return (cs.display === "list-item" && cs.listStyleType !== "none")
        ? "list marker (" + cs.listStyleType + ")" : null;
    },
  };

  for (const el of document.querySelectorAll("*")) {
    const cs = getComputedStyle(el);
    if (!rendered(el, cs)) continue;
    const owns = Array.from(el.childNodes).some(
      (n) => n.nodeType === 3 && n.textContent.trim().length > 0);
    if (owns) judgeContrast(el, cs, pathOf(el), el.textContent.trim().slice(0, 40), 1);
    // PSEUDO-ELEMENT TEXT IS TEXT. It hangs on no child node, so the walk above never saw it.
    //
    // THIS IS A LIST, AND IT HAS NO TRIPWIRE -- so here is the reason, written out. CSS closes the
    // set of pseudo-elements (an author cannot invent one), but the DOM offers no way to ask an
    // element which of them it HAS: `getComputedStyle(el, part)` answers for every spelling, valid
    // or not. There is therefore nothing to compare a list against, and no measurement that could
    // catch a dead entry or a missing one. What the list costs is stated instead: a text-carrying
    // pseudo-element not named here is not judged, and `H146` in `docs/POST_V2_WISHLIST.md` carries
    // that. The four below are the ones that carry TEXT a reader reads; each says HOW the text
    // reaches it, because that differs and a single rule would be wrong for three of them.
    for (const part of Object.keys(PSEUDO_TEXT)) {
      const pseudo = getComputedStyle(el, part);
      const shown = PSEUDO_TEXT[part](el, pseudo);
      if (!shown) continue;
      // A PSEUDO-ELEMENT HAS ITS OWN VISIBILITY, and `rendered()` above was asked about the
      // ELEMENT. So `::before { display: none }` inside a perfectly visible card produced
      // "contrast 1.00:1 ... at opacity 0" and an empty text sample -- findings about a box that is
      // not on screen, which is the exact inversion of the rule one branch up. `checkVisibility`
      // does not reach a pseudo-element, so the three properties it would have asked are asked
      // here, off the pseudo's own computed style.
      if (pseudo.display === "none") continue;
      if (pseudo.visibility !== "visible") continue;
      if (parseFloat(pseudo.opacity) === 0) continue;
      judgeContrast(el, pseudo, pathOf(el) + part, shown.slice(0, 40), pseudo.opacity);
    }
  }

  // ---- motion: which elements this page animates AT ALL, asked of the computed style ----
  for (const el of document.querySelectorAll("*")) {
    const cs = getComputedStyle(el);
    const moving = (cs.transitionDuration + "," + cs.animationDuration).split(",")
      .some((x) => parseFloat(x) > 0);
    if (moving && rendered(el, cs)) out.animated.push(pathOf(el));
  }

  // ---- ranking: a declared view names exactly one thing to do ----
  for (const view of document.querySelectorAll("[" + cfg.viewAttr + "]")) {
    const mine = Array.from(view.querySelectorAll("[" + cfg.primaryAttr + "]"))
      .filter((e) => e.closest("[" + cfg.viewAttr + "]") === view);
    out.views.push({name: view.getAttribute(cfg.viewAttr) || pathOf(view), primary: mine.length});
  }

  // ---- the keyboard side: stamp what the browser puts in the tab order, name what it leaves out ----
  // WHAT COUNTS AS "IN THE TAB ORDER" IS `tabIndex`, the DOM's own number, and never a list of
  // tags: `<a href tabindex="-1">` is a link the mouse can use and the keyboard cannot, and a tag
  // list called it a control and stayed silent about it (measured on a planted draft).
  const nearTabOrder = (el) => {
    for (let n = el; n; n = n.parentElement) { if (n.tabIndex >= 0) return true; }
    return Array.from(el.querySelectorAll("*")).some((e) => e.tabIndex >= 0);
  };
  let n = 0;
  for (const el of document.querySelectorAll("*")) {
    const cs = getComputedStyle(el);
    if (el.tabIndex > 0) out.positive_tabindex.push({where: pathOf(el), value: el.tabIndex});
    if (el.tabIndex >= 0 && !el.disabled && rendered(el, cs)) {
      el.setAttribute(cfg.stampAttr, String(n));
      n += 1;
    } else if ((cs.cursor === "pointer" || el.onclick !== null) && rendered(el, cs)
               && !nearTabOrder(el)) {
      // The page tells a MOUSE user this is clickable and gives a keyboard user no way in. Two
      // declarative signals, and both are read off the element: the cursor it shows, and an
      // activation handler written INTO the markup. A handler attached later by script is not
      // among them -- see the head of this probe. WHICH of the two fired travels with the finding:
      // the sentence used to name the cursor whatever the reason was, so an `onclick` element with
      // a default cursor was reported for a property it did not have.
      const signals = [];
      if (cs.cursor === "pointer") signals.push("cursor: pointer");
      if (el.onclick !== null) signals.push("an onclick attribute");
      out.pointer_only.push({where: pathOf(el), signals: signals.join(" and ")});
    }
  }
  out.focusable = n;
  return out;
}
"""

# A FOCUS INDICATOR IS SOMETHING YOU CAN SEE, so it is measured in pixels: the same padded box of
# the page, shot with the element unfocused and focused, byte-compared. The padding is what makes an
# outline drawn OUTSIDE the element's own box part of the picture.
#
# The rule this replaced was the one the research prescribed -- byte-equal COMPUTED STYLES -- and it
# was measured wrong in the quiet direction: with `a:focus { outline: none }` the UA still moves
# `outline-offset` from 0px to 1px, so the computed styles differ, the rule stayed silent, and
# nothing at all appears on screen. Pixels have no such property.
FOCUS_PIXEL_PAD = 8
# How many focusable elements the pixel comparison covers. Two screenshots each, ~33 ms per shot
# measured on this kit's own Chromium, so this budget is about eight seconds on a draft that spends
# it all. Beyond it the elements are NOT compared and are reported as not measured -- never as
# passed.
FOCUS_PIXEL_BUDGET = 120

_STAMPED_BOXES = r"""
(attr) => Array.from(document.querySelectorAll("[" + attr + "]")).map((el) => {
  const r = el.getBoundingClientRect();
  return {index: el.getAttribute(attr),
          label: (el.textContent || "").trim().slice(0, 40) || el.tagName.toLowerCase(),
          x: r.x + scrollX, y: r.y + scrollY, width: r.width, height: r.height};
})
"""
_ACTIVE_STAMP = r"""
(attr) => {
  const el = document.activeElement;
  if (!el || el === document.body || el === document.documentElement) return null;
  return el.getAttribute(attr);
}
"""


def _probe_config():
    """The one place the numbers and attribute names above reach the page."""
    return {"bodyMin": CONTRAST_BODY_MIN, "largeMin": CONTRAST_LARGE_MIN,
            "largePx": LARGE_TEXT_PX, "largeBoldPx": LARGE_BOLD_TEXT_PX,
            "boldWeight": BOLD_WEIGHT, "viewAttr": VIEW_ATTR,
            "primaryAttr": PRIMARY_ACTION_ATTR, "stampAttr": STAMP_ATTR}


def _focus_clip(page, box):
    """The padded box of `box` as PNG bytes, or None when it cannot be shot.

    None and not an exception, in both cases that produce it — an element with no box at all, and a
    clip the browser refuses (one that reaches past the document, say). The caller reports a None as
    NOT MEASURED; raising here would abort a render that had already produced every screenshot and
    tell the designer nobody had looked at the draft.
    """
    if not box or box["width"] <= 0 or box["height"] <= 0:
        return None
    try:
        return page.screenshot(full_page=True, clip={
            "x": max(0.0, box["x"] - FOCUS_PIXEL_PAD), "y": max(0.0, box["y"] - FOCUS_PIXEL_PAD),
            "width": box["width"] + 2 * FOCUS_PIXEL_PAD,
            "height": box["height"] + 2 * FOCUS_PIXEL_PAD})
    except Exception:                                        # noqa: BLE001 — see the docstring
        return None


def keyboard_path(page, focusable):
    """(findings, undecided) of the KEYBOARD half, walked with real Tab presses on the real page.

    Two failure pictures here, and a third comes from the probe rather than from this walk: an
    element the browser puts in the tab order that Tab never arrives at (a trap, or an order that
    skips it), an element Tab does reach that looks EXACTLY the same focused and unfocused, and —
    in the probe — an element the page marks clickable for the mouse that is in no tab order.

    The bound is `MAX_TAB_PRESSES`; reaching it is reported as "reached k of n", which is what a
    trap looks like from outside. Nothing here can say whether the ORDER is sensible: that is
    composition and stays the designer's judgement (`docs/POST_V2_WISHLIST.md` section 1a).
    """
    findings, undecided = [], []
    if not focusable:
        return findings, undecided
    boxes = {one["index"]: one for one in page.evaluate(_STAMPED_BOXES, STAMP_ATTR)}
    page.evaluate("() => { if (document.activeElement) document.activeElement.blur(); }")
    in_budget = sorted(boxes, key=lambda one: int(one))[:FOCUS_PIXEL_BUDGET]
    resting = {index: _focus_clip(page, boxes[index]) for index in in_budget}
    reached = {}
    for _ in range(min(MAX_TAB_PRESSES, 2 * focusable + TAB_SLACK)):
        page.keyboard.press("Tab")
        index = page.evaluate(_ACTIVE_STAMP, STAMP_ATTR)
        if index is None:
            continue
        if index not in reached:
            reached[index] = _focus_clip(page, boxes.get(index)) if index in resting else None
        if len(reached) >= focusable:
            break

    def label(index):
        return repr(boxes[index]["label"])

    missed = sorted(set(boxes) - set(reached), key=lambda one: int(one))
    if missed:
        findings.append(
            "the keyboard reaches %d of %d focusable elements — %s never receive focus, so what a "
            "mouse can do there a keyboard cannot"
            % (len(reached), focusable, ", ".join(label(one) for one in missed[:4])))
    blind = [one for one in sorted(reached, key=lambda x: int(x))
             if resting.get(one) is not None and resting[one] == reached[one]]
    if blind:
        findings.append(
            "%d focused element(s) look EXACTLY the same as unfocused, pixel for pixel (%s) — a "
            "keyboard user cannot see where they are; give the draft a :focus-visible rule instead "
            "of removing the outline"
            % (len(blind), ", ".join(label(one) for one in blind[:4])))
    unshot = [one for one in sorted(reached, key=lambda x: int(x))
              if one not in resting or resting[one] is None]
    if unshot:
        undecided.append(
            "%d focusable element(s) were NOT compared for a visible focus indicator (%s%s): "
            "past the %d-element budget, or with no box on screen to shoot"
            % (len(unshot), ", ".join(label(one) for one in unshot[:3]),
               " ..." if len(unshot) > 3 else "", FOCUS_PIXEL_BUDGET))
    return findings, undecided


def conformance(page, open_reduced=None):
    """({findings, undecided}) for ONE rendered draft — the mechanically checkable share.

    `open_reduced` opens the SAME draft in a context that asks for reduced motion, and it is a
    CALLABLE rather than a page because it is only ever called when this draft animates something:
    the question it answers is whether those animations stop, so a still draft pays no second page
    load for it. Passing None answers that question with silence rather than with a pass, which is
    what a caller without a browser context gets.
    """
    facts = page.evaluate(_PAGE_PROBE, _probe_config())
    findings = []

    for entry in facts["colour_literals"][:12]:
        findings.append(
            "colour literal outside the token sheet: `%s` in `%s`%s — a frozen revision that spells "
            "its colours cannot say whether the build kept them; declare it as a custom property "
            "and reference it with var()"
            % (entry["property"] + ": " + entry["value"], entry["where"],
               " under @media %s" % entry["media"] if entry["media"] else ""))
    if len(facts["colour_literals"]) > 12:
        findings.append("... and %d further colour literal(s) outside the token sheet"
                        % (len(facts["colour_literals"]) - 12))

    for entry in facts["contrast"][:12]:
        findings.append(
            "contrast %.2f:1 where %.1f:1 is required — %s on %s at %s (%r)"
            % (entry["ratio"], entry["need"], entry["colour"], entry["background"],
               entry["where"], entry["sample"]))
    if len(facts["contrast"]) > 12:
        findings.append("... and %d further text node(s) under the contrast floor"
                        % (len(facts["contrast"]) - 12))

    keyboard_findings, keyboard_undecided = keyboard_path(page, facts["focusable"])
    findings += keyboard_findings
    for entry in facts["pointer_only"][:6]:
        findings.append(
            "%s is clickable for the mouse (%s) and is in no tab order — the keyboard cannot reach "
            "it at all" % (entry["where"], entry["signals"]))
    for entry in facts["positive_tabindex"][:6]:
        findings.append(
            "%s carries tabindex=%d — a positive tabindex overrides the document order for the "
            "whole page, and the order a reader then gets is not the one the layout shows"
            % (entry["where"], entry["value"]))

    if facts["focusable"] and not facts["focus_visible_rules"]:
        # QUALIFIED, NOT SUPPRESSED. "declares no :focus-visible rule at all" is a claim about the
        # whole document, and a sheet this document may not read makes it one nobody checked. The
        # first cut answered that by dropping the finding entirely — so a draft with NO focus rule
        # anywhere plus one unreadable `print.css` came back clean (measured, rc 0). What the
        # unreadable sheet takes away is the word "at all", not the finding: the sentence says what
        # WAS read, and the undecided line below names the sheet (`H145`).
        findings.append(
            "no :focus-visible rule in the sheets this run could read%s — whatever focus looks "
            "like here is the browser default, so the build inherits no focus style from this "
            "contract"
            % ("" if not facts["unreadable_sheets"]
               else " (%d sheet(s) unreadable, named below — the rule may be in one of them)"
                    % len(facts["unreadable_sheets"])))

    if facts["animated"] and open_reduced is not None:
        reduced = open_reduced()
        try:
            still_moving = reduced.evaluate(_PAGE_PROBE, _probe_config())["animated"]
        finally:
            reduced.context.close()
        if still_moving:
            findings.append(
                "%d element(s) keep animating when the system asks for reduced motion (%s) — the "
                "@media (prefers-reduced-motion: reduce) fallback the design spec calls mandatory "
                "is missing or does not cover them"
                % (len(still_moving), ", ".join(still_moving[:4])))

    for view in facts["views"]:
        if view["primary"] != 1:
            findings.append(
                "view %r declares %d primary action(s) [%s]; a view names exactly ONE thing the "
                "user should do here. Write the sentence — %s — then mark that one element."
                % (view["name"], view["primary"], PRIMARY_ACTION_ATTR, RANKING_SENTENCE_TEMPLATE))

    undecided = ["%s: %s" % (one["where"], one["why"]) for one in facts["undecided"]]
    for href in facts["unreadable_sheets"]:
        undecided.append(
            "%s: this document may not read that stylesheet's rules, so every colour literal and "
            "every :focus-visible rule in it is IN EFFECT and unjudged" % href)
    if not facts["views"]:
        # SILENCE IS NOT A PASS. A draft that declares no view at all was judged by the ranking rule
        # nowhere, and said nothing about it — which reads exactly like a draft that passed.
        undecided.append(
            "the whole draft: no [%s] container, so the one-primary-goal rule judged nothing here. "
            "A Phase-1 tile sheet legitimately has none; a per-view mockup has one per view."
            % VIEW_ATTR)
    return {"findings": findings, "undecided": sorted(set(undecided)) + keyboard_undecided}


def repo_root(start):
    """The project root — the nearest ancestor holding `project_memory/`."""
    here = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(here, "project_memory")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def staging_dir(root, task_id):
    return os.path.join(root, "project_memory", "staging", task_id)


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def drafts_in(directory):
    """Every HTML draft staged for this task, EXCEPT what a previous run wrote.

    The review directory is excluded by name: a rendered artefact of this script must never become
    a subject of the next run.
    """
    found = []
    for base, dirs, names in os.walk(directory):
        dirs[:] = [d for d in dirs if d != REVIEW_DIR]
        for name in sorted(names):
            if name.lower().endswith((".html", ".htm")):
                found.append(os.path.join(base, name))
    return sorted(found)


def parse_viewport(text):
    width, _sep, height = str(text).lower().partition("x")
    return int(width), int(height)


def _slug(text):
    return "".join(char if char.isalnum() or char in "-_" else "-" for char in text)[:60]


def render(task_id, references, viewports, root=None, out=sys.stderr):
    root = root or repo_root(os.getcwd())
    if not root:
        out.write("[design-render] no project_memory/ above %s — run this from the project.\n"
                  % os.getcwd())
        return 2
    item_dir = staging_dir(root, task_id)
    if not os.path.isdir(item_dir):
        out.write("[design-render] no staging directory for %s (%s). The designer stages its "
                  "draft there; render the task that owns the draft.\n" % (task_id, item_dir))
        return 2
    drafts = drafts_in(item_dir)
    if not drafts:
        out.write("[design-render] %s stages no .html draft — nothing to render. A wireframe "
                  "(.drawio.svg) is not this script's subject.\n" % task_id)
        return 2
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    except ImportError:
        out.write("[design-render] Playwright (Python) is not installed, so no draft can be "
                  "looked at. This is a hard stop, not a warning: a design draft that reaches the "
                  "user unrendered is the defect this step exists for.\nInstall: %s\n"
                  % INSTALL_HINT)
        return 2

    review = os.path.join(item_dir, REVIEW_DIR)
    os.makedirs(review, exist_ok=True)
    sizes = [parse_viewport(v) for v in viewports]
    record = {
        "tool": os.path.basename(__file__),
        "generated": datetime.datetime.now().replace(microsecond=0).isoformat(),
        "task": task_id,
        "viewports": list(viewports),
        "sources": [],
        "references": [],
    }
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch()
            for draft in drafts:
                relative = os.path.relpath(draft, item_dir).replace(os.sep, "/")
                url = "file:///" + os.path.abspath(draft).replace(os.sep, "/")
                images = []
                for width, height in sizes:
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.goto(url, wait_until="load", timeout=15000)
                    name = "%s__%dx%d.png" % (_slug(os.path.splitext(relative)[0]), width, height)
                    page.screenshot(path=os.path.join(review, name), full_page=True)
                    page.close()
                    images.append(REVIEW_DIR + "/" + name)
                # A page of its OWN for the checks, at the widest configured viewport, and after
                # every screenshot: the probe stamps an attribute on what the browser can focus and
                # then presses Tab, so running it on a page a screenshot still has to come from
                # would put the check's own marks into the image the designer looks at.
                width, height = sizes[0]
                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto(url, wait_until="load", timeout=15000)

                def open_reduced(url=url, width=width, height=height):
                    context = browser.new_context(reduced_motion="reduce",
                                                  viewport={"width": width, "height": height})
                    reduced = context.new_page()
                    reduced.goto(url, wait_until="load", timeout=15000)
                    return reduced

                try:
                    verdict = conformance(page, open_reduced)
                except Exception as exc:                     # noqa: BLE001
                    # A BREAKING CHECK MUST NOT LOOK LIKE A DRAFT NOBODY RENDERED. Every screenshot
                    # of this draft already exists; letting the failure reach the handler below
                    # would drop the record and print "nothing was rendered", which sends the
                    # designer to install a browser they already have. It is a FINDING instead —
                    # loud, exit 3 — because a check that did not run has not passed either.
                    verdict = {"findings": ["the standards checks could not run on this draft (%s: "
                                            "%s) — the screenshots above are complete, but nothing "
                                            "below them was measured"
                                            % (type(exc).__name__, str(exc)[:200])],
                               "undecided": []}
                page.close()
                record["sources"].append({"path": relative, "sha256": file_sha256(draft),
                                          "images": images, "conformance": verdict})
            width, height = sizes[0]
            for index, url in enumerate(references, start=1):
                entry = {"url": url, "image": None, "error": None}
                name = "reference-%02d-%s__%dx%d.png" % (index, _slug(url), width, height)
                try:
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.goto(url, wait_until="load", timeout=20000)
                    page.screenshot(path=os.path.join(review, name), full_page=False)
                    page.close()
                    entry["image"] = REVIEW_DIR + "/" + name
                except Exception as exc:                     # noqa: BLE001 — see the module head
                    entry["error"] = str(exc)[:300]
                    out.write("[design-render] reference %s could not be loaded: %s\n"
                              % (url, entry["error"]))
                record["references"].append(entry)
            browser.close()
    except Exception as exc:                                 # noqa: BLE001
        message = str(exc)
        if "Executable doesn't exist" in message or "playwright install" in message:
            out.write("[design-render] the Chromium binary is missing, so nothing was rendered.\n"
                      "Install: playwright install chromium\n")
        else:
            out.write("[design-render] rendering failed: %s\n" % message[:500])
        return 2

    with open(os.path.join(review, RECORD_NAME), "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
        handle.write("\n")
    out.write("[design-render] %d draft(s) x %d viewport(s) -> %s\n"
              % (len(drafts), len(sizes), os.path.join(review, "")))
    out.write("[design-render] NOW LOOK AT THEM. Read every PNG, compare against the frozen "
              "wireframe and the references, fix what you see, and render again — the record only "
              "says the pixels exist.\n")

    findings = 0
    for entry in record["sources"]:
        verdict = entry.get("conformance") or {}
        for line in verdict.get("undecided") or []:
            out.write("[design-render] %s: NOT DECIDABLE here — %s\n" % (entry["path"], line))
        for line in verdict.get("findings") or []:
            findings += 1
            out.write("[design-render] %s: %s\n" % (entry["path"], line))
    if not findings:
        out.write("[design-render] the automatically checkable share of the design standards "
                  "passed on every draft. That share is contrast, the keyboard path, reduced "
                  "motion, focus visibility, colour literals and one primary goal per declared "
                  "view — it is not an accessibility verdict and it does not judge the design.\n")
        return 0
    out.write("[design-render] %d finding(s) above. They are the automatically checkable share, "
              "so a clean run says nothing about whether the draft is good — and a run with "
              "findings says the frozen contract would hand them all down to the build. Fix and "
              "render again.\n" % findings)
    return 3


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("task_id", help="the task whose staging directory holds the draft")
    parser.add_argument("--reference", action="append", default=[], metavar="URL",
                        help="a style reference (or the current site) to shoot beside the draft; "
                             "take the URLs from the design-ambition Decision item, never from a "
                             "list in this script")
    parser.add_argument("--viewport", action="append", default=[], metavar="WxH",
                        help="override the viewports (default: %s)" % ", ".join(DEFAULT_VIEWPORTS))
    args = parser.parse_args(argv)
    try:
        viewports = [v for v in (args.viewport or list(DEFAULT_VIEWPORTS))]
        for one in viewports:
            parse_viewport(one)
    except ValueError:
        sys.stderr.write("[design-render] a viewport is WIDTHxHEIGHT, e.g. 1440x900\n")
        return 2
    return render(args.task_id, args.reference, viewports)


if __name__ == "__main__":
    sys.exit(main())
