#!/usr/bin/env python3
"""
Gate 2 (SR-0009 clause 2): a spawn in the change circle needs an item.

WHY. DEC-0003 records what this replaces: the order to the implementer used to be written freely in
a chat message, so an outdated item produced no visible error and a summarised session lost the
order entirely. An item named in the spawn makes the order an INPUT -- a stale one produces a wrong
order and the mistake is visible.

WHICH SPAWNS. NOT ALL OF THEM, and this is the definition the gate turns on rather than a list of
role names. Two agents in this repo hold no item (`radar-watcher`,
`codex-watcher` write only into `radar/`), and hard-coding those two would be wrong the day a third
watcher ships or one is renamed. So the SPAWNED AGENT'S OWN DEFINITION answers, through the
frontmatter key `harness_item:` -- `none` for a role that holds none, and required for everything
else including a definition that says nothing. `_harness.spawn_needs_an_item` carries the default
direction, the failure directions and what the self-declaration costs.

WHAT COUNTS AS NAMING AN ITEM: an id that RESOLVES under `project_memory/` (active or archive) and
is NOT terminal. A finished item is no order for work now.

DELIBERATELY WEAKER THAN GATE 4 IN ONE RESPECT: gate 4 additionally demands that the type can carry
work, because SR-0009 asks that of a task list entry (clause 4) and not of a spawn (clause 2, which
requires an open item and nothing further about its type). A spawn that says "read
DEC-0003 and report" names a decision, which is a legitimate thing to send an agent to do, so this
gate does not refuse it.
"""
import os
import sys

# THE IMPORT IS INSIDE THE PROTECTION -- see the same block in `gate_lead_write_scope.py` and the
# measurement in `_harness.py`'s header: a module-level import failure exits 1, and the provider
# reads that as an allow.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import _harness
except BaseException as error:  # noqa: BLE001 -- a gate that cannot load must not mean "allow"
    sys.stderr.write(
        "[harness gate] refused: the shared body of this repo's gates (.claude/hooks/_harness.py) "
        "could not be loaded (%r), so this call could not be judged. A gate that cannot decide "
        "refuses.\nRemedy: repair the file from a shell OUTSIDE Claude Code and start a new "
        "session -- it cannot be repaired from inside this one.\n" % (error,))
    sys.exit(2)


def decide():
    data = _harness.payload()
    root = _harness.repo_root(data)
    agent = _harness.spawned_agent(data)
    if not _harness.spawn_needs_an_item(root, agent):
        return
    text = _harness.spawn_text(data)
    references = _harness.resolve_references(root, text)
    known = _harness.automata(root)
    usable = [ref for ref in references if ref.found and not ref.terminal(known)]
    if usable:
        return
    if references:
        detail = "; ".join(
            "%s: %s" % (ref.text, "does not resolve under %s/" % _harness.STATE_ROOT
                        if not ref.found
                        else "is finished (%s%s)" % (ref.status,
                                                     ", archived" if ref.archived else ""))
            for ref in references)
        reason = "the ids it names lead no open work -- " + detail
    else:
        reason = "it names no item id at all"
    _harness.refuse(
        "this spawn of `%s` was refused: %s.\n"
        "A spawn in this repo's change circle carries the item it works from, so the order is "
        "generated FROM the item instead of written freely (DEC-0003). Put the id in the prompt "
        "-- the implementer and the verifier must receive the SAME id.\n"
        "Remedy: name an open item, e.g. `Dein Auftrag ist TSK-nnnn in "
        "%s/tasks/active/TSK-nnnn.yaml`. If this role legitimately runs without an item (a "
        "watcher), its definition in .claude/agents/%s.md declares `%s: %s` in its "
        "frontmatter -- and .claude/ is refused to the session agent by gate 1, so writing that "
        "declaration is a change the change circle makes, not one this session makes for itself."
        % (agent or "<unnamed>", reason, _harness.STATE_ROOT, agent or "<name>",
           _harness.ITEM_KEY, _harness.ITEM_NONE))


if __name__ == "__main__":
    _harness.guarded(decide)
