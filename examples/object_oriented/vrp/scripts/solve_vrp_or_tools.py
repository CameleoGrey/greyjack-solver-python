"""
Capacitated Vehicles Routing Problem with Time Windows and Multiple Depots (CVRPTW-MD).

This script uses Google OR-Tools to solve a complex vehicle routing problem that includes:
- Multiple depots
- Time windows for deliveries
- Vehicle capacity constraints
- Service times at each location

The solution is optimized using guided local search with path cheapest arc as the first solution strategy.
"""

from __future__ import annotations

import os
import random
import sys
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

# To launch normally from console
script_dir_path = Path(os.path.dirname(os.path.realpath(__file__)))
project_dir_id = script_dir_path.parts.index("greyjack-solver-python")
project_dir_path = Path(*script_dir_path.parts[:project_dir_id + 1])
sys.path.append(str(project_dir_path))

from examples.object_oriented.vrp.persistence.DomainBuilder import DomainBuilder
from greyjack.agents.termination_strategies import *

# Configuration constants
DEFAULT_SPEED_KMH = 50.0  # Default vehicle speed in km/h
MAX_TIME_PER_VEHICLE = 100000  # Maximum time per vehicle in minutes
ALLOWED_WAITING_TIME = 30  # Allowed waiting time in minutes
SOLVE_TIME_LIMIT_SECONDS = 600  # Time limit for solving in seconds

# File paths for different datasets
DATA_DIR_PATH = Path(project_dir_path, "data", "vrp", "data", "import")
#DEFAULT_DATASET_PATH = Path(DATA_DIR_PATH, "belgium", "multidepot-timewindowed", "air", "belgium-tw-d2-n50-k10.vrp")
DEFAULT_DATASET_PATH = Path(DATA_DIR_PATH, "belgium", "multidepot-timewindowed", "air", "belgium-tw-d8-n1000-k40.vrp")



class VRPDataModel:
    """Data model for the Vehicle Routing Problem with Time Windows."""
    
    def __init__(self, file_path: Optional[Path] = None):
        """
        Initialize the VRP data model.
        
        Args:
            file_path: Path to the VRP data file. If None, uses default dataset.
        """
        self.file_path = file_path or DEFAULT_DATASET_PATH
        self.domain_model = None
        self.distance_matrix = []
        self.demands = []
        self.vehicle_capacities = []
        self.num_vehicles = 0
        self.num_depots = 0
        self.depot_indices = []
        self.starts = []
        self.ends = []
        self.time_windows = []
        self.service_times = []
        self.speed = DEFAULT_SPEED_KMH
        
    def build(self) -> Dict[str, Any]:
        """Build the data model from the input file."""
        self._parse_domain_data()
        self._extract_basic_data()
        self._configure_depots()
        self._configure_vehicles()
        self._extract_time_data()
        
        return self._create_data_dict()
    
    def _parse_domain_data(self) -> None:
        """Parse the domain data from the input file."""
        self.domain_model = DomainBuilder(self.file_path).build_domain_from_scratch()
        self.distance_matrix = self.domain_model.distance_matrix
        
    def _extract_basic_data(self) -> None:
        """Extract basic VRP data from the domain model."""
        self.demands = [int(customer.demand) for customer in self.domain_model.customers_dict.values()]
        self.num_vehicles = len(self.domain_model.vehicles)
        self.vehicle_capacities = [vehicle.capacity for vehicle in self.domain_model.vehicles]
        
    def _configure_depots(self) -> None:
        """Configure depot information from the domain model."""
        depot_dict = self.domain_model.depot_dict
        self.depot_indices = []
        
        # Map depot IDs to their array indices
        for depot_id in depot_dict.values():
            for i, customer in enumerate(self.domain_model.customers_dict.values()):
                if customer.id == depot_id:
                    self.depot_indices.append(i)
                    break
        
        # Ensure depots have no demand
        for i in self.depot_indices:
            if i < len(self.demands):
                self.demands[i] = 0
                
        self.num_depots = len(self.depot_indices)
    
    def _configure_vehicles(self) -> None:
        """Configure vehicle start and end locations."""
        self.starts = []
        self.ends = []
        
        # Assign vehicles to depots by cycling through them
        for i in range(self.num_vehicles):
            depot_for_this_vehicle = self.depot_indices[i % len(self.depot_indices)]
            self.starts.append(depot_for_this_vehicle)
            self.ends.append(depot_for_this_vehicle)
    
    def _extract_time_data(self) -> None:
        """Extract time window and service time data."""
        num_locations = len(self.distance_matrix)
        self.service_times = []
        self.time_windows = []
        
        for i in range(num_locations):
            customer = self.domain_model.customers_dict[i]
            self.service_times.append(int(customer.service_time))
            self.time_windows.append((int(customer.time_window_start), int(customer.time_window_end)))
    
    def _create_data_dict(self) -> Dict[str, Any]:
        """Create the data dictionary for the OR-Tools solver."""
        return {
            "distance_matrix": self.distance_matrix,
            "demands": self.demands,
            "vehicle_capacities": self.vehicle_capacities,
            "num_vehicles": self.num_vehicles,
            "num_depots": self.num_depots,
            "starts": self.starts,
            "ends": self.ends,
            "depot_indices": self.depot_indices,
            "time_windows": self.time_windows,
            "service_times": self.service_times,
            "speed": self.speed,
            "domain_model": self.domain_model,
            "dataset_name": self.domain_model.name if self.domain_model else "Unknown"
        }


def create_data_model(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Create the data model for the CVRPTW-MD problem.
    
    Args:
        file_path: Path to the VRP data file. If None, uses default dataset.
        
    Returns:
        Dictionary containing all the problem data.
    """
    data_model = VRPDataModel(file_path)
    return data_model.build()


def print_solution(data: Dict[str, Any], manager: pywrapcp.RoutingIndexManager,
                  routing: pywrapcp.RoutingModel, solution: pywrapcp.Assignment) -> None:
    """
    Print the solution to the console in a formatted way.
    
    Args:
        data: The problem data dictionary.
        manager: The routing index manager.
        routing: The routing model.
        solution: The solution found by the solver.
    """
    print_solution_pretty(data, manager, routing, solution)
    plot_solution(data, manager, routing, solution)


def print_solution_pretty(data: Dict[str, Any], manager: pywrapcp.RoutingIndexManager,
                         routing: pywrapcp.RoutingModel, solution: pywrapcp.Assignment) -> None:
    """
    Print the solution in a visually appealing format with colors and structure.
    
    Args:
        data: The problem data dictionary.
        manager: The routing index manager.
        routing: The routing model.
        solution: The solution found by the solver.
    """
    # ANSI color codes for terminal output
    class Colors:
        HEADER = '\033[95m'
        BLUE = '\033[94m'
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        ENDC = '\033[0m'
        BOLD = '\033[1m'
        UNDERLINE = '\033[4m'
    
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}CVRPTW-MD Solution Report{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.CYAN}Objective Value: {solution.ObjectiveValue()}{Colors.ENDC}")
    print(f"{Colors.CYAN}Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")
    
    total_distance = 0
    total_load = 0
    total_time = 0
    time_dimension = routing.GetDimensionOrDie("Time")
    route_info = []
    
    for vehicle_id in range(data["num_vehicles"]):
        index = routing.Start(vehicle_id)
        start_node = manager.IndexToNode(index)
        
        route_distance = 0
        route_load = 0
        route_nodes = []
        route_times = []
        
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            time_var = time_dimension.CumulVar(index)
            time_min = solution.Min(time_var)
            
            route_load += data["demands"][node_index]
            route_nodes.append(node_index)
            route_times.append(time_min)
            
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(
                previous_index, index, vehicle_id
            )
        
        end_node = manager.IndexToNode(index)
        time_var = time_dimension.CumulVar(index)
        time_min = solution.Min(time_var)
        
        route_nodes.append(end_node)
        route_times.append(time_min)
        
        # Calculate route time
        route_time = route_times[-1] - route_times[0] if len(route_times) > 1 else 0
        
        # Store route information
        route_info.append({
            'vehicle_id': vehicle_id,
            'start_node': start_node,
            'end_node': end_node,
            'nodes': route_nodes,
            'times': route_times,
            'distance': route_distance,
            'load': route_load,
            'time': route_time,
            'capacity': data["vehicle_capacities"][vehicle_id] if vehicle_id < len(data["vehicle_capacities"]) else 0
        })
        
        total_distance += route_distance
        total_load += route_load
        total_time += route_time
    
    # Print detailed route information
    for i, route in enumerate(route_info):
        if route['distance'] > 0:  # Only print routes with actual work
            print(f"{Colors.GREEN}{Colors.BOLD}Vehicle {route['vehicle_id']} Route:{Colors.ENDC}")
            print(f"  {Colors.YELLOW}Depot: {route['start_node']} -> {route['end_node']}{Colors.ENDC}")
            print(f"  {Colors.YELLOW}Distance: {route['distance']:.1f}m | Time: {route['time']:.1f}min{Colors.ENDC}")
            print(f"  {Colors.YELLOW}Load: {route['load']}/{route['capacity']} ({100*route['load']/route['capacity']:.1f}%){Colors.ENDC}")
            
            # Print route path
            path_str = f"{Colors.BLUE}"
            for j, (node, time) in enumerate(zip(route['nodes'], route['times'])):
                if j == 0:
                    path_str += f"Depot({node})"
                elif j == len(route['nodes']) - 1:
                    path_str += f" -> Depot({node})"
                else:
                    demand = data["demands"][node]
                    path_str += f" -> {node}(D:{demand},T:{time})"
            path_str += f"{Colors.ENDC}"
            print(f"  {path_str}\n")
    
    # Print summary statistics
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}Summary Statistics{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.CYAN}Total Distance: {total_distance:.1f}m ({total_distance/1000:.2f}km){Colors.ENDC}")
    print(f"{Colors.CYAN}Total Load: {total_load}{Colors.ENDC}")
    print(f"{Colors.CYAN}Total Time: {total_time:.1f} minutes ({total_time/60:.2f} hours){Colors.ENDC}")
    print(f"{Colors.CYAN}Active Vehicles: {sum(1 for r in route_info if r['distance'] > 0)}/{data['num_vehicles']}{Colors.ENDC}")
    print(f"{Colors.CYAN}Average Distance per Vehicle: {total_distance/max(1, sum(1 for r in route_info if r['distance'] > 0)):.1f}m{Colors.ENDC}")
    print(f"{Colors.CYAN}Average Load per Vehicle: {total_load/max(1, sum(1 for r in route_info if r['distance'] > 0)):.1f}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")
    
    return route_info


def plot_solution(data: Dict[str, Any], manager: pywrapcp.RoutingIndexManager,
                  routing: pywrapcp.RoutingModel, solution: pywrapcp.Assignment) -> None:
    """
    Create a visual plot of the solution using matplotlib.
    
    Args:
        data: The problem data dictionary.
        manager: The routing index manager.
        routing: The routing model.
        solution: The solution found by the solver.
    """
    # Extract coordinates from the domain model
    domain_model = data.get('domain_model')
    if not domain_model:
        print("Domain model not available for plotting. Skipping visualization.")
        return
    
    # Create a figure and axis
    plt.figure(figsize=(12, 10))
    ax = plt.gca()
    
    # Plot all customers
    customers = list(domain_model.customers_dict.values())
    customer_x = [c.latitude for c in customers]
    customer_y = [c.longitude for c in customers]
    
    # Separate depots and regular customers
    depot_indices = data.get('depot_indices', [])
    depot_x = [customers[i].latitude for i in depot_indices if i < len(customers)]
    depot_y = [customers[i].longitude for i in depot_indices if i < len(customers)]
    
    regular_customer_indices = [i for i in range(len(customers)) if i not in depot_indices]
    regular_customer_x = [customers[i].latitude for i in regular_customer_indices]
    regular_customer_y = [customers[i].longitude for i in regular_customer_indices]
    
    # Plot depots
    if depot_x:
        ax.scatter(depot_x, depot_y, c='red', s=200, marker='s', label='Depots', zorder=3)
        for i, (x, y) in enumerate(zip(depot_x, depot_y)):
            ax.annotate(f"D{depot_indices[i]}", (x, y), xytext=(5, 5),
                       textcoords='offset points', fontsize=8, fontweight='bold')
    
    # Plot regular customers
    if regular_customer_x:
        ax.scatter(regular_customer_x, regular_customer_y, c='blue', s=50, alpha=0.7,
                  label='Customers', zorder=2)
        for i in regular_customer_indices:
            x, y = customers[i].latitude, customers[i].longitude
            demand = data['demands'][i]
            ax.annotate(f"{i}({demand})", (x, y), xytext=(3, 3),
                       textcoords='offset points', fontsize=6)
    
    # Plot routes
    time_dimension = routing.GetDimensionOrDie("Time")
    colors = plt.cm.tab10(np.linspace(0, 1, data["num_vehicles"]))
    
    for vehicle_id in range(data["num_vehicles"]):
        index = routing.Start(vehicle_id)
        route_x = []
        route_y = []
        
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_x.append(customers[node_index].latitude)
            route_y.append(customers[node_index].longitude)
            
            previous_index = index
            index = solution.Value(routing.NextVar(index))
        
        # Add the final node
        node_index = manager.IndexToNode(index)
        route_x.append(customers[node_index].latitude)
        route_y.append(customers[node_index].longitude)
        
        # Only plot routes with actual work
        if len(route_x) > 2:  # More than just depot to depot
            ax.plot(route_x, route_y, color=colors[vehicle_id], linewidth=1.5,
                   alpha=0.7, label=f'Vehicle {vehicle_id}')
    
    # Add title and legend
    plt.title(f"CVRPTW-MD Solution - {data.get('dataset_name', 'Unknown Dataset')}", fontsize=14, fontweight='bold')
    plt.xlabel('Latitude', fontsize=12)
    plt.ylabel('Longitude', fontsize=12)
    plt.legend(loc='best', fontsize=8)
    plt.grid(True, alpha=0.3)
    
    # Add statistics as text
    total_distance = 0
    total_load = 0
    active_vehicles = 0
    
    for vehicle_id in range(data["num_vehicles"]):
        index = routing.Start(vehicle_id)
        route_distance = 0
        route_load = 0
        has_work = False
        
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_load += data["demands"][node_index]
            
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(
                previous_index, index, vehicle_id
            )
            has_work = True
        
        if has_work:
            total_distance += route_distance
            total_load += route_load
            active_vehicles += 1
    
    stats_text = f"Total Distance: {total_distance/1000:.2f}km\n"
    stats_text += f"Total Load: {total_load}\n"
    stats_text += f"Active Vehicles: {active_vehicles}/{data['num_vehicles']}"
    
    plt.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=10,
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.show()


def export_solution_to_file(data: Dict[str, Any], manager: pywrapcp.RoutingIndexManager,
                           routing: pywrapcp.RoutingModel, solution: pywrapcp.Assignment,
                           output_path: str = None) -> None:
    """
    Export the solution to a text file in a formatted way.
    
    Args:
        data: The problem data dictionary.
        manager: The routing index manager.
        routing: The routing model.
        solution: The solution found by the solver.
        output_path: Path to save the output file. If None, generates a default name.
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dataset_name = data.get('dataset_name', 'unknown').replace('.vrp', '')
        output_path = f"cvrptw_solution_{dataset_name}_{timestamp}.txt"
    
    with open(output_path, 'w') as f:
        # Redirect print statements to file
        import sys
        original_stdout = sys.stdout
        sys.stdout = f
        
        try:
            print_solution_pretty(data, manager, routing, solution)
        finally:
            sys.stdout = original_stdout
    
    print(f"Solution exported to: {output_path}")


def setup_distance_callback(routing: pywrapcp.RoutingModel, 
                           manager: pywrapcp.RoutingIndexManager,
                           data: Dict[str, Any]) -> int:
    """
    Set up the distance callback for the routing model.
    
    Args:
        routing: The routing model.
        manager: The routing index manager.
        data: The problem data dictionary.
        
    Returns:
        The transit callback index.
    """
    def distance_callback(from_index: int, to_index: int) -> int:
        """Returns the distance between the two nodes."""
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data["distance_matrix"][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    return transit_callback_index


def setup_capacity_constraints(routing: pywrapcp.RoutingModel,
                               manager: pywrapcp.RoutingIndexManager,
                               data: Dict[str, Any]) -> None:
    """
    Set up capacity constraints for the routing model.
    
    Args:
        routing: The routing model.
        manager: The routing index manager.
        data: The problem data dictionary.
    """
    def demand_callback(from_index: int) -> int:
        """Returns the demand of the node."""
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


def setup_time_constraints(routing: pywrapcp.RoutingModel,
                          manager: pywrapcp.RoutingIndexManager,
                          data: Dict[str, Any]) -> None:
    """
    Set up time window constraints for the routing model.
    
    Args:
        routing: The routing model.
        manager: The routing index manager.
        data: The problem data dictionary.
    """
    def time_callback(from_index: int, to_index: int) -> int:
        """Returns the travel time between the two nodes."""
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        distance_km = data["distance_matrix"][from_node][to_node] / 1000.0
        travel_time = distance_km / data["speed"] * 60.0  # Convert to minutes
        # Add service time for the destination node (except for depots)
        service_time = data["service_times"][to_node] if to_node not in data["depot_indices"] else 0
        return int(travel_time + service_time)

    transit_time_callback_index = routing.RegisterTransitCallback(time_callback)
    
    routing.AddDimension(
        transit_time_callback_index,
        ALLOWED_WAITING_TIME,  # allow waiting time
        MAX_TIME_PER_VEHICLE,  # maximum time per vehicle
        False,  # Don't force start cumul to zero
        "Time"
    )
    
    time_dimension = routing.GetDimensionOrDie("Time")
    
    # Add time window constraints for all locations
    for location_idx, time_window in enumerate(data["time_windows"]):
        index = manager.NodeToIndex(location_idx)
        # Ensure time window values are valid
        start_time = max(0, time_window[0])
        end_time = max(start_time, time_window[1])
        time_dimension.CumulVar(index).SetRange(start_time, end_time)
    
    # Instantiate route start and end times to produce feasible times
    for i in range(data["num_vehicles"]):
        routing.AddVariableMinimizedByFinalizer(
            time_dimension.CumulVar(routing.Start(i)))
        routing.AddVariableMinimizedByFinalizer(
            time_dimension.CumulVar(routing.End(i)))


def setup_search_parameters() -> pywrapcp.DefaultRoutingSearchParameters:
    """
    Set up the search parameters for the routing solver.
    
    Returns:
        The configured search parameters.
    """
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.FromSeconds(SOLVE_TIME_LIMIT_SECONDS)
    return search_parameters


def solve_cvrptw_md(file_path: Optional[Path] = None,
                    export_to_file: bool = False,
                    output_path: Optional[str] = None) -> Optional[pywrapcp.Assignment]:
    """
    Solve the CVRPTW-MD problem.
    
    Args:
        file_path: Path to the VRP data file. If None, uses default dataset.
        export_to_file: Whether to export the solution to a text file.
        output_path: Custom path for the exported file. If None, generates a default name.
        
    Returns:
        The solution found by the solver, or None if no solution was found.
    """
    # Create the data model
    data = create_data_model(file_path)
    
    # Create the routing index manager
    manager = pywrapcp.RoutingIndexManager(
        len(data["distance_matrix"]),
        data["num_vehicles"],
        data["starts"],
        data["ends"]
    )
    
    # Create the routing model
    routing = pywrapcp.RoutingModel(manager)
    
    # Set up various constraints and callbacks
    setup_distance_callback(routing, manager, data)
    setup_capacity_constraints(routing, manager, data)
    setup_time_constraints(routing, manager, data)
    
    # Set up search parameters
    search_parameters = setup_search_parameters()
    
    # Solve the problem
    solution = routing.SolveWithParameters(search_parameters)
    
    # Print solution if found
    if solution:
        print_solution(data, manager, routing, solution)
        
        # Export to file if requested
        if export_to_file:
            export_solution_to_file(data, manager, routing, solution, output_path)
    else:
        print("No solution found!")
    
    return solution


def main() -> None:
    """Main function to solve the CVRPTW-MD problem."""
    # Solve with pretty printing and visualization
    # Set export_to_file=True to save the solution to a text file
    solve_cvrptw_md(export_to_file=False)


if __name__ == "__main__":
    main()
