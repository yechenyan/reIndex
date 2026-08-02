from __future__ import annotations

__all__ = ["render_package", "validate_package"]


def __getattr__(name: str):
    if name == "render_package":
        from .renderer import render_package

        return render_package
    if name == "validate_package":
        from .validation import validate_package

        return validate_package
    raise AttributeError(name)
