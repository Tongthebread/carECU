# DriveEval AI development plan

Preserve the existing automotiveECU project and build on the existing uncommitted MVP.

1. **Simulation correctness**: six distinct deterministic scenarios, environmental effects,
   configurable evaluation rules, reproducibility and safety regression tests.
2. **Backend workflow**: persisted queued/running/completed/failed jobs, configuration snapshots,
   metrics and comparison endpoints, offline and optional LLM reports, export, migrations,
   integration boundaries and failure handling.
3. **Dashboard**: scenario and algorithm creation, environment configuration, status polling,
   run inspection, telemetry, comparison, failure analysis and downloadable reports/results.
4. **Delivery**: PostgreSQL Compose, SQLite local workflow, CI, sample data, architecture,
   limitations and exact run/test instructions.

Each milestone updates README and runs its relevant checks before the next begins.
The source request ends at the dashboard Overview / Pass rate bullet; the explicit
MVP workflow supplies the rest of the dashboard requirements.

Design decisions: single API worker with an in-process executor for the portfolio deployment;
SQLAlchemy stores telemetry and evaluation as run-owned JSON documents (logical entities),
keeping each completed result atomic. No vehicle validation or release certification is claimed.
CARLA remains an explicitly unavailable adapter until a supported runtime is supplied.

## Completion

All four milestones are implemented and documented in README. Validation includes
24 backend tests on SQLite and PostgreSQL, two dashboard workflow tests, production
builds, container health, 18-run live campaigns and a Chrome walkthrough. See
[validation record](VALIDATION.md) for service-integration limits.
