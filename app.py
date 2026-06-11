"""print-friendly-pdf Flask app — Cloud Run entry point."""
import json
import os
import time
from pathlib import Path

from flask import Flask, request, jsonify, make_response, send_file
from io import BytesIO

from pdf_print_prep.core import process_pdf, generate_thumbnails

app = Flask(__name__)

MAX_SIZE = 32 * 1024 * 1024
ALLOWED_ORIGIN = "https://print-friendly-pdf.indyri.se"


def _cors(response):
    origin = request.headers.get("Origin", "")
    if origin == ALLOWED_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.after_request
def apply_cors(response):
    return _cors(response)


@app.route("/convert", methods=["OPTIONS"])
@app.route("/thumbnails", methods=["OPTIONS"])
def options():
    return _cors(make_response())


def _validate_upload():
    """Shared upload validation. Returns (pdf_bytes, stem) or raises with
    a (response, status) tuple via ValueError carrying the response."""
    if "pdf" not in request.files:
        return None, None, (jsonify(error="No file uploaded"), 400)
    f = request.files["pdf"]
    if not f.filename.lower().endswith(".pdf"):
        return None, None, (jsonify(error="File must be a PDF"), 400)
    data = f.read()
    if len(data) > MAX_SIZE:
        return None, None, (jsonify(error="File too large. Maximum size is 32MB."), 400)
    return data, Path(f.filename).stem, None


def _parse_classifications():
    raw = request.form.get("classifications")
    if raw is None:
        return None, None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None, (jsonify(error="classifications must be valid JSON"), 400)
    if not isinstance(parsed, list):
        return None, (jsonify(error="classifications must be a JSON array"), 400)
    for n, e in enumerate(parsed):
        if (not isinstance(e, dict)
                or not isinstance(e.get("page_index"), int)
                or e.get("background") not in ("dark", "light", "mixed")
                or not isinstance(e.get("safe_to_invert"), bool)):
            return None, (jsonify(error=f"invalid classification entry at index {n}"), 400)
    return parsed, None


@app.route("/convert", methods=["POST"])
def convert():
    start = time.time()
    data, stem, err = _validate_upload()
    if err:
        return err
    classifications, err = _parse_classifications()
    if err:
        return err
    try:
        out = process_pdf(data, dpi=150, invert=True,
                          classifications=classifications)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:
        return jsonify(error=f"Processing failed: {e}"), 500
    print(f"/convert: {time.time() - start:.1f}s")
    return send_file(BytesIO(out), mimetype="application/pdf",
                     download_name=f"{stem}_print.pdf")


@app.route("/thumbnails", methods=["POST"])
def thumbnails():
    start = time.time()
    data, _, err = _validate_upload()
    if err:
        return err
    try:
        thumbs = generate_thumbnails(data)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:
        return jsonify(error=f"Processing failed: {e}"), 500
    print(f"/thumbnails: {time.time() - start:.1f}s")
    return jsonify(thumbnails=thumbs)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
