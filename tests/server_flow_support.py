import hashlib
import mimetypes
from pathlib import Path

from reindex_server.domain import SearchHit

ROOT_ID = "056e95b3-aad8-4740-af7e-973356ec4e44"
TABLE_ID = "333563cf-1334-45a5-9d19-55f53f79757f"
TABLE_PATH = (
    "bielefelder-netz-gmbh-netzausbauplan-2022/"
    "00005--aggregierte-10-jahresplanung-untere-netzebenen.node.md"
)


class FixtureSearchBackend:
    def search(self, collection, options, query_embedding):
        unit = next(
            unit
            for unit in collection.units
            if options.query.casefold() in unit.contextual_text.casefold()
        )
        return [SearchHit(unit, 1.0, ("lexical",), {"lexical": 1}, bm25_score=1.0)]

    def grep(self, collection, pattern, limit, regex, case_sensitive):
        return []


def fixture() -> tuple[Path, Path]:
    fixture_root = Path(__file__).resolve().parents[1] / "testbase" / "test1"
    package = fixture_root / "reIndex" / "test1"
    source = (
        fixture_root
        / "test1"
        / "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
    )
    return package, source


async def push(client, name, package, source, base_version_id, *, race=False):
    blobs = {}
    files = []
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        _manifest_file(
            files, blobs, "package", path.relative_to(package).as_posix(), path
        )
    _manifest_file(files, blobs, "raw", source.name, source)
    payload = {
        "name": name,
        "collection_id": ROOT_ID,
        "base_version_id": base_version_id,
        "message": f"Publish {name}",
        "manifest": {
            "spec": "reindex/transport@1.0",
            "package_root": package.name,
            "files": files,
        },
    }
    started = await client.post("/v1/push", json=payload)
    assert started.status_code == 200, started.text
    plan = started.json()
    raced = await client.post("/v1/push", json=payload) if race else None
    if raced is not None:
        assert raced.status_code == 200, raced.text
    for item in plan["missing_blobs"]:
        path = blobs[item["sha256"]]
        uploaded = await client.post(
            "/v1/push/blob",
            data={"upload_id": plan["upload_id"], "sha256": item["sha256"]},
            files={"blob": (path.name, path.read_bytes())},
        )
        assert uploaded.status_code == 200, uploaded.text
    committed = await client.post(
        "/v1/push/commit", json={"upload_id": plan["upload_id"]}
    )
    assert committed.status_code == 200, committed.text
    if raced is not None:
        stale = await client.post(
            "/v1/push/commit", json={"upload_id": raced.json()["upload_id"]}
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "stale_base"
    return committed.json()


def _manifest_file(files, blobs, namespace, logical_path, path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    blobs[digest] = path
    files.append(
        {
            "namespace": namespace,
            "logical_path": logical_path,
            "sha256": digest,
            "byte_size": path.stat().st_size,
            "media_type": mimetypes.guess_type(path.name)[0]
            or "application/octet-stream",
        }
    )
