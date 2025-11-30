# This Python file uses the following encoding: utf-8
import sys
from pathlib import Path

import blobconverter
import cv2
from PyQt5.QtQml import QQmlApplicationEngine, qmlRegisterType, qmlRegisterSingletonType, QQmlEngine
from PyQt5.QtQuick import QQuickPaintedItem
from PyQt5.QtGui import QImage
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable, QThreadPool
import depthai as dai

# To be used on the @QmlElement decorator
# (QML_IMPORT_MINOR_VERSION is optional)
from PyQt5.QtWidgets import QApplication
from depthai_sdk.previews import Previews
from depthai_sdk.utils import resizeLetterbox, createBlankFrame
from gui.config_handler import ConfigHandler

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
        painter.drawImage(0, 0, self.frame)

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
        instance.guiOnSelectReportingOptions(temp, cpu, memory)

    @pyqtSlot(str)
    def selectReportingPath(self, value):
        instance.guiOnSelectReportingPath(value)

    @pyqtSlot(str)
    def selectEncodingPath(self, value):
        instance.guiOnSelectEncodingPath(value)

    @pyqtSlot(bool, int)
    def toggleColorEncoding(self, enabled, fps):
        instance.guiOnToggleColorEncoding(enabled, fps)

    @pyqtSlot(bool, int)
    def toggleLeftEncoding(self, enabled, fps):
        instance.guiOnToggleLeftEncoding(enabled, fps)

    @pyqtSlot(bool, int)
    def toggleRightEncoding(self, enabled, fps):
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
        instance.guiOnToggleDepthEncoding(enabled, fps)

    @pyqtSlot(bool)
    def togglePointCloud(self, enabled):
        instance.guiOnTogglePointCloud(enabled)

    @pyqtSlot(bool, int)
    def toggleIrEncoding(self, enabled, fps):
        instance.guiOnToggleIrEncoding(enabled, fps)

    @pyqtSlot()
    def toggleRecording(self):
        instance.guiOnToggleRecording()


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
        w, h = int(self.writer.width()), int(self.writer.height())
        scaledFrame = resizeLetterbox(frame, (w, h))
        if len(frame.shape) == 3:
            if colorMode == QImage.Format_RGB888:
                scaledFrame = cv2.cvtColor(scaledFrame, cv2.COLOR_RGB2BGR)
            img = QImage(scaledFrame.data, w, h, frame.shape[2] * w, colorMode)
        else:
            img = QImage(scaledFrame.data, w, h, w, QImage.Format_Grayscale8)
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
        self.createProgressFrame()
        self.createProgressFrame()
        
        # Load configuration
        config = ConfigHandler()
        
        # Apply loaded configuration
        if config.get_value("sync") is not None:
            self.setData(["sync", config.get_value("sync")])
            self.guiOnToggleSync(config.get_value("sync"))
            
        if config.get_value("rgbDepthAlignment") is not None:
            self.setData(["rgbDepthAlignment", config.get_value("rgbDepthAlignment")])
            self.guiOnToggleRgbDepthAlignment(not config.get_value("rgbDepthAlignment"))
            
        if config.get_value("depthEnabled") is not None:
            self.setData(["depthEnabled", config.get_value("depthEnabled")])
            self.guiOnToggleDepth(config.get_value("depthEnabled"))
            
        if config.get_value("nnEnabled") is not None:
            self.setData(["nnEnabled", config.get_value("nnEnabled")])
            self.guiOnToggleNN(config.get_value("nnEnabled"))
            
        if config.get_value("disparityEnabled") is not None:
            self.setData(["disparityEnabled", config.get_value("disparityEnabled")])
            self.guiOnToggleDisparity(config.get_value("disparityEnabled"))
            
        if config.get_value("cnnModel") is not None:
            self.setData(["cnnModel", config.get_value("cnnModel")])
            self.guiOnAiSetupUpdate(cnn=config.get_value("cnnModel"))
            
        if config.get_value("shaves") is not None:
            self.setData(["shaves", config.get_value("shaves")])
            self.guiOnAiSetupUpdate(shave=config.get_value("shaves"))
            
        if config.get_value("modelSource") is not None:
            self.setData(["modelSource", config.get_value("modelSource")])
            self.guiOnAiSetupUpdate(source=config.get_value("modelSource"))
            
        if config.get_value("fullFov") is not None:
            self.setData(["fullFov", config.get_value("fullFov")])
            self.guiOnAiSetupUpdate(fullFov=config.get_value("fullFov"))
            
        if config.get_value("sbb") is not None:
            self.setData(["sbb", config.get_value("sbb")])
            self.guiOnAiSetupUpdate(sbb=config.get_value("sbb"))
            
        if config.get_value("sbbFactor") is not None:
            self.setData(["sbbFactor", config.get_value("sbbFactor")])
            self.guiOnAiSetupUpdate(sbbFactor=config.get_value("sbbFactor"))
            
        if config.get_value("ovVersion") is not None:
            self.setData(["ovVersion", config.get_value("ovVersion")])
            self.guiOnAiSetupUpdate(ov=config.get_value("ovVersion").replace("VERSION_", ""))
            
        if config.get_value("countLabel") is not None:
            self.setData(["countLabel", config.get_value("countLabel")])
            self.guiOnAiSetupUpdate(countLabel=config.get_value("countLabel"))
            
        if config.get_value("subpixel") is not None:
            self.setData(["subpixel", config.get_value("subpixel")])
            self.guiOnDepthSetupUpdate(subpixel=config.get_value("subpixel"))
            
        if config.get_value("extendedDisparity") is not None:
            self.setData(["extendedDisparity", config.get_value("extendedDisparity")])
            self.guiOnDepthSetupUpdate(extended=config.get_value("extendedDisparity"))
            
        if config.get_value("lrc") is not None:
            self.setData(["lrc", config.get_value("lrc")])
            self.guiOnDepthSetupUpdate(lrc=config.get_value("lrc"))
            
        if config.get_value("disparityConfidenceThreshold") is not None:
            self.setData(["disparityConfidenceThreshold", config.get_value("disparityConfidenceThreshold")])
            self.guiOnDepthConfigUpdate(dct=config.get_value("disparityConfidenceThreshold"))
            
        if config.get_value("lrcThreshold") is not None:
            self.setData(["lrcThreshold", config.get_value("lrcThreshold")])
            self.guiOnDepthConfigUpdate(lrcThreshold=config.get_value("lrcThreshold"))
            
        if config.get_value("bilateralSigma") is not None:
            self.setData(["bilateralSigma", config.get_value("bilateralSigma")])
            self.guiOnDepthConfigUpdate(sigma=config.get_value("bilateralSigma"))
            
        if config.get_value("depthRangeFrom") is not None and config.get_value("depthRangeTo") is not None:
            self.setData(["depthRangeFrom", config.get_value("depthRangeFrom")])
            self.setData(["depthRangeTo", config.get_value("depthRangeTo")])
            self.guiOnDepthSetupUpdate(depthFrom=int(config.get_value("depthRangeFrom") * 1000), depthTo=int(config.get_value("depthRangeTo") * 1000))
            
        if config.get_value("medianFilter") is not None:
            self.setData(["medianFilter", config.get_value("medianFilter")])
            value = getattr(dai.MedianFilter, config.get_value("medianFilter"))
            self.guiOnDepthConfigUpdate(median=value)
            
        if config.get_value("irLaserDotProjector") is not None:
            self.setData(["irLaserDotProjector", config.get_value("irLaserDotProjector")])
            self.guiOnDepthConfigUpdate(irLaser=config.get_value("irLaserDotProjector"))
            
        if config.get_value("irFloodIlluminator") is not None:
            self.setData(["irFloodIlluminator", config.get_value("irFloodIlluminator")])
            self.guiOnDepthConfigUpdate(irFlood=config.get_value("irFloodIlluminator"))
            
        if config.get_value("colorIso") is not None and config.get_value("colorExposure") is not None:
            self.setData(["colorIso", config.get_value("colorIso")])
            self.setData(["colorExposure", config.get_value("colorExposure")])
            self.guiOnCameraConfigUpdate("color", sensitivity=config.get_value("colorIso"), exposure=config.get_value("colorExposure"))
            
        if config.get_value("colorContrast") is not None:
            self.setData(["colorContrast", config.get_value("colorContrast")])
            self.guiOnCameraConfigUpdate("color", contrast=config.get_value("colorContrast"))
            
        if config.get_value("colorBrightness") is not None:
            self.setData(["colorBrightness", config.get_value("colorBrightness")])
            self.guiOnCameraConfigUpdate("color", brightness=config.get_value("colorBrightness"))
            
        if config.get_value("colorSaturation") is not None:
            self.setData(["colorSaturation", config.get_value("colorSaturation")])
            self.guiOnCameraConfigUpdate("color", saturation=config.get_value("colorSaturation"))
            
        if config.get_value("colorSharpness") is not None:
            self.setData(["colorSharpness", config.get_value("colorSharpness")])
            self.guiOnCameraConfigUpdate("color", sharpness=config.get_value("colorSharpness"))
            
        if config.get_value("colorFps") is not None:
            self.setData(["colorFps", config.get_value("colorFps")])
            self.guiOnCameraSetupUpdate("color", fps=config.get_value("colorFps"))
            
        if config.get_value("colorResolution") is not None:
            self.setData(["colorResolution", config.get_value("colorResolution")])
            state = config.get_value("colorResolution")
            if state == "THE_1080_P":
                self.guiOnCameraSetupUpdate("color", resolution=1080)
            elif state == "THE_4_K":
                self.guiOnCameraSetupUpdate("color", resolution=2160)
            elif state == "THE_12_MP":
                self.guiOnCameraSetupUpdate("color", resolution=3040)
                
        if config.get_value("monoIso") is not None and config.get_value("monoExposure") is not None:
            self.setData(["monoIso", config.get_value("monoIso")])
            self.setData(["monoExposure", config.get_value("monoExposure")])
            self.guiOnCameraConfigUpdate("left", sensitivity=config.get_value("monoIso"), exposure=config.get_value("monoExposure"))
            self.guiOnCameraConfigUpdate("right", sensitivity=config.get_value("monoIso"), exposure=config.get_value("monoExposure"))
            
        if config.get_value("monoContrast") is not None:
            self.setData(["monoContrast", config.get_value("monoContrast")])
            self.guiOnCameraConfigUpdate("left", contrast=config.get_value("monoContrast"))
            self.guiOnCameraConfigUpdate("right", contrast=config.get_value("monoContrast"))
            
        if config.get_value("monoBrightness") is not None:
            self.setData(["monoBrightness", config.get_value("monoBrightness")])
            self.guiOnCameraConfigUpdate("left", brightness=config.get_value("monoBrightness"))
            self.guiOnCameraConfigUpdate("right", brightness=config.get_value("monoBrightness"))
            
        if config.get_value("monoSaturation") is not None:
            self.setData(["monoSaturation", config.get_value("monoSaturation")])
            self.guiOnCameraConfigUpdate("left", saturation=config.get_value("monoSaturation"))
            self.guiOnCameraConfigUpdate("right", saturation=config.get_value("monoSaturation"))
            
        if config.get_value("monoSharpness") is not None:
            self.setData(["monoSharpness", config.get_value("monoSharpness")])
            self.guiOnCameraConfigUpdate("left", sharpness=config.get_value("monoSharpness"))
            self.guiOnCameraConfigUpdate("right", sharpness=config.get_value("monoSharpness"))
            
        if config.get_value("monoFps") is not None:
            self.setData(["monoFps", config.get_value("monoFps")])
            self.guiOnCameraSetupUpdate("left", fps=config.get_value("monoFps"))
            self.guiOnCameraSetupUpdate("right", fps=config.get_value("monoFps"))
            
        if config.get_value("monoResolution") is not None:
            self.setData(["monoResolution", config.get_value("monoResolution")])
            state = config.get_value("monoResolution")
            if state == "THE_720_P":
                self.guiOnCameraSetupUpdate("left", resolution=720)
                self.guiOnCameraSetupUpdate("right", resolution=720)
            elif state == "THE_800_P":
                self.guiOnCameraSetupUpdate("left", resolution=800)
                self.guiOnCameraSetupUpdate("right", resolution=800)
            elif state == "THE_400_P":
                self.guiOnCameraSetupUpdate("left", resolution=400)
                self.guiOnCameraSetupUpdate("right", resolution=400)
        
        return self.app.exec()
