# This Python file uses the following encoding: utf-8
import sys
from pathlib import Path

import blobconverter
import cv2
from PyQt5.QtQml import QQmlApplicationEngine, qmlRegisterType, qmlRegisterSingletonType, QQmlEngine
from PyQt5.QtQuick import QQuickPaintedItem
from PyQt5.QtGui import QImage
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable, QThreadPool, QRectF
import depthai as dai
import numpy as np

# To be used on the @QmlElement decorator
# (QML_IMPORT_MINOR_VERSION is optional)
from PyQt5.QtWidgets import QApplication
from depthai_sdk.previews import Previews
from depthai_sdk.utils import resizeLetterbox, createBlankFrame
from gui.config_handler import ConfigHandler
from s3_uploader import S3Uploader
import threading

# If BGR format is available
colorMode = QImage.Format_RGB888
try:
    colorMode = QImage.Format_BGR888
except:
    colorMode = QImage.Format_RGB888

class Singleton(type(QQuickPaintedItem)):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


instance = None


# @QmlElement
class ImageWriter(QQuickPaintedItem):
    frame = QImage()

    def __init__(self, parent):
        super().__init__(parent)
        self.setRenderTarget(QQuickPaintedItem.FramebufferObject)
        self.setProperty("parent", parent)

    def paint(self, painter):
        painter.drawImage(QRectF(0, 0, self.width(), self.height()), self.frame)

    def update_frame(self, image):
        self.frame = image
        self.update()


# @QmlElement
class AppBridge(QObject):
    @pyqtSlot()
    def applyAndRestart(self):
        instance.restartDemo()

    @pyqtSlot()
    def reloadDevices(self):
        instance.guiOnReloadDevices()

    @pyqtSlot(bool)
    def toggleStatisticsConsent(self, value):
        instance.guiOnStaticticsConsent(value)

    @pyqtSlot(bool)
    def toggleSync(self, value):
        ConfigHandler().set_value("sync", value)
        instance.guiOnToggleSync(value)

    @pyqtSlot(bool)
    def toggleRgbDepthAlignment(self, value):
        ConfigHandler().set_value("rgbDepthAlignment", value)
        instance.guiOnToggleRgbDepthAlignment(not value)

    @pyqtSlot(str)
    def runApp(self, appName):
        instance.guiOnRunApp(appName)

    @pyqtSlot(str)
    def terminateApp(self, appName):
        instance.guiOnTerminateApp(appName)

    @pyqtSlot(str)
    def selectDevice(self, value):
        instance.guiOnSelectDevice(value)

    @pyqtSlot(bool, bool, bool)
    def selectReportingOptions(self, temp, cpu, memory):
        ConfigHandler().set_value("reportTemp", temp)
        ConfigHandler().set_value("reportCpu", cpu)
        ConfigHandler().set_value("reportMem", memory)
        instance.guiOnSelectReportingOptions(temp, cpu, memory)

    @pyqtSlot(str)
    def selectReportingPath(self, value):
        ConfigHandler().set_value("reportPath", value)
        instance.guiOnSelectReportingPath(value)

    @pyqtSlot(str)
    def selectEncodingPath(self, value):
        ConfigHandler().set_value("encodeOutput", value)
        instance.guiOnSelectEncodingPath(value)

    @pyqtSlot(bool, int)
    def toggleColorEncoding(self, enabled, fps):
        ConfigHandler().set_value("encodeColor", enabled)
        ConfigHandler().set_value("encodeColorFps", fps)
        instance.guiOnToggleColorEncoding(enabled, fps)

    @pyqtSlot(bool, int)
    def toggleLeftEncoding(self, enabled, fps):
        ConfigHandler().set_value("encodeLeft", enabled)
        ConfigHandler().set_value("encodeLeftFps", fps)
        instance.guiOnToggleLeftEncoding(enabled, fps)

    @pyqtSlot(bool, int)
    def toggleRightEncoding(self, enabled, fps):
        ConfigHandler().set_value("encodeRight", enabled)
        ConfigHandler().set_value("encodeRightFps", fps)
        instance.guiOnToggleRightEncoding(enabled, fps)

    @pyqtSlot(bool)
    def toggleDepth(self, enabled):
        ConfigHandler().set_value("depthEnabled", enabled)
        instance.guiOnToggleDepth(enabled)

    @pyqtSlot(bool)
    def toggleNN(self, enabled):
        ConfigHandler().set_value("nnEnabled", enabled)
        instance.guiOnToggleNN(enabled)

    @pyqtSlot(bool)
    def toggleDisparity(self, enabled):
        ConfigHandler().set_value("disparityEnabled", enabled)
        instance.guiOnToggleDisparity(enabled)

    @pyqtSlot(bool, int)
    def toggleDepthEncoding(self, enabled, fps):
        ConfigHandler().set_value("encodeDepth", enabled)
        ConfigHandler().set_value("encodeDepthFps", fps)
        instance.guiOnToggleDepthEncoding(enabled, fps)

    @pyqtSlot(bool)
    def togglePointCloud(self, enabled):
        ConfigHandler().set_value("encodePointCloud", enabled)
        instance.guiOnTogglePointCloud(enabled)

    @pyqtSlot(bool, int)
    def toggleIrEncoding(self, enabled, fps):
        ConfigHandler().set_value("encodeIr", enabled)
        ConfigHandler().set_value("encodeIrFps", fps)
        instance.guiOnToggleIrEncoding(enabled, fps)

    @pyqtSlot(bool, int)
    def toggleTofEncoding(self, enabled, fps):
        ConfigHandler().set_value("encodeTof", enabled)
        ConfigHandler().set_value("encodeTofFps", fps)
        instance.guiOnToggleTofEncoding(enabled, fps)

    @pyqtSlot()
    def toggleRecording(self):
        instance.guiOnToggleRecording()

    @pyqtSlot()
    def uploadFiles(self):
        # Get config for user UUID and upload path
        config = ConfigHandler()
        # Assuming user UUID is stored in config, or we generate/retrieve it. 
        # The request says "user UUID from the config.json".
        # Let's check how config is handled. ConfigHandler reads config.json.
        # We need to ensure 'user_uuid' is available. 
        # If not explicitly in config.json, we might need to fallback or it might be 'app.args.deviceId' or similar?
        # The request specifically says "user UUID from the config.json".
        
        user_uuid = config.get_value("user_id")
        if not user_uuid:
            print("User ID not found in config.json. Cannot upload.")
            return

        upload_path = config.get_value("encodeOutput")
        if not upload_path:
            # Fallback to default recordings path if not set
            upload_path = str(Path.cwd() / "recordings")
        
        bucket_name = config.get_value("s3_bucket")
        if not bucket_name:
            bucket_name = "uploads" # Default fallback
            print("S3 bucket not found in config.json. Using default 'uploads'.")

        region_name = config.get_value("s3_region")

        def upload_worker():
            uploader = S3Uploader(bucket_name, region_name)
            uploader.scan_and_upload(upload_path, user_uuid)

        threading.Thread(target=upload_worker, daemon=True).start()


# @QmlElement
class AIBridge(QObject):
    @pyqtSlot(str)
    def setCnnModel(self, name):
        ConfigHandler().set_value("cnnModel", name)
        instance.guiOnAiSetupUpdate(cnn=name)

    @pyqtSlot(int)
    def setShaves(self, value):
        ConfigHandler().set_value("shaves", value)
        instance.guiOnAiSetupUpdate(shave=value)

    @pyqtSlot(str)
    def setModelSource(self, value):
        ConfigHandler().set_value("modelSource", value)
        instance.guiOnAiSetupUpdate(source=value)

    @pyqtSlot(bool)
    def setFullFov(self, value):
        ConfigHandler().set_value("fullFov", value)
        instance.guiOnAiSetupUpdate(fullFov=value)

    @pyqtSlot(bool)
    def setSbb(self, value):
        ConfigHandler().set_value("sbb", value)
        instance.guiOnAiSetupUpdate(sbb=value)

    @pyqtSlot(float)
    def setSbbFactor(self, value):
        if instance.writer is not None:
            ConfigHandler().set_value("sbbFactor", value)
            instance.guiOnAiSetupUpdate(sbbFactor=value)

    @pyqtSlot(str)
    def setOvVersion(self, state):
        ConfigHandler().set_value("ovVersion", state)
        instance.guiOnAiSetupUpdate(ov=state.replace("VERSION_", ""))

    @pyqtSlot(str)
    def setCountLabel(self, state):
        ConfigHandler().set_value("countLabel", state)
        instance.guiOnAiSetupUpdate(countLabel=state)


# @QmlElement
class PreviewBridge(QObject):
    @pyqtSlot(str)
    def changeSelected(self, state):
        instance.guiOnPreviewChangeSelected(state)


# @QmlElement
class DepthBridge(QObject):
    @pyqtSlot(bool)
    def toggleSubpixel(self, state):
        ConfigHandler().set_value("subpixel", state)
        instance.guiOnDepthSetupUpdate(subpixel=state)

    @pyqtSlot(bool)
    def toggleExtendedDisparity(self, state):
        ConfigHandler().set_value("extendedDisparity", state)
        instance.guiOnDepthSetupUpdate(extended=state)

    @pyqtSlot(bool)
    def toggleLeftRightCheck(self, state):
        ConfigHandler().set_value("lrc", state)
        instance.guiOnDepthSetupUpdate(lrc=state)

    @pyqtSlot(int)
    def setDisparityConfidenceThreshold(self, value):
        ConfigHandler().set_value("disparityConfidenceThreshold", value)
        instance.guiOnDepthConfigUpdate(dct=value)

    @pyqtSlot(int)
    def setLrcThreshold(self, value):
        ConfigHandler().set_value("lrcThreshold", value)
        instance.guiOnDepthConfigUpdate(lrcThreshold=value)

    @pyqtSlot(int)
    def setBilateralSigma(self, value):
        ConfigHandler().set_value("bilateralSigma", value)
        instance.guiOnDepthConfigUpdate(sigma=value)

    @pyqtSlot(int, int)
    def setDepthRange(self, valFrom, valTo):
        ConfigHandler().set_value("depthRangeFrom", valFrom)
        ConfigHandler().set_value("depthRangeTo", valTo)
        instance.guiOnDepthSetupUpdate(depthFrom=int(valFrom * 1000), depthTo=int(valTo * 1000))

    @pyqtSlot(str)
    def setMedianFilter(self, state):
        ConfigHandler().set_value("medianFilter", state)
        value = getattr(dai.MedianFilter, state)
        instance.guiOnDepthConfigUpdate(median=value)

    @pyqtSlot(int)
    def setIrLaserDotProjector(self, value):
        ConfigHandler().set_value("irLaserDotProjector", value)
        instance.guiOnDepthConfigUpdate(irLaser=value)

    @pyqtSlot(int)
    def setIrFloodIlluminator(self, value):
        ConfigHandler().set_value("irFloodIlluminator", value)
        instance.guiOnDepthConfigUpdate(irFlood=value)


# @QmlElement
class ColorCamBridge(QObject):
    name = "color"

    @pyqtSlot(int, int)
    def setIsoExposure(self, iso, exposure):
        if iso > 0 and exposure > 0:
            ConfigHandler().set_value("colorIso", iso)
            ConfigHandler().set_value("colorExposure", exposure)
            instance.guiOnCameraConfigUpdate("color", sensitivity=iso, exposure=exposure)

    @pyqtSlot(int)
    def setContrast(self, value):
        ConfigHandler().set_value("colorContrast", value)
        instance.guiOnCameraConfigUpdate("color", contrast=value)

    @pyqtSlot(int)
    def setBrightness(self, value):
        ConfigHandler().set_value("colorBrightness", value)
        instance.guiOnCameraConfigUpdate("color", brightness=value)

    @pyqtSlot(int)
    def setSaturation(self, value):
        ConfigHandler().set_value("colorSaturation", value)
        instance.guiOnCameraConfigUpdate("color", saturation=value)

    @pyqtSlot(int)
    def setSharpness(self, value):
        ConfigHandler().set_value("colorSharpness", value)
        instance.guiOnCameraConfigUpdate("color", sharpness=value)

    @pyqtSlot(int)
    def setFps(self, value):
        ConfigHandler().set_value("colorFps", value)
        instance.guiOnCameraSetupUpdate("color", fps=value)

    @pyqtSlot(str)
    def setResolution(self, state):
        ConfigHandler().set_value("colorResolution", state)
        if state == "THE_1080_P":
            instance.guiOnCameraSetupUpdate("color", resolution=1080)
        elif state == "THE_4_K":
            instance.guiOnCameraSetupUpdate("color", resolution=2160)
        elif state == "THE_12_MP":
            instance.guiOnCameraSetupUpdate("color", resolution=3040)


# @QmlElement
class MonoCamBridge(QObject):

    @pyqtSlot(int, int)
    def setIsoExposure(self, iso, exposure):
        if iso > 0 and exposure > 0:
            ConfigHandler().set_value("monoIso", iso)
            ConfigHandler().set_value("monoExposure", exposure)
            instance.guiOnCameraConfigUpdate("left", sensitivity=iso, exposure=exposure)
            instance.guiOnCameraConfigUpdate("right", sensitivity=iso, exposure=exposure)

    @pyqtSlot(int)
    def setContrast(self, value):
        ConfigHandler().set_value("monoContrast", value)
        instance.guiOnCameraConfigUpdate("left", contrast=value)
        instance.guiOnCameraConfigUpdate("right", contrast=value)

    @pyqtSlot(int)
    def setBrightness(self, value):
        ConfigHandler().set_value("monoBrightness", value)
        instance.guiOnCameraConfigUpdate("left", brightness=value)
        instance.guiOnCameraConfigUpdate("right", brightness=value)

    @pyqtSlot(int)
    def setSaturation(self, value):
        ConfigHandler().set_value("monoSaturation", value)
        instance.guiOnCameraConfigUpdate("left", saturation=value)
        instance.guiOnCameraConfigUpdate("right", saturation=value)

    @pyqtSlot(int)
    def setSharpness(self, value):
        ConfigHandler().set_value("monoSharpness", value)
        instance.guiOnCameraConfigUpdate("left", sharpness=value)
        instance.guiOnCameraConfigUpdate("right", sharpness=value)

    @pyqtSlot(int)
    def setFps(self, value):
        ConfigHandler().set_value("monoFps", value)
        instance.guiOnCameraSetupUpdate("left", fps=value)
        instance.guiOnCameraSetupUpdate("right", fps=value)

    @pyqtSlot(str)
    def setResolution(self, state):
        ConfigHandler().set_value("monoResolution", state)
        if state == "THE_720_P":
            instance.guiOnCameraSetupUpdate("left", resolution=720)
            instance.guiOnCameraSetupUpdate("right", resolution=720)
        elif state == "THE_800_P":
            instance.guiOnCameraSetupUpdate("left", resolution=800)
            instance.guiOnCameraSetupUpdate("right", resolution=800)
        elif state == "THE_400_P":
            instance.guiOnCameraSetupUpdate("left", resolution=400)
            instance.guiOnCameraSetupUpdate("right", resolution=400)


class DemoQtGui:
    instance = None
    writer = None
    window = None
    progressFrame = None

    def __init__(self):
        global instance
        self.app = QApplication([sys.argv[0]])
        self.engine = QQmlApplicationEngine()
        self.engine.quit.connect(self.app.quit)
        instance = self
        qmlRegisterType(ImageWriter, 'dai.gui', 1, 0, 'ImageWriter')
        qmlRegisterType(AppBridge, 'dai.gui', 1, 0, 'AppBridge')
        qmlRegisterType(AIBridge, 'dai.gui', 1, 0, 'AIBridge')
        qmlRegisterType(PreviewBridge, 'dai.gui', 1, 0, 'PreviewBridge')
        qmlRegisterType(DepthBridge, 'dai.gui', 1, 0, 'DepthBridge')
        qmlRegisterType(ColorCamBridge, 'dai.gui', 1, 0, 'ColorCamBridge')
        qmlRegisterType(MonoCamBridge, 'dai.gui', 1, 0, 'MonoCamBridge')
        self.engine.addImportPath(str(Path(__file__).parent / "views"))
        self.engine.load(str(Path(__file__).parent / "views" / "root.qml"))
        self.window = self.engine.rootObjects()[0]
        if not self.engine.rootObjects():
            raise RuntimeError("Unable to start GUI - no root objects!")

    def setData(self, data):
        name, value = data
        self.window.setProperty(name, value)

    def updatePreview(self, frame):
        # Pass the original frame to ImageWriter. The paint() method handles scaling to the view.
        # This avoids stride/alignment issues caused by resizing to odd GUI dimensions.
        scaledFrame = frame
        
        frameH, frameW = scaledFrame.shape[:2]
        if len(scaledFrame.shape) == 3:
            # ensure contiguous array for QImage
            if not scaledFrame.flags['C_CONTIGUOUS']:
                scaledFrame = np.ascontiguousarray(scaledFrame)
            
            bytesPerLine = frameW * 3
            if colorMode == QImage.Format_RGB888:
                scaledFrame = cv2.cvtColor(scaledFrame, cv2.COLOR_RGB2BGR)
            img = QImage(scaledFrame.data, frameW, frameH, bytesPerLine, colorMode)
        else:
            if not scaledFrame.flags['C_CONTIGUOUS']:
                scaledFrame = np.ascontiguousarray(scaledFrame)
            bytesPerLine = frameW
            img = QImage(scaledFrame.data, frameW, frameH, bytesPerLine, QImage.Format_Grayscale8)
            
        # Keep a reference to the numpy array to prevent it from being garbage collected
        img.__data_ref__ = scaledFrame
        self.writer.update_frame(img)

    def updateDownloadProgress(self, curr, total):
        frame = self.createProgressFrame(curr / total)
        if colorMode == QImage.Format_RGB888:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        img = QImage(frame.data, frame.shape[1], frame.shape[0], frame.shape[2] * frame.shape[1], colorMode)
        self.writer.update_frame(img)

    def createProgressFrame(self, donePercentage=None):
        confManager = getattr(self, "confManager", None)
        w, h = int(self.writer.width()), int(self.writer.height())
        if self.progressFrame is None:
            self.progressFrame = createBlankFrame(w, h)
            downloadText = "Downloading model blob..."
            textsize = cv2.getTextSize(downloadText, cv2.FONT_HERSHEY_TRIPLEX, 0.5, 4)[0][0]
            offset = int((w - textsize) / 2)
            cv2.putText(self.progressFrame, downloadText, (offset, 250), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (255, 255, 255), 4, cv2.LINE_AA)
            cv2.putText(self.progressFrame, downloadText, (offset, 250), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

        newFrame = self.progressFrame.copy()
        if donePercentage is not None:
            cv2.rectangle(newFrame, (100, 300), (460, 350), (255, 255, 255), cv2.FILLED)
            cv2.rectangle(newFrame, (110, 310), (int(110 + 340 * donePercentage), 340), (0, 0, 0), cv2.FILLED)
        return newFrame

    def showSetupFrame(self, text):
        w, h = int(self.writer.width()), int(self.writer.height())
        setupFrame = createBlankFrame(w, h)
        cv2.putText(setupFrame, text, (200, 250), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (255, 255, 255), 4, cv2.LINE_AA)
        cv2.putText(setupFrame, text, (200, 250), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        if colorMode == QImage.Format_RGB888:
                setupFrame = cv2.cvtColor(setupFrame, cv2.COLOR_RGB2BGR)
        img = QImage(setupFrame.data, w, h, setupFrame.shape[2] * w, colorMode)
        self.writer.update_frame(img)

    def startGui(self):
        self.writer = self.window.findChild(QObject, "writer")
        self.showSetupFrame("Starting demo...")
        medianChoices = list(filter(lambda name: name.startswith('KERNEL_') or name.startswith('MEDIAN_'), vars(dai.MedianFilter).keys()))[::-1]
        self.setData(["medianChoices", medianChoices])
        colorChoices = list(filter(lambda name: name[0].isupper(), vars(dai.ColorCameraProperties.SensorResolution).keys()))
        self.setData(["colorResolutionChoices", colorChoices])
        monoChoices = list(filter(lambda name: name[0].isupper(), vars(dai.MonoCameraProperties.SensorResolution).keys()))
        self.setData(["monoResolutionChoices", monoChoices])
        self.setData(["modelSourceChoices", [Previews.color.name, Previews.left.name, Previews.right.name]])
        versionChoices = sorted(filter(lambda name: name.startswith("VERSION_"), vars(dai.OpenVINO).keys()), reverse=True)
        self.setData(["ovVersions", versionChoices])
        
        # Initialize QML models to prevent undefined errors
        self.setData(["modelChoices", []])
        self.setData(["countLabels", []])
        self.setData(["deviceChoices", []])

        self.createProgressFrame()
        self.createProgressFrame()
        
        # Load configuration
        config = ConfigHandler()
        
        # Helper to safely update args
        def update_arg(name, value):
            if hasattr(self, 'confManager'):
                setattr(self.confManager.args, name, value)

        # Apply loaded configuration
        if config.get_value("sync") is not None:
            val = config.get_value("sync")
            self.setData(["sync", val])
            update_arg("sync", val)
            
        if config.get_value("rgbDepthAlignment") is not None:
            val = config.get_value("rgbDepthAlignment")
            self.setData(["rgbDepthAlignment", val])
            update_arg("noRgbDepthAlign", not val)
            
        if config.get_value("depthEnabled") is not None:
            val = config.get_value("depthEnabled")
            self.setData(["depthEnabled", val])
            # depthEnabled is derived from args.show containing "depth"
            # We can't easily set it here without manipulating args.show
            pass 
            
        if config.get_value("nnEnabled") is not None:
            val = config.get_value("nnEnabled")
            self.setData(["nnEnabled", val])
            # nnEnabled is complex to set directly on args
            pass
            
        if config.get_value("disparityEnabled") is not None:
            val = config.get_value("disparityEnabled")
            self.setData(["disparityEnabled", val])
            pass
            
        if config.get_value("cnnModel") is not None:
            val = config.get_value("cnnModel")
            self.setData(["cnnModel", val])
            update_arg("cnnModel", val)
            
        if config.get_value("shaves") is not None:
            val = config.get_value("shaves")
            self.setData(["shaves", val])
            update_arg("shaves", val)
            
        if config.get_value("modelSource") is not None:
            val = config.get_value("modelSource")
            self.setData(["modelSource", val])
            update_arg("camera", val) # 'camera' arg controls model source
            
        if config.get_value("fullFov") is not None:
            val = config.get_value("fullFov")
            self.setData(["fullFov", val])
            update_arg("disableFullFovNn", not val)
            
        if config.get_value("sbb") is not None:
            val = config.get_value("sbb")
            self.setData(["sbb", val])
            update_arg("spatialBoundingBox", val)
            
        if config.get_value("sbbFactor") is not None:
            val = config.get_value("sbbFactor")
            self.setData(["sbbFactor", val])
            update_arg("sbbScaleFactor", val)
            
        if config.get_value("ovVersion") is not None:
            val = config.get_value("ovVersion")
            self.setData(["ovVersion", val])
            update_arg("openvinoVersion", val.replace("VERSION_", ""))
            
        if config.get_value("countLabel") is not None:
            val = config.get_value("countLabel")
            self.setData(["countLabel", val])
            update_arg("countLabel", val)
            
        if config.get_value("subpixel") is not None:
            val = config.get_value("subpixel")
            self.setData(["subpixel", val])
            update_arg("subpixel", val)
            
        if config.get_value("extendedDisparity") is not None:
            val = config.get_value("extendedDisparity")
            self.setData(["extendedDisparity", val])
            update_arg("extendedDisparity", val)
            
        if config.get_value("lrc") is not None:
            val = config.get_value("lrc")
            self.setData(["lrc", val])
            update_arg("stereoLrCheck", val)
            
        if config.get_value("disparityConfidenceThreshold") is not None:
            val = config.get_value("disparityConfidenceThreshold")
            self.setData(["disparityConfidenceThreshold", val])
            update_arg("disparityConfidenceThreshold", val)
            
        if config.get_value("lrcThreshold") is not None:
            val = config.get_value("lrcThreshold")
            self.setData(["lrcThreshold", val])
            update_arg("lrcThreshold", val)
            
        if config.get_value("bilateralSigma") is not None:
            val = config.get_value("bilateralSigma")
            self.setData(["bilateralSigma", val])
            update_arg("sigma", val)
            
        if config.get_value("depthRangeFrom") is not None and config.get_value("depthRangeTo") is not None:
            self.setData(["depthRangeFrom", config.get_value("depthRangeFrom")])
            self.setData(["depthRangeTo", config.get_value("depthRangeTo")])
            update_arg("minDepth", int(config.get_value("depthRangeFrom") * 1000))
            update_arg("maxDepth", int(config.get_value("depthRangeTo") * 1000))
            
        if config.get_value("medianFilter") is not None:
            val = config.get_value("medianFilter")
            self.setData(["medianFilter", val])
            # Map string to size for args
            size = 0
            if val == "KERNEL_3x3": size = 3
            elif val == "KERNEL_5x5": size = 5
            elif val == "KERNEL_7x7": size = 7
            update_arg("stereoMedianSize", size)
            
        if config.get_value("irLaserDotProjector") is not None:
            val = config.get_value("irLaserDotProjector")
            self.setData(["irLaserDotProjector", val])
            update_arg("irDotBrightness", val)
            
        if config.get_value("irFloodIlluminator") is not None:
            val = config.get_value("irFloodIlluminator")
            self.setData(["irFloodIlluminator", val])
            update_arg("irFloodBrightness", val)
            
        if config.get_value("colorIso") is not None and config.get_value("colorExposure") is not None:
            self.setData(["colorIso", config.get_value("colorIso")])
            self.setData(["colorExposure", config.get_value("colorExposure")])
            # Camera controls are complex lists in args, skipping complex update for now to avoid errors
            # update_arg("cameraSensitivity", ...) 
            
        if config.get_value("colorContrast") is not None:
            self.setData(["colorContrast", config.get_value("colorContrast")])
            
        if config.get_value("colorBrightness") is not None:
            self.setData(["colorBrightness", config.get_value("colorBrightness")])
            
        if config.get_value("colorSaturation") is not None:
            self.setData(["colorSaturation", config.get_value("colorSaturation")])
            
        if config.get_value("colorSharpness") is not None:
            self.setData(["colorSharpness", config.get_value("colorSharpness")])
            
        if config.get_value("colorFps") is not None:
            val = config.get_value("colorFps")
            self.setData(["colorFps", val])
            update_arg("rgbFps", val)
            
        if config.get_value("colorResolution") is not None:
            val = config.get_value("colorResolution")
            self.setData(["colorResolution", val])
            update_arg("rgbResolution", val)
                
        if config.get_value("monoIso") is not None and config.get_value("monoExposure") is not None:
            self.setData(["monoIso", config.get_value("monoIso")])
            self.setData(["monoExposure", config.get_value("monoExposure")])
            
        w, h = int(self.writer.width()), int(self.writer.height())
        setupFrame = createBlankFrame(w, h)
        cv2.putText(setupFrame, text, (200, 250), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (255, 255, 255), 4, cv2.LINE_AA)
        cv2.putText(setupFrame, text, (200, 250), cv2.FONT_HERSHEY_TRIPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        if colorMode == QImage.Format_RGB888:
                setupFrame = cv2.cvtColor(setupFrame, cv2.COLOR_RGB2BGR)
        img = QImage(setupFrame.data, w, h, setupFrame.shape[2] * w, colorMode)
        self.writer.update_frame(img)

    def startGui(self):
        self.writer = self.window.findChild(QObject, "writer")
        self.showSetupFrame("Starting demo...")
        medianChoices = list(filter(lambda name: name.startswith('KERNEL_') or name.startswith('MEDIAN_'), vars(dai.MedianFilter).keys()))[::-1]
        self.setData(["medianChoices", medianChoices])
        colorChoices = list(filter(lambda name: name[0].isupper(), vars(dai.ColorCameraProperties.SensorResolution).keys()))
        self.setData(["colorResolutionChoices", colorChoices])
        monoChoices = list(filter(lambda name: name[0].isupper(), vars(dai.MonoCameraProperties.SensorResolution).keys()))
        self.setData(["monoResolutionChoices", monoChoices])
        self.setData(["modelSourceChoices", [Previews.color.name, Previews.left.name, Previews.right.name]])
        versionChoices = sorted(filter(lambda name: name.startswith("VERSION_"), vars(dai.OpenVINO).keys()), reverse=True)
        self.setData(["ovVersions", versionChoices])
        
        # Initialize QML models to prevent undefined errors
        self.setData(["modelChoices", []])
        self.setData(["countLabels", []])
        self.setData(["deviceChoices", []])

        self.createProgressFrame()
        self.createProgressFrame()
        
        # Load configuration
        config = ConfigHandler()
        
        # Helper to safely update args
        def update_arg(name, value):
            if hasattr(self, 'confManager'):
                setattr(self.confManager.args, name, value)

        # Apply loaded configuration
        if config.get_value("sync") is not None:
            val = config.get_value("sync")
            self.setData(["sync", val])
            update_arg("sync", val)
            
        if config.get_value("rgbDepthAlignment") is not None:
            val = config.get_value("rgbDepthAlignment")
            self.setData(["rgbDepthAlignment", val])
            update_arg("noRgbDepthAlign", not val)
            
        if config.get_value("depthEnabled") is not None:
            val = config.get_value("depthEnabled")
            self.setData(["depthEnabled", val])
            # depthEnabled is derived from args.show containing "depth"
            # We can't easily set it here without manipulating args.show
            pass 
            
        if config.get_value("nnEnabled") is not None:
            val = config.get_value("nnEnabled")
            self.setData(["nnEnabled", val])
            # nnEnabled is complex to set directly on args
            pass
            
        if config.get_value("disparityEnabled") is not None:
            val = config.get_value("disparityEnabled")
            self.setData(["disparityEnabled", val])
            pass
            
        if config.get_value("cnnModel") is not None:
            val = config.get_value("cnnModel")
            self.setData(["cnnModel", val])
            update_arg("cnnModel", val)
            
        if config.get_value("shaves") is not None:
            val = config.get_value("shaves")
            self.setData(["shaves", val])
            update_arg("shaves", val)
            
        if config.get_value("modelSource") is not None:
            val = config.get_value("modelSource")
            self.setData(["modelSource", val])
            update_arg("camera", val) # 'camera' arg controls model source
            
        if config.get_value("fullFov") is not None:
            val = config.get_value("fullFov")
            self.setData(["fullFov", val])
            update_arg("disableFullFovNn", not val)
            
        if config.get_value("sbb") is not None:
            val = config.get_value("sbb")
            self.setData(["sbb", val])
            update_arg("spatialBoundingBox", val)
            
        if config.get_value("sbbFactor") is not None:
            val = config.get_value("sbbFactor")
            self.setData(["sbbFactor", val])
            update_arg("sbbScaleFactor", val)
            
        if config.get_value("ovVersion") is not None:
            val = config.get_value("ovVersion")
            self.setData(["ovVersion", val])
            update_arg("openvinoVersion", val.replace("VERSION_", ""))
            
        if config.get_value("countLabel") is not None:
            val = config.get_value("countLabel")
            self.setData(["countLabel", val])
            update_arg("countLabel", val)
            
        if config.get_value("subpixel") is not None:
            val = config.get_value("subpixel")
            self.setData(["subpixel", val])
            update_arg("subpixel", val)
            
        if config.get_value("extendedDisparity") is not None:
            val = config.get_value("extendedDisparity")
            self.setData(["extendedDisparity", val])
            update_arg("extendedDisparity", val)
            
        if config.get_value("lrc") is not None:
            val = config.get_value("lrc")
            self.setData(["lrc", val])
            update_arg("stereoLrCheck", val)
            
        if config.get_value("disparityConfidenceThreshold") is not None:
            val = config.get_value("disparityConfidenceThreshold")
            self.setData(["disparityConfidenceThreshold", val])
            update_arg("disparityConfidenceThreshold", val)
            
        if config.get_value("lrcThreshold") is not None:
            val = config.get_value("lrcThreshold")
            self.setData(["lrcThreshold", val])
            update_arg("lrcThreshold", val)
            
        if config.get_value("bilateralSigma") is not None:
            val = config.get_value("bilateralSigma")
            self.setData(["bilateralSigma", val])
            update_arg("sigma", val)
            
        if config.get_value("depthRangeFrom") is not None and config.get_value("depthRangeTo") is not None:
            self.setData(["depthRangeFrom", config.get_value("depthRangeFrom")])
            self.setData(["depthRangeTo", config.get_value("depthRangeTo")])
            update_arg("minDepth", int(config.get_value("depthRangeFrom") * 1000))
            update_arg("maxDepth", int(config.get_value("depthRangeTo") * 1000))
            
        if config.get_value("medianFilter") is not None:
            val = config.get_value("medianFilter")
            self.setData(["medianFilter", val])
            # Map string to size for args
            size = 0
            if val == "KERNEL_3x3": size = 3
            elif val == "KERNEL_5x5": size = 5
            elif val == "KERNEL_7x7": size = 7
            update_arg("stereoMedianSize", size)
            
        if config.get_value("irLaserDotProjector") is not None:
            val = config.get_value("irLaserDotProjector")
            self.setData(["irLaserDotProjector", val])
            update_arg("irDotBrightness", val)
            
        if config.get_value("irFloodIlluminator") is not None:
            val = config.get_value("irFloodIlluminator")
            self.setData(["irFloodIlluminator", val])
            update_arg("irFloodBrightness", val)
            
        if config.get_value("colorIso") is not None and config.get_value("colorExposure") is not None:
            self.setData(["colorIso", config.get_value("colorIso")])
            self.setData(["colorExposure", config.get_value("colorExposure")])
            # Camera controls are complex lists in args, skipping complex update for now to avoid errors
            # update_arg("cameraSensitivity", ...) 
            
        if config.get_value("colorContrast") is not None:
            self.setData(["colorContrast", config.get_value("colorContrast")])
            
        if config.get_value("colorBrightness") is not None:
            self.setData(["colorBrightness", config.get_value("colorBrightness")])
            
        if config.get_value("colorSaturation") is not None:
            self.setData(["colorSaturation", config.get_value("colorSaturation")])
            
        if config.get_value("colorSharpness") is not None:
            self.setData(["colorSharpness", config.get_value("colorSharpness")])
            
        if config.get_value("colorFps") is not None:
            val = config.get_value("colorFps")
            self.setData(["colorFps", val])
            update_arg("rgbFps", val)
            
        if config.get_value("colorResolution") is not None:
            val = config.get_value("colorResolution")
            self.setData(["colorResolution", val])
            update_arg("rgbResolution", val)
                
        if config.get_value("monoIso") is not None and config.get_value("monoExposure") is not None:
            self.setData(["monoIso", config.get_value("monoIso")])
            self.setData(["monoExposure", config.get_value("monoExposure")])
            
        if config.get_value("monoContrast") is not None:
            self.setData(["monoContrast", config.get_value("monoContrast")])
            
        if config.get_value("monoBrightness") is not None:
            self.setData(["monoBrightness", config.get_value("monoBrightness")])
            
        if config.get_value("monoSaturation") is not None:
            self.setData(["monoSaturation", config.get_value("monoSaturation")])
          # Misc Properties
        if config.get_value("reportPath") is not None:
            self.setData(["reportPath", config.get_value("reportPath")])
            update_arg("reportFile", config.get_value("reportPath"))

        if config.get_value("encodeOutput") is not None:
            self.setData(["encodeOutput", config.get_value("encodeOutput")])
            # encodeOutput is not directly an arg, it's used when encoding is enabled
            pass

        if config.get_value("encodeColor") is not None and config.get_value("encodeColorFps") is not None:
            self.setData(["encodeColor", config.get_value("encodeColor")])
            self.setData(["encodeColorFps", config.get_value("encodeColorFps")])
            if config.get_value("encodeColor"):
                if hasattr(self, 'confManager'):
                    self.confManager.args.encode["color"] = config.get_value("encodeColorFps")

        if config.get_value("encodeLeft") is not None and config.get_value("encodeLeftFps") is not None:
            self.setData(["encodeLeft", config.get_value("encodeLeft")])
            self.setData(["encodeLeftFps", config.get_value("encodeLeftFps")])
            if config.get_value("encodeLeft"):
                if hasattr(self, 'confManager'):
                    self.confManager.args.encode["left"] = config.get_value("encodeLeftFps")

        if config.get_value("encodeRight") is not None and config.get_value("encodeRightFps") is not None:
            self.setData(["encodeRight", config.get_value("encodeRight")])
            self.setData(["encodeRightFps", config.get_value("encodeRightFps")])
            if config.get_value("encodeRight"):
                if hasattr(self, 'confManager'):
                    self.confManager.args.encode["right"] = config.get_value("encodeRightFps")

        if config.get_value("encodeDepth") is not None and config.get_value("encodeDepthFps") is not None:
            self.setData(["encodeDepth", config.get_value("encodeDepth")])
            self.setData(["encodeDepthFps", config.get_value("encodeDepthFps")])
            if config.get_value("encodeDepth"):
                if hasattr(self, 'confManager'):
                    self.confManager.args.encode["depth"] = config.get_value("encodeDepthFps")

        if config.get_value("encodeIr") is not None and config.get_value("encodeIrFps") is not None:
            self.setData(["encodeIr", config.get_value("encodeIr")])
            self.setData(["encodeIrFps", config.get_value("encodeIrFps")])
            # IR encoding might not be supported in args.encode directly or needs mapping
            pass

        if config.get_value("encodePointCloud") is not None:
            self.setData(["encodePointCloud", config.get_value("encodePointCloud")])
            # Point cloud enabled is on _demoInstance, which might not be ready if called too early
            # But startGui runs after __init__, so _demoInstance should exist (if we fix init order)
            if hasattr(self, '_demoInstance'):
                self._demoInstance.pointCloudEnabled = config.get_value("encodePointCloud")

        # The following methods are assumed to be part of the class containing this code
        # and are placed here based on the instruction's context for insertion.
        def guiOnToggleTofEncoding(self, enabled, fps):
            oldConfig = self.confManager.args.encode or {}
            if enabled:
                oldConfig["tof"] = fps
            elif "tof" in oldConfig:
                del oldConfig["tof"]
            self.updateArg("encode", oldConfig)

        def guiOnTogglePointCloud(self, enabled):
            self._demoInstance.pointCloudEnabled = enabled

        if config.get_value("reportTemp") is not None and config.get_value("reportCpu") is not None and config.get_value("reportMem") is not None:
            self.setData(["reportTemp", config.get_value("reportTemp")])
            self.setData(["reportCpu", config.get_value("reportCpu")])
            self.setData(["reportMem", config.get_value("reportMem")])
            # Reporting options are usually args
            if config.get_value("reportTemp") or config.get_value("reportCpu") or config.get_value("reportMem"):
                update_arg("report", True)
                # Specific report fields might need more complex handling
        
        return self.app.exec()
