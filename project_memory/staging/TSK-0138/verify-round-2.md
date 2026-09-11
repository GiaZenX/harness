# Prüfbericht TSK-0138 — Runde 2 — **FAIL (eng begrenzt; vier von fünf Punkten PASS)**

Prüfer: `harness-verifier` (Opus, high). Als Text geliefert, vom Lead hierher gelegt (2026-09-11 18:4x, Uhr gelesen).
Eigene Kopie `…/verify/repo2` (ohne `.git`), Rig `vrig5.py`, eigenes scaffoldetes Pilotprojekt, echter
`_gate.py gate_approval.py`-Prozess. Keine Schreibvorgänge ins Repo/den Bestand.

## B1 — Bündel-Prägung: PASS
`approvals.py:1014` trägt die fünfte Frage als Aufruf von `_assert_the_list_covers` (dieselbe Funktion wie im Lauf);
`mint` reicht die unterschriebene Liste durch (`:2815`). Vier Ungültigkeiten gegen den echten Haken: A Inhalt
bewegt → `rc=0 | no approval was created`, 3× TRIAGED/ref=null, keine APR, Anfrage offen; B zweites `update` auf ein
gehashtes Feld → dito; E ein überlappendes Bündel hat ein Item vorher archiviert → nichts läuft, die anderen
unberührt; D sauberer Lauf → 3× archive/VERIFIED/APR-0002. Rot-zuerst nachgestellt (Fix am Aufrufer entfernt →
`1 failed`), zurückgesetzt, byte-identisch.

## B2 — `nodes_naming`: PASS in der Mechanik, ein benannter Rest im Ergebnis
(a) fünf zufällige benannte Fehler: eigene `ast`-Lesung = exakt dieselben Knotenmengen; drei Assertions gelesen
(BUG-0064/0063/0047) — messen den Defekt. (b) fünf zufällige Zurückgehaltene: eigener grep 0 Treffer. (c)
parametrize-Fall-Id wird gefunden. (d) run_command/summary tragen alle k Knoten.
**Rest:** „ein Test nennt die Id" lässt eine Nebenbemerkung zu. **14 der 45** hängen an genau einem Knoten; alle 14
Nennzeilen gelesen: zwölf sind das Thema des Tests, **zwei nicht** — **BUG-0050** (einziger Knoten
`test_a_warning_is_recorded_as_a_warning_and_not_as_a_block`, Nennzeile „…the reading BUG-0050 was written from.
Nothing was caught") und **BUG-0044** (historische Beiläufigkeit „(BUG-0044/BUG-0041)"). BUG-0050 steht in Zeile 4,
BUG-0044 in Zeile 3. Minimalfix: die zwei Ids aus den Zeilen nehmen. Dieselbe Klasse: BUG-0074 (zurückgehalten)
nur über „(BUG-0074's lesson, one command over)" gefunden.

## P1–P3 — PASS
5,0 % / 449 Zeichen / Sperr-TTL als Grund (`state.py:428 lock_ttl 60.0`, `lock.py:127-133 LockLost`); DEC-0100 aktiv,
DEC-0086 archiviert, fünf Nennungen. Neue Messung gegen eine Kopie des echten Bestands (283 Evidenzen): Anfrage 31,1
s, PostToolUse **32,3 s = 3,23 s je Fehler = 54 % der TTL** (das Protokoll sagt 28,0 s, eine Runde alt) — nicht
blockierend; der Kommentar sagt zu Recht, die Messung sei zu wiederholen.

## Neuer Fund `tools/test_presets.py` — PASS (minimal und ehrlich; zweite Bereichsüberschreitung, Abnahme Lead).
## Stempel/Spiegel — PASS (`2026.09.11-17` ×3 unchanged; `gate_approval.py` `a44623dc…` ×3 = 07691ba).
## Suiten nachgerechnet: test_approvals_dispatch 212 · test_close_measured_pass 12 · test_presets 34.

## Nicht gemessen
Die übrigen zwölf Läufe aus §5, ruff/validate, (g)-Zahlen; 44 der 49 Zeilen nicht im Detail (nur die 14
Einknoten-Zeilen vollständig); `nodes_naming` liest nur modulweite `def test_*` (keine Test-Klassen im Repo — heute
kein Loch, eine ungeprüfte Annahme).

## Die eine Frage
Vier der fünf Klicks sind sicher; der dritte und vierte nicht, solange BUG-0044 und BUG-0050 in ihren Zeilen stehen.
**Blockierend:** die zwei Ids aus Zeilen 3/4 nehmen. **Löcherliste:** die Regel „ein Test nennt die Id" deckt eine
beiläufige Nennung wie eine messende (Mechanismus). **Prosa:** 28,0 s → 32,3 s.
