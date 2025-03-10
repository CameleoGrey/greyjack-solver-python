
from greyjack.greyjack import TabuSearchSimple, TabuSearchHardSoft, TabuSearchHardMediumSoft
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants

class TabuSearchBase:
    def new(score_variant, variables_manager_py, 
            neighbours_count, tabu_entity_rate, semantic_groups_map, mutation_rate_multiplier=None, move_probas=None, discrete_ids=None):
        if score_variant == ScoreVariants.SimpleScore:
            return TabuSearchSimple(variables_manager_py, neighbours_count, tabu_entity_rate,
                                    semantic_groups_map, mutation_rate_multiplier, move_probas, discrete_ids)
        if score_variant == ScoreVariants.HardSoftScore:
            return TabuSearchHardSoft(variables_manager_py, neighbours_count, tabu_entity_rate, 
                                      semantic_groups_map, mutation_rate_multiplier, move_probas, discrete_ids)
        if score_variant == ScoreVariants.HardMediumSoftScore:
            return TabuSearchHardMediumSoft(variables_manager_py, neighbours_count, tabu_entity_rate, 
                                            semantic_groups_map, mutation_rate_multiplier, move_probas, discrete_ids)
        
        raise Exception("score_variant unrecognized")