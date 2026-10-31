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
