import importlib.util
import os
import sys
from pathlib import Path



class Supervisor:
    def runDemo(self, func, args):
        env = os.environ.copy()

        if args.guiType == "qt":
            if "QT_QPA_PLATFORM_PLUGIN_PATH" in os.environ:
                os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH")
            if "QT_QPA_FONTDIR" in os.environ:
                os.environ.pop("QT_QPA_FONTDIR")

            # Qt-specific environment variables
            os.environ["QT_QUICK_BACKEND"] = "software"
            try:
                os.environ["LD_LIBRARY_PATH"] = str(Path(importlib.util.find_spec("PyQt5").origin).parent / "Qt5/lib")
            except Exception:
                pass # Ignore if PyQt5 not found, might be using different backend or installed differently

        os.environ["DEPTHAI_INSTALL_SIGNAL_HANDLER"] = "0"
        
        args.noSupervisor = True
            
        func()




