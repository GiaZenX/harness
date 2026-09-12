# Seam S4 (user patch) -- the commit gate's remedy is rc 2 since this round

**Why the user and not a role.** `.claude/hooks/gate_commit_evidence.py` is in `.claude/hooks/`,
which every role in this repository is refused; the remedy every refusal prints says it: run the
fix from a shell OUTSIDE Claude Code and start a new session.

**What broke it.** This round made `--run-command` and `--run-scope` required on the `evidence`
surface (BUG-0192 / H108, S2): an Evidence that declares no run scope counted as a full run, so a
partial run opened a merge in silence. The gate's remedy text was written before that and does not
carry the pair, so the line it prints is now refused.

**Measured against the running kernel, 2026-09-12 13:2x**, by typing the printed line:

    PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory evidence \
        --kind review --result pass --related TSK-0141 \
        --summary "verifier PASS for deadbeef" \
        --artifact-ref staging/TSK-0141/protocol.md

    python scripts/harness.py evidence: error: the following arguments are required:
        --run-command, --run-scope

This is the line the gate prints at EVERY blocked hand-over, so it is on the path every delivery
takes. `.claude/hooks/gate_test_scope.py:709-712` already carries the pair and needs nothing.

**Why no test caught it:** `tools/test_hooks.py::_texts_that_name_the_evidence_vocabulary` reads the
three kits' instruction files, the shipped kit modules and the README -- `.claude/hooks/` of THIS
repository is outside its corpus. Widening that corpus is a change to a file stream C owns, and it
is named here rather than made.

## The patch

File: `.claude/hooks/gate_commit_evidence.py`, in the refusal text (lines 418-423 at 10a5127).

BEFORE:

    "Remedy -- the verifier records its verdict, then the commit is open:\n"
    "    PYTHONPATH=team-kits python -B -m kernel.cli --root %s evidence \\\n"
    "        --kind review --result pass --related <ITEM-ID> \\\n"
    "        --summary \"verifier PASS for %s\" \\\n"
    "        --artifact-ref <path/relative/to/%s>\n"
    "(PowerShell: $env:PYTHONPATH=\"team-kits\"; python -B -m kernel.cli --root %s evidence "
    "...)\n"

AFTER (two lines added; nothing else changes, and the `%s` order is untouched):

    "Remedy -- the verifier records its verdict, then the commit is open:\n"
    "    PYTHONPATH=team-kits python -B -m kernel.cli --root %s evidence \\\n"
    "        --kind review --result pass --related <ITEM-ID> \\\n"
    "        --summary \"verifier PASS for %s\" \\\n"
    "        --artifact-ref <path/relative/to/%s> \\\n"
    "        --run-command \"<the line the verdict was produced by>\" \\\n"
    "        --run-scope <full|selection>\n"
    "(PowerShell: $env:PYTHONPATH=\"team-kits\"; python -B -m kernel.cli --root %s evidence "
    "...)\n"

## THE PATCH IS NOT ENOUGH ON ITS OWN -- the gate suite has ten more call sites (round 3, F4)

Measured by the verifier after applying this patch in a copy: the remedy really records an
Evidence (`EVD-0403 review: pass`, rc 0), and the acceptance this file prescribes is still red --
`python -B -m pytest .claude/hooks/test_gates.py -q -k commit` -> 3 failed, 17 passed, 31 errors,
with `python scripts/harness.py evidence: error: the following arguments are required:
--run-command, --run-scope` underneath.

`.claude/hooks/test_gates.py` drives the `evidence` surface as a real subprocess at TEN places
(`:1560, :1584, :1616, :1641, :1659, :1980, :2067, :2553, :6911`) and carries the pair at one
(`:7333`). That file belongs to TSK-0143 (stream C), and the lead has told that stream; the patch
above is not acceptable until those call sites carry the pair too. Recorded here so the two halves
travel together.

Correction to an earlier sentence in this stream's protocol: "why no test saw it" was wrong. A test
DID see it -- in the suite `CLAUDE.md` starts separately, which runs in neither `pytest tools/` nor
a kit run.

## The arbiter after the patch

Type the printed line against this repository's own store -- it has to record an `EVD` instead of
exiting 2:

    PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory evidence \
        --kind review --result pass --related <ITEM-ID> --summary "verifier PASS for <digest>" \
        --artifact-ref staging/<ITEM-ID>/protocol.md \
        --run-command "python -B -m pytest tools/ -q" --run-scope full

and `python -B -m pytest .claude/hooks/test_gates.py -q -k commit` for the gate's own suite.


## Lead's note (2026-09-12 21:04, clock read)

The sentence above that `gate_test_scope.py:709-712` "already carries the pair and needs nothing" is true for the FILE (it renders `--run-scope full --run-command "..."` correctly) and was false for the vocabulary reader of TSK-0144's first cut, which read the SOURCE `--%s` and reported the file as omitting the pair (verifier M, round 1, B1). The reader now treats a computed flag as 'not spelled' (`_COMPUTED_FLAG_RX`), so after this patch `tools/test_hooks.py::test_every_evidence_command_a_text_spells_names_every_argument_the_cli_requires` is GREEN (measured in the rig with the patch applied: 1 passed) and red without it. Nothing else to patch in gate_test_scope.py.
