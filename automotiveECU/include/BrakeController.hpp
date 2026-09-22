#pragma once

#include "Vehicle.hpp"
#include "AEBController.hpp"

class BrakeController
{
public:
    void applyBrakes(VehicleState& vehicle, AEBState state) const;
};