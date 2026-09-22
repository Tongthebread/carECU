#include <iostream>
#include <thread>
#include <chrono>

#include "../include/AEBController.hpp"

const char* stateToString(AEBState state)
{
    switch (state)
    {
        case AEBState::NORMAL:
            return "NORMAL";

        case AEBState::WARNING:
            return "WARNING";

        case AEBState::BRAKING:
            return "BRAKING";

        case AEBState::EMERGENCY:
            return "EMERGENCY";
    }

    return "UNKNOWN";
}

int main()
{
    // Create our simulated vehicle
    VehicleState car;

    car.speed = 20.0;              // 20 m/s = 72 km/h
    car.obstacleDistance = 100.0;  // obstacle 100 meters away
    car.relativeSpeed = 20.0;      // approaching obstacle at 20 m/s

    const double timeStep = 0.1;   // simulation step = 100 ms

    while (car.obstacleDistance > 0.0)
    {
        // Ask the AEB controller what it should do
        AEBState state = updateAEB(car);

        // Calculate time to collision
        double ttc = calculateTTC(
            car.obstacleDistance,
            car.relativeSpeed
        );
        switch (state)
        {
            case AEBState::NORMAL:
                break;

            case AEBState::WARNING:
                std::cout << "Warning: Obstacle ahead!" << std::endl;
                break;

            case AEBState::BRAKING:
                std::cout << "Braking: Applying brakes!" << std::endl;
                break;

            case AEBState::EMERGENCY:
                std::cout << "Emergency: Full braking!" << std::endl;
                break;
        }
        std::cout
            << "Distance: " << car.obstacleDistance
            << " m | Speed: " << car.speed
            << " m/s | TTC: " << ttc
            << " s | AEB: " << stateToString(state)
            << std::endl;

        // Simulate the car moving toward the obstacle
        car.obstacleDistance -= car.relativeSpeed * timeStep;

        // Wait 100 ms
        std::this_thread::sleep_for(
            std::chrono::milliseconds(100)
        );
    }

    std::cout << "Simulation finished." << std::endl;

    return 0;
}