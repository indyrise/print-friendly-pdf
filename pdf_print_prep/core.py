"""
print-friendly-pdf — core processing logic.

Converts design-heavy PDFs (dark backgrounds, white text, colored charts)
into print-friendly PDFs via hue-preserving lightness inversion.

Two design decisions distinguish this from naive PDF inverters:

1. HUE-PRESERVING INVERSION. Inverting lightness L in HSL space — rather
   than inverting RGB — flips dark backgrounds to light and white text to
   black while leaving saturated mid-lightness colors (chart bars, accents)
   nearly unchanged. The HSL lightness flip reduces to a closed-form RGB
   operation:

       RGB' = RGB + (1 - max(RGB) - min(RGB))

   Proof of no clipping: with k = 1 - max - min,
       max + k = 1 - min  <= 1   (min >= 0)
       min + k = 1 - max  >= 0   (max <= 1)
   Hue and chroma are preserved because adding a constant to all three
   channels leaves (max - min) and channel ordering unchanged.

2. SURGICAL PAGE REPLACEMENT. Only dark-detected pages are rasterized and
   replaced. Light pages remain the original vector content — searchable,
   sharp, and small. A document needing no changes is returned unchanged.
"""

from io import BytesIO

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

DARK_THRESHOLD = 80           # mean corner RGB below this => dark page
CORNER_SIZE = 10              # corner sample square in pixels
DETECT_DPI = 36               # cheap low-res render for detection only
PAGE_CHARS_PNG_THRESHOLD = 200  # page chars >= this => PNG, else JPEG
NEAR_WHITE = 225              # min(RGB) >= this => near-white pixel (R1)
MIN_REGION_FRACTION = 0.02    # preserve components >= 2% of page area (R1)


def preserve_light_regions_mask(img: Image.Image):
    """R1: find large near-white regions (content panels, cards) on a page
    about to be inverted, and return a boolean mask of pixels to preserve.

    Near-white pixels are labeled into connected components; components
    covering >= MIN_REGION_FRACTION of the page are kept, with holes
    filled so panel contents (logos, text inside cards) are preserved
    along with the panel background.

    Fail-open: if nothing qualifies, returns None and the page inverts
    exactly as before.
    """
    from scipy import ndimage

    arr = np.asarray(img)
    near_white = arr.min(axis=-1) >= NEAR_WHITE
    if not near_white.any():
        return None

    labels, n = ndimage.label(near_white)
    if n == 0:
        return None

    min_area = MIN_REGION_FRACTION * arr.shape[0] * arr.shape[1]
    sizes = ndimage.sum(near_white, labels, range(1, n + 1))
    keep = [i + 1 for i, s in enumerate(sizes) if s >= min_area]
    if not keep:
        return None

    mask = np.isin(labels, keep)
    mask = ndimage.binary_fill_holes(mask)  # include panel contents
    return mask


def invert_lightness(img: Image.Image, preserve_panels: bool = True) -> Image.Image:
    """Hue-preserving lightness inversion (HSL L -> 1-L), vectorized.

    If preserve_panels is True (R1), large near-white content regions are
    excluded from inversion and keep their original pixels.
    """
    arr = np.asarray(img, dtype=np.float32) / 255.0
    mx = arr.max(axis=-1, keepdims=True)
    mn = arr.min(axis=-1, keepdims=True)
    out = arr + (1.0 - mx - mn)

    # Snap light, near-neutral pixels (inverted backgrounds) to pure white.
    # Colored content (chart bars, accents) has chroma above the threshold
    # and is untouched; this removes the residual background tint that
    # hue preservation would otherwise leave (e.g. navy -> pale blue).
    mx2 = out.max(axis=-1)
    mn2 = out.min(axis=-1)
    light_neutral = ((mx2 + mn2) / 2 >= 0.85) & ((mx2 - mn2) <= 0.12)
    out = np.where(light_neutral[..., None], 1.0, out)

    if preserve_panels:
        mask = preserve_light_regions_mask(img)
        if mask is not None:
            out = np.where(mask[..., None], arr, out)
            pct = 100.0 * mask.mean()
            print(f"  R1: preserved light panel region(s), "
                  f"{pct:.1f}% of page area")

    return Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), mode="RGB")


def _pixmap_to_image(pix) -> Image.Image:
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    white = Image.new("RGB", img.size, (255, 255, 255))
    white.paste(img)
    return white


def is_dark_page(img: Image.Image) -> bool:
    """Corner-sampling heuristic: mean RGB of four corners below threshold."""
    w, h = img.size
    s = min(CORNER_SIZE, w, h)
    corners = [
        img.crop((0, 0, s, s)),
        img.crop((w - s, 0, w, s)),
        img.crop((0, h - s, s, h)),
        img.crop((w - s, h - s, w, h)),
    ]
    pixels = [p for c in corners for p in list(c.getdata())]
    mean_rgb = sum(sum(p) / 3 for p in pixels) / len(pixels)
    return mean_rgb < DARK_THRESHOLD


def process_pdf(pdf_bytes: bytes, dpi: int = 150, invert: bool = True,
                classifications=None) -> bytes:
    """Invert lightness on dark-detected pages; leave all other pages as
    original vector content. Returns processed PDF as bytes.

    classifications: optional list of dicts
        [{"page_index": 0, "background": "dark|light|mixed",
          "safe_to_invert": true|false}, ...]
    If provided, overrides the corner-sampling heuristic per page.
    Pages without an entry fall back to the heuristic.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    if doc.needs_pass:
        raise ValueError("Password-protected PDFs are not supported")
    if len(doc) == 0:
        raise ValueError("PDF contains no pages")

    print(f"Pages: {len(doc)}")

    cls = {}
    if classifications:
        for entry in classifications:
            cls[entry["page_index"]] = entry

    # --- Pass 1: cheap detection at low DPI ---
    to_invert = []
    for i, page in enumerate(doc):
        if not invert:
            break
        if i in cls:
            e = cls[i]
            dark = (e["background"] == "dark"
                    or (e["background"] == "mixed" and e["safe_to_invert"]))
            source = "classification"
        else:
            img = _pixmap_to_image(page.get_pixmap(dpi=DETECT_DPI))
            dark = is_dark_page(img)
            source = "heuristic"
        print(f"Page {i}: dark={dark} ({source})")
        if dark:
            to_invert.append(i)

    if not to_invert:
        print("--- print-friendly-pdf complete ---")
        print("No dark pages detected — returning original unchanged")
        return pdf_bytes

    # --- Pass 2: rasterize, invert, and replace only the dark pages ---
    for i in to_invert:
        page = doc[i]
        rect = page.rect
        page_chars = len(page.get_text())
        fmt = "png" if page_chars >= PAGE_CHARS_PNG_THRESHOLD else "jpeg"

        img = invert_lightness(_pixmap_to_image(page.get_pixmap(dpi=dpi)))

        buf = BytesIO()
        if fmt == "jpeg":
            img.save(buf, format="JPEG", quality=85)
        else:
            img.save(buf, format="PNG")

        # Insert replacement page at position i (original shifts to i+1),
        # keep original page dimensions in points, then delete the original.
        new_page = doc.new_page(pno=i, width=rect.width, height=rect.height)
        new_page.insert_image(new_page.rect, stream=buf.getvalue())
        doc.delete_page(i + 1)
        print(f"Page {i}: inverted and replaced ({fmt}, {page_chars} chars)")

    print("--- print-friendly-pdf complete ---")
    print(f"Pages processed: {len(doc)}")
    print(f"Inverted: {to_invert}")
    print(f"Untouched (original vector): "
          f"{[i for i in range(len(doc)) if i not in to_invert]}")

    return doc.tobytes(garbage=3, deflate=True)


def generate_thumbnails(pdf_bytes: bytes) -> list:
    """Low-res page thumbnails for browser-side AI classification (v1.5)."""
    import base64
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if doc.needs_pass:
        raise ValueError("Password-protected PDFs are not supported")
    if len(doc) == 0:
        raise ValueError("PDF contains no pages")
    out = []
    for i, page in enumerate(doc):
        scale = 150 / page.rect.width
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
        img = _pixmap_to_image(pix)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=70)
        out.append({"page_index": i,
                    "image": base64.b64encode(buf.getvalue()).decode()})
    return out
