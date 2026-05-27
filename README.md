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

Optionally pass up to four image paths to preload them:

```
python simple_img_compare.py a.png b.png
```

## Controls (per panel)

- Click an empty panel to open a file picker.
- Drag an image file onto a panel to load it (requires `tkinterdnd2`).
- Mouse wheel to zoom in/out (centered on the cursor).
- Click and drag to pan.
- Double-click to reset to fit.
- Right-click for a menu: Open / Reset view / Clear image.

## Menu bar

- **File** — Add Image / Remove Image (compare between 2 and 4 panels at once),
  Exit.
- **Edit** — Clear All Images.
- **View** — Lock Views (sync zoom/pan), Reset All Views.
- **Help** — About.

### Lock Views

With **View ▸ Lock Views** enabled (or `Ctrl+L`), zooming, panning, or resetting
one panel applies the same operation to every other panel, so the images move
in unison. Disable it to manipulate each panel independently again.

