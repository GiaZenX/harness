#!/usr/bin/env python3
"""A claim of automation about the radar watchers is a mechanism this repo can measure, never a
sentence (PR-0010 AC-1, invariant 1 of that goal) -- and since DEC-0090 the same is true of the
duo's ARTIFACTS: the names they carry, the rung they pin, and the report name they write.

MEASURED 2026-09-05 before this existed: `radar/README.md` line 3 said "A scheduled watcher duo
runs once a week", both watcher definitions said "Triggered by the weekly schedule", and nothing IN
THIS REPOSITORY started a run. What started the claude half was outside it and went unread for a
day: a Claude DESKTOP scheduled task on the maintainer's host, whose Friday-evening reports had been
in `radar/` since 2026-07-17 (DEC-0089, correcting DEC-0085). So this module reads the three texts
that describe how a run starts and refuses any AUTOMATION claim the declaration does not back --
PER WATCHER, because the halves are in different states: the claude half's Friday run is recorded
and shows its cadence, its Sunday run and both codex runs do not exist yet. HOW MANY reports there
were is deliberately not written here: the number grows every week, and
`tools/radar_routine.py --describe` counts it.

WHAT COUNTS AS A CLAIM (`automation_claims`): a SENTENCE carrying a form of "schedule", "automatic"
or "automation", "cron", the Task Scheduler, a weekday, an app's task/routine/automation, or the
rejected cloud routine by name -- unless the same sentence names the ABSENCE of a mechanism
(`DISCLAIMER_RX`). The word half is deliberately coarse in one direction: a sentence that uses the
word about something else is refused too, and the text answers by rewording. A cadence on its own
("once a week", "weekly") is an intent and not a claim of a mechanism. A LIMIT is not a disclaimer:
"fires only while the app is open" says how the mechanism runs and is judged as a claim about it
(DEC-0089 (4)) -- the two spellings that used to be read as exemptions are in
`test_the_claim_reader_reads_what_it_claims` as claims.

WHAT BACKS A CLAIM is `tools/radar_routine.py --describe`, asked as a PROCESS, and its
`starts_itself` is a map per watcher DERIVED from the lead's record (`radar/routine.json`) and the
cadence the reports show -- for EVERY run that watcher owes, which since DEC-0090 (3) is one per
provider. The rule lives in `schedule_claim_offence`, one reader for the shipped texts and the
synthetic ones:

  * a claiming sentence names the mechanism -- the module, or one of the kinds of local app routine
    the declaration publishes -- or it is refused;
  * the watchers it is about are the ones it names, or both when it names none; if every one of
    them is started by a recorded routine for every run it owes, naming the mechanism is enough;
  * otherwise the sentence has to say WHO starts a run (`STARTER_RX`), because for that watcher
    something does not.

Both states are walked by `test_the_claim_rule_follows_the_record_per_watcher` on sentences it
writes itself, so neither branch waits for the repository to reach it.
"""
import datetime
import io
import json
import os
import re
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from conftest import load_kit_module  # noqa: E402 -- the suite's one loader for shipped scripts
from test_model_pins import under_an_agents_directory  # noqa: E402 -- one role-location predicate

# The texts that tell a reader how a watcher run starts: the radar directory's own README and the
# watcher definitions. `test_the_texts_this_reads_are_the_ones_that_describe_the_watchers` derives
# the second half from the tracked tree -- every role definition that names `radar/` -- so a third
# watcher joins the subject or turns that test red.
TEXTS = ("radar/README.md", ".claude/agents/claude-watcher.md", ".claude/agents/codex-watcher.md")
RADAR_README = TEXTS[0]
WATCHER_ROLES = ("claude-watcher", "codex-watcher")
MECHANISM = os.path.join(ROOT, "tools", "radar_routine.py")
# WHO STARTS A RUN, as the shapes a true sentence can take for a run nothing starts by itself.
# It is an enumeration of wordings and it is guarded from both ends by
# `test_the_starter_reader_reads_a_named_starter_and_nothing_else`: a sentence with none of them is
# refused, and each one is shown to admit a sentence that really does name a starter.
STARTER_RX = re.compile(
    r"\brun by\b|\bstarted by\b|\bstart(?:s|ed)? it\b|\byou (?:run|start)\b|\bthe lead\b|"
    r"\bby hand\b|\bwhen (?:you|the lead|somebody)\b|--run\b",
    re.IGNORECASE)
# The words that make a sentence a claim about a mechanism. The two apps and the cloud routine are
# named here because the natural true sentence about any of them carries none of the older words
# ("the Desktop task starts the claude-watcher every Friday") -- measured 2026-09-06 for the cloud
# shape, whose sentence the previous reader looked straight past. `automat` rather than `automatic`
# since DEC-0090: a Codex AUTOMATION is the codex half's mechanism, and a reader that only knew the
# adjective would have let "the Codex app Automation runs it every Monday" through un-judged.
_APP_ROUTINE = r"(?:desktop|codex|local|app)[ -](?:task|routine|automation|app)s?"
AUTOMATION_CLAIM_RX = re.compile(
    r"\bschedul|\bautomat|\bcron\b|task scheduler|aufgabenplanung"
    r"|\b" + _APP_ROUTINE + r"\b|\bclaude\.ai\b|\bcloud routine\b|\bremotetrigger\b"
    r"|\b(?:mon|tues|wednes|thurs|fri|satur|sun)days?\b",
    re.IGNORECASE)
# A sentence that NAMES the absence of a mechanism is not a claim of one; these are the shapes
# such a sentence may take, and `test_the_claim_reader_reads_what_it_claims` shows they cannot be
# stretched around a claim. A LIMIT ("only while the app is open", "state unknown", "nothing here
# can ask it") is NOT among them since DEC-0089: it describes how the mechanism runs and is read as
# a claim about it.
DISCLAIMER_RX = re.compile(
    r"does not build|nothing in this repo starts|no (?:cron|schedule)|started by (?:hand|a person)"
    r"|does not start itself|starts nothing",
    re.IGNORECASE)
SENTENCE_END_RX = re.compile(r"(?<=[.!?])\s+")


def read(relative):
    with io.open(os.path.join(ROOT, relative.replace("/", os.sep)), encoding="utf-8-sig") as handle:
        return handle.read()


def sentences(text):
    """The sentences of a markdown text: paragraphs joined across their line breaks (a `#`
    comment prefix and list markers stripped), then split at sentence ends."""
    paragraphs, current = [], []
    for line in text.splitlines():
        bare = re.sub(r"^\s*(?:#+\s*|[-*]\s+)?", "", line).strip()
        if bare:
            current.append(bare)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return [sentence for paragraph in paragraphs for sentence in SENTENCE_END_RX.split(paragraph)
            if sentence.strip()]


def automation_claims(text):
    """Every sentence of `text` that claims a mechanism starts the watchers.

    A sentence carrying a claim WORD (`AUTOMATION_CLAIM_RX`) is a claim; one that carries it AND
    names the ABSENCE of the mechanism (`DISCLAIMER_RX`) is a measured statement, not a claim, and is
    left out. Sentences, not lines: a claim and its disclaimer wrap across lines in every markdown
    file this reads.
    """
    return [sentence for sentence in sentences(text)
            if AUTOMATION_CLAIM_RX.search(sentence) and not DISCLAIMER_RX.search(sentence)]


def mechanism_description():
    """What the trigger mechanism says about itself, or None when the repo ships none.

    Asked as a PROCESS (`--describe`, JSON on stdout), never read as text: the description is the
    declaration's own answer, produced by the code that derives it.
    """
    if not os.path.isfile(MECHANISM):
        return None
    run = subprocess.run([sys.executable, "-B", MECHANISM, "--describe"],
                         capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def mechanism_names(described):
    """The words a sentence may use to NAME the mechanism, derived from the declaration.

    The module's own stem, plus the words of every routine KIND the declaration publishes that are
    not a runner id. That last clause is what keeps `codex` out of the set: `codex-watcher` is a
    watcher's name, and a sentence naming it would otherwise count as naming a mechanism. What is
    left of `desktop_task` is "desktop" and "task", of `codex_automation` "automation" -- which is
    exactly how a true sentence about either app names it.
    """
    runners = set(described["runners"])
    words = {os.path.splitext(os.path.basename(MECHANISM))[0]}
    for routine in described["routines"]:
        words |= {part for part in str(routine["kind"]).split("_") if part not in runners}
    return words


def test_no_text_claims_a_schedule_the_repo_does_not_build():
    """The invariant, on the shipped texts, in whatever state the record is in.

    NO mechanism shipped -> no text may claim one. A mechanism shipped -> every claiming sentence
    is judged by `schedule_claim_offence` against the declaration's per-watcher answer.

    RED against the texts of b7f282e (three files, five claiming lines); RED again the day a text
    calls the rejected cloud routine the mechanism, or promises a schedule for a run
    `radar/routine.json` does not record -- which since DEC-0090 (3) includes the three routines
    the user has not created yet.
    """
    described = mechanism_description()
    claims = {relative: automation_claims(read(relative)) for relative in TEXTS}
    if described is None:
        offenders = {relative: lines for relative, lines in claims.items() if lines}
        assert not offenders, (
            "these lines claim a mechanism starts the watchers and the repo builds none (%s does "
            "not exist): %s" % (os.path.relpath(MECHANISM, ROOT).replace(os.sep, "/"),
                                json.dumps(offenders, indent=2)))
        return
    assert set(described["watchers"]) == set(WATCHER_ROLES), described
    assert described["cadence"] == "weekly", described
    assert set(described["starts_itself"]) == set(WATCHER_ROLES), described["starts_itself"]
    assert all(isinstance(value, bool) for value in described["starts_itself"].values())
    offenders = {relative: [(sentence, schedule_claim_offence(sentence, described))
                            for sentence in found
                            if schedule_claim_offence(sentence, described)]
                 for relative, found in claims.items()}
    offenders = {relative: rows for relative, rows in offenders.items() if rows}
    assert not offenders, json.dumps(offenders, indent=2)


def schedule_claim_offence(sentence, described):
    """Why this claiming sentence is not backed by the declaration, or None when it is.

    THE RULE lives in ONE function so the shipped texts and the synthetic ones of
    `test_the_claim_rule_follows_the_record_per_watcher` are judged by the same reader:

      * a sentence naming a mechanism the DECLARATION lists as not built (`cloud_option`, by the
        names it publishes) is refused whatever else it says -- naming a real routine beside it
        does not rescue it;
      * the sentence names the mechanism -- the module, or one of the kinds of local app routine
        the declaration publishes -- so a reader can go and see what it does; a sentence naming
        neither (a bare "schedule") is refused;
      * the watchers it speaks about are the ones it names, or both when it names none; for every
        one of them the declaration's `starts_itself` says whether every run it owes is started by
        a recorded routine with a measured cadence;
      * where every named watcher is, naming the mechanism is enough; where one is not, the sentence
        has to say who starts the rest, because nothing does by itself.
    """
    # A MECHANISM THE DECLARATION LISTS AS NOT BUILT is refused first and whatever else the
    # sentence says: naming the Desktop task in the same breath did not make "the claude.ai cloud
    # routine starts the claude-watcher every Friday from the Desktop" true, and a reader that only
    # asked for the mechanism's name let it pass (verify round 1 of TSK-0133, B3). The names are
    # the declaration's own (`cloud_option.named_as`), not a list kept here -- and that list has no
    # tripwire at either end, which is BUG-0274 / H190 and is open.
    for key, option in described.items():
        if isinstance(option, dict) and option.get("built") is False:
            named = [word for word in option.get("named_as", ())
                     if word.lower() in sentence.lower()]
            if named:
                return ("names %s (%r), which the declaration lists as not built"
                        % (key, named[0]))
    named_mechanism = [word for word in mechanism_names(described)
                       if re.search(r"\b%s\b" % re.escape(word), sentence, re.IGNORECASE)]
    if not named_mechanism:
        return ("names none of %s as the mechanism"
                % ", ".join(sorted(mechanism_names(described))))
    named = [watcher for watcher in WATCHER_ROLES if watcher in sentence] or list(WATCHER_ROLES)
    silent = [watcher for watcher in named if not described["starts_itself"].get(watcher)]
    if not silent:
        return None
    return None if STARTER_RX.search(sentence) else (
        "not every weekly run of %s is started by a recorded routine with a measured cadence, so "
        "the sentence has to say who starts the rest" % ", ".join(silent))


def routine_module(name="radar_routine_under_test"):
    return load_kit_module(name, os.path.join(ROOT, "tools", "radar_routine.py"))


def a_record_naming(directory, name="routine.json", entries=None, **overrides):
    """A `radar/routine.json` in the shape the declaration publishes, written to `directory`.

    One well-formed entry for the claude half's claude-run by default; `overrides` bend that entry,
    `entries` replaces the list outright.
    """
    entry = {"id": "claude-watcher-by-claude", "watcher": "claude-watcher", "runner": "claude",
             "kind": "desktop_task",
             "path": "~/.claude/scheduled-tasks/radar-watcher/SKILL.md",
             "schedule_as_told": {"day": "friday", "time_local": "~20:00",
                                  "as_told_by": "the user, 2026-09-06"},
             "source": "DEC-0089", "first_report": "2026-07-17", "last_report": "2026-08-28",
             "recorded": "2026-09-06"}
    entry.update(overrides)
    path = os.path.join(directory, name)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"routines": [entry] if entries is None else entries,
                   "recorded_by": "a test"}, handle)
    return path


def every_routine_recorded(directory, name="all-four.json"):
    """A record holding all four routines of the plan, each on the evening the plan names."""
    routine = routine_module("radar_routine_full_record")
    entries = [{"id": key, "watcher": entry["watcher"], "runner": entry["runner"],
                "kind": entry["kind"],
                "schedule_as_told": {"day": entry["schedule_as_told"]["day"],
                                     "time_local": "~20:00", "as_told_by": "a test"},
                "source": "a test"}
               for key, entry in sorted(routine.routine_plan().items())]
    return a_record_naming(directory, name=name, entries=entries)


def a_radar_dir_with(directory, *names):
    """A radar directory holding exactly these dated report names (empty files)."""
    where = os.path.join(directory, "radar")
    os.makedirs(where, exist_ok=True)
    for name in os.listdir(where):
        os.remove(os.path.join(where, name))
    for name in names:
        io.open(os.path.join(where, name), "w", encoding="utf-8").close()
    return where


# 2026-07-17 / 07-24 are Fridays; 2026-09-05 / 09-12 are Saturdays; 2026-07-15 is a Wednesday.
# 2026-09-06 / 09-13 are Sundays; 2026-09-07 / 09-14 are Mondays.
FRIDAYS = ("2026-07-17-claude-by-claude.md", "2026-07-24-claude-by-claude.md")
SATURDAYS = ("2026-09-05-codex-by-claude.md", "2026-09-12-codex-by-claude.md")
SUNDAYS = ("2026-09-06-claude-by-codex.md", "2026-09-13-claude-by-codex.md")
MONDAYS = ("2026-09-07-codex-by-codex.md", "2026-09-14-codex-by-codex.md")


_BULLET_END = "(?=" + chr(92) + "n" + chr(92) + "s*" + chr(92) + "n)"
_REJECTED_BULLET_RX = re.compile(r"^- \*\*The rejected alternative\*\*.*?" + _BULLET_END,
                                 re.MULTILINE | re.DOTALL)
_BOLD_SPAN_RX = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)


def names_the_rejected_bullet_writes(text):
    """Every name `radar/README.md`'s rejected-alternative bullet writes for the option.

    MARKED BY THE TEXT ITSELF, because deciding which noun phrase of a paragraph IS a name for a
    mechanism is world knowledge and not a derivation from this tree. The bullet writes each name
    in bold; its own lead-in is bold too and is dropped, being the heading of the bullet and not a
    name. Backticks stay free for code (`cloud_option`, `--describe`), so marking a name cannot
    collide with naming a field.
    """
    bullet = _REJECTED_BULLET_RX.search(text)
    if bullet is None:
        return None
    spans = [" ".join(span.split()) for span in _BOLD_SPAN_RX.findall(bullet.group(0))]
    return sorted({span.lower() for span in spans[1:]})


def test_the_names_of_the_rejected_option_are_the_ones_its_bullet_writes():
    """BUG-0274 / H190: the names of the not-built cloud option are measured at BOTH ends against
    the bullet that describes it -- a name the shipped text writes and the declaration does not
    publish let a sentence promoting the rejected option through the claim reader.

    THE OCCASION IS MEASURED (TSK-0133 verify round 2, N1): with one sentence inserted into
    `radar/README.md`, "The hosted code routine of the platform starts the radar-watcher every
    Friday from the Desktop." and its sandbox twin were GREEN over the whole of this file, while
    the same sentence with `claude.ai` in it was red -- because the three names the declaration
    published were a list nothing measured, and the README described the very same option in two
    words the list did not carry.

    BOTH ENDS: a name the bullet writes and the declaration does not publish is red (the shape
    above), and an entry the declaration publishes that the bullet never writes is red too -- a
    dead name is a reader nobody can reach. And each published name is driven through the claim
    reader, so the list is not merely equal to the text but really refuses a sentence.
    """
    described = mechanism_description()
    published = sorted({name.lower() for name in described["cloud_option"]["named_as"]})
    assert published, "the declaration publishes no name for the rejected option at all"
    written = names_the_rejected_bullet_writes(read(RADAR_README))
    assert written is not None, (
        "%s carries no bullet beginning `- **The rejected alternative**`, so the second source "
        "this list is measured against is gone" % RADAR_README)
    assert written == published, (
        "the names %s writes for the rejected option and the ones the declaration publishes have "
        "drifted apart -- written %s, published %s. A name only the text has passes the claim "
        "reader; a name only the declaration has is one nobody can reach."
        % (RADAR_README, written, published))
    for name in published:
        sentence = ("The %s starts the claude-watcher every Friday from the Desktop task."
                    % name)
        offence = schedule_claim_offence(sentence, described)
        assert offence and "not built" in offence, (
            "a sentence promoting the rejected option as %r is not refused (%r), although the "
            "declaration lists it as not built" % (name, offence))


def test_the_runner_vocabulary_is_the_ladders_provider_vocabulary():
    """The RUNNERS table is an enumeration, so both its ends are held against the ladder (DEC-0090).

    A watcher runs under every provider the harness knows, and the harness knows its providers in
    exactly one place: `team-kits/model_tiers.yaml`. So the runner ids ARE that file's provider
    keys -- a provider the ladder gains and this table does not is red (the new runner would silently
    owe no routine), and a runner here the ladder cannot place a model for is red too (its overlay
    could not be generated). That is also why the FOUR routines are nowhere written down as a number:
    four is `len(WATCHERS) * len(RUNNERS)`.

    AND THE SUFFIXES: every watcher's report suffix has to be one of those provider ids, because
    `report_runner` reads a legacy two-part name as a run by the watcher's own provider. The module
    refuses at import when that breaks; this states it where a reader looks for it.
    """
    routine = routine_module("radar_routine_vocabulary")
    tiers = load_kit_module("gen_provider_artifacts_for_runners",
                            os.path.join(ROOT, "team-kits", "gen_provider_artifacts.py"))
    providers, _aliases = tiers.load_tiers()
    assert set(routine.RUNNERS) == set(providers), (
        "the runners and the ladder's providers disagree: %s vs %s"
        % (sorted(routine.RUNNERS), sorted(providers)))
    assert {entry["suffix"] for entry in routine.WATCHERS.values()} <= set(routine.RUNNERS)
    assert routine.SESSION_RUNNER in routine.RUNNERS
    for runner, entry in routine.RUNNERS.items():
        assert entry["kind"] and entry["app"] and "%(watcher)s" in entry["follow"], runner


def test_the_routine_plan_covers_every_watcher_on_every_runner_and_staggers_them():
    """The four routines of DEC-0090 (4): the PAIRS are derived, the evenings are the user's.

    Three properties, and each one is a way the plan could be wrong without anybody noticing:
    every watcher is planned on every runner (the product, not a list somebody maintains); no two
    routines share an evening, because an app skips a scheduled task while another one of its own is
    running, which is the reason the user was asked for four different days at all; and every
    routine names the report it writes, so the four never collide on one file name.

    The staggering is measured rather than described: two routines moved onto one evening make this
    red, and until 2026-09-11 the four weekdays stood only in a decision's prose.
    """
    routine = routine_module("radar_routine_plan")
    plan = routine.routine_plan()
    assert set(plan) == {routine.routine_id(watcher, runner)
                         for watcher in routine.WATCHERS for runner in routine.RUNNERS}
    days = [entry["schedule_as_told"]["day"] for entry in plan.values()]
    assert len(set(days)) == len(days), "two routines share an evening: %s" % sorted(days)
    assert set(days) <= set(routine.WEEKDAYS), sorted(days)
    writes = [entry["writes"] for entry in plan.values()]
    assert len(set(writes)) == len(writes), "two routines write the same report name: %s" % writes
    for key, entry in plan.items():
        assert entry["kind"] == routine.RUNNERS[entry["runner"]]["kind"], key
        assert entry["instructions"].count(entry["writes"]) == 1, key
        assert entry["watcher"] in entry["instructions"] and entry["runner"] in entry["instructions"]


def test_the_describe_output_hands_the_lead_an_instructions_text_for_every_routine():
    """DEC-0090 (5): nothing here can create a routine, so `--describe` has to hand out the text.

    The lead asks Claude Desktop for the two Claude tasks and the USER pastes the two Codex texts
    into the Codex app; a text that does not say which artifact to follow, or that leaves the report
    name out, produces a run that overwrites the other provider's report. Read out of the PROCESS,
    so what is measured is what the lead would really copy.
    """
    described = mechanism_description()
    assert len(described["routines"]) == len(described["watchers"]) * len(described["runners"])
    for entry in described["routines"]:
        body = entry["instructions"]
        assert entry["writes"] in body, entry["id"]
        assert "radar/decided.md" in body and "READ-ONLY" in body, entry["id"]
        assert re.search(r"\.(?:md|toml)\b", body), (
            "%s does not say which artifact the run is to follow" % entry["id"])
        assert entry["schedule_as_told"]["day"] and entry["schedule_as_told"]["as_told_by"]
        assert "not readable from disk" in entry["schedule_as_told"]["as_told_by"], (
            "the schedule is published without saying it is a statement and not a measurement")
        assert isinstance(entry["recorded"], bool) and isinstance(entry["starts_itself"], bool)


def test_the_self_start_reader_answers_off_the_record_and_the_reports():
    """`starts_itself` is DERIVED per watcher from two things and needs both (DEC-0089 (3)).

    The field decides how far every text in `TEXTS` may go, so a constant there would be a claim
    nothing checks -- and it WAS one until 2026-09-06, when the mutation that flipped it stayed
    green. A ROUTINE is live when its record entry is well-formed AND that watcher-and-runner's
    reports show the recorded weekday at least `CADENCE_EVIDENCE_MIN` times, and False for every way
    short of that: no record, an unreadable one, an unknown watcher or runner, a kind that is not
    the runner's, a day that is not a weekday, too few reports on the day, reports of the other
    runner, and a routine merely MENTIONED in some other field. All of them are the fail-closed
    direction -- a half-written record or a run somebody started by hand never makes a sentence
    truer than the mechanism.

    AND THE WATCHER ANSWER IS `all`, not `any` (DEC-0090 (3)): a watcher whose Friday task fires
    while its Sunday Automation does not exist is started for half of what it owes, and a text may
    not say it runs weekly through its routine. Measured below: the record that makes the claude
    half's Friday run live leaves `starts_itself` False for both.
    """
    routine = routine_module("radar_routine_self_start")
    with tempfile.TemporaryDirectory() as directory:
        radar = a_radar_dir_with(directory, *FRIDAYS)
        live = a_record_naming(directory)
        assert routine.live_routines(live, radar)["claude-watcher-by-claude"] is True
        assert sum(routine.live_routines(live, radar).values()) == 1
        assert routine.starts_itself(live, radar) == {"claude-watcher": False,
                                                      "codex-watcher": False}, (
            "one of two weekly runs counted as the watcher being started by a mechanism")
        assert not any(routine.live_routines(
            os.path.join(directory, "no-such-file.json"), radar).values())
        broken = os.path.join(directory, "broken.json")
        with io.open(broken, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("{not json")
        assert not any(routine.live_routines(broken, radar).values())
        # every way a recorded entry fails to be a routine this module can count
        for label, overrides in (("another kind", {"kind": "cloud_trigger"}),
                                 ("the other runner's kind", {"kind": "codex_automation"}),
                                 ("unknown watcher", {"watcher": "not-a-watcher"}),
                                 ("unknown runner", {"runner": "not-a-runner"}),
                                 ("not a weekday", {"schedule_as_told": {"day": "weekly"}}),
                                 ("no schedule", {"schedule_as_told": None})):
            half = a_record_naming(directory, name="half.json", **overrides)
            assert not any(routine.live_routines(half, radar).values()), label
        for entry in ("a string where an entry should be", 42):
            odd = os.path.join(directory, "odd.json")
            with io.open(odd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump({"routines": [entry]}, handle)
            assert not any(routine.live_routines(odd, radar).values()), entry
        # ...and NO string search: a record that merely MENTIONS a routine in another field is not one
        mention = os.path.join(directory, "mention.json")
        with io.open(mention, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"note": "kind desktop_task, watcher claude-watcher, runner claude, friday",
                       "routines": []}, handle)
        assert not any(routine.live_routines(mention, radar).values())
        # THE SECOND HALF: the record alone is a sentence; the reports have to show the weekday
        one_friday = a_radar_dir_with(directory, FRIDAYS[0])
        assert routine.live_routines(live, one_friday)["claude-watcher-by-claude"] is False, (
            "one report on the weekday counted as a cadence -- a hand-started run can produce one")
        other_days = a_radar_dir_with(directory, "2026-07-15-claude-by-claude.md",
                                      "2026-08-01-claude-by-claude.md")
        assert routine.live_routines(live, other_days)["claude-watcher-by-claude"] is False
        wrong_watcher = a_radar_dir_with(directory, "2026-07-17-codex-by-claude.md",
                                         "2026-07-24-codex-by-claude.md")
        assert routine.live_routines(live, wrong_watcher)["claude-watcher-by-claude"] is False, (
            "the other watcher's reports counted as this watcher's cadence")
        wrong_runner = a_radar_dir_with(directory, "2026-07-17-claude-by-codex.md",
                                        "2026-07-24-claude-by-codex.md")
        assert routine.live_routines(live, wrong_runner)["claude-watcher-by-claude"] is False, (
            "the other RUNNER's reports counted as this routine's cadence -- the whole point of "
            "the suffix DEC-0090 (3) added")
        undated = a_radar_dir_with(directory, "2026-07-03.md", "2026-07-10.md")   # Fridays, no suffix
        assert routine.live_routines(live, undated)["claude-watcher-by-claude"] is False, (
            "a report with no watcher suffix counted as a named watcher's run")
        # ...and a watcher turns True only when ALL of its routines are live
        four = every_routine_recorded(directory)
        everything = a_radar_dir_with(directory, *FRIDAYS, *SATURDAYS, *SUNDAYS, *MONDAYS)
        assert all(routine.live_routines(four, everything).values())
        assert routine.starts_itself(four, everything) == {"claude-watcher": True,
                                                           "codex-watcher": True}
        missing_one = a_radar_dir_with(directory, *FRIDAYS, *SATURDAYS, *SUNDAYS, MONDAYS[0])
        assert routine.starts_itself(four, missing_one) == {"claude-watcher": True,
                                                            "codex-watcher": False}
    # ...and the repository's own answer, which is what the texts are held against today: the claude
    # half's Friday run is recorded (DEC-0089) and shows its Fridays, the other three of DEC-0090 (4)
    # are not created yet. The day the lead records them and their second reports land, this line is
    # the one that says the texts may now say so.
    assert routine.starts_itself() == {"claude-watcher": False, "codex-watcher": False}, (
        "radar/routine.json or the reports moved -- re-read the texts in %s against the new answer"
        % (TEXTS,))
    assert routine.live_routines()["claude-watcher-by-claude"] is True, (
        "the Friday run DEC-0089 measured is no longer backed by the record and the reports")


def test_the_claim_rule_follows_the_record_per_watcher(tmp_path, monkeypatch):
    """The invariant has a state PER WATCHER (DEC-0089) and both are walked here, not just today's.

    STATE ONE, the one the repository is in: only the claude half's Friday run is recorded and shows
    its cadence -- so every sentence about either watcher has to say who starts the rest. STATE TWO:
    all four routines of DEC-0090 (4) are recorded and have run twice -- a sentence about both may
    now name the mechanism alone. In EVERY state a sentence that calls the rejected cloud routine the
    mechanism is an offence, because it names nothing the declaration knows.

    Both states are measured on sentences THIS TEST WRITES, judged by `schedule_claim_offence`, the
    same reader the shipped texts go through.
    """
    routine = routine_module("radar_routine_two_states")
    monkeypatch.setattr(routine, "RADAR", a_radar_dir_with(str(tmp_path), *FRIDAYS, *SATURDAYS,
                                                           *SUNDAYS, *MONDAYS))
    monkeypatch.setattr(routine, "ROUTINE_RECORD", a_record_naming(str(tmp_path)))
    state_one = routine.description()
    assert state_one["starts_itself"] == {"claude-watcher": False, "codex-watcher": False}
    assert "Desktop" in state_one["started_by"]["claude-watcher"]
    assert "--run codex-watcher" in state_one["started_by"]["codex-watcher"]
    assert "Codex app" in state_one["started_by"]["codex-watcher"], (
        "the run no command here can start is offered as `--run` anyway")
    monkeypatch.setattr(routine, "ROUTINE_RECORD", every_routine_recorded(str(tmp_path)))
    state_two = routine.description()
    assert state_two["starts_itself"] == {"claude-watcher": True, "codex-watcher": True}

    # The sentence that was TRUE before DEC-0090 (3) and is only half true after it: the Friday
    # Desktop task is recorded, the Sunday Automation is not, so the watcher is not started for
    # everything it owes. It is the state-one offence this round added, and the same sentence is
    # backed in state two.
    claude_bare = ("The claude-watcher is scheduled every Friday evening by a Claude Desktop "
                   "scheduled task on the maintainer's host (recorded in radar/routine.json).")
    claude_ok = claude_bare[:-1] + ", and the lead starts its Codex run by hand."
    codex_silent = "The codex-watcher is started every Saturday by a Claude Desktop scheduled task."
    codex_ok = ("The codex-watcher has no recorded Desktop task yet; the lead starts it with "
                "`--run codex-watcher` when `--due` names it.")
    both_desktop = "Both watchers are started weekly by Claude Desktop scheduled tasks."
    automation = "The codex-watcher runs every Monday as a Codex app Automation."
    both_bare = "The watchers run on a weekly schedule."
    module_silent = "tools/radar_routine.py declares a weekly schedule."
    cloud_again = ("A claude.ai code routine starts both watchers weekly in a cloud sandbox and "
                   "returns each report as a pull request.")
    # the verifier's sentence (TSK-0133 round 1, B3): the not-built mechanism dressed in the
    # built one's name, about the watcher whose task IS recorded
    cloud_dressed = ("The claude.ai cloud routine starts the claude-watcher every Friday from the "
                     "Desktop.")
    for sentence in (claude_bare, claude_ok, codex_silent, codex_ok, both_desktop, automation,
                     both_bare, module_silent, cloud_again, cloud_dressed):
        assert automation_claims(sentence), "not even read as a claim: %r" % sentence

    assert schedule_claim_offence(claude_ok, state_one) is None
    assert "who starts the rest" in (schedule_claim_offence(claude_bare, state_one) or ""), (
        "the watcher whose Friday task IS recorded may claim a bare weekly schedule while its "
        "second weekly run exists nowhere -- the half-truth DEC-0090 (3) created")
    assert "who starts the rest" in (schedule_claim_offence(codex_silent, state_one) or "")
    assert schedule_claim_offence(codex_ok, state_one) is None
    assert "codex-watcher" in (schedule_claim_offence(both_desktop, state_one) or "")
    assert "codex-watcher" in (schedule_claim_offence(automation, state_one) or ""), (
        "a Codex Automation promised for a routine the record does not hold passed the reader")
    assert "names none of" in (schedule_claim_offence(both_bare, state_one) or "")
    assert "who starts the rest" in (schedule_claim_offence(module_silent, state_one) or "")
    assert "not built" in (schedule_claim_offence(cloud_again, state_one) or "")
    assert "not built" in (schedule_claim_offence(cloud_dressed, state_one) or ""), (
        "the cloud routine passed because the sentence also named the Desktop -- the declaration "
        "lists it as not built, and that has to be read before anything else")
    # state two: every routine is recorded and shows its evening -- both may be named alone
    assert schedule_claim_offence(claude_bare, state_two) is None
    assert schedule_claim_offence(both_desktop, state_two) is None
    assert schedule_claim_offence(codex_silent, state_two) is None
    assert schedule_claim_offence(automation, state_two) is None
    assert schedule_claim_offence(module_silent, state_two) is None
    # ...and the cloud routine is an offence in EVERY state: it is the rejected alternative
    for sentence in (cloud_again, cloud_dressed):
        assert "not built" in (schedule_claim_offence(sentence, state_two) or ""), (
            "a sentence naming the cloud routine passed -- DEC-0089 rejected it: %r" % sentence)
    assert state_two["cloud_option"]["named_as"], "the declaration publishes no name for the option"


def test_the_claim_reader_reads_what_it_claims():
    """Both directions of `automation_claims`, on literal text: the shapes the shipped texts
    carried on 2026-09-05 are claims, so are the Desktop, Automation and cloud sentences DEC-0089
    and DEC-0090 made natural, a cadence alone is not, the disclaimer shapes exempt only a sentence
    that names the ABSENCE of a mechanism -- a claim with the word 'not' somewhere else stays a
    claim, and a LIMIT on the mechanism (a condition, an unknown state, 'nothing here can ask it')
    is a claim about it, not an exemption -- and a claim wrapped over two lines with its disclaimer
    on the second is one sentence."""
    for claiming in ("A scheduled **watcher duo** runs once a week and writes dated reports here.",
                     "Triggered by the weekly schedule (or manually).",
                     "# Runs on the weekly schedule, outside the change circle",
                     "runs automatically every Monday",
                     "a cron job starts both",
                     "the schedule is not optional",
                     "the routine does not start the QA gate itself, and is scheduled weekly",
                     "we cannot ask the user, and the watchers run on a weekly schedule",
                     "The claude-watcher runs every Friday at 20:00 through the Desktop app.",
                     "A claude.ai code routine starts both watchers weekly in a cloud sandbox.",
                     # the codex half's own mechanism, whose natural sentence carries no older word
                     "the codex-watcher is an Automation of the Codex app",
                     "a local app routine writes it every week",
                     # limits are claims about the mechanism, not exemptions (DEC-0089 (4))
                     "the Desktop task fires only while the app is open",
                     "a desktop scheduled task exists, and nothing here can ask it or count on it",
                     "the Desktop app starts both watchers, its state unknown",
                     "The duo is scheduled.\nIt is started by hand only in emergencies."):
        assert automation_claims(claiming), claiming
    for allowed in ("meant to run once a week -- the CLAUDE half",
                    "You are meant to run once a week and are READ-ONLY",
                    "Started by hand today (radar/README.md says how a run starts)",
                    "refuses any sentence that claims a schedule this repo does not build",
                    "there is no cron entry and no scheduled task",
                    "the session cron is session-only, so the routine does not start itself",
                    "a schedule is declared and the routine starts nothing on its own",
                    "line 3 said \"a scheduled watcher duo runs once a week\" while every run\n"
                    "had been started by hand.",
                    # THE NAMED LIMIT, not an endorsement: a cadence with the person removed and no
                    # mechanism word is exactly the shape this reader does not see -- carried as
                    # `BUG-0273` (H189) with its bound; the day the reader learns the shape this
                    # line moves to the list above and the hole closes with it
                    "The watcher duo runs once a week without a human."):
        assert not automation_claims(allowed), allowed


def test_the_starter_reader_reads_a_named_starter_and_nothing_else():
    """The other half of the invariant, and it is an enumeration, so both ends are measured.

    `STARTER_RX` decides whether a claiming sentence says WHO starts a run -- the question that
    matters for a run no recorded routine starts. A sentence that names nobody must not pass, and
    a sentence that names a starter in any of the shapes the shipped texts use must. The mutation
    this denies is the one that makes the whole clause vacuous: a pattern that matches everything
    (then the first list passes) or nothing (then the shipped texts cannot be written).
    """
    for names_a_starter in ("the schedule is the routine's; the lead runs it",
                            "a weekly cadence, started by the lead",
                            "run by a person when `--due` says so",
                            "the schedule lives in tools/radar_routine.py; you run it",
                            "scheduled weekly -- start it with --run codex-watcher",
                            "a cron-like cadence that somebody starts by hand"):
        assert STARTER_RX.search(names_a_starter), names_a_starter
    for names_nobody in ("a scheduled watcher duo runs once a week",
                         "the routine is scheduled weekly",
                         "runs automatically every Monday",
                         "tools/radar_routine.py declares a weekly schedule"):
        assert not STARTER_RX.search(names_nobody), names_nobody


def test_the_mechanism_reader_names_the_apps_and_not_the_watchers():
    """The clause that decides whether a claiming sentence NAMES a mechanism, from both ends.

    Derived from the declaration (`mechanism_names`), because a list here would have gone stale the
    day the codex half's Automation joined -- which is exactly what happened to the previous reader:
    it asked for the module stem or the word `desktop`, and "the Codex app Automation runs it every
    Monday" therefore counted as naming no mechanism at all, i.e. it was refused for the wrong
    reason and would have been accepted the moment somebody added `automation` beside `desktop`
    without noticing that `codex` names a WATCHER too.
    """
    described = mechanism_description()
    words = mechanism_names(described)
    assert {"radar_routine", "desktop", "automation"} <= words, sorted(words)
    assert not (set(described["runners"]) & words), (
        "a runner id counts as naming the mechanism, so a sentence about the codex-watcher would "
        "pass that clause for free: %s" % sorted(words))
    assert not (set(described["watchers"]) & words), sorted(words)


# A role NAME, as a word rather than as part of a path: `claude-watcher` in a sentence names the
# agent, `~/.claude/scheduled-tasks/radar-watcher/SKILL.md` names the folder a Desktop task was
# created in, which the app owns and nobody renames. The lookaround is what tells the two apart.
ROLE_NAME_RX = re.compile(r"(?<![\w./\\-])([a-z][a-z0-9]*-watcher)(?![\w./\\-])")


def duo_artifacts():
    """Every file that speaks FOR the duo: the guarded texts, each watcher's generated Codex
    overlay, the declaration module and the record it reads. Derived from the running module, so a
    third watcher's overlay joins the subject without anybody editing a list."""
    routine = routine_module("radar_routine_artifacts")
    return list(TEXTS) + [routine.OVERLAY % watcher for watcher in sorted(routine.WATCHERS)] + [
        "tools/radar_routine.py", "radar/routine.json"]


def test_no_artifact_of_the_duo_names_a_watcher_the_repo_does_not_define():
    """DEC-0090 (1): after the rename, `radar-watcher` is a name nothing answers to.

    THE RULE IS NOT "the string radar-watcher is gone" -- that would go stale the day the duo is
    renamed again, and it would refuse the Desktop task's FOLDER, which keeps its old name because
    the app owns it. The rule is that every `<x>-watcher` a duo artifact names AS A WORD has a role
    definition in `.claude/agents/`. RED on the tree before this round: five such names across the
    two definitions, both overlays and the README, none of which resolved after the rename.

    `ROLE_NAME_RX` is a reader with two ends, so both are stated: a name inside a path is not a
    role name, and a name standing on its own is.
    """
    routine = routine_module("radar_routine_names")
    assert ROLE_NAME_RX.findall("start `--run claude-watcher` now") == ["claude-watcher"]
    assert ROLE_NAME_RX.findall("~/.claude/scheduled-tasks/radar-watcher/SKILL.md") == []
    assert ROLE_NAME_RX.findall(".claude/agents/claude-watcher.md") == []
    offenders = {}
    for relative in duo_artifacts():
        for name in sorted(set(ROLE_NAME_RX.findall(read(relative)))):
            if name not in routine.WATCHERS:
                offenders.setdefault(relative, []).append(name)
    assert not offenders, (
        "these files name a watcher this repo has no definition for, so a reader and a run are "
        "sent at nothing: %s" % json.dumps(offenders, indent=2))
    for watcher in routine.WATCHERS:
        assert os.path.isfile(os.path.join(ROOT, (routine.DEFINITION % watcher).replace("/",
                                                                                        os.sep)))


def test_every_codex_overlay_is_the_one_its_claude_definition_generates():
    """DEC-0090 (2): the Codex overlay is GENERATED, and the shipped file has to be that output.

    WHY IT IS A TEST AND NOT A CONVENTION: these two files were hand-copied in 2026-07 with a blind
    Claude->Codex word substitution and shipped for two months telling a Codex run to read
    `platform.Codex.com/...` and to write `radar/<today>-AGENTS.md`. Nothing could go red, because
    nothing derived them from anything.

    The measurement is the whole file, byte for byte against `overlay_text`, plus the three things
    the generation exists for, asserted separately so a failure says WHICH one moved: the model is
    the ladder's row for the rung the definition pins (never a second spelling of `gpt-5.6-sol`),
    the effort stands under the key the ladder names for that provider, and the runner line is the
    ONE line that differs from the definition.
    """
    routine = routine_module("radar_routine_overlays")
    tiers_reader = load_kit_module("gen_provider_artifacts_for_overlays",
                                   os.path.join(ROOT, "team-kits", "gen_provider_artifacts.py"))
    tiers, aliases = tiers_reader.load_tiers()
    for watcher in sorted(routine.WATCHERS):
        generated = routine.overlay_text(watcher)
        # PARSED, not searched: what a Codex run reads is the TOML document, so the pins are asked
        # of a parser. `tomllib` is stdlib from 3.11; where it is absent the byte comparison below
        # still holds the whole file against the generator, which is the stronger half anyway.
        try:
            import tomllib
        except ImportError:                                         # pragma: no cover -- py<3.11
            tomllib = None
        if tomllib is not None:
            document = tomllib.loads(generated)
            assert document["name"] == watcher, document
            assert document["developer_instructions"].strip(), document
        assert read(routine.OVERLAY % watcher) == generated, (
            "%s is not what `python tools/radar_routine.py --write-overlays` produces from %s"
            % (routine.OVERLAY % watcher, routine.DEFINITION % watcher))
        definition = read(routine.DEFINITION % watcher)
        meta, body = tiers_reader.parse_frontmatter(definition)
        expected = tiers_reader.provider_model(meta["model"], "codex", tiers, aliases)
        assert expected != meta["model"], "the rung was not translated at all"
        assert 'model = "%s"' % expected in generated
        assert '%s = "%s"' % (tiers["codex"][tiers_reader.EFFORT_FIELD_KEY],
                              meta[tiers["claude"][tiers_reader.EFFORT_FIELD_KEY]]) in generated
        assert routine.runner_line(watcher, "codex") in generated
        assert routine.runner_line(watcher, "claude") in definition
        assert routine.runner_line(watcher, "claude") not in generated, (
            "the overlay still tells the run it is a claude run")
        assert len(routine.RUNNER_LINE_RX.findall(body)) == 1, (
            "%s states its runner more than once, so the generator rewrites one of two answers"
            % (routine.DEFINITION % watcher))


def test_a_pin_the_ladder_cannot_place_is_refused_before_an_overlay_is_written(tmp_path):
    """DEC-0076 lineage: a rung `model_tiers.yaml` has no row for costs the run, not a warning.

    Measured for real spawns in `docs/reviews/2026-09-02-model-pin-and-bom-measurement.md` -- the
    spawn dies with the model name it sent. So the generator refuses rather than writing an overlay
    pinning a model no provider has, and it refuses with the KIT's own sentence, which names the
    decision. Both directions: the retired `light` rung and a typo are refused, a missing effort is
    refused, and the rung the repo really pins goes through.
    """
    routine = routine_module("radar_routine_unplaceable")
    watcher = sorted(routine.WATCHERS)[0]
    source = read(routine.DEFINITION % watcher)
    target = tmp_path / (routine.DEFINITION % watcher)
    target.parent.mkdir(parents=True)
    for bad in ("light", "haiku", "opus-4-1-does-not-exist"):
        target.write_text(re.sub(r"(?m)^model: .*$", "model: %s" % bad, source), encoding="utf-8")
        with pytest.raises(SystemExit) as refused:
            routine.overlay_text(watcher, root=str(tmp_path))
        assert "DEC-0076" in str(refused.value) and bad in str(refused.value), bad
    target.write_text(re.sub(r"(?m)^effort: .*$", "", source), encoding="utf-8")
    with pytest.raises(SystemExit) as refused:
        routine.overlay_text(watcher, root=str(tmp_path))
    assert "effort" in str(refused.value)
    target.write_text(source, encoding="utf-8")
    assert routine.overlay_text(watcher, root=str(tmp_path)) == routine.overlay_text(watcher)


def test_the_cloud_option_says_it_is_not_built_and_its_prompt_stays_consistent():
    """DEC-0089 (2): the cloud routine is the REJECTED alternative -- the declaration keeps it as
    a documented option that says so, and nothing in `--describe` calls it the mechanism.

    The option's text is still measured for consistency, because a documented option whose prompt
    contradicts its own spec documents nothing: every duty it publishes appears in the prompt as a
    WHOLE LINE (the first cut fused two string literals without their newline), and the prompt does
    not send a run back to the repository for its instructions.
    """
    routine = routine_module("radar_routine_prompt")
    described = routine.description()
    option = described["cloud_option"]
    assert option["built"] is False and option["rejected_by"] == "DEC-0089", option
    assert "cloud" not in described["mechanism"].lower(), (
        "the declaration calls the cloud routine the mechanism: %s" % described["mechanism"])
    assert "Desktop" in described["mechanism"] and "Automation" in described["mechanism"]
    for watcher, prompt in option["prompts"].items():
        lines = [line.strip() for line in prompt.splitlines()]
        blob = " ".join(lines)
        assert option["remote"] in blob and option["base_branch"] in blob, watcher
        assert option["writes"][watcher] in blob, "the prompt does not name the one file it may write"
        assert "radar/decided.md" in blob and "outside" in blob, (
            "the prompt does not forbid what the option says it must: %s" % option["must_not_write"])
        assert routine.BRANCH_PATTERN.format(date="<YYYY-MM-DD>", watcher=watcher) in blob, watcher
        assert routine.PR_TITLE_PATTERN.format(watcher=watcher, date="<YYYY-MM-DD>") in blob
        assert "Do NOT merge" in blob, "the prompt lets a cloud run merge its own report"
        assert watcher in lines[0], "the prompt does not say which watcher it is"
        assert any(line.startswith("This prompt is complete on its own") for line in lines)
        numbered = [line for line in lines if re.match(r"^\d\.", line)]
        assert len(numbered) >= 8, (watcher, numbered)
        assert not any(re.search(r"\S {3,}\S", line) for line in lines), (
            "a line carries a run of blanks -- two string literals fused without their newline")


def test_the_routine_counts_a_run_per_watcher_and_runner_and_period():
    """The routine's own reader, on a directory it is handed rather than on today's `radar/`.

    `due()` answers WHICH of the four routines owes a run, so it has to tell them apart by BOTH
    names the report carries and it has to count per ISO week. Two mutations are denied here: the
    cheap one, counting any dated report as any watcher's run -- then one watcher's report silently
    clears the other's duty; and the one DEC-0090 (3) added, counting per watcher only -- then a
    Claude run of the claude-watcher clears the duty of its Codex run, and the second model family
    never gets asked.

    THE OLD TWO-PART NAMES have to stay countable (every report written before the runner suffix): a `<date>-claude.md` counts as a run of the claude-watcher BY CLAUDE, which is the
    convention DEC-0090 (3) asks for. The undated pair at the start of `radar/` (2026-07-03,
    2026-07-06, before the split into two watchers) is the third case: they are runs of the
    directory and of no named watcher, so they must clear nobody.
    """
    routine = routine_module("radar_routine_due")
    monday = datetime.date(2026, 9, 7)                      # a Monday: 2026-W37
    every = {routine.routine_id(watcher, runner)
             for watcher in routine.WATCHERS for runner in routine.RUNNERS}

    def owed(names, today=monday):
        original = routine.RADAR
        try:
            routine.RADAR = str(names)
            return routine.due(today)
        finally:
            routine.RADAR = original

    with tempfile.TemporaryDirectory() as directory:
        def place(*files):
            for name in os.listdir(directory):
                os.remove(os.path.join(directory, name))
            for name in files:
                io.open(os.path.join(directory, name), "w", encoding="utf-8").close()

        place()
        assert set(owed(directory)) == every, "an empty radar/ owes all four runs"
        place("2026-09-07-claude-by-claude.md")
        assert set(owed(directory)) == every - {"claude-watcher-by-claude"}, (
            "one run cleared more than its own routine")
        place("2026-09-07-claude-by-claude.md", "2026-09-07-claude-by-codex.md",
              "2026-09-07-codex-by-claude.md", "2026-09-07-codex-by-codex.md")
        assert owed(directory) == {}, "all four ran this week and something is still owed"
        place("2026-08-31-claude-by-claude.md", "2026-08-31-codex-by-codex.md")   # the week before
        assert set(owed(directory)) == every, "last week's runs cleared this week"
        # the legacy two-part names: the watcher's own provider is the runner they count for
        place("2026-09-07-claude.md", "2026-09-07-codex.md")
        assert set(owed(directory)) == {"claude-watcher-by-codex", "codex-watcher-by-claude"}, (
            "a two-part name no longer counts as a run by the watcher's own provider, so every "
            "report written before DEC-0090 (3) stopped being countable")
        place("2026-07-03.md", "2026-07-06.md")                        # the undated-suffix pair
        assert set(owed(directory)) == every, (
            "a report with no watcher suffix cleared a named watcher's duty")


def test_the_report_name_is_spelled_in_exactly_one_place():
    """`report_name` is the only speller, and the reader is its inverse (DEC-0090 (3)).

    A name that `runs()` cannot read back into the pair `report_name` wrote it for is a routine that
    can never be counted -- which is how a watcher would silently owe a run forever. So the two are
    measured against each other for every routine of the plan, on a directory this test writes.

    ONE FILE AT A TIME, and that is the whole difference between this test and the one it replaced:
    the first cut placed all four names and compared the SET of pairs it read back, which is
    symmetric under swapping the two halves of the pattern -- the mutation that writes
    `<date>-<runner>-by-<suffix>.md` left it green (measured 2026-09-11, row R11 of the round's
    red-first rig). A pair is only meaningful against the routine it was written for.
    """
    routine = routine_module("radar_routine_names_roundtrip")
    written = datetime.date(2026, 9, 11)
    with tempfile.TemporaryDirectory() as directory:
        for entry in routine.routine_plan().values():
            relative = routine.report_name(entry["watcher"], entry["runner"], written.isoformat())
            assert relative.startswith("radar/"), relative
            path = os.path.join(directory, os.path.basename(relative))
            io.open(path, "w", encoding="utf-8").close()
            assert routine.runs(directory) == [
                (written, routine.WATCHERS[entry["watcher"]]["suffix"], entry["runner"])], (
                "%s reads back as something other than the routine it was written for" % relative)
            os.remove(path)


def test_a_second_run_in_the_same_period_is_refused_unless_it_is_asked_for():
    """`--run` asks `--due` first, and says why when it refuses (TSK-0130 round-2 finding R2-5).

    MEASURED by the verifier: two `--run codex-watcher` on one day both started the watcher -- about
    four minutes and a hundred thousand tokens each -- and the second reported `new_reports: []`,
    having rewritten the same dated file. The routine already knew: `--due` said nobody owed a run.
    So the refusal comes BEFORE the watcher is started, and `--force` is the way past it.

    ASKED OF THIS RUN'S ROUTINE since DEC-0090 (3): the report that already exists is the one a
    `SESSION_RUNNER` run would rewrite, so a report of the SAME watcher by the OTHER provider must
    not refuse the run -- the second half below, which the per-watcher question got wrong.

    Run as a PROCESS against a radar directory this test controls, so nothing here depends on which
    reports the repository happens to hold today. `--force` is measured by its EFFECT on the
    decision, not by starting a real watcher: the run is allowed through to the point where it
    would spawn, which the recorder below stands in for.
    """
    routine = routine_module("radar_routine_force")
    with tempfile.TemporaryDirectory() as directory:
        io.open(os.path.join(directory, "2026-09-07-codex-by-claude.md"), "w",
                encoding="utf-8").close()
        started = []
        monkey = pytest.MonkeyPatch()
        try:
            monkey.setattr(routine, "RADAR", directory)
            monkey.setattr(routine, "ROUTINE_RECORD", os.path.join(directory, "none.json"))
            monkey.setattr(routine, "run_watcher",
                           lambda name, **kw: started.append(name) or _FakeRun())
            monkey.setattr(routine.datetime, "date", _FixedDate)
            refused = routine.main(["--run", "codex-watcher"])
            assert refused == 1 and not started, (
                "a second run in the same ISO week started the watcher again")
            forced = routine.main(["--run", "codex-watcher", "--force"])
            assert started == ["codex-watcher"], "--force did not let the run through"
            assert forced == 0
            # ...and the watcher that has NOT run this period is never refused
            routine.main(["--run", "claude-watcher"])
            assert started == ["codex-watcher", "claude-watcher"]
            # ...and the OTHER provider's report of the same watcher is a different duty
            io.open(os.path.join(directory, "2026-09-07-claude-by-codex.md"), "w",
                    encoding="utf-8").close()
            started.clear()
            routine.main(["--run", "claude-watcher"])
            assert started == ["claude-watcher"], (
                "a Codex run of the claude-watcher refused its Claude run for the same week")
        finally:
            monkey.undo()


def test_no_model_is_forced_on_a_hand_started_run():
    """`--run` must not override the pin DEC-0090 (2) put in the definition.

    The flag used to default to `sonnet` -- the rung the user replaced -- so every hand-started run
    would have quietly run one rung below what the definition says, and the pin would have been true
    only of the scheduled runs. Measured on the ARGUMENT LIST the module builds, with the spawn
    replaced: no `--model` unless one is asked for, and the asked-for one passed through.
    """
    routine = routine_module("radar_routine_model_flag")
    seen = {}
    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(routine.subprocess, "run",
                       lambda argv, **kw: seen.setdefault("argv", argv) and None or _FakeRun())
        routine.run_watcher("claude-watcher")
        assert "--model" not in seen["argv"], seen["argv"]
        assert "--agent" in seen["argv"] and "claude-watcher" in seen["argv"]
        assert routine.SESSION_RUNNER in seen["argv"][2], (
            "the prompt does not tell the run which runner it is, so it cannot name its report")
        seen.clear()
        routine.run_watcher("claude-watcher", model="sonnet")
        assert seen["argv"][seen["argv"].index("--model") + 1] == "sonnet"
    finally:
        monkey.undo()
    with pytest.raises(SystemExit):
        routine.run_watcher("not-a-watcher")


class _FixedDate(datetime.date):
    """`date.today()` pinned into the ISO week of the report the test above places."""

    @classmethod
    def today(cls):
        return cls(2026, 9, 7)


class _FakeRun:
    """What `run_watcher` returns -- enough of a CompletedProcess for `--run` to report on."""

    returncode = 0
    stdout = '{"result": "pretend report"}'
    stderr = ""


WATCHER_EXEMPTION_RX = re.compile(r"(?m)^harness_item:\s*none\s*$")


def test_the_texts_this_reads_are_the_ones_that_describe_the_watchers():
    """`TEXTS` is an enumeration, so both ends are measured against the tracked tree: every WATCHER
    definition and the radar README are in it, and every entry exists. A watcher is the one kind
    of role that declares `harness_item: none` -- the spawn gate's exemption for a role outside the
    change circle that writes only into `radar/` (the reason stands beside the line in both
    definitions) -- and names `radar/`. A third watcher joins the subject or turns this red; a role
    that merely mentions the directory (the lead names it as a writable path) does not."""
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60)
    assert tracked.returncode == 0, tracked.stderr
    watchers = []
    for relative in (path for path in tracked.stdout.split("\0") if under_an_agents_directory(path)):
        try:
            text = read(relative)
        except (OSError, UnicodeDecodeError):
            continue
        if WATCHER_EXEMPTION_RX.search(text) and "radar/" in text:
            watchers.append(relative)
    assert len(watchers) >= 2, "fewer than two watcher definitions found: %s" % watchers
    assert set(watchers) | {RADAR_README} == set(TEXTS), (
        "the subject moved: watchers %s, read %s" % (sorted(watchers), sorted(TEXTS)))
    for relative in TEXTS:
        assert os.path.isfile(os.path.join(ROOT, relative.replace("/", os.sep))), relative
    routine = routine_module("radar_routine_texts")
    assert {os.path.basename(path).rsplit(".", 1)[0] for path in watchers} == set(routine.WATCHERS)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
