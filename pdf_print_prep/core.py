from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import fitz
from PIL import Image, ImageOps


JPEG_THRESHOLD_CHARS_PER_PAGE = 200


@dataclass
class ProcessingSummary:
    page_count: int
    fmt: str
    chars_per_page: float
    lightened_pages: list[int]
    skipped_safe_false_pages: list[int]
    skipped_light_pages: list[int]
    image_dominant_pages: list[int]


def _open_pdf(pdf_bytes: bytes) -> fitz.Document:
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError("PDF could not be opened") from exc

    if doc.needs_pass:
        doc.close()
        raise ValueError("Password-protected PDFs are not supported")

    if len(doc) == 0:
        doc.close()
        raise ValueError("PDF contains no pages")

    return doc


def _format_page_list(pages: list[int]) -> str:
    if not pages:
        return "none"
    return ", ".join(str(page + 1) for page in pages)


def _classifications_by_page(
    classifications: list[dict[str, Any]] | None,
) -> dict[int, dict[str, Any]]:
    if not classifications:
        return {}

    by_page: dict[int, dict[str, Any]] = {}
    for entry in classifications:
        by_page[entry["page_index"]] = entry
    return by_page


def _select_output_format(doc: fitz.Document) -> tuple[str, float, list[int]]:
    print(f"Pages: {len(doc)}")
    page_text = [page.get_text() for page in doc]
    image_dominant_pages = [
        index for index, text in enumerate(page_text) if len(text) < 20
    ]
    for page_index in image_dominant_pages:
        print(f"Page {page_index + 1}: image-dominant (<20 chars)")

    total_chars = sum(len(text) for text in page_text)
    chars_per_page = total_chars / len(doc)
    fmt = "jpeg" if chars_per_page < JPEG_THRESHOLD_CHARS_PER_PAGE else "png"
    if fmt == "jpeg":
        print(
            f"Format: JPEG (chars_per_page={chars_per_page:.0f}) "
            "- gradient/image-heavy document"
        )
    else:
        print(f"Format: PNG (chars_per_page={chars_per_page:.0f})")
    return fmt, chars_per_page, image_dominant_pages


def _pixmap_to_rgb_image(pixmap: fitz.Pixmap) -> Image.Image:
    mode = "RGBA" if pixmap.alpha else "RGB"
    img = Image.frombytes(mode, (pixmap.width, pixmap.height), pixmap.samples)
    if img.mode != "RGB":
        img = img.convert("RGBA")
        white = Image.new("RGBA", img.size, (255, 255, 255, 255))
        white.alpha_composite(img)
        img = white.convert("RGB")
    else:
        white = Image.new("RGB", img.size, (255, 255, 255))
        white.paste(img)
        img = white
    return img


def _should_lighten_by_heuristic(img: Image.Image) -> bool:
    w, h = img.size
    sample = min(10, w, h)
    corners = [
        img.crop((0, 0, sample, sample)),
        img.crop((w - sample, 0, w, sample)),
        img.crop((0, h - sample, sample, h)),
        img.crop((w - sample, h - sample, w, h)),
    ]
    pixels = [pixel for corner in corners for pixel in corner.getdata()]
    mean_rgb = sum(sum(pixel) / 3 for pixel in pixels) / len(pixels)
    return mean_rgb < 80


def _should_lighten_by_classification(entry: dict[str, Any]) -> bool:
    background = entry["background"]
    safe_to_lighten = entry["safe_to_lighten"]
    if not safe_to_lighten:
        return False
    return background == "dark" or background == "mixed"


def _lighten_image(img: Image.Image) -> Image.Image:
    lut = []
    for value in range(256):
        if value <= 60:
            lut.append(int(220 + (255 - 220) * (1 - value / 60)))
        else:
            lut.append(value)
    return img.point(lut * 3)


def _crop_image(img: Image.Image) -> Image.Image:
    bbox = ImageOps.invert(img).getbbox()
    if not bbox:
        print("Crop skipped: empty bounding box")
        return img

    x1, y1, x2, y2 = bbox
    x1 = max(0, x1 - 10)
    y1 = max(0, y1 - 10)
    x2 = min(img.width, x2 + 10)
    y2 = min(img.height, y2 + 10)
    return img.crop((x1, y1, x2, y2))


def _print_summary(summary: ProcessingSummary) -> None:
    print("--- print-friendly-pdf complete ---")
    print(f"Pages processed: {summary.page_count}")
    print(f"Format: {summary.fmt.upper()} (chars_per_page={summary.chars_per_page:.0f})")
    print(f"Lightening applied: pages {_format_page_list(summary.lightened_pages)}")
    print(
        "Lightening skipped (classification safe_to_lighten=false): "
        f"page {_format_page_list(summary.skipped_safe_false_pages)}"
    )
    print(
        "Lightening skipped (light background): "
        f"page {_format_page_list(summary.skipped_light_pages)}"
    )
    print(
        "Image-dominant pages (< 20 chars): "
        f"{_format_page_list(summary.image_dominant_pages)}"
    )


def process_pdf(
    pdf_bytes: bytes,
    dpi: int = 150,
    lighten: bool = True,
    crop: bool = True,
    classifications: list[dict[str, Any]] | None = None,
) -> bytes:
    doc = _open_pdf(pdf_bytes)
    output_pdf = fitz.open()
    lightened_pages: list[int] = []
    skipped_safe_false_pages: list[int] = []
    skipped_light_pages: list[int] = []
    classifications_by_page = _classifications_by_page(classifications)

    try:
        fmt, chars_per_page, image_dominant_pages = _select_output_format(doc)

        for page_index, source_page in enumerate(doc):
            try:
                pixmap = source_page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB)
                img = _pixmap_to_rgb_image(pixmap)

                lightening_applied = False
                lightening_source = "disabled"
                if lighten:
                    classification = classifications_by_page.get(page_index)
                    if classification:
                        lightening_source = "classification"
                        if not classification["safe_to_lighten"]:
                            skipped_safe_false_pages.append(page_index)
                        elif classification["background"] == "light":
                            skipped_light_pages.append(page_index)
                        if _should_lighten_by_classification(classification):
                            img = _lighten_image(img)
                            lightening_applied = True
                            lightened_pages.append(page_index)
                    else:
                        lightening_source = "heuristic"
                        if _should_lighten_by_heuristic(img):
                            img = _lighten_image(img)
                            lightening_applied = True
                            lightened_pages.append(page_index)

                print(
                    f"Page {page_index + 1}: lightening "
                    f"{'applied' if lightening_applied else 'skipped'} "
                    f"({lightening_source})"
                )

                if crop:
                    img = _crop_image(img)

                buf = BytesIO()
                if fmt == "jpeg":
                    img.save(buf, format="JPEG", quality=85)
                else:
                    img.save(buf, format="PNG")

                output_page = output_pdf.new_page(width=img.width, height=img.height)
                output_page.insert_image(output_page.rect, stream=buf.getvalue())
            except Exception as exc:
                raise RuntimeError(f"Page {page_index + 1} failed: {exc}") from exc

        result = output_pdf.tobytes()
        _print_summary(
            ProcessingSummary(
                page_count=len(doc),
                fmt=fmt,
                chars_per_page=chars_per_page,
                lightened_pages=lightened_pages,
                skipped_safe_false_pages=skipped_safe_false_pages,
                skipped_light_pages=skipped_light_pages,
                image_dominant_pages=image_dominant_pages,
            )
        )
        return result
    finally:
        output_pdf.close()
        doc.close()


def generate_thumbnails(pdf_bytes: bytes) -> list[dict[str, Any]]:
    doc = _open_pdf(pdf_bytes)
    thumbnails: list[dict[str, Any]] = []
    try:
        for page_index, page in enumerate(doc):
            rect = page.rect
            scale = 150 / rect.width
            matrix = fitz.Matrix(scale, scale)
            pixmap = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
            img = _pixmap_to_rgb_image(pixmap)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=70)
            thumbnails.append(
                {
                    "page_index": page_index,
                    "image": base64.b64encode(buf.getvalue()).decode("ascii"),
                }
            )
    finally:
        doc.close()
    return thumbnails
