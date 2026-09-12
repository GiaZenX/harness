# TSK-0142 -- stream B (kits), order 3b of PR-0012 "Bug-Null"

Base: 10a5127 on feat/harness-v2. Streams A (kernel) and C (tools) run in the same working tree.

## The rig (red-first)

`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0142/rig/` -- a copy of `team-kits/`, `tools/`,
`docs/`, `radar/`, `user/`, `.claude/` and the root files, WITHOUT `.git`, taken at 2026-09-12
09:56 from the pristine base. It is never fixed: every new test is copied into it and run there
to see the defect's RED, then run in the repository against the fix to see GREEN. The arbiter is
the pytest line in each row.

## Plan and the way it was REJECTED

The rejected way: fix per hole in the repository first and reconstruct the defect afterwards by
hand-reverting the changed hunk. It loses on two counts measured in generation 3 -- a hand-revert
of a hunk that touches a mirrored file has to be undone in three kits, and a rig that resolves
its paths against the repository reaches the tree it was meant to leave alone. A frozen pristine
copy costs one `cp -r` of 557 files and makes every red reproducible after the fact. What it does
NOT cover: a defect whose reproduction needs the repository's own `.git` (none here -- no row of
my list is about git history).

## Rows

### 2026-09-12 10:11 -- `gate_ledger_valid.py` (office): H62/H64/H67/H68 in ONE change

The four are one defect seen from four sides: the gate cut its command line on the PLAIN text, so
a separator or a `>` inside argument prose was read as shell syntax, and the decoy question was
asked twice with two different conditions. What replaces it is a **syntax view** -- `_syntax_view`
fills the content of a quoted span with a neutral character and keeps the LENGTH, so every cutter
finds its separators there and cuts the original text at the same offsets. One exception, and it
is the whole safety of the construction: the characters of a `_SUBSTITUTION_OPEN_RX` match are
never filled, because `"$(cp evil.py scripts/)"` is a quoted span whose content the shell RUNS.

**The defect my own first cut introduced, found before the suite ran.** The first version asked
`_payload_is_inert` about the span as a whole. That question short-circuits on a single quote --
and `_readings_of` puts synthetic single quotes around values the shell BUILT, so the `'$(tar'` of
`echo "$(tar -xf evil.tar -C scripts/)"` counted as inert, the opening was filled, and the line
went rc 2 -> rc 0: `BUG-0065` reopened by the repair of `BUG-0160`. Measured on the probe matrix
(three KEEP rows flipped to rc 0), repaired by skipping the opening CHARACTER-WISE instead of
asking about the span. The skip is what the final docstring states.

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H62 / BUG-0154 | OVERREF | the decoy question was asked a second time in `_a_reading_writes_the_ledger`'s ledger-path branch, without the read-only condition its own reader carries | `gate_ledger_valid.py` `_a_reading_writes_the_ledger`: the second `_DECOY_VALIDATOR_RX` branch removed, the reason written where it stood | rig `grep "tools/ledger_add.py" ledger/2026.csv && git commit -m x` rc 2 -> repo rc 0; pytest node RED in rig | `tools/test_hooks_v2.py::test_a_decoy_path_in_a_reading_stage_is_prose` | see run below | EVD-0327 |
| H64 / BUG-0156 | OVERREF | `_redirect_targets` read every `>` of the raw segment, quoted argument prose included | `_redirect_targets` now finds the operator in `_syntax_view(segment)` and reads the target out of the text at the same offsets | rig `grep -n "row > ledger/2026.csv" ledger/2026.csv && git commit -m x` rc 2 -> repo rc 0; node RED in rig | `tools/test_hooks_v2.py::test_a_quoted_redirection_sign_in_argument_prose_is_not_a_redirect` | see run below | EVD-0328 |
| H67 / BUG-0159 | DESIGN/hole | the decoy check lived inside `_writes_ledger`, which `handle_pre_tool_use` asks only under `blocked_op` | new `uses_an_unguarded_validator` + a refusal of its own in `handle_pre_tool_use`, asked of EVERY shell line | rig `python tools/ledger_add.py` rc 0 -> repo rc 2; node RED in rig | `tools/test_hooks_v2.py::test_an_unguarded_validator_is_refused_without_a_blocked_operation` | see run below | EVD-0329 |
| H68 / BUG-0160 | OVERREF | the segment and stage cuts were plain text splits | `_COMMAND_CUT_RX` / `_STAGE_CUT_RX` + `_cut` over `_syntax_view`; the substitution opening is a member of the cut instead of a rewrite of the text | rig `grep "a; b" ledger/2026.csv && git commit -m x` rc 2 -> repo rc 0; node RED in rig | `tools/test_hooks_v2.py::test_a_quoted_separator_is_argument_text_and_a_substitution_still_cuts` | see run below | EVD-0330 |

`BUG-0160`'s OTHER half -- a hand-typed backslash in the validator path -- was measured ALREADY
CLOSED at the base: `python scripts\ledger_add.py --validate ledger/2026.csv` is rc 0 in the
pristine rig. Written down rather than claimed as this round's work.

Red-first arbiter, one line: pristine rig `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0142/rig`
with the NEW test file copied in --
`python -B -m pytest tools/test_hooks_v2.py -q -p no:randomly -k "unguarded_validator or decoy_path_in_a_reading_stage or quoted_redirection_sign or quoted_separator_is_argument_text or neighbour_of_a_vouched_run"`
-> **6 failed, 10 passed** (5.8 s). Same line in the repository -> **16 passed** (6.9 s).

Runs: `pytest -q -p no:randomly <the five node ids>` -> 7 passed, 6.7 s
(`staging/TSK-0142/run-ledger-gate.log`).
A wider reading selection (`-k "ledger or validator or vouched or decoy or redirect or stage or
word_end or heredoc or substitution"`) -> 975 passed, 5 failed, 167 s; two of the five are the
matrix rows this change re-pinned, three are foreign (below). 167 s is over the three-minute
guidance and that selection is not repeated.

### Foreign reds (2026-09-12 10:05, seen once, NOT reproducible alone)

* `tools/test_hooks_v2.py::test_resolving_the_quoting_does_not_refuse_what_the_quoting_protected[echo 'a > b is a redirect']`
* `tools/test_hooks_v2.py::test_a_redirect_inside_a_quoted_program_counts[awk 'BEGIN{print "x" > "project_memory/approvals/APR-0001.yaml"}']`
* `tools/test_hooks_v2.py::test_a_redirect_inside_a_quoted_program_counts[awk 'BEGIN{while((getline l < ".claude/hooks/gate_approval.py")>0) print l > "kk/g.py"}']`

All three read `.claude/hooks/` and `team-kits/kernel/`, both of which streams A and C were editing
during that 167 s run. Re-run alone immediately afterwards: **9 passed** in the repository AND 9
passed in the pristine rig. Left alone.

### 2026-09-12 10:16 -- H117 / BUG-0201 and BUG-0030

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H117 / BUG-0201 | DESIGN | nothing started `tools/finance_dashboard.py`; the ledger's two write paths pass `handle_post_tool_use`, which validated and did nothing else | `gate_ledger_valid.py`: `_render_the_finance_page` + `RENDERER`/`RENDER_TIMEOUT`, called where the handler has already found a changed ledger; every failure a note, never a block. `templates/repo/dashboards/ABOUT.txt`: the "IT DOES NOT REBUILD ITSELF YET" paragraph replaced by what IS built and what still is not (a change outside a tool call) | rig: `pytest tools/test_finance_dashboard.py::test_a_ledger_write_renders_the_finance_page` -> **1 failed** (no page after the edit); repo -> **1 passed** | `tools/test_finance_dashboard.py::test_a_ledger_write_renders_the_finance_page` | `tools/test_finance_dashboard.py` whole: 53 passed, 67 s | EVD-0332 |
| BUG-0030 | hygiene | two literal 0x08 bytes in a shipped hook; nothing would catch the next one | the bytes were measured ALREADY GONE at the base (scan over every kit hook, script, tool, skill and constitution: 0 files). What this round adds is AC-1's measurement as a tripwire: `tools/test_hooks.py::test_no_shipped_kit_file_carries_a_control_character`, over `kernel.hashing.kit_hash_inputs` of all three kits, text decided by "decodes as UTF-8" | rig with one 0x08 injected into `office-team/hooks/gate_ledger_valid.py` -> **1 failed**, naming the file; byte removed -> passes; repo -> **1 passed** (4.9 s) | `tools/test_hooks.py::test_no_shipped_kit_file_carries_a_control_character` | node id, 4.9 s | EVD-0333 |

AC-2 of BUG-0030 ("byte-identical mirrored, kit stamp new") is not this stream's to close: the
stamp belongs to the merging item (`bump_kit_version.py` is forbidden here), and the file is
office-only, so there is no mirror to compare. Named, not claimed.

### 2026-09-12 10:48 -- `gate_write_scope.py` + `_compat.py` (all three kits, mirrored)

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H201 / BUG-0285 | ENUM | three enumerations of the directory verbs (a tuple in `handle_shell`, `== "popd"` in `_walk`, four words inside `_READ_ONLY_VERBS`) and all three short of the written-out PowerShell cmdlets | one `_DIRECTORY_VERBS` mapping spelling -> kind; `_READ_ONLY_VERBS` derives its entries from it, `_walk` asks it for `pop`, `handle_shell` asks it for membership | probe, real hook, two-step entry `<verb> .github ; <verb> hooks ; echo x > note.txt`: rig **chdir rc 0, sl rc 0, push-location rc 0** (one spelling MORE than the report knew), repo all rc 2; `cd .github ; cd hooks ; pop-location ; echo x > note.txt` rig rc 2 -> repo rc 0; pytest node RED in rig | `tools/test_hooks.py::test_every_directory_verb_moves_this_gates_base_and_no_other_word_does` | below | EVD-0337 |
| H204 / BUG-0288 | DESIGN | a command substitution is a command in a WORD; the decomposition knew separators, stages and parens, and the prose removal deleted the span before any reader | `substitution_bodies()` + `prose_removed_view()`: the bodies are APPENDED as their own pipelines (not spliced with a separator -- that lands inside the quoted span, measured on the ledger gate this round) | rig `echo $(cp evil.py .claude/hooks/g.py)` rc 0 -> repo rc 2; same for the three `-m` spellings; node RED in rig | `tools/test_hooks.py::test_a_command_a_substitution_introduces_is_judged_as_a_command` | below | EVD-0338 |
| H205 / BUG-0289 | DESIGN | `_HEREDOC_RX` removed EVERY body, and a body is where a shell gets its program | new `_compat.prose_heredoc_free` (a body is removed unless a command parser is fed it), used by `prose_removed_view`; `_heredoc_scan` is the one scanner both `_compat` readers share | rig `bash <<'EOF' / echo x > project_memory/x.yaml / EOF` rc 0 -> repo rc 2; node RED in rig | `tools/test_hooks.py::test_a_heredoc_body_handed_to_a_shell_is_judged_as_a_command` | below | EVD-0339 |
| H15 / BUG-0107 | DESIGN | the workshop's gates borrow this module's UNDERSCORED helpers and nothing declared that surface | `HARNESS_BORROWS` in the kit + a test that reads `_harness.py` with `ast` and holds both ends | rig: `HARNESS_BORROWS` does not exist -> node RED; repo green | `tools/test_hooks.py::test_the_harness_borrows_only_what_this_kit_declares` | below | EVD-0340 |

**The second defect I introduced and caught.** Switching the heredoc removal to
`_compat.literal_heredoc_free` closed H205 and broke the other end in the same move:
`tools/test_hooks_v2.py::test_a_heredoc_body_is_prose` went red, because an UNQUOTED delimiter
means the shell expands the body and that reader therefore KEEPS it -- so
`cat > /tmp/notes.md <<EOF` with `project_memory` in its prose became rc 2. The two readers answer
different questions and `prose_heredoc_free` is the second one; both are now named beside each
other in `_compat`.

**And the first one, live:** a stray parenthesis in `gate_write_scope.py` made
`_harness.shell_reader` raise and gate 1 refused EVERY Bash call of this session until the file
parsed again (repaired through `Edit`, which does not take that path). That is `BUG-0107`'s own
failure direction, measured by accident, and it is what the new declaration is for.

Mirror after every change: `hooks/gate_write_scope.py` dev=office=research `d53e2681fa9a`,
`hooks/_compat.py` dev=office=research `1058422a4df3` (sha256 head, binary read).

Runs: `pytest tools/test_hooks.py -k "write_scope or heredoc or substitution or redirect or
pipeline or read_only or prose or verb or borrow or directory"` -> 150 passed, 121 s.
`pytest tools/test_hooks_v2.py -k "write_scope or heredoc or quoted_program or prose or directory
or pushd or walk or compat"` -> 220 passed, 88 s. The two probe matrices
(`cases-ws*.json`, `cases-ledger*.json`) unchanged in every KEEP/OK row.

### 2026-09-12 10:50 -- `_compat.py` H57 / H66, and the third defect of my own

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H57 / BUG-0149 | OVERREF-turned-hole | `gate_ledger_valid` borrowed `_compat.literal_heredoc_free`, which answers what the SHELL EXPANDS -- so the body of `python <<'EOF'` was removed, and a body handed to an INTERPRETER is a program that can replace the ledger's judge | `_compat.heredoc_free(command, keep)` is now the one scanner and the CONDITION is the caller's; the ledger gate passes its own: a body is prose only when the program that receives it only reads (`_verb_only_reads(head)`) | rig `python <<'EOF' / open('scripts/ledger_add.py','w')... / EOF` rc 0 -> repo rc 2 (same for `perl`, and for a ledger write plus a commit); P4-12's `cat` heredoc stays rc 0 in both | `tools/test_hooks_v2.py::test_a_heredoc_body_an_interpreter_executes_is_not_prose_here` | below | EVD-0343 |
| H66 / BUG-0158 | INSTR | `shell_words` promised "every reading an ordinary shell could give" and resolved only the POSIX backslash; PowerShell's backtick escape was resolved by nothing | one reading per entry of `_ESCAPE_CHARS` (`_escape_rx`), derived instead of spelled; `gate_ledger_valid._readings_of` judges EVERY reading instead of the first and the last, which would have skipped the new middle one | rig `copy-item evil.py scr`+backtick+`ipts/ ; git commit -m x` rc 0 (control without the backtick rc 2) -> repo rc 2; node RED in rig | `tools/test_hooks.py::test_every_escape_character_of_this_kit_gets_its_own_reading` | below | EVD-0344 |

**The third defect I introduced and caught.** `substitution_bodies` carried ONE set of substitution
openings including the backtick. In a PowerShell line the backtick is the LINE CONTINUATION, so it
opened a substitution that never closed and the rest of the line became its own pipeline:
`test_a_continuation_the_named_shell_does_not_honour_is_not_joined[PowerShell-backtick + LF]` went
red in all three kits (235 s selection). The set is per shell now
(`_SUBSTITUTIONS_BY_SHELL`) and the tool is threaded from the payload; the union is NOT the safe
direction here, and the comment says so with this measurement.

Mirror: `gate_write_scope.py` `0193db282e40`, `_compat.py` `c9fba81ebacb`, identical in all three
kits (sha256 head, binary read).

Runs after the change: `pytest tools/test_hooks_v2.py -k "continuation"` 29 passed 30 s;
`-k "ledger or validator or vouched or decoy"` **918 passed, 241 s**; the seven new/adjacent node
ids 7 passed 13 s.

### 2026-09-12 11:08 -- H168 / BUG-0250 leftovers, and the STAMP-DEPENDENT REDS

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H168 / BUG-0250 | DESIGN | the two SKILL bullets and the three config templates were already repaired at the base (`STALE_LADDER_TEXTS` is empty and `tools/test_model_ladder.py` is green); what was NOT was the `light` -> haiku translation, still live in five files after `model_tiers.yaml` retired that rung | `scaffold_team.sh` (frontmatter rewrite + model_map stamping), `scaffold_team.ps1` (the same two), `session_status.py` in all three kits (the unresolved-alias list and the `canon` map) | rig: `pytest tools/test_model_pins.py::test_no_installer_or_hook_translates_a_tier_alias_the_table_does_not_declare` -> **1 failed**, naming `['haiku', 'light']` in `scaffold_team.sh`; repo -> 1 passed | `tools/test_model_pins.py::test_no_installer_or_hook_translates_a_tier_alias_the_table_does_not_declare` | `tools/test_model_pins.py` + `tools/test_model_ladder.py` whole: 19 passed, 16 s | EVD-0362 |

The part of BUG-0250 that was already closed is written down rather than claimed: the SKILLs say
"Up-scaling is not decided in this file", the three `project_config.yaml` templates say
"`light`/haiku are retired", and `STALE_LADDER_TEXTS` is `{}`.

### Stamp-dependent reds -- ELEVEN, expected, and not mine to close

`python tools/bump_kit_version.py` is forbidden in this item (the goal round stamps once), and a
changed kit file makes `write_kit_state` refuse with "does not hash to the `content:` in its own
VERSION". Every scaffold/installer test that really installs therefore fails. Measured on both
sides with the SAME test files: pristine rig `pytest tools/test_hooks.py -k "scaffold or
session_status or alias or model"` -> **34 passed, 6 skipped (305 s)**; repository -> **11 failed,
23 passed, 6 skipped (113 s)**.

* `test_scaffold_ps1_rejects_external_control_file_symlink_before_mutation[scripts/kit_checks.py]`
* `test_scaffold_ps1_rejects_external_control_file_symlink_before_mutation[.claude/kit_update_pending.repo]`
* `test_scaffold_ps1_rolls_back_base_after_provider_collision`
* `test_scaffold_ps1_rejects_unknown_quoted_recorded_preset_before_mutation`
* `test_scaffold_ps1_rejects_duplicate_preset_keys_before_mutation`
* `test_scaffold_preset_and_map_sync`
* `test_the_shipped_scaffold_records_the_trays_of_the_kit_it_installs` (4 parametrisations)
* `test_both_scaffold_launchers_leave_no_tier_alias_in_installed_frontmatter`

They go green with the merge's single `bump_kit_version.py`. Nothing else in the selection failed.

### 2026-09-12 11:21 -- BUG-0262, BUG-0207, and the three seams stream C handed over

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H180 / BUG-0262 | INSTR | a timing test FAILED when its stability reading could not be taken, so a busy host turned a delivery run red for a reason that is not the code | `tools/test_hooks_v2.py`: the decision is its own function (`_skip_unless_the_stability_reading_can_be_taken`) and SKIPS with both figures; the linearity assertion behind it still fails loudly | rig with the `raise AssertionError` form restored in that function -> **1 failed**; repo -> 1 passed | `tools/test_hooks_v2.py::test_a_timing_reading_that_cannot_be_taken_skips_and_does_not_fail` | node ids, 4 s | EVD-0364 |
| H123 / BUG-0207 | DESIGN | `_filing` reads `robocopy`/`rsync` as copiers, the copy/move branch answered and RETURNED before any destroying word was looked for; and a `/`-introduced flag stood in none of the three positions the destroying-word reader looks at | `guard_fs_tripwire.py`: the move branch no longer returns unconditionally -- a copier carrying a destroying word and NOT relocating destroys in its DESTINATION, which becomes the reach; a word introduced with `-` **or** `/` is read as a flag; `mir`/`mirror` join `SWEEPING_DESTRUCTION` with the reason (a mirror removes what it does not name) | probe, real guard: rig `robocopy inbox archive/finance/2026 /MIR` rc 0, `/PURGE` rc 0, `rsync --delete` rc 0, `rsync --del` rc 0 -> repo all rc 2, while every ordinary filing row (`--remove-source-files`, `/MOVE`, `cp`, `mv`, copy-out, absolute path) stays rc 0 in both; node RED in rig | `tools/test_hooks.py::test_a_copier_that_destroys_in_its_destination_is_a_delete_there` | `pytest tools/test_hooks.py -k "tripwire or destro or archive or filing or sweep or tray"` 125 passed / 4 stamp-failed, 178 s | (below) |
| BUG-0263 AC-4 (seam from C) | ENUM | a second fenced-block reader in `tools/test_office_package.py`, written while the repo-wide one was fence-blinded | `_FENCE_RX` and `_outside_fences` deleted; `hygiene._test_citations(text)` is asked directly, since that reader carries `_without_fenced_blocks` itself now | -- (a deletion; the FLOOR of 8 / 9 citations is what would catch a silent loss, and it holds) | `tools/test_office_package.py::test_every_test_the_field_report_verdicts_name_is_one_that_exists` (2 parametrisations, 8 s) | as named | -- |

**Seam (2) from stream C -- the three DEAD test pointers -- resolve.** Measured through the
kernel's own reader (`kernel.naming_tests.declares`) at 11:30: all three nodes exist
(`tools/test_hooks.py::test_every_escape_character_of_this_kit_gets_its_own_reading`,
`tools/test_hooks_v2.py::test_a_heredoc_body_an_interpreter_executes_is_not_prose_here`). They were
written by me in the same hour; C's sweep read the tree before they landed. No edit needed.

**Seam (3) from stream C -- the PowerShell parse error at `scaffold_team.ps1:545` WAS MINE**, and
it is the fourth defect I introduced this round: removing the retired `-replace` from a
backtick-continued chain left a trailing continuation with nothing behind it. Repaired; the arbiter
is PowerShell's own parser (`[Parser]::ParseFile`, probe `ps_parse.ps1`) -- `scaffold_team.ps1`,
`init_project_memory.ps1` and `install.ps1` all parse clean. `tools/test_pointer_sweep.py
-k test_the_root_files_the_sweep_skips_are_installed_and_would_be_noisy` still reports 3 failed,
and the reason is now the STAMP class, not the parse: the scaffold log ends in
"`does not hash to the content: in its own VERSION`". Those three join the list below.

Stamp-dependent reds are therefore **fourteen**, not eleven -- the three
`test_pointer_sweep.py::test_the_root_files_the_sweep_skips_are_installed_and_would_be_noisy`
parametrisations belong to the same class and go green with the merge's single bump.

### 2026-09-12 11:30 -- H94, H193, H70

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H94 / BUG-0186 | DESIGN | the research constitution gave the rendered report to the Report-Writer and made it a completeness condition, while §0 refuses every tool write under the state directory -- and neither section named `freeze-report`, the one route that exists | `research-team/constitution/AGENTS.md`: §17 names the command, its three stdin keys and where `--help` is the authority; the §6 ownership row points at §17 | rig: the node asserts `freeze-report` is in both sections -> **1 failed** on §6; repo -> 1 passed. The command itself is read off the SHIPPED PARSER, so a rename there is red too | `tools/test_role_contracts.py::test_the_research_constitution_names_the_command_that_files_a_rendered_report` | `tools/test_role_contracts.py` whole: 36 passed, 6 s | EVD-0370 |
| H193 / BUG-0277 | DESIGN | a staging without `write_kit_state.py` installed green on a `[warn]`; the same staging is then refused by every stamp check, because the recorder is a `kit_hash_inputs` member | `scaffold_team.sh` + `scaffold_team.ps1`: an explicit refusal right after the preflight, BEFORE anything is copied, naming both halves of the consequence | rig: both launchers rc 0 on a staging with the recorder removed -> repo rc != 0 with no `.claude/hooks` in the project; the same staging with the recorder back is not refused by that rule | `tools/test_hooks.py::test_a_staging_without_its_trust_recorder_is_refused_before_anything_is_installed` | that node, 48 s | EVD-0371 |
| H70 / BUG-0162 | INSTR | the completeness tripwire asks which PATTERNS the exemption consults, so an exemption consulting none frees a stage while both readers stay green | `tools/test_hooks_v2.py`: a second tripwire that asks the OUTCOME -- every stage `_stages_beside_the_vouched_runs` drops must be claimed by one of the three named exemptions, and every stage they claim must be dropped | mutant tree (`_round-scratch/TSK-0142/mutant`) with `stage.strip().startswith("deno ")` planted as a fourth exemption: the NEW node **1 failed** naming the freed stage, the OLD pattern tripwire **passed** in the same run -- which is `BUG-0162`'s mechanism, measured | `tools/test_hooks_v2.py::test_every_stage_the_exemption_frees_is_freed_by_a_named_exemption` | 302 passed, 6.6 s (the three vouching node selections) | EVD-0372 |

`_may_open_a_vouched_stage` was asking the gate for a decomposition it no longer makes (a plain
`_SEGMENT_SPLIT_RX.split` plus `split("|")`); it goes through the shipped `_cut` now, and the three
cut patterns are named in `_REFUSING_PATTERNS_OF_THE_EXEMPTION` so the equality stays an equality.

### The constitution PIN -- handed over, not written

`python tools/pin_constitution_sections.py` reports **2 CHANGED sections**, both
`research-team constitution/AGENTS.md`:

* `§17. Experiment & application reports` -- anchors no registered hook
* `§6. Items + ownership (the kernel WRITES; these roles own the CONTENT)` -- anchors
  `gate_dispatch`, `gate_subagent_output`

`tools/test_shortening_net.py::test_no_section_of_a_pinned_instruction_file_disappears_unnoticed`
is RED on exactly those two (35 passed, 1 failed, 55 s). I did NOT re-pin: `--write` appends the
journal line to `docs/reviews/phase0-disposition.md`, and `docs/**` is this item's forbidden scope.
Writing the pin JSON alone would be worse than leaving it -- the next `--write` would then find
nothing to report and the journal would never get the trace, which is the one thing that tool
exists for. **Seam handoff, one command, for whoever may write the journal:**

    python tools/pin_constitution_sections.py --write --note "BUG-0186: research §17 and the §6 ownership row name `freeze-report`, the only route a rendered report has into canonical state (§0 refuses every tool write there). No rule classified `behalten` is lost: both sections keep every sentence and gain the command."

### 2026-09-12 11:51 -- H177 / BUG-0259, and the two seams from stream A

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H177 / BUG-0259 | DESIGN | the neutrality rule walks LISTS, so a SCALAR was never judged and `correspondence.yaml` shipped three terms the kit decided for the business -- each written verbatim into a letter a customer reads | `correspondence.yaml`: `address`, `closing` and `offer.valid_days` ship EMPTY with the reason in the header; `letter_draft.a_term` already refuses each with the route, so no script change was needed | rig: the new node names all three filled values -> **1 failed**; repo -> 1 passed | `tools/test_kit_neutrality.py::test_every_term_the_letter_writer_reads_ships_empty` | `tools/test_office_package.py` + `tools/test_kit_neutrality.py`: **79 passed**, 90 s | EVD-0373 |

The rule is DERIVED from `letter_draft.py`'s own `a_term(...)` call sites (read with `ast`), not
from a list of keys: a term added to that script is under the rule the day it ships.

**My fifth self-introduced defect**, and it is the price of the change rather than a slip: emptying
the three terms turned **21** tests of `tools/test_office_package.py` red at once, because every
pilot drafted a letter from the SHIPPED template. Repaired where a real project repairs it -- a
`declare_the_terms(repo)` fixture that records them through the document, called by
`declare_the_ladder`; idempotent, because a second blind replace produced `address: "Sie" "Sie"`
and a YAML error that reads as the script under test crashing. Two parametrised plants had to
follow (`closing`, `valid_days`), and one row of `test_a_reminder_the_data_does_not_carry_is_refused`
now declares the terms first, because they are refused BEFORE the ladder and that row is about the
ladder.

**Seam S2 from stream A -- `--run-scope` in the spelled-out `evidence` calls.** 23 call sites,
3 already carried it. I added `--run-command` AND `--run-scope` (the parser needs both, so a line
naming only the scope is one argparse rejects) to **17** in my scope:

* `team-kits/{dev,research}-team/hooks/gate_git.py` -- six remedies each, mirrored;
* `team-kits/{dev,office,research}-team/skills/project-auditor/SKILL.md`;
* `team-kits/dev-team/skills/quality-engineer/SKILL.md`;
* `team-kits/research-team/skills/reviewer/SKILL.md`.

Measured after the change through the test's own reader: the ONLY call sites still without
`--run-scope` are **`README.md`, `team-kits/kernel/staging.py`, `team-kits/kernel/state.py`** --
all three outside this item's allowed scope. `pytest tools/test_hooks.py -k "evidence or skill or
instruction"` 40 passed, 63 s. **A's parser half can be applied once those three follow.**

`test_the_evidence_the_merge_gate_demands_has_an_installed_producer` had to follow the new scaffold
refusal: its fixture DELETED `write_kit_state.py` from the staging on purpose (to keep the stamp out
of that pin). It replaces it with a NO-OP stand-in now -- the staging stays complete, the stamp
stays out, and the docstring says which of the two reasons each half serves.

### 2026-09-12 11:55 -- H210 / BUG-0294, and verifier finding B9

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H210 / BUG-0294 | DESIGN | `kit_design_render.py` answers rc 3 on a conformance finding and writes `review/render.json` anyway; `gate_design_sighted` reads that record and asks only "was this rendered", so a role that ignored the exit code presented a draft with findings and nothing refused | `gate_design_sighted._verdict` reads the entry's `conformance.findings` as well as its provenance and refuses on them, naming them; `undecided` is deliberately NOT read, and the code says why. The three texts that CLAIMED the non-judgement follow: the renderer's header, the `product-designer` SKILL line and the `ENFORCEMENT.md` row | rig: renderer rc 3, gate **rc 0** -> repo gate **rc 2** naming the finding; the undecided draft (text over a gradient) stays renderer rc 0 / gate rc 0 in both | `tools/test_design_conformance.py::test_a_draft_with_conformance_findings_is_refused_and_an_undecided_one_is_not` | `tools/test_design_conformance.py` whole: 38 passed, 68 s | EVD-0374 |

The test that PINNED the old split
(`test_a_record_is_written_even_when_the_checks_find_something_and_the_sighting_gate_still_opens`)
is the one rewritten: it keeps the half that must not move (the record IS still written on a
finding, or the refusal a designer meets would send them to fix the wrong thing) and inverts the
half that was the hole.

**Verifier finding B9, accepted and repaired.** EVD-0367 recorded `BUG-0263` against
`tools/test_office_package.py::test_every_test_the_field_report_verdicts_name_is_one_that_exists`,
whose first docstring paragraph did not NAME that bug, so `naming_tests.coverage_blocker` refused
it. Repaired at the source: that test's first paragraph now says what it measures from this side --
the duplicate reader is gone and the ONE reader still finds every citation. Re-measured through the
kernel's own reader: `coverage_blocker(root, "BUG-0263", <that node>)` returns `""`. **BUG-0263 is
NOT in my batch lines** -- it is stream C's close (EVD-0358); EVD-0367 stands as a second,
same-direction record from this side.

### 2026-09-12 12:05 -- H90 / BUG-0182, and H94 / BUG-0186 MOVED after a measured ceiling

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H90 / BUG-0182 | DESIGN | `_bookings` pairs its readings on `source`, so two rows differing only in `id` share ONE reading pair; `validate_cross`'s duplicate rule needed an `invoice_no`, which a receipt or a fee often has none of | `templates/repo/scripts/ledger_add.py` `validate_cross`: a second duplicate rule keyed on the WHOLE ROW MINUS THE ID, over live (non-reversed, non-cancelled) rows; the finding names the route (tell them apart in `note`, or reverse) | rig: two identical fee rows -> `--validate` rc 0 ("is valid"); repo -> rc 1 naming "differs only in its id"; the same two told apart in `note` are rc 0 in both | `tools/test_office_package.py::test_one_voucher_booked_twice_without_an_invoice_number_is_refused` | `tools/test_office_package.py` + `tools/test_finance_dashboard.py`: 126 passed, 165 s | EVD-0375 |

**H94 / BUG-0186 moved out of the constitution, and the reason is a measurement.** The first cut
put the route into research `§17` + the `§6` ownership row. `tools/validate.py` then failed with
*"research-team: lead instruction package is 63172 bytes (> 62894 recorded, spec II.5)"* -- the
package sits AT its ceiling, so no addition of any size fits, and raising the record needs
`tools/record_lead_package_sizes.py --write --note`, which is outside this item's scope. Shortening
my own sentence to 17 bytes still left it 9 over, measured.

So the route went where the Report-Writer actually reads it -- `skills/report-writer/SKILL.md`,
outside the lead package -- and that is where the real defect was: that page said to hand the paths
back and *"report the missing promotion step as the infrastructure defect it is"*, a sentence about
a step that had been built and measured in TSK-0106. The constitution is byte-identical with HEAD
again (`git diff` empty), so its two pin entries are gone.

EVD-0370 is SUPERSEDED by **EVD-0376**: its node
(`test_the_research_constitution_names_the_command_that_files_a_rendered_report`) no longer exists,
and an evidence naming a node nothing declares is a run nobody can repeat. EVD-0370 is the lead's
to archive.

### The pin -- ONE section left, handed over

`python tools/pin_constitution_sections.py` now reports **1 CHANGED section**:
`dev-team hooks/ENFORCEMENT.md §1. What each mechanism refuses` (the `gate_design_sighted` row,
rewritten for `BUG-0294`). Same reason as before: `--write` appends the journal line to
`docs/reviews/phase0-disposition.md`, which is this item's forbidden scope.

    python tools/pin_constitution_sections.py --write --note "BUG-0294: the gate_design_sighted row says what the gate now does -- it reads the render record's conformance.findings and refuses a draft that has them, and still does not read `undecided`. No rule classified `behalten` is lost; the row's old sentence claimed a non-judgement the code no longer makes."

## COUNTS -- 2026-09-12 12:07, honest

* **closed: 21** (each with a red-first measurement, a naming node and an EVD through the kernel)
  `BUG-0030` `BUG-0107`/H15 `BUG-0149`/H57 `BUG-0154`/H62 `BUG-0156`/H64 `BUG-0158`/H66
  `BUG-0159`/H67 `BUG-0160`/H68 `BUG-0162`/H70 `BUG-0182`/H90 `BUG-0186`/H94 `BUG-0201`/H117
  `BUG-0207`/H123 `BUG-0250`/H168 `BUG-0259`/H177 `BUG-0262`/H180 `BUG-0277`/H193 `BUG-0285`/H201
  `BUG-0288`/H204 `BUG-0289`/H205 `BUG-0294`/H210
* **downgraded with a measurement: 0.** I opened no exception. Where a row could not be finished,
  it is listed below as NOT REACHED -- which is a different sentence from "measured unclosable",
  and writing it as the latter would be the claim this protocol exists to avoid.
* **handed to the user's patch: 2** -- `BUG-0139`/H47 and `BUG-0055` (both need a file every role
  is forbidden; the exact patches are in "Seam handoffs" below).
* **not reached: 23**, plus `BUG-0056` and seam S3. Wall clock, not judgement: the 21 above took
  the round, and each of them cost a red-first rig, a probe matrix and at least one reading suite.
  `BUG-0196`/H112, `BUG-0240`/H158, `BUG-0153`/H61, `BUG-0143`/H51, `BUG-0169`/H77, `BUG-0151`/H59,
  `BUG-0260`/H178, `BUG-0212`/H129, `BUG-0164`/H72, `BUG-0197`/H113, `BUG-0208`/H124,
  `BUG-0167`/H75, `BUG-0183`/H91, `BUG-0202`/H118, `BUG-0203`/H119, `BUG-0248`/H166,
  `BUG-0222`/H139, `BUG-0223`/H140, `BUG-0174`/H82, `BUG-0191`/H107, `BUG-0147`/H55,
  `BUG-0180`/H88, `BUG-0286`/H202.

What I read of each of those before leaving it: the item's `observed` and `limits`. Three of them
carry a mechanism I would have attempted next and can say where the fix sits, so the next cut does
not start from zero: `BUG-0153`/H61 wants `_kernel.Deadline` in the kits, modelled on
`.claude/hooks/_harness.py::Deadline`, reading the registered `timeout` out of the kit's own
`settings/settings.json`; `BUG-0208`/H124 wants a `business.timezone` field in the office
`business_profile.yaml` template that `_duties.briefing` reads instead of the machine's zone;
`BUG-0222`/H139 is now BUILDABLE for the first time -- it was blocked because its two host files
ship dev/research byte-identical and `research-team/**` was forbidden to TSK-0119, and both are
inside THIS item's scope.

### Verification batch lines (built against a store copy first: 3 lines, **0 refused**)

    python scripts/harness.py request-approval verification --batch BUG-0030 BUG-0107 BUG-0149 BUG-0154 BUG-0156 BUG-0158 BUG-0159 BUG-0160 BUG-0162 BUG-0182
    python scripts/harness.py request-approval verification --batch BUG-0186 BUG-0201 BUG-0207 BUG-0250 BUG-0259 BUG-0262 BUG-0277 BUG-0285 BUG-0288 BUG-0289
    python scripts/harness.py request-approval verification --batch BUG-0294

Every closed id appears in exactly one line. `BUG-0263` is deliberately NOT in them -- it is stream
C's close (EVD-0358); my EVD-0367 is a second record from this side.

### Seam handoffs

1. **`BUG-0139` / H47** -- gate 1 borrows the kits' target reader but not their line-assignment map,
   so `F=team-kits/kernel/state.py; echo x > $F` is rc 0 at the repo gate and rc 2 at the kit gate
   (re-measured today: kit gate rc 2 for both the state and the `.claude` spelling). The kit half
   is ready: `gate_write_scope._line_assignments` / `_resolve` exist and are now declared on the
   borrow surface question. The remaining line is in `.claude/hooks/_harness.py`, which every role
   is forbidden -- USER's shell:
   in `_harness.written_paths`, resolve each redirect target through the kit's map before judging
   it, i.e. build `assignments = module._line_assignments(all_tokens)` once per line and pass every
   target through `module._resolve(target, assignments)`. Add `_line_assignments` and `_resolve` to
   `gate_write_scope.HARNESS_BORROWS` in the same change, or
   `tools/test_hooks.py::test_the_harness_borrows_only_what_this_kit_declares` goes red -- which is
   that test doing its job.
2. **`BUG-0055`** -- the scope manifest has no wireframe field. `_SCOPE_FIELDS` is in
   `team-kits/kernel/approvals.py`, stream A's file and outside mine. The user refused the
   exception, so this needs A: add the field WITH the migration its own comment describes (every
   stored hash changes and every live approval dies), then a red-first probe over "freeze a
   wireframe twice against an APPROVED root".
3. **`tools/pin_constitution_sections.py --write --note "..."`** -- one section
   (`dev-team hooks/ENFORCEMENT.md §1`), command and note spelled out above. The journal lands in
   `docs/reviews/phase0-disposition.md`, this item's forbidden scope.
4. **Seam S2 from stream A (`BUG-0192`/H108)** -- my 17 call sites carry `--run-command` +
   `--run-scope` now. The three that remain are outside my scope and A's parser half waits on them:
   `README.md`, `team-kits/kernel/staging.py`, `team-kits/kernel/state.py`.
5. **Seam S3 from stream A (`BUG-0265`/H183)** -- the installer recording what it copies OUTSIDE
   `.claude/`. NOT ATTEMPTED; the reader half is in A's protocol and waits for the file.
6. **EVD-0370 is superseded by EVD-0376** and is the lead's to archive (an EVD is immutable).

### Foreign reds

* The three from 2026-09-12 10:05 (above), not reproducible alone, in the repo or in the rig.
* Nothing else. Every other red I met this round was mine or the stamp class.

### STAMP-DEPENDENT REDS -- SIXTEEN, expected, not mine to close

The eleven listed earlier, plus
`tools/test_pointer_sweep.py::test_the_root_files_the_sweep_skips_are_installed_and_would_be_noisy`
(3 parametrisations) and
`tools/test_reference_skills.py::test_a_reference_skill_reaches_every_preset_and_not_only_team`
(2 parametrisations). All of them install from a staging and meet
"`does not hash to the content: in its own VERSION`". `python tools/bump_kit_version.py` is
forbidden in this item; one bump in the merge clears all sixteen.

### Finishing runs

* `python -m ruff check team-kits/ tools/` -> **All checks passed**
* `python tools/validate.py` -> **3 failures, all "VERSION not bumped"** (dev/office/research).
  The research lead-package size failure my first constitution cut produced is GONE: the
  constitution is byte-identical with HEAD.
* mirror after every hook change: `pytest tools/test_hooks.py -k "identical or mirror or
  shared_kit"` -> 4 passed
* the reading suites, each as a selection, are named in the rows above with their durations.
* NO stamp, NO full run, NO commit, NO push, NO mint.

Last clock reading of this protocol: **2026-09-12 12:07**.

### Closing run, 2026-09-12 12:09

All 23 naming nodes of this round in ONE selection: **23 passed, 46 s**. That is the line a
verifier re-runs first; each of them was measured RED beforehand in the pristine rig (or, for
`BUG-0162`, in the mutant tree with the pattern-free fourth exemption planted), and the rows above
carry the before/after per hole.

## B2 -- continuation (2026-09-12, from 12:10)

Same item, same working tree, same rig
(`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0142/rig`, pristine, no `.git`). B's rows above are
untouched. My list is B's "NOT REACHED" 23 plus `BUG-0056` and seam S3.

I read B's protocol WHOLE (413 lines) rather than from its last section -- the reading discipline
asks for that to be said, and the cost is visible here: the 21 closed rows carry the rig's shape,
the mirror hashes and the five self-introduced defects, and the COUNTS block alone does not.

### Plan, and the way it was REJECTED

The rejected way: take the 23 in the order B listed them. It loses on a measurement B already
took -- three of those rows are not defects any more (the item is stale, the code moved), and two
others name a fix location that is a user DECISION and not a line of code. Ordering by "is the fix
a line in this repository, and is its host file in my scope" puts the buildable ones first and
makes the unbuildable ones a written measurement instead of a row that ran out of clock. What it
does NOT cover: a row whose staleness is only visible after the build starts -- `BUG-0222` below is
exactly that case, and it cost the first 40 minutes of this continuation.

### 2026-09-12 12:17 -- seam S3 / `BUG-0265`: the installer records what it places

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H183 / BUG-0265 (INSTALLER HALF) | DESIGN | `kernel.report.installed_kit_paths` could only exclude the DIRECTORIES a kit fills (`INSTALLER_SCRIPT_DIRS = ("scripts", "tools")`), because nothing recorded WHICH files in them are the kit's -- so a project's own script there was unswept and no finding said so | `scaffold_team.sh` + `scaffold_team.ps1`: `shipped_list`/`$shippedList` collected at the TOP of the repo-template walk (one place, not one per branch -- the kit-owned branch returns), written as `.claude/kit_repo_files.json` by the interpreter, and added to `RESTORABLE`/`$restorable` and to both symlink preflights | pristine rig: **1 failed** ("sh installed no .claude/kit_repo_files.json", 29 s); repo **1 passed** (38 s) | `tools/test_hooks.py::test_the_installer_records_which_files_it_places_outside_the_hook_bundle` | that node, 38 s | EVD-0380 |

**The defect my first cut introduced, caught by the real twin and not by a test.** The JSON writer
was a `python -c` source carrying double quotes and a `\n` escape. PowerShell strips double quotes
and mangles backslashes when it hands a string to a native executable, so `python` received
`open(sys.argv[1], w, encoding=utf-8, newline=\n)` and died on a SyntaxError -- **and the scaffold
still exited 0**, because a failing native call does not stop a PowerShell script. Measured on the
real `.ps1` run (`s3/run3.log`); repaired by writing one source that carries neither a double quote
nor a backslash (`chr(10)`), identical in both twins, plus a `$LASTEXITCODE` check. Measured after:
the two manifests are byte-identical (`cmp`, 19 entries, office-team).

**What this does NOT close, and it is AC-1:** the sweep still reads the two directory names. The
reader is `team-kits/kernel/report.py`, stream A's file. Exact patch under "Seam handoffs (B2)".
`BUG-0265` is therefore NOT in my verification batch lines.

**A second measurement worth the line:** every test that really runs a scaffold was red for the
stamp reason (B's list of 16). `_stamp_staging` in `tools/test_hooks.py` re-stamps the COPIED
staging with `kernel.hashing.kit_hash` before the run, so this test measures the installer and not
whether somebody has run `tools/bump_kit_version.py`. It is used by the new test only; retrofitting
B's 16 belongs to the round that stamps.

### 2026-09-12 12:33 -- `BUG-0222` / H139: the item was HALF STALE, and the other half is built

**Measured before building anything:** C1/C2/C3 are already in `browser_smoke`, in dev AND research
byte-identically, and `tools/test_hooks.py::test_the_built_app_is_judged_on_c1_c2_c3_and_each_is_red_on_its_own_violation`
holds them. The module docstring even names H139 as closed by it. So only B3 (colour literals in
the application code) was open.

**The way I REJECTED, and it was my first cut of this row:** add B3 to `design_standards`, i.e. to
the RENDERED page, reusing `facts["colour_literals"]` which that probe already computes. It was
written, mirrored, and then reverted -- `tools/test_hooks.py::test_the_build_half_leaves_out_the_two_rules_a_build_cannot_answer`
pins the opposite as a deliberate decision with a stated reason: a build legitimately serves
third-party CSS nobody wrote as tokens. Reverted to byte-identical with HEAD in both kits
(`1a7077452cf4`) before the second cut. The mirror probe also created an office-team copy of a
dev/research-only file on the way (`mirror.py` writes into all three kits where the directory
exists); removed, `git status` clean for that path.

The second cut takes the objection seriously instead of overruling it: the SUBJECT is the
stylesheets the project WROTE (`kit_checks._frontend_sources`, which already skips `dist/`,
`node_modules/`, `vendor/`, `third_party/` and minified files), one blank page per sheet, judged by
the same browser probe -- so no third-party CSS is ever the subject and the definition of "a colour
literal" stays the CSS parser's rather than a table of notations.

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H139 / BUG-0222 | DESIGN | the B3 half of FR-0077 was judged on the frozen design revision only; a build that stopped referencing its tokens was caught by nothing | `kit_browser_checks.py` (dev + research, mirrored `9ec41b20adde`): `B3`, `_own_stylesheets` (the walker `kit_checks` owns), `own_stylesheet_literals`, wired into the open browser of `browser_smoke` and reported in THREE states -- fail, ok, and "no subject" for a project whose colours never reach a stylesheet of its own | rig with the FIX copied in and the judging call removed (mutation of the fix, not absence of it): **1 failed**, B3 reported `ok` on a sheet carrying `#dddddd`; repo **2 passed** (23 s) | `tools/test_hooks.py::test_a_colour_literal_in_the_projects_own_stylesheet_is_a_build_finding` | `-k "browser or built_app or build_half or projects_own_stylesheet or frontend"` -> 16 passed, 61 s | EVD-0379 |

`test_the_build_half_leaves_out_the_two_rules_a_build_cannot_answer` is renamed
(`..._leaves_out_the_rules_the_served_document_cannot_answer`) and gained the B3 verdict: with no
stylesheet of the project's own, B3 must WARN and must not pass. The old name claimed a rule was
left out that is now asked of a different subject.

### 2026-09-12 12:38 -- `BUG-0196` / H112: a run that gave up is not a run

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H112 / BUG-0196 | DESIGN | the run record is derived from the event log, and `last_run` read only the STOP -- so a subagent that hit `gate_subagent_output`'s give-up branch silenced the weekly reminder for a report nobody received (H112's own "unsafe direction") | `_routine.py` (all three kits, mirrored `ee4cde63ee26`): `GAVE_UP_EVENT`, `_role_of` (ONE reader for both record kinds -- the give-up reason opens with the agent type), and a `last_run` that pairs stop and give-up by POSITION, not by time: the two hooks sit in one `SubagentStop` matcher group, so which of them lands first is the provider's business. The module docstring's claim that a give-up counts as a run is replaced by the pointer to the test | rig with the FIX copied in and the give-up branch removed (a mutation OF the fix): the stop was read as a run at 12:38:18 while the give-up record stood one line below it; repo 3 passed | `tools/test_routine_feed.py::test_a_run_that_gave_up_on_its_output_contract_is_not_a_run` | `tools/test_routine_feed.py` whole: 32 passed, 7.6 s | EVD-0397 (supersedes EVD-0387, whose run command named a `-k` selection and no node id) |

Both shipped hooks run as PROCESSES in that test, so a rename of either record turns it red instead
of making the feed blind.

### 2026-09-12 12:47 -- `BUG-0208` / H124: whose day a deadline is due on

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H124 / BUG-0208 | DESIGN | `_duties` read `datetime.date.today()`, so the register's dates belonged to whichever machine ran the session and no field of the kit declared the business's own clock | `business_profile.yaml` gains `business.timezone` with its reason; `_duties.business_today` answers in THREE states -- no declaration to this machine's zone, an IANA name to that zone's date, and a name this machine cannot resolve to the machine's date PLUS a line that reaches the briefing. `register` / `briefing` read the clock ONCE and hand it down | rig with the fix copied in and the declared zone read-and-dropped: two projects 25 hours apart (Pacific/Kiritimati UTC+14, Pacific/Niue UTC-11) came back with the same day; repo 38 passed | `tools/test_office_duties.py::test_the_register_reads_the_business_time_zone_and_names_one_it_cannot_resolve` | `tools/test_office_duties.py` whole: 38 passed, 6.6 s | EVD-0398 (supersedes EVD-0390, same reason) |

**What stays open, now written in the code rather than in an item:** the register is computed once,
at SessionStart, so a session running past midnight keeps its answer. There is no second occasion to
read a clock at; that half of H124 is a property of the event and not of this reader.

### 2026-09-12 12:55 -- `BUG-0202` / H118: the dunning term this business agreed

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H118 / BUG-0202 | DESIGN | the finance page dunned by the legal default as a constant in the generator and presented it as this business's rule; `receivables.payment_terms_days` had meanwhile arrived in the profile and nothing read it -- the constant's own comment still claimed the field did not exist, a protection claim that had rotted | `tools/finance_dashboard.py`: `payment_term_days(profile)` returns the term AND the sentence that says whose it is, carried on `data["payment_term"]` and read at all four use sites (the page script's `TERM_DAYS`, the filter label, the summary line, the footnote) | rig: the page of a project declaring 14 days had no `var TERM_DAYS = 14;` -- "the page script still counts with the legal default"; repo 55 passed | `tools/test_finance_dashboard.py::test_the_page_dunning_term_is_the_one_this_business_agreed` | `tools/test_finance_dashboard.py` whole: 55 passed, 51 s | EVD-0399 |

The second node is the fail-closed half
(`::test_a_payment_term_that_is_not_a_positive_number_of_days_is_not_a_term`): `null` -- what the
template ships -- an empty string, a word, a zero, a negative and a list all mean "not declared".
**What is NOT closed** is the other half of H118, and it is a property of a static page: the age is
computed in the BROWSER from the reader's clock, because the page is a pure function of the ledger
and deliberately carries no generation timestamp. The page says so itself, in the same sentence that
now names the term's source.

## REWORK -- the verifier's round-1 findings B1..B4 (2026-09-12 13:06)

### B1 / `BUG-0289` -- a here-document the shell receives through a PIPE

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H205 / BUG-0289 (rework) | DESIGN | `_fed_to_a_command_parser` read only the text in FRONT of the opener, where the program name stands for a direct `bash <<EOF`. A here-document is the STANDARD INPUT of its stage, and a pipeline hands that input on | `_compat.py`: the subject is the whole PIPELINE -- left of the opener to the last separator (a pipe ends it there, because a stage's own name stands in front of it), right of the opener to the first `;`, `&`, `\|\|` or line break (a pipe does NOT end it). `_SOURCE_NAMES` adds `source` and a dot that stands as a WORD. The END of the opener is handed in, so a delimiter spelled `sh` is not a shell | `ws_probe.py`, real gate processes: `cat` heredoc piped to `bash`, the same through `tee`, `. /dev/stdin` and `source /dev/stdin` were **rig rc 0 -> repo rc 2**; a heredoc followed by `;` and a `./build.sh` heredoc stay rc 0 in both | `tools/test_hooks.py::test_a_heredoc_body_handed_to_a_shell_is_judged_as_a_command` | below | EVD-0393 (**supersedes EVD-0339**) |

The office ledger gate is repaired by the same reader, and the verifier's own line is the arbiter: a
`cat` heredoc piped to `bash` carrying `sed -i` on the ledger plus a commit was **rig rc 0 -> repo
rc 2**, likewise the `. /dev/stdin` spelling, while P4-12's commit message and a `cat` prose body
stay rc 0 in both (`ledger_probe.py`, `cases-ledger-b3.json`). Two rows added to
`tools/test_hooks_v2.py::test_a_heredoc_body_an_interpreter_executes_is_not_prose_here`.

### B2 / `BUG-0288` -- process substitution

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H204 / BUG-0288 (rework) | ENUM | `_SUBSTITUTIONS_BY_SHELL` carried the value-returning openers only, while `gate_ledger_valid._SUBSTITUTION_OPEN_RX` one file away already read the whole class | `gate_write_scope.py`: the two process-substitution openers in the Bash entry, with the measurement beside them | `cat` with a process substitution copying into `.claude/hooks/` and one writing an evidence item were **rig rc 0 -> repo rc 2**; an ordinary `echo` substitution stays rc 0 in both | `tools/test_hooks.py::test_a_command_a_substitution_introduces_is_judged_as_a_command` | below | EVD-0394 (**supersedes EVD-0338**) |

### B3 / `BUG-0186` -- the page the role reads FIRST

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H94 / BUG-0186 (rework) | INSTR | the withdrawn sentence ("stage the rendered files ... and report that gap") stood in `research-team/agents/report-writer.md`, which is INJECTED at every spawn, while the correction lived in the SKILL -- registered, not injected, as that same file says of itself | the role file names `freeze-report` as the only route into `reports/`; the contract test reads BOTH pages and refuses both withdrawn phrasings | rig with the SKILL fixed and the role file pristine: **1 failed**, naming `agents/report-writer.md`; repo 36 passed | `tools/test_role_contracts.py::test_the_report_writer_is_told_the_command_that_files_its_render` | `tools/test_role_contracts.py` whole: 36 passed, 4.3 s | EVD-0395 |

`python tools/pin_constitution_sections.py` -> **all pins current** (the role file is not a pinned
section; the one section B handed over is current too), and `python tools/validate.py` reports only
the three expected "VERSION not bumped".

### B4 / `BUG-0107` -- one of TWO borrowed modules

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H15 / BUG-0107 (rework) | DESIGN | the declaration covered `gate_write_scope` only; the workshop also reaches `_compat._MASK_RX`, and the tripwire filtered the harness's attribute reads on the receiver NAME `module`, so the second module was invisible to it | `_compat.py` declares its own `HARNESS_BORROWS`; the test derives BOTH ends -- which kit modules the workshop loads, from the `_from_kit` literals in `_harness.py`, and which receivers hold one, from the file itself (a name it neither imports nor owns: `os` is imported, `self` is the instance, `str` is a builtin) | rig with BOTH fixes in and `_MASK_RX` renamed in all three kits: **1 failed**, `assert not ['_MASK_RX']`; repo 1 passed | `tools/test_hooks.py::test_the_harness_borrows_only_what_this_kit_declares` | that node, 4.3 s | EVD-0396 (**supersedes EVD-0340**) |

### Runs behind B1 / B2 / B4

* `pytest tools/test_hooks.py -k "write_scope or heredoc or substitution or redirect or pipeline or read_only or prose or verb or borrow or directory"` -> 130 passed, **20 failed, every one of them a `gate_git` node**, 168 s. FOREIGN, and measured rather than assumed -- the bisection is below.
* `pytest tools/test_hooks_v2.py -k "write_scope or heredoc or quoted_program or prose or directory or pushd or walk or compat"` -> **221 passed**, 120 s.
* `pytest tools/test_hooks.py -k "heredoc or substitution or borrow or ledger or vouched"` -> 45 passed, 18 s.
* mirror after every hook change: `_compat.py` `0e2ec6391da1`, `gate_write_scope.py` `deadc12553ef`, `_routine.py` `ee4cde63ee26` -- all three kits equal (sha256 head, binary read).

### Foreign reds (B2), with the isolation that attributes them

20 nodes of `tools/test_hooks.py`, all `gate_git`:
`test_gate_git_reads_a_quoted_verb_as_the_verb_it_is` (5 cases),
`test_gate_git_reads_a_redirection_as_shell_syntax` (8),
`test_gate_git_is_not_switched_off_by_what_stands_between_git_and_its_verb` (6),
`test_a_line_that_also_merges_keeps_the_delivery_demand` (1 case).

BISECTED in a tree of its own (`_round-scratch/TSK-0142/isolate`): the pristine kits plus this
repository's current `tools/`, one layer swapped in at a time, measured with
`-k gate_git_reads_a_quoted_verb`:

| what was swapped in | result |
|---|---|
| nothing (pristine kits + current tools) | 5 passed |
| + this round's `_compat.py` and `gate_write_scope.py` | 5 passed |
| + this round's `gate_git.py` | 5 passed |
| + the current `team-kits/kernel/` | **5 failed** |

So the cause is stream A's in-progress kernel and not this stream's files. Left alone, as the item
prescribes.

### 2026-09-12 13:14 -- `BUG-0183` / H91: the plan, and now the plate beside it

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H91 / BUG-0183 | DESIGN | `--tree` renders `path_template`s -- the tree IS the plan, which is what the user steered for -- so a folder that really exists under `archive/` and that no rule covers appeared nowhere in the picture the kit presents as the visible truth | `scripts/filing_plan.py`: `unplanned_directories` beside `tree_lines` (never inside it -- `process_doc.py` renders the Verfahrensdokumentation from that function and that document describes the PLAN). A folder is unplanned when it is deeper than every template that matches it, or matches none; a `<placeholder>` segment stands for any name, as a property and not a vocabulary of spellings; the walk starts at the plan's own roots and is bounded | pristine rig: the unplanned folder was absent from the output (`assert 'archive/privat' in ['archive']`); repo 11 passed | `tools/test_hooks.py::test_a_folder_the_archive_really_has_and_no_rule_describes_is_named` | `-k "filing_plan or tree or aktenplan"` -> 11 passed, 19 s | EVD-0400 |

The second node is the other direction (`::test_an_archive_that_matches_its_plan_is_reported_as_nothing`):
a tidy project must read as tidy, or the new paragraph is noise and a project switches it off.
**Not closed, and it is the item's own sentence:** the comparison in the other direction -- a rule
whose folder does not exist yet -- stays the `project-auditor`'s check.

### 2026-09-12 13:21 -- `BUG-0286` / H202: a patch body is a list of writes

The re-measurement first, because most of the item is no longer true. The pipe and substitution
shapes H22/H202 names are ALREADY refused on this tree (real gate processes, `ws_probe.py`):

| line | rc |
|---|---|
| `echo .claude/hooks/g.py \| xargs -I{} cp evil.py {}` | 2 |
| `grep -rl needle project_memory/tasks \| xargs rm -f` | 2 |
| `find project_memory -name '*.yaml' \| xargs sed -i s/a/b/` | 2 |
| `ls project_memory/tasks/active \| while read f ; do cp evil.py …$f ; done` | 2 |
| `cp evil.py $(echo .claude/hooks/g.py)` | 2 |
| `F=.claude/hooks/g.py ; cp evil.py $F` | 2 |

What was still open is the PATCH half, and it was open inside a single command line:

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H202 / BUG-0286 | DESIGN | `git apply <<'EOF'` with a diff naming `.claude/hooks/gate_write_scope.py` was **rc 0** at the write-scope gate -- the applier is a writing stage, but the paths it writes stood in the here-document body, and the body was removed as prose before the first reader. The enforcement layer rewriting itself inside one line | `_compat._PATCH_APPLIER_NAMES` joins the `_STDIN_PARSER_RX` membership, and the comment says what joins them: for a shell, for `eval`, for `.`/`source` and for a patch applier alike the body is not DATA the program receives, it is what the program DOES | rig with everything of this round in and the patch appliers dropped from the membership: **rc 0** again; repo rc 2 for `git apply`, `patch -p1` and `git am`, and for the canonical-state direction | `tools/test_hooks.py::test_a_patch_body_a_line_carries_names_the_paths_that_line_writes` | `tools/test_hooks_v2.py -k "heredoc or prose or ledger or vouched or compat"` -> 801 passed, 132 s | EVD-0403 |

**What stays open, measured and NOT claimed closed:** a patch that lies in a FILE
(`git apply changes.diff`, `patch -p1 < changes.diff`) is rc 0. The paths are in no word of the
line, and this gate decides BEFORE the line runs. Closing it means the gate READING that file, and
that is a decision with two edges I did not take alone at the end of a round: a filesystem read in
the decision path is what the `H61` measurement warns about (one question about a path on an
unroutable host cost 42.1 s), and refusing an unreadable patch is an over-refusal on an everyday
developer operation in three kits. It is in "Seam handoffs (B2)" as a decision, with both options.

## S2 (`BUG-0192`/H108) -- the other half of A's strict parser, and a correction to my own report

A's half is IN this tree: `evidence` now REQUIRES `--run-command` and `--run-scope`. Measured
consequence in my own suites, and it is the correction: the **20 `gate_git` reds I recorded as
FOREIGN above were not foreign**. The bisection was right about the cause (the current kernel) and
wrong about the owner -- the failing call is `tools/test_hooks.py::capture_evidence`, a fixture in
MY file, recording an Evidence the shipped command can no longer record. Six call sites in my scope
now name both arguments (`tools/test_hooks.py` five, `tools/test_e2e.py` one).

Re-measured after that change: `pytest tools/test_hooks.py -k "write_scope or heredoc or
substitution or redirect or pipeline or read_only or prose or verb or borrow or directory"` ->
**150 passed, 0 failed** (138 s), and `tools/test_e2e.py` -> 20 passed (30 s). The row above stays
in this protocol with its correction rather than being deleted: "foreign" was a claim, and it was
wrong.

## COUNTS -- 2026-09-12 13:27 (B2 continuation)

* **closed by B2: 6** -- `BUG-0183`/H91, `BUG-0196`/H112, `BUG-0202`/H118, `BUG-0208`/H124,
  `BUG-0222`/H139, `BUG-0286`/H202. Each with a red-first measurement (five of them a MUTATION of
  the fix rather than its absence), a naming node and an EVD through the kernel.
* **reworked from the verifier's round 1: 4** -- `BUG-0289`/H205 and `BUG-0288`/H204 (both
  blocking, both re-measured with the verifier's own attack lines), `BUG-0186`/H94, `BUG-0107`/H15.
* **half built, seam: 1** -- `BUG-0265`/H183: the installer writes the manifest (AC-2), the sweep
  that reads it is stream A's file (AC-1). NOT in my batch lines.
* **downgraded with a measurement: 0.** I opened no exception.
* **not reached: 18** -- `BUG-0240`/H158, `BUG-0153`/H61, `BUG-0143`/H51, `BUG-0169`/H77,
  `BUG-0151`/H59, `BUG-0260`/H178, `BUG-0212`/H129, `BUG-0164`/H72, `BUG-0197`/H113,
  `BUG-0167`/H75, `BUG-0203`/H119, `BUG-0248`/H166, `BUG-0223`/H140, `BUG-0174`/H82,
  `BUG-0191`/H107, `BUG-0147`/H55, `BUG-0180`/H88, `BUG-0056` -- wall clock plus the four rework
  rows, which took the middle of this continuation. NOT REACHED is a different sentence from
  "measured unclosable", and writing it as the latter is the claim this protocol exists to avoid.
  What I measured about three of them before leaving them is below, because a measurement that is
  not written down has to be taken again.

### What was measured about three of the not-reached rows

* **`BUG-0153`/H61 is a SEAM, not a build.** The harness's construction is fail-closed on a
  registration that states no `timeout`. Measured over the shipped registrations:
  **dev 1 of 31 entries carry one, office 0 of 30, research 1 of 28.** A `Deadline` of that shape
  in the kits would therefore refuse essentially every hook call in every installed project, and
  the file that would have to change first -- `team-kits/*/settings/settings.json` -- is in this
  item's `forbidden_scope`. The patch is in "Seam handoffs (B2)".
* **`BUG-0222`/H139 was half stale**, and the half that was built is written above.
* **`BUG-0202`/H118's own item text** ("`business_profile.yaml` carries no payment term, measured
  2026-09-02") was stale too: the field arrived afterwards and nothing read it. Two items in one
  round whose mechanism had moved is worth the lead's attention more than either row is.

### Verification batch lines (B2) -- built against a store copy first, 0 refused

B's three lines stay B's and are re-measured as still accepted now that B1/B2 are green
(`batch_dry_run.py`, 3 lines, 0 refused). MY ids are one further line:

    python scripts/harness.py request-approval verification --batch BUG-0183 BUG-0196 BUG-0202 BUG-0208 BUG-0222 BUG-0286

`BUG-0265` is deliberately NOT in it: only AC-2 is built here. `BUG-0288`, `BUG-0289`, `BUG-0186`
and `BUG-0107` stay in B's lines 1 and 2 -- they are the same ids, reworked, and an id belongs to
exactly one line.

### Seam handoffs (B2)

1. **`BUG-0265`/H183, the kernel half** -- the installer now writes
   `.claude/kit_repo_files.json` (`{"kit": …, "repo_files": [repo-relative paths]}`, LF, no BOM,
   byte-identical from both twins). For stream A, in
   `team-kits/kernel/report.py::installed_kit_paths`, where `INSTALLER_SCRIPT_DIRS` is unioned in:

        shipped = os.path.join(repo_root, ".claude", "kit_repo_files.json")
        try:
            with open(ext_path(shipped), encoding="utf-8-sig") as handle:
                named = {str(one).replace("\\", "/").strip("/")
                         for one in (json.load(handle).get("repo_files") or [])}
        except Exception:   # noqa: BLE001 -- "A MISSING READER IS NOT SILENCE", as above
            named = set()
        # A project installed BEFORE the installer wrote this record has none, and dropping the
        # directories there would un-exclude every kit script at once.
        prefixes |= named or set(INSTALLER_SCRIPT_DIRS)

   The two-ended tripwire on the enumeration stays; it then guards the pre-manifest fallback.
2. **`BUG-0153`/H61** -- a kit-side `Deadline` is ONE patch across two owners, and the second half
   is first: **dev 1 of 31 hook registrations carry a `timeout`, office 0 of 30, research 1 of 28**
   (measured over the shipped `settings/settings.json`). A fail-closed reader of that field refuses
   every call until they carry one. So: (a) give every entry in `team-kits/*/settings/settings.json`
   an explicit `timeout` -- forbidden to this item, and the owner of that file decides the numbers;
   (b) then `_compat` can carry the harness's construction (`_harness.Deadline` +
   `_the_budget_is_spent` are the model, and `HOOK_DEADLINE_SECONDS` is already the kits' own
   budget). Applying (b) alone shuts every kit hook.
3. **`BUG-0286`/H202, the patch FILE** -- a DECISION, not a patch, and both options change gate
   behaviour for every project: (a) the gate READS the patch file named by an operand or an input
   redirect (bounded, inside the repo only) and judges the paths it names -- a filesystem read in
   the decision path, which is what the H61 measurement warns about; or (b) a patch-applying stage
   whose patch this gate cannot read is REFUSED -- fail-closed, and an over-refusal on an everyday
   operation. The heredoc half is closed either way.
4. **S2 (`BUG-0192`/H108)** -- done on my side: six call sites in `tools/test_hooks.py` and
   `tools/test_e2e.py` now name `--run-command` and `--run-scope`. What A's own note still lists as
   outstanding -- `README.md`, `team-kits/kernel/staging.py`, `team-kits/kernel/state.py` -- is
   outside my scope and unchanged.
5. **B's seam 3 (the constitution pin)** is DONE in this tree: `python tools/pin_constitution_sections.py`
   reports `3 kits, 12 files, 125 sections, all pins current`.

### EVDs of this continuation

`BUG-0222` EVD-0379, `BUG-0265` EVD-0380 (installer half only), `BUG-0196` **EVD-0397**
(supersedes EVD-0387), `BUG-0208` **EVD-0398** (supersedes EVD-0390), `BUG-0202` EVD-0399,
`BUG-0183` EVD-0400, `BUG-0286` EVD-0403; rework: `BUG-0289` EVD-0393 (supersedes EVD-0339),
`BUG-0288` EVD-0394 (supersedes EVD-0338), `BUG-0186` EVD-0395, `BUG-0107` EVD-0396 (supersedes
EVD-0340).

EVD-0387 and EVD-0390 were superseded for a reason worth keeping: their `run_command` named a `-k`
selection and a whole file, so `kernel.naming_tests.coverage_blocker` could not read a node out of
them and a verification batch over those ids would have been refused at request time. Every EVD of
this continuation was re-checked through that reader afterwards -- **9 ids, all "OK"**.

### Finishing runs (B2)

* `python -m ruff check .` -> **All checks passed**
* `python tools/validate.py` -> **3 failures, all "VERSION not bumped"** (dev/office/research) --
  the stamp class, and the stamp belongs to the merging item.
* `python tools/pin_constitution_sections.py` -> all pins current.
* mirror after every hook change (sha256 head, binary read, all three kits equal):
  `_compat.py` `250c1007125b`, `gate_write_scope.py` `deadc12553ef`, `_routine.py` `ee4cde63ee26`,
  `templates/repo/scripts/kit_browser_checks.py` dev=research `9ec41b20adde`;
  `pytest tools/test_hooks.py -k "identical or mirror or shared_kit"` -> 4 passed.
* the reading suites, each as a selection, are named in the rows above with their durations.
* NO stamp, NO full run, NO commit, NO push, NO mint.

Last clock reading of this continuation: **2026-09-12 13:27**.

### Closing run (B2), 2026-09-12 13:31

All 16 naming nodes of this continuation -- my six closures, the four rework rows and the
installer half -- in ONE node-id selection: **16 passed, 84 s**. That is the line a verifier
re-runs first; each of them was measured RED beforehand, five of them by MUTATING the fix in the
rig rather than by its absence, and the rows above carry the before/after per hole.

## B3 -- continuation (2026-09-12, from 13:32)

Same item, same working tree, same rig root
(`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0142/`). B's and B2's rows above are untouched.
My list is B2's "NOT REACHED" 18 (`BUG-0056` included) plus the lead's extra row F5.

I did NOT read B's or B2's sections whole: I opened the protocol at line 410 (the start of the
"B2 -- continuation" heading the order names) and read from there to the end, 356 lines. The 18 BUG
items I read whole, because each is the order itself for its row.

### Plan, and the way it was REJECTED

The rejected way: work the 18 in the order the item lists them and give every row the same
red-first build. It loses on a property of THIS list that B and B2's lists did not have -- ten of
the eighteen are `TRIAGED` "gemessene Grenzen" records whose `limits` field enumerates several
sub-limits at once, and most sub-limits name their own owner (kernel, a user decision, the shipped
old stock). Treating such a record as one buildable hole spends the clock on the halves that have
no line in this repository and leaves the halves that DO have one unbuilt. So the order is: per
item, split `limits` into its sub-limits, ask each one "is there a line for this in a file of my
`allowed_scope`", build those, and write the rest as a MEASURED downgrade or a seam with its owner
named. What the smaller way would not have covered: a sub-limit that is buildable while the record
around it is not -- `BUG-0180`(a3)/(a5) and `BUG-0167`'s BR-CO-14 are exactly that, and under the
rejected order both would have been "not reached" behind eight unbuildable rows.

### 13:36 -- F5 (the lead's extra row): already closed, measured

`tools/test_e2e.py` has exactly ONE `evidence` invocation (line 502), and it carries
`--run-command` / `--run-scope` (lines 505-506) -- B2's S2 fix. The finding named the line numbers
the fix now occupies. Measured rather than argued:
`pytest tools/test_e2e.py::test_e2e_the_merge_gate_opens_on_evidence_a_role_produced_and_shuts_on_a_fresh_fail`
-> **1 passed, 6.8 s**. `grep -n '"evidence"'` over `tools/test_e2e.py`, `test_hooks.py`,
`test_hooks_v2.py`, `test_office_package.py`: six sites, all six carry the pair. Nothing to change.

### 13:40 -- `BUG-0180` / H88 (a3 and a5): a manifest line neither twin owns

The item's `limits` field holds five sub-limits. Two of them have a line in a file of my scope
(`team-kits/scaffold_team.sh` / `.ps1`); the other three do not, and stand under "What stays open"
below.

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H88 (a3+a5) / BUG-0180 | DESIGN | a snapshot's `RESTORE_SET` was replayed over two classes of line neither installer owns. (a3) a word carrying its OWN ROOT: measured 2026-09-12 on the shipped twins, real installs -- the POSIX twin rc 1 through the OWNERSHIP refusal (a sentence about a foreign manifest, which is the wrong reason), the PowerShell twin rc 1 through an unhandled `GetFullPath` NotSupportedException with no sentence at all. (a5) a `KEPT_ONLY` path: **both twins rc 0**, and the user's `.claude/settings.local.json` came back holding `{"from": "the OLD snapshot"}` -- the backup pass copies those files, so "the snapshot holds a copy" was true of them and that is the half of the ownership rule that let them through | both twins: `manifest_line_is_a_repo_relative_name` / `Test-RepoRelativeName` (SEGMENTS are judged -- nothing empty, nothing `.`/`..`, no character either platform reads as a root or a separator -- rather than spellings enumerated), `in_kept_only` / `$keptOnly -contains`, and two refusals that name the property before the first line is acted on | (a) the shipped twins, `rollback_probe.py` in `b3/t1`: the two rows above, with the witness outside the project and the user's file as evidence. (b) a MUTATION of the fix (`b3/redfirst.py manifest_guards`, the two branches cut out of both twins in a .git-less tree): the naming node **1 failed, 60 s**, arbiter's line `sh/rooted refused for another reason: ... does not own and did not save a copy of`. Repo after: **1 passed, 126 s**; probe in `b3/t2`: all four runs rc 1, both witnesses intact | `tools/test_hooks.py::test_neither_twin_replays_a_manifest_line_that_is_not_the_installers_to_write` | that node (126 s); `tools/test_kitupdate.py -k "rollback or restore or snapshot or manifest"` -> 5 passed, **9 failed, all of them the STAMP class**, 208 s | EVD-0406 |

**The 9 are foreign and it is measured, not assumed:** the same selection in the mutation rig
(my fix cut out, everything else current) gives **the same 9 failures**, 317 s. Their arbiter's line
is the installer's own: `[write_kit_state] ...dev-team does not hash to the content: in its own
VERSION -- the kit source has been edited since it was stamped`. `tools/test_kitupdate.py` does not
re-stamp its staging, so every test in it that runs a real scaffold measures whether somebody has
run `tools/bump_kit_version.py`. That is B's list of 16, and the stamp belongs to the merging item.

**What stays open in H88, measured and not claimed closed:** (1) a snapshot written before
2026-09-01 carries no `RESTORE_SET` at all and is refused with its reason -- there is nothing to
derive a set from, so this is a property of the old snapshots and not of the reader; (2) the
residue list of the NEW kit survives its own withdrawal; (3) a foreign manifest built ONLY out of
`RESTORABLE` paths is still indistinguishable from ours -- the ownership rule cannot tell a line we
wrote from a line somebody copied out of our own list, and the record that could (a signature over
the manifest) is a decision about what a snapshot is, not a line in this file.

### 14:05 -- `BUG-0167` / H75: the tax total a document states TWICE

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H75 (BR-CO-14) / BUG-0167 | DESIGN | the money path checked BR-CO-15 (BT-112 = BT-109 + BT-110) and nothing else, so a head that is internally consistent while its own VAT breakdown says another number went through at **rc 0** -- the ledger would carry a tax amount the document itself denies. The `limits` field named it: "BR-CO-14 ungeprueft (in sich stimmiger, positions-widriger Kopf laeuft durch, gemessen)" | `einvoice_extract.py`: `BREAKDOWN_RULE`, `out["tax_breakdown"]` in BOTH syntax branches (CII `ApplicableTradeTax/CalculatedAmount`, UBL `TaxSubtotal/TaxAmount`, read through the same currency filter as every other amount) and `breakdown_failure`, which judges only what the document STATES -- no breakdown, or one it cannot read as figures, is an absent second statement and not a contradiction. Tolerance one cent PER STATED CATEGORY, because every BT-117 is itself rounded. `invoice_intake.py` asks it after BR-CO-15 and lists the rule in `norm_rules_checked` | the shipped extractor as its own process, a CII head 1000.00/190.00/1190.00 (BR-CO-15 holds) with a breakdown of 35.00 + 95.00: **rc 0**, `assert 0 == 2`. After: rc 2 naming both figures. The two silent directions are rows of the same test and were green before AND after | `tools/test_hooks.py::test_einvoice_a_tax_total_its_own_breakdown_contradicts_is_refused` | `tools/test_hooks.py -k "einvoice or invoice_intake or intake"` -> 15 passed, 15 s; `tools/test_office_package.py` -> 73 passed, 116 s | EVD-0407 |

**What stays open in H75, unchanged and not claimed:** the guard is arithmetic and not semantics
(three amounts from the WRONG document reconcile perfectly -- `FR-0065` carries that second
reading); UBL remains synthetically evidenced only; and the three named edge forms of the reader
each keep their safe direction.

## REWORK -- the verifier's round-2 findings C1 and C2 (2026-09-12, 14:10)

### C2 / `BUG-0289` (second rework): a FILE NAME is not the program it feeds

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H205 / BUG-0289 (rework 2) | DESIGN | `_fed_to_a_command_parser` asked the stdin-parser membership of the RAW span of the pipeline, where a word can be anything -- a file NAME included. So a redirection TARGET beginning with a member word made the here-document a command | `_compat._names_a_stdin_parser`: `_argument_scan` first (it drops a redirection together with its target -- this file's one reader of that fact), then the membership. All three kits, mirrored `971572a321b4` | the shipped gate as real processes (`ws_probe.py`, `cases-c2.json`): `cat > patch.diff <<'EOF'`, `cat > patch/notes.md <<'EOF'`, `cat > bash.md <<'EOF'` and `cat > source.txt <<'EOF'` were **rc 2 -> rc 0**; `patch -p1`, `patch.exe -p1`, `git apply`, `cat <<'EOF' \| bash` and `. /dev/stdin` heredocs stay **rc 2**, the two ordinary rows stay rc 0 | `tools/test_hooks.py::test_a_heredoc_body_handed_to_a_shell_is_judged_as_a_command` (promise rows + `nohup bash` / `timeout 5 bash`, so the fix cannot buy its silence by losing the runner case) | `tools/test_hooks_v2.py -k "heredoc or prose or ledger or vouched or compat"` -> 801 passed, 267 s; `tools/test_hooks.py -k "heredoc or substitution or borrow or ledger or vouched or patch_body"` -> 46 passed, 26 s | EVD-0408 (**supersedes EVD-0393**) |

**What it still over-refuses, measured and written into the code rather than claimed away:** an
ordinary OPERAND whose name begins with a member word (`cat patch.diff <<'EOF'`). Separating an
operand from a program needs the runner question -- in `nohup bash <<'EOF'` the operand IS what
executes -- and the direction that keeps those refusing is the one a gate has to take.

### C1 / `BUG-0286` -- the patch FILE: measured, and it stays OPEN

The verifier is right that "a decision with two options" is not one of the two states the house
rule allows. So here is the measurement instead of the option list, taken at the shipped gate as
real processes (`ws_probe.py`, `cases-c1.json`, dev kit):

| line | rc |
|---|---|
| `git apply changes.diff` | 0 |
| `patch -p1 < changes.diff` | 0 |
| `cat changes.diff \| git apply` | 0 |
| `git apply <(cat changes.diff)` | 0 |
| `git am 0001-fix.patch` | 0 |
| `git apply feature.patch` (ordinary) | 0 |
| `git apply --check feature.patch` (ordinary) | 0 |
| `patch src/app.py < fix.diff` (ordinary) | 0 |
| `git apply /tmp/x.diff` (ordinary) | 0 |
| `git apply <<'EOF'` naming `.claude/hooks/...` | **2** |
| `git apply <<'EOF'` naming `src/app.py` | 0 |

**THE SHAPE THE VERIFIER ASKED ME TO PRICE REFUSES ALL TEN OF THE FIRST ROWS.** "A stage whose
program word is a patch applier and whose patch source is not in the line's words" is TRUE of the
five attack lines and TRUE of the four ordinary ones, character for character: they differ only in
the CONTENT of a file this gate never opens. There is no narrower shape, because the only thing
that separates them is that content. So the cheap middle is not cheap -- it refuses every
patch application in every project of three kits, and that is not a residue I may impose without
the user. `BUG-0286` stays OPEN and is OUT of the batch lines (B2's corrected line is below).

### DEC question BUG-0286 (for the user, in plain German)

> Ein Patch (eine Datei mit Änderungen, die ein Befehl auf dein Projekt anwendet) kann auch die
> Schutzregeln selbst überschreiben. Steht der Patch direkt im Befehl, wird das heute erkannt und
> verweigert. Liegt er in einer DATEI, sieht die Schutzregel nur den Dateinamen und lässt ihn
> durch. Drei Wege, jeder mit seinem Preis — welchen willst du?
>
> 1. **Die Schutzregel liest die Patch-Datei** und urteilt über die Pfade darin. Preis: sie öffnet
>    beim Prüfen eine Datei; liegt die auf einem nicht erreichbaren Netzlaufwerk, kann das Prüfen
>    hängen (im Harness einmal mit 42,1 s gemessen), und der Haken wird dann abgewürgt, was der
>    Anbieter als „durchlassen" liest.
> 2. **Jede Anwendung eines Patches aus einer Datei wird verweigert.** Preis, gemessen: das trifft
>    `git apply feature.patch` genauso wie den Angriff — also jedes normale Einspielen eines
>    Patches in jedem Projekt aller drei Kits, weil beide Zeilen sich nur im Inhalt der Datei
>    unterscheiden.
> 3. **Es bleibt offen**, wie schon beim selbstgeschriebenen Skript (`H11`): die Regel schützt
>    gegen Irrtum, nicht gegen Absicht, und wer einen Patch von Hand anlegt und einspielt, weiß,
>    was er tut. Preis: der Weg bleibt offen und steht mit dieser Messung in der Löcherliste.

### 14:24 -- `BUG-0169` / H77: the rule reached the leads and stopped there

The item's `limits` names five sub-limits. Four of them are measurements about what NOTHING can
enforce (free text, the prose test's blindness to direction, `document_types` standing bare in a
German sentence, a changed card wording devaluing open questions) -- they are properties of free
text and of the approval mint, not lines in a file. The fifth names a role: "der Records-Clerk als
einzige Nicht-Lead-Rolle mit freiem `--reason` trägt die Regel nicht (kleine eigene Runde)". That
one is built.

**The item is partly stale, and the derivation is what showed it:** the records-clerk is NOT the
only such role. Read off the two running ends -- the kernel's typed manifest keys
(`LINE_MANIFEST_BUILDERS` minus `LINE_MANIFEST_RESOLVERS`) and the option spellings the shipped role
pages carry -- four non-lead pages type an approval value: `office-team/records-clerk` (`--reason`,
plus two paths) and `project-auditor` in **all three kits** (`--trigger`, `--cadence`, `--role`,
`--scope`).

| id | class | mechanism | change | red-first (arbiter) | naming node | suites | EVD |
|---|---|---|---|---|---|---|---|
| H77 (records-clerk half) / BUG-0169 | INSTR | the rule that says which language a value in an approval card carries stood on the LEAD surfaces only, while four other role pages tell their role to type one. The user signs the card, so this is the surface where their reading IS the protection | the rule's own text, contiguous and unretold, appended to `office-team/agents/records-clerk.md` and to `project-auditor.md` in all three kits, each with ONE role-specific sentence naming the values IT types (the clerk's `--reason` against its two paths; the auditor's `--trigger`/`--cadence` against `--role`/`--scope`). The lead's sentence about its SKILL is left out rather than copied: these roles have no such second surface, and a copied sentence would be a claim the kit does not build | rig with this round's tree and the block cut off the four pages (`b3/rf2_build.py`): **1 failed**, `Match(size=17)` -- the longest span the page shares with the leads' rule is 17 characters. Repo: 1 passed | `tools/test_role_contracts.py::test_every_role_that_types_an_approval_value_carries_the_language_rule` | `tools/test_role_contracts.py` whole -> 37 passed, 5.8 s; `tools/test_context_budget.py tools/test_kit_neutrality.py` -> 49 passed, 45 s (the pages grow, and the budget is what a page growing is measured against) | EVD-0409 |

The test holds TWO ends: a contiguous span of at least 300 characters shared with the rule the
leads carry (so a drifting copy is red instead of a second rule), and a section of the page's own
naming `request-approval`, the occasion and one of the values THAT role types.

## The rest of the list, measured -- 2026-09-12 14:45

One row each, and each says WHICH of the three states it is in: **downgraded with a measurement**
(the fix is not a line in this repository), **seam** (the line is here but outside this item's
`allowed_scope`), or **not reached** (buildable here, the clock ran out -- stated as itself and
never dressed up as one of the other two).

### `BUG-0153` / H61 -- SEAM, and the order asked for the row and the patch only

Measured over the shipped registrations (`team-kits/*/settings/settings.json`, counted by hook
entry): **dev 1 of 31 entries carry a `timeout`, office 0 of 30, research 1 of 28.** The
construction that closes the hole is fail-closed on a registration that states no deadline
(`.claude/hooks/_harness.Deadline` refuses the call), so carrying it into the kits TODAY would
refuse essentially every hook call in every installed project. The file that has to change first is
in this item's `forbidden_scope`. The patch, in the order it has to be applied:

1. **First, the registrations.** Every entry in `team-kits/*/settings/settings.json` gets an
   explicit `timeout`. The numbers are the owner's call; the measurement that bounds them is in the
   item: all observed gate runtimes <= 0.405 s and the largest own child bound outside
   `gate_pipeline` 20 s.
2. **Then, and only then, the reader.** `_compat` carries the harness's construction
   (`_harness.Deadline` + `_the_budget_is_spent` are the model, and `HOOK_DEADLINE_SECONDS` is
   already the kits' own budget). Applying (2) alone shuts every kit hook -- that is the measured
   reason for the order, not a preference.

### `BUG-0143` / H51 -- DOWNGRADED with a measurement

The one refusal per finding is not an oversight, it is one of TWO deliberate bounds against a loop,
and the code says so at the place it happens (`gate_dispatch`, the `Stop` arm): a refused stop is
answered by the provider with CONTINUING, and the condition that caused it outlives the refusal --
so a gate that refuses every time builds an endless loop between provider and hook.
`stop_hook_active` is the second bound. What is NOT lost is the finding: `_kernel.record_note` runs
for every finding on every stop, BEFORE either bound, so the audit line exists for each one.

> Ein Hook kann einen Abbruch nur EINMAL je Befund verweigern: der Anbieter beantwortet eine
> Verweigerung mit Weitermachen, und die Ursache besteht weiter -- eine zweite Verweigerung waere
> eine Endlosschleife zwischen Anbieter und Hook. Jeder weitere Fall steht im Pruefprotokoll.

### `BUG-0151` / H59 -- SEAM (kernel), with its measurement

The evidence drawer has two demanders and both sit behind places a small project never reaches
(`gate_git` at the MERGE; the `DONE -> VALIDATED` edge, which H58 measures as not walked). Making a
project OWE the QA step is a rule of the item automaton -- `team-kits/kernel/**`, this item's
`forbidden_scope` and stream A's file. What the kits already do is the half that is theirs: the
emptiness is SAID at every session start (`_kernel.unverified_delivery_briefing`, one text in three
kits). Owner: the kernel's automaton, `DONE -> VALIDATED`.

### `BUG-0260` / H178 -- the USER's decision, with the question written

`AC-1` of the item asks for a DEC recording the user's answer; neither branch is a line I may write
first. The measurement stands: `grep -rn narrow team-kits/kernel/` has no occurrence of the
classification, so `count_failed_run_locked` counts a FAILED run whatever QA called it, and the
climb is capped at the role's top -- the failure mode of an over-eager count is a more expensive
model on a retry, never a weaker one.

> Wenn die Qualitaetssicherung einen Fehlschlag als "rein mechanisch" einstuft, aendert das heute
> nichts: der naechste Versuch laeuft trotzdem eine Stufe teurer, weil der Zaehler nur zaehlt, dass
> ein Lauf gescheitert ist. Zwei Wege, und jeder kostet etwas:
>
> (a) Wir streichen die Einstufung aus den Rollentexten. Preis: der Bericht kann den Unterschied
> zwischen "der Code war falsch" und "ein Tippfehler im Befehl" dann gar nicht mehr ausdruecken --
> die Information geht ganz verloren, dafuer verspricht kein Text mehr etwas, das es nicht gibt.
>
> (b) Die Einstufung wird ein Feld auf dem Auftrag, das NUR die pruefende Rolle setzen darf.
> Preis: jede andere Rolle -- auch die, die den Fehlschlag verursacht hat -- braucht dafuer eine
> Rueckfrage bei der Pruefung, also einen Schritt mehr pro Fehlschlag; dafuer bleibt die
> Unterscheidung erhalten und ein billiger Wiederholungslauf wird moeglich.
>
> Welchen willst du?

### `BUG-0212` / H129 -- DOWNGRADED with a measurement

The WHAT-half of the destruction rule is a vocabulary of stems, and the reason is a property of the
event and not of the reader: a `PreToolUse` hook runs BEFORE the line and has no "afterwards" to
compare against, so whether a program removes a file is a fact about the PROGRAM. The bound is
built and measured at both ends: every stem is load-bearing at both ends
(`tools/test_hooks.py::test_every_destroying_stem_is_load_bearing_at_both_ends`), and the stems are
read over EVERY word of an invocation and by word stem, so every verb-noun form carries without its
own entry.

> Ob ein Programm eine Datei loescht, kann man der Befehlszeile nicht ansehen -- die Schutzregel
> laeuft vor dem Befehl und hat kein Nachher zum Vergleichen; sie erkennt die gaengigen
> Loeschbefehle und sagt selbst, was sie nicht sieht.

### `BUG-0164` / H72 -- DOWNGRADED with a measurement, and ONE question with its price

Of the four named limits, three are USER decisions about how strict the wall should be (the tidy-up
exception compares template + file name instead of place; overwriting an inbox document is free;
three named over-refusals), and the fourth is the procedural limit (blindness to foreign programs,
the lead as second reader). The item's own sentence is the measurement that matters and it still
holds: no chain reaches what was closed -- a foreign or swapped document under a doubly-read name.

CORRECTED IN TSK-0144 (verifier round 3, D1): the sentence below ASKED the user something while the
row was counted as one of the eight measurements and stood in no question list. Either it asks
properly -- situation, options, price per option, the form H178 and H166 carry -- or it stops
asking. It asks properly, because three of the four limits really are the user's call:

> **Lage.** Die Vier-Augen-Regel fuers Archiv haelt, was sie sagt: ein fremdes oder vertauschtes
> Dokument unter einem doppelt gelesenen Namen kommt nicht durch (gemessen). An drei Stellen greift
> sie bewusst nicht: beim Aufraeumen nach Vorlage (dort werden Vorlage und Dateiname verglichen,
> nicht der Ablageort), beim Ueberschreiben eines Dokuments im Posteingang, und an drei benannten
> Stellen, an denen sie sonst zu oft verweigern wuerde.
>
> (a) Es bleibt, wie es ist. Preis: nichts wird langsamer, und die drei Stellen bleiben offen --
> wer dort ein Dokument austauscht, wird nicht bemerkt.
>
> (b) Die Regel gilt auch dort. Preis: jedes Aufraeumen und jedes Ueberschreiben im Posteingang
> braucht dann eine zweite Bestaetigung, also einen Klick mehr an einer Stelle, die heute
> nebenbei laeuft -- und die drei benannten Ueber-Verweigerungen kommen zurueck.
>
> Es ist keine Frage nach einem Fehler im Code, sondern nach der Strenge, die du willst.

### `BUG-0197` / H113 -- SEAM (kernel), with its measurement

The register DERIVES what is owed; "this was done" is a RECORD, and a record about the business's
obligations is canonical state, whose only writer is the kernel. The direction is the safe one and
is measured: over-reporting, never silence -- an entry stands until its SOURCE changes. Owner: the
kernel (a done-record for a duty), not `hooks/_duties.py`.

### `BUG-0203` / H119 -- DOWNGRADED with a measurement (both halves)

(1) The generator running against an invalid ledger is bounded by the generator itself: it
validates, writes the finding verbatim into the page's banner, leaves the sums visible and calls
them not dependable (`test_an_invalid_ledger_is_named_on_the_page`). (2) A hand-written
`dashboards/finanzen.html` is indistinguishable from a generated one; the bound is that the next run
overwrites it atomically and the folder guide says so. `DEC-0056` decides the adversary here is the
ERROR and not intent, and neither half leaves a wrong number standing silently.

> Die Finanzseite wird immer neu erzeugt; wer sie von Hand aendert, verliert die Aenderung beim
> naechsten Lauf -- sie ist kein Dokument, sondern ein Ausdruck.

### `BUG-0248` / H166 -- the USER's decision (and the Steuerberatung's)

The intake REFUSES a mixed-rate document today and names the rates; nothing is booked silently. The
shape a mixed-rate document would be booked in changes the ledger's row identity
(`net x (1 + rate) = gross`), which the EUeR per-line sums and the section 19 threshold watch both
read. That is not a line I may choose.

> Eine Rechnung mit zwei Steuersaetzen (7 % und 19 % nebeneinander) kann das Kassenbuch heute nicht
> in EINER Zeile fuehren, also verweigert die Annahme und nennt die Saetze; gebucht wird von Hand.
> Wie so ein Beleg kuenftig aussehen soll -- mehrere Zeilen mit einer gemeinsamen Rechnungsnummer
> oder eine Zeile je Satz --, entscheidest du mit deiner Steuerberatung; beides aendert, wie die
> Auswertung summiert.

### `BUG-0223` / H140 -- NOT REACHED (buildable here)

Both halves have a line in a file of my scope (the dev kit's design checks). The first --
`[data-view]`-less markup with two `data-primary-action` being rc 0 -- is the one that is buildable:
judge the DOCUMENT as one view where the draft declares none. What stopped it is the clock, not a
measurement, and the existing test
`tools/test_design_conformance.py::test_a_draft_that_declares_no_view_says_so_instead_of_saying_nothing`
is the row the change would have to keep.

### `BUG-0174` / H82 -- DOWNGRADED with a measurement

Seven named limits, each shipped WITH the measured price of the alternative, and the core is
measured red on the running version: a staged draft does not reach the user without a render record
over exactly its bytes. What remains are questions about how much further a hook may reach into a
role's freedom -- user decisions, not defects.

> Die Regel "kein Entwurf zum Nutzer, den niemand angesehen hat" ist gebaut und gemessen; die Reste
> sind Fragen, wie weit ein Hook einer Rolle hineinreden darf.

### `BUG-0191` / H107 -- DOWNGRADED with a measurement

A design brief is a Decision item, and a Decision item is free text: nothing parses its halves and
no gate reads free text. Both ENDS are built instead -- the PM writes the halves separately and
sends a process rule into the `INV`, the designer hands one back as a finding if it reaches them.

> Ein Auftragstext laesst sich nicht maschinell in "Ziel" und "Vorschrift" zerlegen; dafuer sind
> beide Seiten angewiesen, eine Vorschrift im Brief zu melden statt sie auszufuehren.

### `BUG-0147` / H55 -- DOWNGRADED with a measurement, plus a seam

Two halves, and the first is a world limit: the OLD stock is the copies already installed in users'
projects, and nothing written here today changes a file that is already on somebody's disk. In a
RAISED project the bridge refuses every caller (measured rc 2). The second half -- the bridge this
repository still ships (`user/bridge/update_kit.py`, named by `install.sh` line 282 and `install.ps1`
line 309) -- is a line in this repository but OUTSIDE my `allowed_scope`, so it is in "Seam handoffs
(B3)".

> Alte Installationen tragen eine Update-Bruecke, die auf ein gesprochenes Ja statt einer
> protokollierten Freigabe laeuft; geheilt wird das erst mit dem Hochziehen auf das neue Kit, weil
> niemand eine Datei aendern kann, die laengst auf einem fremden Rechner liegt.

### `BUG-0056` -- the item's headline case does not exist; what exists is a different one

Measured in the running migration rather than argued: what the migration RECORDS as the source of an
imported record is `legacy_source`, and it is written from `entry["source"]`, which is a
STATE-RELATIVE path (`migrate.py`: the entry is built as `{"source": rel, ...}` from the walk under
the state root). The walk never leaves the state root, and the remedy for a file outside it prints
"COPY it -- the original stays where it is" into `staging/`. So a V1 file outside the state tree is
never a RECORDED one, and the item's `docs/old/product_requirements.yaml` is rc 0 because nothing
knows about it -- not because a gate ignores a record.

What IS recorded and IS writable is the DEPOSIT copy under `project_memory/staging/`: staging is
deliberately open (proposals are not state), and an imported record's `legacy_source` names exactly
such a copy. Closing that means the write-scope gate asking the migration's record -- a scan over
the item files in the decision path of EVERY write, which is the cost `H61` warns about. The item is
therefore **half stale and half a decision**, and it belongs in front of the lead with that
measurement rather than being closed or downgraded by me.

### `BUG-0240` / H158 -- NOT REACHED (buildable here), with the reading that shortens the next attempt

The occasion arm is buildable inside `hooks/_routine.py` (my scope), and the reader it needs already
exists in the kits: `_kernel.open_state` / `_kernel.kernel_module` give a hook the kernel's own
state, and `_kernel.unverified_delivery_briefing` is the shipped example of a briefing derived from
it. So an occasion ("a root item reached a terminal state after the last audit run") does not need a
new hook, a new registration or a new record. What stopped it is the clock.

### 14:48 -- the OTHER end of `BUG-0180`, and the gap in my own measurement

My first measurement of this row only showed the two REFUSALS. That a rollback over the manifest
the installer itself wrote still runs was left to
`tools/test_kitupdate.py::test_a_rollback_restores_the_previous_bundle_byte_for_byte` -- which is
red today for the STAMP reason and therefore measured nothing at all. A guard whose only
measurement is that it refuses is one nobody has watched allow. Taken by hand
(`b3/own_manifest_probe.py`): two real installs per twin, then `--rollback` over the snapshot's own
16-line `RESTORE_SET` -- **rc 0 in both twins**, `Rollback done`. The test's docstring now says the
inherited end is stamp-dependent and carries this measurement beside it.

### Correction to my own `BUG-0223` row, 14:36 -- it is a DOWNGRADE and not "not reached"

I wrote above that the `[data-view]`-less half is buildable. I then read the shipped renderer, and
that claim is wrong: `kit_design_render.py` already reports the case, as UNDECIDED with its reason
("a Phase-1 tile sheet legitimately has none; a per-view mockup has one per view"). Judging the
DOCUMENT as one view -- the change I had in mind -- would make every tile sheet red, because a tile
sheet carries one primary action per tile and no markup tells a tile sheet from a mockup. So the
silence is the correct answer for an undecidable subject, and the honest state of this row is
**downgraded with a measurement**, not "not reached". The correction stands here rather than being
edited into the row above, for the reason B2's "foreign" correction stands: the first version was a
claim, and it was wrong.

> Die Rangfolge-Regel ("eine Seite sagt genau EINE Sache, die der Nutzer hier tun soll") braucht
> eine ausgezeichnete Ansicht. Ein Entwurf, der keine auszeichnet, kann ein Kachelblatt sein, bei
> dem mehrere Hauptaktionen richtig sind -- deshalb sagt die Prüfung dort "nicht entscheidbar"
> statt zu urteilen, und sie druckt diesen Satz, damit niemand das Schweigen als Bestanden liest.

### Correction to my own `BUG-0240` row, 14:46 -- it is a SEAM, not "not reached"

I wrote above that the occasion arm is buildable here and that only the clock stopped it. I then
read the test the item's own `regression_tests` names first, and that is wrong in a way worth the
correction: `tools/test_review_procedure.py::test_no_occasion_makes_the_audit_run_due_and_that_is_the_seam`
PINS the current behaviour, and its docstring says so in as many words -- "THIS TEST IS WRITTEN TO
GO RED ... the day an occasion makes the run due, the two projects part company here, and the
honest-limit sentence in every kit's auditing skill and role definition is what has to be
corrected." That file is in this item's `forbidden_scope`.

So closing H158 is ONE change across two owners, and building only my half would leave a knowingly
red test in a file I may not touch -- which is the seam-damage this repository's constitution names
by measurement. The change, exactly, for whoever owns both:

1. **`hooks/_routine.py`** (mirrored, all three kits) gains the occasion arm beside the period:

       def delivery_occasions(root, since):
           """[(item id, when)] -- records that reached a TERMINAL state after `since`.

           THE OCCASION HALF OF FR-0084, as a definition and not a status list: a state is terminal
           when its own automaton has no way out of it (`backlog_types.AUTOMATA[<type>].terminals`),
           and the type comes from the file's own id. The walk stats first and parses only what
           changed after `since`, so an ordinary session start reads no file at all.
           """

   The reader it needs is already in the kits: `_kernel.kernel_module("backlog_types", root)` hands
   a hook the kernel's own vocabulary, the way `_kernel.unverified_delivery_briefing` hands it the
   report. `routine_duties` then reports the run as due when an occasion stands after the last run,
   whatever the period says, and NAMES the occasion in the duty.
   The failure direction to state in the docstring, because it is real: a fresh clone gives every
   file a new mtime, so every record reads as "just changed" once -- which makes the run due once,
   the nagging direction, and never silent.

2. **`tools/test_review_procedure.py::test_no_occasion_makes_the_audit_run_due_and_that_is_the_seam`**
   turns around: the `plain` and `delivered` projects must now DIFFER, and the test that pins the
   seam becomes the test that pins the occasion (the docstring says this is the intended
   transition).

3. **The honest-limit sentence** in every kit's auditing SKILL and `project-auditor` definition --
   the one that tells the role the run hangs on a period and not on an occasion -- is corrected in
   the same change, or the kits ship a text that is now false. That half IS in my scope; it is not
   written, because writing it while (1) and (2) are not applied would make the text the false one.

## COUNTS -- 2026-09-12 14:40 (B3 continuation)

* **closed by B3: 3** -- `BUG-0180`/H88 (the a3 and a5 sub-limits), `BUG-0167`/H75 (BR-CO-14),
  `BUG-0169`/H77 (the records-clerk sub-limit, and three auditor pages the derivation found).
  Each with a red-first measurement, a naming node and an EVD through the kernel.
* **reworked from the verifier's round 2: 1** -- `BUG-0289`/H205 (C2: a file name read as the
  program it feeds; four everyday lines were rc 2 through the shipped gate). EVD-0408 supersedes
  EVD-0393.
* **measured and left OPEN as the verifier asked: 1** -- `BUG-0286`/H202 (C1), with the price of
  the shape and the user's question written out. It is OUT of the batch lines.
* **stale finding, measured green: 1** -- the lead's F5 row.
* **downgraded with a measurement: 7** -- `BUG-0143`/H51, `BUG-0212`/H129, `BUG-0164`/H72,
  `BUG-0203`/H119, `BUG-0174`/H82, `BUG-0191`/H107, `BUG-0223`/H140. Each with the
  measurement and one plain-German sentence; none says "later".
* **`BUG-0147`/H55 -- SPLIT, and counted as both halves** (verifier round 3, D2; corrected in
  TSK-0144): a DOWNGRADE for the world limit (a copy already installed on somebody's disk cannot
  be changed from here, and in a raised project the bridge refuses every caller -- measured rc 2)
  PLUS a REPO LINE that was reparable and has been repaired -- `user/bridge/update_kit.py` ships
  from this repository, and its success output now SAYS that no approval covers the one lift it
  performs (`tools/test_kitupdate.py::test_a_stock_without_update_kit_is_lifted_by_the_bootstrap_and_told_about_it`
  reads that off the real stdout of a real lift). Counting it undivided read as "unclosable" for a
  line that was not.
* **`BUG-0164`/H72 also carries ONE question** (D1 above), so it stands in the measurements AND in
  the question list; the row says which half is which.
* **seams (the line exists but not in my scope): 4** -- `BUG-0153`/H61 (kit `settings.json` first,
  then the reader), `BUG-0151`/H59 (the kernel's `DONE -> VALIDATED` edge), `BUG-0197`/H113 (a
  done-record is canonical state).
* **the user's decision: 2** -- `BUG-0260`/H178, `BUG-0248`/H166, each with its question in plain
  German.
* **half stale, in front of the lead: 1** -- `BUG-0056`: the recorded V1 file outside the state
  tree does not exist (the migration's record is state-relative); what exists is the deposit copy
  under `staging/`, and closing that puts a state scan in the decision path of every write.
* **not reached: 0.**
* **seam by test ownership: 1** -- `BUG-0240`/H158: the code is mine, the test that PINS the opposite (`tools/test_review_procedure.py::test_no_occasion_makes_the_audit_run_due_and_that_is_the_seam`) is in my `forbidden_scope` and says of itself that it is written to go red on this change. The exact patch across the two owners is in the correction above.

18 + F5 = 19 rows, all of them answered.

### Verification batch lines (B3) -- built against a store copy first, 0 refused

Five lines, measured together (`batch_dry_run.py`, `batches-b3-all.txt`): **5 lines, refused 0**.
B's three are unchanged; B2's line is CORRECTED (`BUG-0286` removed, per C1); mine is the last.

    python scripts/harness.py request-approval verification --batch BUG-0030 BUG-0107 BUG-0149 BUG-0154 BUG-0156 BUG-0158 BUG-0159 BUG-0160 BUG-0162 BUG-0182
    python scripts/harness.py request-approval verification --batch BUG-0186 BUG-0201 BUG-0207 BUG-0250 BUG-0259 BUG-0262 BUG-0277 BUG-0285 BUG-0288 BUG-0289
    python scripts/harness.py request-approval verification --batch BUG-0294
    python scripts/harness.py request-approval verification --batch BUG-0183 BUG-0196 BUG-0202 BUG-0208 BUG-0222
    python scripts/harness.py request-approval verification --batch BUG-0180 BUG-0167 BUG-0169

### Seam handoffs (B3)

1. **`BUG-0153`/H61** -- the two-step patch, in the order it has to be applied, is the row above.
   Owner of step 1: whoever owns `team-kits/*/settings/settings.json` (forbidden here).
2. **`BUG-0147`/H55, the shipped bridge** -- `user/bridge/update_kit.py` is in this repository and
   outside my `allowed_scope`. What a fix there can reach is only NEW installs; the old stock on a
   user's disk is unreachable by construction.
3. **`BUG-0151`/H59** -- the kernel's `DONE -> VALIDATED` edge (H58) is the only thing that could
   make a solo project owe the QA step. `team-kits/kernel/**`, stream A.
4. **`BUG-0197`/H113** -- a "this duty is done" record is canonical state; the kernel is its only
   writer. `team-kits/kernel/**`.
5. **`BUG-0056`** -- the decision named in its row: the write-scope gate asking the migration's
   record means a scan over the item files in the decision path of every write.
6. **`BUG-0286`/H202** -- the DEC question above, for the user.

### Foreign reds (B3)

* `tools/test_kitupdate.py -k "rollback or restore or snapshot or manifest"`: **9 failed**, and the
  attribution is measured rather than assumed -- the same 9 fail in a rig with my change cut out
  (317 s). All nine are the STAMP class: the installer refuses a staging whose kit files do not
  hash to their own `VERSION`, and that file does not re-stamp its copy. B's list of 16, and the
  stamp belongs to the merging item.
* Nothing else. No red in any suite I ran was attributable to another stream's file.

### Finishing runs (B3)

* `python -m ruff check .` -> **All checks passed**
* `python tools/validate.py` -> **3 failures, all "VERSION not bumped"** -- the stamp class.
* `python tools/pin_constitution_sections.py` -> 3 kits, 12 files, 125 sections, all pins current.
* mirror after the hook change: `_compat.py` `971572a321b4`, equal in all three kits (sha256 head,
  binary read); `pytest tools/test_hooks.py -k "identical or mirror or shared_kit"` -> 4 passed,
  39 s.
* the reading suites are named in the rows with their durations. NO stamp, NO full run, NO commit,
  NO push, NO mint.

Last clock reading of this continuation: **2026-09-12 14:40**.

### Closing run (B3), 2026-09-12 14:52

All six nodes of this continuation -- the three closures, the C2 rework in both gates, and the
lead's F5 row -- in ONE node-id selection: **6 passed, 83 s**. That is the line a verifier re-runs
first; each was measured RED beforehand (two of them by MUTATING this round's own fix in a .git-less
rig, one of them at the shipped gate as real processes), and the rows above carry the before and
after per hole.

`python -m ruff check .` after the last edit -> All checks passed.

Last clock reading of this continuation: **2026-09-12 14:53**.
