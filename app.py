import datetime
import hashlib
import sqlite3
import uvicorn
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse

app = FastAPI(title="Sistema de Gestión de Préstamos con Seguridad")

DB_NAME = "prestamos.db"
# Cambia esta contraseña por la que tú prefieras
ADMIN_PASSWORD = "Saurin200319"  


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prestamos (
            id TEXT PRIMARY KEY,
            deudor TEXT NOT NULL,
            monto_inicial REAL NOT NULL,
            modalidad TEXT NOT NULL,
            tasa_interes REAL NOT NULL,
            moneda TEXT NOT NULL,
            estado_cliente TEXT NOT NULL,
            total_deuda REAL NOT NULL,
            saldo_pendiente REAL NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_prestamo TEXT NOT NULL,
            codigo_pago TEXT NOT NULL,
            fecha_hora TEXT NOT NULL,
            monto_abonado REAL NOT NULL,
            saldo_restante REAL NOT NULL,
            FOREIGN KEY (id_prestamo) REFERENCES prestamos (id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


init_db()


@app.get("/api/prestamos")
def listar_prestamos():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM prestamos")
    filas_p = cursor.fetchall()

    resultado = []
    for p in filas_p:
        (
            id_p,
            deudor,
            monto_in,
            modalidad,
            tasa,
            moneda,
            estado_cli,
            total_d,
            saldo_p,
        ) = p

        cursor.execute(
            "SELECT fecha_hora, monto_abonado, saldo_restante, codigo_pago FROM pagos WHERE id_prestamo = ?",
            (id_p,),
        )
        pagos_raw = cursor.fetchall()
        pagos = [
            {
                "fecha_hora": row[0],
                "monto_abonado": round(row[1], 2),
                "saldo_restante": round(row[2], 2),
                "codigo_pago": row[3],
            }
            for row in pagos_raw
        ]

        progreso = (
            100
            if total_d == 0
            else min(
                100, round(((total_d - saldo_p) / total_d) * 100, 1)
            )
        )

        resultado.append({
            "id": id_p,
            "deudor": deudor,
            "moneda": moneda,
            "estado_cliente": estado_cli,
            "monto_inicial": round(monto_in, 2),
            "total_deuda": round(total_d, 2),
            "tasa": f"{round(tasa * 100, 1)}%",
            "saldo_pendiente": round(saldo_p, 2),
            "modalidad": modalidad,
            "progreso": progreso,
            "pagos": pagos,
        })

    conn.close()
    return resultado


@app.post("/api/prestamos/nuevo")
def crear_prestamo(
    deudor: str = Form(...),
    monto: float = Form(...),
    modalidad: str = Form(...),
    tasa: float = Form(...),
    moneda: str = Form(...),
    estado_cliente: str = Form(...),
):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM prestamos")
    total = cursor.fetchone()[0]
    id_p = f"PRES-{total + 101}"

    tasa_dec = tasa / 100.0
    total_deuda = monto * (1 + tasa_dec)

    cursor.execute(
        """
        INSERT INTO prestamos (id, deudor, monto_inicial, modalidad, tasa_interes, moneda, estado_cliente, total_deuda, saldo_pendiente)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            id_p,
            deudor,
            monto,
            modalidad,
            tasa_dec,
            moneda,
            estado_cliente,
            total_deuda,
            total_deuda,
        ),
    )

    conn.commit()
    conn.close()
    return {"status": "ok", "id": id_p}


@app.post("/api/prestamos/pago")
def abonar(id_prestamo: str = Form(...), monto: float = Form(...)):
    if monto <= 0:
        raise HTTPException(
            status_code=400, detail="El monto debe ser positivo"
        )

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT saldo_pendiente FROM prestamos WHERE id = ?", (id_prestamo,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")

    saldo_actual = row[0]
    if saldo_actual <= 0:
        conn.close()
        raise HTTPException(
            status_code=400, detail="El préstamo ya está liquidado"
        )

    monto_real = min(monto, saldo_actual)
    nuevo_saldo = saldo_actual - monto_real
    fecha_hora = datetime.datetime.now().strftime("%d/%m/%Y %I:%M %p")

    payload = f"{id_prestamo}|{monto_real}|{nuevo_saldo}|{fecha_hora}"
    codigo_hash = hashlib.sha256(payload.encode()).hexdigest()[:10].upper()
    codigo_pago = f"PAY-{codigo_hash[:5]}-{codigo_hash[5:]}"

    cursor.execute(
        "UPDATE prestamos SET saldo_pendiente = ? WHERE id = ?",
        (nuevo_saldo, id_prestamo),
    )
    cursor.execute(
        """
        INSERT INTO pagos (id_prestamo, codigo_pago, fecha_hora, monto_abonado, saldo_restante)
        VALUES (?, ?, ?, ?, ?)
    """,
        (id_prestamo, codigo_pago, fecha_hora, monto_real, nuevo_saldo),
    )

    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "recibo": {
            "codigo_pago": codigo_pago,
            "fecha_hora": fecha_hora,
            "monto_abonado": round(monto_real, 2),
            "saldo_restante": round(nuevo_saldo, 2),
        },
    }


@app.delete("/api/prestamos/eliminar/{id_prestamo}")
def eliminar_prestamo(id_prestamo: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM prestamos WHERE id = ?", (id_prestamo,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_CONTENT


HTML_CONTENT = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sistema de Gestión de Préstamos</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0f172a; --card-bg: #1e293b; --accent: #38bdf8;
            --text-main: #f8fafc; --text-muted: #94a3b8; --success: #22c55e;
            --danger: #f43f5e; --border: #334155;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }}
        body {{ background-color: var(--bg-color); color: var(--text-main); padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        
        .role-selector {{
            background: #1e293b; padding: 15px; border-radius: 8px; border: 1px solid var(--border);
            display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;
        }}
        .role-selector select {{ padding: 8px 12px; background: #0f172a; color: white; border: 1px solid var(--accent); border-radius: 6px; }}

        .grid {{ display: grid; grid-template-columns: 320px 1fr; gap: 20px; }}
        @media(max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}

        .card {{ background: var(--card-bg); border-radius: 12px; padding: 20px; border: 1px solid var(--border); margin-bottom: 20px; }}
        form label {{ display: block; font-size: 0.85rem; color: var(--text-muted); margin-top: 10px; }}
        form input, form select {{ width: 100%; padding: 10px; margin-top: 4px; border-radius: 6px; border: 1px solid var(--border); background: #0f172a; color: white; }}
        button {{ width: 100%; background: var(--accent); color: #000; font-weight: 600; padding: 10px; border: none; border-radius: 6px; margin-top: 15px; cursor: pointer; }}
        
        .prestamo-item {{ background: #0f172a; border-radius: 8px; padding: 20px; margin-bottom: 15px; border: 1px solid var(--border); }}
        .badge-puntual {{ background: #065f46; color: #34d399; padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; }}
        .badge-deudor {{ background: #881337; color: #fda4af; padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; }}
        
        .actions {{ display: flex; gap: 8px; margin-top: 15px; flex-wrap: wrap; }}
        .actions button {{ padding: 8px 12px; font-size: 0.82rem; margin-top: 0; width: auto; }}
        
        .admin-only {{ display: block; }}
        .cobrador-mode .admin-only {{ display: none !important; }}
    </style>
</head>
<body class="cobrador-mode" id="bodyMode">
    <div class="container">
        <div class="role-selector">
            <div>
                <strong>Modo de Acceso Actual:</strong> <span id="lblRole" style="color: #22c55e;">COBRADOR (Solo Registro de Abonos)</span>
            </div>
            <div>
                <label style="margin-right: 8px; font-size: 0.9rem;">Perfil:</label>
                <select id="selectPerfil" onchange="solicitarCambioPerfil(this.value)">
                    <option value="cobrador" selected>Cobrador</option>
                    <option value="admin">Administrador (Requiere Clave)</option>
                </select>
            </div>
        </div>

        <div class="grid">
            <div class="admin-only">
                <div class="card">
                    <h2>+ Nuevo Préstamo</h2>
                    <form id="formNuevo">
                        <label>Nombre del Deudor</label>
                        <input type="text" id="deudor" required placeholder="Ej. Juan Pérez">
                        
                        <label>Moneda</label>
                        <select id="moneda">
                            <option value="S/" selected>Soles (S/)</option>
                            <option value="$">Dólares ($)</option>
                        </select>

                        <label>Monto Prestado</label>
                        <input type="number" id="monto" required min="1" step="0.01">
                        
                        <label>Modalidad de Pago</label>
                        <select id="modalidad">
                            <option value="diario">Diario</option>
                            <option value="semanal" selected>Semanal</option>
                        </select>
                        
                        <label>Tasa de Interés (%)</label>
                        <input type="number" id="tasa" value="10">

                        <label>Estado del Cliente</label>
                        <select id="estado_cliente">
                            <option value="Cliente Puntual">Cliente Puntual</option>
                            <option value="Cliente Deudor">Cliente Deudor</option>
                        </select>
                        
                        <button type="submit">Crear Préstamo</button>
                    </form>
                </div>
            </div>

            <div style="grid-column: span 2;" id="colPréstamos">
                <div class="card">
                    <h2>Lista de Préstamos</h2>
                    <input type="text" id="buscador" placeholder="🔍 Buscar cliente por nombre..." onkeyup="filtrarClientes()" style="width: 100%; padding: 10px; margin-bottom: 15px; border-radius: 6px; background: #0f172a; border: 1px solid var(--border); color: white;">
                    <div id="listaPrestamos">Cargando...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const PASSWORD_CORRECTA = "{ADMIN_PASSWORD}";
        let prestamosGlobal = [];
        let esAdmin = false;

        function solicitarCambioPerfil(rol) {{
            if (rol === 'admin') {{
                const pass = prompt('🔒 Ingresa la contraseña de Administrador:');
                if (pass === PASSWORD_CORRECTA) {{
                    esAdmin = true;
                    aplicarPerfil('admin');
                }} else {{
                    alert('❌ Contraseña incorrecta.');
                    document.getElementById('selectPerfil').value = esAdmin ? 'admin' : 'cobrador';
                }}
            }} else {{
                esAdmin = false;
                aplicarPerfil('cobrador');
            }}
        }}

        function aplicarPerfil(rol) {{
            const body = document.getElementById('bodyMode');
            const lbl = document.getElementById('lblRole');
            const col = document.getElementById('colPréstamos');

            if (rol === 'admin') {{
                body.className = 'admin-mode';
                lbl.innerText = 'ADMINISTRADOR (Control Total)';
                lbl.style.color = '#38bdf8';
                col.style.gridColumn = 'span 1';
            }} else {{
                body.className = 'cobrador-mode';
                lbl.innerText = 'COBRADOR (Solo Registro de Abonos)';
                lbl.style.color = '#22c55e';
                col.style.gridColumn = 'span 2';
            }}
            cargarPrestamos();
        }}

        async function cargarPrestamos() {{
            try {{
                const res = await fetch('/api/prestamos');
                prestamosGlobal = await res.json();
                renderizarLista(prestamosGlobal);
            }} catch (err) {{
                document.getElementById('listaPrestamos').innerHTML = '<p style="color: var(--danger)">Error al conectar con la base de datos.</p>';
            }}
        }}

        function renderizarLista(data) {{
            const contenedor = document.getElementById('listaPrestamos');
            if (data.length === 0) {{
                contenedor.innerHTML = '<p style="color: var(--text-muted)">No hay registros.</p>';
                return;
            }}

            let html = '';
            for (let p of data) {{
                html += `
                <div class="prestamo-item">
                    <div style="display:flex; justify-content:space-between;">
                        <strong>${{p.id}} — ${{p.deudor}}</strong>
                        <span class="${{p.estado_cliente === 'Cliente Deudor' ? 'badge-deudor' : 'badge-puntual'}}">${{p.estado_cliente}}</span>
                    </div>
                    
                    <div style="margin-top: 10px; font-size: 0.9rem;">
                        <div>Total a Pagar: <strong>${{p.moneda}} ${{p.total_deuda}}</strong></div>
                        <div style="font-size:1.1rem; margin-top:5px; color:${{p.saldo_pendiente === 0 ? 'var(--success)' : 'var(--danger)'}}">
                            Saldo Restante: <strong>${{p.moneda}} ${{p.saldo_pendiente}}</strong>
                        </div>
                    </div>

                    <div class="actions">
                        ${{p.saldo_pendiente > 0 ? `<button onclick="realizarPago('${{p.id}}')" style="background: var(--success); color: black;">+ Registrar Cobro / Abono</button>` : ''}}
                        <button class="admin-only" onclick="eliminarPrestamo('${{p.id}}')" style="background: var(--danger); color: white;">🗑️ Borrar</button>
                    </div>
                </div>
                `;
            }}
            contenedor.innerHTML = html;
        }}

        function filtrarClientes() {{
            const texto = document.getElementById('buscador').value.toLowerCase();
            const filtrados = prestamosGlobal.filter(p => p.deudor.toLowerCase().includes(texto));
            renderizarLista(filtrados);
        }}

        document.getElementById('formNuevo').addEventListener('submit', async (e) => {{
            e.preventDefault();
            const formData = new FormData();
            formData.append('deudor', document.getElementById('deudor').value);
            formData.append('monto', document.getElementById('monto').value);
            formData.append('modalidad', document.getElementById('modalidad').value);
            formData.append('tasa', document.getElementById('tasa').value);
            formData.append('moneda', document.getElementById('moneda').value);
            formData.append('estado_cliente', document.getElementById('estado_cliente').value);

            await fetch('/api/prestamos/nuevo', {{ method: 'POST', body: formData }});
            e.target.reset();
            cargarPrestamos();
        }});

        async function realizarPago(id) {{
            const monto = prompt('Monto cobrado por el trabajador:');
            if (!monto || isNaN(monto) || parseFloat(monto) <= 0) return;

            const formData = new FormData();
            formData.append('id_prestamo', id);
            formData.append('monto', monto);

            const res = await fetch('/api/prestamos/pago', {{ method: 'POST', body: formData }});
            const data = await res.json();
            if (data.recibo) {{
                alert(`¡Cobro registrado con éxito!\nCódigo de Comprobante: ${{data.recibo.codigo_pago}}`);
            }}
            cargarPrestamos();
        }}

        async function eliminarPrestamo(id) {{
            if (confirm(`¿Borrar este préstamo permanentemente?`)) {{
                await fetch(`/api/prestamos/eliminar/${{id}}`, {{ method: 'DELETE' }});
                cargarPrestamos();
            }}
        }}

        cargarPrestamos();
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)