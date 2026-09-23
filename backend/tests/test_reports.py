import httpx
from types import SimpleNamespace
from app.services.reports import generate_report
from app.schemas import AlgorithmProfile, ScenarioConfig, ScenarioType
from app.simulators import MockSimulator


def run_record():
    config = ScenarioConfig()
    result = MockSimulator().run(ScenarioType.PEDESTRIAN_CROSSING, config, AlgorithmProfile.AGGRESSIVE)
    return SimpleNamespace(id=12, metrics=result.metrics.model_dump(),
                           snapshot={"configuration": config.model_dump()},
                           telemetry=[s.model_dump() for s in result.telemetry])


def test_successful_ai_analysis_and_provider_failure(monkeypatch):
    monkeypatch.setenv('OPENAI_BASE_URL', 'http://provider.invalid/v1')
    monkeypatch.setenv('OPENAI_MODEL', 'test-model')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-secret')
    calls = []
    def response(self, url, **kwargs):
        calls.append(kwargs)
        return httpx.Response(200, request=httpx.Request('POST', url),
                              json={"choices": [{"message": {"content": "Investigate measured TTC."}}]})
    monkeypatch.setattr(httpx.Client, 'post', response)
    report = generate_report(run_record(), True)
    assert report['generated_by'] == 'openai-compatible+deterministic-analysis'
    assert report['ai_analysis'] == 'Investigate measured TTC.'
    assert report['failure_cases']
    assert 'test-secret' not in str(report)
    assert calls[0]['json']['model'] == 'test-model'
    def fail(*args, **kwargs):
        raise httpx.ConnectError('offline')
    monkeypatch.setattr(httpx.Client, 'post', fail)
    fallback = generate_report(run_record(), True)
    assert fallback['generated_by'] == 'deterministic-analysis'
    assert 'failed' in fallback['llm_status']


def test_optional_sinks_do_not_break_results(monkeypatch):
    from app.services.integrations import MLflowSink, S3Sink, publish_result
    monkeypatch.setenv('MLFLOW_TRACKING_URI', 'http://offline.invalid')
    monkeypatch.setenv('S3_BUCKET', 'test')
    calls = []
    def fail(self, *args):
        calls.append(type(self).__name__)
        raise RuntimeError('offline')
    monkeypatch.setattr(MLflowSink, 'publish', fail)
    monkeypatch.setattr(S3Sink, 'publish', fail)
    publish_result(1, object())
    assert calls == ['MLflowSink', 'S3Sink']
