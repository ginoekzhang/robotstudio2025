import time
from pylx16a.lx16a import LX16A, ServoTimeoutError

# ---------- CONFIG ----------
PORT = "/dev/ttyUSB0"  # e.g. Linux

# Neutral angles for inverted leg config
HIP_NEUTRAL = 100
KNEE_NEUTRAL = 160          # degrees

HIP_NEUTRAL_MIRROR = 140
KNEE_NEUTRAL_MIRROR = 80

MIN_ANGLE = 40
MAX_ANGLE = 200

# FL and BR are +forward, FR and BL are -forward
HIP_SWING = 25         # hip forward/back offset from neutral
KNEE_LIFT = 20         # how far knee bends to lift the foot
KNEE_DOWN = 10         # how much to "push" into the ground from neutral

STEP_TIME = 0.40       # time for one leg-group step (seconds)
PHASE_TIME = STEP_TIME / 4.0  # push, lift, swing, down each get 1/4

# Offsets per servo ID (1–8)
OFFSETS = [0, 0, 10, 15, -25, -20, -25, -15]

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
    """
    Move a single servo with angle clamped to safe range and applying
    per-servo offset.
    """
    sid = servo.get_id()
    if sid < 1 or sid > len(OFFSETS):
        raise ValueError(f"Servo ID {sid} has no defined offset.")
    offset = OFFSETS[sid - 1]
    angle_cmd = clamp_angle(angle + offset)
    servo.move(angle_cmd)


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
        print(f"Servo {e.get_id()} is not responding. Exiting...")
        return

    # Convenience mapping: leg name -> (hip servo, knee servo)
    leg_servos = {
        name: (servos[ids["hip"]], servos[ids["knee"]])
        for name, ids in LEGS.items()
    }

    # ---------- HELPER: POSE HELPERS FOR EACH LEG ----------

    def leg_ground(name: str):
        """Leg on ground in neutral-ish support configuration."""
        hip, knee = leg_servos[name]
        if name in ("FL", "BR"):
            # non-mirrored side
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL,                  # neutral hip
                KNEE_NEUTRAL + KNEE_DOWN      # slightly 'pushing' into ground
            )
        else:
            # mirrored side
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL_MIRROR,
                KNEE_NEUTRAL_MIRROR + KNEE_DOWN
            )

    def leg_push(name: str):
        """Leg on ground, hip slightly behind to generate thrust."""
        hip, knee = leg_servos[name]
        if name in ("FL", "BR"):
            # +forward side: push = hip back
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL - HIP_SWING,
                KNEE_NEUTRAL + KNEE_DOWN
            )
        else:
            # mirrored: push = hip forward (since their forward is opposite)
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL_MIRROR + HIP_SWING,
                KNEE_NEUTRAL_MIRROR + KNEE_DOWN
            )

    def leg_lift(name: str):
        """Leg lifting the foot off the ground (knee bent more)."""
        hip, knee = leg_servos[name]
        if name in ("FL", "BR"):
            # keep hip back during lift
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL - HIP_SWING,
                KNEE_NEUTRAL - KNEE_LIFT
            )
        else:
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL_MIRROR + HIP_SWING,
                KNEE_NEUTRAL_MIRROR - KNEE_LIFT
            )

    def leg_swing(name: str):
        """Leg swung forward while lifted."""
        hip, knee = leg_servos[name]
        if name in ("FL", "BR"):
            # +forward side: hip forward from neutral
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL + HIP_SWING,
                KNEE_NEUTRAL - KNEE_LIFT
            )
        else:
            # mirrored: forward = neutral - HIP_SWING
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL_MIRROR - HIP_SWING,
                KNEE_NEUTRAL_MIRROR - KNEE_LIFT
            )

    def leg_down(name: str):
        """Leg placing foot back on ground after swing."""
        hip, knee = leg_servos[name]
        if name in ("FL", "BR"):
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL + HIP_SWING,          # stays slightly forward
                KNEE_NEUTRAL + KNEE_DOWN          # down to ground
            )
        else:
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL_MIRROR - HIP_SWING,
                KNEE_NEUTRAL_MIRROR + KNEE_DOWN
            )

    # ---------- HELPER: STAND NEUTRAL ----------
    def stand_neutral():
        for name in leg_servos.keys():
            leg_ground(name)
        time.sleep(1.0)

    stand_neutral()
    time.sleep(5)
    print("Starting push → lift → swing → down trot gait. Ctrl+C to stop.")

    # ---------- GAIT LOOP ----------
    try:
        while True:
            # =====================================================
            # PHASE A: swing group = (FL, BR), support = (FR, BL)
            # =====================================================

            # 1) PUSH: everyone on ground, hips pushing backward
            leg_push("FL")
            leg_push("BR")
            leg_push("FR")
            leg_push("BL")
            time.sleep(PHASE_TIME)

            # 2) LIFT: FL & BR lift, FR & BL stay pushing
            leg_lift("FL")
            leg_lift("BR")
            leg_push("FR")
            leg_push("BL")
            time.sleep(PHASE_TIME)

            # 3) SWING: FL & BR swing forward while lifted
            leg_swing("FL")
            leg_swing("BR")
            leg_push("FR")
            leg_push("BL")
            time.sleep(PHASE_TIME)

            # 4) DOWN: FL & BR touch down in front, FR & BL still pushing
            leg_down("FL")
            leg_down("BR")
            leg_push("FR")
            leg_push("BL")
            time.sleep(PHASE_TIME)

            # Optionally bring FR/BL back to a more neutral support
            leg_ground("FR")
            leg_ground("BL")
            time.sleep(PHASE_TIME * 0.5)

            # =====================================================
            # PHASE B: swing group = (FR, BL), support = (FL, BR)
            # =====================================================

            # 1) PUSH: everyone on ground, hips pushing backward
            leg_push("FL")
            leg_push("BR")
            leg_push("FR")
            leg_push("BL")
            time.sleep(PHASE_TIME)

            # 2) LIFT: FR & BL lift, FL & BR stay pushing
            leg_push("FL")
            leg_push("BR")
            leg_lift("FR")
            leg_lift("BL")
            time.sleep(PHASE_TIME)

            # 3) SWING: FR & BL swing forward while lifted
            leg_push("FL")
            leg_push("BR")
            leg_swing("FR")
            leg_swing("BL")
            time.sleep(PHASE_TIME)

            # 4) DOWN: FR & BL touch down in front, FL & BR still pushing
            leg_push("FL")
            leg_push("BR")
            leg_down("FR")
            leg_down("BL")
            time.sleep(PHASE_TIME)

            # Optionally bring FL/BR back to more neutral support
            leg_ground("FL")
            leg_ground("BR")
            time.sleep(PHASE_TIME * 0.5)

    except KeyboardInterrupt:
        print("\nStopping, returning to neutral.")
        stand_neutral()


if __name__ == "__main__":
    main()
