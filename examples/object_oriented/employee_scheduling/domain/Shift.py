

class Shift():

    def __init__(self, id, start, end, location, required_skill):

        self.id = id
        self.start = start
        self.end = end
        self.location = location
        self.required_skill = required_skill
        self.employee = None

        pass

    def __str__(self):
        
        shift_info = "{}: {} - {} ({})".format(self.id, self.start, self.end, self.required_skill)

        return shift_info