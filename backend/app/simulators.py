from abc import ABC, abstractmethod
import random

from .schemas import (
    AlgorithmProfile,
    EvaluationMetrics,
    ScenarioConfig,
    ScenarioType,
    SimulationResult,
    TelemetrySample,
)


class Simulator(ABC):
    @abstractmethod
    def run(self, scenario_type: ScenarioType, config: ScenarioConfig, algorithm: AlgorithmProfile) -> SimulationResult:
        raise NotImplementedError


class MockSimulator(Simulator):
    """Fast deterministic simulator for local development and automated tests."""

    _profile_factor = {
        AlgorithmProfile.BASELINE: 1.0,
        AlgorithmProfile.CAUTIOUS: 1.25,
        AlgorithmProfile.AGGRESSIVE: 0.72,
    }

    def run(self, scenario_type: ScenarioType, config: ScenarioConfig, algorithm: AlgorithmProfile) -> SimulationResult:
        rng = random.Random(config.random_seed)
        factor = self._profile_factor[algorithm]
        step_s = 0.2
        samples: list[TelemetrySample] = []
        speed_mps = config.ego_speed_kph / 3.6
        position_m = 0.0
        lane_offset = 0.0
        reaction_time = config.reaction_delay_s * factor + 0.15
        braking_started = False

        for index in range(int(config.duration_s / step_s) + 1):
            timestamp_s = round(index * step_s, 2)
            obstacle_distance = max(0.0, config.obstacle_distance_m - position_m)
            is_hazard = scenario_type in {
                ScenarioType.PEDESTRIAN_CROSSING,
                ScenarioType.EMERGENCY_BRAKING,
                ScenarioType.LOW_VISIBILITY_OBSTACLE,
            }
            hazard_visible = timestamp_s >= reaction_time and is_hazard
            acceleration = rng.uniform(-0.15, 0.15) + config.sensor_noise * rng.uniform(-1, 1)
            if hazard_visible:
                braking_started = True
                acceleration -= 3.2 * factor
            if scenario_type == ScenarioType.STOP_AND_GO and index % 25 < 8:
                acceleration -= 1.8
            speed_mps = max(0.0, speed_mps + acceleration * step_s)
            position_m += speed_mps * step_s
            if scenario_type in {ScenarioType.LANE_DEPARTURE, ScenarioType.VEHICLE_CUT_IN}:
                lane_offset += (0.06 if scenario_type == ScenarioType.LANE_DEPARTURE else 0.03) * step_s
                lane_offset += rng.uniform(-0.015, 0.015)
            else:
                lane_offset += rng.uniform(-0.01, 0.01) * (1 + config.sensor_noise)
            relative_speed = max(speed_mps, 0.01)
            ttc = obstacle_distance / relative_speed if obstacle_distance > 0 else 0.0
            samples.append(
                TelemetrySample(
                    timestamp_s=timestamp_s,
                    position_m=round(position_m, 3),
                    speed_kph=round(speed_mps * 3.6, 3),
                    acceleration_mps2=round(acceleration, 3),
                    lane_offset_m=round(lane_offset, 3),
                    distance_to_obstacle_m=round(obstacle_distance, 3),
                    time_to_collision_s=round(ttc, 3) if obstacle_distance > 0 else 0.0,
                )
            )

        metrics = self._evaluate(samples, scenario_type, config, reaction_time, braking_started)
        return SimulationResult(
            algorithm_version=algorithm,
            scenario_type=scenario_type,
            random_seed=config.random_seed,
            telemetry=samples,
            metrics=metrics,
        )

    @staticmethod
    def _evaluate(
        samples: list[TelemetrySample],
        scenario_type: ScenarioType,
        config: ScenarioConfig,
        reaction_time: float,
        braking_started: bool,
    ) -> EvaluationMetrics:
        collision = any(sample.distance_to_obstacle_m <= 0.1 for sample in samples)
        min_ttc = min((sample.time_to_collision_s or 0 for sample in samples), default=0)
        min_distance = min((sample.distance_to_obstacle_m for sample in samples), default=0)
        max_deceleration = min((sample.acceleration_mps2 for sample in samples), default=0)
        average_speed = sum(sample.speed_kph for sample in samples) / max(len(samples), 1)
        speed_violations = sum(sample.speed_kph > config.speed_limit_kph * 1.05 for sample in samples)
        max_lane_deviation = max((abs(sample.lane_offset_m) for sample in samples), default=0)
        lane_duration = sum(0.2 for sample in samples if abs(sample.lane_offset_m) > 0.8)
        successful_stop = not scenario_type == ScenarioType.EMERGENCY_BRAKING or (braking_started and min_distance > 0.5)
        violations: list[str] = []
        if collision:
            violations.append("collision")
        if min_ttc < 1.5:
            violations.append("critical_time_to_collision")
        if scenario_type == ScenarioType.LANE_DEPARTURE and max_lane_deviation > 1.0:
            violations.append("excessive_lane_deviation")
        if scenario_type == ScenarioType.EMERGENCY_BRAKING and not successful_stop:
            violations.append("stopping_distance_exceeded")
        if speed_violations > 0:
            violations.append("speed_limit_violation")
        severity = "critical" if collision or "critical_time_to_collision" in violations else "warning" if violations else "none"
        return EvaluationMetrics(
            collision_occurred=collision,
            collision_count=int(collision),
            minimum_time_to_collision_s=round(min_ttc, 3),
            minimum_following_distance_m=round(min_distance, 3),
            maximum_deceleration_mps2=round(max_deceleration, 3),
            average_speed_kph=round(average_speed, 3),
            speed_limit_violations=speed_violations,
            maximum_lane_deviation_m=round(max_lane_deviation, 3),
            lane_departure_duration_s=round(lane_duration, 3),
            successful_stop=successful_stop,
            reaction_time_s=round(reaction_time, 3),
            scenario_completion_time_s=samples[-1].timestamp_s if samples else 0,
            passed=not violations,
            failure_severity=severity,
            violations=violations,
        )


class CarlaSimulator(Simulator):
    """Adapter boundary for a future CARLA implementation."""

    def run(self, scenario_type: ScenarioType, config: ScenarioConfig, algorithm: AlgorithmProfile) -> SimulationResult:
        raise RuntimeError("CARLA support requires the optional carla dependency and is not enabled yet")