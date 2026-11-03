from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    skill_mastery = relationship("UserSkillMastery", back_populates="user", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="user", cascade="all, delete-orphan")
    scaffold_sessions = relationship("ScaffoldSession", back_populates="user", cascade="all, delete-orphan")

class Skill(Base):
    __tablename__ = "skills"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text)
    domain = Column(String(100), index=True)
    difficulty_base = Column(Integer, default=50)
    mastery_threshold = Column(Integer, default=80)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    prerequisites = relationship("SkillPrerequisite", foreign_keys="SkillPrerequisite.skill_id", back_populates="skill")
    dependents = relationship("SkillPrerequisite", foreign_keys="SkillPrerequisite.prerequisite_id", back_populates="prerequisite")
    tasks = relationship("Task", back_populates="skill")
    mastery_records = relationship("UserSkillMastery", back_populates="skill")

class SkillPrerequisite(Base):
    __tablename__ = "skill_prerequisites"
    
    id = Column(Integer, primary_key=True, index=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False)
    prerequisite_id = Column(Integer, ForeignKey("skills.id"), nullable=False)
    weight = Column(Float, default=1.0)
    
    skill = relationship("Skill", foreign_keys=[skill_id], back_populates="prerequisites")
    prerequisite = relationship("Skill", foreign_keys=[prerequisite_id], back_populates="dependents")

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    difficulty = Column(Integer, default=50)
    expected_solution = Column(Text, nullable=False)
    solution_intent = Column(Text)
    starter_code = Column(Text)
    test_cases = Column(JSON)
    estimated_time_minutes = Column(Integer, default=15)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    skill = relationship("Skill", back_populates="tasks")
    submissions = relationship("Submission", back_populates="task")

class Submission(Base):
    __tablename__ = "submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    code = Column(Text, nullable=False)
    language = Column(String(50), default="python")
    passed = Column(Boolean, default=False)
    score = Column(Float, default=0.0)
    execution_result = Column(Text)
    error_category = Column(String(100))
    attempt_number = Column(Integer, default=1)
    struggle_time_seconds = Column(Integer, default=0)
    hints_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="submissions")
    task = relationship("Task", back_populates="submissions")
    scaffold_session = relationship("ScaffoldSession", back_populates="submission", cascade="all, delete-orphan", uselist=False)
    peer_reviews = relationship("PeerReview", back_populates="submission", cascade="all, delete-orphan")

class PeerReview(Base):
    __tablename__ = "peer_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    feedback = Column(Text, nullable=False)
    coverage_score = Column(Integer)
    actionability_score = Column(Integer)
    tone_score = Column(Integer)
    total_score = Column(Integer)
    is_helpful = Column(Boolean)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    submission = relationship("Submission", back_populates="peer_reviews")
    reviewer = relationship("User")

class ScaffoldSession(Base):
    __tablename__ = "scaffold_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    cognitive_state = Column(JSON)
    hints_provided = Column(JSON)
    hint_intensities = Column(JSON)
    final_mastery_delta = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    user = relationship("User", back_populates="scaffold_sessions")
    submission = relationship("Submission", back_populates="scaffold_session")

class UserSkillMastery(Base):
    __tablename__ = "user_skill_mastery"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False)
    mastery_level = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    last_practiced = Column(DateTime, default=datetime.utcnow)
    decay_rate = Column(Float, default=0.1)
    attempts_count = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="skill_mastery")
    skill = relationship("Skill", back_populates="mastery_records")
    
    def apply_decay(self):
        days_since = (datetime.utcnow() - self.last_practiced).days
        decay_factor = (self.decay_rate ** (days_since / 7))
        self.mastery_level = max(0.0, self.mastery_level * decay_factor)
        return self.mastery_level

class HintFeedback(Base):
    __tablename__ = "hint_feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    helpful = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    submission = relationship("Submission")
