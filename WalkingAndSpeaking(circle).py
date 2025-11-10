import asyncio
import logging
import sys
import time

import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice
# Импорт для движения и остановки
from mini.apis.api_action import MoveRobot, MoveRobotDirection, MoveRobotResponse, StopAllAction
# Импорт для руки
from mini.apis.api_action import PlayAction, PlayActionResponse
# Импорт для датчика расстояния
from mini.apis.api_sence import GetInfraredDistance
from mini.apis.base_api import MiniApiResultType
# Импорт для TTS
from mini.apis.api_sound import StartPlayTTS
# Импорт для обнаружения лица
from mini.apis.api_observe import ObserveFaceDetect
from mini.pb2.codemao_facedetecttask_pb2 import FaceDetectTaskResponse

MiniSdk.set_log_level(logging.INFO)
MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

ROBOT_ID = "412"
SEARCH_TIMEOUT = 20
FORWARD_STEPS = 5  # Шаги вперед в цикле
TURN_STEPS = 1  # Шаги поворота в цикле (примерно 30 градусов)
SLEEP_TIME = 0.3
OBSTACLE_DISTANCE_MM = 150  # Расстояние для обнаружения препятствия
OBSTACLE_BYPASS_STEPS = 7  # Шаги для обхода препятствия
PAUSE_DURATION = 8  # Длительность паузы при обнаружении лица

# Фразы
PHRASE_PROMOTION = "Welcome to PSB academy, I am robot promoter. Nice to meet you!"
PHRASE_STOP = "Im fine, just need to avoid obstacle"
PHRASE_RESUME = "Resuming promoting"
PHRASE_FACE_DETECTED = "Hi, how are you. If u have any questions, scan the QR code"

# Глобальные переменные для управления состоянием
face_observer: ObserveFaceDetect | None = None
is_robot_paused = False
last_face_action_time = 0
SPEECH_COOLDOWN = 5  # Задержка между действиями при обнаружении лица


# --- Базовые функции (Поиск, Подключение, Речь) ---

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


async def speak(text: str):
    tts = StartPlayTTS(text=text)
    asyncio.create_task(tts.execute())
    print(f"[🗣] Spoke: '{text}' (in background)")


# --- Движение ---

async def move_forward(steps: int):
    block = MoveRobot(step=steps, direction=MoveRobotDirection.FORWARD)
    resultType, response = await block.execute()
    if resultType == MiniApiResultType.Success and isinstance(response, MoveRobotResponse) and response.isSuccess:
        print(f"[→] Walked forward {steps} steps")
        return True
    else:
        print("[X] Move forward failed!")
        return False


async def turn_left(steps: int):
    block = MoveRobot(step=steps, direction=MoveRobotDirection.LEFTWARD)
    resultType, response = await block.execute()
    if resultType == MiniApiResultType.Success and isinstance(response, MoveRobotResponse) and response.isSuccess:
        print(f"[↰] Turned left ({steps} step)")
    else:
        print("[X] Turn left failed!")


async def turn_right(steps: int):
    block = MoveRobot(step=steps, direction=MoveRobotDirection.RIGHTWARD)
    resultType, response = await block.execute()
    if resultType == MiniApiResultType.Success and isinstance(response, MoveRobotResponse) and response.isSuccess:
        print(f"[↱] Turned right ({steps} step)")
    else:
        print("[X] Turn right failed!")


async def turn_left_90():
    for _ in range(3):
        await turn_left(TURN_STEPS)  # 3 x 30° = 90°
        await asyncio.sleep(0.1)


async def turn_right_90():
    for _ in range(3):
        await turn_right(TURN_STEPS)  # 3 x 30° = 90°
        await asyncio.sleep(0.1)


# --- Действия (Рука) ---

async def play_action_by_name(action_name: str):
    play_cmd = PlayAction(action_name=action_name)
    result_type, response = await play_cmd.execute()
    if result_type == MiniApiResultType.Success and isinstance(response, PlayActionResponse) and response.isSuccess:
        print(f"Action '{action_name}' executed successfully.")
    else:
        print(f"Failed to execute action '{action_name}', result={result_type}")


# --- Обнаружение препятствий ---

async def get_distance() -> float:
    sensor = GetInfraredDistance()
    result_type, response = await sensor.execute()
    if result_type == MiniApiResultType.Success and hasattr(response, "distance"):
        return response.distance
    return 1000.0


async def bypass_obstacle():
    print("[⚠] Initiating obstacle bypass.")
    await speak(PHRASE_STOP)

    # Обход (схема: 90° влево, вперед, 90° вправо, 2х вперед, 90° вправо, вперед, 90° влево)
    await turn_left_90()
    await move_forward(OBSTACLE_BYPASS_STEPS)

    await turn_right_90()
    await move_forward(OBSTACLE_BYPASS_STEPS * 2)

    await turn_right_90()
    await move_forward(OBSTACLE_BYPASS_STEPS)

    await turn_left_90()

    await speak(PHRASE_RESUME)
    print("[✓] Obstacle bypassed. Resuming pattern.")


# --- Обнаружение лица ---

async def DoFaceAction():
    global is_robot_paused, last_face_action_time

    await StopAllAction(is_serial=True).execute()
    is_robot_paused = True
    print("[PAUSE] Robot paused due to face detection.")

    await speak(PHRASE_FACE_DETECTED)
    await play_action_by_name("greet_2")
    await asyncio.sleep(PAUSE_DURATION)

    is_robot_paused = False
    last_face_action_time = time.time()
    print("[RESUME] Robot resumed after face interaction.")


def face_detect_handler(msg: FaceDetectTaskResponse):
    global is_robot_paused, last_face_action_time

    if msg.isSuccess:
        count = msg.count
        current_time = time.time()

        if count > 0 and not is_robot_paused and (current_time - last_face_action_time) > SPEECH_COOLDOWN:
            asyncio.create_task(DoFaceAction())
        elif count > 0:
            print(f"[COUNT] Faces Detected: {count}. Action skipped (Paused or Cooldown).")
        else:
            print("[COUNT] Faces Detected: 0.")


def setup_face_observer():
    global face_observer
    if face_observer is None:
        face_observer = ObserveFaceDetect()
        face_observer.set_handler(face_detect_handler)
        face_observer.start()
        print("[OBSERVE] Face detection observer started.")


def stop_face_observer():
    global face_observer
    if face_observer:
        face_observer.stop()
        face_observer = None
        print("[OBSERVE] Face detection observer stopped.")


# --- Основной цикл движения (интегрированный с выбором направления) ---

async def walk_in_circle_pattern(turn_function):
    turn_counter = 0

    # Определяем название выбранного направления для вывода в консоль
    direction_name = "LEFTWARD (Налево)" if turn_function == turn_left else "RIGHTWARD (Направо)"
    print(f"[INFO] Chosen movement direction: {direction_name}")

    while True:
        # 1. Проверяем паузу (из-за обнаружения лица)
        if is_robot_paused:
            # print("Robot is paused. Waiting...") # Можно закомментировать, чтобы не спамить
            await asyncio.sleep(0.5)
            continue

        # 2. Проверяем препятствие
        distance = await get_distance()
        if distance <= OBSTACLE_DISTANCE_MM:
            print(f" Obstacle detected at {distance:.1f} mm! Stopping and bypassing.")
            await StopAllAction(is_serial=True).execute()
            await bypass_obstacle()
            # После обхода сразу переходим к следующей итерации цикла
            continue

        # 3. Движение вперед
        await move_forward(FORWARD_STEPS)
        await asyncio.sleep(SLEEP_TIME)

        # 4. Поворот (используем выбранную функцию)
        await turn_function(TURN_STEPS)
        turn_counter += 1
        # print(f"[🔁] Turn count: {turn_counter}") # Можно закомментировать, чтобы не спамить

        # 5. Промо-фраза каждые два поворота (полкруга)
        if turn_counter % 2 == 0:
            asyncio.create_task(speak(PHRASE_PROMOTION))

        await asyncio.sleep(SLEEP_TIME)


# --- Главная функция ---

async def main():
    # === ВЫБОР ОПЦИИ ===
    while True:
        print("\n--- Выбор направления движения ---")
        print("1: Все повороты налево (LEFTWARD)")
        print("2: Все повороты направо (RIGHTWARD)")
        choice = input("Введите 1 или 2: ")

        if choice == '1':
            selected_turn_function = turn_left
            break
        elif choice == '2':
            selected_turn_function = turn_right
            break
        else:
            print("Неверный ввод. Пожалуйста, введите 1 или 2.")
    # =====================

    device = await search_device_by_name(ROBOT_ID, SEARCH_TIMEOUT)
    if not device:
        print("[Error] No robot found.")
        return

    connected = await connect_device(device)
    if not connected:
        print("[Error] Could not connect to robot.")
        return

    try:
        await MiniSdk.enter_program()
        print("[✓] Entered programming mode.")
        await asyncio.sleep(1)

        # Настраиваем наблюдателя за лицом
        setup_face_observer()

        # Стартовая фраза
        await speak(PHRASE_PROMOTION)
        await asyncio.sleep(1)

        # Запускаем основной цикл с выбранной функцией поворота
        await walk_in_circle_pattern(selected_turn_function)

    except Exception as e:
        print(f"An unhandled error occurred: {e}")

    finally:
        # Очистка
        stop_face_observer()
        await MiniSdk.quit_program()
        await MiniSdk.release()
        print("[✓] Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Program interrupted by user.")
        asyncio.run(MiniSdk.quit_program())
        sys.exit(0)