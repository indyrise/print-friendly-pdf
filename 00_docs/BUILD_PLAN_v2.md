# Build Plan v2 — print-friendly-pdf

**Date:** 2026-06-10
**Status:** Active — supersedes build plan dated 2026-06-07
**Change note:** Backend code (core.py, cli.py, app.py, Dockerfile) was
built and tested by Claude (Fable 5) directly; Codex phases 1–6 of the
original plan are retired. This plan covers integration, deployment, and
the v1.5 frontend in a single launch. R1 (region masking) is excluded —
see V1.5_REQUIREMENTS.md.

---

## Goal

Single combined launch: deterministic inversion (v1 behavior) plus BYO-key
AI classification (v1.5 behavior) live at print-friendly-pdf.indyri.se.

Success metric: the validation document converts to readable, ink-light output;
light PDFs pass through byte-identical; live URL is portfolio-presentable.

## Already done (verified in Fable session, 2026-06-10)

- core.py: hue-preserving inversion, surgical page replacement, detection
  pass, classifications support, thumbnails — tested on synthetic dark
  page, the validation document's panel pages, and 14-page light PDF (byte-identical return)
- app.py: /convert and /thumbnails with full validation matrix — tested
  via Flask test client (200, 400 paths)
- cli.py tested end to end; Dockerfile and requirements.txt written
- README with known limitations; V1.5_REQUIREMENTS.md with R1

## Phases

### Phase 1 — Local integration (Rucha's machine)
- Unzip package into repo, `pip3 install numpy`
- Run CLI on full 54-page validation PDF; inspect output in Chrome print
  preview (5 representative pages: cover, table page, chart page,
  text-heavy page, mixed)
- Run CLI on one light-background PDF; confirm pass-through
**Exit:** Full-document output acceptable; commit code to repo.

### Phase 2 — Flask local
- `python3 app.py`; curl POST the validation PDF to /convert
- Confirm PDF response opens in Chrome; spot-check one 400 path
**Exit:** Local end-to-end works.

### Phase 3 — Docker local
- Build and run container; repeat Phase 2 test against container
**Exit:** Container behavior matches local.

### Phase 4 — Cloud Run
- Deploy per established runbook (Rucha executes; Perplexity for steps if
  needed): max 2 instances, min 0, concurrency 1, 300s, 1GB, dedicated
  least-privilege service account
**Exit:** /convert and /thumbnails respond correctly at Cloud Run URL.

### Phase 5 — GCP billing controls (hard gate before public URL)
- $20/month budget; 50% email alert; 100% billing-disable automation via
  Pub/Sub + Cloud Function (explicit setup, not default)
**Exit:** Budget active, automation tested.

### Phase 6 — Frontend (single page, both modes)
- Static HTML/JS on Vercel; Claude builds the artifact
- v1 path: upload -> /convert -> PDF opens in new tab
- v1.5 path: optional Anthropic key field (show/hide; "key stays in your
  browser" label; link to console.anthropic.com) -> /thumbnails ->
  browser calls Anthropic per page -> /convert with classifications
- Key lives in a JS variable only; never in storage, never sent to
  Cloud Run
- Client-side size check: warn >25MB, block >32MB
- Cloud Run URL as JS constant; CORS origin must match
  https://print-friendly-pdf.indyri.se
**Exit:** Both modes work in Chrome; no-key degrades cleanly to v1.

### Phase 7 — QA (both modes)
- v1 mode: the validation document full PDF + light PDF + error states
- v1.5 mode (manual, Rucha's key): classification JSON visible in network
  tab on /convert; key absent from all Cloud Run requests; dark-chart
  pages correctly classified
- Verify R1: white panels on dark pages preserved with original colors
**Exit:** Both modes validated; limitations match README.

### Phase 8 — Public
- GoDaddy CNAME live; repo public; README final
**Exit:** Live URL resolves end to end.

## Deferred

- ~~R1 region-aware masking~~ — IMPLEMENTED 2026-06-10, included in launch (deterministic connected-component masking, scipy added to requirements)
- OCR / searchable text layer, cross-browser, >32MB, async/email delivery

## Toolchain

PyMuPDF, Pillow, numpy, Flask, Python 3.11 · Cloud Run · Vercel ·
GoDaddy CNAME · GitHub indyrise/print-friendly-pdf
