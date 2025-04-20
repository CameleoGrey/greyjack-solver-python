


from greyjack.persistence.CotwinBuilderBase import CotwinBuilderBase
from greyjack.variables.GJInteger import GJInteger
from examples.object_oriented.boiler_plate_code.cotwin.Cotwin import Cotwin
from examples.object_oriented.boiler_plate_code.score.IncrementalScoreCalculator import IncrementalScoreCalculator
from examples.object_oriented.boiler_plate_code.score.PlainScoreCalculator import PlainScoreCalculator


class CotwinBuilder(CotwinBuilderBase):
    def __init__(self, use_incremental_score_calculator, use_greed_init):
        self.use_incremental_score_calculator = use_incremental_score_calculator
        self.use_greed_init = use_greed_init
        pass

    def build_cotwin(self, domain, is_already_initialized):

        cotwin = Cotwin()

        cotwin.add_planning_entities_list(self._build_some_planning_entities(domain, is_already_initialized), "some_planning_entities")
        #cotwin.add_problem_facts_list(self._build_some_problem_facts(domain), "some_problem_facts")

        if self.use_incremental_score_calculator:
            score_calculator = IncrementalScoreCalculator()
        else:
            score_calculator = PlainScoreCalculator()

        cotwin.set_score_calculator( score_calculator )

        return cotwin
    
    def _build_some_planning_entities(self, domain, is_already_initialized):
        return some_planning_entities
    
    def _build_some_problem_facts(self, domain):
        return some_problem_facts

    def _remove_redundant_fields(self, entities_list, redundant_fields):

        for i in range(len(entities_list)):
            for field_name in redundant_fields:
                delattr(entities_list[i], field_name)



