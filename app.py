from __future__ import annotations

import json
import os
import time
from io import BytesIO
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, make_response, request, send_file

from pdf_print_prep.core import generate_thumbnails, process_pdf


ALLOWED_ORIGIN = "https://print-friendly-pdf.indyri.se"
MAX_FILE_BYTES = 32 * 1024 * 1024

app = Flask(__name__)


@app.after_request
def apply_cors(response):
    origin = request.headers.get("Origin", "")
    if origin == ALLOWED_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/convert", methods=["OPTIONS"])
def options_convert():
    return make_response()


@app.route("/thumbnails", methods=["OPTIONS"])
def options_thumbnails():
    return make_response()


def _json_error(message: str, status_code: int):
    response = jsonify({"error": message})
    response.status_code = status_code
    return response


def _read_pdf_upload() -> tuple[bytes | None, str | None, Any]:
    if "pdf" not in request.files:
        return None, None, _json_error("No file uploaded", 400)

    upload = request.files["pdf"]
    filename = upload.filename or "upload.pdf"
    if Path(filename).suffix.lower() != ".pdf":
        return None, None, _json_error("File must be a PDF", 400)

    pdf_bytes = upload.read()
    if len(pdf_bytes) > MAX_FILE_BYTES:
        return (
            None,
            None,
            _json_error("File too large. Maximum size is 32MB.", 400),
        )
    return pdf_bytes, filename, None


def _validate_classifications(raw: str | None) -> tuple[list[dict[str, Any]] | None, Any]:
    if raw is None or raw == "":
        return None, None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None, _json_error("classifications must be valid JSON", 400)

    if not isinstance(parsed, list):
        return None, _json_error("classifications must be a JSON array", 400)

    valid_backgrounds = {"dark", "light", "mixed"}
    for index, entry in enumerate(parsed):
        if not isinstance(entry, dict):
            return None, _json_error(f"invalid classification entry at index {index}", 400)
        if not isinstance(entry.get("page_index"), int):
            return None, _json_error(f"invalid classification entry at index {index}", 400)
        if entry.get("background") not in valid_backgrounds:
            return None, _json_error(f"invalid classification entry at index {index}", 400)
        if not isinstance(entry.get("safe_to_lighten"), bool):
            return None, _json_error(f"invalid classification entry at index {index}", 400)

    return parsed, None


def _processing_error(exc: Exception):
    message = str(exc)
    if "Password-protected PDFs are not supported" in message:
        return _json_error("Password-protected PDFs are not supported", 400)
    if "PDF contains no pages" in message:
        return _json_error("PDF contains no pages", 400)
    if "PDF could not be opened" in message:
        return _json_error("Password-protected PDFs are not supported", 400)
    return _json_error(f"Processing failed: {message}", 500)


@app.route("/convert", methods=["POST"])
def convert():
    started = time.perf_counter()
    pdf_bytes, filename, upload_error = _read_pdf_upload()
    if upload_error:
        return upload_error

    classifications, classification_error = _validate_classifications(
        request.form.get("classifications")
    )
    if classification_error:
        return classification_error

    try:
        output_bytes = process_pdf(
            pdf_bytes,
            dpi=150,
            lighten=True,
            crop=True,
            classifications=classifications,
        )
    except Exception as exc:
        return _processing_error(exc)
    finally:
        print(f"/convert completed in {time.perf_counter() - started:.2f}s")

    original_stem = Path(filename or "upload").stem
    return send_file(
        BytesIO(output_bytes),
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"{original_stem}_print.pdf",
    )


@app.route("/thumbnails", methods=["POST"])
def thumbnails():
    started = time.perf_counter()
    pdf_bytes, _filename, upload_error = _read_pdf_upload()
    if upload_error:
        return upload_error

    try:
        thumbnail_data = generate_thumbnails(pdf_bytes)
    except Exception as exc:
        return _processing_error(exc)
    finally:
        print(f"/thumbnails completed in {time.perf_counter() - started:.2f}s")

    return jsonify({"thumbnails": thumbnail_data})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
