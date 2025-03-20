
from greyjack.agents.base.Agent import Agent
from greyjack.agents.metaheuristic_bases.LateAcceptanceBase import LateAcceptanceBase
from greyjack.score_calculation.score_requesters.OOPScoreRequester import OOPScoreRequester

class LateAcceptance(Agent):
    def __init__(
        self,
        late_acceptance_size,
        tabu_entity_rate,
        mutation_rate_multiplier=None,
        move_probas=None,
        migration_frequency=999_999_999_999, # probably, better use only comparing with global. Need more researching.
        compare_to_global_frequency=10, # too often comparing significally decreases common performance for fast-stepping metaheuristics
        termination_strategy=None,
    ):
        
        super().__init__(1.0, migration_frequency, termination_strategy, compare_to_global_frequency)

        self.population_size = 1
        self.late_acceptance_size = late_acceptance_size
        self.tabu_entity_rate = tabu_entity_rate
        self.mutation_rate_multiplier = mutation_rate_multiplier
        self.move_probas = move_probas
        self.is_win_from_comparing_with_global = True # Much faster convergence without stucking in local optimums (with high migration frequency)

    def _build_metaheuristic_base(self):
        self.score_requester = OOPScoreRequester(self.cotwin)
        semantic_groups_dict = self.score_requester.variables_manager.semantic_groups_map.copy()
        discrete_ids = self.score_requester.variables_manager.discrete_ids.copy()

        self.metaheuristic_base = LateAcceptanceBase.new(
            self.cotwin.score_calculator.score_variant,
            self.score_requester.variables_manager,
            self.late_acceptance_size,
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