from datetime import timedelta
from math import isfinite
from time import monotonic

from ortools.sat.python import cp_model

from ..cotwin.CotFoodPackaging import CotFoodPackaging
from .FoodPackagingSolution import FoodPackagingSolution
from .ScoreNoImprovement import ScoreNoImprovement


class FoodPackagingSolver:
    def __init__(
        self,
        workers: int = 10,
        no_improvement_seconds: float = 15,
        time_limit: float | None = None,
    ):
        if type(workers) is not int or workers < 1:
            raise ValueError("workers must be a positive integer")
        for name, value in (
            ("no_improvement_seconds", no_improvement_seconds),
            ("time_limit", time_limit),
        ):
            if name == "time_limit" and value is None:
                continue
            if type(value) not in (int, float) or not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number")
        self.workers = workers
        self.no_improvement_seconds = no_improvement_seconds
        self.time_limit = time_limit

    def _run_phase(
        self,
        cotwin: CotFoodPackaging,
        model: cp_model.CpModel,
        remaining: float | None,
        best_score=None,
        best_snapshot=None,
        sequence=0,
        elapsed_before=0,
        stop_on_zero_hard=False,
    ):
        error = model.validate()
        if error:
            raise ValueError(f"Invalid CP-SAT model: {error}")
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = self.workers
        solver.parameters.random_seed = 0
        solver.parameters.cp_model_presolve = False
        if remaining is not None:
            solver.parameters.max_time_in_seconds = remaining
        monitor = ScoreNoImprovement(
            solver,
            cotwin,
            self.no_improvement_seconds,
            best_score,
            best_snapshot,
            sequence,
            elapsed_before,
            stop_on_zero_hard,
        )
        monitor.start()
        try:
            status = solver.solve(model, monitor)
        finally:
            monitor.close()
        return status, monitor

    @staticmethod
    def _build_refined_model(
        cotwin: CotFoodPackaging, best_hard_penalty: int
    ) -> cp_model.CpModel:
        """Fix the proven hard score, then minimize medium before soft."""
        refined = cotwin.model.clone()
        refined.add(cotwin.hard_penalty == best_hard_penalty)
        refined.minimize(
            cotwin.medium_weight * cotwin.medium_penalty + cotwin.soft_penalty
        )
        return refined

    def solve(self, cotwin: CotFoodPackaging) -> FoodPackagingSolution:
        started = monotonic()
        status, monitor = self._run_phase(
            cotwin,
            cotwin.model,
            self.time_limit,
            stop_on_zero_hard=cotwin.mode == "penalized",
        )
        best_score = monitor.best_score
        best_snapshot = monitor.best_snapshot
        sequence = monitor.sequence
        stopped_idle = monitor.timed_out
        if cotwin.mode == "penalized" and best_score is not None:
            # Once a nonnegative hard score reaches zero it is proven minimal.
            hard_proven = status == cp_model.OPTIMAL or best_score[0] == 0
            remaining = (
                None
                if self.time_limit is None
                else max(0.0, self.time_limit - (monotonic() - started))
            )
            if (
                hard_proven
                and not stopped_idle
                and (remaining is None or remaining > 0)
            ):
                refined = self._build_refined_model(cotwin, best_score[0])
                status, monitor = self._run_phase(
                    cotwin,
                    refined,
                    remaining,
                    best_score,
                    best_snapshot,
                    sequence,
                    monotonic() - started,
                )
                best_score = monitor.best_score
                best_snapshot = monitor.best_snapshot
                stopped_idle = monitor.timed_out
                if status in (cp_model.INFEASIBLE, cp_model.MODEL_INVALID):
                    raise RuntimeError(
                        "Refined model rejected an earlier feasible schedule"
                    )
            elif status == cp_model.OPTIMAL:
                status = cp_model.FEASIBLE

        elapsed = monotonic() - started
        if status == cp_model.OPTIMAL:
            reason = "optimal"
        elif status == cp_model.INFEASIBLE:
            reason = "infeasible"
        elif status == cp_model.MODEL_INVALID:
            reason = "model_invalid"
        elif stopped_idle:
            reason = "no_improvement"
        elif self.time_limit is not None:
            reason = "time_limit"
        else:
            reason = "search_stopped"

        if best_snapshot is None:
            return FoodPackagingSolution(
                status=cp_model.CpSolver().status_name(status),
                line_routes=None,
                start_times=None,
                hard_penalty=None,
                medium_penalty=None,
                soft_penalty=None,
                elapsed_seconds=elapsed,
                termination_reason=reason,
                mode=cotwin.mode,
            )
        if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            status = cp_model.FEASIBLE  # Retain a proven valid earlier-phase incumbent.
        routes, minute_starts = best_snapshot
        return FoodPackagingSolution(
            status=cp_model.CpSolver().status_name(status),
            line_routes=routes,
            start_times={
                job_id: cotwin.origin + timedelta(minutes=value)
                for job_id, value in minute_starts.items()
            },
            hard_penalty=best_score[0],
            medium_penalty=best_score[1],
            soft_penalty=best_score[2],
            elapsed_seconds=elapsed,
            termination_reason=reason,
            mode=cotwin.mode,
        )
