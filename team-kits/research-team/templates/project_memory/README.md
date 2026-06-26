# project_memory/ — artifact templates (research-team)

These YAML skeletons are the canonical structure of a research project's `project_memory/`.
The **PM** (the foreground agent, here the Research Lead) copies them into the project's `project_memory/`
at project init and fills them as the phase model progresses. `project_memory/` is the **single source of
truth** — no ad-hoc status/summary/report files are allowed (also enforced by a hook).

| File | Write owner | Purpose |
|---|---|---|
| `project_config.yaml` | PM | Preset, repo mode, model map |
| `research_questions.yaml` | PM | RQs (customer-visible goals) |
| `protocol_amendments.yaml` | PM | PAs (changes to an existing RQ) |
| `hypotheses.yaml` | Methodologist | Falsifiable hypotheses (HYP) |
| `experiment_designs.yaml` | PM + Methodologist | EXP designs (technical) |
| `tasks.yaml` | Researcher / Data Analyst | Experiment tasks (TSK) |
| `methodology.yaml` | Methodologist | Approach, rationale, threats to validity |
| `decisions.yaml` | Methodologist | Methodology Decision Records (MDR) |
| `research_guidelines.yaml` | Methodologist | Hard research rules (Reviewer-enforced) |
| `literature.yaml` | Methodologist | Prior art / novelty evidence |
| `results.yaml` | Researcher (raw) / Data Analyst (derived) | Recorded outcomes |
| `findings.yaml` | Data Analyst | Interpretation per hypothesis |
| `validity_criteria.yaml` | Reviewer | Definition of Validity |
| `review_reports.yaml` | Reviewer | Methodological review results |
| `validation_reports.yaml` | Reviewer | Reproduction + validity results |
| `acceptance_reports.yaml` | Reviewer | RQ acceptance checks |
| `fzulg_documentation.yaml` | PM | FZulG eligibility + effort/cost layer |
| `progress.yaml` | PM | Status line + metrics overview |
| `changelog.yaml` | PM | History |
| `progress.dashboard.template.html` | PM | Static shell the dashboard is rendered from |
| `generate_dashboard.py` | PM | Generator: builds the dashboard from the YAML files |
| `progress.dashboard.html` | PM | Generated dashboard (do not hand-edit) |
| `reports/experiment_report.template.html` | Report Writer | Fixed per-experiment report template |
| `reports/EXP-*.html` | Report Writer | Rendered per-experiment reports |
| `reports/assets/` | (bundled) | Local KaTeX (CSS/JS/fonts) for offline LaTeX |

## Dashboard

`progress.dashboard.html` is a self-contained, dependency-free dashboard. It is generated, never
hand-edited: the **PM** runs `generate_dashboard.py`, which reads the YAML artifacts (RQs, tasks, PAs,
`progress.yaml`), rebuilds the file from `progress.dashboard.template.html`, archives the previous version
under `dashboard_history/`, and lists what changed since the last run. The bars are expandable to reveal
the items behind each status (id, title, owner, origin, start/end dates). Running the generator needs
PyYAML (`pip install pyyaml`); the generated HTML itself has no dependencies and opens by double-click.

## Experiment reports

After each experiment the Report Writer renders `reports/EXP-xxxx.html` from
`reports/experiment_report.template.html`, so every report looks identical. Formulas render **offline** via
the bundled KaTeX in `reports/assets/` (no CDN). The report presents existing results only — it never alters
data or conclusions.

Everyone may read everything; each role writes only its own area. See the constitution (`CLAUDE.md`) for
the full rules.
