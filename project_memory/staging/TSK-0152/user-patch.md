# TSK-0152 -- user patch for `.claude/hooks/_harness.py` (+ two texts that describe it)

Gate 1 refuses `.claude/hooks/*.py` to every role of this repository, so these changes are the
user's to apply, from a shell OUTSIDE Claude Code:

```
cd "C:\Offline Repos\AgentAndSkills"
python project_memory\staging\TSK-0152\apply_user_patch.py --check
python project_memory\staging\TSK-0152\apply_user_patch.py
```

The script is the authority on the exact text: every BEFORE below occurs exactly once in its file
(measured with `--check`, see the protocol), the script writes ALL its sites or NOTHING, and a
second run reports every site "already done". It needs the kit files of this same working tree:
site 2 calls `_compat.eaten_in_flight`, which TSK-0152 moved into the kits' shared reader.

What the patch closes, and the test in `.claude/hooks/test_gates.py` that is red before it and green
after it (measured in a copy, protocol section 6):

| Hole | Bug | Test |
|---|---|---|
| H13 | BUG-0105 | `test_gate1_refuses_the_lead_a_new_file_beside_the_stamper_bug_0105` |
| H151 | BUG-0233 | `test_gate1_refuses_the_lead_gate5s_declaration_bug_0233` |
| H69 | BUG-0161 | `test_gate1_refuses_a_character_the_shell_never_sees_bug_0161` (both callers) |

H47 / BUG-0139 is NOT in this patch: it is a class question (DEC-0070 rule 2, "the resolution"),
asked in German in the protocol.

## 1 -- `_harness.py`, `ProtectedArea`: a producer is protected with its directory (H13, H151)

Three sites (1a/1b/1c in the script). 1a adds the slot `producer_directories` to
`ProtectedArea.__slots__`; 1b fills it in `__init__` right after `self.producer_files = ...`: the
directory of every producer file, the checkout root excepted. It is a SLOT and not a local of
`verdict` because `_sandbox.protected_files` walks the slots -- the first cut (a loop inside
`verdict`) protected `tools/test_surface.json` while the measurement watch list did not hash it,
and `test_the_measurement_watch_list_is_the_area_the_gate_protects` went red in the patched copy
(protocol section 9). 1c, anchor (end of the kit-version branch, occurs once):
```
                "`kernel.hashing.kit_hash_inputs`, not from a list kept here."))
        return None, None
```
AFTER: between those two lines, a last check -- every directory in that slot is protected for the
SESSION agent:
```
        for directory in self.producer_directories:
            if under(path, directory):
                return SESSION_ONLY, ("this path lies in %s, the directory of a file gate 1 derives "
                                      "its protected area from. ..." % _shown(self.root, directory))
```
Why LAST: every narrower reason (canonical state, `.claude/`, the producer file itself, kit
content) answers first, so no refusal text a test already reads changes. Why the directory: the
producer set is measured per call (`decision_inputs`), and a NEW file beside the stamper -- its next
helper, a module it would import, gate 5's declaration -- is written where that set already points.
Measured for a `Write` payload on this tree (the producer set held `.claude/hooks/_harness.py`,
`team-kits/kernel/{__init__,hashing}.py`, `tools/bump_kit_version.py`): `tools/` is the one
directory this adds; the others, and a kit's `hooks/` that a shell payload loads, are protected
already. An implementer subagent still
writes `tools/` (the audience is `SESSION_ONLY`).

## 2 -- `_harness.py`, `payload()`: the kits' CR door (H69)

Anchor (the overflow refusal's last line, occurs once):
```
               "Remedy: split the call." % module.STDIN_LIMIT)
```
AFTER that line:
```
    eaten = module.eaten_in_flight(data)
    if eaten:
        refuse("This tool call could not be inspected: its command line carries a character its "
               "shell will never see (%s), ..." % eaten)
```
`module` is the kits' `_compat`, which these gates already borrow; `eaten_in_flight` is the rule the
kits' own payload door applies (a bare CR on the Bash rail).

## 3 -- `_harness.py`, `decision_inputs` docstring (H13)

BEFORE:
```
    WHAT IT DOES NOT REACH, named rather than implied: files, not directories. A module that
    `bump_kit_version.py` imports lazily inside a function this gate never calls is not loaded and
    therefore not protected, and neither is a NEW file placed beside it. Only `tools/` as a whole
    would cover those, and `tools/` is not derivable from anything this gate reads.
```
AFTER: the files are returned here, the verdict protects their directories; what stays open is a
module in a directory no producer lies in.

## 4 -- `CLAUDE.md`: the `tools/` paragraph

BEFORE:
```
**`tools/` ist damit nicht mehr pauschal frei** — geschützt ist die Datei, aus der abgeleitet wird,
nicht das Verzeichnis. Ein *neues* File neben ihr bleibt schreibbar; das steht als Loch in
`docs/POST_V2_WISHLIST.md`, nicht als Schutzbehauptung hier.
```
AFTER: `tools/` is protected for the session agent as a derivation (the producer's directory), a
new file beside the stamper and gate 5's declaration included; an implementer subagent writes there.

## 5 -- `tools/test_surface.json`, `_comment`: its own protection (H151)

BEFORE: `WHAT IT IS NOT: protected. ... Named as H151 with its chain rather than claimed away here;
...` -- AFTER: `WHO MAY WRITE IT: an implementer subagent, not the session agent. ...`

Sites 4 and 5 are in the patch rather than written now because both sentences are true only once
sites 1-3 are applied.

After applying: the lead amends `SR-0009`'s contract clause "every file the derivation itself reads,
the producer included" by "and the directory each of them lies in" -- the contract states the
protected area, and the patch widens it.
