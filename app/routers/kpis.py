from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.core.dependencies import get_taller_actual
from app.models.taller import Taller

router = APIRouter(prefix="/kpis", tags=["KPIs"])

@router.get("/dashboard")
def get_kpis(db: Session = Depends(get_db), taller: Taller = Depends(get_taller_actual)):

    # 1. Tiempo promedio de asignación (minutos)
    tiempo_asignacion = db.execute(text("""
        SELECT ROUND(AVG(
            EXTRACT(EPOCH FROM (
                SELECT MIN(h2.creado_en)
                FROM historial_estados h2
                WHERE h2.incidente_id = i.id
                AND h2.estado_nuevo = 'taller_asignado'
            ) - i.creado_en
        ) / 60), 1) as promedio_min
        FROM incidentes i
        WHERE i.taller_id = :taller_id
        AND i.estado NOT IN ('buscando_taller', 'cancelado')
    """), {"taller_id": str(taller.id)}).fetchone()

    # 2. Tiempo promedio de llegada (minutos)
    tiempo_llegada = db.execute(text("""
        SELECT ROUND(AVG(
            EXTRACT(EPOCH FROM (
                SELECT MIN(h2.creado_en)
                FROM historial_estados h2
                WHERE h2.incidente_id = i.id
                AND h2.estado_nuevo = 'en_atencion'
            ) - (
                SELECT MIN(h3.creado_en)
                FROM historial_estados h3
                WHERE h3.incidente_id = i.id
                AND h3.estado_nuevo = 'taller_asignado'
            )
        ) / 60), 1) as promedio_min
        FROM incidentes i
        WHERE i.taller_id = :taller_id
        AND i.estado IN ('en_atencion', 'finalizado')
    """), {"taller_id": str(taller.id)}).fetchone()

    # 3. Incidentes por tipo
    por_tipo = db.execute(text("""
        SELECT 
            COALESCE(tipo_problema, 'sin_clasificar') as tipo,
            COUNT(*) as total
        FROM incidentes
        WHERE taller_id = :taller_id
        GROUP BY tipo_problema
        ORDER BY total DESC
    """), {"taller_id": str(taller.id)}).fetchall()

    # 4. Total de incidentes por estado
    por_estado = db.execute(text("""
        SELECT estado, COUNT(*) as total
        FROM incidentes
        WHERE taller_id = :taller_id
        GROUP BY estado
        ORDER BY total DESC
    """), {"taller_id": str(taller.id)}).fetchall()

    # 5. Casos cancelados
    cancelados = db.execute(text("""
        SELECT 
            COUNT(*) FILTER (WHERE estado = 'cancelado') as cancelados,
            COUNT(*) as total
        FROM incidentes
        WHERE taller_id = :taller_id
    """), {"taller_id": str(taller.id)}).fetchone()

    # 6. SLA — servicios finalizados en menos de 60 minutos
    sla = db.execute(text("""
        SELECT
            COUNT(*) FILTER (
                WHERE completado_en IS NOT NULL
                AND EXTRACT(EPOCH FROM (completado_en - creado_en)) / 60 <= 60
            ) as dentro_sla,
            COUNT(*) FILTER (WHERE estado = 'finalizado') as total_finalizados
        FROM incidentes
        WHERE taller_id = :taller_id
    """), {"taller_id": str(taller.id)}).fetchone()

    # 7. Calificación promedio
    calificacion = db.execute(text("""
        SELECT 
            ROUND(AVG(puntuacion), 1) as promedio,
            COUNT(*) as total
        FROM calificaciones
        WHERE taller_id = :taller_id
    """), {"taller_id": str(taller.id)}).fetchone()

    # 8. Ingresos del mes actual
    ingresos_mes = db.execute(text("""
        SELECT 
            COALESCE(SUM(p.monto_taller), 0) as ingresos,
            COUNT(*) as pagos
        FROM pagos p
        JOIN incidentes i ON p.incidente_id = i.id
        WHERE i.taller_id = :taller_id
        AND DATE_TRUNC('month', p.creado_en) = DATE_TRUNC('month', NOW())
    """), {"taller_id": str(taller.id)}).fetchone()

    # 9. Incidentes por día (últimos 7 días)
    por_dia = db.execute(text("""
        SELECT 
            DATE(creado_en) as dia,
            COUNT(*) as total
        FROM incidentes
        WHERE taller_id = :taller_id
        AND creado_en >= NOW() - INTERVAL '7 days'
        GROUP BY DATE(creado_en)
        ORDER BY dia ASC
    """), {"taller_id": str(taller.id)}).fetchall()

    # 10. Zonas con más incidentes
    zonas = db.execute(text("""
        SELECT 
            ROUND(latitud::numeric, 2) as lat,
            ROUND(longitud::numeric, 2) as lng,
            COUNT(*) as total
        FROM incidentes
        WHERE taller_id = :taller_id
        GROUP BY ROUND(latitud::numeric, 2), ROUND(longitud::numeric, 2)
        ORDER BY total DESC
        LIMIT 10
    """), {"taller_id": str(taller.id)}).fetchall()

    total_inc = cancelados.total if cancelados else 0
    total_cancel = cancelados.cancelados if cancelados else 0
    tasa_cancelacion = round((total_cancel / total_inc * 100), 1) if total_inc > 0 else 0

    sla_pct = 0
    if sla and sla.total_finalizados and sla.total_finalizados > 0:
        sla_pct = round((sla.dentro_sla / sla.total_finalizados * 100), 1)

    return {
        "tiempo_promedio_asignacion_min": float(tiempo_asignacion.promedio_min) if tiempo_asignacion and tiempo_asignacion.promedio_min else 0,
        "tiempo_promedio_llegada_min": float(tiempo_llegada.promedio_min) if tiempo_llegada and tiempo_llegada.promedio_min else 0,
        "incidentes_por_tipo": [{"tipo": r.tipo, "total": r.total} for r in por_tipo],
        "incidentes_por_estado": [{"estado": r.estado, "total": r.total} for r in por_estado],
        "total_incidentes": total_inc,
        "total_cancelados": total_cancel,
        "tasa_cancelacion_pct": tasa_cancelacion,
        "sla_cumplimiento_pct": sla_pct,
        "calificacion_promedio": float(calificacion.promedio) if calificacion and calificacion.promedio else 0,
        "total_calificaciones": calificacion.total if calificacion else 0,
        "ingresos_mes_actual": float(ingresos_mes.ingresos) if ingresos_mes else 0,
        "pagos_mes_actual": ingresos_mes.pagos if ingresos_mes else 0,
        "incidentes_por_dia": [{"dia": str(r.dia), "total": r.total} for r in por_dia],
        "zonas_mas_incidentes": [{"lat": float(r.lat), "lng": float(r.lng), "total": r.total} for r in zonas],
    }