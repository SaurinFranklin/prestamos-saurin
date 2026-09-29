"""Lógica de negocio (sin HTML ni rutas)."""
import re
import urllib.parse
from datetime import date

from sqlalchemy.orm import Session

from config import ID_INICIAL
from database import SessionLocal
from models import PagoDB, PrestamoDB, UsuarioDB


class ErrorNegocio(Exception):
    """Error de validación que se le muestra al usuario."""


# --- Usuarios ---------------------------------------------------------
def listar_cobradores(db: Session) -> list[tuple[str, str]]:
    filas = (
        db.query(UsuarioDB.username, UsuarioDB.nombre)
        .filter(UsuarioDB.rol == "cobrador")
        .all()
    )
    return [(username, nombre) for username, nombre in filas]


def nombre_usuario(username: str) -> str:
    """Para plantillas: abre su propia sesión (no depende de la petición)."""
    db = SessionLocal()
    try:
        usuario = db.query(UsuarioDB).filter(UsuarioDB.username == username).first()
        return usuario.nombre if usuario else username
    finally:
        db.close()


# --- Préstamos --------------------------------------------------------
def prestamos_visibles(db: Session, usuario: dict) -> list[PrestamoDB]:
    consulta = db.query(PrestamoDB)
    if usuario["rol"] == "admin":
        consulta = consulta.filter(PrestamoDB.usuario_id == usuario["id"])
    elif usuario["rol"] in ("gerente", "supervisor"):
        pass
    else:
        consulta = consulta.filter(PrestamoDB.cobrador_asignado == usuario["username"])
    return consulta.all()


def obtener_prestamo(db: Session, prestamo_id: str) -> PrestamoDB | None:
    return db.query(PrestamoDB).filter(PrestamoDB.id == prestamo_id).first()


def tiene_acceso(usuario: dict, prestamo: PrestamoDB) -> bool:
    if usuario["rol"] == "admin":
        return prestamo.usuario_id == usuario["id"]
    if usuario["rol"] in ("gerente", "supervisor"):
        return True
    return prestamo.cobrador_asignado == usuario["username"]


def _generar_id(db: Session) -> str:
    mayor = ID_INICIAL
    for (pid,) in db.query(PrestamoDB.id).all():
        numeros = re.findall(r"\d+", str(pid))
        if numeros:
            mayor = max(mayor, int(numeros[0]))
    return f"PRES-{mayor + 1}"


def crear_prestamo(db: Session, deudor: str, monto: float, interes: float,
                   modalidad: str, cobrador: str, usuario_id: int,
                   telefono: str = "", metodo_pago: str = "Efectivo") -> PrestamoDB:
    if cobrador not in dict(listar_cobradores(db)):
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
        usuario_id=usuario_id,
        telefono=telefono,
        metodo_pago=metodo_pago,
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
        f"Modalidad: {p.modalidad or 'Diario'}\n"
        f"Método de Pago: {p.metodo_pago or 'Efectivo'}\n\n"
        "Concepto | Monto Cobrado\n"
        f"Abono a Préstamo #{p.id} | S/ {pago.monto:.2f}\n\n"
        f"Saldo Restante: S/ {p.saldo:.2f}"
    )
    return f"https://api.whatsapp.com/send?text={urllib.parse.quote(texto)}"


def url_whatsapp_cliente(prestamo: PrestamoDB, mensaje: str = "") -> str:
    """Genera URL de WhatsApp para enviar mensaje al cliente."""
    if not prestamo.telefono:
        return ""
    texto = mensaje or (
        f"Estimado/a {prestamo.deudor}, le recordamos que tiene un préstamo "
        f"pendiente de S/ {prestamo.saldo:.2f}. Por favor, realice su pago "
        f"a tiempo. Gracias."
    )
    telefono = prestamo.telefono.replace(" ", "").replace("-", "")
    if not telefono.startswith("+"):
        telefono = "+51" + telefono
    return f"https://api.whatsapp.com/send?phone={telefono}&text={urllib.parse.quote(texto)}"


def notificar_pago_cliente(pago: PagoDB) -> str:
    """Genera URL para notificar al cliente sobre su pago."""
    p = pago.prestamo
    if not p.telefono:
        return ""
    texto = (
        f"✅ *PAGO RECIBIDO*\n\n"
        f"Estimado/a {p.deudor}, hemos recibido su pago de S/ {pago.monto:.2f}.\n\n"
        f"Préstamo: {p.id}\n"
        f"Saldo restante: S/ {p.saldo:.2f}\n\n"
        f"¡Gracias por su puntualidad!"
    )
    telefono = p.telefono.replace(" ", "").replace("-", "")
    if not telefono.startswith("+"):
        telefono = "+51" + telefono
    return f"https://api.whatsapp.com/send?phone={telefono}&text={urllib.parse.quote(texto)}"
