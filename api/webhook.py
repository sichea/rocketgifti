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

@app.get("/api/ping")
async def ping():
    """상태 체크용 (Health Check)"""
    return {"status": "ok", "app": "rocketgifti-bot"}
