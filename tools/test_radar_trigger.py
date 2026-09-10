#!/usr/bin/env python3
"""A claim of automation about the radar watchers is a mechanism this repo can measure, never a
sentence (PR-0010 AC-1, invariant 1 of that goal).

MEASURED 2026-09-05 before this existed: `radar/README.md` line 3 said "A scheduled watcher duo
runs once a week", both watcher definitions said "Triggered by the weekly schedule", and nothing IN
THIS REPOSITORY started a run. What started the radar half was outside it and went unread for a
day: a Claude DESKTOP scheduled task on the maintainer's host, whose Friday-evening reports had been
in `radar/` since 2026-07-17 (DEC-0089, correcting DEC-0085). So this module reads the three texts
that describe how a run starts and refuses any AUTOMATION claim the declaration does not back --
PER WATCHER, because the two halves are in different states: the radar half is recorded and shows
its cadence, the codex half has no task yet. HOW MANY reports there were is deliberately not
written here: the number grows every week, and `tools/radar_routine.py --describe` counts it.

WHAT COUNTS AS A CLAIM (`automation_claims`): a SENTENCE carrying a form of "schedule",
"automatic", "cron", the Task Scheduler, a weekday, the Desktop task/routine/app, or the rejected
cloud routine by name -- unless the same sentence names the ABSENCE of a mechanism (`DISCLAIMER_RX`).
The word half is deliberately coarse in one direction: a sentence that uses the word about
something else is refused too, and the text answers by rewording. A cadence on its own ("once a
week", "weekly") is an intent and not a claim of a mechanism. A LIMIT is not a disclaimer: "fires
only while the app is open" says how the mechanism runs and is judged as a claim about it
(DEC-0089 (4)) -- the two spellings that used to be read as exemptions are in
`test_the_claim_reader_reads_what_it_claims` as claims.

WHAT BACKS A CLAIM is `tools/radar_routine.py --describe`, asked as a PROCESS, and its
`starts_itself` is a map per watcher DERIVED from the lead's record (`radar/routine.json`) and the
cadence the reports show. The rule lives in `schedule_claim_offence`, one reader for the shipped
texts and the synthetic ones:

  * a claiming sentence names the mechanism -- the module or the Desktop task -- or it is refused;
  * the watchers it is about are the ones it names, or both when it names none; if every one of
    them is recorded and shows its cadence, naming the mechanism is enough;
  * otherwise the sentence has to say WHO starts a run (`STARTER_RX`), because for that watcher
    nothing does by itself.

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
TEXTS = ("radar/README.md", ".claude/agents/radar-watcher.md", ".claude/agents/codex-watcher.md")
RADAR_README = TEXTS[0]
WATCHER_ROLES = ("radar-watcher", "codex-watcher")
MECHANISM = os.path.join(ROOT, "tools", "radar_routine.py")
# WHO STARTS A RUN, as the shapes a true sentence can take for a watcher nothing starts by itself.
# It is an enumeration of wordings and it is guarded from both ends by
# `test_the_starter_reader_reads_a_named_starter_and_nothing_else`: a sentence with none of them is
# refused, and each one is shown to admit a sentence that really does name a starter.
STARTER_RX = re.compile(
    r"\brun by\b|\bstarted by\b|\bstart(?:s|ed)? it\b|\byou (?:run|start)\b|\bthe lead\b|"
    r"\bby hand\b|\bwhen (?:you|the lead|somebody)\b|--run\b",
    re.IGNORECASE)
# The words that make a sentence a claim about a mechanism. The Desktop app and the cloud routine
# are named here because the natural true sentence about either carries none of the older words
# ("the Desktop task starts the radar-watcher every Friday") -- measured 2026-09-06 for the cloud
# shape, whose sentence the previous reader looked straight past.
AUTOMATION_CLAIM_RX = re.compile(
    r"\bschedul|\bautomatic|\bcron\b|task scheduler|aufgabenplanung"
    r"|\bdesktop (?:task|routine|app)\b|\bclaude\.ai\b|\bcloud routine\b|\bremotetrigger\b"
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


def test_no_text_claims_a_schedule_the_repo_does_not_build():
    """The invariant, on the shipped texts, in whatever state the record is in.

    NO mechanism shipped -> no text may claim one. A mechanism shipped -> every claiming sentence
    is judged by `schedule_claim_offence` against the declaration's per-watcher answer.

    RED against the texts of b7f282e (three files, five claiming lines); RED again the day a text
    calls the rejected cloud routine the mechanism, or says the codex half is scheduled while no
    task with a measured cadence is recorded for it -- the mutation the generation-5 merge measured.
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
        names it publishes) is refused whatever else it says -- naming the Desktop task beside it
        does not rescue it;
      * the sentence names the mechanism -- the module, or the Desktop task -- so a reader can go
        and see what it does; a sentence naming neither (a bare "schedule") is refused;
      * the watchers it speaks about are the ones it names, or both when it names none; for every
        one of them the declaration's `starts_itself` says whether a recorded task with a measured
        cadence starts it;
      * where every named watcher is started by such a task, naming the mechanism is enough; where
        one is not, the sentence has to say who starts a run for it, because nothing does by itself.
    """
    # A MECHANISM THE DECLARATION LISTS AS NOT BUILT is refused first and whatever else the
    # sentence says: naming the Desktop task in the same breath did not make "the claude.ai cloud
    # routine starts the radar-watcher every Friday from the Desktop" true, and a reader that only
    # asked for the mechanism's name let it pass (verify round 1 of TSK-0133, B3). The names are
    # the declaration's own (`cloud_option.named_as`), not a list kept here.
    for key, option in described.items():
        if isinstance(option, dict) and option.get("built") is False:
            named = [word for word in option.get("named_as", ())
                     if word.lower() in sentence.lower()]
            if named:
                return ("names %s (%r), which the declaration lists as not built"
                        % (key, named[0]))
    stem = os.path.splitext(os.path.basename(MECHANISM))[0]
    if stem not in sentence and not re.search(r"\bdesktop\b", sentence, re.IGNORECASE):
        return "names neither %s nor the Desktop task as the mechanism" % stem
    named = [watcher for watcher in WATCHER_ROLES if watcher in sentence] or list(WATCHER_ROLES)
    silent = [watcher for watcher in named if not described["starts_itself"].get(watcher)]
    if not silent:
        return None
    return None if STARTER_RX.search(sentence) else (
        "no recorded task with a measured cadence starts %s, so the sentence has to say who does"
        % ", ".join(silent))


def routine_module(name="radar_routine_under_test"):
    return load_kit_module(name, os.path.join(ROOT, "tools", "radar_routine.py"))


def a_record_naming(directory, name="routine.json", entries=None, **overrides):
    """A `radar/routine.json` in the shape the declaration publishes, written to `directory`.

    One well-formed entry for the radar half by default; `overrides` bend that entry, `entries`
    replaces the list outright.
    """
    entry = {"kind": "desktop_task", "watcher": "radar-watcher",
             "path": "~/.claude/scheduled-tasks/radar-watcher/SKILL.md",
             "schedule": {"day": "friday", "time_local": "~20:00",
                          "as_told_by": "the user, 2026-09-06", "source": "DEC-0089"},
             "first_measured_report": "2026-07-17", "last_measured_report": "2026-08-28",
             "recorded": "2026-09-06"}
    entry.update(overrides)
    path = os.path.join(directory, name)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"desktop_tasks": [entry] if entries is None else entries,
                   "recorded_by": "a test"}, handle)
    return path


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
FRIDAYS = ("2026-07-17-claude.md", "2026-07-24-claude.md")
SATURDAYS = ("2026-09-05-codex.md", "2026-09-12-codex.md")


def test_the_self_start_reader_answers_off_the_record_and_the_reports():
    """`starts_itself` is DERIVED per watcher from two things and needs both (DEC-0089 (3)).

    The field decides how far every text in `TEXTS` may go, so a constant there would be a claim
    nothing checks -- and it WAS one until 2026-09-06, when the mutation that flipped it stayed
    green. It answers True for a watcher whose record entry is well-formed AND whose reports show
    the recorded weekday at least `CADENCE_EVIDENCE_MIN` times, and False for every way short of
    that: no record, an unreadable one, an entry of another kind, an unknown watcher, no path, a
    day that is not a weekday, too few reports on the day, reports on other days, and a task merely
    MENTIONED in some other field. All of them are the fail-closed direction -- a half-written
    record or a run somebody started by hand never makes a sentence truer than the mechanism.
    """
    routine = routine_module("radar_routine_self_start")
    with tempfile.TemporaryDirectory() as directory:
        radar = a_radar_dir_with(directory, *FRIDAYS)
        live = a_record_naming(directory)
        assert routine.starts_itself(live, radar) == {"radar-watcher": True, "codex-watcher": False}
        assert routine.starts_itself(os.path.join(directory, "no-such-file.json"), radar) == {
            "radar-watcher": False, "codex-watcher": False}
        broken = os.path.join(directory, "broken.json")
        with io.open(broken, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("{not json")
        assert not any(routine.starts_itself(broken, radar).values())
        # every way a recorded entry fails to be a desktop task this routine can count
        for label, overrides in (("another kind", {"kind": "cloud_trigger"}),
                                 ("unknown watcher", {"watcher": "not-a-watcher"}),
                                 ("no path", {"path": "  "}),
                                 ("not a weekday", {"schedule": {"day": "weekly"}}),
                                 ("no schedule", {"schedule": None})):
            half = a_record_naming(directory, name="half.json", **overrides)
            assert not any(routine.starts_itself(half, radar).values()), label
        for entry in ("a string where an entry should be", 42):
            odd = os.path.join(directory, "odd.json")
            with io.open(odd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump({"desktop_tasks": [entry]}, handle)
            assert not any(routine.starts_itself(odd, radar).values()), entry
        # ...and NO string search: a record that merely MENTIONS a task in another field is not one
        mention = os.path.join(directory, "mention.json")
        with io.open(mention, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"note": "kind desktop_task, watcher radar-watcher, friday, path set",
                       "desktop_tasks": []}, handle)
        assert not any(routine.starts_itself(mention, radar).values())
        # THE SECOND HALF: the record alone is a sentence; the reports have to show the weekday
        one_friday = a_radar_dir_with(directory, FRIDAYS[0])
        assert routine.starts_itself(live, one_friday)["radar-watcher"] is False, (
            "one report on the weekday counted as a cadence -- a hand-started run can produce one")
        other_days = a_radar_dir_with(directory, "2026-07-15-claude.md", "2026-08-01-claude.md")
        assert routine.starts_itself(live, other_days)["radar-watcher"] is False
        wrong_suffix = a_radar_dir_with(directory, "2026-07-17-codex.md", "2026-07-24-codex.md")
        assert routine.starts_itself(live, wrong_suffix)["radar-watcher"] is False, (
            "the other watcher's reports counted as this watcher's cadence")
        undated = a_radar_dir_with(directory, "2026-07-03.md", "2026-07-10.md")     # Fridays, no suffix
        assert routine.starts_itself(live, undated)["radar-watcher"] is False, (
            "a report with no watcher suffix counted as a named watcher's run")
        # ...and the codex half turns True the same way and no other
        both = a_record_naming(directory, name="both.json", entries=[
            json.load(io.open(live, encoding="utf-8"))["desktop_tasks"][0],
            dict(json.load(io.open(live, encoding="utf-8"))["desktop_tasks"][0],
                 watcher="codex-watcher", path="~/.claude/scheduled-tasks/codex-watcher/SKILL.md",
                 schedule={"day": "saturday", "time_local": "~20:00"})])
        assert routine.starts_itself(both, a_radar_dir_with(directory, *FRIDAYS, *SATURDAYS)) == {
            "radar-watcher": True, "codex-watcher": True}
        assert routine.starts_itself(both, a_radar_dir_with(directory, *FRIDAYS, SATURDAYS[0])) == {
            "radar-watcher": True, "codex-watcher": False}
    # ...and the repository's own answer, which is what the texts are held against today: the radar
    # half is recorded (DEC-0089) and shows its Fridays, the codex half has no task yet. The day the
    # lead records that task and its second Saturday report lands, this line is the one that says
    # the texts may now say so.
    assert routine.starts_itself() == {"radar-watcher": True, "codex-watcher": False}, (
        "radar/routine.json or the reports moved -- re-read the texts in %s against the new answer"
        % (TEXTS,))


def test_the_claim_rule_follows_the_record_per_watcher(tmp_path, monkeypatch):
    """The invariant has a state PER WATCHER (DEC-0089) and both are walked here, not just today's.

    STATE ONE, the one the repository is in: the radar half is recorded and shows its cadence, the
    codex half is not -- so a sentence about the radar half may say its Desktop task starts it, a
    sentence about the codex half (or about both) has to say who starts a run. STATE TWO: the lead
    has recorded the codex task and it has run twice -- a sentence about both may now name the
    mechanism alone. In EVERY state a sentence that calls the rejected cloud routine the mechanism
    is an offence, because it names nothing the declaration knows.

    Both states are measured on sentences THIS TEST WRITES, judged by `schedule_claim_offence`, the
    same reader the shipped texts go through.
    """
    routine = routine_module("radar_routine_two_states")
    monkeypatch.setattr(routine, "RADAR", a_radar_dir_with(str(tmp_path), *FRIDAYS, *SATURDAYS))
    monkeypatch.setattr(routine, "ROUTINE_RECORD", a_record_naming(str(tmp_path)))
    state_one = routine.description()
    assert state_one["starts_itself"] == {"radar-watcher": True, "codex-watcher": False}
    assert "Desktop" in state_one["started_by"]["radar-watcher"]
    assert "--run codex-watcher" in state_one["started_by"]["codex-watcher"]
    radar_entry = routine.desktop_tasks()[0]
    monkeypatch.setattr(routine, "ROUTINE_RECORD", a_record_naming(str(tmp_path), name="two.json", entries=[
        radar_entry, dict(radar_entry, watcher="codex-watcher",
                          path="~/.claude/scheduled-tasks/codex-watcher/SKILL.md",
                          schedule={"day": "saturday", "time_local": "~20:00"})]))
    state_two = routine.description()
    assert state_two["starts_itself"] == {"radar-watcher": True, "codex-watcher": True}

    radar_ok = ("The radar-watcher is started every Friday evening by a Claude Desktop scheduled "
                "task on the maintainer's host (recorded in radar/routine.json).")
    codex_silent = "The codex-watcher is started every Saturday by a Claude Desktop scheduled task."
    codex_ok = ("The codex-watcher has no recorded Desktop task yet; the lead starts it with "
                "`--run codex-watcher` when `--due` names it.")
    both_desktop = "Both watchers are started weekly by Claude Desktop scheduled tasks."
    both_bare = "The watchers run on a weekly schedule."
    module_silent = "tools/radar_routine.py declares a weekly schedule."
    cloud_again = ("A claude.ai code routine starts both watchers weekly in a cloud sandbox and "
                   "returns each report as a pull request.")
    # the verifier's sentence (TSK-0133 round 1, B3): the not-built mechanism dressed in the
    # built one's name, about the watcher whose task IS recorded
    cloud_dressed = ("The claude.ai cloud routine starts the radar-watcher every Friday from the "
                     "Desktop.")
    for sentence in (radar_ok, codex_silent, codex_ok, both_desktop, both_bare, module_silent,
                     cloud_again, cloud_dressed):
        assert automation_claims(sentence), "not even read as a claim: %r" % sentence

    assert schedule_claim_offence(radar_ok, state_one) is None
    assert "who does" in (schedule_claim_offence(codex_silent, state_one) or "")
    assert schedule_claim_offence(codex_ok, state_one) is None
    assert "codex-watcher" in (schedule_claim_offence(both_desktop, state_one) or "")
    assert "names neither" in (schedule_claim_offence(both_bare, state_one) or "")
    assert "who does" in (schedule_claim_offence(module_silent, state_one) or "")
    assert "not built" in (schedule_claim_offence(cloud_again, state_one) or "")
    assert "not built" in (schedule_claim_offence(cloud_dressed, state_one) or ""), (
        "the cloud routine passed because the sentence also named the Desktop -- the declaration "
        "lists it as not built, and that has to be read before anything else")
    # state two: the codex half is recorded and shows its Saturdays -- both may be named alone
    assert schedule_claim_offence(both_desktop, state_two) is None
    assert schedule_claim_offence(codex_silent, state_two) is None
    assert schedule_claim_offence(module_silent, state_two) is None
    # ...and the cloud routine is an offence in EVERY state: it is the rejected alternative
    for sentence in (cloud_again, cloud_dressed):
        assert "not built" in (schedule_claim_offence(sentence, state_two) or ""), (
            "a sentence naming the cloud routine passed -- DEC-0089 rejected it: %r" % sentence)
    assert state_two["cloud_option"]["named_as"], "the declaration publishes no name for the option"


def test_the_claim_reader_reads_what_it_claims():
    """Both directions of `automation_claims`, on literal text: the shapes the shipped texts
    carried on 2026-09-05 are claims, so are the Desktop and cloud sentences DEC-0089 made natural,
    a cadence alone is not, the disclaimer shapes exempt only a sentence that names the ABSENCE of
    a mechanism -- a claim with the word 'not' somewhere else stays a claim, and a LIMIT on the
    mechanism (a condition, an unknown state, 'nothing here can ask it') is a claim about it, not an
    exemption -- and a claim wrapped over two lines with its disclaimer on the second is one
    sentence."""
    for claiming in ("A scheduled **watcher duo** runs once a week and writes dated reports here.",
                     "Triggered by the weekly schedule (or manually).",
                     "# Runs on the weekly schedule, outside the change circle",
                     "runs automatically every Monday",
                     "a cron job starts both",
                     "the schedule is not optional",
                     "the routine does not start the QA gate itself, and is scheduled weekly",
                     "we cannot ask the user, and the watchers run on a weekly schedule",
                     "The radar-watcher runs every Friday at 20:00 through the Desktop app.",
                     "A claude.ai code routine starts both watchers weekly in a cloud sandbox.",
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
    matters for a watcher no recorded task starts. A sentence that names nobody must not pass, and
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
    assert "Desktop" in described["mechanism"] and "cloud" not in described["mechanism"].lower(), (
        "the declaration calls the cloud routine the mechanism: %s" % described["mechanism"])
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


def test_the_routine_counts_a_run_per_watcher_and_per_period():
    """The routine's own reader, on a directory it is handed rather than on today's `radar/`.

    `due()` answers WHICH watcher owes a run, so it has to tell the two apart by the suffix their
    dated reports carry and it has to count per ISO week. The mutation this denies is the cheap one:
    counting any dated report as any watcher's run -- then one watcher's report silently clears the
    other's duty, which is exactly the blindness the whole module exists against.

    The undated pair at the start of `radar/` (2026-07-03, 2026-07-06, before the split into two
    watchers) is the second half: they are runs of the directory and of no named watcher, so they
    must clear nobody.
    """
    routine = load_kit_module("radar_routine_under_test", os.path.join(ROOT, "tools",
                                                                      "radar_routine.py"))
    monday = datetime.date(2026, 9, 7)                      # a Monday: 2026-W37

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
        assert set(owed(directory)) == set(WATCHER_ROLES), "an empty radar/ owes both runs"
        place("2026-09-07-claude.md")
        assert set(owed(directory)) == {"codex-watcher"}, "a claude report cleared the codex duty"
        place("2026-09-07-claude.md", "2026-09-07-codex.md")
        assert owed(directory) == {}, "both ran this week and something is still owed"
        place("2026-08-31-claude.md", "2026-08-31-codex.md")           # the week before
        assert set(owed(directory)) == set(WATCHER_ROLES), "last week's runs cleared this week"
        place("2026-07-03.md", "2026-07-06.md")                        # the undated-suffix pair
        assert set(owed(directory)) == set(WATCHER_ROLES), (
            "a report with no watcher suffix cleared a named watcher's duty")


def test_a_second_run_in_the_same_period_is_refused_unless_it_is_asked_for():
    """`--run` asks `--due` first, and says why when it refuses (TSK-0130 round-2 finding R2-5).

    MEASURED by the verifier: two `--run codex-watcher` on one day both started the watcher -- about
    four minutes and a hundred thousand tokens each -- and the second reported `new_reports: []`,
    having rewritten the same dated file. The routine already knew: `--due` said nobody owed a run.
    So the refusal comes BEFORE the watcher is started, and `--force` is the way past it.

    Run as a PROCESS against a radar directory this test controls, so nothing here depends on which
    reports the repository happens to hold today. `--force` is measured by its EFFECT on the
    decision, not by starting a real watcher: the run is allowed through to the point where it
    would spawn, which the recorder below stands in for.
    """
    routine = routine_module("radar_routine_force")
    with tempfile.TemporaryDirectory() as directory:
        io.open(os.path.join(directory, "2026-09-07-codex.md"), "w", encoding="utf-8").close()
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
            routine.main(["--run", "radar-watcher"])
            assert started == ["codex-watcher", "radar-watcher"]
        finally:
            monkey.undo()


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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
