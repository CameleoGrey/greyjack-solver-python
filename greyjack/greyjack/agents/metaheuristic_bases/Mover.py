import random
from collections import deque

# mostly rewrited by LLM (Rust->Python) for tests purpose only. Will be replaced by normally wrapped Rust version
class Mover:
    def __init__(
        self,
        tabu_entity_rate,
        tabu_entity_size_map,
        tabu_ids_sets_map,
        tabu_ids_vecdeque_map,
        group_mutation_rates_map,
        move_probas,
    ):
        self.tabu_entity_rate = tabu_entity_rate
        self.tabu_entity_size_map = tabu_entity_size_map
        self.tabu_ids_sets_map = tabu_ids_sets_map
        self.tabu_ids_vecdeque_map = tabu_ids_vecdeque_map
        self.group_mutation_rates_map = group_mutation_rates_map
        self.moves_count = 6
        self.move_probas_tresholds = self._calculate_move_probas_tresholds(move_probas)

    def _calculate_move_probas_tresholds(self, move_probas):
        if move_probas is None:
            increments = [round(1.0 / self.moves_count, 3)] * self.moves_count
            increments[0] += 1.0 - sum(increments)
        else:
            assert len(move_probas) == self.moves_count, "Optional move probas vector length is not equal to available moves count"
            assert round(sum(move_probas), 1) == 1.0, "Optional move probas sum must be equal to 1.0"
            increments = move_probas

        proba_thresholds = []
        accumulator = 0.0
        for proba in increments:
            accumulator += proba
            proba_thresholds.append(accumulator)
        return proba_thresholds

    def select_non_tabu_ids(self, group_name, selection_size, right_end):
        random_ids = []
        while len(random_ids) < selection_size:
            random_id = random.randint(0, right_end - 1)
            if random_id not in self.tabu_ids_sets_map[group_name]:
                self.tabu_ids_sets_map[group_name].add(random_id)
                self.tabu_ids_vecdeque_map[group_name].appendleft(random_id)
                random_ids.append(random_id)

                if len(self.tabu_ids_vecdeque_map[group_name]) > self.tabu_entity_size_map[group_name]:
                    removed_id = self.tabu_ids_vecdeque_map[group_name].pop()
                    self.tabu_ids_sets_map[group_name].remove(removed_id)
        return random_ids

    def do_move(self, candidate, variables_manager, incremental):
        random_value = random.random()
        if random_value <= self.move_probas_tresholds[0]:
            return self.change_move(candidate, variables_manager, incremental)
        elif random_value <= self.move_probas_tresholds[1]:
            return self.swap_move(candidate, variables_manager, incremental)
        elif random_value <= self.move_probas_tresholds[2]:
            return self.swap_edges_move(candidate, variables_manager, incremental)
        elif random_value <= self.move_probas_tresholds[3]:
            return self.scramble_move(candidate, variables_manager, incremental)
        elif random_value <= self.move_probas_tresholds[4]:
            return self.insertion_move(candidate, variables_manager, incremental)
        elif random_value <= self.move_probas_tresholds[5]:
            return self.inverse_move(candidate, variables_manager, incremental)
        else:
            raise ValueError("Something wrong with probabilities")

    def get_necessary_info_for_move(self, variables_manager):
        group_ids, group_name = variables_manager.get_random_semantic_group_ids()
        group_mutation_rate = self.group_mutation_rates_map[group_name]
        random_values = [random.random() for _ in range(variables_manager.variables_count)]
        crossover_mask = [val < group_mutation_rate for val in random_values]
        current_change_count = sum(crossover_mask)
        return group_ids, group_name, current_change_count

    def change_move(self, candidate, variables_manager, incremental):
        group_ids, group_name, current_change_count = self.get_necessary_info_for_move(variables_manager)

        if current_change_count < 1:
            current_change_count = 1
        if len(group_ids) < current_change_count:
            return None, None, None

        if self.tabu_entity_rate == 0.0:
            changed_columns = random.sample(range(len(group_ids)), current_change_count)
        else:
            changed_columns = self.select_non_tabu_ids(group_name, current_change_count, len(group_ids))
        changed_columns = [group_ids[i] for i in changed_columns]

        if incremental:
            deltas = [variables_manager.get_column_random_value(i) for i in changed_columns]
            return None, changed_columns, deltas
        else:
            changed_candidate = candidate.copy()
            for i in changed_columns:
                changed_candidate[i] = variables_manager.get_column_random_value(i)
            return changed_candidate, changed_columns, None

    def swap_move(self, candidate, variables_manager, incremental):
        group_ids, group_name, current_change_count = self.get_necessary_info_for_move(variables_manager)

        if current_change_count < 2:
            current_change_count = 2
        if len(group_ids) < current_change_count:
            return None, None, None

        if self.tabu_entity_rate == 0.0:
            changed_columns = random.sample(range(len(group_ids)), current_change_count)
        else:
            changed_columns = self.select_non_tabu_ids(group_name, current_change_count, len(group_ids))
        changed_columns = [group_ids[i] for i in changed_columns]

        if incremental:
            deltas = [candidate[i] for i in changed_columns]
            for i in range(1, current_change_count):
                deltas[i - 1], deltas[i] = deltas[i], deltas[i - 1]
            return None, changed_columns, deltas
        else:
            changed_candidate = candidate.copy()
            for i in range(1, current_change_count):
                changed_candidate[changed_columns[i - 1]], changed_candidate[changed_columns[i]] = (
                    changed_candidate[changed_columns[i]],
                    changed_candidate[changed_columns[i - 1]],
                )
            return changed_candidate, changed_columns, None

    def swap_edges_move(self, candidate, variables_manager, incremental):
        group_ids, group_name, current_change_count = self.get_necessary_info_for_move(variables_manager)

        if len(group_ids) == 0:
            return None, None, None
        if current_change_count < 2:
            current_change_count = 2
        if current_change_count > len(group_ids) - 1:
            current_change_count = len(group_ids) - 1

        if self.tabu_entity_rate == 0.0:
            columns_to_change = random.sample(range(len(group_ids) - 1), current_change_count)
        else:
            columns_to_change = self.select_non_tabu_ids(group_name, current_change_count, len(group_ids) - 1)

        edges = []
        changed_columns = []
        for i in range(current_change_count):
            edge = (group_ids[columns_to_change[i]], group_ids[columns_to_change[i] + 1])
            edges.append(edge)
            changed_columns.extend(edge)
        edges = edges[1:] + edges[:1]

        if incremental:
            deltas = []
            for edge in edges:
                deltas.extend([candidate[edge[0]], candidate[edge[1]]])
            for i in range(1, current_change_count):
                deltas[2 * (i - 1)], deltas[2 * i] = deltas[2 * i], deltas[2 * (i - 1)]
                deltas[2 * (i - 1) + 1], deltas[2 * i + 1] = deltas[2 * i + 1], deltas[2 * (i - 1) + 1]
            return None, changed_columns, deltas
        else:
            changed_candidate = candidate.copy()
            for i in range(1, current_change_count):
                left_edge = edges[i - 1]
                right_edge = edges[i]
                changed_candidate[left_edge[0]], changed_candidate[right_edge[0]] = (
                    changed_candidate[right_edge[0]],
                    changed_candidate[left_edge[0]],
                )
                changed_candidate[left_edge[1]], changed_candidate[right_edge[1]] = (
                    changed_candidate[right_edge[1]],
                    changed_candidate[left_edge[1]],
                )
            return changed_candidate, changed_columns, None

    def scramble_move(self, candidate, variables_manager, incremental):
        current_change_count = random.randint(3, 6)
        group_ids, group_name = variables_manager.get_random_semantic_group_ids()

        if len(group_ids) < current_change_count - 1:
            return None, None, None

        if self.tabu_entity_rate == 0.0:
            current_start_id = random.randint(0, len(group_ids) - current_change_count)
        else:
            current_start_id = self.select_non_tabu_ids(group_name, 1, len(group_ids) - current_change_count)[0]

        native_columns = [group_ids[current_start_id + i] for i in range(current_change_count)]
        scrambled_columns = native_columns.copy()
        random.shuffle(scrambled_columns)

        if incremental:
            deltas = [candidate[i] for i in scrambled_columns]
            return None, scrambled_columns, deltas
        else:
            changed_columns = native_columns.copy()
            changed_candidate = candidate.copy()
            for oi, si in zip(native_columns, scrambled_columns):
                changed_candidate[oi], changed_candidate[si] = changed_candidate[si], changed_candidate[oi]
            return changed_candidate, changed_columns, None

    def insertion_move(self, candidate, variables_manager, incremental):
        group_ids, group_name = variables_manager.get_random_semantic_group_ids()
        current_change_count = 2

        if len(group_ids) <= 1:
            return None, None, None

        if self.tabu_entity_rate == 0.0:
            chosen_position = random.randint(0, len(group_ids) - 1)
        else:
            chosen_position = self.select_non_tabu_ids(group_name, 1, len(group_ids) - 1)[0]

        chosen_ids = random.sample(group_ids, current_change_count)
        
        if incremental:
            deltas = []
            for i in range(current_change_count):
                deltas.append(candidate[chosen_ids[i]])
            return None, [chosen_position], deltas
        else:
            changed_candidate = candidate.copy()
            for i in range(current_change_count):
                # Move elements to the new position
                changed_candidate.insert(chosen_position, changed_candidate.pop(chosen_ids[i]))
            return changed_candidate, [chosen_position], None

    def inverse_move(self, candidate, variables_manager, incremental):
        group_ids, group_name = variables_manager.get_random_semantic_group_ids()

        if len(group_ids) <= 1:
            return None, None, None

        range_to_reverse = random.sample(group_ids, 2)
        range_to_reverse.sort()

        if incremental:
            deltas = [candidate[i] for i in range_to_reverse]
            deltas.reverse()
            return None, range_to_reverse, deltas
        else:
            changed_candidate = candidate.copy()
            to_reverse = changed_candidate[range_to_reverse[0]:range_to_reverse[1] + 1]
            to_reverse.reverse()
            changed_candidate[range_to_reverse[0]:range_to_reverse[1] + 1] = to_reverse
            return changed_candidate, range_to_reverse, None