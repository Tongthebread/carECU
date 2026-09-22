// AEBController.cpp

#include "../include/AEBController.hpp"

double calculateTTC(double distance, double relativeSpeed)
{
    // If we are not approaching the obstacle,
    // there is no collision risk.
    if (relativeSpeed <= 0.0)
        return 9999.0;

    return distance / relativeSpeed;
}

AEBState updateAEB(const VehicleState& vehicle)
{
    double ttc = calculateTTC(
        vehicle.obstacleDistance,
        vehicle.relativeSpeed
    );

    if (ttc < 1.0)
        return AEBState::EMERGENCY;

    if (ttc < 1.5)
        return AEBState::BRAKING;

    if (ttc < 3.0)
        return AEBState::WARNING;

    return AEBState::NORMAL;
}