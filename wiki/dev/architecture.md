# Architecture

ReIndex is a Python uv workspace with independently publishable packages.

```text
packages/cli     local build, upload, search, browse, get, and query commands
packages/server  HTTP service and future storage/index integrations
testbase         raw fixtures, reproducible builders, and generated packages
wiki             protocol, user, and developer documentation
tasks            active work and reviewed history
```

The canonical layer is the file package described by the v0.1 standard. PostgreSQL,
full-text indexes, embeddings, and object storage are derived serving layers and
must not replace the source package as protocol truth. Their agreed v0.1 service
contract is documented in [`backend-service.md`](backend-service.md); the runtime
implementation is intentionally still limited to `/health`.

The initial fixture proves the `raw PDF -> Node tree` boundary. Database upload
and query behavior are intentionally left for later tasks.
