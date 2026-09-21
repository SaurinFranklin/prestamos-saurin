"""Lógica de negocio (sin HTML ni rutas)."""
import re
import urllib.parse
from datetime import date

from sqlalchemy.orm import Session

from config import ID_INICIAL, USUARIOS
from models import PagoDB, PrestamoDB


class ErrorNegocio(Exception):
    """Error de validación que se le muestra al usuario."""


# --- Usuarios ---------------------------------------------------------
def listar_cobradores() -> list[tuple[str, str]]:
    return [(user, d["nombre"]) for user, d in USUARIOS.items() if d["rol"] == "cobrador"]


def nombre_usuario(username: str) -> str:
    return USUARIOS.get(username, {}).get("nombre", username)


# --- Préstamos --------------------------------------------------------
def prestamos_visibles(db: Session, usuario: dict) -> list[PrestamoDB]:
    consulta = db.query(PrestamoDB)
    if usuario["rol"] != "admin":
        consulta = consulta.filter(PrestamoDB.cobrador_asignado == usuario["username"])
    return consulta.all()


def obtener_prestamo(db: Session, prestamo_id: str) -> PrestamoDB | None:
    return db.query(PrestamoDB).filter(PrestamoDB.id == prestamo_id).first()


def tiene_acceso(usuario: dict, prestamo: PrestamoDB) -> bool:
    return usuario["rol"] == "admin" or prestamo.cobrador_asignado == usuario["username"]


def _generar_id(db: Session) -> str:
    mayor = ID_INICIAL
    for (pid,) in db.query(PrestamoDB.id).all():
        numeros = re.findall(r"\d+", str(pid))
        if numeros:
            mayor = max(mayor, int(numeros[0]))
    return f"PRES-{mayor + 1}"


def crear_prestamo(db: Session, deudor: str, monto: float, interes: float,
                   modalidad: str, cobrador: str) -> PrestamoDB:
    if cobrador not in dict(listar_cobradores()):
        raise ErrorNegocio("Cobrador no válido.")

    total = monto + monto * (interes / 100)
    prestamo = PrestamoDB(
        id=_generar_id(db),
        deudor=deudor,
        monto=monto,
        interes=interes,
        total=total,
        saldo=total,
        modalidad=modalidad,
        cobrador_asignado=cobrador,
    )
    db.add(prestamo)
    db.commit()
    return prestamo


def eliminar_prestamo(db: Session, prestamo: PrestamoDB) -> None:
    db.delete(prestamo)
    db.commit()


# --- Pagos ------------------------------------------------------------
def registrar_pago(db: Session, prestamo: PrestamoDB, monto: float, registrado_por: str) -> PagoDB:
    if monto <= 0:
        raise ErrorNegocio("El monto debe ser mayor a cero.")
    if monto > prestamo.saldo:
        raise ErrorNegocio("El monto supera el saldo restante.")

    prestamo.saldo = max(0.0, prestamo.saldo - monto)
    pago = PagoDB(
        prestamo_id=prestamo.id,
        fecha=date.today().isoformat(),
        monto=monto,
        registrado_por=registrado_por,
    )
    db.add(pago)
    db.commit()
    db.refresh(pago)
    return pago


def url_whatsapp(pago: PagoDB) -> str:
    p = pago.prestamo
    texto = (
        "*BOLETA DE COMPROBANTE DE PAGO*\n"
        "Empresa: Préstamos Geison\n"
        f"Código: {p.id}\n"
        f"Cliente: {p.deudor}\n"
        f"Monto Prestado: S/ {p.monto:.2f}\n"
        f"Interés ({p.interes:.1f}%): S/ {p.monto_interes:.2f}\n"
        f"Total a Pagar: S/ {p.total:.2f}\n\n"
        f"Fecha: {pago.fecha}\n"
        f"Modalidad: {p.modalidad or 'Diario'}\n\n"
        "Concepto | Monto Cobrado\n"
        f"Abono a Préstamo #{p.id} | S/ {pago.monto:.2f}\n\n"
        f"Saldo Restante: S/ {p.saldo:.2f}"
    )
    return f"https://api.whatsapp.com/send?text={urllib.parse.quote(texto)}"
