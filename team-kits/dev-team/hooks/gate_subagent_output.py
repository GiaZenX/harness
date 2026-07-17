#!/usr/bin/env python3
"""
SubagentStop — a kit specialist may not stop without honoring its output contract.

Every role skill defines an "Output to the PM/manager" YAML block; a real failure class is the
specialist that "finishes" with prose, an apology, or nothing — and the PM builds on air. Claude
uses exit 2; Codex uses `decision: block` with a continuation reason. Scope: only OUR specialists
(an agent file exists for agent_type); utility/foreign agents pass. Verdict roles must also carry
`verdict:`.
Uncertainty -> exit 0.
"""
import json
import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _audit
import _compat


VERDICT_ROLES = ("quality-engineer", "reviewer")
DEFAULT_REQUIRED = ("summary",)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if str(data.get("hook_event_name") or "") != "SubagentStop":
        sys.exit(0)
    atype = str(data.get("agent_type") or "")
    required = DEFAULT_REQUIRED + (("verdict",) if atype in VERDICT_ROLES else ())
    low = str(data.get("last_assistant_message") or "").lower()
    missing = [k for k in required if (k + ":") not in low]
    if data.get("stop_hook_active"):
        # a stop hook already blocked this cycle — honor stop_hook_active (docs guidance) instead
        # of looping the subagent forever; log WHAT is still missing so the PM's retro sees the
        # exact contract violation (field data: bare `gave_up` lines were undiagnosable).
        try:
            _audit.record_event("gate_subagent_output", "gave_up",
                                "%s still missing %s" % (atype, ",".join(missing) or "nothing"))
        except Exception:
            pass
        sys.exit(0)
    if not atype:
        sys.exit(0)
    root = find_repo_root(data.get("cwd"))
    if not os.path.isfile(os.path.join(root, ".claude", "agents", atype + ".md")):
        sys.exit(0)  # not one of our kit specialists

    if missing:
        _audit.record("gate_subagent_output", "%s missing %s" % (atype, ",".join(missing)))
        message = (
            "[team-kit gate] Your final message is missing the output-contract key(s): %s. "
            "Do NOT run any more tools and do NOT continue working — ONLY print the YAML output "
            "block for the work you already did (see 'Output to the PM' in your skill: summary, "
            "ids, statuses%s), then stop. A real retry spent 41 minutes doing NEW work instead of "
            "restating; the PM builds on this block and prose-only endings produced work built on "
            "air.\n"
            % (", ".join(missing), ", verdict" if atype in VERDICT_ROLES else "")
        )
        _compat.stop(message, "SubagentStop")
    sys.exit(0)


if __name__ == "__main__":
    main()
