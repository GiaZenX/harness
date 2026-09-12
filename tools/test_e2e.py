#!/usr/bin/env python3
"""
End-to-end scenario tests — the REAL provider path, not the unit-test shortcut.

Motivation (audit-proven): the unit suite sends payloads via json.dumps (ASCII-escaped) and
reads hook output in the parent's locale — which made it STRUCTURALLY blind to the Windows
encoding class (cp1252 stdin mojibake, cp1252 subprocess reads) that produced three separate
MAJORs in one week. These scenarios emulate what providers actually do: raw UTF-8 bytes on
stdin, real subprocess chains, umlauts in paths/messages/output.
"""
import json
import os
import shutil
import subprocess
import sys
import time

import pytest

from conftest import load_kit_module

pytestmark = pytest.mark.skipif(shutil.which("git") is None,
                                reason="e2e scenarios need git on PATH")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "team-kits", "dev-team", "hooks")
OFFICE_HOOKS = os.path.join(ROOT, "team-kits", "office-team", "hooks")
SCRIPTS = os.path.join(ROOT, "team-kits", "dev-team", "templates", "repo", "scripts")


def raw_hook(name, payload, project_dir, hooks_dir=None):
    """Run a hook exactly like a provider does: raw UTF-8 bytes on stdin, bytes captured."""
    # HARNESS_KERNEL_PATH: the kernel-backed gates resolve `kernel` relative to the PROJECT, and a
    # tmp_path repo has no `.claude/kernel` — without it they fail closed on every call, which
    # would make these scenarios measure a missing install instead of the behaviour under test.
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir),
               HARNESS_KERNEL_PATH=os.path.join(ROOT, "team-kits"))
    return subprocess.run([sys.executable, os.path.join(hooks_dir or HOOKS, name)],
                          input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                          capture_output=True, env=env, timeout=120)


def capture_root_item(repo):
    """The repo's first typed root item — what the merge gates now trigger on (spec II.2/II.11/2).

    Through the kernel, so the item is one the state validator accepts: a hand-written stub would
    make every gate here block on a broken fixture rather than on the thing under test.
    """
    sys.path.insert(0, os.path.join(ROOT, "team-kits"))
    from kernel.state import ProjectState
    root = os.path.join(str(repo), "project_memory")
    os.makedirs(root, exist_ok=True)
    return ProjectState(root).capture("PR", {
        "title": "Checkout flow", "class": "normal", "problem": "no checkout",
        "goal": "working checkout",
        "acceptance_criteria": [{"id": "AC-1", "text": "order completes"}],
        "invariants": [], "out_of_scope": [], "priority": "high",
        "user_story": "As a buyer I can pay",
    })


def launched_hook(gate, payload, project_dir, hooks_dir=None):
    """Run a gate the way the shipped `settings.json` registers it: behind `_gate.py`.

    Calling the gate module directly is a different program. The launcher owns `__main__`, and a
    round was lost to exactly that difference once already (`_assert_minting_caller` saw the
    launcher and every approval in every kit silently stopped minting). An end-to-end scenario that
    took the shortcut would be measuring a registration nobody ships.
    """
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir),
               HARNESS_KERNEL_PATH=os.path.join(ROOT, "team-kits"))
    return subprocess.run(
        [sys.executable, os.path.join(hooks_dir or HOOKS, "_gate.py"), gate],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True, env=env, timeout=120)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _git(cwd, *args):
    return subprocess.run(["git", "-c", "core.quotepath=off", "-C", str(cwd), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=30)


# ---------------- scenario: full gate_pipeline chain with UTF-8 runner output ----------------
def test_e2e_gate_pipeline_red_run_shows_utf8_fail_lines(tmp_path):
    """A RED quality.py emitting Vitest-style UTF-8 glyphs (❯) must yield a BLOCK whose stderr
    still contains the FAIL line — the cp1252 read once dropped the ENTIRE output (p.stdout was
    None) and the PM debugged blind for a night."""
    capture_root_item(tmp_path)
    write(str(tmp_path / "scripts" / "quality.py"),
          "import sys\n"
          "for s in (sys.stdout, sys.stderr):\n"
          "    try:\n"
          "        s.reconfigure(encoding='utf-8', errors='replace')\n"
          "    except Exception:\n"
          "        pass\n"
          "print('  \\u276f FAIL  frontend tests \\u2014 K\\u00e4ufer-Flow broken')\n"
          "sys.exit(1)\n")
    payload = {"tool_name": "Bash", "cwd": str(tmp_path),
               "tool_input": {"command": "git push origin main"}}
    r = raw_hook("gate_pipeline.py", payload, tmp_path)
    assert r.returncode == 2
    err = r.stderr.decode("utf-8")  # strict: the OUTBOUND side must be real UTF-8 (audit:
    assert "FAIL" in err            # cp1252 stderr turned Käufer into mojibake for providers)
    assert "Käufer-Flow" in err     # the umlaut SURVIVES the whole chain, not just the line


def test_e2e_gate_pipeline_green_cache_with_umlaut_filename(tmp_path):
    """Green-tree cache round trip in a repo containing an umlaut filename — git status/rev-parse
    output flows through the pinned decoder; second push must hit the cache, not rerun."""
    repo = tmp_path / "repo"
    capture_root_item(repo)
    counter = tmp_path / "runs.txt"  # OUTSIDE the repo — the tree must stay clean
    write(str(repo / "scripts" / "quality.py"),
          "open(r'%s', 'a').write('x')\nprint('[quality] pipeline GREEN.')\n" % str(counter))
    write(str(repo / "Belege" / "Müller_Rechnung.md"), "beleg\n")
    write(str(repo / ".gitignore"), ".claude/.gate_pipeline_green\nproject_memory/.audit/\n")
    for args in (("init", "-q"), ("add", "-A"),
                 ("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")):
        assert _git(repo, *args).returncode == 0
    payload = {"tool_name": "Bash", "cwd": str(repo),
               "tool_input": {"command": "git push origin main"}}
    assert raw_hook("gate_pipeline.py", payload, repo).returncode == 0
    assert raw_hook("gate_pipeline.py", payload, repo).returncode == 0
    assert counter.read_text() == "x"  # second run served from the green-tree cache


# ---------------- scenario: text-matching guards fed raw UTF-8 like a real provider ----------------
def test_e2e_office_fs_tripwire_blocks_umlaut_path_delete(tmp_path):
    """The office fs tripwire must still recognize inbox/archive targets when the path carries
    German umlauts and arrives as raw UTF-8 (the mojibake class silently missed patterns)."""
    payload = {"tool_name": "Bash", "cwd": str(tmp_path),
               "tool_input": {"command": 'rm -rf "archive/3-Rechnungen/Müller GmbH"'}}
    r = raw_hook("guard_fs_tripwire.py", payload, tmp_path, hooks_dir=OFFICE_HOOKS)
    assert r.returncode == 2


def test_e2e_gate_git_umlaut_commit_prose_passes_force_blocks(tmp_path):
    """Umlaut prose in a commit message must not trip the push gate; a real force-push in the
    same raw-UTF-8 shape must still block."""
    prose = {"tool_name": "Bash", "cwd": str(tmp_path),
             "tool_input": {"command":
                            'git commit -m "docs: erklärt warum git push --force verboten ist"'}}
    assert raw_hook("gate_git.py", prose, tmp_path).returncode == 0
    forced = {"tool_name": "Bash", "cwd": str(tmp_path),
              "tool_input": {"command": 'git push origin main --force'}}
    assert raw_hook("gate_git.py", forced, tmp_path).returncode == 2


# ---------------- scenario: kit_checks repo-wide YAML with umlaut filename ----------------
def test_e2e_repo_wide_yaml_parses_umlaut_filenames(tmp_path):
    """A tracked, BROKEN YAML with an umlaut name must be found and named (git quotepath once
    octal-escaped such paths so isfile() skipped them — the file was silently unchecked)."""
    pytest.importorskip("yaml")
    mod = load_kit_module("kit_checks_e2e", os.path.join(SCRIPTS, "kit_checks.py"))
    repo = tmp_path / "repo"
    write(str(repo / "project_memory" / "product" / "active" / "PR-0001.yaml"),
          "id: PR-0001\nstatus: DRAFT\n")
    write(str(repo / "config" / "Geschäftskonten.yaml"), "a: [unclosed\n")
    for args in (("init", "-q"), ("add", "-A")):
        assert _git(repo, *args).returncode == 0
    calls = {"ok": [], "fail": [], "warn": []}
    mod.check_project_memory_yaml(str(repo), lambda n, *a: calls["ok"].append(n),
                                  lambda n, m: calls["fail"].append((n, m)),
                                  lambda n, m: calls["warn"].append((n, m)))
    hits = [m for n, m in calls["fail"] if n == "yaml-lint (repo-wide)"]
    assert hits and "Geschäftskonten" in hits[0]  # found AND correctly named, no mojibake


# ---------------- scenario: session_status end-to-end with umlaut branch ----------------
def test_e2e_session_status_survives_umlaut_git_state(tmp_path):
    """SessionStart briefing in a repo whose branch name carries umlauts — the pinned git decode
    must deliver a readable branch line, never crash the hook (additionalContext JSON intact)."""
    repo = tmp_path / "repo"
    write(str(repo / "project_memory" / "product" / "active" / "PR-0001.yaml"),
          "id: PR-0001\nstatus: DRAFT\n")
    for args in (("init", "-q", "-b", "feature/PR-0001-büro"), ("add", "-A"),
                 ("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")):
        assert _git(repo, *args).returncode == 0
    payload = {"hook_event_name": "SessionStart", "cwd": str(repo)}
    r = raw_hook("session_status.py", payload, repo)
    assert r.returncode == 0
    out = json.loads(r.stdout.decode("utf-8", "replace"))
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "büro" in ctx  # branch survived the decode intact, no mojibake


# ---------------- scenario: BOM-written config must not permanently block pushes ----------------
def test_e2e_memory_complete_accepts_bom_config(tmp_path):
    """A PS-5.1-style BOM rewrite of project_config.yaml (name on line 1) once made
    config_unfilled() blind — the gate blocked every push of a correctly filled project and
    escalated. The stdlib gates read utf-8-sig now."""
    capture_root_item(tmp_path)
    cfg = tmp_path / "project_memory" / "project_config.yaml"
    cfg.write_bytes("﻿name: Bürosoftware Müller GmbH\npreset: solo\n".encode("utf-8"))
    payload = {"tool_name": "Bash", "cwd": str(tmp_path),
               "tool_input": {"command": "git push origin main"}}
    r = raw_hook("gate_memory_complete.py", payload, tmp_path)
    err = r.stderr.decode("utf-8", "replace")
    assert "project_config.yaml" not in err  # filled config never appears in the block list
    # POSITIVE CONTROL on the same axis. The assertion above is negative and holds just as well
    # against EMPTY stderr — it stayed green with the gate's trigger disabled, proving nothing
    # about the BOM path. The same BOM-encoded file with an UNFILLED key must reach the gate and
    # block; only both directions together show that the config was actually read.
    cfg.write_bytes("﻿name: Bürosoftware Müller GmbH\nstacks: [TODO]\n".encode("utf-8"))
    r2 = raw_hook("gate_memory_complete.py", payload, tmp_path)
    assert r2.returncode == 2
    assert "project_config.yaml" in r2.stderr.decode("utf-8", "replace")


# ---------------- scenario: capture body decode is the kernel's, not the console's ----------
def _capture_cli(root, item_type, body, extra_env=None):
    """Run `python -B -m kernel.cli capture <TYPE>` as a REAL process, UTF-8 bytes on stdin.

    The heredoc a role types delivers UTF-8 bytes; the reproduction control is the CALLER's stdin
    codepage, forced to cp1252 so the RED is host-independent (a UTF-8 host would hide it). The fix
    reads `sys.stdin.buffer` and decodes UTF-8, so the caller's codepage no longer decides -- and
    the test never sets PYTHONUTF8/PYTHONIOENCODING to UTF-8 to get there.
    """
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "team-kits"),
               PYTHONIOENCODING="cp1252")
    env.pop("PYTHONUTF8", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory",
         "capture", item_type],
        input=body, capture_output=True, env=env, cwd=str(root), timeout=120)


def test_e2e_capture_stores_umlaut_body_as_utf8_bytes_whatever_the_stdin_codepage(tmp_path):
    """A `capture` body carrying `ü` must land in the item as UTF-8 bytes even when the caller's
    stdin decodes as cp1252 -- measured on the RAW BYTES of the written file, not the console.

    Without the fix `sys.stdin.read()` decoded the piped c3bc as cp1252 (`Ã¼`) and yaml.safe_dump
    re-encoded it, storing c383c2bc in an L2-immutable field -- the exact corruption that drove a
    pilot's root-item drift (BUG-0018).
    """
    os.makedirs(str(tmp_path / "project_memory"))
    body = json.dumps({
        "title": "Käufer-Rechnung als UTF-8 ablegen",
        "context": "der Käufer sieht Umlaute im Konto",
        "decision": "der Kernel dekodiert den Body selbst als UTF-8",
        "consequences": "kein Mojibake mehr für Müller",
        "source": "docs/reviews/2026-08-10-tsk0028-measurements.md",
        # the capture door asks every decision who carries it (DEC-0083); this one commits nobody
        "work": "none",
    }, ensure_ascii=False).encode("utf-8")
    r = _capture_cli(tmp_path, "DEC", body)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    written = sorted((tmp_path / "project_memory" / "decisions" / "active").glob("DEC-*.yaml"))
    assert len(written) == 1, [p.name for p in written]
    data = written[0].read_bytes()
    assert b"K\xc3\xa4ufer" in data          # ä stored as real UTF-8 (c3a4), the item is readable
    assert b"M\xc3\xbcller" in data          # ü stored as real UTF-8 (c3bc)
    assert b"\xc3\x83\xc2\xbc" not in data    # NOT the double-encoded 'Ã¼' the cp1252 read produced
    assert b"\xc3\x83\xc2\xa4" not in data    # NOT the double-encoded 'Ã¤' either


def test_e2e_capture_refuses_a_body_that_is_not_utf8_instead_of_crashing(tmp_path):
    """The counter-direction: a body that is genuinely not UTF-8 (a lone cp1252 0xFC) is refused
    with a UsageError (rc 2), not a bare UnicodeDecodeError traceback -- the kernel does not guess
    a codepage, and the refusal keeps the same clean-exit contract every other malformed body has.
    """
    os.makedirs(str(tmp_path / "project_memory"))
    body = b'{"title": "M\xfcller", "request_text": "x"}'  # 0xFC is cp1252 'ü', invalid UTF-8
    r = _capture_cli(tmp_path, "FR", body)
    assert r.returncode == 2, r.stderr.decode("utf-8", "replace")
    err = r.stderr.decode("utf-8", "replace")
    assert "not valid UTF-8" in err
    assert "Traceback" not in err


def test_e2e_capture_accepts_a_bom_prefixed_body_and_stores_it_without_bom(tmp_path):
    """A `capture` body that a producer prepended a UTF-8 BOM to (`EF BB BF`, the shape a
    PowerShell here-string over a native pipe emits) must be accepted and stored WITHOUT the mark
    (BUG-0021), measured on the RAW BYTES of the written item.

    Without the fix the strict `utf-8` decode kept the BOM as U+FEFF at the front of the string and
    `json.loads` refused with "Unexpected UTF-8 BOM" — the kernel reported the body as not-JSON
    (rc 2) while the error's own remedy already named `utf-8-sig`. The fix decodes the byte stream
    with `utf-8-sig`, which strips a single leading BOM and otherwise decodes like `utf-8`, so
    BUG-0018 (the byte stream is the kernel's to decode, not the console's) is untouched: the umlaut
    below still has to land as real UTF-8.
    """
    os.makedirs(str(tmp_path / "project_memory"))
    body = b"\xef\xbb\xbf" + json.dumps({
        "title": "BOM-behafteter Body wird angenommen",
        "context": "ein Produzent stellt der JSON ein BOM voran",
        "decision": "der Kernel dekodiert den Body mit utf-8-sig",
        "consequences": "kein exit 2 mehr für Müller, kein BOM im Item",
        "source": "docs/reviews/2026-08-11-tsk0044-measurements.md",
        # the capture door asks every decision who carries it (DEC-0083); this one commits nobody
        "work": "none",
    }, ensure_ascii=False).encode("utf-8")
    r = _capture_cli(tmp_path, "DEC", body)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    written = sorted((tmp_path / "project_memory" / "decisions" / "active").glob("DEC-*.yaml"))
    assert len(written) == 1, [p.name for p in written]
    data = written[0].read_bytes()
    assert b"\xef\xbb\xbf" not in data       # the BOM never reaches the stored item / its hash
    assert b"\xef\xbb\xbf" != data[:3]       # in particular not at the front of the file
    assert b"M\xc3\xbcller" in data          # ü still stored as real UTF-8 (BUG-0018 not undone)


# ---------------- scenario: the V2 chain itself — draft PR, approval, SR, task, spawn ----------
sys.path.insert(0, os.path.join(ROOT, "team-kits"))
from kernel import approvals, dispatch  # noqa: E402
from kernel.state import ProjectState  # noqa: E402


def _leased_task(repo):
    """Walk the chain to a leased task and return (state, task, dispatch header).

    Every step is a kernel operation, and the approval step is a real subprocess through the
    shipped launcher — the one step of the chain that a test is not allowed to shortcut, because
    the kernel refuses to mint for any other caller.
    """
    state = ProjectState(os.path.join(str(repo), "project_memory"))
    os.makedirs(state.root, exist_ok=True)
    pr = state.capture("PR", {
        "title": "Rechnungsübersicht für Käufer", "class": "normal",
        "problem": "der Käufer sieht seine Rechnungen nicht",
        "goal": "Rechnungsliste im Konto",
        "acceptance_criteria": [{"id": "AC-1", "text": "Käufer sieht seine Rechnungen"}],
        "invariants": [], "out_of_scope": [], "priority": "high",
        "user_story": "Als Käufer sehe ich meine Rechnungen",
    })
    assert state.read_item(pr["id"])["status"] != "APPROVED"  # a fresh PR is a DRAFT, not a plan

    request = approvals.create_pending_request(state, "scope", pr["id"])
    question = approvals.build_question(request)
    approved = launched_hook("gate_approval.py", {
        "hook_event_name": "PostToolUse", "tool_name": "AskUserQuestion", "cwd": str(repo),
        "tool_input": {"questions": [question]},
        "tool_response": {"questions": [question], "answers": {
            question["question"]: approvals.approve_label(request["mint_code"])}},
    }, repo)
    assert approved.returncode == 0, approved.stderr.decode("utf-8", "replace")
    assert state.read_item(pr["id"])["status"] == "APPROVED"

    sr = state.capture("SR", {
        "title": "GET /rechnungen liefert die Belege des angemeldeten Käufers",
        "derives_from": pr["id"],
        "contract": "200 + JSON-Liste für den eigenen Account, 403 für fremde",
        "affected_components": ["api"],
    })
    state.transition(sr["id"], "ACCEPTED")   # the architect step the lease owes (FR-0085)
    task = dispatch.create_task(state, {
        "product_requirement": pr["id"], "derives_from": sr["id"], "type": "implementation",
        "assigned_role": "backend-developer", "acceptance_refs": ["AC-1"],
        "required_inputs": [], "allowed_scope": ["src/"], "forbidden_scope": ["secrets/"],
        "expected_outputs": ["src/rechnungen.py"], "dependencies": [],
    })
    state.transition(task["id"], "READY")
    lease = dispatch.create_lease(state, task["id"])
    return state, task, dispatch.dispatch_header(lease)


def test_e2e_the_draft_to_dispatch_chain_runs_through_the_shipped_hooks(tmp_path):
    """Draft PR → user approval → SR → task → lease → the spawn the dispatch gate lets through.

    The single scenario the disposition asks of this file, and the one thing the unit tests around
    the kernel cannot show: they exercise the links, this walks the CHAIN. Each link consumes what
    the one before it produced — the mint turns the DRAFT into the approval `create_lease` demands,
    the SR carries the PR's id, the task carries the root revision the lease validates, and the
    header the gate parses is the nonce the lease minted. A link that quietly stopped feeding the
    next one leaves every unit test green.

    German text throughout, because that is what this file is for: the whole chain crosses process
    boundaries as raw UTF-8, and an item title mangled on the way in reappears as a dispatch that
    refuses to match itself.
    """
    state, task, header = _leased_task(tmp_path)
    spawn = launched_hook("gate_dispatch.py", {
        "hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": str(tmp_path),
        "tool_input": {"subagent_type": "backend-developer",
                       "prompt": "objective: Rechnungsliste bauen\n%s\noutput: Diff" % header},
    }, tmp_path)
    assert spawn.returncode == 0, spawn.stderr.decode("utf-8", "replace")
    lease = state._read_yaml(os.path.join(state.root, "tasks", "leases",
                                          task["id"] + ".lease.yaml"))
    assert lease.get("awaiting_bind_until")  # the child may now claim the task

    # the counter-direction on the same chain: the role the task was NOT planned for is refused,
    # so the pass above measures the chain and not a gate that waves everything through.
    other = launched_hook("gate_dispatch.py", {
        "hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": str(tmp_path),
        "tool_input": {"subagent_type": "frontend-developer",
                       "prompt": "objective: Rechnungsliste bauen\n%s\noutput: Diff" % header},
    }, tmp_path)
    assert other.returncode == 2


def test_e2e_a_lock_held_by_a_foreign_process_makes_the_gate_wait_not_skip(tmp_path):
    """Spec II.12, v2.1 test cases: "Lock: zweiter Prozess wartet/blockt."

    The kernel's own lock tests run inside one interpreter. This is the case the lock exists for:
    another PROCESS holds it — a `harness` command, a second agent session — while a shipped hook
    needs the state. The failure this rules out is the silent one: a gate that finds the lock taken
    and proceeds unlocked would still exit 0, and only a torn write days later would show it.

    Measured as elapsed time, because "waited" and "did not wait" are otherwise the same green.
    """
    state, _task, header = _leased_task(tmp_path)
    hold = 2.0
    holder = subprocess.Popen(
        [sys.executable, "-c",
         "import sys, time\n"
         "sys.path.insert(0, %r)\n"
         "from kernel.lock import KernelLock\n"
         "lock = KernelLock(%r).acquire()\n"
         "sys.stdout.write('held\\n')\n"
         "sys.stdout.flush()\n"
         "time.sleep(%r)\n"
         "lock.release()\n" % (os.path.join(ROOT, "team-kits"), state.root, hold)],
        stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        started = time.monotonic()
        spawn = launched_hook("gate_dispatch.py", {
            "hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": str(tmp_path),
            "tool_input": {"subagent_type": "backend-developer",
                           "prompt": "objective: Rechnungsliste bauen\n%s\noutput: Diff" % header},
        }, tmp_path)
        waited = time.monotonic() - started
    finally:
        holder.wait(timeout=30)
    assert spawn.returncode == 0, spawn.stderr.decode("utf-8", "replace")
    assert waited >= hold / 2, (
        "the dispatch gate answered in %.2fs while another process held the kernel lock for %.1fs "
        "— it did not wait for the lock." % (waited, hold))


def test_e2e_quality_scalar_configs_never_crash(tmp_path):
    """Scalar-typed knobs (coverage_gate: streng / project: string) crashed the structured
    branches with AttributeError — the whole pipeline died with a traceback (audit repro).
    Type guards must fall back gracefully."""
    scripts = tmp_path / "scripts"
    os.makedirs(str(scripts))
    for f in ("quality.py", "kit_checks.py", "kit_browser_checks.py"):
        import shutil as _sh
        _sh.copy(os.path.join(SCRIPTS, f), str(scripts / f))
    invariants = tmp_path / "project_memory" / "invariants" / "active"
    write(str(invariants / "INV-0001.yaml"),
          "id: INV-0001\nscope: coverage_gate\nsource: PR-0001\n"
          "check: {kind: test, ref: tests/t.py::t}\nvalue: streng\nstatus: unverified\n")
    write(str(tmp_path / "project_memory" / "project_config.yaml"), "project: nur-ein-string\n")
    r = subprocess.run([sys.executable, str(scripts / "quality.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(tmp_path), timeout=120)
    assert "Traceback" not in (r.stdout + r.stderr)
    assert r.returncode in (0, 1)  # honest verdict, never a crash


# ---------------- scenario: the QA-evidence merge gate, end to end ----------------
def test_e2e_the_merge_gate_opens_on_evidence_a_role_produced_and_shuts_on_a_fresh_fail(tmp_path):
    """Task done → QA records Evidence through the harness CLI → merge. Three states, one repo.

    The scenario the phase-0 disposition asks for (rows 115/338/507), and the reason it is here
    rather than only in the unit suite: the V1 gate demanded a `project_memory/*report*.yaml`
    that NOTHING in V2 could write, so it blocked every merge and push in a scaffolded project.
    Proving that is fixed means proving both halves in the same repo — that the gate still
    refuses without proof, and that the proof is something a role can actually produce. So the
    Evidence here is written by the shipped `python scripts/harness.py evidence` command, not by the test.

    Both hooks run behind `_gate.py`, the way `settings.json` registers them; and the whole path
    carries German item text, because that is what this file exists to catch.
    """
    state, task, _header = _leased_task(tmp_path)
    merge = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(tmp_path),
             "tool_input": {"command": "git merge feat/%s-rechnungsübersicht"
                                       % task["product_requirement"]}}

    blocked = launched_hook("gate_git.py", merge, tmp_path)
    assert blocked.returncode == 2
    assert "no QA Evidence" in blocked.stderr.decode("utf-8", "replace")

    # The shipped entry point, in the position a project has it: `scripts/harness.py` beside a
    # `.claude/hooks` bridge. Copied rather than scaffolded because this file's subject is the
    # gate/kernel chain — that the INSTALLERS put the file there is measured separately, by
    # `test_the_evidence_the_merge_gate_demands_has_an_installed_producer`. What is measured here
    # is that the command a role types resolves the state directory on its own: no `--root`
    # appears below, and the Evidence still lands in the repo's own state.
    sys.path.insert(0, os.path.join(ROOT, "team-kits"))
    from kernel import cli
    shutil.copytree(HOOKS, os.path.join(str(tmp_path), ".claude", "hooks"), dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    entry = os.path.join(str(tmp_path), *cli.ENTRY_POINT.split("/"))
    os.makedirs(os.path.dirname(entry), exist_ok=True)
    shutil.copyfile(os.path.join(ROOT, "team-kits", "dev-team", "templates", "repo",
                                 *cli.ENTRY_POINT.split("/")), entry)

    def record(kind, result):
        return subprocess.run(
            [sys.executable, os.path.join(*cli.ENTRY_POINT.split("/")), "evidence",
             "--kind", kind, "--result", result, "--related", task["id"],
             "--summary", "Rechnungsübersicht geprüft", "--artifact-ref",
             "staging/%s/lauf.log" % task["id"],
             "--run-command", "python scripts/quality.py", "--run-scope", "full"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=dict(os.environ, HARNESS_KERNEL_PATH=os.path.join(ROOT, "team-kits")),
            cwd=str(tmp_path), timeout=120)

    # One Evidence per delivery-judging kind, because that is what the gate now waits for — and
    # the kinds come from the kernel, so a widened vocabulary changes this run instead of leaving
    # it asserting rc 0 against a set the gate refuses.
    sys.path.insert(0, os.path.join(ROOT, "team-kits"))
    from kernel.backlog_types import QA_EVIDENCE_KINDS
    for kind in sorted(QA_EVIDENCE_KINDS):
        recorded = record(kind, "pass")
        assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    assert launched_hook("gate_git.py", merge, tmp_path).returncode == 0

    # ...and the gate is not simply stuck open afterwards: a regression found later re-blocks it,
    # bound through the TASK to the PR the branch names — the indirect binding the V1 gate could
    # only approximate by matching the item's name anywhere in a file.
    assert record("test", "fail").returncode == 0
    reblocked = launched_hook("gate_git.py", merge, tmp_path)
    assert reblocked.returncode == 2
    assert "not a pass" in reblocked.stderr.decode("utf-8", "replace")

    # force-push stays refused throughout — it is not a QA question
    forced = launched_hook("gate_git.py", dict(
        merge, tool_input={"command": "git push --force origin main"}), tmp_path)
    assert forced.returncode == 2
    assert "force-push" in forced.stderr.decode("utf-8", "replace")


# ---------------- scenario: the sanctioned edit path (BUG-0001), through the real CLI ----------
def _update_cli(root, item_id, changes):
    """Run `python -B -m kernel.cli update <item_id>` as a REAL process, JSON changes on stdin.

    The command reads its changes as a JSON object on stdin, exactly like `capture`; the guards
    that decide which changes are legal live in `state.update_item`, so this drives the running
    surface rather than the function under it.
    """
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "team-kits"))
    return subprocess.run(
        [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory",
         "update", item_id],
        input=json.dumps(changes, ensure_ascii=False).encode("utf-8"),
        capture_output=True, env=env, cwd=str(root), timeout=120)


def _approved_pr(repo):
    """Capture a PR and take it to APPROVED through a REAL approval mint, returning (state, pr_id).

    The mint is the one step a test cannot shortcut (`approvals.mint` refuses every caller but
    `gate_approval.py`), so after this the PR carries a LIVE `approval_ref` — the thing an
    invalidating edit has to clear.
    """
    state = ProjectState(os.path.join(str(repo), "project_memory"))
    os.makedirs(state.root, exist_ok=True)
    pr = state.capture("PR", {
        "title": "Rechnungsübersicht für Käufer", "class": "normal",
        "problem": "der Käufer sieht seine Rechnungen nicht",
        "goal": "Rechnungsliste im Konto",
        "acceptance_criteria": [{"id": "AC-1", "text": "Käufer sieht seine Rechnungen"}],
        "invariants": [], "out_of_scope": [], "priority": "high",
        "user_story": "Als Käufer sehe ich meine Rechnungen",
    })
    request = approvals.create_pending_request(state, "scope", pr["id"])
    question = approvals.build_question(request)
    approved = launched_hook("gate_approval.py", {
        "hook_event_name": "PostToolUse", "tool_name": "AskUserQuestion", "cwd": str(repo),
        "tool_input": {"questions": [question]},
        "tool_response": {"questions": [question], "answers": {
            question["question"]: approvals.approve_label(request["mint_code"])}},
    }, repo)
    assert approved.returncode == 0, approved.stderr.decode("utf-8", "replace")
    assert state.read_item(pr["id"])["status"] == "APPROVED"
    return state, pr["id"]


def test_e2e_update_changes_a_field_and_invalidates_a_current_approval(tmp_path):
    """The `update` command exists (BUG-0001: `state.update_item` had no CLI surface) and a change
    to a HASHED field of an approved item invalidates the approval ATOMICALLY (spec II.2).

    Measured on the item BEFORE and AFTER through the real CLI process: `goal` is in
    `HASHED_FIELDS['PR']`, so editing it drops the live `approval_ref`, resets the status to the
    invalidation target (DRAFT for a PR) and bumps the revision — the whole reason the edit path is
    the kernel's and not a file write.
    """
    state, pr_id = _approved_pr(tmp_path)
    before = state.read_item(pr_id)
    assert before.get("approval_ref"), before          # a live approval exists to invalidate

    r = _update_cli(tmp_path, pr_id, {"goal": "Rechnungsliste UND Summen im Konto"})
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")

    after = state.read_item(pr_id)
    assert after["goal"] == "Rechnungsliste UND Summen im Konto"   # the edit landed
    assert not after.get("approval_ref")               # approval invalidated
    assert after["status"] == "DRAFT"                  # invalidation_target('PR')
    assert after["revision"] == before["revision"] + 1


@pytest.mark.parametrize("field,value", [
    ("status", "APPROVED"),
    ("id", "PR-9999"),
    ("revision", 99),
    ("approval_ref", "APR-9999"),
    ("created", "1999-01-01T00:00:00"),
])
def test_e2e_update_refuses_a_kernel_set_field_and_leaves_the_item_untouched(tmp_path, field, value):
    """The kernel-set fields (`id`, `status`, `revision`, `approval_ref`, `created`) are NOT
    writable through `update` — otherwise `update` would be a way past the automaton (set `status`
    freely) and past the approval (clear `approval_ref` without a re-mint).

    Refused with rc 1 (a StateError, the command was attempted and the kernel said no), and the
    item on disk is byte-for-byte what it was — in particular the live approval is still there, so
    a refused edit cannot double as a covert invalidation.
    """
    state, pr_id = _approved_pr(tmp_path)
    before = state.read_item(pr_id)

    r = _update_cli(tmp_path, pr_id, {field: value})
    assert r.returncode == 1, r.stderr.decode("utf-8", "replace")
    assert field in r.stderr.decode("utf-8", "replace")
    assert state.read_item(pr_id) == before            # nothing moved, approval intact
