# Block classification task

Classify only the supplied uncertain blocks using each full-page overview plus
its high-resolution union-region crop. The crop is the primary evidence for
small table grids; the overview supplies page context. Correct LiteParse's type,
bbox, splits, and merges.

- Preserve every supplied source block ID in at least one returned item.
- Multiple source blocks may map to one item; one source block may be split
  into multiple items when the image clearly contains distinct regions.
- For every table-like source block, compare its bbox with the visible grid.
  Return a tight bbox for exactly one complete logical table, including its
  first visible row and every later row. Do not return a row fragment, and do not let
  padding include an adjacent table.
- If one LiteParse block crosses two adjacent table grids (for example, the last
  row of one table plus the first row of the next), you must return two items
  with unique classifyBlockIds and the same sourceBlockId. Give each item the
  complete visual bbox of its own table; never choose just one of the tables.
- Use `table` for native-text tables, `image_table` for tables whose cells are
  pixels, `figure` for non-table images/charts, `text` for misclassified normal
  content, `formula` for formulas, and `skip` for decorative/noise content.
- `canMergePrevious` is true when this item may continue the preceding table
  on the same or immediately preceding page. When uncertain, use true.
- A first row that belongs to the following data region does not merge with an
  unrelated preceding table; the following data item should point back to it.
- Bboxes must stay within the page.
- Use the supplied overlap IDs and native table row previews. When a large
  LiteParse table bbox contains smaller logical tables, avoid duplicating the
  same physical content: narrow the parent to its unique data region or mark a
  truly duplicate representation as `skip`.

Before returning, perform a visual coverage audit from top to bottom across the
union of all supplied overlapping block regions on each full-page screenshot:

- Every visually distinct table grid that intersects that union must appear
  exactly once as a returned table item when it contains meaningful visible cell
  content. A completely blank colored box, empty single-cell input area, or
  decorative layout frame is not an extraction table; do not create a table
  task for it. Do this even when no small source bbox tightly encloses a real
  content-bearing grid; split a large overlapping parent source block and reuse
  its sourceBlockId when necessary.
- A source bbox is evidence about LiteParse's grouping, not a boundary that may
  hide the beginning or end of a visual table. Compare nearby lines, spacing,
  column count, and titles in the screenshot before deciding the complete bbox.
- List the audited visual tables mentally in page/y order, then check that the
  returned table items have the same count and coverage with neither gaps nor
  duplicates. Runtime will validate only IDs and page bounds; it will not repair
  your bbox or discover omitted grids with static vector-line rules.
