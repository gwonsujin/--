import RPi.GPIO as GPIO
import time
import math
import pygame
from grovepi import *
import grove_rgb_lcd as lcd
import os

# ========================================
# 1. 상수 및 설정 (Constants & Configuration)
# ========================================

# GPIO 핀 설정
# 버튼: B1(값 증가), B2(다음/선택), B3(값 감소), B4(이전/종료)
BTN_PINS = [22, 23, 24, 25] 
STOP_BUTTON_PIN = BTN_PINS[3] # B4는 정지 버튼으로도 사용

# 부저 및 센서 핀
BUZZER_PIN = 3
PIR_PIN = 8      # 모션 센서
DHT_PIN = 7      # 온습도 센서
DHT_TYPE = 0     # 0: DHT11, 1: DHT22

# 파일 저장 경로 설정
BASE_DIR = "/home/pi/iot"
RECORDS_FILE = "exercise_time.txt" 
RECORDS_PATH = os.path.join(BASE_DIR, RECORDS_FILE)
TOTAL_TIME_PATH = os.path.join(BASE_DIR, "total_time.txt")
MUSIC_PATH = os.path.join(BASE_DIR, "music.mp3")

# 타이머 및 센서 설정 값
BUTTON_DEBOUNCE_S = 0.15
BUTTON_HOLD_S = 2.0

PIR_SAMPLES = 3
PIR_INTERVAL_S = 0.1
PIR_MOTION_THRESHOLD = 2

PAUSE_ON_NO_MOTION_S = 8  # 움직임 감지 모드에서 움직임 없을 시 일시정지 대기 시간
PAUSE_ON_MOTION_S = 8     # 움직임 없음 모드에서 움직임 감지 시 일시정지 대기 시간

# 음악 초기화
try:
    pygame.mixer.init()
    sound_sample = pygame.mixer.music
    if os.path.exists(MUSIC_PATH):
        sound_sample.load(MUSIC_PATH)
        sound_sample.set_volume(0.1)
    else:
        print(f"음악 파일을 찾을 수 없습니다: {MUSIC_PATH}")
        sound_sample = None
except Exception as e:
    print(f"오디오 초기화 오류: {e}")
    sound_sample = None

# 초기 메뉴 설정 값
# [모드, 운동시간, 휴식시간, 세트수]
menu = [
    [1],  # 모드 (1: 움직임, 2: 정지, 3: 환경, 4: 기록, 5: 레벨)
    [30], # 운동 시간 (초)
    [10], # 휴식 시간 (초)
    [3]   # 세트 수
]

records = []
record_index = 0

# ========================================
# 2. 하드웨어 초기화 (Hardware Initialization)
# ========================================
def init_hardware():
    """GPIO 및 GrovePi 센서 초기화"""
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    # 버튼 초기화
    for pin in BTN_PINS:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    
    # GrovePi 센서 초기화
    try:
        pinMode(PIR_PIN, "INPUT")
        pinMode(BUZZER_PIN, "OUTPUT")
    except Exception as e:
        print(f"하드웨어 초기화 오류: {e}")

# ========================================
# 3. 사운드 및 알림 (Sound & Buzzer)
# ========================================
def beep_ms(ms: int):
    """지정된 시간(ms) 동안 부저 울림"""
    try:
        digitalWrite(BUZZER_PIN, 1)
        time.sleep(ms / 1000.0)
        digitalWrite(BUZZER_PIN, 0)
    except Exception:
        pass

def short_beep(times=1, dur_ms=120, gap_ms=80):
    """짧은 비프음 (횟수, 지속시간, 간격 조절 가능)"""
    for _ in range(times):
        beep_ms(dur_ms)
        if times > 1:
            time.sleep(gap_ms / 1000.0)

def long_beep(dur_ms=400):
    """긴 비프음"""
    beep_ms(dur_ms)

def state_change_beep():
    """상태 변경 시 아주 짧은 비프음"""
    beep_ms(50)

# 효과음 매핑
ok_sound = short_beep                               # 확인/선택
cancel_sound = lambda: short_beep(times=2, dur_ms=80) # 취소/경고
alert_sound = long_beep                             # 알림 (운동/휴식 전환 등)
start_sound = lambda: short_beep(times=2)           # 시작

# 배경음 제어
def play_bgm():
    if sound_sample:
        try:
            if not sound_sample.get_busy():
                sound_sample.play(-1) # 반복 재생
        except: pass

def stop_bgm():
    if sound_sample:
        try:
            sound_sample.stop()
        except: pass

def pause_bgm():
    if sound_sample:
        try:
            sound_sample.pause()
        except: pass

def resume_bgm():
    if sound_sample:
        try:
            sound_sample.unpause()
        except: pass

# ========================================
# 4. LCD 디스플레이 (LCD Display)
# ========================================
def set_lcd_color(r, g, b):
    try:
        lcd.setRGB(r, g, b)
    except Exception:
        pass

def set_lcd_text(text):
    try:
        lcd.setText(text)
    except Exception:
        pass

def get_progress_bar(current, total, width=10):
    """진행 상황을 텍스트 바 형태로 반환"""
    if total <= 0:
        return "█" * width
    fill_len = int(width * current / total)
    fill_len = max(0, min(fill_len, width))
    return f'{"█" * fill_len}{"░" * (width - fill_len)}'

# ========================================
# 5. 환경 센서 로직 (Environment Logic - Mode 3)
# ========================================
def classify_env(temp, hum):
    """온습도에 따른 환경 상태 평가"""
    # 적정 온도: 18~22도, 적정 습도: 40~60%
    if 18 <= temp <= 22 and 40 <= hum <= 60:
        return "GOOD"
    # 약간 벗어난 범위
    if 15 <= temp <= 27 and (30 <= hum < 40 or 60 < hum <= 70):
        return "MODERATE"
    # 그 외
    return "BAD"

def show_env_info():
    """온습도 정보를 읽어 LCD에 표시"""
    try:
        temp, hum = dht(DHT_PIN, DHT_TYPE)
        if math.isnan(temp) or math.isnan(hum):
            set_lcd_color(255, 0, 0)
            set_lcd_text("Sensor Error")
            return

        status = classify_env(temp, hum)
        
        # 상태에 따른 색상 변경
        if status == "GOOD":
            set_lcd_color(0, 255, 0)      # 초록
        elif status == "MODERATE":
            set_lcd_color(255, 255, 0)    # 노랑
        else:
            set_lcd_color(255, 0, 0)      # 빨강

        line1 = f"Status:{status}"
        line2 = f"T:{temp:4.1f}C H:{hum:4.1f}%"
        set_lcd_text(line1 + "\n" + line2)
    except Exception as e:
        print(f"DHT 오류: {e}")
        set_lcd_color(255, 0, 0)
        set_lcd_text("DHT Error")

# ========================================
# 6. 기록 관리 로직 (Record Logic - Mode 4 & 5)
# ========================================
def load_records():
    """파일에서 운동 기록을 불러옴"""
    global records
    try:
        if os.path.exists(RECORDS_PATH):
            with open(RECORDS_PATH, "r") as f:
                lines = f.readlines()
                # 유효한 라인만 파싱 (날짜, 시간)
                records = []
                for l in lines:
                    if "," in l:
                        parts = l.strip().split(",")
                        if len(parts) >= 2:
                            records.append((parts[0], int(parts[1])))
        else:
            records = []
    except Exception as e:
        print(f"기록 불러오기 오류: {e}")
        records = []

def save_record(exercise_s, total_sets):
    """운동 기록과 누적 시간을 파일에 저장"""
    # 디렉토리 확인 및 생성
    if not os.path.exists(BASE_DIR):
        try:
            os.makedirs(BASE_DIR)
            print(f"디렉토리 생성: {BASE_DIR}")
        except Exception as e:
            print(f"디렉토리 생성 실패: {e}")
            return

    total_ex = exercise_s * total_sets
    today = time.strftime("%Y-%m-%d")

    # 1. 일별 기록 저장 (exercise_time.txt)
    try:
        with open(RECORDS_PATH, "a") as f:
            f.write(f"{today},{total_ex}\n")
        print(f"기록 저장됨: {today}, {total_ex}초")
    except Exception as e:
        print(f"기록 저장 오류: {e}")

    # 2. 누적 시간 업데이트 (total_time.txt)
    try:
        total = 0
        if os.path.exists(TOTAL_TIME_PATH):
            try:
                with open(TOTAL_TIME_PATH, "r") as f:
                    content = f.read().strip()
                    if content:
                        total = int(content)
            except:
                total = 0
            
        total += total_ex
        
        with open(TOTAL_TIME_PATH, "w") as f:
            f.write(str(total))
        print(f"총 누적 시간 업데이트: {total}초")
    except Exception as e:
        print(f"누적 시간 업데이트 오류: {e}")

def show_record_page(index):
    """특정 인덱스의 기록을 LCD에 표시"""
    global records
    load_records() # 최신 기록 불러오기
    
    if not records:
        set_lcd_color(255, 100, 100)
        set_lcd_text("NO RECORDS")
        return

    # 인덱스 범위 조정
    if index >= len(records): index = len(records) - 1
    if index < 0: index = 0
    
    date, sec = records[index]
    set_lcd_color(255, 165, 0) # 주황색
    set_lcd_text(f"Rec {index+1}/{len(records)}\n{date} {sec}s")

def show_level():
    """누적 시간에 따른 레벨 표시 (Mode 5)"""
    try:
        if os.path.exists(TOTAL_TIME_PATH):
            with open(TOTAL_TIME_PATH, "r") as f:
                total = int(f.read().strip())
        else:
            total = 0
    except:
        total = 0

    level = min(10, total // 10)   # 10초당 1레벨 (예시)
    percent = min(100, total)      # 100초면 100% (예시)

    set_lcd_color(200, 100, 255)
    set_lcd_text(f"LEVEL {level}\n{percent}%")

# ========================================
# 7. 타이머 및 운동 로직 (Timer & Exercise Logic)
# ========================================
def read_pir_stable():
    """PIR 센서 값을 안정적으로 읽기 (노이즈 필터링)"""
    samples = []
    for _ in range(PIR_SAMPLES):
        try:
            val = digitalRead(PIR_PIN)
            samples.append(val)
        except Exception:
            samples.append(0)
        time.sleep(PIR_INTERVAL_S)
    
    motion_count = sum(samples)
    return 1 if motion_count >= PIR_MOTION_THRESHOLD else 0

def responsive_sleep(duration_s):
    """
    지정된 시간 동안 대기하며 정지 버튼 입력을 확인
    정지 버튼이 눌리면 True 반환
    """
    steps = 10
    for _ in range(int(duration_s * steps)):
        if GPIO.input(STOP_BUTTON_PIN) == GPIO.HIGH:
            return True # 정지 신호 감지
        time.sleep(1 / steps)
    return False

def wait_for_resume(required_state):
    """
    일시정지 상태에서 재개를 기다림
    필요한 상태(움직임/멈춤)가 감지되면 재개
    """
    while GPIO.input(STOP_BUTTON_PIN) == GPIO.LOW:
        motion = read_pir_stable()
        if motion == required_state:
            return False # 정상 재개
        time.sleep(0.3)
    return True # 정지 버튼 눌림

def check_pause_condition(mode, motion, last_valid_state_time):
    """모션/정지 상태에 따른 일시정지 조건 확인"""
    now = time.time()
    diff = now - last_valid_state_time

    if mode == 1:  # 움직임 감지 모드
        if motion == 0 and diff >= PAUSE_ON_NO_MOTION_S:
            return "No Motion!"
    elif mode == 2: # 정지 감지 모드
        if motion == 1 and diff >= PAUSE_ON_MOTION_S:
            return "Motion Detect!"
    return None

def handle_pause(reason, required_state):
    """일시정지 처리 및 재개 대기"""
    pause_bgm()
    cancel_sound()

    set_lcd_color(255, 165, 0)
    set_lcd_text(f"PAUSED\n{reason}")

    if wait_for_resume(required_state):
        stop_bgm()
        set_lcd_color(255, 0, 0)
        set_lcd_text("Stopped\nReturning...")
        time.sleep(1.5)
        return False # 정지됨

    ok_sound()
    resume_bgm()
    return True # 재개됨

def run_single_set(set_num, total_sets, mode, exercise_s, rest_s):
    """한 세트의 운동 실행"""
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

        # 일시정지 조건 체크
        reason = check_pause_condition(mode, motion, last_valid_state_time)
        if reason:
            if not handle_pause(reason, required_state):
                return False # 정지 버튼 눌림
            last_valid_state_time = time.time()
            last_pir_state = -1

        # 정상 상태면 유효 시간 갱신
        if motion == required_state:
            last_valid_state_time = time.time()

        # 화면 갱신
        status_text = "MOVE" if motion == 1 else "STAY"
        remaining_s = exercise_s - timer_s
        bar = get_progress_bar(timer_s, exercise_s, 10)
        set_lcd_color(0, 255, 0)
        set_lcd_text(f"M{mode} Set {set_num}/{total_sets} {status_text}\n{bar} {remaining_s}s")

        if responsive_sleep(1):
            stop_bgm()
            set_lcd_color(255, 0, 0)
            set_lcd_text("Stopped\nReturning...")
            time.sleep(1.5)
            return False

        timer_s += 1

    stop_bgm()
    alert_sound()

    # 마지막 세트가 아니면 휴식
    if set_num < total_sets:
        for t in range(rest_s):
            remaining_s = rest_s - t
            bar = get_progress_bar(t, rest_s, 10)
            set_lcd_color(0, 150, 255)
            set_lcd_text(f"Rest {set_num}/{total_sets}\n{bar} {remaining_s}s")

            if responsive_sleep(1):
                set_lcd_color(255, 0, 0)
                set_lcd_text("Stopped\nReturning...")
                time.sleep(1.5)
                return False

        start_sound() # 다음 세트 시작 알림
    
    return True

def run_exercise_session(m):
    """전체 운동 세션 실행"""
    try:
        pinMode(PIR_PIN, "INPUT")
        time.sleep(0.5)
    except Exception as e:
        print(f"PIR 초기화 오류: {e}")

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
    set_lcd_color(255, 0, 255)
    set_lcd_text("Complete!\nPress any btn")
    
    # 기록 저장
    save_record(exercise_s, total_sets)

    while all(GPIO.input(p) == GPIO.LOW for p in BTN_PINS):
        time.sleep(0.05)
    time.sleep(BUTTON_DEBOUNCE_S)

def start_exercise(m):
    """운동 시작 진입점"""
    # 모드 3, 4, 5에서는 운동 시작 불가
    if m[0][0] >= 3:
        set_lcd_color(255, 0, 0)
        set_lcd_text("Cannot Start\nin this Mode")
        time.sleep(1.0)
        return 0

    print("\n=== 운동 시작 ===")
    print(f"Mode: {m[0][0]}, 운동: {m[1][0]}s, 휴식: {m[2][0]}s, 세트: {m[3][0]}")
    
    run_exercise_session(m) 
    
    print("=== 운동 종료 ===")
    set_lcd_color(0, 255, 0)
    set_lcd_text("Back to Menu")
    time.sleep(0.5)
    return 0  # 메뉴 초기 화면으로 복귀

# ========================================
# 8. 메뉴 화면 함수 (Menu Display Functions)
# ========================================
def show_mode(m):
    """모드 선택 화면"""
    mode = m[0][0]
    if mode == 1:
        set_lcd_color(0, 255, 0)
        set_lcd_text("Mode 1\nMove Detection")
    elif mode == 2:
        set_lcd_color(0, 100, 255)
        set_lcd_text("Mode 2\nStay Detection")
    elif mode == 3:
        show_env_info()
    elif mode == 4:
        show_record_page(record_index)
    elif mode == 5:
        show_level()

def show_exercise(m):
    """운동 시간 설정 화면"""
    set_lcd_color(255, 255, 255)
    set_lcd_text(f"Exercise Time\n{m[1][0]}s")

def show_rest(m):
    """휴식 시간 설정 화면"""
    set_lcd_color(255, 255, 255)
    set_lcd_text(f"Rest Time\n{m[2][0]}s")

def show_sets(m):
    """세트 수 설정 화면"""
    mode = m[0][0]
    exer = m[1][0]
    rest = m[2][0]
    sets = m[3][0]
    
    line1 = f"M:{mode} Ex:{exer} R:{rest}"
    line2 = f"Sets:{sets} (Press>)"
    
    set_lcd_color(0, 255, 255)
    set_lcd_text(f"{line1}\n{line2}")

# ========================================
# 9. 메인 루프 (Main Loop)
# ========================================
def main():
    global step, record_index
    
    menu_funcs = [show_mode, show_exercise, show_rest, show_sets]
    step = 0
    
    init_hardware()
    set_lcd_color(0, 255, 0)
    print("프로그램 시작! (Ctrl+C로 종료)")
    
    menu_funcs[step](menu)
    
    try:
        while True:
            # --- 버튼 1: 값 증가 (Up / +) ---
            if GPIO.input(BTN_PINS[0]) == GPIO.HIGH:
                ok_sound()
                if step == 0: # 모드 변경
                    menu[0][0] += 1
                    if menu[0][0] > 5: menu[0][0] = 1 # 1~5 순환
                elif step == 1: # 운동 시간 증가
                    menu[1][0] += 10
                elif step == 2: # 휴식 시간 증가
                    menu[2][0] += 5
                elif step == 3: # 세트 수 증가
                    menu[3][0] += 1
                
                # 기록 모드(4)일 때 페이지 넘김
                if step == 0 and menu[0][0] == 4:
                    load_records()
                    record_index = (record_index + 1) % max(1, len(records))

                menu_funcs[step](menu)
                time.sleep(BUTTON_DEBOUNCE_S)
            
            # --- 버튼 2: 다음 단계 / 선택 (Next / Select) ---
            elif GPIO.input(BTN_PINS[1]) == GPIO.HIGH:
                ok_sound()
                
                # 모드 3, 4, 5에서는 다음 단계로 넘어가지 않고 화면 갱신만 함
                if step == 0 and menu[0][0] >= 3:
                     menu_funcs[step](menu)
                else:
                    step = step + 1
                    if step >= len(menu_funcs):  # 설정 완료 시 운동 시작
                        step = start_exercise(menu)
                    
                    menu_funcs[step](menu)
                
                time.sleep(BUTTON_DEBOUNCE_S)

            # --- 버튼 3: 값 감소 (Down / -) ---
            elif GPIO.input(BTN_PINS[2]) == GPIO.HIGH:
                ok_sound()
                if step == 0: # 모드 변경
                    menu[0][0] -= 1
                    if menu[0][0] < 1: menu[0][0] = 5 # 1~5 순환
                elif step == 1: # 운동 시간 감소
                    menu[1][0] = max(10, menu[1][0] - 10)
                elif step == 2: # 휴식 시간 감소
                    menu[2][0] = max(5, menu[2][0] - 5)
                elif step == 3: # 세트 수 감소
                    menu[3][0] = max(1, menu[3][0] - 1)
                
                # 기록 모드(4)일 때 페이지 이전
                if step == 0 and menu[0][0] == 4:
                    load_records()
                    record_index = (record_index - 1) % max(1, len(records))
                
                menu_funcs[step](menu)
                time.sleep(BUTTON_DEBOUNCE_S)

            # --- 버튼 4: 이전 / 종료 (Prev / Exit) ---
            elif GPIO.input(BTN_PINS[3]) == GPIO.HIGH:
                press_start = time.time()
                
                # 길게 누르면 종료 확인
                while GPIO.input(BTN_PINS[3]) == GPIO.HIGH:
                    if time.time() - press_start > BUTTON_HOLD_S:
                        print("\n=== 프로그램 종료 (버튼 길게 누름) ===")
                        long_beep()
                        raise KeyboardInterrupt 
                    time.sleep(0.05)
                
                # 짧게 누르면 이전 메뉴로
                if time.time() - press_start < 0.5:
                    ok_sound()
                    step -= 1
                    if step < 0: step = 0
                    menu_funcs[step](menu)
                    
                time.sleep(BUTTON_DEBOUNCE_S)
                
            else:
                time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        stop_bgm()
        GPIO.cleanup()
        set_lcd_color(128, 128, 128)
        set_lcd_text("Goodbye!")

if __name__ == "__main__":
    main()
