#!/usr/bin/env python3
"""Every model a spawnable role pins must be one `team-kits/model_tiers.yaml` can PLACE.

WHY THIS COSTS A RUN AND NOT A WARNING: an unplaceable pin does not quietly fall back to the
parent's model. Measured against real spawns on a rig outside the repo -- protocol and the verbatim
platform answer in `docs/reviews/2026-09-02-model-pin-and-bom-measurement.md`, findings 1 and 2 --
the spawn dies at once and the parent gets an API error naming the model it sent. That was measured
for a typo AND for the tier alias `worker` that every kit SOURCE carries: the alias is legitimate in
the source and becomes a concrete name at install time, so the two ends need different readers.

WHAT WAS ALREADY COVERED, and is therefore not repeated here: `tools/validate.py` step 8 asks
`gen_provider_artifacts.provider_neutral_model` whether a KIT SOURCE may carry a value, and
`test_both_scaffold_launchers_leave_no_tier_alias_in_installed_frontmatter` (in `tools/test_hooks.py`)
measures that the install resolves the alias. Neither of them ever looked at `.claude/agents/`, this
repo's OWN spawnable roles, which is the gap this module closes -- with one reader for every role
definition the repo tracks, so a new role directory is covered the day it appears.
"""
import io
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.join(ROOT, "tools"))
from conftest import load_kit_module  # noqa: E402 -- the suite's one loader for shipped scripts

# The module that READS `model_tiers.yaml`, borrowed rather than re-implemented: what the table can
# place is a property of the table, and `tools/validate.py` asks the same file the same way.
tiers_reader = load_kit_module(
    "gen_provider_artifacts_for_model_pins",
    os.path.join(ROOT, "team-kits", "gen_provider_artifacts.py"))

REFERENCE = tiers_reader.REFERENCE_PROVIDER

_FRONTMATTER_RX = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_MODEL_RX = re.compile(r"""(?m)^model:[ \t]*["']?([^"'\s#]+)["']?[ \t]*$""")


def _tracked_paths():
    """Repo-relative paths git TRACKS -- the files that actually ship, not what a walk finds."""
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=60)
    assert result.returncode == 0, result.stderr
    return [path for path in result.stdout.split("\0") if path]


def under_an_agents_directory(relative):
    """Is this a `*.md` somewhere below a directory named `agents`?

    A LOCATION. The client's own rule is a different question, and deliberately not this one: of
    five opening shapes placed under `agents/`, the client loaded the one whose first line is the
    frontmatter delimiter and dropped the other four without a word. That measurement, and why the
    rule must not become the subject, is section 5a of
    `docs/reviews/2026-09-02-model-pin-and-bom-measurement.md`.

    So this predicate is wider than what THAT client reads. That `docs/agents/notes.md` falls
    into it is FRICTION, and what is measured about it is a red run of these checks -- not a client
    pointed at that tree. What the client DOES load is section 5a of the document above.

    THE DEPTH IS THE POINT and it has no holder in the shipped tree, which is why
    `test_the_role_predicate_reaches_any_depth_and_stops_at_the_directory_name` states it on literal
    paths: this repo ships no role in a subdirectory, so narrowing this function back to the parent
    directory leaves every other test in both modules green. Until 2026-09-02 it WAS narrow, and a
    role one level down carried an unchecked pin at both ends, because the coverage check asked the
    same narrow question.

    `tools/test_repo_hygiene.py` imports this function rather than restating it. Two definitions of
    THIS NAME in one module are caught by `ruff` (F811); a second function under a different name
    is caught by nothing, so the sharing is a convention with one mechanical half.
    """
    return relative.endswith(".md") and "agents" in os.path.dirname(relative).split("/")


def role_definitions(root, relative_paths):
    """The role definitions among `relative_paths` that are really on disk."""
    return [path for path in relative_paths
            if under_an_agents_directory(path)
            and os.path.isfile(os.path.join(root, path.replace("/", os.sep)))]


def pinned_model(root, relative_path):
    """The `model:` a role definition pins, or None when it pins none (the session lead pins none:
    a lead bound through `settings.json` takes the model of the session it leads)."""
    with io.open(os.path.join(root, relative_path.replace("/", os.sep)),
                 encoding="utf-8-sig") as handle:
        text = handle.read()
    block = _FRONTMATTER_RX.match(text)
    if not block:
        return None
    found = _MODEL_RX.search(block.group(1))
    return found.group(1) if found else None


def _model_values(provider_table, aliases):
    """The MODEL entries of one provider's block: its rung rows.

    The block also carries `effort_field`, which is a frontmatter key and not a model -- reading it
    as one made the tripwire below refuse `effort` on its first run. Which rows are rungs is the
    generator's own reading (`gen_provider_artifacts.rungs`), asked rather than re-spelled: since
    DEC-0076 the rows are keyed by rung name and the top rung has no alias, so "key in aliases"
    would have read two of three rows.
    """
    del aliases  # the rows are told apart by the generator's own reader, not by the alias names
    return list(tiers_reader.rungs({"block": provider_table}, "block").values())


def the_table_can_place(value):
    """Can `model_tiers.yaml` turn this value into a concrete model for every provider it knows?

    ONE clause, and it is the table's own translation rather than a vocabulary spelled out here:
    a value the table understands comes back CHANGED for every non-reference provider, because the
    lookup went through a tier. A tier alias, a reference-platform tier value and the above-lead pin
    all pass that way; a typo and a foreign provider's own model id come back untouched and fail.
    """
    tiers, aliases = tiers_reader.load_tiers()
    others = [name for name in tiers if name != tiers_reader.REFERENCE_PROVIDER]
    return bool(others) and all(
        tiers_reader.provider_model(value, provider, tiers, aliases) != value
        for provider in others)


def unplaceable_pins(root, relative_paths):
    """(path, value) for every role definition whose pin the table cannot place."""
    found = []
    for path in role_definitions(root, relative_paths):
        value = pinned_model(root, path)
        if value is not None and not the_table_can_place(value):
            found.append((path, value))
    return found


def test_every_model_a_shipped_role_pins_resolves_in_the_tiers_table():
    """The pins this repo ships, against the table that has to place them.

    Goes red the moment any role definition -- this repo's own or a kit's -- carries a value
    `model_tiers.yaml` cannot translate, which is the state whose consequence at spawn time is
    measured in `docs/reviews/2026-09-02-model-pin-and-bom-measurement.md`.
    """
    offenders = unplaceable_pins(ROOT, _tracked_paths())
    assert not offenders, (
        "these role definitions pin a model team-kits/model_tiers.yaml cannot place, so the spawn "
        "dies with model_not_found instead of falling back: %s"
        % ", ".join("%s -> %r" % pair for pair in offenders))


def test_the_pin_reader_covers_every_agents_directory_the_repo_tracks():
    """The other end of the subject: a reader that looked at ONE location would pass silently.

    That is not hypothetical -- it is the state this module was written into: the kit sources had
    two readers and `.claude/agents/` had none. Derived from the tracked tree, so a fourth kit or a
    new role home joins the subject without anybody editing a list.

    THE PINS ARE COUNTED, not just the files, because a reader that finds every role definition and
    no `model:` line in any of them leaves the check above asserting nothing. The candidate that
    looked most likely -- a CRLF checkout against a pattern anchored at `$` -- was measured NOT to
    be one: `pinned_model` reads in text mode, so a `\r` never reaches the pattern (rig case B in
    `docs/reviews/2026-09-02-model-pin-and-bom-measurement.md`, finding 9). The count stands for the
    ones nobody has thought of.
    """
    tracked = _tracked_paths()
    seen = role_definitions(ROOT, tracked)
    homes = {os.path.dirname(path) for path in tracked if under_an_agents_directory(path)}
    assert homes, "no agents/ directory found at all -- the tracked-file reader stopped working"
    covered = {os.path.dirname(path) for path in seen}
    assert covered == homes, "role directories the reader skipped: %s" % sorted(homes - covered)
    assert any(home.startswith(".claude/") for home in homes), (
        "this repo's own roles are no longer part of the subject")
    pinned = [path for path in seen if pinned_model(ROOT, path) is not None]
    assert len(pinned) > len(seen) // 2, (
        "%d of %d role definitions came back without a model pin -- the frontmatter reader, not "
        "the tree, is what changed" % (len(seen) - len(pinned), len(seen)))


def test_the_reader_refuses_what_the_table_cannot_place_and_demands_no_tier_be_pinned():
    """Both directions of the check, run rather than described.

    Direction one: a value the table cannot place is refused -- with a typo and with a foreign
    provider's own model id, which is the shape a copied line takes. Direction two: everything the
    table DECLARES is accepted, and a tree that pins a single tier passes -- a tier nobody pins is
    not an error, and the reader must not quietly require one pin per tier.

    AND THE ROW READER ITSELF, because it decides how much direction two covers: `_model_values`
    claims to return every RUNG row, and the reading it replaced ("key in aliases") returned only
    the rows an alias names. That mutation weakens this test instead of failing it -- the loop
    below simply asks about fewer values -- so the count is asserted against the alias count here.
    """
    tiers, aliases = tiers_reader.load_tiers()
    reference_rows = _model_values(tiers[REFERENCE], aliases)
    assert len(reference_rows) > len(aliases), (
        "the row reader returned %d rows for %d aliases: the top rung has no alias, so a reader "
        "that tells rows apart by the alias names skips it and everything below asks less"
        % (len(reference_rows), len(aliases)))
    assert not the_table_can_place("opus-4-1-does-not-exist")
    foreign = [value for provider, table in tiers.items() if provider != REFERENCE
               for value in _model_values(table, aliases)]
    assert foreign, "model_tiers.yaml knows no second provider -- the refusal below proves nothing"
    assert not the_table_can_place(foreign[0])
    for value in list(aliases) + _model_values(tiers[REFERENCE], aliases):
        assert the_table_can_place(value), (
            "%r is in model_tiers.yaml and the reader refuses it" % value)


def test_the_role_predicate_reaches_any_depth_and_stops_at_the_directory_name():
    """The two edges of `under_an_agents_directory`, stated on literal paths.

    NEITHER EDGE HAS A HOLDER IN THE SHIPPED TREE, which is the whole reason this test exists:
    the repo ships no role in a subdirectory and no `agents-old/`, so narrowing the predicate back
    to the file's parent directory leaves every other test in both modules green -- measured by
    doing exactly that. Without the five assertions below, the depth claim in
    `under_an_agents_directory` is carried by nothing.
    """
    assert under_an_agents_directory("a/agents/c.md"), "the level the loader always had"
    assert under_an_agents_directory("a/agents/b/c.md"), "one level down, and the client loads it"
    assert not under_an_agents_directory("a/agents-old/c.md"), "a longer name is a different name"
    assert not under_an_agents_directory("agents.md"), "a file called agents is not a directory"
    assert not under_an_agents_directory("a/agents/c.txt"), "a role definition is markdown"


def test_a_tier_nobody_pins_is_not_an_error(tmp_path):
    """The surjectivity half, measured on a tree that pins exactly one of the table's tiers."""
    tiers, aliases = tiers_reader.load_tiers()
    only = sorted(aliases)[0]
    role = tmp_path / "any" / "agents" / "solo.md"
    role.parent.mkdir(parents=True)
    role.write_text("---\nname: solo\nmodel: %s\n---\nbody\n" % only, encoding="utf-8")
    relative = ["any/agents/solo.md"]
    assert role_definitions(str(tmp_path), relative) == relative
    assert not unplaceable_pins(str(tmp_path), relative)
    assert len(aliases) > 1, "with one alias this tree would pin them all and assert nothing"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
