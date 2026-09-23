import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Activity, ArrowUpRight, Download, Play, Plus, ShieldCheck } from 'lucide-react';
import { defaults, downloadJson, downloadRun, post, request } from './api';
import type { Algorithm, Comparison, Configuration, Overview, Report, Rules, Run, Scenario } from './api';
import './styles.css';

const TelemetryCharts = lazy(() => import('./TelemetryCharts'));
const pages = ['Overview', 'Scenario lab', 'Run explorer', 'Compare', 'Reports'] as const;
type Page = typeof pages[number];
const types = ['pedestrian_crossing', 'emergency_braking', 'vehicle_cut_in', 'lane_departure', 'low_visibility_obstacle', 'stop_and_go'];
const human = (text: string) => text.replace(/_/g, ' ');
const value = (v: unknown) => v == null ? '—' : typeof v === 'number' ? Number(v.toFixed(3)).toString() : typeof v === 'boolean' ? (v ? 'Yes' : 'No') : Array.isArray(v) ? v.join(', ') || 'None' : String(v);
const metricLabels: Record<string, string> = { minimum_time_to_collision_s: 'Minimum TTC · s', minimum_following_distance_m: 'Minimum gap · m', maximum_deceleration_mps2: 'Max deceleration · m/s²', average_speed_kph: 'Average speed · km/h', collision_count: 'Collision count', collision_occurred: 'Collision occurred', maximum_lane_deviation_m: 'Maximum lane deviation · m', lane_departure_duration_s: 'Lane departure · s', successful_stop: 'Successful stop', reaction_time_s: 'Reaction time · s', scenario_completion_time_s: 'Elapsed simulation · s', speed_limit_violations: 'Speeding samples', passed: 'Passed', failure_severity: 'Severity' };
const configFields: [keyof Configuration, string, number, number, number][] = [
  ['ego_speed_kph', 'Ego speed · km/h', 0, 200, 1], ['speed_limit_kph', 'Speed limit · km/h', 1, 200, 1],
  ['obstacle_distance_m', 'Initial obstacle gap · m', 1, 500, 1], ['reaction_delay_s', 'Reaction delay · s', 0, 5, 0.1],
  ['rain_intensity', 'Rain intensity · 0–1', 0, 1, 0.05], ['fog_density', 'Fog density · 0–1', 0, 1, 0.05],
  ['traffic_density', 'Traffic density · 0–1', 0, 1, 0.05], ['sensor_noise', 'Sensor noise · 0–1', 0, 1, 0.01],
  ['random_seed', 'Random seed', 0, 2147483647, 1], ['duration_s', 'Duration · s', 1, 120, 0.1],
];
const ruleFields: [keyof Rules, string, number, number, number][] = [
  ['minimum_ttc_s', 'Critical TTC threshold · s', 0, 10, 0.1], ['maximum_lane_deviation_m', 'Max lane deviation · m', 0.1, 5, 0.1],
  ['lane_boundary_m', 'Lane boundary · m', 0.1, 5, 0.1], ['safe_stop_distance_m', 'Safe stop gap · m', 0, 20, 0.1], ['speed_tolerance_fraction', 'Speed tolerance · fraction', 0, 0.5, 0.01],
];

export default function App() {
  const [page, setPage] = useState<Page>('Overview');
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [algorithms, setAlgorithms] = useState<Algorithm[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [scenarioId, setScenarioId] = useState('');
  const [algorithmId, setAlgorithmId] = useState('');
  const [config, setConfig] = useState<Configuration>(structuredClone(defaults));
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selected, setSelected] = useState<Run | null>(null);
  const [compareIds, setCompareIds] = useState<number[]>([]);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [online, setOnline] = useState(false);
  const [filter, setFilter] = useState('all');
  const [offset, setOffset] = useState(0);
  const [useLlm, setUseLlm] = useState(false);

  const refresh = useCallback(async () => {
    const [s, a, r, o] = await Promise.all([request<Scenario[]>('/api/scenarios'), request<Algorithm[]>('/api/algorithms'), request<Run[]>(`/api/runs?limit=100&offset=${offset}`), request<Overview>('/api/overview')]);
    setScenarios(s); setAlgorithms(a); setRuns(r); setOverview(o); setOnline(true);
    return { s, a, r };
  }, [offset]);
  useEffect(() => {
    let mounted = true;
    refresh().then(({ s, a, r }) => {
      if (!mounted) return;
      setScenarioId(current => current || String(s[0]?.id ?? ''));
      setAlgorithmId(current => current || String(a[0]?.id ?? ''));
      setSelectedId(current => current ?? r[0]?.id ?? null);
    }).catch(e => { setOnline(false); setError(e.message); });
    const timer = setInterval(() => { refresh().catch(() => setOnline(false)); }, 2000);
    return () => { mounted = false; clearInterval(timer); };
  }, [refresh]);
  useEffect(() => {
    const scenario = scenarios.find(s => s.id === Number(scenarioId));
    if (scenario) setConfig({ ...defaults, ...scenario.configuration, rules: { ...defaults.rules, ...scenario.configuration.rules } });
  }, [scenarioId]);
  const selectedStatus = runs.find(r => r.id === selectedId)?.status;
  useEffect(() => {
    if (selectedId == null) return;
    let active = true;
    setReport(null); setSelected(null);
    request<Run>(`/api/runs/${selectedId}`).then(run => { if (active) setSelected(run); }).catch(e => setError(e.message));
    return () => { active = false; };
  }, [selectedId, selectedStatus]);

  async function act(task: () => Promise<void>) {
    setBusy(true); setError(''); setNotice('');
    try { await task(); } catch (e) { setError(e instanceof Error ? e.message : 'Operation failed'); }
    finally { setBusy(false); }
  }
  function startRun() {
    void act(async () => {
      const run = await post<Run>('/api/runs', { scenario_id: Number(scenarioId), algorithm_id: Number(algorithmId), configuration: config });
      setSelectedId(run.id); setPage('Run explorer'); setNotice(`Run #${run.id} submitted. Status updates automatically.`); await refresh();
    });
  }
  function createScenario(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    void act(async () => {
      const scenario = await post<Scenario>('/api/scenarios', { name: form.get('name'), description: form.get('description'), scenario_type: form.get('scenario_type'), configuration: config });
      await refresh(); setScenarioId(String(scenario.id)); setNotice(`Created ${scenario.name}. Ready to simulate.`);
    });
  }
  function createAlgorithm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    void act(async () => {
      const algorithm = await post<Algorithm>('/api/algorithms', { name: form.get('name'), version: form.get('version'), artifact_id: form.get('artifact_id'), configuration: { reaction_multiplier: Number(form.get('reaction')), braking_multiplier: Number(form.get('braking')), lane_gain_multiplier: Number(form.get('lane')) } });
      await refresh(); setAlgorithmId(String(algorithm.id)); setNotice(`Created algorithm ${algorithm.name}.`);
    });
  }
  const completed = selected?.status === 'completed';
  const shownRuns = runs.filter(r => filter === 'all' || (filter === 'failures' ? r.status === 'completed' && !r.metrics.passed : r.status === filter));
  const toggleCompare = (id: number) => { setComparison(null); setCompareIds(ids => ids.includes(id) ? ids.filter(i => i !== id) : ids.length < 10 ? [...ids, id] : ids); };
  const inspect = (run: Run) => { setSelectedId(run.id); setPage('Run explorer'); };
  const runTable = <div className="table-wrap history-table"><table><thead><tr><th>Compare</th><th>Run / scenario</th><th>Algorithm</th><th>Seed</th><th>Status</th><th>Result</th><th>Inspect</th></tr></thead><tbody>{shownRuns.map(run => <tr key={run.id}>
    <td><input aria-label={`Compare run ${run.id}`} type="checkbox" disabled={run.status !== 'completed' || (!compareIds.includes(run.id) && compareIds.length >= 10)} checked={compareIds.includes(run.id)} onChange={() => toggleCompare(run.id)} /></td>
    <td><b>#{run.id} · {run.snapshot.scenario_name ?? `Scenario ${run.scenario_id}`}</b></td><td>{run.snapshot.algorithm_name ?? `Algorithm ${run.algorithm_id}`}</td><td>{run.random_seed}</td>
    <td><span className={`badge ${run.status}`}>{run.status}</span></td><td>{run.status === 'completed' ? <span className={run.metrics.passed ? 'pass' : 'fail'}>{run.metrics.passed ? 'PASS' : 'FAIL'}</span> : '—'}</td>
    <td><button className="subtle small" aria-label={`Inspect run ${run.id}`} onClick={() => inspect(run)}><ArrowUpRight size={16} /></button></td>
  </tr>)}</tbody></table>{!shownRuns.length && <p className="empty compact">No runs match. Create your first simulation in Scenario lab.</p>}</div>;

  return <main className="shell">
    <header className="topbar"><div className="brand"><div className="brand-mark"><Activity size={21} /></div><div><strong>DriveEval <em>AI</em></strong><span>ADAS evaluation control room</span></div></div><div className="status"><span className={`dot ${online ? '' : 'offline'}`} />{online ? 'API CONNECTED' : 'API UNAVAILABLE'} · SYNTHETIC DATA</div></header>
    <nav aria-label="Dashboard pages">{pages.map(item => <button key={item} className={`nav-button ${page === item ? 'active' : ''}`} onClick={() => setPage(item)}>{item}</button>)}</nav>
    <section className="intro"><div><p className="eyebrow">EVALUATION / {page.toUpperCase()}</p><h1>{page === 'Overview' ? 'Know before you release.' : page === 'Scenario lab' ? 'Design the edge case.' : page === 'Compare' ? 'Measure the difference.' : page === 'Reports' ? 'Evidence into insight.' : 'Every run. Every signal.'}</h1><p className="lede">Repeatable scenarios. Transparent safety rules. Deterministic mock telemetry for engineering exploration.</p></div><div className="intro-meta"><span>TOTAL RUNS</span><b>{overview?.total_runs.toString().padStart(2, '0') ?? '—'}</b></div></section>
    {error && <div role="alert" className="error">{error}<button className="subtle small" onClick={() => setError('')}>Dismiss</button></div>}
    {notice && <div role="status" className="notice">{notice}</div>}
    {page === 'Overview' && <>
      <section className="kpis"><Kpi label="Total simulations" value={value(overview?.total_runs)} /><Kpi label="Pass rate · completed runs" value={overview?.pass_rate == null ? '—' : `${overview.pass_rate.toFixed(1)}%`} /><Kpi label="Failed evaluations" value={value(overview?.failed_evaluations)} /><Kpi label="Active jobs" value={value(overview?.active_jobs)} /></section>
      <section className="panel controls"><div className="panel-heading"><div><p className="eyebrow">TEST CAMPAIGN</p><h2>Start with a scenario. Follow the evidence.</h2></div><button onClick={() => setPage('Scenario lab')}><Plus size={16} /> Configure test</button></div><p className="lede">Six scenario families and three algorithm profiles are ready. Use the same configuration and seed for controlled comparisons.</p></section>
      <section className="panel section"><div className="panel-heading"><h2>Run history</h2><button className="subtle" onClick={() => setPage('Compare')}>Compare selected ({compareIds.length})</button></div>{runTable}</section>
    </>}
    {page === 'Scenario lab' && <>
      <section className="panel controls"><div className="panel-heading"><div><p className="eyebrow">SIMULATION SETUP</p><h2>Choose a scenario and algorithm</h2></div><span className="badge">MOCK / seed {config.random_seed}</span></div>
        <form onSubmit={e => { e.preventDefault(); startRun(); }}>
        <div className="control-grid"><label>Scenario<select required value={scenarioId} onChange={e => setScenarioId(e.target.value)}>{scenarios.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label>Algorithm<select required value={algorithmId} onChange={e => setAlgorithmId(e.target.value)}>{algorithms.map(a => <option key={a.id} value={a.id}>{a.name} · {a.version}</option>)}</select></label><button disabled={busy || !online || !scenarioId || !algorithmId}><Play size={16} /> Start simulation</button></div>
        <h3>Environment and vehicle</h3><div className="form-grid">{configFields.map(([key, label, min, max, step]) => <label key={key}>{label}<input required type="number" min={min} max={max} step={step} value={Number(config[key])} onChange={e => setConfig({ ...config, [key]: Number(e.target.value) })} /></label>)}
        <label>Weather<select value={config.weather} onChange={e => setConfig({ ...config, weather: e.target.value })}>{['clear', 'rain', 'snow'].map(v => <option key={v}>{v}</option>)}</select></label>
        <label>Time of day<select value={config.time_of_day} onChange={e => setConfig({ ...config, time_of_day: e.target.value })}>{['day', 'dusk', 'night'].map(v => <option key={v}>{v}</option>)}</select></label></div>
        <details><summary>Evaluation rules</summary><p className="muted">Collisions always fail. The thresholds below are saved with every run.</p><div className="form-grid">{ruleFields.map(([key, label, min, max, step]) => <label key={key}>{label}<input required type="number" min={min} max={max} step={step} value={Number(config.rules[key])} onChange={e => setConfig({ ...config, rules: { ...config.rules, [key]: Number(e.target.value) } })} /></label>)}</div>
        <div className="actions"><label className="check"><input type="checkbox" checked={config.rules.fail_on_critical_ttc} onChange={e => setConfig({ ...config, rules: { ...config.rules, fail_on_critical_ttc: e.target.checked } })} />Fail on critical TTC</label><label className="check"><input type="checkbox" checked={config.rules.fail_on_speeding} onChange={e => setConfig({ ...config, rules: { ...config.rules, fail_on_speeding: e.target.checked } })} />Fail on speeding</label></div></details></form>
      </section>
      <div className="content-grid section"><form className="panel controls" onSubmit={createScenario}><p className="eyebrow">SCENARIO LIBRARY</p><h2>Save a new scenario</h2><p className="muted">Uses the environment and safety rules configured above.</p><div className="stack"><label>Name<input name="name" required maxLength={120} placeholder="Wet road / pedestrian crossing" /></label><label>Scenario type<select name="scenario_type">{types.map(t => <option key={t} value={t}>{human(t)}</option>)}</select></label><label>Description<textarea name="description" maxLength={500} rows={2} /></label><button disabled={busy}>Save scenario</button></div></form>
      <form className="panel controls" onSubmit={createAlgorithm}><p className="eyebrow">ALGORITHM REGISTRY</p><h2>Register a tuned algorithm</h2><div className="stack"><label>Algorithm name<input name="name" required maxLength={120} placeholder="Baseline / brake tuning" /></label><label>Base profile<select name="version">{['baseline-v1', 'cautious-v2', 'aggressive-v3'].map(v => <option key={v}>{v}</option>)}</select></label><label>Git commit or artifact ID<input name="artifact_id" maxLength={120} /></label><div className="form-grid"><label>Reaction multiplier<input name="reaction" type="number" min={0.2} max={3} step={0.1} defaultValue={1} required /></label><label>Braking multiplier<input name="braking" type="number" min={0.2} max={2} step={0.1} defaultValue={1} required /></label><label>Lane gain multiplier<input name="lane" type="number" min={0.1} max={3} step={0.1} defaultValue={1} required /></label></div><button disabled={busy}>Register algorithm</button></div></form></div>
    </>}
    {(page === 'Run explorer' || page === 'Compare') && <section className="panel controls"><div className="panel-heading"><h2>{page === 'Compare' ? 'Select 2–10 completed runs' : 'Explore evaluations'}</h2><label>Filter<select value={filter} onChange={e => setFilter(e.target.value)}>{['all', 'failures', 'queued', 'running', 'completed', 'failed'].map(f => <option key={f} value={f}>{f === 'failed' ? 'job errors' : f}</option>)}</select></label></div>{runTable}<div className="actions"><button className="subtle" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>Previous</button><span className="muted">Page {offset / 100 + 1}</span><button className="subtle" disabled={runs.length < 100} onClick={() => setOffset(offset + 100)}>Next</button></div></section>}
    {page === 'Run explorer' && selected && <>
      <section className="panel controls section"><div className="panel-heading"><div><p className="eyebrow">RUN #{selected.id} / {selected.status}</p><h2>{selected.snapshot.scenario_name ?? 'Legacy scenario'} · {selected.snapshot.algorithm_name ?? 'Legacy algorithm'}</h2></div><span className={`badge ${selected.metrics.passed ? 'completed' : 'failed'}`}>{completed ? selected.metrics.passed ? 'PASS' : 'FAIL' : selected.status}</span></div>
        {selected.error_message && <p className="error">{selected.error_message}</p>}
        {!completed && !selected.error_message && <p className="muted">Simulation queued or running. Results appear automatically.</p>}
        {completed && <><div className="actions"><button className="subtle" onClick={() => void act(async () => downloadRun(selected.id, 'json'))}><Download size={15} />JSON</button><button className="subtle" onClick={() => void act(async () => downloadRun(selected.id, 'csv'))}><Download size={15} />CSV</button><button onClick={() => setPage('Reports')}>Analyze run</button></div><div className="metric-grid">{Object.entries(metricLabels).map(([key, label]) => <div key={key}><span>{label}</span><strong>{value(selected.metrics[key])}</strong></div>)}</div>
        <h3>Findings</h3><p className={selected.metrics.passed ? 'pass' : 'fail'}>{selected.metrics.violations?.map(human).join(' · ') || 'No configured failure thresholds exceeded.'}</p>{!!selected.metrics.warnings?.length && <p className="muted">Warnings: {selected.metrics.warnings.map(human).join(' · ')}</p>} </>}
        <details><summary>Saved configuration and provenance</summary><pre>{JSON.stringify(selected.snapshot, null, 2)}</pre><pre>{JSON.stringify(selected.environment, null, 2)}</pre></details>
      </section>
      {completed && <Suspense fallback={<p className="muted">Loading telemetry charts…</p>}><TelemetryCharts run={selected} /></Suspense>}
    </>}
    {page === 'Compare' && <section className="panel controls section"><div className="panel-heading"><div><h2>Algorithm comparison</h2><p className="muted">Selected: {compareIds.map(id => `#${id}`).join(', ') || 'None'}. Match scenario, environment and seed for a controlled comparison.</p></div><button disabled={busy || compareIds.length < 2} onClick={() => void act(async () => { setComparison(await request<Comparison>(`/api/compare?run_ids=${compareIds.join(',')}`)); })}>Compare runs</button></div>
      {comparison && <>{comparison.warning && <p className="error">{comparison.warning}</p>}<div className="table-wrap"><table><thead><tr><th>Metric</th>{comparison.runs.map(r => <th key={r.id}>#{r.id} · {r.snapshot.algorithm_name}</th>)}</tr></thead><tbody>{Object.entries(metricLabels).map(([key, label]) => <tr key={key}><th>{label}</th>{comparison.runs.map(r => <td key={r.id}>{value(r.metrics[key])}</td>)}</tr>)}</tbody></table></div><details><summary>Numeric changes relative to first run</summary><pre>{JSON.stringify(comparison.deltas_from_first, null, 2)}</pre></details></>}
    </section>}
    {page === 'Reports' && <section className="panel controls"><p className="eyebrow">FAILURE ANALYSIS / RELEASE REVIEW</p><h2>Generate an evaluation report</h2><div className="control-grid"><label>Completed run<select value={completed ? String(selectedId) : ''} onChange={e => setSelectedId(Number(e.target.value))}><option value="" disabled>Select a completed run</option>{runs.filter(r => r.status === 'completed').map(r => <option key={r.id} value={r.id}>#{r.id} · {r.snapshot.scenario_name} / {r.snapshot.algorithm_name}</option>)}</select></label><label className="check"><input type="checkbox" checked={useLlm} onChange={e => setUseLlm(e.target.checked)} />Use configured AI provider</label><button disabled={busy || !completed} onClick={() => void act(async () => { setReport(await post<Report>(`/api/runs/${selectedId}/report`, { use_llm: useLlm })); })}>{busy ? 'Generating…' : 'Generate report'}</button></div><p className="muted">AI mode sends the saved configuration and metrics to the server-configured provider. Offline analysis is always available.</p>
      {report && <article className="report"><div className="panel-heading"><h2>{report.headline} · #{report.run_id}</h2><button className="subtle" onClick={() => downloadJson(`driveeval-report-${report.run_id}.json`, report)}><Download size={15} />Export report</button></div><p className="eyebrow">{report.generated_by}</p><p>{report.summary}</p><h3>Recommendation</h3><p>{report.recommendation}</p>{report.llm_status && <p className="muted">AI status: {report.llm_status}</p>}{report.ai_analysis && <><h3>AI-assisted analysis</h3><p className="analysis-text">{report.ai_analysis}</p></>}<h3>Failure timeline</h3>{report.failure_cases.length ? <div className="table-wrap failure-table"><table><thead><tr><th>Time · s</th><th>Gap · m</th><th>TTC · s</th><th>Lane offset · m</th></tr></thead><tbody>{report.failure_cases.map((s, i) => <tr key={i}><td>{s.timestamp_s}</td><td>{value(s.distance_m)}</td><td>{value(s.ttc_s)}</td><td>{s.lane_offset_m}</td></tr>)}</tbody></table></div> : <p>No collision, critical TTC or excessive lane-offset samples. Review summary for other rule failures.</p>}<p className="muted">{report.limitations}</p></article>}
    </section>}
    <footer><ShieldCheck size={16} /> Synthetic mock evaluation · Reproducible by seed · Not vehicle validation or release certification</footer>
  </main>;
}
function Kpi({ label, value }: { label: string; value: string }) { return <div className="kpi"><Activity className="kpi-icon" size={20} /><span>{label}</span><strong>{value}</strong></div>; }

