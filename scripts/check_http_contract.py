from __future__ import annotations

from reindex_server.app import create_app
from reindex_server.openapi_contract import (
    implementation_openapi,
    load_openapi_contract,
    openapi_diff,
)


def main() -> int:
    contract = load_openapi_contract()
    implementation = implementation_openapi(create_app(object()))
    if contract != implementation:
        print(openapi_diff(contract, implementation))
        return 1
    print(
        f"HTTP contract matches FastAPI implementation: {len(contract['paths'])} paths"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
