from fastapi.templating import Jinja2Templates

from config import BASE_DIR
from services import nombre_usuario, url_whatsapp_cliente

templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.filters["soles"] = lambda valor: f"S/ {valor:.2f}"
templates.env.globals["nombre_usuario"] = nombre_usuario
templates.env.globals["url_whatsapp_cliente"] = url_whatsapp_cliente