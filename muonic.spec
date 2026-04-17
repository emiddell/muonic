# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec file for muonic
#
# Build with:
#   pyinstaller muonic.spec
#
# The output will be in dist/muonic/

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all matplotlib data files (includes backends, fonts, etc.)
matplotlib_datas = collect_data_files('matplotlib')

platform_datas = [] if sys.platform == 'win32' else [
    ('bin/which_tty_daq', 'bin'),
]

platform_hiddenimports = (
    ['serial.serialwin32'] if sys.platform == 'win32' else ['serial.serialposix']
)

a = Analysis(
    ['bin/muonic'],
    pathex=["."],
    binaries=[],
    datas=[
        # Application data files (accessed via os.path.dirname(__file__))
        ('muonic/daq/simdaq.txt',            'muonic/daq'),
        ('muonic/gui/daq_commands_help.txt', 'muonic/gui'),
        ('muonic/gui/muonic.xpm',            'muonic/gui'),
    ] + platform_datas + matplotlib_datas,
    hiddenimports=[
        # Matplotlib Qt6 backend (imported dynamically at runtime)
        'matplotlib.backends.backend_qtagg',
        'matplotlib.backends.backend_agg',
        # PyQt6 C extension required by PyQt6 itself
        'PyQt6.sip',
        # scipy submodules that PyInstaller may miss
        'scipy.special._ufuncs_cxx',
        'scipy.linalg.cython_blas',
        'scipy.linalg.cython_lapack',
        'scipy.sparse.csgraph._validation',
        # pyserial - may need explicit inclusion
        'serial',
        'serial.serialutil',
        'muonic',
    ] + platform_hiddenimports,
    hookspath=[],
    hooksconfig={
        "matplotlib": {
            "backends": ["qtagg"],
        },
    },
    runtime_hooks=[],
    excludes=[
        # Exclude unused heavy packages to keep the bundle smaller
        'tkinter',
        '_tkinter',
        # IPython is a dev/analysis tool, not needed by the GUI,
        # and its import-time side effects (rich, colorama) interfere
        # with argparse output and sys.argv in the bootloader context
        'IPython',
        'ipython',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='muonic',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # console=True keeps the terminal visible so logging output is shown
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='muonic',
)
