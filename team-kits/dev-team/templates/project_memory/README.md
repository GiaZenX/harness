# project_memory/ — artifact templates

These YAML skeletons are the canonical structure of a project's `project_memory/`.
The **PM** (the foreground agent) copies them into the project's `project_memory/` at project init and
fills them as the phase model progresses. `project_memory/` is the **single source of truth** — no ad-hoc
status/summary/report files are allowed (this is also enforced by a hook).

| File | Write owner | Purpose |
|---|---|---|
| `project_config.yaml` | PM | Preset, repo mode, model map |
| `product_requirements.yaml` | PM | PRDs (functional) |
| `change_requests.yaml` | PM | CRs |
| `system_requirements.yaml` | PM + Architect | SRs (technical) |
| `tasks.yaml` | Backend / Frontend | Tasks |
| `architecture.yaml` | Architect | Components, structure |
| `decisions.yaml` | Architect | ADRs |
| `coding_guidelines.yaml` | Architect | Hard code rules (QA-enforced) |
| `testing_guidelines.yaml` | QA | Test rules |
| `definition_of_done.yaml` | QA | DoD |
| `review_reports.yaml` | QA | Code review results |
| `test_reports.yaml` | QA | Test results |
| `acceptance_reports.yaml` | QA | Acceptance checks |
| `progress.yaml` | PM | Status line + metrics overview |
| `progress.dashboard.template.html` | PM | Static shell the dashboard is rendered from |
| `generate_dashboard.py` | PM | Generator: builds the dashboard from the YAML files |
| `progress.dashboard.html` | PM | Generated user-facing dashboard (do not hand-edit) |
| `changelog.yaml` | PM | History |

`progress.dashboard.html` is a self-contained, dependency-free dashboard. It is generated, never
hand-edited: the **PM** runs `generate_dashboard.py`, which reads the YAML artifacts (PRDs, tasks, CRs,
`progress.yaml`), rebuilds the file from `progress.dashboard.template.html`, archives the previous version
under `dashboard_history/`, and lists what changed since the last run. The bars are expandable to reveal
the items behind each status (id, title, owner, origin, start/end dates). Running the generator needs
PyYAML (`pip install pyyaml`); the generated HTML itself has no dependencies and opens by double-click.

Everyone may read everything; each role writes only its own area. See the constitution (`CLAUDE.md`) for
the full rules.
