import RPi.GPIO as GPIO
import time
import pygame
from grovepi import *
from grove_rgb_lcd import *

# ========================================
# [수정] 모듈 Import 추가
# ========================================
import datetime_logic as logic   # 계산 모듈
import csv_module as saver       # 저장 모듈
import level_module as leveling  # 레벨 모듈

# ========================================
# Constants 
# ========================================
# 버튼 핀 번호 설정
btn = [22, 23, 24, 25] # B1(Val+), B2(Next), B3(Val-), B4(Prev)

# 모션감지/부저 핀 번호 설정
PIR_D = 8
BUZZER_D = 3

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

    # ========================================
    # [수정] 인자를 개별 값이 아닌 리스트(m) 전체로 변경
    # ========================================
    save_record(m) 

    print("=== 운동 종료 ===")
    setRGB(0, 255, 0)
    setText("Back to Menu")
    time.sleep(0.5)
    return 0  # 운동 후 다시 메뉴로 돌아감 (step = 0)

# ========================================
# [수정] 기록 저장 함수 (모듈 사용)
# ========================================
# 전역 변수를 수정하기 위해 global 선언 필요
def save_record(m):
    global records  # <--- [추가]
    
    # 1. 계산
    timestamp, w_time, sets, total_sec = logic.calculate_total_time(m)
    
    # 2. 레벨 판별
    current_level_str = leveling.determine_level(total_sec)
    
    # 3. 저장
    saver.save_to_csv(timestamp, w_time, sets, total_sec, current_level_str)
    
    # 4. [핵심 수정] 메모리 상의 기록 초기화 -> 다음 조회 시 CSV 다시 읽음
    records = []  # <--- [추가] 이렇게 하면 다음 조회 때 갱신된 파일을 읽어옴
    
    print(f"--> 기록 저장 완료: {total_sec}초 ({current_level_str})")

# ========================================
# [수정] 기록 보기 모드 (CSV 읽기)
# ========================================
def record_mode_wrapper(m):
    global records, record_index

    # 파일은 한 번만 읽거나, 레코드가 비었을 때 다시 읽음
    if not records:
        try:
            import csv
            import os
            file_name = 'workout_log.csv'
            
            if os.path.isfile(file_name):
                with open(file_name, "r", encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader, None) # 헤더(제목줄) 건너뛰기
                    
                    # CSV 구조: [0]날짜, [1]운동, [2]세트, [3]총시간, [4]등급
                    # 필요한 것: 날짜와 총시간
                    records = []
                    for row in reader:
                        if len(row) >= 4:
                            records.append((row[0], int(row[3])))
            else:
                records = []
                for row in reader:
                    # 데이터 유효성 검사 강화
                    if len(row) >= 5: # 날짜, 운동, 세트, 총시간, 등급 (5개 열)
                        try:
                            # 날짜와 총시간(정수변환)만 추출
                            r_date = row[0]
                            r_sec = int(row[3]) 
                            records.append((r_date, r_sec))
                        except ValueError:
                            continue # 숫자가 아니면 이 줄은 건너뜀
        except Exception as e:
            print(f"기록 읽기 실패: {e}")
            records = []

    # 인덱스 범위 정리
    if records:
        record_index = max(0, min(record_index, len(records)-1))

    show_record_page(records, record_index)


def show_record_page(records, index):
    if not records:
        setRGB(255, 100, 100)
        setText("NO RECORDS")
        return

    date, sec = records[index]
    setRGB(255, 165, 0)
    setText(f"{date}\n{sec}s")

#level 시스템

# ========================================
# [수정] 레벨 시스템 (누적 시간 기반)
# ========================================
def show_level(m):
    # 1. csv_module의 함수를 이용해 총 누적 시간(초)을 가져옴
    total_accumulated = saver.get_total_accumulated_time()
    
    # 2. 레벨 계산 (새로운 모듈 기준인 100초 단위로 맞춤)
    # level_module은 문자열을 반환하므로, 여기선 게이지바용 숫자가 필요해 직접 계산
    level_num = total_accumulated // 100 
    
    # 퍼센트 계산 (다음 레벨까지 남은 % 표시)
    # 예: 150초면 -> 1레벨, 50% 달성
    percent = total_accumulated % 100

    setRGB(200, 100, 255)
    # 화면 표시: 총 시간 / 레벨 / 퍼센트
    setText(f"Total: {total_accumulated}s\nLv.{level_num} ({percent}%)")



# ========================================
# Main Loop 
# ========================================
menu_funcs = [show_mode, show_exercise, show_rest, show_sets, record_mode_wrapper, show_level]

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
                case 4: # Record Mode
                    if records:
                        record_index = (record_index + 1) % len(records)

            
            menu_funcs[step](menu)
            time.sleep(BUTTON_DEBOUNCE_S)
        
        # --- Button 2 (Next) ---
        elif GPIO.input(btn[1]) == GPIO.HIGH:
            ok_sound() # Beep on button press
            step = step + 1
            if step >= len(menu_funcs):  # 3을 넘으면 운동 시작
                step = start_exercise(menu)
            
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
                case 4: # Record Mode
                    if records:
                        record_index = (record_index - 1) % len(records)
            
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