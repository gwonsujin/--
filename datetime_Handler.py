import datetime_logic as logic  # 계산 모듈 import
import csv_module as saver      # 저장 모듈 import

def process_and_save_workout(menu_data):
    """
    [통합 함수]
    1. 계산 모듈을 통해 데이터를 가공하고
    2. 저장 모듈을 통해 CSV로 기록함
    """
    try:
        # 1. 데이터 계산 (logic 모듈 사용)
        # 반환값: (날짜, 운동시간, 세트수, 총시간)
        timestamp, w_time, sets, total_sec = logic.calculate_total_time(menu_data)
        
        # 2. 데이터 저장 (saver 모듈 사용)
        # 계산된 데이터를 인자로 넘겨줌
        saver.save_to_csv(timestamp, w_time, sets, total_sec)
        
        return True # 성공 시 True 반환
        
    except Exception as e:
        print(f"에러 발생: {e}")
        return False