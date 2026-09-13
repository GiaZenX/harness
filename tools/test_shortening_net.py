#!/usr/bin/env python3
"""The net the ≤150-line shortening (spec II.11/3) rests on — three measurements, one purpose.

An independent run deleted each of the 16 sections of the dev constitution ONE AT A TIME and ran
all 34 instruction-text tests against every mutant. Only §2 (3 tests) and §7 (1 test) were
noticed; the other 13 sections — roughly 150 lines — could be deleted whole with the suite green.
`tools/validate.py` is no third net for this: it resolves the §-NUMBERS a text cites, so it sees a
missing number and never a missing rule. Whoever performs the shortening today works without
feedback, and the parity matrix that was supposed to BE the feedback carries rows that were wrong
about the code: row 108 was corrected in 2026-07 (filed as "replaced by a gate" with no gate), and
this round measured more — rows 14, 34 and 56 describe a state the code has left, and rows 3, 6,
14, 25, 48, 54, 80, 82, 97 and 99 claimed a replacement that is missing, missing in one of the
kits the rule lives in, or is a PIN on the very text the classification permits deleting.

WHAT THIS MODULE CHECKS, and — as loudly — what it does not:

  * THE MATRIX RESOLVES (§3 of the disposition). A row whose classification is in the document's
    own DELETION-LICENCE list must NAME the replacement as `file.py:symbol`, resolved by AST, and
    must name one for EVERY KIT THE RULE LIVES IN. When the file is a kit hook it must be
    REGISTERED there, under a matcher that can hand it the tools it judges. What this does NOT
    establish is that the named mechanism enforces the named rule: that pairing stays a reading
    decision. Three failures become impossible — licensing a deletion in favour of a replacement
    that is not there, one that is red the moment the licence is used, and one wired under a
    matcher it can never be reached through. The third was PARTIAL until 2026-08-16 and is what
    that round closed: a matcher is judged against the tools a hook declares, and the reader missed
    them wherever the hook bound the tool name to a NAME first (`gate_write_scope`,
    `gate_ledger_valid`) — measured, both `gate_write_scope` registrations replaced by one on
    `matcher: "WebFetch"` and the module stayed green; today that mutation fails
    `test_every_shipped_kit_hook_has_a_registration` and
    `test_every_named_mechanism_resolves_in_the_running_code`. What is left of the caveat is
    COUNTED rather than described (`test_the_licences_resting_on_an_unjudgeable_matcher_are_counted`,
    0 rows today), because a caveat nobody counts is how a hole grows quietly.
  * A PIN IS NOT A REPLACEMENT. `test_hooks_v2.py:test_the_ui_inventory_snapshot_rule_is_shipped`
    READS three shipped instruction texts and fails when the rule is not in them. Named as the
    replacement for parity rows 25/97 it turned the licence upside down: using the licence makes
    the mechanism red. Detected by AST (`_reads_shipped_instructions`) and refused in the licence
    class; the document carries `durch Test GEPINNT → behalten` for that case.
  * THE PINNED INSTRUCTION FILES — constitution, lead agent file and lead SKILL (what spec II.5
    weighs and II.11/3 shortens) PLUS `hooks/ENFORCEMENT.md`, the §2 hook table after it left the
    constitutions. That file is deliberately outside the byte budget — it does not load with a
    session — and just as deliberately inside the pin, because it carries rules. Keeping the two
    subjects apart is `_pinned_files` vs `_lead_package`; collapsing them either way reopens a
    hole. Every section carries a digest of its heading AND its
    body: a deleted section fails on the missing key, a RENAMED one on the changed key, a gutted
    one on the digest. This is deliberately NOT a semantic check — it cannot tell a typo from a
    deleted rule. It converts a silent deletion into a mandatory second look and prints which
    registered hooks the section anchors. `python tools/pin_constitution_sections.py --write`
    re-pins and writes one confirmation line per section into the disposition, so re-pinning
    leaves a trace instead of being a gesture.
  * THE SESSION-START BLOCKS ARE COUNTED TWICE, BY DIFFERENT MEANS. The emission SITES are counted
    by AST, so deleting a block is red even when no input can switch it off; WHICH sites an input
    switches is measured by ablation against the real process. Neither half is redundant: measured,
    the identity line could be deleted in both provider wordings with the whole suite green, and
    the first cut of the census compared raw output between fixtures in different directories, so
    every ablation "changed" the output and a hook with a block removed passed.

The registration reader is the kernel's own (`report._wired_hooks`, `report._invoked_scripts`,
`report._swallows_exit_code`) plus the agents' frontmatter, because a hook is registered on two
surfaces: `settings/settings.json` for the session, and an agent's own `hooks:` block for that
specialist. Reading only the first reported `guard_guidelines` and `format_on_write` as dead code
in the first cut of this module — they are registered per agent, and the "finding" was an artefact
of the reader.
"""
import ast
import functools
import glob
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conftest                                                # noqa: E402
import lead_package                                            # noqa: E402
import parity_sources                                          # noqa: E402
from test_disposition import _cells, _resolve_file, _symbols   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM_KITS = os.path.join(ROOT, "team-kits")
DOC = os.path.join(ROOT, "docs", "reviews", "phase0-disposition.md")
PINS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "constitution_section_pins.json")

sys.path.insert(0, TEAM_KITS)

# The mechanism field marker. One character, so it survives every reflow of the cell it ends.
MECH = "⚙"
OPEN_TOKEN = "offen"
ENTRY_SEPARATOR = " · "


# EVERY CACHED READER, so a test that changes a file can say so. The caches are what took this
# module from 170 s to 12 s, and they are stale by construction: measured, `_registered_hooks`
# still answered 25 after every `PreToolUse` registration was removed, and `_lines()` still
# returned 936 lines over an emptied document. Harmless today — no test in the suite edits a tree
# file and reads it again — but this module is made of mutation tests, and the next one will.
_CACHED_READERS = []


def _cached(function):
    cached = functools.lru_cache(maxsize=None)(function)
    _CACHED_READERS.append(cached)
    return cached


@pytest.fixture(autouse=True)
def _readers_start_cold():
    """Drop every cached answer before each test.

    Per TEST, not per call: within one test the tree does not change under the reader, and paying
    the copytree again for every citation is what the caches were added to stop.
    """
    for reader in _CACHED_READERS:
        reader.cache_clear()
    yield


# --------------------------------------------------------------------------- the matrix reader
@_cached
def _lines():
    """The document, cached as a TUPLE.

    Cached because `_source_kits` alone reads it once per matrix row, and the module's runtime is
    paid by the whole suite. A tuple rather than a list so a caller cannot mutate what the next
    caller reads.
    """
    with open(DOC, encoding="utf-8") as handle:
        return tuple(handle.read().splitlines())


def _reading_view():
    """The document as it READS — a sentence does not stop at a line break, and every figure this
    module asserts is wrapped somewhere."""
    return re.sub(r"\s+", " ", "\n".join(_lines()))


def _matrix_rows():
    """(number, rule, sources, classification) for every row of §3, the parity matrix.

    §3 only: §1's inventory rows and §6's tables have three cells and a different vocabulary, and
    counting them in would answer a question this module is not asking. `_cells` is imported rather
    than rewritten because this document is ABOUT shell metacharacters — three of its rows carry a
    pipe inside a code span, and a naive `split("|")` drops them silently (see `test_disposition`).
    """
    rows, inside = [], False
    for line in _lines():
        if line.startswith("## 3."):
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if not inside or not line.startswith("|"):
            continue
        cells = _cells(line.strip().strip("|"))
        if len(cells) != 4 or not cells[0].isdigit():
            continue
        rows.append(tuple(cells))
    return rows


# A strikethrough span is a WITHDRAWN classification, not a classification. Row 108 reads
# `~~durch Gate ersetzt~~ → behalten (Prosa)`: it says in the document's own vocabulary that the
# gate classification was taken back, and a reader that matched the raw text would demand a
# mechanism from the one row that was corrected precisely because there is none.
_STRIKE_RX = re.compile(r"~~.*?~~")


def _classification_head(classification):
    """The row's DISPOSITION, normalised — without parenthetical, addenda or mechanism field.

    The head is what the document's vocabulary is checked against; everything after the first `(`
    or em-dash is commentary a later round appended. Judging the whole cell would read row 7's
    addendum — which explains what `gate_git` does — as six more classifications.
    """
    head = _STRIKE_RX.sub("", classification.rsplit(MECH, 1)[0])
    for separator in ("(", "—"):
        head = head.split(separator)[0]
    head = re.sub(r"\s+", " ", head.replace("**", "")).strip()
    return head.lstrip("→ ").strip(" .")


def _designation(classification):
    """The classification BEFORE the first dated addendum — what the row said about its mechanism
    when it was written, which is the subject of the starting-point figures."""
    return re.split(r"—\s*\*\*", classification.rsplit(MECH, 1)[0])[0]


def _labelled_terms(label):
    """Every backticked term under a bold label in the document, up to the blank line.

    THE VOCABULARY LIVES IN THE DOCUMENT, not in this file. A list of spellings in a test is the
    shape that produced the next defect one round later here, and a classification the document
    has not declared must fail rather than be silently understood: measured with the head
    `durch Kernel ersetzt` on row 30, a reader that asked `"durch Gate" in head` let the row leave
    the licence class in silence, mechanism field and all.
    """
    collecting, terms = False, []
    for line in _lines():
        if line.startswith("**%s" % label):
            collecting = True
        elif collecting and not line.strip():
            break
        if collecting:
            terms += re.findall(r"`([^`]+)`", line)
    assert terms, "the document declares no %r block" % label
    return terms


def _vocabulary():
    return _labelled_terms("Klassifikationsvokabular")


def _licence_classifications():
    return _labelled_terms("Löschlizenz")


def _licenses_a_deletion(classification):
    """Does this row permit deleting the rule's prose because something else carries it?

    Answered from the document's two declared lists, never from a substring of the head.
    """
    return _classification_head(classification) in _licence_classifications()


def _mechanism_field(classification):
    """The row's mechanism field: everything from the LAST marker to the end of the cell, or None.

    The LAST one, because the field is appended to a cell that in one case carries ten thousand
    characters of addenda, and because taking the first would let a marker character inside that
    prose shadow the real field.
    """
    if MECH not in classification:
        return None
    return classification.rsplit(MECH, 1)[1].strip()


_CITATION_RX = re.compile(r"`([A-Za-z0-9_./-]+\.py):([A-Za-z_][A-Za-z0-9_]*)`")
_ENTRY_PREFIX_RX = re.compile(r"^([a-z]{3}(?:\+[a-z]{3})*):\s*")


# ------------------------------------------------------------------------ kits, roles, sources
@_cached
def _kit_dirs():
    """Every shipped kit — the directories that carry a constitution, taken from the tree."""
    return sorted(os.path.dirname(os.path.dirname(path)) for path in
                  glob.glob(os.path.join(TEAM_KITS, "*", "constitution", "AGENTS.md")))


def _kit_of_shorthand(shorthand):
    """`dev`/`off`/`res` -> the kit directory, by the prefix the document's own legend uses."""
    for kit in _kit_dirs():
        if os.path.basename(kit).startswith(shorthand):
            return kit
    return None


def _names_a_specialist_file(sources):
    """Does this rule also live in a role file outside the lead package?

    DERIVED, not listed. "Specialist file" used to be read off a `Spezialisten:` group in the
    legend; it is now exactly "a source file no section pin watches". The question the count
    answers — "does the parity licence permit deleting prose no section pin watches" — is a
    question about the PIN's subject, so it is answered from the pin's own definition
    (`_pinned_files`) and NOT from the byte budget's subject (`_lead_package`). The two were the
    same set until the §2 hook table moved to `hooks/ENFORCEMENT.md`: that file is pinned (it
    carries rules) and is not in the budget (it does not load with the session), and answering
    this question from the budget would have filed every pointer into it as unwatched prose.
    """
    for pointer in parity_sources.pointers(sources):
        for kit, path, shipped in pointer.targets() or []:
            if shipped and path not in _pinned_files(kit):
                return True
    return False


def _source_kits(sources):
    """Every kit whose text the rule lives in — the licence has to hold in each of them.

    THE OMISSION THIS CLOSES, measured: row 14 names `dev/AGENTS` AND `res/AGENTS` as its sources,
    its mechanism `guard_guidelines.py` shipped in the dev kit only, and a licence checked against
    "the kits that ship the file" was green while it permitted deleting the RESEARCH prose of a
    rule the research kit does not enforce.

    A SHORTHAND THAT RESOLVES TO NOTHING IS A TYPO IN THE COLUMN THE SHORTENING WILL EDIT.
    Measured: row 97's sources set to `zz:30-34; yy:38-41` resolved to NO kits at all, the per-kit
    obligation quietly became empty, and six tests stayed green.
    """
    kits, unknown = set(), []
    for pointer in parity_sources.pointers(sources):
        targets = pointer.targets()
        if targets is None:
            unknown.append(pointer.raw)
            continue
        kits |= {kit for kit, _path, shipped in targets if shipped}
    assert not unknown, (
        "these source pointers name no shorthand the §3 legend maps to a file, so the rule's kits "
        "cannot be resolved: %s (in %r)" % (", ".join(sorted(set(unknown))), sources))
    return kits


def _field_entries(field, source_kits):
    """[(kits, text)] — the mechanism field split into its per-kit entries.

    An entry may be prefixed `dev:` or `dev+res:`; an unprefixed entry covers every source kit no
    prefixed entry claims. The grammar exists because the matrix classifies a rule ONCE while the
    rule lives in up to three kits with different hook inventories.
    """
    entries, claimed, bare = [], set(), []
    for part in [part.strip() for part in (field or "").split(ENTRY_SEPARATOR) if part.strip()]:
        match = _ENTRY_PREFIX_RX.match(part)
        if match:
            kits = {_kit_of_shorthand(name) for name in match.group(1).split("+")}
            kits.discard(None)
            claimed |= kits
            entries.append((kits, part[match.end():].strip()))
        else:
            bare.append(part)
    for part in bare:
        entries.append((set(source_kits) - claimed, part))
    return entries


def _is_open(field):
    return any(text.startswith(OPEN_TOKEN) for _kits, text in _field_entries(field, set()))


# --------------------------------------------------------------- what a registration looks like
def _string_constants(tree):
    """{name: frozenset of strings} for module-level constants that ARE a set of tool names.

    A hook writes `FILE_TOOLS = ("Edit", "Write", …)` beside its docstring and then compares
    `data.get("tool_name")` against the NAME. Reading only literal comparators therefore answered
    "this hook declares no tools" for eight of them — `gate_approval` (`TOOL`), `gate_dispatch` and
    `gate_proc_approved` (`SPAWN_TOOLS`), `gate_push_token` and `gate_shell_hygiene`
    (`SHELL_TOOLS`), `guard_memory_budget` (`FILE_TOOLS`) — and every licence resting on one of
    them was counted as unjudgeable. A single string is a set of one, because `TOOL = "…"` is the
    same declaration with one member.
    """
    values = {}
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            values[node.targets[0].id] = frozenset([value.value])
        elif isinstance(value, (ast.Tuple, ast.List, ast.Set)) and value.elts and all(
                isinstance(element, ast.Constant) and isinstance(element.value, str)
                for element in value.elts):
            values[node.targets[0].id] = frozenset(element.value for element in value.elts)
    return values


def _reads_the_tool_name(node, bound):
    """Does this expression yield the payload's `tool_name`?

    Either the read itself (`data.get("tool_name")`) or a name that HOLDS it. Both spellings are
    one property — "the left operand of this comparison is the tool name" — and reading only the
    first is what this reader got wrong for a round: `gate_write_scope` and `gate_ledger_valid`
    bind it (`tool = data.get("tool_name")`) and dispatch on the NAME two lines down, so the
    literal-shape reader answered `set()` for the most-cited mechanism in the parity table.
    """
    if isinstance(node, ast.Name):
        return node.id in bound
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get" and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "tool_name")


def _own_nodes(scope):
    """Every node of this scope EXCEPT the bodies of the functions nested in it.

    So each statement belongs to exactly one scope and a name can be attributed to the frame it is
    written in — `ast.walk` alone puts every nested function's body into the module's answer, which
    is the confusion the binding reader below was measured to have.
    """
    out, stack = [], list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        out.append(node)
        stack += list(ast.iter_child_nodes(node))
    return out


def _bindings_of(scope):
    """The names THIS scope binds to the payload's tool name — and only those.

    PER SCOPE, and a name is only bound when EVERY assignment to it in the scope reads the tool
    name. Both halves were measured false in the permissive direction as a module-wide answer:
    with `tool = data.get("tool_name")` anywhere in the file, a foreign function writing
    `tool = cfg.get("mode")` and comparing `tool == "WebFetch"` added `WebFetch` to the hook's
    declared tools — `_unjudgeable_matchers` then answered "judged" and `_matcher_reaches` "True"
    for a matcher the hook never sees. No shipped hook has that shape (checked over all three
    kits), which is exactly why the claim had to be measured rather than believed; the probe is in
    `test_the_tool_reader_follows_a_module_constant_and_a_bound_name`.
    """
    reads, rebinds = set(), set()
    for node in _own_nodes(scope):
        if not isinstance(node, ast.Assign):
            continue
        names = {target.id for target in node.targets if isinstance(target, ast.Name)}
        (reads if _reads_the_tool_name(node.value, ()) else rebinds).update(names)
    return reads - rebinds, reads | rebinds


def _scoped_tool_name_bindings(tree):
    """[(scope, names bound to the tool name in it)] — module scope plus every function scope.

    A function inherits the module's bindings for every name it does not assign itself, which is
    what Python does; a name it assigns is its own, and then only its own assignments decide.
    """
    module_bound, module_assigned = _bindings_of(tree)
    scopes = [(tree, module_bound)]
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local_bound, local_assigned = _bindings_of(node)
        scopes.append((node, local_bound | (module_bound - local_assigned)))
    del module_assigned
    return scopes


@_cached
def _declared_tools(path):
    """The tool names a hook judges itself, read from its own `data.get("tool_name")` test.

    A matcher is a tool-name FILTER, so a gate registered on a tool it exits on can never block —
    the shape `report._wired_hooks` calls "a one-token typo silently upgraded a project". Measured
    with `gate_test_coverage` registered on `Read`: the hook exits at its own `tool_name` check,
    and a reader that only asked "is it wired" still certified it as the mechanism behind a
    deletion licence.

    BOTH SIDES OF THE COMPARISON ARE READ THROUGH A DEFINITION rather than a shape, and each half
    was a round's under-report:

      * the COMPARATOR may be a name — `guard_memory_budget` writes
        `data.get("tool_name") not in FILE_TOOLS` with the tuple declared beside its docstring, and
        the literal-only reader answered `set()` for it (`_string_constants`; the pinned count of
        unjudgeable licences fell from 14 to 8 when it landed).
      * the LEFT SIDE may be a name too — `gate_write_scope` and `gate_ledger_valid` bind
        `tool = data.get("tool_name")` and dispatch on `tool` (`_reads_the_tool_name`). Measured
        before this half existed: `_declared_tools` answered `set()` for `gate_write_scope`, the
        most-cited mechanism in the parity table, and eight live deletion licences were counted
        unjudgeable because of it. That binding is read PER SCOPE
        (`_scoped_tool_name_bindings`), because the module-wide first cut let a rebound name in a
        foreign function add a tool the hook never sees.

    An empty answer means the hook does not filter on the tool name at all — every SessionStart
    hook keys off the EVENT instead — and then no matcher over tool names can be judged against it.
    Whether that is a HOLE depends on the registration and not on the hook alone: a matcher that
    selects nothing away has nothing to be wrong about. `_unjudgeable_matchers` is where the two
    halves meet, and the licences left resting on one are counted and pinned by
    `test_the_licences_resting_on_an_unjudgeable_matcher_are_counted`. (An earlier version of this
    line claimed "13 of 29" — measured over hook FILES including `_compat.py`, asserted by nothing,
    and wrong.)
    """
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    constants = _string_constants(tree)
    tools = set()
    for scope, bound in _scoped_tool_name_bindings(tree):
        for node in _own_nodes(scope):
            if not isinstance(node, ast.Compare) or not _reads_the_tool_name(node.left, bound):
                continue
            for comparator in node.comparators:
                if isinstance(comparator, (ast.Tuple, ast.List, ast.Set)):
                    tools |= {e.value for e in comparator.elts
                              if isinstance(e, ast.Constant) and isinstance(e.value, str)}
                elif isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                    tools.add(comparator.value)
                elif isinstance(comparator, ast.Name):
                    tools |= constants.get(comparator.id, frozenset())
    return tools


def _selects_tools(event, matcher):
    """Does this registration's matcher pick TOOL NAMES out of what the event carries?

    Two conditions, and neither is spelled here. WHICH EVENTS match on tools is
    `gen_provider_artifacts.TOOL_MATCHED_EVENTS`, the repo's one answer to that question — the
    generator needs it to translate a matcher for Codex, and a second list in a test module is how
    the last two duplicated readers drifted. WHETHER THE MATCHER PICKS ANYTHING is the provider's
    documented default: `None`, `""` and `*` are "every value", so such a registration reaches the
    hook whatever the event hands it and there is nothing about it a reader could get wrong.

    The shipped counter-cases for both halves: `Notification` under
    `agent_completed|agent_needs_input` names notification KINDS, not tools (all three kits), and
    every `SessionStart`/`SubagentStop` registration carries no matcher at all.

    The import is lazy and carries NO `sys.path` insert — the module-level one above is what makes
    it resolve, exactly as `_registrations` imports the kernel. Inserting here was measured at 15
    `sys.path` entries growing to 126 over one pass across the three kits, because this predicate
    runs once per registration.
    """
    from gen_provider_artifacts import TOOL_MATCHED_EVENTS
    return event in TOOL_MATCHED_EVENTS and matcher not in (None, "", "*")


def _matcher_reaches(event, matcher, tools):
    """Could a registration under this matcher ever hand the hook a tool it acts on?

    A matcher that selects no tools reaches everything (`_selects_tools`); otherwise it is an
    unanchored regex over tool names, and every shipped kit spells it as plain alternatives, so the
    tokens are compared. A hook that declares no tools is not judged here.
    """
    if not tools or not _selects_tools(event, matcher):
        return True
    return bool({token.strip() for token in str(matcher).split("|")} & tools)


@_cached
def _registrations(kit_dir):
    """{hook filename: frozenset of (event, matcher)} — every SHIPPED registration of this kit.

    TWO SURFACES, and reading one of them is how this module's first cut invented a defect:

      * `settings/settings.json`, read with the kernel's own `report._wired_hooks`. That reader
        knows the ways a registration cannot fire (non-`command` type, missing file, a mention
        that is not an invocation, a swallowed exit code) and honours `disableAllHooks`. It KEEPS
        the matcher but does not judge it — that is `_matcher_reaches` here, and claiming
        otherwise in this docstring was itself a defect for one round.
      * the agents' own frontmatter `hooks:` block. `guard_guidelines` and `format_on_write` are
        registered ONLY there — deliberately, because a settings hook fires for the lead too and
        those two are the specialists'. A reader that skipped this surface reported both as dead
        code while both run.

    The second surface is judged with the SAME kernel helpers as the first, so "this command runs
    that file" has one definition in the repo rather than one per reader.

    THE EVENT IS KEPT BESIDE THE MATCHER, and the matcher is not consumed here — the split of
    2026-08-16. What a matcher selects on is a property of its EVENT (`_selects_tools`), so a
    reader that dropped the event could only compare every matcher against tool names; and whether
    a registration can start the hook (`_registered_hooks`) is a different question from whether
    this module can DECIDE that (`_unjudgeable_matchers`), which the old reader answered inside
    itself and left the second question nothing to read.
    """
    from kernel import report
    hooks_dir = os.path.join(kit_dir, "hooks")
    if not os.path.isdir(hooks_dir):
        return {}
    shipped = {name for name in os.listdir(hooks_dir) if name.endswith(".py")}
    found = {}

    def record(name, event, matcher):
        if name in shipped:
            found.setdefault(name, set()).add((event, matcher))

    settings = os.path.join(kit_dir, "settings", "settings.json")
    if os.path.isfile(settings):
        staged = tempfile.mkdtemp(prefix="kit-wiring-")
        try:
            claude = os.path.join(staged, ".claude")
            shutil.copytree(hooks_dir, os.path.join(claude, "hooks"))
            shutil.copy(settings, os.path.join(claude, "settings.json"))
            for name, events in report._wired_hooks(staged).items():
                for event, matchers in events.items():
                    for matcher in matchers:
                        record(name, event, matcher)
        finally:
            shutil.rmtree(staged, ignore_errors=True)

    yaml = pytest.importorskip("yaml")
    for path in sorted(glob.glob(os.path.join(kit_dir, "agents", "*.md"))):
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
        if raw.count("---") < 2:
            continue
        front = yaml.safe_load(raw.split("---", 2)[1]) or {}
        for event, entries in (front.get("hooks") or {}).items():
            for group in entries if isinstance(entries, list) else []:
                if not isinstance(group, dict):
                    continue
                matcher = group.get("matcher")
                for hook in group.get("hooks") or []:
                    if not isinstance(hook, dict) or hook.get("type", "command") != "command":
                        continue
                    command = str(hook.get("command") or "")
                    if report._swallows_exit_code(command):
                        continue
                    for name in report._invoked_scripts(command):
                        record(name, event, matcher)
    return {name: frozenset(entries) for name, entries in found.items()}


def _registered_hooks(kit_dir):
    """{hook filename} — every hook of this kit a SHIPPED registration could actually start."""
    return frozenset(
        name for name, entries in _registrations(kit_dir).items()
        if any(_matcher_reaches(event, matcher,
                                _declared_tools(os.path.join(kit_dir, "hooks", name)))
               for event, matcher in entries))


def _unjudgeable_matchers(kit_dir, name):
    """The registrations of this hook whose matcher this module cannot judge — the hole, as a set.

    A tool matcher is judged against the tool names the hook says it acts on. Two ways there is
    nothing left to judge, and both are properties rather than exemptions: the hook DECLARES its
    tools (then `_matcher_reaches` answers), or the matcher selects no tools at all
    (`_selects_tools` — an absent matcher, and every matcher on an event that does not match on
    tools).

    WHAT THIS DOES NOT ASK, named because the sentence above reads wider than the instrument:
    whether a matcher over ANOTHER vocabulary is right. `notify_agent_events` is registered on
    `Notification` under `agent_completed|agent_needs_input`; that those two kinds exist is
    `gen_provider_artifacts`' subject (it translates them for Codex, and
    `test_every_registration_a_kit_writes_survives_the_codex_translation` measures it), not this
    module's. Reading it here would mean comparing a notification kind against a tool set, which is
    the wrong comparison rather than a stricter one.
    """
    if _declared_tools(os.path.join(kit_dir, "hooks", name)):
        return frozenset()
    return frozenset(entry for entry in _registrations(kit_dir).get(name, ())
                     if _selects_tools(*entry))


def _kit_relative(path):
    """The cited file's path INSIDE its kit, or None when it does not live in one.

    Generalises the per-kit question away from `hooks/`: `kit_checks.py` sits under
    `templates/repo/scripts/` and ships in dev and research only, while parity row 49 sources the
    rule from `audit:26` — the auditor role of ALL THREE kits. The licence therefore covered the
    office auditor's budget prose with a mechanism the office kit does not have, and a check that
    only asked the question for hooks could not see it. The kernel is deliberately NOT kit-relative
    (it is one shared tree), so a kernel citation is not asked this question.
    """
    for kit in _kit_dirs():
        if os.path.abspath(path).startswith(kit + os.sep):
            return os.path.relpath(os.path.abspath(path), kit)
    return None


def _kits_shipping(relative):
    return [kit for kit in _kit_dirs() if os.path.isfile(os.path.join(kit, relative))]


# ------------------------------------------------- a mechanism that READS the text it replaces
def _module_paths(tree, path):
    """{name: absolute path} for module-level constants that name a place in this repo.

    A small evaluator over `__file__`, `os.path.dirname/abspath/join` and string literals — enough
    for the `ROOT`/`TEAM_KITS`/`HOOKS` idiom every module in `tools/` uses, and it RESOLVES rather
    than pattern-matches, so a constant assembled in two steps is followed.
    """
    values = {"__file__": path}

    def evaluate(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return values.get(node.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            arguments = [evaluate(argument) for argument in node.args]
            if not arguments or any(argument is None for argument in arguments):
                return None
            if node.func.attr == "join":
                return os.path.join(*arguments)
            if node.func.attr == "dirname":
                return os.path.dirname(arguments[0])
            if node.func.attr == "abspath":
                return os.path.abspath(arguments[0])
        return None

    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            resolved = evaluate(node.value)
            if resolved:
                values[node.targets[0].id] = resolved
    return values


_READ_CALLS = ("open", "read_text", "read_bytes", "readlines")


@_cached
def _instruction_dirs():
    """The directories a kit ships INSTRUCTION TEXT in — derived from the lead package itself.

    `constitution/`, `agents/`, `skills/` are not typed here: they are the first path segment of
    every file the lead's instruction texts live in — `_lead_package` PLUS
    `lead_package.on_demand_files`, because the lead SKILL stopped being part of what LOADS without
    stopping being instruction text (see `_pinned_files`). Deriving from the loaded half alone
    silently dropped `skills/` the day that split happened, and the probe below went red for two of
    its six cases, which is what it is for. So the day a kit ships its lead instructions from a
    fourth place, this follows. The narrowing matters because "somewhere under `team-kits/`" was
    too wide:
    a swept tree found `generate_dashboard.py:render`, `pii_scan.py:main` and `report_lint.py:lint`
    reading files under a path that resolves inside `team-kits/` in THIS repo and under
    `<project>/scripts/` once installed. None is cited today; the day one is, the licence would
    have been refused for a reason that is not true.
    """
    dirs = set()
    for kit in _kit_dirs():
        for path in _lead_package(kit) + tuple(lead_package.on_demand_files(kit)):
            dirs.add(os.path.relpath(path, kit).replace(os.sep, "/").split("/")[0])
    assert dirs, "no lead package resolved — the instruction directories cannot be derived"
    return frozenset(dirs)


def _reads_shipped_instructions(path, symbol):
    """Does this symbol OPEN a file inside the shipped kit tree?

    THE HEAVIEST CORRECTION OF THIS ROUND. A check that reads a shipped instruction text is a PIN
    on that text — it goes red when the text is deleted. Naming it as the replacement that permits
    deleting the text inverts the licence: `test_the_ui_inventory_snapshot_rule_is_shipped` was
    named that way for parity rows 25 and 97, and deleting the licensed sentence from
    `dev-team/constitution/AGENTS.md` §7 made the "replacement" fail with "constitution\\AGENTS.md
    no longer names the UI inventory snapshot".

    What is detected is a DIRECT read in the cited symbol's own body, resolved through the module's
    path constants. A read behind a helper is not followed, and a hook that locates a file at
    RUNTIME from the project root is not this — the subject is a check that reads the kits out of
    THIS repo. Both limits are named rather than papered over.
    """
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    # `startswith(TEAM_KITS + sep)` alone missed the kit ROOT itself, which is the name every
    # module in `tools/` actually uses (`TEAM_KITS`), so the detector found no pin at all.
    kit_names = set()
    for name, value in _module_paths(tree, path).items():
        resolved = os.path.abspath(value)
        if resolved != TEAM_KITS and not resolved.startswith(TEAM_KITS + os.sep):
            continue
        # a constant that resolves INTO `templates/` belongs to a script the kit installs into a
        # project; in that project the same expression names `<project>/scripts/`, not a kit
        if "templates" in os.path.relpath(resolved, TEAM_KITS).split(os.sep):
            continue
        kit_names.add(name)
    if not kit_names:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != symbol:
            continue
        # WHICH PLACE inside the kit: either a constant already points into an instruction
        # directory, or the body spells one (the shipped case does: `os.path.join("constitution",
        # "AGENTS.md")` beside `os.path.join("skills", …)`).
        spelled = {inner.value for inner in ast.walk(node)
                   if isinstance(inner, ast.Constant) and isinstance(inner.value, str)}
        instruction = _instruction_dirs()
        if not (spelled & set(instruction) or any(
                os.path.relpath(os.path.abspath(_module_paths(tree, path)[name]),
                                TEAM_KITS).replace(os.sep, "/").split("/")[1:2] == [directory]
                for name in kit_names for directory in instruction)):
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            name = inner.func.id if isinstance(inner.func, ast.Name) else (
                inner.func.attr if isinstance(inner.func, ast.Attribute) else "")
            if name not in _READ_CALLS:
                continue
            # THE RECEIVER COUNTS, NOT ONLY THE ARGUMENTS. `Path(TEAM_KITS, …).read_text()` puts
            # the path in `inner.func.value`, so a reader over `inner.args` alone ran zero times
            # for it — `read_text` was listed as covered and was dead code. Measured on a probe
            # module with the same constants: `open(os.path.join(TEAM_KITS, …))` was found,
            # `(Path(TEAM_KITS)/…).read_text()` and `.open()` were not.
            for part in list(inner.args) + [inner.func]:
                for referenced in ast.walk(part):
                    if isinstance(referenced, ast.Name) and referenced.id in kit_names:
                        return True
    return False


# ============================================================ TASK 1 — the matrix as a claim
def test_every_cached_reader_can_be_dropped():
    """The caches are the module's speed and its one way to answer from a tree that has moved.

    Measured, and the reason the autouse fixture above exists: `_registered_hooks` still answered
    25 after every `PreToolUse` registration had been removed, and `_lines()` still returned 936
    lines over an emptied document. No test in the suite edits a tree file and reads it again
    WITHIN one test, so this is a trap rather than a live defect — but this module is made of
    mutation tests and the next one will do exactly that.

    WHAT IS MEASURED HERE, precisely, so the fixture is not credited with more than it does: that
    every cached reader is REGISTERED for clearing and that clearing it works. That the fixture is
    wired autouse is not something this can prove — a test asserting an empty cache at its own
    start passes trivially when it runs first, which under `-n 8` is a coin toss.
    """
    # Six today. The figure is a floor against "the decorator was dropped from all of them", not a
    # census: it fell from eight when the two legend readers were replaced by
    # `parity_sources.source_files`, which reads the document's shorthand->file map instead.
    assert len(_CACHED_READERS) >= 6, len(_CACHED_READERS)
    for reader in _CACHED_READERS:
        assert hasattr(reader, "cache_clear"), reader
    _kit_dirs()
    assert _kit_dirs.cache_info().currsize > 0, "the reader is not caching at all"
    _kit_dirs.cache_clear()
    assert _kit_dirs.cache_info().currsize == 0, "a cleared reader kept its answer"


def test_the_matrix_reader_sees_every_row():
    """A floor. Every derivation below is worthless over a table this reader stopped matching."""
    rows = _matrix_rows()
    numbers = [int(row[0]) for row in rows]
    assert numbers == list(range(1, len(rows) + 1)), numbers[:5] + numbers[-5:]
    assert len(rows) > 100, len(rows)
    heading = [line for line in _lines() if line.startswith("## 3.")]
    assert re.search(r"\(%d Regeln\)" % len(rows), heading[0]), (
        "the §3 heading does not say %d — %r" % (len(rows), heading[0]))


def test_every_classification_is_one_the_document_declares():
    """The head vocabulary is CLOSED, and the document is where it is closed."""
    vocabulary = _vocabulary()
    strangers = sorted({_classification_head(row[3]) for row in _matrix_rows()} - set(vocabulary))
    assert not strangers, (
        "these classifications are not in the vocabulary the document declares (%s):\n  %s"
        % (", ".join(vocabulary), "\n  ".join(strangers)))
    assert set(_licence_classifications()) <= set(vocabulary), (
        "the licence list names a classification the vocabulary does not")


def test_the_licence_reader_separates_a_withdrawn_classification_from_a_live_one():
    """The floor under `_licenses_a_deletion`, and it is not decoration.

    Row 108 is the ONE row a round corrected from "replaced by a gate" to "keep as prose" — by
    striking the old classification through rather than deleting it. A reader over the raw cell
    demands a mechanism from exactly the row that was corrected because none exists; a reader that
    accepted anything would let the shortening delete every rule in the table.
    """
    assert _licenses_a_deletion("durch Gate ersetzt (→GS3; heute guard_pm_scope)")
    assert _licenses_a_deletion("durch Gate+Test ersetzt (BUG VERIFIED via Evidence)")
    assert _licenses_a_deletion("durch Gate ersetzt + behalten")
    assert not _licenses_a_deletion("~~durch Gate ersetzt~~ → **behalten (Prosa)**")
    assert not _licenses_a_deletion("behalten (min-keep)")
    assert not _licenses_a_deletion("bewusst geändert (Kernel wird einziger Schreiber)")
    assert not _licenses_a_deletion("durch Test GEPINNT → behalten (Prosa bleibt)")
    assert not _licenses_a_deletion(
        "behalten — der Nachtrag erklärt, was durch Gate ersetzt WURDE")
    live = [row for row in _matrix_rows() if _licenses_a_deletion(row[3])]
    assert 30 < len(live) < 60, len(live)


def test_the_starting_point_figures_are_the_rows_that_are_there():
    """The four figures the document states about what the matrix named BEFORE this round.

    Disjoint by construction and counted over the DESIGNATION — the classification as written,
    without the dated addenda a later round appended, because an addendum that happens to cite code
    is not the row naming its mechanism. The first version of this sentence said 22/18/13, which
    sums to 53 over 43 rows: the buckets overlapped and nothing said so.
    """
    hookish = re.compile(r"\b((?:gate|guard|notify|session|format|auto|kit)_[a-z_]+)")
    shorthand = re.compile(r"\b(GS[1-5]|APR2)\b")
    counts = {"symbol": 0, "hook": 0, "shorthand": 0, "nothing": 0}
    for row in _matrix_rows():
        if not (_licenses_a_deletion(row[3]) or _mechanism_field(row[3])):
            continue
        text = _designation(row[3])
        if _CITATION_RX.search(text):
            counts["symbol"] += 1
        elif hookish.search(text):
            counts["hook"] += 1
        elif shorthand.search(text):
            counts["shorthand"] += 1
        else:
            counts["nothing"] += 1
    total = sum(counts.values())
    sentence = (r"von %d Zeilen mit Mechanismus-Anspruch nannten %d ein auflösbares Symbol, "
                r"%d einen Hook-Namen im Fliesstext, %d nur ein GS-Kürzel und %d gar nichts"
                % (total, counts["symbol"], counts["hook"], counts["shorthand"],
                   counts["nothing"]))
    assert re.search(sentence, _reading_view()), (
        "the document's starting-point sentence does not match the count: %r over %d rows"
        % (counts, total))


def test_every_row_that_licenses_a_deletion_names_a_replacement():
    """A row in the licence class must carry the mechanism field. No exceptions.

    This is the half that makes the shortening an operation with feedback: the permission to delete
    a rule from the constitution is exactly this classification, so the classification has to say
    WHAT is taking over — in a form something can resolve, not as a hook name in prose.
    """
    naked = [(row[0], _classification_head(row[3])) for row in _matrix_rows()
             if _licenses_a_deletion(row[3]) and _mechanism_field(row[3]) is None]
    assert not naked, (
        "these rows license deleting a rule and name no replacement:\n  "
        + "\n  ".join("#%s %s" % pair for pair in naked))


def test_every_named_mechanism_resolves_in_the_running_code():
    """`file.py:symbol` resolved by AST; a kit hook must be REGISTERED in every kit the rule lives
    in, under a matcher that can reach the tools the hook judges.

    A hook FILE proves that somebody wrote the mechanism; a registration proves it runs; the
    matcher proves it can be handed the calls it acts on. `gate_proc_approved` is the cautionary
    case in this very table — classified "replaced by a gate" while the shipped hook read a store
    that no longer existed, and nothing could say so.
    """
    unresolved = []
    for number, _rule, sources, classification in _matrix_rows():
        field = _mechanism_field(classification)
        if field is None:
            continue
        licensed = _licenses_a_deletion(classification)
        source_kits = _source_kits(sources)
        covered = set()
        for kits, text in _field_entries(field, source_kits):
            covered |= kits
            citations = _CITATION_RX.findall(text)
            if text.startswith(OPEN_TOKEN):
                assert not citations, (
                    "#%s marks an entry `%s` and cites code in it — say one thing"
                    % (number, OPEN_TOKEN))
                continue
            if not citations:
                unresolved.append("#%s carries an entry that cites nothing: %r" % (number, text))
                continue
            for name, symbol in citations:
                path = _resolve_file(name)
                if path is None:
                    unresolved.append("#%s %s:%s — no such file in this repo, or several"
                                      % (number, name, symbol))
                    continue
                if symbol not in _symbols(path):
                    unresolved.append("#%s %s:%s — the file defines no such name"
                                      % (number, name, symbol))
                    continue
                if licensed and _reads_shipped_instructions(path, symbol):
                    unresolved.append(
                        "#%s %s:%s READS the shipped instruction text, so it goes RED when the "
                        "licence is used — that is a pin, not a replacement"
                        % (number, name, symbol))
                    continue
                relative = _kit_relative(path)
                if relative is None:
                    continue        # the kernel: one shared tree, no per-kit question
                for kit in sorted(kits or _kits_shipping(relative)):
                    if not os.path.isfile(os.path.join(kit, relative)):
                        unresolved.append(
                            "#%s %s — the rule lives in %s and that kit does not ship %s"
                            % (number, name, os.path.basename(kit),
                               relative.replace(os.sep, "/")))
                        continue
                    if relative.split(os.sep)[0] != "hooks":
                        continue    # only a hook has a registration to judge
                    if name not in _registered_hooks(kit):
                        unresolved.append(
                            "#%s %s — %s ships the hook and no shipped registration can start it "
                            "for the tools it judges" % (number, name, os.path.basename(kit)))
        if licensed and source_kits - covered:
            unresolved.append(
                "#%s licenses a deletion in %s and its mechanism field says nothing about %s"
                % (number, ", ".join(sorted(os.path.basename(k) for k in source_kits)),
                   ", ".join(sorted(os.path.basename(k) for k in source_kits - covered))))
    assert not unresolved, (
        "the parity matrix points at replacements that are not running:\n  "
        + "\n  ".join(unresolved))


def test_the_open_mechanism_count_is_the_rows_that_are_there():
    """The number of rows carrying an open entry is COUNTED and compared with the sentence.

    A figure nobody asserts drifts — measured inside a single round on the corpus count of the span
    test. Reclassifying these rows is a user decision, so what is pinned is the COUNT.
    """
    open_rows = [row[0] for row in _matrix_rows() if _is_open(_mechanism_field(row[3]))]
    # An empty set gets no parenthesis: `(…)` with nothing in it reads like a list somebody forgot
    # to fill, and after the 2026-08-02 round the honest sentence is that NO row still claims a
    # mechanism it does not have. The count is what is pinned either way.
    tail = (r" \(%s\)" % ", ".join(open_rows)) if open_rows else ""
    assert re.search(r"\*\*%d Zeilen tragen mindestens ein `%s %s`\*\*%s"
                     % (len(open_rows), MECH, OPEN_TOKEN, tail), _reading_view()), (
        "the prose does not say that %d rows are open, or names other rows than %s"
        % (len(open_rows), ", ".join(open_rows) or "none"))


def test_the_number_of_live_deletion_licences_is_stated():
    """The one figure the shortening actually hangs on: how many rules may lose their prose.

    Derived as "in the licence class AND no entry open", so a row covered in dev and open in
    research does not count — the licence has to hold everywhere the rule lives.
    """
    live = [row[0] for row in _matrix_rows()
            if _licenses_a_deletion(row[3]) and not _is_open(_mechanism_field(row[3]))]
    assert re.search(r"\*\*%d Zeilen tragen nach dieser Runde eine wirksame Löschlizenz\*\*"
                     % len(live), _reading_view()), (
        "the document does not state %d live deletion licences" % len(live))


def test_no_mechanism_that_reads_the_shipped_text_carries_a_licence():
    """The general form of the row-25/97 defect, over every cited mechanism.

    Named separately from the resolution test so the detector itself is measured: it must find the
    pin it was written for AND leave the gate mechanisms alone, because a detector that answered
    "yes" to everything would empty the licence class in silence.
    """
    pins, others = [], []
    for row in _matrix_rows():
        for name, symbol in _CITATION_RX.findall(_mechanism_field(row[3]) or ""):
            path = _resolve_file(name)
            if path and _reads_shipped_instructions(path, symbol):
                pins.append((row[0], name, symbol, _licenses_a_deletion(row[3])))
            elif path:
                others.append((row[0], name, symbol))
    assert pins, "the detector finds no pin at all — rows 25/97 name one"
    assert others, "the detector calls every mechanism a pin"
    licensed = [entry for entry in pins if entry[3]]
    assert not licensed, (
        "these rows license a deletion and name a mechanism that reads the very text: %s"
        % ", ".join("#%s %s:%s" % entry[:3] for entry in licensed))


def test_the_pin_detector_reads_the_spellings_it_claims(tmp_path):
    """The floor under `_reads_shipped_instructions`, over a probe carrying every spelling.

    Without it the receiver half of the reader is unmeasured: the only mechanism the matrix cites
    as a pin today uses `open(os.path.join(TEAM_KITS, ...))`, so deleting the `inner.func` walk
    changed nothing the suite could see — measured, the module stayed green with the fix removed.
    A reader whose claimed coverage rests on no case is the same thing as `read_text` being listed
    and never reached, which is exactly the defect this probe was written for.

    The counter-direction is asserted too, so "return True" is not a way out: a read behind a
    HELPER stays undetected (the named limit) and a read of a shipped HOOK is not instruction text.
    """
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import os\n"
        "from pathlib import Path\n"
        "TEAM_KITS = os.path.join(%r)\n" % TEAM_KITS
        + "def by_open():\n"
          "    return open(os.path.join(TEAM_KITS, 'dev-team', 'constitution', 'AGENTS.md')).read()\n"
          "def by_read_text():\n"
          "    return (Path(TEAM_KITS) / 'dev-team' / 'constitution' / 'AGENTS.md').read_text()\n"
          "def by_path_open():\n"
          "    return (Path(TEAM_KITS) / 'dev-team' / 'skills' / 'x' / 'SKILL.md').open().read()\n"
          "def helper(p):\n"
          "    return open(p).read()\n"
          "def by_helper():\n"
          "    return helper(os.path.join(TEAM_KITS, 'dev-team', 'constitution', 'AGENTS.md'))\n"
          "def by_read_bytes():\n"
          "    return (Path(TEAM_KITS) / 'dev-team' / 'agents' / 'x.md').read_bytes()\n"
          "def by_readlines():\n"
          "    return open(os.path.join(TEAM_KITS, 'dev-team', 'skills',"
          " 'x', 'SKILL.md')).readlines()\n"
          "def by_hook():\n"
          "    return open(os.path.join(TEAM_KITS, 'dev-team', 'hooks', 'gate_git.py')).read()\n",
        encoding="utf-8")
    # every name in `_READ_CALLS` has a case here, so removing one from the tuple goes red
    # rather than quietly shrinking the coverage this docstring claims
    seen = {name: _reads_shipped_instructions(str(probe), name)
            for name in ("by_open", "by_read_text", "by_path_open", "by_read_bytes",
                         "by_readlines", "by_helper", "by_hook")}
    assert seen == {"by_open": True, "by_read_text": True, "by_path_open": True,
                    "by_read_bytes": True, "by_readlines": True,
                    "by_helper": False, "by_hook": False}, seen


def test_the_tool_reader_follows_a_module_constant_and_a_bound_name(tmp_path):
    """The floor under `_declared_tools`, and the two defects it was written for.

    BOTH SIDES OF THE COMPARISON, because each of them cost a round:

      * the COMPARATOR as a module constant — the shape `guard_memory_budget` ships
        (`data.get("tool_name") not in FILE_TOOLS`). A reader over literal comparators alone
        answered `set()` for it, which `_matcher_reaches` reads as "this hook cannot be judged,
        assume the matcher reaches", so the hook was filed as matcher-blind and every licence
        resting on it was counted into the pinned figure. Eight shipped hooks have that shape; the
        count fell from 14 to 8.
      * the LEFT SIDE as a bound name — the shape `gate_write_scope` and `gate_ledger_valid` ship
        (`tool = data.get("tool_name")`, then `tool in FILE_TOOLS`). Same silence, same
        consequence: the most-cited mechanism of the parity table declared nothing, and eight
        licences were counted unjudgeable for it. The count fell from 8 to 0.

    All four declaration forms and both comparison shapes are on the probe, so dropping one goes
    red instead of quietly shrinking what this docstring claims. And the counter-direction is
    asserted: a name the module does not declare, a constant that is not a set of strings, and a
    name bound to something OTHER than the tool name must still answer "no tools" — a reader that
    guessed there would certify a matcher against a tool set it invented.

    THE THIRD PROBE IS THE PERMISSIVE DIRECTION, and it is the one the first cut of this fix got
    wrong. The binding was collected module-wide with the claim that over-collecting costs nothing;
    measured, it costs the whole judgement: a hook that binds the tool name in one function and a
    FOREIGN function that rebinds the same name to something else (`tool = cfg.get("mode")`, then
    `tool == "WebFetch"`) made `_declared_tools` answer `WebFetch` as well — and a tool a hook never
    sees, in the set a matcher is judged against, is a licence certified on a registration that
    cannot fire. `_bindings_of` is per scope and drops a name any assignment in that scope rebinds.
    """
    probe = tmp_path / "probe_tools.py"
    probe.write_text(
        "TOOL = 'AskUserQuestion'\n"
        "SPAWN_TOOLS = ('Agent', 'Task')\n"
        "FILE_TOOLS = ['Edit', 'Write']\n"
        "SHELL_TOOLS = {'Bash', 'PowerShell'}\n"
        "NOTEBOOK_TOOLS = ('NotebookEdit',)\n"
        "TIMEOUT = 60\n"
        "def a(data):\n"
        "    return data.get('tool_name') == TOOL\n"
        "def b(data):\n"
        "    return data.get('tool_name') in SPAWN_TOOLS\n"
        "def c(data):\n"
        "    return data.get('tool_name') not in FILE_TOOLS\n"
        "def d(data):\n"
        "    return data.get('tool_name') in SHELL_TOOLS\n"
        "def e(data):\n"
        "    tool = data.get('tool_name')\n"
        "    if tool in NOTEBOOK_TOOLS:\n"
        "        return tool == 'Read'\n"
        "    return False\n", encoding="utf-8")
    assert _declared_tools(str(probe)) == {
        "AskUserQuestion", "Agent", "Task", "Edit", "Write", "Bash", "PowerShell",
        "NotebookEdit", "Read"}

    blind = tmp_path / "probe_blind.py"
    blind.write_text(
        "TIMEOUT = 60\n"
        "def a(data):\n"
        "    return data.get('tool_name') in UNDECLARED\n"
        "def b(data):\n"
        "    return data.get('tool_name') == TIMEOUT\n"
        "def c(data):\n"
        "    return data.get('hook_event_name') == 'SessionStart'\n"
        "def d(data):\n"
        "    event = data.get('hook_event_name')\n"
        "    return event == 'PreToolUse'\n", encoding="utf-8")
    assert _declared_tools(str(blind)) == set()

    # the permissive shape: one function binds the tool name, another rebinds the SAME name
    rebound = tmp_path / "probe_rebound.py"
    rebound.write_text(
        "SHELL_TOOLS = ('Bash', 'PowerShell')\n"
        "def judges(data):\n"
        "    tool = data.get('tool_name')\n"
        "    return tool in SHELL_TOOLS\n"
        "def elsewhere(cfg):\n"
        "    tool = cfg.get('mode')\n"
        "    return tool == 'WebFetch'\n", encoding="utf-8")
    assert _declared_tools(str(rebound)) == {"Bash", "PowerShell"}, (
        "a name another function rebinds is not the tool name there — reading the binding "
        "module-wide put `WebFetch` into the set a matcher is judged against")

    # the shipped cases this was written for, so the probe cannot drift away from the tree. One per
    # comparison shape: the constant on the right, and the tool name bound to a name on the left.
    hooks = os.path.join(_kit_dirs()[0], "hooks")
    budget = os.path.join(hooks, "guard_memory_budget.py")
    assert _declared_tools(budget) == {"Edit", "Write", "MultiEdit", "NotebookEdit"}, \
        _declared_tools(budget)
    scope = os.path.join(hooks, "gate_write_scope.py")
    assert _declared_tools(scope) == {"Edit", "Write", "MultiEdit", "NotebookEdit",
                                      "Bash", "PowerShell"}, _declared_tools(scope)


def test_the_judgeability_question_is_asked_only_of_a_matcher_that_selects_tools(tmp_path):
    """The floor under `_unjudgeable_matchers`, over the four cases its docstring distinguishes.

    A synthetic kit, so the mutation is outside the shipped tree and the four cases stand side by
    side rather than being read off whichever hook happens to ship them today:

      * no declared tools + a tool matcher   -> UNJUDGEABLE. This is the hole the count exists for,
        and without this case "return frozenset()" would pass everything.
      * no declared tools + no matcher       -> judged. `kit_trust_state` and
        `gate_subagent_output` are the shipped case, and it is what took rows 19 and 54 out.
      * declared tools + a tool matcher      -> judged by `_matcher_reaches`.
      * no declared tools + a matcher on an event that does not select tools -> judged, the limit
        the docstring names: `Notification` matches notification kinds, and comparing one against
        a tool set is the wrong question rather than a stricter one.
    """
    kit = tmp_path / "probe-team"
    (kit / "hooks").mkdir(parents=True)
    for name in ("blind_tool_matcher.py", "blind_no_matcher.py", "blind_other_vocabulary.py"):
        (kit / "hooks" / name).write_text(
            'import sys\nif str(data.get("hook_event_name")) != "PreToolUse":\n'
            "    sys.exit(0)\n", encoding="utf-8")
    (kit / "hooks" / "declares.py").write_text(
        'SHELL_TOOLS = ("Bash", "PowerShell")\n'
        'tool = data.get("tool_name")\nif tool not in SHELL_TOOLS:\n    raise SystemExit(0)\n',
        encoding="utf-8")
    (kit / "settings").mkdir(parents=True)
    (kit / "settings" / "settings.json").write_text(json.dumps({"hooks": {
        "PreToolUse": [
            {"matcher": "Bash|PowerShell",
             "hooks": [{"type": "command", "command": "python blind_tool_matcher.py"}]},
            {"matcher": "Bash|PowerShell",
             "hooks": [{"type": "command", "command": "python declares.py"}]},
        ],
        "SubagentStop": [{"hooks": [{"type": "command",
                                     "command": "python blind_no_matcher.py"}]}],
        "Notification": [{"matcher": "agent_completed|agent_needs_input",
                          "hooks": [{"type": "command",
                                     "command": "python blind_other_vocabulary.py"}]}],
    }}), encoding="utf-8")

    verdict = {name: bool(_unjudgeable_matchers(str(kit), name))
               for name in ("blind_tool_matcher.py", "blind_no_matcher.py",
                            "blind_other_vocabulary.py", "declares.py")}
    assert verdict == {"blind_tool_matcher.py": True, "blind_no_matcher.py": False,
                       "blind_other_vocabulary.py": False, "declares.py": False}, verdict
    # and the registration reader agrees that all four run — the judgeability question is about
    # what this module can DECIDE, never about whether the hook is wired
    assert _registered_hooks(str(kit)) == {"blind_tool_matcher.py", "blind_no_matcher.py",
                                           "blind_other_vocabulary.py", "declares.py"}


def test_the_licences_resting_on_an_unjudgeable_matcher_are_counted():
    """How many live licences rest on a registration whose matcher this module CANNOT judge.

    THE COUNT IS 0 SINCE 2026-08-16, and it got there by reading two facts the module already had
    rather than by lowering the bar — both halves are in `_unjudgeable_matchers`:

      * `gate_write_scope` and `gate_ledger_valid` DO declare their tools, through a name
        (`tool = data.get("tool_name")`). The reader now follows that binding, which is what took
        rows 6, 17, 34, 62, 73 and 106 out of this set.
      * `gate_subagent_output` and `kit_trust_state` are registered with NO matcher (`SubagentStop`,
        `SessionStart`). A registration that selects nothing cannot name a tool the hook never
        sees, so there is nothing left to judge — rows 19 and 54. (`_selects_tools` asks the EVENT
        too, and that half takes no row out today: no licence rests on `notify_agent_events`, the
        one hook with a matcher over another vocabulary. Its floor is
        `test_the_judgeability_question_is_asked_only_of_a_matcher_that_selects_tools`.)

    WHAT THIS NUMBER IS NOT, and it read as the other thing for a whole round: it is a statement
    about MATCHER JUDGEABILITY, not about which routes a rule can be broken through. The
    counter-example is in the tree — `guard_pm_scope` declares its tools and is registered on the
    file tools only, so its shell route is open and it is not in this set, nor should it be.

    WHAT IS STILL NOT DERIVED, so a later reader does not read 0 as "solved": the tool class of a
    hook that filters on the PAYLOAD instead of the tool name. The proposal was a table —
    `file_paths` means the file tools, `tool_input.command` the shell tools — which is the
    enumeration of special cases this repo keeps paying for, and it misfires on any hook that
    touches a field for a reason other than acting on it. No shipped hook needs it today; the day
    one does, this number moves and says so.
    """
    resting = []
    for number, _rule, sources, classification in _matrix_rows():
        field = _mechanism_field(classification)
        if not _licenses_a_deletion(classification) or _is_open(field):
            continue
        for kits, text in _field_entries(field, _source_kits(sources)):
            for name, _symbol in _CITATION_RX.findall(text):
                path = _resolve_file(name)
                relative = _kit_relative(path) if path else None
                if not relative or relative.split(os.sep)[0] != "hooks":
                    continue
                if any(_unjudgeable_matchers(kit, os.path.basename(relative))
                       for kit in (kits or _kits_shipping(relative))):
                    resting.append(number)
    resting = sorted(set(resting), key=int)
    # No parenthesis behind an empty set — the same reading decision
    # `test_the_open_mechanism_count_is_the_rows_that_are_there` states for its own list: `(…)`
    # with nothing in it reads like a list somebody forgot to fill. The COUNT is pinned either way.
    tail = (r" \(%s\)" % ", ".join(resting)) if resting else ""
    assert re.search(r"\*\*%d der %d wirksamen Lizenzen ruhen auf einem Hook, dessen Matcher "
                     r"dieses Modul nicht beurteilen kann\*\*%s"
                     % (len(resting),
                        len([row for row in _matrix_rows() if _licenses_a_deletion(row[3])
                             and not _is_open(_mechanism_field(row[3]))]),
                        tail), _reading_view()), (
        "the document does not state that %d licences rest on an unjudgeable matcher (%s)"
        % (len(resting), ", ".join(resting) or "none"))


def _event_handlers(tree):
    """{event: handler name} — the hook's OWN event→symbol mapping, or {} when it declares none.

    A module-level dict from string constants to function names is what `gate_dispatch` and
    `gate_ledger_valid` ship (`HANDLERS = {"PreToolUse": handle_pre_tool_use, …}`) and what their
    `main` dispatches through. Read rather than assumed: this is the file stating which of its
    symbols an event can reach, and nothing else in the repo states it.
    """
    handlers = {}
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)):
            continue
        for key, value in zip(node.value.keys, node.value.values):
            if (isinstance(key, ast.Constant) and isinstance(key.value, str)
                    and isinstance(value, ast.Name)):
                handlers[key.value] = value.id
    return handlers


def _call_graph(tree):
    """{function name: the module functions it calls} — plain names and `self`-less attributes."""
    defined = {node.name for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    graph = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls = set()
        for inner in _own_nodes(node):
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
                calls.add(inner.func.id)
        graph[node.name] = calls & defined
    return graph


def _reached_from(graph, entry):
    """`entry` plus everything it can call, transitively."""
    seen, stack = set(), [entry]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack += list(graph.get(current, ()))
    return seen


def _tool_names(node, constants):
    """The tool names this comparator lists, or None when it lists nothing readable.

    A tuple/list/set of string constants, or a module-level name bound to one -- both are shipped
    shapes (`("Edit", "Write")` and `SPAWN_TOOLS`), and a name this module does not bind answers
    None, which the caller reads as "no constraint" rather than as an empty set.
    """
    if isinstance(node, ast.Name):
        node = constants.get(node.id)
    if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return None
    words = [element.value for element in node.elts
             if isinstance(element, ast.Constant) and isinstance(element.value, str)]
    return frozenset(words) or None


def _tool_guard(statement, constants):
    """The tools a statement still ADMITS, when it is a guard that ENDS the hook for the others.

    THE SHIPPED SHAPE, read off the parse tree and not off a spelling in prose:
    `if data.get("tool_name") not in <tools>: sys.exit(0)` -- ten of them across the three kits'
    hooks today, with the comparator either a literal tuple or a module constant. A `return` counts
    as ending too, because a handler that returns is done.

    Anything else answers None = "this statement constrains nothing", which is the permissive
    direction and is why this reader can only ever add a constraint it really read.
    """
    if not isinstance(statement, ast.If) or len(statement.body) != 1:
        return None
    end = statement.body[0]
    ends = isinstance(end, ast.Return) or (
        isinstance(end, ast.Expr) and isinstance(end.value, ast.Call)
        and ast.unparse(end.value.func) in ("sys.exit", "exit"))
    if not ends:
        return None
    test = statement.test
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1
            and isinstance(test.ops[0], ast.NotIn)):
        return None
    if "tool_name" not in ast.unparse(test.left):
        return None
    return _tool_names(test.comparators[0], constants)


def _narrow(left, right):
    """Two tool constraints intersected; None is "no constraint" and loses to everything."""
    if left is None:
        return right
    if right is None:
        return left
    return left & right


def _widen(left, right):
    """Two constraints a symbol can run under at once; None means "unconstrained on some path"."""
    if left is None or right is None:
        return None
    return left | right


def _module_constants(tree):
    return {target.id: node.value
            for node in tree.body if isinstance(node, ast.Assign)
            for target in node.targets if isinstance(target, ast.Name)}


def _calls_under(scope, constants):
    """[(callee, the tools admitted where it is called)] for one function body, IN ORDER.

    The guards are cumulative down the body: a statement after `if tool_name not in SPAWN_TOOLS:
    sys.exit(0)` runs only for those tools, a statement before it runs for all of them. That
    ordering is the whole point of this reader -- see `_reach_of`.
    """
    admitted, out = None, []
    for statement in scope.body:
        guard = _tool_guard(statement, constants)
        if guard is not None:
            admitted = _narrow(admitted, guard)
            continue
        for inner in ast.walk(statement):
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
                out.append((inner.func.id, admitted))
    return out


def _own_guard(scope, constants):
    """The tools every guard in this function's OWN body admits, intersected."""
    admitted = None
    for statement in scope.body:
        guard = _tool_guard(statement, constants)
        if guard is not None:
            admitted = _narrow(admitted, guard)
    return admitted


@_cached
def _reach_of(path, symbol):
    """{event: the tools admitted where this SYMBOL does its work}, or None for "not narrowed".

    THE MECHANISM FIELD NAMES A SYMBOL, NOT A FILE, and the file-level answer is measurably the
    wrong subject: `gate_dispatch` is registered on six events, two of which Codex has
    (`Stop`, `SubagentStart`), so the FILE runs there while several of its symbols cannot.

    AND THE EVENT ALONE IS NOT THE SUBJECT EITHER, which was measured in this repository with a
    marker written from inside the function against real hook processes (TSK-0149 verify round 1,
    F1): DEC-0107 registered `gate_dispatch` on `PreToolUse` with the matcher `Bash|PowerShell` as
    well, an event-only reader therefore read two of its symbols as Codex-reachable, and the marker
    said entered False on every Bash payload and True only on an Agent one. `handle_pre_tool_use`
    exits unless the tool is in `SPAWN_TOOLS`. So the reader narrows by the TOOL CLASS the handler
    demands as well, and it reads that class off the guard rather than off a list kept here.

    WHERE A SYMBOL DOES ITS WORK is the choice this reader makes, and it is the alarming direction
    on purpose: a function is judged by the guards inside its OWN body as well as by those on the
    way to it. `handle_pre_tool_use` therefore answers `SPAWN_TOOLS` although its first statement
    runs for every tool -- because what the parity matrix cites it FOR (no spawn without an
    approved task) is behind that guard, and a reader answering "reachable" here would say a Codex
    session is covered where it is not. The opposite choice is the reassuring one, and house rule 3
    forbids that as firmly as the alarming one.

    None means the question does not narrow: the hook declares no handler map (then every
    registration runs its `main` end to end), or the symbol is reachable from a scope no handler
    owns -- `main` itself is the shipped case of that.
    """
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    handlers = _event_handlers(tree)
    if not handlers:
        return None
    constants = _module_constants(tree)
    scopes = {node.name: node for node in ast.walk(tree)
              if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    reach = {}
    for event, handler in handlers.items():
        if handler not in scopes:
            continue
        answer, stack, seen = {}, [(handler, None)], set()
        while stack:
            name, context = stack.pop()
            if (name, context) in seen or name not in scopes:
                continue
            seen.add((name, context))
            runs_under = _narrow(context, _own_guard(scopes[name], constants))
            answer[name] = runs_under if name not in answer else _widen(answer[name], runs_under)
            for callee, prefix in _calls_under(scopes[name], constants):
                stack.append((callee, _narrow(context, prefix)))
        if symbol in answer:
            reach[event] = answer[symbol]
    return reach or None


def _events_reaching(path, symbol):
    """The events under which this SYMBOL can run, or None -- the event half of `_reach_of`."""
    reach = _reach_of(path, symbol)
    return frozenset(reach) if reach else None


def _matcher_admits(matcher, tools):
    """Does this registration's matcher name a tool the symbol's guard still admits?

    A matcher of `None` or `*` is every tool, so it admits whatever the guard asks for; anything
    else is the alternation the provider writes (`Agent|Task`, `Bash|PowerShell`), and the question
    is whether the two sets meet. `tools` of None is "the symbol demands no class" and admits every
    matcher -- the permissive end, and the one every hook without a tool guard lands on.
    """
    if tools is None:
        return True
    if matcher in (None, "", "*"):
        return True
    return bool({word.strip() for word in str(matcher).split("|") if word.strip()} & tools)


def _reaches_codex(kit_dir, name, symbol=None):
    """Can any shipped registration start this MECHANISM under Codex?

    Asked of the generator that writes the Codex artifacts, never of a second table here:
    `CODEX_EVENTS` says which events exist there and `codex_matchers_for` translates the matcher,
    contributing nothing for a tool `CODEX_UNSUPPORTED_TOOLS` declares. An empty translation is
    therefore "this registration does not exist on Codex" -- and the empty TUPLE is the answer to
    read, not the truthiness of its members: a matcher of `None` translates to `(None,)`, which is
    one registration and not none (measured while writing this: `any(...)` read that as no
    registration and filed every `SessionStart` hook as Codex-blind).

    TWO NARROWINGS, NOT ONE, and the second was bought with a measured wrong count (TSK-0149 verify
    round 1, F1): the registrations are narrowed to the ones whose EVENT reaches `symbol`, and the
    surviving matchers are then narrowed to the ones naming a TOOL the symbol's own guard still
    admits (`_reach_of`). Without the second, a `PreToolUse('Bash|PowerShell')` entry made every
    `PreToolUse` symbol of `gate_dispatch` look Codex-covered while the handler exits on any tool
    outside `SPAWN_TOOLS`. With no symbol the question is asked of the FILE, which is the weaker
    question and is why the callers pass one.
    """
    from gen_provider_artifacts import CODEX_EVENTS, codex_matchers_for
    reach = _reach_of(os.path.join(kit_dir, "hooks", name), symbol) if symbol else None
    for event, matcher in _registrations(kit_dir).get(name, ()):
        if reach is not None and event not in reach:
            continue
        if event not in CODEX_EVENTS:
            continue
        tools = reach[event] if reach is not None else None
        for translated in codex_matchers_for(event, matcher):
            if _matcher_admits(translated, tools):
                return True
    return False


def test_the_licences_whose_mechanism_cannot_run_on_codex_are_counted():
    """The limit this round measured, and the reason it belongs beside the other two counts.

    A kit ships for two providers, and its constitution is loaded by BOTH. Where the replacing
    mechanism is registered only on tools Codex has no equivalent for, deleting the prose does not
    move the rule from the text into the gate — it deletes the only carrier the Codex session has.
    Two shipped hooks say so in their own words (`guard_agent_spawn`: "on Codex no spawn hook runs
    at all and the rule binds through the constitution alone"; `gen_provider_artifacts`'
    `AskUserQuestion` note for `guard_question_context`), and the office constitution states it for
    its own §1 ("On Codex this binds as POLICY only"). Counted here instead of remembered.

    THE SUBJECT IS THE CITED SYMBOL, not the file that holds it, and the first cut of this test got
    that wrong: `gate_dispatch` runs on two events Codex has, so file-wise it "runs there", while
    rows 4 and 54 name `handle_pre_tool_use` and `_refuse_untrusted_bundle` — bound by the hook's
    own `HANDLERS` to `PreToolUse('Agent|Task')` and reachable through nothing else. Both were
    missing from the count while this docstring quoted `guard_agent_spawn`'s Codex sentence.
    `_events_reaching` is the narrowing, and mutating it back to the file question turns this red.

    A ROW COUNTS WHEN ONE OF ITS NAMED MECHANISMS IS OUT, not only when all of them are: the field
    names what takes the rule over, so a half that Codex cannot start is prose the Codex session
    still needs. Row 54 is exactly that shape — `kit_trust_state.transition` runs there,
    `gate_dispatch._refuse_untrusted_bundle` does not.

    WHAT IS PINNED IS THE COUNT, as with the other two: which rows they are is a fact about the
    registrations, and reclassifying a row is a user decision. What the number is FOR is the
    executor of the next shortening pass — these rows are the ones a standing licence does not make
    cuttable.
    """
    blind = []
    for number, _rule, sources, classification in _matrix_rows():
        field = _mechanism_field(classification)
        if not _licenses_a_deletion(classification) or _is_open(field):
            continue
        for kits, text in _field_entries(field, _source_kits(sources)):
            for name, symbol in _CITATION_RX.findall(text):
                path = _resolve_file(name)
                relative = _kit_relative(path) if path else None
                if not relative or relative.split(os.sep)[0] != "hooks":
                    continue
                if any(not _reaches_codex(kit, os.path.basename(relative), symbol)
                       for kit in (kits or _kits_shipping(relative))):
                    blind.append(number)
    blind = sorted(set(blind), key=int)
    tail = (r" \(%s\)" % ", ".join(blind)) if blind else ""
    assert re.search(r"\*\*%d der %d wirksamen Lizenzen ruhen auf einem Mechanismus, den Codex "
                     r"nicht starten kann\*\*%s"
                     % (len(blind),
                        len([row for row in _matrix_rows() if _licenses_a_deletion(row[3])
                             and not _is_open(_mechanism_field(row[3]))]),
                        tail), _reading_view()), (
        "the document does not state that %d licences rest on a mechanism Codex cannot start (%s)"
        % (len(blind), ", ".join(blind) or "none"))


def test_the_codex_reader_separates_a_spawn_hook_from_a_shell_hook():
    """The floor under `_reaches_codex`: a reader answering the same for both closes nothing.

    Over the shipped tree in both directions, because each direction is a different failure. A
    reader that answered "reachable" everywhere would empty the count above; one that answered
    "blind" everywhere would refuse every licence with a reason that is not true. `guard_agent_spawn`
    is registered on `Agent|Task` only — the declared gap — and `gate_write_scope` on the file and
    shell tools, which Codex has.
    """
    kit = _kit_dirs()[0]
    assert not _reaches_codex(kit, "guard_agent_spawn.py"), (
        "`Agent`/`Task` is in CODEX_UNSUPPORTED_TOOLS, so no Codex registration starts this hook")
    assert _reaches_codex(kit, "gate_write_scope.py")
    assert _reaches_codex(kit, "session_status.py"), (
        "a SessionStart registration carries no matcher and exists on Codex — the empty-tuple "
        "reading of `codex_matchers_for` is what this asserts")


def test_the_codex_reader_asks_about_the_symbol_and_not_only_its_file():
    """The floor under `_reach_of`: file, event and TOOL CLASS are three different subjects.

    `gate_dispatch.py` is registered on six events; `Stop` and `SubagentStart` exist on Codex, so
    the FILE runs there. Its `HANDLERS` bind `handle_post_tool_use` to `PostToolUse` alone, whose
    matcher is `Agent|Task` -- tools `CODEX_UNSUPPORTED_TOOLS` declares, so that registration
    translates to nothing and the SYMBOL cannot run there. That is the event half.

    AND THE TOOL HALF, which was measured wrong in this repository before it existed (TSK-0149
    verify round 1, F1, with a marker written from inside the function against real hook
    processes): DEC-0107 registered the same file on `PreToolUse` with the matcher
    `Bash|PowerShell`. An event-only reader concluded that `handle_pre_tool_use` and
    `_refuse_untrusted_bundle` had become Codex-reachable and the shipped review document lost two
    rows off its Codex-blind count -- while the marker said entered False on every Bash payload,
    because the handler exits unless the tool is in `SPAWN_TOOLS`. The three assertions in the
    middle are that difference: the symbol BEFORE the guard really is reachable on Codex now, and
    the two behind it are not.

    The last three are the permissive directions `_reach_of` names: a handler on a Codex event with
    no tool guard IS reachable, a symbol no handler owns (`main`) narrows nothing, and the file
    answers when no symbol is asked.
    """
    kit = _kit_dirs()[0]
    dispatch = os.path.join(kit, "hooks", "gate_dispatch.py")
    assert _reaches_codex(kit, "gate_dispatch.py"), "the FILE has Codex-reachable registrations"

    # the EVENT half
    assert _events_reaching(dispatch, "handle_post_tool_use") == frozenset(["PostToolUse"])
    assert _events_reaching(dispatch, "handle_spawn_failure") == frozenset(["PostToolUseFailure"])
    assert not _reaches_codex(kit, "gate_dispatch.py", "handle_post_tool_use")
    assert not _reaches_codex(kit, "gate_dispatch.py", "handle_spawn_failure")

    # the TOOL half, on the ONE event Codex and this hook really share for a tool it has
    spawn_only = _reach_of(dispatch, "_refuse_untrusted_bundle")["PreToolUse"]
    assert spawn_only and "Bash" not in spawn_only, (
        "the reader does not see the tool guard `handle_pre_tool_use` puts in front of this "
        "symbol, so a `Bash` registration reads as coverage it is not: %r" % (spawn_only,))
    assert not _reaches_codex(kit, "gate_dispatch.py", "_refuse_untrusted_bundle")
    assert not _reaches_codex(kit, "gate_dispatch.py", "handle_pre_tool_use")
    assert _reach_of(dispatch, "_refuse_a_classification_the_judged_role_wrote") == {
        "PreToolUse": None}, (
        "the symbol that runs BEFORE the guard must stay unconstrained -- it is the one thing the "
        "new registration really did add on Codex, and a reader that lost it would over-report")
    assert _reaches_codex(kit, "gate_dispatch.py",
                          "_refuse_a_classification_the_judged_role_wrote")

    # the permissive directions
    assert _reaches_codex(kit, "gate_dispatch.py", "handle_stop"), (
        "`Stop` is a Codex event and its handler carries no tool guard -- a reader that answered "
        "'blind' for every symbol of this file would count rows that are not blind")
    assert _events_reaching(dispatch, "main") is None


def test_the_licences_whose_rule_also_lives_in_a_specialist_file_are_counted():
    """The limit of the section pin, DERIVED — the last figure in that paragraph that was prose.

    Of the four numbers in it, three were counted by tests and one was written by hand, and the
    hand-written one drifted inside this very round: it listed row 49, which the per-kit correction
    (N6) had just made open, so it was no longer a live licence at all. Counted here, the set is
    17 again but not the same 17 — 49 out, 88 in (`res/re:22-30`, a kit-prefixed specialist source
    the prose had missed). A number that agrees with the old one by accident is the strongest
    argument for deriving it.

    What it means for the shortening: for these rows the parity licence permits deleting prose that
    ALSO stands in a specialist SKILL or agent file, and no pin watches those — measured by
    deleting "Never change SRs, architecture, or requirements." from
    `skills/backend-developer/SKILL.md` with the suite green.
    """
    live = [row for row in _matrix_rows()
            if _licenses_a_deletion(row[3]) and not _is_open(_mechanism_field(row[3]))]
    outside = [row[0] for row in live if _names_a_specialist_file(row[2])]
    assert re.search(r"%d der %d wirksamen Lizenzen\*\* \(%s\)"
                     % (len(outside), len(live), ", ".join(outside)), _reading_view()), (
        "the document does not state that %d of %d live licences also live in a specialist file "
        "(%s)" % (len(outside), len(live), ", ".join(outside)))


def test_the_registration_reader_can_tell_a_dead_hook_from_a_live_one(tmp_path):
    """The floor under `_registered_hooks`: a reader that answers "registered" to everything makes
    every check above pass over any table at all.

    Five shapes in ONE synthetic kit, each a way a registration exists or does not: wired in
    settings, wired in an agent's frontmatter, shipped and wired nowhere, wired with its exit
    status thrown away (`; exit 0`), and wired under a matcher naming only tools the hook exits on.
    The last two must not count.
    """
    kit = tmp_path / "fake-team"
    (kit / "hooks").mkdir(parents=True)
    for name in ("live_settings.py", "live_frontmatter.py", "orphan.py", "swallowed.py",
                 "wrong_matcher.py"):
        (kit / "hooks" / name).write_text(
            'import sys\nif data.get("tool_name") not in ("Bash", "PowerShell"):\n'
            "    sys.exit(0)\n", encoding="utf-8")
    (kit / "constitution").mkdir(parents=True)
    (kit / "constitution" / "AGENTS.md").write_text("# x\n", encoding="utf-8")
    (kit / "settings").mkdir(parents=True)
    (kit / "settings" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Bash|PowerShell",
         "hooks": [{"type": "command", "command": "python live_settings.py"}]},
        {"matcher": "Bash|PowerShell",
         "hooks": [{"type": "command", "command": "python swallowed.py; exit 0"}]},
        {"matcher": "Read", "hooks": [{"type": "command", "command": "python wrong_matcher.py"}]},
    ]}}), encoding="utf-8")
    (kit / "agents").mkdir(parents=True)
    (kit / "agents" / "role.md").write_text(
        "---\nname: role\nhooks:\n  PreToolUse:\n    - matcher: Bash\n      hooks:\n"
        "        - type: command\n          command: python live_frontmatter.py\n---\nbody\n",
        encoding="utf-8")
    assert _registered_hooks(str(kit)) == {"live_settings.py", "live_frontmatter.py"}


def test_every_shipped_kit_hook_has_a_registration():
    """The general form of the same question over the real kits: a hook nobody can start is dead
    weight in the hashed bundle, and this is what makes the registration check meaningful rather
    than a formality nobody could ever trip.
    """
    dead = []
    for kit in _kit_dirs():
        hooks_dir = os.path.join(kit, "hooks")
        shipped = {name for name in os.listdir(hooks_dir)
                   if name.endswith(".py") and not name.startswith("_")}
        dead += ["%s/%s" % (os.path.basename(kit), name)
                 for name in sorted(shipped - _registered_hooks(kit))]
    assert not dead, "these hooks ship and no registration can start them: %s" % ", ".join(dead)


# The case-exact tree reader lives in `conftest.py`: the entry-gate sweep in `test_hooks.py` asks
# the same question of the two global instruction files, and two copies of "what does this tree call
# its files" would drift the way every other duplicated reader in this repo has. The floor test
# below is unchanged and still measures the reader it names.
_repo_spells = conftest.repo_spells


def test_every_repo_path_the_document_names_exists():
    """A path in a steering document is a promise that something is there.

    Measured: the paragraph that DEFINES the mechanism field pointed at `tools/test_parity_net.py`
    — this module's working title. The reader was sent to the checking instance and found nothing,
    and neither `validate.py` nor the citation test saw it, because a bare path carries no symbol.
    Scope is the repo-rooted directories; a PROJECT-relative `scripts/...` is not a path in this
    repo and is deliberately not judged here.

    THE READER IS CASE-EXACT, and that is the correction of 2026-08-02. It used `os.path.exists`,
    which asks the FILESYSTEM whether it folds case — NTFS and APFS say yes, ext4 says no. So the
    guard for this whole class was green on the two developer platforms and would have failed on
    the `ubuntu-latest` leg of `.github/workflows/ci.yml`: measured, a document reference spelled
    `docs/post_v2_wishlist.md` against a tree carrying `docs/POST_V2_WISHLIST.md` passed here and
    is a dead link on every case-sensitive checkout. `_repo_spells` asks the TREE for its names
    instead.
    """
    roots = ("tools/", "docs/", "team-kits/", "radar/", ".github/")
    missing = sorted({path for path in re.findall(r"`([A-Za-z0-9_./-]+)`", "\n".join(_lines()))
                      if path.startswith(roots) and not path.endswith("/") and "*" not in path
                      and not _repo_spells(path)})
    assert not missing, "the document names paths this repo does not have: %s" % ", ".join(missing)


def test_the_path_reader_reads_the_tree_and_not_the_filesystems_case_folding():
    """The floor under `_repo_spells`, and it is RED on Windows without the fix.

    A reader built on `os.path.exists` answers this test's first two assertions with True and True
    on any case-folding filesystem, so the miscased spelling passes — which is exactly how a
    lowercase `docs/post_v2_wishlist.md` reference shipped past a green local suite. Asserting the
    behaviour of `os.path.exists` itself would be asserting the platform; what is asserted is that
    THIS reader does not depend on it.

    The subject is a file that really is in the tree, taken from the tree rather than typed, so
    the case that is "wrong" is wrong by construction and not by a guess about the repo.
    """
    real = sorted(name for name in os.listdir(os.path.join(ROOT, "docs"))
                  if name.endswith(".md") and name != name.lower())
    assert real, "no mixed-case file under docs/ to measure with"
    correct = "docs/" + real[0]
    assert _repo_spells(correct), correct
    assert not _repo_spells(correct.lower()), (
        "%r resolved — the reader is asking the filesystem about case folding, not the tree about "
        "its names" % correct.lower())
    assert not _repo_spells("docs/" + real[0].upper() + "x")
    assert not _repo_spells("tools/no_such_module.py")
    # a directory is a name the tree carries too, and the walk must not stop at the last segment
    assert _repo_spells("team-kits/dev-team/hooks/gate_git.py")
    assert not _repo_spells("team-kits/DEV-TEAM/hooks/gate_git.py")


# ================================================== TASK 2 — the sections carry what is claimed
@_cached
def _lead_package(kit_dir):
    """The three files spec II.5 weighs together and II.11/3 shortens — derived, never listed.

    THE SAME derivation `validate.py` weighs, and now literally so: both call
    `lead_package.files`. The sentence "validate.py computes the same package" stood here while
    the two were separate copies of one idea — true by coincidence, which is the state one edit
    away from being false. Pinning only the constitution left the lead SKILL unwatched, and it is
    half the shortening: measured by deleting the "Serialize agents that edit the same files" rule
    from the dev PM SKILL, the whole suite stayed green.
    """
    return lead_package.files(kit_dir)


@_cached
def _pinned_files(kit_dir):
    """Every shipped instruction file a section pin watches — the lead package PLUS the reference.

    THE PIN'S SUBJECT AND THE BUDGET'S SUBJECT ARE NOT THE SAME QUESTION, and conflating them is
    how this round nearly recreated the hole the pin exists for. The budget weighs what LOADS with
    every session; the pin watches what carries RULES. `hooks/ENFORCEMENT.md` — the §2 hook table
    after it moved out of the constitutions — is the first file where the two answers differ: it is
    8 KB of enforcement description that no session loads. Left out of here, its rows would have
    become exactly what the pin was written for after an independent run deleted thirteen
    constitution sections whole with the suite green.

    THE LEAD SKILL IS THE SECOND SUCH FILE, as of the measurement that took it out of the budget:
    it is registered on demand and not injected at session start (see `lead_package.files`), so it
    stopped being part of what LOADS while losing none of its rules. It comes in here through
    `lead_package.on_demand_files` — derived from the same kit, not typed out — because the
    alternative was the exact regression this docstring's own last paragraph describes: deleting
    the "Serialize agents that edit the same files" rule from the dev PM SKILL with the suite
    green.
    """
    return (_lead_package(kit_dir) + tuple(lead_package.on_demand_files(kit_dir))
            + (_reference_doc(kit_dir),))


def _sections(path):
    """[(key, lines)] — the preamble plus every `## ` section, keyed by its FULL heading.

    THE KEY IS THE HEADING TEXT, not its number. A number-keyed pin let `## 14. Behavior (all
    roles)` be renamed to `## 14. Style notes (optional, non-binding)` with the body untouched and
    every test green — a binding section demoted to a tone suggestion. Keyed by heading that is a
    deletion plus an addition, which is what it is.

    The PREAMBLE is a section even though it has no heading, because it carries a rule (parity #1,
    a minimum-keep item) and is exactly as deletable as any other.
    """
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    marks = [index for index, line in enumerate(lines) if line.startswith("## ")]
    out = []
    if marks:
        out.append(("(preamble)", lines[:marks[0]]))
    for position, index in enumerate(marks):
        end = marks[position + 1] if position + 1 < len(marks) else len(lines)
        out.append((lines[index][3:].strip(), lines[index:end]))
    keys = [key for key, _body in out]
    assert len(keys) == len(set(keys)), "duplicate section heading in %s" % path
    return out


def _digest(lines):
    """A digest of the section AS WRITTEN — heading included, line structure preserved.

    The first cut collapsed ALL whitespace, which made it blind to markdown structure: a nested
    list and a flat one hash the same, and so do two table rows pulled onto one line. Only trailing
    whitespace and blank lines are dropped now, so indentation and line boundaries count. The
    honest reading of this pin is that any edit moves it — it cannot tell a corrected typo from a
    deleted rule, and it is not meant to.
    """
    body = "\n".join(line.rstrip() for line in lines if line.strip())
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def measure_sections():
    """{kit: {relative path: {section key: {digest, hooks}}}} over every PINNED instruction file.

    `_pinned_files`, not `_lead_package`: the subject is "text that carries rules", and since the
    §2 hook table moved to `hooks/ENFORCEMENT.md` that is one file wider than the byte budget's
    subject.

    THE FLOOR UNDER EVERY FIGURE BELOW: a pinned file that yields NO section is in the subject set
    and watched by nothing. `_sections` keys on `## ` headings and answers `[]` for a file that
    carries none — not even a preamble entry — so the file's whole text could then be emptied with
    `section_differences` reporting nothing at all. That is not hypothetical here: measured, a
    deliberate re-stamp put `hooks/ENFORCEMENT.md` into the pin with 0 sections and no test in the
    suite objected. The property demanded is therefore the one the pin needs, stated per file
    rather than per filename: every subject contributes at least one watched section.
    """
    out = {}
    for kit in _kit_dirs():
        registered = {name[:-3] for name in _registered_hooks(kit)}
        files = {}
        for path in _pinned_files(kit):
            sections = {}
            for key, lines in _sections(path):
                body = "\n".join(lines)
                sections[key] = {
                    "digest": _digest(lines),
                    "hooks": sorted(name for name in registered
                                    if re.search(r"\b%s\b" % re.escape(name), body)),
                }
            # NAMED RELATIVE TO ITS OWN KIT, not to ROOT: `_pinned_files` composes every path out
            # of `kit`, so that start is always expressible — while `relpath(path, ROOT)` raises
            # ValueError as soon as the two sit on different Windows drives, which is exactly the
            # synthetic kit under `tmp_path` this refusal is measured on. The hosted windows runner
            # keeps the workspace on D: and pytest's tmp on C:, and this line was the crash rather
            # than the refusal there (BUG-0069). The kit's own name is kept in front so the reader
            # still gets a path they can find.
            assert sections, (
                "%s/%s is a pinned instruction file and carries no `## ` heading, so it contributes "
                "no section — the pin would watch the file by name and nothing of its content"
                % (os.path.basename(kit), os.path.relpath(path, kit).replace(os.sep, "/")))
            files[os.path.relpath(path, kit).replace(os.sep, "/")] = sections
        out[os.path.basename(kit)] = files
    return out


def _pins():
    with io.open(PINS, encoding="utf-8") as handle:
        return json.load(handle)


def section_differences(pinned, measured):
    """[(what, kit, file, section, hooks)] — every section that appeared, vanished or changed."""
    changes = []
    for kit in sorted(set(pinned) | set(measured)):
        before, after = pinned.get(kit, {}), measured.get(kit, {})
        for name in sorted(set(before) | set(after)):
            was, now = before.get(name, {}), after.get(name, {})
            for key in sorted(set(was) | set(now)):
                if key in was and key not in now:
                    changes.append(("GONE", kit, name, key, was[key].get("hooks") or []))
                elif key in now and key not in was:
                    changes.append(("NEW", kit, name, key, now[key].get("hooks") or []))
                elif was[key]["digest"] != now[key]["digest"]:
                    changes.append(("CHANGED", kit, name, key, now[key].get("hooks") or []))
    return changes


def test_no_section_of_a_pinned_instruction_file_disappears_unnoticed():
    """The measured hole, closed as far as a text check honestly can close it.

    Thirteen of the sixteen dev constitution sections could be deleted whole with the suite green,
    and the lead SKILL had no pin at all. Here every section of every pinned file carries a digest
    of its heading and body: a deletion fails on the missing key, a rename on the changed key and a
    gutting on the digest. What it CANNOT do is tell a rule from a typo; it forces a look, and the
    message names the registered hooks the section anchors so the look starts at the mechanism.

    Re-pin with `python tools/pin_constitution_sections.py --write --note "..."` — deliberately a
    separate, manual step that writes one line per section into the disposition: a pin that healed
    itself inside the test run would be a record of nothing, and the shortening will move ~50
    sections at once, which is exactly when a silent overwrite stops being a decision.
    """
    changes = section_differences(_pins(), measure_sections())
    assert not changes, "\n  " + "\n  ".join(
        "%s  %s %s §%r — anchors %s"
        % (what, kit, name, key, ", ".join(hooks) or "no registered hook")
        for what, kit, name, key, hooks in changes)


def _hand_built_evolution_types():
    """The item types a lead must hand-build, derived from the kernel and the shipped kits.

    Four properties, each read from something that RUNS, and their intersection is the subject:

      * the kernel can CAPTURE it (`backlog_types.REQUIRED_FIELDS` — the types `capture` creates),
      * EVERY shipped kit's `project_memory` template ships its active tray, so every kit's
        projects can hold one (`ACTIVE_DIRS` against the template tree),
      * it BINDS to a root item (`PARENT_FIELDS`), i.e. it exists in reaction to something already
        captured rather than starting a tree of its own,
      * and the kernel has NO producer of its own for it. `cli.evidence` and `dispatch.create_task`
        call `capture` with the type spelled out and assemble the body themselves; every other type
        reaches `capture` as `args.item_type` with a JSON body the CALLER composed in full, against
        a contract the kernel refuses it for missing.

    That last property is what makes this the set the instruction text owes an explanation for: a
    lead who is told to create one and does not know what fills it meets the refusal, not the rule.
    Listed instead of derived it would be `("FR", "CR", "BUG")` today; a fifth such type would join
    the subject on the day it ships a tray, and nobody has to remember to add it here.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel.backlog_types import ACTIVE_DIRS, PARENT_FIELDS, REQUIRED_FIELDS
    has_own_producer = set()
    for path in sorted(glob.glob(os.path.join(TEAM_KITS, "kernel", "*.py"))):
        with open(path, encoding="utf-8") as handle:
            for node in ast.walk(ast.parse(handle.read())):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "capture" and node.args
                        and isinstance(node.args[0], ast.Constant)):
                    has_own_producer.add(node.args[0].value)
    return {item_type for item_type in REQUIRED_FIELDS
            if item_type in PARENT_FIELDS and item_type not in has_own_producer
            and all(os.path.isdir(os.path.join(kit, "templates", "project_memory",
                                               *ACTIVE_DIRS[item_type].split("/")))
                    for kit in _kit_dirs())}


def _sections_naming(paths, item_type):
    """Sections of `paths` that name `item_type` OUTSIDE a table row.

    The table row is excluded because it is the thing being distinguished FROM: an ownership table
    assigns a type to a role, which is not a statement about when one arises or what fills it. The
    match is the bare type id as a word, so `BUG-0007` and `bugs/active` do not stand in for it.
    """
    pattern = re.compile(r"(?<![A-Za-z0-9_-])%s(?![A-Za-z0-9_-])" % re.escape(item_type))
    hits = []
    for path in paths:
        for key, lines in _sections(path):
            if any(pattern.search(line) for line in lines
                   if not line.lstrip().startswith("|")):
                hits.append("%s §%s" % (os.path.basename(path), key))
    return hits


def test_every_hand_built_item_type_is_ruled_on_and_not_merely_assigned():
    """A type the kernel enforces and no text explains costs its lead a refusal it cannot read.

    Measured before this test existed, at HEAD a7c6250: `office-team` named `FR`, `CR` and `BUG`
    in exactly two places each — the constitution's ownership table (a table row, so not counted
    here) and one restatement of that row in the lead SKILL's "what you own" — while the kernel
    refuses a `CR` without `target_pr`/`target_revision`/`change_description`/`acceptance_criteria`
    and a `BUG` without `related_pr`/`observed`/`expected`/`repro`/`severity`/`acceptance_criteria`.
    `research-team` was in the same state for `BUG` and `FR`. `dev-team` was not, which is why it
    is the shape the other two were brought to rather than a fourth thing invented here.

    WHAT THE THRESHOLD IS AND IS NOT. Two non-table sections is what an INVENTORY produces: the
    type is assigned once and the assignment is repeated once. Three is the first count an
    inventory cannot reach, so it is the floor on "something beyond the listing exists". It is a
    floor on TREATMENT and nothing more — it cannot read whether the treatment is correct, and
    saying otherwise would be the reassuring lie this file exists to prevent. What judges the
    content is the section pin above (every one of these sections is digested there, so a gutting
    is reported) and the human reading the journal line it forces.
    """
    thin = []
    for kit in _kit_dirs():
        # THE LEAD'S INSTRUCTION TEXT, loaded or on demand. The floor is about what the lead can
        # READ about a type, and the lead SKILL carries most of it — it left the LOADED package
        # (measured: it is registered, not injected) without leaving the instructions.
        package = _lead_package(kit) + tuple(lead_package.on_demand_files(kit))
        for item_type in sorted(_hand_built_evolution_types()):
            where = _sections_naming(package, item_type)
            if len(where) < 3:
                thin.append("%s/%s: %s" % (os.path.basename(kit), item_type,
                                           ", ".join(where) or "nowhere outside a table"))
    assert not thin, (
        "the kernel refuses these types without their own fields, and the lead package assigns "
        "them without ever saying when one arises or what fills it:\n  " + "\n  ".join(thin))


def test_the_hand_built_type_subject_is_the_intersection_it_claims():
    """The floor under the test above: a subject that quietly emptied would assert nothing.

    Both halves, because either one alone is satisfiable by an accident. The set must be
    non-empty AND must exclude the two types the kernel captures for the caller — a derivation
    that let `EVD` or `TSK` in would be measuring text about items no lead composes, and one that
    let everything in would demand a rule for types that belong to the architect or the reviewer.
    """
    subject = _hand_built_evolution_types()
    assert subject, "the hand-built-type derivation selected nothing at all"
    assert not subject & {"EVD", "TSK"}, (
        "`cli.evidence` and `dispatch.create_task` capture these types themselves, so they are "
        "not the ones a lead composes as a JSON object: %s" % sorted(subject & {"EVD", "TSK"}))


def test_the_section_reader_sees_a_deletion_a_rename_and_a_gutting(tmp_path):
    """The floor under the pin: the reader must notice all three mutations.

    A pin whose reader answers the same for a deleted section as for a present one is the shape
    that stayed green through a real defect. All three are performed here, on a COPY outside the
    shipped tree.
    """
    source = os.path.join(_kit_dirs()[0], "constitution", "AGENTS.md")
    with open(source, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    intact = {key: _digest(body) for key, body in _sections(source)}
    assert len(intact) > 10, sorted(intact)

    start = next(index for index, line in enumerate(lines) if line.startswith("## 14. "))
    end = next((index for index in range(start + 1, len(lines))
                if lines[index].startswith("## ")), len(lines))
    victim = lines[start][3:].strip()
    copy = tmp_path / "AGENTS.md"

    copy.write_text("\n".join(lines[:start] + lines[end:]), encoding="utf-8")
    assert victim not in dict(_sections(str(copy))), "the reader did not notice a deleted section"

    renamed = list(lines)
    renamed[start] = "## 14. Style notes (optional, non-binding)"
    copy.write_text("\n".join(renamed), encoding="utf-8")
    assert victim not in dict(_sections(str(copy))), (
        "a section renamed from binding to optional reads as the same section")

    gutted = list(lines)
    gutted[start + 1:end] = [""]
    copy.write_text("\n".join(gutted), encoding="utf-8")
    after = {key: _digest(body) for key, body in _sections(str(copy))}
    assert victim in after, "the gutted section lost its heading — wrong mutation"
    assert after[victim] != intact[victim], (
        "the reader gives a gutted section the same digest as a full one")


def _synthetic_kit(root, reference_body):
    """A kit with every surface `measure_sections` reads, so only the KIT DISCOVERY is faked.

    Written rather than copied: the lead package derives from `settings/settings.json`'s `agent`
    key and the reference from `hooks/_compat.py:REFERENCE_NAME`, so a kit that satisfies those two
    derivations is a kit as far as the pin is concerned — and building it here means the mutation
    below happens outside the shipped tree.
    """
    _write(root / "constitution" / "AGENTS.md", "# C\n\n## 1. A rule\n\nbody\n")
    _write(root / "settings" / "settings.json", json.dumps({"agent": "lead"}))
    _write(root / "agents" / "lead.md", "# L\n\n## 1. A rule\n\nbody\n")
    _write(root / "skills" / "lead" / "SKILL.md", "# S\n\n## 1. A rule\n\nbody\n")
    _write(root / "hooks" / "_compat.py", 'REFERENCE_NAME = "ENFORCEMENT.md"\n')
    _write(root / "hooks" / "ENFORCEMENT.md", reference_body)
    return str(root)


def test_a_pinned_file_that_carries_no_section_is_refused(tmp_path, monkeypatch):
    """The floor under the pin's own subject: a pinned file must contribute a watched section.

    THE HOLE, measured before the floor existed: `_sections` returns `[]` for a file with no `## `
    heading — not even the preamble entry, because that entry is derived from the first heading —
    so such a file entered the pin as an empty mapping. `section_differences` compares mappings per
    file, and an empty one against an empty one is no difference: the whole text could then be
    rewritten or emptied with `test_no_section_of_a_pinned_instruction_file_disappears_unnoticed`
    green. `hooks/ENFORCEMENT.md` carries exactly one `## ` heading today, which is one edit away
    from none.

    Only `_kit_dirs` is replaced. The lead package, the reference pointer, the section reader and
    the hook reader all run over a real directory, so what is measured is `measure_sections` and
    not a stand-in for it.
    """
    monkeypatch.setattr(
        sys.modules[__name__], "_kit_dirs",
        lambda: (_synthetic_kit(tmp_path / "kit-team", "# Reference\n\nprose, no heading\n"),))
    for reader in _CACHED_READERS:
        reader.cache_clear()
    with pytest.raises(AssertionError) as refusal:
        measure_sections()
    assert "ENFORCEMENT.md" in str(refusal.value), refusal.value

    # the counter-direction, so "refuse everything" is not a way out: one heading is enough, and
    # the file then really is watched by a digest
    monkeypatch.setattr(
        sys.modules[__name__], "_kit_dirs",
        lambda: (_synthetic_kit(tmp_path / "kit-team", "# Reference\n\n## 1. What is refused\n\nx\n"),))
    for reader in _CACHED_READERS:
        reader.cache_clear()
    measured = measure_sections()["kit-team"]["hooks/ENFORCEMENT.md"]
    assert "1. What is refused" in measured, sorted(measured)


@_cached
def _reference_doc(kit_dir):
    """The file this kit's refusals point at — read out of `hooks/_compat.py`, never spelled here.

    `_compat.REFERENCE_NAME` is what `reference_note()` interpolates into every block message, so
    the document a role is SENT to is a fact about the running code. Reading it by AST means a
    rename follows into the checks below instead of leaving them pointed at a file nobody is told
    about any more; the module is not imported, because importing a hook reconfigures the process's
    streams for a question that is answered by one assignment.
    """
    path = os.path.join(kit_dir, "hooks", "_compat.py")
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == "REFERENCE_NAME" \
                and isinstance(node.value, ast.Constant):
            return os.path.join(kit_dir, "hooks", node.value.value)
    raise AssertionError("%s defines no REFERENCE_NAME — nothing tells a blocked role where the "
                         "enforcement table is" % path)


def test_every_registered_hook_is_anchored_in_its_kits_constitution():
    """The other direction: a mechanism that runs must be findable in the text roles actually read.

    This is what notices a NEW gate wired without a word in the constitution — the case the digest
    pin cannot see, because nothing changed in a section that has to change. It names every
    mechanism that lost its anchor.

    THE SUBJECT STAYS THE CONSTITUTION ALONE, decided when the §2 hook table moved to
    `hooks/ENFORCEMENT.md`, and the widening was the tempting mistake. What this test is for is the
    text that is ALWAYS THERE: the constitution loads at every session start and every subagent
    spawn, the reference loads when somebody opens it. Asking the union would let a gate be wired
    with its only mention in a document no session reads — the anchor would be satisfied by a file
    that is, by construction, absent from the context the rule has to hold in. The descriptions
    moved; the NAMES did not, and this is the check that keeps them where they are.
    """
    orphaned = []
    for kit in _kit_dirs():
        with open(os.path.join(kit, "constitution", "AGENTS.md"), encoding="utf-8") as handle:
            body = handle.read()
        for name in sorted(_registered_hooks(kit)):
            stem = name[:-3]
            if stem.startswith("_"):
                continue        # the dispatcher and the shared helpers are not rules
            if not re.search(r"\b%s\b" % re.escape(stem), body):
                orphaned.append("%s: %s" % (os.path.basename(kit), stem))
    assert not orphaned, (
        "these hooks enforce something the constitution never names: %s" % ", ".join(orphaned))


def test_no_enforcement_text_claims_a_hook_that_no_registration_starts():
    """And the counter-direction, house rule 3 in executable form: a text may not promise
    protection the wiring does not build.

    THE SUBJECT IS THE UNION, and it is the opposite decision from the test above for a reason that
    is not symmetry. "Must be named" is about a text that is always loaded, so widening it would
    weaken it. "Must not lie" is about a text somebody READS — and the reference is read at the one
    moment the reader has been refused and needs to know what refused them. A dead hook name is at
    least as harmful there as in the constitution. The reference file is not spelled here either:
    it is whatever `_compat.REFERENCE_NAME` sends a blocked role to (`_reference_doc`), so the
    subject follows the pointer rather than a copy of its filename.

    The hook set is derived — every hook FILE the kit ships — so it covers a hook that is named,
    exists, and can be started by nothing. It does not cover a name that is no file at all: that is
    prose about something else, and `validate.py` owns whether it resolves.
    """
    lying = []
    for kit in _kit_dirs():
        texts = {}
        for path in (os.path.join(kit, "constitution", "AGENTS.md"), _reference_doc(kit)):
            assert os.path.isfile(path), path
            with open(path, encoding="utf-8") as handle:
                texts[os.path.basename(path)] = handle.read()
        registered = _registered_hooks(kit)
        for name in sorted(os.listdir(os.path.join(kit, "hooks"))):
            if not name.endswith(".py") or name.startswith("_") or name in registered:
                continue
            for where, body in sorted(texts.items()):
                if re.search(r"\b%s\b" % re.escape(name[:-3]), body):
                    lying.append("%s %s: %s" % (os.path.basename(kit), where, name[:-3]))
    assert not lying, (
        "these texts name a hook no registration can start: %s" % ", ".join(lying))


# A NAME RUN: code spans separated by nothing but `, `. The inventory is located by its SHAPE and
# not by the words above it, because a heading is a spelling and this repo has paid for those.
_NAME_RUN_RX = re.compile(r"`([a-z][a-z0-9_]+)`(?:, `[a-z][a-z0-9_]+`)+")


@_cached
def _presented_inventory(kit_dir):
    """The list the constitution PRESENTS as this kit's mechanisms — the longest such run.

    Longest, because a kit names its whole apparatus in exactly one place and nowhere else strings
    two dozen hook names together; a floor in the test below refuses to answer at all if the run it
    finds is too short to be that place, so a reformatting that breaks the run fails loudly instead
    of quietly comparing against a fragment.

    A MAJORITY OF SHIPPED HOOK NAMES, NOT ALL OF THEM, and that correction was measured while
    writing this: demanding all of them made the ONE case that matters in the second direction
    unreachable — a bogus name added to the list dropped the whole run out of the reader, and the
    check reported "no inventory found" instead of "this name starts nothing". That is the whole of
    what the majority is for. It carries nothing against a COMPETING run: measured over all three
    constitutions with this same reader, the longest run that is not the inventory is four spans,
    so the longest-run rule already decides that on its own.
    """
    shipped = {name[:-3] for name in os.listdir(os.path.join(kit_dir, "hooks"))
               if name.endswith(".py") and not name.startswith("_")}
    with open(os.path.join(kit_dir, "constitution", "AGENTS.md"), encoding="utf-8") as handle:
        flat = re.sub(r"\s+", " ", handle.read())
    best = ()
    for match in _NAME_RUN_RX.finditer(flat):
        names = tuple(re.findall(r"`([a-z][a-z0-9_]+)`", match.group(0)))
        if len(names) > len(best) and sum(name in shipped for name in names) * 2 > len(names):
            best = names
    return best


def test_the_inventory_the_constitution_presents_is_the_registrations_it_ships():
    """The sentence says "complete in both directions", and until now nothing measured either.

    THE DEFECT (found by the verifier on TSK-0095, in the office kit): `gate_second_reading` and
    `record_filing_reading` shipped with TSK-0087, are registered in `settings/settings.json`, have
    their own row in `hooks/ENFORCEMENT.md` — and never reached the list. 24 registered, 22 listed.
    The claim above it read "no mechanism that runs is missing from this list".

    WHY NOTHING CAUGHT IT. `test_every_registered_hook_is_anchored_in_its_kits_constitution` asks
    whether the NAME occurs anywhere in the constitution, and both names occur in §2 prose about
    the four-eyes rule. That is the right question for its own subject (a mechanism must be
    findable in the text roles read) and the wrong instrument for this one: the LIST is a claim
    about a set, so it has to be compared as a set.

    THE DIRECTION MATTERS AND IS THE HARDER HALF TO NOTICE: this understated the protection. A
    reader of that list concludes the two hooks do not exist, and house rule 3 treats an
    under-alarming text exactly like an over-alarming one. Both directions are asserted here, over
    all three kits, so the reader itself is proven by the two that are correct.
    """
    findings = []
    for kit in _kit_dirs():
        name = os.path.basename(kit)
        listed = _presented_inventory(kit)
        assert len(listed) >= 10, (
            "%s: the longest run of hook names in the constitution is %d long, which is not an "
            "inventory — either the list was reformatted out of one run or this kit stopped "
            "presenting one: %s" % (name, len(listed), ", ".join(listed) or "nothing"))
        duplicated = sorted({one for one in listed if listed.count(one) > 1})
        if duplicated:
            findings.append("%s lists %s twice" % (name, ", ".join(duplicated)))
        registered = {hook[:-3] for hook in _registered_hooks(kit) if not hook.startswith("_")}
        for missing in sorted(registered - set(listed)):
            findings.append("%s REGISTERS %s and does not list it — the list understates what runs"
                            % (name, missing))
        for stale in sorted(set(listed) - registered):
            findings.append("%s lists %s and no shipped registration can start it" % (name, stale))
    assert not findings, (
        "the constitutions claim their hook list is complete in both directions and it is not:\n  "
        + "\n  ".join(findings))


# ============================ TASK 2b — what a REFUSAL claims about the text it sends you to
def _self_named_docs(kit_dir):
    """{word: kit-relative path} for every pinned text that names ITSELF twice.

    THE VOCABULARY IS NOT TYPED HERE, and the derivation is the reason this is a definition rather
    than the list of spellings that produces the next defect: a document names itself in its TITLE
    and in its LOCATION, and the words those two share are what a reader calls it. `constitution/
    AGENTS.md` is titled "Working Method — Constitution (Dev Team)" and lives under `constitution/`,
    so it answers `constitution`; `hooks/ENFORCEMENT.md` is titled "Enforcement reference …" and
    answers `enforcement`. Measured against the wider candidates: taking the whole title yields
    `working` and `method` too, and those fire on "report it instead of working around it" and on
    `packaging.method` — a reader that flags a correct refusal is worse here than none.
    """
    out = {}
    for path in _pinned_files(kit_dir):
        relative = os.path.relpath(path, kit_dir).replace(os.sep, "/")
        title = ""
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
        shared = ({word.lower() for word in re.findall(r"[A-Za-z]{4,}", title)}
                  & {word.lower() for word in re.findall(r"[A-Za-z]{4,}", relative)})
        for word in shared:
            out[word] = relative
    return out


def _docstrings(tree):
    """Every string this module addresses to a MAINTAINER rather than to an agent."""
    return {ast.get_docstring(node, clean=False)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and ast.get_docstring(node, clean=False) is not None}


def _agent_facing_strings(path):
    """[(line, text)] — every string literal a hook can put in front of an agent.

    Docstrings are excluded and everything else is in, which is a split rather than a guess: a
    docstring is the file explaining itself to whoever opens it, any other literal can end up in a
    block message, a remedy, a returned reason or a warning. Data-flow was the alternative and it
    misses the real shape — `gate_push_token` builds its reason as a RETURN value that a `block`
    call consumes three frames later, and a reader over `block(...)` arguments alone did not see it
    (measured: that string named the constitution and the argument reader reported zero hits).
    """
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    docs = _docstrings(tree)
    return [(node.lineno, node.value) for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and node.value not in docs]


def _cited_location(word, text):
    """The `§anchor` this string offers for `word`, or None — ONE definition, two callers.

    The anchor path deliberately stops at `:` as well as at whitespace and sentence punctuation:
    the colon is what introduces a GLOSS (`§8: never work on a dirty tree`), so swallowing it into
    the anchor is what made the gloss clause silently unreachable (measured on the probe below —
    the reader called the glossed citation "fine").
    """
    return re.search(r"\b%s\b[^.\n]{0,24}?%s([^\s,.):]+)"
                     % (re.escape(word), parity_sources.ANCHOR_MARK), text, re.I)


def test_no_refusal_claims_something_about_a_text_nothing_can_check():
    """House rule 3 in the direction this repo had not measured: the MECHANISM claiming about the TEXT.

    A hook ships byte-identically to several kits (the mirror rule), while the constitution it
    refers to is a DIFFERENT document in each of them. So a refusal that attributes its rule to
    "the constitution" is a claim that can be true in one kit and false in the next, and no reader
    can tell which — measured twice on 2026-08-02: after II.11/3 redeemed parity licence 30, the
    dev constitution stopped naming force-push while `gate_git` and `gate_push_token` still sent
    their reader there, and `gate_shell_hygiene` glossed `constitution §8` as "never work on a
    dirty tree" although office §8 is the BEHAVIOR section and the office constitution carries no
    dirty-tree rule at all.

    TWO CLAUSES, and both are the house rule rather than a taste:

      * A refusal may name a per-kit text only through a LOCATION — a `§` anchor. A bare
        attribution is a claim nothing can resolve, which is precisely what rotted here.
      * It may not QUOTE what stands at that location. "Prefer naming a location over quoting text
        from another file: a quotation nothing checks is a claim that rots."

    THE REFERENCE IS EXEMPT, derived and not excepted: `_compat.stop` appends its pointer to EVERY
    refusal, and it ships inside the same hashed bundle as the hook, so it is the one document a
    refusal is entitled to point at.

    HOW WIDE THIS REALLY IS, because the sentences above read wider than the instrument. The sweep
    runs over `_self_named_docs`, so it sees an attribution only when it uses a word the target text
    forms as TITLE ∩ LOCATION. Two of the four pinned texts per kit have a `# ` title and therefore
    a word: the constitution (`constitution`) and the reference (`enforcement`, exempt). The lead
    AGENT file and the lead SKILL carry YAML frontmatter and no title, so they contribute nothing —
    and those are exactly the two a refusal is most likely to misattribute to. Measured by putting
    four spellings into `gate_git.py` one at a time: "your AGENTS.md forbids this outright", "the
    team rules forbid this outright" and "forbidden by the project-manager SKILL" all PASS; only
    "forbidden by the constitution" is caught. So this closes ONE spelling of the class, and the
    sentence above is about that spelling.

    WHY THE OBVIOUS WIDENING IS REFUSED, measured the same way `working`/`method` were. Taking the
    frontmatter `name:` as the missing title yields `manager` + `project` for the dev and research
    lead files and `manager` + `office` for the office ones, and `description:` adds `skills`. Over
    every agent-facing string in every kit that is 111 hits for `project`, 22 for `manager`, 21 for
    `skills` and 5 for `office` — and they are CORRECT refusals: "no canonical project state",
    "the installed enforcement bundle is not the one this project trusts", `guard_pm_scope`'s own
    "You are the Project Manager — you do NOT …", `guard_harness_selfmod`'s `skills/` path list.
    The reason is structural rather than bad luck: a TITLE names the document, while frontmatter
    `name:` names the ROLE, and a refusal may address its reader by role as often as it likes. A
    checker that flags a correct refusal is worse than none, so the widening stays unbuilt and the
    hole stays counted here.

    WHAT THIS DOES NOT COVER EITHER, named rather than implied: whether an anchored citation points
    at the section that carries the rule. `constitution §8` resolves in all three kits and means Git
    in two of them and Behavior in the third; deciding that needs the rule↔section pairing, which is
    a reading. The gloss ban is what made that particular one visible, and it is a weaker instrument.
    """
    offenders = []
    for kit in _kit_dirs():
        documents = _self_named_docs(kit)
        reference = os.path.basename(_reference_doc(kit))
        exempt = {word for word, relative in documents.items()
                  if os.path.basename(relative) == reference}
        for path in sorted(glob.glob(os.path.join(kit, "hooks", "*.py"))):
            for lineno, text in _agent_facing_strings(path):
                for word in sorted(set(documents) - exempt):
                    if not re.search(r"\b%s\b" % re.escape(word), text, re.I):
                        continue
                    where = "%s/hooks/%s:%d" % (os.path.basename(kit),
                                                os.path.basename(path), lineno)
                    anchor = _cited_location(word, text)
                    if not anchor:
                        offenders.append(
                            "%s names %r and no %s location — an attribution nothing can resolve"
                            % (where, word, parity_sources.ANCHOR_MARK))
                        continue
                    if text[anchor.end():anchor.end() + 1] == ":":
                        offenders.append(
                            "%s quotes what stands at %s%s instead of only naming it"
                            % (where, parity_sources.ANCHOR_MARK, anchor.group(1)))
    assert not offenders, (
        "these refusals claim something about a shipped text that nothing checks:\n  "
        + "\n  ".join(sorted(set(offenders))))


def test_the_refusal_sweep_covers_the_texts_its_docstring_claims_and_no_others():
    """The reach of the sweep, MEASURED, so the paragraph describing it cannot quietly rot.

    `test_no_refusal_claims_something_about_a_text_nothing_can_check` says it covers the pinned
    texts that carry a `# ` title and not the two that carry YAML frontmatter instead. That is a
    statement about the tree, and the tree moves: give the lead SKILL a title and the sweep silently
    widens, drop the constitution's and it silently empties. Both are things a later reader must be
    told, and the honest way to tell them is to fail here.

    The subject is derived twice over and named nowhere: the pinned texts are `_pinned_files`, the
    reference is `_compat.REFERENCE_NAME`, and "the lead agent file and the lead SKILL" is simply
    the pinned texts minus the reference minus whatever the sweep can see. Giving either of those a
    `# ` title that shares a word with its path widens the sweep and fails HERE, which is the
    sentence in the docstring above going stale rather than a behaviour breaking.

    IT ASKS `_pinned_files` AND NOT `_lead_package`, because the question is which shipped RULE
    texts the sweep reaches — the lead SKILL is one of those whether or not a session loads it, and
    it stopped loading in the same round this line was written.
    """
    for kit in _kit_dirs():
        visible = {os.path.normcase(os.path.join(kit, name.replace("/", os.sep)))
                   for name in _self_named_docs(kit).values()}
        reference = os.path.normcase(_reference_doc(kit))
        package = [path for path in map(os.path.normcase, _pinned_files(kit))
                   if path != reference]
        blind = [path for path in package if path not in visible]

        assert reference in visible, (
            "%s: the reference carries no title, so the exemption the sweep grants it is dead code"
            % os.path.basename(kit))
        assert len(visible) == 2, (
            "%s: the sweep now sees %d pinned texts, not 2 — its docstring says which two and why"
            % (os.path.basename(kit), len(visible)))
        assert len(package) - len(blind) == 1, (
            "%s: the sweep sees %d of the %d pinned rule texts; the docstring claims exactly the "
            "constitution" % (os.path.basename(kit), len(package) - len(blind), len(package)))
        assert len(blind) == 2, (
            "%s: %d pinned rule texts are invisible to the sweep, not 2 — the docstring names the "
            "agent file and the SKILL: %s"
            % (os.path.basename(kit), len(blind),
               ", ".join(sorted(os.path.relpath(path, kit) for path in blind))))


def test_the_refusal_reader_finds_both_shapes_and_leaves_a_correct_citation_alone(tmp_path):
    """The floor under the sweep: a reader that answers "fine" to everything closes nothing.

    Both refused shapes and both permitted ones are put through the real reader, on a probe outside
    the shipped tree, so "return no offenders" is not a way out. The permitted cases are the two the
    kits really ship (`constitution §6`, `constitution §2.7`) — a check that flagged those would be
    the false direction this predicate was narrowed to avoid.
    """
    probe = tmp_path / "probe_hook.py"
    probe.write_text(
        '"""A docstring naming the constitution is not agent-facing and must not count."""\n'
        "BARE = 'force-push is forbidden by the team constitution.'\n"
        "GLOSS = 'lose them (constitution \\u00a78: never work on a dirty tree).'\n"
        "LOCATED = 'the per-area coverage rule, constitution \\u00a76). Have QA add tests.'\n"
        "NESTED = 'state the rules BEFORE code (constitution \\u00a72.7), as INV items.'\n"
        "UNRELATED = 'report it instead of working around it.'\n", encoding="utf-8")
    found = {}
    for _lineno, text in _agent_facing_strings(str(probe)):
        anchor = _cited_location("constitution", text)
        if not re.search(r"\bconstitution\b", text, re.I):
            verdict = "not judged"
        elif not anchor:
            verdict = "bare attribution"
        elif text[anchor.end():anchor.end() + 1] == ":":
            verdict = "gloss"
        else:
            verdict = "fine"
        found[text.split("=")[0][:12]] = verdict
    verdicts = sorted(found.values())
    assert verdicts.count("bare attribution") == 1, found
    assert verdicts.count("gloss") == 1, found
    assert verdicts.count("fine") == 2, found
    assert verdicts.count("not judged") == 1, found
    # the module docstring names it too and is deliberately invisible to the reader
    assert all("docstring" not in text for _line, text in _agent_facing_strings(str(probe)))


# =================================== TASK 3 — what session_status really injects, by running it
HOOKS = os.path.join(TEAM_KITS, "dev-team", "hooks")
SESSION_STATUS = os.path.join(HOOKS, "session_status.py")


def emission_sites(path=SESSION_STATUS):
    """How many places in `main()` put a block into the briefing — counted from the AST.

    The ablation below can only see blocks an INPUT switches. Two of them no input switches — the
    identity line and the state-directory briefing, an if/else that always appends — so a census
    resting on ablation alone could not notice their deletion: measured by removing the identity
    line in both provider wordings, this module and the whole suite stayed green. Counting the
    emission sites is the half that fails for those.
    """
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    main = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "main")
    appends = [node for node in ast.walk(main)
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and node.func.attr == "append" and isinstance(node.func.value, ast.Name)
               and node.func.value.id == "parts"]
    seeds = [node for node in ast.walk(main) if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == "parts"
                     for target in node.targets)]
    return sum(1 for node in appends if node.args and _emits_something(node.args[0])) \
        + sum(1 for node in seeds if _emits_something(node.value))


def _emits_something(node):
    """Does this expression put TEXT into the briefing?

    A SITE MUST EMIT. Counting `parts = []` as a site let the identity block be emptied while the
    number stayed 14, so the first fix excluded the empty LITERAL — and `parts = [""]` walked
    straight past it, one character away from the mutation it was written for. That was a special
    case for one spelling of emptiness, not a definition.

    The definition: a value is empty when everything it can statically be shown to contain is an
    empty string. A sequence is empty when every element is; a constant when it is falsy; anything
    the reader cannot evaluate (a name, a call, an f-string, a concatenation) is assumed to emit.

    THAT LAST ASSUMPTION IS THE UNSAFE DIRECTION HERE, and an earlier version of this docstring
    claimed the opposite. For a counter whose job is to notice an emptied site, counting too much
    means the number does NOT move — which is precisely the mutation this reader exists for.
    Measured, both still read as 14: `parts = list()` and `parts = [] + []`. They are the known
    remainder; the reason to keep the assumption is that the alternative — calling every
    unevaluable expression empty — would drop live sites and lower the pinned number instead,
    which fails in the same direction AND for the ordinary case.
    """
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return any(_emits_something(element) for element in node.elts)
    if isinstance(node, ast.Constant):
        return bool(node.value)
    return True


def _session_start(repo, home, env=None):
    """Run the SHIPPED hook as a process and return its `additionalContext`.

    A real process with JSON on stdin, in a project OUTSIDE this repo: importing `main()` would
    measure a function, and what a session gets is the output of a program.
    """
    # HARNESS_KERNEL_PATH: a scaffolded project carries the kernel at `.claude/kernel`, and this
    # fixture writes only the files each toggle needs. The kit-comparison block asks the kernel
    # since FR-0006 (`_kernel.kit_update_verdict`), so without it the `update_available` toggle
    # would switch a paragraph that says "the kernel could not be reached" either way -- the census
    # would then be counting the fixture's gaps rather than the hook's blocks.
    environment = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo), HOME=str(home),
                       USERPROFILE=str(home), CLAUDE_CONFIG_DIR=os.path.join(str(home), ".claude"),
                       HARNESS_KERNEL_PATH=TEAM_KITS)
    environment.pop("TEAM_KIT_PROVIDER", None)
    environment.update(env or {})
    body = {"cwd": str(repo), "hook_event_name": "SessionStart", "session_id": "this-session"}
    result = subprocess.run([sys.executable, SESSION_STATUS],
                            input=json.dumps(body), capture_output=True, text=True,
                            env=environment, timeout=120)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


def _write(path, text):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(str(path), "w", encoding="utf-8") as handle:
        handle.write(text)


def _project(base, without=()):
    """A project in which every session-start condition is true, minus the ones named.

    Built fresh for every measurement, because the hook WRITES: it consumes `kit_updated_from`,
    stamps `kit_last_seen_version`, records `project_path.state` and counts sessions in
    `kit_update_pending.state`. A second run in the same directory measures a different project.
    """
    home, repo = base / "home", base / "repo"
    _write(home / ".claude" / "team-kits" / "dev-team" / "VERSION",
           "version: 2026.08.01-1\ncontent: staged\n")
    _write(repo / "CLAUDE.md", "<!-- agents-and-skills:team-kit dev-team -->\n@AGENTS.md\n")
    installed = ("version: 2026.08.01-1\ncontent: staged\n" if "update_available" in without
                 else "version: 2026.07.01-1\ncontent: local\n")
    _write(repo / ".claude" / "kit_version", installed)

    if "version_change" not in without:
        _write(repo / ".claude" / "kit_updated_from", "version: 2026.06.01-1\n")
    if "merge_backlog" not in without:
        _write(repo / ".claude" / "kit_update_pending.repo", "# diverged\n- scripts/quality.py\n")
    # The drift check reads `project_memory/project_config.yaml`, so it is NESTED inside the state
    # directory rather than beside it. Written flat, the "no state directory" case still created
    # `project_memory/` through the drift fixture and the briefing never flipped to its second
    # wording — caught by the control below.
    if "state_dir" not in without:
        _write(repo / "project_memory" / "generated" / "session_brief.yaml", "brief: {}\n")
        if "model_drift" not in without:
            _write(repo / "project_memory" / "project_config.yaml",
                   "model_map:\n  backend-developer: opus\n")
            _write(repo / ".claude" / "agents" / "backend-developer.md",
                   "---\nname: backend-developer\nmodel: sonnet\n---\nbody\n")
    if "path_change" not in without:
        _write(repo / ".claude" / "project_path.state", os.path.join("X:", "elsewhere") + "\n")
    if "transcript" not in without:
        key = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(str(repo)))
        _write(home / ".claude" / "projects" / key / "older-session.jsonl", "{}\n")
    if "git_branch" not in without:
        for argv in (["git", "init", "-q", str(repo)],
                     ["git", "-C", str(repo), "-c", "user.email=x@y.z", "-c", "user.name=x",
                      "commit", "-q", "--allow-empty", "-m", "base"]):
            subprocess.run(argv, capture_output=True, timeout=120)
    return home, repo


# The conditions this hook REACTS to — inputs, never expected wordings. The assertion is that
# switching one off changes what the process emits; a check that searched for "KIT MERGE BACKLOG"
# would stop measuring the hook the moment somebody rewords the banner, and rewording is precisely
# what the II.8 rewrite does. `state_dir` is deliberately NOT among them: switching it off SWAPS
# the briefing's wording instead of removing a block, which is why the site count above exists.
_TOGGLES = ("version_change", "update_available", "merge_backlog", "model_drift",
            "path_change", "transcript", "git_branch")


def _speech(base, without=(), env=None):
    """What the hook SAYS for this configuration, with the fixture's own location removed.

    THIS NORMALISATION IS THE MEASUREMENT, and leaving it out made the first cut of the census green
    under its own mutation. Two projects differ in their absolute paths, and the hook prints paths —
    the transcript pointer alone carries the project directory twice, once verbatim and once as the
    `~/.claude/projects/<key>` key. So EVERY ablation "changed the output", including one performed
    on a hook with a block deliberately disabled.
    """
    home, repo = _project(base, without=without)
    said = _session_start(repo, home, env=env)
    for needle in (str(repo), str(home), re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(str(repo)))):
        said = said.replace(needle, "<fixture>")
    return said


def test_the_census_control_reads_the_hook_and_not_the_fixture(tmp_path):
    """The floor under the census: identical configurations in different directories must be
    indistinguishable. Without it, "the output changed" says nothing about the hook.
    """
    assert _speech(tmp_path / "control-a") == _speech(tmp_path / "control-b")
    assert _speech(tmp_path / "control-c", without=_TOGGLES) \
        == _speech(tmp_path / "control-d", without=_TOGGLES)


def test_the_session_start_hook_emits_what_the_disposition_counts(tmp_path):
    """The block census, counted twice by different means and stated in the document.

    The disposition row said "alle ~6 injizierten Blöcke" and the II.8 rewrite was about to be
    planned against that figure. `~6` is the shape of a number nobody counted. The two figures are
    pinned separately because each covers what the other cannot: the AST sees a deleted block no
    input controls, the ablation sees a block that stopped reacting to its input.
    """
    sites = emission_sites()
    assert re.search(r"%d Emissionsstellen" % sites, _reading_view()), (
        "the disposition does not state %d emission sites" % sites)

    full = _speech(tmp_path / "full")
    assert full.strip(), "the hook emitted nothing at all"
    silent = [condition for index, condition in enumerate(_TOGGLES)
              if _speech(tmp_path / ("off-%d" % index), without=(condition,)) == full]
    assert not silent, (
        "switching these conditions off changed nothing the hook says, so they inject no block "
        "(or the fixture no longer switches them): %s" % ", ".join(silent))
    assert re.search(r"%d davon schaltbar" % len(_TOGGLES), _reading_view()), (
        "the disposition does not state %d switchable blocks" % len(_TOGGLES))

    # the state-directory briefing SWAPS rather than disappears — the property that keeps it out
    # of the toggle list, asserted rather than assumed
    without_state = _speech(tmp_path / "no-state", without=("state_dir",))
    assert without_state.strip() and without_state != full, (
        "the state-directory briefing neither swapped nor stayed — the census grouping is wrong")


def test_the_update_banner_carries_a_codex_only_extension(tmp_path):
    """The Codex procedure is emitted only together with the update banner — measured, because the
    rewrite has to decide whether the II.8 state machine keeps a provider-specific branch.

    Held fixed: the configuration. Varied: the provider, and then the update. The DIFFERENCE of the
    two provider differences is the block; comparing raw lengths once would credit the identity
    line's provider wording for it.
    """
    def codex_surplus(label, without):
        codex = _speech(tmp_path / (label + "-codex"), without=without,
                        env={"TEAM_KIT_PROVIDER": "codex"})
        return len(codex) - len(_speech(tmp_path / (label + "-claude"), without=without))

    surplus = codex_surplus("update", ()) - codex_surplus("current", ("update_available",))
    assert surplus > 200, (
        "the Codex update procedure is not a block of its own: an update pending buys only %d "
        "characters of Codex-specific text" % surplus)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
