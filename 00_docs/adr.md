# ADR — pdf-print-prep

**Status:** Accepted  
**Date:** 2026-06-07

---

## Context

Design-heavy PDFs (dark backgrounds, colored layouts) are ink-expensive to print. The immediate use case is the SenseAI Ventures State of AI 2026 report — a Canva-exported PDF with near-full-page dark backgrounds, colored charts, and embedded images.

Existing tools either invert all colors (damages charts) or only whiten the HTML chrome around page images (does not reduce ink on the pages themselves). Neither solves the actual problem.

The tool is intended as a public-facing portfolio project with a live URL at pdf-print-prep.indyri.se.

---

## Product Modes

The tool ships in two versions:

| Mode | Version | AI | API Key | Cost to user |
|---|---|---|---|---|
| Deterministic | v1 | None | Not required | Free |
| AI-enhanced | v1.5 | Claude vision classification | User's own Anthropic key | User's Anthropic bill |

**v1 is the baseline.** It works without any API key and is the primary portfolio artifact.

**v1.5 is an optional enhancement.** User pastes their own Anthropic API key into the UI. The browser calls Anthropic directly for page classification using small thumbnails only. The backend never receives, stores, or logs the user's key. This is the same pattern as escape-room-builder.indyri.se.

Hosted AI mode (tool owner's key, owner's cost) is explicitly out of scope. The BYO API pattern eliminates that cost and security surface entirely.

---

## Decision

### Processing — v1 (deterministic)

- Rasterize each page with PyMuPDF at specified DPI
- Composite onto white canvas to eliminate transparency artifacts
- Detect dark background via corner sampling: sample four corners (10x10px), compute mean RGB; if below 80, treat as dark page
- Apply luminance-based LUT via Pillow `point()` — maps pixel values 0–60 toward 220–255, leaves mid-tones and highlights stable. Not a full inversion. Not a histogram-wide autocontrast.
- Apply LUT to R, G, B channels independently
- Optional crop via `ImageOps.invert(img).getbbox()` — simple trim heuristic, may be a no-op on many full-page designed rasters
- Reassemble processed page images into a PDF using PyMuPDF
- Return PDF as file response — browser opens in tab with native print button

### Output Format Selection

PNG is the default format. Post-lightening pages are text-dominant with light backgrounds where JPEG compression artifacts are most visible and most damaging to print quality.

A document-level heuristic determines format before rasterization:

- Compute total characters across all pages using `page.get_text()` data already extracted in preflight
- Divide by page count to get chars_per_page
- If chars_per_page < 200: use JPEG at quality 85 (gradient/image-heavy document, file size reduction acceptable)
- If chars_per_page >= 200: use PNG (text-dominant document, sharpness preserved)
- Threshold of 200 is provisional — tune after benchmarking on representative PDFs
- Decision is document-level, not per-page — one format for the entire output PDF
- Log format decision and chars_per_page to terminal

### Processing — v1.5 (AI-enhanced, additive)

v1.5 uses a single `POST /convert` endpoint shared with v1. The only addition is a lightweight `POST /thumbnails` endpoint used by the browser to obtain small page previews for classification.

**v1.5 flow:**

1. Browser uploads PDF to `POST /thumbnails`
2. Cloud Run rasterizes each page at low resolution (150px wide), returns array of small JPEG thumbnails as base64 JSON — lightweight, no full-res images
3. Browser receives thumbnails, calls Anthropic API directly per page using user's key
4. Classification response per page: `{"background": "dark|light|mixed", "safe_to_lighten": true|false, "reason": "one sentence"}`
5. Browser sends original PDF + classification JSON to `POST /convert`
6. Cloud Run rasterizes at full DPI, applies LUT based on provided classifications (falls back to corner-sampling heuristic for any page missing classification), assembles PDF, returns it

**Key properties of this design:**
- Single `/convert` endpoint shared between v1 and v1.5 — v1.5 simply adds an optional classification JSON field
- Browser holds only small thumbnails and classification JSON — no full-res images in browser memory
- No server-side session storage — no state persisted between `/thumbnails` and `/convert` calls
- Absent classifications field → heuristic fallback for all pages
- Malformed or structurally invalid classifications field → 400, not silent fallback
- Valid classification entries must contain `page_index` (integer), `background` (string: "dark", "light", or "mixed"), and `safe_to_lighten` (boolean); entries missing required fields are rejected with 400
- Duplicate `page_index` entries: last entry wins
- `background="mixed"` is eligible for lightening only when `safe_to_lighten` is true
- AI failure or missing classification for a specific page degrades cleanly to heuristic for that page only
- User key never touches the backend

### Output Format

PDF, not HTML. Returned with `Content-Type: application/pdf`, `Content-Disposition: inline`. Browser opens in tab with native PDF viewer — familiar print button, download button. No auxiliary text layer in v1; deferred to v2.

### Target Browser

v1 is optimized for Chrome. Cross-browser print behavior is explicitly out of scope for v1.

### Deployment

- Python processing on Cloud Run:
  - `POST /convert` — v1 and v1.5 (accepts optional classification JSON)
  - `POST /thumbnails` — v1.5 only, lightweight low-res rasterization for browser classification
- Vercel hosts static frontend — no Vercel serverless functions in the file handling path
- Browser uploads PDF directly to Cloud Run to avoid Vercel function body size limits
- Synchronous request/response for both v1 and v1.5
- For v1, treat 32MB as supported maximum; warn above 25MB in UI
- Public GitHub repo: indyrise/pdf-print-prep
- Subdomain: pdf-print-prep.indyri.se via GoDaddy CNAME to Vercel

---

## Security and Cost Risk Mitigation

### Cloud Run controls
- Max instances: 2 — absolute ceiling on concurrent compute
- Min instances: 0 — zero cost when idle
- Request concurrency: 1 per instance
- CPU allocated during request processing only
- Timeout: 300 seconds (set explicitly — default may be insufficient for large PDFs)
- Memory: 1GB
- Dedicated least-privilege service account — no broad IAM roles
- CORS restricted to https://pdf-print-prep.indyri.se only — browser hygiene, not a hard security boundary. Does not prevent direct script or curl access. OPTIONS preflight responses apply the same origin restriction as normal responses.

### GCP billing controls
- Monthly budget cap set before Cloud Run URL is made public — hard prerequisite
- Alert at 50%: email notification to rucha@indyri.se
- Alert at 100%: triggers billing-disable automation workflow (not automatic by default — requires Cloud Pub/Sub + Cloud Function setup; must be configured explicitly)
- Recommended starting cap: $20/month
- At max 2 instances, ~60-90 seconds per conversion, Cloud Run compute costs approximately $0.002-0.003 per PDF — thousands of conversions required to approach $20 cap
- v1.5 AI classification cost falls entirely on user's Anthropic key, not the tool owner
- `/thumbnails` endpoint is lightweight — low-res rasterization only, minimal compute cost

### BYO API key security rules (v1.5)
- User key lives in browser memory only for that session
- Key is sent directly from browser to Anthropic — backend never receives it
- Key is never stored in localStorage, sessionStorage, or any persistent browser store
- Key is never logged server-side
- Key is never included in Cloud Run requests
- This is the same pattern as escape-room-builder.indyri.se

---

## Tradeoffs

- Luminance remap targets dark backgrounds but may affect dark chart elements — `--no-lighten` flag provides fallback
- Rasterized images lose vector sharpness at high zoom — acceptable for print use case
- PNG default preserves text sharpness at cost of larger file size; JPEG used automatically for image-heavy documents via chars_per_page heuristic
- No searchable text layer in PDF output in v1 — deferred to v2
- Synchronous wait with spinner acceptable for portfolio use case, not for production scale
- Crop heuristic may be a no-op on many full-page designed rasters — acceptable, documented
- CORS is browser hygiene only; primary cost protection is GCP billing cap and Cloud Run max instances
- Billing disable at cap will take the service offline — acceptable for portfolio use case, documented in README
- v1.5 browser holds only small thumbnails and classification JSON between /thumbnails and /convert calls — lightweight, no full-res image storage in browser
- AI cost estimates are provisional pending real benchmarks on actual documents

---

## Alternatives Considered

| Option | Reason rejected |
|---|---|
| Full color inversion | Damages charts |
| White HTML chrome only | Saves negligible ink on dark-background reports |
| HTML output | PDF output gives better UX — native browser print button |
| JPEG as universal default | Post-lightening text pages show visible compression artifacts |
| Per-page format selection | Adds complexity; document-level heuristic sufficient |
| AI for format selection | Unnecessary — PyMuPDF text extraction already provides the signal |
| Hosted AI mode (owner's key) | Unnecessary cost and security surface given BYO API pattern works |
| CLI-only for v1.5 | Not aligned with portfolio goals; live URL required |
| Async processing with polling | Adds complexity; synchronous sufficient for v1 |
| Proxy upload through Vercel serverless | Vercel function body size limits make this unreliable |
| OCR for image-dominant pages | Deferred to v2 |
| WeasyPrint for PDF output | PyMuPDF handles reassembly natively; no extra dependency needed |
| Email delivery for large files | Significant architecture addition; deferred to future enhancement |
| Two-step /rasterize + /assemble flow | More complex and data-heavy than single-request pattern; replaced by /thumbnails + single /convert |
| Server-side session storage for v1.5 | Unnecessary; /thumbnails and /convert are independent stateless calls |
| Full-res images in browser memory | Unnecessary data transfer; thumbnails sufficient for classification |

---

## Consequences

- Output is PDF, opened via browser native viewer, printed via familiar print button
- Chart damage possible on dark-chart pages — `--no-lighten` flag allows fallback
- Tool designed for design-tool PDF exports (Canva, Figma); behavior on scanned PDFs undefined
- Accessibility limited: rasterized pages not screen-reader accessible; v2 item
- If document requires authentication and no password provided, tool exits with clear message
- Zero-page PDFs rejected with 400
- Files over 32MB out of scope for v1
- Billing disable at cap will take the service offline — documented in README
- v1.5 AI classification accuracy better than corner-sampling for mixed-layout pages; AI failure falls back to heuristic per page, not to a fixed default
- Cross-browser print behavior not tested or supported in v1

---

## Future Enhancements

- **Email delivery for large files:** async processing, email API integration (SendGrid/Resend), GCS storage for output PDF, failure notification. Significant architecture addition — treat as a separate build.
- **Parallel chunk processing:** split PDF into N-page blocks (default 10), spin up parallel Cloud Run jobs per chunk, assemble chunks at delivery time. Natural v2 architecture for large file performance without async complexity.
- **Searchable text layer:** OCR or PyMuPDF text overlay in output PDF
- **Cross-browser support:** test and fix print behavior in Firefox, Safari
- **LUT curve tuning:** adjust threshold and curve based on real-world output from v1
- **Larger file support:** streaming or object storage uploads beyond 32MB
- **Format threshold tuning:** 200 chars/page is provisional; refine after v1 data

---

## Toolchain

PyMuPDF (fitz), Pillow, Flask, argparse, pathlib, base64, Python 3.11  
Vercel (static frontend), Google Cloud Run (processing backend)  
GitHub: indyrise/pdf-print-prep  
Domain: GoDaddy CNAME → Vercel
