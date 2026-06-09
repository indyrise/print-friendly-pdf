# print-friendly-pdf

Convert design-heavy PDFs into print-friendly PDFs by lightening dark page
backgrounds and reassembling the result as a browser-printable PDF.

v1 is deterministic: no OCR, no AI calls, no API key. The backend is also ready
for the later v1.5 browser flow, where optional page classifications can be sent
to `/convert` and lightweight thumbnails can be requested from `/thumbnails`.

## Local CLI

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python cli.py input.pdf
```

Optional flags:

```bash
.venv/bin/python cli.py input.pdf --dpi 150 --no-lighten --no-crop
```

The output is written next to the input as `input_print.pdf`.

## Local Web App

```bash
.venv/bin/python app.py
```

The Flask app listens on `PORT` or `8080` by default.

Endpoints:

- `POST /convert` with multipart field `pdf`
- `POST /thumbnails` with multipart field `pdf`

Both endpoints reject files over 32MB. `/convert` returns an inline PDF named
`{original_stem}_print.pdf`.

## Known Limits

- Password-protected PDFs are not supported.
- Output pages are rasterized, so searchable text is not preserved in v1.
- The dark-background heuristic uses page corners and may miss centered dark
  panels.
- Dark chart elements can be affected by lightening.
- Chrome is the target browser for v1.
