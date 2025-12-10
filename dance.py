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

t = 1

#OFFSETS = [0, 0, 10, -15, -30, -15, -25, -15]

time.sleep(1)
servo1.move(140)
servo2.move(85)

servo3.move(110)
servo4.move(135)

servo5.move(70)
servo6.move(135)

servo7.move(115)
servo8.move(70)
time.sleep(3)

while True:
  servo5.move(110)
  servo6.move(150)

  servo7.move(75)
  servo8.move(55)
  time.sleep(1)

  
