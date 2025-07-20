import random
import numpy as np

from examples.object_oriented.tsp_greynet.cotwin.CotStop import CotStop
from examples.object_oriented.tsp_greynet.cotwin.CotLocation import CotLocation
from examples.object_oriented.tsp_greynet.cotwin.TSPCotwin import TSPCotwin
from examples.object_oriented.tsp_greynet.score.GreynetScoreCalculatorTSP import GreynetScoreCalculatorTSP

from greyjack.persistence.CotwinBuilderBase import CotwinBuilderBase
from greyjack.variables.GJInteger import GJInteger


class CotwinBuilder(CotwinBuilderBase):

    def __init__(self):

        super().__init__()

        pass

    def build_cotwin(self, domain_model, is_already_initialized):
        
        domain_locations = domain_model.locations_list
        distance_matrix = domain_model.distance_matrix

        problem_fact_locations = self._build_problem_fact_locations(domain_locations)
        planning_stops = self._build_planning_stops(problem_fact_locations)
        score_calculator = GreynetScoreCalculatorTSP(problem_fact_locations, distance_matrix)

        cotwin = TSPCotwin()
        cotwin.add_planning_entities_list(planning_stops, "planning_stops")
        cotwin.set_score_calculator(score_calculator)
        
        return cotwin
    
    def _build_problem_fact_locations(self, domain_locations):

        problem_fact_locations = []
        for i, domain_location in enumerate(domain_locations):
            problem_fact_location = CotLocation(
                location_id=i,
                latitude=domain_location.latitude,
                longitude=domain_location.longitude
            )
            problem_fact_locations.append(problem_fact_location)

        return problem_fact_locations

    def _build_planning_stops(self, locations):
        """Creates a Stop entity for each location that needs to be visited."""
        planning_stops = []

        n_locations = len(locations)

        for i, loc in enumerate(locations):
            previous_stop_var = GJInteger(
                lower_bound=0,
                upper_bound=n_locations - 1,
                frozen=False,
                initial_value=n_locations - 1 - i
            )
            
            # Create the Stop entity
            planning_stop = CotStop(
                location_id=loc.location_id,
                previous_stop_id=previous_stop_var
            )
            planning_stops.append(planning_stop)

        return planning_stops