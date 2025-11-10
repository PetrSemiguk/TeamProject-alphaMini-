import asyncio
import logging
import sys
import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice
from mini.apis.api_action import MoveRobot, MoveRobotDirection, MoveRobotResponse, StopAllAction
from mini.apis.api_sence import GetInfraredDistance
from mini.apis.base_api import MiniApiResultType
from mini.apis.api_sound import StartPlayTTS

# === SDK CONFIG ===
MiniSdk.set_log_level(logging.INFO)
MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

# === CONSTANTS ===
ROBOT_ID = "412"
SEARCH_TIMEOUT = 20
WALK_STEPS = 20
STEP_SIZE = 5                # шаги за один execute
OBSTACLE_DISTANCE_MM = 100   # порог в миллиметрах
RESUME_WAIT = 1.5
SLEEP_AFTER_PROGRAM = 3
OBSTACLE_BYPASS_STEPS = 7    # шаги при обходе препятствия

PHRASE_START = "Welcome to PSB academy, I am robot promoter. Nice to meet you!"
PHRASE_STOP = "Obstacle detected. Initiating bypass."
PHRASE_RESUME = "Bypass complete. Resuming normal path."

# === HELPER FUNCTIONS ===

async def search_device(serial_number: str, timeout: int) -> WiFiDevice:
    try:
        device = await MiniSdk.get_device_by_name(serial_number, timeout)
        print(f"[✓] Found device: {device}")
        return device
    except Exception as e:
        print(f"[X] Error searching device: {e}")
        return None

async def connect_device(device: WiFiDevice):
    try:
        connected = await MiniSdk.connect(device)
        if connected:
            print(f"[✓] Connected to {device.name}")
            return True
        print("[X] Connection failed")
        return False
    except Exception as e:
        print(f"[X] Error connecting: {e}")
        return False

async def speak(text: str):
    tts = StartPlayTTS(text=text)
    result_type, response = await tts.execute()
    if result_type == MiniApiResultType.Success:
        print(f"[🗣] Spoke: '{text}'")
    else:
        print(f"[X] Failed to speak, result_type={result_type}")

async def get_distance() -> float:
    sensor = GetInfraredDistance()
    result_type, response = await sensor.execute()
    if result_type == MiniApiResultType.Success and hasattr(response, "distance"):
        print(f"[📏] Distance: {response.distance:.1f} mm")
        return response.distance
    print("[X] Failed to get distance")
    return 1000.0  # если ошибка — считаем путь свободным

async def move_forward(steps: int):
    move_cmd = MoveRobot(step=steps, direction=MoveRobotDirection.FORWARD)
    result_type, response = await move_cmd.execute()
    if result_type == MiniApiResultType.Success and isinstance(response, MoveRobotResponse) and response.isSuccess:
        print(f"[→] Walked forward {steps} steps")
        return True
    print("[X] Move failed")
    return False

async def turn_left():
    move_cmd = MoveRobot(step=1, direction=MoveRobotDirection.LEFTWARD)
    result_type, response = await move_cmd.execute()
    if result_type == MiniApiResultType.Success and isinstance(response, MoveRobotResponse) and response.isSuccess:
        print(f"[↩️] Turned left ~30°")
    else:
        print("[X] Turn left failed")
    await asyncio.sleep(0.2)

async def turn_right():
    move_cmd = MoveRobot(step=1, direction=MoveRobotDirection.RIGHTWARD)
    result_type, response = await move_cmd.execute()
    if result_type == MiniApiResultType.Success and isinstance(response, MoveRobotResponse) and response.isSuccess:
        print(f"[↪️] Turned right ~30°")
    else:
        print("[X] Turn right failed")
    await asyncio.sleep(0.2)

# === 90° TURN HELPERS ===
async def turn_left_90():
    for _ in range(3):  # 3 маленьких шага ~30° = 90°
        await turn_left()
        await asyncio.sleep(0.1)

async def turn_right_90():
    for _ in range(3):  # 3 маленьких шага ~30° = 90°
        await turn_right()
        await asyncio.sleep(0.1)

# === OBSTACLE BYPASS LOGIC ===
async def bypass_obstacle():
    """Обход препятствия"""
    await speak(PHRASE_STOP)

    # Лево 90° и шаги в обход
    await turn_left_90()
    await move_forward(OBSTACLE_BYPASS_STEPS)

    # Прямо
    await turn_right_90()
    await move_forward(OBSTACLE_BYPASS_STEPS)

    # Прямо
    await move_forward(OBSTACLE_BYPASS_STEPS)

    # Направо 90° и шаги
    await turn_right_90()
    await move_forward(OBSTACLE_BYPASS_STEPS)

    # Влево 90° — возвращение к исходному направлению
    await turn_left_90()
    await speak(PHRASE_RESUME)

# === MAIN WALKING LOGIC ===
async def walk_with_obstacle_check():
    while True:
        steps_done = 0
        while steps_done < WALK_STEPS:
            distance = await get_distance()
            if distance <= OBSTACLE_DISTANCE_MM:
                print(f"[🚧] Obstacle detected at {distance:.1f} mm! Performing bypass.")
                await StopAllAction(is_serial=True).execute()
                await bypass_obstacle()
                continue  # проверяем путь снова

            moved = await move_forward(STEP_SIZE)
            if moved:
                steps_done += STEP_SIZE

            await asyncio.sleep(0.1)

        # После 20 шагов делаем 90° поворот налево
        await turn_left_90()
        # Произнесём фразу после поворота
        await speak(PHRASE_START)

# === MAIN PROGRAM ===
async def main():
    device = await search_device(ROBOT_ID, SEARCH_TIMEOUT)
    if not device:
        print("[X] Robot not found")
        return

    if not await connect_device(device):
        print("[X] Connection failed")
        return

    await MiniSdk.enter_program()
    print("[✓] Entered program mode")
    await asyncio.sleep(SLEEP_AFTER_PROGRAM)

    await speak
