# level_module.py

def determine_level(total_seconds):
    """
    총 운동 시간을 입력받아 레벨(문자열)을 반환하는 함수
    - 0~99초: 0레벨
    - 100~199초: 1레벨
    ...
    - 900~999초: 9레벨
    - 1000초 이상: 운동 왕
    """
    if total_seconds >= 1000:
        return "!!! 운동 왕 (Master) !!!"
    
    # 파이썬의 정수 나누기(//)를 사용하면 100단위로 쉽게 레벨을 구할 수 있습니다.
    # 예: 250 // 100 = 2 (레벨)
    level = total_seconds // 100
    
    return f"{level} 레벨"