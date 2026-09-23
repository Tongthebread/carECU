# DriveEval AI

Cloud-ready ADAS simulation, benchmarking and algorithm evaluation portfolio project.
Configure driving scenarios, execute reproducible tests, inspect telemetry and failures,
compare algorithm versions, generate evaluation reports and export evidence.

**All default telemetry is synthetic.** The deterministic mock requires no CARLA, cloud
account or AI API key. It does not validate real vehicle behavior or certify release safety.

## Quick start — Docker / PostgreSQL

```bash
docker compose up --build -d
```

Open **http://localhost:5173**. API documentation: **http://localhost:8000/docs**.
Compose creates PostgreSQL, applies Alembic migrations, seeds six scenarios and three
algorithm profiles, and serves the dashboard through nginx with an API proxy.
`docker compose down` stops services and retains database data.

If ports are occupied, set `DRIVEEVAL_API_PORT` and `DRIVEEVAL_DASHBOARD_PORT` when running
Compose. Use either Docker or local development on the default ports.

## Local development — SQLite

Python 3.12+ and Node.js 22.12+ are required. Docker and CI target Python 3.12;
local checks also run on Python 3.13.

```bash
make setup                  # creates .venv, installs backend and frontend dependencies
make backend-run            # terminal 1: API on :8000; optional root .env is loaded
make frontend-run           # terminal 2: dashboard on :5173
```

SQLite persists in `backend/driveeval.db`. Migrations run at API startup. Existing MVP
records are preserved. Copy `.env.example` to `.env` if configuration is needed; no keys
are needed for the default workflow. For a specific interpreter: `make setup PYTHON=python3.12`.

## Try the full workflow

1. Open **Scenario lab**. Pick a seeded scenario or save a new one using the environment
   and rules shown above the save form.
2. Choose `baseline-v1`, `cautious-v2` or `aggressive-v3`, or register a tuned profile with
   a Git/artifact identifier. Set speed, weather, fog, traffic, noise, delay and seed.
3. Start a simulation. **Run explorer** updates the job status and shows pass/fail metrics,
   speed/gap/lane charts, saved configuration and JSON/CSV downloads.
4. Run another algorithm with the same scenario and seed. Select both rows and use
   **Compare**. Mismatched configurations produce a warning.
5. Open **Reports** to inspect failure timestamps, generate offline analysis or request
   the configured AI provider, and download the report as JSON.

With the API running, `make demo` executes an 18-run campaign across six scenario families
and three profiles. Repeating this command adds new runs; it never removes existing data.

## Tests and verification

```bash
make backend-test           # isolated temporary SQLite database; preserves your local DB
make frontend-test          # DOM workflow and API-outage tests
make frontend-build         # strict TypeScript check and production bundle
```

The backend tests cover all six scenarios, determinism, environmental effects, pass/fail
rules, asynchronous jobs, restart recovery, comparisons, exports, migrations and report
provider fallback. Frontend tests cover scenario configuration → two algorithms → comparison
→ report, plus unavailable-API behavior. Chart code loads separately from the main bundle.

CI additionally tests PostgreSQL and container health. The [validation record](docs/VALIDATION.md)
distinguishes checks run locally from configured CI checks.

## API

FastAPI exposes interactive OpenAPI docs at `/docs` and schema at `/openapi.json`.

| Operation | Endpoint |
| --- | --- |
| Database health | `GET /health` |
| Overview statistics | `GET /api/overview` |
| Create/list scenarios | `POST`, `GET /api/scenarios` |
| Register/list algorithms | `POST`, `GET /api/algorithms` |
| Queue simulation (202) | `POST /api/runs` |
| Run history | `GET /api/runs?limit=100&offset=0` |
| Details/status/telemetry/metrics | `GET /api/runs/{id}` and `/status`, `/telemetry`, `/metrics` |
| Compare 2–10 runs | `GET /api/compare?run_ids=1,2` |
| Read/generate report | `GET`, `POST /api/runs/{id}/report` |
| Download evidence | `GET /api/runs/{id}/export?format=json` or `csv` |

Example job body: `{"scenario_id":1,"algorithm_id":2}`. An optional `configuration` replaces
the scenario configuration with a fully defaulted, validated configuration. Job states are
`queued`, `running`, `completed`, `failed`; completed does not imply a passing evaluation.
Results requested before completion return 409; missing records return 404; invalid inputs
return 422. The deprecated two-ID start URL remains available but now also returns 202.

## Optional integrations

- **AI analysis:** set `OPENAI_BASE_URL` (including the API prefix, typically `/v1`),
  `OPENAI_MODEL`, and optionally `OPENAI_API_KEY`. Select AI mode when generating a report.
  The provider receives saved configuration and metrics. No provider means offline analysis;
  provider errors also fall back. Keys never enter the frontend bundle.
- **MLflow:** install `.venv/bin/python -m pip install -e 'backend[tracking]'` and set
  `MLFLOW_TRACKING_URI`. Completed-run scalar metrics and identifying parameters are logged.
- **S3-compatible storage:** install `.venv/bin/python -m pip install -e 'backend[storage]'`,
  set `S3_BUCKET`, optionally `S3_ENDPOINT_URL`, and standard AWS credentials. Results are
  stored as `runs/{id}.json`. Local results remain available when the sink fails.
- **CARLA:** an explicit adapter skeleton and [setup/implementation guide](docs/CARLA.md).
  No CARLA run is advertised or required. A real adapter awaits a supported CARLA runtime.

Optional sinks are supported by source installs; add the extras and corresponding environment
variables to your API image/Compose configuration when deploying those integrations.

## Architecture and milestone record

React/TypeScript/Vite/Recharts → FastAPI → SQLAlchemy → SQLite or PostgreSQL. A single worker
runs a simulator adapter, metrics/rules engine and reporting services. Telemetry and evaluation
are typed run-owned JSON documents committed atomically with each completed run. Run snapshots
retain configuration, rules, seed, artifact and simulator provenance.

Run **one API process/replica**: the portfolio executor is in-process, and restart recovery
marks interrupted jobs failed. Multi-worker scaling needs a durable queue and job leases.
The local application has no authentication; public deployment requires access controls.
See [architecture and metric definitions](docs/ARCHITECTURE.md) for assumptions and limits.

| Milestone | Delivered | Validation at completion |
| --- | --- | --- |
| 1. Simulator | Six distinct scenarios, environmental effects, tuning, configurable rules | 17 simulator tests |
| 2. API workflow | Persisted jobs, snapshots, migrations, reports, comparisons and exports | 21 backend tests |
| 3. Dashboard | Five pages covering the complete MVP workflow | TypeScript/Vite build; workflow tests; Chrome walkthrough |
| 4. Delivery | PostgreSQL Compose, pinned dependencies, CI, sample campaign, documentation | See validation record |

[Initial development plan](docs/DEVELOPMENT_PLAN.md). The pre-existing `automotiveECU/`
project remains separate and unchanged. The supplied specification ended at the dashboard
Overview “Pass rate” bullet; the preceding MVP workflow defined the rest of the delivered UI.
