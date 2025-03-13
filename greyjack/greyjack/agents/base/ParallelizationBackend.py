
from enum import Enum

class ParallelizationBackend(Enum):
    Multiprocessing = 0 # for max performance
    Threading = 1 # for debugging