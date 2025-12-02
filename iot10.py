import RPi.GPIO as GPIO
import time
import pygame
from grovepi import *
from grove_rgb_lcd import *
import math

# ========================================
# Constants 
# ========================================
# 버튼 핀 번호 설정
btn = [22, 23, 24, 25] # B1(Val+), B2(Next), B3(Val-), B4(Prev)

# 모션감지/부저 핀 번호 설정
PIR_D = 8
BUZZER_D = 3

sensor_port = 7
sensor_type = 0

# --- Advanced Timer Constants ---
STOP_BUTTON_PIN = btn[3] # B4 is the Stop button
BUTTON_DEBOUNCE_S = 0.15
BUTTON_HOLD_S = 2.0         # --- NEW: Hold for 2s to quit ---

PIR_SAMPLES = 3
PIR_INTERVAL_S = 0.1        # Faster PIR read
PIR_MOTION_THRESHOLD = 2
PAUSE_ON_NO_MOTION_S = 8
PAUSE_ON_MOTION_S = 8

pygame.mixer.init()
sound_sample=pygame.mixer.music
sound_sample.load("/home/pi/iot/music.mp3")
sound_sample.set_volume(0.1)

# ========================================
# 초기 설정 
# ========================================
menu = [
    [1], # 모드 (m[0][0])
    [30], # 운동시간 (m[1][0])
    [10], # 휴식시간 (m[2][0])
    [3]  # 세트수 (m[3][0])
]

# ========================================
# 하드웨어 초기화 
# ========================================
def init_hardware():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    # GPIO 버튼 초기화
    for pin in btn:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    
    # GrovePi PIR, buzzer 초기화
    try:
        pinMode(PIR_D, "INPUT")
        pinMode(BUZZER_D, "OUTPUT")
    except Exception as e:
        print(f"HW Init Error: {e}")

# ========================================
# 부저 함수 
# ========================================
def beep_ms(ms: int):
    try:
        digitalWrite(BUZZER_D, 1)
        time.sleep(ms / 1000.0)
        digitalWrite(BUZZER_D, 0)
    except Exception:
        pass # Ignore errors

def short_beep(times=1, dur_ms=120, gap_ms=80):
    for _ in range(times):
        beep_ms(dur_ms)
        if times > 1:
            time.sleep(gap_ms / 1000.0)

def long_beep(dur_ms=400):
    beep_ms(dur_ms)

# --- NEW: Very short beep for state change ---
def state_change_beep():
    beep_ms(50)
# --- END NEW ---

# --- Sound Mapping ---
ok_sound = short_beep
cancel_sound = lambda: short_beep(times=2, dur_ms=80)
alert_sound = long_beep
start_sound = lambda: short_beep(times=2)
def _noop(*args, **kwargs): pass
play_bgm = pause_bgm = resume_bgm = stop_bgm = _noop
# --- End Sound Mapping ---

# ========================================
# LCD Menu Functions 
# ========================================
def show_mode(m):
    """모드 선택 화면"""
    if m[0][0] == 1:
        setRGB(0, 255, 0)
        setText("MOVE")
    elif m[0][0] == 2:
        setRGB(0, 100, 255)
        setText("STAY")
    elif m[0][0] == 3:
        setRGB(255, 0, 255)
        setText("TEMP")
    elif m[0][0] == 4:
        setRGB(255, 165, 0)
        setText("RECORD")
    else:
        setRGB(255, 255, 255)
        setText("LEVEL")

def show_exercise(m):
    """운동 시간 설정"""
    setRGB(255, 255, 255)
    setText(f"Exercise Time\n{m[1][0]}s")

def show_rest(m):
    """휴식 시간 설정"""
    setRGB(255, 255, 255)
    setText(f"Rest Time\n{m[2][0]}s")

def show_sets(m):
    """세트 수 설정"""
    mode = m[0][0]
    exer = m[1][0]
    rest = m[2][0]
    sets = m[3][0]
    
    line1 = f"M:{mode} Ex:{exer} R:{rest}"
    line2 = f"Sets:{sets} (Press>)"
    
    setRGB(0, 255, 255)
    setText(f"{line1}\n{line2}")

# ========================================
# Timer Logic 
# ========================================
def get_progress_bar(current, total, width=10):
    if total <= 0:
        return "█" * width
    fill_len = int(width * current / total)
    fill_len = max(0, min(fill_len, width))
    return f'{"█" * fill_len}{"░" * (width - fill_len)}'

def responsive_sleep(duration_s):
    """Waits for 1s, but checks for Stop button 10x."""
    steps = 10
    for _ in range(int(duration_s * steps)):
        if GPIO.input(STOP_BUTTON_PIN) == GPIO.HIGH:
            return True # Stop signal detected
        time.sleep(1 / steps)
    return False

def read_pir_stable():
    """Stable PIR Read"""
    samples = []
    for _ in range(PIR_SAMPLES):
        try:
            val = digitalRead(PIR_D)
            samples.append(val)
        except Exception:
            samples.append(0)
        time.sleep(PIR_INTERVAL_S)
    
    motion_count = sum(samples)
    return 1 if motion_count >= PIR_MOTION_THRESHOLD else 0

def wait_for_resume(required_state):
    """Wait for resume from pause."""
    while GPIO.input(STOP_BUTTON_PIN) == GPIO.LOW:
        motion = read_pir_stable()
        if motion == required_state:
            return False # Resumed normally
        time.sleep(0.3)
    return True # Stop signal detected

# ========================================
# run_exercise_session 내부 기능 분리 함수들
# ========================================

def init_pir_for_exercise():
    """PIR 초기화"""
    try:
        pinMode(PIR_D, "INPUT")
        time.sleep(0.5)
    except Exception as e:
        print(f"PIR init error: {e}")


def check_pause_condition(mode, motion, last_valid_state_time):
    """모션/정지 상태에 따른 Pause 조건 체크"""
    now = time.time()
    diff = now - last_valid_state_time

    if mode == 1:  # 움직여야 하는 모드
        if motion == 0 and diff >= PAUSE_ON_NO_MOTION_S:
            return "No Motion!"
    else:  # mode 2 — 가만히 있어야 하는 모드
        if motion == 1 and diff >= PAUSE_ON_MOTION_S:
            return "Motion Detect!"

    return None


def handle_pause(reason, required_state):
    """Pause 화면 표시 후 Resume 기다리기"""
    pause_bgm()
    cancel_sound()

    setRGB(255, 165, 0)
    setText(f"PAUSED\n{reason}")

    if wait_for_resume(required_state):
        stop_bgm()
        setRGB(255, 0, 0)
        setText("Stopped\nReturning...")
        time.sleep(1.5)
        return False

    ok_sound()
    resume_bgm()
    return True


def update_exercise_display(mode, set_num, total_sets, motion, timer_s, exercise_s):
    """LCD 운동 진행 상황 갱신"""
    status_text = "MOVE" if motion == 1 else "STAY"
    remaining_s = exercise_s - timer_s
    bar = get_progress_bar(timer_s, exercise_s, 10)

    setRGB(0, 255, 0)
    setText(f"M{mode} Set {set_num}/{total_sets} {status_text}\n{bar} {remaining_s}s")


def run_rest_interval(set_num, total_sets, rest_s):
    """세트 사이 휴식 구간"""
    for t in range(rest_s):
        remaining_s = rest_s - t
        bar = get_progress_bar(t, rest_s, 10)

        setRGB(0, 150, 255)
        setText(f"Rest {set_num}/{total_sets}\n{bar} {remaining_s}s")

        if responsive_sleep(1):
            setRGB(255, 0, 0)
            setText("Stopped\nReturning...")
            time.sleep(1.5)
            return False

    start_sound()  # 휴식 끝 → 다음 세트 시작 알림
    return True


def run_single_set(set_num, total_sets, mode, exercise_s, rest_s):
    """한 세트의 운동 구간 전체 처리"""
    play_bgm()
    timer_s = 0
    last_valid_state_time = time.time()
    last_pir_state = -1

    required_state = 1 if mode == 1 else 0

    while timer_s < exercise_s:
        motion = read_pir_stable()

        # 상태 변화 감지 비프음
        if last_pir_state != -1 and motion != last_pir_state:
            state_change_beep()
        last_pir_state = motion

        # Pause 조건 체크
        reason = check_pause_condition(mode, motion, last_valid_state_time)
        if reason:
            if not handle_pause(reason, required_state):
                return False
            last_valid_state_time = time.time()
            last_pir_state = -1

        # 정상 상태면 타이머 갱신
        if motion == required_state:
            last_valid_state_time = time.time()

        update_exercise_display(mode, set_num, total_sets, motion, timer_s, exercise_s)

        if responsive_sleep(1):
            stop_bgm()
            return False

        timer_s += 1

    stop_bgm()
    alert_sound()

    # 마지막 세트가 아니면 휴식
    if set_num < total_sets:
        return run_rest_interval(set_num, total_sets, rest_s)

    return True


# ========================================
# ✨ 최종: 분리된 run_exercise_session
# ========================================
def run_exercise_session(m):
    init_pir_for_exercise()

    mode = m[0][0]
    exercise_s = m[1][0]
    rest_s = m[2][0]
    total_sets = m[3][0]

    start_sound()
    if responsive_sleep(0.5):
        return

    for set_num in range(1, total_sets + 1):
        ok = run_single_set(set_num, total_sets, mode, exercise_s, rest_s)
        if not ok:
            return

    # 완료 화면
    setRGB(255, 0, 255)
    setText("Complete!\nPress any btn")

    while all(GPIO.input(p) == GPIO.LOW for p in btn):
        time.sleep(0.05)

    time.sleep(BUTTON_DEBOUNCE_S)

def start_exercise(m):
    """운동 시작"""
    print("\n=== 운동 시작 ===")
    print(f"Mode: {m[0][0]}, 운동: {m[1][0]}s, 휴식: {m[2][0]}s, 세트: {m[3][0]}")
    
    #운동 함수 시작
    sound_sample.play()
    run_exercise_session(m) 
    sound_sample.stop()

    print("=== 운동 종료 ===")

    #운동기록
    try:
        with open("records.txt", "a", encoding="utf-8") as f:  # append 모드로 열기
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            mode_name = {1: "MOVE", 2: "STAY"}.get(m[0][0], "UNKNOWN")
            record_line = f"[{timestamp}] Mode:{mode_name}, Exercise:{m[1][0]}s, Rest:{m[2][0]}s, Sets:{m[3][0]}\n"
            f.write(record_line)
        print(f"운동 기록 저장 완료 → record.txt ({record_line.strip()})")
        time.sleep(0.5)
    except Exception as e:
        print(f"기록 저장 실패: {e}")
        time.sleep(0.5)


    setRGB(0, 255, 0)
    setText("Back to Menu")
    time.sleep(0.5)
    return 0  # 운동 후 다시 메뉴로 돌아감 (step = 0)

#온습도
def show_temp():
    temp, hum = dht(sensor_port, sensor_type)

    if 15 <= temp <= 27 and 30 <= hum <= 70:
        status = "GOOD"
    else:
        status = "BAD"

    setRGB(100, 255, 100)
    setText(f"{temp:.1f}°C {hum:.1f}%\nStatus: {status}")

    while True:
        if GPIO.input(btn[3]) == GPIO.HIGH:
            ok_sound()
            time.sleep(BUTTON_DEBOUNCE_S)
            break
    # step 0으로 리턴 → 메인 루프로 돌아감
    return 0

def show_record():
    """records.txt 내용을 LCD에 간단히 표시 (날짜는 YY.MM.DD 형식, 최신순)"""
    setRGB(100, 255, 100)
    try:
        with open("records.txt", "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            print(lines)
    except FileNotFoundError:
        setText("No Records Yet\n(Press < to exit)")
        while True:
            if GPIO.input(btn[3]) == GPIO.HIGH:
                ok_sound()
                time.sleep(BUTTON_DEBOUNCE_S)
                break
        return 0

    if not lines:
        setText("No Records Yet\n(Press < to exit)")
        while True:
            if GPIO.input(btn[3]) == GPIO.HIGH:
                ok_sound()
                time.sleep(BUTTON_DEBOUNCE_S)
                break
        return 0

    # 최신 기록부터 표시
    lines.reverse()
    page = 0
    total = len(lines)

    def parse_record(line):
        """
        예: [2025-12-02 23:10:02] Mode:MOVE, Exercise:20s, Rest:5s, Sets:4
        → ("25.12.02", "MOVE", "20", "5", "4")
        """
        try:
            parts = line.split("] ")
            date_str = parts[0][1:11]  # 2025-12-02
            yy = date_str[2:4]
            mm = date_str[5:7]
            dd = date_str[8:10]
            short_date = f"{yy}.{mm}.{dd}"
            data = parts[1].split(", ")
            mode = data[0].split(":")[1]
            exer = data[1].split(":")[1].replace("s", "")
            rest = data[2].split(":")[1].replace("s", "")
            sets = data[3].split(":")[1]
            return short_date, mode, exer, rest, sets
        except Exception:
            return "--.--.--", "?", "?", "?", "?"

    def show_page():
        date, mode, exer, rest, sets = parse_record(lines[page])
        setText(f"[{date}]{mode}\nEx:{exer} R:{rest} S:{sets}")
        print(f"[LCD] Page {page+1}/{total} → {date} | {mode} Ex:{exer} R:{rest} S:{sets}")

    show_page()

    while True:
        # --- Next (B2) ---
        if GPIO.input(btn[0]) == GPIO.HIGH:
            if page < total - 1:
                page += 1
                ok_sound()
                show_page()
            else:
                cancel_sound()
            time.sleep(BUTTON_DEBOUNCE_S)

        # --- Prev (B3) ---
        elif GPIO.input(btn[2]) == GPIO.HIGH:
            if page > 0:
                page -= 1
                ok_sound()
                show_page()
            else:
                cancel_sound()
            time.sleep(BUTTON_DEBOUNCE_S)

        # --- Exit (B4) ---
        elif GPIO.input(btn[3]) == GPIO.HIGH:
            ok_sound()
            time.sleep(BUTTON_DEBOUNCE_S)
            break

        time.sleep(0.05)

    return 0


# def show_record():
#     setRGB(100, 255, 100)
#     setText(f"record")

#     while True:
#         if GPIO.input(btn[3]) == GPIO.HIGH:
#             ok_sound()
#             time.sleep(BUTTON_DEBOUNCE_S)
#             break
#     # step 0으로 리턴 → 메인 루프로 돌아감
#     return 0


def show_level():
    """운동 기록 기반 레벨 시스템 (레벨 10 이상 '운동의 신' 칭호 부여)"""
    total_time = 0

    try:
        with open("records.txt", "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        setRGB(255, 100, 100)
        setText("No Records Yet\n(Press < to exit)")
        while True:
            if GPIO.input(btn[3]) == GPIO.HIGH:
                ok_sound()
                time.sleep(BUTTON_DEBOUNCE_S)
                break
        return 0

    # 총 운동 시간 계산 (Exercise × Sets)
    for line in lines:
        try:
            parts = line.split(", ")
            exercise = int(parts[1].split(":")[1].replace("s", ""))
            sets = int(parts[3].split(":")[1])
            total_time += exercise * sets
        except Exception:
            continue

    # 레벨 계산
    level = total_time // 100  # 100 단위당 레벨 1
    if level > 10:
        level = 10  # 레벨 10이 최대

    # LCD 표시용 텍스트
    if level >= 10:
        title = "<You are God>"
    else:
        title = f"Level {level}"

    # LCD 색상 및 출력
    if level < 5:
        setRGB(100, 255, 100)
    elif level < 10:
        setRGB(255, 255, 100)
    else:
        setRGB(255, 100, 0)  # 운동의 신 색상 강조

    setText(f"Total:{total_time}s\n{title}")
    print(f"[LEVEL] 총 운동시간={total_time}s → {title}")

    # 종료 버튼 대기
    while True:
        if GPIO.input(btn[3]) == GPIO.HIGH:
            ok_sound()
            time.sleep(BUTTON_DEBOUNCE_S)
            break
        time.sleep(0.05)

    return 0


# ========================================
# Main Loop 
# ========================================
menu_funcs = [show_mode, show_exercise, show_rest, show_sets, show_temp, show_record, show_level]
step = 0

setRGB(0,255,0)
print("mode start! (Ctrl+C로 종료)")
init_hardware()
menu_funcs[step](menu)

try:
    while True:
        # --- Button 1 (Val+) ---
        if GPIO.input(btn[0]) == GPIO.HIGH:
            ok_sound() # Beep on button press
            match step:
                case 0: # Mode
                    menu[0][0] += 1
                    if menu[0][0] > 5:   # 모드 1~5 순환
                        menu[0][0] = 1
                case 1: # Exercise
                    menu[1][0] += 10
                case 2: # Rest
                    menu[2][0] += 5
                case 3: # Sets
                    menu[3][0] += 1
            
            menu_funcs[step](menu)
            time.sleep(BUTTON_DEBOUNCE_S)
        
        # --- Button 2 (Next) ---
        elif GPIO.input(btn[1]) == GPIO.HIGH:
            ok_sound() # Beep on button press
            step = step + 1
            mode = menu[0][0]
            if mode in [1, 2] and step > 3:
                step = start_exercise(menu)
            elif mode ==3:
                show_temp()
                step = 0
            elif mode == 4:
                show_record()
                step = 0
            elif mode ==5:
                show_level()
                step = 0

            menu_funcs[step](menu)
            time.sleep(BUTTON_DEBOUNCE_S)

        # --- Button 3 (Val-) ---
        elif GPIO.input(btn[2]) == GPIO.HIGH:
            ok_sound() # Beep on button press
            match step:
                case 0: # Mode
                    menu[0][0] -= 1
                    if menu[0][0] < 1:   # 모드 1~5 순환
                        menu[0][0] = 5
                case 1: # Exercise
                    menu[1][0] = max(10, menu[1][0] - 10)
                case 2: # Rest
                    menu[2][0] = max(5, menu[2][0] - 5)
                case 3: # Sets
                    menu[3][0] = max(1, menu[3][0] - 1)
            
            menu_funcs[step](menu)
            time.sleep(BUTTON_DEBOUNCE_S)

        # --- Button 4 (Prev / HOLD TO QUIT) ---
        elif GPIO.input(btn[3]) == GPIO.HIGH:
            press_start = time.time()
            
            # --- NEW: Check for long press ---
            while GPIO.input(btn[3]) == GPIO.HIGH:
                if time.time() - press_start > BUTTON_HOLD_S:
                    print("\n=== Quit Program (Hold B4) ===")
                    long_beep()
                    raise KeyboardInterrupt 
                time.sleep(0.05)
            # --- END NEW ---
            
            # If it was just a short press, run the "Prev"
            if time.time() - press_start < 0.5:
                ok_sound() # Beep on button press
                step -= 1
                if step < 0:  # 음수 방지
                    step = 0
                menu_funcs[step](menu)
                
            time.sleep(BUTTON_DEBOUNCE_S)
            
        else:
            time.sleep(0.01)

except KeyboardInterrupt:
    print("\n종료합니다.")
finally:
    GPIO.cleanup()
    setRGB(128, 128, 128)
    setText("Goodbye!")