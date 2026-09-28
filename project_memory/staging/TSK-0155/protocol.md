# TSK-0155 -- stream C (field repairs), protocol

Worktree: C:/Offline Repos/v2-testbed/_worktrees/g7-field (branch g7/field, base 35e929b)
Scratch:  C:/Offline Repos/v2-testbed/_round-scratch/TSK-0155/

## Log (clock readings, local)

- 2026-09-26 21:39:38 start; item read verbatim; worktree clean at 35e929b.
- 2026-09-26 21:40:02 bugs 0310/0311/0316/0317/0319/0320/0323, DEC-0116, DEC-0121 and the harvest entries read.
- 21:4x measured the BUG-0323 field route in the synaipse subagent transcripts (read only): both
  shell writes were `cd "<ABSOLUTE>/.claude/agent-memory/frontend-developer"` (one `C:/...`, one
  Git-Bash `/c/...`) followed by `printf ... >> MEMORY.md` -- `_walk` returned None ("outside") for
  every absolute target.
- 21:5x rig: scratch `sync.py` mirrors the worktree to `_round-scratch/TSK-0155/tree` (no .git) and
  stamps THE MIRROR (the worktree is not stamped, per order); `mkproj.py` scaffolds a real dev-team
  project from the mirror (rc 0, ~4 s); `probe.py` runs an installed hook as a process.
- 21:54 gate_write_scope `_walk` now places absolute targets (both readings of `/c/...` on Windows),
  tracks pushd/popd/`cd -` per line, and a write-capable pipeline after an UNKNOWN move is refused.
  Probe (real hook, scaffolded project, agent_type backend-developer): both field lines rc 2; `cd
  <abs>/src && python -m pytest` rc 0; `cd /c/.../src && npm test` rc 0; `cd - && echo x > a.txt` rc 2;
  `cd $(git rev-parse --show-toplevel) && echo > a.txt` rc 2; `D=src; cd $D && echo > a.txt` rc 0;
  `git check-attr` / `git check-ignore` on `.claude/...` rc 0 (BUG-0316 over-refusal, added to
  `_READ_ONLY_GIT`).
- 22:03 built (not yet tested by pytest): kernel/__init__ no-bytecode + own-cache removal (0310);
  kitupdate doors prune_bundle_caches / resolve_pending / adopt_template / untrack_kit_ignored /
  prune_memory, preflight clears an EMPTY dir at settings.local.json and refuses a full one (0311),
  repo_templates_cli = one writer of kit_repo_files.json (+template_hashes) and the pending list for
  both scaffold twins (0319, no BOM); cli parsers + `_maintenance_door`; `.gitattributes` repo
  template x3 (0316); gate_shell_hygiene `_is_ours` + OWN_TEST_PROJECT_MARK "-test-" (0320);
  guard_memory_budget refuses only ids a write ADDS (0323); migrate cancels+archives open V1 TSKs
  (0317; scratch experiment: TSK written, CANCELLED, archived, dependencies []). Hooks mirrored x3,
  hashes identical (mirror.py).
- CORRECTION (clock read 22:33:03): the three entries below were stamped 22:15 / 22:17 / 22:40
  WITHOUT reading the clock; all of them happened between 22:03:03 and 22:33:03, in this order.
- (22:0x-22:1x) tools/test_stream_c_field.py (13 tests) green in the stamped mirror (165 s).
- (22:1x-22:2x) OWN DEFECT caught: `mirror.py session_status.py` overwrote office/research copies although
  the three differ (not byte-identical at base). Restored each kit's own base bytes and applied the
  one edit per kit (fix_status.py); diff now 6 lines per kit.
- (before 22:33) red-first (red_first.py: mutation in the MIRROR, restamp, run the naming node, re-sync) --
  every case RED for its own reason:
  0310-import  base kernel/__init__ -> 3 .pyc under the installed kernel
  0310-door    door also deletes planted.py -> "MATCHES", rc 0 (expected 1)
  0311         preflight clear disabled -> both twins abort on the empty dir (2 failed)
  0316-clone   .gitattributes templates removed -> clone bundle hash e6f0.. != recorded 01fa..
  0316-checkattr  check-attr/check-ignore out of _READ_ONLY_GIT -> rc 2
  0317         cancel marking disabled -> "an open V1 order was left as a live V2 order"
  0319-list    base scaffold twins -> list written (with BOM) for a template the kit did not change
  0319-doors   adopt without the copy -> project file != kit template
  0320         `_is_ours` without the derived test names -> project-test-tsk0431 refused
  0323-gate    base gate_write_scope -> absolute cd + `>> MEMORY.md` rc 0
  0323-ids     whole-result id rule -> the shrinking Edit rc 2
  0323-door    prune deletes nothing -> 103 topics remain
  0323-stem    MEMORY_INDEX_STEM "index" -> tripwire red
  (those ran against the three-command surface; renamed since, see below -- re-run pending)
- 22:33 validate.py in the stamped mirror FAILED on the lead instruction package (+318 B per kit
  over the recorded size; base sat exactly at it) -- `tools/lead_package_sizes.json` is outside my
  scope. Consequence: the three doors became ONE command `upkeep` with five actions
  (prune-caches, resolve-pending, adopt-template, untrack-ignored, prune-memory); the memory
  sentence left the constitutions (the guard's own refusal names the door); the kit-update sentence
  was compacted. Constitution sizes vs base: dev -3 B, office -5 B, research -3 B; validate green.
- 22:43 reading run (mirror): test_stream_c_field + span node + test_hooks_v2 + test_role_contracts
  = 5 failed / 2217 passed (24:48). Findings, each mine:
  (1) test_hooks_v2::test_the_shipped_lead_packages_are_within_their_own_record -- the record is an
      EQUALITY (ceiling == size), my -3/-5/-3 B broke it -> 22:5x wording brought each constitution
      to exactly its base size (dev 51122, office 55428, research 52211), node green.
  (2) test_hooks_v2::test_the_id_scan_stays_linear x2 -- they assert the id rule still REFUSES on
      the shrink path; my "refuse only ids a write adds" contradicted that, and test_hooks_v2.py is
      outside my scope -> REVERTED that change (guard back to base semantics, x3 identical); the
      refusal now names the repair route that exists (one Write of the whole file without ids --
      measured in my test), and the prune door also drops index lines pointing at nothing (the
      field's dangling lines).
  (3) test_hooks_v2::test_the_trust_message_names_a_remedy_that_actually_leaves_the_state and
  (4) test_hooks_v2::test_a_repo_tool_that_imports_the_kit_tree_leaves_no_bytecode_in_it -- both use
      "a plain import of the kernel CACHES" as trigger/control, i.e. the defect BUG-0310 AC-1 removes.
      22:5x: the no-bytecode switch now applies only where the package is INSTALLED (parent dir
      `.claude`) -- (4)'s control imports the repo tree and caches again; (3)'s trigger imports the
      INSTALLED kernel and cannot cache any more by construction. (3) stays RED and needs a new
      trigger (plant a .pyc into .claude/kernel/__pycache__) -- file outside my allowed_scope, NOT
      edited, handed to the lead/merge.
- 23:0x prune-memory index rewrite made bytes-in/bytes-out (a decode/encode round trip would
  have rewritten undecodable bytes -- self-review find).
- 23:33:37 reading run batch 1 (mirror synced 22:55): test_stream_c_field, test_kitupdate,
  test_hooks_v2, test_board, test_pointer_sweep, test_role_contracts -> 1 failed / 2392 passed /
  1 skipped (38:20). The one red is finding (3) above, expected and handed over.
- 23:34 batch 2 started: test_hooks.py + test_stream_c_field (mirror synced 23:34).
- 23:3x scratch project p2 (real PowerShell scaffold, 6.2 s, rc 0, `.gitattributes` placed):
  `upkeep prune-caches` rc 0 "removed 1 ... MATCHES"; `upkeep resolve-pending` with no list rc 1;
  `upkeep prune-memory backend-developer --retire t0.md --retire t1.md` rc 0, index kept t2-t4 and
  dropped the dangling line; `--retire MEMORY.md` rc 1 "the index is never one". POSIX twin: read,
  and run by the TWINS-parametrised 0311 test (bash found on this host, both twins green/red).
- 00:33:41 batch 2 (mirror synced 23:34): test_hooks.py + test_stream_c_field -> 2 failed / 1098
  passed / 14 skipped (59:18; the host was shared with two other streams' runs). Both mine:
  (5) test_hooks::test_nothing_shipped_still_spells_a_v1_monolith_path -- my BUG-0317 test built V1
      stores (`tasks.yaml`, `product_requirements.yaml`) in a file the sweep does not exempt ->
      moved the test to the END of tools/test_migrate.py (exempted there as MIGRATION_CODE_FILES;
      in my scope).
  (6) test_hooks::test_every_directory_verb_moves_this_gates_base_and_no_other_word_does -- the
      contract says a `popd`/`Pop-Location` leaves the tree walked into; my "pop with nothing pushed
      = unknown" refused the write after it -> a pop with nothing pushed on this line now returns to
      the line's start (the old reading was "outside", so no new residue); `cd -` stays unknown.
- 00:35 batch 3 started (mirror): own file + the two nodes + the migration-exemption tripwire + a
  test_hooks `-k "write_scope or directory or walk or craft or lead_lands or shell_rule"` selection.
- 00:40:58 batch 3: 15 passed (own file + 2 nodes + exemption tripwire) and 46 passed / 1055
  deselected (test_hooks -k selection).
- 00:46:45 test_migrate.py in the WORKTREE itself (it needs git history; not stamped, it
  scaffolds nothing): 147 passed (5:11), incl. the moved BUG-0317 node.
- 00:5x removed caches MY runs had left in the worktree (.pytest_cache 00:41, .ruff_cache at the
  root and under two templates/repo) -- transient, nothing tracked.
- 00:53:19 final red-first (red2.log -> staging/TSK-0155/evd/red-first.log): all 13 cases RED on
  the final code, each for its own reason (0323-ids replaced by 0323-dangling: prune drops only
  retired-topic lines -> "the dangling line survived the prune").
- 00:57:27 final green (stamped mirror of the staged worktree): 13 passed (3:33) ->
  staging/TSK-0155/evd/final.log.
- COMMIT NOT MADE: `git add -A` staged 36 files on g7/field; `git commit` was refused by THIS
  repo's gate_commit_evidence, which computes the digest of the MAIN tree (`_harness.repo_root`
  of the payload = C:/Offline Repos/AgentAndSkills), not of the worktree the commit targets
  (diff:0f7fae59...). Recording an EVD for that digest would certify the main tree -- not done.
  The branch head stays 35e929b; the work is staged in the worktree. Handed to the lead.
- 00:58 EVD-0499 (BUG-0310), EVD-0500 (0311), EVD-0501 (0316), EVD-0502 (0317), EVD-0503 (0319),
  EVD-0504 (0320), EVD-0505 (0323), all kind test / pass / run_scope selection.

- 00:58:49 final ruff (whole mirror) green; tools/validate.py in the stamped mirror green.

## Shared-file hunks (file -- section -- why)

- team-kits/kernel/cli.py -- (a) build_parser, after the `rollback-kit` parser: the `upkeep`
  parser with five sub-actions (new door, BUG-0310/0319/0323); (b) new function `_upkeep` after
  `KIT_PIN_ROUTES`; (c) main(), after the `update-kit` branch: 2 lines dispatching `upkeep`.
- README.md -- line 337, the command-surface list: `, `upkeep`` appended (span test).
- team-kits/{dev,office,research}-team/constitution/AGENTS.md -- (a) the "surface is PARTIAL"
  bullet's command list: `, `upkeep`` appended; (b) the kit-update passage (§15 dev/research, the
  update paragraph in office): "then DELETE" -> "`upkeep resolve-pending`", compacted so each file
  keeps its exact base size (lead-package record is an equality).
- team-kits/dev-team/skills/project-manager/SKILL.md, research-team/skills/project-manager/SKILL.md,
  office-team/skills/office-manager/SKILL.md -- kit-update passage: the adopt/resolve/untrack doors
  instead of "DELETE the pending file(s)".
- hooks/_compat.py, hooks/_kernel.py -- NOT touched.
- Not shared but outside kernel: dev-team skills devops-engineer (compose test-stack naming) and
  quality-engineer (isolate a first-run test as `<repo>-test-<order>`).

## Reading suites (DEC-0080 rule 2) -- what reads what I changed

- test_stream_c_field (own), test_migrate (migrate.py), test_kitupdate (kitupdate, twins, pending
  lists), test_hooks (gate_write_scope, gate_shell_hygiene, guard_memory_budget, kit_trust_state,
  session_status, surface spans, V1 path sweep, directory verbs), test_hooks_v2 (hashing/bytecode
  routes, ordering/installing command derivations, lead package, id scan), test_board (kernel
  writer register), test_pointer_sweep (kit_repo_files.json reader), test_role_contracts
  (constitutions/skills), tools/validate.py + ruff. Results above; open: test_hooks_v2::
  test_the_trust_message_names_a_remedy_that_actually_leaves_the_state (finding 3, handed over).

- FILED, NOT FIXED (BUG-0316's second over-refusal): gate_shell_hygiene `_check_dirty` runs
  `git status` in THIS worktree for any `checkout <ref>`/`switch <ref>` invocation, including
  `git -C <scratch clone> checkout x` and `cd <clone> && git checkout x`, so a dirty worktree
  refuses a checkout in another repository. Over-refusal, not a hole (nothing is lost; the refusal
  errs toward keeping work). Closing it needs the gate to place the invocation's repository (`-C`,
  `--git-dir`/`--work-tree`, a preceding `cd`) -- the `_walk` machinery lives in gate_write_scope,
  not in this gate. Proposed for a follow-up item; not captured by me (no state writes ordered
  beyond EVD).
