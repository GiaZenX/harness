"""Generation 5 work orders: ONE per goal (DEC-0067), created through the kernel with argument lists
(shell quoting broke twice in generation 3). Seams named as `--seam-scope` fields (DEC-0070 rule 1,
DEC-0080 rule 1); the cut is MEASURED with check-scopes before spawn. Hole numbers are no longer
reserved in the item: the kernel allocates them (`capture BUG --hole`, generation 4). Tiers per
DEC-0077 (4) / DEC-0080 (8): implementers Fable 5.1 (G5-2 and G5-3 xhigh, G5-1 high), verifiers Opus
high -- spawn parameters, not item fields. Not idempotent -- run once; read the ids it prints."""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]

BASE = "b7f282e"
COMMON_FORBIDDEN = [
    "scaffold_team.*", "install.*", "init_project_memory.*", "user/**", ".claude/settings.json",
    ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py", "CLAUDE.md", "project_memory/**",
]
COMMON_SEAMS = [
    "tools/**", "docs/**", "team-kits/*/VERSION", "team-kits/kernel/cli.py",
    "team-kits/*/constitution/AGENTS.md", "team-kits/*/agents/*.md", "tools/lead_package_sizes.json",
    "docs/reviews/phase0-disposition.md", "README.md",
]
RULES = (
    "Per absorbed wish or bug its own red-first test measured in a copy outside the repo (restore the "
    "defect, see red, put it back) and its own acceptance line in the protocol; the verifier reports "
    "PER acceptance criterion of the goal. Every new property claim -- code comment, docstring, docs, "
    "hole item -- is MEASURED before handover. DEC-0080 (6): every new READER or tripwire this stream "
    "writes gets, before the report, a mutation in the direction its docstring denies (a reader that "
    "reads less than it claims was the repeated class of generation 4) -- the mutation and its red line "
    "stand in the protocol per reader. A named test must be able to fail. Holes: a measured gap is a "
    "BUG item captured through `PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory "
    "capture BUG --hole` (kernel-allocated number; `limits` duty; module prefix in citations) -- no "
    "hand numbers, no document entries. forbidden_scope project_memory/** EXCEPTS "
    "project_memory/staging/(this task id)/ and the kernel command lines this order names. Wherever "
    "the truth about a shell can be executed, a real shell is the arbiter. Only the READING suites run "
    "in the stream -- and DEC-0080 (2): a stream that changes a DISPATCH, LEASE or VALIDATOR rule runs "
    "every suite that READS that rule (grep the predicate's callers, list them in the protocol) -- "
    "the full suite belongs to the merge; gate 5 is live: a full-surface line is refused, the "
    "DELIVERY_RUN prefix is the merge's, never a stream's. HOST RULE: one pytest at a time, every run "
    "with a timeout, no CPU-saturating rig (four hard power-offs on 2026-09-04). Clock: every protocol "
    "time is read, never extrapolated (DEC-0080 (7))."
)
HANDOVER = (
    "Handover: worktree C:/Offline Repos/v2-testbed/_worktrees/g5-{name} (branch g5/{name} off "
    "feat/harness-v2 at " + BASE + "); ALL scratch only under C:/Offline Repos/v2-testbed/_round-scratch/"
    "(this task id)/; a red-first rig refuses to run outside its own directory and writes binary; "
    "verifier copies made WITHOUT the .git file of the worktree; patch = the worktree diff WITHOUT the "
    "VERSION hunks at C:/Offline Repos/v2-testbed/_round-scratch/(this task id)/stream-{name}.patch (a "
    "patch carrying VERSION hunks is a cut finding); protocol at project_memory/staging/(this task id)/"
    "stream-protocol.md with: seam table (received / expected at merge), per-criterion acceptance line + "
    "red-first tests, reader mutations, measured lines, what was deliberately not closed but named "
    "(as hole items), the one-line rejected alternative of the plan (FR-0084 shape, now a constitution "
    "duty), suites run (reading suites + the suites that read a changed rule), provisional VERSION "
    "stamp, wall-clock (read) and tokens for the (g) table. DEC-first proposals go to the lead as "
    "project_memory/staging/(this task id)/dec-*.json -- the user decides, the stream waits on that "
    "point and works on the rest. No commit, no push, no install to the global store."
)

STREAMS = {
    "ladders": dict(
        pr="PR-0010", type="implementation", acs=["AC-1", "AC-2", "AC-3", "AC-4", "AC-5", "AC-6", "AC-7"],
        allowed=[
            "team-kits/model_tiers.yaml", "team-kits/gen_provider_artifacts.py",
            "team-kits/kernel/dispatch.py", "team-kits/*/hooks/gate_dispatch.py",
            "team-kits/*/ladder.yaml", "team-kits/*/constitution/AGENTS.md", "team-kits/*/agents/*.md",
            "team-kits/*/templates/repo/.codex/**", "team-kits/*/settings/**",
            ".claude/agents/radar-watcher.md", ".claude/agents/codex-watcher.md", "radar/**",
            "team-kits/*/VERSION", "tools/**", "docs/**", "README.md",
        ],
        forbidden=COMMON_FORBIDDEN + [
            "team-kits/kernel/report.py", "team-kits/kernel/state.py", "team-kits/kernel/backlog_types.py",
            "team-kits/kernel/documents.py", "team-kits/kernel/filing.py", "team-kits/kernel/holes.py",
            "team-kits/*/skills/**", "team-kits/*/hooks/gate_*.py", "team-kits/*/hooks/guard_*.py",
            "team-kits/*/hooks/_*.py", "team-kits/office-team/templates/**",
            ".claude/agents/harness-*.md", ".claude/hooks/**",
        ],
        seams=COMMON_SEAMS + ["team-kits/*/settings/settings.json"],
        inputs=[
            "project_memory/product/active/PR-0010.yaml (AC-1..AC-7) and what it absorbed: FR-0088 (trigger + first codex report + ladder), BUG-0092 (stale price anchors, both providers); the decisions it builds: DEC-0076 (three rungs), DEC-0077 (two axes, escalation built, gen-5 tiers), DEC-0078 (per-kit ladder declarations, office ladder), DEC-0034 (rules 1-5 and the open thresholds), DEC-0047 (endpoints per kit), DEC-0074/DEC-0079 (the shape of a kit-delivery derivation in dispatch.py -- reuse that reading for the ladder declaration), FR-0047 (pin tests, silent downgrade visible)",
            "radar/2026-09-05-codex.md (Astra gpt-6-astra GA 2026-09-03, prices, the max-vs-ultra contradiction, the Interrupt event, the missing-pin 400), radar/2026-09-04-claude.md, radar/decided.md (seven codex-0905 entries pointing here), radar/README.md (the schedule claim without a mechanism)",
            "team-kits/model_tiers.yaml (aliases, tiers, MAINTENANCE header, price anchors, watch dates), team-kits/gen_provider_artifacts.py (provider_neutral_model, the .codex overlay, codex_matchers), team-kits/kernel/dispatch.py (create_lease, architect_step_owed, _the_kit_delivery_of_the_architect_step), team-kits/*/hooks/gate_dispatch.py, the role pins in team-kits/*/agents/*.md (measured 2026-09-05: PM dev/research fable, architects/reviewer/office-manager/office-developer lead, the rest worker, 25 high / 2 low), .claude/agents/radar-watcher.md and codex-watcher.md (last changed 2026-08-08, model sonnet)",
            "DEC-0080 (the generation-4 retrospective: rules 1-9), DEC-0063, DEC-0070; project_memory/staging/generation-4-streams.md (the measured watcher findings and the user's words on the ladders)",
        ],
        outputs=[
            "PR-0010 AC-1 (trigger, DEC-FIRST): a proposal dec-trigger.json to the lead with two measured alternatives (a lead session-start routine vs an OS-level weekly task running both watchers headless via the CLI) and what each survives (session end, host reboot, a missing session); after the user's answer the mechanism is built and measured once end to end (a run started by the mechanism writes a dated report into radar/), and a test refuses a watcher definition or README sentence that claims a schedule the repo does not build.",
            "PR-0010 AC-2: the next codex report is produced by the built trigger in the shipped shape; the Sol/Terra/Astra effort ceiling (max vs ultra) measured against the Codex CLI, not copied; findings triaged into radar/decided.md with items where a change follows.",
            "PR-0010 AC-3 (DEC-0076): model_tiers.yaml = exactly three rungs per provider (claude fable/opus/sonnet, codex astra/sol/terra with the measured ids), no `light` alias or haiku/luna row; gen_provider_artifacts refuses a light/haiku pin with a sentence naming DEC-0076; the .codex overlay and every constitution ladder sentence consistent; every pin resolves in a test; red-first.",
            "PR-0010 AC-4 (BUG-0092): price anchors of both providers reworded to the measured current prices, dead watch dates removed, a shipped test red on any past watch date in model_tiers.yaml (red-first with today's file), the MAINTENANCE header names the finding-to-item route.",
            "PR-0010 AC-5: the rollout line in the protocol (stamp -> global store install -> update-kit at the next session start) and what a project sees when its pinned model no longer exists.",
            "PR-0010 AC-6 (DEC-0077/DEC-0078, DEC-0034 rules 1-5): EVERY kit declares its OWN ladder in team-kits/<kit>/ladder.yaml (rungs, endpoints, effort pair, named exceptions -- dev/research high/xhigh climbing to fable, office medium/high with opus as the top for every role except office-developer and the sonnet-LOW filing floor); the dispatcher READS it at spawn (kernel create_lease + the kit dispatch path) and derives RUNG (role pin + kit endpoint) and EFFORT (default / large by the goal's class) from state; a kit without a declaration is refused at dispatch with a sentence; rule 2: an order that FAILED climbs one rung per failure with the threshold a config value carrying its DEC line and a default measured on a pilot; rules 1/3/4/5 as DEC-0034 states them; rung and effort written on the lease and shown in the session brief; measured as a PROCESS on a scaffolded pilot per kit; red-first per rule; the kernel carries no kit-name branch and no default ladder.",
            "PR-0010 AC-7: DEC-0034, DEC-0047, DEC-0076, DEC-0077, DEC-0078 cited by the code that implements them; the three constitutions' ladder paragraphs say what is BUILT; the model_tiers.yaml header no longer calls the mechanic an open work item; the harness roles' model pins (.claude/agents/harness-*.md, owned by G5-1) receive the sentence to write as a SEAM.",
            RULES,
            "Seams: team-kits/kernel/cli.py (G5-1 and G5-3 add commands too -- your block only); the three constitutions and team-kits/*/agents/*.md (G5-1 writes the comment-discipline duty and the CR rule, G5-3 the office correspondence role -- you write ONLY ladder sentences and model/effort pins, listed per file in the protocol); tools/lead_package_sizes.json and docs/reviews/phase0-disposition.md (every stream grows a lead package: record, do not overwrite); README.md (command surface); team-kits/*/settings/settings.json if the trigger registers a hook (G5-1/G5-3 do not touch settings). Reach seam (DEC-0080 (1)): the dispatcher change touches every kit -- measure all three pilots, and list every suite that reads create_lease / architect_step_owed / the ladder reader before handover (DEC-0080 (2)).",
            HANDOVER.format(name="ladders"),
        ],
    ),
    "stock": dict(
        pr="PR-0008", type="implementation", acs=["AC-1", "AC-2", "AC-3", "AC-4", "AC-5", "AC-6", "AC-7"],
        allowed=[
            "team-kits/kernel/report.py", "team-kits/kernel/state.py", "team-kits/kernel/backlog_types.py",
            "team-kits/kernel/cli.py", "team-kits/kernel/holes.py", "team-kits/*/constitution/AGENTS.md",
            "team-kits/*/agents/*.md", "team-kits/*/skills/project-manager/**",
            "team-kits/office-team/skills/office-manager/SKILL.md", "team-kits/*/skills/project-auditor/**",
            ".claude/agents/harness-lead.md", ".claude/agents/harness-implementer.md",
            ".claude/agents/harness-verifier.md", "team-kits/*/VERSION", "tools/**", "docs/**", "README.md",
        ],
        forbidden=COMMON_FORBIDDEN + [
            "team-kits/kernel/dispatch.py", "team-kits/kernel/documents.py", "team-kits/kernel/filing.py",
            "team-kits/kernel/approvals.py", "team-kits/model_tiers.yaml", "team-kits/gen_provider_artifacts.py",
            "team-kits/*/hooks/**", "team-kits/*/settings/**", "team-kits/*/templates/**",
            "team-kits/*/ladder.yaml", ".claude/agents/radar-watcher.md", ".claude/agents/codex-watcher.md",
            "radar/**", ".claude/hooks/**",
        ],
        seams=COMMON_SEAMS + ["team-kits/office-team/skills/office-manager/SKILL.md"],
        inputs=[
            "project_memory/product/active/PR-0008.yaml (AC-1..AC-7) and what it absorbed: FR-0058 (the stock lies upward), BUG-0023 (empty expected_outputs), BUG-0022 (CR type never reached), FR-0007 (comment discipline into the kits: DEC-0008 + SR-0008 are the rule), FR-0012 (a decision landing in prose has no catcher -- DEC-0034's 26 days without an item are the case, DEC-0080 records it), the generation-4 leftovers (BUG-0025, BUG-0033, BUG-0069, BUG-0088, BUG-0090, BUG-0091 to VERIFY against b7f282e with evidence lines; BUG-0083..0086 and BUG-0089 and TSK-0121..0126 to archive)",
            "project_memory/generated/index.yaml and every active BUG/FR (89 BUGs + 155 migrated hole items in bugs/active, 21 FRs -- measured 2026-09-05); the kernel's evidence and transition commands (`evidence`, `transition`, `archive`, `update`) -- every verdict is a kernel write, never a file edit; kernel/report.py (validate_state, tasks_under_an_inbox_item, closed_by_delivery cross-check) as the place of the derivable 'done' and the decision-without-item catcher; kernel/backlog_types.py (AUTOMATA CR, REQUIRED_FIELDS); DEC-0080 rules 3 and 7 and DEC-0077 (4) for .claude/agents/harness-*.md (rules 1-3/7 into harness-lead.md, rule 6 into harness-verifier.md, model pins: implementer fable / verifier opus with the effort line -- the verifier-role pin is a SEAM sentence from G5-2)",
            "DEC-0080 (retrospective), DEC-0063, DEC-0070, DEC-0066 (hierarchy), DEC-0067; the constitutions' 'duties that have no gate behind them' section (G4-3 added the rejected-alternative paragraph there -- the comment-discipline duty joins it byte-identical x3)",
        ],
        outputs=[
            "PR-0008 AC-1 (FR-0058 survey): every one of the active BUGs -- the 89 pre-existing and the 155 migrated holes -- measured against b7f282e (observed line re-run or test executed, one short run at a time) and given ONE of three verdicts THROUGH THE KERNEL: VERIFIED + archived with an Evidence item naming the measurement; OPEN/TRIAGED with the re-measured chain and date written by `update`; CANCELLED/superseded naming the absorbing item; the protocol tables all of them with verdict and measured line; no verdict without a measurement; batches by module so the round can be resumed from disk after a crash.",
            "PR-0008 AC-2 (FR-0058 wishes): the 21 FRs triaged against b7f282e: delivered -> MERGED with resulting_item, absorbed -> pointing at their goal, the deferred block (FR-0024, FR-0019, FR-0022, FR-0023, FR-0025, FR-0020) TRIAGED with the user's 'needs planning' note in the item, no FR left whose source describes something built.",
            "PR-0008 AC-3 (the derivable 'done'): validate names an item standing OPEN while its confirming evidence or named regression test exists and passes -- derived from items + evidence store + the test tree, no list; red-first; measured on this repo's store (the survey feeds it).",
            "PR-0008 AC-4 (BUG-0023): create-task and capture TSK refuse an empty expected_outputs list naming the field (one rule, both entrances); the validator names existing items with an empty list; red-first.",
            "PR-0008 AC-5 (BUG-0022): the CR type reached in a measured run on a scaffolded dev pilot (a change to something built produces a CR through its automaton) with the PM texts saying WHEN a CR applies instead of a PR replacement and a test on the text-to-behaviour path -- or the type removed with the reasons recorded; the PR-replacement path stays and records the replacement.",
            "PR-0008 AC-6 (generation-4 leftovers): BUG-0025, BUG-0033, BUG-0069 (after the user's push: the hosted run is the evidence -- name it as the one line that waits), BUG-0088, BUG-0090, BUG-0091 VERIFIED against b7f282e with their evidence lines; BUG-0083..0086, BUG-0089 archived; TSK-0121..TSK-0126 archived; PR-0004..PR-0007 walked to their delivered status with the merge commit as delivered_commit where the automaton asks for it.",
            "PR-0008 AC-7 (FR-0007 + FR-0012): the comment-discipline duty (a comment carries the WHY and points at items; a property claim becomes a test the comment names; a named test must resolve; no sentence claims a check the code does not build) in the three constitutions' 'duties that have no gate behind them' section byte-identical x3 and in every implementing role definition; the kits ship the mechanical half (a pointer sweep over the project's own code and role texts, red on a named test or item that does not resolve) scaffolded and measured on a pilot per kit; FR-0012: a validator line naming a Decision item whose text demands build work while no item points at it -- DEC-FIRST proposal dec-decision-catcher.json on how a decision says it demands work (a field, a phrase class, or the pointer direction), the user decides; then built red-first and shipped to the three kits in the same round.",
            RULES,
            "Seams: team-kits/kernel/cli.py (G5-2 and G5-3 add commands -- your block only); the constitutions and team-kits/*/agents/*.md (G5-2 writes ladder sentences + model/effort pins, G5-3 the office correspondence role -- you write the comment-discipline duty and the CR rule, per file in the protocol); .claude/agents/harness-*.md are YOURS (DEC-0080 rules 1-3/7 into harness-lead.md, rule 6 into harness-verifier.md, the model/effort pin lines as G5-2 hands them); tools/lead_package_sizes.json + docs/reviews/phase0-disposition.md (record, not overwrite); README.md. Reach seam (DEC-0080 (1)): the validator lines run in every kit -- measure all three pilots; list every suite that reads validate_state before handover (DEC-0080 (2)).",
            HANDOVER.format(name="stock"),
        ],
    ),
    "office": dict(
        pr="PR-0009", type="implementation", acs=["AC-1", "AC-2", "AC-3", "AC-4", "AC-5", "AC-6"],
        allowed=[
            "team-kits/office-team/**", "team-kits/kernel/documents.py", "team-kits/kernel/filing.py",
            "team-kits/kernel/cli.py", "team-kits/*/VERSION", "tools/**", "docs/**", "README.md",
        ],
        forbidden=COMMON_FORBIDDEN + [
            "team-kits/kernel/dispatch.py", "team-kits/kernel/report.py", "team-kits/kernel/state.py",
            "team-kits/kernel/backlog_types.py", "team-kits/kernel/approvals.py", "team-kits/kernel/holes.py",
            "team-kits/model_tiers.yaml", "team-kits/gen_provider_artifacts.py", "team-kits/dev-team/**",
            "team-kits/research-team/**", "team-kits/office-team/hooks/gate_dispatch.py",
            "team-kits/office-team/ladder.yaml", "team-kits/office-team/settings/**",
            "team-kits/office-team/skills/project-auditor/**",
            ".claude/agents/**", ".claude/hooks/**", "radar/**",
        ],
        seams=COMMON_SEAMS + ["team-kits/office-team/constitution/AGENTS.md", "team-kits/office-team/agents/*.md",
                              "team-kits/office-team/skills/office-manager/SKILL.md"],
        inputs=[
            "project_memory/product/active/PR-0009.yaml (AC-1..AC-6) and what it absorbed: FR-0033 (correspondence), FR-0081 (SKR03/SKR04 + EUeR mapping, year-versioned, legal space), FR-0002 (eight takeovers -- docs/ source section), BUG-0070 (add-filing-rule cannot create the rules list), BUG-0071 (categories have no kernel writer, P4-12 lineage), BUG-0072 (einvoice_extract.py non-reconciling net), BUG-0079 (documents.py prints a remedy it refuses); DEC-0075 (the invoice application is its own product; this goal builds the DOCKING POINT: intake, validation, number-range continuity per business, filing, booking, the interface contract written for the app project; the three marketplace cases create / cancel-and-reissue / import-only are separated by law), DEC-0078 (office runs the lower ladder -- not built here, G5-2 owns it), DEC-0056, DEC-0066",
            "team-kits/office-team/** (constitution, skills incl. office-manager and bookkeeper, templates/project_memory incl. filing_plan.yaml and master_data.yaml, templates/repo/scripts/einvoice_extract.py, hooks except gate_dispatch.py), team-kits/kernel/documents.py (the document route and its remedies), team-kits/kernel/filing.py (add-filing-rule), the office pilot measurements in the round logs (P4-9, P4-12, the live finds of 2026-08-29), the humanizer skill the kit ships (the plain-language bar for outgoing texts)",
            "DEC-0080 (retrospective rules), DEC-0063, DEC-0070; the user's words 2026-09-05 on the invoice application (two businesses, eBay / Kaufland / Shopify, sequential numbers, the docking point is what the kit owns)",
        ],
        outputs=[
            "PR-0009 AC-1 (FR-0033, DEC-FIRST): dec-correspondence.json to the lead -- role vs teachable workflow, with the measured cost of each (one more agent definition and its ladder pin vs a skill the office-manager runs) -- the user decides; then a scaffolded office pilot produces an offer, a reminder (Mahnung) and a customer letter from ledger + master data through the sanctioned document route, each reviewed before it leaves (gate or duty named), measured end to end; texts pass the kit's humanizer / plain-language bar.",
            "PR-0009 AC-2 (docking point, DEC-0075): an intake route accepts an invoice file the external app produced (fixture set: one ZUGFeRD PDF, one XRechnung XML), validates norm rules (EN 16931 rule subset named) and the reconciling triple, checks number-range continuity per business against the ledger, files it through the document route and books it; a planted violation (broken triple, gap in a number range, missing mandatory field) is refused naming the figures; the INTERFACE CONTRACT (file shape, drop location, what the kit answers, the three marketplace cases) is written as docs/ for the app project; measured on a pilot; red-first.",
            "PR-0009 AC-3 (FR-0081): SKR03/SKR04 as year-versioned kit documents with the account-to-EUeR-line mapping and the legal space named; the bookkeeper's booking names an account and the EUeR rollup reads the mapping; a kernel writer exists for the document (no editor line); measured on a pilot; red-first.",
            "PR-0009 AC-4 (FR-0002): each of the eight takeovers built here with its own acceptance line, absorbed by a named item, or rejected with the reason -- none stays prose without a verdict; the table in the protocol.",
            "PR-0009 AC-5 (BUG-0070 + BUG-0071): add-filing-rule creates the rules list when the plan carries none (>1 keys still refused, =1 unchanged); categories -- and, decided in the round with reasons, every kit-document list -- get a sanctioned approval-gated kernel writer (special case vs general mechanism recorded, P4-12 lineage); red-first on an old-stock copy outside the repo.",
            "PR-0009 AC-6 (BUG-0072 + BUG-0079): einvoice_extract.py returns the reconciling document total from CII structures and fails loudly on a non-reconciling triple (both directions tested, the extraction-path change named precisely enough for a project-side sweep); every remedy line the kernel prints is executed by a test against the CLI and accepted (documents.py first, the other modules grepped); red-first.",
            RULES,
            "Seams: team-kits/kernel/cli.py (G5-1 and G5-2 add commands -- your block only); team-kits/office-team/constitution/AGENTS.md and office-team/agents/*.md (G5-1 writes the comment-discipline duty into every constitution and implementing role, G5-2 the ladder sentences and pins -- you write the correspondence role/workflow and the docking-point duty, per file in the protocol); mirrored files: none expected (office is not mirrored) -- if a change needs dev/research, it is a SEAM sentence to the merge, not a write; tools/lead_package_sizes.json + docs/reviews/phase0-disposition.md (record, not overwrite); README.md. Reach seam (DEC-0080 (1)): a kernel writer in documents.py / filing.py is read by every kit -- measure a dev and a research pilot for no regression; list every suite that reads the changed kernel functions (DEC-0080 (2)).",
            HANDOVER.format(name="office"),
        ],
    ),
}


def main():
    for name, spec in STREAMS.items():
        argv = list(KERNEL) + [
            "--product-requirement", spec["pr"], "--derives-from", spec["pr"],
            "--type", spec["type"], "--assigned-role", "harness-implementer",
        ]
        for ac in spec["acs"]:
            argv += ["--acceptance-ref", ac]
        for path in spec["allowed"]:
            argv += ["--allowed-scope", path]
        for path in spec["forbidden"]:
            argv += ["--forbidden-scope", path]
        for path in spec["seams"]:
            argv += ["--seam-scope", path]
        for line in spec["inputs"]:
            argv += ["--required-input", line]
        for line in spec["outputs"]:
            argv += ["--expected-output", line]
        env = dict(os.environ, PYTHONPATH="team-kits")
        print("== stream", name, "(", spec["pr"], ")")
        result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
        print(result.stdout.strip()[-400:])
        if result.returncode != 0:
            print(result.stderr.strip()[-1500:])
            print("!! rc", result.returncode, "-- stopping")
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
