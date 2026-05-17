# CI/CD Developer Experience Health Report

## Sendable Summary

This report separates the deployment-confidence story (main branch) from the developer-experience story (all runs). Both views are needed: main-branch health is what governs release decisions; all-runs health is what governs developer friction.

## Headline Metrics

### Main branch (release confidence)

- Runs analyzed: 9
- Pass rate: 67%
- Retry rate: 56%
- Flake rate (passed-with-retries): 22%
- Median duration: 26.9 minutes
- Long-tail duration (p90): 50.3 minutes
- Rollbacks: 1
- Release confidence risk: High

### All runs (developer experience)

- Runs analyzed: 15
- Pass rate: 67%
- Retry rate: 60%
- Flake rate (passed-with-retries): 27%
- Median duration: 22.1 minutes
- Long-tail duration (p90): 47.7 minutes
- Rollbacks: 1
- Release confidence risk: High

## Per-Service Breakdown

Sorted by pass rate ascending so the services that need attention surface first.

| Service | Runs | Pass rate | Retry rate | Median min | Rollbacks |
| --- | ---: | ---: | ---: | ---: | ---: |
| `web-app` | 4 | 25% | 100% | 28.9 | 1 |
| `cash-service` | 3 | 67% | 100% | 49.8 | 0 |
| `portfolio-api` | 5 | 80% | 20% | 20.3 | 0 |
| `auth-service` | 3 | 100% | 33% | 16.2 | 0 |

## Risk Signals (Main Branch)

- Failure concentration: `e2e` is the top failure stage on main (2 run(s)).
- Retry concentration: `e2e` is the top retry stage on main (3 run(s)); passed-with-retries still costs developer time.
- Service concentration: `web-app` accounts for 2 failed run(s) on main.
- Rollback signal: 1 main-branch rollback(s) in this window.

## Recommended Actions

1. Treat the 1 main-branch rollback(s) as a release-review trigger, not a one-off — capture the contributing CI signal before the next deploy.
2. Stabilize the `e2e` stage on main first; that is where deployment confidence is actually being eroded.
3. Assign a platform owner for `web-app` — failures are concentrating there and the service-level table makes the gap visible.
4. Surface flake rate (passed-with-retries) on the platform dashboard alongside pass rate so devex friction stops being invisible.
5. Flag the long-tail duration (50.3 min p90) as a developer-friction incident on main; pass/fail alone hides it.

## Developer Experience Impact

This is the decision-making layer a CI/CD and Developer Experience role should produce: where failures concentrate on the release-critical branch, which retries waste developer time on every branch, which services need an owner, and what action would reduce friction before the next deploy. The point is not to mimic a full platform; it is to make the platform conversation actionable in one short readout.
