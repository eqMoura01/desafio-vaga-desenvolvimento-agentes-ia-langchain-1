import os
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PACKAGE_ROOT / ".env")

DEFAULT_DB_PATH = PACKAGE_ROOT.parent / "anexo_desafio_1.db"


def db_path() -> Path:
    raw = os.environ.get("DB_PATH", "").strip()
    if not raw:
        return DEFAULT_DB_PATH
    path = Path(raw)
    if path.is_absolute():
        return path
    return (PACKAGE_ROOT / path).resolve()


def model_name() -> str:
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def max_queries() -> int:
    raw = os.environ.get("MAX_QUERIES", "5").strip() or "5"
    return max(1, int(raw))
