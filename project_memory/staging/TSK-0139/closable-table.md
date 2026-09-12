# TSK-0139 -- the ids AC-3 closes, in the shape `tools/close_measured_pass.py` reads

NOT A SURVEY, and it must not be read as one. This table exists so the ONE tool that derives a
defect's naming nodes and re-runs them can be pointed at the ids of THIS order instead of at
TSK-0131's stock-taking. The verdict column says `MEASURED-PASS` for every row because that is the
word the tool filters on; what the row asserts is only "this order says the defect is closable, go
and measure it". The measurement is the tool's re-run, and a row whose nodes fail or whose defect
no test names comes back held back -- which is the point of running it rather than typing evidence.

The ids are the two lists of the protocol's section 20 (a): the fifteen this order fixed red-first,
and the sixteen it measured already fixed with a naming test.

| Item | Stand | Loch | Verdikt | Evidenz | Gemessene Zeile | Titel |
|---|---|---|---|---|---|---|
| BUG-0010 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0014 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0016 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0017 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0022 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0023 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0026 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0027 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0031 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0034 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0037 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0044 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0046 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0050 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0052 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0053 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0054 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0057 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0058 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0062 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0067 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0074 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0075 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0076 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0077 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0079 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0080 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0081 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0082 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0087 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
| BUG-0092 | TRIAGED | - | MEASURED-PASS | - |  | AC-3 of PR-0012 |
