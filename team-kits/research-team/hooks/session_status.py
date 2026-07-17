#!/usr/bin/env python3
"""
SessionStart — inject project state so the Research Lead wakes up knowing the situation.

Reinforces the "session 1 = setup, session 2+ = work" model: when the project-manager
session agent starts, it is reminded that it IS the Research Lead, told the git branch,
and pointed at project_memory/ to read before acting. Stdlib + git only (no YAML
dependency), so it never fails on a fresh machine. Cannot block; emits additionalContext.
"""
import sys
import os
import json
import re
import subprocess
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
        "model_map/effort_map (§11) BEFORE delegating — or, if the map itself is outdated, "
        "correct the map with a reported reason."
    )


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
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
            if seen and seen != local_v:
                parts.append(
                    "KIT UPDATED since this repo's last session: %s -> %s (applied externally). Tell "
                    "the user in your FIRST paragraph what changed for the team, and work through any "
                    "kit_update_pending entries before feature work." % (seen, local_v))
            elif not seen and pending_exists:
                # bootstrap gap (forensics): the marker file is introduced by the very update it
                # should announce — with pending files present, an external update DID just land,
                # so announce it even though the previous version is unknown.
                parts.append(
                    "KIT UPDATED externally to %s (first session with version tracking — the exact "
                    "previous version is unknown). Tell the user in your FIRST paragraph and work "
                    "through the kit_update_pending entries before feature work." % local_v)
            if seen != local_v:
                with open(seen_p, "w", encoding="utf-8") as fh:
                    fh.write(local_v)
    except Exception:
        pass

    if os.path.isdir(os.path.join(cwd, "project_memory")):
        parts.append(
            "project_memory/ exists. On the user's FIRST message (whatever it says — even just 'weiter'), "
            "BEFORE acting read project_memory/progress.yaml, research_questions.yaml, any DRAFT "
            "plan/masterplan left by the install session, and any open experiment/review reports, then "
            "give the user a one-line status (active RQ, running experiments, pending validation) and ask "
            "what to do next. " + (
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
                    "(%s) — usually a newer harness. Propose the update to the user; on their OK run the "
                    "scaffold_team script and then init_project_memory (both safe: backup first, "
                    "copy-if-absent — project_memory content is NEVER overwritten), then ask for a session "
                    "restart. Never hand-merge harness files. The scaffold re-applies the recorded preset "
                    "from project_config.yaml and re-stamps each agent's model:/effort: from "
                    "model_map/effort_map automatically (verify; this hook nags on drift), and it records "
                    "diverged files in .claude/kit_update_pending.* — work those through. After updating, "
                    "gates may require newly added fields in existing YAMLs — fill those small deltas."
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

    # kit-update follow-through: diverged tooling the scripts recorded stays pending until the PM
    # merged (or consciously skipped) every line and DELETED the file — [kept] lines alone were
    # ignored in a real project, so kit fixes silently never arrived. The nag ESCALATES across
    # sessions (a real PM acknowledged it once at 12:08 and never returned for 7 hours).
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
