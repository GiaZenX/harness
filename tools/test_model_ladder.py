#!/usr/bin/env python3
"""`team-kits/model_tiers.yaml` after DEC-0076, and the texts that describe the built ladder.

THREE SUBJECTS, each read the way the thing that runs reads it: the tiers table through
`gen_provider_artifacts.load_tiers` (the reader every generator and validator uses); the
generator's refusal as a PROCESS on a repo whose role pins a retired rung; the watch dates and
the maintenance route off the file's own comment block, because a date and a route that exist
only in prose are exactly the two things three radar reports could not get changed (BUG-0092).
The constitutions' ladder paragraphs are read against each kit's `ladder.yaml` (DEC-0078
consequences: "the kit's ladder paragraph must match the declaration (a test reads both)").
"""
import datetime
import io
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM_KITS = os.path.join(ROOT, "team-kits")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, TEAM_KITS)
from conftest import load_kit_module  # noqa: E402 -- the suite's one loader for shipped scripts
from kernel import dispatch  # noqa: E402

yaml = pytest.importorskip("yaml")
GENERATOR = os.path.join(TEAM_KITS, "gen_provider_artifacts.py")
TIERS = os.path.join(TEAM_KITS, "model_tiers.yaml")
tiers_reader = load_kit_module("gen_provider_artifacts_for_model_ladder", GENERATOR)


def kit_dirs():
    return sorted(os.path.join(TEAM_KITS, name) for name in os.listdir(TEAM_KITS)
                  if os.path.isfile(os.path.join(TEAM_KITS, name, "constitution", "AGENTS.md")))


def read(path):
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


# -- the table -------------------------------------------------------------------------------------

def test_every_provider_declares_exactly_the_three_rungs():
    """DEC-0076 (1): three rungs per provider, the same three positions everywhere, no fourth row.

    The count and the key set are read off the reference block, so a provider that gained or lost
    a row is red without this test naming today's rung names. That `light` is no longer placeable
    is the one example DEC-0076 names, and it is asserted as an example of the property, not as
    the property.
    """
    tiers, aliases = tiers_reader.load_tiers()
    reference = tiers_reader.rungs(tiers, tiers_reader.REFERENCE_PROVIDER)
    assert len(reference) == 3, reference
    assert len(tiers) >= 2, "the table knows no second provider -- the sameness below proves nothing"
    for provider in tiers:
        rows = tiers_reader.rungs(tiers, provider)
        assert set(rows) == set(reference), "%s declares %s, the reference %s" % (
            provider, sorted(rows), sorted(reference))
        assert len(set(rows.values())) == 3, "%s maps two rungs to one model: %s" % (provider, rows)
    assert set(aliases.values()) < set(reference), "an alias names a rung that is not a row"
    assert len(aliases) == 2, "the top rung has an alias the scaffold's rewrite does not know"
    assert not tiers_reader.table_places("light", tiers, aliases)
    assert not tiers_reader.provider_neutral_model("light", tiers, aliases)


def test_the_top_rung_translates_to_every_providers_own_top_row():
    """The correction DEC-0076 asked for: `fable` is not sent to the lead row of another provider
    any more -- each provider's top row answers, and it differs from that provider's lead row.
    RED against the table before this round: fable -> gpt-5.6-sol."""
    tiers, aliases = tiers_reader.load_tiers()
    lead_alias = next(alias for alias, rung in aliases.items() if rung == "opus")
    top = [name for name in tiers_reader.rungs(tiers, tiers_reader.REFERENCE_PROVIDER)
           if name not in set(aliases.values())]
    assert top == ["fable"], top
    for provider in tiers:
        if provider == tiers_reader.REFERENCE_PROVIDER:
            continue
        translated = tiers_reader.provider_model("fable", provider, tiers, aliases)
        assert translated == tiers_reader.rungs(tiers, provider)["fable"]
        assert translated != tiers_reader.provider_model(lead_alias, provider, tiers, aliases)


def _generator_repo(tmp_path, model):
    """The smallest repo the generator reads up to its pin check: settings, the roles manifest and
    one role definition. It stops at the pin when the pin is retired, and at the missing skill
    otherwise -- which is how the test tells the refusal apart from any later one."""
    repo = tmp_path / ("repo-" + model)
    (repo / ".claude" / "agents").mkdir(parents=True)
    (repo / ".claude" / "settings.json").write_text('{"agent": "lead"}', encoding="utf-8")
    (repo / ".claude" / "team_kit_roles.txt").write_text(
        "# agents-and-skills:team-kit-roles v1 team=demo count=1\nlead\n", encoding="utf-8")
    (repo / ".claude" / "agents" / "lead.md").write_text(
        "---\nname: lead\ndescription: the lead\nmodel: %s\neffort: high\n---\nbody\n" % model,
        encoding="utf-8")
    return repo


@pytest.mark.parametrize("retired", ["light", "haiku"])
def test_the_generator_refuses_a_retired_rung_pin_with_a_sentence_naming_the_decision(tmp_path, retired):
    """DEC-0076 (1) as a process: the shipped generator, a role pinning `light` or `haiku`, one
    sentence that names the decision and the pins that would have worked. The counter-run pins an
    alias and gets PAST the pin check (it fails later, on the missing skill), so the refusal
    measured is the pin's and not a refusal any repo of this shape would get."""
    run = subprocess.run([sys.executable, "-B", GENERATOR, "--repo", str(_generator_repo(tmp_path, retired)),
                          "--providers", "codex", "--lead", "lead"],
                         capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert run.returncode != 0
    assert "DEC-0076" in run.stderr and retired in run.stderr and "left untouched" in run.stderr, run.stderr
    control = subprocess.run([sys.executable, "-B", GENERATOR, "--repo", str(_generator_repo(tmp_path, "worker")),
                              "--providers", "codex", "--lead", "lead"],
                             capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert control.returncode != 0 and "DEC-0076" not in control.stderr, control.stderr
    assert "skill" in control.stderr, control.stderr


# -- the comment block: watch dates and the maintenance route --------------------------------------

WATCH_MARKER_RX = re.compile(r"^#\s*Watch dates\b", re.MULTILINE)
DATE_RX = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def watch_dates(text):
    """The dates listed under the `Watch dates` marker of a tiers table, as `date` objects.

    THE MARKER IS REQUIRED: a table with no marker cannot be read as 'nothing to watch', because
    that is exactly what deleting the block would look like. The list runs from the marker line to
    the first comment line that is blank or the first non-comment line; a date elsewhere in the
    file is a dated FACT (a shutdown that happened, a GA) and not a watch.
    `test_the_watch_date_reader_reads_the_block_and_only_the_block` mutates both edges.
    """
    marker = WATCH_MARKER_RX.search(text)
    if marker is None:
        raise AssertionError("model_tiers.yaml has no `# Watch dates` block -- the reader that refuses a "
                             "past watch date has nothing to read (BUG-0092 AC-2)")
    found = []
    for line in text[marker.start():].splitlines():
        if not line.startswith("#") or not line[1:].strip():
            break
        for match in DATE_RX.findall(line):
            found.append(datetime.date.fromisoformat(match))
    return found


def test_no_watch_date_in_the_tiers_table_lies_in_the_past():
    """BUG-0092 AC-2: red on any watch date before today's local date. RED against the shipped
    file of b7f282e (2026-08-05 and 2026-08-31 stood under the marker on 2026-09-05)."""
    today = datetime.date.today()
    stale = [date for date in watch_dates(read(TIERS)) if date < today]
    assert not stale, "watch dates in the past, remove them and make what they were about a fact or " \
                      "an item: %s" % ", ".join(date.isoformat() for date in stale)


def test_the_watch_date_reader_reads_the_block_and_only_the_block():
    """Both edges of `watch_dates`: a date under the marker is read (a past one is caught), a date
    in the paragraph above it is not, and a file without the marker is refused rather than read as
    empty -- the mutation in the direction the docstring denies."""
    text = ("# Price anchors: Opus 4.1 was shut down 2026-08-05\n"
            "# Watch dates -- a date in the past here is a defect:\n"
            "#   2099-01-01 something far off\n"
            "#   2000-01-01 something long gone\n"
            "\n"
            "#   2001-01-01 after the blank line, not a watch\n"
            "aliases: {}\n")
    assert watch_dates(text) == [datetime.date(2099, 1, 1), datetime.date(2000, 1, 1)]
    with pytest.raises(AssertionError):
        watch_dates(text.replace("# Watch dates", "# Dates"))


def test_the_maintenance_header_names_the_finding_to_item_route():
    """BUG-0092 AC-3, measured against the text: the MAINTENANCE paragraph names the capture
    command and the item link a watcher finding travels through, and says the journal is not the
    route. A header that names two maintainers and no route is the state three reports died in."""
    text = read(TIERS)
    start = text.index("MAINTENANCE")
    paragraph = text[start:text.index("\n#\n", start)]
    for needle in ("capture", "related_pr", "radar/decided.md", "BUG-0092"):
        assert needle in paragraph, "the MAINTENANCE paragraph does not name %r" % needle
    assert "open work item" not in text, "the header still calls the mechanic an open work item (AC-7)"
    for decision in ("DEC-0076", "DEC-0077", "DEC-0078"):
        assert decision in text, "the header does not point at %s" % decision


# -- the constitutions against the declarations ---------------------------------------------------

def ladder_paragraph(constitution_text):
    """The section of a constitution that carries the ladder -- the one whose heading names models."""
    sections = re.split(r"(?m)^## ", constitution_text)
    # `models` in the plural: "Presets & models" / "Models & presets" are the ladder sections,
    # "Phase model" and "The PROC model" are not
    hits = [section for section in sections if re.match(r"\d+\.\s[^\n]*\bmodels\b", section, re.IGNORECASE)]
    assert len(hits) == 1, "expected exactly one models section, found %d" % len(hits)
    return hits[0]


def test_the_constitutions_ladder_paragraph_says_what_the_declaration_says():
    """DEC-0078 consequences: each kit's ladder paragraph names its own top rung, its effort pair
    and every excepted role, points at `ladder.yaml`, and no longer carries the user-gated ladder
    the dispatcher never made (`sonnet-xhigh`) or the retired rung. Both files read, per kit."""
    for kit in kit_dirs():
        with io.open(os.path.join(kit, dispatch.LADDER_FILE), encoding="utf-8") as handle:
            ladder = dispatch._valid_ladder(kit, yaml.safe_load(handle))
        text = ladder_paragraph(read(os.path.join(kit, "constitution", "AGENTS.md")))
        name = os.path.basename(kit)
        assert dispatch.LADDER_FILE in text, "%s: the paragraph does not point at the declaration" % name
        assert re.search(r"\*\*%s\*\*" % ladder["top"], text), "%s: top rung %s not named" % (name, ladder["top"])
        for effort in ladder["effort"].values():
            assert re.search(r"\*\*%s\*\*" % effort, text), "%s: effort %s not named" % (name, effort)
        for role in ladder["exceptions"]:
            assert role in text, "%s: excepted role %s not named" % (name, role)
        for retired in ("sonnet-xhigh", "haiku", "`light`"):
            assert retired not in text, "%s: the paragraph still carries %r" % (name, retired)
        assert "ladder_for_order" in text or "python scripts/harness.py ladder" in text, name


def role_pin_of(kit, role):
    """The model a kit's OWN source pins for a role, resolved to a rung through the tiers table."""
    tiers, aliases = tiers_reader.load_tiers()
    pin = dispatch.role_pin(os.path.join(kit, "agents"), role)
    return tiers_reader.tier_of(str(pin), aliases)


def climbs(ladder, kit, role):
    """Does an order of `role` still climb a rung after a FAILED run? -- from the declaration.

    The behaviour itself is the kernel's and is measured against it in
    `tools/test_ladder.py::test_the_filing_pair_starts_on_its_pin_at_low_effort_and_still_climbs`;
    what is answered HERE is the same question in the form a TEXT has to get right, and it is
    computed from the shipped declaration plus the shipped pin rather than read out of prose:
    an order starts on the higher of its pin and its class floor, and it climbs while its role's top
    lies above that start.
    """
    rungs = ladder["rungs"]
    exception = ladder["exceptions"].get(role, {})
    top = str(exception.get("top", ladder["top"]))
    if "rung" in exception:
        start = str(exception["rung"])
    else:
        rule = ladder["classes"][ladder["roles"][role]]
        base = role_pin_of(kit, role)
        floor = top if rule == "top" else base if rule == "pin" else rule
        start = rungs[max(rungs.index(base), rungs.index(floor))]
    return rungs.index(top) > rungs.index(start)


def texts_that_describe_a_kits_ladder(kit):
    """The two shipped texts that tell a role what its ladder does: the constitution's paragraph
    and the declaration's own comment header (everything above the first non-comment line)."""
    declaration = read(os.path.join(kit, dispatch.LADDER_FILE))
    header = []
    for line in declaration.splitlines():
        if line.strip() and not line.startswith("#"):
            break
        header.append(line)
    return {"constitution": ladder_paragraph(read(os.path.join(kit, "constitution", "AGENTS.md"))),
            dispatch.LADDER_FILE: "\n".join(header)}


# WHAT A TEXT SAYS ABOUT A CLIMB, as three readings rather than one word. The first cut asked only
# whether "climb" occurred, and the verifier of round 2 measured what that came to: a paragraph
# changed to "a FAILED run NEVER climbs its rung above sonnet" -- the exact opposite claim -- kept
# the word and stayed green while the declaration climbed. So a denial is read as a denial, and a
# "keeps/stays on its rung" is read as the same denial in other words.
CLIMB_RX = re.compile(r"\bclimb", re.IGNORECASE)
DENIED_CLIMB_RX = re.compile(
    r"\b(?:never|not|cannot|can't|does\s?n[o']t|no\s+longer|without)\b(?:\s+\S+){0,3}\s+climb"
    r"|\bkeeps?\s+(?:its|their|the)\s+(?:rung|pin)\b|\bstays?\s+on\s+(?:its|their|the)\s+(?:rung|pin)\b",
    re.IGNORECASE)


def asserts_a_climb(sentence):
    """Does this sentence say the role's rung DOES climb? -- the statement, not the word.

    `tools/test_model_ladder.py::test_the_climb_reader_reads_the_statement_and_not_the_word`
    walks both directions on literal sentences, including the one the verifier planted.
    """
    return bool(CLIMB_RX.search(sentence)) and not DENIED_CLIMB_RX.search(sentence)


def test_the_climb_reader_reads_the_statement_and_not_the_word():
    """Both directions of `asserts_a_climb`, on literal text -- the round-2 finding as a test.

    The sentences below are the shapes the shipped texts use and the shapes a wrong text would use;
    the second group all CONTAIN "climb" and all DENY it, which is exactly the case a word search
    cannot tell from the first group.
    """
    for says_it_climbs in (
            "a FAILED run climbs its rung to opus like any other order",
            "the office-developer, which climbs to fable like a dev-team builder",
            "after every FAILED run one rung up, capped at the role's top -- it climbs"):
        assert asserts_a_climb(says_it_climbs), says_it_climbs
    for denies_it in (
            "a FAILED run never climbs its rung above sonnet, because the exception holds",
            "a FAILED run does not climb its rung here",
            "the pair cannot climb past sonnet",
            "the filing pair keeps its rung whatever happens",
            "the filing pair stays on its rung after a FAILED run"):
        assert not asserts_a_climb(denies_it), denies_it
    # ...and a sentence that says nothing about climbing is not a claim either way
    assert not asserts_a_climb("the filing pair runs at low effort")


def test_a_text_that_names_an_excepted_role_says_whether_its_rung_still_climbs():
    """B1 of the round-1 verification, as a reader instead of a corrected sentence.

    An `exceptions:` entry that fixes only the EFFORT leaves the rung alone -- the role starts on
    its pin and rule 2 climbs it like any other order. Until 2026-09-06 the office constitution and
    the office `ladder.yaml` said the filing pair "keeps `sonnet`/`low` as the named exception",
    which is false the moment a run fails (measured: records-clerk sonnet -> opus).

    BOTH DIRECTIONS, so the reader cannot rot in either: a text that names an excepted role whose
    rung still climbs has to say so, and a text that names one whose rung is pinned by a `top`
    exception must not claim a climb for it. The day the user answers the open question with
    `top: sonnet` for the filing pair, this test demands the OTHER sentence.
    """
    for kit in kit_dirs():
        with io.open(os.path.join(kit, dispatch.LADDER_FILE), encoding="utf-8") as handle:
            ladder = dispatch._valid_ladder(kit, yaml.safe_load(handle))
        for role in ladder["exceptions"]:
            still_climbs = climbs(ladder, kit, role)
            for where, text in texts_that_describe_a_kits_ladder(kit).items():
                sentences = [part for part in re.split(r"(?<=[.;])\s+", text) if role in part]
                if not sentences:
                    continue
                said = any(asserts_a_climb(part) for part in sentences)
                assert said == still_climbs, (
                    "%s/%s names %s and %s a climb, but the declaration %s one: %r"
                    % (os.path.basename(kit), where, role, "claims" if said else "claims no",
                       "gives it" if still_climbs else "denies it", sentences))


# -- the retired ladder, in the files that still instruct it ---------------------------------------

# WHAT THE RETIRED LADDER LOOKS LIKE, as a property rather than as the four steps it had: it spells
# a RUNG and an EFFORT as ONE hyphenated step (`sonnet-high`, `opus-xhigh`). DEC-0077 (1) made them
# two axes, so a kit text that still writes them as one step is instructing a ladder the dispatcher
# does not walk. Both halves of the pattern are READ, never listed: the rung names and their aliases
# come out of `model_tiers.yaml` through the generator's own reader, the efforts out of what the kits
# actually ship (their `ladder.yaml` pairs and exceptions, their `effort_map`s) -- so a rung or an
# effort that arrives tomorrow is covered without touching this file.
#
# THE OPEN SET, with the item that carries it. It held five shipped files while TSK-0130 ran (the
# two PM skills and the three `project_config.yaml` templates, all outside that item's
# allowed_scope) and the generation-5 merge (TSK-0133) emptied it: G5-1 rewrote the skills, the
# merge the templates. What BUG-0250 (H168) still carries is not a `<rung>-<effort>` step and is
# therefore outside this reader on purpose: `session_status.py`'s `lead/worker/light` map and the
# scaffold's `light -> haiku` rewrite lines. The map stays an enumeration measured from BOTH ends
# below, so the next file to spell a retired step lands here with its item instead of passing.
STALE_LADDER_TEXTS = {}


def shipped_effort_vocabulary():
    """Every effort value the kits actually ship -- ladder pairs, ladder exceptions, effort maps."""
    efforts = set()
    for kit in kit_dirs():
        ladder = dispatch._valid_ladder(kit, yaml.safe_load(read(os.path.join(kit, dispatch.LADDER_FILE))))
        efforts.update(ladder["effort"].values())
        efforts.update(str(rule["effort"]) for rule in ladder["exceptions"].values()
                       if "effort" in rule)
        config = yaml.safe_load(read(os.path.join(
            kit, "templates", "project_memory", "project_config.yaml")))
        efforts.update(str(value) for value in (config.get("effort_map") or {}).values())
    return efforts


def retired_ladder_steps(text):
    """The `<rung>-<effort>` steps a text spells, both vocabularies read off the shipped files."""
    tiers, aliases = tiers_reader.load_tiers()
    names = set(aliases) | set(tiers_reader.rungs(tiers, tiers_reader.REFERENCE_PROVIDER))
    pattern = re.compile(r"\b(?:%s)-(?:%s)\b" % ("|".join(sorted(names)),
                                                 "|".join(sorted(shipped_effort_vocabulary()))))
    return sorted(set(pattern.findall(text)))


def tracked_kit_files():
    """Every tracked file under `team-kits/` -- the shipped surface, asked of git, not of a walk."""
    listed = subprocess.run(["git", "ls-files", "-z", "team-kits"], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=60)
    assert listed.returncode == 0, listed.stderr
    return [path for path in listed.stdout.split("\0") if path]


def test_no_shipped_kit_text_still_names_the_retired_user_gated_ladder():
    """DEC-0076/DEC-0077 in the shipped texts: nothing outside the named open set instructs the
    retired rung-plus-effort ladder any more.

    BOTH ENDS of `STALE_LADDER_TEXTS` are measured, because it is an enumeration and an enumeration
    that only ever grows is a claim nobody re-reads: a file that claims the ladder and is NOT in the
    map fails here (the contradiction spread), and a file IN the map that no longer claims it fails
    too (the repair happened and the entry, with it the item's own justification, is dead). The
    entries are outside TSK-0130's scope by its item's own boundaries -- BUG-0250 carries the
    measurement, the seven files and the repair.
    """
    claiming = {}
    for relative in tracked_kit_files():
        try:
            text = read(os.path.join(ROOT, relative.replace("/", os.sep)))
        except (OSError, UnicodeDecodeError):
            continue
        steps = retired_ladder_steps(text)
        if steps:
            claiming[relative] = steps
    spread = {path: steps for path, steps in claiming.items() if path not in STALE_LADDER_TEXTS}
    assert not spread, (
        "these shipped kit files spell a rung and an effort as one ladder step and are not in the "
        "open set of BUG-0250: %s" % spread)
    repaired = sorted(set(STALE_LADDER_TEXTS) - set(claiming))
    assert not repaired, (
        "these files no longer instruct the retired ladder -- drop them from STALE_LADDER_TEXTS "
        "(and close BUG-0250 when the set is empty): %s" % repaired)


def test_the_retired_ladder_reader_reads_both_vocabularies_off_the_shipped_files():
    """The mutation direction the reader above denies: that it knows only today's four steps.

    A step built from an ALIAS (`worker`) and from an effort only one kit ships (`medium`, the
    office default) is found, and a hyphenated pair of two words that are neither is not -- so the
    day a rung or an effort is added, the reader covers it without an edit here.
    """
    assert retired_ladder_steps("ladder worker-medium -> lead-xhigh") == ["lead-xhigh", "worker-medium"]
    assert retired_ladder_steps("sonnet-high") == ["sonnet-high"]
    assert retired_ladder_steps("read-only, opus level, high effort, luna-ultra") == []
    assert "medium" in shipped_effort_vocabulary() and "low" in shipped_effort_vocabulary()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
