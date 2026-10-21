"""Offline evaluation checks positive scenario scopes without claiming precision."""

import json
from pathlib import Path

import pytest

from app.analytics.evaluate import evaluate_report, main


def answer_key() -> dict[str, object]:
    """Provide the five public scenario labels and their inclusive truth periods."""
    return {
        "schema_version": 1,
        "anomalies": [
            {"id": "A01", "period": "2026-09"},
            {"id": "A02", "period": "2026-08"},
            {"id": "A03", "period": "2026-07"},
            {"id": "A04", "period": "2026-09-10/2026-09-19", "product_id": 1},
            {"id": "A05", "period": "2026-06", "order_item_id": 999},
        ],
    }


def evidence() -> list[dict[str, object]]:
    """Describe findings with correct scopes and observed-versus-baseline direction."""
    return [
        {
            "id": "volume",
            "kind": "volume_shift",
            "entity": {"category": "pumps"},
            "period": {"start": "2026-09-01", "end": "2026-10-01"},
            "observed": "10",
            "baseline": "100",
        },
        {
            "id": "discount",
            "kind": "discount_shift",
            "entity": {"category": "valves", "region": "South"},
            "period": {"start": "2026-08-01", "end": "2026-09-01"},
            "observed": "0.6",
            "baseline": "0.1",
        },
        {
            "id": "refund",
            "kind": "refund_shift",
            "entity": {"category": "compressors"},
            "period": {"start": "2026-07-01", "end": "2026-08-01"},
            "observed": "0.5",
            "baseline": "0.01",
        },
        {
            "id": "stock",
            "kind": "stockout",
            "entity": {"product_id": 1},
            "period": {"start": "2026-09-09", "end": "2026-09-21"},
        },
        {
            "id": "line",
            "kind": "quantity_outlier",
            "entity": {"item_id": 999},
            "period": {"start": "2026-06-15", "end": "2026-06-16"},
        },
    ]


def test_empty_findings_report_zero_positive_coverage() -> None:
    """Missing evidence lists all five missed labels without false-positive claims."""
    result = evaluate_report({"schema_version": 1, "findings": []}, answer_key())

    assert result["total_scenarios"] == 5
    assert result["detected_scenarios"] == []
    assert result["missed_scenarios"] == ["A01", "A02", "A03", "A04", "A05"]
    assert result["coverage_percent"] == "0"
    assert "precision" in str(result["note"])


def test_correct_scopes_and_directions_cover_all_five_scenarios() -> None:
    """Only label-matching evidence contributes to positive scenario coverage."""
    result = evaluate_report(
        {"schema_version": 1, "findings": evidence()}, answer_key()
    )

    assert result["coverage_percent"] == "100"
    assert result["detected_scenarios"] == ["A01", "A02", "A03", "A04", "A05"]
    assert result["missed_scenarios"] == []
    assert result["matches"] == {
        "A01": ["volume"],
        "A02": ["discount"],
        "A03": ["refund"],
        "A04": ["stock"],
        "A05": ["line"],
    }


@pytest.mark.parametrize("end", ["2026-09-01", "2026-08-01"])
def test_empty_or_reversed_finding_period_is_rejected(end: str) -> None:
    """Malformed saved evidence cannot claim coverage using an invalid interval."""
    row = evidence()[0]
    row["period"] = {"start": "2026-09-01", "end": end}
    with pytest.raises(ValueError, match="increasing"):
        evaluate_report({"schema_version": 1, "findings": [row]}, answer_key())


def test_partial_month_cannot_cover_a_monthly_scenario() -> None:
    """A short exposure must not be scored as a whole-month volume drop."""
    row = evidence()[0]
    row["period"] = {"start": "2026-09-15", "end": "2026-10-01"}
    result = evaluate_report({"schema_version": 1, "findings": [row]}, answer_key())
    assert result["coverage_percent"] == "0"


def test_wrong_direction_month_entity_and_model_kind_do_not_match() -> None:
    """Temporal proximity alone cannot make unrelated or opposite findings hits."""
    rows = evidence()
    rows[0]["observed"] = "200"
    rows[1]["entity"] = {"category": "valves", "region": "North"}
    rows[2]["period"] = {"start": "2026-06-01", "end": "2026-07-01"}
    rows[3]["entity"] = {"product_id": 2}
    rows[4]["entity"] = {"item_id": 998}
    model_signal = dict(evidence()[0], id="model", kind="multivariate")

    result = evaluate_report(
        {"schema_version": 1, "findings": rows + [model_signal]}, answer_key()
    )

    assert result["coverage_percent"] == "0"
    assert result["detected_scenarios"] == []


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("2026-09-10", "2026-09-20", "20"),
        ("2026-09-10", "2026-09-19", "0"),
        ("2026-09-11", "2026-09-20", "0"),
    ],
)
def test_stock_evidence_must_cover_every_truth_day(
    start: str, end: str, expected: str
) -> None:
    """The answer key's last stock day is inclusive; finding end is exclusive."""
    stock = evidence()[3]
    stock["period"] = {"start": start, "end": end}

    result = evaluate_report({"schema_version": 1, "findings": [stock]}, answer_key())

    assert result["coverage_percent"] == expected


@pytest.mark.parametrize("ids", [["A01", "A02", "A03", "A04", "A06"], ["A01"] * 5])
def test_unknown_or_duplicate_answer_labels_are_rejected(ids: list[str]) -> None:
    """An altered or incomplete answer key cannot produce a misleading denominator."""
    truth = {"schema_version": 1, "anomalies": [{"id": ident} for ident in ids]}

    with pytest.raises(ValueError, match="five unique"):
        evaluate_report({"schema_version": 1, "findings": []}, truth)


@pytest.mark.parametrize(
    "report",
    [
        {"schema_version": 2, "findings": []},
        {"schema_version": 1, "findings": "invalid"},
        {"schema_version": 1, "findings": ["credential-do-not-print"]},
        {"schema_version": 1, "findings": [{"entity": {}, "period": {}}]},
    ],
)
def test_evaluation_cli_sanitizes_malformed_input(
    report: dict[str, object],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bad JSON structures return one safe error without a traceback or source data."""
    report_path = tmp_path / "report.json"
    truth_path = tmp_path / "truth.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    truth_path.write_text(json.dumps(answer_key()), encoding="utf-8")

    assert main(["--report", str(report_path), "--ground-truth", str(truth_path)]) == 1

    captured = capsys.readouterr()
    assert not captured.out
    assert json.loads(captured.err) == {
        "error": "Invalid report or evaluation answer key."
    }
    assert "credential-do-not-print" not in captured.err
