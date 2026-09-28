# TSK-0156 verify round 1 (Pruefer, zweiter Anlauf) -- FAIL

Der erste Pruefer brach mit einem Verbindungsfehler ab; dieses Dokument ersetzt sein Skelett.
Kopie: C:\Offline Repos\v2-testbed\_round-scratch\TSK-0156\verify\tree (robocopy /MIR ohne .git,
Klon von 35e929b als .git). 15:23 neu gespiegelt; rig/cmp.py: 138 geaenderte Dateien byte-gleich
mit dem Hauptbaum (einzige Abweichung eine staging-Datei der Leitung, create_wave1_streams.py).
Rig: ...\verify\rig\ (verweigert fremdes cwd, liest/schreibt binaer bzw. newline="").
Sonden liegen NUR in der Kopie: tree/tools/test_zz_verify_*.py, tree/.claude/hooks/test_zz_verify_h47.py.
Kein Log ganz gelesen; jeweils nur Endzeilen bzw. FAILED-Zeilen.

## Urteil

FAIL. F4 blockiert die Runde in der jetzigen Form: eine in einer Sitzung durchlaufende Kette,
die DIESE Runde neu erzeugt (Zustand CHILD_WAITING aus BUG-0313) und die nirgends benannt ist.
Kleiner Fix (unten) oder benannte Ausnahme in der Loecherliste mit Abnahme des Nutzers.
F1, F2, F3, F5 sind niedrig und koennen als benannte Reste in dieselbe Nacharbeit.

## Befunde

F4 (mittel, NEU durch diese Runde, nirgends benannt, BLOCKIEREND) team-kits/kernel/dispatch.py:1886
(`_relet_refusal_locked`, Zweig CHILD_WAITING) mit :2225 (`record_child_resume`), :2289
(`record_child_end`) und :1798 (`sweep_expired_leases`). Ein Kind, das auf seinen eigenen
Hintergrundlauf WARTET und dessen Lease die Leitung fegt, bleibt fuer immer "wartend".
Mechanismus: Wiederaufnahme und Ende werden nur ueber die Lease dem Task zugeordnet;
`sweep-leases` loescht die Lease eines laufenden IN_PROGRESS-Tasks (lease_only), CHILD_WAITING
bleibt am Task stehen, und keine spaetere Stelle kann es loeschen. Der Kernel selbst schickt die
Leitung hinein (Abhilfe "then sweep-leases"). Gemessen (tree/tools/test_zz_verify_waitsweep.py,
echte gate_dispatch-Prozesse + kernel.cli, Lease-TTL 15 min per created_epoch abgelaufen):
  STEP2 dispatch rc 1 | "a lease for TSK-0001 already exists ... (already expired -- the sweep releases it now). Remedy: wait, then `python scripts/harness.py sweep-leases`"
  STEP5 resume rc 0 | bound task: None | waiting: 2026-09-27T15:56:28 on python -m pytest tests/test_checkout.py -q
  STEP6 child write rc 2 | "this subagent is not bound to a task, so it has no write scope at all"
  STEP8 final stop rc 0 | ended: None | waiting: 2026-09-27T15:56:28 ... | status: IN_PROGRESS
  STEP9 lead stop rc 0 |   (kein Befund: CHILD_WAITING ist fuer idle_dispatches kein Fund)
  STEP10 dispatch rc 1 | "Its child ended its turn WAITING ... and resumes when that run completes ... Remedy: wait for its result"
Der Lauf ist fertig, das Kind ist wieder aufgenommen UND beendet -- die Verweigerung sagt das
Gegenteil, und der Stop-Haken der Leitung meldet es nie. Ausweg existiert, wird aber in diesem
Zweig nicht genannt: `transition TSK-0001 FAILED` rc 0 (gemessen, test_exit_after_sweep). Vor
dieser Runde haette der Stop CHILD_ENDED geschrieben und die Neuvergabe zugelassen.
Fix (minimal): `sweep_expired_leases` laesst die Lease eines Tasks mit CHILD_WAITING stehen (das
Kind lebt) und nennt sie unter "still running"; der WAITING-Zweig nennt den FAILED-Ausweg wie der
Zweig darunter. Test: genau diese Kette, rot vor dem Fix.

F1 (niedrig, Kommentar behauptet mehr als geprueft) tools/test_light_kit.py:890 -- Kommentar
"FR-0095: no request marker, no path, no checksum", geprueft wird nur "approvals/pending" (:895).
Gemessen (tree/tools/test_zz_verify_cards.py, 17 Karten ueber `_real_request`): Pfade im Lesetext
bei analysis ("Lesebereich: src/**"), routine ("project_memory/**"), document_proposal/
document_revision ("aus dem Vorschlag »staging/TSK-0001/profile.yaml«"), filing_correction,
filing_rule, push. Meist der Gegenstand selbst; der staging-Vorschlagspfad nicht (DEC-0119 (6)).
Keine Hex-Folge >= 8 auf irgendeiner Karte. Fix: Kommentar verengen oder Vorschlagspfad aus dem
Lesetext nehmen und "Gegenstand ist ein Pfad" als Regel benennen.

F2 (niedrig, veralteter Zeiger) tools/test_presets.py:712 und :761 nennen `_preset_target_form`,
das Strom A entfernt hat (rig/sigs.py "REMOVED"; keine Definition mehr). Heute
`approvals._preset_lines` (approvals.py:2666). Fix: Zeiger umstellen.

F3 (niedrig) team-kits/*/hooks/gate_write_scope.py `_upkeep_refusal` (dev :1268-1316):
(a) unbenannte Ueber-Verweigerung: `upkeep --help` und `upkeep prune-memory --help` aus einem
Subagenten rc 2 "do not parse" (SystemExit(0) von --help wird als Parse-Fehler gelesen); die
Verweigerung schickt den Subagenten selbst zu `upkeep prune-memory <your role> ...`.
(b) Eigenschaftssatz ohne Test (:1275 "Parsing prints nothing"): Mutation rig/m_upkeep_quiet.py
(redirect_stdout/stderr entfernt) -> tools/test_hooks_v2.py -k "upkeep or prune": 34 passed, RC 0.
Fix: --help als lesend durchlassen oder benennen; den Satz mit Test belegen oder streichen.

F5 (niedrig, Docstring breiter als Code) team-kits/kernel/__init__.py:12 "NO IMPORTER CACHES INTO
THE INSTALLED PACKAGE, whichever route started it": `_INSTALLED` vergleicht den Ordnernamen
woertlich mit ".claude". Gemessen (rig/pyc_case.py, Kopie des Kernels unter <proj>/.claude/kernel,
Prozess ohne -B): ueber `.claude` "pyc files: 0", ueber `.CLAUDE` (derselbe Ordner auf diesem
Host) "pyc files: 9" -- genau der BUG-0310-Zustand. Heilbar mit `upkeep prune-caches`.
Fix: normcase(+realpath) im Vergleich oder den Satz auf die gebaute Schreibweise verengen.

## Negativbefunde gemessen
- Signaturnaehte: einzige geaenderte Signatur, die ein Aufrufer ausserhalb der Kits borgt, ist
  `gate_write_scope._walk` (.claude/hooks/_harness.py:2538). Alle anderen von .claude/hooks
  geborgten Namen haben base->merge denselben AST (rig/bodies.py); A/B-Parameter
  (note, spawn_description, background_tasks, session_id) sind angehaengt mit Default. Die 15 von A
  entfernten approvals-Helfer und gate_approval._markers: kein Aufrufer mehr, nur F2 als Prosa.
- _walk-Fix: M1 (Zwei-Argument-Zweig aus) -> 11 rot / 51 gruen (6:43); M2 (relativ statt absolut,
  was der Docstring verneint) -> 1 rot ([(cd tools && python bump_kit_version.py)]).
- Upkeep-Schranke (BUG-0325), echte Prozesse, Subagent backend-developer: rc 2 fuer env-Starter,
  py -3, -B -X utf8, Backslash, ./scripts, --keep-newest=0 vor der Rolle, doppeltes --retire,
  `--` vor der Rolle, `;`/`&&`, `< /dev/null`, quotierte/teilquotierte Fremdrolle, `$R`,
  adopt-template `> /dev/null`, PowerShell nackt und mit `&`; rc 0 fuer die eigene Rolle (nackt,
  quotiert, `| tail -3`). Mutation "unparsbar = erlaubt" -> 1 rot. prune_memory begrenzt --retire
  auf das Rollenverzeichnis (kitupdate.py:1809-1816).
- Wrapper `timeout 60`, `nohup`, `bash -c`, `sh -c`, `cmd /c`, `xargs`, `python -c`, `$(echo upkeep)`,
  `Start-Process` gehen rc 0 durch -- dieselben Wrapper lassen auch `dispatch`/`set-preset` aus
  einem Subagenten durch (test_zz_verify_order_probe.py 10/10 rc 0): benannte Klassengrenze von
  Regel 4 (L39/L43), nicht neu.
- BUG-0313/0314 als Prozess: tools/test_stream_b_order_flow.py 17 passed (echte gate_dispatch-
  Prozesse); die Luecke ausserhalb dieser Tests ist F4.
- A: 17 Kartenmuster ohne Hex >= 8 und ohne Request-Id; Notiz letzter Block und im Hash
  (consumed_request :4073); gate_approval: Mint nur ueber Echo == build_question und Label.
- Nutzer-Patch 4 in der Kopie: --check "4 site(s)" / apply "DONE -- 4" / --check "0 site(s)" /
  apply "DONE -- 0", alle rc 0; 0 CR-Bytes. H47-Test unpatched 12 failed / 4 passed, patched gruen;
  Mutation Stelle 1b (Backtick) -> 2 rot. Gate-Auswahl (-k redirect/unresolved/resolve/variable/
  placed/expansion/tilde/null/sink/candidates/bug_0139/written, 56 Knoten) gepatcht: 55 gruen.
- H47-Schreibweisen gepatcht: rc 2 fuer `>$F`, `1>`, `&>`, `>|`, `&>>`, `exec 3>`, PowerShell `>`;
  rc 0 fuer `tee $F`, `cp x $F`, `sed -i .. $F`, `dd of=$F`, `Out-File $F` = Operanden-Haelfte
  H16/H200 bzw. L43, benannt. (DEC-0120 consequences "closes the last measured path" ist breiter
  -- Text der Leitung.)
- Stempel: bump_kit_version.py --check "unchanged (2026.09.27-4)" x3; validate.py "all structural
  checks passed"; ruff 0.15.20 ausserhalb project_memory "All checks passed!" (1 Fehler im
  Leitungs-Skript); Pins "all pins current", Groessen "every size is the one on record".
- Spiegel: 28 Hooks x3, einzig session_status.py verschieden (KIT_SPECIFIC_HOOKS).
- Naming-Tests in der Kopie (rig/streams.log): stream_a 34, stream_b 17, stream_c 12 passed;
  Hand-over-Knoten 5 passed; test_hooks_v2 -k "upkeep or prune" 34 passed; test_hooks
  -k reason_the_requester_typed 1 passed; test_hooks Befehlsflaechen-Register 4 passed.
- Kit-Texte: "shall I continue" steht nur noch als Verbot (x3 Verfassungen, x3 PM-Skills).

## Nicht gemessen
- `.claude/hooks/test_gates.py::test_gate1_places_a_tilde_word_where_the_shell_puts_it` haengt in
  meinem Rig > 9:42 (zweimal, auch mit stdin=/dev/null); faulthandler: Threads warten in
  `_changes_the_protected_file` auf `bash -c` (echte Shell-Schiedsinstanz), nicht in einem Gate.
  Test, _sandbox.py und Shell-Pfad sind in dieser Runde unveraendert -- vermutlich dieselbe
  Stau-Klasse wie A's 39-Minuten-Lauf; ob er auf dem Hauptbaum ebenso haengt, ungemessen. Vor dem
  DELIVERY_RUN wissen.
- Volle Suite (Auftrag), echte Claude-Code-Sitzung, Codex-Provider (background_tasks dort),
  A's urspruengliches F (nicht reproduziert, wie beim Umsetzer).
