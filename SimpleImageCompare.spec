# PyInstaller spec for Simple Image Compare.
# Produces a single-file binary on Windows/Linux and an .app bundle on macOS.
# Build with:  pyinstaller --clean --noconfirm SimpleImageCompare.spec
import sys
from PyInstaller.utils.hooks import collect_all

# tkinterdnd2 ships Tcl scripts + a native lib that PyInstaller misses by
# default; collect_all picks up the data files, binaries, and hidden imports.
_dnd_datas, _dnd_binaries, _dnd_hidden = collect_all("tkinterdnd2")

a = Analysis(
    ["simple_img_compare.py"],
    pathex=[],
    binaries=_dnd_binaries,
    datas=_dnd_datas,
    hiddenimports=_dnd_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SimpleImageCompare",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="SimpleImageCompare.app",
        icon=None,
        bundle_identifier="com.nickjcoco.simpleimgcompare",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "0.1.0",
        },
    )
