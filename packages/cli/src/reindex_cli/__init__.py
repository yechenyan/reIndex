from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("reindex")
except PackageNotFoundError:  # Source-only execution without an installed distribution.
    __version__ = "0.0.0+local"
