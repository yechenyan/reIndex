from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_repository_and_cli_skill_copies_match() -> None:
    for name in ("reindex-create", "reindex-scan"):
        repository = ROOT / ".agents" / "skills" / name / "SKILL.md"
        packaged = ROOT / "packages" / "cli" / "skills" / name / "SKILL.md"
        assert repository.read_bytes() == packaged.read_bytes()
