# Codex Prompt — print-friendly-pdf

## Task

Build a Python tool called `print-friendly-pdf` that converts design-heavy PDFs (dark backgrounds, colored layouts) into print-friendly PDFs. The core goal is ink reduction — pages with dark backgrounds should be lightened so they are actually printable without heavy ink use.

Output is a PDF file. The browser opens it in a new tab with a native print button. Target browser is Chrome.

The tool has two entry points sharing the same core processing logic:
1. A Flask web app for Cloud Run deployment (primary)
2. A local CLI for testing (secondary)

This prompt covers v1 (deterministic baseline) and the backend additions needed for v1.5 (AI-enhanced). The v1.5 frontend is a separate build.

---

## Dependencies

PyMuPDF (fitz), Pillow, Flask, argparse, pathlib, base64, os. No WeasyPrint. No OCR. No external APIs.

---

## File Structure

```
pdf_print_prep/
  core.py           # shared processing logic
  cli.py            # CLI entry point (local testing)
  app.py            # Flask entry point (Cloud Run)
  Dockerfile
  requirements.txt
```

---

## Core Processing Logic (core.py)

All processing functions live here, imported by both cli.py and app.py.

### process_pdf(pdf_bytes, dpi=150, lighten=True, classifications=None) -> bytes

Accepts PDF as bytes. Returns processed PDF as bytes.

`classifications` is an optional list of dicts: `[{"page_index": 0, "background": "dark", "safe_to_lighten": true}, ...]`  
If provided, used instead of corner-sampling heuristic for lightening decisions.  
If None or missing entries for a page, falls back to corner-sampling heuristic for that page.

**Step 1 — Preflight and Format Selection**

- Open PDF from bytes using PyMuPDF
- If document requires authentication and no password provided, raise ValueError with clear message
- Log total page count to stdout
- Per page: run `page.get_text()`; if fewer than 20 characters, log page number as image-dominant. No OCR.
- Compute document-level output format:
  ```python
  all_text = [page.get_text() for page in pdf]
  if len(pdf) == 0: raise ValueError("PDF contains no pages")
  total_chars = sum(len(t) for t in all_text)
  chars_per_page = total_chars / len(pdf)
  fmt = "jpeg" if chars_per_page < 200 else "png"
  ```
- Log format decision and chars_per_page to stdout:
  ```
  Format: PNG (chars_per_page=342)
  ```
  or:
  ```
  Format: JPEG (chars_per_page=47) — gradient/image-heavy document
  ```

**Step 2 — Rasterize**

- Rasterize each page using `page.get_pixmap(dpi=dpi)`
- Convert to Pillow RGB Image
- Composite onto white canvas to eliminate transparency artifacts:
  ```python
  white = Image.new("RGB", img.size, (255, 255, 255))
  white.paste(img)
  img = white
  ```
- Note: does not remove dark backgrounds already painted into the page — handled in Step 3

**Step 3 — Background Detection and Lightening**

- Skip if `lighten=False`
- Per page, determine whether to lighten:
  - If `classifications` provided and entry exists for this page index:
    - Use `safe_to_lighten` and `background` from classification
    - Skip lightening if `safe_to_lighten` is False
    - Skip lightening if `background` is "light"
    - Skip lightening if `background` is "mixed" and `safe_to_lighten` is false
    - Apply lightening if `background` is "dark" or if `background` is "mixed" and `safe_to_lighten` is true
  - Otherwise fall back to corner-sampling heuristic:
    ```python
    w, h = img.size
    corners = [
        img.crop((0, 0, 10, 10)),
        img.crop((w-10, 0, w, 10)),
        img.crop((0, h-10, 10, h)),
        img.crop((w-10, h-10, w, h)),
    ]
    pixels = [p for c in corners for p in list(c.getdata())]
    mean_rgb = sum(sum(p) / 3 for p in pixels) / len(pixels)
    should_lighten = mean_rgb < 80
    ```
- If lightening applies:
  - Build 256-entry LUT:
    ```python
    lut = []
    for i in range(256):
        if i <= 60:
            lut.append(int(220 + (255 - 220) * (1 - i / 60)))
        else:
            lut.append(i)
    ```
  - Apply via `img = img.point(lut * 3)`
  - This is a luminance-based remap — not a full inversion, not histogram-wide autocontrast
- Log per page: whether lightening was applied, and whether classification or heuristic was used

**Step 4 — PDF Reassembly**

- Create new PyMuPDF document: `output_pdf = fitz.open()`
- Per processed page image:
  - Save to bytes buffer:
    ```python
    buf = BytesIO()
    if fmt == "jpeg":
        img.save(buf, format="JPEG", quality=85)
    else:
        img.save(buf, format="PNG")
    img_bytes = buf.getvalue()
    ```
  - Create new page: `page = output_pdf.new_page(width=img.width, height=img.height)`
  - Insert image: `page.insert_image(page.rect, stream=img_bytes)`
- Return: `output_pdf.tobytes()`

**Step 6 — Terminal Summary**

Print on completion:
```
--- print-friendly-pdf complete ---
Pages processed: 54
Format: JPEG (chars_per_page=47)
Lightening applied: pages 1-48, 50-54
Lightening skipped (classification safe_to_lighten=false): page 12
Lightening skipped (light background): page 49
Image-dominant pages (< 20 chars): 3, 7, 22
```

---

### generate_thumbnails(pdf_bytes) -> list[dict]

Lightweight function for v1.5 `/thumbnails` endpoint.

- Open PDF from bytes using PyMuPDF
- Per page: rasterize at low resolution (scale to 150px wide, maintain aspect ratio)
- Convert to JPEG at quality 70
- Encode as base64 string
- Return list: `[{"page_index": 0, "image": "<base64 jpeg>"}, ...]`

---

## Flask Entry Point (app.py)

### POST /convert

- Accept multipart form upload, field name: `pdf`
- Accept optional form field: `classifications` — JSON string, array of per-page classification objects
  - If absent: pass `classifications=None` — heuristic fallback for all pages
  - If present but not valid JSON → return `400 {"error": "classifications must be valid JSON"}`
  - If present but not a list → return `400 {"error": "classifications must be a JSON array"}`
  - If any entry missing `page_index` (integer), `background` (string: "dark", "light", or "mixed"), or `safe_to_lighten` (boolean) → return `400 {"error": "invalid classification entry at index N"}`
  - Duplicate `page_index` entries: last entry in the array wins
  - `background="mixed"` is eligible for lightening only when `safe_to_lighten` is true
- Validate with correct HTTP status codes:
  - No file in request → `400 {"error": "No file uploaded"}`
  - Extension not `.pdf` → `400 {"error": "File must be a PDF"}`
  - File size over 32MB → `400 {"error": "File too large. Maximum size is 32MB."}`
  - Password-protected PDF (caught as ValueError) → `400 {"error": "Password-protected PDFs are not supported"}`
  - Zero-page PDF → `400 {"error": "PDF contains no pages"}`
  - Any other processing failure → `500 {"error": "Processing failed: {message}"}`
- Call `process_pdf(pdf_bytes, dpi=150, lighten=True, classifications=classifications)`
- Return PDF as file download:
  - `Content-Type: application/pdf`
  - `Content-Disposition: inline; filename="{original_stem}_print.pdf"`
- Log processing time per request to stdout

### POST /thumbnails

- Accept multipart form upload, field name: `pdf`
- Validate: file present, `.pdf` extension, size under 32MB — 400 if not
- Call `generate_thumbnails(pdf_bytes)`
- Return JSON with key `"thumbnails"`: `{"thumbnails": [{"page_index": 0, "image": "<base64 jpeg>"}, ...]}`
- Return correct HTTP status codes:
  - No file → `400 {"error": "No file uploaded"}`
  - Extension not `.pdf` → `400 {"error": "File must be a PDF"}`
  - File size over 32MB → `400 {"error": "File too large. Maximum size is 32MB."}`
  - Password-protected or unreadable PDF → `400 {"error": "Password-protected PDFs are not supported"}`
  - Zero-page PDF → `400 {"error": "PDF contains no pages"}`
  - Unexpected failure → `500 {"error": "Processing failed: {message}"}`
- Log processing time to stdout

### CORS

```python
ALLOWED_ORIGIN = "https://print-friendly-pdf.indyri.se"

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
    origin = request.headers.get("Origin", "")
    response = make_response()
    if origin == ALLOWED_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

@app.route("/thumbnails", methods=["OPTIONS"])
def options_thumbnails():
    origin = request.headers.get("Origin", "")
    response = make_response()
    if origin == ALLOWED_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response
```

### Startup

```python
PORT = int(os.environ.get("PORT", 8080))
app.run(host="0.0.0.0", port=PORT)
```

---

## CLI Entry Point (cli.py)

```
python cli.py input.pdf [--dpi 150] [--no-lighten]
```

- Read PDF from file path
- Call `process_pdf()` with flags, `classifications=None`
- Write output PDF to `{input_stem}_print.pdf` in same directory as input
- Print terminal summary on completion

**Error handling:**
- Missing file → exit with message, non-zero return code
- Authentication-required PDF → exit with message, non-zero return code
- Per-page error → log page number and error, abort immediately (fail-fast; do not produce partial output)

---

## Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["python", "app.py"]
```

---

## requirements.txt

```
pymupdf
pillow
flask
```

---

## Important Notes for Codex

- CLI and Flask app share all processing logic from core.py — do not duplicate
- Output is a PDF assembled from processed page images using PyMuPDF — not HTML
- Format selection is document-level (one format for the whole PDF), not per-page
- PNG is the default for text-heavy documents; JPEG for gradient/image-heavy documents
- The chars_per_page threshold of 200 is provisional — QA phase will validate and may adjust it
- All user-caused errors return 400; only unexpected processing failures return 500
- CORS is restricted to the Vercel frontend domain only — not wildcard
- No Anthropic API calls anywhere in this codebase — AI classification happens in browser JS only
- Target browser is Chrome — do not add cross-browser print workarounds
- The `classifications` parameter in `process_pdf()` is how v1 becomes v1.5-ready — it must be implemented correctly and tested with both None and a populated array
- `/thumbnails` is a lightweight endpoint — it must not run the full processing pipeline; rasterize at low res only
- The two endpoints are independent and stateless — no shared state between a `/thumbnails` call and a subsequent `/convert` call

---

## What This Tool Does Not Do (v1)

- Does not perform OCR
- Does not call any external AI API — that happens in the browser in v1.5
- Does not support password-protected PDFs
- Does not preserve a searchable text layer in the output PDF
- Does not guarantee removal of all dark backgrounds — heuristic targets near-uniform dark fills via corner sampling; dark chart regions may be partially affected
- Does not support files over 32MB
- Does not guarantee correct behavior in browsers other than Chrome
