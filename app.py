import os
import urllib.parse
from datetime import date
from fastapi import FastAPI, Form, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

# -------------------------------------------------------------------
# Configuración de Base de Datos PostgreSQL (SQLAlchemy)
# -------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# Render usa "postgres://", pero SQLAlchemy requiere "postgresql://"
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

# Genera las tablas en la base de datos automáticamente
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
    "Saurin": {"password": "saurin1903", "rol": "admin", "nombre": "Administrador"},
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
# Vistas HTML (Interfaz con CSS #050505)
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
            <div class="d-flex justify-content-between align-items-center border-bottom border-secondary py-1 small">
                <span>📅 {pago.fecha} ({pago.registrado_por})</span>
                <span class="badge bg-success">S/ {pago.monto:.2f}</span>
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
                    <h5 class="mb-0 text-info fw-bold">#{p.id} — {p.deudor}</h5>
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
                <a class="navbar-brand fw-bold text-info" href="/">📌 Préstamos Saurin</a>
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
            
    return RedirectResponse(url=f"/?msg={urllib.parse.quote('Abono registrado.')}", status_code=status.HTTP_302_FOUND)

@app.post("/crear")
def crear_prestamo(deudor: str = Form(...), monto: float = Form(...), interes: float = Form(...), cobrador: str = Form(...), request: Request = None, db: Session = Depends(get_db)):
    user = obtener_usuario_actual(request)
    if not user or user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    total_prestamos = db.query(PrestamoDB).count()
    nuevo_id = f"PRES-{101 + total_prestamos}"
    total = monto + (monto * (interes / 100))
    
    nuevo_prestamo = PrestamoDB(
        id=nuevo_id, deudor=deudor, monto=monto, interes=interes, total=total, saldo=total, cobrador_asignado=cobrador
    )
    
    db.add(nuevo_prestamo)
    db.commit()
    
    return RedirectResponse(url=f"/?msg={urllib.parse.quote('Préstamo creado.')}", status_code=status.HTTP_302_FOUND)

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
