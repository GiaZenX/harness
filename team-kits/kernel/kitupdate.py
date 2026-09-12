"""Updating the KIT an installed project runs -- and stopping the session that ran the update.

THE FLOW THIS RESTORES (FR-0006, whose own decision record this store no longer holds -- it is
the canonical item BUG-0020 deleted). V1 told the lead "on the user's OK, run the scaffold".
V2 turned that into "ASK THE USER TO RUN it -- you cannot run either yourself", which was a SIDE
EFFECT of `gate_write_scope` refusing every write-capable command line that names the enforcement
layer, not a decision about the update flow. Measured 2026-08-16 against a project scaffolded
OUTSIDE this repo at an older stamp: both installer spellings are rc 2 at that gate, and the
SessionStart briefing handed the lead exactly that sentence. That is the shape of the preset dead
end BUG-0041 closed, and it is closed the same way -- the KERNEL runs the kit's own installer, on
the user's minted approval, and nothing about the gate's permission changes.

WHY IT RUNS THE KIT'S OWN INSTALLER, and why a kit update may use it where a preset change may
not: `kernel.presets` argues the first half (a scaffold is the ownership manifest, the backup, the
rollback, the symlink pre-flight, the tier-alias rewrite, the model re-stamp, the provider
artifacts and the trust record -- a second implementation would be a second answer to "what is
installed"). Its `assert_installable` then REFUSES a scaffold against a staging that has moved on,
because that would be a kit update wearing a preset change's clothes. This module is that refused
operation, made its own step with its own user decision -- which is what that refusal's remedy
already told the reader to do.

THE RESTART IS PART OF THE COMMAND, not advice, and that is the half V1 lacked. What changes
under a running session is measured rather than assumed (2026-08-16, real scaffold over a live
project): `.claude/hooks` and `.claude/kernel` are the new kit's from the moment the installer
finishes -- the provider re-reads a hook FILE on every call -- while the REGISTRATION in
`settings.json`, the agent set and the session agent are what the session started with. The
process running this command has its own kernel deleted and re-copied underneath it (measured:
`.claude/kernel/hashing.py` absent for 5 ms, 1.58 s into a 3.4 s run), so every module a failure
branch here needs is imported at module scope -- an import AFTER the installer starts is an import
out of a tree the installer is replacing. `.claude/HANDOVER_PENDING` therefore has to exist when
this command returns, whatever happened to the installer, and `ensure_restart_is_forced` is what
makes that true by construction rather than by the installer having got that far.

WHO READS THAT MARKER, named because a marker nothing reads is a comment in file form: the global
`~/.claude/hooks/handover_guard.py` refuses spawns, product-code writes and further work-engine
calls while it exists, and `gate_dispatch` refuses a specialist spawn on it in every kit -- the
second one so the stop does not depend on a user-global installation the project cannot see.
Nothing else reads it: `gate_write_scope`, `gate_git` and the rest are unaffected, and this module
claims no more than that (`tools/test_kitupdate.py::test_the_marker_this_command_leaves_really_
stops_the_session`).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

from . import approvals, presets, references, trays
from .hashing import BundleSourceMissing, hook_bundle_hash, kit_hash, modified_bundle_files
from .state import ProjectState, StateError

# The APR kind that authorises this operation, and the command that consumes it. One name, three
# readers: the vocabulary, the manifest builder and the refusals below.
KIND = "kit_update"
COMMAND = "update-kit"

# WHERE THE TWO RELEASES STATE THEIR IDENTITY. Both files are `kernel.hashing`'s doing -- the
# staged one is what `tools/bump_kit_version.py` stamps, the installed one is the copy the scaffold
# takes of it -- so the same reader answers both.
INSTALLED_VERSION_FILE = presets.KIT_VERSION_FILE       # .claude/kit_version
STAGED_VERSION_FILE = presets.STAGED_VERSION_FILE       # VERSION
# What `.claude/kit_update_pending.repo` is: the repo templates a scaffold found DIVERGED and kept.
# Reported after a run rather than acted on -- merging them is the lead's work, and the session
# briefing nags until the file is gone.
PENDING_PREFIX = os.path.join(".claude", "kit_update_pending.")
PENDING_TEMPLATES = PENDING_PREFIX + "repo"

# THE TWO PENDING LISTS AN INSTALL CAN LEAVE, and where each entry's kit template lives -- so no
# reader composes that path for itself. An entry names a file relative to `project` (repo root for
# the scaffold's list, the state directory for `init_project_memory`'s), and the template it was
# compared against sits at `<kit>/templates/<template>/<entry>`.
PENDING_LISTS = {
    "repo": {"template": "repo", "project": ""},
    "memory": {"template": trays.STATE_DIRNAME, "project": trays.STATE_DIRNAME},
}

# THE MARKERS A SESSION START CONSUMES, which is the property rather than a list of file names: an
# installer writes one, a SessionStart hook removes it, so its presence proves that no session has
# started since the last install. That makes it the exact definition of "this project is waiting
# for a restart, not for another update" -- and running a second installer over it would destroy
# the first one's announcement (the scaffold's own "never overwrite an unconsumed marker" rule).
# Each entry names the consumer that makes the property true, and both are measured as processes
# by `tools/test_kitupdate.py::test_every_marker_this_command_refuses_on_is_consumed_by_a_session_
# start`, which is what keeps an entry from outliving its consumer.
RESTART_MARKERS = (
    {"path": os.path.join(".claude", "HANDOVER_PENDING"),
     "consumer": "clear_handover_marker.py, on a SessionStart whose source is `startup`"},
    {"path": os.path.join(".claude", "kit_updated_from"),
     "consumer": "session_status.py, which announces the transition once and deletes it"},
)
# The one this command WRITES when the installer did not get that far -- the first of the two, by
# the same identity the guard reads it under. Named once; `RESTART_MARKERS` carries the reason.
HANDOVER_MARKER = RESTART_MARKERS[0]["path"]

# WHAT THIS COMMAND DOES NOT RE-READ after the installer, in the words every outcome carries. Same
# rule as `presets.UNREAD` and for the same measured reason: a scope stated in some messages is a
# scope the others deny. The readings below are the version stamp, the ownership manifest, the hook
# bundle and the two markers; the role skills, the provider artifacts, the repo templates and the
# constitution are not among them.
UNREAD = ("the role skills, the generated provider artifacts, the repo templates and the "
          "constitution were not re-read, so a missing or a half-copied one would not show here")

_NUMBER = re.compile(r"\d+")
# The two lines a kit's VERSION file carries; `identity` reads exactly these and nothing else.
_STAMP_FIELDS = ("version", "content")


def version_order(version: str):
    """The comparable key of a kit's `version:` value, or None when it carries no number.

    THE ONE DEFINITION OF "WHICH KIT IS NEWER", and it used to be two: this rule lived in the
    hooks' `_compat` where only the session briefing could reach it, so the command that REFUSES a
    downgrade would have been a second copy of the rule the briefing OFFERS one on. The hooks now
    ask this function through `_kernel.kit_update_verdict`, so the briefing and the refusal cannot
    disagree about a direction.

    Every part of the stamp that orders it is a number, so the key is the numbers in the order they
    appear -- a property of the format rather than a parse of it. A fourth component sorts correctly
    with no edit here, and a hand-edited stamp answers None, which callers read as "cannot say which
    is newer" and never as equal.
    """
    return tuple(int(number) for number in _NUMBER.findall(str(version or ""))) or None


def identity(text: str) -> dict:
    """{"version", "content"} -- a kit's own two statements about which release it is.

    Both, and not the version alone: `content:` is the hash `bump_kit_version` stamps over
    everything a scaffold reads or installs, so the pair is what tells two kits apart that carry
    one stamp -- the "KIT CONTENT MISMATCH" the session briefing has always been able to name and
    nothing could act on. A key that is absent is simply absent; the callers decide what that means.
    """
    values = {}
    for line in str(text or "").splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() in _STAMP_FIELDS and key.strip() not in values:
            values[key.strip()] = value.strip()
    return values


_KIT_LINE = re.compile(r"^\s*kit\s*:\s*(\S+)\s*$", re.MULTILINE)


def _kit_line(text: str):
    """A pin record's optional `kit:` -- the one field a VERSION file does not carry.

    Not folded into `identity`: that function reads what a kit says about ITSELF, and the two files
    it reads (a staged `VERSION`, an installed `kit_version`) have no such line. A pin is a
    different record and may name the kit it holds.
    """
    found = _KIT_LINE.search(str(text or ""))
    return found.group(1) if found else None


def _stamp(path: str) -> dict:
    try:
        return identity(presets.read_text(path))
    except OSError:
        return {}


# The verdicts `relation` answers with. A closed set, because it is a comparison of two order keys
# plus the readability of the two files -- every branch of that comparison has a name here, and
# `assert_updatable` answers each of them exactly once.
UP_TO_DATE = "up_to_date"
UPDATE_AVAILABLE = "update_available"
DOWNGRADE = "downgrade"
CONTENT_MISMATCH = "content_mismatch"
UNREADABLE_ORDER = "unreadable_order"
UNREADABLE = "unreadable"
NOT_STAGED = "not_staged"


def relation(root: str, kit: str) -> dict:
    """How the STAGED kit stands to the one this project installed -- the whole comparison, once.

    THREE READERS OF THIS ONE ANSWER: the approval question (through `change_manifest`), the
    command that acts on it, and the SessionStart briefing that OFFERS the update. The briefing used
    to compute its own, which is how a project could be told "KIT UPDATE AVAILABLE" by one file
    while another refused it.

    NEVER RAISES: an absent staging, an unreadable stamp and a hand-edited one are answers here, not
    errors, because the briefing must be able to ask without a try/except deciding what it prints.
    `assert_updatable` is where a verdict becomes a refusal.
    """
    directory = os.path.join(presets.staging_root(), kit)
    installed = _stamp(os.path.join(root, INSTALLED_VERSION_FILE))
    staged = _stamp(os.path.join(directory, STAGED_VERSION_FILE))
    answer = {"kit": kit, "kit_dir": directory, "from": installed, "to": staged}
    if not os.path.isdir(directory):
        return dict(answer, verdict=NOT_STAGED)
    if not installed or not staged:
        return dict(answer, verdict=UNREADABLE)
    if installed == staged:
        return dict(answer, verdict=UP_TO_DATE)
    here, there = version_order(installed.get("version")), version_order(staged.get("version"))
    if here is None or there is None:
        return dict(answer, verdict=UNREADABLE_ORDER)
    if there > here:
        return dict(answer, verdict=UPDATE_AVAILABLE)
    if there < here:
        return dict(answer, verdict=DOWNGRADE)
    return dict(answer, verdict=CONTENT_MISMATCH)


def _shown(stamp: dict) -> str:
    return stamp.get("version") or "no readable version stamp"


def assert_updatable(answer: dict) -> None:
    """Refuse every verdict that is not an update -- BEFORE anything moves.

    Each refusal says what the project has, what is staged, and what the remedy is; none of them
    is a retry of this command, because none of the causes is a transient. The DOWNGRADE branch is
    the one with teeth: a scaffold run from an older staging PRUNES the hooks this project has and
    leaves its newer kernel in place, so it is not an update in the other direction but a broken
    installation (measured 2026-08-02 against a real staging, the case the briefing has named
    since; `tools/test_kitupdate.py::test_an_older_staging_is_refused_before_the_installer_starts`).
    """
    verdict = answer["verdict"]
    if verdict == UPDATE_AVAILABLE:
        return
    if verdict == NOT_STAGED:
        raise StateError(
            "the kit '%s' is not staged on this machine (%s), so there is no release to update "
            "to -- nothing was changed. Remedy: this is an infrastructure gap, not a retry; report "
            "it and name the directory. The kits are installed once per machine, outside any "
            "project." % (answer["kit"], answer["kit_dir"]))
    if verdict == UNREADABLE:
        raise StateError(
            "the two kit stamps cannot both be read (this project: %s, staged: %s), so which "
            "release is which cannot be established -- refused (fail-closed); nothing was changed. "
            "Remedy: report the gap and name the two files, %s and %s."
            % (_shown(answer["from"]), _shown(answer["to"]),
               INSTALLED_VERSION_FILE.replace(os.sep, "/"), STAGED_VERSION_FILE))
    if verdict == UP_TO_DATE:
        raise StateError(
            "this project already runs the staged '%s' kit (%s), so there is no update to install "
            "-- nothing was changed. Remedy: none is needed. Re-applying the SAME release is a "
            "repair, not an update, and this command is not it: it is a scaffold run from a shell "
            "outside this session." % (answer["kit"], _shown(answer["to"])))
    if verdict == DOWNGRADE:
        raise StateError(
            "the staged '%s' kit (%s) is OLDER than the one this project runs (%s) -- refused; "
            "nothing was changed. Installing it would prune the files this project's release added "
            "and leave the newer ones standing, which is a broken installation rather than an "
            "update in the other direction. Remedy: tell the user their staging is behind and let "
            "them update it (the harness installer) first."
            % (answer["kit"], _shown(answer["to"]), _shown(answer["from"])))
    if verdict == CONTENT_MISMATCH:
        raise StateError(
            "the staged '%s' kit and the one this project runs carry the SAME version stamp (%s) "
            "and DIFFERENT content -- one of the two was changed without a version bump. Refused; "
            "nothing was changed. Remedy: that is a finding to report, not an update to run."
            % (answer["kit"], _shown(answer["to"])))
    raise StateError(
        "which of the two kit stamps is newer cannot be determined (this project: %s, staged: %s) "
        "-- refused (fail-closed); nothing was changed. Remedy: at least one stamp carries no "
        "readable version; report it to the user and let them decide, and do not install on a "
        "guess." % (_shown(answer["from"]), _shown(answer["to"])))


def assert_the_staging_is_its_own_stamp(directory: str) -> None:
    """The staged tree must still hash to the `content:` its own VERSION claims.

    WHY IT IS CHECKED HERE AND NOT ONLY AT THE END: `write_kit_state.py` makes the same comparison
    as the last step of the scaffold, and a failure there fails the run, which rolls it back. That
    is a rollback of an enforcement layer this project depends on, over a fact that was knowable
    before the first file moved -- 20 ms of hashing (measured over the three shipped kits,
    2026-08-16). The approval also names this hash, so a staging edited between the question and
    the command is refused rather than installed
    (`tools/test_kitupdate.py::test_a_staging_edited_after_the_question_is_refused`).
    """
    claimed = _stamp(os.path.join(directory, STAGED_VERSION_FILE)).get("content")
    if not claimed:
        raise StateError(
            "the staged kit at %s carries no `content:` hash in its %s, so it is not a kit this "
            "harness stamped -- refused; nothing was changed. Remedy: re-install the harness "
            "(`install.ps1`/`install.sh`), which stamps the staging." % (directory,
                                                                         STAGED_VERSION_FILE))
    try:
        measured = kit_hash(directory)
    except OSError as exc:
        raise StateError(
            "the staged kit at %s could not be hashed (%s), so it cannot be checked against its "
            "own stamp -- refused (fail-closed); nothing was changed. Remedy: report the gap and "
            "name the directory." % (directory, exc)) from None
    if measured != claimed:
        raise StateError(
            "the staged kit at %s does not hash to the `content:` in its own %s (%s vs %s) -- its "
            "source has been edited since it was stamped. Refused; nothing was changed. Remedy: "
            "re-install the harness (`install.ps1`/`install.sh`); installing an unstamped tree "
            "would put files into this project's enforcement layer that no release covers."
            % (directory, STAGED_VERSION_FILE, measured[:12], claimed[:12]))


# -- which STOCK is on disk, and whether it may be written over (FR-0044, II.11/5) --------------

# The stocks an installer can meet. The first four are not four cases somebody listed: they are
# the cross product of TWO readings of the state directory -- does a V2 kernel own state here, and
# does a V1 record still lie here.
#
# THE FIFTH IS THE CROSS PRODUCT'S OWN PRECONDITION, and it was missing for one round. That product
# only describes a reading that COMPLETED: a document the reading could not open might hold V1
# records or might not, and where that difference decides whether an installer may write, the
# answer is neither of the four. `classify` says exactly where it decides (there is one such place,
# derived rather than listed) and `tools/test_kitupdate.py::test_a_stock_whose_reading_did_not_
# complete_is_not_written_over` measures the DECISION rather than the sentence.
GREENFIELD = "greenfield"
V2_STOCK = "v2"
V1_STOCK = "v1"
MIXED_STOCK = "mixed"
UNKNOWN_STOCK = "unknown"


def _v1_reading(root: str) -> dict:
    """{"kernel_area", "v1_documents", "unreadable"} for the state directory under `root`.

    THE RECOGNISER IS `migrate`'s OWN, and this is its third reader rather than a third rule:
    `migrate.build_plan` translates the records, `report._check_no_v1_records_outside_the_archive`
    refuses a merge over them, and this one decides whether an installer may write here at all. All
    three ask `search_coverage` which files may be looked at and `scan_document` what a V1 record
    is; a rule of this module's own is how the installer and the validator would come to disagree
    about the same file.

    THE OTHER HALF IS THE SAME WALK'S `KERNEL` VERDICT -- the area the V2 kernel's own path builders
    can name (items, `generated/`, `approvals/`, `archive/`). It is what tells a V1 project from a
    V2 one, and the version STAMP is not: the pre-kernel installer wrote `.claude/kit_version` and
    `.claude/team_kit_roles.txt` too, so every field project of that vintage carries both
    (`git show 9e4419b~1:team-kits/scaffold_team.sh`, and the readings are in `H86`).

    WHAT IT WILL SPEND IS BOUNDED BY `report`'s two caps rather than by numbers of this module's
    own, and a document the caps or a parse error kept it from is reported in `unreadable`. WHAT
    THAT DOES TO THE VERDICT is the half the previous version of this paragraph left out, and it is
    the deciding half: where an unread document could still change the answer -- no kernel area of
    its own AND no V1 record found yet -- the verdict is `unknown` and the install is REFUSED, not
    annotated. Only where the answer stands either way (`v1` already found, or a live kernel area,
    which leaves `v2` and `mixed` and both are written over) does the reading merely say it may be
    short. A message is not a protection; `H86` (e) carries what that sentence cost. What the bound
    costs on real stocks, and what this reading does not see, is `H86` in
    `docs/POST_V2_WISHLIST.md`.
    """
    # Lazy, for `report`'s own reason: `migrate` imports `report` while `report` imports `migrate`
    # only inside its functions, so a module-scope import here would fix an order for both.
    import yaml

    from . import migrate, report
    state = ProjectState(os.path.join(root, trays.STATE_DIRNAME))
    coverage = migrate.search_coverage(state)
    reading = {"kernel_area": [rel for rel, verdict, _why in coverage if verdict == migrate.KERNEL],
               "v1_documents": {}, "unreadable": []}
    for where, why in migrate.unlistable_notes(coverage):
        reading["unreadable"].append((where, why))
    spent = 0
    for rel in sorted(rel for rel, verdict, _why in coverage if verdict == migrate.SEARCHED):
        path = os.path.join(state.root, *rel.split("/"))
        try:
            size = os.path.getsize(path)
        except OSError as exc:
            reading["unreadable"].append((rel, "could not be measured (%s)" % exc))
            continue
        if size > report.DOCUMENT_MAX_BYTES or spent + size > report.DOCUMENT_SCAN_MAX_BYTES:
            reading["unreadable"].append(
                (rel, "is %d bytes and this reading is bounded to %d per document and %d in total"
                 % (size, report.DOCUMENT_MAX_BYTES, report.DOCUMENT_SCAN_MAX_BYTES)))
            continue
        spent += size
        try:
            with open(path, encoding="utf-8-sig") as handle:
                payload = yaml.safe_load(handle)
        except (OSError, yaml.YAMLError) as exc:
            reading["unreadable"].append((rel, "could not be parsed (%s)" % exc))
            continue
        held = [key for _ordinal, key, record in migrate.scan_document(payload)
                if migrate._declares_status(record)
                and migrate._is_backlog_type(migrate.V1_ID_RE.match(key).group(1))]
        if held:
            reading["v1_documents"][rel] = held
    return reading


def classify(root: str) -> dict:
    """Which stock an installer would be writing over here -- `{"stock", ...the readings}`.

    WHERE AN INCOMPLETE READING CHANGES THE ANSWER, and where it does not -- derived, so it cannot
    drift into a list of cases. A document this reading could not open is a document that might
    hold V1 records. Ask what that would change:

      * a V1 record was already found -> the verdict is `v1`/`mixed` whatever else is in there;
      * the kernel owns part of this state -> the two remaining possibilities are `v2` and `mixed`,
        and BOTH are written over (see `assert_the_stock_may_be_written_over`), so the unread
        document cannot change the decision;
      * neither -> the two remaining possibilities are `greenfield` and `v1`, and those two differ
        in exactly the decision this reading exists for. That is the one place where "did not look"
        may not be resolved as "looked and found none", and it is `unknown`.

    NEVER RAISES for a state that is simply absent: a project with no state directory is
    `greenfield`, which is the answer, not an error. Everything else is the caller's decision --
    `assert_the_stock_may_be_written_over` is where a verdict becomes a refusal.
    """
    if not os.path.isdir(os.path.join(root, trays.STATE_DIRNAME)):
        return {"stock": GREENFIELD, "kernel_area": [], "v1_documents": {}, "unreadable": [],
                "root": root}
    reading = _v1_reading(root)
    if reading["v1_documents"]:
        stock = MIXED_STOCK if reading["kernel_area"] else V1_STOCK
    elif reading["kernel_area"]:
        stock = V2_STOCK
    elif reading["unreadable"]:
        stock = UNKNOWN_STOCK
    else:
        stock = GREENFIELD
    return dict(reading, stock=stock, root=root)


def _v1_summary(answer: dict) -> str:
    """The documents holding records, and -- when the list is cut -- HOW MANY are not shown.

    A refusal that says "7 document(s)" and then names five reads as the whole list, and the two it
    dropped were the largest ones in the field copies (`H86`). The count is part of the sentence.
    """
    documents = sorted(answer["v1_documents"])
    shown = ", ".join("%s (%d)" % (rel, len(answer["v1_documents"][rel])) for rel in documents[:5])
    rest = len(documents) - 5
    return shown + (" and %d more" % rest if rest > 0 else "")


def _unreadable_summary(answer: dict) -> str:
    return "; ".join("%s %s" % (where, why) for where, why in answer["unreadable"][:5])


def describe_stock(answer: dict) -> str:
    """One line for the installer's own output -- the verdict plus what it rests on."""
    if answer["stock"] in (V1_STOCK, MIXED_STOCK):
        detail = "V1 backlog records in %s" % _v1_summary(answer)
    elif answer["stock"] == V2_STOCK:
        detail = "%d file(s) in the kernel's own area, no V1 backlog record" % len(
            answer["kernel_area"])
    elif answer["stock"] == UNKNOWN_STOCK:
        # THE DOCUMENTS ARE NAMED HERE TOO, not only in the refusal: this is the line a person
        # watching the install reads, and a verdict they cannot act on is a verdict they report.
        detail = ("nothing of this harness's kernel is here and %d document(s) could not be read, "
                  "so whether V1 records lie in them is not known: %s"
                  % (len(answer["unreadable"]), _unreadable_summary(answer)))
    else:
        detail = "no state this harness wrote"
    short = (" -- %d document(s) could not be read: %s"
             % (len(answer["unreadable"]), _unreadable_summary(answer))
             if answer["unreadable"] and answer["stock"] != UNKNOWN_STOCK else "")
    return "%s (%s)%s" % (answer["stock"], detail, short)


def assert_the_stock_may_be_written_over(answer: dict) -> None:
    """A V2 kit is not installed over a V1 stock -- spec II.11/5's "existing repos stay pinned".

    WHY ONLY THE `v1` VERDICT REFUSES, and `mixed` does not. A `v1` stock has no V2 kernel: its
    whole state is monoliths this harness's kernel cannot read, and installing over it leaves a
    project whose enforcement layer refuses every tool write to a state directory no command can
    read either -- there is no route back from inside. A `mixed` stock HAS a live V2 installation,
    the update is legitimately about that installation, and its V1 remnants are a finding the
    validator already makes on every run (SR-0001). Refusing there would stop the update of every
    project that ever carried a remnant, which is over-refusal and not a pin.

    ...AND WHY `unknown` REFUSES TOO. It is the same refusal for the same reason: the reading that
    would have told `greenfield` from `v1` did not finish, and `greenfield` is the answer that
    permits the overwrite. Until 2026-09-01 this branch did not exist -- measured against a real
    BuyPlugGo copy whose single monolith carried one unbalanced `[`: the verdict was `greenfield`,
    the installer ran to rc 0 and put the V2 enforcement layer over the V1 state, and the only
    thing that said anything was the printed line. A MESSAGE that says "this may be short" beside a
    DECISION that proceeds is the reassuring half of the claim without the protecting half.

    NOTHING IS WRITTEN ON EITHER REFUSING PATH, and that is measured rather than promised:
    `tools/test_kitupdate.py::test_a_v1_stock_is_refused_and_the_installer_writes_nothing` and
    `tools/test_kitupdate.py::test_a_stock_whose_reading_did_not_complete_is_not_written_over`
    hash the project tree before and after a real `scaffold_team` run.
    """
    if answer["stock"] == UNKNOWN_STOCK:
        raise StateError(
            "which stock lies in this project cannot be established: nothing here belongs to this "
            "harness's kernel, and %d document(s) of its state could not be read (%s) -- so "
            "whether they hold V1 backlog records is unknown, and unknown is not empty. Refused "
            "(fail-closed); nothing was changed. Remedy: repair or move the document(s) named "
            "above (an editor or a shell outside the session), then run the installer again; "
            "`python scripts/harness.py migrate --dry-run` refuses the same files for the same "
            "reason and names them too."
            % (len(answer["unreadable"]), _unreadable_summary(answer)))
    if answer["stock"] != V1_STOCK:
        return
    raise StateError(
        "this project's state is a V1 stock (%d document(s) still hold V1 backlog records: %s) and "
        "no part of it belongs to this harness's kernel -- refused; nothing was changed. Installing "
        "over it would replace the enforcement layer while leaving a state directory no command "
        "here can read, and that layer then refuses every tool write to it. Remedy: the project "
        "stays on what it runs today until its records are imported -- `python "
        "scripts/harness.py migrate --dry-run` names every record that needs an answer first."
        % (len(answer["v1_documents"]), _v1_summary(answer)))


# -- the pin: a project that may not be replaced by the staged release (FR-0041) ----------------

# WHERE A PIN IS RECORDED. One file, and it carries the same two-line vocabulary every other stamp
# in this harness carries (`identity`), because what a pin names is a BUNDLE: the release this
# project is held at. It lives under `.claude/` for the reason every enforcement record does -- a
# session's own tool writes are refused there, so a pin is the user's statement and not a role's.
PIN_FILE = os.path.join(".claude", "kit_pin")


def pin_in_force(root: str) -> dict:
    """The pin this project carries, or None -- `{"version", "content", "text", "path"}`.

    IN FORCE EVEN WHEN IT IS UNREADABLE. A pin file whose stamp cannot be read still says that
    somebody pinned this project; reading it as "no pin" would make a damaged record an unpinning,
    which is the one way a pin may not end. `version` is then None and the refusal says so.

    `kit` is optional in the record and filled in from the installation when absent (`pinned_kit`);
    it is read here so that a pin has one reader rather than two.
    """
    path = os.path.join(root, PIN_FILE)
    if not os.path.exists(path):
        return None
    try:
        text = presets.read_text(path)
    except OSError as exc:
        return {"version": None, "content": None, "text": "unreadable (%s)" % exc, "path": path}
    stamp = identity(text)
    return {"version": stamp.get("version"), "content": stamp.get("content"),
            "kit": _kit_line(text), "text": text.strip(), "path": path}


def pinned_kit(root: str, pin: dict) -> str:
    """WHICH KIT the pin holds this project at -- its own `kit:` line, else the one installed here.

    A pin that states no kit still pins one: "stay as you are" is about the installation that is
    here, and the ownership manifest is what says which kit that is. When neither can be read the
    answer is None, and the caller refuses on it -- see `assert_not_pinned`.
    """
    if pin.get("kit"):
        return pin["kit"]
    try:
        return presets.installation(root)["kit"]
    except StateError:
        return None


def _bundle_words(kit: str, stamp: dict) -> str:
    """A bundle in one phrase -- kit plus whichever stamp fields are stated, hashes shortened."""
    stated = [(field, stamp.get(field)) for field in _STAMP_FIELDS if stamp.get(field)]
    if not stated:
        return "%s at a release nothing states" % (kit or "an unnamed kit")
    return "%s %s" % (kit or "an unnamed kit",
                      " ".join(value[:16] for _field, value in stated))


def assert_not_pinned(root: str, kit: str, to_stamp: dict) -> None:
    """Refuse to put a DIFFERENT bundle on a pinned project, and say how the pin is lifted.

    A PIN HOLDS A BUNDLE, AND A BUNDLE IS NOT A VERSION STRING. For one round this compared the
    version alone, and `tools/bump_kit_version.py` stamps all three kits with the SAME version --
    so a project pinned to `dev-team 2026.09.01-4` took `office-team 2026.09.01-4` at rc 0, its
    enforcement layer and its constitution replaced, while the pin said nothing (measured
    2026-09-01, `tools/test_kitupdate.py::test_a_pin_does_not_let_another_kit_in_at_the_same_
    version`). What is compared now is every part of the bundle the record can be held to: the KIT
    always (`pinned_kit`), and each stamp field the pin STATES. A field the pin does not state is
    not invented -- `content:` in particular is the exact tree, and demanding it of a pin that only
    names a version would turn every repair into a refusal.

    THE SAME BUNDLE IS NOT A MOVE, which is why the comparison is an equality and not a ban:
    re-applying the pinned release is a repair, and a pin that stopped repairs would leave a
    half-installed project with no way back short of deleting the record.

    WHAT THIS PIN DELIBERATELY DOES NOT DO is silence the session briefing's "KIT UPDATE AVAILABLE"
    nag: that hook computes its offer from `relation` and knows nothing of this file, so a pinned
    project is still told an update exists and hears about the pin when the update is REFUSED. It is
    the noisy failure rather than the silent one (BUG-0078's marker class is the silent one), and
    the cost is that the user learns of their own pin one step later than they could (`H87`).
    """
    pin = pin_in_force(root)
    if pin is None:
        return
    held = pinned_kit(root, pin)
    stated = {field: pin[field] for field in _STAMP_FIELDS if pin.get(field)}
    if held and held == kit and stated and all(
            (to_stamp or {}).get(field) == value for field, value in stated.items()):
        return
    raise StateError(
        "this project is PINNED to %s and %s is not that bundle -- refused; nothing was changed. "
        "The pin is %s and it says:\n%s\nRemedy: this is the user's decision to reverse, not a "
        "retry -- they delete that file from a shell outside this session, and the install runs. "
        "Re-applying the pinned bundle itself stays allowed."
        % (_bundle_words(held, stated), _bundle_words(kit, to_stamp or {}),
           PIN_FILE.replace(os.sep, "/"), pin["text"]))


def assert_no_pin_blocks_a_rollback(root: str) -> None:
    """A pin stops a ROLLBACK as well, and that is the whole meaning of the word.

    THE THIRD DOOR, and it was open for one round. A rollback replaces the installed bundle exactly
    as an update does -- only with an older one -- so a pin that let it through was not "stay as
    you are". What it produced was worse than a gap: measured 2026-09-01, a project pinned to
    2099.12.31-9 was rolled back to 2026.09.01-4 at rc 0 with the pin still in place, and after
    that NEITHER an update NOR a repair could run, because the only bundle the pin admits is the
    one that is no longer installed. Refusing here is the direction that leaves the project usable
    (`tools/test_kitupdate.py::test_a_pin_stops_a_rollback_in_both_twins`).
    """
    pin = pin_in_force(root)
    if pin is None:
        return
    raise StateError(
        "this project is PINNED and a rollback would replace its bundle just as an update does -- "
        "refused; nothing was changed. The pin is %s and it says:\n%s\nRemedy: the user deletes "
        "that file from a shell outside this session if the pin is to end, then the rollback runs."
        % (PIN_FILE.replace(os.sep, "/"), pin["text"]))


def waiting_for_a_restart(root: str) -> list:
    """The restart markers this project still carries -- see `RESTART_MARKERS` for what that proves."""
    return [marker for marker in RESTART_MARKERS
            if os.path.exists(os.path.join(root, marker["path"]))]


def assert_no_restart_is_pending(root: str) -> None:
    """An install has already happened here and no session has started since -- refuse.

    Not a caution: running the installer again over an unconsumed marker overwrites the record of
    what the FIRST update did (`kit_updated_from` is the from-version the next session announces,
    and the scaffold refuses to overwrite it), and it asks a session that was already told to stop
    to do more work. The way out is the restart both markers are waiting for.
    """
    pending = waiting_for_a_restart(root)
    if not pending:
        return
    raise StateError(
        "this project is already waiting for a session restart -- refused; nothing was changed. %s "
        "still exists, and it is removed by %s. Remedy: end this session and start a new one in "
        "this folder; the update state is picked up there. If the marker is stale because no "
        "restart will happen, that is a gap to report, not a command to retry."
        % ("; ".join(marker["path"].replace(os.sep, "/") for marker in pending),
           "; ".join(marker["consumer"] for marker in pending)))


def _plan(state: ProjectState) -> dict:
    """Everything one kit update needs to know, resolved ONCE -- and every check that has no side
    effect, ahead of every one that has.

    `apply` and the approval question are two readers of this one derivation: if each resolved the
    kit and the two stamps for itself, the question could name a release the command then does not
    install, which is what the approval hash exists to prevent (the shape
    `approvals.preset_subject_manifest` argues for the preset case).
    """
    root = presets.repo_root(state)
    kit = presets.installation(root)["kit"]
    answer = relation(root, kit)
    assert_updatable(answer)
    # ...AND THE PIN AHEAD OF THE HASHING: a pinned project is not going to install anything, so
    # it may not be told first that some staging it will never read no longer matches its stamp.
    assert_not_pinned(root, kit, answer["to"])
    assert_the_staging_is_its_own_stamp(answer["kit_dir"])
    assert_no_restart_is_pending(root)
    return dict(answer, root=root, manifest=approvals.kit_update_subject_manifest(
        kit, answer["from"].get("version"), answer["from"].get("content"),
        answer["to"].get("version"), answer["to"].get("content")))


def change_manifest(state: ProjectState) -> dict:
    """What an update would DO here, in the shape the approval hashes -- re-derived at apply."""
    return _plan(state)["manifest"]


# -- what a run leaves behind -------------------------------------------------------------------

def _bundle_reading(root: str, kit_dir: str) -> str:
    """WHICH kit's enforcement bundle is installed right now -- the reader the stamp cannot be.

    TWO READERS, BECAUSE THE STAMP IS STALE FOR THE WINDOW THIS MATTERS IN. The installer copies
    `.claude/hooks` and `.claude/kernel` LONG before it writes `.claude/kit_version` (measured
    2026-08-16 against the real scaffold with the timeout shortened: at 1.6 s the bundle was
    already the staged kit's while the stamp still named the old release and `kit_state.json` still
    recorded the old bundle hash -- so every kernel-backed gate refused, and a caller that asked the
    stamp alone would have reported "nothing was installed"). The answers are properties, not
    guesses:

      staged   -- the installed bundle is byte-identical to the staged kit's files
      recorded -- it is not, but it still hashes to what `.claude/kit_state.json` vouched for, i.e.
                  nothing has moved
      neither  -- it is neither: a half-copied bundle, or one that was edited
      unreadable -- it cannot be measured at all, which is the fail-closed answer and the state
                  every integrity gate refuses on

    `tools/test_kitupdate.py::test_an_aborted_update_is_not_reported_off_the_stamp_alone` is the
    measurement that keeps the pair honest.
    """
    claude = os.path.join(root, ".claude")
    try:
        if not modified_bundle_files(os.path.join(kit_dir, "hooks"),
                                     os.path.join(os.path.dirname(kit_dir), "kernel"), claude):
            return "staged"
    except (BundleSourceMissing, OSError):
        pass                        # no source to compare against: the other two readings still hold
    measured = hook_bundle_hash(claude)
    if measured is None:
        return "unreadable"
    try:
        with open(os.path.join(claude, "kit_state.json"), encoding="utf-8-sig") as handle:
            recorded = (json.load(handle) or {}).get("hook_bundle_hash")
    except (OSError, ValueError):
        recorded = None
    return "recorded" if recorded and recorded == measured else "neither"


def _installed_state(root: str, kit_dir: str) -> dict:
    """What this project says it runs, and what it actually runs -- read, never assumed."""
    return {"stamp": _stamp(os.path.join(root, INSTALLED_VERSION_FILE)),
            "bundle": _bundle_reading(root, kit_dir)}


_BUNDLE_WORDS = {
    "staged": "the enforcement bundle on disk is the STAGED kit's",
    "recorded": "the enforcement bundle on disk is still the one this project recorded trust for",
    "neither": "the enforcement bundle on disk is NEITHER the staged kit's nor the one this "
               "project recorded trust for, i.e. half-copied or edited",
    "unreadable": "the enforcement bundle on disk cannot be measured at all, which is the state "
                  "every integrity gate refuses on",
}


def _describe(reading: dict) -> str:
    return "stamp %s, and %s" % (_shown(reading["stamp"]), _BUNDLE_WORDS[reading["bundle"]])


def _marker_path(root: str) -> str:
    return os.path.join(root, HANDOVER_MARKER)


def _restart_marker_as_found(root: str) -> str:
    """What the marker says about this project right now -- READ, and nothing written.

    THE BRANCH THIS EXISTS FOR, and it is a correction of this same round: the "nothing moved"
    outcome used to ensure the marker like every other one, and the resulting sentence was measured
    FALSE by the very command that wrote it. The chain (real scaffold, real approval, a preset typo
    in `project_config.yaml` -- a cause the PM can fix in-session through the kernel): the installer
    refuses touching nothing, the marker is written anyway, `gate_dispatch` then refuses every spawn
    with "an installer changed this project's kit files", the user-global guard closes the rest, and
    `assert_no_restart_is_pending` refuses the RETRY. The session was dead over a typo, with no
    route out that this harness has. A project nothing happened to needs no restart, so it gets no
    marker -- and both halves of what this returns are read off the disk rather than asserted, so a
    hardcoded sentence cannot pass (`tools/test_kitupdate.py::test_an_installer_that_refused_
    without_touching_anything_leaves_no_marker_and_can_be_retried`).
    """
    if os.path.exists(_marker_path(root)):
        return ("the restart marker %s is in place, so this session is stopped either way"
                % HANDOVER_MARKER.replace(os.sep, "/"))
    return ("no restart marker was set (%s does not exist), so this session is not stopped and this "
            "command can be run again once the cause above is dealt with"
            % HANDOVER_MARKER.replace(os.sep, "/"))


def ensure_restart_is_forced(root: str, kit: str) -> str:
    """Make the handover marker exist, and say what was found or written -- never claim it.

    PUBLIC because a second caller lives outside this package: `user/bridge/update_kit.py`, the
    bootstrap for a stock whose kernel predates this module (BUG-0059), runs the same installer and
    owes the same stop sign. Vendoring the marker's path and text there would be a second answer to
    "what stops a session whose kit changed underneath it".

    THE WINDOW THIS EXISTS FOR, measured 2026-08-16 against the real scaffold: between 2.4 s and
    3.4 s of a 3.4 s run the update was materially complete -- new stamp, new bundle, trust record
    rewritten -- and the marker was still absent, because the installer writes it as its very last
    act. A run killed there leaves a session whose kit has changed and whose only stop sign was
    never raised. So the marker is ensured by this command instead of being inherited from the
    installer's luck, and the result is READ BACK: a marker that could not be written is the one
    thing this command may not be quiet about.

    CALLED ONLY WHERE THE INSTALLATION REALLY MOVED -- the success path and the branch that measured
    a change. The other branch reads instead of writing, for the reason
    `_restart_marker_as_found` carries.
    """
    path = _marker_path(root)
    if os.path.exists(path):
        return "the restart marker %s is in place" % HANDOVER_MARKER.replace(os.sep, "/")
    try:
        ProjectState._write_text_atomic(path, _MARKER_TEXT % (kit, COMMAND))
    except OSError as exc:
        return ("THE RESTART MARKER %s COULD NOT BE WRITTEN (%s), so nothing stops this session "
                "from carrying on under a kit that has changed underneath it -- end the session "
                "now" % (HANDOVER_MARKER.replace(os.sep, "/"), exc))
    if not os.path.exists(path):
        return ("THE RESTART MARKER %s IS STILL ABSENT after writing it, so nothing stops this "
                "session from carrying on under a kit that has changed underneath it -- end the "
                "session now" % HANDOVER_MARKER.replace(os.sep, "/"))
    return ("the restart marker %s was not left by the installer and was written by this command"
            % HANDOVER_MARKER.replace(os.sep, "/"))


_MARKER_TEXT = (
    "# agents-and-skills handover marker (BUG-0016, DEC-0032)\n"
    "# The '%s' kit was updated in this session by `%s`. Until the session is restarted the\n"
    "# kit's dispatch gate refuses specialist spawns here, and the user-global handover guard --\n"
    "# where the harness installed one -- refuses work-engine commands and product writes too.\n"
    "# A SessionStart(startup) hook clears this file on the next real restart.\n")


def pending_entries(path: str):
    """The `- <path>` lines of a pending list, in order. [] no such list -- None NOT READABLE.

    One reader for both installers' output, because both write the same record
    (`printf -- "- %s\\n"` / `"- $_"`) and three readers used to slice it three ways.

    THE THIRD ANSWER IS THE POINT, exactly as in `_same_but_for_line_endings` and from the same
    defect one layer up: with `[]` for both, a list that EXISTS and could not be opened was
    indistinguishable from one with nothing left in it, so the caller read it as resolved, said so,
    and DELETED it. Measured with a real hook against a genuine unmerged divergence and read access
    denied by ACL: no nag, and the file gone -- a kit fix dropped out together with its own record,
    which is the expensive direction. (Before the re-validation existed the same denial produced no
    nag either, but the file SURVIVED, so this was a regression of that round and not an old hole.)
    `FileNotFoundError` is separated from the rest rather than probed with `os.path.exists`, so the
    two answers cannot swap under a race.

    AND EVERY OTHER WAY OF NOT READING IT IS THE SAME ANSWER (BUG-0163). This caught `OSError`
    alone, so anything else `open()` or the decoder raises -- a `ValueError` out of a codec is the
    reachable one -- travelled up and aborted `update-kit` AFTER the installer had already run,
    with the tree half moved. The hook around this was guarded; the command was not. "Unknown" is
    the right answer for every failure to read, and it is the safe one: the nag stays.
    `tools/test_kitupdate.py::test_a_pending_list_that_cannot_be_read_at_all_is_unknown_and_not_a_crash`
    """
    try:
        with open(path, encoding="utf-8-sig", errors="ignore") as handle:
            return [line.strip()[2:].strip() for line in handle if line.strip().startswith("- ")]
    except FileNotFoundError:
        return []                 # no such list -- nothing is pending
    except Exception:             # noqa: BLE001 -- see the paragraph above: not read is not empty
        return None               # it EXISTS and could not be read -- unknown, never "empty"


def _same_but_for_line_endings(one: str, other: str):
    """True equal / False differs / None NOT COMPARED -- ignoring line-ending style.

    THE THIRD ANSWER IS THE POINT, and its absence was the defect this signature exists for: with a
    bare True/False, "these two files differ" and "one of them could not be opened at all" were the
    same answer, and the caller then signed a sentence saying every entry had been held against its
    template while nothing had been read (measured with the staged kit removed -- see
    `outstanding_pending`). None keeps the entry exactly as False does; what it changes is what the
    caller may CLAIM about it.

    THE SAME COMPARISON THE INSTALLERS DECIDE AN ENTRY WITH -- `scaffold_team.ps1`'s
    `Get-NormalizedSha256` and the `.sh` twin's `tr -d '\\r'` both drop EVERY carriage return, so
    this drops every one too: a reader that normalised only CRLF PAIRS would call a file different
    that the writer called equal, and the entry would nag forever. (`hashing.kit_hash` normalises
    the pair instead; that value is a release stamp, not this question.)

    WHAT MATCHING THE WRITER COSTS, stated because the paragraph above only said it was consistent:
    dropping every CR is not "line-ending style" for a file that is not line-oriented text. Two files
    differing ONLY by a lone CR inside a line compare EQUAL here, and so does a BINARY template
    (a `.woff2`) that gained or lost a 0x0D byte -- this rule is applied to whatever a pending list
    names, not only to source. Both are over-DROPPING, i.e. a kit fix that consists of nothing but
    such a byte would stop being reported. Nothing here narrows that: narrowing it would mean this
    reader and the two installers disagreeing about the same file, which is the failure that put
    four matching scripts on the user's list in the first place.

    EVERY FAILURE TO READ IS THE THIRD ANSWER, not only an `OSError` -- the same correction as in
    `pending_entries` and for the same measured reason (BUG-0163): a reader that let anything else
    escape aborted `update-kit` after the installer had moved the tree.
    `tools/test_kitupdate.py::test_a_pending_list_that_cannot_be_read_at_all_is_unknown_and_not_a_crash`
    """
    read = []
    for path in (one, other):
        try:
            with open(path, "rb") as handle:
                read.append(handle.read().replace(b"\r", b""))
        except Exception:         # noqa: BLE001 -- not compared is its own answer, never "differs"
            return None
    return read[0] == read[1]


def outstanding_pending(root: str, kit: str = None) -> dict:
    """{suffix: {"entries": [...], "checked": bool, "read": bool}} per pending list found on disk.

    RE-VALIDATED AGAINST THE TREE, NOT TRUSTED AS WRITTEN, and that is the half BUG-0068 kept open.
    Measured 2026-08-26 on the user's real office project: all four scripts named in
    `.claude/kit_update_pending.repo` were RAW byte-identical to the template the project had been
    updated from, three of them with mtimes older than the update -- so the list did not correct
    itself, and the nag went on sending a non-developer user to the terminal for files that already
    matched. Nothing rewrites such a list between installer runs, so the list is a snapshot from one
    moment and the tree is the fact.

    `checked` IS THE HALF THAT MAKES THE CALLER'S SENTENCE TRUE, and it is separate from `entries`
    because the two answer different questions. `entries` is what to report; `checked` says whether
    EVERY entry of that list was really held against a template this process could open. It is False
    the moment one entry was kept without a comparison -- an unresolvable kit (no
    `.claude/team_kit_roles.txt`), a staging that is not on this machine, a template or project file
    that cannot be read, an entry naming a path outside its own tree. Measured with
    `~/.claude/team-kits/office-team` removed, which is the ordinary state on a second machine and
    before the harness install: every entry comes back kept, the answer is a NON-EMPTY dict, and a
    caller that inferred "compared" from "the kernel answered" then signed a nag with "each entry was
    re-checked" while nothing had been opened
    (`tools/test_kitupdate.py::test_a_backlog_that_could_not_be_re_checked_says_so`).

    WHY THE COMPARISON IS AGAINST THE STAGED TEMPLATE rather than against a hash recorded when the
    entry was written: a recorded hash would have to be added by a future installer run, so it could
    do nothing for the list a project ALREADY carries -- which is the only list the user has. The
    staged template is also the sharper question: it is the content the project would have to track
    today, so a project that merged forward is released and one that never merged keeps nagging.

    THE DIRECTION IS TOWARDS NAGGING, in every branch: everything that is not a read-and-equal keeps
    the entry. A stale nag costs a sentence; a silent skip costs the kit fix.

    `read` IS THE OTHER HALF, and it is what makes DELETING a list safe. A list that exists and could
    not be opened has no entries to report, and a caller that read "no entries" as "nothing left to
    merge" said so and removed the file -- measured with a real hook against a genuine unmerged
    divergence with read access denied by ACL: no nag, and the record gone. `read` is False there,
    `entries` is empty because it is UNKNOWN rather than because it is nothing, and no caller may
    resolve or delete such a list (`tools/test_kitupdate.py::test_a_pending_list_that_cannot_be_read
    _is_never_called_resolved`). Reachable through an ACL denial and through a cloud placeholder that
    is not hydrated -- the user's real project lives in OneDrive.

    A list that exists, was READ, and has no outstanding entry answers with an empty `entries` and
    `read` True, which is how a caller tells "resolved, delete me" from both "no such list" (absent
    from the answer entirely) and "cannot say".
    """
    answer = {}
    for suffix in PENDING_LISTS:
        path = os.path.join(root, PENDING_PREFIX + suffix)
        if not os.path.isfile(path):
            continue
        entries = pending_entries(path)
        answer[suffix] = {"entries": [] if entries is None else entries,
                          "checked": entries is not None,
                          "read": entries is not None}
    if not answer:
        return answer
    try:
        kit = kit or presets.installation(root)["kit"]
        templates = os.path.join(presets.staging_root(), kit, "templates")
    except (StateError, OSError):
        # NOTHING was compared: which kit this project runs, or where its templates are, could not
        # be established. Every entry stays AND every list says so.
        for found in answer.values():
            found["checked"] = found["read"] and not found["entries"]
        return answer
    for suffix, found in answer.items():
        if not found["read"]:
            continue        # nothing to compare, and `checked` must not be reset to True below
        spec = PENDING_LISTS[suffix]
        outstanding, checked = [], True
        for entry in found["entries"]:
            parts = [part for part in str(entry).replace("\\", "/").split("/") if part]
            if not parts or ".." in parts:
                outstanding.append(entry)   # not a path inside its own tree -- kept, not compared
                checked = False
                continue
            template = os.path.join(templates, spec["template"], *parts)
            project = os.path.join(root, spec["project"], *parts) if spec["project"] \
                else os.path.join(root, *parts)
            verdict = _same_but_for_line_endings(project, template)
            if verdict is None:
                outstanding.append(entry)   # one side could not be opened -- kept, not compared
                checked = False
            elif not verdict:
                outstanding.append(entry)
        found["entries"], found["checked"] = outstanding, checked
    return answer


def _pending_templates(root: str) -> str:
    """The diverged repo templates the run recorded, if any -- the lead's follow-up work.

    Counted through `outstanding_pending`, so this report and the session briefing's nag cannot
    disagree about how much work is left (they did: this one counted the written lines).
    """
    if not os.path.isfile(os.path.join(root, PENDING_TEMPLATES)):
        return ""
    found = outstanding_pending(root).get("repo")
    where = PENDING_TEMPLATES.replace(os.sep, "/")
    if found is None or not found["read"]:
        # UNKNOWN, and it must not borrow either of the two sentences below: an unopenable list has
        # no entries to count and is not one that "already matches" (`pending_entries`).
        return ("%s was left by the run and could NOT be READ from here, so what it still asks for "
                "is unknown -- it is neither resolved nor removed on that ground. Report it and "
                "name the file; a permission denial and a cloud placeholder that is not downloaded "
                "both look like this" % where)
    if not found["entries"]:
        return ("%s was left by the run and every entry in it already matches the new kit's "
                "template, so there is nothing to merge; the next session start removes the file"
                % where)
    # ...and the count is qualified where it was not measured, for `outstanding_pending`'s reason.
    return ("%d repo template(s) are listed in %s as differing from the new kit's and were KEPT%s; "
            "the session briefing nags until that file is worked through and deleted"
            % (len(found["entries"]), where, "" if found["checked"] else
               " (they could NOT be re-checked against the kit templates from here, so the count is "
               "the file's own and an entry may already match again)"))


# -- role memory an update leaves behind (BUG-0088) ---------------------------------------------

# WHERE A ROLE'S MEMORY TREE LIES. The same directory name the kit hook that polices its budget
# uses (`guard_memory_budget.MEMORY_DIR`), and the kernel cannot borrow that one: it ships BESIDE
# the kit hooks, not under them, and a project's copy of them is exactly what an update replaces.
# So the name stands here once and the two are held together by
# `tools/test_kitupdate.py::test_the_memory_directory_this_command_reads_is_the_one_the_kit_hook_polices`,
# which reads both out of the running modules rather than out of this sentence.
MEMORY_DIR = os.path.join(".claude", "agent-memory")
# The frontmatter key whose PRESENCE is what makes a provider load that tree for a role.
MEMORY_KEY = "memory"


def memory_residue(root: str) -> dict:
    """`{"orphaned": [(role, why, files)], "read": bool}` -- memory trees no installed role declares.

    THE SUBJECT IS A PROPERTY, NOT A LIST OF ROLE NAMES: a directory under the memory tree is
    residue when the role definition INSTALLED RIGHT NOW does not declare `memory:` -- either
    because no definition of that name is installed any more, or because none could be read out of
    the one that is. Stream E of generation 3 removed the key from three roles (FR-0064) and the
    trees an older kit wrote stayed; no installer, scaffold or kernel path named `agent-memory` at
    all, measured over all of them (BUG-0088).

    `read` IS THE THIRD ANSWER, and it is `pending_entries`' reason one storey up: a memory tree
    that EXISTS and could not be listed has no entries to report, and a caller that read the empty
    list as "nothing left here" would say so. An ABSENT tree is `read` True with nothing orphaned --
    that is the ordinary case and it is not the same answer.

    THE ROLE FILE IS READ THROUGH `references._frontmatter`, the kernel's one frontmatter reader,
    so a role definition and a skill definition are read by the same code. Its `None` is folded into
    "no `memory:` declaration could be read", which is what the sentence says -- never "the role
    dropped the key", because a file this process could not parse says nothing about what the role
    declares.
    """
    directory = os.path.join(root, MEMORY_DIR)
    try:
        names = sorted(one for one in os.listdir(directory)
                       if os.path.isdir(os.path.join(directory, one)))
    except FileNotFoundError:
        return {"orphaned": [], "read": True}       # no memory tree here at all
    except OSError:
        return {"orphaned": [], "read": False}      # it exists and could not be listed
    agents = os.path.join(root, presets.AGENTS_DIR)
    orphaned = []
    for name in names:
        role_file = os.path.join(agents, name + presets.ROLE_SUFFIX)
        if not os.path.isfile(role_file):
            why = "no role definition of that name is installed any more"
        else:
            front = references._frontmatter(role_file)
            if front is not None and MEMORY_KEY in front:
                continue
            why = ("the installed %s%s carries no `%s:` this command could read"
                   % (name, presets.ROLE_SUFFIX, MEMORY_KEY))
        held = 0
        for _base, _subdirs, files in os.walk(os.path.join(directory, name)):
            held += len(files)
        orphaned.append((name, why, held))
    return {"orphaned": orphaned, "read": True}


def _memory_residue_note(root: str) -> str:
    """One sentence about role memory this update did not touch -- a READING, never a promise.

    IT LISTS AND REMOVES NOTHING, and that is a decision with a reason rather than an omission.
    Three of them, and the first is the one that decides: whether a provider still loads an existing
    tree for a role that no longer declares the key is UNMEASURED (BUG-0088 AC-2), so removal would
    be an irreversible act on an unmeasured premise -- the direction DEC-0056 (c) keeps its care for,
    and the content is the user's own craft knowledge, not this harness's record. Second, the only
    restorable quarantine a project has is the installer's snapshot under `.claude/backups/`, which
    the two `scaffold_team` twins own and write the restore set of; a tree moved there by this
    command would sit outside that set and a rollback would not put it back. Third, what the user
    can do about it -- delete it, or put the key back -- is a decision about their own material.
    The open half is `H160` in `docs/POST_V2_WISHLIST.md`.
    """
    found = memory_residue(root)
    where = MEMORY_DIR.replace(os.sep, "/")
    if not found["read"]:
        return ("%s exists here and could NOT be listed, so whether a role memory tree survived "
                "this update is unknown -- report it and name the directory; a permission denial "
                "and a cloud placeholder that is not downloaded both look like this" % where)
    if not found["orphaned"]:
        return ""
    return ("%d role memory tree(s) under %s are not declared by any role this project now "
            "installs and were LEFT AS THEY ARE (%s) -- nothing here removes them: what a provider "
            "does with such a tree is not measured, and the content is the user's own craft notes. "
            "Tell the user, and let them decide between deleting the directory and putting the "
            "role's `%s:` back"
            % (len(found["orphaned"]), where,
               "; ".join("%s: %d file(s), %s" % (name, held, why)
                         for name, why, held in found["orphaned"]),
               MEMORY_KEY))


def _follow_up(root: str) -> str:
    """Everything this run leaves for somebody to act on, in the one line the caller prints.

    IT TRAVELS IN THE `pending_templates` KEY and keeps that name because `kernel/cli.py`'s
    `update-kit` branch is what prints it, and this module does not own that file. Said here rather
    than left to be found: a second sentence under a second key would need a change to `cli.py` to
    reach anybody, and a report the user never gets is not a report.
    `tools/test_kitupdate.py::test_the_update_report_names_a_memory_tree_no_installed_role_declares`
    runs the real command and reads its OUTPUT, so a renamed key reddens there instead of going
    quiet.
    """
    return "; ".join(part for part in (_pending_templates(root), _memory_residue_note(root))
                     if part)


# -- the previous bundle, and how it is replayed (FR-0041) --------------------------------------

# WHERE THE INSTALLER PUTS THE BUNDLE IT REPLACES, and the one file inside a snapshot that says
# which of its paths a rollback puts back. Both twins of `scaffold_team` write that file at the
# moment they take the snapshot, so the set a rollback replays is the set the run that MADE it
# owned -- an older snapshot is replayed by its own contract and not by today's idea of one. This
# module only READS it: the replay is the installer's, for `presets`' reason (a second
# implementation would be a second answer to "what is installed").
BACKUPS_DIR = os.path.join(".claude", "backups")
RESTORE_SET = "RESTORE_SET"


def rollback_command(kit: str) -> str:
    """The installer line that replays the previous bundle, in the spelling THIS host would run.

    The flag follows the twin `presets.installer_command` picked -- the same two-twins fact, read
    off the script it returned rather than guessed at, so a host without PowerShell is told the
    bash spelling.
    """
    argv = presets.installer_command(kit)
    flag = "-Rollback" if any(part.endswith(".ps1") for part in argv) else "--rollback"
    return " ".join(argv + [flag])


def previous_bundle(root: str) -> dict:
    """The snapshot a rollback would replay -- `{"stamp", "path", "entries"}` -- or None.

    THE NEWEST ONE, because that is the one the LAST install wrote and therefore the one holding
    the bundle this project ran before it. The stamps sort by name because the installer builds
    them from `YYYYmmdd-HHMMSS` plus a collision suffix, so lexical order is chronological order.

    A SNAPSHOT WITHOUT A RESTORE SET IS NOT A CANDIDATE, and it is not silently skipped either: it
    predates the manifest, so which of its paths the installer OWNED is exactly what nobody
    recorded, and replaying "everything in it" would put back files the installer only reads (a
    user's `settings.local.json` among them). `skipped` names them so a reader is told why the
    snapshot they can see is not the one offered.
    """
    directory = os.path.join(root, BACKUPS_DIR)
    try:
        stamps = sorted(os.listdir(directory), reverse=True)
    except OSError:
        return None
    skipped = []
    for stamp in stamps:
        path = os.path.join(directory, stamp)
        manifest = os.path.join(path, RESTORE_SET)
        if not os.path.isfile(manifest):
            if os.path.isdir(path):
                skipped.append(stamp)
            continue
        try:
            entries = [line.strip() for line in presets.read_text(manifest).splitlines()
                       if line.strip()]
        except OSError:
            skipped.append(stamp)
            continue
        return {"stamp": stamp, "path": path, "entries": entries, "skipped": skipped}
    return None


def restorable(root: str, kit: str) -> str:
    """One sentence about what a rollback could put back here -- for a refusal that has to say it.

    It is a READING and never a promise: the snapshot is named, the number of paths it would put
    back is the manifest's own, and the line says what a rollback does NOT undo, because the
    installer writes records outside the set it owns (`tools/test_kitupdate.py::test_a_rollback_
    restores_the_previous_bundle_byte_for_byte` measures the set it does).
    """
    found = previous_bundle(root)
    if found is None:
        return ("no snapshot under %s carries a restore set, so there is no bundle this harness "
                "can replay -- restore by hand from %s if one is there"
                % (BACKUPS_DIR.replace(os.sep, "/"), BACKUPS_DIR.replace(os.sep, "/")))
    return ("the bundle this project ran before the last install is in %s/%s and %s puts its %d "
            "recorded path(s) back; records the installer writes outside that set (the update "
            "markers, the pending lists) are not undone by it"
            % (BACKUPS_DIR.replace(os.sep, "/"), found["stamp"], rollback_command(kit),
               len(found["entries"])))


def _after_a_failed_install(root, kit, kit_dir, was, command, reason):
    """Refuse with the state the run actually left -- read through both readers, never asserted.

    The defect this shape exists for is `presets._after_a_failed_install`'s, in the sharper
    position: there the abort left role files missing, here it can leave the project's whole
    enforcement layer half-replaced. Nothing here is claimed. The installation is READ BACK
    (`_installed_state`), and the three outcomes are told apart by that reading:

      unchanged -- say so, with the limit of what was read, and set NO marker: a project nothing
                  happened to needs no restart, and a marker written there stops the session over a
                  cause the PM could fix in the next minute (`_restart_marker_as_found` carries the
                  measured chain). The marker state is read out, not asserted;
      anything else -- run the installer ONCE more, which is the operation that COMPLETES the
                  update the user approved (unlike the preset case there is nothing to restore: the
                  scaffold rolls its own changes back when it REFUSES, and a run that was killed is
                  finished rather than undone), then read again and say what is there now.

    The repair run's own exit code decides nothing -- it is a note in the message. What stops the
    first run usually stops the second, and a reading taken only when the repair returned cleanly
    is the over-alarming half of this same defect (`presets` measured it; the branch is the same).

    RETURNS the refusal so the call sites read `raise _after_a_failed_install(...)`.
    """
    if _installed_state(root, kit_dir) == was:
        return StateError(
            "%s Nothing about the installation moved: %s -- and %s; %s. Remedy: deal with what the "
            "installer said above, then run this command again; report the gap if it is not yours "
            "to fix, and pass that limit on with it."
            % (reason, _describe(was), _restart_marker_as_found(root), UNREAD))
    repair_note = ""
    try:
        again = subprocess.run(command, cwd=root, capture_output=True,
                               timeout=presets.INSTALLER_TIMEOUT, **presets.CHILD_TEXT)
        if again.returncode != 0:
            repair_note = " (the completing run itself exited %d)" % again.returncode
    except (OSError, subprocess.SubprocessError) as exc:
        repair_note = " (the completing run could not be completed: %s)" % exc
    repaired = _installed_state(root, kit_dir)
    marker = ensure_restart_is_forced(root, kit)
    return StateError(
        "%s THE INSTALLATION HAD ALREADY MOVED: it was [%s], and after running the installer once "
        "more to complete it, it is [%s]%s. %s; %s. Remedy: report BOTH readings to the user and "
        "stop -- this session may not work under them either way. The way back is named rather "
        "than left to a directory listing: %s. Either that or a repair scaffold is a step for a "
        "shell outside this session."
        % (reason, _describe(was), _describe(repaired), repair_note, marker, UNREAD,
           restorable(root, kit)))


def apply(state: ProjectState) -> dict:
    """Install the staged kit over this project, on the user's approval -- FR-0006's command.

    ORDER, and every step of it is deliberate. Everything that can refuse without a side effect
    runs first (`_plan`: which kit, which direction, is the staging its own stamp, is a restart
    already pending), then the approval is re-derived and checked against the minted one, then the
    state to compare against is READ, then the interpreter for the installer is looked up -- a pure
    PATH lookup whose refusal says "nothing was changed", which is a sentence that has to be true
    when it is printed rather than restored afterwards (`presets.apply` carries the measurement
    that made this ordering a rule). Only then does anything move.

    WHAT THIS DOES NOT DO, and the caller prints it: it cannot make the new kit's registration take
    effect in the RUNNING session. That is why the marker is ensured on every path out of here that
    MEASURED a change -- and on no other: see `_restart_marker_as_found`.
    """
    with state.lock:
        plan = _plan(state)
        manifest = plan["manifest"]
        if approvals.live_line_approval(state, KIND, manifest) is None:
            raise StateError(
                "no user approval covers this kit update, so nothing was changed. What it would "
                "do: install the '%s' kit %s over the %s this project runs, replacing its hooks, "
                "kernel, roles, settings and constitution. Remedy: ask for it first -- `python "
                "scripts/harness.py request-approval %s` prints the question, and the USER approves "
                "by answering it; then run `python scripts/harness.py %s` again."
                % (plan["kit"], _shown(plan["to"]), _shown(plan["from"]), KIND, COMMAND))
        root, kit_dir = plan["root"], plan["kit_dir"]
        # BEFORE the installer: this is what every failure branch compares against, and after the
        # first copied file there is no way back to it.
        was = _installed_state(root, kit_dir)
        # ...AND THE INTERPRETER SEARCH BELONGS AHEAD OF IT TOO. One number for how long a child
        # may run (`presets.INSTALLER_TIMEOUT`), read through that module rather than copied.
        command = presets.installer_command(plan["kit"])
        try:
            result = subprocess.run(command, cwd=root, capture_output=True,
                                    timeout=presets.INSTALLER_TIMEOUT, **presets.CHILD_TEXT)
        except (OSError, subprocess.SubprocessError) as exc:
            raise _after_a_failed_install(
                root, plan["kit"], kit_dir, was, command,
                "the kit's installer did not complete (%s)." % exc) from None
        if result.returncode != 0:
            raise _after_a_failed_install(
                root, plan["kit"], kit_dir, was, command,
                "the kit's installer refused (exit %d). It said:\n%s\n"
                % (result.returncode,
                   ((result.stderr or "") + (result.stdout or "")).strip()[-1200:]))
        now = _installed_state(root, kit_dir)
        return {"kit": plan["kit"], "from": _shown(plan["from"]), "to": _shown(plan["to"]),
                "installed": _describe(now),
                "marker": ensure_restart_is_forced(root, plan["kit"]),
                "pending_templates": _follow_up(root)}


# -- the installer's own pre-flight, as a process (FR-0044) -------------------------------------

# What the installer is about to do, in the two words this reader tells apart. An INSTALL puts a
# staged bundle on top of whatever is here, so it asks about the stock AND the pin; a ROLLBACK puts
# a bundle this project already ran back, so the stock is not its question -- but the pin is,
# because a pin says "stay as it is" and a rollback changes it too.
INSTALL = "install"
ROLLBACK = "rollback"


def preflight_cli(argv) -> int:
    """`<root> <kit-dir> [rollback]` -- may the installer touch this project? 0 yes, 1 no.

    WHY THE INSTALLER ASKS THIS AND NOT THE OTHER WAY ROUND. Every door into a project's
    enforcement layer goes through `scaffold_team` -- the user running it, `update-kit` starting it
    as a child, and the rollback -- so one reading placed in front of the installer covers all
    three, while a check living only in `update-kit` would leave the doors the user uses open.
    That is also why the verdict must be reached before the first file moves: after the snapshot
    there is a way back, but after the bundle is replaced over a state no command can read there is
    none.

    FAILS CLOSED, and that is a decision about IRREVERSIBILITY rather than about defence
    (DEC-0056 (c)): a reading this function could not complete leaves "may this be overwritten"
    unanswered, and the overwrite it guards is not undoable from inside the project afterwards. Two
    things carry that, and for one round only the second existed: the `unknown` VERDICT, which is
    the reading failing at one document (`classify`), and this `except`, which is the reading
    failing altogether. The message says what to report, so a defect in this reader is a stop with
    a name and not a mystery.
    """
    root = argv[0] if argv else "."
    kit_dir = argv[1] if len(argv) > 1 else ""
    doing = argv[2] if len(argv) > 2 else INSTALL
    try:
        if doing == ROLLBACK:
            assert_no_pin_blocks_a_rollback(root)
            return 0
        # THE STAGED RELEASE IS READ HERE, out of the kit directory the installer was started from,
        # rather than parsed in the shell: `identity` is the one reader of a kit stamp, and a second
        # one written in bash and PowerShell would be two more. The kit is that directory's own
        # name for the same reason -- it is what `presets.kit_dir` builds the path from.
        staged = _stamp(os.path.join(kit_dir, STAGED_VERSION_FILE))
        kit = os.path.basename(os.path.normpath(kit_dir)) if kit_dir else None
        answer = classify(root)
        sys.stdout.write("  [preflight] stock: %s\n" % describe_stock(answer))
        if answer["stock"] == MIXED_STOCK:
            # NOT a refusal -- see `assert_the_stock_may_be_written_over` for why a live V2
            # installation with V1 remnants is updated rather than stopped. It is said out loud
            # here because the validator's finding about the same documents only reaches whoever
            # runs the validator, and the person watching this install may be neither.
            sys.stdout.write(
                "  [preflight] this project holds BOTH: the update goes ahead, and the V1 records "
                "above stay a second copy of state nothing points at until `python "
                "scripts/harness.py migrate --dry-run` is worked through\n")
        assert_the_stock_may_be_written_over(answer)
        assert_not_pinned(root, kit, staged)
    except StateError as refused:
        sys.stderr.write("%s\n" % refused)
        return 1
    except Exception as exc:                                  # noqa: BLE001 -- see the docstring
        sys.stderr.write(
            "the installer's pre-flight could not establish whether %s may be written over (%s: "
            "%s) -- refused (fail-closed); nothing was changed. Remedy: report the gap and name "
            "this message; it is a defect in the reading, not something to retry.\n"
            % (root, type(exc).__name__, exc))
        return 1
    return 0
