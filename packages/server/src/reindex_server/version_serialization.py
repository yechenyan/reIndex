from __future__ import annotations


def unique_blobs(manifest: dict) -> dict[str, dict]:
    return {str(item["sha256"]): item for item in manifest["files"]}


def version_json(version, active_version_id: str | None) -> dict:
    return {
        "version_id": version.id,
        "parent_version_id": version.parent_version_id,
        "package_hash": version.package_hash,
        "manifest_sha256": version.manifest_sha256,
        "message": version.message,
        "operation": version.operation,
        "source_version_id": version.source_version_id,
        "created_at": version.created_at.isoformat(),
        "stats": version.stats,
        "is_active": version.id == active_version_id,
    }
