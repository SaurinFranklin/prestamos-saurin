from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
import urllib.parse

app = FastAPI()

# Base de datos temporal con préstamos iniciales
prestamos = [
    {
        "id": "PRES-101",
        "deudor": "Franklin",
        "moneda": "Soles (S/)",
        "monto": 300.0,
        "interes": 10.0,
        "total": 330.0,
        "saldo": 210.0,
        "modalidad": "Diario",
        "estado": "Cliente Puntual",
        "pagos": [
            {"fecha": "2026-08-18", "monto": 120.0, "registrado_por": "Cobrador"}
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
        "pagos": [
            {"fecha": "2026-08-18", "monto": 1000.0, "registrado_por": "Cobrador"}
        ]
    }
]

def obtener_html(mensaje: str = "", ultimo_pago: dict = None):
    cards_html = ""
    for p in prestamos:
        historial_html = "".join([
            f"<li class='list-group-item d-flex justify-content-between align-items-center bg-dark text-white border-secondary small py-1'>"
            f"<span>📅 {p_item['fecha']}</span>"
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

        cards_html += f"""
        <div class='col-md-6 mb-4 item-prestamo' data-nombre='{p["deudor"].lower()}'>
            <div class='card bg-dark text-white border-secondary shadow-lg h-100'>
                <div class='card-header d-flex justify-content-between align-items-center border-secondary bg-black bg-opacity-25 py-2'>
                    <h5 class='m-0 text-info font-monospace fs-6'>#{p["id"]} — {p["deudor"]}</h5>
                    <span class='badge {badge_color}'>{estado_texto}</span>
                </div>
                <div class='card-body py-3'>
                    <div class='row mb-2 text-center'>
                        <div class='col-6 border-end border-secondary'>
                            <small class='text-muted d-block'>Total a Pagar</small>
                            <strong class='fs-6 text-light'>S/ {p["total"]:.2f}</strong>
                        </div>
                        <div class='col-6'>
                            <small class='text-muted d-block'>Saldo Restante</small>
                            <strong class='fs-6 {"text-success" if p["saldo"] <= 0 else "text-danger"}'>S/ {p["saldo"]:.2f}</strong>
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
                <div class='card-footer border-secondary bg-black bg-opacity-25 d-flex justify-content-between align-items-center solo-admin py-2' style='display: none;'>
                    <form action='/eliminar' method='post' onsubmit='return confirm("¿Eliminar préstamo?");' class='m-0 w-100'>
                        <input type='hidden' name='p_id' value='{p["id"]}'>
                        <button type='submit' class='btn btn-outline-danger btn-sm w-100 py-1'>🗑️ Eliminar Préstamo</button>
                    </form>
                </div>
            </div>
        </div>
        """

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

            <!-- Formato de Boleta para Impresión / PDF -->
            <div class="d-none d-print-block p-3 text-black">
                <h4 class="text-center fw-bold mb-1">🧾 BOLETA DE COMPROBANTE DE PAGO</h4>
                <div class="text-center small mb-3"><strong>Empresa:</strong> Préstamos Saurin</div>
                <hr class="my-2">
                <div class="row small mb-2">
                    <div class="col-6"><strong>Código:</strong> {ultimo_pago.get('id', 'PRES-101')}</div>
                    <div class="col-6 text-end"><strong>Fecha:</strong> 2026-08-18</div>
                    <div class="col-6"><strong>Cliente:</strong> {ultimo_pago['deudor']}</div>
                    <div class="col-6 text-end"><strong>Modalidad:</strong> {ultimo_pago.get('modalidad', 'Diario')}</div>
                </div>
                <table class="table table-bordered table-sm my-3 border-dark">
                    <thead class="table-light border-dark">
                        <tr>
                            <th>Concepto</th>
                            <th class="text-end">Monto</th>
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
            .extra-small {{ font-size: 0.8rem; }}
            
            @media print {{
                body {{ background-color: #ffffff !important; color: #000000 !important; }}
                .d-print-none {{ display: none !important; }}
                .d-print-block {{ display: block !important; }}
                #comprobante-alerta {{
                    background-color: #ffffff !important;
                    color: #000000 !important;
                    border: 2px solid #000000 !important;
                    box-shadow: none !important;
                }}
            }}
        </style>
    </head>
    <body class="text-light">
        <div class="container py-4">
            <div class="d-flex justify-content-between align-items-center pb-3 mb-4 border-bottom border-secondary d-print-none">
                <h2 class="fw-bold text-info m-0 fs-4">💼 Préstamos Saurin</h2>
                <div class="d-flex align-items-center gap-2">
                    <label class="small text-muted d-none d-sm-inline">Perfil:</label>
                    <select id="select-perfil" class="form-select form-select-sm bg-dark text-white border-info">
                        <option value="cobrador">Cobrador (Solo Registro)</option>
                        <option value="admin">Administrador (Control Total)</option>
                    </select>
                </div>
            </div>

            {alerta_html}

            <div class="row d-print-none">
                <div class="col-lg-4 mb-4 solo-admin" style="display: none;">
                    <div class="card bg-dark text-white border-info shadow">
                        <div class="card-header bg-info bg-opacity-10 border-info py-2">
                            <h5 class="m-0 text-info fs-6">+ Nuevo Préstamo</h5>
                        </div>
                        <div class="card-body">
                            <form action="/crear" method="post">
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

                <div class="col-lg-12" id="contenedor-prestamos">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h5 class="m-0 text-white">Lista de Préstamos</h5>
                        <input type="text" id="buscador" class="form-control form-control-sm w-50 bg-dark text-white border-secondary" placeholder="🔍 Buscar cliente..." onkeyup="filtrarClientes()">
                    </div>

                    <div class="row">
                        {cards_html}
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            document.addEventListener("DOMContentLoaded", function() {{
                const selectorPerfil = document.getElementById('select-perfil');
                
                // Forzar inicio en cobrador
                selectorPerfil.value = 'cobrador';
                aplicarModoCobrador();

                selectorPerfil.addEventListener('change', function() {{
                    const perfil = this.value;
                    const admins = document.querySelectorAll('.solo-admin');
                    const colPrestamos = document.getElementById('contenedor-prestamos');

                    if (perfil === 'admin') {{
                        const clave = prompt("Ingrese la clave de Administrador:");
                        if (clave === "Saurin.1903") {{
                            admins.forEach(el => el.style.display = 'block');
                            colPrestamos.className = "col-lg-8";
                        }} else {{
                            if (clave !== null) alert("Clave incorrecta");
                            selectorPerfil.value = 'cobrador';
                            aplicarModoCobrador();
                        }}
                    }} else {{
                        aplicarModoCobrador();
                    }}
                }});
            }});

            function aplicarModoCobrador() {{
                const admins = document.querySelectorAll('.solo-admin');
                const colPrestamos = document.getElementById('contenedor-prestamos');
                admins.forEach(el => el.style.display = 'none');
                if (colPrestamos) colPrestamos.className = "col-lg-12";
            }}

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

@app.get("/", response_class=HTMLResponse)
def inicio():
    return obtener_html()

@app.post("/crear", response_class=HTMLResponse)
def crear_prestamo(deudor: str = Form(...), moneda: str = Form(...), monto: float = Form(...), modalidad: str = Form(...), interes: float = Form(...), estado: str = Form(...)):
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
        "pagos": []
    })
    return obtener_html(f"Préstamo registrado para <strong>{deudor}</strong>.")

@app.post("/abonar", response_class=HTMLResponse)
def abonar_prestamo(p_id: str = Form(...), monto_abono: float = Form(...)):
    for p in prestamos:
        if p["id"] == p_id:
            if p["saldo"] <= 0:
                return obtener_html("⚠️ Este préstamo ya fue cancelado completamente.")
            
            monto_real = min(monto_abono, p["saldo"])
            p["saldo"] = max(0.0, p["saldo"] - monto_real)
            p["pagos"].append({"fecha": "2026-08-18", "monto": monto_real, "registrado_por": "Cobrador"})
            
            info_pago = {
                "id": p["id"],
                "deudor": p["deudor"],
                "monto": monto_real,
                "saldo": p["saldo"],
                "modalidad": p["modalidad"]
            }
            return obtener_html(f"Abono de S/ {monto_real:.2f} registrado.", ultimo_pago=info_pago)
    return obtener_html("Error al registrar abono.")

@app.post("/eliminar", response_class=HTMLResponse)
def eliminar_prestamo(p_id: str = Form(...)):
    global prestamos
    prestamos = [p for p in prestamos if p["id"] != p_id]
    return obtener_html("Préstamo eliminado.")
