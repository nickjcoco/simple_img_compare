"""Side-by-side image comparison app.

Two panels: click to open a file, or drag an image onto a panel. Each panel
auto-fits the image to its size and supports independent zoom (mouse wheel)
and pan (click-and-drag).
"""
from __future__ import annotations

import sys
from pathlib import Path
from tkinter import Canvas, Frame, Menu, Tk, filedialog

from PIL import Image, ImageTk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp", ".ico"}
MIN_ZOOM = 0.05
MAX_ZOOM = 40.0
ZOOM_STEP = 1.15


class ImagePane(Frame):
    """A single image panel: load via click or drag-drop, zoom, and pan."""

    def __init__(self, master, title: str):
        super().__init__(master, bg="#1e1e1e", bd=1, relief="solid")
        self.title = title
        self.pil_image: Image.Image | None = None
        self.tk_image: ImageTk.PhotoImage | None = None
        self.zoom: float = 1.0
        self.fit_zoom: float = 1.0
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0
        self._pan_anchor: tuple[int, int] | None = None
        self._image_id: int | None = None
        self._placeholder_id: int | None = None

        self.canvas = Canvas(
            self, bg="#1e1e1e", highlightthickness=0, cursor="hand2"
        )
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._on_left_click)
        self.canvas.bind("<B1-Motion>", self._on_pan)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        # Mouse wheel: Windows/macOS use <MouseWheel>, X11 uses Button-4/5.
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", self._on_wheel)
        self.canvas.bind("<Button-5>", self._on_wheel)
        # Double-click resets the view to fit.
        self.canvas.bind("<Double-Button-1>", lambda e: self.reset_view())
        # Right-click context menu. macOS sends Button-2 for right-click;
        # Control-Click is also a common macOS convention.
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Button-2>", self._on_right_click)
        self.canvas.bind("<Control-Button-1>", self._on_right_click)

        self._menu = Menu(self.canvas, tearoff=0)
        self._menu.add_command(label="Open image...", command=self._open_file_dialog)
        self._menu.add_command(label="Reset view", command=self.reset_view)
        self._menu.add_separator()
        self._menu.add_command(label="Clear image", command=self.clear_image)

        if _DND_AVAILABLE:
            self.canvas.drop_target_register(DND_FILES)
            self.canvas.dnd_bind("<<Drop>>", self._on_drop)

        self._draw_placeholder()

    # ---------- placeholder / drawing ----------

    def _draw_placeholder(self):
        self.canvas.delete("all")
        self._image_id = None
        w = self.canvas.winfo_width() or 1
        h = self.canvas.winfo_height() or 1
        msg = f"{self.title}\n\nClick to choose an image"
        if _DND_AVAILABLE:
            msg += "\nor drag one here"
        self._placeholder_id = self.canvas.create_text(
            w // 2, h // 2,
            text=msg,
            fill="#888888",
            font=("TkDefaultFont", 12),
            justify="center",
        )

    def _redraw(self):
        if self.pil_image is None:
            self._draw_placeholder()
            return
        self.canvas.delete("all")
        self._placeholder_id = None
        w = max(1, int(self.pil_image.width * self.zoom))
        h = max(1, int(self.pil_image.height * self.zoom))
        # PIL's high-quality resample for the displayed size.
        resized = self.pil_image.resize((w, h), Image.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)
        self._image_id = self.canvas.create_image(
            self.offset_x, self.offset_y,
            image=self.tk_image, anchor="nw",
        )

    # ---------- loading ----------

    def load_image(self, path: str | Path):
        try:
            img = Image.open(path)
            img.load()
        except (OSError, ValueError) as e:
            self.canvas.delete("all")
            self.canvas.create_text(
                (self.canvas.winfo_width() or 1) // 2,
                (self.canvas.winfo_height() or 1) // 2,
                text=f"Could not open image:\n{e}",
                fill="#ff8888",
                font=("TkDefaultFont", 11),
                justify="center",
            )
            return
        self.pil_image = img.convert("RGBA") if img.mode not in ("RGB", "RGBA") else img
        self.reset_view()

    def clear_image(self):
        """Remove the loaded image and restore the placeholder."""
        self.pil_image = None
        self.tk_image = None
        self.zoom = 1.0
        self.fit_zoom = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self._pan_anchor = None
        self._image_id = None
        self.canvas.configure(cursor="hand2")
        self._draw_placeholder()

    def reset_view(self):
        """Fit the image to the canvas, centered."""
        if self.pil_image is None:
            return
        cw = self.canvas.winfo_width() or 1
        ch = self.canvas.winfo_height() or 1
        zx = cw / self.pil_image.width
        zy = ch / self.pil_image.height
        self.fit_zoom = max(MIN_ZOOM, min(zx, zy))
        self.zoom = self.fit_zoom
        dw = self.pil_image.width * self.zoom
        dh = self.pil_image.height * self.zoom
        self.offset_x = (cw - dw) / 2
        self.offset_y = (ch - dh) / 2
        self._redraw()

    # ---------- event handlers ----------

    def _on_resize(self, event):
        if self.pil_image is None:
            self._draw_placeholder()
            return
        # If currently at (or near) fit zoom, keep it fitted on resize.
        if abs(self.zoom - self.fit_zoom) < 1e-6:
            self.reset_view()
        else:
            self._redraw()

    def _on_left_click(self, event):
        # Either start a pan, or — if there's no image yet — open a file dialog.
        if self.pil_image is None:
            self._open_file_dialog()
            return
        self._pan_anchor = (event.x, event.y)
        self.canvas.configure(cursor="fleur")

    def _on_pan(self, event):
        if self._pan_anchor is None or self.pil_image is None:
            return
        ax, ay = self._pan_anchor
        self.offset_x += event.x - ax
        self.offset_y += event.y - ay
        self._pan_anchor = (event.x, event.y)
        if self._image_id is not None:
            self.canvas.coords(self._image_id, self.offset_x, self.offset_y)

    def _on_release(self, event):
        self._pan_anchor = None
        self.canvas.configure(cursor="hand2")

    def _on_wheel(self, event):
        if self.pil_image is None:
            return
        # Normalize wheel direction across platforms.
        if event.num == 4:
            direction = 1
        elif event.num == 5:
            direction = -1
        else:
            direction = 1 if event.delta > 0 else -1
        factor = ZOOM_STEP if direction > 0 else 1 / ZOOM_STEP
        new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, self.zoom * factor))
        if new_zoom == self.zoom:
            return
        # Zoom centered on the cursor position.
        img_x = (event.x - self.offset_x) / self.zoom
        img_y = (event.y - self.offset_y) / self.zoom
        self.zoom = new_zoom
        self.offset_x = event.x - img_x * self.zoom
        self.offset_y = event.y - img_y * self.zoom
        self._redraw()

    def _on_right_click(self, event):
        state = "normal" if self.pil_image is not None else "disabled"
        # Items: 0 Open, 1 Reset, 2 sep, 3 Clear
        self._menu.entryconfigure(1, state=state)
        self._menu.entryconfigure(3, state=state)
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    def _on_drop(self, event):
        path = _parse_dnd_path(event.data)
        if path:
            self.load_image(path)

    def _open_file_dialog(self):
        path = filedialog.askopenfilename(
            title=f"Choose image for {self.title}",
            filetypes=[
                ("Images", " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTS))),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.load_image(path)


def _parse_dnd_path(data: str) -> str | None:
    """tkinterdnd2 returns a Tcl list; paths with spaces are wrapped in braces."""
    data = data.strip()
    if not data:
        return None
    if data.startswith("{"):
        end = data.find("}")
        if end != -1:
            return data[1:end]
    return data.split()[0]


def main():
    root = TkinterDnD.Tk() if _DND_AVAILABLE else Tk()
    root.title("Simple Image Compare")
    root.geometry("1200x700")
    root.minsize(400, 300)

    container = Frame(root, bg="#111111")
    container.pack(fill="both", expand=True, padx=4, pady=4)
    container.columnconfigure(0, weight=1, uniform="pane")
    container.columnconfigure(1, weight=1, uniform="pane")
    container.rowconfigure(0, weight=1)

    left = ImagePane(container, "Image A")
    right = ImagePane(container, "Image B")
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
    right.grid(row=0, column=1, sticky="nsew", padx=(2, 0))

    # Allow passing initial images on the command line.
    if len(sys.argv) > 1:
        left.after(50, lambda: left.load_image(sys.argv[1]))
    if len(sys.argv) > 2:
        right.after(50, lambda: right.load_image(sys.argv[2]))

    root.mainloop()


if __name__ == "__main__":
    main()
