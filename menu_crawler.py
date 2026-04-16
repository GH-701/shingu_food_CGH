import sys
import os
import requests
import datetime
import urllib3
import ssl
import json
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_

# Windows 터미널 한글 깨짐 방지
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# -----------------------------------------------------------------------------
# 설정 / Configuration
# -----------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8217138523:AAEMf_f9j5Imr91HVFTSgtaXled1tHdo-9Y').strip()
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '8330266163').strip()

# 신구대학교 API URL
API_URL = "https://www.shingu.ac.kr/ajaxf/FR_BST_SVC/BistroCarteInfo.do"
MENU_ID = "1630"

# 식당 정보 (교직원식당 제외)
BISTROS = [
    {"name": "학생식당(미래창의관)", "seq": "5", "icon": "🎓"},
    {"name": "학생식당(서관)", "seq": "7", "icon": "🍱"}
]

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# -----------------------------------------------------------------------------
# SSL Adapter (학교 서버 보안 환경 대응용)
# -----------------------------------------------------------------------------
class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        # 보안 수준을 하향 조정하여 오래된 서버와 통신 가능하게 함
        ctx = ssl_.create_urllib3_context(ciphers='DEFAULT:@SECLEVEL=1')
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=ctx
        )

# -----------------------------------------------------------------------------
# 주요 기능 함수
# -----------------------------------------------------------------------------
def get_kst_now():
    """한국 시간(KST) 현재 시간 반환 (GitHub Actions 대응)"""
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)

import html

def send_telegram_message(message):
    """텔레그램 메시지 전송"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[오류] 텔레그램 토큰 또는 채팅 ID가 설정되지 않았습니다.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"❌ 텔레그램 전송 실패 (상태 코드: {response.status_code})")
            print(f"응답 내용: {response.text}")
            # HTML 모드 오류일 경우 일반 텍스트로 재시도
            if "can't parse entities" in response.text:
                print("🔄 HTML 파싱 오류로 인해 일반 텍스트 모드로 재시도합니다...")
                payload.pop('parse_mode')
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    print("✅ 일반 텍스트로 전환하여 전송 성공")
                    return
        
        response.raise_for_status()
        print("✅ 텔레그램 메시지 전송 성공")
    except Exception as e:
        print(f"💥 텔레그램 통신 중 치명적 오류 발생: {e}")

def get_menu_data(seq):
    """API를 통해 특정 식당의 주간 식단 데이터를 가져옴"""
    now = get_kst_now()
    monday = now - datetime.timedelta(days=now.weekday())
    friday = monday + datetime.timedelta(days=6)
    
    start_day = monday.strftime("%Y.%m.%d")
    end_day = friday.strftime("%Y.%m.%d")
    
    payload = {
        'MENU_ID': MENU_ID,
        'BISTRO_SEQ': seq,
        'START_DAY': start_day,
        'END_DAY': end_day
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    session = requests.Session()
    session.mount('https://', LegacySSLAdapter())
    
    try:
        response = session.post(API_URL, data=payload, headers=headers, verify=False, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️ [{seq}] 식단 수집 실패: {e}")
        return None

def main():
    print("🚀 신구대학교 오늘의 학식 배송 시작")
    
    kst_now = get_kst_now()
    today_key = kst_now.strftime("%Y%m%d")
    display_date = kst_now.strftime("%Y년 %m월 %d일 (%a)")
    
    # HTML 태그 사용하여 가독성 높임
    final_message = f"<b>🍱 신구대학교 오늘의 학식</b>\n📅 {display_date}\n\n"
    
    for bistro in BISTROS:
        bistro_name = bistro['name']
        bistro_seq = bistro['seq']
        bistro_icon = bistro['icon']
        
        print(f"🔍 [{bistro_name}] 데이터를 읽어오는 중...")
        json_data = get_menu_data(bistro_seq)
        
        menu_text = "❕ 등록된 식단 정보가 없습니다."
        
        if json_data:
            items = json_data.get('data', []) if isinstance(json_data, dict) else json_data
            
            todays_item = None
            if isinstance(items, list):
                for item in items:
                    if item.get('STD_DT') == today_key:
                        todays_item = item
                        break
            
            if todays_item:
                message_lines = []
                for i in range(1, 6): # CARTE1 ~ CARTE5 수집
                    nm = (todays_item.get(f'CARTE{i}_NM') or '').strip()
                    cont = (todays_item.get(f'CARTE{i}_CONT') or '').strip()
                    if nm or cont:
                        if nm: 
                            safe_nm = html.escape(nm)
                            message_lines.append(f"<b>[{safe_nm}]</b>")
                        if cont:
                            # 특수문자 HTML 엔티티 처리 및 줄바꿈 정리
                            clean_cont = cont.replace('\r\n', '\n').replace('\n', ', ').strip(', ')
                            safe_cont = html.escape(clean_cont)
                            message_lines.append(f"{safe_cont}")
                        message_lines.append("")
                
                if message_lines:
                    menu_text = "\n".join(message_lines).strip()
        
        final_message += f"{bistro_icon} <b>{bistro_name}</b>\n"
        final_message += f"{menu_text}\n"
        final_message += "───────────────────\n\n"
    
    final_message += "맛있게 드세요! 😋"
    send_telegram_message(final_message.strip())

if __name__ == "__main__":
    main()
