"""Conexión y sesión de base de datos."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DATABASE_URL

es_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False, "timeout": 30} if es_sqlite else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

if es_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        """WAL: lectores no bloquean al escritor; busy timeout evita errores."""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


def init_db() -> None:
    """Crea las tablas si no existen."""
    import models  # noqa: F401  (registra los modelos en Base)
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
