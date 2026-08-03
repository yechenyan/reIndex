from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageChops

from pdf_table_codegen.evidence import _contact
from pdf_table_codegen.job import load_job
from pdf_table_codegen.reference import sample_indices
from pdf_table_codegen.runner import _module, run_job, verify_job
from pdf_table_codegen.skill import install_skill

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "testbase" / "test5-table"
BIELEFELD = FIXTURES / "bielefelder-netz-2022" / "job.yaml"
SWS_SOLINGEN = FIXTURES / "sws-netze-solingen-2024" / "project" / "job.yaml"


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_visual_reference_sampling_handles_short_tables() -> None:
    assert sample_indices(0) == []
    assert sample_indices(1) == [0]
    assert sample_indices(2) == [0, 1]
    assert sample_indices(3) == [0, 1, 2]
    assert sample_indices(4) == [0, 1, 2, 3]
    assert sample_indices(5) == [0, 1, 3, 4]


def test_all_pdf_projects_have_resolvable_jobs() -> None:
    jobs = sorted([*FIXTURES.glob("*/job.yaml"), *FIXTURES.glob("*/project/job.yaml")])
    assert len(jobs) == 5
    for path in jobs:
        job = load_job(path)
        assert job.source.is_file()
        project_root = path.parent.parent if path.parent.name == "project" else path.parent
        assert job.source.parent == project_root


def test_agent_skill_installs_idempotently(tmp_path: Path) -> None:
    target, status = install_skill(tmp_path)
    assert status == "installed"
    assert (target / "SKILL.md").is_file()
    assert (target / "references" / "audit.md").is_file()
    assert (target / "references" / "extraction-strategies.md").is_file()
    assert install_skill(tmp_path) == (target, "unchanged")


def test_loading_extractor_does_not_write_project_bytecode(tmp_path: Path) -> None:
    extractor = tmp_path / "extractor.py"
    extractor.write_text("VALUE = 1\n", encoding="utf-8")
    assert _module(extractor).VALUE == 1
    assert not (tmp_path / "__pycache__").exists()


def test_later_contact_group_uses_local_layout_positions(tmp_path: Path) -> None:
    pages = []
    for page_number in range(13, 18):
        path = tmp_path / f"page-{page_number}.png"
        image = Image.new("RGB", (120, 160), "white")
        image.putpixel((page_number, page_number), (0, 0, 0))
        image.save(path)
        pages.append((page_number, path))
    target = tmp_path / "contact.jpg"
    _contact(pages, target)
    with Image.open(target) as contact:
        white = Image.new("RGB", contact.size, "white")
        assert ImageChops.difference(contact.convert("RGB"), white).getbbox() is not None


def test_bielefeld_frozen_reference_passes() -> None:
    report = verify_job(BIELEFELD)
    assert report["ok"]
    assert not [check for check in report["checks"] if not check["ok"]]
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["aggregierte-10-jahresplanung.columns"]["actual"] == 3
    assert checks["aggregierte-10-jahresplanung.rows"]["actual"] == 24
    assert checks["massnahmenplan.columns"]["actual"] == 20
    assert checks["massnahmenplan.rows"]["actual"] == 52
    for index in (0, 1, 50, 51):
        assert checks[f"massnahmenplan.row[{index}]"]["ok"]


def test_sws_full_document_reference_passes() -> None:
    report = verify_job(SWS_SOLINGEN)
    assert report["ok"]
    checks = {check["name"]: check for check in report["checks"]}
    inventory = checks["full_table_inventory"]
    assert inventory["ok"]
    assert len(inventory["expected"]) == 6
    table_id = inventory["expected"][-1]
    assert checks[f"{table_id}.columns"]["actual"] == 16
    assert checks[f"{table_id}.rows"]["actual"] == 13


def test_bielefeld_output_is_deterministic() -> None:
    job = load_job(BIELEFELD)
    run_job(BIELEFELD)
    before = {path.name: _digest(path) for path in job.output_dir.glob("*")}
    run_job(BIELEFELD)
    after = {path.name: _digest(path) for path in job.output_dir.glob("*")}
    assert before == after
