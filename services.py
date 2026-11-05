import re
import urllib.parse
from datetime import date, timedelta
from sqlalchemy.orm import Session

from config import ID_INICIAL
from database import SessionLocal
from models import ClienteDB, CuotaDB, PagoDB, PrestamoDB, UsuarioDB


class ErrorNegocio(Exception):
    """Excepción para errores de regla de negocio que se muestran al usuario."""
    pass


# --- Usuarios y Cobradores --
def listar_cobradores(db: Session) -> list[tuple[str, str]]:
    filas = (
        db.query(UsuarioDB.username, UsuarioDB.nombre)
        .filter(UsuarioDB.rol == "cobrador")
        .all()
    )
    return [(username, nombre) for username, nombre in filas]


def nombre_usuario(username: str) -> str:
    """Para uso en plantillas Jinja2: abre y cierra su propia sesión."""
    db = SessionLocal()
    try:
        usuario = db.query(UsuarioDB).filter(UsuarioDB.username == username).first()
        return usuario.nombre if usuario else username
    finally:
        db.close()


# --- Gestión de Clientes ---
def obtener_o_crear_cliente(
    db: Session,
    documento: str,
    nombre: str,
    telefono: str = "",
    direccion: str = ""
) -> ClienteDB:
    """Busca un cliente por documento o por nombre; si no existe, lo crea con identificador único."""
    doc_limpio = (documento or "").strip()
    nombre_limpio = (nombre or "").strip()

    if not doc_limpio and not nombre_limpio:
        raise ErrorNegocio("Debe ingresar al menos el nombre del cliente.")

    cliente = None
    # 1. Buscar primero por documento si fue proporcionado
    if doc_limpio:
        cliente = db.query(ClienteDB).filter(ClienteDB.documento_identidad == doc_limpio).first()

    # 2. Si no se especificó documento o no se encontró, buscar por nombre exacto/similar
    if not cliente and nombre_limpio:
        cliente = db.query(ClienteDB).filter(ClienteDB.nombre_completo.ilike(nombre_limpio)).first()

    # 3. Si no existe, crearlo garantizando un documento de identidad único
    if not cliente:
        if doc_limpio:
            doc_final = doc_limpio
        else:
            base_slug = re.sub(r'[^a-zA-Z0-9]', '', nombre_limpio)[:8].upper() or "CLI"
            doc_final = f"CLI-{base_slug}"
            contador = 1
            while db.query(ClienteDB).filter(ClienteDB.documento_identidad == doc_final).first():
                doc_final = f"CLI-{base_slug}-{contador}"
                contador += 1

        try:
            cliente = ClienteDB(
                documento_identidad=doc_final,
                nombre_completo=nombre_limpio,
                telefono=telefono,
                direccion=direccion,
                calificacion="Bueno",
                activo=True
            )
            db.add(cliente)
            db.commit()
            db.refresh(cliente)
        except Exception:
            db.rollback()
            raise
    else:
        # Si ya existe el cliente, actualizamos sus datos si se enviaron nuevos
        try:
            modificado = False
            if telefono and cliente.telefono != telefono:
                cliente.telefono = telefono
                modificado = True
            if direccion and cliente.direccion != direccion:
                cliente.direccion = direccion
                modificado = True
            if doc_limpio and cliente.documento_identidad.startswith("CLI-"):
                # Si el cliente no tenía DNI real y ahora sí lo tiene, lo actualizamos
                cliente.documento_identidad = doc_limpio
                modificado = True
            if modificado:
                db.commit()
        except Exception:
            db.rollback()
            raise

    return cliente


def listar_clientes(db: Session) -> list[ClienteDB]:
    """Obtiene la lista de clientes registrados."""
    return db.query(ClienteDB).order_by(ClienteDB.nombre_completo.asc()).all()


# --- Motor de Amortización y Fechas ---
def _calcular_siguiente_fecha(fecha_base: date, modalidad: str, salto: int) -> date:
    """Calcula la fecha de vencimiento según la periodicidad del crédito."""
    mod = (modalidad or "Diario").capitalize()
    
    if mod == "Diario":
        fecha = fecha_base
        dias_agregados = 0
        while dias_agregados < salto:
            fecha += timedelta(days=1)
            if fecha.weekday() != 6: 
                dias_agregados += 1
        return fecha

    elif mod == "Semanal":
        return fecha_base + timedelta(weeks=salto)

    elif mod == "Quincenal":
        return fecha_base + timedelta(days=15 * salto)

    elif mod == "Mensual":
        return fecha_base + timedelta(days=30 * salto)

    return fecha_base + timedelta(days=salto)


def calcular_cronograma(
    monto: float,
    interes_porcentaje: float,
    modalidad: str,
    numero_cuotas: int,
    fecha_inicio: date = None
) -> list[dict]:
    """Genera la lista detallada de cuotas con capital, interés y fecha de vencimiento."""
    if monto <= 0:
        raise ErrorNegocio("El monto del préstamo debe ser mayor a cero.")
    if numero_cuotas <= 0:
        raise ErrorNegocio("El número de cuotas debe ser al menos 1.")

    fecha_base = fecha_inicio or date.today()
    interes_total = round(monto * (interes_porcentaje / 100.0), 2)
    total_a_pagar = round(monto + interes_total, 2)

    capital_cuota_base = round(monto / numero_cuotas, 2)
    interes_cuota_base = round(interes_total / numero_cuotas, 2)
    total_cuota_base = round(total_a_pagar / numero_cuotas, 2)

    cronograma = []
    capital_acumulado = 0.0
    interes_acumulado = 0.0
    total_acumulado = 0.0

    for i in range(1, numero_cuotas + 1):
        fecha_vence = _calcular_siguiente_fecha(fecha_base, modalidad, i)

        if i == numero_cuotas:
            cap = round(monto - capital_acumulado, 2)
            inte = round(interes_total - interes_acumulado, 2)
            tot = round(total_a_pagar - total_acumulado, 2)
        else:
            cap = capital_cuota_base
            inte = interes_cuota_base
            tot = total_cuota_base
            capital_acumulado += cap
            interes_acumulado += inte
            total_acumulado += tot

        cronograma.append({
            "numero_cuota": i,
            "fecha_vencimiento": fecha_vence.isoformat(),
            "monto_capital": cap,
            "monto_interes": inte,
            "total_cuota": tot,
            "saldo_cuota": tot,
            "estado": "Pendiente"
        })

    return cronograma


# --- Préstamos --
def prestamos_visibles(db: Session, usuario: dict) -> list[PrestamoDB]:
    consulta = db.query(PrestamoDB)
    if usuario["rol"] == "admin":
        consulta = consulta.filter(PrestamoDB.usuario_id == usuario["id"])
    elif usuario["rol"] in ("gerente", "supervisor"):
        pass
    else:
        consulta = consulta.filter(PrestamoDB.cobrador_asignado == usuario["username"])
    
    prestamos = consulta.all()
    # Actualizar estados de mora al consultar
    for p in prestamos:
        actualizar_estado_mora(db, p)
    return prestamos


def obtener_prestamo(db: Session, prestamo_id: str) -> PrestamoDB | None:
    prestamo = db.query(PrestamoDB).filter(PrestamoDB.id == prestamo_id).first()
    if prestamo:
        actualizar_estado_mora(db, prestamo)
    return prestamo


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


def crear_prestamo(
    db: Session,
    deudor: str,
    monto: float,
    interes: float,
    modalidad: str,
    cobrador: str,
    usuario_id: int,
    telefono: str = "",
    metodo_pago: str = "Efectivo",
    documento: str = "",
    direccion: str = "",
    numero_cuotas: int = 1
) -> PrestamoDB:
    """Crea un nuevo préstamo, asocia al cliente y genera su cronograma de cuotas."""
    if cobrador not in dict(listar_cobradores(db)):
        raise ErrorNegocio("Cobrador no válido.")
    if monto <= 0:
        raise ErrorNegocio("El monto debe ser mayor a 0.")
    if numero_cuotas <= 0:
        numero_cuotas = 1

    cliente = obtener_o_crear_cliente(
        db,
        documento=documento,
        nombre=deudor,
        telefono=telefono,
        direccion=direccion
    )

    hoy = date.today()
    cronograma_datos = calcular_cronograma(
        monto=monto,
        interes_porcentaje=interes,
        modalidad=modalidad,
        numero_cuotas=numero_cuotas,
        fecha_inicio=hoy
    )

    total = sum(c["total_cuota"] for c in cronograma_datos)
    fecha_fin = cronograma_datos[-1]["fecha_vencimiento"] if cronograma_datos else hoy.isoformat()

    try:
        prestamo = PrestamoDB(
            id=_generar_id(db),
            cliente_id=cliente.id,
            deudor=cliente.nombre_completo,
            monto=monto,
            interes=interes,
            total=total,
            saldo=total,
            modalidad=modalidad,
            numero_cuotas=numero_cuotas,
            fecha_inicio=hoy.isoformat(),
            fecha_vencimiento=fecha_fin,
            estado="Puntual",
            cobrador_asignado=cobrador,
            usuario_id=usuario_id,
            telefono=cliente.telefono or telefono,
            metodo_pago=metodo_pago,
        )
        db.add(prestamo)
        db.flush() 

        for c in cronograma_datos:
            cuota = CuotaDB(
                prestamo_id=prestamo.id,
                numero_cuota=c["numero_cuota"],
                fecha_vencimiento=c["fecha_vencimiento"],
                monto_capital=c["monto_capital"],
                monto_interes=c["monto_interes"],
                total_cuota=c["total_cuota"],
                saldo_cuota=c["saldo_cuota"],
                estado=c["estado"],
            )
            db.add(cuota)

        db.commit()
        db.refresh(prestamo)
        return prestamo
    except Exception:
        db.rollback()
        raise


def eliminar_prestamo(db: Session, prestamo: PrestamoDB) -> None:
    db.delete(prestamo)
    db.commit()


# --- Pagos y Distribución de Cuotas --
def actualizar_estado_mora(db: Session, prestamo: PrestamoDB) -> None:
    """Verifica si alguna cuota venció para marcar el préstamo en mora."""
    if prestamo.saldo <= 0:
        prestamo.estado = "Completado"
        return

    hoy_str = date.today().isoformat()
    tiene_mora = False

    for cuota in prestamo.cuotas:
        if cuota.saldo_cuota > 0 and cuota.fecha_vencimiento < hoy_str:
            cuota.estado = "Vencida"
            tiene_mora = True
        elif cuota.saldo_cuota <= 0:
            cuota.estado = "Pagada"
        elif cuota.saldo_cuota < cuota.total_cuota:
            cuota.estado = "Parcial"

    prestamo.estado = "En Mora" if tiene_mora else "Puntual"
    db.commit()


def registrar_pago(
    db: Session,
    prestamo: PrestamoDB,
    monto: float,
    registrado_por: str,
    metodo_pago: str = "Efectivo",
    cuota_id: int | None = None
) -> PagoDB:
    """Registra un pago y aplica el abono a las cuotas mediante FIFO o cuota elegida."""
    if monto <= 0:
        raise ErrorNegocio("El monto debe ser mayor a cero.")
    if monto > round(prestamo.saldo, 2):
        raise ErrorNegocio(f"El monto (S/ {monto:.2f}) supera el saldo pendiente (S/ {prestamo.saldo:.2f}).")

    prestamo.saldo = max(0.0, round(prestamo.saldo - monto, 2))

    pago = PagoDB(
        prestamo_id=prestamo.id,
        cuota_id=cuota_id,
        fecha=date.today().isoformat(),
        monto=monto,
        registrado_por=registrado_por,
        metodo_pago=metodo_pago,
    )
    db.add(pago)

    monto_restante = monto
    cuotas_ordenadas = sorted(prestamo.cuotas, key=lambda c: c.numero_cuota)

    if cuota_id:
        cuota_especifica = next((c for c in cuotas_ordenadas if c.id == cuota_id), None)
        if cuota_especifica and cuota_especifica.saldo_cuota > 0:
            abono = min(monto_restante, cuota_especifica.saldo_cuota)
            cuota_especifica.saldo_cuota = round(cuota_especifica.saldo_cuota - abono, 2)
            cuota_especifica.estado = "Pagada" if cuota_especifica.saldo_cuota <= 0 else "Parcial"
            monto_restante -= abono

    for cuota in cuotas_ordenadas:
        if monto_restante <= 0:
            break
        if cuota.saldo_cuota <= 0:
            continue

        abono = min(monto_restante, cuota.saldo_cuota)
        cuota.saldo_cuota = round(cuota.saldo_cuota - abono, 2)
        cuota.estado = "Pagada" if cuota.saldo_cuota <= 0 else "Parcial"
        monto_restante = round(monto_restante - abono, 2)

    actualizar_estado_mora(db, prestamo)

    db.commit()
    db.refresh(pago)
    return pago


# --- Notificaciones y Comprobantes ---
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
        f"Método de Pago: {pago.metodo_pago or 'Efectivo'}\n\n"
        "Concepto | Monto Cobrado\n"
        f"Abono a Préstamo #{p.id} | S/ {pago.monto:.2f}\n\n"
        f"Saldo Restante: S/ {p.saldo:.2f}"
    )
    return f"https://api.whatsapp.com/send?text={urllib.parse.quote(texto)}"


def url_whatsapp_cliente(prestamo: PrestamoDB, mensaje: str = "") -> str:
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