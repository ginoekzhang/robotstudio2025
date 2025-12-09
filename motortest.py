from math import sin, cos, pi
from pylx16a.lx16a import *
import time

LX16A.initialize("/dev/ttyUSB0")

try:
    servo1 = LX16A(1)
    servo2 = LX16A(2)
    servo1.set_angle_limits(0, 240)
    servo2.set_angle_limits(0, 240)
except ServoTimeoutError as e:
    print(f"Servo {e.id_} is not responding. Exiting...")
    quit()

t = 0

time.sleep(3)
servo1.move(0)
time.sleep(3)
servo1.move(240)
time.sleep(3)
servo1.move(120)
time.sleep(3)

#while True:
#    servo1.move(0)
#    time.sleep(3)
#    servo1.move(240)
#    time.sleep(3)
#    servo1.move(120)
#    time.sleep(3)
    #servo2.move(205)

#    time.sleep(3)
    #t += 0.1
