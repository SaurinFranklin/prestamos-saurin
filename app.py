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

        modalidad_texto = getattr(p, "modalidad", "Diario") or "Diario"

        tarjetas += f"""
        <div class="col-md-6 mb-4">
            <div class="card bg-black text-white shadow border border-secondary">
                <div class="card-header bg-dark d-flex justify-content-between align-items-center border-bottom border-secondary">
                    <div>
                        <h5 class="mb-0 text-info fw-bold">#{p.id} — {p.deudor}</h5>
                        <small class="badge bg-outline-secondary text-muted border border-secondary mt-1">🗓️ {modalidad_texto}</small>
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
        <title>Boleta #{pago.id} - Préstamos Geison</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{
                background-color: #f8f9fa;
                font-family: Arial, Helvetica, sans-serif;
                color: #000;
            }}
            .boleta-container {{
                max-width: 550px;
                margin: 20px auto;
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
                font-size: 20px;
                font-weight: 800;
                letter-spacing: 0.5px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
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
            .info-box-title {{
                font-weight: bold;
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
            .tabla-concepto th {{
                border: 1px solid #000;
                padding: 8px;
                font-weight: bold;
                font-size: 14px;
            }}
            .tabla-concepto td {{
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
            @media print {{
                .no-print {{ display: none !important; }}
                body {{ background: #fff !important; }}
                .boleta-container {{ border: 2px solid #000 !important; margin: 0 auto; box-shadow: none !important; }}
            }}
        </style>
    </head>
    <body class="p-3">
        <div class="boleta-container shadow-sm">
            <div class="boleta-header">
                <div class="boleta-title">
                    <span>🧾</span> BOLETA DE COMPROBANTE DE PAGO
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
                    <span class="info-box-title">Monto Prestado: S/</span>
                    <div class="info-box-val">{prestamo.monto:.2f}</div>
                </div>
                <div>
                    <span class="info-box-title">Interés ({prestamo.interes:.1f}%): S/</span>
                    <div class="info-box-val">{monto_interes:.2f}</div>
                </div>
                <div>
                    <span class="info-box-title">Total a Pagar: S/</span>
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
                        <td style="color: #666;">Abono a Préstamo #{prestamo.id}</td>
                        <td style="text-align: right; font-weight: bold;">S/ {pago.monto:.2f}</td>
                    </tr>
                </tbody>
            </table>

            <div class="saldo-line">
                Saldo Restante: S/ {prestamo.saldo:.2f}
            </div>

            <div class="d-grid gap-2 mt-4 no-print">
                <a href="{url_wa}" target="_blank" class="btn btn-success fw-bold py-2">📲 Enviar por WhatsApp</a>
                <button onclick="window.print()" class="btn btn-outline-dark fw-bold py-2">🖨️ Imprimir / Guardar PDF</button>
                <a href="/" class="btn btn-sm btn-link text-muted text-center text-decoration-none mt-1">🔙 Volver al Panel</a>
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
