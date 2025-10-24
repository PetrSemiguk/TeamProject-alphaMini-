import asyncio
import logging
import sys
import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice
from PIL import Image
from io import BytesIO

# === SDK Configuration ===
MiniSdk.set_log_level(logging.INFO)
MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

# === Constants ===
ROBOT_ID = "412"  # последние цифры серийного номера AlphaMini
SEARCH_TIMEOUT = 20  # время поиска (сек)
SLEEP_DURATION = 2  # задержка после подключения

# === Search for the robot ===
async def search_device_by_name(serial_number_suffix: str, timeout: int) -> WiFiDevice:
    try:
        result = await MiniSdk.get_device_by_name(serial_number_suffix, timeout)
        print(f"[✓] Found device: {result}")
        return result
    except Exception as e:
        print(f"[X] Error searching for device: {e}")
        return None

# === Connect to the robot ===
async def connect_device(device: WiFiDevice):
    try:
        connected = await MiniSdk.connect(device)
        if connected:
            print(f"[✓] Successfully connected to {device.name}")
            return True
        else:
            print("[X] Connection failed")
            return False
    except Exception as e:
        print(f"[X] Error connecting: {e}")
        return False

# === Get camera images ===
async def get_camera_images(programmer):
    # === Проверка датчиков камеры 1 ====
    if programmer.camera1:
        camera1 = programmer.camera1
        await asyncio.sleep(1)
        frame1 = await camera1.get_frame()
        print(f"[INFO] Camera image received:\n{str(frame1)}")
    else:
        print("[Error] No camera 1 found.")

    # === Проверка датчиков камеры 2 ====
    if programmer.camera2:
        camera2 = programmer.camera2
        await asyncio.sleep(1)
        frame2 = await camera2.get_frame()
        print(f"[INFO] Camera image received:\n{str(frame2)}")
    else:
        print("[Error] No camera 2 found.")

    # === Проверка датчиков камеры 3 ====
    if programmer.camera3:
        camera3 = programmer.camera3
        await asyncio.sleep(1)
        frame3 = await camera3.get_frame()
        print(f"[INFO] Camera image received:\n{str(frame3)}")
    else:
        print("[Error] No camera 3 found.")

    # === Проверка датчиков камеры 4 ====
    if programmer.camera4:
        camera4 = programmer.camera4
        await asyncio.sleep(1)
        frame4 = await camera4.get_frame()
        print(f"[INFO] Camera image received:\n{str(frame4)}")
    else:
        print("[Error] No camera 4 found.")

# === Check if human detected in the images ===
async def check_human_in_images(frame1, frame2, frame3, frame4):
    # Replace with your own logic for detecting humans in images
    # For example, using OpenCV library:
    # https://docs.opencv.org/master/d7/d9f/tutorial_py_face_detection.html
    pass

# === Main connection and processing logic ===
async def main():
    device = await search_device_by_name(ROBOT_ID, SEARCH_TIMEOUT)
    if not device:
        print("[Error] No robot found.")
        return

    connected = await connect_device(device)
    if not connected:
        print("[Error] Couldn't connect to the robot.")
        sys.exit()

    programmer = MiniSdk.Programmer()
    await programmer.connect(device)

    # === Check if human detected in images ====
    frames = (frame1, frame2, frame3, frame4)
    human_detected = await check_human_in_images(*frames)

    if human_detected:
        print("[INFO] Human detected!")
        # Replace with your own logic for stopping the robot and making sounds
        pass
    else:
        print("[INFO] No human detected.")
        # Replace with your own logic for continuing to process images
        pass

    await asyncio.sleep(SLEEP_DURATION)
    await programmer.disconnect()

# === Main ====
if name == "main":
    asyncio.run(main())
else:
    pass