import time
import threading
import random
from gpiozero import PWMLED

# ========================================
# Multi-LED Configuration (Direct GPIO)
# ========================================
# gpiozero 라이브러리를 사용하여 PWM 및 다중 LED 제어
# 기본 핀: GPIO 5, 6, 13, 19 (4개 LED)

class MultiLightController:
    def __init__(self, pins=[5, 6, 13, 19]):
        self.running = False
        self.current_mode = None
        self.thread = None
        self.music_playing = False
        
        # PWMLED 객체 리스트 생성
        self.leds = []
        try:
            for p in pins:
                self.leds.append(PWMLED(p))
        except Exception as e:
            print(f"LED Init Error: {e}")

    def _all_off(self):
        """모든 LED 끄기"""
        for led in self.leds:
            led.value = 0

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
        for led in self.leds:
            led.close()

    # --- Effects ---

    def _effect_exercise(self):
        """운동 모드: Random Pop (APT Style)"""
        while self.running:
            try:
                if self.music_playing:
                    # APT의 톡톡 튀는 느낌: 랜덤한 LED가 짧게 반짝임
                    target_led = random.choice(self.leds)
                    target_led.value = 1.0 # 켜짐
                    
                    # 비트감: 0.05 ~ 0.2초 (빠름)
                    duration = random.uniform(0.05, 0.2)
                    time.sleep(duration)
                    
                    target_led.value = 0 # 꺼짐
                    
                    # 다음 비트까지 아주 짧은 대기 (Staccato)
                    time.sleep(random.uniform(0.02, 0.1))
                else:
                    # 심장박동 (Heartbeat) - 전체 동기화
                    for led in self.leds: led.value = 1.0
                    time.sleep(0.1)
                    for led in self.leds: led.value = 0
                    time.sleep(0.1)
                    for led in self.leds: led.value = 1.0
                    time.sleep(0.1)
                    for led in self.leds: led.value = 0
                    time.sleep(1.0)
            except: pass

    def _effect_rest(self):
        """휴식 모드: Synchronized Breathing"""
        # gpiozero의 pulse()를 쓰면 좋지만, 스레드 제어를 위해 직접 구현
        while self.running:
            try:
                # Inhale
                for i in range(0, 101, 2):
                    if not self.running: break
                    val = i / 100.0
                    for led in self.leds: led.value = val
                    time.sleep(0.04)
                
                time.sleep(0.5)
                
                # Exhale
                for i in range(100, -1, -2):
                    if not self.running: break
                    val = i / 100.0
                    for led in self.leds: led.value = val
                    time.sleep(0.04)
                    
                time.sleep(1.0)
            except: pass

    def _effect_pause(self):
        """일시정지: Wave / Chase (순차 점멸)"""
        while self.running:
            try:
                for led in self.leds:
                    if not self.running: break
                    led.value = 1.0
                    time.sleep(0.2)
                    led.value = 0
                time.sleep(0.1)
            except: pass

    def _effect_complete(self):
        """완료: Chaos Strobe (무작위 고속 점멸)"""
        while self.running:
            try:
                for led in self.leds:
                    led.value = random.choice([0, 1])
                time.sleep(0.05)
            except: pass
