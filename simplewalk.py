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

# Separate swing amounts for front vs rear to smooth gait
HIP_SWING_FRONT = 10    # front legs step a bit larger
HIP_SWING_REAR  = 6     # rear legs push a bit softer

KNEE_LIFT = 6           # how far knee bends to lift the foot
KNEE_DOWN = 4           # how much to "push" into the ground from neutral

STEP_TIME = 0.8         # time for one diagonal pair's full cycle (seconds)
PHASE_TIME = STEP_TIME / 4.0  # push, lift, swing, down each get 1/4

# Lean forward: extra angle on both joints of front legs in neutral/support
# BUT: FL is -, FR is + (per your note)
FRONT_NEUTRAL_LEAN = -5  # magnitude of lean

# Offsets per servo ID (1–8) – your calibrated values
OFFSETS = [0, 0, 10, -15, -30, -15, -25, -15]

# Servo IDs:
# front left leg:  [1 (hip), 2 (knee)]
# front right leg: [3 (hip), 4 (knee)]
# back right leg:  [5 (hip), 6 (knee)]
# back left leg:   [7 (hip), 8 (knee)]

LEGS = {
    "FL": {"hip": 1, "knee": 2},
    "FR": {"hip": 3, "knee": 4},
    "BR": {"hip": 5, "knee": 6},
    "BL": {"hip": 7, "knee": 8},
}


def clamp_angle(angle: float) -> int:
    """Clamp angle to [MIN_ANGLE, MAX_ANGLE]."""
    return max(MIN_ANGLE, min(MAX_ANGLE, int(angle)))


def set_servo_angle(servo: LX16A, angle: float, t: float):
    """
    Move a single servo with angle clamped to safe range and applying
    per-servo offset, over time t (seconds).
    """
    sid = servo.get_id()
    if sid < 1 or sid > len(OFFSETS):
        raise ValueError(f"Servo ID {sid} has no defined offset.")
    offset = OFFSETS[sid - 1]
    angle_cmd = clamp_angle(angle + offset)

    # PyLX-16A expects time in *milliseconds*
    move_time_ms = int(max(t, 0.0) * 1000)
    servo.move(angle_cmd, move_time_ms)


def set_leg(hip_servo: LX16A, knee_servo: LX16A,
            hip_angle: float, knee_angle: float, t: float):
    """Convenience for setting a leg's hip and knee over time t."""
    set_servo_angle(hip_servo, hip_angle, t)
    set_servo_angle(knee_servo, knee_angle, t)


def main():
    # ---------- INITIALIZE ----------
    LX16A.initialize(PORT)

    try:
        servos = {i: LX16A(i) for i in range(1, 9)}
        # Set angle limits for safety
        for s in servos.values():
            s.set_angle_limits(MIN_ANGLE, MAX_ANGLE)
    except ServoTimeoutError as e:
        print(f"Servo {getattr(e, 'id_', '?')} is not responding. Exiting...")
        return

    # Convenience mapping: leg name -> (hip servo, knee servo)
    leg_servos = {
        name: (servos[ids["hip"]], servos[ids["knee"]])
        for name, ids in LEGS.items()
    }

    # ---------- POSE HELPERS (ALL TIMED) ----------

    def is_front(name: str) -> bool:
        return name in ("FL", "FR")

    def is_non_mirror(name: str) -> bool:
        # Your earlier logic treated FR/BR as "non-mirrored"
        return name in ("FR", "BR")

    def apply_front_lean(name: str, hip_angle: float, knee_angle: float):
        """
        Apply forward lean for front legs:
        - FL: -FRONT_NEUTRAL_LEAN
        - FR: +FRONT_NEUTRAL_LEAN
        Rear legs unchanged.
        """
        if name == "FR":
            hip_angle += FRONT_NEUTRAL_LEAN
            knee_angle += FRONT_NEUTRAL_LEAN
        elif name == "FL":
            hip_angle -= FRONT_NEUTRAL_LEAN
            knee_angle -= FRONT_NEUTRAL_LEAN
        return hip_angle, knee_angle

    def leg_ground(name: str, t: float):
        """
        Leg on ground in neutral-ish support configuration.
        For FL/FR, apply asymmetric lean via apply_front_lean().
        """
        hip, knee = leg_servos[name]

        if is_non_mirror(name):
            hip_angle = HIP_NEUTRAL
            knee_angle = KNEE_NEUTRAL + KNEE_DOWN
        else:
            hip_angle = HIP_NEUTRAL_MIRROR
            knee_angle = KNEE_NEUTRAL_MIRROR + KNEE_DOWN

        if is_front(name):
            hip_angle, knee_angle = apply_front_lean(name, hip_angle, knee_angle)

        set_leg(hip, knee, hip_angle, knee_angle, t)

    def leg_push(name: str, t: float):
        """
        Swing leg "push" phase (on ground, hip behind).
        Front uses HIP_SWING_FRONT, rear uses HIP_SWING_REAR.
        """
        hip, knee = leg_servos[name]
        swing = HIP_SWING_FRONT if is_front(name) else HIP_SWING_REAR

        if is_non_mirror(name):
            hip_angle = HIP_NEUTRAL - swing
            knee_angle = KNEE_NEUTRAL + KNEE_DOWN
        else:
            hip_angle = HIP_NEUTRAL_MIRROR + swing
            knee_angle = KNEE_NEUTRAL_MIRROR + KNEE_DOWN

        set_leg(hip, knee, hip_angle, knee_angle, t)

    def leg_lift(name: str, t: float):
        """
        Swing leg "lift" phase (knee bends more, hip still behind).
        """
        hip, knee = leg_servos[name]
        swing = HIP_SWING_FRONT if is_front(name) else HIP_SWING_REAR

        if is_non_mirror(name):
            hip_angle = HIP_NEUTRAL - swing
            knee_angle = KNEE_NEUTRAL - KNEE_LIFT
        else:
            hip_angle = HIP_NEUTRAL_MIRROR + swing
            knee_angle = KNEE_NEUTRAL_MIRROR - KNEE_LIFT

        set_leg(hip, knee, hip_angle, knee_angle, t)

    def leg_swing(name: str, t: float):
        """
        Swing leg "swing" phase (leg moves forward while lifted).
        """
        hip, knee = leg_servos[name]
        swing = HIP_SWING_FRONT if is_front(name) else HIP_SWING_REAR

        if is_non_mirror(name):
            hip_angle = HIP_NEUTRAL + swing
            knee_angle = KNEE_NEUTRAL - KNEE_LIFT
        else:
            hip_angle = HIP_NEUTRAL_MIRROR - swing
            knee_angle = KNEE_NEUTRAL_MIRROR - KNEE_LIFT

        set_leg(hip, knee, hip_angle, knee_angle, t)

    def leg_down(name: str, t: float):
        """
        Swing leg "down" phase (foot returns to ground, slightly forward).
        """
        hip, knee = leg_servos[name]
        swing = HIP_SWING_FRONT if is_front(name) else HIP_SWING_REAR

        if is_non_mirror(name):
            hip_angle = HIP_NEUTRAL + swing
            knee_angle = KNEE_NEUTRAL + KNEE_DOWN
        else:
            hip_angle = HIP_NEUTRAL_MIRROR - swing
            knee_angle = KNEE_NEUTRAL_MIRROR + KNEE_DOWN

        set_leg(hip, knee, hip_angle, knee_angle, t)

    def support_push(name: str, t: float):
        """
        Support leg pushing but not as extreme as swing leg.
        Front uses ~half of HIP_SWING_FRONT,
        Rear uses ~one-third of HIP_SWING_REAR.
        """
        hip, knee = leg_servos[name]
        if is_front(name):
            swing = HIP_SWING_FRONT / 2.0
        else:
            swing = HIP_SWING_REAR / 3.0

        if is_non_mirror(name):
            hip_angle = HIP_NEUTRAL - swing
            knee_angle = KNEE_NEUTRAL + KNEE_DOWN
        else:
            hip_angle = HIP_NEUTRAL_MIRROR + swing
            knee_angle = KNEE_NEUTRAL_MIRROR + KNEE_DOWN

        if is_front(name):
            hip_angle, knee_angle = apply_front_lean(name, hip_angle, knee_angle)

        set_leg(hip, knee, hip_angle, knee_angle, t)

    def support_forward(name: str, t: float):
        """
        Support leg slightly forward – used when swing legs are behind,
        so the body doesn't just sit on one diagonal.
        """
        hip, knee = leg_servos[name]
        if is_front(name):
            swing = HIP_SWING_FRONT / 2.0
        else:
            swing = HIP_SWING_REAR / 3.0

        if is_non_mirror(name):
            hip_angle = HIP_NEUTRAL + swing
            knee_angle = KNEE_NEUTRAL + KNEE_DOWN
        else:
            hip_angle = HIP_NEUTRAL_MIRROR - swing
            knee_angle = KNEE_NEUTRAL_MIRROR + KNEE_DOWN

        if is_front(name):
            hip_angle, knee_angle = apply_front_lean(name, hip_angle, knee_angle)

        set_leg(hip, knee, hip_angle, knee_angle, t)

    # ---------- STAND NEUTRAL ----------
    def stand_neutral():
        for name in leg_servos.keys():
            leg_ground(name, 0.5)
        time.sleep(0.6)

    stand_neutral()
    time.sleep(2.0)
    print("Starting two-leg trot gait with asymmetric forward-lean. Ctrl+C to stop.")

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

            # 1) PUSH
            for leg in support_legs:
                support_push(leg, PHASE_TIME)
            for leg in swing_legs:
                leg_push(leg, PHASE_TIME)
            time.sleep(PHASE_TIME)

            # 2) LIFT
            for leg in support_legs:
                support_push(leg, PHASE_TIME)
            for leg in swing_legs:
                leg_lift(leg, PHASE_TIME)
            time.sleep(PHASE_TIME)

            # 3) SWING
            for leg in support_legs:
                support_forward(leg, PHASE_TIME)
            for leg in swing_legs:
                leg_swing(leg, PHASE_TIME)
            time.sleep(PHASE_TIME)

            # 4) DOWN
            for leg in support_legs:
                leg_ground(leg, PHASE_TIME)
            for leg in swing_legs:
                leg_down(leg, PHASE_TIME)
            time.sleep(PHASE_TIME)

            # =====================================================
            # PHASE B: swing group = (FR, BL), support = (FL, BR)
            # =====================================================
            swing_legs = ["FR", "BL"]
            support_legs = ["FL", "BR"]

            # 1) PUSH
            for leg in support_legs:
                support_push(leg, PHASE_TIME)
            for leg in swing_legs:
                leg_push(leg, PHASE_TIME)
            time.sleep(PHASE_TIME)

            # 2) LIFT
            for leg in support_legs:
                support_push(leg, PHASE_TIME)
            for leg in swing_legs:
                leg_lift(leg, PHASE_TIME)
            time.sleep(PHASE_TIME)

            # 3) SWING
            for leg in support_legs:
                support_forward(leg, PHASE_TIME)
            for leg in swing_legs:
                leg_swing(leg, PHASE_TIME)
            time.sleep(PHASE_TIME)

            # 4) DOWN
            for leg in support_legs:
                leg_ground(leg, PHASE_TIME)
            for leg in swing_legs:
                leg_down(leg, PHASE_TIME)
            time.sleep(PHASE_TIME)

    except KeyboardInterrupt:
        print("\nStopping, returning to neutral.")
        stand_neutral()


if __name__ == "__main__":
    main()
