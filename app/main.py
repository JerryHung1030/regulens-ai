"""Entry point for the Regulens-AI application.

This provides a minimal command-line interface that mirrors a subset of the
planned GUI workflow. It loads API settings from ``config_default.yaml`` and
outputs the raw Markdown diff to ``stdout`` or a file.
"""

from __future__ import annotations

import sys
try:  # optional dependency
    import yaml
except Exception:  # pragma: no cover - fallback for minimal environments
    yaml = None  # type: ignore

from .logger import logger
# Import GUI components
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt # Added for Qt.ColorScheme
from .mainwindow import MainWindow
from .settings import Settings
from .translator import Translator
# from pathlib import Path # No longer needed for direct QSS file access here
from .utils.theme_manager import load_qss_with_theme, get_available_themes # Import the new function and get_available_themes
from .utils.font_manager import load_custom_fonts, get_font
from .utils.icon_manager import get_app_icon, get_window_icon
from .utils.windows_taskbar_advanced import initialize_windows_taskbar, set_taskbar_icon

def main(argv: list[str] | None = None) -> None:
    # CLI argument parsing can be added here if needed for GUI configuration
    # For now, we directly launch the GUI.
    logger.info("Application starting...")

    qapp = QApplication(sys.argv if argv is None else [sys.argv[0]] + argv)
    
    # 設定應用程式圖示
    try:
        app_icon = get_app_icon()
        if not app_icon.isNull():
            qapp.setWindowIcon(app_icon)
            logger.info("Application icon set successfully")
        else:
            logger.warning("Failed to load application icon")
    except Exception as e:
        logger.warning(f"Failed to set application icon: {e}")
    
    # 設定 Windows 任務列圖示
    try:
        if sys.platform.startswith('win'):
            # 初始化 Windows 任務列管理器
            if initialize_windows_taskbar("RegulensAI.App"):
                # 使用圖示管理器獲取圖示路徑
                from .utils.icon_manager import get_icon_manager
                icon_manager = get_icon_manager()
                taskbar_icon = icon_manager.get_window_icon()
                if not taskbar_icon.isNull():
                    set_taskbar_icon(str(icon_manager._icons_dir / "icon.ico"))
                    logger.info("Windows taskbar icon setup completed")
                else:
                    logger.warning("No taskbar icon available")
            else:
                logger.warning("Failed to initialize Windows taskbar manager")
    except Exception as e:
        logger.warning(f"Failed to setup Windows taskbar: {e}")
    
    # 載入自定義字體
    load_custom_fonts()
    
    # 設定預設字體
    default_font = get_font('regular', 10)  # 使用較小的字體大小
    qapp.setFont(default_font)

    settings = Settings()  # Load settings (e.g., from config_default.yaml or user settings)
    translator = Translator(settings=settings)  # 傳入 settings 對象

    # Load and apply theme CSS
    theme_setting = settings.get("theme", "default")
    logger.debug(f"Loaded theme setting: {theme_setting}")

    effective_theme_name = ""

    if theme_setting == "system":
        is_dark_mode = qapp.styleHints().colorScheme() == Qt.ColorScheme.Dark
        try:
            themes = get_available_themes()
            if is_dark_mode:
                # 移除 light 和 dark 主題，只考慮其他深色主題
                dark_themes = [t for t in themes if t not in ['light', 'dark']]
                effective_theme_name = dark_themes[0] if dark_themes else "dark"
            else:
                effective_theme_name = "light"
        except Exception:
            effective_theme_name = "dark" if is_dark_mode else "light"
        logger.debug(f"System theme detected: {'Dark' if is_dark_mode else 'Light'}. Effective theme: {effective_theme_name}")
    else:
        try:
            themes = get_available_themes()
            if theme_setting.lower() in themes:
                effective_theme_name = theme_setting.lower()
            else:
                effective_theme_name = "light"
                logger.warning(f"Theme '{theme_setting}' not found, defaulting to 'light'")
        except Exception:
            effective_theme_name = "light"
            logger.warning(f"Error loading themes, defaulting to 'light'")

    if effective_theme_name:
        try:
            logger.debug(f"Attempting to load and apply theme: {effective_theme_name}")
            themed_qss = load_qss_with_theme(effective_theme_name)
            qapp.setStyleSheet(themed_qss)
            logger.debug(f"{effective_theme_name.capitalize()} theme QSS applied successfully.")
        except FileNotFoundError as e:
            logger.error(f"Theme file not found for '{effective_theme_name}': {e}. Please ensure base.qss and theme JSON exist in assets/ and assets/themes/.")
        except Exception as e:
            logger.error(f"Error loading theme '{effective_theme_name}': {e}")
    else:
        # This case should ideally not be reached if we always default to light.
        logger.warning("No effective theme name determined. No theme will be applied.")


    # MainWindow no longer takes CompareManager
    main_window = MainWindow(settings, translator)
    main_window.resize(1100, 900)
    main_window.show()

    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
