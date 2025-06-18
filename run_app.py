import sys
import os

# Ensure the project root (where this script is located) is in sys.path.
# This helps PyInstaller find the 'app' package correctly, especially if
# PyInstaller is run from a different directory or if the CWD is unexpected.
# For most PyInstaller setups where you run it from the project root and
# this script is in the root, this might be redundant but adds robustness.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)

# Now that the project root is confirmed to be in sys.path,
# we can reliably import from the 'app' package.
from app import main as app_main

if __name__ == '__main__':
    # The sys.argv are automatically passed to the QApplication instance
    # created within app_main.main(), so no need to pass them explicitly here.
    app_main.main()
