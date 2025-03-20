
from greyjack.greyjack import SimulatedAnnealingSimple, SimulatedAnnealingHardSoft, SimulatedAnnealingHardMediumSoft
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants

class SimulatedAnnealingBase:
    def new(score_variant, variables_manager_py, 
            initial_temperature, tabu_entity_rate, 
            semantic_groups_dict, cooling_rate, 
            mutation_rate_multiplier=None, 
            move_probas=None, discrete_ids=None):
        if score_variant == ScoreVariants.SimpleScore:
            return SimulatedAnnealingSimple(variables_manager_py, 
                                            initial_temperature, tabu_entity_rate, 
                                            semantic_groups_dict, cooling_rate, 
                                            mutation_rate_multiplier, 
                                            move_probas, discrete_ids)
        if score_variant == ScoreVariants.HardSoftScore:
            return SimulatedAnnealingHardSoft(variables_manager_py, 
                                            initial_temperature, tabu_entity_rate, 
                                            semantic_groups_dict, cooling_rate, 
                                            mutation_rate_multiplier, 
                                            move_probas, discrete_ids)
        if score_variant == ScoreVariants.HardMediumSoftScore:
            return SimulatedAnnealingHardMediumSoft(variables_manager_py, 
                                                    initial_temperature, tabu_entity_rate, 
                                                    semantic_groups_dict, cooling_rate, 
                                                    mutation_rate_multiplier, 
                                                    move_probas, discrete_ids)
        
        raise Exception("score_variant unrecognized")