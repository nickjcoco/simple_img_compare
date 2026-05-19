# simple_img_compare

Simple side-by-side image compare app. Cross-platform — anywhere Python and Tk
are available (Windows, macOS, Linux).

## Install

```
pip install -r requirements.txt
```

`Pillow` is required. `tkinterdnd2` is optional but enables drag-and-drop;
the app still works (click-to-open) without it. Tk ships with the standard
Python installers on Windows and macOS; on Linux install your distro's
`python3-tk` package.

## Run

```
python simple_img_compare.py
```

Optionally pass one or two image paths to preload them:

```
python simple_img_compare.py left.png right.png
```

## Controls (per panel)

- Click an empty panel to open a file picker.
- Drag an image file onto a panel to load it (requires `tkinterdnd2`).
- Mouse wheel to zoom in/out (centered on the cursor).
- Click and drag to pan.
- Double-click to reset to fit.

