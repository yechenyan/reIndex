"""Public Python API for ReIndex."""

from importlib.metadata import PackageNotFoundError, version

from reindex_cli.api import ApiClient

try:
    __version__ = version("reindex")
except PackageNotFoundError:  # Source-only execution without an installed distribution.
    __version__ = "0.0.0+local"

__all__ = ["ApiClient", "__version__"]
