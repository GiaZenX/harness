# TSK-0131 / PR-0008 — Prüfbericht Runde 3 (harness-verifier)

Gemessen 2026-09-06 15:34–15:52 (Uhr gelesen, `date`), Opus 5.
**Frische** Kopie `…/verify/r3` (robocopy aus dem Arbeitsbaum, ohne die `.git`-Zeigerdatei),
Merge-Sicht `…/verify/mergeview` (dieser Code über einer **Kopie** des heutigen Hauptstores und
`docs/`), Rig `…/verify/rig.py` unverändert (verweigert außerhalb seines Verzeichnisses, schreibt
binär). Im Repo wurde nichts geschrieben außer dieser Datei unter `project_memory/staging/TSK-0131/`.

**Urteil: FAIL.** Beide Blocker der Runde 2 sind geschlossen und nachgemessen, der Rig-Fehler ist
gefunden und behoben, N-B3 sauber zurückgenommen. Zwei **neue** Befunde bleiben, beide von derselben
Klasse wie die vorigen — ein Prüfer, der weniger liest, als sein Docstring behauptet —, beide
einzeilig und beide auf der Testseite, ohne Angriffskette.

---

## Teil 1 — die Blocker der Runde 2: beide GESCHLOSSEN

### N-B2 (leere `work`-Schreibweisen) — GESCHLOSSEN

Zwei Prädikate, beide Türen fragen dasselbe. Gemessen an der echten Kommandofläche und am Validator:

```
capture DEC   no work at all  rc=1   work: {}   rc=1   work: []    rc=1   work: ''   rc=1
              work: ['']      rc=1   work:'   ' rc=1   work: [[]]  rc=1   work: [None] rc=1
              work: none      rc=0 DEC-0001 VALID
              work: ['none']  rc=0   work: 'NONE' rc=0   work: ['TSK-9999'] rc=0

validate:  no work / {} / [] / '' / [''] / '   ' / [[]] / [None]  -> warning 'decision without a carrier'
           work: none        -> SILENT
           work: ['none']    -> error 'work names none, which no item carries'
           work: 'NONE'      -> error 'work names NONE, which no item carries'
           work: ['TSK-9999']-> error
           work: ['DEC-0001']-> SILENT
```

Das ist genau, was `DEC-0083` (2) verlangt: **eine** Stille, und `["none"]` als Id wie jede andere.

### N-B1 (die Leiter im Lead-SKILL) — GESCHLOSSEN

Der Schritt behält **keine Kopie**. Gemessen am ausgelieferten Text: `user-gated`, `sonnet-high`,
`kernel derives`, `rung is DERIVED`, `QA FAIL`, `user-confirmed` — **keines** kommt vor. Der
Docstring des umbenannten Wächters sagt jetzt richtig, dass die Verfassungen von b7f282e **dieselbe**
user-gated Leiter vorschreiben und die Ausgabe konsistent war; die falsche Fassung ist benannt.

Vier Rückfälle, jeder rot:

```
token-form relapse (`sonnet-high -> ...`)      rc=1  1 failed   „keeps its own copy of the scaling rule"
prose relapse (user-gated, first QA fail)      rc=1  1 failed   dito
a sentence about what the KERNEL derives       rc=1  1 failed   dito
the pointer removed                            rc=1  1 failed   „took the rule out without telling its lead where it lives now"
```

### N-B3 (`migrate.py`) — SAUBER ZURÜCKGENOMMEN

Der Patch trägt **keinen** `team-kits/kernel/migrate.py`-Hunk (nachgezählt: die vier Treffer auf
„migrate.py" sind `tools/test_migrate.py` und `tools/test_migrate_holes.py`). `tools/test_migrate.py`
im git-tragenden Arbeitsbaum: **141 passed in 201.83s**. Die eine Zeile (`DEC_WORK_FIELD:
DEC_WORK_NONE` in `_receipt_fields`) steht als Naht in N13.

### Der Rig-Fehler — gefunden, behoben, und die Überdeckung ist echt

Meine Runde-2-Notiz („die N5-Zeilen ‚ohne das Gate / ohne das Manifest → RED' konnte ich nicht
reproduzieren") ist bestätigt und die Ursache benannt: das Rig stempelte nicht neu, also brach jeder
Scaffold am Inhalts-Hash und das Rot war ein Artefakt. Mit Neustempelung, am Pilot-Test gemessen:

```
does the docstring state the overlap? True
baseline                  rc=0  1 passed, 2 deselected
gate reader dropped       rc=0  1 passed        ← einzeln nicht nötig
manifest reader dropped   rc=0  1 passed        ← einzeln nicht nötig
BOTH readers dropped      rc=1  1 failed        „a freshly scaffolded project is not clean: rc 1, 40"
```

Genau die Behauptung, die jetzt im Docstring steht. Der Befund der Runde 2 ist damit erledigt und
richtig aufgelöst.

---

## Teil 2 — die neuen Befunde

### N3-B1 — `findings_beside_the_receipts_carrier` verwirft die Warnung für **jede** Entscheidung, nicht für die Quittung

`tools/test_migrate.py:3867–3883`. Der Docstring sagt:

> „THIS FILTER IS NARROW ON PURPOSE: it drops a warning only for the item this run just wrote as its
> receipt, and only that one message. **Any other finding -- including a second decision without a
> carrier -- comes through**, which is what keeps these assertions worth making."

Gebaut ist `receipts = {stem for stem, _path in state.iter_active_items(migrate.RECEIPT_TYPE)}`, und
`migrate.RECEIPT_TYPE == "DEC"` — also **jedes aktive DEC-Item des Stores**, nicht die Quittung.

**Gemessene Zeile**, gegen die Funktion, die läuft, mit einer Quittung und einer zweiten trägerlosen
Entscheidung im Store:

```
migrate.RECEIPT_TYPE = DEC
validate_state carrier warnings: ['DEC-0001', 'DEC-0002']
after the filter: []
the docstring says a SECOND decision without a carrier comes through: False
active DEC items the filter treats as receipts: ['DEC-0001', 'DEC-0002']
```

Das trifft **zehn** Zusicherungsstellen in `tools/test_migrate.py` — in einer Suite, die V1-Entscheidungen
als `DEC`-Items importiert, und die genau diese Runde als Beleg führt („141 passed"). Ein
`assert not findings` liest dort stärker, als es misst: die Prüfung, die diese Runde gebaut hat, ist
in dieser Suite abgeschaltet, nicht verengt.

**Minimaler Fix:** die Quittung an dem erkennen, was sie ist (die Ids, die *dieser* Lauf geschrieben
hat, oder `migrate`s eigene Quittungsmarke im `source`/`title`), nicht am Typ. Eine Zeile — und der
Docstring stimmt dann wieder mit dem Code überein.

### N3-B2 — die Zeiger-Hälfte des Wächters folgt dem Zeiger nicht

`tools/test_review_procedure.py:1304–1305` (Docstring) und `:1338–1347` (Code):

> „AND THE POINTER IS FOLLOWED: **the paragraph the SKILL sends its lead to has to exist in that
> kit's constitution**, so a pointer at nothing fails here rather than in a project."

Gebaut ist `[unit for unit in _lead_in_units(...) if "ladder" in unit.lower()]` — irgendein
Fettabsatz, in dem das **Wort** vorkommt.

**Gemessene Zeile:**

```
units the guard accepts as the ladder paragraph, as shipped: 2
   * - **Your own rung is PINNED, not locked:** … (the DEC-0034 ladder's T3 …)   ← nur eine Erwähnung
   * - **Effort:** all `high`. … Escalation ladder (user-gated, …)              ← die echte Regel

after removing the REAL ladder paragraph: 1 unit(s) still accepted
real ladder paragraph removed        rc=0  1 passed
every mention of 'ladder' gone       rc=1  1 failed
```

Der Absatz, auf den der Lead geschickt wird, kann also verschwinden, ohne dass der Wächter es
merkt — er feuert erst, wenn das Wort nirgends mehr steht. Das ist dieselbe Klasse wie N-B1 der
Runde 2, eine Ebene tiefer, und sie ist gerade jetzt relevant: G5-2 **ersetzt** diesen Absatz
(`staging/TSK-0130/stream-protocol.md`, „(h) THE DEFECT OF THE ROUND: a rule classified `behalten`
was deleted with the ladder paragraph").

**Minimaler Fix:** den Absatz an dem erkennen, wofür der SKILL ihn hält — der Fettabsatz, der die
Sprossen/Effort-Regel **trägt** (z. B. eine `<rung>-<effort>`-Angabe oder das Wort `Effort:` im
Lead-in) —, oder mindestens fordern, dass **genau einer** so heißt, und den Docstring auf das
zurücknehmen, was gemessen wird.

**Beide Befunde sind testseitig, einzeilig und tragen keine Angriffskette.** Ich melde sie als
blockierend, weil beide eine Eigenschaft behaupten, die der Code nicht baut — die Regel, die in
diesem Repo auch dann FAIL ist, wenn der Code stimmt. Wenn der Lead die Runde schließen will, dürfen
sie als benannte Reste in die Löcherliste — **dann aber mit dem Docstring zusammen**, denn eine
stehen gelassene Falschbehauptung ist der teurere der beiden Fehler.

---

## Teil 3 — benannte Reste

**R3-1 — die Zahlen in N15 stammen vom ALTEN Kernel.** N15: „`kernel.cli validate` auf dem
Hauptstore: **0 error(s), 67 warning(s)**, davon **0** ‚without a carrier'". Gemessen, beide Kernel
nacheinander gegen denselben Store:

```
validate @ b7f282e kernel   0 error(s), 67 warning(s)
validate @ stream kernel    0 error(s), 78 warning(s)   ·  11 × 'decision without a carrier'
                            DEC-0005 0007 0023 0035 0037 0049 0052 0054 0058 0085 0086
```

67 ist die Zahl der Code-Fassung, die dieses Paket **ersetzt**. Die Zeile misst nicht den Teil, der
läuft, und sie verdeckt elf echte Befunde. Korrigieren, nicht wegdiskutieren — die elf sind übrigens
kein Defekt dieses Stroms, sondern der Bestand, den die neue Zeile zum ersten Mal sichtbar macht.

**R3-2 — die Entscheidung dieser Runde trägt selbst kein `work`.** `DEC-0086` steht `VALID` und ist
einer der elf ohne Träger; `DEC-0083` (5) verlangt genau, dass die Entscheidungen der Generation 4/5,
die Arbeit verlangen, ihr `work` per `update` bekommen. Dazu: **N12 nennt die DEC-Nummer nicht** —
dort steht „Die DEC-Nummer reicht der Lead nach", während der Auftrag dieser Runde sagt, N12 trage
`DEC-0086` bei der Id. Beides ist eine Kernel-Zeile.

**R3-3 — die Bestandstabelle ist dem Store eine Runde hinterher.** Gemessen:

```
in table, not active: ['BUG-0267']      (seit dieser Runde DUPLICATE, archiviert)
active, not in table: ['BUG-0268']
Stand mismatches: 1  [('BUG-0025', table 'OPEN', store 'TRIAGED')]
```

202 Zeilen gegen 202 aktive BUGs stimmt zufällig, weil eines raus- und eines reinkam. Die zwölf
Stichproben (4 alte, 4 Löcher, 4 FRs) sind sonst stimmig, jede genannte Evidenz existiert, und die
Verdikt-Korrektur der Runde 2 hält (0 Zeilen mit PASS auf kurzem Lauf; BUG-0016/0025
`MEASURED-PARTIAL`, BUG-0069 `MEASURED-OPEN` mit `EVD-0091/fail`). Eine Neuerzeugung genügt — aber
eine Tabelle, die dem Store widerspricht, ist in einem Ziel, das „der Bestand darf nicht nach oben
lügen" heißt, die eine Zeile, die man nicht stehen lässt.

**R3-4 — `work` nimmt eine andere ENTSCHEIDUNG als Träger an.** `work: ['DEC-0001']` ist still,
während die Zeigerrichtung eine Entscheidung ausdrücklich **nicht** als Träger liest (der Test der
Runde 2: „a decision quoting another decision was read as its carrier" ist ein Rot). Die beiden
Richtungen widersprechen sich; der DEC-0034-Fall ist damit eine Ebene höher wieder erreichbar.
Ein Satz in `_check_decision_carriers` (ein `work`-Ref, der ein `DEC` ist, ist kein Träger).

**R3-5 — `work: 'NONE'` kommt durch die Tür und wird sofort vom Validator als Fehler genannt.**
Kohärent (die Stille ist genau `none`), aber die Tür lässt einen Wert durch, von dem sie weiß, dass
der Validator ihn ablehnt. Eine Zeile in der Türmeldung („`none` in Kleinbuchstaben") spart eine
Runde.

**R3-6 — eine Naht fehlt in N13.** Der Wächter dieses Stroms verlangt in **jeder** Kit-Verfassung
einen Fettabsatz, der das Wort `ladder` enthält, und im SKILL die wörtliche Zeichenkette
`constitution's ladder paragraph`. G5-2 schreibt genau diesen Absatz um. Das Risiko ist nach N3-B2
klein (jede Erwähnung genügt), die Abhängigkeit gehört trotzdem in die Nahttabelle.

**R3-7 — vier der fünf reparierten Bugs stehen noch `OPEN`.** Nur `BUG-0025` ist `TRIAGED`;
`BUG-0033/0088/0090/0091` sind `OPEN`, `BUG-0069` bleibt offen wie beschrieben. Gemessen in einem
Wegwerf-Store: `request-approval scope BUG-nnnn` ist **rc 0 auch aus `OPEN`**, der Relay des Leads
ist also nicht blockiert; die Kante, die die Münzung schließt, ist `TRIAGED → APPROVED`. Kein Fehler,
aber der freie Schritt fehlt bei vier von fünf.

---

## Teil 4 — Urteil je Kriterium und Pflicht

| AC | Urteil | Grund |
|---|---|---|
| AC-1 | **TEILWEISE — wartet auf die sechs Münzungen** (nicht angelastet, `DEC-0086` A) | 202 Zeilen, Verdiktvokabular korrekt, 7 nachgemessene Ketten; die Statuswechsel gehören dem Klick. Offen: R3-3 |
| AC-2 | **TEILWEISE** | 4 MERGED+archiviert, der zurückgestellte Block mit Notiz, FR-0002/FR-0004 nachgemessen |
| AC-3 | **PASS** | unverändert grün; die drei Zustände der Stock-Zeile stehen |
| AC-4 | **PASS** | unverändert (Runde 2 gemessen) |
| AC-5 | **PASS** | unverändert; dev + research tragen die Wurzelersatz-Regel |
| AC-6 | **TEILWEISE — wartet auf sechs Münzungen und vier Lieferfreigaben** (nicht angelastet) | Evidenz liegt, Ketten stehen; PR-0004..0007 `APPROVED` |
| AC-7 Texte | **PASS** | Kommentarabsatz byte-identisch ×3, 9 Rollendefinitionen, Lead-SKILL ohne Kopie |
| AC-7 Mechanik | **PASS** | Piloten sauber, Überdeckung gemessen |
| AC-7 FR-0012 | **PASS auf dem Code**, mit R3-4/R3-5 | alle sieben Leerformen an beiden Türen, `none` still, `["none"]` Fehler |

**Pflicht 8 (rot-zuerst, Mutationen, Löcher, Suiten, Host, Uhr): TEILWEISE.** Rot-zuerst je Fix in
meiner Kopie nachgestellt (vier Leiter-Rückfälle rot, sieben `work`-Formen an beiden Türen, die
Überdeckung mit Neustempelung). Löcher: **BUG-0268 = `H185`**, mit `limits` und Modulpräfix
(`gate_test_scope`, `DEC-0050`/`FR-0086`), im Zeigerindex (`docs/POST_V2_WISHLIST.md:2472`, 175
Zeilen); **BUG-0267 `DUPLICATE`, archiviert** — die Rüge der Runde 2 ist damit sauber erledigt.
Dagegen: **N3-B1** und **N3-B2** sind zwei benannte Prüfungen, die weniger lesen als ihr Docstring
sagt, und **R3-1** ist eine Zahl, die gegen den falschen Code gemessen wurde.

**Pflicht 9 (Nähte): PASS mit R3-6.** N13 ist erweitert und nennt die G5-2-Zeile wörtlich, die
`STALE_LADDER_TEXTS`-Einträge, die `migrate.py`-Zeile und den `migrate-holes --reindex`-Schritt.
Merge-Sicht gemessen (dieser Code über einer Kopie des heutigen Hauptstores):

```
test_the_harness_role_texts_carry_the_generation_4_rules_with_their_pointers
test_every_constitution_carries_the_comment_discipline_duty
test_no_lead_skill_keeps_its_own_copy_of_the_scaling_rule
test_every_implementing_role_definition_carries_the_comment_duty
test_every_decision_pointer_in_a_shipped_kit_file_resolves
test_every_test_pointer_this_repo_writes_resolves            ->  6 passed in 36.65s
```

und dieselben vier über dem b7f282e-Store des Arbeitsbaums: **1 failed, 3 passed** — der eine Rote
ist `DEC-0080`, das im Hauptstore liegt. Die Naht ist also genau die, die das Protokoll beschreibt.

**Pflicht 10 (Handover): PASS.**

```
patch bytes=242454  CRLF lines=0  LF-only lines=3458
37 Dateien, 36 mit index-Zeile, neu: tools/test_pointer_sweep.py
pre-image mismatches: 0   (jeder `index <old>..` gegen `git rev-parse b7f282e:<pfad>`)
VERSION 0 · project_memory 0 · CLAUDE.md 0 · .claude/hooks 0 · settings.json 0 ·
kit hooks 0 · kit templates 0 · model_tiers 0 · team-kits/kernel/migrate.py 0
```

Alle 37 Pfade liegen im `allowed_scope`. Kein Commit, kein Push, keine Installation.

---

## Ausdrückliche Negativbefunde

**Gemessen und in Ordnung:** die sieben leeren `work`-Formen an beiden Türen plus `none` und
`["none"]`; die vier Leiter-Rückfälle rot; der Lead-SKILL ohne jedes Inhaltswort der Regel;
`tools/test_migrate.py` 141 passed im git-tragenden Baum; `migrate.py` aus dem Patch; die
Überdeckung der drei Kit-Material-Leser (einzeln grün, zusammen rot, Docstring sagt es); BUG-0268
= H185 mit `limits` und Indexzeile, BUG-0267 DUPLICATE archiviert; zwölf Tabellenstichproben gegen
Store und Evidenz; sechs Naht-Tests in der Merge-Sicht grün und derselbe Rote über dem b7f282e-Store;
Patch sauber; `request-approval scope` aus `OPEN` rc 0.

**Nicht gemessen:** die volle Suite (gehört dem Merge); die Zahlen 905 / 3358 der Nacharbeit nicht
nachgefahren; die drei frischen Piloten dieser Runde nur über den Pilot-Test, nicht noch einmal von
Hand (Runde 2 hat sie einzeln gemessen, der Code der Piloten-Ableitung ist unverändert);
`test_hooks`/`test_hooks_v2` nicht (35 min, Host-Regel); der gehostete CI-Lauf (BUG-0069); ob der
Agent-Aufruf einen `model`-Parameter trägt; die Spiegelung nicht byteweise nachgehasht; G5-2s Baum
liegt mir nicht vor — die Aussage über den Absatz nach dem Merge stammt aus dessen Protokoll, nicht
aus dessen Dateien.

---

## Urteil

**FAIL.**

**Blockierend für die Runde** (beide testseitig, je eine Zeile, ohne Angriffskette — als benannte
Reste akzeptabel, dann aber **mit** ihren Docstrings):
* **N3-B1** — `tools/test_migrate.py:3867` verwirft die Träger-Warnung für **jedes** aktive
  `DEC`-Item; der Docstring sagt ausdrücklich das Gegenteil. Gemessen: zwei trägerlose
  Entscheidungen im Store, `validate_state` nennt beide, der Filter gibt `[]` zurück. Zehn
  Zusicherungsstellen in der Suite, die dieser Runde als Beleg dient.
* **N3-B2** — `tools/test_review_procedure.py:1338–1347` prüft nicht, ob der Absatz existiert, auf
  den der SKILL zeigt, sondern ob das **Wort** `ladder` irgendwo in einem Fettabsatz steht. Gemessen:
  echten Leiter-Absatz entfernt → `1 passed`; erst wenn das Wort ganz verschwindet → `1 failed`.
  Genau der Absatz wird von G5-2 ersetzt.

**Benannte Reste** (Löcherliste bzw. Tisch des Leads): **R3-1** (die 67/0 in N15 sind die Zahlen des
alten Kernels; der Paketkernel sagt 78 und elf trägerlose Entscheidungen), **R3-2** (`DEC-0086` ohne
`work`; N12 ohne die Id), **R3-3** (Tabelle gegen Store: BUG-0025, BUG-0267, BUG-0268), **R3-4**
(eine Entscheidung als Träger einer Entscheidung ist still), **R3-5** (`NONE` durch die Tür),
**R3-6** (die Verfassungs-Absatz-Abhängigkeit fehlt in N13), **R3-7** (vier der fünf reparierten Bugs
noch `OPEN`; der Relay ist trotzdem fahrbar, gemessen).

AC-1/AC-2/AC-6 bleiben offen **auf die sechs Münzungen und vier Lieferfreigaben** — das ist die
Nutzerentscheidung `DEC-0086` (A) und wird dem Strom nicht angelastet.
