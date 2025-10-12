import asyncio
import logging
import sys
from mini.apis.api_action import MoveRobot, MoveRobotDirection, MoveRobotResponse
from mini.apis.api_action import PlayAction, PlayActionResponse
from mini.apis.base_api import MiniApiResultType
import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice

# === SDK Configuration ===
MiniSdk.set_log_level(logging.INFO)
MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

# === Constants ===
ROBOT_ID = "412"  # последние цифры серийника
SEARCH_TIMEOUT = 20  # сек — время поиска
SLEEP_DURATION = 2
STEP_SIZE = 1  # шаг движения
TURN_STEPS = 12  # примерное количество шагов для поворота 180° (можно откалибровать)


# === Robot Wrapper ===
class Robot:
    def __init__(self, device: WiFiDevice):
        self.device = device


# === Step 1: Discover Robot ===
async def search_device_by_name(serial_number_suffix: str, timeout: int) -> WiFiDevice:
    try:
        result = await MiniSdk.get_device_by_name(serial_number_suffix, timeout)
        print(f"[✓] Found device: {result}")
        return result
    except Exception as e:
        print(f"[X] Error searching for device: {e}")
        return None


# === Step 2: Connect Robot ===
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


# === Movement Functions ===
async def move_robot(direction: MoveRobotDirection, step: int = STEP_SIZE):
    block = MoveRobot(step=step, direction=direction)
    resultType, response = await block.execute()
    print(f"move_robot result: {response}")
    if not (resultType == MiniApiResultType.Success and
            response is not None and
            isinstance(response, MoveRobotResponse) and
            response.isSuccess):
        print("Move command failed!")


async def play_builtin_action(name: str):
    block = PlayAction(action_name=name)
    resultType, response = await block.execute()
    ok = (resultType == MiniApiResultType.Success and
          isinstance(response, PlayActionResponse) and
          response is not None and
          response.isSuccess)
    print(f"[→] action {name} -> {'OK' if ok else 'FAILED'}")


async def raise_hands():
    await play_builtin_action("021")  # Built-in action: Raise hands


# === Automatic Routine ===
async def automatic_routine():
    print("[→] Starting automatic routine...")

    # Идём вперёд 10 шагов
    for _ in range(10):
        await move_robot(MoveRobotDirection.FORWARD)

    # Разворот на 180° (примерное количество шагов TURN_STEPS)
    print("[→] Turning 180°")
    for _ in range(TURN_STEPS):
        await move_robot(MoveRobotDirection.LEFTWARD)

    # Идём назад 10 шагов
    for _ in range(10):
        await move_robot(MoveRobotDirection.BACKWARD)

    print("[→] Automatic routine finished.")


# === Main Routine ===
async def main():
    device = await search_device_by_name(ROBOT_ID, SEARCH_TIMEOUT)
    if not device:
        print("[Error] No robot found.")
        return

    robot = await connect_device(device)
    if not robot:
        print("[Error] Connection failed.")
        return

    try:
        await MiniSdk.enter_program()
        print("[✓] Entered programming mode")
        await asyncio.sleep(SLEEP_DURATION)

        # Запуск автоматической рутины
        await automatic_routine()

    finally:
        await MiniSdk.quit_program()
        await MiniSdk.release()
        print("[✓] Shutdown complete")


# === Run Program ===
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
        sys.exit(0)
