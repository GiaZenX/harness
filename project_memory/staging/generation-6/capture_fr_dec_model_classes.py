"""User 2026-09-28 ~22:xx: model classes by task properties -- research wish (FR) + his tier decisions (DEC).
Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture"]
env = dict(os.environ, PYTHONPATH="team-kits")

FR = {
    "title": "Recherche: Modellklasse nach Aufgaben-Eigenschaften (vier Ja/Nein-Fragen) statt nach Modellnamen -- "
             "wie machen es andere, welche Eigenschaften trennen die Klassen belastbar, wie misst man eine Klasse",
    "request_text": "User 2026-09-28: 'Nur jetzt bleibt noch die Frage offen fuer was benutzen wir Opus, fuer was "
                    "Sonnet, fuer was Fable und fuer was Haiku. Oder eben andere Modelle anderer Anbieter? ... Aber "
                    "wie definieren wir das? Da es sehr viel Interpretationsspielraum hat und ja immer neuere Modelle "
                    "rauskommen.' On the lead's proposal (four yes/no questions: steers other orders -> Giga; failed "
                    "a verification -> one class up; test decides and no design choice -> Kilo; else Mega; a measured "
                    "class-to-model table per provider): 'Ja kannst es ja nochmal recherchieren.'",
    "source": "user messages 2026-09-28; create_wave1_streams.py stream C (MODEL CLASS BY TASK PROPERTIES); FR-0097",
}
DEC = {
    "title": "Stufen: Opus und Fable auf ZWEI Stufen -- Giga = Opus xhigh, Tera = Fable, selten und nur mit gemessenem "
             "Vorteil (teuer); Haiku bleibt fuer Code gesperrt, Haiku 5.5 wird fuer eine Nicht-Code-Routineklasse "
             "(Recherche-Zusammenfassung, Berichte) gemessen, sobald es erscheint",
    "context": "User 2026-09-28: 'wuerde Opus und Fable auf zwei verschiedene Stufen setzen. Und Fable ist sehr teuer "
               "deshalb eher vermeiden und nicht haeufig nutzen. Nur wenn es wirklich einen Vorteil bietet. Haiku 5.5 "
               "wird hoffe ich mal richtig gut fuer Recherche oder fuer Routine-Aufgaben, Zusammenfassung von "
               "Berichten oder so. Das momentane ist so schlecht ohne Reasoning und halluziniert mega.'",
    "decision": "(1) Giga = Opus (xhigh) -- the planning class (DEC-0127). (2) Tera = Fable: used only for a named step "
                "where a MEASURED advantage over Giga exists (benchmark of that class), never as a default; the PM "
                "states the measured reason on the order. (3) Haiku: never for code (unchanged). A read-only "
                "routine class below Kilo (summaries of reports, research digests, routine lookups) is opened for "
                "Haiku 5.5 only after it passes a measurement on such tasks with a hallucination check against the "
                "sources; the current Haiku stays excluded. (4) The class-to-model table is data maintained by "
                "measurement (DEC-0126).",
    "consequences": "Stream C builds Tera as an explicit, rarely used class with a measured-reason requirement; the "
                    "measurement harness gets a hallucination check for the routine class.",
    "work": ["PR-0012"],
    "source": "user message 2026-09-28; DEC-0114; DEC-0118; DEC-0126; DEC-0127",
}
out = []
for kind, body in (("FR", FR), ("DEC", DEC)):
    r = subprocess.run(BASE + [kind], cwd=ROOT, env=env, input=json.dumps(body), capture_output=True, text=True,
                       encoding="utf-8")
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr[-800:])
    if r.returncode:
        sys.exit(r.returncode)
