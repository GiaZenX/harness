"""The kanban board the kernel writes beside its index (FR-0030/TSK-0071, FR-0053/TSK-0079).

EVERY CHECK HERE READS THE PAGE THAT SHIPS, parsed as HTML by `_Board` below, and the page is
produced by a real kernel state write or by the shipped renderer itself. That is deliberate and it
is the reason there is no JSON data block in the artefact: a test that read an embedded payload
would measure something no browser renders, and the failure this whole feature exists against --
a view that quietly stops showing an item -- lives in the DOM, not in a payload beside it.

TSK-0079 ADDED A SCRIPT TO THE PAGE AND THE RULE ABOVE DID NOT MOVE. Which view is showing and
which item detail is open are `hidden` attributes the RENDERER writes, so the tests below read the
DOM state exactly as before; the script moves those attributes at a click and carries no item
content at all (`test_the_page_script_carries_no_item_content_at_all`). What this suite does NOT
measure is the click itself -- there is no browser in it. The round's report
(`docs/reviews/2026-08-21-tsk0079-measurements.md`) records the browser run that does, and this
sentence is the only place that limit is claimed.
"""
import ast
import os
import re
import shutil
import subprocess
import sys
import time
import tracemalloc
from html.parser import HTMLParser

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM_KITS = os.path.join(ROOT, "team-kits")
sys.path.insert(0, TEAM_KITS)

from conftest import (approve, satisfy_the_architect_step,  # noqa: E402 -- the walkers
                      walk_to_status)
from kernel import backlog_tree, board  # noqa: E402
from kernel.backlog_types import ACTIVE_DIRS, AUTOMATA  # noqa: E402
from kernel.state import ProjectState  # noqa: E402


PR_FIELDS = {
    "title": "Checkout flow",
    "class": "normal",
    "problem": "no checkout",
    "goal": "working checkout",
    "acceptance_criteria": [{"id": "AC-1", "text": "order completes"}],
    "invariants": [],
    "out_of_scope": ["payments"],
    "priority": "high",
}
RQ_FIELDS = {
    "title": "Does it hold?",
    "class": "normal",
    "question": "does it?",
    "motivation": "because",
    "acceptance_criteria": [{"id": "AC-1", "text": "answered"}],
    "out_of_scope": ["ethics"],
    "priority": "high",
}
PROC_FIELDS = {"title": "File an invoice", "steps": ["scan", "file"], "roles": ["office-manager"]}
BUG_FIELDS = {
    "title": "crash on save",
    "related_pr": "PR-0001",
    "observed": "it crashes",
    "expected": "it saves",
    "repro": "press save",
    "severity": "high",
    "acceptance_criteria": [{"id": "AC-1", "text": "saves"}],
}
TSK_FIELDS = {
    "product_requirement": "PR-0001",
    "root_revision": 1,
    "derives_from": "PR-0001",
    "type": "implementation",
    "assigned_role": "backend-developer",
    "acceptance_refs": ["AC-1"],
    "required_inputs": [],
    "allowed_scope": ["src/**"],
    "forbidden_scope": [],
    "expected_outputs": ["code"],
    "dependencies": [],
}
SR_FIELDS = {
    "title": "checkout contract",
    "derives_from": "PR-0001",
    "contract": "POST /checkout returns 201",
    "affected_components": ["api"],
}

# WHAT ONE HOSTILE FILE MAY COST A STATE WRITE, in one place for the three tests that ask it.
#
# WHERE IT IS THE LOAD-BEARING MEASURE: the two ITEM-field bomb tests. There the defect's whole
# effect is an intermediate string that is built and thrown away, so the page barely moves and the
# allocation is the only witness. Wall-clock is not the measure anywhere here, because it does not
# separate the versions until that intermediate costs hundreds of megabytes. The number sits
# between the two figures this round measured: about forty times what a bounded render of these
# fixtures allocates, and well under the cheapest unbounded one. Both figures are in the TSK-0115
# protocol and are not repeated here -- a measurement in two places is one that rots in one of them.
#
# AT THE THIRD SITE IT IS NOT LOAD-BEARING TODAY, and that is said rather than implied: since
# `board.open_requests` stopped carrying `request_id`, every field it reads reaches the page, so
# the page-size assertion catches those defects on its own -- deleting this bound there leaves the
# test red anyway (measured this round). It stands there for the day a field the page does NOT show
# is read again, which is the shape that got past this suite once already.
_MEMORY_BUDGET = 8 * 1024 * 1024

# ...and the wall-clock bound beside it, which is the SUITE's house form rather than a measurement:
# no defect of this round was found by it, and none of these three would pass on a machine slow
# enough for it to matter. It stands so that a state write that hangs fails as a test rather than
# as a timeout nobody can read.
_STATE_WRITE_SECONDS = 30


class _Unprintable:
    """A field value that raises when it is rendered -- the CLASS the per-item guard exists
    for, rather than one shape somebody thought of. No YAML file produces this one, which is
    why it is handed to the renderer directly."""

    def __str__(self):
        raise ValueError("this value cannot be rendered")

    __repr__ = __str__


# Elements that never carry an end tag, so the parser below must not keep them on its stack.
_VOID = ("br", "meta", "link", "img", "input", "hr", "source", "area", "base", "col")


class _Board(HTMLParser):
    """The rendered page, read the way a browser reads it.

    Sections, columns, cards, tabs, views, tree nodes and item details are all recovered from the
    DOM's own attributes, so a card that never made it into the markup is a card this parser does
    not have -- which is exactly the failure the tests below are about. `columns` keeps the ORDER
    the page puts them in, because a kanban board whose columns are in a random order is not one.

    IT KEEPS AN ELEMENT STACK rather than a "what am I inside right now" flag. The page nests three
    views, a tree, groups and a dialog, so which item a piece of text belongs to is an ANCESTOR
    question -- and the flag version answered it with whatever element came last, which is how a
    tree node's title would have been appended to its own card's.
    """

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.generated_at = None
        self.columns = {}          # {type: [status, ...]} in page order
        self.cards = {}            # {(type, status): [item id, ...]}
        self.counts = {}           # {(type, status): the count the column CLAIMS}
        self.warnings = []         # [[kind, type, text, view], ...]
        self.titles = {}           # {item id: the title on its card's face}
        self.details = {}          # {item id: {field: text}} -- the modal's field list
        self.detail_ids = []       # every data-detail on the page, in order, duplicates included
        self.detail_titles = {}
        self.detail_status = {}
        self.hidden = {}           # {item id: is its detail hidden in the markup}
        self.views = {}            # {view key: is it hidden in the markup}
        self.tabs = []             # [(view key, aria-selected, tag name), ...]
        self.tab_counts = {}       # {view key: the number the tab CLAIMS}
        self.nodes = {}            # {(view, id): {type, parent, depth, unassigned}}
        self.node_titles = {}
        self.groups = []
        self.group_areas = []      # {(view, parent, type, area, count)} -- FR-0017's outline           # [(view, parent id, type, count), ...]
        self.refs = []             # [(detail id, id it links to), ...]
        self.attributes = []       # [(tag, attribute, value), ...] -- everything, for the guards
        self.elements = []         # [(tag, {attribute: value}), ...] -- element by element
        self.tags = set()
        self.element_ids = set()
        self.hrefs = []
        self.script = ""
        self.archived = None
        self.archived_text = ""
        self.overlay_hidden = None
        self.silent = set()        # {type} -- named on the page although it has no entries
        self.figures = {}          # {focus key: the number on the button}
        self.focus_lists = {}      # {focus key: the count the list CLAIMS}
        self.focus_rows = {}       # {focus key: [item id or "", ...]} in page order
        self.folds = {}            # {(view, node id): aria-expanded}
        self.fold_spaces = set()   # {(view, node id)} -- nodes drawn without a fold control
        self.group_hidden = []     # [(view, parent id, type, is it hidden), ...]
        self.reasons = {}          # {(view, node id): the refusal kind on its row}
        self.reason_words = {}     # {(view, node id): the word the row shows}
        self.milestones = {}       # {milestone id: is it late}
        self.milestone_goals = {}  # {milestone id: [goal id, ...] it links to}
        self.milestone_dates = {}  # {milestone id: the date on its card}
        self.milestone_lanes = {}  # {milestone id: the counted lanes, in words}
        self.ticks = []            # [(milestone id, class attribute), ...] on the ruler
        self.today_mark = None     # the today marker's own class, or None
        self.records_total = None
        self.empties = {}          # {type: the line naming its empty slots}
        self.rule_text = ""        # the sentence under the three figures
        self.style = ""
        self.noscript_style = ""
        self._stack = []
        self._field = None
        self.feed(text)

    # -- stack helpers ---------------------------------------------------------
    def _enclosing(self, attribute):
        for _tag, attrs in reversed(self._stack):
            if attribute in attrs:
                return attrs[attribute]
        return None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.add(tag)
        self.elements.append((tag, attrs))
        for name, value in attrs.items():
            self.attributes.append((tag, name, value or ""))
        if "id" in attrs:
            self.element_ids.add(attrs["id"])
        if "href" in attrs:
            self.hrefs.append(attrs["href"])
        if tag not in _VOID:
            self._stack.append((tag, attrs))
        view = self._enclosing("data-view")
        if tag == "time" and "data-generated-at" in attrs:
            self.generated_at = attrs["data-generated-at"]
        if attrs.get("class") == "overlay":
            self.overlay_hidden = "hidden" in attrs
        if tag == "div" and "data-view" in attrs:
            self.views[attrs["data-view"]] = "hidden" in attrs
        if "data-tab" in attrs:
            self.tabs.append((attrs["data-tab"], attrs.get("aria-selected"), tag))
        if "data-archived" in attrs:
            self.archived = int(attrs["data-archived"])
        if tag == "section" and "data-type" in attrs:
            self.columns.setdefault(attrs["data-type"], [])
        if tag == "div" and "data-status" in attrs:
            key = (self._enclosing("data-type"), attrs["data-status"])
            self.columns[key[0]].append(key[1])
            self.cards.setdefault(key, [])
            self.counts[key] = int(attrs["data-count"])
        if "data-open" in attrs:
            column = self._enclosing("data-status")
            detail = self._enclosing("data-detail")
            if detail is not None:
                self.refs.append((detail, attrs["data-open"]))
            elif column is not None:
                self.cards[(self._enclosing("data-type"), column)].append(attrs["data-open"])
        if tag == "article" and "data-detail" in attrs:
            self.detail_ids.append(attrs["data-detail"])
            self.details.setdefault(attrs["data-detail"], {})
            self.hidden[attrs["data-detail"]] = "hidden" in attrs
        if tag == "li" and "data-node" in attrs:
            self.nodes[(view, attrs["data-node"])] = {
                "type": attrs["data-node-type"], "parent": attrs["data-parent"],
                "depth": int(attrs["data-depth"]),
                "unassigned": self._enclosing("data-unassigned") is not None}
        if "data-group" in attrs:
            self.groups.append((view, attrs["data-group-parent"], attrs["data-group"],
                                int(attrs["data-count"])))
            self.group_areas.append((view, attrs["data-group-parent"], attrs["data-group"],
                                     attrs.get("data-group-area", ""),
                                     int(attrs["data-count"])))
        if tag == "li" and "data-warning" in attrs:
            self.warnings.append([attrs["data-warning"], attrs["data-type"], "", view])
        if "data-silent" in attrs:
            self.silent.add(attrs["data-silent"])
        if "data-focus-list" in attrs:
            self.focus_lists[attrs["data-focus-list"]] = int(attrs["data-count"])
            self.focus_rows.setdefault(attrs["data-focus-list"], [])
        if "data-open" in attrs and self._enclosing("data-focus-list") is not None:
            self.focus_rows[self._enclosing("data-focus-list")].append(attrs["data-open"])
        if "data-request" in attrs and self._enclosing("data-focus-list") is not None:
            # a request whose subject is not on the board: a row with no control, naming its subject
            self.focus_rows[self._enclosing("data-focus-list")].append(attrs["data-request"])
        if "data-fold" in attrs:
            self.folds[(view, attrs["data-fold"])] = attrs.get("aria-expanded")
        if attrs.get("class") == "fold-space":
            self.fold_spaces.add((view, self._enclosing("data-node")))
        if "data-group" in attrs:
            self.group_hidden.append((view, attrs["data-group-parent"], attrs["data-group"],
                                      "hidden" in attrs))
        if "data-reason" in attrs:
            self.reasons[(view, self._enclosing("data-node"))] = attrs["data-reason"]
        if tag == "li" and "data-milestone" in attrs:
            self.milestones[attrs["data-milestone"]] = attrs["data-late"] == "true"
        if tag == "div" and "data-milestone" in attrs:
            self.ticks.append((attrs["data-milestone"], attrs.get("class", "")))
        if attrs.get("class") == "ref" and self._enclosing("data-milestone"):
            self.milestone_goals.setdefault(
                self._enclosing("data-milestone"), []).append(attrs["data-open"])
        if attrs.get("class") == "today":
            self.today_mark = attrs.get("class")
        if "data-records" in attrs:
            self.records_total = int(attrs["data-records"])

    def handle_endtag(self, tag):
        for position in range(len(self._stack) - 1, -1, -1):
            if self._stack[position][0] == tag:
                del self._stack[position:]
                return

    def handle_data(self, data):
        if self._stack and self._stack[-1][0] == "style":
            if any(tag == "noscript" for tag, _attrs in self._stack):
                self.noscript_style += data
            else:
                self.style += data
            return
        for tag, attrs in reversed(self._stack):
            if attrs.get("class") == "num" and self._enclosing("data-focus"):
                self.figures[self._enclosing("data-focus")] = int(data)
                return
            if attrs.get("class") == "rule":
                self.rule_text += data
                return
            if attrs.get("class") == "empties":
                key = self._enclosing("data-type")
                self.empties[key] = self.empties.get(key, "") + data
                return
            if attrs.get("class") == "date" and self._enclosing("data-milestone"):
                key = self._enclosing("data-milestone")
                self.milestone_dates[key] = self.milestone_dates.get(key, "") + data
                return
            if attrs.get("class") == "goals":
                key = self._enclosing("data-milestone")
                self.milestone_lanes[key] = self.milestone_lanes.get(key, "") + data
                return
            if attrs.get("class") == "why":
                key = (self._enclosing("data-view"), self._enclosing("data-node"))
                self.reason_words[key] = self.reason_words.get(key, "") + data
                return
            if attrs.get("class") == "count" and self._enclosing("data-tab"):
                self.tab_counts[self._enclosing("data-tab")] = int(data)
                return
            if tag == "script":
                self.script += data
                return
            if tag in ("dt", "dd"):
                detail = self._enclosing("data-detail")
                if tag == "dt":
                    self._field = data
                elif detail is not None and self._field is not None:
                    self.details[detail][self._field] = (
                        self.details[detail].get(self._field, "") + data)
                return
            if attrs.get("class") == "title":
                detail = self._enclosing("data-detail")
                if detail is not None:
                    self.detail_titles[detail] = self.detail_titles.get(detail, "") + data
                elif self._enclosing("data-status") is not None:
                    card = self._enclosing("data-open")
                    self.titles[card] = self.titles.get(card, "") + data
                else:
                    key = (self._enclosing("data-view"), self._enclosing("data-open"))
                    self.node_titles[key] = self.node_titles.get(key, "") + data
                return
            if attrs.get("class") == "badge":
                detail = self._enclosing("data-detail")
                if detail is not None:
                    self.detail_status[detail] = self.detail_status.get(detail, "") + data
                return
            if attrs.get("class") == "archived":
                self.archived_text += data
                return
            if tag == "li" and "data-warning" in attrs:
                self.warnings[-1][2] += data
                return

    # -- readers the tests use -------------------------------------------------
    def where(self, item_id):
        """(type, status) of the one card carrying this id -- KeyError if the page dropped it."""
        found = [key for key, ids in self.cards.items() if item_id in ids]
        assert len(found) == 1, "%s appears %d time(s) on the board" % (item_id, len(found))
        return found[0]

    def kinds(self):
        return [(kind, item_type) for kind, item_type, _text, _view in self.warnings]

    def visible_views(self):
        return sorted(key for key, hidden in self.views.items() if not hidden)


def _read_board(state):
    return _Board(open(os.path.join(state.root, "generated", board.FILENAME),
                       encoding="utf-8").read())


def _state(tmp_path, name="project_memory"):
    root = tmp_path / name
    root.mkdir()
    return ProjectState(str(root))


def _write_item(state, item_type, stem, text):
    """One item file straight into the store -- the shape the kernel would refuse to write."""
    directory = os.path.join(state.root, *ACTIVE_DIRS[item_type].split("/"))
    os.makedirs(directory, exist_ok=True)
    open(os.path.join(directory, stem + ".yaml"), "w", encoding="utf-8").write(text)


# ---------------- (a) the view cannot go stale: it is written where the index is ----------------

def test_every_state_write_leaves_a_board_as_fresh_as_the_index(tmp_path):
    """The finding FR-0030 records, flipped: the pilot project never generated its dashboard because
    nothing triggered it. The board has no trigger of its own -- it is written inside
    `state._regenerate_index_locked`, so every writer that touches the index refreshes it.

    Capture, the approval mint, transition and archive are driven here rather than one of them,
    because "every writer" is the claim; the ones not driven reach the same method.
    `walk_to_status` is the sanctioned walker -- a gated edge is walked by MINTING its approval, so
    this measures the board on the route a real session takes.
    """
    state = _state(tmp_path)
    pr = state.capture("PR", PR_FIELDS)
    page = _read_board(state)
    assert page.where(pr["id"]) == ("PR", "DRAFT")

    approve(state, pr["id"], "scope")                       # the mint writes state too
    assert _read_board(state).where(pr["id"]) == ("PR", "APPROVED")

    walk_to_status(state, pr, "IN_DELIVERY")
    assert _read_board(state).where(pr["id"]) == ("PR", "IN_DELIVERY")

    state.transition(pr["id"], "REJECTED")                  # a plain, ungated edge
    state.archive(pr["id"])
    page = _read_board(state)
    assert not any(pr["id"] in ids for ids in page.cards.values()), (
        "an archived item is still on the board")
    assert pr["id"] not in page.details, "an archived item still has a detail on the page"

    # ...and the page is never OLDER than the index: one clock reading feeds both files
    index = yaml.safe_load(open(os.path.join(state.root, "generated", "index.yaml"),
                                encoding="utf-8"))
    assert page.generated_at == index["generated_at"]


def test_the_documented_command_names_every_artefact_it_writes(tmp_path):
    """`generate-index` is what a role is told to run, so it is what must produce the board -- and
    it must SAY it did, or the one artefact a person opens is the one the command never mentions.

    THE COUNT IS DERIVED FROM THE RUN, not written here. This test asked for exactly two printed
    lines until TSK-0120, and the seam that gave `state._write_board` its two diagrams would have
    left them unannounced while the test stayed green on a number that was no longer the truth --
    a test whose expectation is a literal cannot see an artefact arrive. So the question is now the
    one that matters: does everything this call left under `generated/` get named, and does
    everything it named exist. (Historically this test was called
    test_the_documented_command_writes_and_names_both_artefacts; the name is quoted without
    backticks here because it no longer resolves.)
    """
    state = _state(tmp_path)
    state.capture("PR", PR_FIELDS)
    result = subprocess.run(
        [sys.executable, "-B", "-m", "kernel.cli", "--root", state.root, "generate-index"],
        cwd=TEAM_KITS, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    printed = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert all(os.path.isfile(path) for path in printed), printed
    generated = os.path.join(state.root, "generated")
    assert sorted(os.path.basename(path) for path in printed) == sorted(os.listdir(generated)), (
        printed, os.listdir(generated))
    assert board.FILENAME in [os.path.basename(path) for path in printed], printed


# ---------------- the columns are the type's own chain ----------------

def test_the_columns_of_a_type_are_its_own_automaton_in_chain_order(tmp_path):
    """Kanban slots are DERIVED: the chain in chain order, then the side states, then the
    terminals. Read off the automaton here, not off `board.status_columns`, so the two ends are
    independent -- a chain change has to move the page, not just the helper.

    FR-0075 ADDED THE ONE SUBTRACTION and this test carries it rather than ignoring it: an END
    state holding no card is not drawn (nine of them across the page was what made the shipped
    board unreadable). So the drawn slots are a SUBSEQUENCE of the derived order, what is left out
    is a terminal, and every left-out slot is still named in the line under the row -- nothing
    silently vanishes. The other end (an empty CHAIN slot stays) is
    `test_an_empty_end_state_is_named_not_drawn`.
    """
    state = _state(tmp_path)
    state.capture("PR", PR_FIELDS)
    state.capture("TSK", TSK_FIELDS)
    page = _read_board(state)
    for item_type in ("PR", "TSK"):
        automaton = AUTOMATA[item_type]
        shown = page.columns[item_type]
        expected = list(automaton.chain)
        expected += sorted(automaton.states - set(expected) - automaton.terminals)
        expected += sorted(automaton.terminals - set(expected))
        assert shown == [status for status in expected if status in shown], (item_type, shown)
        missing = [status for status in expected if status not in shown]
        assert set(missing) <= automaton.terminals, (item_type, missing)
        for status in missing:
            assert status in page.empties[item_type], (item_type, status, page.empties)


def test_every_field_of_an_item_is_in_its_detail_exactly_once(tmp_path):
    """Nothing an item records may be missing from its record on the page, and nothing twice.

    THE EXPECTATION COMES FROM THE PAGE, NOT FROM `HEADER_FIELDS`. The first cut of this test read
    `set(item) - set(board.FACE_FIELDS)`, i.e. it compared the constant with itself: the verifier
    widened the constant and watched a field vanish from the card entirely -- the face renders only
    id and title -- with the suite still green. That is exactly the disappearance FR-0030 exists
    against. So the three RENDERED PLACES are looked up in the parsed page and each one only counts
    when it actually shows the item's value.

    TSK-0079 MOVED THE SURFACE and this test moved with it rather than being duplicated: the fold
    inside the card is gone, the item's record is the detail the card opens, and its header is where
    id, title and status are shown. The second half is new and is the reason the move is safe: the
    item is on the board AND in both trees, and it still has exactly ONE record on the page. A
    detail rendered per view would pass the field check and quietly triple the page.
    """
    state = _state(tmp_path)
    item = state.capture("PR", PR_FIELDS)
    page = _read_board(state)
    shown_elsewhere = {
        name for name, rendered in (("id", item["id"]),
                                    ("title", page.detail_titles.get(item["id"], "")),
                                    ("status", page.detail_status.get(item["id"], "")))
        if name in item and rendered == str(item[name])}
    assert shown_elsewhere == {"id", "title", "status"}, (
        "a field the detail is supposed to show in its header is not there: %s" % (shown_elsewhere,))
    assert set(page.details[item["id"]]) == set(item) - shown_elsewhere
    # a nested value reads as text, not as a Python repr somebody has to decode
    assert page.details[item["id"]]["acceptance_criteria"] == "id: AC-1; text: order completes"

    assert page.where(item["id"]) == ("PR", "DRAFT")
    assert ("product", item["id"]) in page.nodes and ("system", item["id"]) in page.nodes
    assert page.detail_ids.count(item["id"]) == 1, (
        "the item is shown in three views and carries %d records"
        % page.detail_ids.count(item["id"]))


def test_a_title_that_tries_to_close_the_elements_around_it_does_not_break_the_page(tmp_path):
    """A hand-written item is not the only source of a hostile title, and every element the page
    wraps an item in is one a title can try to close: the card is a `<button>`, the record an
    `<article>`, and the script that opens the record ends at the first `</script>`. The proof is
    that the PARSER still finds the card, the node and the record, and reads the title back whole.
    """
    state = _state(tmp_path)
    fields = dict(PR_FIELDS,
                  title="fix </button></article></script><script>alert(1)</script> leak")
    item = state.capture("PR", fields)
    page = _read_board(state)
    assert page.where(item["id"]) == ("PR", "DRAFT")
    assert page.titles[item["id"]] == fields["title"]
    assert page.detail_titles[item["id"]] == fields["title"]
    assert page.node_titles[("product", item["id"])] == fields["title"]


# ---------------- (b) every kit renders its own types ----------------

def _kit_state(tmp_path, kit):
    """A state directory as that kit's scaffold installs it -- its own template tree, verbatim."""
    root = tmp_path / kit / "project_memory"
    shutil.copytree(os.path.join(TEAM_KITS, kit, "templates", "project_memory"), str(root))
    return ProjectState(str(root))


@pytest.mark.parametrize("kit,captures,expected_absent", [
    ("dev-team", [("PR", PR_FIELDS)], ("RQ", "HYP", "EXP", "PROC")),
    ("research-team", [("RQ", RQ_FIELDS)], ("PR", "PROC", "ARC")),
    ("office-team", [("PROC", PROC_FIELDS)], ("PR", "RQ", "HYP", "EXP", "ARC")),
])
def test_each_kit_renders_the_types_its_own_template_ships(tmp_path, kit, captures,
                                                           expected_absent):
    """FR-0030/3: all three kits, with KIT-APPROPRIATE types. Which types those are is read off the
    state tree the kit ships -- there is no per-kit type table to disagree with it -- so the
    expectation here is derived from that same tree, and the hard-named absences are the
    counter-direction: a board that simply showed every type the kernel knows would fail them."""
    state = _kit_state(tmp_path, kit)
    for item_type, fields in captures:
        state.capture(item_type, fields)
    page = _read_board(state)
    shipped = {item_type for item_type, directory in ACTIVE_DIRS.items()
               if os.path.isdir(os.path.join(state.root, *directory.split("/")))}
    # A TYPE WITH NO ITEMS KEEPS ITS NAME AND LOSES ITS ROW (FR-0075): an empty row of empty slots
    # is what filled the shipped page (32 empty against 13 filled slots, measured in the design
    # pass), and dropping the type without a word is the disappearance FR-0030 exists against. So
    # the two together are the kit's set, and neither alone is.
    assert set(page.columns) | page.silent == shipped, (
        kit, sorted(page.columns), sorted(page.silent), sorted(shipped))
    assert not (set(page.columns) & page.silent), "a type is both drawn and called silent"
    for absent in expected_absent:
        assert absent not in page.columns and absent not in page.silent, (
            "%s renders %s, which it does not ship" % (kit, absent))
    for item_type, _fields in captures:
        assert page.cards[(item_type, AUTOMATA[item_type].initial)]


@pytest.mark.parametrize("kit", ["dev-team", "office-team", "research-team"])
def test_every_kit_ships_a_directory_for_every_type_the_product_view_places(tmp_path, kit):
    """A kit whose template tree lacks a type its PRODUCT view places hides that type from its user.

    THE VIEW IS THE CONTRACT AND THE TREE IS THE DELIVERY, and only their disagreement is a defect.
    The product view is the conversation with the user (`backlog_tree.VIEWS`), so every kit has one
    -- unlike the system view, whose children a kit may legitimately not use: dev-team ships no
    hypotheses and no experiments and that is right. What a kit may NOT do is place a type in the
    customer's own view and ship no drawer for it: on a fresh project that type is neither drawn nor
    named silent, so nobody using that kit ever learns it exists, and the first item of that type
    appears in a directory the scaffold never made.

    WHY THIS TEST EXISTS AT ALL: `DEC-0064` (5) made the `milestones/active` directory in three kits
    a merge-round seam and its `consequences` promised "every line has a test that goes red without
    it, so a half-applied seam is visible, not silent". Measured in the TSK-0120 merge round, in a
    copy outside the repo: with all three directories deleted, the tripwire the DEC named --
    `test_each_kit_renders_the_types_its_own_template_ships` -- stayed GREEN (3 passed), because it
    derives its expectation from the same shipped tree and so cannot see the tree lose a drawer.
    """
    state = _kit_state(tmp_path, kit)
    product = next(view for view in backlog_tree.VIEWS if view.key == "product")
    missing = [item_type for item_type in product.children
               if not os.path.isdir(os.path.join(state.root, *ACTIVE_DIRS[item_type].split("/")))]
    assert not missing, (
        "%s places %s in the product view but ships no directory for it" % (kit, missing))
    state.generate_index()                        # a fresh project, no item captured yet
    page = _read_board(state)
    unseen = [item_type for item_type in product.children
              if item_type not in page.columns and item_type not in page.silent]
    assert not unseen, ("%s never names %s on a fresh board" % (kit, unseen))


@pytest.mark.parametrize("kit", ["dev-team", "office-team", "research-team"])
def test_every_kit_ships_a_type_its_backlog_trees_can_hang_from(tmp_path, kit):
    """The trees are rootless in a kit that ships no root type, and then both backlog tabs are one
    long Unassigned list. `ROOT_TYPES` is derived from `ROOT_TYPE_BY_KIT` plus the office kit's
    procedures, and this is the measurement that keeps that derivation honest against the trees the
    kits actually install -- read off the state directory, not off the map it was derived from."""
    state = _kit_state(tmp_path, kit)
    present = set(board.types_present(state))
    assert present & backlog_tree.ROOT_TYPES, (
        "%s ships no type either backlog tree can hang from (%s)" % (kit, sorted(present)))


# ---------------- (c) nothing a type does not describe is ever dropped ----------------

def test_an_item_type_no_status_vocabulary_describes_still_appears_with_a_warning(tmp_path):
    """The "Other" path of the shipped dashboard, one layer down. This board assigns no type to a
    hand-kept view, so what is left to be unknown about a type is its STATUS VOCABULARY: a type the
    kernel gains without an automaton has no column of its own. Its items get one anyway, and the
    page says so -- a whole item type quietly missing from the only overview a user opens is the
    failure worth designing against."""
    state = _state(tmp_path)
    row = {"id": "ZZZ-0001", "type": "ZZZ", "title": "from a type nobody wired", "status": "WEIRD"}
    page = _Board(board.render(state, [(row, dict(row))], "2026-08-16T12:00:00"))
    assert page.where("ZZZ-0001") == ("ZZZ", "WEIRD")
    assert page.kinds() == [("unknown-status", "ZZZ")]


def test_a_status_off_its_types_vocabulary_still_appears_and_warns(tmp_path):
    """The same property through the shipped write path, in the shape that really produces it: a
    hand-edited item file. The kernel refuses such a status on its own transitions, so the item
    only ever reaches the store by hand -- and that is precisely when a board must not hide it."""
    state = _state(tmp_path)
    _write_item(state, "BUG", "BUG-0001", "id: BUG-0001\ntitle: crash\nstatus: WAT\n")
    state.generate_index()
    page = _read_board(state)
    assert page.where("BUG-0001") == ("BUG", "WAT")
    assert ("unknown-status", "BUG") in page.kinds()


def test_a_record_type_without_a_status_is_not_reported_as_a_defect(tmp_path):
    """The counter-direction, and the reason the warning above is not simply "no column matched":
    Evidence, approvals and the frozen design types carry NO status by contract. Their cards belong
    in a column of their own, and calling that a defect would make the banner meaningless noise on
    every project that has ever recorded a test run."""
    state = _state(tmp_path)
    pr = state.capture("PR", PR_FIELDS)
    evidence = state.capture("EVD", {"kind": "test", "related": [pr["id"]], "result": "pass",
                                     "summary": "suite green",
                                     "artifact_refs": ["staging/TSK-0001/log.txt"]})
    page = _read_board(state)
    assert page.where(evidence["id"]) == ("EVD", board.NO_STATUS)
    assert not page.warnings, page.warnings


def test_an_item_file_that_cannot_be_read_is_shown_rather_than_dropped(tmp_path):
    """A corrupt item is the one an overview must show most loudly: the index already reports it as
    `corrupt`, and a board that skipped those rows would be reassuring about a state nobody can
    read."""
    state = _state(tmp_path)
    _write_item(state, "SR", "SR-0001", "- this is a list, not an item\n")
    state.generate_index()
    page = _read_board(state)
    assert page.where("SR-0001") == ("SR", board.UNREADABLE)
    assert ("unreadable", "SR") in page.kinds()


def test_a_self_referential_item_body_does_not_stop_the_state_write(tmp_path):
    """The regression this renderer can cause and the index never could. A YAML anchor pointing at
    its own container is a legal file `yaml.safe_load` resolves into a self-referential object; the
    board is rendered at the END of every state write, so an unbounded walk over it would not merely
    spoil one page -- it would raise out of `_regenerate_index_locked` and make every later capture
    in that project fail. The item still has to reach the board, so the bound may not simply drop it.
    """
    state = _state(tmp_path)
    _write_item(state, "BUG", "BUG-0001", "id: BUG-0001\ntitle: loops\nstatus: OPEN\n"
                                          "repro: &loop\n  - step\n  - *loop\n")
    state.generate_index()                       # the write itself must survive it
    state.capture("PR", PR_FIELDS)               # ...and so must the next one
    page = _read_board(state)
    assert page.where("BUG-0001") == ("BUG", "OPEN")
    assert page.details["BUG-0001"]["repro"].startswith("step")


# ---------------- the freshness claim, on the writers that did NOT regenerate ----------------

def _kernel_calls():
    """{(module, function): {called attribute names}} for every function in the kernel package.

    Parsed, not imported: the question is which calls a function CONTAINS, and that is a property
    of the source. Nested functions are attributed to the enclosing one, which is what the rule
    below needs -- a writer that regenerates from inside a closure still regenerates.
    """
    found = {}
    kernel_dir = os.path.join(TEAM_KITS, "kernel")
    for name in sorted(os.listdir(kernel_dir)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(kernel_dir, name), encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=name)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = found.setdefault((name, node.name), set())
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call):
                    target = inner.func
                    calls.add(target.attr if isinstance(target, ast.Attribute)
                              else getattr(target, "id", ""))
    return found


# Kernel functions that write a file WITHOUT regenerating the index, each with the reason the board
# does not have to care. Every entry is a claim about WHAT that function writes, and both ends are
# measured by the test below: an entry whose function no longer writes at all is dead, and a writer
# that is neither here nor regenerating is the B2 defect coming back.
_WRITERS_THE_BOARD_DOES_NOT_RENDER = {
    ("state.py", "_write_yaml_atomic"): "IS the writer (delegates to _write_text_atomic)",
    ("state.py", "_regenerate_index_locked"): "IS the regeneration",
    ("state.py", "_write_board"): "writes the board itself",
    ("approvals.py", "create_pending_request"): "approvals/pending/ -- not listed by "
                                                "iter_active_items and not in the index",
    ("checkpoints.py", "record"): "tasks/checkpoints/ -- no ACTIVE_DIRS home, so no card",
    ("dispatch.py", "mark_awaiting_bind"): "the lease file, which is not an item",
    ("dispatch.py", "clear_awaiting_bind"): "the lease file",
    ("dispatch.py", "bind_agent_by_role"): "the lease file",
    ("dispatch.py", "bind_agent"): "the lease file",
    ("dispatch.py", "validate_dispatch"): "the lease file (the claim)",
    ("scopes.py", "write_record"): "tasks/scope-checks/ -- the record of one check-scopes run "
                                   "(DEC-0092 (2)), a measurement the dispatcher reads and not an "
                                   "item; no ACTIVE_DIRS home, so no card",
    ("dispatch.py", "_release_lease_locked"): "resets the TASK, but every caller regenerates -- "
                                              "checked below, because one of them did not",
    ("staging.py", "freeze_design"): "its DSN manifest, then `_update_item_locked` on the root, "
                                     "which regenerates",
    ("report.py", "generate_session_brief"): "generated/session_brief.yaml",
    ("presets.py", "record_preset"): "project_config.yaml -- a kit document, no card",
    ("filing.py", "apply"): "filing_plan.yaml -- a kit document, no card (and nothing it writes "
                            "is an item: the plan says where documents belong, the board shows "
                            "what the project is working on)",
    ("documents.py", "apply"): "a kit DOCUMENT -- `layout.is_project_document` is what it refuses "
                               "anything else by, so what it writes can never be an item and has "
                               "no card",
    ("documents.py", "apply_revision"): "the same kit DOCUMENT through the same refusal, on the "
                                        "route that may replace and delete (FR-0067)",
    ("approvals.py", "withdraw_request"): "approvals/withdrawn/ -- the record that a pending "
                                          "QUESTION was taken back (BUG-0302). Not an item, no "
                                          "ACTIVE_DIRS home and therefore no card, exactly like "
                                          "the pending file it replaces; what the board shows of "
                                          "an approval request it reads through `open_requests` "
                                          "at render time, not out of the index",
    ("presets.py", "_after_a_failed_install"): "a .claude marker file",
    ("kitupdate.py", "ensure_restart_is_forced"): "a .claude marker file",
}


def test_no_kernel_writer_of_a_rendered_file_leaves_the_board_behind():
    """The board can only be as fresh as the index, so every kernel write has to regenerate it.

    Two did not, and the verifier found them by hand: `approvals.revoke` (the APR card kept saying
    `revoked = False` -- a field the index does not even carry, so only the board could show it)
    and the lease-expiry release in `dispatch._validate_lease_locked` (task READY on disk, LEASED
    on the index and the board). Both are fixed; this is what keeps the pair from coming back, and
    it derives the writers from the package instead of trusting a sentence in a docstring.
    """
    calls = _kernel_calls()
    writers = {key for key, made in calls.items()
               if {"_write_yaml_atomic", "_write_text_atomic"} & made}
    offenders = sorted(key for key in writers
                       if "_regenerate_index_locked" not in calls[key]
                       and key not in _WRITERS_THE_BOARD_DOES_NOT_RENDER)
    assert not offenders, (
        "these kernel functions write a file and regenerate neither index nor board; if what they "
        "write is not rendered, say so in _WRITERS_THE_BOARD_DOES_NOT_RENDER: %s" % offenders)
    # the other end: an exemption for a function that no longer writes anything is a dead claim
    dead = sorted(key for key in _WRITERS_THE_BOARD_DOES_NOT_RENDER if key not in writers)
    assert not dead, "exempted, but no longer a writer: %s" % dead
    # ...and the one exemption that is an argument about its CALLERS is checked on them
    for key, made in calls.items():
        if "_release_lease_locked" in made and key != ("dispatch.py", "_release_lease_locked"):
            assert "_regenerate_index_locked" in made, (
                "%s releases a lease (which resets the task) without regenerating -- the board "
                "and the index then keep the task LEASED" % (key,))


def test_a_revoked_approval_shows_as_revoked_on_the_board(tmp_path):
    """`revoked` lives on the APR item and in NO index row, so the board is the only place it can
    be read at all -- and before the fix it was the one place that still said `False` after the
    file said `True`."""
    state = _state(tmp_path)
    pr = state.capture("PR", PR_FIELDS)
    apr = approve(state, pr["id"], "scope")
    assert _read_board(state).details[apr["id"]]["revoked"] == "False"
    sys.path.insert(0, TEAM_KITS)
    from kernel import approvals
    approvals.revoke(state, apr["id"])
    assert _read_board(state).details[apr["id"]]["revoked"] == "True"


def test_an_expired_lease_puts_the_task_back_on_the_board_as_ready(tmp_path):
    """The other half: an expired lease returns the task to READY on disk. Of the four release
    sites this one -- the gate's own validation path -- regenerated nothing, so the board (and the
    index under it) went on showing a task as LEASED that nobody held."""
    sys.path.insert(0, TEAM_KITS)
    from kernel import dispatch
    state = _state(tmp_path)
    pr = state.capture("PR", PR_FIELDS)
    approve(state, pr["id"], "scope")
    task = state.capture("TSK", dict(TSK_FIELDS, product_requirement=pr["id"],
                                     derives_from=pr["id"]))
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]),
                               state.read_item(pr["id"]))
    lease = dispatch.create_lease(state, task["id"], ttl=-1)     # already expired
    assert _read_board(state).where(task["id"]) == ("TSK", "LEASED")
    with pytest.raises(dispatch.DispatchError):
        dispatch.validate_lease(state, {"task_id": task["id"], "lease": lease["nonce"],
                                        "root_revision": lease["root_revision"]})
    assert state.read_item(task["id"])["status"] == "READY"
    assert _read_board(state).where(task["id"]) == ("TSK", "READY")


# ---------------- the board may never fail the state write it is written by ----------------

def test_a_surrogate_in_an_item_does_not_stop_the_state_write(tmp_path):
    """A lone surrogate is legal YAML and UTF-8 cannot encode it. The state write has already
    happened by the time the page is written, so a raised UnicodeEncodeError there would report a
    successful capture as failed -- and, because the renderer reads ALL items, it would do so for
    every later capture in that project, with the hand edit the gates refuse as the only apparent
    remedy."""
    state = _state(tmp_path)
    _write_item(state, "BUG", "BUG-0001", 'id: BUG-0001\ntitle: lone half\nstatus: OPEN\n'
                                          'observed: "\\uD800"\n')
    state.generate_index()
    item = state.capture("PR", PR_FIELDS)          # the NEXT write must go through as well
    page = _read_board(state)
    assert page.where("BUG-0001") == ("BUG", "OPEN")
    assert page.where(item["id"]) == ("PR", "DRAFT")


def test_an_alias_bomb_cannot_stretch_a_state_write(tmp_path):
    """A small item file whose YAML aliases multiply into tens of millions of values.

    `yaml.safe_load` resolves aliases into SHARED objects, so a kilobyte can describe a structure
    whose flattening is enormous -- while the index beside it stays a few hundred bytes, because it
    never looks inside a field. The first cut of this round met that twice over: it handed the
    container at the depth bound to `str()` (which unfolds the entire graph below it, the shape the
    verifier measured at 14.87 s per state write) and it cut the text only AFTER building it.

    TWO BOMBS, BECAUSE THE TWO BOUNDS FAIL DIFFERENTLY, and one of them shipped untested for a
    round because a single shape cannot show both:
      * `deep` grows OUTWARD -- every level doubles the one below it, so its LARGEST container is
        the one the walk meets exactly AT the depth bound. `str()` there unfolds that whole graph
        in ONE call, which no character budget can interrupt. (The earlier shape had the mass the
        other way round: the SMALLEST container sat at the bound, worth 14 characters under
        `str()`, so restoring that defect left every assertion green.)
      * `wide` keeps its mass BELOW the bound, where the marker never applies and only the walk's
        own budget can stop the multiplication.
    Each mutation is caught by exactly one of them, and both are measured by the same assertions.

    WHAT IS ASSERTED AND WHY IT IS NOT A STOPWATCH. Wall-clock separates the versions only at sizes
    whose intermediate string costs hundreds of megabytes, so the load-bearing measure is what the
    work actually consumes: the memory the render allocates (`tracemalloc`, which sees the
    intermediate the file never gets), plus the bytes the item may add to the page and the fact
    that the deep container was MARKED. That last one is only evidence because `NESTED_MARKER` is
    not the ellipsis a budget cut appends -- while it was, this assertion held for the wrong reason.
    """
    levels, width = 24, 150
    state = _state(tmp_path)
    state.generate_index()
    board_path = os.path.join(state.root, "generated", board.FILENAME)
    empty = os.path.getsize(board_path)             # the page around the cards, measured not guessed

    # `l1` is two leaves; every level after it is two references to the level below, so `l24`
    # stands for 2**23 leaves in ~500 bytes of file.
    deep = ["  - &l1 [xxxxxxxxxx, xxxxxxxxxx]"]
    deep += ["  - &l%d [*l%d, *l%d]" % (n, n - 1, n - 1) for n in range(2, levels + 1)]
    deep.append("  - [*l%d]" % levels)
    # ...and three levels of `width` copies, whose mass sits above the depth bound
    wide = ["  - &w1 [%s]" % ", ".join(["xxxxxxxxxx"] * width)]
    wide += ["  - &w%d [%s]" % (n, ", ".join(["*w%d" % (n - 1)] * width)) for n in (2, 3)]
    wide.append("  - [%s]" % ", ".join(["*w3"] * width))
    lines = len(deep) + len(wide)                   # one card line per top-level element
    _write_item(state, "BUG", "BUG-0001",
                "id: BUG-0001\ntitle: bomb\nstatus: OPEN\nrepro:\n%s\nobserved:\n%s\n"
                % ("\n".join(deep), "\n".join(wide)))
    path = os.path.join(state.root, *ACTIVE_DIRS["BUG"].split("/"), "BUG-0001.yaml")

    tracemalloc.start()
    started = time.time()
    state.generate_index()
    took = time.time() - started
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    grew = os.path.getsize(board_path) - empty
    item_bytes = os.path.getsize(path)
    assert peak < _MEMORY_BUDGET, (
        "rendering a %d-byte item allocated %.1f MB" % (item_bytes, peak / 1024.0 / 1024))
    # the page bound is the BUDGET, read off `board`: one line per top-level element, each within
    # VALUE_MAX_CHARS, plus room for the markup around a card, a tree node and a warning
    assert grew < lines * (board.VALUE_MAX_CHARS + 128) + 4096, (
        "the item added %d bytes to the board (item file: %d bytes)" % (grew, item_bytes))
    assert took < _STATE_WRITE_SECONDS, (
        "one item stretched a state write to %.1f s" % took)
    page = _read_board(state)
    assert page.where("BUG-0001") == ("BUG", "OPEN")
    assert board.NESTED_MARKER in page.details["BUG-0001"]["repro"], (
        "the container at the depth bound was unfolded instead of marked")


def test_a_board_that_cannot_be_written_does_not_fail_the_state_write(tmp_path, capsys):
    """The write itself can fail for reasons no renderer controls: on Windows an ordinary read
    handle on `board.html` makes `os.replace` refuse (measured on this host), and a directory in
    the file's place does it on every platform. The state write must still go through, and the
    failure must be SAID -- a silent one would be a stale page nobody doubts."""
    state = _state(tmp_path)
    state.capture("PR", PR_FIELDS)
    board_path = os.path.join(state.root, "generated", board.FILENAME)
    before = open(board_path, encoding="utf-8").read()
    os.remove(board_path)
    os.mkdir(board_path)                            # nothing can replace this with a file
    item = state.capture("BUG", BUG_FIELDS)         # must NOT raise
    assert state.read_item(item["id"])["id"] == item["id"]
    index = yaml.safe_load(open(os.path.join(state.root, "generated", "index.yaml"),
                                encoding="utf-8"))
    assert item["id"] in [row["id"] for row in index["items"]], "the index write was skipped too"
    said = capsys.readouterr().err
    assert board.FILENAME in said and "NOT rebuilt" in said, said
    os.rmdir(board_path)
    open(board_path, "w", encoding="utf-8").write(before)


def test_an_item_no_renderer_can_read_costs_its_own_card_and_nothing_else(tmp_path):
    """The per-item guard, driven with a body no YAML file produces -- deliberately, because the
    guard exists for the CLASS (the body's shape is the file's decision, not this module's) and
    not for one shape somebody thought of. The neighbouring card must survive it, and the page has
    to NAME the id rather than quietly drop a row."""
    state = _state(tmp_path)
    good = ({"id": "PR-0002", "type": "PR", "title": "fine", "status": "DRAFT"},
            {"id": "PR-0002", "title": "fine", "status": "DRAFT"})
    broken = ({"id": "PR-0001", "type": "PR", "title": "bad body", "status": "DRAFT"},
              ["not a mapping at all"])
    # ...and the second half of the same guard: the CARD and the tree node are drawn outside
    # `_detail`'s try, so a title nothing can render would cost the page rather than the item
    titleless = ({"id": "PR-0003", "type": "PR", "title": _Unprintable(), "status": "DRAFT"},
                 {"id": "PR-0003", "status": "DRAFT"})
    page = _Board(board.render(state, [broken, good, titleless], "2026-08-16T12:00:00"))
    assert page.where("PR-0002") == ("PR", "DRAFT")
    assert page.where("PR-0001") == ("PR", "DRAFT")
    assert page.where("PR-0003") == ("PR", "DRAFT")
    assert page.titles["PR-0002"] == "fine"
    assert page.titles.get("PR-0003", "") == ""
    assert ("system", "PR-0003") in page.nodes
    assert page.kinds() == [("unrenderable", "PR"), ("unrenderable", "PR")]
    assert "PR-0001" in page.warnings[0][2] and "PR-0003" in page.warnings[1][2]


def test_every_column_counts_the_cards_it_actually_carries(tmp_path):
    """The number beside a column head is a claim about the cards under it. An unchecked counter is
    where a number quietly stops being true -- and this one is what a reader trusts when a column is
    long enough to scroll."""
    state = _state(tmp_path)
    for _ in range(3):
        state.capture("PR", PR_FIELDS)
    page = _read_board(state)
    for key, count in page.counts.items():
        assert count == len(page.cards[key]), key
    assert page.counts[("PR", "DRAFT")] == 3


# ---------------- (d) three views in one file, one of them showing ----------------

def test_the_page_shows_one_view_and_the_other_two_are_hidden_in_the_dom(tmp_path):
    """FR-0053/2: real tabs, not anchors into one endless page.

    WHAT IS MEASURED IS DOM STATE, because that is what the browser reads and what a test can read
    without one: the two inactive views carry the `hidden` attribute the renderer wrote, so they are
    not displayed by the browser's own stylesheet -- with no CSS and no script involved. The script
    moves that attribute at a click; it cannot be what decides the page's initial state, or the file
    would show three stacked views for the moment before it runs.

    THE TABS ARE BUTTONS AND NOT LINKS, and that is the other half of the ask: an `<a href="#...">`
    would scroll a long page instead of switching a view, which is exactly the shape FR-0053 was
    written against. Every tab must name a view that exists, and the selected one must be the one
    showing -- a tab pointing at a view the page does not have is a dead control.
    """
    state = _state(tmp_path)
    state.capture("PR", PR_FIELDS)
    page = _read_board(state)
    assert set(page.views) == {"board", "product", "system"}, sorted(page.views)
    assert page.visible_views() == ["board"], page.views
    assert {key for key, _selected, _tag in page.tabs} == set(page.views)
    assert {tag for _key, _selected, tag in page.tabs} == {"button"}, (
        "a tab that is a link scrolls the page instead of switching the view")
    selected = [key for key, mark, _tag in page.tabs if mark == "true"]
    assert selected == page.visible_views(), (selected, page.visible_views())
    # ...and every item detail starts hidden, or the page opens with 200 records unrolled
    assert set(page.hidden.values()) == {True}
    # ...and so does the overlay they sit in. It is `position: fixed; inset: 0`, so without the
    # attribute it lies over the whole page from the first paint: nothing behind it can be clicked,
    # including the tabs and every card. Measured in a browser for the round's report; here it is
    # the attribute the renderer has to write.
    assert page.overlay_hidden is True, "the modal backdrop covers the page from the start"
    # the number beside a tab is a claim about what is behind it -- an unchecked counter is
    # where a number quietly stops being true, and the column heads are checked for the same
    # reason (`test_every_column_counts_the_cards_it_actually_carries`)
    assert page.tab_counts["board"] == sum(len(ids) for ids in page.cards.values())
    for view in ("product", "system"):
        assert page.tab_counts[view] == len([key for key in page.nodes if key[0] == view]), (
            view, page.tab_counts[view])


def test_the_page_script_carries_no_item_content_at_all(tmp_path):
    """The script is a CONSTANT, and that is the whole escaping argument for the new surface.

    Nothing item-derived is interpolated into it, so a `</script>` in a title cannot end it early
    and no second escaping layer (JS string, JSON, attribute-inside-JS) exists to get wrong. This
    measures the property rather than the intention: two stores with nothing in common must produce
    the same script, byte for byte. An embedded payload -- the shape a "just put the items in a
    JSON blob" rewrite would take -- fails here on its first hostile character and on its first
    benign one too.
    """
    first = _state(tmp_path, "one")
    first.capture("PR", PR_FIELDS)
    second = _state(tmp_path, "two")
    root = second.capture("PR", dict(PR_FIELDS, title="</script>", goal="'; alert(2); //"))
    second.capture("BUG", dict(BUG_FIELDS, related_pr=root["id"],
                               title="</script><script>alert(1)</script>",
                               observed="'; alert(2); //"))
    one, two = _read_board(first), _read_board(second)
    assert one.script.strip(), "the page carries no script at all"
    assert one.script == two.script, "item content reached the page's script"


def test_a_hostile_field_cannot_add_an_element_or_an_attribute_to_the_page(tmp_path):
    """The new surfaces -- the modal, the tree labels, the reference buttons -- through the REAL
    write path, with the attack aimed at each of them.

    THE MEASURE IS A DIFF AND NOT A LIST OF FORBIDDEN STRINGS: an injection IS, by definition, an
    element or an attribute that item content put into the page. So the same store is written twice,
    once benignly and once with every string field hostile, and the SETS of tag names and attribute
    names have to match. It costs nothing to keep true and it does not have to be told what the next
    attack looks like -- an `onerror=` inside a title, a `data-open` a field invents, a `<script>`
    an id closes the attribute for, all land as a new name in one of the two sets.

    The ID is hostile too, and by hand: `capture` assigns ids, so the only way one reaches the page
    is a file somebody wrote -- and that is the value that goes into `data-open`, `data-detail` and
    `data-node`, i.e. into an attribute rather than into text.

    THE FIXTURE IS DUMPED AS ONE DOCUMENT, and that is not a style choice. It was composed field by
    field with `yaml.safe_dump(value).strip()`, and `safe_dump` of a scalar ends its document with
    `...` -- which `strip()` does not remove, because it is not whitespace. The file was therefore a
    broken multi-document stream, the item arrived as `(unreadable)`, and the hostile id and title
    never reached the page at all: the escaping mutations this test exists for stayed GREEN. A
    fixture that cannot deliver its attack is a test that cannot fail.
    """
    attack = '</article><img src=x onerror=alert(1)><a href="javascript:alert(2)">x</a>'
    stores = {}
    for kind, title, evil_id in (("benign", "checkout", "BUG-0002"),
                                 ("hostile", attack, 'BUG-0002" onclick="alert(3)')):
        state = _state(tmp_path, kind)
        pr = state.capture("PR", dict(PR_FIELDS, title=title, problem=attack if kind else "x"))
        state.capture("SR", dict(SR_FIELDS, title=title, derives_from=pr["id"],
                                 contract=attack, affected_components=[attack]))
        _write_item(state, "BUG", "BUG-0002", yaml.safe_dump(
            {"id": evil_id, "title": title, "status": "OPEN", "related_pr": pr["id"]},
            allow_unicode=True, default_flow_style=False))
        state.generate_index()
        stores[kind] = _read_board(state)

    benign, hostile = stores["benign"], stores["hostile"]
    # the fixture has to ARRIVE, or everything below passes on an empty page
    assert hostile.details[evil_id]["related_pr"] == pr["id"], sorted(hostile.details)
    assert hostile.detail_titles[evil_id] == attack
    assert hostile.tags == benign.tags, hostile.tags ^ benign.tags
    assert ({name for _tag, name, _value in hostile.attributes}
            == {name for _tag, name, _value in benign.attributes}), (
        "item content introduced an attribute: %s"
        % ({name for _tag, name, _value in hostile.attributes}
           ^ {name for _tag, name, _value in benign.attributes}))
    # ...and the hostile text is still SHOWN -- escaping that drops the content is not a fix
    assert attack in hostile.details[[key for key in hostile.details
                                      if key.startswith("PR-")][0]]["problem"]


def test_the_page_carries_no_event_handler_and_no_link_out_of_itself(tmp_path):
    """Self-containment and the javascript:-URL class, as properties of every attribute on a page
    rendered from hostile items.

    Both halves are DEFINITIONS rather than lists of bad strings: an inline handler is an attribute
    whose NAME starts with `on` (that is what the class is), and a link out of this file is an
    attribute whose VALUE starts with a URL scheme or a slash. What is left is the page's own
    anchors, and those must resolve inside it -- a fragment pointing at an id the page does not
    carry is a dead link, which is how the type navigation would rot if a section were renamed.
    """
    state = _state(tmp_path)
    pr = state.capture("PR", dict(PR_FIELDS, title='javascript:alert(1)',
                                  problem='<a href="javascript:alert(2)">x</a>'))
    state.capture("BUG", dict(BUG_FIELDS, related_pr=pr["id"],
                              observed="https://example.invalid/steal?c=1"))
    page = _read_board(state)
    handlers = sorted({(tag, name) for tag, name, _value in page.attributes
                       if name.lower().startswith("on")})
    assert not handlers, handlers
    scheme = re.compile(r"\s*([A-Za-z][A-Za-z0-9+.\-]*:|//|/)")
    outward = sorted({(tag, name, value) for tag, name, value in page.attributes
                      if scheme.match(value)})
    assert not outward, outward
    assert page.hrefs, "the type navigation vanished -- this check would then prove nothing"
    for href in page.hrefs:
        assert href.startswith("#") and href[1:] in page.element_ids, href


# ---------------- (e) the two trees, built from real links only ----------------

def _dev_store(tmp_path, name="project_memory"):
    """A PR with a system requirement, a bug and two tasks under it -- one task per link shape."""
    state = _state(tmp_path, name)
    pr = state.capture("PR", PR_FIELDS)
    sr = state.capture("SR", dict(SR_FIELDS, derives_from=pr["id"]))
    bug = state.capture("BUG", dict(BUG_FIELDS, related_pr=pr["id"]))
    under_sr = state.capture("TSK", dict(TSK_FIELDS, product_requirement=pr["id"],
                                         derives_from=sr["id"]))
    under_root = state.capture("TSK", dict(TSK_FIELDS, product_requirement=pr["id"],
                                           derives_from=pr["id"]))
    return state, pr, sr, bug, under_sr, under_root


def test_a_task_hangs_under_the_item_it_was_cut_from_and_not_under_the_root(tmp_path):
    """FR-0053/3, the placement rule, measured on the rendered tree.

    A `TSK` names TWO real parents -- `product_requirement` (the root it serves) and `derives_from`
    (the item its criteria come from) -- so "the first link that resolves" is not a rule, it is a
    coin toss that always lands on the root. The DEEPEST resolvable parent is the rule, and both
    directions are here: the task cut from the SR sits under the SR at depth 2, the task cut from
    the root itself sits under the root at depth 1. A renderer that took the first field would put
    both at depth 1 and this goes red.
    """
    state, pr, sr, _bug, under_sr, under_root = _dev_store(tmp_path)
    page = _read_board(state)
    assert page.nodes[("system", under_sr["id"])]["parent"] == sr["id"]
    assert page.nodes[("system", under_sr["id"])]["depth"] == 2
    assert page.nodes[("system", under_root["id"])]["parent"] == pr["id"]
    assert page.nodes[("system", under_root["id"])]["depth"] == 1
    assert page.nodes[("system", sr["id"])]["parent"] == pr["id"]
    assert page.nodes[("system", pr["id"])]["depth"] == 0


def test_a_bug_that_names_a_system_requirement_hangs_under_it_rather_than_under_the_root(tmp_path):
    """FR-0054, the half a reader sees: the system tree could only group bugs under the product
    root, because `related_pr` was the only binding a BUG had.

    NO CASE FOR THE NEW FIELD ANYWHERE IN THE RENDERER -- it is a binding field, and the placement
    rule (deepest resolvable parent) does the rest. Both directions, because a renderer that
    simply preferred the new field would pass the first assertion and fail the second: the bug
    that names no SR still hangs from the root.
    """
    state, pr, sr, plain, _under_sr, _under_root = _dev_store(tmp_path)
    named = state.capture("BUG", dict(BUG_FIELDS, related_pr=pr["id"], related_sr=sr["id"]))
    page = _read_board(state)
    assert page.nodes[("system", named["id"])]["parent"] == sr["id"]
    assert page.nodes[("system", named["id"])]["depth"] == 2
    assert page.nodes[("system", plain["id"])]["parent"] == pr["id"]
    assert page.nodes[("system", plain["id"])]["depth"] == 1


def test_children_of_one_parent_stand_under_their_outline_area(tmp_path):
    """FR-0017 on the surface a person reads: the grouping is what an outline IS.

    Until this, `area` reached the page only as a field on a card -- the backlog had an outline
    nothing was outlined by. The tree already groups a parent's children per type (FR-0053); the
    area is the second key of that same grouping, so nothing new decides where an item goes.

    Three properties, and the third is what keeps the field optional: an item that names no area
    keeps the group it always had, the groups of one type are ordered by area, and the UNFILED
    group comes last -- a reader looking for what is not sorted yet finds it in one place.
    """
    state = _state(tmp_path)
    pr = state.capture("PR", PR_FIELDS)
    state.capture("SR", dict(SR_FIELDS, derives_from=pr["id"], area="Zahlung/Karten"))
    state.capture("SR", dict(SR_FIELDS, derives_from=pr["id"], area="Anmeldung"))
    state.capture("SR", dict(SR_FIELDS, derives_from=pr["id"]))
    page = _read_board(state)
    mine = [(area, count) for view, parent, item_type, area, count in page.group_areas
            if view == "system" and parent == pr["id"] and item_type == "SR"]
    assert mine == [("Anmeldung", 1), ("Zahlung/Karten", 1), ("", 1)], mine


def test_a_bug_stands_in_a_group_of_its_own_under_the_root_it_was_recorded_against(tmp_path):
    """The bugs of a root do not belong between its system requirements: FR-0053 asks for a group,
    and the renderer gives EVERY type one, so the ask needs no case of its own. Measured as the
    groups the page actually draws under one parent, with their counts."""
    state, pr, sr, bug, under_sr, _under_root = _dev_store(tmp_path)
    page = _read_board(state)
    under_pr = {(item_type, count) for view, parent, item_type, count in page.groups
                if view == "system" and parent == pr["id"]}
    assert under_pr == {("SR", 1), ("BUG", 1), ("TSK", 1)}, under_pr
    assert page.nodes[("system", bug["id"])]["parent"] == pr["id"]
    assert (("system", sr["id"], "TSK", 1)) in page.groups
    assert page.nodes[("system", under_sr["id"])]["parent"] == sr["id"]


def test_the_product_tree_carries_the_customer_types_and_never_a_task(tmp_path):
    """FR-0053/3: the product backlog is the conversation with the user -- root, requests, change
    requests -- and a task on it would be the work plan leaking into it. The counter-direction is
    the point of the test: the same items ARE on the page, on the board tab and in the system tree,
    so this measures curation and not disappearance."""
    state, pr, sr, bug, under_sr, _under_root = _dev_store(tmp_path)
    request = state.capture("FR", {"title": "make it faster", "request_text": "please",
                                   "related_pr": pr["id"]})
    change = state.capture("CR", {"title": "other checkout", "target_pr": pr["id"],
                                  "target_revision": 1, "change_description": "swap it",
                                  "acceptance_criteria": []})
    page = _read_board(state)
    product = {item_id: node for (view, item_id), node in page.nodes.items() if view == "product"}
    assert set(product) == {pr["id"], request["id"], change["id"]}, sorted(product)
    assert product[request["id"]]["parent"] == pr["id"]
    assert product[change["id"]]["parent"] == pr["id"]
    for absent in (sr["id"], bug["id"], under_sr["id"]):
        assert absent not in product
        assert absent in {item_id for (view, item_id) in page.nodes if view == "system"}
        assert page.where(absent)                       # ...and on the board, as ever


def test_a_procedure_that_names_another_one_is_still_a_root(tmp_path):
    """The one place the tree leaves a real link unused, standing here so it rots visibly.

    A `PROC` may carry `derives_from` (optional, spec II.2) and `ROOT_TYPES` counts it as a root
    anyway: the office kit has no PR and is led by its procedures, so nesting one under another
    would bury that kit's whole backlog a level down. If this ever stops being what we want, this
    is the test that says so.
    """
    state = _state(tmp_path)
    first = state.capture("PROC", PROC_FIELDS)
    second = state.capture("PROC", dict(PROC_FIELDS, title="File a receipt",
                                        derives_from=first["id"]))
    page = _read_board(state)
    for view in ("product", "system"):
        assert page.nodes[(view, second["id"])]["parent"] == ""
        assert page.nodes[(view, second["id"])]["depth"] == 0
        assert not page.nodes[(view, second["id"])]["unassigned"]


def test_an_item_the_tree_cannot_place_is_visible_with_the_reason(tmp_path):
    """The FR-0030 nothing-vanishes property, carried into the trees (FR-0053/3).

    An unplaceable item is the one a curated view would drop most naturally -- it belongs nowhere in
    the hierarchy -- and dropping it is how a backlog view starts lying. So it is IN the page, in a
    group that says what it is, and the view's banner says why it is there. Both are read off the
    rendered page here; the reason itself is measured per case below.
    """
    state = _state(tmp_path)
    pr = state.capture("PR", PR_FIELDS)
    homeless = state.capture("FR", {"title": "no home", "request_text": "please"})
    page = _read_board(state)
    assert page.nodes[("product", homeless["id"])]["unassigned"] is True
    assert page.nodes[("product", homeless["id"])]["parent"] == ""
    assert page.node_titles[("product", homeless["id"])] == "no home"
    unassigned = [entry for entry in page.warnings
                  if entry[3] == "product" and entry[0].startswith("unassigned-")]
    assert len(unassigned) == 1, page.warnings
    assert unassigned[0][1] == "FR" and "related_pr" in unassigned[0][2], unassigned
    # the root beside it is placed as ever -- an Unassigned group that swallows everything is
    # no better than one that swallows nothing
    assert page.nodes[("product", pr["id"])]["unassigned"] is False


def _refused_no_link(state):
    """An FR whose `related_pr` its contract lets it omit -- and it did."""
    state.capture("PR", PR_FIELDS)
    return state.capture("FR", {"title": "no home", "request_text": "please"})["id"], "product"


def _refused_missing_link(state):
    """A TSK with none of the two bindings its contract REQUIRES -- a hand-written file, because
    `capture` refuses it."""
    state.capture("PR", PR_FIELDS)
    _write_item(state, "TSK", "TSK-0001", "id: TSK-0001\ntitle: orphan\nstatus: DRAFT\n")
    state.generate_index()
    return "TSK-0001", "system"


def _refused_off_view(state):
    """An FR pointing at a BUG: a real item on this board, and one the product view does not
    place."""
    pr = state.capture("PR", PR_FIELDS)
    bug = state.capture("BUG", dict(BUG_FIELDS, related_pr=pr["id"]))
    return state.capture("FR", {"title": "sideways", "request_text": "please",
                                "related_pr": bug["id"]})["id"], "product"


def _refused_unknown_link(state):
    """An FR pointing at an id no item carries -- an archived root, or a typo. Hand-written,
    because `capture` refuses a binding it cannot resolve: this shape only ever arrives as a file
    (an edited one, or a root that was archived under it), which is exactly when a view may not
    quietly drop the item."""
    state.capture("PR", PR_FIELDS)
    _write_item(state, "FR", "FR-0001",
                "id: FR-0001\ntitle: dangling\nstatus: NEW\nrequest_text: please\n"
                "related_pr: PR-9999\n")
    state.generate_index()
    return "FR-0001", "product"


def _refused_unreadable(state):
    """A file no parser can read -- it still belongs to a type, so it still belongs in the view."""
    state.capture("PR", PR_FIELDS)
    _write_item(state, "BUG", "BUG-0001", "- a list, not an item\n")
    state.generate_index()
    return "BUG-0001", "system"


_REFUSALS = {
    backlog_tree.NO_LINK: _refused_no_link,
    backlog_tree.MISSING_LINK: _refused_missing_link,
    backlog_tree.OFF_VIEW: _refused_off_view,
    backlog_tree.UNKNOWN_LINK: _refused_unknown_link,
    backlog_tree.UNREADABLE: _refused_unreadable,
}


def test_every_reason_a_tree_can_refuse_an_item_is_one_a_store_can_produce():
    """The tripwire on the reasons, from the dead end: a kind with no message would raise on the
    page, and a kind no store can reach is a case nobody can trigger and nobody can fix.

    THREE MAPS, ONE SET OF REASONS, and the third one was added in TSK-0115 without being read
    here: `_REASON_LABELS` is what the board puts on the refused item's OWN row (DEC-0066 (5)),
    and its comment claimed this test held it against `MESSAGES` in both directions while this
    test never looked at it. Measured with the claim standing: a dead entry left all 69 tests of
    this module green, and a MISSING one turned two others red -- but not this one, the one the
    comment named. Both ends are here now, so the sentence over there is one the code builds.
    """
    assert set(_REFUSALS) == set(backlog_tree.MESSAGES), (
        set(_REFUSALS) ^ set(backlog_tree.MESSAGES))
    assert set(backlog_tree._REASON_LABELS) == set(backlog_tree.MESSAGES), (
        "a reason the page must put a word on, or a word for a reason nothing produces: %s"
        % (set(backlog_tree._REASON_LABELS) ^ set(backlog_tree.MESSAGES),))
    for kind in backlog_tree.MESSAGES:
        assert backlog_tree.reason_label(kind, "FR"), kind


@pytest.mark.parametrize("kind", sorted(_REFUSALS))
def test_the_reason_a_link_did_not_resolve_is_the_one_the_contract_gives(tmp_path, kind):
    """Four ways a link can fail to resolve plus the unreadable file, each on the page with ITS OWN
    reason -- because the remedies differ: a `TSK` without `derives_from` breaks its contract, an
    `FR` without `related_pr` does not (spec II.2 declares it optional), an id that lands on an item
    this view does not place is a third thing, and an id that lands nowhere at all is a fourth. One
    warning for all of them would be one message nobody can act on.
    """
    state = _state(tmp_path, kind.replace("-", "_"))
    item_id, view = _REFUSALS[kind](state)
    page = _read_board(state)
    assert page.nodes[(view, item_id)]["unassigned"] is True
    mine = [entry for entry in page.warnings if entry[3] == view and entry[0] == kind]
    assert len(mine) == 1, (kind, page.warnings)
    assert item_id in mine[0][2], mine


# ---------------- the tree may never fail the state write it is written by ----------------

def test_a_link_that_points_at_itself_cannot_hang_the_state_write(tmp_path):
    """A `derives_from` naming its own item is a legal file, and the placement loop is what such a
    file attacks: an item waiting for itself is never ready, so a loop that waited would spin at the
    end of every state write in that project. It resolves to a warning and the write goes on."""
    state = _state(tmp_path)
    state.capture("PR", PR_FIELDS)
    _write_item(state, "SR", "SR-0001",
                "id: SR-0001\ntitle: itself\nstatus: PROPOSED\nderives_from: SR-0001\n")
    _write_item(state, "SR", "SR-0002",
                "id: SR-0002\ntitle: the other one\nstatus: PROPOSED\nderives_from: SR-0003\n")
    _write_item(state, "SR", "SR-0003",
                "id: SR-0003\ntitle: and back\nstatus: PROPOSED\nderives_from: SR-0002\n")
    state.generate_index()
    item = state.capture("BUG", BUG_FIELDS)          # the NEXT write must go through as well
    page = _read_board(state)
    for stuck in ("SR-0001", "SR-0002", "SR-0003"):
        assert page.nodes[("system", stuck)]["unassigned"] is True
        assert page.where(stuck) == ("SR", "PROPOSED")
    assert page.where(item["id"])[0] == "BUG"


def test_a_long_chain_of_links_still_reaches_the_page(tmp_path):
    """Depth is the items' own doing: a task deriving from a task deriving from a task is a legal
    store, and this renderer runs at the END of every state write.

    WHAT A RECURSIVE WALK COSTS HERE IS NOT AN ERROR, IT IS SILENCE, and that is why the depth is
    worth a test of its own. The RecursionError lands inside `state._write_board`, which is
    deliberately fail-soft: the state write goes through, one line reaches stderr, and the PAGE
    keeps its previous content -- so the tree simply stops telling the truth from the day the chain
    grew. The stack in `board._branches` is what makes the depth cost memory instead of frames. The
    boundary was measured on the recursive version (it kept the page at a few hundred levels and
    lost it a few hundred further on; the round's report carries both depths), and the chain built
    here is past it.
    """
    state = _state(tmp_path)
    pr = state.capture("PR", PR_FIELDS)
    depth = 1200
    previous = pr["id"]
    for number in range(1, depth + 1):
        item_id = "SR-%04d" % number
        _write_item(state, "SR", item_id,
                    "id: %s\ntitle: link %d\nstatus: PROPOSED\nderives_from: %s\n"
                    % (item_id, number, previous))
        previous = item_id
    state.generate_index()
    page = _read_board(state)
    assert page.nodes[("system", "SR-%04d" % depth)]["depth"] == depth
    assert not page.nodes[("system", "SR-%04d" % depth)]["unassigned"]


# ---------------- the modal's references, and what is not on this board ----------------

def test_every_id_a_field_names_opens_that_item_and_an_id_the_board_lacks_does_not(tmp_path):
    """FR-0053/1: linked items are CLICKABLE references, and clicking one opens that item.

    WHICH VALUES BECOME REFERENCES IS A DEFINITION, not a list of fields: anything shaped like an
    id that this board holds an item for. So `dependencies` and a mention inside prose link exactly
    as `derives_from` does, and no field has to be added to a list the day it starts holding a
    reference.

    THE COUNTER-DIRECTION IS THE HALF THAT ROTS: `AC-1` is not an id and must stay text, and an id
    whose item is not on this board -- archived, or a typo -- must stay text too, because a control
    that opens nothing is worse than a plain reference.
    """
    state, pr, sr, _bug, under_sr, _under_root = _dev_store(tmp_path)
    edited = state.update_item(under_sr["id"], {"dependencies": ["SR-9999", sr["id"]]})
    assert edited["dependencies"] == ["SR-9999", sr["id"]]
    page = _read_board(state)
    linked = {ref for detail, ref in page.refs if detail == under_sr["id"]}
    assert linked == {pr["id"], sr["id"]}, linked
    fields = page.details[under_sr["id"]]
    assert "SR-9999" in fields["dependencies"] and "SR-9999" not in linked
    assert "AC-1" in fields["acceptance_refs"] and not any(
        ref.startswith("AC-") for _detail, ref in page.refs)
    # every reference the page draws opens a record that is really on the page
    for _detail, ref in page.refs:
        assert ref in page.details, ref


def test_the_tab_strip_counts_what_the_archive_holds_and_the_board_does_not(tmp_path):
    """FR-0053/2 asks the tabs to carry the archive counts, and the reason is the sentence beside
    them: this board shows `active` items only, so a reader who has archived 77 tasks sees three and
    has no way to tell whether the rest are gone or done. The count is taken from the archive tree
    the kernel itself writes into (`state.archive_path`), so it moves with an archive, and only ids
    of that type are counted -- the staging directories that retire into the same tree are not
    items."""
    state = _state(tmp_path)
    state.generate_index()
    assert _read_board(state).archived == 0
    pr = state.capture("PR", PR_FIELDS)
    state.transition(pr["id"], "REJECTED")
    state.archive(pr["id"])
    page = _read_board(state)
    assert page.archived == 1, page.archived_text
    assert "PR 1" in page.archived_text, page.archived_text
    assert not any(pr["id"] in ids for ids in page.cards.values())

    # THE COUNTER-DIRECTION, and the reason the walk reads `archive/<TYPE>/` rather than the whole
    # archive: `staging.clear_staging` retires whole staging directories into `archive/staging/`,
    # and a staged proposal is not an item. A file in there that LOOKS like an item -- which is
    # exactly what a staged item proposal looks like -- may not move this number.
    staged = os.path.join(state.archive_root(), "staging", "2026", "TSK-0001")
    os.makedirs(staged, exist_ok=True)
    open(os.path.join(staged, "PR-0002.yaml"), "w", encoding="utf-8").write(
        "id: PR-0002\ntitle: a proposal, not an item\n")
    state.generate_index()
    page = _read_board(state)
    assert page.archived == 1, (
        "a staged proposal was counted as an archived item: %s" % page.archived_text)


def test_an_alias_bomb_in_a_binding_field_cannot_stretch_a_state_write(tmp_path):
    """The alias bomb again, one module along -- and the reason the first bomb test could not see it.

    `test_an_alias_bomb_cannot_stretch_a_state_write` puts its bomb in `repro` and `observed`, i.e.
    in fields only the RENDERER walks, where `board._Ink` and `VALUE_MAX_DEPTH` bound it. TSK-0079
    gave the same YAML a second reader: `backlog_tree.parents_of` looks into the BINDING fields, and
    it spelled `str(one)` with no budget around it -- one call that unfolds the whole alias graph,
    which is precisely the defect `board._emit` exists against. Measured on the shipped code before
    the fix: 97.77 s and 480 MB for ONE state write, against 0.02 s without the bomb.

    The bomb sits in `derives_from`, so it is the placement that reads it, and the assertions are
    the ones the older bomb test uses -- allocated memory, page growth and wall clock as the coarse
    net. The item still has to REACH the page: a bound that dropped it would trade one failure for
    the one FR-0030 exists against.
    """
    levels = 24
    state = _state(tmp_path)
    state.capture("PR", PR_FIELDS)
    board_path = os.path.join(state.root, "generated", board.FILENAME)
    before = os.path.getsize(board_path)

    bomb = ["  - &l1 [xxxxxxxxxx, xxxxxxxxxx]"]
    bomb += ["  - &l%d [*l%d, *l%d]" % (n, n - 1, n - 1) for n in range(2, levels + 1)]
    bomb.append("  - [*l%d]" % levels)
    _write_item(state, "SR", "SR-0001",
                "id: SR-0001\ntitle: bound to a bomb\nstatus: PROPOSED\nderives_from:\n%s\n"
                % "\n".join(bomb))
    path = os.path.join(state.root, *ACTIVE_DIRS["SR"].split("/"), "SR-0001.yaml")

    tracemalloc.start()
    started = time.time()
    state.generate_index()
    took = time.time() - started
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert peak < _MEMORY_BUDGET, (
        "placing a %d-byte item allocated %.1f MB" % (os.path.getsize(path), peak / 1024.0 / 1024))
    assert os.path.getsize(board_path) - before < 64 * 1024, "the item stretched the page"
    assert took < _STATE_WRITE_SECONDS, (
        "one binding field stretched a state write to %.1f s" % took)

    page = _read_board(state)
    assert page.where("SR-0001") == ("SR", "PROPOSED")
    assert page.nodes[("system", "SR-0001")]["unassigned"] is True, (
        "a binding that names no id is not a reason to drop the item")


def test_a_value_cut_short_never_offers_a_reference_the_item_does_not_name(tmp_path):
    """A display bound may not invent a link, and this one could.

    `VALUE_MAX_CHARS` cuts wherever the budget runs out, and that can be INSIDE an id: an item
    naming `PR-000199999` was rendered as `PR-0001…`, `_linked` recognised the fragment, and the
    record offered a button that opens a DIFFERENT item -- one the item never named. The whole
    point of the tree rules is that the board invents no link, and this was the same defect on the
    other surface.

    The counter-direction is in the same store: an id that the cut did NOT touch still links, so the
    fix cannot be "stop linking in long values".

    THE FILLER ENDS IN A SPACE, and that is load-bearing rather than cosmetic. `_REFERENCE` matches
    on word boundaries, so a fragment glued to the filler (`xxxPR-0001`) is no match at all and the
    first cut of this test could not fail -- it measured the boundary rule, not the budget. The
    space is what puts the fragment where a reader, and the pattern, see an id.
    """
    state = _state(tmp_path)
    victim = state.capture("PR", PR_FIELDS)                      # PR-0001, really on the board
    assert victim["id"] == "PR-0001"
    other = state.capture("PR", dict(PR_FIELDS, title="the second one"))
    filler = "x" * (board.VALUE_MAX_CHARS - len("PR-0001") - 1) + " "
    item = state.capture("BUG", dict(BUG_FIELDS, related_pr=other["id"],
                                     observed=filler + "PR-000199999 is the one that broke",
                                     expected="see %s" % other["id"]))
    page = _read_board(state)
    assert page.details[item["id"]]["observed"].endswith("…"), (
        "the value was not cut short at all -- there is nothing here to invent a reference from")
    linked = {reference for detail, reference in page.refs if detail == item["id"]}
    assert victim["id"] not in linked, (
        "the budget cut a longer id into a reference to another item: %s" % sorted(linked))
    assert other["id"] in linked, "an id the cut never touched stopped linking"


def test_every_attribute_the_page_script_acts_on_is_one_the_renderer_writes(tmp_path):
    """The markup and the script are ONE mechanism written in two languages, and nothing else in
    this file couples them: rename `data-open` in the renderer alone and every card goes dead while
    all the other checks stay green -- the DOM is intact, the page just stops answering.

    BOTH ENDS, READ OFF THE ARTEFACT. Every `data-` name the script mentions has to exist in the
    page, and every element that LOOKS like a control -- a `<button>` -- has to carry at least one
    name the script acts on. The second half is what makes this a definition rather than a list: a
    dead control is a button the script cannot see, whatever it is called.

    This does not EXECUTE the script; there is no browser in this suite (the module docstring says
    where the click was measured instead). It measures the coupling, which is the half that rots
    silently.
    """
    state, _pr, _sr, _bug, _under_sr, _under_root = _dev_store(tmp_path)
    page = _read_board(state)
    named = set(re.findall(r"data-[a-z-]+", page.script))
    assert named, "the script names no attribute at all -- this check would prove nothing"
    carried = {name for _tag, name, _value in page.attributes}
    assert named <= carried, "the script acts on attributes the page does not write: %s" % (
        sorted(named - carried),)
    dead = [attrs for tag, attrs in page.elements
            if tag == "button" and not (set(attrs) & named)]
    assert not dead, "these controls carry nothing the script acts on: %s" % (dead[:3],)


def test_every_type_that_moves_through_a_lifecycle_is_placed_by_a_backlog_view():
    """The tripwire under the one list FR-0053 could not derive: which types belong in which view.

    BOTH ENDS. A type named by a view that the kernel does not have is a dead entry, and a type
    with an AUTOMATON that no view shows is an item that moves through states and appears in neither
    backlog -- the two ways this curation rots. The automaton is the right side of the second half:
    a type with one is a piece of living work by definition, while a record type (Evidence,
    approvals, the frozen design revisions) has no lifecycle to show in a backlog and belongs on the
    board tab alone.
    """
    named = set(backlog_tree.ROOT_TYPES)
    for view in backlog_tree.VIEWS:
        named.update(view.children)
    assert named <= set(ACTIVE_DIRS), "a view names a type the kernel does not have: %s" % (
        sorted(named - set(ACTIVE_DIRS)),)
    assert set(AUTOMATA) <= named, (
        "these types move through a lifecycle and no backlog view places them: %s"
        % sorted(set(AUTOMATA) - named))
    for item_type in named:
        assert backlog_tree.label(item_type) != item_type, (
            "%s is placed by a view and has no plain-language name" % item_type)


# ---------------- (f) FR-0075: the three numbers a reader looks for first ----------------

def _pending(state, item_id, kind="scope", ttl=3600.0):
    """A real, UNANSWERED approval request -- the shape that makes an item wait on the user.

    Through `approvals.create_pending_request`, never a hand-written file: a request nothing
    produces is a shape the board could agree with while production disagrees. The request does not
    regenerate the index (it is one of the exempted writers), so the caller regenerates.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import approvals
    return approvals.create_pending_request(state, kind, item_id, ttl_seconds=ttl)


def _busy_store(tmp_path, name="project_memory"):
    """One item of each kind the first strip counts: blocked, waiting on the user, in flight."""
    state = _state(tmp_path, name)
    pr = state.capture("PR", PR_FIELDS)
    approve(state, pr["id"], "scope")
    stuck = state.capture("TSK", dict(TSK_FIELDS, product_requirement=pr["id"],
                                      derives_from=pr["id"], blocked_by=pr["id"]))
    moving = state.capture("TSK", dict(TSK_FIELDS, product_requirement=pr["id"],
                                       derives_from=pr["id"]))
    walk_to_status(state, moving, "READY")
    asked = state.capture("BUG", dict(BUG_FIELDS, related_pr=pr["id"]))
    _pending(state, asked["id"])
    state.generate_index()
    return state, pr, stuck, moving, asked


def test_the_first_strip_counts_blocked_waiting_and_in_flight_from_the_state(tmp_path):
    """FR-0075's brief, as three numbers over a real store -- and the number IS the list.

    The failure this is written against is the one every dashboard grows into: a figure computed
    from one walk and a list built from another, drifting apart without anybody noticing because
    both look plausible. So the figure, the list's own `data-count` and the ids actually in the list
    are read off the rendered page and compared.

    READY IS IN FLIGHT, and that is DEC-0065 (4) measured rather than asserted in prose: the task
    walked here sits in READY and lands in the third number, because `board.lane` reads the
    automaton (not the first status, not a last one) instead of a list of statuses. The sentence
    that says so is on the page too -- a rule a reader cannot see is a rule that surprises them.
    """
    state, pr, stuck, moving, asked = _busy_store(tmp_path)
    page = _read_board(state)
    assert page.figures == {"blocked": 1, "you": 1, "flight": 2}, page.figures
    assert page.focus_lists == page.figures, (page.focus_lists, page.figures)
    assert page.focus_rows["blocked"] == [stuck["id"]]
    assert page.focus_rows["you"] == [asked["id"]]
    # the root is APPROVED and the task READY: neither is a first status, neither is a last one,
    # so both are in flight -- the rule, not a list of statuses (DEC-0065 (4))
    assert page.focus_rows["flight"] == [pr["id"], moving["id"]], page.focus_rows["flight"]
    assert state.read_item(moving["id"])["status"] == "READY"
    assert state.read_item(pr["id"])["status"] == "APPROVED"
    assert "READY" in page.rule_text, page.rule_text


def test_an_expired_approval_request_is_not_waiting_on_anyone(tmp_path):
    """A request past its own `expires_at_epoch` can never mint, so nobody owes it an answer.

    The rule is the session brief's and the board now applies it too; the clock both use is the
    stamp of the state write, not a reading of their own (`board._clock`). An expired request that
    still counted would send a user looking for a question they cannot answer.
    """
    state = _state(tmp_path)
    pr = state.capture("PR", PR_FIELDS)
    _pending(state, pr["id"], ttl=-1.0)                     # already expired when it was written
    state.generate_index()
    page = _read_board(state)
    assert page.figures["you"] == 0, page.focus_rows["you"]
    assert page.focus_rows["you"] == []


def _flattened_length(value, priced=None):
    """How long `str(value)` WOULD be, priced over the graph instead of built.

    The alias graph is a DAG of shared lists, so a walk that remembers what it has already priced
    is linear in the levels while `str()` is exponential in them -- which is the whole defect these
    fixtures are about, and the reason this may not simply call `str()` to find out: measuring the
    strength of the bomb would then cost exactly what the bomb costs.
    """
    priced = {} if priced is None else priced
    if id(value) in priced:
        return priced[id(value)]
    if not isinstance(value, (list, tuple)):
        return len(str(value))
    priced[id(value)] = 0                       # a self-referential graph terminates here
    total = 2 + 2 * max(len(value) - 1, 0) + sum(_flattened_length(one, priced) for one in value)
    priced[id(value)] = total
    return total


_BOMB_LEVELS = 21


def _alias_bomb_request(field):
    """A pending request whose `field` is a YAML alias graph -- ~500 bytes, 2**21 values.

    ONE FIXTURE PER FIELD, and that is the point rather than thoroughness. Every field this reader
    renders is its OWN `str()` call, so a defence applied to two of three is a defence nobody
    measures on the third -- which is exactly what happened for a round: the bomb sat in `item`
    only, and dropping the bound on `kind` left the whole module green.

    THE DEPTH IS WHAT GIVES THE ASSERTION ITS MARGIN, and it is written ONCE: the terminal alias is
    derived from `_BOMB_LEVELS` rather than spelled beside it. That coupling is not hypothetical --
    a probe of this round lowered the loop and left the reference at `a20`, so the file no longer
    parsed, the reader skipped it, and the "defect" measured 0.19 MB and looked harmless. A fixture
    that cannot deliver its attack is a test that cannot fail, which is why
    `test_a_request_file_nothing_could_write_costs_neither_the_page_nor_the_write` asserts that the
    file ARRIVES as a container before it asserts anything about the cost.
    """
    plain = {"request_id": "r1", "kind": "scope", "item": "PR-0001"}
    plain.pop(field, None)
    lines = ["%s: %s" % (key, value) for key, value in sorted(plain.items())]
    lines += ["expires_at_epoch: 4102444800", "a0: &a0 [x, x]"]
    for level in range(1, _BOMB_LEVELS):
        lines.append("a%d: &a%d [*a%d, *a%d]" % (level, level, level - 1, level - 1))
    lines.append("%s: *a%d" % (field, _BOMB_LEVELS - 1))
    return "\n".join(lines) + "\n"


# Pending request files `approvals.create_pending_request` CANNOT write -- the ttl is its own
# argument and no command exposes it -- so each of these only ever arrives as a hand-written or
# corrupted file. That is the class this renderer is built against twice over (`board._emit`,
# `backlog_tree.parents_of`), and the board became the first reader of this directory in TSK-0115.
_UNWRITABLE_REQUESTS = {
    "an epoch no platform clock can express":
        "request_id: r1\nkind: scope\nitem: PR-0001\nexpires_at_epoch: 99999999999\n",
    "a float epoch out of range":
        "request_id: r1\nkind: scope\nitem: PR-0001\nexpires_at_epoch: 1e30\n",
    "an alias graph where the item id belongs": _alias_bomb_request("item"),
    # ...and the counter-direction: a field this reader does NOT read may hold anything, and must
    # cost nothing. `request_id` is no longer carried into the strip (`board.open_requests`), so
    # this shape is the evidence that dropping it really dropped the cost with it.
    "an alias graph in a field the board does not read": _alias_bomb_request("request_id"),
    "an alias graph where the approval kind belongs": _alias_bomb_request("kind"),
}


@pytest.mark.parametrize("shape", sorted(_UNWRITABLE_REQUESTS))
def test_a_request_file_nothing_could_write_costs_neither_the_page_nor_the_write(tmp_path, shape):
    """The strip reads a new directory, so the two defences of this module have to reach it.

    WHAT IS MEASURED IS THAT THE PAGE IS REBUILT, not merely that the state write survives -- and
    that distinction is the finding. `state._write_board` is fail-soft by design: an exception in
    the renderer is caught, the write goes through, and the PAGE SILENTLY KEEPS ITS OLD CONTENT.
    So a single unreadable request file does not cost one card, it costs every later board of that
    project, at every state write, until somebody deletes the file. Measured on the code before the
    fix: `time.localtime` raised OSError on one epoch and OverflowError on the other, and the board
    stopped being rebuilt from then on.

    THE OTHER THREE SHAPES ARE THE OTHER DEFENCE: `str()` on an alias graph unfolds the whole graph
    in one call, which no budget can interrupt. Measured before the fix: a 504-byte request file
    rendered a 107 MB page. So the size is asserted against the SAME store without the file rather
    than against a number -- what the file may cost is "about as much as a request", not "less
    than N".

    ONE SHAPE PER FIELD, because the page cannot see all three. `kind` and `item` reach the markup,
    so a bomb in either shows up in the page SIZE; `request_id` reaches nothing a reader sees, and
    a bomb there costs only the time and the memory of building a string that is thrown away. That
    is why the measure here is `tracemalloc` -- the same one
    `test_an_alias_bomb_cannot_stretch_a_state_write` settled on for the same reason -- and not a
    stopwatch: wall-clock separates the two versions only once the intermediate costs hundreds of
    megabytes, while the allocation shows it at once.
    """
    state = _state(tmp_path, shape.replace(" ", "_"))
    pr = state.capture("PR", PR_FIELDS)
    plain = os.path.getsize(os.path.join(state.root, "generated", board.FILENAME))
    pending = os.path.join(state.root, "approvals", "pending")
    os.makedirs(pending, exist_ok=True)
    body = _UNWRITABLE_REQUESTS[shape]
    open(os.path.join(pending, "r1.yaml"), "w", encoding="utf-8").write(body)
    # THE FIXTURE HAS TO BE STRONG ENOUGH TO SHOW THE DEFECT, and being a container is not strong.
    # Everything below is about what one file COSTS, so a bomb whose flattening is shorter than the
    # page proves nothing at all: with a shallow graph the unbounded reader stays under every bound
    # here and the test passes with both defences removed. The subject is therefore the EFFECT --
    # what `str()` on that field would produce, priced over the graph instead of built -- and it
    # has to exceed the page the request is added to. That is what binds `_BOMB_LEVELS` to its own
    # purpose rather than to a number somebody trusts.
    parsed = yaml.safe_load(body)
    assert isinstance(parsed, dict) and parsed.get("expires_at_epoch"), shape
    if "alias graph" in shape:
        bombed = [value for key, value in parsed.items()
                  if key in ("item", "kind", "request_id") and isinstance(value, list)]
        assert len(bombed) == 1, (
            "the alias graph did not resolve into a container: %s" % sorted(parsed))
        flattened = _flattened_length(bombed[0])
        assert flattened > plain, (
            "this bomb flattens to %d characters and the page around it is %d bytes -- it could "
            "not even double the page, so nothing below is evidence" % (flattened, plain))

    tracemalloc.start()
    started = time.time()
    second = state.capture("PR", dict(PR_FIELDS, title="written after the bad file"))
    took = time.time() - started
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    page = _read_board(state)
    index = yaml.safe_load(open(os.path.join(state.root, "generated", "index.yaml"),
                                encoding="utf-8"))
    assert page.generated_at == index["generated_at"], (
        "the board was not rebuilt with this state write -- one unreadable request file froze it")
    assert page.where(pr["id"]) == ("PR", "DRAFT") and page.where(second["id"]) == ("PR", "DRAFT")
    assert page.figures["you"] == 1, "the request itself no longer arrives"
    grown = os.path.getsize(os.path.join(state.root, "generated", board.FILENAME))
    assert grown < plain * 2, (
        "one request file grew the page from %d to %d bytes" % (plain, grown))
    assert peak < _MEMORY_BUDGET, (
        "reading a %d-byte request file allocated %.1f MB"
        % (len(_UNWRITABLE_REQUESTS[shape]), peak / 1024.0 / 1024))
    assert took < _STATE_WRITE_SECONDS, (
        "one request file stretched a state write to %.1f s" % took)



def test_the_board_and_the_session_brief_agree_on_the_open_requests(tmp_path):
    """BUG-0210: two readers of `approvals/pending/` with one rule between them, held against each
    other in the same moment.

    THE SEAM HAS LANDED AND THIS PARAGRAPH SAYS WHAT IS LEFT (measured 2026-09-12). The expiry RULE
    is no longer copied: `approvals.has_expired` / `approvals.open_requests` is the one place that
    says when a request can no longer mint, and both readers ask it -- `approvals.open_requests`
    even takes the optional `now` the seam asked for. What is NOT shared is the WALK, on purpose:
    `board` reads the files through its own `_flat`, because a request file is a hand-written file
    and the page's defence against one nothing could write is its own (`_emit`'s depth bound and
    character budget), and because importing `report` here would close the package's import graph
    into a cycle.

    WHAT THAT LEAVES, and it is the whole of what H126 still is: TWO CLOCKS. The brief reads
    `time.time()`, the page its own stamp, so between two state writes the page can still show a
    request the brief no longer counts. That is deliberate -- the page stays a pure function of the
    state it was rendered from, and it says so in its own head -- and this test is what keeps the
    two honest, because it asks them in ONE moment.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import report
    state = _state(tmp_path)
    pr = state.capture("PR", PR_FIELDS)
    bug = state.capture("BUG", dict(BUG_FIELDS, related_pr=pr["id"]))
    gone = state.capture("PR", dict(PR_FIELDS, title="archived under its own question"))
    _pending(state, pr["id"])
    _pending(state, bug["id"])
    _pending(state, gone["id"])
    _pending(state, bug["id"], ttl=-1.0)                    # expired: open for neither reader
    # ...and one whose ITEM is no longer on the board. A request outlives the item it was asked
    # about, and it is still a question somebody has to answer -- if the board counted only the
    # requests it can put a card behind, it would quietly answer "nothing waits on you" while the
    # brief said otherwise. That is the divergence this test exists for.
    state.transition(gone["id"], "REJECTED")
    state.archive(gone["id"])
    brief = yaml.safe_load(open(report.generate_session_brief(state, "dev-team", "v", "audited"),
                                encoding="utf-8"))
    page = _read_board(state)
    assert gone["id"] not in page.details, "the archived item is still on the board"
    assert sorted(page.focus_rows["you"]) == sorted(row["item"] for row in brief["open_approvals"])
    assert page.figures["you"] == len(brief["open_approvals"]) == 3


def test_a_blocked_card_carries_its_blocker_on_its_face(tmp_path):
    """What is blocked has to be answerable without opening anything -- so the id an item waits for
    is ON the card, not in the record behind it. Both spellings the field takes are the item file's
    own decision (BUG-0015: a binding field is a scalar or a list), so both reach the face."""
    state = _state(tmp_path)
    pr = state.capture("PR", PR_FIELDS)
    approve(state, pr["id"], "scope")
    one = state.capture("TSK", dict(TSK_FIELDS, product_requirement=pr["id"],
                                    derives_from=pr["id"], blocked_by=pr["id"]))
    two = state.capture("TSK", dict(TSK_FIELDS, product_requirement=pr["id"],
                                    derives_from=pr["id"], blocked_by=[pr["id"], "TSK-9999"]))
    asked = state.capture("BUG", dict(BUG_FIELDS, related_pr=pr["id"]))
    _pending(state, asked["id"])
    state.generate_index()
    text = open(os.path.join(state.root, "generated", board.FILENAME), encoding="utf-8").read()
    page = _Board(text)
    faces = {attrs.get("data-open"): attrs.get("class", "") for tag, attrs in page.elements
             if tag == "button" and "card" in (attrs.get("class") or "")}
    assert "blocked" in faces[one["id"]] and "blocked" in faces[two["id"]]
    marks = re.findall(r'<span class="flag">blocked by ([^<]+)</span>', text)
    assert sorted(marks) == sorted([pr["id"], "%s, TSK-9999" % pr["id"]]), marks
    # ...and the second signal of the pair, on the same surface: an item somebody owes an answer
    # for names the KIND of approval, so a reader knows what they are being asked before opening
    # anything
    assert "you" in faces[asked["id"]] and "blocked" not in faces[asked["id"]], faces[asked["id"]]
    assert re.findall(r'<span class="flag">waiting on you: ([^<]+)</span>', text) == [
        "scope approval"]


def test_living_types_precede_records_and_no_type_is_lost(tmp_path):
    """DEC-0065 (3): work first, paperwork filed at the end -- and the filing loses nothing.

    Which half a type belongs to is DERIVED (`board.type_order`: a type with an automaton moves, a
    type without one is written once and looked up), so a type added to the kernel lands in the
    right half the day it ships. The counter-direction is the one that matters: every entry on the
    page is either in a slot or in the records block, and the two together are all of them.
    """
    state = _state(tmp_path)
    pr = state.capture("PR", PR_FIELDS)
    state.capture("EVD", {"kind": "test", "related": [pr["id"]], "result": "pass",
                          "summary": "suite green", "artifact_refs": ["staging/x/log.txt"]})
    page = _read_board(state)
    drawn = list(page.columns)
    assert drawn.index("PR") < drawn.index("EVD"), drawn
    assert page.records_total == 1, page.records_total
    on_page = sorted(item_id for ids in page.cards.values() for item_id in ids)
    assert on_page == sorted(page.details), (on_page, sorted(page.details))
    assert page.tab_counts["board"] == len(on_page) == 2


def test_an_empty_end_state_is_named_not_drawn(tmp_path):
    """BOTH ENDS of the empty rule, on one row.

    An empty slot in the CHAIN stays: the flow reads left to right and a gap in it is information
    ("nothing has reached APPROVED yet"). An empty TERMINAL goes: "0 REJECTED" is the normal state
    of every healthy project, and a page mostly made of such slots was what the design pass measured
    as the reason the shipped board could not be read
    (`project_memory/staging/TSK-0115/01-information-architecture.md`). Neither disappears in
    silence -- the line under the row names both, so the rule cannot quietly become "drop what is
    empty".
    """
    state = _state(tmp_path)
    state.capture("PR", PR_FIELDS)                          # one DRAFT, nothing else
    page = _read_board(state)
    automaton = AUTOMATA["PR"]
    drawn = set(page.columns["PR"])
    assert not (drawn & automaton.terminals), (
        "an end state with no card is drawn: %s" % sorted(drawn & automaton.terminals))
    empty_chain = [status for status in automaton.chain
                   if status != "DRAFT" and status not in automaton.terminals]
    assert set(empty_chain) <= drawn, (empty_chain, sorted(drawn))
    for status in empty_chain:
        assert page.counts[("PR", status)] == 0
    for status in sorted(automaton.terminals):
        assert status in page.empties["PR"], (status, page.empties["PR"])
    assert "no cards in" in page.empties["PR"]


def test_a_task_without_a_title_shows_its_work_on_the_face(tmp_path):
    """A `TSK` owes no `title` -- its contract asks for the kind of work, the item it serves and the
    role that holds it. The shipped board rendered those cards as bare ids, which is what the design
    pass measured. The face is built from the fields the item's own body carries, so nothing is
    invented and no per-type table decides it."""
    state = _state(tmp_path)
    pr = state.capture("PR", PR_FIELDS)
    approve(state, pr["id"], "scope")
    task = state.capture("TSK", dict(TSK_FIELDS, product_requirement=pr["id"],
                                     derives_from=pr["id"]))
    assert "title" not in task
    page = _read_board(state)
    face = page.titles[task["id"]]
    assert TSK_FIELDS["type"] in face and pr["id"] in face and TSK_FIELDS["assigned_role"] in face


def test_an_item_not_under_a_goal_says_what_it_is_in_kit_language(tmp_path):
    """DEC-0066 (5): an `FR` without a `related_pr` breaks no rule -- the kits treat the inbox as
    where a wish waits for triage -- so the page says what the item IS instead of calling it
    unassigned. The word is derived from the type's OWN home directory (`backlog_tree.home_word`),
    so it is the vocabulary the project's tree already uses and there is no second naming to drift.
    """
    state = _state(tmp_path)
    state.capture("PR", PR_FIELDS)
    wish = state.capture("FR", {"title": "no home", "request_text": "please"})
    page = _read_board(state)
    key = ("product", wish["id"])
    assert page.reasons[key] == backlog_tree.NO_LINK
    assert page.reason_words[key] == "inbox — not yet triaged", page.reason_words[key]
    assert "unassigned" not in page.reason_words[key].lower()


def test_every_deep_group_starts_hidden_and_every_root_open(tmp_path):
    """The default the design pass argued for and sighted: roots open, everything below folded.

    A page whose first view is a list of closed roots answers nothing; a fully open system view of
    this repo is far longer than a screen (the design pass counted it,
    `project_memory/staging/TSK-0115/08-final.md`). So the reader meets every root with what hangs
    directly under it, and one click opens the level below. The default is DOM state the renderer writes, which is why
    it can be read here without a browser. Every node with children also has exactly one control,
    and every node without children a spacer -- otherwise the rows do not line up and a node's
    children become unreachable without a mouse.
    """
    state, pr, sr, _bug, _under_sr, _under_root = _dev_store(tmp_path)
    page = _read_board(state)
    for view, parent, item_type, hidden in page.group_hidden:
        depth = page.nodes[(view, parent)]["depth"]
        assert hidden == (depth >= board.FOLD_DEPTH), (view, parent, item_type, depth, hidden)
    assert any(not hidden for *_rest, hidden in page.group_hidden), "nothing is open at all"
    assert any(hidden for *_rest, hidden in page.group_hidden), "nothing is folded at all"
    parents = {(view, parent) for view, parent, _type, _hidden in page.group_hidden}
    for key in page.nodes:
        if key in parents:
            assert key in page.folds and key not in page.fold_spaces, key
        else:
            assert key in page.fold_spaces and key not in page.folds, key
    assert ("system", pr["id"]) in page.folds and ("system", sr["id"]) in page.folds


def test_a_fold_control_states_what_it_hides(tmp_path):
    """A control that says "expanded" over a hidden branch is worse than no control: a screen
    reader is told the opposite of what the page shows. So `aria-expanded` is false exactly when
    that node's groups carry `hidden`, and the control names the node it belongs to."""
    state, _pr, _sr, _bug, _under_sr, _under_root = _dev_store(tmp_path)
    page = _read_board(state)
    hidden_of = {}
    for view, parent, _type, hidden in page.group_hidden:
        hidden_of.setdefault((view, parent), []).append(hidden)
    for key, states in hidden_of.items():
        assert len(set(states)) == 1, ("one node, two fold states", key, states)
        assert page.folds[key] == ("false" if states[0] else "true"), (key, states)
    labels = {attrs["data-fold"]: attrs.get("aria-label") for _tag, attrs in page.elements
              if "data-fold" in attrs}
    assert labels, "no fold control on the page at all"
    for node_id, label in labels.items():
        assert label and node_id in label, (node_id, label)


def test_the_noscript_page_shows_every_group_and_no_fold_control(tmp_path):
    """Without a script the page may not claim a behaviour it no longer has, and it may not hide
    anything behind a control that no longer works.

    The rules are PARSED out of the page's own `<noscript><style>` block -- the thing a browser
    applies -- and not searched for as text in the source file. Every selector whose whole effect is
    script (the tabs, the fold controls, the "Expand all" pair, the three focus figures) is in the
    `display: none` rule, and `[hidden]` is un-hidden, so every folded branch and every record
    stands open instead of being unreachable.
    """
    state, _pr, _sr, _bug, _under_sr, _under_root = _dev_store(tmp_path)
    page = _read_board(state)
    rules = {}
    for block in page.noscript_style.split("}"):
        if "{" not in block:
            continue
        selectors, body = block.split("{", 1)
        for selector in selectors.split(","):
            rules.setdefault(selector.strip(), []).append(body.strip())
    unhidden = " ".join(rules.get("[hidden]", []))
    assert "display: block" in unhidden and "!important" in unhidden, page.noscript_style
    for selector in (".tabs", ".fold", ".tree-tools", ".figures", ".focus-list", ".interactive"):
        assert "display: none" in " ".join(rules.get(selector, [])), (
            "%s still stands on a page whose script never runs" % selector)
    # the controls those rules name are really on the page -- a rule for a selector nothing carries
    # would pass the loop above and protect nothing
    classes = {name for _tag, attrs in page.elements
               for name in (attrs.get("class") or "").split()}
    assert {"fold", "tree-tools", "figures", "focus-list", "tabs"} <= classes, sorted(classes)


def test_the_board_is_a_pure_function_of_the_state_and_the_stamp_it_is_handed(tmp_path):
    """The page reads no clock of its own, so the same state and the same stamp are the same bytes.

    Two things on the page depend on "now" -- whether an approval request has expired and where
    today stands on the ruler -- and both are answered from `generated_at`, the ONE reading the
    index beside it was written from. A `time.time()` in here would make the page disagree with its
    own index by a second often enough to matter, and would make this test flap instead of fail.
    """
    state, _pr, _stuck, _moving, _asked = _busy_store(tmp_path)
    rows = yaml.safe_load(open(os.path.join(state.root, "generated", "index.yaml"),
                               encoding="utf-8"))["items"]
    entries = [(row, state.read_item(row["id"])) for row in rows]
    first = board.render(state, entries, "2026-08-16T12:00:00")
    second = board.render(state, entries, "2026-08-16T12:00:00")
    assert first == second, "the same state and stamp produced two different pages"
    later = board.render(state, entries, "2026-08-16T12:00:01")
    assert later != first, "the stamp does not reach the page at all"
    # ...and the stamp is really the page's clock: the store holds a request that is open by any
    # wall clock (it was created seconds ago with an hour to run), and a page stamped a year out
    # has to call it expired. A `time.time()` in the renderer answers this one differently, which
    # is what makes the claim above falsifiable rather than merely fast enough to be equal twice.
    ahead = _Board(board.render(state, entries, "2027-01-01T00:00:00"))
    assert ahead.figures["you"] == 0, ahead.focus_rows["you"]
    assert _Board(first).figures["you"] == 1


def test_a_stamp_the_board_cannot_read_costs_the_today_marker_and_not_the_page(tmp_path):
    """`generated_at` is a string the caller hands in, so a caller that hands in something else may
    not cost the report. What is lost is exactly the two answers that needed a clock: no today
    marker on the ruler, and no request called expired -- over-reporting an open question is a
    nuisance, dropping one is the failure the strip exists against."""
    state = _state(tmp_path)
    pr = state.capture("PR", PR_FIELDS)
    _pending(state, pr["id"], ttl=-1.0)                     # expired against any real clock
    entries = [({"id": pr["id"], "type": "PR", "title": pr["title"], "status": pr["status"]}, pr)]
    page = _Board(board.render(state, entries, "not a timestamp"))
    assert page.where(pr["id"]) == ("PR", "DRAFT")
    assert page.figures["you"] == 1, "a request was called expired with no clock to judge it by"
    assert board._clock("not a timestamp") == (None, None)


def test_every_type_the_kernel_has_carries_a_plain_language_name():
    """BOTH ENDS of the one list `backlog_tree` cannot derive: what a type is CALLED.

    Since FR-0075 the board heads every row of slots and every block of paperwork with this name, so
    a type missing from the map appears on the page as its own code (`EVD` where "evidence records"
    belongs) and a name for a type the kernel does not have is a promise nobody keeps. Neither end
    is visible from inside the map, which is why they are measured against `ACTIVE_DIRS`.
    """
    assert set(backlog_tree._LABELS) <= set(ACTIVE_DIRS), (
        "named, but no such type: %s" % sorted(set(backlog_tree._LABELS) - set(ACTIVE_DIRS)))
    assert set(ACTIVE_DIRS) <= set(backlog_tree._LABELS), (
        "the kernel has these types and the board would show their code: %s"
        % sorted(set(ACTIVE_DIRS) - set(backlog_tree._LABELS)))
    for item_type in ACTIVE_DIRS:
        assert backlog_tree.label(item_type, 1) != item_type, item_type
        assert backlog_tree.label(item_type, 2) != item_type, item_type


# ---------------- (g) FR-0079: milestones on a timeline (DEC-0064: MST is a TYPE) ----------------

# The type lines DEC-0064 hands to stream C, in one place, so this suite is the arbiter of the
# seam rather than a second opinion about it. Stream A owns the RENDERING; `backlog_types` is
# C-owned, so until C applies these lines a store cannot hold a milestone at all and the fixture
# below installs them for the duration of one test. The day they land, `_milestone_type` compares
# the kernel's with these and goes red on any difference -- which is what makes a hand-off
# measurable instead of hopeful.
_MST_SEAM = {
    "chain": ("PLANNED", "REACHED"),
    "terminals": ("REACHED", "MISSED", "DROPPED"),
    "terminal_from": {"MISSED": ("PLANNED",), "DROPPED": ("PLANNED",)},
    "directory": "milestones/active",
    "required": ("title", "due", "derives_from"),
    "label": ("milestone", "milestones"),
}
MST = board.MILESTONE_TYPE


@pytest.fixture
def milestone_type(monkeypatch):
    """The kernel with DEC-0064's milestone type -- applied by stream C, or installed here.

    Two directions, one fixture. When `backlog_types` already carries the type, every line is
    compared with the decision and a divergence fails HERE, at the arbiter test the seam table
    names. When it does not, the lines are installed for this test only, so the renderer is
    measured against the state it will run in rather than against a type nobody has.

    `PARENT_FIELDS` is not installed as a value of its own: it is DERIVED from the field contract
    (`backlog_types._parent_fields`), so the fixture re-runs that derivation over the patched
    contract and installs its result. A hand-written tuple here would be a second answer to
    "what binds a milestone to its goals".
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import backlog_types
    if MST in backlog_types.ACTIVE_DIRS:                    # the seam has landed
        automaton = backlog_types.AUTOMATA[MST]
        assert automaton.chain == _MST_SEAM["chain"], automaton.chain
        assert automaton.terminals == frozenset(_MST_SEAM["terminals"]), automaton.terminals
        assert backlog_types.ACTIVE_DIRS[MST] == _MST_SEAM["directory"]
        assert backlog_types.REQUIRED_FIELDS[MST] == _MST_SEAM["required"]
        assert backlog_tree._LABELS[MST] == _MST_SEAM["label"]
        return
    monkeypatch.setitem(backlog_types.AUTOMATA, MST, backlog_types._Automaton(
        chain=_MST_SEAM["chain"], terminals=_MST_SEAM["terminals"],
        terminal_from=_MST_SEAM["terminal_from"]))
    monkeypatch.setitem(backlog_types.ACTIVE_DIRS, MST, _MST_SEAM["directory"])
    monkeypatch.setitem(backlog_types.REQUIRED_FIELDS, MST, _MST_SEAM["required"])
    monkeypatch.setitem(backlog_tree._LABELS, MST, _MST_SEAM["label"])
    monkeypatch.setitem(backlog_tree.PARENT_FIELDS, MST,
                        backlog_types._parent_fields()[MST])
    product = backlog_tree.VIEWS[0]
    monkeypatch.setattr(backlog_tree, "VIEWS",
                        (product._replace(children=product.children + (MST,)),)
                        + backlog_tree.VIEWS[1:])


def _milestone(number, due, goals, status="PLANNED", title="a date we owe somebody"):
    """One MST entry the way `state._regenerate_index_locked` would hand it to the renderer."""
    item_id = "%s-%04d" % (MST, number)
    body = {"id": item_id, "title": title, "status": status, "due": due,
            "derives_from": list(goals), "revision": 1, "approval_ref": None}
    row = {"id": item_id, "type": MST, "title": title, "status": status, "revision": 1,
           "approval_ref": None}
    return row, body


def _entries_of(state):
    """(row, body) pairs for everything in the store -- what the kernel hands `board.render`."""
    rows = yaml.safe_load(open(os.path.join(state.root, "generated", "index.yaml"),
                               encoding="utf-8"))["items"]
    return [(row, state.read_item(row["id"])) for row in rows]


def test_a_milestone_stands_on_the_timeline_with_the_goals_it_names(tmp_path, milestone_type):
    """FR-0079's acceptance, rendered: a milestone is an item with a date, a title and the goals it
    is a date for, and what hangs under those goals is counted BY LANE.

    NO PERCENTAGE, and that is not a taste: archived items are not on this board (the kernel's own
    rule), so a share would count the visible half only and read as progress. The counts are the
    ones the system tree already places under the goal, so the timeline and the tree cannot
    disagree about what belongs to a milestone.
    """
    state, pr, _sr, _bug, _under_sr, _under_root = _dev_store(tmp_path)
    entries = _entries_of(state) + [_milestone(1, "2026-09-30", [pr["id"]])]
    page = _Board(board.render(state, entries, "2026-08-16T12:00:00"))
    assert "timeline" in page.views and page.views["timeline"] is True     # hidden, not selected
    assert page.tab_counts["timeline"] == 1
    assert set(page.milestones) == {"%s-0001" % MST}
    assert page.milestone_goals["%s-0001" % MST] == [pr["id"]]
    assert page.milestone_dates["%s-0001" % MST] == "2026-09-30"
    # four items hang under the root in the system tree, all in their first status
    assert "4 planned" in page.milestone_lanes["%s-0001" % MST], page.milestone_lanes
    assert "%" not in page.milestone_lanes["%s-0001" % MST], "a share of an invisible whole"
    assert [item_id for item_id, _cls in page.ticks] == ["%s-0001" % MST]
    assert page.details["%s-0001" % MST]["due"] == "2026-09-30"


def test_a_milestone_past_its_date_and_not_reached_is_late(tmp_path, milestone_type):
    """Late is a question about the DATE and the item's own state, and the state is read the way
    every other item's is: `board.lane` over the type's automaton. A milestone already reached is
    not late however long ago its date was, and one still planned is late the day after."""
    state, pr, _sr, _bug, _under_sr, _under_root = _dev_store(tmp_path)
    entries = _entries_of(state) + [
        _milestone(1, "2026-08-15", [pr["id"]]),                        # yesterday, still planned
        _milestone(2, "2026-08-15", [pr["id"]], status="REACHED"),      # yesterday, reached
        _milestone(3, "2026-09-30", [pr["id"]]),                        # still ahead
    ]
    page = _Board(board.render(state, entries, "2026-08-16T12:00:00"))
    assert page.milestones == {"%s-0001" % MST: True, "%s-0002" % MST: False,
                               "%s-0003" % MST: False}, page.milestones
    marks = dict(page.ticks)
    assert "late" in marks["%s-0001" % MST] and "late" not in marks["%s-0002" % MST]
    assert "done" in marks["%s-0002" % MST], marks


def test_two_milestones_a_day_apart_keep_both_labels(tmp_path, milestone_type):
    """The ruler has three bands so that no two labels can share one: the today marker owns the top
    band, and a tick label that would stand within `board.LABEL_BAND_GAP` per cent of its neighbour
    takes the middle band instead of the bottom one. Measured in a browser by
    `test_board_browser.test_ruler_labels_share_no_band`; here it is the attribute that decides it.
    """
    state, pr, _sr, _bug, _under_sr, _under_root = _dev_store(tmp_path)
    entries = _entries_of(state) + [_milestone(1, "2026-09-01", [pr["id"]]),
                                    _milestone(2, "2026-09-02", [pr["id"]])]
    page = _Board(board.render(state, entries, "2026-08-16T12:00:00"))
    marks = dict(page.ticks)
    assert "up" not in marks["%s-0001" % MST], marks
    assert "up" in marks["%s-0002" % MST], "two labels a day apart stand in one band"
    # ...and two far apart do not pay for it
    entries = _entries_of(state) + [_milestone(1, "2026-09-01", [pr["id"]]),
                                    _milestone(2, "2027-06-01", [pr["id"]])]
    marks = dict(_Board(board.render(state, entries, "2026-08-16T12:00:00")).ticks)
    assert "up" not in marks["%s-0002" % MST], marks


def test_a_milestone_with_an_unreadable_date_is_shown_with_no_date(tmp_path, milestone_type):
    """`capture` refuses a date `date.fromisoformat` cannot read (DEC-0064 (3)), so this shape only
    ever arrives as a hand-written file -- which is exactly when the board may not fail the state
    write it is written by. The card stands, says "no date", and takes no place on the ruler."""
    state, pr, _sr, _bug, _under_sr, _under_root = _dev_store(tmp_path)
    entries = _entries_of(state) + [_milestone(1, "gestern", [pr["id"]]),
                                    _milestone(2, "2026-09-30", [pr["id"]])]
    page = _Board(board.render(state, entries, "2026-08-16T12:00:00"))
    assert page.milestone_dates["%s-0001" % MST] == "no date"
    assert page.milestones["%s-0001" % MST] is False, "a date nobody can read is not late"
    assert [item_id for item_id, _cls in page.ticks] == ["%s-0002" % MST]
    assert page.details["%s-0001" % MST]["due"] == "gestern"      # the file's own value, shown


def test_a_state_without_milestones_offers_no_timeline_tab(tmp_path):
    """A tab for zero milestones is an empty promise -- the design pass sighted exactly that and
    the counter-direction is the test above, where one milestone brings the tab."""
    state, _pr, _sr, _bug, _under_sr, _under_root = _dev_store(tmp_path)
    page = _read_board(state)
    assert "timeline" not in page.views
    assert "timeline" not in {key for key, _selected, _tag in page.tabs}


def test_the_milestone_type_is_wired_completely_or_not_at_all():
    """The tripwire on a half-applied seam, in both directions.

    `board.MILESTONE_TYPE` is the one place stream A names the type; every other property of a
    milestone -- its slots, its lane, its plain-language name, its place in a tree -- is derived
    like any other type's. What can go wrong is a PARTIAL hand-over: a directory without an
    automaton renders a milestone with no lane, an automaton without a label heads its row with a
    code, and a label without a directory is a name for a type no project can hold. So the five
    places are all in, or all out.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import backlog_types
    places = {
        "ACTIVE_DIRS": MST in backlog_types.ACTIVE_DIRS,
        "AUTOMATA": MST in backlog_types.AUTOMATA,
        "REQUIRED_FIELDS": MST in backlog_types.REQUIRED_FIELDS,
        "label": MST in backlog_tree._LABELS,
        "a backlog view": any(MST in view.children for view in backlog_tree.VIEWS),
    }
    assert len(set(places.values())) == 1, (
        "the milestone type is applied in some places and not others: %s" % places)
