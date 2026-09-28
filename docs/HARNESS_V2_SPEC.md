# Harness V2 — Auditbericht & Spezifikation (v2.1)

**Status: IN UMSETZUNG** (v2.0 konsolidiert Claude ↔ Codex 2026-07-20; v2.1 nach
verifiziertem Review 2026-07-24 — 3 Opus-Explore-Verifikationen, 1 Opus-Plan-Gegenprüfung,
2 Fable-Vollständigkeitsprüfungen; Phase 0 + Phase 1 abgeschlossen)

**Amendment 2026-07-24 (Spike-Ergebnisse, empirisch):** Die Spikes S2b und S3 wurden nicht
per Userprobe, sondern durch **Transkript-Forensik dieser Session** (S2b) und einen
**headless `claude -p`-Lauf mit Probe-Hooks** (S3) entschieden — Belege im
Phase-0-Bericht §5. Konsequenz: II.2 Punkt 3 des Freigabeprotokolls ist durch den
**Mint-Code-Mechanismus** ersetzt (Options-Identität ist auf der Plattform nicht
verfügbar); die S3-Lease-Bindung ist Ende-zu-Ende bestätigt und funktioniert über BEIDE
Punkte (`SubagentStart.agent_id` und `PostToolUse(Agent).tool_response.agentId`).

**Änderungsprotokoll v2.0 → v2.1** (jede Änderung mit Quelle; alles andere wortgleich):
Teil I faktenkorrigiert (A.1/1–8: I.1.2 Bootstrap-Nuance; I.1.3 Markerzahl/Snapshots;
I.1.4 Neufassung; I.1.5/7 Messwerte; I.1.6 Terminologie; I.1.8 76 Dateien) · II.2
(ARC/WFR-Zeilen+Verzeichnisse, masterplan.md, Nicht-Commit-Regel, FR/PROC-Glättung,
INV.check-Format, TSK-Zeitstempel+legacy_fields, Freigabeprotokoll Marker+Options-Identität+
Bündelung, Research-Fix EXP/HYP, DONE/VALIDATED-Fußnote) · II.3 (Wireframe-Stufe, Bündelung)
· II.4 (Nebenläufigkeit&Locking NEU, agent_id-Write-Scope, Hash-Abgleich, ID-Eindeutigkeit,
PostToolUse-Präzisierung, Bootstrap-Loch, Provider-Parität beweisbar, stdin-Bound,
Staging-Erweiterung) · II.5 (Zählweise, Kürzungs-Sequenz, Latenz, Trigger, Schemas) · II.6
(INV-Beispiel korrigiert) · II.6a NEU (ARC+WFR) · II.7 (präzisiert) · II.8 (+gitignore) ·
II.9 (CSV, process_definitions) · II.10 (Mapping, Branchkonvention, Freeze-Sequenz) · II.10a
(3 Textpräzisierungen: lokaler Scheduled Task, Paritätsmatrix-Kategorie, 904 MB) · II.11
(Phase 0 erweitert, 76-Dateien-Release, Kürzungs-Checkliste, globale CLAUDE.md) · II.12
(neue Testfälle) · II.13 (Risiko 1 präzisiert, 3–5 erweitert, 6 neu) · II.14 (/2 neu
gefasst, Messwerte) · Entscheide 2026-07-24: Wireframes immer bei UI · APR-Bündelung ·
Ablage docs/. **Alle Teil-I-Zahlen sind Messwerte des Reviews 2026-07-24** (Agenten-Evidenz
im Review-Report docs/reviews/). Bewusste Drops gegenüber v2.0: der Hinweis auf das
17-Zeilen-Kit-Template filing_plan.yaml (ersetzt durch den korrigierten Projektbefund
I.1.6) und „oder Userfrage" in II.13/5 (die Abhilfe ist jetzt immer ein benannter Befehl;
Userfragen bleiben Teil von II.8/II.10a).

Auftrag: Read-only-Untersuchung des Harness-Repos `C:\Offline Repos\AgentAndSkills` anhand der
drei damit gebauten Projekte, dann ein ausführungsreifer V2-Plan. **Scope (User-Entscheid):
Lieferumfang ist ausschließlich das Harness** — die drei Projekte dienten der Analyse; ihre
Migration ist dokumentierte Folgearbeit in getrennten, userbestätigten Aufträgen. Bisher wurde
nichts verändert.

---

# Teil I — Auditbericht (Befunde, verifiziert; v2.1-korrigiert)

## I.1 Kernbefunde

1. **"Erst Backlog, dann Agent" war nie technisch erzwungen.** dev-team
   `guard_agent_spawn.py` prüft nur Prompt-Keywords (objective/output), Rolle,
   run_in_background — KEINE Existenz von PRD/SR/Task (verifiziert: null Referenzen auf
   project_memory). Hart erzwungen erst beim Merge (`gate_memory_complete.py:157`, Regex
   `PRD-\d` in product_requirements.yaml). Git-Beweise für Code-vor-Task: portfolio
   `50fd21f fix(committee)…` → danach `2440947 docs(tasks): book TSK-0164 (commit 50fd21f)`;
   synaipse `fix(hardware)` vor `chore(tasks): log TSK-0262..0264`.
2. **Das funktionierende Gegenmuster existiert bereits im office-Kit:**
   `gate_proc_approved.py` blockt Spawns ohne APPROVED PROC mit gültigem `approved_hash` —
   mit einer Bootstrap-Ausnahme (Z. 72): solange KEIN PROC approved ist, passieren Spawns
   frei. V2 schließt dieses Loch (II.4, Paritätsmatrix-Eintrag „bewusst geändert").
3. **Monolith-Bloat:** synaipse tasks.yaml 961 KiB/15.004 Z. (264 TSK), design.yaml
   991 KiB/9.695 Z. mit 14 `SUPERSEDED`-Markern (die Phrase „historical record" 3×; die
   v2.0-Zahl „~150" war eine Falsch-Transkription) und **vier Hardware-Order-Stellen, von
   denen drei zur per design.yaml:9220 abgelösten Revision gehören** (Details Befund 4);
   system_requirements.yaml 490 KiB. portfolio gleiche Muster kleiner (u. a. review_reports
   121 KB, decisions 102 KB, test_reports 99,6 KB). BuyPlugGo filing_log.yaml 577 KiB/6.481 Z.
   (append-only, mit dokumentierter früherer Korruption). Dashboards regeneriert + je 20
   History-Snapshots (3,42 bzw. 2,36 MiB pro Repo).
4. **Die Hardware-Reihenfolge (synaipse) — Neufassung nach Review:** design.yaml enthält
   vier Order-Aussagen auf verschiedenen Achsen: :8014/:8017/:8023 (Grid-/Row-Toggle:
   „card order CPU, GPU, RAM, **STORAGE**" — das Wort „ROM" existiert in der Datei nirgends)
   und :9216 (side_by_side desktop, **User-Entscheidung 2026-07-19**: „Memory · Processor ·
   Graphics · Storage"), deren `supersedes:` (:9220) das alte 2x2-Grid-Layout explizit
   ablöst. `frontend/src/app/HardwareAnatomy.tsx` rendert Memory→Processor→Graphics→Storage
   (Z. 83/109/145/192) und folgt damit der NEUESTEN dokumentierten User-Entscheidung — kein
   aktiver Regelverstoß. Offen (Folgearbeit, User-Entscheid): War „Memory zuerst" in :9216
   eine bewusste Umsortierung oder ein Transkriptionsfehler (inkl. Label-Frage ROM vs.
   STORAGE)? Der Kernbefund bleibt: Die Vorgabe existiert nur als Prosa auf vier Stellen,
   nie als SR/AC/Invariante — nicht einmal das v2.0-Audit konnte sie fehlerfrei zitieren
   (transkribierte „ROM"). Genau dafür sind INV-Items mit Test-Referenz da (II.6).
5. **Memory-Bloat trotz Prosa-Cap:** Verfassung fordert "MEMORY.md INDEX ≤ 40 lines" — kein
   Hook erzwingt es. synaipse `.claude/agent-memory/`: 159 Dateien/0,96 MiB; frontend
   MEMORY.md 17,7 KB/102 Einträge inkl. Einweg-Trivia. Sessiondaten: BuyPlugGo 904 MB (fast
   alles Subagent-Transkripte), synaipse 155 MB/369 Sessions, portfolio 69,5 MB.
6. **BuyPlugGo:** archive/ sauber (6.126 Dateien, entspricht den 5 dokumentierten Top-Knoten),
   daneben 4.370 unaufgeräumte Legacy-Dateien (4-Website/ 3.525, 5-Shopify/ 845).
   ORDNERSTRUKTUR_GUIDELINES.md auf 54 KB (v1.13) gewachsen; das Projekt-`filing_plan.yaml`
   (102 Z.) existiert und wird von gate_filing genutzt, ist aber als „Derived 1:1 from …
   v1.11" die NACHGEFÜHRTE Kopie der Prosa und hängt ihr hinterher — die Wahrheit lebt in
   der Prosa, die Ableitungsrichtung ist falsch herum (V2 dreht sie um, II.9). PROCs liegen
   in `process_definitions.yaml` (16 Stück, alle mit approved_hash; Status
   ACTIVE/APPROVED/PROPOSED/RETIRED). Das Ledger sind CSV-Dateien (ledger/2025.csv 66,8 KB,
   ledger/2026.csv 115,4 KB).
7. **Update-Flow:** ~6 injizierte Blöcke in `session_status.py` (Update-Announce,
   kit_updated_from-Marker, MERGE-BACKLOG-Eskalation, Drift-Tripwires, Transkript-Handover,
   project_memory-Read-Reminder) → Quelle der "Neustart ja/nein?"-Verwirrung; der
   II.8-Ersatz disponiert ALLE Blöcke. portfolio trägt seit 07-18 einen offenen Update-Nag
   (kit_update_pending.state, Repo auf 2026.07.17-9).
8. **Lockstep-Abhängigkeit (kritisch für die Umsetzung):** Repo-weit referenzieren **76
   Dateien** die Monolith-Dateinamen hart — darunter die 6 dev-Gate-Hooks (session_status,
   gate_memory_complete, gate_git, gate_pipeline, gate_test_coverage,
   gate_packaging_decision), `guard_yaml_valid.py` (harter progress.yaml-Branch, Z. 130),
   `auto_dashboard.py`, das ausgelieferte TEMPLATE `generate_dashboard.py` (liegt in den
   Projekten — kein Hook), die 4 Scaffold-/Init-Skripte, `kit_checks.py`, `retro.py`, die
   Cross-Kit-Kopien (office/research), Verfassungen/SKILLs, `gate_packaging_decision`↔
   `architecture.yaml` und die globale Entry-Gate-Datei (`user/claude/CLAUDE.md`). Die
   vollständige Liste erzeugt Phase 0 (II.11/0).

## I.2 Diagnose

Nicht belegbar ist "Opus ist dümmer geworden". Belegbar sind: immer größere aktive Kontexte,
mehrere konkurrierende Sources of Truth (progress.yaml + Dashboard + Snapshots +
Agent-Memories + Transkript-Skim), Prozessregeln als Prosa statt Zustandsmaschine,
Agentenstarts ohne persistierte Arbeit, historische/verworfene Inhalte im aktiven Kontext.
Die drei User-Thesen (mehr Doku ≠ mehr Kontrolle; zu viele Sources of Truth; konkrete
Anforderungen als Prosa behandelt) sind vollständig bestätigt.

## I.3 User-Entscheidungen (2026-07-20, verbindlich)

1. **Ledger:** Append-only vollständig abgeschafft. Edits erlaubt, immer validierungspflichtig;
   git-History + Evidence = Audit-Trail.
2. **Backlog:** Einzeldateien aktiv/archiv + generierter kompakter Index.
3. **Scope:** Dieser Auftrag liefert das Harness (Kits V2 + Migrations-Tooling + Tests).
   Projekt-Migrationen sind Folgearbeit.

---

# Teil II — V2-Spezifikation (einzig geltende Fassung)

## II.1 Rollenmodell

- **Product Orchestrator** ist der User-facing-Name des Default-Leads (dev/research/office).
  Interne Agent-IDs `project-manager`/`office-manager` bleiben (kein ID-Churn; Umbenennung
  verbessert kein Verhalten und vergrößert den Lockstep-Umbau).
- Der Orchestrator: erfasst jeden Wunsch vor Delegation, spiegelt sein Verständnis, fragt nur
  produktrelevante Lücken, zeigt Ziel/AC/Invarianten/Out-of-Scope, holt die passende
  Userfreigabe ein, legt Tasks vor jedem Spezialistenaufruf an, kontrolliert State und Scope,
  schreibt keinen Produktcode. Er exploriert selbst read-only; bestätigte Informationen werden
  nie erneut abgefragt.
- Spezialisten (Architect, Frontend, Backend, QA als Kern; Designer, Research, DevOps,
  Office-Rollen situativ) verändern den kanonischen Zustand nicht — sie liefern kompakte
  Result-Envelopes (≤4 KB), die der Orchestrator über den State-Kernel übernimmt.
- Der Auditor ist keine Station in der Delivery-Kette mehr, läuft aber als VERPFLICHTENDE
  Routine nach festem Takt (wöchentlich bei aktiven Projekten + ereignisbasiert — Details
  II.10a), legitimiert durch eine widerrufbare `APR.kind: routine`-Freigabe.

## II.2 Zustandsmodell und IDs

**Eine ID-Konvention:** V2 verwendet konsequent `PR-xxxx` für Product Requirements; ein
importiertes V1-Item bekommt eine neue V2-ID und behält seinen früheren Namen als WERT unter
`legacy_fields.legacy_id` (`kernel/migrate.py`) — kein Verweisfeld, sondern die Herkunft des
Datensatzes. (Diese Zeile nannte bis 2026-08-04 ein Feld namens `legacy_ids`, das nie existiert
hat; sie war der letzte Ort dieser Behauptung außerhalb der Korrekturen, die sie benennen.)
Ablauf: neuer eigenständiger Wunsch →
Draft-PR (kein FR→PRD-Umweg); Wunsch zu bestehendem PR → FR (Inbox); Änderung an bestätigter
Revision → CR.

| Typ | Bedeutung |
|---|---|
| PR | Führende User-Ebene: Produktziel, AC, Invarianten, Scope |
| FR | Inbox-Wunsch — noch keinem PR zugeordnet oder zu einem bestehenden (`related_pr` optional) |
| CR | Änderung einer bereits freigegebenen PR-Revision |
| BUG | Abweichung vom bestätigten Verhalten |
| SR | Technischer Vertrag unter einem PR |
| TSK | Ausführbarer Auftrag für genau eine Rolle (= Work Order, keine Extra-Datei) |
| PROC | Wiederverwendbares Office-Verfahren (`derives_from` optional — Standalone zulässig) |
| INV | Projektweite Invariante — nur bei echter Wiederverwendung; sonst lebt die Invariante im PR/Design |
| APR | Userfreigabe einer konkreten Revision oder Analyse |
| ARC | Architekturdiagramm (`.drawio.svg`) — kein eigener Statusautomat, fährt auf dem Promotion-Pfad (II.6a) |
| WFR | Wireframe (`.drawio.svg`) — Scope-Level-Designreferenz vor der HTML-Revision (II.6a) |
| Evidence | Test-/Review-/Abnahmebeleg ohne eigenen Projektstatus |

**Dateistruktur (einzige):**

```
project_memory/
  product/active/PR-0001.yaml      inbox/active/FR-0001.yaml
  product/masterplan.md            # eingefrorenes Discovery-Artefakt (keine Statusquelle)
  changes/active/CR-0001.yaml      bugs/active/BUG-0001.yaml
  system/active/SR-0001.yaml       tasks/active/TSK-0001.yaml
  procedures/active/PROC-0001.yaml (office)
  design/active/  design/revisions/DSN-0001.html   # eingefrorene freigegebene Revisionen
  design/wireframes/WFR-0001.rNN.drawio.svg        # eingefrorene freigegebene Wireframes (II.6a)
  architecture/active/ARC-0001.drawio.svg (+ ARC-0001.yaml)
  architecture/revisions/          # eingefrorene freigegebene ARC-Revisionen
  decisions/active/                approvals/APR-0001.yaml
  evidence/                        archive/<type>/<year>/
  invariants/active/INV-0001.yaml  # nur bei echter Wiederverwendung (sonst im PR/Design)
  staging/<task_id>/               # nichtkanonische Vorschläge (Designer/Architect)
  staging/<ROOT-ID>/               # Vor-Task-Artefakte (z. B. small-WFR vor scope-Freigabe)
  generated/{index.yaml, session_brief.yaml, dashboard.html}   # NICHT committet
```

Regeln: eine Datei = ein Item; Geschlossenes/Verworfenes verlässt den aktiven Kontext;
index/session_brief/dashboard sind vollständig regenerierbar und werden NIE manuell gepflegt;
Historie liegt in Git, nicht als Changelog in aktiven Dateien; progress.yaml, Dashboard-History
und narrative Statuslogs entfallen als Sources of Truth. **Nicht committet werden**
`kit_state.json`, `generated/**` und der Kernel-Lock (Scaffold-.gitignore) — alles
regenerierbar; das verhindert zugleich Merge-Konflikte generierter Artefakte. Archivpfade
sind deterministisch (`archive/<type>/<year>/<ID>.yaml`) — verhindert
Rename/Rename-Konflikte bei parallelem Archivieren.

**PR-Pflichtfelder:** id, title, class, status, problem, goal, user_story (optional bei
technical_enabler), acceptance_criteria [{id,text}], invariants, out_of_scope, priority,
revision, approval_ref.
**TSK-Pflichtfelder:** id, product_requirement, root_revision, derives_from, type,
assigned_role, status, acceptance_refs, required_inputs, allowed_scope, forbidden_scope,
expected_outputs, dependencies, design_ref (Pflicht nur, wenn für den UI-Scope ein bestätigtes
Design existiert). Zusätzlich optionale, vom KERNEL gesetzte Zeitstempel
(created/leased_at/started/completed); Commit-/QA-Belege leben in Evidence
(`kind: acceptance` referenziert commit_hash), nicht am TSK; nicht abgebildete V1-Felder
wandern nach `legacy_fields` statt verloren zu gehen.
**Weitere Pflichtfelder (vor Phase 1 fixiert, IDs immer `<TYP>-nnnn`):**
- FR: id, title, status, related_pr (optional), request_text, triage_result, created.
- CR: id, title, status, target_pr, target_revision, change_description,
  acceptance_criteria, revision, approval_ref.
- BUG: id, title, status, related_pr, observed, expected, repro, severity,
  acceptance_criteria (Fix-Kriterien), approval_ref.
- SR: id, title, status, derives_from (PR/RQ), contract (technischer Vertrag),
  affected_components, revision.
- PROC: id, title, status, derives_from (optional), steps, roles, approved_hash, revision,
  approval_ref.
- INV: id, text/value, scope, source (PR/DSN), check `{kind: test|script,
  ref: <pytest-nodeid|pfad::test>}`, status. Der State-Validator (fail-closed) prüft
  EXISTENZ und Sammelbarkeit des referenzierten Tests; fehlt er, gilt die Invariante als
  `unverified` und blockiert Merge/Abnahme.
- APR: id, kind, item, revision, subject_manifest_hash, request_id, mint_code, approved_at,
  expires (routine/analysis), revoked (bool).
- ARC (Companion-YAML): id, title, scope, derives_from [SR/PR], revision, approval_ref
  (leer bis eingefroren), diagram_hash, assets (Manifest mit Hashes ODER self-contained),
  render_check.
- WFR (Companion-YAML): id, title, derives_from [PR/RQ], revision, diagram_hash,
  render_check, scope_apr_ref (gesetzt beim Einfrieren über die scope-Freigabe — der WFR
  trägt keine eigene APR).
- DSN (Manifest-YAML neben der eingefrorenen Revision): id, revision, file_hash, root
  (PR/RQ — die Bindung, über die der Referenzgraph läuft), root_revision, frozen_at.
  Wie ARC/WFR ohne eigenen Statusautomaten; Zustand = Ort + Wurzelrevision.
- Decision: id, title, status (VALID|SUPERSEDED), context, decision, consequences, source.
- Evidence: id, kind (test|review|acceptance|audit), related (das beurteilte Item — TSK/PR/RQ/EXP,
  bei `audit` auch ein projektweiter Wurzelbezug, im office-Kit ein PROC), **result (pass|fail)**,
  summary, artifact_refs, created — trägt NIE eigenen Projektstatus. `result` ist eine Ergänzung
  aus der gate_git-Runde 2026-07-27: Evidence trägt keinen Status, muss aber ein URTEIL tragen,
  sonst kann der Merge-Gate den bestandenen Lauf nicht vom gescheiterten unterscheiden und würde
  auf der blossen EXISTENZ eines Berichts öffnen. Binär mit Absicht — ein „inconclusive" wäre der
  Wert, auf den kein Gate handeln kann; ein Lauf, der nicht entscheiden konnte, ist ein `fail` mit
  Begründung im `summary` (II.10a: ein Teillauf ist keine Merge-Evidenz). Ein Evidence-Item ist ein
  PROTOKOLL: nach dem Erfassen unveränderlich, abgelöst nur durch ein neueres Urteil. `related` und
  `artifact_refs` müssen etwas NENNEN — eine leere Liste ist dort dieselbe Aussage wie ein
  fehlendes Feld (Nachtrag Prüfrunde 9): `result` ist die Behauptung und `summary` die Prosa dazu,
  die Referenz ist das einzige Feld, das aus dem Protokoll hinaus auf etwas Nachlesbares zeigt —
  und `gate_git` öffnet einen Merge auf diesem Protokoll.

**Freigaben:** `APR.kind ∈ {analysis, scope, delivery, acceptance, routine}` — `routine`
(z. B. Auditor-Takt) ist gebunden an Rolle, Read-only-Scope, Trigger, Ablaufdatum und
jederzeit widerrufbar. Gehasht wird je Art ein deterministisch erzeugtes
**`subject_manifest`**:
- `analysis`: Analysefrage, Read-only-Scope, erwartetes Ergebnis, gelistete Analyse-Tasks
- `scope`: problem, goal, acceptance_criteria, invariants, out_of_scope, verbindliche
  Designreferenzen (inkl. freigegebener Wireframes, II.6a)
- `delivery`: Root-Revision, SRs, Architektur (inkl. eingefrorener ARC-Hashes), Tasks, Risiken
- `acceptance`: ausgelieferte Revision/Commit und Evidence-Referenzen
- `routine`: Rolle, Scope, Trigger, Takt, Ablaufdatum

**Bündelung (User-Entscheid 2026-07-24):** EINE analysis- oder scope-APR darf MEHRERE im
subject_manifest GELISTETE Analyse-Tasks decken (z. B. „Architect + QA untersuchen X
read-only"). Persistierungs- und Auditpflicht pro Task bleiben unverändert — nur die
Frage-Frequenz sinkt.

**Hash-Kanonisierung:** kanonisches JSON (sortierte Keys, NFC-normalisierter
Unicode) + `hash_schema_version` — NICHT yaml.safe_dump (PyYAML-versionsabhängig; das heutige
proc_hash.py nutzt genau das, ohne NFC und ohne Versionsfeld — verifiziert). Bestehende
PROC-Hashes sind Legacy: beim kuratierten Import werden sie NEU BERECHNET, aber es wird KEINE
APR erzeugt (Freigabe nur durch echte Useraktion). Jede Änderung gehashter Felder entwertet
die Freigabe (typabhängige Invalidierung, siehe Statusautomaten).

**Beweisbare Freigabe-Herkunft (Zwei-Phasen-Protokoll):** Ein manuelles `approved_by: user`
genügt nicht.
1. Der Kernel schreibt VOR der Frage einen unveränderlichen **Pending-Approval-Request**
   (Request-ID, Item, Revision, Content-Hash, APR-Art, Ablaufzeit) und **erzeugt die
   vollständige strukturierte Freigabefrage deterministisch selbst** — inkl. der Optionen und
   des Markers `[APR-REQ:<request_id>]` im Fragetext. Pro Freigabe genau EINE Frage mit den
   Optionen **Freigeben / Ändern / Ablehnen**. *Stand seit FR-0095 (TSK-0153, 2026-09-26): die
   Frage ist eine ruhige Karte ohne Request-ID, Pfad und Prüfsumme; die Hooks finden die Anfrage
   über den Mint-Code im Freigabe-Label (`approvals.pending_request_by_code`), und „markiert“ heißt
   im Folgenden: mit Freigabe-Label `Freigeben [<code>]` (oder mit der ersten Kartenzeile
   `approvals.CARD_PREFIX`, dann über den genauen Kartentext gefunden).*
2. Ein **PreToolUse-Hook auf `AskUserQuestion`** behandelt NUR markierte Fragen als
   Freigabefragen und verlangt für sie **exakte Übereinstimmung** von Fragetext, Header UND
   allen Optionen mit der Kernel-generierten Frage (String-Gleichheit, keine semantische
   Prüfung — das Modell darf den Frageinhalt nicht kontrollieren). Markerlose Fragen
   passieren immer, prägen aber nie — Spoofing bleibt wirkungslos, weil ausschließlich der
   Token-Pfad State bewegt und Downstream fail-closed ist.
3. Ein **PostToolUse-Hook** liest die Antwort aus dem Tool-Result
   (`toolUseResult.answers`) und prägt NUR beim wortgleichen Freigabe-Label den einmaligen
   Token (gebunden an Request-ID, Mint-Code, Item, Revision, Hash, APR-Art).
   "Ändern"/"Ablehnen"/sonstiger Text, abgelaufene oder nicht passende Requests prägen nie;
   Freitext invalidiert den Pending-Request NICHT automatisch (er läuft per TTL aus).

**MINT-CODE statt Options-Identität (empirischer Befund 2026-07-24, Spike S2b — ersetzt die
v2.0-Forderung):** Claude Code 2.1.219 liefert
`toolUseResult.answers = {Fragetext: Antwort-STRING}`. Eine geklickte Option und ein in die
stets vorhandene „Other"-Zeile GETIPPTER Text sind **strukturell ununterscheidbar** (an
echten Session-Transkripten verifiziert: geklickte Labels und eine getippte Freitextantwort
stehen in exakt derselben Form). Die ursprüngliche Forderung „Token bindet an die
Options-IDENTITÄT, nie an den Antwort-String" ist auf dieser Plattform **nicht
implementierbar**. Ersatzmechanismus mit gleicher Schutzwirkung gegen versehentliche
Freigaben: Der Kernel erzeugt je Request einen **Mint-Code** (6 Hex-Zeichen), der
AUSSCHLIESSLICH im Freigabe-Label steht (`Freigeben [7f3a2c]`) — nie im Fragetext. Geprägt
wird nur bei wortgleicher Übereinstimmung. Folgen: beiläufiger Freitext („ok", „ja",
„freigeben") prägt NIE; das Modell kann ohnehin keine Antworten erzeugen (die Plattform
schreibt sie, und der PreToolUse-Hook fixiert die Frage, die der User gesehen hat).
**Ehrlich ausgewiesenes Restrisiko:** Ein User, der den Code bewusst abtippt, prägt — er ist
aber die freigebende Instanz selbst. Der Capability-Wert für `approval_provenance` ist
deshalb ein User-Entscheid (streng: `unverified` → audited; nach amendierter Definition:
`verified` mit dokumentiertem Restrisiko).
Kann ein Provider diese Herkunft nicht beweisen, gilt für Freigaben dort
`approval_provenance: unverified` → Gesamtmodus höchstens `audited`.

**Kit-Root-Typen im gemeinsamen Kernel:** dev/office: `PR`; research: `RQ` (darunter `HYP`
und `EXP`). Tasks, Freigaben, Dispatch und Evidence sind kit-übergreifend identisch.

**Research-Struktur (vollständig, Teil von V2):** Dateistruktur ergänzt um
`research/active/RQ-0001.yaml`, `hypotheses/active/HYP-0001.yaml`,
`experiments/active/EXP-0001.yaml`. Beziehungen: HYP `derives_from` RQ; EXP `derives_from`
HYP (oder direkt RQ bei explorativen Studien); TSK `derives_from` EXP/RQ.
RQ-Pflichtfelder: id, title, class, status, question, motivation, acceptance_criteria
(= Beantwortungskriterien), out_of_scope, priority, revision, approval_ref.
HYP: id, derives_from, statement, testable_prediction, status — HYP wird NICHT eigenständig
freigegeben (kein approval_ref); es fährt auf der RQ-Scope-Freigabe.
EXP: id, derives_from, design (gehasht), variables, success_criteria, status, evidence_refs,
revision, approval_ref — EXP trägt die delivery-Freigabe bei class large.
`TSK.root_revision` denormalisiert die RQ-Revision über die Kette TSK→EXP→HYP→RQ.
E2E: Frage → Draft-RQ → scope-Freigabe → HYP → EXP-Design (delivery-Freigabe bei class
large) → Ausführungs-TSKs → Evidence → Analyse → RQ beantwortet → Abnahme → Archiv.

**Statusautomaten (verbindlich — Übergänge nur via Kernel `transition`, alles andere ist
Schema-Fehler):**

| Typ | Zustände (Reihenfolge) | Terminal |
|---|---|---|
| PR / RQ | DRAFT → APPROVED → IN_DELIVERY → DELIVERED → ACCEPTED | ACCEPTED, REJECTED, SUPERSEDED |
| FR | OPEN → TRIAGED | MERGED, CONVERTED, REJECTED |
| CR | DRAFT → APPROVED → APPLIED | APPLIED, REJECTED |
| BUG | OPEN → TRIAGED → APPROVED → FIXED → VERIFIED | VERIFIED, REJECTED, DUPLICATE |
| SR | PROPOSED → ACCEPTED | SUPERSEDED |
| TSK | DRAFT → READY → LEASED → IN_PROGRESS → SUBMITTED → DONE → VALIDATED; IN_PROGRESS\|SUBMITTED\|DONE → FAILED | VALIDATED, CANCELLED |
| PROC | DRAFT → APPROVED → ACTIVE | RETIRED |
| HYP | PROPOSED → TESTING | SUPPORTED, REFUTED, INCONCLUSIVE |
| EXP | DESIGNED → APPROVED → RUNNING → COMPLETED → ANALYZED | ANALYZED, ABORTED |

TSK-Fußnote: SUBMITTED→DONE = der Orchestrator übernimmt den Result-Envelope über den
Kernel; DONE→VALIDATED = eine QA-Evidence referenziert die abgedeckten AC/Invarianten.
ARC/WFR haben bewusst KEINEN eigenen Automaten (II.6a: Zustand = Ort + approval_ref).

Querregeln: BLOCKED ist ein Flag (blocked_by), kein Status. TSK-Rückwege explizit:
LEASED → READY bei Lease-Timeout/Spawnfehler; FAILED → READY nur bei genehmigtem Retry,
sonst FAILED → CANCELLED; VALIDATED und CANCELLED sind terminal.

**Freigabepflichtige Übergänge (Implementierungsnachtrag 2026-07-31):** Welche Kante eine
Userfreigabe braucht, wird ABGELEITET statt gelistet. `approvals.APPROVAL_TRANSITIONS` sagt
bereits, welche Kante eine Freigabe-Art BEGEHT (der Mint führt sie selbst aus); rückwärts gelesen
sagt dieselbe Tabelle, welche Kante ohne eine solche Freigabe gesperrt ist. `transition` verlangt
dafür eine gültige, nicht widerrufene, inhaltlich passende APR dieser Art, deren Herkunft über den
konsumierten Request beweisbar ist — und es gibt bewusst KEIN Flag, das das abschaltet (II.4:
„Bootstrap ist kein Config-Flag"). **Die Sperre hat einen begehbaren Gegenpart, und ohne den wäre sie
eine Sackgasse:** `request-approval <kind> <ITEM-ID>` schreibt den Pending-Request und gibt die
kernelgenerierte Frage aus (Phase 1); geprägt wird weiterhin ausschliesslich durch die ANTWORT des Users
(Phase 3, `gate_approval` als PostToolUse). Vor diesem Kommando hatte `create_pending_request` im
ausgelieferten Baum keinen Aufrufer — ein Wurzel-Item wäre nie aus DRAFT gekommen. Anlass war eine Messung: `transition PR-0002 APPROVED` bewegte
ein Wurzel-Item an allen acht PreToolUse-Gates vorbei aus seinem DRAFT, während `gate_git` einen
Merge genau deshalb verweigert, weil ein Item im Anfangsstatus als „nicht freigegeben" gilt.
Zwei Folgen sind USERENTSCHEIDE und ausdrücklich keine Implementierungsdetails:
- Die Ableitung fordert die delivery-Freigabe für `APPROVED → IN_DELIVERY` in JEDER Risikoklasse,
  während die Klassentabelle unten die „zweite Delivery-Freigabe" nur für `large` nennt. Eine
  Ausnahme über `class` wäre eine zweite Regel neben der Ableitung (und `class` existiert nicht auf
  jedem betroffenen Typ), deshalb ist die Verschärfung BENANNT statt eingebaut.
- `SR` (PROPOSED → ACCEPTED) bleibt ungesperrt, weil keine APR-Art ein `subject_manifest` für einen
  SR hat. Das zu ändern heißt, zuerst eine Art mit einem Manifest zu definieren — Spezifikation,
  nicht Implementierung. Aus demselben Grund deckt das scope-Manifest bei `PROC` und `SR` heute
  nur `{item, revision}` ab (`_SCOPE_FIELDS` nennt keins ihrer Inhaltsfelder), sodass dort ein
  Edit AM Kernel VORBEI vom Content-Hash nicht gefangen wird.

**Freigabe-Invalidierung (typabhängig):** Inhaltsänderung an gehashten Feldern JEDES Items
mit aktueller approval_ref — egal in welchem Status, auch IN_DELIVERY/DELIVERED — geschieht
ATOMAR: Revision erhöhen, approval_ref löschen, Status auf den typabhängigen
Invalidierungszustand setzen:

| Typ | Invalidierungsziel |
|---|---|
| PR / RQ / CR / PROC | DRAFT |
| BUG | TRIAGED |
| SR | PROPOSED |
| EXP | DESIGNED |

(HYP steht bewusst NICHT in dieser Tabelle — es trägt kein approval_ref und fährt auf der
RQ-Scope-Freigabe; ARC/WFR invalidieren über die Revision ihres referenzierten PR/SR bzw.
das scope-/delivery-Manifest, II.6a.)

Tasks einer entwerteten Root-Revision dürfen weder neu geleast noch promotet werden
(laufende Leases laufen aus; SUBMITTED-Ergebnisse warten auf Re-Freigabe). Terminale Items
wandern nach archive/. Neue Zustände sind eine Spezifikationsänderung, keine
Implementierungsentscheidung.

**Risikoklassen:** small = Scope-Freigabe + direkter Task + automatisierte Prüfung
(Architect/Designer/QA-Agent können entfallen). normal = + technische Zerlegung, SRs, QA.
large = + Architektur-/Designplan, Risiken, zweite Delivery-Freigabe. Die Klasse reduziert
Agentenketten, niemals Persistierungs- oder Freigabepflicht. **Kein Subagent ohne
Userfreigabe** — auch begrenzte Draft-Analyse braucht `APR.kind: analysis` (Bündelung
mehrerer gelisteter Analyse-Tasks in einer APR zulässig, s. o.).
**UI-Zusatz (User-Entscheid 2026-07-24):** Die Wireframe-Stufe (II.6a) ist bei JEDEM
UI-Scope verpflichtend, auch class small. Bei small darf der ORCHESTRATOR den WFR selbst
erstellen und mit dem User iterieren (Planungsartefakt wie AC-Text, KEIN Produktcode —
„Designer kann entfallen" bleibt für small wahr); die HTML-/DSN-Stufe bleibt bei small
optional (bestehende DSN-Revision genügt bzw. expliziter User-Entscheid). Ab class normal
erstellt die Designerin WFR und DSN. Verzicht auf den Wireframe nur per explizitem
User-Decision-Item — nie durch den Orchestrator.

## II.3 Verbindlicher Ablauf

1. User äußert Wunsch → Orchestrator speichert das erste Root-Item GEMÄSS KIT (dev/office:
   Draft-PR, research: Draft-RQ) bzw. FR / CR / BUG — vor jeder Delegation.
2. Orchestrator zeigt Verständnis, AC, Invarianten, Out-of-Scope, offene Produktfragen.
   Bei UI-Scopes gehört dazu die Wireframe-Iteration (II.6a): WFR entwerfen → mit dem User
   iterieren → der freigegebene WFR wird Teil des scope-Manifests.
3. Userbestätigung → APR mit Revisions-Hash.
4. Orchestrator legt Analyse-/Ausführungstasks an (Vorschläge dürfen von Spezialisten kommen,
   werden aber VOR Implementierung persistiert). Eine analysis-/scope-APR kann mehrere
   gelistete Analyse-Tasks decken (II.2, Bündelung).
5. Dispatch nur über strukturierten Header (II.4); Analyseagenten implementieren nicht im
   selben Auftrag.
6. Spezialisten liefern Result-Envelope; QA prüft gegen referenzierte AC/Invarianten.
7. Scope-Änderung → FR/CR, entwertet ggf. die Freigabe. Nach Userabnahme → Archiv.

## II.4 State-Kernel und Enforcement

**State-Kernel** (ein Python-Kern, von Hooks/Dashboard/Scaffold/Migration gemeinsam genutzt):
`capture, approve, create-task, dispatch, submit-result, transition, archive, generate-index,
generate-session-brief, validate, migrate --dry-run, doctor`. Index-Update atomar in der
State-Operation — kein PostToolUse-Regenerator, der einen zweiten inkonsistenten Zustand
erzeugen kann.

**Nebenläufigkeit & Locking (neu in v2.1 — Garantie-Voraussetzung, kein Detail):** Jede
State-Operation läuft unter einem prozessübergreifenden Lock (atomar via
`O_CREAT|O_EXCL`-Lockdatei mit PID+TTL, Windows-tauglich, Stale-Break nach TTL); der Lock
umfasst Item-Write UND Index-Regeneration. Ohne diesen Lock sind „zweiter Claim blockiert"
und „Index atomar" nicht implementierbar. ID-Vergabe `<TYP>-nnnn` = Max-Scan über
active+archive unter Lock (kein Counter-File). Persistenz: Temp-Datei + `os.replace`;
OneDrive-Ausnahme dokumentiert (Sync pausieren). Windows-Pfade: der Kernel nutzt
Extended-Length-Pfade (`\\?\`) für open/replace UND der State-Validator warnt bei absoluten
Pfaden >240 Zeichen. Hooks lesen stdin BEGRENZT (bounded read); Work-Orders REFERENZIEREN
Staging-Inhalte, statt sie einzubetten. `harness doctor` meldet gehaltene/verwaiste Locks.
Eine Session, die den Lock nicht erhält, wartet/retryt — sie überspringt nie still.

**Dispatch mit Lease (kein direktes IN_PROGRESS aus dem PreToolUse-Hook):**
READY → kurzlebige Dispatch-Lease mit Nonce und **TTL** → Header
`HARNESS_DISPATCH {"task_id":"TSK-0042","root_revision":3,"lease":"<nonce>"}`.
Lebenszyklus: PreToolUse validiert die Lease; die Bindung des Kindes (SubagentStart) oder
PostToolUse auf den Spawn, was zuerst kommt (BUG-0314): Erfolg → IN_PROGRESS, Fehlschlag → sofort zurück auf READY; verwaiste Lease → nach TTL automatisch
READY (kein Task bleibt durch abgebrochene Agentenstarts hängen). Das Gate parst
AUSSCHLIESSLICH den Header, nie freie Prompt-Prosa. Ein paralleler zweiter Claim wird
blockiert. Beim Dispatch bindet der Kernel zusätzlich `lease → agent_id` (Hook-Payloads
tragen bei Subagent-Tool-Calls eine agent_id) — die Grundlage des Write-Scope-Gates
(Schicht 3).

**Vorschlagsbereich für Spezialisten mit Lebenszyklus:** Designer/Architect — und bei
class small der Orchestrator für den WFR — schreiben große Vorschläge nach
`staging/<task_id>/` (nichtkanonisch, nie bei Sessionstart oder im Dashboard geladen; im
Session-Brief nur als Pointer); der 4-KB-Cap gilt nur für den Result-Envelope, der
Staging-Inhalte referenziert. Vor-Task-Artefakte (z. B. der small-WFR vor der
scope-Freigabe) nutzen den Staging-Schlüssel `staging/<ROOT-ID>/`. Lebenszyklus: nach
Freigabe promotet der Kernel den Inhalt in den kanonischen Zustand und LEERT das
Staging-Verzeichnis; nach Ablehnung wird es ARCHIVIERT (nie still gelöscht —
"History-Prune" bedeutet überall archivieren); bei Taskabschluss räumt
`submit-result`/`archive` das Verzeichnis nach denselben Regeln — der State-Validator flaggt
verwaiste Staging-Ordner; „verwaist" heißt: weder aktiver Task NOCH aktives Root-Item.

**Gate-Schichten:**
1. Spawn-Form: installierte Rolle + strukturierter Header (heutiger `guard_agent_spawn`).
2. Dispatch-Gate: Task existiert + READY-Lease, Rollenmatch, Root-Revision + gültiger
   APR-Hash, Abhängigkeiten erfüllt, erforderliche design_ref/AC-Referenzen vorhanden.
3. Write-Scope: Spezialisten nur im freigegebenen Datei-Scope; kanonischer State nur über den
   Kernel. Mechanik: PreToolUse(Edit|Write) löst `agent_id → TSK → allowed_scope` auf und
   erzwingt den Scope — auch bei parallelen Leases sauber attribuierbar. Ist die
   Spawn-Zeit-Bindung der agent_id auf einem Provider nicht Ende-zu-Ende beweisbar, gilt
   `state_write_protection: unverified` → Modus höchstens `audited`.
4. State-Validator: vollständige Schemas, Referenzgraph, Statusübergänge, Budgets, verwaiste
   Items — UND der Content-Hash JEDES aktiven Items wird gegen den hinterlegten APR-Hash
   gerechnet: Out-of-band-Edits (IDE, am Kernel vorbei) invalidieren die Freigabe
   fail-closed („out-of-band edit invalidated approval; re-approve or revert").
5. CI/Merge: State-Validator + Tests + Evidence grün + ID-Eindeutigkeit über Branches
   (zwei Branches, gleiche neue Item-ID → Merge-Block).

**Fail-closed-Klassifizierung:** ALLE Integritätsgates sind fail-closed (Dispatch, Approval,
State-Write, Filing, Ledger-Folgegates, Git/Merge, Harness-Selbstschutz): leerer, beschädigter
oder unbekannter Zustand blockiert; catch-all im Hook liefert bei internem Fehler exit 2 +
Diagnose (ein crashender Hook würde in Claude Code sonst durchlassen). Nur Komfort-Hooks
(Formatierung, Dashboard, Benachrichtigungen) sind fail-open. Präzisierung: In PostToolUse
ist KEIN State-Compute erlaubt (verhindert eine zweite Wahrheit); reine Formatierung und das
Setzen eines Index-STALE-Dirty-Flags sind zulässig. Das V1-Bootstrap-Loch von
gate_proc_approved (leerer PROC-Bestand ließ Spawns passieren) entfällt: leerer Zustand
blockiert — außer im expliziten Installer-Bootstrap (unten).

**Bootstrap/Migration ist kein Config-Flag** (der Lead könnte sein eigenes Gate umgehen):
aktivierbar nur über den expliziten Installer-/Migrationsbefehl mit Lock, leerem Zielzustand
und Userbestätigung.

**Provider-Parität:** Claude erhält den getesteten veto-fähigen PreToolUse-Pfad auf
Agent|Task. Für Codex ist mechanisch belegt (`gen_provider_artifacts.py`, deklarierte Lücke
`CODEX_UNSUPPORTED_TOOLS`: `codex_matchers("Agent|Task") == ()`,
`codex_matchers("AskUserQuestion") == ()`), dass Dispatch-Veto und Approval-Provenance dort NICHT hookbar
sind → `spawn_veto` und `approval_provenance` sind auf Codex konstruktionsbedingt
`unverified`, der Gesamtmodus dort höchstens `audited` (jeder Start protokolliert und
nachträglich validiert); ein angeforderter `hard`-Modus deaktiviert dort Delegation.
`state_write_protection` ist auch auf Codex erreichbar (Edit|Write→apply_patch mappt,
agent_id vorhanden — Spike S3). Provider-Artefakte entstehen nur durch den vollständigen,
userbestätigten Scaffold-Lauf (`gen_provider_artifacts.py`).

**Aktivierungsprüfung:** `harness doctor` (read-only): Kit-Version, Lead-Rolle, Spezialisten,
Providerkonfiguration, Hook-Bundle-Hash, State-Version, Trust-Status, gehaltene Locks,
Capability-Matrix; nicht Feststellbares wird als `unknown` gemeldet. Keine SessionStart-Probe
schreibt in den Projektzustand.

## II.5 Memory- und Kontext-Rückbau (einheitliche Budgets)

- Generierter Session-Bootstrap ≤25 KB (`kernel/schemas/session_brief.yaml: max_serialized_bytes`).
- Lead-Instruktionspaket: **keine gegriffene Obergrenze mehr, sondern eine Ratsche.** Die Grenze ist
  pro Kit die aufgezeichnete Messung in `tools/lead_package_sizes.json`; `tools/validate.py` lässt
  kein Paket über seinen eigenen Rekord wachsen und **scheitert dabei hart** — die Zusage aus
  II.11/3 ist damit eingelöst, und sie ist einlösbar, weil ein Rekord erfüllt startet. Der Rekord
  bewegt sich nur über `python tools/record_lead_package_sizes.py --write --note "<Grund>"`, das je
  Kit eine Zeile in das Journal von `docs/reviews/phase0-disposition.md` schreibt. **Warum keine
  Zahl mehr:** die alte war „25 KB" zu 1024 B gelesen — eine Typografie-Entscheidung, keine
  Rechnung. Sie wurde nie gegen den Inhalt gerechnet, wog bis 2026-08-02 eine Datei mit, die gar
  nicht lädt, und wurde von allen drei Kits um mehrere KB verfehlt, auch nach der Entdopplungsrunde
  vom 2026-08-03, die zwischen den beiden geladenen Dateien misst statt schätzt. Dazwischen liegt
  keine Füllung, sondern Regeln mit Paritätsklassifikation `behalten` plus die Arbeitsschleife, die
  die Verfassungen tragen, WEIL das Lead-SKILL nicht lädt. Eine Grenze, die jedes Subjekt dauerhaft
  verfehlt und dabei nur warnt, ist keine Grenze. Ein Aufschlag auf die Messung wäre eine zweite
  gegriffene Zahl neben der gerade entfernten und existiert darum nicht; wer weniger will, kürzt und
  zeichnet neu auf.
- **Zählweise:** Das Paket zählt ALLES sessionfix Geladene — und das ist **agent.md + Verfassung**,
  nicht mehr. Die
  Verfassung lädt via `CLAUDE.md`-Shim (Codex liest `AGENTS.md` nativ) immer mit; das **Lead-SKILL
  lädt NICHT** und zählt darum nicht: gemessen 2026-08-02 in drei Sitzungen und zwei Kits, mit
  Kontrollwörtern am Dateiende und `--tools ""`, kamen Verfassung und agent.md wörtlich an, das
  SKILL fehlte, und die `init`-Zeile des Streams führt es unter `skills` **und** `slash_commands` —
  auf Abruf registriert, nicht injiziert. Was der Lead trotzdem ohne Abruf braucht, steht seither
  als Arbeitsschleife IN der Verfassung (dev/research §5a, office §4a), also innerhalb des
  Budgets. **Eine Definitionsstelle:** die Ableitung, welche Dateien das Paket sind, steht in
  `tools/lead_package.py` (`files()`, `size()`, `ceiling()`); `tools/validate.py` liest von dort
  und benennt in seiner Meldung genau die Dateien, die es gewogen hat. `on_demand_files()` daneben
  ist die andere Hälfte derselben Messung: was Regeln trägt, ohne zu laden (der Sektionspin in
  `tools/test_shortening_net.py` fragt danach).
- **Keine Zeilengrenze mehr für Verfassung und Lead-SKILL.** Die frühere Vorgabe „je ≤150 Zeilen"
  (interim 220, erzwungen in `tools/validate.py`) ist ersatzlos gestrichen, weil sie gemessen
  nichts über Grösse aussagte: die drei Verfassungen hielten 220 nur, weil 31–46 ihrer Zeilen
  110–1 899 Zeichen lang sind (auf 100 Spalten umbrochen: 383/368/394 Zeilen), und ein
  Verdichtungspilot brachte −24,9 % Bytes bei einem Anstieg von 20 auf 36 Zeilen — die
  Zeilengrenze arbeitete also gegen die Byte-Aussage daneben. Eine per-Datei-Byte-Grenze tritt
  NICHT an ihre Stelle: keine Aufteilung des Paketrekords auf seine beiden Dateien folgt aus
  etwas, und eine gegriffene Zahl neben einer gemessenen ist der Fehler, nicht die Reparatur.
  Damit gibt es genau **eine** Grössenaussage über eine Verfassung — die über das Paket, dessen
  Teil sie ist.
- **Kürzungs-Sequenz (verbindlich):** Die Kürzung auf das Paketbudget ist erst zulässig, NACHDEM
  die ersetzenden Gates/Tests stehen (Reihenfolge II.11: Gates vor Kürzung); jede entfernte Regel
  wird in der Paritätsmatrix als „durch Gate/Test ersetzt" belegt. **Verlagern ist keine
  Kürzung:** Text, der vollständig erhalten bleibt und nur aus dem sessionfix geladenen Paket in
  eine Datei umzieht, die beim Sitzungsstart nicht lädt, braucht keine Löschlizenz — er verliert
  seine Startkosten, nicht seinen Inhalt. Erster Fall: die §2-Hooktabelle der drei Verfassungen
  liegt jetzt in `team-kits/<kit>/hooks/ENFORCEMENT.md` (installiert `.claude/hooks/ENFORCEMENT.md`),
  und jede Hook-Verweigerung nennt deren Pfad.
- Aktives Item ≤200 Zeilen/12 KB. Result-Envelope ≤4 KB (Rohlogs nur referenziert).
- MEMORY.md: generierter Index ≤40 Zeilen. Craft-Topic ≤100 Zeilen/8 KB, ≤20 aktive Topics
  pro Rolle. Projektstatus/Tasks/Entscheidungen/Sessionfortschritt sind in Agent-Memory
  verboten; Einweg-Trivia wird Test, Codekommentar, Skill-Fix — oder gar nicht persistiert.
- **Schemata:** Result-Envelope {task_id, role, status_proposal, summary, outputs[],
  evidence[], scope_touched[], followups[]} und session_brief {Kit+Version+Enforcement-Modus,
  aktive PRs mit nächstem Schritt, aktive TSKs, offene Freigaben, Staging-Pointer,
  Budget-Status} werden VOR Phase 1 als Pflichtfeld-SCHEMADATEIEN fixiert (Ablage:
  `team-kits/<kit>/schemas/`, nicht Spec-Prosa).
- Budgets werden durch `guard_memory_budget` (Integritätsgate, fail-closed) + State-Validator
  + CI erzwungen. **Trigger:** agent-memory/** (bei Write), MEMORY.md (bei Write),
  project_memory-Items (bei Kernel-Write), Envelope (bei submit-result) — Triggertabelle als
  Matcher-Konfiguration, nicht Verfassungsprosa. Audit-Logs rotieren bei ~1 MB außerhalb des
  Startkontexts.
- **Latenz:** Integritätsgates sind stdlib-first (keine PyYAML-Importlast im heißen Pfad, wo
  vermeidbar); Latenz ist ein gemessenes p95-Ziel (Richtwert ~300 ms, Warnschwelle 500 ms)
  im CI-Bench — KEIN blockierendes Gate.
- Transkripte sind reine Diagnose/Audit — bei normalem Neustart nicht gelesen; die neue
  Session arbeitet allein aus generated/session_brief.yaml + aktiven Items.
- Kontextschwellen (50 %/70 %) nur als Hinweis, wenn der Host verlässliche Daten liefert —
  kein Scheingate; Autocompact 80 ist keine Qualitätsgarantie und ersetzt keine kleinen
  Sessions. "Real run"-Anekdoten wandern aus Prompts in Regressionstests.

## II.6 Design

- **Design-Promotion:** Der Designer schreibt eine Proposal-Version nach staging/. Nach
  Userfreigabe kopiert der KERNEL sie unveränderlich nach design/revisions/ (Datei + Hash +
  PR-Revision + Freigabezeitpunkt) und aktualisiert design_ref. Externe Assets: Manifest mit
  allen Asset-Hashes, oder die Preview bleibt self-contained. Alte Revisionen archiviert,
  aktive Referenz eindeutig; UI-Tasks bei vorhandenem bestätigtem Design ohne design_ref
  gesperrt.
- Harte Vorgaben werden strukturierte Invarianten mit Test-Referenz, Beispiel:

```yaml
invariants:
  - id: INV-HARDWARE-ORDER
    value: PENDING-USER-DECISION  # CPU,GPU,RAM,STORAGE (Grid-Kanon :8014) vs.
                                  # Memory,Processor,Graphics,Storage (:9216, neuer) —
                                  # Reihenfolge UND Label (ROM vs. STORAGE) entscheidet
                                  # der User in der synaipse-Folgearbeit (II.14/2)
    check: {kind: test, ref: frontend/tests/hardware_order.spec}
```

  (Der v2.0-Beispielwert `[CPU, GPU, RAM, ROM]` war selbst eine Falsch-Transkription — der
  beste Beweis, warum Invarianten strukturiert UND testreferenziert sein müssen. Die
  Anwendung auf synaipse ist Folgearbeit und wird dort vom User entschieden.)
- Widersprüchliche Design-Rulings werden nie automatisch aufgelöst.

## II.6a Architektur- und Wireframe-Artefakte (draw.io; neu in v2.1)

**Kanonisches Format:** Architekturdiagramme und Wireframes sind `.drawio.svg` — zugleich
valides SVG (im Browser, in Markdown und im Dashboard direkt sichtbar) und in der
VS-Code-Extension (hediet.vscode-drawio) editierbar; ein Format, kein Export-Schritt.
Mermaid ist nur noch ephemer im Chat zulässig, nie kanonisch (Paritätsmatrix: das bisherige
Kit-Ruling „Prefer Mermaid over draw.io" wird per User-Entscheid bewusst umgekehrt).
Der Scaffold ergänzt `.vscode/extensions.json` (draw.io-Empfehlung) und liefert
Vorlagen-Diagramme mit definierten Styles; Diagramme bleiben klein — ein Anliegen pro Datei
(Mitigation des LLM-Layout-Risikos bei mxGraph-XML).

**ARC (Architekturdiagramm):** Ablage `architecture/active/ARC-nnnn.drawio.svg` +
Companion-YAML (Felder: II.2). Der Architect-Agent-Memory enthält NUR Pointer auf
ARC-Dateien (II.5). **Promotion nutzt den bestehenden Design-Promotion-Pfad:** Vorschlag in
staging/ → Freigabe → der Kernel friert unveränderlich nach `architecture/revisions/` ein.
**Kein eigener Statusautomat, keine eigene Invalidierungszeile** — der ARC-Zustand ergibt
sich aus Ort + approval_ref; die Freigabe-Invalidierung folgt der Revision des
referenzierten PR/SR (wie design_ref). Der eingefrorene ARC-Hash geht in das
delivery-subject_manifest („Architektur"); ein separater Ref am TSK entfällt.
**Validierung (fail-closed):** Der Kernel prüft bei Promotion die eingebettete mxGraph-XML
auf Wohlgeformtheit und Renderbarkeit; Fehlschlag blockiert die Promotion.
**Auflösung des Monolithen:** Der heutige `architecture.yaml`-Monolith wird aufgelöst
(components/data_flow → SRs bzw. schlankes Architektur-Item); `packaging.method` erhält eine
definierte, gate-lesbare Heimat (Feld am schlanken Architektur-Item + Decision), und
`gate_packaging_decision.py` (heute harter Leser von architecture.yaml:84–89) wird IM SELBEN
atomaren Lockstep-Release umgestellt (II.11/2).

**WFR (Wireframe-Pipeline):** Stufenvertrag mit klaren Prüfgegenständen:
1. `WFR-nnnn.drawio.svg` in staging/ — NUR Layout, Inhaltsblöcke, Flows (keine Farben/Typo).
   Prüffrage an den User: „Ist alles drin? Stimmt die Aufteilung?" — schnelle
   Iterationsrunden.
2. Die Wireframe-Freigabe ist Teil des **scope**-subject_manifest („verbindliche
   Designreferenzen") — der WFR wird gehasht; jede Änderung invalidiert die scope-Freigabe.
   Mit der scope-Freigabe friert der KERNEL den WFR nach `design/wireframes/` ein (Datei +
   Hash + Freigabezeitpunkt; das Staging wird gemäß II.4-Lebenszyklus geräumt); die
   DSN-Revision leitet sich vom eingefrorenen WFR ab. KEIN neuer APR-Kind, KEIN neues
   TSK-Feld (die verbindliche Implementierungsreferenz bleibt design_ref auf die
   eingefrorene DSN-Revision).
3. HTML-Design-Preview (Designerin, self-contained) = die verbindliche visuelle Revision →
   friert als DSN ein (bestehender Mechanismus, II.6). Prüffrage: Look & Feel.
4. Implementierung (React ODER framework-frei — Architect-Decision-Item je Projekt; das Kit
   bleibt framework-agnostisch); UI-TSK verlangt design_ref (unverändert).
**Pflicht (User-Entscheid 2026-07-24):** bei JEDEM UI-Scope, auch small — Details und
small-Sonderweg: II.2 Risikoklassen. Fehlt bei einem UI-Scope der Wireframe im
scope-Manifest → scope-APR blockiert (fail-closed).

## II.7 Dashboard

Der Dashboard-Generator liest generated/index.yaml und die aktiven Item-Dateien zur
GENERIERUNGSZEIT und bettet kompaktes JSON ein; das DOM rendert lazy; Archiv/Volltext werden
nie eingebettet (V1 `generate_dashboard.py` arbeitet bereits so — dies präzisiert die
v2.0-Formulierung „Details per Item-Datei bei Aufruf"). Sichten: Product (Default: aktive
PRs mit Status/Blocker/nächstem Schritt), Delivery (Task-Board, Erledigtes verborgen),
System (SRs/Abhängigkeiten), Decisions, Archive. Max. 50 Items pro Seite, Details lazy, kein
Archiv/Volltext im initialen DOM, keine committete Dashboard-History (Release-Snapshots
optional als Buildartefakte), Dashboard schreibt keinen Status. Funktionsfähig offline per
Doppelklick (file://).

## II.8 Kit-Updates

Eine providerneutrale `.claude/kit_state.json` als Zustandsautomat:
`update_available → approved → applying → hooks_trust_required → restart_required → active`;
zusätzlich eine **Enforcement-Capability-Matrix** statt eines einzelnen Flags:
`capabilities: {spawn_veto, approval_provenance, hook_trust, state_write_protection}`, jede
einzeln `verified|unverified`. Gesamtstatus `enforcement: hard` NUR wenn alle notwendigen
Fähigkeiten verifiziert sind; sonst `audited`. Die Abnahmeforderung "0 Starts ohne
Userfreigabe" gilt beweisbar nur im Hard-Modus; im Audited-Modus wird sie als geprüfte
Policy ausgewiesen. `harness doctor` meldet die Matrix; nicht Feststellbares bleibt
`unverified`. `kit_state.json` ist Laufzeit-/Maschinenzustand und wird NICHT committet.
Fehler → `failed_rolled_back` mit genau EINER nächsten Aktion. Repo-Lock gegen parallele
Update-Controller; Sessions mit erkanntem Versionswechsel dürfen weder delegieren noch erneut
updaten; veränderter Hook-Hash verlangt /hooks-Bestätigung, danach genau ein neuer
Sessionstart; die neue Session führt `harness doctor` aus und setzt erst dann `active`.
Ersetzt restlos: kit_updated_from-Marker, kit_update_pending.*-Dateien, Nag-Counter,
Transkript-Hinweise, mehrdeutige Neustartfragen.

## II.9 Office-Kit (BuyPlugGo-Muster)

**Filing:** `filing_plan.yaml` wird einzige maschinenlesbare Wahrheit — pro Regel:
id, path_template, document_types, filename_template, required_metadata, collision_policy,
examples. Menschenlesbare Ansicht wird generiert; Git = Versionshistorie; die große
Prosa-Guideline wird nach bestätigtem Cutover Legacy. (Heute ist die Richtung umgekehrt:
das Projekt-filing_plan.yaml ist eine v1.11-Ableitung der v1.13-Prosa — das Lag beweist das
Problem.) Passt eine Datei zu keiner Regel: nicht verschieben, nicht umbenennen, nicht ins
Ledger übernehmen — User fragen mit konkretem Schemaänderungsvorschlag. `filing_log.yaml` →
regenerierbarer Scan-Index.

**Ledger:** Append-only entfällt vollständig (User-Entscheid; `guard_ledger_direct` wird
gelöscht). Das Ledger sind CSV-Dateien (`ledger/<jahr>.csv`). Empfohlener Edit-/Importpfad
validiert vor atomarer Speicherung; direkte Edits lösen sofortige Vollvalidierung aus
(Schema, Datum, Pflichtspalten, Netto/Steuer/Brutto, Rechnungsnummern-Dubletten,
referenzielle Konsistenz — formuliert auf CSV-Spalten). Ein Post-Edit-Fehler markiert den
Zustand sichtbar ungültig (behauptet kein Rollback); Dispatch, Commit, Merge und Reports
bleiben bis zur Korrektur blockiert. Git + Evidence = Audit-Trail.

`gate_proc_approved` bleibt als Basis des Dispatch-Gates (ohne das V1-Bootstrap-Loch, II.4);
PROCs werden Per-Item-Dateien (heutiger Store: `process_definitions.yaml`; V1-Status
PROPOSED mappt auf DRAFT, II.10). Legacy-Kandidaten (4-Website/, 5-Shopify/) werden nur
inventarisiert — Bedeutung und Löschung entscheidet der User.

## II.10 Migrations-Tooling (Teil des Harness; Ausführung = Folgearbeit)

Prinzipien: kein Vollimport der V1-Historie; keine automatisch erzeugte Userfreigabe
(importierte Items behalten ihren regulären Anfangsstatus und tragen das FLAG
`migration_confirmation_required: true` + `approval_ref: null` — KEIN neuer Status; nur
echte Useraktion erzeugt APR); keine automatisch entschiedenen Widersprüche (Konflikte =
kleine strukturierte Decision-Items, Markdown nur generierte Ansicht); keine *.v1.bak-Kopien;
kein Force-Ersetzen (divergierte kit-owned Dateien werden inventarisiert und per Diff
bestätigt); keine Migration bei dirty Worktree, offener Schreibsession oder unklarem
Scaffold-Zustand.

**Status-Mapping V1→V2 (verbindliche, maschinenlesbare Tabelle im Migrations-Tool):**
TSK `TODO`→READY · PRD `TESTED`→DELIVERED · PRD `DONE`→ACCEPTED (terminal → Archiv) ·
PRD/PROC `PROPOSED`→DRAFT · SR `DRAFT`→PROPOSED · SR `ACTIVE`→ACCEPTED · SR `DONE`→ACCEPTED
(+Archiv-Kandidat). Der V1-Originalwert wird in `legacy_fields` bewahrt (SR ACTIVE/DONE
kollabieren auf ACCEPTED — ohne legacy_fields wäre das verlustbehaftet); unbekannte Werte →
Block + Decision-Item, nie raten. (Das komplette V1-SR-Vokabular ist disjunkt zu V2 —
verifiziert an synaipse/portfolio.)

**Nachtrag 2026-08-04 — zwei Stellen, an denen der gebaute Import von diesem Absatz abweicht, und
warum:** (a) *Anfangsstatus.* Ein Datensatz, den die Tabelle als abgeschlossen führt
(`archive_candidate`), wird nach SR-0004/DEC-0004 direkt unter `archive/<typ>/<jahr>/` auf seinem
gemappten Status geschrieben statt aktiv auf dem Anfangsstatus; der Feldvertrag gilt für ihn nicht.
Beides ist an `kernel/state.capture_migrated_archive` begründet und dort auch begrenzt. (b) *Die
ACCEPTED-Zeilen.* `PRD DONE`/`PRD ACCEPTED` sind oben mit „terminal → Archiv" notiert und werden
NICHT archiviert: ein PR/RQ erreicht `ACCEPTED` nur über die Kante, die eine `acceptance`-Freigabe
schließt, und der Import würde damit genau die automatisch erzeugte Userfreigabe erzeugen, die
derselbe Absatz verbietet — dasselbe gilt für jeden anderen V1-Wert hinter einer Freigabekante.
Solche Datensätze kommen aktiv auf ihrem Anfangsstatus an, der V1-Wert bleibt in `legacy_fields`.
Die Regel selbst steht in `kernel/state.migration_writable_statuses`.

(c) *Der zweite Riegel — GEMELDETE Vertragsabweichung, nicht umgedeutet.* SR-0002 verlangt die
Ausnahme wörtlich „nur bei Endzuständen", SR-0004 „dessen abgebildeter Status ein Endzustand seines
Automaten ist". Der gebaute Riegel ist ein anderer: `archive_candidate` (was das V1-Vokabular als
beendet führt) **plus** Erreichbarkeit ohne Freigabekante. Die beiden Regeln fallen auf den
ausgelieferten Tabellen in beide Richtungen auseinander — `TSK DONE` wird archiviert, obwohl `DONE`
kein Terminal des Task-Automaten ist, und ein auf `ACCEPTED` gemapptes SR wird archiviert, obwohl
`SUPERSEDED` das einzige Terminal dieses Automaten ist. Begründet ist der Ersatz an
`kernel/state.migration_archive_status` (Terminalität ist eine Eigenschaft eines LEBENDEN V2-Items
und sagt nichts über einen Datensatz von 2025 — genau diese Lesart hat erledigte V1-Tasks nach
`tasks/active/` gelegt). SR-0002 und SR-0004 sind kanonischer Zustand und wurden NICHT nachgezogen;
die Abweichung steht hier und an `capture_migrated_archive` (Riegel zwei) und wartet auf eine
Entscheidung. Gemessen wird sie von
`test_state.test_the_archive_paths_second_bolt_is_not_the_terminal_check_sr_0002_asks_for`.

(d) *Die Zeile `SR DONE→ACCEPTED (+Archiv-Kandidat)` — offenes Loch, mit Mechanismus.* Sie greift
heute, und der Grund ist eine FEHLENDE Zeile, keine Entscheidung: `approvals.APPROVAL_TRANSITIONS`
kennt für `SR` überhaupt kein Freigabe-Kind, und `migration_writable_statuses` liest eine fehlende
Kante als *keine Freigabe im Weg*. `approvals.required_approval_kinds` führt genau diese Kante
(`SR PROPOSED → ACCEPTED`) als *„Reported, not bridged"* — also als Freigabe, die man bauen müsste
und die niemand gebaut hat. Ergebnis, Ende zu Ende gemessen: `archive/SR/<jahr>/SR-nnnn.yaml` mit
`status: ACCEPTED`, `approval_ref: null` und keiner Anfrage irgendwo — dieselbe Form, die derselbe
Absatz für `CR APPLIED` als Defekt beschreibt, hier durch eine Abwesenheit erzeugt statt durch eine
Subtraktion. Nichts im Harness kann *entschieden: keine Freigabe nötig* von *das Kind wurde nie
gebaut* unterscheiden; das schließt erst ein APR-Kind mit Manifest, und das ist eine
Spec-Entscheidung. Stolperdrähte an beiden Enden:
`test_state.test_which_archive_bound_rows_rest_on_an_absent_approval_edge` (SR/TSK/FR/HYP) und
`test_migrate.test_a_finished_v1_sr_is_archived_at_accepted_with_no_approval_behind_it`.

(e) *Der Umzug nach `legacy/` — GEMELDETE Abweichung von den drei Auflagen unten, keine Umdeutung.*
Der Absatz „Ablauf pro Repo" weiter unten verlangt für das Verschieben von V1-Dateien drei Dinge:
eine **gesonderte Userzustimmung** („optionales späteres Verschieben nach legacy_v1/ nur mit
gesonderter Userzustimmung"), ein **Legacy-Manifest**, über das SessionStart, Dashboard und Gates
die Dateien ausschließen, und einen **fail-closed Integrity-Guard**, der Writes auf das Manifest und
alle erfassten V1-Dateien blockiert. Gebaut ist etwas anderes — in allen drei Punkten, und unter
einem vierten Namen:

* Der Umzug passiert **im selben Lauf** wie der Import (`migrate._retire_absorbed_documents`),
  nicht als späterer, eigens zugestimmter Schritt. Die einzige Zustimmung ist der Plan-Digest, den
  der Trockenlauf druckt und den der schreibende Lauf zurückbekommen muss — der beweist, dass der
  Zustand sich zwischen Lesen und Schreiben nicht bewegt hat, **nicht**, dass ein Nutzer dem
  Verschieben zugestimmt hat. Was der Trockenlauf dafür leistet: er nennt jede Datei, die er
  verschieben würde, unter einer eigenen Überschrift.
* Es gibt **kein Manifest**. Die Ausschlusswirkung kommt statt dessen aus dem Ort selbst:
  `legacy/` ist ein kernel-geschriebener Bereich (`state.legacy_root`), also liest `migrate` dort
  keine V1-Quellen mehr, `gate_write_scope` weist einen Tool-Write dorthin ab und der SR-0001-Scan
  überspringt ihn. Eine zweite, danebenliegende Aussage über dieselbe Menge Dateien entsteht damit
  gar nicht erst — das ist der Grund, aber es ist eine andere Konstruktion als die verlangte, und
  ein Wiederherstellungs-Befehl („Wiederherstellung nur über expliziten userbestätigten
  Restore-Befehl") existiert nicht.
* Es gibt **keinen Integrity-Guard**. Für die *stehenbleibenden* V1-Dateien ist das bereits im
  Modulkopf von `kernel/migrate.py` als offenes Loch benannt; für die *verschobenen* gilt nur der
  Tool-Write-Riegel von `gate_write_scope`, und der ist kein fail-closed Integritätsschutz: er
  hindert einen Editor außerhalb der Session an nichts, und niemand prüft die im Beleg
  festgehaltenen Pruefsummen jemals nach.
* Und das **Verzeichnis heißt nicht so wie die Auflage es nennt**: verlangt ist `legacy_v1/`,
  angelegt wird `legacy/` (`state.legacy_root`). Das ist der kleinste der vier Unterschiede und
  steht trotzdem hier, weil er der einzige ist, den ein Leser für einen Tippfehler halten kann: wer
  nach der Auflage sucht, sucht ein Verzeichnis, das kein Lauf anlegt.

Was der gebaute Umzug dafür zusätzlich einhält und die Auflagen nicht verlangen: verschoben wird nur
eine Datei, deren Datensätze **alle** zu Items geworden sind (SR-0005); **nie** eine Datei, deren
Inhalt ein registriertes, blockierfähiges Hook liest (`layout.gated_documents`) — sonst läse dieses
Gate danach eine abwesende Datei; und **nie auf einen Platz, an dem schon etwas liegt** (seit
2026-08-09): `os.replace` ersetzt still, und was dort liegt, ist das, wovon die Quittung eines
früheren Laufs den Hash trägt. Der Trockenlauf meldet diesen Fall vorab, und der Lauf fragt
unmittelbar vor der Zugschleife noch einmal. **Was das nicht deckt**, und es steht hier statt
implizit zu bleiben: zwischen dieser Frage und dem `os.replace` liegen zwei weitere Aufrufe, und
`os.replace` hat keine no-clobber-Variante — eine Datei, die in dieser Spanne entsteht, wird
ersetzt. Das ist der Eintrag `L30` in `docs/POST_V2_WISHLIST.md`, mit gemessener Kette und
Begrenzung. Die Abweichung steht hier und wartet auf eine Entscheidung; SR-0005
ist kanonischer Zustand und wurde NICHT nachgezogen. Stolperdrähte:
`test_migrate.test_a_fully_absorbed_v1_store_moves_to_legacy_with_its_hash_in_the_receipt`,
`test_migrate.test_a_document_a_registered_gate_reads_is_never_moved_to_legacy`,
`test_migrate.test_a_second_document_of_the_same_name_does_not_replace_the_one_already_retired`
und `test_migrate.test_the_move_asks_again_when_the_place_was_free_while_the_plan_was_built`.

(e2) *Was der Trockenlauf einem Leser über eine unerreichbare Datei sagt (DEC-0024).* Der
SR-0001-Vorlauf nennt jede Datei, die der Datensatz-Suchlauf nicht lesen kann, mit **allen** Gründen
dafür — und **leitet kein Ziel im Zustandsbaum mehr ab**. Das ist die eingeengte Fassung eines
Satzes, der bis Runde 7 „schlägt keine Bewegung mehr vor" behauptete. **Eine** Abhilfe verlangt
weiterhin eine Bewegung, die des belegten `legacy/`-Landeplatzes — sie nennt seit Runde 9 aber ein
Ziel, und zwar ein konstruiertes **außerhalb** des Zustandsverzeichnisses
(`migrate.overflow_deposit_of`: `../v1-legacy-overflow/`, Name aus Landeplatzpfad und sha256 des dort
stehenden Inhalts). Gedruckt werden zwei Schritte in dieser Reihenfolge: erst die **Kopie**, dann das
Entfernen des Originals. `L35` in `docs/POST_V2_WISHLIST.md` trägt die Kette und die zwei Reste, die
dabei benannt und nicht geschlossen sind. Die `UNLISTABLE`-Zeile bot dieselbe Bewegung bis Runde 8
als Alternative an und tut es nicht mehr: sie kann jedes Verzeichnis treffen, auch `product/active/`,
wo das Wurzelitem liegt, und für das existiert nach der Installation kein Schreiber
(`migrate.THE_ONLY_UNLISTABLE_STEP`, den seit Runde 9 auch `report.validate_state` durchreicht,
statt eine zweite Antwort auf dieselbe Bedingung zu drucken). Bis 2026-08-09 leitete er ein
Ziel aus dem Zustandsbaum ab (*benenn es zurück in ein `.yaml`-Dokument*); acht gemessene
Fundstellen in vier Prüfrunden zeigten, dass jedes so abgeleitete Ziel gegen eine weitere Autorität
zu prüfen gewesen wäre (kernel-geschriebener Bereich, Wand als Ziel, Wand als Quelle, belegter
Platz, und zuletzt zwei Abhilfen **eines** Berichts auf denselben freien Platz). Statt der nächsten
Klausel nennt die Meldung jetzt eine **Kopie** in die Ablage unter `staging/`, die dieses Kommando
selbst besitzt und deren Name der kodierte Quellpfad ist (`migrate.deposit_of`): das Original
bleibt stehen, zwei Zeilen eines Berichts können nicht **auf derselben Datei landen**, und ein Ziel
dort ist weder Wand noch kernel-geschrieben. Die zweite Zusicherung gilt seit TSK-0023 Runde 6
**nach der Faltung des Dateisystems** und nicht nur für die Zeichenketten: prozentkodiert allein
ergaben `PROC-0811a` und `PROC-0811A` zwei Namen und eine Datei. Der Name wird darum in ein Alphabet
kodiert, auf dem die Faltung dieses Dateisystems die Identität ist (`migrate._NAME_ALPHABET`). Der
Preis ist benannt: die Meldung sagt nicht mehr, wohin eine Datei gehört, damit der nächste Lauf sie
durchsucht — das entscheidet der Nutzer, und der Trockenlauf ist das Orakel dafür. Stolperdrähte:
`test_migrate.test_no_instruction_this_command_prints_can_take_a_file_away`,
`test_migrate.test_the_place_a_taken_landing_is_freed_to_is_named_and_lies_outside_the_state_directory`,
`test_migrate.test_two_sources_this_filesystem_would_fold_together_get_two_deposits`,
`test_migrate.test_two_records_of_one_document_that_differ_only_in_case_get_two_deposits` und
`test_migrate.test_a_document_a_registered_gate_reads_is_offered_no_way_to_move_or_rename_it`.

(f) *Der Name des Flags — umbenannt auf Nutzerentscheidung, kein Leser gebaut (DEC-0021).* Der
Prinzipien-Absatz oben verlangt das Flag `migration_confirmation_required: true`; geschrieben wird
seit dieser Runde `imported_from_v1: true` (`kernel/backlog_types.IMPORT_MARK`, drei Schreibstellen:
`migrate._with_legacy`, `state.capture_migrated_archive`, `state.capture_migrated_unresolved`). Der
Grund ist eine Messung, kein Geschmack: **kein** Leser im Kernel, in den Hooks, im Sitzungsbrief
oder im Dashboard wertet das Feld aus, und diese Spec verspricht auch keinen — der Name behauptete
damit eine Bestätigungspflicht, die nichts durchsetzt, also genau die Klasse *Kommentar behauptet
Schutz, den der Code nicht baut*, nur im Datenschema statt in Prosa. Zwei Prüfrunden haben das
unabhängig gemessen. Der wirksame Riegel ist `approval_ref`, und der **wird** gelesen; ein zweiter
Riegel daneben wären zwei Antworten auf dieselbe Frage. Der Nutzer hat am 2026-08-07 zwischen
*umbenennen*, *Leser bauen* und *als Loch führen* entschieden: umbenennen, ohne Leser. Was die
importierten Items dieser Runde tragen, wandert damit erst beim nächsten Lauf mit — die Migration
ist wiederholbar, das ist ihr abgenommener Entwurf. Stolperdraht:
`test_migrate.test_the_import_mark_says_where_an_item_came_from_and_claims_no_lever`.

**Branch↔Item-Konvention:** Arbeitsbranches heißen `<typ>/<ITEM-ID>-<slug>` mit Präfixen
`pr/ rq/ bug/ cr/` (z. B. `pr/PR-0012-checkout`); gate_git prüft Existenz + TYPGERECHTEN
Arbeitsstatus des referenzierten Items statt des heutigen `PRD-\d`-Regex (PR/RQ:
IN_DELIVERY; BUG: APPROVED|FIXED; CR: APPROVED); Lease-Abgleich als Feinschliff in Phase 1.

Ablauf pro Repo: Read-only Dry-run außerhalb des Repos (Kandidaten aktiv/geschlossen,
Konflikte, Memory-Kandidaten, Legacy-Dateien, geplante Änderungen) → User kuratiert →
Cutover: V1-Monolithe bleiben lesbar, werden per Legacy-Manifest von SessionStart, Dashboard
und Gates ausgeschlossen (optionales späteres Verschieben nach legacy_v1/ nur mit gesonderter
Userzustimmung) → typisierte Verzeichnisse atomar aktiviert → Smoke-Test → Userbestätigung
macht V2 kanonisch. **Legacy wirklich read-only:** Ein Integrity-Guard (fail-closed) blockiert
Writes auf das Legacy-Manifest und alle erfassten V1-Dateien; Wiederherstellung nur über
expliziten userbestätigten Restore-Befehl. **Sequenzregel:** Der Legacy-Freeze eines Repos
setzt das vollständige atomare Lockstep-Release (II.11/2) voraus — nie umgekehrt (sonst
liest ein alter Hook eine eingefrorene Datei und blockiert). Legacy-Import bestätigt zudem
die alten PROC-/Item-Hashes neu (Legacy-Hashes gelten nicht weiter). Memory-Rotation
(MEMORY.md → Index + topics/, History-Prune) gehört zum Tooling.

## II.10a Betriebsregeln (Peer-Review-Schlussrunde)

**Verhaltens-Paritätsmatrix (Pflicht VOR jedem Kürzen von Verfassungen/SKILLs/Agents):**
Jede bestehende Regel wird klassifiziert: `behalten | durch Gate ersetzt | durch Test
ersetzt | bewusst geändert (mit Begründung + Ersatzverhalten) | bewusst entfernt (mit
Begründung)`. Mindestens erhalten bleiben: Deutsch zum User / Englisch in Artefakten;
Orchestrator schreibt keinen Produktcode; kein Spezialist ohne freigegebenen Task; keine
stillen Scope-/Designänderungen; Push nur nach expliziter Userfreigabe;
Dirty-Worktree-Schutz; technische Entscheidungen beim Team, Produktentscheidungen beim User;
QA-/Regressionstestpflicht; bestätigte Design-Preview als verbindliche Revision.

**Fast Mode (verbindlich definiert):** Während der Entwicklung nur betroffene Tests + Lint +
Typprüfung, reale Browserprüfung bei Interaktionsfehlern, KEINE Vollsuite nach jedem
Kleinschritt. Vor Merge/Release/Abnahme: vollständiger Quality-Gate; partielle Tests gelten
nicht als Merge-Evidence.

**Auditor-Routine (User-Entscheid):** wöchentlich bei aktiven Projekten + ereignisbasiert
(nach Kit-Update, nach großen PRs/CRs bzw. strukturellen Änderungen, vor Releases).
Wiederkehrende Freigabe als widerrufbare, zeitlich begrenzte Routinefreigabe. Jeder Lauf =
eine Evidence-Datei; jeder Befund wird SOFORT als BUG/CR/TSK erfasst oder mit begründeter
Entscheidung verworfen; identische Befunde per Fingerprint zusammengeführt; keine wachsende
review_findings.yaml.

**Auslöser-Betriebsvertrag (User-Entscheid: Hybrid via Claude-Routine):**
- Eine Claude-Routine — konkret: ein LOKALER Scheduled Task (Windows-Aufgabenplanung,
  headless `claude -p`; Cloud-Routinen haben keinen Zugriff auf lokale Repos) — löst den
  wöchentlichen Lauf automatisch aus.
- SessionStart prüft providerneutral als Fallback, ob ein Audit überfällig ist — bei Codex
  und anderen Providern ohne Routinen ist dieser Fallback der einzige Auslöser und bleibt
  wirksam.
- Routine und SessionStart-Fallback verwenden dieselbe Wochen-ID + Lease → kein Doppellauf.
- Die `APR.kind: routine`-Freigabe hasht Rolle, Read-only-Scope, Trigger, Takt und
  Ablaufdatum.
- `last_completed` wird aus der Audit-Evidence BERECHNET; `next_due` ist generiert — beides
  nie manuell gepflegt.
- Abgelaufene oder widerrufene Routinefreigabe blockiert den Audit-Dispatch (fail-closed)
  und zeigt genau EINE notwendige Useraktion.
- Tests (→ II.12): Automation feuert, Session-Fallback feuert bei überfälligem Audit,
  Deduplizierung per Wochen-ID, Parallelstart blockiert, abgelaufene Freigabe blockiert.

**Installations-Preflight (bestehende Repos schützen):** Installer/Scaffold klassifiziert
zuerst: `greenfield → V2 initialisieren`; `V2 → normales Update`; `V1 → migration_required,
KEINE Änderungen`; `mixed/incomplete → blockieren + Konfliktbericht`. V1 und V2 bleiben
nebeneinander versioniert verfügbar; bestehende Repos werden auf ihre installierte
Hauptversion gepinnt; kein V2-Hook wird je gegen V1-project_memory installiert; V2 wird erst
globaler Standard, wenn der portfolio-Pilot bestanden ist; Rollback auf das unveränderte
V1-Bundle bleibt möglich.

**Erster Projektstart (bleibt verbindlich erhalten):** Strukturiert-oder-frei-Gate →
bestehendes Projekt read-only untersuchen → Plan entwerfen → User bestätigt → V2-State +
erstes Root-Item gemäß Kit anlegen (dev/office: PR, research: RQ) → Kit vollständig
scaffolden → Hooks vertrauen → genau EIN notwendiger Neustart → Orchestrator übernimmt aus
session_brief + aktiven Items. Spätere Sessions erstellen weder Kit noch Plan neu — sie
setzen am gespeicherten aktiven Zustand fort.

**Nutzung als Masterprompt:** Dieses Dokument ist die versionierte Referenz-Spezifikation,
NICHT der Einmal-Prompt (das wäre neuer Kontext-Bloat). Startauftrag kurz: "Implementiere
ausschließlich Teil II der freigegebenen Harness-V2-Spezifikation, phasenweise, beginnend
mit Phase 0; keine Projektmigration, keine Aktivierung als globaler Standard, kein
Überschreiben bestehender Installationen ohne gesonderte Userfreigabe; jede Phase besteht
ihre Abnahmetests, bevor die nächste beginnt."

**Transkript-Hinweis:** Die Sessiondaten unter `.claude/projects` (904 MB BuyPlugGo usw.)
werden durch V2 nicht kleiner — sie werden nur nicht mehr als Arbeitsgedächtnis gelesen.
Eine Aufbewahrungs-/Löschregel ist ein separater, userbestätigter Auftrag (→ II.14).

## II.11 Umsetzung im Harness-Repo (Reihenfolge)

0. **Phase 0 — Vollinventar + Paritätsmatrix (read-only, User-Entscheid):** "Jede Datei"
   heißt technisch: alle per `git ls-files` erfassten Dateien plus bekannte verwaltete
   Installer-/Registry-Dateien; ausgeschlossen sind .git, Caches, Buildartefakte und
   Backups; die Anzahl wird ermittelt, nicht fest verdrahtet (Messwert 2026-07-24: 274
   getrackte Dateien). Jede Datei wird disponiert: `übernehmen | anpassen | durch
   V2-Mechanik ersetzt | bewusst entfernen` — je mit Ein-Zeilen-Begründung. Ergebnis ist ein
   Dispositionsbericht, den der User VOR Phase 1 bestätigt. Die Verhaltens-Paritätsmatrix
   (II.10a) ist Teil dieses Berichts. **v2.1-Erweiterungen:** (a) die vollständige
   **Lockstep-Disposition aller ~76 Monolith-Abhängigen** (statt „6+1"; inkl.
   guard_yaml_valid, auto_dashboard, generate_dashboard-TEMPLATE, Scaffold/Init-Skripte,
   kit_checks, retro, Cross-Kit-Kopien, gate_packaging_decision↔architecture.yaml,
   masterplan-Check, globale CLAUDE.md); (b) drei Read-only-**Spikes** mit je einem
   `verified|unverified`-Verdikt — S1 Kernel-Lock-Design (O_EXCL, PID+TTL, Stale-Break auf
   Windows+OneDrive), S2 AskUserQuestion-Protokoll (feuert PostToolUse mit strukturierten
   answers inkl. Options-Identität?), S3 agent_id-Spawn-Bindung (liefert PostToolUse(Agent)
   die Kind-Agent-ID?); (c) Disposition von architecture.yaml/packaging, masterplan.md und
   der generated/-Git-Strategie. Ziel: nichts Bewährtes geht beim Rückbau verloren ("besser
   machen, nicht schlechter").
1. **State-Kernel + Schemas** (`team-kits/<kit>/…` gemeinsamer Kern, `_backlog_types.py` für
   Kit-Root-Typen; Hash-Modul aus proc_hash.py verallgemeinert). Schemadateien: Envelope,
   session_brief, ARC-/WFR-Companion, Status-Mapping-Tabelle (II.10).
2. **Hooks**: neu gate_dispatch (Lease + Header, fail-closed), guard_memory_budget,
   gate_ledger_valid (office); **Lockstep-Umstellung ALLER Monolith-Abhängigen aus der
   Phase-0-Disposition (~76 Dateien — u. a. die 6 Gate-Hooks, guard_yaml_valid,
   auto_dashboard, das generate_dashboard-TEMPLATE, Scaffold/Init, kit_checks, retro,
   Cross-Kit-Kopien, gate_packaging_decision↔architecture.yaml) in EINEM atomaren
   Release** — kein Teilrelease entfernt Monolithe, solange ein Gate sie erwartet;
   Löschung: guard_ledger_direct.
3. **session_status.py** → Update-Zustandsautomat + session_brief-Verweis (ALLE ~6
   injizierten Blöcke disponiert); **Templates** → typisierte Struktur, ITEM-Templates,
   Lead-Paket auf die Grössenregel aus II.5 (der Rekord in `tools/lead_package_sizes.json`, hart
   erzwungen von `tools/validate.py`; die frühere feste Zahl 25 600 und die frühere
   Zeilenvorgabe „≤150" sind dort ersatzlos gestrichen und begründet) — **Kürzung erst NACH den
   ersetzenden Gates aus Schritt 2 (Release-Checklistenpunkt, D/9), jede entfernte Regel per
   Paritätsmatrix belegt**; Verlagerung ohne Textverlust braucht keine Lizenz (II.5).
4. **harness doctor**, Scaffold-/Init-Anpassung (kit_state.json-Konsolidierung, Migration der
   alten Marker), `gen_provider_artifacts.py`-Regen, VERSION-Bump + registry.yaml; **globale
   `~/.claude/CLAUDE.md` (`user/claude/CLAUDE.md`) + `user/codex/AGENTS.md` + team-kits-
   Templates auf den V2-Flow umstellen** (PR/RQ-Draft statt PRD/progress.yaml;
   masterplan.md → product/masterplan.md ohne progress-Referenz).
5. **Tests** (II.12) in Scratch-Repos; danach wird NUR eine **seitlich installierte V2-RC**
   erzeugt (versioniert neben V1 gemäß Preflight II.10a, bestehende Repos bleiben auf V1
   gepinnt). V2 wird erst nach bestandenem portfolio-Pilot UND expliziter Userfreigabe zum
   Standard in `~/.claude/team-kits`.

## II.12 Verifikation

**Dispatch-Gate-Tests** (subprocess, JSON-stdin, Scratch-Repo; Fixtures einmal mit
PS-5.1-BOM + `\`-Pfaden): Spawn ohne Header → Block; freie Prosa mit zufälliger TSK-ID →
Block; Task fehlt/nicht READY → Block; Rollen-Mismatch → Block; falsche Root-Revision oder
ungültiger APR-Hash → Block (nach Re-Approve + Hash-Update → pass); fehlende design_ref bei
bestätigtem Design → Block; offene Abhängigkeit → Block; zweiter Claim derselben Lease →
Block; Draft-Analyse ohne APR.kind analysis → Block; leerer Zustand ohne Bootstrap-Modus →
Block; korruptes State-YAML und simulierter Hook-Crash → Block mit Diagnose (fail-closed-
Nachweis); Lease-Timeout → Task wieder READY; manuell geschriebene APR ohne
Provider-geprägten Token → Block bzw. nur `audited`; Approval-Protokoll: Freigabefrage passt
nicht zum Pending-Request → Block, abgelaufener Request → kein Token, Freitext-Antwort →
kein Token, NUR das wortgleiche Freigabe-Label mit dem Mint-Code dieses Requests prägt
(ein blankes „Freigeben" prägt nicht — Amendment 2026-07-24); ungültiger Statusübergang (z. B. TSK
DRAFT→IN_PROGRESS direkt) → Block; verwaister staging/-Ordner ohne aktiven Task/Root-Item →
vom Validator geflaggt; Write auf Legacy-Manifest oder erfasste V1-Datei → Block (Restore
nur per userbestätigtem Befehl). Claude- und Codex-Pfade separat; Research-E2E:
RQ→HYP→EXP→TSK→Evidence→Abnahme inkl. EXP-delivery-Invalidierung.

**Auditor-Routine-Tests:** Automation löst den Wochenlauf aus; SessionStart-Fallback löst
bei überfälligem Audit aus; gleiche Wochen-ID verhindert Doppellauf; Parallelstart wird per
Lease blockiert; abgelaufene/widerrufene Routinefreigabe blockiert den Audit-Dispatch mit
genau einer Useraktion.

**Weitere Gates:** MEMORY.md 41 Zeilen → Block / 40 → pass; Ledger-Edit (CSV) mit
Summenfehler → Folge-Workflow blockiert, gültiger Edit → pass, Append-only-Guard
nachweislich entfernt; nicht klassifizierbare Datei bleibt unberührt + Ask-User-Text;
gate_memory_complete triggert auf product/active/PR-*.yaml (Lockstep-Regression).

**Paritätsrisiken R1/R3/R5/R6/R10/R11 (Phase 2, Nachtrag 2026-07-25):** `git push` ohne
geprägtes Push-Token → Block, mit Token → pass, nach neuem Commit → wieder Block
(HEAD-Bindung macht es einmalig); widerrufenes und abgelaufenes Token → Block;
handgeschriebene push-APR → Block. PII-Scan: Counterparty-Name in getrackter Datei
außerhalb ledger/ → Block mit Datei:Zeile, Name nur im Ledger → pass (140-Namen-Vorfall).
**R5:** entferntes sichtbares UI-Element ohne CR → der UI-Inventar-Snapshot schlägt fehl
(Snapshot-Muster aus testing_guidelines). **R6:** ausgelieferte index.html ≠ Build-Hash →
Delivery-Freshness-Fail (grüner Smoke-Test gegen ein veraltetes Bundle zertifiziert Code,
der nicht der geprüfte ist). Fremdes Docker-Compose-Projekt oder `prune` → Block, Lesen
(`ps`/`logs`/`inspect`/`build`/`up`) → pass; merge/rebase/pull/`reset --hard`/Branchwechsel
auf dirty tree → Block, `add`/`stash`/`checkout -b`/`checkout -- <datei>` → pass.

**Neue v2.1-Testfälle:** Lock: zweiter Prozess wartet/blockt; Stale-Lock wird nach TTL
gebrochen; doctor meldet gehaltenen Lock. ID-Kollision zweier Branches → Merge-Block.
Out-of-band-Edit an gehashtem Feld → Dispatch/Merge-Block mit Re-Approve-Hinweis.
Getipptes blankes „Freigeben" (auch via „Other") prägt NIE — Mint-Code-Bindung; der
Mint-Code steht ausschließlich im Options-Label, nie im Fragetext. Unbekannter
V1-Statuswert → Migrations-Block + Decision-Item. Budget-Trigger je Pfad (agent-memory /
MEMORY.md / Item / Envelope) einzeln. Pfad >240 Zeichen → Validator-Warnung. Überlanger
Hook-stdin → bounded read ohne Crash. Dirty-Flag-Hook schreibt NUR das Stale-Flag, nie
State. Legacy-Freeze VOR dem Lockstep-Release → Migrations-Tool blockiert. ARC-Promotion
mit fehlerhafter XML → Block; ARC ohne derives_from → Validator-Flag; ARC-Inhalt in
Agent-Memory statt Pointer → Budget-Flag; Änderung eines eingefrorenen ARC →
delivery-APR invalidiert. Wireframe nach scope-Freigabe geändert → scope-APR invalidiert;
UI-Scope ohne Wireframe im scope-Manifest → Block; DSN eingefroren → design_ref gesetzt →
UI-TSK leasbar. INV mit nicht existentem check-Test → `unverified` → Merge-Block.
Fail-closed-Blockmeldung nennt konkreten Restore-Befehl (korruptes YAML-Szenario).
Dashboard offline per Doppelklick bedienbar. Codex-Pfad: Dispatch+Approval laufen
nachweislich `audited` (protokolliert + nachvalidiert), doctor meldet spawn_veto +
approval_provenance `unverified`. Latenz-Bench (CI, p95, nicht blockierend).

**E2E pro Kit (Scratch):** Wunsch → Draft-PR → Verständnis (+ WFR bei UI) → Freigabe →
Analyse-Task → SR/Tasks → Implementierung → QA → Abnahme → Archiv; FR-Triage → CR/neue
Revision; small-Pfad ohne unnötige Agentenkette; neue Session rekonstruiert PR, Task,
Designrevision und nächsten Schritt OHNE Transkript; Kit-Update zeigt jederzeit genau einen
nächsten Schritt, zwei parallele Updates unmöglich, alte Session nach Versionswechsel
delegationsunfähig; Dashboard mit 1.000 Items bedienbar (kein Archiv/Volltext im initialen
DOM).

**Abnahmekriterien (nach Enforcement-Modus getrennt):**
- `hard` (alle Capabilities verifiziert): unerlaubte Starts sind technisch VERHINDERT —
  100 % Spezialistenstarts mit gültigem Task, 0 Starts ohne passende Userfreigabe.
- `audited`: jeder Start wird protokolliert und nachträglich validiert; Verstöße werden
  ausgewiesen — es gibt keine Präventionsgarantie und der Plan behauptet dort keine.
- Modusunabhängig: 0 aktive Transkript-Abhängigkeiten; 0 manuell gepflegte Statusfelder in
  generierten Ansichten; keine DONE/REJECTED/SUPERSEDED-Inhalte im Standardkontext; alle
  Budgets automatisiert geprüft; jede Information hat genau einen kanonischen Speicherort.
- Phase-0-Abnahme: Dispositionsbericht + Paritätsmatrix + die drei Spike-Verdikte S1–S3
  liegen vor und sind vom User bestätigt.

**Betriebs- und Migrations-Tests (ergänzend):** Preflight klassifiziert
greenfield/V2/V1/mixed korrekt, je mit No-write-Nachweis auf V1-Beständen; Version-Pinning
hält gepinnte Repos auf V1; RC-Parallelinstallation kollidiert nicht mit V1-Bundle;
Rollback stellt das unveränderte V1-Bundle wieder her; Fast Mode: partielle Tests während
der Entwicklung erlaubt, werden aber als Merge-Evidence abgelehnt; ALLE Memory-Budgets
(Lead-Paket, Session-Bootstrap, Item, Result-Envelope, MEMORY.md, Craft-Topic,
Topic-Anzahl) einzeln geprüft; typabhängige Freigabe-Invalidierung je Item-Typ inkl.
"Task entwerteter Root-Revision nicht leasbar" und Archivierung terminaler Items;
Status-Mapping-Tabelle vollständig gegen die realen V1-Bestände (synaipse/portfolio/
BuyPlugGo) geprüft.

## II.13 Risiken

- Lockstep (größtes Risiko, verifiziert und GRÖSSER als in v2.0 angenommen): ~76 Dateien
  repo-weit — Hooks, das generate_dashboard-TEMPLATE in den Projekten, Scaffold/Init,
  Cross-Kit-Kopien, globale Entry-Gate-Datei — hängen an Monolith-Namen. Nur ein atomares
  Release der vollständigen Phase-0-Disposition.
- Hash-Kanonisierung: EINE Dump-Konvention für alle Hash-Nutzer, sonst platzen Freigaben.
- Codex-Veto-Lücke: mechanisch belegt (Agent|Task→None, AskUserQuestion→None) — ehrlich als
  `audited` ausweisen, nie als `hard`.
- OneDrive (später, BuyPlugGo-Migration): Sync pausieren, kein os.replace über synchronisierte
  Ordner; MAX_PATH-Vorsorge (II.4: `\\?\` + Validator-Warnung >240).
- Fail-closed-Gates dürfen legitime Arbeit nicht dauerblockieren: jede Block-Meldung nennt
  die konkrete Abhilfe als ausführbaren Befehl (`harness doctor` → benannter
  `git restore <item>` + `harness generate-index`).
- Plattformannahmen: Die drei Phase-0-Spikes (S1 Lock, S2 AskUserQuestion-PostToolUse, S3
  agent_id-Bindung) entscheiden, welche Capabilities `verified` werden — bis dahin keine
  `hard`-Zusagen.

## II.14 Folgearbeit (NICHT Teil dieses Auftrags, empfohlene Reihenfolge)

1. portfolio (kleiner Pilot: Update-Automat, Per-Item-Backlog, Dashboard-Skalierung),
2. synaipse (Designrevision; **INV-HARDWARE-ORDER: zuerst :9216-Klärung durch den User —
   bewusste Umsortierung vs. Transkriptionsfehler, inkl. Label-Entscheid ROM vs. STORAGE —
   DANACH ggf. Code-Anpassung HardwareAnatomy.tsx + Regressionstest gemäß der dann
   fixierten Invariante**; Memory-Bereinigung 159 Dateien/0,96 MiB),
3. BuyPlugGo (erst Fixtures; dann filing_plan-Cutover, editierbares Ledger,
   legacy_files-Inventar für den User; OneDrive pausiert),
4. Transkript-Aufbewahrungsregel für `.claude/projects` (904 MB BuyPlugGo, 155 MB synaipse,
   69,5 MB portfolio) — separater, userbestätigter Auftrag.

## Entscheidungsprotokoll v2.1 (2026-07-24)

1. Wireframe-Pflicht: **immer bei UI-Scopes**, auch small (small-Sonderweg: II.2
   Risikoklassen); Verzicht nur per explizitem User-Decision-Item.
2. Analyse-Freigaben: **gebündelt** — eine analysis-/scope-APR deckt mehrere im Manifest
   gelistete Analyse-Tasks; Persistierung/Audit pro Task unverändert.
3. Kanonische Ablage dieser Spec: **`docs/HARNESS_V2_SPEC.md`** im Harness-Repo
   (git-versioniert); die frühere plans/-Datei trägt einen Verweis-Header.
4. Unverändert verbindlich: alle I.3-Entscheide (2026-07-20) und alle
   II.10a-Betriebsregeln.
