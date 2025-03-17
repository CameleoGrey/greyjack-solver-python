
from greyjack.agents.base.Agent import Agent
from greyjack.agents.metaheuristic_bases.TabuSearchBase import TabuSearchBase
from greyjack.score_calculation.score_requesters.OOPScoreRequester import OOPScoreRequester

class TabuSearch(Agent):
    def __init__(
        self,
        neighbours_count,
        tabu_entity_rate,
        mutation_rate_multiplier=None,
        move_probas=None,
        compare_to_global=False,
        migration_frequency=None,
        termination_strategy=None,
    ):
        
        super().__init__(1.0, migration_frequency, termination_strategy)

        self.population_size = 1
        self.neighbours_count = neighbours_count
        self.tabu_entity_rate = tabu_entity_rate
        self.mutation_rate_multiplier = mutation_rate_multiplier
        self.move_probas = move_probas

        # If true - stucks more often in local minimums, but converges much faster
        # may be useful in multiple stages solving
        self.is_win_from_comparing_with_global = compare_to_global

    def _build_metaheuristic_base(self):
        self.score_requester = OOPScoreRequester(self.cotwin)
        semantic_groups_dict = self.score_requester.variables_manager.semantic_groups_map.copy()
        discrete_ids = self.score_requester.variables_manager.discrete_ids.copy()

        self.metaheuristic_base = TabuSearchBase.new(
            self.cotwin.score_calculator.score_variant,
            self.score_requester.variables_manager,
            self.neighbours_count,
            self.tabu_entity_rate,
            semantic_groups_dict,
            self.mutation_rate_multiplier,
            self.move_probas.copy() if self.move_probas else None,
            discrete_ids,
        )

        # to remove redundant clonning
        self.metaheuristic_name = self.metaheuristic_base.metaheuristic_name
        self.metaheuristic_kind = self.metaheuristic_base.metaheuristic_kind

        return self