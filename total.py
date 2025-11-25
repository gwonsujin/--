import RPi.GPIO as GPIO
import time
import pygame
import datetime
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

# DHT 온습도 센서 (GrovePi D7)
DHT_PIN = 7
DHT_TYPE = 0  # 0: DHT11, 1: DHT22  <-- 실제 센서 종류에 맞게 수정 필요

# --- Advanced Timer Constants ---
STOP_BUTTON_PIN = btn[3] # B4 is the Stop button
BUTTON_DEBOUNCE_S = 0.15
BUTTON_HOLD_S = 2.0         # Hold for 2s to quit

PIR_SAMPLES = 3
PIR_INTERVAL_S = 0.1        # Faster PIR read
PIR_MOTION_THRESHOLD = 2
PAUSE_ON_NO_MOTION_S = 8
PAUSE_ON_MOTION_S = 8

# BGM
pygame.mixer.init()
sound_sample = pygame.mixer.music
sound_sample.load("/home/pi/iot/music.mp3")
sound_sample.set_volume(0.1)

# ========================================
# 초기 설정 
# ========================================
# menu[0][0] : Mode (1=MOVE, 2=STAY, 3=TEMP, 4=RECORD, 5=LEVEL)
menu = [
    [1],  # 모드
    [30], # 운동시간 (초)
    [10], # 휴식시간 (초)
    [3]   # 세트수
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
# 부저 / 사운드 함수 
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

def state_change_beep():
    beep_ms(50)

# --- Sound Mapping ---
ok_sound = short_beep
cancel_sound = lambda: short_beep(times=2, dur_ms=80)
alert_sound = long_beep
start_sound = lambda: short_beep(times=2)
def _noop(*args, **kwargs): 
    pass
play_bgm = pause_bgm = resume_bgm = stop_bgm = _noop
# --- End Sound Mapping ---

# ========================================
# LCD Menu Functions 
# ========================================
def show_mode(m):
    """모드 선택 화면"""
    mode = m[0][0]
    if mode == 1:
        setRGB(0, 255, 0)
        setText("MOVE")
    elif mode == 2:
        setRGB(0, 100, 255)
        setText("STAY")
    elif mode == 3:
        setRGB(255, 0, 255)
        setText("TEMP")
    elif mode == 4:
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
# 온습도(TEMP 모드) 관련 함수
# ========================================
def read_dht_safe():
    """DHT 센서에서 온도/습도 읽기 (NaN/에러 처리)"""
    try:
        temp, hum = dht(DHT_PIN, DHT_TYPE)
        if temp is None or hum is None:
            return None, None
        if math.isnan(temp) or math.isnan(hum):
            return None, None
        return temp, hum
    except Exception:
        return None, None

def show_temp_env(m):
    """TEMP 모드에서 온습도 1회 측정 후 표시"""
    temp, hum = read_dht_safe()

    if temp is None or hum is None:
        setRGB(255, 100, 100)
        setText("TEMP ERROR\nCheck sensor")
        return

    # 상태 구간은 예시 (임의이지만 합리적 범위)
    if 18 <= temp <= 22 and 40 <= hum <= 60:
        status = "GOOD"
    elif 15 <= temp <= 27 and 30 <= hum <= 70:
        status = "MODERATE"
    else:
        status = "BAD"

    setRGB(100, 255, 100)
    setText(f"{temp:.1f}C {hum:.1f}%\nStatus: {status}")

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
    """duration_s 동안 Stop 버튼(B4) 입력을 주기적으로 확인"""
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
    """Pause 상태에서 재개 조건 대기"""
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

    # mode 1: 움직여야 하는 모드 (MOVE)
    # mode 2: 가만히 있어야 하는 모드 (STAY)
    if mode == 1:  
        if motion == 0 and diff >= PAUSE_ON_NO_MOTION_S:
            return "No Motion!"
    else:  # mode != 1 → STAY 모드 취급
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

    required_state = 1 if mode == 1 else 0  # MOVE→모션 필요, STAY→모션 없을 때 정상

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

        # 정상 상태면 타이머 기준 갱신
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

def run_exercise_session(m):
    init_pir_for_exercise()

    mode = m[0][0]
    exercise_s = m[1][0]
    rest_s = m[2][0]
    total_sets = m[3][0]

    # 혹시 모드가 3~5인 상태에서 시작되면 기본으로 MOVE로 강제
    if mode not in (1, 2):
        mode = 1
        m[0][0] = 1

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

# ========================================
# 기록 저장 / 레벨 시스템 (6개월 기준)
# ========================================
def save_record(exercise_s, total_sets):
    """운동 한 번 끝날 때 기록 저장"""
    total_ex = exercise_s * total_sets
    today = time.strftime("%Y-%m-%d")

    # 기록 저장 (날짜, 세션 운동 시간)
    try:
        with open("/home/pi/iot/records.txt", "a") as f:
            f.write(f"{today},{total_ex}\n")
    except Exception as e:
        print("record save error:", e)

    # total_time.txt는 load_total_last_6months에서 다시 계산하므로 여기서는 건드리지 않음

def load_total_last_6months():
    """최근 6개월 동안의 총 운동시간(초) 계산 및 total_time.txt 갱신"""
    records_path = "/home/pi/iot/records.txt"
    cutoff = datetime.date.today() - datetime.timedelta(days=180)

    total = 0

    try:
        with open(records_path, "r") as f:
            lines = f.readlines()

        for line in lines:
            if not line.strip():
                continue
            date_str, sec_str = line.strip().split(",")
            y, m_, d = map(int, date_str.split("-"))
            record_date = datetime.date(y, m_, d)

            if record_date >= cutoff:
                total += int(sec_str)

    except Exception:
        total = 0

    # 최신 누적 시간 total_time.txt 갱신
    try:
        with open("/home/pi/iot/total_time.txt", "w") as f:
            f.write(str(total))
    except Exception as e:
        print("total_time write error:", e)

    return total

def calc_level(total_seconds):
    """0~10 레벨 계산: 0~99→0, 100~199→1, ..., 900~999→9, 1000이상→10"""
    level = total_seconds // 100
    if level > 10:
        level = 10
    if level < 0:
        level = 0
    return level

def show_level(m=None):
    """LEVEL 메뉴: 최근 6개월 누적 기준 레벨 표시"""
    total = load_total_last_6months()
    level = calc_level(total)

    setRGB(200, 100, 255)
    setText(f"LEVEL {level}\n{total}s")

# ========================================
# 기록 보기(RECORD 모드)
# ========================================
records = []
record_index = 0

def record_mode_wrapper(m):
    """RECORD 모드 진입 시 초기 로드 및 현재 페이지 표시"""
    global records, record_index

    # 파일은 한 번만 읽기
    if not records:
        try:
            with open("/home/pi/iot/records.txt", "r") as f:
                lines = f.readlines()
                records = [
                    (d, int(sec)) 
                    for d, sec in (l.strip().split(",") for l in lines if l.strip())
                ]
        except Exception:
            records = []

    # 인덱스 범위 정리
    if records:
        record_index = max(0, min(record_index, len(records) - 1))

    show_record_page(records, record_index)

def show_record_page(records, index):
    if not records:
        setRGB(255, 100, 100)
        setText("NO RECORDS")
        return

    date, sec = records[index]
    setRGB(255, 165, 0)
    setText(f"{date}\n{sec}s")

# ========================================
# 운동 시작
# ========================================
def start_exercise(m):
    """운동 시작"""
    print("\n=== 운동 시작 ===")
    print(f"Mode: {m[0][0]}, 운동: {m[1][0]}s, 휴식: {m[2][0]}s, 세트: {m[3][0]}")

    sound_sample.play()
    run_exercise_session(m)
    sound_sample.stop()

    # 운동 기록 저장 + 6개월 기준 누적 갱신
    save_record(m[1][0], m[3][0])
    load_total_last_6months()

    print("=== 운동 종료 ===")
    setRGB(0, 255, 0)
    setText("Back to Menu")
    time.sleep(0.5)
    return 0  # 운동 후 다시 메뉴로 돌아감 (step = 0)

# ========================================
# Main Loop 
# ========================================
# step: 0=MODE, 1=EXERCISE, 2=REST, 3=SETS, 4=RECORD, 5=LEVEL
menu_funcs = [show_mode, show_exercise, show_rest, show_sets, record_mode_wrapper, show_level]
step = 0

setRGB(0, 255, 0)
print("mode start! (Ctrl+C로 종료)")
init_hardware()
menu_funcs[step](menu)

try:
    while True:
        # --- Button 1 (Val+) ---
        if GPIO.input(btn[0]) == GPIO.HIGH:
            ok_sound()
            mode = menu[0][0]

            # TEMP 모드에서 B1 → 온습도 갱신
            if step == 0 and mode == 3:
                show_temp_env(menu)
                time.sleep(BUTTON_DEBOUNCE_S)
                continue

            match step:
                case 0:  # Mode
                    menu[0][0] += 1
                    if menu[0][0] > 5:   # 모드 1~5 순환
                        menu[0][0] = 1
                case 1:  # Exercise
                    menu[1][0] += 10
                case 2:  # Rest
                    menu[2][0] += 5
                case 3:  # Sets
                    menu[3][0] += 1
                case 4:  # Record Mode - 다음 기록 페이지
                    if records:
                        record_index = (record_index + 1) % len(records)

            menu_funcs[step](menu)
            time.sleep(BUTTON_DEBOUNCE_S)
        
        # --- Button 2 (Next) ---
        elif GPIO.input(btn[1]) == GPIO.HIGH:
            ok_sound()
            mode = menu[0][0]

            # TEMP 모드에서 B2 → 온습도 갱신
            if step == 0 and mode == 3:
                show_temp_env(menu)
                time.sleep(BUTTON_DEBOUNCE_S)
                continue

            step = step + 1
            if step >= len(menu_funcs):
                # 마지막 메뉴를 지나면 운동 시작
                step = start_exercise(menu)
            
            menu_funcs[step](menu)
            time.sleep(BUTTON_DEBOUNCE_S)

        # --- Button 3 (Val-) ---
        elif GPIO.input(btn[2]) == GPIO.HIGH:
            ok_sound()
            mode = menu[0][0]

            # TEMP 모드에서 B3 → 온습도 갱신
            if step == 0 and mode == 3:
                show_temp_env(menu)
                time.sleep(BUTTON_DEBOUNCE_S)
                continue

            match step:
                case 0:  # Mode
                    menu[0][0] -= 1
                    if menu[0][0] < 1:   # 모드 1~5 순환
                        menu[0][0] = 5
                case 1:  # Exercise
                    menu[1][0] = max(10, menu[1][0] - 10)
                case 2:  # Rest
                    menu[2][0] = max(5, menu[2][0] - 5)
                case 3:  # Sets
                    menu[3][0] = max(1, menu[3][0] - 1)
                case 4:  # Record Mode - 이전 기록 페이지
                    if records:
                        record_index = (record_index - 1) % len(records)
            
            menu_funcs[step](menu)
            time.sleep(BUTTON_DEBOUNCE_S)

        # --- Button 4 (Prev / HOLD TO QUIT) ---
        elif GPIO.input(btn[3]) == GPIO.HIGH:
            press_start = time.time()
            
            # 길게 누르면 프로그램 종료
            while GPIO.input(btn[3]) == GPIO.HIGH:
                if time.time() - press_start > BUTTON_HOLD_S:
                    print("\n=== Quit Program (Hold B4) ===")
                    long_beep()
                    raise KeyboardInterrupt 
                time.sleep(0.05)
            
            # 짧게 누른 경우: 이전 메뉴로
            if time.time() - press_start < 0.5:
                ok_sound()
                step -= 1
                if step < 0:
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
