import os
import urllib.parse
from datetime import date
from fastapi import FastAPI, Form, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
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
    estado = Column(String, default="Cliente Puntual")
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

SECRET_KEY = "saurin_secret_key_super_segura"
serializer = URLSafeTimedSerializer(SECRET_KEY)

USUARIOS = {
    "Geison": {"password": "xiomara789", "rol": "admin", "nombre": "Administrador"},
    "Lester": {"password": "juan123", "rol": "cobrador", "nombre": "Cobrador"},
    "pedro": {"password": "pedro123", "rol": "cobrador", "nombre": "Cobrador"}
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
        <title>Login - Préstamos Saurin</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #050505 !important; }}
            .card-login {{ background-color: #121212 !important; border: 1px solid #222222 !important; }}
        </style>
    </head>
    <body class="text-light d-flex align-items-center justify-content-center" style="min-height: 100vh;">
        <div class="card card-login text-white p-4 shadow-lg rounded-3" style="width: 100%; max-width: 380px;">
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

def obtener_html_panel(user: dict, db: Session, mensaje: str = ""):
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

        tarjetas += f"""
        <div class="col-md-6 mb-4">
            <div class="card bg-black text-white shadow border border-secondary">
                <div class="card-header bg-dark d-flex justify-content-between align-items-center border-bottom border-secondary">
                    <div>
                        <h5 class="mb-0 text-info fw-bold">#{p.id} — {p.deudor}</h5>
                        <small class="badge bg-outline-secondary text-muted border border-secondary mt-1">🗓️ {p.modalidad}</small>
                    </div>
                    <div>
                        <span class="badge bg-success">{p.estado}</span>
                        {btn_eliminar}
                    </div>
                </div>
                <div class="card-body">
                    <p class="small text-muted mb-2">Cobrador: <strong>{USUARIOS.get(p.cobrador_asignado, {}).get('nombre', p.cobrador_asignado)}</strong></p>
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
                            <strong class="text-danger">S/ {p.saldo:.2f}</strong>
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

                    <form action="/pagar/{p.id}" method="post">
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
                    <input type="number" step="0.01" name="monto" class="form-control bg-dark text-white border-secondary" placeholder="Monto (S/)" required>
                </div>
                <div class="col-md-2">
                    <input type="number" step="0.1" name="interes" class="form-control bg-dark text-white border-secondary" placeholder="Interés %" value="15" required>
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

    return f"""
    <!DOCTYPE html>
    <html lang="es" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Préstamos Saurin</title>
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
            {seccion_crear}
            <h4 class="mb-3 text-light">Lista de Préstamos</h4>
            <div class="row">
                {tarjetas if tarjetas else '<div class="col-12"><div class="alert alert-warning bg-dark border-warning text-warning">No hay préstamos asignados.</div></div>'}
            </div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """

# -------------------------------------------------------------------
# Endpoints / Rutas
# -------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index(request: Request, msg: str = "", db: Session = Depends(get_db)):
    user = obtener_usuario_actual(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return obtener_html_panel(user, db, mensaje=msg)

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
    cobrador_nombre = USUARIOS.get(pago.registrado_por, {}).get("nombre", pago.registrado_por)
    
    texto_wa = f"📌 *PRÉSTAMOS SAURIN*\n" \
               f"🧾 *Comprobante de Pago #{pago.id}*\n" \
               f"👤 Cliente: {prestamo.deudor}\n" \
               f"🗓️ Modalidad: {prestamo.modalidad}\n" \
               f"💰 Abono: S/ {pago.monto:.2f}\n" \
               f"📉 Saldo Restante: S/ {prestamo.saldo:.2f}\n" \
               f"📅 Fecha: {pago.fecha}\n" \
               f"📱 Registrado por: {cobrador_nombre}\n\n" \
               f"¡Gracias por su pago!"
               
    url_wa = f"https://api.whatsapp.com/send?text={urllib.parse.quote(texto_wa)}"

    return f"""
    <!DOCTYPE html>
    <html lang="es" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Comprobante #{pago.id} - Préstamos Saurin</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #050505 !important; color: #ffffff; }}
            .ticket {{ background-color: #121212; border: 1px dashed #444; max-width: 400px; margin: 30px auto; padding: 25px; border-radius: 10px; }}
            @media print {{
                .no-print {{ display: none !important; }}
                body {{ background-color: #ffffff !important; color: #000000 !important; }}
                .ticket {{ border: 1px solid #000; background-color: #fff !important; color: #000 !important; }}
            }}
        </style>
    </head>
    <body class="p-3">
        <div class="ticket shadow-lg">
            <h3 class="text-center text-info fw-bold mb-1">📌 PRÉSTAMOS SAURIN</h3>
            <p class="text-center text-muted small mb-3">Comprobante Oficial de Pago</p>
            <hr class="border-secondary">
            
            <div class="d-flex justify-content-between mb-2">
                <span class="text-muted">N° Recibo:</span>
                <strong>#{pago.id}</strong>
            </div>
            <div class="d-flex justify-content-between mb-2">
                <span class="text-muted">Fecha:</span>
                <span>{pago.fecha}</span>
            </div>
            <div class="d-flex justify-content-between mb-2">
                <span class="text-muted">Cliente:</span>
                <strong>{prestamo.deudor}</strong>
            </div>
            <div class="d-flex justify-content-between mb-2">
                <span class="text-muted">Modalidad:</span>
                <span>{prestamo.modalidad}</span>
            </div>
            <div class="d-flex justify-content-between mb-2">
                <span class="text-muted">Cobrador:</span>
                <span>{cobrador_nombre}</span>
            </div>
            
            <hr class="border-secondary my-3">
            
            <div class="d-flex justify-content-between mb-2 fs-5">
                <span>Monto Abonado:</span>
                <strong class="text-success">S/ {pago.monto:.2f}</strong>
            </div>
            <div class="d-flex justify-content-between mb-2">
                <span class="text-muted">Saldo Restante:</span>
                <strong class="text-danger">S/ {prestamo.saldo:.2f}</strong>
            </div>
            
            <hr class="border-secondary my-3">
            <p class="text-center small text-muted mb-4">¡Gracias por su puntualidad!</p>
            
            <div class="d-grid gap-2 no-print">
                <a href="{url_wa}" target="_blank" class="btn btn-success fw-bold">📲 Enviar por WhatsApp</a>
                <button onclick="window.print()" class="btn btn-outline-info fw-bold">🖨️ Imprimir / Guardar PDF</button>
                <a href="/" class="btn btn-sm btn-link text-muted text-center mt-1">⬅️ Volver al Panel</a>
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
