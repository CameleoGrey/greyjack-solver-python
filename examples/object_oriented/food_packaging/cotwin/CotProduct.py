

class CotProduct:
    def __init__(self, id=None, name=None):
        self.product_id = id
        self.name = name

    def __str__(self):
        return self.name if self.name else ""