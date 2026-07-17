#!/usr/bin/env python3
"""
SessionStart — inject business state so the Office Manager wakes up knowing the situation.

Briefs the manager (role, git branch, first-message procedure), counts the inbox, flags DUE
quarterly reports (a completed quarter with ledger entries but no generated report), flags STALE
compliance-register entries (past review_by), and carries the platform nags: kit-update pending
(escalating) + model/effort sync. Stdlib + git only for the core; yaml parts are best-effort.
Cannot block; emits additionalContext.
"""
import datetime
import json
import os
import re
import subprocess
import sys
import time


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root


def git(cwd, *args):
    try:
        r = subprocess.run(["git", "-C", cwd, *args],
                           capture_output=True, text=True, timeout=5)
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
    """Deterministic sync check: every model_map/effort_map entry must equal the agent's
    frontmatter (the scaffold stamps the maps on update; this catches manual drift)."""
    cfg = os.path.join(cwd, "project_memory", "project_config.yaml")
    agents = os.path.join(cwd, ".claude", "agents")
    if not os.path.isfile(cfg) or not os.path.isdir(agents):
        return []
    try:
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
            # provider-neutral tier aliases (team-kits/model_tiers.yaml): `lead` IS opus etc. —
            # a map saying `lead` with frontmatter `opus` is in sync, not drift.
            canon = {"lead": "opus", "worker": "sonnet", "light": "haiku"}
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
        "model_map/effort_map BEFORE delegating — or, if the map itself is outdated, correct the "
        "map with a reported reason."
    )


def due_reports(cwd):
    """Completed quarters of the current+previous year that HAVE ledger entries but no generated
    report file — an empty quarter (business started later) must not nag forever."""
    import csv
    due = []
    today = datetime.date.today()
    for year in (today.year - 1, today.year):
        ledger = os.path.join(cwd, "ledger", "%d.csv" % year)
        if not os.path.isfile(ledger):
            continue
        quarters_with_rows = set()
        try:
            with open(ledger, encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    eff = (row.get("payment_date") or row.get("doc_date") or "")
                    if eff[:4] == str(year) and len(eff) >= 7:
                        quarters_with_rows.add((int(eff[5:7]) - 1) // 3 + 1)
        except Exception:
            continue
        for q in sorted(quarters_with_rows):
            q_end = datetime.date(year, q * 3, 1) + datetime.timedelta(days=31)
            q_end = q_end.replace(day=1) - datetime.timedelta(days=1)  # last day of the quarter
            if q_end >= today:
                continue
            if not os.path.isfile(os.path.join(cwd, "reports", "euer_%d_Q%d.md" % (year, q))):
                due.append("%d Q%d" % (year, q))
    return due


def stale_register_entries(cwd):
    p = os.path.join(cwd, "project_memory", "compliance_register.yaml")
    if not os.path.isfile(p):
        return 0
    try:
        import yaml  # type: ignore[import-untyped]
        doc = yaml.safe_load(open(p, encoding="utf-8", errors="ignore").read()) or {}
    except Exception:
        return 0
    today = datetime.date.today().isoformat()
    stale = 0
    for entry in (doc.get("register") or []):
        if isinstance(entry, dict):
            rb = str(entry.get("review_by") or "")
            if rb and rb < today:
                stale += 1
    return stale


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    cwd = find_repo_root(data.get("cwd"))
    is_codex = os.environ.get("TEAM_KIT_PROVIDER", "claude").strip().lower() == "codex"

    if is_codex:
        parts = [
            "You are the Office Manager — the foreground session agent the user talks to. Follow "
            "the repository-root AGENTS.md and read .agents/skills/office-manager/SKILL.md; use "
            "project_memory/ as business truth. Do not depend on Claude-only shims or role memory."
        ]
    else:
        parts = ["You are the Office Manager — the session agent the user talks to. Follow ./AGENTS.md."]

    branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if branch:
        dirty = git(cwd, "status", "--porcelain")
        parts.append("Git branch: %s%s." % (branch, " (uncommitted changes present)" if dirty else " (clean)"))

    # version-change announcement: an EXTERNAL restamp leaves staged==local, so the update banner
    # below stays silent — a real PM never told the user the harness had changed. Track the last
    # version THIS repo's sessions have seen (own marker file, session_status-owned).
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
            if seen and seen != local_v:
                parts.append(
                    "KIT UPDATED since this repo's last session: %s -> %s (applied externally). Tell "
                    "the user in your FIRST paragraph what changed for the team, and work through any "
                    "kit_update_pending entries before routine work." % (seen, local_v))
            elif not seen and pending_exists:
                # bootstrap gap (forensics): the marker file is introduced by the very update it
                # should announce — with pending files present, an external update DID just land,
                # so announce it even though the previous version is unknown.
                parts.append(
                    "KIT UPDATED externally to %s (first session with version tracking — the exact "
                    "previous version is unknown). Tell the user in your FIRST paragraph and work "
                    "through the kit_update_pending entries before routine work." % local_v)
            if seen != local_v:
                with open(seen_p, "w", encoding="utf-8") as fh:
                    fh.write(local_v)
    except Exception:
        pass

    if os.path.isdir(os.path.join(cwd, "project_memory")):
        parts.append(
            "project_memory/ exists. On the user's FIRST message (whatever it says — even just "
            "'weiter'), BEFORE acting read project_memory/progress.yaml, business_profile.yaml, "
            "process_definitions.yaml and any DRAFT plan left by the install session, then give the "
            "user a one-line status (open inbox items, running PROCs, due reports, drafts waiting in "
            "outbox/) and ask what to do next. " + (
                "Use the native office-manager skill; optional Codex host memory is not role-specific "
                "or business truth and must not be maintained manually."
                if is_codex else "Also consult your Claude office-manager agent memory."
            )
        )
    else:
        parts.append(
            "No project_memory/ yet. Run your startup gate: create project_memory/ from the kit "
            "templates (init script), run the onboarding interview, confirm the preset. Do not "
            "delegate before project_config.yaml and business_profile.yaml exist."
        )

    try:
        inbox = os.path.join(cwd, "inbox")
        if os.path.isdir(inbox):
            items = [f for f in os.listdir(inbox)
                     if not f.startswith(".") and f.lower() not in ("readme.txt", "readme.md")]
            if items:
                parts.append("INBOX: %d unprocessed item(s) (%s%s)."
                             % (len(items), ", ".join(sorted(items)[:5]),
                                " …" if len(items) > 5 else ""))
    except Exception:
        pass

    try:
        due = due_reports(cwd)
        if due:
            parts.append(
                "REPORT DUE: quarterly statement(s) missing for %s — run `python "
                "scripts/euer_report.py` per quarter (deterministic; the bookkeeper adds _notes.md)."
                % ", ".join(due))
    except Exception:
        pass

    try:
        stale = stale_register_entries(cwd)
        if stale:
            parts.append(
                "COMPLIANCE REGISTER: %d entr%s past review_by — schedule a compliance-researcher "
                "watch run (per its PROC)." % (stale, "y is" if stale == 1 else "ies are"))
    except Exception:
        pass

    # kit-update detection: compare the repo's installed kit stamp with the staged kit version.
    try:
        kit = ""
        cpath = os.path.join(cwd, "CLAUDE.md")
        if os.path.isfile(cpath):
            with open(cpath, encoding="utf-8", errors="ignore") as fh:
                m = re.search(r"agents-and-skills:team-kit\s+([\w-]+)", fh.readline())
            kit = m.group(1) if m else ""
        if kit:
            staged_p = os.path.join(os.path.expanduser("~"), ".claude", "team-kits", kit, "VERSION")
            local_p = os.path.join(cwd, ".claude", "kit_version")
            staged = open(staged_p, encoding="utf-8").read().lstrip("\ufeff").strip() if os.path.isfile(staged_p) else ""
            local = open(local_p, encoding="utf-8").read().lstrip("\ufeff").strip() if os.path.isfile(local_p) else ""
            if staged and staged != local:
                lv = local.splitlines()[0].replace("version: ", "") if local else "no version stamp"
                sv = staged.splitlines()[0].replace("version: ", "")
                parts.append(
                    "KIT UPDATE AVAILABLE: the staged '%s' kit (%s) differs from this repo's installed kit "
                    "(%s). Propose the update to the user; on their OK run the scaffold_team script and "
                    "then init_project_memory (both safe: backup first, copy-if-absent — project_memory "
                    "content is NEVER overwritten), then ask for a session restart. The scaffold re-stamps "
                    "model:/effort: from the maps; work through any kit_update_pending files afterwards."
                    % (kit, sv, lv)
                )
                if is_codex:
                    parts.append(
                        "CODEX KIT UPDATE PROCEDURE: after explicit user approval, run the full "
                        "scaffold with explicit filesystem permission escalation because .codex/ and "
                        ".agents/skills/ are read-only harness paths. Never run the provider generator "
                        "alone. Then verify generated TOMLs, open /hooks, review and trust the changed "
                        "bundle hash, and start a new session before delegating."
                    )
    except Exception:
        pass

    # kit-update follow-through: escalating nag until the pending backlog is worked through.
    try:
        pend_lines, pend_files = [], []
        for suffix in ("repo", "memory"):
            p = os.path.join(cwd, ".claude", "kit_update_pending." + suffix)
            if os.path.isfile(p):
                pend_files.append(suffix)
                with open(p, encoding="utf-8", errors="ignore") as fh:
                    pend_lines += [ln.strip()[2:] for ln in fh if ln.strip().startswith("- ")]
        state_p = os.path.join(cwd, ".claude", "kit_update_pending.state")
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
            urgency = ("" if sessions <= 1 else
                       " OPEN SINCE %s — this is the %d. session that sees it. Work through at least ONE "
                       "entry NOW (or log a conscious skip in progress.yaml log:) before feature work; "
                       "acknowledging it once and moving on is the documented failure mode." % (first, sessions))
            parts.append(
                "KIT UPDATE NOT FINISHED (%s): %d file(s) still diverge from the kit templates (%s%s) "
                "— diff each against the kit template, merge the kit's fixes via the owning role (or "
                "document a conscious skip in progress.yaml log:), then DELETE the pending file(s). "
                "Name this backlog in the FIRST paragraph of your reply to the user — a real PM "
                "mentioned it once in passing and never returned.%s"
                % ("+".join(pend_files), len(pend_lines), "; ".join(pend_lines[:5]),
                   " …" if len(pend_lines) > 5 else "", urgency)
            )
        elif os.path.isfile(state_p):
            try:
                os.remove(state_p)  # backlog cleared -> reset the counter
            except Exception:
                pass
    except Exception:
        pass

    # model/effort sync: nag on any drift from the user-confirmed maps BEFORE delegating.
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


    # Rename tripwire: a MATURE project whose Claude auto-memory dir is missing usually means the
    # folder was renamed — the memory stays orphaned under the OLD path key (a real rename cost
    # the PM its cross-session memory unnoticed; the same rename silently detached a compose
    # volume). Heuristic + hint only; wrong key derivation just stays silent.
    try:
        progress = os.path.join(cwd, "project_memory", "progress.yaml")
        seasoned = (os.path.isfile(progress)
                    and open(progress, encoding="utf-8", errors="ignore").read().count("\n  - ") >= 10)
        if seasoned:
            key = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(cwd))
            mem = os.path.join(os.path.expanduser("~"), ".claude", "projects", key, "memory")
            if not os.path.isdir(mem):
                parts.append(
                    "RENAME TRIPWIRE: this project looks mature but has NO Claude auto-memory "
                    "under its current path key — if the folder was recently renamed, the "
                    "memory (and Codex trust) sit under the OLD key: check "
                    "~/.claude/projects/<old-name> and move the memory dir; also verify docker "
                    "compose volumes still attach (pin `name:` in compose)."
                )
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
