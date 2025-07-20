# greynet/collectors/composite_collector.py
from .base_collector import BaseCollector

class CompositeCollector(BaseCollector):
    """
    A collector that wraps multiple collectors to perform several aggregations
    on the same group simultaneously.
    """
    def __init__(self, collector_suppliers: dict):
        """
        Initializes the CompositeCollector.
        
        Args:
            collector_suppliers (dict): A dictionary where keys are strings (the name
                                      of the aggregation) and values are collector
                                      suppliers (e.g., Collectors.count()).
        """
        # Instantiate each collector from its supplier function
        self._collectors = {
            key: supplier() for key, supplier in collector_suppliers.items()
        }
        # Maps an item's memory ID to its list of undo functions from sub-collectors
        self._undo_map = {}

    def insert(self, item):
        item_id = item.greynet_fact_id
        # It's possible for an item to be re-inserted in some complex update scenarios,
        # so we ensure a clean list of undo functions.
        self._undo_map[item_id] = []
        
        for collector in self._collectors.values():
            undo_func = collector.insert(item)
            self._undo_map[item_id].append(undo_func)
            
        def undo():
            """The undo function to be returned for this insertion."""
            if item_id in self._undo_map:
                for single_undo_func in self._undo_map[item_id]:
                    single_undo_func()
                del self._undo_map[item_id]
        
        return undo

    def result(self):
        """
        Returns a dictionary containing the results from each nested collector.
        """
        return {
            key: collector.result() for key, collector in self._collectors.items()
        }

    def is_empty(self):
        """
        The composite is considered empty if its collectors have not processed any items.
        We can check the state of the first collector as they are all populated in sync.
        """
        if not self._collectors:
            return True
        
        # Get the first collector instance to check its state
        first_collector = next(iter(self._collectors.values()))
        return first_collector.is_empty()

