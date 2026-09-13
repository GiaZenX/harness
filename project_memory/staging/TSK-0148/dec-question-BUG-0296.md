# Frage an den Nutzer (DEC-first, DEC-0102 (3)) — BUG-0296 / H212

**Das ist eine Entscheidungsvorlage, keine Änderung.** An der Leseregel selbst wurde nichts
angefasst: kein einziges Wort wurde ergänzt (genau das verlangt DEC-0102 (3), bevor die Klasse
entschieden ist). Die Datei, um die es geht, gehört ohnehin einem anderen Strom dieser Runde.

## Worum es geht, in Alltagssprache

Jeder Auftrag an einen Bau-Agenten läuft auf einer **Modellstufe** — grob: teures, starkes Modell
oder billigeres, schwächeres. Die Projektleitung darf für einen kleinen Auftrag ausdrücklich die
**billigere** Stufe verlangen. Erlaubt wird das nur, wenn der Auftrag eine **Abnahme mit einem Test**
hat: „nach dieser Änderung wird Test X grün". Der Gedanke dahinter: Wo es einen Test gibt, sagt der
Test, ob die Arbeit gut ist — dafür reicht ein schwächeres Modell. Wo nur Prosa steht („soll sauber
und gut lesbar sein"), muss ein starkes Modell ran.

Die Prüfung, ob eine Abnahme „einen Test nennt", liest dafür **deutschen und englischen Fließtext**.
Und dort sitzt das Problem: Ein Satz, der einen Test **verneint**, muss als „kein Test" erkannt
werden. Sonst kauft genau der Satz, der sagt *„hier wird nichts getestet"*, die billige Stufe.

Der aktuelle Fall: **„Das Ergebnis wird ohne den Nachweis der Tests rot."** Der Satz sagt: ohne
Testnachweis. Die Prüfung liest ihn als Zusage eines Tests und gewährt die billige Stufe. Ursache
ist ein Detail der deutschen Grammatik: Das Wörtchen **„der"** kann Genitiv sein („der Tests" =
*von den Tests*) oder Nominativ/Dativ — und nichts in dieser Prüfung kann entscheiden, welches von
beiden gemeint ist. Sie bricht deshalb an dieser Stelle ab und übersieht das, was danach steht.

## Was gemessen ist — die Geschichte dieser einen Prüfregel

Die Regel ist in **vier aufeinanderfolgenden Prüfrunden viermal** durchgefallen, jedes Mal an einem
anderen Wort und jedes Mal in die **gefährliche** Richtung (billige Stufe gewährt statt verweigert):

| Runde | was fehlte | Beispielsatz, der durchkam |
|---|---|---|
| 1 (H194 / BUG-0278) | die deutschen Zwillinge von `never`/`none`: nie, niemals, nirgends | „Ein Test wird niemals rot" |
| 2 | die Klammer-Verneinung `neither … nor` / `weder … noch` als Konstruktion | „Neither of the tests goes red …" |
| 3 | die Fortsetzung einer Wortgruppe durch ein nachgestelltes Substantiv (deutscher Genitiv, englisches `of`) | „ohne die Hilfe eines Tests" |
| 4 (H212 / BUG-0296, heute offen) | der **mehrdeutige** Genitivartikel `der` / `einer`, den keine Wortliste auflösen kann | „ohne den Nachweis **der** Tests" |

Zwei Dinge daran sind das eigentliche Signal:

1. **Gefunden hat diese vier Lücken jedes Mal ein Prüfer von Hand, nie die Regel selbst.** Die
   eingebaute Selbstkontrolle kann prüfen, ob jedes *gelistete* Wort wirklich gebraucht wird — sie
   kann **nicht** sehen, dass ein Wort **fehlt**. Ein fehlendes Wort ist unsichtbar, bis jemand den
   Satz hinschreibt.
2. **Der vierte Fall ist nicht durch ein weiteres Wort zu schließen.** Die ersten drei waren
   Lückenfüller. Hier ist die Form selbst mehrdeutig: Dasselbe Wort „der" ist in dem einen Satz
   Genitiv und im nächsten nicht. Ein Wortlisten-Leser kann das nicht entscheiden, egal wie lang
   die Liste wird.

**Was der Fehler heute kostet, ehrlich begrenzt:** Ein falsch gelesener Satz führt dazu, dass ein
Auftrag auf einem **billigeren Modell** läuft. Er schreibt nichts frei, er hebt keine Schutzregel
auf, er gibt nichts frei. Das Ergebnis ist schlechtere Arbeit an einer Stelle, an der die Abnahme
schwach ist — nicht ein Schaden am Bestand. Deshalb ist der Eintrag als „niedrig" eingestuft und
deshalb ist das hier eine **Entscheidungs-** und keine Notfallfrage.

## Die Frage

> **Soll die Prüfung weiterhin natürliche Sprache beurteilen — oder soll sie die Abnahme in einer
> festen Form verlangen und alles andere unbeurteilt lassen?**

Die Frage ist absichtlich größer als der eine Satz: Sie entscheidet die **Klasse**. Nach DEC-0070 (2)
und DEC-0102 (3) wird sie beantwortet, **bevor** wieder ein Wort ergänzt wird.

## Die drei möglichen Antworten und was jede kostet

**A — Weiterlesen wie bisher (Wort für Wort nachbessern).**
*Preis:* Die Sache bleibt bequem — die Projektleitung schreibt die Abnahme so, wie sie ohnehin
schreibt, und niemand muss eine Schreibvorschrift lernen. Dafür ist zu erwarten, dass **jede weitere
Prüfrunde eine weitere Lücke findet** (bisher: vier von vier). Der heutige Fall lässt sich damit
gar nicht schließen, weil „der" mehrdeutig ist; er bliebe dauerhaft offen und würde als Loch
weitergetragen. Kosten fallen in Prüferzeit an, nicht in Schaden.

**B — Feste Form verlangen (die Prosa-Lesung abschalten).**
Die billigere Stufe wird nur noch gewährt, wenn die Abnahme **nachprüfbar** eine Testdatei oder
einen Testnamen nennt — das ist der **zweite, bereits gebaute Weg** derselben Prüfung: Sie schaut
heute schon zuerst nach, ob die erwarteten Ergebnisse eine Testdatei nennen (`test_x.py`, eine Datei
im Ordner `tests/`). Nur wenn das fehlt, fängt sie an, Sätze zu lesen. Dieser zweite Teil würde
wegfallen.
*Preis:* Die Klasse der Sprachlücken **hört auf zu existieren** — kein Wort mehr, das fehlen kann.
Dafür wird die Projektleitung **öfter auf die teure Stufe verwiesen**, nämlich immer dann, wenn eine
Abnahme zwar einen Test meint, ihn aber nur beschreibt statt ihn zu benennen. Das kostet echtes
Geld pro Auftrag. Und: bestehende Aufträge in laufenden Projekten, deren Abnahme nur beschreibend
formuliert ist, verlieren die billige Stufe ab dem Tag der Umstellung. **Wie viele das sind, kann
ich hier nicht messen** — in diesem Repository wird nicht dispatcht; die Zahl steht in den
installierten Projekten, nicht hier. Das ist eine offene Zahl, keine geschätzte.

**C — Weiterlesen, aber bei Zweifel in die teure Richtung.**
Die Sätze werden weiter gelesen; sobald die Lesung an eine Stelle kommt, die sie **nicht entscheiden
kann** (genau das mehrdeutige „der"/„einer"), wird die billige Stufe **verweigert** statt gewährt.
*Preis:* Die Gefahrenrichtung dreht sich dort um, wo der Leser seine eigene Unsicherheit **kennt**:
Ein Zweifelsfall kostet dann Geld (ein unnötig teurer Lauf) statt Qualität. Aufwand: klein, eine
Stelle im Leser.

**Wie weit C wirklich trägt — nachgemessen, weil hier zuerst eine falsche Zahl stand.** In einer
früheren Fassung dieser Vorlage stand, C hätte „alle vier bisherigen Fälle rückwirkend entschärft".
Das ist **falsch**, und die Prüfung dieser Runde hat es gemessen. C kann nur dort greifen, wo die
Lesung überhaupt in die zweifelhafte Stelle läuft — das ist das Satzglied hinter einer
**Präpositions**-Verneinung („ohne", „without"). Gemessen an den vier Sätzen der vier Runden
(2026-09-13 00:17, gegen den laufenden Leser):

| Runde | Satz trägt eine Präpositions-Verneinung? | greift C? |
|---|---|---|
| 1 (nie/niemals/nirgends) | **nein** | nein |
| 2 (weder … noch) | **nein** | nein |
| 3 (Genitiv-Nachstellung) | ja („ohne") | ja |
| 4 (mehrdeutiger Artikel, heute) | ja („ohne") | ja |

Der Grund ist sauber benennbar: Ein **fehlendes** Wort in der Verneinungsliste erzeugt kein
„unentscheidbar", sondern ein selbstsicheres „hier wird gar nicht verneint" — und wo der Leser sicher
ist, hat C nichts zu verweigern. **C entschärft also die Runden 3 und 4, nicht 1 und 2.**

**Was an C ungemessen ist, ausdrücklich:** die Kosten in der Gegenrichtung. Die Rot-zuerst-Formel
dieses Hauses — „Ohne den Fix wird ein Test rot" — läuft durch **genau denselben** Leser (auch sie
trägt „Ohne"; gemessen, und heute wird sie korrekt als Zusage gelesen). Ob eine so formulierte,
völlig korrekte Abnahme unter C zur Verweigerung würde, hängt an den Artikeln im Satz und **wurde
nicht gemessen**. Solange das offen ist, ist der Preis von C eine unbekannte Zahl unnötig teurer
Läufe.

## Keine Empfehlung — und warum das hier die ehrliche Antwort ist

Ich gebe **keine** Empfehlung. Die Vorfassung dieser Vorlage empfahl C mit einer Begründung, die
sich in der Prüfung als falsch gemessen herausstellte; eine zweite Empfehlung, die auf einer
ungemessenen Zahl steht, wäre derselbe Fehler noch einmal. Was fehlt, um eine begründete Empfehlung
zu geben, ist genau zwei Messungen groß:

1. **Für C:** die Fehlalarm-Rate — wie viele korrekt formulierte Abnahmen (Rot-zuerst-Formel und
   ihre Varianten) unter C die teure Stufe bekämen.
2. **Für B:** wie viele bestehende Abnahmesätze in den laufenden Projekten nur beschreibend
   formuliert sind und die billige Stufe am Umstellungstag verlören (in diesem Repository nicht
   messbar — hier wird nicht dispatcht).

Was ohne weitere Messung feststeht: **A** kann den heutigen Fall nicht schließen (die Form ist
mehrdeutig, keine Wortliste entscheidet sie). **B** beendet die Klasse vollständig und ist die
teuerste Umstellung. **C** halbiert sie — sie wirkt gegen die Lückenart der Runden 3 und 4 und
gar nicht gegen die der Runden 1 und 2.

## Was der Nutzer entscheiden muss

Nur **A, B oder C**. Alles Weitere (welche Datei, welcher Test, welche Runde) leitet sich daraus ab
und ist nicht seine Frage.
