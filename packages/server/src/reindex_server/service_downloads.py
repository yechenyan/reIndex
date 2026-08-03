from __future__ import annotations

import io
import zipfile

from .domain import Collection
from .push_protocol import load_snapshot_from_manifest
from .storage import object_key


class ServiceDownloadMixin:
    def pull(
        self, name: str, version_id: str | None = None
    ) -> tuple[bytes, Collection, str, str]:
        collection = self.resolve_collection(name)
        if version_id:
            fetched = self.fetch_version(name, version_id)
            output = io.BytesIO()
            with zipfile.ZipFile(
                output, "w", compression=zipfile.ZIP_DEFLATED
            ) as bundle:
                for item in fetched["manifest"]["files"]:
                    if item["namespace"] != "package" or not item[
                        "logical_path"
                    ].endswith(".node.md"):
                        continue
                    with self.store.open(object_key(item["sha256"])) as stream:
                        bundle.writestr(item["logical_path"], stream.read())
            return (
                output.getvalue(),
                collection,
                fetched["version"]["version_id"],
                fetched["version"]["package_hash"],
            )
        nodes = self.browse(collection.id, None, recursive=True)
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for summary in sorted(nodes, key=lambda value: value.path):
                node = self.get_node(collection.id, summary.id)
                card = node.link("card")
                if card is None:
                    raise KeyError(f"Node has no card resource: {node.path}")
                with self.store.open(card.resource.object_key) as stream:
                    bundle.writestr(node.path, stream.read())
        return (
            output.getvalue(),
            collection,
            collection.active_version_id or "",
            collection.package_hash or "",
        )

    def version_snapshot(self, name: str, version_id: str):
        fetched = self.fetch_version(name, version_id)
        return load_snapshot_from_manifest(
            fetched["manifest"], fetched["collection_id"], self.store
        )
