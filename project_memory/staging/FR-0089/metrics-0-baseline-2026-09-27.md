# FR-0089 -- Ausgangswerte (Welle 0, Schritt 0b), gemessen 2026-09-27

Plan: `docs/PLAN_V2_5_VEREINFACHUNG.md` §5 (DEC-0124). Gemessen read-only in diesem Repo und in
`C:\Offline Repos\synaipse-unified`, Stand 2026-09-27 ca. 14:45. Jede Zeile nennt Methode und Quelle,
damit dieselbe Messung nach jeder Welle wiederholt werden kann.

## Kurz gesagt (einfache Sprache)

- **Unnötige Sperren sind häufig.** In beiden Projekten wird etwa jeder dreißigste Arbeitsschritt eines
  Agenten von einer Schutzregel abgewiesen (hier 4,2 von 100, in synaipse 3,3 von 100). In einer
  Stichprobe von je 30 Abweisungen waren **zwei Drittel harmlos** (Lesen, Schreiben in freie
  Arbeitsordner, Befehle, die die Regel nur nicht lesen konnte). Echten Schutz gab es in 9 von 30
  Fällen, hier davon 6 absichtliche Test-Commits, mit denen die Leitung eine Prüfsumme abliest.
  Diese Messung selbst wurde 4-mal grundlos gestoppt.
- **Freigabe-Klicks:** Hier kosteten die großen Ziele im September 14 bzw. 45 Klicks. Seit dem 20.
  waren es nur 5. In synaipse waren es 34 Klicks in drei Tagen (12/13/9 pro Tag), zwei Drittel davon
  Umfangsfreigaben. Pro Ziel sind es bis zu 8.
- **Prüfrunden:** Hier braucht ein Auftrag im Mittel 2,4 Prüfrunden (Median 2). **Jede** erste Prüfung
  ist durchgefallen (14 von 14). In synaipse kommen auf 35 Bauaufträge 19 Prüfaufträge.
- **Tokens:** Die Aufträge 5 bis 7 haben hier zusammen rund **867 Mio.** Eingabe-Token gelesen, allein
  Auftrag 7 bisher 398 Mio. Pro Arbeitsschritt liest ein Bauer im Mittel 100 000 bis 470 000 Token.
  Nicht das Warten treibt die Kosten, sondern die Größe des Kontexts mal die Zahl der Schritte.
- **Warten und Hängen:** Im engen Sinn (reine Warte-Schritte) ist Polling klein: 2,8 % der Schritte
  und 5 % der Token hier, 0,7 % in synaipse. Aber die Bauer hier verbringen **gut die Hälfte ihrer
  Laufzeit** in Warteschleifen auf Testläufe. Zwei Läufe hingen, ohne dass es jemand bemerkte. Ein
  Test stand 37 Minuten still und fiel erst nach 39 Minuten auf. Eine vergessene Warteschleife meldete
  sich erst nach rund 42 Stunden. Ein Lebenszeichen alle paar Minuten hätte beides nach höchstens
  5–10 Minuten gemeldet.
- **Aufträge je Ziel:** In synaipse im Mittel 12,7 Aufträge je Ziel. Parallel arbeiteten bis gestern
  höchstens 2 Bauer, heute bis zu 4. Hier liefen in drei der sieben Aufträge je 3 Bauer parallel.
- **Gesamtlauf der Tests:** Er dauert inzwischen **64 bis 134 Minuten**, früher 38 bis 46. Die
  Gesamtläufe finden echte Fehler, aber immer VOR der Prüfung. Ein Lauf NACH dem Bestehen der
  Prüfung hat bisher nichts gefunden, was der Prüfer übersehen hatte (0 von 1, ein weiterer läuft noch).
- **Buchführung gegen Produkt:** In synaipse sind 61 % der Commits seit dem 20. reine
  Buchführung (nach Präfix), 49 % berühren nur die Projektakte. Hier sind es 4 von 10 (Präfix) bzw.
  3 von 10 (nur Projektakte).
- **Text beim PM-Start:** Beim Start liest der PM in synaipse wirklich die Verfassung (52 KB), seine
  Rollendatei (11 KB) und den Sitzungsbrief (4 KB), zusammen rund 16 500 Token. Der erste Schritt
  kostet gemessen 53 469 Token. Die PM-Anleitung (SKILL, 50–55 KB) wird beim Start **nicht**
  geladen und wurde in der ganzen Sitzung kein einziges Mal aufgerufen.

---

## 1. Fehlblockaden (Verweigerung eines harmlosen Befehls) je Sitzung

| Größe | hier | synaipse | Methode | Quelle |
|---|---|---|---|---|
| Nutzbarkeit von `.audit/hook_events.jsonl` | **nicht nutzbar**: 814 Zeilen, letzte Verweigerung 2026-09-13, 0 seit 09-14; Inhalt sind Testläufe der Kit-Hooks aus der Repo-Wurzel (Fixture-Namen `neighbour-stack`/`myproject`; ein Umsetzer notierte 09-03: „ein Lauf von `tools/test_hooks.py` aus der Repo-Wurzel hängt eine Zeile an“). Die Werkstatt-Gates in `.claude/hooks/` schreiben **kein** Audit (Grep nach `jsonl`/`.audit`: 0 Treffer) | nutzbar: 741 Ereignisse, 263 `block` (2026-09-25 15:27 → 09-27 14:46) | Zeilen gezählt, `event == block` | beide `project_memory/.audit/hook_events.jsonl` |
| Ersatzquelle hier | Mitschriften: `tool_result`, der „hook error“ + „[harness gate]“ trägt, gepaart mit dem `tool_use` | – | Python über `~/.claude/projects/<slug>/<session>.jsonl` + `…/subagents/agent-*.jsonl` | Mitschriften |
| Verweigerungen gesamt | Sitzung 6a21859f (09-25 12:36 → 09-27, Lead + 28 Unteragenten): **164** bei 3 866 Werkzeugaufrufen = **4,2 je 100**; Sitzung 4c7eb015 (09-03 → 09-25): 690 / 22 584 = 3,1 je 100 | seit Sitzungsstart 9e1f8b08 (09-26 06:47): **207** bei 6 222 Werkzeugaufrufen = **3,3 je 100**; je Tag 55 / 143 / 65 | Zähler wie oben; synaipse: Blocks im Zeitfenster der Mitschrift | wie oben |
| je PM-Sitzung | 164 (eine Lead-Sitzung über 3 Tage) | 263 über 3 PM-Sitzungen (245c3458, 377041e2, 9e1f8b08) ≈ **88 je Sitzung** | Summe / Sitzungen | Mitschriften-Verzeichnis |
| nach Gate | gate_lead_write_scope 140, gate_commit_evidence 16, gate_test_scope 3, unklar 5 | gate_write_scope 120 (79 nennen kanonischen Zustand, 40 nennen `staging/`, das offen sein soll), gate_subagent_output 49 (45 × „project-manager missing summary“, feuert auf den PM selbst), guard_memory_budget 44, gate_shell_hygiene 15, gate_dispatch 11, guard_yaml_valid 8, guard_agent_spawn 5, gate_pipeline 4, gate_git 3, Rest 4 | Gate-Name aus dem Hook-Pfad bzw. Feld `hook` | wie oben |
| Stichprobe 30 (Zufall, Seed 7) | **harmlos 20**, echter Schutz 9 (davon 6 absichtliche `git commit -q -m x`-Proben zum Ablesen des Diff-Digests), unklar 1 → **69 % harmlos** ≈ 113 harmlose in der Sitzung ≈ **2,9 je 100 Aufrufe** | **harmlos 20**, echter Schutz 9, unklar 1 → **69 % harmlos** ≈ 181 harmlose ≈ **60 je PM-Sitzung** | Regel unten | Stichprobe im Protokoll dieser Messung |
| Eigene Messung (Kontrolle) | diese Messung: 4 Verweigerungen, alle harmlos (`cd` + Lesen, `for`-Schleife mit `TSK-$i`, `python -c "…{…}"`, `for f in …; head`) | – | beobachtet | diese Sitzung |

**Klassifikationsregel.** *Echter Schutz* heißt: Der abgewiesene Befehl hätte (a) kanonischen
Zustand, die Schutzschicht oder eine Hook-Datei beschrieben, gelöscht oder gestartet, (b) ohne Beleg
committet, (c) bei roter Qualitätspipeline gemergt, (d) eine explizite Prozessregel gebrochen (Auftrag
ohne `objective`, Gedächtnis-Budget, Gesamtlauf ohne `DELIVERY_RUN`). Das gilt unabhängig davon, ob
die Absicht legitim war. *Harmlos* heißt: Die Wirkung des Befehls ist nur lesend oder zielt nur auf
freie Pfade (Scratch, `staging/`, Temp). Oder das Gate konnte ein Wort nicht platzieren (`$x`, `{`,
`cd /c/…`), und derselbe Befehl lief in anderer Schreibweise durch. Eine Stop-Forderung an den PM
(„missing summary“) zählt ebenfalls als harmlos.

Stichprobe hier, harmlos: Lese-Schleifen über `project_memory/*/active` (4), Kopien Repo → Scratch
(`tar`, `robocopy`) (2), Schreiben nur in Scratch mit `$V`/`$S`/`$P` (4), `md5sum` einer Hook-Datei als
„Start“ gelesen (1), `Get-Process … SilentlyContinue` als `git silentlycontinue` gelesen (1),
`python -c` mit `{` (2), Mess-Schleifen `TSK-$i`/`$t` (2), `gh run view … > scratch` (1), `git show >
Temp` (1), `cd /c/…` + Scratch-Rig (1), `mkdir staging` + `cd` (1). Echter Schutz: 6 Commit-Proben,
Kernel-Beleg + Commit in einer Zeile (1), `cp` einer Hook-Datei in den Spiegel (1), `sed -i` auf
`_kernel.py` (1, Verweigerungsgrund falsch zugeordnet, Ergebnis richtig). Unklar: 1 (Ausgabetext
enthielt das Suchwort).
Stichprobe synaipse, harmlos: `mkdir project_memory/staging/…` (3), Lese-Befehle über
`project_memory` (`for`, `find -exec cat`, `python -c yaml`, `git check-attr`, `git archive | tar` in
Scratch) (7), Kernel-Weg `scripts/harness.py submit-result` selbst verweigert (1),
Staging-Probeskript (1), „project-manager missing summary“ (8). Echt: Gedächtnis-Budget (4), Auftrag
ohne `objective` (2), rote Pipeline vor Merge (2), `rm .claude/kit_update_pending.repo` (1). Unklar:
Skript `$S` mit Staging-Eingabe (1).

## 2. Freigabe-Klicks je Ziel und je Tag

| Größe | hier | synaipse | Methode | Quelle |
|---|---|---|---|---|
| Klicks gesamt (erteilte APR) | 80 (verbraucht 80, zurückgezogen 12, offen 0) | 34 (verbraucht 34, zurückgezogen 7, offen 1) | ein APR = eine Nutzerantwort (`minted_via: user_answer_via_approval_hook`; hier 4 ältere ohne Feld) | `approvals/APR-*.yaml`, `approvals/{consumed,withdrawn,pending}/` |
| je Tag | 09-03: 4 · 09-04: 2 · 09-05: 1 · 09-06: 9 · **09-11: 26 · 09-12: 27** · 09-13: 6 · 09-25: 2 · 09-26: 3 | **09-25: 12 · 09-26: 13 · 09-27: 9** | `approved_at[:10]` | wie oben |
| seit 09-20 | 5 (4 verification, 1 hole_exception) | 34 | Filter `approved_at ≥ 2026-09-20` | wie oben |
| je Ziel | PR-0011 (09-11 01:52–14:40): **14**; PR-0012 (09-11 14:40 → 09-13 16:00): **45** (26 verification, 12 hole_exception, 3 delivery, 3 acceptance, 1 scope); V2-Wurzeln PR-0001..0010: je 2 | PR-0031: **8** (6 scope, 1 delivery, 1 acceptance) · PR-0019: 6 · PR-0017: 6 · PR-0018: 3 · PR-0020: 3 · PR-0032: 2 · PR-0021/0022/0009: je 1 · ohne Ziel 2, BUG 1 | hier: Zeitfenster aus dem Rundenprotokoll, weil Stapel-Freigaben `item: null` tragen; synaipse: `item` → Ziel über `target_pr`/`product_requirement`/`derives_from` | wie oben + Items |
| nach Art | verification 30, hole_exception 13, scope 12, delivery 11, acceptance 11, plan 3 | **scope 23 (68 %)**, delivery 7, plan/kit_update/routine/acceptance je 1 | Feld `kind` | wie oben |

## 3. Prüfrunden je Auftrag

| Größe | hier | synaipse | Methode | Quelle |
|---|---|---|---|---|
| Runden je Auftrag, TSK-0138..0156 | 0138: 2 · 0139: 2 · 0140: 2 · 0141: **4** · 0142: 3 · 0143: 3 · 0144: 2 · 0145: 0 (vor Bau neu geschnitten) · 0146: 2 (Rest in 0149) · 0147: 2 · 0148: 2 · 0149: 3 · 0150: 2 · 0151: 3 (+1 durch Limit getötet) · 0152: 2 (Rest ohne 3. Runde geschlossen) · 0153/0154/0155: 0 (Ströme, Prüfung im Merge) · 0156: Runde 1 läuft | – | „VERIFY/CHECK round n“ je Auftrag im Protokoll gezählt | `project_memory/staging/generation-6-streams.md` Z. 46–174; `staging/TSK-0156/verify-round-1.md` |
| Mittel / Median (14 geprüfte Aufträge) | 34 Runden / 14 = **2,43**, Median **2** | – | Summe / Anzahl | wie oben |
| Erste Runde durchgefallen | **14 von 14** | – | Ergebnis Runde 1 | wie oben |
| Je Ziel (Order) | Order 3 (0140 + 3b 0141–0144): 14 · Order 4 (0146–0149): 9 · Order 5: 2 · Order 6a: 3 · Order 6: 2 | QA-Aufträge je Ziel: PR-0018 3 · PR-0019 3 · PR-0020 0 · PR-0021 6 · PR-0031 6 · PR-0032 2 (**20 von 76** geleasten Aufträgen) | synaipse: `assigned_role ∈ {quality-engineer, qa}` oder `type ∈ {review, test}`, nur Aufträge mit `leased_at` | Protokoll; synaipse `tasks/active` + `archive/TSK` |
| Prüf- je Bauauftrag | 14 Aufträge, 34 Prüfrunden (Nacharbeiten nicht getrennt gezählt) | 19 quality-engineer-Leases auf 35 Bauaufträge (frontend 18, backend 8, devops 9) = **0,54**; `failed_runs` Summe 13, Status FAILED 6; gate_subagent_output: 35 × Nachlieferung, 10 × aufgegeben | Rollen der geleasten Aufträge | synaipse Items + hook_events |

## 4. Tokens (Unteragenten; Messwerkzeug `tools/measure_agent_tokens.py`)

Aufruf: `python -B tools/measure_agent_tokens.py --item TSK-0150` … `TSK-0156`. Das Werkzeug ordnet
einen Agenten jedem Item zu, das in seinem ERSTEN Prompt steht. Das zählt doppelt: Der
Merge-Bauer a0e26d1f und der Merge-Prüfer a5f88635 nennen 0153–0156, dieser Mess-Agent ab17fd69
nennt alle sieben. Die Tabelle ordnet darum jeden Agenten nach seiner Beschreibung genau einem
Auftrag zu und lässt den Mess-Agenten weg (gleiches Modul, `collect()` + `summary()`).

| Auftrag | Agenten (Bauer/Prüfer) | Züge | Median Kontext je Zug (Median der Agenten-Mediane) | Eingabe gesamt | Polling-Züge | Polling-Anteil Eingabe |
|---|---|---|---|---|---|---|
| TSK-0150 (Order 5) | 2 (1/1) | 664 | 284 281 | **189,1 M** | 28 | 6,4 % |
| TSK-0151 (Order 6a) | 9 (5/4) | 847 | 134 164 | **160,8 M** | 4 | 0,8 % |
| TSK-0152 (Order 6) | 6 (4/2) | 629 | 107 344 | **118,8 M** | 11 | 4,2 % |
| TSK-0153 (Strom A) | 2 (2/0) | 334 | 280 791 | 109,9 M | 6 | 1,6 % |
| TSK-0154 (Strom B) | 1 (1/0) | 327 | 470 553 | 143,9 M | 23 | 9,4 % |
| TSK-0155 (Strom C) | 1 (1/0) | 268 | 419 082 | 104,8 M | 20 | 9,7 % |
| TSK-0156 (Merge; Prüfer läuft noch) | 2 (1/1) | 237 | 128 675 | 39,6 M | 0 | 0 % |
| **Order 7 (0153–0156)** | 6 | 1 166 | 303 736 | **398,2 M** | 49 | 6,4 % |
| **Summe 0150–0156** | 23 | 3 306 | 143 359 | **866,8 M** | 92 | 5,1 % |

Rohausgabe des Werkzeugs je `--item` (mit Doppelzählung, zum 1:1-Vergleich): 0150 190,2 M · 0151
161,9 M · 0152 120,0 M · 0153 148,6 M · 0154 182,6 M · 0155 143,5 M · 0156 38,7 M.

| Je geliefertem Wunsch | hier | synaipse | Methode | Quelle |
|---|---|---|---|---|
| Unteragenten | Order 5: 189 M (5 BUGs VERIFIED → 38 M je Bug) · Order 6a: 161 M · Order 6: 119 M (3 BUGs + Archivtür) · Order 7: 398 M für ~19 Items (≈ 21 M je Item), noch ohne Abschluss | geliefert: PR-0018 (DELIVERED) **76,7 M**, PR-0031 (ACCEPTED) **122,2 M**; in Lieferung: PR-0019 158,5 M, PR-0020 128,3 M, PR-0021 104,4 M, PR-0032 47,6 M; alle 80 Agenten 637,7 M | synaipse: `--project-dir ~/.claude/projects/C--Offline-Repos-synaipse-unified`, Agent → erstes `TSK-nnnn` im Prompt → Ziel | Mitschriften; Items |
| Leitung / PM (kommt dazu) | Lead-Sitzung 6a21859f: 415 Züge, Median 416 738, **173,2 M** (Orders 6a–7 + Planung) | PM-Sitzung 9e1f8b08: 654 Züge, Median **347 085**, **249,5 M** | Hauptmitschrift, gleiche Zählregel (distinct `message.id`) | Mitschriften |
| Kontext je Zug, alle Unteragenten | 110 Agenten: Median der Mediane 199 548 | 80 Agenten: 125 114 | `summary()` über alles | wie oben |

## 5. Polling-Anteil und unbemerkt hängende Läufe

| Größe | hier | synaipse | Methode | Quelle |
|---|---|---|---|---|
| Polling-Züge (enge Definition des Werkzeugs: jeder Aufruf des Zugs ist `sleep`/`Start-Sleep`/`timeout /t`) | 0150–0156: 92 von 3 306 Zügen = **2,8 %**, 5,1 % der Eingabe; alle 110 Agenten: 525 / 22 248 = 2,4 %, 3,8 % | 31 von 4 379 = **0,7 %**, 0,7 % der Eingabe | `measure_agent_tokens.py` | Mitschriften |
| Warte-Aufrufe (weite Definition: `until`-Schleifen, `wait_*.py`, `tail -f`, `Wait-Process`, `sleep`, die das Werkzeug NICHT als Polling zählt) | Sitzung 6a21859f: 167 Aufrufe, **1 053 min** von 1 943 min Agenten-Laufzeit = **54 %**; typisch 10-min-Blöcke auf Testläufe | 64 Aufrufe, 102 von 1 595 min = **6,4 %** | Dauer `tool_use` → `tool_result` für Befehle mit Warte-Muster; Laufzeit = erste bis letzte Zeile je Agent | Mitschriften |
| Unbemerkt hängende Läufe | **2**: (a) Strom A (TSK-0153), `.claude/hooks/test_gates.py` voll: Knoten #39 **hing 37 min**, erst nach 39 min von Hand abgebrochen, dabei ging die Fehlermeldung eines F verloren (Merge-Bauer a0e26d1f, 09-27 07:12; Protokoll Z. 173–174); (b) TSK-0144 (Order 3b): Wartevorgang auf einen abgebrochenen Gesamtlauf vom 09-12 blieb stehen und meldete sich erst **~42 h** später (Lücke 2 537 min in Agent a73612ae, Protokoll Z. 142). Dazu Verwandte: TSK-0150 Versuch 1 endete nach 6 min ohne Summenzeile (rc 1, abgeschnitten); 3 Bauer vom Nutzungslimit getötet (TSK-0151-Prüfer, TSK-0152-Bauer, Strom A), bemerkt erst beim nächsten Blick der Leitung | **0 sichtbar**: kein Werkzeugaufruf ≥ 15 min, keine Lücke > 15 min in Unteragenten-Mitschriften; aber gate_subagent_output 10 × „gave up“ und BUG-0313 (wartendes Kind als FAILED gebucht, zweiter Bauer parallel) | Aufrufe ≥ 10/15 min und Zeilen-Lücken ≥ 15 min je Agent; Textsuche „hing/stalled/abgebrochen“ | Mitschriften; Rundenprotokoll |
| Wie ein Herzschlag sie gefangen hätte | Testläufe mit Fortschritt je Knoten (`-v`/Zeitstempel je Knoten) in eine Datei; Wächter meldet, wenn > N min keine neue Zeile kommt. Der längste gesunde Knoten liegt bei ca. 2 min, damit reicht N = 5. Fall (a) wäre nach ~5 statt 37–39 min gemeldet worden, mit Knotenname, und das F wäre erhalten geblieben. Fall (b) braucht eine Frist am Warten selbst (Deadline = erwartete Laufzeit × 1,5, bei 90-min-Läufen ~2 h 15) statt 42 h. Beim Limit-Tod fehlt `SubagentStop` mit Ergebnis, der Herzschlag bleibt aus, Meldung innerhalb der Frist | – | Ableitung aus den gemessenen Fällen | – |

## 6. Aufträge je Ziel / parallele Bauer

| Größe | hier | synaipse | Methode | Quelle |
|---|---|---|---|---|
| Aufträge je Ziel | Gen 6: Order 1: 1 · Order 2: 1 · Order 3: 5 (0140 + 3 Ströme + Zielrunde) · Order 4: 4 (+1 storniert) · Order 5: 1 · Order 6a: 1 · Order 6: 1 · Order 7: 4 (3 Ströme + Merge) | 76 geleaste Aufträge über 6 Ziele: PR-0018 17 · PR-0019 11 · PR-0020 11 · PR-0021 13 · PR-0031 18 · PR-0032 6 → **Mittel 12,7, Median 12**; dazu 569 TSK-Items gesamt (davon 96 in 9 min nach der V2-Migration neu angelegt, laut Protokoll Z. 170) | Rundenprotokoll; synaipse `leased_at` gesetzt, Ziel über Item-Kette | Protokoll; synaipse Items |
| Agenten-Starts je Auftrag | 0150: 2 · 0151: **9** · 0152: 6 · Order 7: 6 (+1 Prüfer läuft) | 80 Agenten für 76 Aufträge | Mitschriften-Zuordnung (§4) | Mitschriften |
| Parallele Bauer (max. gleichzeitig) | 3 (Order 3b, Order 4, Order 7), sonst 1 | 09-25: 1 · 09-26: **2** · 09-27: **4** (alle Rollen: 2 / 3 / 8); 47 überlappende `leased_at`–`completed`-Paare; Median-Laufzeit eines Auftrags 17,6 min | Sweep über `[leased_at, completed]` (offene Leases bis 14:31), Bauer = frontend/backend/devops | synaipse Items |

## 7. Gesamtlauf-Dauer und Funde

| Lauf | Dauer | Ergebnis | Quelle |
|---|---|---|---|
| TSK-0126 (Gen 5) | 46:24 | 4 687 grün | `staging/TSK-0126/run-full-suite.txt` |
| TSK-0133 (Gen 5) | 38:19 | 1 rot (CRLF-Hygiene) | `staging/TSK-0133/run-full-suite.txt` |
| TSK-0135 Lauf 1 / 2 | 39:31 / 39:55; Gates 12:37 | 8 rot (vor Zielrunde, alle behoben) / grün | `staging/TSK-0135/full-*.log` |
| TSK-0144 | 1 Lauf nach 9 min abgebrochen; **68:36** (4 116 s) | erster Lauf 9 rot (behoben); dann 1 rot (bekannter S4-Schiedsrichter) | Protokoll Z. 96 |
| TSK-0149 Lauf 1 / 2 | ? / **76:14** (4 574 s) | 7 rot (6 echt, behoben) / 1 rot (S4) | Protokoll Z. 125 |
| TSK-0150 | Versuch 1 abgeschnitten (6 min); **2:14:18** (8 058 s); Gates 44:22 | 4 rot (3 behoben, 1 bekannt) / Gates 3 rot | `staging/TSK-0150/runs.md` |
| TSK-0151 | **1:04:20** (3 860 s); Gates ~20 min | grün (nach Prüfer-PASS); ein früherer Lauf 2 rot, beide durch Änderungen der Leitung | `staging/TSK-0151/full-run-final.txt`, Protokoll Z. 151/158 |
| TSK-0152 | **1:19:49** / **1:27:19** | 3 rot (Vertragstests, vor Prüfer) / grün; zweiter Lauf nach Nacharbeit von gate 5 verweigert | `staging/TSK-0152/full-run*.txt` |
| Strom A (TSK-0153), test_gates.py | nach 39 min abgebrochen (Knoten hing 37 min) | 1 F, nicht zuordenbar | Protokoll Z. 173 |

| Größe | hier | synaipse | Methode |
|---|---|---|---|
| Gesamtlauf-Dauer heute | **64–134 min** (Gen 6 ab TSK-0144, 6 vollständige Läufe: 64, 69, 76, 80, 87, 134 min; Median 78 min), vor Gen 6 38–46 min; Gate-Suite 13–44 min | nicht gemessen (kein `full-run`-Protokoll; Pipeline `scripts/quality.py`, 4 × rot vor Merge verweigert) | Dateien + Protokoll |
| Schneller Kern | existiert nicht | – | – |
| Gesamtläufe mit Fund, den der Prüfer übersah | **0 von 1** Läufen NACH einem Prüfer-PASS (TSK-0151: grün; TSK-0156 steht aus). Läufe VOR der Prüfung fanden echte Fehler in 6 von 8 Aufträgen (0135: 8, 0144: 9, 0149: 6, 0150: 3, 0152: 3, 0151: 2 von der Leitung selbst) → gefunden vom Bauer, bevor ein Prüfer sie sehen konnte. Umgekehrt fand der Prüfer in TSK-0152 F1–F3 nach einem grünen Gesamtlauf | Reihenfolge Lauf ↔ Prüfrunde im Protokoll |

## 8. Produkt- vs. Buchführungs-Commits (`git log --since=2026-09-20`)

| Größe | hier | synaipse | Methode | Quelle |
|---|---|---|---|---|
| Commits | 10 | 110 (107 ohne Merges) | `git log --since=2026-09-20 --oneline` | git |
| nach Präfix | `state:` **4** (Buchführung) · Auftrag/Produkt (`order 6a`, `order 6`) **2** · `user patch … applied` 3 · `radar:` 1 | Buchführung `chore(memory)` 60 + `chore(state)` 5 + `chore(pm-memory)` 2 = **67 (61 %)** · Produkt `feat` 6 + `fix` 6 + `test` 6 = **18 (16 %)** · `docs(unified/architecture/product)` 8 · Kit/Infra `chore(kit/git/agents/codex/unified/deps)` + `ci` 14 · `merge` 3 | Präfix bis `:` | git |
| nach berührten Dateien | nur `project_memory/`: **3 von 10** | nur `project_memory/`: **52 von 107 (49 %)** | `git log --no-merges --name-only`, alle Pfade unter `project_memory/` | git |

## 9. Textlast beim PM-Start (Dev-Kit)

| Größe | hier (Kit-Quelle, Arbeitsbaum) | synaipse (installiert, gemessen) | Methode | Quelle |
|---|---|---|---|---|
| Verfassung `AGENTS.md` | 52 045 B | 51 592 B (über `CLAUDE.md`-Shim 58 B geladen; in der Mitschrift als `instructions`-Anhang 51 650 B) | Dateigröße; Anhang in Mitschrift | `team-kits/dev-team/constitution/AGENTS.md`; synaipse Mitschrift 9e1f8b08 |
| Rollendatei `project-manager.md` | 10 673 B | 10 807 B, **im Systemprompt** (38 von 40 Probezeilen gefunden) | Dateigröße; Zeilenprobe gegen `prompt_snapshot` | `agents/project-manager.md` |
| PM-SKILL | 54 616 B | 50 020 B, **nicht geladen**: 3 von 80 Probezeilen im Systemprompt (Zufallstreffer), 0 `Skill`-Aufrufe in 654 PM-Zügen; Frontmatter `skills: [project-manager]` wirkt für die Hauptsitzung nicht | wie oben; `tools/lead_package.py` `files()` = Verfassung + Rollendatei (Docstring: Messung 2026-08-02, SKILL fehlte) | `skills/project-manager/SKILL.md` |
| Sitzungsbrief (SessionStart-Hook) | – | 3 684 B `additionalContext` | Anhang `hook_additional_context` | Mitschrift |
| Kit-eigene Last zusammen | 62 718 B (`files()`: Verfassung + Rolle) | ≈ 66 KB ≈ **16 500 Token** (Bytes/4) | Summe | – |
| Weitere feste Last (nicht Kit) | – | globale `~/.claude/CLAUDE.md` 19 302 B, MCP-Anweisungen 16 186 B, Agentenliste 7 037 B, Werkzeuge + Basis-Systemprompt | Anhänge der Mitschrift | Mitschrift |
| Erster Zug gemessen | Lead dieses Repos: 90 398 Token (harness-lead, kein Kit) | **53 469 Token** (36 240 Cache-Schreiben + 17 227 Cache-Lesen) | `usage` des ersten Assistant-Zugs | Mitschriften |
| Korrektur zum Review | Das Review (`independent-review-2026-09-27.md`) rechnete ~117 KB ≈ 30 000 Token Pflichtlektüre inkl. SKILL. Gemessen: ohne SKILL ~66 KB kit-eigen. Die SKILL-Regeln erreichen den PM derzeit gar nicht | – | – | – |

## Wiederholen nach jeder Welle

1. Verweigerungen: dieselbe Mitschriften-Zählung (Sitzung des Lead + Unteragenten; synaipse: `hook_events.jsonl` im Fenster der Sitzung) + neue Stichprobe 30 mit Seed 7 und obiger Regel.
2. `approvals/APR-*.yaml` nach `approved_at` (Tag) und `item` → Ziel.
3. Rundenprotokoll: VERIFY-Runden je Auftrag; synaipse: QA-Leases je Ziel.
4. `python -B tools/measure_agent_tokens.py --item <TSK>` (+ `--project-dir …synaipse-unified`), Zuordnung ohne Doppelzählung.
5. Werkzeug-Polling + weite Warte-Aufrufe (Muster oben) + Aufrufe/Lücken ≥ 15 min.
6. `leased_at`/`completed`-Sweep; Agenten je Auftrag.
7. Summenzeile `in N s` der Gesamtlauf-Dateien; Reihenfolge Lauf ↔ PASS.
8. `git log --since=<Wellenstart> --oneline` + `--name-only`.
9. Dateigrößen + erster Zug einer frischen PM-Sitzung in synaipse (`usage`, `instructions`, `prompt_snapshot`).
