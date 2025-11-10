import asyncio
import logging
import sys
import time

import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice

from mini.apis.api_action import MoveRobot, MoveRobotDirection, MoveRobotResponse, StopAllAction

from mini.apis.api_action import PlayAction, PlayActionResponse

from mini.apis.api_sence import GetInfraredDistance
from mini.apis.base_api import MiniApiResultType

from mini.apis.api_sound import StartPlayTTS

from mini.apis.api_observe import ObserveFaceDetect
from mini.pb2.codemao_facedetecttask_pb2 import FaceDetectTaskResponse

MiniSdk.set_log_level(logging.INFO)
MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

ROBOT_ID = "412"
SEARCH_TIMEOUT = 20
FORWARD_STEPS = 5
SQUARE_SIDE_STEPS = 20
TURN_STEPS = 1
SLEEP_TIME = 0.3
OBSTACLE_DISTANCE_MM = 150
OBSTACLE_BYPASS_STEPS = 7
PAUSE_DURATION = 8
SPEECH_DURATION = 3

# Фразы
PHRASE_PROMOTION = "Welcome to PSB academy, I am robot promoter. Nice to meet you!"
PHRASE_STOP = "Im fine, just need to avoid obstacle"
PHRASE_RESUME = "Resuming promoting"
PHRASE_FACE_DETECTED = "Hi, how are you. If u have any questions, scan the QR code"


face_observer: ObserveFaceDetect | None = None
is_robot_paused = False
last_face_action_time = 0
SPEECH_COOLDOWN = 5  #



async def search_device_by_name(serial_number_suffix: str, timeout: int) -> WiFiDevice:
    try:
        result = await MiniSdk.get_device_by_name(serial_number_suffix, timeout)
        print(f"Found device: {result}")
        return result
    except Exception as e:
        print(f"Error searching for device: {e}")
        return None


async def connect_device(device: WiFiDevice):
    try:
        connected = await MiniSdk.connect(device)
        if connected:
            print(f"Successfully connected to {device.name}")
            return True
        else:
            print("Connection failed")
            return False
    except Exception as e:
        print(f"Error connecting: {e}")
        return False


async def speak(text: str):
    tts = StartPlayTTS(text=text)
    asyncio.create_task(tts.execute())
    print(f"Spoke: '{text}' (in background)")




async def move_forward(steps: int):
    block = MoveRobot(step=steps, direction=MoveRobotDirection.FORWARD)
    resultType, response = await block.execute()
    if resultType == MiniApiResultType.Success and isinstance(response, MoveRobotResponse) and response.isSuccess:
        print(f"Walked forward {steps} steps")
        return True
    else:
        print("Move forward failed!")
        return False


async def turn_left(steps: int):
    block = MoveRobot(step=steps, direction=MoveRobotDirection.LEFTWARD)
    resultType, response = await block.execute()
    if resultType == MiniApiResultType.Success and isinstance(response, MoveRobotResponse) and response.isSuccess:
        pass
    else:
        print("Turn left failed!")


async def turn_right(steps: int):
    block = MoveRobot(step=steps, direction=MoveRobotDirection.RIGHTWARD)
    resultType, response = await block.execute()
    if resultType == MiniApiResultType.Success and isinstance(response, MoveRobotResponse) and response.isSuccess:
        pass
    else:
        print("Turn right failed!")


async def turn_left_90():
    for _ in range(3):
        await turn_left(TURN_STEPS)
        await asyncio.sleep(0.1)


async def turn_right_90():
    for _ in range(3):
        await turn_right(TURN_STEPS)
        await asyncio.sleep(0.1)




async def play_action_by_name(action_name: str):
    play_cmd = PlayAction(action_name=action_name)
    result_type, response = await play_cmd.execute()
    if result_type == MiniApiResultType.Success and isinstance(response, PlayActionResponse) and response.isSuccess:
        print(f"Action '{action_name}' executed successfully.")
    else:
        print(f"Failed to execute action '{action_name}', result={result_type}")




async def get_distance() -> float:
    sensor = GetInfraredDistance()
    result_type, response = await sensor.execute()
    if result_type == MiniApiResultType.Success and hasattr(response, "distance"):
        return response.distance
    return 1000.0


async def bypass_obstacle():
    print("Initiating obstacle bypass.")
    await speak(PHRASE_STOP)

    await turn_left_90()
    await move_forward(OBSTACLE_BYPASS_STEPS)

    await turn_right_90()
    await move_forward(OBSTACLE_BYPASS_STEPS * 2)

    await turn_right_90()
    await move_forward(OBSTACLE_BYPASS_STEPS)

    await turn_left_90()

    await speak(PHRASE_RESUME)
    print("Obstacle bypassed. Resuming pattern.")



async def resume_robot():
    global is_robot_paused, last_face_action_time
    if is_robot_paused:
        is_robot_paused = False
        last_face_action_time = time.time()
        print("[RESUME] Face disappeared. Robot resumed movement.")


async def DoFaceAction():
    global is_robot_paused


    await StopAllAction(is_serial=True).execute()
    is_robot_paused = True
    print("[PAUSE] Robot paused due to face detection and waiting for person to leave.")


    await speak(PHRASE_FACE_DETECTED)
    await play_action_by_name("greet_2")

    await asyncio.sleep(SPEECH_DURATION)




def face_detect_handler(msg: FaceDetectTaskResponse):
    global is_robot_paused, last_face_action_time

    if msg.isSuccess:
        count = msg.count
        current_time = time.time()

        if count > 0:

            if not is_robot_paused and (current_time - last_face_action_time) > SPEECH_COOLDOWN:

                asyncio.create_task(DoFaceAction())
            elif is_robot_paused:

                pass

        else:

            if is_robot_paused:

                asyncio.create_task(resume_robot())


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




async def walk_in_circle_pattern(turn_function):
    turn_counter = 0

    direction_name = "LEFTWARD(counterclockwise)" if turn_function == turn_left else "RIGHTWARD(clockwise)"
    print(f"[INFO] Chosen pattern: CIRCLE. Direction: {direction_name}")

    while True:

        if is_robot_paused:
            await asyncio.sleep(0.5)
            continue


        distance = await get_distance()
        if distance <= OBSTACLE_DISTANCE_MM:
            print(f" Obstacle detected at {distance:.1f} mm! Stopping and bypassing.")
            await StopAllAction(is_serial=True).execute()
            await bypass_obstacle()
            continue


        await move_forward(FORWARD_STEPS)
        await asyncio.sleep(SLEEP_TIME)

        #
        await turn_function(TURN_STEPS)
        turn_counter += 1


        if turn_counter % 2 == 0:
            asyncio.create_task(speak(PHRASE_PROMOTION))

        await asyncio.sleep(SLEEP_TIME)




async def walk_in_square_pattern(turn_function):
    side_counter = 0

    turn_90_function = turn_left_90 if turn_function == turn_left else turn_right_90
    direction_name = "LEFTWARD (counterclockwise)" if turn_function == turn_left else "RIGHTWARD (clockwise)"
    print(f"[INFO] Chosen pattern: SQUARE. Direction: {direction_name}")

    while True:

        if is_robot_paused:
            await asyncio.sleep(0.5)
            continue


        steps_done = 0
        while steps_done < SQUARE_SIDE_STEPS:


            distance = await get_distance()
            if distance <= OBSTACLE_DISTANCE_MM:
                print(f" Obstacle detected at {distance:.1f} mm! Stopping and bypassing.")
                await StopAllAction(is_serial=True).execute()
                await bypass_obstacle()
                continue


            await move_forward(FORWARD_STEPS)
            steps_done += FORWARD_STEPS
            await asyncio.sleep(SLEEP_TIME)


        print(f"[→] Side {side_counter % 4 + 1} complete. Turning 90 degrees.")
        await turn_90_function()
        side_counter += 1


        if side_counter % 4 == 0:
            asyncio.create_task(speak(PHRASE_PROMOTION))

        await asyncio.sleep(SLEEP_TIME * 2)




async def main():

    selected_pattern_function = None
    while True:
        print("\n Step 1: Choose the moving algorithm:")
        print("1: CIRCLE moving algorithm")
        print("2: SQUARE walking algorithm")
        pattern_choice = input("Type 1 or 2: ")

        if pattern_choice == '1':
            pattern_name = "Circle"
            break
        elif pattern_choice == '2':
            pattern_name = "Square"
            break
        else:
            print("Incorrect input. Please, type 1 or 2.")


    selected_turn_function = None
    while True:
        print(f"\nStep 2: Choose the direction of the movement {pattern_name} ")
        print("1: Counterclockwise direction (Leftward)")
        print("2: Clockwise direction(Rightward)")
        direction_choice = input("Type 1 or 2: ")

        if direction_choice == '1':
            selected_turn_function = turn_left
            break
        elif direction_choice == '2':
            selected_turn_function = turn_right
            break
        else:
            print("Incorrect input. Please, type 1 or 2.")


    if pattern_name == "Circle":
        selected_pattern_function = walk_in_circle_pattern
    else:
        selected_pattern_function = walk_in_square_pattern


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
        print("Entered programming mode.")
        await asyncio.sleep(1)


        setup_face_observer()


        await speak(PHRASE_PROMOTION)
        await asyncio.sleep(1)


        await selected_pattern_function(selected_turn_function)

    except Exception as e:
        print(f"An unhandled error occurred: {e}")

    finally:

        stop_face_observer()
        await MiniSdk.quit_program()
        await MiniSdk.release()
        print("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
        asyncio.run(MiniSdk.quit_program())
        sys.exit(0)