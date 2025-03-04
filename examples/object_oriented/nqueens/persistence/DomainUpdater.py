

class DomainUpdater():
    def __init__(self):
        pass

    @staticmethod
    def update_domain(domain_model, cotwin_solution):

        for i, row_id in enumerate( cotwin_solution.variable_values_dict.values() ):
            domain_model.queens[i].row.row_id = row_id


        return domain_model

