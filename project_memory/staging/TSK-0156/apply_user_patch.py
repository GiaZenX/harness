"""The USER's patch for TSK-0156 -- run it from a shell OUTSIDE Claude Code.

WHY YOU AND NOT A ROLE: `.claude/hooks/*.py` and `.claude/agents/*.md` are refused to every role of
this repository (gate 1); the gates cannot be edited from inside the session that runs under them.
What each site is for, with the hole it closes and the test that measures it, stands in
`user-patch.md` beside this file.

HOW:
    cd "C:\\Offline Repos\\AgentAndSkills"
    python project_memory\\staging\\TSK-0156\\apply_user_patch.py --check     (reads only, says what it would do)
    python project_memory\\staging\\TSK-0156\\apply_user_patch.py             (applies ALL or NOTHING)
Then `git diff --stat` shows the changed files; start a new Claude Code session.

ALL OR NOTHING: every BEFORE text must occur exactly once in its file (or its AFTER text is already
there -- then the site counts as done). If one site does not fit, nothing is written and the script
says which one. Every file is read and written with its own line endings untouched.
"""
import io
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

SITES = [
    ("1a H47: `_candidates` learns the path position", ".claude/hooks/_harness.py",
     "def _candidates(compat_module, word, position, starts=False):\n",
     "def _candidates(compat_module, word, position, starts=False, path_position=False):\n"),
    ("1b H47: a word in a path position is a possible path whatever it looks like",
     ".claude/hooks/_harness.py",
     "        unresolved = _unresolved_at(str(reading)) if _could_name_a_path(reading, starts) else None\n",
     "        unresolved = (_unresolved_at(str(reading))\n"
     "                      if path_position or _could_name_a_path(reading, starts) else None)\n"
     "        if path_position and \"`\" in str(reading):\n"
     "            # a backtick opens a command substitution that `_UNRESOLVED` does not list; in a\n"
     "            # path position it is refused like `$(` (DEC-0120 (1)), and nowhere else widened\n"
     "            tick = str(reading).index(\"`\")\n"
     "            unresolved = tick if unresolved is None else min(unresolved, tick)\n"),
    ("1c H47: a redirect target is a path position (DEC-0120)", ".claude/hooks/_harness.py",
     "            out.extend(_candidates(compat_module, target, directory))\n",
     "            # A REDIRECT TARGET IS ALWAYS A PATH (DEC-0120, BUG-0139/H47), so a shell expansion in\n"
     "            # it is REFUSED as unplaceable rather than resolved -- `_could_name_a_path` reads only a\n"
     "            # separator or the program position as \"path\", and `> $F` has neither. No second copy\n"
     "            # of the kits' resolver; the cost (`echo x > $LOG` refused) is DEC-0120 (3).\n"
     "            # `.claude/hooks/test_gates.py::test_gate1_refuses_a_redirect_into_a_variable_bug_0139`\n"
     "            # `.claude/hooks/test_gates.py::test_gate1_still_passes_a_redirect_with_no_expansion_in_its_target`\n"
     "            out.extend(_candidates(compat_module, target, directory, path_position=True))\n"),
    ("2 FR-0093 / BUG-0313: the lead's background-run line", ".claude/agents/harness-lead.md",
     "  into every turn of the second. A run longer than a few minutes starts in the background and\n"
     "  the agent waits for its completion notice -- no loop of sleeping and looking at a log. A file\n"
     "  over 2,000 lines, and every protocol, is read by section, never whole.\n",
     "  into every turn of the second. A run longer than a few minutes starts in the background and\n"
     "  the agent waits for its completion notice -- no loop of sleeping and looking at a log -- and\n"
     "  it does NOT end its turn to wait: an ended turn is its report to you, whatever still runs,\n"
     "  and a child that resumed on a late notice had already been read as finished (`BUG-0313`;\n"
     "  the kits' PM skills carry the same correction). A file over 2,000 lines, and every protocol,\n"
     "  is read by section, never whole.\n"),
]


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
        # AFTER FIRST: a site whose BEFORE text is a prefix of its AFTER text still shows its
        # BEFORE once when it is done, and would otherwise be applied a second time
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
    for rel in sorted({rel for _n, rel, _b, _a in todo}):
        with io.open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="") as handle:
            handle.write(texts[rel])
    print("DONE -- %d site(s) changed. Check with `git diff --stat`, then start a new Claude Code "
          "session." % len(todo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
