import enum

from sqlalchemy import Column, String, BigInteger, ForeignKey, CheckConstraint, Enum, ARRAY
from sqlalchemy.ext.declarative import declarative_base

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


class User(Base):
    __tablename__ = "users"
    
    # index
    discord_id = Column(BigInteger, primary_key=True, index=True, nullable=False, unique=True, autoincrement=False)
    
    # attrbutes
    status = Column(Enum(Status, name="enum_status"), nullable=False, default=Status.online)
    skills = Column(ARRAY(Enum(Skills, name="enum_skills")))
    rhythm_games = Column(ARRAY(Enum(RhythmGames, name="enum_rhythm_games")))
    

# event

"""
Event:
- id
- event_id ( ctftime, nullable, unique )
- discord channel id (if custom_event -> index)
- discord scheduled event id
- start
- finish 
- title

challenge:
- id
- event_id
- name
- status (solved, need help, processing)
- thread id

Display_weight:
- User_id
- challenge_id
- weight

User and event: many to many
User and challenge: many to many
"""