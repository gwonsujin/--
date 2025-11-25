# csv_module.py
import csv
import os

# 인자에 level 추가됨
def save_to_csv(timestamp, w, s, total, level):
    """
    계산된 데이터 + 레벨을 전달받아 파일에 저장하는 함수
    """
    file_name = 'workout_log.csv'
    file_exists = os.path.isfile(file_name)
    
    with open(file_name, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # 파일이 처음 만들어질 때 헤더 작성 (여기에 '등급' 추가)
        if not file_exists:
            writer.writerow(['날짜', '단일운동시간', '세트수', '총운동시간', '등급'])
        
        # 데이터 저장 (마지막에 level 추가)
        writer.writerow([timestamp, w, s, total, level])
        print(f"[저장 완료] {timestamp} - 총 {total}초 ({level})")

# [csv_module.py] 맨 아래에 추가할 코드

def get_total_accumulated_time():
    """
    CSV 파일을 읽어서 지금까지의 총 운동 시간(초) 합계를 반환
    """
    file_name = 'workout_log.csv'
    total_sum = 0
    
    if not os.path.isfile(file_name):
        return 0
        
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None) # 헤더 건너뛰기
            
            for row in reader:
                if len(row) >= 4:
                    # 4번째 열(인덱스 3)이 '총운동시간'입니다.
                    total_sum += int(row[3])
    except Exception as e:
        print(f"읽기 에러: {e}")
        return 0
        
    return total_sum