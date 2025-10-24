import asyncio
import logging
import sys
import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice
from mini.apis.api_sound import StartPlayTTS  # правильный импорт TTS

# === SDK Configuration ===
MiniSdk.set_log_level(logging.INFO)
MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

# === Constants ===
ROBOT_ID = "412"      # последние цифры серийного номера робота
SEARCH_TIMEOUT = 20
SLEEP_DURATION = 2
PHRASE_TO_SPEAK = "Welcome to PSB academy, i am robot promoter. Nice to meet you!"

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
            return True  # возвращаем True, как в твоем первом коде
        else:
            print("[X] Connection failed")
            return False
    except Exception as e:
        print(f"[X] Error connecting: {e}")
        return False

# === Speak ===
async def make_alphamini_speak(text_to_speak: str):
    tts_block = StartPlayTTS(text=text_to_speak)
    response = await tts_block.execute()
    if response.isSuccess:
        print(f"[🗣] AlphaMini successfully spoke: '{text_to_speak}'")
    else:
        print(f"[X] Error making AlphaMini speak: {response.resultCode}")

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

    # 🔊 Произнесение фразы
    await make_alphamini_speak(PHRASE_TO_SPEAK)

    await asyncio.sleep(SLEEP_DURATION)
    await MiniSdk.quit_program()
    await MiniSdk.release()
    print("[✓] Shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Program interrupted by user.")
        sys.exit(0)
