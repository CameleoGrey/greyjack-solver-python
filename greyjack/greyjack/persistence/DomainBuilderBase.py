

from abc import ABC, abstractmethod
from copy import deepcopy

class DomainBuilderBase(ABC):
    
    # Default function to build domain model without using existing solution
    @abstractmethod
    def build_domain_from_scratch(self):
        pass

    # For multistage solving or extracting human-understandable representation for
    # post-solving actions (for example: print metrics, check correctness of solution,
    # serializing to JSON the whole domain and sending to another service).
    # means raw solution JSON 
    @abstractmethod
    def build_from_solution(self, solution):
        pass

    # For multistage solving cases, when you need to take solution
    # from the N-1 stage, build domain from solution, then change that domain
    # by some logic (for example: freeze some variables to prevent changes in the Nth stage)
    # and then use it as initial solution.
    # Suggest just to use return domain.clone() in most cases due to the described logic above.
    @abstractmethod
    def build_from_domain(self, domain):
        return deepcopy(domain)