import math
from statistics import mean, stdev
from typing import List, Dict, Optional


class Metrics:
    """
    Centralised evaluation metrics for the ambulance dispatch system.

    All methods are pure functions (no state) so they can be called
    freely from any module without instantiation.
    """

    # =========================================================
    # RESPONSE TIME METRICS
    # =========================================================

    @staticmethod
    def average_response_time(times: List[float]) -> float:
        """Mean response time. Returns inf for an empty list."""
        if not times:
            return math.inf
        return round(mean(times), 2)

    @staticmethod
    def min_response_time(times: List[float]) -> float:
        """Best-case response time."""
        if not times:
            return math.inf
        return round(min(times), 2)

    @staticmethod
    def max_response_time(times: List[float]) -> float:
        """Worst-case response time."""
        if not times:
            return math.inf
        return round(max(times), 2)

    @staticmethod
    def std_response_time(times: List[float]) -> float:
        """
        Standard deviation of response times.
        IMPROVEMENT: exposes spread — a low average with high std_dev
        signals inconsistent service quality.
        """
        if len(times) < 2:
            return 0.0
        return round(stdev(times), 2)

    @staticmethod
    def percentile_response_time(times: List[float], p: float) -> float:
        """
        IMPROVEMENT: p-th percentile response time (0–100).
        Useful for reporting e.g. the 90th-percentile SLA target.

        Example
        -------
        >>> Metrics.percentile_response_time(times, 90)
        """
        if not times:
            return math.inf
        if not (0 <= p <= 100):
            raise ValueError(f"Percentile must be in [0, 100], got {p}")
        sorted_t = sorted(times)
        idx = (p / 100) * (len(sorted_t) - 1)
        lo, hi = int(idx), min(int(idx) + 1, len(sorted_t) - 1)
        return round(sorted_t[lo] + (idx - lo) * (sorted_t[hi] - sorted_t[lo]), 2)

    # =========================================================
    # SUCCESS RATE
    # =========================================================

    @staticmethod
    def success_rate(
        successful_dispatches: int,
        total_dispatches: int
    ) -> float:
        """Percentage of emergencies that received an ambulance."""
        if total_dispatches == 0:
            return 0.0
        return round((successful_dispatches / total_dispatches) * 100, 2)

    # =========================================================
    # AMBULANCE UTILIZATION
    # =========================================================

    @staticmethod
    def ambulance_utilization(
        busy_time: float,
        total_time: float
    ) -> float:
        """
        Percentage of time the fleet was occupied.

        utilization = (total busy time across all ambulances)
                      / (fleet size × simulation duration)

        A value near 100 % signals a fleet under heavy stress.
        """
        if total_time <= 0:
            return 0.0
        return round((busy_time / total_time) * 100, 2)

    # =========================================================
    # THROUGHPUT
    # =========================================================

    @staticmethod
    def throughput(
        completed_emergencies: int,
        simulation_duration: float
    ) -> float:
        """
        Emergencies completed per unit of simulation time.
        Higher is better; drops sharply during surge events.
        """
        if simulation_duration <= 0:
            return 0.0
        return round(completed_emergencies / simulation_duration, 2)

    # =========================================================
    # QUEUE DELAY
    # =========================================================

    @staticmethod
    def average_queue_delay(delays: List[float]) -> float:
        """
        Mean time an emergency spent waiting in the queue
        before any ambulance was assigned.
        0.0 means every emergency was dispatched immediately.
        """
        if not delays:
            return 0.0
        return round(mean(delays), 2)

    # =========================================================
    # IMPROVEMENT DELTA  (IMPROVEMENT: new helper)
    # =========================================================

    @staticmethod
    def improvement_over_baseline(
        baseline_times: List[float],
        improved_times: List[float]
    ) -> Dict:
        """
        IMPROVEMENT: quantify how much one method beats another.

        Returns
        -------
        dict with absolute_improvement and percent_improvement.
        Positive values mean improved_times is better (faster).
        """
        if not baseline_times or not improved_times:
            return {"absolute_improvement": math.nan, "percent_improvement": math.nan}

        base_avg = mean(baseline_times)
        impr_avg = mean(improved_times)
        absolute = round(base_avg - impr_avg, 2)
        percent  = round((absolute / base_avg) * 100, 2) if base_avg else math.nan

        return {
            "absolute_improvement": absolute,
            "percent_improvement":  percent,
        }

    # =========================================================
    # FULL SUMMARY
    # =========================================================

    @staticmethod
    def build_summary(
        response_times:        List[float],
        successful_dispatches: int,
        total_dispatches:      int,
        busy_time:             float             = 0.0,
        total_time:            float             = 1.0,
        completed_emergencies: int               = 0,
        simulation_duration:   float             = 1.0,
        queue_delays:          Optional[List[float]] = None,
    ) -> Dict:
        """
        Build a complete metrics snapshot for one simulation run.

        FIX: added guards for total_time / simulation_duration ≤ 0
             to avoid silent division-by-zero in edge cases.
        IMPROVEMENT: added std_dev and p90 response time.
        """
        if queue_delays is None:
            queue_delays = []

        # Clamp denominators so helpers don't receive 0
        safe_total_time          = max(total_time, 1e-9)
        safe_simulation_duration = max(simulation_duration, 1e-9)

        return {
            "avg_response_time":    Metrics.average_response_time(response_times),
            "min_response_time":    Metrics.min_response_time(response_times),
            "max_response_time":    Metrics.max_response_time(response_times),
            "std_response_time":    Metrics.std_response_time(response_times),
            "p90_response_time":    Metrics.percentile_response_time(response_times, 90),
            "success_rate":         Metrics.success_rate(successful_dispatches, total_dispatches),
            "ambulance_utilization":Metrics.ambulance_utilization(busy_time, safe_total_time),
            "throughput":           Metrics.throughput(completed_emergencies, safe_simulation_duration),
            "avg_queue_delay":      Metrics.average_queue_delay(queue_delays),
        }

    # =========================================================
    # PRINT SUMMARY
    # =========================================================

    @staticmethod
    def print_summary(summary: Dict):
        """
        Pretty-print a metrics summary dict.

        IMPROVEMENT: human-readable labels with units and aligned columns.
        """
        # Mapping: key → (display label, unit suffix)
        display = {
            "avg_response_time":     ("Avg Response Time",     "units"),
            "min_response_time":     ("Min Response Time",     "units"),
            "max_response_time":     ("Max Response Time",     "units"),
            "std_response_time":     ("Std Dev (Response)",    "units"),
            "p90_response_time":     ("P90 Response Time",     "units"),
            "success_rate":          ("Success Rate",          "%"),
            "ambulance_utilization": ("Fleet Utilization",     "%"),
            "throughput":            ("Throughput",            "emerg/unit"),
            "avg_queue_delay":       ("Avg Queue Delay",       "units"),
        }

        print("\n" + "=" * 45)
        print(f"{'SYSTEM METRICS':^45}")
        print("=" * 45)

        for key, value in summary.items():
            label, unit = display.get(key, (key, ""))
            val_str = f"{value} {unit}" if not math.isnan(float(value if value is not None else math.nan)) else "N/A"
            print(f"  {label:<28} {val_str}")

        print("=" * 45)