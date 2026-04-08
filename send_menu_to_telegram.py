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
    """시스템의 curl 명령어를 사용하여 데이터를 가져옵니다."""
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
        "-k", 
        api_url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, check=True)
        raw_output = result.stdout.decode('utf-8', errors='ignore')
        if not raw_output.strip(): return []
        
        data = json.loads(raw_output)
        # 중요: 신구대 API는 {"data": [...]} 형식으로 응답함
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return []
    except Exception as e:
        print(f"API 호출 오류 (SEQ={bistro_seq}): {e}")
        return []

def parse_west_lunch(content):
    """서관 중식 데이터(한식+양식) 파싱"""
    k, w = "정보없음", "정보없음"
    content = content.replace("**", "").replace('"', '').strip()
    if "한식" in content and "양식" in content:
        parts = content.split("양식")
        k = parts[0].replace("한식", "").strip(", ").strip()
        w = parts[1].strip(", ").strip()
    elif "한식" in content:
        k = content.replace("한식", "").strip()
    elif "양식" in content:
        w = content.replace("양식", "").strip()
    else:
        k = content
    return k, w

def get_today_menu():
    today = datetime.now()
    target_dt = today.strftime("%Y%m%d")
    weekday_str = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"][today.weekday()]
    
    menu = {
        "date": f"{today.year}년 {today.month}월 {today.day}일 ({weekday_str})",
        "west": {"조식": "정보없음", "한식": "정보없음", "양식": "정보없음", "분식": "정보없음"},
        "mirae": {"조식": "정보없음", "중식": "정보없음", "분식": "정보없음"}
    }

    # 1. 서관 (7)
    items_west = fetch_menu_data_using_curl("7")
    for item in items_west:
        if item.get("STD_DT") == target_dt:
            menu["west"]["조식"] = item.get("CARTE1_CONT", "정보없음").replace("\r\n", " ").strip()
            k, w = parse_west_lunch(item.get("CARTE2_CONT", ""))
            menu["west"]["한식"] = k
            menu["west"]["양식"] = w
            menu["west"]["분식"] = item.get("CARTE3_CONT", "정보없음").replace("\r\n", " ").strip()

    # 2. 미래창의관 (5)
    items_mirae = fetch_menu_data_using_curl("5")
    for item in items_mirae:
        if item.get("STD_DT") == target_dt:
            menu["mirae"]["조식"] = item.get("CARTE1_CONT", "정보없음").replace("\r\n", " ").strip()
            menu["mirae"]["중식"] = item.get("CARTE2_CONT", "정보없음").replace("\r\n", " ").strip()
            menu["mirae"]["분식"] = item.get("CARTE3_CONT", "정보없음").replace("\r\n", " ").strip()

    return menu

def send_to_telegram(text):
    import urllib.request
    import ssl
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    context = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, context=context) as response:
            return json.loads(response.read().decode()).get("ok", False)
    except: return False

if __name__ == "__main__":
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
        print(f"✅ 전송 완료!\n{msg}")
    else:
        print("❌ 전송 실패")
