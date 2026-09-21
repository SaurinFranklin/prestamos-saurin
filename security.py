"""Autenticación, sesión y permisos."""
import hmac

from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from config import SECRET_KEY, SESSION_MAX_AGE, USUARIOS

serializer = URLSafeTimedSerializer(SECRET_KEY)


class NoAutenticado(Exception):
    """Se lanza cuando no hay sesión válida; main.py redirige a /login."""


def verificar_credenciales(username: str, password: str) -> dict | None:
    datos = USUARIOS.get(username)
    if datos and hmac.compare_digest(datos["password"].encode(), password.encode()):
        return datos
    return None


def crear_token(username: str, datos: dict) -> str:
    return serializer.dumps(
        {"username": username, "rol": datos["rol"], "nombre": datos["nombre"]}
    )


def obtener_usuario_actual(request: Request) -> dict | None:
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        return serializer.loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None


# --- Dependencias de FastAPI ------------------------------------------
def requiere_usuario(request: Request) -> dict:
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise NoAutenticado()
    return usuario


def requiere_admin(usuario: dict = Depends(requiere_usuario)) -> dict:
    if usuario["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return usuario
