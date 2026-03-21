import sys
import os
from fastapi import FastAPI, Request

# 상위 디렉터리 경로 추가 (app 패키지 및 main.py 로드를 위함)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import get_app
from telegram import Update

app = FastAPI()

# 봇 인스턴스 전역 생성 (Vercel 환경에서 재사용 됨)
telegram_app = get_app()
is_initialized = False

@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    """
    Vercel Serverless Endpoint for Telegram Webhook.
    """
    global is_initialized
    if not is_initialized:
        await telegram_app.initialize()
        is_initialized = True

    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True, "message": "Update processed"}

@app.post("/api/internal/draw")
async def internal_draw(event_id: str):
    """
    웹 어드민에서 호출하는 실시간 추첨 실행 API.
    """
    from app.draw_service import perform_draw_and_send
    
    # 텔레그램 봇 객체 가져오기 (DM 발송용)
    bot = telegram_app.bot
    
    result = await perform_draw_and_send(event_id, bot=bot)
    
    if result["success"]:
        return {"ok": True, "successCount": result["successCount"], "totalWinners": result["totalWinners"]}
    else:
        return {"ok": False, "message": result["message"]}

@app.get("/api/ping")
async def ping():
    """상태 체크용 (Health Check)"""
    return {"status": "ok", "app": "rocketgifti-bot"}
