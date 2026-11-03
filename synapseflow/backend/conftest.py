import os
import tempfile

# Default to an isolated SQLite database for tests unless explicitly overridden.
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.gettempdir(), "synapseflow_test.db"))
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("SANDBOX_TIMEOUT_SECONDS", "5")