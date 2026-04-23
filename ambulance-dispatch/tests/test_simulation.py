from src.core.simulation_engine import SimulationEngine


def test_dispatch_integration():
    sim = SimulationEngine(
        duration=100,
        lambda_rate=0.05,
        grid_size=20
    )

    sim.run()

    assert len(sim.ambulances) > 0
    assert len(sim.processed_events) > 0