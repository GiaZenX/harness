"""Tests for the status automata + V1 mapping (HARNESS_V2_SPEC.md II.2 / II.10 / II.12)."""
import ast
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "team-kits"))
_TEAM_KITS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "team-kits")

from kernel.state import CONFIRMING_EVIDENCE, _KERNEL_SET  # noqa: E402
from kernel import approvals, backlog_types  # noqa: E402
from kernel.backlog_types import (  # noqa: E402
    AUTOMATA,
    _Automaton,
    EVIDENCE_KINDS,
    FR_DISCARD_TERMINALS,
    FR_RESULT_TERMINALS,
    INVALIDATION_TARGET,
    REFERENCE_LIST_FIELDS,
    SINGLE_VALUE_FIELDS,
    TransitionError,
    UnknownV1Status,
    assert_transition,
    confirming_edge,
    format_id,
    initial_status,
    invalidation_target,
    is_terminal,
    map_v1_status,
    parse_id,
)

KERNEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "team-kits", "kernel")


def test_an_accepted_system_requirement_is_finished_without_being_terminal():
    """BUG-0281 (H7 re-filed): an agreed system requirement carried open work for ever.

    "Terminal" and "finished" are two questions and the kernel only had the first: a terminal state
    has no outgoing edge, while `SR.ACCEPTED` is a life end that still has one (a later requirement
    supersedes it). Every reader that asked `is_terminal` to mean "is this still work" therefore
    answered wrong for the one type whose natural end is not a terminal.

    THE DECLARATION IS CHECKED AGAINST THE AUTOMATON, both ways: a `done_states` entry that is not
    a state of its automaton, and one that is really a terminal, fail at IMPORT -- so the map
    cannot drift away from the states it talks about. And `is_finished` keeps the terminal reading
    for every other type, which the rows below hold: a draft task is unfinished, a validated one is
    finished through its terminal, and a proposed requirement is unfinished.
    """
    assert backlog_types.is_finished("SR", "ACCEPTED") is True
    assert backlog_types.is_terminal("SR", "ACCEPTED") is False, (
        "ACCEPTED must stay non-terminal -- the edge to SUPERSEDED leaves it")
    assert backlog_types.is_finished("SR", "PROPOSED") is False
    assert backlog_types.is_finished("SR", "SUPERSEDED") is True

    assert backlog_types.is_finished("TSK", "DRAFT") is False
    assert backlog_types.is_finished("TSK", "VALIDATED") is True
    assert backlog_types.is_finished("BUG", "OPEN") is False

    for item_type, automaton in backlog_types.AUTOMATA.items():
        for state in automaton.done_states:
            assert state in automaton.states, (item_type, state)
            assert state not in automaton.terminals, (item_type, state)

    with pytest.raises(AssertionError):
        backlog_types._Automaton(chain=("A", "B"), terminals=("C",),
                                 terminal_from={"C": ("A", "B")}, done_states=("C",))
    with pytest.raises(AssertionError):
        backlog_types._Automaton(chain=("A", "B"), terminals=("C",),
                                 terminal_from={"C": ("A", "B")}, done_states=("Z",))


def test_the_fr_result_terminals_partition_the_fr_automaton():
    """BUG-0009(a): the split "points to a result item" vs "points to nothing" is a fact about what
    each FR OUTCOME means, so it is written out -- but pinned to the automaton from both ends. Every
    classified value is a real FR terminal (no dead entry), and together they cover EVERY FR terminal
    (a fourth terminal added to the automaton fails here until it is placed on one side)."""
    terminals = AUTOMATA["FR"].terminals
    assert FR_RESULT_TERMINALS | FR_DISCARD_TERMINALS == terminals
    assert FR_RESULT_TERMINALS.isdisjoint(FR_DISCARD_TERMINALS)


# -- chains and terminals ------------------------------------------------------

def test_every_chain_edge_is_allowed():
    for item_type, auto in AUTOMATA.items():
        for src, dst in zip(auto.chain, auto.chain[1:]):
            assert_transition(item_type, src, dst)  # must not raise


def test_all_edge_endpoints_are_registered_states():
    """Fable-Check 5: a typo'd edge must be impossible, not a dead edge."""
    for item_type, auto in AUTOMATA.items():
        for src, dst in auto.allowed:
            assert src in auto.states and dst in auto.states, (item_type, src, dst)


def test_terminals_have_no_outgoing_edges():
    for item_type, auto in AUTOMATA.items():
        for terminal in auto.terminals:
            assert is_terminal(item_type, terminal)
            outgoing = [e for e in auto.allowed if e[0] == terminal]
            assert outgoing == [], (item_type, terminal, outgoing)


def test_initial_states():
    assert initial_status("PR") == "DRAFT"
    assert initial_status("RQ") == "DRAFT"
    assert initial_status("FR") == "OPEN"
    assert initial_status("BUG") == "OPEN"
    assert initial_status("SR") == "PROPOSED"
    assert initial_status("TSK") == "DRAFT"
    assert initial_status("PROC") == "DRAFT"
    assert initial_status("HYP") == "PROPOSED"
    assert initial_status("EXP") == "DESIGNED"


# -- II.12 named cases ---------------------------------------------------------

def test_tsk_draft_to_in_progress_direct_is_blocked():
    """II.12: 'ungueltiger Statusuebergang (z. B. TSK DRAFT->IN_PROGRESS direkt) -> Block'."""
    with pytest.raises(TransitionError):
        assert_transition("TSK", "DRAFT", "IN_PROGRESS")


def test_tsk_back_edges():
    assert_transition("TSK", "LEASED", "READY")        # lease timeout / spawn failure
    assert_transition("TSK", "IN_PROGRESS", "FAILED")
    assert_transition("TSK", "SUBMITTED", "FAILED")
    assert_transition("TSK", "DONE", "FAILED")
    assert_transition("TSK", "FAILED", "READY")        # approved retry
    assert_transition("TSK", "FAILED", "CANCELLED")


def test_tsk_validated_only_from_done():
    assert_transition("TSK", "DONE", "VALIDATED")
    for src in ("DRAFT", "READY", "LEASED", "IN_PROGRESS", "SUBMITTED", "FAILED"):
        with pytest.raises(TransitionError):
            assert_transition("TSK", src, "VALIDATED")


def test_tsk_terminals_are_terminal():
    for terminal in ("VALIDATED", "CANCELLED"):
        with pytest.raises(TransitionError):
            assert_transition("TSK", terminal, "READY")


def test_bug_verified_only_from_fixed():
    assert_transition("BUG", "FIXED", "VERIFIED")
    with pytest.raises(TransitionError):
        assert_transition("BUG", "TRIAGED", "VERIFIED")


def test_pr_accepted_only_from_delivered():
    assert_transition("PR", "DELIVERED", "ACCEPTED")
    with pytest.raises(TransitionError):
        assert_transition("PR", "APPROVED", "ACCEPTED")


def test_fr_terminal_requires_triage():
    with pytest.raises(TransitionError):
        assert_transition("FR", "OPEN", "MERGED")
    assert_transition("FR", "TRIAGED", "CONVERTED")


def test_blocked_is_not_a_status_anywhere():
    for item_type, auto in AUTOMATA.items():
        assert "BLOCKED" not in auto.states, item_type
        with pytest.raises(TransitionError):
            assert_transition(item_type, auto.initial, "BLOCKED")


def test_unknown_type_and_status_fail_closed():
    with pytest.raises(TransitionError):
        assert_transition("XXX", "DRAFT", "APPROVED")
    with pytest.raises(TransitionError):
        assert_transition("PR", "DRAFT", "SHIPPED")


# -- invalidation table (spec II.2) --------------------------------------------

def test_invalidation_targets_match_spec_table():
    assert INVALIDATION_TARGET == {
        "PR": "DRAFT",
        "RQ": "DRAFT",
        "CR": "DRAFT",
        "PROC": "DRAFT",
        "BUG": "TRIAGED",
        "SR": "PROPOSED",
        "EXP": "DESIGNED",
    }


def test_hyp_has_no_invalidation_target():
    """Spec II.2: HYP deliberately absent -- no approval_ref, rides on RQ scope."""
    with pytest.raises(KeyError):
        invalidation_target("HYP")


def test_invalidation_targets_are_valid_states():
    for item_type, target in INVALIDATION_TARGET.items():
        assert target in AUTOMATA[item_type].states


# -- id convention -------------------------------------------------------------

def test_id_roundtrip():
    assert format_id("TSK", 42) == "TSK-0042"
    assert parse_id("TSK-0042") == ("TSK", 42)
    assert parse_id("PR-12345") == ("PR", 12345)  # >4 digits allowed


def test_id_rejects_garbage():
    for bad in ("TSK42", "tsk-0042", "TSK-42", "XXX-0042", "", "PRD-0001"):
        with pytest.raises(ValueError):
            parse_id(bad)


# -- V1 -> V2 mapping (spec II.10) ---------------------------------------------

def test_v1_mapping_table():
    assert map_v1_status("TSK", "TODO") == ("TSK", "READY", False)
    assert map_v1_status("PRD", "TESTED") == ("PR", "DELIVERED", False)
    assert map_v1_status("PRD", "DONE") == ("PR", "ACCEPTED", True)
    assert map_v1_status("PRD", "PROPOSED") == ("PR", "DRAFT", False)
    assert map_v1_status("SR", "DRAFT") == ("SR", "PROPOSED", False)
    assert map_v1_status("SR", "ACTIVE") == ("SR", "ACCEPTED", False)
    assert map_v1_status("SR", "DONE") == ("SR", "ACCEPTED", True)
    assert map_v1_status("PROC", "PROPOSED") == ("PROC", "DRAFT", False)


def test_v1_mapping_targets_are_valid_v2_states():
    """Every mapped status has to be one the target type can actually carry.

    Asked of `status_values`, not of `AUTOMATA` directly: a status-bearing type without an
    automaton (`DEC`, `INV`) is not exempt from the question, it just answers it from a different
    map -- and reading `AUTOMATA[v2t]` raised `KeyError` the moment the table gained its first
    `DEC` row, which is a crash rather than a verdict.
    """
    from kernel.backlog_types import V1_STATUS_MAPPING, status_values
    for (_v1t, _v1s), (v2t, v2s, _arch) in V1_STATUS_MAPPING.items():
        assert status_values(v2t), (v2t, "has no status vocabulary at all")
        assert v2s in status_values(v2t), (v2t, v2s)


def test_unknown_v1_status_blocks():
    """Spec II.10: unknown values -> block + Decision item, never guess."""
    with pytest.raises(UnknownV1Status):
        map_v1_status("SR", "WEIRD_LEGACY_STATE")


# -- the Evidence vocabulary: one list, one derivation -------------------------

def test_the_delivery_judging_kinds_are_derived_from_the_kinds_not_listed_again():
    """`QA_EVIDENCE_KINDS` must be a SUBTRACTION, not a second spelling of the same words.

    The two constants held the same three words twice, and that shape has produced one defect per
    review round in this repo: a kind added to `EVIDENCE_KINDS` alone becomes a verdict a role can
    legally record and the merge gate never reads — `gate_git` would answer "no QA Evidence" for
    work that has some. Nothing was red about it, because both lists were internally consistent.

    So the assertion is on the SOURCE of the assignment, read from the parsed module rather than
    matched as text: whatever `QA_EVIDENCE_KINDS` is built from, it may not be the kind words
    themselves. The partition below is what the derivation then guarantees and what a reader can
    check against the one declared exception.
    """
    import ast
    from kernel.backlog_types import (EVIDENCE_KINDS, PROJECT_EVIDENCE_KINDS, QA_EVIDENCE_KINDS)
    assert QA_EVIDENCE_KINDS | PROJECT_EVIDENCE_KINDS == EVIDENCE_KINDS
    assert not (QA_EVIDENCE_KINDS & PROJECT_EVIDENCE_KINDS)
    source = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "team-kits", "kernel", "backlog_types.py")
    with open(source, encoding="utf-8") as handle:
        module = ast.parse(handle.read())
    assignments = [node for node in module.body if isinstance(node, ast.Assign)
                   and any(getattr(target, "id", None) == "QA_EVIDENCE_KINDS"
                           for target in node.targets)]
    assert len(assignments) == 1, "QA_EVIDENCE_KINDS is assigned %d times" % len(assignments)
    spelled = {node.value for node in ast.walk(assignments[0].value)
               if isinstance(node, ast.Constant) and node.value in EVIDENCE_KINDS}
    assert not spelled, (
        "QA_EVIDENCE_KINDS spells %s literally instead of deriving the set. A kind added to "
        "EVIDENCE_KINDS would then have to be remembered here too, and forgetting it is silent: "
        "the kind stays legal at capture and stops counting for the merge gate."
        % ", ".join(sorted(spelled)))


def test_the_confirming_edge_is_derived_from_each_types_own_edge_set():
    """`confirming_edge` tells "closed because it was confirmed" from "closed because it was
    abandoned", and it reads that off the automaton instead of a table.

    The property: the chain's LAST status, when it is a terminal whose only incoming edge comes
    from its chain predecessor. A terminal a type can be dropped into (REJECTED, DUPLICATE,
    CANCELLED, SUPERSEDED) has several sources and is therefore not one.

    This matters because `state.CONFIRMING_EVIDENCE` hangs the regression-test rule on that edge:
    renaming BUG's FIXED or VERIFIED moves the rule with the automaton, and a chain that gains a
    second way into its final status stops being a confirmation by construction.
    """
    assert confirming_edge("BUG") == ("FIXED", "VERIFIED")
    assert confirming_edge("TSK") == ("DONE", "VALIDATED")
    assert confirming_edge("PR") == ("DELIVERED", "ACCEPTED")
    # FR/HYP/SR/PROC end in a terminal reachable from several statuses, or have no terminal on
    # the chain at all -- there is nothing to confirm, so there is no edge
    assert confirming_edge("FR") is None
    assert confirming_edge("HYP") is None
    assert confirming_edge("SR") is None
    assert confirming_edge("unknown-type") is None
    # ...and the derivation really is over the EDGES: every answer names a real edge of the type
    for item_type, edge in ((t, confirming_edge(t)) for t in AUTOMATA):
        if edge is not None:
            assert edge in AUTOMATA[item_type].allowed, item_type


def test_a_final_status_reachable_without_the_chain_is_not_a_confirmation(monkeypatch):
    """THE HALF NO SHIPPED AUTOMATON EXERCISES TODAY, measured on a synthetic one rather than
    asserted in prose -- without this the "only incoming edge" clause of `confirming_edge` was
    unfalsifiable: every current type whose chain ends in a terminal happens to have exactly one
    edge into it, so removing the clause changed no answer.

    It is the clause that carries the meaning. A status the item can be DROPPED into is not proof
    that the work was done, so hanging a "show me the regression test" rule on it would demand
    evidence for an abandonment -- and, worse, would let a type that gains such a shortcut keep
    the rule's NAME while losing its content.
    """
    both_ways = _Automaton(
        chain=("OPEN", "FIXING", "CLOSED"),
        terminals=("CLOSED",),
        terminal_from={"CLOSED": ("OPEN",)},      # ...and straight from OPEN, skipping the work
    )
    one_way = _Automaton(
        chain=("OPEN", "FIXING", "CLOSED"), terminals=("CLOSED",), terminal_from={})
    monkeypatch.setitem(AUTOMATA, "XX", both_ways)
    assert confirming_edge("XX") is None
    monkeypatch.setitem(AUTOMATA, "XX", one_way)
    assert confirming_edge("XX") == ("FIXING", "CLOSED")


# -- the fields outside the contract universe (BUG-0038 / H43) -----------------------------------

# Where a read of an item field ENDS UP counts as reading it as a sequence. `field_elements` is in
# here on purpose: it is the fix, and a site that goes through it must stay VISIBLE to the
# derivation -- otherwise repairing the last reader of a field would delete that field from the
# derived set and red the tuple from the other end.
_SEQUENCE_CALLS = frozenset(("list", "tuple", "set", "sorted", "len", "join", "enumerate",
                             "reversed", "any", "all", "field_elements"))

# How a name comes to hold an ITEM: a kernel call that hands back stored item content, or
# `active_items`, the mapping the state validator passes between its own checks. Both are matched
# as NAMES, so renaming one narrows the derivation silently -- the limit is named in
# `_item_fields_read_as_sequences`, and the equality test's floor is what would notice a reader
# that had gone completely blind.
_ITEM_SOURCES = ("read_item", "read_anywhere", "iter_active_items", "_iter_active", "active_items")


def _kernel_trees():
    trees = {}
    for name in sorted(os.listdir(KERNEL_DIR)):
        if name.endswith(".py"):
            with open(os.path.join(KERNEL_DIR, name), encoding="utf-8") as handle:
                trees[name] = ast.parse(handle.read(), name)
    return trees


def _module_string_constants(trees):
    """Every package-level `NAME = "literal"`, across all modules.

    `DEC_SUPERSEDES_FIELD` is read as a NAME at all four of its read sites, so a reader that only
    understood string literals would have found `design_refs` and `premise_rechecks` and reported
    the third field as absent -- i.e. it would have argued for deleting a live entry.
    """
    constants = {}
    for tree in trees.values():
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                    and isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = node.value.value
    return constants


def _item_bound_names(tree):
    """The names this module binds from an item source -- plus aliases, to a fixed point."""
    names = set()
    for _pass in range(4):
        before = set(names)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                value = node.value
                from_item = (isinstance(value, ast.Call)
                             and getattr(value.func, "attr", "") in _ITEM_SOURCES)
                if from_item or (isinstance(value, ast.Name) and value.id in names):
                    for target in node.targets:
                        names.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
            if isinstance(node, (ast.For, ast.comprehension)):
                source = ast.dump(node.iter)
                if any(name in source for name in _ITEM_SOURCES):
                    names.update(n.id for n in ast.walk(node.target) if isinstance(n, ast.Name))
        if names == before:
            break
    return names


def _key_read(node, names, constants, aliases=()):
    """The field `node` reads off an item -- `<item>.get("f")`, `<item>["f"]`, or a local name that
    was bound to one of those. None if it is neither.

    THE ALIAS HOP IS THE COMMON IDIOM AND WAS THE FOURTH BLIND SPOT. Measured: an injected direct
    read turned both tripwires red, while the same read written in two steps
    (`risky = item.get("f") or []` / `for ref in risky`) passed both -- any binding to a local name
    broke the chain, and `dispatch.py:1084` shows the two-step shape is lived kernel style. ONE hop
    is followed, deliberately: two would be a dataflow analysis, and what the second hop would buy
    is unmeasured. The hop is followed WITHOUT SCOPE ANALYSIS, so a name bound in one function and
    iterated in another links across -- that direction ADDS a candidate and shows up as a red
    equality, never as a quiet miss.
    """
    if isinstance(node, ast.Name) and node.id in aliases:
        return aliases[node.id]
    while isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        node = node.values[0]      # the `... or []` tail is the shape this class was written in
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in ("get", "pop") and node.args:
        receiver, key = node.func.value, node.args[0]
    elif isinstance(node, ast.Subscript):
        receiver, key = node.value, node.slice
    else:
        return None
    if not (isinstance(receiver, ast.Name) and receiver.id in names):
        return None
    if isinstance(key, ast.Constant) and isinstance(key.value, str):
        return key.value
    if isinstance(key, ast.Name) and key.id in constants:
        return constants[key.id]
    if isinstance(key, ast.Attribute) and key.attr in constants:
        return constants[key.attr]
    return None


def _key_read_aliases(tree, names, constants):
    """{local name -> the field it was bound to} for every `X = <item read>` in this module.

    A read wrapped in a call (`X = field_elements(item.get("f"))`) is NOT an alias: the value has
    already been through the one definition, so following it would report the fix as an offender.
    """
    aliases = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        field = _key_read(node.value, names, constants)
        if not field:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                aliases[target.id] = field
    return aliases


def _item_fields_read_as_sequences():
    """{field -> {(where, what consumes it)}} for every item field the kernel reads ELEMENT-WISE
    and no contract declares -- derived from the kernel's own sources, not from the tuple.

    THE DERIVATION `REFERENCE_LIST_FIELDS` IS MEASURED AGAINST (BUG-0038 / H43). Per module: the
    names bound from an ITEM source (`_item_bound_names`), then every mapping read off such a name
    that lands in a sequence context -- a `for`, a comprehension, or one of `_SEQUENCE_CALLS`.
    Fields any contract declares drop out (`backlog_types._contract_fields`, both sources, plus the
    kernel-set ones), because those are the universe `migrate.parse_field_map` already bounds and
    the TSK-0033 sweep already measured. What remains is the class that fell between the two.

    ONE LOCAL BINDING IS FOLLOWED between the read and the sequence context (`_key_read_aliases`),
    because the two-step spelling is the idiom this code is written in and it was invisible here.

    WHAT THIS DOES NOT SEE, named rather than promised away:
      * a value that reaches its reader through a RETURN dict rather than an item read. `cli.py`
        prints the `design_refs` of `result["root"]` that way, and that site is measured by
        `test_staging_cli.test_a_scalar_design_ref_survives_the_freeze_as_one_reference` instead;
      * a field name that is neither a literal nor a package-level string constant;
      * a value whose way from the read to the sequence context is anything MORE than the one local
        binding `_key_read_aliases` follows. The hop is the property and the spelling is not: past
        that single hop the trace ends, and by what the value travelled makes no difference. One hop
        is followed because the two-step idiom is what this code is written in; the second is where
        this stops being a reader and becomes a dataflow analysis, and what that would buy here is
        unmeasured;
      * any reader outside `team-kits/kernel/` -- the kits' hooks and scripts were the TSK-0033
        sweep's subject and are measured there.
    """
    trees = _kernel_trees()
    constants = _module_string_constants(trees)
    declared = set(_KERNEL_SET)
    for fields in backlog_types._contract_fields().values():
        declared |= set(fields)
    found = {}
    for module, tree in trees.items():
        names = _item_bound_names(tree)
        aliases = _key_read_aliases(tree, names, constants)
        for node in ast.walk(tree):
            places = []
            if isinstance(node, (ast.For, ast.comprehension)):
                places.append((node.iter, "for" if isinstance(node, ast.For) else "comprehension"))
            elif isinstance(node, ast.Call):
                called = (node.func.id if isinstance(node.func, ast.Name)
                          else getattr(node.func, "attr", ""))
                if called in _SEQUENCE_CALLS:
                    places.extend((argument, called) for argument in node.args)
            for place, consumer in places:
                field = _key_read(place, names, constants, aliases)
                if field and field not in declared:
                    found.setdefault(field, set()).add(
                        ("%s:%d" % (module, place.lineno), consumer))
    return found


def test_the_reference_list_fields_are_what_the_kernel_reads_elementwise():
    """Both ends of the one enumeration BUG-0038 left behind.

    `REFERENCE_LIST_FIELDS` names item fields NO capture contract declares, so no property of
    `REQUIRED_FIELDS`/`OPTIONAL_FIELDS` can produce them -- which is exactly how the TSK-0033 sweep
    walked past all three. The tuple is therefore held against a derivation over the running kernel
    sources, in BOTH directions: a name the kernel no longer reads element-wise is a dead entry, and
    a field the kernel reads that way without being declared is the next H43.

    The derivation's own blind spots are in `_item_fields_read_as_sequences`, not glossed here.
    """
    derived = _item_fields_read_as_sequences()
    assert set(REFERENCE_LIST_FIELDS) == set(derived), (
        "declared but not read element-wise anywhere: %s; read element-wise but not declared: %s"
        % (sorted(set(REFERENCE_LIST_FIELDS) - set(derived)),
           sorted(set(derived) - set(REFERENCE_LIST_FIELDS))))
    # ...and the derivation has to have teeth: an instrument that finds nothing would satisfy the
    # equality above only for an empty tuple, and pass silently the day it stops parsing.
    assert derived, "the reader found no element-wise item-field read at all in team-kits/kernel/"


def test_every_kernel_read_of_a_reference_list_field_goes_through_field_elements():
    """The fix, measured at every site the derivation finds rather than at the ones someone recalled.

    A bare `for ref in item.get(f) or []` reads a WORD as its letters, and BUG-0038 is what that
    cost in the one case that WRITES the value back (`staging.freeze_design`: 35 entries in the
    canonical item, validator silent). `backlog_types.field_elements` is the single definition of
    "how many things does this field hold"; a site that does not go through it is a reader that
    decided the shape for itself.
    """
    offenders = sorted(
        "%s (consumed by %s, not field_elements)" % (where, consumer)
        for field, sites in _item_fields_read_as_sequences().items()
        for where, consumer in sites if consumer != "field_elements")
    assert not offenders, offenders


def test_every_captured_type_declares_the_outline_field_and_none_declares_it_twice():
    """FR-0017: `area` is a CONTRACT field of every type `capture` creates, not a loose key.

    The distinction is the one `PROC.derives_from` and `FR.related_pr` cost a round each: a field
    the contract does not declare is invisible to everything that derives from the contract --
    `_contract_fields`, and through it the field-name universe the reference sweep bounds itself
    with. `capture` stores an undeclared key just as happily, which is exactly why its presence in
    the store proves nothing and this reads the derivation instead.

    The counter-direction is the second assertion: it comes from ONE place, so no type carries it
    twice and no type's own `OPTIONAL_FIELDS` has to repeat it.
    """
    contracts = backlog_types._contract_fields()
    missing = sorted(item_type for item_type in backlog_types.REQUIRED_FIELDS
                     if backlog_types.AREA_FIELD not in contracts.get(item_type, ()))
    assert not missing, missing
    assert not [item_type for item_type, names in backlog_types.OPTIONAL_FIELDS.items()
                if backlog_types.AREA_FIELD in names]


def test_the_single_value_fields_are_contract_fields_nothing_resolves_elementwise():
    """One end of the `SINGLE_VALUE_FIELDS` enumeration: the entry that has gone DEAD (DEC-0043).

    An entry is a claim about a field of a type, so it dies in two ways and both are checked here:
    the field leaves that type's contract (the refusal then guards a field no item can carry), or
    the same field turns up in `REFERENCE_LIST_FIELDS`, whose whole property is that the kernel
    resolves its ELEMENTS -- one field cannot both hold one thing and be taken apart.

    The OTHER end -- the entry that was never needed, because the shipped readers learned to read
    several -- is `test_hooks.test_the_shipped_readers_of_a_single_value_field_still_read_one_value`;
    it needs the readers themselves and lives with them.
    """
    contracts = backlog_types._contract_fields()
    assert SINGLE_VALUE_FIELDS, "an empty contract would make both ends of this vacuous"
    for (item_type, field), (why, remedy) in sorted(SINGLE_VALUE_FIELDS.items()):
        # the contradiction is asked FIRST, or it could never be the answer: a
        # `REFERENCE_LIST_FIELDS` name is one NO contract declares by construction, so the
        # membership check below would always fire first and diagnose the wrong thing.
        assert field not in REFERENCE_LIST_FIELDS, (
            "%s is declared as holding ONE thing and as a field whose elements the kernel resolves"
            % field)
        assert field in contracts.get(item_type, ()), (
            "%s.%s: no contract of that type declares the field" % (item_type, field))
        assert why and remedy, "%s.%s: an entry owes a why and a remedy" % (item_type, field)


def test_the_evidence_rule_names_only_edges_the_automaton_has():
    """`state.CONFIRMING_EVIDENCE` may not carry a type whose automaton has no confirming edge --
    that row would be a rule that can never fire, which is the shape this repo keeps finding.

    It also pins the SCOPE honestly: the map is deliberately smaller than the set of confirming
    edges, because a required proof is a promise a shipped text makes and only BUG's is written
    down. A new row is fine; a row for a type with no such edge is not.
    """
    for item_type, kind in CONFIRMING_EVIDENCE.items():
        assert confirming_edge(item_type) is not None, item_type
        assert kind in EVIDENCE_KINDS, (item_type, kind)


def test_an_amendment_is_the_type_that_names_the_revision_it_amends():
    """Both ends of the ONE field name BUG-0040's derivation rests on.

    `AMENDMENT_TYPES` decides whose `acceptance_criteria` an approval may add to a root's
    contract (`dispatch._amendment_criteria_locked`), so a derivation that silently answered
    "nobody" would put the pilot-3 refusal straight back, and one that answered "everybody" would
    let any approved item under the root lend its criteria to any task.

    THE PROPERTY, stated over every type the contracts declare rather than over CR: an amendment is
    the type whose own contract makes it name the REVISION of the item it amends. The dead end is
    the field name -- rename `target_revision` and the set empties. The needless end is the
    counter-direction: `BUG` binds to a root and carries `acceptance_criteria`, and is NOT an
    amendment, so the field really discriminates instead of merely selecting everything.

    The two duties that make the derivation SAFE are asserted for every member, because they are
    what the dispatch reader assumes and neither is guaranteed by the field name: an amendment must
    be able to NAME its target (a binding field), and its criteria must be inside what a scope
    approval hashes -- otherwise `dispatch._approval_covers_criteria` would vouch for content no
    user ever signed.
    """
    declared = backlog_types.DECLARED_REQUIRED_FIELDS
    derived = backlog_types.AMENDMENT_TYPES
    assert derived, (
        "no type declares %r -- the amendment derivation is dead and every approved amendment's "
        "criteria are unreachable again (BUG-0040)" % backlog_types.AMENDMENT_REVISION_FIELD)
    for item_type, fields in declared.items():
        assert (item_type in derived) == (backlog_types.AMENDMENT_REVISION_FIELD in fields), item_type
    assert "BUG" not in derived, (
        "BUG binds to a root and carries acceptance_criteria -- if it is an amendment, the field "
        "no longer discriminates and the criteria of every approved bug widen the root's universe")
    for item_type in sorted(derived):
        assert backlog_types.PARENT_FIELDS.get(item_type), (
            "%s is an amendment with no binding field -- it can never name the root it amends"
            % item_type)
        assert "acceptance_criteria" in backlog_types.HASHED_FIELDS.get(item_type, ()), (
            "%s is an amendment whose criteria are not approval-relevant content" % item_type)
        signed = approvals.item_subject_manifest(
            {"id": "%s-0001" % item_type, "revision": 1, "acceptance_criteria": []}, "scope")
        assert "acceptance_criteria" in signed, (
            "%s: a scope approval does not sign its criteria, so nothing backs the widening"
            % item_type)


# -- the third Evidence outcome (FR-0082) and a remedy read off the table (BUG-0089) ------------

def test_only_the_passing_result_opens_anything_the_kernel_decides():
    """FR-0082: adding a verdict value must not open a door, and this measures that it does not.

    THE PROPERTY, over the RUNNING readers rather than over a docstring: every place in the kernel
    and in the two kits that ship `gate_git` which decides on an Evidence `result` compares against
    `PASSING_RESULT` -- so a value added to `EVIDENCE_RESULTS` arrives CLOSING. Read out of the
    source with `ast`, because a grep over the text would be satisfied by the comment that claims
    it.

    RED WITHOUT THE FIX: with any of those comparisons written as the literal `"pass"` again the
    claim would still hold by accident, so what this really catches is the other direction -- a
    reader that compares against `"fail"` (or against any member of the vocabulary that is not the
    passing one), which is how a third value becomes a silently-opening one.
    """
    import ast as _ast

    readers = [os.path.join(_TEAM_KITS, "kernel", name)
               for name in ("report.py", "state.py")]
    readers += [os.path.join(_TEAM_KITS, kit, "hooks", "gate_git.py")
                for kit in ("dev-team", "research-team")]
    closing = set(backlog_types.EVIDENCE_RESULTS) - {backlog_types.PASSING_RESULT}
    offences = []
    for path in readers:
        tree = _ast.parse(open(path, encoding="utf-8").read())
        for node in _ast.walk(tree):
            # `<something>["result"] <op> <constant>` and `.get("result") <op> <constant>`
            if not isinstance(node, _ast.Compare) or len(node.comparators) != 1:
                continue
            if not _reads_the_result_field(node.left):
                continue
            for other in node.comparators:
                if isinstance(other, _ast.Constant) and other.value in closing:
                    offences.append("%s:%d compares a verdict against %r"
                                    % (os.path.basename(path), node.lineno, other.value))
    assert not offences, (
        "a reader that decides on a NON-passing verdict value by name stops deciding the day the "
        "vocabulary grows: %s" % "; ".join(offences))


def _reads_the_result_field(node):
    """True when this expression reads an Evidence `result` -- subscript or `.get`."""
    import ast as _ast

    if isinstance(node, _ast.Subscript) and isinstance(node.slice, _ast.Constant):
        return node.slice.value == "result"
    if (isinstance(node, _ast.Call) and isinstance(node.func, _ast.Attribute)
            and node.func.attr == "get" and node.args
            and isinstance(node.args[0], _ast.Constant)):
        return node.args[0].value == "result"
    return False


def test_a_blocked_verdict_is_in_the_vocabulary_and_carries_its_own_field_name():
    """FR-0082: the two names the rest of the kernel spells the third outcome with."""
    assert backlog_types.BLOCKED_RESULT in backlog_types.EVIDENCE_RESULTS
    assert backlog_types.PASSING_RESULT in backlog_types.EVIDENCE_RESULTS
    assert backlog_types.BLOCKED_REASON_FIELD in backlog_types.OPTIONAL_FIELDS["EVD"]
    # ...and it is NOT required of the type: an EVD is immutable, so a required field here would
    # turn every Evidence a project already holds into a validator error no command can repair.
    assert backlog_types.BLOCKED_REASON_FIELD not in backlog_types.REQUIRED_FIELDS["EVD"]


@pytest.mark.parametrize("item_type", sorted(AUTOMATA))
def test_the_replanning_route_names_only_edges_the_automaton_has(item_type):
    """BUG-0089, both ends, over every shipped automaton.

    END ONE -- nothing NAMED is unwalkable: every target the route offers is an edge the automaton
    really has from that status. That is the half the bug was: `TSK` READY offered a transition to
    DRAFT and the automaton has no edge into DRAFT at all.

    END TWO -- nothing WALKABLE that belongs in the route is left out: from each status, the route
    is exactly the reachable initial status plus the reachable terminals, so a new back-edge into
    the planning status starts being offered without an edit here.
    """
    from kernel.backlog_types import replanning_route

    automaton = AUTOMATA[item_type]
    for status in sorted(automaton.states):
        route = replanning_route(item_type, status)
        reachable = {dst for src, dst in automaton.allowed if src == status}
        for target in route["replan"] + route["close"]:
            assert target in reachable, (item_type, status, target)
        assert set(route["replan"]) == reachable & {automaton.initial}
        assert set(route["close"]) == reachable & automaton.terminals


# -- the milestone type (DEC-0064, FR-0079 -- the kernel half of stream A's seam) ---------------

def test_the_milestone_automaton_can_only_end_a_milestone_once():
    """DEC-0064 (2): `REACHED` through the chain, `MISSED`/`DROPPED` only from `PLANNED`.

    THE PROPERTY, and it is why the terminals are not all reachable from everywhere: a milestone
    that has been reached cannot afterwards have been missed or called off. The construction
    self-check inside `_Automaton` already refuses an edge out of a terminal at import time; what
    this adds is the direction that check cannot see -- that the two ways of NOT reaching it are
    open exactly while the milestone is still ahead.
    """
    automaton = AUTOMATA["MST"]
    assert automaton.initial == "PLANNED"
    assert automaton.terminals == frozenset(("REACHED", "MISSED", "DROPPED"))
    assert automaton.allowed == {("PLANNED", "REACHED"), ("PLANNED", "MISSED"),
                                 ("PLANNED", "DROPPED")}
    assert backlog_types.INVALIDATION_TARGET.get("MST") is None
    assert not [pair for pair in approvals.APPROVAL_TRANSITIONS if pair[0] == "MST"], (
        "a milestone is a date, not something a user signs (DEC-0064 (2))")


def test_every_declared_date_field_is_a_field_its_type_really_has():
    """`DATE_FIELDS` is a map of names beside a contract, so both its ends are measured.

    END ONE -- every declared date field is in that type's own field contract (required or
    optional): a rule about a field the type does not have is a rule that never fires.

    END TWO -- and this is the one that catches a half-applied seam: `date.fromisoformat` has to be
    able to read the values the shipped items carry, so the declaration is not merely well-formed
    but usable. Asserted by parsing a value the field is documented to hold.
    """
    from datetime import date

    from kernel.backlog_types import DATE_FIELDS, OPTIONAL_FIELDS, REQUIRED_FIELDS

    for item_type, fields in DATE_FIELDS.items():
        contract = (set(REQUIRED_FIELDS.get(item_type, ()))
                    | set(OPTIONAL_FIELDS.get(item_type, ())))
        for field in fields:
            assert field in contract, (item_type, field)
    assert date.fromisoformat("2026-10-01")


# -- the inbox and the hole (BUG-0091/DEC-0066, FR-0087/DEC-0073) ---------------

def test_the_inbox_types_are_the_ones_whose_triage_names_a_result():
    """`TRIAGE_RESULT_LINK` is a contract, so both of its ends are held to the automata.

    A type is an INBOX type when its lifecycle can end by naming the item it BECAME. What makes it
    a contract and not a derivation is that no shape of an automaton tells a triage outcome from
    any other terminal -- it is a fact about what the outcome means. So the tripwire holds it to
    what CAN go stale: every terminal named here is one its type really has, and the field named
    here is one the type may carry.
    """
    import kernel.backlog_types as bt

    assert bt.TRIAGE_RESULT_LINK, "no type is the inbox any more, so nothing is refused under one"
    contract = bt._contract_fields()
    for item_type, (terminals, field) in sorted(bt.TRIAGE_RESULT_LINK.items()):
        automaton = bt.AUTOMATA[item_type]
        assert terminals <= automaton.terminals, (item_type, sorted(terminals))
        assert terminals, "%s is in the map and names no outcome" % item_type
        assert bt.is_inbox_type(item_type)
        # the field is a duty rather than a capture field, so it is enough that nothing else
        # already claims the name for this type
        assert field not in contract.get(item_type, ()), (item_type, field)
    for item_type in bt.AUTOMATA:
        assert bt.is_inbox_type(item_type) == (item_type in bt.TRIAGE_RESULT_LINK), item_type


def test_every_status_dependent_duty_names_a_status_its_type_really_has():
    """`STATUS_DEPENDENT_FIELDS` is the map the validator's duty loop reads -- both ends measured.

    A duty keyed on a status the automaton does not have is a rule that can never fire, which is
    the shape a renamed status leaves behind. A duty naming a field the type may not carry is the
    other end: it would be a demand no body could satisfy.
    """
    import kernel.backlog_types as bt

    assert bt.STATUS_DEPENDENT_FIELDS
    contract = bt._contract_fields()
    for (item_type, status), field in sorted(bt.STATUS_DEPENDENT_FIELDS.items()):
        assert item_type in bt.AUTOMATA, item_type
        assert status in bt.AUTOMATA[item_type].states, (item_type, status)
        declared = set(contract.get(item_type, ()))
        elsewhere = set().union(*contract.values()) - declared
        assert field in declared or field not in elsewhere, (
            "%s owes %r in %s, and that field belongs to another type's contract"
            % (item_type, field, status))


def test_the_hole_contract_is_a_subset_of_the_contract_its_type_declares():
    """A hole owes LESS than its type, and never something its type does not know.

    `HOLE_REQUIRED_FIELDS` is what `required_fields_of` holds a hole to instead of the full `BUG`
    contract, because a hole is a defect nobody is closing -- `expected`, `repro` and
    `acceptance_criteria` would be a form filled in for a fix that is not planned. What must hold
    is that every field it DOES demand is one a `BUG` may carry, or the demand could not be met.
    """
    import kernel.backlog_types as bt

    declared = set(bt._contract_fields()["BUG"])
    assert set(bt.HOLE_REQUIRED_FIELDS) <= declared, (
        sorted(set(bt.HOLE_REQUIRED_FIELDS) - declared))
    assert set(bt.HOLE_REQUIRED_FIELDS) < set(bt.DECLARED_REQUIRED_FIELDS["BUG"]), (
        "the hole contract is not narrower than its type's, so it buys nothing")
    for field in (bt.HOLE_NUMBER_FIELD, bt.HOLE_LIMIT_FIELD, bt.HOLE_TEST_FIELD):
        assert field in bt.OPTIONAL_FIELDS["BUG"], field
        assert field not in bt.REQUIRED_FIELDS["BUG"], (
            "%s is required of every BUG, which turns 91 stored records into validator errors"
            % field)

    # ...and the switch really switches: a BUG carrying a hole number is held to the hole contract
    assert bt.required_fields_of("BUG", {bt.HOLE_NUMBER_FIELD: "H1"}) == bt.HOLE_REQUIRED_FIELDS
    assert bt.required_fields_of("BUG", {}) == bt.DECLARED_REQUIRED_FIELDS["BUG"]
    assert bt.required_fields_of("PR", {bt.HOLE_NUMBER_FIELD: "H1"}) == \
        bt.DECLARED_REQUIRED_FIELDS["PR"]


def test_the_hole_exception_ending_is_reachable_only_from_a_judged_hole():
    """The ending FR-0087 asked for, held to the automaton rather than to this sentence.

    A user accepts an exception for a gap somebody has LOOKED at -- never for one nobody has read
    (`OPEN`) and never for one already fixed. And it is a TERMINAL: nothing walks out of it, so an
    acceptance cannot be edited into something the user never said; a falling exception (DEC-0069
    (3)) is a new item with its own measurement.
    """
    import kernel.backlog_types as bt

    automaton = bt.AUTOMATA["BUG"]
    status = bt.HOLE_EXCEPTION_STATUS
    assert status in automaton.terminals
    sources = {src for src, dst in automaton.allowed if dst == status}
    assert sources == {"TRIAGED"}, sources
    assert not [edge for edge in automaton.allowed if edge[0] == status]


def test_the_hole_contract_is_the_reading_side_and_capture_still_asks_the_full_one(tmp_path):
    """Where the narrower hole contract applies -- measured on both surfaces, not assumed.

    `required_fields_of` is what `report.validate_state` holds a STORED item to, and
    `state.capture_migrated_hole` writes past the field contract like every migration door. But
    `state.capture` asks `REQUIRED_FIELDS` through `capture_preflight`, so `capture --hole` still
    owes the full `BUG` contract. The comment at `HOLE_REQUIRED_FIELDS` described one half as the
    whole until the round-1 verification measured the other.
    """
    import kernel.backlog_types as bt
    from kernel.state import ProjectState, StateError

    root = tmp_path / "project_memory"
    root.mkdir()
    state = ProjectState(str(root))
    state.capture("PR", {"title": "goal", "class": "normal", "problem": "p", "goal": "g",
                         "acceptance_criteria": [{"id": "AC-1", "text": "t"}], "invariants": [],
                         "out_of_scope": [], "priority": "high", "user_story": "As the lead"})
    thin = {"title": "a gap", "related_pr": "PR-0001", "observed": "measured", "severity": "low"}

    with pytest.raises(StateError) as refusal:
        state.capture("BUG", dict(thin), hole=True)
    for field in ("expected", "repro", "acceptance_criteria"):
        assert field in str(refusal.value), (field, str(refusal.value))

    # ...while the migration door writes the same body, and the validator judges it by the narrower
    # contract rather than reporting three missing fields
    stored = state.capture_migrated_hole(dict(thin, **{bt.HOLE_NUMBER_FIELD: "H1"}), "TRIAGED")
    from kernel import report
    assert not [f for f in report.validate_state(state)
                if f["item"] == stored["id"] and "missing" in f["message"]], (
        "the validator asked a stored hole for the fields the hole contract does not demand")
