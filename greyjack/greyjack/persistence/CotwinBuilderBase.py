


from abc import ABC, abstractmethod

class CotwinBuilderBase(ABC):

    @abstractmethod
    def build_cotwin(self, domain, is_already_initialized):
        pass