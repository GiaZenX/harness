# Prüfbericht TSK-0149 (PR-0012, Order 4, Zielrunde) — Runde 2 — **FAIL (ein Bezeichner: test_hooks.py:19546)**

Prüfer: `harness-verifier` (Opus, high), 12 min, +42 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-13 08:15, Uhr gelesen).

# Prüfbericht TSK-0149, Runde 2 (Nacharbeit F1–F5) — Urteil: **FAIL**, ein einziger, benannter Punkt

Frischer Schnappschuss `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0149/verify2/tree` (robocopy ohne `.git`), drei neu gescaffoldete Piloten aus diesem Baum, Rig mit cwd-Verweigerung und Binär-I/O. Kopie deckungsgleich mit dem Repo (`m_treediff.py`: einzige Abweichung `project_memory/staging/generation-6/capture_dec_order4_retrospective.py`, nach meinem Schnappschuss geschrieben; die zwei „DIFFERENT" sind mein eigener `generate-index`-Lauf). Repo nicht beschrieben.

## F1 — behoben, am Mechanismus, und das Paar ist das richtige

`tools/test_shortening_net.py:1324` (`_tool_guard`, liest den AST: `if data.get("tool_name") not in <tools>: sys.exit(0)/return`, Komparator Tupel **oder** Modulkonstante — eine Definition, keine Aufzählung) und `:1404` (`_reach_of`).

Antworten des Lesers gegen meine Marker-Messung:

```
_refuse_untrusted_bundle                        reach={'PreToolUse': {'Task','Agent'}}  codex=False
handle_pre_tool_use                             reach={'PreToolUse': {'Task','Agent'}}  codex=False
_refuse_a_classification_the_judged_role_wrote  reach={'PreToolUse': None}              codex=True
main                                            reach=None                              codex=True
```

Marker am frischen Piloten unverändert: `entered False / False / True` (Bash, Bash-Evidenzzeile, Agent), `gate_dispatch.py` Hash 6a5bc651… wie in Runde 1 — das Verhalten wurde nicht angefasst, nur der Leser nachgezogen. Dass `handle_pre_tool_use` als Symbol vor der Wache doch läuft, steht im Docstring als **bewusst alarmierende Richtung** ausgeschrieben, mit dem Satz „house rule 3 forbids [the reassuring one] as firmly" — eine getroffene und begründete Wahl, keine versteckte Über-Verweigerung.

Dokument `docs/reviews/phase0-disposition.md:747`: „**5 der 36** … (4, 15, 41, 54, 56)", mit dem Absatz darüber, dass die Zahl kurz auf 3 stand, warum das falsch war, und dass sie aus dem Leser kommt und nicht aus dem Absatz.

Die drei Mutationen, jede auf dem Knoten, der sie besitzt:

| Mutation | Zählknoten | Leserknoten |
|---|---|---|
| Baseline | 1 passed | 1 passed (Boden: 1 passed) |
| DEC-0107-Registrierung entfernt | **grün** | **1 failed** (`assert False`, `test_shortening_net.py:1627`) |
| Wache aus `handle_pre_tool_use` entfernt | **1 failed** („does not state that 3 … (15, 41, 56)") | 1 failed |
| „event only" (`_tool_guard` liest nichts) | **1 failed** (gleiche 3) | 1 failed |

Ja, das ist das richtige Paar: die entfernte Registrierung ändert die Zahl **nicht** (die Wache schloss die beiden Zeilen ohnehin aus), also kann nur der Leserknoten sie sehen — genau dafür muss er existieren. Die beiden Mutationen, die die Zahl wirklich verschieben würden, landen auf dem Zählknoten. Wiederhergestellt: 3 passed.

## F2 — als Loch geschrieben, Hygiene grün und in beide Richtungen rot

`team-kits/{dev,office,research}-team/hooks/gate_write_scope.py:1616`: `H219` (`BUG-0304`) mit **drei Mechanismen** (effektives Kommandowort hinter Präfix/Wrapper, Eingabeumleitung in einen Interpreter, Datenfluss über eine Substitution) und den fünf gemessenen Schreibweisen, ausdrücklich „None of them is a regression of the rule below". `BUG-0304` steht mit `hole_number: H219`, `status: OPEN`; die Löcherlisten-Zeile 2522 ist eine reine Ableitung des Items (der ganze Diff der Datei ist Reindex-Form: Links dort, wo eine Prosadatei existiert, H170-Status aus dem Item, H218/H219 neu) — inhaltlich also keine Handschrift.

`docs/holes/H214.md` und `H219.md` existieren nicht, und das ist zulässig:

```
baseline (no H214.md, no H219.md)          -> 1 passed
(a) prose file H214.md added, row unlinked -> 1 failed  "these prose files exist while their row does not link at them: H214"
(b) row links at an absent prose file      -> 1 failed  "these index rows link at a prose file that does not exist: H219"
restored                                   -> 1 passed
```

`tools/test_repo_hygiene.py::test_every_hole_is_one_index_row_one_prose_file_and_one_item` — grün ohne Akte, rot in beiden Richtungen. Der Knoten kann scheitern.

Verhalten von `gate_write_scope` nach der Docstring-Runde unverändert: alle 24 Sonden-Zeilen Zeile für Zeile identisch zu Runde 1 (neun Verweigerungen rc 2, `bash $(which ci.sh)` und die Evidenzzeile rc 0, die fünf H219-Formen rc 0). Die drei Dateien byte-identisch (`11e96221…` x3).

## F3 — korrigiert und ehrlich

`lead-lines.md` §5: „14 rows … 27 active BUG items, so 13 are NOT in the rollup" — deckt sich mit meiner Messung. BUG-0242 steht in der Liste, ist als **per Klick schließbar** ausgeschrieben, mit dem Unterschied Builder/Lead und der ehrlichen Alternative (Ausnahme- statt Verifikationsklick, falls der Lead die Nichtentfernung als unerfülltes Kriterium liest). Neue Batch-Zeile „M (this order) | BUG-0242 | EVD-0448" in §1.

Read-only nachgebaut (`approvals.batch_walk_blockers`, `batch_closing_types('verification') == ['BUG']`):

```
distinct ids in the batch lines: 12
  A 2 / A+seam 1 / B 6 / C 2 / M 1 / deferred 1  -> jeweils 0 refused
TOTAL refused: 0      BATCH_LIMIT respected: True
```

## F4 — Zahl und Zeiger weg

`tools/test_hooks.py`: „THIRTEEN MEASUREMENTS … five everyday lines" ist ersetzt durch die Begründung „that went stale the moment a line was appended (verifier round 1 of TSK-0149, F4)"; „The last two are …" ist zu „The everyday lines are the ones the same reading could …" geworden — kein Positionszeiger mehr.

## F5 — zwei von drei sauber, der dritte tauscht eine falsche Zahl gegen einen **falschen Zeiger** (NEUER BEFUND, blockierend)

* `team-kits/kernel/state.py:2009` — „every EVD entry of the table below … however many there are, which is why this sentence no longer counts them" ✔
* `tools/test_hooks.py:2669-2674` — die 24/21/22 sind weg, mit der Begründung, dass drei Leser drei Antworten gaben (u. a. meine 25/27/22) ✔
* **`tools/test_hooks.py:19545-19547`** — „every shipped kit entry states a `timeout` — that is a property and it is held by `test_every_shipped_hook_of_this_kit_reaches_the_deadline_that_arms_it`, not by a count in this sentence."

Gemessen, Mutation in der Richtung, die der Satz verneint (`timeout: 120` aus dem ersten `PreToolUse`-Eintrag von `team-kits/dev-team/settings/settings.json` entfernt, danach byte-identisch wiederhergestellt):

```
test_every_shipped_hook_of_this_kit_reaches_the_deadline_that_arms_it -> 3 passed
test_every_registration_names_a_window_its_gate_can_answer_inside     -> 1 failed
```

Der genannte Knoten registriert seine Haken **selbst** ohne Fenster und prüft, dass jeder refüsiert — er hält „jeder ausgelieferte Haken ist scharfgestellt", nicht „jeder ausgelieferte **Eintrag** nennt ein `timeout`". Die Eigenschaft, die der Satz behauptet, hält `tools/test_hooks.py:3221::test_every_registration_names_a_window_its_gate_can_answer_inside` (liest die ausgelieferten Registrierungen und meldet den Eintrag ohne Fenster). Damit ist die Reparatur von F5 in genau die teurere Hälfte der Hausregel gerutscht: ein benannter Test, der für sein Thema nicht rot werden kann.

**Minimalfix:** in Zeile 19546 den Namen auf `test_every_registration_names_a_window_its_gate_can_answer_inside` ändern. Ein Bezeichner, keine Codeänderung, `tools/` geht in keinen Kit-Hash ein — also **kein dritter Stempel und kein Lauf** nötig; die Nachprüfung ist ein `grep` plus die eine Mutation oben.

## Abschlussmessungen

Stempel **2026.09.13-3**, zweiter Aufruf `unchanged` x3, die drei Inhalts-Hashes (`692a218d…`, `2cad2ccc…`, `5833924

0…`) sind die neu berechneten. `ruff check tools team-kits user` grün. `tools/validate.py` grün. `gen_known_holes.py --check` „up to date (3 capabilities)". `generate-index` → nur `generated_at` weicht ab, Index = Store. Spiegel: von 31 mehrfach ausgelieferten Hook-Dateien weichen nur `format_on_write.py` und `session_status.py` ab, beide mit Grund in `KIT_SPECIFIC_HOOKS`.

**Nicht gemessen in dieser Runde:** kein dritter Volllauf und keine Gate-Suite (DEC-0050, wie beauftragt); die sechs Lese-Selektionen aus M2s Protokoll habe ich nicht nachgefahren, sondern nur die von euch benannten Knoten und meine eigenen Mutationen; `tools/test_context_budget.py` und die Decken habe ich nach dem -3-Stempel nicht erneut gefahren (nur `validate.py`, das die Decke hart erzwingt, ist grün).

## Urteil

**FAIL** mit **einem** blockierenden Punkt: `tools/test_hooks.py:19546` nennt für die Eigenschaft „jeder ausgelieferte Eintrag nennt ein `timeout`" einen Test, der bei ihrer Verletzung grün bleibt (gemessen: 3 passed vs. 1 failed am richtigen Knoten). Ein Bezeichner Fix, ohne Stempel, ohne Lauf. F1–F4 sind sauber behoben und gegen Mutationen gehalten; F2 ist als `BUG-0304`/`H219` korrekt als benannter Rest geschrieben statt weggeredet. Nach der Zeigerkorrektur ist aus meiner Sicht nichts mehr offen.

Pfade: `C:\Offline Repos\AgentAndSkills\tools\test_hooks.py`, `C:\Offline Repos\AgentAndSkills\tools\test_shortening_net.py`, `C:\Offline Repos\AgentAndSkills\team-kits\dev-team\hooks\gate_write_scope.py`, `C:\Offline Repos\AgentAndSkills\docs\reviews\phase0-disposition.md`, `C:\Offline Repos\AgentAndSkills\project_memory\staging\TSK-0149\lead-lines.md`. Meine Sonden dieser Runde: `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0149\verify2\` (`m_f1.py`, `m_f1mut.py`, `m_f2.py`, `m_f5point.py`, `m_close.py`, `m_reach.py`, `m_e2.py`, `m_treediff.py`, `m_mirrors.py`).