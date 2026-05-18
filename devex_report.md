# Wealthsimple CI/CD Release Confidence Brief

Synthetic sample generated from a compact multi-service pipeline history. Designed to show how I would frame CI/CD reliability, developer friction, and service ownership in a platform review.

## Decision Strip

**Hold**: Main branch shows rollback exposure plus concentrated `e2e` instability, so the next deploy should be gated on targeted stabilization work.

## Best 30-Second Skim

- Release risk on `main` is **High** because 56% of runs required retries and the sample window includes 1 rollback.
- Developer friction risk across all runs is **High**; `web-app` has the most retry-affected runs (4) while `web-app` is the clearest release-risk service on `main`.
- The fastest next action is to stabilize `e2e` on `main` and make a named owner accountable for `web-app`.

## What This Artifact Helps Decide

| Question | Evidence in this packet | Why it matters |
| --- | --- | --- |
| Can we trust the next deploy? | Main-branch retry, rollback, and failure concentration | Separates release confidence from general CI noise |
| Where is developer time being lost? | Retry events, retry-touched minutes, long-tail duration | Makes friction visible before it becomes team-normal |
| Which service needs ownership attention first? | Per-service table sorted by pass rate | Turns platform pain into an accountable next action |

## Sendable Summary

This report separates the deployment-confidence story (`main`) from the developer-experience story (all runs). That split matters for a CI/CD and Developer Experience role: release gating, rollback prevention, and service ownership should be judged differently from day-to-day branch friction.

## Headline Metrics

### Main branch (release confidence)

- Runs analyzed: 9
- Pass rate: 67%
- Retry rate: 56%
- Flake rate (passed-with-retries): 22%
- Retry events: 10
- Retry-touched minutes: 186.9
- Median duration: 26.9 minutes
- Long-tail duration (p90): 50.3 minutes
- Rollbacks: 1
- Release confidence risk: High

### All runs (developer experience)

- Runs analyzed: 15
- Pass rate: 67%
- Retry rate: 60%
- Flake rate (passed-with-retries): 27%
- Retry events: 15
- Retry-touched minutes: 302.3
- Median duration: 22.1 minutes
- Long-tail duration (p90): 47.7 minutes
- Rollbacks: 1
- Developer friction risk: High

## Developer Friction Tax

| Signal | Main branch | All runs |
| --- | ---: | ---: |
| Retry-affected runs | 5 | 9 |
| Retry events | 10 | 15 |
| Retry-touched minutes | 186.9 | 302.3 |
| Long-tail duration p90 | 50.3 min | 47.7 min |

Retry-touched minutes are not presented as exact engineering hours lost. They are a conservative signal that the release path is spending meaningful time inside unstable or rerun-heavy work.

## Per-Service Breakdown

Sorted by pass rate ascending so the services that need attention surface first.

| Service | Runs | Pass rate | Retry rate | Median min | Rollbacks |
| --- | ---: | ---: | ---: | ---: | ---: |
| `web-app` | 4 | 25% | 100% | 28.9 | 1 |
| `cash-service` | 3 | 67% | 100% | 49.8 | 0 |
| `portfolio-api` | 5 | 80% | 20% | 20.3 | 0 |
| `auth-service` | 3 | 100% | 33% | 16.2 | 0 |

## Risk Signals (Main Branch)

- Failure concentration: `e2e` is the top failure stage on main (2 runs).
- Retry concentration: `e2e` is the top retry stage on main (3 runs); passed-with-retries still costs developer time.
- Service concentration: `web-app` accounts for 2 failed runs on main.
- Rollback signal: 1 main-branch rollback in this window.

## Recommended Actions

1. Treat the 1 main-branch rollback as a release-review trigger, not a one-off — capture the contributing CI signal before the next deploy.
2. Stabilize the `e2e` stage on main first; that is where deployment confidence is actually being eroded.
3. Assign a platform owner for `web-app` — failures are concentrating there and the service-level table makes the gap visible.
4. Surface flake rate (passed-with-retries) on the platform dashboard alongside pass rate so devex friction stops being invisible.
5. Flag the long-tail duration (50.3 min p90) as a developer-friction incident on main; pass/fail alone hides it.

## Honest Scope

This is a synthetic sample, not a claim about Wealthsimple's actual pipeline data, tooling mix, or service topology. The value is in the decision framing: separating release confidence from developer friction, showing where ownership should be made explicit, and turning CI noise into a short operating brief.

## Developer Experience Impact

This is the decision-making layer a CI/CD and Developer Experience role should produce: where failures concentrate on the release-critical branch, which retries waste developer time on every branch, which services need an owner, and what action would reduce friction before the next deploy. The point is not to mimic a full platform; it is to make the platform conversation actionable in one short readout.
