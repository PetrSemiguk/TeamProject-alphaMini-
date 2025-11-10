import asyncio
import logging
import sys

import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice
from mini.apis.api_sound import StartPlayTTS
from mini.apis.api_observe import ObserveFaceDetect
from mini.pb2.codemao_facedetecttask_pb2 import FaceDetectTaskResponse
from mini.apis.base_api import MiniApiResultType

# --- CONFIGURATION ---
MiniSdk.set_log_level(logging.INFO)
MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

# --- CONSTANTS ---
# ✅ ИЗМЕНЕНО: Используем ваш серийный номер 412
ROBOT_SERIAL_SUFFIX = "412"
TIMEOUT_DURATION = 30  # Time in seconds to run the face count test (Время в секундах для выполнения теста на подсчет лиц)


# --- CORE UTILITIES ---

async def tts_speak(text: str):
    """Makes the robot speak a given phrase."""
    block: StartPlayTTS = StartPlayTTS(text=text)
    # Запускаем команду и немедленно возвращаемся, не блокируя асинхронный цикл
    await block.execute()


async def search_device_by_name(serial_number_suffix: str, timeout: int = 10) -> WiFiDevice | None:
    """Searches for the robot device on the network."""
    try:
        print(f"[SEARCH] Looking for robot with suffix: {serial_number_suffix}...")
        result = await MiniSdk.get_device_by_name(serial_number_suffix, timeout)
        print(f"[SEARCH] Found device: {result.name}")
        return result
    except Exception as e:
        print(f"[ERROR] Error searching for device: {e}")
        return None


async def test_connect(dev: WiFiDevice) -> bool:
    """Connects to the robot."""
    print(f"[CONNECT] Attempting connection to {dev.name}...")
    return await MiniSdk.connect(dev)


async def shutdown():
    """Exits program mode and releases SDK resources."""
    print("\n[SHUTDOWN] Exiting programming mode and releasing SDK resources...")
    await MiniSdk.quit_program()
    await MiniSdk.release()
    print("[SHUTDOWN] Complete.")


# --- FACE COUNT LOGIC ---

async def run_face_count_test():
    """
    Starts the continuous face detection observer and monitors the count.
    (Запускает непрерывный наблюдатель обнаружения лиц и отслеживает количество.)
    """
    print(f"\n[TEST] Starting Face Count Observer for {TIMEOUT_DURATION} seconds...")

    # Запускаем TTS как задачу, чтобы не блокировать основной поток
    asyncio.create_task(tts_speak("Starting face count test. Please step in front of my camera."))

    observer: ObserveFaceDetect = ObserveFaceDetect()

    # 1. Define the handler function (Определение функции-обработчика)
    def count_handler(msg: FaceDetectTaskResponse):
        """
        Callback function that receives the face count event from the robot.
        (Функция обратного вызова, которая получает событие подсчета лиц от робота.)
        """
        if msg.isSuccess:
            count = msg.count
            print(f"[COUNT] Faces Detected: **{count}**")

            # Обязательно используем asyncio.create_task, чтобы TTS не блокировал обработчик
            if count > 0:
                # Добавляем короткую задержку перед TTS, чтобы предотвратить спам
                async def say_count():
                    await asyncio.sleep(0.5)
                    await tts_speak(f"Welcome to psb academy")

                asyncio.create_task(say_count())

    # 2. Set the handler and start the observer (Установка обработчика и запуск наблюдателя)
    observer.set_handler(count_handler)
    print("[OBSERVE] Setting handler and starting observation.")
    # Запуск наблюдения
    observer.start()

    # 3. Wait for the test duration (Основная программа ожидает здесь)
    await asyncio.sleep(TIMEOUT_DURATION)

    # 4. Stop the observer (Остановка наблюдателя)
    observer.stop()
    print("\n[TEST] Face Count Observer stopped.")
    asyncio.create_task(tts_speak("Face count test complete."))


# --- MAIN PROGRAM EXECUTION ---

async def main():
    # 1. Search for device (Поиск устройства)
    device = await search_device_by_name(ROBOT_SERIAL_SUFFIX)

    if device:
        # 2. Connect (Подключение)
        connected = await test_connect(device)

        if connected:
            print("[MAIN] Successfully connected to the robot. Initiating program...")
            try:
                # 3. Enter program mode (Вход в режим программы)
                await MiniSdk.enter_program()
                print("[MAIN] Entered program mode.")
                await asyncio.sleep(4)  # Даем время на вход

                # 4. Run the test (Запуск теста)
                await run_face_count_test()

            except Exception as e:
                print(f"[ERROR] An error occurred during test: {e}")
            finally:
                # 5. Shutdown (Выход и очистка)
                await shutdown()
        else:
            print("[MAIN] Failed to connect to the robot.")
    else:
        print("[MAIN] Robot device not found. Check the serial suffix and WiFi connection.")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user (Ctrl+C). Exiting.")
        # Убедимся, что робот выйдет из программного режима даже при прерывании
        try:
            asyncio.run(shutdown())
        except Exception:
            pass
        sys.exit(0)