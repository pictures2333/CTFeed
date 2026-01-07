import enum

from sqlalchemy import Column, String, BigInteger, ForeignKey, CheckConstraint, Enum, ARRAY, Table, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# User
class Status(enum.Enum):
    online="online"
    offline="offline"


class Skills(enum.Enum):
    web="Web"
    reverse="Reverse Engineering"
    pwn="Pwn"
    crypto="Crypto"
    misc="Misc"
    forensics="Forensics"
    web3="Web3"
    Pentest="Pentest"
    ppc="PPC"
    osint="OSINT"
    hardware="Hardware"
    network="Network"


class RhythmGames(enum.Enum):
    pjsk="Project Sekai"
    phigros="Phigros"
    arcaea="Arcaea"
    osu="osu!"
    maimai="maimai"
    chunithm="CHUNITHM"
    sdvx="SOUND VOLTEX"


user_event = Table(
    "user_event",
    Base.metadata,
    Column("user_discord_id", ForeignKey("users.discord_id", ondelete="RESTRICT"), primary_key=True),
    Column("event_id", ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    
    # index
    discord_id = Column(BigInteger, primary_key=True, index=True, nullable=False, unique=True, autoincrement=False)
    
    # attrbutes
    status = Column(Enum(Status, name="enum_status"), nullable=False, default=Status.online)
    skills = Column(ARRAY(Enum(Skills, name="enum_skills")))
    rhythm_games = Column(ARRAY(Enum(RhythmGames, name="enum_rhythm_games")))
    
    # event
    events = relationship(
        "Event",
        secondary=user_event,
        back_populates="users"
    )
    

# event
class Event(Base):
    __tablename__ = "events"
    
    # index
    id = Column(BigInteger, primary_key=True, index=True, nullable=False, unique=True, autoincrement=True)
    
    # general attrbutes
    archived = Column(Boolean, nullable=False, default=False)
    
    # event attrbutes
    # event_id
    # - from CTFTime -> not null
    # - custom event -> null
    event_id = Column(BigInteger, nullable=True, unique=True)
    title = Column(String, nullable=True)
    start = Column(BigInteger, nullable=True)
    finish = Column(BigInteger, nullable=True)
    
    # discord attrbutes
    channel_id = Column(BigInteger, nullable=True, unique=True)
    scheduled_event_id = Column(BigInteger, nullable=True, unique=True)
    
    # user
    users = relationship(
        "User",
        secondary=user_event,
        back_populates="events"
    )
    
    # challenges
    challenges = relationship("Challenge", back_populates="event")


# challenge
class ChallengeStatus(enum.Enum):
    solved="solved"
    need_help="need_help"
    processing="processing"


class Challenge(Base):
    __tablename__ = "challenges"
    
    # index
    id = Column(BigInteger, primary_key=True, index=True, nullable=False, unique=True, autoincrement=True)
    
    # attrbutes
    event_id = Column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    event = relationship("Event", back_populates="challenges")
    name = Column(String, nullable=False)
    status = Column(Enum(ChallengeStatus, name="enum_challenge_status"), nullable=False, default=ChallengeStatus.processing)
    
    # discord attrbutes
    thread_id = Column(BigInteger, nullable=False, unique=True)


"""
Display_weight: for 配題
- User_id
- challenge_id
- weight

User and challenge: many to many
"""