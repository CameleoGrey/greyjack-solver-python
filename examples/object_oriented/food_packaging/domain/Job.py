



class Job:
    def __init__(self, id=None, name=None, product=None, duration=None, min_start_time=None,
                 ideal_end_time=None, max_end_time=None, priority=0, pinned=False):
        
        self.id = id
        self.name = name
        self.product = product
        self.duration = duration
        self.min_start_time = min_start_time
        self.ideal_end_time = ideal_end_time
        self.max_end_time = max_end_time
        self.priority = priority
        self.pinned = pinned
        
        self.line = None

    def __str__(self):
        job_info = "{} ({}) | duration {} | min_start_time {} | max_end_time {} | ideal_end_time {}".format(self.id, self.name, self.duration, 
                                                                                                                        self.min_start_time, self.max_end_time, 
                                                                                                                        self.ideal_end_time)
        return job_info