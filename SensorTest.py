import asyncio
import logging
import sys
from mini.dns.dns_browser import WiFiDevice
import mini.mini_sdk as MiniSdk
from mini.apis.base_api import MiniApiResultType
from mini.apis.api_sence import GetInfraredDistance

# === SDK Configuration & Constants ===
MiniSdk.set_log_level(logging.INFO)
MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)
ROBOT_ID = "412"
SEARCH_TIMEOUT = 20
SLEEP_DURATION = 1


# === Search and Connect ===
async def search_device_by_name(serial_number_suffix: str, timeout: int) -> WiFiDevice:
    try:
        result = await MiniSdk.get_device_by_name(serial_number_suffix, timeout)
        print(f"[✓] Found device: {result}")
        return result
    except Exception:
        print("[X] Error searching for device.")
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
    except Exception:
        print("[X] Error connecting.")
        return False


# ----------------------------------------------------------------------
## Мониторинг датчика расстояния
# ----------------------------------------------------------------------

async def monitor_distance():
    """Непрерывно опрашивает и выводит данные с TOF IR сенсора."""

    print("\n=======================================================")
    print(" [📊] Начинаю мониторинг TOF IR сенсора. Нажмите Ctrl+C для выхода.")
    print("=======================================================")

    # Создаем блок команды
    monitor_command = GetInfraredDistance(is_serial=True)

    while True:
        try:
            # Вызываем .execute() НА БЛОКЕ КОМАНДЫ
            result_type, response = await monitor_command.execute()

            if result_type == MiniApiResultType.Success and response and hasattr(response, 'distance'):
                distance_mm = response.distance

                # *** Визуальный индикатор для проверки ***
                # Предупреждение о близком объекте (например, 200 мм = 20 см)
                if distance_mm < 200:
                    print(f"[🚨 БЛИЗКО] Расстояние: {distance_mm} мм")
                else:
                    print(f"[✅ ОК] Расстояние: {distance_mm} мм")
            else:
                # В случае неудачи или таймаута
                print(f"[⚠️ ОШИБКА] Мониторинг не удался. Результат: {result_type}")

            await asyncio.sleep(0.5)

        except (asyncio.CancelledError, KeyboardInterrupt):
            print("\n[!] Мониторинг прерван пользователем.")
            break
        except Exception as e:
            print(f"[X] КРИТИЧЕСКАЯ ОШИБКА ЧТЕНИЯ СЕНСОРА: {e}")
            break

        # ----------------------------------------------------------------------


## Основная логика
# ----------------------------------------------------------------------

async def main():
    device_info = await search_device_by_name(ROBOT_ID, SEARCH_TIMEOUT)
    if not device_info:
        print("[Error] Робот не найден.")
        return

    is_connected = await connect_device(device_info)
    if not is_connected:
        print("[Error] Не удалось подключиться к роботу.")
        return

    try:
        program_success = await MiniSdk.enter_program()

        if program_success:
            print("[✓] Вход в программный режим успешен.")
            await asyncio.sleep(SLEEP_DURATION)

            # Начинаем мониторинг
            await monitor_distance()
        else:
            print("[X] Ошибка: Не удалось войти в программный режим.")

    except Exception as e:
        print(f"[X] Произошла ошибка в главной функции: {e}")

    finally:
        # Выход из программного режима и освобождение ресурсов
        await MiniSdk.quit_program()
        await MiniSdk.release()
        print("[✓] Завершение работы.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Программа прервана пользователем.")
        sys.exit(0)