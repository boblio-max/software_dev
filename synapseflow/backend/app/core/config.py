from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "SynapseFlow"

    # Database (defaults to local SQLite so the app runs without Postgres)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./synapseflow.db")

    # AI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

    # Vector DB
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_ENV: str = os.getenv("PINECONE_ENV", "us-east-1")
    PINECONE_INDEX: str = os.getenv("PINECONE_INDEX", "synapseflow-struggles")

    # Auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # CORS
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001")

    # Feature Flags
    ENABLE_PEER_REVIEW: bool = True
    ENABLE_LANGGRAPH_SCAFFOLD: bool = True
    ENABLE_REALTIME: bool = True

    # Scaffold Configuration
    MAX_HINT_INTENSITY: float = 1.0
    MIN_HINT_INTENSITY: float = 0.0
    FRUSTRATION_THRESHOLD: int = 70
    MASTERY_DECAY_DAYS: int = 7

    # Sandbox
    SANDBOX_TIMEOUT_SECONDS: int = int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "5"))

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()