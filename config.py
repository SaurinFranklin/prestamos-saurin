"""Configuración central de la aplicación."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# --- Base de datos ---------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- Sesión ----------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "geison_secret_key_super_segura")
SESSION_MAX_AGE = 86400  # 24 horas, en segundos

# --- Negocio ---------------------------------------------------------
MODALIDADES = ["Diario", "Semanal", "Quincenal", "Mensual"]
INTERES_POR_DEFECTO = 15
ID_INICIAL = 100  # el primer préstamo será PRES-101
