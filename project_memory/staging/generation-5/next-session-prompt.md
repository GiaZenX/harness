# Handover prompt for the next session (write nothing from memory -- the state on disk is the authority; this file only points)

Weiter mit Generation 5. Stand: Generation 4 ist gemergt, geprüft, committet und GEPUSHT (Merge
`b7f282e` auf `feat/harness-v2`, EVD-0084 Lieferlauf, EVD-0085 Prüfurteil; Kits `2026.09.05-6`;
155 Löcher als BUG-Items migriert über `kernel.cli migrate-holes`). Die Rückschau steht als
**DEC-0080**. Generation 5 läuft: drei Ströme gespawnt am 2026-09-05 (Fable 5.1, effort high) aus
`b7f282e`, Plan-Freigabe erteilt, Schnitt vor READY gemessen (disjunkt).

Lies in dieser Reihenfolge, bevor du etwas tust:

1. `project_memory/decisions/active/DEC-0080.yaml` -- die Rückschau von Generation 4, neun Regeln
   (Reichweiten-Naht, Suiten die eine geänderte Regel lesen, widerlegte Sätze vor dem Schnitt
   greppen, keine Volllast, Stempel vor Volllauf, Leser-Klasse zuerst angreifen, Uhr lesen, Stufen,
   der Gen-5-Schnitt). Dazu DEC-0075 (Rechnungs-App = eigenes Produkt), DEC-0076/0077/0078
   (Leitern, zwei Achsen, Büro-Leiter je Kit), DEC-0079 (DEC-0074 präzisiert).
2. `project_memory/staging/generation-5-streams.md` -- das Logbuch von Generation 5 (Ziele,
   Dateihoheit, Nähte, Spawn) und `project_memory/staging/generation-4-streams.md` (das ganze
   Gen-4-Logbuch mit allen Messungen; die Uhrzeit-Korrektur beachten).
3. Die drei Aufträge: `project_memory/tasks/active/TSK-0130.yaml` (PR-0010 Watcher, Leitern,
   Eskalation), `TSK-0131.yaml` (PR-0008 Bestandsbereinigung), `TSK-0132.yaml` (PR-0009 Büro-Paket);
   ihre Protokolle unter `project_memory/staging/TSK-013x/stream-protocol.md`, Patches unter
   `C:/Offline Repos/v2-testbed/_round-scratch/TSK-013x/stream-*.patch`, Worktrees
   `C:/Offline Repos/v2-testbed/_worktrees/g5-ladders|g5-stock|g5-office`.
4. `project_memory/generated/index.yaml` -- der Zustand.

Laufende Agenten: KEINE, die eine neue Sitzung fortsetzen koennte -- Subagenten sind an die Sitzung
gebunden; nach einem Neustart (oder einer Nutzer-Pause, die als Stopp gilt: Resume wird verweigert,
neue Agenten nur auf ausdrueckliches 'weiter') werden sie NEU gespawnt, mit 'Vorgefunden' zuerst:
den Plattenstand messen (Protokoll, verify-round-*.md, Worktree git status, Patch), dann weiterbauen.
Stand 2026-09-06 (clock read): TSK-0132 CLOSED (PASS Runde 3); TSK-0131 an der Abschlusszeile
(N3-B1/N3-B2, Kernel-Zahlen, work auf DEC-0085/0086, Umfragetabelle, (g)-Zeile) -> danach kurze
Prueferrunde 4 (neuer Opus-Pruefer); TSK-0130 zeichnet die Desktop-Aufgabe als vierte Form auf und
wartet auf die zwei Cloud-Routinen aus der claude.ai-Oberflaeche (Prompts: scratchpad
radar_describe.json bzw. `python tools/radar_routine.py --describe` im Worktree g5-ladders) -> der Lead
schreibt radar/routine.json aus RemoteTrigger list/get, faehrt einmal, uebergibt Ids/Log -> Runde 3.
STAND 20:12 (clock read): alle drei Stroeme CANCELLED (= geliefert in den Merge, Konvention Gen 3/4); TSK-0133 READY, Fable-Umsetzer gespawnt (Merge-Protokoll: staging/TSK-0133/merge-protocol.md); danach Opus-Merge-Pruefer, EVD, Commit; Push nur auf Wort des Nutzers. Nach dem Merge: radar/routine.json durch den Lead auf dem gemergten Baum (Daten), Runde 3 = PR-0010 AC-1 unter PR-0010/TSK-0133, Abnahme-Mints PR-0004..0010, Archiv der TSK-0130..0133, Gen-5-Retrospektive-DEC, Neustart wenn der Nutzer zu Hause ist. DEC-0087/0088:
die leichte Arbeitsform ist Generation 6, Generation 5 laeuft unveraendert zu Ende.

Was ansteht: die drei DEC-first-Vorschläge der Ströme an den Nutzer (Watcher-Auslöser;
Entscheidungs-ohne-Item-Fänger; Schriftverkehr Rolle oder Ablauf) -- je eine AskUserQuestion, dann
Capture als DEC; die Berichte -> Prüfer (Opus) -> Nacharbeiten -> Abschlusszeilen; dann die
Merge-Runde als eigener Auftrag (Reihenfolge nach Nähten: G5-1 Kernel/Validator zuerst? -- MESSEN:
wer empfängt Sätze, kommt zuletzt; Stempel VOR dem Volllauf, DEC-0080 (5); ein Volllauf mit
`DELIVERY_RUN=<merge-TSK>`; die Migrations-Reindex-Zeile `kernel.cli migrate-holes --reindex` nach
neuen Löchern). Nach dem Merge-Commit: Push nur auf Wort des Nutzers; der Neustart (Gate 5 und
Rollentexte für den Lead) sobald der Nutzer zuhause ist; der Rollout in seine Projekte
(Kit-Speicher-Installation, update-kit beim nächsten Sitzungsstart) ebenfalls dann.

Offen beim Nutzer, ohne Eile: Humanizer-Geschmacksurteil (FR-0072); das Einstiegs-Interview der
Rechnungs-App (DEC-0075, eigenes Repo mit dem Entwickler-Kit); die Planungsrunde des
zurückgestellten Blocks (Backlog/Kanban FR-0024/0019/0022; Provider/Container FR-0023/0025/0020);
zwei fremde interaktive Claude-Sitzungen auf dem Rechner („waive-92", „waive-b1") -- Lastverdacht.

Aufräumen beim Rundenabschluss (CLAUDE.md): die g4-Worktrees und `_round-scratch/TSK-0121..0126`
nach dem Gen-5-Merge entfernen, sobald kein Protokoll mehr auf ihre Rigs zeigt (die Prüfberichte
tun es -- vorher die Rig-Skripte, die zitiert werden, nach `staging/` kopieren oder den Zeiger
korrigieren).


STAND 2026-09-10 23:47 (clock read): der Nutzer ist weg und hat DEC-0093 gegeben -- Gen 5 eigenstaendig abschliessen (Merge TSK-0133 laeuft, Fable, nach Wochenlimit fortgesetzt; Volllauf 3 rot / 4841 gruen liegt in staging/TSK-0133/run-full-suite.txt), Opus-Merge-Pruefer, EVD, COMMIT ohne Rueckfrage, KEIN PUSH; danach Gen 6 auf dem committeten Baum starten: PR-0011 (DRAFT, 12 ACs) nach DEC-0087 (7) schneiden -- EIN Bauer (Fable, high) mit dem ganzen Ziel, zweiter Auftrag nur bei gemessen disjunkten Mengen, check-scopes, READY, spawn; die Plan-/Scope-Frage zu PR-0011 und die Abnahmen PR-0004..0010 als EIN Buendel bei seiner Rueckkehr. Neue DECs heute: 0089 (lokale Desktop-Routine ist der Mechanismus), 0090 (claude-/codex-watcher, opus-Sprosse, vier Routinen), 0091 (Stufe je Auftrag), 0092 (Fakten-Checkpoint statt Begruendungsfeld + Struktur-Gate), 0093. BUG-0271 (Freigabe-Frage Maschinendeutsch, Schwester BUG-0073). TSK-0134 (Watcher) haengt an PR-0011. Updates an den Nutzer: 2-3 Saetze.


STAND 2026-09-11 01:5x (clock read): GENERATION 5 COMMITTED (5048c18, NICHT gepusht) und geschlossen (closeout_gen5.py, DEC-0094 Retrospektive). GENERATION 6 laeuft unter DEC-0093 (eigenstaendig, keine Rueckfragen, Updates in 2-3 Saetzen): PR-0011 DRAFT (12 ACs) ist das Ziel; TSK-0134 (Watcher: claude-/codex-watcher, opus-Sprosse beide Anbieter, Runner-Suffix, routine.json) READY -> Opus-Bauer; danach der EINE Light-Kit-Auftrag aus PR-0011 (staging/generation-6/create_light_kit_order.py, DRAFT, Fable high, ein Pruefer am Ziel + ein Zwischencheck). Fuer den Nutzer bei Rueckkehr als EIN Buendel: Plan/Scope PR-0011, Abnahmen PR-0004..0010, Push, BUG-0069 hosted run, vier lokale Routinen (DEC-0090 (5)), FR-0089-Urteil. Rundenlog Gen 6: project_memory/staging/generation-6-streams.md (anlegen beim ersten Eintrag).


STAND 2026-09-11 08:55 (clock read): GENERATION 6 GOAL COMMITTED 6a412d8 (PR-0011 alle zwoelf ACs PASS nach Zielrunde + Nacharbeit + kurzer Runde 2; EVD-0095/0096/0097), NICHT gepusht. DEC-0095 (Bauer/Orchestrator/Pruefer OPUS; Fable nur Architektur-Schritt + Eskalationsziel) und DEC-0096 (Effort vor Sprosse) laufen als TSK-0136 (Opus, READY, Bauer gespawnt); danach EINE kurze gezielte Pruefung, EVD, Commit, dann ROLLOUT in den globalen Kit-Speicher des Nutzers (C:/Users/zenti/.claude/team-kits), dann STOPP -- keine neuen Agenten, kein Experiment ohne sein Wort (Wochenbudget: 30 %% in 8 h gemessen, DEC-0095 (6)). Nutzer-Buendel bei Rueckkehr: Push (5048c18 + 6a412d8 + TSK-0136), Plan/Scope PR-0011, Abnahmen PR-0004..0011, BUG-0069 hosted run, vier lokale Routinen (Desktop SKILL.md auf claude-watcher.md umstellen!), FR-0089-Experiment (Arm A Fable allein / Arm B Kit) und sein Urteil. Die Sitzung des Leads nach dem Commit neu starten (DEC-0095 (6)); harness-lead.md traegt dann `model: opus`.


STAND 2026-09-11 11:35 (clock read) -- GENERATION 6 GESCHLOSSEN, AUSGEROLLT, GESTOPPT: Commits 5048c18 (Gen 5), 6a412d8 (Light Kit + Watcher), e0e515f (Opus-Standard, Effort vor Sprosse), f81b2da (Default/Boden, Test-Leser) -- KEINER gepusht. Globaler Store auf 2026.09.11-10 (install.ps1 11:33, Backup backups/20260911-113312); die drei Projekte ziehen beim naechsten Sitzungsstart. DEC-0095/0096/0097 gebaut; FR-0091 (Modell-Recherche) bestaetigt sie. Offene Loecher der Runde: H190-H194. Rundenlog: staging/generation-6-streams.md. NAECHSTE SITZUNG (Lead nun auf opus, harness-lead.md): zuerst die Gen-6-Retrospektive als DEC aus dem Rundenlog; dann das Nutzer-Buendel in EINER Sitzung: Push (vier Commits), Plan/Scope-Frage PR-0011, Abnahmen PR-0004..0011 (delivery -> acceptance), vier lokale Routinen (Desktop-Task SKILL.md auf .claude/agents/claude-watcher.md umstellen; Codex-App-Automationen aus `python tools/radar_routine.py --describe`), FR-0089-Experiment (Arm A Fable allein / Arm B Kit, Urteil des Nutzers), BUG-0069 nach dem Push. Kein neuer Agent ohne sein Wort (Wochenbudget).


## Stand nach PR-0012 Order 3b + Zielrunde (2026-09-12 21:19, Uhr gelesen)

- **Commit 18f9c24 gepusht** (feat/harness-v2), Stempel **2026.09.12-6**. Volllauf EVD-0413: 1 rot (S4-Schiedsrichter, bis der Nutzer den Shell-Patch fährt) / 5077 grün. CI zeigt diesen einen roten Test, bis der Patch drin ist.
- **Drei parallele Ströme** (DEC-0101): TSK-0141 A Kern (28 geschlossen, 4 Prüfrunden), TSK-0142 B Kits (B/B2/B3, 31 geschlossen, 3 Prüfrunden), TSK-0143 C Werkzeuge (9 geschlossen, 3 Prüfrunden); Zielrunde TSK-0144 (2 Prüfrunden). Alle CANCELLED nach dem Commit (Muster). Rundenlog: `staging/generation-6-streams.md`. Retrospektive: **DEC-0102**.
- **Offen beim Nutzer (Klicks):** 10 Verifikations-Fragen (68 Ids) + 8 Ausnahme-Fragen (53 Ids, je mit deutschem Satz in `limits`) -- Anfragen angelegt 2026-09-12 21:19; Fragen wortgleich aus `approvals.build_question` (Scratchpad `q_final.json`). Elf alte Anfragen von 09:15 (abgelehnte Ausnahme-Stapel) sind noch offen und werden NICHT gestellt.
- **Entscheidungsfragen an den Nutzer (8):** H155/BUG-0237, H170/BUG-0252, H171/BUG-0253 (TSK-0141 protocol.md, Abschnitt "DEC questions for the user", Frage 1 in der umgeschriebenen Fassung), BUG-0286/H202, H178/BUG-0260, H166/BUG-0248, H72/BUG-0164, BUG-0056 (TSK-0142 protocol.md); Antworten -> DEC je Frage, dann Aufträge.
- **Shell-Patch des Nutzers:** `staging/TSK-0143/h182-harness-patch-EXTENDED.md` (7 Stellen) + `staging/TSK-0141/s4-gate-commit-evidence-patch.md` (Stelle 8, mit Lead-Notiz) + H47-Zeile in `_harness.py` (TSK-0142 protocol, Seam 1). Danach Session-Neustart; dann wird der S4-Test grün.
- **Nächster Auftrag (in-repo, kein Klick nötig):** H61/BUG-0153 (timeout in alle Kit-Hook-Registrierungen, dann der Leser), H113/BUG-0197 (Erledigt-Datensatz), H59/BUG-0151 (Verweigerung statt Warnung -- Entscheidung?), BUG-0295..0301 (Prüfer-Reste), BUG-0069 (schließt mit grüner CI nach dem Patch). Noch nicht als TSK angelegt.
- **Nicht vergessen:** Desktop-App-Sitzung für die Claude-Watcher-Aufgabe (DEC-0098), Codex-Automationen, FR-0089-Experiment, `migrate-holes --reindex` nach jeder Loch-Aufnahme (Stand 207 Löcher).

### Nachtrag 2026-09-12 22:58 (Uhr gelesen) -- nach den Klicks und Entscheidungen des Nutzers

- 18 + 3 Klicks erteilt: 65 VERIFIED, 56 ACCEPTED_EXCEPTION (Archiv: 199 VERIFIED / 70 ACCEPTED_EXCEPTION / 4 REJECTED / 2 DUPLICATE). **Aktive BUGs: 27** (davon 9 = Schutzdateien dieses Repos -> Nutzer-Patch: H13 H18 H19 H23 H47 H69 H151 H182 H188; 5 = durch Entscheidungen bestellt: H155 H171 H178 H166 + H170 als Ausnahme angefragt; 3 = in-repo-Rest H59 H61 H113; 1 = Stempel-Nachmessung H160; 8 = Prüfer-Reste BUG-0295..0302; BUG-0069 = CI).
- Acht Entscheidungen als DEC-0103..0110 aufgenommen. **Order 4 = TSK-0145 (DRAFT)**, Skript `generation-6/create_bug_null_order_4.py`; READY + Spawn nach dem Wort des Nutzers (Zeitpunkt).
- Elf alte Anfragen von 09:15 stehen weiter unter approvals/pending (BUG-0302: keine Rücknahme-Tür); der Hook meldet sie bei jeder Frage -- harmlos, aber laut.
- Commits: 18f9c24 (3b + Zielrunde), 05f7d79 (Zustand), dann der Abschluss-Commit dieser Sitzung; alle gepusht.

### Nachtrag 2026-09-13 09:03 (Uhr gelesen) -- Order 4 abgeschlossen

- **Commit 92d746a gepusht**, Stempel **2026.09.13-3**, Rollout 08:20. Volllauf EVD-0446: 5139 grün / 1 rot (S4-Schiedsrichter) / 14 skipped. Order 4 = TSK-0146/0147/0148 (Ströme) + TSK-0149 (Zielrunde), alle CANCELLED nach dem Commit; Prüfrunden 10, Nacharbeiten 6; 23:02-08:33.
- Klicks: 11 weitere VERIFIED (BUG-0237 0302 0295 0299 0153 0248 0260 0298 0300 0301 0242). Entscheidungen: DEC-0112 (BUG-0296: feste Form statt Prosa-Leser), DEC-0113 (H59: nachfragen statt anhalten). Retrospektive DEC-0111 (Regeln 6-9).
- **Aktive BUGs: 16** = 9 Schutzdateien (Nutzer-Patch: H13 H18 H19 H23 H47 H69 H151 H182 H188) + BUG-0253 (Nutzer-Konfigzeile `model_tiers: ladder.yaml` in project_memory/project_config.yaml, dann Klick) + BUG-0297 (Nutzer-Patch S4) + BUG-0069 (CI) + BUG-0296/0151/0197/0303/0304 (Order 5).
- **Order 5 = TSK-0150 (DRAFT)**: DEC-0112, DEC-0113, H113, BUG-0303, BUG-0304. READY + Spawn nach dem Wort des Nutzers.
- 12 alte Anfragen mit `withdraw-request` zurückgenommen (approvals/withdrawn/); pending ist leer bis auf nichts. Nutzer-Patch-Dateien: staging/TSK-0143/h182-harness-patch-EXTENDED.md (7 Stellen) + staging/TSK-0141/s4-gate-commit-evidence-patch.md (Stelle 8) + H47-Zeile (TSK-0142 protocol Seam 1).
