# FR-0089 — Kosten / Nutzen / Qualität / Effizienz: Multi-Agenten-Harness gegen EINEN Fable (Zusammenfassung des Leads, 2026-09-06)

Grundlage: `research-A-evidence.md` (Belege aus Papieren und Herstellertexten), `research-B-practice.md`
(Praxisberichte 2025/2026), `research-C-our-numbers-and-routines.md` (unsere eigenen Zahlen aus den
Generationen 3–5 und die Routinen-Frage). Jede Zahl unten steht dort mit Quelle und Datum.

## 1. Was die Welt gemessen hat

| Befund | Zahl / Quelle | Bedeutung für uns |
|---|---|---|
| Multi-Agenten-Systeme kosten strukturell mehr | ~15× Tokens gegenüber einem Chat, ~4× gegenüber einem einfachen Agenten (Anthropic, „How we built our multi-agent research system", 2025); 7–15× in Praxisberichten 2026 | passt zu unseren Generationen: ~4–5,6 Mio. Tokens je Rolle und Generation |
| Der Gewinn liegt in **Breite**, nicht in Tiefe | Anthropic: 90,2 % besser als ein einzelner Opus bei **Recherche**; aber „coding has fewer truly parallelizable tasks than research", geteilter Kontext „not a good fit" | Bauen ist meist sequenziell und kontextgebunden → Delegation verliert |
| Die meisten Fehler sind **Koordination**, nicht Modellschwäche | MAST-Studie: 41–87 % Fehlerrate in sieben Frameworks, 14 Fehlermodi, einfache Fixes bringen nur +9–16 % | genau unsere Befundklassen: Nähte, Neuschnitte, „Kommentar behauptet A, Code tut B" |
| Frontend ist der schwächste Fall für Aufteilung | Cognition „Don't build multi-agents" (2025): zwei parallele Arbeiter bauen unpassende Teile (Flappy-Bird-Beispiel); 2026 präzisiert: mehrere Agenten nur, wenn **einer schreibt** | deine Beobachtung, fast wörtlich; unsere Regel „es schreibt immer nur einer" ist der belegte Kern |
| **Unabhängige Prüfung** ist der klar belegte Gewinn | ein Prüfagent ohne Autorkontext findet ~2 Fehler je Pull Request, über die Hälfte schwer — **weil** er den Kontext nicht teilt | die einzige Rolle, die sich in allen drei Generationen bezahlt gemacht hat |
| Mehr Denkaufwand bringt logarithmisch wenig | dokumentiert: doppelte Denk-Tokens ≠ doppelte Qualität; OpenAI empfiehlt `medium` als Standard, `high/xhigh` nur für wirklich harte Aufgaben; ein offener GitHub-Fall: ~20 % Tokens in 2 h weg ohne Fortschritt | dein Astra-Erlebnis ist ein bekannter Effekt, kein Zufall; DEC-0076/0077 (Standard `high`, `xhigh` nur für große Ziele) ist eher noch zu großzügig |
| „Kleinstes Team zuerst" ist Konsens | Anthropic „Building effective agents": Komplexität nur, wenn sie **nachweislich** hilft — „this might mean not building agentic systems at all" | die Kits müssen mit dem Solo-Preset anfangen, nicht mit dem Team |
| **Nicht gemessen** in der Literatur | keine kontrollierte Studie zu Frontend-/Design-Kohärenz; nichts zu genau unserer Form (Lead + Arbeiter + separater Prüfer) | das beantwortet nur unser eigenes Experiment |

## 2. Was unsere eigenen Zahlen sagen (Bericht C)

- Generation 3: ~4,6 Mio. Umsetzer / ~2,4 Mio. Prüfer, ~53 h kritischer Pfad (der teuerste Einzelposten: ~13 h aus einer verlorenen Fertigmeldung — ein Orchestratorfehler).
- Generation 4: ~4 Mio. / ~5,6 Mio. — der Prüferanteil stieg von ~34 % auf ~58 %, obwohl DEC-0070 ihn senken wollte; die Befundklasse „ein Leser liest weniger, als sein Kommentar behauptet" über 80-mal in 16 Prüfberichten.
- Generation 5 (unfertig): der einzige saubere Wert bisher ~105 k Tokens je abgenommenem Kriterium (TSK-0132), dort überwogen echte Defekte (9) die Prosa-Befunde (5) — der Prüfer fand Dinge, die kein Autor sah.
- Die drei teuersten Einzelbefunde: zwei aus den Host-Abstürzen und dem ungelesenen Suiten-Merge der Generation 4, einer aus dem Orchestratorfehler der Generation 3 — **alle drei Koordination, keiner ein Produktdefekt.**
- Was die Zahlen **nicht** sagen können: Es gibt kein kontrolliertes Experiment „ein Fable allein gegen die Pipeline" in diesem Repo; die Generationen sind keine saubere Reihe (Stufen und Schnittregeln änderten sich).

## 3. Meine Meinung (Lead)

1. **Du hast recht — für das, was du bewertest.** Frontend, Design, ein kleines Produkt: ein Fable mit dem ganzen Kontext ist schneller, billiger und kohärenter. Jede Delegation verdünnt die Absicht; ein Sonnet mit „Spielraum" liefert Runden statt Ideen. Die Literatur und unsere Protokolle sagen dasselbe.
2. **Was bleiben muss:** der **unabhängige Prüfer** — nicht als Runde um Runde, sondern als letztes Tor mit klarem Auftrag. Er war in allen drei Generationen die einzige Rolle, deren Befunde der Autor nicht sehen konnte (435 rote Tests im Merge, die umgehbare Bremse, meine eigene falsch formulierte Entscheidung).
3. **Was weg oder klein muss:** Parallelität als Standard. Ströme lohnen nur, wenn die Arbeit **wirklich unabhängig** ist (unsere vier Gen-4-Ziele waren es — und trotzdem kamen 435 rote Tests aus den Nähten). Für ein Produkt: **ein** Schreiber.
4. **Zu groß geworden?** Für das Harness selbst: ja, an Stellen — ein großer Teil der Arbeit fließt in unsere eigene Verwaltung. Das ist Investition ins Werkzeug und gehört nicht in ein Produktprojekt. Die Kits müssen **Solo-Fable als Standard** haben und erst auf gemessenen Bedarf wachsen (der Projektmanager fragt dich, wenn eine Rolle fehlt — DEC-0048 hat das schon vorgesehen; die Voreinstellung muss klein sein).
5. **Aufwand:** `medium/high` als Standard, `xhigh` nur auf ausdrückliche Anweisung für einen benannten Schritt — nie als Dauerbetrieb.

## 4. Die Entscheidungsregel, die ich vorschlage

| Aufgabe | Form |
|---|---|
| Frontend, Design, UX, kleines Produkt, alles Kreativ-Zusammenhängende | **ein Fable** end-to-end, Prüfer nur als letztes Tor (eine Runde, klarer Auftrag) |
| Kernel-/Vertragsarbeit mit Testpflicht (wie hier) | Umsetzer + Prüfer (die Zwei-Rollen-Schleife), **kein** dritter Strom, es sei denn die Dateimengen sind gemessen disjunkt |
| Breite Recherche, viele unabhängige Quellen | Orchestrator + parallele Sonnet-Arbeiter (der einzige belegte Multi-Agenten-Gewinn) |
| Arbeiter-Aufträge | enge, testbare Scheiben mit Abnahmekriterium; **nie** „Spielraum" |

## 5. Das Experiment (der nächste Schritt, statt Gefühl gegen Gefühl)

Dieselbe Frontend-Aufgabe, dieselbe Vorgabe, zwei Wege: (a) ein Fable allein, (b) das Kit mit Team. Gemessen: Tokens, Wanduhr, Runden, und **dein** Qualitätsurteil (du kannst Frontend bewerten). Ein Nachmittag, ein klares Ergebnis — und danach setzen wir das Kit-Preset danach. Vorschlag: als erstes Stück der Rechnungs-App-Oberfläche (DEC-0075), damit das Experiment gleich etwas Nützliches baut.
