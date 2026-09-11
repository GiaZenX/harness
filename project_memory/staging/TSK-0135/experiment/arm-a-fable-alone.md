# Arm A — ein Fable allein (der Lead fährt ihn, DEC-0093 (4): das Urteil wartet auf den Nutzer)

Ein leerer Ordner **außerhalb** dieses Repos (Vorschlag:
`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0135/experiment/arm-a/`), darin nur `brief.md`
(Abschnitt „Die Aufgabe" aus `brief.md`, wörtlich) und `invoices.json` (die 24 Einträge aus
`invoices.json` neben dieser Datei). Kein `.claude/`, kein Kit, keine Hooks.

Eine Sitzung, headless, ohne weitere Anweisung als die Aufgabe:

    claude -p "Lies brief.md und invoices.json in diesem Ordner und erledige die Aufgabe aus brief.md vollständig." \
      --model fable --allowedTools "Read,Write,Edit,Bash(python *)" --max-turns 60 --output-format json

Notieren: `claude --version`, die Uhr vor und nach dem Lauf, das JSON-Ergebnis vollständig (als
`arm-a.result.json` neben den Dateien), und die entstandenen Dateien (`index.html`, `NOTES.md`, …)
unverändert. Danach die Seite dem Nutzer öffnen — sein Urteil ist die Qualitätszahl.

Was der Lead NICHT tut: nachbessern, eine zweite Sitzung starten, dem Modell etwas erklären. Ein
Lauf, der abbricht, ist ein Ergebnis („Arm A brach nach n Turns ab").
