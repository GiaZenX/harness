# FR-0023: Harness für alle Anbieter, ein Rechercheertrag (2026-09-25)

Auftrag: Recherche zu FR-0023 (Harness, das mit jedem Anbieter läuft), Blick auf FR-0020 und FR-0025.
Nur gelesen; diese Datei ist die einzige Schreibstelle. Alle Außenquellen am **2026-09-25** gesehen,
außer wo ein anderes Datum steht. Kennzeichnung: **[offiziell]** = Hersteller-Doku, Hersteller-Repo
oder Hersteller-Changelog; **[Hinweis]** = Blog, Vergleichsseite, Drittanbieter-Issue oder
Suchmaschinen-Auszug. Ein Hinweis ist ein Anhaltspunkt und kein Beleg. **[Repo]** = in diesem Repo
gelesen. Eine Empfehlung steht hier absichtlich nicht; Abschnitt 6 nennt die Fragen an den Nutzer.

Der Wunsch in einem Satz: eine eigene App, in der man den KI-Anbieter wechselt (Anthropic, OpenAI,
Google, Kimi, Qwen, DeepSeek, lokal) und dabei nichts verliert (Chats, Plugins, Repos, Zustand).
Jeder Anbieter soll gleich arbeiten, ohne Kit und mit Kit.

---

## 1. Was das Repo heute schon tut, und wo es an Claude/Codex hängt (10 Zeilen) [Repo]

1. **Neutral sind** der Kernel (`team-kits/kernel/`, reines Python, YAML-Zustand in `project_memory/`),
   die Items, die Freigabe-Aufzeichnung und die Gate-*Logik* (Python-Skripte, die JSON über stdin lesen).
2. **Eine Kit-Quelle, zwei Zielformate:** `gen_provider_artifacts.py` übersetzt die installierten
   `.claude/**`-Dateien in `.codex/config.toml`, `.codex/hooks.json`, `.codex/agents/<role>.toml` und
   `.agents/skills/`. `hooks/_compat.py` gleicht die Codex-Nutzlast an (`apply_patch` → `Edit`).
3. **Quellformat-Entscheidung (HARNESS_LOG 2026-07-14):** Die Quelle bleibt bewusst Claude-nativ.
   Neutral ist nur die *Bedeutung*: Rang-Aliase statt Modellnamen (`model_tiers.yaml`: drei Ränge je
   Anbieter, DEC-0076), Verfassung als `AGENTS.md`, `codex:`-Overlay als Ventil. Stolperdraht: das
   Overlay wächst, ein **dritter Anbieter braucht Artefakte**, oder der `@import`-Vertrag bricht.
4. **Claude-spezifisch:** Sitzungsbindung (`agent:` in `settings.json`), Spawn-Wächter auf `Agent|Task`,
   Freigaben über `AskUserQuestion` → `gate_approval.py`, Werkzeug-Allowlists je Rolle in der Frontmatter,
   Übergabe am Marker in Zeile 1 von `./CLAUDE.md`.
5. **Codex-Lücken, benannt:** `Agent|Task` und `AskUserQuestion` stehen in `CODEX_UNSUPPORTED_TOOLS`.
   `SubagentStart` kann einen Spawn nicht verhindern (openai/codex#32753 „not planned“). Hooks laufen
   erst nach Projekt- und `/hooks`-Trust. Ein Worktree-Lauf ohne Trust hat **keine** Gates (Radar-Codex 09-25, Punkt 3).
6. **Radar 09-25:** Claude Code liest `AGENTS.md` jetzt nativ (2.1.277). Der Kit-Shim ist die dritte
   Zeile der offiziellen Tabelle und bricht nicht. Er ist aber die einzige Stelle, an der die
   Übergabe an den PM erkannt wird, und darf deshalb nicht „vereinfacht“ werden (Claude-Radar, Punkt 3).
7. **Radar 09-25, Codex:** `additionalContext` auf `PreToolUse` ist jetzt dokumentiert (#19385
   geschlossen). Das Overlay erreicht fünf Codex-Hook-Fähigkeiten gar nicht; der Stolperdraht kann das
   nicht sehen, weil daraus Schweigen entsteht und keine Ansammlung (Punkt 5). Hook-Schichten werden
   **zusammengeführt**; ob ein `allow` aus einer höheren Schicht ein `deny` des Kits überstimmt, ist ungemessen (Punkt 6).
8. **Schon vorbereitet für eine eigene App:** `kernel/sdk_approval.py` (FR-0083) ist die Tür, durch die ein
   einbettendes Programm aus dem Agent-SDK-Callback `canUseTool` eine Freigabe prägt, mit benannter
   Herkunft. Vorarbeit: `docs/research/2026-08-15-multi-provider-eigene-oberflaeche.md` (Abo-Matrix je Anbieter,
   Agent SDK als Motor, claude-code-router und claudecodeui als Vorbilder).
9. **Nicht vorhanden:** kein dritter Anbieter, kein eigener Agentenkreislauf, kein Chat-Export, keine
   Übertragung von Chats zwischen Anbietern. Der Kernel kennt Pfade wie `.claude/hooks` (`hashing.py`,
   `report.py`, `presets.py`) und ist darum im Code nicht völlig neutral, auch wenn die Bedeutung es ist.
10. **Ehrliche Kurzform:** Neutral sind Zustand, Regeln und Gate-Logik. An den Anbieter gebunden sind
    die Stellen, an denen die Gates *eingehängt* werden (Hooks), wer spricht (Sitzungsbindung, Freigabe-Tool)
    und wer spawnt (Subagenten).

---

## 2. Die Außenwelt, Teil 1: Laufzeiten, die viele Anbieter bedienen

### 2.1 Übersicht

„Blockiert vor dem Werkzeug“ heißt: Ein Skript oder Plugin kann einen Werkzeugaufruf **verweigern**,
bevor er ausgeführt wird. Genau das braucht jedes Gate dieses Harness.

| Laufzeit | Anbieter | Blockierender Pre-Tool-Hook | Subagenten | Skills | AGENTS.md | Sitzungsexport | Lizenz / Aktivität |
|---|---|---|---|---|---|---|---|
| **OpenCode** (anomalyco/opencode, vorher sst/opencode) | 75+ über AI SDK + models.dev, darunter Anthropic (API-Key), OpenAI, Google, Moonshot/Kimi, DeepSeek, Ollama, LM Studio, llama.cpp [offiziell] | Ja: JS/TS-Plugin `tool.execute.before`, ein `throw` blockiert. Dazu `permission.asked`/`permission.replied` [offiziell]. **Keine** Claude-Hook-Dateien nativ (Issue #12472 offen seit 2026-02-06) [offiziell] | Ja: Markdown-Frontmatter mit `model` (`provider/model-id`) und `permission` je Agent (`read`/`edit`/`bash`/`task`/`webfetch` → allow/ask/deny). **Ein Subagent kann einen anderen Anbieter nutzen** [offiziell] | Ja, liest auch `~/.claude/skills/` [offiziell] | Ja, dazu `CLAUDE.md` als Rückfall und `~/.claude/CLAUDE.md` [offiziell] | `opencode export` / `import` als JSON; Rundlauf-Fehler in 1.4.3 gemeldet (#21941) [offiziell] | MIT, rund 210k Sterne, v1.18.32 vom 2026-09-21 [offiziell] |
| **Goose** (aaif-goose/goose, seit 2026-04 in der AAIF) | 15+: Anthropic, OpenAI, Google, Ollama, OpenRouter, Azure, Bedrock … [offiziell] | Ja: `PreToolUse` mit Exit 2 oder `{"decision":"block"}`, **Claude-ähnliche Form**; Standard bei Hook-Fehler ist *durchlassen*, außer `on_failure: block`; nur Erlauben/Verweigern, kein Umschreiben der Eingabe [offiziell] | Ja, dazu Markdown-Agenten `.agents/agents/*.md` ab v1.34.0 [Hinweis: rulesync#2404] | Ja [offiziell: agentskills.io] | Ja (AAIF-Gründungsprojekt) | Rezepte (YAML-Abläufe); Chat-Export nicht geprüft | Apache-2.0, 54,6k Sterne, v1.52.0 vom 2026-09-23 [offiziell] |
| **Crush** (charmbracelet) | 25+, OpenAI-/Anthropic-kompatible Endpunkte, Ollama [offiziell] | Nur `PreToolUse`: Exit 2 blockiert, Exit 49 hält an, `allow` genehmigt [offiziell: docs/hooks] | nicht belegt | Ja | Ja (plus `CRUSH.md`) | nicht geprüft | **FSL-1.1-MIT** (quelloffen, anfangs nicht frei für Konkurrenzprodukte), 28,3k Sterne |
| **Cline** (+ CLI) | Anthropic, OpenAI, Google, OpenRouter, Bedrock, Vertex, Ollama, LM Studio, jede OpenAI-kompatible API [offiziell] | Ja: `PreToolUse` gibt `"cancel": true` zurück (**eigene Form, nicht Claude-förmig**), Skripte unter `.clinerules/hooks/`; laut Hersteller-Blog nur macOS/Linux [Hinweis: cline.bot/blog] | „Multi-agent teams“ [offiziell README] | Ja | nicht geprüft | nicht geprüft | Apache-2.0, 69,3k Sterne |
| **Kilo Code / Kilo CLI** | wie Roo/OpenCode, viele Anbieter | Die CLI ist ein **OpenCode-Fork** (Kilo CLI 1.0 vom 2026-02-03) [offiziell: kilo.ai]; Sitzungs-Hooks fehlen laut offener Anfrage [Hinweis] | Ja | Ja | Ja | nicht geprüft | MIT |
| **Roo Code** | – | – | – | – | – | – | **Eingestellt**: angekündigt 2026-04-21, Repo archiviert am 2026-05-15 [Hinweis: kilo.ai, Kilo auf X] |
| **Continue** | 100+ | 17 Hook-Events laut Drittquelle | – | – | – | – | **Am Ende**: von Cursor übernommen (2026-06-18), Repo schreibgeschützt [Hinweis: rulesync#3078 zitiert das README] |
| **OpenHands** (+ Software Agent SDK) | modellunabhängig (LiteLLM-Basis; in dieser Runde nicht erneut geprüft) | Ja: `PreToolUse` Exit 2 blockiert, **Exit 1 blockiert nicht**; die Doku verweist ausdrücklich auf den Claude-Code-Hook-Vertrag; auch Hooks vom Typ `agent` [offiziell] | Delegation vorhanden | Ja: `SKILL.md`, liest `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` [offiziell] | Ja | Gespräche als Objekte; Export nicht geprüft | MIT; SDK-Repo 1,2k Sterne. Sicherheitsbefund: LLM-Risikoeinstufung kann „LOW“ lügen (#4157) [offiziell] |
| **Gemini CLI** | **nur Gemini** (Google) [offiziell, soweit gelesen] | Ja: `BeforeTool`, Exit 2 oder `decision: "deny"`; `"ask"` gebaut, aber undokumentiert (#28046) [offiziell] | Ja: `.gemini/agents/*.md` mit `tools`, `model`, `max_turns` [offiziell] | Ja | per `contextFileName` einstellbar [Hinweis] | nicht geprüft | Apache-2.0 |
| **Qwen Code** / **Kimi Code CLI** | Qwen / Kimi (Herstellerwerkzeuge) | Qwen: `PreToolUse` Exit 2 oder `permissionDecision: "deny"`, **genau die Claude-Form** [offiziell: qwenlm.github.io]; Kimi: Hooks an Agenten [offiziell, nur als Suchauszug gesehen] | ja / ja | ja | – | – | Herstellerwerkzeuge |
| **Zed Agent** (Editor) | Zed-gehostet, API-Keys, Abos, Gateways, Ollama [offiziell] | **Keine Skript-Hooks gefunden**; Werkzeugrechte als allow/deny/confirm-Regeln [offiziell] | Profile | Ja (Skills ersetzen Rules) | Ja | – | Hauptklient von **ACP** (unten) |
| **Aider** | viele (LiteLLM) | keine Hook-Schicht bekannt (in dieser Runde nicht gemessen) | nein | – | liest AGENTS.md laut agents.md-Liste | – | – |
| **Claude Agent SDK** | offiziell nur Claude (API, Bedrock, Vertex, Foundry). Anthropic unterstützt ausdrücklich **nicht**, Claude Code über ein Gateway zu Nicht-Claude-Modellen zu leiten [offiziell: llm-gateway]; technisch geht es über `ANTHROPIC_BASE_URL` + LiteLLM [offiziell: LiteLLM-Doku]; Kimi, Qwen, DeepSeek und Ollama haben eigene Anthropic-Endpunkte [Repo: Recherche vom 2026-08-15] | Ja: dieselben Hooks wie Claude Code, dazu `canUseTool` [offiziell] | Ja | Ja, liest `.claude/` wie die CLI | Ja (über CLAUDE.md-Import) | Sitzungen: resume, fork | Kommerzielle Bedingungen; **claude.ai-Login in Drittprodukten nur mit Genehmigung** [offiziell] |
| **OpenAI Agents SDK** | OpenAI; andere über `ModelProvider`, OpenAI-kompatible `base_url`, LiteLLM/Any-LLM als „best-effort, beta“ [offiziell] | Tool-Guardrails, `needs_approval` [offiziell] | Handoffs | – | – | Sessions | eine Bibliothek, **keine** fertige Coding-Laufzeit |
| **Codex CLI selbst** | OpenAI; eingebaut `ollama`/`lmstudio` (`--oss`); eigene `model_providers`, aber **nur noch die Responses-API** (`wire_api = "chat"` entfernt) [offiziell: Config-Doku + openai/codex Discussion #7782; Entfernungsdatum Feb. 2026 nur als Hinweis] | Ja (siehe Abschnitt 1) | Ja (Spawn nicht verhinderbar) | Ja | Ja | App-Server (JSON-RPC) mit Threads und Freigabe-Anfragen an den Klienten [offiziell] | Apache-2.0 |
| **LiteLLM** (Gateway) | 100+ | – (reine Modellschicht) | – | – | – | – | **Lieferketten-Angriff** am 2026-03-24: PyPI-Versionen 1.82.7/1.82.8 waren bösartig [offiziell: LiteLLM-Sicherheitsblog] |

Nebenbefunde:
- **Übersetzer für Konfigurationen gibt es fertig:** `rulesync` (MIT, rund 1,5k Sterne) erzeugt aus einer
  Quelle Regeln, MCP, Befehle, Subagenten, Skills, **Hooks** und Rechte für über 50 Werkzeuge. Hooks und
  Rechte werden dabei am seltensten unterstützt [offiziell: Repo]. Dazu ähnlich `Chemaclass/agnostic-ai` [Hinweis].
  Das ist die fremde Verwandte unseres `gen_provider_artifacts.py`.
- **Eine Brücke Claude-Hooks → OpenCode gibt es als Drittanbieter-Plugin** (`magarcia/opencode-claude-hooks`,
  nach eigener Angabe rund 80 % Abdeckung; `Stop` mit Wiederaufnahme geht ohne Kern-Änderung nicht) [Hinweis].
- Quelltextstudie über elf Laufzeiten (Claude Code, Codex, Gemini CLI, Mistral Vibe, OpenHands, Aider,
  mini-SWE-agent, Hermes, Pi, OpenCode, OpenClaw): arXiv 2609.00006, eingereicht 2026-07-15 [Hinweis: Preprint].
  Nützlich als Landkarte, sagt aber nichts über übertragbare Gates.

### 2.2 Welche Laufzeit könnte die Gates und den Kernel *aufnehmen*?

Gemessen an dem, was die Gates brauchen: ein Veto vor jedem Werkzeug, auch in Subagenten; eine
Freigabe, die nur ein Mensch geben kann; eine Rolle je Agent mit eigenen Werkzeugrechten.

- **OpenCode ist der stärkste Kandidat auf dem Papier:** mehr als 75 Anbieter, gemischte Besetzung je Agent,
  Werkzeugrechte je Agent und je Subagent (`task`), ein blockierender Hook, Rechte-Ereignisse, ein
  Server/Klient-Aufbau mit SDK und Desktop-App, MIT-Lizenz, sehr aktiv. **Offen:** Ob
  `tool.execute.before` auch *in Subagenten* feuert, war eine Sicherheitslücke (#5894, geschlossen). Eine
  Drittpartei hat gegen 1.18.30 erneut nachgemessen und Widersprüchliches gefunden (nightgauge#1805, offen
  seit 2026-09-15) [Hinweis]. Die Hooks sind **JS im Prozess**, keine Shell-Skripte: Unsere Python-Gates
  bräuchten ein kleines Plugin, das sie mit Claude-förmiger Nutzlast aufruft. Kein Claude-Abo:
  Anthropic-Nutzung nur per API-Key (Plugins seit 1.3.0 entfernt, „Anthropic explicitly prohibits“) [offiziell].
- **Goose ist der Kandidat mit dem nächsten Hook-Vertrag:** Exit 2 und JSON-Block wie bei Claude, Matcher als
  Regex, Stiftung (AAIF) statt Firma, Apache-2.0. **Aber:** Bei einem Hook-Fehler lässt Goose standardmäßig
  durch (bei uns wäre `on_failure: block` Pflicht). Es gibt keine Eingabe-Korrektur, und
  Werkzeugrechte je Subagent sind in dieser Runde nicht belegt.
- **OpenHands SDK** ist als *Bibliothek* für eine eigene App interessant: Die Hooks folgen dem Claude-Vertrag,
  und es gibt eine REST-/TS-/Python-API. Es ist aber mehr Baukasten als fertige Laufzeit.
- **Gemini CLI, Qwen Code und Kimi CLI** sind Einzelanbieter-Werkzeuge. Sie wären der **dritte, vierte und
  fünfte Anbieter im heutigen Weg A** und keine Aufnahme-Laufzeit.
- **Nicht in Frage:** Roo (eingestellt), Continue (am Ende), Aider (keine Hooks, keine Subagenten), Zed Agent
  (keine Skript-Hooks), Crush (nur ein Hook-Typ; die Lizenz schränkt eine eigene App ein).

---

## 3. Die Außenwelt, Teil 2: offene Standards für Übertragbarkeit

| Bereich | Standard | Stand | Wer liest ihn |
|---|---|---|---|
| **Projektanweisungen** | **AGENTS.md**, von der **Agentic AI Foundation (AAIF, Linux Foundation)** betreut; AAIF gegründet im Dezember 2025 mit MCP, goose und AGENTS.md; seit Juni 2026 auch „agentgateway“ [offiziell: agents.md, linuxfoundation.org; agentgateway nur Hinweis] | Die nächstgelegene Datei gilt; verschachtelt erlaubt | Codex, Jules, Gemini CLI, Claude, Junie, Copilot, Cursor, VS Code, Zed, Aider, Warp … (20+) [offiziell]. **Claude Code nativ seit 2.1.277**, aber nur, wenn keine `CLAUDE.md` existiert; sonst über `@AGENTS.md`-Import [offiziell: code.claude.com/docs/en/memory] |
| **Skills** | **Agent Skills** (`SKILL.md`), von Anthropic entwickelt und als offener Standard freigegeben [offiziell: agentskills.io] | Ordner mit `SKILL.md` (name, description) plus scripts/references/assets; stufenweises Laden | über 40 Klienten, darunter Claude Code, Codex, Gemini CLI, OpenCode, Goose, OpenHands, Cursor, Copilot/VS Code, Junie, Kiro, Roo, Mistral Vibe, Deep Code (DeepSeek), Qwen Code [offiziell]. **Der am weitesten verbreitete gemeinsame Nenner** |
| **Werkzeuge / Konnektoren** | **MCP** (AAIF) | reif | praktisch alle oben |
| **Plugin-Pakete** | **Agent Plugins 1.0** (agent-plugins.org, vorher „Open Plugins“); Kernbetreuer laut GitHub: AWS, Anysphere, Microsoft, OpenAI, Vercel, Google (2026-08-06) [offiziell: github.blog 2026-08-12] | v1 standardisiert **nur Skills + MCP**. Hooks, Agenten, Befehle und Regeln gelten ausdrücklich als „too client-specific“ und stehen auf der Roadmap [offiziell] | VS Code, Copilot CLI/SDK/App; Kiro, Cursor laut AWS; Goose sagt, es folge der Hook-Spezifikation von „Open Plugins“ [offiziell]. **Anthropic in der Ankündigung nicht genannt** |
| **Hooks** | **kein Standard.** Faktisch setzt sich **der Claude-Code-Vertrag** durch: JSON über stdin (`tool_name`, `tool_input`), Exit 2 = Veto, stderr = Grund | – | Claude-förmig: Codex, Goose, OpenHands, Qwen Code, Gemini CLI (andere Eventnamen), Crush (nur PreToolUse). Andere Form: OpenCode (JS-Plugin), Cline (`cancel`). Codex setzt `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA` „for compatibility“ [offiziell: learn.chatgpt.com/docs/hooks] |
| **Subagent-Definitionen** | **kein Standard**; faktisch Markdown + YAML-Frontmatter (`name`, `description`, `tools`, `model`) | – | Claude (`.claude/agents`), Gemini (`.gemini/agents`), OpenCode (`.opencode/agents`), Goose (`.agents/agents`); Codex nutzt TOML. Die Feldnamen unterscheiden sich (`max_turns`/`maxTurns`, `permission` vs. `tools`) |
| **Sitzung live zwischen Oberfläche und Agent** | **ACP (Agent Client Protocol)**, von Zed gestartet, JetBrains arbeitet mit, Apache-Lizenz [offiziell: zed.dev/acp] | `session/new`, `session/load` (der Agent **muss** den ganzen Verlauf erneut an den Klienten schicken), `session/resume`, `session/close`; `session/request_permission` mit allow_once/reject_once/…, aber der Agent **„MAY“** fragen [offiziell] | Agenten: Claude Agent, Codex CLI, Copilot, Cursor, Devin, OpenHands, Cline, Gemini, OpenCode, 50+; Klienten: Zed, JetBrains, VS Code, Neovim, Emacs, Obsidian … [offiziell] |
| **Chat-/Verlaufsexport** | **kein Standard für Wiederaufnahme.** Für Aufzeichnung und Auswertung gibt es **ATIF** (Agent Trajectory Interchange Format, Harbor-RFC 0001; v1.7 kann Subagent-Verläufe einbetten) [offiziell: harborframework.com / GitHub-RFC] | ATIF ist ein Protokoll**format**, kein Weg, eine Sitzung in einem anderen Werkzeug fortzusetzen | NVIDIA NeMo Relay, Arize Phoenix, VT Code [Hinweis]. Herstellerwege: `opencode export/import`; **Codex `/import`** holt aus Claude Code höchstens 50 Chats der letzten 30 Tage [offiziell] |
| **Gedächtnis** | **kein ratifizierter Standard** (Stand Juli 2026). Vorschläge: Portable Agent Memory (arXiv), Engram-Spezifikation (PLUR, Apache-2.0), memorywire [Hinweis] | – | Mem0, Letta, Zep und Cognee haben je ein eigenes Schema [Hinweis] |

**Was das für den Wunsch heißt:** Anweisungen (AGENTS.md), Skills (SKILL.md) und Werkzeuge (MCP) sind
heute zwischen Anbietern übertragbar. Hooks, Subagenten, Freigaben, Chats und Gedächtnis sind es
**nicht**; jede App muss sie selbst tragen oder übersetzen. Genau dort sitzen die Garantien dieses Harness.
Der eigene `project_memory/`-Zustand ist der seltene Fall, in dem das Gedächtnis *schon* anbieterfrei
ist: YAML im Repo, vom Kernel geführt.

---

## 4. Die Außenwelt, Teil 3: Claude Code und Codex heute

- **Anweisungen:** Beide lesen `AGENTS.md`. Claude Code tut es nativ seit 2.1.277, aber *nicht*, wenn
  eine `CLAUDE.md` daneben liegt; dann nur über `@AGENTS.md`. Der Schalter `instructionFiles`
  (`claude-md-or-agents-md` | `claude-md-and-agents-md` | `claude-md` | `managed-only`) lässt sich nur in
  Benutzer- oder Managed-Einstellungen setzen [offiziell: memory-Doku; Repo: Claude-Radar Punkt 3].
- **Skills:** Beide lesen `SKILL.md`, aber aus **verschiedenen Ordnern** (`.claude/skills/` bzw.
  `.agents/skills/`). Heute kopiert der Generator [Repo].
- **Plugins:** Die Formate unterscheiden sich (`.claude-plugin/plugin.json` bzw. `.codex-plugin/plugin.json`).
  Codex setzt `CLAUDE_PLUGIN_ROOT` für Hook-Befehle, **ersetzt es aber nicht in `.mcp.json`-Argumenten**
  (openai/codex#19582) [offiziell: Hook-Doku; Issue-Status nicht geprüft].
- **Umzug:** Codex `/import` (CLI und ChatGPT-Desktop) übernimmt aus Claude Code Anweisungen, Einstellungen,
  Skills, Plugins, Projekt-Memories, MCP, **Hooks**, Slash-Befehle, **Subagenten** und Chats (CLI: 50 Stück,
  30 Tage). Man soll danach prüfen, ob sich Hooks und Werkzeugrechte anders verhalten [offiziell:
  learn.chatgpt.com/docs/import]. Einen offiziellen Rückweg Codex → Claude Code habe ich nicht gefunden.
- **Gegenseitiges Aufrufen:** `openai/codex-plugin-cc` (Codex aus Claude Code heraus) [offiziell: openai-Repo];
  `sendbird/cc-plugin-codex` (andersherum) [Hinweis].
- **Was eine App weiterhin übersetzen müsste**, selbst wenn beide Werkzeuge bleiben:
  1. die Hook-Registrierung (JSON-Settings bzw. TOML/hooks.json, Matcher-Namen `Edit|Write` bzw. `apply_patch`);
  2. die Subagent-Definition (Markdown bzw. TOML, `tools` hat bei Codex keine Entsprechung);
  3. die Sitzungsbindung des Leiters (`agent:` bzw. `config.toml` + Lead-Skill);
  4. das Freigabe-Werkzeug (`AskUserQuestion` hookbar bzw. `request_user_input`, das nur im Hauptagenten geht
     und nicht hookbar ist);
  5. den Spawn-Veto (bei Codex nicht möglich);
  6. das Vertrauensmodell (Codex-Trust je Hook-Hash; Claude ohne dieses Modell);
  7. den Chat-Verlauf (zwei eigene Speicherformate; kein gemeinsames Format zum Weitermachen);
  8. die Modellnamen und den Aufwand (`effort`), was `model_tiers.yaml` heute schon tut.

---

## 5. Drei Kandidaten-Architekturen für „eine App, jeder Anbieter“

### A. Native Artefakte je CLI erzeugen, die App steuert die CLIs von außen (heutiger Weg, erweitert)
- **Idee:** Die Kit-Quelle bleibt Claude-nativ. `gen_provider_artifacts.py` bekommt je weiteres Werkzeug ein
  Ziel (Gemini CLI, Qwen Code, Kimi CLI, vielleicht Goose). Die App ist nur **Oberfläche und Umschalter**:
  Sie spricht jede CLI über ACP oder den Codex-App-Server an und liest `project_memory/` direkt.
- **Behält:** Blockierende Gates, Werkzeugrechte und Isolation, wo die jeweilige CLI sie hat. Jede CLI wird
  einzeln gemessen, wie damals bei Codex; die Copilot-Entfernung ist der Präzedenzfall für ein ehrliches Nein.
- **Verliert:** Gleichheit. Jedes Werkzeug hat andere Lücken (Codex: kein Spawn-Veto, kein hookbares Freigabe-Tool).
  Chats bleiben je CLI getrennt; ein Wechsel mitten in der Arbeit heißt: der Zustand kommt mit
  (`project_memory/`), der Chatverlauf nicht. Anbieter ohne eigene CLI (DeepSeek, lokal) gehen nur über eine
  CLI mit Gateway (Claude Code + Anthropic-Endpunkt, was Anthropic nicht unterstützt, oder Codex mit
  Responses-API).
- **Aufwand:** je neuer CLI eine Messrunde plus Generator-Ziel, nach Codex-Erfahrung Wochen. Die App-Hülle kommt dazu.
- **Hauptrisiko:** Der **Stolperdraht der Quellformat-Entscheidung feuert** („ein dritter Anbieter braucht
  Artefakte“). Die Pflege wächst mit jeder CLI und jedem Upstream-Release. Fertige Übersetzer (rulesync)
  zeigen, dass gerade Hooks und Rechte am schlechtesten übersetzbar sind.

### B. Eine bestehende Laufzeit für viele Anbieter übernehmen oder forken und Gates plus Kernel darauf setzen
- **Idee:** Eine Laufzeit (am ehesten OpenCode, sonst Goose) wird der **eine** Motor für alle Anbieter. Die Gates
  laufen als Plugin/Hook dieser Laufzeit: bei OpenCode ein JS-Plugin, das die Python-Gates mit Claude-förmiger
  Nutzlast aufruft; bei Goose fast direkt als `PreToolUse` mit `on_failure: block`. Der Kernel bleibt unverändert.
- **Behält:** Ein einziger Hook-Vertrag für alle Anbieter, **gleiche Garantien unabhängig vom Modell**, gemischte
  Besetzung je Rolle (OpenCode: `model` je Agent), Werkzeugrechte je Agent, Chat-Export innerhalb der Laufzeit.
- **Verliert:** Die Claude-Code- und Codex-Oberflächen als Hauptweg; Abo-Zugang zu Claude (nur API-Key,
  Anthropic untersagt Abo-Plugins). Die heutige Messbasis gegen Claude/Codex müsste neu entstehen. Spawn-Veto,
  Stop-Wiederaufnahme und ein menschliches Freigabe-Werkzeug hängen an Upstream-Funktionen (#12472 offen,
  Subagent-Hook-Abdeckung unklar).
- **Aufwand:** Monate. Dazu kommen rund 35 Hooks je Kit, eine Brückenschicht, eine Messrunde gegen die neue
  Laufzeit, und entweder Fork-Pflege oder das Hinterherlaufen hinter Upstream (OpenCode veröffentlicht wöchentlich).
- **Hauptrisiko:** Die Durchsetzung **hängt an einem fremden Projekt**, das unsere Sicherheitsannahmen nicht
  teilt. Die Subagent-Lücke #5894 war genau die Klasse von Loch, die hier zählt. Ein Fork übernimmt dazu die
  ganze Pflege.

### C. Eigene Laufzeit auf einem Modell-Gateway
- **Idee:** Die App enthält einen eigenen Agentenkreislauf (Werkzeuge, Subagenten, Verdichtung, Sandbox) und
  spricht alle Modelle über ein Gateway an (LiteLLM, agentgateway, claude-code-router oder direkt die
  Anthropic- und OpenAI-kompatiblen Endpunkte der Anbieter). Gates und Kernel sind dann **Code im Kreislauf**
  statt Hooks von außen; Freigaben laufen durch die eigene Oberfläche (die Tür `kernel/sdk_approval.py` gibt es schon).
- **Behält und gewinnt:** die stärkste Durchsetzung (kein fremder Hook, der ausfallen oder übersprungen werden
  kann), echtes Spawn-Veto, ein Chatformat für alle Anbieter (also **Wechsel ohne Verlust**, z. B. als ATIF),
  Skills, AGENTS.md und MCP als Standards.
- **Verliert:** Alles, was Claude Code und Codex fertig mitbringen und laufend verbessern (Werkzeuge,
  Sandbox, Verdichtung, IDE-Anbindung). Abo-Zugänge fallen praktisch weg; es wird pro Token bezahlt
  (Anthropic: claude.ai-Login in Drittprodukten nur mit Genehmigung). Die Qualität der Werkzeugaufrufe
  schwankt je Modell; die Repo-Recherche vom 2026-08-15 nennt Feldberichte über falsch gemeldete Erfolge bei Kimi.
- **Aufwand:** der größte, eher Quartale als Monate für einen belastbaren Stand, dazu eine Messrunde je Modell.
- **Hauptrisiko:** Eine **zweite Plattform**, die jedes Gate neu messen muss (dasselbe Argument, das FR-0025
  hinter FR-0024 gestellt hat), und die Lieferkette des Gateways (LiteLLM-Angriff März 2026).

*(Querschnitt: Die **Oberfläche** der App ist in allen drei Fällen dieselbe Frage und kann für A über ACP bzw.
den Codex-App-Server laufen. FR-0020, das „dünne Installation“ und „ein Ordner“ will, wird in B und C einfacher,
weil die anbietereigenen Ordner wegfallen, in A dagegen schwerer. FR-0025 (Container) passt zu C am
natürlichsten.)*

---

## 6. Was der Nutzer zuerst beantworten muss

1. **Was heißt „nichts verlieren“ genau?** Reicht es, wenn *Zustand, Entscheidungen, Skills und Regeln*
   mitkommen (das kann A heute fast), oder muss der **Chatverlauf** selbst beim Wechsel weiterlaufen (das geht
   nur mit B innerhalb einer Laufzeit oder mit C)?
2. **Abo oder Bezahlung pro Token?** Sollen die Abos (Claude Max, ChatGPT, Kimi-/Qwen-Coding-Pläne) weiter
   genutzt werden? Die Abos binden meist an die Hersteller-Werkzeuge (spricht für A). Eine eigene Laufzeit
   läuft praktisch per API-Key.
3. **Wie viel Durchsetzung ist Pflicht?** Muss jeder Anbieter *dieselben* blockierenden Gates, das Spawn-Veto und
   die rein menschliche Freigabe haben, oder darf ein Anbieter mit benannter, schwächerer Stufe laufen (wie
   Codex heute)?
4. **Welche Anbieter wirklich, in welcher Reihenfolge?** Eine Messrunde pro Anbieter ist beschlossen
   (FR-0023-Triage). Welcher ist der dritte?
5. **Nur für den Nutzer oder später auch für andere?** Für Dritte ist Abo-Nutzung verboten, und die Regeln des
   Agent SDK (Branding, Login) greifen.
6. **Bereitschaft, Durchsetzung an ein fremdes Projekt zu hängen?** (B) Oder eine eigene Plattform zu pflegen?
   (C) Oder weiter mit Lücken je CLI zu leben? (A)
7. **Ist die Quellformat-Entscheidung vom 2026-07-14 wieder offen?** Jeder dritte Anbieter löst ihren
   Stolperdraht aus. Das ist eine Nutzerentscheidung und keine Umsetzerfrage.

---

## 7. Quellen (alle gesehen 2026-09-25)

**Repo:** `project_memory/inbox/active/FR-0023.yaml`, `FR-0020.yaml`, `FR-0025.yaml`; `HARNESS_LOG.md`
(Eintrag 2026-07-14, Z. ~313–345); `team-kits/gen_provider_artifacts.py` Z. 1–120; `team-kits/model_tiers.yaml`
Z. 1–60; `radar/2026-09-25-claude-by-claude.md` Punkt 3 und Quellformat-Scan; `radar/2026-09-25-codex-by-claude.md`
Punkte 2, 5, 6; `docs/research/2026-08-15-multi-provider-eigene-oberflaeche.md`; `README.md` Paritätsmatrix;
`team-kits/dev-team/hooks/_compat.py` (Kopf); `team-kits/kernel/sdk_approval.py` (Kopf).

**Offiziell:**
- OpenCode: https://opencode.ai/docs/plugins/ · https://opencode.ai/docs/agents/ · https://opencode.ai/docs/rules/ ·
  https://opencode.ai/docs/providers/ · https://github.com/sst/opencode · https://github.com/anomalyco/opencode/releases ·
  https://github.com/anomalyco/opencode/issues/12472 · https://github.com/sst/opencode/issues/5894 ·
  https://github.com/anomalyco/opencode/issues/21941 · https://opencode.ai/docs/cli/
- Goose: https://goose-docs.ai/docs/guides/context-engineering/hooks/ · https://goose-docs.ai/docs/guides/context-engineering/subagents/ ·
  https://github.com/aaif-goose/goose · https://github.com/aaif-goose/goose/releases · https://goose-docs.ai/blog/2026/04/07/goose-moves-to-aaif/
- Crush: https://github.com/charmbracelet/crush · https://github.com/charmbracelet/crush/blob/main/docs/hooks/README.md
- Cline: https://github.com/cline/cline
- OpenHands: https://docs.openhands.dev/overview/skills · https://docs.openhands.dev/sdk/guides/hooks ·
  https://docs.openhands.dev/sdk/guides/security · https://github.com/OpenHands/software-agent-sdk ·
  https://github.com/OpenHands/software-agent-sdk/issues/4157
- Gemini CLI: https://geminicli.com/docs/hooks/reference/ · https://geminicli.com/docs/core/subagents/ ·
  https://github.com/google-gemini/gemini-cli/issues/28046
- Qwen Code: https://qwenlm.github.io/qwen-code-docs/en/users/features/hooks/ · Kimi: https://www.kimi.com/code/docs/en/kimi-code-cli/customization/agents.html (nur Suchauszug)
- Zed: https://zed.dev/docs/ai/tool-permissions · https://zed.dev/docs/ai/llm-providers · https://zed.dev/acp
- ACP: https://agentclientprotocol.com/protocol/session-setup · https://agentclientprotocol.com/protocol/tool-calls
- Claude Code / Agent SDK: https://code.claude.com/docs/en/llm-gateway · https://code.claude.com/docs/en/agent-sdk/overview ·
  https://code.claude.com/docs/en/memory
- Codex: https://learn.chatgpt.com/docs/hooks · https://learn.chatgpt.com/docs/import · https://learn.chatgpt.com/docs/config-file/config-advanced ·
  https://learn.chatgpt.com/docs/app-server · https://github.com/openai/codex/discussions/7782 · https://github.com/openai/codex/issues/19582 ·
  https://github.com/openai/codex-plugin-cc
- OpenAI Agents SDK: https://openai.github.io/openai-agents-python/models/
- LiteLLM: https://docs.litellm.ai/docs/tutorials/claude_non_anthropic_models · https://docs.litellm.ai/blog/security-update-march-2026
- Standards: https://agents.md/ · https://agentskills.io/ · https://agent-plugins.org/specification ·
  https://github.blog/changelog/2026-08-12-agent-plugins-1-0-in-vs-code-copilot-cli-and-the-copilot-app/ ·
  https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation ·
  https://www.harborframework.com/docs/agents/trajectory-format · https://github.com/harbor-framework/harbor/blob/main/rfcs/0001-trajectory-format.md
- rulesync: https://github.com/dyoshikawa/rulesync

**Hinweise (nicht als Beleg lesen):**
- Kilo/Roo: https://kilo.ai/articles/roo-to-kilo-migration-guide · https://blog.kilo.ai/p/thank-you-roo · https://www.morphllm.com/comparisons/opencode-vs-kilo-code
- Continue EOL: https://github.com/dyoshikawa/rulesync/issues/3078
- Goose-Markdown-Agenten: https://github.com/dyoshikawa/rulesync/issues/2404
- Cline-Hook-Form: https://cline.bot/blog/cline-v3-36-hooks
- OpenCode-Subagent-Hook-Nachmessung: https://github.com/nightgauge/nightgauge/issues/1805 · Brücke: https://github.com/magarcia/opencode-claude-hooks
- Codex `wire_api = "chat"` entfernt (Datum): https://www.morphllm.com/codex-provider-configuration
- AAIF agentgateway: https://aaif.io/ (Suchauszug)
- Gedächtnis-Standards: https://plur.ai/blog/open-standard-ai-agent-memory/ · https://arxiv.org/html/2605.11032v1 · https://arxiv.org/pdf/2606.01138
- Quelltextstudie: https://arxiv.org/abs/2609.00006
- Agnostic-ai: https://github.com/Chemaclass/agnostic-ai/issues/889
