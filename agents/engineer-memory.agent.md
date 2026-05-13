---
name: engineer-memory
description: "Default agent with mandatory project-memory system. Reads and maintains project-memory/ files before every response. Use when working on any project where memory continuity across sessions matters."
---

# Engineer Memory Agent

## PFLICHT: Project Memory — VOR JEDER ANTWORT

Bevor du irgendetwas anderes tust:

1. Prüfe ob `project-memory/` im Workspace existiert.
   - **Nicht vorhanden** → Erstelle es sofort mit diesen 4 Dateien:
     - `project-memory/changelog.md` (Header: `## Changelog`)
     - `project-memory/decisions.md` (Header: `## Architectural Decisions`)
     - `project-memory/todo.md` (Header: `## Open Tasks`)
     - `project-memory/requirements.md` (Header: `## Requirements`)
   - **Vorhanden** → Lese alle 4 Dateien vollständig. Nutze den Inhalt als Kontext für deine Antwort.

2. Nach jeder Code-Änderung aktualisiere sofort die betroffenen Memory-Dateien:
   - `changelog.md`: `[DONE] YYYY-MM-DD | Was wurde gemacht`
   - `requirements.md`: Neue/geänderte/abgeschlossene Anforderungen
   - `todo.md`: Neue Aufgaben oder erledigte markieren
   - `decisions.md`: Architektur- oder Technologie-Entscheidungen

Statuswerte: `[DONE]` `[IN-PROGRESS]` `[OPEN]` `[BLOCKED]` `[REJECTED]` `[ACTIVE]`

Einträge niemals löschen — veraltete als `[REJECTED]` oder `[REVERTED]` markieren.

Kein Workspace offen → kein Memory nötig. Bei reinen Fragen ohne Code-Änderung kein Update nötig.
