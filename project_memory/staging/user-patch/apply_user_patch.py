"""The USER's patch for this repository's own enforcement layer -- run it from a shell OUTSIDE Claude Code.

WHY YOU AND NOT A ROLE: `.claude/hooks/**`, `.claude/agents/**`, `.claude/settings.json` and
`project_memory/project_config.yaml` are refused to every role of this repository (gate 1); a gate cannot be repaired
from inside the session that runs it. Every change below is TEXT except the config line: no gate decides differently
afterwards (sources: staging/TSK-0143/h182-harness-patch-EXTENDED.md sites 1-7, staging/TSK-0141/s4-gate-commit-
evidence-patch.md site 8, DEC-0105 for the config line).

HOW:
    cd "C:\\Offline Repos\\AgentAndSkills"
    python project_memory\\staging\\user-patch\\apply_user_patch.py --check     (reads only, says what it would do)
    python project_memory\\staging\\user-patch\\apply_user_patch.py             (applies ALL or NOTHING)
Then `git diff --stat` shows the changed files; start a new Claude Code session.

ALL OR NOTHING: every BEFORE text must occur exactly once in its file (or its AFTER text is already there -- then the
site counts as done). If one site does not fit, nothing is written and the script says which one.
"""
import io
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

SITES = [
    ("1a H182", ".claude/hooks/gate_spawn_needs_item.py",
     r'''role names. Two agents in this repo run on a weekly schedule and hold no item (`radar-watcher`,''',
     r'''role names. Two agents in this repo hold no item (`radar-watcher`,'''),
    ("1b H182", ".claude/hooks/gate_spawn_needs_item.py",
     r'''frontmatter key `harness_item:` -- `none` for a schedule-driven role, and required for everything''',
     r'''frontmatter key `harness_item:` -- `none` for a role that holds none, and required for everything'''),
    ("2 H182", ".claude/hooks/gate_spawn_needs_item.py",
     r'''        "scheduled watcher), its definition in .claude/agents/%s.md declares `%s: %s` in its "''',
     r'''        "watcher), its definition in .claude/agents/%s.md declares `%s: %s` in its "'''),
    ("3 H182", ".claude/hooks/_harness.py",
     r'''    this repo genuinely have no item -- the weekly watchers run on a schedule and write only into''',
     r'''    this repo genuinely have no item -- the watchers write only into'''),
    ("4 four gates", ".claude/agents/harness-lead.md",
     r'''decision refuses. So the enforcement is four gates of this repo's own, in `.claude/hooks/`,''',
     r'''decision refuses. So the enforcement is this repo's own gates, in `.claude/hooks/`,'''),
    ("5 four gates", ".claude/hooks/_harness.py",
     r'''replaced by four gates written for this repo, plus a bound session agent so the payload shape the''',
     r'''replaced by gates written for this repo, plus a bound session agent so the payload shape the'''),
    ("6 four gates", ".claude/hooks/_harness.py",
     r'''    the registration of all four gates.''',
     r'''    the registration of every gate this repo runs.'''),
    ("7 SR-0006", ".claude/settings.json",
     r'''The PreToolUse gates below are the replacement SR-0006 specifies''',
     r'''The PreToolUse gates below are the replacement SR-0009 specifies (it replaced SR-0006 on 2026-08-13)'''),
    ("8 S4 remedy", ".claude/hooks/gate_commit_evidence.py",
     r'''        "        --artifact-ref <path/relative/to/%s>\n"
        "(PowerShell:''',
     r'''        "        --artifact-ref <path/relative/to/%s> \\\n"
        "        --run-command \"<the line the verdict was produced by>\" \\\n"
        "        --run-scope <full|selection>\n"
        "(PowerShell:'''),
]

CONFIG = "project_memory/project_config.yaml"
CONFIG_LINE = "model_tiers: ladder.yaml"


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
        if n_before == 1:
            todo.append((name, rel, b, a))
        elif n_before == 0 and n_after >= 1:
            print("  already done   %s  (%s)" % (name, rel))
        else:
            problems.append("%s: BEFORE text found %d times in %s (must be exactly 1)" % (name, n_before, rel))
    config = read(CONFIG)
    config_todo = not any(line.strip().startswith("model_tiers:") for line in config.splitlines())
    if not config_todo:
        print("  already done   config line (%s)" % CONFIG)
    return texts, todo, config_todo, problems


def main():
    check = "--check" in sys.argv
    texts, todo, config_todo, problems = plan()
    if problems:
        print("NOTHING WRITTEN -- these sites do not fit the tree:")
        for p in problems:
            print("  " + p)
        return 1
    for name, rel, _b, _a in todo:
        print("  %s  %s  (%s)" % ("would change" if check else "change      ", name, rel))
    if config_todo:
        print("  %s  config line '%s' (%s)" % ("would add   " if check else "add         ", CONFIG_LINE, CONFIG))
    if check:
        print("CHECK ONLY -- %d site(s) to change, config line %s. Run without --check to apply."
              % (len(todo), "to add" if config_todo else "present"))
        return 0
    for name, rel, b, a in todo:
        texts[rel] = texts[rel].replace(b, a, 1)
    for rel in {rel for _n, rel, _b, _a in todo}:
        with io.open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="") as handle:
            handle.write(texts[rel])
    if config_todo:
        config = read(CONFIG)
        eol = "\r\n" if "\r\n" in config else "\n"
        if not config.endswith(("\n", "\r\n")):
            config += eol
        with io.open(os.path.join(ROOT, CONFIG), "w", encoding="utf-8", newline="") as handle:
            handle.write(config + CONFIG_LINE + eol)
    print("DONE -- %d site(s) changed%s. Check with `git diff --stat`, then start a new Claude Code session."
          % (len(todo), ", config line added" if config_todo else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
