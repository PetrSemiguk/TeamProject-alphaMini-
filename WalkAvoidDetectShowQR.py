import asyncio
import logging
import sys
import time  # Добавлен импорт time для точного отслеживания времени паузы

import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice
from mini.apis.api_action import MoveRobot, MoveRobotDirection, MoveRobotResponse, StopAllAction
# === ИМПОРТ ДЛЯ РУКИ ===
from mini.apis.api_action import PlayAction, PlayActionResponse
# ========================
from mini.apis.api_sence import GetInfraredDistance
from mini.apis.base_api import MiniApiResultType
from mini.apis.api_sound import StartPlayTTS
from mini.apis.api_observe import ObserveFaceDetect
from mini.pb2.codemao_facedetecttask_pb2 import FaceDetectTaskResponse


MiniSdk.set_log_level(logging.INFO)
MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)


ROBOT_ID = "412"
SEARCH_TIMEOUT = 20
WALK_STEPS = 25
STEP_SIZE = 5
OBSTACLE_DISTANCE_MM = 150
SLEEP_AFTER_PROGRAM = 3
OBSTACLE_BYPASS_STEPS = 7
PAUSE_DURATION = 8


PHRASE_START = "Welcome to PSB academy, I am robot promoter. Nice to meet you!"
PHRASE_STOP = "Im fine, just need to avoid obstacle"
PHRASE_RESUME = "Resuming promoting"
PHRASE_FACE_DETECTED = "Hi, how are you. If u have any questions, scan the QR code"


face_observer: ObserveFaceDetect | None = None
is_robot_paused = False
last_face_action_time = 0
SPEECH_COOLDOWN = 5






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
    asyncio.create_task(tts.execute())
    print(f"[🗣] Spoke: '{text}' (in background)")


async def get_distance() -> float:
    sensor = GetInfraredDistance()
    result_type, response = await sensor.execute()
    if result_type == MiniApiResultType.Success and hasattr(response, "distance"):
        return response.distance
    return 1000.0


async def move_forward(steps: int):
    move_cmd = MoveRobot(step=steps, direction=MoveRobotDirection.FORWARD)
    result_type, response = await move_cmd.execute()
    if result_type == MiniApiResultType.Success and isinstance(response, MoveRobotResponse) and response.isSuccess:
        print(f"Walked forward {steps} steps")
        return True
    print("Move failed")
    return False


async def turn_left():
    move_cmd = MoveRobot(step=1, direction=MoveRobotDirection.LEFTWARD)
    result_type, response = await move_cmd.execute()
    if result_type == MiniApiResultType.Success and isinstance(response, MoveRobotResponse) and response.isSuccess:
        print(f"Turned left 30°")
    await asyncio.sleep(0.2)


async def turn_right():
    move_cmd = MoveRobot(step=1, direction=MoveRobotDirection.RIGHTWARD)
    result_type, response = await move_cmd.execute()
    if result_type == MiniApiResultType.Success and isinstance(response, MoveRobotResponse) and response.isSuccess:
        print(f"Turned right 30°")
    await asyncio.sleep(0.2)




async def play_action_by_name(action_name: str):

    play_cmd = PlayAction(action_name=action_name)
    result_type, response = await play_cmd.execute()
    if result_type == MiniApiResultType.Success and isinstance(response, PlayActionResponse) and response.isSuccess:
        print(f"Action '{action_name}' executed successfully.")
    else:
        print(f"Failed to execute action '{action_name}', result={result_type}")


async def DoFaceAction():

    global is_robot_paused, last_face_action_time


    await StopAllAction(is_serial=True).execute()
    is_robot_paused = True


    # 2. Произносим фразу
    await speak(PHRASE_FACE_DETECTED)


    await play_action_by_name("greet_2")


    await asyncio.sleep(PAUSE_DURATION)


    is_robot_paused = False
    last_face_action_time = time.time()





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




async def turn_left_90():
    for _ in range(3):
        await turn_left()
        await asyncio.sleep(0.1)


async def turn_right_90():
    for _ in range(3):
        await turn_right()
        await asyncio.sleep(0.1)


async def bypass_obstacle():

    await speak(PHRASE_STOP)

    await turn_left_90()
    await move_forward(OBSTACLE_BYPASS_STEPS)

    await turn_right_90()
    await move_forward(OBSTACLE_BYPASS_STEPS)

    await move_forward(OBSTACLE_BYPASS_STEPS)

    await turn_right_90()
    await move_forward(OBSTACLE_BYPASS_STEPS)

    await turn_left_90()
    await speak(PHRASE_RESUME)




async def walk_with_obstacle_check():

    while True:
        steps_done = 0
        while steps_done < WALK_STEPS:

            if is_robot_paused:
                await asyncio.sleep(0.5)
                continue


            distance = await get_distance()
            if distance <= OBSTACLE_DISTANCE_MM:
                print(f" Obstacle detected at {distance:.1f} mm!")
                await StopAllAction(is_serial=True).execute()
                await bypass_obstacle()
                continue


            moved = await move_forward(STEP_SIZE)
            if moved:
                steps_done += STEP_SIZE

            await asyncio.sleep(0.1)


        if not is_robot_paused:
            for _ in range(3):
                await turn_left()
                await asyncio.sleep(0.2)


            await speak(PHRASE_START)




async def main():
    device = await search_device(ROBOT_ID, SEARCH_TIMEOUT)
    if not device:
        print("Robot not found")
        return

    if not await connect_device(device):
        print("Connection failed")
        return

    try:
        await MiniSdk.enter_program()
        print("Entered program mode")
        await asyncio.sleep(SLEEP_AFTER_PROGRAM)


        setup_face_observer()


        await speak(PHRASE_START)
        await walk_with_obstacle_check()

    except Exception as e:
        print(f"An unhandled error occurred: {e}")
    finally:

        stop_face_observer()

        print("\n[SHUTDOWN] Exiting programming mode and releasing SDK resources...")
        await MiniSdk.quit_program()
        await MiniSdk.release()
        print("[SHUTDOWN] Complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Program interrupted by user (Ctrl+C)")
        asyncio.run(MiniSdk.quit_program())
        sys.exit(0)