from __future__ import annotations

import ast
from pathlib import Path


def strategy_catalog(directory: Path) -> list[dict]:
    result = []
    for path in sorted(directory.glob("strategy_*.py")):
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        functions = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                functions.append({"name": node.name, "arguments": [item.arg for item in node.args.args]})
        result.append(
            {"fileName": path.name, "documentation": ast.get_docstring(tree) or "", "functions": functions}
        )
    return result
