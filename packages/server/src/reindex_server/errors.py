class ConflictError(ValueError):
    """The requested mutation conflicts with current server state."""


class StaleBaseError(ConflictError):
    def __init__(
        self, base_version_id: str | None, head_version_id: str | None
    ) -> None:
        super().__init__("remote Collection has advanced; fetch and resolve locally")
        self.base_version_id = base_version_id
        self.head_version_id = head_version_id
