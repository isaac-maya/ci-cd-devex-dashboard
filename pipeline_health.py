"""Summarize CI/CD health into release-confidence and devex signals."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).parent
RUNS_PATH = ROOT / "sample_runs.json"
REPORT_PATH = ROOT / "devex_report.md"
HTML_PATH = ROOT / "index.html"


def load_runs() -> list[dict]:
    return json.loads(RUNS_PATH.read_text(encoding="utf-8"))


def counted(noun: str, count: int) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {noun}{suffix}"


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    quantiles = statistics.quantiles(values, n=100, method="inclusive") if len(values) > 1 else [values[0]]
    index = max(0, min(len(quantiles) - 1, int(p) - 1))
    return quantiles[index]


def summarize(runs: list[dict]) -> dict:
    total = len(runs)
    if total == 0:
        return {"total": 0}
    failed = [run for run in runs if run["status"] == "failed"]
    retried = [run for run in runs if run["retries"] > 0]
    rollbacks = [run for run in runs if run["rollback"]]
    flaky = [run for run in runs if run["status"] == "passed" and run["retries"] > 0]
    failure_stages = Counter(run["failure_stage"] for run in failed if run.get("failure_stage"))
    retry_stages = Counter(run.get("retry_stage") for run in retried if run.get("retry_stage"))
    failed_services = Counter(run["service"] for run in failed)
    retried_services = Counter(run["service"] for run in retried)
    durations = [run["duration_min"] for run in runs]
    return {
        "total": total,
        "pass_rate": 1 - len(failed) / total,
        "retry_rate": len(retried) / total,
        "flake_rate": len(flaky) / total,
        "retried_count": len(retried),
        "retry_events": sum(run["retries"] for run in retried),
        "retry_touched_minutes": sum(run["duration_min"] for run in retried),
        "median_duration": statistics.median(durations),
        "long_tail_duration": percentile(durations, 90),
        "rollback_rate": len(rollbacks) / total,
        "rollback_count": len(rollbacks),
        "top_failure_stage": failure_stages.most_common(1)[0] if failure_stages else ("none", 0),
        "top_retry_stage": retry_stages.most_common(1)[0] if retry_stages else ("none", 0),
        "top_failing_service": failed_services.most_common(1)[0] if failed_services else ("none", 0),
        "top_retried_service": retried_services.most_common(1)[0] if retried_services else ("none", 0),
    }


def per_service(runs: list[dict]) -> list[dict]:
    services = sorted({run["service"] for run in runs})
    rows = []
    for service in services:
        service_runs = [run for run in runs if run["service"] == service]
        metrics = summarize(service_runs)
        rows.append({
            "service": service,
            "runs": metrics["total"],
            "pass_rate": metrics["pass_rate"],
            "retry_rate": metrics["retry_rate"],
            "median_duration": metrics["median_duration"],
            "rollbacks": metrics["rollback_count"],
        })
    return sorted(rows, key=lambda row: (row["pass_rate"], -row["retry_rate"]))


def risk_level(metrics: dict) -> str:
    score = 0
    if metrics["pass_rate"] < 0.75:
        score += 2
    if metrics["retry_rate"] > 0.35:
        score += 1
    if metrics["flake_rate"] > 0.20:
        score += 1
    if metrics["rollback_count"] > 0:
        score += 2
    if metrics["long_tail_duration"] > 40:
        score += 1
    if score >= 4:
        return "High"
    if score >= 2:
        return "Medium"
    return "Low"


def decision_strip(metrics: dict) -> tuple[str, str]:
    risk = risk_level(metrics)
    failure_stage, failure_count = metrics["top_failure_stage"]
    service, service_failures = metrics["top_failing_service"]

    if risk == "High":
        if metrics["rollback_count"] > 0:
            return (
                "Hold",
                f"Main branch shows rollback exposure plus concentrated `{failure_stage}` instability, so the next deploy should be gated on targeted stabilization work.",
            )
        return (
            "Investigate",
            f"Main branch is carrying elevated failure and retry pressure in `{failure_stage}` and should be reviewed before the next deploy.",
        )
    if risk == "Medium":
        if service != "none" and service_failures > 0:
            return (
                "Investigate",
                f"`{service}` is the main source of release risk in this window; assign an owner and clear the failure concentration before treating the pipeline as healthy.",
            )
        return (
            "Investigate",
            "Main branch is stable enough to continue moving, but the current signals justify a targeted review before treating the release path as healthy.",
        )
    return (
        "Ship",
        "Main branch is showing low release risk in this sample window; continue to watch retries and long-tail duration without blocking the next deploy.",
    )


def recommended_actions(main_metrics: dict, overall_metrics: dict) -> list[str]:
    failure_stage, _ = main_metrics["top_failure_stage"]
    retry_stage, _ = main_metrics["top_retry_stage"]
    service, _ = main_metrics["top_failing_service"]
    actions: list[str] = []

    if main_metrics["rollback_count"] > 0:
        actions.append(
            f"Treat the {counted('main-branch rollback', main_metrics['rollback_count'])} as a release-review trigger, not a one-off — capture the contributing CI signal before the next deploy."
        )
    if failure_stage != "none":
        actions.append(
            f"Stabilize the `{failure_stage}` stage on main first; that is where deployment confidence is actually being eroded."
        )
    if service != "none":
        actions.append(
            f"Assign a platform owner for `{service}` — failures are concentrating there and the service-level table makes the gap visible."
        )
    if retry_stage != "none" and retry_stage != failure_stage:
        actions.append(
            f"Track `{retry_stage}` retries separately from failures; passed-with-retries hides developer-time cost behind eventual green."
        )
    if overall_metrics["flake_rate"] > 0.20:
        actions.append(
            "Surface flake rate (passed-with-retries) on the platform dashboard alongside pass rate so devex friction stops being invisible."
        )
    if main_metrics["long_tail_duration"] > 40:
        actions.append(
            f"Flag the long-tail duration ({main_metrics['long_tail_duration']:.1f} min p90) as a developer-friction incident on main; pass/fail alone hides it."
        )

    return actions or ["No urgent actions triggered by the current sample dataset."]


def render_service_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Service | Runs | Pass rate | Retry rate | Median min | Rollbacks |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['service']}` | {row['runs']} | {row['pass_rate']:.0%} | "
            f"{row['retry_rate']:.0%} | {row['median_duration']:.1f} | {row['rollbacks']} |"
        )
    return lines


def render_metrics_block(label: str, metrics: dict, risk_label: str) -> list[str]:
    return [
        f"### {label}",
        "",
        f"- Runs analyzed: {metrics['total']}",
        f"- Pass rate: {metrics['pass_rate']:.0%}",
        f"- Retry rate: {metrics['retry_rate']:.0%}",
        f"- Flake rate (passed-with-retries): {metrics['flake_rate']:.0%}",
        f"- Retry events: {metrics['retry_events']}",
        f"- Retry-touched minutes: {metrics['retry_touched_minutes']:.1f}",
        f"- Median duration: {metrics['median_duration']:.1f} minutes",
        f"- Long-tail duration (p90): {metrics['long_tail_duration']:.1f} minutes",
        f"- Rollbacks: {metrics['rollback_count']}",
        f"- {risk_label}: {risk_level(metrics)}",
        "",
    ]


def render_report(runs: list[dict], main_metrics: dict, overall_metrics: dict, service_rows: list[dict]) -> str:
    failure_stage, failure_count = main_metrics["top_failure_stage"]
    retry_stage, retry_count = main_metrics["top_retry_stage"]
    failing_service, failing_count = main_metrics["top_failing_service"]
    retried_service, retried_count = overall_metrics["top_retried_service"]
    actions = recommended_actions(main_metrics, overall_metrics)
    release_decision, decision_reason = decision_strip(main_metrics)
    main_risk = risk_level(main_metrics)
    overall_risk = risk_level(overall_metrics)

    lines = [
        "# Wealthsimple CI/CD Release Confidence Brief",
        "",
        "Synthetic sample generated from a compact multi-service pipeline history. Designed to show how I would frame CI/CD reliability, developer friction, and service ownership in a platform review.",
        "",
        "## Decision Strip",
        "",
        f"**{release_decision}**: {decision_reason}",
        "",
        "## Best 30-Second Skim",
        "",
        f"- Release risk on `main` is **{main_risk}** because {main_metrics['retry_rate']:.0%} of runs required retries and the sample window includes {counted('rollback', main_metrics['rollback_count'])}.",
        f"- Developer friction risk across all runs is **{overall_risk}**; `{retried_service}` has the most retry-affected runs ({retried_count}) while `{failing_service}` is the clearest release-risk service on `main`.",
        f"- The fastest next action is to stabilize `{failure_stage}` on `main` and make a named owner accountable for `{failing_service}`.",
        "",
        "## What This Artifact Helps Decide",
        "",
        "| Question | Evidence in this packet | Why it matters |",
        "| --- | --- | --- |",
        "| Can we trust the next deploy? | Main-branch retry, rollback, and failure concentration | Separates release confidence from general CI noise |",
        "| Where is developer time being lost? | Retry events, retry-touched minutes, long-tail duration | Makes friction visible before it becomes team-normal |",
        "| Which service needs ownership attention first? | Per-service table sorted by pass rate | Turns platform pain into an accountable next action |",
        "",
        "## Sendable Summary",
        "",
        "This report separates the deployment-confidence story (`main`) from the developer-experience story (all runs). That split matters for a CI/CD and Developer Experience role: release gating, rollback prevention, and service ownership should be judged differently from day-to-day branch friction.",
        "",
        "## Headline Metrics",
        "",
        *render_metrics_block("Main branch (release confidence)", main_metrics, "Release confidence risk"),
        *render_metrics_block("All runs (developer experience)", overall_metrics, "Developer friction risk"),
        "## Developer Friction Tax",
        "",
        "| Signal | Main branch | All runs |",
        "| --- | ---: | ---: |",
        f"| Retry-affected runs | {main_metrics['retried_count']} | {overall_metrics['retried_count']} |",
        f"| Retry events | {main_metrics['retry_events']} | {overall_metrics['retry_events']} |",
        f"| Retry-touched minutes | {main_metrics['retry_touched_minutes']:.1f} | {overall_metrics['retry_touched_minutes']:.1f} |",
        f"| Long-tail duration p90 | {main_metrics['long_tail_duration']:.1f} min | {overall_metrics['long_tail_duration']:.1f} min |",
        "",
        "Retry-touched minutes are not presented as exact engineering hours lost. They are a conservative signal that the release path is spending meaningful time inside unstable or rerun-heavy work.",
        "",
        "## Per-Service Breakdown",
        "",
        "Sorted by pass rate ascending so the services that need attention surface first.",
        "",
        *render_service_table(service_rows),
        "",
        "## Risk Signals (Main Branch)",
        "",
        f"- Failure concentration: `{failure_stage}` is the top failure stage on main ({counted('run', failure_count)}).",
        f"- Retry concentration: `{retry_stage}` is the top retry stage on main ({counted('run', retry_count)}); passed-with-retries still costs developer time.",
        f"- Service concentration: `{failing_service}` accounts for {counted('failed run', failing_count)} on main.",
        f"- Rollback signal: {counted('main-branch rollback', main_metrics['rollback_count'])} in this window.",
        "",
        "## Recommended Actions",
        "",
        *[f"{idx}. {action}" for idx, action in enumerate(actions, start=1)],
        "",
        "## Honest Scope",
        "",
        "This is a synthetic sample, not a claim about Wealthsimple's actual pipeline data, tooling mix, or service topology. The value is in the decision framing: separating release confidence from developer friction, showing where ownership should be made explicit, and turning CI noise into a short operating brief.",
        "",
        "## Developer Experience Impact",
        "",
        "This is the decision-making layer a CI/CD and Developer Experience role should produce: where failures concentrate on the release-critical branch, which retries waste developer time on every branch, which services need an owner, and what action would reduce friction before the next deploy. The point is not to mimic a full platform; it is to make the platform conversation actionable in one short readout.",
        "",
    ]
    return "\n".join(lines)


def render_html(main_metrics: dict, overall_metrics: dict, service_rows: list[dict]) -> str:
    release_decision, decision_reason = decision_strip(main_metrics)
    main_risk = risk_level(main_metrics)
    overall_risk = risk_level(overall_metrics)

    risk_theme = {
        "High": ("#b42318", "#fef3f2"),
        "Medium": ("#b54708", "#fffaeb"),
        "Low": ("#067647", "#ecfdf3"),
    }
    accent, accent_bg = risk_theme[main_risk]

    def service_rows_html() -> str:
        rows = []
        for row in service_rows:
            rows.append(
                "<tr>"
                f"<td><code>{row['service']}</code></td>"
                f"<td>{row['runs']}</td>"
                f"<td>{row['pass_rate']:.0%}</td>"
                f"<td>{row['retry_rate']:.0%}</td>"
                f"<td>{row['median_duration']:.1f} min</td>"
                f"<td>{row['rollbacks']}</td>"
                "</tr>"
            )
        return "\n".join(rows)

    def action_rows() -> str:
        return "\n".join(
            f"<li>{action}</li>" for action in recommended_actions(main_metrics, overall_metrics)
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CI/CD Release Confidence Brief</title>
  <style>
    :root {{
      --paper: #fcfbf7;
      --ink: #161616;
      --muted: #667085;
      --line: #d0d5dd;
      --panel: #ffffff;
      --accent: {accent};
      --accent-bg: {accent_bg};
      --link: #175cd3;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--paper);
      color: var(--ink);
      line-height: 1.45;
    }}
    .wrap {{
      max-width: 980px;
      margin: 0 auto;
      padding: 32px 20px 64px;
    }}
    .eyebrow {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 10px;
      font-weight: 600;
    }}
    h1 {{
      margin: 0;
      font-size: 30px;
      line-height: 1.1;
      letter-spacing: -0.03em;
    }}
    .subtitle {{
      max-width: 760px;
      margin-top: 12px;
      color: #344054;
      font-size: 15px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 20px;
      margin-top: 18px;
    }}
    .decision {{
      border-left: 5px solid var(--accent);
      background: var(--accent-bg);
    }}
    .decision-label {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 8px;
      font-weight: 600;
    }}
    .decision-value {{
      font-size: 28px;
      font-weight: 700;
      color: var(--accent);
      margin-bottom: 8px;
    }}
    h2 {{
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin: 0 0 12px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 12px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: #fff;
    }}
    .metric-label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 6px;
      font-weight: 600;
    }}
    .metric-value {{
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.03em;
    }}
    .metric-note {{
      font-size: 12px;
      color: #475467;
      margin-top: 4px;
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
    }}
    li + li {{
      margin-top: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      text-align: left;
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
    }}
    th {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      font-weight: 600;
    }}
    code {{
      font-family: "IBM Plex Mono", "SFMono-Regular", Menlo, monospace;
      font-size: 12px;
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      margin-top: 14px;
      font-size: 14px;
    }}
    a {{
      color: var(--link);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .scope {{
      color: #475467;
      font-size: 14px;
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <div class="eyebrow">Public Demo · CI/CD · Developer Experience</div>
    <h1>CI/CD Release Confidence Brief</h1>
    <p class="subtitle">A compact platform-engineering sample that separates release confidence on <code>main</code> from developer friction across all runs, then turns that split into an ownership and release-decision artifact.</p>

    <section class="panel decision">
      <div class="decision-label">Decision Strip</div>
      <div class="decision-value">{release_decision}</div>
      <div>{decision_reason}</div>
    </section>

    <section class="panel">
      <h2>Best 30-Second Skim</h2>
      <ul>
        <li>Release risk on <code>main</code> is <strong>{main_risk}</strong> because {main_metrics['retry_rate']:.0%} of runs required retries and the sample window includes {counted('rollback', main_metrics['rollback_count'])}.</li>
        <li>Developer friction risk across all runs is <strong>{overall_risk}</strong>; <code>{overall_metrics['top_retried_service'][0]}</code> has the most retry-affected runs ({overall_metrics['top_retried_service'][1]}).</li>
        <li>The fastest next action is to stabilize <code>{main_metrics['top_failure_stage'][0]}</code> on <code>main</code> and make a named owner accountable for <code>{main_metrics['top_failing_service'][0]}</code>.</li>
      </ul>
    </section>

    <section class="panel">
      <h2>Headline Metrics</h2>
      <div class="grid">
        <div class="metric">
          <div class="metric-label">Main Branch Risk</div>
          <div class="metric-value">{main_risk}</div>
          <div class="metric-note">{main_metrics['total']} runs · {main_metrics['retry_rate']:.0%} retries · {counted('rollback', main_metrics['rollback_count'])}</div>
        </div>
        <div class="metric">
          <div class="metric-label">Developer Friction Risk</div>
          <div class="metric-value">{overall_risk}</div>
          <div class="metric-note">{overall_metrics['total']} runs · {overall_metrics['retry_events']} retry events · {overall_metrics['retry_touched_minutes']:.1f} retry-touched minutes</div>
        </div>
        <div class="metric">
          <div class="metric-label">Failure Concentration</div>
          <div class="metric-value"><code>{main_metrics['top_failure_stage'][0]}</code></div>
          <div class="metric-note">{counted('run', main_metrics['top_failure_stage'][1])} on main</div>
        </div>
        <div class="metric">
          <div class="metric-label">Service To Triage First</div>
          <div class="metric-value"><code>{main_metrics['top_failing_service'][0]}</code></div>
          <div class="metric-note">{counted('failed run', main_metrics['top_failing_service'][1])} on main</div>
        </div>
      </div>
    </section>

    <section class="panel">
      <h2>Developer Friction Tax</h2>
      <table>
        <thead>
          <tr>
            <th>Signal</th>
            <th>Main branch</th>
            <th>All runs</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>Retry-affected runs</td><td>{main_metrics['retried_count']}</td><td>{overall_metrics['retried_count']}</td></tr>
          <tr><td>Retry events</td><td>{main_metrics['retry_events']}</td><td>{overall_metrics['retry_events']}</td></tr>
          <tr><td>Retry-touched minutes</td><td>{main_metrics['retry_touched_minutes']:.1f}</td><td>{overall_metrics['retry_touched_minutes']:.1f}</td></tr>
          <tr><td>Long-tail duration p90</td><td>{main_metrics['long_tail_duration']:.1f} min</td><td>{overall_metrics['long_tail_duration']:.1f} min</td></tr>
        </tbody>
      </table>
    </section>

    <section class="panel">
      <h2>Per-Service Breakdown</h2>
      <table>
        <thead>
          <tr>
            <th>Service</th>
            <th>Runs</th>
            <th>Pass rate</th>
            <th>Retry rate</th>
            <th>Median</th>
            <th>Rollbacks</th>
          </tr>
        </thead>
        <tbody>
          {service_rows_html()}
        </tbody>
      </table>
    </section>

    <section class="panel">
      <h2>Recommended Actions</h2>
      <ul>
        {action_rows()}
      </ul>
    </section>

    <section class="panel">
      <h2>Inspect Or Run</h2>
      <div class="links">
        <a href="./devex_report.md">Open generated report</a>
        <a href="https://github.com/isaac-maya/ci-cd-devex-dashboard">View source repo</a>
      </div>
      <p class="scope">Scope note: this is a synthetic sample, not a claim about Wealthsimple's actual pipeline topology or tooling. The value is in the decision framing, service ownership signals, and the separation between release confidence and developer friction.</p>
    </section>
  </main>
</body>
</html>
"""


def main() -> None:
    runs = load_runs()
    main_runs = [run for run in runs if run["branch"] == "main"]
    main_metrics = summarize(main_runs)
    overall_metrics = summarize(runs)
    service_rows = per_service(runs)
    REPORT_PATH.write_text(
        render_report(runs, main_metrics, overall_metrics, service_rows),
        encoding="utf-8",
    )
    HTML_PATH.write_text(
        render_html(main_metrics, overall_metrics, service_rows),
        encoding="utf-8",
    )
    print(
        f"Analyzed {overall_metrics['total']} runs ({main_metrics['total']} on main). "
        f"Main-branch risk: {risk_level(main_metrics)}; overall risk: {risk_level(overall_metrics)}."
    )


if __name__ == "__main__":
    main()
