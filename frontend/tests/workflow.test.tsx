import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../src/App';
import { defaults } from '../src/api';
import type { Run } from '../src/api';

// Charts are separately built by Vite; jsdom has no layout engine.
vi.mock('../src/TelemetryCharts', () => ({ default: () => <div>Telemetry charts</div> }));
let scenarios: any[];
let algorithms: any[];
let runs: Run[];
let calls: { path: string; body: any }[];

beforeEach(() => {
  calls = [];
  scenarios = [{ id: 1, name: 'Pedestrian crossing', scenario_type: 'pedestrian_crossing', configuration: structuredClone(defaults) }];
  algorithms = [{ id: 1, name: 'Baseline', version: 'baseline-v1' }, { id: 2, name: 'Cautious', version: 'cautious-v2' }];
  runs = [];
  vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
    const path = String(input);
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ path, body });
    let result: any;
    if (path === '/api/scenarios') {
      if (body) { result = { id: scenarios.length + 1, ...body }; scenarios.unshift(result); }
      else result = scenarios;
    } else if (path === '/api/algorithms') {
      if (body) { result = { id: algorithms.length + 1, ...body }; algorithms.push(result); }
      else result = algorithms;
    } else if (path === '/api/overview') result = { total_runs: runs.length, completed_runs: runs.length, pass_rate: 100, failed_evaluations: 0, active_jobs: 0 };
    else if (path.startsWith('/api/runs?')) result = runs;
    else if (path === '/api/runs' && body) {
      result = { id: runs.length + 1, scenario_id: body.scenario_id, algorithm_id: body.algorithm_id, status: 'completed', random_seed: body.configuration.random_seed,
        environment: body.configuration, snapshot: { scenario_name: scenarios.find(s => s.id === body.scenario_id).name, algorithm_name: algorithms.find(a => a.id === body.algorithm_id).name },
        metrics: { passed: true, violations: [], warnings: [], average_speed_kph: 20, failure_severity: 'none' }, telemetry: [], error_message: '' };
      runs.unshift(result);
    } else if (path.includes('/report')) result = { run_id: 1, headline: 'ADAS Evaluation Report', summary: 'Synthetic run passed.', recommendation: 'Review broader coverage.', generated_by: 'deterministic-analysis', failure_cases: [], limitations: 'Synthetic data.' };
    else if (path.startsWith('/api/compare')) result = { runs, comparable: true, deltas_from_first: [] };
    else if (/\/api\/runs\/\d+$/.test(path)) result = runs.find(r => r.id === Number(path.split('/').pop()));
    else throw new Error(`Unexpected request ${path}`);
    return { ok: true, json: async () => structuredClone(result) };
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test('configure scenario, execute two profiles, compare and generate report', async () => {
  const user = userEvent.setup(); render(<App />);
  await screen.findByText(/API CONNECTED/);
  await user.click(screen.getByRole('button', { name: 'Scenario lab', exact: true }));
  const speed = screen.getByLabelText('Ego speed · km/h');
  await user.clear(speed); await user.type(speed, '30');
  const seed = screen.getByLabelText('Random seed'); await user.clear(seed); await user.type(seed, '42');
  await user.type(screen.getByPlaceholderText('Wet road / pedestrian crossing'), 'City crossing');
  await user.click(screen.getByRole('button', { name: 'Save scenario' }));
  await screen.findByText('Created City crossing. Ready to simulate.');
  expect(scenarios[0].configuration.ego_speed_kph).toBe(30);
  expect(scenarios[0].configuration.random_seed).toBe(42);
  await user.click(screen.getByRole('button', { name: 'Start simulation' }));
  await screen.findByText('Telemetry charts');
  expect(runs[0].environment.ego_speed_kph).toBe(30);
  await user.click(screen.getByRole('button', { name: 'Scenario lab', exact: true }));
  await user.selectOptions(screen.getByLabelText('Algorithm', { exact: true }), '2');
  await user.click(screen.getByRole('button', { name: 'Start simulation' }));
  await waitFor(() => expect(runs).toHaveLength(2));
  await user.click(screen.getByRole('button', { name: 'Compare', exact: true }));
  await user.click(screen.getByLabelText('Compare run 1'));
  await user.click(screen.getByLabelText('Compare run 2'));
  await user.click(screen.getByRole('button', { name: 'Compare runs' }));
  await screen.findByText('Numeric changes relative to first run');
  expect(calls.some(c => c.path === '/api/compare?run_ids=1,2')).toBe(true);
  await user.click(screen.getByRole('button', { name: 'Reports', exact: true }));
  await user.click(screen.getByRole('button', { name: 'Generate report' }));
  await screen.findByText('Synthetic run passed.');
  expect(calls.find(c => c.path.endsWith('/report'))?.body.use_llm).toBe(false);
});

test('shows API errors and disables simulation while offline', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('API offline')));
  const user = userEvent.setup(); render(<App />);
  expect((await screen.findByRole('alert')).textContent).toContain('API offline');
  await user.click(screen.getByRole('button', { name: 'Scenario lab', exact: true }));
  expect((screen.getByRole('button', { name: 'Start simulation' }) as HTMLButtonElement).disabled).toBe(true);
});
