import os
from pathlib import Path
from PySide6.QtGui import QFontDatabase, QFont
from ..logger import logger

# 定義字體權重常量
FONT_WEIGHT = {
    'regular': 400,
    'medium': 500,
    'semi_bold': 600,
    'bold': 700,
    'extra_bold': 800
}

# 定義字體家族名稱
FONT_FAMILIES = {
    'noscript': 'MonoLisa Static-NoScript',
    'noscript_semi_bold': 'MonoLisa Static-NoScript SemiBold',
    'script': 'MonoLisa Static-Script',
    'script_semi_bold': 'MonoLisa Static-Script SemiBold'
}

def load_custom_fonts() -> None:
    """載入自定義字體。"""
    try:
        # 獲取當前腳本所在目錄
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        # 從 utils 往上兩層到專案根目錄
        project_root = os.path.dirname(os.path.dirname(current_script_dir))
        fonts_dir = os.path.join(project_root, "assets", "fonts")
        
        logger.debug(f"Looking for fonts in directory: {fonts_dir}")
        
        # 檢查字體目錄是否存在
        if not os.path.exists(fonts_dir):
            logger.warning(f"Fonts directory not found: {fonts_dir}")
            return
            
        # 獲取所有 .ttf 檔案
        font_files = [f for f in os.listdir(fonts_dir) if f.endswith('.ttf')]
        logger.debug(f"Found {len(font_files)} font files: {font_files}")
        
        # 載入每個字體
        loaded_families = []
        for font_file in font_files:
            font_path = os.path.join(fonts_dir, font_file)
            try:
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    font_families = QFontDatabase.applicationFontFamilies(font_id)
                    for family in font_families:
                        loaded_families.append(family)
                        logger.debug(f"Successfully loaded font: {family} from {font_file}")
                else:
                    logger.warning(f"Failed to load font: {font_file}")
            except Exception as e:
                logger.error(f"Error loading font {font_file}: {e}")
                
        # 記錄所有已載入的字體家族
        logger.debug(f"All loaded font families: {loaded_families}")
        
    except Exception as e:
        logger.error(f"Error in load_custom_fonts: {e}")

def get_font(style: str = 'regular', size: int = 10, italic: bool = False) -> QFont:
    """獲取指定字體。
    
    Args:
        style: 字體樣式 ('regular', 'semi_bold')
        size: 字體大小 (預設 10)
        italic: 是否使用斜體 (預設 False)
    """
    # 根據樣式選擇字體系列
    if style == 'regular':
        family = FONT_FAMILIES['noscript']
        weight = FONT_WEIGHT['regular']
    elif style == 'semi_bold':
        family = FONT_FAMILIES['noscript_semi_bold']
        weight = FONT_WEIGHT['semi_bold']
    else:
        family = FONT_FAMILIES['noscript']
        weight = FONT_WEIGHT['regular']

    # 創建字體
    font = QFont(family, size, weight)
    font.setItalic(italic)
    
    # 檢查字體是否可用
    if not QFontDatabase.hasFamily(family):
        logger.warning(f"Font family '{family}' not found, falling back to system font")
        font = QFont()  # 使用系統預設字體
    
    return font

def get_script_font(style: str = 'regular', size: int = 10, italic: bool = False) -> QFont:
    """獲取 Script 風格字體。
    
    Args:
        style: 字體樣式 ('regular', 'semi_bold')
        size: 字體大小 (預設 10)
        italic: 是否使用斜體 (預設 False)
    """
    # 根據樣式選擇字體系列
    if style == 'regular':
        family = FONT_FAMILIES['script']
        weight = FONT_WEIGHT['regular']
    elif style == 'semi_bold':
        family = FONT_FAMILIES['script_semi_bold']
        weight = FONT_WEIGHT['semi_bold']
    else:
        family = FONT_FAMILIES['script']
        weight = FONT_WEIGHT['regular']

    # 創建字體
    font = QFont(family, size, weight)
    font.setItalic(italic)
    
    # 檢查字體是否可用
    if not QFontDatabase.hasFamily(family):
        logger.warning(f"Font family '{family}' not found, falling back to system font")
        font = QFont()  # 使用系統預設字體
    
    return font 