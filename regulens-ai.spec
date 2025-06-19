# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# collect tiktoken data files (e.g. JSON encodings)
datas_tiktoken = collect_data_files('tiktoken')
# collect all tiktoken_ext submodules for hidden-import
hiddenimports_tiktoken = collect_submodules('tiktoken_ext') + ['tiktoken_ext.openai_public']

# existing data files
datas = [
    ('assets', 'assets'),
    ('config_default.yaml', '.'),
    ('sample_data', 'sample_data'),
    ('sample_data/sample2_符合規範Demo', 'sample_data/sample2_符合規範Demo'),
    ('sample_data/sample3_不符合規範Demo', 'sample_data/sample3_不符合規範Demo'),
    ('sample_data/sample2_符合規範Demo/external_regulations', 'sample_data/sample2_符合規範Demo/external_regulations'),
    ('sample_data/sample2_符合規範Demo/procedures', 'sample_data/sample2_符合規範Demo/procedures'),
    ('sample_data/sample3_不符合規範Demo/external_regulations', 'sample_data/sample3_不符合規範Demo/external_regulations'),
    ('sample_data/sample3_不符合規範Demo/procedures', 'sample_data/sample3_不符合規範Demo/procedures'),
] + datas_tiktoken

# existing hidden imports
hiddenimports = [
    'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
    'PySide6.QtSvg', 'PySide6.QtSvgWidgets',
    'openai', 'faiss', 'numpy', 'pandas', 'pydantic',
    'loguru', 'yaml', 'weasyprint', 'pdfkit', 'langchain',
    'requests', 'aiohttp', 'httpx', 'sqlalchemy', 'tqdm',
    'tenacity', 'markdown', 'lxml', 'cssselect2', 'tinycss2',
    'webencodings', 'pypdf', 'python-docx', 'pillow', 'fonttools',
    'pyphen', 'pydyf', 'tinyhtml5', 'zopfli', 'Brotli',
    'certifi', 'charset-normalizer', 'idna', 'urllib3',
    'multidict', 'yarl', 'frozenlist', 'aiosignal',
    'attrs', 'sniffio', 'anyio', 'httpcore', 'h11',
    'greenlet', 'cffi', 'pycparser', 'packaging',
    'python-dateutil', 'pytz', 'six', 'regex',
    'typing_extensions', 'mypy_extensions', 'annotated_types',
    'pydantic_core', 'typing_inspect', 'typing_inspection',
    'iniconfig', 'pluggy', 'propcache', 'jiter', 'mdurl',
    'markdown_it_py', 'marshmallow', 'dataclasses_json',
    'distro', 'numexpr', 'pyarrow', 'QtPy', 'shiboken6',
    'tzdata', 'vcrpy', 'aiohappyeyeballs', 'langsmith',
    # (…any others you rely on…)
] + hiddenimports_tiktoken

a = Analysis(
    ['run_app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'scipy', 'IPython', 'jupyter',
        'notebook', 'pytest', 'test', 'tests', 'unittest',
        'doctest', 'pdb', 'profile', 'cProfile', 'trace',
        'venv', '.venv', 'virtualenv',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RegulensAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 隱藏控制台視窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icons/icon.ico',
)
