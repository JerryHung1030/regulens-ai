"""
圖示管理模組
提供統一的圖示載入和管理功能
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSize

from ..logger import logger

def get_resource_path(relative_path: str) -> Path:
    """獲取資源檔案的路徑，支援 PyInstaller 打包後的路徑"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包後的路徑
        base_path = Path(sys._MEIPASS)
    else:
        # 開發環境的路徑
        base_path = Path(__file__).parent.parent.parent
    
    return base_path / relative_path

class IconManager:
    """圖示管理器"""
    
    def __init__(self):
        self._icons_cache: Dict[str, QIcon] = {}
        self._icons_dir = self._get_icons_directory()
        self._load_icon_config()
    
    def _get_icons_directory(self) -> Path:
        """獲取圖示目錄路徑"""
        # 使用新的路徑解析方法
        icons_dir = get_resource_path("assets/icons")
        
        if not icons_dir.exists():
            logger.warning(f"圖示目錄不存在: {icons_dir}")
            # 嘗試相對路徑
            icons_dir = Path("assets/icons")
        
        return icons_dir
    
    def _load_icon_config(self):
        """載入圖示設定"""
        self.icon_config = {
            'main_icon': 'logo.png',
            'sizes': [16, 32, 48, 64, 128, 256],
            'formats': ['png', 'ico']
        }
        
        # 嘗試載入自定義設定
        config_file = self._icons_dir / "icon_config.py"
        if config_file.exists():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("icon_config", config_file)
                config_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(config_module)
                
                if hasattr(config_module, 'MAIN_ICON'):
                    self.icon_config['main_icon'] = str(config_module.MAIN_ICON)
                if hasattr(config_module, 'ICON_SIZES'):
                    self.icon_config['sizes'] = list(config_module.ICON_SIZES.keys())
                    
                logger.debug("已載入自定義圖示設定")
            except Exception as e:
                logger.warning(f"載入圖示設定失敗: {e}")
    
    def get_icon(self, name: str, size: Optional[int] = None) -> QIcon:
        """
        獲取圖示
        
        Args:
            name: 圖示名稱（不包含副檔名）
            size: 圖示尺寸，如果為 None 則使用預設圖示
            
        Returns:
            QIcon 物件
        """
        cache_key = f"{name}_{size}" if size else name
        
        if cache_key in self._icons_cache:
            return self._icons_cache[cache_key]
        
        # 嘗試載入圖示
        icon_path = self._find_icon_file(name, size)
        if icon_path and icon_path.exists():
            icon = QIcon(str(icon_path))
            self._icons_cache[cache_key] = icon
            logger.debug(f"已載入圖示: {icon_path}")
            return icon
        else:
            logger.warning(f"找不到圖示: {name} (size: {size})")
            # 返回空圖示
            return QIcon()
    
    def _find_icon_file(self, name: str, size: Optional[int] = None) -> Optional[Path]:
        """尋找圖示檔案"""
        # 如果指定了尺寸，優先尋找對應尺寸的檔案
        if size:
            # 嘗試 PNG 格式
            png_path = self._icons_dir / f"{name}_{size}x{size}.png"
            if png_path.exists():
                return png_path
            
            # 嘗試 ICO 格式
            ico_path = self._icons_dir / f"{name}.ico"
            if ico_path.exists():
                return ico_path
        
        # 嘗試預設圖示檔案
        default_paths = [
            self._icons_dir / f"{name}.png",
            self._icons_dir / f"{name}.ico",
            self._icons_dir / self.icon_config['main_icon']
        ]
        
        for path in default_paths:
            if path.exists():
                return path
        
        return None
    
    def get_app_icon(self) -> QIcon:
        """獲取應用程式主圖示"""
        return self.get_icon("logo")
    
    def get_window_icon(self) -> QIcon:
        """獲取視窗圖示（通常使用較大尺寸）"""
        # 嘗試獲取 32x32 或 48x48 的圖示
        for size in [32, 48, 64]:
            icon = self.get_icon("logo", size)
            if not icon.isNull():
                return icon
        
        # 如果沒有找到特定尺寸，使用預設圖示
        return self.get_app_icon()
    
    def get_toolbar_icon(self) -> QIcon:
        """獲取工具列圖示（通常使用較小尺寸）"""
        # 嘗試獲取 16x16 或 32x32 的圖示
        for size in [16, 32]:
            icon = self.get_icon("logo", size)
            if not icon.isNull():
                return icon
        
        # 如果沒有找到特定尺寸，使用預設圖示
        return self.get_app_icon()
    
    def list_available_icons(self) -> Dict[str, Any]:
        """列出可用的圖示"""
        available_icons = {}
        
        if not self._icons_dir.exists():
            return available_icons
        
        for file_path in self._icons_dir.glob("*"):
            if file_path.is_file() and file_path.suffix.lower() in ['.png', '.ico']:
                size_info = self._extract_size_from_filename(file_path.name)
                available_icons[file_path.name] = {
                    'path': str(file_path),
                    'size': size_info,
                    'format': file_path.suffix.lower()[1:]  # 移除點號
                }
        
        return available_icons
    
    def _extract_size_from_filename(self, filename: str) -> Optional[int]:
        """從檔案名稱中提取尺寸資訊"""
        import re
        match = re.search(r'(\d+)x(\d+)', filename)
        if match:
            width, height = map(int, match.groups())
            if width == height:  # 確保是正方形
                return width
        return None
    
    def clear_cache(self):
        """清除圖示快取"""
        self._icons_cache.clear()
        logger.debug("圖示快取已清除")

# 全域圖示管理器實例
_icon_manager: Optional[IconManager] = None

def get_icon_manager() -> IconManager:
    """獲取全域圖示管理器實例"""
    global _icon_manager
    if _icon_manager is None:
        _icon_manager = IconManager()
    return _icon_manager

def get_app_icon() -> QIcon:
    """獲取應用程式圖示"""
    return get_icon_manager().get_app_icon()

def get_window_icon() -> QIcon:
    """獲取視窗圖示"""
    return get_icon_manager().get_window_icon()

def get_toolbar_icon() -> QIcon:
    """獲取工具列圖示"""
    return get_icon_manager().get_toolbar_icon()

def get_icon(name: str, size: Optional[int] = None) -> QIcon:
    """獲取指定圖示"""
    return get_icon_manager().get_icon(name, size) 