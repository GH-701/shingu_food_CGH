import os
import urllib.request
import urllib.parse
import json
import ssl
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# 설정 / Configuration
# -----------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8292351740:AAGv71z1VveMHpnNwNXvgx1uBWJOF8EcaH0')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '8419206166')

def fetch_api_data(bistro_seq, start_day, end_day):
    """신구대학교 API에서 데이터를 가져옵니다."""
    api_url = "https://www.shingu.ac.kr/ajaxf/FR_BST_SVC/BistroCarteInfo.do"
    params = {
        "pageNo": "1",
        "MENU_ID": "1630",
        "START_DAY": start_day,
        "END_DAY": end_day,
        "BISTRO_SEQ": bistro_seq
    }
    data = urllib.parse.urlencode(params).encode('utf-8')
    req = urllib.request.Request(api_url, data=data, method='POST')
    
    # 브라우저처럼 보이게 하기 위해 헤더 추가
    req.add_header('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8')
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
    
    context = ssl._create_unverified_context()
    
    try:
        with urllib.request.urlopen(req, context=context) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"API 호출 오류 (BISTRO_SEQ={bistro_seq}): {e}")
        return []

def get_today_menu():
    """오늘의 식단을 크롤링합니다."""
    today = datetime.now()
    # today = datetime(2026, 4, 8) # 테스트용
    
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    start_day = monday.strftime("%Y.%m.%d")
    end_day = friday.strftime("%Y.%m.%d")
    target_dt = today.strftime("%Y%m%d")
    weekday_str = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"][today.weekday()]
    
    menu_info = {
        "date": f"{today.year}년 {today.month}월 {today.day}일 ({weekday_str})",
        "west": {"breakfast": "정보 없음", "lunch_k": "정보 없음", "lunch_w": "정보 없음", "snack": "정보 없음"},
        "mirae": {"breakfast": "정보 없음", "lunch": "정보 없음", "snack": "정보 없음"}
    }

    # 1. 서관 (SEQ=7)
    data_west = fetch_api_data("7", start_day, end_day)
    for item in data_west:
        if item.get("BISTRO_DT") == target_dt:
            content = item.get("DIET_CONTENT", "").replace("\r\n", ", ").strip()
            div_nm = item.get("BISTRO_DIV_NM", "")
            if "조식" in div_nm: menu_info["west"]["breakfast"] = content
            elif "한식" in div_nm: menu_info["west"]["lunch_k"] = content
            elif "양식" in div_nm: menu_info["west"]["lunch_w"] = content
            elif "분식" in div_nm: menu_info["west"]["snack"] = content

    # 2. 미래창의관 (SEQ=5)
    data_mirae = fetch_api_data("5", start_day, end_day)
    for item in data_mirae:
        if item.get("BISTRO_DT") == target_dt:
            content = item.get("DIET_CONTENT", "").replace("\r\n", ", ").strip()
            div_nm = item.get("BISTRO_DIV_NM", "")
            if "조식" in div_nm: menu_info["mirae"]["breakfast"] = content
            elif "분식" in div_nm: menu_info["mirae"]["snack"] = content
            else: menu_info["mirae"]["lunch"] = content # 보통 중식

    return menu_info

def format_message(menu):
    """메시지 포맷팅"""
    msg = f"🏫 *신구대학교 오늘의 식단*\n📅 {menu['date']}\n\n"
    
    msg += "📍 *학생식당 (서관)*\n"
    msg += f"• 조식: {menu['west']['breakfast']}\n"
    msg += f"• 중식(한식): {menu['west']['lunch_k']}\n"
    msg += f"• 중식(양식): {menu['west']['lunch_w']}\n"
    msg += f"• 분식: {menu['west']['snack']}\n\n"
    
    msg += "📍 *학생식당 (미래창의관)*\n"
    msg += f"• 조식: {menu['mirae']['breakfast']}\n"
    msg += f"• 중식: {menu['mirae']['lunch']}\n"
    msg += f"• 분식: {menu['mirae']['snack']}\n\n"
    
    msg += "맛있게 드세요! 😋"
    return msg

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    data_json = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=data_json, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode()).get("ok", False)
    except: return False

if __name__ == "__main__":
    menu = get_today_menu()
    formatted_text = format_message(menu)
    if send_to_telegram(formatted_text):
        print("✅ 오늘의 식단 전송 완료!")
    else:
        print("❌ 전송 실패")
