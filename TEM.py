
#온습도 읽고 lcd에 표시하는 함수
def show_env(m):
    try:
        temp, hum = grovepi.dht(DHT_PIN, DHT_TYPE)
        if math.isnan(temp) or math.isnan(hum):
            temp = hum = 0
    except:
        temp = hum = 0

    if 18 <= temp <= 22 and 40 <= hum <= 60:
        status = "GOOD"
    elif 15 <= temp <= 27 and 30 <= hum <= 70:
        status = "MODERATE"
    else:
        status = "BAD"

    setRGB(100, 255, 100)
    setText(f"{temp:.1f}°C {hum:.1f}%\nStatus: {status}")



# 마지막에 show_env 추가하기
menu_funcs = [show_mode, show_exercise, show_rest, show_sets, show_env]

