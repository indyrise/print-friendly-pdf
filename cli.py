from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pdf_print_prep.core import process_pdf


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert a design-heavy PDF into a print-friendly PDF."
    )
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--no-lighten", action="store_true")
    args = parser.parse_args()

    if not args.input_pdf.exists():
        print(f"Input file does not exist: {args.input_pdf}", file=sys.stderr)
        return 1
    if args.input_pdf.suffix.lower() != ".pdf":
        print("Input file must be a PDF", file=sys.stderr)
        return 1

    try:
        output_bytes = process_pdf(
            args.input_pdf.read_bytes(),
            dpi=args.dpi,
            lighten=not args.no_lighten,
            classifications=None,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_path = args.input_pdf.with_name(f"{args.input_pdf.stem}_print.pdf")
    output_path.write_bytes(output_bytes)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

