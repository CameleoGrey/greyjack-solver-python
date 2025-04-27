

import math
import numpy as np
import traceback
from greyjack.persistence.CotwinBuilderBase import CotwinBuilderBase
from greyjack.variables.GJInteger import GJInteger
from examples.object_oriented.facility_location.domain.Location import Location
from examples.object_oriented.facility_location.cotwin.Cotwin import Cotwin
from examples.object_oriented.facility_location.cotwin.CotConsumer import CotConsumer
from examples.object_oriented.facility_location.cotwin.CotFacility import CotFacility
from examples.object_oriented.facility_location.score.IncrementalScoreCalculator import IncrementalScoreCalculator
from examples.object_oriented.facility_location.score.PlainScoreCalculator import PlainScoreCalculator


class CotwinBuilder(CotwinBuilderBase):
    def __init__(self, use_incremental_score_calculator, use_greed_init):
        self.use_incremental_score_calculator = use_incremental_score_calculator
        self.use_greed_init = use_greed_init
        pass

    def build_cotwin(self, domain, is_already_initialized):

        try: 
            cotwin = Cotwin()

            all_locations_map = {}
            i = 0
            for facility in domain.facilities:
                all_locations_map[facility.location] = i
                i += 1
            for consumer in domain.consumers:
                all_locations_map[consumer.location] = i
                i += 1

            planning_consumers = self._build_planning_consumers(domain, all_locations_map, is_already_initialized)
            problem_fact_facilities = self._build_problem_fact_facilities(domain, all_locations_map)

            if self.use_incremental_score_calculator:
                score_calculator = IncrementalScoreCalculator()
                self._add_utility_info_for_incremental_scoring(domain, score_calculator, planning_consumers, problem_fact_facilities, all_locations_map)
                self._remove_redundant_fields(planning_consumers, ["location_id", "demand"])
                cotwin.add_planning_entities_list(planning_consumers, "consumers")
            else:
                score_calculator = PlainScoreCalculator()
                cotwin.add_planning_entities_list(planning_consumers, "consumers")
                cotwin.add_problem_facts_list(problem_fact_facilities, "facilities")

            cotwin.set_score_calculator( score_calculator )
        except Exception as e:
            print(traceback.format_exc())

        return cotwin
    
    def _add_utility_info_for_incremental_scoring(self, domain, score_calculator, planning_consumers, problem_fact_facilities, all_locations_map):

        inverse_all_locations_map = {k: v for v, k in all_locations_map.items()}
        n_locations = len(inverse_all_locations_map)
        distance_matrix = np.zeros((n_locations, n_locations), np.int64) + np.iinfo(np.int64).max
        for i in range(n_locations):
            for j in range(n_locations):
                location_i = inverse_all_locations_map[i]
                location_j = inverse_all_locations_map[j]
                distance_matrix[i][j] = math.ceil(Location.METERS_PER_DEGREE * np.sqrt( (location_i.longitude - location_j.longitude)**2 + (location_i.latitude - location_j.latitude)**2 ))
        score_calculator.utility_objects["distance_matrix"] = distance_matrix

        # consumer ids are starting from len(facilities)
        # holding tail of len(facilities) in the beginning for comfort
        demands = np.zeros((n_locations,), np.int64) + np.iinfo(np.int64).max
        location_ids = np.zeros((n_locations,), np.int64) + np.iinfo(np.int64).max
        for planning_consumer in planning_consumers:
            demands[planning_consumer.customer_id] = planning_consumer.demand
            location_ids[planning_consumer.customer_id] = planning_consumer.location_id
        score_calculator.utility_objects["demands"] = demands
        score_calculator.utility_objects["location_ids"] = location_ids

        m_facilities = len(problem_fact_facilities)
        setup_costs = np.zeros((m_facilities,), np.int64) + np.iinfo(np.int64).max
        capacities = np.zeros((m_facilities,), np.int64) + np.iinfo(np.int64).max
        for i, cot_facility in enumerate(problem_fact_facilities):
            setup_costs[i] = cot_facility.setup_cost
            capacities[i] = cot_facility.capacity
        score_calculator.utility_objects["setup_costs"] = setup_costs
        score_calculator.utility_objects["capacities"] = capacities

        pass

    def _build_planning_consumers(self, domain, all_locations_map, is_already_initialized):
        
        m_facilities = len(domain.facilities)
        planning_consumers = []
        for i, consumer in enumerate(domain.consumers):
            cot_consumer = CotConsumer(
                customer_id=m_facilities + i,
                location_id=all_locations_map[consumer.location],
                demand=consumer.demand,
                facility_id=GJInteger(0, len(domain.facilities)-1, False, None)
            )
            planning_consumers.append(cot_consumer)

        return planning_consumers
    
    def _build_problem_fact_facilities(self, domain, all_locations_map):

        problem_fact_facilities = []
        for i, facility in enumerate(domain.facilities):
            cot_facility = CotFacility(
                facility_id=i, 
                location_id=all_locations_map[facility.location], 
                setup_cost=facility.setup_cost, 
                capacity=facility.capacity
            )
            problem_fact_facilities.append(cot_facility)

        return problem_fact_facilities

    def _remove_redundant_fields(self, entities_list, redundant_fields):

        for i in range(len(entities_list)):
            for field_name in redundant_fields:
                delattr(entities_list[i], field_name)



