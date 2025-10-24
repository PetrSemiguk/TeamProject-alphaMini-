import asyncio
import logging
import sys
import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice
from mini.apis.api_action import MoveRobot, MoveRobotDirection, MoveRobotResponse
from mini.apis.base_api import MiniApiResultType

# === SDK Configuration ===
MiniSdk.set_log_level(logging.INFO)
MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

# === Constants ===
ROBOT_ID = "412"      # последние цифры серийного номера робота
SEARCH_TIMEOUT = 10
STEP_SIZE = 1
WALK_STEPS = 20        # шагов вперед за один проход
SLEEP_DURATION = 2

# === Search and Connect ===
async def search_device_by_name(serial_number_suffix: str, timeout: int) -> WiFiDevice:
    try:
        result = await MiniSdk.get_device_by_name(serial_number_suffix, timeout)
        print(f"[✓] Found device: {result}")
        return result
    except Exception as e:
        print(f"[X] Error searching for device: {e}")
        return None

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

# === Movement ===
async def move_forward(steps: int):
    block = MoveRobot(step=steps, direction=MoveRobotDirection.FORWARD)
    resultType, response = await block.execute()
    if (
        resultType == MiniApiResultType.Success
        and isinstance(response, MoveRobotResponse)
        and response.isSuccess
    ):
        print(f"[→] Walked forward {steps} steps")
    else:
        print("[X] Move failed!")

async def turn_left():
    # Делаем три "малых шага влево" для полного поворота на 90°
    for i in range(3):
        block = MoveRobot(step=1, direction=MoveRobotDirection.LEFTWARD)
        resultType, response = await block.execute()
        if (
            resultType == MiniApiResultType.Success
            and isinstance(response, MoveRobotResponse)
            and response.isSuccess
        ):
            print(f"[↰] Turned left part {i+1}/3")
        else:
            print("[X] Turn failed!")
        await asyncio.sleep(0.1)  # короткая пауза для плавности и ускорения поворота

# === Main Loop ===
async def walk_forever():
    while True:
        await move_forward(WALK_STEPS)
        await asyncio.sleep(0.5)
        await turn_left()
        await asyncio.sleep(0.2)  # небольшая пауза после поворота

# === Main ===
async def main():
    device = await search_device_by_name(ROBOT_ID, SEARCH_TIMEOUT)
    if not device:
        print("[Error] No robot found.")
        return

    connected = await connect_device(device)
    if not connected:
        print("[Error] Could not connect to robot.")
        return

    await MiniSdk.enter_program()
    print("[✓] Entered programming mode.")
    await asyncio.sleep(SLEEP_DURATION)

    # 🚶 Робот ходит по квадрату бесконечно
    await walk_forever()

    await MiniSdk.quit_program()
    await MiniSdk.release()
    print("[✓] Shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Program interrupted by user.")
        sys.exit(0)
