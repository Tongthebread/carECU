# Optional CARLA adapter

The default simulator is synthetic. `CarlaSimulator` is an intentionally unavailable
adapter skeleton, as requested; no endpoint claims to execute CARLA. CARLA was not
installed on the development host, so no executable CARLA scenario was validated.

To prepare a separate CARLA environment:

1. Choose a release and follow its [official package installation guide](https://carla.readthedocs.io/en/latest/start_quickstart/).
   Use the operating system, GPU and Python version supported by that specific release;
   do not assume the backend's Python environment can load every CARLA wheel.
2. Download the simulator package and install its matching Python client wheel in a
   dedicated virtual environment. Installing the Python client alone does not install the server.
3. Start the simulator with its supplied launcher, then run its PythonAPI example scripts
   to verify connectivity. See [official first steps](https://carla.readthedocs.io/en/0.9.15/tuto_G_getting_started/).

To implement the platform adapter, subclass `Simulator` and return `SimulationResult`.
Use synchronous stepping, a fixed timestep, seeded traffic, collision sensors and
per-sample telemetry in SI units (speed is exported in km/h). Preserve world settings
and clean up every spawned actor in `finally`. Route telemetry through `evaluate` and
record map, simulator release, controller artifact and seed in the run snapshot.
Start with lead-vehicle braking. Require repeatability and collision-sensor tests before
exposing a CARLA selector in the dashboard. A separate worker can bridge incompatible
Python environments without changing the FastAPI service.
