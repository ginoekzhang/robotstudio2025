import time
from pylx16a.lx16a import * 

PORT = "/dev/ttyUSB0"
SERVO_IDS = list(range(1, 9))

ANGLE_MIN = 40
ANGLE_MAX = 200
HOME_ANGLE = 120          
MOVE_TIME_MS = 1500       
POS_TOLERANCE_DEG = 5.0   

MAX_SAFE_TEMP_C = 70      
MIN_SAFE_VIN_MV = 5000    

def init_servos():
    LX16A.initialize(PORT)
    servos = {}
    for sid in SERVO_IDS:
        s = LX16A(sid)
        s.set_angle_limits(ANGLE_MIN, ANGLE_MAX)
        servos[sid] = s
    return servos

def log_current_positions(servos):
    print("current motor positions")
    for sid, s in servos.items():
        try:
            pos = s.get_physical_angle()
            print(f"servo {sid}: {pos:.1f} deg")
        except ServoError as e:
            print(f"ERROR: servo {sid} did not reply: {e}")

def check_temp_and_voltage(servos):
    print("temp check")
    ok = True
    for sid, s in servos.items():
        try:
            temp = s.get_temp()
            print(f"servo {sid}: {temp} C")
            if temp > MAX_SAFE_TEMP_C:
                print(f"ERROR: servo {sid} over temperature")
                ok = False
        except ServoError as e:
            print(f"ERROR: servo {sid} tempRead failed: {e}")
            ok = False

    print("voltage check")
    try:
        vin_mv = servos[SERVO_IDS[0]].get_vin()
        vin_v = vin_mv / 1000.0
        print(f"bus voltage: {vin_v:.2f} V")
        if vin_mv < MIN_SAFE_VIN_MV:
            print(f"ERROR: voltage too low (< {MIN_SAFE_VIN_MV/1000:.2f} V)")
            ok = False
    except ServoError as e:
        print(f"ERROR: could not read voltage: {e}")
        ok = False
    return ok


def move_to_home(servos):
    print("moving to home pos")
    for sid, s in servos.items():
        try:
            s.move(HOME_ANGLE, MOVE_TIME_MS)
        except ServoError as e:
            print(f"ERROR: servo {sid} moveTimeWrite failed: {e}")
    #wait
    time.sleep(MOVE_TIME_MS / 1000.0 + 0.5)


def verify_home(servos):
    print("verify home pos")
    all_ok = True
    for sid, s in servos.items():
        try:
            pos = s.get_physical_angle()
            error = abs(pos - HOME_ANGLE)
            print(f"servo {sid}: {pos:.1f} deg (error {error:.1f})")
            if error > POS_TOLERANCE_DEG:
                print(f"ERROR: servo {sid} did not reach home position")
                all_ok = False
        except ServoError as e:
            print(f"ERROR: servo {sid} during verify: {e}")
            all_ok = False
    if all_ok:
        print("robot reached home state")
    else:
        print("ERROR: at least one joint is not at home")
    return all_ok


def homing_initialization():
    servos = init_servos()
    log_current_positions(servos)
    if not check_temp_and_voltage(servos):
        print("temp/voltage problem")
        return False
    move_to_home(servos)
    ok = verify_home(servos)
    return ok

if __name__ == "__main__":
    success = homing_initialization()
    print("\nDone, success =", success)
