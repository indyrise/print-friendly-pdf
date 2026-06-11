# ADR v2 — print-friendly-pdf

**Status:** Accepted — supersedes ADR dated 2026-06-07
**Date:** 2026-06-10
**Change note:** This revision was produced after Claude (Fable 5) built and
tested a working implementation directly, replacing the original
LUT-lightening architecture that failed validation. The Codex
implementation path was retired for this project.

---

## Context

Design-heavy PDFs (dark backgrounds, colored layouts) are ink-expensive to
print. The original v1 approach — a luminance LUT that lightened only dark
pixels — failed on its motivating use case: white text on dark backgrounds
remained white after lightening, producing unreadable output. Naive RGB
inversion (the approach used by existing free tools) fixes text but flips
every chart color. Neither solves the actual problem.

## Decision

### Core algorithm — hue-preserving lightness inversion

Invert lightness L in HSL space rather than inverting RGB values. The
operation reduces to closed form:

    RGB' = RGB + (1 - max(RGB) - min(RGB))

Properties (proven, not assumed):
- No clipping: with k = 1 - max - min, max+k = 1-min <= 1 and
  min+k = 1-max >= 0
- Hue and chroma preserved: adding a constant to all channels leaves
  channel ordering and (max - min) unchanged
- White (L=1) -> black; dark backgrounds (L~0.1) -> light; saturated
  mid-lightness colors (chart bars) pass through nearly unchanged

This is the differentiator versus existing inverters, which damage chart
colors via full RGB inversion.

### Surgical page replacement

Only dark-detected pages are rasterized and replaced. All other pages
retain original vector content — searchable, sharp, original size. A
document with no dark pages is returned byte-identical to the input.
Validated: 14-page light PDF returned unchanged (previously 89MB of
unnecessary raster output under the full re-raster design).

### Page detection

Corner-sampling heuristic at low DPI (36) for the detection pass; full-DPI
rasterization only for pages being replaced. Optional per-page
`classifications` JSON overrides the heuristic (v1.5 AI flow). Schema
field is `safe_to_invert` (renamed from `safe_to_lighten` — the operation
changed).

### Deployment scope — combined v1 + v1.5 launch

v1 and v1.5 deploy together. Rationale: the backend is identical (the
`/thumbnails` endpoint and `classifications` support are already built and
tested); v1.5 is frontend-only additional scope with clean degradation to
v1 behavior when no API key is provided. The original staged sequence
assumed incremental Codex implementation; that assumption no longer holds.

**Amendment 2026-06-10 (same day):** R1 region-aware masking was
implemented and validated in-session (deterministic connected-component
masking of near-white regions >= 2% of page area, hole-filled to preserve
panel contents, fail-open design). All four acceptance criteria passed on
the validation document's panel pages; light-PDF byte-identical regression held. R1 is
included in launch scope. Adds scipy dependency.

### Unchanged from v1 ADR

PDF output (not HTML), Content-Disposition inline, Chrome-first, 32MB
ceiling, synchronous request/response, browser uploads direct to Cloud Run
(no Vercel functions in file path), CORS restricted to
https://print-friendly-pdf.indyri.se, BYO API key pattern (key never
touches backend), GCP billing controls as hard prerequisite before public
URL, Cloud Run limits (max 2 instances, concurrency 1, 300s timeout, 1GB).

## Known limitations (documented, accepted for launch)

- Light panels below the ~2% area threshold invert with the page (by design); threshold untuned beyond one document
- Replaced pages lose searchable text layer
- Centered dark panels on light pages not detected by corner sampling
- Password-protected PDFs rejected; 32MB ceiling

## Alternatives considered (this revision)

| Option | Reason rejected |
|---|---|
| LUT lightening (original v1) | White text stays white — unreadable; failed validation |
| Naive RGB inversion | Damages chart colors; commodity capability of existing free tools |
| Staged v1-then-v1.5 deploy | Backend identical between stages; staging adds delay without de-risking |
| Include R1 in launch | Untuned algorithm on critical path; deferred |
| Full-document re-raster | 30x size bloat on pass-through documents; replaced by surgical page replacement |

## Toolchain

PyMuPDF, Pillow, numpy, Flask, Python 3.11
Cloud Run (backend) · Vercel (static frontend) · GoDaddy CNAME
GitHub: indyrise/print-friendly-pdf · Live: print-friendly-pdf.indyri.se
