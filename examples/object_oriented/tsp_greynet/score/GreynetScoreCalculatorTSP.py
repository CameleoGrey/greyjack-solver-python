

from typing import List, Dict

from examples.object_oriented.tsp_greynet.cotwin.CotStop import CotStop
from examples.object_oriented.tsp_greynet.cotwin.CotLocation import CotLocation

from greyjack.score_calculation.greynet.builder import ConstraintBuilder, Collectors
from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
from greyjack.score_calculation.score_calculators.GreynetScoreCalculator import GreynetScoreCalculator


class GreynetScoreCalculatorTSP(GreynetScoreCalculator):
    """
    Uses the Greynet rule engine to calculate the score for the TSP problem.
    """
    def __init__(self, locations: List[CotLocation], distance_matrix: Dict[int, Dict[int, float]]):
        """
        Initializes the calculator by defining all constraints.
        
        Args:
            locations (List[CotLocation]): The list of all locations (including depot at id 0).
            distance_matrix (Dict): A pre-computed matrix for O(1) distance lookups.
        """
        self.locations = locations
        self.distance_matrix = distance_matrix
        
        self.stop_location_ids = {int(loc.location_id) for loc in locations}

        # Initialize the constraint builder with our score class
        builder = ConstraintBuilder(score_class=HardSoftScore)
        self.define_constraints(builder)
        
        # Pass the fully configured builder to the parent constructor
        super().__init__(constraint_builder=builder, score_variant=ScoreVariants.HardSoftScore)

    def define_constraints(self, cb: ConstraintBuilder):
        """
        Defines the hard and soft constraints for the TSP problem.
        
        Args:
            cb (ConstraintBuilder): The greynet constraint builder instance.
        """

        # --- HARD CONSTRAINTS ---

        # Constraint 1: A stop cannot be its own predecessor.
        @cb.constraint("self_predecessor", 1.0)
        def self_predecessor():
            return (cb.for_each(CotStop)
                      .filter(lambda stop: int(stop.location_id) == int(stop.previous_stop_id))
                      .penalize_hard(1)
                   )

        # Constraint 2: Every stop must be a predecessor to exactly one other stop.
        @cb.constraint("predecessor_count", 1.0)
        def predecessor_count():
            return (cb.for_each(CotStop)
                      .group_by(lambda stop: int(stop.previous_stop_id), Collectors.count())
                      .filter(lambda prev_id, count: count != 1)
                      .penalize_hard(lambda prev_id, count: abs(count - 1))
                   )
        
        # TODO: Implement chained variables to eliminate subtours...

        # --- SOFT CONSTRAINT (OBJECTIVE) ---

        # Constraint 3: Minimize the total distance of the tour.
        @cb.constraint("total_distance", 1.0)
        def total_distance():
            return (cb.for_each(CotStop)
                      # The penalty is the distance between this stop and its predecessor.
                      .penalize_soft(lambda stop: self.distance_matrix[int(stop.previous_stop_id)][int(stop.location_id)])
                   )