import time
from pylx16a.lx16a import * 

PORT = "/dev/ttyUSB0"       
SERVO_IDS = list(range(1, 9))

#based on servo pos on leg
LED_SEQUENCE = [1, 2, 7, 8, 3, 4, 5, 6]

ANGLE_MIN = 40
ANGLE_MAX = 200

def init_servos():
    LX16A.initialize(PORT)
    servos = {}
    for sid in SERVO_IDS:
        s = LX16A(sid)
        s.set_angle_limits(ANGLE_MIN, ANGLE_MAX)
        servos[sid] = s
    return servos

def query_motor_positions(servos):
    all_ok = True
    for sid, s in servos.items():
        try:
            pos = s.get_physical_angle()
            print(f"servo {sid}: {pos:.1f} deg")
        except ServoError as e:
            print(f"ERROR: servo {sid} did not reply: {e}")
            all_ok = False
    if not all_ok:
        print("comm error with at least one motor")
    else:
        print("all motors responded")
    return all_ok

def enable_disable_test(servos):
    for sid, s in servos.items():
        try:
            #disable first
            s.disable_torque()
            time.sleep(0.05)
            print(f"servo {sid}: disabled")

            #then enable and test
            s.enable_torque()
            time.sleep(0.05)
            loaded = s.is_torque_enabled()
            if loaded != 1:
                print(f"ERROR: servo {sid}: could not enable")
            else:
                print(f"servo {sid}: enabled")
        except ServoError as e:
            print(f"ERROR: servo {sid} during enable/disable: {e}")


def check_voltage(servos, min_mv=5000):
    s = servos[SERVO_IDS[0]]
    try:
        vin_mv = s.get_vin()
        vin_v = vin_mv / 1000.0
        print(f"bus voltage: {vin_v:.2f} V")
        if vin_mv < min_mv:
            print(f"ERROR: voltage too low (< {min_mv/1000:.2f} V).")
            return False
        else:
            print("voltage OK.")
            return True
    except ServoError as e:
        print(f"ERROR: could not read voltage: {e}")
        return False


def flash_led_sequence(servos, flashes=3, on_time=0.15, off_time=0.15):
    print("Flashing LED")

    for sid in LED_SEQUENCE:
        s = servos[sid]
        print(f"flashing LED on servo {sid}")
        for _ in range(flashes):
            s.led_power_on()
            time.sleep(on_time)
            s.led_power_off()
            time.sleep(off_time)

def robot_boot_test():
    servos = init_servos()
    ok_comm = query_motor_positions(servos)
    enable_disable_test(servos)
    ok_v = check_voltage(servos)
    flash_led_sequence(servos)

    if ok_comm and ok_v:
        print("\nboot test PASS")
    else:
        print("\nboot test FAIL")

if __name__ == "__main__":
    robot_boot_test()
