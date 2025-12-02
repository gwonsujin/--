from light import MultiLightController
import time

# 테스트할 핀 번호 (빵판에 연결한 핀 번호로 수정 가능)
TEST_PINS = [5, 6, 13, 19] 
# 4개 LED 구성

def main():
    print("=== LED Breadboard Test ===")
    print(f"Pins: {TEST_PINS}")
    
    # 컨트롤러 초기화
    lc = MultiLightController(pins=TEST_PINS)
    
    try:
        print("\n1. Exercise Mode (Heartbeat)")
        lc.set_music_playing(False)
        lc.set_mode('EXERCISE')
        time.sleep(5)
        
        print("\n2. Exercise Mode (Random Pop - APT Style)")
        lc.set_music_playing(True)
        time.sleep(5)
        
        print("\n3. Rest Mode (Sync Breathing)")
        lc.set_mode('REST')
        time.sleep(8)
        
        print("\n4. Pause Mode (Wave/Chase)")
        lc.set_mode('PAUSE')
        time.sleep(5)
        
        print("\n5. Complete Mode (Chaos Strobe)")
        lc.set_mode('COMPLETE')
        time.sleep(5)
        
        print("\nTest Complete.")
        
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        lc.cleanup()
        print("Cleanup Done.")

if __name__ == "__main__":
    main()
