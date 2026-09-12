#!/usr/bin/env python3
"""
PreToolUse(Bash|PowerShell) — shell-hygiene gate, parity risks R10 and R11, promoted from
"optional" to FIRM by the user's "maximal härten" decision of 2026-07-24.

Two rules, one hook, because they share the only thing that matters for cost: they both trigger on
a shell command and would otherwise be two process spawns per Bash call.

R10 — FOREIGN DOCKER PROJECTS ARE OFF-LIMITS (devops SKILL §3). The incident it comes from: an OOM
hunt stopped a NEIGHBOUR project's production database. Compose projects share one daemon, so
`docker stop <name>` reaches anything on the machine, and a model debugging a memory problem has
every reason to look at the biggest container it can see.

R11 — NEVER WORK ON A DIRTY TREE (constitution §8: "offer Commit/Stash/Discard first"). Scoped to
the operations that can LOSE the uncommitted work — merge, rebase, `reset --hard`, a branch
switch, pull. `git checkout -b`, `git stash` and `git add` stay open: those are how the agent gets
the tree clean, and a rule that blocks its own remedy is a deadlock.

BOTH FAIL OPEN WHEN THEY CANNOT SEE. No docker daemon means the destructive command will fail on
its own; no git worktree means there is no uncommitted work to protect. This is deliberate and
different from the ledger gate: there, "cannot tell" hides broken money data, so it refuses. Here,
"cannot tell" means the hazard does not exist in this environment, and refusing would block
ordinary work to protect nothing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import _kernel
except BaseException as exc:  # noqa: BLE001 — a hook that cannot load must not mean "allow"
    sys.stderr.write("[team-kit hook] refused: could not load hook helpers (%r). Remedy: run "
                     "`python scripts/harness.py doctor`; a partial checkout or half-finished kit update is the "
                     "usual cause.\n" % (exc,))
    sys.exit(2)

import _compat  # noqa: E402

HOOK = "gate_shell_hygiene"
SHELL_TOOLS = ("Bash", "PowerShell")


# -- R10 ----------------------------------------------------------------------
# Verbs that STOP or DESTROY. `docker ps/logs/inspect/stats/build/run` are absent: reading is how
# you find out what is going on, and a gate that blocks diagnosis gets worked around.
#
# WHICH WORDS OF A COMMAND THESE ARE COMPARED AGAINST is `_compat.docker_invocations`, the same
# reader the git half of this file already decides on, and NOT a position in a regex. The old
# pattern was `docker\s+(?:compose\s+)?(verb)`, i.e. the verb had to be the first or second word,
# and every global option was therefore a bypass. Measured 2026-07-31 as real hook processes,
# before this: `docker --context remote system prune -af`, `docker -H tcp://x:2375 system prune
# -af` and `docker --log-level debug volume prune` were ALLOWED while `docker system prune -af`
# was refused, and `docker compose -p other down` — compose's own way of naming a FOREIGN project
# — was allowed as well, because `-p` stood where the pattern expected the verb.
_DOCKER_DESTRUCTIVE = frozenset((
    "stop", "kill", "rm", "rmi", "restart", "down", "prune", "pause"))
# `prune` takes everything on the daemon, so there is no target to check: by construction it
# reaches other people's projects.
_PRUNE = "prune"
# How compose NAMES a project on the command line. Read only out of a call that is already
# destructive, which is what makes it unambiguous: no destructive docker verb uses `-p` for
# anything else (`stop`/`kill`/`restart` take `-s`/`-t`, `rm` takes `-f`/`-l`/`-v`, `rmi` takes
# `-f`), while `docker run -p 8080:80` — the one `-p` that means a port — is not destructive.
# This pair is what `_docker_targets` steps over so a project name is not mistaken for a container;
# WHICH PROJECT a line designates is not decided here but in `_foreign_designations`, from compose's
# own precedence, because a list of flags is what BUG-0053 measured four ways past.
_PROJECT_FLAGS = ("--project-name", "-p")
_PROJECT_NAME_ENV = "COMPOSE_PROJECT_NAME"
_COMPOSE_LABEL = "com.docker.compose.project"

# -- R11 ----------------------------------------------------------------------
# Operations that can lose uncommitted work, as SUBCOMMANDS read by `_compat.git_invocations`.
# This hook kept its own regexes for one round too long and therefore kept both defects the shared
# reader was written to end — measured as real hook processes on a dirty tree: `git reset --hard
# HEAD~1` blocked while `git "reset" --hard HEAD~1`, `git rese''t --hard HEAD~1`,
# `git reset --ha\<newline>rd HEAD~1`, `git "merge" feat/x` and `git "checkout" main` all ran, and
# the last of those was blocked by NO hook in the kit. A pattern is a list of spellings; what an
# operation IS cannot be a question about quoting.
_DIRTY_RISK_SUBCOMMANDS = frozenset(("merge", "rebase", "pull", "cherry-pick", "revert", "am"))
# `checkout -b` / `switch -c` CREATE a branch and carry the changes along, which is safe and
# routine; only a switch to an EXISTING ref is in scope.
_SWITCH_SUBCOMMANDS = frozenset(("checkout", "switch"))
_CREATE_BRANCH_FLAGS = frozenset(("-b", "-B", "-c", "-C"))
# `git checkout -- <path>` and `git checkout <ref> -- <path>` restore FILES; that is a deliberate
# discard, which the constitution names as one of the three offers.
_PATHSPEC = "--"


def _git(root, *args):
    try:
        result = _compat.run_captured(["git", "-C", root] + list(args), timeout=15)
    except Exception:  # noqa: BLE001
        return None
    return (result.stdout or "").strip() if result.returncode == 0 else None


def _destructive_docker_calls(command):
    """[(verb, tokens after it, tokens BEFORE it, the segment)] for every docker call that stops
    or destroys something.

    The third element is not the second: compose's project options stand BEFORE the operation
    (`docker compose -p other down`), while a container name stands after it, so a rule that read
    only the tail could never see the project — which is how `-p other` was measured passing. They
    are separated rather than handed over as one list because compose reuses letters across the two
    positions: `-f` before the subcommand is `--file`, `-f` after `docker compose rm` is `--force`,
    and a reader that took both would turn every `docker rm -f <name>` into a compose file.

    The SEGMENT comes with them because one of compose's four project sources is not an argument at
    all — `COMPOSE_PROJECT_NAME=other docker compose down` sets it in the environment of this call,
    and that assignment stands in the segment in front of the program word.

    The verb is looked for among the call's WORDS — its subcommand plus every following token that
    is not a flag — because docker's operations are two words deep (`system prune`, `container rm`,
    `compose down`) and only the first of them is the subcommand. `_compat.docker_invocations` has
    already resolved the global options away, so what remains really is the operation.

    A verb the text does not fix is `verb=None` — a call that could be any docker command. Its
    TARGETS are still read and still checked against the daemon below, which is a refusal a role
    can act on; it deliberately does NOT trigger the prune refusal, which needs no target and could
    therefore never be verified. That direction is chosen rather than inherited: making an
    unresolvable verb fire an unconditional ban would refuse ordinary lines that merely say the
    word docker in front of an expansion, and the daemon check refuses only when the object really
    does belong to somebody else.

    THE PRICE OF SEARCHING ALL THE WORDS, measured and accepted: `docker exec api prune` — the
    daemon-wide verb as an argument to a container's OWN command — is refused as if it were
    `docker system prune`. It is the same trade the git reader makes and in the same direction; the
    alternative is knowing where each of docker's ~40 subcommands stops taking sub-verbs, which is
    the positional rule this replaced. Fourteen further ordinary docker lines were measured silent.

    A DESTRUCTIVE VERB HIDDEN IN AN ARGUMENT EXPANSION IS NOT SEEN (`docker system $VERB -af`):
    `Invocation.resolved` reports only whether the SUBCOMMAND is fixed, so an expansion further
    along is read as an ordinary word. Closing that means an undetermined-value predicate per
    token, which the reader does not expose.
    """
    calls = []
    # `lower=False`, and it is load-bearing rather than tidy: a container name is CASE-SENSITIVE
    # and goes straight into `docker inspect`. The first cut of this conversion took the default
    # (`lower=True`) and lost that -- measured with a docker shim logging its argv,
    # `docker rm OtherDB` reached the daemon probe as `inspect … otherdb`, the daemon answered
    # "No such object", and `_compose_project_of` returned None, which this gate reads as "the
    # command will fail on its own" and allows. HEAD refused all three of `docker rm OtherDB`,
    # `docker stop OtherDB` and `docker rm "OtherDB"`; the conversion allowed them.
    # The VERB comparison is unaffected: `_compat._subcommand_candidates` stores the lowered token
    # as the subcommand whatever this flag says, and the words below are lowered here.
    for invocation in _compat.docker_invocations(command, lower=False):
        arguments = list(invocation.arguments)
        if not invocation.resolved:
            calls.append((None, arguments, arguments, invocation.segment))
            continue
        words = [(str(invocation.subcommand), -1)] + [
            (token.strip("\"'").lower(), index) for index, token in enumerate(arguments)
            if not token.startswith("-")]
        for word, index in words:
            if word in _DOCKER_DESTRUCTIVE:
                calls.append((word, arguments[index + 1:],
                              arguments[:index] if index >= 0 else [], invocation.segment))
                break
    return calls


def _docker_targets(tokens):
    """Names/ids a destructive docker call was given, minus its flags and their values."""
    out, skip = [], False
    for token in tokens:
        if skip:
            skip = False
            continue
        if token.startswith("-"):
            skip = _flag_name(token) in _PROJECT_FLAGS and "=" not in token
            continue
        stripped = token.strip("\"'")
        if stripped:
            out.append(stripped)
    return out


def _flag_name(token):
    return token.split("=", 1)[0].strip("\"'").lower()


def _option_values(tokens, long_name, short_name=None):
    """Every value handed to this option, in each form a POSIX command line can carry one:
    `--long value`, `--long=value`, `-o value`, `-ovalue`.

    THIS IS THE HALF THAT IS NOT ABOUT COMPOSE. Whether a short option's value is attached to it or
    stands beside it is a property of option syntax, and the rule above was measured passing a
    foreign project for no better reason than the attached spelling: `_flag_name` split on `=` only,
    so `-pother` never equalled `-p` and `docker compose -pother down` was rc 0 while
    `docker compose -p other down` was rc 2 (BUG-0053). One reader, so the four sources below each
    get all four spellings without any of them writing a list.

    A long option is compared whole, so `--project-name` cannot be read as an attached `-p` value.
    """
    values, expect = [], False
    for token in tokens:
        bare = str(token).strip("\"'")
        if expect:
            expect = False
            if bare:
                values.append(bare)
            continue
        if bare == long_name or (short_name and bare == short_name):
            expect = True
        elif bare.startswith(long_name + "="):
            value = bare[len(long_name) + 1:]
            if value:
                values.append(value)
        elif (short_name and not bare.startswith("--")
                and len(bare) > len(short_name) and bare.startswith(short_name)):
            value = bare[len(short_name):].lstrip("=")
            if value:
                values.append(value)
    return values


def _environment_project(segment):
    """The project name an assignment in THIS call's own segment gives compose, or None.

    `COMPOSE_PROJECT_NAME=other docker compose down` names a foreign project without a single
    option, which is why this question is asked of the segment and not of the argument list. The
    segment is the boundary on purpose: an assignment in a NEIGHBOURING segment
    (`export COMPOSE_PROJECT_NAME=other && docker compose down`) belongs to another call as far as
    this reader can tell, and is the named residue of this rule rather than a silent catch.
    """
    for word in _compat.shell_words(segment or "", str.split):
        for reading in _compat.shell_readings(word):
            name, separator, value = reading.partition("=")
            if separator and name.strip("\"'").upper() == _PROJECT_NAME_ENV:
                value = value.strip("\"'")
                if value:
                    return value
    return None


def _inside(root, path):
    """Does this path word point INSIDE the repo? Unreadable answers `False` — fail-closed."""
    try:
        resolved = os.path.abspath(os.path.join(root, os.path.expanduser(str(path))))
    except (OSError, ValueError):
        return False
    base = os.path.normcase(os.path.abspath(root))
    resolved = os.path.normcase(resolved)
    return resolved == base or resolved.startswith(base + os.sep)


def _foreign_designations(root, ours, head, segment):
    """How this call designates a compose project that is not this repo's — [] when it does not.

    WHERE COMPOSE TAKES THE PROJECT NAME FROM, in its own documented precedence: the
    `-p`/`--project-name` option, then `COMPOSE_PROJECT_NAME` in the environment, then a `name:`
    inside the compose file, then the BASENAME OF THE PROJECT DIRECTORY — which is
    `--project-directory` when given, otherwise the directory of the first `-f`/`--file`, otherwise
    the working directory. Only the last of those is this repo's own without anybody saying so;
    each of the others is a way for one line to reach another project's stack, and R10 is about the
    property they share, not about the flag that happened to be measured first.

    THE TWO SOURCES ARE ASKED TWO DIFFERENT QUESTIONS, and that is deliberate rather than untidy. A
    NAME is compared against this repo's names. A LOCATION is compared against this repo's TREE:
    `docker compose -f docker/compose.yml down` really does make compose call the project `docker`,
    so comparing that derived name would refuse an ordinary in-repo layout — while the stack it
    touches is still ours. Foreign is "the file or directory lies outside this repo", which is the
    thing R10 protects.

    NOT READ, and named rather than left to be found: the compose file's own top-level `name:`
    (this gate does not open files a command names — it would have to read a foreign path to find
    out that it is foreign), a relative path resolved against a working directory DEEPER than the
    repo root (`..` is resolved against the root, which refuses more rather than less), and the
    deprecated `docker-compose` v1 binary, whose global options are consumed before the arguments
    begin — that spelling arrives here as a bare verb with no head at all.
    """
    found = []
    for name in _option_values(head, "--project-name", "-p"):
        if name.lower() not in ours:
            found.append((name, "named by `-p`/`--project-name`"))
    environment = _environment_project(segment)
    if environment and environment.lower() not in ours:
        found.append((environment, "set through %s in this command" % _PROJECT_NAME_ENV))
    for value in _option_values(head, "--project-directory"):
        if not _inside(root, value):
            found.append((value, "the project directory `--project-directory` points at"))
    for value in _option_values(head, "--file", "-f"):
        directory = os.path.dirname(value)
        if directory and not _inside(root, directory):
            found.append((value, "the compose file `-f`/`--file` points at, whose directory is "
                                 "the project"))
    return found


def _compose_project_of(root, name):
    """The compose project a container/volume belongs to, or None when it cannot be determined."""
    for kind in ("container", "volume"):
        out = _compat.run_captured(
            ["docker", kind, "inspect", "--format",
             "{{ index .Config.Labels \"%s\" }}" % _COMPOSE_LABEL if kind == "container"
             else "{{ index .Labels \"%s\" }}" % _COMPOSE_LABEL, name],
            cwd=root, timeout=20)
        if out.returncode == 0:
            value = (out.stdout or "").strip()
            return value if value and value != "<no value>" else ""
    return None


def _our_compose_projects(root):
    """What this repo's compose project is called. Compose defaults to the DIRECTORY name."""
    names = {os.path.basename(os.path.abspath(root)).lower()}
    # ...and whatever an explicit name says, since a folder rename silently detaches every volume
    for env_file in (".env", os.path.join("docker", ".env")):
        try:
            with open(os.path.join(root, env_file), encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if line.strip().upper().startswith("COMPOSE_PROJECT_NAME"):
                        names.add(line.split("=", 1)[-1].strip().strip("\"'").lower())
        except OSError:
            continue
    names.discard("")
    return names


def _check_docker(root, command):
    # A COMMAND THE READER WILL NOT FINISH READING IS NOT A HARMLESS ONE, and this branch is here
    # because the conversion to `_compat.docker_invocations` lost it. Over `GIT_READ_LIMIT` the
    # reader answers with ONE unresolved invocation carrying no text at all, so the verb search
    # below has nothing to search and every rule falls silent. HEAD did not have that hole: its
    # regex ran over `git_argument_text`, which returns the raw command over the limit, so the
    # prune pattern still matched. Measured on a 524 329-byte command ending in
    # `; docker system prune -af`: HEAD rc 2, the conversion rc 0. The bare `docker` word is looked
    # for first (one linear scan, affordable at any size) so an oversized command that has nothing
    # to do with docker is not refused by this rule.
    #
    # AND THAT SCAN IS ALL R10 HAS UP HERE, which is an asymmetry worth stating rather than
    # discovering: over the limit the only reader is a literal search of the RAW text, so every
    # spelling in which `d-o-c-k-e-r` does not stand contiguously escapes it -- quote splitting
    # (`d""ocker`, `dock''er`), a line continuation, an ANSI-C escape. Measured inside a 524 KB
    # command: rc 0 for those, rc 2 for the same line under the limit, where `_argument_scan`
    # resolves all of them. HEAD is identical here, so this is the shape of the hole and not a
    # regression; closing it means a reader that stays affordable at 512 KB, not a longer pattern.
    if (len(command or "") > _compat.GIT_READ_LIMIT
            and _compat.DOCKER_READER.word_rx.search(command)):
        _kernel.block(
            HOOK,
            "this command names docker and is %d bytes — past the %d the shell readers can finish "
            "in a PreToolUse budget, so this gate cannot tell whether it stops or destroys "
            "anything. A command it cannot read is not one it may call harmless (spec II.4 is "
            "fail-closed, and a gate that reads for minutes decides nothing while the session "
            "waits)."
            % (len(command), _compat.GIT_READ_LIMIT),
            remedy="run the docker step as its own short command; put the bulk (a generated list, "
                   "a here-doc payload) in a file and pass the file.")
    calls = _destructive_docker_calls(command)
    if not calls:
        return          # reading (`ps`, `logs`, `inspect`, `build`, `up`) is never this gate's business
    ours = None
    for verb, tokens, head, segment in calls:
        if verb == _PRUNE:
            _kernel.block(
                HOOK,
                "`docker prune` removes resources across the WHOLE daemon, so it cannot be scoped "
                "to this project — a real OOM hunt once stopped a neighbour project's production "
                "database this way (devops SKILL §3).",
                remedy="remove this project's own resources by name, or `docker compose down` "
                       "inside the repo. If a machine-wide prune is really what you want, that is "
                       "the user's call to make and to run.")
        if ours is None:
            ours = _our_compose_projects(root)
        # DESIGNATED projects first, and without asking the daemon: a line that says which project
        # it reaches says so whether or not docker is running here.
        for designation, how in _foreign_designations(root, ours, head, segment):
            _kernel.block(
                HOOK,
                "this command designates compose project %r (%s), which is not this repo's (%s). "
                "Foreign Docker projects are off-limits: compose projects share one daemon, so a "
                "line that points compose at another project reaches that project's stack outright "
                "— a real OOM hunt stopped a NEIGHBOUR project's production database exactly here "
                "(devops SKILL §3)." % (designation, how, "/".join(sorted(ours))),
                remedy="run compose inside this repo, against this repo's own compose file and "
                       "without a foreign project name, or ask the user explicitly before touching "
                       "anything else on the daemon.")
        for target in _docker_targets(tokens):
            project = _compose_project_of(root, target)
            if project is None:
                continue    # no daemon, or no such object: the command will fail on its own
            if project.lower() not in ours:
                _kernel.block(
                    HOOK,
                    "%r belongs to compose project %r, not to this repo (%s). Foreign Docker "
                    "projects are off-limits: containers and volumes share one daemon, so this "
                    "reaches another project's data — a real OOM hunt stopped a NEIGHBOUR "
                    "project's production database exactly here (devops SKILL §3)."
                    % (target, project or "<none>", "/".join(sorted(ours))),
                    remedy="act on this project's own containers, or ask the user explicitly "
                           "before touching anything else on the daemon.")


def _switches_branch(invocation):
    """A switch to an EXISTING ref — the only checkout/switch shape that can lose work."""
    arguments = invocation.arguments
    if any(token in _CREATE_BRANCH_FLAGS or token == _PATHSPEC for token in arguments):
        return False    # creating a branch carries changes along; `--` restores files on purpose
    return bool(arguments)


def _dirty_risk_verb(command):
    """The name of the operation that can lose uncommitted work, or None.

    One pass over the same invocation reader every other git gate uses, so the three rules cannot
    disagree with each other about what counts as `reset --hard`. An invocation whose verb the
    shell builds at run time answers YES to all of them (`GitInvocation.runs`), which is the
    fail-closed reading: the rule protects data that is gone once the command runs.
    """
    for invocation in _compat.git_invocations(command):
        if invocation.runs(*_DIRTY_RISK_SUBCOMMANDS):
            # `%s`, not `+`: an unresolved verb is `_compat.UNRESOLVED_SUBCOMMAND`, which is an
            # object precisely so no command text can spell it — it renders, it does not concatenate
            return (invocation.subcommand if invocation.resolved
                    else "git %s" % (invocation.subcommand,))
        if invocation.runs("reset") and "--hard" in invocation.arguments:
            return "reset --hard"
        if invocation.runs(*_SWITCH_SUBCOMMANDS) and _switches_branch(invocation):
            return "branch switch"
    return None


def _check_dirty(root, command):
    verb = _dirty_risk_verb(command)
    if verb is None:
        return
    status = _git(root, "status", "--porcelain")
    if not status:
        return          # clean, or not a worktree at all
    # `split(None, 1)` rather than `line[3:]`: porcelain is `XY<space>PATH`, but `_git` strips the
    # output, so the leading space of an unstaged ` M a.txt` is already gone and a fixed offset
    # eats the first character of the filename ("a.txt" was reported as ".txt").
    changed = [line.split(None, 1)[-1] for line in status.splitlines()[:5] if line.split()]
    # THE CITATION THAT WAS HERE IS GONE, and it was wrong in one of the three kits it ships to.
    # This file is byte-identical in all three (the mirror rule), so `constitution §8` named the
    # Git section in dev and research and the BEHAVIOR section in office -- and the office
    # constitution carries no dirty-tree rule at all, so the gloss quoted a sentence that is not
    # there. What stayed is the SITUATION the refusal describes ("a dirty tree"), because that is
    # this gate's own reading of the worktree and not a claim about anybody's text. The one
    # document a refusal may point at is appended by `_compat.stop` from `_compat.REFERENCE_NAME`.
    _kernel.block(
        HOOK,
        "`%s` on a dirty tree can lose the uncommitted changes below.\n%s%s"
        % (verb, "\n".join("  - " + name for name in changed),
           "\n  … and more" if len(status.splitlines()) > 5 else ""),
        remedy="offer the user Commit, Stash or Discard first, then run this again. `git add`, "
               "`git stash` and `git checkout -b` stay open so you can get there.")


def main():
    data = _kernel.payload(HOOK)
    if str(data.get("hook_event_name") or "") != "PreToolUse":
        sys.exit(0)
    if data.get("tool_name") not in SHELL_TOOLS:
        sys.exit(0)
    raw = str((data.get("tool_input") or {}).get("command") or "")
    root = _kernel.find_repo_root(data.get("cwd"))
    # BOTH rules now take the RAW command: each normalises through the reader that decides it
    # (`_compat.docker_invocations` / `_compat.git_invocations`), and a caller that pre-normalises
    # for one of them is the seam at which a gate reaches for the wrong view.
    _check_docker(root, raw)
    _check_dirty(root, raw)
    sys.exit(0)


if __name__ == "__main__":
    _kernel.run_gate(HOOK, main)
