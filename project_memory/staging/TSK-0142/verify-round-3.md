# Prüfbericht TSK-0142 (PR-0012, Order 3b, Strom B, B3-Abschluss) — Runde 3 — **PASS (drei benannte Reste D1-D3)**

Prüfer: `harness-verifier` (Opus, high), 18 min, +51 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-12 15:12, Uhr gelesen). D1/D3 (Frageform/Preise) und D2 (H55 Repo-Zeile) → Zielrunde TSK-0144.

Alles gemessen. Abschlussbericht:

---

# Prüfbericht TSK-0142, Runde 3 (B3-Abschluss) — **PASS**, mit drei benannten Resten

Einzel-Schnappschuss `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0142\verify3\`; zwei Piloten aus diesem Schnappschuss, Hook-Liste je aus deren eigener `settings.json` (9 Bash-Hooks pro Kit).

## Bestätigt

**(2) C2-Rework vollständig** — alle registrierten Bash-Hooks, beide Kits:
```
rc 0 (früher fälschlich 2):  cat > patch.diff <<'EOF' · cat > patch/notes.md <<'EOF' ·
                             cat > bash.md <<'EOF' · cat > source.txt <<'EOF' · cat > sh.md <<'EOF'
rc 2 (unverändert):          bash/sh -s/nohup bash/timeout 5 bash <<'EOF' · cat <<'EOF' | bash ·
                             … | tee | bash · . /dev/stdin · source /dev/stdin · xargs -0 bash -c ·
                             patch -p1 · patch.exe -p1 · git apply · git am · cat <(cp …) ·
                             tee >(cp …) · echo $(cp …)
== pilot-dev / pilot-office: 8 OK-Zeilen, 16 REFUSE-Zeilen -> ALL AS SPECIFIED
```
EVD-0408 ist in der Batchzeile gebunden (BUG-0289→EVD-0408), EVD-0393 abgelöst.

**(1) Die drei Schließungen**, jede mit einer Mutation des Fixes:
| Mutation | Knoten | Ergebnis |
|---|---|---|
| V1 `scaffold_team.sh:300` / `.ps1:269` — wurzeltragendes Manifestwort wieder akzeptiert | `test_neither_twin_replays_a_manifest_line_that_is_not_the_installers_to_write` | **1 failed, 53 s** |
| V2 `scaffold_team.sh:311` / `.ps1:276` — `KEPT_ONLY`-Wächter entfernt | derselbe | **1 failed, 100 s** |
| V3 `einvoice_extract.py:199 breakdown_failure` stumm | `test_einvoice_a_tax_total_its_own_breakdown_contradicts_is_refused` | **1 failed** |
| V4b–e Regelblock von **je einer** der vier Rollenseiten entfernt | `test_every_role_that_types_an_approval_value_carries_the_language_rule` | **4 von 4 rot** (dev/research/office `project-auditor.md`, office `records-clerk.md`) |

Und die Richtung, die B3 selbst als Lücke in der eigenen Messung benannt hat — **der Rollback muss weiter laufen** — habe ich nachgestellt (zwei echte Installationen je Zwilling, dann `--rollback`, mit einer vom Nutzer danach geänderten `.claude/settings.local.json`):
```
sh   install1 rc 0 | install2 rc 0 | --rollback rc 0 | settings.local.json des Nutzers unverändert: True
ps1  install1 rc 0 | install2 rc 0 | --rollback rc 0 | settings.local.json des Nutzers unverändert: True
```
Die Ableitung hinter H77 habe ich gegen den laufenden Code gelesen: `_roles_that_type_an_approval_value()` findet **7** Seiten, davon 4 Nicht-Lead — genau die vier, die B3 versorgt hat.

**(3) C1 / BUG-0286** ist aus allen Zeilen raus und offen. B3s Preis-Messung ist **ehrlich**: die Angriffszeile und die Alltagszeile sind dieselbe Gestalt — `git apply changes.diff` und `git apply feature.patch` unterscheiden sich in keinem Wort der Zeile, nur im Inhalt einer Datei, die das Gate nie öffnet (von mir in Runde 2 und heute gegengemessen: beide rc 0, `git apply <<'EOF'` mit `.claude/hooks/…` rc 2, mit `src/app.py` rc 0). Eine engere Gestalt kann es deshalb nicht geben, und die DEC-Frage nennt drei Wege **mit ihren Preisen**, in Alltagssprache, inkl. der gemessenen 42,1 s für Weg 1.

**(5)–(8):** H61 exakt nachgezählt — **dev 1/31, office 0/30, research 1/28, zusammen 2 von 89**. H158 ist wirklich gepinnt: `tools/test_review_procedure.py:997` mit dem Docstring „THIS TEST IS WRITTEN TO GO RED" (Datei in `forbidden_scope`) — der Seam über zwei Eigentümer stimmt. H59/H113 sind Kernel-Kanten (Automat `DONE→VALIDATED` bzw. ein Erledigt-Datensatz als kanonischer Zustand) — beides nicht in B3s Scope. **Fünf Batchzeilen, 29 Ids, rc 0, 0 refused, jede Id genau einmal, `BUG-0286` in keiner.** Spiegel: keine Datei, die zwei oder drei Kits ausliefern, unterscheidet sich (48 Hook-Dateien). Decke unverändert: dev 61064, office 66435, **research 62894**. Pins: „3 kits, 12 files, 125 sections, all pins current". `ruff` über `team-kits/ tools/ user/`: All checks passed. `validate.py`: nur die drei Stempel-Fehler. Abschlusslauf der sechs Knoten: **6 passed, 145 s**. Naming über **alle** TSK-0142-EVDs inkl. 0406/0407/0408/0409: durchweg OK.

**(4) Die acht Downgrades, einzeln geprüft — sechs sind Messungen, zwei sind falsch einsortiert:**
- **H51/BUG-0143 — Messung.** Anbieter-Grenze, und die Behauptung „der Befund geht nicht verloren" stimmt am Code: `team-kits/*/hooks/gate_dispatch.py:538` schreibt `record_note` für **jeden** Befund, `:539` prüft erst danach `stop_hook_active`.
- **H129/BUG-0212 — Messung.** Ein `PreToolUse`-Haken hat kein Nachher; der Stolperdraht existiert und läuft (`test_every_destroying_stem_is_load_bearing_at_both_ends`, mit `test_an_invalid_ledger_is_named_on_the_page` zusammen **19 passed, 9 s**).
- **H119/BUG-0203 — Messung** (beide Hälften, Test oben mitgelaufen).
- **H82/BUG-0174, H107/BUG-0191, H140/BUG-0223 — Messungen**; H140 hat B3 selbst von „not reached" auf „Downgrade" korrigiert, mit dem Grund (ein Kachelblatt hat keine ausgezeichnete Ansicht, also ist Schweigen die richtige Antwort) — die Korrektur steht im Protokoll statt die erste Fassung zu löschen.
- **H72/BUG-0164 — falsch einsortiert** (siehe D1).
- **H55/BUG-0147 — halb falsch einsortiert** (siehe D2).

**(7) BUG-0056:** B3s „halb veraltet" ist gemessen und ich habe die tragende Stelle nachgelesen: `team-kits/kernel/migrate.py:1462` baut den Eintrag als `{"source": rel, …}` aus dem Lauf **unter der Zustandswurzel**, und `:1227` schreibt `legacy_source: entry["source"]`. Ein aufgezeichneter V1-Pfad außerhalb des Zustandsbaums entsteht also gar nicht. Gebaut ist damit nichts Neues; offen bleibt die **Depot-Kopie unter `project_memory/staging/`**, die absichtlich schreibbar ist — das Schließen hieße, das Schreib-Gate bei **jedem** Schreibzugriff die Migrationsdatensätze scannen zu lassen (die H61-Kosten). Das gehört so vor den Lead, wie B3 es hinschreibt.

## Befunde

### D1 — `BUG-0164` / H72 steht unter „downgraded", stellt dem Nutzer aber eine Frage — ohne Frage
`project_memory/staging/TSK-0142/protocol.md:996-1006`. Der eine deutsche Satz der Zeile lautet: „…ist es **eine Frage an dich**, ob es strenger werden soll — nicht ein Fehler im Code." Damit ist die Zeile inhaltlich das, was H178 und H166 sind: eine **Nutzerentscheidung**. Sie hat aber keine Frage mit Optionen und Preisen, und in den COUNTS zählt sie als eine der acht Messungen. Gemessene Belegstelle für die Ungleichbehandlung: dieselbe Datei führt `BUG-0260`/H178 (`:968`), `BUG-0248`/H166 (`:1027`) und `BUG-0286` (`:878`) je mit ausformulierter Frage. Minimal: entweder dieselbe Form (drei Zeilen: Lage, Optionen, Preis je Option) oder der Satz hört auf zu fragen. Kein Blocker für den Merge — die Id steht in keiner Freigabezeile.

### D2 — `BUG-0147` / H55 wird als Downgrade gezählt, obwohl die zweite Hälfte eine Zeile **in diesem Repo** ist
`install.sh:282` und `install.ps1:309` nennen beide `user/bridge/update_kit.py`, und die Datei liegt hier (`user/bridge/update_kit.py`). Das Nutzerwort sagt: was hier reparierbar ist, wird repariert. B3 schreibt das in der Zeile (`:1068` „plus a seam") und in „Seam handoffs (B3)" Nr. 2 auch hin — aber die COUNTS führen die Zeile ungeteilt unter „downgraded with a measurement: 8". Wer nur die Zählung liest, hält eine reparierbare Repo-Zeile für unschließbar. Minimal: in der Zählung als „Downgrade (Welt-Grenze) + Seam (Repo-Zeile)" trennen; die Weltgrenze (fremde Rechner) bleibt unbestritten.

### D3 — die Frage zu `BUG-0260` / H178 nennt zwei Wege **ohne** ihren Preis
`protocol.md:976-980`. Der Text sagt, was (a) und (b) tun, nicht was sie kosten — anders als die Fragen zu H202 („trifft jedes normale Einspielen eines Patches", gemessen) und H166 („beides ändert, wie die Auswertung summiert"). Für einen Nutzer ohne Technikwissen ist eine Option ohne Preis nicht entscheidbar. Minimal: je Weg einen Halbsatz Preis — bei (a) verliert der Bericht die Einstufung ganz, bei (b) kann nur die prüfende Rolle sie setzen und jede andere Rolle braucht dafür eine Rückfrage.

## Explizite Negativbefunde

**Gemessen, in Ordnung:** C2-Matrix (24 Zeilen × 9 Hooks × 2 Kits), die vier Mutationen der drei Schließungen, die vier Rollenseiten einzeln, Rollback-Erlaubnisrichtung in beiden Zwillingen, Naming über alle EVDs, Abschlusslauf 6/6, fünf Batchzeilen (29 Ids, 0 refused, `BUG-0286` abwesend), H61-Zählung 2/89, H158-Pin, `record_note` vor der Schranke, die zwei zitierten Stolperdrähte, Spiegel-md5, Decke, Pins, ruff, validate.

**Nicht gemessen:** der volle Lauf und der Stempel (Lieferkriterium der Merge-Runde; die 16 stempelabhängigen Reds habe ich nicht einzeln nachgestellt, B3s Bisektion für die 9 in `test_kitupdate.py` habe ich nicht wiederholt); die Kernel-Hälften H59/H113/BUG-0265-AC-1 (Strom A); die drei übrigen offenen H88-Teile (alte Snapshots ohne `RESTORE_SET`, Residuenliste, fremdes Manifest nur aus `RESTORABLE`-Pfaden); die UBL-Seite von H75 (laut B3 nur synthetisch belegt); die PowerShell-Seite der Heredoc-Regel.

**Eigene Fehlgriffe:** drei meiner Mutationen an den Rollenseiten waren inert (ein einzelnes `request-approval` ersetzt, eine Satzmitte gebrochen, einen Wert gestrichen, den der Test über `--role`/`--scope` weiterhin findet) — erst das Entfernen des ganzen Blocks hat gemessen. Das lag an meinen Mutationen, nicht am Test.

## Urteil

**PASS.**

Die drei Schließungen dieser Runde halten der Mutation stand, das C2-Rework schließt meine Runde-2-Über-Verweigerung, ohne einen einzigen Angriff freizugeben, und `BUG-0286` ist sauber aus den Freigabezeilen heraus und als Nutzerfrage mit gemessenen Preisen aufgestellt — damit ist der Zustand, den ich in Runde 2 blockiert habe, aufgelöst. Die **29 Ids in den fünf Zeilen sind aus meiner Sicht freigabereif**.

Die drei Befunde blockieren den Merge **nicht** — keiner berührt eine Freigabezeile oder eine Angriffskette. Sie gehören in die Übergabe an den Lead als benannte Reste: **D1** (H72 braucht die Frageform oder einen Satz, der nicht fragt), **D2** (H55 in der Zählung trennen — eine Repo-Zeile bleibt zu reparieren), **D3** (die H178-Frage braucht ihre Preise). Dazu unverändert aus Runde 2, weiterhin offen und gemessen: `BUG-0286` (Patch-Datei, Nutzerfrage), die `H11`-Klasse `cat <<'EOF' > run.sh ; bash run.sh` und die Kernel-/Settings-Seams H61, H59, H113, H158, BUG-0265-AC-1.