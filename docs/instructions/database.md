# Database

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Start PostgreSQL, apply migrations, load the sample data, run SQL by hand, and change the schema safely. The full explanation in Russian is in the [Stage 02 guide](../STAGE_02.md).

## Services

`compose.yaml` defines two PostgreSQL 17 services on the same digest-pinned image:

| Service | Purpose | Port | Database | Storage |
| --- | --- | --- | --- | --- |
| `db` | Development | `127.0.0.1:5436` | `industrialflow` | Volume `postgres_data`, survives `docker compose down` |
| `db-test` | Integration tests (profile `test`) | `127.0.0.1:5437` | `industrialflow_test` | `tmpfs`, gone when stopped |

Credentials and ports come from `.env` (copy `.env.example`). The development password is for local use only.

## Start and migrate

```bash
docker compose up --detach --wait db
uv run alembic upgrade head
```

`--wait` returns when the healthcheck (`pg_isready`) passes. The current migration chain creates six domain tables, `reports`, `agent_runs` and `alembic_version`. Verify:

```bash
uv run alembic current
```

Expected output: `0004 (head)`. Migration `0001` creates the six domain tables; `0002` (Stage 06) adds the `reports` table for saved API reports; `0003` (Stage 07) adds `agent_runs`, the AI analyst's investigation history; `0004` (Stage 09) adds `api_tokens` (hashes, roles, expiry, revocation). `curl http://127.0.0.1:8000/ready` returns `{"status":"ready","revision":"0004"}` while the API is running.

## Sample data

```bash
uv run python -m app.db.sample
```

Loads 2 customers, 3 products, 5 orders (3 paid, 1 cancelled, 1 pending), 2 refunds and 3 inventory snapshots, only if `customers` is empty. The expected answers are listed in `app/db/sample.py`. It remains a separate fixture for the Stage 02 SQL exercise. The Stage 03 demo loader refuses any existing domain rows, so choose the sample or the full demo before loading into a database.

## Full demo dataset and quality

```bash
uv run python -m app.data.generate --output data/demo --seed 42 --orders 20000
uv run python -m app.data.load --input data/demo
uv run python -m app.data.quality
```

Generation creates six CSV files, a manifest and evaluation ground truth, without using a database. Loading validates the bundle and uses one transaction against `DATABASE_URL`, requiring all six domain tables to be empty. It provides no reset option. Data quality checks only read the database: orders without lines, excessive aggregate refunds, refunds on unpaid orders and refunds before payment. See [Demo data](demo-data.md) and the Russian [Stage 03 guide](../STAGE_03.md).

## Run SQL

Interactive psql:

```bash
docker compose exec db psql -U analyst -d industrialflow
```

Useful psql commands: `\dt` (tables), `\d orders` (columns, constraints, indexes), `\q` (quit).

Run a query file from `sql/`:

```bash
docker compose exec -T db psql -U analyst -d industrialflow < sql/02_net_revenue_by_month.sql
```

| File | Shows |
| --- | --- |
| `01_paid_order_totals.sql` | Totals of paid orders: `JOIN`, `GROUP BY` |
| `02_net_revenue_by_month.sql` | Paid sales minus refunds per Moscow month: CTE, `FULL OUTER JOIN` |
| `03_sales_by_category.sql` | Sales and share per category: window function `SUM(...) OVER ()` |
| `04_double_counting.sql` | How joining refunds inflates sales: 338 000.00 instead of 328 000.00 |

The same files are executed by `tests/integration/test_queries.py` and compared with hand-computed results.

## Change the schema

1. Edit the models in `app/db/models.py`.
2. Generate a migration and **read it**:

   ```bash
   uv run alembic revision --autogenerate --rev-id 0005 -m "Describe the change"
   ```

3. Apply it and check that models and migrations match:

   ```bash
   uv run alembic upgrade head
   uv run alembic check
   ```

4. Check the rollback: `uv run alembic downgrade -1`, then `upgrade head` again.

Never edit a migration that has already been applied anywhere; add a new one instead. To preview SQL without running it: `uv run alembic upgrade head --sql`.

## Stop and reset

```bash
docker compose stop
```

Stops containers and keeps data. `docker compose down` removes containers and keeps the volume. **`docker compose down -v` deletes the volume and all development data.** To rebuild the schema from scratch without deleting the volume:

```bash
uv run alembic downgrade base
uv run alembic upgrade head
```

`downgrade base` drops all tables together with their rows.
