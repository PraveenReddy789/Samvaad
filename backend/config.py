import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

POLICIES_DIR = DATA_DIR / "policies"
SOP_DIR = DATA_DIR / "sop"
PRODUCTS_DIR = DATA_DIR / "products"
CALLS_DIR = DATA_DIR / "calls"
CUSTOMERS_DIR = DATA_DIR / "customers"

# Storage paths
QDRANT_STORAGE_PATH = str(DATA_DIR / "qdrant_db")
SQLITE_DB_PATH = str(DATA_DIR / "collection_agent.db")

# Database Configuration (PostgreSQL with SQLite local auto-fallback)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{SQLITE_DB_PATH}")

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mistral")  # "mistral", "ollama", "huggingface"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "open-mistral-7b")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

# Embedding Configuration
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "auto")  # "bge-m3", "mistral", "auto"
MISTRAL_EMBED_MODEL = "mistral-embed"
BGE_M3_MODEL = "BAAI/bge-m3"

# Qdrant Configuration
QDRANT_COLLECTION = "recovery_knowledge"
QDRANT_HOST = os.getenv("QDRANT_HOST", None)
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# Voice / TTS Configuration
TTS_VOICE = os.getenv("TTS_VOICE", "en-IN-NeerjaNeural")  # High quality natural Indian English
TTS_AUDIO_DIR = str(DATA_DIR / "tts_cache")

# Server Configuration
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
