import pytest
from app.schemas import AlgorithmConfig, AlgorithmProfile, ScenarioConfig, ScenarioType
from app.simulators import MockSimulator

simulator = MockSimulator()


@pytest.mark.parametrize("scenario", list(ScenarioType))
def test_reproducible_and_finite(scenario):
    config = ScenarioConfig(random_seed=42)
    first = simulator.run(scenario, config, AlgorithmProfile.BASELINE)
    assert first == simulator.run(scenario, config, AlgorithmProfile.BASELINE)
    assert first.telemetry[0].position_m == 0
    assert first.telemetry[0].timestamp_s == 0
    assert all(s.speed_kph >= 0 for s in first.telemetry)
    assert first.metrics.collision_count <= 1
    assert first.model_dump_json()


def test_profiles_produce_success_and_failure():
    config = ScenarioConfig(obstacle_distance_m=35)
    cautious = simulator.run(ScenarioType.PEDESTRIAN_CROSSING, config, AlgorithmProfile.CAUTIOUS)
    aggressive = simulator.run(ScenarioType.PEDESTRIAN_CROSSING, config, AlgorithmProfile.AGGRESSIVE)
    assert cautious.metrics.passed
    assert not aggressive.metrics.passed
    assert cautious.metrics.reaction_time_s < aggressive.metrics.reaction_time_s
    assert cautious.metrics.maximum_deceleration_mps2 > aggressive.metrics.maximum_deceleration_mps2


def test_lane_scenario_has_no_phantom_obstacle():
    result = simulator.run(ScenarioType.LANE_DEPARTURE, ScenarioConfig(), AlgorithmProfile.BASELINE)
    assert not result.metrics.collision_occurred
    assert result.metrics.minimum_time_to_collision_s is None
    assert result.metrics.minimum_following_distance_m is None


def test_short_run_does_not_claim_successful_stop():
    result = simulator.run(ScenarioType.EMERGENCY_BRAKING,
                           ScenarioConfig(duration_s=1, obstacle_distance_m=500), AlgorithmProfile.BASELINE)
    assert not result.metrics.successful_stop
    assert not result.metrics.passed


@pytest.mark.parametrize("change", [{"weather": "snow"}, {"rain_intensity": 1}, {"fog_density": 1},
                                   {"time_of_day": "night"}, {"sensor_noise": 0.8}, {"reaction_delay_s": 2}])
def test_environment_changes_behavior(change):
    normal = simulator.run(ScenarioType.PEDESTRIAN_CROSSING, ScenarioConfig(), AlgorithmProfile.CAUTIOUS)
    changed = simulator.run(ScenarioType.PEDESTRIAN_CROSSING, ScenarioConfig(**change), AlgorithmProfile.CAUTIOUS)
    assert normal.telemetry != changed.telemetry


def test_traffic_and_tuning_affect_runs():
    base = simulator.run(ScenarioType.STOP_AND_GO, ScenarioConfig(), AlgorithmProfile.BASELINE)
    dense = simulator.run(ScenarioType.STOP_AND_GO, ScenarioConfig(traffic_density=1), AlgorithmProfile.BASELINE)
    tuned = simulator.run(ScenarioType.STOP_AND_GO, ScenarioConfig(), AlgorithmProfile.BASELINE,
                          AlgorithmConfig(braking_multiplier=0.5))
    assert base.telemetry != dense.telemetry
    assert base.telemetry != tuned.telemetry


def test_rule_configuration_and_null_ttc():
    from app.evaluation import evaluate
    from app.schemas import EvaluationRules, TelemetrySample
    samples = [TelemetrySample(timestamp_s=t, position_m=0, speed_kph=0, acceleration_mps2=0,
                               lane_offset_m=0, distance_to_obstacle_m=10, time_to_collision_s=None)
               for t in [0, 0.1]]
    result = evaluate(samples, ScenarioType.EMERGENCY_BRAKING, ScenarioConfig(), None)
    assert result.passed and result.successful_stop
    assert result.minimum_time_to_collision_s is None
    samples[0].time_to_collision_s = 0.5
    result = evaluate(samples, ScenarioType.EMERGENCY_BRAKING,
                      ScenarioConfig(rules=EvaluationRules(fail_on_critical_ttc=False)), None)
    assert result.passed
    assert "critical_time_to_collision" in result.warnings
