

class CotShift():

    def __init__(self, id, start, end, location, required_skill, employee):

        self.shift_id = id
        self.start = start
        self.end = end
        self.start_date = self.start.date()
        self.location = location
        self.required_skill = required_skill
        self.employee_id = employee

        pass