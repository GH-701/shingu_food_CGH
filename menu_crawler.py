import os
import json
import subprocess
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# 설정 / Configuration
# -----------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8292351740:AAGv71z1VveMHpnNwNXvgx1uBWJOF8EcaH0')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '8419206166')

def fetch_menu_data_using_curl(bistro_seq):
    api_url = "https://www.shingu.ac.kr/ajaxf/FR_BST_SVC/BistroCarteInfo.do"
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    start_day = monday.strftime("%Y.%m.%d")
    end_day = friday.strftime("%Y.%m.%d")
    
    post_data = f"pageNo=1&MENU_ID=1630&BISTRO_SEQ={bistro_seq}&START_DAY={start_day}&END_DAY={end_day}"
    
    cmd = [
        "curl", "-s", "-X", "POST", 
        "-d", post_data,
        "-H", "Content-Type: application/x-www-form-urlencoded; charset=UTF-8",
        "-H", "Origin: https://www.shingu.ac.kr",
        "-H", "Referer: https://www.shingu.ac.kr/cms/FR_CON/index.do?MENU_ID=1630",
        "-H", "User-Agent: Mozilla/5.0",
        "-k", # 수집 시 SSL 우회
        api_url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, check=True)
        raw_output = result.stdout.decode('utf-8', errors='ignore')
        if not raw_output.strip(): return []
        data = json.loads(raw_output)
        items = data.get("data", []) if isinstance(data, dict) else data
        print(f"📡 SEQ={bistro_seq}: {len(items)}개의 데이터 수집됨")
        return items
    except: return []

def parse_west_lunch(content):
    k, w = "정보없음", "정보없음"
    if not content: return k, w
    content = content.replace("**", "").replace('"', '').strip()
    if "한식" in content and "양식" in content:
        parts = content.split("양식")
        k = parts[0].replace("한식", "").strip(", ").strip()
        w = parts[1].strip(", ").strip()
    elif "한식" in content: k = content.replace("한식", "").strip()
    elif "양식" in content: w = content.replace("양식", "").strip()
    else: k = content
    return k, w

def get_today_menu():
    today = datetime.now()
    target_dt = today.strftime("%Y%m%d")
    weekday_str = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"][today.weekday()]
    res = {
        "date": f"{today.year}년 {today.month}월 {today.day}일 ({weekday_str})",
        "west": {"조식": "정보없음", "한식": "정보없음", "양식": "정보없음", "분식": "정보없음"},
        "mirae": {"조식": "정보없음", "중식": "정보없음", "분식": "정보없음"}
    }
    # 데이터 수집
    for seq, key in [("7", "west"), ("5", "mirae")]:
        items = fetch_menu_data_using_curl(seq)
        for item in items:
            if item.get("STD_DT") == target_dt:
                res[key]["조식"] = item.get("CARTE1_CONT", "정보없음").replace("\r\n", " ").strip()
                if seq == "7":
                    k, w = parse_west_lunch(item.get("CARTE2_CONT", ""))
                    res[key]["한식"], res[key]["양식"] = k, w
                else:
                    res[key]["중식"] = item.get("CARTE2_CONT", "정보없음").replace("\r\n", " ").strip()
                res[key]["분식"] = item.get("CARTE3_CONT", "정보없음").replace("\r\n", " ").strip()
    return res

def send_to_telegram(text):
    """전송 시에도 SSL 우회(-k) 적용"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    
    cmd = [
        "curl", "-k", "-s", "-X", "POST", # -k 추가하여 강제 전송
        "-H", "Content-Type: application/json",
        "-d", json.dumps(payload),
        url
    ]
    try:
        print("📢 텔레그램 강제 전송 시도 중...")
        result = subprocess.run(cmd, capture_output=True, check=True)
        resp = json.loads(result.stdout.decode('utf-8'))
        if resp.get("ok"):
            print("✅ 텔레그램 전송 완벽 성공!")
            return True
        else:
            print(f"❌ 텔레그램 응답 에러: {resp}")
            return False
    except Exception as e:
        print(f"❌ 전송 오류: {e}")
        return False

if __name__ == "__main__":
    print("=" * 40)
    print("🍱 신구대 식단 로봇 (보안 우회 모드)")
    print("=" * 40)
    menu = get_today_menu()
    msg = f"🏫 *신구대학교 오늘의 식단*\n📅 {menu['date']}\n\n"
    msg += "📍 *학생식당 (서관)*\n"
    msg += f"• 조식: {menu['west']['조식']}\n"
    msg += f"• 중식(한식): {menu['west']['한식']}\n"
    msg += f"• 중식(양식): {menu['west']['양식']}\n"
    msg += f"• 분식: {menu['west']['분식']}\n\n"
    msg += "📍 *학생식당 (미래창의관)*\n"
    msg += f"• 조식: {menu['mirae']['조식']}\n"
    msg += f"• 중식: {menu['mirae']['중식']}\n"
    msg += f"• 분식: {menu['mirae']['분식']}\n\n"
    msg += "맛있게 드세요! 😋"
    if send_to_telegram(msg):
        print("🎉 모든 절차 완료!")
    print("=" * 40)
