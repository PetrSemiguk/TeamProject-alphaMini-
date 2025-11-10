import asyncio
import logging
import sys

import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice
from mini.apis.api_action import MoveRobot, MoveRobotDirection, MoveRobotResponse, StopAllAction
from mini.apis.api_sence import GetInfraredDistance
from mini.apis.base_api import MiniApiResultType
from mini.apis.api_sound import StartPlayTTS
# === ИМПОРТ ДЛЯ ОБНАРУЖЕНИЯ ЛИЦ ===
from mini.apis.api_observe import ObserveFaceDetect
from mini.pb2.codemao_facedetecttask_pb2 import FaceDetectTaskResponse

# ==================================

# === SDK CONFIG ===
MiniSdk.set_log_level(logging.INFO)
MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

# === CONSTANTS ===
ROBOT_ID = "412"
SEARCH_TIMEOUT = 20
WALK_STEPS = 20
STEP_SIZE = 5  # шаги за один execute
OBSTACLE_DISTANCE_MM = 150  # порог в миллиметрах
RESUME_WAIT = 1.5
SLEEP_AFTER_PROGRAM = 3
OBSTACLE_BYPASS_STEPS = 7  # шаги при обходе препятствия

# === ФРАЗЫ ===
PHRASE_START = "Welcome to PSB academy, I am robot promoter. Nice to meet you!"
PHRASE_STOP = "Obstacle detected. Initiating bypass."
PHRASE_RESUME = "Bypass complete. Resuming normal path."
PHRASE_FACE_DETECTED = "Hi, how are you. If u have any questions, scan the QR code"

# === ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ===
face_observer: ObserveFaceDetect | None = None
is_face_detected = False
last_face_speech_time = 0
SPEECH_COOLDOWN = 5  # Задержка в секундах между приветствиями


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
    # Используем create_task для неблокирующего вызова TTS
    asyncio.create_task(tts.execute())
    print(f"[🗣] Spoke: '{text}' (in background)")


async def get_distance() -> float:
    sensor = GetInfraredDistance()
    result_type, response = await sensor.execute()
    if result_type == MiniApiResultType.Success and hasattr(response, "distance"):
        print(f"[📏] Distance: {response.distance:.1f} mm")
        return response.distance
    print("[X] Failed to get distance")
    return 1000.0


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


# === FACE DETECTION LOGIC ===

def face_detect_handler(msg: FaceDetectTaskResponse):
    """
    Callback function that receives the face count event from the robot.
    """
    global is_face_detected, last_face_speech_time

    if msg.isSuccess:
        count = msg.count
        print(f"[COUNT] Faces Detected: **{count}**")

        # Обновляем глобальный флаг
        is_face_detected = count > 0

        # Если обнаружены лица и прошло достаточно времени с последнего приветствия
        if count > 0 and (asyncio.get_event_loop().time() - last_face_speech_time) > SPEECH_COOLDOWN:
            print("[FACE] Initiating welcome speech.")
            last_face_speech_time = asyncio.get_event_loop().time()
            # Запускаем речь как отдельную асинхронную задачу
            asyncio.create_task(speak(PHRASE_FACE_DETECTED))


def setup_face_observer():
    """Initializes and starts the continuous face detection observer."""
    global face_observer
    if face_observer is None:
        face_observer = ObserveFaceDetect()
        face_observer.set_handler(face_detect_handler)
        face_observer.start()
        print("[OBSERVE] Face detection observer started.")


def stop_face_observer():
    """Stops the continuous face detection observer."""
    global face_observer
    if face_observer:
        face_observer.stop()
        face_observer = None
        print("[OBSERVE] Face detection observer stopped.")


# === OBSTACLE BYPASS LOGIC (без изменений) ===

async def turn_left_90():
    for _ in range(3):
        await turn_left()
        await asyncio.sleep(0.1)


async def turn_right_90():
    for _ in range(3):
        await turn_right()
        await asyncio.sleep(0.1)


async def bypass_obstacle():
    """Обход препятствия с точными 90° поворотами"""
    await speak(PHRASE_STOP)

    # Лево 90° и 7 шагов
    await turn_left_90()
    await move_forward(OBSTACLE_BYPASS_STEPS)

    # Прямо 7 шагов (корректируем: после 90° поворота робот смотрит вдоль препятствия)
    await turn_right_90()
    await move_forward(OBSTACLE_BYPASS_STEPS)

    # Прямо 7 шагов
    await move_forward(OBSTACLE_BYPASS_STEPS)

    # Направо 90° и 7 шагов
    await turn_right_90()
    await move_forward(OBSTACLE_BYPASS_STEPS)

    # Влево 90° — возвращение к исходному направлению
    await turn_left_90()
    await speak(PHRASE_RESUME)


# === MAIN WALKING LOGIC ===

async def walk_with_obstacle_check():
    """
    Основной цикл движения.
    В цикле: делает 5 шагов, проверяет расстояние, если нет препятствия - повторяет.
    После 20 шагов (4 раза по 5 шагов) поворачивает и начинает новый блок.
    Фоновый наблюдатель лиц работает постоянно.
    """
    while True:
        steps_done = 0
        while steps_done < WALK_STEPS:
            # 1. Проверка препятствия
            distance = await get_distance()
            if distance <= OBSTACLE_DISTANCE_MM:
                print(f"[🚧] Obstacle detected at {distance:.1f} mm! Performing bypass.")
                await StopAllAction(is_serial=True).execute()
                await bypass_obstacle()
                continue  # проверяем путь снова после обхода

            # 2. Движение
            moved = await move_forward(STEP_SIZE)
            if moved:
                steps_done += STEP_SIZE

            # Фоновый наблюдатель лиц уже обрабатывает PHRASE_FACE_DETECTED,
            # нам не нужно ничего добавлять сюда для приветствия.

            await asyncio.sleep(0.1)

        # 3. После 20 шагов поворачиваем налево 3 раза (90°)
        for _ in range(3):
            await turn_left()
            await asyncio.sleep(0.2)

        # 4. Произнесём фразу перед следующим блоком шагов
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

    try:
        await MiniSdk.enter_program()
        print("[✓] Entered program mode")
        await asyncio.sleep(SLEEP_AFTER_PROGRAM)

        # === ЗАПУСК ФОНОВОГО НАБЛЮДАТЕЛЯ ЛИЦ ===
        setup_face_observer()
        # =======================================

        await speak(PHRASE_START)
        await walk_with_obstacle_check()

    except Exception as e:
        print(f"[FATAL ERROR] An unhandled error occurred: {e}")
    finally:
        # === ОСТАНОВКА НАБЛЮДАТЕЛЯ ЛИЦ ПРИ ЗАВЕРШЕНИИ ===
        stop_face_observer()
        # ===============================================
        print("\n[SHUTDOWN] Exiting programming mode and releasing SDK resources...")
        await MiniSdk.quit_program()
        await MiniSdk.release()
        print("[SHUTDOWN] Complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Program interrupted by user (Ctrl+C)")
        # Принудительный выход из режима программы
        asyncio.run(MiniSdk.quit_program())
        sys.exit(0)