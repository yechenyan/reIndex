from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pdf import render_page


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Render a PDF page in visual-page coordinates")
    value.add_argument("pdf", type=Path)
    value.add_argument("page", type=int, help="1-based page number")
    value.add_argument("output", type=Path)
    value.add_argument("--dpi", type=int, default=180)
    value.add_argument("--bbox", nargs=4, type=float, metavar=("X0", "Y0", "X1", "Y1"))
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = render_page(args.pdf, args.page, args.output, args.dpi, tuple(args.bbox) if args.bbox else None)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

