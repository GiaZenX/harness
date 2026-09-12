#!/usr/bin/env python3
"""
SessionStart() — maintain `.claude/kit_state.json`, the record `hook_trust` is measured against.

THE EVIDENCE THIS HOOK PROVIDES IS ITS OWN EXECUTION. `python scripts/harness.py doctor` may only call
`hook_trust` verified when the installed hook bundle is the one the project recorded AND those
hooks actually run. The scaffold can establish the first half (it wrote the bundle) but never the
second: Claude Code reads settings.json at session start, so the hooks a scaffold installs are not
running in the session that ran it. That is why `write_kit_state.py` records
`state: restart_required` and this hook — which cannot execute unless hooks execute — is what
flips it to `active`.

The transitions, all of them evidence-based:

  any state that is not `active` + hash matches -> active  (hooks demonstrably run; bundle is the
                                                            recorded one again)
  any state                      + hash differs -> hooks_trust_required
  no kit_state.json                             -> nothing written (absence of a record is not one)

The last line matters most. Inventing a state here would let a project that never ran the scaffold
report the same trust as one that did, and this file is the only thing standing between "the
bundle was reviewed" and "some hooks exist".

THE FIRST ARROW LEADS OUT OF `hooks_trust_required` TOO, and this paragraph used to say the
opposite — "nothing here leads OUT of it" — while the running code returned `active` for a
`hooks_trust_required` record whose hash matched again (measured by EXECUTING `transition`,
TSK-0057 and again for TSK-0139: `('active', None)`; BUG-0037). What the state MEANS is why the
exit is right rather than a leak: it records that the INSTALLED bundle is not the one this project
vouched for, and the vouched-for one is the RECORD, which only `write_kit_state.py` — i.e. the
scaffold — ever writes. A bundle whose hash equals the record again IS the reviewed bundle, so
the difference this state reports has ended. The case that reaches this arrow in practice is a
change rolled back (a `__pycache__` inside the hashed bundle, deleted again) and not a review that
was skipped: nothing an agent can do makes an ARBITRARY bundle match a record it cannot rewrite.

`test_the_trust_state_exits_on_a_bundle_that_matches_the_record_again` executes all four
combinations, so this paragraph cannot drift back into a claim about an arrow that is there.
What still holds unchanged: while the hashes differ, no number of new sessions clears the state,
which is why the message this hook prints names the scaffold and not merely a restart;
`gate_dispatch`'s spawn refusal, which is what the state actually costs, names the same step.

COMFORT HOOK, fail-open (spec II.4). It informs and records; it must never refuse a session. It
imports `_kernel` for the ONE definition of the bundle hash and immediately calls `disarm()`:
importing that bridge arms an excepthook that turns any escaping error into exit 2, which is
correct for an integrity gate and wrong here — a briefing hook that kills the session because a
JSON file is malformed is a worse failure than the one it reports.
"""
import contextlib
import json
import os
import sys
import tempfile

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

STATES_NEEDING_TRUST = ("hooks_trust_required",)


def bundle_hash(repo_root):
    """The installed bundle's hash via the kernel's single definition, or None."""
    try:
        import _kernel
        _kernel.disarm()  # comfort hook: an internal error must never become exit 2
        hashing = _kernel.kernel_module("hashing", repo_root)
        return hashing.hook_bundle_hash(os.path.join(repo_root, ".claude"))
    except BaseException:  # noqa: BLE001 — see the module docstring: informing, never blocking
        return None


def load_state(path):
    try:
        with open(path, encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def save_state(path, data):
    """Atomic replace via a UNIQUE temp file.

    `os.replace` is atomic; a fixed `kit_state.json.tmp` is not. Two SessionStarts racing — a
    window reopened while another is still starting — would truncate the same scratch file, and
    on POSIX nothing serialises that. `mkstemp` costs a line and removes the class.
    """
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix="kit_state.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp)
        raise


def transition(data, actual):
    """(new_state, message) for a kit_state mapping and the bundle hash measured right now."""
    recorded = data.get("hook_bundle_hash")
    current = data.get("state")
    if not recorded:
        return None, None
    if actual != recorded:
        if current in STATES_NEEDING_TRUST:
            return None, None  # already said; saying it again every session is noise
        return "hooks_trust_required", (
            "HOOK BUNDLE CHANGED since this project trusted it (recorded %s, installed %s). "
            "Enforcement is reported as `audited` and NO specialist can be spawned until somebody "
            "vouches for the bundle again. FIRST open /hooks and review what changed in "
            "`.claude/hooks` and `.claude/kernel`; if the change is not yours, treat it as a "
            "finding — the enforcement layer is the thing an agent would want to edit. THEN the "
            "scaffold_team script has to run once from the project root, followed by ONE new "
            "session: re-installing the kit files is what records the reviewed bundle. Further "
            "sessions on their own change nothing — this hook only MEASURES the bundle, it never "
            "rewrites the record. ASK THE USER TO RUN THE SCAFFOLD; `gate_write_scope` refuses a "
            "WRITE-CAPABLE command line that names the enforcement layer, and starting a script "
            "is write-capable, so this session cannot run the scaffold itself (reading the layer "
            "is unaffected). The commonest cause is not an edit at all: a python process that imports "
            "`.claude/kernel` without `-B` leaves a `__pycache__` inside the hashed bundle. The "
            "scaffold prunes it, and deleting that one directory clears it too — the user's step "
            "either way, for the same reason."
            % (str(recorded)[:12], str(actual)[:12]))
    if current == "active":
        return None, None
    return "active", None


def main():
    # `tolerate_overflow=True`: this hook only informs, so an oversized payload must not refuse
    # the session (the opposite of the integrity gates, spec II.4).
    data = _compat.load(tolerate_overflow=True)
    repo_root = find_repo_root(data.get("cwd"))
    path = os.path.join(repo_root, ".claude", "kit_state.json")
    parts = []
    try:
        state = load_state(path)
        if state is not None:
            actual = bundle_hash(repo_root)
            if actual is not None:
                new_state, message = transition(state, actual)
                if new_state:
                    state["state"] = new_state
                    if new_state == "hooks_trust_required":
                        state["hook_bundle_hash_seen"] = actual
                    save_state(path, state)
                if message:
                    parts.append(message)
    except BaseException:  # noqa: BLE001 — comfort hook, see the module docstring
        pass
    if parts:
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": " ".join(parts)}}))
    sys.exit(0)


if __name__ == "__main__":
    main()
