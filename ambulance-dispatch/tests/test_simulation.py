from src.core.simulation_engine import SimulationEngine


def test_simulation_runs():
    sim = SimulationEngine(
        duration=100,
        lambda_rate=0.05,
        grid_size=20
    )

    sim.run()

    assert len(sim.processed_events) > 0
    assert len(sim.hospitals) == 3
    assert len(sim.depots) == 2