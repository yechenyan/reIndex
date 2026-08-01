class ReIndexError(RuntimeError):
    """Expected CLI failure with a user-facing message."""


class ManifestError(ReIndexError):
    """The authoring manifest is invalid."""


class PackageError(ReIndexError):
    """The generated package violates the ReIndex protocol."""
