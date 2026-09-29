"""Autenticación, sesión, permisos y hashing de contraseñas."""
import hashlib
import hmac
import os

from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from config import SECRET_KEY, SESSION_MAX_AGE

ITERACIONES_PBKDF2 = 260_000
serializer = URLSafeTimedSerializer(SECRET_KEY)

CAMPOS_TOKEN = ("id", "username", "rol", "nombre")


class NoAutenticado(Exception):
    """Se lanza cuando no hay sesión válida; main.py redirige a /login."""


# --- Contraseñas (PBKDF2, sin dependencias extra) --------------------
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERACIONES_PBKDF2)
    return f"pbkdf2_sha256${ITERACIONES_PBKDF2}${salt.hex()}${dk.hex()}"


def verificar_password(password: str, almacenado: str) -> bool:
    try:
        _, iteraciones, salt_hex, hash_hex = almacenado.split("$")
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iteraciones)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


# --- Credenciales en base de datos ------------------------------------
def verificar_credenciales(db: Session, username: str, password: str) -> dict | None:
    from models import UsuarioDB

    usuario = db.query(UsuarioDB).filter(UsuarioDB.username == username).first()
    if usuario and verificar_password(password, usuario.password_hash):
        return {
            "id": usuario.id,
            "username": usuario.username,
            "rol": usuario.rol,
            "nombre": usuario.nombre,
        }
    return None


def crear_token(datos: dict) -> str:
    return serializer.dumps({campo: datos[campo] for campo in CAMPOS_TOKEN})


def obtener_usuario_actual(request: Request) -> dict | None:
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        datos = serializer.loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None
    if not all(campo in datos for campo in CAMPOS_TOKEN):
        return None  # sesión vieja (dict de config): fuerza re-login
    return datos


# --- Dependencias de FastAPI ------------------------------------------
def requiere_usuario(request: Request) -> dict:
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise NoAutenticado()
    return usuario


def requiere_admin(usuario: dict = Depends(requiere_usuario)) -> dict:
    if usuario["rol"] not in ("admin", "gerente"):
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return usuario


def requiere_supervisor(usuario: dict = Depends(requiere_usuario)) -> dict:
    if usuario["rol"] not in ("admin", "gerente", "supervisor"):
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return usuario
