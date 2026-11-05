"""Rutas de reportes ejecutivos, métricas financieras y análisis de cartera."""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import CuotaDB, PagoDB, PrestamoDB, UsuarioDB
from security import requiere_admin
from templating import templates

router = APIRouter()


@router.get("/reportes", response_class=HTMLResponse)
def reportes(
    request: Request,
    user: dict = Depends(requiere_admin),
    db: Session = Depends(get_db)
):
    hoy = date.today()
    hoy_str = hoy.isoformat()

    # 1. Métricas de conteo de cartera
    total_prestamos = db.query(PrestamoDB).count()
    prestamos_activos = db.query(PrestamoDB).filter(PrestamoDB.saldo > 0).count()
    prestamos_completados = db.query(PrestamoDB).filter(PrestamoDB.saldo <= 0).count()
    prestamos_al_dia = db.query(PrestamoDB).filter(PrestamoDB.saldo > 0, PrestamoDB.estado != "En Mora").count()
    prestamos_en_mora = db.query(PrestamoDB).filter(PrestamoDB.saldo > 0, PrestamoDB.estado == "En Mora").count()

    # 2. Métricas monetarias agregadas
    total_prestado = float(db.query(func.sum(PrestamoDB.monto)).scalar() or 0.0)
    total_cobrado = float(db.query(func.sum(PagoDB.monto)).scalar() or 0.0)
    total_por_cobrar = float(db.query(func.sum(PrestamoDB.saldo)).scalar() or 0.0)
    total_pactado = float(db.query(func.sum(PrestamoDB.total)).scalar() or 0.0)
    total_intereses = round(total_pactado - total_prestado, 2)

    # 3. Capital en riesgo (mora)
    monto_en_riesgo = float(
        db.query(func.sum(PrestamoDB.saldo))
        .filter(PrestamoDB.estado == "En Mora")
        .scalar() or 0.0
    )
    porcentaje_mora = round((monto_en_riesgo / total_por_cobrar * 100), 1) if total_por_cobrar > 0 else 0.0

    # 4. Cobranzas del día de hoy
    pagos_hoy = db.query(func.count(PagoDB.id)).filter(PagoDB.fecha == hoy_str).scalar() or 0
    recaudado_hoy = float(db.query(func.sum(PagoDB.monto)).filter(PagoDB.fecha == hoy_str).scalar() or 0.0)

    # 5. Serie de tiempo: Cobros de los últimos 7 días para el gráfico
    dias_labels = []
    cobros_dias = []
    for i in range(6, -1, -1):
        dia = hoy - timedelta(days=i)
        dia_str = dia.isoformat()
        dias_labels.append(dia.strftime("%d/%m"))
        recaudo = db.query(func.sum(PagoDB.monto)).filter(PagoDB.fecha == dia_str).scalar() or 0.0
        cobros_dias.append(round(float(recaudo), 2))

    # 6. Panel de Alertas: Cuotas para hoy y Cuotas vencidas
    cuotas_hoy = (
        db.query(CuotaDB)
        .join(PrestamoDB)
        .filter(CuotaDB.saldo_cuota > 0, CuotaDB.fecha_vencimiento == hoy_str)
        .order_by(CuotaDB.numero_cuota.asc())
        .all()
    )

    cuotas_vencidas = (
        db.query(CuotaDB)
        .join(PrestamoDB)
        .filter(CuotaDB.saldo_cuota > 0, CuotaDB.fecha_vencimiento < hoy_str)
        .order_by(CuotaDB.fecha_vencimiento.asc())
        .limit(15)
        .all()
    )

    # 7. Rendimiento de cobradores
    cobradores = db.query(UsuarioDB).filter(UsuarioDB.rol == "cobrador").all()
    rendimiento_cobradores = []
    for c in cobradores:
        asignados = db.query(PrestamoDB).filter(PrestamoDB.cobrador_asignado == c.username).count()
        cobrado_total = float(
            db.query(func.sum(PagoDB.monto))
            .join(PrestamoDB, PagoDB.prestamo_id == PrestamoDB.id)
            .filter(PrestamoDB.cobrador_asignado == c.username)
            .scalar() or 0.0
        )
        rendimiento_cobradores.append({
            "nombre": c.nombre,
            "username": c.username,
            "prestamos": asignados,
            "cobrado": cobrado_total,
        })

    return templates.TemplateResponse(request, "reportes.html", {
        "user": user,
        "total_prestamos": total_prestamos,
        "prestamos_activos": prestamos_activos,
        "prestamos_completados": prestamos_completados,
        "prestamos_al_dia": prestamos_al_dia,
        "prestamos_en_mora": prestamos_en_mora,
        "total_prestado": total_prestado,
        "total_cobrado": total_cobrado,
        "total_por_cobrar": total_por_cobrar,
        "total_intereses": total_intereses,
        "monto_en_riesgo": monto_en_riesgo,
        "porcentaje_mora": porcentaje_mora,
        "pagos_hoy": pagos_hoy,
        "recaudado_hoy": recaudado_hoy,
        "dias_labels": dias_labels,
        "cobros_dias": cobros_dias,
        "cuotas_hoy": cuotas_hoy,
        "cuotas_vencidas": cuotas_vencidas,
        "rendimiento_cobradores": rendimiento_cobradores,
    })
