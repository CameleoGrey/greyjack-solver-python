
from greyjack.agents.base.Agent import Agent
from greyjack.agents.metaheuristic_bases.LSHADEBase import LSHADEBase
from greyjack.score_calculation.score_requesters.OOPScoreRequester import OOPScoreRequester
from greyjack.score_calculation.score_requesters.PureMathScoreRequester import PureMathScoreRequester
from greyjack.cotwin.CotwinBase import CotwinBase
from greyjack.pure_math.MathModel import MathModel

class LSHADE(Agent):

    """
    Classic Tanabe-Fukunaga version of LSHADE (https://metahack.org/CEC2014-Tanabe-Fukunaga.pdf) 
    with my own modifications to make it better work in common (not only for continuous tasks, but also for MIP).
    For pure integer tasks works much badder than Tabu, GenAlg, LateAcc. Don't use LSHADE for purely integer tasks.
    Later will be modified further. From 2014 there were a lot of modifications invented by researchers.

    WARNING! Don't use this metaheuristic with already initialized values (it will stuck due to sampling from history mechanism)!
    """

    def __init__(
        self, population_size=128, history_archive_size=100, 
        p_best_rate=0.2, tabu_entity_rate=0.2, 
        mutation_rate_multiplier=1.0, move_probas=None,
        memory_pruning_rate=0.0, guarantee_of_change_size=1.0, 
        initial_f=0.5, initial_cr=0.02, initial_mutation_proba=0.5,
        migration_rate=0.00001, migration_frequency=10, termination_strategy=None
    ):
        
        super().__init__(migration_rate, migration_frequency, termination_strategy, compare_to_global_frequency=1)

        self.population_size = population_size
        self.history_archive_size = history_archive_size
        self.p_best_rate = p_best_rate
        self.memory_pruning_rate = memory_pruning_rate
        self.guarantee_of_change_size = guarantee_of_change_size
        self.initial_f = initial_f
        self.initial_cr = initial_cr
        self.initial_mutation_proba = initial_mutation_proba

        self.tabu_entity_rate = tabu_entity_rate
        self.mutation_rate_multiplier = mutation_rate_multiplier
        self.move_probas = move_probas

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

        self.metaheuristic_base = LSHADEBase.new(
            score_variant,
            self.score_requester.variables_manager,

            self.population_size, 
            self.history_archive_size, 
            self.p_best_rate, 
            self.memory_pruning_rate, 
            self.guarantee_of_change_size, 
            self.initial_f, 
            self.initial_cr, 
            self.initial_mutation_proba,

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