"""print-friendly-pdf CLI."""
import argparse
import sys
from pathlib import Path

from pdf_print_prep.core import process_pdf


def main():
    parser = argparse.ArgumentParser(
        description="Convert design-heavy PDFs into print-friendly PDFs "
                    "via hue-preserving lightness inversion.")
    parser.add_argument("input", help="Path to input PDF")
    parser.add_argument("--dpi", type=int, default=150,
                        help="Raster DPI for replaced pages (default 150)")
    parser.add_argument("--no-invert", action="store_true",
                        help="Skip inversion entirely (pass-through)")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    try:
        out = process_pdf(path.read_bytes(), dpi=args.dpi,
                          invert=not args.no_invert)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    out_path = path.with_name(f"{path.stem}_print.pdf")
    out_path.write_bytes(out)
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
