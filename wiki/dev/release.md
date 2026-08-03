# Package release

This guide publishes the independently installable `reindex` package. It
does not deploy `reindex-server` or provide a hosted API.

## Release contract

- Version source: `packages/cli/pyproject.toml`
- Release entrypoint: `scripts/release_pypi.py`
- Distribution name: `reindex`
- Python import: `reindex`
- Installed command: `rei`
- Credentials: `UV_PUBLISH_TOKEN`, `PYPI_TOKEN`, or `[pypi].token` in the
  gitignored `config/local.toml`

The Python API and CLI read their version from installed package metadata, so
`rei --version`, `reindex.__version__`, and PyPI cannot drift independently.

## Standard flow

Start from a clean worktree. Confirm that the target version has not already
been uploaded, because PyPI files cannot be replaced. Then run one command:

```bash
uv run python scripts/release_pypi.py patch
```

The target may also be `minor`, `major`, or an explicit `X.Y.Z`. The script:

1. updates the CLI version;
2. runs Ruff and the CLI release regression tests;
3. builds one wheel and one source distribution;
4. validates both with Twine;
5. installs the wheel into a clean temporary environment;
6. verifies both commands, package version, `init`, and all bundled skills;
7. publishes only the verified artifacts.

If a step fails after a version bump, the original version is restored. Use
`--keep-version-on-failure` only when intentionally retaining the bump.

## Preflight and TestPyPI

Build and verify without uploading:

```bash
uv run python scripts/release_pypi.py X.Y.Z --skip-publish
```

Test the upload protocol against TestPyPI:

```bash
uv run python scripts/release_pypi.py X.Y.Z --test-pypi
```

`--allow-dirty` is an explicit escape hatch for local release-candidate
testing. Do not use it for a production upload: the published artifact should
always correspond to a reviewable commit.

## Post-publish verification

After the package index reports the new version, install from the index rather
than from the workspace or local wheel:

```bash
uv tool install --force reindex==X.Y.Z
rei --version
rei --help
```

Then run the author workflow against a disposable Collection and API. The full
local HTTP fixture procedure is documented in `testing.md`.
