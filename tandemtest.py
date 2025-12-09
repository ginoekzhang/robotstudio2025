from math import sin, cos, pi
from pylx16a.lx16a import *
import time

LX16A.initialize("/dev/ttyUSB0")

try:
    servo1 = LX16A(1)
    servo2 = LX16A(2)
    servo3 = LX16A(3)
    servo4 = LX16A(4)
    servo1.set_angle_limits(0, 240)
    servo2.set_angle_limits(0, 240)
    servo3.set_angle_limits(0, 240)
    servo4.set_angle_limits(0, 240)
except ServoTimeoutError as e:
    print(f"Servo {e.id_} is not responding. Exiting...")
    quit()
except Error as e1:
    print(f"Unexpected Error with servo {e.id_}. Exiting...")
    quit()

t = 0

time.sleep(3)
servo1.move(100)
servo2.move(180)
servo3.move(140)
servo4.move(60)
time.sleep(3)

while True:
    servo2.move(60)
    servo1.move(140)
    servo4.move(180)
    servo3.move(100)
    
    time.sleep(1)
    servo1.move(100)
    servo2.move(180)
    servo3.move(140)
    servo4.move(60)
    time.sleep(1)


#    time.sleep(3)
    #t += 0.1
