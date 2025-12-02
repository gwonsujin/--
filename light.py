import RPi.GPIO as GPIO
import time
import threading
import random

# ========================================
# Dual LED Pin Configuration
# ========================================
# LED_LEFT = 5   # D5 Port (나중에 메인 코드에서 설정하거나 여기서 주석 해제)
# LED_RIGHT = 6  # D6 Port

class DualLightController:
    def __init__(self, pin_left=5, pin_right=6):
        self.running = False
        self.current_mode = None
        self.thread = None
        self.music_playing = False
        
        # 핀 설정 (인스턴스 생성 시 전달받거나 기본값 사용)
        self.LED_LEFT = pin_left
        self.LED_RIGHT = pin_right
        
        self.pwm_left = None
        self.pwm_right = None
        
        self._setup_gpio()

    def _setup_gpio(self):
        """GPIO 초기화"""
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.LED_LEFT, GPIO.OUT)
        GPIO.setup(self.LED_RIGHT, GPIO.OUT)
        
        # PWM 초기화 (100Hz) - 숨쉬기 효과용
        self.pwm_left = GPIO.PWM(self.LED_LEFT, 100)
        self.pwm_right = GPIO.PWM(self.LED_RIGHT, 100)
        self.pwm_left.start(0)
        self.pwm_right.start(0)

    def _all_off(self):
        """모든 LED 끄기"""
        if self.pwm_left: self.pwm_left.ChangeDutyCycle(0)
        if self.pwm_right: self.pwm_right.ChangeDutyCycle(0)
        # PWM 모드가 아닐 때를 대비해 확실히 끔
        GPIO.output(self.LED_LEFT, 0)
        GPIO.output(self.LED_RIGHT, 0)

    def set_music_playing(self, playing):
        """음악 재생 상태 설정 (운동 모드 패턴 변경용)"""
        self.music_playing = playing

    def set_mode(self, mode):
        """
        모드 설정 및 효과 실행
        mode: 'EXERCISE', 'REST', 'PAUSE', 'COMPLETE', 'OFF'
        """
        if self.current_mode == mode:
            return

        self.stop() # 이전 효과 중지
        self.current_mode = mode
        self.running = True

        if mode == 'EXERCISE':
            self.thread = threading.Thread(target=self._effect_exercise)
        elif mode == 'REST':
            self.thread = threading.Thread(target=self._effect_rest)
        elif mode == 'PAUSE':
            self.thread = threading.Thread(target=self._effect_pause)
        elif mode == 'COMPLETE':
            self.thread = threading.Thread(target=self._effect_complete)
        elif mode == 'OFF':
            self._all_off()
            self.running = False
            return

        if self.thread:
            self.thread.start()

    def stop(self):
        """현재 실행 중인 효과 중지"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join()
        self._all_off()
        self.current_mode = None

    def cleanup(self):
        """종료 시 리소스 해제"""
        self.stop()
        if self.pwm_left: self.pwm_left.stop()
        if self.pwm_right: self.pwm_right.stop()
        # GPIO.cleanup()은 메인 코드에서 관리하는 것이 좋을 수 있음
        # 여기서는 LED 핀만 정리
        GPIO.cleanup([self.LED_LEFT, self.LED_RIGHT])

    # --- Effects ---

    def _effect_exercise(self):
        """운동 모드: 리듬 매치 (Rhythm Match)"""
        # 음악이 나오면 비트에 맞춰 랜덤 점멸, 아니면 심장박동
        while self.running:
            if self.music_playing:
                # 랜덤 패턴: 왼쪽, 오른쪽, 혹은 둘 다
                pattern = random.choice(['LEFT', 'RIGHT', 'BOTH'])
                duration = random.uniform(0.1, 0.3) # 빠른 비트
                
                if pattern == 'LEFT':
                    GPIO.output(self.LED_LEFT, 1)
                    GPIO.output(self.LED_RIGHT, 0)
                elif pattern == 'RIGHT':
                    GPIO.output(self.LED_LEFT, 0)
                    GPIO.output(self.LED_RIGHT, 1)
                else:
                    GPIO.output(self.LED_LEFT, 1)
                    GPIO.output(self.LED_RIGHT, 1)
                
                time.sleep(duration)
                self._all_off()
                time.sleep(0.1)
            else:
                # 심장박동 (Heartbeat) - 두 번 쿵쿵
                GPIO.output(self.LED_LEFT, 1)
                GPIO.output(self.LED_RIGHT, 1)
                time.sleep(0.1)
                self._all_off()
                time.sleep(0.1)
                GPIO.output(self.LED_LEFT, 1)
                GPIO.output(self.LED_RIGHT, 1)
                time.sleep(0.1)
                self._all_off()
                time.sleep(1.0) # 휴식

    def _effect_rest(self):
        """휴식 모드: 숨쉬기 (Breathing)"""
        # 양쪽 LED가 천천히 밝아졌다 어두워짐
        while self.running:
            # Inhale
            for dc in range(0, 101, 2):
                if not self.running: break
                self.pwm_left.ChangeDutyCycle(dc)
                self.pwm_right.ChangeDutyCycle(dc)
                time.sleep(0.04)
            
            time.sleep(0.5)
            
            # Exhale
            for dc in range(100, -1, -2):
                if not self.running: break
                self.pwm_left.ChangeDutyCycle(dc)
                self.pwm_right.ChangeDutyCycle(dc)
                time.sleep(0.04)
                
            time.sleep(1.0)

    def _effect_pause(self):
        """일시정지: 비상등 (Hazard Light)"""
        # 동시에 깜빡임
        while self.running:
            GPIO.output(self.LED_LEFT, 1)
            GPIO.output(self.LED_RIGHT, 1)
            time.sleep(0.5)
            self._all_off()
            time.sleep(0.5)

    def _effect_complete(self):
        """완료: 경찰차 스트로브 (Strobe)"""
        # 좌우 번갈아 가며 빠르게 점멸
        while self.running:
            # 왼쪽 3번
            for _ in range(3):
                if not self.running: break
                GPIO.output(self.LED_LEFT, 1)
                time.sleep(0.05)
                GPIO.output(self.LED_LEFT, 0)
                time.sleep(0.05)
            
            # 오른쪽 3번
            for _ in range(3):
                if not self.running: break
                GPIO.output(self.LED_RIGHT, 1)
                time.sleep(0.05)
                GPIO.output(self.LED_RIGHT, 0)
                time.sleep(0.05)
