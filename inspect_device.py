import depthai as dai

def print_camera_features():
    try:
        # Connect to the device
        with dai.Device() as device:
            print(f"Device connected: {device.getMxId()}")
            print(f"Device name: {device.getDeviceName()}")
            print("-" * 50)
            
            # Get connected camera features
            print("Connected Camera Features:")
            cameras = device.getConnectedCameraFeatures()
            
            for cam in cameras:
                print(f"\nCamera on Socket: {cam.socket}")
                print(f"  Sensor Name: {cam.sensorName}")
                print(f"  Supported Types (Resolutions):")
                for config in cam.configs:
                    print(f"    - Type: {config.type}, Width: {config.width}, Height: {config.height}")
                
                print(f"  Supported Colors: {[c.name for c in cam.supportedTypes]}")
                print(f"  Orientation: {cam.orientation}")
                # Check for other properties if available
                if hasattr(cam, 'maxFps'):
                     print(f"  Max FPS: {cam.maxFps}")


    except Exception as e:
        print(f"Failed to connect to device or retrieve info: {e}")

if __name__ == "__main__":
    print_camera_features()
