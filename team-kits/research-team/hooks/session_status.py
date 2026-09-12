#!/usr/bin/env python3
"""
SessionStart() — inject project state so the Research Lead wakes up knowing the situation.

Reinforces the "session 1 = setup, session 2+ = work" model: when the project-manager
session agent starts, it is reminded that it IS the Research Lead, told the git branch,
and pointed at project_memory/ to read before acting. Stdlib + git only (no YAML
dependency), so it never fails on a fresh machine. Cannot block; emits additionalContext.

It also names the recurring project audit when it is due for the current ISO week (FR-0038).
That answer is not this kit's own: role, run record and wording live in the shared `_routine`,
mirrored in all three kits. The hook REPORTS it; the PM proposes it to the user and spawns it
(`DEC-0028`).
"""
import sys
import os
import json
import re
import time


# NO BYTECODE FROM A HOOK RUN, for the reason `_gate.py` states at length: this file lives in
# the hashed enforcement bundle and imports its neighbours out of it, so caching them would
# change the bundle by being run — `hooks_trust_required` at the next session, blamed on
# anything but the hook that caused it. The kits register this hook as `python -B`, so in
# production the flag is redundant; it is here because a hook is also started directly — by the
# test suite, by a person diagnosing one — and the measurement must not depend on how it was
# started. `_gate.py` carries the same line for the gates it launches; this one is not launched.
sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _compat
from _root import find_repo_root
from _compat import run_captured


def git(cwd, *args):
    try:
        r = run_captured(["git", "-C", cwd, *args], timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _parse_map(txt, name):
    """Parse a flat `<name>:` block of `key: value` lines (stdlib only — no yaml import here by
    design, so this hook never fails on a fresh machine). Comments and blank lines are skipped;
    the block ends at the first non-indented content line."""
    m = re.search(r"(?m)^%s:[ \t]*(?:#.*)?$" % name, txt)
    if not m:
        return {}
    out = {}
    for line in txt[m.end():].splitlines():
        if line.strip().startswith("#") or not line.strip():
            continue
        mm = re.match(r'''[ \t]+([A-Za-z0-9_-]+):[ \t]*["']?([A-Za-z0-9_.-]+)["']?''', line)
        if mm:
            out[mm.group(1)] = mm.group(2)
        elif not line.startswith((" ", "\t")):
            break  # left the block
    return out


def model_effort_mismatches(cwd):
    """Deterministic §11 sync check: every model_map/effort_map entry must equal the agent's
    frontmatter. The scaffold resets frontmatter to kit defaults — when a kit update happens
    outside a session, nothing else reminds the PM (a real project ran its user-approved opus
    frontend on sonnet for two days this way)."""
    cfg = os.path.join(cwd, "project_memory", "project_config.yaml")
    agents = os.path.join(cwd, ".claude", "agents")
    if not os.path.isfile(cfg) or not os.path.isdir(agents):
        return []
    try:
        # utf-8-sig: a PS 5.1 Set-Content/Out-File writes a BOM — without stripping it the first
        # line never matches and a perfectly synced repo would nag forever (audit finding)
        txt = open(cfg, encoding="utf-8-sig", errors="ignore").read()
    except Exception:
        return []
    mism = []
    for mapname, field in (("model_map", "model"), ("effort_map", "effort")):
        for role, want in _parse_map(txt, mapname).items():
            ap = os.path.join(agents, role + ".md")
            if not os.path.isfile(ap):
                continue
            try:
                raw = open(ap, encoding="utf-8-sig", errors="ignore").read()
            except Exception:
                continue
            fm = raw.split("---", 2)[1] if raw.startswith("---") and raw.count("---") >= 2 else ""
            got = re.search(r'''(?m)^%s:[ \t]*["']?([A-Za-z0-9_.-]+)["']?''' % field, fm)
            have = got.group(1) if got else "MISSING"
            # a RAW tier alias in the INSTALLED frontmatter is broken regardless of the map:
            # Claude cannot resolve `model: worker` and the subagent dies at spawn ("model may
            # not exist" — a real bookkeeper crashed; an OneDrive-synced scaffold write had
            # left the alias unresolved and the canonicalized compare below saw "in sync").
            if field == "model" and have in ("lead", "worker"):
                mism.append("%s frontmatter model='%s' is an UNRESOLVED tier alias — subagents "
                            "crash at spawn; re-run the scaffold (or set the real model name)"
                            % (role, have))
                continue
            # provider-neutral tier aliases (team-kits/model_tiers.yaml `aliases:`): `lead` IS
            # opus etc. — a map saying `lead` with frontmatter `opus` is in sync, not drift. The
            # third entry was `light: haiku`, an alias that table retired (DEC-0076: three rungs
            # per provider, no light row), so this hook translated a value no kit source may
            # carry and no installer produces any more (BUG-0250).
            canon = {"lead": "opus", "worker": "sonnet"}
            if canon.get(have, have) != canon.get(want, want):
                mism.append("%s %s=%s (map says %s)" % (role, field, have, want))
    return mism


def model_effort_sync_guidance():
    """Return provider-safe recovery instructions for model/effort drift.

    The installed Claude agent frontmatter is the shared generator source. Claude may repair that
    source directly; Codex artifacts are generated/read-only and must never become an independent
    source of truth.
    """
    if os.environ.get("TEAM_KIT_PROVIDER", "claude").strip().lower() == "codex":
        return (
            "Do NOT edit .codex/agents/*.toml or one isolated provider source. Ask the user to "
            "confirm a full scaffold re-sync from project_config.yaml; only after confirmation run "
            "the scaffold (it invokes the provider generator), with explicit filesystem permission "
            "escalation when required by the read-only harness paths. Then verify the generated "
            ".codex/agents/*.toml model/effort mappings, review/re-trust the changed hook bundle in "
            "/hooks, and start a new session BEFORE delegating. Never run the provider generator "
            "alone. If the map itself is outdated, correct it with a reported reason first."
        )
    return (
        "Re-sync each named agent's model:/effort: frontmatter line in .claude/agents/ to "
        "model_map/effort_map (§11) BEFORE delegating — or, if the map itself is outdated, "
        "correct the map with a reported reason."
    )


def main():
    # BOUNDED read (spec II.4): a raw `json.load(sys.stdin)` buffers a payload of any size.
    # `tolerate_overflow=True` because this hook only INFORMS; it must never refuse a call.
    data = _compat.load(tolerate_overflow=True)
    cwd = find_repo_root(data.get("cwd"))
    is_codex = os.environ.get("TEAM_KIT_PROVIDER", "claude").strip().lower() == "codex"

    if is_codex:
        parts = [
            "You are the Research Lead (Project Manager) — the foreground session agent the user "
            "talks to. Follow the repository-root AGENTS.md and read "
            ".agents/skills/project-manager/SKILL.md; use project_memory/ as project truth. Do not "
            "depend on Claude-only shims or role memory."
        ]
    else:
        parts = ["You are the Research Lead (Project Manager) — the session agent the user talks to. Follow ./AGENTS.md."]

    branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if branch:
        dirty = git(cwd, "status", "--porcelain")
        parts.append("Git branch: %s%s." % (branch, " (uncommitted changes present)" if dirty else " (clean)"))

    # version-change announcement: an EXTERNAL restamp leaves staged==local, so the update banner
    # below stays silent — a real PM never told the user the harness had changed and dove straight
    # into feature work. Track the last version THIS repo's sessions have seen (own marker file,
    # session_status-owned; the pending-state counters are reset by the scaffold and must not
    # clobber this).
    try:
        local_v = ""
        lp = os.path.join(cwd, ".claude", "kit_version")
        if os.path.isfile(lp):
            lines_v = open(lp, encoding="utf-8").read().lstrip("\ufeff").strip().splitlines()
            local_v = lines_v[0].replace("version: ", "") if lines_v else ""
        if local_v:
            seen_p = os.path.join(cwd, ".claude", "kit_last_seen_version")
            seen = ""
            if os.path.isfile(seen_p):
                seen = open(seen_p, encoding="utf-8").read().strip()
            pending_exists = any(
                os.path.isfile(os.path.join(cwd, ".claude", "kit_update_pending." + s))
                for s in ("repo", "memory"))
            # one-shot marker the SCAFFOLD writes (previous version): survives however many
            # broken/parallel restarts happen in between — the pure last_seen delta got lost
            # when no clean SessionStart followed a mid-session update (audit: a live repo sat
            # two days without the banner), and it mislabeled PM-run updates as "external".
            marker_p = os.path.join(cwd, ".claude", "kit_updated_from")
            marker = ""
            if os.path.isfile(marker_p):
                mlines = open(marker_p, encoding="utf-8-sig").read().strip().splitlines()
                marker = mlines[0].replace("version: ", "") if mlines else ""
            if marker and marker != local_v:
                parts.append(
                    "KIT UPDATED: %s -> %s (the update itself is COMPLETE — do NOT run the "
                    "scaffold again). Tell the user in your FIRST paragraph what changed for the "
                    "team, and work through any kit_update_pending MERGE tasks before feature "
                    "work." % (marker, local_v))
            elif seen and seen != local_v:
                parts.append(
                    "KIT UPDATED since this repo's last session: %s -> %s. Tell the user in your "
                    "FIRST paragraph what changed for the team, and work through any "
                    "kit_update_pending entries before feature work." % (seen, local_v))
            elif not seen and pending_exists:
                # bootstrap gap (forensics): the marker file is introduced by the very update it
                # should announce — with pending files present, an update DID just land, so
                # announce it even though the previous version is unknown.
                parts.append(
                    "KIT UPDATED to %s (first session with version tracking — the exact previous "
                    "version is unknown). Tell the user in your FIRST paragraph and work through "
                    "the kit_update_pending entries before feature work." % local_v)
            if marker:
                try:
                    os.remove(marker_p)  # consumed — the announcement fires exactly once
                except Exception:
                    pass
            if seen != local_v:
                with open(seen_p, "w", encoding="utf-8") as fh:
                    fh.write(local_v)
    except Exception:
        pass

    if os.path.isdir(os.path.join(cwd, "project_memory")):
        parts.append(
            "project_memory/ exists. On the user's FIRST message (whatever it says — even just 'weiter'), "
            "BEFORE acting read project_memory/generated/session_brief.yaml — the kernel's rollup of "
            "active roots, tasks, open approvals and validator findings — plus the DRAFT research "
            "question(s) and product/masterplan.md left by the install session, then give the user a "
            "one-line status (active RQ, running experiments, pending approvals) and ask what to do next. "
            "If the brief is missing or stale, regenerate it (`python scripts/harness.py generate-session-brief`, which "
            "needs `--kit/--kit-version/--enforcement` — see `python scripts/harness.py --help`) instead "
            "of reconstructing the state by hand. " + (
                "Use the native project-manager skill; optional Codex host memory is not role-specific "
                "or project truth and must not be maintained manually."
                if is_codex else "Also consult your Claude project-manager agent memory."
            )
        )
    else:
        parts.append(
            "No project_memory/ yet. If the user wants to start work, run your startup gate: create "
            "project_memory/ from the kit templates, confirm the team preset + per-specialist models, "
            "then proceed. Do not delegate before project_config.yaml exists."
        )

    # THE WALLS. A kit document a registered gate refuses work over, still carrying its shipped
    # template, is the one project state no session can work its way out of — and until now it was
    # first noticed as a refusal at the end of a work cycle. The derivation and the sentence both
    # live in `_kernel` (one text, three kits); only this adapter is per-kit.
    #
    # `disarm()` IMMEDIATELY AFTER THE IMPORT, and it is not tidiness: importing `_kernel` arms the
    # gates' excepthook, which turns any later escape into `os._exit(2)` — that skips the stdout
    # flush at the end of this function, so a briefing hook would lose the ENTIRE briefing over an
    # unrelated error. This hook informs and must never refuse.
    try:
        import _kernel
        _kernel.disarm()
        wall_briefing = _kernel.gated_document_briefing(cwd)
        if wall_briefing:
            parts.append(wall_briefing)
        # THE DISPATCHES NOTHING IS BEHIND ANY MORE (DEC-0044 / BUG-0042). Also in `_kernel`, one
        # text for three kits, and passed this session's own id: that id is the whole term the
        # sweep decides on, so a hook that forgot it would sweep nothing at all rather than sweep
        # wrongly.
        orphan_briefing = _kernel.orphaned_dispatch_briefing(cwd, data.get("session_id"))
        if orphan_briefing:
            parts.append(orphan_briefing)
        # THE WORK BOOKED AS FINISHED THAT NOTHING MEASURED (BUG-0060). Also in `_kernel`, and for
        # the same reason: the decision is the kernel's, so this briefing and `validate` cannot
        # answer it differently.
        verdict_briefing = _kernel.unverified_delivery_briefing(cwd)
        if verdict_briefing:
            parts.append(verdict_briefing)
    except BaseException:
        pass

    # THE RECURRING AUDIT RUN THIS PROJECT OWES (FR-0038). The record, the weekly period and the
    # wording all live in the shared `_routine`, so the three kits cannot drift into three answers;
    # this adapter only prints. IT PROPOSES AND NOTHING MORE -- `DEC-0028`: the hook reports, the PM
    # spawns. AND IF THE MODULE CANNOT BE LOADED THE BRIEFING SAYS SO, because a swallowed failure
    # here reads as "nothing is due" -- the same wrong reading the kit-merge notice below refuses to
    # allow (`tools/test_routine_feed.py::
    # test_a_missing_routine_module_is_a_line_in_the_briefing_rather_than_silence`).
    try:
        import _routine
        routine_notice = _routine.notice(cwd)
        if routine_notice:
            parts.append(routine_notice)
    except Exception as exc:
        parts.append(
            "ROUTINE CHECK UNAVAILABLE (%s): whether the recurring project audit is due could not "
            "be determined here, so this briefing says nothing about it. Do not read that as a run "
            "that happened." % exc.__class__.__name__)

    # kit-update detection: compare the repo's installed kit stamp with the staged kit version.
    try:
        kit = ""
        cpath = os.path.join(cwd, "CLAUDE.md")
        if os.path.isfile(cpath):
            with open(cpath, encoding="utf-8", errors="ignore") as fh:
                first_line = fh.readline().lstrip("\ufeff")
            # DEC-0039 / BUG-0011: the marker counts only as the shim line scaffold_team writes on
            # line 1 (`<!-- agents-and-skills:team-kit <team> -->`), not as a bare occurrence
            # anywhere on it — a quote, prose, a negation or a `#` comment that names the marker must
            # NOT read as an install, nor a line that carries anything after the `-->`. BOM/CRLF/
            # leading-space tolerant so real installs keep matching.
            m = re.match(r"\s*<!--\s*agents-and-skills:team-kit\s+([\w-]+)\s*-->\s*$", first_line)
            kit = m.group(1) if m else ""
        if kit:
            # THE DIRECTION IS THE KERNEL'S ANSWER AND NOT THIS HOOK'S (FR-0006): `update-kit`
            # refuses on the same verdict, so a briefing that ordered the two stamps itself
            # could OFFER an update that command then REFUSES. `_kernel.kit_update_verdict`
            # carries the derivation and the one case this block may not fall silent in (a
            # kernel it cannot reach); the four sentences below are this kit's own.
            import _kernel
            verdict, lv, sv, why = _kernel.kit_update_verdict(cwd, kit)
            if verdict == "unclear":
                parts.append(
                    "KIT VERSION MISMATCH: the staged '%s' kit (%s) differs from this repo's "
                    "installed kit (%s), and at least one of the two stamps carries no readable "
                    "version, so which is newer cannot be determined here (%s). Report it to "
                    "the user and let them decide; `update-kit` refuses it for the same "
                    "reason." % (kit, sv, lv, why))
            elif verdict == "downgrade":
                parts.append(
                    "KIT DOWNGRADE OFFERED, do NOT install it: the staged '%s' kit (%s) is OLDER "
                    "than this repo's installed kit (%s). Installing it would prune files this "
                    "project needs and leave others in place; `update-kit` refuses it. Tell the "
                    "user their staging is behind and let them update the staging (the harness "
                    "installer) first." % (kit, sv, lv))
            elif verdict == "content":
                parts.append(
                    "KIT CONTENT MISMATCH: the staged '%s' kit and this repo's installed kit carry "
                    "the SAME version stamp (%s) but different content hashes — one of the two was "
                    "changed without a version bump. That is a finding to report, not an update to "
                    "run, and `update-kit` refuses it." % (kit, sv))
            elif verdict == "update":
                parts.append(
                    "KIT UPDATE AVAILABLE: the staged '%s' kit (%s) is NEWER than this repo's "
                    "installed kit (%s). Propose it to the user in one sentence, with what it "
                    "costs: a session restart. On their OK you install it YOURSELF, in two "
                    "commands — `python scripts/harness.py request-approval kit_update` prints the "
                    "approval question (relay it VERBATIM; the USER answers it), then `python "
                    "scripts/harness.py update-kit` installs it. That command re-reads both stamps "
                    "when it runs, so a PARALLEL session that already updated is caught there and "
                    "not by this briefing, which is a snapshot from session start. It refuses a "
                    "downgrade, a staging that no longer hashes to its own stamp and a project "
                    "already waiting for a restart, and it runs the kit's own installer — never "
                    "hand-merge harness files. AFTERWARDS THIS SESSION IS STOPPED: the handover "
                    "marker is set, so specialist spawns are refused here; with the harness's "
                    "user-global handover guard installed, further work-engine commands and "
                    "product writes as well. Diverged repo templates are recorded in "
                    ".claude/kit_update_pending.* — work those through in the NEXT session, where "
                    "gates may also require newly added fields in existing YAMLs."
                    % (kit, sv, lv)
                )
                if is_codex:
                    parts.append(
                        "CODEX KIT UPDATE NOTE: `update-kit` starts the kit's installer as a CHILD "
                        "of this session, and .codex/ plus .agents/skills/ are read-only harness "
                        "paths there — that combination is NOT measured on Codex. If the installer "
                        "refuses on one of them, the command reports its message together with the "
                        "state it read back; hand that to the user instead of retrying. Never run "
                        "the provider generator alone. After a successful update, verify the "
                        "generated TOMLs, open /hooks, review and trust the changed bundle hash, "
                        "and start a new session before delegating."
                    )
            elif verdict == "pinned":
                parts.append(
                    "KIT UPDATE AVAILABLE BUT THIS PROJECT IS PINNED — do NOT propose installing "
                    "it: the staged '%s' kit (%s) is newer than this repo's installed kit (%s), "
                    "and the user has held this project at the release it runs. %s\nEvery door "
                    "refuses here: `update-kit`, the installer run by hand, and a rollback. Tell "
                    "the user the newer release exists AND that their own pin is what holds it — "
                    "asking for an approval first would spend their answer on a command that then "
                    "refuses. `python scripts/harness.py unpin-kit` prints what ends the pin; only "
                    "the USER can do it, and no command of yours can."
                    % (kit, sv, lv, why)
                )
    except Exception:
        pass

    # kit-update follow-through: diverged tooling the scripts recorded stays pending until the PM
    # merged (or consciously skipped) every line and DELETED the file — [kept] lines alone were
    # ignored in a real project, so kit fixes silently never arrived. The nag ESCALATES across
    # sessions (a real PM acknowledged it once at 12:08 and never returned for 7 hours).
    # ...and the list is RE-VALIDATED here rather than believed: an entry whose file matches its kit
    # template again is not reported, and a list with no entry left is DELETED. Measured on the
    # user's real office project (BUG-0068): four scripts stayed on it while being byte-identical to
    # the template, so the nag sent a non-technical user to the terminal for files that already
    # matched. Which entries are still true is `kernel.kitupdate.outstanding_pending`, reached
    # through `_kernel.pending_merge_backlog`; a project whose kernel cannot be reached answers None
    # and nags on the file as WRITTEN, so a damaged project loses no backlog.
    # THE IMPORT STANDS IN ITS OWN try, and that is not tidiness: inside the one below, a kernel
    # shim that cannot be imported took the WHOLE nag with it (measured: no backlog reported at all
    # while the pending file stood), which is the opposite of what `pending_merge_backlog` promises
    # for a damaged project. Unreachable means `backlog = None`, which nags on the file as WRITTEN.
    backlog = None
    try:
        import _kernel
        backlog = _kernel.pending_merge_backlog(cwd)
    except Exception:
        backlog = None
    try:
        pend_lines, pend_files, resolved, unreadable = [], [], [], []
        # ...and this stays True only while every reported entry was really held against a template
        # this process could open. `backlog is not None` means the kernel ANSWERED, which is not the
        # same thing and must never be read as it.
        really_checked = backlog is not None
        for suffix in ("repo", "memory"):
            p = os.path.join(cwd, ".claude", "kit_update_pending." + suffix)
            if not os.path.isfile(p):
                continue
            if backlog is not None and suffix in backlog:
                if not backlog[suffix]["read"]:
                    # EXISTS and could not be opened: what it asks for is UNKNOWN, never "nothing".
                    # Reading the empty entry list as "resolved" would delete a backlog nobody read (BUG-0068).
                    unreadable.append(p)
                    really_checked = False
                    continue
                entries = backlog[suffix]["entries"]
                really_checked = really_checked and backlog[suffix]["checked"]
            else:
                try:
                    with open(p, encoding="utf-8", errors="ignore") as fh:
                        entries = [ln.strip()[2:] for ln in fh if ln.strip().startswith("- ")]
                except Exception:
                    unreadable.append(p)
                    really_checked = False
                    continue
                really_checked = False
            if entries:
                pend_files.append(suffix)
                pend_lines += entries
            else:
                resolved.append(p)
        for p in resolved:
            try:
                os.remove(p)  # READ, and nothing left to merge — the file is the nag, so it goes
            except Exception:
                pass
        state_p = os.path.join(cwd, ".claude", "kit_update_pending.state")
        if unreadable:
            parts.append(
                "KIT MERGE BACKLOG UNREADABLE: %s exists and could NOT be opened here, so what it "
                "still asks for is unknown — it was NOT resolved and was NOT deleted. Do not read "
                "the absence of a file list as an empty backlog: open the file yourself, or tell "
                "the user this project carries a pending kit-merge file the session cannot read (a "
                "permission denial and a cloud placeholder that is not downloaded both look like "
                "this). Name it in the FIRST paragraph of your reply to the user."
                % "; ".join(os.path.relpath(p, cwd).replace(os.sep, "/") for p in unreadable))
        if pend_lines:
            # resumes/compactions are NOT new sessions: post-limit resumes inflated the counter to
            # "3rd session" before the PM ever saw the notice once (forensics) — the scolding text
            # then misattributes blame. Only a real session start increments.
            is_resume = str(data.get("source") or "") in ("resume", "compact")
            sessions, first = 1, time.strftime("%Y-%m-%d")
            try:
                with open(state_p, encoding="utf-8") as fh:
                    st = json.load(fh)
                prev = int(st.get("sessions", 0))
                sessions = prev if (is_resume and prev >= 1) else prev + 1
                first = st.get("first_seen", first)
            except Exception:
                pass
            try:
                with open(state_p, "w", encoding="utf-8") as fh:
                    json.dump({"sessions": sessions, "first_seen": first}, fh)
            except Exception:
                pass
            # no scolding on the first day: every window/reopen counts as a session, and a user
            # actively working the backlog hit "5th session" within ONE evening (audit)
            today = time.strftime("%Y-%m-%d")
            urgency = ("" if sessions <= 1 or first == today else
                       " OPEN SINCE %s — this is the %d. session that sees it. Work through at least ONE "
                       "entry NOW (or record a conscious skip as a decision item) before feature work; "
                       "acknowledging it once and moving on is the documented failure mode." % (first, sessions))
            # the CLAIM is made only where a comparison really HAPPENED — not merely where the
            # kernel answered. Hanging it on the answer printed "each entry was re-checked" over a
            # project whose staged kit is not on this machine at all, where nothing had been opened.
            checked = (" Each entry was re-checked against the kit template at this session start."
                       if really_checked else
                       " NOT re-checked here (the kit templates could not be read — an unreachable "
                       "kernel, or the kit is not staged on this machine), so an entry may already "
                       "match its kit template again — diff before you merge.")
            parts.append(
                "KIT MERGE BACKLOG (%s) — the kit VERSION is already current; do NOT run the "
                "scaffold again because of these (it cannot resolve them). %d "
                "project file(s) still diverge from the kit templates (%s%s) — diff each against "
                "the kit template, merge the kit's fixes via the owning role (or record a "
                "conscious skip as a decision item), then DELETE the pending file(s).%s Name "
                "this backlog in the FIRST paragraph of your reply to the user.%s"
                % ("+".join(pend_files), len(pend_lines), "; ".join(pend_lines[:5]),
                   " …" if len(pend_lines) > 5 else "", checked, urgency)
            )
        elif not unreadable and os.path.isfile(state_p):
            try:
                os.remove(state_p)  # backlog CLEARED -> reset the counter; unknown is not cleared
            except Exception:
                pass
    except Exception:
        pass

    # §11 model/effort sync: scaffold resets agent frontmatter to kit defaults — nag on any drift
    # from the user-confirmed maps BEFORE the PM delegates on the wrong tier.
    try:
        mism = model_effort_mismatches(cwd)
        if mism:
            parts.append(
                "MODEL/EFFORT OUT OF SYNC with project_config.yaml: %s%s. %s"
                % ("; ".join(mism[:6]), " …" if len(mism) > 6 else "",
                   model_effort_sync_guidance())
            )
    except Exception:
        pass


    # PREVIOUS-SESSION handover: point the PM at the last transcript so settled decisions are
    # not re-litigated (a real office PM re-proposed something the prior session had already
    # resolved — project_memory is the truth, but recently-unlogged context lives in the
    # transcript tail). Hint only; reading is the PM's judgment call.
    try:
        key = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(cwd))
        tdir = os.path.join(os.path.expanduser("~"), ".claude", "projects", key)
        sid = str(data.get("session_id") or "")
        # no session_id -> no hint: without the exclusion the newest transcript IS our own
        # session and the PM would be told to skim itself (audit)
        if sid and os.path.isdir(tdir):
            cands = [os.path.join(tdir, f) for f in os.listdir(tdir)
                     if f.endswith(".jsonl") and sid not in f]
            if cands:
                prev_t = max(cands, key=os.path.getmtime)
                age_h = (time.time() - os.path.getmtime(prev_t)) / 3600.0
                parts.append(
                    "PREVIOUS SESSION transcript: %s (last activity %.0fh ago). Before resuming "
                    "ongoing work, skim its END (final ~150 lines) for where that session "
                    "stopped and what was already decided — never re-open settled decisions. "
                    "project_memory stays the source of truth; use the transcript to catch what "
                    "the last session failed to log there." % (prev_t, age_h))
    except Exception:
        pass

    # Rename/move tripwire: remember the project's absolute path in a gitignored per-machine
    # state file; a recorded path differing from the current one is DETERMINISTIC evidence the
    # folder was renamed or moved (a real rename orphaned the PM's auto-memory under the old
    # path key and silently detached a compose volume). The previous absence-of-memory
    # heuristic false-fired on every mature project without auto-memory — memory is opt-in
    # (audit finding, empirically two of three live projects). First run just records.
    try:
        state_dir = os.path.join(cwd, ".claude")
        path_state = os.path.join(state_dir, "project_path.state")
        current = os.path.abspath(cwd)
        recorded = ""
        if os.path.isfile(path_state):
            recorded = open(path_state, encoding="utf-8", errors="ignore").read().strip()
        if recorded and os.path.normcase(recorded) != os.path.normcase(current):
            old_key = re.sub(r"[^A-Za-z0-9]", "-", recorded)
            parts.append(
                "PROJECT PATH CHANGED since the last session (was: %s). If the folder was "
                "renamed/moved on this machine: Claude auto-memory and Codex trust may sit "
                "under the OLD key ~/.claude/projects/%s — move the memory dir and re-approve "
                "trust; also verify docker compose volumes still attach (pin `name:` in "
                "compose). A fresh clone/new machine can ignore this."
                % (recorded, old_key)
            )
        if os.path.isdir(state_dir) and recorded != current:
            with open(path_state, "w", encoding="utf-8") as fh:
                fh.write(current + "\n")
    except Exception:
        pass

    out = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": " ".join(parts),
        }
    }
    sys.stdout.write(json.dumps(out))
    sys.exit(0)


if __name__ == "__main__":
    main()
