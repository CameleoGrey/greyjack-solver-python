



class Employee():

    def __init__(self, name, skills):

        self.name = name
        self.skills = skills
        self.unavailable_dates = []
        self.undesired_dates = []
        self.desired_dates = []

        pass

    def __str__(self):
        
        employee_info = "{} ({}) | Unavailable dates {} | Undesired dates {} | Desired dates {}".format(self.name, self.skills, 
                                                                                                        self.unavailable_dates, self.undesired_dates, 
                                                                                                        self.desired_dates)

        
        return employee_info