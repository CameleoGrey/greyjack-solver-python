

from greyjack.SolverOOP import SolverOOP
from greyjack.agents.base.ParallelizationBackend import ParallelizationBackend
from greyjack.agents.base.LoggingLevel import LoggingLevel

class SolverPureMath(SolverOOP):

    def __init__(self, 
                 math_model, 
                 agent,
                 parallelization_backend=ParallelizationBackend.Multiprocessing, 
                 logging_level=LoggingLevel.Info, 
                 n_jobs=None, 
                 score_precision=None,
                 available_ports=None, 
                 default_port="25000"):
        
        super().__init__(
            domain_builder=math_model, 
            cotwin_builder=None, 
            agent=agent,
            parallelization_backend=parallelization_backend, 
            logging_level=logging_level, 
            n_jobs=n_jobs, 
            score_precision=score_precision,
            available_ports=available_ports, 
            default_port=default_port,
            initial_solution=None
        )

        pass