# Research: was sich bei Anthropic/Claude seit ca. 2026-08-10 geaendert hat

Auftrag: FR-0023 (provider-unabhaengiges Harness). Frage des Nutzers: "Claude Design wurde
wohl komplett integriert oder so -- was hat sich bei Anthropic/Claude sonst noch getan."
Fenster: ca. 2026-08-10 bis 2026-09-25. Heute: 2026-09-25.

**Was hier NICHT wiederholt wird:** `radar/2026-09-25-claude-by-claude.md` (gelesen vor
dieser Recherche) deckt den Claude-Code-Changelog 2.1.270-2.1.282 (13.-24.09.2026) im Detail
ab -- Opus 5.5 als neues Standard-Opus, den Preis-Anker-Fehler in `model_tiers.yaml`,
natives `AGENTS.md`-Lesen, `.claude/rules/`, neue Hook-Events, u.v.m. Wer das lesen will:
dort nachschlagen, nicht hier. Diese Datei deckt den **Rest der Anthropic-Produktflaeche**
ab: die Apps (claude.ai, Desktop, Mobile), Cowork, Claude Design, Skills/Marketplace,
Memory/Projects, Artifacts, Connectors/MCP, das Agent SDK, Preise/Plaene. Modell-Lineup
(Opus 5.5 GA 2026-09-22) nur kurz, wie beauftragt.

Jede Aussage ist mit Quelle + Datum belegt. Herstelleraussagen ("laut Anthropic ...",
Marketing-Formulierungen) sind als **Behauptung** markiert, nicht als gemessene Tatsache.

---

## 1. Claude Design -- was es ist, und was "integriert" heisst

**Was es ist** (2-3 Saetze): Claude Design ist ein im April 2026 gestartetes Anthropic-Produkt,
mit dem man aus Prompts, Bildern, Dokumenten oder auch ganzen Code-Repos schnelle visuelle
Entwuerfe erzeugt -- Prototypen, Folien, One-Pager, Landingpages -- wobei es nach Herstelleraussage
automatisch das eigene Design-System des Nutzers anwendet. Seither wurde es mehrfach erweitert:
engere Anbindung an Claude Code (Design-zu-Code-Uebergabe per `/design`-Befehl im Terminal) und,
laut einer Ankuendigung von Mitte 2026, bessere Anbindung an Unternehmens-Design-Systeme, Codebases
und Markenregeln.

**Was "integriert" am 2026-09-16 konkret bedeutet** (gemessen gegen den offiziellen Release-Note-
Eintrag, nicht nur eine Presse-Zusammenfassung): Anthropic hat an diesem Tag Claude Chat und Claude
Cowork zu einer Oberflaeche verschmolzen ("Unified Chat and Cowork Experience") und im selben
Schritt **Claude Design, Claude Slides und Claude Docs in jede Konversation** verfuegbar gemacht,
statt sie an einen eigenen Modus zu binden. Wortlaut der Release Notes: "Claude Design, Slides, and
Docs now available in any conversation" -- verfuegbar auf allen Plaenen, bei Enterprise-Plaenen
sind Beta-Funktionen standardmaessig aus. Rollout ueber mehrere Wochen, zuerst Pro/Max auf
Web/Desktop/Mobile, Team/Free folgen.

Das heisst konkret: "integriert" bezieht sich **nicht** auf Claude Code oder die Desktop-App im
engeren technischen Sinn, sondern auf **claude.ai / die Claude-Apps** -- Design ist jetzt ein
Werkzeug, das Claude innerhalb eines normalen Chats von selbst zieht, statt dass man vorher in
einen "Cowork"- oder "Design"-Modus wechseln musste.

- Quellen: support.claude.com/en/articles/12138966-release-notes (gelesen 2026-09-25, Eintrag
  16.09.2026); techcrunch.com/2026/09/16/anthropic-merges-claude-chat-and-cowork-in-one-interface
  (gelesen 2026-09-25); techcrunch.com/2026/04/17/anthropic-launches-claude-design-a-new-product-for-creating-quick-visuals
  (Launch, gelesen 2026-09-25); itbrief.asia/story/anthropic-expands-claude-design-with-new-connectors
  (gelesen 2026-09-25, Datum des beschriebenen Updates in der Quelle nicht praezise, daher als
  Hintergrund markiert, nicht als Fenster-Ereignis).
- **Relevanz fuers Harness**: keine direkte -- Claude Design ist ein claude.ai/Cowork-Feature ohne
  Bezug zu Claude Code, Skills-Format oder MCP. Einzig indirekt: es zeigt das allgemeine Muster
  dieses Fensters (siehe Abschnitt 2) -- Anthropic loest getrennte "Modi" zugunsten einer
  einzigen Oberflaeche auf, was fuer ein provider-uebergreifendes Harness bedeutet, dass
  Feature-Grenzen bei Claude zunehmend **Produkt-intern** verschwimmen, waehrend die
  API/Claude-Code-Seite (Skills, MCP, Agent SDK) separate, stabilere Vertraege bleibt.

## 2. Claude-Apps: Chat/Cowork-Fusion, Mobile, Desktop

**Cowork geht in "Claude" auf** (2026-09-16, dieselbe Ankuendigung wie oben): Man waehlt nicht
mehr zwischen "Chat" und "Cowork" -- bestehende Tasks, Projekte, Connectors und Dateien werden
uebernommen. Rollout ueber mehrere Wochen. Vorher war Cowork ein eigener Desktop-Tab (seit April
2026 GA), in dem Claude Dateien liest, geplante Aufgaben faehrt und fertige Arbeit zurueckliefert.

- Quellen: techcrunch.com/2026/09/16/... (s.o.); 9to5mac.com/2026/09/16/anthropic-merging-claude-cowork-with-chat
  (gelesen 2026-09-25); support.claude.com Release Notes, Eintrag 16.09.2026.
- **Relevanz fuers Harness**: keine direkte -- reines Endnutzer-App-Feature, kein API-/CLI-Vertrag.

**Mobile**: Claude Cowork ist jetzt auch auf Web und Mobile verfuegbar (vorher Desktop-only),
Rollout beginnend mit dem Max-Plan (Datum in Quelle nicht praezise, im Fenster). CarPlay-Anbindung
fuer die iOS-App wurde ergaenzt (Sprachsteuerung ueber das Infotainment-System).
- Quellen: pymnts.com/news/artificial-intelligence/2026/anthropic-launches-mobile-access-for-claude-cowork
  (gelesen 2026-09-25); Sammel-Recherche zu Mobile-Updates, gelesen 2026-09-25 (Herstellerangaben,
  Einzeldatum fuer CarPlay nicht verifiziert -- als Behauptung markiert).
- **Relevanz fuers Harness**: keine.

**Datenexport (bestehendes Feature, zur Vollstaendigkeit auf Portabilitaet gepruft, nicht neu in
diesem Fenster)**: Nutzer koennen unter Settings > Privacy > "Export data" ihre Chat-Historie und
Kontodaten als JSON in einer ZIP-Datei herunterladen (Web/Desktop; nicht aus der iOS/Android-App).
Das ist die bestehende GDPR-Auskunftsfunktion, kein neues Feature dieses Fensters -- aber direkt
portabilitaetsrelevant, deshalb hier vermerkt.
- Quelle: support.claude.com/en/articles/9450526-export-your-claude-data (gelesen 2026-09-25;
  Aenderungsdatum der Seite nicht ermittelbar, daher nicht als "neu" gezaehlt).
- **Relevanz fuers Harness**: **mittel** -- es existiert ein offizieller Weg, Chat-Verlaeufe als
  JSON zu exportieren. Das deckt aber nur Konto-/Chatdaten ab, nicht Memory-Eintraege, Projects,
  Skills oder Plugin-Konfiguration einzeln (siehe Abschnitt 5) -- also Teil-Portabilitaet, keine
  vollstaendige.

## 3. Claude Marketplace (Plugins/Connectors) -- neu, 2026-09-23

**Was es ist**: Anthropic hat am 23.09.2026 den "Claude Marketplace" gestartet, laut eigener
Ankuendigung "one place to discover plugins, agents, and services from our partners". Drei
Kategorien: (a) ueber 2.000 Connectors/Plugins (u.a. Atlassian, Google, Microsoft, Notion,
Salesforce), (b) Claude-gestuetzte Agenten/Produkte von Drittanbietern (u.a. CrowdStrike,
Cursor, Harvey, Legora, Lovable, Snowflake), (c) Beratungs-/Systemintegrations-Partner aus dem
Claude Partner Network (Accenture, BCG, Deloitte). Teams koennen einen Teil ihres vertraglich
zugesagten Anthropic-Budgets fuer Marketplace-Kaeufe verwenden.
- Quelle: claude.com/blog/claude-marketplace, gelesen/gefetcht 2026-09-25 (Volltext abgerufen).
- **Relevanz fuers Harness -- Portabilitaet**: Die Ankuendigung selbst nennt **explizit**
  "open standards pioneered by Anthropic" als Grundlage der Marketplace-Eintraege: **Model
  Context Protocol (MCP) und Agent Skills**. Das ist eine Bestaetigung, dass MCP und das
  SKILL.md-Format die tragenden, offenen Formate bleiben, auf die sich ein provider-unabhaengiges
  Harness stuetzen kann -- der Marketplace selbst ist aber eine Anthropic-Vertriebsflaeche ohne
  Aussage zu Export/Import oder Lock-in (im gelesenen Text nicht erwaehnt).

**Skill-Format als moegliches offenes Cross-Tool-Format (aus Sekundaerquellen, als Behauptung
markiert -- nicht auf einer offiziellen Anthropic-Seite verifiziert):** Mehrere Drittquellen
behaupten, das SKILL.md-Format folge einem herstelleruebergreifenden "Agent Skills"-Standard
(unter agentskills.io) und dieselbe SKILL.md funktioniere unveraendert in Codex CLI, OpenCode,
Cursor, Gemini CLI u.a. Die offizielle Anthropic-Doku (platform.claude.com, Agent-Skills-Overview,
gelesen 2026-09-25) beschreibt Skills nur als Anthropic-eigenes Format fuer Claude API/Claude
Code/claude.ai und macht **keine** Aussage zu Fremd-Tool-Kompatibilitaet -- die Cross-Tool-
Behauptung stammt ausschliesslich aus Drittquellen (z.B. claudefa.st, totalum.app) und ist daher
als **unbestaetigte Behauptung** zu behandeln, nicht als Faktum.
- Quellen: div. Sekundaerquellen zu "Agent Skills als offener Standard", gelesen 2026-09-25 (siehe
  Suchergebnisse); Gegenprobe: platform.claude.com/docs/en/agents-and-tools/agent-skills/overview,
  gefetcht 2026-09-25 -- **kein** Hinweis auf Fremdanbieter-Kompatibilitaet dort.
- **Relevanz fuers Harness -- WICHTIG, gemessen gegen die offizielle Doku**: Dieselbe Doku-Seite
  stellt klar: **"Custom Skills do not sync across surfaces"** -- eine in Claude Code angelegte
  Skill (`~/.claude/skills/` bzw. `.claude/skills/`) ist getrennt von einer in claude.ai
  hochgeladenen Skill und von einer ueber die API hochgeladenen Skill; jede Oberflaeche verwaltet
  ihre Skills separat, claude.ai kennt kein zentrales Admin-Management fuer Custom Skills. Das ist
  eine **innerhalb-Anthropic-Fragmentierung**, keine externe Portabilitaet -- fuer dieses Repo
  bedeutet es: selbst wenn SKILL.md als Dateiformat wiederverwendbar waere, gibt es bei Anthropic
  selbst keinen eingebauten Sync/Export-Mechanismus zwischen den drei Claude-Oberflaechen.

## 4. Connectors / MCP

**MCP-Spezifikation 2026-07-28 (knapp vor dem Fenster, aber noch wirksamer Hintergrund):** Die
MCP-Spezifikation wurde auf einen zustandslosen Protokollkern umgestellt -- Sitzungsverfolgung auf
Protokollebene entfaellt, Protokollversion/Client-Identitaet/Capabilities wandern in ein
`_meta`-Feld pro Anfrage. Das erlaubt MCP-Server hinter gewoehnlichen Load-Balancern ohne Sticky
Sessions. Datum liegt vor dem beauftragten Fenster (28.07.2026), wird hier nur als Kontext
genannt, weil er die Basis fuer die Marketplace-Connectors ist.
- Quelle: blog.modelcontextprotocol.io/posts/2026-07-28 (gelesen 2026-09-25).
- **Relevanz fuers Harness**: hoch, aber ausserhalb des Fensters -- MCP bleibt der offene,
  herstellerneutrale Verbindungsstandard, den das Harness fuer Tool-Anbindung nutzen kann,
  unabhaengig vom LLM-Anbieter.

**Neu im Fenster -- `mcp-client-2026-09-15` Beta-Header (Claude API):** Ab 15.09.2026 kann ein
Client per Beta-Header die von einem MCP-Server gelieferte Tool-Liste "anpinnen": Anthropic
protokolliert die abgerufene Toolliste in einem `mcp_tool_listing`-Block, und wenn dieser Block in
einer Folgeanfrage zurueckgeschickt wird, sieht Claude fuer den Rest der Konversation exakt diese
Toolliste -- auch wenn der Server seine Tools zwischenzeitlich aendert.
- Quelle: Sekundaerrecherche zu platform.claude.com/docs/en/agents-and-tools/mcp-connector,
  gelesen 2026-09-25 (Wortlaut aus Release-Notes-Aggregatoren, nicht direkt aus der Primaerquelle
  zitiert -- als weitgehend gesichert, aber ohne eigenen Primaerseiten-Abruf markiert).
- **Relevanz fuers Harness**: klein, aber konkret -- ein Mechanismus, um MCP-Tool-Drift innerhalb
  einer Sitzung zu vermeiden, ist genau die Art Stabilitaetsgarantie, die ein provider-uebergreifendes
  Dispatch/Hook-System (das Tool-Listen ueber mehrere Anbieter hinweg konsistent halten muss)
  brauchen wuerde -- aktuell Anthropic-spezifisch als Beta-Header, kein Teil der offenen
  MCP-Spezifikation selbst.

**Connector-Verzeichnis**: laut Drittquelle (Stand September 2026) listet das offizielle Claude-
Connectors-Verzeichnis inzwischen ueber 800 Connectors; jeder verbindet sich ueber Anthropics
Cloud-Infrastruktur, einheitlich ueber claude.ai, Desktop, Cowork und Mobile.
- Quelle: composio.dev/content/best-claude-connectors und Folgequellen, gelesen 2026-09-25
  (Zahlenangabe als Behauptung einer Drittquelle markiert, nicht auf einer Anthropic-Seite
  primaer verifiziert).
- **Relevanz fuers Harness**: gering -- Konsum-Feature fuer claude.ai, kein CLI-/Harness-Bezug.

## 5. Memory und Project Knowledge

**Memory-Ueberholung, 2026-08-25** (offizieller Blogpost, Volltext gelesen): Anthropic hat das
Memory-Modell umgebaut -- statt taeglicher Zusammenfassungen jetzt einzelne, nach Themen
("Topics") kategorisierte Eintraege, die live waehrend des Gespraechs entstehen ("Claude now adds
topics to memory as you chat, instead of summarizing conversations after they end"). Nutzer sehen
und verwalten jedes Thema einzeln (lesen/bearbeiten/loeschen) unter Settings. Sensible Themen
(Gesundheit, Ethnie, Religion, Politik, Geschlechtsidentitaet u.ae.) werden standardmaessig NICHT
gespeichert, koennen aber vom Nutzer aktiv eingeschaltet werden; Ausweisnummern, Vorstrafen,
Einwanderungsstatus werden unabhaengig von der Einstellung nie gespeichert. **Wichtigster Punkt
fuer dieses Fenster**: Memory ist jetzt ueber Chat UND Cowork hinweg identisch/geteilt ("the memory
you use in chat is the same as in Claude Cowork") -- vorher waren das getrennte Speicher.
Verfuegbar auf Free/Pro/Max, Web/Desktop/Mobile.
- Quelle: claude.com/blog/claudes-memory-works-everywhere-and-you-decide-whats-in-it, Volltext
  gefetcht 2026-09-25; techcrunch.com/2026/08/25/claude-cowork-finally-remembers-what-you-told-the-app-in-chat
  (gelesen 2026-09-25).
- **Portabilitaet -- explizit gepruft, NICHT gefunden**: Der Blogpost enthaelt **keine** Aussage
  zu Datenexport, Portabilitaet oder ob der Speicher konto- oder anbietergebunden ist. Kein
  Hinweis auf eine Export-Funktion speziell fuer Memory-Eintraege (getrennt vom allgemeinen
  Datenexport aus Abschnitt 2).
- **Relevanz fuers Harness**: **mittel** -- Memory ist ein reines claude.ai/Cowork-Konzept ohne
  Beruehrung mit Claude Code, der API oder MCP; fuer ein provider-agnostisches Harness (das auf
  Dateien/Items im Repo als "Gedaechtnis" setzt, nicht auf Anbieter-Memory) bedeutet das: Claude-
  eigenes Memory bleibt weiterhin ausserhalb der Repo-eigenen `project_memory/`-Mechanik und ist
  nicht uebertragbar -- der bestehende Architekturentscheid, das Gedaechtnis im Kernel statt im
  Anbieter zu fuehren, bleibt also weiterhin die einzige providerneutrale Loesung.

**Projects mit mehreren parallelen Threads (Beta, im Fenster genannt, Datum in Quellen nicht
praezise, daher als "waehrend des Fensters gesehen" markiert)**: Ein Projekt kann jetzt mehrere
parallele "Threads" mit gemeinsamem Speicher und einer "Projekt-Bibliothek" koordinieren; ein
"Koordinator"-Thread steuert Arbeits-Threads. Ausdruecklich: Projects/Chat-Suche sind **eigene**
Speicherraeume, die **nicht** zu Claude Code, der API oder einem anderen Anbieter-Assistenten
uebergreifen (Formulierung einer Drittquelle, sinngemaess wiedergegeben).
- Quelle: memorylake.ai/en/blogs/claude-projects-thread-memory, gelesen 2026-09-25 (Drittquelle,
  keine Anthropic-Primaerquelle gefunden -- als Behauptung markiert).
- **Relevanz fuers Harness**: bestaetigt denselben Punkt wie oben -- Projekt-Wissen bleibt
  Anthropic-intern und plattformgebunden, kein Cross-Provider-Mechanismus vorhanden oder
  angekuendigt.

## 6. Artifacts

Bereits in Abschnitt 1 mitbehandelt: Die 2026-09-16-Aenderung macht Artifacts/Design/Slides/Docs
konversationsweit statt modusgebunden verfuegbar. Keine eigene, ueber Abschnitt 1 hinausgehende
Aenderung im Fenster gefunden.
- **Relevanz fuers Harness**: keine zusaetzliche.

## 7. Agent SDK

Aus Aggregator-Quellen (keine Primaerquelle einzeln gefetcht, da es sich um Changelog-Kleinteile
handelt): Im September 2026 wurden `pasted_content` zu `SDKUserMessage` und optionale
Latenzfelder fuer Remote-Sessions zur "success result"-Nachricht ergaenzt. Ausserdem (Juli 2026,
knapp vor dem Fenster, als Hintergrund) ein `agent-memory-2026-07-22`-Beta-Header, der die
Reihenfolge von Memory-Store-Listing-Ergebnissen stabilisiert; von den SDKs (Python 0.116.0,
TypeScript 0.110.0 u.a.) inzwischen standardmaessig gesendet.
- Quelle: Sekundaerrecherche gegen platform.claude.com/docs/en/release-notes/overview und
  github.com/anthropics/claude-agent-sdk-typescript/releases, gelesen 2026-09-25 (Einzelheiten
  nicht primaer verifiziert, als vermutlich zutreffend markiert).
- **Relevanz fuers Harness**: gering -- Detailaenderungen am SDK-Nachrichtenformat, kein
  Architektur- oder Formatwechsel, der die Provider-Abstraktion von FR-0023 beruehrt.

## 8. Modell-Lineup (nur kurz, wie beauftragt)

Claude Opus 5.5 wurde am 2026-09-22 GA und ist jetzt das Standard-Opus-Modell ($4/$20 pro MTok,
1M Kontext) -- bereits ausfuehrlich und mit Auswirkung auf `model_tiers.yaml` in
`radar/2026-09-25-claude-by-claude.md` Punkt 1+2 behandelt, hier nicht wiederholt. Ausserdem am
2026-09-01 GA gegangen: Fable 5.1 und Mythos 5.1 (Mythos bleibt laut Radar-Bericht limitierter
Zugang/Project Glasswing).
- Quelle: support.claude.com Release Notes, Eintraege 01.09. und 22.09.2026, gelesen 2026-09-25.

## 9. Preise/Plaene

Am 29.08.2026 kuendigte Anthropic an, dass ab 14.09.2026 das **staendige woechentliche
Nutzungslimit fuer Claude Code dauerhaft 25% ueber dem Stand vor der Sommer-Promotion** liegt
(die Promotion selbst lief 13.05.-13.09.2026 mit +50%). Ausserdem: Enterprise-Preise wurden auf
eine einzige Sitzplatzart vereinheitlicht ($20/Nutzer/Monat, jaehrlich abgerechnet, Nutzung separat
zu Standard-API-Preisen) -- Datum der Umstellung in den Quellen nicht praezise auf das Fenster
eingrenzbar, daher als Hintergrund markiert.
- Quelle: Sekundaerrecherche (Aggregatoren, u.a. intuitionlabs.ai, benchlm.ai), gelesen
  2026-09-25 -- Primaerquelle (anthropic.com/news oder claude.com/pricing) fuer das exakte
  29.08.-Datum nicht einzeln gefetcht, daher als **wahrscheinlich zutreffend, nicht einzeln
  primaer verifiziert** markiert.
- **Relevanz fuers Harness**: keine direkte -- Preis-/Limit-Politik, kein Format- oder
  Architektur-Punkt.

## 10. Skills-Sicherheits-Scan (Enterprise, knapp vor dem Fenster)

Am 06.08.2026 (vier Tage vor dem beauftragten Fenster, hier nur der Vollstaendigkeit halber kurz
erwaehnt): Claude-Enterprise-Plaene koennen eine automatische Pruefung von Drittanbieter-Skills/
Plugins auf bekannte Schadmuster beim Hochladen/Bearbeiten aktivieren (Beta).
- Quelle: support.claude.com Release Notes, Eintrag 06.08.2026, gelesen 2026-09-25.
- **Relevanz fuers Harness**: gering -- ein Sicherheitsfeature der Anthropic-eigenen
  Skill-Upload-Flaeche (claude.ai/Cowork), nicht des Dateiformats SKILL.md selbst.

---

## Zusammenfassung: was fuer FR-0023 (Provider-Abstraktion) zaehlt

1. **MCP und das SKILL.md-Format bleiben die offenen, providerneutralen Anker** -- von Anthropic
   selbst im Claude-Marketplace-Launch (2026-09-23) als "open standards pioneered by Anthropic"
   bezeichnet (Abschnitt 3). Das bestaetigt, worauf ein provider-agnostisches Harness bauen
   sollte -- aber die Cross-Tool-Kompatibilitaetsbehauptung selbst stammt nur aus Drittquellen,
   nicht aus Anthropics eigener Doku.
2. **Innerhalb von Anthropic selbst gibt es keinen Sync/Export fuer Skills, Memory oder Projects**
   zwischen claude.ai, Claude Code und der API (Abschnitte 3 und 5, aus der offiziellen
   Agent-Skills-Doku bzw. Sekundaerquellen zu Memory) -- der bestehende Architekturentscheid
   dieses Repos, Gedaechtnis/Zustand im eigenen Kernel statt beim Anbieter zu fuehren, bleibt
   damit die einzig providerneutrale Wahl, nicht nur pragmatisch, sondern weil Anthropic selbst
   keine Cross-Surface-Portabilitaet anbietet.
3. Alles Uebrige in diesem Fenster (Design/Cowork/Chat-Fusion, Memory-Ueberholung, Marketplace,
   Mobile/CarPlay) ist **claude.ai/Cowork-Produktflaeche** ohne Beruehrungspunkt mit Claude Code,
   dem Skills-Dateiformat oder MCP -- also ohne direkten Hebel auf das Harness in diesem Repo.
