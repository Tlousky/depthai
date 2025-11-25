import sys
import os

# Set default arguments for the packaged app
# We prepend these to sys.argv so they are parsed by depthai_demo
if "--guiType" not in sys.argv:
    sys.argv.extend(["--guiType", "qt"])
if "--skipVersionCheck" not in sys.argv:
    sys.argv.append("--skipVersionCheck")

# Import depthai_demo after setting args, as it parses args on import
import depthai_demo

if __name__ == "__main__":
    # runQt is defined in depthai_demo and handles the Qt GUI loop
    depthai_demo.runQt()
