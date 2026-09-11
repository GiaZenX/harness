# FR-0089 — Das Experiment: dieselbe Frontend-Aufgabe, zwei Wege (PR-0011 AC-6)

Beide Arme bekommen **diesen Text wörtlich** als Aufgabe. Nichts wird ergänzt, nichts erklärt; was
hier nicht steht, entscheidet der Bauer selbst — genau das ist Teil der Messung.

## Die Aufgabe (an den Bauer, wörtlich)

Baue eine **Rechnungsübersicht** als eigenständige Web-Seite, die ohne Server läuft (eine Datei
`index.html` plus, wenn du willst, `styles.css` und `app.js` daneben; kein Build-Schritt, kein
Framework-Download nötig, offline im Browser zu öffnen). Sie liest die beigelegte Datei
`invoices.json` (Format unten) und zeigt:

1. eine **Liste aller Rechnungen** mit Nummer, Kunde, Datum, Betrag brutto, Status
   (`offen`, `bezahlt`, `überfällig`);
2. **drei Kennzahlen** oben: Summe offen, Summe überfällig, Summe bezahlt im laufenden Monat;
3. einen **Filter** nach Status und eine **Suche** nach Kunde oder Nummer;
4. beim Klick auf eine Zeile eine **Detailansicht** (Positionen, Netto, Steuer, Brutto, Fälligkeit);
5. eine Darstellung, die auf einem **Handy** (360 px breit) und auf einem Desktop gut lesbar ist.

Überfällig ist eine offene Rechnung, deren Fälligkeit vor dem heutigen Tag liegt. Beträge in Euro
mit zwei Nachkommastellen, Datum als `TT.MM.JJJJ`. Die Seite ist auf **Deutsch**. Lege außerdem
eine Datei `NOTES.md` an: was du entschieden hast, was du weggelassen hast, wie man die Seite öffnet.

`invoices.json` (Beispiel; die echte Datei liegt daneben und hat 24 Einträge):

```json
[
  {"number": "RE-2026-0101", "customer": "Müller GmbH", "issued": "2026-08-02", "due": "2026-08-16",
   "status": "offen", "lines": [{"text": "Beratung 8 h", "net": 960.00, "vat_rate": 19}]},
  {"number": "RE-2026-0102", "customer": "Schulz & Partner", "issued": "2026-08-05", "due": "2026-08-19",
   "status": "bezahlt", "paid_on": "2026-08-15",
   "lines": [{"text": "Wartung Q3", "net": 450.00, "vat_rate": 19}, {"text": "Fahrt", "net": 60.00, "vat_rate": 19}]}
]
```

Fertig ist die Arbeit, wenn die fünf Punkte oben im Browser sichtbar funktionieren und `NOTES.md`
sagt, was du getan hast.

## Was gemessen wird (beide Arme gleich)

| Größe | Quelle |
|---|---|
| Tokens (Eingabe/Ausgabe/Cache) | die JSON-Ausgabe der Sitzung (`--output-format json`, Feld `usage` / `modelUsage`) |
| Wanduhr | `duration_ms` der Sitzung; bei mehreren Sitzungen die Summe plus die Wartezeiten dazwischen, gelesen von der Uhr |
| Runden | Arm A: 1 (eine Sitzung) — Arm B: Sitzungen des PM + Bauer-Spawns + Prüferrunden, aus `project_memory/.audit/hook_events.jsonl` und den Items |
| Qualität | **das Urteil des Nutzers**, der die Seite öffnet — nicht das eines Agenten; Vorschlag: Note 1–5 je Punkt 1–5 der Aufgabe plus ein Satz |

## Was fair bleibt

- Beide Arme starten in einem leeren Ordner, der nur `invoices.json` und diesen Text enthält.
- Beide Arme laufen auf derselben Provider-Version (`claude --version` wird notiert).
- Arm A bekommt keinen Hinweis auf Prüfung oder Selbstkontrolle; Arm B keinen Hinweis auf Kürze.
- Kein Arm sieht das Ergebnis des anderen.
