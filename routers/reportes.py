"""Rutas de reportes y estadísticas."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from database import get_db
from security import requiere_admin, requiere_usuario
from templating import templates

router = APIRouter()


@router.get("/reportes", response_class=HTMLResponse)
def reportes(request: Request, user: dict = Depends(requiere_admin),
             db: Session = Depends(get_db)):
    from models import PagoDB, PrestamoDB, UsuarioDB
    from sqlalchemy import func

    total_prestamos = db.query(PrestamoDB).count()
    prestamos_activos = db.query(PrestamoDB).filter(PrestamoDB.saldo > 0).count()
    prestamos_completados = db.query(PrestamoDB).filter(PrestamoDB.saldo <= 0).count()

    total_prestado = db.query(func.sum(PrestamoDB.monto)).scalar() or 0
    total_cobrado = db.query(func.sum(PagoDB.monto)).scalar() or 0
    total_por_cobrar = db.query(func.sum(PrestamoDB.saldo)).scalar() or 0

    pagos_hoy = db.query(PagoDB).filter(
        PagoDB.fecha == func.date("now")
    ).count()

    cobradores = db.query(UsuarioDB).filter(UsuarioDB.rol == "cobrador").all()
    rendimiento_cobradores = []
    for c in cobradores:
        prestamos_asignados = db.query(PrestamoDB).filter(
            PrestamoDB.cobrador_asignado == c.username
        ).count()
        cobrado_total = db.query(func.sum(PagoDB.monto)).join(
            PrestamoDB, PagoDB.prestamo_id == PrestamoDB.id
        ).filter(PrestamoDB.cobrador_asignado == c.username).scalar() or 0
        rendimiento_cobradores.append({
            "nombre": c.nombre,
            "prestamos": prestamos_asignados,
            "cobrado": cobrado_total,
        })

    return templates.TemplateResponse(request, "reportes.html", {
        "user": user,
        "total_prestamos": total_prestamos,
        "prestamos_activos": prestamos_activos,
        "prestamos_completados": prestamos_completados,
        "total_prestado": total_prestado,
        "total_cobrado": total_cobrado,
        "total_por_cobrar": total_por_cobrar,
        "pagos_hoy": pagos_hoy,
        "rendimiento_cobradores": rendimiento_cobradores,
    })
