# Build Log — print-friendly-pdf

---

## What Was Being Built

A public-facing Python tool to convert design-heavy PDFs (dark backgrounds, colored layouts) into print-friendly versions via luminance LUT lightening. Stack: PyMuPDF, Pillow, Flask, Python 3.11, Cloud Run backend, Vercel static frontend. Intended as a portfolio artifact at print-friendly-pdf.indyri.se.

---

## What Was Tried

- Specced full v1 architecture across ADR.md, BUILD_PLAN.md, CODEX_PROMPT.md — two Perplexity review passes, multiple Claude revision rounds
- Codex implemented Phases 1–6 (core.py, cli.py, app.py, Dockerfile, requirements.txt)
- Discovered Dockerfile included `apt-get install libmupdf-dev` — flagged and removed; PyMuPDF wheels are self-contained since v1.18
- `.gitignore` was blank on repo creation; `__pycache__` and `.DS_Store` were already tracked — fixed with `git rm --cached`, full `.gitignore` added
- App renamed from `pdf-print-prep` to `print-friendly-pdf` mid-build; all three spec docs updated
- SenseAI PDF references removed from public docs before commit
- Ran CLI on SenseAI PDF (the motivating use case): output was unreadable — white text on dark background remained white after LUT lightening; expected background removal, actual result was cream background with invisible white text
- Ran CLI on HBR article (light-background PDF): output had near-zero margins — crop heuristic was trimming real content margins; crop removed entirely from codebase and spec
- Searched for existing tools: invert-pdf.club, ihatepdf, lovedpdf, and several others already solve full PDF inversion for printing, some without file upload
- Project abandoned

---

## What Broke or Surprised

- **White text assumption**: The LUT approach lightens backgrounds but does not recolor text. White text on dark pages becomes white text on light pages — unreadable. This was the primary use case.
- **Crop heuristic**: `ImageOps.invert(img).getbbox()` trimmed actual content margins on standard PDFs. Removing it entirely was the right call; no valid opt-in use case emerged.
- **Solved problem**: Full PDF color inversion for printing is a saturated, well-solved space. A 10-minute search surfaced multiple free tools. This search happened after the spec was complete and implementation was underway.

---

## What Was Learned

- PyMuPDF wheels are self-contained since ~v1.18 — `apt-get install libmupdf-dev` fails on slim containers and should never be added
- LUT lightening is insufficient for PDFs with white text on dark backgrounds — the majority of design-heavy PDFs use this pattern
- Searching for prior art belongs at the start of scoping, not after hitting a failure in QA

---

## Carry-forward

Before speccing any document processing tool, test the proposed approach mentally against the exact input that motivated the build — if the failure mode isn't handled, either expand the spec or search for prior art first.

---

## Status

**Abandoned.** The motivating use case (dark-background design PDFs) requires full color inversion, not LUT lightening. Full inversion is already a solved, saturated problem with multiple free tools available. V1 as built works only on light-background PDFs that don't need processing.
