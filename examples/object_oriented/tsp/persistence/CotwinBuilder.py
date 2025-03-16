import random
import numpy as np

from examples.object_oriented.tsp.cotwin.CotStop import CotStop
from examples.object_oriented.tsp.cotwin.EdgeDistance import EdgeDistance
from examples.object_oriented.tsp.cotwin.TSPCotwin import TSPCotwin
from examples.object_oriented.tsp.score.PlainScoreCalculatorTSP import PlainScoreCalculatorTSP
from examples.object_oriented.tsp.score.IncrementalScoreCalculatorTSP import IncrementalScoreCalculatorTSP

from greyjack.persistence.CotwinBuilderBase import CotwinBuilderBase
from greyjack.variables.GJInteger import GJInteger


class CotwinBuilder(CotwinBuilderBase):

    def __init__(self, use_incremental_score_calculator):

        super().__init__()

        self.use_incremental_score_calculator = use_incremental_score_calculator

        pass

    def build_cotwin(self, domain_model, is_already_initialized):

        tsp_cotwin = TSPCotwin()

        tsp_cotwin.add_planning_entities_list(self._build_planning_path_stops(domain_model), "path_stops")

        # (!) better use distance matrix mapping than building and joining large distance dataframe!
        #tsp_cotwin.add_problem_facts_list(self._build_edge_distances(domain_model), "edge_distances")

        if self.use_incremental_score_calculator:
            score_calculator = PlainScoreCalculatorTSP()
        else:
            score_calculator = IncrementalScoreCalculatorTSP()

        score_calculator.utility_objects["distance_matrix"] = domain_model.distance_matrix
        tsp_cotwin.set_score_calculator( score_calculator )

        return tsp_cotwin

    def _build_edge_distances(self, domain_model):

        distance_matrix = domain_model.distance_matrix
        n_stops = len(distance_matrix)

        edge_distances = []
        for i in range(n_stops):
            for j in range(n_stops):
                current_edge_distance = EdgeDistance( i, j, distance_matrix[i][j] )
                edge_distances.append( current_edge_distance )

        return edge_distances

    def _build_planning_path_stops(self, domain_model):

        planning_path_stops = []
        locations_list = domain_model.locations_list
        n_locations = len(locations_list)
        n_stops = n_locations - 1 # excluding depot

        # greed heuristic for initializing
        initial_stop_ids = []
        current_approx_stop = 0
        for i in range(1, n_locations):
            candidate_stops = domain_model.distance_matrix[current_approx_stop]
            candidate_stops = np.argsort( candidate_stops )#[::-1]#[5:] #<-- for experiments
            existing_stop_ids = set(initial_stop_ids)
            for candidate_stop in candidate_stops:
                if ((candidate_stop not in existing_stop_ids)
                        and (candidate_stop != current_approx_stop)
                        and (candidate_stop != 0)):
                    initial_stop_ids.append( candidate_stop )
                    current_approx_stop = candidate_stop
                    break

        for i in range(0, n_stops):
            # initial_value=1+i for simulating situation, in which we don't 
            # know good start solution or greed heuristic, but know, what solution must contain unique stops
            # initial_stop_ids[i] for using greed heuristic
            planning_stop = CotStop(stop_id=i, location_list_id=GJInteger(1, n_locations-1, False, initial_stop_ids[i]))
            planning_path_stops.append(planning_stop)

        return planning_path_stops