# Publishing — print-friendly-pdf

## Positioning statement

print-friendly-pdf converts design-heavy PDFs (dark backgrounds, white
text, colored charts) into ink-light, printable documents — without
destroying chart colors. Unlike existing inverters that flip every color
via naive RGB inversion, it inverts *lightness* in HSL space and snaps neutral backgrounds to pure white, so white
text becomes black, dark backgrounds become light, and chart colors pass
through nearly unchanged. It only touches the pages that need it: light
pages keep their original vector content, and a document with no dark
pages is returned byte-identical. Built as an AI-assisted development
case study — architecture, implementation, and in-session validation are
documented in `00_docs/`.

## License recommendation

**MIT.** Rationale: maximum reuse for a portfolio piece (permissive
licenses signal "use this, learn from this"), no copyleft obligations to
explain, and all dependencies (PyMuPDF is AGPL — see note) need checking.

> **Dependency note (resolve before publish):** PyMuPDF is licensed
> AGPL-3.0 (or commercial). Distributing this project under MIT is fine —
> your code is yours — but *deploying* it as a network service has AGPL
> implications via PyMuPDF: AGPL requires source availability for
> network-served software. Since this repo IS the public source of the
> deployed service, you satisfy that by default. State this explicitly in
> the README license section: project code MIT, PyMuPDF dependency AGPL,
> deployed service source is this repo.

## Repo structure

```
print-friendly-pdf/
  pdf_print_prep/
    __init__.py
    core.py              # inversion algorithm, page replacement, thumbnails
  cli.py                 # local CLI entry point
  app.py                 # Flask app (Cloud Run entry point)
  make_test_pdf.py       # generates synthetic validation PDF
  Dockerfile
  requirements.txt
  README.md
  LICENSE                # add: MIT text
  V1.5_REQUIREMENTS.md   # R1 record (implemented)
  00_docs/               # ADRs, build plans, build log, lessons learned
    ADR_v1.md            # superseded, kept for history
    ADR_v2.md            # active
    BUILD_PLAN_v1.md     # superseded
    BUILD_PLAN_v2.md     # active
    CODEX_PROMPT_v1.md   # superseded (retired implementation path)
    BUILD_LOG.md
    LESSONS_LEARNED.md
```

## Install path

```bash
git clone https://github.com/indyrise/print-friendly-pdf
cd print-friendly-pdf
pip install -r requirements.txt        # pymupdf pillow flask numpy scipy

# CLI
python cli.py your.pdf                 # writes your_print.pdf alongside
python make_test_pdf.py                # generate the synthetic test PDF

# Local server
python app.py                          # serves on :8080
curl -X POST -F "pdf=@your.pdf" http://localhost:8080/convert -o out.pdf

# Container
docker build -t print-friendly-pdf .
docker run -p 8080:8080 print-friendly-pdf
```

## Contribution notes

- Issues and PRs welcome; this is a portfolio project maintained on a
  best-effort basis
- Before a PR: run the regression set — synthetic PDF (dark page inverts,
  light page untouched), a light-only PDF (must return byte-identical),
  and a dark-background PDF with white panels (panels preserved)
- Algorithm changes require a before/after image pair in the PR
  description
- Known-good tuning values (`NEAR_WHITE=225`, `MIN_REGION_FRACTION=0.02`,
  `DARK_THRESHOLD=80`) were validated on a limited document set —
  threshold-tuning contributions with diverse test documents are the most
  valuable kind

## What's needed to publish

1. **Add LICENSE file** (MIT text) and the PyMuPDF/AGPL note to README
2. **Remove or relocate local test artifacts** — `*_print.pdf` outputs are
   already gitignored; confirm no test PDFs are staged
3. **Sanitization done 2026-06-10:** validation-document name and owner
   email genericized across all files (verified zero occurrences)
4. **README final pass:** live URL goes in only after Phase 8 (CNAME
   live); until then mark as "deployment in progress"
5. **GCP billing controls active before the live URL appears anywhere
   public** (Build Plan v2, Phase 5 — hard gate)
6. Push, confirm repo renders correctly on GitHub, link from indyri.se
