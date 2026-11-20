# Annotation editor

From `neuralnet-training`:

```sh
uv run annotator/annotate.py --data data/mixed-1000
```

Opens a local browser editor for real images in `labels.json`.

- Drag empty space to create a box; drag inside a box to move it.
- Select a box and drag its corners to resize. Delete/Backspace removes it.
- Left/right arrows save and confirm the current image, then navigate.
- Enter saves and confirms without navigating, including the last image.
- Confirming an image with no boxes marks it as a reviewed negative.

Starts at the first unreviewed image. Unreadable images cannot be confirmed;
use arrows to skip them and fix the source file before finalizing.
Edits are saved to `labels.json`; originals and synthetic records are untouched.
The first save creates `labels.before-review.json`. Closing with unsaved edits
shows a browser warning. Stop the server with Ctrl+C.

After reviewing all real images:

```sh
uv run autolabel.py --finalize data/mixed-1000
```

An existing `dataset.json` is not updated by the editor. Remove that generated
file before finalizing again if it already exists. Keep the same source groups
and split settings when comparing training runs.
