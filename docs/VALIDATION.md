# Validation record

Checks executed during implementation:

- 24 backend tests pass on local Python 3.13, using an isolated SQLite database.
- Two frontend workflow tests pass using Vitest/jsdom and a mocked API.
- TypeScript and Vite production build passes; main bundle and charts load separately.
- Backend (Python 3.12) and frontend Docker images build successfully.
- Live SQLite API: 18-run campaign completed with both passing and failing evaluations.
- Chrome: visually inspected overview, configured and executed a run, observed completed
  metrics and chart elements, generated and viewed an offline report.

- 24 backend tests pass in the Python 3.12 container with SQLite.
- 24 backend tests pass in the Python 3.12 container against a dedicated PostgreSQL database.
- Compose reports all three services healthy (PostgreSQL, API, nginx dashboard).
- An 18-run campaign through the nginx proxy and PostgreSQL completed: 11 passed the
  configured evaluation rules and 7 failed; no simulation jobs errored.
- Visually checked speed/gap curves, units, lane thresholds and tooltips in Chrome.
- `git diff --check` passes. CI workflows are configured; GitHub-hosted execution was
  not triggered during this session.

The verification Compose services were stopped after testing; the local development
API/dashboard remain available on ports 8000/5173. Verification volumes retain test data.

Limitations: no real CARLA runtime, LLM provider credentials, MLflow service or S3 service
was used. LLM success/error and sink-outage paths use test doubles. Frontend DOM tests do
not validate chart pixels; browser inspection provides a separate visual check.
