from dataclasses import dataclass, field
from greyjack.score_calculation.greynet.greynet_fact import greynet_fact
from greyjack.variables.GJInteger import GJInteger

@greynet_fact
@dataclass
class CotLocation:
    """Represents a physical location with coordinates. This is a problem fact."""
    location_id: int
    latitude: float
    longitude: float