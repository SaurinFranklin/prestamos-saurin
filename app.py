from fastapi import FastAPI, Form, Request, Response, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature
import urllib.parse

app = FastAPI()

# Clave secreta para firmar las cookies de sesión
SECRET_KEY = "saurin_secret_key_super_segura"
serializer = URLSafeTimedSerializer(SECRET_KEY)

# Usuarios del sistema (Puedes agregar más cobradores aquí)
USUARIOS = {
    "Saurin": {"password": "saurin1903", "rol": "admin", "nombre": "Administrador"},
    "juan": {"password": "juan123", "rol": "cobrador", "nombre": "Juan Cobrador"},
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
        "saldo": 320.0,
        "modalidad": "Diario",
        "estado": "Cliente Puntual",
        "cobrador_asignado": "juan",
        "pagos": [
            {"fecha": "2026-08-18", "monto": 25.0, "registrado_por": "juan"}
        ]
    },
    {
        "id": "PRES-102",
        "deudor": "Marufith",
        "moneda": "Soles (S/)",
        "monto": 1000.0,
        "interes": 10.0,
        "total": 1100.0,
        "saldo": 100.0,
        "modalidad": "Diario",
        "estado": "Cliente Puntual",
        "cobrador_asignado": "pedro",
        "pagos": [
            {"fecha": "2026-08-18", "monto": 1000.0, "registrado_por": "pedro"}
        ]
    }
]

def obtener_usuario_actual(request: Request):
    session_token = request.cookies.get("session")
    if not session_token:
        return None
    try:
        username = serializer.loads(session_token, salt="session-cookie", max_age=86400)
        return USUARIOS.get(username)
    except BadSignature:
        return None

def login_required(request: Request):
    user = obtener_usuario_actual(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )
    return user

def render_login(error=""):
    error_html = f'<div class="alert alert-danger py-2 small">{error}</div>' if error else ""
    return f"""
    <!DOCTYPE html>
    <html lang="es" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login - Préstamos Saurin</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #0b0f19; display: flex; align-items: center; justify-content: center; height: 100vh; }}
            .card-login {{ width: 100%; max-width: 380px; }}
        </style>
    </head>
    <body>
        <div class="card card-login bg-dark text-white border-secondary shadow-lg p-4 rounded">
            <h3 class="text-center text-info fw-bold mb-3">💼 Préstamos Saurin</h3>
            <p class="text-center text-muted small mb-4">Ingresa tus credenciales para acceder</p>
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

def obtener_html_panel(user: dict, mensaje: str = "", ultimo_pago: dict = None):
    es_admin = user["rol"] == "admin"
    username_actual = [u for u, datos in USUARIOS.items() if datos == user][0]

    # Filtrar préstamos
    if es_admin:
        prestamos_visibles = prestamos
    else:
        prestamos_visibles = [p for p in prestamos if p.get("cobrador_asignado") == username_actual]

    cards_html = ""
    for p in prestamos_visibles:
        historial_html = "".join([
            f"<li class='list-group-item d-flex justify-content-between align-items-center bg-dark text-white border-secondary small py-1'>"
            f"<span>📅 {p_item['fecha']} ({p_item.get('registrado_por', 'sistema')})</span>"
            f"<span class='badge bg-success'>S/ {p_item['monto']:.2f}</span>"
            f"</li>"
            for p_item in p["pagos"]
        ]) if p["pagos"] else "<li class='list-group-item bg-dark text-muted border-secondary small py-1'>Sin abonos registrados</li>"

        if p["saldo"] <= 0:
            badge_color = "bg-primary"
            estado_texto = "PAID - Cancelado"
            seccion_abono = """
            <div class='p-2 rounded bg-success bg-opacity-10 border border-success mt-2 text-center'>
                <span class='text-success fw-bold small'>✅ Préstamo Pagado Totalmente</span>
            </div>
            """
        else:
            badge_color = "bg-success" if p["estado"] == "Cliente Puntual" else "bg-warning text-dark" if p["estado"] == "En Seguimiento" else "bg-danger"
            estado_texto = p["estado"]
            seccion_abono = f"""
            <form action='/abonar' method='post' class='p-2 rounded bg-black bg-opacity-50 border border-secondary mt-2'>
                <input type='hidden' name='p_id' value='{p["id"]}'>
                <label class='form-label extra-small text-info fw-bold mb-1'>Registrar Nuevo Abono:</label>
                <div class='input-group input-group-sm'>
                    <span class='input-group-text bg-secondary text-white border-secondary'>S/</span>
                    <input type='number' step='0.01' max='{p["saldo"]}' name='monto_abono' class='form-control bg-dark text-white border-secondary' placeholder='Monto' required>
                    <button class='btn btn-success fw-bold' type='submit'>💰 Cobrar</button>
                </div>
            </form>
            """

        boton_eliminar = f"""
        <div class='card-footer border-secondary bg-black bg-opacity-25 py-2'>
            <form action='/eliminar' method='post' onsubmit='return confirm("¿Eliminar préstamo?");' class='m-0 w-100'>
                <input type='hidden' name='p_id' value='{p["id"]}'>
                <button type='submit' class='btn btn-outline-danger btn-sm w-100 py-1'>🗑️ Eliminar Préstamo</button>
            </form>
        </div>
        """ if es_admin else ""

        cobrador_nombre = USUARIOS.get(p.get("cobrador_asignado"), {}).get("nombre", "No Asignado")

        cards_html += f"""
        <div class='col-md-6 mb-4 item-prestamo' data-nombre='{p["deudor"].lower()}'>
            <div class='card bg-dark text-white border-secondary shadow-lg h-100'>
                <div class='card-header d-flex justify-content-between align-items-center border-secondary bg-black bg-opacity-25 py-2'>
                    <div>
                        <h5 class='m-0 text-info font-monospace fs-6'>#{p["id"]} — {p["deudor"]}</h5>
                        <small class='text-muted extra-small'>Cobrador: <b>{cobrador_nombre}</b></small>
                    </div>
                    <span class='badge {badge_color}'>{estado_texto}</span>
                </div>
                <div class='card-body py-3'>
                    <div class='row mb-2 text-center g-1'>
                        <div class='col-4 border-end border-secondary'>
                            <small class='text-muted d-block extra-small'>Prestado</small>
                            <strong class='small text-light'>S/ {p["monto"]:.2f}</strong>
                        </div>
                        <div class='col-4 border-end border-secondary'>
                            <small class='text-muted d-block extra-small'>Total (+Int)</small>
                            <strong class='small text-info'>S/ {p["total"]:.2f}</strong>
                        </div>
                        <div class='col-4'>
                            <small class='text-muted d-block extra-small'>Saldo Restante</small>
                            <strong class='small {"text-success" if p["saldo"] <= 0 else "text-danger"}'>S/ {p["saldo"]:.2f}</strong>
                        </div>
                    </div>
                    
                    <p class='mb-2 small text-center'><span class='text-muted'>Modalidad:</span> <strong>{p["modalidad"]}</strong> | <span class='text-muted'>Interés:</span> <strong>{p["interes"]}%</strong></p>

                    <button class='btn btn-outline-info btn-sm w-100 mb-2 py-1' type='button' data-bs-toggle='collapse' data-bs-target='#historial-{p["id"]}'>
                        📋 Ver Historial ({len(p["pagos"])})
                    </button>
                    
                    <div class='collapse mb-2' id='historial-{p["id"]}'>
                        <ul class='list-group list-group-flush rounded'>
                            {historial_html}
                        </ul>
                    </div>

                    {seccion_abono}
                </div>
                {boton_eliminar}
            </div>
        </div>
        """

    cobradores_options = "".join([
        f'<option value="{u}">{d["nombre"]}</option>'
        for u, d in USUARIOS.items() if d["rol"] == "cobrador"
    ])

    formulario_nuevo = f"""
    <div class="col-lg-4 mb-4">
        <div class="card bg-dark text-white border-info shadow">
            <div class="card-header bg-info bg-opacity-10 border-info py-2">
                <h5 class="m-0 text-info fs-6">+ Nuevo Préstamo</h5>
            </div>
            <div class="card-body">
                <form action="/crear" method="post">
                    <div class="mb-2">
                        <label class="form-label small mb-1">Asignar Cobrador</label>
                        <select name="cobrador_asignado" class="form-select form-select-sm bg-dark text-white border-secondary" required>
                            {cobradores_options}
                        </select>
                    </div>
                    <div class="mb-2">
                        <label class="form-label small mb-1">Nombre del Deudor</label>
                        <input type="text" name="deudor" class="form-control form-control-sm bg-dark text-white border-secondary" placeholder="Ej. Juan Pérez" required>
                    </div>
                    <div class="mb-2">
                        <label class="form-label small mb-1">Moneda</label>
                        <select name="moneda" class="form-select form-select-sm bg-dark text-white border-secondary">
                            <option value="Soles (S/)">Soles (S/)</option>
                            <option value="Dólares ($)">Dólares ($)</option>
                        </select>
                    </div>
                    <div class="mb-2">
                        <label class="form-label small mb-1">Monto Prestado</label>
                        <input type="number" step="0.01" name="monto" class="form-control form-control-sm bg-dark text-white border-secondary" required>
                    </div>
                    <div class="row mb-2">
                        <div class="col-6">
                            <label class="form-label small mb-1">Modalidad</label>
                            <select name="modalidad" class="form-select form-select-sm bg-dark text-white border-secondary">
                                <option value="Diario">Diario</option>
                                <option value="Semanal">Semanal</option>
                                <option value="Quincenal">Quincenal</option>
                                <option value="Mensual">Mensual</option>
                            </select>
                        </div>
                        <div class="col-6">
                            <label class="form-label small mb-1">Interés (%)</label>
                            <input type="number" step="0.1" name="interes" value="10" class="form-control form-control-sm bg-dark text-white border-secondary" required>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label small mb-1">Estado Inicial</label>
                        <select name="estado" class="form-select form-select-sm bg-dark text-white border-secondary">
                            <option value="Cliente Puntual">Cliente Puntual</option>
                            <option value="En Seguimiento">En Seguimiento</option>
                            <option value="En Mora">En Mora</option>
                        </select>
                    </div>
                    <button type="submit" class="btn btn-info btn-sm w-100 fw-bold">Crear Préstamo</button>
                </form>
            </div>
        </div>
    </div>
    """ if es_admin else ""

    alerta_html = ""
    if mensaje and ultimo_pago:
        msg_wsp = (
            f"🧾 *COMPROBANTE DE PAGO - PRESTAMOS SAURIN*\n"
            f"👤 Cliente: {ultimo_pago['deudor']}\n"
            f"💵 Abono: S/ {ultimo_pago['monto']:.2f}\n"
            f"📊 Saldo Restante: S/ {ultimo_pago['saldo']:.2f}\n"
            f"📅 Fecha: 2026-08-18\n"
            f"¡Gracias por su pago!"
        )
        msg_encoded = urllib.parse.quote(msg_wsp)

        monto_prestado = ultimo_pago.get('monto_prestado', 0.0)
        interes_pct = ultimo_pago.get('interes', 0.0)
        monto_interes = monto_prestado * (interes_pct / 100.0)
        monto_total = ultimo_pago.get('total', 0.0)

        alerta_html = f"""
        <div class="alert alert-success alert-dismissible fade show p-3 mb-4 shadow bg-dark text-white border-success position-relative" role="alert" id="comprobante-alerta">
            <div class="d-flex flex-wrap justify-content-between align-items-center gap-3 pe-5 d-print-none">
                <div>
                    <strong class="text-success fs-6">✅ {mensaje}</strong><br>
                    <span class="text-light small">Cliente: <b class="text-white">{ultimo_pago['deudor']}</b> | Saldo Restante: <b class="text-warning">S/ {ultimo_pago['saldo']:.2f}</b></span>
                </div>
                <div class="d-flex gap-2">
                    <a href="https://api.whatsapp.com/send?text={msg_encoded}" target="_blank" class="btn btn-sm btn-success fw-bold">
                        📲 Enviar WhatsApp
                    </a>
                    <button onclick="window.print()" class="btn btn-sm btn-outline-light fw-bold">
                        🖨️ PDF / Imprimir
                    </button>
                </div>
            </div>
            <button type="button" class="btn-close btn-close-white d-print-none ms-2" data-bs-dismiss="alert" aria-label="Close"></button>

            <!-- Boleta de Impresión en PDF -->
            <div class="d-none d-print-block p-4 text-black">
                <h4 class="text-center fw-bold mb-1">🧾 BOLETA DE COMPROBANTE DE PAGO</h4>
                <div class="text-center small mb-3"><strong>Empresa:</strong> Préstamos Saurin</div>
                <hr class="my-2 border-dark">
                
                <div class="row small mb-2">
                    <div class="col-6"><strong>Código:</strong> {ultimo_pago.get('id', 'PRES-101')}</div>
                    <div class="col-6 text-end"><strong>Fecha:</strong> 2026-08-18</div>
                    <div class="col-6"><strong>Cliente:</strong> {ultimo_pago['deudor']}</div>
                    <div class="col-6 text-end"><strong>Modalidad:</strong> {ultimo_pago.get('modalidad', 'Diario')}</div>
                </div>

                <div class="p-2 border border-dark rounded bg-light small mb-3">
                    <div class="row text-center">
                        <div class="col-4">Monto Prestado: <strong>S/ {monto_prestado:.2f}</strong></div>
                        <div class="col-4">Interés ({interes_pct}%): <strong>S/ {monto_interes:.2f}</strong></div>
                        <div class="col-4">Total a Pagar: <strong>S/ {monto_total:.2f}</strong></div>
                    </div>
                </div>

                <table class="table table-bordered table-sm my-2 border-dark">
                    <thead class="table-light border-dark">
                        <tr>
                            <th>Concepto</th>
                            <th class="text-end">Monto Cobrado</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Abono a Préstamo #{ultimo_pago.get('id', 'PRES-101')}</td>
                            <td class="text-end fw-bold">S/ {ultimo_pago['monto']:.2f}</td>
                        </tr>
                    </tbody>
                </table>
                
                <div class="text-end fw-bold fs-6 mt-2">
                    Saldo Restante: S/ {ultimo_pago['saldo']:.2f}
                </div>
            </div>
        </div>
        """
    elif mensaje:
        alerta_html = f'<div class="alert alert-warning alert-dismissible fade show small py-2 d-print-none" role="alert">{mensaje}<button type="button" class="btn-close d-print-none" data-bs-dismiss="alert"></button></div>'

    col_size = "col-lg-8" if es_admin else "col-lg-12"

    return f"""
    <!DOCTYPE html>
    <html lang="es" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Préstamos Saurin</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #0b0f19; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
            .card {{ transition: transform 0.2s; }}
            .card:hover {{ transform: translateY(-2px); }}
            .extra-small {{ font-size: 0.75rem; }}
            
            @media print {{
                @page {{ margin: 1cm; }}
                body {{ background-color: #ffffff !important; color: #000000 !important; }}
                .d-print-none {{ display: none !important; }}
                .d-print-block {{ display: block !important; }}
                #comprobante-alerta {{
                    background-color: #ffffff !important;
                    color: #000000 !important;
                    border: 2px solid #000000 !important;
                    box-shadow: none !important;
                    padding: 0 !important;
                }}
            }}
        </style>
    </head>
    <body class="text-light">
        <div class="container py-4">
            <div class="d-flex justify-content-between align-items-center pb-3 mb-4 border-bottom border-secondary d-print-none">
                <h2 class="fw-bold text-info m-0 fs-4">💼 Préstamos Saurin</h2>
                <div class="d-flex align-items-center gap-3">
                    <span class="small text-muted">Usuario: <strong class="text-white">{user['nombre']}</strong> <span class="badge bg-info">{user['rol'].upper()}</span></span>
                    <a href="/logout" class="btn btn-sm btn-outline-danger">Cerrar Sesión</a>
                </div>
            </div>

            {alerta_html}

            <div class="row d-print-none">
                {formulario_nuevo}

                <div class="{col_size}" id="contenedor-prestamos">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h5 class="m-0 text-white">Lista de Préstamos Asignados</h5>
                        <input type="text" id="buscador" class="form-control form-control-sm w-50 bg-dark text-white border-secondary" placeholder="🔍 Buscar cliente..." onkeyup="filtrarClientes()">
                    </div>

                    <div class="row">
                        {cards_html if cards_html else "<div class='text-muted p-3'>No tienes préstamos asignados.</div>"}
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            function filtrarClientes() {{
                const query = document.getElementById('buscador').value.toLowerCase();
                const items = document.querySelectorAll('.item-prestamo');
                items.forEach(item => {{
                    const nombre = item.getAttribute('data-nombre');
                    item.style.display = nombre.includes(query) ? 'block' : 'none';
                }});
            }}
        </script>
    </body>
    </html>
    """

# RUTAS DE AUTENTICACIÓN

@app.get("/login", response_class=HTMLResponse)
def login_page():
    return render_login()

@app.post("/login")
def login(response: Response, username: str = Form(...), password: str = Form(...)):
    user = USUARIOS.get(username)
    if not user or user["password"] != password:
        return HTMLResponse(content=render_login("Usuario o contraseña incorrectos"), status_code=400)
    
    token = serializer.dumps(username, salt="session-cookie")
    redirect_resp = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    redirect_resp.set_cookie(key="session", value=token, httponly=True, max_age=86400)
    return redirect_resp

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("session")
    return response

# RUTAS PRINCIPALES DE LA APLICACIÓN

@app.get("/", response_class=HTMLResponse)
def inicio(request: Request, user: dict = Depends(login_required)):
    return obtener_html_panel(user)

@app.post("/crear", response_class=HTMLResponse)
def crear_prestamo(request: Request, deudor: str = Form(...), moneda: str = Form(...), monto: float = Form(...), modalidad: str = Form(...), interes: float = Form(...), estado: str = Form(...), cobrador_asignado: str = Form(...), user: dict = Depends(login_required)):
    if user["rol"] != "admin":
        return obtener_html_panel(user, "⚠️ Solo el Administrador puede crear préstamos.")

    total = monto + (monto * (interes / 100))
    nuevo_id = f"PRES-{100 + len(prestamos) + 1}"
    prestamos.append({
        "id": nuevo_id,
        "deudor": deudor,
        "moneda": moneda,
        "monto": monto,
        "interes": interes,
        "total": total,
        "saldo": total,
        "modalidad": modalidad,
        "estado": estado,
        "cobrador_asignado": cobrador_asignado,
        "pagos": []
    })
    return obtener_html_panel(user, f"Préstamo registrado para <strong>{deudor}</strong> asignado a <strong>{USUARIOS.get(cobrador_asignado, {}).get('nombre')}</strong>.")

@app.post("/abonar", response_class=HTMLResponse)
def abonar_prestamo(request: Request, p_id: str = Form(...), monto_abono: float = Form(...), user: dict = Depends(login_required)):
    username_actual = [u for u, datos in USUARIOS.items() if datos == user][0]

    for p in prestamos:
        if p["id"] == p_id:
            if user["rol"] != "admin" and p.get("cobrador_asignado") != username_actual:
                return obtener_html_panel(user, "⚠️ No tienes permiso para abonar a este préstamo.")

            if p["saldo"] <= 0:
                return obtener_html_panel(user, "⚠️ Este préstamo ya fue cancelado completamente.")
            
            monto_real = min(monto_abono, p["saldo"])
            p["saldo"] = max(0.0, p["saldo"] - monto_real)
            p["pagos"].append({"fecha": "2026-08-18", "monto": monto_real, "registrado_por": username_actual})
            
            info_pago = {
                "id": p["id"],
                "deudor": p["deudor"],
                "monto": monto_real,
                "saldo": p["saldo"],
                "modalidad": p["modalidad"],
                "monto_prestado": p["monto"],
                "interes": p["interes"],
                "total": p["total"]
            }
            return obtener_html_panel(user, f"Abono de S/ {monto_real:.2f} registrado por {user['nombre']}.", ultimo_pago=info_pago)
    return obtener_html_panel(user, "Error al registrar abono.")

@app.post("/eliminar", response_class=HTMLResponse)
def eliminar_prestamo(request: Request, p_id: str = Form(...), user: dict = Depends(login_required)):
    if user["rol"] != "admin":
        return obtener_html_panel(user, "⚠️ Acceso denegado: Solo el Administrador puede eliminar.")

    global prestamos
    prestamos = [p for p in prestamos if p["id"] != p_id]
    return obtener_html_panel(user, "Préstamo eliminado por el Administrador.")
