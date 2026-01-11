from .general import General
from .user import User, UserSimple, UpdateUser, DiscordUser
from .event import EventSimple, Event

User.model_rebuild()
Event.model_rebuild()