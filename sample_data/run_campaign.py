"""Seed a live local API with an 18-run campaign and verify terminal job states."""
import json
import os
import time
import urllib.request

base = os.getenv("DRIVEEVAL_API_URL", "http://127.0.0.1:8000")


def request(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    with urllib.request.urlopen(urllib.request.Request(base + path, data=data,
                                headers={"Content-Type": "application/json"}), timeout=30) as response:
        return json.load(response)


if __name__ == "__main__":
    scenarios = request('/api/scenarios')
    algorithms = request('/api/algorithms')
    selected_scenarios = {s['scenario_type']: s for s in reversed(scenarios)}
    selected_algorithms = {}
    for algorithm in algorithms:
        selected_algorithms.setdefault(algorithm['version'], algorithm)
    ids = [request('/api/runs', {'scenario_id': s['id'], 'algorithm_id': a['id']})['id']
           for s in selected_scenarios.values() for a in selected_algorithms.values()]
    deadline = time.monotonic() + 60
    pending = set(ids)
    while pending and time.monotonic() < deadline:
        for run_id in list(pending):
            run = request(f'/api/runs/{run_id}')
            if run['status'] in {'completed', 'failed'}:
                pending.remove(run_id)
                outcome = 'PASS' if run['metrics'].get('passed') else 'FAIL'
                print(f"Run {run_id}: {run['status']} / {outcome}")
        if pending:
            time.sleep(0.2)
    if pending:
        raise SystemExit(f'Timed out waiting for runs: {sorted(pending)}')
    print(json.dumps(request('/api/overview'), indent=2))
