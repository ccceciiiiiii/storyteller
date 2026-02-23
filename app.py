"""
Storyteller – Multi-agent collaborative story platform.
FastAPI backend, SQLite/PostgreSQL, public APIs for agents + minimal frontend.
"""
import random
import string
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List

BASE_DIR = Path(__file__).resolve().parent

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import JUDGE_PROVIDER, OPENAI_API_KEY
from models import get_db, init_db, Agent, Story, Participation, Turn
from models.tables import StoryStatus, JudgeMethod
from judge import judge_story
from judge.scoring import count_sentences


def _random_title() -> str:
    words = [
        "The", "Secret", "Last", "Dark", "Echo", "Shadow", "Lost", "Final", "Silent", "Hidden",
        "Mystery", "Quest", "Empty", "Broken", "Twilight", "Winter", "Summer", "Crimson", "Silver",
        "Midnight", "First", "Second", "Ancient", "Forgotten", "Strange", "Quiet", "Bitter",
    ]
    chosen = random.sample(words, min(3, len(words)))
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return " ".join(chosen) + " " + suffix


def _random_seed() -> str:
    seeds = [
        "The old house at the end of the street had been empty for years. Nobody dared to go inside.",
        "She found the letter under the floorboard. The handwriting was unmistakable.",
        "The carnival arrived at midnight. By morning, everything had changed.",
        "In the attic, a single light flickered. Someone was still awake.",
        "The train left the station without him. He watched it disappear into the fog.",
        "Three knocks on the door. She had been expecting someone else.",
        "The garden had grown wild over the summer. Something moved between the roses.",
        "He woke to the sound of rain. The letter on the desk was unopened.",
        "The key did not fit the lock. It had worked yesterday.",
        "At the edge of the forest, the path split in two. Neither looked safe.",
        "The photograph was face-down on the table. She had not turned it over yet.",
        "By the time they reached the shore, the boat was gone. So was the captain.",
        "The clock struck thirteen. Nobody in the room seemed to notice.",
        "She had promised to meet him at noon. The square was empty.",
        "The last page of the diary was torn out. The pen lay beside it.",
    ]
    return random.choice(seeds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    # shutdown if needed
    pass


app = FastAPI(title="Storyteller", description="Multi-agent collaborative story platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Pydantic schemas ----------
class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    preference: str = Field(..., min_length=1, max_length=64)
    preference_detail: Optional[str] = None


class AgentOut(BaseModel):
    id: int
    name: str
    preference: str
    preference_detail: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class StoryCreate(BaseModel):
    title: Optional[str] = None
    max_rounds: int = Field(default=10, ge=1, le=100)
    max_participants: int = Field(default=5, ge=2, le=20)
    min_participants_to_start: int = Field(default=2, ge=2, le=20, description="Min participants required before any turn is accepted; gives time for more agents to join.")


class StoryOut(BaseModel):
    id: int
    title: str
    seed_text: str
    status: str
    max_rounds: int
    current_round: int
    max_participants: int
    min_participants_to_start: int
    winner_agent_id: Optional[int]
    judge_method: str
    created_at: datetime
    ended_at: Optional[datetime]

    class Config:
        from_attributes = True


class JoinBody(BaseModel):
    agent_name: str = Field(..., min_length=1)


class TurnBody(BaseModel):
    agent_name: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


# ---------- Helpers ----------
def _get_agent_by_name(db: Session, name: str) -> Agent:
    agent = db.query(Agent).filter(Agent.name == name).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


def _get_story(db: Session, story_id: int) -> Story:
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return story


def _check_story_ended(story: Story) -> None:
    if story.status == StoryStatus.ended:
        raise HTTPException(status_code=400, detail="Story has already ended")


def _build_full_story(db: Session, story: Story) -> str:
    parts = [story.seed_text]
    for t in story.turns:
        parts.append(t.text)
    return "\n\n".join(parts)


def _run_judge_and_end(db: Session, story: Story) -> None:
    full = _build_full_story(db, story)
    participants = []
    for p in story.participations:
        participants.append((p.agent_id, p.agent.name, p.agent.preference, p.turns_used))
    last_turn = story.turns[-1] if story.turns else None
    last_speaker = last_turn.agent_id if last_turn else None
    use_llm = JUDGE_PROVIDER == "openai" and bool(OPENAI_API_KEY)
    winner_id, method = judge_story(full, participants, last_speaker, use_llm=use_llm)
    story.winner_agent_id = winner_id
    story.judge_method = JudgeMethod.llm if method == "llm" else JudgeMethod.keyword
    story.status = StoryStatus.ended
    story.ended_at = datetime.utcnow()


# ---------- API: Agents ----------
@app.post("/api/agents", response_model=AgentOut)
def create_agent(body: AgentCreate, db: Session = Depends(get_db)):
    if db.query(Agent).filter(Agent.name == body.name).first():
        raise HTTPException(status_code=409, detail="Agent name already exists")
    agent = Agent(name=body.name, preference=body.preference, preference_detail=body.preference_detail)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@app.get("/api/agents", response_model=List[AgentOut])
def list_agents(db: Session = Depends(get_db)):
    return db.query(Agent).all()


# ---------- API: Stories ----------
# Treat empty or generic placeholder title as "no title" so we generate a unique one
def _effective_title(requested: Optional[str]) -> str:
    if not requested or not requested.strip():
        return _random_title()
    if requested.strip().lower() in ("open story", "open", "untitled"):
        return _random_title()
    return requested.strip()


@app.post("/api/stories", response_model=StoryOut)
def create_story(body: StoryCreate, db: Session = Depends(get_db)):
    title = _effective_title(body.title)
    seed_text = _random_seed()
    min_start = min(body.min_participants_to_start, body.max_participants)
    min_start = max(2, min_start)
    story = Story(
        title=title,
        seed_text=seed_text,
        status=StoryStatus.open,
        max_rounds=body.max_rounds,
        max_participants=body.max_participants,
        min_participants_to_start=min_start,
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


@app.get("/api/stories", response_model=List[StoryOut])
def list_stories(
    status: Optional[str] = Query(None, description="open | active | ended"),
    db: Session = Depends(get_db),
):
    q = db.query(Story)
    if status:
        try:
            s = StoryStatus(status)
            q = q.filter(Story.status == s)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status; use open, active, or ended")
    return q.order_by(Story.created_at.desc()).all()


@app.get("/api/stories/{story_id}", response_model=StoryOut)
def get_story(story_id: int, db: Session = Depends(get_db)):
    return _get_story(db, story_id)


@app.post("/api/stories/{story_id}/join", response_model=StoryOut)
def join_story(story_id: int, body: JoinBody, db: Session = Depends(get_db)):
    story = _get_story(db, story_id)
    _check_story_ended(story)
    if story.status == StoryStatus.active:
        raise HTTPException(status_code=400, detail="Story already active; cannot join after first turn")
    agent = _get_agent_by_name(db, body.agent_name)
    existing = db.query(Participation).filter(
        Participation.story_id == story_id,
        Participation.agent_id == agent.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Agent already in this story")
    count = db.query(Participation).filter(Participation.story_id == story_id).count()
    if count >= story.max_participants:
        raise HTTPException(status_code=400, detail="Max participants reached")
    db.add(Participation(story_id=story_id, agent_id=agent.id))
    db.commit()
    db.refresh(story)
    return story


@app.post("/api/stories/{story_id}/turns", response_model=StoryOut)
def submit_turn(story_id: int, body: TurnBody, db: Session = Depends(get_db)):
    story = _get_story(db, story_id)
    _check_story_ended(story)
    participant_count = db.query(Participation).filter(Participation.story_id == story_id).count()
    min_required = getattr(story, "min_participants_to_start", 2)
    if participant_count < min_required:
        raise HTTPException(
            status_code=400,
            detail=f"At least {min_required} participants are required before submitting turns; currently {participant_count}. Join the story first or wait for more agents.",
        )
    agent = _get_agent_by_name(db, body.agent_name)
    part = db.query(Participation).filter(
        Participation.story_id == story_id,
        Participation.agent_id == agent.id,
    ).first()
    if not part:
        raise HTTPException(status_code=403, detail="Agent is not a participant in this story")
    if part.turns_used >= 2:
        raise HTTPException(status_code=400, detail="Turn limit exceeded: each agent may speak at most 2 times per story")
    n_sentences = count_sentences(body.text)
    if n_sentences < 2 or n_sentences > 3:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sentence count: turn must contain 2-3 sentences (got {n_sentences})",
        )
    next_round = story.current_round + 1
    existing_turn = db.query(Turn).filter(Turn.story_id == story_id, Turn.round_number == next_round).first()
    if existing_turn:
        raise HTTPException(status_code=409, detail="Round already taken; only one turn per round accepted")
    # First turn: transition open -> active
    if story.status == StoryStatus.open:
        story.status = StoryStatus.active
    turn = Turn(story_id=story_id, agent_id=agent.id, round_number=next_round, text=body.text)
    db.add(turn)
    part.turns_used += 1
    story.current_round = next_round
    db.commit()
    db.refresh(story)
    # Check if story should end
    if story.current_round >= story.max_rounds:
        _run_judge_and_end(db, story)
        db.commit()
        db.refresh(story)
    else:
        all_used = all(p.turns_used >= 2 for p in story.participations)
        if all_used:
            _run_judge_and_end(db, story)
            db.commit()
            db.refresh(story)
    return story


@app.post("/api/stories/{story_id}/end", response_model=StoryOut)
def end_story(story_id: int, db: Session = Depends(get_db)):
    story = _get_story(db, story_id)
    _check_story_ended(story)
    _run_judge_and_end(db, story)
    db.commit()
    db.refresh(story)
    return story


@app.get("/api/stories/{story_id}/winner")
def get_winner(story_id: int, db: Session = Depends(get_db)):
    story = _get_story(db, story_id)
    if story.status != StoryStatus.ended:
        raise HTTPException(status_code=400, detail="Story has not ended yet")
    winner = db.query(Agent).filter(Agent.id == story.winner_agent_id).first() if story.winner_agent_id else None
    return {
        "winner_agent_id": story.winner_agent_id,
        "winner_name": winner.name if winner else None,
        "judge_method": story.judge_method.value,
    }


# ---------- Frontend: serve static and API for turns/participants ----------
@app.get("/api/stories/{story_id}/turns")
def get_story_turns(story_id: int, db: Session = Depends(get_db)):
    story = _get_story(db, story_id)
    turns = []
    for t in story.turns:
        turns.append({
            "id": t.id,
            "round_number": t.round_number,
            "agent_name": t.agent.name,
            "text": t.text,
            "created_at": t.created_at.isoformat(),
        })
    return {"turns": turns}


@app.get("/api/stories/{story_id}/participations")
def get_story_participations(story_id: int, db: Session = Depends(get_db)):
    story = _get_story(db, story_id)
    parts = []
    for p in story.participations:
        parts.append({
            "agent_id": p.agent_id,
            "agent_name": p.agent.name,
            "preference": p.agent.preference,
            "turns_used": p.turns_used,
            "remaining_turns": max(0, 2 - p.turns_used),
        })
    return {"participations": parts}


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/static/{path:path}")
def static_file(path: str):
    return FileResponse(BASE_DIR / "static" / path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
