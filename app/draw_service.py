import random
from datetime import datetime
from app import db
from app.config import (
    GIFTISHOW_API_BASE, GIFTISHOW_CUSTOM_AUTH_CODE,
    GIFTISHOW_CUSTOM_AUTH_TOKEN, GIFTISHOW_USER_ID, GIFTISHOW_DEV_YN,
    GIFTISHOW_CALLBACK_NO
)
from app.giftishow import GiftishowClient

async def perform_draw_and_send(event_id: str, bot=None):
    """
    웹이나 명령어 어디서든 공통으로 사용할 수 있는 추첨 및 발송 코어 함수.
    """
    event = db.get_event(event_id)
    if not event or event.get("status") != "OPEN":
        return {"success": False, "message": "이벤트가 닫혀있거나 없습니다."}

    participants = db.get_event_participants(event_id)
    if not participants:
        return {"success": False, "message": "참여자가 없습니다."}

    # 이벤트 종료 처리
    db.set_event_status(event_id, "CLOSED")
    
    winner_count = event.get("winner_count", 1)
    draw_type = event.get("draw_type", "RANDOM")
    
    winners = []
    if draw_type == "FCFS":
        winners = participants[:winner_count]
    else:
        random.shuffle(participants)
        winners = participants[:winner_count]

    if not winners:
        return {"success": False, "message": "당첨자 선정 실패"}

    # 기프티쇼 클라이언트 준비
    client = GiftishowClient(
        base_url=GIFTISHOW_API_BASE,
        custom_auth_code=GIFTISHOW_CUSTOM_AUTH_CODE,
        custom_auth_token=GIFTISHOW_CUSTOM_AUTH_TOKEN,
        user_id=GIFTISHOW_USER_ID,
        dev_yn=GIFTISHOW_DEV_YN
    )
    
    success_count = 0
    for w in winners:
        winner_tid = w["telegram_id"]
        db.update_participant_send_result(event_id, winner_tid, is_winner=True)
        
        tr_id = f"ev_{datetime.now().strftime('%Y%m%d')}_{event_id[:4]}_{random.randint(100, 999)}"[:25]
        
        try:
            resp = client.send_coupon(
                tr_id=tr_id,
                phone_no="01000000000",
                goods_code=event["goods_code"],
                gubun="I",
                callback_no=GIFTISHOW_CALLBACK_NO,
                mms_title="이벤트 당첨",
                mms_msg="축하합니다! 이벤트에 당첨되었습니다."
            )
            inner = resp.get("result", {})
            result = inner.get("result", {})
            pin = result.get("pinNo")
            img = result.get("couponImgUrl")
            
            if pin or img:
                db.update_participant_send_result(
                    event_id, winner_tid,
                    send_status="SUCCESS", tr_id=tr_id, 
                    coupon_pin=pin, coupon_img_url=img
                )
                success_count += 1
                
                # 텔레그램 DM 발송 (봇 객체가 있을 경우)
                if bot:
                    dm_lines = [f"🎉 <b>[{event['title']}] 당첨을 축하합니다!</b>\n"]
                    if img:
                        try: await bot.send_photo(chat_id=winner_tid, photo=img, caption="교환 바코드")
                        except: pass
                    if pin:
                        dm_lines.append(f"PIN: <code>{pin}</code>")
                    dm_lines.append("\n⚠️ 유효기간 30일 / 기간연장·환불 불가")
                    try: await bot.send_message(chat_id=winner_tid, text="\n".join(dm_lines), parse_mode="HTML")
                    except: pass
            else:
                db.update_participant_send_result(event_id, winner_tid, send_status="FAILED", tr_id=tr_id)
        except Exception as e:
            print(f"Draw bulk error for {winner_tid}:", e)
            db.update_participant_send_result(event_id, winner_tid, send_status="FAILED_EXP")
            
    return {"success": True, "successCount": success_count, "totalWinners": len(winners)}
