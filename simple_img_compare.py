"""Side-by-side image comparison app.

Compare 2–4 images side by side. Click a panel to open a file, or drag an
image onto it. Each panel auto-fits its image and supports independent zoom
(mouse wheel) and pan (click-and-drag). A View ▸ Lock Views toggle syncs
zoom/pan/reset across all panels, and panels can be added/removed from the
File menu.
"""
from __future__ import annotations

import sys
from pathlib import Path
from tkinter import BooleanVar, Canvas, Frame, Menu, Tk, filedialog, messagebox

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

    def __init__(self, master, title: str, on_user_transform=None):
        super().__init__(master, bg="#1e1e1e", bd=1, relief="solid")
        self.title = title
        # Called as on_user_transform(self, kind, **params) after a user-driven
        # zoom/pan/reset so a controller can mirror it to other panes.
        self.on_user_transform = on_user_transform
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
        self.canvas.bind("<Double-Button-1>", lambda e: self._user_reset())
        # Right-click context menu. macOS sends Button-2 for right-click;
        # Control-Click is also a common macOS convention.
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Button-2>", self._on_right_click)
        self.canvas.bind("<Control-Button-1>", self._on_right_click)

        self._menu = Menu(self.canvas, tearoff=0)
        self._menu.add_command(label="Open image...", command=self._open_file_dialog)
        self._menu.add_command(label="Reset view", command=self._user_reset)
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
        self._draw_overlays()

    def _draw_overlays(self):
        """Bottom-left zoom % and bottom-right resolution badges."""
        if self.pil_image is None:
            return
        cw = self.canvas.winfo_width() or 1
        ch = self.canvas.winfo_height() or 1
        pad = 6
        self._draw_badge(pad, ch - pad, f"{self.zoom * 100:.0f}%", anchor="sw")
        self._draw_badge(
            cw - pad, ch - pad,
            f"{self.pil_image.width} × {self.pil_image.height}",
            anchor="se",
        )

    def _draw_badge(self, x, y, text, anchor):
        font = ("TkDefaultFont", 9)
        tid = self.canvas.create_text(
            x, y, text=text, fill="#e6e6e6", font=font, anchor=anchor,
        )
        bbox = self.canvas.bbox(tid)
        if bbox is None:
            return
        bx0, by0, bx1, by1 = bbox
        rid = self.canvas.create_rectangle(
            bx0 - 4, by0 - 2, bx1 + 4, by1 + 2,
            fill="#000000", outline="", stipple="gray50",
        )
        self.canvas.tag_lower(rid, tid)

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
        dx = event.x - ax
        dy = event.y - ay
        self._pan_anchor = (event.x, event.y)
        self.apply_pan(dx, dy)
        if self.on_user_transform:
            self.on_user_transform(self, "pan", dx=dx, dy=dy)

    def apply_pan(self, dx, dy):
        if self.pil_image is None:
            return
        self.offset_x += dx
        self.offset_y += dy
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
        before = self.zoom
        self.apply_zoom(factor, event.x, event.y)
        if self.zoom != before and self.on_user_transform:
            self.on_user_transform(self, "zoom", factor=factor, ex=event.x, ey=event.y)

    def apply_zoom(self, factor, ex, ey):
        if self.pil_image is None:
            return
        new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, self.zoom * factor))
        if new_zoom == self.zoom:
            return
        # Zoom centered on the (ex, ey) canvas point.
        img_x = (ex - self.offset_x) / self.zoom
        img_y = (ey - self.offset_y) / self.zoom
        self.zoom = new_zoom
        self.offset_x = ex - img_x * self.zoom
        self.offset_y = ey - img_y * self.zoom
        self._redraw()

    def _user_reset(self):
        """Reset this pane to fit and notify the controller (for view-lock)."""
        if self.pil_image is None:
            return
        self.reset_view()
        if self.on_user_transform:
            self.on_user_transform(self, "reset")

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


MIN_PANES = 2
MAX_PANES = 4


class App:
    """Owns the window, menu bar, and the set of image panes."""

    def __init__(self, root):
        self.root = root
        self.panes: list[ImagePane] = []
        self.lock_var = BooleanVar(value=False)

        self.container = Frame(root, bg="#111111")
        self.container.pack(fill="both", expand=True, padx=4, pady=4)
        self.container.rowconfigure(0, weight=1)

        self._build_menu()
        for _ in range(MIN_PANES):
            self.add_pane()

    # ---------- menu ----------

    def _build_menu(self):
        menubar = Menu(self.root)

        self.file_menu = Menu(menubar, tearoff=0)
        self.file_menu.add_command(
            label="Add Image", command=self.add_pane, accelerator="Ctrl++"
        )
        self.file_menu.add_command(
            label="Remove Image", command=self.remove_pane, accelerator="Ctrl+-"
        )
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=self.file_menu)

        edit_menu = Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Clear All Images", command=self.clear_all)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        view_menu = Menu(menubar, tearoff=0)
        view_menu.add_checkbutton(
            label="Lock Views (sync zoom/pan)",
            variable=self.lock_var,
            accelerator="Ctrl+L",
        )
        view_menu.add_command(label="Reset All Views", command=self.reset_all)
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)
        self.root.bind("<Control-plus>", lambda e: self.add_pane())
        self.root.bind("<Control-equal>", lambda e: self.add_pane())
        self.root.bind("<Control-minus>", lambda e: self.remove_pane())
        self.root.bind("<Control-l>", lambda e: self.lock_var.set(not self.lock_var.get()))

    def _update_menu_state(self):
        self.file_menu.entryconfigure(
            "Add Image", state="normal" if len(self.panes) < MAX_PANES else "disabled"
        )
        self.file_menu.entryconfigure(
            "Remove Image",
            state="normal" if len(self.panes) > MIN_PANES else "disabled",
        )

    # ---------- panes ----------

    def add_pane(self):
        if len(self.panes) >= MAX_PANES:
            return
        title = f"Image {chr(ord('A') + len(self.panes))}"
        pane = ImagePane(self.container, title, on_user_transform=self._broadcast)
        self.panes.append(pane)
        self._relayout()
        self._update_menu_state()

    def remove_pane(self):
        if len(self.panes) <= MIN_PANES:
            return
        self.panes.pop().destroy()
        self._relayout()
        self._update_menu_state()

    def _relayout(self):
        for i in range(MAX_PANES):
            self.container.columnconfigure(i, weight=0, uniform="")
        last = len(self.panes) - 1
        for i, pane in enumerate(self.panes):
            padx = (0 if i == 0 else 1, 0 if i == last else 1)
            pane.grid(row=0, column=i, sticky="nsew", padx=padx)
            self.container.columnconfigure(i, weight=1, uniform="pane")

    # ---------- view-lock broadcast ----------

    def _broadcast(self, source, kind, **kw):
        if not self.lock_var.get():
            return
        for pane in self.panes:
            if pane is source:
                continue
            if kind == "zoom":
                pane.apply_zoom(kw["factor"], kw["ex"], kw["ey"])
            elif kind == "pan":
                pane.apply_pan(kw["dx"], kw["dy"])
            elif kind == "reset":
                pane.reset_view()

    # ---------- menu actions ----------

    def clear_all(self):
        for pane in self.panes:
            pane.clear_image()

    def reset_all(self):
        for pane in self.panes:
            pane.reset_view()

    def _show_about(self):
        messagebox.showinfo(
            "About Simple Image Compare",
            "Simple Image Compare\n\n"
            "Compare 2–4 images side by side.\n\n"
            "• Click a pane or drag an image onto it to load.\n"
            "• Mouse wheel to zoom, click-drag to pan, double-click to fit.\n"
            "• Right-click a pane for its menu.\n"
            "• View ▸ Lock Views syncs zoom/pan/reset across all panes.",
        )


def main():
    root = TkinterDnD.Tk() if _DND_AVAILABLE else Tk()
    root.title("Simple Image Compare")
    root.geometry("1200x700")
    root.minsize(400, 300)

    app = App(root)

    # Allow passing up to MAX_PANES initial images on the command line.
    for i, path in enumerate(sys.argv[1 : 1 + MAX_PANES]):
        while len(app.panes) <= i:
            app.add_pane()
        pane = app.panes[i]
        pane.after(50, lambda p=pane, src=path: p.load_image(src))

    root.mainloop()


if __name__ == "__main__":
    main()
