"""The USER's patch for TSK-0151 -- run it from a shell OUTSIDE Claude Code.

WHY YOU AND NOT A ROLE: `.claude/agents/**` is refused to every role of this repository (gate 1); a
role definition the gates read cannot be edited from inside the session that runs under it. Every
change below is TEXT in three role definitions; no gate decides differently afterwards. What each
site is for, with its before/after text, stands in `user-patch.md` beside this file.

HOW:
    cd "C:\\Offline Repos\\AgentAndSkills"
    python project_memory\\staging\\TSK-0151\\apply_user_patch.py --check     (reads only, says what it would do)
    python project_memory\\staging\\TSK-0151\\apply_user_patch.py             (applies ALL or NOTHING)
Then `git diff --stat` shows the changed files; start a new Claude Code session (the lead's
`effort:` binds at session start).

ALL OR NOTHING: every BEFORE text must occur exactly once in its file (or its AFTER text is already
there -- then the site counts as done). If one site does not fit, nothing is written and the script
says which one. AFTER a real run it regenerates the two Codex overlays of the watchers
(`python tools/radar_routine.py --write-overlays`), because those are generated FROM the two
watcher definitions this patch changes and a test holds them equal.
"""
import io
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

SITES = [
    ("1 lead effort (DEC-0114 (5))", ".claude/agents/harness-lead.md",
     "harness_item: required\nmodel: opus\n---\n",
     "harness_item: required\nmodel: opus\neffort: xhigh\n---\n"),
    ("2 order cost lines (FR-0093)", ".claude/agents/harness-lead.md",
     "  order goes out\". The order is generated FROM the item, so a coarse item is a coarse round.\n",
     "  order goes out\". The order is generated FROM the item, so a coarse item is a coarse round.\n"
     "- **Three cost lines every order carries, word for word** (`FR-0093`, which holds the\n"
     "  measurement). A rework is a FRESH agent given only the verifier's report, the item and the\n"
     "  protocol path -- never a resumed implementer, whose context carries the whole first attempt\n"
     "  into every turn of the second. A run longer than a few minutes starts in the background and\n"
     "  the agent waits for its completion notice -- no loop of sleeping and looking at a log. A file\n"
     "  over 2,000 lines, and every protocol, is read by section, never whole.\n"),
    ("3 claude-watcher schedule (DEC-0098)", ".claude/agents/claude-watcher.md",
     "  report into radar/. Never changes code. Its Friday run is started by a Claude Desktop scheduled\n"
     "  task on the maintainer's host (DEC-0089; recorded in radar/routine.json, explained in\n"
     "  radar/README.md); its Sunday run is a Codex app Automation the user has not created yet, and\n"
     "  until both have been recorded the lead starts the missing run with\n",
     "  report into radar/. Never changes code. Its Friday run is started by a Claude Desktop scheduled\n"
     "  task on the maintainer's host, `watcher-duo`, which runs it first and the codex-watcher second\n"
     "  (DEC-0089, DEC-0098; recorded in radar/routine.json, explained in radar/README.md); its Codex\n"
     "  run is a Codex app Automation on the same Friday evening that the user has not created yet, and\n"
     "  until both have been recorded the lead starts the missing run with\n"),
    ("4 codex-watcher schedule (DEC-0098)", ".claude/agents/codex-watcher.md",
     "  radar/. Never changes code. Neither of its two weekly runs is recorded yet (DEC-0090 (4): a\n"
     "  Claude Desktop scheduled task on Saturday and a Codex app Automation on Monday, created at the\n"
     "  next local session and recorded in radar/routine.json once they have run); until then the lead\n",
     "  radar/. Never changes code. Neither of its two weekly runs is recorded yet (DEC-0098: the second\n"
     "  step of the Claude Desktop scheduled task `watcher-duo` and a Codex app Automation, both on\n"
     "  Friday evening, recorded in radar/routine.json once they have run); until then the lead\n"),
    ("5 claude-watcher tier duty (DEC-0114)", ".claude/agents/claude-watcher.md",
     "   - **TIER TABLE (team-kits/model_tiers.yaml):** when a model/price finding changes what `lead`/\n"
     "     `worker`/`light` should map to on the CLAUDE side, add an explicit tier-change PROPOSAL to the\n"
     "     report (old -> new + evidence). You never edit the table yourself — re-tiering is always a\n"
     "     user decision.\n",
     "   - **TIER TABLE (team-kits/model_tiers.yaml):** the table carries no prices (DEC-0114 (3)); per\n"
     "     rung it says what the model is SUITED FOR (`suited_for:`, the vendor's words, source, read\n"
     "     date). When a finding changes that positioning, or what a rung (`sonnet`/`opus`/`fable`)\n"
     "     should map to on the CLAUDE side, add an explicit tier-change PROPOSAL to the report (old ->\n"
     "     new + evidence). The claude row passes the names through on purpose, so a new model behind\n"
     "     a name is a finding to report, not a defect (DEC-0114 (2)). You never edit the table\n"
     "     yourself — re-tiering is always a user decision.\n"),
    ("6 codex-watcher tier duty (DEC-0114)", ".claude/agents/codex-watcher.md",
     "     + pricing — new family members, price changes, deprecations. When a finding changes what\n"
     "     `lead`/`worker`/`light` should map to for the codex provider, add an explicit tier-change\n"
     "     PROPOSAL (old -> new + evidence). You never edit the table — re-tiering is a user decision.\n",
     "     + pricing — new family members, price changes, deprecations. The table carries no prices\n"
     "     (DEC-0114 (3)); per rung it says what the model is SUITED FOR (`suited_for:`). When a finding\n"
     "     changes that positioning, or what a rung (`sonnet`/`opus`/`fable`) should map to for the\n"
     "     codex provider, add an explicit tier-change PROPOSAL (old -> new + evidence). You never\n"
     "     edit the table — re-tiering is a user decision.\n"),
]
WATCHERS = {".claude/agents/claude-watcher.md", ".claude/agents/codex-watcher.md"}


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8", newline="") as handle:
        return handle.read()


def plan():
    texts, problems, todo = {}, [], []
    for name, rel, before, after in SITES:
        text = texts.get(rel)
        if text is None:
            try:
                text = texts[rel] = read(rel)
            except OSError as exc:
                problems.append("%s: cannot read %s (%s)" % (name, rel, exc))
                continue
        # the file may be CRLF on this host: match the anchor in the file's own line ending
        eol = "\r\n" if "\r\n" in text else "\n"
        b, a = before.replace("\n", eol), after.replace("\n", eol)
        n_before, n_after = text.count(b), text.count(a)
        # AFTER FIRST: a site whose BEFORE text is a prefix of its AFTER text (site 2) still shows
        # its BEFORE once when it is done, and was applied a second time (verifier round 1, V5)
        if n_after >= 1:
            print("  already done   %s  (%s)" % (name, rel))
        elif n_before == 1:
            todo.append((name, rel, b, a))
        else:
            problems.append("%s: BEFORE text found %d times in %s (must be exactly 1)"
                            % (name, n_before, rel))
    return texts, todo, problems


def main():
    check = "--check" in sys.argv
    texts, todo, problems = plan()
    if problems:
        print("NOTHING WRITTEN -- these sites do not fit the tree:")
        for problem in problems:
            print("  " + problem)
        return 1
    for name, rel, _b, _a in todo:
        print("  %s  %s  (%s)" % ("would change" if check else "change      ", name, rel))
    if check:
        print("CHECK ONLY -- %d site(s) to change. Run without --check to apply." % len(todo))
        return 0
    for name, rel, b, a in todo:
        texts[rel] = texts[rel].replace(b, a, 1)
    for rel in {rel for _n, rel, _b, _a in todo}:
        with io.open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="") as handle:
            handle.write(texts[rel])
    if WATCHERS & {rel for _n, rel, _b, _a in todo}:
        run = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "tools", "radar_routine.py"),
                              "--write-overlays"], cwd=ROOT)
        if run.returncode != 0:
            print("the sites are written, but regenerating the Codex overlays failed (rc %d) -- run "
                  "`python tools/radar_routine.py --write-overlays` yourself" % run.returncode)
            return 1
    print("DONE -- %d site(s) changed. Check with `git diff --stat`, then start a new Claude Code "
          "session." % len(todo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
