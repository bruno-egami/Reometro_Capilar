from gui.app import App
import sys
import os

# Ensure script directory is in path (crucial for local imports if running from outside)
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

import reologia_plot_style as rps
import traceback

def exception_handler(exc_type, exc_value, exc_traceback):
    try:
        from logger_config import logger
        logger.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))
    except Exception:
        import traceback
        traceback.print_exception(exc_type, exc_value, exc_traceback)

if __name__ == "__main__":
    sys.excepthook = exception_handler
    rps.apply_dark_style()
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
