---
name: interview
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

# Grill Me

Befrage mich gnadenlos zu jedem Aspekt dieses Plans bis wir ein gemeinsames Verständnis erreichen.

## Wie du vorgehst

1. Analysiere den Plan / die Anforderung zuerst still
2. Identifiziere alle offenen Entscheidungen und Abhängigkeiten (Decision Tree)
3. Stelle jede Frage EINZELN als Poll — niemals mehrere auf einmal

## Fragen-Format (PFLICHT)

Jede Frage MUSS als `askQuestions`-Poll gestellt werden:
- **Copilot:** Rufe `#tool:vscode_askQuestions` auf
- **Claude Code:** Rufe das tool `askQuestions` auf
- Verwende `options` mit konkreten Antwortmöglichkeiten
- Markiere deine Empfehlung mit `recommended: true`
- Setze `allowFreeformInput: true` für Ergänzungen
- Nutze `multiSelect: true` wenn mehrere Optionen kombinierbar sind

## Gesprächsführung

- Starte mit den wichtigsten Abhängigkeiten (Was bestimmt alles andere?)
- Folge dem Decision Tree: Antwort A öffnet Branch A, Antwort B öffnet Branch B
- Erkläre kurz WARUM du diese Frage stellst (ein Satz)
- Gib deine Empfehlung und begründe sie kurz
- Wenn eine Frage durch Codebase-Analyse beantwortet werden kann → erst analysieren, dann Frage stellen oder überspringen
- Stelle niemals eine Frage die schon beantwortet wurde

## Abschluss

Wenn alle Entscheidungszweige geklärt sind:
- Fasse die Entscheidungen zusammen
- Zeige den vollständigen Plan als Requirement-Liste (REQ-XXXX Format)
- Frage ob der Plan so umgesetzt werden soll