"""Do two open work orders own a common file? -- the pre-dispatch check of DEC-0062 (1)/(2).

WHAT IT IS FOR. A generation is cut by FILE OWNERSHIP: every stream owns a disjoint set of files,
and two streams whose `allowed_scope`s reach the same file collide in the merge instead of in the
cut. That rule was carried by the orchestrator's reading alone. This is the reading made
mechanical, and it lives in the KERNEL rather than in a repo script because the three kits share
one kernel and a project reaches it through `scripts/harness.py check-scopes` -- measured by
stream D (`H136`): a script under a skill directory is rc 2 at `gate_write_scope`, so there is no
executable route out of a skill, and a copy per kit would be a fourth spelling of the predicate.

THE PREDICATE IS THE ONE THAT RUNS, and that is the whole point. `allowed_scope` is enforced by
`gate_write_scope`, whose `_matches` decides prefix-vs-glob, what `**` widens and what a single `*`
does NOT cross -- fed with both sides FOLDED through that module's own `_norm`, which is how the
gate really asks it. A second spelling here -- `fnmatch`, a hand-rolled regex, or the raw predicate
without the folding -- would answer a different question than the gate the specialists actually
meet, and the disagreement would show up as a collision nobody predicted. The measured case is the
folding: with `_matches` asked raw, `Tools/**` and `tools/**` came back DISJOINT while the gate
grants both orders the same files. So both halves are IMPORTED and asked.
`tools/test_parallel_scopes.py::test_the_matcher_is_the_shipped_gates_own_and_not_a_second_spelling`
reads the answer off the imported module rather than off this sentence.

TWO UNIVERSES, ONE PREDICATE. "In scope" is asked of paths, so the answer depends on which paths
exist. The check therefore asks it twice over the same predicate:

  * the REAL TREE (`git ls-files -c -o --exclude-standard`) -- every file that is there today; and
  * the WITNESSES of the two orders -- one concrete path per `allowed_scope` entry, its wildcards
    filled with a placeholder segment. A stream that will CREATE `src/api.py` owns nothing under
    `src/**` today, so the tree half is blind to two orders that both claim an empty directory;
    the witness half is not.

Neither half is complete on its own, and the incompleteness is measured rather than assumed -- but
the class it consists of is NOT the one this paragraph named until BUG-0218 was closed. The pair
`a/*x` x `a/y*`, which no single-entry filling reached, is found now (`pair_witnesses` unifies the
two entries and yields `a/yx`); what remained after that was a different class, measured by brute
force over every path up to five segments against the SHIPPED predicate, 6 pairs -- and its
mechanism is one sentence: an entry WITHOUT a wildcard is a DIRECTORY PREFIX to the gate (it owns
everything under it) and was a literal path to `_unify`, so every pairing of a wildcard-free entry
with a glob one was blind over an empty tree (`a/b` x `a/**/c`, whose real shared path is `a/b/c`).
That is closed too: `pair_witnesses` offers the wildcard-free entry in BOTH readings.
What no witness half can reach is a pair whose shared region needs a path shape neither entry
states; the tree half answers those from the first file that lands there.

WHAT THIS REFUSES: nothing. It is a check a caller runs before it hands out work, and its answer is
an exit code. The refusals at dispatch time live in `kernel.dispatch` and read what this leaves
behind: a running lease over a shared file is refused there from the live computation (stream D's
C-2), and a SECOND build lease under one goal is refused there unless a RECORD of this check
measured the pair disjoint (DEC-0092 (2), `write_record` / `covering_record` below) -- named
rather than implied, because a reader of a check command may otherwise take it for a gate.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid

from .backlog_types import TSK_EFFORT_FIELD, TSK_RUNG_FIELD, field_elements, is_terminal
from .state import ProjectState, _now_iso

# WHAT A WILDCARD RUN BECOMES IN A WITNESS. One segment, because `**` matches any depth including a
# single segment and `*` matches inside one -- so a single placeholder satisfies both readings of
# an entry with no file behind it yet.
PLACEHOLDER = "_"
GATE = "gate_write_scope.py"
# The field a work order declares its SEAMS in (DEC-0062 (5), stream D requirement C-4). Spelled
# once, here, because three readers need it: the field contract, this check, and the printout.
SEAM_FIELD = "seam_scope"
# How many shared paths a pair prints before the list is cut. A cut list still decides the exit
# code; it is only the reading that is bounded.
PATHS_SHOWN = 10
# WHERE A RUN OF THIS CHECK LEAVES ITS RECORD (DEC-0092 (2)). Until generation 6 the check refused
# nothing and recorded nothing; the dispatcher now asks, before it grants a SECOND build lease
# under one goal, whether the two orders' file sets were MEASURED disjoint -- and this record is
# the measurement. One file per run, beside the leases, in the kernel-written part of the state
# (`kernel.layout.kernel_written_subtrees` lists it), so no role can write one by hand any more
# than it can write a lease. Which orders a record covers is decided by DIGEST
# (`order_digest`), not by id alone: an order re-scoped after the check is a different cut.
RECORDS_DIR = ("tasks", "scope-checks")
RECORD_SUFFIX = ".check.yaml"


class ScopeCheckError(RuntimeError):
    """The check could not run at all -- distinct from "the check ran and refused"."""


def _hooks_dir() -> str:
    """Where the shipped gate lives, relative to THIS kernel package.

    Anchored on the kernel rather than on the project tree, because the kernel is what is running:
    in a scaffolded project the two sit side by side under `.claude/`, and in the workshop
    checkout the kernel is `team-kits/kernel` while every kit carries its own `hooks/`. Both are
    found by asking where this file is, so no caller passes a path and no second layout rule
    exists.

    WHICH KIT'S COPY, in the workshop case, is not a choice: the file is mirrored byte-identical
    across the kits (`tools/test_hooks.py::test_shared_kit_files_identical`, and
    `KIT_SPECIFIC_HOOKS` does not name it), so the first one found answers for all three.
    """
    parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    installed = os.path.join(parent, "hooks")
    if os.path.isfile(os.path.join(installed, GATE)):
        return installed
    if os.path.isdir(parent):
        for entry in sorted(os.listdir(parent)):
            candidate = os.path.join(parent, entry, "hooks")
            if os.path.isfile(os.path.join(candidate, GATE)):
                return candidate
    raise ScopeCheckError(
        "no %s next to this kernel (%s), so the path predicate the specialists really meet cannot "
        "be asked. Remedy: run this from a scaffolded project or from the kit checkout; a second "
        "spelling of the predicate would answer a different question than the gate does."
        % (GATE, parent))


def _shipped_halves():
    """(`_matches`, `_norm`, the file both came from) -- imported, never restated.

    TWO HALVES, because the gate's answer is made of two: `_matches` decides prefix-vs-glob, and
    `_norm` is what both sides have been folded with before it ever sees them (`_scope_entries`
    folds every entry, `_repo_relative(fold=True)` folds the path). Taking only the first was a
    measured hole in this file: `Tools/**` and `tools/**` came back DISJOINT while the gate grants
    both orders the same files on a case-insensitive filesystem.
    """
    hooks = _hooks_dir()
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import gate_write_scope
    return gate_write_scope._matches, gate_write_scope._norm, os.path.join(hooks, GATE)


def matcher():
    """(the predicate as the GATE asks it, the file it came from).

    A wrapper and not the bare `_matches`, for the reason `_shipped_halves` gives: the gate never
    calls its predicate on unfolded text, so a caller that does is asking a question the gate does
    not answer. Both sides go through the shipped `_norm` first, in the shipped order.
    `tools/test_parallel_scopes.py::test_the_matcher_is_the_shipped_gates_own_and_not_a_second_spelling`
    reads the two halves off the module and then measures the folded pair.
    """
    matches, norm, gate = _shipped_halves()

    def folded(path, entry):
        return matches(norm(path), norm(entry))

    return folded, gate


def scope_entries(item: dict, field: str) -> list:
    """The entries of one scope field, folded the way the gate folds them.

    `field_elements` and not a list comprehension over the raw value: a scope written as a bare
    string is ONE entry to the kernel (BUG-0015), and this has to count it the same way.

    Blank, `.` and `*` are DROPPED rather than read as "everything": the gate refuses an order
    carrying one, so such an order is broken before this check has an opinion -- and reading it as
    the whole repository here would report an overlap the gate would never let happen.

    THE FOLD BELONGS HERE AND NOT ONLY IN `matcher`, because entries are compared to each other and
    not only to paths: `pair_seam` intersects two orders' `seam_scope` as plain strings, so an
    order declaring `Docs/**` and one declaring `docs/**` had NO seam in common. That failed
    closed -- the pair was reported as an overlap -- but the reader was told "you collide" instead
    of "your seam is spelled two ways", which is a different repair. Folding all three fields at
    the door makes one spelling of a path one entry everywhere in this module.
    `tools/test_parallel_scopes.py::test_a_seam_the_two_orders_spell_differently_is_still_one_seam`.
    """
    _matches, norm, _gate = _shipped_halves()
    entries = []
    for raw in field_elements(item.get(field)):
        entry = norm(str(raw))
        while entry.startswith("./"):
            entry = entry[2:]
        entry = entry.strip().rstrip("/")
        if entry in ("", ".", "*"):
            continue
        entries.append(entry)
    return entries


def in_scope(matches, order: dict, path: str) -> bool:
    """The one predicate: inside `allowed_scope`, outside `forbidden_scope`.

    The order of the two follows the gate: `forbidden_scope` is asked first there, so a path a work
    order forbids itself is not owned by it however wide its allowance is.
    """
    if any(matches(path, entry) for entry in order["forbidden"]):
        return False
    return any(matches(path, entry) for entry in order["allowed"])


def witnesses(entries) -> list:
    """One concrete path per scope entry -- what the entry would own if the tree were empty.

    ONE HALF OF THE WITNESS QUESTION and the older one: it fills each entry ALONE, so it answers
    "what would this entry own" and not "what could these two share". The second half is
    `pair_witnesses`, and BUG-0218 is the case that needs it -- `a/*x` yields `a/_x`, which no
    longer matches `a/y*` although `a/yx` satisfies both.
    """
    return [re.sub(r"\*+", PLACEHOLDER, entry) for entry in entries]


# HOW A SCOPE ENTRY IS READ WHEN A WITNESS IS BUILT FOR A PAIR. Three wildcards and a literal, and
# the difference that matters is whether the wildcard crosses a path separator: `**` does, `*` and
# `?` do not. Nothing here decides ownership -- `in_scope` does, with the GATE's own predicate --
# so a token read too generously costs a candidate that is thrown away, never a wrong verdict.
_ANY_SEGMENTS, _ANY_RUN, _ANY_CHAR = "**", "*", "?"


def _tokens(entry: str) -> list:
    """A scope entry as the tokens `_unify` walks: `**`, `*`, `?`, or one literal character."""
    found, index = [], 0
    while index < len(entry):
        if entry.startswith(_ANY_SEGMENTS, index):
            found.append(_ANY_SEGMENTS)
            index += 2
        elif entry[index] in (_ANY_RUN, _ANY_CHAR):
            found.append(entry[index])
            index += 1
        else:
            found.append(entry[index])
            index += 1
    return found


def _nullable(tokens, index: int) -> bool:
    """Can the rest of this pattern match the empty string -- i.e. is it wildcards all the way?"""
    return all(token in (_ANY_SEGMENTS, _ANY_RUN) for token in tokens[index:])


def _unify(left, right, i: int, j: int, seen: dict):
    """A concrete path both token lists accept, or None -- a joint walk, not a sample of each.

    THE PROPERTY, and it is why this is a search and not a substitution: a witness for a PAIR has
    to satisfy two patterns at once, so the character a wildcard stands for is chosen by the OTHER
    pattern wherever that one is literal. `a/*x` and `a/y*` have no common filling under
    `witnesses`, and `a/yx` under this one.

    Memoised on (i, j) -- the same pair of positions is reached by many wildcard splits, and
    without the table two long `**` entries walk exponentially.
    `tools/test_parallel_scopes.py::test_two_orders_that_share_only_a_region_no_single_witness_reaches_collide`
    """
    if (i, j) in seen:
        return seen[(i, j)]
    seen[(i, j)] = None                   # a cycle through two wildcards contributes nothing
    found = None
    if i >= len(left) and j >= len(right):
        found = ""
    elif i >= len(left):
        found = "" if _nullable(right, j) else None
    elif j >= len(right):
        found = "" if _nullable(left, i) else None
    else:
        head_left, head_right = left[i], right[j]
        wild = (_ANY_SEGMENTS, _ANY_RUN)
        # A wildcard may stand for nothing at all -- try that first, it is the shortest witness.
        for skip_i, skip_j in ((i + 1, j) if head_left in wild else (None, None), \
                               (i, j + 1) if head_right in wild else (None, None)):
            if found is None and skip_i is not None:
                found = _unify(left, right, skip_i, skip_j, seen)
        if found is None:
            # ...otherwise it stands for ONE character, and which character is the other side's say
            letter = _one_character(head_left, head_right)
            if letter is not None:
                rest = _unify(left, right,
                              i if head_left in wild else i + 1,
                              j if head_right in wild else j + 1, seen)
                if rest is not None:
                    found = letter + rest
    seen[(i, j)] = found
    return found


def _one_character(head_left, head_right):
    """The character these two tokens can BOTH consume here, or None when they cannot.

    `**` is the only token that may consume a separator; `*`, `?` and a literal `/` may not meet it
    on the other side, which is what keeps a witness inside the segment its pattern describes.
    """
    wildcards = (_ANY_SEGMENTS, _ANY_RUN, _ANY_CHAR)
    literals = {token for token in (head_left, head_right) if token not in wildcards}
    if len(literals) > 1:
        return None                        # two different literals cannot be one character
    letter = literals.pop() if literals else PLACEHOLDER
    if letter == "/" and any(token in (_ANY_RUN, _ANY_CHAR)
                             for token in (head_left, head_right)):
        return None                        # only `**` crosses a separator
    return letter


def pair_witnesses(first: dict, second: dict) -> list:
    """One candidate path per pair of allowed entries -- what the two orders COULD share.

    CANDIDATES AND NOT A VERDICT. Everything this returns is handed to `in_scope` with the gate's
    own predicate, exactly like the file list and the single-entry witnesses, so a candidate this
    builder gets wrong is a path that fails the predicate and disappears -- it can widen what the
    check SEES, never what it claims. That is what makes closing BUG-0218 safe on a reader
    `dispatch` refuses leases with.
    """
    found = []
    for left in _readings(first["allowed"]):
        for right in _readings(second["allowed"]):
            path = _unify(_tokens(left), _tokens(right), 0, 0, {})
            if path:
                found.append(path)
    return found


def _readings(entries) -> list:
    """Every way the GATE reads these entries -- a wildcard-free one is also a directory prefix.

    THE SECOND READING IS NOT A SECOND SPELLING, it is what the gate already does: an entry with no
    wildcard matches the path itself AND everything under it, while `_unify` treats it as a literal
    and can then unify it with nothing that goes deeper. Measured by brute force over every path up
    to five segments against the shipped predicate: 6 pairs shared a real path and produced no
    witness at all, every one of them a wildcard-free entry against a glob (`a/b` x `a/**/c`).
    Offering both readings costs a candidate `in_scope` throws away when the gate disagrees, which
    is the same trade the rest of this builder makes.
    `tools/test_parallel_scopes.py::test_a_wildcard_free_entry_is_offered_as_the_directory_prefix_the_gate_reads`
    """
    found = []
    for entry in entries:
        found.append(entry)
        if not set("*?") & set(entry):
            found.append("%s/**" % entry.rstrip("/"))
    return found


def tracked_files(tree: str) -> list:
    """Every file git carries or would carry -- the real universe the scopes resolve against.

    `-c -o --exclude-standard`: cached AND untracked-but-not-ignored, because a file a stream has
    already created is as much a collision as a committed one, while an ignored build product is
    nobody's ownership. A tree git cannot answer for yields NO files rather than an exception --
    the witness half still decides, and a project without git is not a project without a cut.
    """
    try:
        result = subprocess.run(["git", "ls-files", "-c", "-o", "--exclude-standard"],
                                cwd=tree, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def open_orders(state: ProjectState, only=None) -> list:
    """Every work order that is not in a terminal status, read through the kernel's own contract.

    "Open" is `backlog_types.is_terminal` and not a list of status words: a cut is judged BEFORE
    the dispatch, so a DRAFT order counts exactly as much as a LEASED one -- both are work somebody
    is about to hand out. `--only` overrides the status filter, because a caller naming two ids is
    asking about those two whatever they are.
    """
    orders = []
    for stem, path in state.iter_active_items("TSK"):
        try:
            item = state._read_yaml(path)
        except Exception:  # noqa: BLE001 -- an unreadable order is the validator's finding
            continue
        if not isinstance(item, dict) or not item.get("id"):
            continue
        if only:
            if item["id"] not in only:
                continue
        elif is_terminal("TSK", str(item.get("status") or "")):
            continue
        orders.append({
            "id": str(item["id"]),
            "root": str(item.get("product_requirement") or ""),
            "allowed": scope_entries(item, "allowed_scope"),
            "forbidden": scope_entries(item, "forbidden_scope"),
            "seam": scope_entries(item, SEAM_FIELD),
            # The PM's tier ask per order (DEC-0091 (3): "beside the order in check-scopes, so two
            # parallel orders show their two rungs side by side"). Read, never derived: the lease
            # derives, this prints what was asked.
            "asks": {TSK_RUNG_FIELD: item.get(TSK_RUNG_FIELD), TSK_EFFORT_FIELD: item.get(TSK_EFFORT_FIELD)},
        })
    return sorted(orders, key=lambda order: order["id"])


def asks_line(order: dict) -> str:
    """One order's tier ask as the check prints it beside the order."""
    asks = order.get("asks") or {}
    named = ["%s %s" % (field, asks[field]) for field in (TSK_RUNG_FIELD, TSK_EFFORT_FIELD)
             if asks.get(field)]
    return ("asks %s (DEC-0091; the lease derives the final pair)" % ", ".join(named)
            if named else "no tier ask (the ladder's own answer applies)")


def order_digest(order: dict) -> str:
    """What a record has to agree with for the order it names: the three scope fields, folded.

    A DIGEST AND NOT THE ID, because the id survives a re-scope and the measurement does not: the
    plan fields are frozen once an order leaves DRAFT, so past that point the digest is the id's
    twin, and while the order is still being planned a changed scope stops every earlier record
    from covering it. Nothing else of the order is in it -- a title or an ask changing does not
    move a file set.
    """
    body = {"allowed": sorted(order["allowed"]), "forbidden": sorted(order["forbidden"]),
            "seam": sorted(order["seam"])}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def _records_dir(state: ProjectState) -> str:
    return os.path.join(state.root, *RECORDS_DIR)


def _record_path(state: ProjectState, name: str) -> str:
    return os.path.join(_records_dir(state), name + RECORD_SUFFIX)


def write_record(state: ProjectState, orders: list, colliding: set, files: int, gate: str) -> str:
    """The record of ONE run: every compared order with its digest, and every pair's verdict.

    Every pair is written out as measured -- `disjoint` and `overlapping` are both lists of pairs
    -- so a reader asking about two ids finds an answer or finds the pair absent, and absent is
    "not compared in this run", never "disjoint" (the same three-way honesty `check` prints).
    """
    ids = [order["id"] for order in orders]
    pairs = [(first, second) for index, first in enumerate(ids) for second in ids[index + 1:]]
    record = {
        "checked_at": _now_iso(),
        "matcher": gate,
        "files_in_tree": int(files),
        "orders": {order["id"]: {"root": order["root"], "digest": order_digest(order),
                                 "allowed": list(order["allowed"]),
                                 "forbidden": list(order["forbidden"]),
                                 "seam": list(order["seam"])}
                   for order in orders},
        "disjoint": [list(pair) for pair in pairs if frozenset(pair) not in colliding],
        "overlapping": [list(pair) for pair in pairs if frozenset(pair) in colliding],
    }
    # THE NAME ORDERS THE RECORDS (`records` sorts by it, `covering_record` asks the newest naming
    # a pair), so it carries microseconds: two runs inside one second are the ordinary case in a
    # test and a real one after a re-scope, and with a seconds stamp their order was the nonce's.
    stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H%M%S.%f")
    path = _record_path(state, "%s-%s" % (stamp, uuid.uuid4().hex[:8]))
    state._write_yaml_atomic(path, record)
    _drop_records_about_closed_orders(state, {order["id"] for order in open_orders(state)})
    return path


def _drop_records_about_closed_orders(state: ProjectState, open_ids: set) -> list:
    """Remove every record none of whose orders is still open; returns what went.

    THE BOUND ON THE DIRECTORY, by a property and not by a count: a record covers a pair only
    while both orders are open (`covering_record` asks `open_orders`), so a record about orders
    that have all ended can never answer again and only makes every later `records()` read longer.
    Pruned at every run of the check, so the directory holds at most the runs made while the
    orders they name were live. WHAT THIS DOES NOT BOUND, said rather than implied: a project that
    runs the check many times over the same long-lived orders keeps every one of those runs until
    the orders close -- named in TSK-0135's protocol as the residual, with the reading cost.
    `tools/test_light_kit.py::test_a_check_scopes_record_about_closed_orders_is_dropped_at_the_next_run`
    """
    gone = []
    for record in records(state):
        if not any(order_id in open_ids for order_id in record.get("orders") or {}):
            try:
                os.remove(record["path"])
                gone.append(record["path"])
            except OSError:
                continue
    return gone


def records(state: ProjectState) -> list:
    """Every readable record, NEWEST FIRST -- the order a reader wants, because the newest run
    over a pair is the one that measured the orders as they stand."""
    directory = _records_dir(state)
    if not os.path.isdir(directory):
        return []
    found = []
    for name in sorted(os.listdir(directory), reverse=True):
        if not name.endswith(RECORD_SUFFIX):
            continue
        try:
            record = state._read_yaml(os.path.join(directory, name))
        except Exception:  # noqa: BLE001 -- an unreadable record covers nothing
            continue
        if isinstance(record, dict) and isinstance(record.get("orders"), dict):
            record["path"] = os.path.join(directory, name)
            found.append(record)
    return found


def covering_record(state: ProjectState, first: str, second: str):
    """The NEWEST record that names the pair at all -- and it, if it measured `first` and `second`
    disjoint AS THEY STAND NOW; otherwise None.

    THE NEWEST MEASUREMENT OF THE PAIR IS THE ONE THAT COUNTS, whatever it found: a later run that
    measured the same two orders overlapping (a file created in the tree since) REVOKES the older
    disjoint verdict, so only the newest record naming the pair is asked, never the newest one that
    happens to say disjoint. Measured the other way at the mid-goal check (B3): the older
    verdict admitted the second builder while a newer record said OVERLAP, held back only by the
    live file check in `dispatch._assert_no_running_lease_owns_the_same_file_locked` -- which
    still stands behind this one for the file class it catches.
    "As they stand now" is the digest comparison: the record's digest of each order has to equal
    the digest of the order the store holds today. A pair no record names covers nothing.
    `tools/test_light_kit.py::test_a_record_stops_covering_an_order_whose_scope_moved_since`
    `tools/test_light_kit.py::test_a_newer_overlap_record_revokes_an_older_disjoint_verdict`
    """
    current = {order["id"]: order_digest(order)
               for order in open_orders(state, {first, second})}
    if len(current) != 2:
        return None
    wanted = frozenset((first, second))
    for record in records(state):
        named = [key for key in ("disjoint", "overlapping")
                 if any(frozenset(pair) == wanted for pair in record.get(key) or ())]
        if not named:
            continue
        stored = record["orders"]
        if named == ["disjoint"] and all(
                isinstance(stored.get(one), dict) and stored[one].get("digest") == current[one]
                for one in wanted):
            return record
        return None
    return None


def goal_partition(state: ProjectState, root_id: str, declared=()) -> list:
    """The measured-disjoint SETS a goal's open orders fall into -- DEC-0092 (3)(a)'s line.

    Two orders that share a path (outside their declared seam) are one set; the sets are the
    connected components of that relation, so "this goal splits into N sets" is a statement about
    file ownership and not about how many orders the PM happened to cut. One order is one set;
    no order is no set.
    """
    orders = [order for order in open_orders(state) if order["root"] == str(root_id)]
    if len(orders) < 2:
        return [[order["id"] for order in orders]] if orders else []
    matches, _gate = matcher()
    files = tracked_files(os.path.dirname(os.path.abspath(state.root)))
    parent = {order["id"]: order["id"] for order in orders}

    def find(one):
        while parent[one] != one:
            parent[one] = parent[parent[one]]
            one = parent[one]
        return one

    for pair in overlaps(matches, orders, files, declared):
        if pair["files"] or pair["witnesses"]:
            parent[find(pair["a"])] = find(pair["b"])
    groups = {}
    for order in orders:
        groups.setdefault(find(order["id"]), []).append(order["id"])
    return sorted(sorted(group) for group in groups.values())


def pair_seam(first: dict, second: dict, declared=()) -> list:
    """The entries that count as SHARED ON PURPOSE for this pair.

    BOTH ORDERS HAVE TO SAY SO, and that is the fail-closed reading rather than a strictness for
    its own sake: a seam is a file no stream can own alone (DEC-0062 (5)). If only one order
    declares `docs/**` and the other simply owns it, the second one was cut believing the file was
    its own -- which is exactly the surprise the seam table exists to prevent. So a one-sided
    declaration leaves the pair overlapping, and the printout shows why.
    `tools/test_parallel_scopes.py::test_a_seam_only_one_of_the_two_declares_is_not_a_seam`.

    A CALLER MAY ALSO DECLARE ONE, and that is a different statement rather than a second route to
    the same one: the items carry the cut a project has already written down, while the argument is
    the orchestrator asking "what if these three were the seam" before any item says so. It applies
    to every pair, which is what makes it an answer about the CUT and not about one order.
    """
    return sorted(set(first["seam"]) & set(second["seam"]) | set(declared))


def owns_anything_outside(matches, order: dict, files, seam) -> bool:
    """Does this order still own a path once the seam is taken away?

    THE LIMIT OF A DECLARATION, and it is a property rather than a shape. A seam is what two
    streams share ON PURPOSE and apply in the merge; it is not a way of declaring the collision
    away. `seam_scope: ["**"]` -- or `--seam **` -- matches every path either order owns, so every
    collision becomes "seam only" and the check reports rc 0 on a cut that is entirely shared.
    What separates the two cases is not how the entry is spelled (`**`, `team-kits/**`, a list of
    every entry the order has) but whether the order is left owning ANYTHING of its own. That also
    keeps the legitimate seam legitimate: an order owning `team-kits/kernel/**` and declaring
    `team-kits/*/VERSION` still owns the kernel afterwards.
    `tools/test_parallel_scopes.py::test_a_seam_that_leaves_an_order_owning_nothing_is_refused`
    holds both ends.

    WHAT THIS QUESTION DOES NOT REACH: a seam NARROWER than the overlap. It leaves both orders
    owning something, so it passes here while still covering part of a real collision -- `H143` in
    `docs/POST_V2_WISHLIST.md`, with the measurement. The routes that end without comparing
    anything at all -- one open order, or a `--only` that names exactly one -- are `H142`.
    """
    for path in list(files) + witnesses(order["allowed"]):
        if in_scope(matches, order, path) and not any(matches(path, entry) for entry in seam):
            return True
    return False


def _spelled_apart(matches, first: dict, second: dict, shared) -> list:
    """The paths BOTH orders declare as a seam in different WORDS -- BUG-0231's second residue.

    `pair_seam` intersects the two declarations as STRINGS while the gate compares FILE SETS, so
    `docs/` and `docs/**` are one set to the predicate and two entries to the intersection: the
    pair is then refused with the ordinary OVERLAP message, which is fail-closed and a worse
    answer -- the caller reads "these two collide" where the truth is "you spelled one seam twice".
    This is the answer, not a change of verdict: the paths are named, and the remedy is to write
    the entry the same way on both orders.
    `tools/test_parallel_scopes.py::test_two_spellings_of_one_seam_are_named_as_such_and_not_as_a_collision`
    """
    return sorted(path for path in shared
                  if any(matches(path, entry) for entry in first["seam"])
                  and any(matches(path, entry) for entry in second["seam"]))


def overlaps(matches, orders, files, declared=()) -> list:
    """[{a, b, files, witnesses, seam, swallowed}] for every pair that shares a path.

    A SEAM IS SUBTRACTED, NOT IGNORED: both halves are reported, and only the undeclared half
    decides the verdict. A pair that shares nothing at all does not appear here.

    A SEAM THAT SWALLOWS AN ORDER IS NOT SUBTRACTED AT ALL (`owns_anything_outside`): the pair is
    then reported with everything it shares, because a declaration that leaves one side owning
    nothing is not a seam -- it is the whole scope handed over, and the check would otherwise say
    `disjoint` about a cut that is entirely shared. The seam this cannot reach -- one NARROWER than
    the overlap -- is `H143` in `docs/POST_V2_WISHLIST.md`.
    """
    real = set(files)
    found = []
    for index, first in enumerate(orders):
        for second in orders[index + 1:]:
            seam = pair_seam(first, second, declared)
            swallowed = [order["id"] for order in (first, second)
                         if seam and not owns_anything_outside(matches, order, files, seam)]
            effective = () if swallowed else seam
            universe = (list(files) + witnesses(first["allowed"] + second["allowed"])
                        + pair_witnesses(first, second))
            shared_files, shared_witnesses, shared_seam = set(), set(), set()
            for path in universe:
                if not (in_scope(matches, first, path) and in_scope(matches, second, path)):
                    continue
                if any(matches(path, entry) for entry in effective):
                    shared_seam.add(path)
                elif path in real:
                    shared_files.add(path)
                else:
                    shared_witnesses.add(path)
            if shared_files or shared_witnesses or shared_seam:
                found.append({"a": first["id"], "b": second["id"],
                              "files": sorted(shared_files), "witnesses": sorted(shared_witnesses),
                              "seam": sorted(shared_seam), "swallowed": swallowed,
                              "spelled_apart": _spelled_apart(
                                  matches, first, second,
                                  sorted(shared_files | shared_witnesses))})
    return found


def check(state: ProjectState, only=None, declared=()) -> tuple:
    """Run the check: `(exit code, [lines])`.

    THREE OUTCOMES AND THEY NEVER SHARE A WORD. Nothing to compare is not "disjoint" -- a missing
    state directory, a task tray with one open order and a mistyped `--root` all land there, so the
    line says that nothing was measured rather than that everything was fine
    (`tools/test_parallel_scopes.py::test_a_state_with_nothing_to_compare_never_says_disjoint`).

    AND WHAT THE CALLER SPELLED OUT HAS TO BE ANSWERABLE, not merely resolvable (BUG-0225). An
    `--only` that names ids is a request for a COMPARISON; when it resolves to fewer than two open
    orders there is no comparison to be had, and answering 0 tells a script the cut was checked.
    That is rc 1 -- a usage answer, told apart from the refused cut's rc 2. A run nobody narrowed
    keeps its 0: the tool run with no arguments outside a project is how
    `tools/test_hooks_v2.py::test_a_repo_tool_that_imports_the_kit_tree_leaves_no_bytecode_in_it`
    drives it, and that run asked for nothing.
    """
    matches, gate = matcher()
    orders = open_orders(state, set(only or ()) or None)
    if len(orders) < 2:
        line = ("%d open work order(s) under %s -- NOTHING WAS COMPARED."
                % (len(orders), state.root))
        if only:
            return 1, [line + " You named %s, and a comparison needs two open orders; drop "
                              "--only, or name the order this one should be compared against."
                       % ", ".join(sorted(str(one) for one in only))]
        return 0, [line]
    tree = os.path.dirname(os.path.abspath(state.root))
    files = tracked_files(tree)
    lines = ["matcher: %s | %d open orders | %d files in the tree"
             % (gate, len(orders), len(files))]
    for order in orders:
        lines.append("order %s under %s: %s" % (order["id"], order["root"] or "?", asks_line(order)))
    undeclared = 0
    colliding = set()
    for pair in overlaps(matches, orders, files, declared):
        collides = bool(pair["files"] or pair["witnesses"])
        undeclared += 1 if collides else 0
        if collides:
            colliding.add(frozenset((pair["a"], pair["b"])))
        lines.append("%s %s x %s" % ("OVERLAP" if collides else "seam only", pair["a"], pair["b"]))
        for path in pair["files"][:PATHS_SHOWN]:
            lines.append("    file      %s" % path)
        for path in pair["witnesses"][:PATHS_SHOWN]:
            lines.append("    witness   %s  (no such file today -- both scopes would own it)"
                         % path)
        for path in pair["seam"][:PATHS_SHOWN]:
            lines.append("    seam      %s  (declared by BOTH orders -- applied in the merge round)"
                         % path)
        for path in pair.get("spelled_apart", [])[:PATHS_SHOWN]:
            lines.append("    spelled apart  %s  (BOTH orders declare it as a seam, in different "
                         "words -- write the entry identically on both and it stops colliding)"
                         % path)
        for order_id in pair["swallowed"]:
            lines.append("    NOT A SEAM: the declaration leaves %s owning nothing of its own, so "
                         "it hands the whole scope over rather than sharing a file" % order_id)
    # THE RECORD, written for every run that compared something -- a refused cut is a measurement
    # too, and the dispatcher reads the pairs, not the exit code (DEC-0092 (2)).
    record = write_record(state, orders, colliding, len(files), gate)
    lines.append("recorded: %s (the dispatcher reads this before it grants a second builder under "
                 "one goal, DEC-0092 (2))" % os.path.relpath(record, state.root).replace(os.sep, "/"))
    if not undeclared:
        lines.append("disjoint: no pair of open orders owns a common path outside the declared "
                     "seam.")
        return 0, lines
    lines.append(
        "refused: %d overlapping pair(s). Group them into ONE order with one owner, move the "
        "shared files out of one of the two scopes, or declare them in `%s` on BOTH orders "
        "(DEC-0062 (1)/(2)/(5))." % (undeclared, SEAM_FIELD))
    return 2, lines

