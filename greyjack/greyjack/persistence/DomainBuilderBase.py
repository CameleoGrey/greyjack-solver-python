

from abc import ABC, abstractmethod
from copy import deepcopy

class DomainBuilderBase(ABC):
    
    # Default function to build domain model without using existing solution or domain object
    @abstractmethod
    def build_domain_from_scratch(self):
        pass

    # For multistage solving or extracting human-understandable representation for
    # post-solving actions (for example: print metrics, check correctness of solution,
    # serializing to JSON the whole domain and sending to another service).
    # means raw solution JSON 
    # initial_domain - is domain object, that will be updated by values of solution (GJSolution)
    # WARNING! In a replanning scenario initial_domain=None will (probably) cause incorrect update
    # due to offset of enities (for example: build_from_scratch() builds 10 vehicles, but domain for 
    # replanning has 9 vehicles (something was removed, that's why need replanning))
    # For replanning scenario always write case for processing initial_domain=YOUR_DOMAIN_OBJECT_FOR_REPLANNING
    @abstractmethod
    def build_from_solution(self, solution, initial_domain=None):
        pass

    # For multistage solving cases, when you need to take solution
    # from the N-1 stage, build domain from solution, then change that domain
    # by some logic (for example: freeze some variables to prevent changes in the Nth stage)
    # and then use it as initial solution.
    # Suggest just to use return domain.clone() in most cases due to the described logic above.
    @abstractmethod
    def build_from_domain(self, domain):
        return deepcopy(domain)