"""Check a running Docker stand end to end; standard library only.

    SMOKE_TOKEN=ida_… python3 scripts/smoke_stack.py \
        --api http://127.0.0.1:8001 --ui http://127.0.0.1:8502

Checks: health and readiness at the latest migration, 401 without a token,
the seed 42 September numbers through the API, a completed agent run with
verified evidence, the investigation in history and the Streamlit health
endpoint. The token comes from SMOKE_TOKEN, never from the command line.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

SEPTEMBER = (
    "start=2026-09-01&end=2026-10-01&compare_start=2026-08-01&compare_end=2026-09-01"
)
EXPECTED_NET = "466678757.35"
EXPECTED_CHANGE = ("-165497371.86", "-26.18")


def call(
    url: str, token: str | None = None, body: dict[str, Any] | None = None
) -> tuple[int, Any]:
    """One HTTP request; returns the status and the decoded JSON or text."""
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        payload, status = error.read(), error.code
    try:
        return status, json.loads(payload)
    except ValueError:
        return status, payload.decode("utf-8", "replace")


def check(condition: bool, message: str) -> None:
    """Print the step or stop with an error."""
    if not condition:
        print(f"FAIL {message}", file=sys.stderr)
        raise SystemExit(1)
    print(f"ok   {message}")


def main() -> int:
    """Run the checks in order; the first failure stops the script."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8001")
    parser.add_argument("--ui", default="http://127.0.0.1:8502")
    parser.add_argument("--revision", default="0004")
    args = parser.parse_args()
    token = os.environ.get("SMOKE_TOKEN", "").strip()
    check(bool(token), "SMOKE_TOKEN is set")

    status, body = call(f"{args.api}/health")
    check(status == 200 and body == {"status": "ok"}, "GET /health")
    status, body = call(f"{args.api}/ready")
    check(
        status == 200 and body.get("revision") == args.revision,
        f"GET /ready at revision {args.revision}",
    )
    status, _ = call(f"{args.api}/api/reports")
    check(status == 401, "an /api route without a token answers 401")

    status, body = call(f"{args.api}/api/metrics/revenue?{SEPTEMBER}", token)
    change = body.get("comparison", {}).get("net_revenue", {}) if status == 200 else {}
    check(
        status == 200
        and body.get("net_revenue") == EXPECTED_NET
        and (change.get("absolute"), change.get("percent")) == EXPECTED_CHANGE,
        "September net revenue and change match the seed 42 dataset",
    )

    question = {"question": "Почему в сентябре снизилась выручка?"}
    status, run = call(f"{args.api}/api/agent/runs", token, question)
    cited = [
        item["value"]
        for fact in (run.get("report") or {}).get("facts", [])
        for item in fact["evidence"]
    ] if status == 201 else []  # fmt: skip
    check(
        status == 201
        and run.get("status") == "completed"
        and EXPECTED_CHANGE[0] in cited,
        "the agent answers with verified evidence",
    )
    status, history = call(f"{args.api}/api/agent/runs?limit=5", token)
    check(
        status == 200 and run["id"] in {item["id"] for item in history["items"]},
        "the investigation is stored in history",
    )

    status, body = call(f"{args.ui}/_stcore/health")
    check(status == 200 and body == "ok", "Streamlit health endpoint")
    print("Smoke check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
