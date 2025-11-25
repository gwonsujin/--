# datetime_logic.py
import datetime

def calculate_total_time(menu_data):
    """
    menu 리스트를 입력받아 운동 결과 데이터를 반환하는 함수
    """
    w_time = menu_data[1][0] # 운동시간
    sets = menu_data[3][0]   # 세트수
    
    total_seconds = w_time * sets
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 4개의 값을 튜플로 반환
    return now, w_time, sets, total_seconds