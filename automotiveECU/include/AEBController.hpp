#pragma once

#include "Vehicle.hpp"
#include "AEBStates.hpp"

double calculateTTC(double distance, double relativeSpeed);
AEBState updateAEB(const VehicleState& vehicle);
