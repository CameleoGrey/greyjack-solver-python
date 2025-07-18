# greynet/common/index/uni_index.py
from collections import defaultdict

class UniIndex:
    def __init__(self, index_properties):
        self._index_properties = index_properties
        self._index_map = defaultdict(list)

    def put(self, tuple_):
        key = self._index_properties.get_property(tuple_)
        self._index_map[key].append(tuple_)

    def get(self, key):
        return self._index_map.get(key, [])

    def remove(self, tuple_):
        key = self._index_properties.get_property(tuple_)
        if key in self._index_map:
            try:
                self._index_map[key].remove(tuple_)
                if not self._index_map[key]:
                    del self._index_map[key]
            except ValueError:
                pass # Tuple was already removed.