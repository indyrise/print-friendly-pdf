# Lessons Learned — print-friendly-pdf

**Status:** Abandoned  
**Date:** 2026-06-09  
**Time logged:** 1h 16m

---

## What Broke

**The core assumption was wrong.** The tool was designed to lighten dark backgrounds via luminance LUT. The motivating PDF (a Canva-exported design report) used white text on dark backgrounds. Lightening the background left white text white — unreadable against a light page. The LUT approach has no mechanism to recolor text.

**The fix (full inversion) is a solved problem.** Searching for alternatives revealed multiple free tools (invert-pdf.club, ihatepdf, lovedpdf, and others) doing exactly this — some without even uploading the file. The space is saturated.

**Crop was removed mid-build.** The crop heuristic (`ImageOps.invert(img).getbbox()`) trimmed real margins on standard PDFs. Tested on an HBR article — output had near-zero margins. Removed entirely rather than made opt-in; no valid use case emerged.

**V1 works on the wrong PDFs.** Light-background PDFs don't need processing. Dark-background PDFs need more than LUT lightening. V1 is functional but solves a problem that doesn't exist in practice.

---

## What Was Decided

- Crop removed entirely — heuristic caused more harm than benefit across arbitrary PDFs
- `libmupdf-dev` apt line removed from Dockerfile — PyMuPDF wheels are self-contained since v1.18; the apt line would fail on slim containers
- App renamed from `pdf-print-prep` to `print-friendly-pdf` mid-build
- SenseAI PDF references removed from all public-facing docs before they were committed
- "Test on 5 pages" clarified as manual inspection of full output, not a code-enforced constraint
- Project abandoned after confirming full inversion is already a solved, saturated problem

---

## What Carries Forward

- PyMuPDF wheels are self-contained — never add `apt-get install libmupdf-dev` to a slim container Dockerfile
- Validate the motivating use case against the proposed approach before speccing — a 10-minute search at the start would have surfaced invert-pdf.club
- "Does this tool work on the PDF I actually want to print?" is a required pre-spec check, not a QA item

---

## What to Do Differently

- Search for existing solutions before scoping — not after hitting a wall
- Test the tool on the exact document that motivated the build in the first session, not a substitute
- Full inversion as default would have produced readable output; LUT-only was underspecced for the actual use case

---

## Carry-forward sentence

Before speccing any document processing tool, run the intended input through the proposed approach mentally and confirm the output handles the failure mode (e.g. white text on dark background) — if it doesn't, either expand the spec or search for prior art first.
