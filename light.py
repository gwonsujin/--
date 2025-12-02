import time
import threading
import random
from grovepi import *

# ========================================
# Dual LED Pin Configuration (GrovePi)
# ========================================
# A1 Port -> Pin 15
# A2 Port -> Pin 16
# Note: GrovePi Analog ports used as Digital Outputs

class DualLightController:
    def __init__(self, pin_left=15, pin_right=16):
        self.running = False
        self.current_mode = None
        self.thread = None
        self.music_playing = False
        
        # 핀 설정 (A1=15, A2=16)
        self.LED_LEFT = pin_left
        self.LED_RIGHT = pin_right
        
        self._setup_gpio()

    def _setup_gpio(self):
        """GPIO 초기화"""
        try:
            pinMode(self.LED_LEFT, "OUTPUT")
            pinMode(self.LED_RIGHT, "OUTPUT")
        except Exception as e:
            print(f"Light Init Error: {e}")

    def _all_off(self):
        """모든 LED 끄기"""
        try:
            digitalWrite(self.LED_LEFT, 0)
            digitalWrite(self.LED_RIGHT, 0)
        except: pass

    def set_music_playing(self, playing):
        """음악 재생 상태 설정"""
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
        # GrovePi는 별도의 cleanup이 필요 없거나 digitalWrite(0)으로 충분

    # --- Effects ---

    def _effect_exercise(self):
        """운동 모드: 리듬 매치 (Rhythm Match) - BGM: Rosé 'APT' Style"""
        while self.running:
            try:
                if self.music_playing:
                    # APT의 경쾌한 리듬에 맞춰 더 빠르고 끊어지는 느낌으로 점멸
                    pattern = random.choice(['LEFT', 'RIGHT', 'BOTH', 'BOTH', 'CROSS'])
                    # 비트감: 0.1~0.25초 (약 120~300 BPM 느낌)
                    duration = random.uniform(0.1, 0.25) 
                    
                    if pattern == 'LEFT':
                        digitalWrite(self.LED_LEFT, 1)
                        digitalWrite(self.LED_RIGHT, 0)
                    elif pattern == 'RIGHT':
                        digitalWrite(self.LED_LEFT, 0)
                        digitalWrite(self.LED_RIGHT, 1)
                    elif pattern == 'CROSS':
                        # 따닥 (빠르게 교차)
                        digitalWrite(self.LED_LEFT, 1)
                        digitalWrite(self.LED_RIGHT, 0)
                        time.sleep(0.05)
                        digitalWrite(self.LED_LEFT, 0)
                        digitalWrite(self.LED_RIGHT, 1)
                        duration -= 0.05 # 시간 보정
                    else:
                        digitalWrite(self.LED_LEFT, 1)
                        digitalWrite(self.LED_RIGHT, 1)
                    
                    time.sleep(max(0, duration))
                    self._all_off()
                    time.sleep(0.05) # 짧은 간격 (Staccato)
                else:
                    # 심장박동 (Heartbeat)
                    digitalWrite(self.LED_LEFT, 1)
                    digitalWrite(self.LED_RIGHT, 1)
                    time.sleep(0.1)
                    self._all_off()
                    time.sleep(0.1)
                    digitalWrite(self.LED_LEFT, 1)
                    digitalWrite(self.LED_RIGHT, 1)
                    time.sleep(0.1)
                    self._all_off()
                    time.sleep(1.0)
            except: pass

    def _effect_rest(self):
        """휴식 모드: 천천히 깜빡임 (Slow Blink)"""
        # A1/A2 포트는 PWM(숨쉬기) 지원이 어려우므로 천천히 깜빡임으로 대체
        while self.running:
            try:
                digitalWrite(self.LED_LEFT, 1)
                digitalWrite(self.LED_RIGHT, 1)
                time.sleep(1.0)
                digitalWrite(self.LED_LEFT, 0)
                digitalWrite(self.LED_RIGHT, 0)
                time.sleep(1.0)
            except: pass

    def _effect_pause(self):
        """일시정지: 비상등 (Hazard Light)"""
        while self.running:
            try:
                digitalWrite(self.LED_LEFT, 1)
                digitalWrite(self.LED_RIGHT, 1)
                time.sleep(0.5)
                self._all_off()
                time.sleep(0.5)
            except: pass

    def _effect_complete(self):
        """완료: 경찰차 스트로브 (Strobe)"""
        while self.running:
            try:
                # 왼쪽 3번
                for _ in range(3):
                    if not self.running: break
                    digitalWrite(self.LED_LEFT, 1)
                    time.sleep(0.05)
                    digitalWrite(self.LED_LEFT, 0)
                    time.sleep(0.05)
                
                # 오른쪽 3번
                for _ in range(3):
                    if not self.running: break
                    digitalWrite(self.LED_RIGHT, 1)
                    time.sleep(0.05)
                    digitalWrite(self.LED_RIGHT, 0)
                    time.sleep(0.05)
            except: pass
