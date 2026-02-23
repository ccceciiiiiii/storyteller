"""SQLAlchemy models - Agent, Story, Participation, Turn."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class StoryStatus(str, enum.Enum):
    open = "open"
    active = "active"
    ended = "ended"


class JudgeMethod(str, enum.Enum):
    keyword = "keyword"
    llm = "llm"


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    preference = Column(String(64), nullable=False)  # dark, romantic, melodramatic, suspenseful, comedic
    preference_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    participations = relationship("Participation", back_populates="agent")
    turns = relationship("Turn", back_populates="agent")


class Story(Base):
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(512), nullable=False)
    seed_text = Column(Text, nullable=False)
    status = Column(SQLEnum(StoryStatus), default=StoryStatus.open, nullable=False)
    max_rounds = Column(Integer, default=10, nullable=False)
    current_round = Column(Integer, default=0, nullable=False)
    max_participants = Column(Integer, default=5, nullable=False)
    winner_agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    judge_method = Column(SQLEnum(JudgeMethod), default=JudgeMethod.keyword, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    participations = relationship("Participation", back_populates="story", cascade="all, delete-orphan")
    turns = relationship("Turn", back_populates="story", order_by="Turn.round_number", cascade="all, delete-orphan")


class Participation(Base):
    __tablename__ = "participations"

    story_id = Column(Integer, ForeignKey("stories.id"), primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), primary_key=True)
    turns_used = Column(Integer, default=0, nullable=False)
    join_time = Column(DateTime, default=datetime.utcnow)

    story = relationship("Story", back_populates="participations")
    agent = relationship("Agent", back_populates="participations")


class Turn(Base):
    __tablename__ = "turns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    story = relationship("Story", back_populates="turns")
    agent = relationship("Agent", back_populates="turns")
