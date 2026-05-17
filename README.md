# Wealthsimple CI/CD Developer Experience Dashboard

A lightweight platform-engineering sample for Wealthsimple's CI/CD and Developer Experience work. It turns synthetic pipeline history into two distinct readouts that platform teams actually need: **release confidence** (main branch) and **developer experience** (all runs). The per-service breakdown makes ownership gaps visible in a single table.

## Run

```bash
python3 pipeline_health.py
```

The command refreshes `devex_report.md`.

## What It Demonstrates In 30 Seconds

- Release confidence and developer experience are two views of the same data, not one blended metric — the report shows both side by side.
- A per-service table sorted by pass rate surfaces the problem service in one glance (in the sample data: `web-app` at 25% pass rate, 100% retry rate, one rollback).
- Failure concentration and retry concentration are tracked separately — passed-with-retries is treated as developer-time cost, not hidden behind eventual green.
- Recommended actions tie back to specific main-branch signals so a release review has a concrete agenda.

## Why It Fits Wealthsimple

- **Release confidence**: main-branch view is the deployment-decision story, separated from feature-branch noise.
- **Developer experience**: retry rate, flake rate, and long-tail duration are tracked as devex friction, not just CI noise.
- **Platform ownership**: per-service table makes "who owns this" a visible question, not an implicit one.
- **Internal platform product thinking**: the output is short enough for engineers and delivery leads to use immediately in a release review.

## Files

- `sample_runs.json`: 15 synthetic CI runs across 4 services with retries, failures, retry-stage detail, and one rollback.
- `pipeline_health.py`: local summarizer; produces main-branch view, all-runs view, per-service breakdown, and recommended actions.
- `devex_report.md`: generated report ready to share in an application thread or recruiter conversation.
- `outreach_note.md`: Wealthsimple-specific sharing note.

## Data Schema

Each run has: `run_id`, `branch`, `service`, `status` (passed/failed), `duration_min`, `retries`, `rollback`, `failure_stage` (only on failed runs), `retry_stage` (only when retries > 0). Separating `failure_stage` from `retry_stage` matters: a passed run with retries is a developer-time cost, not a failure, but pretending they are the same hides the friction.

## Outreach Hook

A compact CI/CD dashboard that separates release confidence (main branch) from developer experience (all runs), with a per-service breakdown that makes ownership gaps visible. It felt closely aligned with Wealthsimple's focus on CI/CD, deployment guardrails, and developer experience as one platform conversation rather than two.
