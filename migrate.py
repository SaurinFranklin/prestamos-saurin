"""Migración idempotente: crea usuarios, agrega columna dueño y repara datos.

Uso manual:  python3 migrate.py
También se ejecuta al arrancar la app (app.py).
"""
from sqlalchemy import inspect, text

from database import SessionLocal, engine, init_db
from security import hash_password

# Credenciales originales de config.py — ahora se guardan hasheadas en la BD
SEED_USUARIOS = [
    {"username": "Geison", "password": "xiomara789", "rol": "admin", "nombre": "Administrador"},
    {"username": "juan", "password": "juan123", "rol": "cobrador", "nombre": "Juan Cobrador"},
    {"username": "pedro", "password": "pedro123", "rol": "cobrador", "nombre": "Pedro Cobrador"},
]


def _columna_existe(tabla: str, columna: str) -> bool:
    columnas = [c["name"] for c in inspect(engine).get_columns(tabla)]
    return columna in columnas


def ejecutar() -> None:
    init_db()

    # 1. BD antigua sin la columna usuario_id (create_all no altera tablas)
    if not _columna_existe("prestamos", "usuario_id"):
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE prestamos ADD COLUMN usuario_id INTEGER"))

    # 2. Semilla de usuarios (solo si no existen)
    from models import PrestamoDB, UsuarioDB

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

        # 3. Préstamos huérfanos → dueño = admin (cero pérdida de datos)
        admin = db.query(UsuarioDB).filter(UsuarioDB.rol == "admin").first()
        if admin:
            db.query(PrestamoDB).filter(PrestamoDB.usuario_id.is_(None)).update(
                {PrestamoDB.usuario_id: admin.id}
            )
            db.commit()
    finally:
        db.close()
