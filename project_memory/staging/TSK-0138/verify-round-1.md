# Prüfbericht TSK-0138 — Runde 1 (kurzer Check nach dem Auftrag) — **FAIL**

Prüfer: `harness-verifier` (Opus, high). Als Text geliefert, vom Lead hierher gelegt (2026-09-11 17:4x, Uhr gelesen).
Gemessen in `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0138/verify/` (Kopie ohne `.git`, Rigs
`vrig.py`…`vrig4.py`, binär, verweigern fremde Arbeitsverzeichnisse). Keine Schreibvorgänge ins Repo/den Bestand.

## Blockierend

**B1 — `team-kits/kernel/approvals.py:2785-2791` + `:2916`: die Prägung schließt ein Bündel HALB und meldet „keine
Freigabe erteilt".** `batch_walk_blockers` (`:1010`) liest Lesbarkeit, Typ, Kettenposition, bestätigende Evidenz —
keine der drei Ungültigkeiten, auf die `_assert_the_list_covers` im Lauf verweigert (nicht gelistet / Revision bewegt
/ `listed_content_hash` bewegt). Prozess auf eigenem Pilot: `update(acceptance_criteria)` auf ein gelistetes Item,
dann PostToolUse → `rc=0 | no approval was created …`, Ergebnis `['archive/VERIFIED', 'active/TRIAGED',
'active/TRIAGED']`, APR-0001 existiert, Anfrage konsumiert; BUG-0002 TRIAGED **mit** approval_ref, BUG-0003 ohne. Der
Test `test_a_batch_that_moved_since_the_question_closes_nothing_at_all` bewegt nur die Evidenz. Eigener
Geschwistertest (Inhalt bewegt): `1 failed` (`StateError: no active item BUG-0001 … lives in the archive`).
**Minimalfix:** vor `_close_what_the_batch_lists` je gelistetem Item `_assert_the_list_covers(request, item)` —
alles oder nichts.

**B2 — `tools/close_measured_pass.py:50` + `:148`: der Beweis je Fehler kann ein Knoten sein, der den Fehler nicht
misst.** `NODE_RX` nimmt die Zelle `first: <knoten>` der Erhebung (der ERSTE Knoten des Laufs); die EVD-Zusammenfassung
sagt „measured for BUG-nnnn". Erste Bündelzeile: BUG-0002 (robocopy /MOVE) → EVD-0106 =
`test_board::test_a_hostile_field_cannot_add_an_element_or_an_attribute_to_the_page`; BUG-0074 → ein Knoten, dessen
Docstring „BUG-0071 end to end" sagt. **63 von 98** Zeilen zitieren Läufe mit mehr als einem Knoten (bis 19). Fix:
Knoten, die den Fehler NENNEN (BUG-0090 wörtlich), alle fahren; Zeilen ohne solchen Knoten zurückhalten.

## Punkt für Punkt
1 PASS (R1–R7 Verweigerungen nach Namen; P1–P4 Frage: wortgleich rc 0, umformuliert rc 2, Id getauscht rc 2, Id
entfernt rc 2). 2 FAIL (B1); sauberer Lauf, Evidenz-kippt, abgebrochene Prägung + Weiterschluss ohne zweite Frage
PASS; Nebenwirkung: Kernel-Sperre ttl 60 s. 3 PASS im Ergebnis, FAIL in der Begründung: echte Bestandskopie (227
EVD, 208 BUG) Anfrage 26,7 s, PostToolUse 27,8 s = 2,78 s je Fehler; Budget = `_kernel.DEFAULT_WINDOW_SECONDS` 560 s
− 1,5 s Reserve → **5,0 %**, nicht 47 %; Option 449 Zeichen, nicht 764. 4 PASS (`listed_items` → Kind-Liste:
`test_only_a_manifest_of_signed_item_records_reads_as_a_list` rot). 5 teilweise FAIL (B2): 8 zufällige Zeilen 8/8
grün, EVD-Felder stimmen; kein Nachweis auf fail (gemessen); BUG-0058s Knoten trägt, BUG-0074s Knoten misst
BUG-0071. 6 PASS (Bypass-Parameter: `DID NOT RAISE ApprovalError`). 7 PASS (test_staging_cli +8 Fixture, kleiner als
die Alternative). 8 PASS (Stempel -15 ×3, gate_approval.py `a44623dc…` ×3 = 07691ba; Prägepfad
`gate_approval.py:365 → approvals.mint → _close_what_the_batch_lists :2897`; 60 Testzeiger lösen auf; neue Suite 14
passed).

## Prosa
P3: die SKILL-Texte zitieren „DEC-0086's batch form", DEC-0086 sagt „der Kernel ändert sich nicht" → Revision (Lead).
P1/P2: die zwei Protokollzahlen.

## Nicht gemessen
Die Vollläufe des Umsetzers, ruff/validate, (g)-Zahlen, die übrigen 90 Wiederholungszeilen, Trefferquote der
Knoten-Zuordnung jenseits der Stichprobe, office-/research-SKILL über den Diff hinaus. Lesekosten: das Protokoll
ganz (281 Zeilen), rerun.log Kopf/Ende + Stichproben.

## Urteil
**FAIL.** Route für die zehn Klicks so nicht sicher: der erste Klick schlösse BUG-0002 auf einem fremden Knoten (B2),
und ein `update` zwischen Frage und Klick hinterlässt ein halb geschlossenes Bündel (B1). P3 blockiert das
Ausliefern.
