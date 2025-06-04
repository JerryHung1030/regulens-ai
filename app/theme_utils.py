# In app/theme_utils.py

from pathlib import Path
from PySide6.QtWidgets import QApplication
# Make sure these relative imports are correct based on actual location of Settings and logger
from .settings import Settings 
from .logger import logger 

def get_theme_qss(theme_name: str) -> str:
    # Path(__file__).parent should be 'app' directory if theme_utils.py is in 'app'
    # So, (Path(__file__).parent).parent would be the project root.
    project_root = Path(__file__).resolve().parent.parent 
    qss_filename = "dark_theme.qss" if theme_name.lower() == "dark" else "light_theme.qss"
    qss_path = project_root / "assets" / qss_filename

    logger.info(f"Looking for theme file at: {qss_path}")

    if not qss_path.exists():
        # Fallback for cases like running tests where cwd might be project root
        alt_path = Path.cwd() / "assets" / qss_filename
        logger.info(f"Primary path not found, trying alternative path: {alt_path}")
        if alt_path.exists():
            qss_path = alt_path
        else:
            logger.warning(f"Theme file not found at {qss_path} or {alt_path}")
            return ""

    if qss_path.exists():
        try:
            content = qss_path.read_text(encoding='utf-8')
            logger.info(f"Successfully loaded theme file: {qss_path}")
            return content
        except Exception as e:
            logger.error(f"Error reading theme file {qss_path}: {e}")
            return ""
    else: # Should be caught by the above check, but as a safeguard
        logger.warning(f"Theme file not found: {qss_path}")
        return ""

def apply_theme(app: QApplication, settings: Settings) -> None:
    theme_name = settings.get("theme", "Light") # Default to "Light"
    logger.info(f"Applying theme: {theme_name}")
    
    qss = get_theme_qss(theme_name)
    if qss:
        app.setStyleSheet(qss)
    else:
        app.setStyleSheet("") 
        logger.warning(f"No QSS applied for theme {theme_name} due to missing file or read error.")
