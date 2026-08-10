from types import SimpleNamespace

from reindex_server import postgres


class _Cursor:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, command: str) -> None:
        self.commands.append(command)

    def fetchone(self) -> tuple[str]:
        return ("collections",)


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> "_Connection":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def cursor(self) -> _Cursor:
        return self._cursor


def test_initialize_database_preserves_existing_schema(monkeypatch: object) -> None:
    cursor = _Cursor()
    monkeypatch.setattr(
        postgres.psycopg, "connect", lambda *_args, **_kwargs: _Connection(cursor)
    )
    monkeypatch.setattr(
        postgres,
        "files",
        lambda _package: SimpleNamespace(
            joinpath=lambda _name: SimpleNamespace(read_text=lambda **_kwargs: "DROP TABLE collections")
        ),
    )

    postgres.initialize_database("postgresql://example")

    assert "DROP TABLE collections" not in cursor.commands
    assert cursor.commands[0].startswith("SELECT pg_advisory_lock")
    assert cursor.commands[-1].startswith("SELECT pg_advisory_unlock")
