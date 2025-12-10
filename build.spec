# build.spec

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Dahil edilmesi gereken Python modülleri (Otomatik bulunamayanlar buraya)
hidden_imports = [
    'mysql.connector', 
    'mysql', 
    'clr', 
    'System', 
    'Bio.TrustFinger', 
    'Aratek.TrustFinger',
    'PIL',
    'cv2',
    'pygame'
]

a = Analysis(
    ['main.py'],  # Ana giriş dosyanız
    pathex=[],
    binaries=[],
    datas=[], 
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RSA_PAKS',  # EXE'nin adı
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Hata görmek için önce True yapın, her şey tamamsa False yaparsınız
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RSA_PAKS',
)