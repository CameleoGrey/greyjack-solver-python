import uuid

def greynet_fact(cls):
    """
    A class decorator that adds an 'greynet_fact_id' attribute to each instance of the class
    and overrides the __hash__ method to compute the hash based on the instance-specific greynet_fact_id.
    """
    original_init = cls.__init__

    def __init__(self, *args, **kwargs):
        self.greynet_fact_id = uuid.uuid4()
        if original_init:
            original_init(self, *args, **kwargs)

    def hash_function(self):
        return hash(self.greynet_fact_id)
    
    def eq_function(self, other):
        if isinstance(other, cls):
            return self.greynet_fact_id == other.greynet_fact_id
        return False

    cls.__init__ = __init__
    cls.__hash__ = hash_function
    cls.__eq__ = eq_function
    return cls

