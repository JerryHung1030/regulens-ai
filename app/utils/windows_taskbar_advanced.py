"""
Windows 任務列圖示高級處理模組
使用 Windows API 提供更完整的任務列圖示功能
"""

import sys
import os
import ctypes
from pathlib import Path
from typing import Optional, Dict, Any
from PySide6.QtGui import QIcon
from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QWidget

from ..logger import logger

# Windows API 常數
GWL_EXSTYLE = -20
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080

# 任務列按鈕訊息
TB_SETIMAGELIST = 0x0413
TB_GETIMAGELIST = 0x0414

class WindowsTaskbarManager:
    """Windows 任務列管理器"""
    
    def __init__(self):
        self._overlay_icon: Optional[str] = None
        self._app_id: Optional[str] = None
        self._is_initialized = False
        
    def initialize(self, app_id: str = "RegulensAI.App") -> bool:
        """
        初始化 Windows 任務列管理器
        
        Args:
            app_id: 應用程式 ID
            
        Returns:
            bool: 是否成功初始化
        """
        if not sys.platform.startswith('win'):
            logger.debug("非 Windows 平台，跳過初始化")
            return False
        
        try:
            self._app_id = app_id
            self._set_app_user_model_id(app_id)
            self._is_initialized = True
            logger.info(f"Windows 任務列管理器已初始化: {app_id}")
            return True
        except Exception as e:
            logger.error(f"初始化 Windows 任務列管理器失敗: {e}")
            return False
    
    def _set_app_user_model_id(self, app_id: str) -> bool:
        """設定應用程式使用者模型 ID"""
        try:
            # 使用 Windows API 設定應用程式 ID
            if hasattr(ctypes.windll.shell32, 'SetCurrentProcessExplicitAppUserModelID'):
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
                logger.debug(f"已設定應用程式 ID: {app_id}")
                return True
        except Exception as e:
            logger.warning(f"設定應用程式 ID 失敗: {e}")
        
        # 備用方法：設定環境變數
        os.environ['APP_ID'] = app_id
        return True
    
    def set_taskbar_icon(self, icon_path: str) -> bool:
        """
        設定任務列圖示
        
        Args:
            icon_path: 圖示檔案路徑
            
        Returns:
            bool: 是否成功設定
        """
        if not self._is_initialized:
            logger.warning("Windows 任務列管理器未初始化")
            return False
        
        try:
            app = QCoreApplication.instance()
            if app:
                icon = QIcon(icon_path)
                if not icon.isNull():
                    # 設定應用程式圖示
                    app.setWindowIcon(icon)
                    
                    # 強制更新任務列圖示
                    self._force_taskbar_icon_update(icon_path)
                    
                    logger.info(f"任務列圖示已設定: {icon_path}")
                    return True
                else:
                    logger.warning(f"無法載入圖示: {icon_path}")
                    return False
            else:
                logger.warning("QApplication 實例不存在")
                return False
        except Exception as e:
            logger.error(f"設定任務列圖示失敗: {e}")
            return False
    
    def _force_taskbar_icon_update(self, icon_path: str) -> bool:
        """強制更新任務列圖示"""
        try:
            if sys.platform.startswith('win'):
                # 使用 Windows API 強制更新任務列
                import win32gui
                import win32con
                import win32api
                
                # 獲取當前進程的視窗句柄
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    # 設定視窗圖示
                    win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_SMALL, 0)
                    win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_BIG, 0)
                    
                    # 強制重繪任務列
                    win32gui.RedrawWindow(hwnd, None, None, 
                                        win32con.RDW_INVALIDATE | win32con.RDW_UPDATENOW)
                    
                    logger.debug("已強制更新任務列圖示")
                    return True
        except ImportError:
            logger.debug("win32gui 模組不可用，跳過強制更新")
        except Exception as e:
            logger.warning(f"強制更新任務列圖示失敗: {e}")
        
        return False
    
    def set_overlay_icon(self, icon_path: str, description: str = "") -> bool:
        """
        設定任務列覆蓋圖示
        
        Args:
            icon_path: 圖示檔案路徑
            description: 圖示描述
            
        Returns:
            bool: 是否成功設定
        """
        if not self._is_initialized:
            return False
        
        try:
            # 這裡可以實現更複雜的覆蓋圖示邏輯
            # 目前先記錄設定
            self._overlay_icon = icon_path
            logger.debug(f"覆蓋圖示已設定: {icon_path} - {description}")
            return True
        except Exception as e:
            logger.error(f"設定覆蓋圖示失敗: {e}")
            return False
    
    def clear_overlay_icon(self) -> bool:
        """
        清除任務列覆蓋圖示
        
        Returns:
            bool: 是否成功清除
        """
        if not self._is_initialized:
            return False
        
        try:
            self._overlay_icon = None
            logger.debug("覆蓋圖示已清除")
            return True
        except Exception as e:
            logger.error(f"清除覆蓋圖示失敗: {e}")
            return False
    
    def set_window_style(self, widget: QWidget, show_in_taskbar: bool = True) -> bool:
        """
        設定視窗樣式以控制任務列顯示
        
        Args:
            widget: 要設定的視窗元件
            show_in_taskbar: 是否在任務列顯示
            
        Returns:
            bool: 是否成功設定
        """
        if not self._is_initialized:
            return False
        
        try:
            if sys.platform.startswith('win'):
                hwnd = widget.winId().__int__()
                if hwnd:
                    # 獲取當前樣式
                    current_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    
                    if show_in_taskbar:
                        # 移除工具視窗樣式，添加應用程式視窗樣式
                        new_style = current_style & ~WS_EX_TOOLWINDOW | WS_EX_APPWINDOW
                    else:
                        # 添加工具視窗樣式，移除應用程式視窗樣式
                        new_style = current_style | WS_EX_TOOLWINDOW & ~WS_EX_APPWINDOW
                    
                    # 設定新樣式
                    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
                    logger.debug(f"視窗樣式已設定: show_in_taskbar={show_in_taskbar}")
                    return True
        except Exception as e:
            logger.error(f"設定視窗樣式失敗: {e}")
        
        return False
    
    def get_taskbar_info(self) -> Dict[str, Any]:
        """
        獲取任務列資訊
        
        Returns:
            Dict: 任務列資訊
        """
        info = {
            'platform': sys.platform,
            'is_windows': sys.platform.startswith('win'),
            'is_initialized': self._is_initialized,
            'app_id': self._app_id,
            'overlay_icon': self._overlay_icon
        }
        
        if sys.platform.startswith('win'):
            try:
                app = QCoreApplication.instance()
                if app:
                    icon = app.windowIcon()
                    info['has_icon'] = not icon.isNull()
                    info['icon_size'] = icon.actualSize(icon.availableSizes()[0] if icon.availableSizes() else (32, 32))
            except Exception as e:
                logger.warning(f"獲取圖示資訊失敗: {e}")
        
        return info

# 全域任務列管理器實例
_taskbar_manager: Optional[WindowsTaskbarManager] = None

def get_taskbar_manager() -> WindowsTaskbarManager:
    """獲取全域任務列管理器實例"""
    global _taskbar_manager
    if _taskbar_manager is None:
        _taskbar_manager = WindowsTaskbarManager()
    return _taskbar_manager

def initialize_windows_taskbar(app_id: str = "RegulensAI.App") -> bool:
    """初始化 Windows 任務列"""
    return get_taskbar_manager().initialize(app_id)

def set_taskbar_icon(icon_path: str) -> bool:
    """設定任務列圖示"""
    return get_taskbar_manager().set_taskbar_icon(icon_path)

def set_overlay_icon(icon_path: str, description: str = "") -> bool:
    """設定覆蓋圖示"""
    return get_taskbar_manager().set_overlay_icon(icon_path, description)

def clear_overlay_icon() -> bool:
    """清除覆蓋圖示"""
    return get_taskbar_manager().clear_overlay_icon()

def set_window_taskbar_visibility(widget: QWidget, show: bool = True) -> bool:
    """設定視窗在任務列的顯示狀態"""
    return get_taskbar_manager().set_window_style(widget, show)

def get_taskbar_info() -> Dict[str, Any]:
    """獲取任務列資訊"""
    return get_taskbar_manager().get_taskbar_info() 