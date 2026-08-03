# Independent visual audit

Create the reference before reading extractor output. Record the source SHA-256,
frozen inventory SHA-256, expected table IDs, header, total row count, total
column count, and source-derived row samples.

Use these sample indices for a table with `n` data rows:

- `n = 0`: fail unless the inventory explicitly allows an empty table.
- `n = 1`: sample row 0 once.
- `n = 2` or `n = 3`: sample every row.
- `n >= 4`: sample rows 0, 1, `n-2`, and `n-1`.

For multi-page tables, also sample a row around each continuation boundary and at
least one middle-page row. Preserve exact visible text except for Unicode and
whitespace normalization. If the extractor intentionally normalizes a value,
record both the visual source value and expected normalized value; the validator
compares the latter.

The reference must never be imported by `extractor.py`. Freeze it by recording
its SHA-256 in the audit record. A source hash mismatch is a new fixture, not a
silent reference update.

To reduce wall time without reducing coverage, partition frozen table IDs among
available Agents after the inventory audit. Give each Agent only the source crop
and neutral geometry for its assigned tables, never extractor output. Merge the
fragments in inventory order, then have the primary Agent visually confirm every
header and sample before freezing. Parallel drafting replaces typing latency; it
does not replace the primary visual check.
