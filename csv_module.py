# csv_module.py (파일명을 import 하기 좋게 csv_module로 가정하거나 기존 이름 사용)
import csv
import os

def save_to_csv(timestamp, w, s, total):
    """
    계산된 데이터를 전달받아 파일에 저장하는 함수
    """
    file_name = 'workout_log.csv'
    file_exists = os.path.isfile(file_name)
    
    with open(file_name, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['날짜', '단일운동시간', '세트수', '총운동시간'])
        
        # 전달받은 데이터 저장
        writer.writerow([timestamp, w, s, total])
        print(f"[저장 완료] {timestamp} - 총 {total}초")

# datetime_Handler.py 맨 아래에 추가
if __name__ == "__main__":
    # 테스트용 가짜 데이터 (모드 1, 운동 30초, 휴식 10초, 3세트)
    test_menu = [[1], [30], [10], [3]]
    
    print("--- 운동 종료 시뮬레이션 ---")
    success = process_and_save_workout(test_menu)
    
    if success:
        print("테스트 성공: workout_log.csv 파일을 확인해보세요.")
    else:
        print("테스트 실패")