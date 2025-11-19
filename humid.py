from grovepi import *
from grove_rgb_lcd import *
import time, math

온습도 센서 d7
lcd센서 i2c1

1. 적절한 온습도에 대한 함수

def classify_env(temp, hum):
    if 18 <= temp <= 22 and 40 <= hum <= 60:
        return "GOOD"
    if 15 <= temp <= 27 and (30 <= hum < 40 or 60 < hum <= 70):
        return "MODERATE"
    return "BAD"

2. 모드 3번째 선택시 작동할 함수

def show_mode3():
    temp, hum = dht(sensor_port, sensor_type)
    if math.isnan(temp) or math.isnan(hum):
        return
    
    status = classify_env(temp, hum)

    if status == "GOOD":
        setRGB(0, 255, 0)
    elif status == "MODERATE":
        setRGB(255, 255, 0)
    else:
        setRGB(255, 0, 0)

    line1 = f"Status:{status}"
    line2 = f"T:{temp:4.1f}C H:{hum:4.1f}%"
    setText(line1 + "\n" + line2)
    time.sleep(0.5)

