#pragma once

struct VehicleState {
    double speed;             // vehicle speed (m/s)
    double obstacleDistance;  // distance to obstacle (m)
    double relativeSpeed;     // closing speed (m/s)
    double acceleration;       // vehicle acceleration (m/s^2)
};