
from greyjack.greyjack import LateAcceptanceSimple, LateAcceptanceHardSoft, LateAcceptanceHardMediumSoft
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants

class LateAcceptanceBase:
    def new(score_variant, variables_manager_py, 
            late_acceptance_size, tabu_entity_rate, semantic_groups_map, mutation_rate_multiplier=None, move_probas=None, discrete_ids=None):
        if score_variant == ScoreVariants.SimpleScore:
            return LateAcceptanceSimple(variables_manager_py, late_acceptance_size, tabu_entity_rate,
                                    semantic_groups_map, mutation_rate_multiplier, move_probas, discrete_ids)
        if score_variant == ScoreVariants.HardSoftScore:
            return LateAcceptanceHardSoft(variables_manager_py, late_acceptance_size, tabu_entity_rate, 
                                      semantic_groups_map, mutation_rate_multiplier, move_probas, discrete_ids)
        if score_variant == ScoreVariants.HardMediumSoftScore:
            return LateAcceptanceHardMediumSoft(variables_manager_py, late_acceptance_size, tabu_entity_rate, 
                                            semantic_groups_map, mutation_rate_multiplier, move_probas, discrete_ids)
        
        raise Exception("score_variant unrecognized")