"""Triage of the 22 kit-gap entries synaipse-unified logged 2026-09-25/26 (tools/harvest_kit_gaps.py; the raw text is
staging/generation-6/harvest-synaipse-2026-09-26.txt, entry ids below) plus the lead's measurement of synaipse's
order cutting. One BUG per distinct defect; entries already covered are marked, not re-captured. Not idempotent.
Prints `entry -> BUG` pairs for `harvest_kit_gaps.py --mark`."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "BUG"]
SRC = "synaipse-unified kit_gaps.jsonl, harvested 2026-09-26 (staging/generation-6/harvest-synaipse-2026-09-26.txt)"


def bug(title, entries, observed, expected, severity, ac, limits):
    return {"entries": entries, "body": {
        "title": title, "related_pr": "PR-0012", "severity": severity,
        "observed": "FIELD (synaipse-unified), entries %s: %s" % (", ".join(entries), observed),
        "expected": expected, "repro": "see the harvest entries named in `observed`",
        "acceptance_criteria": [{"id": "AC-1", "text": ac}], "source": SRC, "limits": limits}}


BUGS = [
    bug("Die FR-0093-Kostenzeile ('lange Laeufe im Hintergrund, auf die Meldung warten') kollidiert mit dem "
        "Subagenten-Lebenszyklus der Kits: gate_dispatch liest ein Kind, das auf seinen eigenen Hintergrundlauf "
        "wartet, als gestoppt -- Folge: FAILED gebucht, Retry, ein ZWEITER Bauer auf denselben Dateien",
        ["e3787f88e90b1259", "815d3f586242165c"],
        "TSK-0448: the child started its red run in the background and ended its turn to wait; gate_dispatch refused "
        "the lead's turn end ('no child is on TSK-0448', child stopped, nothing staged) and named FAILED; the lead "
        "booked FAILED, the user approved a retry, and a second builder ran concurrently while the first child "
        "resumed on its completion notice, finished CR-0012 (81d7ff7) and submitted. REGRESSION of TSK-0151 "
        "(0a79fc5), which put the line word for word into every kit's order text.",
        "The dispatch/stop gates treat a child that waits on its own background command as ALIVE (it has an "
        "outstanding background task), or the kits' order line tells a SUBAGENT to run long commands in the "
        "foreground with a timeout and keeps the background rule for the LEAD only -- whichever the running path "
        "can measure; no FAILED is ever proposed for a child with a pending completion notice.",
        "high",
        "a process test: a child that starts a background run and ends its turn is not reported stopped by "
        "gate_dispatch, and the lead's turn end is not answered with FAILED -- names this bug, red on 2026.09.26-5",
        "Im Feld passiert: ein Auftrag wurde fälschlich als gescheitert gebucht und doppelt gebaut. Begrenzt: der "
        "erste Bauer hat trotzdem fertig geliefert; bis zur Korrektur sollen Unteragenten lange Läufe im Vordergrund "
        "mit Zeitlimit fahren."),
    bug("Der Lease-Lebenszyklus hat Sackgassen: eine abgelaufene Lease laesst den Auftrag in IN_PROGRESS haengen, "
        "und ein Vordergrund-Kind kann sich nie selbst buchen, weil LEASED->IN_PROGRESS erst nach seinem Ende laeuft",
        ["a4660368946a097a", "84eb410f8037d1cf", "4ed998fc5d5b05a7"],
        "TSK-0358: 'lease expired -- task returned to READY' while the task stayed IN_PROGRESS; dispatch then refused "
        "('IN_PROGRESS, not READY'), IN_PROGRESS->READY is illegal. TSK-0437: submit-result refused 'LEASED -- needs "
        "IN_PROGRESS'; the promotion runs in the spawn's PostToolUse, which for a foreground spawn fires only after "
        "the child finished -- and the PM skill recommends run_in_background false. sweep-leases then released the "
        "committed work to READY with no self-service route back.",
        "Every lease state has an exit the running roles can take: an expired lease really returns the task to "
        "READY (or offers a re-lease that keeps the committed result); a self-path child can book while its lease "
        "is LEASED or the promotion happens at spawn start; the PM skill's foreground default and the lifecycle agree.",
        "high",
        "process tests for the three dead ends (expired lease left IN_PROGRESS; foreground self-path child books; "
        "swept lease with committed work re-bookable) -- each names this bug, red on 2026.09.26-5",
        "Im Feld: Arbeit war fertig und committet, liess sich aber nicht verbuchen; der PM musste von Hand nachtragen. "
        "Begrenzt: nichts geht verloren, es kostet Nacharbeit des PM."),
    bug("Die Pruefung 'ist die Freigabe verdrahtet' irrt: report._runs_no_file loest das Argument des _gate.py-"
        "Starters gegen die Repo-Wurzel statt gegen das Hooks-Verzeichnis auf -- jede Plan-Frage warnt 'wird nichts "
        "freigeben', obwohl gate_approval registriert ist",
        ["5b533a2666fb43dc"],
        "request-approval plan PR-0018..PR-0030: approval_mint_is_wired False because repo_root/gate_approval.py is "
        "absent; the hook IS registered through the _gate.py launcher with the argument gate_approval.py.",
        "The wiring check resolves a launcher argument the way the launcher does (hooks directory), and a test holds "
        "the launcher form.", "high",
        "a test with the _gate.py launcher registration: approval_mint_is_wired True -- names this bug",
        "Die Warnung ist falsch, die Freigabe funktioniert trotzdem. Begrenzt: sie verunsichert und kann den PM "
        "dazu bringen, eine gültige Frage nicht zu stellen."),
    bug("Hash und Vertrauen brechen auf einem Windows-Checkout mit autocrlf: hook_bundle_hash und diagram_hash "
        "normalisieren CRLF nicht, das Kit liefert keine .gitattributes-Regel dafuer; dazu verweigert gate_write_scope "
        "lesende git check-attr/check-ignore und gate_shell_hygiene liest einen Checkout in einem Scratch-Klon als "
        "Branchwechsel",
        ["77b4f320a3d11ce9"],
        "TSK-0440 in a fresh autocrlf=true clone: two .md files of the hook bundle as CRLF -> doctor reports the "
        "bundle changed after trust; a frozen .drawio.svg diagram_hash breaks the same way.",
        "Either the hashes read text as LF-normalised bytes, or the kit ships and installs a .gitattributes rule "
        "(eol=lf) for every hashed path -- the smaller change that makes a fresh autocrlf clone trust-clean; the two "
        "over-refusals fixed or filed.", "high",
        "a test: an autocrlf-style CRLF copy of the installed bundle keeps the recorded hook_bundle_hash (or the "
        "installed .gitattributes prevents the CRLF checkout) -- names this bug",
        "Wer das Projekt auf Windows frisch klont, hat sofort eine 'veränderte' Schutzschicht und gesperrte "
        "Spezialisten. Begrenzt: im bestehenden Checkout tritt es nicht auf."),
    bug("Die V1->V2-Migration importiert offene Auftraege, die nie startbar sind (Abhaengigkeiten als V1-Ids, "
        "V1-Rollenwoerter, leere acceptance_refs) -- jede muss storniert und neu angelegt werden",
        ["57564f47253406b9"],
        "all 66 imported open tasks undispatchable; derives_from frozen after DRAFT. The re-created plan kept the V1 "
        "granularity (one order per SR + a QA review per SR), see the lead's measurement in the next item.",
        "migrate maps dependencies to V2 ids, role words to installed role names and fills acceptance_refs, or "
        "imports open V1 tasks as CANCELLED with a pointer and lets the PM cut V2 orders in the light form.",
        "medium", "a migration test with an open V1 task: the result is dispatchable or explicitly cancelled -- "
        "names this bug",
        "Nach dem Umzug waren alle offenen Aufträge unbrauchbar. Begrenzt: einmalig pro Projekt, der PM hat sie neu angelegt."),
    bug("Der PM schneidet in winzige Scheiben und laesst nach fast jeder pruefen -- entgegen der leichten Form "
        "(EIN Bauer je Ziel, EIN Pruefer am Ziel, kleine Aenderung ohne eigenen Pruefer, DEC-0087/0088); nichts im "
        "Kit bemerkt es, und parallel gebaut wird nie",
        [],
        "MEASURED by the lead 2026-09-26 in synaipse-unified/project_memory/tasks: after the migration the PM "
        "re-created 96 orders in 9 minutes (TSK-0363..0458: 36 backend, 14 ui, 11 quality-engineer REVIEW orders, "
        "one QA review per SR) and runs them one at a time (leased_at strictly serial); every small UI change of the "
        "user (CR-0012..CR-0015, one expected output each) got its own builder order AND its own QA test order. The "
        "dev-team PM skill says the opposite (project-manager/SKILL.md step 7: 'no verifier DURING the build ... a "
        "small change under an existing goal gets NO separate verifier'), but only as prose; the brief's "
        "lease_distribution line does not flag it.",
        "The kit notices and says it where the PM decides: (a) at create-task, an order below a goal that already "
        "has an open build order, or a QA order for a change with one expected output, gets a fact line (not a "
        "refusal) naming DEC-0087/0088; (b) the session brief shows orders per goal and the verifier share; (c) "
        "the migration re-cut (previous item) does not reproduce V1 granularity; (d) disjoint goals can run as "
        "parallel builders -- the brief names candidates (`check-scopes`).",
        "high",
        "a test: create-task for a second build order under the same goal, and for a QA order on a one-output "
        "change, prints the fact line; the brief carries orders-per-goal -- names this bug",
        "Kostet im Feld Zeit und Tokens: viele kleine Runden statt einer grossen. Begrenzt: die Qualität leidet "
        "nicht, nur Tempo und Budget."),
    bug("Die Kit-Update-Nacharbeit hat keine Tueren: die Pending-Liste loeschen, eine Kit-Vorlage uebernehmen, neu "
        "ignorierte Dateien aus git nehmen -- alles verweigert; und die Liste meldet Projekt-gegen-Vorlage-"
        "Abweichung als Kit-Aenderung (leere Merge-Runde je Update, dazu ein UTF-8-BOM)",
        ["99ab1bcbe672d3d6", "169e0ed3594f49f1", "5b87abeccbef4061", "25f81f43379be18d"],
        "the pending list's header and the session notice say 'then DELETE this file' -- gate_write_scope refuses; "
        "taking a byte-identical kit template needs a write into the enforcement layer; `git rm --cached` under the "
        "state directory refused; seven templates reported as changed although the pre/post kit diff is empty.",
        "kernel doors for the three chores (resolve the pending list; adopt the kit template for a listed path; "
        "untrack paths the kit now ignores), and the pending list lists only templates the KIT changed between the "
        "two versions, written without BOM.", "medium",
        "tests for each door and for the list: an update with no kit-side template change lists nothing -- names this bug",
        "Jedes Kit-Update kostet eine leere Nacharbeitsrunde und hinterlässt Dateien, die niemand entfernen darf. "
        "Begrenzt: der Schutz selbst ist korrekt, nur die Aufräumwege fehlen."),
    bug("gate_shell_hygiene: Aufraeumen der eigenen Test-Container (eigenes Compose-Projekt) ist unmoeglich, und "
        "die Zustimmung des Nutzers laesst sich nicht registrieren -- rund 8 GB bleiben liegen",
        ["85e0e507e483aea5", "3ef943aabd741bf1"],
        "compose project qa-tsk0431 created by a QA order itself for isolation; its volumes/images are 'foreign'; "
        "after the user agreed in chat the gate refused again -- its remedy has no way to register the answer.",
        "a project-owned naming for test compose projects the gate recognises as this repo's (e.g. a prefix derived "
        "from the repo), or an approval kind for a named cleanup the user mints.", "medium",
        "a test: a compose project named by the kit's test convention is cleanable; a foreign one stays refused -- "
        "names this bug",
        "Speicher bleibt belegt, bis der Nutzer selbst aufräumt. Begrenzt: nichts Fremdes wird angefasst."),
    bug("Der Widerspruchs-Check haelt einen VERIFIED-Fehler fuer widerspruechlich, solange ein aelterer "
        "gescheiterter Selektionslauf sein 'aktuelles Urteil' ist -- ein spaeterer bestandener Selektionslauf ersetzt "
        "ihn nie",
        ["1542b4c4d303833c"],
        "BUG-0001 VERIFIED vs EVD-0025 (old failing selection) while EVD-0028 (passing selection) exists; resolved "
        "only by archiving; the same trap waits for BUG-0002.",
        "the current verdict for a bug is the NEWEST run of the same scope that names it; a later passing selection "
        "supersedes an older failing one.", "medium",
        "a test: fail(selection) then pass(selection) on the same bug -> no contradiction -- names this bug",
        "Ein korrekt geschlossener Fehler meldet einen Widerspruch. Begrenzt: Umgehung durch Archivieren."),
    bug("Der Architektur-Schritt ist ein Henne-Ei: unter einem grossen Ziel ohne ACCEPTED SR wird genau der "
        "Architekten-Auftrag verweigert, der das SR ableiten soll; und ein SR mit einem fremden zweiten Elternteil "
        "zaehlt still nicht -- die Verweigerung nennt keins",
        ["96fa2200b574757c", "4f8324641513b18d"],
        "TSK-0444 under PR-0019 (large): refused 'no SR ACCEPTED' -- worked around by re-rooting under a "
        "technical_enabler goal; TSK-0445: SR-0280..0283 ACCEPTED but each also derives from CR-0007 (other goals), "
        "one stray parent voids them for the check, the refusal names none.",
        "the architecture class itself is exempt from the architect-step precondition (it IS the step); a SR counts "
        "for every goal it derives from; the refusal lists the SRs it examined and why each did not count.",
        "medium", "tests for both shapes -- name this bug",
        "Der PM musste Aufträge umhängen, um weiterzukommen. Begrenzt: es gibt eine Umgehung."),
    bug("Handwerks-Gedaechtnis: ein Shell-Schreibzugriff nach `cd` in das Gedaechtnis-Verzeichnis wird nicht "
        "gesehen (relative Pfade), und ein Gedaechtnis ueber dem Budget ist aus keiner Sitzung wieder unter das Budget "
        "zu bringen",
        ["c995c06a91035d2d", "9ab362823d864942"],
        "TSK-0450's frontend-developer appended to its agent-memory MEMORY.md via the shell after a cd (gate saw only "
        "relative paths); the memory holds 103 topics vs budget 20, guard_memory_budget refuses every Edit while it "
        "references items, git restore refused, no route deletes surplus topic files.",
        "gate_write_scope places relative words after a cd it can compute (or refuses them like this repo's gate "
        "does, H20 class), and a kernel/guard door prunes an over-budget memory to budget (deleting is safe).",
        "medium", "tests: the cd+append line is refused; the prune door brings a 103-topic memory under budget -- "
        "name this bug",
        "Ein Gedächtnis-Eintrag kam am Schutz vorbei, und das übervolle Gedächtnis ist gesperrt. Begrenzt: betrifft "
        "nur die Handwerks-Notizen, nicht Code oder Projektakte."),
    bug("Die Fehlschlag-Klasse (DEC-0107) kann der pruefenden Rolle nie gelingen: waehrend IN_PROGRESS verweigert der "
        "Kernel ('nur fuer einen FAILED-Lauf'), nach FAILED verweigert gate_dispatch (keine Lease mehr beim Pruefer)",
        ["9252f74bcdf50ed5"],
        "TSK-0454 failed only on a delivery-sequence state rule; the verifier tried `mechanical` and was refused in "
        "both states.",
        "the classification is accepted from the verifying role in the one window the process really has (e.g. with "
        "the FAILED transition itself, or by the role whose lease just ended, within its hand-back).", "medium",
        "a process test: the verifier classifies its failed run as mechanical and the climb counter skips it -- "
        "names this bug",
        "Jeder gescheiterte Prüflauf zählt als Fehler des Bauers und kann das Modell unnötig hochstufen. Begrenzt: "
        "Kosten, keine falsche Lieferung."),
]

ALREADY = {"46188f2d49451e25": "DEC-0118", "60269703d415f386": "BUG-0311"}

env = dict(os.environ, PYTHONPATH="team-kits")
pairs = list(ALREADY.items())
for item in BUGS:
    r = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(item["body"]),
                       capture_output=True, text=True, encoding="utf-8")
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-1500:])
        sys.exit(r.returncode)
    bug_id = r.stdout.split()[0]
    pairs += [(entry, bug_id) for entry in item["entries"]]
print("PAIRS " + json.dumps(pairs))
