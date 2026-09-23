from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


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


class EvaluationRules(StrictModel):
    minimum_ttc_s: float = Field(1.5, ge=0, le=10)
    maximum_lane_deviation_m: float = Field(1.0, gt=0, le=5)
    lane_boundary_m: float = Field(0.8, gt=0, le=5)
    safe_stop_distance_m: float = Field(0.5, ge=0, le=20)
    speed_tolerance_fraction: float = Field(0.05, ge=0, le=0.5)
    fail_on_critical_ttc: bool = True
    fail_on_speeding: bool = True


class ScenarioConfig(StrictModel):
    ego_speed_kph: float = Field(50, ge=0, le=200)
    speed_limit_kph: float = Field(50, ge=1, le=200)
    weather: Literal["clear", "rain", "snow"] = "clear"
    rain_intensity: float = Field(0, ge=0, le=1)
    fog_density: float = Field(0, ge=0, le=1)
    time_of_day: Literal["day", "dusk", "night"] = "day"
    traffic_density: float = Field(0.3, ge=0, le=1)
    obstacle_distance_m: float = Field(35, ge=1, le=500)
    sensor_noise: float = Field(0.02, ge=0, le=1)
    reaction_delay_s: float = Field(0.5, ge=0, le=5)
    random_seed: int = Field(7, ge=0, le=2147483647)
    duration_s: float = Field(12, ge=1, le=120)
    rules: EvaluationRules = Field(default_factory=EvaluationRules)


class AlgorithmConfig(StrictModel):
    reaction_multiplier: float = Field(1, ge=0.2, le=3)
    braking_multiplier: float = Field(1, ge=0.2, le=2)
    lane_gain_multiplier: float = Field(1, ge=0.1, le=3)


class TelemetrySample(StrictModel):
    timestamp_s: float
    position_m: float
    speed_kph: float
    acceleration_mps2: float
    lane_offset_m: float
    distance_to_obstacle_m: float | None
    time_to_collision_s: float | None
    collision: bool = False
    obstacle_speed_kph: float | None = None


class EvaluationMetrics(StrictModel):
    collision_occurred: bool
    collision_count: int
    minimum_time_to_collision_s: float | None
    minimum_following_distance_m: float | None
    maximum_deceleration_mps2: float
    average_speed_kph: float
    speed_limit_violations: int
    maximum_lane_deviation_m: float
    lane_departure_duration_s: float
    successful_stop: bool
    reaction_time_s: float | None
    scenario_completion_time_s: float
    passed: bool
    failure_severity: str
    violations: list[str]
    warnings: list[str] = Field(default_factory=list)


class SimulationResult(StrictModel):
    algorithm_version: AlgorithmProfile
    scenario_type: ScenarioType
    random_seed: int
    telemetry: list[TelemetrySample]
    metrics: EvaluationMetrics
