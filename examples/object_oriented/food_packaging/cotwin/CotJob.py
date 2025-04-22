



class CotJob:
    def __init__(self, job_id=None, name=None, product_id=None, duration=None, min_start_time=None,
                 ideal_end_time=None, max_end_time=None, priority=0, line_id=None, line_position=None):
        
        self.job_id = job_id
        self.name = name
        self.product_id = product_id
        self.duration = duration
        self.min_start_time = min_start_time
        self.ideal_end_time = ideal_end_time
        self.max_end_time = max_end_time
        self.priority = priority
        
        self.line_id = line_id
        self.line_position = line_position

    def __str__(self):
        return f"{self.id}({self.product.name})" if self.product else f"{self.id}(None)"