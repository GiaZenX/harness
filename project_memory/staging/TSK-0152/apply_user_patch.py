"""The USER's patch for TSK-0152 -- run it from a shell OUTSIDE Claude Code.

WHY YOU AND NOT A ROLE: `.claude/hooks/*.py` is refused to every role of this repository (gate 1);
the gates cannot be edited from inside the session that runs under them. What each site is for, with
its before/after text and the hole it closes, stands in `user-patch.md` beside this file.

HOW:
    cd "C:\\Offline Repos\\AgentAndSkills"
    python project_memory\\staging\\TSK-0152\\apply_user_patch.py --check     (reads only, says what it would do)
    python project_memory\\staging\\TSK-0152\\apply_user_patch.py             (applies ALL or NOTHING)
Then `git diff --stat` shows the changed files; start a new Claude Code session (the gates' files are
read on every call, but a new session is the clean point to take them up).

ALL OR NOTHING: every BEFORE text must occur exactly once in its file (or its AFTER text is already
there -- then the site counts as done). If one site does not fit, nothing is written and the script
says which one. Every file is read and written with its own line endings untouched.
"""
import io
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

SITES = [
    ("1a H13/H151: the producers' directories are an area (a slot)", ".claude/hooks/_harness.py",
     "                 \"staging\", \"hook_directories\")\n",
     "                 \"staging\", \"hook_directories\", \"producer_directories\")\n"),
    ("1b H13/H151: the producers' directories, derived once per call", ".claude/hooks/_harness.py",
     "        self.producer_files = decision_inputs(root)\n",
     "        self.producer_files = decision_inputs(root)\n"
     "        # The directory every producer lies in, the checkout itself excepted (widening to it would\n"
     "        # protect every file of the repo). A SLOT and not a local of `verdict`, because the areas\n"
     "        # ARE the slots: `_sandbox.protected_files` walks them, so the measurement watch list covers\n"
     "        # what this area protects -- held by\n"
     "        # `.claude/hooks/test_gates.py::test_the_measurement_watch_list_is_the_area_the_gate_protects`.\n"
     "        self.producer_directories = sorted(\n"
     "            directory for directory in {os.path.dirname(name) for name in self.producer_files}\n"
     "            if not (under(directory, root) and under(root, directory)))\n"),
    ("1c H13/H151: a producer's directory is protected (the rule)", ".claude/hooks/_harness.py",
     "                \"`kernel.hashing.kit_hash_inputs`, not from a list kept here.\"))\n"
     "        return None, None\n",
     "                \"`kernel.hashing.kit_hash_inputs`, not from a list kept here.\"))\n"
     "        # A PRODUCER IS PROTECTED WITH ITS DIRECTORY (BUG-0105/H13, BUG-0233/H151), asked LAST so\n"
     "        # every narrower reason above answers first. The producer set is measured per call\n"
     "        # (`decision_inputs`); a NEW file beside the stamper -- its next helper, a module it would\n"
     "        # import, gate 5's declaration `tools/test_surface.json` -- is written where that set\n"
     "        # already points.\n"
     "        # `.claude/hooks/test_gates.py::test_gate1_refuses_the_lead_a_new_file_beside_the_stamper_bug_0105`\n"
     "        # `.claude/hooks/test_gates.py::test_gate1_refuses_the_lead_gate5s_declaration_bug_0233`\n"
     "        for directory in self.producer_directories:\n"
     "            if under(path, directory):\n"
     "                return SESSION_ONLY, (\n"
     "                    \"this path lies in %s, the directory of a file gate 1 derives its protected \"\n"
     "                    \"area from. A NEW file there is protected too: the producer's next helper or \"\n"
     "                    \"data file would otherwise be written beside it unrefused (H13), and gate 5 \"\n"
     "                    \"decides on such a file (`tools/test_surface.json`, H151). An implementer \"\n"
     "                    \"subagent writes it, ordered by an item.\" % _shown(self.root, directory))\n"
     "        return None, None\n"),
    ("2 H69: the kits' CR door, borrowed from the shared reader", ".claude/hooks/_harness.py",
     "               \"Remedy: split the call.\" % module.STDIN_LIMIT)\n",
     "               \"Remedy: split the call.\" % module.STDIN_LIMIT)\n"
     "    # THE KITS' SECOND DOOR, asked of the reader these gates already borrow (BUG-0161 / H69): a\n"
     "    # character the tool's shell never sees makes the line read here not the line that runs --\n"
     "    # `project_mem<CR>ory/...` is one canonical path to that shell and two words to this reader.\n"
     "    # `.claude/hooks/test_gates.py::test_gate1_refuses_a_character_the_shell_never_sees_bug_0161`\n"
     "    eaten = module.eaten_in_flight(data)\n"
     "    if eaten:\n"
     "        refuse(\"This tool call could not be inspected: its command line carries a character its \"\n"
     "               \"shell will never see (%s), so what this gate reads is not what would run.\\n\"\n"
     "               \"Remedy: write the line without that character; a command in several steps is \"\n"
     "               \"spelled with a real newline or with `;`, `&&`, `||`.\" % eaten)\n"),
    ("3 H13: the docstring of decision_inputs", ".claude/hooks/_harness.py",
     "    WHAT IT DOES NOT REACH, named rather than implied: files, not directories. A module that\n"
     "    `bump_kit_version.py` imports lazily inside a function this gate never calls is not loaded and\n"
     "    therefore not protected, and neither is a NEW file placed beside it. Only `tools/` as a whole\n"
     "    would cover those, and `tools/` is not derivable from anything this gate reads.\n",
     "    FILES HERE, DIRECTORIES IN `ProtectedArea.verdict`: this returns the files, and the verdict\n"
     "    protects the DIRECTORY each of them lies in as well (BUG-0105/H13), so a module\n"
     "    `bump_kit_version.py` imports lazily, or a NEW file placed beside it, is covered although it\n"
     "    was never loaded. What stays open: such a module in a directory no producer lies in.\n"),
    ("4 CLAUDE.md: tools/ after the patch", "CLAUDE.md",
     "**`tools/` ist damit nicht mehr pauschal frei** — geschützt ist die Datei, aus der abgeleitet wird,\n"
     "nicht das Verzeichnis. Ein *neues* File neben ihr bleibt schreibbar; das steht als Loch in\n"
     "`docs/POST_V2_WISHLIST.md`, nicht als Schutzbehauptung hier.\n",
     "**`tools/` ist für den Sitzungsagenten geschützt**, und zwar als Ableitung: geschützt ist jede\n"
     "Datei, aus der abgeleitet wird, UND das Verzeichnis, in dem sie liegt — also auch ein *neues*\n"
     "File neben dem Stempler und die Erklärung, auf der Gate 5 entscheidet (`tools/test_surface.json`).\n"
     "Ein Umsetzer-Subagent schreibt dort weiter (H13, H151; TSK-0152).\n"),
    ("5 tools/test_surface.json: its own protection", "tools/test_surface.json",
     "WHAT IT IS NOT: protected. `_harness.decision_inputs` derives gate 1's protected area from the "
     "modules a gate LOADED, and a JSON file is not a module -- so whoever may write tools/ may switch "
     "this gate off without touching a protected path. Named as H151 with its chain rather than "
     "claimed away here; per DEC-0056 a gate guards against error, not against an insider who edits "
     "the declaration.",
     "WHO MAY WRITE IT: an implementer subagent, not the session agent. Gate 1 protects the directory "
     "of every file it derives its protected area from, and `tools/bump_kit_version.py` lies here "
     "(H151, H13; TSK-0152). Per DEC-0056 a gate guards against error, not against an insider who "
     "edits the declaration."),
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
        # AFTER FIRST: a site whose BEFORE text is a prefix of its AFTER text (site 1) still shows its
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
