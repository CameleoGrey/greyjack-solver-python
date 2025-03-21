
from greyjack.agents.base.Agent import Agent
from greyjack.agents.metaheuristic_bases.SimulatedAnnealingBase import SimulatedAnnealingBase
from greyjack.score_calculation.score_requesters.OOPScoreRequester import OOPScoreRequester


class SimulatedAnnealing(Agent):
    def __init__(
        self,
        initial_temperature,
        cooling_rate,
        tabu_entity_rate,
        mutation_rate_multiplier=None,
        move_probas=None,
        migration_frequency=None,
        compare_to_global_frequency=10, # too often comparing significally decreases common performance for fast-stepping metaheuristics
        termination_strategy=None,
    ):  
        
        super().__init__(1.0, migration_frequency, termination_strategy, compare_to_global_frequency)

        self.population_size = 1
        self.initial_temperature = initial_temperature
        self.cooling_rate = cooling_rate
        self.tabu_entity_rate = tabu_entity_rate
        self.mutation_rate_multiplier = mutation_rate_multiplier
        self.move_probas = move_probas

        # If true - stucks more often in local minimums, but converges much faster
        # may be useful in multiple stages solving
        self.is_win_from_comparing_with_global = True

    def _build_metaheuristic_base(self):
        self.score_requester = OOPScoreRequester(self.cotwin)
        semantic_groups_dict = self.score_requester.variables_manager.semantic_groups_map.copy()
        discrete_ids = self.score_requester.variables_manager.discrete_ids.copy()

        """
        new(score_variant, variables_manager_py, 
            initial_temperature, tabu_entity_rate, 
            semantic_groups_dict, cooling_rate=None, 
            mutation_rate_multiplier=None, 
            move_probas=None, discrete_ids=None):
        """

        self.metaheuristic_base = SimulatedAnnealingBase.new(
            self.cotwin.score_calculator.score_variant,
            self.score_requester.variables_manager,
            self.initial_temperature,
            self.tabu_entity_rate,
            semantic_groups_dict,
            self.cooling_rate,
            self.mutation_rate_multiplier,
            self.move_probas.copy() if self.move_probas else None,
            discrete_ids,
        )

        # to remove redundant clonning
        self.metaheuristic_name = self.metaheuristic_base.metaheuristic_name
        self.metaheuristic_kind = self.metaheuristic_base.metaheuristic_kind

        return self