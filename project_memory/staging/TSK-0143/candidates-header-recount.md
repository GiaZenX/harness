# List (iii) -- the header of `order-3b-candidates.md`, counted from its own rows

The verifier's G1: the header of `project_memory/staging/TSK-0140/order-3b-candidates.md` states
**105 / ja 79**, and the table under it carries **121 / ja 95**. Measured 2026-09-12 over the file
itself (`_round-scratch/TSK-0143`, one reader over every line matching `^| H<n> |`):

| section heading | rows |
|---|---|
| `## OVERREF (10)` | 10 |
| `## ENUM (7)` | 7 |
| `## PROV (12)` | 12 |
| `## INSTR (23)` | 23 |
| `## DESIGN (53)` | 53 |
| `## Zuerst: die CLOSE-Loecher, die Auftrag 3 nicht mehr erreicht hat (16)` | 16 |
| **total** | **121** |

121 distinct `H` numbers, no id twice. By verdict: **ja 95, gesperrt 8, nein 18**.

WHERE THE DIFFERENCE COMES FROM, so the correction is not just a number swap: the header was
written over the five CLASS sections (10 + 7 + 12 + 23 + 53 = 105, of which ja 79) and the sixth
section -- the 16 CLOSE holes order 3 did not reach, every one of them `ja` -- was appended later
without the header following. 105 + 16 = 121 and 79 + 16 = 95, which is exactly the pair the
verifier measured. Each section's own heading count is right; only the total aged.

## The line to replace

`project_memory/staging/TSK-0140/order-3b-candidates.md`, the paragraph directly above `## OVERREF`.

BEFORE

```
**105 gaps: ja 79, gesperrt 8, nein 18.** Order 3b attempts every `ja`; the `gesperrt` rows are the user's shell; only the `nein` rows are candidates for an accepted exception at all.
```

AFTER

```
**121 gaps: ja 95, gesperrt 8, nein 18** -- the five class sections (105, ja 79) plus the 16 CLOSE holes order 3 did not reach, every one of them `ja`. Order 3b attempts every `ja`; the `gesperrt` rows are the user's shell; only the `nein` rows are candidates for an accepted exception at all. Counted from the rows of this file rather than carried forward: the first figure aged the moment the sixth section was appended (stream C, TSK-0143).
```

## Why this is a list and not a fix I applied

`project_memory/staging/TSK-0140/` lies in this item's `forbidden_scope` (`project_memory/**`, with
`staging/TSK-0143/` the single exception), so the correction is handed over rather than made. The
generator named in that file's own header (`_round-scratch/TSK-0140/make_order_3b.py`) writes the
paragraph; whoever re-runs it should take the count from the rows, not from a constant.
