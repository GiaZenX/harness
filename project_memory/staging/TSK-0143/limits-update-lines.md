# List (ii) for the lead -- one `limits` sentence per gap that stays open, and the batches

Built by `_round-scratch/TSK-0143/make_limits_lines.py` (stream C, TSK-0143, rebuilt in rework 1)
and DRY-CHECKED against a COPY of the store (`_round-scratch/TSK-0143/store-copy`, made from
`project_memory/` on 2026-09-12 at 12:1x): **34 update lines and 6 batch lines, rc 0 every one,
0 refused**. Nothing here was executed against the real store -- that is the lead's to run.

## What changed in rework 1

* **BUG-0165 / H73 is GONE from this list: it is CLOSED.** Its own entry called (a) "die eine echte
  Lücke" and carried the closing direction, and that direction lands in this stream's own scope. It
  is built, red-first, with a naming test and EVD-0377. An exception for a gap the record itself
  calls closable here was the third state this repo does not have, and the verifier was right.
* **Real umlauts.** The 34 sentences are written with ä/ö/ü/ß and stored UTF-8. The user reads them
  inside the approval question, and the kernel prints real umlauts there; a transliterated
  "Waechter" was a sentence written for a terminal nobody looks at. Verified on the written bodies:
  `bug-0157-limits.json` begins `Ausf\xc3\xbchrens`. One sentence (BUG-0198) carries no umlaut
  because none of its words has one.
* **BUG-0102's sentence now says the true thing plainly**: this is a decision not to spend time,
  not a limit of the world, and it names the measured size of the job so the user can price it.

## Why these sentences

The exception question prints `id (limits)`, so the sentence in that field IS what the user reads
before deciding. Every one was read against the entry it belongs to and rewritten wherever a
non-developer would have stopped at a word -- "Shell", "Client", "Hook", "Interpreter", "Gate" are
gone; "Claude Code", "Codex", "Python", "git" stay, because those are names of programs the user
can look up and the sentence says what each one decides.

Sources: the 18 `nein` rows take their sentence from column six of
`staging/TSK-0140/order-3b-candidates.md`; the four re-filed gaps from the `limits` field of their
own item (BUG-0282, BUG-0284, BUG-0292, BUG-0293); the four LOCKED rows (BUG-0106, BUG-0235,
BUG-0283, BUG-0287) are written against the code each names, and the last two keep the sentence
their own `expected` field dictates; the eight REST rows are this stream's own measurements.

## BEFORE THE BATCHES (LEAD'S NOTE 2026-09-12 12:5x: the sentence below is WITHDRAWN -- the verifier measured `batch_walk_blockers(state, 'hole_exception', [OPEN ids]) -> []` in rounds 2 and 3, the builder does not defend it; NO transition is run before the batches): fourteen of these items are OPEN, and the edge starts at TRIAGED

Measured 2026-09-12 over `project_memory/bugs/active/`: `BUG-0251`, `BUG-0254`, `BUG-0255`,
`BUG-0257`, `BUG-0269`, `BUG-0270`, `BUG-0273`, `BUG-0282`, `BUG-0283`, `BUG-0284`, `BUG-0287`,
`BUG-0291`, `BUG-0292`, `BUG-0293` stand at **OPEN**; the rest are TRIAGED. The BUG automaton
reaches `ACCEPTED_EXCEPTION` from `TRIAGED` and from nowhere else -- the edge set is
`backlog_types.AUTOMATA["BUG"].allowed`, built in `team-kits/kernel/backlog_types.py:87` out of the
`terminal_from` ARGUMENT (which is not an attribute of the automaton, the verifier's F6). That is
deliberate: an exception is accepted for a gap somebody has LOOKED at, never for one nobody has
read yet. `request-approval` accepts the batch anyway (rc 0 above) -- the refusal comes when the
answer is APPLIED. So each of those fourteen needs a `transition <id> TRIAGED` before its batch is
asked, or the user's click lands on a refusal. That transition is the lead's: this item forbids me
to transition a BUG.

## The update lines

Each body is a file in this directory, so the German sentence keeps its punctuation and its
umlauts and no shell has to carry them. Run from the repository root:

```
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory update <BUG> \
  < project_memory/staging/TSK-0143/limits/<bug>-limits.json
```

| id | hole | body |
|---|---|---|
| BUG-0102 | H10 | `project_memory/staging/TSK-0143/limits/bug-0102-limits.json` |
| BUG-0106 | H14 | `project_memory/staging/TSK-0143/limits/bug-0106-limits.json` |
| BUG-0128 | H36 | `project_memory/staging/TSK-0143/limits/bug-0128-limits.json` |
| BUG-0141 | H49 | `project_memory/staging/TSK-0143/limits/bug-0141-limits.json` |
| BUG-0142 | H50 | `project_memory/staging/TSK-0143/limits/bug-0142-limits.json` |
| BUG-0145 | H53 | `project_memory/staging/TSK-0143/limits/bug-0145-limits.json` |
| BUG-0157 | H65 | `project_memory/staging/TSK-0143/limits/bug-0157-limits.json` |
| BUG-0166 | H74 | `project_memory/staging/TSK-0143/limits/bug-0166-limits.json` |
| BUG-0170 | H78 | `project_memory/staging/TSK-0143/limits/bug-0170-limits.json` |
| BUG-0177 | H85 | `project_memory/staging/TSK-0143/limits/bug-0177-limits.json` |
| BUG-0181 | H89 | `project_memory/staging/TSK-0143/limits/bug-0181-limits.json` |
| BUG-0198 | H114 | `project_memory/staging/TSK-0143/limits/bug-0198-limits.json` |
| BUG-0199 | H115 | `project_memory/staging/TSK-0143/limits/bug-0199-limits.json` |
| BUG-0206 | H122 | `project_memory/staging/TSK-0143/limits/bug-0206-limits.json` |
| BUG-0214 | H131 | `project_memory/staging/TSK-0143/limits/bug-0214-limits.json` |
| BUG-0224 | H141 | `project_memory/staging/TSK-0143/limits/bug-0224-limits.json` |
| BUG-0230 | H147 | `project_memory/staging/TSK-0143/limits/bug-0230-limits.json` |
| BUG-0234 | H152 | `project_memory/staging/TSK-0143/limits/bug-0234-limits.json` |
| BUG-0235 | H153 | `project_memory/staging/TSK-0143/limits/bug-0235-limits.json` |
| BUG-0241 | H159 | `project_memory/staging/TSK-0143/limits/bug-0241-limits.json` |
| BUG-0251 | H169 | `project_memory/staging/TSK-0143/limits/bug-0251-limits.json` |
| BUG-0254 | H172 | `project_memory/staging/TSK-0143/limits/bug-0254-limits.json` |
| BUG-0255 | H173 | `project_memory/staging/TSK-0143/limits/bug-0255-limits.json` |
| BUG-0257 | H175 | `project_memory/staging/TSK-0143/limits/bug-0257-limits.json` |
| BUG-0269 | H186 | `project_memory/staging/TSK-0143/limits/bug-0269-limits.json` |
| BUG-0270 | H187 | `project_memory/staging/TSK-0143/limits/bug-0270-limits.json` |
| BUG-0273 | H189 | `project_memory/staging/TSK-0143/limits/bug-0273-limits.json` |
| BUG-0282 | H198 | `project_memory/staging/TSK-0143/limits/bug-0282-limits.json` |
| BUG-0283 | H199 | `project_memory/staging/TSK-0143/limits/bug-0283-limits.json` |
| BUG-0284 | H200 | `project_memory/staging/TSK-0143/limits/bug-0284-limits.json` |
| BUG-0287 | H203 | `project_memory/staging/TSK-0143/limits/bug-0287-limits.json` |
| BUG-0291 | H207 | `project_memory/staging/TSK-0143/limits/bug-0291-limits.json` |
| BUG-0292 | H208 | `project_memory/staging/TSK-0143/limits/bug-0292-limits.json` |
| BUG-0293 | H209 | `project_memory/staging/TSK-0143/limits/bug-0293-limits.json` |

## The batches -- six questions, at most ten ids each

Grouped by what the USER is deciding about, not by the code's class: a question that mixes "the
manufacturer decides this" with "you cannot see it in a sentence" is one nobody can answer in a
single click.

### PROV-1 -- was der Hersteller entscheidet (Claude Code, Codex), 10

```
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory \
  request-approval hole_exception --batch BUG-0141 BUG-0142 BUG-0145 BUG-0170 BUG-0198 BUG-0199 BUG-0251 BUG-0254 BUG-0255 BUG-0293
```

### PROV-2 -- was außerhalb dieses Rechners liegt (Python, git, Apps, Ämter), 5

```
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory \
  request-approval hole_exception --batch BUG-0128 BUG-0181 BUG-0214 BUG-0230 BUG-0269
```

### TEXT-1 -- was man einem Satz nicht ansehen kann, 4

```
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory \
  request-approval hole_exception --batch BUG-0157 BUG-0224 BUG-0257 BUG-0273
```

### EXEC-1 -- was ein gestartetes Programm danach tut, 3

```
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory \
  request-approval hole_exception --batch BUG-0282 BUG-0284 BUG-0292
```

### GATE-1 -- Stellen in den Schutzdateien, die niemand hier ändern darf, 4

```
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory \
  request-approval hole_exception --batch BUG-0106 BUG-0235 BUG-0283 BUG-0287
```

These four are the rows the spawn message expected as before/after patches in list (i), and they
are NOT patches. Each one's own record says so: BUG-0106's `limits` states the remedy gate 3 prints
is one the session agent MUST be able to run, BUG-0235's two halves are a cheap prefilter and a
fail-closed over-refusal, BUG-0283 and BUG-0287 both carry `expected: ... until applied, an
exception with this sentence` and the sentence itself. What each would need is a BEHAVIOUR change
in a gate -- and that is not something a user applies blind from a shell: it needs a red-first
measurement inside the file, and no role of this round may write those files.

### REST-1 -- was Strom C dieser Runde gemessen und NICHT geschlossen hat, 8

```
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory \
  request-approval hole_exception --batch BUG-0102 BUG-0166 BUG-0177 BUG-0206 BUG-0234 BUG-0241 BUG-0270 BUG-0291
```

Every sentence in this batch carries the measurement stream C took for it; the protocol has the row
behind each. Two moved on this round and their sentence says so instead of repeating the old one:
`BUG-0241` now has its path pointers judged (one of its three unread kinds closed, red-first), and
`BUG-0291` is down to a single site, which is patch site 7. `BUG-0102` is the one whose sentence
names a CHOICE rather than a limit, and the size of the job behind it, so the user decides whether
to buy it.

## What is NOT in this list, and why

* Every gap stream C closed carries an EVD instead -- they belong in the VERIFICATION batch.
* `BUG-0165` was in this list in round 1 and is not any more: it is closed (EVD-0377).
