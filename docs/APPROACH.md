# Approach

Living document. Sections are filled in as the stages that inform them are
completed; stages not yet built are marked as planned.

## Problem statement

IndustrialFlow, a fictional distributor of industrial equipment (pumps,
compressors, valves, sensors), keeps orders, customers, products, refunds and
inventory in a relational database. Managers ask questions such as *"Why did
revenue drop in September? Which categories and regions contributed most? Are
there anomalies?"* Answering them today means a manual round of SQL, a
spreadsheet and a written summary.

## Solution overview

An AI analyst that answers such questions by running a short investigation:
it selects data through a fixed set of analytics tools, performs exact
calculations, builds charts and writes a structured report that separates
facts, hypotheses and recommendations, each backed by tool results.

## Key principles

1. **Numbers come from code, not from the model.** Revenue, averages,
   comparisons and anomaly scores are computed by deterministic SQL or Python.
   The LLM interprets the question, chooses tools and explains results.
2. **Restricted tools before free-form SQL.** The agent calls parameterised,
   pre-defined queries. Text-to-SQL, if added, will use a read-only role,
   table allow-lists and timeouts.
3. **Exact money arithmetic.** PostgreSQL `NUMERIC` and Python `Decimal`,
   never `float`.
4. **Reproducibility.** Locked dependencies, seeded demo data, and a
   `ground_truth.json` of injected anomalies used only for evaluation.
5. **Modular monolith.** One FastAPI service with clear internal layers;
   no microservices.

## Architecture

Planned components: Streamlit frontend → FastAPI backend → agent runtime →
analytics services and SQL repository → PostgreSQL. Detailed in
`ARCHITECTURE.md` once stage 06 is built.

**Implemented (stage 01):** FastAPI application with `GET /health`,
environment-based settings (`pydantic-settings`), pytest suite, Ruff, strict
mypy and a GitHub Actions workflow.

## Data model

Planned for stage 02: `customers`, `products`, `orders`, `order_items`,
`refunds`, `inventory_snapshots`.

Metric definitions fixed up front:

- Net revenue = paid sales − processed refunds; sales are recognised on the
  payment date, refunds in the period they are processed.
- Average order value = paid sales / paid orders, before refunds.
- Cancelled and unpaid orders are excluded. Amounts are in RUB, excluding VAT.

## Remaining sections

LLM models, agent tools, analytical methods, security, evaluation,
limitations, assumptions and future work are added in the stages that
implement them.
