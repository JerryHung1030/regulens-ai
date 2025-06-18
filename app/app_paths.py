import os
import sys
from pathlib import Path

def get_app_data_dir() -> Path:
    """
    Returns the application data directory for the current operating system.
    Creates the directory if it doesn't exist.
    """
    app_name = "regulens-ai"
    
    if sys.platform == "win32":
        # Windows - 使用當前工作目錄，適合封裝
        path = Path.cwd() / "user_data"
    elif sys.platform == "darwin":
        # macOS
        path = Path.home() / "Library" / "Application Support" / app_name
    else:
        # Linux and other Unix-like systems
        path = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")) / app_name

    path.mkdir(parents=True, exist_ok=True)
    return path

if __name__ == '__main__':
    # Test the function
    app_data_path = get_app_data_dir()
    print(f"Application data directory: {app_data_path}")
    print(f"Directory exists: {app_data_path.exists()}")
