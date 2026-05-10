from src.core.emergency import Emergency
from src.simulation.poisson_generator import PoissonEmergencyGenerator


class SurgeScenario:
    def __init__(self, generator):
        self.generator = generator
        self.surge_log = []

    def inject(self, current_time, count):
        if count < 1:
            raise ValueError("Surge count must be at least 1.")

        events = self.generator.generate_burst(current_time, count)
        self.surge_log.append({
            "time": current_time,
            "count": count,
            "ids": [e.event_id for e in events],
        })

        print(
            f"[SURGE @ t={current_time:.2f}] "
            f"Injected {count} emergencies: IDs {[e.event_id for e in events]}"
        )
        return events

    def verify_no_double_assignment(self, ambulances):
        seen = {}
        violation_found = False

        for amb in ambulances:
            if amb.current_emergency is None:
                continue
            eid = amb.current_emergency.event_id
            if eid in seen:
                print(
                    f"[CAPACITY VIOLATION] Emergency {eid} assigned to "
                    f"Ambulance {seen[eid]} AND Ambulance {amb.id}!"
                )
                violation_found = True
            else:
                seen[eid] = amb.id

        if not violation_found:
            print("[CAPACITY CHECK] OK — no double-assignments detected.")
        return not violation_found

    def summary(self):
        return list(self.surge_log)


def run_surge_test(sim_engine, surge_count=7, surge_at_time=50.0):
    scenario = SurgeScenario(sim_engine.generator)
    surge_events = scenario.inject(surge_at_time, surge_count)

    for event in surge_events:
        sim_engine.event_queue.push(event)

    print(f"\n--- Surge injected: {surge_count} emergencies ---")
    print(f"Queue size after injection: {sim_engine.event_queue.size()}\n")

    sim_engine.update_ambulances()
    capacity_ok = scenario.verify_no_double_assignment(sim_engine.ambulances)

    return {
        "surge_ids": [e.event_id for e in surge_events],
        "capacity_ok": capacity_ok,
        "processed_count": len(sim_engine.processed_events),
    }