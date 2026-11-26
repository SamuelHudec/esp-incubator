# Annotation editor

From `neuralnet-training`:

```sh
uv run annotator/annotate.py --data data/annotations-camera
```

Opens a local browser editor for all images in `labels.json`.

- **Only images with 0 or multiple boxes** selects images whose box count
  is not one. The list stays fixed while editing so corrected images do not jump
  away; toggle off/on to refresh it. It does not confirm hidden images.
- **Mark remaining as reviewed** accepts all remaining records, including hidden
  images. A confirmation shows how many empty annotations become negatives.
  Existing boxes are preserved; unreadable images block the batch without partial
  changes. Save any current edit first or let the button save it.
- Drag empty space to create a box; drag inside a box to move it.
- Select a box and drag its corners to resize. Delete/Backspace removes it.
- Left/right arrows save and confirm the current image, then navigate.
- Enter saves and confirms without navigating, including the last image.
- Confirming an image with no boxes marks it as a reviewed negative.

Starts at the first unreviewed image. Unreadable images cannot be confirmed;
fix the source file before confirming them.
Edits are saved to `labels.json`; original images are untouched. Camera and extra-source annotations are editable.
Older runs also load missing records from `review_no_faces.json`, without
overwriting existing corrections. The new dataset builder uses only reviewed entries from every source; confirmed
empty boxes are included as negatives.
The first save creates `labels.before-review.json`. Closing with unsaved edits
shows a browser warning. Stop the server with Ctrl+C.

After reviewing a collection, create as many training mixes as needed:

```sh
uv run create_dataset.py --real-data data/annotations-camera --extra-data data/annotations-wider --count 1000 --out data/train-1000
```

No finalize step is needed. Existing `dataset.json` files are snapshots and remain
unchanged; create a new output directory after changing annotations. Do not delete
old experiment manifests to update a collection. See the
[three-stage workflow](../README.md#data-preparation-annotate-once-review-once-mix-many-times)
for reusable collections and mixing multiple extra sources.

Use **Remove image** to exclude the current image from this annotation collection.
Removal takes one click, without a confirmation; the editor advances to the next visible image. This also
works for unreadable images. Original photo files stay on disk because other
collections may reference them. Excluded records retain their annotations for
recovery but are hidden in the editor, skipped by bulk review, size filtering and
new training mixes, and are not reannotated on incremental runs. Existing training
snapshots are unchanged; create a new mix after removal.

Removal preserves the current filtered list and advances to its immediate next
image. Removing the last visible image explicitly reports that the previous image
is being shown. The displayed `#` record number remains stable across removals;
only the visible position/count changes. Toggle the filter to recompute membership.
Navigation regression checks: `node tests/test_annotator_navigation.js` from the
training directory.

The **Only not reviewed** checkbox shows images awaiting review. Combine it with
**Only images with 0 or multiple boxes** to require both conditions. Both filters
keep a stable snapshot while editing or confirming images; toggle either filter
to refresh the list. Excluded images remain hidden.
