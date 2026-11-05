"""Rutas de gestión integral y perfil 360° de clientes."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from models import ClienteDB, PrestamoDB
from security import requiere_admin, requiere_usuario
from templating import templates

router = APIRouter()


@router.get("/clientes", response_class=HTMLResponse)
def listar_clientes(
    request: Request,
    q: str = "",
    msg: str = "",
    err: str = "",
    user: dict = Depends(requiere_usuario),
    db: Session = Depends(get_db)
):
    """Directorio general de clientes con métricas de endeudamiento y riesgo."""
    consulta = db.query(ClienteDB)

    if q.strip():
        termino = f"%{q.strip()}%"
        consulta = consulta.filter(
            or_(
                ClienteDB.nombre_completo.ilike(termino),
                ClienteDB.documento_identidad.ilike(termino),
                ClienteDB.telefono.ilike(termino),
            )
        )

    clientes_raw = consulta.order_by(ClienteDB.nombre_completo.asc()).all()

    # Procesar métricas por cliente
    clientes_data = []
    for c in clientes_raw:
        total_prestamos = len(c.prestamos)
        activos = sum(1 for p in c.prestamos if p.saldo > 0)
        saldo_total = sum(p.saldo for p in c.prestamos)
        tiene_mora = any(p.estado == "En Mora" and p.saldo > 0 for p in c.prestamos)

        if tiene_mora:
            estado_salud = "En Mora"
        elif activos > 0:
            estado_salud = "Al Día"
        elif total_prestamos > 0:
            estado_salud = "Sin Deuda"
        else:
            estado_salud = "Nuevo"

        clientes_data.append({
            "cliente": c,
            "total_prestamos": total_prestamos,
            "prestamos_activos": activos,
            "saldo_total": saldo_total,
            "estado_salud": estado_salud,
        })

    return templates.TemplateResponse(request, "clientes.html", {
        "user": user,
        "clientes": clientes_data,
        "q": q,
        "msg": msg,
        "err": err,
    })


@router.get("/clientes/{cliente_id}", response_class=HTMLResponse)
def detalle_cliente(
    cliente_id: int,
    request: Request,
    msg: str = "",
    err: str = "",
    user: dict = Depends(requiere_usuario),
    db: Session = Depends(get_db)
):
    """Ficha 360° del cliente con historial completo de créditos y pagos."""
    cliente = db.query(ClienteDB).filter(ClienteDB.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # Métricas consolidadas del cliente
    total_prestado = sum(p.monto for p in cliente.prestamos)
    total_pagado = sum((p.total - p.saldo) for p in cliente.prestamos)
    saldo_pendiente = sum(p.saldo for p in cliente.prestamos)

    return templates.TemplateResponse(request, "cliente_detalle.html", {
        "user": user,
        "c": cliente,
        "prestamos": cliente.prestamos,
        "total_prestado": total_prestado,
        "total_pagado": total_pagado,
        "saldo_pendiente": saldo_pendiente,
        "msg": msg,
        "err": err,
    })


@router.post("/clientes/{cliente_id}/editar")
def editar_cliente(
    cliente_id: int,
    nombre_completo: str = Form(...),
    documento: str = Form(""),
    telefono: str = Form(""),
    direccion: str = Form(""),
    calificacion: str = Form("Bueno"),
    user: dict = Depends(requiere_admin),
    db: Session = Depends(get_db)
):
    """Actualiza datos personales y calificación de riesgo del cliente."""
    cliente = db.query(ClienteDB).filter(ClienteDB.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    try:
        cliente.nombre_completo = nombre_completo.strip()
        if documento.strip():
            cliente.documento_identidad = documento.strip()
        cliente.telefono = telefono.strip()
        cliente.direccion = direccion.strip()
        cliente.calificacion = calificacion
        db.commit()
    except Exception as e:
        db.rollback()
        return RedirectResponse(
            f"/clientes/{cliente_id}?err=Error al actualizar: {str(e)}",
            status_code=status.HTTP_302_FOUND
        )

    return RedirectResponse(
        f"/clientes/{cliente_id}?msg=Cliente actualizado correctamente.",
        status_code=status.HTTP_302_FOUND
    )
