



class PackagingSchedule:
    def __init__(self):

        self.products = []
        self.lines = []
        self.jobs = []
    
    def print_schedule(self):
        
        schedule_info = ""
        for line in self.lines:
            schedule_info += "######################################################" + "\n"
            schedule_info += str(line) + "\n"
        
        print(schedule_info)
