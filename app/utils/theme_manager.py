import json
import os
import sys
from typing import Dict, Any, Optional
from pathlib import Path


def get_resource_path(relative_path: str) -> Path:
    """獲取資源檔案的路徑，支援 PyInstaller 打包後的路徑"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包後的路徑
        base_path = Path(sys._MEIPASS)
    else:
        # 開發環境的路徑
        base_path = Path(__file__).parent.parent.parent
    
    return base_path / relative_path


class ThemeManager:
    """主題管理器，負責處理顏色變數替換和主題載入"""
    
    def __init__(self):
        self.color_variables = {}
        self.themes_dir = get_resource_path("assets/themes")
        self._load_color_variables()
    
    def _load_color_variables(self):
        """載入顏色變數定義"""
        color_vars_file = self.themes_dir / "color_variables.json"
        if color_vars_file.exists():
            with open(color_vars_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.color_variables = data.get("color_variables", {})
    
    def _resolve_color_variable(self, value: str, theme_name: str) -> str:
        """解析顏色變數，將變數替換為實際顏色值"""
        if not value.startswith("$"):
            return value
        
        # 移除 $ 符號
        var_path = value[1:]
        
        # 解析變數路徑，例如 $primary 或 $background.primary
        path_parts = var_path.split(".")
        
        # 從顏色變數中查找
        current = self.color_variables
        for part in path_parts:
            if part in current:
                current = current[part]
            else:
                return value  # 如果找不到變數，返回原始值
        
        # 如果找到的是字典且包含主題名稱，返回對應的顏色
        if isinstance(current, dict) and theme_name in current:
            return current[theme_name]
        
        # 如果直接是顏色值，返回該值
        if isinstance(current, str) and current.startswith("#"):
            return current
        
        return value
    
    def _process_theme_colors(self, theme_data: Dict[str, Any], theme_name: str) -> Dict[str, Any]:
        """處理主題中的顏色變數"""
        processed_theme = {}
        
        for key, value in theme_data.items():
            if isinstance(value, str):
                # 處理字串值中的顏色變數
                processed_theme[key] = self._resolve_color_variable(value, theme_name)
            elif isinstance(value, dict):
                # 遞迴處理巢狀字典
                processed_theme[key] = self._process_theme_colors(value, theme_name)
            else:
                # 其他類型直接保留
                processed_theme[key] = value
        
        return processed_theme
    
    def load_theme(self, theme_name: str) -> Optional[Dict[str, Any]]:
        """載入指定主題並解析顏色變數"""
        theme_file = self.themes_dir / f"{theme_name}.json"
        
        if not theme_file.exists():
            return None
        
        try:
            with open(theme_file, 'r', encoding='utf-8') as f:
                theme_data = json.load(f)
            
            # 處理顏色變數
            processed_theme = self._process_theme_colors(theme_data, theme_name)
            return processed_theme
            
        except Exception as e:
            print(f"載入主題 {theme_name} 時發生錯誤: {e}")
            return None
    
    def get_available_themes(self) -> list:
        """獲取可用的主題列表"""
        themes = []
        for theme_file in self.themes_dir.glob("*.json"):
            if theme_file.name != "color_variables.json":
                theme_name = theme_file.stem
                themes.append(theme_name)
        return themes
    
    def create_theme_from_template(self, new_theme_name: str, base_theme_name: str = "light") -> bool:
        """從現有主題創建新主題"""
        base_theme = self.load_theme(base_theme_name)
        if not base_theme:
            return False
        
        # 創建新主題檔案
        new_theme_file = self.themes_dir / f"{new_theme_name}.json"
        
        # 修改主題名稱
        base_theme["theme_name"] = f"{new_theme_name.title()} Theme for Regulens-AI"
        
        try:
            with open(new_theme_file, 'w', encoding='utf-8') as f:
                json.dump(base_theme, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"創建主題 {new_theme_name} 時發生錯誤: {e}")
            return False
    
    def update_color_variable(self, var_path: str, theme_name: str, color_value: str) -> bool:
        """更新顏色變數"""
        try:
            path_parts = var_path.split(".")
            current = self.color_variables
            
            # 導航到正確的位置
            for part in path_parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # 確保目標位置是字典
            if not isinstance(current, dict):
                current = {}
            
            # 設置顏色值
            if path_parts[-1] not in current:
                current[path_parts[-1]] = {}
            
            if isinstance(current[path_parts[-1]], dict):
                current[path_parts[-1]][theme_name] = color_value
            else:
                current[path_parts[-1]] = {theme_name: color_value}
            
            # 保存更新
            color_vars_file = self.themes_dir / "color_variables.json"
            with open(color_vars_file, 'w', encoding='utf-8') as f:
                json.dump({"color_variables": self.color_variables}, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"更新顏色變數時發生錯誤: {e}")
            return False
    
    def get_color_variables(self) -> Dict[str, Any]:
        """獲取所有顏色變數"""
        return self.color_variables.copy()


# 全域主題管理器實例
theme_manager = ThemeManager()


def get_available_themes() -> list[str]:
    """獲取所有可用的主題名稱列表。"""
    return theme_manager.get_available_themes()


def load_qss_with_theme(theme_name: str) -> str:
    """載入 QSS 並應用主題顏色變數"""
    try:
        # 載入主題數據（包含顏色變數解析）
        theme_data = theme_manager.load_theme(theme_name)
        if not theme_data:
            raise FileNotFoundError(f"Theme '{theme_name}' not found")
        
        # 載入基礎 QSS 檔案，使用新的路徑解析方法
        base_qss_path = get_resource_path("assets/base.qss")
        if not base_qss_path.exists():
            raise FileNotFoundError(f"Base QSS file not found: {base_qss_path}")
        
        with open(base_qss_path, "r", encoding="utf-8") as f:
            qss_content = f.read()
        
        # 替換 QSS 中的佔位符
        for placeholder, value in theme_data.items():
            qss_content = qss_content.replace(f"@{placeholder}", str(value))
        
        return qss_content
        
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as e:
        raise Exception(f"Error decoding theme JSON file for '{theme_name}': {e}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred while loading the theme '{theme_name}': {e}")


if __name__ == '__main__':
    print("Executing theme_manager.py __main__ block...")
    try:
        print("Available themes:", theme_manager.get_available_themes())
        print("Attempting to load 'light' theme (first 50 chars):")
        qss = load_qss_with_theme("light")
        print(qss[:50] + "..." if qss else "No QSS returned.")
    except Exception as e:
        print(f"Error in __main__: {e}")
        print("Ensure 'assets/base.qss' and relevant theme JSON files exist for this test.")
    print("theme_manager.py __main__ block finished.")
