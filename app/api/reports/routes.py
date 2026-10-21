from flask import Blueprint, jsonify, request, send_file

from app.services.report_service import ReportService
from app.utils.error_handlers import AppError

reports_bp = Blueprint("reports_bp", __name__)


@reports_bp.route("/sales", methods=["GET"])
def get_sales_report():
    phone = request.args.get("phone")
    if not phone:
        raise AppError("phone es requerido", 400, "INVALID_PAYLOAD")
    data = ReportService.get_sales_summary(
        phone,
        request.args.get("start_date"),
        request.args.get("end_date"),
    )
    return jsonify({
        "success": True,
        "data": data,
        "message": "Reporte obtenido exitosamente",
    }), 200


@reports_bp.route("/sales/pdf", methods=["GET"])
def get_sales_pdf():
    phone = request.args.get("phone")
    if not phone:
        raise AppError("phone es requerido", 400, "INVALID_PAYLOAD")
    buffer = ReportService.generate_sales_pdf(
        phone,
        request.args.get("start_date"),
        request.args.get("end_date"),
    )
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"reporte_ventas_{phone}.pdf",
    )
