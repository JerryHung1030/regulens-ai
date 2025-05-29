from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QPushButton,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QStyle,
)

from app.models.project import CompareProject


class ProjectEditor(QWidget):
    """用於選擇檔案與啟動比較的介面"""

    compare_requested = Signal(CompareProject)

    def __init__(self, project: CompareProject, parent: QWidget | None = None):
        super().__init__(parent)
        self.project = project
        self._build_ui()
        self.project.changed.connect(self._refresh)
        self._refresh()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignTop)
        lay.setSpacing(20)
        lay.setContentsMargins(20, 20, 20, 20)

        # 專案標題和操作按鈕
        title_row = QHBoxLayout()
        title = QLabel(f"<h2>{self.project.name}</h2>")
        title.setStyleSheet("margin: 0;")
        title_row.addWidget(title)

        # 重命名按鈕
        btn_rename = QToolButton()
        btn_rename.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        btn_rename.setToolTip("重命名專案")
        btn_rename.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 4px;
                border-radius: 4px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
        """)
        btn_rename.clicked.connect(self._rename_project)
        title_row.addWidget(btn_rename)

        # 刪除按鈕
        btn_delete = QToolButton()
        btn_delete.setIcon(self.style().standardIcon(QStyle.SP_DialogDiscardButton))
        btn_delete.setToolTip("刪除專案")
        btn_delete.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 4px;
                border-radius: 4px;
            }
            QToolButton:hover {
                background-color: #ffebee;
            }
        """)
        btn_delete.clicked.connect(self._delete_project)
        title_row.addWidget(btn_delete)

        title_row.addStretch()
        lay.addLayout(title_row)

        # 檔案上傳區域
        upload_frame = QWidget()
        upload_frame.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        upload_lay = QVBoxLayout(upload_frame)
        upload_lay.setSpacing(16)

        # 內規上傳
        input_group = QWidget()
        input_lay = QVBoxLayout(input_group)
        input_lay.setSpacing(8)
        
        input_label = QLabel("內規檔案")
        input_label.setStyleSheet("font-weight: bold;")
        input_lay.addWidget(input_label)
        
        input_btn = QPushButton("選擇內規 JSON")
        input_btn.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        input_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                background-color: white;
                border: 1px solid #e0e0e0;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        input_btn.clicked.connect(self._choose_input)
        input_lay.addWidget(input_btn)
        
        self.lbl_input = QLabel("<i>未選擇</i>")
        self.lbl_input.setStyleSheet("color: #666;")
        input_lay.addWidget(self.lbl_input)
        
        upload_lay.addWidget(input_group)

        # 外規上傳
        ref_group = QWidget()
        ref_lay = QVBoxLayout(ref_group)
        ref_lay.setSpacing(8)
        
        ref_label = QLabel("外規檔案")
        ref_label.setStyleSheet("font-weight: bold;")
        ref_lay.addWidget(ref_label)
        
        ref_btn = QPushButton("選擇外規 JSON")
        ref_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        ref_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                background-color: white;
                border: 1px solid #e0e0e0;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        ref_btn.clicked.connect(self._add_refs)
        ref_lay.addWidget(ref_btn)
        
        self.lbl_refs = QLabel("<i>未選擇</i>")
        self.lbl_refs.setStyleSheet("color: #666;")
        ref_lay.addWidget(self.lbl_refs)
        
        upload_lay.addWidget(ref_group)
        lay.addWidget(upload_frame)

        # 比較按鈕
        self.btn_compare = QPushButton("開始比較")
        self.btn_compare.setStyleSheet("""
            QPushButton {
                padding: 12px 24px;
                border-radius: 6px;
                background-color: #2196f3;
                color: white;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:disabled {
                background-color: #bdbdbd;
            }
        """)
        self.btn_compare.clicked.connect(lambda: self.compare_requested.emit(self.project))
        lay.addWidget(self.btn_compare, alignment=Qt.AlignCenter)
        lay.addStretch()

    def _rename_project(self):
        name, ok = QInputDialog.getText(
            self,
            "重命名專案",
            "請輸入新的專案名稱：",
            text=self.project.name
        )
        if ok and name:
            self.project.rename(name)  # Emits project.updated

    def _delete_project(self):
        reply = QMessageBox.question(
            self,
            "確認刪除",
            f"確定要刪除專案「{self.project.name}」嗎？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.project.deleted.emit()

    # ------ File pickers ----------------------------------------------
    def _choose_input(self):
        path, _ = QFileDialog.getOpenFileName(self, "選擇內規 JSON", "", "JSON Files (*.json)")
        self.project.set_input(Path(path) if path else None)

    def _add_refs(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "選擇外規 JSON", "", "JSON Files (*.json)")
        if paths:
            self.project.set_refs([Path(p) for p in paths])

    # ------------------------------------------------------------------
    def _refresh(self):
        """更新 UI 顯示"""
        # 更新標題
        title = self.findChild(QLabel)
        if title:
            title.setText(f"<h2>{self.project.name}</h2>")
        
        # 更新檔案路徑顯示
        self.lbl_input.setText(str(self.project.input_path) if self.project.input_path else "<i>未選擇</i>")
        if self.project.ref_paths:
            self.lbl_refs.setText("\n".join(str(p) for p in self.project.ref_paths))
        else:
            self.lbl_refs.setText("<i>未選擇</i>")
        self.btn_compare.setEnabled(self.project.ready)
