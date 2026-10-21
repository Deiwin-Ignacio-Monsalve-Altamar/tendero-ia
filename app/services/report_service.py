from datetime import date, datetime, time
from io import BytesIO
from typing import Optional
from xml.sax.saxutils import escape

from app.extensions import db
from app.models.business import Business
from app.models.transaction import Transaction, TransactionItem
from app.utils.error_handlers import AppError, NotFoundError


class ReportService:
    @staticmethod
    def _parse_date(value: Optional[str], field_name: str) -> Optional[date]:
        if value is None:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (TypeError, ValueError) as error:
            raise AppError(
                f"{field_name} debe tener formato YYYY-MM-DD",
                400,
                "INVALID_DATE",
            ) from error

    @staticmethod
    def _format_cop(amount: float) -> str:
        formatted = f"{amount:,.0f}".replace(",", ".")
        return f"$ {formatted} COP"

    @staticmethod
    def get_sales_summary(
        phone: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        business = Business.query.filter_by(phone_number=phone).first()
        if business is None:
            raise NotFoundError("No existe un negocio asociado al teléfono")

        parsed_start = ReportService._parse_date(start_date, "start_date")
        parsed_end = ReportService._parse_date(end_date, "end_date")
        if parsed_start and parsed_end and parsed_start > parsed_end:
            raise AppError(
                "start_date no puede ser posterior a end_date", 400, "INVALID_DATE_RANGE"
            )

        query = db.session.query(Transaction).filter(
            Transaction.business_id == business.id,
            Transaction.status == "CONFIRMED",
        )
        if parsed_start:
            query = query.filter(
                Transaction.created_at >= datetime.combine(parsed_start, time.min)
            )
        if parsed_end:
            query = query.filter(
                Transaction.created_at <= datetime.combine(parsed_end, time(23, 59, 59))
            )
        transactions = query.order_by(Transaction.created_at.asc(), Transaction.id.asc()).all()

        items_by_transaction = {}
        items_query = (
            db.session.query(TransactionItem)
            .join(Transaction, Transaction.id == TransactionItem.transaction_id)
            .filter(
                Transaction.business_id == business.id,
                Transaction.status == "CONFIRMED",
            )
        )
        if parsed_start:
            items_query = items_query.filter(
                Transaction.created_at >= datetime.combine(parsed_start, time.min)
            )
        if parsed_end:
            items_query = items_query.filter(
                Transaction.created_at <= datetime.combine(parsed_end, time(23, 59, 59))
            )
        for item in items_query.order_by(TransactionItem.id.asc()).all():
            items_by_transaction.setdefault(item.transaction_id, []).append(item.to_dict())

        transaction_data = [
            {
                "id": transaction.id,
                "business_id": transaction.business_id,
                "phone_number": transaction.phone_number,
                "total_amount": transaction.total_amount,
                "status": transaction.status,
                "raw_input": transaction.raw_input,
                "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
                "items": items_by_transaction.get(transaction.id, []),
            }
            for transaction in transactions
        ]
        return {
            "business": business.to_dict(),
            "filters": {"start_date": start_date, "end_date": end_date},
            "total_revenue": sum(transaction.total_amount for transaction in transactions),
            "total_sales_count": len(transactions),
            "transactions": transaction_data,
        }

    @staticmethod
    def generate_sales_pdf(
        phone: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> BytesIO:
        summary = ReportService.get_sales_summary(phone, start_date, end_date)

        # Loaded lazily so JSON reporting remains available when the PDF extra is absent.
        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except ImportError as error:
            raise AppError(
                "La generación de PDF requiere ReportLab instalado",
                500,
                "PDF_DEPENDENCY_MISSING",
            ) from error

        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title="Reporte de Ventas - Tendero IA",
        )
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            textColor=colors.HexColor("#17324D"),
            spaceAfter=8,
        ))
        styles.add(ParagraphStyle(
            name="TableCell",
            parent=styles["BodyText"],
            fontSize=7.5,
            leading=9,
            alignment=TA_LEFT,
        ))
        styles.add(ParagraphStyle(
            name="TableCellRight",
            parent=styles["TableCell"],
            alignment=TA_RIGHT,
        ))

        story = [
            Paragraph("Reporte de Ventas - Tendero IA", styles["ReportTitle"]),
            Paragraph(f"<b>Teléfono:</b> {escape(phone)}", styles["BodyText"]),
            Paragraph(
                "<b>Rango:</b> "
                f"{escape(start_date or 'Todas las fechas')} — {escape(end_date or 'Todas las fechas')}",
                styles["BodyText"],
            ),
            Paragraph(
                f"<b>Emitido:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                styles["BodyText"],
            ),
            Spacer(1, 5 * mm),
            Paragraph(
                f"<b>Total acumulado:</b> {ReportService._format_cop(summary['total_revenue'])}"
                f" &nbsp;&nbsp; <b>Cantidad de ventas:</b> {summary['total_sales_count']}",
                styles["BodyText"],
            ),
            Spacer(1, 5 * mm),
        ]

        table_data = [["ID", "Fecha", "Ítems", "Método", "Total"]]
        for transaction in summary["transactions"]:
            item_lines = []
            for item in transaction["items"]:
                item_name = escape(str(item.get("canonical_name") or item.get("raw_name") or "Producto"))
                item_lines.append(
                    f"{item['quantity']} x {item_name}"
                    f" — {ReportService._format_cop(item['subtotal'])}"
                )
            items_paragraph = Paragraph("<br/>".join(item_lines) or "—", styles["TableCell"])
            created_at = transaction["created_at"]
            display_date = created_at.replace("T", " ")[:19] if created_at else "—"
            table_data.append([
                str(transaction["id"]),
                Paragraph(escape(display_date), styles["TableCell"]),
                items_paragraph,
                "No especificado",
                Paragraph(
                    ReportService._format_cop(transaction["total_amount"]),
                    styles["TableCellRight"],
                ),
            ])

        report_table = Table(
            table_data,
            colWidths=[10 * mm, 34 * mm, 72 * mm, 26 * mm, 32 * mm],
            repeatRows=1,
            hAlign="LEFT",
        )
        report_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324D")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("LEADING", (0, 0), (-1, -1), 10),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F5F8")]),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CCD4DC")),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(report_table)
        document.build(story)
        buffer.seek(0)
        return buffer
