

import numpy as np
import traceback
from datetime import datetime
from greyjack.persistence.CotwinBuilderBase import CotwinBuilderBase
from greyjack.variables.GJInteger import GJInteger
from examples.object_oriented.food_packaging.cotwin import *
from examples.object_oriented.food_packaging.score.IncrementalScoreCalculator import IncrementalScoreCalculator
from examples.object_oriented.food_packaging.score.PlainScoreCalculator import PlainScoreCalculator


class CotwinBuilder(CotwinBuilderBase):
    def __init__(self, use_incremental_score_calculator, use_greed_init):
        self.use_incremental_score_calculator = use_incremental_score_calculator
        self.use_greed_init = use_greed_init
        pass

    def build_cotwin(self, domain, is_already_initialized):

        try:
            cotwin = Cotwin()

            planning_jobs = self._build_planning_jobs(domain, is_already_initialized)
            problem_fact_lines = self._build_problem_fact_lines(domain)
            problem_fact_products = self._build_problem_fact_products(domain)

            if self.use_incremental_score_calculator:
                score_calculator = IncrementalScoreCalculator()
                self._add_utility_info_for_incremental_scoring(domain, score_calculator, planning_jobs)
                self._remove_redundant_fields( planning_jobs, ["name", "product_id", "duration", "min_start_time", "ideal_end_time", "max_end_time", "priority"] )
                cotwin.add_planning_entities_list( planning_jobs, "jobs" )
            else:
                score_calculator = PlainScoreCalculator()
                cotwin.add_planning_entities_list( planning_jobs, "jobs" )
                cotwin.add_problem_facts_list( problem_fact_lines, "lines" )
                cotwin.add_problem_facts_list( problem_fact_products, "products" )

            cotwin.set_score_calculator( score_calculator )

        except Exception as e:
            print(traceback.format_exc())


        return cotwin
    
    def _add_utility_info_for_incremental_scoring(self, domain, score_calculator, planning_jobs):

        product_ids = []
        durations = []
        min_start_times = []
        ideal_end_times = []
        max_end_times = []
        priorities = []
        for job in planning_jobs:
            product_ids.append(job.product_id)
            durations.append(job.duration.seconds // 60)
            min_start_times.append(int(datetime.combine(job.min_start_time, datetime.min.time()).timestamp() // 60))
            ideal_end_times.append(int(datetime.combine(job.ideal_end_time, datetime.min.time()).timestamp() // 60))
            max_end_times.append(int(datetime.combine(job.max_end_time, datetime.min.time()).timestamp() // 60))
            priorities.append(job.priority)
        score_calculator.utility_objects["product_ids"] = product_ids
        score_calculator.utility_objects["durations"] = durations
        score_calculator.utility_objects["min_start_times"] = min_start_times
        score_calculator.utility_objects["ideal_end_times"] = ideal_end_times
        score_calculator.utility_objects["max_end_times"] = max_end_times
        score_calculator.utility_objects["priorities"] = priorities

        operators_to_int_map = list(sorted(list(set([line.operator for line in domain.lines]))))
        operators_to_int_map = {k: v for v, k in enumerate(operators_to_int_map)}
        operators = []
        start_date_times = []
        for line in domain.lines:
            operators.append(operators_to_int_map[line.operator])
            start_date_times.append(int(datetime.combine(line.start_date_time, datetime.min.time()).timestamp() // 60))
        score_calculator.utility_objects["operators"] = operators
        score_calculator.utility_objects["start_date_times"] = start_date_times
        score_calculator.utility_objects["m_lines"] = len(start_date_times)

        k_products = len(domain.products)
        cleaning_duration_matrix = np.zeros((k_products, k_products), np.int64)
        for i in range(k_products):
            for j in range(k_products):
                product_i = domain.products[i]
                product_j = domain.products[j]
                cleaning_duration_matrix[i][j] = product_i.cleaning_durations[product_j].seconds // 60
        score_calculator.utility_objects["cleaning_duration_matrix"] = cleaning_duration_matrix

        pass
    
    def _build_planning_jobs(self, domain, is_already_initialized):

        planning_jobs = []
        for job in domain.jobs:
            planning_job = CotJob(
                job_id=job.id, 
                name=job.name, 
                product_id=job.product.id, 
                duration=job.duration, 
                min_start_time=job.min_start_time,
                ideal_end_time=job.ideal_end_time,
                max_end_time=job.max_end_time, 
                priority=job.priority,
                # TODO: add frozen (pinned) processing
                line_id = GJInteger(0, len(domain.lines) - 1, False, None, semantic_groups=["lines", "common"]),
                # defines order of jobs in an assigned line
                line_position = GJInteger(0, len(domain.jobs) - 1, False, None, semantic_groups=["line_positions", "common"])
            )
            planning_jobs.append( planning_job )

        return planning_jobs
    
    def _build_problem_fact_lines(self, domain):

        problem_fact_lines = []
        for line in domain.lines:
            problem_fact_line = CotLine(
                id=line.id,
                name=line.name, 
                operator=line.operator, 
                start_date_time=line.start_date_time
            )
            problem_fact_lines.append(problem_fact_line)


        return problem_fact_lines
    
    def _build_problem_fact_products(self, domain):
        problem_fact_products = []
        for product in domain.products:
            problem_fact_product = CotProduct(
                id=product.id,
                name=product.name
            )
            problem_fact_products.append(problem_fact_product)


        return problem_fact_products

    def _remove_redundant_fields(self, entities_list, redundant_fields):

        for i in range(len(entities_list)):
            for field_name in redundant_fields:
                delattr(entities_list[i], field_name)



