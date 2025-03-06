import random
from collections import defaultdict, deque
import math
from greyjack.agents.metaheuristic_bases.Mover import Mover
from greyjack.agents.base.Individual import Individual

# mostly rewrited by LLM (Rust->Python) for tests purpose only. Will be replaced by normally wrapped Rust version
class TabuSearchBase:
    def __init__(
        self,
        neighbours_count,
        tabu_entity_rate,
        mutation_rate_multiplier=None,
        move_probas=None,
        semantic_groups_map=None,
        discrete_ids=None,
    ):
        self.neighbours_count = neighbours_count
        self.tabu_entity_rate = tabu_entity_rate
        self.metaheuristic_kind = "LocalSearch"
        self.metaheuristic_name = "TabuSearch"
        self.discrete_ids = discrete_ids

        current_mutation_rate_multiplier = mutation_rate_multiplier if mutation_rate_multiplier is not None else 0.0
        group_mutation_rates_map = {}
        for group_name, group_ids in semantic_groups_map.items():
            group_size = len(group_ids)
            current_group_mutation_rate = current_mutation_rate_multiplier * (1.0 / group_size)
            group_mutation_rates_map[group_name] = current_group_mutation_rate

        self.mover = Mover(
            tabu_entity_rate,
            defaultdict(int),
            defaultdict(set),
            defaultdict(deque),
            group_mutation_rates_map,
            move_probas,
        )

    def sample_candidates_plain(self, population, current_top_individual, variables_manager):
        if not self.mover.tabu_entity_size_map:
            for group_name, group_ids in variables_manager.semantic_groups_map.items():
                self.mover.tabu_ids_sets_map[group_name] = set()
                self.mover.tabu_entity_size_map[group_name] = max(math.ceil(self.tabu_entity_rate * len(group_ids)), 1)
                self.mover.tabu_ids_vecdeque_map[group_name] = deque()

        current_best_candidate = population[0].variable_values
        candidates = []
        for _ in range(self.neighbours_count):
            changed_candidate, changed_columns, _ = self.mover.do_move(current_best_candidate, variables_manager, False)
            candidate = changed_candidate.copy()
            variables_manager.fix_variables(candidate, changed_columns)
            candidates.append(candidate)

        return candidates

    def sample_candidates_incremental(self, population, current_top_individual, variables_manager):
        if not self.mover.tabu_entity_size_map:
            for group_name, group_ids in variables_manager.semantic_groups_map.items():
                self.mover.tabu_ids_sets_map[group_name] = set()
                self.mover.tabu_entity_size_map[group_name] = max(math.ceil(self.tabu_entity_rate * len(group_ids)), 1)
                self.mover.tabu_ids_vecdeque_map[group_name] = deque()

        current_best_candidate = population[0].variable_values
        deltas = []
        for _ in range(self.neighbours_count):
            _, changed_columns, candidate_deltas = self.mover.do_move(current_best_candidate, variables_manager, True)
            candidate_deltas = [(col_id, delta_value) for col_id, delta_value in zip(changed_columns, candidate_deltas)]
            variables_manager.fix_deltas(candidate_deltas, changed_columns)
            deltas.append(candidate_deltas)

        return current_best_candidate.copy(), deltas

    def build_updated_population(self, current_population, candidates):
        candidates.sort()
        best_candidate = candidates[0]
        if best_candidate.score <= current_population[0].score:
            new_population = [best_candidate]
        else:
            new_population = current_population.copy()
        return new_population

    def build_updated_population_incremental(self, current_population, sample, deltas, scores):
        best_score_id = min(range(len(scores)), key=lambda i: scores[i])
        best_score = scores[best_score_id]
        if best_score <= current_population[0].score:
            best_deltas = deltas[best_score_id]
            for var_id, new_value in best_deltas:
                sample[var_id] = new_value
            best_candidate = Individual(sample.copy(), best_score)
            new_population = [best_candidate]
        else:
            new_population = current_population.copy()
        return new_population

    def get_metaheuristic_kind(self):
        return self.metaheuristic_kind

    def get_metaheuristic_name(self):
        return self.metaheuristic_name