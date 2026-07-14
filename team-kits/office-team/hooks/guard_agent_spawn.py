#!/usr/bin/env python3
"""
PreToolUse(Agent|Task) guard — only role-based specialist spawns are allowed.

Kills the `subagent_type=None` / generic-agent spawn bug from the real test run.
The PM (main agent) MUST spawn specialists by their exact role. This hook reads the
allowed roles from the installed `./.claude/agents/*.md` basenames, so it is
kit-agnostic and always correct. Exit 2 + stderr blocks; uncertainty -> exit 0.

Also the V14 backstop: `run_in_background` MUST be set EXPLICITLY on every spawn. The platform
defaults to background, and a real run spawned 37/37 specialists that way by omission — losing
completion accounting and pushing the PM into a settings workaround. false = normal sequential
delegation; true = a deliberate parallel batch the PM fully awaits (notify_agent_events logs the
completions). Forcing the field makes the choice conscious instead of a silent default.
"""
import sys
import os
import json
import glob


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _audit


def block(why):
    _audit.record("guard_agent_spawn", why)
    sys.stderr.write(
        "[team-kit guard] Agent spawn blocked: %s\n"
        "Spawn a specialist by its EXACT role as subagent_type (one of the installed "
        "./.claude/agents/). Never spawn a generic/unnamed agent.\n" % why
    )
    sys.exit(2)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") not in ("Agent", "Task"):
        sys.exit(0)
    inp = data.get("tool_input") or {}
    sub = inp.get("subagent_type")

    cwd = find_repo_root(data.get("cwd"))
    agents_dir = os.path.join(cwd, ".claude", "agents")
    if not os.path.isdir(agents_dir):
        sys.exit(0)  # can't determine the role set -> don't block
    roles = {os.path.splitext(os.path.basename(p))[0]
             for p in glob.glob(os.path.join(agents_dir, "*.md"))}
    # the session agent (the PM/lead) is NEVER spawnable as a subagent (constitution §1 — no second PM)
    lead = "project-manager"
    try:
        with open(os.path.join(cwd, ".claude", "settings.json"), encoding="utf-8") as fh:
            lead = (json.load(fh).get("agent") or lead)
    except Exception:
        pass
    roles.discard(lead)
    if not roles:
        sys.exit(0)

    if not sub or not str(sub).strip():
        block("no subagent_type given (generic agent)")
    if str(sub) == lead:
        block("the %r (PM/lead) is the session agent and MUST NOT be spawned as a subagent" % lead)
    if str(sub) not in roles:
        block("subagent_type %r is not an installed specialist role (%s)" % (sub, ", ".join(sorted(roles))))
    if "run_in_background" not in inp:
        block("run_in_background not set — the platform silently defaults to background. Set it "
              "EXPLICITLY: `run_in_background: false` for normal sequential delegation (the default "
              "choice), `true` ONLY for a deliberate parallel batch — then NEVER advance the phase "
              "before ALL completion notifications have returned")

    # work-order minimal schema (Anthropic: every subagent needs an objective, an output format,
    # sources and boundaries — vague orders produce duplicated work and gaps). Deterministic floor:
    # the prompt must carry `objective` and `output` keys; the skills define the full template.
    prompt_low = str(inp.get("prompt") or "").lower()
    missing = [k for k in ("objective", "output") if k not in prompt_low]
    if missing:
        block("work order lacks %s — every delegation is a YAML work order with at least:\n"
              "  objective: <one sentence - what DONE looks like>\n"
              "  read_first: [the exact files to read]\n"
              "  output: <the YAML keys expected back>\n"
              "  boundaries: <what is OUT of scope>" % " + ".join("`%s:`" % k for k in missing))

    # allowed spawn -> audit it (V2): the Notification route for background completions proved dead
    # in a real environment (0 of 15 completions logged), so spawn accounting must not depend on it.
    try:
        _audit.record_event("guard_agent_spawn", "spawn",
                            "%s (run_in_background=%s)" % (sub, inp.get("run_in_background")))
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
