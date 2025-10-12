import asyncio  # Enables writing asynchronous (non-blocking) code
import logging  # For controlling the logging output
import mini.mini_sdk as MiniSdk  # Main SDK to control AlphaMini
from mini.dns.dns_browser import WiFiDevice  # Represents a discovered AlphaMini robot over Wi-Fi

# === SDK Configuration ===
MiniSdk.set_log_level(logging.INFO)  # Show informative logs in the console
MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)  # Set the AlphaMini type (EDU version)

# === Constants ===
ROBOT_ID = "412"  # Partial serial number of the robot (last few digits)
SEARCH_TIMEOUT = 10  # Time (in seconds) to wait for robot discovery

# === Robot Wrapper Class ===
class Robot:
    def __init__(self, device: WiFiDevice):
        self.device = device

# === Step 1: Discover Robot by Partial Serial Number ===
async def search_device_by_name(serial_number_suffix: str, timeout: int) -> WiFiDevice:
    try:
        result = await MiniSdk.get_device_by_name(serial_number_suffix, timeout)
        print(f"[✓] Found device: {result}")
        return result
    except Exception as e:
        print(f"[X] Error searching for device: {e}")
        return None

# === Step 2: Connect to the Robot ===
async def connect_device(device: WiFiDevice) -> Robot:
    try:
        connected = await MiniSdk.connect(device)
        if connected:
            print(f"[✓] Successfully connected to {device.name}")
            return Robot(device)
        else:
            print("[X] Connection failed")
            return None
    except Exception as e:
        print(f"[X] Error connecting to device: {e}")
        return None

# === Step 3: Enter Programming Mode ===
async def enter_programming_mode():
    try:
        await MiniSdk.enter_program()
        print("[✓] Entered programming mode")
    except Exception as e:
        print(f"[X] Error entering programming mode: {e}")

# === Step 4: Optional Shutdown Placeholder ===
async def shutdown_robot():
    print("[✓] Finished robot session (placeholder for future shutdown commands)")

# === Main Async Routine ===
async def main():
    device = await search_device_by_name(ROBOT_ID, SEARCH_TIMEOUT)
    if not device:
        print("[Error] No robot found.")
        return

    robot = await connect_device(device)
    if not robot:
        print("[Error] Connection failed.")
        return

    await enter_programming_mode()
    await shutdown_robot()

# === Run Main Async Logic ===
if __name__ == "__main__":
    asyncio.run(main())
