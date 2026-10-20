import logging

from flask import jsonify
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from app.extensions import db

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, message, status_code=400, error_code="BAD_REQUEST", details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details


class NotFoundError(AppError):
    def __init__(self, message="Recurso no encontrado", details=None):
        super().__init__(message, 404, "NOT_FOUND", details)


class UnauthorizedTenantError(AppError):
    def __init__(self, message="No autorizado para este recurso", details=None):
        super().__init__(message, 403, "UNAUTHORIZED_TENANT", details)


class RateLimitError(AppError):
    def __init__(self, message="Límite de solicitudes excedido con Gemini", details=None):
        super().__init__(message, 429, "GEMINI_RATE_LIMIT", details)


def _error_response(status_code, error_code, message, details=None):
    return jsonify({
        "success": False,
        "error": {
            "status_code": status_code,
            "error_code": error_code,
            "message": message,
            "details": details,
        },
    }), status_code


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(error):
        return _error_response(
            error.status_code, error.error_code, error.message, error.details
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return _error_response(
            error.code or 500,
            error.name.upper().replace(" ", "_"),
            error.description,
        )

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error):
        db.session.rollback()
        logger.error(
            "Database operation failed",
            exc_info=(type(error), error, error.__traceback__),
        )
        return _error_response(500, "DATABASE_ERROR", "Error interno de base de datos")

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        logger.error(
            "Unhandled application error",
            exc_info=(type(error), error, error.__traceback__),
        )
        return _error_response(
            500, "INTERNAL_SERVER_ERROR", "Error interno del servidor"
        )
