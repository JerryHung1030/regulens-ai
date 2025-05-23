from __future__ import annotations

from pathlib import Path
import sys
import asyncio
from typing import Any

from PySide6.QtCore import QFutureWatcher, Qt
from PySide6.QtConcurrent import run as qt_run
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QProgressDialog,
)

from .api_client import ApiClient
from .compare_manager import CompareManager, CompareError
from .export import to_pdf, to_txt


def _load_config(path: Path) -> dict:
    """Load YAML or simple key:value config."""
    text = path.read_text()
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None
    if yaml is not None:
        return yaml.safe_load(text)
    data: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            data[key.strip()] = val.strip().strip('"')
    return data


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, manager: CompareManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manager = manager
        self._result: str = ""
        self._watcher: QFutureWatcher | None = None
        self.setWindowTitle("Regulens-AI")
        self._init_ui()

    def _init_ui(self) -> None:
        header = QLabel("<h1>Regulens-AI</h1>")

        # input file selector
        self.input_edit = QLineEdit()
        input_browse = QPushButton("Browse")
        input_browse.clicked.connect(self._browse_input)
        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("Input File:"))
        input_row.addWidget(self.input_edit)
        input_row.addWidget(input_browse)

        # reference file selector
        self.ref_edit = QLineEdit()
        ref_browse = QPushButton("Browse")
        ref_browse.clicked.connect(self._browse_reference)
        ref_row = QHBoxLayout()
        ref_row.addWidget(QLabel("Reference File:"))
        ref_row.addWidget(self.ref_edit)
        ref_row.addWidget(ref_browse)

        # parameters
        form = QFormLayout()
        self.param_spin = QSpinBox()
        self.param_spin.setRange(0, 100)
        self.param_spin.setValue(0)
        form.addRow("param", self.param_spin)

        # action buttons
        self.compare_btn = QPushButton("Compare")
        self.compare_btn.clicked.connect(self._do_compare)

        self.export_txt_btn = QPushButton("Export TXT")
        self.export_txt_btn.setEnabled(False)
        self.export_txt_btn.clicked.connect(self._export_txt)

        self.export_pdf_btn = QPushButton("Export PDF")
        self.export_pdf_btn.setEnabled(False)
        self.export_pdf_btn.clicked.connect(self._export_pdf)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.compare_btn)
        btn_row.addWidget(self.export_txt_btn)
        btn_row.addWidget(self.export_pdf_btn)
        btn_row.addStretch()

        # result viewer
        self.viewer = QTextBrowser()

        layout = QVBoxLayout()
        layout.addWidget(header)
        layout.addLayout(input_row)
        layout.addLayout(ref_row)
        layout.addLayout(form)
        layout.addLayout(btn_row)
        layout.addWidget(self.viewer)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    # ----- slots -----
    def _browse_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Input JSON",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if path:
            self.input_edit.setText(path)

    def _browse_reference(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference JSON",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if path:
            self.ref_edit.setText(path)

    def _do_compare(self) -> None:
        input_path = self.input_edit.text()
        ref_path = self.ref_edit.text()
        if not input_path or not ref_path:
            QMessageBox.warning(self, "Missing Files", "Please select both input and reference files")
            return
        self.compare_btn.setEnabled(False)
        self.progress = QProgressDialog("Comparing...", None, 0, 0, self)
        self.progress.setWindowTitle("Please wait")
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setCancelButton(None)
        self.progress.show()

        def task() -> Any:
            return asyncio.run(
                self.manager.acompare(
                    Path(input_path),
                    Path(ref_path),
                    param=self.param_spin.value(),
                )
            )

        self._watcher = QFutureWatcher()
        self._watcher.finished.connect(self._on_compare_done)
        future = qt_run(task)
        self._watcher.setFuture(future)

    def _on_compare_done(self) -> None:
        assert self._watcher is not None
        self.progress.close()
        self.compare_btn.setEnabled(True)
        try:
            resp = self._watcher.result()
        except CompareError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        except Exception as exc:  # pragma: no cover - unexpected
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._result = resp.result
        self.viewer.setPlainText(self._result)
        self.export_txt_btn.setEnabled(True)
        self.export_pdf_btn.setEnabled(True)

    def _export_txt(self) -> None:
        if not self._result:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Text",
            "result.txt",
            "Text Files (*.txt);;All Files (*)",
        )
        if path:
            to_txt(self._result, Path(path))

    def _export_pdf(self) -> None:
        if not self._result:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export PDF",
            "result.pdf",
            "PDF Files (*.pdf);;All Files (*)",
        )
        if path:
            try:
                to_pdf(self._result, Path(path))
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))


def main() -> None:
    app = QApplication(sys.argv)
    cfg = _load_config(Path("config_default.yaml"))
    client = ApiClient(cfg["base_url"], cfg["api_key"], timeout=cfg.get("timeout", 30))
    manager = CompareManager(client)
    win = MainWindow(manager)
    win.resize(800, 600)
    win.show()
    app.exec()


if __name__ == "__main__":
    main()
