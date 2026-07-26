import json

from reindex_cli.cli import main


def test_doctor(capsys) -> None:
    assert main(["doctor"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "ok"
    assert result["version"] == "0.1.0"

