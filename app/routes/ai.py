from flask import Blueprint, request, jsonify
from app.services.ai_service import generate_invoice_description
ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")


@ai_bp.route("/generate-description", methods=["POST"])
def generate_description():
    """
    API endpoint to generate a professional line item description.
    Accepts JSON: { "service_name": str, "context": str, "tone": str }
    """
    data = request.get_json() or {}
    service_name = data.get("service_name", "").strip()
    context = data.get("context", "").strip()
    tone = data.get("tone", "Professional").strip()
    if not service_name:
        return jsonify(
            {"success": False, "message": "Service name is required."}), 400
    result = generate_invoice_description(service_name, context, tone)
    return jsonify(result)
