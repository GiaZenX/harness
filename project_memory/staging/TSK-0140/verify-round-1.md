# Prüfbericht TSK-0140 (PR-0012, Order 3) — Runde 1 — **FAIL (ein Klick-Blocker, eine AC-5-Zahl, Rest Prosa)**

Prüfer: `harness-verifier` (Opus, high). Als Text geliefert, vom Lead hierher gelegt (2026-09-12 09:1x, Uhr gelesen).
Eigene Kopie `…\TSK-0140\verify\` (Rig nur eigenes Verzeichnis, Binär-IO), eigener Pilot + zweiter über einer Kopie
des echten Stores. Keine Schreibzugriffe ins Repo, kein Volllauf.

## Befunde
**F1** `kernel/cli.py:1789-1805` — der neue Zweig ist für den im Kommentar genannten Fall unerreichbar (`hole_exception
BUG-0005` → rc 2 aus `:1756`; nur mit `--batch` dazu feuert er, und die Remedy lässt die übergebene Liste fallen;
„closes" ist das falsche Verb). **F2 — blockiert OVERREF-1 und DESIGN-1:** BUG-0105/0106/0107/0110/0111/0115
(H13/14/15/18/19/23) tragen **denselben** `limits`-Satz, der auf andere Einträge verweist; 128 Löcher → 123
verschiedene Bounds, genau diese Sechsergruppe identisch. **F3** `exception-batches.md` Spalten `hole | bug | sev |
bound` statt `id | mechanism | why unclosable | bound`. **F4** nach allen 15 Klicks bleibt `stock lies upward: 7`,
nicht 0 (52 − 107 − 6): sechs nicht erreichte CLOSE-Löcher + **BUG-0067, der heute schließbar ist**
(`names_the_item` True ×3). **F5** Pin-Journal sagt „18 CHANGED", gemessen 17 (append-only). **F6** `CLAUDE.md:182-
183` „kein Kit, keine Kit-Hooks" — registriert ist das Kit-`gate_approval.py` zweimal. **F7** „four gates" in
`test_gates.py:4618/:4689` (Präsens) und in den gesperrten `harness-lead.md:33` / `_harness.py:8`. **F8** `limits`
nicht typgeprüft (`7`, Liste, Dict → rc 0, Option `BUG-0011 (7)`). **F9** Kosten: Ausnahme-Mint 0,35–0,44 s/Eintrag;
Verifikations-Batch **34,7 s für sechs** (~5,8 s/Eintrag → bei 10 nahe der 60-s-TTL). **F10** H190-Rückstufung halb
ehrlich (zweite Form = Beide-Enden-Draht, gebautes Muster). **F11** `approval_card` sagt nach dem Klick „für keinen
Vorgang" (listengebundene Arten).

## Negative Befunde — gemessen
Batch-Route als Prozesse (Pilot + echter Store): wortgleich → alle Items ACCEPTED_EXCEPTION, archiviert, `limits`
erhalten (4/4, 10/10 ×2); getauschte Id → rc 2; ohne `limits` → rc 1 namentlich, Remedy funktioniert; `limits` oder
`severity` zwischen Frage und Klick geändert → nichts schließt; Loch- und Nicht-Lochitem beide angenommen; 11 Ids → rc
2, Doppel-Id rc 1, Fremdtyp rc 1. Zwei eigene Mutationen rot (Klettern entfernt; content_question fixiert). Drei
Rot-Zeilen nachgestellt + eigenes Gegenende (sechstes Gate ohne Tabellenzeile → rot; eigener Fehlgriff `tools/hashing.py`
offen gesagt). Sechs Schließungen nennen ihre Id am erklärten Ort, Assertions messen die Lücke. Die drei älteren Roten
grün; Pin-Sweep 17 = 17, drei Stichproben echte Textänderungen; BUG-0067 Git Bash 1 passed / WSL 1 skipped mit
Begründung. AC-5: unchanged ×3, ruff/validate grün, Index = Store; `_routine.py` ×3 identisch. H182-Patch wendet sauber
an (kein roter Test ohne ihn — die Notiz sagt es). Die 16 nicht erreichten CLOSE-Löcher in keiner Ausnahmeliste; H190 in
ENUM-1; fünf Stichproben quer durch die Klassen: Bounds gemessen und heute wahr (H188 live rc 2).

## Nicht gemessen
Kein Volllauf; ob der echte Client eine ~1.870-Zeichen-Option wortgleich spiegelt (falls gekürzt: nichts mintet); 12
der 14 Listen nicht einzeln als Prozess; SDK-Mint-Strecke; Reindex nach den Klicks; H169s Provider-Messung.

## Verdikt
**FAIL.** Blockierend nur F2 (zwei von fünfzehn Fragen). F4 blockiert die AC-5-Zahl. Rest Prosa/benannte Reste.
Mechanisch sind alle fünfzehn Klicks sicher; inhaltlich dreizehn.
