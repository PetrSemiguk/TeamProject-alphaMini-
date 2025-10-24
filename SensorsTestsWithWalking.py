import asyncio
import logging
import sys
import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice
from mini.apis.base_api import MiniApiResultType
from mini.apis.api_sound import StartPlayTTS
# --- ИМПОРТЫ ---
from mini.apis.api_action import MoveRobot, MoveRobotDirection, StopAllAction
from mini.apis.api_sence import GetInfraredDistance

# === SDK Configuration ===
MiniSdk.set_log_level(logging.INFO)
MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

# === Constants ===
ROBOT_ID = "412"
SEARCH_TIMEOUT = 20
SLEEP_DURATION = 1
PHRASE_TO_SPEAK_START = "Welcome to PSB academy, I am robot promoter. Nice to meet you!"
PHRASE_TO_SPEAK_STOP = "Stop. Obstacle detected."
PHRASE_TO_SPEAK_RESUME = "Obstacle removed. Resuming movement."  # Новая фраза
# *** ЦЕЛЕВОЕ РАССТОЯНИЕ ДЛЯ ОСТАНОВКИ ***
TARGET_DISTANCE_MM = 100
# *** ВРЕМЯ ОЖИДАНИЯ ПЕРЕД ПЕРЕЗАПУСКОМ ДВИЖЕНИЯ (в секундах) ***
RESUME_WAIT_TIME = 5


# --- Вспомогательные функции (без изменений) ---

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
        is_connected = await MiniSdk.connect(device)
        if is_connected:
            print(f"[✓] Successfully connected to {device.name}")
            return True
        else:
            print("[X] Connection failed")
            return False
    except Exception as e:
        print(f"[X] Error connecting: {e}")
        return False


async def make_alphamini_speak(text_to_speak: str):
    tts_block = StartPlayTTS(text=text_to_speak)
    await tts_block.execute()


# ----------------------------------------------------------------------
## Единый Цикл: Движение, Остановка, Ожидание и Продолжение
# ----------------------------------------------------------------------

async def move_and_monitor():
    """Движение шагами по 1, проверка сенсора после каждого шага.
       После остановки ждет, пока препятствие исчезнет, и продолжает движение."""

    print("\n=======================================================")
    print(f" [🤖] Движение шагами по 1. Остановка на {TARGET_DISTANCE_MM} мм.")
    print("=======================================================")

    monitor_command = GetInfraredDistance(is_serial=True)
    move_one_step_command = MoveRobot(
        step=1,
        direction=MoveRobotDirection.FORWARD,
        is_serial=True  # Блокирует выполнение до завершения 1 шага
    )

    while True:  # БЕСКОНЕЧНЫЙ ЦИКЛ, выход только по Ctrl+C

        # 1. ПРОВЕРКА СЕНСОРА ПЕРЕД ШАГОМ
        result_type, response = await monitor_command.execute()
        distance_mm = float('inf')

        if result_type == MiniApiResultType.Success and response and hasattr(response, 'distance'):
            distance_mm = response.distance

            if distance_mm <= TARGET_DISTANCE_MM:
                print(f"\n[🛑 СТОП!] Препятствие на {distance_mm} мм.")

                # --- ЛОГИКА ОСТАНОВКИ И ОЖИДАНИЯ ---
                await StopAllAction(is_serial=True).execute()  # Гарантированная остановка
                await make_alphamini_speak(PHRASE_TO_SPEAK_STOP)

                print(f"[⏸️] Ожидаю, пока препятствие будет убрано (>{TARGET_DISTANCE_MM} мм)...")

                # Цикл ожидания, пока расстояние не увеличится
                while distance_mm <= TARGET_DISTANCE_MM:
                    await asyncio.sleep(0.5)
                    result_type, response = await monitor_command.execute()
                    if result_type == MiniApiResultType.Success and response and hasattr(response, 'distance'):
                        distance_mm = response.distance
                        print(f"   [⏳] Текущее расстояние: {distance_mm} мм.")
                    else:
                        distance_mm = TARGET_DISTANCE_MM  # Если ошибка, ждем дальше, считая, что препятствие есть

                # Препятствие убрано!
                await make_alphamini_speak(PHRASE_TO_SPEAK_RESUME)
                print(f"[▶️] Препятствие убрано. Возобновляю движение через {RESUME_WAIT_TIME} секунд...")
                await asyncio.sleep(RESUME_WAIT_TIME)

                continue  # Возвращаемся в начало цикла, чтобы сделать следующий шаг

        # 2. ВЫПОЛНЕНИЕ ОДНОГО ШАГА (если препятствий нет)
        # print("[🏃] Выполняю шаг...") # Отключено для чистоты вывода
        await move_one_step_command.execute()

        await asyncio.sleep(0.05)  # Пауза между шагами


# ----------------------------------------------------------------------
## Основной контроллер
# ----------------------------------------------------------------------

async def main():
    device = await search_device_by_name(ROBOT_ID, SEARCH_TIMEOUT)
    if not device:
        print("[Error] Робот не найден.")
        return

    connected = await connect_device(device)
    if not connected:
        print("[Error] Could not connect to robot.")
        return

    try:
        program_success = await MiniSdk.enter_program()

        if program_success:
            print("[✓] Entered programming mode. Starting control loop...")
            await asyncio.sleep(SLEEP_DURATION)

            asyncio.create_task(make_alphamini_speak(PHRASE_TO_SPEAK_START))
            await asyncio.sleep(1)

            # Запускаем бесконечный цикл движения
            await move_and_monitor()

        else:
            print("[X] Error: Failed to enter programming mode.")

    except Exception as e:
        print(f"[X] An error occurred in main: {e}")

    finally:
        # Робот остаётся в программном режиме до нажатия Ctrl+C
        await MiniSdk.release()
        print("[✓] Программа Python завершена. Робот остаётся в программном режиме.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Выход из программы и корректное завершение работы робота
        print("\n[!] Program interrupted by user. Quitting robot program.")
        asyncio.run(MiniSdk.quit_program())
        sys.exit(0)