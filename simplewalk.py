import time
from pylx16a.lx16a import LX16A, ServoTimeoutError

# ---------- CONFIG ----------
PORT = "/dev/ttyUSB0"  # e.g. Linux

# Neutral angles for inverted leg config (your calibrated values)
HIP_NEUTRAL = 100
KNEE_NEUTRAL = 150          # degrees

HIP_NEUTRAL_MIRROR = 140
KNEE_NEUTRAL_MIRROR = 85

MIN_ANGLE = 40
MAX_ANGLE = 200

# Small, slow movements (your choice)
HIP_SWING = 10         # hip forward/back offset from neutral
KNEE_LIFT = 6          # how far knee bends to lift the foot
KNEE_DOWN = 4          # how much to "push" into the ground from neutral

STEP_TIME = 0.8        # time for one diagonal pair's full cycle
PHASE_TIME = STEP_TIME / 4.0  # push, lift, swing, down each get 1/4

# Offsets per servo ID (1–8) – your calibrated values
OFFSETS = [0, 0, 10, -15, -30, -15, -25, -15]

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

    # ---------- POSE HELPERS ----------

    def leg_ground(name: str):
        """Leg on ground in neutral-ish support configuration."""
        hip, knee = leg_servos[name]
        if name in ("FR", "BR"):   # your non-mirrored side
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL,
                KNEE_NEUTRAL + KNEE_DOWN
            )
        else:
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL_MIRROR,
                KNEE_NEUTRAL_MIRROR + KNEE_DOWN
            )

    def leg_push(name: str):
        """Leg on ground, hip slightly behind to generate thrust."""
        hip, knee = leg_servos[name]
        if name in ("FR", "BR"):
            # push = hip back
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL - HIP_SWING,
                KNEE_NEUTRAL + KNEE_DOWN
            )
        else:
            # mirrored: push = hip forward
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL_MIRROR + HIP_SWING,
                KNEE_NEUTRAL_MIRROR + KNEE_DOWN
            )

    def leg_lift(name: str):
        """Leg lifting the foot off the ground (knee bent more)."""
        hip, knee = leg_servos[name]
        if name in ("FR", "BR"):
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL - HIP_SWING,      # still back
                KNEE_NEUTRAL - KNEE_LIFT      # lift foot
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
        if name in ("FR", "BR"):
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL + HIP_SWING,      # forward
                KNEE_NEUTRAL - KNEE_LIFT
            )
        else:
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL_MIRROR - HIP_SWING,
                KNEE_NEUTRAL_MIRROR - KNEE_LIFT
            )

    def leg_down(name: str):
        """Leg placing foot back on ground after swing."""
        hip, knee = leg_servos[name]
        if name in ("FR", "BR"):
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL + HIP_SWING,          # still slightly forward
                KNEE_NEUTRAL + KNEE_DOWN          # down to ground
            )
        else:
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL_MIRROR - HIP_SWING,
                KNEE_NEUTRAL_MIRROR + KNEE_DOWN
            )

    # Slightly different poses for support legs to "compensate"

    def support_push(name: str):
        """
        Support leg pushing but not as extreme as swing leg.
        Think of this as a half-push to share load.
        """
        hip, knee = leg_servos[name]
        if name in ("FR", "BR"):
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL - HIP_SWING / 2,
                KNEE_NEUTRAL + KNEE_DOWN
            )
        else:
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL_MIRROR + HIP_SWING / 2,
                KNEE_NEUTRAL_MIRROR + KNEE_DOWN
            )

    def support_forward(name: str):
        """
        Support leg slightly forward – used when swing legs are behind,
        so the body doesn't just sit on one diagonal.
        """
        hip, knee = leg_servos[name]
        if name in ("FR", "BR"):
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL + HIP_SWING / 2,
                KNEE_NEUTRAL + KNEE_DOWN
            )
        else:
            set_leg(
                hip,
                knee,
                HIP_NEUTRAL_MIRROR - HIP_SWING / 2,
                KNEE_NEUTRAL_MIRROR + KNEE_DOWN
            )

    # ---------- STAND NEUTRAL ----------
    def stand_neutral():
        for name in leg_servos.keys():
            leg_ground(name)
        time.sleep(1.0)

    stand_neutral()
    time.sleep(3)
    print("Starting two-leg trot gait with support compensation. Ctrl+C to stop.")

    # Diagonal pairs:
    # Phase A: swing = (FL, BR), support = (FR, BL)
    # Phase B: swing = (FR, BL), support = (FL, BR)

    try:
        while True:
            # =====================================================
            # PHASE A: swing group = (FL, BR), support = (FR, BL)
            # =====================================================
            swing_legs = ["FL", "BR"]
            support_legs = ["FR", "BL"]

            # 1) PUSH: all 4 push, swing pair slightly more
            for leg in support_legs:
                support_push(leg)
            for leg in swing_legs:
                leg_push(leg)
            time.sleep(PHASE_TIME)

            # 2) LIFT: swing legs lift, support legs keep pushing
            for leg in support_legs:
                support_push(leg)
            for leg in swing_legs:
                leg_lift(leg)
            time.sleep(PHASE_TIME)

            # 3) SWING: swing legs swing forward, support legs move toward neutral/forward
            for leg in support_legs:
                support_forward(leg)
            for leg in swing_legs:
                leg_swing(leg)
            time.sleep(PHASE_TIME)

            # 4) DOWN: swing legs land in front, support legs neutral-ish
            for leg in support_legs:
                leg_ground(leg)
            for leg in swing_legs:
                leg_down(leg)
            time.sleep(PHASE_TIME)

            # =====================================================
            # PHASE B: swing group = (FR, BL), support = (FL, BR)
            # =====================================================
            swing_legs = ["FR", "BL"]
            support_legs = ["FL", "BR"]

            # 1) PUSH
            for leg in support_legs:
                support_push(leg)
            for leg in swing_legs:
                leg_push(leg)
            time.sleep(PHASE_TIME)

            # 2) LIFT
            for leg in support_legs:
                support_push(leg)
            for leg in swing_legs:
                leg_lift(leg)
            time.sleep(PHASE_TIME)

            # 3) SWING
            for leg in support_legs:
                support_forward(leg)
            for leg in swing_legs:
                leg_swing(leg)
            time.sleep(PHASE_TIME)

            # 4) DOWN
            for leg in support_legs:
                leg_ground(leg)
            for leg in swing_legs:
                leg_down(leg)
            time.sleep(PHASE_TIME)

    except KeyboardInterrupt:
        print("\nStopping, returning to neutral.")
        stand_neutral()


if __name__ == "__main__":
    main()
