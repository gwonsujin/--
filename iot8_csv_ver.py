################################################################################
# 파일 6: iot8_csv_ver.py (메인 프로그램)
# 목적: 라즈베리파이 IoT 운동 트래커 메인 프로그램
# 구성: GPIO, LCD, PIR센서, 부저, 버튼 제어 + 운동 로직
################################################################################

import RPi.GPIO as GPIO
import time
import pygame
import os
from grovepi import *
from grove_rgb_lcd import *

# ========================================
# [사용자 모듈 임포트]
# ========================================
import datetime_logic as logic
import csv_module as saver
import level_module as leveling

# ========================================
# [전역 변수 초기화]
# ========================================
records = []       # 기록 저장용 리스트
record_index = 0   # 기록 보기 인덱스

# ========================================
# [하드웨어 핀 상수 정의]
# ========================================
btn = [22, 23, 24, 25]  # 버튼 4개 핀 번호
PIR_D = 8               # PIR 센서 핀
BUZZER_D = 3            # 부저 핀
STOP_BUTTON_PIN = btn[3]

# ========================================
# [타이밍 상수]
# ========================================
BUTTON_DEBOUNCE_S = 0.15      # 버튼 디바운싱 시간
BUTTON_HOLD_S = 2.0           # 길게 누르기 판정 시간
PIR_SAMPLES = 3               # PIR 안정화 샘플 수
PIR_INTERVAL_S = 0.1          # PIR 샘플링 간격
PIR_MOTION_THRESHOLD = 2      # 움직임 감지 임계값
PAUSE_ON_NO_MOTION_S = 8      # 무동작 일시정지 시간
PAUSE_ON_MOTION_S = 8         # 동작감지 일시정지 시간

# ========================================
# [사운드 초기화]
# ========================================
pygame.mixer.init()
sound_sample = pygame.mixer.music
music_path = "/home/pi/iot/music.mp3"

if os.path.exists(music_path):
    try:
        sound_sample.load(music_path)
        sound_sample.set_volume(0.1)
    except Exception as e:
        print(f"BGM Error: {e}")
else:
    # 파일 없으면 더미 함수 처리 (에러 방지)
    sound_sample.play = lambda *args: None
    sound_sample.stop = lambda *args: None

# ========================================
# [메뉴 초기값]
# 형식: [[모드], [운동시간], [휴식시간], [세트수]]
# ========================================
menu = [[1], [30], [10], [3]]

# ========================================
# [하드웨어 초기화 함수]
# ========================================
def init_hardware():
    """GPIO 및 GrovePi 하드웨어 초기화"""
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    for pin in btn:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    try:
        pinMode(PIR_D, "INPUT")
        pinMode(BUZZER_D, "OUTPUT")
    except Exception as e:
        print(f"HW Init Error: {e}")

# ========================================
# [부저 제어 함수]
# ========================================
def beep_ms(ms: int):
    """밀리초 단위로 부저 울리기"""
    try:
        digitalWrite(BUZZER_D, 1)
        time.sleep(ms / 1000.0)
        digitalWrite(BUZZER_D, 0)
    except: 
        pass

def short_beep(times=1, dur_ms=120, gap_ms=80):
    """짧은 비프음 (여러 번 가능)"""
    for _ in range(times):
        beep_ms(dur_ms)
        if times > 1: 
            time.sleep(gap_ms / 1000.0)

def long_beep(dur_ms=400): 
    """긴 비프음"""
    beep_ms(dur_ms)

def state_change_beep(): 
    """상태 변경 비프음"""
    beep_ms(50)

# ========================================
# [사운드 이벤트 함수]
# ========================================
ok_sound = short_beep
cancel_sound = lambda: short_beep(times=2, dur_ms=80)
alert_sound = long_beep
start_sound = lambda: short_beep(times=2)

# BGM 제어 (현재는 더미)
def _noop(*args, **kwargs): 
    pass
play_bgm = pause_bgm = resume_bgm = stop_bgm = _noop

# ========================================
# [LCD 화면 표시 함수]
# ========================================
def show_mode(m):
    """모드 선택 화면"""
    if m[0][0] == 1:   
        setRGB(0, 255, 0); setText("MOVE")
    elif m[0][0] == 2: 
        setRGB(0, 100, 255); setText("STAY")
    elif m[0][0] == 3: 
        setRGB(255, 0, 255); setText("TEMP")
    elif m[0][0] == 4: 
        setRGB(255, 165, 0); setText("RECORD")
    else:              
        setRGB(255, 255, 255); setText("LEVEL")

def show_exercise(m): 
    """운동 시간 설정 화면"""
    setRGB(255, 255, 255)
    setText(f"Exercise Time\n{m[1][0]}s")

def show_rest(m):     
    """휴식 시간 설정 화면"""
    setRGB(255, 255, 255)
    setText(f"Rest Time\n{m[2][0]}s")

def show_sets(m):     
    """세트 수 확인 화면"""
    setRGB(0, 255, 255)
    setText(f"M:{m[0][0]} Ex:{m[1][0]} R:{m[2][0]}\nSets:{m[3][0]} (Press>)")

# ========================================
# [타이머 및 진행바 함수]
# ========================================
def get_progress_bar(current, total, width=10):
    """진행 상황을 시각화하는 프로그레스바 생성"""
    if total <= 0: 
        return "█" * width
    fill_len = int(width * current / total)
    fill_len = max(0, min(fill_len, width))
    return f'{"█" * fill_len}{"░" * (width - fill_len)}'

def responsive_sleep(duration_s):
    """중단 버튼 체크가 가능한 sleep 함수"""
    steps = 10
    for _ in range(int(duration_s * steps)):
        if GPIO.input(STOP_BUTTON_PIN) == GPIO.HIGH: 
            return True
        time.sleep(1 / steps)
    return False

# ========================================
# [PIR 센서 제어 함수]
# ========================================
def read_pir_stable():
    """PIR 센서 안정화된 값 읽기 (노이즈 제거)"""
    samples = []
    for _ in range(PIR_SAMPLES):
        try: 
            samples.append(digitalRead(PIR_D))
        except: 
            samples.append(0)
        time.sleep(PIR_INTERVAL_S)
    return 1 if sum(samples) >= PIR_MOTION_THRESHOLD else 0

def wait_for_resume(required_state):
    """일시정지 후 재개 대기"""
    while GPIO.input(STOP_BUTTON_PIN) == GPIO.LOW:
        if read_pir_stable() == required_state: 
            return False
        time.sleep(0.3)
    return True

# ========================================
# [운동 세션 로직 - 초기화]
# ========================================
def init_pir_for_exercise():
    """운동 시작 전 PIR 센서 초기화"""
    try: 
        pinMode(PIR_D, "INPUT")
        time.sleep(0.5)
    except: 
        pass

# ========================================
# [운동 세션 로직 - 일시정지 체크]
# ========================================
def check_pause_condition(mode, motion, last_valid_state_time):
    """일시정지 조건 확인"""
    now = time.time()
    diff = now - last_valid_state_time
    if mode == 1 and motion == 0 and diff >= PAUSE_ON_NO_MOTION_S: 
        return "No Motion!"
    if mode == 2 and motion == 1 and diff >= PAUSE_ON_MOTION_S: 
        return "Motion Detect!"
    return None

def handle_pause(reason, required_state):
    """일시정지 처리"""
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

# ========================================
# [운동 세션 로직 - 화면 업데이트]
# ========================================
def update_exercise_display(mode, set_num, total_sets, motion, timer_s, exercise_s):
    """운동 중 LCD 화면 업데이트"""
    status = "MOVE" if motion == 1 else "STAY"
    bar = get_progress_bar(timer_s, exercise_s, 10)
    setRGB(0, 255, 0)
    setText(f"M{mode} Set {set_num}/{total_sets} {status}\n{bar} {exercise_s - timer_s}s")

# ========================================
# [운동 세션 로직 - 휴식 구간]
# ========================================
def run_rest_interval(set_num, total_sets, rest_s):
    """세트 간 휴식 시간 처리"""
    for t in range(rest_s):
        bar = get_progress_bar(t, rest_s, 10)
        setRGB(0, 150, 255)
        setText(f"Rest {set_num}/{total_sets}\n{bar} {rest_s - t}s")
        
        if responsive_sleep(1):
            setRGB(255, 0, 0)
            setText("Stopped\nReturning...")
            time.sleep(1.5)
            return False
    
    start_sound()
    return True

# ========================================
# [운동 세션 로직 - 단일 세트 실행]
# ========================================
def run_single_set(set_num, total_sets, mode, exercise_s, rest_s):
    """한 세트 운동 실행"""
    play_bgm()
    timer_s = 0
    last_valid_state_time = time.time()
    last_pir_state = -1
    required_state = 1 if mode == 1 else 0

    while timer_s < exercise_s:
        motion = read_pir_stable()
        
        # 상태 변경 감지 시 비프음
        if last_pir_state != -1 and motion != last_pir_state: 
            state_change_beep()
        last_pir_state = motion
        
        # 일시정지 조건 체크
        reason = check_pause_condition(mode, motion, last_valid_state_time)
        if reason:
            if not handle_pause(reason, required_state): 
                return False
            last_valid_state_time = time.time()
            last_pir_state = -1
        
        # 올바른 상태일 때 시간 갱신
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
# [운동 세션 로직 - 전체 세션]
# ========================================
def run_exercise_session(m):
    """전체 운동 세션 실행"""
    init_pir_for_exercise()
    start_sound()
    
    if responsive_sleep(0.5): 
        return
    
    for s in range(1, m[3][0] + 1):
        if not run_single_set(s, m[3][0], m[0][0], m[1][0], m[2][0]): 
            return
    
    setRGB(255, 0, 255)
    setText("Complete!\nPress any btn")
    
    while all(GPIO.input(p) == GPIO.LOW for p in btn): 
        time.sleep(0.05)
    
    time.sleep(BUTTON_DEBOUNCE_S)

# ========================================
# [데이터 저장 함수]
# ========================================
def save_record(m):
    """운동 기록 저장"""
    global records
    timestamp, w_time, sets, total_sec = logic.calculate_total_time(m)
    current_level_str = leveling.determine_level(total_sec)
    saver.save_to_csv(timestamp, w_time, sets, total_sec, current_level_str)
    
    # 기록 초기화 -> 다음 조회 시 갱신된 파일 읽도록 유도
    records = []
    print(f"--> Saved: {total_sec}s ({current_level_str})")

# ========================================
# [기록 조회 함수]
# ========================================
def record_mode_wrapper(m):
    """기록 모드 진입 시 CSV 파일 로드"""
    global records, record_index
    
    # records가 비어있으면 파일에서 다시 읽기
    if not records:
        try:
            import csv
            file_name = 'workout_log.csv'
            if os.path.isfile(file_name):
                with open(file_name, "r", encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if len(row) >= 5:
                            try: 
                                records.append((row[0], int(row[3])))
                            except: 
                                continue
        except Exception as e:
            print(f"Load Error: {e}")
            records = []

    if records:
        record_index = max(0, min(record_index, len(records)-1))
    else:
        record_index = 0
    
    show_record_page(records, record_index)

def show_record_page(records, index):
    """기록 페이지 표시"""
    if not records:
        setRGB(255, 100, 100)
        setText("NO RECORDS")
    else:
        date, sec = records[index]
        setRGB(255, 165, 0)
        setText(f"{date}\n{sec}s")

# ========================================
# [레벨 조회 함수]
# ========================================
def show_level(m):
    """현재 누적 레벨 표시"""
    total = saver.get_total_accumulated_time()
    level = total // 100
    percent = total % 100
    setRGB(200, 100, 255)
    setText(f"Total: {total}s\nLv.{level} ({percent}%)")

# ========================================
# [운동 시작 함수]
# ========================================
def start_exercise(m):
    """운동 시작 및 저장 처리"""
    print("\n=== Start Workout ===")
    sound_sample.play()
    run_exercise_session(m) 
    sound_sample.stop()
    save_record(m) 
    print("=== End Workout ===")
    setRGB(0, 255, 0)
    setText("Back to Menu")
    time.sleep(0.5)
    return 0

# ========================================
# [메인 루프 설정]
# ========================================
menu_funcs = [
    show_mode,           # 0: 모드 선택
    show_exercise,       # 1: 운동 시간
    show_rest,           # 2: 휴식 시간
    show_sets,           # 3: 세트 수
    record_mode_wrapper, # 4: 기록 조회
    show_level           # 5: 레벨 조회
]
step = 0

# ========================================
# [메인 실행 부분]
# ========================================
print("System Ready. (Ctrl+C to Quit)")
init_hardware()
menu_funcs[step](menu)

try:
    while True:
        # 버튼1: 값 변경 / 다음 기록
        if GPIO.input(btn[0]) == GPIO.HIGH:
            ok_sound()
            if step == 0: 
                menu[0][0] = 1 if menu[0][0] >= 5 else menu[0][0] + 1
            elif step == 1: 
                menu[1][0] += 10
            elif step == 2: 
                menu[2][0] += 5
            elif step == 3: 
                menu[3][0] += 1
            elif step == 4 and records: 
                record_index = (record_index + 1) % len(records)
            menu_funcs[step](menu)
            time.sleep(BUTTON_DEBOUNCE_S)
        
        # 버튼2: 다음 메뉴 / 시작
        elif GPIO.input(btn[1]) == GPIO.HIGH:
            ok_sound()
            step += 1
            if step >= len(menu_funcs): 
                step = start_exercise(menu)
            menu_funcs[step](menu)
            time.sleep(BUTTON_DEBOUNCE_S)

        # 버튼3: 이전 값 / 이전 기록
        elif GPIO.input(btn[2]) == GPIO.HIGH:
            ok_sound()
            if step == 0: 
                menu[0][0] = 5 if menu[0][0] <= 1 else menu[0][0] - 1
            elif step == 1: 
                menu[1][0] = max(10, menu[1][0] - 10)
            elif step == 2: 
                menu[2][0] = max(5, menu[2][0] - 5)
            elif step == 3: 
                menu[3][0] = max(1, menu[3][0] - 1)
            elif step == 4 and records: 
                record_index = (record_index - 1) % len(records)
            menu_funcs[step](menu)
            time.sleep(BUTTON_DEBOUNCE_S)

        # 버튼4: 이전 메뉴 / 종료 (길게 누르기)
        elif GPIO.input(btn[3]) == GPIO.HIGH:
            t_start = time.time()
            while GPIO.input(btn[3]) == GPIO.HIGH:
                if time.time() - t_start > BUTTON_HOLD_S:
                    long_beep()
                    raise KeyboardInterrupt
                time.sleep(0.05)
            ok_sound()
            step = max(0, step - 1)
            menu_funcs[step](menu)
            time.sleep(BUTTON_DEBOUNCE_S)
        
        else: 
            time.sleep(0.01)

except KeyboardInterrupt:
    print("\nShutting down...")
finally:
    GPIO.cleanup()
    setRGB(0, 0, 0)
    setText("")