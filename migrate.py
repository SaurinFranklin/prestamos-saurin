from sqlalchemy import inspect, text

from database import SessionLocal, engine, init_db
from security import hash_password

# Credenciales de inicio de sesión iniciales
SEED_USUARIOS = [
    {"username": "Geison", "password": "xiomara789", "rol": "admin", "nombre": "Administrador"},
    {"username": "juan", "password": "juan123", "rol": "cobrador", "nombre": "Juan Cobrador"},
    {"username": "pedro", "password": "pedro123", "rol": "cobrador", "nombre": "Pedro Cobrador"},
]


def _columna_existe(tabla: str, columna: str) -> bool:
    """Inspecciona el catálogo de la BD para verificar si una columna ya existe."""
    inspector = inspect(engine)
    if not inspector.has_table(tabla):
        return False
    columnas = [c["name"] for c in inspector.get_columns(tabla)]
    return columna in columnas


def ejecutar() -> None:
    init_db()

    columnas_prestamos = [
        ("usuario_id", "INTEGER"),
        ("cliente_id", "INTEGER"),
        ("telefono", "VARCHAR"),
        ("metodo_pago", "VARCHAR DEFAULT 'Efectivo'"),
        ("numero_cuotas", "INTEGER DEFAULT 1"),
        ("fecha_inicio", "VARCHAR"),
        ("fecha_vencimiento", "VARCHAR"),
    ]
    with engine.begin() as conn:
        for col_nombre, col_tipo in columnas_prestamos:
            if not _columna_existe("prestamos", col_nombre):
                conn.execute(text(f"ALTER TABLE prestamos ADD COLUMN {col_nombre} {col_tipo}"))

    columnas_pagos = [
        ("cuota_id", "INTEGER"),
        ("metodo_pago", "VARCHAR DEFAULT 'Efectivo'"),
        ("notas", "VARCHAR"),
    ]
    with engine.begin() as conn:
        for col_nombre, col_tipo in columnas_pagos:
            if not _columna_existe("pagos", col_nombre):
                conn.execute(text(f"ALTER TABLE pagos ADD COLUMN {col_nombre} {col_tipo}"))

    from models import ClienteDB, CuotaDB, PrestamoDB, UsuarioDB

    db = SessionLocal()
    try:
        for seed in SEED_USUARIOS:
            existe = (
                db.query(UsuarioDB)
                .filter(UsuarioDB.username == seed["username"])
                .first()
            )
            if not existe:
                db.add(UsuarioDB(
                    username=seed["username"],
                    password_hash=hash_password(seed["password"]),
                    rol=seed["rol"],
                    nombre=seed["nombre"],
                ))
        db.commit()

        admin = db.query(UsuarioDB).filter(UsuarioDB.rol == "admin").first()
        if admin:
            db.query(PrestamoDB).filter(PrestamoDB.usuario_id.is_(None)).update(
                {PrestamoDB.usuario_id: admin.id}
            )
            db.commit()

        prestamos_sin_cliente = db.query(PrestamoDB).filter(PrestamoDB.cliente_id.is_(None)).all()
        for p in prestamos_sin_cliente:
            doc_gen = f"CLI-{p.id}"
            cliente = db.query(ClienteDB).filter(ClienteDB.documento_identidad == doc_gen).first()
            if not cliente:
                cliente = ClienteDB(
                    documento_identidad=doc_gen,
                    nombre_completo=p.deudor or "Cliente Histórico",
                    telefono=p.telefono or "",
                    direccion="",
                    calificacion="Bueno",
                    activo=True,
                )
                db.add(cliente)
                db.flush()
            p.cliente_id = cliente.id

        prestamos_todos = db.query(PrestamoDB).all()
        for p in prestamos_todos:
            if not p.cuotas:
                cuota = CuotaDB(
                    prestamo_id=p.id,
                    numero_cuota=1,
                    fecha_vencimiento=p.fecha_vencimiento or "2026-12-31",
                    monto_capital=p.monto,
                    monto_interes=p.monto_interes,
                    total_cuota=p.total,
                    saldo_cuota=p.saldo,
                    estado="Pagada" if p.completado else ("En Mora" if p.estado == "En Mora" else "Pendiente"),
                )
                db.add(cuota)

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    ejecutar()
    print(" Migración completada con éxito.")