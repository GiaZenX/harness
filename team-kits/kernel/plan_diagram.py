"""The implementation plan and the mindmap, generated from the items (FR-0080, DEC-0065 (2)).

WHAT A GENERATED `.drawio.svg` IS HERE (`docs/research/2026-07-27-plan-als-diagramm.md`, section 1):
a valid SVG whose root carries the whole draw.io document, uncompressed, in its `content`
attribute -- so draw.io and the VS Code extension open it as an editable diagram while every
browser renders the SVG half. BOTH halves come from ONE layout pass in this file: the geometry is a
grid computed by multiplication, with no layout library, no browser and no JVM, because this runs
at the end of every state write beside the board.

THE FILES ARE A PURE FUNCTION OF THE ENTRIES. No clock, no random id, no reading of anything the
caller did not hand over -- which is what lets `is_pristine` re-render and compare bytes, and what
`test_plan_diagram.test_the_diagram_is_a_pure_function_of_the_entries` measures over the module's
own syntax tree as well as over two runs. The root also carries `data-source-digest`, a sha256 over
the canonical entry list, so the two failure modes are told apart rather than lumped together: same
digest and different bytes means somebody edited the file; a different digest means the state moved
on and the file is stale.

WHY THE TWO PICTURES ARE THESE TWO. The plan answers "which steps are needed and where do we
stand": one row per root, three lanes, every item under the root in the lane its own status puts it
in (`board.lane`, the same derivation the board's third number uses, so a card and a cell can never
disagree). The mindmap answers "what belongs to what" -- the view in which a misunderstanding shows
up, which is what the wishlist asked for it.

WHAT THEY DO NOT CARRY, said here because a picture cannot say it itself:
  * NO PROJECT NAME. FR-0075's rule for this generation is no new writer and no new field, and the
    kernel exposes no project name to this layer; inventing a reader for one would be exactly that
    new coupling. The centre of the mindmap is therefore the backlog itself, counted.
  * NO ARCHIVE. Archived items are not on the board and are not here either, for the board's own
    reason -- both pictures show `active` state.
  * A BOUND ON SIZE. A project with thousands of items would otherwise produce one file with
    thousands of cells at the end of every state write. The bound is `CELL_BUDGET`, and what falls
    outside it is SAID ON THE IMAGE rather than dropped in silence
    (`test_plan_diagram.test_a_project_over_the_budget_says_what_it_left_out`).

WHO REGENERATES THEM. The same trigger as the board -- `state._regenerate_index_locked` ->
`state._write_board` -- is where they belong (DEC-0065 (2)), and `state.py` is not this stream's
file. Until that one call line is applied, THIS MODULE IS THE ONLY WAY THE FILES ARE PRODUCED and
nothing anywhere claims otherwise; the test that will carry the claim afterwards is
`test_board.test_no_kernel_writer_of_a_rendered_file_leaves_the_board_behind`, extended by these
two names. Between two state writes nobody notices a hand edit either -- `is_pristine` runs in the
tests and in no gate; that is H127 in `docs/POST_V2_WISHLIST.md`, with what bounds it.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import xml.etree.ElementTree as ET

from . import backlog_tree, board

# What the two files are called under `generated/`, beside `board.FILENAME`. The suffix is the one
# the kits already use for wireframes and architecture diagrams (FR-0080: the format is in use, the
# wish extends it), so the same tools open them.
PLAN_FILENAME = "plan.drawio.svg"
MINDMAP_FILENAME = "mindmap.drawio.svg"

# THE SAME TWO NAMES, ONCE, for the readers that want the names WITHOUT paying for the pictures:
# `kernel.cli` prints what `generate-index` wrote, and rendering both files to learn their names
# would be the second cost of an announcement. `render_all` is built from this tuple, so a third
# picture cannot reach `generated/` unannounced.
FILENAMES = (PLAN_FILENAME, MINDMAP_FILENAME)

# What produced the file, on the file. Not a version and not a date -- a date would make the bytes
# depend on the clock, which is the property this module is built on.
GENERATOR = "kernel.plan_diagram"

# The lanes, in the order a plan is read, and in the words the board already uses for them
# (`board.LANE_WORDS`): one vocabulary, so a cell and a card cannot name one lane two things.
LANES = (board.NEW, board.FLIGHT, board.DONE)

# THE WHOLE PALETTE. Every colour in this file is one of these, which is what
# `test_plan_diagram.test_no_colour_outside_the_named_palette` reads out of the syntax tree -- a
# literal added at a call site is the way a diagram grows a colour nobody chose.
INK = "#16181c"
PAPER = "#ffffff"
RULE = "#c9ced6"
LANE_FILL = {board.NEW: "#eceef1", board.FLIGHT: "#dfe6f5", board.DONE: "#d9ead3"}

# A font STACK rather than one family: the file is opened in a browser and in draw.io, on machines
# this generator knows nothing about.
FONT = "Segoe UI, system-ui, sans-serif"

# How wide one character is, as a share of the font size. SVG `<text>` does not wrap and does not
# clip, so a label longer than its box simply runs over the next one -- which is the same defect the
# board's own layout round measured, one format along. Every label is therefore cut to what its BOX
# holds (`_fits`), and this is the only number that turns a box width into a character budget. It is
# measured on the rendered file rather than guessed (the figure and the sample are in the round's
# report) and it is deliberately a little generous: over-cutting costs a word, under-cutting costs
# the neighbouring cell.
CHAR_WIDTH = 0.62

# How many item cells ONE file may carry. A bound has to exist because this runs at the end of every
# state write over the whole active store, and what it costs is the caller's latency; the number is
# the one measured for TSK-0115 against this repo's own state (the figure is in the round's report,
# not repeated here). Over the budget the picture SAYS what it left out -- see the module docstring.
CELL_BUDGET = 240


def canonical(entries) -> str:
    """What the diagrams are a function of: id, type, status, title and parents, sorted.

    The digest is over THIS and not over the rendered bytes, because it has to answer a different
    question: "was this file rendered from the state the store holds now?". Bytes answer "has
    anybody touched the file". Together they separate a hand edit from a stale file, which is the
    whole of `is_pristine`.
    """
    rows = []
    for row, body in entries:
        node = backlog_tree.Node(row, body)
        rows.append([str(row.get("id") or ""), str(row.get("type") or ""),
                     str(row.get("status") or ""), str(row.get("title") or ""),
                     backlog_tree.parents_of(node)])
    return json.dumps(sorted(rows), ensure_ascii=False, separators=(",", ":"))


def digest_of(entries) -> str:
    """The sha256 over `canonical`, with the encoding tolerance the state layer already uses.

    `errors="replace"` and not the default, for `state._write_text_atomic`'s measured reason: a
    YAML file can hold a lone surrogate, and `str.encode` refuses one. Without this the DIGEST --
    computed before any label is clipped -- raised out of the renderer, i.e. out of the state write
    it will run inside once the trigger seam lands. What it costs is stated rather than hidden: two
    items differing only in which unencodable half they carry hash the same. That is a shape no
    well-formed store holds, and the digest answers "has the state moved on", not "are these bytes
    authentic". `test_plan_diagram.test_a_control_character_in_a_title_cannot_break_the_model`.
    """
    return hashlib.sha256(canonical(entries).encode("utf-8", "replace")).hexdigest()


# What XML 1.0 does not allow inside a document, as the negation of what it does (§2.2) -- the C0
# controls except tab/newline/return, and the surrogate halves a YAML file can carry. `html.escape`
# does NOT cover these: it answers `&<>"`, which is a different question, so a title beginning with
# a NUL byte produced two files that were not well-formed XML at all -- and `is_pristine` still
# called them pristine, because equal bytes is what pristine means. Measured on a title
# `NUL, SOH, " NUL first"`: both files unparseable, both reported clean. Every label goes through
# `_clip`, so this is the one door.
# `test_plan_diagram.test_a_control_character_in_a_title_cannot_break_the_model`.
_XML_FORBIDDEN = re.compile(
    "[^%s%s%s%s-%s%s-%s%s-%s]" % (chr(0x09), chr(0x0A), chr(0x0D),
                                  chr(0x20), chr(0xD7FF), chr(0xE000), chr(0xFFFD),
                                  chr(0x10000), chr(0x10FFFF)))

# What stands where one of them stood: the replacement character, so the label SAYS that
# something unreadable was there instead of quietly closing the gap.
_REPLACEMENT = chr(0xFFFD)


def _clip(text, limit: int) -> str:
    text = " ".join(_XML_FORBIDDEN.sub(_REPLACEMENT, str(text or "")).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _fits(width: int, small: bool = True) -> int:
    """How many characters a box of `width` holds at that cell's font size -- see `CHAR_WIDTH`.

    The box's own padding (6 px on each side, the offset `_Sheet.box` draws the text at) is taken
    off first, and the result never falls below a handful of characters: a box too narrow for a
    label is a layout to fix, not a reason to render an ellipsis on its own.
    """
    return max(int((width - 12) / (CHAR_WIDTH * (10 if small else 12))), 8)


def _lane_label(node, limit: int, prefix: str = "", suffix: str = "") -> str:
    """One cell's text: what the item is, and -- as a WORD -- which lane it stands in.

    The fill already says the lane, and a fill alone is a colour-only status (WCAG 1.4.1); the
    research note names that as a gate on this format. So the word is on the cell.
    `test_plan_diagram.test_status_is_never_carried_by_colour_alone`.

    THE LANE WORD IS SPENT FIRST AND THE TITLE TAKES WHAT IS LEFT. Composing the line and clipping
    it afterwards puts the word at the end of the budget, where a long title eats it -- which is
    the colour-only cell coming back through the display bound rather than through the palette.
    """
    key = board.lane(node.item_type, node.row.get("status"))
    word = board.LANE_WORDS.get(key, "")
    face = board.face_title(node.row, node.body) or backlog_tree.label(node.item_type)
    tail = "%s%s" % (suffix, (" — " + word) if word else "")
    return _clip("%s%s %s" % (prefix, node.item_id, face), max(limit - len(tail), 8)) + tail


class _Sheet:
    """The SVG elements and the matching draw.io cells, collected in ONE pass.

    Two outputs from one walk rather than two renderers: a geometry the browser draws and a model
    draw.io edits that came from different code would drift the first time either changed.
    """

    def __init__(self):
        self.svg, self.cells, self.serial = [], [], 1

    def _next(self) -> str:
        self.serial += 1
        return "c%d" % self.serial

    def box(self, x, y, width, height, text, fill=PAPER, stroke=INK, bold=False, small=False):
        cell_id = self._next()
        size = 10 if small else 12
        self.svg.append('<rect x="%d" y="%d" width="%d" height="%d" rx="2" fill="%s" '
                        'stroke="%s"/>' % (x, y, width, height, fill, stroke))
        self.svg.append('<text x="%d" y="%d" font-family="%s" font-size="%d"%s fill="%s">%s</text>'
                        % (x + 6, y + height // 2 + size // 3, FONT, size,
                           ' font-weight="600"' if bold else "", INK, html.escape(text)))
        style = ("rounded=1;whiteSpace=wrap;html=1;fillColor=%s;strokeColor=%s;fontSize=%d;%s"
                 % (fill, stroke, size, "fontStyle=1;" if bold else ""))
        self.cells.append('<mxCell id="%s" value="%s" style="%s" vertex="1" parent="1">'
                          '<mxGeometry x="%d" y="%d" width="%d" height="%d" as="geometry"/>'
                          "</mxCell>"
                          % (cell_id, html.escape(text, quote=True), style, x, y, width, height))
        return cell_id

    def line(self, x1, y1, x2, y2, source, target):
        self.svg.append('<path d="M%d %d L%d %d L%d %d" fill="none" stroke="%s"/>'
                        % (x1, y1, x1, y2, x2, y2, RULE))
        self.cells.append('<mxCell id="%s" style="edgeStyle=orthogonalEdgeStyle;endArrow=none;'
                          'strokeColor=%s;" edge="1" parent="1" source="%s" target="%s">'
                          '<mxGeometry relative="1" as="geometry"/></mxCell>'
                          % (self._next(), RULE, source, target))

    def text(self, x, y, text, size=13, bold=True):
        self.svg.append('<text x="%d" y="%d" font-family="%s" font-size="%d"%s fill="%s">%s</text>'
                        % (x, y, FONT, size, ' font-weight="600"' if bold else "", INK,
                           html.escape(text)))
        self.cells.append('<mxCell id="%s" value="%s" style="text;html=1;fontSize=%d;%s" '
                          'vertex="1" parent="1">'
                          '<mxGeometry x="%d" y="%d" width="300" height="20" as="geometry"/>'
                          "</mxCell>"
                          % (self._next(), html.escape(text, quote=True), size,
                             "fontStyle=1;" if bold else "", x, y - 14))


def _wrap(sheet, width, height, name, digest) -> str:
    """The `.drawio.svg`: the SVG geometry plus the whole mxfile in `content`, both from `sheet`."""
    model = ('<mxfile host="%s" agent="%s"><diagram id="d1" name="%s">'
             '<mxGraphModel dx="0" dy="0" grid="1" gridSize="10" guides="1" page="1" '
             'pageWidth="%d" pageHeight="%d"><root><mxCell id="0"/><mxCell id="1" parent="0"/>%s'
             "</root></mxGraphModel></diagram></mxfile>"
             % (GENERATOR, GENERATOR, html.escape(name, quote=True), width, height,
                "".join(sheet.cells)))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d" data-generator="%s" data-source-digest="%s" content="%s">\n'
            '<rect width="%d" height="%d" fill="%s"/>\n%s\n</svg>\n'
            % (width, height, width, height, GENERATOR, digest, html.escape(model, quote=True),
               width, height, PAPER, "\n".join(sheet.svg)))


def _outline(root, view) -> list:
    """[(node, the area of the group it stands in), ...] under one root, in reading order.

    ONE WALKER for both pictures, so the plan and the mindmap can never hold different sets of
    items. The order is `Node.grouped_children`'s -- the view's type order, then areas, exactly the
    tree the board draws -- so the two answers to "what hangs under this root" are the same answer.

    ITERATIVE, WITH AN EXPLICIT STACK, for `board._branches`' reason: the tree's depth is the
    items' own doing and this runs inside a state write, where a RecursionError would be caught and
    turn into a silently stale file.
    """
    out, stack = [], [(root, "")]
    while stack:
        node, area = stack.pop()
        if node is not root:
            out.append((node, area))
        follow = []
        for _item_type, group_area, children in node.grouped_children(view):
            follow.extend((child, group_area) for child in children)
        stack.extend(reversed(follow))
    return out


def _budget(rows: list) -> tuple:
    """(what fits in one file, the sentence naming what did not) -- see `CELL_BUDGET`."""
    if len(rows) <= CELL_BUDGET:
        return rows, ""
    return rows[:CELL_BUDGET], ("%d of %d items shown — the board carries all of them"
                                % (CELL_BUDGET, len(rows)))


def plan(entries) -> str:
    """One row per root, three lanes, every item under the root in the lane its status puts it in.

    The root's own cell carries its lane as a word too: it is an item with a state like any other,
    and a row whose header was the one uncoloured, unworded cell read as "the root has no state".
    """
    system = backlog_tree.arrange(backlog_tree.VIEWS[-1], entries)
    sheet = _Sheet()
    column, box_h, gap, left = 360, 22, 4, 360
    width = left + 3 * (column + 20) + 20
    y = 50
    sheet.text(20, 30, "Implementation plan", size=16)
    for index, key in enumerate(LANES):
        sheet.box(left + index * (column + 20), y, column, box_h, board.LANE_WORDS[key],
                  fill=LANE_FILL[key], bold=True)
    y += box_h + 16
    shown, left_out = _budget([(root, node) for root in system.roots
                               for node, _area in _outline(root, backlog_tree.VIEWS[-1])])
    per_root: dict = {}
    for root, node in shown:
        per_root.setdefault(root.item_id, []).append(node)
    for root in system.roots:
        by_lane = {key: [] for key in LANES}
        for node in per_root.get(root.item_id, []):
            key = board.lane(node.item_type, node.row.get("status"))
            if key in by_lane:
                by_lane[key].append(node)
        rows = max(1, max(len(nodes) for nodes in by_lane.values()))
        block = rows * (box_h + gap)
        root_lane = board.lane(root.item_type, root.row.get("status"))
        root_id = sheet.box(20, y, left - 40, block,
                            _lane_label(root, _fits(left - 40, small=False)),
                            fill=LANE_FILL.get(root_lane, PAPER), bold=True)
        for index, key in enumerate(LANES):
            x = left + index * (column + 20)
            for offset, node in enumerate(by_lane[key]):
                cell = sheet.box(x, y + offset * (box_h + gap), column, box_h,
                                 _lane_label(node, _fits(column)),
                                 fill=LANE_FILL[key], stroke=RULE, small=True)
                if not offset:
                    sheet.line(left - 20, y + box_h // 2, x, y + box_h // 2, root_id, cell)
        if not any(by_lane.values()):
            sheet.box(left, y, column, box_h, "nothing under this root yet", fill=PAPER,
                      stroke=RULE, small=True)
        y += block + 14
    if not system.roots:
        sheet.text(20, y + 10,
                   "no root item yet — the plan starts with the first product requirement",
                   size=12, bold=False)
        y += 40
    if left_out:
        sheet.text(20, y + 10, left_out, size=12, bold=False)
        y += 30
    return _wrap(sheet, width, y + 20, "Implementation plan", digest_of(entries))


def mindmap(entries) -> str:
    """The backlog, its roots, and everything under them as an indented outline to the right.

    THE COLUMN IS THE ITEM'S DEPTH IN THE TREE, so "what belongs to what" is the shape of the
    picture rather than a caption on it, and the ORDER inside a level is `Node.grouped_children`'s
    -- the view's type order, then the outline areas FR-0017 asks for, which is the same order the
    board's tree view draws. An area, where a project keeps one, stands on the cell it groups.

    NO SEPARATE HEADING CELLS for the type groups: a heading cell carries no item, so it would need
    a fill of its own, and the only fills this file has are the three lanes -- a heading wearing a
    lane colour tells a reader that a group is "planned". The type is on every cell instead, in
    plain language, which is where a reader looks anyway.
    """
    view = backlog_tree.VIEWS[-1]
    system = backlog_tree.arrange(view, entries)
    sheet = _Sheet()
    box_h, gap, step, box_w, x0 = 22, 6, 400, 380, 20
    rows = [(root, node, area) for root in system.roots
            for node, area in _outline(root, view)]
    shown, left_out = _budget(rows)
    per_root: dict = {}
    for root, node, area in shown:
        per_root.setdefault(root.item_id, []).append((node, area))
    sheet.text(x0, 30, "Mindmap", size=16)
    y, widest = 60, x0 + box_w
    centre = sheet.box(x0, y, box_w, box_h * 2,
                       _clip("backlog — %d item(s) under %d root(s)"
                             % (len(rows), len(system.roots)), _fits(box_w, small=False)),
                       bold=True)
    y += box_h * 2 + gap
    for root in system.roots:
        root_lane = board.lane(root.item_type, root.row.get("status"))
        placed = {root.item_id: sheet.box(
            x0 + step, y, box_w, box_h, _lane_label(root, _fits(box_w, small=False)),
            fill=LANE_FILL.get(root_lane, PAPER), bold=True)}
        sheet.line(x0 + box_w, y - gap, x0 + step, y + box_h // 2, centre, placed[root.item_id])
        widest = max(widest, x0 + step + box_w)
        y += box_h + gap
        for node, area in per_root.get(root.item_id, []):
            x = x0 + (node.depth + 1) * step
            key = board.lane(node.item_type, node.row.get("status"))
            text = _lane_label(node, _fits(box_w),
                               prefix=backlog_tree.label(node.item_type) + " ",
                               suffix=(" [%s]" % area) if area else "")
            cell = sheet.box(x, y, box_w, box_h, text, fill=LANE_FILL.get(key, PAPER),
                             stroke=RULE, small=True)
            parent = node.parent.item_id if node.parent else root.item_id
            if parent in placed:
                sheet.line(x - step + box_w, y - gap, x, y + box_h // 2, placed[parent], cell)
            placed[node.item_id] = cell
            widest = max(widest, x + box_w)
            y += box_h + gap
        y += gap
    if not system.roots:
        sheet.text(x0 + step, y, "no root item yet — nothing to hang a mindmap from", size=12,
                   bold=False)
        y += 30
    if left_out:
        sheet.text(x0, y + 10, left_out, size=12, bold=False)
        y += 30
    return _wrap(sheet, widest + 20, y + 20, "Mindmap", digest_of(entries))


def render_all(entries) -> list:
    """[(filename, text), ...] -- both pictures from one reading of the entries.

    The caller writes them; this returns text. That is what keeps the module a pure function and
    what lets `is_pristine` compare a file on disk with a fresh render of the same entries.
    """
    return [(name, renderer(entries))
            for name, renderer in zip(FILENAMES, (plan, mindmap))]


def verdicts(directory: str, entries) -> list:
    """[(filename, verdict, reason), ...] for the diagrams that ARE on disk in `directory`.

    THE CALLER A VALIDATOR CAN AFFORD, and that is the whole reason it exists beside
    `is_pristine`: the judgement needs a fresh render, and asking per file rendered the same
    entries once per picture. One render here, both answers from it. A file that is not there is
    not judged -- a project whose state has never been written has no diagram to lose, and a
    finding about one would be about the directory rather than about anybody's work.

    This is the reader `report.validate_state` uses, which is the half of BUG-0211 that says a
    hand edit is SEEN; the other half -- that it is overwritten at the next state write -- is
    `state._write_board`.
    `tools/test_report.py::test_a_hand_edited_diagram_is_reported_and_a_missing_one_is_not`
    """
    fresh = dict(render_all(entries))
    found = []
    for name in FILENAMES:
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        verdict, reason = is_pristine(path, entries, fresh)
        found.append((name, verdict, reason))
    return found


def is_pristine(path: str, entries, fresh_by_name: dict = None) -> tuple:
    """(verdict, reason) for one generated diagram: pristine, hand-edited, stale or foreign.

    THREE OUTCOMES AND NOT TWO, because the two failures need different answers. A HAND EDIT is
    work somebody will lose at the next state write and has to be told about; a STALE file is
    nobody's mistake and disappears by itself. The digest on the root separates them: it is over the
    state the file was rendered FROM, so an equal digest with unequal bytes can only be an edit,
    and an unequal digest can only be a state that has moved on.
    `test_plan_diagram.test_a_hand_edit_is_told_from_a_stale_file`.
    """
    if fresh_by_name is None:
        fresh_by_name = dict(render_all(entries))
    fresh = fresh_by_name.get(os.path.basename(path))
    if fresh is None:
        return "foreign", "no diagram of this name is generated here"
    try:
        with open(path, "rb") as handle:
            found = handle.read()
    except OSError as exc:
        return "foreign", "cannot be read (%s)" % exc
    if found == fresh.encode("utf-8"):
        return "pristine", "bytes equal to a fresh render"
    try:
        recorded = ET.parse(path).getroot().get("data-source-digest")
    except ET.ParseError:
        return "foreign", "not even XML"
    current = digest_of(entries)
    if recorded == current:
        return "hand-edited", "same source digest, different bytes"
    return "stale", ("rendered from a state that has moved on (%s… against %s…)"
                     % ((recorded or "none")[:8], current[:8]))
