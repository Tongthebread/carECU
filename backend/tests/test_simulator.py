from app.schemas import AlgorithmProfile, ScenarioConfig, ScenarioType
from app.simulators import MockSimulator


def test_mock_simulation_is_reproducible():
    simulator = MockSimulator()
    config = ScenarioConfig(random_seed=42, obstacle_distance_m=40)
    first = simulator.run(ScenarioType.EMERGENCY_BRAKING, config, AlgorithmProfile.BASELINE)
    second = simulator.run(ScenarioType.EMERGENCY_BRAKING, config, AlgorithmProfile.BASELINE)

    assert first.model_dump() == second.model_dump()
    assert len(first.telemetry) > 10


def test_algorithm_profiles_produce_different_results():
    simulator = MockSimulator()
    config = ScenarioConfig(random_seed=9, obstacle_distance_m=30)
    cautious = simulator.run(ScenarioType.EMERGENCY_BRAKING, config, AlgorithmProfile.CAUTIOUS)
    aggressive = simulator.run(ScenarioType.EMERGENCY_BRAKING, config, AlgorithmProfile.AGGRESSIVE)

    assert cautious.metrics.reaction_time_s > aggressive.metrics.reaction_time_s
    assert cautious.metrics.maximum_deceleration_mps2 < aggressive.metrics.maximum_deceleration_mps2