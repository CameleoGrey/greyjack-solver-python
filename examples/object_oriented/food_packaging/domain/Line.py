



class Line:
    def __init__(self, id=None, name=None, operator=None, start_date_time=None):
        self.id = id
        self.name = name
        self.operator = operator
        self.start_date_time = start_date_time
        self.jobs = []

    def __str__(self):
       
        line_info = ""
        line_info += "Line: {} | start_date_time: {}".format(self.id, self.start_date_time) + "\n"
        
        for job in self.jobs:
            line_info += str(job) + "\n"
        
        return line_info

       