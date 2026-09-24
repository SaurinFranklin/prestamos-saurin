"""Rutas de préstamos, pagos y comprobantes."""
import urllib.parse

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

import services
from config import INTERES_POR_DEFECTO, MODALIDADES
from database import get_db
from security import requiere_admin, requiere_usuario
from templating import templates

router = APIRouter()


def _volver_al_panel(msg: str = "", err: str = "") -> RedirectResponse:
    clave, texto = ("msg", msg) if msg else ("err", err)
    return RedirectResponse(f"/?{clave}={urllib.parse.quote(texto)}",
                            status_code=status.HTTP_302_FOUND)


def _prestamo_o_404(db: Session, prestamo_id: str):
    prestamo = services.obtener_prestamo(db, prestamo_id)
    if not prestamo:
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")
    return prestamo


# --- Panel ------------------------------------------------------------
@router.get("/", response_class=HTMLResponse)
def panel(request: Request, msg: str = "", err: str = "",
          user: dict = Depends(requiere_usuario), db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "panel.html", {
        "user": user,
        "prestamos": services.prestamos_visibles(db, user),
        "cobradores": services.listar_cobradores(db),
        "modalidades": MODALIDADES,
        "interes_defecto": INTERES_POR_DEFECTO,
        "msg": msg,
        "err": err,
    })


# --- Crear / eliminar (solo admin) -----------------------------------
@router.post("/crear")
def crear(deudor: str = Form(...), monto: float = Form(...), interes: float = Form(...),
          modalidad: str = Form("Diario"), cobrador: str = Form(...),
          user: dict = Depends(requiere_admin), db: Session = Depends(get_db)):
    try:
        services.crear_prestamo(db, deudor, monto, interes, modalidad, cobrador,
                                user["id"])
    except services.ErrorNegocio as e:
        return _volver_al_panel(err=str(e))
    return _volver_al_panel(msg="Préstamo creado correctamente.")


@router.post("/eliminar/{prestamo_id}")
def eliminar(prestamo_id: str, user: dict = Depends(requiere_admin),
             db: Session = Depends(get_db)):
    prestamo = services.obtener_prestamo(db, prestamo_id)
    if prestamo and services.tiene_acceso(user, prestamo):
        services.eliminar_prestamo(db, prestamo)
    return _volver_al_panel(msg="Préstamo eliminado.")


# --- Pagos ------------------------------------------------------------
@router.post("/pagar/{prestamo_id}")
def pagar(prestamo_id: str, monto: float = Form(...),
          user: dict = Depends(requiere_usuario), db: Session = Depends(get_db)):
    prestamo = _prestamo_o_404(db, prestamo_id)
    if not services.tiene_acceso(user, prestamo):
        raise HTTPException(status_code=403, detail="No autorizado")

    try:
        pago = services.registrar_pago(db, prestamo, monto, user["username"])
    except services.ErrorNegocio as e:
        return _volver_al_panel(err=str(e))

    return RedirectResponse(f"/comprobante/{pago.id}", status_code=status.HTTP_302_FOUND)


@router.get("/comprobante/{pago_id}", response_class=HTMLResponse)
def comprobante(pago_id: int, request: Request,
                user: dict = Depends(requiere_usuario), db: Session = Depends(get_db)):
    from models import PagoDB

    pago = db.query(PagoDB).filter(PagoDB.id == pago_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    if not services.tiene_acceso(user, pago.prestamo):
        raise HTTPException(status_code=403, detail="No autorizado")

    return templates.TemplateResponse(request, "comprobante.html", {
        "pago": pago,
        "prestamo": pago.prestamo,
        "url_wa": services.url_whatsapp(pago),
    })
