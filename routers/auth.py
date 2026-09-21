"""Rutas de login / logout."""
from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from config import SESSION_MAX_AGE
from security import crear_token, obtener_usuario_actual, verificar_credenciales
from templating import templates

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if obtener_usuario_actual(request):
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request, "login.html", {"error": ""})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    datos = verificar_credenciales(username, password)
    if not datos:
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "Usuario o contraseña incorrectos"}, status_code=400,
        )

    respuesta = RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    respuesta.set_cookie("session", crear_token(username, datos),
                         httponly=True, max_age=SESSION_MAX_AGE)
    return respuesta


@router.get("/logout")
def logout():
    respuesta = RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    respuesta.delete_cookie("session")
    return respuesta
