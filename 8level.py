#최근 6개월 기록만 누적하는 함수

import datetime

def load_total_last_6months():
    records_path = "/home/pi/iot/records.txt"
    cutoff = datetime.date.today() - datetime.timedelta(days=180)

    total = 0

    try:
        with open(records_path, "r") as f:
            lines = f.readlines()

        for line in lines:
            date_str, sec_str = line.strip().split(",")
            y, m, d = map(int, date_str.split("-"))
            record_date = datetime.date(y, m, d)

            if record_date >= cutoff:
                total += int(sec_str)

    except:
        total = 0

    # 최신 누적 시간 total_time.txt 갱신
    with open("/home/pi/iot/total_time.txt", "w") as f:
        f.write(str(total))

    return total


# 레벨계산(0~10)
def calc_level(total_seconds):
    level = total_seconds // 100
    return min(level, 10)


#lcd자신의 레벨 표시 수정
def show_level():
    total = load_total_last_6months()  # 최근 6개월 누적만 사용
    level = calc_level(total)

    setRGB(200, 100, 255)
    setText(f"LEVEL {level}\n{total}s")


#운동 끝날 때, 저장 후 레벨 반영하도록 수정 ( 6개월만 으로 수정)
save_record(m[1][0], m[3][0])
load_total_last_6months()   # ← 추가
