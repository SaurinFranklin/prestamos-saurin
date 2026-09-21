"""Motor de plantillas Jinja2 (escapa el HTML automáticamente)."""
from fastapi.templating import Jinja2Templates

from config import BASE_DIR
from services import nombre_usuario

templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.filters["soles"] = lambda valor: f"S/ {valor:.2f}"
templates.env.globals["nombre_usuario"] = nombre_usuario
