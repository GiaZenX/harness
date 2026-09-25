# TSK-0151 -- lead finding before the verifier (2026-09-25 17:40, clock read)

## F1 (blocking): the Codex top rung is unreachable -- contradicts DEC-0114 (4) and the user's answer

- DEC-0114 (4): "the Codex top stays gpt-6-astra". The user, asked separately at 15:07 (round log
  `staging/generation-6-streams.md`): **"Astra bleibt oben"**.
- The build (protocol.md section on the Claude-side form) set `top: opus` in all three kit ladders and in
  `ladder.yaml`, and removed the office-developer's fable exception. Consequence the builder itself reports:
  on Codex no ladder reaches `gpt-6-astra` any more.
- The builder rejected `tiers.claude.fable: opus` for three measured reasons (spawn_model_refusal compares the
  model to the rung name; `_reference_rungs`; the rung step resets effort). Those reasons stand; they reject that
  FORM, not the requirement.
- REQUIRED: the ladder answer is provider-aware at the top -- on Claude no class/pin/escalation reaches Fable
  (BUG-0306 AC-2 stays), on Codex the architecture class and the escalation still reach the top rung
  (gpt-6-astra) exactly as before 8677bd2 (dev/research: build climbs to top; office: only the office-developer).
  Choose the smallest form that the kernel can answer per provider (e.g. a per-provider `top` in the ladder, or
  a provider cap the kernel applies) and say in the protocol which form and why; measure through
  `kernel.cli ladder` answers for BOTH providers per kit; a test naming BUG-0306 that is red on the current tree
  for the Codex half and green after.

## Not findings (recorded so the verifier does not re-open them)

- BUG-0307 AC-1 says "one task per runner"; DEC-0098 (2) wants two Codex Automations. The builder followed the
  decision -- correct; the AC wording was the lead's error.
- The two red full-run nodes were the lead's: `radar/routine.json` named the old task (reworded, green 17:3x) and
  the CRLF proof file (converted to LF, green). The hole index was reindexed by the lead (210 holes).
- `test_gates.py` H138 / H155 name tests that were already missing on 8677bd2 -> order 6 (archive door), not
  this order.
