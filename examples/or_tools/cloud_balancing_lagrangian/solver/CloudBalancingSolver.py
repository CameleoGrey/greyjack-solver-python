"""Projected-subgradient Lagrangian search with business-score replay."""

from copy import deepcopy
from decimal import Decimal, ROUND_CEILING, localcontext
from math import isfinite, sqrt
from time import monotonic

from ortools.linear_solver import pywraplp

from ..cotwin.CotScheduleCB import CotScheduleCB
from .CloudBalancingSolution import CloudBalancingSolution
from .ScoreNoImprovement import ScoreNoImprovement


class CloudBalancingSolver:
    def __init__(
        self,
        no_improvement_seconds: float = 15,
        time_limit: float | None = None,
        max_iterations: int | None = None,
    ) -> None:
        for name, value in (
            ("no_improvement_seconds", no_improvement_seconds),
            ("time_limit", time_limit),
        ):
            if value is None and name == "time_limit":
                continue
            if type(value) not in (int, float) or not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number")
        if max_iterations is not None and (
            type(max_iterations) is not int or max_iterations < 1
        ):
            raise ValueError("max_iterations must be a positive integer")
        self.no_improvement_seconds = no_improvement_seconds
        self.time_limit = time_limit
        self.max_iterations = max_iterations

    def solve(self, cotwin: CotScheduleCB) -> CloudBalancingSolution:
        started = monotonic()
        total_deadline = (
            float("inf") if self.time_limit is None else started + self.time_limit
        )
        logger = ScoreNoImprovement(started, self.no_improvement_seconds)
        iterations = 0
        best_bound: Decimal | None = None
        best_bound_float = float("-inf")
        capacity_prices = {
            c.computer_id: [0.0, 0.0, 0.0] for c in cotwin.domain.computers
        }
        activation_prices = {
            c.computer_id: (
                c.cost / cotwin.process_count if cotwin.process_count else 0.0
            )
            for c in cotwin.domain.computers
        }

        if cotwin.mode == "strict" and self._proven_infeasible(cotwin):
            return self._result(cotwin, logger, started, "infeasible", iterations, None)

        if not cotwin.domain.processes:
            logger.record((0, 0), {})
            return self._result(
                cotwin, logger, started, "optimal", iterations, Decimal(0)
            )

        if cotwin.use_greedy_seed and self._remaining(logger, total_deadline) > 0:
            seed = self._first_fit(cotwin)
            if seed is not None:
                self._record(cotwin, logger, seed)

        reason = "search_stopped"
        while self._remaining(logger, total_deadline) > 0:
            if self.max_iterations is not None and iterations >= self.max_iterations:
                reason = "iteration_limit"
                break
            self._set_relaxed_objective(cotwin, capacity_prices, activation_prices)
            cotwin.model.SetTimeLimit(
                max(1, int(1000 * self._remaining(logger, total_deadline)))
            )
            status = cotwin.model.Solve()
            if status != pywraplp.Solver.OPTIMAL:
                reason = "dual_unresolved"
                break
            iterations += 1
            if self._remaining(logger, total_deadline) <= 0:
                reason = self._deadline_reason(logger, total_deadline)
                break

            candidate = self._recover_assignment(
                cotwin, capacity_prices, activation_prices
            )
            if candidate is not None:
                self._record(cotwin, logger, candidate)
            if self._remaining(logger, total_deadline) <= 0:
                reason = self._deadline_reason(logger, total_deadline)
                break

            dual_float = self._dual_value_float(
                cotwin, capacity_prices, activation_prices
            )
            if dual_float > best_bound_float + 1e-7:
                bound = self._dual_value_exact(
                    cotwin, capacity_prices, activation_prices
                )
                if best_bound is None or bound > best_bound:
                    best_bound = bound
                best_bound_float = dual_float

            if logger.best_score is not None and best_bound is not None:
                upper = self._weighted(cotwin, logger.best_score)
                if best_bound > upper:
                    raise RuntimeError("Lagrangian lower bound exceeds replayed score")
                if best_bound.to_integral_value(rounding=ROUND_CEILING) >= upper:
                    reason = "optimal"
                    break

            gradients = self._subgradients(cotwin, capacity_prices, activation_prices)
            self._update_prices(
                cotwin,
                capacity_prices,
                activation_prices,
                gradients,
                dual_float,
                logger.best_score,
                iterations,
                min(logger.deadline, total_deadline),
            )

        if reason == "search_stopped":
            reason = self._deadline_reason(logger, total_deadline)
        return self._result(cotwin, logger, started, reason, iterations, best_bound)

    @staticmethod
    def _remaining(logger: ScoreNoImprovement, total_deadline: float) -> float:
        return max(0.0, min(logger.deadline, total_deadline) - monotonic())

    @staticmethod
    def _deadline_reason(logger: ScoreNoImprovement, total_deadline: float) -> str:
        return "time_limit" if total_deadline <= logger.deadline else "no_improvement"

    @staticmethod
    def _proven_infeasible(cotwin: CotScheduleCB) -> bool:
        computers = cotwin.domain.computers
        processes = cotwin.domain.processes
        if any(
            not any(
                all(
                    demand <= capacity
                    for demand, capacity in zip(p.requirements, c.resources)
                )
                for c in computers
            )
            for p in processes
        ):
            return True
        return any(
            sum(p.requirements[r] for p in processes)
            > sum(c.resources[r] for c in computers)
            for r in range(3)
        )

    @staticmethod
    def _weighted(cotwin: CotScheduleCB, score: tuple[int, int]) -> int:
        return (
            score[1]
            if cotwin.mode == "strict"
            else cotwin.hard_weight * score[0] + score[1]
        )

    @staticmethod
    def _record(
        cotwin: CotScheduleCB,
        logger: ScoreNoImprovement,
        assignments: dict[int, int],
    ) -> None:
        domain = deepcopy(cotwin.domain)
        if set(assignments) != {p.process_id for p in domain.processes}:
            raise ValueError("Incomplete process assignment")
        for process in domain.processes:
            process.computer_id = assignments[process.process_id]
        metrics = domain.calculate_metrics()
        score = metrics["hard_penalty"], metrics["soft_cost"]
        if cotwin.mode == "strict" and score[0] != 0:
            return
        logger.record(score, assignments)

    @staticmethod
    def _first_fit(cotwin: CotScheduleCB) -> dict[int, int] | None:
        computers = cotwin.domain.computers
        loads = {c.computer_id: [0, 0, 0] for c in computers}
        counts = {c.computer_id: 0 for c in computers}
        assignments = {}
        for process in cotwin.domain.processes:
            demand = process.requirements
            selected = next(
                (
                    c
                    for c in computers
                    if all(
                        loads[c.computer_id][r] + demand[r] <= c.resources[r]
                        for r in range(3)
                    )
                ),
                None,
            )
            if selected is None:
                if cotwin.mode == "strict":
                    return None
                selected = min(
                    computers,
                    key=lambda c: (
                        CloudBalancingSolver._incremental_overload(
                            loads[c.computer_id], demand, c.resources
                        )
                        * cotwin.hard_weight
                        + (c.cost if counts[c.computer_id] == 0 else 0),
                        c.computer_id,
                    ),
                )
            cid = selected.computer_id
            assignments[process.process_id] = cid
            counts[cid] += 1
            for r in range(3):
                loads[cid][r] += demand[r]
        return CloudBalancingSolver._evacuate_feasible(
            cotwin, assignments, loads, counts
        )

    @staticmethod
    def _incremental_overload(
        load: list[int], demand: tuple[int, int, int], capacity: tuple[int, int, int]
    ) -> int:
        return sum(
            max(0, load[r] + demand[r] - capacity[r]) - max(0, load[r] - capacity[r])
            for r in range(3)
        )

    @staticmethod
    def _set_relaxed_objective(
        cotwin: CotScheduleCB,
        capacity_prices: dict[int, list[float]],
        activation_prices: dict[int, float],
    ) -> None:
        objective = cotwin.model.Objective()
        for group in cotwin.groups:
            for cid, variable in group.choices.items():
                objective.SetCoefficient(
                    variable,
                    activation_prices[cid]
                    + sum(
                        capacity_prices[cid][r] * group.requirements[r]
                        for r in range(3)
                    ),
                )
        for computer in cotwin.domain.computers:
            cid = computer.computer_id
            objective.SetCoefficient(
                cotwin.activation[cid],
                computer.cost - cotwin.process_count * activation_prices[cid],
            )
        objective.SetOffset(
            -sum(
                capacity_prices[c.computer_id][r] * c.resources[r]
                for c in cotwin.domain.computers
                for r in range(3)
            )
        )

    @staticmethod
    def _dual_value_float(
        cotwin: CotScheduleCB,
        capacity_prices: dict[int, list[float]],
        activation_prices: dict[int, float],
    ) -> float:
        value = -sum(
            capacity_prices[c.computer_id][r] * c.resources[r]
            for c in cotwin.domain.computers
            for r in range(3)
        )
        for group in cotwin.groups:
            value += len(group.process_ids) * min(
                activation_prices[c.computer_id]
                + sum(
                    capacity_prices[c.computer_id][r] * group.requirements[r]
                    for r in range(3)
                )
                for c in cotwin.domain.computers
            )
        value += sum(
            min(0.0, c.cost - cotwin.process_count * activation_prices[c.computer_id])
            for c in cotwin.domain.computers
        )
        return value

    @staticmethod
    def _dual_value_exact(
        cotwin: CotScheduleCB,
        capacity_prices: dict[int, list[float]],
        activation_prices: dict[int, float],
    ) -> Decimal:
        with localcontext() as context:
            context.prec = 100
            mu = {
                cid: tuple(Decimal(str(value)) for value in prices)
                for cid, prices in capacity_prices.items()
            }
            lam = {cid: Decimal(str(value)) for cid, value in activation_prices.items()}
            value = -sum(
                mu[c.computer_id][r] * c.resources[r]
                for c in cotwin.domain.computers
                for r in range(3)
            )
            for group in cotwin.groups:
                value += len(group.process_ids) * min(
                    lam[c.computer_id]
                    + sum(
                        mu[c.computer_id][r] * group.requirements[r] for r in range(3)
                    )
                    for c in cotwin.domain.computers
                )
            value += sum(
                min(Decimal(0), c.cost - cotwin.process_count * lam[c.computer_id])
                for c in cotwin.domain.computers
            )
            return +value

    @staticmethod
    def _subgradients(
        cotwin: CotScheduleCB,
        capacity_prices: dict[int, list[float]],
        activation_prices: dict[int, float],
    ) -> tuple[dict[int, list[float]], dict[int, float]]:
        # GLOP returns an extreme point. At a price tie that can put every
        # process on one identical computer, yielding an unhelpful ascent
        # direction. Average optimal choices across the tied computers instead.
        loads = {c.computer_id: [0.0, 0.0, 0.0] for c in cotwin.domain.computers}
        counts = {c.computer_id: 0.0 for c in cotwin.domain.computers}
        for group in cotwin.groups:
            costs = {
                c.computer_id: activation_prices[c.computer_id]
                + sum(
                    capacity_prices[c.computer_id][r] * group.requirements[r]
                    for r in range(3)
                )
                for c in cotwin.domain.computers
            }
            minimum = min(costs.values())
            tolerance = 1e-12 * max(1.0, abs(minimum))
            tied = [cid for cid, cost in costs.items() if cost <= minimum + tolerance]
            share = len(group.process_ids) / len(tied)
            for cid in tied:
                counts[cid] += share
                for r in range(3):
                    loads[cid][r] += share * group.requirements[r]
        capacity = {
            c.computer_id: [loads[c.computer_id][r] - c.resources[r] for r in range(3)]
            for c in cotwin.domain.computers
        }
        activation = {
            c.computer_id: counts[c.computer_id]
            - cotwin.process_count
            * (
                0.0
                if c.cost - cotwin.process_count * activation_prices[c.computer_id]
                > 1e-9
                else 1.0
                if c.cost - cotwin.process_count * activation_prices[c.computer_id]
                < -1e-9
                else counts[c.computer_id] / cotwin.process_count
            )
            for c in cotwin.domain.computers
        }
        return capacity, activation

    @staticmethod
    def _update_prices(
        cotwin: CotScheduleCB,
        capacity_prices: dict[int, list[float]],
        activation_prices: dict[int, float],
        gradients: tuple[dict[int, list[float]], dict[int, float]],
        dual_value: float,
        best_score: tuple[int, int] | None,
        iteration: int,
        deadline: float,
    ) -> None:
        capacity_gradients, activation_gradients = gradients
        norm_squared = sum(
            value * value for row in capacity_gradients.values() for value in row
        ) + sum(value * value for value in activation_gradients.values())
        if norm_squared == 0:
            return
        if best_score is None:
            step = cotwin.hard_weight / (sqrt(norm_squared) * sqrt(iteration))
        else:
            gap = max(
                0.0, CloudBalancingSolver._weighted(cotwin, best_score) - dual_value
            )
            step = gap / (norm_squared * sqrt(iteration))
        initial_step = min(1.0, step)
        costs = {c.computer_id: c.cost for c in cotwin.domain.computers}
        best_value = dual_value
        chosen = None
        for reduction in range(24):
            if monotonic() >= deadline:
                break
            step = initial_step / (1 << reduction)
            candidate_capacity = {}
            candidate_activation = {}
            for cid, row in capacity_prices.items():
                candidate_capacity[cid] = [
                    (
                        min(
                            float(cotwin.hard_weight),
                            max(0.0, row[r] + step * capacity_gradients[cid][r]),
                        )
                        if cotwin.mode == "penalized"
                        else max(0.0, row[r] + step * capacity_gradients[cid][r])
                    )
                    for r in range(3)
                ]
                # Beyond cost/P the activation choice is used=1 and the
                # assignment term has slope at most P, so the dual cannot rise.
                candidate_activation[cid] = min(
                    costs[cid] / cotwin.process_count,
                    max(0.0, activation_prices[cid] + step * activation_gradients[cid]),
                )
            value = CloudBalancingSolver._dual_value_float(
                cotwin, candidate_capacity, candidate_activation
            )
            if value > best_value + 1e-9:
                best_value = value
                chosen = candidate_capacity, candidate_activation
        if chosen is not None:
            capacity_prices.update(chosen[0])
            activation_prices.update(chosen[1])

    def _recover_assignment(
        self,
        cotwin: CotScheduleCB,
        capacity_prices: dict[int, list[float]],
        activation_prices: dict[int, float],
    ) -> dict[int, int] | None:
        computers = cotwin.domain.computers
        by_id = {c.computer_id: c for c in computers}
        reduced_costs = {}
        preferences = {}
        regrets = {}
        for group in cotwin.groups:
            costs = {
                c.computer_id: activation_prices[c.computer_id]
                + sum(
                    capacity_prices[c.computer_id][r] * group.requirements[r]
                    for r in range(3)
                )
                for c in computers
            }
            ordered = sorted(costs.values())
            regret = ordered[1] - ordered[0] if len(ordered) > 1 else 0.0
            for pid in group.process_ids:
                reduced_costs[pid] = costs
                preferences[pid] = {
                    cid: variable.solution_value()
                    for cid, variable in group.choices.items()
                }
                regrets[pid] = regret

        processes = sorted(
            cotwin.domain.processes,
            key=lambda p: (-regrets[p.process_id], -sum(p.requirements), p.process_id),
        )
        loads = {c.computer_id: [0, 0, 0] for c in computers}
        counts = {c.computer_id: 0 for c in computers}
        assignments = {}
        for process in processes:
            demand = process.requirements
            choices = [
                c
                for c in computers
                if cotwin.mode != "strict"
                or all(
                    loads[c.computer_id][r] + demand[r] <= c.resources[r]
                    for r in range(3)
                )
            ]
            if not choices:
                return None
            selected = min(
                choices,
                key=lambda c: (
                    cotwin.hard_weight
                    * self._incremental_overload(
                        loads[c.computer_id], demand, c.resources
                    )
                    + (c.cost if counts[c.computer_id] == 0 else 0),
                    -preferences[process.process_id][c.computer_id],
                    reduced_costs[process.process_id][c.computer_id],
                    c.computer_id,
                ),
            )
            cid = selected.computer_id
            assignments[process.process_id] = cid
            counts[cid] += 1
            for r in range(3):
                loads[cid][r] += demand[r]

        self._improve_one_pass(cotwin, assignments, loads, counts, by_id)
        return self._evacuate_feasible(cotwin, assignments, loads, counts)

    @staticmethod
    def _improve_one_pass(
        cotwin: CotScheduleCB,
        assignments: dict[int, int],
        loads: dict[int, list[int]],
        counts: dict[int, int],
        by_id: dict[int, object],
    ) -> dict[int, int]:
        for process in cotwin.domain.processes:
            old_id = assignments[process.process_id]
            old = by_id[old_id]
            demand = process.requirements
            old_load = loads[old_id]
            old_overload = sum(max(0, old_load[r] - old.resources[r]) for r in range(3))
            reduced_overload = sum(
                max(0, old_load[r] - demand[r] - old.resources[r]) for r in range(3)
            )
            removed_hard = reduced_overload - old_overload
            removed_cost = -old.cost if counts[old_id] == 1 else 0
            best_delta = (0, 0)
            best_id = old_id
            for target in cotwin.domain.computers:
                cid = target.computer_id
                if cid == old_id:
                    continue
                if cotwin.mode == "strict" and any(
                    loads[cid][r] + demand[r] > target.resources[r] for r in range(3)
                ):
                    continue
                hard = removed_hard + CloudBalancingSolver._incremental_overload(
                    loads[cid], demand, target.resources
                )
                soft = removed_cost + (target.cost if counts[cid] == 0 else 0)
                delta = (hard, soft)
                if delta < best_delta:
                    best_delta = delta
                    best_id = cid
            if best_id != old_id:
                assignments[process.process_id] = best_id
                counts[old_id] -= 1
                counts[best_id] += 1
                for r in range(3):
                    loads[old_id][r] -= demand[r]
                    loads[best_id][r] += demand[r]
        return assignments

    @staticmethod
    def _evacuate_feasible(
        cotwin: CotScheduleCB,
        assignments: dict[int, int],
        loads: dict[int, list[int]],
        counts: dict[int, int],
    ) -> dict[int, int]:
        """Close costly computers when their whole process set fits elsewhere."""
        computers = cotwin.domain.computers
        if any(
            loads[c.computer_id][r] > c.resources[r]
            for c in computers
            for r in range(3)
        ):
            return assignments
        for source in sorted(computers, key=lambda c: (-c.cost, c.computer_id)):
            source_id = source.computer_id
            if source.cost == 0 or counts[source_id] == 0:
                continue
            processes = sorted(
                (
                    p
                    for p in cotwin.domain.processes
                    if assignments[p.process_id] == source_id
                ),
                key=lambda p: (-sum(p.requirements), p.process_id),
            )
            trial_loads = {cid: row.copy() for cid, row in loads.items()}
            trial_counts = counts.copy()
            trial_counts[source_id] = 0
            trial_loads[source_id] = [0, 0, 0]
            moves = {}
            for process in processes:
                demand = process.requirements
                choices = [
                    c
                    for c in computers
                    if c.computer_id != source_id
                    and trial_counts[c.computer_id] > 0
                    and all(
                        trial_loads[c.computer_id][r] + demand[r] <= c.resources[r]
                        for r in range(3)
                    )
                ]
                if not choices:
                    break
                target = min(
                    choices,
                    key=lambda c: (
                        sum(
                            (c.resources[r] - trial_loads[c.computer_id][r] - demand[r])
                            / max(1, c.resources[r])
                            for r in range(3)
                        ),
                        c.computer_id,
                    ),
                )
                cid = target.computer_id
                moves[process.process_id] = cid
                trial_counts[cid] += 1
                for r in range(3):
                    trial_loads[cid][r] += demand[r]
            if len(moves) == len(processes):
                assignments.update(moves)
                loads.update(trial_loads)
                counts.update(trial_counts)
        return assignments

    @staticmethod
    def _result(
        cotwin: CotScheduleCB,
        logger: ScoreNoImprovement,
        started: float,
        reason: str,
        iterations: int,
        bound: Decimal | None,
    ) -> CloudBalancingSolution:
        if reason == "optimal":
            status = "OPTIMAL"
        elif reason == "infeasible":
            status = "INFEASIBLE"
        elif logger.best_assignments is not None:
            status = "FEASIBLE"
        else:
            status = "UNKNOWN"
        return CloudBalancingSolution(
            status,
            logger.best_assignments,
            None if logger.best_score is None else logger.best_score[0],
            None if logger.best_score is None else logger.best_score[1],
            monotonic() - started,
            reason,
            cotwin.mode,
            iterations,
            bound,
        )
