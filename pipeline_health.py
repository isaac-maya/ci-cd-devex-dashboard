"""Summarize CI/CD health into release-confidence and devex signals."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).parent
RUNS_PATH = ROOT / "sample_runs.json"
REPORT_PATH = ROOT / "devex_report.md"


def load_runs() -> list[dict]:
    return json.loads(RUNS_PATH.read_text(encoding="utf-8"))


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
    durations = [run["duration_min"] for run in runs]
    return {
        "total": total,
        "pass_rate": 1 - len(failed) / total,
        "retry_rate": len(retried) / total,
        "flake_rate": len(flaky) / total,
        "median_duration": statistics.median(durations),
        "long_tail_duration": percentile(durations, 90),
        "rollback_rate": len(rollbacks) / total,
        "rollback_count": len(rollbacks),
        "top_failure_stage": failure_stages.most_common(1)[0] if failure_stages else ("none", 0),
        "top_retry_stage": retry_stages.most_common(1)[0] if retry_stages else ("none", 0),
        "top_failing_service": failed_services.most_common(1)[0] if failed_services else ("none", 0),
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


def recommended_actions(main_metrics: dict, overall_metrics: dict) -> list[str]:
    failure_stage, _ = main_metrics["top_failure_stage"]
    retry_stage, _ = main_metrics["top_retry_stage"]
    service, _ = main_metrics["top_failing_service"]
    actions: list[str] = []

    if main_metrics["rollback_count"] > 0:
        actions.append(
            f"Treat the {main_metrics['rollback_count']} main-branch rollback(s) as a release-review trigger, not a one-off — capture the contributing CI signal before the next deploy."
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


def render_metrics_block(label: str, metrics: dict) -> list[str]:
    return [
        f"### {label}",
        "",
        f"- Runs analyzed: {metrics['total']}",
        f"- Pass rate: {metrics['pass_rate']:.0%}",
        f"- Retry rate: {metrics['retry_rate']:.0%}",
        f"- Flake rate (passed-with-retries): {metrics['flake_rate']:.0%}",
        f"- Median duration: {metrics['median_duration']:.1f} minutes",
        f"- Long-tail duration (p90): {metrics['long_tail_duration']:.1f} minutes",
        f"- Rollbacks: {metrics['rollback_count']}",
        f"- Release confidence risk: {risk_level(metrics)}",
        "",
    ]


def render_report(runs: list[dict], main_metrics: dict, overall_metrics: dict, service_rows: list[dict]) -> str:
    failure_stage, failure_count = main_metrics["top_failure_stage"]
    retry_stage, retry_count = main_metrics["top_retry_stage"]
    failing_service, failing_count = main_metrics["top_failing_service"]
    actions = recommended_actions(main_metrics, overall_metrics)

    lines = [
        "# CI/CD Developer Experience Health Report",
        "",
        "## Sendable Summary",
        "",
        "This report separates the deployment-confidence story (main branch) from the developer-experience story (all runs). Both views are needed: main-branch health is what governs release decisions; all-runs health is what governs developer friction.",
        "",
        "## Headline Metrics",
        "",
        *render_metrics_block("Main branch (release confidence)", main_metrics),
        *render_metrics_block("All runs (developer experience)", overall_metrics),
        "## Per-Service Breakdown",
        "",
        "Sorted by pass rate ascending so the services that need attention surface first.",
        "",
        *render_service_table(service_rows),
        "",
        "## Risk Signals (Main Branch)",
        "",
        f"- Failure concentration: `{failure_stage}` is the top failure stage on main ({failure_count} run(s)).",
        f"- Retry concentration: `{retry_stage}` is the top retry stage on main ({retry_count} run(s)); passed-with-retries still costs developer time.",
        f"- Service concentration: `{failing_service}` accounts for {failing_count} failed run(s) on main.",
        f"- Rollback signal: {main_metrics['rollback_count']} main-branch rollback(s) in this window.",
        "",
        "## Recommended Actions",
        "",
        *[f"{idx}. {action}" for idx, action in enumerate(actions, start=1)],
        "",
        "## Developer Experience Impact",
        "",
        "This is the decision-making layer a CI/CD and Developer Experience role should produce: where failures concentrate on the release-critical branch, which retries waste developer time on every branch, which services need an owner, and what action would reduce friction before the next deploy. The point is not to mimic a full platform; it is to make the platform conversation actionable in one short readout.",
        "",
    ]
    return "\n".join(lines)


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
    print(
        f"Analyzed {overall_metrics['total']} runs ({main_metrics['total']} on main). "
        f"Main-branch risk: {risk_level(main_metrics)}; overall risk: {risk_level(overall_metrics)}."
    )


if __name__ == "__main__":
    main()
