# print-friendly-pdf

## Install
```
pip install pdf2print
```

## Usage
```
pdf2print input.pdf
pdf2print input.pdf --dpi 300
```

Converts design-heavy PDFs (dark backgrounds, white text, colored charts)
into print-friendly versions — without destroying chart colors.

**Live:** https://print-friendly-pdf.indyri.se

## Why this exists

Dark-background PDFs are ink-expensive to print. Existing inverters do naive
RGB inversion, which makes text readable but flips every chart color
(red becomes cyan, orange becomes blue). This tool does neither-or:

1. **Hue-preserving lightness inversion.** Lightness is inverted in HSL
   space, which reduces to a closed-form RGB operation:
   `RGB' = RGB + (1 − max(RGB) − min(RGB))`. White text becomes black,
   dark backgrounds become light, and saturated chart colors — which sit
   near mid-lightness — pass through nearly unchanged. Provably no clipping.

2. **Surgical page replacement.** Only dark-detected pages are rasterized
   and replaced. Every other page keeps its original vector content —
   searchable, sharp, and small. A document with no dark pages is returned
   byte-identical.

## Usage

### CLI
```
python cli.py input.pdf [--dpi 150] [--no-invert]
```
Writes `input_print.pdf` alongside the input.

### Web
Upload a PDF at the live URL. The converted PDF opens in a new tab with
the browser's native print button. Chrome-first.

## Known limitations

- **Light-panel preservation uses a size threshold.** Large white
  content panels (cards, callout boxes) on dark pages are detected via
  connected-component analysis and preserved with their original colors.
  Regions below ~2% of page area (small icons, white text) invert with
  the page — by design. The threshold is conservative and fails open:
  if no region qualifies, the page inverts normally.
- Dark-page detection uses corner sampling — centered dark panels on
  light pages are not detected (v1.5 adds AI classification)
- Replaced pages lose their searchable text layer
- 32MB file ceiling
- Password-protected PDFs not supported

## Stack

PyMuPDF, Pillow, numpy, Flask, Python 3.11 · Cloud Run backend ·
Vercel static frontend · GoDaddy CNAME

## License

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

**Dependency notice:** This project uses [PyMuPDF](https://pymupdf.readthedocs.io/) (fitz),
which is licensed under the [GNU AGPL v3](https://www.gnu.org/licenses/agpl-3.0.html).
If you deploy this software as a network service, the AGPL requires you to make the
complete source code available to users. This repository satisfies that requirement.
