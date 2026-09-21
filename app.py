"""Punto de entrada:  uvicorn main:app --host 0.0.0.0 --port $PORT"""
from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from config import BASE_DIR
from database import init_db
from routers import auth, prestamos
from security import NoAutenticado

init_db()

app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.exception_handler(NoAutenticado)
async def redirigir_a_login(request: Request, exc: NoAutenticado):
    return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)


@app.head("/")
def health_check():
    """Usado por servicios de monitoreo / hosting."""
    return HTMLResponse(content="", status_code=200)


app.include_router(auth.router)
app.include_router(prestamos.router)
