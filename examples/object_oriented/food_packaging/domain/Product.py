



class Product:
    def __init__(self, id=None, name=None):
        self.id = id
        self.name = name
        self.cleaning_durations = {}

    def __str__(self):
        return self.name if self.name else ""

    def get_cleanup_duration(self, previous_product):
        cleanup_duration = self.cleaning_durations.get(previous_product)
        if cleanup_duration is None:
            raise ValueError(f"Cleanup duration previous_product ({previous_product}) "
                           f"to to_product ({self}) is missing.")
        return cleanup_duration