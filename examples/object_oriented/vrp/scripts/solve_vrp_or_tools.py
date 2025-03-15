from copy import deepcopy
from pathlib import Path
import random
import os
import sys

# To launch normally from console
script_dir_path = Path(os.path.dirname(os.path.realpath(__file__)))
project_dir_id = script_dir_path.parts.index("greyjack-solver-python")
project_dir_path = Path(*script_dir_path.parts[:project_dir_id+1])
sys.path.append(str(project_dir_path))

from examples.object_oriented.vrp.persistence.DomainBuilder import DomainBuilder
from greyjack.agents.termination_strategies import *

"""Capacited Vehicles Routing Problem (CVRP)."""

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp


def create_data_model():

    dir_path = os.path.dirname(os.path.realpath(__file__))
    # simple VRP datasets (without multi-depot and time windows)
    data_dir_path = Path(project_dir_path, "data", "vrp", "data", "import")
    #file_path = Path(data_dir_path, "vrpweb", "basic", "air", "A-n32-k5.vrp")
    #file_path = Path(data_dir_path, "vrpweb", "basic", "air", "F-n135-k7.vrp")
    #file_path = Path(data_dir_path, "usa", "basic", "air", "usa-n100-k10.vrp")
    file_path = Path(data_dir_path, "belgium", "basic", "air", "belgium-n1000-k40.vrp")

    # Warning! For datasets without predefined distances, custom distances are multiplied by 1000 and rounded to int
    # Inside output true distances without rounding are using.
    domain_model = DomainBuilder(file_path).build_domain_from_scratch()
    distance_matrix = domain_model.distance_matrix
    demands = [int(customer.demand) for customer in domain_model.customers_dict.values()]
    k_vehicles = len(domain_model.vehicles)
    capacities = [vehicle.capacity for vehicle in domain_model.vehicles]

    """Stores the data for the problem."""
    data = {}
    data["distance_matrix"] = distance_matrix
    data["demands"] = demands
    data["vehicle_capacities"] = capacities
    data["num_vehicles"] = k_vehicles
    data["depot"] = 0
    return data


def print_solution(data, manager, routing, solution):
    """Prints solution on console."""
    print(f"Objective: {solution.ObjectiveValue()}")
    total_distance = 0
    total_load = 0
    for vehicle_id in range(data["num_vehicles"]):
        index = routing.Start(vehicle_id)
        plan_output = f"Route for vehicle {vehicle_id}:\n"
        route_distance = 0
        route_load = 0
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_load += data["demands"][node_index]
            plan_output += f" {node_index} Load({route_load}) -> "
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(
                previous_index, index, vehicle_id
            )
        plan_output += f" {manager.IndexToNode(index)} Load({route_load})\n"
        plan_output += f"Distance of the route: {route_distance}m\n"
        plan_output += f"Load of the route: {route_load}\n"
        print(plan_output)
        total_distance += route_distance
        total_load += route_load
    print(f"Total distance of all routes: {total_distance}m")
    print(f"Total load of all routes: {total_load}")


def main():
    """Solve the CVRP problem."""
    # Instantiate the data problem.
    data = create_data_model()

    # Create the routing index manager.
    manager = pywrapcp.RoutingIndexManager(
        len(data["distance_matrix"]), data["num_vehicles"], data["depot"]
    )

    # Create Routing Model.
    routing = pywrapcp.RoutingModel(manager)

    # Create and register a transit callback.
    def distance_callback(from_index, to_index):
        """Returns the distance between the two nodes."""
        # Convert from routing variable Index to distance matrix NodeIndex.
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data["distance_matrix"][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)

    # Define cost of each arc.
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Add Capacity constraint.
    def demand_callback(from_index):
        """Returns the demand of the node."""
        # Convert from routing variable Index to demands NodeIndex.
        from_node = manager.IndexToNode(from_index)
        return data["demands"][from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        data["vehicle_capacities"],  # vehicle maximum capacities
        True,  # start cumul to zero
        "Capacity",
    )

    # Setting first solution heuristic.
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.AUTOMATIC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.AUTOMATIC
    )
    search_parameters.time_limit.FromSeconds(10)

    # Solve the problem.
    solution = routing.SolveWithParameters(search_parameters)

    # Print solution on console.
    if solution:
        print_solution(data, manager, routing, solution)


if __name__ == "__main__":
    main()