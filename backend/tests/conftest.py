import os
import sys
from pathlib import Path

# Set required env vars before any app imports
os.environ["GITHUB_TOKEN"] = "test_github_token"
os.environ["GITHUB_CLIENT_ID"] = "test_client_id"
os.environ["GITHUB_CLIENT_SECRET"] = "test_client_secret"
os.environ["SECRET_KEY"] = "test_secret_key_not_default"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_issuecompass"
os.environ["AI_ENABLED"] = "false"
os.environ["GROQ_API_KEY"] = ""
os.environ["EMBEDDINGS_ENABLED"] = "false"
os.environ["JINA_API_KEY"] = ""

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
