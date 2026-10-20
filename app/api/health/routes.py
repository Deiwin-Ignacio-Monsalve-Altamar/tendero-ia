from flask import Blueprint, jsonify

health_bp = Blueprint('health_bp', __name__)

@health_bp.route('/health', methods=['GET'])
def health():
    return jsonify({"success": True, "data": {"status": "ok"}}), 200
