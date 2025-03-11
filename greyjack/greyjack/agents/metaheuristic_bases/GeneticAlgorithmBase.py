
from greyjack.greyjack import GeneticAlgorithmSimple, GeneticAlgorithmHardSoft, GeneticAlgorithmHardMediumSoft
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants

class GeneticAlgorithmBase:
    def new(score_variant, variables_manager_py, 
            population_size, crossover_probability, p_best_rate,
            tabu_entity_rate, 
            semantic_groups_dict,
            mutation_rate_multiplier, move_probas, discrete_ids):
        if score_variant == ScoreVariants.SimpleScore:
            return GeneticAlgorithmSimple(variables_manager_py, population_size,
                                          crossover_probability, p_best_rate, tabu_entity_rate, 
                                          semantic_groups_dict, 
                                          mutation_rate_multiplier, move_probas, discrete_ids)
        if score_variant == ScoreVariants.HardSoftScore:
            return GeneticAlgorithmHardSoft(variables_manager_py, population_size,
                                            crossover_probability, p_best_rate, tabu_entity_rate, 
                                            semantic_groups_dict, 
                                            mutation_rate_multiplier, move_probas, discrete_ids)
        if score_variant == ScoreVariants.HardMediumSoftScore:
            return GeneticAlgorithmHardMediumSoft(variables_manager_py, population_size,
                                                  crossover_probability, p_best_rate, tabu_entity_rate, 
                                                  semantic_groups_dict, 
                                                  mutation_rate_multiplier, move_probas, discrete_ids)
        
        raise Exception("score_variant unrecognized")