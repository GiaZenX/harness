---
applyTo: "**"
---
# PFLICHT: Project Memory System

> Diese Anweisungen sind VERBINDLICH und müssen bei JEDER Anfrage ausgeführt werden – ohne Ausnahme.

## SCHRITT 1 – VOR jeder Antwort (MANDATORY)

Ist ein Workspace offen?
- **JA** → Prüfe ob `/project-memory/` existiert.
  - Existiert NICHT → Erstelle es SOFORT mit diesen 4 Dateien:
    - `project-memory/changelog.md` (leer, mit Header `## Changelog`)
    - `project-memory/decisions.md` (leer, mit Header `## Architectural Decisions`)
    - `project-memory/todo.md` (leer, mit Header `## Open Tasks`)
    - `project-memory/requirements.md` (leer, mit Header `## Requirements`)
  - Existiert → Lese alle 4 Dateien. Nutze den Inhalt als Kontext.
- **NEIN** → Weiter ohne Memory.

## SCHRITT 2 – NACH Code-Änderungen (MANDATORY)

Wurde Code erstellt, geändert oder gelöscht? → Aktualisiere **sofort**:
- `changelog.md`: `[DONE] YYYY-MM-DD | Was wurde gemacht`
- `requirements.md`: Neue/geänderte/abgeschlossene Anforderungen
- `todo.md`: Neue Aufgaben oder erledigte markieren
- `decisions.md`: Architektur- oder Technologie-Entscheidungen

Bei reinen Fragen/Erklärungen ohne Code-Änderung: kein Update nötig.

## Statuswerte

| Tag | Bedeutung |
|-----|-----------|
| `[DONE]` | Abgeschlossen |
| `[IN-PROGRESS]` | Aktiv in Arbeit |
| `[OPEN]` | Zu erledigen |
| `[BLOCKED]` | Wartet auf Abhängigkeit |
| `[REJECTED]` | Bewusst verworfen – NICHT neu vorschlagen |
| `[ACTIVE]` | Gültige Entscheidung – einhalten |

## Regeln

- NIEMALS Memory ignorieren
- NIEMALS Einträge löschen (als `[REJECTED]` oder `[REVERTED]` markieren)
- Alle Einträge kurz und maschinenlesbar halten
- Datum immer im Format `YYYY-MM-DD`
