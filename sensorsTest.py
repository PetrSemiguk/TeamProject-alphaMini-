import asyncio
import logging
import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice

MiniSdk.set_log_level(logging.INFO)
MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

ROBOT_ID = "412"
SEARCH_TIMEOUT = 10
POLL_INTERVAL = 1.0  # как часто читать сенсор (сек)
OBSTACLE_METHOD = "get_distance_front"  # заменить на свой метод, если в SDK другой

class Robot:
    def __init__(self, device: WiFiDevice):
        self.device = device

async def search_device_by_name(serial_number_suffix: str, timeout: int) -> WiFiDevice:
    try:
        result = await MiniSdk.get_device_by_name(serial_number_suffix, timeout)
        print(f"[✓] Found device: {result}")
        return result
    except Exception as e:
        print(f"[X] Error searching for device: {e}")
        return None

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

async def enter_programming_mode():
    try:
        await MiniSdk.enter_program()
        print("[✓] Entered programming mode")
    except Exception as e:
        print(f"[X] Error entering programming mode: {e}")

# === 🦿 Walk Forward ===
async def walk_forward(steps: int = 10):
    try:
        print(f"[→] Walking forward {steps} steps...")
        for _ in range(steps):
            await MiniSdk.run_action("walk_forward")
        print("[✓] Walk complete")
    except Exception as e:
        print(f"[X] Error walking forward: {e}")

# === 🚨 Sensor Test ===
async def sensor_poll_loop():
    """Цикл для теста расстояния до препятствия"""
    print("[info] Starting obstacle distance test. Ctrl+C to stop.")
    while True:
        distance = None
        try:
            # Попытка вызвать метод SDK
            if hasattr(MiniSdk, OBSTACLE_METHOD):
                func = getattr(MiniSdk, OBSTACLE_METHOD)
                if asyncio.iscoroutinefunction(func):
                    distance = await func()
                else:
                    distance = func()
            else:
                print(f"[X] Method {OBSTACLE_METHOD} not found in SDK")
        except Exception as e:
            print(f"[X] Error reading sensor: {e}")

        if distance is not None:
            print(f"[🔍] Distance ahead: {distance} cm")
        else:
            print("[🔍] No distance reading available")

        await asyncio.sleep(POLL_INTERVAL)

async def shutdown_robot():
    print("[✓] Finished robot session")
    try:
        await MiniSdk.quit_program()
    except:
        pass
    try:
        await MiniSdk.release()
    except:
        pass

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

    # Запускаем тест сенсора (только чтение расстояния)
    await sensor_poll_loop()

    await shutdown_robot()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Program interrupted by user.")
