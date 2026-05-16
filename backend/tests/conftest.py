import os
import sys
from pathlib import Path

# Set required env vars before any app imports
os.environ.setdefault("GITHUB_TOKEN", "test_github_token")
os.environ.setdefault("GITHUB_CLIENT_ID", "test_client_id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("SECRET_KEY", "test_secret_key_not_default")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test_issuecompass")

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
