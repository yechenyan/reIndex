# Deploy

`render.yaml` is the deployment source of truth. It follows Loom's pattern of a
repository-root Blueprint and package-owned server entrypoint.

The Blueprint defines two paid services in `oregon`:

- `reindex-paradedb`: pinned `paradedb/paradedb:0.24.3-pg18` private image,
  Standard compute and a 10 GB disk mounted at `/var/lib/postgresql`.
- `reindex-api`: Pro Python service with Qwen embedding dependencies,
  pre-deploy schema migration and `/health`.

Render Managed Postgres cannot install `pg_search`, so production search uses
the ParadeDB private service rather than a `databases:` resource. The Blueprint
generates the database password once and copies it to the API with
`fromService`; it never stores a connection string or password in source.
`reindex-server init-db` runs automatically as the API pre-deploy command.

The ParadeDB Community deployment is a single-node search database without
physical BM25 replication or automatic failover. The relational and search
projection must therefore remain rebuildable from ReIndex packages. Move to
ParadeDB Enterprise/BYOC before promising database HA. The current raw/resource
`FileStore` is also local; configure an S3 adapter before horizontally scaling
the API.

Validate before deployment:

```bash
render blueprints validate render.yaml
```

For local development, `DATABASE_URL` can point directly at a ParadeDB
container. Set `REINDEX_EMBEDDINGS=qwen`; there is no process-local search
fallback.
