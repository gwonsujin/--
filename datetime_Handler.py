################################################################################
# 파일 4: datetime_Handler.py
# 목적: 모듈 통합 및 전체 프로세스 처리
# 사용법: process_and_save_workout(menu_data) 호출
################################################################################

import datetime_logic as logic   # 계산 모듈
import csv_module as saver       # 저장 모듈
import level_module as leveling  # 레벨 모듈

def process_and_save_workout(menu_data):
    """
    [통합 함수]
    1. 계산 모듈로 데이터 가공
    2. 레벨 모듈로 등급 판별
    3. 저장 모듈로 CSV 기록 (레벨 포함)
    
    Args:
        menu_data: [[모드], [운동시간], [휴식시간], [세트수]]
    
    Returns:
        bool: 성공 여부
    """
    try:
        # 1. 데이터 계산
        timestamp, w_time, sets, total_sec = logic.calculate_total_time(menu_data)
        
        # 2. 레벨 판별
        current_level = leveling.determine_level(total_sec)
        
        # 화면 출력 (확인용)
        print(f"--------------------------")
        print(f"결과: {total_sec}초 -> {current_level}")
        print(f"--------------------------")

        # 3. 데이터 저장
        saver.save_to_csv(timestamp, w_time, sets, total_sec, current_level)
        
        return True 
        
    except Exception as e:
        print(f"에러 발생: {e}")
        return False


# 테스트 코드
if __name__ == "__main__":
    test_menu = [[1], [30], [10], [5]]  # 150초 예상 -> 1 레벨
    
    print("--- 테스트 시작 ---")
    process_and_save_workout(test_menu)