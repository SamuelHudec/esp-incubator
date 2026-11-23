# Annotation editor

From `neuralnet-training`:

```sh
uv run annotator/annotate.py --data data/mixed-1000
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
use arrows to skip them and fix the source file before finalizing.
Edits are saved to `labels.json`; original images are untouched. Camera and extra-source annotations are editable.
Older runs also load missing records from `review_no_faces.json`, without
overwriting existing corrections. Unreviewed extra-source misses are excluded
by finalize; confirmed empty boxes are included as negatives.
The first save creates `labels.before-review.json`. Closing with unsaved edits
shows a browser warning. Stop the server with Ctrl+C.

After reviewing all real images:

```sh
uv run autolabel.py --finalize data/mixed-1000
```

An existing `dataset.json` is not updated by the editor. Remove that generated
file before finalizing again if it already exists. Keep the same source groups
and split settings when comparing training runs.
