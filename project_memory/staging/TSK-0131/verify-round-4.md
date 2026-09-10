# TSK-0131 / PR-0008 — Prüfbericht Runde 4 (harness-verifier, Abschlussrunde)

Gemessen 2026-09-06 **19:02:59 bis 19:47:15** (Uhr gelesen, `date`), Opus 5 high (`DEC-0081`).
Neuer Prüfer (der Vorgänger wurde vom Nutzer pausiert); nichts aus den Vorberichten übernommen,
ohne es selbst zu messen.

**Arbeitsweise.** Frische Kopie des Arbeitsbaums **ohne** `.git`-Zeigerdatei unter
`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0131/verify/r4/tree` (robocopy, 2188 Dateien).
Eigenes Rig `…/verify/r4/r4rig.py` — es **verweigert den Lauf außerhalb seines eigenen
Verzeichnisses** und öffnet **jede** Datei binär mit ausdrücklicher Kodierung (`DEC-0070`; die
Verweigerung ist gemessen: aus dem Elternverzeichnis gestartet rc 1, „refuses to run outside its own
directory"). Für `tools/test_migrate.py` (dessen V1-Fixture die Repo-Historie liest) hat das Rig
einen **eigenen Klon** `…/verify/r4/gitmirror` (`git clone --no-checkout --no-local` aus dem
Arbeitsbaum, 52 MB) — der Hauptcheckout wird dabei weder gelesen-geschrieben noch verändert.
In das Repo und in den Arbeitsbaum wurde **nichts** geschrieben außer dieser Datei.

**Eine Messgrenze vorweg, gemessen statt behauptet:** Gate 1 verweigert **jeder** Rolle jede
Befehlszeile, die den Hauptstore nennt — auch der Lese-Route `kernel.cli --root <Hauptstore>
validate` (rc 2, Text: „no tool call in this repo may write …/project_memory"). Der Validator-Lauf
(d) wurde deshalb gegen eine **binäre Kopie** des Hauptstores gefahren (`copy_store.py`, 1532
Dateien, nur lesend auf der Quelle).

---

## Teil 1 — die beiden Befunde der Runde 3

### N3-B1 (Quittungsfilter) — **GESCHLOSSEN**, in beide Richtungen selbst nachgemessen

`tools/test_migrate.py:3908` erkennt die Quittung jetzt an ihrer **Identität**: dem `source`-Präfix,
das `migrate._receipt_fields` selbst schreibt (`_receipt_source_prefix`, :3867). Aus der laufenden
Funktion gelesen:

```
SOURCE : 'spec II.10; plan digest DIGEST'      PREFIX : 'spec II.10; plan digest '
```

Mutationen in meinem Rig (`r4rig.log`), jede eine einzige Änderung, jede mit `timeout`:

```
BASELINE (neuer Test + eine alte Zusicherungsstelle)   GREEN  2 passed in 14.48s
M1 Filter fällt auf den TYP zurück (Defekt der R3)     RED    1 failed, 141 passed in 472.97s
       FAILED tools/test_migrate.py::test_the_receipt_filter_drops_the_receipt_and_nothing_else
M2 Präfix aus einer getippten Zeichenkette             RED    2 failed in 13.69s  (beide Richtungen)
M3 Identität am FALSCHEN Feld (`title` statt `source`) RED    2 failed in 13.83s
```

M1 lief über die **ganze** Datei: der Rückfall wird von **genau einem** Test gefangen, dem neuen,
und von keinem anderen — die Behauptung (a) des Auftrags ist damit gemessen, nicht geglaubt.

### N3-B2 (Zeiger-Hälfte der Leiter) — **im Kern geschlossen**, eine Achse trägt nicht

`tools/test_review_procedure.py:1290` erkennt den Absatz jetzt an dem, was er trägt. Mit dem
**laufenden** Leser über den **Baum** gemessen (`ladder_probe.py`, nicht an einem Zitat):

```
rungs: fable, haiku, lead, light, opus, sonnet, worker · effort field: effort
effort values: high, low, max, medium, xhigh
dev-team units=35 qualifying=1 · research-team units=35 qualifying=1 · office-team units=27 qualifying=0
```

Mutationen:

```
L0 Baseline                                        GREEN  1 passed in 2.36s
L1 Absatz verliert die SPROSSE als Wert            RED    1 failed in 2.56s
L3 ein ZWEITER Regel-Absatz kommt dazu             RED    1 failed in 2.61s
L2 Absatz verliert die EFFORT-Achse                GREEN  1 passed in 7.46s   ← siehe N4-2
```

Die Klasse, die Runde 3 gemeldet hat (jede beliebige Erwähnung des Wortes „ladder" genügt), ist
damit weg: das Löschen des echten Absatzes ist rot. Die **zweite** Achse ist es nicht — Befund N4-2.

---

## Teil 2 — neue Befunde (KEINE Reste der Runde 3; `DEC-0088` (c): Klasse „Prosa gegen Code")

### N4-1 — der Quittungsfilter darf **alles** über die Quittung verschlucken, und kein Test merkt es

`tools/test_migrate.py:3924–3926` behauptet:

> „THIS FILTER IS NARROW, and now really: it drops the carrier warning for the receipts of this run
> **and nothing else. Any other finding … comes through**, and the claim is held by
> `tools/test_migrate.py::test_the_receipt_filter_drops_the_receipt_and_nothing_else`."

Der genannte Test liest **nur** Meldungen, die `without a carrier` enthalten
(`tools/test_migrate.py:3902`). Also hält er die Verengung **auf das Item**, nicht die **auf die
Meldung**. Gemessene Zeile — Mutation „der Filter verwirft **jeden** Befund über die Quittung"
(`if one["item"] not in receipts`), über die ganze Datei:

```
M4 filter drops EVERY finding about the receipt     GREEN  rc=0  142 passed in 464.50s (0:07:44)
```

Kein einziger Test wird rot. Damit steht die Hälfte „and nothing else" als Prosa da — genau die
Konstruktion, wegen der Runde 3 blockiert hat, eine Ebene weiter innen. (Nebenbefund derselben
Zeile, mechanisch und nicht gemessen-nötig: das Präfix ist **lauf-unabhängig**, also schweigt der
Filter auch für die Quittung eines **anderen** Laufs — „of this run" ist nicht das, was der Code
unterscheidet.)

**Schwere:** niedrig (testseitig, keine Angriffskette; der ausgelieferte Filter ist korrekt).
**Minimaler Fix:** eine Zeile im Test — dem Store neben der Quittung einen **zweiten** Befund über
die Quittung geben und zusichern, dass er durchkommt; **oder** den Satz auf das zurücknehmen, was
gemessen wird.

### N4-2 — die Effort-Achse des Leiter-Absatzes darf aus dem **Nachbar-Aufzählungspunkt** kommen

`tools/test_review_procedure.py:1392` behauptet:

> „the constitution must hold exactly ONE **bold paragraph** that states both axes — a rung of
> `team-kits/model_tiers.yaml` as a value, and that file's effort field."

Gebaut ist `_states_the_scaling_rule` (:1290) über `_lead_in_units` (:838), und eine „unit" ist
**nicht** ein Absatz, sondern die **Spanne von einem Fett-Lead-in bis zum nächsten** — hier zehn
Zeilen, die drei weitere Aufzählungspunkte einschließen. Gemessen (`ladder_probe2.py`, laufender
Leser):

```
== wie ausgeliefert: qualifying units = 1
   lead-in : - **Effort:** all `high`. … Escalation
   unit lines: 10
   `effort` gefunden in Zeile 0  (der Leiter-Punkt)
   `effort` gefunden in Zeile 4: - The scaffold stamps Claude `model:`/`effort:` frontmatter …
== Effort-Achse aus dem Leiter-Absatz entfernt: qualifying units = 1
   `effort` gefunden in Zeile 4  ← der Nachbarpunkt trägt die Achse jetzt allein
```

und der Wächter dazu: `L2 … GREEN 1 passed in 7.46s`
(`team-kits/dev-team/constitution/AGENTS.md:374`).

Damit ist die Protokollzeile N20 (b) — „**Effort-Achse weg → rot**" — in der Form, in der sie
dasteht, **nicht** reproduzierbar: rot wird sie erst mit einer **zweiten** Änderung, die den
Nachbarpunkt zu einem eigenen Fett-Lead-in macht (so steht sie in `redfirst.py`, Fall
`ladder-paragraph-loses-the-effort-axis`, zwei Edits). Das Protokoll nennt sie als eine Achse.

**Folge für die Naht (N18):** ein G5-2-Absatz, der die Sprosse trägt, aber die Effort-Achse **nicht**
nennt, bleibt grün, solange irgendein Punkt in derselben Spanne das Wort `effort` führt — der
Wächter schützt die Naht schwächer, als N18 zusagt.

**Schwere:** niedrig (testseitig, keine Angriffskette). **Minimaler Fix:** die Effort-Achse im
**Lead-in-Block** suchen (bis zum ersten Zeilenumbruch mit neuem `- `), **oder** Docstring und N18
auf „Spanne bis zum nächsten Fett-Lead-in" zurücknehmen.

### N4-3 — R3-1 ist an **einer** Stelle korrigiert und an einer zweiten stehen geblieben

`project_memory/staging/TSK-0131/stream-protocol.md:629` (N8):

> „`kernel.cli validate` auf dem Hauptstore: **0 error(s), 67 warning(s)**."

N15 (:768) ist genau dafür ausdrücklich korrigiert, N8 nicht. 67 ist die Zahl des Kernels, den
dieses Paket **ersetzt**; zum Zeitpunkt von N8 (Ende Nacharbeit 1) war die Trägerprüfung im Paket
bereits gebaut (N2). Meine Messung mit dem **laufenden** Kernel gegen den Hauptstore steht unten
unter (d): **0 / 77 / 10**. Zeile 369 (Runde 1, 00:36) ist sachlich in Ordnung — damals gab es die
Prüfung noch nicht —, sagt das aber nicht dazu.

**Schwere:** niedrig. **Minimaler Fix:** ein Satz bei :629 wie der bei :768.

### N4-4 — die (g)-Zeile trägt keine **Prüfer**-Token

N19 nennt Token nur für die Umsetzer (A ~896 k, B 247 k). Der Auftrag verlangt „Token impl/verif je
Runde". Für diese Runde: **Prüfer Runde 4 ≈ 165 k** (eigener Zähler: 14 966 890 bei Beginn gegen
14 801 683 am Ende der Messungen, 19:47). Die Runden 1–3 nennen ihre Prüfer-Token nirgends; das
kann nur der Lead aus dem Spawn-Protokoll nachtragen.

---

## Teil 3 — die Prüfpunkte des Auftrags, je mit der gemessenen Zeile

**(a) Quittungsfilter** — siehe N3-B1. Dritte Gestalt gesucht und **gefunden**: N4-1 (Verengung auf
das Item statt auf die Meldung) passiert beide Tests.

**(b) Leiter-Absatz** — siehe N3-B2/N4-2. „Qualifiziert" ist am **Baum** gemessen (dev 1/35,
research 1/35, office 0/27, mit dem laufenden Leser nachgezogen). Die Aussage über **G5-2s** Absatz
ist an dessen **Zitat** gemessen, nicht an dessen Baum — das benennt der Umsetzer in N20 (h) selbst;
mir lag G5-2s Baum ebenfalls nicht vor.

**(c) Docstring ohne Scratch-Zeiger + BUG-0270/H187.**
`tools/test_migrate.py:3927` nennt den Geschwister-Test, keine Rig-Datei. Kein Treffer auf
`redfirst` in `team-kits/`; die Treffer in `docs/` sind ältere Rundenprotokolle
(`docs/reviews/2026-09-02-*`, `docs/holes/H159.md`), nicht dieser Runde.
H187 gegen den **laufenden** Sweep (`sweep_check.py`, eigener Leser der Suite):

```
top-level directories the sweep reads: ['docs', 'team-kits']
citations the sweep judges            : 480
test pointers under tools/*.py the sweep never opens: 39
of those, resolving at nothing: 4   → alle vier in tools/test_pointer_sweep.py (Zeilen 90/92/93/94)
```

Mechanismus, Kette, Zahl und die `limits`-Schranke des Items stimmen mit dem Gemessenen überein.
Die Loch-Leser über der Merge-Sicht: **3 passed, 1 failed in 26.60s**, und der eine Rote ist fremd
(H169/H171 → `tools/test_ladder.py`, G5-2).

**(d) Validator-Zahlen des laufenden Kernels gegen den Hauptstore** (19:06:01–19:06:17, Paketkernel
gegen die binäre Kopie des Hauptstores):

```
0 error(s), 77 warning(s)      davon 10 × „decision without a carrier":
DEC-0005 0007 0023 0035 0037 0052 0054 0058 0087 0088
Stock lies upward: 0 item(s)
```

Exakt die Zahlen und exakt die Liste aus N20 (e). **Bestätigt.**

**(e) `work`** im Store: `DEC-0085: [TSK-0130]`, `DEC-0086: [TSK-0131]`, `DEC-0049: none`;
`DEC-0087`/`DEC-0088` ohne `work` — im Protokoll (N20 (e)/(h)) mit Grund benannt. N12 nennt
`DEC-0086` bei der Id. **Bestätigt.**

**(f) Bestandstabelle gegen den Store** (`reconcile.py`, gegen die Store-Kopie):

```
table rows: 199 · active BUG items: 199 · in table not active: [] · active not in table: []
status mismatches: 0
Zeilen mit Loch-Id: 119   (Kopfzeile der Tabelle: „199 … davon 119 migrierte Loecher")
Verdiktsummen 8+1+98+52+40 = 199
```

Stichproben: `EVD-0091` (result **fail**, BUG-0069), `EVD-0086`/`EVD-0090` (**pass**) liegen im
Store. **Bestätigt.**

**(g) Die (g)-Zeile.** Stufe, Runden/Verifikationen, Wandzeit (gelesen), eigene Befunde,
Verifiziererbefunde, Nähte (`STALE_LADDER_TEXTS`, `migrate.py _receipt_fields`,
`migrate-holes --reindex`), Nutzerzeile (`BUG-0069`), neue Items: **vollständig**. Token: Umsetzer
ja, **Prüfer nein** → N4-4. Store-Nachprüfung der (g)-Aussagen:
`PR-0004..0007 = DELIVERED`, `BUG-0025/0033/0088/0090/0091 = VERIFIED, archiviert`,
`BUG-0089 = VERIFIED archiviert`, `BUG-0267 = DUPLICATE archiviert`, `BUG-0069 = OPEN`,
`TSK-0121…0126 = CANCELLED archiviert`. **Bestätigt.**

**(h) Die drei Roten.** Selbst gefahren, nicht aus dem Protokoll übernommen:

```
Paketbaum (Store b7f282e):   3 failed in 4.03s
   test_review_procedure::test_every_item_pointer_the_harness_role_texts_write_resolves
   test_review_procedure::test_the_harness_role_texts_carry_the_generation_4_rules_with_their_pointers
   test_repo_hygiene::test_every_decision_pointer_in_a_shipped_kit_file_resolves
Merge-Sicht (derselbe Code, Kopie des heutigen Hauptstores):   3 passed in 7.21s
```

Store-Naht, kein Defekt. Der Lauf `r4-reading-suites.log` ist in sich stimmig (drei `F`,
`3 failed, 1122 passed in 1664.36s`); nachgerechnet, nicht wiederholt (`DEC-0050`).

**Reste R3-2/R3-4/R3-5/R3-6/R3-7:** erledigt. R3-4 rot-zuerst selbst nachgestellt:

```
C0 baseline test_report                                  GREEN  124 passed in 59.37s
C1 „eine Entscheidung als Träger ist wieder still"       RED    1 failed, 123 passed in 58.72s
       FAILED tools/test_report.py::test_a_decision_nobody_carries_is_named_and_none_is_the_silence
```

(genau der Test, den der Docstring von `report._check_decision_carriers` nennt).

**Zusätzlich selbst gemessen (Ableitungen der Runde 4, je eine Mutation):**

```
V1 Sprossen-Ableitung verliert die Alias-lose Hälfte   RED  1 failed, 2 passed
V2 ein Kit-Agent trägt ein Effort, das die Tabelle nicht nennt  RED  1 failed, 2 passed
V3 Tier-Tabelle nennt kein Effort-Feld                 RED  2 failed, 1 passed
D1 ein Wort Drift im Kommentar-Absatz einer Verfassung RED  2 failed
       test_every_constitution_carries_the_comment_discipline_duty
       test_a_paragraph_the_constitutions_share_is_one_text
```

Die Byte-Gleichheit ×3 (Hausregel 6) ist also wirklich gebaut, nicht behauptet.

**Paket/Handover.** `git apply --check` gegen einen frisch aus `b7f282e` entpackten Baum: **rc 0**.
Danach `git apply` + `diff -r` gegen den Paketbaum: **die einzigen Unterschiede sind die drei
`VERSION`-Dateien** (absichtlich draußen) und ein Hook-Audit-Log — der Patch **ist** das Paket.
37 Dateien, alle im `allowed_scope`; kein `VERSION`-, `project_memory/`-, `CLAUDE.md`-,
`.claude/hooks`-, `settings.json`-, `templates/`-, `kernel/migrate.py`-Hunk.
Stempel gelesen: dev `2026.09.06-9`, office `2026.09.06-8`, research `2026.09.06-10`;
`tools/bump_kit_version.py` in meiner Kopie: **unchanged** für alle drei.

**Eine Beobachtung ohne Befundcharakter:** `docs/POST_V2_WISHLIST.md` im **Hauptcheckout** trägt
H185/H186/H187 (Zeilen 2471–2474) und weicht damit von `HEAD` ab (`git show HEAD:` → 0 Treffer);
der Patch trägt die Datei nicht. Das ist der `migrate-holes --reindex`-Schritt, den N18 als
Merge-Naht führt — der Merge muss ihn also nicht nachholen, sondern die vorhandene Änderung
mit-committen.

---

## Ausdrückliche Negativbefunde

**Gemessen und in Ordnung:** Quittungsfilter in beiden Richtungen (M1 über die ganze Datei: genau
ein Test fängt den Rückfall); Identität am falschen Feld ist laut (M3); Leiter-Absatz Sprosse und
Eindeutigkeit (L1/L3 rot); Sprossen-/Effort-Ableitung an beiden Enden (V1/V2/V3 rot); die
Träger-Fehlerzeile (C1 rot, genannter Test); Kommentar-Pflicht byte-identisch ×3 (D1 rot in zwei
Suiten); Validator 0/77/10 mit identischer Liste; `work` auf DEC-0085/0086/0049; Tabelle 199 = 199,
0 Standabweichungen, 119 Loch-Zeilen, Stichproben-Evidenz vorhanden; H187 gegen den laufenden Sweep
(2 Bäume, 480 Zitate, 39 ungelesene Zeiger, 4 tote, alle vier Illustrationen); Loch-Leser der
Merge-Sicht 3 passed/1 fremd rot; die drei Roten sind die Store-Naht (in beiden Richtungen selbst
gefahren); Patch rc 0 und deckungsgleich mit dem Baum; Stempel aktuell; PR/BUG/TSK-Stände im Store.

**Nicht gemessen (ausdrücklich):** die volle Suite (gehört dem Merge, `DEC-0050`); `test_hooks`
(37:12) und `test_hooks_v2` (27:34) nicht wiederholt — nur die Logs nachgerechnet; der Lauf der 18
lesenden Suiten nicht wiederholt (nur nachgerechnet, und die drei Roten einzeln nachgefahren); die
Token-Zahlen der Umsetzer (fremde Zähler); der gehostete CI-Lauf (`BUG-0069`); G5-2s Baum (liegt mir
nicht vor — jede Aussage über dessen Absatz stammt aus dessen Protokollzitat); die drei Piloten der
Kit-Mechanik (Runde 2/3 gemessen, Code unverändert); die Spiegelung nicht byteweise nachgehasht,
sondern über die zwei Wächter-Tests mutiert; `.claude/hooks/test_gates.py` nur in der Merge-Sicht
und nur mit den drei Loch-Lesern.

---

## Urteil

**FAIL** — mit **keinem** blockierenden Befund.

Beide Befunde der Runde 3 sind geschlossen und von mir rot-zuerst nachgemessen; alle sieben Reste
sind erledigt oder benannt; die Zahlen (d)/(e)/(f)/(g)/(h) stimmen mit dem Gemessenen überein; das
Paket ist sauber und der Patch deckungsgleich mit dem Baum. Das FAIL steht allein auf der Regel
„kein Satz behauptet Schutz, den der Code nicht baut" — und alle drei Sätze sind einzeilig zu
korrigieren:

| Befund | blockiert die Runde? | Mechanismus (nicht die zwei Schreibweisen) |
|---|---|---|
| **N4-1** `tools/test_migrate.py:3924` | **nein** — benannter Rest | Der Filter ist auf das **Item** verengt, der Satz behauptet die Verengung auf die **Meldung**; die Zusicherung liest nur Trägermeldungen, also ist die Richtung „jeder andere Befund über die Quittung" ungemessen (M4: 142 passed) |
| **N4-2** `tools/test_review_procedure.py:1392` | **nein** — benannter Rest | Die Prüfeinheit ist die **Spanne bis zum nächsten Fett-Lead-in**, nicht ein Absatz; die zweite Achse kann aus jedem Punkt dieser Spanne stammen (L2 grün). Betrifft die G5-2-Naht |
| **N4-3** `stream-protocol.md:629` | **nein** — benannter Rest | Eine Messung mit dem Kernel, den dieses Paket ersetzt, steht unqualifiziert neben der korrigierten Fassung derselben Zahl |
| **N4-4** `stream-protocol.md` N19 | **nein** | (g)-Zeile ohne Prüfer-Token; für Runde 4 oben nachgereicht |

Nach `DEC-0088` (c) ist das die Klasse **„Prosa gegen Code"** — sie gehört in die Checkliste des
Bauenden bzw. in die Retrospektive, **nicht** in eine fünfte Runde. Meine Empfehlung an den Lead:
die drei Sätze in einem Zug korrigieren (je eine Zeile, keine Suite betroffen außer den beiden
Sekunden-Läufen, die ich oben gefahren habe) und **dann** mergen; wer stattdessen die Lücken
schreiben will statt die Sätze, braucht für N4-1 und N4-2 je ein Loch-Item mit dem Mechanismus aus
der Tabelle oben — ein stehen gelassener Satz ist der teurere der beiden Fehler.

**AC-Urteile:** AC-1 **PASS** (199/199 gegen den Store, Verdikte mit Messzeile, die Münzungen sind
gefahren) · AC-2 **PASS** · AC-3 **PASS** (`Stock lies upward: 0`, Zeile läuft im Hauptstore) ·
AC-4 **PASS** (unverändert seit Runde 2) · AC-5 **PASS** · AC-6 **PASS** (fünf VERIFIED+archiviert,
PR-0004..0007 DELIVERED, TSK-0121..0126 archiviert; offen nur `BUG-0069` = Nutzerzeile) ·
AC-7 **PASS** mit N4-1/N4-2 als benannten Resten auf der Testseite.
