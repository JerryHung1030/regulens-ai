import json
import os
from pathlib import Path

def get_available_themes() -> list[str]:
    """獲取所有可用的主題名稱列表。"""
    try:
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_script_dir))
        themes_dir = os.path.join(project_root, "assets", "themes")
        
        # 獲取所有 .json 檔案
        theme_files = [f for f in os.listdir(themes_dir) if f.endswith('.json')]
        
        # 移除 .json 副檔名並返回主題名稱列表
        themes = [os.path.splitext(f)[0] for f in theme_files]
        
        # 確保至少有一個主題
        if not themes:
            raise FileNotFoundError("No theme files found in themes directory")
            
        return themes
    except Exception as e:
        raise Exception(f"Error getting available themes: {e}")

def load_qss_with_theme(theme_name: str) -> str:
    # This function loads a base QSS file and a theme-specific JSON file.
    # It replaces placeholders in the QSS content with values from the JSON file.
    try:
        # 從當前檔案位置開始，往上找到專案根目錄
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_script_dir))  # 從 utils 往上兩層到專案根目錄
        assets_dir = os.path.join(project_root, "assets")

        base_qss_path = os.path.join(assets_dir, "base.qss")
        theme_json_path = os.path.join(assets_dir, "themes", f"{theme_name}.json")

        if not os.path.exists(base_qss_path):
            raise FileNotFoundError(f"Base QSS file not found: {base_qss_path}")
        if not os.path.exists(theme_json_path):
            raise FileNotFoundError(f"Theme JSON file not found: {theme_json_path}")

        with open(base_qss_path, "r", encoding="utf-8") as f:
            qss_content = f.read()

        with open(theme_json_path, "r", encoding="utf-8") as f:
            color_theme = json.load(f)

        for placeholder, value in color_theme.items():
            qss_content = qss_content.replace(f"@{placeholder}", str(value))

        return qss_content

    except FileNotFoundError:
        raise
    except json.JSONDecodeError as e:
        raise Exception(f"Error decoding theme JSON file {theme_json_path}: {e}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred while loading the theme '{theme_name}': {e}")

if __name__ == '__main__':
    print("Executing theme_manager.py __main__ block...")
    try:
        print("Attempting to load 'light' theme (first 50 chars):")
        qss = load_qss_with_theme("light")
        print(qss[:50] + "..." if qss else "No QSS returned.")
    except Exception as e:
        print(f"Error in __main__: {e}")
        # Provide more specific guidance for the __main__ test
        print("Ensure 'assets/base.qss' and relevant theme JSON (e.g., 'assets/themes/light.json') exist for this test.")
    print("theme_manager.py __main__ block finished.")
