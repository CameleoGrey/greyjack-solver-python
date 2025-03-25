
from greyjack.greyjack import LSHADESimple, LSHADEHardSoft, LSHADEHardMediumSoft
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants

class LSHADEBase:
    def new(score_variant, variables_manager_py, population_size, history_archive_size, p_best_rate, memory_pruning_rate, guarantee_of_change_size, 
            initial_f, initial_cr, initial_mutation_proba, tabu_entity_rate, semantic_groups_dict,
            mutation_rate_multiplier, move_probas, discrete_ids):
        if score_variant == ScoreVariants.SimpleScore:
            return LSHADESimple(variables_manager_py, population_size, history_archive_size, p_best_rate, memory_pruning_rate, guarantee_of_change_size, 
                                initial_f, initial_cr, initial_mutation_proba, tabu_entity_rate, semantic_groups_dict,
                                mutation_rate_multiplier, move_probas, discrete_ids)
        if score_variant == ScoreVariants.HardSoftScore:
            return LSHADEHardSoft(variables_manager_py, population_size, history_archive_size, p_best_rate, memory_pruning_rate, guarantee_of_change_size, 
                                initial_f, initial_cr, initial_mutation_proba, tabu_entity_rate, semantic_groups_dict,
                                mutation_rate_multiplier, move_probas, discrete_ids)
        if score_variant == ScoreVariants.HardMediumSoftScore:
            return LSHADEHardMediumSoft(variables_manager_py, population_size, history_archive_size, p_best_rate, memory_pruning_rate, guarantee_of_change_size, 
                                initial_f, initial_cr, initial_mutation_proba, tabu_entity_rate, semantic_groups_dict,
                                mutation_rate_multiplier, move_probas, discrete_ids)
        
        raise Exception("score_variant unrecognized")