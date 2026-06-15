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
app.config["MAX_CONTENT_LENGTH"] = MAX_SIZE
app.config["MAX_FORM_MEMORY_SIZE"] = MAX_SIZE
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
    """Shared upload validation. Returns (pdf_bytes, stem, err)."""

    print("CONTENT_TYPE:", request.content_type, flush=True)
    print("CONTENT_LENGTH:", request.content_length, flush=True)
    print("FORM KEYS:", list(request.form.keys()), flush=True)
    print("FILE KEYS:", list(request.files.keys()), flush=True)

    if "pdf" not in request.files:
        raw = request.get_data(cache=True)
        print("RAW LENGTH:", len(raw), flush=True)
        print("RAW FIRST 500:", raw[:500], flush=True)
        return None, None, (jsonify(error="No file uploaded"), 400)

    f = request.files["pdf"]

    print("PDF FILENAME:", f.filename, flush=True)
    print("PDF CONTENT_TYPE:", f.content_type, flush=True)

    if not f.filename.lower().endswith(".pdf"):
        return None, None, (jsonify(error="File must be a PDF"), 400)

    data = f.read()

    print("PDF BYTE LENGTH:", len(data), flush=True)

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
