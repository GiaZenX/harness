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
| `fzulg_documentation.yaml` | PM | BSFZ application (form fields, work plan) + eligibility pillars + effort |
| `progress.yaml` | PM | Status line + metrics overview |
| `changelog.yaml` | PM | History |
| `progress.dashboard.template.html` | PM | Static shell the dashboard is rendered from |
| `generate_dashboard.py` | PM | Generator: builds the dashboard from the YAML files |
| `progress.dashboard.html` | PM | Generated dashboard (do not hand-edit) |
| `reports/scientific_report.template.tex` | Report Writer | Fixed LaTeX template (submittable report) |
| `reports/experiment_report.template.html` | Report Writer | Fixed HTML preview template |
| `reports/EXP-*.{tex,pdf,html}` | Report Writer | Rendered per-experiment reports (LaTeX/PDF + HTML preview) |
| `reports/fzulg_application_RQ-*.md` | Report Writer | Rendered BSFZ application draft |
| `reports/assets/` | (bundled) | Local KaTeX (CSS/JS/fonts) for the offline HTML preview |

## Dashboard

`progress.dashboard.html` is a self-contained, dependency-free dashboard. It is generated, never
hand-edited: the **PM** runs `generate_dashboard.py`, which reads the YAML artifacts (RQs, tasks, PAs,
`progress.yaml`), rebuilds the file from `progress.dashboard.template.html`, archives the previous version
under `dashboard_history/`, and lists what changed since the last run. The bars are expandable to reveal
the items behind each status (id, title, owner, origin, start/end dates). Running the generator needs
PyYAML (`pip install pyyaml`); the generated HTML itself has no dependencies and opens by double-click.

## Experiment reports

Immediately after each experiment's **Reviewer-gate PASS** (per experiment, never deferred to the RQ merge)
the Report Writer renders the **scientific report in LaTeX** (`reports/EXP-xxxx.tex`,
compiled to `EXP-xxxx.pdf` when a LaTeX engine is available) — the submittable deliverable — plus a
self-contained **HTML preview** (`reports/EXP-xxxx.html`) whose formulas render **offline** via the bundled
KaTeX in `reports/assets/` (no CDN). KaTeX is only the preview's math renderer; the LaTeX/PDF is the report.
Once an RQ's `fzulg_documentation.yaml` is `READY`, it also renders the **BSFZ application draft**
(`reports/fzulg_application_RQ-xxxx.md`). The Report Writer presents existing results only — it never alters
data or conclusions.

Everyone may read everything; each role writes only its own area. See the constitution (`CLAUDE.md`) for
the full rules.
