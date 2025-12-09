from math import sin, cos, pi
from pylx16a.lx16a import *
import time

LX16A.initialize("/dev/ttyUSB0")

try:
    servo1 = LX16A(1)
    servo2 = LX16A(2)
    servo3 = LX16A(3)
    servo4 = LX16A(4)
    servo5 = LX16A(5)
    servo6 = LX16A(6)
    servo7 = LX16A(7)
    servo8 = LX16A(8)
    servo1.set_angle_limits(0, 240)
    servo2.set_angle_limits(0, 240)
    servo3.set_angle_limits(0, 240)
    servo4.set_angle_limits(0, 240)
    servo5.set_angle_limits(0, 240)
    servo6.set_angle_limits(0, 240)
    servo7.set_angle_limits(0, 240)
    servo8.set_angle_limits(0, 240)


except ServoTimeoutError as e:
    print(f"Servo {e.id_} is not responding. Exiting...")
    quit()
except Error as e1:
    print(f"Unexpected Error with servo {e.id_}. Exiting...")
    quit()

t = 0

#servo3.set_angle_offset(+10, permanent=True)
#servo4.set_angle_offset(-15, permanent=True)

#servo5.set_angle_offset(-25, permanent=True)
#servo6.set_angle_offset(-20, permanent=True)

#servo7.set_angle_offset(-25, permanent=True)
#servo8.set_angle_offset(-15, permanent=True)


time.sleep(3)
servo1.move(35)
servo2.move(205)

time.sleep(3)
servo3.move(45)
servo4.move(190)

time.sleep(3)
servo5.move(180)
servo6.move(15)

time.sleep(3)
servo7.move(180)
servo8.move(20)
time.sleep(3)
