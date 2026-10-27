import csv
import io
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.serializers import clean_value, row_to_dict
from app.security import require_viewer

router = APIRouter(prefix="/api", tags=["reportes"])

SORT_COLUMNS = {"report_date": "report_date", "generated_at": "generated_at"}


def serialize_report(row):
    data = row_to_dict(row)
    data["highlights"] = clean_value(data.get("highlights") or [])
    data["statistics"] = clean_value(data.get("statistics") or {})
    return data


@router.get("/reports")
def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    q: str | None = Query(default=None, max_length=120),
    sort: str = Query(default="report_date"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    user=Depends(require_viewer),
    db: Session = Depends(get_db),
):
    if sort not in SORT_COLUMNS:
        raise HTTPException(status_code=422, detail="Columna de orden no permitida")
    where = ""
    params = {}
    if q:
        where = "WHERE (title ILIKE :q OR summary ILIKE :q)"
        params["q"] = f"%{q}%"
    total = db.execute(text(f"SELECT count(*) FROM ai.reports {where}"), params).scalar_one()
    rows = (
        db.execute(
            text(
                f"""
                SELECT id, report_date, title, summary, highlights, statistics,
                       model, prompt_version, status, numbers_valid, generated_at
                FROM ai.reports
                {where}
                ORDER BY {SORT_COLUMNS[sort]} {order.upper()}
                LIMIT :limit OFFSET :offset
                """
            ),
            {
                **params,
                "limit": page_size,
                "offset": (page - 1) * page_size,
            },
        )
        .mappings()
        .all()
    )
    return {
        "items": [serialize_report(row) for row in rows],
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }


@router.get("/reports/{report_id:int}")
def get_report(
    report_id: int, user=Depends(require_viewer), db: Session = Depends(get_db)
):
    row = (
        db.execute(
            text(
                """
                SELECT id, report_date, title, summary, highlights, statistics,
                       model, prompt_version, status, numbers_valid, generated_at
                FROM ai.reports WHERE id = :report_id
                """
            ),
            {"report_id": report_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return serialize_report(row)


def report_rows(db):
    return (
        db.execute(
            text(
                """
                SELECT id, report_date, title, summary, status, numbers_valid,
                       model, generated_at
                FROM ai.reports
                ORDER BY report_date DESC
                """
            )
        )
        .mappings()
        .all()
    )


@router.get("/reports/export")
def export_reports(
    format: str = Query(default="csv", pattern="^(csv|pdf)$"),
    user=Depends(require_viewer),
    db: Session = Depends(get_db),
):
    rows = report_rows(db)
    if format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            ["id", "fecha", "titulo", "resumen", "estado", "cifras_validas", "modelo", "generado"]
        )
        for row in rows:
            writer.writerow(
                [
                    row["id"],
                    row["report_date"],
                    row["title"],
                    row["summary"],
                    row["status"],
                    row["numbers_valid"],
                    row["model"],
                    row["generated_at"],
                ]
            )
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=reportes_sismowatch.csv"},
        )
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter, title="Reportes SismoWatch")
    styles = getSampleStyleSheet()
    elements = [Paragraph("Reportes sismicos SismoWatch", styles["Title"]), Spacer(1, 0.2 * inch)]
    data = [["Fecha", "Titulo", "Estado", "Cifras validas"]]
    for row in rows:
        data.append(
            [
                str(row["report_date"]),
                Paragraph(escape(row["title"]), styles["BodyText"]),
                row["status"],
                "si" if row["numbers_valid"] else "no",
            ]
        )
    table = Table(data, colWidths=[1.0 * inch, 3.4 * inch, 1.2 * inch, 1.0 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), "#1f2937"),
                ("TEXTCOLOR", (0, 0), (-1, 0), "#ffffff"),
                ("GRID", (0, 0), (-1, -1), 0.4, "#9ca3af"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(table)
    document.build(elements)
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=reportes_sismowatch.pdf"},
    )
