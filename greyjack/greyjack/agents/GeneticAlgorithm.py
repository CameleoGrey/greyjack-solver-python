
from greyjack.agents.base.Agent import Agent
from greyjack.agents.metaheuristic_bases.GeneticAlgorithmBase import GeneticAlgorithmBase
from greyjack.score_calculation.score_requesters.OOPScoreRequester import OOPScoreRequester
from greyjack.score_calculation.score_requesters.PureMathScoreRequester import PureMathScoreRequester
from greyjack.cotwin.CotwinBase import CotwinBase
from greyjack.pure_math.MathModel import MathModel

class GeneticAlgorithm(Agent):
    def __init__(
        self,
        population_size=128, crossover_probability=0.5, p_best_rate=0.05,
        tabu_entity_rate=0.0, mutation_rate_multiplier=None, move_probas=None,
        migration_rate=0.00001, migration_frequency=10, termination_strategy=None,
    ):
        
        super().__init__(migration_rate, migration_frequency, termination_strategy, compare_to_global_frequency=1)

        self.population_size = population_size
        self.crossover_probability = crossover_probability
        self.p_best_rate = p_best_rate
        self.tabu_entity_rate = tabu_entity_rate
        self.mutation_rate_multiplier = mutation_rate_multiplier
        self.move_probas = move_probas
        # Didn't check, in theory ruins island concept for genetic algorithm (better turn off)
        self.is_win_from_comparing_with_global = False

    def _build_metaheuristic_base(self):
        
        # when I use issubclass() solver dies silently, so check specific attributes
        if hasattr(self.cotwin, "planning_entities"):
            self.score_requester = OOPScoreRequester(self.cotwin)
            score_variant = self.cotwin.score_calculator.score_variant
        elif isinstance(self.cotwin, MathModel):
            self.score_requester = PureMathScoreRequester(self.cotwin)
            score_variant = self.cotwin.score_variant
            self.cotwin.score_calculator.is_incremental = False
        else:
            raise Exception("Cotwin must be either subclass of CotwinBase, either be instance of MathModel")

        semantic_groups_dict = self.score_requester.variables_manager.semantic_groups_map.copy()
        discrete_ids = self.score_requester.variables_manager.discrete_ids

        self.metaheuristic_base = GeneticAlgorithmBase.new(
            score_variant,
            self.score_requester.variables_manager,
            self.population_size, 
            self.crossover_probability, 
            self.p_best_rate,
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