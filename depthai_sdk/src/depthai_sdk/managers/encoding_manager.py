import traceback
from pathlib import Path
from ..previews import Previews
import depthai as dai
import os

class EncodingManager:
    """
    Manager class that handles video encoding
    """

    _encodingQueues = {}
    _encodingNodes = {}
    _encodingFiles = {}

    def __init__(self, encodeConfig: dict, encodeOutput=None):
        """
        Args:
            encodeConfig (dict): Encoding config consisting of keys as preview names and values being the encoding FPS
            encodeOutput (pathlib.Path, Optional): Output directory for the recorded videos
        """
        self.encodeConfig = encodeConfig
        self.encodeOutput = Path(encodeOutput) if encodeOutput is not None else None
        if self.encodeOutput is not None and not self.encodeOutput.exists():
            os.makedirs(self.encodeOutput, exist_ok=True)

    def createEncoders(self, pm):
        """
        Creates VideoEncoder nodes using Pipeline manager, based on config provided during initialization

        Args:
            pm (depthai_sdk.managers.PipelineManager): Pipeline Manager instance
        """

        self._encodingNodes.clear()
        for cameraName, encFps in self.encodeConfig.items():
            pm.createEncoder(cameraName, encFps)
            self._encodingNodes[cameraName] = getattr(pm.nodes, cameraName + "Enc")

    def createDefaultQueues(self, device):
        """
        Creates output queues for VideoEncoder nodes created in :code:`create_encoders` function.
        """
        self._encodingQueues.clear()
        self._encodingFiles.clear()

        for cameraName, node in self._encodingNodes.items():
            self._encodingQueues[cameraName] = device.getOutputQueue(cameraName + "EncXout", maxSize=30, blocking=True)

    def startRecording(self, output_path=None, enabled_streams=None):
        if output_path is not None:
            self.encodeOutput = Path(output_path)
            if not self.encodeOutput.exists():
                os.makedirs(self.encodeOutput, exist_ok=True)

        for cameraName, node in self._encodingNodes.items():
            if enabled_streams is not None and cameraName not in enabled_streams:
                continue
            suffix = ".h265" if node.getProfile() == dai.VideoEncoderProperties.Profile.H265_MAIN else ".h264"
            self._encodingFiles[cameraName] = (self.encodeOutput / cameraName).with_suffix(suffix).open('wb')

    def stopRecording(self):
        if not self._encodingFiles:
            print("No recording in progress.")
            return
            
        # Save references before clearing
        files_to_convert = dict(self._encodingFiles)
        
        # Close all files
        for name, file in files_to_convert.items():
            file.close()
        
        # Clear the active files dict
        self._encodingFiles.clear()
        
        # Convert to mp4
        self._convertToMp4(files_to_convert)

    def parseQueues(self):
        """
        Parse the output queues, consuming the available data packets in it and storing them inside opened stream files
        """
        for name, queue in self._encodingQueues.items():
            while queue.has():
                data = queue.get().getData()
                if name in self._encodingFiles:
                    data.tofile(self._encodingFiles[name])

    def _convertToMp4(self, files_dict):
        """
        Tries to perform FFMPEG-based conversion from raw stream into mp4 video.

        If successful, each stream file (e.g. :code:`color.h265`) will be available along with a ready to use video file
        (e.g. :code:`color.mp4`).

        In case of failure, this method will print traceback and commands that can be used for manual conversion
        """

        def printManual():
            print(
                "To view the encoded data, convert the stream file (.h264/.h265) into a video file (.mp4), using commands below:")
            cmd = "ffmpeg -framerate {} -i {} -c copy {}"
            for name, file in files_dict.items():
                print(cmd.format(self._encodingNodes[name].getFrameRate(), file.name, str(Path(file.name).with_suffix('.mp4'))))

        try:
            import ffmpy3
            for name, file in files_dict.items():
                fps = self._encodingNodes[name].getFrameRate()
                outName = str(Path(file.name).with_suffix('.mp4'))
                try:
                    ff = ffmpy3.FFmpeg(
                        inputs={file.name: "-y"},
                        outputs={outName: "-c copy -framerate {}".format(fps)}
                    )
                    print("Running conversion command... [{}]".format(ff.cmd))
                    ff.run()
                except ffmpy3.FFExecutableNotFoundError:
                    print("FFMPEG executable not found!")
                    traceback.print_exc()
                    printManual()
                except ffmpy3.FFRuntimeError:
                    print("FFMPEG runtime error!")
                    traceback.print_exc()
                    printManual()
            print("Video conversion complete!")
            for name, file in files_dict.items():
                print("Produced file: {}".format(str(Path(file.name).with_suffix('.mp4'))))
                # Cleanup source file
                try:
                    os.remove(file.name)
                    print("Deleted source file: {}".format(file.name))
                except OSError as e:
                    print("Error deleting source file {}: {}".format(file.name, e))

        except ImportError:
            print("Module ffmpy3 not found!")
            traceback.print_exc()
            printManual()
        except:
            print("Unknown error!")
            traceback.print_exc()
            printManual()

    def close(self):
        """
        Closes opened stream files and output queues. Called when demo is stopped.
        """
        for queue in self._encodingQueues.values():
            queue.close()

        if self._encodingFiles:
            files_to_convert = dict(self._encodingFiles)
            for name, file in files_to_convert.items():
                file.close()
            self._encodingFiles.clear()
            self._convertToMp4(files_to_convert)
