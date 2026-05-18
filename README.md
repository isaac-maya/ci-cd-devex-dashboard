# Wealthsimple CI/CD Developer Experience Dashboard

🌐 **Live demo:** https://isaac-maya.github.io/ci-cd-devex-dashboard/

A lightweight platform-engineering sample for Wealthsimple's CI/CD and Developer Experience work. It turns synthetic pipeline history into two distinct readouts that platform teams actually need: **release confidence** (main branch) and **developer experience** (all runs). The per-service breakdown makes ownership gaps visible in a single table.

This repo is the public demo layer. Application-specific hiring-manager packets are maintained separately inside role bundles so they can be tailored per application without turning the public repo into a one-off packet.

## Run

```bash
python3 pipeline_health.py
```

The command refreshes `devex_report.md`.

## What It Demonstrates In 30 Seconds

- Release confidence and developer experience are two views of the same data, not one blended metric.
- The generated brief starts with a decision strip, then shows the developer-friction tax and the service that should be triaged first.
- Failure concentration and retry concentration are tracked separately, so passed-with-retries is treated as developer-time cost instead of being hidden behind eventual green.
- The static site and the Markdown brief now come from the same generator, which keeps the public demo aligned with the underlying sample data.

## Why It Fits Wealthsimple

- **Release confidence**: main-branch view is the deployment-decision story, separated from feature-branch noise.
- **Developer experience**: retry rate, flake rate, and long-tail duration are tracked as devex friction, not just CI noise.
- **Platform ownership**: per-service table makes "who owns this" a visible question, not an implicit one.
- **Internal platform product thinking**: the output is short enough for engineers and delivery leads to use immediately in a release review.

## Public Demo Files

- `sample_runs.json`: 15 synthetic CI runs across 4 services with retries, failures, retry-stage detail, and one rollback.
- `pipeline_health.py`: local summarizer; produces the Markdown brief and the static site from the same computed metrics.
- `devex_report.md`: generated report with release confidence, developer friction tax, and ownership signals.
- `index.html`: generated public demo page for GitHub Pages.

## Data Schema

Each run has: `run_id`, `branch`, `service`, `status` (passed/failed), `duration_min`, `retries`, `rollback`, `failure_stage` (only on failed runs), `retry_stage` (only when retries > 0). Separating `failure_stage` from `retry_stage` matters: a passed run with retries is a developer-time cost, not a failure, but pretending they are the same hides the friction.

## Public Share Hook

A compact CI/CD release-confidence brief that separates release confidence on `main` from developer friction across all runs, then turns retries, rollback exposure, and service concentration into a short platform decision artifact.
