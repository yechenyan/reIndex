from __future__ import annotations

import argparse
import json
from pathlib import Path

from reindex_cli.cli_contract import public_contract
from reindex_cli.cli_dispatch import validate_handler_coverage

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "packages" / "web-app" / "public" / "doc" / "cli-v1.json"


def rendered_contract() -> str:
    return json.dumps(public_contract(), ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile the CLI contract for Web docs.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    validate_handler_coverage()
    expected = rendered_contract()
    if args.check:
        actual = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if actual != expected:
            print(f"CLI contract artifact is stale: {OUTPUT}")
            return 1
        print("CLI contract, handlers, and Web artifact match")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
