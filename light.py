import time
import threading
import random
from grovepi import *

# ========================================
# Multi-LED Configuration (GrovePi)
# ========================================
# GrovePi 포트 D4, D5, D6 사용
# D5, D6: PWM 지원 (Breathing 효과 가능)
# D4: PWM 미지원 (Digital ON/OFF만 가능)

class MultiLightController:
    def __init__(self, pins=[4, 5, 6]):
        self.running = False
        self.current_mode = None
        self.thread = None
        self.music_playing = False
        
        self.pins = pins
        self._setup_gpio()

    def _setup_gpio(self):
        """GPIO 초기화"""
        try:
            for p in self.pins:
                pinMode(p, "OUTPUT")
                analogWrite(p, 0) # 끄기
        except Exception as e:
            print(f"Light Init Error: {e}")

    def _all_off(self):
        """모든 LED 끄기"""
        try:
            for p in self.pins:
                analogWrite(p, 0)
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
        self._all_off()

    # --- Effects ---

    def _effect_exercise(self):
        """운동 모드: Random Pop (APT Style)"""
        while self.running:
            try:
                if self.music_playing:
                    # APT의 톡톡 튀는 느낌
                    target_pin = random.choice(self.pins)
                    digitalWrite(target_pin, 1)
                    
                    duration = random.uniform(0.05, 0.2)
                    time.sleep(duration)
                    
                    digitalWrite(target_pin, 0)
                    time.sleep(random.uniform(0.02, 0.1))
                else:
                    # 심장박동 (Heartbeat)
                    for p in self.pins: digitalWrite(p, 1)
                    time.sleep(0.1)
                    for p in self.pins: digitalWrite(p, 0)
                    time.sleep(0.1)
                    for p in self.pins: digitalWrite(p, 1)
                    time.sleep(0.1)
                    for p in self.pins: digitalWrite(p, 0)
                    time.sleep(1.0)
            except: pass

    def _effect_rest(self):
        """휴식 모드: Breathing (PWM)"""
        # D5, D6는 PWM 가능. D4는 PWM 불가하므로 그냥 켜두거나 깜빡임.
        # 여기서는 D4도 같이 PWM 시도하되, 안되면 디지털로 동작할 것임.
        while self.running:
            try:
                # Inhale
                for duty in range(0, 256, 5):
                    if not self.running: break
                    for p in self.pins:
                        try:
                            analogWrite(p, duty)
                        except:
                            digitalWrite(p, 1 if duty > 127 else 0)
                    time.sleep(0.04)
                
                time.sleep(0.5)
                
                # Exhale
                for duty in range(255, -1, -5):
                    if not self.running: break
                    for p in self.pins:
                        try:
                            analogWrite(p, duty)
                        except:
                            digitalWrite(p, 1 if duty > 127 else 0)
                    time.sleep(0.04)
                    
                time.sleep(1.0)
            except: pass

    def _effect_pause(self):
        """일시정지: Wave / Chase"""
        while self.running:
            try:
                for p in self.pins:
                    if not self.running: break
                    digitalWrite(p, 1)
                    time.sleep(0.2)
                    digitalWrite(p, 0)
                time.sleep(0.1)
            except: pass

    def _effect_complete(self):
        """완료: Chaos Strobe"""
        while self.running:
            try:
                for p in self.pins:
                    digitalWrite(p, random.choice([0, 1]))
                time.sleep(0.05)
            except: pass
