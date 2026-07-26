# Deploy

`render.yaml` is the deployment source of truth. It follows Loom's pattern of a
repository-root Blueprint and package-owned server entrypoint.

The current Blueprint defines one Python web service:

- service: `reindex-api`
- package: `packages/server`
- command: `reindex-server run --port $PORT`
- health check: `/health`

Validate before deployment:

```bash
render blueprints validate
```

No database or persistent disk is declared yet. Add those only when the storage
contract is implemented and documented.

