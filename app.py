import os
import urllib.parse
from datetime import date
from fastapi import FastAPI, Form, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

# -------------------------------------------------------------------
# Configuración de Base de Datos PostgreSQL / SQLite
# -------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelos ORM
class PrestamoDB(Base):
    __tablename__ = "prestamos"

    id = Column(String, primary_key=True, index=True)
    deudor = Column(String, nullable=False)
    monto = Column(Float, nullable=False)
    interes = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    saldo = Column(Float, nullable=False)
    modalidad = Column(String, default="Diario")
    estado = Column(String, default="Puntual")
    cobrador_asignado = Column(String, nullable=False)

    pagos = relationship("PagoDB", back_populates="prestamo", cascade="all, delete-orphan")

class PagoDB(Base):
    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    prestamo_id = Column(String, ForeignKey("prestamos.id"))
    fecha = Column(String, nullable=False)
    monto = Column(Float, nullable=False)
    registrado_por = Column(String, nullable=False)

    prestamo = relationship("PrestamoDB", back_populates="pagos")

Base.metadata.create_all(bind=engine)

# Migración automática
with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE prestamos ADD COLUMN modalidad VARCHAR DEFAULT 'Diario';"))
        conn.commit()
    except Exception:
        pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------------------------------------------
# Configuración de App y Autenticación
# -------------------------------------------------------------------
app = FastAPI()

SECRET_KEY = "geison_secret_key_super_segura"
serializer = URLSafeTimedSerializer(SECRET_KEY)

USUARIOS = {
    "Geison": {"password": "xiomara789", "rol": "admin", "nombre": "Administrador"},
    "juan": {"password": "juan123", "rol": "cobrador", "nombre": "Juan Cobrador"},
    "pedro": {"password": "pedro123", "rol": "cobrador", "nombre": "Pedro Cobrador"}
}

def obtener_usuario_actual(request: Request):
    session_token = request.cookies.get("session")
    if not session_token:
        return None
    try:
        return serializer.loads(session_token, max_age=86400)
    except BadSignature:
        return None

# -------------------------------------------------------------------
# Vistas HTML
# -------------------------------------------------------------------
def render_login_html(error: str = ""):
    error_html = f'<div class="alert alert-danger py-2 small">{error}</div>' if error else ""
    return f"""
    <!DOCTYPE html>
    <html lang="es" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login - Préstamos Geison</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #050505 !important; }}
            .card-login {{ background-color: #121212 !important; border: 1px solid #222222 !important; }}
        </style>
    </head>
    <body class="text-light d-flex align-items-center justify-content-center" style="min-height: 100vh;">
        <div class="card card-login text-white p-4 shadow-lg rounded-3" style="width: 100%; max-width: 380px;">
            <h3 class="text-center text-info mb-3">📌 Préstamos Geison</h3>
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

def obtener_html_panel(user: dict, db: Session, mensaje: str = "", error_msg: str = ""):
    es_admin = user["rol"] == "admin"
    usuario_actual = user["username"]
    
    if es_admin:
        prestamos_visibles = db.query(PrestamoDB).all()
    else:
        prestamos_visibles = db.query(PrestamoDB).filter(PrestamoDB.cobrador_asignado == usuario_actual).all()

    tarjetas = ""
    for p in prestamos_visibles:
        historial = ""
        pagos_ordenados = sorted(p.pagos, key=lambda x: x.id, reverse=True)
        for pago in pagos_ordenados:
            historial += f"""
            <div class="d-flex justify-content-between align-items-center border-bottom border-secondary py-2 small">
                <div>
                    <div>📅 {pago.fecha}</div>
                    <small class="text-muted">Por: {pago.registrado_por}</small>
                </div>
                <div class="d-flex align-items-center gap-1">
                    <span class="badge bg-success">S/ {pago.monto:.2f}</span>
                    <a href="/comprobante/{pago.id}" target="_blank" class="btn btn-sm btn-outline-info py-0 px-1" title="Ver Comprobante">📄 Recibo</a>
                </div>
            </div>
            """
        
        btn_eliminar = f"""
        <form action="/eliminar/{p.id}" method="post" style="display:inline;" onsubmit="return confirm('¿Eliminar préstamo?');">
            <button type="submit" class="btn btn-sm btn-outline-danger">🗑️</button>
        </form>
        """ if es_admin else ""

        modalidad_texto = getattr(p, "modalidad", "Diario") or "Diario"
        nombre_cobrador = USUARIOS.get(p.cobrador_asignado, {}).get('nombre', p.cobrador_asignado)
        badge_estado = '<span class="badge bg-secondary">COMPLETADO</span>' if p.saldo <= 0 else f'<span class="badge bg-success">{p.estado}</span>'

        # Atributos data-search para filtrado rápido con JS
        search_data = f"{p.id} {p.deudor} {nombre_cobrador} {modalidad_texto}".lower()

        tarjetas += f"""
        <div class="col-md-6 mb-4 card-prestamo-item" data-search="{search_data}">
            <div class="card bg-black text-white shadow border border-secondary">
                <div class="card-header bg-dark d-flex justify-content-between align-items-center border-bottom border-secondary">
                    <div>
                        <h5 class="mb-0 text-info fw-bold">#{p.id} — {p.deudor}</h5>
                        <small class="badge bg-outline-secondary text-muted border border-secondary mt-1">🗓️ {modalidad_texto}</small>
                    </div>
                    <div>
                        {badge_estado}
                        {btn_eliminar}
                    </div>
                </div>
                <div class="card-body">
                    <p class="small text-muted mb-2">Cobrador: <strong>{nombre_cobrador}</strong></p>
                    <div class="row text-center my-3">
                        <div class="col-4">
                            <small class="text-muted d-block">Prestado</small>
                            <strong>S/ {p.monto:.2f}</strong>
                        </div>
                        <div class="col-4">
                            <small class="text-muted d-block">Total (+Int)</small>
                            <strong class="text-info">S/ {p.total:.2f}</strong>
                        </div>
                        <div class="col-4">
                            <small class="text-muted d-block">Saldo</small>
                            <strong class="{'text-success' if p.saldo <= 0 else 'text-danger'}">S/ {p.saldo:.2f}</strong>
                        </div>
                    </div>
                    
                    <button class="btn btn-sm btn-outline-info w-100 mb-2" type="button" data-bs-toggle="collapse" data-bs-target="#historial-{p.id}">
                        📋 Ver Historial ({len(p.pagos)})
                    </button>
                    
                    <div class="collapse mb-3" id="historial-{p.id}">
                        <div class="card card-body bg-dark border-secondary p-2">
                            {historial if historial else '<small class="text-muted text-center">Sin abonos</small>'}
                        </div>
                    </div>

                    {'<div class="alert alert-success py-1 my-0 text-center small fw-bold">✓ Préstamo Pagado Totalmente</div>' if p.saldo <= 0 else f'''
                    <form action="/pagar/{p.id}" method="post">
                        <div class="input-group">
                            <span class="input-group-text bg-dark text-white border-secondary">S/</span>
                            <input type="number" step="0.01" min="0.01" max="{p.saldo}" name="monto" class="form-control bg-dark text-white border-secondary" placeholder="Monto" required>
                            <button class="btn btn-success fw-bold" type="submit">💰 Cobrar</button>
                        </div>
                    </form>
                    '''}
                </div>
            </div>
        </div>
        """

    seccion_crear = ""
    if es_admin:
        cobradores_options = "".join([f'<option value="{k}">{v["nombre"]}</option>' for k, v in USUARIOS.items() if v["rol"] == "cobrador"])
        seccion_crear = f"""
        <div class="card bg-black text-white p-3 mb-4 shadow border border-secondary">
            <h5 class="text-info mb-3">➕ Crear Nuevo Préstamo</h5>
            <form action="/crear" method="post" class="row g-3">
                <div class="col-md-3">
                    <input type="text" name="deudor" class="form-control bg-dark text-white border-secondary" placeholder="Nombre Deudor" required>
                </div>
                <div class="col-md-2">
                    <input type="number" step="0.01" min="1" name="monto" class="form-control bg-dark text-white border-secondary" placeholder="Monto (S/)" required>
                </div>
                <div class="col-md-2">
                    <input type="number" step="0.1" min="0" name="interes" class="form-control bg-dark text-white border-secondary" placeholder="Interés %" value="15" required>
                </div>
                <div class="col-md-2">
                    <select name="modalidad" class="form-select bg-dark text-white border-secondary" required>
                        <option value="Diario" selected>Diario</option>
                        <option value="Semanal">Semanal</option>
                        <option value="Quincenal">Quincenal</option>
                        <option value="Mensual">Mensual</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <select name="cobrador" class="form-select bg-dark text-white border-secondary" required>
                        {cobradores_options}
                    </select>
                </div>
                <div class="col-md-1">
                    <button type="submit" class="btn btn-info w-100 fw-bold">Guardar</button>
                </div>
            </form>
        </div>
        """

    alerta = f'<div class="alert alert-success alert-dismissible fade show">{mensaje}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>' if mensaje else ""
    alerta_err = f'<div class="alert alert-danger alert-dismissible fade show">{error_msg}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>' if error_msg else ""

    return f"""
    <!DOCTYPE html>
    <html lang="es" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Préstamos Geison</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #050505 !important; }}
            .navbar {{ background-color: #000000 !important; border-bottom: 1px solid #222222 !important; }}
        </style>
    </head>
    <body class="text-light">
        <nav class="navbar navbar-expand-lg navbar-dark mb-4">
            <div class="container">
                <a class="navbar-brand fw-bold text-info" href="/">📌 Préstamos Geison</a>
                <div class="d-flex align-items-center gap-3">
                    <span class="small">Usuario: <strong>{user['nombre']}</strong> ({user['rol'].upper()})</span>
                    <a href="/logout" class="btn btn-sm btn-outline-light">Cerrar Sesión</a>
                </div>
            </div>
        </nav>
        <div class="container">
            {alerta}
            {alerta_err}
            {seccion_crear}
            
            <!-- BUSCADOR EN TIEMPO REAL -->
            <div class="row mb-4">
                <div class="col-12">
                    <div class="input-group">
                        <span class="input-group-text bg-black text-info border-secondary">🔍 Buscar</span>
                        <input type="text" id="inputBuscador" class="form-control bg-dark text-white border-secondary p-2" placeholder="Escribe nombre de cliente, código (#PRES-101) o cobrador...">
                    </div>
                </div>
            </div>

            <h4 class="mb-3 text-light">Lista de Préstamos</h4>
            <div class="row" id="contenedorPrestamos">
                {tarjetas if tarjetas else '<div class="col-12"><div class="alert alert-warning bg-dark border-warning text-warning">No hay préstamos asignados.</div></div>'}
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            // Filtrado dinámico sin recargar página
            document.getElementById('inputBuscador').addEventListener('keyup', function() {{
                const query = this.value.toLowerCase().trim();
                const items = document.querySelectorAll('.card-prestamo-item');
                
                items.forEach(item => {{
                    const text = item.getAttribute('data-search');
                    if (text.includes(query)) {{
                        item.style.display = 'block';
                    }} else {{
                        item.style.display = 'none';
                    }}
                }});
            }});
        </script>
    </body>
    </html>
    """

# -------------------------------------------------------------------
# Endpoints / Rutas
# -------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index(request: Request, msg: str = "", err: str = "", db: Session = Depends(get_db)):
    user = obtener_usuario_actual(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return obtener_html_panel(user, db, mensaje=msg, error_msg=err)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if obtener_usuario_actual(request):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return render_login_html()

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    user_data = USUARIOS.get(username)
    if not user_data or user_data["password"] != password:
        return HTMLResponse(content=render_login_html("Usuario o contraseña incorrectos"), status_code=400)
    
    session_payload = {"username": username, "rol": user_data["rol"], "nombre": user_data["nombre"]}
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
def registrar_pago(prestamo_id: str, monto: float = Form(...), request: Request = None, db: Session = Depends(get_db)):
    user = obtener_usuario_actual(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    prestamo = db.query(PrestamoDB).filter(PrestamoDB.id == prestamo_id).first()
    if not prestamo:
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")
        
    if user["rol"] != "admin" and prestamo.cobrador_asignado != user["username"]:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    # Validación: No permitir abonos menores o iguales a 0 o superiores al saldo restante
    if monto <= 0:
        return RedirectResponse(url=f"/?err={urllib.parse.quote('El monto debe ser mayor a cero.')}", status_code=status.HTTP_302_FOUND)
    if monto > prestamo.saldo:
        return RedirectResponse(url=f"/?err={urllib.parse.quote('El monto supera el saldo restante.')}", status_code=status.HTTP_302_FOUND)
    
    prestamo.saldo = max(0.0, prestamo.saldo - monto)
    nuevo_pago = PagoDB(prestamo_id=prestamo.id, fecha=date.today().isoformat(), monto=monto, registrado_por=user["username"])
    
    db.add(nuevo_pago)
    db.commit()
    db.refresh(nuevo_pago)
            
    return RedirectResponse(url=f"/comprobante/{nuevo_pago.id}", status_code=status.HTTP_302_FOUND)

@app.get("/comprobante/{pago_id}", response_class=HTMLResponse)
def ver_comprobante(pago_id: int, request: Request, db: Session = Depends(get_db)):
    user = obtener_usuario_actual(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        
    pago = db.query(PagoDB).filter(PagoDB.id == pago_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
        
    prestamo = pago.prestamo
    modalidad_texto = getattr(prestamo, "modalidad", "Diario") or "Diario"
    monto_interes = prestamo.monto * (prestamo.interes / 100.0)
    
    texto_wa = f"*BOLETA DE COMPROBANTE DE PAGO*\n" \
               f"Empresa: Préstamos Geison\n" \
               f"Código: {prestamo.id}\n" \
               f"Cliente: {prestamo.deudor}\n" \
               f"Monto Prestado: S/ {prestamo.monto:.2f}\n" \
               f"Interés ({prestamo.interes:.1f}%): S/ {monto_interes:.2f}\n" \
               f"Total a Pagar: S/ {prestamo.total:.2f}\n\n" \
               f"Fecha: {pago.fecha}\n" \
               f"Modalidad: {modalidad_texto}\n\n" \
               f"Concepto | Monto Cobrado\n" \
               f"Abono a Préstamo #{prestamo.id} | S/ {pago.monto:.2f}\n\n" \
               f"Saldo Restante: S/ {prestamo.saldo:.2f}"
               
    url_wa = f"https://api.whatsapp.com/send?text={urllib.parse.quote(texto_wa)}"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Recibo #{pago.id} - Préstamos Geison</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            /* ESTILOS EN PANTALLA (Ticket Oscuro) */
            body {{
                background-color: #0d0d0d;
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                padding: 20px;
            }}
            .ticket-pantalla {{
                background-color: #171717;
                border: 1px dashed #333333;
                border-radius: 16px;
                padding: 24px;
                width: 100%;
                max-width: 360px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            }}
            .ticket-header {{
                text-align: center;
                margin-bottom: 20px;
            }}
            .ticket-title {{
                color: #00d2ff;
                font-size: 20px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }}
            .ticket-subtitle {{
                color: #888;
                font-size: 13px;
                margin-top: 2px;
            }}
            .ticket-row {{
                display: flex;
                justify-content: space-between;
                font-size: 14px;
                margin-bottom: 8px;
                color: #ccc;
            }}
            .ticket-row strong {{
                color: #fff;
            }}
            .monto-destacado {{
                font-size: 18px;
                font-weight: bold;
                color: #2ed573;
            }}
            .saldo-destacado {{
                font-size: 18px;
                font-weight: bold;
                color: #ff4757;
            }}
            .btn-wa {{
                background-color: #059669;
                color: white;
                font-weight: 600;
                border: none;
            }}
            .btn-wa:hover {{
                background-color: #047857;
                color: white;
            }}
            .btn-pdf {{
                background-color: transparent;
                border: 1px solid #00d2ff;
                color: #00d2ff;
                font-weight: 600;
            }}
            .btn-pdf:hover {{
                background-color: #00d2ff;
                color: #000;
            }}

            .boleta-impresion {{
                display: none;
            }}

            /* ESTILOS EN IMPRESIÓN / PDF (Boleta Blanca Limpia) */
            @page {{
                margin: 10mm;
            }}
            @media print {{
                .ticket-pantalla {{
                    display: none !important;
                }}
                body {{
                    background-color: #fff !important;
                    color: #000 !important;
                    display: block !important;
                    padding: 0 !important;
                }}
                .boleta-impresion {{
                    display: block !important;
                    max-width: 650px;
                    margin: 0 auto;
                    background: #fff;
                    border: 2px solid #000;
                    border-radius: 12px;
                    padding: 24px;
                }}
                .boleta-header {{
                    text-align: center;
                    margin-bottom: 20px;
                }}
                .boleta-title {{
                    font-size: 22px;
                    font-weight: 800;
                    letter-spacing: 0.5px;
                }}
                .divider {{
                    border-top: 1px solid #ccc;
                    margin: 15px 0;
                }}
                .info-grid {{
                    display: flex;
                    justify-content: space-between;
                    font-size: 14px;
                    line-height: 1.6;
                }}
                .info-box {{
                    border: 1px solid #000;
                    border-radius: 8px;
                    padding: 12px;
                    margin: 15px 0;
                    display: flex;
                    justify-content: space-between;
                    text-align: center;
                    font-size: 13px;
                }}
                .info-box div {{
                    flex: 1;
                }}
                .info-box-val {{
                    font-weight: bold;
                    font-size: 15px;
                    margin-top: 4px;
                }}
                .tabla-concepto {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 15px 0;
                    border: 1px solid #000;
                }}
                .tabla-concepto th, .tabla-concepto td {{
                    border: 1px solid #000;
                    padding: 8px;
                    font-size: 14px;
                }}
                .saldo-line {{
                    text-align: right;
                    font-size: 16px;
                    font-weight: bold;
                    margin-top: 15px;
                }}
            }}
        </style>
    </head>
    <body>

        <!-- VISTA EN PANTALLA (Ticket Oscuro) -->
        <div class="ticket-pantalla">
            <div class="ticket-header">
                <div class="ticket-title">📌 PRÉSTAMOS GEISON</div>
                <div class="ticket-subtitle">Comprobante Oficial de Pago</div>
            </div>

            <div class="my-3">
                <div class="ticket-row"><span>N° Recibo:</span> <strong>#{pago.id}</strong></div>
                <div class="ticket-row"><span>Fecha:</span> <strong>{pago.fecha}</strong></div>
                <div class="ticket-row"><span>Cliente:</span> <strong>{prestamo.deudor}</strong></div>
                <div class="ticket-row"><span>Modalidad:</span> <strong>{modalidad_texto}</strong></div>
                <div class="ticket-row"><span>Cobrador:</span> <strong>{pago.registrado_por}</strong></div>
            </div>

            <hr style="border-color: #333;" class="my-3">

            <div class="ticket-row align-items-center">
                <span>Monto Abonado:</span>
                <span class="monto-destacado">S/ {pago.monto:.2f}</span>
            </div>
            <div class="ticket-row align-items-center">
                <span>Saldo Restante:</span>
                <span class="saldo-destacado">S/ {prestamo.saldo:.2f}</span>
            </div>

            <hr style="border-color: #333;" class="my-3">

            <p class="text-center text-muted small my-3">¡Gracias por su puntualidad!</p>

            <div class="d-grid gap-2">
                <a href="{url_wa}" target="_blank" class="btn btn-wa py-2">📱 Enviar por WhatsApp</a>
                <button onclick="window.print()" class="btn btn-pdf py-2">🖨️ Imprimir / Guardar PDF</button>
                <a href="/" class="btn btn-sm text-secondary text-center text-decoration-none mt-1">🔙 Volver al Panel</a>
            </div>
        </div>

        <!-- VISTA EXCLUSIVA PARA IMPRESIÓN / PDF (Boleta Blanca) -->
        <div class="boleta-impresion">
            <div class="boleta-header">
                <div class="boleta-title">
                    🧾 BOLETA DE COMPROBANTE DE PAGO
                </div>
                <div class="mt-1 fs-6">
                    <strong>Empresa:</strong> Préstamos Geison
                </div>
            </div>

            <div class="divider"></div>

            <div class="info-grid">
                <div>
                    <div><strong>Código:</strong> {prestamo.id}</div>
                    <div><strong>Cliente:</strong> {prestamo.deudor}</div>
                </div>
                <div class="text-end">
                    <div><strong>Fecha:</strong> {pago.fecha}</div>
                    <div><strong>Modalidad:</strong> {modalidad_texto}</div>
                </div>
            </div>

            <div class="info-box">
                <div>
                    <div><strong>Monto Prestado: S/</strong></div>
                    <div class="info-box-val">{prestamo.monto:.2f}</div>
                </div>
                <div>
                    <div><strong>Interés ({prestamo.interes:.1f}%): S/</strong></div>
                    <div class="info-box-val">{monto_interes:.2f}</div>
                </div>
                <div>
                    <div><strong>Total a Pagar: S/</strong></div>
                    <div class="info-box-val">{prestamo.total:.2f}</div>
                </div>
            </div>

            <table class="tabla-concepto">
                <thead>
                    <tr>
                        <th style="width: 65%;">Concepto</th>
                        <th style="width: 35%; text-align: right;">Monto Cobrado</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="color: #444;">Abono a Préstamo #{prestamo.id}</td>
                        <td style="text-align: right; font-weight: bold;">S/ {pago.monto:.2f}</td>
                    </tr>
                </tbody>
            </table>

            <div class="saldo-line">
                Saldo Restante: S/ {prestamo.saldo:.2f}
            </div>
        </div>

    </body>
    </html>
    """

@app.post("/crear")
def crear_prestamo(deudor: str = Form(...), monto: float = Form(...), interes: float = Form(...), modalidad: str = Form("Diario"), cobrador: str = Form(...), request: Request = None, db: Session = Depends(get_db)):
    user = obtener_usuario_actual(request)
    if not user or user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    total_prestamos = db.query(PrestamoDB).count()
    nuevo_id = f"PRES-{101 + total_prestamos}"
    total = monto + (monto * (interes / 100))
    
    nuevo_prestamo = PrestamoDB(
        id=nuevo_id, deudor=deudor, monto=monto, interes=interes, total=total, saldo=total, modalidad=modalidad, cobrador_asignado=cobrador
    )
    
    db.add(nuevo_prestamo)
    db.commit()
    
    return RedirectResponse(url=f"/?msg={urllib.parse.quote('Préstamo creado correctamente.')}", status_code=status.HTTP_302_FOUND)

@app.post("/eliminar/{prestamo_id}")
def eliminar_prestamo(prestamo_id: str, request: Request = None, db: Session = Depends(get_db)):
    user = obtener_usuario_actual(request)
    if not user or user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    prestamo = db.query(PrestamoDB).filter(PrestamoDB.id == prestamo_id).first()
    if prestamo:
        db.delete(prestamo)
        db.commit()
    
    return RedirectResponse(url=f"/?msg={urllib.parse.quote('Préstamo eliminado.')}", status_code=status.HTTP_302_FOUND)
