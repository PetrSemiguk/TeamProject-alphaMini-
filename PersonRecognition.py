import asyncio
import logging
import sys
import cv2
import time
from threading import Thread, Lock
import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice
from mini.apis.base_api import MiniApiResultType
from mini.apis.api_sound import StartPlayTTS

# ================== CONFIGURATION ==================
MiniSdk.set_log_level(logging.INFO)
MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

ROBOT_ID = "412"
SEARCH_TIMEOUT = 20
CAMERA_ID = 6  # Камера ноутбука (единственная доступная)
MOTION_THRESHOLD = 3000  # Чувствительность детекции
REACTION_COOLDOWN = 8  # Секунды между реакциями робота

# Фразы для робота
REACTIONS = [
    "Welcome to PSB academy! I am your robot promoter. Nice to meet you!",
    "Hello there! Welcome to PSB academy. How can I help you today?",
    "Greetings! I'm here to tell you about PSB academy. Welcome!",
    "Hey! I noticed you. Can I tell you about our programs?"
]


# ================== MOTION DETECTOR (LAPTOP CAMERA) ==================
class MotionDetector:
    """Детектор движения через камеру ноутбука"""

    def __init__(self, camera_id=0):
        self.camera_id = camera_id
        self.cap = None
        self.detection_active = False
        self.motion_detected = False
        self.last_detection_time = 0
        self.lock = Lock()
        self.prev_frame = None
        self.frame_count = 0

    def start(self):
        """Запуск камеры и детекции"""
        try:
            print(f"[📷] Opening laptop camera (ID: {self.camera_id})...")
            self.cap = cv2.VideoCapture(self.camera_id)

            if not self.cap.isOpened():
                print("[❌] Failed to open laptop camera!")
                print("[💡] Make sure no other app is using the camera")
                return False

            # Настройка параметров камеры
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)

            # Проверка чтения кадра
            ret, test_frame = self.cap.read()
            if not ret:
                print("[❌] Camera opened but cannot read frames!")
                return False

            print(f"[✓] Camera working! Resolution: {test_frame.shape[1]}x{test_frame.shape[0]}")

            self.detection_active = True

            # Запуск потока детекции
            detection_thread = Thread(target=self._detection_loop, daemon=True)
            detection_thread.start()

            print("[✓] Motion detection started!")
            return True

        except Exception as e:
            print(f"[❌] Error starting camera: {e}")
            return False

    def _detection_loop(self):
        """Основной цикл детекции движения"""
        print("\n" + "=" * 70)
        print("👁️  MOTION DETECTION ACTIVE (USING LAPTOP CAMERA)")
        print("=" * 70)
        print("[ℹ️]  Position laptop so camera sees the area in front of robot")
        print("[ℹ️]  Move your hand or walk in front of camera to test")
        print("[ℹ️]  Robot will speak when motion is detected")
        print("[ℹ️]  Press Ctrl+C to stop")
        print("=" * 70 + "\n")

        while self.detection_active:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue

                self.frame_count += 1

                # Конвертация в grayscale для детекции
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)

                # Инициализация первого кадра
                if self.prev_frame is None:
                    self.prev_frame = gray
                    continue

                # Вычисление разницы между кадрами
                frame_delta = cv2.absdiff(self.prev_frame, gray)
                thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
                thresh = cv2.dilate(thresh, None, iterations=2)

                # Поиск контуров (области движения)
                contours, _ = cv2.findContours(
                    thresh.copy(),
                    cv2.RETR_EXTERNAL,
                    cv2.CHAIN_APPROX_SIMPLE
                )

                # Подсчет площади движения
                motion_area = 0
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > 500:  # Игнорируем мелкие движения (шум)
                        motion_area += area

                # Обновление статуса детекции
                with self.lock:
                    current_time = time.time()

                    if motion_area > MOTION_THRESHOLD:
                        # Движение обнаружено!
                        if not self.motion_detected:
                            print(f"\n🔴 MOTION DETECTED!")
                            print(f"   Area: {int(motion_area)} | Frame: #{self.frame_count}")

                        self.motion_detected = True
                        self.last_detection_time = current_time
                    else:
                        # Движения нет
                        if current_time - self.last_detection_time > 1.5:
                            if self.motion_detected:
                                print("✅ Motion stopped\n")
                            self.motion_detected = False

                # Обновляем предыдущий кадр
                self.prev_frame = gray

                # Небольшая задержка
                time.sleep(0.05)

            except Exception as e:
                print(f"[❌] Detection error: {e}")
                time.sleep(0.5)

    def is_motion_detected(self):
        """Проверка наличия движения"""
        with self.lock:
            return self.motion_detected

    def stop(self):
        """Остановка детекции и освобождение камеры"""
        print("\n[🔧] Stopping camera...")
        self.detection_active = False
        if self.cap:
            self.cap.release()
        print("[✓] Camera released")


# ================== ROBOT PROMOTER ==================
class RobotPromoter:
    """Робот-промоутер с детекцией движения"""

    def __init__(self):
        self.detector = MotionDetector(CAMERA_ID)
        self.last_reaction_time = 0
        self.reaction_index = 0
        self.is_reacting = False
        self.reaction_count = 0

    async def search_device_by_name(self, serial_number_suffix: str, timeout: int):
        """Поиск робота в сети"""
        try:
            print(f"[🔍] Searching for robot with ID: {serial_number_suffix}...")
            result = await MiniSdk.get_device_by_name(serial_number_suffix, timeout)
            print(f"[✓] Found robot: {result}")
            return result
        except Exception as e:
            print(f"[❌] Error searching for device: {e}")
            return None

    async def connect_device(self, device):
        """Подключение к роботу"""
        try:
            print(f"[🔌] Connecting to robot...")
            connected = await MiniSdk.connect(device)
            if connected:
                print(f"[✓] Successfully connected!")
                return True
            else:
                print("[❌] Connection failed")
                return False
        except Exception as e:
            print(f"[❌] Connection error: {e}")
            return False

    async def make_alphamini_speak(self, text: str):
        """Робот говорит"""
        try:
            tts_block = StartPlayTTS(text=text)
            response = await tts_block.execute()

            if response.isSuccess:
                print(f"[🗣️]  Robot: '{text}'")
                return True
            else:
                print(f"[❌] Speech failed (code: {response.resultCode})")
                return False

        except Exception as e:
            print(f"[❌] TTS error: {e}")
            return False

    async def react_to_motion(self):
        """Реакция на обнаруженное движение"""
        if self.is_reacting:
            return

        self.is_reacting = True
        current_time = time.time()

        # Проверка cooldown
        if current_time - self.last_reaction_time < REACTION_COOLDOWN:
            self.is_reacting = False
            return

        self.reaction_count += 1

        print("\n" + "🤖 " * 25)
        print(f"⚡ ROBOT REACTION #{self.reaction_count}")
        print("🤖 " * 25)

        # Выбор фразы (циклически)
        reaction = REACTIONS[self.reaction_index]
        self.reaction_index = (self.reaction_index + 1) % len(REACTIONS)

        # Робот говорит
        success = await self.make_alphamini_speak(reaction)

        if success:
            self.last_reaction_time = current_time
            print(f"[✓] Reaction complete")
            print(f"[⏳] Next reaction available in {REACTION_COOLDOWN} seconds")
        else:
            print("[⚠️]  Reaction failed, but continuing...")

        self.is_reacting = False
        print("🤖 " * 25 + "\n")

    async def detection_mode(self):
        """Режим детекции и реакции"""
        print("\n" + "=" * 70)
        print("🚀 ROBOT PROMOTER - ACTIVE MODE")
        print("=" * 70)
        print("[ℹ️]  Robot is now monitoring for movement")
        print("[ℹ️]  When motion detected → Robot will greet")
        print("[ℹ️]  Position laptop camera to see visitor area")
        print("=" * 70 + "\n")

        while True:
            try:
                # Проверка движения
                if self.detector.is_motion_detected():
                    await self.react_to_motion()

                await asyncio.sleep(0.3)

            except Exception as e:
                print(f"[❌] Loop error: {e}")
                await asyncio.sleep(1)

    async def run(self):
        """Главный запуск"""
        print("\n" + "=" * 70)
        print("🤖 ALPHAMINI ROBOT PROMOTER - INITIALIZATION")
        print("=" * 70 + "\n")

        # Шаг 1: Подключение к роботу
        print("[1/4] Connecting to robot...")
        device = await self.search_device_by_name(ROBOT_ID, SEARCH_TIMEOUT)
        if not device:
            print("[❌] Robot not found!")
            print("[💡] Check: 1) ROBOT_ID is correct, 2) Robot is on same network")
            return

        connected = await self.connect_device(device)
        if not connected:
            print("[❌] Could not connect to robot!")
            return

        # Шаг 2: Вход в программный режим
        print("\n[2/4] Entering programming mode...")
        await MiniSdk.enter_program()
        print("[✓] Programming mode active")
        await asyncio.sleep(1)

        # Шаг 3: Запуск камеры
        print("\n[3/4] Starting laptop camera...")
        if not self.detector.start():
            print("[❌] Camera initialization failed!")
            await MiniSdk.quit_program()
            await MiniSdk.release()
            return

        await asyncio.sleep(2)  # Прогрев камеры

        # Шаг 4: Запуск режима детекции
        print("\n[4/4] Starting detection mode...")
        print("[✓] All systems ready!\n")

        try:
            await self.detection_mode()

        except KeyboardInterrupt:
            print("\n\n[🛑] Stopping robot promoter...")

        finally:
            # Очистка
            print("\n" + "=" * 70)
            print("🔧 SHUTDOWN SEQUENCE")
            print("=" * 70)
            print(f"[📊] Total reactions performed: {self.reaction_count}")

            self.detector.stop()

            await MiniSdk.quit_program()
            await MiniSdk.release()

            print("[✓] Robot disconnected")
            print("[✓] Camera released")
            print("[✓] Shutdown complete")
            print("=" * 70 + "\n")


# ================== MAIN ==================
async def main():
    promoter = RobotPromoter()
    await promoter.run()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🎥 ALPHAMINI ROBOT PROMOTER WITH LAPTOP CAMERA")
    print("=" * 70)
    print("System: AlphaMini EDU + Laptop Webcam")
    print("Method: Motion Detection → Speech Response")
    print("=" * 70 + "\n")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Program interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n[💥] Critical error: {e}")
        sys.exit(1)