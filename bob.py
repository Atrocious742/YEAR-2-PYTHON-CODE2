import math
import time
import threading
import bisect

import pyautogui
import pystray
from PIL import Image, ImageDraw


# ==================================================
# SETTINGS
# ==================================================

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

IDLE_TIME = 5.0
SPEED = 1.0
LOOP_SIZE = 100
FPS = 120

SCREEN_W, SCREEN_H = pyautogui.size()


# ==================================================
# CIRCLE POSITIONS
# Adjust these to fit your wallpaper
# ==================================================

LEFT_CIRCLE_X = SCREEN_W * 0.385
RIGHT_CIRCLE_X = SCREEN_W * 0.610
CIRCLE_CENTER_Y = SCREEN_H * 0.495

BASE_RADIUS_X = SCREEN_W * 0.14
BASE_RADIUS_Y = SCREEN_H * 0.24

# Keep the cursor just outside the circle outlines
OUTER_MARGIN = 1.04


# ==================================================
# STATE
# ==================================================

moving = False
running = True

last_user_position = pyautogui.position()
last_user_movement = time.monotonic()

state_lock = threading.Lock()


# ==================================================
# BUILD A CONTINUOUS OUTER PATH
# ==================================================

def build_outer_path(samples=1000):
    """
    Trace the exposed outer arcs of two overlapping circles.

    Travel order:
      1. Upper-left arc
      2. Upper-right arc
      3. Lower-right arc
      4. Lower-left arc

    All joins share the same coordinates.
    The path never intentionally crosses the middle.
    """

    scale = LOOP_SIZE / 100.0

    rx = BASE_RADIUS_X * scale * OUTER_MARGIN
    ry = BASE_RADIUS_Y * scale * OUTER_MARGIN

    left_x = LEFT_CIRCLE_X
    right_x = RIGHT_CIRCLE_X
    cy = CIRCLE_CENTER_Y

    separation = right_x - left_x
    half_separation = separation / 2

    if separation <= 0:
        raise ValueError(
            "The right circle must be to the right of the left circle."
        )

    if half_separation >= rx:
        raise ValueError(
            "The circles do not overlap. Increase BASE_RADIUS_X "
            "or move the circle centres closer together."
        )

    # Angle of the circle intersections
    alpha = math.acos(half_separation / rx)

    points = []

    def add_arc(cx, start_angle, end_angle, count):
        for i in range(count + 1):
            t = i / count
            angle = start_angle + (end_angle - start_angle) * t

            x = cx + rx * math.cos(angle)
            y = cy + ry * math.sin(angle)

            points.append((x, y))

    # 1. Upper-left arc: leftmost point to upper intersection
    add_arc(
        left_x,
        math.pi,
        2 * math.pi - alpha,
        samples
    )

    # 2. Upper-right arc: upper intersection to rightmost point
    add_arc(
        right_x,
        math.pi + alpha,
        2 * math.pi,
        samples
    )

    # 3. Lower-right arc: rightmost point to lower intersection
    add_arc(
        right_x,
        0,
        math.pi - alpha,
        samples
    )

    # 4. Lower-left arc: lower intersection to leftmost point
    add_arc(
        left_x,
        alpha,
        math.pi,
        samples
    )

    # Remove consecutive duplicate points at the arc joins
    clean_points = []

    for point in points:
        if (
            not clean_points
            or math.dist(point, clean_points[-1]) > 0.001
        ):
            clean_points.append(point)

    return clean_points


# ==================================================
# DISTANCE-BASED MOVEMENT
# ==================================================

def build_distance_table(points):
    """
    Calculate the distance along the path between every
    consecutive point. This avoids uneven movement speeds.
    """

    distances = [0.0]
    total = 0.0

    for i in range(1, len(points)):
        total += math.dist(points[i - 1], points[i])
        distances.append(total)

    # Include the closing segment back to the first point
    total += math.dist(points[-1], points[0])

    return distances, total


def point_at_distance(points, distances, total, distance):
    """
    Find an interpolated position at any distance along
    the closed path, including the final closing segment.
    """

    distance %= total

    index = bisect.bisect_right(distances, distance) - 1
    index = max(0, min(index, len(points) - 1))

    start_distance = distances[index]

    if index + 1 < len(points):
        next_point = points[index + 1]
        segment_length = distances[index + 1] - start_distance
    else:
        next_point = points[0]
        segment_length = total - start_distance

    if segment_length <= 0:
        return points[index]

    fraction = (distance - start_distance) / segment_length

    x1, y1 = points[index]
    x2, y2 = next_point

    return (
        x1 + (x2 - x1) * fraction,
        y1 + (y2 - y1) * fraction
    )


# ==================================================
# MOUSE MOVEMENT THREAD
# ==================================================

def mouse_loop():
    global moving, running
    global last_user_position, last_user_movement

    path = []
    distances = []
    total_length = 0.0

    cached_size = None
    travel_distance = 0.0

    expected_position = None
    movement_grace_until = 0.0

    previous_time = time.perf_counter()

    while running:
        frame_start = time.perf_counter()
        now = time.monotonic()
        current = pyautogui.position()

        # Emergency stop: top-left corner
        if current.x <= 2 and current.y <= 2:
            print("Emergency stop activated.")
            stop_program()
            return

        # ------------------------------
        # WAIT FOR USER INACTIVITY
        # ------------------------------

        if not moving:
            if current != last_user_position:
                last_user_position = current
                last_user_movement = now

            elif now - last_user_movement >= IDLE_TIME:
                moving = True
                travel_distance = 0.0

                expected_position = None
                movement_grace_until = now + 0.3

                cached_size = None
                previous_time = time.perf_counter()

                print("Continuous outer-circle movement started.")

        # ------------------------------
        # CONTINUOUS MOVEMENT
        # ------------------------------

        if moving:

            # Rebuild the path if loop size changes
            if cached_size != LOOP_SIZE or not path:
                path = build_outer_path()
                distances, total_length = build_distance_table(path)

                cached_size = LOOP_SIZE
                travel_distance = 0.0
                previous_time = time.perf_counter()

            # Detect manual mouse movement
            if (
                expected_position is not None
                and now >= movement_grace_until
                and (
                    abs(current.x - expected_position[0]) > 30
                    or abs(current.y - expected_position[1]) > 30
                )
            ):
                moving = False

                last_user_position = current
                last_user_movement = now
                expected_position = None

                print("Manual movement detected.")
                print(f"Waiting {IDLE_TIME:.1f} seconds...")

            else:
                # Actual elapsed time keeps speed consistent
                current_time = time.perf_counter()
                elapsed = min(current_time - previous_time, 0.05)
                previous_time = current_time

                # At 1x, complete one circuit in about 12 seconds
                pixels_per_second = (
                    total_length / 12.0
                ) * SPEED

                travel_distance = (
                    travel_distance + pixels_per_second * elapsed
                ) % total_length

                x, y = point_at_distance(
                    path,
                    distances,
                    total_length,
                    travel_distance
                )

                target_x = round(max(3, min(SCREEN_W - 3, x)))
                target_y = round(max(3, min(SCREEN_H - 3, y)))

                pyautogui.moveTo(
                    target_x,
                    target_y,
                    duration=0,
                    _pause=False
                )

                expected_position = (target_x, target_y)

        # Maintain a steady update rate
        elapsed_frame = time.perf_counter() - frame_start
        time.sleep(max(0, 1.0 / FPS - elapsed_frame))


# ==================================================
# TRAY ICON
# ==================================================

def create_icon():
    image = Image.new("RGB", (64, 64), "black")
    draw = ImageDraw.Draw(image)

    points = []

    for i in range(200):
        angle = i / 200 * math.tau
        points.append((
            32 + 24 * math.cos(angle),
            32 + 16 * math.sin(angle)
        ))

    draw.line(points, fill="white", width=4)
    return image


# ==================================================
# SETTINGS ACTIONS
# ==================================================

def set_idle_time(value):
    global IDLE_TIME
    IDLE_TIME = float(value)
    print(f"Idle time: {IDLE_TIME} seconds")


def set_speed(value):
    global SPEED
    SPEED = float(value)
    print(f"Speed: {SPEED}x")


def set_loop_size(value):
    global LOOP_SIZE
    LOOP_SIZE = int(value)
    print(f"Loop size: {LOOP_SIZE}%")


def toggle_movement(icon, item):
    global moving
    global last_user_position, last_user_movement

    with state_lock:
        moving = not moving

        if moving:
            print("Movement enabled.")
        else:
            last_user_position = pyautogui.position()
            last_user_movement = time.monotonic()
            print("Movement paused.")


def stop_program():
    global running, moving
    running = False
    moving = False


def exit_program(icon, item):
    stop_program()
    icon.stop()


# ==================================================
# MENU CALLBACK HELPERS
# ==================================================

def speed_action(value):
    def action(icon, item):
        set_speed(value)
    return action


def idle_action(value):
    def action(icon, item):
        set_idle_time(value)
    return action


def size_action(value):
    def action(icon, item):
        set_loop_size(value)
    return action


# ==================================================
# SYSTEM TRAY MENU
# ==================================================

def build_menu():

    speed_items = [
        pystray.MenuItem(
            label,
            speed_action(value),
            checked=lambda item, v=value: SPEED == v
        )
        for label, value in [
            ("0.25x", 0.25),
            ("0.5x", 0.5),
            ("1x", 1.0),
            ("1.5x", 1.5),
            ("2x", 2.0),
            ("3x", 3.0),
            ("5x", 5.0)
        ]
    ]

    idle_items = [
        pystray.MenuItem(
            f"{value} seconds",
            idle_action(value),
            checked=lambda item, v=value: IDLE_TIME == v
        )
        for value in [2, 5, 10, 15, 30, 60]
    ]

    size_items = [
        pystray.MenuItem(
            f"{value}%",
            size_action(value),
            checked=lambda item, v=value: LOOP_SIZE == v
        )
        for value in [25, 50, 75, 100, 125, 150, 200]
    ]

    return pystray.Menu(
        pystray.MenuItem(
            "Movement",
            toggle_movement,
            checked=lambda item: moving
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Speed", pystray.Menu(*speed_items)),
        pystray.MenuItem("Idle Time", pystray.Menu(*idle_items)),
        pystray.MenuItem("Loop Size", pystray.Menu(*size_items)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", exit_program)
    )


# ==================================================
# START
# ==================================================

if __name__ == "__main__":
    print("Mouse mover running.")
    print("Look for the icon in your system tray.")
    print(f"Movement begins after {IDLE_TIME} seconds of inactivity.")
    print("Move the mouse to take control.")
    print("Move to the top-left corner for emergency stop.")

    thread = threading.Thread(target=mouse_loop, daemon=True)
    thread.start()

    icon = pystray.Icon(
        "MouseMover",
        create_icon(),
        "Mouse Mover",
        build_menu()
    )

    icon.run()