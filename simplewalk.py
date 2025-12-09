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
# NOTE: we interpret FRONT_NEUTRAL_LEAN as signed: FR +=, FL -=
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

# ---------- HEALTH CHECK CONFIG ----------
HEALTH_INTERVAL = 10.0     # seconds between health checks
MAX_TEMP_C = 60.0          # overheat threshold
MIN_VOLT = 5.0             # acceptable bus voltage range (approx)
MAX_VOLT = 7.5
POSITION_TOL = 20.0        # deg away from last command considered "maybe stuck"
MIN_CURRENT = 50.0         # mA, if get_current() is available (tune!)
MAX_CURRENT = 2000.0       # mA

# Stores last commanded angle (AFTER offsets, clamped) per servo ID
EXPECTED_ANGLES = {}       # filled in main()


def clamp_angle(angle: float) -> int:
    """Clamp angle to [MIN_ANGLE, MAX_ANGLE]."""
    return max(MIN_ANGLE, min(MAX_ANGLE, int(angle)))


def set_servo_angle(servo: LX16A, angle: float, t: float):
    """
    Move a single servo with angle clamped to safe range and applying
    per-servo offset, over time t (seconds).
    Also updates EXPECTED_ANGLES for health checking.
    """
    global EXPECTED_ANGLES

    sid = servo.get_id()
    if sid < 1 or sid > len(OFFSETS):
        raise ValueError(f"Servo ID {sid} has no defined offset.")
    offset = OFFSETS[sid - 1]
    angle_cmd = clamp_angle(angle + offset)

    # PyLX-16A expects time in *milliseconds*
    move_time_ms = int(max(t, 0.0) * 1000)
    servo.move(angle_cmd, move_time_ms)

    # record expected final angle
    EXPECTED_ANGLES[sid] = angle_cmd


def set_leg(hip_servo: LX16A, knee_servo: LX16A,
            hip_angle: float, knee_angle: float, t: float):
    """Convenience for setting a leg's hip and knee over time t."""
    set_servo_angle(hip_servo, hip_angle, t)
    set_servo_angle(knee_servo, knee_angle, t)


# ---------- HEALTH CHECK UTILITIES ----------

def _retry_read(func, retries=3, delay=0.05):
    """
    Call func(), retrying on ServoTimeoutError up to 'retries' times.
    Returns (ok, value_or_exception).
    """
    for attempt in range(retries):
        try:
            return True, func()
        except ServoTimeoutError as e:
            print(f"  ServoTimeoutError on attempt {attempt+1}: {e}")
            time.sleep(delay)
    # final failure
    return False, e  # last exception


def flash_led(servo: LX16A, times: int = 2, on_time: float = 0.08, off_time: float = 0.08):
    """Flash servo LED as a heartbeat, if supported by library."""
    if not hasattr(servo, "set_led_power"):
        return
    for _ in range(times):
        try:
            servo.set_led_power(True)
        except TypeError:
            servo.set_led_power(1)
        time.sleep(on_time)
        try:
            servo.set_led_power(False)
        except TypeError:
            servo.set_led_power(0)
        time.sleep(off_time)


def health_check(servos: dict) -> bool:
    """
    Periodic health check:
      - query motor positions, temps, currents (if available)
      - check for stuck / overheating / suspicious current
      - check bus voltage
      - retry on comm errors
      - flash LEDs twice if healthy
    Returns True if OK, False if any serious error.
    """
    print("\n[Health] Running health check...")
    errors = []
    global EXPECTED_ANGLES

    servo_list = list(servos.values())
    if not servo_list:
        print("[Health] No servos?")
        return False

    # ---- Bus voltage (use servo 1 as representative) ----
    if hasattr(servo_list[0], "get_vin"):
        ok, vin_or_exc = _retry_read(servo_list[0].get_vin)
        if ok:
            vin_mv = vin_or_exc  # library usually returns mV
            vin_v = vin_mv / 1000.0
            print(f"[Health] Bus voltage: {vin_v:.2f} V")
            if vin_v < MIN_VOLT or vin_v > MAX_VOLT:
                errors.append(f"Bus voltage out of range: {vin_v:.2f} V")
        else:
            errors.append(f"Cannot read bus voltage: {vin_or_exc}")

    # ---- Per-servo checks ----
    for sid, servo in servos.items():
        print(f"[Health] Checking servo {sid}...")

        # Position / comm
        if hasattr(servo, "get_physical_pos"):
            ok, pos_or_exc = _retry_read(servo.get_physical_pos)
            if ok:
                pos = pos_or_exc
                print(f"  pos = {pos:.1f} deg")
                # rough "stuck" check vs last command
                expected = EXPECTED_ANGLES.get(sid)
                if expected is not None:
                    if abs(pos - expected) > POSITION_TOL:
                        errors.append(
                            f"Servo {sid}: position {pos:.1f} far from expected "
                            f"{expected:.1f} (maybe stuck?)"
                        )
            else:
                errors.append(f"Servo {sid}: comm error (position): {pos_or_exc}")
                continue  # skip temp/current for this servo

        # Temperature
        if hasattr(servo, "get_temp"):
            ok, temp_or_exc = _retry_read(servo.get_temp)
            if ok:
                temp = temp_or_exc
                print(f"  temp = {temp:.1f} C")
                if temp > MAX_TEMP_C:
                    errors.append(f"Servo {sid}: OVERHEAT ({temp:.1f} C)")
            else:
                errors.append(f"Servo {sid}: comm error (temp): {temp_or_exc}")

        # Current (if API provides get_current)
        if hasattr(servo, "get_current"):
            ok, cur_or_exc = _retry_read(servo.get_current)
            if ok:
                current_ma = cur_or_exc
                print(f"  current = {current_ma:.0f} mA")
                if current_ma < MIN_CURRENT:
                    errors.append(f"Servo {sid}: current too LOW ({current_ma:.0f} mA)")
                elif current_ma > MAX_CURRENT:
                    errors.append(f"Servo {sid}: current too HIGH ({current_ma:.0f} mA)")
            else:
                errors.append(f"Servo {sid}: comm error (current): {cur_or_exc}")
        else:
            # silently skip if not supported
            pass

    if errors:
        print("[Health] ❌ Problems detected:")
        for e in errors:
            print("   -", e)
        print("[Health] Aborting gait due to health errors.")
        return False

    # If OK, flash LEDs twice as heartbeat
    print("[Health] ✅ All checks OK, flashing LEDs.")
    for servo in servo_list:
        flash_led(servo, times=2)

    return True


# ---------- MAIN WALKING CODE ----------
def main():
    global EXPECTED_ANGLES

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

    # init EXPECTED_ANGLES
    EXPECTED_ANGLES = {sid: None for sid in servos.keys()}

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
        - FL: subtract FRONT_NEUTRAL_LEAN
        - FR: add FRONT_NEUTRAL_LEAN
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
        """Leg on ground in neutral-ish support configuration."""
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
        """Swing leg 'push' phase (on ground, hip behind)."""
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
        """Swing leg 'lift' phase (knee bends more, hip still behind)."""
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
        """Swing leg 'swing' phase (leg moves forward while lifted)."""
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
        """Swing leg 'down' phase (foot returns to ground, slightly forward)."""
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
        """Support leg slightly forward to balance when swing legs are behind."""
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
            leg_ground(name, 0.4)
        time.sleep(0.5)

    stand_neutral()
    time.sleep(1.0)
    print("Starting two-leg trot gait with health checks. Ctrl+C to stop.")

    last_health = time.time()

    try:
        while True:
            # maybe run health check before each full cycle
            now = time.time()
            if now - last_health >= HEALTH_INTERVAL:
                ok = health_check(servos)
                last_health = now
                if not ok:
                    break  # abort gait

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
        print("\nStopping (KeyboardInterrupt).")

    # on any exit, go back to neutral
    print("Returning to neutral pose.")
    stand_neutral()


if __name__ == "__main__":
    main()
