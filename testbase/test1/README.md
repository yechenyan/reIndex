# test1: Bielefelder Netz GmbH Netzausbauplan 2022

This fixture contains:

- `raw/2022_07_28_..._pdf.pdf`: unchanged five-page source PDF
- `reIndex/`: generated `reindex/node@0.1` package
- `build_reindex.py`: reproducible build entrypoint
- `fixture_extract.py`: semantic text, cell-grid table, and image extraction
- `fixture_nodes.py`: Node, CSV, frontmatter, hash, and preview writers

Rebuild from the repository root:

```bash
uv run --package reindex-cli python testbase/test1/build_reindex.py
```

## Generated package

The PDF becomes a document group with six ordered children:

1. title, contents, and introduction text;
2. the original embedded 110kV network map;
3. planning-basis text;
4. expansion, services, and other text;
5. normalized aggregate investment table with complete CSV and a high-resolution
   visual companion;
6. complete 52-row, 20-column measures table with CSV and a high-resolution
   visual companion.

The table extractor uses the PDF's actual vector grid and word coordinates. It
does not infer missing values. Text line wraps are normalized, while companion
PNGs preserve the original visual layout for verification. These PNGs are
representations of their tables, not independent image Nodes.
