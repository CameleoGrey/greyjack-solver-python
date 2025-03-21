
import numpy as np
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
from greyjack.agents.base.individuals.IndividualSimple import IndividualSimple
from greyjack.agents.base.individuals.IndividualHardSoft import IndividualHardSoft
from greyjack.agents.base.individuals.IndividualHardMediumSoft import IndividualHardMediumSoft


class Individual:

    def get_related_individual_type(score_variant):

        if score_variant == ScoreVariants.SimpleScore:
            return IndividualSimple
        if score_variant == ScoreVariants.HardSoftScore:
            return IndividualHardSoft
        if score_variant == ScoreVariants.HardMediumSoftScore:
            return IndividualHardMediumSoft
        
        raise Exception("score_variant unrecognized")

    def get_related_individual_type_by_value(score_variant_value):

        if score_variant_value == ScoreVariants.SimpleScore:
            return IndividualSimple
        if score_variant_value == ScoreVariants.HardSoftScore:
            return IndividualHardSoft
        if score_variant_value == ScoreVariants.HardMediumSoftScore:
            return IndividualHardMediumSoft
        
        raise Exception("score_variant unrecognized")


