"""Metrics derived only from sampled telemetry; rules remain explicit in the run snapshot."""
from .schemas import EvaluationMetrics, ScenarioConfig, ScenarioType, TelemetrySample

STOP_SCENARIOS = {ScenarioType.EMERGENCY_BRAKING, ScenarioType.PEDESTRIAN_CROSSING,
                  ScenarioType.LOW_VISIBILITY_OBSTACLE}


def evaluate(samples: list[TelemetrySample], scenario: ScenarioType, config: ScenarioConfig,
             reaction_time: float | None) -> EvaluationMetrics:
    rules = config.rules
    collisions = sum(s.collision and (i == 0 or not samples[i-1].collision) for i, s in enumerate(samples))
    ttcs = [s.time_to_collision_s for s in samples if s.time_to_collision_s is not None]
    distances = [s.distance_to_obstacle_m for s in samples if s.distance_to_obstacle_m is not None]
    min_ttc = min(ttcs) if ttcs else None
    min_distance = min(distances) if distances else None
    lane_max = max(abs(s.lane_offset_m) for s in samples)
    speeding = sum(s.speed_kph > config.speed_limit_kph * (1 + rules.speed_tolerance_fraction) for s in samples)
    stopped = (samples[-1].speed_kph <= 0.1 and not collisions
               and (min_distance is None or min_distance >= rules.safe_stop_distance_m))
    violations, warnings = [], []
    if collisions:
        violations.append("collision")
    if min_ttc is not None and min_ttc < rules.minimum_ttc_s:
        warnings.append("critical_time_to_collision")
        if rules.fail_on_critical_ttc:
            violations.append("critical_time_to_collision")
    if lane_max > rules.maximum_lane_deviation_m:
        violations.append("excessive_lane_deviation")
    if scenario in STOP_SCENARIOS and not stopped:
        violations.append("unsafe_or_incomplete_stop")
    if speeding:
        warnings.append("speed_limit_violation")
        if rules.fail_on_speeding:
            violations.append("speed_limit_violation")
    duration = samples[-1].timestamp_s
    integral = sum((a.speed_kph + b.speed_kph) / 2 * (b.timestamp_s - a.timestamp_s)
                   for a, b in zip(samples, samples[1:]))
    lane_duration = sum(b.timestamp_s - a.timestamp_s for a, b in zip(samples, samples[1:])
                        if abs(a.lane_offset_m) > rules.lane_boundary_m)
    return EvaluationMetrics(
        collision_occurred=bool(collisions), collision_count=collisions,
        minimum_time_to_collision_s=min_ttc, minimum_following_distance_m=min_distance,
        maximum_deceleration_mps2=max(0, -min(s.acceleration_mps2 for s in samples)),
        average_speed_kph=round(integral / duration, 3) if duration else samples[0].speed_kph,
        speed_limit_violations=speeding, maximum_lane_deviation_m=round(lane_max, 3),
        lane_departure_duration_s=round(lane_duration, 3), successful_stop=stopped,
        reaction_time_s=reaction_time, scenario_completion_time_s=duration,
        passed=not violations, failure_severity="critical" if collisions or "critical_time_to_collision" in warnings
        else "warning" if violations or warnings else "none", violations=violations, warnings=warnings,
    )
