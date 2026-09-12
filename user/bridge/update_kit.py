#!/usr/bin/env python3
"""The ONE lift a project one release behind cannot perform for itself (BUG-0059, FR-0006).

WHAT IS BROKEN WITHOUT THIS, measured 2026-08-22 against a real `2026.08.14-9` install rebuilt from
this repo's own history and scaffolded by that release's own installer: its `.claude/kernel` has no
`kitupdate.py`, so its entry point answers `update-kit --help` with exit 2, and its own
`gate_write_scope` answers the scaffold invocation with exit 2 as well (a write-capable command
line naming `.claude`/`team-kits`). The PM of such a project can therefore run neither the new
command -- it does not exist there yet -- nor the installer, and pilot 4 measured what is left over:
two PowerShell lines handed to a non-technical user, who did not get through them (P4-1, and B4 one
pilot earlier).

WHY THIS FILE LIVES OUTSIDE `~/.claude`, which is the whole of the trick: that gate decides on what
a command LINE names, and a line naming this file names neither protected word. Measured against
the same real install, through every hook its own `settings.json` registers on `Bash`/`PowerShell`:
`python <this file>` is exit 0 where the scaffold line is exit 2.

SO THE REFUSAL BELOW IS WHAT KEEPS IT A BOOTSTRAP RATHER THAN A BACK DOOR: `has_the_approved_route`
asks the PROJECT'S OWN entry point whether it carries `update-kit`, and a project that answers yes
is sent to `request-approval kit_update` + `update-kit` instead of being installed over from here.
The route that mints no approval exists only where no approving route exists
(`tools/test_kitupdate.py::test_the_bridge_refuses_a_project_that_can_reach_the_approved_route`).

WHAT THIS DOES NOT DO, said plainly because the difference is the user's: it mints no approval and
reads none. The release it installs is the one the USER staged when they ran the harness installer,
and the per-project decision is the OK the PM asks for in the chat before starting this -- the shape
DEC-0001 described and V2 lost. Nothing in the old stock can ENFORCE that asking; what is enforced
here is everything the kernel already decides about an update, borrowed rather than re-implemented:
the direction (`kitupdate.assert_updatable`), the staging against its own stamp
(`assert_the_staging_is_its_own_stamp`), that no restart is already pending, and that the session is
stopped afterwards (`ensure_restart_is_forced`).

IT ADDS A ROUTE AND REMOVES NONE. A project whose PM never hears of this file keeps the flow its own
briefing describes; that is why nothing here has to be true for the old stock to keep working.
"""
from __future__ import annotations

import os
import subprocess
import sys

# Where the harness installer stages the kits, spelled the way both scaffold twins spell it. This
# file is started by an agent in a project, so it has no kernel on its path until this line.
STAGING = os.path.join(os.path.expanduser("~"), ".claude", "team-kits")
# The project's own entry point -- the same relative path every kit's scaffold installs.
ENTRY_POINT = os.path.join("scripts", "harness.py")
# How long the project's parser may take to answer "do you carry this command". It is an argparse
# run over one import; a project that needs longer than this is answering nothing useful.
SURFACE_TIMEOUT = 60


def _fail(message: str):
    """Every exit from here that is not the completed lift -- one wording, one exit code."""
    sys.stderr.write(message.rstrip() + "\n")
    raise SystemExit(2)


def _kernel():
    """The STAGED kernel -- the release this bridge would install, and the one that decides.

    Imported from the staging rather than vendored: "which kit is newer", "is the staging its own
    stamp", "how is this host's installer started" and "what stops the session" are answers this
    harness already has, and a copy here would be a second one that ages differently.
    """
    if STAGING not in sys.path:
        sys.path.insert(0, STAGING)
    try:
        from kernel import kitupdate, presets                        # noqa: PLC0415
        from kernel.state import StateError                          # noqa: PLC0415
    except Exception as exc:                                         # noqa: BLE001
        _fail("this bridge could not load the staged kernel from %s (%r), so it cannot say which "
              "release is staged here -- nothing was changed. Remedy: install the harness on this "
              "machine (`install.ps1`/`install.sh` in the agents-and-skills checkout), then run "
              "this again." % (STAGING, exc))
    return kitupdate, presets, StateError


def project_root(start: str) -> str:
    """The installed project `start` sits in: the nearest ancestor carrying a `.claude` directory.

    The kits' own hooks answer this with `_root.find_repo_root`, which lives inside an installation
    and is therefore unavailable to a file that runs before one is current. `.claude` is what a
    scaffolded project has by construction, so it is the marker used here, and the refusal names it.
    """
    current = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(current, ".claude")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            _fail("this is not an installed project: no `.claude` directory was found in %s or "
                  "above it -- nothing was changed. Remedy: run this from the project folder whose "
                  "kit is behind." % os.path.abspath(start))
        current = parent


def has_the_approved_route(root: str, command: str, timeout: float = SURFACE_TIMEOUT):
    """Does THIS project's entry point carry `command` -- asked of the parser that runs.

    True/False/None, and the third is not a formality: a surface that could not be ASKED at all --
    no `scripts/harness.py`, or one that did not return within `timeout` -- is a different situation
    from one that answered, and the caller refuses on it rather than guessing. Everything else the
    parser can do is folded into False: an entry point that carries the command exits 0 on its
    `--help`, and one that crashes carries nothing a caller could use either way.

    ASKED, NOT READ OFF A FILE NAME: `.claude/kernel/kitupdate.py` being present says the module was
    copied, not that the command is on the surface, and the surface is what the PM would type.
    Measured on both sides against real installs -- exit 2 on a 2026.08.14-9 project, exit 0 on a
    project this repo's current scaffold installed
    (`tools/test_kitupdate.py::test_the_bridge_reads_the_route_off_the_projects_own_entry_point`).
    """
    script = os.path.join(root, ENTRY_POINT)
    if not os.path.isfile(script):
        return None
    try:
        result = subprocess.run([sys.executable, "-B", script, command, "--help"], cwd=root,
                                capture_output=True, timeout=timeout, text=True,
                                encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    return result.returncode == 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        _fail("this bridge takes no arguments (got %r). It installs the staged release of the kit "
              "THIS project already runs, and nothing else -- nothing was changed." % (argv,))
    kitupdate, presets, StateError = _kernel()
    root = project_root(os.getcwd())

    try:
        kit = presets.installation(root)["kit"]
    except StateError as exc:
        # THE RESOLVED ROOT IS PART OF THIS REFUSAL, because the reader cannot see which folder was
        # judged: `project_root` climbs to the nearest ancestor carrying a `.claude` directory, and
        # from a folder beside a project that can be the HOME directory. Without the path, "this
        # project has no ownership manifest" reads as a broken project rather than as "you are
        # standing somewhere else".
        _fail("%s\nThe folder judged here is %s -- the nearest ancestor of %s that has a `.claude` "
              "directory. If that is not the project you meant, run this from the project folder "
              "itself." % (exc, root, os.path.abspath(os.getcwd())))

    route = has_the_approved_route(root, kitupdate.COMMAND)
    if route:
        _fail(
            "this project's own entry point carries `%s`, so this bridge is not the route -- "
            "nothing was changed. That route asks the USER first and records their answer, which "
            "this one cannot. Remedy: `python %s request-approval %s` prints the question, the USER "
            "approves by answering it, then `python %s %s` installs the release."
            % (kitupdate.COMMAND, ENTRY_POINT.replace(os.sep, "/"), kitupdate.KIND,
               ENTRY_POINT.replace(os.sep, "/"), kitupdate.COMMAND))
    if route is None:
        # BOTH ways the question can go unanswered, in one sentence, because this branch cannot
        # tell them apart and a message that names only the missing file would be false for the
        # other one: `has_the_approved_route` answers None for an absent entry point AND for one
        # that did not return in time.
        _fail(
            "this project's entry point (%s) could not be asked whether it already carries `%s` -- "
            "it is missing, or it did not answer within %g s. Refused (fail-closed); nothing was "
            "changed. Remedy: report the gap and name the folder; a project whose own surface "
            "cannot be read is not one this bootstrap should install over."
            % (ENTRY_POINT.replace(os.sep, "/"), kitupdate.COMMAND, SURFACE_TIMEOUT))

    answer = kitupdate.relation(root, kit)
    try:
        kitupdate.assert_updatable(answer)
        kitupdate.assert_the_staging_is_its_own_stamp(answer["kit_dir"])
        kitupdate.assert_no_restart_is_pending(root)
    except StateError as exc:
        _fail("%s" % exc)

    command = presets.installer_command(kit)
    result = subprocess.run(command, cwd=root, capture_output=True,
                            timeout=presets.INSTALLER_TIMEOUT, **presets.CHILD_TEXT)
    marker = kitupdate.ensure_restart_is_forced(root, kit)
    if result.returncode != 0:
        _fail("the kit's installer refused (exit %d). It said:\n%s\n%s. The installer rolls its "
              "own changes back when it refuses; what a KILLED run leaves is not undone. Remedy: "
              "report both this message and the state above to the user and end the session."
              % (result.returncode, ((result.stderr or "") + (result.stdout or "")).strip()[-1200:],
                 marker))
    sys.stdout.write(
        "kit '%s' updated from %s to %s.\n%s.\n"
        "NO APPROVAL COVERS THIS ONE LIFT, and that is the thing to say out loud: the release "
        "installed here is the one the USER staged, and the per-project decision was the OK they "
        "gave in the chat. The stock this project ran carries no `%s` approval kind, so there was "
        "nothing to mint and nothing in this project's state records the answer -- this update is "
        "the only one in its life that no record covers. Report that to the user in the same "
        "breath as the restart (`H55` is the measured gap).\n"
        "RESTART REQUIRED: tell the user in plain words that the update is installed and that the "
        "session has to be restarted (close and reopen the window, or start a new session in this "
        "folder). Do NOT start further work in this session -- the new hooks, roles and settings "
        "only bind at the next start, and from there `python %s %s` is the route for every future "
        "update, and that one DOES record the user's approval.\n"
        % (kit, answer["from"].get("version") or "no readable version stamp",
           answer["to"].get("version") or "no readable version stamp", marker, kitupdate.KIND,
           ENTRY_POINT.replace(os.sep, "/"), kitupdate.COMMAND))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
