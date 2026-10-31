"""Configuration centrale de FOOTBALL INTELLIGENCE PRO.

Les secrets (clés API) sont lus depuis le fichier .env, jamais écrits dans le code.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Dossier racine du projet (fonctionne aussi dans l'exécutable PyInstaller)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

APP_NAME = "FOOTBALL INTELLIGENCE PRO"
APP_VERSION = "0.1.0"

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "football_intelligence.db"

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
API_FOOTBALL_BASE_URL = os.getenv("API_FOOTBALL_BASE_URL", "https://v3.football.api-sports.io")
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "6"))
REQUEST_TIMEOUT_SECONDS = 15


def mask_key(key: str) -> str:
    """Affiche une clé sans la révéler en entier (ex. 'abcd…wxyz')."""
    if not key:
        return "absente"
    if len(key) <= 8:
        return "••••"
    return f"{key[:4]}…{key[-4:]}"


def write_env_value(name: str, value: str, path: Path | None = None) -> None:
    """Écrit ou remplace une valeur dans le fichier .env (le crée à partir de .env.example si besoin)."""
    path = path or (BASE_DIR / ".env")
    if not path.exists():
        example = BASE_DIR / ".env.example"
        path.write_text(example.read_text(encoding="utf-8") if example.exists() else "", encoding="utf-8")
    lines = path.read_text(encoding="utf-8").splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == name:
            lines[i] = f"{name}={value}"
            found = True
    if not found:
        lines.append(f"{name}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
