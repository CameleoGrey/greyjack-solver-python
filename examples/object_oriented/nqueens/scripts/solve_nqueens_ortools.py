"""OR-Tools solution to the N-queens problem."""
import sys
import time
from ortools.sat.python import cp_model


class NQueenSolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, queens: list[cp_model.IntVar]):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__queens = queens
        self.__solution_count = 0
        self.__start_time = time.time()

    @property
    def solution_count(self) -> int:
        return self.__solution_count

    def on_solution_callback(self):
        current_time = time.time()
        print(
            f"Solution {self.__solution_count}, "
            f"time = {current_time - self.__start_time} s"
        )
        self.__solution_count += 1

        """all_queens = range(len(self.__queens))
        for i in all_queens:
            for j in all_queens:
                if self.value(self.__queens[j]) == i:
                    # There is a queen in column j, row i.
                    print("Q", end=" ")
                else:
                    print("_", end=" ")
            print()
        print()"""



def main(board_size: int) -> None:
    # Creates the solver.
    model = cp_model.CpModel()

    # Creates the variables.
    # There are `board_size` number of variables, one for a queen in each column
    # of the board. The value of each variable is the row that the queen is in.
    queens = [model.new_int_var(0, board_size - 1, f"x_{i}") for i in range(board_size)]

    # Creates the constraints.
    # All rows must be different.
    model.add_all_different(queens)

    # No two queens can be on the same diagonal.
    model.add_all_different(queens[i] + i for i in range(board_size))
    model.add_all_different(queens[i] - i for i in range(board_size))

    # Solve the model.
    solver = cp_model.CpSolver()
    solution_printer = NQueenSolutionPrinter(queens)
    solver.parameters.enumerate_all_solutions = False
    solver.solve(model, solution_printer)

    # Statistics.
    print("\nStatistics")
    print(f"  conflicts      : {solver.num_conflicts}")
    print(f"  branches       : {solver.num_branches}")
    print(f"  wall time      : {solver.wall_time} s")
    print(f"  solutions found: {solution_printer.solution_count}")


if __name__ == "__main__":
    # By default, solve the 8x8 problem.
    size = 256
    if len(sys.argv) > 1:
        size = int(sys.argv[1])
    main(size)