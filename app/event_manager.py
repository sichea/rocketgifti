import uuid
import random
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app import db
from app.config import (
    ADMIN_TELEGRAM_IDS, GIFTISHOW_API_BASE, GIFTISHOW_CUSTOM_AUTH_CODE,
    GIFTISHOW_CUSTOM_AUTH_TOKEN, GIFTISHOW_USER_ID, GIFTISHOW_DEV_YN,
    GIFTISHOW_CALLBACK_NO
)
from app.giftishow import GiftishowClient
from app.draw_service import perform_draw_and_send

CB_JOIN_EVENT = "ev_join"

def gen_event_id():
    return "EV_" + uuid.uuid4().hex[:8].upper()

async def cmd_create_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /event <goods_code> <winner_count> <draw_type> [quiz_answer]
    예: /event 1234567 10 RANDOM
    """
    tid = update.effective_user.id
    if tid not in ADMIN_TELEGRAM_IDS:
        return

    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "사용법: /event <상품코드> <당첨자수> <추첨방식:RANDOM/FCFS/QUIZ> [퀴즈정답]\n"
            "예: /event 0000109761 5 RANDOM"
        )
        return

    goods_code = args[0]
    try:
        winner_count = int(args[1])
    except ValueError:
        await update.message.reply_text("당첨자 수는 숫자여야 합니다.")
        return
        
    draw_type = args[2].upper()
    quiz_answer = args[3] if len(args) > 3 else None

    product = db.get_product(goods_code)
    if not product:
        await update.message.reply_text(f"상품코드 {goods_code} 를 찾을 수 없습니다.")
        return
        
    event_id = gen_event_id()
    title = f"{product['name']} 이벤트 ({winner_count}명)"
    
    db.create_event(
        event_id=event_id, 
        admin_id=tid, 
        title=title, 
        goods_code=goods_code, 
        winner_count=winner_count, 
        draw_type=draw_type
    )

    keyboard = [
        [InlineKeyboardButton("🎉 이벤트 참여하기", callback_data=f"{CB_JOIN_EVENT}:{event_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = (
        f"🎁 <b>{title}</b> 이벤트 오픈!\n\n"
        f"방식: {draw_type}\n"
    )
    if draw_type == "QUIZ":
        msg += "⚠️ 이 메시지에 <b>[정답 단어]</b>를 답장(Reply) 형식으로 달아서 참여해주세요!\n"
    else:
        msg += "👇 아래 버튼을 눌러 바로 참여하세요!\n"

    await update.message.reply_photo(
        photo=product["image_url_big"] or product["image_url"],
        caption=msg,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    await update.message.reply_text(f"이벤트가 생성되었습니다.\nID: `{event_id}`\n\n추첨 명령어: `/draw {event_id}`", parse_mode="Markdown")


async def on_join_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    tid = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    data = query.data

    parts = data.split(":")
    if len(parts) < 2:
        return
        
    event_id = parts[1]
    event = db.get_event(event_id)
    
    if not event or event.get("status") != "OPEN":
        await query.answer("종료되었거나 없는 이벤트입니다.", show_alert=True)
        return

    draw_type = event.get("draw_type")
    quiz_answer = None

    if draw_type == "QUIZ":
        await query.answer("퀴즈 이벤트는 참여 버튼이 아닌 정답 메시지로 답장(Reply)해야 합니다.", show_alert=True)
        return

    res = db.join_event(event_id, tid, username, quiz_answer)
    if res == "ALREADY_JOINED":
        await query.answer("이미 참여하셨습니다! 행운을 빕니다 🍀", show_alert=True)
    elif res == "SUCCESS":
        await query.answer("이벤트에 정상 참여되었습니다! 🎉", show_alert=True)
    else:
        await query.answer("참여 중 오류가 발생했습니다.", show_alert=True)


async def on_quiz_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    사용자가 이벤트 메시지에 답장으로 퀴즈 정답을 보냈을 때 수집.
    (간단한 구현: 답장한 메시지가 이벤트 알림이라고 가정하거나 개선 필요)
    """
    pass # 구체적 구현은 추가 과제


async def cmd_draw_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /draw <event_id>
    """
    tid = update.effective_user.id
    if tid not in ADMIN_TELEGRAM_IDS:
        return

    args = context.args
    if not args:
        await update.message.reply_text("사용법: `/draw <event_id>`", parse_mode="Markdown")
        return
        
    event_id = args[0]
    event = db.get_event(event_id)
    if not event:
        await update.message.reply_text("이벤트를 찾을 수 없습니다.")
        return
        
    if event.get("status") != "OPEN":
        await update.message.reply_text("이미 추첨 완료되었거나 닫힌 이벤트입니다.")
        return

    participants = db.get_event_participants(event_id)
    if not participants:
        await update.message.reply_text("참여자가 없습니다.")
        return

    db.set_event_status(event_id, "CLOSED")
    
    winner_count = event.get("winner_count", 1)
    draw_type = event.get("draw_type", "RANDOM")
    
    winners = []
    if draw_type == "FCFS":
        # 선착순
        winners = participants[:winner_count]
    else:
        # RANDOM or QUIZ (퀴즈는 일단 참여자 중에서 랜덤)
        random.shuffle(participants)
        winners = participants[:winner_count]

    if not winners:
        await update.message.reply_text("당첨자를 선정하지 못했습니다.")
        return

    winner_names = [f"@{w.get('username', 'Unknown')}" for w in winners]
    
    msg = f"🎉 <b>[{event['title']}] 추첨 완료!</b>\n\n⚠️ 당첨자들에게 기프티콘을 곧바로 다이렉트(DM) 발송합니다!"
    status_msg = await update.message.reply_text(msg, parse_mode="HTML")
    
    # 코어 추첨 서비스 호출
    result = await perform_draw_and_send(event_id, bot=context.bot)
    
    if result["success"]:
        await status_msg.reply_text(f"✅ 총 {result['successCount']}/{result['totalWinners']} 명에게 발송 되었습니다.")
    else:
        await status_msg.reply_text(f"❌ 실패: {result['message']}")
