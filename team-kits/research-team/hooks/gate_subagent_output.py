#!/usr/bin/env python3
"""
SubagentStop — a kit specialist may not stop without honoring its output contract.

Every role skill defines an "Output to the PM/manager" YAML block; a real failure class is the
specialist that "finishes" with prose, an apology, or nothing — and the PM builds on air. Exit 2
BLOCKS the stop and feeds stderr back to the subagent (documented semantics), so it restates its
result as the contract YAML and only then stops. Scope: only OUR installed specialists (an agent
file exists for agent_type); utility/foreign agents pass. Verdict roles must also carry `verdict:`.
Uncertainty -> exit 0.
"""
import json
import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _audit


VERDICT_ROLES = ("quality-engineer", "reviewer")
DEFAULT_REQUIRED = ("summary",)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if str(data.get("hook_event_name") or "") != "SubagentStop":
        sys.exit(0)
    if data.get("stop_hook_active"):
        # a stop hook already blocked this cycle — honor stop_hook_active (docs guidance) instead
        # of looping the subagent forever; log the give-up so the PM sees the contract violation.
        try:
            _audit.record_event("gate_subagent_output", "gave_up",
                                str(data.get("agent_type") or ""))
        except Exception:
            pass
        sys.exit(0)
    atype = str(data.get("agent_type") or "")
    if not atype:
        sys.exit(0)
    root = find_repo_root(data.get("cwd"))
    if not os.path.isfile(os.path.join(root, ".claude", "agents", atype + ".md")):
        sys.exit(0)  # not one of our kit specialists

    required = DEFAULT_REQUIRED + (("verdict",) if atype in VERDICT_ROLES else ())
    low = str(data.get("last_assistant_message") or "").lower()
    missing = [k for k in required if (k + ":") not in low]
    if missing:
        _audit.record("gate_subagent_output", "%s missing %s" % (atype, ",".join(missing)))
        sys.stderr.write(
            "[team-kit gate] Your final message is missing the output-contract key(s): %s. Every "
            "specialist ends with its YAML output block (see 'Output to the PM' in your skill) — "
            "restate your FULL result as that YAML now (summary, ids, statuses%s), then stop. The PM "
            "builds on this block; prose-only endings have produced work built on air.\n"
            % (", ".join(missing), ", verdict" if atype in VERDICT_ROLES else "")
        )
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
