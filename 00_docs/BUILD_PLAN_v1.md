> **SUPERSEDED by BUILD_PLAN_v2.md (2026-06-10)** — kept for project history.

# Build Plan — print-friendly-pdf

**Date:** 2026-06-07  
**Status:** Approved for implementation

---

## Goal

A public-facing tool that converts design-heavy PDFs into print-friendly PDFs. Users upload a PDF, the tool lightens dark backgrounds, and the browser opens the result in a new tab with a familiar print button.

**Primary success metric:** A sample design-heavy PDF prints without heavy ink use, charts remain recognizable, and the live URL is portfolio-presentable.

---

## Time Tracking (standing instruction)

Track the following for every phase throughout the build. This is a portfolio proof-of-work artifact, not productivity theater.

- Start and end time per phase
- Biggest blocker encountered
- What caused rework, if anything
- What you would change in the spec next time

A simple text log alongside the code is sufficient.

---

## Product Versions

**v1 — Deterministic baseline**  
No AI. No API key required. Works for all users immediately.

**v1.5 — AI-enhanced (additive)**  
User supplies their own Anthropic key in the UI. Browser uses lightweight thumbnails to call Anthropic directly for classification. Backend never receives the key. Same pattern as escape-room-builder.indyri.se.

Build v1 to completion and live before starting v1.5.

---

## Constraints

- Python only for processing
- No OCR, no WeasyPrint, no vision API calls from backend
- No hosted AI mode — BYO API only for v1.5
- Browser uploads directly to Cloud Run — not proxied through Vercel serverless functions
- v1 file size ceiling: 32MB hard limit, warn above 25MB
- Synchronous request/response in both v1 and v1.5
- GCP billing budget must be confirmed active before Cloud Run URL is made public
- User API key never touches the backend in v1.5
- v1 is optimized for Chrome — cross-browser print behavior is explicitly out of scope

---

## Mandated Build Sequence

Follow this order exactly. Do not move to the next step until the current one is confirmed working.

1. Get `core.py` working locally via CLI on a sample design-heavy PDF
2. Test on 5 representative pages before running the full PDF
3. Validate format heuristic threshold — benchmark chars_per_page on a sample design-heavy PDF and one text-heavy PDF
4. Wrap in Flask, test locally
5. Containerize, test Docker locally against a sample design-heavy PDF
6. Deploy to Cloud Run, confirm end-to-end
7. Build Vercel frontend
8. Confirm GCP billing budget active before making URL public
9. Do not touch v1.5 until v1 is live and you have real output examples

---

## v1 Phases

### Phase 0 — Infrastructure Preflight

**GitHub**
- Create public repo `indyrise/print-friendly-pdf` on GitHub
- Add `.gitignore` (Python template), `README.md` (placeholder), `.env.example` (empty for now — no secrets in v1)
- Clone locally

**GoDaddy**
- Log into GoDaddy DNS for `indyri.se`
- Add CNAME record: `print-friendly-pdf` → `cname.vercel-dns.com`
- Note: CNAME can be created now; it will only resolve once the Vercel deployment exists in Phase 9

**Vercel**
- Vercel project creation happens in Phase 9 — domain hookup is intentionally split
- When creating the Vercel project in Phase 9, add `print-friendly-pdf.indyri.se` as a custom domain in project settings

**GCP**
- Confirm a GCP project exists with billing enabled — required before Cloud Run deployment in Phase 7
- Do not enable Cloud Run API yet — defer to Phase 7

**Exit criteria:** Repo cloned locally with `.gitignore`, `README.md`, and `.env.example` committed; GoDaddy CNAME record saved; GCP project confirmed with billing active.

---

### Phase 1 — Preflight, Ingestion, and Format Selection

- Accept PDF path via argparse for local testing; accept multipart upload in Flask app
- Validate file exists and is a PDF
- If document requires authentication and no password provided, exit with clear message
- Log total page count
- Per page: run `page.get_text()`; if fewer than 20 characters, log as image-dominant. No OCR.
- Compute format selection:
  - Sum total characters across all pages from already-extracted `get_text()` data
  - Divide by page count to get chars_per_page
  - If chars_per_page < 200: fmt = "jpeg" (gradient/image-heavy — file size reduction acceptable)
  - If chars_per_page >= 200: fmt = "png" (text-dominant — sharpness preserved)
  - Log format decision and chars_per_page to terminal
  - Threshold of 200 is provisional — tune after Phase 11 QA

**Exit criteria:** Clean open on valid PDF; clear errors on authenticated or missing file; format decision logged correctly on sample design-heavy PDF (expected: JPEG) and a text-heavy PDF (expected: PNG). The mandated 5-page test (build sequence step 2) is manual inspection of 5 representative pages in the full output — not a code-enforced constraint; no `--pages` flag required.

---

### Phase 2 — Rasterization

- Rasterize each page using `page.get_pixmap(dpi=dpi)`, convert to Pillow RGB Image
- Composite onto white canvas to eliminate transparency artifacts
- Note: does not remove dark backgrounds already painted into the page — handled in Phase 3

**Exit criteria:** One Pillow Image per page; no crashes on mixed page sizes or orientations.

---

### Phase 3 — Background Detection and Lightening

- Skip entirely if `--no-lighten` set
- Sample four corners (10x10px); compute mean RGB
- If mean RGB below 80 (dark background detected):
  - Build 256-entry LUT: values 0–60 map linearly to 220–255; values 61–255 map to themselves
  - Apply via `img.point(lut * 3)` across R, G, B channels
  - This is a luminance-based remap — not a full inversion, not histogram-wide autocontrast
- Log per page whether lightening was applied
- Note: heuristic may miss centered dark panels or content vs background distinctions — this is the limitation v1.5 addresses

**Exit criteria:** Dark-background pages visibly lighter; light pages unchanged; `--no-lighten` bypasses entirely.

---

### Phase 4 — PDF Reassembly

- Create new PyMuPDF document
- Per processed page image:
  - Save to bytes buffer using format determined in Phase 1 (JPEG quality 85 or PNG)
  - Create new page matching image dimensions
  - Insert image as full-page content via `page.insert_image(page.rect, stream=img_bytes)`
- Write to bytes buffer and return via `output_pdf.tobytes()`

**Exit criteria:** Output PDF opens correctly in Chrome; pages match input page count; no crashes.

---

### Phase 6 — Flask App (POST /convert)

- Accept multipart PDF upload, field name: `pdf`
- Accept optional JSON field: `classifications` — array of per-page `{page_index, background, safe_to_lighten}` (used by v1.5)
  - If absent: heuristic fallback for all pages
  - If present but not valid JSON, not a list, or any entry missing `page_index` (integer), `background` ("dark", "light", or "mixed"), or `safe_to_lighten` (boolean): return 400
  - Duplicate `page_index` entries: last entry wins
  - `background="mixed"` entries eligible for lightening only when `safe_to_lighten` is true
- Validate with correct HTTP status codes:
  - No file uploaded → 400 with clear message
  - Extension not `.pdf` → 400 with clear message
  - File size over 32MB → 400 with clear message
  - Password-protected PDF → 400 with clear message
  - Zero-page PDF → 400 with clear message
  - Processing failure → 500 with JSON error message
- Run full processing pipeline: dpi=150, lighten=True, format via heuristic
- Apply classifications if valid and present; fall back to corner-sampling heuristic for any page missing a classification entry
- Return PDF as file response:
  - `Content-Type: application/pdf`
  - `Content-Disposition: inline; filename="{original_stem}_print.pdf"`
- Log processing time per request to stdout
- Read PORT from environment, default 8080
- CORS: restrict `Access-Control-Allow-Origin` to `https://print-friendly-pdf.indyri.se` only — OPTIONS preflight responses apply the same origin restriction as normal responses
- Handle OPTIONS preflight for both `/convert` and `/thumbnails` with origin-restricted headers

**Exit criteria:** All error codes return correct HTTP status; upload → processing → PDF download works end to end in Chrome; classifications field accepted and ignored gracefully when not provided.

---

### Phase 7 — Dockerfile and Cloud Run

- Base: `python:3.11-slim`
- No system-level MuPDF dependency — PyMuPDF wheels are self-contained since v1.18; `pip install pymupdf` handles it
- `pip install pymupdf pillow flask`
- `EXPOSE 8080`, `CMD ["python", "app.py"]`
- **Test locally with Docker against a sample design-heavy PDF before proceeding** — Docker build friction is a known risk; resolve locally before Cloud Run deployment
- Cloud Run configuration:
  - Max instances: 2
  - Min instances: 0
  - Request concurrency: 1
  - Timeout: 300 seconds
  - Memory: 1GB
  - Dedicated least-privilege service account

**Exit criteria:** Local Docker run accepts a sample design-heavy PDF and returns correct PDF output; Cloud Run deployment live and tested end to end.

---

### Phase 8 — GCP Billing Controls (hard prerequisite before URL goes public)

- Create monthly budget in GCP Billing console: $20 cap
- Alert at 50%: email notification to project owner
- Alert at 100%: configure billing-disable automation workflow via Cloud Pub/Sub + Cloud Function (not automatic by default — must be set up explicitly)
- Document in README: billing disable will take the service offline

**Exit criteria:** Budget confirmed active and automation workflow tested before public URL is shared.

---

### Phase 9 — Vercel Frontend (v1)

- Single static HTML/JS page — no Vercel serverless functions in file handling path
- Browser uploads PDF directly to Cloud Run URL
- UI:
  - Drag-and-drop or file picker
  - Client-side size check: warn above 25MB, block above 32MB with clear message
  - Processing spinner: "Converting — this may take 1-2 minutes for large PDFs"
  - On success: PDF opens in new browser tab (Chrome)
  - On error: clear user-facing message mapped from HTTP status code
- Cloud Run URL stored as JS constant in frontend
- Claude handles frontend HTML/JS artifact

**Exit criteria:** Upload → spinner → PDF opens in new tab in Chrome; all error states show clear messages; no file routing through Vercel functions.

---

### Phase 10 — Public Repo and Subdomain

- Push to `indyrise/print-friendly-pdf`, public
- README: what the tool does, live URL, known limitations (dark chart risk, 32MB ceiling, billing disable risk, Chrome-first), local CLI usage instructions
- CNAME in GoDaddy: `print-friendly-pdf.indyri.se` → Vercel deployment URL

**Exit criteria:** Live URL resolves; tool works end to end; README portfolio-presentable.

---

### Phase 11 — QA (v1)

Run on 5 representative pages of a sample design-heavy PDF:
- Dark full-page background
- Chart-heavy page
- Text-heavy page (check PNG sharpness — small text must be clearly readable)
- Mixed layout
- Image-dominant page

Also run on one text-heavy PDF to validate format heuristic:
- Confirm chars_per_page >= 200 triggers PNG
- Confirm PNG output is visibly sharper than JPEG would be on text pages

Check: ink reduction in Chrome print preview, charts recognizable, PDF opens correctly in browser tab.

If chart damage unacceptable: rerun with `--no-lighten`, document tradeoff.
If format threshold needs adjustment: update threshold, re-run, document new value in ADR.

**Exit criteria:** Tool ships with known behavior documented; format heuristic validated on at least two document types.

---

## v1.5 Phases (start only after v1 is live with real output examples)

### Phase 12 — Cloud Run v1.5 Endpoint

Add one new lightweight endpoint alongside existing `/convert`:

**POST /thumbnails**
- Accept multipart PDF upload, field name: `pdf`
- Validate with correct HTTP status codes:
  - No file → 400
  - Extension not `.pdf` → 400
  - File size over 32MB → 400
  - Password-protected or unreadable PDF → 400
  - Zero-page PDF → 400
  - Unexpected processing failure → 500
- Rasterize each page at low resolution (150px wide, maintain aspect ratio) using PyMuPDF
- Convert each to JPEG at quality 70 (classification quality, not print quality)
- Return JSON with key `"thumbnails"`: `{"thumbnails": [{"page_index": 0, "image": "<base64 jpeg>"}, ...]}`
- This is a lightweight endpoint — fast, low memory, not the full pipeline
- Log processing time to stdout

**`/convert` update for v1.5**
- Already accepts optional `classifications` JSON field (built in Phase 6)
- No changes needed to `/convert` for v1.5 — it is already v1.5-ready

**Exit criteria:** `/thumbnails` returns correctly sized thumbnails for all pages; response time acceptable for browser to display progress; `/convert` correctly applies provided classifications.

---

### Phase 13 — Vercel Frontend (v1.5)

Add optional AI enhancement UI to existing frontend:
- Anthropic API key input field with "Show/Hide" toggle
- Label: "Key stays in your browser only — sent directly to Anthropic"
- Link to console.anthropic.com

**v1.5 flow in browser JS:**
1. User provides key and uploads PDF
2. Browser POSTs PDF to `/thumbnails`, receives thumbnail array
3. Browser calls Anthropic API directly per page thumbnail using user's key — classification prompt returns `{background, safe_to_lighten, reason}`
4. Browser POSTs original PDF + classifications JSON to `/convert`
5. PDF returned and opened in new tab

- If key not provided: skip steps 2-4, POST directly to `/convert` without classifications (v1 behavior)
- Key lives in JS variable only — never written to localStorage or sessionStorage
- Key never included in any request to Cloud Run
- Update spinner: "Converting — large PDFs may take 2-4 minutes"

**Exit criteria:** BYO key flow works end to end; no-key flow falls back to v1 cleanly; key verified absent from all Cloud Run request logs via browser network tab; classification JSON visible in browser network tab on `/convert` request.

---

### Phase 14 — QA (v1.5)

- Verify AI classification correctly identifies dark-chart pages as safe_to_lighten: false and preserves them
- Verify missing classifications fall back to corner-sampling heuristic per page
- Verify key never appears in Cloud Run request logs
- Verify no-key users get v1 behavior without error
- Compare output quality: v1.5 should produce visibly better results than v1 on mixed-layout pages

**Exit criteria:** v1.5 demonstrably more accurate than v1 on mixed-layout pages; clean degradation to v1 behavior confirmed.

---

## Open Questions — Deferred to v2 and Beyond

- **Email delivery for large files:** async processing, email API (SendGrid/Resend), GCS storage for output PDF, failure notification — treat as a separate build
- **Parallel chunk processing:** split PDF into N-page blocks (default 10), parallel Cloud Run jobs, assemble at delivery — natural v2 for large file performance
- **Searchable text layer:** OCR or PyMuPDF text overlay in output PDF
- **Cross-browser print support:** Firefox, Safari
- **LUT curve tuning:** based on v1 real-world output
- **Larger file support:** streaming or object storage uploads beyond 32MB
- **Format threshold tuning:** 200 chars/page is provisional; refine after v1 data

---

## Toolchain

PyMuPDF (fitz), Pillow, Flask, argparse, pathlib, base64, Python 3.11  
Vercel (static frontend), Google Cloud Run (processing backend)  
GitHub: indyrise/print-friendly-pdf  
Domain: GoDaddy CNAME → Vercel
