
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
        migration_frequency=None,
        termination_strategy=None,
    ):
        
        super().__init__(1.0, migration_frequency, termination_strategy)

        self.population_size = 1
        self.late_acceptance_size = late_acceptance_size
        self.tabu_entity_rate = tabu_entity_rate
        self.mutation_rate_multiplier = mutation_rate_multiplier
        self.move_probas = move_probas

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

        return self