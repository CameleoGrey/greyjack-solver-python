# greynet/common/index_properties.py
class IndexProperties:
    def __init__(self, property_retriever):
        self._property_retriever = property_retriever

    def get_property(self, obj):
        return self._property_retriever(obj)