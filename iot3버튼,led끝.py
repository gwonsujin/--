import RPi.GPIO as GPIO
import time
from grovepi import *
from grove_rgb_lcd import *

# 버튼 핀 번호 설정
btn = [22,23,24,25]

# 모션감지/부저 핀 번호 설정
PIR_D = 8        
BUZZER_D = 3

#일단 스피커 사용 안함
BGM_PATH = "/home/pi/iot/music.mp3"
BGM_VOLUME = 0.4

#초기 설정
menu = [
    [1], #모드
    [30], #운동시간
    [10], #휴식시간
    [1] #세트수
]

#하드웨어 초기화
def init_hardware():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    # GPIO 버튼 초기화
    for pin in btn:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    
    # GrovePi PIR, buzzer 초기화
    pinMode(PIR_D, "INPUT")
    pinMode(BUZZER_D, "OUTPUT")


    
# 부저 함수
def beep_ms(ms: int):
    digitalWrite(BUZZER_D, 1)
    time.sleep(ms / 1000.0)
    digitalWrite(BUZZER_D, 0)

def short_beep(times=1, dur_ms=120, gap_ms=80):
    for _ in range(times):
        beep_ms(dur_ms)
        time.sleep(gap_ms / 1000.0)

def long_beep(dur_ms=400):
    beep_ms(dur_ms)

ok_sound = short_beep
cancel_sound = lambda: short_beep(times=2, dur_ms=80)
alert_sound = long_beep
start_sound = lambda: short_beep(times=2)

def show_mode(m):
    """모드 선택 화면"""
    if m[0][0] == 1:
        setRGB(0, 255, 0)
        setText("Mode 1\nmove mode")
    elif m[0][0] == 2:
        setRGB(0, 0, 255)
        setText("Mode 2\nstay mode")
    else:
        setRGB(255, 255, 255)
        setText("Unknown Mode")

def show_exercise(m):
    """운동 시간 설정"""
    setRGB(255, 255, 255)
    setText(f"Exercise Time\n{m[1][0]} s")

def show_rest(m):
    """휴식 시간 설정"""
    setRGB(255, 255, 255)
    setText(f"Rest Time\n{m[2][0]} s")

def show_sets(m):
    """세트 수 설정"""
    setRGB(255, 255, 255)
    setText(f"Sets\n{m[3][0]} times")

def run_exercise_session(m):
    exercise_time = m[1][0]
    rest_time = m[2][0]
    total_sets = m[3][0]

    for set_num in range(1, total_sets + 1):
        # === 준비 카운트다운 ===
        setRGB(0, 100, 255)
        for i in range(3, 0, -1):
            setText(f"Set {set_num}/{total_sets}\nReady in {i}s")
            short_beep()
            time.sleep(1)

        # === 운동 타이머 ===
        setRGB(0, 255, 0)
        left = exercise_time
        while left > 0:
            motion = read_pir()
            motion_text = "Motion!" if motion else "No Motion"
            bar_len = int((exercise_time - left) / exercise_time * 16)
            bar = "■" * bar_len + " " * (16 - bar_len)
            setText(f"Set{set_num}/{total_sets} {left}s\n{motion_text}")
            time.sleep(1)
            left -= 1

        # === 세트 종료 ===
        long_beep()
        setRGB(0, 0, 255)
        setText(f"Set {set_num} Done!\nRest {rest_time}s")
        time.sleep(rest_time)

    # === 전체 완료 ===
    setRGB(0, 255, 0)
    setText("All Sets Done!\nGood job!")
    short_beep(times=3)
    time.sleep(2)


def start_exercise(m):
    """운동 시작 화면"""
    short_beep(times=2) #운동 시작 부저 두번
    setRGB(0, 255, 255)
    print("\n=== 운동 시작 ===")
    print(f"Mode: {m[0][0]}, 운동: {m[1][0]}s, 휴식: {m[2][0]}s, 세트: {m[3][0]}")
    setText(f"start exercise")
    time.sleep(3)
    setText(f"end exercise")
    #운동 함수 시작
    
    run_exercise_session(m)
    
    long_beep() #운동 종료 부저 길게
    setRGB(0, 255, 0)
    setText("Back to Menu")
    time.sleep(0.5)
    return 0  # 운동 후 다시 메뉴로 돌아감 (step = 0) 이거 되는지 확인해야됨.

menu_funcs = [show_mode, show_exercise, show_rest, show_sets]
step = 0


setRGB(0,255,0)
print("mode start! (Ctrl+C로 종료)")
init_hardware()
menu_funcs[step](menu)

try:
    while True:
        if GPIO.input(btn[0]) == GPIO.HIGH:  # 버튼 눌림
            short_beep(times=1) # 버튼 눌리면 부저 한번
            match step:
                case 0:
                    print(f"Button {btn[0]} pressed!")
            
                    menu[0][0] =1 if menu[0][0] == 2 else 2
                    print("step0")

                case 1:
                    menu[1][0] += 10
                    print("step1")
                case 2:
                    menu[2][0] += 5
                    print("step2")
                case 3:
                    menu[3][0] += 1
                    print("step3")
            
            menu_funcs[step](menu)
            time.sleep(0.1)  # 중복 입력 방지용 딜레이
            
        elif GPIO.input(btn[1]) == GPIO.HIGH:  # 버튼 눌림
            short_beep(times=1) # 버튼 눌리면 부저 한번
            print(f"Button {btn[1]} pressed!")
            # step = (step + 1) % len(menu_funcs)
            step = step + 1
            if step >= len(menu_funcs):  # 3을 넘으면 운동 시작
                step = start_exercise(menu)
            else:
                menu_funcs[step](menu)
            time.sleep(0.1)  # 중복 입력 방지용 딜레이


        elif GPIO.input(btn[2]) == GPIO.HIGH:  # 버튼 눌림
            short_beep(times=1) # 버튼 눌리면 부저 한번
            print(f"Button {btn[2]} pressed!")
            match step:
                case 1:
                    menu[1][0] = max(1, menu[1][0] - 10)
                case 2:
                    menu[2][0] = max(1, menu[2][0] - 5)
                case 3:
                    menu[3][0] = max(1, menu[3][0] - 1)
            menu_funcs[step](menu)

            time.sleep(0.1)  # 중복 입력 방지용 딜레이


        elif GPIO.input(btn[3]) == GPIO.HIGH:  # 버튼 눌림
            short_beep(times=1) # 버튼 눌리면 부저 한번
            step -= 1

            if step < 0:  # 음수 방지
                step = 0
            menu_funcs[step](menu)
            print(f"Button {btn[3]} pressed!")
            time.sleep(0.1)  # 중복 입력 방지용 딜레이
            
except KeyboardInterrupt:
    print("\n종료합니다.")
    GPIO.cleanup()

