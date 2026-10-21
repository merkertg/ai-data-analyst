"""Offline positive-scenario coverage; this module is never imported by detection."""

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path


def _matches(finding: dict[str, object], scenario: dict[str, object]) -> bool:
    """Match a known injected scope and direction, not statistical precision."""
    entity = finding.get("entity")
    bounds = finding.get("period")
    if not isinstance(entity, dict) or not isinstance(bounds, dict):
        raise ValueError("finding entity and period must be objects")
    start = date.fromisoformat(str(bounds["start"]))
    end = date.fromisoformat(str(bounds["end"]))
    if start >= end:
        raise ValueError("finding period must have an increasing exclusive end")
    label = str(scenario.get("period", ""))
    if "/" in label:
        first, last = label.split("/", 1)
        expected_start = date.fromisoformat(first)
        expected_end = date.fromisoformat(last) + timedelta(days=1)
    else:
        expected_start = date.fromisoformat(label + "-01")
        expected_end = (
            date(expected_start.year + 1, 1, 1)
            if expected_start.month == 12
            else date(expected_start.year, expected_start.month + 1, 1)
        )
    if start >= expected_end or end <= expected_start:
        return False
    kind = finding.get("kind")
    ident = scenario.get("id")
    if ident == "A04":
        return (
            kind == "stockout"
            and entity.get("product_id") == scenario.get("product_id")
            and start <= expected_start
            and end >= expected_end
        )
    if ident == "A05":
        return kind == "quantity_outlier" and entity.get("item_id") == scenario.get(
            "order_item_id"
        )
    rules = {
        "A01": ("volume_shift", "pumps", None, -1),
        "A02": ("discount_shift", "valves", "South", 1),
        "A03": ("refund_shift", "compressors", None, 1),
    }
    if ident not in rules:
        raise ValueError("unsupported scenario ID")
    expected_kind, category, region, direction = rules[str(ident)]
    if (
        kind != expected_kind
        or entity.get("category") != category
        or entity.get("region") != region
        or start != expected_start
        or end != expected_end
    ):
        return False
    observed = Decimal(str(finding["observed"]))
    baseline = Decimal(str(finding["baseline"]))
    if not observed.is_finite() or not baseline.is_finite():
        raise ValueError("evaluation requires finite evidence")
    return (observed - baseline) * direction > 0


def evaluate_report(report: object, ground_truth: object) -> dict[str, object]:
    """Measure coverage of five positive labels, not the false-positive rate."""
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("unsupported report")
    if not isinstance(ground_truth, dict) or ground_truth.get("schema_version") != 1:
        raise ValueError("unsupported ground truth")
    findings = report.get("findings")
    scenarios = ground_truth.get("anomalies")
    if not isinstance(findings, list) or not isinstance(scenarios, list):
        raise ValueError("findings and scenarios must be lists")
    if not scenarios or any(not isinstance(row, dict) for row in findings + scenarios):
        raise ValueError("expected scenario and finding objects")
    ids = [str(row.get("id", "")) for row in scenarios]
    if len(ids) != len(set(ids)) or set(ids) != {"A01", "A02", "A03", "A04", "A05"}:
        raise ValueError("expected five unique scenario labels")
    matches = {
        str(scenario["id"]): [
            str(finding["id"]) for finding in findings if _matches(finding, scenario)
        ]
        for scenario in scenarios
    }
    detected = [ident for ident, evidence in matches.items() if evidence]
    missed = [ident for ident, evidence in matches.items() if not evidence]
    return {
        "total_scenarios": len(scenarios),
        "detected_scenarios": detected,
        "missed_scenarios": missed,
        "coverage_percent": str(Decimal(len(detected) * 100) / len(scenarios)),
        "matches": matches,
        "note": (
            "Positive scenario coverage only; precision, causality and "
            "performance on unseen data are not measured."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Read an explicit saved report and answer key; do not connect to a database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        truth = json.loads(args.ground_truth.read_text(encoding="utf-8"))
        result = evaluate_report(report, truth)
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError):
        print(
            json.dumps({"error": "Invalid report or evaluation answer key."}),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
