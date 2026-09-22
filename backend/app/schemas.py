from enum import Enum

from pydantic import BaseModel, Field


class ScenarioType(str, Enum):
    PEDESTRIAN_CROSSING = "pedestrian_crossing"
    EMERGENCY_BRAKING = "emergency_braking"
    VEHICLE_CUT_IN = "vehicle_cut_in"
    LANE_DEPARTURE = "lane_departure"
    LOW_VISIBILITY_OBSTACLE = "low_visibility_obstacle"
    STOP_AND_GO = "stop_and_go"


class AlgorithmProfile(str, Enum):
    BASELINE = "baseline-v1"
    CAUTIOUS = "cautious-v2"
    AGGRESSIVE = "aggressive-v3"


class ScenarioConfig(BaseModel):
    ego_speed_kph: float = Field(default=50, ge=0, le=200)
    speed_limit_kph: float = Field(default=50, ge=1, le=200)
    weather: str = "clear"
    rain_intensity: float = Field(default=0, ge=0, le=1)
    fog_density: float = Field(default=0, ge=0, le=1)
    time_of_day: str = "day"
    traffic_density: float = Field(default=0.3, ge=0, le=1)
    obstacle_distance_m: float = Field(default=35, ge=1, le=500)
    sensor_noise: float = Field(default=0.02, ge=0, le=1)
    reaction_delay_s: float = Field(default=0.5, ge=0, le=5)
    random_seed: int = 7
    duration_s: float = Field(default=12, ge=1, le=120)


class TelemetrySample(BaseModel):
    timestamp_s: float
    position_m: float
    speed_kph: float
    acceleration_mps2: float
    lane_offset_m: float
    distance_to_obstacle_m: float
    time_to_collision_s: float | None


class EvaluationMetrics(BaseModel):
    collision_occurred: bool
    collision_count: int
    minimum_time_to_collision_s: float
    minimum_following_distance_m: float
    maximum_deceleration_mps2: float
    average_speed_kph: float
    speed_limit_violations: int
    maximum_lane_deviation_m: float
    lane_departure_duration_s: float
    successful_stop: bool
    reaction_time_s: float
    scenario_completion_time_s: float
    passed: bool
    failure_severity: str
    violations: list[str]


class SimulationResult(BaseModel):
    algorithm_version: AlgorithmProfile
    scenario_type: ScenarioType
    random_seed: int
    telemetry: list[TelemetrySample]
    metrics: EvaluationMetrics