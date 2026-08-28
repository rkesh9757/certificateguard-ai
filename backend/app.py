"""
app.py

CertificateGuard AI — backend API.

Endpoints:
  GET  /api/health                 -> liveness check
  POST /api/verify/manual          -> verify hand-entered certificate details
  POST /api/verify/upload          -> OCR + verify an uploaded certificate image

Run locally:
  pip install -r requirements.txt
  python app.py
  (server starts on http://localhost:5000)

Note: pytesseract needs the Tesseract OCR binary installed separately
on the machine — see ocr_engine.py for install instructions.
"""

import random
import string
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS

from database import init_db
from ocr_engine import run_ocr, extract_fields
from verification_engine import run_verification

app = Flask(__name__)
CORS(app)  # allow the frontend (served from a different origin) to call this API

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _make_report_id() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"CG-{suffix}"


def _build_response(fields: dict, result: dict) -> dict:
    return {
        "reportId": _make_report_id(),
        "timestamp": datetime.now().isoformat(),
        "fields": fields,
        "score": result["score"],
        "verdict": result["verdict"],   # "genuine" | "suspicious" | "fake"
        "checks": result["checks"],
    }


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/verify/manual", methods=["POST"])
def verify_manual():
    body = request.get_json(silent=True) or {}

    fields = {
        "candidateName": (body.get("candidateName") or "").strip(),
        "institution": (body.get("institution") or "").strip(),
        "certId": (body.get("certId") or "").strip(),
        "issueDate": (body.get("issueDate") or "").strip(),
        "course": (body.get("course") or "").strip(),
    }

    if not (fields["candidateName"] and fields["institution"] and fields["certId"]):
        return jsonify({
            "error": "Please provide at least candidate name, institution and certificate ID."
        }), 400

    result = run_verification(fields, mode="manual")
    return jsonify(_build_response(fields, result))


@app.route("/api/verify/upload", methods=["POST"])
def verify_upload():
    if "file" not in request.files:
        return jsonify({"error": "No file field in the request."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not _allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type. Use JPG, PNG or WEBP."}), 400

    image_bytes = file.read()

    try:
        text, ocr_confidence, image_dims = run_ocr(image_bytes)
    except Exception as exc:  # pytesseract / PIL errors
        return jsonify({"error": f"Could not read this image: {exc}"}), 422

    fields = extract_fields(text)
    result = run_verification(
        fields,
        mode="upload",
        ocr_confidence=ocr_confidence,
        image_dims=image_dims,
    )
    return jsonify(_build_response(fields, result))


@app.errorhandler(413)
def too_large(_err):
    return jsonify({"error": "File too large. Maximum size is 8 MB."}), 413


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)