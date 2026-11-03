from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from typing import Optional
import os

from .core.config import get_settings
from .models import Base, User, Skill, Task, Submission, UserSkillMastery, PeerReview, ScaffoldSession, HintFeedback
from .ai.scaffold_engine import ScaffoldEngine
from .ai.knowledge_graph import KnowledgeGraph
from .ai.pairing import PeerPairingEngine
from .core.sandbox import grade_submission

settings = get_settings()

# Database setup
def _make_engine():
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False}, pool_pre_ping=True, future=True)
    # Normalize postgres URLs so either scheme works.
    if url.startswith("postgresql://") and "+psycopg2" not in url and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return create_engine(url, pool_pre_ping=True, future=True)


engine = _make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Ensure schema exists even when the ASGI lifespan is not triggered (e.g. tests).
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Auth
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title=settings.PROJECT_NAME, version="1.1.0", lifespan=lifespan)

# CORS
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "project": settings.PROJECT_NAME, "version": "1.1.0"}


@app.get("/")
def root():
    return {"message": "SynapseFlow API is running", "version": "1.1.0"}


# ============================================================
# AUTH ENDPOINTS
# ============================================================

@app.post(f"{settings.API_V1_PREFIX}/auth/register")
def register(email: str, username: str, password: str, full_name: Optional[str] = None, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username taken")

    user = User(
        email=email,
        username=username,
        hashed_password=get_password_hash(password),
        full_name=full_name
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username, "email": user.email}


@app.post(f"{settings.API_V1_PREFIX}/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


# ============================================================
# SKILLS ENDPOINTS
# ============================================================

@app.get(f"{settings.API_V1_PREFIX}/skills/graph")
def get_skill_graph(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kg = KnowledgeGraph(db)
    return kg.get_skill_graph_for_user(current_user.id)


@app.get(f"{settings.API_V1_PREFIX}/skills/unlocked")
def get_unlocked_skills(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kg = KnowledgeGraph(db)
    return kg.get_unlocked_skills(current_user.id)


@app.get(f"{settings.API_V1_PREFIX}/skills/recommended")
def get_recommended_skill(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kg = KnowledgeGraph(db)
    return kg.get_recommended_next_skill(current_user.id)


# ============================================================
# TASKS ENDPOINTS
# ============================================================

@app.get(f"{settings.API_V1_PREFIX}/tasks")
def list_tasks(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.id).all()
    return [
        {
            "id": task.id,
            "skill_id": task.skill_id,
            "title": task.title,
            "description": task.description,
            "difficulty": task.difficulty,
            "starter_code": task.starter_code,
            "estimated_time_minutes": task.estimated_time_minutes,
        }
        for task in tasks
    ]


@app.get(f"{settings.API_V1_PREFIX}/tasks/{{task_id}}")
def get_task(task_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": task.id,
        "skill_id": task.skill_id,
        "title": task.title,
        "description": task.description,
        "difficulty": task.difficulty,
        "starter_code": task.starter_code,
        "estimated_time_minutes": task.estimated_time_minutes
    }


@app.post(f"{settings.API_V1_PREFIX}/tasks/submit")
def submit_task(task_id: int, code: str, struggle_time_seconds: int = 0, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    engine = ScaffoldEngine(llm_provider="openai", model=settings.LLM_MODEL, api_key=settings.OPENAI_API_KEY)

    attempts = db.query(Submission).filter(Submission.user_id == current_user.id, Submission.task_id == task_id).all()
    last_edit = db.query(Submission.created_at).filter(Submission.user_id == current_user.id, Submission.task_id == task_id).order_by(Submission.created_at.desc()).first()
    hints_used = sum(s.hints_used for s in attempts)

    struggle_history = {
        "attempts": [{"error_category": s.error_category for s in attempts}],
        "last_edit_time": last_edit[0] if last_edit else None,
        "hints_used": hints_used,
        "delete_count": 0
    }

    cognitive = engine.analyze_attempt(code, task.description, task.expected_solution, struggle_history)

    grade = grade_submission(code, task.test_cases)
    passed = grade["passed"]
    score = max(float(cognitive.attempt_quality), (grade["passed_count"] / grade["total"]) * 100.0 if grade["total"] else 0.0)
    if passed:
        score = max(score, 85.0)

    submission = Submission(
        user_id=current_user.id,
        task_id=task_id,
        code=code,
        passed=passed,
        score=score,
        error_category=cognitive.error_category,
        attempt_number=len(attempts) + 1,
        struggle_time_seconds=struggle_time_seconds,
        execution_result=str(grade) if not passed else "ok",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    kg = KnowledgeGraph(db)
    mastery = db.query(UserSkillMastery).filter(
        UserSkillMastery.user_id == current_user.id, UserSkillMastery.skill_id == task.skill_id
    ).first()
    if not mastery:
        mastery = UserSkillMastery(user_id=current_user.id, skill_id=task.skill_id)
        db.add(mastery)
        db.commit()

    new_mastery = engine.update_mastery(
        mastery.mastery_level,
        {"passed": passed, "score": score}
    )
    mastery.mastery_level = new_mastery
    mastery.last_practiced = datetime.utcnow()
    mastery.attempts_count += 1
    mastery.success_rate = (mastery.success_rate * (mastery.attempts_count - 1) + (1 if passed else 0)) / mastery.attempts_count
    db.commit()

    return {
        "submission_id": submission.id,
        "passed": passed,
        "score": score,
        "cognitive_state": cognitive.to_dict(),
        "mastery_level": new_mastery
    }


# ============================================================
# HINTS ENDPOINTS
# ============================================================

@app.get(f"{settings.API_V1_PREFIX}/hints/next")
def get_next_hint(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    submission = db.query(Submission).filter(Submission.id == submission_id, Submission.user_id == current_user.id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    task = db.query(Task).filter(Task.id == submission.task_id).first()

    engine = ScaffoldEngine(llm_provider="openai", model=settings.LLM_MODEL, api_key=settings.OPENAI_API_KEY)

    cognitive = engine.analyze_attempt(
        submission.code, task.description, task.expected_solution,
        {"attempts": [], "hints_used": submission.hints_used}
    )

    hint = engine.generate_hint(
        cognitive.to_dict(),
        {
            "hints_used": submission.hints_used,
            "task_type": "coding",
            "domain": "python_basics",
            "previous_hints": []
        }
    )

    session = ScaffoldSession(
        user_id=current_user.id,
        submission_id=submission.id,
        cognitive_state=cognitive.to_dict(),
        hints_provided=[hint],
        hint_intensities=[hint.get("intensity", 0.5)]
    )
    db.add(session)
    db.commit()

    submission.hints_used += 1
    db.commit()

    return hint


@app.post(f"{settings.API_V1_PREFIX}/hints/feedback")
def rate_hint(submission_id: int, rating: int, helpful: bool, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    submission = db.query(Submission).filter(Submission.id == submission_id, Submission.user_id == current_user.id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    fb = HintFeedback(submission_id=submission_id, rating=rating, helpful=helpful)
    db.add(fb)
    db.commit()
    return {"message": "Feedback recorded", "rating": rating, "helpful": helpful}


@app.get(f"{settings.API_V1_PREFIX}/peer/match")
def get_reviewer_matches(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    engine_p = PeerPairingEngine(db)
    matches = engine_p.match_reviewers(submission_id, k=3)
    return {"submission_id": submission_id, "reviewers": matches}


# ============================================================
# PEER REVIEW ENDPOINTS
# ============================================================

@app.get(f"{settings.API_V1_PREFIX}/peer/to-review")
def get_review_queue(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reviewed = db.query(PeerReview).filter(PeerReview.reviewer_id == current_user.id).all()
    reviewed_ids = {r.submission_id for r in reviewed}

    q = db.query(Submission).filter(Submission.user_id != current_user.id)
    if reviewed_ids:
        q = q.filter(Submission.id.notin_(reviewed_ids))
    submissions = q.order_by(Submission.created_at.desc()).limit(5).all()

    result = []
    for s in submissions:
        task = db.query(Task).filter(Task.id == s.task_id).first()
        result.append({
            "submission_id": s.id,
            "username": s.user.username,
            "task_title": task.title if task else "Unknown",
            "code": s.code,
            "score": s.score,
            "created_at": s.created_at.isoformat()
        })
    return result


@app.post(f"{settings.API_V1_PREFIX}/peer/review")
def submit_peer_review(submission_id: int, feedback: str, coverage_score: int, actionability_score: int, tone_score: int, helpful: bool, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot review your own submission")

    existing = db.query(PeerReview).filter(
        PeerReview.submission_id == submission_id,
        PeerReview.reviewer_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already reviewed this submission")

    total = round((coverage_score + actionability_score + tone_score) / 3)
    review = PeerReview(
        submission_id=submission_id,
        reviewer_id=current_user.id,
        feedback=feedback,
        coverage_score=coverage_score,
        actionability_score=actionability_score,
        tone_score=tone_score,
        total_score=total,
        is_helpful=helpful
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return {
        "review_id": review.id,
        "total_score": total,
        "message": "Review submitted successfully"
    }


# ============================================================
# ANALYTICS ENDPOINTS
# ============================================================

@app.get(f"{settings.API_V1_PREFIX}/analytics/progress")
def get_progress(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mastery = db.query(UserSkillMastery).filter(UserSkillMastery.user_id == current_user.id).all()
    submissions = db.query(Submission).filter(Submission.user_id == current_user.id).all()

    return {
        "total_submissions": len(submissions),
        "passed_submissions": sum(1 for s in submissions if s.passed),
        "skills_in_progress": len(mastery),
        "mastery_by_skill": [
            {
                "skill_id": m.skill_id,
                "mastery_level": m.mastery_level,
                "success_rate": m.success_rate,
                "attempts": m.attempts_count
            } for m in mastery
        ]
    }


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    def connect(self, websocket: WebSocket):
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)


manager = ConnectionManager()


@app.websocket("/ws/scaffold")
async def websocket_scaffold(websocket: WebSocket):
    await websocket.accept()
    manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await websocket.send_json({"response": "Received", "echo": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get(f"{settings.API_V1_PREFIX}/analytics/scaffold")
def scaffold_metrics(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.query(ScaffoldSession).filter(ScaffoldSession.user_id == current_user.id).all()
    total = len(sessions)
    avg_intensity = 0.0
    if total:
        vals = []
        for s in sessions:
            vals += s.hint_intensities or []
        avg_intensity = sum(vals) / len(vals) if vals else 0.0
    return {"sessions": total, "avg_hint_intensity": round(avg_intensity, 3)}