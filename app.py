from fastapi import FastAPI, Form, Request, Response, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature
from datetime import date
import urllib.parse

app = FastAPI()

# Clave secreta para firmar las cookies de sesión
SECRET_KEY = "saurin_secret_key_super_segura"
serializer = URLSafeTimedSerializer(SECRET_KEY)

# Usuarios del sistema
USUARIOS = {
    "Saurin": {"password": "saurin1903", "rol": "admin", "nombre": "Administrador"},
    "Llovi": {"password": "yeray7410", "rol": "cobrador", "nombre": "Juan Cobrador"},
    "pedro": {"password": "pedro123", "rol": "cobrador", "nombre": "Pedro Cobrador"}
}

# Base de datos temporal
prestamos = [
    {
        "id": "PRES-101",
        "deudor": "Franklin",
        "moneda": "Soles (S/)",
        "monto": 300.0,
        "interes": 15.0,
        "total": 345.0,
        "saldo": 260.0,
        "modalidad": "Diario",
        "estado": "Cliente Puntual",
        "cobrador_asignado": "juan",
        "pagos": [
            {"fecha": "2026-08-18", "monto": 25.0, "registrado_por": "juan"},
            {"fecha": "2026-08-18", "monto": 25.0, "registrado_por": "Saurin"},
            {"fecha": "2026-08-18", "monto": 35.0, "registrado_por": "Saurin"}
        ]
    },
    {
        "id": "PRES-102",
        "deudor": "Mariela",
        "moneda": "Soles (S/)",
        "monto": 1000.0,
        "interes": 10.0,
        "total": 1100.0,
        "saldo": 1100.0,
        "modalidad": "Diario",
        "estado": "Cliente Puntual",
        "cobrador_asignado": "pedro",
        "pagos": []
    }
]

def obtener_usuario_actual(request: Request):
    session_token = request.cookies.get("session")
    if not session_token:
        return None
    try:
        user = serializer.loads(session_token, max_age=86400) # Sesión válida por 1 día
        return user
    except BadSignature:
        return None

def render_login_html(error: str = ""):
    error_html = f'<div class="alert alert-danger py-2 small">{error}</div>' if error else ""
    return f"""
    <!DOCTYPE html>
    <html lang="es" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login - Préstamos Saurin</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="text-light d-flex align-items-center justify-content-center" style="min-height: 100vh; background-color: #0f1115;">
        <div class="card bg-secondary text-white p-4 shadow-lg" style="width: 100%; max-width: 380px;">
            <h3 class="text-center text-info mb-3">📌 Préstamos Saurin</h3>
            <p class="text-center text-muted mb-4">Ingresa tus credenciales para acceder</p>
            {error_html}
            <form action="/login" method="post">
                <div class="mb-3">
                    <label class="form-label small">Usuario</label>
                    <input type="text" name="username" class="form-control bg-dark text-white border-secondary" required autofocus>
                </div>
                <div class="mb-4">
                    <label class="form-label small">Contraseña</label>
                    <input type="password" name="password" class="form-control bg-dark text-white border-secondary" required>
                </div>
                <button type="submit" class="btn btn-info w-100 fw-bold">Iniciar Sesión</button>
            </form>
        </div>
    </body>
    </html>
    """

def obtener_html_panel(user: dict, mensaje: str = "", ultimo_pago_dict: dict = None):
    es_admin = user["rol"] == "admin"
    usuario_actual = user["username"]
    
    # Filtrar préstamos
    if es_admin:
        prestamos_visibles = prestamos
    else:
        prestamos_visibles = [p for p in prestamos if p.get("cobrador_asignado") == usuario_actual]

    tarjetas = ""
    for p in prestamos_visibles:
        historial = ""
        for pago in reversed(p["pagos"]):
            historial += f"""
            <div class="d-flex justify-content-between align-items-center border-bottom border-secondary py-1 small">
                <span>📅 {pago['fecha']} ({pago.get('registrado_por', 'Sistem')})</span>
                <span class="badge bg-success">S/ {pago['monto']:.2f}</span>
            </div>
            """
        
        # Botón para eliminar (solo visible para admin)
        btn_eliminar = f"""
        <form action="/eliminar/{p['id']}" method="post" style="display:inline;" onsubmit="return confirm('¿Seguro que deseas eliminar este préstamo?');">
            <button type="submit" class="btn btn-sm btn-outline-danger">🗑️ Eliminar</button>
        </form>
        """ if es_admin else ""

        tarjetas += f"""
        <div class="col-md-6 mb-4">
            <div class="card bg-dark text-white shadow-sm border-secondary">
                <div class="card-header bg-dark d-flex justify-content-between align-items-center">
                    <h5 class="mb-0 text-info">#{p['id']} — {p['deudor']}</h5>
                    <div>
                        <span class="badge bg-success">{p['estado']}</span>
                        {btn_eliminar}
                    </div>
                </div>
                <div class="card-body">
                    <p class="small text-muted mb-2">Cobrador: <strong>{USUARIOS.get(p.get('cobrador_asignado'), {}).get('nombre', p.get('cobrador_asignado'))}</strong></p>
                    <div class="row text-center my-3">
                        <div class="col-4">
                            <small class="text-muted d-block">Prestado</small>
                            <strong>S/ {p['monto']:.2f}</strong>
                        </div>
                        <div class="col-4">
                            <small class="text-muted d-block">Total (+Int)</small>
                            <strong class="text-info">S/ {p['total']:.2f}</strong>
                        </div>
                        <div class="col-4">
                            <small class="text-muted d-block">Saldo Restante</small>
                            <strong class="text-danger">S/ {p['saldo']:.2f}</strong>
                        </div>
                    </div>
                    <p class="small text-center text-muted">Modalidad: <strong>{p['modalidad']}</strong> | Interés: <strong>{p['interes']}%</strong></p>
                    
                    <button class="btn btn-sm btn-outline-info w-100 mb-2" type="button" data-bs-toggle="collapse" data-bs-target="#historial-{p['id']}">
                        📋 Ver Historial ({len(p['pagos'])})
                    </button>
                    
                    <div class="collapse mb-3" id="historial-{p['id']}">
                        <div class="card card-body bg-dark border-secondary p-2">
                            {historial if historial else '<small class="text-muted text-center">Sin abonos registrados</small>'}
                        </div>
                    </div>

                    <form action="/pagar/{p['id']}" method="post" class="mt-3">
                        <label class="form-label small fw-bold text-info">Registrar Nuevo Abono:</label>
                        <div class="input-group">
                            <span class="input-group-text bg-dark text-white border-secondary">S/</span>
                            <input type="number" step="0.01" name="monto" class="form-control bg-dark text-white border-secondary" placeholder="Monto" required>
                            <button class="btn btn-success fw-bold" type="submit">💰 Cobrar</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
        """

    # Formulario para crear nuevos préstamos (Solo Admin)
    seccion_crear = ""
    if es_admin:
        cobradores_options = ""
        for k, v in USUARIOS.items():
            if v["rol"] == "cobrador":
                cobradores_options += f'<option value="{k}">{v["nombre"]}</option>'
        
        seccion_crear = f"""
        <div class="card bg-secondary text-white p-3 mb-4 shadow-sm">
            <h5 class="text-info mb-3">➕ Crear Nuevo Préstamo</h5>
            <form action="/crear" method="post" class="row g-3">
                <div class="col-md-3">
                    <input type="text" name="deudor" class="form-control bg-dark text-white border-secondary" placeholder="Nombre Deudor" required>
                </div>
                <div class="col-md-2">
                    <input type="number" step="0.01" name="monto" class="form-control bg-dark text-white border-secondary" placeholder="Monto (S/)" required>
                </div>
                <div class="col-md-2">
                    <input type="number" step="0.1" name="interes" class="form-control bg-dark text-white border-secondary" placeholder="Interés %" value="15" required>
                </div>
                <div class="col-md-2">
                    <select name="cobrador" class="form-select bg-dark text-white border-secondary" required>
                        {cobradores_options}
                    </select>
                </div>
                <div class="col-md-3">
                    <button type="submit" class="btn btn-info w-100 fw-bold">Guardar Préstamo</button>
                </div>
            </form>
        </div>
        """

    alerta_html = f'<div class="alert alert-success alert-dismissible fade show" role="alert">{mensaje}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>' if mensaje else ""

    return f"""
    <!DOCTYPE html>
    <html lang="es" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Préstamos Saurin</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-dark text-light">
        <nav class="navbar navbar-expand-lg navbar-dark bg-secondary shadow-sm mb-4">
            <div class="container">
                <a class="navbar-brand fw-bold text-info" href="/">📌 Préstamos Saurin</a>
                <div class="d-flex align-items-center gap-3">
                    <span class="small">Usuario: <strong>{user['nombre']}</strong> ({user['rol'].upper()})</span>
                    <a href="/logout" class="btn btn-sm btn-outline-light">Cerrar Sesión</a>
                </div>
            </div>
        </nav>

        <div class="container">
            {alerta_html}
            {seccion_crear}
            
            <h4 class="mb-3 text-light">Lista de Préstamos</h4>
            <div class="row">
                {tarjetas if tarjetas else '<div class="col-12"><div class="alert alert-warning">No tienes préstamos asignados.</div></div>'}
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """

@app.get("/", response_class=HTMLResponse)
def index(request: Request, msg: str = ""):
    user = obtener_usuario_actual(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return obtener_html_panel(user, mensaje=msg)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    user = obtener_usuario_actual(request)
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return render_login_html()

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    user_data = USUARIOS.get(username)
    if not user_data or user_data["password"] != password:
        return HTMLResponse(content=render_login_html("Usuario o contraseña incorrectos"), status_code=400)
    
    session_payload = {
        "username": username,
        "rol": user_data["rol"],
        "nombre": user_data["nombre"]
    }
    session_token = serializer.dumps(session_payload)
    
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="session", value=session_token, httponly=True, max_age=86400)
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("session")
    return response

@app.post("/pagar/{prestamo_id}")
def registrar_pago(prestamo_id: str, monto: float = Form(...), request: Request = None):
    user = obtener_usuario_actual(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    for p in prestamos:
        if p["id"] == prestamo_id:
            # Control de permisos para cobrador
            if user["rol"] != "admin" and p.get("cobrador_asignado") != user["username"]:
                raise HTTPException(status_code=403, detail="No tienes permiso para registrar pagos en este préstamo")
            
            p["saldo"] = max(0.0, p["saldo"] - monto)
            
            # FECHA AUTOMÁTICA DEL DÍA EN QUE SE REALIZA EL REGISTRO
            fecha_hoy = date.today().isoformat()
            
            p["pagos"].append({
                "fecha": fecha_hoy,
                "monto": monto,
                "registrado_por": user["username"]
            })
            break
            
    msg = urllib.parse.quote("Abono registrado exitosamente.")
    return RedirectResponse(url=f"/?msg={msg}", status_code=status.HTTP_302_FOUND)

@app.post("/crear")
def crear_prestamo(deudor: str = Form(...), monto: float = Form(...), interes: float = Form(...), cobrador: str = Form(...), request: Request = None):
    user = obtener_usuario_actual(request)
    if not user or user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado: solo Administradores pueden crear préstamos")
    
    nuevo_id = f"PRES-{101 + len(prestamos)}"
    total = monto + (monto * (interes / 100))
    
    nuevo = {
        "id": nuevo_id,
        "deudor": deudor,
        "moneda": "Soles (S/)",
        "monto": monto,
        "interes": interes,
        "total": total,
        "saldo": total,
        "modalidad": "Diario",
        "estado": "Cliente Puntual",
        "cobrador_asignado": cobrador,
        "pagos": []
    }
    prestamos.append(nuevo)
    
    msg = urllib.parse.quote("Nuevo préstamo registrado exitosamente.")
    return RedirectResponse(url=f"/?msg={msg}", status_code=status.HTTP_302_FOUND)

@app.post("/eliminar/{prestamo_id}")
def eliminar_prestamo(prestamo_id: str, request: Request = None):
    user = obtener_usuario_actual(request)
    if not user or user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado: solo Administradores pueden eliminar préstamos")
    
    global prestamos
    prestamos = [p for p in prestamos if p["id"] != prestamo_id]
    
    msg = urllib.parse.quote("Préstamo eliminado.")
    return RedirectResponse(url=f"/?msg={msg}", status_code=status.HTTP_302_FOUND)
