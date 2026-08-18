from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse

app = FastAPI()

# Base de datos temporal
prestamos = [
    {
        "id": "PRES-101",
        "deudor": "Marufith",
        "moneda": "Soles (S/)",
        "monto": 1000.0,
        "interes": 20.0,
        "total": 1200.0,
        "saldo": 1175.0,
        "modalidad": "Semanal",
        "estado": "Cliente Puntual",
        "pagos": [
            {"fecha": "2026-08-18", "monto": 25.0, "registrado_por": "Cobrador"}
        ]
    }
]

def obtener_html(mensaje: str = "", boleta_html: str = ""):
    cards_html = ""
    for p in prestamos:
        historial_html = "".join([
            f"<li class='list-group-item d-flex justify-content-between align-items-center bg-dark text-white border-secondary'>"
            f"<span>📅 {p_item['fecha']} - {p_item['registrado_por']}</span>"
            f"<span class='badge bg-success fs-6'>S/ {p_item['monto']:.2f}</span>"
            f"</li>"
            for p_item in p["pagos"]
        ]) if p["pagos"] else "<li class='list-group-item bg-dark text-muted border-secondary'>Sin abonos registrados</li>"

        badge_color = "bg-success" if p["estado"] == "Cliente Puntual" else "bg-warning text-dark" if p["estado"] == "En Seguimiento" else "bg-danger"

        cards_html += f"""
        <div class='col-md-6 mb-4 item-prestamo' data-nombre='{p["deudor"].lower()}'>
            <div class='card bg-dark text-white border-secondary shadow-lg h-100'>
                <div class='card-header d-flex justify-content-between align-items-center border-secondary bg-black bg-opacity-25'>
                    <h5 class='m-0 text-info font-monospace'>#{p["id"]} — {p["deudor"]}</h5>
                    <span class='badge {badge_color}'>{p["estado"]}</span>
                </div>
                <div class='card-body'>
                    <div class='row mb-3 text-center'>
                        <div class='col-6 border-end border-secondary'>
                            <small class='text-muted d-block'>Total a Pagar</small>
                            <strong class='fs-5 text-light'>S/ {p["total"]:.2f}</strong>
                        </div>
                        <div class='col-6'>
                            <small class='text-muted d-block'>Saldo Restante</small>
                            <strong class='fs-5 text-danger'>S/ {p["saldo"]:.2f}</strong>
                        </div>
                    </div>
                    
                    <p class='mb-1'><small class='text-muted'>Modalidad:</small> <strong>{p["modalidad"]}</strong> | <small class='text-muted'>Interés:</small> <strong>{p["interes"]}%</strong></p>

                    <button class='btn btn-outline-info btn-sm w-100 mb-3' type='button' data-bs-toggle='collapse' data-bs-target='#historial-{p["id"]}'>
                        📋 Ver Historial de Pagos ({len(p["pagos"])})
                    </button>
                    
                    <div class='collapse mb-3' id='historial-{p["id"]}'>
                        <ul class='list-group list-group-flush rounded'>
                            {historial_html}
                        </ul>
                    </div>

                    <form action='/abonar' method='post' class='p-2 rounded bg-black bg-opacity-50 border border-secondary'>
                        <input type='hidden' name='p_id' value='{p["id"]}'>
                        <label class='form-label small text-info fw-bold mb-1'>Registrar Nuevo Abono:</label>
                        <div class='input-group input-group-sm mb-2'>
                            <span class='input-group-text bg-secondary text-white border-secondary'>S/</span>
                            <input type='number' step='0.01' name='monto_abono' class='form-control bg-dark text-white border-secondary' placeholder='Monto' required>
                            <button class='btn btn-success fw-bold' type='submit'>💰 Cobrar</button>
                        </div>
                    </form>
                </div>
                <div class='card-footer border-secondary bg-black bg-opacity-25 d-flex justify-content-between align-items-center solo-admin'>
                    <form action='/eliminar' method='post' onsubmit='return confirm("¿Eliminar préstamo?");' class='m-0 w-100'>
                        <input type='hidden' name='p_id' value='{p["id"]}'>
                        <button type='submit' class='btn btn-outline-danger btn-sm w-100'>🗑️ Eliminar Préstamo</button>
                    </form>
                </div>
            </div>
        </div>
        """

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
            .card:hover {{ transform: translateY(-3px); }}
            @media print {{
                body * {{ visibility: hidden; }}
                #boleta-imprimir, #boleta-imprimir * {{ visibility: visible; }}
                #boleta-imprimir {{ position: absolute; left: 0; top: 0; width: 100%; color: #000 !important; background: #fff !important; }}
            }}
        </style>
    </head>
    <body class="text-light">
        <div class="container py-4">
            <!-- Navbar / Header -->
            <div class="d-flex justify-content-between align-items-center pb-3 mb-4 border-bottom border-secondary">
                <h2 class="fw-bold text-info m-0">💼 Préstamos Saurin</h2>
                <div class="d-flex align-items-center gap-2">
                    <label class="small text-muted">Perfil:</label>
                    <select id="select-perfil" class="form-select form-select-sm bg-dark text-white border-info" onchange="cambiarPerfil()">
                        <option value="cobrador">Cobrador (Solo Registro)</option>
                        <option value="admin">Administrador (Control Total)</option>
                    </select>
                </div>
            </div>

            {f'<div class="alert alert-success alert-dismissible fade show" role="alert">{mensaje}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>' if mensaje else ''}

            <!-- Modal / Vista de Boleta -->
            {boleta_html}

            <div class="row">
                <!-- Panel Crear Préstamo (Solo Admin) -->
                <div class="col-lg-4 mb-4 solo-admin">
                    <div class="card bg-dark text-white border-info shadow">
                        <div class="card-header bg-info bg-opacity-10 border-info">
                            <h5 class="m-0 text-info">+ Nuevo Préstamo</h5>
                        </div>
                        <div class="card-body">
                            <form action="/crear" method="post">
                                <div class="mb-3">
                                    <label class="form-label small">Nombre del Deudor</label>
                                    <input type="text" name="deudor" class="form-control bg-dark text-white border-secondary" placeholder="Ej. Juan Pérez" required>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label small">Moneda</label>
                                    <select name="moneda" class="form-select bg-dark text-white border-secondary">
                                        <option value="Soles (S/)">Soles (S/)</option>
                                        <option value="Dólares ($)">Dólares ($)</option>
                                    </select>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label small">Monto Prestado</label>
                                    <input type="number" step="0.01" name="monto" class="form-control bg-dark text-white border-secondary" required>
                                </div>
                                <div class="row mb-3">
                                    <div class="col-6">
                                        <label class="form-label small">Modalidad</label>
                                        <select name="modalidad" class="form-select bg-dark text-white border-secondary">
                                            <option value="Diario">Diario</option>
                                            <option value="Semanal">Semanal</option>
                                            <option value="Quincenal">Quincenal</option>
                                            <option value="Mensual">Mensual</option>
                                        </select>
                                    </div>
                                    <div class="col-6">
                                        <label class="form-label small">Interés (%)</label>
                                        <input type="number" step="0.1" name="interes" value="10" class="form-control bg-dark text-white border-secondary" required>
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label small">Estado Inicial</label>
                                    <select name="estado" class="form-select bg-dark text-white border-secondary">
                                        <option value="Cliente Puntual">Cliente Puntual</option>
                                        <option value="En Seguimiento">En Seguimiento</option>
                                        <option value="En Mora">En Mora</option>
                                    </select>
                                </div>
                                <button type="submit" class="btn btn-info w-100 fw-bold">Crear Préstamo</button>
                            </form>
                        </div>
                    </div>
                </div>

                <!-- Lista de Préstamos -->
                <div class="col-lg-8" id="contenedor-prestamos">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h4 class="m-0 text-white">Lista de Préstamos</h4>
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
            function cambiarPerfil() {{
                const perfil = document.getElementById('select-perfil').value;
                const admins = document.querySelectorAll('.solo-admin');
                const colPrestamos = document.getElementById('contenedor-prestamos');

                if (perfil === 'admin') {{
                    const clave = prompt("Ingrese la clave de Administrador:");
                    if (clave === "admin") {{
                        admins.forEach(el => el.style.display = 'block');
                        colPrestamos.className = "col-lg-8";
                    }} else {{
                        alert("Clave incorrecta");
                        document.getElementById('select-perfil').value = 'cobrador';
                        aplicarModoCobrador();
                    }}
                }} else {{
                    aplicarModoCobrador();
                }}
            }}

            function aplicarModoCobrador() {{
                const admins = document.querySelectorAll('.solo-admin');
                const colPrestamos = document.getElementById('contenedor-prestamos');
                admins.forEach(el => el.style.display = 'none');
                colPrestamos.className = "col-lg-12";
            }}

            function filtrarClientes() {{
                const query = document.getElementById('buscador').value.toLowerCase();
                const items = document.querySelectorAll('.item-prestamo');
                items.forEach(item => {{
                    const nombre = item.getAttribute('data-nombre');
                    item.style.display = nombre.includes(query) ? 'block' : 'none';
                }});
            }}

            // Ejecutar al cargar
            aplicarModoCobrador();
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
    return obtener_html(f"Préstamo registrado exitosamente para <strong>{deudor}</strong>.")

@app.post("/abonar", response_class=HTMLResponse)
def abonar_prestamo(p_id: str = Form(...), monto_abono: float = Form(...)):
    for p in prestamos:
        if p["id"] == p_id:
            p["saldo"] = max(0.0, p["saldo"] - monto_abono)
            p["pagos"].append({"fecha": "2026-08-18", "monto": monto_abono, "registrado_por": "Cobrador"})
            
            # Generar Boleta Imprimible (Sin sección de firma)
            boleta_html = f"""
            <div class="card bg-white text-dark mb-4 border-success shadow" id="boleta-imprimir">
                <div class="card-body p-4">
                    <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-3">
                        <h4 class="fw-bold text-success m-0">🧾 BOLETA DE COMPROBANTE DE PAGO</h4>
                        <span class="badge bg-secondary">Código: {p["id"]}</span>
                    </div>
                    <div class="row mb-3">
                        <div class="col-6">
                            <p class="mb-1"><strong>Empresa:</strong> Préstamos Saurin</p>
                            <p class="mb-1"><strong>Cliente:</strong> {p["deudor"]}</p>
                        </div>
                        <div class="col-6 text-end">
                            <p class="mb-1"><strong>Fecha:</strong> 2026-08-18</p>
                            <p class="mb-1"><strong>Modalidad:</strong> {p["modalidad"]}</p>
                        </div>
                    </div>
                    <table class="table table-bordered mb-3">
                        <thead class="table-light">
                            <tr>
                                <th>Concepto</th>
                                <th class="text-end">Monto</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Abono a Préstamo #{p["id"]}</td>
                                <td class="text-end fw-bold">S/ {monto_abono:.2f}</td>
                            </tr>
                        </tbody>
                    </table>
                    <div class="d-flex justify-content-between align-items-center border-top pt-2">
                        <span><strong>Saldo Restante:</strong> S/ {p["saldo"]:.2f}</span>
                        <button onclick="window.print()" class="btn btn-primary btn-sm d-print-none">🖨️ Imprimir / Guardar PDF</button>
                    </div>
                </div>
            </div>
            """
            return obtener_html(f"Abono de S/ {monto_abono:.2f} registrado.", boleta_html)
    return obtener_html("Error al registrar abono.")

@app.post("/eliminar", response_class=HTMLResponse)
def eliminar_prestamo(p_id: str = Form(...)):
    global prestamos
    prestamos = [p for p in prestamos if p["id"] != p_id]
    return obtener_html("Préstamo eliminado.")
