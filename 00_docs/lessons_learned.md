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
- validation PDF references removed from all public-facing docs before they were committed
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

---

# Addendum — Project Revived (2026-06-10)

**Status change: Abandoned → Active.**

After the close-out above, Claude (Fable 5) was asked to review the full
project and build a working MVP directly. Two architecture changes
resolved the failure that triggered abandonment:

1. **Hue-preserving lightness inversion** replaced LUT lightening —
   `RGB' = RGB + (1 − max − min)` flips white text to black and dark
   backgrounds to light while leaving saturated chart colors nearly
   unchanged. Validated on the original failing document.
2. **Surgical page replacement** replaced full re-rasterization — only
   dark pages are touched; light documents return byte-identical.

**What this changes about the original conclusions:**
- "The problem is solved by existing tools" was wrong in one specific
  way: existing tools do naive RGB inversion, which destroys chart
  colors. Hue preservation is a real differentiator. The original search
  identified the right competitors but compared against the wrong (LUT)
  architecture rather than asking what would beat them.
- "Search for prior art first" stands, with a refinement: prior art
  defines the bar to clear, not necessarily the reason to stop.

**New lessons:**
- Lightness inversion is symmetric: white panels on dark pages flip to
  black. Logged as R1 in V1.5_REQUIREMENTS.md with acceptance criteria.
- Detection and processing should be separate passes at different DPIs —
  detect cheap (36 DPI), process expensive (150 DPI) only where needed.
- Schema rename: `safe_to_lighten` → `safe_to_invert`; frontend prompt
  must match.

The original close-out is preserved above, unmodified, as an accurate
record of where the project stood on 2026-06-09.
