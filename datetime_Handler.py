# datetime_Handler.py
import datetime_logic as logic   # 계산 모듈
import csv_module as saver       # 저장 모듈 (수정됨)
import level_module as leveling  # 레벨 모듈 (새로 만드셨죠?)

def process_and_save_workout(menu_data):
    """
    [통합 함수]
    1. 계산 모듈로 데이터 가공
    2. 레벨 모듈로 등급 판별
    3. 저장 모듈로 CSV 기록 (레벨 포함)
    """
    try:
        # 1. 데이터 계산
        timestamp, w_time, sets, total_sec = logic.calculate_total_time(menu_data)
        
        # 2. 레벨 판별 (독립 실행)
        current_level = leveling.determine_level(total_sec)
        
        # 화면 출력 (확인용)
        print(f"--------------------------")
        print(f"결과: {total_sec}초 -> {current_level}")
        print(f"--------------------------")

        # 3. 데이터 저장 (인자에 current_level 추가!)
        saver.save_to_csv(timestamp, w_time, sets, total_sec, current_level)
        
        return True 
        
    except Exception as e:
        print(f"에러 발생: {e}")
        return False

if __name__ == "__main__":
    # 테스트용 데이터
    test_menu = [[1], [30], [10], [5]] # 150초 예상 -> 1 레벨
    
    print("--- 테스트 시작 ---")
    process_and_save_workout(test_menu)