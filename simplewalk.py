import time
from pylx16a.lx16a import LX16A, ServoTimeoutError

# ---------- CONFIG ----------
PORT = "/dev/ttyUSB0"  # e.g. Linux
# PORT = "COM3"       # e.g. Windows

NEUTRAL = 120          # degrees
MIN_ANGLE = 40
MAX_ANGLE = 200

HIP_SWING = 25         # how far hip moves forward/back from neutral
KNEE_LIFT = 20         # how far knee bends to lift the foot
KNEE_DOWN = 10         # how much to "push" into the ground from neutral

STEP_TIME = 0.40       # time per main gait phase (seconds)

# Servo IDs:
# front left leg: [1 (hip), 2 (knee)]
# front right leg: [3 (hip), 4 (knee)]
# back right leg: [5 (hip), 6 (knee)]
# back left leg: [7 (hip), 8 (knee)]

LEGS = {
    "FL": {"hip": 1, "knee": 2},
    "FR": {"hip": 3, "knee": 4},
    "BR": {"hip": 5, "knee": 6},
    "BL": {"hip": 7, "knee": 8},
}


def clamp_angle(angle: float) -> int:
    """Clamp angle to [MIN_ANGLE, MAX_ANGLE]."""
    return max(MIN_ANGLE, min(MAX_ANGLE, int(angle)))


def set_servo_angle(servo: LX16A, angle: float):
    """Move a single servo with angle clamped to safe range."""
    angle = clamp_angle(angle)
    servo.move(angle)


def set_leg(hip_servo: LX16A, knee_servo: LX16A,
            hip_angle: float, knee_angle: float):
    """Convenience for setting a leg's hip and knee."""
    set_servo_angle(hip_servo, hip_angle)
    set_servo_angle(knee_servo, knee_angle)


def main():
    # ---------- INITIALIZE ----------
    LX16A.initialize(PORT)

    try:
        servos = {i: LX16A(i) for i in range(1, 9)}
        # Set angle limits for safety
        for s in servos.values():
            s.set_angle_limits(MIN_ANGLE, MAX_ANGLE)
    except ServoTimeoutError as e:
        print(f"Servo {e.id_} is not responding. Exiting...")
        return

    # Convenience mapping: leg name -> (hip servo, knee servo)
    leg_servos = {
        name: (servos[ids["hip"]], servos[ids["knee"]])
        for name, ids in LEGS.items()
    }

    # ---------- HELPER: STAND NEUTRAL ----------
    def stand_neutral():
        for hip, knee in leg_servos.values():
            set_leg(hip, knee, NEUTRAL, NEUTRAL)
        time.sleep(1.0)

    stand_neutral()

    print("Starting simple trot gait. Ctrl+C to stop.")

    # ---------- GAIT LOOP ----------
    try:
        while True:
            # ---- PHASE 1 ----
            # Swing: FL & BR forward, lifted
            # Support: FR & BL on ground, slightly back
            # NOTE: You may need to flip +/- HIP_SWING depending on your geometry.

            # Front-left (swing)
            set_leg(
                *leg_servos["FL"],
                hip_angle=NEUTRAL - HIP_SWING,          # forward
                knee_angle=NEUTRAL - KNEE_LIFT          # lift foot
            )
            # Back-right (swing)
            set_leg(
                *leg_servos["BR"],
                hip_angle=NEUTRAL - HIP_SWING,          # forward
                knee_angle=NEUTRAL - KNEE_LIFT
            )

            # Front-right (support)
            set_leg(
                *leg_servos["FR"],
                hip_angle=NEUTRAL + HIP_SWING,          # backward
                knee_angle=NEUTRAL + KNEE_DOWN          # pushing into ground
            )
            # Back-left (support)
            set_leg(
                *leg_servos["BL"],
                hip_angle=NEUTRAL + HIP_SWING,
                knee_angle=NEUTRAL + KNEE_DOWN
            )

            time.sleep(STEP_TIME)

            # Optional: place swing legs down before switching phase
            set_leg(
                *leg_servos["FL"],
                hip_angle=NEUTRAL - HIP_SWING,
                knee_angle=NEUTRAL + KNEE_DOWN   # down to ground
            )
            set_leg(
                *leg_servos["BR"],
                hip_angle=NEUTRAL - HIP_SWING,
                knee_angle=NEUTRAL + KNEE_DOWN
            )
            time.sleep(STEP_TIME * 0.5)

            # ---- PHASE 2 ----
            # Swing: FR & BL forward, lifted
            # Support: FL & BR on ground, slightly back

            # Front-right (swing)
            set_leg(
                *leg_servos["FR"],
                hip_angle=NEUTRAL - HIP_SWING,          # forward
                knee_angle=NEUTRAL - KNEE_LIFT
            )
            # Back-left (swing)
            set_leg(
                *leg_servos["BL"],
                hip_angle=NEUTRAL - HIP_SWING,
                knee_angle=NEUTRAL - KNEE_LIFT
            )

            # Front-left (support)
            set_leg(
                *leg_servos["FL"],
                hip_angle=NEUTRAL + HIP_SWING,
                knee_angle=NEUTRAL + KNEE_DOWN
            )
            # Back-right (support)
            set_leg(
                *leg_servos["BR"],
                hip_angle=NEUTRAL + HIP_SWING,
                knee_angle=NEUTRAL + KNEE_DOWN
            )

            time.sleep(STEP_TIME)

            # Place swing legs down
            set_leg(
                *leg_servos["FR"],
                hip_angle=NEUTRAL - HIP_SWING,
                knee_angle=NEUTRAL + KNEE_DOWN
            )
            set_leg(
                *leg_servos["BL"],
                hip_angle=NEUTRAL - HIP_SWING,
                knee_angle=NEUTRAL + KNEE_DOWN
            )

            time.sleep(STEP_TIME * 0.5)

    except KeyboardInterrupt:
        print("\nStopping, returning to neutral.")
        stand_neutral()


if __name__ == "__main__":
    main()
