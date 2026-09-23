from abc import ABC, abstractmethod
import math
import random

from .evaluation import evaluate
from .schemas import AlgorithmConfig, AlgorithmProfile, ScenarioConfig, ScenarioType, SimulationResult, TelemetrySample


class Simulator(ABC):
    @abstractmethod
    def run(self, scenario_type: ScenarioType, config: ScenarioConfig, algorithm: AlgorithmProfile,
            tuning: AlgorithmConfig | None = None) -> SimulationResult:
        """Produce synthetic or adapter-provided telemetry and its evaluation."""


class MockSimulator(Simulator):
    """Seeded point-mass model. Synthetic portfolio data, never vehicle validation."""
    # Delay multiplier, dry-road braking m/s², lateral correction gain.
    profiles = {
        AlgorithmProfile.BASELINE: (1.0, 5.5, 0.8),
        AlgorithmProfile.CAUTIOUS: (0.65, 7.0, 1.6),
        AlgorithmProfile.AGGRESSIVE: (1.5, 3.8, 0.3),
    }

    def run(self, scenario_type, config, algorithm, tuning=None):
        tuning = tuning or AlgorithmConfig()
        rng = random.Random(config.random_seed)
        delay, brake, lane_gain = self.profiles[algorithm]
        visibility_delay = config.fog_density * 1.4 + {"day": 0, "dusk": 0.2, "night": 0.5}[config.time_of_day]
        reaction_delay = (config.reaction_delay_s * delay * tuning.reaction_multiplier
                          + visibility_delay + config.sensor_noise * rng.uniform(0, 0.5))
        if scenario_type == ScenarioType.LOW_VISIBILITY_OBSTACLE:
            reaction_delay += 0.5
        grip = max(0.25, 1 - 0.4 * config.rain_intensity - {"clear": 0, "rain": 0.15, "snow": 0.5}[config.weather])
        brake *= grip * tuning.braking_multiplier
        lane_gain *= tuning.lane_gain_multiplier * grip
        speed = config.ego_speed_kph / 3.6
        target_speed = min(config.ego_speed_kph, config.speed_limit_kph) / 3.6
        position, lane, acceleration = 0.0, 0.0, 0.0
        obstacle_position = config.obstacle_distance_m
        lead_speed = speed * 0.7 if scenario_type == ScenarioType.EMERGENCY_BRAKING else 0.0
        event_time = 1.0 if scenario_type in {ScenarioType.VEHICLE_CUT_IN, ScenarioType.LANE_DEPARTURE} else 0.0
        collision, reacted_at = False, None
        samples = []
        steps = math.ceil(config.duration_s / 0.1)
        previous_t = 0.0
        for index in range(steps + 1):
            t = min(round(index * 0.1, 6), config.duration_s)
            dt = t - previous_t
            previous_t = t
            active = scenario_type != ScenarioType.LANE_DEPARTURE and t >= event_time
            if scenario_type == ScenarioType.VEHICLE_CUT_IN:
                lead_speed = target_speed * 0.45
                if index and t - dt < event_time <= t:
                    obstacle_position = position + config.obstacle_distance_m * (1 - 0.4 * config.traffic_density)
            elif scenario_type == ScenarioType.STOP_AND_GO:
                lead_speed = target_speed * max(0, math.sin(t * (0.7 + config.traffic_density)))
            elif scenario_type == ScenarioType.EMERGENCY_BRAKING:
                lead_speed = max(0, lead_speed - 7.5 * dt)
            obstacle_position += lead_speed * dt
            ready = t >= event_time + reaction_delay
            if index:
                acceleration = 0.0
                if ready and not collision:
                    if reacted_at is None:
                        reacted_at = round(t - event_time, 3)
                    if scenario_type == ScenarioType.LANE_DEPARTURE:
                        acceleration = max(-brake, min(1.8, target_speed - speed))
                    elif scenario_type in {ScenarioType.STOP_AND_GO, ScenarioType.VEHICLE_CUT_IN}:
                        gap = obstacle_position - position
                        desired_gap = 3 + speed * (1.6 if algorithm == AlgorithmProfile.CAUTIOUS else 1.0)
                        acceleration = max(-brake, min(1.8, 0.45 * (gap - desired_gap) + 0.9 * (lead_speed - speed)))
                    else:
                        acceleration = -brake
                    if speed > 0:
                        acceleration += config.sensor_noise * rng.uniform(-0.3, 0.3)
                old_speed = speed
                speed = max(0, speed + acceleration * dt) if not collision else 0
                acceleration = (speed - old_speed) / dt
                position += (old_speed + speed) * 0.5 * dt
                drift = 0.55 if scenario_type == ScenarioType.LANE_DEPARTURE and t >= event_time else 0.01
                if scenario_type == ScenarioType.VEHICLE_CUT_IN and event_time <= t < event_time + 1:
                    drift += 0.2
                lane += (drift + rng.uniform(-1, 1) * config.sensor_noise - (lane_gain * lane if ready else 0)) * dt
            distance = max(0.0, obstacle_position - position) if active else None
            if active and obstacle_position <= position:
                collision = True
                speed = 0.0
            closing_speed = speed - lead_speed
            ttc = (0.0 if collision else distance / closing_speed if distance is not None and closing_speed > 0.01 else None)
            samples.append(TelemetrySample(
                timestamp_s=t, position_m=round(position, 4), speed_kph=round(speed * 3.6, 4),
                acceleration_mps2=round(acceleration, 4), lane_offset_m=round(lane, 4),
                distance_to_obstacle_m=round(distance, 4) if distance is not None else None,
                time_to_collision_s=round(ttc, 4) if ttc is not None else None,
                collision=collision, obstacle_speed_kph=round(lead_speed * 3.6, 4) if active else None))
            if collision:
                break
        return SimulationResult(algorithm_version=algorithm, scenario_type=scenario_type,
                                random_seed=config.random_seed, telemetry=samples,
                                metrics=evaluate(samples, scenario_type, config, reacted_at))


class CarlaSimulator(Simulator):
    """Explicit optional adapter boundary; see docs/CARLA.md before implementing."""
    def run(self, scenario_type, config, algorithm, tuning=None):
        raise RuntimeError("CARLA adapter is not configured. Use the mock simulator; see docs/CARLA.md.")
