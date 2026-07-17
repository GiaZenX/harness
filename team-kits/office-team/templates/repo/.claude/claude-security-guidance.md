# Project security-review policy (read by the security-guidance plugin's LLM reviewer)

Scope guidance for this repository (a back-office workspace, not a software product):

- `project_memory/**` (YAML bookkeeping: PROCs, filing plan/log, registers, progress),
  `ledger/**` (text CSV), `reports/**` and `docs/**` are **business state, not executable
  code**. Do NOT deep-review them; the only finding worth raising there is an actual committed
  secret/credential.
- `inbox/`, `archive/`, `outbox/` contain the user's REAL business documents (invoices,
  personal data). They are untracked by design — never quote their contents into a review.
- Focus the review effort on the only executable surface: `scripts/**` and `.claude/hooks/**`
  changes (the enforcement layer itself is kit-owned and hash-tracked — flag any edit to it).
- The repository's own guards already enforce append-only ledger writes, verified filing and
  PROC approval hashes — treat those classes as covered; prioritise anything that would
  exfiltrate document contents or weaken a guard.
