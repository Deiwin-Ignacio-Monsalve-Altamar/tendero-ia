from flask import Blueprint, jsonify, request
import math

from app.services.product_service import ProductService
from app.utils.error_handlers import AppError, NotFoundError

products_bp = Blueprint("products_bp", __name__)


def _business_for_phone(phone):
    if not isinstance(phone, str) or not phone.strip():
        return None
    return ProductService.get_or_create_business(phone.strip())


def _json_payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AppError("Se requiere un objeto JSON", 400, "INVALID_PAYLOAD")
    return data


@products_bp.route("", methods=["GET"])
def list_products():
    business = _business_for_phone(request.args.get("phone"))
    if business is None:
        raise AppError("phone es requerido", 400, "INVALID_PAYLOAD")
    products = ProductService.list_products(business.id)
    return jsonify({"success": True, "data": [product.to_dict() for product in products]}), 200


@products_bp.route("", methods=["POST"])
def create_product():
    data = _json_payload()
    name = data.get("name")
    aliases = data.get("aliases", "")
    if not isinstance(name, str) or not name.strip() or not isinstance(aliases, str):
        raise AppError("name y aliases deben ser texto", 400, "INVALID_PAYLOAD")
    if data.get("price") is None:
        raise AppError("phone, name y price son requeridos", 400, "INVALID_PAYLOAD")
    business = _business_for_phone(data.get("phone"))
    if business is None:
        raise AppError("phone, name y price son requeridos", 400, "INVALID_PAYLOAD")
    try:
        price = float(data["price"])
        if not math.isfinite(price) or price < 0:
            raise ValueError
    except (TypeError, ValueError):
        raise AppError("price debe ser un número no negativo", 400, "INVALID_PRICE")
    product = ProductService.create_product(
        business.id, name.strip(), price, aliases
    )
    return jsonify({"success": True, "data": product.to_dict()}), 201


@products_bp.route("/<int:product_id>", methods=["PUT"])
def update_product(product_id):
    data = _json_payload()
    business = _business_for_phone(data.get("phone"))
    if business is None:
        raise AppError("phone es requerido", 400, "INVALID_PAYLOAD")
    if "name" in data and (not isinstance(data["name"], str) or not data["name"].strip()):
        raise AppError("name debe ser texto no vacío", 400, "INVALID_PAYLOAD")
    if "aliases" in data and not isinstance(data["aliases"], str):
        raise AppError("aliases debe ser texto", 400, "INVALID_PAYLOAD")
    if "price" in data:
        try:
            data["price"] = float(data["price"])
            if not math.isfinite(data["price"]) or data["price"] < 0:
                raise ValueError
        except (TypeError, ValueError):
            raise AppError("price debe ser un número no negativo", 400, "INVALID_PRICE")
    product = ProductService.update_product(
        business.id,
        product_id,
        name=data.get("name"),
        price=data.get("price"),
        aliases=data.get("aliases"),
    )
    if product is None:
        raise NotFoundError("Producto no encontrado para este teléfono")
    return jsonify({"success": True, "data": product.to_dict()}), 200


@products_bp.route("/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    data = request.get_json(silent=True)
    if data is not None and not isinstance(data, dict):
        raise AppError("Se requiere un objeto JSON", 400, "INVALID_PAYLOAD")
    data = data or {}
    business = _business_for_phone(data.get("phone") or request.args.get("phone"))
    if business is None:
        raise AppError("phone es requerido", 400, "INVALID_PAYLOAD")
    if not ProductService.delete_product(business.id, product_id):
        raise NotFoundError("Producto no encontrado para este teléfono")
    return jsonify({"success": True, "data": {"message": "Product deleted"}}), 200
