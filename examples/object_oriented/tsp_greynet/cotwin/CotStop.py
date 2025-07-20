
from dataclasses import dataclass, field
from greyjack.score_calculation.greynet.greynet_fact import greynet_fact
from greyjack.variables.GJInteger import GJInteger

@greynet_fact
@dataclass
class CotStop:
    """
    Represents a stop that must be visited. This is our main Planning Entity.
    The planning variable 'previous_stop_id' determines which stop comes before this one in the tour.
    """
    location_id: int
    previous_stop_id: GJInteger = field(default=None)