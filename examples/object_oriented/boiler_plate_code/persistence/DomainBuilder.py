
import random

from greyjack.persistence.DomainBuilderBase import DomainBuilderBase

class DomainBuilder(DomainBuilderBase):

    def __init__(self, random_seed=45):
        super().__init__()

        self.random_seed = random_seed

    def build_domain_from_scratch(self):
        return domain
    
    def build_from_solution(self, solution, initial_domain=None):
        return domain

    def build_from_domain(self, domain):
        return super().build_from_domain(domain)


