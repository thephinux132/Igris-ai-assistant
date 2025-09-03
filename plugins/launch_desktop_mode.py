"""
Plugin to launch the Igris OS Desktop Environment.
"""
import sys
from pathlib import Path

# Ensure the 'gui' directory is in the Python path to find igris_shell
try:
    from core.igris_core import ROOT_DIR
except ImportError:
    ROOT_DIR = Path(__file__).resolve().parent.parent

GUI_DIR = ROOT_DIR / "gui"
if str(GUI_DIR) not in sys.path:
    sys.path.insert(0, str(GUI_DIR))

def run():
    """
    Initializes and runs the Igris Desktop Shell.
    """
    try:
        from igris_shell import launch_shell
        print("[INFO] Launching Igris Desktop Environment...")
        # This call will block until the shell window is closed.
        launch_shell()
        return "Igris Desktop session ended."
    except ImportError as e:
        return f"[ERROR] Could not launch desktop shell. Is 'igris_shell.py' in the 'gui' directory? Details: {e}"
    except Exception as e:
        return f"[ERROR] An unexpected error occurred while launching the desktop shell: {e}"