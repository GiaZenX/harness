#!/usr/bin/env python3
"""
The mechanically checkable half of the design standards, measured on the SHIPPED script.

WHAT IS UNDER TEST: `team-kits/dev-team/templates/repo/scripts/kit_design_render.py`, run as a
PROCESS against a project outside this repo, exactly the way a designer runs it. Nothing here
imports the check and calls it with a hand-built page: what the standards half judges is a rendered
DOM, so a fixture that skipped the browser would measure the assertion and not the draft.

WHY THE CASES ARE PLANTED ONE PER RULE: a draft that violates six rules at once proves that
SOMETHING refused, and the round after it deletes five of the six without anything turning red. So
each case below starts from ONE clean draft and breaks exactly one property in it -- and the clean
draft itself is a case, because a check that refuses everything is worth as little as one that
refuses nothing.

WHAT IS NOT MEASURED HERE, and it is the honest half of `FR-0077`: no `axe-core` run. axe is an npm
package, the kit ships no npm manifest at all (`templates/repo/` carries `requirements-dev.txt`,
`ruff.toml` and `scripts/`), and the one dependency file it does ship was outside this stream's file
ownership -- so what ships is the share that needs no dependency. The place that says so to a reader
is the script's own module docstring and `docs/POST_V2_WISHLIST.md` section 1c, and
`tools/test_design_conformance.py::test_the_report_never_calls_a_draft_accessible` holds the wording
of every run to it.
"""
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, "team-kits", "dev-team")
RENDER = os.path.join(KIT, "templates", "repo", "scripts", "kit_design_render.py")
HOOKS = os.path.join(KIT, "hooks")
DESIGNER_SKILL = os.path.join(KIT, "skills", "product-designer", "SKILL.md")
TASK = "TSK-0007"
DRAFT = "DSN-0001.html"

# ONE clean draft, and every case below is this string with exactly one property broken. It carries
# every shape the checks look at -- a token sheet, a transition, a focus rule, a declared view with
# one primary action, a link and a button -- because a case that has to ADD the shape it breaks
# would also be testing that the shape was added.
CLEAN = """<!doctype html><html lang="de"><head><meta charset="utf-8"><title>DSN</title><style>
:root { --bg:#ffffff; --fg:#1a1a1a; --brand:#0b5fff; --line:#d0d0d0; }
body { background: var(--bg); color: var(--fg); font-family: system-ui, sans-serif; }
.card { border:1px solid var(--line); transition: transform 180ms ease-out; }
a:focus-visible, button:focus-visible { outline: 3px solid var(--brand); outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) {
  * { transition-duration: 0ms !important; animation-duration: 0ms !important; }
}
</style></head><body>
<section data-view="uebersicht"><h1>Uebersicht</h1>
<div class="card">Eine Karte</div>
<button data-primary-action>Rechnung anlegen</button>
<a href="#hilfe">Hilfe</a>
</section></body></html>"""

FOCUS_RULE = ("a:focus-visible, button:focus-visible { outline: 3px solid var(--brand); "
              "outline-offset: 2px; }")
REDUCED_BLOCK = ("@media (prefers-reduced-motion: reduce) {\n"
                 "  * { transition-duration: 0ms !important; animation-duration: 0ms !important; }\n"
                 "}")
HELP_LINK = '<a href="#hilfe">Hilfe</a>'

# (case name, the draft, the sentence the refusal must carry). The sentence is asserted and not only
# the exit code: with `== 3` alone, every case would stay green on the wrong finding, and the round
# that swapped two rules would not notice.
PLANTED = [
    ("contrast below the WCAG ratio",
     CLEAN.replace("--fg:#1a1a1a", "--fg:#bbbbbb"),
     "where 4.5:1 is required"),
    ("a colour literal outside the token sheet",
     CLEAN.replace("border:1px solid var(--line)", "border:1px solid #dddddd"),
     "colour literal outside the token sheet"),
    # A KEYFRAME IS CSS THE AUTHOR WROTE, and the first cut of the rule walk keyed on
    # `selectorText`, which a keyframe step does not have — so this was the one place a hardcoded
    # colour passed. Measured on this draft before the walk learned `keyText`.
    ("a colour literal inside a keyframe",
     CLEAN.replace("</style>", "@keyframes pulse { 0% { background-color: #ff0000; } }\n</style>"),
     "@keyframes step"),
    ("animation that ignores reduced motion",
     CLEAN.replace(REDUCED_BLOCK, ""),
     "keep animating when the system asks for reduced motion"),
    ("a focus that cannot be seen",
     CLEAN.replace(FOCUS_RULE, "a:focus, button:focus { outline: none; }"),
     "look EXACTLY the same as unfocused, pixel for pixel"),
    # THE CASE THE RESEARCH'S OWN RULE MISSED. `docs/research/2026-07-27-SYNTHESE.md` C2 prescribes
    # "invisible focus = byte-equal computed styles"; measured on this draft, Chromium still moves
    # the link's `outline-offset` from 0px to 1px while nothing appears on screen, so the computed
    # styles differ and that rule stays silent. The shipped check compares PIXELS for this reason.
    ("a focus ring only the computed style still shows",
     CLEAN.replace(FOCUS_RULE,
                   "button:focus-visible { outline: 3px solid var(--brand); } "
                   "a:focus { outline: none; }"),
     "look EXACTLY the same as unfocused, pixel for pixel"),
    ("something the mouse can click and the keyboard cannot reach",
     CLEAN.replace('<div class="card">', '<div class="card" style="cursor:pointer">'),
     "is in no tab order"),
    ("a link taken out of the tab order",
     CLEAN.replace(HELP_LINK, '<a href="#hilfe" tabindex="-1">Hilfe</a>'),
     "is in no tab order"),
    ("a positive tabindex",
     CLEAN.replace(HELP_LINK, '<a href="#hilfe" tabindex="3">Hilfe</a>'),
     "overrides the document order"),
    ("a view with TWO primary actions",
     CLEAN.replace(HELP_LINK, '<a href="#hilfe" data-primary-action>Hilfe</a>'),
     "declares 2 primary action(s)"),
    ("a view with NO primary action",
     CLEAN.replace(" data-primary-action", ""),
     "declares 0 primary action(s)"),
]


def stage(tmp_path, body, name=DRAFT, task=TASK):
    """A project outside this repo with one staged draft, and its repo-relative path."""
    relative = "project_memory/staging/%s/%s" % (task, name)
    path = os.path.join(str(tmp_path), *relative.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(body)
    return relative


def render(tmp_path, task=TASK):
    """The shipped script as a process, from the project directory — no import, no monkeypatch."""
    return subprocess.run([sys.executable, "-B", RENDER, task], cwd=str(tmp_path),
                          capture_output=True, text=True, timeout=600)


def _needs_a_browser(done):
    """Skip only where the machine has no Chromium, and never where the script found something.

    The same boundary `tools/test_hooks.py::test_the_shipped_renderer_writes_a_record_the_gate_accepts`
    draws: exit 2 with the install line is a machine without a browser, and exit 2 for any other
    reason is a failure this suite must show.
    """
    text = done.stdout + done.stderr
    if done.returncode == 2 and ("Chromium" in text or "Playwright (Python) is not installed" in text):
        pytest.skip("no Chromium on this machine — the browser half cannot be measured here")


@pytest.mark.parametrize("name,body,sentence", PLANTED,
                         ids=[one[0].replace(" ", "-") for one in PLANTED])
def test_each_planted_standard_violation_makes_the_shipped_render_refuse(tmp_path, name, body,
                                                                         sentence):
    """One property broken, one refusal, and the refusal says WHICH property (FR-0077, FR-0078).

    Exit 3 and not 2: the draft WAS rendered and the record written — 2 is reserved for a draft
    nobody looked at, and the two answers must not collapse into one.
    """
    pytest.importorskip("playwright")
    stage(tmp_path, body)
    done = render(tmp_path)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert done.returncode == 3, (name, text)
    assert sentence in text, (name, text)


def test_the_clean_draft_this_suite_breaks_passes_untouched(tmp_path):
    """The other end of every case above: unbroken, this draft is exit 0.

    Without this, a check that refused every draft would make all ten cases green, and the cost of
    these rules to a legitimate draft would be invisible.
    """
    pytest.importorskip("playwright")
    stage(tmp_path, CLEAN)
    done = render(tmp_path)
    _needs_a_browser(done)
    assert done.returncode == 0, done.stdout + done.stderr


def _sighting_gate(root, relative):
    """The shipped `gate_design_sighted` as a process, asked about one staged draft by name."""
    payload = {"hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion", "cwd": str(root),
               "tool_input": {"questions": [{"question": "Datei: %s" % relative, "header": "Design",
                                             "options": [{"label": "A",
                                                          "description": "die Kacheln"}]}]}}
    return subprocess.run([sys.executable, os.path.join(HOOKS, "gate_design_sighted.py")],
                          input=json.dumps(payload), capture_output=True, text=True,
                          env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root),
                                   HARNESS_KERNEL_PATH=os.path.join(ROOT, "team-kits")),
                          timeout=120)


def test_a_draft_with_conformance_findings_is_refused_and_an_undecided_one_is_not(tmp_path):
    """BUG-0294: a rendered draft with findings no longer walks past the sighting gate.

    Two questions used to have two answers and only one of them refused: the record said the draft
    was RENDERED and the exit code said what was wrong, so a role that ignored the exit code
    presented a draft with findings and nothing stopped it. Measured before the repair: a draft
    with a contrast of 1.92:1 was renderer rc 3 and hook rc 0.

    THE RECORD IS STILL WRITTEN on a finding, and that half has not moved -- the day the renderer
    withholds it, the refusal a designer meets says "nobody has rendered this draft" and sends them
    to fix the wrong thing. What changed is that the gate reads the record's
    `conformance.findings` as well as its provenance.

    THE COUNTER-END IS THE SECOND HALF: a draft whose contrast the checker could not DECIDE (text
    over a gradient) is `NOT DECIDABLE`, renderer rc 0, and the gate opens. Without it this test
    would be satisfied by a gate that refused every rendered draft.
    """
    pytest.importorskip("playwright")
    relative = stage(tmp_path, CLEAN.replace("--fg:#1a1a1a", "--fg:#bbbbbb"))
    done = render(tmp_path)
    _needs_a_browser(done)
    assert done.returncode == 3, done.stdout + done.stderr
    record_path = os.path.join(str(tmp_path), "project_memory", "staging", TASK, "review",
                               "render.json")
    with open(record_path, encoding="utf-8") as handle:
        record = json.load(handle)
    entry, = record["sources"]
    assert entry["conformance"]["findings"], record

    gate = _sighting_gate(tmp_path, relative)
    assert gate.returncode == 2, gate.stdout + gate.stderr
    assert "conformance finding" in gate.stderr, gate.stderr

    undecided = tmp_path / "undecided"
    relative = stage(undecided, CLEAN.replace("body { background: var(--bg);",
                                              "body { background: linear-gradient(#fff, #eee);"))
    clean = render(undecided)
    _needs_a_browser(clean)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    opened = _sighting_gate(undecided, relative)
    assert opened.returncode == 0, opened.stdout + opened.stderr


def test_a_value_the_check_cannot_decide_is_named_and_is_not_a_finding(tmp_path):
    """Text over a gradient: reported as NOT DECIDABLE, exit 0.

    The dangerous direction is the other one — counting an undecidable contrast as a pass and
    saying nothing. Both halves are here: the words have to appear AND the run has to stay 0, so
    neither turning it into a refusal nor dropping the line keeps this green.
    """
    pytest.importorskip("playwright")
    stage(tmp_path, CLEAN.replace("body { background: var(--bg);",
                                  "body { background: linear-gradient(#fff, #eee);"))
    done = render(tmp_path)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert done.returncode == 0, text
    assert "NOT DECIDABLE" in text and "gradient behind the text" in text, text


def test_text_nobody_can_see_is_not_judged_for_contrast(tmp_path):
    """The over-refusal side of the contrast rule, and the reason it asks the DOM instead of a formula.

    An element's OWN `opacity` is 1 inside a wrapper whose opacity is 0 — a tooltip, a slide that
    has not entered, a collapsed panel. Reading the element alone reports a contrast finding on
    text nobody can see, and the designer is sent to fix a colour that is never on screen. The
    question goes to `checkVisibility`, which walks the ancestors, and this measures that: red
    without it, because the low-contrast paragraph below is invisible and must not be reported.
    """
    pytest.importorskip("playwright")
    body = CLEAN.replace(":root { --bg:#ffffff;", ":root { --faint:#bbbbbb; --bg:#ffffff;")
    body = body.replace("</style>",
                        ".ghost { opacity: 0; } .faint { color: var(--faint); }\n</style>")
    body = body.replace("</section>",
                        '<div class="ghost"><p class="faint">Unsichtbar</p></div></section>')
    stage(tmp_path, body)
    done = render(tmp_path)
    _needs_a_browser(done)
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_report_never_calls_a_draft_accessible(tmp_path):
    """The condition `docs/POST_V2_WISHLIST.md` section 1c puts on building this at all.

    "A gate text that says 'accessible' REPLACES the manual review instead of carrying it" — so the
    words are checked against what a run actually PRINTS, on both a clean and a failing draft, and
    not against a sentence in a file. `barrierefrei` is in the list because the section states the
    condition in German and a German message is the one a reader here would write.
    """
    pytest.importorskip("playwright")
    forbidden = ("accessible", "accessibility-compliant", "wcag-compliant", "wcag compliant",
                 "barrierefrei", "fully accessible", "a11y verified")
    for body in (CLEAN, CLEAN.replace("--fg:#1a1a1a", "--fg:#bbbbbb")):
        stage(tmp_path, body)
        done = render(tmp_path)
        _needs_a_browser(done)
        text = (done.stdout + done.stderr).lower()
        assert text.strip(), done
        for word in forbidden:
            assert word not in text, (word, text)
        assert "automatically checkable share" in text, text


def test_a_project_that_stages_no_draft_never_reaches_the_browser(tmp_path):
    """The DEC-0056 cost side: what a project without a UI pays for these checks.

    It pays a directory listing. The script answers "stages no .html draft" and returns BEFORE the
    Playwright import, which is what this measures: the run that says so must not also carry the
    install line, because carrying it would mean the import had been attempted. Nothing is mocked —
    if the guard ever moved below the import, a machine without Playwright would print the other
    message and this turns red.
    """
    os.makedirs(os.path.join(str(tmp_path), "project_memory", "staging", TASK))
    with open(os.path.join(str(tmp_path), "project_memory", "staging", TASK, "WFR-0001.drawio.svg"),
              "w", encoding="utf-8") as handle:
        handle.write("<svg/>")
    done = render(tmp_path)
    text = done.stdout + done.stderr
    assert done.returncode == 2, text
    assert "stages no .html draft" in text, text
    assert "playwright" not in text.lower(), text
    assert not os.path.isdir(os.path.join(str(tmp_path), "project_memory", "staging", TASK,
                                          "review")), "a run that rendered nothing left a review/"


def test_a_check_that_breaks_is_a_finding_and_never_looks_like_an_unrendered_draft(tmp_path):
    """The failure mode of a checking step bolted onto a rendering step, measured rather than argued.

    Every screenshot of the draft already exists by the time the checks run. If a check raises and
    the exception reaches the renderer's own handler, the run answers 2 with "nothing was rendered"
    and drops the record — so the designer is sent to install a browser they have, and
    `gate_design_sighted` then refuses the presentation for a reason that is not true.

    The defect is planted in a COPY of the shipped script — one line, the page probe replaced by a
    throw — and the copy is run as a process on a project outside this repo. Nothing is mocked: the
    subject is the same file with one thing wrong in it.
    """
    pytest.importorskip("playwright")
    with open(RENDER, encoding="utf-8") as handle:
        source = handle.read()
    marker = "_PAGE_PROBE = r\"\"\"\n"
    assert marker in source, "the page probe is not where this test plants its defect any more"
    broken = source.replace(marker, marker + "() => { throw new Error('planted'); }\n/*\n", 1)
    broken = broken.replace("\n\"\"\"\n\n# A FOCUS INDICATOR", "\n*/\n\"\"\"\n\n# A FOCUS INDICATOR", 1)
    script = os.path.join(str(tmp_path), "scripts", "kit_design_render.py")
    os.makedirs(os.path.dirname(script), exist_ok=True)
    with open(script, "w", encoding="utf-8") as handle:
        handle.write(broken)
    stage(tmp_path, CLEAN)
    done = subprocess.run([sys.executable, "-B", script, TASK], cwd=str(tmp_path),
                          capture_output=True, text=True, timeout=600)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert done.returncode == 3, text
    assert "the standards checks could not run on this draft" in text, text
    assert os.path.isfile(os.path.join(str(tmp_path), "project_memory", "staging", TASK, "review",
                                       "render.json")), text


def test_a_stylesheet_this_document_may_not_read_is_undecided_and_never_an_accusation(tmp_path):
    """`H145`: a linked sheet under `file://` throws on `cssRules`, and silence made it two defects.

    Measured by a verifier on the first cut: a colour literal that lived only in the linked sheet
    passed (rc 0, not a word), and a `:focus-visible` rule that lived only there produced "the draft
    declares no :focus-visible rule at all" — an accusation about a rule sitting in the file, in
    effect. Both halves are here, because fixing only the loud one would leave the silent one.
    """
    pytest.importorskip("playwright")
    linked = "project_memory/staging/%s/tokens.css" % TASK
    body = CLEAN.replace("<style>", '<link rel="stylesheet" href="tokens.css"><style>')
    body = body.replace(FOCUS_RULE, "")
    stage(tmp_path, body)
    path = os.path.join(str(tmp_path), *linked.split("/"))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(".card { border-color: #ff00ff; }\n"
                     "a:focus-visible, button:focus-visible { outline: 3px solid #0b5fff; }\n")
    done = render(tmp_path)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert "may not read that stylesheet's rules" in text, (
        "the unreadable sheet was counted as an empty one — everything in it is unjudged and "
        "nothing says so: %s" % text)
    assert "declares no :focus-visible rule at all" not in text, (
        "the draft was accused of having no :focus-visible rule while one sits in the sheet this "
        "document may not read: %s" % text)
    assert "sheet(s) unreadable" in text, (
        "the finding no longer says that a sheet went unread, so a reader cannot tell a draft that "
        "HAS no focus rule from one whose rule nobody could look at: %s" % text)


def test_a_faded_element_is_judged_on_the_colour_the_reader_gets(tmp_path):
    """`H146`, first half: `opacity` under 1 was read as fully opaque, so faded text was a pass.

    `.card { opacity: .05 }` renders text nobody can make out and came back rc 0. The whole
    ancestor chain's opacity is folded into the text's alpha now.
    """
    pytest.importorskip("playwright")
    stage(tmp_path, CLEAN.replace(".card { border:1px solid var(--line);",
                                  ".card { opacity: 0.05; border:1px solid var(--line);"))
    done = render(tmp_path)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert done.returncode == 3, text
    assert "at opacity" in text, text


def test_text_a_pseudo_element_generates_is_text(tmp_path):
    """`H146`, second half: `::before { content }` carries a label and no child node holds it."""
    pytest.importorskip("playwright")
    body = CLEAN.replace(":root { --bg:#ffffff;", ":root { --faint:#bbbbbb; --bg:#ffffff;")
    body = body.replace("</style>", '.card::before { content: "Neu"; color: var(--faint); }\n</style>')
    stage(tmp_path, body)
    done = render(tmp_path)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert done.returncode == 3, text
    assert "::before" in text, text


def test_a_colour_literal_in_a_presentation_attribute_is_one_too(tmp_path):
    """`<rect fill="#ff0000">` is CSS the author wrote in another syntax — the last authored gap.

    The rule is not a list of attribute names: an attribute counts when this browser accepts its
    NAME as a CSS property carrying that value, so `class`, `id` and `d` never reach the colour
    test at all. The second half of that claim is measured here too — a draft whose SVG carries
    only non-colour attributes stays green.
    """
    pytest.importorskip("playwright")
    svg = ('<svg width="20" height="20" viewBox="0 0 20 20" class="mark">'
           '<rect x="0" y="0" width="20" height="20" %s/></svg>')
    stage(tmp_path, CLEAN.replace("</section>", (svg % 'fill="#ff0000"') + "</section>"))
    done = render(tmp_path)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert done.returncode == 3, text
    assert "fill attribute" in text, text

    stage(tmp_path, CLEAN.replace("</section>", (svg % 'fill="var(--brand)"') + "</section>"))
    quiet = render(tmp_path)
    _needs_a_browser(quiet)
    assert quiet.returncode == 0, (quiet.stdout + quiet.stderr)


def test_a_draft_that_declares_no_view_says_so_instead_of_saying_nothing(tmp_path):
    """`N8`: silence and a pass looked the same for the ranking rule.

    A Phase-1 tile sheet legitimately declares no view, so this must not be a finding — but a
    per-view mockup that forgot the attribute got exactly the same wordless rc 0, and the designer
    had no way to tell "judged and fine" from "not judged at all".
    """
    pytest.importorskip("playwright")
    stage(tmp_path, CLEAN.replace(' data-view="uebersicht"', ""))
    done = render(tmp_path)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert done.returncode == 0, text
    assert "the one-primary-goal rule judged nothing here" in text, text


def test_an_unreadable_sheet_does_not_buy_a_draft_out_of_the_focus_rule_finding(tmp_path):
    """The counter-case of `H145`'s fix: suppression was global, and that was a way past the rule.

    Measured by a verifier on the first fix: a draft with NO `:focus-visible` rule anywhere plus one
    linked, entirely irrelevant `print.css` came back rc 0 — the finding was dropped because SOME
    sheet was unreadable, not because the rule was found. What an unreadable sheet takes away is the
    word "at all", not the finding, so the sentence is qualified and the run still answers 3.
    """
    pytest.importorskip("playwright")
    body = CLEAN.replace("<style>", '<link rel="stylesheet" href="print.css"><style>')
    body = body.replace(FOCUS_RULE, "")
    stage(tmp_path, body)
    with open(os.path.join(str(tmp_path), "project_memory", "staging", TASK, "print.css"),
              "w", encoding="utf-8") as handle:
        handle.write("@media print { .only-print { display: block; } }\n")
    done = render(tmp_path)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert done.returncode == 3, text
    assert "no :focus-visible rule in the sheets this run could read" in text, text
    assert "sheet(s) unreadable" in text, text


@pytest.mark.parametrize("rule,why", [
    ('content: "Neu"; color: var(--faint); display: none;', "display: none"),
    ('content: "Neu"; color: var(--faint); visibility: hidden;', "visibility: hidden"),
    ('content: "Neu"; color: var(--faint); opacity: 0;', "opacity: 0"),
    ('content: ""; color: var(--faint);', "an empty content string"),
])
def test_a_pseudo_element_nobody_can_see_is_not_judged_either(tmp_path, rule, why):
    """The inversion `H146`'s fix opened: `rendered()` was asked about the ELEMENT, never the pseudo.

    Measured by a verifier: `::before { display: none }` on a perfectly visible card produced
    "contrast 1.00:1 ... at opacity 0" and a sample of '""' — findings about a box that is not on
    screen, which is exactly what
    `tools/test_design_conformance.py::test_text_nobody_can_see_is_not_judged_for_contrast`
    forbids one branch up. `checkVisibility` does not reach a pseudo-element, so its own three
    properties are asked instead, and an empty content string generates a box and no text.
    """
    pytest.importorskip("playwright")
    body = CLEAN.replace(":root { --bg:#ffffff;", ":root { --faint:#bbbbbb; --bg:#ffffff;")
    body = body.replace("</style>", ".card::before { %s }\n</style>" % rule)
    stage(tmp_path, body)
    done = render(tmp_path)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert done.returncode == 0, (why, text)
    assert "::before" not in text, (why, text)


def test_a_pseudo_element_inside_a_hidden_element_stays_unjudged(tmp_path):
    """The other half of the same boundary: the ELEMENT is invisible, the pseudo inherits that."""
    pytest.importorskip("playwright")
    body = CLEAN.replace(":root { --bg:#ffffff;", ":root { --faint:#bbbbbb; --bg:#ffffff;")
    body = body.replace("</style>",
                        '.ghost { display: none; } '
                        '.ghost::before { content: "Neu"; color: var(--faint); }\n</style>')
    body = body.replace("</section>", '<div class="ghost"></div></section>')
    stage(tmp_path, body)
    done = render(tmp_path)
    _needs_a_browser(done)
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_finding_names_the_signal_that_made_an_element_mouse_only(tmp_path):
    """`N-1`: two signals decide, and the sentence used to name only one of them.

    An element with an `onclick` and the default cursor was reported as "clickable for the mouse
    (cursor: pointer)" — a property it did not have, which sends the reader to look for a CSS rule
    that is not there.
    """
    pytest.importorskip("playwright")
    stage(tmp_path, CLEAN.replace('<div class="card">',
                                  '<div class="card" onclick="void 0">'))
    done = render(tmp_path)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert done.returncode == 3, text
    assert "an onclick attribute" in text, text
    assert "cursor: pointer" not in text, text


# The rules an `@import` pulls in, as a data: URL — the ONE spelling of an import whose rules this
# document may read under `file://`. A same-directory `theme.css` throws `SecurityError` there
# (measured), which is the other direction and the other test below.
IMPORTED_CSS = "a:focus-visible{outline:3px solid %230b5fff}.imported{color:%23ff00ff}"


def test_an_imported_sheet_this_document_may_not_read_is_recorded_like_any_other(tmp_path):
    """`@import` hangs under `styleSheet`, not under `cssRules` — so the walk went straight past it.

    Measured by a verifier: an inline `@import url("theme.css")` carrying the draft's only
    `:focus-visible` rule and a colour literal produced neither finding. The worse half is the
    second one: the IMPORTING sheet reads fine, so nothing landed in `unreadable_sheets` and the
    absence claim came out UNQUALIFIED — the draft was told it has no focus rule anywhere, while the
    rule sat one sheet down and in effect.
    """
    pytest.importorskip("playwright")
    body = CLEAN.replace("<style>", '<style>\n@import url("theme.css");')
    body = body.replace(FOCUS_RULE, "")
    stage(tmp_path, body)
    with open(os.path.join(str(tmp_path), "project_memory", "staging", TASK, "theme.css"),
              "w", encoding="utf-8") as handle:
        handle.write("a:focus-visible { outline: 3px solid #0b5fff; }\n"
                     ".imported { color: #ff00ff; }\n")
    done = render(tmp_path)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert done.returncode == 3, text
    assert "sheet(s) unreadable" in text, (
        "the absence claim came out unqualified although a sheet went unread: %s" % text)
    assert "theme.css" in text, ("the unreadable import is not named anywhere: %s" % text)


def test_an_imported_sheet_that_can_be_read_is_read(tmp_path):
    """The other direction: when the import IS readable, its rules count — for and against the draft.

    Without the fix this went wrong twice in the same run: the `:focus-visible` rule inside the
    import was not seen (so the draft was accused of having none) and the colour literal inside it
    was not seen either (so a token violation passed). Both are asserted here.
    """
    pytest.importorskip("playwright")
    body = CLEAN.replace("<style>", '<style>\n@import url("data:text/css,%s");' % IMPORTED_CSS)
    body = body.replace(FOCUS_RULE, "")
    stage(tmp_path, body)
    done = render(tmp_path)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert "focus-visible rule" not in text, (
        "the draft was accused of having no focus rule while the import carries one: %s" % text)
    assert "sheet(s) unreadable" not in text, ("a readable import was recorded as unreadable: %s"
                                               % text)
    assert done.returncode == 3, text
    assert "colour literal outside the token sheet" in text, (
        "the colour literal inside the readable import was not found: %s" % text)


def test_the_text_of_a_placeholder_is_text(tmp_path):
    """`::placeholder` carries the classic contrast defect of a mockup, and `content` never sees it.

    Its text is the ATTRIBUTE — `content` computes to `normal` for it (measured) — so the rule that
    reads generated content skipped it, and a placeholder in the muted token came back rc 0. The
    counter-direction is measured in the same test: an input WITHOUT the attribute has no
    placeholder text and must stay quiet, which is also what keeps this off every other element
    (`getComputedStyle` answers for a pseudo-element the element does not have).
    """
    pytest.importorskip("playwright")
    body = CLEAN.replace(":root { --bg:#ffffff;", ":root { --faint:#bbbbbb; --bg:#ffffff;")
    body = body.replace("</style>", ".inp::placeholder { color: var(--faint); }\n</style>")
    stage(tmp_path, body.replace("</section>",
                                 '<input class="inp" placeholder="Suchbegriff"></section>'))
    done = render(tmp_path)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert done.returncode == 3, text
    assert "::placeholder" in text, text

    stage(tmp_path, body.replace("</section>", '<input class="inp"></section>'))
    quiet = render(tmp_path)
    _needs_a_browser(quiet)
    assert quiet.returncode == 0, (quiet.stdout + quiet.stderr)


def test_the_bullet_of_a_list_is_text(tmp_path):
    """`::marker` is drawn from the LIST STYLE, not from `content` (which computes to `normal`).

    A bullet in the muted token is as unreadable as the line beside it, and it was rc 0. The
    counter-direction: a list whose marker is switched off renders none, and nothing is judged.
    """
    pytest.importorskip("playwright")
    body = CLEAN.replace(":root { --bg:#ffffff;", ":root { --faint:#bbbbbb; --bg:#ffffff;")
    body = body.replace("</style>", "li::marker { color: var(--faint); }\n</style>")
    stage(tmp_path, body.replace("</section>", "<ul><li>Eintrag</li></ul></section>"))
    done = render(tmp_path)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert done.returncode == 3, text
    assert "::marker" in text, text

    stage(tmp_path, body.replace("</style>", "li { list-style-type: none; }\n</style>")
          .replace("</section>", "<ul><li>Eintrag</li></ul></section>"))
    quiet = render(tmp_path)
    _needs_a_browser(quiet)
    assert quiet.returncode == 0, (quiet.stdout + quiet.stderr)


def _render_module():
    """The shipped renderer as a module — its own constants, so no spelling is repeated here."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("kit_design_render_under_test", RENDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _skill_section(text, needle):
    """The markdown section whose `## ` heading contains `needle` — heading to next `## `.

    STRUCTURAL, and that is the whole point of it. The predecessor of this reader took a 4000
    character window around the first occurrence of `data-view`, which is not a section at all: a
    word could satisfy it from a neighbouring paragraph, and a section near the top of the file
    produced a NEGATIVE start index and therefore an empty slice — red for a reason that has
    nothing to do with the text. Both are measured in
    `tools/test_design_conformance.py::test_the_section_reader_cuts_at_headings_and_not_at_a_character_count`.
    """
    heads = [m for m in re.finditer(r"(?m)^##\s+(?P<title>.*)$", text)]
    for index, head in enumerate(heads):
        if needle.lower() not in head.group("title").lower():
            continue
        stop = heads[index + 1].start() if index + 1 < len(heads) else len(text)
        return text[head.start():stop]
    return None


def test_the_section_reader_cuts_at_headings_and_not_at_a_character_count():
    """The floor under the reader above, in both directions the window version got wrong."""
    text = "## Ranking: the one\nbody A\n\n## Next\nbody B\n"
    assert _skill_section(text, "ranking").strip().endswith("body A"), "it must stop at the next ##"
    assert "body A" in _skill_section(text, "ranking"), "a section at offset 0 must not come back empty"
    assert _skill_section("## Next\nbody B\n", "ranking") is None
    assert _skill_section("## Only\nbody\n", "only").strip().endswith("body"), "the last section runs to EOF"


def test_the_skill_teaches_the_ranking_PROCEDURE_the_check_demands():
    """FR-0078's second half: a PROCEDURE in the skill, not an adjective — measured, not read.

    The renderer refuses a declared view that names none or two primary actions, and its refusal
    tells the designer to write ONE sentence, quoting `RANKING_SENTENCE_TEMPLATE`. That template is
    the procedure's first step; an adjective ("make sure the view is clear") is what stands there
    when the step is gone. So this couples the skill's own ranking SECTION — cut at its heading, not
    windowed — to that template read out of the module, and to the two attributes.

    MEASURED RED on the shape a verifier planted: replacing step 1 with an adjective while leaving
    the two attribute steps in place. The predecessor of this test passed that mutation, because it
    searched for the words "sentence" and "first" in 4000 characters around `data-view` and both
    survived elsewhere — "first" inside the adjective sentence itself. A template with two named
    blanks cannot survive its own deletion.

    WHAT THIS CANNOT SEE, and it is the boundary of every coupling of a text to a constant: the
    template being REVOKED beside itself. A section that quotes the template and then writes "this
    is only an example, judge the view instead" carries the string and teaches the adjective, and
    this stays green — measured by a verifier. Presence is mechanical; meaning is not, and a check
    that pretended otherwise would be the reassuring sentence this repo keeps finding a defect
    behind. What answers for it is a reader of the skill, not this test.
    """
    module = _render_module()
    with open(DESIGNER_SKILL, encoding="utf-8") as handle:
        skill = handle.read()
    for attribute in (module.VIEW_ATTR, module.PRIMARY_ACTION_ATTR):
        assert attribute in skill, (
            "the product-designer skill never names %r, so the procedure it teaches and the check "
            "that reads it are two different things" % attribute)
    section = _skill_section(skill, "ranking")
    assert section, "the product-designer skill has no `## Ranking…` section any more"
    assert module.RANKING_SENTENCE_TEMPLATE in section, (
        "the skill's ranking section does not carry the sentence template the renderer's own "
        "refusal quotes (%r). Without it the section states a property to achieve and not a step "
        "to perform — which is the adjective FR-0078 exists to remove."
        % module.RANKING_SENTENCE_TEMPLATE)
    for attribute in (module.VIEW_ATTR, module.PRIMARY_ACTION_ATTR):
        assert attribute in section, (
            "%r is named somewhere in the skill but not in its ranking section — the step that "
            "marks it is what makes the sentence checkable" % attribute)
    assert os.path.basename(RENDER) in section, (
        "the ranking section never names the command that reads the mark, so the designer is told "
        "to write an attribute and never told what reads it")


def test_the_refusal_quotes_the_same_template_the_skill_teaches(tmp_path):
    """One template, two readers — the refusal a designer meets and the step they were taught.

    Read off the finding the shipped script really PRINTS on a planted two-goal view, not off its
    source: a refusal that paraphrased the template would send the designer to write a sentence
    that is not the one the skill's step names, and nothing else here would notice.
    """
    pytest.importorskip("playwright")
    module = _render_module()
    stage(tmp_path, CLEAN.replace(HELP_LINK, '<a href="#hilfe" data-primary-action>Hilfe</a>'))
    done = render(tmp_path)
    _needs_a_browser(done)
    text = done.stdout + done.stderr
    assert done.returncode == 3, text
    assert module.RANKING_SENTENCE_TEMPLATE in text, (module.RANKING_SENTENCE_TEMPLATE, text)


def test_the_numbers_the_check_uses_are_the_wcag_ones_and_live_in_one_place():
    """The contrast floors — in the module, in the page probe, and in the skill that teaches them.

    A ratio is a number, and a number in a second place outlives the first (SR-0008). Three places
    could hold one here, and each is checked against the module's constants rather than against a
    literal in this file: the probe must carry NO number of its own, and the product-designer skill
    must teach the same two ratios it does. The skill's line is not merged into the code — a
    threshold a machine applies and a habit a role is taught are different things — so it is
    coupled, and this is the coupling.
    """
    module = _render_module()
    assert (module.CONTRAST_BODY_MIN, module.CONTRAST_LARGE_MIN) == (4.5, 3.0)
    assert (module.LARGE_TEXT_PX, module.LARGE_BOLD_TEXT_PX, module.BOLD_WEIGHT) == (24.0, 18.66, 700)
    config = module._probe_config()
    assert config["bodyMin"] == module.CONTRAST_BODY_MIN
    assert config["largeMin"] == module.CONTRAST_LARGE_MIN
    for number in ("4.5", "3.0", "18.66"):
        assert number not in module._PAGE_PROBE, (
            "%s stands inside the page probe as well as in a constant — one of the two will be "
            "changed alone" % number)
    with open(DESIGNER_SKILL, encoding="utf-8") as handle:
        skill = handle.read()
    line = [one for one in skill.splitlines() if "Contrast is three numbers" in one]
    assert len(line) == 1, "the designer skill no longer states the contrast ratios in one line"
    taught = {float(one) for one in re.findall(r"(\d+(?:\.\d+)?):1", skill[skill.index(line[0]):
                                                                          skill.index(line[0]) + 400])}
    assert taught == {module.CONTRAST_BODY_MIN, module.CONTRAST_LARGE_MIN}, (
        "the skill teaches %s and the check applies %s — the same number in two places, already "
        "apart" % (sorted(taught), sorted({module.CONTRAST_BODY_MIN, module.CONTRAST_LARGE_MIN})))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
