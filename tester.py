# tester.py
import datetime_logic as logic
import csv_module as saver
import level_module as leveling

# 가상의 운동 메뉴 (모드1, 30초, 10초휴식, 5세트)
mock_menu = [[1], [30], [10], [5]]

print("=== 모듈 통합 테스트 시작 ===")

# 1. 계산 테스트
print("\n[1] 계산 모듈 테스트...")
timestamp, w, s, total = logic.calculate_total_time(mock_menu)
print(f" -> 결과: {timestamp}, {w}초x{s}세트 = {total}초")

# 2. 레벨 테스트
print("\n[2] 레벨 모듈 테스트...")
lv = leveling.determine_level(total)
print(f" -> 결과: {lv}")

# 3. 저장 테스트
print("\n[3] CSV 저장 테스트...")
try:
    saver.save_to_csv(timestamp, w, s, total, lv)
    print(" -> 저장 성공 (workout_log.csv 확인해보세요)")
except Exception as e:
    print(f" -> 저장 실패: {e}")

# 4. 누적 시간 읽기 테스트
print("\n[4] 누적 시간 읽기 테스트...")
acc = saver.get_total_accumulated_time()
print(f" -> 현재까지 총 누적 운동시간: {acc}초")

print("\n=== 테스트 종료 ===")