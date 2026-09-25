# Plan: anbieterfrei arbeiten — Harness × Modell frei wählbar

Entwurf 1, 2026-09-25, zum Gegenlesen durch den Nutzer. Gehört zu **FR-0023** (dazu FR-0020, FR-0025).
Grundlage: deine Festlegungen **DEC-0115**, die zwei Recherchen unter
`project_memory/staging/FR-0023/` und die Durchsicht von `synaipse-unified`. Nichts hier ist
beschlossen, was nicht als DEC benannt ist.

## 1. Leitidee

Du öffnest **ein** Programm, wählst **Harness** (das Arbeitsprogramm im Hintergrund, z. B. Claude Code
oder Codex) und **Modell** (z. B. Claude, ChatGPT, Kimi, DeepSeek, ein lokales Modell) und legst los.
Vorausgewählt ist **Claude Code + Claude**. Egal was du kombinierst: es sieht gleich aus, es fühlt
sich an, als schriebe man immer mit demselben Gegenüber, und beim Wechsel geht **nichts** verloren —
weder Projektstand noch Regeln, Skills, Werkzeuge noch der Chatverlauf. Das gilt im freien Modus und
im Kit-Modus. Ziel ist, schnell den Anbieter wechseln zu können, wenn sich Tarife oder Qualität ändern.

## 2. Was du festgelegt hast

| Frage | Deine Antwort | Wo festgehalten |
|---|---|---|
| Was überlebt einen Wechsel? | Alles, auch der Chat | DEC-0115 (P1) |
| Bezahlung | Abos bleiben die Grundlage | DEC-0115 (P2) |
| Gleicher Schutz überall? | Abgestuft ist ok, aber sichtbar | DEC-0115 (P3) |
| Für wen? | Erst für dich; Ziel: jeder Anbieter inkl. lokal | DEC-0115 (P4) |
| Deine Zugänge | Claude-Abo, ChatGPT-Abo, Kimi-Abo, DeepSeek-API | Chat 2026-09-25 |
| Standard | Claude Code + Claude, frei kombinierbar (z. B. Codex + Kimi) | Chat 2026-09-25 |

## 3. Das Bild: drei Schichten statt einem Riesenprogramm

```
 ┌──────────────────────────────────────────────────────────────┐
 │ SYNAIPSE (der ganze Arbeitsplatz, siehe §5)                  │
 │  Harness wählen · Modell wählen · Abo/API/lokal · ein Fenster│
 │  eigener Chat-Speicher (neutral, jede Nachricht mit Modell)  │
 └───────────────▲──────────────────────────────▲───────────────┘
                 │ ACP (offenes Protokoll       │ liest/schreibt
                 │ Oberfläche ↔ Agent)          │ über Kernel-Befehle
 ┌───────────────┴───────────────┐  ┌───────────┴───────────────┐
 │ HARNESS (austauschbar)        │  │ GEDÄCHTNIS + REGELN        │
 │ Claude Code · Codex ·         │  │ (AgentAndSkills)           │
 │ Kimi CLI · Qwen Code ·        │  │ project_memory/ · AGENTS.md│
 │ Gemini CLI · später OpenCode  │  │ Skills · Schutzregeln ·    │
 │ … jeweils mit Modell-Backend  │  │ Rollen · Freigaben         │
 └───────────────────────────────┘  └───────────────────────────┘
```

- **Oberfläche** — das, was du siehst. Überall dasselbe Aussehen. Sie spricht die Harnesse über
  **ACP** an (Agent Client Protocol, offen, von Zed gestartet): Claude Code, Codex, Gemini, OpenCode und
  über 50 weitere Agenten sprechen es schon. Damit muss die Oberfläche nicht für jedes Programm eigene
  Anbindungen lernen.
- **Harness** — das Arbeitsprogramm im Hintergrund, austauschbar. Wo es ein Abo gibt, läuft das Abo
  im Programm, für das es gilt (Claude-Abo → Claude Code, ChatGPT-Abo → Codex, Kimi-Abo → Kimi CLI oder
  Claude Code mit Kimi-Anschluss). Wo nur ein API-Schlüssel da ist (DeepSeek) oder ein lokales Modell,
  läuft es über ein Harness mit umgeleitetem Modell-Anschluss.
- **Gedächtnis + Regeln** — das, was dieses Repo heute schon anbieterfrei baut: Projektakte,
  Entscheidungen, Rollen, Schutzregeln, Freigaben, `AGENTS.md`, Skills. Kommt bei jedem Wechsel mit,
  weil es Dateien im Projekt sind und keinem Anbieter gehören.

**Der Chat überlebt so:** Ein laufendes Gespräch kann nicht von einem Programm ins andere wandern
(jedes hält seinen Verlauf für sich, und dafür gibt es keinen Standard). Deshalb schreibt die
Oberfläche **jeden Chat selbst mit**, in einem eigenen, neutralen Format. Wechselst du Harness oder
Modell, startet die neue Sitzung mit einer Übergabe: Projektstand + verdichteter bisheriger Chat. Für
dich sieht es aus wie ein durchgehender Chat. Gemessen wird das mit einem **Wechseltest**: dieselbe
Aufgabe, mitten drin der Wechsel, danach muss das neue Modell ohne Nachfragen weitermachen.

## 4. Welche Kombinationen gehen (Stand: zu messen)

| Harness ↓ / Modell → | Claude | ChatGPT | Kimi | DeepSeek | lokal (Ollama) |
|---|---|---|---|---|---|
| **Claude Code** | ✅ Abo, heute | ❌ ChatGPT-Abo gilt dort nicht | 🔬 Kimi-Abo ist laut Kimi für Claude Code gedacht | 🔬 API, Anschluss laut DeepSeek vorhanden | 🔬 über Vermittler |
| **Codex** | ❌ | ✅ Abo, heute | 🔬 Codex spricht nur die Responses-Schnittstelle → evtl. Übersetzer | 🔬 dito | 🔬 eingebaut (`--oss`) |
| **Kimi CLI** | ❓ | ❓ | 🔬 Abo | ❓ | ❓ |
| **OpenCode** (später) | ⚠️ nur API, kein Abo | ⚠️ API | 🔬 | 🔬 | 🔬 |

✅ läuft · 🔬 muss gemessen werden · ⚠️ geht, aber gegen DEC-0115 (P2, Abos zuerst) · ❌ geht nicht · ❓ unbekannt.
Wichtig: **Anthropic unterstützt Claude Code mit fremden Modellen offiziell nicht.** Technisch geht es;
ob unsere Schutzregeln, Hilfsagenten und Freigaben dann halten, ist genau die erste Messung.

Zu jeder Zeile gehört später eine **Fähigkeiten-Tabelle** (DEC-0115 P3): blockierende Schutzregeln ja/nein,
Hilfsagenten mit Rechten ja/nein, Freigabe-Fragen ja/nein, Spawn-Veto ja/nein. Ein Harness, dem etwas
fehlt, darf mitspielen — aber sichtbar markiert, und Rollen, die das Fehlende brauchen, laufen dort nicht.

## 5. Synaipse und AgentAndSkills: vereinen oder getrennt?

**Was Synaipse ist** — nach seinem eigenen Masterplan (`synaipse-unified/project_memory/masterplan.md`,
Richtung freigegeben 2026-09-05), nicht nur nach dem heute gebauten Stand: **ein ruhiger Arbeitsplatz
für lokale KI und angebundene Anbieter** mit Chat, Code, Cowork und „Modelle & Geräte“. Zwölf Pakete
P1–P12: Design-System (P1), Harness-Nachweis und austauschbarer Laufzeit-Vertrag (P2), Anbieter und
Zugänge — Abo, API, lokal (P3), lokale Modelle, Hardware-Scan, Hugging Face (P4), Gespräche, Spaces,
Dokumente, Gedächtnis (P5), Erweiterungen, MCP, Hooks, echte Freigaben (P6), Code/Cowork mit Dateien,
Terminal, Git (P7), **Agenten-Teams, Vorlagen, Routinen (P8)**, eigene Geräte und Hintergrundarbeit (P9),
Routing, Benchmarks, Cache (P10), Windows-Paket, API/SDK, Fernzugriff (P11), Medien und
Spezial-Integrationen (P12). Als ersten Harness-Kandidaten prüft Synaipse das offizielle
**deepseek-harness** (Developer Preview; Skills, MCP, dauerhafte Sitzungs-Historie — Freigaben und
Abbrechen fehlen in dessen Python-SDK, alle acht Pflicht-Nachweise H01–H08 stehen noch auf NOT_RUN).

Gebaut ist davon heute vor allem: Chat mit lokalen Modellen (Ollama), Chat-Speicher mit Modell je
Nachricht, Dokumente/RAG, Regeln für ausgehende Verbindungen. Entwickelt wird es mit dem Entwickler-Kit
dieses Repos — **noch in der alten Fassung 2026.07.18-3** (vor V2).

**Das korrigiert mein erstes Bild:** Synaipse ist nicht „nur die Oberfläche“, sondern **das ganze
Programm** — inklusive eigener Harness-Schnittstelle, Anbieter-Verwaltung und Agenten-Teams. Die Frage
ist deshalb nicht mehr „wer baut die App“, sondern **was AgentAndSkills in Synaipse ist.**

**Empfehlung: AgentAndSkills wird das „Team-Kit-Modul“ von Synaipse — getrennt gepflegt, über eine
feste Schnittstelle eingesteckt.**

- **Synaipse** besitzt: Oberfläche, Anbieter und Zugänge, Harness-Anbindung (P2/P3), Chat-Speicher,
  Geräte, Modelle. Das ist die Welt, in der du „Harness wählen, Modell wählen, loslegen“ machst.
- **AgentAndSkills** besitzt: Team-Kits (Rollen, Regeln, Leitern), Projektakte (`project_memory/` +
  Kernel), Schutzregeln, Freigabe-Protokoll, Prüfer-Pflicht. Genau das, was Synaipse in **P6 (Hooks,
  echte Freigaben)** und **P8 (Agenten-Teams, Vorlagen)** braucht — dort wird es eingesteckt, statt es
  in Synaipse ein zweites Mal zu bauen.
- **Die Schnittstelle:** Kernel-Befehle, `project_memory/`-Dateien, die Freigabe-Tür
  `kernel/sdk_approval.py`, und die Kit-Vorlagen (siehe §5a). Kein gemeinsamer Code.
- **Warum getrennt:** beide ändern sich ständig; getrennt behält jedes seinen Takt, solange die
  Schnittstelle stabil bleibt. Vereinen lässt sich später immer noch (ein Installer, der beides
  mitbringt), umgekehrt ist es schwer.
- **Erster kleiner Schritt:** synaipse-unified auf das aktuelle Kit heben; dann sieht Synaipse bei der
  eigenen Entwicklung schon den Motor, den es später einsteckt.

## 5a. Eine Vorlage für alle — statt .md hier, .toml dort

**Dein Wunsch:** eine **zentrale Stelle** für Team-Kits, Rollen, Skills, Regeln — und nicht für jeden
Anbieter eigene Vorlagen (.md für Claude, .toml für Codex, .json hier, .yaml dort).

**Wie es heute ist:** schon halb so. Es gibt **eine** Kit-Quelle; ein Übersetzer
(`gen_provider_artifacts.py`) erzeugt daraus automatisch die Codex-Dateien. Aber: (1) die Quelle ist im
**Claude-Format** geschrieben (Entscheidung vom 14.07.), (2) die übersetzten Dateien landen in **jedem
Projekt** (`.claude/`, `.codex/`), (3) jedes weitere Harness braucht einen weiteren Übersetzer.

**Warum es mit mehreren Harnessen schwierig ist — und warum es trotzdem geht:** Jedes Harness liest nur
seine eigenen Ordner und Formate (Claude Code `.claude/agents/*.md`, Codex `.codex/agents/*.toml`, Gemini
`.gemini/`, Goose `.agents/`). Diese Dateien **müssen** auf der Platte stehen, sonst sieht das Harness
nichts. Sie müssen aber **nicht von Hand gepflegt** werden. Das Ziel ist darum:

1. **Eine neutrale Quelle** — ein Format, das kein Harness direkt liest, aber alles beschreibt: Rolle,
   Aufgabe, Werkzeugrechte, Modell-Stufe, Schutzregeln, Freigaben. Teile davon gibt es schon als offene
   Standards: `AGENTS.md` (Regeln), `SKILL.md` (Skills), MCP (Werkzeuge). Für Rollen und Schutzregeln
   gibt es keinen Standard — dort wird unser eigenes Format die Quelle.
2. **Ein Übersetzer je Harness** — erzeugt beim Installieren oder beim Harness-Wechsel automatisch die
   Dateien, die das jeweilige Harness braucht. Du siehst sie nie und bearbeitest sie nie.
3. **Eine zentrale Ablage** — die Kits liegen einmal auf dem Rechner (heute schon
   `~/.claude/team-kits`), im Projekt steht nur ein Verweis (**FR-0020**, „dünne Installation“). In
   Synaipse wäre das die Erweiterungs-Bibliothek (P6: „Settings > Extensions“).
4. **Was ein Harness nicht kann, wird gemeldet, nicht verschwiegen** — der Übersetzer schreibt es in die
   Fähigkeiten-Tabelle (§4), statt eine Regel still wegzulassen.

Das ist die Neuentscheidung des Quellformats vom 14.07.: **von „Claude-Format als Quelle“ zu „neutrale
Quelle, Claude ist nur ein Übersetzungsziel unter mehreren“.** Sie fällt sowieso an, sobald ein drittes
Harness dazukommt (der Stolperdraht von damals), und sie gehört an den Anfang, nicht ans Ende.

## 5b. Was ist ACP?

**ACP = Agent Client Protocol.** Eine offene, gemeinsame „Sprache“, in der ein Programm mit einer
Oberfläche (z. B. Synaipse) einem KI-Arbeitsprogramm (Claude Code, Codex, Gemini, OpenCode …) sagt:
„starte eine Sitzung“, „hier ist die nächste Nachricht“, „zeig mir, was du tust“, „frag mich, bevor du
das darfst“. Vergleich: **wie USB für Agenten** — die Oberfläche muss nicht für jedes Programm einen
eigenen Stecker bauen, sondern spricht einmal ACP, und über 50 Agenten verstehen es schon. Gestartet vom
Editor Zed, offen (Apache-Lizenz), JetBrains macht mit. Für Synaipse wäre das ein Weg, in P2 mehrere
Harnesse **gleichzeitig** anschließbar zu machen, statt nur einen Kandidaten (deepseek-harness). Grenze:
ACP überträgt den Chat nicht von einem Harness zum anderen — dafür bleibt der eigene Chat-Speicher (§3).

## 6. Etappen

| # | Etappe | Was danach feststeht | Aufwand (grob) |
|---|---|---|---|
| **E0** | **Messrunde „Claude Code mit fremdem Modell“**: Kimi-Abo, DeepSeek-API, ein lokales Modell. Laufen alle Schutzregeln, Hilfsagenten, Freigaben? | Ob Claude Code als Standard-Harness für alle Modelle taugt (DEC-0115 P5) | 1–2 Tage; du trägst die Schlüssel selbst ein |
| **E1** | **Fähigkeiten-Tabelle** je Harness × Modell (§4), gemessen wie damals bei Codex | Welche Kombination welche Stufe hat | je Harness ~1 Tag |
| **E2** | **ACP-Probe in Synaipse**: die Oberfläche steuert Claude Code und Codex über ACP, ein Fenster, zwei Harnesse | Ob ACP die gemeinsame Oberfläche trägt | ~1 Woche |
| **E3** | **Neutraler Chat-Speicher + Übergabe + Wechseltest** (§3) | „Der Chat überlebt den Wechsel“ gemessen | 1–2 Wochen |
| **E4** | **Drittes Harness als Kit-Ziel** (Kimi CLI oder Qwen Code), Neuentscheidung des Quellformats vom 14.07. | Ob die Kit-Quelle Claude-nativ bleibt oder neutral wird | Wochen |
| **E5** | App-Politur: Desktop-Hülle, Einstellungen, Tarif-Übersicht | Nutzbar im Alltag | offen |

Vorher (klein, sofort sinnvoll): **synaipse-unified auf das aktuelle Kit heben** — sonst arbeitet das
Programm, das den Motor später benutzen soll, mit einer zwei Monate alten Fassung davon.

## 7. Offene Fragen an dich

1. Ist die Aufteilung **Synaipse = das Programm, AgentAndSkills = sein Team-Kit-Modul (P6/P8)** so richtig?
1a. Soll die **neutrale Kit-Quelle** (§5a) als erste Etappe kommen — vor dem dritten Harness?
2. Soll E0 mit **Kimi** (Abo) oder **DeepSeek** (API) anfangen? Und welches lokale Modell hast du oder willst du?
3. Soll Synaipse ein **Browser-Programm** bleiben oder eine **Desktop-App** werden (M4 ist dort geplant)?
4. Welches **dritte Harness** ist dir wichtiger: Kimi CLI (dein Abo), Qwen Code, Gemini CLI?
5. Darf synaipse-unified jetzt auf das aktuelle Kit gehoben werden?

## 8. Risiken

- **Anthropic-Regeln:** Claude-Abo nur in Anthropic-Programmen; Claude Code mit fremden Modellen nicht
  unterstützt. Kann sich jederzeit ändern → darum E0 zuerst und regelmäßig nachmessen (Watcher).
- **Jedes Harness hat andere Lücken** (Codex: kein Spawn-Veto, Freigabe-Werkzeug nicht abfangbar) →
  abgestuft und sichtbar (P3), nie still.
- **Pflegeaufwand wächst mit jedem Harness** → nur Harnesse aufnehmen, die gemessen tragen; die
  Copilot-Entfernung ist der Präzedenzfall für ein ehrliches Nein.
- **Werkzeug-Qualität schwankt je Modell** (Feldberichte über falsch gemeldete Erfolge) → der Prüfer bleibt
  Pflicht, gerade bei fremden Modellen.

## 9. Meine eigenen Vorschläge (nicht von dir verlangt)

- **ACP statt Eigenbau** für die Verbindung Oberfläche ↔ Harness: spart die teuerste Arbeit und
  bringt 50+ Agenten gratis mit.
- **Tarif-Wächter:** die Watcher melden schon Modell- und Preisänderungen; daraus kann Synaipse später
  einen Hinweis machen („Kimi ist jetzt günstiger für diese Rolle“) — genau dein „schnell wechseln, wenn
  sich Tarife ändern“.
- **Rolle × Modell statt nur Harness × Modell:** der Kernel kann heute schon je Rolle ein Modell wählen.
  Später z. B. Bauen mit Claude, Prüfen mit Kimi — ein zweites Modell als Prüfer findet andere Fehler.
