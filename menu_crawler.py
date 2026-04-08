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
    """curl 명령어로 학교 서버의 차단을 우회하여 데이터를 가져옵니다."""
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
        "-H", "User-Agent: Mozilla/5.0",
        "-k", 
        api_url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, check=True)
        raw_output = result.stdout.decode('utf-8', errors='ignore')
        if not raw_output.strip(): return []
        
        data = json.loads(raw_output)
        # 응답이 {"data": [...]} 또는 [...] 인 경우 모두 대응
        items = []
        if isinstance(data, dict) and "data" in data:
            items = data["data"]
        elif isinstance(data, list):
            items = data
            
        print(f"📡 SEO(SEQ={bistro_seq}): {len(items)}개의 식단 데이터 수집 성공")
        return items
    except Exception as e:
        print(f"⚠️ API 호출 오류 (SEQ={bistro_seq}): {e}")
        return []

def parse_west_lunch(content):
    """서관 중식(한식/양식)을 텍스트 분석해서 나눕니다."""
    k, w = "정보없음", "정보없음"
    if not content: return k, w
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
    # today = datetime(2026, 4, 8) # 테스트 시 날짜 고정
    target_dt = today.strftime("%Y%m%d")
    weekday_str = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"][today.weekday()]
    
    res = {
        "date": f"{today.year}년 {today.month}월 {today.day}일 ({weekday_str})",
        "west": {"조식": "정보없음", "한식": "정보없음", "양식": "정보없음", "분식": "정보없음"},
        "mirae": {"조식": "정보없음", "중식": "정보없음", "분식": "정보없음"}
    }

    # 서관 수집
    west_items = fetch_menu_data_using_curl("7")
    for item in west_items:
        if item.get("STD_DT") == target_dt:
            res["west"]["조식"] = item.get("CARTE1_CONT", "정보없음").replace("\r\n", " ").strip(", ")
            k, w = parse_west_lunch(item.get("CARTE2_CONT", ""))
            res["west"]["한식"] = k
            res["west"]["양식"] = w
            res["west"]["분식"] = item.get("CARTE3_CONT", "정보없음").replace("\r\n", " ").strip(", ")

    # 미래창의관 수집
    mirae_items = fetch_menu_data_using_curl("5")
    for item in mirae_items:
        if item.get("STD_DT") == target_dt:
            res["mirae"]["조식"] = item.get("CARTE1_CONT", "정보없음").replace("\r\n", " ").strip(", ")
            res["mirae"]["중식"] = item.get("CARTE2_CONT", "정보없음").replace("\r\n", " ").strip(", ")
            res["mirae"]["분식"] = item.get("CARTE3_CONT", "정보없음").replace("\r\n", " ").strip(", ")

    return res

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
            result = json.loads(response.read().decode())
            if result.get("ok"):
                return True
            else:
                print(f"❌ 텔레그램 서버 응답 오류: {result}")
                return False
    except Exception as e:
        print(f"❌ 텔레그램 전송 중 예외 발생: {e}")
        return False

if __name__ == "__main__":
    print("-" * 50)
    print("🚀 신구대학교 자동 식단 수집 봇 시작")
    print("-" * 50)
    
    current_menu = get_today_menu()
    
    msg_body = f"🏫 *신구대학교 오늘의 식단*\n📅 {current_menu['date']}\n\n"
    msg_body += "📍 *학생식당 (서관)*\n"
    msg_body += f"• 조식: {current_menu['west']['조식']}\n"
    msg_body += f"• 중식(한식): {current_menu['west']['한식']}\n"
    msg_body += f"• 중식(양식): {current_menu['west']['양식']}\n"
    msg_body += f"• 분식: {current_menu['west']['분식']}\n\n"
    msg_body += "📍 *학생식당 (미래창의관)*\n"
    msg_body += f"• 조식: {current_menu['mirae']['조식']}\n"
    msg_body += f"• 중식: {current_menu['mirae']['중식']}\n"
    msg_body += f"• 분식: {current_menu['mirae']['분식']}\n\n"
    msg_body += "맛있게 드세요! 😋"

    print("📢 텔레그램 전송 시도 중...")
    if send_to_telegram(msg_body):
        print(f"✅ 전송 성골! (일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    else:
        print("❌ 전송 실패 (위 오류 메시지를 확인하세요)")
    print("-" * 50)
