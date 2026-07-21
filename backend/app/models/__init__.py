"""ORM models. Importing this package registers every table on Base.metadata."""
from app.models.assignment import AssignmentRow
from app.models.lap import LapRow
from app.models.reference_lap import ReferenceLapRow
from app.models.swim import SwimRow
from app.models.swimmer import SwimmerRow
from app.models.user import UserRow
from app.models.venue import VenueRow

__all__ = [
    "AssignmentRow",
    "LapRow",
    "ReferenceLapRow",
    "SwimRow",
    "SwimmerRow",
    "UserRow",
    "VenueRow",
]
